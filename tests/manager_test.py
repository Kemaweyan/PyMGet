import unittest
from unittest.mock import Mock, MagicMock, patch
import queue

from pymget import manager
from pymget.errors import FatalError, CancelError

class testManager(unittest.TestCase):

    def setUp(self):
        self.manager = manager.Manager()
        self.mirror = Mock()
        self.console = Mock()
        self.command_line = Mock()
        self.command_line.urls = []
        self.context = Mock()
        self.outfile = MagicMock()
        self.outfile.context.failed_parts = []
        self.outfile.context.offset = 0
        self.outfile.context.written_bytes = 0
        self.task_info = Mock()
        self.task_info.name = 'test'
        self.task_info.file_size = 100
        self.manager.console = self.console
        self.manager.outfile = self.outfile
        self.manager.context = self.context
        self.manager.mirrors['test'] = self.mirror

    def test_prepare_ok(self):
        self.manager.prepare(Mock(), self.command_line, self.outfile)
        self.assertEqual(self.manager.server_filename, 'out')
        self.assertEqual(self.manager.offset, 0)
        self.assertEqual(self.manager.written_bytes, 0)
        self.assertEqual(self.manager.old_progress, 0)
        self.assertEqual(len(self.manager.failed_parts), 0)

    def test_prepare_no_mirrors(self):
        self.manager.mirrors = {}
        with self.assertRaises(FatalError):
            self.manager.prepare(Mock(), self.command_line, self.outfile)

    def test_create_mirror_ok(self):
        self.manager.mirrors = {}
        self.manager.check_filename = Mock(return_value=True)
        self.manager.create_mirror(Mock())
        self.assertEqual(len(self.manager.mirrors), 1)

    def test_create_mirror_wrong_name(self):
        self.manager.mirrors = {}
        self.manager.check_filename = Mock(return_value=False)
        self.manager.create_mirror(Mock())
        self.assertEqual(len(self.manager.mirrors), 0)

    def test_check_filename_first_mirror_known_filename(self):
        self.mirror.filename = 'test'
        self.assertTrue(self.manager.check_filename(self.mirror))
        self.assertEqual(self.manager.server_filename, self.mirror.filename)

    def test_check_filename_first_mirror_unknown_filename_answer_yes(self):
        self.console.ask = Mock(return_value=True)
        self.mirror.filename = ''
        self.assertTrue(self.manager.check_filename(self.mirror))
        self.assertEqual(self.manager.server_filename, '')
        self.assertTrue(self.console.warning.called)
        self.assertTrue(self.console.ask.called)

    def test_check_filename_first_mirror_unknown_filename_answer_no(self):
        self.console.ask = Mock(return_value=False)
        self.mirror.filename = ''
        self.assertFalse(self.manager.check_filename(self.mirror))
        self.assertEqual(self.manager.server_filename, '')
        self.assertTrue(self.console.warning.called)
        self.assertTrue(self.console.ask.called)

    def test_check_filename_second_mirror_filename_same(self):
        self.manager.server_filename = 'path/to/filename'
        self.mirror.filename = 'filename'
        self.assertTrue(self.manager.check_filename(self.mirror))
        self.assertEqual(self.manager.server_filename, 'path/to/filename')

    def test_check_filename_second_mirror_filename_different_answer_yes(self):
        self.console.ask = Mock(return_value=True)
        self.manager.server_filename = 'path/to/filename'
        self.mirror.filename = 'other_filename'
        self.assertTrue(self.manager.check_filename(self.mirror))
        self.assertEqual(self.manager.server_filename, 'path/to/filename')
        self.assertTrue(self.console.warning.called)
        self.assertTrue(self.console.ask.called)

    def test_check_filename_second_mirror_filename_different_answer_no(self):
        self.console.ask = Mock(return_value=False)
        self.manager.server_filename = 'path/to/filename'
        self.mirror.filename = 'other_filename'
        self.assertFalse(self.manager.check_filename(self.mirror))
        self.assertEqual(self.manager.server_filename, 'path/to/filename')
        self.assertTrue(self.console.warning.called)
        self.assertTrue(self.console.ask.called)

    def test_wait_connections_nothing(self):
        self.mirror.wait_connection = Mock(return_value=False)
        self.manager.give_task = Mock()
        self.manager.wait_connections()
        self.assertFalse(self.mirror.connect.called)
        self.assertFalse(self.manager.give_task.called)

    def test_wait_connections_need_connect(self):
        self.mirror.need_connect = True
        self.mirror.ready = False
        self.mirror.wait_connection = Mock(return_value=True)
        self.manager.give_task = Mock()
        self.manager.wait_connections()
        self.assertTrue(self.mirror.connect.called)
        self.assertFalse(self.manager.give_task.called)

    def test_wait_connections_ready(self):
        self.mirror.need_connect = False
        self.mirror.ready = True
        self.mirror.wait_connection = Mock(return_value=True)
        self.manager.give_task = Mock()
        self.manager.wait_connections()
        self.assertFalse(self.mirror.connect.called)
        self.assertTrue(self.manager.give_task.called)

    def test_give_task_failed_part(self):
        self.manager.mirrors = {}
        self.manager.failed_parts.append(10)
        self.manager.give_task(self.mirror)
        self.mirror.download.assert_called_with(10)
        self.assertIn(10, self.manager.parts_in_progress)

    def test_give_task_first_part(self):
        self.manager.mirrors = {}
        self.manager.give_task(self.mirror)
        self.mirror.download.assert_called_with(0)
        self.assertIn(0, self.manager.parts_in_progress)

    def test_give_task_new_offset(self):
        self.manager.offset = 10
        self.manager.file_size = 100
        self.manager.block_size = 10
        self.manager.mirrors = {}
        self.manager.give_task(self.mirror)
        self.mirror.download.assert_called_with(10)
        self.assertIn(10, self.manager.parts_in_progress)
        self.assertEqual(self.manager.offset, 20)

    def test_give_task_all_done(self):
        self.manager.offset = 100
        self.manager.file_size = 100
        self.manager.block_size = 10
        self.manager.mirrors = {}
        self.manager.give_task(self.mirror)
        self.assertFalse(self.mirror.download.called)
        self.assertNotIn(100, self.manager.parts_in_progress)
        self.assertEqual(self.manager.offset, 100)

    def test_download_all_done(self):
        self.manager.written_bytes = 100
        self.manager.file_size = 100
        self.manager.download()
        self.mirror.join.assert_called_with()
        self.mirror.close.assert_called_with()
        self.manager.context.delete.assert_called_with()

    def test_download_cancel(self):
        self.task_info.process = Mock(side_effect=KeyboardInterrupt)
        self.manager.data_queue.get = Mock(return_value=self.task_info)
        with self.assertRaises(CancelError):
            self.manager.download()
        self.mirror.cancel.assert_called_with()
        self.mirror.join.assert_called_with()
        self.mirror.close.assert_called_with()
        self.manager.context.update.assert_called_with(0, 0, [0])

    def test_download_dnl_ok(self):
        self.manager.keep_download = Mock(side_effect=[True, False])
        self.manager.data_queue.get = Mock(side_effect=[self.task_info, queue.Empty])
        self.manager.download()
        self.task_info.process.assert_called_with(self.manager)
        self.mirror.join.assert_called_with()
        self.mirror.close.assert_called_with()
        self.context.update.assert_called_with(0, 0, [0])
        self.context.delete.assert_called_with()

    def test_del_active_part(self):
        self.manager.parts_in_progress.extend([10, 20, 30])
        self.manager.del_active_part(20)
        self.assertIn(10, self.manager.parts_in_progress)
        self.assertNotIn(20, self.manager.parts_in_progress)
        self.assertIn(30, self.manager.parts_in_progress)

    def test_add_failed_part(self):
        self.manager.parts_in_progress.extend([10, 20, 30])
        self.manager.add_failed_part(20)
        self.assertIn(10, self.manager.parts_in_progress)
        self.assertNotIn(20, self.manager.parts_in_progress)
        self.assertIn(30, self.manager.parts_in_progress)
        self.assertIn(20, self.manager.failed_parts)

    def test_delete_mirror(self):
        self.manager.delete_mirror('test')
        self.mirror.join.assert_called_with()
        self.assertNotIn(self.mirror, self.manager.mirrors)

    def test_do_error_not_last_mirror(self):
        self.task_info.status = 0
        self.manager.delete_mirror = Mock()
        self.manager.do_error(self.task_info)
        self.manager.delete_mirror.assert_called_with('test')

    def test_do_error_last_mirror(self):
        self.task_info.status = 0
        self.manager.delete_mirror = Mock()
        self.manager.mirrors = {}
        with self.assertRaises(FatalError):
            self.manager.do_error(self.task_info)
        self.manager.delete_mirror.assert_called_with('test')

    def test_redirect(self):
        url_mock = Mock()
        self.task_info.location = url_mock
        self.manager.create_mirror = Mock()
        self.manager.delete_mirror = Mock()
        self.manager.redirect(self.task_info)
        self.manager.create_mirror.assert_called_with(url_mock)
        self.manager.delete_mirror.assert_called_with('test')

    def test_set_progress(self):
        mirror2 = Mock()
        mirror2.task_progress = 10
        self.task_info.task_progress = 20
        self.manager.mirrors['test2'] = mirror2
        self.manager.written_bytes = 100
        self.manager.set_progress(self.task_info)
        self.console.progress.assert_called_with(130)

    def test_write_data(self):
        data = b'\x00'*10
        self.task_info.offset = 100
        self.task_info.data = data
        self.manager.del_active_part = Mock()
        self.manager.written_bytes = 100
        self.manager.write_data(self.task_info)
        self.assertEqual(self.manager.written_bytes, 110)
        self.manager.del_active_part.assert_called_with(100)
        self.mirror.done.assert_called_with()
        self.outfile.seek.assert_called_with(100)
        self.outfile.write.assert_called_with(data)

    def test_set_file_size_first(self):
        self.manager.set_file_size(self.task_info)
        self.assertEqual(self.manager.file_size, 100)
        self.assertEqual(self.mirror.file_size, 100)
        self.assertTrue(self.mirror.ready)
        self.mirror.connect_message.assert_called_with(self.console)
        self.outfile.seek.assert_called_with(99)
        self.outfile.write.assert_called_with(b'\x00')

    def test_set_file_size_equals(self):
        self.manager.file_size = 100
        self.manager.set_file_size(self.task_info)
        self.assertEqual(self.mirror.file_size, 100)
        self.assertTrue(self.mirror.ready)
        self.mirror.connect_message.assert_called_with(self.console)

    def test_set_file_size_differs(self):
        self.manager.file_size = 200
        self.manager.delete_mirror = Mock()
        self.manager.set_file_size(self.task_info)
        self.assertEqual(self.manager.file_size, 200)
        self.manager.delete_mirror.assert_called_with('test')
