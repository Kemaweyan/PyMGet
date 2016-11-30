#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os
import queue
from collections import deque
from abc import ABCMeta, abstractmethod

from . import messages
from .errors import FatalError, CancelError
from .utils import calc_size
from .mirrors import Mirror
from .data_queue import DataQueue

class IManager(metaclass=ABCMeta):

    """
    An interface for download manager.

    """
    @abstractmethod
    def prepare(self, console, command_line, outfile): pass

    @abstractmethod
    def download(self): pass

    @abstractmethod
    def del_active_part(self, offset): pass

    @abstractmethod
    def add_failed_part(self, offset): pass

    @abstractmethod
    def delete_mirror(self, name): pass

    @abstractmethod
    def set_file_size(self, task_info): pass

    @abstractmethod
    def redirect(self, task_info): pass

    @abstractmethod
    def do_error(self, task_info): pass

    @abstractmethod
    def set_progress(self, task_info): pass

    @abstractmethod
    def write_data(self, task_info): pass



class Manager(IManager):

    """
    Creates mirror objects from the list of URLs, connects to them,
    gives tasks and process results.    
    
    """
    def __init__(self):

        """
        :console: a console object
        :command_line: a command line object
        :outfile: an outfile object

        """
        self.data_queue = self._dataqueue()
        self.console = None
        self.outfile = None
        self.block_size = 0
        self.timeout = 0
        self.user_path = ''
        self.urls = []
        self.server_filename = '' # filename on the server, now is unknown
        self.file_size = 0 # file size if unknown, is will be determined after connect
        self.mirrors = {} # a dictionary for mirrors, names of hosts would be used as keys
        self.parts_in_progress = [] # a list of active tasksself.context = self.outfile.context # save context related to the file
        self.offset = 0
        self.written_bytes = 0 
        self.old_progress = 0
        self.failed_parts = deque([])

    def prepare(self, console, command_line, outfile):

        """
        Creates mirrors and an output file.
        Loads data from the context related
        to the file.

        """
        self.console = console
        self.outfile = outfile
        self.block_size = command_line.block_size
        self.timeout = command_line.timeout
        self.user_path = command_line.filename
        self.urls = command_line.urls
        for url in self.urls:
            self.create_mirror(url) # try to create a mirror
        if not self.mirrors: # there are no mirrors - error
            raise FatalError(_("There are no mirrors to download."))
        if self.server_filename == '': # can't determine a filename
            self.server_filename = 'out' # use the name 'out'
        self.outfile.create_path(self.server_filename) # create a path to the file
        self.context = self.outfile.context # save context related to the file
        self.offset = self.context.offset # get current offset from the context and continue downloading from that offset
        self.written_bytes = self.context.written_bytes # get the count of written bytes (currect progress) from the context 
        self.old_progress = self.written_bytes # save currect progress (necessary for correct calculation of download speed)
        self.failed_parts = deque(self.context.failed_parts) # load a list of failed parts from the context

    def create_mirror(self, url):

        """
        Creates a mirror and adds that to the list.
        If failed prints an error message.

        :url: the URL object describes the download link, type URL

        """
        mirror = self._mirror.create(url, self.block_size, self.timeout)
        # compare filename on this server with other ones
        if self.check_filename(mirror):
            self.mirrors[url.host] = mirror # add the mirror to the list

    def check_filename(self, mirror):

        """
        Checks filename for equality to other servers.

        :mirror: the mirror object, type Mirror

        """
        if self.server_filename == '': # the filename is not yes known, so it's the first mirror
            if mirror.filename == '': # the mirror can't determine filename
                self.console.warning(_("unable to determine filename on the mirror {}").format(mirror.name))
                # ask a confirmation to use the mirror
                return self.console.ask(_("Use the mirror {} anyway?").format(mirror.name), False)
            self.server_filename = mirror.filename # save filename
            return True # the filename is valid
        if os.path.basename(self.server_filename) == mirror.filename: # filename is the same
            return True # the filename is valid
        # this place we reach only if the filename differs
        self.console.warning(_("filename on the server {} differs with {}. Probably that's another file.").format(mirror.name, self.server_filename))
        # ask a confirmation to use the mirror
        return self.console.ask(_("Use the mirror {} anyway?").format(mirror.name), False)

    def wait_connections(self):

        """
        Waits completing of threads and starts a connection
        or gives a task if necessary. 

        """
        for name, mirror in self.mirrors.items():
            if mirror.wait_connection(): # threads of the mirror are not running
                if mirror.ready: # check the mirror is ready to take a task
                    self.give_task(mirror) # give a task
                elif mirror.need_connect: # check the mirror needs a connection
                    mirror.connect() # start a connection

    def give_task(self, mirror):

        """
        Gives a task to the mirror.

        :mirror: the mirror object, type Mirror

        """
        if self.failed_parts: # there is failed task
            failed_offset = self.failed_parts.popleft() # get the offset of that task
            mirror.download(failed_offset) # start download the part
            self.parts_in_progress.append(failed_offset) # add the offset to the list of active parts
        elif self.offset < self.file_size or self.file_size == 0: # the file is not complete
            mirror.download(self.offset) # start download from current offset
            self.parts_in_progress.append(self.offset) # add the offset to the list of active parts
            self.offset += self.block_size # increase current offset

    def keep_download(self):

        """
        Returns False if downloading completed.
        Otherwise returns True.

        """
        # downloading is complete if file size is known (more than 0)
        # and all the data is written to the output file
        return self.file_size == 0 or self.written_bytes < self.file_size

    def download(self):

        """
        Downloads the file.

        """
        with self.outfile: # open output file
            try:
                while self.keep_download(): # downloading is not complete
                    self.wait_connections() # wait mirrors (connections, giving tasks)
                    while True:
                        try:
                            # check the queue, if it's empty - an exception is raised
                            task_info = self.data_queue.get(False, 0.01)
                            try:
                                # process given result from the mirror
                                task_info.process(self)
                            finally:
                                needle_parts = self.parts_in_progress.copy() # save non-completed parts
                                needle_parts.extend(self.failed_parts) # add failed parts
                                self.context.update(self.offset, self.written_bytes, needle_parts) # save the context
                        except queue.Empty: # if the queue is empty
                            # it meats that there is nothing to do
                            # and we need to wait mirrors or give a new task
                            break # quit the loop (go to waiting mirrors)
            except KeyboardInterrupt: # user interrupted process
                # cancel all active threads
                for mirror in self.mirrors.values():
                    mirror.cancel()
                raise CancelError(_("Operation has been cancelled by user."))
            finally:
                # loop for shut down the program
                for mirror in self.mirrors.values():
                    mirror.join() # wait threads
                    mirror.close() # close connection
                self.console.message() # print empty string to console
        self.context.delete() # remove the context file

    def del_active_part(self, offset):

        """
        Deletes an active task from the list.

        :offset: an offset of the part, type int

        """
        self.parts_in_progress.remove(offset)

    def add_failed_part(self, offset):

        """
        Adds failed task in the list.

        :offset: an offset of the part, type int

        """
        self.del_active_part(offset) # failed task is inactive
        self.failed_parts.append(offset)

    def delete_mirror(self, name):

        """
        Deleten a mirror.

        :name: a name of the mirror, type str

        """
        mirror = self.mirrors[name]
        mirror.join()
        del self.mirrors[name]

    def set_file_size(self, name, file_size):

        """
        Set the size of the file at first call and allocate
        a space on HDD. At other calls compares the size
        with sizes on other mirrors.

        :name: a name of the mirror that sent a TaskInfo object, type str
        :file_size: a size of the file received from the mirror, type int

        """
        if self.file_size == 0: # first call (the filesize is not yet known)
            self.file_size = file_size
            self.console.create_progressbar(self.file_size, self.old_progress)
            self.outfile.seek(self.file_size - 1) # seek to last byte
            self.outfile.write(b'\x00') # write zero
            downloading_msg = _("\nDownloading file {} {} bytes ({}):\n").format(self.outfile.filename, self.file_size, calc_size(self.file_size))
            self.console.message(downloading_msg)
        elif self.file_size != file_size: # call is not the first and the size differs
            # the file is broken or it's another file
            self.console.error(_("size of the file on the server {} {} bytes differs with received before {} bytes.").format(name, file_size, self.file_size))
            self.delete_mirror(name) # delete the mirror
            return
        mirror = self.mirrors[name]
        mirror.file_size = file_size # save the filename in the mirror
        mirror.ready = True # mark the mirror as ready to download a part
        mirror.connect_message(self.console) # print connection message

    def redirect(self, name, location):

        """
        Removes the mirror and creates a new one
        with new addres from redirect info.

        :name: a name of the mirror that sent a TaskInfo object, type str
        :location: a new location of the file for redirect, type networking.URL

        """
        self.delete_mirror(name)
        self.create_mirror(location)
        self.console.message(_("Redirect from mirror {} to address {}:").format(name, location.url))

    def do_error(self, name, status):

        """
        Executes if an error has occurred.

        :name: a name of the mirror that sent a TaskInfo object, type str
        :status: a status code of the error, type int

        """
        if status == 0: # connection error
            self.console.error(_("unable to connect to the server {}").format(name))
        elif status == 200: # the mirror does not support partial downlaod
            self.console.error(_("server {} does not support partial downloading.").fotmat(tname))
        else: # another error (probably HTTP 4xx/5xx)
            self.console.error(_("wrong server response. Code {}").format(status))
        self.delete_mirror(name) # delete the mirror
        if not self.mirrors: # if no mirror remains
            # downloading impossible, quit program
            raise FatalError(_("unable to download the file."))

    def set_progress(self, name, task_progress):

        """
        Updates the progress of downloading.

        :name: a name of the mirror that sent a TaskInfo object, type str
        :task_progress: a progress of current task given to the mirror, type int

        """
        # update the progress of the mirror
        mirror = self.mirrors[name]
        mirror.task_progress = task_progress
        # progress is written data + current progress of
        # active tasks
        progress = self.written_bytes + sum(map(lambda m: m.task_progress, self.mirrors.values()))
        # update the progress in the console, to calculate download speed
        # pass the progress of current session
        self.console.progress(progress)

    def write_data(self, name, offset, data):

        """
        Writes data to the file, release the mirror.

        :name: a name of the mirror that sent a TaskInfo object, type str
        :offset: an offset of data part gotten from the mirror, type int
        :data: data of the task given to the mirror, type bytes

        """
        self.del_active_part(offset) # the task becomes inactive
        self.outfile.seek(offset) # seek to offset of the task
        self.outfile.write(data) # write data
        self.written_bytes += len(data) # increase the written bytes count
        mirror = self.mirrors[name]
        mirror.done() # mark the mirror as completed downloading

    @property
    def _dataqueue(self):
        return DataQueue

    @property
    def _mirror(self):
        return Mirror
