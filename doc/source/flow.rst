Managers
========

The manager class is designed to leverage many of the underlying classes (UART, Network, PDF, ...) together to effectively manage the state of development boards. Since in some cases not a single interface can be used to handle all failure modes, the manager class selectively uses the core classes to bring boards up and down, no matter their existing state or cause of failure.

Using Managers
--------------


Boot Flow
---------

Below is the logic used to effectively load a boot files (bitstream, kernel, device tree) and test if the board is ready for driver specific or other tests that require a booted board.

.. graphviz:: updateboot.dot
