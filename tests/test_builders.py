from nebula import builder
import os
import shutil
import pytest


@pytest.fixture(autouse=True)
def run_around_tests():
    # Before test
    if os.path.isdir("libiio"):
        shutil.rmtree("libiio")
    if os.path.isdir("hdl"):
        shutil.rmtree("hdl")
    yield
    # After test
    if os.path.isdir("libiio"):
        shutil.rmtree("libiio")
    # if os.path.isdir("hdl"):
    #     shutil.rmtree("hdl")


def test_libiio_build():
    b = builder()
    b.analog_clone_build("libiio")
    assert os.path.isfile("libiio/build/libiio.so")


def test_hdl_build():
    b = builder()
    b.analog_clone_build("hdl", "hdl_2018_r2", "fmcomms2", "zed")
    filename = "hdl/projects/fmcomms2/zed/fmcomms2_zed.sdk/system_top.hdf"
    assert os.path.isfile(filename)


#
#
# def test_linux_build():
#     analog_clone_build("linux", "2018_R2")
#     path = ""
#     assert os.path.isfile(path)


if __name__ == "__main__":
    test_libiio_build()
