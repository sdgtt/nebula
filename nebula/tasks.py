from invoke import Collection
from invoke import task
import nebula
import logging


logging.getLogger().setLevel(logging.WARNING)


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


uart = Collection("uart")
uart.add_task(get_ip)

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


net = Collection("net")
net.add_task(restart_board)

#############################################
@task
def show_log(c):
    """ Show log for all following tasks """
    logging.getLogger().setLevel(logging.DEBUG)


ns = Collection()
ns.add_task(show_log)
ns.add_collection(uart)
ns.add_collection(net)
