import unittest

from dummy_objects import *
from pymget.pymget import PyMGet
from pymget.networking import VERSION
from pymget.errors import CancelError, FatalError

class TestPyMGet(unittest.TestCase):

    def setUp(self):
        class PyMGetForTests(PyMGet):
            @property
            def _console(self):
                return DummyConsole
            @property
            def _command_line(self):
                return DummyCommandLine
            @property
            def _outfile(self):
                return DummyOutputFile
            @property
            def _manager(self):
                return DummyManager
        self._pymget = PyMGetForTests

    def test_run_ok(self):
        app = self._pymget([])
        app.run()
        self.assertTrue(app.cl.parse_called)
        self.assertTrue(app.manager.prepare_called)
        self.assertTrue(app.manager.download_called)
        self.assertEqual(app.console.text, '\nPyMGet v{}\n'.format(VERSION))

    def test_run_cancel(self):
        def user_cancel():
            raise CancelError('Canceled by user')
        app = self._pymget([])
        app.manager.download = user_cancel
        app.run()
        self.assertTrue(app.console.text, 'Canceled by user')

    def test_run_error(self):
        def user_cancel():
            raise FatalError('There are no mirrors')
        app = self._pymget([])
        app.manager.download = user_cancel
        app.run()
        self.assertTrue(app.console.error_called)
        self.assertTrue(app.console.text, 'There are no mirrors')
