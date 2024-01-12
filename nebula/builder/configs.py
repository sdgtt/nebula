import yaml
import os
from functools import reduce

def read_yaml_and_get_includes(yaml_file):

    if not os.path.exists(yaml_file):
        raise Exception(f"Config file not found: {yaml_file}")
    
    with open(yaml_file, "r") as f:
        config = yaml.safe_load(f)

    if config is None:
        return {}, []

    if "include" in config:
        includes = config["include"]
        del config["include"]
    else:
        includes = []

    return config, includes

import collections


def merge_dict_with_subdicts(dict1: dict, dict2: dict) -> dict:
    """
    similar behaviour to builtin dict.update - but knows how to handle nested dicts
    """
    q = collections.deque([(dict1, dict2)])
    while len(q) > 0:
        d1, d2 = q.pop()
        for k, v in d2.items():
            if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
                q.append((d1[k], v))
            else:
                d1[k] = v

    return dict1

class BuilderConfig:
    def import_config(self, resource, release):
        if resource not in ["linux", "hdl", "uboot"]:
            raise Exception("Resource not found")
        root_folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "resources"
        )
        # release_config_file = os.path.join(root_folder, resource, f"release_{release}.yaml")
        # if not os.path.exists(release_config_file):
        #     raise Exception(f"Config file not found: {release_config_file}")
        
        resource_root = os.path.join(root_folder, resource)
        resource_config_file = os.path.join(resource_root, f"release_{release}.yaml")
        config, includes_paths = read_yaml_and_get_includes(resource_config_file)

        configs_to_merge = [config]

        while len(includes_paths) > 0:
            include_file_path = os.path.join(root_folder, includes_paths[0])
            includes_paths.pop(0)

            if not os.path.exists(include_file_path):
                raise Exception(f"Include file not found {include_file_path}")
            
            include_config, new_include_paths = read_yaml_and_get_includes(include_file_path)
            includes_paths.extend(new_include_paths)
            configs_to_merge.append(include_config)

        # Favor configs down tree like devicetree works
        configs_to_merge.reverse()

        # Merge all configs
        final_config = {}
        for config_to_merge in configs_to_merge:
            final_config = merge_dict_with_subdicts(final_config, config_to_merge)

        return final_config

if __name__ == "__main__":
    builder = BuilderConfig()
    final_config = builder.import_config("uboot", "2021_R1")

    import pprint
    pprint.pprint(final_config)
