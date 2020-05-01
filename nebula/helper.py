import yaml
import os
import pathlib
import netifaces
import glob


def get_uarts():
    import uart as c

    LINUX_SERIAL_FOLDER = c.LINUX_SERIAL_FOLDER
    print(LINUX_SERIAL_FOLDER)
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
        print("YAML Config Interactive Generation")
        for key in configs.keys():
            section = configs[key]
            outconfig[key] = []
            for fields in section.keys():
                field = section[fields]
                while 1:
                    print("-------------")
                    stri = field["help"] + ".\nExample: " + str(field["example"]) + " "
                    if field["optional"]:
                        stri = stri + " (optional)"
                    if "callback" in list(field.keys()):
                        out = eval(field["callback"] + "()")
                        if out:
                            stri = stri + out
                    stri = stri + ": "
                    out = input(stri)
                    if not out:
                        if not field["optional"]:
                            print("Not optional!!!!")
                            continue
                        print("Skipping")
                        break
                    if out.lower() == "false":
                        out = False
                    if out.lower() == "true":
                        out = True
                    d = {field["name"]: out}
                    outconfig[key].append(d)
                    break
        # Output
        import common as c

        loc = input(
            "Output config locations [Default {}] : ".format(c.LINUX_DEFAULT_PATH)
        )
        if not loc:
            loc = c.LINUX_DEFAULT_PATH
        out = os.path.join(head_tail[0], "resources", "out.yaml")
        with open(out, "w") as file:
            documents = yaml.dump(outconfig, file)
