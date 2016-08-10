#!/usr/bin/env python3

import sys, os
from threading import Thread
from http import client
from queue import Queue, Empty
from collections import deque

class Part:

    def __init__(self, thread_name, status, begin, data=None, file_size=None):
        self.thread_name = thread_name
        self.data = data
        self.status = status
        self.begin = begin
        self.file_size = file_size




class DownloadThread(Thread):

    user_agent = 'PyMGet/1.00 ({} {}, {})'.format(os.uname().sysname, os.uname().machine, os.uname().release)

    def __init__(self, url, block_size, timeout):
        Thread.__init__(self)
        self.name = url
        self.block_size = block_size
        self.timeout = timeout
        lst = url.split('/', 3)
        assert lst[0] == 'http:', 'Wrong URL. It is not HTTP protocol.'
        self.host = lst[2]
        self.request = '/' + lst[3]

    def start_download(self, position):
        self.position = position
        self.start()

    def run(self):
        headers = {'User-Agent': self.user_agent, 'Range': 'bytes={}-{}'.format(self.position, self.position + self.block_size - 1)}
        conn = client.HTTPConnection(self.host, timeout=self.timeout)
        conn.request('GET', self.request, headers=headers)
        response = conn.getresponse()

        if response.status == 206:
            file_size = int(response.getheader('Content-Range').split('/')[-1])
            data = response.read()
            part = Part(self.name, response.status, self.position, data, file_size)
        else:
            part = Part(self.name, response.status, self.position)

        Manager.data_queue.put(part)
        




class Manager:

    data_queue = Queue()

    def __init__(self, urls, block_size, filename, timeout):
        if filename is None:
            self.filename = urls[0].split('/')[-1]
            if self.filename == '':
                self.filename = 'out'
        else:
            self.filename = filename

        self.block_size = block_size

        self.timeout = timeout

        self.threads = {}
        for url in urls:
            try:
                self.threads[url] = DownloadThread(url, self.block_size, timeout)
            except AssertionError as e:
                print(str(e))


    def download(self):
        position = 0
        file_size = 0
        written_bytes = 0
        failed_parts = deque([])
        with open(self.filename, 'wb') as outfile:
            for thread in self.threads.values():
                thread.start_download(position)
                position += self.block_size

            while file_size == 0 or written_bytes < file_size:
                part = self.data_queue.get()

                try:
                    assert part.status != 200, 'Server does not support partial download.'
                    assert part.status == 206, 'Error {}'.format(part.status)
                    if file_size == 0:
                        file_size = part.file_size
                    assert file_size == part.file_size, 'File size differs from first one.'

                    outfile.seek(part.begin, 0)
                    written_bytes += outfile.write(part.data)

                    self.threads[part.thread_name].join()
                    thread = DownloadThread(part.thread_name, self.block_size, self.timeout)
                    self.threads[part.thread_name] = thread

                    if len(failed_parts) > 0:
                        thread.start_download(failed_parts.popleft())
                    elif position < file_size:
                        thread.start_download(position)
                        position += self.block_size
                except AssertionError as e:
                    print(e)
                    failed_parts.append(part.begin)
                    self.threads[part.thread_name].join()
                    del self.threads[part.thread_name]
                    if len(self.threads) == 0:
                        return 1
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
    
