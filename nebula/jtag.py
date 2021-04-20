import os
import logging
import shutil
import subprocess

from nebula.common import utils

log = logging.getLogger(__name__)


class jtag(utils):
    """ JTAG Module """

    def __init__(
        self,
        vivado_version="2019.1",
        custom_vivado_path=None,
        yamlfilename=None,
        board_name=None,
    ):
        self.vivado_version = vivado_version
        self.custom_vivado_path = custom_vivado_path

        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )

    def _shell_out2(self, script):
        logging.info("Running command: " + script)
        p = subprocess.Popen(script, shell=True, executable="/bin/bash",stdout=None)
        (output, err) = p.communicate()
        # logging.info(output.decode("utf-8"))
        # return output.decode("utf-8")

    def run_xsdb(self, cmd):
        if not self.custom_vivado_path:
            vivado = ". /opt/Xilinx/Vivado/" + str(self.vivado_version) + "/settings64.sh"
        else:
            vivado = os.path.join(self.custom_vivado_path, "settings64.sh")
        cmd = vivado + '; xsdb -eval "{}"'.format(cmd)
        self._shell_out2(cmd)

    def restart_board(self):
        cmd = "connect; "
        cmd += "after 3000; "
        cmd += "targets 1; "
        cmd += "rst -system; "
        cmd += "con"
        self.run_xsdb(cmd)

    def tcl_errors_recover(self):
        # DAP (Cannot open JTAG port: AP transaction error, DAP status 0x30000021)
        pass

    def boot_to_uboot(self):
        """ From JTAG reset board and load up FSBL and uboot
        This should be followed by uboot interaction to stop it"""
        assert os.path.isfile("fsbl.elf")
        assert os.path.isfile("u-boot.elf")

        cmd = "connect; "
        cmd += "after 3000; "
        cmd += "targets 1; "
        cmd += "puts {Reset System}; "
        cmd += "rst -system; "
        cmd += "con; "
        cmd += "after 1000; "

        cmd += "target 2; "
        # cmd += "con; "
        # cmd += "stop; "
        cmd += "after 1000; "
        
        cmd += "puts {Loading FSBL}; "
        cmd += "dow fsbl.elf; "
        cmd += "con; "
        cmd += "after 1000; "

        cmd += "puts {Loading U-BOOT}; "
        cmd += "dow u-boot.elf; "
        cmd += "con; "
        self.run_xsdb(cmd)

    def load_post_uboot_files(self):
        assert os.path.isfile("system_top.bit")
        assert os.path.isfile("uImage")
        assert os.path.isfile("devicetree.dtb")

        cmd = "connect; "
        cmd += "after 3000; "

        # Device is assumed running
        # cmd += "targets 2; "
        # cmd += "con; "
        # cmd += "after 3000; "

        cmd += "target 1; "
        cmd += "puts {STOPPING}; "
        cmd += "stop; "
        cmd += "after 3000; "

        cmd += "puts {Loading BIT}; "
        cmd += "fpga -file system_top.bit; "
        cmd += "puts {Loading DT}; "
        cmd += "dow -data devicetree.dtb 0x2A00000; "
        cmd += "puts {Loading Kernel}; "
        cmd += "dow -data uImage 0x3000000; "
        cmd += "con; "
        cmd += "after 3000"

        # u-boot takes over from here
        # Must not overwrite memory locations

        self.run_xsdb(cmd)


    def full_boot(self):
        assert os.path.isfile("system_top.bit")
        assert os.path.isfile("fsbl.elf")
        assert os.path.isfile("u-boot.elf")
        assert os.path.isfile("uImage")
        assert os.path.isfile("devicetree.dtb")

        cmd = "connect; "
        cmd += "after 3000; "
        cmd += "targets 1; "
        cmd += "rst -system; "
        cmd += "con; "
        cmd += "after 3000; "

        cmd += "target 2; "
        cmd += "dow fsbl.elf; "
        cmd += "con; "
        cmd += "after 3000; "

        cmd += "dow u-boot.elf; "
        cmd += "con; "
        cmd += "after 3000; "

        cmd += "target 1; "
        cmd += "stop; "
        cmd += "after 3000; "

        cmd += "fpga -file system_top.bit; "
        cmd += "dow -data devicetree.dtb 0x2A00000; "
        cmd += "dow -data uImage 0x3000000; "
        cmd += "con; "
        cmd += "after 3000"

        # u-boot takes over from here
        # Must not overwrite memory locations

        self.run_xsdb(cmd)
