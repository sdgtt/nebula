import os
import time
import pytest

here = os.path.dirname(os.path.abspath(__file__))
cfg = os.path.join(here, "nebula_config", "nebula-vesync.yaml")

log_folder = os.path.join(here, "logs")
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

def test_vesync_pdu():

    import nebula

    manager = nebula.manager(configfilename=cfg, board_name="vesync_test", monitor_type="")
    assert manager.power is not None, "PDU device not initialized"

    # Test power cycle
    manager.power.power_cycle_board()
    time.sleep(2)
    # Test power down
    manager.power.power_down_board()
    time.sleep(2)
    # Test power up
    manager.power.power_up_board()
    time.sleep(2)
    # Power down
    manager.power.power_down_board()