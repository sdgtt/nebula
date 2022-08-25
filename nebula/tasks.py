import logging
import os
import time
from operator import truediv

import nebula
import yaml
from invoke import Collection, task

logging.getLogger().setLevel(logging.WARNING)


class MyFilter(logging.Filter):
    def filter(self, record):
        return "nebula" in record.name


LINUX_DEFAULT_PATH = "/etc/default/nebula"
WINDOWS_DEFAULT_PATH = "C:\\nebula\\nebula.yaml"

if os.name in ["nt", "posix"]:
    if os.path.exists(LINUX_DEFAULT_PATH):
        DEFAULT_NEBULA_CONFIG = LINUX_DEFAULT_PATH
    else:
        DEFAULT_NEBULA_CONFIG = WINDOWS_DEFAULT_PATH


def load_yaml(filename):
    with open(filename, "r") as stream:
        configs = yaml.safe_load(stream)
    return configs


#############################################
@task(
    help={
        "vivado_version": "Set vivado version. Defaults to 2019.1",
        "custom_vivado_path": "Full path to vivado settings64 file. When set ignores vivado version",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def jtag_reboot(
    c,
    vivado_version="2019.1",
    custom_vivado_path=None,
    yamlfilename="/etc/default/nebula",
    board_name=None,
):
    """Reboot board using JTAG"""
    j = nebula.jtag(
        vivado_version=vivado_version,
        custom_vivado_path=custom_vivado_path,
        yamlfilename=yamlfilename,
        board_name=board_name,
    )
    j.restart_board()


jtag = Collection("jtag")
jtag.add_task(jtag_reboot, "reboot")


#############################################
@task(
    help={"filter": "Required substring in design names"},
)
def supported_boards(c, filter=None):
    """Print out list of supported design names"""
    h = nebula.helper()
    h.list_supported_boards(filter)


info = Collection("info")
info.add_task(supported_boards, "supported_boards")


#############################################
@task(
    help={
        "uri": "URI of board running iiod with drivers to check",
        "iio_device_names": "List of IIO driver names to check on board",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def check_iio_devices(
    c,
    uri,
    iio_device_names=None,
    yamlfilename="/etc/default/nebula",
    board_name=None,
):
    """Verify all IIO drivers appear on system as expected.
    Exception is raised otherwise
    """
    d = nebula.driver(yamlfilename=yamlfilename, uri=uri, board_name=board_name)
    d.check_iio_devices()


driver = Collection("driver")
driver.add_task(check_iio_devices, "check_iio_devices")


#############################################
@task(
    help={
        "ip": "IP address of board with gcov enabled kernel",
        "linux_build_dir": "Build directory of kernel",
        "username": "Username of DUT. Defaults to root",
        "password": "Password of DUT. Defaults to analog",
    },
)
def kernel_cov(c, ip, linux_build_dir, username="root", password="analog"):
    """Collect DUT gcov kernel logs and generate html report (Requires lcov to be installed locally)"""
    cov = nebula.coverage(ip, username, password)
    cov.collect_gcov_trackers()
    cov.gen_lcov_html_report(linux_build_dir)


cov = Collection("coverage")
cov.add_task(kernel_cov, "kernel")


#############################################
@task(
    help={
        "release": "Name of release to download. Default is 2019_R1",
    },
)
def download_sdcard(c, release="2019_R1"):
    """Download, verify, and decompress SD card image"""
    d = nebula.downloader()
    d.download_sdcard_release(release)


@task(
    help={
        "board_name": "Board configuration name. Ex: zynq-zc702-adv7511-ad9361-fmcomms2-3",
        "source": "Boot file download source. Options are: local_fs, artifactory, remote.\nDefault: local_fs",
        "source_root": "Location of source boot files. Dependent on source.\nFor artifactory sources this is the domain name",
        "branch": "Name of branches to get related files. Default: release",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "filetype": "Selects type of related files to be downloaded. Options: boot (boot_partition files), noos (no-OS files), microblaze (microblaze files), rpi (rpi files), firmware . Default: boot",
        # "boot_partition": "If filetype is boot and boot_partition is True, boot files are downloaded from boot partition folder, else from hdl and linux folders. Default: True "
    },
)
def download_boot_files(
    c,
    source="local_fs",
    source_root=None,
    branch="release",
    yamlfilename="/etc/default/nebula",
    board_name=None,
    filetype="boot_partition",
):
    """Download bootfiles for a specific development system"""
    d = nebula.downloader(yamlfilename=yamlfilename, board_name=board_name)
    try:
        file = {
            "firmware": None,
            "boot_partition": True,
            "noos": None,
            "microblaze": None,
            "rpi": None,
        }
        if filetype == "hdl_linux":
            file["boot_partition"] = False
        else:
            file[filetype] = True
    except Exception:
        raise Exception("Filetype no supported.")

    d.download_boot_files(
        board_name,
        source,
        source_root,
        branch,
        firmware=file["firmware"],
        boot_partition=file["boot_partition"],
        noos=file["noos"],
        microblaze=file["microblaze"],
        rpi=file["rpi"],
    )


dl = Collection("dl")
dl.add_task(download_sdcard, "sdcard")
dl.add_task(download_boot_files, "bootfiles")


#############################################
@task(
    help={
        "repo": "Name of repo",
        "branch": "Git branch name. Default is master",
        "project": "Name of HDL project",
        "board": "Name of development board",
        "def_config": "Kernel def config",
        "githuborg": "Github organization string. Default to analogdevicesinc",
        "vivado_version": "Vivado version (ex: 2018.2). Defaults to determine from source/release",
    },
)
def repo(
    c,
    repo,
    branch="master",
    project=None,
    board=None,
    def_config=None,
    githuborg="analogdevicesinc",
    vivado_version=None,
):
    """Clone and build git project"""
    if vivado_version == "Inherit":
        vivado_version = None
    p = nebula.builder()
    p.vivado_override = vivado_version
    p.analog_clone_build(
        repo,
        branch,
        project,
        board,
        def_config,
        githuborg,
    )


builder = Collection("build")
builder.add_task(repo)


#############################################
@task(
    help={
        "pdutype": "Type of PDU used. Current options: cyberpower, vesync",
        "outlet": "Outlet index of which dev board is connected",
        "pduip": "IP address of PDU (optional)",
        "username": "Username of PDU service (optional)",
        "password": "Password of PDU service (optional)",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def power_cycle(
    c,
    pdutype,
    outlet,
    pduip=None,
    username=None,
    password=None,
    yamlfilename="/etc/default/nebula",
    board_name=None,
):
    """Reboot board with PDU"""
    p = nebula.pdu(
        pdu_type=pdutype,
        pduip=pduip,
        outlet=outlet,
        username=username,
        password=password,
        yamlfilename=yamlfilename,
        board_name=board_name,
    )

    p.power_cycle_board()


pdu = Collection("pdu")
pdu.add_task(power_cycle)


#############################################
@task()
def gen_config(c):
    """Generate YAML configuration interactively"""
    try:
        h = nebula.helper()
        h.create_config_interactive()
        del h
    except Exception as ex:
        print(ex)


@task(
    help={
        "section": "Section of yaml to update",
        "field": "Field of section of yaml to update",
        "value": "New field value. If none if given field is only printed",
        "yamlfilename": "Path to yaml config file. Default: OS_SPECIFIC",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def update_config(
    c, section, field, value=None, yamlfilename=DEFAULT_NEBULA_CONFIG, board_name=None
):
    """Update or read field of existing yaml config file"""
    h = nebula.helper()
    h.update_yaml(
        configfilename=yamlfilename,
        section=section,
        field=field,
        new_value=value,
        board_name=board_name,
    )


@task(
    help={
        "outfile": "Output file name",
        "netbox_ip": "IP of netbox server",
        "netbox_port": "Port netbox is running on the netbox server",
        "netbox_token": "Token for authenticating API requests",
        "netbox_baseurl": "baseurl pointing to netbox instance (if exist)",
        "jenkins_agent": "Target Jenkins agent to generate config to",
        "board_name": "Target board to generate config to, takes higher priority over jenkins_agent",
        "devices_status": "Select only devices with the specified device status defined in netbox",
        "devices_role": "Select only devices with the specified device role defined in netbox",
        "devices_tag": "Select only devices with the specified device tag defined in netbox",
        "template": "Template for config generation",
    },
)
def gen_config_netbox(
    c,
    outfile="nebula",
    netbox_ip="localhost",
    netbox_token="0123456789abcdef0123456789abcdef01234567",
    netbox_port=None,
    netbox_baseurl=None,
    jenkins_agent=None,
    board_name=None,
    devices_status=None,
    devices_role=None,
    devices_tag=None,
    template=None,
):
    """Generate YAML configuration from netbox"""
    h = nebula.helper()
    h.create_config_from_netbox(
        outfile=outfile,
        netbox_ip=netbox_ip,
        netbox_port=netbox_port,
        netbox_baseurl=netbox_baseurl,
        netbox_token=netbox_token,
        jenkins_agent=jenkins_agent,
        board_name=board_name,
        devices_status=devices_status,
        devices_role=devices_role,
        devices_tag=devices_tag,
        template=template,
    )


#############################################
@task(
    help={
        "system_top_bit_path": "Path to system_top.bit",
        "bootbinpath": "Path to BOOT.BIN.",
        "uimagepath": "Path to kernel image.",
        "devtreepath": "Path to devicetree.",
        "folder": "Resource folder containing BOOT.BIN, kernel, device tree, and system_top.bit.\nOverrides other setting",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def update_boot_files_jtag_manager(
    c,
    system_top_bit_path="system_top.bit",
    bootbinpath="BOOT.BIN",
    uimagepath="uImage",
    devtreepath="devicetree.dtb",
    folder=None,
    yamlfilename="/etc/default/nebula",
    board_name=None,
):
    """Update boot files through JTAG (Assuming board is running)"""
    m = nebula.manager(configfilename=yamlfilename, board_name=board_name)
    # m.board_reboot_jtag_uart()

    if not folder:
        m.board_reboot_auto(
            system_top_bit_path=system_top_bit_path,
            bootbinpath=bootbinpath,
            uimagepath=uimagepath,
            devtreepath=devtreepath,
        )
    else:
        m.board_reboot_auto_folder(folder, design_name=board_name, jtag_mode=True)


@task(
    help={
        "system_top_bit_path": "Path to system_top.bit",
        "bootbinpath": "Path to BOOT.BIN.",
        "uimagepath": "Path to kernel image.",
        "devtreepath": "Path to devicetree.",
        "folder": "Resource folder containing BOOT.BIN, kernel, device tree, and system_top.bit.\nOverrides other setting",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
        "sdcard": "No arguments required. If set, reference files is obtained from SD card.",
    },
)
def recovery_device_manager(
    c,
    system_top_bit_path="system_top.bit",
    bootbinpath="BOOT.BIN",
    uimagepath="uImage",
    devtreepath="devicetree.dtb",
    folder=None,
    yamlfilename="/etc/default/nebula",
    board_name=None,
    sdcard=False,
):
    """Recover device through many methods (Assuming board is running)"""
    m = nebula.manager(configfilename=yamlfilename, board_name=board_name)

    if not folder:
        m.board_reboot_auto(
            system_top_bit_path=system_top_bit_path,
            bootbinpath=bootbinpath,
            uimagepath=uimagepath,
            devtreepath=devtreepath,
            recover=True,
        )
    else:
        m.board_reboot_auto_folder(folder, sdcard, design_name=board_name, recover=True)


@task(
    help={
        "vivado_version": "Vivado tool version. Default: 2021.1.",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def check_jtag_manager(
    c,
    vivado_version="2021.1",
    yamlfilename="/etc/default/nebula",
    board_name=None,
):
    """Recover JTAG device"""
    nebula.manager(
        configfilename=yamlfilename,
        board_name=board_name,
        vivado_version=vivado_version,
    )


@task(
    help={
        "system_top_bit_path": "Path to system_top.bit",
        "bootbinpath": "Path to BOOT.BIN.",
        "uimagepath": "Path to kernel image.",
        "devtreepath": "Path to devicetree.",
        "folder": "Resource folder containing BOOT.BIN, kernel, device tree, and system_top.bit.\nOverrides other setting",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def update_boot_files_manager(
    c,
    system_top_bit_path="system_top.bit",
    bootbinpath="BOOT.BIN",
    uimagepath="uImage",
    devtreepath="devicetree.dtb",
    folder=None,
    yamlfilename="/etc/default/nebula",
    board_name=None,
):
    """Update boot files through u-boot menu (Assuming board is running)"""
    m = nebula.manager(configfilename=yamlfilename, board_name=board_name)

    if not folder:
        m.board_reboot_auto(
            system_top_bit_path=system_top_bit_path,
            bootbinpath=bootbinpath,
            uimagepath=uimagepath,
            devtreepath=devtreepath,
        )
    else:
        m.board_reboot_auto_folder(folder, design_name=board_name)


manager = Collection("manager")
manager.add_task(update_boot_files_manager, name="update_boot_files")
manager.add_task(update_boot_files_jtag_manager, name="update_boot_files_jtag")
manager.add_task(recovery_device_manager, name="recovery_device_manager")
manager.add_task(check_jtag_manager, name="check_jtag")


#############################################
@task(
    help={
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist it will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def restart_board_uart(
    c, address="auto", yamlfilename="/etc/default/nebula", board_name=None
):
    """Reboot DUT from UART connection assuming Linux is accessible"""
    try:
        u = nebula.uart(
            address=address, yamlfilename=yamlfilename, board_name=board_name
        )
        u.print_to_console = False
        cmd = "reboot"
        u.get_uart_command_for_linux(cmd, "")
        # if addr:
        #     if addr[-1] == "#":
        #         addr = addr[:-1]
        #     print(addr)
        # else:
        #     print("Address not found")
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist it will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def get_ip(c, address="auto", yamlfilename="/etc/default/nebula", board_name=None):
    """Get IP of DUT from UART connection"""
    #     try:
    # YAML will override
    u = nebula.uart(address=address, yamlfilename=yamlfilename, board_name=board_name)
    u.print_to_console = False
    addr = u.get_ip_address()
    del u
    if addr:
        print(addr)
    else:
        raise Exception("Address not found")


#     except Exception as ex:
#         print(ex)


@task(
    help={
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist it will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def set_local_nic_ip_from_usbdev(
    c, address="auto", yamlfilename="/etc/default/nebula", board_name=None
):
    """Set IP of virtual NIC created from DUT based on found MAC"""
    try:
        import os

        if os.name not in ["nt", "posix"]:
            raise Exception("This command only works on Linux currently")
        u = nebula.uart(
            address=address, yamlfilename=yamlfilename, board_name=board_name
        )
        u.print_to_console = False
        ipaddr = u.get_ip_address()
        if not ipaddr:
            # Try again, sometimes there is junk in terminal
            ipaddr = u.get_ip_address()
        if not ipaddr:
            print("Board IP is not set, must be set first")
            return
        # Get local mac from board
        addr = u.get_local_mac_usbdev()
        addr = addr.replace(":", "")
        addr = addr.replace("\r", "")
        addr = addr.strip()
        # Get IP of virtual nic
        cmd = (
            "ip -4 addr l enx"
            + addr
            + "| grep -v 127 | awk '$1 == \"inet\" {print $2}' | awk -F'/' '{print $1}'"
        )
        out = c.run(cmd)
        local = out.stdout
        local = local.replace("\r", "").replace("\n", "").strip()
        # Compare against local
        ipaddrs = ipaddr.split(".")
        do_not_set = False
        if local:
            remotesub = ".".join(ipaddrs[:-1])
            locals = local.split(".")
            localsub = ".".join(locals[:-1])
            do_not_set = remotesub == localsub
            if do_not_set:
                ipaddrs = local

        if not do_not_set:
            # Create new address
            ipaddrs[-1] = str(int(ipaddrs[-1]) + 9)
            ipaddrs = ".".join(ipaddrs)
            cmd = "ifconfig enx" + addr + " " + ipaddrs
            c.run(cmd)

        print("Local IP Set:", ipaddrs, "Remote:", ipaddr)
        del u
    except Exception as ex:
        raise ex


@task(
    help={
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist it will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def get_carriername(
    c, address="auto", yamlfilename="/etc/default/nebula", board_name=None
):
    """Get Carrier (FPGA) name of DUT from UART connection"""
    try:
        u = nebula.uart(
            address=address, yamlfilename=yamlfilename, board_name=board_name
        )
        u.print_to_console = False
        cmd = "cat /sys/firmware/devicetree/base/model"
        addr = u.get_uart_command_for_linux(cmd, "")
        if addr:
            if addr[-1] == "#":
                addr = addr[:-1]
            addr = addr.split("\x00")
            if "@" in addr[-1]:
                addr = addr[:-1]
            addr = "-".join(addr)
            print(addr)
        else:
            print("Address not found")
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist it will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def get_mezzanine(
    c, address="auto", yamlfilename="/etc/default/nebula", board_name=None
):
    """Get Mezzanine (FMC) name of DUT from UART connection"""
    try:
        u = nebula.uart(
            address=address, yamlfilename=yamlfilename, board_name=board_name
        )
        u.print_to_console = False
        cmd = "find /sys/ -name eeprom | xargs fru-dump -b -i | grep Part Number"
        addr = u.get_uart_command_for_linux(cmd, "")
        if addr:
            if addr[-1] == "#":
                addr = addr[:-1]
            print(addr)
        else:
            print("Address not found")
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist it will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
        "period": "Waiting time in seconds",
    },
)
def get_uart_log(
    c, address="auto", yamlfilename="/etc/default/nebula", board_name=None, period=120
):
    """Read UART boot message on no-OS builds."""
    u = nebula.uart(
        address=address, yamlfilename=yamlfilename, board_name=board_name, period=period
    )
    u.get_uart_boot_message()


@task(
    help={
        "nic": "Network interface name to set. Default is eth0",
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist it will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def set_dhcp(
    c, address="auto", nic="eth0", yamlfilename="/etc/default/nebula", board_name=None
):
    """Set board to use DHCP for networking from UART connection"""
    try:
        u = nebula.uart(
            address=address, yamlfilename=yamlfilename, board_name=board_name
        )
        u.print_to_console = False
        u.request_ip_dhcp()
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "ip": "IP Address to set NIC to",
        "nic": "Network interface name to set. Default is eth0",
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist it will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    },
)
def set_static_ip(
    c,
    ip,
    address="auto",
    nic="eth0",
    yamlfilename="/etc/default/nebula",
    board_name=None,
):
    """Set Static IP address of board of DUT from UART connection"""
    try:
        u = nebula.uart(
            address=address, yamlfilename=yamlfilename, board_name=board_name
        )
        u.print_to_console = False
        u.set_ip_static(ip, nic)
        del u
    except Exception as ex:
        print(ex)


@task(
    help={
        "system_top_bit_filename": "Path to system_top.bit.",
        "uimagepath": "Path to kernel image.",
        "devtreepath": "Path to devicetree.",
        "address": "UART device address (/dev/ttyACMO). If a yaml config exist it will override,"
        + " if no yaml file exists and no address provided auto is used",
        "yamlfilename": "Path to yaml config file. Default: /etc/default/nebula",
        "reboot": "Reboot board from linux console to get to u-boot menu. Default False",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    }
)
def update_boot_files_uart(
    c,
    system_top_bit_filename,
    uimagepath,
    devtreepath,
    address=None,
    yamlfilename="/etc/default/nebula",
    reboot=False,
    board_name=None,
):
    """Update boot files through u-boot menu (Assuming board is running)"""
    u = nebula.uart(address=address, yamlfilename=yamlfilename, board_name=board_name)
    u.print_to_console = False
    if reboot:
        u._write_data("reboot")
        time.sleep(4)
    u.update_boot_files_from_running(
        system_top_bit_filename=system_top_bit_filename,
        kernel_filename=uimagepath,
        devtree_filename=devtreepath,
    )


uart = Collection("uart")
uart.add_task(restart_board_uart, name="restart_board")
uart.add_task(get_ip)
uart.add_task(set_dhcp)
uart.add_task(set_static_ip)
uart.add_task(get_carriername)
uart.add_task(get_mezzanine)
uart.add_task(get_uart_log)
uart.add_task(update_boot_files_uart, name="update_boot_files")
uart.add_task(set_local_nic_ip_from_usbdev)


#############################################
@task(
    help={
        "ip": "IP address of board",
        "user": "Board username. Default: root",
        "password": "Password for board. Default: analog",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    }
)
def check_dmesg(c, ip, user="root", password="analog", board_name=None):
    """Download and parse remote board's dmesg log
    Three log files will be produced:
        dmesg.log - Full dmesg
        dmesg_err.log - dmesg errors only
        dmesg_warn.log - dmesg warnings only
    """
    n = nebula.network(
        dutip=ip, dutusername=user, dutpassword=password, board_name=board_name
    )
    (e, _) = n.check_dmesg()
    if e:
        raise Exception("Errors found in dmesg log. Check dmesg_err.log file")


@task(
    help={
        "ip": "IP address of board",
        "user": "Board username. Default: root",
        "password": "Password for board. Default: analog",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    }
)
def restart_board(c, ip, user="root", password="analog", board_name=None):
    """Reboot development system over IP"""
    n = nebula.network(
        dutip=ip, dutusername=user, dutpassword=password, board_name=board_name
    )
    n.reboot_board(bypass_sleep=True)


@task(
    help={
        "ip": "IP address of board. Default from yaml",
        "user": "Board username. Default: root",
        "password": "Password for board. Default: analog",
        "bootbinpath": "Path to BOOT.BIN. Optional",
        "uimagepath": "Path to kernel image. Optional",
        "devtreepath": "Path to devicetree. Optional",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    }
)
def update_boot_files(
    c,
    ip=None,
    user="root",
    password="analog",
    bootbinpath=None,
    uimagepath=None,
    devtreepath=None,
    board_name=None,
):
    """Update boot files on SD Card over SSH"""
    n = nebula.network(
        dutip=ip, dutusername=user, dutpassword=password, board_name=board_name
    )
    n.update_boot_partition(
        bootbinpath=bootbinpath, uimagepath=uimagepath, devtreepath=devtreepath
    )


@task(
    help={
        "ip": "IP address of board. Default from yaml",
        "user": "Board username. Default: root",
        "password": "Password for board. Default: analog",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
    }
)
def run_diagnostics(
    c,
    ip=None,
    user="root",
    password="analog",
    board_name=None,
):
    """Run adi_diagnostics and fetch result"""
    n = nebula.network(
        dutip=ip, dutusername=user, dutpassword=password, board_name=board_name
    )
    n.run_diagnostics()


@task(
    help={
        "ip": "IP address of board. Default from yaml",
        "user": "Board username. Default: root",
        "password": "Password for board. Default: analog",
        "board_name": "Name of DUT design (Ex: zynq-zc706-adv7511-fmcdaq2). Require for multi-device config files",
        "command": "Shell command to run via ssh. Supports linux systems for now.",
        "ignore_exception": "Ignore errors encountered on the remote side.",
        "retries": "Number of execution attempts",
    }
)
def run_command(
    c,
    ip=None,
    user="root",
    password="analog",
    board_name=None,
    command=None,
    ignore_exception=False,
    retries=3,
):
    """Run command to expand sd card via IP"""
    n = nebula.network(
        dutip=ip, dutusername=user, dutpassword=password, board_name=board_name
    )
    n.run_ssh_command(command, ignore_exception, retries)


net = Collection("net")
net.add_task(restart_board)
net.add_task(update_boot_files)
net.add_task(check_dmesg)
net.add_task(run_diagnostics)
net.add_task(run_command)


#############################################
@task(
    help={
        "level": "Set log level. Default is DEBUG",
    }
)
def show_log(c, level="DEBUG"):
    """Show log for all following tasks"""
    log = logging.getLogger("nebula")
    log.setLevel(getattr(logging, level))
    log = logging.getLogger()
    root_handler = log.handlers[0]
    root_handler.addFilter(MyFilter())
    root_handler.setFormatter(
        logging.Formatter("%(levelname)s | %(name)s : %(message)s")
    )


ns = Collection()
ns.add_task(gen_config)
ns.add_task(show_log)
ns.add_task(update_config)
ns.add_task(gen_config_netbox)

ns.add_collection(builder)
ns.add_collection(uart)
ns.add_collection(net)
ns.add_collection(pdu)
ns.add_collection(manager)
ns.add_collection(dl)
ns.add_collection(cov)
ns.add_collection(driver)
ns.add_collection(info)
ns.add_collection(jtag)
