#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import platform
import threading
from http import client
import ftplib
from abc import ABCMeta, abstractmethod, abstractproperty

from . import __version__
from .task_info import *
from .data_queue import DataQueue

VERSION = '1.40'

class URL:

    """
    Parses url string. Supported protocols: HTTP/HTTPS/FTP

    """
    url_re = re.compile('^(https?|ftp)://([\w\.-]+(?::\d+)?)((?:/(.+?))?/([^\/]+)?)?$', re.I)

    def __init__(self, url):

        """
        :url: url string, type str

        """
        self.url = url
        # regular expression validates url and splits it on following parts:
        # protocol (1), host with port if present (2), path to the file (4), filename (5)
        # path + filename also are united to request (3)
        matches = self.url_re.match(url)
        self.protocol = matches.group(1).lower() # http, https or ftp
        self.host = matches.group(2) # hostname or ip address in format host or host:port
        self.request = matches.group(3) if matches.group(3) else '/' # the request beginning with /
        self.path = matches.group(4) if matches.group(4) else '' # path to the file without beginning /
        self.filename = matches.group(5) if matches.group(5) else '' # filename




class INetworkThread(metaclass=ABCMeta):

    """
    An interface for network threads.

    """
    @abstractmethod
    def start(self): pass

    @abstractmethod
    def join(self): pass

    @abstractmethod
    def cancel(self): pass



class NetworkThread(threading.Thread, INetworkThread):

    """
    Abstract base class for network threads.

    """
    # user_agent string for HTTP(S) servers
    user_agent = 'PyMGet/{} ({} {}, {})'.format(__version__, platform.uname().system, platform.uname().machine, platform.uname().release)

    def __init__(self):
        threading.Thread.__init__(self)
        self.data_queue = self._dataqueue()
        self.ready = threading.Event() # a flag that the thread is completed
        self.cancelled = threading.Event() # a flag that the thread has been cancelled

    def cancel(self):

        """
        Sets the cancel flag.
        The thread will be terminated when
        it checks this flag and that is setted.

        """
        self.cancelled.set()

    @property
    def _dataqueue(self):
        return DataQueue

    @abstractmethod
    def run(self): pass # runs in separate thread, should be implemented in inherited classes




# Connection threads classes

class ConnectionThread(NetworkThread):

    """
    Abstract base class for connection threads.

    """
    def __init__(self, url, timeout):

        """
        :url: the URL object describes the download link, type URL
        :timeout: timeout in seconds, type int

        """
        NetworkThread.__init__(self)
        self.url = url
        self.timeout = timeout
        self.conn = None

    def run(self):
        """
        Runs in separate thread, calls an abstract method connect.
        Puts a TaskInfo object in the queue.

        """
        try:
            # connect method implementation should return a TaskInfo object
            info = self.connect()
        except:
            # if an error has occurred create a TaskHeadError object
            info = TaskHeadError(self.url.host, 0)
        finally:
            self.data_queue.put(info) # put the result in the queue
            self.ready.set() # and mark the thread as completed

    @abstractmethod
    def connect(self): pass # make connection, should be implemented in subclasses. Should return a TaskInfo object

    # abstract property, subclasses should implement it and return class for connection
    @abstractproperty
    def protocol(self): pass

class HTTXThread(ConnectionThread):

    """
    Base class for HTTP and HTTPS protocols.

    """
    def redirect(self, location, status):
        
        """
        Reates a TaskRedirect object to redirect mirror.

        :location: a new URL from redirect header, type str
        :status: a response status, type int

        """
        url = ''
        # location string could contain either an abolute path or a relative one.
        # Also relative address could begin with /, i.e. from the root directory
        # on the same server, or be related to current path.
        # Therefore we split location for 3 parts:
        # 1) a host with a protocol http(s)://site.com
        # 2) the rest of the link (including first / if it presents)
        # 3) beginning / if it presents (as a flag)
        redirect_re = re.compile('^(https?://[^/]+)?((/)?(?:.*))$', re.I)
        matches = redirect_re.match(location)
        if matches.group(1): # if there is a host in the location
            url = location # the path is absolute, redirect there
        elif matches.group(3): # there is beginning /
            # the path is related to the root directory of the same server
            # add a path to the host
            url = '{}://{}{}'.format(self.url.protocol, self.url.host, matches.group(2))
        else: # the path is related to current directory on the server
            # get current path from the request
            path = self.url.request.rsplit('/', 1)[0] + '/'
            # add a new path to current path with the host
            url = '{}://{}{}'.format(self.url.protocol, self.url.host, path + matches.group(2))
        return TaskRedirect(self.url.host, status, URL(url))

    def connect(self):
        
        """
        Make a connectio nto the server.
        Subclasses should implemet a property 'protocol',
        returning client.HTTPConnection or client.HTTPSConnection

        """
        # sends User-Agent and Refferer (main page on the server) in the header, 
        # it's necessary when the server blocks downloading via links from other resources
        headers = {'User-Agent': self.user_agent, 'Refferer': '{}://{}/'.format(self.url.protocol, self.url.host)}
        self.conn = self.protocol(self.url.host, timeout=self.timeout)
        self.conn.request('HEAD', self.url.request, headers=headers)
        response = self.conn.getresponse()

        # status 3xx
        if response.status // 100 == 3:
            location = response.getheader('Location')
            return self.redirect(location, response.status)

        if response.status != 200: # HTTP(S) error
            return TaskHeadError(self.url.host, response.status)

        file_size = int(response.getheader('Content-Length'))
        info = TaskHeadData(self.url.host, response.status, file_size)
        response.close()
        return info

