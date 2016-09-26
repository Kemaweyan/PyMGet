import unittest

from dummy_objects import *
from pymget.networking import *
from pymget.task_info import *

class testURL(unittest.TestCase):

    def test_http_no_path_no_endslash(self):
        url = URL('http://server.com')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_https_no_path_no_endslash(self):
        url = URL('https://server.com')
        self.assertEqual(url.protocol, 'https')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_ftp_no_path_no_endslash(self):
        url = URL('ftp://server.com')
        self.assertEqual(url.protocol, 'ftp')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_no_path_no_endslash_with_port(self):
        url = URL('http://server.com:8888')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server.com:8888')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_no_path_no_endslash_with_digits(self):
        url = URL('http://server123.com')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server123.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_no_path_no_endslash_with_digits_only(self):
        url = URL('http://123.com')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, '123.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_no_path_no_endslash_with_minus(self):
        url = URL('http://ser-ver.com')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'ser-ver.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_no_path_with_endslash(self):
        url = URL('http://server.com')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_with_path(self):
        url = URL('http://server.com/path/to/file')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/path/to/file')
        self.assertEqual(url.path, 'path/to')
        self.assertEqual(url.filename, 'file')

    def test_http_with_path_with_endslash(self):
        url = URL('http://server.com/path/to/file/')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/path/to/file/')
        self.assertEqual(url.path, 'path/to/file')
        self.assertEqual(url.filename, '')


class TestHTTXConnection(unittest.TestCase):

    def setUp(self):
        class HTTXConnectionForTests(HTTPThread):
            @property
            def _dataqueue(self):
                return DummyDataQueue
            @property
            def protocol(self):
                return DummyHTTXConnection()
        self._connection = HTTXConnectionForTests

    def test_run_ok(self):
        conn = self._connection(DummyURL(''), 0)
        conn.connect = lambda: TaskHeadData('', 200, 0)
        self.assertFalse(conn.ready.is_set())
        conn.run()
        self.assertIsInstance(conn.data_queue.get(), TaskHeadData)
        self.assertTrue(conn.ready.is_set())

    def test_run_error(self):
        conn = self._connection(DummyURL(''), 0)
        conn.connect = lambda: 1 / 0
        self.assertFalse(conn.ready.is_set())
        conn.run()
        self.assertIsInstance(conn.data_queue.get(), TaskHeadError)
        self.assertTrue(conn.ready.is_set())

    def test_redirect_with_host(self):
        location = 'http://server.com/path/to/file'
        conn = self._connection(DummyURL(''), 0)
        info = conn.redirect(location, 301)
        self.assertIsInstance(info, TaskRedirect)
        self.assertEqual(info.location.url, location)

    def test_redirect_absolute(self):
        url = DummyURL('')
        url.protocol = 'http'
        url.host = 'server.com'
        conn = self._connection(url, 0)
        info = conn.redirect('/path/to/file', 301)
        self.assertIsInstance(info, TaskRedirect)
        self.assertEqual(info.location.url, 'http://server.com/path/to/file')

    def test_redirect_relative(self):
        url = DummyURL('')
        url.protocol = 'http'
        url.host = 'server.com'
        url.request = '/path/to/file'
        conn = self._connection(url, 0)
        info = conn.redirect('another_file', 301)
        self.assertIsInstance(info, TaskRedirect)
        self.assertEqual(info.location.url, 'http://server.com/path/to/another_file')

    def test_connect_ok(self):
        DummyHTTXConnection.response = DummyHTTXResponse(200, {'Content-Length': '100'})
        conn = self._connection(DummyURL(''), 0)
        info = conn.connect()
        self.assertIsInstance(info, TaskHeadData)
        self.assertEqual(info.file_size, 100)

    def test_connect_redirect(self):
        DummyHTTXConnection.response = DummyHTTXResponse(301, {'Location': 'http://server.com'})
        conn = self._connection(DummyURL(''), 0)
        info = conn.connect()
        self.assertIsInstance(info, TaskRedirect)
        self.assertEqual(info.location.url, 'http://server.com')

    def test_connect_error(self):
        DummyHTTXConnection.response = DummyHTTXResponse(404, {})
        conn = self._connection(DummyURL(''), 0)
        info = conn.connect()
        self.assertIsInstance(info, TaskHeadError)
        self.assertEqual(info.status, 404)



class TestFTPConnection(unittest.TestCase):

    def setUp(self):
        class FTPConnectionForTests(FTPThread):
            @property
            def protocol(self):
                return DummyFTPConnection
        self._connection = FTPConnectionForTests

    def test_connect(self):
        conn = self._connection(DummyURL(''), 0)
        info = conn.connect()
        self.assertIsInstance(info, TaskHeadData)
        self.assertEqual(info.file_size, 100)


