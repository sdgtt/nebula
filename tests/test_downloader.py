import importlib
import os
import shutil
from unittest.mock import patch

import pytest

from nebula import downloader

downloader_module = importlib.import_module("nebula.downloader")

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


def downloader_cloudsmith_test(
    board_name, branch, filetype, source="cloudsmith", version=None
):
    cloudsmith_auth = os.environ.get("CLOUDSMITH_AUTH")
    if not cloudsmith_auth:
        pytest.skip("CLOUDSMITH_AUTH environment variable not set")
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
    d = downloader(
        yamlfilename=yaml, board_name=board_name, cloudsmith_auth=cloudsmith_auth
    )
    d.download_boot_files(
        board_name,
        source=source,
        branch=branch,
        firmware=file["firmware"],
        boot_partition=file["boot_partition"],
        noos=file["noos"],
        microblaze=file["microblaze"],
        rpi=file["rpi"],
        version=version,
    )


@pytest.fixture(autouse=True)
def cleanup():
    if os.path.isdir("outs"):
        shutil.rmtree("outs")
    files = ["2019_R1-2020_02_04.img"]
    for file in files:
        if os.path.isfile(file + ".xz"):
            os.remove(file + ".xz")
        if os.path.isfile(file):
            os.remove(file)
    yield
    if os.path.isdir("outs"):
        shutil.rmtree("outs")
    for file in files:
        if os.path.isfile(file + ".xz"):
            os.remove(file + ".xz")
        if os.path.isfile(file):
            os.remove(file)


@pytest.fixture()
def downloader_fixture():
    yield downloader_test


@pytest.fixture()
def cloudsmith_fixture():
    yield downloader_cloudsmith_test


@pytest.mark.parametrize(
    "board_name",
    ["zynq-zc706-adv7511-fmcomms11", "zynqmp-zcu102-rev10-adrv9002-rx2tx2-vcmos"],
)
@pytest.mark.parametrize("branch", ["release", "main"])
@pytest.mark.parametrize("filetype", ["boot_partition"])
def test_boot_downloader(downloader_fixture, board_name, branch, filetype):
    if branch == "main":
        with patch.object(
            downloader_module, "get_newest_folder", return_value="2026_03_18-11_24_07"
        ):
            downloader_fixture(board_name, branch, filetype)
    else:
        downloader_fixture(board_name, branch, filetype)
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
def test_hdl_linux_downloader(downloader_fixture, board_name, branch, filetype):
    downloader_fixture(board_name, branch, filetype)
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
def test_noos_downloader(downloader_fixture, board_name, branch, filetype):
    downloader_fixture(board_name, branch, filetype)
    file = [_ for _ in os.listdir("outs") if _.endswith(".zip")]
    assert len(file) >= 1
    assert os.path.isfile("outs/hashes.txt")


@pytest.mark.skip(reason="Not built")
@pytest.mark.parametrize("board_name", ["kc705_fmcomms4"])
@pytest.mark.parametrize("branch", ["release", "main"])
@pytest.mark.parametrize("filetype", ["microblaze"])
def test_microblaze_downloader(downloader_fixture, board_name, branch, filetype):
    downloader_fixture(board_name, branch, filetype)
    try:
        assert os.path.isfile("outs/system_top.hdf")
    except Exception:
        assert os.path.isfile("outs/system_top.xsa")
    assert os.path.isfile("outs/simpleImage.kc705_fmcomms4.strip")
    assert os.path.isfile("outs/properties.yaml")
    assert os.path.isfile("outs/hashes.txt")


@pytest.mark.parametrize("board_name", ["eval-adxrs290-pmdz"])
@pytest.mark.parametrize("branch", ["v6.12.y-2026r1"])
@pytest.mark.parametrize("filetype", ["rpi"])
def test_rpi_downloader(downloader_fixture, board_name, branch, filetype):
    downloader_fixture(board_name, branch, filetype)
    assert os.path.isfile("outs/kernel7l.img")
    assert os.path.isfile("outs/rpi-adxrs290.dtbo")
    # assert os.path.isfile("outs/properties.txt")
    assert os.path.isfile("outs/hashes.txt")


@pytest.mark.parametrize("board_name", ["rpi5-adis16480bmlz"])
@pytest.mark.parametrize("branch", ["v6.12.y-2026r1"])
@pytest.mark.parametrize("filetype", ["rpi"])
def test_rpi5_downloader(downloader_fixture, board_name, branch, filetype):
    downloader_fixture(board_name, branch, filetype)
    assert os.path.isfile("outs/kernel_2712.img")
    assert os.path.isfile("outs/adis16480.dtbo")
    assert os.path.isfile("outs/rpi_modules_64bit.tar.gz")
    # assert os.path.isfile("outs/properties.txt")
    # assert os.path.isfile("outs/hashes.txt")


