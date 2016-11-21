#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from abc import ABCMeta, abstractmethod

from . import messages
from .utils import *

class IProgressBar(metaclass=ABCMeta):

    """
    An interface for ProgressBar.

    """
    @abstractmethod
    def update(self, complete): pass


class ProgressBar(IProgressBar):

    """
    Progress indicator.
    To change a progress use 'update' method

    """
    WIDTH = 46 # the width of progressbar is 79 - [everything else]

    def __init__(self, total, old_progress):

        """
        :total: a file size to downlaod, type int
        :old_progress: number of bytes downloaded in previous sessions, type int

        """
        self.total = total
        self.old_progress = old_progress
        self.start_time = self.time

    def get_percentage(self, complete):

        """
        Calculates downloading percentage.

        :complete: number of bytes downloaded in all sessions, type int

        """
        return complete / self.total

    def get_progress(self, percentage):

        """
        Calculates a count of 'complete' symbols in the progress bar.

        :percentage: downloading percentage, type float

        """
        return round(self.WIDTH * percentage)

    def get_speed(self, complete):

        """
        Calculates a speed of downloading.

        :complete: number of bytes downloaded in all sessions, type int

        """
        return (complete - self.old_progress) / (self.time - self.start_time)

    def get_eta(self, complete, speed):

        """
        Calculates ETA.

        :complete: number of bytes downloaded in all sessions, type int
        :speed: a speed of downloading, type float

        """
        return round((self.total - complete) / speed)

    def _update(self, complete):

        """
        Creates the current progress string.

        :complete: number of bytes downloaded in all sessions, type int

        """
        percentage = self.get_percentage(complete)
        progress = self.get_progress(percentage)
        # to prevent errors because of zero division
        try:
            speed = self.get_speed(complete)
            eta = self.get_eta(complete, speed)
        except:
            speed = 0
            eta = 0

        # progressbar format:
        # [progress string] |progress in percents| |download speed| |estimated time of arrival|
        #   WIDTH symbols        7 symbols            12 symbols            9 symbols

        progress_str = '[{0:-<{1}}]'.format('#'*progress, self.WIDTH)
        percentage_str = '{0:>7.2%}'.format(percentage)
        speed_str = '{0:>10}/{1}'.format(calc_size(speed), _("s"))
        eta_str = '{0:>9}'.format(calc_eta(eta))

        return '{0} {1} {2} {3}'.format(progress_str, percentage_str, speed_str, eta_str)

    def update(self, complete):

        """
        Sets the current progress.

        :complete: number of bytes downloaded in all sessions, progress calculates as complete / total * 100%, type int

        """
        # get progress string
        bar = self._update(complete)

        # write the string to standard output
        print(bar, end='\r', flush=True)

    @property
    def time(self):
        return time.time()



class IConsole(metaclass=ABCMeta):

    """
    An interface for Console.

    """
    @abstractmethod
    def create_progressbar(self, total, old_progress): pass

    @abstractmethod
    def message(self, text='', end='\n'): pass

    @abstractmethod
    def error(self, text, end='\n'): pass

    @abstractmethod
    def warning(self, text, end='\n'): pass

    @abstractmethod
    def ask(self, text, default): pass

    @abstractmethod
    def progress(self, complete): pass



class Console(IConsole):

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
    progress: prints/updates a progressbar

    """
    def __init__(self):
        # a flag that indicates a presence of 
        self.newline = True # newline symbol in the end of the last printed line
        self.progressbar = None

    def create_progressbar(self, total, old_progress):

        """
        Creates a progress bar.

        :total: a file size to downlaod, type int
        :old_progress: number of bytes downloaded in previous sessions, type int

        """
        self.progressbar = self._progressbar(total, old_progress)

    def _out(self, text, end='\n'):

        """
        Prints a text into stdout.

        """
        print(text, end=end)

    def message(self, text='', end='\n'):

        """
        Prints an information message.

        :text: a text to print, type str
        :end: an ending symbol, default is newline, type str

        """
        if not self.newline:
            text = '\n' + text
        # get a presence of newline symbol
        self.newline = '\n' in end or text.endswith('\n')
        self._out(text, end)

    def error(self, text, end='\n'):

        """
        Prints an error message.

        :key: a text of the error message, type str
        :end: an ending symbol, default is newline, type str

        """
        text = '\n' + _('Error: ') + text
        self.message(text, end)

    def warning(self, text, end='\n'):

        """
        Prints a warning message.

        :key: a text of a warning message, type str
        :end: an ending symbol, default is newline, type str

        """
        text = '\n' + _('Warning: ') + text
        self.message(text, end)

    def ask(self, text, default):

        """
        Prints a question with answers 'yes' or 'no'.

        :key: a text of the question, type str
        :default: default answer (it would be applied when user press Enter), type bool

        """
        YES = ['y', 'yes', _('yes'), _('yes')[0]] # answers interpreted as 'yes'
        NO = ['n', 'no', _('no'), _('no')[0]] # answers interpreted as 'no'

        if default: # YES by default
            yes_text = _('yes').upper() # make YES uppercase
            no_text = _('no')
        else: # NO by default
            yes_text = _('yes')
            no_text = _('no').upper() # make NO uppercase
        # add answers to text
        question_text = '{} ({}/{}): '.format(text, yes_text, no_text)

        # Repeate until user typed a valid answer
        while True:
            answer = input(question_text).lower()
            if answer in YES:
                return True
            if answer in NO:
                return False
            if answer == '':
                return default

    def progress(self, complete):

        """
        Prints/updates a progressbar.

        :complete: number of bytes downloaded in all sessions, progress calculates as complete / total * 100%, type int

        """
        # do nothing if there is no progressbar
        if not self.progressbar:
            return
        # if there was printed a message, add an empty line
        if self.newline:
            print()
        self.newline = False # there is not newline symbol in the end of the line now
        self.progressbar.update(complete)

    # properties for easy testing
    # in auto-testing code you may 
    # reimplement them with dummy objects

    @property
    def _progressbar(self):
        """
        Returns a ProgressBar class.

        """
        return ProgressBar