class TestHTTXDownload(unittest.TestCase):
    
    def setUp(self):
        class HTTXDownloadForTests(HTTXDownloadThread):
            @property
            def _dataqueue(self):
                return DummyDataQueue
        self._download = HTTXDownloadForTests
        self.connection = DummyHTTXConnection()
        self.url = DummyURL('')

    def test_run_get_data(self):
        self.connection.response = DummyHTTXResponse(206, {'Content-Length': '100'}, b'\x00'*100)
        dnl = self._download(self.url, self.connection, 0, 4*2**20)
        dnl.run()
        self.assertTrue(dnl.ready.is_set())
        self.assertIsInstance(dnl.data_queue.get(), TaskProgress)
        info = dnl.data_queue.get()
        self.assertIsInstance(info, TaskData)
        self.assertEqual(self.connection.request, 'request')
        self.assertEqual(self.connection.headers['Range'], 'bytes=0-4194303')
        self.assertEqual(len(info.data), 100)

    def test_run_get_data_no_partial(self):
        self.connection.response = DummyHTTXResponse(200, {'Content-Length': '100'}, b'\x00'*100)
        dnl = self._download(self.url, self.connection, 0, 4*2**20)
        dnl.run()
        info = dnl.data_queue.get()
        self.assertTrue(dnl.ready.is_set())
        self.assertIsInstance(info, TaskError)
        self.assertEqual(info.status, 200)

    def test_run_get_data_http_error(self):
        self.connection.response = DummyHTTXResponse(404, {'Content-Length': '100'}, b'\x00'*100)
        dnl = self._download(self.url, self.connection, 0, 4*2**20)
        dnl.run()
        info = dnl.data_queue.get()
        self.assertTrue(dnl.ready.is_set())
        self.assertIsInstance(info, TaskError)
        self.assertEqual(info.status, 404)

    def test_run_get_data_get_error(self):
        self.connection.response = DummyHTTXResponse(206, {'Content-Length': '100'}, b'\x00'*100)
        self.connection.response.read = lambda s: 1 / 0
        dnl = self._download(self.url, self.connection, 0, 4*2**20)
        dnl.run()
        info = dnl.data_queue.get()
        self.assertTrue(dnl.ready.is_set())
        self.assertIsInstance(info, TaskError)
        self.assertEqual(info.status, 0)

    def test_run_get_data_cancel(self):
        self.connection.response = DummyHTTXResponse(206, {'Content-Length': '100'}, b'\x00'*100)
        dnl = self._download(self.url, self.connection, 0, 4*2**20)
        dnl.cancel()
        dnl.run()
        info = dnl.data_queue.get()
        self.assertTrue(dnl.ready.is_set())
        self.assertIsInstance(info, TaskError)
        self.assertEqual(info.status, 0)


class TestFTPDownload(unittest.TestCase):
    
    def setUp(self):
        class FTPDownloadForTests(FTPDownloadThread):
            @property
            def _dataqueue(self):
                return DummyDataQueue
        self._download = FTPDownloadForTests
        self.connection = DummyFTPConnection('', '', '', 0)
        self.url = DummyURL('')

    def test_run_get_data(self):
        self.connection.socket = DummySocket(b'\x00'*100)
        dnl = self._download(self.url, self.connection, 0, 4*2**20, 100)
        dnl.run()
        self.assertTrue(dnl.ready.is_set())
        self.assertIsInstance(dnl.data_queue.get(), TaskProgress)
        info = dnl.data_queue.get()
        self.assertIsInstance(info, TaskData)
        self.assertEqual(len(info.data), 100)

    def test_run_get_data_error(self):
        self.connection.socket = DummySocket(b'\x00'*100)
        self.connection.socket.recv = lambda x: None
        dnl = self._download(self.url, self.connection, 0, 4*2**20, 100)
        dnl.run()
        info = dnl.data_queue.get()
        self.assertTrue(dnl.ready.is_set())
        self.assertIsInstance(info, TaskError)
        self.assertEqual(info.status, 0)

    def test_run_get_data_cancel(self):
        self.connection.socket = DummySocket(b'\x00'*100)
        dnl = self._download(self.url, self.connection, 0, 4*2**20, 100)
        dnl.cancel()
        dnl.run()
        info = dnl.data_queue.get()
        self.assertTrue(dnl.ready.is_set())
        self.assertIsInstance(info, TaskError)
        self.assertEqual(info.status, 0)
