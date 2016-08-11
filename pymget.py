#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os
import threading, queue
from http import client
from collections import deque
import time, struct, re
import ftplib
from abc import ABCMeta, abstractmethod, abstractproperty

VERSION = '1.21'

start_msg = '\nPyMGet v{}\n'

error_msg = '\nОшибка: '
warning_msg = '\nВнимание: '

connected_msg = 'Соединение с сервером {} OK'
downloading_msg = '\nПолучение файла {} {} байт ({}):\n'
redirect_msg = '\nПеренаправление с зеркала {} по адресу {}'
cancel_msg = 'Операция отменена пользователем.'

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
file_open_error = "не удалось открыть файл '{}': {}"
file_create_error = "не удалось создать файл '{}': {}"
file_write_error = "запись в файл '{}' завершилась неудачей."
permission_denied_error = 'отказано в доступе.'

empty_filename_warning = 'невозможно определить имя файла на зеркале {}. Возможно, это другой файл.'
other_filename_warning = 'имя файла на зеркале {} отличается от {}. Возможно, это другой файл.'

anyway_download_question = 'Всё равно использовать зеркало {}? (да/НЕТ):'
rewrite_file_question = 'Файл {} существует. Вы действительно хотите перезаписать файл? (да/НЕТ):'
file_create_question = 'Файл {} не найден. Начать скачивание заново? (ДА/нет):'



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
        self._total = 0
        self.time = 0

    @property
    def total(self):
        return self._total

    @total.setter
    def total(self, total):
        self.time = time.time()
        self._total = total

    def update(self, complete, gotten_bytes):
        try:
            speed = gotten_bytes / (time.time() - self.time)
            percent = complete / self.total
            progress = round(self.WIDTH * percent)
        except:
            speed = 0
            percent = 0
            progress = 0

        bar = '[{0:-<{1}}] {2:>7.2%} {3:>10}/s\r'.format('#'*progress, self.WIDTH, percent, calc_units(speed))

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
        if text:
            self.out(error_msg + text, end)

    def warning(self, text, end='\n'):
        if text:
            self.out(warning_msg + text, end)

    def progress(self, complete, gotten_bytes):
        if self.newline:
            print()
        self.newline = False
        self.progressbar.update(complete, gotten_bytes)

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




class Part(metaclass=ABCMeta):

    def __init__(self, name, status):
        self.console = Console()
        self.name = name
        self.status = status

    def delete_mirror(self, manager):
        mirror = manager.mirrors[self.name]
        mirror.join()
        del manager.mirrors[self.name]
        if self.name in manager.gotten_sizes:
            del manager.gotten_sizes[self.name]
        if not manager.mirrors:
            raise DownloadError(download_impossible_error)

    @abstractmethod
    def process(self, manager): pass

class HeadPart(Part):

    def __init__(self, name, status, file_size):
        Part.__init__(self, name, status)
        self.file_size = file_size

    def process(self, manager):
        if manager.file_size == 0:
            manager.file_size = self.file_size
            self.console.progressbar.total = self.file_size
            manager.outfile.seek(self.file_size - 1)
            manager.outfile.write(b'\x00')
            self.console.out(downloading_msg.format(manager.filename, self.file_size, calc_units(self.file_size)))
        elif manager.file_size != self.file_size:
            self.console.error(filesize_error.format(self.name, self.file_size, self.file_size))
            self.delete_mirror(manager)
            return
        mirror = manager.mirrors[self.name]
        mirror.file_size = self.file_size
        mirror.ready = True
        mirror.connect_message()
        

class RedirectPart(Part):

    def __init__(self, name, status, location):
        Part.__init__(self, name, status)
        self.location = location

    def process(self, manager):
        try:
            self.delete_mirror(manager)
        except:
            pass
        new_mirror = Mirror.create(URL(self.location), manager.block_size, manager.timeout)
        manager.mirrors[new_mirror.name] = new_mirror
        self.console.out(redirect_msg.format(self.name, self.location))

