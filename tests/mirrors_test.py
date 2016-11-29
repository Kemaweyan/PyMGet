import unittest
from unittest.mock import Mock, MagicMock, patch

from pymget import mirrors
from pymget import networking as nw

class testMirror(unittest.TestCase):

    def setUp(self):
        self.mirror = mirrors.HTTPMirror(Mock(), 10, 0)

    def test_create_mirror_factory_http(self):
        url = Mock()
        url.protocol = 'http'
        self.assertIsInstance(mirrors.Mirror.create(url, 10, 0), mirrors.HTTPMirror)

    def test_create_mirror_factory_https(self):
        url = Mock()
        url.protocol = 'https'
        self.assertIsInstance(mirrors.Mirror.create(url, 10, 0), mirrors.HTTPSMirror)

    def test_create_mirror_factory_ftp(self):
        url = Mock()
        url.protocol = 'ftp'
        self.assertIsInstance(mirrors.Mirror.create(url, 10, 0), mirrors.FTPMirror)

    def test_created_mirror(self):
        self.assertFalse(self.mirror.ready)
        self.assertTrue(self.mirror.need_connect)
        self.assertIsNone(self.mirror.conn)
        self.assertIsNone(self.mirror.conn_thread)
        self.assertIsNone(self.mirror.dnl_thread)
        self.assertEqual(self.mirror.file_size, 0)
        self.assertEqual(self.mirror.task_progress, 0)

    @patch.object(nw.HTTPThread, 'start')
    @patch.object(nw.HTTPThread, '__init__', return_value=None)
    def test_connect_start(self, conn_thread_init_mock, conn_thread_start_mock):
        url = Mock()
        self.mirror.url = url
        self.mirror.connect()
        self.assertFalse(self.mirror.ready)
        self.assertFalse(self.mirror.need_connect)
        conn_thread_init_mock.assert_called_with(url, 0)
        conn_thread_start_mock.assert_called_with()

    @patch.object(nw.HTTXDownloadThread, 'start')
    @patch.object(nw.HTTXDownloadThread, '__init__', return_value=None)
    def test_download_start(self, dnl_thread_init_mock, dnl_thread_start_mock):
        url = Mock()
        conn = Mock()
        self.mirror.url = url
        self.mirror.conn = conn
        self.mirror.download(0)
        self.assertFalse(self.mirror.ready)
        dnl_thread_init_mock.assert_called_with(url, conn, 0, 10)
        dnl_thread_start_mock.assert_called_with()

    def test_cancel_with_connection_thread(self):
        conn_thread = Mock()
        self.mirror.conn_thread = conn_thread
        self.mirror.cancel()
        conn_thread.cancel.assert_called_with()

    def test_cancel_with_download_thread(self):
        dnl_thread = Mock()
        self.mirror.dnl_thread = dnl_thread
        self.mirror.cancel()
        dnl_thread.cancel.assert_called_with()

    def test_join_with_connection_thread(self):
        conn_thread = Mock()
        self.mirror.conn_thread = conn_thread
        self.mirror.join()
        conn_thread.join.assert_called_with()

    def test_join_with_download_thread(self):
        dnl_thread = Mock()
        self.mirror.dnl_thread = dnl_thread
        self.mirror.join()
        dnl_thread.join.assert_called_with()

    def test_close_with_connection(self):
        conn = Mock()
        self.mirror.conn = conn
        self.mirror.close()
        conn.close.assert_called_with()

    def test_connect_message(self):
        console = Mock()
        self.mirror.url.host = 'host'
        self.mirror.connect_message(console)
        console.message.assert_called_with('Connecting to host OK')
    
    def test_wait_connection_without_threads(self):
        self.assertTrue(self.mirror.wait_connection())
        self.assertIsNone(self.mirror.conn_thread)
        self.assertIsNone(self.mirror.dnl_thread)

    def test_wait_connection_with_connection_thread_running(self):
        thread = Mock()
        thread.ready.wait = Mock(return_value=False)
        self.mirror.conn_thread = thread
        self.assertFalse(self.mirror.wait_connection())
        self.assertIsNotNone(self.mirror.conn_thread)
        self.assertIsNone(self.mirror.dnl_thread)

    def test_wait_connection_with_connection_thread_done(self):
        thread = Mock()
        thread.ready.wait = Mock(return_value=True)
        self.mirror.conn_thread = thread
        self.assertTrue(self.mirror.wait_connection())
        self.assertIsNone(self.mirror.conn_thread)

    def test_wait_download_with_connection_thread_running(self):
        thread = Mock()
        thread.ready.wait = Mock(return_value=False)
        self.mirror.dnl_thread = thread
        self.assertFalse(self.mirror.wait_connection())
        self.assertIsNone(self.mirror.conn_thread)
        self.assertIsNotNone(self.mirror.dnl_thread)

    def test_wait_download_with_connection_thread_done(self):
        thread = Mock()
        thread.ready.wait = Mock(return_value=True)
        self.mirror.dnl_thread = thread
        self.assertTrue(self.mirror.wait_connection())
        self.assertIsNone(self.mirror.conn_thread)
        self.assertIsNone(self.mirror.dnl_thread)

    def test_done(self):
        self.mirror.need_connect = False
        self.mirror.ready = False
        self.mirror.task_progress = 100
        self.mirror.done()
        self.assertTrue(self.mirror.ready)
        self.assertFalse(self.mirror.need_connect)
        self.assertEqual(self.mirror.task_progress, 0)



class TestFTPMirror(unittest.TestCase):

    def setUp(self):
        self.mirror = mirrors.FTPMirror(Mock(), 10, 0)

    def test_done(self):
        self.mirror.need_connect = False
        self.mirror.ready = False
        self.mirror.task_progress = 100
        self.mirror.done()
        self.assertFalse(self.mirror.ready)
        self.assertTrue(self.mirror.need_connect)
        self.assertEqual(self.mirror.task_progress, 0)

    @patch.object(nw.FTPDownloadThread, 'start')
    @patch.object(nw.FTPDownloadThread, '__init__', return_value=None)
    def test_download_start(self, dnl_thread_init_mock, dnl_thread_start_mock):
        url = Mock()
        conn = Mock()
        self.mirror.url = url
        self.mirror.conn = conn
        self.mirror.download(0)
        self.assertFalse(self.mirror.ready)
        dnl_thread_init_mock.assert_called_with(url, conn, 0, 10, 0)
        dnl_thread_start_mock.assert_called_with()

    def test_connect_message_first_call(self):
        console = Mock()
        self.mirror.url.host = 'host'
        self.mirror.connect_message(console)
        console.message.assert_called_with('Connecting to host OK')
        self.assertTrue(self.mirror.connected)

    def test_connect_message_second_call(self):
        console = Mock()
        self.mirror.url.host = 'host'
        self.mirror.connected = True
        self.assertTrue(self.mirror.connected)
        self.assertFalse(console.message.called)
        self.assertTrue(self.mirror.connected)
