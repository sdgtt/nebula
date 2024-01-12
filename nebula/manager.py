import glob
import logging
import os
import tarfile
import time

import yaml

import nebula.common as common
import nebula.errors as ne
import nebula.helper as helper
from nebula.driver import driver
from nebula.jtag import jtag
from nebula.netconsole import netconsole
from nebula.network import network
from nebula.pdu import pdu
from nebula.tftpboot import tftpboot
from nebula.uart import uart
from nebula.usbdev import usbdev
from nebula.usbmux import usbmux

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class manager:
    """Board Manager"""

    def __init__(  # noqa:C901
        self,
        monitor_type="uart",
        configfilename=None,
        board_name=None,
        vivado_version=None,
        extras=None,
    ):
        # Check if config info exists in yaml
        self.configfilename = configfilename
        self.monitor_type = monitor_type
        if configfilename:
            stream = open(configfilename, "r")
            configs = yaml.safe_load(stream)
            stream.close()
        else:
            configs = None

        configs = common.multi_device_check(configs, board_name)

        self.power = None
        if "pdu-config" in configs:
            self.power = pdu(yamlfilename=configfilename, board_name=board_name)

        self.jtag_use = False
        self.jtag = False
        if "board-config" in configs:
            for config in configs["board-config"]:
                if "allow-jtag" in config:
                    self.jtag_use = config["allow-jtag"]
                    if self.jtag_use:
                        try:
                            self.jtag = jtag(
                                yamlfilename=configfilename,
                                board_name=board_name,
                                vivado_version=vivado_version,
                            )
                        except Exception as e:
                            log.info(str(e))
                            log.info(
                                "Power cycling board and will attempt jtag connection again."
                            )
                            self.power.power_cycle_board()
                            time.sleep(60)
                            self.jtag = jtag(
                                yamlfilename=configfilename,
                                board_name=board_name,
                                vivado_version=vivado_version,
                            )

        if "netconsole" in monitor_type.lower():
            monitor_uboot = netconsole(port=6666, logfilename="uboot.log")
            monitor_kernel = netconsole(port=6669, logfilename="kernel.log")
            self.monitor = [monitor_uboot, monitor_kernel]
        elif "uart" in monitor_type.lower():
            if "uart-config" not in configs:
                configfilename = None
            else:
                configfilename = self.configfilename
            u = uart(yamlfilename=configfilename, board_name=board_name)
            self.monitor = [u]

            self.driver = driver(yamlfilename=configfilename, board_name=board_name)

        if "network-config" not in configs:
            configfilename = None
        else:
            configfilename = self.configfilename
        self.net = network(yamlfilename=configfilename, board_name=board_name)

        self.reference_boot_folder = None
        self.devicetree_subfolder = None
        self.boot_subfolder = None
        if "downloader-config" in configs:
            for config in configs["downloader-config"]:
                if "reference_boot_folder" in config:
                    self.reference_boot_folder = config["reference_boot_folder"]
                if "devicetree_subfolder" in config:
                    self.devicetree_subfolder = config["devicetree_subfolder"]
                if "boot_subfolder" in config:
                    self.boot_subfolder = config["boot_subfolder"]

        # self.boot_src = tftpboot()

        self.tftp = False

        if "usbmux-config" in configs:
            self.usbsdmux = usbmux(
                yamlfilename=self.configfilename, board_name=board_name
            )
        else:
            self.usbsdmux = None

        self.help = helper()
        self.usbdev = usbdev()
        self.board_name = board_name

    def _release_thread_lock(func):
        """A decorator to force a method to close thread resource"""

        def inner(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            finally:
                # close any open threading locks
                self.monitor[0].stop_log()

        return inner

    def get_status(self):
        pass

    def load_boot_bin(self):
        pass

    def _check_files_exist(self, *args):
        for filename in args:
            if not filename:
                continue
            if not os.path.exists(filename):
                raise Exception(filename + " not found or does not exist")

    def copy_reference_from_sdcard(self, bootbinpath, uimagepath, devtreepath):
        target = os.path.basename(uimagepath).strip("\n")
        if "uImage" in str(uimagepath):
            ref = "zynq-common/" + str(target)
        else:
            ref = "zynqmp-common/" + str(target)
        self.monitor[0].copy_reference(ref, target)

        if self.boot_subfolder is not None:
            ref = self.reference_boot_folder + "/" + str(self.boot_subfolder)
        else:
            ref = self.reference_boot_folder
        target = os.path.basename(bootbinpath).strip("\n")
        ref = ref + "/" + str(target)
        self.monitor[0].copy_reference(ref, target)

        if self.devicetree_subfolder is not None:
            ref = self.reference_boot_folder + "/" + str(self.devicetree_subfolder)
        else:
            ref = self.reference_boot_folder
        target = os.path.basename(devtreepath).strip("\n")
        ref = ref + "/" + str(target)
        self.monitor[0].copy_reference(ref, target)

    def network_check(self):
        if not self.net.ping_board():
            ip = self.monitor[0].get_ip_address()
            if ip != self.net.dutip:
                log.info("DUT IP changed to: " + str(ip))
                self.net.dutip = ip
                self.driver.uri = "ip:" + ip
                # Update config file
                self.help.update_yaml(
                    self.configfilename, "network-config", "dutip", ip, self.board_name
                )
            if not ip:
                self.monitor[0].request_ip_dhcp()
                ip = self.monitor[0].get_ip_address()
                if not ip:
                    self.monitor[0].stop_log()
                    raise ne.NetworkNotFunctionalAfterBootFileUpdate
                else:
                    self.net.dutip = ip
                    # Update config file
                    self.help.update_yaml(
                        self.configfilename,
                        "network-config",
                        "dutip",
                        ip,
                        self.board_name,
                    )

        # Check SSH
        if self.net.check_ssh():
            self.monitor[0].stop_log()
            raise ne.SSHNotFunctionalAfterBootFileUpdate

    @_release_thread_lock  # type: ignore
    def recover_board(  # noqa:C901
        self,
        system_top_bit_path,
        bootbinpath,
        uimagepath,
        devtreepath,
        extlinux_path=None,
        scr_path=None,
        preloader_path=None,
        fsblpath=None,
        ubootpath=None,
        sdcard=False,
    ):
        """Recover boards with UART, PDU, JTAG, USB-SD-Mux and Network if available"""
        self._check_files_exist(
            system_top_bit_path,
            bootbinpath,
            uimagepath,
            devtreepath,
            extlinux_path,
            scr_path,
            preloader_path,
            fsblpath,
            ubootpath,
        )
        try:
            # Flush UART
            self.monitor[0]._read_until_stop()  # Flush
            self.monitor[0].start_log(logappend=True)
            # Check if Linux is accessible
            log.info("Checking if Linux is accessible")
            try:
                out = self.monitor[0].get_uart_command_for_linux("uname -a", "Linux")
                if not out:
                    raise ne.LinuxNotReached
            except Exception as e:
                # raise LinuxNotReached for other exceptions
                log.info(str(e))
                raise ne.LinuxNotReached

            # Get IP over UART
            ip = self.monitor[0].get_ip_address()
            if not ip:
                self.monitor[0].request_ip_dhcp()
                ip = self.monitor[0].get_ip_address()
            if not ip:
                raise ne.NetworkNotFunctional
            if ip != self.net.dutip:
                log.info("DUT IP changed to: " + str(ip))
                self.net.dutip = ip
                self.driver.uri = "ip:" + ip
                # Update config file
                self.help.update_yaml(
                    self.configfilename, "network-config", "dutip", ip, self.board_name
                )

            self.monitor[0].stop_log()
            log.info("Linux accessible over Ethernet. System is good as is")
            return

        except (ne.LinuxNotReached, TimeoutError):
            log.warn("Linux is not accessible")
            try:
                if self.usbsdmux:
                    log.info("Will try to recover using usb-sd mux...")
                    self.power.power_down_board()
                    if sdcard:
                        # TODO: Recover using SD card boot files
                        pass
                    else:
                        self.usbsdmux.update_boot_files_from_external(
                            bootbin_loc=bootbinpath,
                            kernel_loc=uimagepath,
                            devicetree_loc=devtreepath,
                            extlinux_loc=extlinux_path,
                            scr_loc=scr_path,
                            preloader_loc=preloader_path,
                        )
                        # if devtreepath:
                        #     self.usbsdmux.update_devicetree_for_mux(devtreepath)
                    self.usbsdmux.set_mux_mode("dut")

                    # powercycle board
                    log.info("Power cycling to boot")
                    self.power_cycle_to_boot()
                else:
                    # Power cycle
                    log.info("Will try to recover using uart...")
                    log.info("Forcing UART override on reset")
                    if self.jtag_use:
                        log.info("Resetting with JTAG")
                        self.jtag.restart_board()
                    else:
                        # TODO: consider zed boards which uart closes after a powercycle
                        log.info("Power cycling")
                        self.power.power_cycle_board()

                    # Enter u-boot menu
                    if not self.monitor[0]._enter_uboot_menu_from_power_cycle():
                        raise ne.UbootNotReached

                    if self.tftp:
                        # Move files to correct position for TFTP
                        # self.monitor[0].load_system_uart_from_tftp()

                        # Load boot files over tftp
                        self.monitor[0].load_system_uart_from_tftp()

                    else:
                        # TODO: Add option to load boot files from SD card reference
                        # Load boot files via uart
                        log.info("Sending reference via uart")
                        self.monitor[0].load_system_uart(
                            system_top_bit_filename=system_top_bit_path,
                            kernel_filename=uimagepath,
                            devtree_filename=devtreepath,
                        )
                        results = self.monitor[0]._read_until_done_multi(
                            done_strings=["Starting kernel", "root@analog"],
                            max_time=100,
                        )

                        if len(results) == 1:
                            raise Exception("u-boot menu cannot boot kernel")
                        elif not results[1]:
                            raise Exception("Linux not fully booting")

                log.info("Linux fully booted")

                # Check is networking is working
                self.network_check()
                log.info("Board recovery complete")
                log.info("Home sweet home")
                self.monitor[0].stop_log()

            # JTAG RECOVERY
            except Exception as e:

                if self.jtag:
                    log.warn("Recovery failed. Will try JTAG")
                    self.board_reboot_jtag_uart(
                        system_top_bit_path,
                        uimagepath,
                        devtreepath,
                        fsblpath,
                        ubootpath,
                        sdcard,
                    )
                    log.info("Linux fully recovered")
                else:
                    log.error("JTAG not configured, cannot recover further!")
                    raise e
                self.monitor[0].stop_log()

    @_release_thread_lock  # type: ignore
    def board_reboot_jtag_uart(
        self,
        system_top_bit_path,
        uimagepath,
        devtreepath,
        fsblpath=None,
        ubootpath=None,
        sdcard=False,
    ):
        """Reset board and load fsbl, uboot, bitstream, and kernel
        over JTAG. Then over UART boot
        """
        self.monitor[0]._read_until_stop()  # Flush
        self.monitor[0].start_log(logappend=True)
        log.info("Resetting and looking DDR with boot files")
        log.info("Resetting with JTAG and checking if u-boot is reachable")
        self.jtag.restart_board()
        if self.monitor[0]._enter_uboot_menu_from_power_cycle():
            log.info("u-boot accessible after JTAG reset")
        else:
            log.info("u-boot not reachable, manually loading u-boot over JTAG")
            self.jtag.boot_to_uboot(fsblpath, ubootpath)
            log.info("Taking over UART control")
            if not self.monitor[0]._enter_uboot_menu_from_power_cycle():
                raise ne.UbootNotReached

        if self.tftp:
            # Load boot files over tftp
            self.monitor[0].load_system_uart_from_tftp()
        else:
            # TODO: Add option to load boot files from SD card reference
            # Load boot files via uart
            log.info("Sending reference via uart")
            self.monitor[0].load_system_uart(
                system_top_bit_filename=system_top_bit_path,
                kernel_filename=uimagepath,
                devtree_filename=devtreepath,
            )
            results = self.monitor[0]._read_until_done_multi(
                done_strings=["U-Boot", "Starting kernel", "root@analog"], max_time=100
            )

            if len(results) == 1:
                raise Exception("u-boot not reached")
            elif not results[1]:
                raise Exception("u-boot menu cannot boot kernel")
            elif not results[2]:
                raise Exception("Linux not fully booting")

            log.info("Linux fully booted")

            # Check is networking is working
            self.network_check()
            self.monitor[0].stop_log()

    @_release_thread_lock  # type: ignore
    def board_reboot_uart_net_pdu(
        self,
        system_top_bit_path,
        bootbinpath,
        uimagepath,
        devtreepath,
        extlinux_path=None,
        scr_path=None,
        preloader_path=None,
        sdcard=False,
    ):
        """Manager when UART, PDU, and Network are available"""
<<<<<<< HEAD
        if not sdcard:
            self._check_files_exist(
<<<<<<< HEAD
                system_top_bit_path,
                bootbinpath,
                uimagepath,
                devtreepath,
                extlinux_path,
                scr_path,
                preloader_path,
=======
                system_top_bit_path, bootbinpath, uimagepath, devtreepath
>>>>>>> 497fc8d (fix lint)
            )
        try:
            # Flush UART
            self.monitor[0]._read_until_stop()  # Flush
            self.monitor[0].start_log(logappend=True)
            # Check if Linux is accessible
            log.info("Checking if Linux is accessible")
            try:
                out = self.monitor[0].get_uart_command_for_linux("uname -a", "Linux")
                if not out:
                    raise ne.LinuxNotReached
            except Exception as e:
                # raise LinuxNotReached for other exceptions
                log.info(str(e))
                raise ne.LinuxNotReached

            # Get IP over UART
            ip = self.monitor[0].get_ip_address()
            if not ip:
                self.monitor[0].request_ip_dhcp()
                ip = self.monitor[0].get_ip_address()
            if not ip:
                raise ne.NetworkNotFunctional
            if ip != self.net.dutip:
                log.info("DUT IP changed to: " + str(ip))
                self.net.dutip = ip
                self.driver.uri = "ip:" + ip
                # Update config file
                self.help.update_yaml(
                    self.configfilename, "network-config", "dutip", ip, self.board_name
                )

            # Update board over SSH and reboot
            log.info("Update board over SSH and reboot")
            if sdcard:
                self.net.update_boot_partition_existing_files(self.board_name)
            else:
                self.net.update_boot_partition(
                    bootbinpath=bootbinpath,
                    uimagepath=uimagepath,
                    devtreepath=devtreepath,
                    extlinux_path=extlinux_path,
                    scr_path=scr_path,
                    preloader_path=preloader_path,
                )
            log.info("Waiting for reboot to complete")

            # Verify uboot anad linux are reached
            results = self.monitor[0]._read_until_done_multi(
                done_strings=["U-Boot", "Starting kernel", "root@analog"], max_time=100
            )

            if len(results) == 1:
                # try power cycling again first
                self.power_cycle_to_boot()
            elif not results[1]:
                raise Exception("u-boot menu cannot boot kernel")
            elif not results[2]:
                raise Exception("Linux not fully booting")

            log.info("Linux fully booted")

        except (ne.LinuxNotReached, ne.SSHError, TimeoutError):
            # Power cycle
            log.info("SSH reboot failed again after power cycling")
            log.info("Forcing UART override on reset")
            if self.jtag_use:
                log.info("Resetting with JTAG")
                self.jtag.restart_board()
            else:
                log.info("Power cycling")
                self.power.power_cycle_board()

            # Enter u-boot menu
            self.monitor[0]._enter_uboot_menu_from_power_cycle()

            if self.tftp:
                # Move files to correct position for TFTP
                # self.monitor[0].load_system_uart_from_tftp()

                # Load boot files over tftp
                self.monitor[0].load_system_uart_from_tftp()

            else:
                # Load boot files
                self.monitor[0].load_system_uart(
                    system_top_bit_filename=system_top_bit_path,
                    kernel_filename=uimagepath,
                    devtree_filename=devtreepath,
                )
            # NEED A CHECK HERE OR SOMETHING
            log.info("Waiting for boot to complete")
            time.sleep(60)

        # Check is networking is working
        self.network_check()

        print("Home sweet home")
        self.monitor[0].stop_log()

    @_release_thread_lock  # type: ignore
    def board_reboot_sdmux_pdu(
        self,
        system_top_bit_path=None,
        bootbinpath=None,
        uimagepath=None,
        devtreepath=None,
        devtree_overlay_path=None,
        devtree_overlay_config_path=None,
        extlinux_path=None,
        scr_path=None,
        preloader_path=None,
    ):
        """Manager when sdcardmux, pdu is available"""

        try:
            # Flush UART
            self.monitor[0]._read_until_stop()  # Flush
            self.monitor[0].start_log(logappend=True)
            # Check if Linux is accessible
            log.info("Checking if Linux is accessible")
            try:
                out = self.monitor[0].get_uart_command_for_linux("uname -a", "Linux")
                if not out:
                    raise ne.LinuxNotReached
            except Exception as e:
                # raise LinuxNotReached for other exceptions
                log.info(str(e))
                raise ne.LinuxNotReached

            # Get IP over UART
            ip = self.monitor[0].get_ip_address()
            if not ip:
                self.monitor[0].request_ip_dhcp()
                ip = self.monitor[0].get_ip_address()
            if not ip:
                raise ne.NetworkNotFunctional
            if ip != self.net.dutip:
                log.info("DUT IP changed to: " + str(ip))
                self.net.dutip = ip
                self.driver.uri = "ip:" + ip
                # Update config file
                self.help.update_yaml(
                    self.configfilename, "network-config", "dutip", ip, self.board_name
                )

            log.info("Update board over usb-sd-mux")
            self.usbsdmux.update_boot_files_from_external(
                bootbin_loc=bootbinpath,
                kernel_loc=uimagepath,
                devicetree_loc=devtreepath,
                devicetree_overlay_loc=devtree_overlay_path,
                devicetree_overlay_config_loc=devtree_overlay_config_path,
                extlinux_loc=extlinux_path,
                scr_loc=scr_path,
                preloader_loc=preloader_path,
            )
            # if devtreepath:
            #     self.usbsdmux.update_devicetree_for_mux(devtreepath)
            self.usbsdmux.set_mux_mode("dut")
            # powercycle board
            log.info("Power cycling to boot")
            self.power_cycle_to_boot()

        except Exception as e:
            log.error("Updating boot files using usbsdmux failed to complete")
            raise e

        # Check is networking is working
        self.network_check()

        print("Home sweet home")
        self.monitor[0].stop_log()

    def board_reboot(self):
        # Try to reboot over SSH first
        try:
            self.net.reboot_board()
        except Exception as ex:
            # Try power cycling
            log.info("SSH reboot failed, power cycling " + str(ex))
            self.power.power_cycle_board()
            time.sleep(60)
            try:
                ip = self.monitor[0].get_ip_address()
                if not ip:
                    self.monitor[0].request_ip_dhcp()
                    ip = self.monitor[0].get_ip_address()
                log.info("IP Address Found: " + str(ip))
                if ip != self.net.dutip:
                    log.info("DUT IP changed to: " + str(ip))
                    self.net.dutip = ip
                    self.driver.uri = "ip:" + ip
                    # Update config file
                    self.help.update_yaml(
                        self.configfilename,
                        "network-config",
                        "dutip",
                        ip,
                        self.board_name,
                    )
                self.net.check_board_booted()
            except Exception as ex:
                log.info("Still cannot get to board after power cycling")
                log.info("Exception: " + str(ex))
                try:
                    log.info("SSH reboot failed again after power cycling")
                    log.info("Forcing UART override on power cycle")
                    log.info("Power cycling")
                    self.power.power_cycle_board()
                    log.info("Spamming ENTER to get UART console")
                    for _ in range(60):
                        self.monitor[0]._write_data("\r\n")
                        time.sleep(0.1)

                    self.monitor[0].load_system_uart()
                    time.sleep(20)
                    log.info("IP Address: " + str(self.monitor[0].get_ip_address()))
                    self.net.check_board_booted()
                except Exception as ex:
                    raise Exception("Getting board back failed", str(ex))

    def power_cycle_to_boot(self):
        log.info("Power cycling")
        # self.monitor[0].stop_log()
        # return
        # CANNOT USE JTAG TO POWERCYCLE IT DOES NOT WORK
        # stop uart logging first
        try:
            self.monitor[0].stop_log()
            self.power.power_cycle_board()
            log.info("Waiting for boot to complete")
            results = self.monitor[0]._read_until_done_multi(
                done_strings=["U-Boot", "Starting kernel", "root@analog"], max_time=100
            )
        except Exception as ex:
            # Try to reinitialize uart and manually boot via u-boot
            log.warning("UART is unavailable.")
            log.warning(str(ex))
            # wait longer and restart board using jtag
            time.sleep(60)
            self.monitor[0].reinitialize_uart()
            self.monitor[0].start_log(logappend=True)
            self.jtag.restart_board()
            log.info("Waiting for boot to complete")
            results = self.monitor[0]._read_until_done_multi(
                done_strings=["U-Boot", "Starting kernel", "root@analog"], max_time=100
            )

        if len(results) == 1:
            raise Exception("u-boot not reached")
        elif not results[1]:
            raise Exception("u-boot menu cannot boot kernel")
        elif not results[2]:
            raise Exception("Linux not fully booting")

    def run_test(self):
        # Move BOOT.BIN, kernel and devtree to target location
        # self.boot_src.update_boot_files()

        # Start loggers
        for mon in self.monitor:
            mon.start_log()
        # Power cycle board
        self.board_reboot()

        # Check IIO context and devices
        self.driver.run_all_checks()

        # Run tests

        # Stop and collect logs
        for mon in self.monitor:
            mon.stop_log()

    def _find_boot_files(self, folder):
        if not os.path.isdir(folder):
            raise Exception("Boot files folder not found")
        files = os.listdir(folder)
        res = []
        for file in files:
            path = os.path.join(folder, file)
            filesize = os.stat(path).st_size
            if filesize <= 80:
                res.append(file)
        if len(res) != 0:
            raise Exception("Empty files:" + str(res))

        if "bootgen_sysfiles.tgz" in files:
            tar = os.path.join(folder, "bootgen_sysfiles.tgz")
            tf = tarfile.open(tar, "r:gz")
            tf.extractall(folder)
            tf.close()
            # populate again files after tgz extraction
            files = os.listdir(folder)

        targets = {
            "bit": ["system_top.bit"],
            "bootbin": ["BOOT.BIN", "soc_system.rbf"],
            "kernel": ["uImage", "Image", "zImage"],
            "dt": ["devicetree.dtb", "system.dtb", "socfpga.dtb"],
            "ext": ["extlinux.conf"],
            "scr": ["u-boot.scr"],
            "preloader": ["u-boot-with-spl.sfp"],
            "uboot": [
                "u-boot_zynq.elf",
                "u-boot_adi_zynqmp_adrv9009_zu11eg_adrv2crr_fmc.elf",
                "u-boot_xilinx_zynqmp_zcu102_revA.elf",
            ],
        }
        required = ["bootbin", "dt", "kernel"]
        found_files = {}
        for filetype in targets.keys():
            for pattern in targets[filetype]:
                if pattern in files:
                    found_files.update({filetype: os.path.join(folder, pattern)})
                    continue
            if filetype not in found_files.keys():
                if filetype in required:
                    raise Exception(f"{filetype} - {pattern} not found")
                else:
                    found_files.update({filetype: None})

        return (
            found_files["bit"],
            found_files["bootbin"],
            found_files["kernel"],
            found_files["dt"],
            found_files["ext"],
            found_files["scr"],
            found_files["preloader"],
            found_files["uboot"],
        )

    def board_reboot_auto_folder(
        self, folder, sdcard=False, design_name=None, recover=False, jtag_mode=False
    ):
        """Automatically select loading mechanism
        based on current class setup and automatically find boot
        files from target folder"""

        if design_name in ["pluto", "m2k"]:
            log.info("Firmware based device selected")
            if jtag_mode:
                raise Exception("jtag_mode not supported for firmware device")
            try:
                files = glob.glob(os.path.join(folder, "*.zip"))
            except IndexError:
                files = glob.glob(os.path.join(folder, "*.frm"))
            if not files:
                raise Exception("No files found in folder: " + folder)
            if len(files) > 1:
                raise Exception("Too manyfiles found in folder: " + folder)

            log.info(files[0])
            self.usbdev.update_firmware(files[0], device=design_name)
            time.sleep(3)
            if not self.usbdev.wait_for_usb_mount(device=design_name):
                raise Exception("Firmware update failed for: " + design_name)

        else:
            log.info("SD-Card/microblaze based device selected")
            (
                bit,
                bootbin,
                kernel,
                dt,
                ext,
                scr,
                preloader,
                uboot,
            ) = self._find_boot_files(folder)
            log.info("Found boot files:")
            for file in [bootbin, kernel, dt, bit, ext, scr, preloader, uboot]:
                if file:
                    log.info(file)
            if jtag_mode:
                self.board_reboot_jtag_uart(
                    system_top_bit_path=bit,
                    uimagepath=kernel,
                    devtreepath=dt,
                    sdcard=sdcard,
                )
            else:
                self.board_reboot_auto(
                    system_top_bit_path=bit,
                    bootbinpath=bootbin,
                    uimagepath=kernel,
                    devtreepath=dt,
                    extlinux_path=ext,
                    scr_path=scr,
                    preloader_path=preloader,
                    sdcard=sdcard,
                    recover=recover,
                )

    def board_reboot_auto(
        self,
        system_top_bit_path,
        bootbinpath,
        uimagepath,
        devtreepath,
        extlinux_path=None,
        scr_path=None,
        preloader_path=None,
        sdcard=False,
        recover=False,
    ):
        """Automatically select loading mechanism
        based on current class setup"""
        if recover:
            self.recover_board(
                system_top_bit_path=system_top_bit_path,
                bootbinpath=bootbinpath,
                uimagepath=uimagepath,
                devtreepath=devtreepath,
                extlinux_path=extlinux_path,
                scr_path=scr_path,
                preloader_path=preloader_path,
                sdcard=sdcard,
            )
        else:
            if sdcard:
                self.board_reboot_uart_net_pdu(
                    system_top_bit_path=system_top_bit_path,
                    bootbinpath=bootbinpath,
                    uimagepath=uimagepath,
                    devtreepath=devtreepath,
                    sdcard=sdcard,
                )
            elif self.usbsdmux:
                self.board_reboot_sdmux_pdu(
                    system_top_bit_path=system_top_bit_path,
                    bootbinpath=bootbinpath,
                    uimagepath=uimagepath,
                    devtreepath=devtreepath,
                    extlinux_path=extlinux_path,
                    scr_path=scr_path,
                    preloader_path=preloader_path,
                )
            else:
                self.board_reboot_uart_net_pdu(
                    system_top_bit_path=system_top_bit_path,
                    bootbinpath=bootbinpath,
                    uimagepath=uimagepath,
<<<<<<< HEAD
                    devtreepath=devtreepath,
<<<<<<< HEAD
                    extlinux_path=extlinux_path,
                    scr_path=scr_path,
                    preloader_path=preloader_path,
                    sdcard=sdcard
=======
                    sdcard=sdcard,
>>>>>>> 497fc8d (fix lint)
=======
                    devtreepath=devtreepath
>>>>>>> d19395a (Copy bootfiles from sdcard using network first)
                )

    def shutdown_powerdown_board(self):
        self.monitor[0].print_to_console = False
        ret = self.monitor[0].get_uart_command_for_linux("\r\n", "root@analog")
        try:
            if ret:
                self.monitor[0]._write_data("shutdown now")
                # wait for shutdown to complete
                time.sleep(10)
            else:
                log.error(
                    "Cannot continue command since linux is not running or not root"
                )
        except Exception as ex:
            log.error(ex)
        finally:
            # force shutdown boards via pdu
            self.power.power_down_board()


if __name__ == "__main__":
    # import pathlib

    # p = pathlib.Path(__file__).parent.absolute()
    # p = os.path.split(p)
    # p = os.path.join(p[0], "resources", "nebula-zed-fmcomms2.yaml")

    # m = manager(configfilename=p)
    # m.run_test()
    pass
