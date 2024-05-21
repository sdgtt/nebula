import glob
import json
import logging
import os
import pathlib
import re
from functools import partial

import click
import netifaces
import yaml

import nebula.errors as ne
from nebula.common import multi_device_check
from nebula.netbox import NetboxDevice, NetboxDevices, netbox

LINUX_DEFAULT_PATH = "/etc/default/nebula"
WINDOWS_DEFAULT_PATH = "C:\\nebula\\nebula.yaml"

log = logging.getLogger(__name__)


def convert_by_id_to_tty(by_id):
    """Translate frandom:
    /dev/serial/by-id/usb-Silicon_Labs_CP2103_USB_to_UART_Bridge_Controller_0001-if00-port0
    to
    /dev/ttyUSB1
    """
    import pyudev

    context = pyudev.Context()
    for device in context.list_devices(subsystem="tty", ID_BUS="usb"):
        if by_id in device.device_links:
            return device.device_node
    return False


def convert_address_to_tty(address):
    """Translate frandom:
    /dev/serial/by-id/usb-Silicon_Labs_CP2103_USB_to_UART_Bridge_Controller_0001-if00-port0
    to
    /dev/ttyUSB1
    Will also work with by_path. Works in docker container.
    """
    import pyudev

    context = pyudev.Context()
    tty = pyudev.Devices.from_device_file(context, address)
    if tty:
        return tty.get("DEVNAME")
    else:
        return False


def get_uarts():
    strs = "\n(Found: "
    default = None
    if os.name in ["nt", "posix"]:
        LINUX_SERIAL_FOLDER = "/dev/serial"
        if os.path.isdir(LINUX_SERIAL_FOLDER):
            fds = glob.glob(LINUX_SERIAL_FOLDER + "/by-id/*")
            for fd in fds:
                print(fd)
                strs = strs + "\n" + str(fd)
                default = str(fd)
            strs = strs[:-2] + ") "
            return (strs, default)
    return (None, default)


def get_nics():
    filter = ["docker0", "lo"]
    default = None
    str = "\n(Found: "
    for nic in netifaces.interfaces():
        if nic not in filter:
            str = str + nic + ", "
            default = nic
    str = str[:-2] + ") "
    return (str, default)


def project_filter(project_dict, filters):
    match = True
    for k, v in filters.items():
        if k in project_dict.keys():
            if not project_dict[k] == v:
                match = False
                break
    return match


