.. nebula documentation master file, created by
   sphinx-quickstart on Thu Mar 26 18:53:29 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Nebula: Embedded Development Tools
=====================================================================

**Nebula** is a utility library designed to aid development with embedded platforms through infrastructure management and orchestration. Targeted at developers working with embedded systems from the desktop or through CI systems, Nebula provides a comprehensive set of tools for board management, boot file deployment, and automated testing.

The majority of the supported functionality is built in pure Python or relies on existing packages built in pure Python, making cross-platform support possible.

Key Features
============

* **Automated Board Management**: Manage development board state through multiple interfaces (UART, Network, JTAG, PDU)
* **Boot File Deployment**: Automate deployment of boot files including u-boot, bitstreams, kernels, and device trees
* **Testing Infrastructure**: Integrate with pytest for automated hardware testing
* **Network Configuration**: Configure board networking through UART or USB interfaces
* **Recovery Mechanisms**: Recover boards from various failure states using multiple fallback methods
* **YAML Configuration**: Flexible configuration system for board definitions and test environments

Interfaces
==========

There are two main interfaces for nebula:

* **Python Module**: For Python projects or projects using Python for testing or tasking, the module interface is designed to complement existing infrastructure to enable boot file deployment automation to development systems.
* **Command-Line Interface (CLI)**: Built on top of invoke, the CLI simplifies common tasks typically done by a developer to build and deploy boot files to a development platform.

Quick Example
=============

Using Nebula as a Python module:

.. code-block:: python

  import nebula

  # Create a manager for your board
  m = nebula.manager(configfilename="board_config.yaml")
  
  # Update boot files on the board
  m.update_boot_files()
  
  # Start tests
  m.start_tests()

Using the CLI:

.. code-block:: bash

  # Update boot files via UART
  nebula uart.update-boot-files --board=pluto
  
  # Get board IP address
  nebula uart.get-ip --board=pluto
  
  # Show supported boards
  nebula info.supported-boards

Getting Started
===============

.. toctree::
   :maxdepth: 1
   :caption: Overview

   Installation <https://github.com/sdgtt/nebula#installation>
   find_config_settings
   hw_devs

.. toctree::
   :maxdepth: 2
   :caption: User Guide

   flow
   pytest
   yml
   examples

.. toctree::
   :maxdepth: 1
   :caption: CLI Reference

   cli

.. toctree::
   :maxdepth: 1
   :caption: API Reference

   core/api

.. toctree::
   :maxdepth: 1
   :caption: Testing

   tests/index


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
