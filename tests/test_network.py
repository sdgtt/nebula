import os
import shutil
import time

import pytest

from nebula import helper as helper
from nebula import network, pdu, uart


def remove_file(files):
    for file in files:
        if os.path.isfile(file):
            os.remove(file)
        if os.path.isfile(file):
            os.remove(file)


@pytest.fixture(autouse=True)
def run_around_tests():
    # Before test
    files = ["dmesg.log", "dmesg_error.log", "dmesg_warn.log"]
    remove_file(files)
    yield
    # After test
    remove_file(files)


# @pytest.mark.skip(reason="Not fully implemented")
# @pytest.mark.dependency(depends=["test_adrv9361_fmc_get_to_uboot_menu"])
def test_adrv9361_fmc_network_update():
    # Get necessary boot files
    root = os.path.dirname(os.path.realpath(__file__))
    bootbinpath = root + "/bootfiles/BOOT.BIN"
    devtree_filename = root + "/bootfiles/devicetree.dtb"
    kernel_filename = root + "/bootfiles/uImage"
    assert os.path.isfile(bootbinpath)
    assert os.path.isfile(devtree_filename)
    assert os.path.isfile(kernel_filename)

    # Go go go
    config = "/etc/default/nebula"
    config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
    n = network(yamlfilename=config)
    n.dutip = "192.168.86.35"
    n.update_boot_partition(bootbinpath, devtree_filename, kernel_filename)
    # n.update_boot_partition_existing_files(subfolder="zynq-adrv9361-z7035-fmc")
    time.sleep(60)
    n.check_board_booted()  # WILL RAISE ON ERROR

    # Check board booted :)


# @pytest.mark.dependency(depends=["test_adrv9361_fmc_get_to_uboot_menu"])
def test_adrv9361_fmc_network_update_existing_files():
    # Get necessary boot files
    root = os.path.dirname(os.path.realpath(__file__))
    bootbinpath = root + "/bootfiles/BOOT.BIN"
    devtree_filename = root + "/bootfiles/devicetree.dtb"
    kernel_filename = root + "/bootfiles/uImage"
    assert os.path.isfile(bootbinpath)
    assert os.path.isfile(devtree_filename)
    assert os.path.isfile(kernel_filename)

    # Go go go
    config = "/etc/default/nebula"
    config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
    n = network(yamlfilename=config)
    n.dutip = "192.168.86.35"
    n.update_boot_partition_existing_files(subfolder="zynq-adrv9361-z7035-fmc")
    time.sleep(60)
    n.check_board_booted()  # WILL RAISE ON ERROR

    # Check board booted :)


# @pytest.mark.dependency(depends=["test_adrv9361_fmc_get_to_uboot_menu"])
def test_dmesg_read():
    # Get necessary boot files

    # Go go go
    config = "/etc/default/nebula"
    # config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
    n = network(yamlfilename=config)
    n.dutip = "192.168.86.35"
    (e, log) = n.check_dmesg()

    assert os.path.isfile("dmesg.log")
    assert os.path.isfile("dmesg_warn.log")
    assert os.path.isfile("dmesg_err.log")


def test_update_boot_partition_existing_files():
    # generate nebula config for zynq-adrv9361-z7035-fmc
    outfile = "resources/nebula-zynq-adrv9361-z7035-fmc.yml"
    board_name = "zynq-adrv9361-z7035-fmc"
    h = helper()
    h.create_config_from_netbox(
        outfile=outfile,
        netbox_ip="192.168.10.11",
        netbox_port="8000",
        netbox_baseurl="netbox",
        netbox_token="0123456789abcdef0123456789abcdef01234567",
        board_name=board_name,
    )

    # initialize network object
    n = network(yamlfilename=outfile, board_name=board_name)
    n.check_board_booted()
    n.update_boot_partition_existing_files(subfolder=board_name)
    time.sleep(60)
    n.check_board_booted()


if __name__ == "__main__":
    test_adrv9361_fmc_network_update()
