import os
import shutil

import pytest
from nebula import driver


# def remove_file(files):
#     for file in files:
#         if os.path.isfile(file):
#             os.remove(file)
#         if os.path.isfile(file):
#             os.remove(file)
#
#
# @pytest.fixture(autouse=True)
# def run_around_tests():
#     # Before test
#     files = ["dmesg.log", "dmesg_error.log", "dmesg_warn.log"]
#     remove_file(files)
#     yield
#     # After test
#     remove_file(files)


# @pytest.mark.dependency(depends=["test_adrv9361_fmc_get_to_uboot_menu"])
def test_iio_device_check():
    # Get necessary boot files

    # Go go go
    config = "/etc/default/nebula"
    # config = "/etc/nebula/nebula-zynq-adrv9361-z7035-fmc.yaml"
    uri = "ip:192.168.86.35"
    d = driver(yamlfilename=config, uri=uri)
    d.check_iio_devices()


if __name__ == "__main__":
    test_iio_device_check()
