#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os
import threading, queue
from http import client
from collections import deque
import time
import struct

VERSION = '1.04'

start_msg = '\nPyMGet v{}\n'

connected_msg = 'Соединение с сервером {} OK'
downloading_msg = '\nПолучение файла {} {} байт ({}):\n\n'

connection_error = '\nОшибка: не удалось соединиться с сервером {}\n\n'
no_partial_error = '\nОшибка: сервер {} не поддерживает скачивание по частям.\n\n'
http_error = '\nОшибка: неверный ответ сервера. Код {}\n\n'
filesize_error = '\nОшибка: размер файла на сервере {} {} байт отличается\nот полученного ранее {} байт.\n\n'



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

    WIDTH = 58

    def __init__(self):
        self.total = 0

    def update(self, complete, speed):
        if self.total != 0:
            progress = round(self.WIDTH * complete / self.total)
            speed_str = '{}/s'.format(calc_units(speed))
        else:
            progress = 0
            speed_str = ''

        progress_str = '[{}]'.format(('#'*progress).ljust(self.WIDTH, '-'))
        percent_str = '{:.2%}'.format(progress / self.WIDTH)
        bar = '{0} {1} {2}\r'.format(progress_str, percent_str.rjust(7), speed_str.rjust(11))

        sys.stdout.write(bar)
        sys.stdout.flush()




class Console:

    def __init__(self, progressbar):
        self.newline = True
        self.progressbar = progressbar

    def out(self, text, end='\n'):
        if not self.newline:
            print()
        print(text, end=end)
        self.newline = '\n' in end or text.endswith('\n')

    def progress(self, complete, speed):
        self.newline = False
        self.progressbar.update(complete, speed)




class Part:

    def __init__(self, name, status, begin, data=None, file_size=None):
        self.name = name
        self.data = data
        self.status = status
        self.begin = begin
        self.file_size = file_size




class ConnectionThread(threading.Thread):

    def __init__(self, host, timeout, port=80):
        threading.Thread.__init__(self)
        self.timeout = timeout
        self.host = host
        self.port = port
        self.ready = threading.Event()

    def run(self):
        self.conn = client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        self.ready.set()




class DownloadThread(threading.Thread):

    user_agent = 'PyMGet/{} ({} {}, {})'.format(VERSION, os.uname().sysname, os.uname().machine, os.uname().release)

    def __init__(self, name, conn, request, begin, block_size):
        threading.Thread.__init__(self)
        self.name = name
        self.conn = conn
        self.request = request
        self.begin = begin
        self.block_size = block_size

    def start(self):
        self.starttime = time.time()
        threading.Thread.start(self)

    def run(self):
        headers = {'User-Agent': self.user_agent, 'Range': 'bytes={}-{}'.format(self.begin, self.begin + self.block_size - 1)}
        status = 0
        try:
            self.conn.request('GET', self.request, headers=headers)
            response = self.conn.getresponse()
            if response.status != 206:
                status = response.status
                raise client.HTTPException
            file_size = int(response.getheader('Content-Range').split('/')[-1])
            data = response.read()
            part = Part(self.name, response.status, self.begin, data, file_size)
            response.close()
        except:
            part = Part(self.name, status, self.begin)
        finally:
            self.time = time.time() - self.starttime
            Manager.data_queue.put(part)




class Mirror:

    def __init__(self, host, request, block_size, timeout):
        self.block_size = block_size
        self.timeout = timeout
        self.name = host
        if ':' in self.name:
            self.host, port = self.name.split(':')
            self.port = int(port)
        else:
            self.host = self.name
            self.port = 80
        self.request = request
        self.thread = ConnectionThread(self.host, self.timeout, self.port)
        self.thread.start()

    def wait_connection(self):
        if not self.thread.ready.wait(0.1):
            return False
        self.thread.join()
        self.conn = self.thread.conn
        return True

    def download(self, begin):
        self.thread = DownloadThread(self.name, self.conn, self.request, begin, self.block_size)
        self.thread.start()

    def close(self):
        self.conn.close()




class StateFile:

    def __init__(self, filename):
        self.filename = filename + '.mget'
        self.failed_parts = []
        self.begin = 0
        self.written_bytes = 0
        self.open_mode = 'wb'
        try:
            with open(self.filename, 'rb') as f:
                data = f.read(struct.calcsize('NNq'))
                self.begin, self.written_bytes, failed_parts_len = struct.unpack('NNq', data)
                if failed_parts_len > 0:
                    data = f.read(struct.calcsize('N' * failed_parts_len))
                    self.failed_parts = struct.unpack('N' * failed_parts_len, data)
                self.open_mode = 'rb+'
        except:
            pass

    def update(self, begin, written_bytes, failed_parts):
        self.begin = begin
        self.written_bytes = written_bytes
        self.failed_parts = failed_parts
        failed_parts_len = len(self.failed_parts)
        format = 'NNq' + 'N' * failed_parts_len
        data = struct.pack(format, self.begin, self.written_bytes, failed_parts_len, *self.failed_parts)
        with open(self.filename, 'wb') as f:
            f.write(data)

    def delete(self):
        try:
            os.remove(self.filename)
        except:
            pass




