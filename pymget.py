#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os
import threading, queue
from http import client
from collections import deque
import time, struct, re
import ftplib
from abc import ABCMeta, abstractproperty

VERSION = '1.15'

start_msg = '\nPyMGet v{}\n'

error_msg = '\nОшибка: '
warning_msg = '\nВнимание: '

connected_msg = 'Соединение с сервером {} OK'
downloading_msg = '\nПолучение файла {} {} байт ({}):'
redirect_msg = '\nПеренаправление с зеркала {} по адресу {}'

connection_error = 'не удалось соединиться с сервером {}'
no_partial_error = 'сервер {} не поддерживает скачивание по частям.'
http_error = 'неверный ответ сервера. Код {}'
filesize_error = 'размер файла на сервере {} {} байт отличается\nот полученного ранее {} байт.'
download_impossible_error = 'невозможно скачать файл.'
wrong_commandline_error = 'неверный аргумент командной строки. '
arg_needs_param_error = "Аргумент '{}' требует указания параметра."
wrong_param_format_error = "Неверный формат параметра '{}': {}"
file_not_found_error = "Файл '{}' не найден."
no_mirrors_error = 'Нет зеркал для скачивания.'

empty_filename_warning = 'невозможно определить имя файла на зеркале {}. Возможно, это другой файл.'
other_filename_warning = 'имя файла на зеркале {} отличается от {}. Возможно, это другой файл.'

anyway_download_question = 'Всё равно использовать зеркало {}? (да/Нет):'



def calc_units(size):
    if size >= 2**40:
        return '{:.2f}TiB'.format(size / 2**40)
    if size >= 2**30:
        return '{:.2f}GiB'.format(size / 2**30)
    if size >= 2**20:
        return '{:.2f}MiB'.format(size / 2**20)
    if size >= 2**10:
        return '{:.2f}KiB'.format(size / 2**10)
    return '{}B'.format(size)




class ProgressBar:

    WIDTH = 57

    def __init__(self):
        self.total = 0

    def update(self, complete, speed):
        if self.total != 0:
            percent = complete / self.total
            progress = round(self.WIDTH * percent)
            speed_str = '{}/s'.format(calc_units(speed))
        else:
            percent = 0
            progress = 0
            speed_str = ''

        progress_str = '[{}]'.format(('#'*progress).ljust(self.WIDTH, '-'))
        percent_str = '{:.2%}'.format(percent)
        bar = '{0} {1} {2}\r'.format(progress_str, percent_str.rjust(7), speed_str.rjust(12))

        sys.stdout.write(bar)
        sys.stdout.flush()



def singleton(cls):
	instances = {}
	def getinstance(*args):
		if cls not in instances:
			instances[cls] = cls(*args)
		return instances[cls]
	return getinstance

@singleton
class Console:

    def __init__(self):
        self.newline = True
        self.progressbar = ProgressBar()

    def out(self, text='', end='\n'):
        if not self.newline:
            print()
        print(text, end=end)
        self.newline = '\n' in end or text.endswith('\n')

    def error(self, text, end='\n'):
        self.out(error_msg + text, end)

    def warning(self, text, end='\n'):
        self.out(warning_msg + text, end)

    def progress(self, complete, speed):
        if self.newline:
            print()
        self.newline = False
        self.progressbar.update(complete, speed)

    def ask(self, text, default):
        YES = ['y', 'yes', 'д', 'да']
        NO = ['n', 'no', 'н', 'нет']
        self.out(text, end=' ')
        while True:
            answer = input().lower()
            if answer in YES:
                return True
            if answer in NO:
                return False
            if answer == '':
                return default




class Part:

    def __init__(self, name, status, offset, fragment_offset=0, complete=True, data=None, file_size=None, speed=0, gotten_size=0):
        self.name = name
        self.data = data
        self.status = status
        self.offset = offset
        self.fragment_offset = fragment_offset
        self.speed = speed
        self.complete = complete
        self.file_size = file_size
        self.gotten_size = gotten_size




class URL:

    def __init__(self, url):
        url_parts = url.split('/', 3)
        self.protocol = url_parts[0].strip(':').lower()
        host = url_parts[2]
        self.request = '/' + url_parts[3]
        if ':' in host:
            self.host, port = host.split(':')
            self.port = int(port)
        else:
            self.host = host
            self.port = 0
        self.filename = self.request.split('/')[-1]




