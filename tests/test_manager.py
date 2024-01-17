import os
import shutil
import time

import pytest
from nebula import helper, manager


# @pytest.mark.skip(reason="Not fully implemented")
# @pytest.mark.dependency()
@pytest.mark.hardware
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


@pytest.mark.hardware
@pytest.mark.parametrize(
    "param",
    [
        {
            "board": "zynq-zc706-adv7511-ad9361-fmcomms5",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-usbmux.yml"),
        },
        {
            "board": "zynqmp-adrv9009-zu11eg-revb-adrv2crr-fmc-revb",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-usbmux.yml"),     
        },
        {
            "board": "zynqmp-zcu102-rev10-adrv9002-vcmos",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-usbmux.yml"),
        },
        {
            "board": "socfpga_cyclone5_de10_nano_cn0540",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-usbmux.yml"),
        }
    ],
)
def test_board_reboot_sdmux_pdu(power_off_dut, sdmux_dutmode, power_on_dut,  param):

    # Get necessary boot files
    board = param["board"]
    config = param["config"]

    files = {
        "bootbinpath": "BOOT.BIN",
        "uimagepath": "uImage",
        "devtreepath": "devicetree.dtb",
    }
    if "files" in param.keys():
        files = param["files"]
    else:
        if "zynqmp" in board:
            files = {
                "bootbinpath": "BOOT.BIN",
                "uimagepath": "Image",
                "devtreepath": "system.dtb",
            }
        elif "socfpga_cyclone5" in board:
            files = {
                "bootbinpath": "soc_system.rbf",
                "uimagepath" : "zImage",
                "devtreepath": "socfpga.dtb",
                "extlinux_path": "extlinux.conf",
                "scr_path": "u-boot.scr",
                "preloader_path": "u-boot-with-spl.sfp"
            }

    boot_files = {
        "system_top_bit_path": None,
        "bootbinpath": None,
        "uimagepath": None,
        "devtreepath" : None,
        "devtree_overlay_path" : None,
        "devtree_overlay_config_path" : None,
        "extlinux_path": None,
        "scr_path": None,
        "preloader_path": None
    }

    root = os.path.dirname(os.path.realpath(__file__))

    for boot_file_path in boot_files.keys():
        if boot_file_path in files.keys():
            boot_files[boot_file_path] = f"{root}/bootfiles/{board}/" + files[boot_file_path]
            assert os.path.isfile(boot_files[boot_file_path])

    m = manager(configfilename=config, board_name=board)
    m.net.check_board_booted()

    m.board_reboot_sdmux_pdu(**boot_files)


@pytest.mark.hardware
@pytest.mark.parametrize(
    "param",
    [
        {
            "board": "zynq-zc706-adv7511-ad9361-fmcomms5",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-usbmux.yml")
        },
        {
            "board": "zynqmp-adrv9009-zu11eg-revb-adrv2crr-fmc-revb",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-usbmux.yml")
        },
        {
            "board": "zynqmp-zcu102-rev10-adrv9002-vcmos",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-usbmux.yml")
        }
    ],
)
def test_recover_board_functional(power_on_dut, param):

    board = param["board"]
    config = param["config"]

    # Get necessary boot files
    root = os.path.dirname(os.path.realpath(__file__))
    system_top_bit = "system_top.bit"
    bootbin = "BOOT.BIN"
    uimage = "uImage"
    devtree = "devicetree.dtb"
    fsbl = "fsbl.elf"
    uboot = "u-boot_zynq.elf"

    if "zc706" in board:
        uboot = "u-boot_zynq_zc706.elf"
    elif "zu11eg" in board:
        uboot = "u-boot_adi_zynqmp_adrv9009_zu11eg_adrv2crr_fmc.elf"
    elif "zcu102" in board:
        uboot = "u-boot_xilinx_zynqmp_zcu102_revA.elf"

    if "zynqmp" in board:
        uimage = "Image"
        devtree = "system.dtb"

    system_top_bit_path = f"{root}/bootfiles/{board}/" + system_top_bit
    bootbinpath = f"{root}/bootfiles/{board}/" + bootbin
    uimagepath = f"{root}/bootfiles/{board}/" + uimage
    devtreepath = f"{root}/bootfiles/{board}/" + devtree
    fsblpath = f"{root}/bootfiles/{board}/" + fsbl
    ubootpath = f"{root}/bootfiles/{board}/" + uboot

    assert os.path.isfile(system_top_bit_path)
    assert os.path.isfile(bootbinpath)
    assert os.path.isfile(uimagepath)
    assert os.path.isfile(devtreepath)
    assert os.path.isfile(fsblpath)
    assert os.path.isfile(ubootpath)

    m = manager(configfilename=config, board_name=board)
    m.net.check_board_booted()

    # recover via usb-sd-mux
    m.recover_board(
        system_top_bit_path, bootbinpath, uimagepath, devtreepath, fsblpath, ubootpath
    )


