import requests
import lzma
from tqdm import tqdm
import pathlib
import hashlib
import os
import csv
import yaml
import shutil
import logging
import ntpath

from artifactory import ArtifactoryPath
from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import re
from datetime import datetime
from github import Github
from pathlib import Path

from nebula.common import utils

log = logging.getLogger(__name__)


def listFD(url):
    page = requests.get(url).text
    soup = BeautifulSoup(page, "html.parser")
    return [url + "/" + node.get("href") for node in soup.find_all("a")]


def convert_to_datetime(date):
    if len(date) == 19:
        return datetime.strptime(date, "%Y_%m_%d-%H_%M_%S")
    else:
        return datetime.strptime(date[:10], "%Y_%m_%d")

def get_latest_release(links):
    latest = "0000_r1"
    for link in links:
        hdl_release = re.findall("hdl_[0-9]{4}_r[1-2]", link, re.IGNORECASE)
        release = re.findall("[0-9]{4}_r[1-2]", link, re.IGNORECASE)
        if len(hdl_release) == 1 and hdl_release[0].lower() > latest.lower():
            latest = hdl_release[0]
        else: 
            if len(release) == 1 and release[0].lower() > latest:
                latest = release[0]   
    return latest

def get_newest_folder(links):
    dates = []
    for link in links:
        folder = link.split("/")[-2]
        matched = re.match("20[1-2][0,1,2,3,4,5,6,7,8,9]_[0-3][0-9]_[0-3][0-9]", folder)
        is_match = bool(matched)

        if is_match:
            dates.append(folder)

    if not dates:
        raise Exception("No folders found")
    dates.sort(key=lambda date: convert_to_datetime(date))

    n = 0
    l = {"hdl":65, "linux":4, "bootpartition":75}
    for k,v in l.items():
        if re.search(k, links[-1]):
            n = v
    
    if len(listFD(links[-1])) < n:
        return dates[-2]
    else:
        return dates[-1]

def get_gitsha(url, daily=False, linux=False, hdl=False):
    dest = "outs"
    if not os.path.isdir(dest):
        os.mkdir(dest)
    file = os.path.join(dest, "properties.yaml")
    with open(file, "a+") as f:
        path = ArtifactoryPath(str(url))
        props = path.properties
        exp = "20[1-2][0-9]_[0-3][0-9]_[0-3][0-9]-[0-2][0-9]_[0-6][0-9]_[0-6][0-9]"
        if not daily:
            bootpartition = {"bootpartition_folder": re.findall(exp, url)[0], "linux_git_sha": props["linux_git_sha"][0], "hdl_git_sha": props["hdl_git_sha"][0]}
            yaml.dump(bootpartition, f)
        else:
            if hdl:
                hdl_props = {"hdl_folder": re.findall(exp, url)[0], "hdl_git_sha": props["git_sha"][0]}
                yaml.dump(hdl_props, f)
            if linux:            
                linux_props = {"linux_folder": re.findall(exp, url)[0], "linux_git_sha": props["git_sha"][0]}
                yaml.dump(linux_props, f)
    
def gen_url(ip, branch, folder, filename, addl, url_template):
    if branch == "master":
        if bool(re.search("boot_partition", url_template)):
            url = url_template.format(ip, branch, "", "")
            # folder = BUILD_DATE/PROJECT_FOLDER
            folder = get_newest_folder(listFD(url[:-1]))+'/'+str(folder)
            return url_template.format(ip, branch, folder, filename)
        elif bool(re.search("hdl", url_template)):
            url = url_template.format(ip, addl, "", "")
            folder = get_newest_folder(listFD(url[:-1]))+'/'+str(folder)
            return url_template.format(ip, addl, folder, filename)
        else:
            url = url_template.format(ip, "", "")
            # folder = BUILD_DATE/PROJECT_FOLDER
            folder = get_newest_folder(listFD(url[:-1]))+'/'+str(folder)
            return url_template.format(ip, folder, filename)
    else:
        url = url_template.format(ip, "", "", "")
        if branch == "release" or branch == "release_latest":
            if bool(re.search("hdl", url_template)):
                release_folder = get_latest_release(listFD(url))+'/'+ addl
            else:
                release_folder = get_latest_release(listFD(url))
        else:
            release_folder = branch if not bool(re.search("hdl", url_template)) else branch+'/'+ addl
        url = url_template.format(ip, release_folder, "", "")
        # folder = BUILD_DATE/PROJECT_FOLDER
        folder = get_newest_folder(listFD(url[:-1]))+'/'+str(folder)
        return url_template.format(ip, release_folder, folder, filename)

