# from pyfiglet import Figlet
# f = Figlet(font="slant")
# print(f.renderText("Nebula"))
import os

from nebula.builder.interface import BuilderInterface as builder
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

if os.name in ["nt", "posix"] and os.path.exists(LINUX_DEFAULT_PATH):
    from nebula.usbmux import usbmux

__version__ = "0.0.1"
name = "Nebula: Embedded Development Tools"
