import pynetbox
from nebula.common import utils


class netbox(utils):
    """NetBox interface"""

    def __init__(
        self,
        ip="localhost",
        port=8000,
        token="0123456789abcdef0123456789abcdef01234567",
        yamlfilename=None,
        board_name=None,
    ):
        self.nb = pynetbox.api(f"http://{ip}:{port}", token=token)
        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )

    def get_mac_from_asset_tag(self, asset_tag):
        dev = self.nb.dcim.devices.get(asset_tag=asset_tag)
        if not dev:
            raise Exception(f"No devices for with asset tage: {asset_tag}")
        intf = self.nb.dcim.interfaces.get(device_id=dev.id)
        return intf.mac_address
