import csv
import hashlib
import logging
import lzma
import ntpath
import os
import pathlib
import re
import shutil
import tarfile
from datetime import datetime
from pathlib import Path

import requests
import yaml
from artifactory import ArtifactoryPath
from bs4 import BeautifulSoup
from github import Github
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from tqdm import tqdm

from nebula.common import utils

log = logging.getLogger(__name__)


def listFD(url, source="artifactory"):
    if source == "cloudsmith":
        return None
    elif source == "artifactory":
        page = requests.get(url).text
        soup = BeautifulSoup(page, "html.parser")
        return [url + "/" + node.get("href") for node in soup.find_all("a")]


def convert_to_datetime(date):
    if len(date) == 19:
        return datetime.strptime(date, "%Y_%m_%d-%H_%M_%S")
    else:
        return datetime.strptime(date[:10], "%Y_%m_%d")


def get_firmware_version(links, source="artifactory"):
    if source == "cloudsmith":
        version = None
    elif source == "artifactory":
        version = None
        for link in links:
            file = link.split("/")[-1]
            if "zip" in file:
                version = file
        return version


def get_latest_release(links, source="artifactory"):
    if source == "cloudsmith":
        return None
    elif source == "artifactory":
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


def get_newest_folder(
    links_or_packages, source="artifactory", branch=None, filename=None, board_name=None
):
    if source == "cloudsmith":
        pass
    elif source == "artifactory":
        dates = []
        for link in links_or_packages:
            folder = link.split("/")[-2]
            matched = re.match(
                "20[1-2][0,1,2,3,4,5,6,7,8,9]_[0-3][0-9]_[0-3][0-9]", folder
            )
            is_match = bool(matched)

            if is_match:
                dates.append(folder)

        if not dates:
            raise Exception("No folders found")
        dates.sort(key=lambda date: convert_to_datetime(date))

        n = 0
        content = {"hdl_output": 130, "boot_files": 65, "linux": 4, "bootpartition": 75}
        for k, v in content.items():
            if re.search(k, links_or_packages[-1]):
                n = v

        if len(listFD(links_or_packages[-1])) < n:
            return dates[-2]
        else:
            return dates[-1]


def get_gitsha(
    url, daily=False, linux=False, hdl=False, build_info=None, source="artifactory"
):
    if source == "cloudsmith":
        return None
    elif source == "artifactory":
        dest = "outs"
        if not os.path.isdir(dest):
            os.mkdir(dest)
        file = os.path.join(dest, "properties.yaml")
        with open(file, "a+") as f:
            path = ArtifactoryPath(str(url))
            props = path.properties
            exp = "20[1-2][0-9]_[0-1][0-9]_[0-3][0-9][-_][0-2][0-9]_[0-5][0-9](?:_[0-5][0-9])?"

            if build_info:
                if build_info["Triggered by"] == "hdl":
                    props["linux_git_sha"] = ["NA"]
                    props["hdl_git_sha"] = [build_info["COMMIT SHA"]]
                elif build_info["Triggered by"] == "linux":
                    props["linux_git_sha"] = [build_info["COMMIT SHA"]]
                    props["hdl_git_sha"] = ["NA"]

            try:
                if not daily:
                    bootpartition = {
                        "bootpartition_folder": re.findall(exp, url)[0],
                        "linux_git_sha": props["linux_git_sha"][0],
                        "hdl_git_sha": props["hdl_git_sha"][0],
                    }
                    yaml.dump(bootpartition, f)
                else:
                    if hdl:
                        hdl_props = {
                            "hdl_folder": re.findall(exp, url)[0],
                            "hdl_git_sha": props["git_sha"][0],
                        }
                        yaml.dump(hdl_props, f)
                    if linux:
                        linux_props = {
                            "linux_folder": re.findall(exp, url)[0],
                            "linux_git_sha": props["git_sha"][0],
                        }
                        yaml.dump(linux_props, f)
            except Exception:
                # TODO: fetch info.txt and get linux or hdl gitsha from there
                bootpartition = {
                    "bootpartition_folder": re.findall(exp, url)[0],
                    "linux_git_sha": "NA",
                    "hdl_git_sha": "NA",
                }
                yaml.dump(bootpartition, f)


