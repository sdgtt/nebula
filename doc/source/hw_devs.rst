Hardware Specific Configurations
################################

Sometimes specialized devices are used to control and manage hardware components. This pages discusses how such devices should be setup and controlled.

USB-SD-Mux from Linux Automation
================================

The USB-SD-Mux is an awesome tool that can mux SD cards into development boards. The main doc for the device is located at `linux-automation.com <https://linux-automation.com/en/products/usb-sd-mux.html>`_.

.. image:: https://linux-automation.com/media/pages/products/usb-sd-mux/usb-sd-mux.jpg
   :target: https://linux-automation.com/media/pages/products/usb-sd-mux/usb-sd-mux.jpg
   :alt: usb-sd-mux
   :align: center
   :width: 70%

Preparing host system
---------------------

It is recommended to first install the udev rules for the mux, which will make referencing the mux easier. To do this, run the following commands:

.. code-block:: bash

    git clone https://github.com/pengutronix/usbsdmux.git
    cd usbsdmux
    sudo cp contrib/udev/99-usbsdmux.rules /etc/udev/rules.d/
    sudo udevadm control --reload-rules

When you connect the mux it will be accessible now through sysfs under **/dev/usb-sd-mux**

.. code-block::

    $ ls /dev/usb-sd-mux/
    id-000000001143

If you want to manually control the mux follow the `documentation here <https://www.linux-automation.com/usbsdmux-M01/product-comissioning.html#quickstart>`_.

Special DUT Specific Settings
-----------------------------

Since the SD card will be used through a mux at the DUT, it is necessary in some cases to adjust the devicetree. Otherwise the SD card will not be recognized.

Xilinx Carriers
^^^^^^^^^^^^^^^

To correctly mount the rootfs the following must be added to the mmc@ff160000 and mmc@ff170000 node in the devicetree:

.. code::block::

    mmc@ff160000 {
        ...
        no-1-8-v;
        ...
    };

    mmc@ff170000 {
        ...
        no-1-8-v;
        ...
    };

This is handled automatically by nebula from the CLI or the **update_devicetree_for_mux** method in the usbmux class.
