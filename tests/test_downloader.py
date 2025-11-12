import os
import pathlib
import shutil
from unittest.mock import Mock, patch

import pytest

from nebula import downloader

# Must be connected to analog VPN


def downloader_test(
    board_name, branch, filetype, source="artifactory", url_template=None
):
    file = {
        "firmware": None,
        "boot_partition": None,
        "noos": None,
        "microblaze": None,
        "rpi": None,
    }
    if filetype == "not_boot_partition":
        file["boot_partition"] = False
    else:
        file[filetype] = True
    yaml = os.path.join(os.path.dirname(__file__), "nebula_config", "nebula.yaml")
    d = downloader(yamlfilename=yaml, board_name=board_name)
    d.download_boot_files(
        board_name,
        source=source,
        source_root="artifactory.analog.com",
        branch=branch,
        firmware=file["firmware"],
        boot_partition=file["boot_partition"],
        noos=file["noos"],
        microblaze=file["microblaze"],
        rpi=file["rpi"],
        url_template=url_template,
    )


@pytest.fixture(autouse=True)
def run_around_tests():
    # Before test
    files = ["2019_R1-2020_02_04.img"]
    for file in files:
        if os.path.isfile(file + ".xz"):
            os.remove(file + ".xz")
        if os.path.isfile(file):
            os.remove(file)
    yield
    # After test
    for file in files:
        if os.path.isfile(file + ".xz"):
            os.remove(file + ".xz")
        if os.path.isfile(file):
            os.remove(file)


@pytest.fixture()
def test_downloader():
    if os.path.isdir("outs"):
        shutil.rmtree("outs")
    yield downloader_test
    if os.path.isdir("outs"):
        shutil.rmtree("outs")


@pytest.mark.parametrize(
    "board_name",
    ["zynq-zc706-adv7511-fmcomms11", "zynqmp-zcu102-rev10-adrv9002-rx2tx2-vcmos"],
)
@pytest.mark.parametrize("branch", ["release", "main", "2023_r2"])
@pytest.mark.parametrize("filetype", ["boot_partition"])
def test_boot_downloader(test_downloader, board_name, branch, filetype):
    test_downloader(board_name, branch, filetype)
    assert os.path.isfile("outs/BOOT.BIN")
    assert os.path.isfile("outs/bootgen_sysfiles.tgz")
    assert os.path.isfile("outs/properties.yaml")
    assert os.path.isfile("outs/hashes.txt")

    if board_name == "zynq-zc706-adv7511-fmcomms11":
        assert os.path.isfile("outs/uImage")
        assert os.path.isfile("outs/devicetree.dtb")
    if board_name == "zynqmp-zcu102-rev10-adrv9002-rx2tx2-vcmos":
        assert os.path.isfile("outs/Image")
        assert os.path.isfile("outs/system.dtb")


@pytest.mark.parametrize(
    "board_name",
    ["zynq-zc706-adv7511-fmcomms11", "zynqmp-zcu102-rev10-adrv9002-rx2tx2-vcmos"],
)
@pytest.mark.parametrize("branch", ["release", "main", "2022_r2", "2023_R2"])
@pytest.mark.parametrize("filetype", ["hdl_linux"])
def test_hdl_linux_downloader(test_downloader, board_name, branch, filetype):
    test_downloader(board_name, branch, filetype)
    assert os.path.isfile("outs/BOOT.BIN")
    assert os.path.isfile("outs/bootgen_sysfiles.tgz")
    assert os.path.isfile("outs/properties.yaml")
    assert os.path.isfile("outs/hashes.txt")

    if board_name == "zynq-zc706-adv7511-fmcomms11":
        assert os.path.isfile("outs/uImage")
        assert os.path.isfile("outs/devicetree.dtb")
    if board_name == "zynqmp-zcu102-rev10-adrv9002-rx2tx2-vcmos":
        assert os.path.isfile("outs/Image")
        assert os.path.isfile("outs/system.dtb")


@pytest.mark.parametrize("board_name", ["max32650_adxl355"])
@pytest.mark.parametrize("branch", ["main"])
@pytest.mark.parametrize("filetype", ["noos"])
def test_noos_downloader(test_downloader, board_name, branch, filetype):
    test_downloader(board_name, branch, filetype)
    file = [_ for _ in os.listdir("outs") if _.endswith(".zip")]
    assert len(file) >= 1
    assert os.path.isfile("outs/hashes.txt")


