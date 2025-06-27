Kernel Coverage Testing
=======================

This example will explain how gcov can be used to get coverage traces of specific drivers.


Building the kernel
-------------------

The kernel must be built with certain configurations and enabled and certain Makefiles updated so the specific driver is selected for coverage monitoring. For complete doc look at the `kernel.org doc <https://www.kernel.org/doc/html/v4.14/dev-tools/gcov.html>`_ .

In short, configure the kernel with::

        CONFIG_DEBUG_FS=y
        CONFIG_GCOV_KERNEL=y

select the gcc's gcov format, default is autodetect based on gcc version::

        CONFIG_GCOV_FORMAT_AUTODETECT=y


To select specific drivers or folders update the necessary Makefiles as:

- For a single file (e.g. main.o)::

	GCOV_PROFILE_main.o := y

- For all files in one directory::

	GCOV_PROFILE := y

To exclude files from being profiled even when CONFIG_GCOV_PROFILE_ALL
is specified, use::

	GCOV_PROFILE_main.o := n

and::

	GCOV_PROFILE := n

Only files which are linked to the main kernel image or are compiled as
kernel modules are supported by this mechanism.

Collecting logs and generating HTML reports
-------------------------------------------

Once the remote kernel is booted and tests have been run. To collect the gcov traces and to generate the HTML report use the CLI API::

  nebula coverage.kernel --ip <ip of DUT> --linux_build_dir <Build directory of kernel>


This will create a directory called **html** with the generated html report.

.. note::

  For the reports to be generated correctly the necessary compiler must be on path which was used to build the kernel and lcov must be installed.
