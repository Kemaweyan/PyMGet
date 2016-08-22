#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import struct

from pymget.console import *
from pymget.messages import Messages
from pymget.errors import FileError, CancelError

# Output file class

class OutputFile:

    """
    Output file class. Writes data to the file.
    Supports the context manager ('with' statement).

    Methods:

    seek: moves internal pointer to specified offset
    write: writes data to the file

    """
    def __init__(self, filename, path):

        """
        :filename: filename on the server, type str
        :path: path for file saving specified by user, type str

        """
        self.lang = Messages()
        self.console = Console()
        if not path: # user has not specified the path
            self.filename = filename # use filename from the server
            self.path = '' # path is empty (write into current directory)
            self.fullpath = filename # use just filename as a fullpath
        elif os.path.isdir(path): # user specified the path to a folder
            self.filename = filename # use filename from the server
            self.path = path # use specified path
            # fullpath is a combination of path and filename
            self.fullpath = path.rstrip(os.sep) + os.sep + filename
        else: # the specified path is not a folder
            self.filename = os.path.basename(path) # extract filename from the path
            self.path = os.path.dirname(path) # extract path to directory too 
            self.fullpath = path # use specified by user path as fullpath
            self.check_folders() # check all folders in the path for existence
        self.context = Context(self.fullpath) # create context related to the file
        self.file = self.open_file() # open the file (get mode from the context)

    def check_folders(self):
        
        """
        Check existence of all directories in the path.
        If directory does not exist - requests 
        a confirmation to create it.

        """
        if os.path.isdir(self.path): # the directory exists
            return # do nothing
        folders = self.path.split(os.sep) # split the path to components
        for i in range(len(folders)):
            # for each folders in the path
            path = os.sep.join(folders[:i + 1])
            if not path: # if the path is empty
                # it hapens in UNIX-like systems when
                # the absolute path is specified (with first /)
                # in this case the first component after splitting
                # would be empty string,
                path = os.sep # so the first folder is /
            if os.path.isdir(path): # folder exists
                continue # skip it
            if os.path.isfile(path): # the path component is a file
                raise FileError(self.lang.error.dir_is_file.format(path)) # wrong path
            # we reach this place only if the folder does not exist
            if not self.console.ask(self.lang.question.create_dir.format(path), True): # ask for creating
                # user denied a request
                raise CancelError(self.lang.message.cancel) # cancel downloading
            try:
                os.mkdir(path) # create a folder
            except:
                # can't create a folder
                raise FileError(self.lang.error.unable_create_dir.format(path, self.lang.error.permission_denied))

    def open_file(self):

        """
        Opens a file for writing or updating.
        Checks an existence of the context (file *.mget): 
        if it does not exist (the context is clean) - creates a new file
        or asks for rewriting existing file.
        if the context exists - opens the file for updating or if
        the file does not exist - asks for creating a new file.

        """
        if self.context.clean: # the context is clean (the first session)
            if os.path.isfile(self.fullpath): # the file exists
                if not self.console.ask(self.lang.question.rewrite_file.format(self.fullpath), False): # ask for rewriting
                    # user answered 'no'
                    raise CancelError(self.lang.message.cancel) # cancelling download
            # the file does not exist or user answered 'yes'
            try:
                return open(self.fullpath, 'wb') # open the file for writing (if it exists all data will be lost)
            except:
                # can't create the file
                raise FileError(self.lang.error.unable_create_file.format(self.fullpath, self.lang.error.permission_denied))
        else: # the context is not clean (it's not a first session)
            try:
                return open(self.fullpath, 'rb+') # open file for updating
            except:
                # if open failed
                if os.path.isfile(self.fullpath): # file exists
                    # permission denied
                    raise FileError(self.lang.error.unable_open_file.format(self.fullpath, self.lang.error.permission_denied))
                # file does not exist
                if not self.console.ask(self.lang.question.create_file.format(self.fullpath), True): # ask for creating
                    # the user's answer is 'no'
                    raise CancelError(self.lang.message.cancel) # cancelling download
                # the answer is 'yes'
                self.context.reset() # reset the context
                return self.open_file() # retry open the file without context

    def __enter__(self):

        """
        Called by context manager when enter.
        Returns a link to self, inside 'with' statement
        methods 'seek' and 'write' are available.

        """
        return self 

    def __exit__(self, exception_type, exception_value, traceback):

        """
        Called by context manager when exit.
        Closes the file if it has been opened.

        """
        try:
            self.file.close()
        except:
            return False # exception has not been catched

    def seek(self, offset):

        """
        Moves internal pointer to offset. 

        :offset: new position in the file, type int

        """
        try:
            self.file.seek(offset, 0) # move a pointer to 'offset' bytes from the begiing of the file (second argument 0)
        except:
            # if it failed - writing error
            raise FileError(self.lang.error.unable_write.format(self.filename))

    def write(self, data):

        """
        Writes data into the file. 

        :data: data to write, type bytes

        """
        try:
            return self.file.write(data) # write into the file
        except:
            # it it faised - writing error
            raise FileError(self.lang.error.unable_write.format(self.filename))



