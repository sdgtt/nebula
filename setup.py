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
    python_requires=">=3.6",
    install_requires=["numpy", "pyserial", "fabric", "yaml", "pysnmp"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
)
