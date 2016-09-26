import unittest
import os, platform
import struct
from io import IOBase

from dummy_objects import DummyConsole, DummyContext
from pymget.outfile import *
from pymget.errors import FileError, CancelError

TMPDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tmp')

def setUpModule():
    os.mkdir(TMPDIR)

def tearDownModule():
    os.rmdir(TMPDIR)

class TestOutputFile(unittest.TestCase):

    def setUp(self):
        class OutputFileForTests(OutputFile):
            @property
            def _context(self):
                return DummyContext
        self.console_no = DummyConsole()
        self.console_yes = DummyConsole()
        self.console_yes.ask = lambda t, d: True
        self._outfile = OutputFileForTests
        self.tmp_dir = TMPDIR

    def test_create_path_without_user_path(self):
        outfile = self._outfile(self.console_yes, '')
        outfile.open_file = lambda: None
        outfile.create_path('test')
        self.assertEqual(outfile.filename, 'test')
        self.assertEqual(outfile.path, '')
        self.assertEqual(outfile.fullpath, 'test')

    def test_create_path_with_user_path_to_file(self):
        path = os.path.join(self.tmp_dir, 'folder', 'file')
        outfile = self._outfile(self.console_yes, path)
        outfile.open_file = lambda: None
        outfile.check_folders = lambda: None
        outfile.create_path('test')
        self.assertEqual(outfile.filename, 'file')
        self.assertEqual(outfile.path, os.path.join(self.tmp_dir, 'folder'))
        self.assertEqual(outfile.fullpath, path)

    def test_create_path_with_user_path_to_existing_folder(self):
        outfile = self._outfile(self.console_yes, self.tmp_dir + os.sep)
        outfile.open_file = lambda: None
        outfile.create_path('test')
        self.assertEqual(outfile.filename, 'test')
        self.assertEqual(outfile.path, self.tmp_dir)
        self.assertEqual(outfile.fullpath, os.path.join(self.tmp_dir, 'test'))

    def test_create_path_with_user_path_to_non_existing_folder(self):
        outfile = self._outfile(self.console_yes, os.path.join(self.tmp_dir, 'folder', ''))
        outfile.open_file = lambda: None
        outfile.check_folders = lambda: None
        outfile.create_path('test')
        self.assertEqual(outfile.filename, 'test')
        self.assertEqual(outfile.path, os.path.join(self.tmp_dir, 'folder'))
        self.assertEqual(outfile.fullpath, os.path.join(self.tmp_dir, 'folder', 'test'))

    def test_check_folders_existing_directory(self):
        outfile = self._outfile(self.console_yes, '')
        outfile.path = self.tmp_dir
        self.assertEqual(outfile.check_folders(), None)

    def test_check_folders_non_existing_directory_ok(self):
        outfile = self._outfile(self.console_yes, '')
        outfile.path = os.path.join(self.tmp_dir, 'folder')
        outfile.check_folders()
        self.assertTrue(os.path.isdir(os.path.join(self.tmp_dir, 'folder')))
        os.rmdir(os.path.join(self.tmp_dir, 'folder'))

    def test_check_folders_non_existing_directory_permission_denied(self):
        outfile = self._outfile(self.console_yes, '')
        outfile.path = os.path.join(self.tmp_dir, 'folder')
        os.chmod(self.tmp_dir, 0o555)
        with self.assertRaises(FileError):
            outfile.check_folders()
        os.chmod(self.tmp_dir, 0o755)

    def test_check_folders_non_existing_directory_is_a_file(self):
        path = os.path.join(self.tmp_dir, 'file')
        with open(path, 'w'): pass
        outfile = self._outfile(self.console_yes, '')
        outfile.path = path
        with self.assertRaises(FileError):
            outfile.check_folders()
        os.remove(path)

    def test_check_folders_non_existing_directory_answer_no(self):
        outfile = self._outfile(self.console_no, '')
        outfile.path = os.path.join(self.tmp_dir, 'folder')
        with self.assertRaises(CancelError):
            outfile.check_folders()

    def test_open_file_clean_context_file_not_exists_ok(self):
        path = os.path.join(self.tmp_dir, 'file')
        outfile = self._outfile(self.console_yes, '')
        outfile.context = outfile._context('')
        outfile.fullpath = path
        f = outfile.open_file()
        self.assertIsInstance(f, IOBase)
        f.close()
        os.remove(path)

    def test_open_file_clean_context_file_not_exists_permission_denied(self):
        path = os.path.join(self.tmp_dir, 'file')
        outfile = self._outfile(self.console_yes, '')
        outfile.context = outfile._context('')
        outfile.fullpath = path
        os.chmod(self.tmp_dir, 0)
        with self.assertRaises(FileError):
            outfile.open_file()
        os.chmod(self.tmp_dir, 0o755)

    def test_open_file_clean_context_file_exists_answer_yes(self):
        path = os.path.join(self.tmp_dir, 'file')
        with open(path, 'w'): pass
        outfile = self._outfile(self.console_yes, '')
        outfile.context = outfile._context('')
        outfile.fullpath = path
        f = outfile.open_file()
        self.assertIsInstance(f, IOBase)
        f.close()
        os.remove(path)

    def test_open_file_clean_context_file_exists_answer_no(self):
        path = os.path.join(self.tmp_dir, 'file')
        with open(path, 'w'): pass
        outfile = self._outfile(self.console_no, '')
        outfile.context = outfile._context('')
        outfile.fullpath = path
        with self.assertRaises(CancelError):
            outfile.open_file()
        os.remove(path)

    def test_open_file_old_context_file_exists_ok(self):
        path = os.path.join(self.tmp_dir, 'file')
        with open(path, 'w'): pass
        outfile = self._outfile(self.console_yes, '')
        outfile.context = outfile._context('')
        outfile.context.clean = False
        outfile.fullpath = path
        f = outfile.open_file()
        self.assertIsInstance(f, IOBase)
        f.close()
        os.remove(path)

    def test_open_file_old_context_file_exists_permission_dinied(self):
        path = os.path.join(self.tmp_dir, 'file')
        with open(path, 'w'): pass
        os.chmod(path, 0)
        outfile = self._outfile(self.console_yes, '')
        outfile.context = outfile._context('')
        outfile.context.clean = False
        outfile.fullpath = path
        with self.assertRaises(FileError):
            outfile.open_file()
        os.remove(path)

    def test_open_file_old_context_file_not_exists_answer_no(self):
        path = os.path.join(self.tmp_dir, 'file')
        outfile = self._outfile(self.console_no, '')
        outfile.context = outfile._context('')
        outfile.context.clean = False
        outfile.fullpath = path
        with self.assertRaises(CancelError):
            outfile.open_file()

    def test_open_file_old_context_file_not_exists_answer_yes(self):
        path = os.path.join(self.tmp_dir, 'file')
        outfile = self._outfile(self.console_yes, '')
        outfile.context = outfile._context('')
        outfile.context.clean = False
        outfile.fullpath = path
        f = outfile.open_file()
        self.assertIsInstance(f, IOBase)
        f.close()
        os.remove(path)

    def test_write_file_ok(self):
        path = os.path.join(self.tmp_dir, 'file')
        outfile = self._outfile(self.console_yes, '')
        outfile.file = open(path, 'w')
        with outfile as f:
            f.write('test')
        with open(path, 'r') as f:
            self.assertEqual(f.read(), 'test')
        os.remove(path)

    def test_seek_file_ok(self):
        path = os.path.join(self.tmp_dir, 'file')
        outfile = self._outfile(self.console_yes, '')
        outfile.file = open(path, 'w')
        with outfile as f:
            f.seek(1)
            f.write('test')
        with open(path, 'r') as f:
            self.assertEqual(f.read(), '\x00test')
        os.remove(path)