@pytest.mark.skip(reason="Not built")
@pytest.mark.parametrize("board_name", ["kc705_fmcomms4"])
@pytest.mark.parametrize("branch", ["release", "main"])
@pytest.mark.parametrize("filetype", ["microblaze"])
def test_microblaze_downloader(test_downloader, board_name, branch, filetype):
    test_downloader(board_name, branch, filetype)
    try:
        assert os.path.isfile("outs/system_top.hdf")
    except Exception:
        assert os.path.isfile("outs/system_top.xsa")
    assert os.path.isfile("outs/simpleImage.kc705_fmcomms4.strip")
    assert os.path.isfile("outs/properties.yaml")
    assert os.path.isfile("outs/hashes.txt")


@pytest.mark.parametrize("board_name", ["eval-adxrs290-pmdz"])
@pytest.mark.parametrize("branch", ["rpi-6.6.y"])
@pytest.mark.parametrize("filetype", ["rpi"])
def test_rpi_downloader(test_downloader, board_name, branch, filetype):
    test_downloader(board_name, branch, filetype)
    assert os.path.isfile("outs/kernel7l.img")
    assert os.path.isfile("outs/rpi-adxrs290.dtbo")
    assert os.path.isfile("outs/properties.txt")
    assert os.path.isfile("outs/hashes.txt")


@pytest.mark.parametrize("board_name", ["pluto"])
@pytest.mark.parametrize(
    "source, branch", [("github", "v0.33"), ("artifactory", "master")]
)
@pytest.mark.parametrize("filetype", ["firmware"])
def test_firmware_downloader(test_downloader, board_name, branch, filetype, source):
    test_downloader(board_name, branch, filetype, source=source)
    file = [_ for _ in os.listdir("outs") if _.endswith(".zip")]
    assert len(file) == 1
    assert os.path.isfile("outs/hashes.txt")


@pytest.mark.parametrize("board_name", ["zynq-zed-adv7511-ad7768-1-evb"])
@pytest.mark.parametrize("branch", ["main"])
@pytest.mark.parametrize("filetype", ["boot_partition"])
@pytest.mark.parametrize(
    "url_template",
    [
        "https://artifactory.analog.com/ui/repos/tree/Properties/sdg-generic-development"
        + "%2Ftest_boot_files%2Fmain%2FHDL_PRs%2Fpr_1942%2F2025_10_23-22_24_49"
    ],
)
def test_boot_downloader_new_flow(
    test_downloader, board_name, branch, filetype, url_template
):
    test_downloader(board_name, branch, filetype, url_template=url_template)
    assert os.path.isfile("outs/BOOT.BIN")
    assert os.path.isfile("outs/uImage")
    assert os.path.isfile("outs/bootgen_sysfiles.tgz")
    assert os.path.isfile("outs/devicetree.dtb")
    assert os.path.isfile("outs/properties.yaml")
    assert os.path.isfile("outs/hashes.txt")


@pytest.mark.skip(reason="filesize")
def test_image_downloader():
    d = downloader()
    d.download_sdcard_release()
    assert os.path.isfile("2019_R1-2020_02_04.img.xz")
    assert os.path.isfile("2019_R1-2020_02_04.img")


@pytest.mark.parametrize(
    "url",
    [
        "https://artifactory.analog.com/ui/repos/tree/Properties/sdg-generic-development%2Ftest_boot_files%2Fmain%2FHDL_PRs%2Fpr_1942%2F2025_10_23-22_24_49"
    ],
)
def test_get_info_txt(url):
    from nebula.downloader import get_info_txt

    build_info = get_info_txt(url)
    assert os.path.isfile("info.txt")
    assert "BRANCH" in build_info.keys()
    assert "PR_ID" in build_info.keys()
    assert "TIMESTAMP" in build_info.keys()
    assert "DIRECTION" in build_info.keys()
    assert "Triggered by" in build_info.keys()
    assert "COMMIT SHA" in build_info.keys()
    assert "COMMIT_DATE" in build_info.keys()


if __name__ == "__main__":
    test_image_downloader()
