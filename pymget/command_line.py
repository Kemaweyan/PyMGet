#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os
import re, textwrap

from pymget.networking import URL
from pymget.console import Console
from pymget.messages import Messages
from pymget.errors import CommandLineError

class CommandLine:

    """
    Reads arguments in the command line and
    executes required actions.

    """
    def __init__(self, argv):

        """
        :argv: a sequence of argument, elements type str

        """
        self.lang = Messages()
        self.argv = argv[1:] # the first argument is a name of program, pass it
        self.block_size = 4 * 2**20 # default block size is 4MB
        self.filename = '' # filename is unknown
        self.timeout = 10 # default timeout is 10 seconds
        self.urls = [] # the list of mirros is empty
        # pattern to search URLs
        self.url_re = re.compile('^(?:https?|ftp)://(?:[\w\.-]+(?::\d+)?)/')
        self.console = Console()

    def show_help(self):

        """
        Shows the help message and terminates program.

        """
        import __main__
        # use __main__ module to define real program name 
        self.console.out(textwrap.dedent(self.lang.message.help.format(os.path.basename(__main__.__file__))))
        sys.exit()

    def parse_block_size(self, block_size):

        """
        Parses an argument of block size.

        :block_size: value of argument, type str

        """
        bs_re = re.compile('(\d+)(\w)?') # pattern for argument "number + (optional) "char"
        matches = bs_re.match(block_size)
        if not matches: # argument does not mutch - wrong argument
            raise CommandLineError(self.lang.error.wrong_argument + self.lang.error.wrong_param.format('block size', block_size))
        self.block_size = int(matches.group(1)) # assign to block size a value of number
        if matches.group(2): # there is a char in the parameter
            if matches.group(2) in 'kK': # k or K
                self.block_size *= 2**10 # that's kilobytes
            elif matches.group(2) in 'mM': # m or M
                self.block_size *= 2**20 # that's megabytes
            else:
                # not m, M, k or K - wrong argument
                raise CommandLineError(self.lang.error.wrong_argument + self.lang.error.wrong_param.format('block size', block_size))

    def parse_timeout(self, timeout):

        """
        Parses an argument of timeout

        :timeout: value of argument, type str

        """
        if not timeout.isdigit(): # parameter is not a number - wrong argument
            raise CommandLineError(self.lang.error.wrong_argument + self.lang.error.wrong_param.format('timeout', timeout))
        self.timeout = int(timeout) # assign timeout

    def parse_urls_file(self, urls_file):

        """
        Parses a file with a list of URLs

        :urls_file: value of parameter (filename), type str

        """
        try:
            urls = []
            with open(urls_file, 'r') as links: # try to open the file in text mode
                # add each line to list without newline symbols
                for link in links:
                    urls.append(link.strip('\r\n'))
            self.urls.extend(urls) # add these URLs to the list of URLs from command line
        except FileNotFoundError:
            raise CommandLineError(self.lang.error.file_not_found.format(urls_file))
        except PermissionError:
            raise CommandLineError(self.lang.error.links_permission_denied.format(urls_file))
        except UnicodeDecodeError: # specified file is not a correct text file
            raise CommandLineError(self.lang.error.corrupted_file.format(urls_file))
     
    def parse_out_file(self, filename):

        """
        Parses a name of output file

        :filename: value of parameter, type str

        """
        self.filename = filename

    def parse_long_arg(self, arg):

        """
        Parses arguments in long format --arg=value

        :arg: an argument, type str

        """
        name, param = arg.split('=') # split by =
        return param # return the second part

    def parse(self):

        """
        Parses the command line

        """
        args_iterator = iter(self.argv) # create an iterator
        # to have access to next() to get parameters of arguments
        for arg in args_iterator:
            if arg == '-h' or arg == '--help':
                self.show_help() # show the help message
            if arg == '-v' or arg == '--version':
                sys.exit() # the version info already shown, just exit
            elif arg == '-b':
                # parse block size, pass next item to the method
                self.parse_block_size(next(args_iterator))
            elif arg == '-T':
                # parse timeout, pass next item to the method
                self.parse_timeout(next(args_iterator))
            elif arg == '-u':
                # parse URLs file, pass next item to the method
                self.parse_urls_file(next(args_iterator))
            elif arg == '-o':
                # parse the name of outfile, pass next item to the method
                self.parse_out_file(next(args_iterator))
            elif arg.startswith('--block-size='):
                # parse block size, get parameter from long argument
                self.parse_block_size(self.parse_long_arg(arg))
            elif arg.startswith('--timeout='):
                # parse timeout, get parameter from long argument
                self.parse_timeout(self.parse_long_arg(arg))
            elif arg.startswith('--urls-file='):
                # parse URLs file, get parameter from long argument
                self.parse_urls_file(self.parse_long_arg(arg))
            elif arg.startswith('--out-file='):
                # parse the name of outfile, get parameter from long argument
                self.parse_out_file(self.parse_long_arg(arg))
            elif self.url_re.match(arg): # argument matches the URL pattern
                self.urls.append(arg) # add it to the list of URLs
            else:
                # argument does not match anything known
                # show warning and pass the argument
                self.console.warning(self.lang.warning.unknown_arg.format(arg))

        # create URL objects from the links,
        # previously filter them with the URL pattern
        self.urls = map(lambda url: URL(url), filter(lambda url: self.url_re.match(url), self.urls))
