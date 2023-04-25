import pytest
from nebula import pdu


@pytest.fixture()
def power_off_dut(config, board):
    p = pdu(
        yamlfilename=config,
        board_name=board,
    )
    p.power_down_board()
    yield
