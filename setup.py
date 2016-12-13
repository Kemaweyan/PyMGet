#!/usr/bin/env python3

import os
from pythongettext.msgfmt import Msgfmt
from setuptools import setup, find_packages
from distutils.command.build import build as _build
from distutils import cmd
import pymget

class build_translations(cmd.Command):
    description = 'Compiles .pot files impto .mo'

    user_options = [
            ('build-lib', None, "lib build folder")
    ]

    def initialize_options(self):
        self.build_lib = None

    def finalize_options(self):
        self.set_undefined_options('build', ('build_lib', 'build_lib'))

    def run(self):
        pot_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'pymget', 'i18n')

        for path, dirs, files in os.walk(pot_dir):
            for f in files:

                if not f.endswith('.pot'):
                    continue

                lang = os.path.splitext(f)[0]
                src = os.path.join(path, f)
                dest_path = os.path.join(self.build_lib, 'pymget', 'i18n', lang, 'LC_MESSAGES')
                dest = os.path.join(dest_path, 'messages.mo')

                if not os.path.exists(dest_path):
                    os.makedirs(dest_path)

                with open(dest, 'wb') as mo_file:
                    msg_fmt = Msgfmt(src)
                    mo_data = msg_fmt.get()
                    mo_file.write(mo_data)


class build(_build):
    sub_commands = [('build_translations', None)] + _build.sub_commands

    def run(self):
        _build.run(self)


cmdclass = {
    'build': build,
    'build_translations': build_translations,
}



entry_points = {
    "console_scripts": [
        "pymget=pymget.pymget:start"
    ]
}

setup(
    name = "pymget",
    version = pymget.__version__,
    fullname = "PyMGet",
    description = "Utility for parallel downloading files from multiple mirrors",
    author = "Taras Gaidukov",
    author_email = "kemaweyan@gmail.com",
    keywords = "downloading mirros parallel",
    long_description = open('README').read(),
    url = "http://pymget.sourceforge.net/",
    license = "GPLv3",
    cmdclass = cmdclass,
    package_data = {"pymget": ["i18n/*/LC_MESSAGES/*.mo"]},
    packages=find_packages(exclude=["tests"]),
    entry_points=entry_points,
    test_suite='tests',
    install_requires=['python-gettext>=3.0']
)