class ConnectionThread(threading.Thread, metaclass=ABCMeta):

    def __init__(self, url, timeout):
        threading.Thread.__init__(self)
        self.url = url
        if self.url.port == 0:
            self.url.port = self.PORT
        self.timeout = timeout
        self.conn = None
        self.ready = threading.Event()

class HTTXThread(ConnectionThread, metaclass=ABCMeta):

    def run(self):
        self.conn = self.protocol(self.url.host, self.url.port, timeout=self.timeout)
        self.ready.set()

class HTTPThread(HTTXThread):

    PORT = 80

    def __init__(self, url, timeout):
        ConnectionThread.__init__(self, url, timeout)
        self.protocol = client.HTTPConnection

class HTTPSThread(HTTXThread):

    PORT = 443

    def __init__(self, url, timeout):
        ConnectionThread.__init__(self, url, timeout)
        self.protocol = client.HTTPSConnection

class FTPThread(ConnectionThread):

    PORT = 21

    def __init__(self, url, timeout):
        ConnectionThread.__init__(self, url, timeout)
        self.path = self.url.request.rsplit('/', 1)[0]

    def run(self):
        try:
            self.conn = ftplib.FTP(self.url.host, 'anonymous', '', timeout=self.timeout)
            self.conn.voidcmd('TYPE I')
            self.conn.cwd(self.path)
            self.conn.voidcmd('PASV')
        except:
            pass
        finally:
            self.ready.set()




class DownloadThread(threading.Thread, metaclass=ABCMeta):

    FRAGMENT_SIZE = 32 * 2**10

    def __init__(self, url, conn, offset, block_size):
        threading.Thread.__init__(self)
        self.name = url.host
        self.conn = conn
        self.request = url.request
        self.offset = offset
        self.block_size = block_size
        self.ready = threading.Event()

    def start(self):
        self.starttime = time.time()
        self.ready.clear()
        threading.Thread.start(self)

class HTTXDownloadThread(DownloadThread, metaclass=ABCMeta):

    user_agent = 'PyMGet/{} ({} {}, {})'.format(VERSION, os.uname().sysname, os.uname().machine, os.uname().release)

    def __init__(self, url, conn, offset, block_size):
        DownloadThread.__init__(self, url, conn, offset, block_size)
        self.location = ''

    def run(self):
        headers = {'User-Agent': self.user_agent, 'Refferer': '{}://{}/'.format(self.protocol, self.name), 
                    'Range': 'bytes={}-{}'.format(self.offset, self.offset + self.block_size - 1)}
        status = 0
        try:
            self.conn.request('GET', self.request, headers=headers)
            response = self.conn.getresponse()
            if response.status // 100 == 3:
                self.location = response.getheader('Location')
                if not self.location.startswith('http'):
                    self.location = '{}://{}/{}'.format(self.protocol, self.name, self.location.rsplit('/', 1)[0])
            if response.status != 206:
                status = response.status
                raise client.HTTPException
            file_size = int(response.getheader('Content-Range').split('/')[-1])
            part_size = int(response.getheader('Content-Length'))
            gotten_size = fragment_offset = 0
            while part_size > gotten_size:
                data = response.read(self.FRAGMENT_SIZE)
                self.time = time.time() - self.starttime
                gotten_size += len(data)
                speed = gotten_size / self.time
                part = Part(self.name, response.status, self.offset, fragment_offset, part_size <= gotten_size, data, file_size, speed, gotten_size)
                fragment_offset = gotten_size
                Manager.data_queue.put(part)
            response.close()
        except:
            part = Part(self.name, status, self.offset)
            Manager.data_queue.put(part)
        finally:
            self.ready.set()

class HTTPDownloadThread(HTTXDownloadThread):
    protocol = 'http'

class HTTPSDownloadThread(HTTXDownloadThread):
    protocol = 'https'

