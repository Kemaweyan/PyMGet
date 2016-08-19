#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os
import re, textwrap

from pymget.networking import URL
from pymget.console import Console
from pymget.messages import Messages
from pymget.errors import CommandLineError

# Класс парсера командной строки

class CommandLine:

    """
    Выбирает параметры командной строки и выполянет соответствующие действия.

    """
    def __init__(self, argv):

        """
        :argv: список параметров, тип sequence (str)

        """
        self.lang = Messages()
        self.argv = argv[1:] # первый параметр отбрасываем (содержит имя программы)
        self.block_size = 4 * 2**20 # размер блока по-молчанию - 4МБ
        self.filename = '' # имя файла неизвестно
        self.timeout = 10 # таймаут по-умолчанию - 10 сек
        self.urls = [] # список зеркал пуст
        # шаблон для нахождения URL
        self.url_re = re.compile('^(?:https?|ftp)://(?:[\w\.-]+(?::\d+)?)/')
        self.console = Console()

    def show_help(self):

        """
        Выводит текст помощи и завершает программу.

        """
        import __main__
        self.console.out(textwrap.dedent(self.lang.message.help.format(os.path.basename(__main__.__file__))))
        sys.exit()

    def parse_block_size(self, block_size):

        """
        Парсит параметр размера блока.

        :block_size: значение параметра, тип str

        """
        bs_re = re.compile('(\d+)(\w)?') # шаблон параметра "число + (опционально) буква"
        matches = bs_re.match(block_size)
        if not matches: # если параметр не сообтветствует шаблону
            # ошибка командной строки
            raise CommandLineError(self.lang.error.wrong_argument + self.lang.error.wrong_param.format('block size', block_size))
        self.block_size = int(matches.group(1)) # присваиваем размеру блока числовуч часть параметра
        if matches.group(2): # если указана размерность
            if matches.group(2) in 'kK': # если k или K
                self.block_size *= 2**10 # значит в килобайты
            elif matches.group(2) in 'mM': # если m или M
                self.block_size *= 2**20 # значит мегабайты
            else:
                # иначе - ошибка командной строки
                raise CommandLineError(self.lang.error.wrong_argument + self.lang.error.wrong_param.format('block size', block_size))

    def parse_timeout(self, timeout):

        """
        Парсит параметр времени ожидания.

        :timeout: значение параметра, тип str

        """
        if not timeout.isdigit(): # если параметр не число
            # ошибка командной строки
            raise CommandLineError(self.lang.error.wrong_argument + self.lang.error.wrong_param.format('timeout', timeout))
        self.timeout = int(timeout) # присваиваем таймаут

    def parse_urls_file(self, urls_file):

        """
        Парсит параметр файла со списком ссылок.

        :urls_file: значение параметра (имя файла), тип str

        """
        try:
            urls = []
            with open(urls_file, 'r') as links: # пробуем открыть текстовый файл
                for link in links: # каждую строку из файла
                    urls.append(link.strip('\r\n')) # добавляем в список, отбросив символы перевода строки
            self.urls.extend(urls) # дополняем список ссылок
        except FileNotFoundError: # файл не найден
            raise CommandLineError(self.lang.error.file_not_found.format(urls_file))
        except PermissionError: # недостаточно прав
            raise CommandLineError(self.lang.error.links_permission_denied.format(urls_file))
        except UnicodeDecodeError: # неверная структура файла
            raise CommandLineError(self.lang.error.corrupted_file.format(urls_file))
     
    def parse_out_file(self, filename):

        """
        Парсит параметр имени выходного файла.

        :filename: значение параметра, тип str

        """
        self.filename = filename

    def parse_long_arg(self, arg):

        """
        Парсит параметры, переданные в длинном формате --arg=value

        :arg: параметр, тип str

        """
        name, param = arg.split('=') # размеляем по символу =
        return param # возвращаем значение

    def parse(self):

        """
        Парсит командную строку.

        """
        args_iterator = iter(self.argv) # создадим итератор
        # для доступа к слудющим элементам с помощью next
        for arg in args_iterator:
            if arg == '-h' or arg == '--help':
                self.show_help() # показываем помощь
            if arg == '-v' or arg == '--version':
                sys.exit() # информация о версии уже показана, просто выходим
            elif arg == '-b':
                # парсим размер блока, передав ему следующий элемент
                self.parse_block_size(next(args_iterator))
            elif arg == '-T':
                # парсим время ожидания, передав ему следующий элемент
                self.parse_timeout(next(args_iterator))
            elif arg == '-u':
                # парсим файл со списком ссылок, передав ему следующий элемент
                self.parse_urls_file(next(args_iterator))
            elif arg == '-o':
                # парсим имя выходного файла, передав ему следующий элемент
                self.parse_out_file(next(args_iterator))
            elif arg.startswith('--block-size='):
                # парсим размер блока, передав ему длинный параметр
                self.parse_block_size(self.parse_long_arg(arg))
            elif arg.startswith('--timeout='):
                # парсим время ожидания, передав ему длинный параметр
                self.parse_timeout(self.parse_long_arg(arg))
            elif arg.startswith('--urls-file='):
                # парсим файл со списком ссылок, передав ему длинный параметр
                self.parse_urls_file(self.parse_long_arg(arg))
            elif arg.startswith('--out-file='):
                # парсим имя выходного файла, передав ему длинный параметр
                self.parse_out_file(self.parse_long_arg(arg))
            elif self.url_re.match(arg): # параметр соответствует шаблону URL
                self.urls.append(arg) # добавляем его в список URL
            else:
                # если параметр не соответствует ничему вышеперечисленному
                # выводим предупреждение про неизвестный аргумент и пропускаем его
                self.console.warning(self.lang.warning.unknown_arg.format(arg))

        # создадим из ссылок объекты URL,
        # предварительно отфильтровав их по шаблону
        self.urls = map(lambda url: URL(url), filter(lambda url: self.url_re.match(url), self.urls))
