import hashlib
import logging
import os
import re
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from tqdm import tqdm

log = logging.getLogger(__name__)


class CloudsmithDownloader:
    """Handles all Cloudsmith-related download operations."""

    BOOT_PARTITION_REPO = "sdg-boot-partition"
    LINUX_RPI_REPO = "sdg-linux-rpi"
    API_BASE = "https://api.cloudsmith.io/v1/packages/adi"

    def __init__(self, username, token):
        if not username or not token:
            raise Exception(
                "Cloudsmith credentials missing. "
                "Pass --cloudsmith-auth user:token or set CLOUDSMITH_AUTH."
            )
        self.username = username
        self.token = token

    def _get_headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    def _retry_session(
        self,
        retries=3,
        backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 504),
    ):
        session = requests.Session()
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

    def _download_file(self, url, fname):
        """Download a file with progress bar and hash computation."""
        resp = self._retry_session().get(
            url, stream=True, auth=(self.username, self.token)
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
        file_hash = sha256_hash.hexdigest()
        with open(os.path.join(os.path.dirname(fname), "hashes.txt"), "a") as h:
            h.write(f"{os.path.basename(fname)},{file_hash}\n")
        return file_hash

    def _verify_hash(self, fname, expected, hash_type="sha256"):
        """Verify file integrity against an expected hash."""
        if hash_type == "md5":
            hash_obj = hashlib.md5()
        elif hash_type == "sha256":
            hash_obj = hashlib.sha256()
        else:
            raise Exception(f"Unsupported hash type: {hash_type}")

        total = os.path.getsize(fname)
        with open(fname, "rb") as f, tqdm(
            desc=f"Hashing: {fname}",
            total=total,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
                bar.update(len(chunk))

        if hash_obj.hexdigest() != expected:
            raise Exception(f"{hash_type.upper()} hash check failed for {fname}")
        log.info(f"{hash_type.upper()} Check: PASSED")

    def _download_and_verify(self, package, filename):
        """Download a package and verify its SHA256 checksum."""
        cdn_url = package["cdn_url"]
        sha256 = package["checksum_sha256"]
        dest = "outs"
        os.makedirs(dest, exist_ok=True)
        out_path = os.path.join(dest, filename)

        log.info(f"Downloading {filename} from {cdn_url}")
        self._download_file(cdn_url, out_path)
        if sha256:
            self._verify_hash(out_path, sha256)
        log.info(f"Downloaded and verified: {out_path}")

    # -------------------------------------------------------------------------
    # API query helpers
    # -------------------------------------------------------------------------

    def _paginated_query(self, query, repo, label="packages", max_pages=3):
        """Execute a paginated Cloudsmith API query and return all packages."""
        headers = self._get_headers()
        all_packages = []
        page = 1
        page_size = 500
        url = (
            f"{self.API_BASE}/{repo}/"
            f"?query={query}&page={page}&page_size={page_size}"
        )
        log.info(f"Fetching {label}: {url}")

        while url and page <= max_pages:
            log.info(f"Fetching page {page} for {label}")
            resp = self._retry_session().get(url, headers=headers)
            resp.raise_for_status()
            page_data = resp.json()

            if isinstance(page_data, dict) and "results" in page_data:
                all_packages.extend(page_data["results"])
                url = page_data.get("next")
                page += 1
            elif isinstance(page_data, list):
                all_packages.extend(page_data)
                if len(page_data) >= page_size:
                    page += 1
                    url = (
                        f"{self.API_BASE}/{repo}/"
                        f"?query={query}&page={page}&page_size={page_size}"
                    )
                else:
                    url = None
            else:
                raise Exception("Unexpected response format from Cloudsmith API")

        if page > max_pages and url:
            log.warning(f"Reached max page limit ({max_pages}) for {label}")

        log.info(f"Total packages for {label}: {len(all_packages)}")
        return all_packages

    @staticmethod
    def _filter_completed(packages):
        """Return only completed raw-format packages with essential fields."""
        return [
            {
                "name": pkg.get("name"),
                "cdn_url": pkg.get("cdn_url"),
                "version": pkg.get("version"),
                "checksum_sha256": pkg.get("checksum_sha256"),
            }
            for pkg in packages
            if pkg.get("status_str") == "Completed" and pkg.get("format") == "raw"
        ]

    def _get_latest_version_prefix(
        self, package_version, repo,
        date_format="%Y_%m_%d-%H_%M_%S", kernel_root=None,
    ):
        """Find the latest build date and return the full version prefix path."""
        query = f"version:{package_version.rstrip('/')}*"
        all_packages = self._paginated_query(
            query, repo, label="version metadata"
        )

        if not all_packages:
            raise Exception(
                f"No packages found for version: {package_version}"
            )

        date_pattern = self._build_date_pattern(date_format)
        pkg_version_base = package_version.rstrip("/")
        date_to_prefix = {}

        for pkg in all_packages:
            version = pkg.get("version", "").rstrip("/")
            if not version.startswith(pkg_version_base):
                continue
            segments = version.split("/")
            for i, segment in enumerate(segments):
                if date_pattern.match(segment):
                    try:
                        date_obj = datetime.strptime(segment, date_format)
                    except ValueError:
                        break
                    if kernel_root and kernel_root in segments[i + 1:]:
                        kr_idx = segments.index(kernel_root, i + 1)
                        date_to_prefix[date_obj] = "/".join(segments[:kr_idx])
                    elif date_obj not in date_to_prefix:
                        date_to_prefix[date_obj] = "/".join(segments[:i + 1])
                    break

        if not date_to_prefix:
            raise Exception(
                f"No valid dates found in metadata for {package_version}"
            )

        latest_date = max(date_to_prefix.keys())
        latest_prefix = date_to_prefix[latest_date]
        log.info(
            f"Latest date: {latest_date.strftime(date_format)}, "
            f"prefix: {latest_prefix}"
        )
        return latest_prefix

    @staticmethod
    def _build_date_pattern(date_format):
        """Convert a strftime format into a compiled regex pattern."""
        regex = date_format
        regex = regex.replace("%Y", r"20\d{2}")
        regex = regex.replace("%m", r"\d{2}")
        regex = regex.replace("%d", r"\d{2}")
        regex = regex.replace("%H", r"\d{2}")
        regex = regex.replace("%M", r"\d{2}")
        regex = regex.replace("%S", r"\d{2}")
        return re.compile(f"^{regex}$")

    # -------------------------------------------------------------------------
    # Public download methods
    # -------------------------------------------------------------------------

    def download_boot_files(
        self, branch, kernel, dt, board_name, kernel_root,
        reference_boot_folder=None, boot_subfolder=None,
        devicetree_subfolder=None, version=None,
    ):
        """Fetch boot files (BOOT.BIN, kernel, dtb, sysfiles) from Cloudsmith."""
        log.info("Getting standard boot files (Cloudsmith)")

        ref_folder = reference_boot_folder or board_name
        boot_path = (
            f"{ref_folder}/{boot_subfolder}" if boot_subfolder else ref_folder
        )
        dt_path = (
            f"{ref_folder}/{devicetree_subfolder}"
            if devicetree_subfolder else boot_path
        )

        pkg_version = (
            version.rstrip("/") + "/" if version
            else f"boot_partition/{branch}/"
        )
        version_prefix = self._get_latest_version_prefix(
            pkg_version, self.BOOT_PARTITION_REPO, kernel_root=kernel_root,
        )

        unique_paths = {boot_path, dt_path}
        version_clauses = [
            f"version:{version_prefix}/{p}/*" for p in unique_paths
        ]
        version_clauses.append(f"version:{version_prefix}/{kernel_root}")

        name_filter = (
            "name:^BOOT.BIN$%20OR%20name:^bootgen_sysfiles.tgz$"
            "%20OR%20name:*.dtb$%20OR%20name:*mage$"
        )
        query = (
            f"({'%20OR%20'.join(version_clauses)})"
            f"%20AND%20({name_filter})"
        )

        all_packages = self._paginated_query(
            query, self.BOOT_PARTITION_REPO, label="boot_files"
        )
        if not all_packages:
            raise Exception(
                f"No packages found for branch={branch}, board={board_name}"
            )
        filtered = self._filter_completed(all_packages)

        for filename in [kernel, "BOOT.BIN", "bootgen_sysfiles.tgz", dt]:
            exp_path = dt_path if filename.endswith(".dtb") else None
            matched = self._match_boot_file(filtered, filename, exp_path)
            if not matched:
                raise Exception(
                    f"No package found for {filename} "
                    f"(branch={branch}, board={board_name})"
                )
            self._download_and_verify(matched, filename)

    def download_rpi_files(self, branch, kernel, arch, version=None):
        """Fetch RPi boot and module tarballs from Cloudsmith."""
        log.info("Getting RPi files from Cloudsmith")

        pkg_version = (
            version.rstrip("/") + "/" if version
            else f"linux_rpi/releases/{branch}/"
        )
        version_prefix = self._get_latest_version_prefix(
            pkg_version, self.LINUX_RPI_REPO, date_format="%Y_%m_%d-%H_%M",
        )

        boot_tar = f"rpi_latest_boot_{arch}.tar.gz"
        modules_tar = f"rpi_modules_{arch}.tar.gz"

        query = (
            f"version:{version_prefix}*"
            f"%20AND%20(name:{boot_tar}%20OR%20name:{modules_tar})"
        )

        all_packages = self._paginated_query(
            query, self.LINUX_RPI_REPO, label="rpi_files"
        )
        filtered = self._filter_completed(all_packages)

        os.makedirs("outs", exist_ok=True)
        for filename in [boot_tar, modules_tar]:
            matched = next(
                (p for p in filtered if p.get("name") == filename), None
            )
            if not matched:
                raise Exception(
                    f"No package found for {filename} "
                    f"(version prefix: {version_prefix})"
                )
            self._download_and_verify(matched, filename)

    def download_firmware(self, device, version=None):
        """Download firmware (pluto/m2k) from Cloudsmith."""
        if "m2k" in device.lower() or "adalm-2000" in device.lower():
            dev = "m2k"
            fw_filename = "m2k-fw-v0.33-1-gdce1.zip"
        elif "pluto" in device.lower():
            dev = "plutosdr"
            fw_filename = "plutosdr-fw-v0.39-1-g8456.zip"
        else:
            raise Exception(f"Unknown device: {device}")

        ver = version or "latest"
        url = (
            f"https://dl.cloudsmith.io/basic/adi/{dev}-fw"
            f"/raw/versions/{ver}/{fw_filename}"
        )
        log.info(f"Downloading {fw_filename} from Cloudsmith: {url}")

        os.makedirs("outs", exist_ok=True)
        self._download_file(url, os.path.join("outs", fw_filename))

    # -------------------------------------------------------------------------
    # Internal match helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _match_boot_file(packages, filename, expected_version_path=None):
        """Find the matching package for a given boot filename.

        For DTB files, uses expected_version_path with trailing slash to
        disambiguate sibling folders (e.g. adrv9002/ vs adrv9002-rx2tx2/).
        """
        for pkg in packages:
            name = pkg.get("name", "")
            if filename == "BOOT.BIN" and name == "BOOT.BIN":
                return pkg
            if filename == "bootgen_sysfiles.tgz" and name == "bootgen_sysfiles.tgz":
                return pkg
            if filename.endswith(".dtb") and name.endswith(".dtb"):
                if expected_version_path:
                    if f"{expected_version_path}/" in pkg.get("version", ""):
                        return pkg
                else:
                    return pkg
            if filename in ("Image", "uImage") and name in ("Image", "uImage"):
                return pkg
        return None
