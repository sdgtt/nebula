import os
import shutil

import pytest

from nebula import builder


@pytest.fixture(autouse=True)
def run_around_tests():
    # Before test
    if os.path.isdir("libiio"):
        shutil.rmtree("libiio")
    if os.path.isdir("hdl"):
        shutil.rmtree("hdl")
    if os.path.isdir("u-boot-xlnx"):
        shutil.rmtree("u-boot-xlnx")
    if os.path.isdir("uboot"):
        shutil.rmtree("uboot")
    if os.path.isdir("linux"):
        shutil.rmtree("linux")
    yield
    # After test
    if os.path.isdir("libiio"):
        shutil.rmtree("libiio")
    # if os.path.isdir("hdl"):
    #     shutil.rmtree("hdl")
    if os.path.isdir("u-boot-xlnx"):
        shutil.rmtree("u-boot-xlnx")
    if os.path.isdir("uboot"):
        shutil.rmtree("uboot")
    if os.path.isdir("linux"):
        shutil.rmtree("linux")


# def test_libiio_build():
#     b = builder()
#     b.analog_clone_build("libiio")
#     assert os.path.isfile("libiio/build/libiio.so")


def test_hdl_build():
    b = builder("2021_R1", "zed", "fmcomms2")
    b.analog_clone_build("hdl")
    filename = "hdl/projects/fmcomms2/zed/fmcomms2_zed.sdk/system_top.hdf"
    filename_new = "hdl/projects/fmcomms2/zed/fmcomms2_zed.sdk/system_top.xsa"
    assert os.path.isfile(filename) or os.path.isfile(filename_new)


def test_uboot_build_zed_individual():
    b = builder("2021_R1", "zed", "fmcomms2")
    repo = "uboot"
    folder = b.analog_clone(repo)
    artifact = b.analog_build(repo, folder)
    assert os.path.isfile(f"{repo}/u-boot")
    assert artifact == f"{repo}/u-boot"


def test_uboot_build_zed():
    b = builder("2021_R1", "zed", "fmcomms2")
    repo = "uboot"
    folder = b.analog_clone(repo)
    artifact = b.analog_build(repo, folder)
    assert os.path.isfile(f"{repo}/u-boot")
    assert artifact == f"{repo}/u-boot"


def test_uboot_build_zcu102_individual():
    b = builder("2021_R1", "zcu102", "fmcomms2")
    repo = "uboot"
    folder = b.analog_clone(repo)
    artifact = b.analog_build(repo, folder)
    assert os.path.isfile(f"{repo}/u-boot")
    assert artifact == f"{repo}/u-boot"


def test_uboot_build_zcu102():
    b = builder("2021_R1", "zcu102", "fmcomms2")
    repo = "uboot"
    artifact = b.analog_clone_build(repo)
    assert os.path.isfile(f"{repo}/u-boot")
    assert artifact == f"{repo}/u-boot"


def test_linux_build_zed_individual():
    b = builder("2021_R1", "zed", "fmcomms2")
    repo = "linux"
    folder = b.analog_clone(repo)
    artifact = b.analog_build(repo, folder)
    path = "linux/arch/arm/boot/uImage"
    assert os.path.isfile(path)
    assert artifact == path


def test_linux_build_zed():
    b = builder("2021_R1", "zed", "fmcomms2")
    artifact = b.analog_clone_build("linux")
    path = "linux/arch/arm/boot/uImage"
    assert os.path.isfile(path)
    assert artifact == path


def test_linux_build_zcu102_individual():
    b = builder("2021_R1", "zcu102", "fmcomms2")
    repo = "linux"
    folder = b.analog_clone(repo)
    artifact = b.analog_build(repo, folder)
    path = "linux/arch/arm64/boot/Image"
    assert os.path.isfile(path)
    assert artifact == path


def test_linux_build_zcu102():
    b = builder("2021_R1", "zcu102", "fmcomms2")
    artifact = b.analog_clone_build("linux")
    path = "linux/arch/arm64/boot/Image"
    assert os.path.isfile(path)
    assert artifact == path


def test_bootbin_build():
    b = builder("2021_R1", "zed", "fmcomms2")
    b.analog_clone_and_build_bootbin()
    path = "bootbin_output/BOOT.BIN"
    assert os.path.isfile(path)


# def test_bootbin_build_arm64():
#     b = builder()
#     b.analog_build_bootbin(
#         hdl_branch="master",
#         uboot_branch="xilinx-v2019.1",
#         board="zcu102",
#         project="adrv9009",
#     )
#     path = "BOOTBIN/BOOT.BIN"
#     assert os.path.isfile(path)


if __name__ == "__main__":
    pass
    # test_uboot_build()
