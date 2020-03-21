#!/usr/bin/python
# import nebula

import argparse
import os
import subprocess
import time

from pyfiglet import Figlet

f = Figlet(font="slant")
print(f.renderText("Nebula"))


class builder:
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
        # return output.decode("utf-8")

    def cmake_build(self, dir):
        os.chdir(dir)
        self.shell_out("mkdir build")
        os.chdir("build")
        self.shell_out("cmake ..")
        self.shell_out("make -j4")

    def add_vivado_path(self, dir):
        # Get version of vivado needed
        try:
            file = open("projects/scripts/adi_project_xilinx.tcl", "rt")
        except FileNotFoundError:
            file = open("projects/scripts/adi_project.tcl", "rt")
        for line in file:
            if "set REQUIRED_VIVADO_VERSION" in line:
                vivado_version = line.split()[2].replace('"', "")
                vivado = "/opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
                if not os.path.isfile(vivado):
                    raise Exception(
                        "Required vivado version not found: " + vivado_version
                    )
                return vivado
        raise Exception("REQUIRED_VIVADO_VERSION not found in repo")

    def uboot_build(self, dir, def_config):
        os.chdir(dir)
        # vivado = add_vivado_path(dir)
        vivado_version = "2018.2"
        vivado = ". /opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
        cmd = vivado
        cmd += "; export ARCH=arm; export CROSS_COMPILE=arm-linux-gnueabihf-"
        cmd += "; make distclean; make clean"
        cmd += "; make " + def_config
        cmd += "; make -j" + str(os.cpu_count())
        self.shell_out2(cmd)

    def hdl_build(self, dir, project, board):
        os.chdir(dir)
        vivado = self.add_vivado_path(dir)
        args = "--no-print-directory"
        cmd = vivado + "; make " + args + " -C projects/" + project + "/" + board
        self.shell_out2(cmd)

    def linux_tools_map(self, branch, arch):
        if branch >= 2018.1:
            CC = "arm-linux-gnueabihf-"
        else:
            CC = "arm-xilinx-linux-gnueabi-"
        return CC

    def linux_build(self, dir):
        os.chdir(dir)
        # vivado = add_vivado_path(dir)
        vivado_version = "2018.2"
        vivado = ". /opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
        cmd = vivado
        cmd += "; export ARCH=arm; export CROSS_COMPILE=arm-linux-gnueabihf-"
        cmd += "; make distclean; make clean"
        cmd += "; make zynq_xcomm_adv7511_defconfig"
        cmd += "; make -j" + str(os.cpu_count()) + " UIMAGE_LOADADDR=0x8000 uImage"
        self.shell_out2(cmd)

    def build_repo(self, repo, project=None, board=None, def_config=None):
        pwd = os.getcwd()
        if repo in ["libiio", "gr-iio", "libad9361", "iio-oscilloscope"]:
            self.cmake_build(repo)
        elif repo == "hdl":
            self.hdl_build(repo, project, board)
        elif repo == "u-boot-xlnx":
            self.uboot_build(repo, def_config)
        elif repo == "linux":
            self.linux_build(repo)
        else:
            print("Unknown ADI repo, not building")
        os.chdir(pwd)

    def analog_clone(self, repo, branch="master", githuborg="analogdevicesinc"):
        cmd = (
            "git clone -b "
            + branch
            + " https://github.com/"
            + githuborg
            + "/"
            + repo
            + ".git"
        )
        if repo in ["linux", "u-boot-xlnx"]:
            cmd += " --depth=1"
        self.shell_out(cmd)

    def analog_clone_build(
        self,
        repo,
        branch="master",
        project=None,
        board=None,
        def_config=None,
        githuborg=None,
    ):
        if "u-boot" in repo:
            self.analog_clone(repo, branch, githuborg="Xilinx")
        else:
            self.analog_clone(repo, branch)
        time.sleep(1)
        self.build_repo(repo, project=project, board=board, def_config=def_config)


if __name__ == "__main__":
    b = builder()
    b.analog_clone_build("u-boot-xlnx", "2018_R2")
    # b.analog_clone_build("linux", "2018_R2")
