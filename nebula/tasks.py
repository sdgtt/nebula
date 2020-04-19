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
@task(
    help={
        "address": "UART device address (/dev/ttyACMO). Overrides yaml",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
    },
)
def get_ip(c, address=None, yamlfilename="/etc/default/nebula"):
    """ Get IP of DUT from UART connection """
    u = nebula.uart(address=address, yamlfilename=yamlfilename)
    u.print_to_console = False
    addr = u.get_ip_address()
    if addr:
        print(addr)
    else:
        print("Address not found")
    del u


@task(
    help={
        "bootbinpath": "Path to BOOT.BIN.",
        "uimagepath": "Path to kernel image.",
        "devtreepath": "Path to devicetree.",
        "address": "UART device address (/dev/ttyACMO). Overrides yaml",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "reboot": "Reboot board from linux console to get to u-boot menu. Defaut False",
    }
)
def update_boot_files_uart(
    c,
    bootbinpath,
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
        bootbinpath=bootbinpath, uimagepath=uimagepath, devtreepath=devtreepath
    )


uart = Collection("uart")
uart.add_task(get_ip)
uart.add_task(update_boot_files_uart, name="update_boot_files")

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
        "ip": "IP address of board",
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
    if ip == None:
        config = load_yaml(DEFAULT_NEBULA_CONFIG)
        ip = config["network-config"]["dutip"]

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
ns.add_task(show_log)
ns.add_collection(uart)
ns.add_collection(net)
