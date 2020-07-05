import os
import shutil

import pytest
from nebula import uart
from nebula import pdu
import time

# @pytest.mark.skip(reason="Not fully implemented")
@pytest.mark.dependency()
def test_adrv9361_fmc_get_to_uboot_menu():

    config = "/etc/default/nebula"
    config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
    power = pdu(yamlfilename=config)
    u = uart(yamlfilename=config)

    # Go go go
    power.power_cycle_board()
    assert u._enter_uboot_menu_from_power_cycle()


# @pytest.mark.skip(reason="Not fully implemented")
@pytest.mark.dependency(depends=["test_adrv9361_fmc_get_to_uboot_menu"])
def test_adrv9361_fmc_uboot_boot():
    # Get necessary boot files
    root = os.path.dirname(os.path.realpath(__file__))
    system_top_bit_filename = root + "/bootfiles/system_top.bit"
    devtree_filename = root + "/bootfiles/devicetree.dtb"
    kernel_filename = root + "/bootfiles/uImage"
    assert os.path.isfile(system_top_bit_filename)
    assert os.path.isfile(devtree_filename)
    assert os.path.isfile(kernel_filename)

    # Go go go
    config = "/etc/default/nebula"
    config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
    u = uart(yamlfilename=config)
    u.print_to_console = True
    u.load_system_uart(system_top_bit_filename, devtree_filename, kernel_filename)
    u.start_log()
    status = u._wait_for_boot_complete_linaro()
    u.stop_log()

    # Check board booted :)
    assert status


if __name__ == "__main__":
    test_adrv9361_fmc_uboot_boot()
