import os
import time
import subprocess
import serial
import yaml


class uart:
    def __init__(self, address='/dev/ttyACM0', fmc="fmcomms2"):
        self.ip = "192.168.86.220"
        self.address = address
        self.fmc = fmc
        self.com = serial.Serial(address, 115200, timeout=0.5)
        self.com.reset_input_buffer()

    def __del__(self):
        print("Closing")
        self.com.close()

    def read_until_done(self):
        for k in range(30):
            data = self.com.readline()
            data = str(data[:-1].decode('ASCII'))
            print(data)
            if data.find("done")>-1:
                print("DONE")
                return
            time.sleep(1)

    def read_until_stop(self):
        buffer = []
        while self.com.in_waiting > 0:
            data = self.com.readline()
            data = str(data[:-1].decode('ASCII'))
            print(data)
            buffer.append(data)
        return buffer

    def write_data(self, data):
        data = data+"\n"
        bdata = data.encode()
        print("-------------------")
        print(bdata)
        print("-------------------")
        self.com.write(bdata)
        time.sleep(4)

    def update_fpga(self):
        cmd = "tftpboot 0x1000000 "+self.ip+":system_top.bit"
        self.write_data(cmd)
        self.read_until_done()

        cmd = "fpga loadb 0 0x1000000 0x1"
        self.write_data(cmd)
        self.read_until_stop()

    def update_dev_tree(self):
        cmd = "tftpboot 0x2A00000 "+self.ip+":devicetree.dtb"
        self.write_data(cmd)
        self.read_until_done()

    def update_kernel(self):
        cmd = "tftpboot 0x3000000 "+self.ip+":uImage"
        self.write_data(cmd)
        self.read_until_done()

    def update_boot_args(self):
        cmd = "setenv bootargs console=ttyPS0,115200 root=/dev/mmcblk0p2 rw earlycon rootfstype=ext4 rootwait"
        self.write_data(cmd)

    def boot(self):
        cmd = "bootm 0x3000000 - 0x2A00000"
        self.write_data(cmd)

    def read_for_time(self,period):
        for k in range(period):
            data = u.read_until_stop()
            time.sleep(1)

def setup_uart():
    # Read yaml
    stream = open("fpga-debug.yaml", 'r')
    configs = yaml.safe_load(stream)
    board = configs.keys()[0]
    u = uart(address=board['uart'])

if __name__ == "__main__":
    u = uart()

    u.update_fpga()
    u.update_dev_tree()
    u.update_kernel()
    u.update_boot_args()
    u.boot()
    u.read_for_time(10)

    u = []