class HeadErrorPart(Part):

    def process(self, manager):
        if self.status == 0:
            msg = connection_error.format(self.name)
        elif self.status == 200:
            msg = no_partial_error.format(self.name)
        else:
            msg = http_error.format(self.status)
        self.console.error(msg)
        self.delete_mirror(manager)
        

class ErrorPart(HeadErrorPart):

    def __init__(self, name, status, offset):
        Part.__init__(self, name, status)
        self.offset = offset

    def del_active_part(self, manager):
        manager.parts_in_progress.remove(self.offset)

    def add_failed_part(self, manager):
        manager.failed_parts.append(self.offset)

    def process(self, manager):
        self.add_failed_part(manager)
        HeadErrorPart.process(self, manager)

class DataPart(ErrorPart):

    def __init__(self, name, status, offset, fragment_offset, data, gotten_size):
        ErrorPart.__init__(self, name, status, offset)
        self.data = data
        self.fragment_offset = fragment_offset
        self.gotten_size = gotten_size

    def process(self, manager):
        manager.gotten_sizes[self.name] = self.gotten_size
        manager.outfile.seek(self.offset + self.fragment_offset)
        manager.outfile.write(self.data)
        progress = manager.written_bytes + sum(manager.gotten_sizes.values())
        self.console.progress(progress, progress - manager.old_progress)

class FinalDataPart(DataPart):

    def process(self, manager):
        self.del_active_part(manager)
        DataPart.process(self, manager)
        manager.written_bytes += self.gotten_size
        manager.gotten_sizes[self.name] = 0
        mirror = manager.mirrors[self.name]
        mirror.done()




class URL:

    def __init__(self, url):
        url_parts = url.split('/', 3)
        self.protocol = url_parts[0].strip(':').lower()
        self.host = url_parts[2]
        self.request = '/' + url_parts[3]
        self.filename = self.request.split('/')[-1]




class ConnectionThread(threading.Thread, metaclass=ABCMeta):

    def __init__(self, url, timeout):
        threading.Thread.__init__(self)
        self.url = url
        self.timeout = timeout
        self.conn = None
        self.ready = threading.Event()

    def run(self):
        try:
            part = self.connect()
        except:
            part = HeadErrorPart(self.url.host, 0)
        finally:
            Manager.data_queue.put(part)
            self.ready.set()

    @abstractmethod
    def connect(self): pass

class HTTXThread(ConnectionThread, metaclass=ABCMeta):

    def connect(self):
        self.conn = self.protocol(self.url.host, timeout=self.timeout)
        self.conn.request('HEAD', self.url.request)
        response = self.conn.getresponse()
        if response.status // 100 == 3:
            location = response.getheader('Location')
            path = ''
            if not location.startswith('http'):
                if not location.startswith('/'):
                    path = '/' + self.url.request.rsplit('/', 1)[0]
                location = '{}://{}{}'.format(self.url.protocol, self.url.host, path + location)
            return RedirectPart(self.url.host, response.status, location)
        if response.status != 200:
            return HeadErrorPart(self.url.host, response.status)
        file_size = int(response.getheader('Content-Length'))
        part = HeadPart(self.url.host, response.status, file_size)
        response.close()
        return part

class HTTPThread(HTTXThread):

    def __init__(self, url, timeout):
        ConnectionThread.__init__(self, url, timeout)
        self.protocol = client.HTTPConnection

class HTTPSThread(HTTXThread):

    def __init__(self, url, timeout):
        ConnectionThread.__init__(self, url, timeout)
        self.protocol = client.HTTPSConnection

class FTPThread(ConnectionThread):

    def __init__(self, url, timeout):
        ConnectionThread.__init__(self, url, timeout)
        self.path = self.url.request.rsplit('/', 1)[0]

    def connect(self):
        self.conn = ftplib.FTP(self.url.host, 'anonymous', '', timeout=self.timeout)
        self.conn.voidcmd('TYPE I')
        self.conn.cwd(self.path)
        self.conn.voidcmd('PASV')
        file_size = self.conn.size(self.url.filename)
        return HeadPart(self.url.host, 200, file_size)




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

