import os
import shutil

import pytest

from nebula import downloader

# Must be connected to analog VPN


def downloader_test(board_name, branch, filetype, source="artifactory"):
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
    print(file)
    yamlfilename = os.path.join("nebula_config", "nebula.yaml")
    d = downloader(yamlfilename=yamlfilename, board_name=board_name)
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


@pytest.mark.parametrize("board_name", ["zynq-zc706-adv7511-fmcomms11"])
@pytest.mark.parametrize("branch", ["release", "master"])
@pytest.mark.parametrize("filetype", ["boot_partition", "not_boot_partition"])
def test_boot_downloader(test_downloader, board_name, branch, filetype):
    test_downloader(board_name, branch, filetype)
    assert os.path.isfile("outs/BOOT.BIN")
    assert os.path.isfile("outs/uImage")
    assert os.path.isfile("outs/bootgen_sysfiles.tgz")
    assert os.path.isfile("outs/devicetree.dtb")
    assert os.path.isfile("outs/properties.yaml")


@pytest.mark.parametrize("board_name", ["zynq-zc702-adv7511-ad9361-fmcomms2-3"])
@pytest.mark.parametrize("branch", ["release", "master"])
@pytest.mark.parametrize("filetype", ["noos"])
def test_noos_downloader(test_downloader, board_name, branch, filetype):
    test_downloader(board_name, branch, filetype)
    try:
        assert os.path.isfile("outs/system_top.hdf")
    except Exception:
        assert os.path.isfile("outs/system_top.xsa")
    assert os.path.isfile("outs/properties.yaml")


@pytest.mark.parametrize("board_name", ["kc705_fmcomms4"])
@pytest.mark.parametrize("branch", ["release", "master"])
@pytest.mark.parametrize("filetype", ["microblaze"])
def test_microblaze_downloader(test_downloader, board_name, branch, filetype):
    test_downloader(board_name, branch, filetype)
    try:
        assert os.path.isfile("outs/system_top.hdf")
    except Exception:
        assert os.path.isfile("outs/system_top.xsa")
    assert os.path.isfile("outs/simpleImage.kc705_fmcomms4.strip")
    assert os.path.isfile("outs/properties.yaml")


@pytest.mark.parametrize("board_name", ["eval-adxrs290-pmdz"])
@pytest.mark.parametrize("branch", ["rpi-5.10.y"])
@pytest.mark.parametrize("filetype", ["rpi"])
def test_rpi_downloader(test_downloader, board_name, branch, filetype):
    test_downloader(board_name, branch, filetype)
    assert os.path.isfile("outs/kernel7l.img")
    assert os.path.isfile("outs/rpi-adxrs290.dtbo")
    assert os.path.isfile("outs/properties.txt")


@pytest.mark.parametrize("board_name", ["pluto"])
@pytest.mark.parametrize(
    "source, branch", [("github", "v0.33"), ("artifactory", "master")]
)
@pytest.mark.parametrize("filetype", ["firmware"])
def test_firmware_downloader(test_downloader, board_name, branch, filetype, source):
    test_downloader(board_name, branch, filetype, source=source)
    if branch == "v0.33":
        assert os.path.isfile("outs/plutosdr-fw-v0.33.zip")
    else:
        assert len(os.listdir("outs")) == 1


@pytest.mark.skip(reason="filesize")
def test_image_downloader():
    d = downloader()
    d.download_sdcard_release()
    assert os.path.isfile("2019_R1-2020_02_04.img.xz")
    assert os.path.isfile("2019_R1-2020_02_04.img")


if __name__ == "__main__":
    test_image_downloader()
