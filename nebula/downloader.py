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

from bs4 import BeautifulSoup
import requests
import re
from datetime import datetime
from github import Github

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


def get_newest_folder(links):
    dates = []
    for link in links:
        folder = link.split("/")[-2]
        matched = re.match("20[1-2][9,0,1]_[0-3][0-9]_[0-3][0-9]", folder)
        is_match = bool(matched)

        if is_match:
            dates.append(folder)

    if not dates:
        raise Exception("No folders found")
    dates.sort(key=lambda date: convert_to_datetime(date))

    return dates[-1]


def gen_url(ip, branch, folder, filename, url_template):
    url = url_template.format(ip, branch, "", "")
    # folder = BUILD_DATE/PROJECT_FOLDER
    folder = get_newest_folder(listFD(url[:-1]))+'/'+folder
    print(url_template.format(ip, branch, folder, filename))
    return url_template.format(ip, branch, folder, filename)


class downloader(utils):
    def __init__(self, http_server_ip=None, yamlfilename=None, board_name=None, reference_boot_folder=None, devicetree_subfolder=None, boot_subfolder=None):
        self.reference_boot_folder = None
        self.devicetree_subfolder = None
        self.boot_subfolder = None
        self.http_server_ip = http_server_ip
        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
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

    def _get_file(self, filename, source, design_source_root, source_root, branch):
        if source == "http":
            url_template = "http://{}/jenkins_export/{}/boot_partitions/{}/{}"
            self._get_http_files(filename, design_source_root, source_root, branch, url_template)
        elif source == "artifactory":
            url_template = "https://{}/artifactory/sdg-generic-development/boot_partition/{}/{}/{}"
            self._get_http_files(filename, design_source_root, source_root, branch, url_template)
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
            print(os.listdir(source_root))
            raise Exception("File not found: " + src)

    def _get_http_files(self, filename, folder, ip, branch, url_template):
        dest = "outs"
        if not os.path.isdir(dest):
            os.mkdir(dest)
        if not ip:
            ip = self.http_server_ip
        if not ip:
            raise Exception(
                "No server IP or domain name specificied. Must be defined in yaml or provided as input"
            )
        url = gen_url(ip, branch, folder, filename, url_template)
        filename = os.path.join(dest, filename)
        self.download(url, filename)

    def _get_files(
        self, design_name, reference_boot_folder, devicetree_subfolder, boot_subfolder, details, source, source_root, branch, firmware=False
    ):
        kernel = False
        kernel_root = False
        dt = False

        if details["carrier"] in ["ZCU102"]:
            kernel = "Image"
            kernel_root = "zynqmp-common"
            dt = "system.dtb"
        elif (
            details["carrier"] in ["Zed-Board", "ZC702", "ZC706"]
            or "ADRV936" in design_name.upper()
        ):
            kernel = "uImage"
            kernel_root = "zynq-common"
            dt = "devicetree.dtb"
        elif "ADALM" in details["carrier"]:
            firmware = True
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

            if source == "local_fs":
                if not source_root:
                    source_root = "/var/lib/tftpboot"
                kernel_root = os.path.join(source_root, kernel_root)
                design_source_root = os.path.join(source_root, design_name)
            else:
                design_source_root = reference_boot_folder
            print("Get standard boot files")
            # Get kernel
            print("Get", kernel)
            print(design_source_root)
            self._get_file(kernel, source, kernel_root, source_root, branch)
            
            if boot_subfolder is not None:
                design_source_root = reference_boot_folder+ '/' +str(boot_subfolder)
            else:
                design_source_root = reference_boot_folder
            # Get BOOT.BIN
            print(design_source_root)
            print("Get BOOT.BIN")
            self._get_file("BOOT.BIN", source, design_source_root, source_root, branch)
            # Get support files (bootgen_sysfiles.tgz)
            print("Get support")
            self._get_file(
                "bootgen_sysfiles.tgz", source, design_source_root, source_root, branch
            )
            # Get device tree
            print("Get", dt)
            if devicetree_subfolder is not None:
                design_source_root = reference_boot_folder+ '/' +str(devicetree_subfolder)
            else:
                design_source_root = reference_boot_folder
            print(design_source_root)
            self._get_file(dt, source, design_source_root, source_root, branch)

    def download_boot_files(
        self,
        design_name,
        source="local_fs",
        source_root="/var/lib/tftpboot",
        branch="master",
        firmware=None,
    ):
        """ download_boot_files Download bootfiles for target design.
            This method can download or move files from different locations
            based on the source specified.

            Parameters:
                design_name: Target design name (same as boot file folder on SD card)
                dtb_folder: Applicable to target design name with sub-folder for devicetree (name of sub-folder)
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

        assert design_name in board_configs, "Invalid design name"

        reference_boot_folder = self.reference_boot_folder
        devicetree_subfolder = self.devicetree_subfolder
        boot_subfolder = self.boot_subfolder

        self._get_files(
            design_name,
            reference_boot_folder,
            devicetree_subfolder,
            boot_subfolder,
            board_configs[design_name],
            source,
            source_root,
            branch,
            firmware,
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

    def download(self, url, fname):
        resp = requests.get(url, stream=True)
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