@pytest.mark.parametrize("board_name", ["pluto"])
@pytest.mark.parametrize(
    "source, branch", [("github", "v0.33"), ("artifactory", "master")]
)
@pytest.mark.parametrize("filetype", ["firmware"])
def test_firmware_downloader(downloader_fixture, board_name, branch, filetype, source):
    downloader_fixture(board_name, branch, filetype, source=source)
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
        + "%2Ftest_boot_files%2Fmain%2FHDL_PRs%2Fpr_2104%2F2026_07_14-07_34_01"
    ],
)
def test_boot_downloader_new_flow(
    downloader_fixture, board_name, branch, filetype, url_template
):
    downloader_fixture(board_name, branch, filetype, url_template=url_template)
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
        "https://artifactory.analog.com/ui/repos/tree/Properties/sdg-generic-development%2Ftest_boot_files%2Fmain%2FHDL_PRs%2Fpr_2104%2F2026_07_14-07_34_01"
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


# =============================================================================
# Cloudsmith tests
# =============================================================================


@pytest.mark.parametrize(
    "board_name",
    [
        "zynq-zc706-adv7511-fmcomms11",
        "zynq-zc702-adv7511-ad9361-fmcomms2-3",
        "zynq-zed-adv7511-ad7768-1-evb",
        "zynqmp-zcu102-rev10-ad9172-fmc-ebz-mode4",
        "zynqmp-zcu102-rev10-ad9081",
        "zynqmp-zcu102-rev10-adrv9002",
        "zynqmp-zcu102-rev10-adrv9002-rx2tx2-vcmos",
        "zynqmp-zcu102-rev10-adrv9002-rx2tx2-vlvds",
        "socfpga_cyclone5_de10_nano_cn0540",
    ],
)
@pytest.mark.parametrize("branch", ["2026_r1"])
@pytest.mark.parametrize("filetype", ["boot_partition"])
def test_boot_downloader_cloudsmith(cloudsmith_fixture, board_name, branch, filetype):
    cloudsmith_fixture(board_name, branch, filetype)
    if board_name.startswith("zynqmp"):
        assert os.path.isfile("outs/Image")
        assert os.path.isfile("outs/system.dtb")
        assert os.path.isfile("outs/BOOT.BIN")
        assert os.path.isfile("outs/bootgen_sysfiles.tgz")
        assert os.path.isfile("outs/hashes.txt")
    elif board_name.startswith("zynq"):
        assert os.path.isfile("outs/uImage")
        assert os.path.isfile("outs/devicetree.dtb")
        assert os.path.isfile("outs/BOOT.BIN")
        assert os.path.isfile("outs/bootgen_sysfiles.tgz")
        assert os.path.isfile("outs/hashes.txt")
    elif board_name.startswith("socfpga_arria10"):
        assert os.path.isfile("outs/zImage")
        assert os.path.isfile("outs/extlinux.conf")
        assert os.path.isfile("outs/socfpga_arria10_socdk_sdmmc.dtb")
        assert os.path.isfile("outs/u-boot.img")
        assert os.path.isfile("outs/u-boot-splx4.sfp")
        assert os.path.isfile("outs/fit_spl_fpga.itb")
        assert os.path.isfile("outs/hashes.txt")
    elif board_name.startswith("socfpga_cyclone5"):
        assert os.path.isfile("outs/zImage")
        assert os.path.isfile("outs/extlinux.conf")
        assert os.path.isfile("outs/soc_system.rbf")
        assert os.path.isfile("outs/socfpga.dtb")
        assert os.path.isfile("outs/u-boot-with-spl.sfp")
        assert os.path.isfile("outs/u-boot.scr")
        assert os.path.isfile("outs/hashes.txt")


@pytest.mark.parametrize("board_name", ["eval-adxrs290-pmdz"])
@pytest.mark.parametrize("branch", ["rpi-6.12.y"])
@pytest.mark.parametrize("filetype", ["rpi"])
def test_rpi_downloader_cloudsmith(cloudsmith_fixture, board_name, branch, filetype):
    cloudsmith_fixture(board_name, branch, filetype)
    assert os.path.isfile("outs/rpi_latest_boot_32bit.tar.gz")
    assert os.path.isfile("outs/rpi_modules_32bit.tar.gz")
    assert os.path.isfile("outs/hashes.txt")


@pytest.mark.parametrize("board_name", ["rpi5-adis16480bmlz"])
@pytest.mark.parametrize("branch", ["rpi-6.12.y"])
@pytest.mark.parametrize("filetype", ["rpi"])
def test_rpi5_downloader_cloudsmith(cloudsmith_fixture, board_name, branch, filetype):
    cloudsmith_fixture(board_name, branch, filetype)
    assert os.path.isfile("outs/rpi_latest_boot_64bit.tar.gz")
    assert os.path.isfile("outs/rpi_modules_64bit.tar.gz")
    assert os.path.isfile("outs/hashes.txt")


@pytest.mark.parametrize("board_name", ["pluto"])
@pytest.mark.parametrize("branch", ["master"])
@pytest.mark.parametrize("filetype", ["firmware"])
def test_firmware_downloader_cloudsmith(
    cloudsmith_fixture, board_name, branch, filetype
):
    cloudsmith_fixture(board_name, branch, filetype, source="cloudsmith")
    file = [_ for _ in os.listdir("outs") if _.endswith(".zip")]
    assert len(file) == 1
    assert os.path.isfile("outs/hashes.txt")


if __name__ == "__main__":
    test_image_downloader()
