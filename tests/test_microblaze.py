"""Test MicroBlaze target with JTAG and UART interface"""

import os
import time
import pytest

here = os.path.dirname(os.path.abspath(__file__))
cfg = os.path.join(here, "nebula-microblaze.yaml")
ref_boot_folder = os.path.join(here, "microblaze_boot_files")

log_folder = os.path.join(here, "logs")
if not os.path.exists(log_folder):
    os.makedirs(log_folder)

def test_microblaze_boot():

    # Check boot files exist
    bitstream = os.path.join(ref_boot_folder, "system_vcu118.bit")
    strip = os.path.join(ref_boot_folder, "vcu118.strip")
    assert os.path.isfile(bitstream), "Bitstream file not found"
    assert os.path.isfile(strip), "Strip file not found"

    import nebula

    manager = nebula.manager(yamlfilename=cfg, board_name="vcu118")
    # Start UART logging
    manager.monitor[0].log_filename = os.path.join(log_folder, "vcu118_uart.log")
    manager.monitor[0]._read_until_stop()  # Flush
    manager.monitor[0].start_log(logappend=True)
    manager.monitor[0].print_to_console = True
    # manager.monitor[0]._attemp_login("root", "root")
    manager.monitor[0]._read_until_stop()  # Flush

    # Boot the board
    manager.jtag.microblaze_boot_linux(bitstream, strip)