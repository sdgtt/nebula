from invoke import Collection
from invoke import task
import nebula
import logging
import time

logging.getLogger().setLevel(logging.WARNING)

DEFAULT_NEBULA_CONFIG = "/etc/default/nebula"


def load_yaml(filename):
    stream = open(filename, "r")
    configs = yaml.safe_load(stream)
    stream.close()
    return configs


#############################################
@task()
def gen_config(c):
    """ Generate YAML configuration interactively """
    try:
        h = nebula.helper()
        h.create_config_interactive()
        del h
    except Exception as ex:
        print(ex)


#############################################
@task(
    help={
        "bootbinpath": "Path to BOOT.BIN.",
        "uimagepath": "Path to kernel image.",
        "devtreepath": "Path to devicetree.",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
    },
)
def update_boot_files_manager(
    c,
    system_top_bit_path="system_top.bit",
    bootbinpath="BOOT.BIN",
    uimagepath="uImage",
    devtreepath="devicetree.dtb",
    yamlfilename="/etc/default/nebula",
):
    """ Update boot files through u-boot menu (Assuming board is running) """
    m = nebula.manager(configfilename=yamlfilename)

    m.board_reboot_auto(
        system_top_bit_path=system_top_bit_path,
        bootbinpath=bootbinpath,
        uimagepath=uimagepath,
        devtreepath=devtreepath,
    )


manager = Collection("manager")
manager.add_task(update_boot_files_manager, name="update_boot_files")

#############################################
@task(
    help={
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist is will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
    },
)
def restart_board_uart(c, address="auto", yamlfilename="/etc/default/nebula"):
    """ Reboot DUT from UART connection assuming Linux is accessible"""
    try:
        u = nebula.uart(address=address, yamlfilename=yamlfilename)
        u.print_to_console = False
        cmd = "reboot"
        u.get_uart_command_for_linux(cmd, "")
        # if addr:
        #     if addr[-1] == "#":
        #         addr = addr[:-1]
        #     print(addr)
        # else:
        #     print("Address not found")
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist is will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
    },
)
def get_ip(c, address="auto", yamlfilename="/etc/default/nebula"):
    """ Get IP of DUT from UART connection """
    try:
        # YAML will override
        u = nebula.uart(address=address, yamlfilename=yamlfilename)
        u.print_to_console = False
        addr = u.get_ip_address()
        if addr:
            print(addr)
        else:
            print("Address not found")
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist is will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
    },
)
def set_local_nic_ip_from_usbdev(c, address="auto", yamlfilename="/etc/default/nebula"):
    """ Set IP of virtual NIC created from DUT based on found MAC """
    try:
        import os

        if not (os.name == "nt" or os.name == "posix"):
            raise Exception("This command only works on Linux currently")
        u = nebula.uart(address=address, yamlfilename=yamlfilename)
        u.print_to_console = False
        ipaddr = u.get_ip_address()
        if not ipaddr:
            print("Board IP is not set, must be set first")
            return
        # Get local mac from board
        addr = u.get_local_mac_usbdev()
        addr = addr.replace(":", "")
        addr = addr.replace("\r", "")
        addr = addr.strip()
        # Get IP of virtual nic
        cmd = (
            "ip -4 addr l enx"
            + addr
            + "| grep -v 127 | awk '$1 == \"inet\" {print $2}' | awk -F'/' '{print $1}'"
        )
        out = c.run(cmd)
        local = out.stdout
        local = local.replace("\r", "").replace("\n", "").strip()
        # Compare against local
        ipaddrs = ipaddr.split(".")
        if local:
            remotesub = ".".join(ipaddrs[:-1])
            locals = local.split(".")
            localsub = ".".join(locals[:-1])
            do_not_set = remotesub == localsub
            if do_not_set:
                ipaddrs = local

        if not do_not_set:
            # Create new address
            ipaddrs[-1] = str(int(ipaddrs[-1]) + 9)
            ipaddrs = ".".join(ipaddrs)
            cmd = "ifconfig enx" + addr + " " + ipaddrs
            c.run(cmd)

        print("Local IP Set:", ipaddrs, "Remote:", ipaddr)
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist is will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
    },
)
def get_carriername(c, address="auto", yamlfilename="/etc/default/nebula"):
    """ Get Carrier (FPGA) name of DUT from UART connection """
    try:
        u = nebula.uart(address=address, yamlfilename=yamlfilename)
        u.print_to_console = False
        cmd = "cat /sys/firmware/devicetree/base/model"
        addr = u.get_uart_command_for_linux(cmd, "")
        if addr:
            if addr[-1] == "#":
                addr = addr[:-1]
            addr = addr.split("\x00")
            if "@" in addr[-1]:
                addr = addr[:-1]
            addr = "-".join(addr)
            print(addr)
        else:
            print("Address not found")
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist is will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
    },
)
def get_mezzanine(c, address="auto", yamlfilename="/etc/default/nebula"):
    """ Get Mezzanine (FMC) name of DUT from UART connection """
    try:
        u = nebula.uart(address=address, yamlfilename=yamlfilename)
        u.print_to_console = False
        cmd = "find /sys/ -name eeprom | xargs fru-dump -b -i | grep Part Number"
        addr = u.get_uart_command_for_linux(cmd, "")
        if addr:
            if addr[-1] == "#":
                addr = addr[:-1]
            print(addr)
        else:
            print("Address not found")
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "nic": "Network interface name to set. Default is eth0",
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist is will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
    },
)
def set_dhcp(c, address="auto", nic="eth0", yamlfilename="/etc/default/nebula"):
    """ Set board to use DHCP for networking from UART connection """
    try:
        u = nebula.uart(address=address, yamlfilename=yamlfilename)
        u.print_to_console = False
        u.request_ip_dhcp()
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "ip": "IP Address to set NIC to",
        "nic": "Network interface name to set. Default is eth0",
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist is will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
    },
)
def set_static_ip(
    c, ip, address="auto", nic="eth0", yamlfilename="/etc/default/nebula"
):
    """ Set Static IP address of board of DUT from UART connection """
    try:
        u = nebula.uart(address=address, yamlfilename=yamlfilename)
        u.print_to_console = False
        u.set_ip_static(ip, nic)
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "system_top_bit_filename": "Path to system_top.bit.",
        "uimagepath": "Path to kernel image.",
        "devtreepath": "Path to devicetree.",
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist is will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "reboot": "Reboot board from linux console to get to u-boot menu. Defaut False",
    }
)
def update_boot_files_uart(
    c,
    system_top_bit_filename,
    uimagepath,
    devtreepath,
    address=None,
    yamlfilename="/etc/default/nebula",
    reboot=False,
):
    """ Update boot files through u-boot menu (Assuming board is running) """
    u = nebula.uart(address=address, yamlfilename=yamlfilename)
    u.print_to_console = False
    if reboot:
        u._write_data("reboot")
        time.sleep(4)
    u.update_boot_files_from_running(
        system_top_bit_filename=system_top_bit_filename,
        kernel_filename=uimagepath,
        devtree_filename=devtreepath,
    )