class HTTXDownloadThread(DownloadThread, metaclass=ABCMeta):

    user_agent = 'PyMGet/{} ({} {}, {})'.format(VERSION, os.uname().sysname, os.uname().machine, os.uname().release)

    def run(self):
        headers = {'User-Agent': self.user_agent, 'Refferer': '{}://{}/'.format(self.protocol, self.name), 
                    'Range': 'bytes={}-{}'.format(self.offset, self.offset + self.block_size - 1)}
        status = 0
        try:
            self.conn.request('GET', self.request, headers=headers)
            response = self.conn.getresponse()
            if response.status != 206:
                status = response.status
                raise client.HTTPException
            part_size = int(response.getheader('Content-Length'))
            gotten_size = fragment_offset = 0
            while part_size > gotten_size:
                data = response.read(self.FRAGMENT_SIZE)
                gotten_size += len(data)
                if part_size <= gotten_size:
                    part = FinalDataPart(self.name, response.status, self.offset, fragment_offset, data, gotten_size)
                else:
                    part = DataPart(self.name, response.status, self.offset, fragment_offset, data, gotten_size)
                fragment_offset = gotten_size
                Manager.data_queue.put(part)
            response.close()
        except Exception as e:
            part = ErrorPart(self.name, status, self.offset)
            Manager.data_queue.put(part)
        finally:
            self.ready.set()

class HTTPDownloadThread(HTTXDownloadThread):
    protocol = 'http'

class HTTPSDownloadThread(HTTXDownloadThread):
    protocol = 'https'

class FTPDownloadThread(DownloadThread):

    def __init__(self, url, conn, offset, block_size, file_size):
        DownloadThread.__init__(self, url, conn, offset, block_size)
        self.filename = url.request.rsplit('/', 1)[1]
        self.host = url.host
        self.file_size = file_size

    def run(self):
        gotten_size = fragment_offset = 0
        try:
            sock = self.conn.transfercmd('RETR ' + self.filename, self.offset)
            while gotten_size < self.block_size:
                data = sock.recv(min(self.block_size - gotten_size, self.FRAGMENT_SIZE))
                if not data:
                    raise Exception
                gotten_size += len(data)
                complete = self.block_size - gotten_size <= 0 or self.file_size - self.offset - gotten_size <= 0
                if complete:
                    part = FinalDataPart(self.name, 206, self.offset, fragment_offset, data, gotten_size)
                else:
                    part = DataPart(self.name, 206, self.offset, fragment_offset, data, gotten_size)
                fragment_offset = gotten_size
                Manager.data_queue.put(part)
                if complete:
                    break
            sock.close()
        except:
            part = ErrorPart(self.name, 0, self.offset)
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
        self.file_size = 0
        self.conn = None
        self.need_connect = True
        self.ready = False
        self.conn_thread = None
        self.dnl_thread = None

    def connect(self):
        self.ready = False
        self.need_connect = False
        self.conn_thread = self.connection_thread(self.url, self.timeout)
        self.conn_thread.start()

    def wait_connection(self):
        if self.conn_thread:
            if not self.conn_thread.ready.wait(0.001):
                return False
            self.conn_thread.join()
            self.conn = self.conn_thread.conn
            self.conn_thread = None
        if self.dnl_thread:
            if not self.dnl_thread.ready.wait(0.001):
                return False
            self.dnl_thread.join()
            self.dnl_thread = None
        return True

    def download(self, offset):
        self.ready = False
        self.dnl_thread = self.download_thread(self.url, self.conn, offset, self.block_size)
        self.dnl_thread.start()

    def done(self):
        self.ready = True

    def connect_message(self):
        self.console.out(connected_msg.format(self.url.host))

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
        self.connected = False

    def done(self):
        self.ready = False
        self.need_connect = True

    @property
    def connection_thread(self):
        return FTPThread

    @property
    def download_thread(self):
        return FTPDownloadThread

    def download(self, offset):
        self.ready = False
        self.dnl_thread = self.download_thread(self.url, self.conn, offset, self.block_size, self.file_size)
        self.dnl_thread.start()

    def connect_message(self):
        if self.connected:
            return
        self.connected = True
        Mirror.connect_message(self)



