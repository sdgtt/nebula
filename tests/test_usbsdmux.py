import os
import shutil

import pytest
from nebula import pdu, usbmux


@pytest.mark.hardware
@pytest.mark.parametrize(
    "param",[
        {
            "board":"eval-cn0508-rpiz",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-rpi.yaml"),
            "target_mux": "id-000000001204",           
        },
    ]
)
def test_find_mux_device(param):
    sd = usbmux(
        board_name=param["board"],
        yamlfilename=param["config"],
        target_mux=param["target_mux"],
    )
    assert sd._mux_in_use == os.path.join(sd.search_path, param["target_mux"])


@pytest.mark.hardware
@pytest.mark.parametrize(
    "param",[
        {
            "board": "eval-cn0508-rpiz",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-rpi.yaml"),
        },
        {
            "board": "socfpga_cyclone5_de10_nano_cn0540",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-manager-usbmux.yml"),            
        }
    ]
)
def test_find_muxed_sdcard(power_off_dut, param):
    sd = usbmux(
        board_name=param["board"],
        yamlfilename=param["config"],
    )
    sd.find_muxed_sdcard()
    assert sd._target_sdcard


@pytest.mark.hardware
@pytest.mark.parametrize(
    "param",[
        {
            "board":"socfpga_cyclone5_de10_nano_cn0540",
            "config": os.path.join(os.path.dirname(__file__),"nebula_config","nebula-manager-usbmux.yml"),
            "files": [
                os.path.join("socfpga_cyclone5_de10_nano_cn0540","soc_system.rbf"),
                os.path.join("socfpga_cyclone5_common","zImage"),
                os.path.join("socfpga_cyclone5_de10_nano_cn0540","socfpga.dtb"),
                os.path.join("socfpga_cyclone5_de10_nano_cn0540","extlinux.conf"),
                os.path.join("socfpga_cyclone5_de10_nano_cn0540","u-boot.scr"),
                os.path.join("socfpga_cyclone5_de10_nano_cn0540","u-boot-with-spl.sfp"),
            ]

        },
    ]
) 
def test_backup_files_to_external(power_off_dut, param):
    sd = usbmux(
        board_name=param["board"],
        yamlfilename=param["config"],
    )
    try:
        sd.find_muxed_sdcard()
        assert sd._target_sdcard
        sd.backup_files_to_external(
            partition="boot",
            destination="backup",
            target=param["files"],
            subfolder=param["board"]
        )
    finally:
        sd.set_mux_mode("off")

@pytest.mark.hardware
@pytest.mark.parametrize(
    "param",[
        {
            "board":"socfpga_cyclone5_de10_nano_cn0540",
            "config": os.path.join(os.path.dirname(__file__),"nebula_config","nebula-manager-usbmux.yml"),
            "files": {
                "bootbin_loc": os.path.join("socfpga_cyclone5_de10_nano_cn0540","soc_system.rbf"),
                "kernel_loc": os.path.join("socfpga_cyclone5_common","zImage"),
                "devicetree_loc": os.path.join("socfpga_cyclone5_de10_nano_cn0540","socfpga.dtb"),
                "extlinux_loc": os.path.join("socfpga_cyclone5_de10_nano_cn0540","extlinux.conf"),
                "scr_loc": os.path.join("socfpga_cyclone5_de10_nano_cn0540","u-boot.scr"),
                "preloader_loc": os.path.join("socfpga_cyclone5_de10_nano_cn0540","u-boot-with-spl.sfp"),
            }
        },
    ]
)
def test_update_boot_files_from_sdcard_itself(power_off_dut, param):
    sd = usbmux(
        board_name=param["board"],
        yamlfilename=param["config"],
    )
    try:
        sd.find_muxed_sdcard()
        assert sd._target_sdcard
        sd.update_boot_files_from_sdcard_itself(
            **param["files"]
        )
    finally:
        sd.set_mux_mode("off")

@pytest.mark.hardware
@pytest.mark.parametrize(
    "param",[
        {
            "board" : "eval-cn0508-rpiz",
            "config": os.path.join(os.path.dirname(__file__), "nebula_config", "nebula-rpi.yaml"),
            "files":{
                "kernel_loc": os.path.join("kernel7.img"),
                "devicetree_loc": os.path.join("bcm2710-rpi-3-b-plus.dtb"),
                "devicetree_overlay_loc" : os.path.join("overlays","rpi-cn0508.dtbo"),
                "devicetree_overlay_config_loc" : os.path.join("config.txt"),
            },
            "modules" : "5.15.92-v7+",
            "config_param" : [
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
        },
        {
            "board":"socfpga_cyclone5_de10_nano_cn0540",
            "config": os.path.join(os.path.dirname(__file__),"nebula_config","nebula-manager-usbmux.yml"),
            "files": {
                "bootbin_loc": os.path.join("socfpga_cyclone5_de10_nano_cn0540","soc_system.rbf"),
                "kernel_loc": os.path.join("socfpga_cyclone5_common","zImage"),
                "devicetree_loc": os.path.join("socfpga_cyclone5_de10_nano_cn0540","socfpga.dtb"),
                "extlinux_loc": os.path.join("socfpga_cyclone5_de10_nano_cn0540","extlinux.conf"),
                "scr_loc": os.path.join("socfpga_cyclone5_de10_nano_cn0540","u-boot.scr"),
                "preloader_loc": os.path.join("socfpga_cyclone5_de10_nano_cn0540","u-boot-with-spl.sfp"),
            }
        },
    ]
)
def test_backup_update_boot_files_external(power_off_dut, param):
    sd = usbmux(
        board_name=param["board"],
        yamlfilename=param["config"],
    )
    try:
        destination = "test_backup"
        subfolder = param["board"]
        if os.path.exists(destination):
            shutil.rmtree(destination)
        folder_b = sd.backup_files_to_external(
            target=[ file for file in param["files"].values()],
            destination=destination,
            subfolder=subfolder,
        )
        assert subfolder == folder_b
        for target_file in [ file for file in param["files"].values()]:
            assert os.path.isfile(os.path.join(destination, folder_b, os.path.basename(target_file)))

        if "config_param" in param:
            with open(os.path.join(destination, folder_b, "config.txt"), "a") as f:
                f.write("\n")
                f.write("### Overlay config \n")
                f.write("\n".join(param["config_param"]))
                f.write("\n")

        target_files = dict()
        for _file, _loc in param["files"].items():
            target_files.update({_file : os.path.join(destination, folder_b, os.path.basename(_loc))})

        sd.update_boot_files_from_external(
            **target_files
        )

        if "modules" in param and param["modules"]:
            folder_r = sd.backup_files_to_external(
                partition="root",
                target=[os.path.join("lib", "modules", param["modules"])],
                destination=destination,
                subfolder=subfolder
            )
            assert subfolder == folder_r
            assert os.path.isdir(os.path.join(destination, folder_r, param["modules"]))

            sd.update_rootfs_files_from_external(
                target=os.path.join(destination, folder_r, param["modules"]),
                destination=os.path.join("lib", "modules", param["modules"]),
            )

    finally:
        sd.set_mux_mode("off")
