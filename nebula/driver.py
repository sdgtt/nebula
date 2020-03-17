import iio
import yaml


class driver:
    def __init__(self, uri="ip:analog", yamlfilename=None, iio_device_names=None):
        self.iio_device_names = iio_device_names
        self.uri = uri
        if yamlfilename:
            self.update_defaults_from_yaml(yamlfilename)

    def update_defaults_from_yaml(self, filename):
        stream = open(filename, "r")
        configs = yaml.safe_load(stream)
        stream.close()
        if "driver-config" not in configs:
            raise Exception("driver-config field not in yaml config file")
        configsList = configs["driver-config"]
        for config in configsList:
            for k in config:
                if not hasattr(self, k):
                    raise Exception("Unknown field in driver yaml " + k)
                setattr(self, k, config[k])

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
