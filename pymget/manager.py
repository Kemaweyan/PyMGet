#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os, queue
from collections import deque

from pymget.messages import Messages
from pymget.errors import FatalError, URLError, FileSizeError
from pymget.console import Console
from pymget.outfile import OutputFile
from pymget.utils import calc_units
from pymget.mirrors import Mirror
from pymget.data_queue import DataQueue

class Manager:

    """
    Creates mirror objects from the list of URLs, connects to them,
    gives tasks and process results.    
    
    """
    def __init__(self, urls, block_size, filename, timeout):

        """
        :urls: the list of URLs, type iterable <URL>
        :block_size: block size, type int
        :filename: name of output file specified by user, type str
        :timeout: timeout for server reply, type int

        """
        self.lang = Messages()
        self.console = Console()
        self.data_queue = DataQueue()
        self.block_size = block_size
        self.timeout = timeout
        self.server_filename = '' # filename on the server, now is unknown
        self.mirrors = {} # a dictionary for mirrors, names of hosts would be used as keys
        for url in urls:
            self.create_mirror(url) # try to create a mirror
        if not self.mirrors: # there are no mirrors - error
            raise FatalError(self.lang.error.no_mirrors)
        if self.server_filename == '': # can't determine a filename
            self.server_filename = 'out' # use the name 'out'
        self.outfile = OutputFile(self.server_filename, filename) # create outfile object
        self.context = self.outfile.context # save context related to the file
        self.offset = self.context.offset # get current offset from the context and continue downloading from that offset
        self.written_bytes = self.context.written_bytes # get the count of written bytes (currect progress) from the context 
        self.old_progress = self.written_bytes # save currect progress (necessary for correct calculation of download speed)
        self.failed_parts = deque(self.context.failed_parts) # load a list of failed parts from the context
        self.file_size = 0 # file size if unknown, is will be determined after connect
        self.parts_in_progress = [] # a list of active tasks

    def create_mirror(self, url):

        """
        Creates a mirror and adds that to the list.
        If failed prints an error message.

        :url: the URL object describes the download link, type URL

        """
        try:
            mirror = Mirror.create(url, self.block_size, self.timeout)
            # compare filename on this server with other ones
            if not self.check_filename(mirror):
                raise URLError(mirror.filename) # wrong address
        except URLError as e: # wrong address
            self.console.error(str(e))
        else:
            self.mirrors[url.host] = mirror # add the mirror to the list

    def check_filename(self, mirror):

        """
        Checks filename for equality to other servers.

        :mirror: the mirror object, type Mirror

        """
        if self.server_filename == '': # the filename is not yes known, so it's the first mirror
            if mirror.filename == '': # the mirror can't determine filename
                self.console.warning(self.lang.warning.empty_filename.format(mirror.name))
                # ask a confirmation to use the mirror
                return self.console.ask(self.lang.question.anyway_download.format(mirror.name), False)
            self.server_filename = mirror.filename # save filename
            return True # the filename is valid
        if os.path.basename(self.server_filename) == mirror.filename: # filename is the same
            return True # the filename is valid
        # this place we reach only if the filename differs
        self.console.warning(self.lang.warning.other_filename.format(mirror.name, self.server_filename))
        # ask a confirmation to use the mirror
        return self.console.ask(self.lang.question.anyway_download.format(mirror.name), False)

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

    def download(self):

        """
        Downloads the file.

        """
        with self.outfile: # open output file
            while self.file_size == 0 or self.written_bytes < self.file_size: # downloading is not complete
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
        # loop for shut down the program
        for mirror in self.mirrors.values():
            mirror.join() # wait threads
            mirror.close() # close connection
        self.console.out() # print empty string to console
        self.context.delete() # remove the context file

    def del_active_part(self, offset):

        """
        Deletes an active task from the list.

        :offset: the offset of the part, type int

        """
        self.parts_in_progress.remove(offset)

    def add_failed_parts(self, offset):

        """
        Adds failed task in the list.

        :offset: the offset of the part, type int

        """
        self.del_active_part(offset) # failed task is inactive
        self.failed_parts.append(offset)

    def delete_mirror(self, name):

        """
        Deleten a mirror.

        :name: name of the mirror, type str

        """
        mirror = self.mirrors[name]
        mirror.join()
        del self.mirrors[name]

    def set_file_size(self, task_info):

        """
        Set the size of the file at first call and allocate
        a space on HDD. At other calls compares the size
        with sizes on other mirrors.

        :task_info: the task result from the queue, type TaskHeadData

        """
        if self.file_size == 0: # first call (the filesize is not yet known)
            self.file_size = task_info.file_size
            self.console.progressbar.total = self.file_size
            self.outfile.seek(self.file_size - 1) # seek to last byte
            self.outfile.write(b'\x00') # write zero
            self.console.out('\n' + self.lang.message.downloading.format(self.outfile.filename, self.file_size, calc_units(self.file_size)) + '\n')
        elif self.file_size != task_info.file_size: # call is not the first and the size differs
            raise FileSizeError # the file is broken or it's another file
        mirror = self.mirrors[task_info.name]
        mirror.file_size = task_info.file_size # save the filename in the mirror
        mirror.ready = True # mark the mirror as ready to download a part
        mirror.connect_message() # print connection message

    def redirect(self, task_info):

        """
        Removes the mirror and creates a new one
        with new addres from redirect info.

        :task_info: the task result from the queue, type TaskRedirect

        """
        self.delete_mirror(task_info.name)
        self.create_mirror(task_info.location)
        self.console.out('\n' + self.lang.message.redirect.format(task_info.name, task_info.location.url))

    def do_error(self, task_info):

        """
        Executes if an error has occurred.

        :task_info: the task result from the queue, type TaskError

        """
        if task_info.status == 0: # connection error
            msg = self.lang.error.unable_connect.format(task_info.name)
        elif task_info.status == 200: # the mirror does not support partial downlaod
            msg = self.lang.error.no_partial.format(task_info.name)
        else: # another error (probably HTTP 4xx/5xx)
            msg = self.lang.error.wrong_http_code.format(task_info.status)
        self.console.error(msg)
        self.delete_mirror(task_info.name) # delete the mirror
        if not self.mirrors: # if no mirror remains
            # downloading impossible, quit program
            raise FatalError(self.lang.error.unable_download)

    def set_progress(self, task_info):

        """
        Updates the progress of downloading.

        :task_info: the task result from the queue, type TaskProgress

        """
        # update the progress of the mirror
        mirror = self.mirrors[task_info.name]
        mirror.task_progress = task_info.task_progress
        # progress is written data + current progress of
        # active tasks
        progress = self.written_bytes + sum(map(lambda m: m.task_progress, self.mirrors.values()))
        # update the progress in the console, to calculate download speed
        # pass the progress of current session
        self.console.progress(progress, progress - self.old_progress)

    def write_data(self, task_info):

        """
        Writes data to the file, release the mirror.

        :task_info: the task result from the queue, type TaskData

        """
        self.del_active_part(task_info.offset) # the task becomes inactive
        self.outfile.seek(task_info.offset) # seek to offset of the task
        self.outfile.write(task_info.data) # write data
        self.written_bytes += len(task_info.data) # increase the written bytes count
        mirror = self.mirrors[task_info.name]
        mirror.done() # mark the mirror as completed downloading
