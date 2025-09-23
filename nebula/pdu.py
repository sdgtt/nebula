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

    def power_cycle_board(self):
        """Power Cycle Board: OFF, wait 5 seconds, ON"""
        log.info(f"Power cycling {self.board_name}")
        if self.pdu_type == "cyberpower":
            self.pdu_dev.set_outlet_on(self.outlet, False)
        elif self.pdu_type == "vesync":
            if isinstance(self.outlet, str):
                found = False
                for o in self.pdu_dev.outlets:
                    if o.device_name == self.outlet:
                        o.turn_off()
                        found = True
                        break
                if not found:
                    log.warning(f"Outlet {self.outlet} not found")
            else:
                self.pdu_dev.outlets[self.outlet].turn_off()
        time.sleep(5)
        if self.pdu_type == "cyberpower":
            self.pdu_dev.set_outlet_on(self.outlet, True)
        elif self.pdu_type == "vesync":
            if isinstance(self.outlet, str):
                for o in self.pdu_dev.outlets:
                    if o.device_name == self.outlet:
                        o.turn_on()
                        break
            else:
                self.pdu_dev.outlets[self.outlet].turn_on()

    def power_down_board(self):
        """Power Down Board"""
        log.info(f"Powering off {self.board_name}")
        if self.pdu_type == "cyberpower":
            self.pdu_dev.set_outlet_on(self.outlet, False)
        elif self.pdu_type == "vesync":
            if isinstance(self.outlet, str):
                found = False
                for o in self.pdu_dev.outlets:
                    if o.device_name == self.outlet:
                        o.turn_off()
                        found = True
                        break
                if not found:
                    log.warning(f"Outlet {self.outlet} not found")
            else:
                self.pdu_dev.outlets[self.outlet].turn_off()

    def power_up_board(self):
        """Power On Board"""
        log.info(f"Powering on {self.board_name}")
        if self.pdu_type == "cyberpower":
            self.pdu_dev.set_outlet_on(self.outlet, True)
        elif self.pdu_type == "vesync":
            if isinstance(self.outlet, str):
                found = False
                for o in self.pdu_dev.outlets:
                    if o.device_name == self.outlet:
                        o.turn_on()
                        found = True
                        break
                if not found:
                    log.warning(f"Outlet {self.outlet} not found")
            else:
                self.pdu_dev.outlets[self.outlet].turn_on()
