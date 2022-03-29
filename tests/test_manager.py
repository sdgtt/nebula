import os
import shutil
import time

import pytest
from nebula import manager


# @pytest.mark.skip(reason="Not fully implemented")
# @pytest.mark.dependency()
def test_board_reboot_uart_net_pdu():
    # Get necessary boot files
    root = os.path.dirname(os.path.realpath(__file__))
    bootbinpath = root + "/bootfiles/BOOT.BIN"
    system_top_bit_filename = root + "/bootfiles/system_top.bit"
    devtree_filename = root + "/bootfiles/devicetree.dtb"
    kernel_filename = root + "/bootfiles/uImage"
    assert os.path.isfile(system_top_bit_filename)
    assert os.path.isfile(devtree_filename)
    assert os.path.isfile(kernel_filename)

    # config = "/etc/default/nebula"
    config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
    # Go go go
    m = manager(configfilename=config)
    m.board_reboot_uart_net_pdu(
        system_top_bit_path=system_top_bit_filename,
        bootbinpath=bootbinpath,
        uimagepath=kernel_filename,
        devtreepath=devtree_filename,
    )


if __name__ == "__main__":
    board_reboot_uart_net_pdu()