@pytest.mark.hardware
@pytest.mark.parametrize(
    "param",
    [
        {
            "board": "zynq-zc706-adv7511-ad9361-fmcomms5",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-usbmux.yml")
        },
        {
            "board": "zynqmp-adrv9009-zu11eg-revb-adrv2crr-fmc-revb",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-usbmux.yml")
        },
        {
            "board": "zynqmp-zcu102-rev10-adrv9002-vcmos",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-usbmux.yml")
        }
    ],
)
def test_recover_board_usbsdmux(power_on_dut, param):

    board = param["board"]
    config = param["config"]

    # Get necessary boot files
    root = os.path.dirname(os.path.realpath(__file__))
    system_top_bit = "system_top.bit"
    bootbin = "BOOT.BIN"
    uimage = "uImage"
    devtree = "devicetree.dtb"
    fsbl = "fsbl.elf"
    uboot = "u-boot_zynq.elf"

    if "zc706" in board:
        uboot = "u-boot_zynq_zc706.elf"
    elif "zu11eg" in board:
        uboot = "u-boot_adi_zynqmp_adrv9009_zu11eg_adrv2crr_fmc.elf"
    elif "zcu102" in board:
        uboot = "u-boot_xilinx_zynqmp_zcu102_revA.elf"

    if "zynqmp" in board:
        uimage = "Image"
        devtree = "system.dtb"

    system_top_bit_path = f"{root}/bootfiles/{board}/" + system_top_bit
    bootbinpath = f"{root}/bootfiles/{board}/" + bootbin
    uimagepath = f"{root}/bootfiles/{board}/" + uimage
    devtreepath = f"{root}/bootfiles/{board}/" + devtree
    fsblpath = f"{root}/bootfiles/{board}/" + fsbl
    ubootpath = f"{root}/bootfiles/{board}/" + uboot

    assert os.path.isfile(system_top_bit_path)
    assert os.path.isfile(bootbinpath)
    assert os.path.isfile(uimagepath)
    assert os.path.isfile(devtreepath)
    assert os.path.isfile(fsblpath)
    assert os.path.isfile(ubootpath)

    m = manager(configfilename=config, board_name=board)
    m.net.check_board_booted()

    # purposely fail dut
    m.net.run_ssh_command(f"rm /boot/{uimage}")
    m.power.power_cycle_board()

    # recover via usb-sd-mux
    m.recover_board(
        system_top_bit_path, bootbinpath, uimagepath, devtreepath, fsblpath, ubootpath
    )


