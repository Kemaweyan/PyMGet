#!/usr/bin/env python3

from setuptools import setup, find_packages

entry_points = {
    "console_scripts": [
        "pymget=pymget.pymget:start"
    ]
}

setup(
    name = "pymget",
    version = "1.34",
    fullname = "PyMGet",
    description = "Utility for parallel downloading files from multiple mirrors",
    author = "Taras Gaidukov",
    author_email = "kemaweyan@gmail.com",
    keywords = "downloading mirros parallel",
    long_description = """The program is designed for parallel download files from multiple mirrors.
                        Supported protocols: HTTP, HTTPS, FTP.""",
    url = "http://pymget.sourceforge.net/",
    license = "GPLv3",
    package_data = {"pymget": ["i18n/*.xml"]},
    packages=find_packages(),
    entry_points = entry_points
)