class Manager:

    data_queue = queue.Queue()

    def __init__(self, urls, block_size, filename, timeout):
        if filename is None:
            self.filename = urls[0].split('/')[-1]
            if self.filename == '':
                self.filename = 'out'
        else:
            self.filename = filename

        self.block_size = block_size

        self.mirrors = {}
        for url in urls:
            url_parts = url.split('/', 3)
            host = url_parts[2]
            request = '/' + url_parts[3]
            self.mirrors[host] = Mirror(host, request, self.block_size, timeout)

    def download(self):
        statefile = StateFile(self.filename)
        begin = statefile.begin
        written_bytes = statefile.written_bytes
        failed_parts = deque(statefile.failed_parts)
        parts_in_progress = []
        file_size = 0
        wait_mirrors = self.mirrors.copy()
        speeds = {}

        progress = ProgressBar()
        console = Console(progress)

        while len(wait_mirrors) > 0:
            remain_mirrors = {}
            for name, mirror in wait_mirrors.items():
                if not mirror.wait_connection():
                    remain_mirrors[name] = wait_mirrors[name]
                else:
                    console.out(connected_msg.format(name))
            wait_mirrors = remain_mirrors
        print()

        with open(self.filename, statefile.open_mode) as outfile:
            for mirror in self.mirrors.values():
                mirror.download(begin)
                parts_in_progress.append(begin)
                begin += self.block_size

            while file_size == 0 or written_bytes < file_size:
                part = self.data_queue.get()

                try:
                    assert part.status != 0, connection_error.format(part.name)
                    assert part.status != 200, no_partial_error.format(part.name)
                    assert part.status == 206, http_error.format(part.status)

                    if file_size == 0:
                        file_size = part.file_size
                        progress.total = file_size
                        outfile.seek(part.file_size - 1, 0)
                        outfile.write(b'\x00')
                        console.out(downloading_msg.format(self.filename, part.file_size, calc_units(part.file_size)))

                    assert file_size == part.file_size, filesize_error.format(part.name, part.file_size, file_size)

                    outfile.seek(part.begin, 0)
                    size = outfile.write(part.data)
                    written_bytes += size

                    parts_in_progress.remove(part.begin)

                    mirror = self.mirrors[part.name]
                    mirror.thread.join()

                    speed = size / mirror.thread.time
                    speeds[part.name] = speed
                    console.progress(written_bytes, sum(speeds.values()))

                    if len(failed_parts) > 0:
                        new_part = failed_parts.popleft()
                        parts_in_progress.append(new_part)
                        mirror.download(new_part)
                    elif begin < file_size:
                        parts_in_progress.append(begin)
                        mirror.download(begin)
                        begin += self.block_size

                except AssertionError as e:
                    console.out(str(e))
                    failed_parts.append(part.begin)
                    self.mirrors[part.name].thread.join()
                    self.mirrors[part.name].close()
                    del self.mirrors[part.name]
                    if len(self.mirrors) == 0:
                        return 1
                finally:
                    needle_parts = parts_in_progress.copy()
                    needle_parts.extend(failed_parts)
                    statefile.update(begin, written_bytes, needle_parts)

            for mirror in self.mirrors.values():
                mirror.thread.join()
                mirror.close()
            print()

        
        statefile.delete()
        return 0




if __name__ == '__main__':

    print(start_msg.format(VERSION))

    block_size = 4 * 2**20
    filename = None
    timeout = 10
    urls = []

    if '-b' in sys.argv:
        i = sys.argv.index('-b') + 1
        block_size = sys.argv[i]
        block_size = int(block_size[:-1]) * {'k': 2**10, 'M': 2**20}[block_size[-1:]]

    if '-o' in sys.argv:
        i = sys.argv.index('-o') + 1
        filename = sys.argv[i]

    if '-T' in sys.argv:
        i = sys.argv.index('-T') + 1
        timeout = sys.argv[i]

    if '-f' in sys.argv:
        i = sys.argv.index('-f') + 1
        with open(sys.argv[i], 'r') as links:
            for link in links:
                urls.append(link.strip('\r\n'))

    for arg in sys.argv:
        if arg.startswith('http://'):
            urls.append(arg)

    manager = Manager(urls, block_size, filename, timeout)
    manager.download()
    