class helper:
    def __init__(self):
        pass

    def list_supported_boards(self, filter=None):
        path = pathlib.Path(__file__).parent.absolute()
        res = os.path.join(path, "resources", "board_table.yaml")
        with open(res) as f:
            board_configs = yaml.load(f, Loader=yaml.FullLoader)
        for config in board_configs:
            if filter in config or not filter:
                print(config)

    def update_yaml(  # noqa: C901
        self, configfilename, section, field, new_value, board_name=None
    ):
        """Update single field of exist config file"""

        if not os.path.isfile(configfilename):
            raise Exception("Specified yaml file does not exist")
        with open(configfilename, "r") as stream:
            configs = yaml.safe_load(stream)
        board_name_request = field == "board-name" and section == "board-config"

        try:
            cfg = multi_device_check(configs, board_name)
        except ne.MultiDevFound:
            if not board_name_request:
                raise ne.MultiDevFound
            # Print out list of boards
            ks = configs.keys()
            names = []
            for config in ks:
                for cfg in configs[config]:
                    if cfg == "board-config":
                        for c in configs[config][cfg]:
                            for f in c:
                                if f == "board-name":
                                    names.append(c["board-name"])
            print(", ".join(names))
            return
        configs = cfg

        updated = False
        try:
            for i, f in enumerate(configs[section]):
                if field in list(f.keys()):
                    updated = True
                    value = configs[section][i][field]
                    if new_value:
                        configs[section][i][field] = new_value
                        print(
                            "Field",
                            field,
                            "in",
                            section,
                            "updated from",
                            value,
                            "to",
                            new_value,
                        )
                    else:
                        # Handle serial translation
                        if section == "uart-config" and field == "address":
                            value = convert_address_to_tty(value)
                        print(str(value))
                    log.info(field + ": " + str(value))
                    break
            if not updated:
                raise Exception("")
        except Exception:
            raise Exception("Field or section does not exist")
        if new_value:
            self._write_config_file(configfilename, configs)

    def create_config_interactive(self):  # noqa: C901
        # Read in template
        path = pathlib.Path(__file__).parent.absolute()
        res = os.path.join(path, "resources", "template_gen.yaml")
        stream = open(res, "r")
        configs = yaml.safe_load(stream)
        stream.close()
        outconfig = dict()
        required_sections = []
        print("YAML Config Interactive Generation")
        print("###################")
        print("FYI Questions are arranged:")
        print("  Question (Options) [Default]")
        print("###################")
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

                    # Filter out if not needed
                    if isinstance(field["optional"], str):
                        # print("optional", field["optional"], field["name"])
                        # print("current_depends", current_depends)
                        if not current_depends:
                            break  # Skip
                        if field["name"] not in current_depends:
                            break  # Skip

                    # Form question
                    # stri = field["help"] + ".\nExample: " + str(field["default"]) + " "
                    # if field["optional"] == True:
                    #     stri = stri + " (optional)"
                    # if "callback" in list(field.keys()):
                    #     out = eval(field["callback"] + "()")
                    #     if out:
                    #         stri = stri + out
                    # stri = stri + ": "
                    # print("-------------")
                    # out = input(stri)

                    extend = ""
                    if "default" in list(field.keys()):
                        default = field["default"]
                    else:
                        default = None
                    ################
                    if "callback" in list(field.keys()):
                        (out, defaultcb) = eval(field["callback"] + "()")
                        if out:
                            extend = out
                        if defaultcb:
                            default = defaultcb

                    ################
                    if "options" in field.keys():
                        options = field["options"]
                        options = click.Choice(options)
                    else:
                        options = None
                    print("###################")
                    out = click.prompt(
                        text=click.style(field["help"] + extend, fg="green"),
                        prompt_suffix=": ",
                        default=default,
                        type=options,
                        show_choices=True,
                    )
                    ################
                    # Check if meets required answers for dependent properties checks to be enabled
                    if required_answer:
                        if not required_answer == out:  # Disable dependency check
                            current_depends = None
                    required_answer = None  # Reset so we break while

                    # Check if we need to ask again
                    if not out:
                        if (not field["optional"]) or (
                            field["name"] in current_depends
                        ):
                            # print("Not optional!!!!")
                            continue
                        break  # Skip
                    # Convert string to boolean
                    if isinstance(out, str):
                        if out.lower() == "false":
                            out = False
                        elif out.lower() == "true":
                            out = True
                    d = {field["name"]: out}
                    outconfig[key].append(d)
                    break
        # Output
        if os.name == "nt" or os.name == "posix":
            if os.path.exists(LINUX_DEFAULT_PATH):
                NEB_PATH = LINUX_DEFAULT_PATH
            else:
                NEB_PATH = WINDOWS_DEFAULT_PATH

        loc = input(
            "Output config file (this not just a folder) [{}] : ".format(NEB_PATH)
        )
        if not loc:
            loc = NEB_PATH
        self._write_config_file(loc, outconfig)
        # out = os.path.join(head_tail[0], "resources", "out.yaml")
        print("Pew pew... all set")

    def create_config_from_netbox(
        self,
        outfile="nebula",
        netbox_ip="localhost",
        netbox_port=None,
        netbox_baseurl=None,
        netbox_token=None,
        jenkins_agent=None,
        board_name=None,
        include_variants=None,
        include_children=None,
        devices_status=None,
        devices_role=None,
        devices_tag=None,
        template=None,
    ):
        # Read in template
        path = pathlib.Path(__file__).parent.absolute()
        template = os.path.join(
            path, "resources", template if template else "template_gen.yaml"
        )
        ni = netbox(
            ip=netbox_ip,
            port=netbox_port,
            base_url=netbox_baseurl,
            token=netbox_token,
            load_config=False,
        )
        outconfig = dict()
        config = dict()

        # load config from file
        with open(template, "r") as f:
            config = yaml.safe_load(f)

        if board_name:
            nbd = NetboxDevice(ni, device_name=board_name)
            outconfig = nbd.to_config(config)
        else:
            nbds = NetboxDevices(
                ni,
                variants=include_variants,
                children=include_children,
                status=devices_status,
                role=devices_role,
                agent=jenkins_agent,
                tag=devices_tag,
            )
            outconfig = nbds.generate_config(config)

        self._write_config_file(filename=outfile, outconfig=outconfig)

    def _write_config_file(self, filename, outconfig):
        with open(filename, "w") as file:
            yaml.dump(outconfig, file, default_flow_style=False)

        # Post process to fix yaml.dump bug where boolean are all lowercase
        file1 = open(filename, "r")
        lines = []
        for line in file1.readlines():
            line = line.replace(": true\n", ": True\n")
            line = line.replace(": false\n", ": False\n")
            lines.append(line)
        file1.close()
        file1 = open(filename, "w")
        file1.writelines(lines)
        file1.close()

    def get_boot_files_from_descriptor(self, descriptor_file, project):
        """
        Extracts the project bootfiles defined on the kuiper desctriptor file.
        i.e kuiper.json
        """

        boot_files = (
            list()
        )  # contains all files needed to be moved to the boot partition

        common_architectures = [
            ("arria10_", "arria10"),
            ("cyclone5_", "cyclone5"),
            ("zynq-", "zynq"),
            ("zynq-", "zynq"),
            ("zynqmp-", "zynqmp"),
            ("versal-", "versal"),
        ]
        common_boards = [
            ("socdk_", "socdk"),
            ("de10_nano_", "de10nano"),
            ("sockit_", "sockit"),
            ("coraz7s-", "coraz7s"),
            ("zc702-", "zc702"),
            ("zc706-", "zc706"),
            ("zed-", "zed"),
            ("zcu102-", "zcu102"),
            ("adrv9009-zu11eg-", "adrv9009zu11eg_adrv2crr"),
            ("vck190-", "vck190"),
            ("-bob", "ccbob"),
            ("z7035-fmc", "ccfmc"),
            ("z7035-packrf", "ccpackrf"),
            ("z7020-packrf", "ccpackrf"),
        ]
        common_names = [
            ("ad9081$", "ad9081"),
            ("adv7511$", "adv7511"),
            ("ad9695", "ad9695"),
            ("ad9783", "ad9783"),
            ("adrv9002$", "adrv9002"),
            ("adrv9009", "adrv9009"),
            ("adrv9371", "adrv9371"),
            ("adrv9375", "adrv9375"),
            ("cn0540", "cn0540"),
            ("cn0579", "cn0579"),
            ("_daq2", "daq2"),
            ("fmcdaq2", "daq2"),
            ("fmcdaq3", "daq3"),
            ("fmcadc2", "fmcadc2"),
            ("fmcadc3", "fmcadc3"),
            ("fmcjesdadc1", "fmcjesdadc1"),
            ("fmcomms11", "fmcomms11"),
            ("fmcomms2", "fmcomms2"),
            ("fmcomms3", "fmcomms3"),
            ("fmcomms4", "fmcomms4"),
            ("fmcomms5", "fmcomms5"),
            ("fmcomms8", "fmcomms8"),
            ("cn0501", "cn0501"),
            ("ad4020", "ad4020"),
            ("cn0363", "cn0363"),
            ("cn0577", "cn0577"),
            ("imageon", "imageon"),
            ("ad4630-24", "ad4630_fmc"),
            ("ad7768-axi-adc", "ad7768"),
            ("ad7768-1-evb", "ad77681_evb"),
            ("ad7768-4-axi-adc", "ad7768-4"),
            ("adaq8092", "adaq8092"),
            ("socdk_fmclidar1", "ad_fmclidar1_ebz"),
            ("adv7511-fmclidar1", "ad_fmclidar1_ebz"),
            ("rev10-fmclidar1", "fmclidar"),
            ("adrv9002[-_]rx2tx2", "adrv9002_rx2tx2"),
            ("cn0506[-_]mii", "cn0506_mii"),
            ("cn0506[-_]rgmii", "cn0506_rgmii"),
            ("cn0506[-_]rmii", "cn0506_rmii"),
            ("ad6676-fmc", "ad6676evb"),
            ("ad9265-fmc-125ebz", "ad9265_fmc"),
            ("ad9434-fmc", "ad9434_fmc"),
            ("ad9739a-fmc", "ad9739a_fmc"),
            ("adrv9008-1", "adrv9008-1"),
            ("adrv9008-2", "adrv9008-2"),
            ("ad9172-fmc-ebz", "ad9172_fmc"),
            ("fmcomms5-ext-lo-adf5355", "fmcomms5-ext-lo-adf5355"),
            ("z7035-bob-vcmos", "adrv9361z7035_cmos"),
            ("z7035-bob-vlvds", "adrv9361z7035_lvds"),
            ("z7020-bob-vcmos", "adrv9364z7020_cmos"),
            ("z7020-bob-vlvds", "adrv9364z7020_lvds"),
            ("z7035-fmc", "adrv9361z7035_lvds"),
            ("z7035-packrf", "adrv9361z7035_lvds"),
            ("z7020-packrf", "adrv9364z7020_lvds"),
            ("ad9467-fmc-250ebz", "ad9467-fmc"),
            ("otg", "adv7511_without_bitstream"),
            ("hps", "de10nano_without_bitfile"),
            ("adrv2crr-fmc-revb", "adrv9009zu11eg_adrv2crr"),
            ("multisom-primary", "multisom-primary"),
            ("multisom-secondary", "multisom-secondary"),
            ("fmcomms8-multisom-primary", "fmcomms8_multisom_primary"),
            ("fmcomms8-multisom-secondary", "fmcomms8_multisom_secondary"),
            ("xmicrowave", "xmicrowave"),
            ("ad9081-vm8-l4", "ad9081_m8_l4"),
            ("ad9081-vm4-l8", "ad9081_m4_l8"),
            ("ad9081[-_]vnp12", "ad9081_np12"),
            ("ad9081-vm8-l4-vcxo122p88", "ad9081_m8_l4_vcxo122p88"),
            ("ad9081-v204b-txmode9-rxmode4", "ad9081_204b_txmode9_rxmode4"),
            ("ad9081-v204c-txmode0-rxmode1", "ad9081_204c_txmode0_rxmode1"),
            ("ad9082-m4-l8", "ad9082_m4_l8"),
            ("ad9082$", "ad9082"),
            ("ad9083-fmc-ebz", "ad9083"),
            ("adrv9008-1", "adrv9008-1"),
            ("adrv9008-2", "adrv9008-2"),
            ("adv7511-adrv9002-vcmos", "adrv9002"),
            ("rev10-adrv9002-vcmos", "adrv9002_cmos"),
            ("rev10-adrv9002-vlvds", "adrv9002_lvds"),
            ("adv7511-adrv9002-rx2tx2-vcmos", "adrv9002_rx2tx2"),
            ("rev10-adrv9002-rx2tx2-vcmos", "adrv9002_rx2tx2_cmos"),
            ("rev10-adrv9002-rx2tx2-vlvds", "adrv9002_rx2tx2_lvds"),
            ("ad9172-fmc-ebz-mode4", "ad9172_mode4"),
            ("arradio", "sockit_arradio"),
            ("adrv9025", "adrv9025"),
        ]

        with open(descriptor_file, "r") as f:
            descriptor = json.load(f)

        assert descriptor

        # for platform in

        p_architecture = None
        p_board = None
        p_name = None

        for ar in common_architectures:
            if re.search(ar[0], project):
                p_architecture = ar[1]

        for br in common_boards:
            if re.search(br[0], project):
                p_board = br[1]

        for pn in common_names:
            if re.search(pn[0], project):
                p_name = pn[1]

        projects = descriptor["projects"]

        # filter project
        if project:
            filter_dict = dict(
                {"architecture": p_architecture, "board": p_board, "name": p_name}
            )
            projects = filter(partial(project_filter, filters=filter_dict), projects)

        for project in projects:
            # if not project['kernel'] in [ bt[1] for bt in boot_files]:
            # boot_files.append((project['name'],project['kernel']))
            boot_files.append((project["name"], project["kernel"]))
            if "preloader" in project:
                boot_files.append((project["name"], project["preloader"]))
            files = project["files"]
            for f in files:
                boot_files.append((project["name"], f["path"]))

        # check if project is supported
        log.info("path:" + str(boot_files))
        if not boot_files:
            raise Exception("Project not supported in this nebula version.")

        return boot_files