@pytest.mark.hardware
@pytest.mark.parametrize(
    "param",
    [
        {
            "board": "zynq-zc706-adv7511-ad9361-fmcomms5",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager.yml")
        },
        {
            "board": "zynqmp-adrv9009-zu11eg-revb-adrv2crr-fmc-revb",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager.yml")
        },
        {
            "board": "zynqmp-zcu102-rev10-adrv9002-vcmos",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager.yml")
        }
    ],
)
def test_recover_board_uart(power_on_dut, param):

    board = param["board"]
    config = param["config"]

    # Get necessary boot files
    root = os.path.dirname(os.path.realpath(__file__))
    system_top_bit = "system_top.bit"
    bootbin = "BOOT.BIN"
    uimage = "uImage"
    devtree = "devicetree.dtb"
    fsbl = "fsbl.elf"
    uboot = "u-boot_zynq.elf"

    if "zc706" in board:
        uboot = "u-boot_zynq_zc706.elf"
    elif "zu11eg" in board:
        uboot = "u-boot_adi_zynqmp_adrv9009_zu11eg_adrv2crr_fmc.elf"
    elif "zcu102" in board:
        uboot = "u-boot_xilinx_zynqmp_zcu102_revA.elf"

    if "zynqmp" in board:
        uimage = "Image"
        devtree = "system.dtb"

    system_top_bit_path = f"{root}/bootfiles/{board}/" + system_top_bit
    bootbinpath = f"{root}/bootfiles/{board}/" + bootbin
    uimagepath = f"{root}/bootfiles/{board}/" + uimage
    devtreepath = f"{root}/bootfiles/{board}/" + devtree
    fsblpath = f"{root}/bootfiles/{board}/" + fsbl
    ubootpath = f"{root}/bootfiles/{board}/" + uboot

    assert os.path.isfile(system_top_bit_path)
    assert os.path.isfile(bootbinpath)
    assert os.path.isfile(uimagepath)
    assert os.path.isfile(devtreepath)
    assert os.path.isfile(fsblpath)
    assert os.path.isfile(ubootpath)

    m = manager(configfilename=config, board_name=board)
    m.net.check_board_booted()

    # purposely fail dut
    m.net.run_ssh_command(f"rm /boot/{uimage}")
    m.net.run_ssh_command(f"rm /boot/{devtree}")
    m.power.power_cycle_board()

    # recover via uart
    m.recover_board(
        system_top_bit_path,
        bootbinpath,
        uimagepath,
        devtreepath,
        fsblpath,
        ubootpath,
    )


# @pytest.mark.skip(reason="Not fully implemented")
@pytest.mark.hardware
@pytest.mark.parametrize(
    "param",
    [
        {
            "board": "zynq-zc706-adv7511-ad9361-fmcomms5",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-jtag.yml")
        },
        {
            "board": "zynqmp-adrv9009-zu11eg-revb-adrv2crr-fmc-revb",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-jtag.yml")
        },
        {
            "board": "zynqmp-zcu102-rev10-adrv9002-vcmos",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-jtag.yml")
        }
    ],
)
def test_recover_board_jtag(power_on_dut, param):

    board = param["board"]
    config = param["config"]

    # Get necessary boot files
    root = os.path.dirname(os.path.realpath(__file__))
    system_top_bit = "system_top.bit"
    bootbin = "BOOT.BIN"
    uimage = "uImage"
    devtree = "devicetree.dtb"
    fsbl = "fsbl.elf"
    uboot = "u-boot_zynq.elf"

    if "zc706" in board:
        uboot = "u-boot_zynq_zc706.elf"
    elif "zu11eg" in board:
        uboot = "u-boot_adi_zynqmp_adrv9009_zu11eg_adrv2crr_fmc.elf"
    elif "zcu102" in board:
        uboot = "u-boot_xilinx_zynqmp_zcu102_revA.elf"

    if "zynqmp" in board:
        uimage = "Image"
        devtree = "system.dtb"

    system_top_bit_path = f"{root}/bootfiles/{board}/" + system_top_bit
    bootbinpath = f"{root}/bootfiles/{board}/" + bootbin
    uimagepath = f"{root}/bootfiles/{board}/" + uimage
    devtreepath = f"{root}/bootfiles/{board}/" + devtree
    fsblpath = f"{root}/bootfiles/{board}/" + fsbl
    ubootpath = f"{root}/bootfiles/{board}/" + uboot

    assert os.path.isfile(system_top_bit_path)
    assert os.path.isfile(bootbinpath)
    assert os.path.isfile(uimagepath)
    assert os.path.isfile(devtreepath)
    assert os.path.isfile(fsblpath)
    assert os.path.isfile(ubootpath)
    m = manager(configfilename=config, board_name=board)
    m.net.check_board_booted()

    # purposely fail dut
    # purposely fail dut
    m.net.run_ssh_command(f"rm /boot/{uimage}")
    m.net.run_ssh_command(f"rm /boot/{devtree}")
    m.net.run_ssh_command(f"rm /boot/{bootbin}")
    m.power.power_cycle_board()

    # recover via uart
    m.recover_board(
        system_top_bit_path,
        bootbinpath,
        uimagepath,
        devtreepath,
        fsblpath,
        ubootpath,
    )

if __name__ == "__main__":
    test_board_reboot_uart_net_pdu()