uart = Collection("uart")
uart.add_task(restart_board_uart, name="restart_board")
uart.add_task(get_ip)
uart.add_task(set_dhcp)
uart.add_task(set_static_ip)
uart.add_task(get_carriername)
uart.add_task(get_mezzanine)
uart.add_task(update_boot_files_uart, name="update_boot_files")
uart.add_task(set_local_nic_ip_from_usbdev)

#############################################
@task(
    help={
        "ip": "IP address of board",
        "user": "Board username. Default: root",
        "password": "Password for board. Default: analog",
    }
)
def restart_board(c, ip, user="root", password="analog"):
    """ Reboot development system over IP """
    n = nebula.network(dutip=ip, dutusername=user, dutpassword=password)
    n.reboot_board(bypass_sleep=True)


@task(
    help={
        "ip": "IP address of board. Default from yaml",
        "user": "Board username. Default: root",
        "password": "Password for board. Default: analog",
        "bootbinpath": "Path to BOOT.BIN. Optional",
        "uimagepath": "Path to kernel image. Optional",
        "devtreepath": "Path to devicetree. Optional",
    }
)
def update_boot_files(
    c,
    ip=None,
    user="root",
    password="analog",
    bootbinpath=None,
    uimagepath=None,
    devtreepath=None,
):
    """ Update boot files on SD Card over SSH """
    n = nebula.network(dutip=ip, dutusername=user, dutpassword=password)
    n.update_boot_partition(
        bootbinpath=bootbinpath, uimagepath=uimagepath, devtreepath=devtreepath
    )


net = Collection("net")
net.add_task(restart_board)
net.add_task(update_boot_files)

#############################################
@task
def show_log(c):
    """ Show log for all following tasks """
    logging.getLogger().setLevel(logging.DEBUG)


ns = Collection()
ns.add_task(gen_config)
ns.add_task(show_log)
ns.add_collection(uart)
ns.add_collection(net)
ns.add_collection(manager)
