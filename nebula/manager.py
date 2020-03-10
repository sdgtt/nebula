import sys
from nebula import netconsole
import fabric
import subprocess
import time


class manager:
    """ Board Manager """

    def __init__(self):
        # self.db_file_location = "/tmp"
        # Check if board in DB if not add config
        # config = yml.read()
        # if config in self.db():
        #     pass

        self.monitor_uboot = netconsole.netconsole(port=45, logfilename="uboot.log")
        self.monitor_kernel = netconsole.netconsole(port=67, logfilename="kernel.log")
        self.power = pdu("192.168.86.1")
        self.dutip = "10.1.1.100"
        self.dutusername = "root"
        self.dutpassword = "analog"

        self.boot_src = tftpboot.tftpboot()

    def reboot_board(self):
        # Try to reboot board with SSH if possible
        try:
            result = fabric.Connection(
                self.dutusername + "@" + self.dutip,
                connect_kwargs={"password": self.dutpassword},
            ).run("reboot", hide=False)
            if result.ok:
                print("Rebooting board with SSH")
                time.sleep(30)
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

        if self.check_ssh():
            raise Exception("SSH failing")
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
        self.boot_src.update_boot_files()
        # Start loggers
        self.monitor_uboot.start_log()
        self.monitor_kernel.start_log()
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
        self.monitor_uboot.stop_log()
        self.monitor_kernel.stop_log()


if __name__ == "__main__":
    m = manager()
    m.run_test()