def gen_url(ip, branch, folder, filename, addl, url_template, source="artifactory"):
    if source == "cloudsmith":
        return None
    elif source == "artifactory":
        if branch == "main":
            if bool(re.search("boot_partition", url_template)):
                url = url_template.format(ip, branch, "", "")
                # folder = BUILD_DATE/PROJECT_FOLDER
                folder = (
                    get_newest_folder(listFD(url[:-1]))
                    + "/boot_partition/"
                    + str(folder)
                )
                return url_template.format(ip, branch, folder, filename)
            elif bool(re.search("hdl", url_template)):
                url = url_template.format(ip, addl, "", "")
                folder = get_newest_folder(listFD(url[:-1])) + "/" + str(folder)
                return url_template.format(ip, addl, folder, filename)
            else:
                url = url_template.format(ip, "", "")
                # folder = BUILD_DATE/PROJECT_FOLDER
                folder = get_newest_folder(listFD(url[:-1])) + "/" + str(folder)
                return url_template.format(ip, folder, filename)
        else:
            url = url_template.format(ip, "", "", "")
            if branch == "release" or branch == "release_latest":
                if bool(re.search("hdl", url_template)):
                    release_folder = get_latest_release(listFD(url)) + "/" + addl
                else:
                    release_folder = get_latest_release(listFD(url))
            else:
                if bool(re.search("boot_partition", url_template)):
                    release_folder = branch.lower()
                elif bool(re.search("hdl", url_template)):
                    release_folder = "hdl_" + branch.lower() + "/" + addl
                else:
                    release_folder = branch.upper()
            url = url_template.format(ip, release_folder, "", "")
            # folder = BUILD_DATE/PROJECT_FOLDER
            folder = (
                    get_newest_folder(listFD(url[:-1]))
                    + "/boot_partition/"
                    + str(folder)
                )
            return url_template.format(ip, release_folder, folder, filename)


def list_files_in_remote_folder(url, source="artifactory"):
    if source == "cloudsmith":
        return None
    elif source == "artifactory":
        """List files in remote artifactory folder"""
        path = ArtifactoryPath(url)
        return path.listdir()


def get_artifact_paths(toolbox, branch, build, ext, root="dev", source="artifactory"):
    if source == "cloudsmith":
        # cloudsmith does not support directory listing
        return None
    elif source == "artifactory":
        log.info(f"Getting {ext} files from {branch} build {build} in {toolbox}")
        path = ArtifactoryPath(
            f"https://artifactory.analog.com/artifactory/sdg-generic-development/{toolbox}/{root}/{branch}/{build}"
        )
        filename_urls = []
        for path in path.iterdir():
            if path.is_file():
                if path.name.endswith(ext):
                    filename_urls.append(path)
        filenames = [path.name for path in filename_urls]
        log.info(f"Found {len(filenames)} {ext} files: {filenames}")
        return filename_urls


def filter_boards(paths, fmc, fpga):
    filtered_paths = []
    rd_names = []
    for path in paths:
        fmc_e, fpga_e, variant_e = interpret_bootbin(path)
        rd_name = translate_to_reference_design_name(fmc_e, fpga_e)
        if fmc is None:
            filtered_paths.append(path)
            rd_names.append(rd_name)
            continue
        if fmc.lower() == fmc_e.lower() and fpga.lower() == fpga_e.lower():
            filtered_paths.append(path)
            rd_names.append(rd_name)
    log.info(f"Filtered to {len(filtered_paths)}  Based on: {fmc} | {fpga} requirement")
    return filtered_paths, rd_names


def download_artifact(path, output_folder, source="artifactory"):
    if source == "cloudsmith":
        # cloudsmith does not support directory listing
        return
    elif source == "artifactory":
        if not os.path.isdir(output_folder):
            os.mkdir(output_folder)
        out_filename = os.path.join(output_folder, path.name)
        log.info(f"Downloading {out_filename} from {str(path)}")
        with path.open() as fd, open(out_filename, "wb") as out:
            out.write(fd.read())


def translate_to_reference_design_name(fmc, fpga):
    path = pathlib.Path(__file__).parent.absolute()
    res = os.path.join(path, "resources", "board_table.yaml")
    with open(res) as f:
        board_configs = yaml.load(f, Loader=yaml.FullLoader)

    if fpga.lower().strip() == "CCBOB_CMOS".lower():
        fpga = "ADRV1CRR-BOB"
    if fpga.lower().strip() == "CCBOB_LVDS".lower():
        fpga = "ADRV1CRR-BOB"
    if fpga.lower().strip() == "CCPACKRF_LVDS".lower():
        fpga = "ADRV-PACKRF"
    if fpga.lower().strip() == "CCFMC_LVDS".lower():
        fpga = "ADRV1CRR-FMC"

    for board in board_configs:
        if board_configs[board]["carrier"].lower().strip() == fpga.lower().strip() and (
            "addons" in board_configs[board] or fmc.lower().strip() in board.lower()
        ):
            if fmc.lower().strip() in board.lower():
                return board
            for addon in board_configs[board]["addons"]:
                if fmc.lower() in addon.lower():
                    return board
    return None


def interpret_bootbin(filename):
    parts = filename.split("(")
    if len(parts) != 2:
        raise ValueError(f"Unexpected filename format: {filename}")
    fmc = parts[0].split(" ")[0]
    fpga = parts[0].split(" ")[1]
    variant = parts[1].split(")")[0]
    log.info(f"Interpreted {filename} as {fmc} | {fpga} | {variant}")
    return fmc, fpga, variant


