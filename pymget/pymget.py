#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys

from pymget.messages import Messages
from pymget.errors import CancelError
from pymget.console import Console
from pymget.manager import Manager
from pymget.networking import VERSION
from pymget.command_line import CommandLine

# выполняется при запуске сценария как самостоятельной программы

def start():

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
    
