#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from messages import Messages
from errors import CancelError
from console import Console
from manager import Manager
from networking import VERSION
from command_line import CommandLine

# выполняется при запуске сценария как самостоятельной программы

if __name__ == '__main__':

    try:
        Messages()
    except Exception as e:
        print(str(e))
        sys.exit()

    console = Console() # создадим объект консоли
    console.out('\nPyMGet v{}\n'.format(VERSION)) # выведем информацию о себе

    try:
        cl = CommandLine(sys.argv)
        cl.parse() # парсим командную строку
        manager = Manager(cl.urls, cl.block_size, cl.filename, cl.timeout) # создаём менеджер
        manager.download() # запускаем скачивание
    except CancelError as e: # если пользователь отменил скачивание
        console.out(str(e))
    except Exception as e: # любая другая ошибка
        console.error(str(e))
    