def generate_bootbin_map_file(bootbin_dir):
    if not os.path.isdir(bootbin_dir):
        raise ValueError(f"Bootbin directory does not exist: {bootbin_dir}")
    bootbin_files = [f for f in os.listdir(bootbin_dir) if f.endswith(".BIN")]
    if len(bootbin_files) == 0:
        raise ValueError(f"No bootbin files found in {bootbin_dir}")
    paths, rd_names = filter_boards(bootbin_files, None, None)
    if len(paths) == 0:
        raise ValueError("No artifacts found that meet criteria")
    return bootbin_files, rd_names


def download_matlab_generate_bootbin(
    root,
    toolbox,
    branch,
    build,
    target_fmc,
    target_fpga,
    download_folder,
    skip_download=False,
):
    paths = get_artifact_paths(toolbox, branch, build, ".BIN", root)
    # paths = [path.name for path in paths]
    # paths, rd_names = filter_boards(paths, target_fmc, target_fpga)
    rd_names = []
    if len(paths) == 0:
        raise ValueError("No artifacts found that meet criteria")
    if not skip_download:
        for path in paths:
            download_artifact(path, download_folder)
    return paths, rd_names


def sanitize_artifactory_url(url, source="artifactory"):
    if source == "cloudsmith":
        return None
    elif source == "artifactory":
        url = re.sub(r"%2F", "/", url)
        url = re.sub("/ui/repos/tree/Properties/", "/artifactory/", url)
        # rebase url
        url = re.sub("/boot_partition/.*$", "", url)
        return url


def get_info_txt(url, source="artifactory"):
    if source == "cloudsmith":
        return None
    elif source == "artifactory":
        art_path = ArtifactoryPath(sanitize_artifactory_url(url))
        info_txt_path = None
        for p in art_path:
            if "info.txt" in str(p):
                info_txt_path = p
                break

        if not info_txt_path:
            raise Exception("Missing info.txt")

        log.info("Parsing info.txt")
        build_info = {"built_projects": []}
        with info_txt_path.open() as fd:
            with open("info.txt", "wb") as out:
                content = fd.read()
                out.write(content)
                info_txt = content.decode("utf-8").split("\n")
                for line in info_txt:
                    match = re.match(r"[\s-]*(.+):(.+)", line)
                    if match:
                        build_info.update(
                            {match.group(1).strip(): match.group(2).strip()}
                        )
                    else:
                        match = re.match(r"\s+-\s([-\w]+)", line)
                        if match:
                            build_info["built_projects"].append(match.group(1))

        return build_info