class downloader(utils):
    def __init__(self, http_server_ip=None, yamlfilename=None, board_name=None):
        self.reference_boot_folder = None
        self.devicetree_subfolder = None
        self.boot_subfolder = None
        self.hdl_folder = None
        self.http_server_ip = http_server_ip
        self.url= None
        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )

        self.soc= None
        self.kernel = None
        self.overlay = None
        self.update_defaults_from_yaml(
            yamlfilename, configname='board', board_name=board_name, attr = ["soc", "kernel", "overlay"]
        )

    def _download_firmware(self, device, release=None):
        if release == "master":
            release = None

        if "m2k" in device.lower() or "adalm-2000" in device.lower():
            dev = "m2k"
        elif "pluto" in device.lower():
            dev = "plutosdr"
        else:
            raise Exception("Unknown device " + device)

        if not release:
            # Get latest
            log.info("Release not set. Checking github for latest")
            g = Github()
            repo = g.get_repo("analogdevicesinc/{}-fw".format(dev))
            rel = repo.get_releases()
            p = rel.get_page(0)
            r = p[0]
            release = r.tag_name
        log.info("Using release: " + release)

        matched = re.match("v[0-1].[0-9][0-9]", release)
        is_match = bool(matched)
        assert is_match, "Version name invalid"

        url = "https://github.com/analogdevicesinc/{dev}-fw/releases/download/{rel}/{dev}-fw-{rel}.zip".format(
            dev=dev, rel=release
        )
        dest = "outs"
        if not os.path.isdir(dest):
            os.mkdir(dest)
        release = os.path.join(dest, dev + "-fw-" + release + ".zip")
        self.download(url, release)

    def _get_file(self, filename, source, design_source_root, source_root, branch, addl=None, url_template=None):
        if source == "artifactory":
            self._get_artifactory_file(filename, design_source_root, source_root, branch, addl, url_template)
        elif source == "local_fs":
            self._get_local_file(filename, design_source_root)
        else:
            raise Exception("Unknown file source")

    def _get_local_file(self, filename, source_root):
        dest = "outs"
        if not os.path.isdir(dest):
            os.mkdir(dest)
        src = os.path.join(source_root, filename)
        if os.path.isfile(src):
            shutil.copy(src, dest)
        else:
            raise Exception("File not found: " + src)

    def _get_artifactory_file(self, filename, folder, ip, branch, addl, url_template):
        dest = "outs"
        if not os.path.isdir(dest):
            os.mkdir(dest)
        if not ip:
            ip = self.http_server_ip
        if not ip:
            raise Exception(
                "No server IP or domain name specificied. Must be defined in yaml or provided as input"
            )
        #get url template base 
        url = gen_url(ip, branch, folder, filename, addl,  url_template)
        self.url = url
        filename = os.path.join(dest, filename)
        log.info("URL: "+url)
        self.download(url, filename)

        if bool(re.search("linux", url)) and bool(re.search(".dtb", url)):
            is_generic = (filename == ("system.dtb" or "devicetree.dtb"))
            if not is_generic:
                old_fname = filename
                if bool(re.search("/arm/", url)):
                    new_fname = os.path.join(dest,"devicetree.dtb")
                elif bool(re.search("/arm64/", url)):
                    new_fname = os.path.join(dest,"system.dtb")

                try:
                    os.rename(old_fname, new_fname)
                except WindowsError:
                    os.remove(new_fname)
                    os.rename(old_fname, new_fname)  
    
    def _get_files_boot_partition(
        self, reference_boot_folder, devicetree_subfolder, boot_subfolder, source, source_root, branch, kernel, kernel_root, dt
    ):
        if source == "artifactory":
            url_template = "https://{}/artifactory/sdg-generic-development/boot_partition/{}/{}/{}"

        log.info("Getting standard boot files")
        # Get kernel
        log.info("Getting "+kernel)
        self._get_file(kernel, source, kernel_root, source_root, branch, url_template=url_template)
            
        if boot_subfolder is not None:
            design_source_root = os.path.join(reference_boot_folder, boot_subfolder)
        else:
            design_source_root = reference_boot_folder
        # Get BOOT.BIN
        log.info("Getting BOOT.BIN")
        self._get_file("BOOT.BIN", source, design_source_root, source_root, branch, url_template=url_template)
        # Get support files (bootgen_sysfiles.tgz)
        log.info("Getting support files")
        self._get_file("bootgen_sysfiles.tgz", source, design_source_root, source_root, branch, url_template=url_template)
        
        # Get device tree
        log.info("Getting "+dt)
        if devicetree_subfolder is not None:
            design_source_root = reference_boot_folder +"/"+ devicetree_subfolder
        else:
            design_source_root = reference_boot_folder
        self._get_file(dt, source, design_source_root, source_root, branch, url_template=url_template)  

        if source == "artifactory":
            get_gitsha(self.url, daily=False)

    def _get_files_hdl(
        self, hdl_folder, source, source_root, branch, hdl_output=False
    ):  
        design_source_root = hdl_folder
        url_template = None
        output = "hdl_output" if hdl_output else "boot_files"  
        #set hdl url template
        if source == "artifactory":
            if branch=="master": 
                url_template = "https://{}/artifactory/sdg-generic-development/hdl/master/{}/{}/{}"
            else:
                url_template = "https://{}/artifactory/sdg-generic-development/hdl/releases/{}/{}/{}"     
          
        if hdl_output:
            log.info("Getting xsa/hdf file")
            try:
                self._get_file("system_top.xsa", source, design_source_root, source_root, branch, output, url_template)
            except Exception:
                self._get_file("system_top.hdf", source, design_source_root, source_root, branch, output, url_template)
        else:    
            # Get BOOT.BIN
            log.info("Getting BOOT.BIN")
            self._get_file("BOOT.BIN", source, design_source_root, source_root, branch, output, url_template)
                        
            # Get support files (bootgen_sysfiles.tgz)
            log.info("Getting support files")
            self._get_file("bootgen_sysfiles.tgz", source, design_source_root, source_root, branch, output, url_template)

        if source == "artifactory":
            get_gitsha(self.url, daily=True, hdl=True)

    def _get_files_linux(
        self, design_name, source, source_root, branch, kernel, kernel_root, dt, arch, microblaze=False
    ):
        url_template = None
        kernel_root = "zynq" if kernel_root == "zynq-common" else "zynq_u"
        if source == "artifactory":
            design_source_root = arch +"/"+ kernel_root
            #set linux url template
            if branch=="master":
                url_template = "https://{}/artifactory/sdg-generic-development/linux/master/{}/{}"
            else:
                url_template = "https://{}/artifactory/sdg-generic-development/linux/releases/{}/{}/{}"

        if microblaze:
            design_source_root = arch
            log.info("Getting simpleimage")
            simpleimage = "simpleImage." +design_name+ ".strip"
            self._get_file(simpleimage, source, design_source_root, source_root, branch, url_template=url_template)
        else:
            #Get files from linux folder
            # Get kernel
            log.info("Getting "+ kernel)
            self._get_file(kernel, source, design_source_root, source_root, branch, url_template=url_template)
            # Get device tree
            dt_dl = design_name + ".dtb"
            log.info("Getting "+ dt_dl)
            design_source_root = arch
            self._get_file(dt_dl, source, design_source_root, source_root, branch, url_template=url_template)
        
        if source == "artifactory":
            get_gitsha(self.url, daily=True, linux=True)

    def _get_files_rpi(
        self, source, source_root, branch, kernel, soc, overlay 
    ):
        dest = "outs"
        if not os.path.isdir(dest):
            os.mkdir(dest)
        file = os.path.join(dest, "properties.yaml")
        #download properties.txt
        if source == "artifactory":
            url_template = "https://{}/artifactory/sdg-generic-development/linux_rpi/{}/{}"
            url = url_template.format(source_root, branch,"")
            build_date= get_newest_folder(listFD(url))
            url= url_template.format(source_root, branch, build_date+"/properties.txt")
            file = os.path.join(dest, "properties.txt")
            self.download(url, file)
            #get_gitsha(self.url, daily=False)    

        url_template = url_template.format(source_root, branch, "{}/{}")
        if "dtbo" not in overlay:
            overlay = overlay + ".dtbo"
        overlay_f = "overlays/"+ overlay
        log.info("Getting overlay "+ overlay)
        url=url_template.format(build_date, overlay_f)
        file = os.path.join(dest, overlay)
        self.download(url, file)
            
        if "img" not in kernel:
            kernel=kernel+".img"
        log.info("Get kernel "+ kernel)
        url=url_template.format(build_date, kernel)
        file = os.path.join(dest, kernel)
        self.download(url, file)

    def _get_files(
        self, design_name, reference_boot_folder, devicetree_subfolder, boot_subfolder, hdl_folder, details, source, source_root, branch, overlay, rpi_kernel, folder=None, 
        firmware=False, noos=False, microblaze=False, rpi=False
    ):
        kernel = False
        kernel_root = False
        dt = False

        if details["carrier"] in ["ZCU102"]:
            kernel = "Image"
            kernel_root = "zynqmp-common"
            dt = "system.dtb"
            arch = "arm64"
        elif (
            details["carrier"] in ["Zed-Board", "ZC702", "ZC706"]
            or "ADRV936" in design_name.upper()
        ):
            kernel = "uImage"
            kernel_root = "zynq-common"
            dt = "devicetree.dtb"
            arch = "arm"
        elif "ADALM" in details["carrier"]:
            firmware = True
        elif (details["carrier"] in ["KC705", "KCU105", "VC707", "VCU118"]
        ):
            arch = "microblaze"
        elif "RPI" in details["carrier"]:
            kernel = rpi_kernel
        else:
            raise Exception("Carrier not supported")

        if firmware:
            # Get firmware
            assert (
                    "pluto" in details["carrier"].lower()
                    or "m2k" in details["carrier"].lower()
                    or "adalm-2000" in details["carrier"].lower()
                ), "Firmware downloads only available for pluto and m2k"
            self._download_firmware(details["carrier"], branch)
        else:

            if source == "local_fs": #to fix
                if not source_root:
                    source_root = "/var/lib/tftpboot"
                kernel_root = os.path.join(source_root, kernel_root)
                design_source_root = os.path.join(source_root, design_name)

            if noos:
                self._get_files_hdl(hdl_folder, source, source_root, branch, hdl_output=True)
            
            if microblaze:
                self._get_files_hdl(hdl_folder, source, source_root, branch, hdl_output=True)
                self._get_files_linux(design_name, source, source_root, branch, kernel, kernel_root, dt, arch, microblaze)
            
            if rpi:
                self._get_files_rpi(source, source_root, branch, kernel, overlay)
            
            if folder:
                if folder == "boot_partition":
                    self._get_files_boot_partition(reference_boot_folder, devicetree_subfolder, boot_subfolder, 
                        source, source_root, branch, kernel, kernel_root, dt)
                elif folder == "hdl_linux":
                    self._get_files_hdl(hdl_folder, source, source_root, branch, hdl_output=False)
                    self._get_files_linux(design_name, source, source_root, branch, kernel, kernel_root, dt, arch)
                else:
                    raise Exception("folder not supported")
             
    def download_boot_files(
        self,
        design_name,
        source="local_fs",
        source_root="/var/lib/tftpboot",
        branch="master",
        firmware=None,
        boot_partition=None,
        noos=None,
        microblaze=None,
        rpi=None
    ):
        """ download_boot_files Download bootfiles for target design.
            This method can download or move files from different locations
            based on the source specified.

            Parameters:
                design_name: Target design name (same as boot file folder on SD card)
                source: Source location type. Options: local_fs, http, artifactory
                source_root: Root location of files. Dependent on source parameter
                    For local_fs this is a system path
                    For http this is a IP or domain name (no http://)
                    For artifactory this is a domain name of the artifactory server 
                    (ex. artifactory.analog.com, no http://)
                branch: Name of branch to get related files. This is only used for
                    http and artifactory sources. Default is master

            Returns:
                A folder with name outs is created with the downloaded boot files
        """
        path = pathlib.Path(__file__).parent.absolute()
        res = os.path.join(path, "resources", "board_table.yaml")
        with open(res) as f:
            board_configs = yaml.load(f, Loader=yaml.FullLoader)
        
        if "-v" in design_name:
            design_name = design_name.split("-v")[0]      

        reference_boot_folder = self.reference_boot_folder
        devicetree_subfolder = self.devicetree_subfolder
        boot_subfolder = self.boot_subfolder
        hdl_folder = self.hdl_folder
        overlay = self.overlay
        rpi_kernel = self.kernel

        if noos:
            res = os.path.join(path, "resources", "noOS_projects.yaml")
            with open(res) as f:
                noos_projects = yaml.load(f, Loader=yaml.FullLoader)
            val = []
            for project in noos_projects:
                hdl_projects = noos_projects[project]
                if hdl_projects is not None:
                    for hdl_project in hdl_projects:
                        if hdl_project == hdl_folder:
                            val.append(hdl_project)
                            log.info("No-OS project:" + project)

            if not val:
                raise Exception("Design has no support!")
        else:
            assert design_name in board_configs, "Invalid design name"

        if not firmware:
            matched = re.match("v[0-1].[0-9][0-9]", branch)
            if bool(matched) and design_name in ['pluto', 'm2k']:
                raise Exception("Add --firmware to command")

        branch = branch
        if boot_partition:
            folder = "boot_partition"    
        else:
            folder = "hdl_linux"

        if noos or microblaze or rpi:
            folder=None
        
        #get files from boot partition folder
        self._get_files(
            design_name,
            reference_boot_folder,
            devicetree_subfolder,
            boot_subfolder,
            hdl_folder,
            board_configs[design_name],
            source,
            source_root,
            branch,
            overlay,
            rpi_kernel,
            folder,
            firmware,
            noos,
            microblaze,
            rpi
            )

    def download_sdcard_release(self, release="2019_R1"):
        rel = self.releases(release)
        self.download(rel["link"], rel["xzname"])
        self.check(rel["xzname"], rel["xzmd5"])
        self.extract(rel["xzname"], rel["imgname"])
        self.check(rel["imgname"], rel["imgmd5"])
        print("Image file available:", rel["imgname"])

    def releases(self, release="2019_R1"):
        rel = {}
        if release == "2018_R2":
            rel["imgname"] = "2018_R2-2019_05_23.img"
            rel["xzmd5"] = "c377ca95209f0f3d6901fd38ef2b4dfd"
            rel["imgmd5"] = "59c2fe68118c3b635617e36632f5db0b"
        elif release == "2019_R1":
            rel["imgname"] = "2019_R1-2020_02_04.img"
            rel["xzmd5"] = "49c121d5e7072ab84760fed78812999f"
            rel["imgmd5"] = "40aa0cd80144a205fc018f479eff5fce"

        else:
            raise Exception("Unknown release")
        rel["link"] = "http://swdownloads.analog.com/cse/" + rel["imgname"] + ".xz"
        rel["xzname"] = rel["imgname"] + ".xz"
        return rel

    def retry_session(self, retries=3, backoff_factor=0.3, 
        status_forcelist=(429, 500, 502, 504),
        session=None,
    ):
        session = session or requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session

    def download(self, url, fname):
        resp = self.retry_session().get(url, stream=True)
        if not resp.ok:
            raise Exception(fname.lstrip("outs/") + " - File not found!" )
        total = int(resp.headers.get("content-length", 0))
        with open(fname, "wb") as file, tqdm(
            desc=fname, total=total, unit="iB", unit_scale=True, unit_divisor=1024,
        ) as bar:
            for data in resp.iter_content(chunk_size=1024):
                size = file.write(data)
                bar.update(size)

    def check(self, fname, ref):
        hash_md5 = hashlib.md5()
        tlfile = pathlib.Path(fname)
        total = os.path.getsize(tlfile)
        with open(fname, "rb") as f, tqdm(
            desc="Hashing: " + fname,
            total=total,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
                size = len(chunk)
                bar.update(size)
        h = hash_md5.hexdigest()
        if h == ref:
            print("MD5 Check: PASSED")
        else:
            print("MD5 Check: FAILEDZz")
            raise Exception("MD5 hash check failed")

    def extract(self, inname, outname):
        tlfile = pathlib.Path(inname)

        decompressor = lzma.LZMADecompressor()
        with open(tlfile, "rb") as ifile:
            total = 0
            with open(outname, "wb") as file, tqdm(
                desc="Decompressing: " + outname,
                total=total,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                data = ifile.read(1024)
                while data:
                    result = decompressor.decompress(data)
                    if result != b"":
                        size = file.write(result)
                        bar.update(size)
                    data = ifile.read(1024)


if __name__ == "__main__":
    d = downloader()
    # d.download_sdcard_release()
    d.download_boot_files("zynq-adrv9361-z7035-fmc")
