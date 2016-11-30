#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractmethod

class ITaskInfo(metaclass=ABCMeta):

    """
    An interface for task info objects.

    """
    @abstractmethod
    def process(self, manager): pass


class TaskInfo(ITaskInfo):

    """
    Abstract base class for object with a result of task performance.
    Subclasses should implement a method 'process' that performs necessary actions.

    """
    def __init__(self, name, status):

        """
        :name: name of the mirror put the object in the queue, type str
        :status: status of performance, type int

        """
        self.name = name
        self.status = status

class TaskHeadData(TaskInfo):

    """
    Contains information of the file.
    
    """
    def __init__(self, name, status, file_size):

        """
        :name: name of the mirror put the object in the queue, type str
        :status: status of performance, type int
        :file_size: file size, type int

        """
        TaskInfo.__init__(self, name, status)
        self.file_size = file_size

    def process(self, manager):

        """
        Executes when connection to server succed.

        """
        manager.set_file_size(self.name, self.file_size) # tell file size to the Manager

class TaskRedirect(TaskInfo):

    """
    Redirects the mirror.
    
    """
    def __init__(self, name, status, location):

        """
        :name: name of the mirror put the object in the queue, type str
        :status: status of performance, type int
        :location: a link to the new place, type URL

        """
        TaskInfo.__init__(self, name, status)
        self.location = location

    def process(self, manager):

        """
        Executes when server redirects request.

        """
        manager.redirect(self.name, self.location) # do redirect

class TaskProgress(TaskInfo):

    """
    Sets new progress value.
    
    """
    def __init__(self, name, status, task_progress):

        """
        :name: name of the mirror put the object in the queue, type str
        :status: status of performance, type int
        :task_progress: count of bytes received in current task, type int

        """
        TaskInfo.__init__(self, name, status)
        self.task_progress = task_progress

    def process(self, manager):

        """
        Sets the progress of current task.

        """
        manager.set_progress(self.name, self.task_progress)

class TaskHeadError(TaskInfo):

    """
    Contains information about connection error.
    
    """
    def process(self, manager):

        """
        Executes when a connection error has occurred.

        """
        manager.do_error(self.name, self.status) # process an error

class TaskError(TaskHeadError):

    """
    Contains information about download error.
    
    """
    def __init__(self, name, status, offset):

        """
        :name: name of the mirror put the object in the queue, type str
        :status: status of performance, type int
        :offset: offset given to the task, type int

        """
        TaskHeadError.__init__(self, name, status)
        self.offset = offset

    def process(self, manager):

        """
        Executes when a download error has occurred.

        """
        manager.add_failed_part(self.offset) # add the task to failed
        TaskHeadError.process(self, manager) # process an

class TaskData(TaskError):

    """
    Contains file data.
    
    """
    def __init__(self, name, status, offset, data):

        """
        :name: name of the mirror put the object in the queue, type str
        :status: status of performance, type int
        :offset: offset given to the task, type int
        :data: file data, type sequence

        """
        TaskError.__init__(self, name, status, offset)
        self.data = data

    def process(self, manager):

        """
        Executes when the task successfully completed.

        """
        manager.write_data(self.name, self.offset, self.data) # write data
