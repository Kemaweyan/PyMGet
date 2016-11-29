import unittest
from unittest.mock import Mock, PropertyMock, MagicMock, patch, DEFAULT

import os
import platform
import struct

from pymget import outfile
from pymget.errors import FileError, CancelError

class TestOutputFile(unittest.TestCase):

    def setUp(self):
        self.console = Mock()
        self.console.ask.return_value = True
        self.of = outfile.OutputFile(self.console, '')

    def test_create_path_without_user_path(self):
        self.of.open_file = Mock(return_value=None)
        self.of.create_path('test')
        self.assertEqual(self.of.filename, 'test')
        self.assertEqual(self.of.path, '')
        self.assertEqual(self.of.fullpath, 'test')

    @patch('os.path.isdir', return_value=False)
    def test_create_path_with_user_path_to_file(self, isdir_mock):
        path = os.path.join('folder', 'file')
        self.of.user_path = path
        self.of.open_file = Mock(return_value=None)
        self.of.check_folders = Mock(return_value=None)
        self.of.create_path('test')
        self.assertEqual(self.of.filename, 'file')
        self.assertEqual(self.of.path, 'folder')
        self.assertEqual(self.of.fullpath, path)

    @patch('os.path.isdir', return_value=True)
    def test_create_path_with_user_path_to_existing_folder(self, isdir_mock):
        self.of.user_path = 'folder'
        self.of.open_file = Mock(return_value=None)
        self.of.create_path('test')
        self.assertEqual(self.of.filename, 'test')
        self.assertEqual(self.of.path, 'folder')
        self.assertEqual(self.of.fullpath, os.path.join('folder', 'test'))

    @patch('os.path.isdir', return_value=False)
    def test_create_path_with_user_path_to_non_existing_folder(self, isdir_mock):
        self.of.user_path = os.path.join('folder', '')
        self.of.open_file = Mock(return_value=None)
        self.of.check_folders = Mock(return_value=None)
        self.of.create_path('test')
        self.assertEqual(self.of.filename, 'test')
        self.assertEqual(self.of.path, 'folder')
        self.assertEqual(self.of.fullpath, os.path.join('folder', 'test'))

    @patch('os.path.isdir', return_value=True)
    def test_check_folders_existing_directory(self, isdir_mock):
        self.of.path = 'path/to/folder'
        self.assertEqual(self.of.check_folders(), None)

    @patch('os.makedirs')
    @patch('os.path.isdir', return_value=False)
    def test_check_folders_non_existing_directory_ok(self, isdir_mock, makedirs_mock):
        self.of.path = 'path/to/folder'
        self.of.check_folders()
        makedirs_mock.assert_called_with('path/to/folder')

    @patch('os.makedirs', side_effect=PermissionError)
    @patch('os.path.isdir', return_value=False)
    def test_check_folders_non_existing_directory_permission_denied(self, isdir_mock, makedirs_mock):
        self.of.path = 'path/to/folder'
        with self.assertRaises(FileError):
            self.of.check_folders()

    @patch('os.makedirs', side_effect=NotADirectoryError)
    @patch('os.path.isdir', return_value=False)
    def test_check_folders_non_existing_directory_is_a_file(self, isdir_mock, makedirs_mock):
        self.of.path = 'path/to/folder'
        with self.assertRaises(FileError):
            self.of.check_folders()

    @patch('os.path.isdir', return_value=False)
    def test_check_folders_non_existing_directory_cancel(self, isdir_mock):
        self.console.ask.return_value = False
        self.of.path = 'path/to/folder'
        with self.assertRaises(CancelError):
            self.of.check_folders()

    @patch('os.path.isfile', return_value=False)
    @patch('builtins.open')
    def test_open_file_clean_context_file_not_exists_ok(self, open_mock, isfile_mock):
        self.of.context = Mock()
        self.of.context.clean = True
        self.of.fullpath = 'path/to/file'
        self.assertEqual(self.of.open_file(), open_mock.return_value)
        isfile_mock.assert_called_with('path/to/file')
        open_mock.assert_called_with('path/to/file', 'wb')

    @patch('os.path.isfile', return_value=False)
    @patch('builtins.open', side_effect=PermissionError)
    def test_open_file_clean_context_file_not_exists_permission_denied(self, open_mock, isfile_mock):
        self.of.context = Mock()
        self.of.context.clean = True
        self.of.fullpath = 'path/to/file'
        with self.assertRaises(FileError):
            self.of.open_file()
        isfile_mock.assert_called_with('path/to/file')

    @patch('os.path.isfile', return_value=True)
    @patch('builtins.open')
    def test_open_file_clean_context_file_exists_answer_yes(self, open_mock, isfile_mock):
        self.of.context = Mock()
        self.of.context.clean = True
        self.of.fullpath = 'path/to/file'
        self.assertEqual(self.of.open_file(), open_mock.return_value)
        isfile_mock.assert_called_with('path/to/file')
        open_mock.assert_called_with('path/to/file', 'wb')

    @patch('os.path.isfile', return_value=True)
    @patch('builtins.open')
    def test_open_file_clean_context_file_exists_answer_no(self, open_mock, isfile_mock):
        self.console.ask.return_value = False
        self.of.context = Mock()
        self.of.context.clean = True
        self.of.fullpath = 'path/to/file'
        with self.assertRaises(CancelError):
            self.of.open_file()
        isfile_mock.assert_called_with('path/to/file')

    @patch('builtins.open')
    def test_open_file_old_context_file_not_exists_ok(self, open_mock):
        self.of.context = Mock()
        self.of.context.clean = False
        self.of.fullpath = 'path/to/file'
        self.assertEqual(self.of.open_file(), open_mock.return_value)
        open_mock.assert_called_with('path/to/file', 'rb+')

    @patch('os.path.isfile', return_value=True)
    @patch('builtins.open', side_effect=PermissionError)
    def test_open_file_old_context_file_exists_permission_denied(self, open_mock, isfile_mock):
        self.of.context = Mock()
        self.of.context.clean = False
        self.of.fullpath = 'path/to/file'
        with self.assertRaises(FileError):
            self.of.open_file()
        isfile_mock.assert_called_with('path/to/file')

    @patch('os.path.isfile', return_value=False)
    @patch('builtins.open', side_effect=[FileNotFoundError, DEFAULT])
    def test_open_file_old_context_file_not_exists_answer_yes(self, open_mock, isfile_mock):
        self.of.context = Mock()
        type(self.of.context).clean = PropertyMock(side_effect=[False, True])
        self.of.fullpath = 'path/to/file'
        self.assertEqual(self.of.open_file(), open_mock.return_value)
        isfile_mock.assert_called_with('path/to/file')
        open_mock.assert_any_call('path/to/file', 'rb+')
        open_mock.assert_any_call('path/to/file', 'wb')

    @patch('os.path.isfile', return_value=False)
    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_open_file_old_context_file_not_exists_answer_no(self, open_mock, isfile_mock):
        self.console.ask.return_value = False
        self.of.context = Mock()
        self.of.context.clean = False
        self.of.fullpath = 'path/to/file'
        with self.assertRaises(CancelError):
            self.of.open_file()
        isfile_mock.assert_called_with('path/to/file')

    def test_write_file_ok(self):
        self.of.file = Mock()
        with self.of as f:
            f.write(b'\x00'*100)
        self.of.file.write.assert_called_with(b'\x00'*100)
        self.of.file.close.assert_called_with()

    def test_write_file_failed(self):
        self.of.file = Mock()
        self.of.file.write = Mock(side_effect=Exception)
        with self.assertRaises(FileError):
            with self.of as f:
                f.write(b'\x00'*100)
        self.of.file.close.assert_called_with()

    def test_seek_file_ok(self):
        self.of.file = Mock()
        with self.of as f:
            f.seek(100)
        self.of.file.seek.assert_called_with(100, 0)
        self.of.file.close.assert_called_with()

    def test_seek_file_failed(self):
        self.of.file = Mock()
        self.of.file.seek = Mock(side_effect=Exception)
        with self.assertRaises(FileError):
            with self.of as f:
                f.seek(100)
        self.of.file.close.assert_called_with()




