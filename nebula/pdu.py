import time

import cyberpower_pdu_snmp as cpdu
import yaml
from pyvesync_v2 import VeSync


class pdu:
    """ Power Distribution Manager """

    def __init__(
        self,
        pduip="192.168.86.10",
        outlet=1,
        pdu_type="cyberpower",
        username="cyber",
        password="cyber",
        yamlfilename=None,
    ):
        self.pduip = pduip
        self.outlet = outlet
        self.pdu_type = pdu_type
        if yamlfilename:
            self.update_defaults_from_yaml(yamlfilename)

        if self.pdu_type == "cyberpower":
            self.pdu_dev = cpdu.CyberPowerPdu(self.pduip)
        elif self.pdu_type == "vesync":
            self.pdu_dev = VeSync(self.username, self.password)
            self.pdu_dev.login()
            self.pdu_dev.update()
        else:
            raise Exception("Unknown PDU type")

    def update_defaults_from_yaml(self, filename):
        stream = open(filename, "r")
        configs = yaml.safe_load(stream)
        stream.close()
        if "pdu-config" not in configs:
            raise Exception("pdu-config field not in yaml config file")
        configsList = configs["pdu-config"]
        for config in configsList:
            for k in config:
                if not hasattr(self, k):
                    raise Exception("Unknown field in pdu yaml " + k)
                setattr(self, k, config[k])

    def power_cycle_board(self):
        if self.pdu_type == "cyberpower":
            self.pdu_dev.set_outlet_on(self.outlet, False)
        elif self.pdu_type == "vesync":
            self.pdu_dev.outlets[self.outlet].turn_off()
        time.sleep(5)
        if self.pdu_type == "cyberpower":
            self.pdu_dev.set_outlet_on(self.outlet, True)
        elif self.pdu_type == "vesync":
            self.pdu_dev.outlets[self.outlet].turn_on()
