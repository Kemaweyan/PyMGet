#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import queue
from utils import singleton

@singleton
class DataQueue(queue.Queue):
    pass

