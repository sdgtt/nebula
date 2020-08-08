import yaml
import os

LINUX_DEFAULT_PATH = "/etc/default/nebula"
WINDOWS_DEFAULT_PATH = "C:\\nebula\\nebula.yaml"


class utils:
    def update_defaults_from_yaml(self, filename, configname):
        """ Utility class for processing yaml files """
        if not filename:
            if os.name == "nt" or os.name == "posix":
                if os.path.exists(LINUX_DEFAULT_PATH):
                    filename = LINUX_DEFAULT_PATH
                else:
                    filename = WINDOWS_DEFAULT_PATH
            else:
                return
        if not os.path.exists(filename):
            return

        stream = open(filename, "r")
        configs = yaml.safe_load(stream)
        stream.close()
        if configname + "-config" not in configs:
            return
            # raise Exception(configname + "-config field not in yaml config file")
        configsList = configs[configname + "-config"]
        for config in configsList:
            for k in config:
                if not hasattr(self, k):
                    raise Exception("Unknown field in " + configname + " yaml: " + k)
                setattr(self, k, config[k])
