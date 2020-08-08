import requests
import lzma
from tqdm import tqdm
import pathlib
import hashlib
import os
import csv
import yaml


class downloader:
    def __init__(self):
        pass

    def _get_files(self, design_name, details):
        firmware = False
        kernel = False
        dt = False

        if details["carrier"] in ["ZCU102"]:
            kernel = "Image"
            dt = "system.dtb"
        elif (
            details["carrier"] in ["Zed-Board", "ZC702", "ZC706"]
            or "ADRV936" in details["carrier"]
        ):
            kernel = "uImage"
            dt = "devicetree.dtb"
        elif "PLUTO" in details["carrier"]:
            firmware = True
        else:
            raise Exception("Carrier not supported")

        if firmware:
            # Get firmware
            print("Get firmware")
        else:
            print("Get standard boot files")
            # Get kernel
            print("Get", kernel)

            # Get BOOT.BIN

            # Get device tree
            print("Get", dt)

            # Get support files (bootgen_sysfiles.tgz)

    def download_boot_files(self, design_name):
        path = pathlib.Path(__file__).parent.absolute()
        res = os.path.join(path, "resources", "board_table.yaml")
        with open(res) as f:
            board_configs = yaml.load(f, Loader=yaml.FullLoader)

        assert design_name in board_configs, "Invalid design name"

        self._get_files(design_name, board_configs[design_name])

    def download_sdcard_release(self, release="2019_R1"):
        rel = self.releases(release)
        self.download(rel["link"], rel["xzname"])
        self.check(rel["xzname"], rel["xzmd5"])
        self.extract(rel["xzname"], rel["imgname"])
        self.check(rel["imgname"], rel["imgmd5"])
        print("Image file available:", rel["imgname"])

    def releases(self, release="2019_R1"):
        rel = dict()
        if release == "2019_R1":
            rel["imgname"] = "2019_R1-2020_02_04.img"
            rel["xzmd5"] = "49c121d5e7072ab84760fed78812999f"
            rel["imgmd5"] = "40aa0cd80144a205fc018f479eff5fce"

        elif release == "2018_R2":
            rel["imgname"] = "2018_R2-2019_05_23.img"
            rel["xzmd5"] = "c377ca95209f0f3d6901fd38ef2b4dfd"
            rel["imgmd5"] = "59c2fe68118c3b635617e36632f5db0b"
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
        total = 0
        with open(tlfile, "rb") as ifile:
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
    d.download_boot_files("zynqmp-zcu102-rev10-adrv9375")
