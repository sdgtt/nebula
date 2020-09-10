import yaml
import os
import nebula.errors as ne

LINUX_DEFAULT_PATH = "/etc/default/nebula"
WINDOWS_DEFAULT_PATH = "C:\\nebula\\nebula.yaml"


def multi_device_check(configs, board_name):
    # Determine if multi-device config
    tmp = configs.copy()
    depth = 0
    while 1:
        if isinstance(tmp, dict):
            depth += 1
            keys = list(tmp.keys())
            tmp = tmp[keys[0]]
        else:
            break

    if depth > 1 and not board_name:
        raise ne.MultiDevFound()
        # raise Exception("Multi-device config found. Board name must be specificied")

    if depth > 1:
        found = False
        for config in configs:
            if config["board-config"]["board-name"] == board_name:
                found = True
                configs = config
                break

        if not found:
            raise Exception("Selected board not found in configuration")

    return configs


class utils:
    def update_defaults_from_yaml(self, filename, configname=None, board_name=None):
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

        configs = multi_device_check(configs, board_name)

        if configname + "-config" not in configs:
            return
            # raise Exception(configname + "-config field not in yaml config file")
        configsList = configs[configname + "-config"]
        for config in configsList:
            for k in config:
                if not hasattr(self, k):
                    raise Exception("Unknown field in " + configname + " yaml: " + k)
                setattr(self, k, config[k])
