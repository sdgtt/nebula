import pytest
import os
import nebula
import logging


logging.getLogger().setLevel(logging.INFO)


class MyFilter(logging.Filter):
    def filter(self, record):
        return "nebula" in record.name


def pytest_addoption(parser):
    group = parser.getgroup("nebula")
    group.addoption(
        "--enable-update",
        action="store_true",
        dest="enable_update",
        default=False,
        help="Update boot files and reboot board(s) with nebula",
    )
    group.addoption(
        "--nb-log-level",
        action="store",
        dest="nb_log_level",
        default="ERROR",
        help="Set log level for nebula",
    )


@pytest.fixture(scope="function")
def sd_card_update_boot(request):
    """pytest fixture to update SD card and reboot board(s) with nebula"""
    enable_update = request.config.getoption("--enable-update")
    if not enable_update:
        yield
        return

    marker = request.node.get_closest_marker("nebula_update_boot")

    if not marker:
        yield
        return

    board_name = marker.args[0]
    if not hasattr(pytest, "nebula_boards_booted"):
        pytest.nebula_boards_booted = []
    if board_name not in pytest.nebula_boards_booted:
        pytest.nebula_boards_booted.append(board_name)

        print("Running boot test for board: " + board_name)

        # board_name = "zynq-adrv9364"
        yamlfilename = "/tmp/hw_test/test.yaml"
        folder = "/tmp/hw_test/boot_files"

        import nebula
        import logging

        level = request.config.getoption("--nb-log-level")
        if level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            raise ValueError("Invalid nebula log level: " + level)

        log = logging.getLogger("nebula")
        log.setLevel(getattr(logging, level))
        log = logging.getLogger()
        root_handler = log.handlers[0]
        root_handler.addFilter(MyFilter())
        root_handler.setFormatter(
            logging.Formatter("%(levelname)s | %(name)s : %(message)s")
        )

        # Update SD card over networking
        m = nebula.manager(configfilename=yamlfilename, board_name=board_name)

        m.board_reboot_auto_folder(folder, design_name=board_name)

    else:
        print("Board already booted: " + board_name)

    yield

    print("Generated log files:")

# # Example use
    
# @pytest.mark.nebula_update_boot("zynq-adrv9364")
# def test_boot_hw(sd_card_update_boot):

#     import iio
#     ctx = iio.Context("ip:analog.local")
#     for dev in ctx.devices:
#         print(dev.name)