class TestContext(unittest.TestCase):

    def setUp(self):
        self.context = outfile.Context('test')

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_create_context(self, open_mock):
        self.context.open_context()
        self.assertTrue(self.context.clean)
        open_mock.assert_called_with('test.pymget', 'rb')

    @patch('builtins.open')
    def test_open_context_without_failed_parts(self, open_mock):
        data = struct.pack('NNq', 10, 10, 0)
        read = Mock(return_value=data)
        open_mock.return_value.__enter__.return_value.read = read
        self.context.open_context()
        self.assertFalse(self.context.clean)
        self.assertEqual(self.context.offset, 10)
        self.assertEqual(self.context.written_bytes, 10)
        self.assertFalse(self.context.failed_parts)
        read.assert_called_with(struct.calcsize('NNq'))

    @patch('builtins.open')
    def test_open_context_with_failed_parts(self, open_mock):
        data = struct.pack('NNq', 10, 10, 2)
        failed_parts_data = struct.pack('NN', 20, 20)
        read = Mock(side_effect=[data, failed_parts_data])
        open_mock.return_value.__enter__.return_value.read = read
        self.context.open_context()
        self.assertFalse(self.context.clean)
        for part in self.context.failed_parts:
            self.assertEqual(part, 20)
        read.assert_any_call(struct.calcsize('NNq'))
        read.assert_any_call(struct.calcsize('NN'))

    def test_modified_no(self):
        self.assertFalse(self.context.modified(0, 0, []))

    def test_modified_yes_offset(self):
        self.assertTrue(self.context.modified(1, 0, []))

    def test_modified_yes_written_bytes(self):
        self.assertTrue(self.context.modified(0, 1, []))

    def test_modified_yes_failed_parts(self):
        self.assertTrue(self.context.modified(0, 0, [1]))

    @patch('builtins.open')
    def test_update(self, open_mock):
        write = Mock()
        open_mock.return_value.__enter__.return_value.write = write
        self.context.update(10, 20, [0, 0])
        self.assertEqual(self.context.offset, 10)
        self.assertEqual(self.context.written_bytes, 20)
        for part in self.context.failed_parts:
            self.assertEqual(part, 0)
        write.assert_called_with(struct.pack('NNqNN', 10, 20, 2, 0, 0))

    def test_reset(self):
        self.context.clean = False
        self.context.update = Mock()
        self.context.reset()
        self.context.update.assert_called_with(0, 0, [])
        self.assertTrue(self.context.clean)

    @patch('os.remove')
    def test_delete(self, remove_mock):
        self.context.delete()
        remove_mock.assert_called_with('test.pymget')

    @patch('os.remove', side_effect=FileNotFoundError)
    def test_delete_empty(self, remove_mock):
        self.context.delete()
        remove_mock.assert_called_with('test.pymget')
