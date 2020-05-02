import os
import shutil

import pytest
from nebula import uart
from nebula import pdu
from nebula import network
import time

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


if __name__ == "__main__":
    test_adrv9361_fmc_uboot_boot()
