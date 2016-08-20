#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import queue

from pymget.utils import singleton

@singleton
class DataQueue(queue.Queue):

    """
    Queue of TaskInfo objects produced
    by network threads and used by Manager.
    Complete implementation is in queue.Queue
    class, but this class makes it singleton
    to access to single object from any place
    of the project.

    """
    pass

