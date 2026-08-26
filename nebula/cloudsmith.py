import hashlib
import logging
import os
import re
import time
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

log = logging.getLogger(__name__)


class CloudsmithDownloader:
    """Download build artifacts from Cloudsmith repositories.

    Handles boot partition files, Raspberry Pi tarballs, and firmware
    packages with paginated API queries, SHA256 verification, and retry
    logic for packages still being processed.
    """

    BOOT_PARTITION_REPO = "sdg-boot-partition"
    LINUX_RPI_REPO = "sdg-linux-rpi"
    M2K_FIRMWARE_REPO = "m2k-fw"
    PLUTOSDR_FIRMWARE_REPO = "plutosdr-fw"
    API_BASE = "https://api.cloudsmith.io/v1/packages/adi"

    def __init__(self, username, token):
        """Initialize the Cloudsmith downloader.

        :param username: Cloudsmith account username.
        :type username: str
        :param token: Cloudsmith API token.
        :type token: str
        :raises Exception: If credentials are missing.
        """
        if not username or not token:
            raise Exception(
                "Cloudsmith credentials missing. "
                "Pass --cloudsmith-auth user:token or set CLOUDSMITH_AUTH."
            )
        self.username = username
        self.token = token
        self._session = None

    def _get_headers(self):
        """Return authorization headers for the Cloudsmith API.

        :returns: Dictionary of HTTP headers.
        :rtype: dict
        """
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }

    def _get_session(self):
        """Return a shared requests session with retry logic.

        :returns: Configured requests session.
        :rtype: requests.Session
        """
        if self._session is None:
            self._session = requests.Session()
            retry = Retry(
                total=3,
                read=3,
                connect=3,
                backoff_factor=0.3,
                status_forcelist=(429, 500, 502, 504),
            )
            adapter = HTTPAdapter(max_retries=retry)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
        return self._session

    def _download_file(self, url, fname):
        """Download a file with progress bar, computing SHA256 during transfer.

        :param url: CDN URL to download from.
        :type url: str
        :param fname: Local file path to write to.
        :type fname: str
        :returns: Hex digest of the downloaded file's SHA256 hash.
        :rtype: str
        """
        resp = self._get_session().get(
            url, stream=True, auth=(self.username, self.token), timeout=(10, 60)
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

    def _download_and_verify(self, package, filename):
        """Download a package and verify its SHA256 checksum.

        :param package: Package dict with ``cdn_url`` and ``checksum_sha256``.
        :type package: dict
        :param filename: Filename to save as in the ``outs/`` directory.
        :type filename: str
        :raises Exception: If SHA256 verification fails.
        """
        cdn_url = package["cdn_url"]
        sha256 = package["checksum_sha256"]
        dest = "outs"
        os.makedirs(dest, exist_ok=True)
        out_path = os.path.join(dest, filename)

        log.info(f"Downloading {filename} from {cdn_url}")
        file_hash = self._download_file(cdn_url, out_path)
        if sha256:
            if file_hash != sha256:
                raise Exception(f"SHA256 hash check failed for {out_path}")
            log.info("SHA256 Check: PASSED")
        else:
            log.warning(
                f"No SHA256 checksum provided for {filename}; "
                "skipping sha256 verification"
            )
        log.info(f"Downloaded and verified: {out_path}")

    def _paginated_query(self, query, repo, label="packages"):
        """Execute a paginated query against the Cloudsmith API.

        :param query: Cloudsmith query string with filters.
        :type query: str
        :param repo: Repository slug (e.g. ``"sdg-boot-partition"``).
        :type repo: str
        :param label: Label for log messages.
        :type label: str
        :returns: List of all package dicts across all pages.
        :rtype: list[dict]
        """
        headers = self._get_headers()
        session = self._get_session()
        all_packages = []
        page = 1
        page_size = 500
        total_pages = None
        base_url = f"{self.API_BASE}/{repo}/"
        log.info(f"Fetching {label}: query={query}")

        while True:
            log.debug(f"Fetching page {page} for {label}")
            params = {"query": query, "page": page, "page_size": page_size}
            resp = session.get(base_url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()

            if total_pages is None:
                total_pages = int(resp.headers.get("x-pagination-pagetotal", 1))
                log.info(f"Total pages for {label}: {total_pages}")
                if total_pages == 0:
                    break

            page_data = resp.json()

            if isinstance(page_data, dict) and "results" in page_data:
                all_packages.extend(page_data["results"])
            elif isinstance(page_data, list):
                all_packages.extend(page_data)
            else:
                raise Exception("Unexpected response format from Cloudsmith API")

            if page >= total_pages:
                break
            page += 1

        log.info(f"Total packages for {label}: {len(all_packages)}")
        return all_packages

    @staticmethod
    def _filter_completed(packages):
        """Filter packages to only those with status ``"Completed"``.

        :param packages: Raw package list from the API.
        :type packages: list[dict]
        :returns: List of dicts with ``name``, ``cdn_url``, ``version``,
            and ``checksum_sha256`` for completed raw packages.
        :rtype: list[dict]
        """
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

    def _query_and_filter(
        self, query, repo, label, expected_filenames,
        max_retries=3, retry_delay=15,
    ):
        """Query packages and filter to completed, retrying for pending files.

        Retries only when expected files exist in the API response but have
        not yet completed server-side processing (virus scan, validation).

        :param query: Cloudsmith query string.
        :type query: str
        :param repo: Repository slug.
        :type repo: str
        :param label: Label for log messages.
        :type label: str
        :param expected_filenames: Set of filenames expected in results.
        :type expected_filenames: set[str]
        :param max_retries: Maximum number of retry attempts.
        :type max_retries: int
        :param retry_delay: Seconds to wait between retries.
        :type retry_delay: int
        :returns: Tuple of (all_packages, filtered_packages).
        :rtype: tuple[list[dict], list[dict]]
        """
        for attempt in range(max_retries + 1):
            all_packages = self._paginated_query(query, repo, label=label)
            filtered = self._filter_completed(all_packages)

            if not expected_filenames:
                return all_packages, filtered

            filtered_names = {pkg["name"] for pkg in filtered}
            all_names = {
                pkg.get("name") for pkg in all_packages
                if pkg.get("format") == "raw"
            }
            pending = (expected_filenames & all_names) - filtered_names

            if not pending:
                break

            if attempt < max_retries:
                log.info(
                    f"Waiting for packages to complete processing: {pending} "
                    f"(retry {attempt + 1}/{max_retries})"
                )
                time.sleep(retry_delay)

        return all_packages, filtered

    def _get_latest_version_prefix(
        self,
        package_version,
        repo,
        date_format="%Y_%m_%d-%H_%M_%S",
        kernel_root=None,
    ):
        """Resolve the latest date-stamped version prefix from metadata.

        Queries metadata marker files (``README.txt`` for boot partition,
        ``rpi_archives_properties.txt`` for RPi) to find the most recent
        date segment in the version path, avoiding parsing all packages.

        :param package_version: Base version path to search under.
        :type package_version: str
        :param repo: Repository slug.
        :type repo: str
        :param date_format: strftime format of the date segment.
        :type date_format: str
        :param kernel_root: Optional kernel root to anchor prefix depth.
        :type kernel_root: str or None
        :returns: Full version prefix up to the resolved date segment.
        :rtype: str
        :raises Exception: If no packages or valid dates are found.
        """
        if repo == self.BOOT_PARTITION_REPO:
            query = f"version:{package_version.rstrip('/')}* AND name:README.txt"
        elif repo == self.LINUX_RPI_REPO:
            query = f"version:{package_version.rstrip('/')}* AND name:rpi_archives_properties.txt"
        else:
            log.info(f"unknown cloudsmith repo: {repo}, using generic query")
            query = f"version:{package_version.rstrip('/')}* "
        all_packages = self._paginated_query(query, repo, label="version metadata")

        if not all_packages:
            raise Exception(f"No packages found for version: {package_version}")

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
                    if kernel_root and kernel_root in segments[i + 1 :]:
                        kr_idx = segments.index(kernel_root, i + 1)
                        date_to_prefix[date_obj] = "/".join(segments[:kr_idx])
                    elif date_obj not in date_to_prefix:
                        date_to_prefix[date_obj] = "/".join(segments[: i + 1])
                    break

        if not date_to_prefix:
            raise Exception(f"No valid dates found in metadata for {package_version}")

        latest_date = max(date_to_prefix.keys())
        latest_prefix = date_to_prefix[latest_date]
        log.info(
            f"Latest date: {latest_date.strftime(date_format)}, "
            f"prefix: {latest_prefix}"
        )
        return latest_prefix

    @staticmethod
    def _build_date_pattern(date_format):
        """Convert a strftime format string into a compiled regex pattern.

        :param date_format: strftime format (e.g. ``"%Y_%m_%d-%H_%M_%S"``).
        :type date_format: str
        :returns: Compiled regex matching the date format.
        :rtype: re.Pattern
        """
        regex = date_format
        regex = regex.replace("%Y", r"20\d{2}")
        regex = regex.replace("%m", r"\d{2}")
        regex = regex.replace("%d", r"\d{2}")
        regex = regex.replace("%H", r"\d{2}")
        regex = regex.replace("%M", r"\d{2}")
        regex = regex.replace("%S", r"\d{2}")
        return re.compile(f"^{regex}$")

    def download_boot_files(
        self,
        branch,
        kernel,
        dt,
        board_name,
        kernel_root,
        reference_boot_folder=None,
        boot_subfolder=None,
        devicetree_subfolder=None,
        boot_filename=None,
        uboot_bootloader=None,
        version=None,
    ):
        """Download boot partition files for a given board from Cloudsmith.

        Resolves the latest date-stamped version and downloads the kernel,
        device tree, and config-declared boot files. No filenames are
        hardcoded — every artifact comes from the board config.

        :param branch: Release branch (e.g. ``"2026_r1"``).
        :type branch: str
        :param kernel: Kernel filename (``"Image"``/``"uImage"``/``"zImage"``).
        :type kernel: str
        :param dt: Device tree filename.
        :type dt: str
        :param board_name: Target board name.
        :type board_name: str
        :param kernel_root: Kernel root folder (e.g. ``"zynqmp-common"``).
        :type kernel_root: str
        :param reference_boot_folder: Override folder for boot file lookup.
        :type reference_boot_folder: str or None
        :param boot_subfolder: Subfolder under reference folder for boot files.
        :type boot_subfolder: str or None
        :param devicetree_subfolder: Subfolder for device tree files.
        :type devicetree_subfolder: str or None
        :param boot_filename: Required comma-separated boot files from the
            board's boot path (Netbox Boot_filename field).
        :type boot_filename: str or None
        :param uboot_bootloader: Bootloader config in ``kernel_root``
            (e.g. ``"extlinux.conf"`` for Intel carriers).
        :type uboot_bootloader: str or None
        :param version: Explicit version path override.
        :type version: str or None
        :raises Exception: If ``boot_filename`` is empty or packages are missing.
        """
        log.info("Getting standard boot files (Cloudsmith)")

        ref_folder = reference_boot_folder or board_name
        boot_path = f"{ref_folder}/{boot_subfolder}" if boot_subfolder else ref_folder
        dt_path = (
            f"{ref_folder}/{devicetree_subfolder}"
            if devicetree_subfolder
            else boot_path
        )

        boot_files = [(kernel_root, kernel)]

        if uboot_bootloader:
            boot_files.append((kernel_root, uboot_bootloader))

        parsed = [
            f.strip() for f in (boot_filename or "").split(",") if f.strip()
        ]
        if not parsed:
            raise Exception(
                f"No boot_filename configured for board={board_name}. "
                "Set the Boot_filename custom field in Netbox."
            )

        for fn in parsed:
            boot_files.append((boot_path, fn))

        if dt:
            boot_files.append((dt_path, dt))

        pkg_version = (
            version.rstrip("/") + "/" if version else f"boot_partition/{branch}/"
        )
        version_prefix = self._get_latest_version_prefix(
            pkg_version,
            self.BOOT_PARTITION_REPO,
        )

        arch = kernel_root.replace("_common", "").replace("-common", "")
        arch = arch.replace("socfpga_", "")
        base_prefix = f"{version_prefix}/boot_partition/adi-{arch}"

        unique_subfolders = {subfolder for subfolder, _ in boot_files}
        version_clauses = [
            f"version:{base_prefix}/{sf}/*" for sf in unique_subfolders
        ]

        unique_filenames = {filename for _, filename in boot_files}
        name_clauses = [f"name:{fn}" for fn in unique_filenames]
        name_filter = " OR ".join(name_clauses)

        query = f"({' OR '.join(version_clauses)}) AND ({name_filter})"

        all_packages, filtered = self._query_and_filter(
            query, self.BOOT_PARTITION_REPO, label="boot_files",
            expected_filenames=unique_filenames,
        )
        if not all_packages:
            raise Exception(
                f"No packages found for branch={branch}, board={board_name}"
            )

        missing = []
        for subfolder, filename in boot_files:
            expected_prefix = f"{base_prefix}/{subfolder}/"
            matched = next(
                (
                    pkg
                    for pkg in filtered
                    if pkg.get("name") == filename
                    and expected_prefix in pkg.get("version", "")
                ),
                None,
            )
            if not matched:
                log.warning(
                    f"No package found for {filename} "
                    f"(branch={branch}, subfolder={subfolder})"
                )
                missing.append(filename)
                continue
            self._download_and_verify(matched, filename)

        if missing:
            raise Exception(
                f"Missing packages for branch={branch}, board={board_name}: "
                f"{', '.join(missing)}"
            )

    def download_rpi_files(self, branch, arch, version=None):
        """Download Raspberry Pi boot and module tarballs from Cloudsmith.

        :param branch: Release branch (e.g. ``"rpi-6.12.y"``).
        :type branch: str
        :param arch: Architecture string (``"32bit"`` or ``"64bit"``).
        :type arch: str
        :param version: Explicit version path override.
        :type version: str or None
        :raises Exception: If expected packages are not found.
        """
        log.info("Getting RPi files from Cloudsmith")

        pkg_version = (
            version.rstrip("/") + "/" if version else f"linux_rpi/releases/{branch}/"
        )
        version_prefix = self._get_latest_version_prefix(
            pkg_version,
            self.LINUX_RPI_REPO,
            date_format="%Y_%m_%d-%H_%M",
        )

        boot_tar = f"rpi_latest_boot_{arch}.tar.gz"
        modules_tar = f"rpi_modules_{arch}.tar.gz"

        query = (
            f"version:{version_prefix}*"
            f" AND (name:{boot_tar} OR name:{modules_tar})"
        )

        _, filtered = self._query_and_filter(
            query, self.LINUX_RPI_REPO, label="rpi_files",
            expected_filenames={boot_tar, modules_tar},
        )

        os.makedirs("outs", exist_ok=True)
        for filename in [boot_tar, modules_tar]:
            matched = next((p for p in filtered if p.get("name") == filename), None)
            if not matched:
                raise Exception(
                    f"No package found for {filename} "
                    f"(version prefix: {version_prefix})"
                )
            self._download_and_verify(matched, filename)

    def download_firmware(self, device, version=None):
        """Download firmware zip for PlutoSDR or ADALM2000 from Cloudsmith.

        :param device: Device identifier (e.g. ``"pluto"``, ``"m2k"``).
        :type device: str
        :param version: Firmware version string, defaults to ``"latest"``.
        :type version: str or None
        :raises Exception: If the device is not recognized.
        """
        if "m2k" in device.lower() or "adalm-2000" in device.lower():
            repo = self.M2K_FIRMWARE_REPO
            fw_filename = "m2k-fw-v0.33-1-gdce1.zip"
        elif "pluto" in device.lower():
            repo = self.PLUTOSDR_FIRMWARE_REPO
            fw_filename = "plutosdr-fw-v0.39-1-g8456.zip"
        else:
            raise Exception(f"Unknown device: {device}")

        ver = version or "latest"
        url = (
            f"https://dl.cloudsmith.io/basic/adi/{repo}"
            f"/raw/versions/{ver}/{fw_filename}"
        )
        log.info(f"Downloading {fw_filename} from Cloudsmith: {url}")

        os.makedirs("outs", exist_ok=True)
        self._download_file(url, os.path.join("outs", fw_filename))