class FTPDownloadThread(DownloadThread):

    def __init__(self, url, conn, offset, block_size):
        DownloadThread.__init__(self, url, conn, offset, block_size)
        self.filename = url.request.rsplit('/', 1)[1]
        self.host = url.host

    def run(self):
        gotten_size = fragment_offset = 0
        try:
            file_size = self.conn.size(self.filename)
            sock = self.conn.transfercmd('RETR ' + self.filename, self.offset)
            while gotten_size < self.block_size:
                data = sock.recv(min(self.block_size - gotten_size, self.FRAGMENT_SIZE))
                self.time = time.time() - self.starttime
                gotten_size += len(data)
                speed = gotten_size / self.time
                complete = self.block_size - gotten_size <= 0 or file_size - self.offset - gotten_size <= 0
                part = Part(self.name, 206, self.offset, fragment_offset, complete, data, file_size, speed, gotten_size)
                fragment_offset = gotten_size
                Manager.data_queue.put(part)
                if complete:
                    break
        except:
            part = Part(self.name, 0, self.offset)
            Manager.data_queue.put(part)
        finally:
            self.ready.set()




class MirrorRedirect(Exception):

    def __init__(self, location):
        Exception.__init__(self)
        self.location = location

class Mirror(metaclass=ABCMeta):

    def create(url, block_size, timeout):
        if url.protocol == 'http':
            return HTTPMirror(url, block_size, timeout)
        if url.protocol == 'https':
            return HTTPSMirror(url, block_size, timeout)
        if url.protocol == 'ftp':
            return FTPMirror(url, block_size, timeout)

    def __init__(self, url, block_size, timeout):
        self.console = Console()
        self.url = url
        self.block_size = block_size
        self.timeout = timeout
        self.dnl_active = False
        self.conn = None
        self.connected = False
        self.dnl_thread = None
        self.conn_thread = self.connection_thread(self.url, self.timeout)
        self.conn_thread.start()

    def wait_connection(self):
        if not self.conn_thread.ready.wait(0.001):
            return False
        self.conn_thread.join()
        self.conn = self.conn_thread.conn
        if not self.connected:
            self.console.out(connected_msg.format(self.url.host))
            self.connected = True
        if self.dnl_active:
            if not self.dnl_thread.ready.wait(0.001):
                return False
            self.dnl_thread.join()
            self.dnl_active = False
        return True

    def download(self, offset):
        self.join()
        self.dnl_thread = self.download_thread(self.url, self.conn, offset, self.block_size)
        self.dnl_active = True
        self.dnl_thread.start()

    def join(self):
        if self.conn_thread:
            self.conn_thread.join()
        if self.dnl_thread:
            self.dnl_thread.join()

    def close(self):
        if self.conn:
            self.conn.close()

    @property
    def name(self):
        return self.url.host

    @property
    def filename(self):
        return self.url.filename

    @abstractproperty
    def connection_thread(self): pass

    @abstractproperty
    def download_thread(self): pass

class HTTPMirror(Mirror):

    @property
    def connection_thread(self):
        return HTTPThread

    @property
    def download_thread(self):
        return HTTPDownloadThread

class HTTPSMirror(Mirror):

    @property
    def connection_thread(self):
        return HTTPSThread

    @property
    def download_thread(self):
        return HTTPSDownloadThread

class FTPMirror(Mirror):

    def __init__(self, url, block_size, timeout):
        Mirror.__init__(self, url, block_size, timeout)
        self.conn_used = False

    def wait_connection(self):
        if self.conn_used:
            self.conn_thread = self.connection_thread(self.url, self.timeout)
            self.conn_used = False
            self.conn_thread.start()
        return Mirror.wait_connection(self)

    def download(self, offset):
        self.conn_used = True
        Mirror.download(self, offset)

    @property
    def connection_thread(self):
        return FTPThread

    @property
    def download_thread(self):
        return FTPDownloadThread



