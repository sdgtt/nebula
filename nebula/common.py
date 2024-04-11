import logging
import os

import yaml

import nebula.errors as ne

LINUX_DEFAULT_PATH = "/etc/default/nebula"
WINDOWS_DEFAULT_PATH = "C:\\nebula\\nebula.yaml"

log = logging.getLogger(__name__)


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

    log.info("Depth of config: " + str(depth))
    log.info("board_name used: " + str(board_name))
    if depth > 1 and not board_name:
        raise ne.MultiDevFound()
    if depth <= 1:
        return configs

    # Filter out config for board of interest
    for config in configs:
        for cfg in configs[config]:
            if cfg == "board-config":
                for c in configs[config][cfg]:
                    for f in c:
                        if f == "board-name" and c["board-name"] == board_name:
                            return configs[config]

    raise Exception("Selected board not found in configuration")


class utils:
    def update_defaults_from_yaml(
        self, filename, configname=None, board_name=None, attr=None
    ):
        """Utility class for processing yaml files"""
        if not filename:
            if os.name in ["nt", "posix"]:
                if os.path.exists(LINUX_DEFAULT_PATH):
                    filename = LINUX_DEFAULT_PATH
                else:
                    filename = WINDOWS_DEFAULT_PATH
            else:
                return
        if not os.path.exists(filename):
            return

        with open(filename, "r") as stream:
            configs = yaml.safe_load(stream)
        configs = multi_device_check(configs, board_name)

        if configname + "-config" not in configs:
            return
            # raise Exception(configname + "-config field not in yaml config file")
        configsList = configs[configname + "-config"]
        for config in configsList:
            for k in config:
                if attr:
                    if not isinstance(attr, list):
                        attr = list(attr)
                    if k in attr:
                        if not hasattr(self, k):
                            raise Exception(
                                "Unknown field in " + configname + " yaml: " + k
                            )
                        setattr(self, k, config[k])
                else:
                    if not hasattr(self, k):
                        raise Exception(
                            "Unknown field in " + configname + " yaml: " + k
                        )
                    setattr(self, k, config[k])
