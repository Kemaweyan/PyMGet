#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import queue

from pymget.utils import singleton

@singleton
class DataQueue(queue.Queue):
    pass

