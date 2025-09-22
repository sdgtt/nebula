# Defining Configuration Settings

Configuration settings for Nebula can be defined in YAML files. These settings allow you to customize various aspects of Nebula's behavior, including hardware interfaces, drivers, and logging options. However, they can be complex to define correctly.

## UART Configuration

To configure UART settings, you can specify parameters such as the device address, baud rate, and log filename. For example:

```yaml
uart-config:
- address: /dev/serial/by-path/pci-0000:00:14.0-usb-0:8.1.1:1.0-port0
- baudrate: '115200'
- logfilename: vcu118.log
```

It is recommended to use the `/dev/serial/by-path/...` path for the UART address, as it is more stable across reboots compared to `/dev/ttyUSB*` or `/dev/ttyACM*`.

To find the correct UART device path, you can use the following command:

```bash
ls -l /dev/serial/by-id
total 0
lrwxrwxrwx 1 root root 13 Sep 16 18:05 usb-Silicon_Labs_CP2105_Dual_USB_to_UART_Bridge_Controller_008116FD-if00-port0 -> ../../ttyUSB1
lrwxrwxrwx 1 root root 13 Sep 16 18:05 usb-Silicon_Labs_CP2105_Dual_USB_to_UART_Bridge_Controller_008116FD-if01-port0 -> ../../ttyUSB2
```


## JTAG Configuration

To configure JTAG settings, you can specify parameters such as the Vivado version and JTAG cable ID. For example:

```yaml
jtag-config:
- vivado_version: '2023.2'
- jtag_cable_id: 210308A3BB8D
- jtag_cpu_target_name: ARM*#0
- jtag_connect_retries: 3 # Optional, default is 3
```

To get the JTAG cable ID, you can use the `xsdb` tool:

```bash
xsdb

****** System Debugger (XSDB) v2023.2
  **** Build date : Oct 13 2023-20:26:23
    ** Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
    ** Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.


xsdb% connect
tcfchan#0
xsdb% jtag targets
  1  Digilent JTAG-SMT2NC 210308A3BB8D
     2  xcvu9p (idcode 14b31093 irlen 18 fpga)
        3  bscan-switch (idcode 04900101 irlen 1 fpga)
           4  debug-hub (idcode 04900220 irlen 1 fpga)

```

You can see the JTAG cable ID in the output (e.g., `210308A3BB8D`).

The `jtag_cpu_target_name` is used to target the ARM or MicroBlaze CPU in the FPGA design. It is common to use a wildcard (`*`) to match the CPU name, as it may vary between designs. Here are some examples:
- For ARM CPUs: `ARM*#0`
- For MicroBlaze CPUs: `MicroBlaze*#0`

