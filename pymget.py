#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os
import threading, queue
from http import client
from collections import deque
import time

VERSION = '1.02'

def calc_speed(size):
    if size >= 2**30:
        return '{:.2f}GiB/s'.format(size / 2**30)
    if size >= 2**20:
        return '{:.2f}MiB/s'.format(size / 2**20)
    if size >= 2**10:
        return '{:.2f}KiB/s'.format(size / 2**10)
    return '{}B/s'.format(size)

class ProgressBar:

    WIDTH = 58

    def __init__(self):
        self.total = 0
        self.update()

    def update(self, complete=0, speed=0):
        if self.total != 0:
            progress = round(self.WIDTH * complete / self.total)
            speed_str = calc_speed(speed)
        else:
            progress = 0
            speed_str = ''

        progress_str = '[{}]'.format(('#'*progress).ljust(self.WIDTH, '-'))
        percent_str = '{:.2%}'.format(progress / self.WIDTH)
        bar = '{0} {1} {2}\r'.format(progress_str, percent_str.rjust(7), speed_str.rjust(11))

        sys.stdout.write(bar)
        sys.stdout.flush()





class Part:

    def __init__(self, name, status, begin, data=None, file_size=None):
        self.name = name
        self.data = data
        self.status = status
        self.begin = begin
        self.file_size = file_size




class ConnectionThread(threading.Thread):

    def __init__(self, host, timeout):
        threading.Thread.__init__(self)
        self.timeout = timeout
        self.host = host
        self.ready = threading.Event()

    def run(self):
        self.conn = client.HTTPConnection(self.host, timeout=self.timeout)
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
        try:
            self.conn.request('GET', self.request, headers=headers)
            response = self.conn.getresponse()
            if response.status != 206:
                raise client.HTTPException
            file_size = int(response.getheader('Content-Range').split('/')[-1])
            data = response.read()
            part = Part(self.name, response.status, self.begin, data, file_size)
            response.close()
        except:
            part = Part(self.name, 0, self.begin)
        finally:
            self.time = time.time() - self.starttime
            Manager.data_queue.put(part)




class Mirror:

    def __init__(self, url, block_size, timeout):
        self.url = url
        self.block_size = block_size
        self.timeout = timeout
        url_parts = self.url.split('/', 3)
        self.host = url_parts[2]
        self.request = '/' + url_parts[3]
        self.thread = ConnectionThread(self.host, self.timeout)
        self.thread.start()

    def wait_connection(self):
        if not self.thread.ready.wait(0.1):
            return False
        self.thread.join()
        self.conn = self.thread.conn
        return True

    def download(self, begin):
        self.thread = DownloadThread(self.url, self.conn, self.request, begin, self.block_size)
        self.thread.start()

    def close(self):
        self.conn.close()



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
            self.mirrors[url] = Mirror(url, self.block_size, timeout)

    def download(self):
        begin = 0
        file_size = 0
        written_bytes = 0
        failed_parts = deque([])
        wait_mirrors = self.mirrors.copy()
        speeds = {}

        while len(wait_mirrors) > 0:
            remain_mirrors = {}
            for name, mirror in wait_mirrors.items():
                if not mirror.wait_connection():
                    remain_mirrors[name] = wait_mirrors[name]
            wait_mirrors = remain_mirrors

        with open(self.filename, 'wb') as outfile:
            for mirror in self.mirrors.values():
                mirror.download(begin)
                begin += self.block_size

            progress = ProgressBar()

            while file_size == 0 or written_bytes < file_size:
                part = self.data_queue.get()

                try:
                    assert part.status != 200, 'Сервер не поддерживает скачивание по частям.'
                    assert part.status == 206, 'Неверный ответ сервера. Код {}'.format(part.status)
                    if file_size == 0:
                        file_size = part.file_size
                        progress.total = file_size
                    assert file_size == part.file_size, 'Размер файла отличается.'

                    outfile.seek(part.begin, 0)
                    size = outfile.write(part.data)
                    written_bytes += size

                    mirror = self.mirrors[part.name]
                    mirror.thread.join()

                    speed = size / mirror.thread.time
                    speeds[part.name] = speed
                    progress.update(written_bytes, sum(speeds.values()))

                    if len(failed_parts) > 0:
                        mirror.download(failed_parts.popleft())
                    elif begin < file_size:
                        mirror.download(begin)
                        begin += self.block_size
                except AssertionError as e:
                    print(e)
                    failed_parts.append(part.begin)
                    self.mirrors[part.name].thread.join()
                    self.mirrors[part.name].close()
                    del self.mirrors[part.name]
                    if len(self.mirrors) == 0:
                        return 1

            for mirror in self.mirrors.values():
                mirror.thread.join()
                mirror.close()
            print()

        return 0




if __name__ == '__main__':

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
    
