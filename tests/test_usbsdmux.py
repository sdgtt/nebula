import os
import shutil

import pytest

from nebula import pdu, usbmux


@pytest.mark.hardware
@pytest.mark.parametrize("target_mux", ["id-000000001204"])
@pytest.mark.parametrize("board", ["eval-cn0508-rpiz"])
@pytest.mark.parametrize(
    "config",
    [os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-rpi.yaml")],
)
def test_find_mux_device(config, board, target_mux):
    sd = usbmux(
        target_mux=target_mux,
        yamlfilename=config,
        board_name=board,
    )
    assert sd._mux_in_use == os.path.join(sd.search_path, target_mux)


@pytest.mark.hardware
@pytest.mark.parametrize("board", ["eval-cn0508-rpiz"])
@pytest.mark.parametrize(
    "config",
    [os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-rpi.yaml")],
)
def test_find_muxed_sdcard(power_off_dut, config, board):
    sd = usbmux(
        yamlfilename=config,
        board_name=board,
    )
    sd.find_muxed_sdcard()
    assert sd._target_sdcard


@pytest.mark.hardware
@pytest.mark.parametrize("board", ["eval-cn0508-rpiz"])
@pytest.mark.parametrize(
    "config",
    [os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-rpi.yaml")],
)
def test_backup_update_boot_files_external(power_off_dut, config, board):
    sd = usbmux(
        yamlfilename=config,
        board_name=board,
    )
    try:
        destination = "test_backup"
        subfolder = "random"
        if os.path.exists(destination):
            shutil.rmtree(destination)
        folder_b = sd.backup_files_to_external(
            target=[
                "kernel7.img",
                "bcm2710-rpi-3-b-plus.dtb",
                "overlays/rpi-cn0508.dtbo",
                "config.txt",
            ],
            destination=destination,
            subfolder=subfolder,
        )
        assert subfolder == folder_b
        assert os.path.isfile(os.path.join(destination, folder_b, "kernel7.img"))
        assert os.path.isfile(
            os.path.join(destination, folder_b, "bcm2710-rpi-3-b-plus.dtb")
        )
        assert os.path.isfile(os.path.join(destination, folder_b, "rpi-cn0508.dtbo"))
        assert os.path.isfile(os.path.join(destination, folder_b, "config.txt"))

        configs = [
            "dtoverlay=rpi-cn0508",
            "dtparam=rotate=270",
            "dtparam=speed=64000000",
            "dtparam=fps=30",
            "dtparam=spi=on",
            "dtparam=i2c1=on",
            "dtparam=i2c_arm=on",
            "dtoverlay=gpio-shutdown",
            "dtparam=gpio_pin=17",
            "dtparam=active_low=1",
            "dtparam=gpiopull=up",
            "dtparam=act_led_gpio=13",
            "dtparam=act_led_trigger=heartbeat",
        ]
        with open(os.path.join(destination, folder_b, "config.txt"), "a") as f:
            f.write("\n")
            f.write("### Overlay config \n")
            f.write("\n".join(configs))
            f.write("\n")

        sd.update_boot_files_from_external(
            bootbin_loc=None,
            kernel_loc=os.path.join(destination, folder_b, "kernel7.img"),
            devicetree_loc=os.path.join(
                destination, folder_b, "bcm2710-rpi-3-b-plus.dtb"
            ),
            devicetree_overlay_loc=os.path.join(
                destination, folder_b, "rpi-cn0508.dtbo"
            ),
            devicetree_overlay_config_loc=os.path.join(
                destination, folder_b, "config.txt"
            ),
        )

        folder_r = sd.backup_files_to_external(
            partition="root",
            target=[os.path.join("lib", "modules", "5.10.63-v7+")],
            destination=destination,
        )
        assert os.path.isdir(os.path.join(destination, folder_r, "5.10.63-v7+"))

        sd.update_rootfs_files_from_external(
            target=os.path.join(destination, folder_r, "5.10.63-v7+"),
            destination=os.path.join("lib", "modules", "5.10.63-v7+"),
        )

    finally:
        sd.set_mux_mode("off")
