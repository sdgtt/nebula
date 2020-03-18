import time

import cyberpower_pdu_snmp as cpdu
import yaml


class pdu:
    """ Power Distribution Manager """

    def __init__(self, pduip="192.168.86.10", outlet=1, yamlfilename=None):
        self.pduip = pduip
        self.outlet = outlet
        if yamlfilename:
            self.update_defaults_from_yaml(yamlfilename)
        self.pdu_cyber = cpdu.CyberPowerPdu(self.pduip)

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
        self.pdu_cyber.set_outlet_on(self.outlet, False)
        time.sleep(5)
        self.pdu_cyber.set_outlet_on(self.outlet, True)
