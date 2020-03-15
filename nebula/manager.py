import sys
from nebula.netconsole import netconsole

from nebula.uart import uart
from nebula.pdu import pdu
from nebula.tftpboot import tftpboot
from nebula.network import network

import yaml


class manager:
    """ Board Manager """

    def __init__(
        self, monitor="uart", configfilename=None,
    ):
        self.configfilename = configfilename

        self.power = pdu("192.168.86.1")

        if "netconsole" in monitor.lower():
            monitor_uboot = netconsole(port=45, logfilename="uboot.log")
            monitor_kernel = netconsole(port=67, logfilename="kernel.log")
            self.monitor = [monitor_uboot, monitor_kernel]
        elif "uart" in monitor.lower():
            # Check if config info exists in yaml
            stream = open(configfilename, "r")
            configs = yaml.safe_load(stream)
            stream.close()
            if "uart-config" not in configs:
                configfilename = None
            u = uart(yamlfilename=configfilename)
            self.monitor = [u]

        if "network-config" not in configs:
            configfilename = None
        self.net = network(yamlfilename=configfilename)

        self.boot_src = tftpboot()

    def get_status(self):
        pass

    def check_iio_context(self):
        pass

    def check_iio_devices(self):
        pass

    def load_boot_bin(self):
        pass

    def run_test(self):
        # Move BOOT.BIN, kernel and devtree to target location
        # self.boot_src.update_boot_files()
        # Start loggers
        for mon in self.monitor:
            mon.start_log()
        # Power cycle board
        self.net.reboot_board()
        # Check to make sure board booted
        try:
            self.net.check_board_booted()
        except:
            pass
        # Check IIO context and devices

        # Run tests

        # Stop and collect logs
        for mon in self.monitor:
            mon.stop_log()


if __name__ == "__main__":
    import pathlib

    p = pathlib.Path(__file__).parent.absolute()
    p = os.path.split(p)
    p = os.path.join(p[0], "resources", "nebula-zed.yaml")

    m = manager(configfilename=p)
    m.run_test()
