import yaml
import os
import pathlib
import netifaces
import glob


def get_uarts():
    LINUX_SERIAL_FOLDER = "/dev/serial"
    str = " (Options: "

    if os.name == "nt" or os.name == "posix":
        if os.path.isdir(LINUX_SERIAL_FOLDER):
            fds = glob.glob(LINUX_SERIAL_FOLDER + "/by-id/*")
            for fd in fds:
                str = str + str(fd) + ", "
            str = str[:-2] + ") "
            return str
    return None


def get_nics():
    str = " (Options: "
    for nic in netifaces.interfaces():
        str = str + nic + ", "
    str = str[:-2] + ") "
    return str


class helper:
    def __init__(self):
        pass

    def create_config_interactive(self):
        # Read in template
        path = pathlib.Path(__file__).parent.absolute()
        head_tail = os.path.split(path)
        res = os.path.join(head_tail[0], "resources", "template_gen.yaml")
        stream = open(res, "r")
        configs = yaml.safe_load(stream)
        stream.close()
        outconfig = dict()
        required_sections = []
        print("YAML Config Interactive Generation")
        for key in configs.keys():
            # Ask if we need it
            if key not in required_sections:
                s = "Do you want to setup " + key + " [Y/n] : "
                o = input(s)
                if o == "n":
                    continue
            #
            section = configs[key]
            outconfig[key] = []
            current_depends = None
            required_answer = None
            for fields in section.keys():
                field = section[fields]
                while 1:
                    # Get dependent props
                    if "requires" in list(field.keys()):
                        deps_string = field["requires"].split(":")
                        required_answer = deps_string[0]
                        current_depends = deps_string[1].split(",")
                        # print("requires", required_answer)
                        # print("current_depends", current_depends)

                    # Filter out if not needed
                    if isinstance(field["optional"], str):
                        # print("optional", field["optional"], field["name"])
                        # print("current_depends", current_depends)
                        if not current_depends:
                            break  # Skip
                        if field["name"] not in current_depends:
                            break  # Skip

                    # Form question
                    stri = field["help"] + ".\nExample: " + str(field["example"]) + " "
                    if field["optional"] == True:
                        stri = stri + " (optional)"
                    if "callback" in list(field.keys()):
                        out = eval(field["callback"] + "()")
                        if out:
                            stri = stri + out
                    stri = stri + ": "
                    print("-------------")
                    out = input(stri)
                    #
                    if required_answer:
                        if not required_answer == out:
                            current_depends = None
                    required_answer = None  # Reset
                    #
                    if not out:
                        if (not field["optional"]) or (
                            field["name"] in current_depends
                        ):
                            print("Not optional!!!!")
                            continue
                        break  # Skip
                    if isinstance(out, str):
                        if out.lower() == "false":
                            out = False
                        elif out.lower() == "true":
                            out = True
                    d = {field["name"]: out}
                    outconfig[key].append(d)
                    break
        # Output
        LINUX_DEFAULT_PATH = "/etc/default/nebula"
        loc = input(
            "Output config locations [Default {}] : ".format(LINUX_DEFAULT_PATH)
        )
        if not loc:
            loc = LINUX_DEFAULT_PATH
        out = os.path.join(head_tail[0], "resources", "out.yaml")
        with open(out, "w") as file:
            documents = yaml.dump(outconfig, file)
