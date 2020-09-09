import os
import shutil
import subprocess

# import psutil
import fabric
from fabric import Connection
import logging
import time
import tempfile

log = logging.getLogger(__name__)


class usbdev:
    def __init__(self):
        self.wait_time_seconds = 120

    def shell_out2(self, script):
        p = subprocess.Popen(
            script,
            shell=True,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        (output, err) = p.communicate()
        return output.decode("utf-8")

    def _mount_dev(self, name):
        # Get mount point
        cmd = "sudo blkid -L " + name
        out = self.shell_out2(cmd)
        out = out.replace("\n", "")
        # Do mount
        temp_dir_path = tempfile.mkdtemp()
        log.info("Trying to auto-mount |" + out + "| to " + temp_dir_path)
        cmd = "sudo mount " + out + " " + temp_dir_path
        out = self.shell_out2(cmd)
        return temp_dir_path

    def _check_disk_mounted(
        self, name="PlutoSDR", skip_exception=False, do_mount=False
    ):
        for l in range(3):
            cmd = "sudo blkid -L " + name
            out = self.shell_out2(cmd)
            if len(out) == 0:
                return False, False
            cmd = "sudo mount -l | grep `sudo blkid -L " + name + "` | grep dev"
            out = self.shell_out2(cmd)
            out = out.split(" ")
            if len(out) > 1:
                partition = out[0]
                mountpoint = out[2]
                break
            elif l == 0:
                log.info("Waiting for automount first")
                time.sleep(15)
            else:
                if do_mount:
                    self._mount_dev(name)
                partition = False
                mountpoint = False
        if not skip_exception:
            if not os.path.exists(partition):
                raise Exception("partition not found: " + str(partition))
            if not os.path.isdir(mountpoint):
                raise Exception("mountpoint not found: " + str(mountpoint))
        return mountpoint, partition

    def update_firmware(self, filename, device="PlutoSDR"):
        if not os.path.isfile(filename):
            raise Exception("File not found: " + filename)
        if "pluto" in device.lower():
            name = "PlutoSDR"
        else:
            name = "M2k"
        mount, partition = self._check_disk_mounted(name=name, do_mount=True)
        log.info("Found mount: " + mount + " for partition: " + partition)
        # Send
        log.info("Copy firmware over")
        shutil.copy(filename, mount)
        # Eject
        log.info("Ejecting")
        self.shell_out2("eject " + partition)
        time.sleep(5)

    def wait_for_usb_mount(self, device):
        if "pluto" in device.lower():
            name = "PlutoSDR"
        else:
            name = "M2k"
        for k in range(self.wait_time_seconds):
            mount, partition = self._check_disk_mounted(
                name=name, skip_exception=True, do_mount=True
            )
            time.sleep(1)
            log.info("Waiting for USB mass storage " + str(k))
            if mount and partition:
                log.info("Found USB mass storage: " + mount + " " + partition)
                return True
        return False


if __name__ == "__main__":
    u = usbdev()
    filename = "outs/plutosdr-fw-v0.32.zip"
    u.update_firmware(filename, device="pluto")
    time.sleep(3)
    u.wait_for_usb_mount(device="pluto")
