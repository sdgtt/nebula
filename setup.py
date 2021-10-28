import re

import setuptools


# From: https://github.com/smartcar/python-sdk/blob/master/setup.py
def _get_version():
    """Extract version from package."""
    with open("nebula/__init__.py") as reader:
        match = re.search(
            r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', reader.read(), re.MULTILINE
        )
        if match:
            return match.group(1)
        else:
            raise RuntimeError("Unable to extract version.")


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="nebula",
    version=_get_version(),
    author="Travis Collins",
    author_email="travis.collins@analog.com",
    description="Testing harness for FPGA hardware",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tfcollins/nebula",
    packages=setuptools.find_packages(),
    package_data={
        "nebula": ["resources/template_gen.yaml", "resources/board_table.yaml", "resources/err_rejects.txt", "resources/noOS_projects.yaml"]
    },
    include_package_data=True,
    python_requires=">=3.6",
    install_requires=[
        "numpy",
        "pyserial",
        "fabric",
        "pyyaml",
        "pysnmp",
        "invoke",
        "xmodem",
        "pytest",
        "pyvesync_v2",
        "pyfiglet",
    ],
    entry_points={"console_scripts": ["nebula = nebula.main:program.run"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
)
