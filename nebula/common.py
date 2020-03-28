import yaml


class utils:
    def update_defaults_from_yaml(self, filename, configname):
        """ Utility class for processing yaml files """
        stream = open(filename, "r")
        configs = yaml.safe_load(stream)
        stream.close()
        if configname + "-config" not in configs:
            raise Exception(configname + "-config field not in yaml config file")
        configsList = configs[configname + "-config"]
        for config in configsList:
            for k in config:
                if not hasattr(self, k):
                    raise Exception("Unknown field in " + configname + " yaml: " + k)
                setattr(self, k, config[k])
