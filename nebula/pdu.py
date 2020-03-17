import time

import cyberpower_pdu_snmp as cpdu


class pdu:
    """ Power Distribution Manager """

    def __init__(self, ip, outlet):
        self.ip = ip
        self.outlet = outlet
        self.pdu_cyber = cpdu.CyberPowerPdu(ip)
        pass

    def power_cycle_board(self):
        self.pdu_cyber.set_outlet_on(self.outlet, False)
        time.sleep(5)
        self.pdu_cyber.set_outlet_on(self.outlet, True)
