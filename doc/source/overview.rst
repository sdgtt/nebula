Overview
============

Nebula is a utility library design to aid development with embedded platforms through infrastructure management and orchestration. Targeted at using systems from the desktop as a standard developer or through a CI system. The majority of the supported functionality is built in pure python, or relies on existing packages built in pure python, making cross-platform support possible.

There are two main interfaces for nebula:

 * **Module**: For python projects or projects using python for testing or tasking, the module interface is designed to complement existing infrastructure to enable boot file (uboot, bitstream, kernel) deployment automation to development systems.
 * **CLI**: Built on top of invoke, the command-line interface simplifies common tasks typically done by a developer to build and deploy boot files to a development platform
