import os
import shutil

import pytest
from nebula import downloader


@pytest.fixture(autouse=True)
def run_around_tests():
    # Before test
    files = ["2019_R1-2020_02_04.img"]
    for file in files:
        if os.path.isfile(file + ".xz"):
            os.remove(file + ".xz")
        if os.path.isfile(file):
            os.remove(file)
    yield
    # After test
    for file in files:
        if os.path.isfile(file + ".xz"):
            os.remove(file + ".xz")
        if os.path.isfile(file):
            os.remove(file)


def test_default_downloader():
    d = downloader()
    d.download_sdcard_release()
    assert os.path.isfile("2019_R1-2020_02_04.img.xz")
    assert os.path.isfile("2019_R1-2020_02_04.img")


if __name__ == "__main__":
    test_default_downloader()
