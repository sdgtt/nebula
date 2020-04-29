import logging
import subprocess
import time

import fabric
from fabric import Connection
from nebula.common import utils

log = logging.getLogger(__name__)


class network(utils):
    def __init__(
        self,
        dutip="analog",
        dutusername="root",
        dutpassword="analog",
        dhcp=False,
        yamlfilename=None,
    ):
        self.dutip = dutip
        self.dutusername = dutusername
        self.dutpassword = dutpassword
        self.dhcp = dhcp
        self.update_defaults_from_yaml(yamlfilename, __class__.__name__)

    def ping_board(self, tries=10):
        """ Ping board and check if any received

            return: True non-zero received, False zero received
        """
        log.info("Checking for board through ping")
        ping = subprocess.Popen(
            ["ping", "-c", "4", self.dutip],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for p in range(tries):
            out, error = ping.communicate()
            if "0 received" not in str(out):
                return False
        return True

    def check_ssh(self):
        """ SSH to board board and check if its possible to run any command

            return: True working ssh, False non-working ssh
        """
        log.info("Checking for board through SSH")
        result = fabric.Connection(
            self.dutusername + "@" + self.dutip,
            connect_kwargs={"password": self.dutpassword},
        ).run("uname -a", hide=True)
        return result.failed

    def check_board_booted(self):
        """ Check if board has network activity with ping, then check SSH working
            This function raises exceptions on failures
        """
        if self.ping_board():
            raise Exception("Board not booted")
        else:
            logging.info("PING PASSED")

        if self.check_ssh():
            raise Exception("SSH failing")
        else:
            logging.info("SSH PASSED")

    def reboot_board(self, bypass_sleep=False):
        """ Reboot board over SSH, otherwise raise exception
        """
        log.info("Rebooting board over SSH")
        # Try to reboot board with SSH if possible
        try:
            result = fabric.Connection(
                self.dutusername + "@" + self.dutip,
                connect_kwargs={"password": self.dutpassword},
            ).run("reboot", hide=False)
            if result.ok:
                print("Rebooting board with SSH")
                if not bypass_sleep:
                    time.sleep(30)
            else:
                # Use PDU
                raise Exception("PDU reset not implemented yet")

        except Exception as ex:
            raise Exception("Exception occurred during SSH Reboot", str(ex))

    def run_ssh_command(self, command):
        result = fabric.Connection(
            self.dutusername + "@" + self.dutip,
            connect_kwargs={"password": self.dutpassword},
        ).run(command, hide=True)
        if result.failed:
            raise Exception("Failed to run command:", command)
        return result

    def copy_file_to_remote(self, src, dest):
        Connection(
            self.dutusername + "@" + self.dutip,
            connect_kwargs={"password": self.dutpassword},
        ).put(src, remote=dest)

    def update_boot_partition(
        self, bootbinpath=None, uimagepath=None, devtreepath=None
    ):
        """ update_boot_partition:
                Update boot files on existing card which from remote files
        """
        log.info("Updating boot files over SSH")
        self.run_ssh_command("mkdir /tmp/sdcard")
        self.run_ssh_command("mount /dev/mmcblk0p1 /tmp/sdcard")
        if bootbinpath:
            self.copy_file_to_remote(bootbinpath, "/tmp/sdcard/")
        if uimagepath:
            self.copy_file_to_remote(uimagepath, "/tmp/sdcard/")
        if devtreepath:
            self.copy_file_to_remote(devtreepath, "/tmp/sdcard/")
        self.run_ssh_command("reboot")

    def update_boot_partition_existing_files(self, subfolder=None):
        """ update_boot_partition_existing_files:
                Update boot files on existing card which contains reference
                files in the BOOT partition

                You must specify the subfolder with the BOOT partition to use.
                For example: zynq-zc706-adv7511-fmcdaq2
        """
        log.info("Updating boot files over SSH from SD card itself")
        if not subfolder:
            raise Exception("Must provide a subfolder")
        self.run_ssh_command("mkdir /tmp/sdcard")
        self.run_ssh_command("mount /dev/mmcblk0p1 /tmp/sdcard")
        self.run_ssh_command("cp /tmp/sdcard/" + subfolder + "/BOOT.BIN /tmp/sdcard/")
        if "zynqmp" in subfolder:
            self.run_ssh_command("cp /tmp/sdcard/zynqmp-common/Image /tmp/sdcard/")
            self.run_ssh_command(
                "cp /tmp/sdcard/" + subfolder + "/system.dtb /tmp/sdcard/"
            )
        else:
            self.run_ssh_command("cp /tmp/sdcard/zynq-common/uImage /tmp/sdcard/")
            self.run_ssh_command(
                "cp /tmp/sdcard/" + subfolder + "/devicetree.dtb /tmp/sdcard/"
            )
        self.run_ssh_command("reboot")
