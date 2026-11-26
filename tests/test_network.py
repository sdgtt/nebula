import os
import shutil
import time
from types import SimpleNamespace
from unittest import mock

import pytest

from nebula import helper as helper
from nebula import network, pdu, uart


def remove_file(files):
    for file in files:
        if os.path.isfile(file):
            os.remove(file)
        if os.path.isfile(file):
            os.remove(file)


@pytest.fixture(autouse=True)
def run_around_tests():
    # Before test
    files = ["dmesg.log", "dmesg_error.log", "dmesg_warn.log"]
    remove_file(files)
    yield
    # After test
    remove_file(files)


# @pytest.mark.skip(reason="Not fully implemented")
# @pytest.mark.dependency(depends=["test_adrv9361_fmc_get_to_uboot_menu"])
def test_adrv9361_fmc_network_update():
    # Get necessary boot files
    root = os.path.dirname(os.path.realpath(__file__))
    bootbinpath = root + "/bootfiles/BOOT.BIN"
    devtree_filename = root + "/bootfiles/devicetree.dtb"
    kernel_filename = root + "/bootfiles/uImage"
    assert os.path.isfile(bootbinpath)
    assert os.path.isfile(devtree_filename)
    assert os.path.isfile(kernel_filename)

    # Go go go
    config = "/etc/default/nebula"
    config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
    n = network(yamlfilename=config)
    n.dutip = "192.168.86.35"
    n.update_boot_partition(bootbinpath, devtree_filename, kernel_filename)
    # n.update_boot_partition_existing_files(subfolder="zynq-adrv9361-z7035-fmc")
    time.sleep(60)
    n.check_board_booted()  # WILL RAISE ON ERROR

    # Check board booted :)


# @pytest.mark.dependency(depends=["test_adrv9361_fmc_get_to_uboot_menu"])
def test_adrv9361_fmc_network_update_existing_files():
    # Get necessary boot files
    root = os.path.dirname(os.path.realpath(__file__))
    bootbinpath = root + "/bootfiles/BOOT.BIN"
    devtree_filename = root + "/bootfiles/devicetree.dtb"
    kernel_filename = root + "/bootfiles/uImage"
    assert os.path.isfile(bootbinpath)
    assert os.path.isfile(devtree_filename)
    assert os.path.isfile(kernel_filename)

    # Go go go
    config = "/etc/default/nebula"
    config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
    n = network(yamlfilename=config)
    n.dutip = "192.168.86.35"
    n.update_boot_partition_existing_files(subfolder="zynq-adrv9361-z7035-fmc")
    time.sleep(60)
    n.check_board_booted()  # WILL RAISE ON ERROR

    # Check board booted :)


# @pytest.mark.dependency(depends=["test_adrv9361_fmc_get_to_uboot_menu"])
def test_dmesg_read():
    # Get necessary boot files

    # Go go go
    config = "/etc/default/nebula"
    # config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
    n = network(yamlfilename=config)
    n.dutip = "192.168.86.35"
    (e, log) = n.check_dmesg()

    assert os.path.isfile("dmesg.log")
    assert os.path.isfile("dmesg_warn.log")
    assert os.path.isfile("dmesg_err.log")


def test_update_boot_partition_existing_files():
    # generate nebula config for zynq-adrv9361-z7035-fmc
    outfile = "resources/nebula-zynq-adrv9361-z7035-fmc.yml"
    board_name = "zynq-adrv9361-z7035-fmc"
    h = helper()
    h.create_config_from_netbox(
        outfile=outfile,
        netbox_ip="192.168.10.11",
        netbox_port="8000",
        netbox_baseurl="netbox",
        netbox_token="0123456789abcdef0123456789abcdef01234567",
        board_name=board_name,
    )

    # initialize network object
    n = network(yamlfilename=outfile, board_name=board_name)
    n.check_board_booted()
    n.update_boot_partition_existing_files(subfolder=board_name)
    time.sleep(60)
    n.check_board_booted()


SYSTEMD_UNITS = (
    "cron.service loaded active running Regular background program processing daemon\r\n"
    "iiod.service loaded failed failed IIO Daemon\r\n"
    "networking.service loaded active exited Raise network interfaces\r\n"
    "rsync.service loaded inactive dead fast remote file copy program daemon\r\n"
    "plymouth-start.service not-found inactive dead plymouth-start.service\r\n"
)
SYSTEMD_ENABLED = "cron.service enabled enabled\r\niiod.service enabled enabled\r\n"


def fake_systemctl(command, **kwargs):
    if "list-units" in command:
        stdout = SYSTEMD_UNITS
    elif "list-unit-files" in command:
        stdout = SYSTEMD_ENABLED
    else:
        stdout = "degraded\r\n"
    return SimpleNamespace(stdout=stdout)


def test_check_systemd_parse(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    n = network(dutip="0.0.0.0", yamlfilename=str(tmp_path / "none.yaml"))
    with mock.patch.object(network, "run_ssh_command", side_effect=fake_systemctl):
        (e, logs) = n.check_systemd()

    assert e
    assert logs["state"] == "degraded"
    assert logs["counts"] == {
        "active": 2,
        "running": 1,
        "inactive": 1,
        "failed": 1,
        "not_found": 1,
        "enabled": 2,
    }
    assert [u["unit"] for u in logs["failed"]] == ["iiod.service"]
    assert [u["unit"] for u in logs["inactive"]] == ["rsync.service"]
    for f in [
        "systemd_services.log",
        "systemd_failed.log",
        "systemd_inactive.log",
        "systemd_enabled.log",
    ]:
        assert os.path.isfile(f)
    with open("systemd_failed.log") as f:
        assert f.read().startswith("iiod.service")


def test_check_systemd_skips_pluto(tmp_path):
    n = network(
        dutip="0.0.0.0", yamlfilename=str(tmp_path / "none.yaml"), board_name="pluto"
    )
    with mock.patch.object(network, "run_ssh_command") as run:
        assert n.check_systemd() == (False, {})
    run.assert_not_called()


if __name__ == "__main__":
    test_adrv9361_fmc_network_update()
