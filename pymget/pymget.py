#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from . import __version__
from .errors import CancelError
from .console import Console
from .manager import Manager
from .command_line import CommandLine
from .outfile import OutputFile

class PyMGet:

    """
    A PyMGet application class.

    """
    def __init__(self, argv):
        self.argv = argv
        self.manager = self._manager() # create a manager object
        self.console = self._console() # create the Console object
        self.console.message('\nPyMGet v{}\n'.format(__version__)) # print an information about program

    def run(self):

        """
        Runs an application.

        """
        try:
            self.cl = self._command_line(self.console, self.argv)
            self.cl.parse() # parse command line
            self.outfile = self._outfile(self.console, self.cl.filename) # create an outfile object
            self.manager.prepare(self.console, self.cl, self.outfile) # prepare the manager object
            self.manager.download() # start downloading
        except CancelError as e: # user cancelled downloading
            self.console.message(str(e))
        except Exception as e: # other errors
            self.console.error(str(e))
        except: # never rich this place
            pass

    @property
    def _console(self):
        return Console

    @property
    def _command_line(self):
        return CommandLine

    @property
    def _outfile(self):
        return OutputFile

    @property
    def _manager(self):
        return Manager



def start():

    """
    The main entry point.

    """
    app = PyMGet(sys.argv)
    app.run()
