import unittest
import os, platform

from dummy_objects import DummyConsole
from pymget.command_line import CommandLine
from pymget.errors import CommandLineError
import pymget.console

TMPDIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tmp')

def setUpModule():
    os.mkdir(TMPDIR)

def tearDownModule():
    os.rmdir(TMPDIR)

class TestCommandLine(unittest.TestCase):

    def setUp(self):
        self.console = DummyConsole()
        self.cl = CommandLine(self.console, ['test'])
        self.urls_file = os.path.join(TMPDIR, 'urls.txt')

    def test_block_size_parser_with_number(self):
        self.cl.parse_block_size('123')
        self.assertEqual(self.cl.block_size, 123)

    def test_block_size_parser_with_number_and_k(self):
        self.cl.parse_block_size('123k')
        self.assertEqual(self.cl.block_size, 123 * 1024)

    def test_block_size_parser_with_number_and_m(self):
        self.cl.parse_block_size('123m')
        self.assertEqual(self.cl.block_size, 123 * 1024 * 1024)

    def test_block_size_parser_with_number_and_K(self):
        self.cl.parse_block_size('123K')
        self.assertEqual(self.cl.block_size, 123 * 1024)

    def test_block_size_parser_with_number_and_M(self):
        self.cl.parse_block_size('123M')
        self.assertEqual(self.cl.block_size, 123 * 1024 * 1024)

    def test_block_size_parser_with_number_and_wrong_symbol(self):
        with self.assertRaises(CommandLineError):
            self.cl.parse_block_size('123G')

    def test_block_size_parser_with_number_and_2_symbols(self):
        with self.assertRaises(CommandLineError):
            self.cl.parse_block_size('123Mk')

    def test_block_size_parser_without_number(self):
        with self.assertRaises(CommandLineError):
            self.cl.parse_block_size('M')

    def test_timeout_parser_with_number(self):
        self.cl.parse_timeout('5')
        self.assertEqual(self.cl.timeout, 5)

    def test_block_size_parser_with_letters(self):
        with self.assertRaises(CommandLineError):
            self.cl.parse_timeout('10s')

    def test_long_arg_parser(self):
        self.assertEqual(self.cl.parse_long_arg('--block-size=5'), '5')

    def test_urls_file_parser_not_found(self):
        with self.assertRaises(CommandLineError):
            self.cl.parse_urls_file(self.urls_file)

    def test_urls_file_parser_ok(self):
        links = ['http://server.com\n', 'http://server.net\n']
        with open(self.urls_file, 'w') as f:
            f.writelines(links)
        self.cl.parse_urls_file(self.urls_file)
        for url in map(lambda t: t.strip('\r\n'), links):
            self.assertIn(url, self.cl.urls)
        os.remove(self.urls_file)

    def test_urls_file_parser_permission_denied(self):
        if platform.uname().system == 'Windows':
            return
        with open(self.urls_file, 'w'): pass
        os.chmod(self.urls_file, 0)
        with self.assertRaises(CommandLineError):
            self.cl.parse_urls_file(self.urls_file)
        os.remove(self.urls_file)

    def test_urls_file_parser_non_unicode(self):
        with open(self.urls_file, 'wb') as f:
            f.write(b'\xff\xd8\xff\xe1\x1e\x00\x00\x00\x34\xab\x02')
        with self.assertRaises(CommandLineError):
            self.cl.parse_urls_file(self.urls_file)
        os.remove(self.urls_file)

    def test_parser_correct_urls(self):
        args = ['test', 'http://server.com', 'https://server.net', 'ftp://server.org']
        cl = CommandLine(self.console, args)
        cl.parse()
        urls = list(map(lambda u: u.url, cl.urls))
        for url in args[1:]:
            self.assertIn(url, urls)

    def test_parser_wrong_urls(self):
        args = ['test', 'server.com', 'htt://server.org']
        cl = CommandLine(self.console, args)
        cl.parse()
        urls = list(map(lambda u: u.url, cl.urls))
        self.assertFalse(urls)

    def test_urls_file_parser_with_urls_in_command_line(self):
        links = ['http://server.com\n', 'https://server.net\n']
        args = ['test', '-u', self.urls_file, 'ftp://server.org']
        with open(self.urls_file, 'w') as f:
            f.writelines(links)
        cl = CommandLine(self.console, args)
        cl.parse()
        links.extend(args[-1:])
        urls = list(map(lambda u: u.url, cl.urls))
        for url in map(lambda t: t.strip('\r\n'), links):
            self.assertIn(url, urls)
        os.remove(self.urls_file)

    def test_parser_block_size_short_argument(self):
        args = ['test', '-b', '100']
        cl = CommandLine(self.console, args)
        cl.parse()
        self.assertEqual(cl.block_size, 100)

    def test_parser_block_size_long_argument(self):
        args = ['test', '--block-size=100',]
        cl = CommandLine(self.console, args)
        cl.parse()
        self.assertEqual(cl.block_size, 100)

    def test_parser_timeout_short_argument(self):
        args = ['test', '-T', '100']
        cl = CommandLine(self.console, args)
        cl.parse()
        self.assertEqual(cl.timeout, 100)

    def test_parser_timeout_long_argument(self):
        args = ['test', '--timeout=100',]
        cl = CommandLine(self.console, args)
        cl.parse()
        self.assertEqual(cl.timeout, 100)

    def test_parser_outfile_short_argument(self):
        args = ['test', '-o', 'foo.bar']
        cl = CommandLine(self.console, args)
        cl.parse()
        self.assertEqual(cl.filename, 'foo.bar')

    def test_parser_outfile_long_argument(self):
        args = ['test', '--out-file=foo.bar',]
        cl = CommandLine(self.console, args)
        cl.parse()
        self.assertEqual(cl.filename, 'foo.bar')

    def test_parser_urls_file_short_argument(self):
        links = ['http://server.com\n', 'http://server.net\n']
        with open(self.urls_file, 'w') as f:
            f.writelines(links)
        args = ['test', '-u', self.urls_file]
        cl = CommandLine(self.console, args)
        cl.parse()
        urls = list(map(lambda u: u.url, cl.urls))
        for url in map(lambda t: t.strip('\r\n'), links):
            self.assertIn(url, urls)
        os.remove(self.urls_file)

    def test_parser_urls_file_long_argument(self):
        links = ['http://server.com\n', 'http://server.net\n']
        with open(self.urls_file, 'w') as f:
            f.writelines(links)
        args = ['test', '--urls-file=' + self.urls_file]
        cl = CommandLine(self.console, args)
        cl.parse()
        urls = list(map(lambda u: u.url, cl.urls))
        for url in map(lambda t: t.strip('\r\n'), links):
            self.assertIn(url, urls)
        os.remove(self.urls_file)
