import unittest
from unittest.mock import patch, Mock

from pymget import console

class TestConsole(unittest.TestCase):

    def setUp(self):
        self.console = console.Console()
        self.console._out = Mock()

    def test_message_with_newline(self):
        self.console.message('Test')
        self.console._out.assert_called_with('Test', '\n')

    def test_message_withot_newline(self):
        self.console.message('Test', end='')
        self.console._out.assert_called_with('Test', '')

    def test_warning_with_newline(self):
        self.console.warning('Test')
        self.console._out.assert_called_with('\nWarning: Test', '\n')

    def test_warning_without_newline(self):
        self.console.warning('Test', end='')
        self.console._out.assert_called_with('\nWarning: Test', '')

    def test_error_with_newline(self):
        self.console.error('Test')
        self.console._out.assert_called_with('\nError: Test', '\n')

    def test_error_without_newline(self):
        self.console.error('Test', end='')
        self.console._out.assert_called_with('\nError: Test', '')

    @patch('builtins.input', return_value='yes')
    def test_ask_question_text_default_yes(self, input_mock):
        self.console.ask('Test', True)
        input_mock.assert_called_with('Test (YES/no): ')

    @patch('builtins.input', return_value='yes')
    def test_ask_question_text_default_no(self, input_mock):
        self.console.ask('Test', False)
        input_mock.assert_called_with('Test (yes/NO): ')

    @patch('builtins.input', return_value='yes')
    def test_ask_default_yes_answer_yes(self, input_mock):
        self.assertTrue(self.console.ask('Test', True))

    @patch('builtins.input', return_value='y')
    def test_ask_default_yes_answer_y(self, input_mock):
        self.assertTrue(self.console.ask('Test', True))

    @patch('builtins.input', return_value='no')
    def test_ask_default_yes_answer_no(self, input_mock):
        self.assertFalse(self.console.ask('Test', True))

    @patch('builtins.input', return_value='n')
    def test_ask_default_yes_answer_n(self, input_mock):
        self.assertFalse(self.console.ask('Test', True))

    @patch('builtins.input', return_value='yes')
    def test_ask_default_no_answer_yes(self, input_mock):
        self.assertTrue(self.console.ask('Test', False))

    @patch('builtins.input', return_value='y')
    def test_ask_default_no_answer_y(self, input_mock):
        self.assertTrue(self.console.ask('Test', False))

    @patch('builtins.input', return_value='no')
    def test_ask_default_no_answer_no(self, input_mock):
        self.assertFalse(self.console.ask('Test', False))

    @patch('builtins.input', return_value='n')
    def test_ask_default_no_answer_n(self, input_mock):
        self.assertFalse(self.console.ask('Test', False))

    @patch('builtins.input', return_value='')
    def test_ask_default_yes_answer_default(self, input_mock):
        self.assertTrue(self.console.ask('Test', True))

    @patch('builtins.input', return_value='')
    def test_ask_default_no_answer_default(self, input_mock):
        self.assertFalse(self.console.ask('Test', False))



class TestProgressBar(unittest.TestCase):

    def setUp(self):
        self.clean_pb = console.ProgressBar(1000000, 0)
        self.clean_pb.start_time = 0
        self.resume_pb = console.ProgressBar(1000000, 500000)
        self.resume_pb.start_time = 0

    @patch('time.time', return_value=1)
    def test_progressbar_progress(self, time_mock):
        self.assertEqual(self.clean_pb.get_progress(0.7), 32)

    @patch('time.time', return_value=1)
    def test_clean_progressbar_speed(self, time_mock):
        self.assertEqual(self.clean_pb.get_speed(256000), 256000)

    @patch('time.time', return_value=1)
    def test_resume_progressbar_speed(self, time_mock):
        self.assertEqual(self.resume_pb.get_speed(756000), 256000)

    @patch('time.time', return_value=1)
    def test_progressbar_eta(self, time_mock):
        self.assertEqual(self.clean_pb.get_eta(256000, 256000), 3)

    @patch('time.time', return_value=1)
    def test_progressbar_eta_with_zero_speed(self, time_mock):
        with self.assertRaises(ZeroDivisionError):
            self.clean_pb.get_eta(256000, 0)

    @patch('time.time', return_value=1)
    def test_progressbar_percentage(self, time_mock):
        self.assertEqual(self.clean_pb.get_percentage(256000), 0.256)

    @patch('time.time', return_value=1)
    def test_clean_progressbar(self, time_mock):
        self.assertEqual(self.clean_pb._update(128000), '[######----------------------------------------]  12.80%  125.00KiB/s  ETA:  7s')

    @patch('time.time', return_value=1)
    def test_resume_progressbar(self, time_mock):
        self.assertEqual(self.resume_pb._update(789451), '[####################################----------]  78.95%  282.67KiB/s  ETA:  1s')
