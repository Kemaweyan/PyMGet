import unittest

from dummy_objects import DummyProgressBar
from pymget.console import *
import pymget.console

class TestConsole(unittest.TestCase):

    def setUp(self):
        class ConsoleForTests(Console):
            @property
            def _progressbar(_self):
                return DummyProgressBar
            def _out(_self, text, end='\n'):
                _self.text = text + end
        self.console = ConsoleForTests()

    def test_message_with_newline(self):
        self.console.message('Test')
        self.assertEqual(self.console.text, 'Test\n')

    def test_message_without_newline(self):
        self.console.message('Test', end='')
        self.assertEqual(self.console.text, 'Test')

    def test_warning_with_newline(self):
        self.console.warning('Test')
        self.assertEqual(self.console.text, '\nWarning: Test\n')

    def test_warning_without_newline(self):
        self.console.warning('Test', end='')
        self.assertEqual(self.console.text, '\nWarning: Test')

    def test_error_with_newline(self):
        self.console.error('Test')
        self.assertEqual(self.console.text, '\nError: Test\n')

    def test_error_without_newline(self):
        self.console.error('Test', end='')
        self.assertEqual(self.console.text, '\nError: Test')

    def test_ask_question_text_default_yes(self):
        text = ''
        def read_question(msg):
            nonlocal text
            text = msg
            return 'yes'
        pymget.console.input = read_question
        self.console.ask('Test', True)
        self.assertEqual(text, 'Test (YES/no): ')

    def test_ask_question_text_default_no(self):
        text = ''
        def read_question(msg):
            nonlocal text
            text = msg
            return 'yes'
        pymget.console.input = read_question
        self.console.ask('Test', False)
        self.assertEqual(text, 'Test (yes/NO): ')

    def test_ask_default_yes_answer_yes(self):
        pymget.console.input = lambda x: 'yes'
        self.assertTrue(self.console.ask('Test', True))

    def test_ask_default_yes_answer_y(self):
        pymget.console.input = lambda x: 'y'
        self.assertTrue(self.console.ask('Test', True))

    def test_ask_default_yes_answer_no(self):
        pymget.console.input = lambda x: 'no'
        self.assertFalse(self.console.ask('Test', True))

    def test_ask_default_yes_answer_n(self):
        pymget.console.input = lambda x: 'n'
        self.assertFalse(self.console.ask('Test', True))

    def test_ask_default_no_answer_yes(self):
        pymget.console.input = lambda x: 'yes'
        self.assertTrue(self.console.ask('Test', False))

    def test_ask_default_no_answer_y(self):
        pymget.console.input = lambda x: 'y'
        self.assertTrue(self.console.ask('Test', False))

    def test_ask_default_no_answer_no(self):
        pymget.console.input = lambda x: 'no'
        self.assertFalse(self.console.ask('Test', False))

    def test_ask_default_no_answer_n(self):
        pymget.console.input = lambda x: 'n'
        self.assertFalse(self.console.ask('Test', False))

    def test_ask_default_yes_answer_default(self):
        pymget.console.input = lambda x: ''
        self.assertTrue(self.console.ask('Test', True))

    def test_ask_default_no_answer_default(self):
        pymget.console.input = lambda x: ''
        self.assertFalse(self.console.ask('Test', False))


class TestProgressBar(unittest.TestCase):

    def setUp(self):
        class ProgressBarForTests(ProgressBar):
            def __init__(_self, total, old_progress):
                ProgressBar.__init__(_self, total, old_progress)
                _self.start_time = 0
            @property
            def time(_self):
                return 1
        self.clean_progressbar = ProgressBarForTests(1000000, 0)
        self.resume_progressbar = ProgressBarForTests(1000000, 500000)

    def test_progressbar_progress(self):
        self.assertEqual(self.clean_progressbar.get_progress(0.7), 32)

    def test_clean_progressbar_speed(self):
        self.assertEqual(self.clean_progressbar.get_speed(256000), 256000)

    def test_resume_progressbar_speed(self):
        self.assertEqual(self.resume_progressbar.get_speed(756000), 256000)

    def test_progressbar_eta(self):
        self.assertEqual(self.clean_progressbar.get_eta(256000, 256000), 3)

    def test_progressbar_eta_with_zero_speed(self):
        with self.assertRaises(ZeroDivisionError):
            self.clean_progressbar.get_eta(256000, 0)

    def test_progressbar_percentage(self):
        self.assertEqual(self.clean_progressbar.get_percentage(256000), 0.256)

    def test_clean_progressbar(self):
        self.assertEqual(self.clean_progressbar._update(128000), '[######----------------------------------------]  12.80%  125.00KiB/s  ETA:  7s\r')

    def test_resume_progressbar(self):
        self.assertEqual(self.resume_progressbar._update(789451), '[####################################----------]  78.95%  282.67KiB/s  ETA:  1s\r')
