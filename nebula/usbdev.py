import os
import shutil
import subprocess


class usbdev:
    def __init__(self):
        pass

    def shell_out(self, cmd):
        cmd = cmd.split(" ")
        print(cmd)
        subprocess.run(cmd)

    def shell_out2(self, script):
        print(script)
        p = subprocess.Popen(script, shell=True, executable="/bin/bash")
        (output, err) = p.communicate()
        return output.decode("utf-8")

    def _check_disk_mounted(self):
        cmd = "sudo mount -l | grep `sudo blkid -L PlutoSDR`"
        out = self.shell_out2(cmd)
        print(out)


if __name__ == "__main__":
    u = usbdev()
    u._check_disk_mounted()
