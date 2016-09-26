import unittest

from dummy_objects import *
from pymget.manager import Manager
from pymget.errors import FatalError, CancelError

class testManager(unittest.TestCase):

    def setUp(self):
        class ManagerForTests(Manager):
            @property
            def _mirror(self):
                return DummyMirror
            @property
            def _dataqueue(self):
                return DummyDataQueue
        self._manager = ManagerForTests
        self.console_no = DummyConsole()
        self.console_yes = DummyConsole()
        self.console_yes.ask = lambda t, d: True
        self.command_line = DummyCommandLine(self.console_no, [])
        self.outfile = DummyOutputFile(self.console_no, '')

    def test_prepare_ok(self):
        manager = self._manager()
        manager.mirrors['test'] = DummyMirror(DummyURL(''), 10, 0)
        manager.prepare(self.console_no, self.command_line, self.outfile)
        self.assertEqual(manager.server_filename, 'out')
        self.assertEqual(manager.offset, 0)
        self.assertEqual(manager.written_bytes, 0)
        self.assertEqual(manager.old_progress, 0)
        self.assertEqual(len(manager.failed_parts), 0)

    def test_prepare_no_mirrors(self):
        manager = self._manager()
        with self.assertRaises(FatalError):
            manager.prepare(self.console_no, self.command_line, self.outfile)

    def test_create_mirror_ok(self):
        manager = self._manager()
        manager.check_filename = lambda m: True
        manager.create_mirror(DummyURL(''))
        self.assertEqual(len(manager.mirrors), 1)

    def test_create_mirror_wrong_name(self):
        manager = self._manager()
        manager.check_filename = lambda m: False
        manager.create_mirror(DummyURL(''))
        self.assertEqual(len(manager.mirrors), 0)

    def test_check_filename_first_mirror_known_filename(self):
        manager = self._manager()
        mirror = DummyMirror(DummyURL(''), 10, 0)
        self.assertTrue(manager.check_filename(mirror))
        self.assertEqual(manager.server_filename, mirror.filename)

    def test_check_filename_first_mirror_unknown_filename_yes(self):
        manager = self._manager()
        manager.console = self.console_yes
        mirror = DummyMirror(DummyURL(''), 10, 0)
        mirror.filename = ''
        self.assertTrue(manager.check_filename(mirror))
        self.assertEqual(manager.server_filename, '')

    def test_check_filename_first_mirror_unknown_filename_no(self):
        manager = self._manager()
        manager.console = self.console_no
        mirror = DummyMirror(DummyURL(''), 10, 0)
        mirror.filename = ''
        self.assertFalse(manager.check_filename(mirror))
        self.assertEqual(manager.server_filename, '')

    def test_check_filename_second_mirror_filename_same(self):
        manager = self._manager()
        manager.server_filename = 'path/to/filename'
        mirror = DummyMirror(DummyURL(''), 10, 0)
        self.assertTrue(manager.check_filename(mirror))
        self.assertEqual(manager.server_filename, 'path/to/filename')

    def test_check_filename_second_mirror_filename_different_yes(self):
        manager = self._manager()
        manager.console = self.console_yes
        manager.server_filename = 'path/to/other_filename'
        mirror = DummyMirror(DummyURL(''), 10, 0)
        self.assertTrue(manager.check_filename(mirror))
        self.assertEqual(manager.server_filename, 'path/to/other_filename')

    def test_check_filename_second_mirror_filename_different_no(self):
        manager = self._manager()
        manager.console = self.console_no
        manager.server_filename = 'path/to/other_filename'
        mirror = DummyMirror(DummyURL(''), 10, 0)
        self.assertFalse(manager.check_filename(mirror))
        self.assertEqual(manager.server_filename, 'path/to/other_filename')

    def test_wait_connections_nothing(self):
        mirror = DummyMirror(DummyURL(''), 10, 0)
        mirror.wait_connection = lambda: False
        manager = self._manager()
        manager.mirrors['test'] = mirror
        manager.wait_connections()
        self.assertFalse(mirror.connect_called)
        self.assertFalse(mirror.download_called)

    def test_wait_connections_need_connect(self):
        mirror = DummyMirror(DummyURL(''), 10, 0)
        mirror.need_connect = True
        manager = self._manager()
        manager.mirrors['test'] = mirror
        manager.wait_connections()
        self.assertTrue(mirror.connect_called)
        self.assertFalse(mirror.download_called)

    def test_wait_connections_ready(self):
        mirror = DummyMirror(DummyURL(''), 10, 0)
        mirror.ready = True
        manager = self._manager()
        manager.mirrors['test'] = mirror
        manager.give_task = lambda m: m.download(0)
        manager.wait_connections()
        self.assertFalse(mirror.connect_called)
        self.assertTrue(mirror.download_called)

    def test_give_task_failed_part(self):
        mirror = DummyMirror(DummyURL(''), 10, 0)
        manager = self._manager()
        manager.failed_parts.append(10)
        manager.give_task(mirror)
        self.assertTrue(mirror.download_called)
        self.assertEqual(mirror.offset, 10)
        self.assertIn(10, manager.parts_in_progress)

    def test_give_task_first_part(self):
        mirror = DummyMirror(DummyURL(''), 10, 0)
        manager = self._manager()
        manager.give_task(mirror)
        self.assertTrue(mirror.download_called)
        self.assertEqual(mirror.offset, 0)
        self.assertIn(0, manager.parts_in_progress)

    def test_give_task_new_offset(self):
        mirror = DummyMirror(DummyURL(''), 10, 0)
        manager = self._manager()
        manager.offset = 10
        manager.file_size = 100
        manager.block_size = 10
        manager.give_task(mirror)
        self.assertTrue(mirror.download_called)
        self.assertEqual(mirror.offset, 10)
        self.assertIn(10, manager.parts_in_progress)
        self.assertEqual(manager.offset, 20)

    def test_give_task_all_done(self):
        mirror = DummyMirror(DummyURL(''), 10, 0)
        manager = self._manager()
        manager.offset = 100
        manager.file_size = 100
        manager.block_size = 10
        manager.give_task(mirror)
        self.assertFalse(mirror.download_called)
        self.assertNotIn(100, manager.parts_in_progress)
        self.assertEqual(manager.offset, 100)

    @staticmethod
    def exit_from_loop(manager):
        manager.written_bytes = 100
        manager.file_size = 100

    def test_download_all_done(self):
        mirror = DummyMirror(DummyURL(''), 10, 0)
        manager = self._manager()
        manager.console = self.console_no
        manager.outfile = self.outfile
        manager.mirrors['test'] = mirror
        manager.context = DummyContext('')
        manager.written_bytes = 100
        manager.file_size = 100
        manager.download()
        self.assertTrue(mirror.join_called)
        self.assertTrue(mirror.close_called)
        self.assertTrue(manager.context.delete_called)

    def test_download_cancel(self):
        def cancel(m):
            raise KeyboardInterrupt
        task_info = DummyTaskInfo()
        task_info.process = cancel
        mirror = DummyMirror(DummyURL(''), 10, 0)
        manager = self._manager()
        manager.console = self.console_no
        manager.outfile = self.outfile
        manager.mirrors['test'] = mirror
        manager.context = DummyContext('')
        manager.data_queue.put(task_info)
        with self.assertRaises(CancelError):
            manager.download()
        self.assertTrue(mirror.cancel_called)
        self.assertTrue(mirror.join_called)
        self.assertTrue(mirror.close_called)
        self.assertTrue(manager.context.update_called)

    def test_download_dnl_ok(self):
        task_info = DummyTaskInfo()
        mirror = DummyMirror(DummyURL(''), 10, 0)
        manager = self._manager()
        manager.console = self.console_no
        manager.outfile = self.outfile
        manager.wait_connections = lambda: self.exit_from_loop(manager)
        manager.mirrors['test'] = mirror
        manager.context = DummyContext('')
        manager.data_queue.put(task_info)
        manager.download()
        self.assertTrue(task_info.process_called)
        self.assertTrue(mirror.join_called)
        self.assertTrue(mirror.close_called)
        self.assertTrue(manager.context.update_called)
        self.assertTrue(manager.context.delete_called)

    def test_del_active_part(self):
        manager = self._manager()
        manager.parts_in_progress.extend([10, 20, 30])
        manager.del_active_part(20)
        self.assertIn(10, manager.parts_in_progress)
        self.assertNotIn(20, manager.parts_in_progress)
        self.assertIn(30, manager.parts_in_progress)

    def test_add_failed_part(self):
        manager = self._manager()
        manager.parts_in_progress.extend([10, 20, 30])
        manager.add_failed_part(20)
        self.assertIn(10, manager.parts_in_progress)
        self.assertNotIn(20, manager.parts_in_progress)
        self.assertIn(30, manager.parts_in_progress)
        self.assertIn(20, manager.failed_parts)

    def test_delete_mirror(self):
        mirror = DummyMirror(DummyURL(''), 10, 0)
        manager = self._manager()
        manager.mirrors['test'] = mirror
        manager.delete_mirror('test')
        self.assertTrue(mirror.join_called)
        self.assertNotIn(mirror, manager.mirrors)

    def test_do_error_not_last_mirror(self):
        def delete_mirror(manager):
            manager.delete_mirror_called = True
        task_info = DummyTaskInfo()
        task_info.name = 'test'
        task_info.status = 0
        mirror = DummyMirror(DummyURL(''), 10, 0)
        manager = self._manager()
        manager.console = self.console_no
        manager.mirrors['test'] = mirror
        manager.delete_mirror = lambda n: delete_mirror(manager)
        manager.do_error(task_info)
        self.assertTrue(manager.delete_mirror_called)

    def test_do_error_last_mirror(self):
        def delete_mirror(manager):
            manager.delete_mirror_called = True
        task_info = DummyTaskInfo()
        task_info.name = 'test'
        task_info.status = 0
        manager = self._manager()
        manager.console = self.console_no
        manager.delete_mirror = lambda n: delete_mirror(manager)
        with self.assertRaises(FatalError):
            manager.do_error(task_info)
        self.assertTrue(manager.delete_mirror_called)

    def test_redirect(self):
        def create_mirror(manager):
            manager.create_mirror_called = True
        def delete_mirror(manager):
            manager.delete_mirror_called = True
        task_info = DummyTaskInfo()
        task_info.name = 'test'
        task_info.location = DummyURL('')
        manager = self._manager()
        manager.console = self.console_no
        manager.create_mirror = lambda l: create_mirror(manager)
        manager.delete_mirror = lambda n: delete_mirror(manager)
        manager.redirect(task_info)
        self.assertTrue(manager.create_mirror_called)
        self.assertTrue(manager.delete_mirror_called)

    def test_set_progress(self):
        mirror1 = DummyMirror(DummyURL(''), 10, 0)
        mirror1.task_progress = 10
        mirror2 = DummyMirror(DummyURL(''), 10, 0)
        task_info = DummyTaskInfo()
        task_info.name = 'test2'
        task_info.task_progress = 20
        console = DummyConsole()
        manager = self._manager()
        manager.console = console
        manager.outfile = self.outfile
        manager.mirrors['test1'] = mirror1
        manager.mirrors['test2'] = mirror2
        manager.written_bytes = 100
        manager.set_progress(task_info)
        self.assertEqual(console.progress_value, 130)

    def test_write_data(self):
        def del_active_part(manager):
            manager.del_active_part_called = True
        task_info = DummyTaskInfo()
        task_info.name = 'test'
        task_info.offset = 10
        task_info.data = b'\x00'*10
        mirror = DummyMirror(DummyURL(''), 10, 0)
        outfile = DummyOutputFile(self.console_no, '')
        manager = self._manager()
        manager.outfile = outfile
        manager.mirrors['test'] = mirror
        manager.del_active_part = lambda n: del_active_part(manager)
        manager.written_bytes = 100
        manager.write_data(task_info)
        self.assertEqual(manager.written_bytes, 110)
        self.assertTrue(manager.del_active_part_called)
        self.assertTrue(mirror.done_called)
        self.assertTrue(outfile.seek_called)
        self.assertTrue(outfile.write_called)

    def test_set_file_size_first(self):
        task_info = DummyTaskInfo()
        task_info.name = 'test'
        task_info.file_size = 100
        mirror = DummyMirror(DummyURL(''), 10, 0)
        outfile = DummyOutputFile(self.console_no, '')
        manager = self._manager()
        manager.console = self.console_no
        manager.outfile = outfile
        manager.mirrors['test'] = mirror
        manager.set_file_size(task_info)
        self.assertEqual(manager.file_size, 100)
        self.assertEqual(mirror.file_size, 100)
        self.assertTrue(mirror.ready)
        self.assertTrue(mirror.connect_message_called)
        self.assertTrue(outfile.seek_called)
        self.assertTrue(outfile.write_called)

    def test_set_file_size_equals(self):
        task_info = DummyTaskInfo()
        task_info.name = 'test'
        task_info.file_size = 100
        mirror = DummyMirror(DummyURL(''), 10, 0)
        manager = self._manager()
        manager.mirrors['test'] = mirror
        manager.file_size = 100
        manager.set_file_size(task_info)
        self.assertEqual(mirror.file_size, 100)
        self.assertTrue(mirror.ready)
        self.assertTrue(mirror.connect_message_called)

    def test_set_file_size_differs(self):
        def delete_mirror(manager):
            manager.delete_mirror_called = True
        task_info = DummyTaskInfo()
        task_info.name = 'test'
        task_info.file_size = 100
        mirror = DummyMirror(DummyURL(''), 10, 0)
        manager = self._manager()
        manager.console = self.console_no
        manager.mirrors['test'] = mirror
        manager.file_size = 200
        manager.delete_mirror = lambda n: delete_mirror(manager)
        manager.set_file_size(task_info)
        self.assertEqual(manager.file_size, 200)
        self.assertTrue(manager.delete_mirror_called)
