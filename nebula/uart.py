import logging
import os
import threading
import time

import serial
import yaml

logging.basicConfig(level=logging.INFO)


class uart:
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
            self.update_defaults_from_yaml(yamlfilename)
        self.com = serial.Serial(self.address, self.baudrate, timeout=0.5)
        self.com.reset_input_buffer()

    def update_defaults_from_yaml(self, filename):
        stream = open(filename, "r")
        configs = yaml.safe_load(stream)
        stream.close()
        if "uart-config" not in configs:
            raise Exception("uart-config field not in yaml config file")
        configsList = configs["uart-config"]
        for config in configsList:
            for k in config:
                if not hasattr(self, k):
                    raise Exception("Unknown field in uart yaml " + k)
                setattr(self, k, config[k])

    def __del__(self):
        logging.info("Closing UART")
        self.com.close()

    def start_log(self):
        """ Trigger monitoring with UART interface """
        self.listen_thread_run = True
        logging.info("Launching UART listening thread")
        self.thread = threading.Thread(target=self.listen, args=())
        self.thread.start()

    def stop_log(self):
        """ Stop monitoring with UART interface """
        self.listen_thread_run = False
        logging.info("Waiting for UART reading thread")
        self.thread.join()
        logging.info("UART reading thread joined")

    def listen(self):
        file = open(self.logfilename, "w")
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
