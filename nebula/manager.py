import sys
from nebula.netconsole import netconsole

from nebula.uart import uart
from nebula.pdu import pdu
from nebula.tftpboot import tftpboot

# import nebula
import fabric
import subprocess
import time
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
        self.dutip = "192.168.86.35"
        self.dutusername = "root"
        self.dutpassword = "analog"

        self.boot_src = tftpboot()

    def reboot_board(self):
        # Try to reboot board with SSH if possible
        try:
            result = fabric.Connection(
                self.dutusername + "@" + self.dutip,
                connect_kwargs={"password": self.dutpassword},
            ).run("reboot", hide=False)
            if result.ok:
                print("Rebooting board with SSH")
                time.sleep(120)
            else:
                # Use PDU
                raise Exception("PDU reset not implemented yet")

        except Exception as ex:
            print(ex)
            print("Exception occured during SSH Reboot")
            pass

    def ping_board(self):
        ping = subprocess.Popen(
            ["ping", "-c", "4", self.dutip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, error = ping.communicate()
        if "0 received" in str(out):
            return True
        return False

    def check_ssh(self):
        result = fabric.Connection(
            self.dutusername + "@" + self.dutip,
            connect_kwargs={"password": self.dutpassword},
        ).run("uname -a", hide=False)
        return result.failed

    def check_board_booted(self):
        if self.ping_board():
            raise Exception("Board not booted")
        else:
            print("PING PASSED")

        if self.check_ssh():
            raise Exception("SSH failing")
        else:
            print("SSH PASSED")
        pass

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
        self.reboot_board()
        # Check to make sure board booted
        try:
            self.check_board_booted()
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
