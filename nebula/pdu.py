import logging
import time

from pyvesync import VeSync

from nebula import cyberpower as cpdu
from nebula.common import utils

log = logging.getLogger(__name__)


class pdu(utils):
    """Power Distribution Manager"""

    def __init__(
        self,
        pduip=None,
        outlet=None,
        pdu_type=None,
        username=None,
        password=None,
        yamlfilename=None,
        board_name=None,
    ):
        props = ["pduip", "outlet", "pdu_type", "username", "password", "board_name"]
        for prop in props:
            setattr(self, prop, None)
        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )
        for prop in props:
            if eval(prop) is not None:
                setattr(self, prop, eval(prop))

        if not isinstance(self.outlet, list):
            self.outlet = [self.outlet]

        if self.pdu_type == "cyberpower":
            if not self.pduip:
                raise Exception("pduip must be set for cyberpower config")
            self.pdu_dev = cpdu.CyberPowerPdu(self.pduip)
        elif self.pdu_type == "vesync":
            if not self.username:
                raise Exception("username must be set for vesync config")
            if not self.password:
                raise Exception("password must be set for vesync config")
            self.pdu_dev = VeSync(self.username, self.password, redact=True)
            self.pdu_dev.login()
            self.pdu_dev.update()
        else:
            raise Exception("Unknown PDU type")
        
    def _get_outlet_vesync(self, name):
        """Get VeSync outlet by name or index"""
        if isinstance(name, str):
            for o in self.pdu_dev.outlets:
                if o.device_name == name:
                    return o
            raise Exception(f"Outlet {name} not found")
        elif isinstance(name, int):
            if name < 0 or name >= len(self.pdu_dev.outlets):
                raise Exception(f"Outlet index {name} out of range")
            return self.pdu_dev.outlets[name]
        else:
            raise Exception("Outlet must be a string or integer")

    def power_cycle_board(self, name=None):
        """Power Cycle Board: OFF, wait 5 seconds, ON"""
        log.info(f"Power cycling {self.board_name}")
        if self.pdu_type == "cyberpower":
            outlets = self.outlet if isinstance(self.outlet, list) else [self.outlet]
            for outlet in outlets:
                self.pdu_dev.set_outlet_on(outlet, False)
        elif self.pdu_type == "vesync":
            if name and name not in self.outlet:
                raise Exception(
                    "Must provide outlet name or index to power cycle.\n"+
                    f"Valid outlets: {self.outlet}")
            if name:
                outlet = self._get_outlet_vesync(name)
                outlet.turn_off()
            for o_name in self.outlet:
                outlet = self._get_outlet_vesync(o_name)
                outlet.turn_off()
                time.sleep(2)
        time.sleep(5)
        if self.pdu_type == "cyberpower":
            outlets = self.outlet if isinstance(self.outlet, list) else [self.outlet]
            for outlet in outlets:
                self.pdu_dev.set_outlet_on(outlet, True)
        elif self.pdu_type == "vesync":
            if name and name not in self.outlet:
                raise Exception(
                    "Must provide outlet name or index to power cycle.\n"+
                    f"Valid outlets: {self.outlet}")
            if name:
                outlet = self._get_outlet_vesync(name)
                outlet.turn_on()
            for o_name in self.outlet:
                outlet = self._get_outlet_vesync(o_name)
                outlet.turn_on()
                time.sleep(2)

    def power_down_board(self, name=None):
        """Power Down Board"""
        log.info(f"Powering off {self.board_name}")
        if self.pdu_type == "cyberpower":
            outlets = self.outlet if isinstance(self.outlet, list) else [self.outlet]
            for outlet in outlets:
                self.pdu_dev.set_outlet_on(outlet, False)
        elif self.pdu_type == "vesync":
            if name and name not in self.outlet:
                raise Exception(
                    "Must provide outlet name or index to power off.\n"+
                    f"Valid outlets: {self.outlet}")
            if name:
                outlet = self._get_outlet_vesync(name)
                outlet.turn_off()
            for o_name in self.outlet:
                outlet = self._get_outlet_vesync(o_name)
                outlet.turn_off()
                time.sleep(2)

    def power_up_board(self, name=None):
        """Power On Board"""
        log.info(f"Powering on {self.board_name}")
        if self.pdu_type == "cyberpower":
            outlets = self.outlet if isinstance(self.outlet, list) else [self.outlet]
            for outlet in outlets:
                self.pdu_dev.set_outlet_on(outlet, True)
        elif self.pdu_type == "vesync":
            if name and name not in self.outlet:
                raise Exception(
                    "Must provide outlet name or index to power on.\n"+
                    f"Valid outlets: {self.outlet}")
            if name:
                outlet = self._get_outlet_vesync(name)
                outlet.turn_on()
            for o_name in self.outlet:
                outlet = self._get_outlet_vesync(o_name)
                outlet.turn_on()
                time.sleep(2)
