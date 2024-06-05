"""USB SD Card MUX controller class to manage the mux and connected cards."""
import glob
import logging
import os
import pathlib
import random
import re
import string
import time
from pathlib import Path

import pyudev
from usbsdmux import usbsdmux

import nebula.helper as helper
from nebula.common import utils

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
        self.board_name = board_name
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
        self.set_mux_mode("host")
        time.sleep(5)
        context = pyudev.Context()
        for device in context.list_devices(subsystem="block"):
            if device.get("ID_SERIAL_SHORT") == os.path.basename(
                self._mux_in_use
            ).strip("id-"):
                self._target_sdcard = re.sub(
                    r"[0-9]+", "", os.path.basename(device.get("DEVNAME"))
                )
                break

        if not self._target_sdcard:
            raise Exception("No muxed SD card found")

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
        log.warn(
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
        partition="boot",
        target=[],
        destination="backup",
        subfolder=None,
    ):
        """Backup specified files to an external location

        Args:
            partition (str): Source partition. Either boot or root
            target (list): Filenames that will be backup'd
            destination (str): Directory name at host to place the backup'd files
            subfolder (str): Directory name under destination to place the backup'd files, random by default
        """
        folder, boot_p, rootfs_folder, root_p = self._mount_sd_card(
            include_root_partition=True
        )

        target_folder = folder
        if partition == "root":
            target_folder = rootfs_folder

        back_up_path = Path(os.path.join(destination, target_folder))
        if subfolder:
            back_up_path = Path(os.path.join(destination, subfolder))
        back_up_path.mkdir(parents=True, exist_ok=True)

        try:
            for f in target:
                files = glob.glob(os.path.join(f"/tmp/{target_folder}", f))
                if not files:
                    raise Exception(f"Cannot enumerate target /tmp/{target_folder}/{f}")
                for file_path in files:
                    log.info(f"Backing up {file_path} to {str(back_up_path)}")
                    if os.path.exists(file_path):
                        os.system(f"cp -r {file_path} {str(back_up_path)}")
                    else:
                        raise Exception("File not found " + file_path)
        except Exception as ex:
            log.error(str(ex))
            raise ex
        finally:
            # unmount sd card
            os.system(f"umount /tmp/{folder}")
            os.system(f"umount /tmp/{rootfs_folder}")

        return subfolder if subfolder else target_folder

    def update_boot_files_from_external(
        self,
        bootbin_loc=None,
        kernel_loc=None,
        devicetree_loc=None,
        devicetree_overlay_loc=None,
        devicetree_overlay_config_loc=None,
        extlinux_loc=None,
        scr_loc=None,
        preloader_loc=None,
    ):
        """Update the boot files from outside SD card itself.

        Args:
            bootbin_loc (str): The path to the boot.bin file
            kernel_loc (str): The path to the kernel file
            devicetree_loc (str): The path to the devicetree file
            devicetree_overlay_loc (str): The path to the devicetree overlay file
            devicetree_overlay_config (str): The devicetree overlay configuration to be written on /boot/config.txt
            extlinux_loc (str): The path to the Extlinux configuration file (Intel boards).
            scr_loc (str): The path to the .scr file (Intel boards).
            preloader_loc (str): The path to the preloader file (.sfp) (Intel boards).
        """
        args = locals()
        folder, boot_p = self._mount_sd_card()
        preloader_p = f"{self._target_sdcard}3"

        try:
            for field, bootfile_loc in args.items():
                if field in ["self"]:
                    continue
                if not bootfile_loc:
                    log.warn(f"Empty argument {field} ")
                    continue
                bootfile_name = os.path.basename(bootfile_loc)
                if not os.path.isfile(bootfile_loc):
                    raise Exception("File not found: " + bootfile_loc)

                if field == "devicetree_overlay_loc":
                    outfile = os.path.join("/tmp", folder, "overlays", bootfile_name)
                elif field == "preloader_loc":
                    log.info(f"Writing {bootfile_loc} to /dev/{preloader_p} ")
                    os.system(
                        f'dd if={bootfile_loc} of="/dev/{preloader_p}" bs=512 status=progress'
                    )
                    continue
                elif field == "extlinux_loc":
                    os.system(f"mkdir -p /tmp/{folder}/extlinux")
                    outfile = os.path.join("/tmp", folder, "extlinux", bootfile_name)
                else:
                    outfile = os.path.join("/tmp", folder, bootfile_name)

                log.info(f"Copying {bootfile_loc} to {outfile} ")
                os.system(f"cp -r {bootfile_loc} {outfile}")

            log.info("Updated boot files successfully... unmounting")
        except Exception as ex:
            log.error(str(ex))
            raise ex
        finally:
            os.system(f"umount /tmp/{folder}")
            os.system(f"rm -rf /tmp/{folder}")

    def update_rootfs_files_from_external(self, target, destination):
        """Update the root file system from outside SD card itself.

        Args:
            target (str): The path to the external target file/folder.
            destination (str): The path to the destination file/folder.
        """
        folder, boot_p, rootfs_folder, root_p = self._mount_sd_card(
            include_root_partition=True
        )

        try:
            outfile = os.path.join("/tmp", rootfs_folder, destination)
            if not os.path.exists(target):
                raise Exception("File/Folder not found: " + target)
            command = f"cp -r {target} {outfile}"
            if os.system(command) != 0:
                raise Exception(f"{command} failed")
            log.info("Updated rootfs successfully... unmounting")
        finally:
            os.system(f"umount /tmp/{folder}")
            os.system(f"rm -rf /tmp/{folder}")
            os.system(f"umount /tmp/{rootfs_folder}")
            os.system(f"rm -rf /tmp/{rootfs_folder}")

    def update_boot_files_from_sdcard_itself(
        self,
        descriptor_path=None,
        bootbin_loc=None,
        kernel_loc=None,
        devicetree_loc=None,
        extlinux_loc=None,
        scr_loc=None,
        preloader_loc=None,
    ):
        """Update the boot files from the SD card itself.

        Args:
            descriptor_path (str): The path to the kuiper.json.
            bootbin_loc (str): The path to the boot.bin file on the SD card.
            kernel_loc (str): The path to the kernel file on the SD card.
            devicetree_loc (str): The path to the devicetree file on the SD card.
            extlinux_loc (str): The path to the Extlinux configuration file on the SD card (Intel boards).
            scr_loc (str): The path to the .scr file on the SD card (Intel boards).
            preloader_loc (str): The path to the preloader file (.sfp) on the SD card (Intel boards).
        """
        args = locals()
        # check if if all loc are still None
        del args["self"]
        del args["descriptor_path"]
        args_status = all(loc is None for loc in args.values())

        folder, boot_p = self._mount_sd_card()
        preloader_p = f"{self._target_sdcard}3"
        mount_path = os.path.join("/tmp/", folder)

        if args_status:
            h = helper()
            if descriptor_path:
                descriptor_path = descriptor_path
            else:
                path = pathlib.Path(__file__).parent.absolute()
                descriptor_path = os.path.join(path, "resources", "kuiper.json")
            try:
                kuiperjson_loc = os.path.join(mount_path, "kuiper.json")
                os.path.isfile(kuiperjson_loc)
                os.replace(kuiperjson_loc, descriptor_path)
            except Exception:
                log.warning("Cannot find project descriptor on target")
            boot_files_path = h.get_boot_files_from_descriptor(
                descriptor_path, self.board_name
            )

            # update items to args
            for boot_file in boot_files_path:
                file_path = os.path.join(mount_path, boot_file[1].lstrip("/boot"))
                loc_map = {
                    "bootbin_loc": "BIN",
                    "kernel_loc": "Image",
                    "devicetree_loc": "dtb",
                    "extlinux_loc": "conf",
                    "scr_loc": "scr",
                    "preloader_loc": "sfp",
                }
                for key, val in loc_map.items():
                    if val in file_path:
                        args.update({key: file_path})

        # filter: remove None loc
        args_filtered = dict(filter(lambda item: item[1] is not None, args.items()))

        try:
            for field, bootfile_loc in args_filtered.items():
                if field in ["self"]:
                    continue
                if mount_path in bootfile_loc:
                    bootfile_loc = bootfile_loc
                else:
                    bootfile_loc = os.path.join(mount_path, bootfile_loc)
                if not os.path.isfile(bootfile_loc):
                    options = os.listdir(f"/tmp/{folder}")
                    options = [
                        folder for o in options if os.path.isdir(f"/tmp/{folder}/{o}")
                    ]
                    os.system(f"umount /tmp/{folder}")
                    os.system(f"rm -rf /tmp/{folder}")
                    raise Exception(
                        "File not found: "
                        + bootfile_loc
                        + "\nOptions are: "
                        + "\n".join(options)
                    )
                if field == "preloader_loc":
                    os.system(
                        f'dd if={bootfile_loc} of="/dev/{preloader_p}" bs=512 status=progress'
                    )
                    continue

                bootfile_name = os.path.basename(bootfile_loc)
                if field == "extlinux_loc":
                    os.system(f"mkdir -p /tmp/{folder}/extlinux")
                    bootfile_name = "extlinux/" + bootfile_name
                log.info(f"Copying {bootfile_loc}")
                os.system(f"cp {bootfile_loc} /tmp/{folder}/{bootfile_name}")

            log.info("Updated boot files successfully... unmounting")
        finally:
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
            log.warn(f"{s.strip()} not found")
        if sn not in dt:
            dt = dt.replace(s, sn)
            dt = dt + "\n&sdc16 { no-1-8-v ;};"
        else:
            log.warn(f"{sn.strip()} already exists")
        s = "mmc@ff170000"
        sn = "sdc17:mmc@ff170000"
        if s not in dt:
            log.warn(f"{s.strip()} not found")
        if sn not in dt:
            dt = dt.replace(s, sn)
            dt = dt + "\n&sdc17 { no-1-8-v ;};"
        else:
            log.warn(f"{sn.strip()} already exists")

        with open(dts_loc, "w") as f:
            f.write(dt)

        # Compile the devicetree
        os.system(
            f"dtc -I dts {dts_loc} " + f" -O dtb -o /tmp/{folder}/{devicetree_filename}"
        )

        log.info("Updated devicetree successfully... unmounting")
        os.system(f"umount /tmp/{folder}")
        os.system(f"rm -rf /tmp/{folder}")
