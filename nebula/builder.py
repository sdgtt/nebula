#!/usr/bin/python

import os
import shutil
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
                vivado = ". " + vivado
                return vivado
        raise Exception("REQUIRED_VIVADO_VERSION not found in repo")

    def uboot_build(self, dir, def_config=None, branch="2018_R2", board="zed"):
        os.chdir(dir)
        if not def_config:
            def_config = self.def_config_map(board)
            cc, arch, vivado_version = self.linux_tools_map(branch, board)
        else:
            cc, arch, vivado_version = self.linux_tools_map(branch, def_config)
        vivado = ". /opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
        cmd = vivado
        cmd += "; export ARCH=" + arch + "; export CROSS_COMPILE=" + cc
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

    def def_config_map(self, board):
        if "zcu102" in board.lower():
            def_conf = "xilinx_zynqmp_zcu102_rev1_0_defconfig"
        elif "zc706" in board.lower():
            def_conf = "zynq_zc706_defconfig"
        elif "zc702" in board.lower():
            def_conf = "zynq_zc702_defconfig"
        elif "zed" in board.lower():
            def_conf = "zynq_zed_defconfig"
        else:
            raise Exception("Unsupported board")
        return def_conf

    def linux_tools_map(self, branch, board):
        if branch == "2018_R2":
            vivado = "2018.2"
        elif branch == "2019_R1":
            vivado = "2018.3"
        else:
            raise Exception("Unsupported branch")
        if "zcu102" in board.lower():
            arch = "arm64"
            cc = "aarch64-linux-gnu-"
        elif (
            "zed" in board.lower()
            or "zc702" in board.lower()
            or "zc706" in board.lower()
        ):
            arch = "arm"
            if float(vivado) >= 2018.1:
                cc = "arm-linux-gnueabihf-"
            else:
                cc = "arm-xilinx-linux-gnueabi-"
        else:
            raise Exception("Unsupported board")
        return (cc, arch, vivado)

    def linux_build(self, dir, branch="2018_R2", board="zed"):
        os.chdir(dir)
        cc, arch, vivado_version = self.linux_tools_map(branch, board)
        vivado = ". /opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
        cmd = vivado
        cmd += "; export ARCH=" + arch + "; export CROSS_COMPILE=" + cc
        cmd += "; make distclean; make clean"
        if "64" in arch:
            cmd += "; make adi_zynqmp_defconfig"
            cmd += "; make -j" + str(os.cpu_count()) + " UIMAGE_LOADADDR=0x8000 Image"
        else:
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
            self.uboot_build(repo, def_config, board=board)
        elif repo == "linux":
            self.linux_build(repo, board=board)
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

    def create_zynq_bif(self, hdf_filename, build_dir):
        pwd = os.getcwd()
        os.chdir(build_dir)
        ### Create zynq.bif file used by bootgen
        filename = "zynq.bif"
        hdf_filename = os.path.basename(hdf_filename)
        f = open(filename, "w+")
        f.write("the_ROM_image:\n")
        f.write("{\n")
        f.write("[bootloader] fsbl.elf\n")
        f.write("system_top.bit\n")
        f.write("u-boot.elf\n")
        f.write("}\n")
        f.close()
        os.chdir(pwd)

    def create_fsbl_project(self, hdf_filename, build_dir):
        pwd = os.getcwd()
        os.chdir(build_dir)
        ### Create create_fsbl_project.tcl file used by xsdk to create the fsbl
        hdf_filename = os.path.basename(hdf_filename)
        filename = "create_fsbl_project.tcl"
        f = open(filename, "w+")
        f.write("hsi open_hw_design " + hdf_filename + "\n")
        f.write(
            "set cpu_name [lindex [hsi get_cells -filter {IP_TYPE==PROCESSOR}] 0]\n"
        )
        f.write("sdk setws ./build/sdk\n")
        f.write("sdk createhw -name hw_0 -hwspec " + hdf_filename + "\n")
        f.write(
            "sdk createapp -name fsbl -hwproject hw_0 -proc $cpu_name -os standalone -lang C -app {Zynq FSBL}\n"
        )
        f.write("configapp -app fsbl build-config release\n")
        f.write("sdk projects -build -type all\n")
        f.close()
        os.chdir(pwd)

    def build_fsbl(self, build_dir, branch, board):
        pwd = os.getcwd()
        os.chdir(build_dir)
        cc, arch, vivado_version = self.linux_tools_map(branch, board)
        vivado = ". /opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
        cmd = vivado
        cmd += "; xsdk -batch -source create_fsbl_project.tcl"
        self.shell_out2(cmd)
        os.chdir(pwd)

    def build_bootbin(self, build_dir, branch, board):
        pwd = os.getcwd()
        os.chdir(build_dir)
        cc, arch, vivado_version = self.linux_tools_map(branch, board)
        vivado = ". /opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
        cmd = vivado
        cmd += "; bootgen -arch zynq -image zynq.bif -o BOOT.BIN -w"
        self.shell_out2(cmd)
        os.chdir(pwd)

    def analog_build_bootbin(
        self,
        hdl_branch="hdl_2018_r2",
        uboot_branch="xilinx-v2018.2",
        board="zed",
        project="fmcomms2",
    ):
        dest = "BOOTBIN"
        if not os.path.isdir(dest):
            os.mkdir(dest)
        # Build HDL
        self.analog_clone_build("hdl", branch=hdl_branch, board=board, project=project)
        hdf_filename = (
            "hdl/projects/"
            + project
            + "/"
            + board
            + "/"
            + project
            + "_"
            + board
            + ".sdk/system_top.hdf"
        )
        shutil.copyfile(hdf_filename, dest + "/system_top.hdf")
        # Build u-boot
        self.analog_clone_build("u-boot-xlnx", branch=uboot_branch, board=board)
        filename = "u-boot-xlnx/u-boot"
        shutil.copyfile(filename, dest + "/u-boot.elf")
        # Build fsbl
        self.create_fsbl_project(os.path.basename(hdf_filename), dest)
        self.build_fsbl(dest, "2018_R2", board)
        shutil.copyfile(dest + "/build/sdk/fsbl/Release/fsbl.elf", dest + "/fsbl.elf")
        shutil.copyfile(
            dest + "/build/sdk/hw_0/system_top.bit", dest + "/system_top.bit"
        )
        # Build bif
        self.create_zynq_bif(hdf_filename, dest)
        # Build BOOT.BIN
        self.build_bootbin(dest, "2018_R2", board)

    def analog_clone_build(
        self,
        repo,
        branch="master",
        project=None,
        board=None,
        def_config=None,
        githuborg=None,
    ):
        if repo in ["linux"] and not board:
            raise Exception("Must supply board for " + repo + " builds")
        if repo in ["u-boot-xlnx"] and (not board and not def_config):
            raise Exception("Must supply board or def_config for " + repo + " builds")
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
