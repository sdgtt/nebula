import os
import shutil

import pytest
from nebula import uart
from nebula import pdu
import time
from fabric import Connection as con


@pytest.mark.dependency()
def test_cli_help():

    config = "/etc/default/nebula"
    config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"

    c = con("localhost")
    o = c.local("nebula --help")
    s = "Usage: nebula [--core-opts] <subcommand> [--subcommand-opts] ..."
    assert s in o.stdout


@pytest.mark.dependency()
def test_cli_get_ip():

    config = "/etc/default/nebula"
    config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
    assert os.path.isfile(config, "Configuration file not found")

    c = con("localhost")
    o = c.local("nebula uart.get-ip -y" + config)
    s = "192.168.86.35"
    assert s in o.stdout


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
