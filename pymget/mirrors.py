#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractproperty, abstractmethod

from . import messages
from .networking import *

class IMirror(metaclass=ABCMeta):

    """
    An interface for Mirrors.

    """
    @abstractmethod
    def connect(self): pass

    @abstractmethod
    def download(self, offset): pass

    @abstractmethod
    def wait_connection(self): pass

    @abstractmethod
    def cancel(self): pass

    @abstractmethod
    def join(self): pass

    @abstractmethod
    def done(self): pass

    @abstractmethod
    def connect_message(self, console): pass

    @abstractmethod
    def close(self): pass



class Mirror(IMirror):

    """
    Abstract base class for mirrors

    """
    @staticmethod
    def create(url, block_size, timeout):

        """
        Static factory method creating an object of the mirror
        depending on the protocol in URL.

        :url: the URL object describes the download link, type URL
        :block_size: block size, type int
        :timeout: timeout in seconds, type int

        """
        if url.protocol == 'http':
            return HTTPMirror(url, block_size, timeout)
        if url.protocol == 'https':
            return HTTPSMirror(url, block_size, timeout)
        if url.protocol == 'ftp':
            return FTPMirror(url, block_size, timeout)

    def __init__(self, url, block_size, timeout):

        """
        :url: the URL object describes the download link, type URL
        :block_size: block size, type int
        :timeout: timeout in seconds, type int

        """
        self.url = url
        self.block_size = block_size
        self.timeout = timeout
        self.file_size = 0 # the file size will be determined after connect
        self.task_progress = 0 # the progress of current task
        self.conn = None # the connection object
        self.need_connect = True # the flag of a need to connect
        self.ready = False # the flag of a rediness to download a part
        self.conn_thread = None # connection thread object
        self.dnl_thread = None # download thread object

    def connect(self):

        """
        Starts connection thread to connect to the server.

        """
        self.ready = False # the mirror is not ready 
        self.need_connect = False # the mirror does not need a connection
        # create a connection thread
        # property connetion_thread should be implemented in subclasses
        self.conn_thread = self.connection_thread(self.url, self.timeout)
        self.conn_thread.start()

    def wait_connection(self):

        """
        Waits completion of threads.

        :return: True if there is no running threads, False - running thread is present

        """
        if self.conn_thread: # connection thread has been created
            # check completeness (timeout 1 ms)
            # method wait returns True when the thread sets internal flag
            # but it does not mean that the thread really terminated
            if not self.conn_thread.ready.wait(0.001):
                return False
            self.conn_thread.join() # wait for real termination of the thread
            self.conn = self.conn_thread.conn # save the connection object
            self.conn_thread = None # delete the connection thread object
        if self.dnl_thread: # download thread has been created
            # check completeness (timeout 1 ms)
            # method wait returns True when the thread sets internal flag
            # but it does not mean that the thread really terminated
            if not self.dnl_thread.ready.wait(0.001):
                return False
            self.dnl_thread.join() # wait for real termination of the thread
            self.dnl_thread = None # delete the download thread object
        return True

    def download(self, offset):

        """
        Starts downlaod thread that downloads the next part.

        :offset: the offset of the part, type int

        """
        self.ready = False # the mirror does not ready to get a task
        # create download thread
        # property download_thread should be implemented in subclasses
        self.dnl_thread = self.download_thread(self.url, self.conn, offset, self.block_size)
        self.dnl_thread.start()

    def cancel(self):

        """
        Canceles operations of the mirror.
        It sets a cancel flag in running threads. 

        """
        if self.conn_thread:
            self.conn_thread.cancel()
        if self.dnl_thread:
            self.dnl_thread.cancel()

    def done(self):

        """
        Marks the mirror as completed downloading.

        """
        self.task_progress = 0 # task is done, clear progress
        self.ready = True # the mirror is ready to get the next task

    def connect_message(self, console):

        """
        Prints connection message.

        """
        console.message(_("Connecting to {} OK").format(self.url.host))

    def join(self):

        """
        Waits for terminating of existing threads.

        """
        if self.conn_thread:
            self.conn_thread.join()
        if self.dnl_thread:
            self.dnl_thread.join()

    def close(self):

        """
        Closes connection if it exists.

        """
        try:
            self.conn.close()
        except:
            pass

    @property
    def name(self):

        """
        The name of the mirror.

        """
        return self.url.host

    @property
    def filename(self):

        """
        The filename on the server.

        """
        return self.url.filename

    @abstractproperty
    def connection_thread(self): pass # abstract property, should return a classname of connection object

    @abstractproperty
    def download_thread(self): pass # abstract property, should return a classname of download object

class HTTXMirror(Mirror):

    """
    Abstract base class for HTTP and HTTPs mirrors.

    """
    @property
    def download_thread(self):

        """
        Returns download thread class, it's common for HTTP and HTTPS.

        """
        return HTTXDownloadThread

class HTTPMirror(HTTXMirror):

    """
    HTTP mirror.

    """
    @property
    def connection_thread(self):

        """
        Returns connection thread class.

        """
        return HTTPThread

class HTTPSMirror(HTTXMirror):

    """
    HTTPS mirror.

    """
    @property
    def connection_thread(self):

        """
        Returns connection thread class.

        """
        return HTTPSThread

class FTPMirror(Mirror):

    """
    FTP mirror.

    """
    def __init__(self, url, block_size, timeout):

        """
        :url: the URL object describes the download link, type URL
        :block_size: block size, type int
        :timeout: timeout in seconds, type int

        """
        Mirror.__init__(self, url, block_size, timeout)
        # FTP mirror re-connects every time when get a new task,
        # there is a flag indicates that a connection message already shown
        self.connected = False

    def done(self):

        """
        Marks the mirror as completed downloading.

        """
        Mirror.done(self)
        self.ready = False # FTP mirror is not ready to get the next task
        # without reconnect
        self.need_connect = True # it needs a new connection

    @property
    def connection_thread(self):

        """
        Returns connection thread class.

        """
        return FTPThread

    @property
    def download_thread(self):

        """
        Returns downloading thread class.

        """
        return FTPDownloadThread

    def download(self, offset):

        """
        Starts downlaod thread that downloads the next part.

        :offset: the offset of the part, type int

        """
        self.ready = False # the mirror is not ready to get the next task
        # create download thread
        # but FTP downlaod thread also needs file_size argument
        self.dnl_thread = self.download_thread(self.url, self.conn, offset, self.block_size, self.file_size)
        self.dnl_thread.start()

    def connect_message(self, console):

        """
        Prints connection message.

        """
        if self.connected: # if it's alredy shown - do nothing
            return
        self.connected = True # set the flag that the message already shown
        Mirror.connect_message(self, console) # show the message
