import unittest
from unittest.mock import Mock, MagicMock, patch

from pymget import networking as nw
from pymget import task_info as ti

class testURL(unittest.TestCase):

    def test_http_no_path_no_endslash(self):
        url = nw.URL('http://server.com')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_https_no_path_no_endslash(self):
        url = nw.URL('https://server.com')
        self.assertEqual(url.protocol, 'https')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_ftp_no_path_no_endslash(self):
        url = nw.URL('ftp://server.com')
        self.assertEqual(url.protocol, 'ftp')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_no_path_no_endslash_with_port(self):
        url = nw.URL('http://server.com:8888')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server.com:8888')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_no_path_no_endslash_with_digits(self):
        url = nw.URL('http://server123.com')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server123.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_no_path_no_endslash_with_digits_only(self):
        url = nw.URL('http://123.com')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, '123.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_no_path_no_endslash_with_minus(self):
        url = nw.URL('http://ser-ver.com')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'ser-ver.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_no_path_with_endslash(self):
        url = nw.URL('http://server.com/')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/')
        self.assertEqual(url.path, '')
        self.assertEqual(url.filename, '')

    def test_http_with_path(self):
        url = nw.URL('http://server.com/path/to/file')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/path/to/file')
        self.assertEqual(url.path, 'path/to')
        self.assertEqual(url.filename, 'file')

    def test_http_with_path_with_endslash(self):
        url = nw.URL('http://server.com/path/to/file/')
        self.assertEqual(url.protocol, 'http')
        self.assertEqual(url.host, 'server.com')
        self.assertEqual(url.request, '/path/to/file/')
        self.assertEqual(url.path, 'path/to/file')
        self.assertEqual(url.filename, '')




class TestHTTXConnection(unittest.TestCase):

    def test_run_ok(self):
        task_info = Mock()
        conn = nw.HTTPThread(Mock(), 0)
        conn.data_queue = Mock()
        conn.connect = Mock(return_value=task_info)
        self.assertFalse(conn.ready.is_set())
        conn.run()
        conn.data_queue.put.assert_called_with(task_info)
        self.assertTrue(conn.ready.is_set())

    def test_run_error(self):
        conn = nw.HTTPThread(Mock(), 0)
        conn.data_queue = Mock()
        conn.connect = Mock(side_effect=Exception)
        self.assertFalse(conn.ready.is_set())
        conn.run()
        args = conn.data_queue.put.call_args
        self.assertIsInstance(args[0][0], ti.TaskHeadError)
        self.assertTrue(conn.ready.is_set())

    def test_redirect_with_host(self):
        location = 'http://server.com/path/to/file'
        conn = nw.HTTPThread(Mock(), 0)
        info = conn.redirect(location, 301)
        self.assertIsInstance(info, ti.TaskRedirect)
        self.assertEqual(info.location.url, location)

    def test_redirect_absolute(self):
        url = Mock()
        url.protocol = 'http'
        url.host = 'server.com'
        conn = nw.HTTPThread(url, 0)
        info = conn.redirect('/path/to/file', 301)
        self.assertIsInstance(info, ti.TaskRedirect)
        self.assertEqual(info.location.url, 'http://server.com/path/to/file')

    def test_redirect_relative(self):
        url = Mock()
        url.protocol = 'http'
        url.host = 'server.com'
        url.request = '/path/to/file'
        conn = nw.HTTPThread(url, 0)
        info = conn.redirect('another_file', 301)
        self.assertIsInstance(info, ti.TaskRedirect)
        self.assertEqual(info.location.url, 'http://server.com/path/to/another_file')

    @patch('http.client.HTTPConnection')
    def test_connect_ok(self, conn_mock):
        response = Mock(status=200)
        response.getheader.return_value = '100'
        conn_mock.return_value.getresponse.return_value = response
        conn = nw.HTTPThread(Mock(), 0)
        info = conn.connect()
        self.assertIsInstance(info, ti.TaskHeadData)
        self.assertEqual(info.file_size, 100)

    @patch('http.client.HTTPConnection')
    def test_connect_redirect(self, conn_mock):
        response = Mock(status=301)
        response.getheader.return_value = 'http://server.com'
        conn_mock.return_value.getresponse.return_value = response
        conn = nw.HTTPThread(Mock(), 0)
        info = conn.connect()
        self.assertIsInstance(info, ti.TaskRedirect)
        self.assertEqual(info.location.url, 'http://server.com')

    @patch('http.client.HTTPConnection')
    def test_connect_error(self, conn_mock):
        response = Mock(status=404)
        conn_mock.return_value.getresponse.return_value = response
        conn = nw.HTTPThread(Mock(), 0)
        info = conn.connect()
        self.assertIsInstance(info, ti.TaskHeadError)
        self.assertEqual(info.status, 404)




