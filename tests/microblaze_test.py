import os
import shutil
import time

import pytest

import nebula
from nebula import downloader, network

here = os.path.dirname(os.path.abspath(__file__))
cfg = os.path.join(here, "nebula_config", "microblaze.yaml")
out_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outs")
log_folder = os.path.join(here, "logs")
if not os.path.exists(log_folder):
    os.makedirs(log_folder)
manager = nebula.manager(
    configfilename=cfg, board_name="kcu105_adrv9371x", microblaze=True
)


def test_microblaze_downloader():
    # Clean output folder
    if os.path.isdir(out_folder):
        shutil.rmtree(out_folder)

    d = downloader(yamlfilename=cfg, board_name="kcu105_adrv9371x")
    d.download_boot_files(
        "kcu105_adrv9371x",
        source="artifactory",
        source_root="artifactory.analog.com",
        branch="main",
        microblaze=True,
    )

    assert os.path.isfile(os.path.join("/root/wk_ace/nebula/outs/", "system_top.bit"))
    assert os.path.isfile(
        os.path.join("/root/wk_ace/nebula/outs/", "simpleImage.strip")
    )
    assert os.path.isfile(os.path.join("/root/wk_ace/nebula/outs/", "hashes.txt"))
    # assert os.path.isfile(os.path.join("/root/wk_ace/nebula/outs/", "properties.yaml"))


def test_microblaze_boot():
    # Use files from outs folder
    bitstream = os.path.join("/root/wk_ace/nebula/outs/", "system_top.bit")
    strip = os.path.join("/root/wk_ace/nebula/outs/", "simpleImage.strip")
    assert os.path.isfile(bitstream), "Bitstream file not found"
    assert os.path.isfile(strip), "Strip file not found"

    manager = nebula.manager(configfilename=cfg, board_name="kcu105_adrv9371x")
    manager.monitor[0].logfilename = os.path.join(
        log_folder, "kcu105_adrv9371x"
    )  # Flush

    # boot microblaze board
    manager.board_reboot_auto_folder(out_folder, microblaze=True)


# @pytest.mark.stress
def test_microblaze_network():
    # test SSH connection and dmesg check for microblaze
    manager.monitor[0].logfilename = os.path.join(
        log_folder, "kcu105_adrv9371x"
    )  # Flush
    net = network(
        yamlfilename=cfg, board_name="kcu105_adrv9371x", dutip=manager.net.dutip
    )
    net.check_dmesg()
