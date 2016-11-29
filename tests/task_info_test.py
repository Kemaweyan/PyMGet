import unittest
from unittest.mock import Mock

from pymget import task_info as ti

class TestTaskInfo(unittest.TestCase):

    def setUp(self):
        self.manager = Mock()

    def test_task_head_data(self):
        info = ti.TaskHeadData('test', 200, 1024)
        self.assertEqual(info.name, 'test')
        self.assertEqual(info.status, 200)
        self.assertEqual(info.file_size, 1024)
        info.process(self.manager)
        self.manager.set_file_size.assert_called_with(info)

    def test_task_redirect(self):
        info = ti.TaskRedirect('test', 301, 'http://server.com')
        self.assertEqual(info.name, 'test')
        self.assertEqual(info.status, 301)
        self.assertEqual(info.location, 'http://server.com')
        info.process(self.manager)
        self.manager.redirect.assert_called_with(info)

    def test_task_progress(self):
        info = ti.TaskProgress('test', 206, 1024)
        self.assertEqual(info.name, 'test')
        self.assertEqual(info.status, 206)
        self.assertEqual(info.task_progress, 1024)
        info.process(self.manager)
        self.manager.set_progress.assert_called_with(info)

    def test_task_head_error(self):
        info = ti.TaskHeadError('test', 404)
        self.assertEqual(info.name, 'test')
        self.assertEqual(info.status, 404)
        info.process(self.manager)
        self.manager.do_error.assert_called_with(info)

    def test_task_error(self):
        info = ti.TaskError('test', 404, 1024)
        self.assertEqual(info.name, 'test')
        self.assertEqual(info.status, 404)
        self.assertEqual(info.offset, 1024)
        info.process(self.manager)
        self.manager.do_error.assert_called_with(info)

    def test_task_data(self):
        info = ti.TaskData('test', 206, 1024, b'\x00'*100)
        self.assertEqual(info.name, 'test')
        self.assertEqual(info.status, 206)
        self.assertEqual(info.offset, 1024)
        self.assertEqual(info.data, b'\x00'*100)
        info.process(self.manager)
        self.manager.write_data.assert_called_with(info)
