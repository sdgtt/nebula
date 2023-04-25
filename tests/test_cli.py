# from msilib.schema import Billboard
import os
import shutil
import subprocess
import time

import pytest
from fabric import Connection as con
from nebula import pdu, uart

# must include -s


@pytest.fixture(autouse=True)
def test_downloader():
    if os.path.isdir("outs"):
        shutil.rmtree("outs")
    yield
    if os.path.isdir("outs"):
        shutil.rmtree("outs")


@pytest.mark.dependency()
def test_cli_help():
    c = con("localhost")
    o = c.local("nebula --help")
    s = "Usage: nebula [--core-opts] <subcommand> [--subcommand-opts] ..."
    assert s in o.stdout


def test_update_config():
    config = os.path.join("nebula_config", "nebula.yaml")
    board = "zynq-zc702-adv7511-ad9361-fmcomms2-3"
    c = con("localhost")
    o = c.local(
        "nebula update-config board-config no-os-project --yamlfilename="
        + config
        + " --board-name="
        + board
    )
    s = "ad9361"
    assert s in o.stdout


def test_dl_bootfiles():
    config = os.path.join("nebula_config", "nebula.yaml")
    board = "zynq-zc702-adv7511-ad9361-fmcomms2-3"
    branch = "release"
    file = "noos"
    source_root = "artifactory.analog.com"
    source = "artifactory"
    c = con("localhost")
    cmd = (
        "nebula dl.bootfiles --board-name="
        + board
        + " --source-root="
        + source_root
        + " --source="
        + source
        + " --yamlfilename="
        + config
        + " --branch="
        + branch
        + " --filetype="
        + file
    )
    c.local(cmd)
    try:
        assert os.path.isfile("outs/system_top.hdf")
    except Exception:
        assert os.path.isfile("outs/system_top.xsa")


def test_show_log():
    config = os.path.join("nebula_config", "nebula.yaml")
    board = "zynq-zc702-adv7511-ad9361-fmcomms2-3"
    c = con("localhost")
    o = c.local(
        "nebula show-log update-config board-config no-os-project --yamlfilename="
        + config
        + " --board-name="
        + board
    )
    s = "INFO"
    assert s in o.stderr


@pytest.mark.hardware
@pytest.mark.parametrize("board", ["eval-cn0508-rpiz"])
@pytest.mark.parametrize(
    "config",
    [os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-rpi.yaml")],
)
def test_usbmux_backup_update_bootfiles(config, board):
    test_dir = os.path.dirname(__file__)
    test_bk_dir = os.path.join(test_dir, "test-backup")

    c = con("localhost")
    o = c.local(
        "nebula show-log usbsdmux.backup-bootfiles"
        + f" --backup-loc {test_bk_dir}"
        + " --backup-subfolder random"
        + " --target-file config.txt"
        + " --target-file bcm2710-rpi-3-b-plus.dtb"
        + " --target-file overlays/rpi-cn0508.dtbo"
        + " --target-file kernel7.img"
        + " --yamlfilename="
        + config
        + " --board-name="
        + board
    )

    assert o.return_code == 0
    assert os.path.isfile(os.path.join(test_bk_dir, "random", "config.txt"))
    assert os.path.isfile(
        os.path.join(test_bk_dir, "random", "bcm2710-rpi-3-b-plus.dtb")
    )
    assert os.path.isfile(os.path.join(test_bk_dir, "random", "rpi-cn0508.dtbo"))
    assert os.path.isfile(os.path.join(test_bk_dir, "random", "kernel7.img"))

    o = c.local(
        "nebula show-log usbsdmux.update-bootfiles"
        + " --devicetree-overlay-config "
        + os.path.join(test_bk_dir, "random", "config.txt")
        + " --devicetree-filename "
        + os.path.join(test_bk_dir, "random", "bcm2710-rpi-3-b-plus.dtb")
        + " --devicetree-overlay-filename "
        + os.path.join(test_bk_dir, "random", "rpi-cn0508.dtbo")
        + " --kernel-filename "
        + os.path.join(test_bk_dir, "random", "kernel7.img")
        + " --no-update-dt"
        + " --mux-mode dut"
        + " --yamlfilename="
        + config
        + " --board-name="
        + board
    )
    assert o.return_code == 0


@pytest.mark.hardware
@pytest.mark.parametrize("board", ["eval-cn0508-rpiz"])
@pytest.mark.parametrize(
    "config",
    [os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-rpi.yaml")],
)
def test_usbmux_backup_update_modules(config, board):
    test_dir = os.path.dirname(__file__)
    test_bk_dir = os.path.join(test_dir, "test-backup")
    modules_path = os.path.join("lib", "modules", "5.10.63-v7+")

    c = con("localhost")
    o = c.local(
        "nebula show-log usbsdmux.backup-bootfiles"
        + " --partition root"
        + f" --backup-loc {test_bk_dir}"
        + " --backup-subfolder random"
        + f" --target-file {modules_path}"
        + " --yamlfilename="
        + config
        + " --board-name="
        + board
    )
    assert o.return_code == 0
    assert os.path.isdir(os.path.join(test_bk_dir, "random", "5.10.63-v7+"))
    o = c.local(
        "nebula show-log usbsdmux.update-modules"
        + " --module-loc "
        + os.path.join(test_bk_dir, "random", "5.10.63-v7+")
        + " --mux-mode off"
        + " --yamlfilename="
        + config
        + " --board-name="
        + board
    )
    assert o.return_code == 0


# @pytest.mark.hardware
# @pytest.mark.parametrize("board", ["eval-cn0508-rpiz"])
# @pytest.mark.parametrize("config",[os.path.join(os.path.dirname(__file__),"nebula_config", "nebula-rpi.yaml")])
# def test_usbmux_update_modules():
#     assert os.path.isdir(os.path.join("outs", "5.10.63-v7+"))
#     c = con("localhost")
#     o = c.local(
#         "nebula show-log usbsdmux.update-modules"
#         + " --module-loc outs/5.10.63-v7+"
#         + " --mux-mode off"
#         + " --yamlfilename=" + config
#         + " --board-name=" + board
#     )
#     assert o.return_code == 0

# need to update nebulaconfig to whatever is deployed
# @pytest.mark.dependency()
# def test_cli_get_ip():

#     config = "/etc/default/nebula"
#     config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
#     assert os.path.isfile(config), "Configuration file not found"

#     c = con("localhost")
#     o = c.local("nebula uart.get-ip -y" + config)
#     s = "192.168.86.35"
#     assert s in o.stdout


#
# # @pytest.mark.skip(reason="Not fully implemented")
# @pytest.mark.dependency(depends=["test_adrv9361_fmc_get_to_uboot_menu"])
# def test_adrv9361_fmc_uboot_boot():
#     # Get necessary boot files
#     root = os.path.dirname(os.path.realpath(__file__))
#     system_top_bit_filename = root + "/bootfiles/system_top.bit"
#     devtree_filename = root + "/bootfiles/devicetree.dtb"
#     kernel_filename = root + "/bootfiles/uImage"
#     assert os.path.isfile(system_top_bit_filename)
#     assert os.path.isfile(devtree_filename)
#     assert os.path.isfile(kernel_filename)
#
#     # Go go go
#     config = "/etc/default/nebula"
#     config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
#     u = uart(yamlfilename=config)
#     u.print_to_console = True
#     u.load_system_uart(system_top_bit_filename, devtree_filename, kernel_filename)
#     u.start_log()
#     time.sleep(30)
#     u.stop_log()
#
#     # Check board booted :)
#
#
# if __name__ == "__main__":
#     test_adrv9361_fmc_uboot_boot()
