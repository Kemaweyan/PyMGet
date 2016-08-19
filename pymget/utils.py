#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def singleton(cls):

    """
    Функция-декоратор синглетон. Объекты декорированных таким образом классов
    будут существовать в единственном экземпляре. Попытка создания новых экземпляров
    будет возвращать ссылку на уже существующий объект. Использование:

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
    Переводит байты в кратные единицы (КБ, МБ, ГБ, ТБ) с 2 десятичными знаками.

    :size: величина в байтах, тип int
    :return: строка, состоящая из величины и единиц измерения, тип str

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
