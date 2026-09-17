.. nebula documentation master file, created by
   sphinx-quickstart on Thu Mar 26 18:53:29 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to nebula's documentation!
==================================

Nebula is a utility library design to aid development with embedded platforms through infrastructure management and orchestration. Targeted at using systems from the desktop as a standard developer or through a CI system. The majority of the supported functionality is built in pure python, or relies on existing packages built in pure python, making cross-platform support possible.

There are two main interfaces for nebula:

 * **Module**: For python projects or projects using python for testing or tasking, the module interface is designed to complement existing infrastructure to enable boot file (uboot, bitstream, kernel) deployment automation to development systems.
 * **CLI**: Built on top of invoke, the command-line interface simplifies common tasks typically done by a developer to build and deploy boot files to a development platform



.. toctree::
   :maxdepth: 2
   :caption: Contents:

   flow
   cli
   pytest
   yml
   hw_devs
   tests/index
   examples
   core/nebula



Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
