import iio

from nebula.common import utils


class driver(utils):
    def __init__(self, uri="ip:analog", yamlfilename=None, iio_device_names=None):
        self.iio_device_names = iio_device_names
        self.uri = uri
        if yamlfilename:
            self.update_defaults_from_yaml(yamlfilename, __class__.__name__)

    def check_iio_context(self):
        pass

    def check_iio_devices(self):
        ctx = iio.Context(self.uri)
        devs = []
        for d in ctx.devices:
            devs.append(d.name)
        for dev in self.iio_device_names:
            if dev not in devs:
                raise Exception("Device not found " + str(dev))