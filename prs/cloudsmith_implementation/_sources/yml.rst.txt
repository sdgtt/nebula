Configuration
=============

Main configuration is done through a main YAML file. If sections are not filled out they will be not set at run-time unless set on the command-line. Not setting certain parameters may limit functionality since some interfaces are required in certain board failure modes. Below is a complete example with documentation for each setting.

.. literalinclude:: ../../resources/nebula-zc706-daq2.yaml
   :language: yaml

Each section of the yaml file applies to specific classes of nebula, and follow the convention *<classname>*\ **-config**, except for system. Therefore, you can modify any class property during initialization through the yaml file. For example if you wanted to change the *bootargs* setting, which is the kernel bootargs set over UART, you would have the following in your yaml:

.. code-block:: yaml

   uart-config:
     - bootargs: console=ttyPS0,115200 root=/dev/mmcblk0p2 rw earlycon rootfstype=ext4 rootwait

If settings exist in the yaml file within a **-config** block that does not has an existing property, this will cause an exception. This is designed to avoid defining settings which do not change behavior.


Generation
----------

If you use the CLI interface through the **nebula gen-config** command to interactively generate this yaml file.
