import fabric
import subprocess
import time
import yaml


class network:
    def __init__(self, dutip="analog", dutusername="root", dutpassword="analog", yamlfilename=None):
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
            raise Except("network-config field not in yaml config file")
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
                time.sleep(10)
            else:
                # Use PDU
                raise Exception("PDU reset not implemented yet")

        except Exception as ex:
            print(ex)
            print("Exception occured during SSH Reboot")
            pass
