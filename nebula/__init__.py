# from pyfiglet import Figlet
# f = Figlet(font="slant")
# print(f.renderText("Nebula"))
import platform

from nebula.builder import builder
from nebula.common import LINUX_DEFAULT_PATH, utils
from nebula.coverage import coverage
from nebula.downloader import downloader
from nebula.driver import driver
from nebula.helper import helper
from nebula.jtag import jtag
from nebula.manager import manager
from nebula.netbox import netbox
from nebula.netconsole import netconsole
from nebula.network import network
from nebula.pdu import pdu
from nebula.tftpboot import tftpboot
from nebula.uart import uart

if platform.system() == "Linux":
    from nebula.usbmux import usbmux

__version__ = "v1.0.0"
name = "Nebula: Embedded Development Tools"
