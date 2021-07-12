import os
import ipaddress
import logging
import threading
import time
import datetime
import glob
from tqdm import tqdm

import serial
from nebula.common import utils
import xmodem

log = logging.getLogger(__name__)

LINUX_SERIAL_FOLDER = "/dev/serial"
LOG_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"


class uart(utils):
    """ UART Interface Handler
            This class enables monitoring and sending commands
            over a UART interface. Monitoring is done using
            threads so monitor will not block.

        Attributes
        ----------
        address
            File descriptor of serial/COM interface
        tftpserverip
            IP address of TFTP server
        logfilename
            Filename to save output log of console
        bootargs
            Kernel bootargs
        baudrate
            Baudrate of UART interface in bits per second (default is 115200)
        print_to_console
            Print output of UART console. Output will appear in log file as well
    """

    def __init__(
        self,
        address=None,
        tftpserverip=None,
        fmc="fmcomms2",
        baudrate=115200,
        logfilename="uart.log",
        bootargs="console=ttyPS0,115200 root=/dev/mmcblk0p2 rw earlycon earlyprintk rootfstype=ext4 rootwait",
        dhcp=False,
        yamlfilename=None,
        board_name=None,
    ):
        self.com = []  # Preset incase __del__ is called before set
        self.tftpserverip = tftpserverip
        self.address = address
        self.fmc = fmc
        self.baudrate = baudrate
        self.bootargs = bootargs
        self.listen_thread_run = False
        self.logfilename = logfilename
        self.thread = None
        self.print_to_console = False
        self.dhcp = dhcp
        self.max_read_time = 30
        self.fds_to_skip = ["Digilent"]
        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )
        if not self.address:
            raise Exception(
                "UART address must be defined (under uart-config in yaml is one option)"
            )
        # Automatically set UART address
        if "auto" in self.address.lower():
            self._auto_set_address()
        self.com = serial.Serial(self.address, self.baudrate, timeout=0.5, write_timeout=5)
        self.com.reset_input_buffer()

    def __del__(self):
        log.info("Closing UART")
        if self.com:
            self.com.close()

    def reinitialize_uart(self):
        log.info("Reinitializing UART")
        if self.com:
            self.com.close()
            self.com = serial.Serial(self.address, self.baudrate, timeout=5)
            self.com.reset_input_buffer()

    def _auto_set_address(self):
        """ Try to set yaml automatically """
        if os.name in ["nt", "posix"]:
            if os.path.isdir(LINUX_SERIAL_FOLDER):
                fds = glob.glob(LINUX_SERIAL_FOLDER + "/by-id/*")
                found = False
                for fd in fds:
                    for skip in self.fds_to_skip:
                        if skip.lower() in fd.lower():
                            continue
                        print("Automatic UART selected:", fd)
                        self.address = fd
                        found = True
                        break
                    if found:
                        break
            else:
                raise Exception("No serial devices connected")

        else:
            raise Exception("Automatic UART detection is not possible in Windows yet")
        if self.com:
            self.com.close()
        self.com = serial.Serial(self.address, self.baudrate, timeout=0.5)
        self.com.reset_input_buffer()

    def start_log(self, logappend=False, force=False):
        """ Trigger monitoring with UART interface """
        if not self.listen_thread_run or force: 
            self.listen_thread_run = True
            print("STARTING UART LOG")
            log.info("Launching UART listening thread")
            if not self.print_to_console:
                log.info("UART console saving to file: " + self.logfilename)
            self.thread = threading.Thread(target=self._listen, args=(logappend,))
            self.thread.start()
        else:
            log.info("UART console is already running... Skipping setting on")

    def stop_log(self, force=False):
        """ Stop monitoring with UART interface """
        if self.listen_thread_run or force:
            self.listen_thread_run = False
            log.info("Waiting for UART reading thread")
            self.thread.join()
            log.info("UART reading thread joined")
        else:
            log.info("UART logging thread not running. Skipping setting off")

    def pipe_to_log_file(self, data, logappend=True, force=False):
        """ Write data to log file"""
        ws = "w"
        if logappend:
            ws = "a"
        if not self.listen_thread_run or force:
            with open(self.logfilename, ws) as file:
                file.writelines(data + "\n")

    def _listen(self, logappend=False):
        ws = "w"
        if logappend:
            ws = "a"
        with open(self.logfilename, ws) as file:
            while self.listen_thread_run:
                data = self._read_until_stop()
                for d in data:
                    file.writelines(d + "\n")
        log.info("UART listening thread closing")

    def _read_until_stop(self):
        buffer = []
        while self.com.in_waiting > 0:
            try:
                data = self.com.readline()
                data = str(data[:-1].decode("ASCII"))
                data = '[' + datetime.datetime.now().strftime(LOG_FORMAT) + '] ' + data
                self.pipe_to_log_file(data)
            except Exception as ex:
                log.warning("Exception occurred during data decode")
                log.warning(str(ex))
                continue
            # if self.print_to_console:
            #     print(data)
            buffer.append(data)
        return buffer

    def _write_data(self, data):
        data = data + "\n"
        bdata = data.encode()
        log.info("--------Sending Data-----------")
        log.info(bdata)
        log.info("-------------------------------")
        self.com.write(bdata)
        time.sleep(1)

    def _send_file(self, filename, address):
        self._write_data("loadx " + address)
        self._read_for_time(5)
        f = open(filename, "rb")
        total = len(f.read()) // 128
        f.close()
        with open(filename, "rb") as infile, tqdm(
            desc="Sending: " + filename,
            total=total,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            ser = self.com

            def putc(data, timeout=1):
                return ser.write(data)

            def getc(size, timeout=1):
                return ser.read(size) or None

            def callback(total_packets, success_count, error_count):
                bar.update(1)
                if False:  # total_packets % 1000 == 0:
                    print(
                        "total_packets {}, success_count {}, error_count {}, total {}".format(
                            total_packets, success_count, error_count, total
                        )
                    )

            log.info("Starting UART file transfer for: " + filename)
            modem = xmodem.XMODEM(getc, putc)
            return modem.send(infile, timeout=10, quiet=True, callback=callback)

    def update_fpga(self, skip_tftpload=False):
        """ Transfter and load system_top.bit over TFTP to system during uboot """
        if not skip_tftpload:
            cmd = "tftpboot 0x1000000 " + self.tftpserverip + ":system_top.bit"
            self._write_data(cmd)
            self._read_until_done(done_string="zynq-uboot")

        cmd = "fpga loadb 0 0x1000000 0x1"
        self._write_data(cmd)
        self._read_until_done(done_string="zynq-uboot")

    def update_dev_tree(self):
        """ Transfter devicetree over TFTP to system during uboot """
        cmd = "tftpboot 0x2A00000 " + self.tftpserverip + ":devicetree.dtb"
        self._write_data(cmd)
        self._read_until_done(done_string="zynq-uboot")

    def update_kernel(self):
        """ Transfter kernel image over TFTP to system during uboot """
        cmd = "tftpboot 0x3000000 " + self.tftpserverip + ":uImage"
        self._write_data(cmd)
        self._read_until_done(done_string="zynq-uboot")

    def update_boot_args(self):
        """ Update kernel boot arguments during uboot """
        cmd = "setenv bootargs " + self.bootargs
        self._write_data(cmd)
        self._read_until_done(done_string="zynq-uboot")

    def boot(self):
        """ Boot kernel from uboot menu """
        cmd = "bootm 0x3000000 - 0x2A00000"
        # cmd = "bootm 0x3000000 0x2000000 0x2a000000"
        self._write_data(cmd)

    def copy_reference(self, reference="BOOT.BIN.ORG",target="BOOT.BIN", done_string = "zynq_uboot"):
        """ Using reference files """
        cmd = "fatload mmc 0 0x8000000 {}".format(reference)
        self._write_data(cmd)
        self._read_until_done(done_string)
        cmd = "fatwrite mmc 0 0x8000000 "+target+" ${filesize}"
        self._write_data(cmd)
        self._read_until_done(done_string)

    def load_system_uart_copy_to_sdcard(
        self, bootbin, devtree_filename, kernel_filename
    ):
        """ Load complete system (BOOT.BIN, devtree, kernel) during uboot from UART (XMODEM)
        and to SD card
        """
        if "uImage" in str(kernel_filename):
            filenames = ["BOOT.BIN","uImage","devicetree.dtb"]
            done_string = "zynq-uboot"
        else:
            filenames = ["BOOT.BIN","Image","system.dtb"]
            done_string = "ZynqMP"
        source_fn = [bootbin, kernel_filename, devtree_filename]
        for i, target in enumerate(filenames):
            log.info("Copying over: "+source_fn[i])
            self._send_file(source_fn[i], "0x8000000")
            self._read_until_done(done_string)
            log.info("Writing over: "+target)
            cmd = "fatwrite mmc 0 0x8000000 "+target+" ${filesize}"
            self._write_data(cmd)
            self._read_until_done(done_string)

    def _attemp_login(self, username, password):
        # Do login
        logged_in = False
        cmd = username
        self._write_data(cmd)
        data = self._read_for_time(period=5)
        # using root username automatically responded with Login Incorrect
        for d in data:
            if isinstance(d, list):
                for c in d:
                    c = c.replace("\r", "")
                    if "Login incorrect" in c or "login:" in c:
                        log.info("Login attempt incorrect")
                        return False
            else:
                c = d.replace("\r", "")
                if "Login incorrect" in c or "login:" in c:
                    log.info("Login attempt incorrect")
                    return False
        cmd = password
        self._write_data(cmd)
        data = self._read_for_time(period=2)
        # Check
        cmd = ""
        self._write_data(cmd)
        data = self._read_for_time(period=1)
        for d in data:
            if isinstance(d, list):
                for c in d:
                    c = c.replace("\r", "")
                    if username+"@" in c or "#" in c:
                        log.info("Logged in success")
                        logged_in = True
        return logged_in

    def _check_for_login(self):
        logged_in=False
        try:
            for _ in range(2):  # Check at least twice
                cmd = ""
                self._write_data(cmd)
                data = self._read_for_time(period=1)
                needs_login = False
                for d in data:
                    if isinstance(d, list):
                        for c in d:
                            c = c.replace("\r", "")
                            log.info(c)
                            if "login:" in c:
                                needs_login = True
            
            if needs_login:
                # Do login
                if self._attemp_login("root","analog"):
                    return True
                else:
                    log.info("Attempting to login as analog")
                    logged_in = self._attemp_login("analog","analog")
            else:
                return True
        except serial.serialutil.SerialTimeoutException as e:
            log.info(str(e))
        return logged_in

    def set_ip_static(self, address, nic="eth0"):
        restart = False
        if self.listen_thread_run:
            restart = True
            self.stop_log()
        # Check if we need to login to the console
        if not self._check_for_login():
            raise Exception("Console inaccessible due to login failure")
        cmd = "/usr/local/bin/enable_static_ip.sh " + address + " " + nic
        self._write_data(cmd)
        if restart:
            data = self._read_for_time(period=1)
            self.start_log(logappend=True)

    def request_ip_dhcp(self, nic="eth0"):
        restart = False
        if self.listen_thread_run:
            restart = True
            self.stop_log()
        # Check if we need to login to the console
        if not self._check_for_login():
            raise Exception("Console inaccessible due to login failure")
        cmd = "/usr/local/bin/enable_dhcp.sh"
        self._write_data(cmd)
        data = self._read_for_time(period=1)
        cmd = "dhclient -r " + nic
        self._write_data(cmd)
        data = self._read_for_time(period=1)
        cmd = "dhclient " + nic
        self._write_data(cmd)
        data = self._read_for_time(period=1)
        if restart:
            self.start_log(logappend=True)

    def get_uart_command_for_linux(self, cmd, findstring):
        """ Write command to UART and wait for a specific string """
        restart = False
        if self.listen_thread_run:
            restart = True
            self.stop_log()
        # Check if we need to login to the console
        if not self._check_for_login():
            raise Exception("Console inaccessible due to login failure")
        self._write_data(cmd)
        data = self._read_for_time(period=1)
        if isinstance(data, list) and isinstance(data[0], list):
            data = data[0]
        data = data[1:]  # Remove command itself
        if restart:
            self.start_log(logappend=True)
        for d in data:
            if isinstance(d, list):
                for c in d:
                    log.info("command response: "+c)
                    c = c.replace("\r", "")
                    try:
                        if len(findstring) == 0:
                            if (len(c) > 0) and (c != cmd) and (cmd not in c):
                                return c
                        elif findstring in c:
                            log.info("Found substring: " + str(c))
                            return c
                    except:
                        continue
            else:
                log.info("command response: "+d)
                try:
                    if len(findstring) == 0:
                        if (len(d) > 0) and (d != cmd) and (cmd not in d):
                            return d
                    elif findstring in d:
                        log.info("Found substring: " + str(d))
                        return d
                except:
                    continue
        return None

    def get_local_mac_usbdev(self):
        """ Read MAC Address of enumerated NIC on host from DUT (Pluto/M2K only) """
        cmd = "cat /www/index.html | grep '00:' | grep -v `cat /sys/class/net/usb0/address` | sed 's/ *<[^>]*> */ /g'"
        return self.get_uart_command_for_linux(cmd, "00")

    def get_ip_address(self):
        """ Read IP address of DUT using ip command from UART """
        # cmd = "ip -4 addr | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v 127"
        cmd = "ip -4 addr | grep -v 127 | awk '$1 == \"inet\" {print $2}' | awk -F'/' '{print $1}'"
        restart = False
        if self.listen_thread_run:
            restart = True
            self.stop_log()
        # Check if we need to login to the console
        if not self._check_for_login():
            raise Exception("Console inaccessible due to login failure")
        self._write_data(cmd)
        data = self._read_for_time(period=1)
        if restart:
            self.start_log(logappend=True)
        for d in data:
            if isinstance(d, list):
                for c in d:
                    c = c.replace("\r", "")
                    try:
                        ipaddress.ip_address(c)
                        log.info("Found IP: " + str(c))
                        return c
                    except:
                        continue
            else:
                try:
                    ipaddress.ip_address(d)
                    log.info("Found IP: " + str(d))
                    return d
                except:
                    continue
        return None

    def _read_for_time(self, period):
        data = []
        for _ in range(period):
            data.append(self._read_until_stop())
            time.sleep(1)
        return data

    def _read_until_done_multi(self, done_strings=["done","done"], max_time=None):
        if self.listen_thread_run:
            restart_log = True
            self.stop_log()
        else:
            restart_log = False
        data = []
        mt = max_time or self.max_read_time
        founds = []
        lastd = ''
        for indx, done_string in enumerate(done_strings):
            log.info("Looking for: "+done_string)
            for t in range(mt):
                breakbreak = False
                data = self._read_until_stop()
                if isinstance(data, list):
                    for d in data:
                        d = lastd+d
                        lastd = ''
                        if done_string in d:
                            log.info(done_string+" found in data")
                            founds.append(True)
                            if indx == len(done_strings)-1:
                                if restart_log:
                                    self.start_log()
                                return founds
                            lastd = d[d.find(done_string):]
                            breakbreak = True
                            break
                    if breakbreak:
                        break
                elif done_string in lastd+data:
                    log.info(done_string+" found in data")
                    founds.append(True)
                    if indx == len(done_strings)-1:
                        if restart_log:
                            self.start_log()
                        return founds
                    else:
                        lastd = lastd+data
                        lastd = lastd[lastd.find(done_string):]
                        break
                else:
                    lastd = ''
                    log.info("Still waiting")
                time.sleep(1)
            if t == mt-1:
                log.info(done_string+" not found in time")
                if restart_log:
                    self.start_log()
                founds.append(False)
                return founds
        # if restart_log:
        #     self.start_log()
        # founds.append(False)
        # return founds


    def _read_until_done(self, done_string="done", max_time=None):
        if self.listen_thread_run:
            restart_log = True
            self.stop_log()
        else:
            restart_log = False
        data = []
        mt = max_time or self.max_read_time
        for _ in range(mt):
            data = self._read_until_stop()
            if isinstance(data, list):
                for d in data:
                    if done_string in d:
                        log.info("done found in data")
                        if restart_log:
                            self.start_log()
                        return True
            elif done_string in data:
                log.info("done found in data")
                if restart_log:
                    self.start_log()
                return True
            else:
                log.info("Still waiting")
            time.sleep(1)
        if restart_log:
            self.start_log()
        return False

    def _check_for_string_console(self, console_out, string):
        for d in console_out:
            if not isinstance(d, list):
                d = [d]
            if isinstance(d, list):
                for c in d:
                    c = c.replace("\r", "")
                    log.info("RAW: "+str(c)+" | Looking for: "+string)
                    if string in c:
                        return True
        return False

    def _wait_for_boot_complete_linaro(self, done_string="Welcome to Linaro 14.04"):
        """ Wait for Linux to boot by waiting for Welcome message """
        restart = False
        if self.listen_thread_run:
            restart = True
            self.stop_log()
        out = self._read_until_done(done_string=done_string, max_time=60)
        if restart:
            self.start_log(logappend=True)
        return out

    def _enter_uboot_menu_from_power_cycle(self):
        log.info("Spamming ENTER to get UART console")
        # stop_at_done = False
        if self.listen_thread_run:
           restart = True
           self.stop_log()
        else:
            restart = False
        for _ in range(30):
            self._write_data("\r\n")
            data = self._read_for_time(1)
            # Check uboot console reached
            if self._check_for_string_console(data, "zynq-uboot"):
                log.info("u-boot menu reached")
                if restart:
                    self.start_log()
                return True
            elif self._check_for_string_console(data, "ZynqMP"):
                log.info("u-boot menu reached")
                if restart:
                    self.start_log()
                return True
            time.sleep(0.1)
        log.info("u-boot menu not reached")
        if restart:
            self.start_log()
        return False

    def load_system_uart_from_tftp(self):
        """ Load complete system (bitstream, devtree, kernel) during uboot from TFTP"""

        restart = False
        if self.listen_thread_run:
            restart = True
            self.stop_log()

        # Flush
        self._read_until_stop()

        cmd = "setenv autoload no"
        self._write_data(cmd)
        self._read_for_time(period=3)
        cmd = "dhcp"
        self._write_data(cmd)
        self._read_until_done(done_string="zynq-uboot")
        cmd = "echo board IP ${ipaddr}"
        self._write_data(cmd)
        self._read_until_done(done_string="zynq-uboot")
        cmd = "setenv serverip 192.168.86.39"
        self._write_data(cmd)
        self._read_until_done(done_string="zynq-uboot")

        self.update_fpga()
        time.sleep(1)
        self.update_dev_tree()
        time.sleep(1)
        self.update_kernel()
        time.sleep(1)
        self.update_boot_args()
        time.sleep(1)
        self.boot()
        self._read_for_time(period=5)

        if restart:
            self.start_log(logappend=True)

    def load_system_uart(
        self, system_top_bit_filename, devtree_filename, kernel_filename
    ):
        """ Load complete system (bitstream, devtree, kernel) during uboot from UART (XMODEM)"""
        self._send_file(system_top_bit_filename, "0x1000000")
        self.update_fpga(skip_tftpload=True)
        self._send_file(devtree_filename, "0x2A00000")
        self._send_file(kernel_filename, "0x3000000")
        self.update_boot_args()
        self.boot()

    def update_boot_files_from_running(
        self, system_top_bit_filename, devtree_filename, kernel_filename
    ):
        """ Load complete system (bitstream, devtree, kernel) during uboot from UART (XMODEM) from a running system """
        # Spam enter while reboot to get to u-boot menu
        log.info("Spamming ENTER to get UART console")
        for _ in range(60):
            self._write_data("\r\n")
            time.sleep(0.1)
        log.info("Loading boot files from UART")
        # Boot board
        self.load_system_uart(
            system_top_bit_filename=system_top_bit_filename,
            devtree_filename=devtree_filename,
            kernel_filename=kernel_filename,
        )


if __name__ == "__main__":

    # import pathlib

    # p = pathlib.Path(__file__).parent.absolute()
    # p = os.path.split(p)
    # p = os.path.join(p[0], "resources", "nebula-zed.yaml")

    # u = uart(yamlfilename=p)
    # u.start_log()
    # time.sleep(10)
    # u.stop_log()
    # u = []
    pass
