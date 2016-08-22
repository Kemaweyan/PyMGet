#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from pymget.messages import Messages
from pymget.errors import CancelError
from pymget.console import Console
from pymget.manager import Manager
from pymget.networking import VERSION
from pymget.command_line import CommandLine

def start():

    """
    The main entry point.

    """
    try:
        Messages() # create the Message object to load string constants
    except Exception as e:
        # if failed - print an error message and exit
        print(str(e))
        sys.exit()

    console = Console() # create the Console object
    console.out('\nPyMGet v{}\n'.format(VERSION)) # print an information about program

    try:
        cl = CommandLine(sys.argv)
        cl.parse() # parse command line
        manager = Manager(cl.urls, cl.block_size, cl.filename, cl.timeout) # create the Manager object
        manager.download() # start downloading
    except CancelError as e: # user cancelled downloading
        console.out(str(e))
    except Exception as e: # other errors
        console.error(str(e))
    
