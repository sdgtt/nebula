import logging
import os
import threading
import time
import ipaddress

import serial
from nebula.common import utils

logging.basicConfig(level=logging.INFO)


class uart(utils):
    """ UART Interface Handler
            This class enables monitoring and sending commands
            over a UART interface. Monitoring is done using
            threads so monitor will not block.
    """

    def __init__(
        self,
        address="/dev/ttyACM0",
        tftpserverip="192.168.86.220",
        fmc="fmcomms2",
        baudrate=115200,
        logfilename="uart.log",
        bootargs="console=ttyPS0,115200 root=/dev/mmcblk0p2 rw earlycon rootfstype=ext4 rootwait",
        yamlfilename=None,
    ):
        self.tftpserverip = tftpserverip
        self.address = address
        self.fmc = fmc
        self.baudrate = baudrate
        self.listen_thread_run = True
        self.logfilename = logfilename
        self.thread = None
        self.print_to_console = True
        if yamlfilename:
            self.update_defaults_from_yaml(yamlfilename, __class__.__name__)
        self.com = serial.Serial(self.address, self.baudrate, timeout=0.5)
        self.com.reset_input_buffer()

    def __del__(self):
        logging.info("Closing UART")
        self.com.close()

    def start_log(self, logappend=False):
        """ Trigger monitoring with UART interface """
        self.listen_thread_run = True
        logging.info("Launching UART listening thread")
        self.thread = threading.Thread(target=self.listen, args=(logappend,))
        self.thread.start()

    def stop_log(self):
        """ Stop monitoring with UART interface """
        self.listen_thread_run = False
        logging.info("Waiting for UART reading thread")
        self.thread.join()
        logging.info("UART reading thread joined")

    def listen(self, logappend=False):
        ws = "w"
        if logappend:
            ws = "a"
        file = open(self.logfilename, ws)
        while self.listen_thread_run:
            data = self.read_until_stop()
            for d in data:
                file.writelines(d + "\n")
        file.close()
        logging.info("UART listening thread closing")

    def read_until_stop(self):
        buffer = []
        while self.com.in_waiting > 0:
            try:
                data = self.com.readline()
                data = str(data[:-1].decode("ASCII"))
            except Exception as ex:
                logging.warning("Exception occurred during data decode")
                logging.warning(ex)
                continue
            if self.print_to_console:
                print(data)
            buffer.append(data)
        return buffer

    def write_data(self, data):
        data = data + "\n"
        bdata = data.encode()
        logging.info("--------Sending Data-----------")
        logging.info(bdata)
        logging.info("-------------------------------")
        self.com.write(bdata)
        time.sleep(4)

    def update_fpga(self):
        """ Transfter and load system_top.bit over TFTP to system during uboot """
        cmd = "tftpboot 0x1000000 " + self.tftpserverip + ":system_top.bit"
        self.write_data(cmd)
        self.read_until_done()

        cmd = "fpga loadb 0 0x1000000 0x1"
        self.write_data(cmd)
        self.read_until_stop()

    def update_dev_tree(self):
        """ Transfter devicetree over TFTP to system during uboot """
        cmd = "tftpboot 0x2A00000 " + self.tftpserverip + ":devicetree.dtb"
        self.write_data(cmd)
        self.read_until_done()

    def update_kernel(self):
        """ Transfter kernel image over TFTP to system during uboot """
        cmd = "tftpboot 0x3000000 " + self.tftpserverip + ":uImage"
        self.write_data(cmd)
        self.read_until_done()

    def update_boot_args(self):
        """ Update kernel boot arguments during uboot """
        cmd = "setenv bootargs " + self.bootargs
        self.write_data(cmd)

    def boot(self):
        """ Boot kernel during uboot """
        cmd = "bootm 0x3000000 - 0x2A00000"
        self.write_data(cmd)

    def get_ip_address(self):
        cmd = "ip -4 addr | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | grep -v 127"
        restart = True
        if self.listen_thread_run:
            restart = True
            self.stop_log()
        self.write_data(cmd)
        data = self.read_for_time(period=3)
        if restart:
            self.start_log(logappend=True)
        for d in data:
            if isinstance(d,list):
                for c in d:
                    c = c.replace('\r','')
                    try:
                        ipaddress.ip_address(c)
                        print("Found IP",c)
                        return c
                    except:
                        continue
            else:
                try:
                    ipaddress.ip_address(d)
                    print("Found IP",d)
                    return d
                except:
                    continue

    def read_for_time(self, period):
        data = []
        for k in range(period):
            data.append(self.read_until_stop())
            time.sleep(1)
        return data

    def load_system_uart(self):
        """ Load complete system (bitstream, devtree, kernel) during uboot """
        self.update_fpga()
        self.update_dev_tree()
        self.update_kernel()
        self.update_boot_args()
        self.boot()


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
