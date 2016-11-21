#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from . import messages

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



def calc_size(size):

    """
    Translate bytes to other units (kB, MB, GB, TB) with 2 digits
    after floating point.

    :size: bytes count, type int
    :return: a string with a value in calculated units, type str

    """
    if size >= 2**40:
        return '{:.2f}{}'.format(size / 2**40, _("TiB"))
    if size >= 2**30:
        return '{:.2f}{}'.format(size / 2**30, _("GiB"))
    if size >= 2**20:
        return '{:.2f}{}'.format(size / 2**20, _("MiB"))
    if size >= 2**10:
        return '{:.2f}{}'.format(size / 2**10, _("KiB"))
    return '{}{}'.format(size, _("B"))



def calc_eta(eta):

    """
    Calculates estimated time of arrival
    in weeks, days, hours, minutes or seconds.

    :eta: ETA in seconds, type int

    """
    if not eta or eta > 3600 * 24 * 7 * 99:
        return ' ETA: ---'
    if eta > 3600 * 24 * 7: # more than a week
        return ' ETA: {:>2}{}'.format(round(eta / 3600 / 24 / 7), _('w'))
    if eta > 3600 * 24: # more than a day
        return ' ETA: {:>2}{}'.format(round(eta / 3600 / 24), _('d'))
    if eta > 3600: # more than a hour
        return ' ETA: {:>2}{}'.format(round(eta / 3600), _('h'))
    if eta > 60: # more than a minute
        return ' ETA: {:>2}{}'.format(round(eta / 60), _('m'))
    return ' ETA: {:>2}{}'.format(eta, _('s'))