class downloader(utils):
    def __init__(
        self,
        http_server_ip=None,
        yamlfilename=None,
        board_name=None,
        cloudsmith_auth=None,
    ):
        self.reference_boot_folder = None
        self.devicetree_subfolder = None
        self.boot_subfolder = None
        self.hdl_folder = None
        self.http_server_ip = http_server_ip
        self.url = None
        self.board_name = board_name
        # rpi fields
        self.devicetree = None
        self.devicetree_overlay = None
        self.kernel = None
        self.modules = None
        self.no_os_project = None
        self.platform = None
        self.username = None
        self.cloudsmith_token = None

        if cloudsmith_auth:
            try:
                self.username, self.cloudsmith_token = cloudsmith_auth.split(":", 1)
            except Exception:
                raise Exception(
                    "Cloudsmith authentication format error, must be user:token"
                )

        # update from config
        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )

    def _download_firmware(self, device, source="github", release=None, version=None):
        if "m2k" in device.lower() or "adalm-2000" in device.lower():
            dev = "m2k"
            fw_filename = "m2k-fw-v0.33-1-gdce1.zip"
        elif "pluto" in device.lower():
            dev = "plutosdr"
            fw_filename = "plutosdr-fw-v0.39-1-g8456.zip"
        else:
            raise Exception("Unknown device " + device)

        if source == "github":
            if release == "main" or release == "release":
                release = None
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
            filename = os.path.join(dest, dev + "-fw-" + release + ".zip")
            self.download(url, filename)
        elif source == "artifactory":
            url_template = "https://artifactory.analog.com/artifactory/sdg-generic-development/m2k_and_pluto/{}-fw/{}/{}"
            url = url_template.format(dev, "", "")
            build_date = get_newest_folder(listFD(url))
            url = url_template.format(dev, build_date, "")
            # get version
            ver = get_firmware_version(listFD(url))
            url = url_template.format(dev, build_date, ver)
            dest = "outs"
            if not os.path.isdir(dest):
                os.mkdir(dest)
            filename = os.path.join(dest, ver)
            self.download(url, filename)
        elif source == "cloudsmith":
            api_key = self.cloudsmith_token
            username = self.username
            if not api_key or not username:
                log.error(
                    "Cloudsmith credentials missing. Pass --cloudsmith-auth user:token or set CLOUDSMITH_AUTH."
                )
                raise Exception("Cloudsmith credentials missing.")

            # Use the version (date string or 'latest' ex. 27-10-2025_08-52-03) to build URL
            if version:
                url = f"https://dl.cloudsmith.io/basic/adi/{dev}-fw/raw/versions/{version}/{fw_filename}"
                log.info(
                    f"Downloading {fw_filename} version {version} from Cloudsmith: {url}"
                )
            else:
                # url = f"https://dl.cloudsmith.io/basic/adi/m2k-fw/raw/versions/latest/m2k-fw-v0.33-1-gdce1.zip"
                url = f"https://dl.cloudsmith.io/basic/adi/{dev}-fw/raw/versions/latest/{fw_filename}"
                log.info(f"Downloading latest {fw_filename} from Cloudsmith: {url}")
            dest = "outs"
            if not os.path.isdir(dest):
                os.mkdir(dest)
            filename = os.path.join(dest, fw_filename)
            self.download(url, filename, username=username, cloudsmith_token=api_key)

    def _get_file(
        self,
        filename,
        source,
        design_source_root,
        source_root,
        branch,
        addl=None,
        url_template=None,
        version=None,
    ):
        if source == "artifactory":
            self._get_artifactory_file(
                filename, design_source_root, source_root, branch, addl, url_template
            )
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
                "No server IP or domain name specified. Must be defined in yaml or provided as input"
            )

        new_flow = False
        for pipeline in [
            "HDL_PRs",
            "Linux_PRs",
            "HDL_latest_commit",
            "Linux_latest_commit",
        ]:
            if bool(re.search(pipeline, url_template)):
                new_flow = True

        if new_flow:
            url = url_template.format(folder, filename)
        else:
            # get url template base
            url = gen_url(ip, branch, folder, filename, addl, url_template)
        self.url = url
        filename = os.path.join(dest, filename)
        log.info("URL: " + url)
        self.download(url, filename)

        if bool(re.search("linux", url)) and bool(re.search(".dtb", url)):
            is_generic = filename == ("system.dtb" or "devicetree.dtb")
            if not is_generic:
                old_fname = filename
                if bool(re.search("/arm/", url)):
                    new_fname = os.path.join(dest, "devicetree.dtb")
                elif bool(re.search("/arm64/", url)):
                    new_fname = os.path.join(dest, "system.dtb")

                try:
                    os.rename(old_fname, new_fname)
                except WindowsError:
                    os.remove(new_fname)
                    os.rename(old_fname, new_fname)

    def _get_cloudsmith_file(
        self,
        branch,
        kernel,
        dt,
        board_name,
        kernel_root,
    ):
        """
        Fetch and process files from Cloudsmith.
        """
        log.info("Getting standard boot files (Cloudsmith)")
        api_key = self.cloudsmith_token
        if not api_key:
            raise Exception(
                "Cloudsmith API key missing. Set CLOUDSMITH_API_KEY environment variable."
            )

        headers = self._get_cloudsmith_headers(api_key)
        file_queries = self._construct_file_queries(
            branch, kernel, dt, board_name, kernel_root
        )
        boot_files = [kernel, "BOOT.BIN", "bootgen_sysfiles.tgz", dt]

        for filename in boot_files:
            all_packages = self._fetch_all_packages(
                headers, file_queries[filename], filename
            )
            filtered_packages = self._filter_packages(all_packages)

            if filtered_packages:
                self._download_and_verify_file(filtered_packages[0], filename)
            else:
                raise Exception(
                    f"No package found for {filename} with version {branch} and board {board_name}"
                )

    def _get_cloudsmith_headers(self, api_key):
        """Generate headers for Cloudsmith API requests."""
        return {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    def _construct_file_queries(self, branch, kernel, dt, board_name, kernel_root):
        """Construct queries for fetching files from Cloudsmith."""
        package_version = f"boot_partition/{branch}/"

        latest_date = self._get_initial_metadata(branch, kernel, package_version)

        return {
            kernel: f"version:boot_partition/{branch}/{latest_date}/{kernel_root}%20AND%20name:*mage$",
            "BOOT.BIN": f"version:boot_partition/{branch}/{latest_date}/{board_name}*%20AND%20name:^BOOT.BIN$",
            "bootgen_sysfiles.tgz": f"version:boot_partition/{branch}/{latest_date}/{board_name}%20AND%20name:^bootgen_sysfiles.tgz$",
            dt: f"version:boot_partition/{branch}/{latest_date}/{board_name}*%20AND%20name:*.dtb$",
        }

    def _fetch_all_packages(self, headers, query, filename):
        """Fetch all packages from Cloudsmith based on the query."""
        all_packages = []
        page = 1
        url = f"https://api.cloudsmith.io/v1/packages/adi/sdg-boot-partition/?query={query}&page={page}&page_size=500"
        log.info(f"Fetching Cloudsmith metadata for {filename} via REST API: {url}")

        while url:
            log.info(f"Fetching page {page} for {filename}")
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            page_data = resp.json()

            if isinstance(page_data, dict) and "results" in page_data:
                all_packages.extend(page_data["results"])
                url = page_data.get("next")
            elif isinstance(page_data, list):
                all_packages.extend(page_data)
                url = None
            else:
                log.error("Unexpected response format from Cloudsmith API")
                raise Exception("Unexpected response format from Cloudsmith API")

            page += 1

        # Log the total number of packages found
        if len(all_packages) == 0:
            raise Exception(f"No packages found for {filename} with query: {query}")
        else:
            log.info(f"Total packages found for {filename}: {len(all_packages)}")

        return all_packages

    def _filter_packages(self, all_packages):
        """Filter packages based on status and format."""
        return [
            {
                "cdn_url": pkg.get("cdn_url"),
                "version": pkg.get("version"),
                "checksum_sha256": pkg.get("checksum_sha256"),
            }
            for pkg in all_packages
            if pkg.get("status_str") == "Completed" and pkg.get("format") == "raw"
        ]

    def _download_and_verify_file(self, package, filename):
        """Download and verify a file from Cloudsmith."""
        cdn_url = package["cdn_url"]
        sha256 = package["checksum_sha256"]
        dest = "outs"
        os.makedirs(dest, exist_ok=True)
        out_path = os.path.join(dest, filename)

        log.info(f"Downloading {filename} from {cdn_url}")
        self.download(cdn_url, out_path)
        if sha256:
            self.check(out_path, sha256, hash_type="sha256")
        log.info(f"Downloaded and verified: {out_path}")

    def _get_initial_metadata(self, branch, filename, package_version):
        """
        Perform an initial query to fetch metadata fields, including the version field.
        Filters and extracts the latest date from the version field.
        """
        log.info(f"Fetching initial metadata with branch {branch}")
        headers = self._get_cloudsmith_headers(self.cloudsmith_token)
        query = f"version:boot_partition/{branch}/*"
        url = f"https://api.cloudsmith.io/v1/packages/adi/sdg-boot-partition/?query={query}&page_size=500"

        all_packages = []
        while url:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            page_data = resp.json()

            if isinstance(page_data, dict) and "results" in page_data:
                all_packages.extend(page_data["results"])
                url = page_data.get("next")
            elif isinstance(page_data, list):
                all_packages.extend(page_data)
                url = None
            else:
                log.error("Unexpected response format from Cloudsmith API")
                raise Exception("Unexpected response format from Cloudsmith API")

        # Log all version fields for debugging
        # log.info(f"All version fields returned: {[pkg.get('version', '') for pkg in all_packages]}")

        # we get the list of dates from the version field
        date_set = set()
        for pkg in all_packages:
            version = pkg.get("version", "")
            if version.startswith(package_version):
                remaining_path = version[len(package_version) :]
                subfolder = remaining_path.split("/")[0]
                try:
                    date_obj = datetime.strptime(subfolder, "%Y_%m_%d-%H_%M_%S")
                    date_set.add(date_obj)
                except ValueError:
                    continue

        log.info(
            f"Dates found: {[date.strftime('%Y_%m_%d-%H_%M_%S') for date in date_set]}"
        )

        if not date_set:
            raise Exception(f"No valid dates found in metadata for {filename}")

        latest_date = max(date_set).strftime("%Y_%m_%d-%H_%M_%S")
        log.info(f"Latest date  {latest_date}")
        return latest_date

    def _get_files_boot_partition(
        self,
        reference_boot_folder,
        devicetree_subfolder,
        boot_subfolder,
        source,
        source_root,
        branch,
        kernel,
        kernel_root,
        dt,
        url_template=None,
    ):
        if source == "cloudsmith":
            self._get_cloudsmith_file(branch, kernel, dt, self.board_name, kernel_root)

        elif source == "artifactory":
            if url_template:
                url_template = (
                    sanitize_artifactory_url(url_template) + "/boot_partition/{}/{}"
                )
            else:
                url_template = "https://{}/artifactory/sdg-generic-development/boot_partition/{}/{}/{}"

            log.info("Getting standard boot files")
            # Get kernel
            log.info("Getting " + kernel)
            self._get_file(
                kernel,
                source,
                kernel_root,
                source_root,
                branch,
                url_template=url_template,
            )

            if boot_subfolder is not None:
                design_source_root = os.path.join(reference_boot_folder, boot_subfolder)
            else:
                design_source_root = reference_boot_folder
            # Get BOOT.BIN
            log.info("Getting BOOT.BIN")
            self._get_file(
                "BOOT.BIN",
                source,
                design_source_root,
                source_root,
                branch,
                url_template=url_template,
            )
            # Get support files (bootgen_sysfiles.tgz)
            log.info("Getting support files")
            self._get_file(
                "bootgen_sysfiles.tgz",
                source,
                design_source_root,
                source_root,
                branch,
                url_template=url_template,
            )

            # Get device tree
            log.info("Getting " + dt)
            if devicetree_subfolder is not None:
                design_source_root = reference_boot_folder + "/" + devicetree_subfolder
            else:
                design_source_root = reference_boot_folder
            self._get_file(
                dt,
                source,
                design_source_root,
                source_root,
                branch,
                url_template=url_template,
            )
        if source == "cloudsmith":
            return None
        elif source == "artifactory":
            # check if info_txt is present
            try:
                build_info = get_info_txt(url_template)
            except Exception as e:
                log.warn(e)
                build_info = None
            get_gitsha(self.url, daily=False, build_info=build_info)

    def _get_files_hdl(self, hdl_folder, source, source_root, branch, hdl_output=False):
        design_source_root = hdl_folder
        url_template = None
        output = "hdl_output" if hdl_output else "boot_files"
        # set hdl url template
        if source == "cloudsmith":
            # create a method for cloudsmith here
            return None
        elif source == "artifactory":
            if branch == "main":
                url_template = (
                    "https://{}/artifactory/sdg-generic-development/hdl/main/{}/{}/{}"
                )
            else:
                url_template = "https://{}/artifactory/sdg-generic-development/hdl/releases/{}/{}/{}"

        if hdl_output:
            log.info("Getting xsa/hdf file")
            try:
                self._get_file(
                    "system_top.xsa",
                    source,
                    design_source_root,
                    source_root,
                    branch,
                    output,
                    url_template,
                )
            except Exception:
                self._get_file(
                    "system_top.hdf",
                    source,
                    design_source_root,
                    source_root,
                    branch,
                    output,
                    url_template,
                )
        else:
            # Get BOOT.BIN
            log.info("Getting BOOT.BIN")
            self._get_file(
                "BOOT.BIN",
                source,
                design_source_root,
                source_root,
                branch,
                output,
                url_template,
            )

            # Get support files (bootgen_sysfiles.tgz)
            log.info("Getting support files")
            self._get_file(
                "bootgen_sysfiles.tgz",
                source,
                design_source_root,
                source_root,
                branch,
                output,
                url_template,
            )

        if source == "artifactory":
            get_gitsha(self.url, daily=True, hdl=True)

    def _get_files_linux(
        self,
        design_name,
        source,
        source_root,
        branch,
        kernel,
        kernel_root,
        dt,
        arch,
        microblaze=False,
    ):
        url_template = None
        if kernel_root == "zynq-common":
            kernel_root = "zynq"
        elif kernel_root == "zynqmp-common" and branch < "2023_R2":
            kernel_root = "zynq_u"
        else:
            kernel_root = "zynqmp"
        if source == "cloudsmith":
            return None
        elif source == "artifactory":
            design_source_root = arch + "/" + kernel_root
            # set linux url template
            if branch == "main":
                url_template = (
                    "https://{}/artifactory/sdg-generic-development/linux/main/{}/{}"
                )
            else:
                url_template = "https://{}/artifactory/sdg-generic-development/linux/releases/{}/{}/{}"

        if microblaze:
            design_source_root = arch
            log.info("Getting simpleimage")
            simpleimage = "simpleImage." + design_name + ".strip"
            self._get_file(
                simpleimage,
                source,
                design_source_root,
                source_root,
                branch,
                url_template=url_template,
            )
        else:
            # Get files from linux folder
            # Get kernel
            log.info("Getting " + kernel)
            self._get_file(
                kernel,
                source,
                design_source_root,
                source_root,
                branch,
                url_template=url_template,
            )
            # Get device tree
            dt_dl = design_name + ".dtb"
            log.info("Getting " + dt_dl)
            design_source_root = arch
            self._get_file(
                dt_dl,
                source,
                design_source_root,
                source_root,
                branch,
                url_template=url_template,
            )

        if source == "artifactory":
            get_gitsha(self.url, daily=True, linux=True)

    def _get_files_rpi(
        self,
        source,
        source_root,
        branch,
        kernel,
        devicetree,
        devicetree_overlay,
        modules,
    ):
        dest = "outs"
        if not os.path.isdir(dest):
            os.mkdir(dest)
        # download properties.txt
        if source == "artifactory":
            arch = "32bit"
            url_template = (
                "https://{}/artifactory/sdg-generic-development/linux_rpi/{}/{}"
            )
            url = url_template.format(source_root, branch, "")
            build_date = get_newest_folder(listFD(url))
            url = url_template.format(
                source_root, branch, build_date + "/" + arch + "/version_rpi.txt"
            )
            file = os.path.join(dest, "properties.txt")
            self.download(url, file)

        url_template = url_template.format(source_root, branch, "{}/" + arch + "/{}")

        if devicetree:
            if "dtb" not in devicetree:
                devicetree = devicetree + ".dtb"
            log.info("Getting device tree " + devicetree)
            url = url_template.format(build_date, devicetree)
            file = os.path.join(dest, devicetree)
            self.download(url, file)

        if devicetree_overlay:
            if "dtbo" not in devicetree_overlay:
                devicetree_overlay = devicetree_overlay + ".dtbo"
            overlay_f = "overlays/" + devicetree_overlay
            log.info("Getting overlay " + devicetree_overlay)
            url = url_template.format(build_date, overlay_f)
            file = os.path.join(dest, devicetree_overlay)
            self.download(url, file)

        if not kernel:
            kernel = ["kernel.img", "kernel7.img", "kernel7l.img"]
        else:
            kernel = [kernel]

        if not isinstance(kernel, list):
            kernel = [kernel]

        for k in kernel:
            if "img" not in k:
                k = k + ".img"
            log.info("Get kernel " + k)
            url = url_template.format(build_date, k)
            file = os.path.join(dest, k)
            self.download(url, file)

        tar_file = "rpi_modules_32bit.tar.gz"
        log.info("Get modules " + tar_file)
        url = url_template.format(build_date, tar_file)
        file = os.path.join(dest, tar_file)
        self.download(url, file)

        with tarfile.open(file) as tf:
            if modules:
                log.info("Extracting module " + modules)
                module_files = [
                    tarinfo
                    for tarinfo in tf.getmembers()
                    if tarinfo.name.startswith(f"./{modules}")
                ]
            else:
                # extract all
                log.info("Extracting all modules")
                module_files = [tarinfo for tarinfo in tf.getmembers()]
            tf.extractall(path=dest, members=module_files)

    def _get_files_noos(self, source, source_root, branch, project, platform):
        dest = "outs"
        if not os.path.isdir(dest):
            os.mkdir(dest)
        if source == "artifactory":
            url_template = (
                "https://{}/artifactory/sdg-generic-development/no-OS/{}/{}/{}/{}"
            )
            url = url_template.format(source_root, branch, "", "", "")
            build_date = get_newest_folder(listFD(url))
            url = url_template.format(
                source_root, branch, build_date, platform, project + ".zip"
            )
            log.info(url)
            file = os.path.join(dest, project + ".zip")
            self.download(url, file)
            # unzip the files
            shutil.unpack_archive(file, dest)

    def _get_files(
        self,
        design_name,
        reference_boot_folder,
        devicetree_subfolder,
        boot_subfolder,
        hdl_folder,
        details,
        source,
        source_root,
        branch,
        devicetree,
        devicetree_overlay,
        kernel,
        modules,
        noos_project,
        platform,
        folder=None,
        firmware=False,
        noos=False,
        microblaze=False,
        rpi=False,
        url_template=None,
        version=None,
    ):
        if not kernel:
            kernel = False
            kernel_root = False

        dt = False

        if details["carrier"] in ["ZCU102", "ADRV2CRR-FMC"]:
            kernel = "Image"
            kernel_root = "zynqmp-common"
            dt = "system.dtb"
            arch = "arm64"
        elif (
            details["carrier"] in ["Zed-Board", "ZC702", "ZC706", "CORAZ7S"]
            or "ADRV936" in design_name.upper()
        ):
            kernel = "uImage"
            kernel_root = "zynq-common"
            dt = "devicetree.dtb"
            arch = "arm"
        elif "ADALM" in details["carrier"]:
            firmware = True
        elif details["carrier"] in ["KC705", "KCU105", "VC707", "VCU118"]:
            arch = "microblaze"
        elif "RPI" in details["carrier"]:
            kernel = kernel
            modules = modules
        elif details["carrier"] in ["Maxim", "ADICUP"]:
            pass
        else:
            raise Exception("Carrier not supported")

        if firmware:
            # Get firmware
            assert (
                "pluto" in details["carrier"].lower()
                or "m2k" in details["carrier"].lower()
                or "adalm-2000" in details["carrier"].lower()
            ), "Firmware downloads only available for pluto and m2k"
            self._download_firmware(details["carrier"], source, branch, version=version)
        else:

            if source == "local_fs":  # to fix
                if not source_root:
                    source_root = "/var/lib/tftpboot"
                kernel_root = os.path.join(source_root, kernel_root)
                # design_source_root = os.path.join(source_root, design_name)

            if noos:
                self._get_files_noos(
                    source, source_root, branch, noos_project, platform
                )

            if microblaze:
                self._get_files_hdl(
                    hdl_folder, source, source_root, branch, hdl_output=True
                )
                self._get_files_linux(
                    design_name,
                    source,
                    source_root,
                    branch,
                    kernel,
                    kernel_root,
                    dt,
                    arch,
                    microblaze,
                )

            if rpi:
                self._get_files_rpi(
                    source,
                    source_root,
                    branch,
                    kernel,
                    devicetree,
                    devicetree_overlay,
                    modules,
                )

            if folder:
                if folder == "boot_partition":
                    self._get_files_boot_partition(
                        reference_boot_folder,
                        devicetree_subfolder,
                        boot_subfolder,
                        source,
                        source_root,
                        branch,
                        kernel,
                        kernel_root,
                        dt,
                        url_template=url_template,
                    )
                elif folder == "hdl_linux":
                    self._get_files_hdl(
                        hdl_folder, source, source_root, branch, hdl_output=False
                    )
                    self._get_files_linux(
                        design_name,
                        source,
                        source_root,
                        branch,
                        kernel,
                        kernel_root,
                        dt,
                        arch,
                    )
                else:
                    raise Exception("folder not supported")

    def download_boot_files(
        self,
        design_name,
        source="local_fs",
        source_root="/var/lib/tftpboot",
        branch="main",
        firmware=None,
        boot_partition=None,
        noos=None,
        microblaze=None,
        rpi=None,
        url_template=None,
        version=None,
    ):
        """download_boot_files Download bootfiles for target design.
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
            http and artifactory sources. Default is main

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
        devicetree = self.devicetree
        devicetree_overlay = self.devicetree_overlay
        kernel = self.kernel
        modules = self.modules
        noos_project = self.no_os_project
        platform = self.platform

        assert design_name in board_configs, "Invalid design name"

        if not firmware:
            matched = re.match("v[0-1].[0-9][0-9]", branch)
            if bool(matched) and design_name in ["pluto", "m2k"]:
                raise Exception("Add --firmware to command")

        branch = branch
        if boot_partition:
            folder = "boot_partition"
        else:
            folder = "hdl_linux"

        if noos or microblaze or rpi:
            folder = None

        # get files from boot partition folder
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
            devicetree,
            devicetree_overlay,
            kernel,
            modules,
            noos_project,
            platform,
            folder,
            firmware,
            noos,
            microblaze,
            rpi,
            url_template,
            version,
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

    def retry_session(
        self,
        retries=3,
        backoff_factor=0.3,
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
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def download(self, url, fname, username=None, cloudsmith_token=None):
        # Cloudsmith path
        if "cloudsmith.io" in url:
            # get credentials such as username and token hard coded need to pass in the ci or env. Ideally we will use the service account for this
            username = self.username
            cloudsmith_token = self.cloudsmith_token
            if not username or not cloudsmith_token:
                raise Exception(
                    "Cloudsmith credentials missing, make sure service user and token are provided"
                )
            resp = self.retry_session().get(
                url, stream=True, auth=(username, cloudsmith_token)
            )
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            sha256_hash = hashlib.sha256()
            with open(fname, "wb") as file, tqdm(
                desc=fname,
                total=total,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for chunk in resp.iter_content(chunk_size=8192):
                    size = file.write(chunk)
                    sha256_hash.update(chunk)
                    bar.update(size)
            hash = sha256_hash.hexdigest()
            with open(os.path.join(os.path.dirname(fname), "hashes.txt"), "a") as h:
                h.write(f"{os.path.basename(fname)},{hash}\n")

        # artifactory path
        else:
            resp = self.retry_session().get(url, stream=True)
            if not resp.ok:
                raise Exception(os.path.basename(fname) + " - File not found!")
            total = int(resp.headers.get("content-length", 0))
            sha256_hash = hashlib.sha256()
            with open(fname, "wb") as file, tqdm(
                desc=fname,
                total=total,
                unit="iB",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for data in resp.iter_content(chunk_size=1024):
                    size = file.write(data)
                    sha256_hash.update(data)
                    bar.update(size)
            hash = sha256_hash.hexdigest()
            with open(os.path.join(os.path.dirname(fname), "hashes.txt"), "a") as h:
                h.write(f"{os.path.basename(fname)},{hash}\n")

    def check(self, fname, ref, hash_type="md5"):
        if hash_type == "md5":
            hash_obj = hashlib.md5()
        elif hash_type == "sha256":
            hash_obj = hashlib.sha256()
        else:
            raise Exception("Unsupported hash type")
        tlfile = pathlib.Path(fname)
        total = os.path.getsize(tlfile)
        with open(fname, "rb") as f, tqdm(
            desc=f"Hashing: {fname}",
            total=total,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
                size = len(chunk)
                bar.update(size)
        h = hash_obj.hexdigest()
        if h == ref:
            log.info(f"{hash_type.upper()} Check: PASSED")
        else:
            log.error(f"{hash_type.upper()} Check: FAILED")
            raise Exception(f"{hash_type.upper()} hash check failed")

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
