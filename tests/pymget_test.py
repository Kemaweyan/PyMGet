import unittest
from unittest.mock import Mock, PropertyMock, patch

from pymget import pymget
from pymget import __version__
from pymget.errors import CancelError, FatalError

class TestPyMGet(unittest.TestCase):

    def setUp(self):
        self.cl_cls = Mock()
        self.outfile_cls = Mock()
        pymget.PyMGet._command_line = PropertyMock(return_value=self.cl_cls)
        pymget.PyMGet._outfile = PropertyMock(return_value=self.outfile_cls)
        pymget.PyMGet._console = PropertyMock()
        self.app = pymget.PyMGet([])
        self.app.manager = Mock()

    def test_run_ok(self):
        self.app.run()
        self.cl_cls.assert_called_with(self.app.console, [])
        self.app.cl.parse.assert_called_with()
        self.outfile_cls.assert_called_with(self.app.console, self.app.cl.filename)
        self.app.manager.prepare.assert_called_with(self.app.console, self.app.cl, self.app.outfile)
        self.app.manager.download.assert_called_with()

    def test_run_cancel(self):
        self.app.manager.download = Mock(side_effect=CancelError('Canceled by user'))
        self.app.run()
        self.app.console.message.assert_called_with('Canceled by user')

    def test_run_error(self):
        self.app.manager.download = Mock(side_effect=FatalError('There are no mirrors'))
        self.app.run()
        self.app.console.error.assert_called_with('There are no mirrors')
