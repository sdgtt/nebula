from pysnmp.hlapi import (
    CommunityData,
    ContextData,
    Integer32,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    setCmd,
)


class CyberPowerPduException(Exception):
    pass


class CyberPowerPdu(object):
    """
    Class to query & control a CyberPower PDU via SNMP.

    Tested on the PDU15SWHVIEC8FNET. I don't understand SNMP well enough to have
    any idea if this would be expected to work on other models.

    This class is basically just a piece of copy-pasted pysnmp code and a
    depository for comments.

    :param host: IP address or hostname of the PDU on the network
    :type host: str
    """

    outlet_state_oids = {
        "immediateOn": 1,
        "immediateOff": 2,
        "immediateReboot": 3,
        "delayedOn": 4,
        "delayedOff": 5,
        "delayedReboot": 6,
        "cancelPendingCommand": 7,
        "outletIdentify": 8,
    }

    def __init__(self, host):
        self.host = host

    def set_outlet_on(self, outlet, on):
        """
        Set an outlet on or off

        :param outlet: Which outlet to set the power for (for my model this is
                       in the range 1 through 8)
        :param on: True means turn it on, False means turn it off
        """

        oid = ObjectIdentity("1.3.6.1.4.1.3808.1.1.3.3.3.1.1.4.{}".format(outlet))
        target_state = "immediateOn" if on else "immediateOff"
        errorIndication, errorStatus, errorIndex, varBinds = next(
            setCmd(
                SnmpEngine(),
                CommunityData("private"),
                UdpTransportTarget((self.host, 161)),
                ContextData(),
                ObjectType(oid, Integer32(self.outlet_state_oids[target_state])),
            )
        )

        if errorIndication:
            raise CyberPowerPduException(errorIndication)
        elif errorStatus:
            raise CyberPowerPduException(
                "%s at %s"
                % (
                    errorStatus.prettyPrint(),
                    errorIndex and varBinds[int(errorIndex) - 1][0] or "?",
                )
            )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("host", help="Hostname/IP address of PDU")
    parser.add_argument("outlet", help="Outlet to interact with")
    parser.add_argument("on", choices=("on", "off"))

    args = parser.parse_args()

    CyberPowerPdu(args.host).set_outlet_on(args.outlet, args.on == "on")
