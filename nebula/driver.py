import logging

from nebula.common import utils

try:
    import iio
except:
    print(
        "--WARNING: IIO bindings not on-path, libIIO dependent operations will not work"
    )


log = logging.getLogger(__name__)


class driver(utils):
    def __init__(
        self, uri="ip:analog", yamlfilename=None, iio_device_names=None, board_name=None
    ):
        self.iio_device_names = iio_device_names
        self.uri = uri
        self.board_name = board_name
        self.update_defaults_from_yaml(
            yamlfilename, __class__.__name__, board_name=board_name
        )

    def check_iio_context(self):
        pass

    def check_iio_devices(self):
        """ Verify all IIO drivers appear on system as expected.
            Exception is raised otherwise
        """
        log.info("Checking uri: " + self.uri)
        ctx = iio.Context(self.uri)
        devs = [d.name for d in ctx.devices]
        # write ctx driver names to a file
        with open(f"{self.board_name}_devs.log", "w") as outfile:
            for i, dev in enumerate(devs):
                if dev:
                    outfile.write(dev)
                    if i < len(devs) - 1:
                        outfile.write("\n")

        missing_devs = []
        for dev in self.iio_device_names:
            log.info("Checking for: " + str(dev))
            if dev not in devs:
                missing_devs.append(dev)

        if len(missing_devs) != 0:
            raise Exception("Device(s) not found " + str(missing_devs))

    def run_all_checks(self):
        self.check_iio_devices()
