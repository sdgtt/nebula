import subprocess
import time

import fabric
import yaml
from fabric import Connection


class network:
    def __init__(
        self,
        dutip="analog",
        dutusername="root",
        dutpassword="analog",
        yamlfilename=None,
    ):
        self.dutip = dutip
        self.dutusername = dutusername
        self.dutpassword = dutpassword
        if yamlfilename:
            self.update_defaults_from_yaml(yamlfilename)

    def update_defaults_from_yaml(self, filename):
        stream = open(filename, "r")
        configs = yaml.safe_load(stream)
        stream.close()
        if "network-config" not in configs:
            raise Exception("network-config field not in yaml config file")
        configsList = configs["network-config"]
        for config in configsList:
            for k in config:
                if not hasattr(self, k):
                    raise Exception("Unknown field in network yaml " + k)
                setattr(self, k, config[k])

    def ping_board(self, tries=10):
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
        result = fabric.Connection(
            self.dutusername + "@" + self.dutip,
            connect_kwargs={"password": self.dutpassword},
        ).run("uname -a", hide=True)
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
