# from pyfiglet import Figlet
# f = Figlet(font="slant")
# print(f.renderText("Nebula"))

from nebula.netconsole import netconsole
from nebula.uart import uart
from nebula.tftpboot import tftpboot
from nebula.pdu import pdu
from nebula.manager import manager
from nebula.network import network
from nebula.driver import driver
from nebula.builder import builder
from nebula.common import utils
from nebula.helper import helper
from nebula.downloader import downloader
from nebula.coverage import coverage
from nebula.jtag import jtag
from nebula.usbdev import usbdev
from nebula.netbox import netbox

__version__ = "0.0.1"
name = "Nebula: Embedded Development Tools"