# Context class

class Context:

    """
    Saves in the special file information about process
    of downloading and loads this information after restart.
    It helps resume downloading after error.

    File format:

    Header:
        current offset, type int
        written bytes count, type int
        failed parts count, type int
    Body:
        a list of offsets of failed parts, type int

    """
    def __init__(self, filename):

        """
        :filename: the fill name of file to downlaod, type str

        """
        self.filename = filename + '.pymget' # the name of context file
        self.failed_parts = [] # parts still need to download
        self.offset = 0 # current offset
        self.written_bytes = 0 # written bytes count
        try:
            with open(self.filename, 'rb') as f: # open the context file
                data = f.read(struct.calcsize('NNq')) # read the header
                # and unpack it
                self.offset, self.written_bytes, failed_parts_len = struct.unpack('NNq', data)
                # if there are failed parts
                if failed_parts_len > 0:
                    data = f.read(struct.calcsize('N' * failed_parts_len)) # read failed parts
                    # and unpack them
                    self.failed_parts = struct.unpack('N' * failed_parts_len, data)
        except: # open file failed or wrong file format
            self.clean = True # consider that context does not exist (it's a first session)
        else: # there are no errors
            self.clean = False # context exists (resume downloading)

    def modified(self, offset, written_bytes, failed_parts):

        """
        Check changes in downloading state.

        :offset: current offset, type int
        :written_bytes: written bytes count, type int
        :failed_parts: offsets of failed parts, type sequence <int>

        """
        # return True if anything differs from the current context
        return self.offset != offset or self.written_bytes != written_bytes or set(self.failed_parts) ^ set(failed_parts)

    def update(self, offset, written_bytes, failed_parts):

        """
        Updates the context.

        :offset: current offset, type int
        :written_bytes: written bytes count, type int
        :failed_parts: offsets of failed parts, type sequence <int>

        """
        # if nothing changed
        if not self.modified(offset, written_bytes, failed_parts):
            # do nothing
            return
        # if something changed - assign new values
        self.offset = offset
        self.written_bytes = written_bytes
        self.failed_parts = failed_parts
        failed_parts_len = len(self.failed_parts)
        pattern = 'NNq' + 'N' * failed_parts_len # create a pattern depending on failed parts count
        # pack data
        data = struct.pack(pattern, self.offset, self.written_bytes, failed_parts_len, *self.failed_parts)
        # save data to the context file
        with open(self.filename, 'wb') as f:
            f.write(data)

    def reset(self):

        """
        Resets the context.

        """
        self.update(0, 0, [])
        self.clean = True

    def delete(self):

        """
        Deletes the context file.

        """
        try:
            os.remove(self.filename)
        except:
            pass # just ignore erros, probably file does not exist
