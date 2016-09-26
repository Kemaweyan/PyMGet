import unittest

from dummy_objects import *
from pymget.mirrors import *

class testMirror(unittest.TestCase):

    def setUp(self):
        class MirrorForTests(Mirror):
            @property
            def connection_thread(self):
                return DummyConnectionThread
            @property
            def download_thread(self):
                return DummyDownloadThread
        self._mirror = MirrorForTests

    def test_create_mirror_factory_http(self):
        url = DummyURL('')
        url.protocol = 'http'
        self.assertIsInstance(Mirror.create(url, 10, 0), HTTPMirror)

    def test_create_mirror_factory_https(self):
        url = DummyURL('')
        url.protocol = 'https'
        self.assertIsInstance(Mirror.create(url, 10, 0), HTTPSMirror)

    def test_create_mirror_factory_ftp(self):
        url = DummyURL('')
        url.protocol = 'ftp'
        self.assertIsInstance(Mirror.create(url, 10, 0), FTPMirror)

    def test_created_mirror(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        self.assertFalse(mirror.ready)
        self.assertTrue(mirror.need_connect)
        self.assertIsNone(mirror.conn)
        self.assertIsNone(mirror.conn_thread)
        self.assertIsNone(mirror.dnl_thread)
        self.assertEqual(mirror.file_size, 0)
        self.assertEqual(mirror.task_progress, 0)

    def test_connect_start(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.connect()
        self.assertFalse(mirror.ready)
        self.assertFalse(mirror.need_connect)
        self.assertTrue(mirror.conn_thread.start_called)

    def test_download_start(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.download(0)
        self.assertFalse(mirror.ready)
        self.assertTrue(mirror.dnl_thread.start_called)

    def test_cancel_without_threads(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.cancel()

    def test_cancel_with_connection_thread(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.conn_thread = DummyConnectionThread(DummyURL(''), 0)
        mirror.cancel()
        self.assertTrue(mirror.conn_thread.cancel_called)

    def test_cancel_with_download_thread(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.dnl_thread = DummyDownloadThread(DummyURL(''), None, 0, 0)
        mirror.cancel()
        self.assertTrue(mirror.dnl_thread.cancel_called)

    def test_join_without_threads(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.join()

    def test_join_with_connection_thread(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.conn_thread = DummyConnectionThread(DummyURL(''), 0)
        mirror.join()
        self.assertTrue(mirror.conn_thread.join_called)

    def test_join_with_download_thread(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.dnl_thread = DummyDownloadThread(DummyURL(''), None, 0, 0)
        mirror.join()
        self.assertTrue(mirror.dnl_thread.join_called)

    def test_close_without_connection(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.close()

    def test_close_with_connection(self):
        class DummyConnection:
            def close(self):
                self.close_called = True
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.conn = DummyConnection()
        mirror.close()
        self.assertTrue(mirror.conn.close_called)

    def test_connect_message(self):
        console = DummyConsole()
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.connect_message(console)
        self.assertEqual(console.text, 'Connecting to host OK')
    
    def test_wait_connection_without_threads(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        self.assertTrue(mirror.wait_connection())
        self.assertIsNone(mirror.conn_thread)
        self.assertIsNone(mirror.dnl_thread)

    def test_wait_connection_with_connection_thread_running(self):
        thread = DummyConnectionThread(DummyURL(''), 0)
        thread.ready.wait = lambda t: False
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.conn_thread = thread
        self.assertFalse(mirror.wait_connection())
        self.assertIsNotNone(mirror.conn_thread)
        self.assertIsNone(mirror.dnl_thread)

    def test_wait_connection_with_connection_thread_done(self):
        thread = DummyConnectionThread(DummyURL(''), 0)
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.conn_thread = thread
        self.assertTrue(mirror.wait_connection())
        self.assertIsNone(mirror.conn_thread)
        self.assertIsNone(mirror.dnl_thread)

    def test_wait_connection_with_donwnload_thread_running(self):
        thread = DummyDownloadThread(DummyURL(''), None, 0, 0)
        thread.ready.wait = lambda t: False
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.dnl_thread = thread
        self.assertFalse(mirror.wait_connection())
        self.assertIsNone(mirror.conn_thread)
        self.assertIsNotNone(mirror.dnl_thread)

    def test_wait_connection_with_donwnload_thread_done(self):
        thread = DummyDownloadThread(DummyURL(''), None, 0, 0)
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.dnl_thread = thread
        self.assertTrue(mirror.wait_connection())
        self.assertIsNone(mirror.conn_thread)
        self.assertIsNone(mirror.dnl_thread)

    def test_done(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.done()
        self.assertTrue(mirror.ready)
        self.assertEqual(mirror.task_progress, 0)



class TestFTPMirror(unittest.TestCase):

    
    def setUp(self):
        class FTPMirrorForTests(FTPMirror):
            @property
            def connection_thread(self):
                return DummyConnectionThread
            @property
            def download_thread(self):
                return DummyDownloadThread
        self._mirror = FTPMirrorForTests

    def test_done(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.done()
        self.assertFalse(mirror.ready)
        self.assertTrue(mirror.need_connect)
        self.assertEqual(mirror.task_progress, 0)

    def test_download_start(self):
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.download(0)
        self.assertFalse(mirror.ready)
        self.assertTrue(mirror.dnl_thread.start_called)

    def test_connect_message_first_call(self):
        console = DummyConsole()
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.connect_message(console)
        self.assertEqual(console.text, 'Connecting to host OK')
        self.assertTrue(mirror.connected)

    def test_connect_message_second_call(self):
        console = DummyConsole()
        mirror = self._mirror(DummyURL(''), 10, 0)
        mirror.connected = True
        mirror.connect_message(console)
        self.assertIsNone(console.text)
        self.assertTrue(mirror.connected)
