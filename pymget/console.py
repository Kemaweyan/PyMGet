#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, platform, time

from pymget.messages import Messages
from pymget.utils import *

class ProgressBar:

    """
    Progress indicator. 
    Please assign 'total' property before using.
    To change a progress use 'update' method

    """
    WIDTH = 57 # the width of progressbar, the number is 80 - [everything else]

    def __init__(self):
        self._total = 0
        self.time = 0
        if platform.system() == 'Windows':
            self.WIDTH -= 1 # in Windows it should be 79 - [everything else]

    @property
    def total(self):
        return self._total

    @total.setter
    def total(self, total):
        self.time = time.time() # save a time when downloading has been started
        self._total = total

    def update(self, complete, gotten_bytes):

        """
        Sets the current progress. The program could download file in multiple sessions (retry after fail), so to calculate
        the correct speed value there are separate arguments for total progress and the progress in current session.

        :complete: number of bytes downloaded in all sessions, progress calculates as complete / total * 100%, type int
        :gotten_bytes: number of bytes downloaded in current session, type int

        """
        # to prevent errors because of zero divizion
        try:
            speed = gotten_bytes / (time.time() - self.time)
            percent = complete / self.total
            progress = round(self.WIDTH * percent)
        except:
            speed = 0
            percent = 0
            progress = 0

        # progressbar format:
        # [progress string] |progress in percents| |download speed|
        #   WIDTH symbols        7 symbols            12 symbols

        bar = '[{0:-<{1}}] {2:>7.2%} {3:>10}/s\r'.format('#'*progress, self.WIDTH, percent, calc_units(speed))

        sys.stdout.write(bar)
        sys.stdout.flush()




@singleton
class Console:

    """
    Used instead of 'print', because it considers presence/absence of newline symbol
    in previous console out. If previous console out was made by progressbar, there
    is no newline symbol in the end of string and 'print' function would print the text
    over progressbar symbols. To prevent this issue console class adds the newline symbol
    before print a new message.

    Methods:

    out: prints a text from newline without prefix
    warning: prints a text with prefix 'Warning: '
    error: prints a text with prefix 'Error: '
    ask: prints a question with answers 'yes' and 'no'
    progress: prints/updates a proogressbar

    """
    def __init__(self):
        # a flag that indicates a presence of 
        self.newline = True # newline symbol in the end of the last printed line
        self.progressbar = ProgressBar()
        self.lang = Messages()

    def out(self, text='', end='\n'):

        """
        Prints a text without prefix.

        :text: a text will be printed, type str
        :end: ending symbol, default is newline, type str

        """
        if not self.newline:
            print()
        print(text, end=end)
        # get a presence of newline symbol
        self.newline = '\n' in end or text.endswith('\n')

    def error(self, text, end='\n'):

        """
        Prints error message. 

        :text: a text will be printed, type str
        :end: ending symbol, default is newline, type str

        """
        if text:
            self.out('\n' + self.lang.common.error + text, end)

    def warning(self, text, end='\n'):

        """
        Prints warning message.

        :text: a text will be printed, type str
        :end: ending symbol, default is newline, type str

        """
        if text:
            self.out('\n' + self.lang.common.warning + text, end)

    def progress(self, complete, gotten_bytes):

        """
        Prints/updates a progressbar.

        :complete: number of bytes downloaded in all sessions, progress calculates as complete / total * 100%, type int
        :gotten_bytes: number of bytes downloaded in current session, type int

        """
        # if there was printed a message, add an empty line
        if self.newline:
            print()
        self.newline = False # there is not newline symbol in the end of the line now
        self.progressbar.update(complete, gotten_bytes)

    def ask(self, text, default):

        """
        Prints a question with answers 'yes' or 'no'.

        :text: a text will be printed, type str
        :default: default answer (it would be applied when user press Enter), type bool

        """
        YES = ['y', 'yes', 'д', 'да'] # answers interpreted as 'yes'
        NO = ['n', 'no', 'н', 'нет'] # answers interpreted as 'no'
        # Repeate until user typed a valid answer
        while True:
            self.out(text, end=' ')
            answer = input().lower()
            if answer in YES:
                return True
            if answer in NO:
                return False
            if answer == '':
                return default
