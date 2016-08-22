#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def singleton(cls):

    """
    Decorator function singleton. There could be only single instance of objects
    created from classes decorated with this decorator. Attempts to create new
    instances return a link to that single object. Usage:

    @singleton
    class ...

    """
    instances = {}
    def getinstance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    return getinstance




def calc_units(size):

    """
    Translate bytes to other units (kB, MB, GB, TB) with 2 digits
    after floating point.

    :size: bytes count, type int
    :return: a string with a value in calculated units, type str

    """
    if size >= 2**40:
        return '{:.2f}TiB'.format(size / 2**40)
    if size >= 2**30:
        return '{:.2f}GiB'.format(size / 2**30)
    if size >= 2**20:
        return '{:.2f}MiB'.format(size / 2**20)
    if size >= 2**10:
        return '{:.2f}KiB'.format(size / 2**10)
    return '{}B'.format(size)
