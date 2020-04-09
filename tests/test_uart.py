import os
import shutil

import pytest
from nebula import uart
import time

@pytest.mark.skip(reason="Not fully implemented"):
def test_adrv9361_fmc_uboot_boot():
    # Get necessary boot files
    system_top_bit_filename = 'system_top.bit'
    devtree_filename = 'devicetree.dtb'
    kernel_filename = 'uImage'
    assert os.path.isfile(system_top_bit_filename)
    assert os.path.isfile(devtree_filename)
    assert os.path.isfile(kernel_filename)

    # Go go go
    u = uart(yamlfilename="nebula-zynq-adrv9361-z7035-fmc.yaml")
    u.load_system_uart_usb(system_top_bit_filename, devtree_filename, kernel_filename)
    time.sleep(30)

    # Check board booted :)

if __name__ == "__main__":
    test_adrv9361_fmc_uboot_boot()