class TestFTPConnection(unittest.TestCase):

    @patch('ftplib.FTP')
    def test_connect(self, conn_mock):
        conn_mock.return_value.size.return_value = 100
        conn = nw.FTPThread(Mock(), 0)
        info = conn.connect()
        self.assertIsInstance(info, ti.TaskHeadData)
        self.assertEqual(info.file_size, 100)




class TestHTTXDownload(unittest.TestCase):
    
    @patch('http.client.HTTPConnection')
    def setUp(self, conn_mock):
        self.response = Mock(status=206)
        self.response.getheader.return_value = '100'
        self.response.read.return_value = b'\x00'*100
        conn_mock.getresponse.return_value = self.response
        self.dnl = nw.HTTXDownloadThread(Mock(request='/test', protocol='http', host='server.com'), conn_mock, 0, 4*2**20)
        self.dnl.data_queue = Mock()
        self.headers = {
                    'User-Agent': nw.HTTXDownloadThread.user_agent,
                    'Refferer': 'http://server.com/', 
                    'Range': 'bytes=0-4194303'
         }

    def test_run_get_data(self):
        self.dnl.run()
        task_progress_args = self.dnl.data_queue.put.call_args_list[0][0]
        task_data_args = self.dnl.data_queue.put.call_args_list[1][0]
        self.assertTrue(self.dnl.ready.is_set())
        self.assertIsInstance(task_progress_args[0], ti.TaskProgress)
        info = task_data_args[0]
        self.assertIsInstance(info, ti.TaskData)
        self.dnl.conn.request.assert_called_with('GET', '/test', headers=self.headers)
        self.assertEqual(len(info.data), 100)

    def test_run_get_data_no_partial(self):
        self.response.status = 200
        self.dnl.run()
        task_info_args = self.dnl.data_queue.put.call_args_list[0][0]
        info = task_info_args[0]
        self.assertTrue(self.dnl.ready.is_set())
        self.assertIsInstance(info, ti.TaskError)
        self.assertEqual(info.status, 200)

    def test_run_get_data_http_error(self):
        self.response.status = 404
        self.dnl.run()
        task_info_args = self.dnl.data_queue.put.call_args_list[0][0]
        info = task_info_args[0]
        self.assertTrue(self.dnl.ready.is_set())
        self.assertIsInstance(info, ti.TaskError)
        self.assertEqual(info.status, 404)

    def test_run_get_data_get_error(self):
        self.response.read = Mock(side_effect=Exception)
        self.dnl.run()
        task_info_args = self.dnl.data_queue.put.call_args_list[0][0]
        info = task_info_args[0]
        self.assertTrue(self.dnl.ready.is_set())
        self.assertIsInstance(info, ti.TaskError)
        self.assertEqual(info.status, 0)

    def test_run_get_data_cancel(self):
        self.dnl.cancel()
        self.dnl.run()
        task_info_args = self.dnl.data_queue.put.call_args_list[0][0]
        info = task_info_args[0]
        self.assertTrue(self.dnl.ready, ti.TaskError)
        self.assertEqual(info.status, 0)


class TestFTPDownload(unittest.TestCase):
    
    @patch('ftplib.FTP')
    def setUp(self, conn_mock):
        self.socket = Mock()
        self.socket.recv.return_value = b'\x00'*100
        conn_mock.transfercmd.return_value = self.socket
        self.dnl = nw.FTPDownloadThread(Mock(filename='test', host='server.com'), conn_mock, 0, 4*2**20, 100)
        self.dnl.data_queue = Mock()

    def test_run_get_data(self):
        self.dnl.run()
        task_progress_args = self.dnl.data_queue.put.call_args_list[0][0]
        task_data_args = self.dnl.data_queue.put.call_args_list[1][0]
        self.assertTrue(self.dnl.ready.is_set())
        self.assertIsInstance(task_progress_args[0], ti.TaskProgress)
        info = task_data_args[0]
        self.assertIsInstance(info, ti.TaskData)
        self.assertEqual(len(info.data), 100)

    def test_run_get_data_error(self):
        self.socket.recv.return_value = None
        self.dnl.run()
        task_info_args = self.dnl.data_queue.put.call_args_list[0][0]
        info = task_info_args[0]
        self.assertTrue(self.dnl.ready.is_set())
        self.assertIsInstance(info, ti.TaskError)
        self.assertEqual(info.status, 0)

    def test_run_get_data_cancel(self):
        self.dnl.cancel()
        self.dnl.run()
        task_info_args = self.dnl.data_queue.put.call_args_list[0][0]
        info = task_info_args[0]
        self.assertTrue(self.dnl.ready.is_set())
        self.assertIsInstance(info, ti.TaskError)
        self.assertEqual(info.status, 0)
