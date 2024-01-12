#!/usr/bin/python

import logging
import os
import shutil
import subprocess
import time
import yaml
from glob import glob

from .tooling import Tooling

log = logging.getLogger(__name__)


class BuilderCore(Tooling):
    vivado_override = None

    def __init__(self, release="2021_R1", board="zed", project="fmcomms2"):
        self.release = release
        self.board = board
        self.project = project
        self.import_all_configs(release)

    
    def import_all_configs(self, release):
        self.cfg_uboot = self.import_config("uboot", release)
        self.cfg_linux = self.import_config("linux", release)
        self.cfg_hdl = self.import_config("hdl", release)

    def _save_metadata(self, metadata):
        ...

    def shell_out(self, cmd):
        cmd = cmd.split(" ")
        logging.info(f"Running command: {cmd}")
        subprocess.run(cmd)

    def shell_out2(self, script):
        logging.info("Running command: " + script)
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
            if (
                "set REQUIRED_VIVADO_VERSION" in line
                or "set required_vivado_version" in line
            ):
                vivado_version = line.split()[2].replace('"', "")
                vivado = "/opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
                if not os.path.isfile(vivado):
                    raise Exception(
                        "Required vivado version not found: " + vivado_version
                    )
                vivado = ". " + vivado
                return vivado
        raise Exception("REQUIRED_VIVADO_VERSION not found in repo")



    def uboot_build(self, dir):
        logging.info("Starting u-boot build")
        os.chdir(dir)
        arch, cc, def_config = self.get_compiler_args("uboot")
        cmd = self.get_tooling_setup_prefix('uboot')
        cmd += "; export ARCH=" + arch + "; export CROSS_COMPILE=" + cc
        cmd += "; make distclean; make clean"
        cmd += "; make " + def_config
        cmd += "; make -j" + str(os.cpu_count())
        self.shell_out2(cmd)
        # Find full path to u-boot.elf
        for filename in glob('./**/u-boot.elf', recursive=True):
            return filename
        raise Exception("u-boot.elf not found")

    def hdl_build(self, dir):
        logging.info("Starting HDL build for project: " + self.project + " board: " + self.board)
        os.chdir(dir)
        # vivado = self.add_vivado_path(dir)
        project_dir = os.path.join("projects", self.project)
        if not os.path.isdir(project_dir):
            raise Exception(f"Project dir not found: {project_dir}")
        board_dir = os.path.join(project_dir, self.board)
        if not os.path.isdir(board_dir):
            raise Exception(f"Board dir not found: {board_dir}")
        cmd = self.get_tooling_setup_prefix('hdl')
        args = "--no-print-directory"
        cmd += f"; make {args} -C {board_dir}"
        if os.name == "nt":
            raise Exception("Windows not supported yet")
        self.shell_out2(cmd)
        # Find .hdf file recursively in current and subdirectories with glob
        for filename in glob('./**/*.hdf', recursive=True):
            return filename
        for filename in glob('./**/*.xsa', recursive=True):
            return filename
        raise Exception("HDF file not found")


    def def_config_map(self, board):
        if "zcu102" in board.lower():
            # def_conf = "xilinx_zynqmp_zcu102_rev1_0_defconfig"
            def_conf = "xilinx_zynqmp_virt_defconfig"
        elif "zc706" in board.lower():
            def_conf = "zynq_zc706_defconfig"
        elif "zc702" in board.lower():
            def_conf = "zynq_zc702_defconfig"
        elif "zed" in board.lower():
            def_conf = "zynq_zed_defconfig"
        else:
            raise Exception("Unsupported board")
        return def_conf

    def linux_tools_map(self, branch, board, build_component: str = "hdl"):
        """Map git branch to supported compilers

        Args:
            branch (str): git branch name
            board (str): board name
            build_component (str): component to build [u_boot_xlnx, linux, hdl]

        Returns:
            tuple: (cc, arch, vivado)
        """

        if build_component not in ["u_boot_xlnx", "linux", "hdl"]:
            raise Exception("Unknown build component")

        if self.vivado_override:
            vivado = self.vivado_override
        else:
            resource_folder = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "resources", "builder"
            )
            tools_file = os.path.join(resource_folder, "builder_tools_2021_R1.yaml")
            if not os.path.isfile(tools_file):
                raise Exception("builder_tools.yaml not found")
            with open(tools_file, "r") as f:
                tools = yaml.safe_load(f)

            vivado = None
            for release in tools:
                print("Release", release)
                print("build_component", build_component)
                print("branch", branch)
                if build_component == "u_boot_xlnx":
                    if branch == tools[release]["u_boot_xlnx_branch"]:
                        vivado = tools[release]["vivado"]
                        break
                elif build_component == "linux":
                    if branch == tools[release]["linux_branch"]:
                        vivado = tools[release]["vivado"]
                        break
                elif build_component == "hdl":
                    if branch == tools[release]["hdl_branch"]:
                        vivado = tools[release]["vivado"]
                        break

            if not vivado:
                raise Exception(
                    "Cannot automatically determine Vivado version, use override"
                )

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

    def linux_build(self, dir):
        logging.info("Starting Linux build")
        os.chdir(dir)
        arch, cc, def_config = self.get_compiler_args("linux")
        cmd = self.get_tooling_setup_prefix('linux')
        cmd += "; export ARCH=" + arch + "; export CROSS_COMPILE=" + cc
        cmd += "; make distclean; make clean"
        cmd += "; make " + def_config
        if "64" in arch:
            cmd += "; make -j" + str(os.cpu_count()) + " UIMAGE_LOADADDR=0x8000 Image"
        else:
            cmd += "; make -j" + str(os.cpu_count()) + " UIMAGE_LOADADDR=0x8000 uImage"
        self.shell_out2(cmd)

        if "64" in arch:
            return "arch/arm64/boot/Image"
        else:
            return "arch/arm/boot/uImage"

    def create_zynq_bif(self, hdf_filename, build_dir):
        logging.info("Constructing zynq-bif")
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

    def create_zynqmp_bif(self, hdf_filename, build_dir):
        logging.info("Constructing zynqmp-bif")
        pwd = os.getcwd()
        os.chdir(build_dir)
        ### Create zynq.bif file used by bootgen
        filename = "zynq.bif"
        hdf_filename = os.path.basename(hdf_filename)
        f = open(filename, "w+")
        f.write("the_ROM_image:\n")
        f.write("{\n")
        f.write("[bootloader,destination_cpu=a53-0] fsbl.elf\n")
        f.write("[pmufw_image] pmufw.elf\n")
        f.write("[destination_device=pl] system_top.bit\n")
        f.write("[destination_cpu=a53-0, exception_level=el-3,trustzone] bl31.elf\n")
        f.write("[destination_cpu=a53-0, exception_level=el-2] u-boot.elf\n")
        f.write("}\n")
        f.close()
        os.chdir(pwd)

    def create_pmufw_project(self, hdf_filename, build_dir):
        logging.info("Constructing pmufw project")
        pwd = os.getcwd()
        os.chdir(build_dir)
        ### Create create_fsbl_project.tcl file used by xsdk to create the fsbl
        hdf_filename = os.path.basename(hdf_filename)
        filename = "create_pmufw_project.tcl"
        f = open(filename, "w+")
        f.write("set hwdsgn [open_hw_design " + hdf_filename + "]\n")
        f.write(
            "generate_app -hw $hwdsgn -os standalone -proc psu_pmu_0 -app zynqmp_pmufw -sw pmufw -dir pmufw\n"
        )
        f.write("quit\n")
        f.close()
        os.chdir(pwd)

    def create_fsbl_project(self, hdf_filename, build_dir):
        logging.info("Constructing fsbl project")
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

    def create_zmp_fsbl_project(self, hdf_filename, build_dir):
        logging.info("Constructing zmp-fsbl project")
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
            "sdk createapp -name fsbl -hwproject hw_0 -proc $cpu_name -os standalone -lang C -app {Zynq MP FSBL}\n"
        )
        f.write("configapp -app fsbl build-config release\n")
        f.write("sdk projects -build -type all\n")
        f.close()
        os.chdir(pwd)

    def build_fsbl(self, build_dir):
        logging.info("Building fsbl")
        pwd = os.getcwd()
        os.chdir(build_dir)
        # arch, cc, def_config = self.get_compiler_args("hdl")
        # cc, arch, vivado_version = self.linux_tools_map(branch, board)
        cmd = self.get_tooling_setup_prefix('hdl')
        # vivado = ". /opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
        # cmd = vivado
        cmd += "; xsdk -batch -source create_fsbl_project.tcl"
        self.shell_out2(cmd)
        os.chdir(pwd)

    def build_pmufw(self, build_dir, branch, board):
        logging.info("Building pmufw")
        pwd = os.getcwd()
        os.chdir(build_dir)
        cc, arch, vivado_version = self.linux_tools_map(branch, board)
        vivado = ". /opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
        cmd = vivado
        cmd += "; hsi -source create_pmufw_project.tcl"
        self.shell_out2(cmd)
        self.shell_out2(
            'grep "CC_FLAGS :=" pmufw/Makefile | grep -e "-Os" || sed -i \'/-mxl-soft-mul/ s/$/ -Os -flto -ffat-lto-objects/\' pmufw/Makefile'
        )
        os.chdir("pmufw")
        cmd = vivado
        cmd += "; make"
        self.shell_out2(cmd)
        os.chdir(pwd)

    def build_zmp_fsbl(self, build_dir, branch, board):
        logging.info("Building zmp-fsbl")
        pwd = os.getcwd()
        os.chdir(build_dir)
        cc, arch, vivado_version = self.linux_tools_map(branch, board)
        vivado = ". /opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
        cmd = vivado
        cmd += "; xsdk -batch -source create_fsbl_project.tcl"
        self.shell_out2(cmd)
        os.chdir(pwd)

    def build_atf(self, build_dir, branch, board):
        logging.info("Building atf")
        pwd = os.getcwd()
        os.chdir(build_dir)
        cc, arch, vivado_version = self.linux_tools_map(branch, board)
        self.analog_clone("arm-trusted-firmware", "xilinx-v" + vivado_version, "Xilinx")
        os.chdir("arm-trusted-firmware")
        vivado = ". /opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
        cmd = vivado
        cmd += "; export CROSS_COMPILE=" + cc + "; PLAT=zynqmp RESET_TO_BL31=1"
        cmd += "; make"
        self.shell_out2(cmd)
        os.chdir(pwd)

    def build_bootbin(self, build_dir, branch, board, archbg="zynq"):
        logging.info("Building BOOT.BIN")
        pwd = os.getcwd()
        os.chdir(build_dir)
        cc, arch, vivado_version = self.linux_tools_map(branch, board)
        vivado = ". /opt/Xilinx/Vivado/" + vivado_version + "/settings64.sh"
        cmd = vivado
        cmd += "; bootgen -arch " + archbg + " -image zynq.bif -o BOOT.BIN -w"
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
        # shutil.copyfile(
        #    dest + "/build/sdk/hw_0/system_top.bit", dest + "/system_top.bit"
        # )

        # Build u-boot
        self.analog_clone_build("u-boot-xlnx", branch=uboot_branch, board=board)
        filename = "u-boot-xlnx/u-boot"
        shutil.copyfile(filename, dest + "/u-boot.elf")

        cc, arch, vivado_version = self.linux_tools_map(uboot_branch, board)

        if arch == "arm":
            # Build fsbl
            self.create_fsbl_project(os.path.basename(hdf_filename), dest)
            self.build_fsbl(dest, hdl_branch, board)
            shutil.copyfile(
                dest + "/build/sdk/fsbl/Release/fsbl.elf", dest + "/fsbl.elf"
            )
            # Build bif
            self.create_zynq_bif(hdf_filename, dest)

            archbg = "zynq"

        elif arch == "arm64":
            pwd = os.getcwd()
            self.create_pmufw_project(os.path.basename(hdf_filename), dest)
            self.build_pmufw(dest, hdl_branch, board)
            shutil.copyfile(dest + "/pmufw/executable.elf", dest + "/pmufw.elf")

            self.build_atf(pwd, hdl_branch, board)
            shutil.copyfile(
                pwd + "/arm-trusted-firmware/build/fvp/release/bl31/bl31.elf",
                dest + "/bl31.elf",
            )

            self.create_zmp_fsbl_project(os.path.basename(hdf_filename), dest)
            self.build_zmp_fsbl(dest, hdl_branch, board)

            shutil.copyfile(
                dest + "/build/sdk/fsbl/Release/fsbl.elf", dest + "/fsbl.elf"
            )
            # Build bif
            self.create_zynqmp_bif(hdf_filename, dest)

            archbg = "zynqmp"

        # Build BOOT.BIN
        self.build_bootbin(dest, hdl_branch, board, archbg=archbg)


if __name__ == "__main__":
    ...
    # b = builder()
    # b.analog_clone_build("u-boot-xlnx", "2018_R2")
    # b.analog_clone_build("linux", "2018_R2")
