"""USB SD Card MUX controller class to manage the mux and connected cards."""
import logging
import os
import random
import re
import string
import time
import glob

from nebula.common import utils
from usbsdmux import usbsdmux
from pathlib import Path

log = logging.getLogger(__name__)


class usbmux(utils):
    """USB SD Card MUX controller and helper methods"""

    search_path = "/dev/usb-sd-mux/"
    target_mux = None
    _mux_in_use = None
    _mux = None
    _target_sdcard = None

    def __init__(
        self, yamlfilename=None, board_name=None, target_mux=None, search_path=None
    ):
        self.target_mux = target_mux
        if search_path:
            self.search_path = search_path

        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )
        self.find_mux_device()
        self._mux = usbsdmux.UsbSdMux(self._mux_in_use)

    def find_mux_device(self):
        """Find the mux device itself."""
        devs = os.listdir(self.search_path)
        if not devs:
            raise Exception("No devices found")

        if self.target_mux:
            if self.target_mux not in devs:
                raise Exception("Target mux device not found")
            self._mux_in_use = os.path.join(self.search_path, self.target_mux)
        else:
            # Pick the first one
            self._mux_in_use = os.path.join(self.search_path, devs[0])

    def get_mux_mode(self):
        """Get the current mux mode."""
        return self._mux.get_mode()

    def set_mux_mode(self, mode):
        """Set the mux mode.

        Args:
            mode (str): The mode to set the mux to. Options are: "host", "dut", "off".
        """
        if mode == "dut":
            self._mux.mode_DUT()
        elif mode == "host":
            self._mux.mode_host()
        elif mode == "off":
            self._mux.mode_disconnect()
        else:
            raise Exception("Unknown mode: " + mode)

    def find_muxed_sdcard(self):
        """Find SD card connected through SD card mux.

        Before calling this method PLEASE POWER DOWN THE DUT.
        """
        self.set_mux_mode("dut")
        time.sleep(1)
        files_pre = os.listdir("/dev")
        self.set_mux_mode("host")
        for _ in range(10):
            time.sleep(2)
            files_post = os.listdir("/dev")
            # Find the difference
            files_diff = list(set(files_post) - set(files_pre))
            if files_diff:
                break
        if not files_diff:
            raise Exception("No muxed SD card found")
        pfiles = [re.sub(r"[0-9]+", "", f) for f in files_diff]
        # remove duplicates from list
        pfiles = list(set(pfiles))
        if len(pfiles) > 1:
            raise Exception("Multiple muxed SD cards found")
        self._target_sdcard = pfiles[0]

    def write_img_file_to_sdcard(self, img_filename):
        """Write an image file to the SD card.

        Args:
            img_filename (str): The path to the image file to write.
        """
        if not os.path.isfile(img_filename):
            raise Exception("File not found: " + img_filename)
        if not self._target_sdcard:
            self.find_muxed_sdcard()
        self.set_mux_mode("host")
        time.sleep(5)
        # Check to make sure SD card is there
        devs = os.listdir("/dev")
        if self._target_sdcard not in devs:
            raise Exception("Target SD card not found")
        print(
            f"WARNING: Writing image file to SD card. Will destroy all data on {self._target_sdcard}"
        )
        time.sleep(5)
        e = os.system(
            f'dd if="{img_filename}" of="/dev/{self._target_sdcard}" bs=4M conv=fsync status=progress'
        )
        if e != 0:
            raise Exception("Error writing image file to SD card")

    def _mount_sd_card(self, include_root_partition=False):
        if not self._target_sdcard:
            self.find_muxed_sdcard()
        self.set_mux_mode("host")
        time.sleep(5)
        # mount the SD card
        devs = os.listdir("/dev")
        boot_p = f"{self._target_sdcard}1"
        if boot_p not in devs:
            raise Exception(f"Target BOOT partition not found {boot_p}")
        boot_p = os.path.join("/dev", boot_p)
        folder = "".join(random.choices(string.ascii_lowercase, k=5))
        os.system(f"mkdir /tmp/{folder}")
        time.sleep(1)
        os.system(f"mount {boot_p} /tmp/{folder}")

        if include_root_partition:
            root_p = f"{self._target_sdcard}2"
            if root_p not in devs:
                raise Exception(f"Target Root FS partition not found {root_p}")
            root_p = os.path.join("/dev", root_p)
            rootfs_folder = "".join(random.choices(string.ascii_lowercase, k=5))
            os.system(f"mkdir /tmp/{rootfs_folder}")
            time.sleep(1)
            os.system(f"mount {root_p} /tmp/{rootfs_folder}")
            return folder, boot_p, rootfs_folder, root_p

        return folder, boot_p

    def backup_files_to_external(
        self,
        partition = "boot",
        target = [],
        destination="backup",
    ):
        """Backup specified files to an external location

        Args:
            partition (str): Source partition. Either boot or root
            target (list): Filenames that will be backup'd
            destination (str): Directory name at host to place the backup'd files
        """
        folder, boot_p, rootfs_folder, root_p = self._mount_sd_card(include_root_partition=True)

        target_folder = folder
        target_partition = boot_p
        if partition == "root":
            target_folder = rootfs_folder
            target_partition = root_p

        back_up_path = Path(os.path.join(destination,target_folder))
        back_up_path.mkdir(parents=True, exist_ok=True)

        try:
            for f in target:
                files = glob.glob(os.path.join(f"/tmp/{target_folder}",f))
                for file_path in files:

                    log.info(f"Backing up {file_path} to {str(back_up_path)}")
                    if os.path.exists(file_path):
                        os.system(f"cp -r {file_path} {str(back_up_path)}")
                    else:
                        raise Exception("File not found " + file_name)
        except Exception as ex:
            log.error(str(ex))
            raise ex
        finally:
            # unmount sd card
            os.system(f"umount /tmp/{folder}")
            os.system(f"umount /tmp/{rootfs_folder}")

        return target_folder

    def update_boot_files_from_external(
        self,
        bootbin_loc=None,
        kernel_loc=None,
        devicetree_loc=None,
        devicetree_overlay_loc=None,
        devicetree_overlay_config_loc=None,
    ):
        """Update the boot files from outside SD card itself.

        Args:
            bootbin_loc (str): The path to the boot.bin file
            kernel_loc (str): The path to the kernel file
            devicetree_loc (str): The path to the devicetree file
            devicetree_overlay_loc (str): The path to the devicetree overlay file
            devicetree_overlay_config (str): The devicetree overlay configuration to be written on /boot/config.txt
        """
        args = locals()
        folder, boot_p = self._mount_sd_card()

        try:
            for btfiletype, loc in args.items():
                if loc:
                    if not isinstance(loc, (str, bytes, os.PathLike)):
                        if isinstance(loc, type(self)):
                            continue
                        raise Exception(f"Invalid type {type(loc)}")
                    if btfiletype == "bootbin_loc":
                        outfile = os.path.join("/tmp",folder,"BOOT.BIN")
                    elif btfiletype == "devicetree_overlay_loc":
                        outfile = os.path.join("/tmp",folder,"overlays",os.path.basename(loc))
                    else:
                        outfile = os.path.join("/tmp",folder,os.path.basename(loc))
                    if not os.path.isfile(loc):
                        raise Exception("File not found: " + loc)
                    log.info(f"Copying {loc} to {outfile} ")
                    os.system(f"cp -r {loc} {outfile}")

            log.info("Updated boot files successfully... unmounting")
        except Exception as ex:
            log.error(str(ex))
        finally:
            os.system(f"umount /tmp/{folder}")
            os.system(f"rm -rf /tmp/{folder}")

    def update_rootfs_files_from_external(
        self,
        target,
        destination
    ):
        """Update the root file system from outside SD card itself.

        Args:
            target (str): The path to the external target file/folder.
            destination (str): The path to the destination file/folder.
        """
        folder, boot_p, rootfs_folder, root_p = self._mount_sd_card(include_root_partition=True)

        try:
            outfile = os.path.join("/tmp",rootfs_folder,destination)
            if not os.path.exists(target):
                raise Exception("File/Folder not found: " + target)

            os.system(f"cp -r {target} {outfile}")
            log.info("Updated rootfs successfully... unmounting")
        finally:
            os.system(f"umount /tmp/{folder}")
            os.system(f"rm -rf /tmp/{folder}")
            os.system(f"umount /tmp/{rootfs_folder}")
            os.system(f"rm -rf /tmp/{rootfs_folder}")

    def update_boot_files_from_sdcard_itself(
        self, bootbin_loc=None, kernel_loc=None, devicetree_loc=None
    ):
        """Update the boot files from the SD card itself.

        Args:
            bootbin_loc (str): The path to the boot.bin file on the SD card.
            kernel_loc (str): The path to the kernel file on the SD card.
            devicetree_loc (str): The path to the devicetree file on the SD card.
        """
        folder, boot_p = self._mount_sd_card()

        if bootbin_loc:
            bootbin_loc = os.path.join("/tmp/", folder, bootbin_loc)
            if not os.path.isfile(bootbin_loc):
                options = os.listdir(f"/tmp/{folder}")
                options = [
                    folder for o in options if os.path.isdir(f"/tmp/{folder}/{o}")
                ]
                os.system(f"umount /tmp/{folder}")
                os.system(f"rm -rf /tmp/{folder}")
                raise Exception(
                    "File not found: "
                    + bootbin_loc
                    + "\nOptions are: "
                    + "\n".join(options)
                )
            os.system(f"cp {bootbin_loc} /tmp/{folder}/BOOT.BIN")
        if kernel_loc:
            kernel_loc = os.path.join("/tmp/", folder, kernel_loc)
            if not os.path.isfile(kernel_loc):
                os.system(f"umount /tmp/{folder}")
                os.system(f"rm -rf /tmp/{folder}")
                raise Exception("File not found: " + kernel_loc)
            image = os.path.basename(kernel_loc)
            os.system(f"cp {kernel_loc} /tmp/{folder}/{image}")
        if devicetree_loc:
            devicetree_loc = os.path.join("/tmp/", folder, devicetree_loc)
            if not os.path.isfile(devicetree_loc):
                options = os.listdir(f"/tmp/{folder}")
                options = [
                    folder for o in options if os.path.isdir(f"/tmp/{folder}/{o}")
                ]
                os.system(f"umount /tmp/{folder}")
                os.system(f"rm -rf /tmp/{folder}")
                raise Exception(
                    "File not found: "
                    + devicetree_loc
                    + "\nOptions are: "
                    + "\n".join(options)
                )
            dt = os.path.basename(devicetree_loc)
            os.system(f"cp {devicetree_loc} /tmp/{folder}/{dt}")

        print("Updated boot files successfully... unmounting")
        os.system(f"umount /tmp/{folder}")
        os.system(f"rm -rf /tmp/{folder}")

    def update_devicetree_for_mux(self, devicetree_filename="system.dtb"):

        folder, boot_p = self._mount_sd_card()

        # Update the devicetree
        devicetree_loc = os.path.join("/tmp/", folder, devicetree_filename)
        if not os.path.isfile(devicetree_loc):
            os.system(f"umount /tmp/{folder}")
            os.system(f"rm -rf /tmp/{folder}")
            raise Exception("File not found: " + devicetree_loc)

        dts = devicetree_filename.replace(".dtb", ".dts")
        dts_loc = os.path.join("/tmp/", folder, dts)
        # Decompile the devicetree
        os.system(
            f"dtc -I dtb /tmp/{folder}/{devicetree_filename} " + f" -O dts -o {dts_loc}"
        )

        with open(dts_loc, "r") as f:
            dt = f.read()

        s = "mmc@ff160000"
        sn = "sdc16:mmc@ff160000"
        if s not in dt:
            print(f"{s.strip()} not found")
        if sn not in dt:
            dt = dt.replace(s, sn)
            dt = dt + "\n&sdc16 { no-1-8-v ;};"
        else:
            print(f"{sn.strip()} already exists")
        s = "mmc@ff170000"
        sn = "sdc17:mmc@ff170000"
        if s not in dt:
            print(f"{s.strip()} not found")
        if sn not in dt:
            dt = dt.replace(s, sn)
            dt = dt + "\n&sdc17 { no-1-8-v ;};"
        else:
            print(f"{sn.strip()} already exists")

        with open(dts_loc, "w") as f:
            f.write(dt)

        # Compile the devicetree
        os.system(
            f"dtc -I dts {dts_loc} " + f" -O dtb -o /tmp/{folder}/{devicetree_filename}"
        )

        print("Updated devicetree successfully... unmounting")
        os.system(f"umount /tmp/{folder}")
        os.system(f"rm -rf /tmp/{folder}")