@singleton
class Context:

    def __init__(self, filename):
        self.filename = filename + '.mget'
        self.failed_parts = []
        self.offset = 0
        self.written_bytes = 0
        try:
            with open(self.filename, 'rb') as f:
                data = f.read(struct.calcsize('NNq'))
                self.offset, self.written_bytes, failed_parts_len = struct.unpack('NNq', data)
                if failed_parts_len > 0:
                    data = f.read(struct.calcsize('N' * failed_parts_len))
                    self.failed_parts = struct.unpack('N' * failed_parts_len, data)
            self.exists = True
        except:
            self.exists = False

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

    def reset(self):
        self.update(0, 0, [])

    def delete(self):
        try:
            os.remove(self.filename)
        except:
            pass




class FileError(Exception): pass
class CancelError(Exception): pass

class OutputFile:

    def __init__(self, filename):
        self.filename = filename
        self.console = Console()
        self.context = Context(self.filename)
        self.file = self.open_file(self.context.exists)

    def open_file(self, context_exists):
        if context_exists:
            try:
                return open(self.filename, 'rb+')
            except:
                if os.path.isfile(self.filename):
                    raise FileError(file_open_error.format(self.filename, permission_denied_error))
                if not self.console.ask(file_create_question.format(self.filename), True):
                    raise CancelError(cancel_msg)
                self.context.reset()
                return self.open_file(False)
        else:
            if os.path.isfile(self.filename):
                if not self.console.ask(rewrite_file_question.format(self.filename), False):
                    raise CancelError(cancel_msg)
            try:
                return open(self.filename, 'wb')
            except:
                raise FileError(file_create_error.format(self.filename, permission_denied_error))

    def __enter__(self):
        return self

    def __exit__(self, exception_type, exception_value, traceback):
        try:
            self.file.close()
        except:
            return False

    def seek(self, offset):
        try:
            self.file.seek(offset, 0)
        except:
            raise FileError(file_write_error.format(self.filename))

    def write(self, data):
        try:
            return self.file.write(data)
        except:
            raise FileError(file_write_error.format(self.filename))




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
        self.outfile = OutputFile(self.filename)
        self.offset = self.context.offset
        self.written_bytes = self.context.written_bytes
        self.old_progress = self.written_bytes
        self.failed_parts = deque(self.context.failed_parts)
        self.file_size = 0
        self.parts_in_progress = []
        self.gotten_sizes = {}

    def check_filename(self, mirror):
        if self.filename == '':
            if mirror.filename == '':
                self.console.warning(empty_filename_warning.format(mirror.name))
                return self.console.ask(anyway_download_question.format(mirror.name), False)
            self.filename = mirror.filename
            return True
        if os.path.basename(self.filename) == mirror.filename:
            return True
        self.console.warning(other_filename_warning.format(mirror.name, self.filename))
        return self.console.ask(anyway_download_question.format(mirror.name), False)

    def wait_connections(self):
        for name, mirror in self.mirrors.items():
            if mirror.wait_connection():
                if mirror.ready:
                    self.give_task(mirror)
                elif mirror.need_connect:
                    mirror.connect()

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
        with self.outfile:
            while self.file_size == 0 or self.written_bytes < self.file_size:
                self.wait_connections()
                while True:
                    try:
                        part = self.data_queue.get(False, 0.01)
                        try:
                            part.process(self)
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
    except FileError as e:
        console.error(str(e))
    except CancelError as e:
        console.out(str(e))
    
