import logging

try:
    import iio
except:
    print(
        "--WARNING: IIO bindings not on-path, libIIO dependent operations will not work"
    )

from nebula.common import utils

log = logging.getLogger(__name__)


class driver(utils):
    def __init__(
        self, uri="ip:analog", yamlfilename=None, iio_device_names=None, board_name=None
    ):
        self.iio_device_names = iio_device_names
        self.uri = uri
        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )

    def check_iio_context(self):
        pass

    def check_iio_devices(self):
        """ Verify all IIO drivers appear on system as expected.
            Exception is raised otherwise
        """
        ctx = iio.Context(self.uri)
        devs = []
        for d in ctx.devices:
            devs.append(d.name)
        for dev in self.iio_device_names:
            log.info("Checking for: " + str(dev))
            if dev not in devs:
                raise Exception("Device not found " + str(dev))

    def run_all_checks(self):
        self.check_iio_devices()