class TestContext(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tmp')
        self.context_file = os.path.join(self.tmp_dir, 'file')
        self.context = Context(self.context_file)

    def test_create_context(self):
        self.context.open_context()
        self.assertTrue(self.context.clean)

    def test_open_context_without_failed_parts(self):
        with open(self.context_file + '.pymget', 'wb') as f:
            data = struct.pack('NNq', 10, 10, 0)
            f.write(data)
        self.context.open_context()
        self.assertFalse(self.context.clean)
        self.assertEqual(self.context.offset, 10)
        self.assertEqual(self.context.written_bytes, 10)
        self.assertFalse(self.context.failed_parts)
        os.remove(self.context_file + '.pymget')

    def test_open_context_with_failed_parts(self):
        with open(self.context_file + '.pymget', 'wb') as f:
            data = struct.pack('NNqNN', 10, 10, 2, 20, 20)
            f.write(data)
        self.context.open_context()
        for part in self.context.failed_parts:
            self.assertEqual(part, 20)
        os.remove(self.context_file + '.pymget')

    def test_modified_no(self):
        self.assertFalse(self.context.modified(0, 0, []))

    def test_modified_yes_offset(self):
        self.assertTrue(self.context.modified(1, 0, []))

    def test_modified_yes_written_bytes(self):
        self.assertTrue(self.context.modified(0, 1, []))

    def test_modified_yes_failed_parts(self):
        self.assertTrue(self.context.modified(0, 0, [1]))

    def test_update(self):
        self.context.update(10, 20, [0, 0])
        self.assertEqual(self.context.offset, 10)
        self.assertEqual(self.context.written_bytes, 20)
        for part in self.context.failed_parts:
            self.assertEqual(part, 0)
        with open(self.context_file + '.pymget', 'rb') as f:
            data = f.read(struct.calcsize('NNq'))
            offset, written_bytes, failed_parts_len = struct.unpack('NNq', data)
            data = f.read(struct.calcsize('N' * failed_parts_len))
            failed_parts = struct.unpack('N' * failed_parts_len, data)
        self.assertEqual(offset, 10)
        self.assertEqual(written_bytes, 20)
        for part in failed_parts:
            self.assertEqual(part, 0)
        os.remove(self.context_file + '.pymget')
