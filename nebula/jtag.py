import logging
import os
import shutil
import subprocess
import time

from nebula.common import utils

log = logging.getLogger(__name__)


class jtag(utils):
    """JTAG Module"""

    def __init__(
        self,
        vivado_version="2019.1",
        custom_vivado_path=None,
        yamlfilename=None,
        board_name=None,
        jtag_cable_id=None,
        jtag_cpu_target_name=None,
        jtag_connect_retries=3,
    ):
        self.vivado_version = vivado_version
        self.custom_vivado_path = custom_vivado_path
        self.jtag_cable_id = jtag_cable_id
        self.jtag_cpu_target_name = jtag_cpu_target_name
        self.jtag_connect_retries = jtag_connect_retries

        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )

        # Check target device available
        jtag_connected = False
        for c in range(self.jtag_connect_retries):
            cmd = "connect; after 1000; " + self.target_set_str(
                self.jtag_cpu_target_name
            )
            jtag_connected = self.run_xsdb(cmd)
            if jtag_connected:
                log.info(
                    "JTAG {} connection attempt successful".format(self.jtag_cable_id)
                )
                break
            log.warning(
                "JTAG {} connection attempt failed.  Attempt {}".format(
                    self.jtag_cable_id, c + 1
                )
            )
            time.sleep(1)

        if not jtag_connected:
            raise Exception(
                "JTAG connection cannot find target HW: {}".format(self.jtag_cable_id)
            )

    def _shell_out2(self, script):
        log.info("Running command: " + script)
        # p = subprocess.Popen(script, shell=True, executable="/bin/bash",stdout=subprocess.PIPE)
        # p = subprocess.Popen([script], executable="/bin/bash",stdout=subprocess.PIPE)
        # output, err = p.communicate()
        try:
            output = subprocess.check_output(
                script, shell=True, executable="/bin/bash", stderr=subprocess.STDOUT
            )
            log.info(output)
            return True
        except Exception as ex:
            log.error("XSDB failed on command: " + script)
            log.error("msg: " + str(ex))
        return False
        # logging.info(output.decode("utf-8"))
        # return output.decode("utf-8")

    def run_xsdb(self, cmd):
        if not self.custom_vivado_path:
            vivado = (
                ". /opt/Xilinx/Vivado/" + str(self.vivado_version) + "/settings64.sh"
            )
        else:
            vivado = os.path.join(self.custom_vivado_path, "settings64.sh")
        if not os.path.isfile(vivado[2:]):
            raise Exception(
                "Vivado not found at: " + vivado[: -(len("settings64.sh") + 1)]
            )

        cmd = vivado + '; xsdb -eval "{}"'.format(cmd)
        # cmd = [vivado + '; xsdb',' -eval "{}"'.format(cmd)]
        return self._shell_out2(cmd)

    def restart_board(self):
        cmd = "connect; "
        cmd += "after 3000; "
        cmd += "puts [jtag target]; "
        cmd += self.target_set_str("APU*")
        cmd += "puts {Reset System}; "
        cmd += "after 1000; "
        cmd += "rst -system; "
        cmd += "after 1000; "
        cmd += "con"
        self.run_xsdb(cmd)

    def tcl_errors_recover(self):
        # DAP (Cannot open JTAG port: AP transaction error, DAP status 0x30000021)
        pass

    def target_set_str(self, target_name):
        return (
            "targets -set -filter {jtag_cable_name =~ {*"
            + self.jtag_cable_id
            + "} && name =~ {"
            + target_name
            + "}} ; "
        )

    def boot_to_uboot(self, fsblpath="fsbl.elf" ,ubootpath="u-boot.elf"):
        """From JTAG reset board and load up FSBL and uboot
        This should be followed by uboot interaction to stop it"""
        assert os.path.isfile(fsblpath)
        assert os.path.isfile(ubootpath)

        cmd = "connect; "
        cmd += "after 3000; "
        cmd += "puts [jtag target]; "
        cmd += self.target_set_str("APU*")
        cmd += "puts {Reset System}; "
        cmd += "after 1000; "
        cmd += "rst -system; "
        cmd += "after 1000; "
        cmd += "con; "
        cmd += "after 1000; "

        cmd += self.target_set_str(self.jtag_cpu_target_name)
        # cmd += "con; "
        # cmd += "stop; "
        cmd += "after 1000; "

        cmd += "puts {Loading FSBL}; "
        cmd += f"dow {fsblpath}; "
        cmd += "con; "
        cmd += "after 1000; "

        cmd += "puts {Loading U-BOOT}; "
        cmd += "if {[catch {dow " + ubootpath + "} result]} {puts {Error loading FSBL... u-boot is probably loaded}; }; "
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

        cmd += self.target_set_str("APU*")
        # cmd += "target 1; "
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