class Context:

    def __init__(self, filename):
        self.filename = filename + '.mget'
        self.failed_parts = []
        self.offset = 0
        self.written_bytes = 0
        self.open_mode = 'wb'
        try:
            with open(self.filename, 'rb') as f:
                data = f.read(struct.calcsize('NNq'))
                self.offset, self.written_bytes, failed_parts_len = struct.unpack('NNq', data)
                if failed_parts_len > 0:
                    data = f.read(struct.calcsize('N' * failed_parts_len))
                    self.failed_parts = struct.unpack('N' * failed_parts_len, data)
                self.open_mode = 'rb+'
        except:
            pass

    def modified(self, offset, written_bytes, failed_parts):
        return self.offset != offset or self.written_bytes != written_bytes or set(self.failed_parts) ^ set(failed_parts)

    def update(self, offset, written_bytes, failed_parts):
        if not self.modified(offset, written_bytes, failed_parts):
            return
        self.offset = offset
        self.written_bytes = written_bytes
        self.failed_parts = failed_parts
        failed_parts_len = len(self.failed_parts)
        format = 'NNq' + 'N' * failed_parts_len
        data = struct.pack(format, self.offset, self.written_bytes, failed_parts_len, *self.failed_parts)
        with open(self.filename, 'wb') as f:
            f.write(data)

    def delete(self):
        try:
            os.remove(self.filename)
        except:
            pass




class DownloadError(Exception): pass

class Manager:

    data_queue = queue.Queue()

    def __init__(self, urls, block_size, filename, timeout):
        self.console = Console()
        self.block_size = block_size
        self.filename = filename
        self.timeout = timeout
        self.mirrors = {}
        for url in urls:
            mirror = Mirror.create(URL(url), self.block_size, self.timeout)
            if self.check_filename(mirror):
                self.mirrors[mirror.name] = mirror
        if not self.mirrors:
            raise DownloadError(no_mirrors_error)
        if self.filename == '':
            self.filename = 'out'
        self.context = Context(self.filename)
        self.offset = self.context.offset
        self.written_bytes = self.context.written_bytes
        self.failed_parts = deque(self.context.failed_parts)
        self.file_size = 0
        self.parts_in_progress = []

    def check_filename(self, mirror):
        if self.filename == '':
            if mirror.filename == '':
                self.console.warning(empty_filename_warning.format(mirror.name))
                return self.console.ask(anyway_download_question.format(mirror.name), False)
            self.filename = mirror.filename
            return True
        if self.filename == mirror.filename:
            return True
        self.console.warning(other_filename_warning.format(mirror.name, self.filename))
        return self.console.ask(anyway_download_question.format(mirror.name), False)

    def wait_connections(self):
        active = 0
        for mirror in self.mirrors.values():
            if mirror.wait_connection():
                self.give_task(mirror)

    def give_task(self, mirror):
        if len(self.failed_parts) > 0:
            new_part = self.failed_parts.popleft()
            mirror.download(new_part)
            self.parts_in_progress.append(new_part)
        elif self.offset < self.file_size or self.file_size == 0:
            mirror.download(self.offset)
            self.parts_in_progress.append(self.offset)
            self.offset += self.block_size

    def download(self):
        speeds = {}
        gotten_sizes = {}
        with open(self.filename, self.context.open_mode) as outfile:
            while self.file_size == 0 or self.written_bytes < self.file_size:
                self.wait_connections()

                while True:
                    try:
                        part = self.data_queue.get(False, 0.01)
                        mirror = self.mirrors[part.name]

                        if part.complete:
                            self.parts_in_progress.remove(part.offset)

                        try:
                            try:
                                if part.status // 100 == 3:
                                    raise MirrorRedirect(mirror.dnl_thread.location)

                                assert part.status != 0, connection_error.format(part.name)
                                assert part.status != 200, no_partial_error.format(part.name)
                                assert part.status == 206, http_error.format(part.status)

                                if self.file_size == 0:
                                    self.file_size = part.file_size
                                    self.console.progressbar.total = self.file_size
                                    outfile.seek(self.file_size - 1, 0)
                                    outfile.write(b'\x00')
                                    self.console.out(downloading_msg.format(self.filename, self.file_size, calc_units(self.file_size)))

                                assert self.file_size == part.file_size, filesize_error.format(part.name, part.file_size, self.file_size)

                                outfile.seek(part.offset + part.fragment_offset, 0)
                                outfile.write(part.data)

                                speeds[part.name] = part.speed
                                gotten_sizes[part.name] = part.gotten_size

                                progress = self.written_bytes + sum(gotten_sizes.values())
                                self.console.progress(progress, sum(speeds.values()))

                                if part.complete:
                                    self.written_bytes += part.gotten_size
                                    gotten_sizes[part.name] = 0
                                    speeds[part.name] = 0

                            except AssertionError as e:
                                self.console.error(str(e))
                                raise
                            except MirrorRedirect as e:
                                self.console.out(redirect_msg.format(part.name, e.location))
                                new_mirror = Mirror(URL(e.location), self.block_size, self.timeout)
                                self.mirrors[new_mirror.name] = new_mirror
                                raise
                        except:
                            self.failed_parts.append(part.offset)
                            mirror.join()
                            mirror.close()
                            del self.mirrors[part.name]
                            del speeds[part.name]
                            del gotten_sizes[part.name]
                            if not self.mirrors:
                                raise DownloadError(download_impossible_error)
                        finally:
                            needle_parts = self.parts_in_progress.copy()
                            needle_parts.extend(self.failed_parts)
                            self.context.update(self.offset, self.written_bytes, needle_parts)
                    except queue.Empty:
                        break

            for mirror in self.mirrors.values():
                mirror.join()
                mirror.close()
            self.console.out()

        self.context.delete()




