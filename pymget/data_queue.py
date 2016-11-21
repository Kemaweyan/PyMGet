#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import queue
from abc import ABCMeta, abstractmethod

from .utils import singleton

class IDataQueue:
    """
    An interface for DataQueue.

    """
    @abstractmethod
    def put(self, obj): pass

    @abstractmethod
    def get(self, block=False, timeout=0): pass


@singleton
class DataQueue(queue.Queue, IDataQueue):

    """
    Queue of TaskInfo objects produced
    by network threads and used by Manager.
    Complete implementation is in queue.Queue
    class, but this class makes it singleton
    to access to single object from any place
    of the project.

    """
    pass

