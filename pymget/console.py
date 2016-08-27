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
    WIDTH = 46 # the width of progressbar is 79 - [everything else]

    def __init__(self):
        self._total = 0
        self.time = 0
        self.lang = Messages()

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
            eta = round((self.total - complete) / speed)
        except:
            speed = 0
            percent = 0
            progress = 0
            eta = 0

        # progressbar format:
        # [progress string] |progress in percents| |download speed| |estimated time of arrival|
        #   WIDTH symbols        7 symbols            12 symbols            9 symbols

        bar = '[{0:-<{1}}] {2:>7.2%} {3:>10}/s {4:>9}\r'.format('#'*progress, self.WIDTH, percent, calc_units(speed), self.calc_eta(eta))

        sys.stdout.write(bar)
        sys.stdout.flush()

    def calc_eta(self, eta):

        """
        Calculates estimated time of arrival
        in weeks, days, hours, minutes or seconds.

        :eta: ETA in seconds, type int

        """
        if not eta or eta > 3600 * 24 * 7 * 99:
            return ' ETA: ---'
        if eta > 3600 * 24 * 7: # more than a week
            return ' ETA: {:>2}{}'.format(round(eta / 3600 * 24 * 7), self.lang.common.week)
        if eta > 3600 * 24: # more than a day
            return ' ETA: {:>2}{}'.format(round(eta / 3600 * 24), self.lang.common.day)
        if eta > 3600: # more than a hour
            return ' ETA: {:>2}{}'.format(round(eta / 3600), self.lang.common.hour)
        if eta > 60: # more than a minute
            return ' ETA: {:>2}{}'.format(round(eta / 60), self.lang.common.minute)
        return ' ETA: {:>2}{}'.format(eta, self.lang.common.second)




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
        YES = ['y', 'yes', self.lang.common.yes, self.lang.common.yes[0]] # answers interpreted as 'yes'
        NO = ['n', 'no', self.lang.common.no, self.lang.common.no[0]] # answers interpreted as 'no'

        if default: # YES by default
            yes_text = self.lang.common.yes.upper() # make YES uppercase
            no_text = self.lang.common.no
        else: # NO by default
            yes_text = self.lang.common.yes
            no_text = self.lang.common.no.upper() # make NO uppercase
        # add answers to text
        question_text = '{} ({}/{}):'.format(text, yes_text, no_text)

        # Repeate until user typed a valid answer
        while True:
            self.out(question_text, end=' ')
            answer = input().lower()
            if answer in YES:
                return True
            if answer in NO:
                return False
            if answer == '':
                return default