class CommandLineError(Exception): pass

class CommandLine:

    def __init__(self, argv):
        self.argv = argv[1:]
        self.block_size = 2**20
        self.filename = ''
        self.timeout = 10
        self.urls = []

    def get_arg(self, arg):
        if arg in self.argv:
            index = self.argv.index(arg)
            del self.argv[index]
            return index
        return None

    def get_param(self, arg):
        index = self.get_arg(arg)
        if not index is None:
            try:
                param = self.argv[index]
                del self.argv[index]
                return param
            except:
                raise CommandLineError(wrong_commandline_error + arg_needs_param_error.format(arg))
        return None

    def get_long_param(self, arg):
        parts = arg.split('=')
        if len(parts) < 2:
            raise CommandLineError(wrong_commandline_error + arg_needs_param_error.format(parts[0]))
        return parts[1]

    def parse_block_size(self, block_size):
        bs_re = re.compile('(\d+)(\w)?')
        matches = bs_re.match(block_size)
        if not matches:
            raise CommandLineError(wrong_commandline_error + wrong_param_format_error.format('block size', block_size))
        self.block_size = int(matches.group(1))
        if matches.group(2):
            if matches.group(2).lower() == 'k':
                self.block_size *= 2**10
            elif matches.group(2).lower() == 'm':
                self.block_size *= 2**20
            else:
                raise CommandLineError(wrong_commandline_error + wrong_param_format_error.format('block size', block_size))

    def parse_timeout(self, timeout):
        if not timeout.isdigit():
            raise CommandLineError(wrong_commandline_error + wrong_param_format_error.format('timeout', timeout))
        self.timeout = int(timeout)

    def parse_filename(self, filename):
        self.filename = filename

    def parse_urls(self, urls_file):
        try:
            with open(urls_file, 'r') as links:
                for link in links:
                    self.urls.append(link.strip('\r\n'))
        except:
            raise CommandLineError(file_not_found_error.format(urls_file))

    def parse_long_args(self):
        remain_args = []
        for arg in self.argv:
            if arg.startswith('--block-size'):
                block_size = self.get_long_param(arg)
                self.parse_block_size(block_size)
            elif arg.startswith('--timeout'):
                timeout = self.get_long_param(arg)
                self.parse_timeout(timeout)
            elif arg.startswith('--out-file'):
                filename = self.get_long_param(arg)
                self.parse_filename(filename)
            elif arg.startswith('--file'):
                urls_file = self.get_long_param(arg)
                self.parse_urls(urls_file)
            else:
                remain_args.append(arg)
        self.argv = remain_args

    def parse(self):
        block_size = self.get_param('-b')
        if block_size:
            self.parse_block_size(block_size)

        timeout = self.get_param('-T')
        if timeout:
            self.parse_timeout(timeout)

        filename = self.get_param('-o')
        if filename:
            self.parse_filename(filename)

        urls_file = self.get_param('-f')
        if urls_file:
            self.parse_urls(urls_file)

        self.parse_long_args()
        self.urls.extend(self.argv)




if __name__ == '__main__':

    console = Console()
    console.out(start_msg.format(VERSION))

    try:
        cl = CommandLine(sys.argv)
        cl.parse()
        manager = Manager(cl.urls, cl.block_size, cl.filename, cl.timeout)
        manager.download()
    except CommandLineError as e:
        console.error(str(e))
    except DownloadError as e:
        console.error(str(e))
    
