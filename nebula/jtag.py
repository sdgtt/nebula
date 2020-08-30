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
        p = subprocess.Popen(script, shell=True, executable="/bin/bash")
        (output, err) = p.communicate()
        # return output.decode("utf-8")

    def run_xsdb(self, cmd):
        if not self.custom_vivado_path:
            vivado = ". /opt/Xilinx/Vivado/" + self.vivado_version + "/settings64.sh"
        else:
            vivado = os.path.append(self.custom_vivado_path, "settings64.sh")
        cmd = vivado + '; xsdb -eval "{}"'.format(cmd)
        self._shell_out2(cmd)

    def restart_board(self):
        cmd = "connect; "
        cmd += "after 3000; "
        cmd += "targets 1; "
        cmd += "rst -system; "
        cmd += "con"
        self.run_xsdb(cmd)
