import pytest

from nebula import pdu, usbmux


def pytest_addoption(parser):
    # register additional options
    parser.addoption(
        "--hardware",
        action="store_true",
        default=None,
        help="Configure pytest to run with hardware setup",
    )


def pytest_configure(config):
    # register additional markers
    config.addinivalue_line("markers", "hardware: Indicates test needs hardware setup")


def pytest_runtest_setup(item):
    # skip tests that needs hardware if not requested
    hw = item.config.getoption("--hardware")
    marks = [mark.name for mark in item.iter_markers()]
    if not hw and "hardware" in marks:
        pytest.skip("Tests requires hardware setup. Use --hardware flag to enable")


@pytest.fixture()
def power_off_dut(param):
    p = pdu(
        board_name=param["board"],
        yamlfilename=param["config"],
    )
    p.power_down_board()
    yield


@pytest.fixture()
def power_on_dut(param):
    p = pdu(
        board_name=param["board"],
        yamlfilename=param["config"],
    )
    p.power_up_board()
    yield


@pytest.fixture()
def sdmux_dutmode(param):
    u = usbmux(
        board_name=param["board"],
        yamlfilename=param["config"],
    )
    u.set_mux_mode(mode="dut")
    yield


@pytest.fixture()
def sdmux_hostmode(param):
    u = usbmux(
        board_name=param["board"],
        yamlfilename=param["config"],
    )
    u.set_mux_mode(mode="host")
    yield


@pytest.fixture()
def sdmux_offmode(param):
    u = usbmux(
        board_name=param["board"],
        yamlfilename=param["config"],
    )
    u.set_mux_mode(mode="off")
    yield