class HTTPThread(HTTXThread):

    """
    HTTP cponnection thread class.
    Implements property 'protocol' as client.HTTPConnection

    """
    @property
    def protocol(self):
        return client.HTTPConnection

class HTTPSThread(HTTXThread):

    """
    HTTPS cponnection thread class.
    Implements property 'protocol' as client.HTTPSConnection

    """
    @property
    def protocol(self):
        return client.HTTPSConnection

class FTPThread(ConnectionThread):

    """
    FTP connection thread class.

    """
    def connect(self):
        """
        Makes an anonymous connection to FTP server, changes current
        directory to directory with requested file and gets its size.

        """
        self.conn = self.protocol(self.url.host, 'anonymous', '', timeout=self.timeout)
        self.conn.voidcmd('TYPE I')
        self.conn.cwd(self.url.path)
        self.conn.voidcmd('PASV')
        file_size = self.conn.size(self.url.filename)
        return TaskHeadData(self.url.host, 200, file_size) # set the code 200 for compatibility with HTTP

    @property
    def protocol(self):
        return ftplib.FTP




# Download threads classes

class DownloadThread(NetworkThread):

    """
    Abstract base class for download threads.

    """
    FRAGMENT_SIZE = 32 * 2**10 # the size of fragments that will be sent to the main thread, equals 32kB

    def __init__(self, url, conn, offset, block_size):

        """
        :url: the URL object describes the download link, type URL
        :conn: the connection object, type client.HTTPConnection, client.HTTPSConnection or ftplib.FTP
        :offset: the offset of the part to download, type int
        :block_size: block size, type int

        """
        NetworkThread.__init__(self)
        self.url = url
        self.conn = conn
        self.offset = offset
        self.block_size = block_size

class HTTXDownloadThread(DownloadThread):

    """
    HTTP/HTTPS downlaod thread class.
    There is no difference in behavior
    of HTTP and HTTPS after connection.

    """
    def run(self):
        """
        Downloads the file, runs in separate thread.

        """
        # sends download range from offset to offset + block_size - 1 (including) in the header
        headers = {'User-Agent': self.user_agent, 'Refferer': '{}://{}/'.format(self.url.protocol, self.url.host), 
                    'Range': 'bytes={}-{}'.format(self.offset, self.offset + self.block_size - 1)}
        status = 0 # set status to 0 that means a connection error
        try:
            self.conn.request('GET', self.url.request, headers=headers)
            response = self.conn.getresponse()
            # the server does not support partial downloading - error
            if response.status != 206:
                status = response.status
                raise MirrorError
            part_size = int(response.getheader('Content-Length')) # actual count of bytes sent by the server
            data = b'' # data buffer
            # loop while all data will be received
            while part_size > len(data):
                if self.cancelled.is_set(): # if the thread has been cancelled
                    # stop the thread, the TaskError would not be processed
                    # because a loop in the main thread already broken
                    raise Exception
                data_fragment = response.read(self.FRAGMENT_SIZE)
                data += data_fragment # add data to the buffer
                # put progress information into the queue
                info = TaskProgress(self.url.host, response.status, len(data))
                self.data_queue.put(info)
            # when the downloading loop finished, create TaskData object
            info = TaskData(self.url.host, response.status, self.offset, data)
            response.close()
        except:
            # if an error has occurred - create a TaskError object
            info = TaskError(self.url.host, status, self.offset)
        finally:
            self.data_queue.put(info) # put result TaskInfo object into the queue
            self.ready.set() # mark the thread as comleted

class FTPDownloadThread(DownloadThread):

    """
    FTP download thread class.

    """
    def __init__(self, url, conn, offset, block_size, file_size):

        """
        :url: the URL object describes the download link, type URL
        :conn: the connection object, type ftplib.FTP
        :offset: the offset of the part to download, type int
        :block_size: block size, type int
        :file_size: filesize gotten from connection thread, type int

        """
        DownloadThread.__init__(self, url, conn, offset, block_size)
        self.file_size = file_size

    def run(self):

        """
        Downloads the file, runs in separate thread.

        """
        data = b'' # data buffer
        try:
            sock = self.conn.transfercmd('RETR ' + self.url.filename, self.offset)
            # loop while received data size is less than block size
            # however the last block could be lesser than that size
            while len(data) < self.block_size:
                if self.cancelled.is_set(): # if the thread has been cancelled
                    # stop the thread, the TaskError would not be processed
                    # because a loop in the main thread already broken
                    raise Exception
                # get data, but not more than fragment size
                # and the size remaining to full block
                data_fragment = sock.recv(min(self.block_size - len(data), self.FRAGMENT_SIZE))
                if not data_fragment: # if there is no data - error
                    raise MirrorError
                data += data_fragment # add data to the buffer
                info = TaskProgress(self.url.host, 206, len(data))
                self.data_queue.put(info)
                # if reached the end of the file - exit loop
                if self.file_size - self.offset - len(data) <= 0:
                    break
            # when the downloading loop finished, create TaskData object
            info = TaskData(self.url.host, 206, self.offset, data)
            sock.close()
        except:
            # if an error has occurred - create a TaskError object
            info = TaskError(self.url.host, 0, self.offset)
        finally:
            self.conn.close()
            self.data_queue.put(info) # put result TaskInfo object into the queue
            self.ready.set() # mark the thread as comleted
