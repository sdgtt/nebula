import glob
import logging
import os
import tarfile
import time

import nebula.common as common
import nebula.errors as ne
import nebula.helper as helper
import yaml
from nebula.driver import driver
from nebula.jtag import jtag
from nebula.netconsole import netconsole
from nebula.network import network
from nebula.pdu import pdu
from nebula.tftpboot import tftpboot
from nebula.uart import uart
from nebula.usbdev import usbdev

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class manager:
    """Board Manager"""

    def __init__(
        self, monitor_type="uart", configfilename=None, board_name=None, extras=None
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

        if "pdu-config" not in configs:
            configfilename = None
        else:
            configfilename = self.configfilename
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
                                vivado_version=extras,
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
                                vivado_version=extras,
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

        self.help = helper.helper()
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
            if not os.path.exists(filename):
                raise Exception(filename + " not found or does not exist")

    def copy_reference_from_sdcard(self, bootbinpath, uimagepath, devtreepath):
        target = uimagepath.split("/")[1].rstrip()
        if "uImage" in str(uimagepath):
            ref = "zynq-common/" + str(target)
        else:
            ref = "zynqmp-common/" + str(target)
        self.monitor[0].copy_reference(ref, target)

        if self.boot_subfolder is not None:
            ref = self.reference_boot_folder + "/" + str(self.boot_subfolder)
        else:
            ref = self.reference_boot_folder
        target = bootbinpath.split("/")[1].rstrip()
        ref = ref + "/" + str(target)
        self.monitor[0].copy_reference(ref, target)

        if self.devicetree_subfolder is not None:
            ref = self.reference_boot_folder + "/" + str(self.devicetree_subfolder)
        else:
            ref = self.reference_boot_folder
        target = devtreepath.split("/")[1].rstrip()
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

    @_release_thread_lock
    def recover_board(
        self, system_top_bit_path, bootbinpath, uimagepath, devtreepath, sdcard=False
    ):
        """Recover boards with UART, PDU, JTAG, and Network are available"""
        self._check_files_exist(
            system_top_bit_path, bootbinpath, uimagepath, devtreepath
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
            try:
                # Power cycle
                log.info("SSH reboot failed again after power cycling")
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
                    raise ne.LinuxNotReached

                if self.tftp:
                    # Move files to correct position for TFTP
                    # self.monitor[0].load_system_uart_from_tftp()

                    # Load boot files over tftp
                    self.monitor[0].load_system_uart_from_tftp()

                else:
                    try:
                        if sdcard:
                            log.info("Copying reference from sdcard")
                            self.copy_reference_from_sdcard(
                                bootbinpath, uimagepath, devtreepath
                            )
                            self.monitor[0]._write_data("\r\n")
                            self.monitor[0]._write_data("boot")
                        else:
                            # Load boot files via uart
                            log.info("Sending reference via uart")
                            self.monitor[0].load_system_uart(
                                system_top_bit_filename=system_top_bit_path,
                                kernel_filename=uimagepath,
                                devtree_filename=devtreepath,
                            )
                    except Exception as ex:
                        log.warning("Error copying reference.")
                        log.warning(str(ex))

                log.info("Waiting for boot to complete")

                # Verify linux is reached
                result = self.monitor[0]._read_until_done(
                    done_string="root@analog", max_time=100
                )

                if not result:
                    # raise Exception("Linux not fully booting")
                    raise ne.LinuxNotReached

                log.info("Linux fully booted")

                # Check is networking is working
                self.network_check()

                print("Home sweet home")
                self.monitor[0].stop_log()

            # JTAG RECOVERY
            except Exception:
                self.board_reboot_jtag_uart(
                    bootbinpath, uimagepath, devtreepath, sdcard
                )

    @_release_thread_lock
    def board_reboot_jtag_uart(
        self, bootbinpath, uimagepath, devtreepath, sdcard=False
    ):
        """Reset board and load fsbl, uboot, bitstream, and kernel
        over JTAG. Then over UART boot
        """
        # self.monitor[0].start_log()
        log.info("Resetting and looking DDR with boot files")
        # self.jtag.full_boot()
        # Check if u-boot loads first
        # log.info("Resetting with JTAG and checking if u-boot is reachable")
        # self.jtag.restart_board()
        # do a power cylcle rather than jtag reboot to make sure jtag devices are working
        log.info("Resetting with JTAG and checking if u-boot is reachable")
        self.jtag.restart_board()
        if self.monitor[0]._enter_uboot_menu_from_power_cycle():
            log.info("u-boot accessible after JTAG reset")
            self.jtag.restart_board()
            log.info("Taking over UART control")
            self.monitor[0]._enter_uboot_menu_from_power_cycle()
        else:
            log.info("u-boot not reachable, manually loading u-boot over JTAG")
            self.jtag.boot_to_uboot()
            log.info("Taking over UART control")
            self.monitor[0]._enter_uboot_menu_from_power_cycle()

        # Get SD card file directory
        if not sdcard:
            # Copy over and write to disk
            log.info("Copying boot files over UART to SD card")
            self.monitor[0].load_system_uart_copy_to_sdcard(
                bootbinpath, devtreepath, uimagepath
            )
        else:
            self.copy_reference_from_sdcard(bootbinpath, uimagepath, devtreepath)

        # self.jtag.load_post_uboot_files()
        # self.monitor[0].update_boot_args()
        # self.monitor[0].boot()
        # self.monitor[0].load_system_uart(
        #     system_top_bit_filename="system_top.bit",
        #     kernel_filename="uImage",
        #     devtree_filename="devicetree.dtb",
        # )
        # power cycle board
        self.power_cycle_to_boot()

        # Check is networking is working
        self.network_check()

        self.monitor[0].stop_log()

    @_release_thread_lock
    def board_reboot_uart_net_pdu(
        self, system_top_bit_path, bootbinpath, uimagepath, devtreepath
    ):
        """Manager when UART, PDU, and Network are available"""
        self._check_files_exist(
            system_top_bit_path, bootbinpath, uimagepath, devtreepath
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
            self.net.update_boot_partition(
                bootbinpath=bootbinpath, uimagepath=uimagepath, devtreepath=devtreepath
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

        if "BOOT.BIN" not in files:
            raise Exception("BOOT.BIN not found")
        if "devicetree.dtb" not in files:
            if "system.dtb" not in files:
                raise Exception("Device tree not found")
            else:
                dt = "system.dtb"
        else:
            dt = "devicetree.dtb"
        if "uImage" not in files:
            if "Image" not in files:
                raise Exception("kernel not found")
            else:
                kernel = "Image"
        else:
            kernel = "uImage"
        if "system_top.bit" not in files:
            if "bootgen_sysfiles.tgz" not in files:
                raise Exception("system_top.bit not found")
            else:
                tar = os.path.join(folder, "bootgen_sysfiles.tgz")
                tf = tarfile.open(tar, "r:gz")
                tf.extractall(folder)
                tf.close()
                files2 = os.listdir(folder)
                if "system_top.bit" not in files2:
                    raise Exception("system_top.bit not found")

        kernel = os.path.join(folder, kernel)
        dt = os.path.join(folder, dt)
        bootbin = os.path.join(folder, "BOOT.BIN")
        bit = os.path.join(folder, "system_top.bit")
        return (bootbin, kernel, dt, bit)

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
            files = glob.glob(os.path.join(folder, "*.zip"))
            if not files:
                raise Exception("No zip files found in folder: " + folder)
            if len(files) > 1:
                raise Exception("Too many zip files found in folder: " + folder)

            self.usbdev.update_firmware(files[0], device=design_name)
            time.sleep(3)
            if not self.usbdev.wait_for_usb_mount(device=design_name):
                raise Exception("Firmware update failed for: " + design_name)

        else:
            log.info("SD-Card/microblaze based device selected")
            (bootbin, kernel, dt, bit) = self._find_boot_files(folder)
            print(bootbin, kernel, dt, bit)
            if jtag_mode:
                self.board_reboot_jtag_uart(
                    system_top_bit_path=bit,
                    bootbinpath=bootbin,
                    uimagepath=kernel,
                    devtreepath=dt,
                )
            if not recover:
                self.board_reboot_uart_net_pdu(
                    system_top_bit_path=bit,
                    bootbinpath=bootbin,
                    uimagepath=kernel,
                    devtreepath=dt,
                )
            else:
                self.recover_board(
                    system_top_bit_path=bit,
                    bootbinpath=bootbin,
                    uimagepath=kernel,
                    devtreepath=dt,
                    sdcard=sdcard,
                )

    def board_reboot_auto(
        self, system_top_bit_path, bootbinpath, uimagepath, devtreepath, recover=False
    ):
        """Automatically select loading mechanism
        based on current class setup"""
        self.board_reboot_uart_net_pdu(
            system_top_bit_path=system_top_bit_path,
            bootbinpath=bootbinpath,
            uimagepath=uimagepath,
            devtreepath=devtreepath,
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
