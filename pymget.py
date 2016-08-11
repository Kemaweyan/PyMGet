#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os
import threading, queue
from http import client
from collections import deque
import time, struct, re, textwrap
import ftplib
from abc import ABCMeta, abstractmethod, abstractproperty

VERSION = '1.26'

start_msg = '\nPyMGet v{}\n'

help_msg = """
    Программа предназначена для параллельного скачивания файлов с нескольких зеркал.
    Поддерживаемые протоколы: HTTP, HTTPS, FTP. 
    
    Использование:

     {} [ПАРАМЕТРЫ...] ССЫЛКИ...

    Параметры:

     -h                             Вывести справочную информацию.
     --help

     -b размер_блока                Задаёт размер блоков, запрашиваемых у заркал.
     --block-size=размер_блока      По-умолчанию равен 4МБ. Значение может быть 
                                    указано в байтах, килобайтах или мегабайтах. Для
                                    этого необходимо после числа добавить символ K 
                                    или M.

     -T время_ожидания              Задаёт время ожидания ответа сервера в секундах.
     --timeout=время_ожидания       По-умолчанию равно 10 сек.

     -o имя_файла                   Задаёт имя файла, в который будут сохранены
     --out-file=имя_файла           данные. По-умолчанию используется имя файла на
                                    сервере. Если имя файла определить невозможно, 
                                    используется имя out.

     -l имя_файла                   Задаёт файл со списком ссылок, где каждая ссылка
     --list_urls=имя_файла          располагается на отдельной строке. Ссылки из 
                                    этого файла добавляются к ссылкам из командной 
                                    строки.

    Ссылки должны начинаться с указания протокола http://, https:// или ftp:// и
    перечисляться через пробел. Если в параметрах указан файл со списком ссылок, то
    в командной строке ссылки можн оне указывать.
"""

error_msg = '\nОшибка: '
warning_msg = '\nВнимание: '

connected_msg = 'Соединение с сервером {} OK'
downloading_msg = '\nПолучение файла {} {} байт ({}):\n'
redirect_msg = '\nПеренаправление с зеркала {} по адресу {}'
cancel_msg = 'Операция отменена пользователем.'

connection_error = 'не удалось соединиться с сервером {}'
no_partial_error = 'сервер {} не поддерживает скачивание по частям.'
http_error = 'неверный ответ сервера. Код {}'
filesize_error = 'размер файла на сервере {} {} байт отличается\nот полученного ранее {} байт.'
download_impossible_error = 'невозможно скачать файл.'
wrong_commandline_error = 'неверный аргумент командной строки. '
arg_needs_param_error = "аргумент '{}' требует указания параметра."
wrong_param_format_error = "неверный формат параметра '{}': {}"
file_not_found_error = "файл '{}' не найден."
file_is_corrupted_error = "невозможно прочесть список ссылок '{}'. Файл повреждён."
file_permission_error = "невозможно прочесть список ссылок '{}'. Отказано в доступе."
no_mirrors_error = 'нет зеркал для скачивания.'
file_open_error = "не удалось открыть файл '{}': {}"
file_create_error = "не удалось создать файл '{}': {}"
file_write_error = "запись в файл '{}' завершилась неудачей."
permission_denied_error = 'отказано в доступе.'

empty_filename_warning = 'невозможно определить имя файла на зеркале {}.'
other_filename_warning = 'имя файла на зеркале {} отличается от {}. Возможно, это другой файл.'
unknown_arg_warning = "неизвестный аргумент: '{}'"

anyway_download_question = 'Всё равно использовать зеркало {}? (да/НЕТ):'
rewrite_file_question = 'Файл {} существует. Вы действительно хотите перезаписать файл? (да/НЕТ):'
file_create_question = 'Файл {} не найден. Начать скачивание заново? (ДА/нет):'


# Классы исключений

class FatalError(Exception): pass
class FileError(Exception): pass
class CancelError(Exception): pass
class CommandLineError(Exception): pass
class URLError(Exception): pass
class MirrorError(Exception): pass




def singleton(cls):

    """
    Функция-декоратор синглетон. Объекты декорированных таким образом классов
    будут существовать в единственном экземпляре. Попытка создания новых экземпляров
    будет возвращать ссылку на уже существующий объект. Использование:

    @singleton
    class ...

    """
    instances = {}
    def getinstance(*args):
        if cls not in instances:
            instances[cls] = cls(*args)
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



# Классы для ввода информации в консоль

class ProgressBar:

    """
    Класс индикатора прогресса. 
    Перед использованием необходимо задать общий размер изменением свойства total.
    Для изменения прогресса используется метод update

    """

    WIDTH = 57 # ширина прогрессбара, вычисляется как 80 - [ширина всего остального]

    def __init__(self):
        self._total = 0
        self.time = 0

    @property
    def total(self):
        return self._total

    @total.setter
    def total(self, total):
        self.time = time.time()
        self._total = total

    def update(self, complete, gotten_bytes):

        """
        Устанавливает текущий прогресс. Поскольку программа может качать файл за несколько сеансов (в результате сбоя),
        для правильного вычисления скорости необходимо отдельно указывать общий прогресс и прогресс за текущий сеанс.

        :complete: общее количество полученных байт за все сеансы, прогресс равен complete / total * 100%, тип int
        :gotten_bytes: количество байт, полученное с момента запуска программы, тип int

        """
        # возможно деление на 0
        try:
            speed = gotten_bytes / (time.time() - self.time)
            percent = complete / self.total
            progress = round(self.WIDTH * percent)
        except:
            speed = 0
            percent = 0
            progress = 0

        # формат прогрессбара:
        # [строка прогресса] |прогресс в процентах| |скорость скачивания|
        #   WIDTH символов        7 символов            12 символов

        bar = '[{0:-<{1}}] {2:>7.2%} {3:>10}/s\r'.format('#'*progress, self.WIDTH, percent, calc_units(speed))

        sys.stdout.write(bar)
        sys.stdout.flush()




@singleton
class Console:

    """
    Класс консоли. Используется вместо print, поскольку дополнительно учитывает 
    наличие/отсутствие перевода строки в конце предыдущего вывода. Если последний 
    вывод был сделан прогрессбаром, то перевода строки в конце нет и функция print
    вывела бы текст поверх прогрессбара. Во избежание этого класс добавляет перевод
    строки перед выводом следующего сообщения.

    Методы:

    out: простой вывод сообщений без префикса.
    warning: выводит сообщение с префиксом 'Внимание: '
    error: выводит сообщение с префиксом 'Ошибка: '
    ask: выводит сообщение с вопросом да/нет
    progress: выводит/обновляет прогрессбар

    """

    def __init__(self):
        self.newline = True
        self.progressbar = ProgressBar()

    def out(self, text='', end='\n'):

        """
        Выводит сообщение без префикса. 

        :text: текст, котоорый будет выведен, тип str
        :end: завершающий символ, по-умолчанию перевод строки, тип str

        """
        if not self.newline:
            print()
        print(text, end=end)
        self.newline = '\n' in end or text.endswith('\n')

    def error(self, text, end='\n'):

        """
        Выводит сообщение об ошибке. 

        :text: текст, котоорый будет выведен, тип str
        :end: завершающий символ, по-умолчанию перевод строки, тип str

        """
        if text:
            self.out(error_msg + text, end)

    def warning(self, text, end='\n'):

        """
        Выводит предупреждение. 

        :text: текст, котоорый будет выведен, тип str
        :end: завершающий символ, по-умолчанию перевод строки, тип str

        """
        if text:
            self.out(warning_msg + text, end)

    def progress(self, complete, gotten_bytes):

        """
        Выводит/обновляет прогрессбар.

        :complete: общее количество полученных байт за все сеансы, прогресс равен complete / total * 100%, тип int
        :gotten_bytes: количество байт, полученное с момента запуска программы, тип int

        """
        # Если перед этим было выведено собщение, то отделяем прогрессбар пустрой строкой
        if self.newline:
            print()
        self.newline = False
        self.progressbar.update(complete, gotten_bytes)

    def ask(self, text, default):

        """
        Выводит сообщение с вопросом, на который необходимо ответить 'да' или 'нет'. 

        :text: текст, котоорый будет выведен, тип str
        :default: ответ по-умолчанию (если пользователь просто нажмёт Enter), тип bool

        """
        YES = ['y', 'yes', 'д', 'да'] # варианты ответов 'да'
        NO = ['n', 'no', 'н', 'нет'] # варианты ответов 'нет'
        # Повторять пока пользователь не даст допустимый ответ
        while True:
            self.out(text, end=' ')
            answer = input().lower()
            if answer in YES:
                return True
            if answer in NO:
                return False
            if answer == '':
                return default




# Классы для работы с сетью

class URL:

    """
    Класс адреса URL. Поддерживаемые протоколы: HTTP/HTTPS/FTP

    """

    def __init__(self, url):

        """
        :url: строка url, тип str

        """
        self.url = url

        # регулярное выражение проверяет правильность URL и разбивает её на составные части:
        # протокол, хост (с портом), путь к файлу, имя файла
        # путь в файлу + имя файла также объединяется в запрос

        url_re = re.compile('^(https?|ftp)://([\w\.-]+(?::\d+)?)((?:/(.+?))?/([^\/]+)?)?$', re.I)
        matches = url_re.match(url)
        # строка не соответствует шаблону - ошибка
        if not matches:
            raise URLError(url)
        self.protocol = matches.group(1).lower() # http, https или ftp
        self.host = matches.group(2) # имя хоста или ip адрес в формате host или host:port
        self.request = matches.group(3) # запрос, начинающийся с /
        self.path = matches.group(4) # путь к файлу без начального /
        self.filename = matches.group(5) # имя файла




class NetworkThread(threading.Thread, metaclass=ABCMeta):

    """
    Базовый абстрактный класс, наследуемый сетевыми потоками.

    """
    # строка user_agent для передачи HTTP(S) серверам
    user_agent = 'PyMGet/{} ({} {}, {})'.format(VERSION, os.uname().sysname, os.uname().machine, os.uname().release)

    def __init__(self):
        threading.Thread.__init__(self)
        self.ready = threading.Event() # индикатор завершения потока

    @abstractmethod
    def run(self): pass # выполняется в отдельном потоке, должен быть реализован в унаследованных классах




# Классы для подключения к серверу

class ConnectionThread(NetworkThread):

    """
    Базовый абстрактный класс для классов соединений.

    """

    def __init__(self, url, timeout):

        """
        :url: объект URL, описывающий адрес сервера, к которому необходимо подключиться, тип URL
        :timeout: максимальное время ожидания в секундах, тип float

        """
        NetworkThread.__init__(self)
        self.url = url
        self.timeout = timeout
        self.conn = None

    def run(self):
        """
        Выполняется в отдельном потоке, вызывает абстрактный метод connect.
        Помещает объект типа Part в очередь менеджера.

        """
        try:
            # объект part создаёт объект класса-наследника
            part = self.connect()
        except:
            # в случае ошибки создаёт объект типа HeadErrorPart
            part = HeadErrorPart(self.url.host, 0)
        finally:
            Manager.data_queue.put(part) # в конце помещаем часть в очередь
            self.ready.set() # и помечаем поток завершенным

    @abstractmethod
    def connect(self): pass # метод, выполняющий подключение, должен быть реализован в унаследованных классах. Возвращает объект типа Part

class HTTXThread(ConnectionThread):

    """
    Базовый класс для HTTP и HTTPS протоколов

    """

    def connect(self):
        
        """
        Осуществляет подключение к серверу.
        Классы-наследники обязаны определить свойство protocol,
        возвращающее client.HTTPConnection или client.HTTPSConnection

        """
        # в заголовке передаёт User-Agent и Refferer - главную страницу сервера для случаев, 
        # когда сервер блокирует скачивание по ссылкам со сторонних ресурсов
        headers = {'User-Agent': self.user_agent, 'Refferer': '{}://{}/'.format(self.url.protocol, self.url.host)}
        self.conn = self.protocol(self.url.host, timeout=self.timeout)
        self.conn.request('HEAD', self.url.request, headers=headers)
        response = self.conn.getresponse()

        # если статус 3xx
        if response.status // 100 == 3:
            location = response.getheader('Location')
            path = ''
            # XXX: переписать через re
            if not location.startswith('http'):
                if not location.startswith('/'):
                    path = '/' + self.url.request.rsplit('/', 1)[0]
                location = '{}://{}{}'.format(self.url.protocol, self.url.host, path + location)
            # возвращает часть для перенаправления
            return RedirectPart(self.url.host, response.status, URL(location))

        if response.status != 200: # ошибка HTTP(S)
            return HeadErrorPart(self.url.host, response.status)

        file_size = int(response.getheader('Content-Length'))
        part = HeadPart(self.url.host, response.status, file_size)
        response.close()
        return part

    # абстрактное свойство, наследники обязаны впернуть класс для соединения
    @abstractproperty
    def protocol(self): pass

class HTTPThread(HTTXThread):

    """
    Класс для подключения по протоколу HTTP.
    Определяет свойство protocol как client.HTTPConnection

    """
    @property
    def protocol(self):
        return client.HTTPConnection

class HTTPSThread(HTTXThread):

    """
    Класс для подключения по протоколу HTTPS.
    Определяет свойство protocol как client.HTTPSConnection

    """
    @property
    def protocol(self):
        return client.HTTPSConnection

class FTPThread(ConnectionThread):

    """
    Класс для подключения по протоколу FTP.

    """

    def connect(self):
        """
        Осуществляет анонимное подключение к FTP серверу, переходит в каталог
        с запрошенным файлом и определяет его размер.

        """
        self.conn = ftplib.FTP(self.url.host, 'anonymous', '', timeout=self.timeout)
        self.conn.voidcmd('TYPE I')
        self.conn.cwd(self.url.path)
        self.conn.voidcmd('PASV')
        file_size = self.conn.size(self.url.filename)
        return HeadPart(self.url.host, 200, file_size) # устанавливаем код 200 для совместимости с HTTP




# Классы для скачивания данных

class DownloadThread(NetworkThread):

    """
    Абстрактный базовый класс потока для скачивания.

    """
    FRAGMENT_SIZE = 32 * 2**10 # размер фрагмента, который будет передаваться в главный поток, равен 32кБ

    def __init__(self, url, conn, offset, block_size):

        """
        :url: объект URL, описывающий ссылку для скачивания, тип URL
        :conn: объект соединения, тип client.HTTPConnection, client.HTTPSConnection или ftplib.FTP
        :offset: смещение, с которого начинать скачивание, тип int
        :block_size: размер блока, который необходимо скачать, тип int

        """
        NetworkThread.__init__(self)
        self.name = url.host
        self.conn = conn
        self.request = url.request
        self.offset = offset
        self.block_size = block_size

class HTTXDownloadThread(DownloadThread):

    """
    Класс потока для скачивания с HTTP/HTTPS.

    """
    def run(self):
        """
        Функция скачивания, выполняется в отдельном потоке

        """
        # в заголовке передаёт диапазон скачивания от offset до offset + block_size - 1 (включительно)
        headers = {'User-Agent': self.user_agent, 'Refferer': '{}://{}/'.format(self.protocol, self.name), 
                    'Range': 'bytes={}-{}'.format(self.offset, self.offset + self.block_size - 1)}
        status = 0 # изначально статус 0, что значит ошибку соединения
        try:
            self.conn.request('GET', self.request, headers=headers)
            response = self.conn.getresponse()
            # сервер не поддерживает скачивание по частям - ошибка
            if response.status != 206:
                status = response.status
                raise MirrorError
            part_size = int(response.getheader('Content-Length')) # столько байт сервер передал клиенту
            gotten_size = 0 # количество полученных байт
            fragment_offset = 0 # смещение первого байта следующего фрагмента
            # цикл пока не получены все переданные байты
            while part_size > gotten_size:
                data = response.read(self.FRAGMENT_SIZE)
                gotten_size += len(data) # нельзя просто добавлять FRAGMENT_SIZE, т.к. последний фрагмент может быть меньше этого размера
                if part_size <= gotten_size: # получены все байты или даже боьше :-)
                    # добавляем в очередь «финальную» часть
                    part = FinalDataPart(self.name, response.status, self.offset, fragment_offset, data, gotten_size)
                else:
                    # не все ещё байты получены - просто добавляем в очередь часть с данными
                    part = DataPart(self.name, response.status, self.offset, fragment_offset, data, gotten_size)
                fragment_offset = gotten_size # смещение следующего фрагмента равно кол-ву уже полученных (добавленных в очередь) байт
                Manager.data_queue.put(part)
            response.close()
        except:
            # в случае ошибки помещаем в очередь часть со статусом
            part = ErrorPart(self.name, status, self.offset)
            Manager.data_queue.put(part)
        finally:
            self.ready.set() # в конце помечаем поток завершенным

class HTTPDownloadThread(HTTXDownloadThread):

    """
    Класс для скачивания с HTTP. Конкретизирует протокол

    """
    @property
    def protocol(self):
        return 'http'

class HTTPSDownloadThread(HTTXDownloadThread):

    """
    Класс для скачивания с HTTPS. Конкретизирует протокол

    """
    @property
    def protocol(self):
        return 'https'

class FTPDownloadThread(DownloadThread):

    """
    Класс для скачивания с FTP.

    """
    def __init__(self, url, conn, offset, block_size, file_size):

        """
        :url: объект URL, описывающий адрес для скачивания, тип URL
        :conn: объект соединения, тип ftplib.FTP
        :offset: смещение, с которого начинать скачивание, тип int
        :block_size: размер блока, который необходимо скачать, тип int
        :file_size: размер файла, полученный при подключении, тип int

        """
        DownloadThread.__init__(self, url, conn, offset, block_size)
        self.filename = url.filename
        self.host = url.host
        self.file_size = file_size

    def run(self):

        """
        Функция скачивания, выполняется в отдельном потоке

        """
        gotten_size = 0 # количество полученных байт
        fragment_offset = 0 # смещение первого байта следующего фрагмента
        try:
            sock = self.conn.transfercmd('RETR ' + self.filename, self.offset)
            # цикл пока получено байт меньше, чем размер блока
            # однако, последний блок может быть меньше этого размера, т.к. размер файла не обязательно кратен размеру блоку
            while gotten_size < self.block_size:
                # получаем даныне, но не более размера фрагмента 
                # и кол-ва данных, оставшихся до целого блока
                data = sock.recv(min(self.block_size - gotten_size, self.FRAGMENT_SIZE))
                if not data: # в случае отсутствия данных - ошибка
                    raise MirrorError
                gotten_size += len(data) # добавляем фактически полученные данные
                # считаем блок завершенным, если получено байт больше или равно размеру блоку
                # или если достингнут конец файла
                complete = self.block_size - gotten_size <= 0 or self.file_size - self.offset - gotten_size <= 0
                if complete:
                    part = FinalDataPart(self.name, 206, self.offset, fragment_offset, data, gotten_size)
                else:
                    part = DataPart(self.name, 206, self.offset, fragment_offset, data, gotten_size)
                fragment_offset = gotten_size # смещение следующего фрагмента равно кол-ву уже полученных (добавленных в очередь) байт
                Manager.data_queue.put(part)
                if complete: # если блок завершен - выходим из цикла
                    break
            sock.close()
        except:
            # в случае ошибки создаём часть с кодом 0, т.е. ошибка подключения
            part = ErrorPart(self.name, 0, self.offset)
            Manager.data_queue.put(part)
        finally:
            self.ready.set() # в конце помечаем поток завершенным



# Классы зеркал

class Mirror(metaclass=ABCMeta):

    """
    Абстрактный базовый класс зеркала

    """
    @staticmethod
    def create(url, block_size, timeout):

        """
        Статический фабричный метод, создающий объект зеркала
        в соответствии с протоколом из URL.

        :url: объект URL, описывающий адрес сервера, тип URL
        :block_size: размер блока, который необходимо скачать, тип int
        :timeout: максимальное время ожидания в секундах, тип float

        """
        if url.protocol == 'http':
            return HTTPMirror(url, block_size, timeout)
        if url.protocol == 'https':
            return HTTPSMirror(url, block_size, timeout)
        if url.protocol == 'ftp':
            return FTPMirror(url, block_size, timeout)

    def __init__(self, url, block_size, timeout):

        """
        :url: объект URL, описывающий адрес сервера, тип URL
        :block_size: размер блока, который необходимо скачать, тип int
        :timeout: максимальное время ожидания в секундах, тип float

        """
        self.console = Console()
        self.url = url
        self.block_size = block_size
        self.timeout = timeout
        self.file_size = 0 # размер файла определяется после подключения
        self.conn = None # объект соединения
        self.need_connect = True # флаг необходимости подключиться
        self.ready = False # флаг готовности качать очередную часть
        self.conn_thread = None # поток соединения
        self.dnl_thread = None # поток скачивания

    def connect(self):

        """
        Подключается к серверу.

        """
        self.ready = False # зеркало не готово качать очередную часть файла
        self.need_connect = False # зеркало не требует подключения
        # создаём поток подключения
        # свойство connetion_thread должено быть определено в наследниках
        self.conn_thread = self.connection_thread(self.url, self.timeout)
        self.conn_thread.start()

    def wait_connection(self):

        """
        Ожидает завершения потоков.

        :return: True если нет активных потоков, False - если есть активный поток

        """
        if self.conn_thread: # если поток подключения создан
            if not self.conn_thread.ready.wait(0.001): # проверяем его завершенность с ожиданием 1 мс
                return False
            self.conn_thread.join() # ждём истиного завершения
            self.conn = self.conn_thread.conn # сохраняем объект соединения
            self.conn_thread = None # удаляем объект потока
        if self.dnl_thread: # если поток скачивания создан
            if not self.dnl_thread.ready.wait(0.001): # проверяем его завершенность с ожиданием 1 мс
                return False
            self.dnl_thread.join() # ждём истиного завершения
            self.dnl_thread = None # удаляем объект потока
        return True

    def download(self, offset):

        """
        Запускает поток скачивания очередной части.

        :offset: смещение, с которого начинать скачивать, тип int

        """
        self.ready = False # зеркало не готово качать очередную часть файла
        # создаём поток скачивания
        # свойство download_thread должено быть определено в наследниках
        self.dnl_thread = self.download_thread(self.url, self.conn, offset, self.block_size)
        self.dnl_thread.start()

    def done(self):

        """
        Помечает зеркало как завершившее скачивание

        """
        self.ready = True # зеркало готово качать очередную часть

    def connect_message(self):

        """
        Выводит сообщение о соединении с сервером

        """
        self.console.out(connected_msg.format(self.url.host))

    def join(self):

        """
        Ожидает завершение созданных потоков

        """
        if self.conn_thread:
            self.conn_thread.join()
        if self.dnl_thread:
            self.dnl_thread.join()

    def close(self):

        """
        Закрывает соединение

        """
        if self.conn:
            self.conn.close()

    @property
    def name(self):

        """
        Имя зеркала

        """
        return self.url.host

    @property
    def filename(self):

        """
        Имя файла

        """
        return self.url.filename

    @abstractproperty
    def connection_thread(self): pass # абстрактное свойство, возвращающее класс потока подключения

    @abstractproperty
    def download_thread(self): pass # абстрактное свойство, возвращающее класс потока скачивания

class HTTPMirror(Mirror):

    """
    Класс зеркала HTTP

    """
    @property
    def connection_thread(self):

        """
        Возвращает класс потока подключения

        """
        return HTTPThread

    @property
    def download_thread(self):

        """
        Возвращает класс потока скачивания

        """
        return HTTPDownloadThread

class HTTPSMirror(Mirror):

    """
    Класс зеркала HTTPS

    """
    @property
    def connection_thread(self):

        """
        Возвращает класс потока подключения

        """
        return HTTPSThread

    @property
    def download_thread(self):

        """
        Возвращает класс потока скачивания

        """
        return HTTPSDownloadThread

class FTPMirror(Mirror):

    """
    Класс зеркала FTP

    """
    def __init__(self, url, block_size, timeout):

        """
        :url: объект URL, описывающий адрес сервера, тип URL
        :block_size: размер блока, который необходимо скачать, тип int
        :timeout: максимальное время ожидания в секундах, тип float

        """
        Mirror.__init__(self, url, block_size, timeout)
        self.connected = False # флаг, сигнализирующий, что сообщение о подключении уже выведено

    def done(self):

        """
        Помечает зеркало как завершившее скачивание

        """
        self.ready = False # в отличие от HTTX FTP сразу е готово качать следующую часть
        self.need_connect = True # а нуждается в переподключении

    @property
    def connection_thread(self):

        """
        Возвращает класс потока подключения

        """
        return FTPThread

    @property
    def download_thread(self):

        """
        Возвращает класс потока скачивания

        """
        return FTPDownloadThread

    def download(self, offset):

        """
        Запускает скачивания очередной части.

        :offset: смещение, с которого начинать скачивать, тип int

        """
        self.ready = False # зеркало не готово качать очередную часть файла
        # создаём поток скачивания
        # но в отличие от HTTX передаём ему ещё параметр file_size
        self.dnl_thread = self.download_thread(self.url, self.conn, offset, self.block_size, self.file_size)
        self.dnl_thread.start()

    def connect_message(self):

        """
        Вывод сообщение о соединении с сервером

        """
        if self.connected: # если уже выводилось - выходим
            return
        self.connected = True # сообщение уже выводилось
        Mirror.connect_message(self)



# Класс выходного файла

class OutputFile:

    """
    Класс выходного файла. Поддерживает менеджер контекста.

    seek: перемещает указатель файла
    write: пишет в файл

    """
    def __init__(self, filename):

        """
        :filename: имя файла, тип str

        """
        self.filename = filename
        self.console = Console()
        self.context = Context(self.filename)
        self.file = self.open_file(self.context.exists)

    def open_file(self, context_exists):

        """
        Открывает файл для записи или обновления.
        Проверяет наличие контекста (файл *.mget): если контекста нет - создаёт новый файл или запрашивает перезапись существующего.
        Если контекст есть, то открывает файл для обновления, если файла нет - запрашивает создание файла.

        :context_exists: флаг сущестования контекста, тип bool

        """
        if context_exists: # если контекст существует
            try:
                return open(self.filename, 'rb+') # открываем файл для обновления
            except:
                # в случае ошибки
                if os.path.isfile(self.filename): # если файл существует
                    raise FileError(file_open_error.format(self.filename, permission_denied_error)) # ошибка доступа
                # если не существует
                if not self.console.ask(file_create_question.format(self.filename), True): # запрашиваем создание
                    # и если пользователь ответил "нет" 
                    raise CancelError(cancel_msg) # отмена скачивания
                self.context.reset() # сбрасываем контекст
                return self.open_file(False) # и вызываем этот-же метод без контекста
        else: # если контекста нет         
            if os.path.isfile(self.filename): # если фаайл существует
                if not self.console.ask(rewrite_file_question.format(self.filename), False): # запрашиваем пересоздание
                    # если пользователь ответил "нет"
                    raise CancelError(cancel_msg) # отмена скачивания
            try:
                return open(self.filename, 'wb') # открываем файл для записи (существующий файл будет перезаписан с нуля)
            except:
                # в случае ошибки - невозможно здать файл
                raise FileError(file_create_error.format(self.filename, permission_denied_error))

    def __enter__(self):
        """
        Медод, вызываем менеджером контекста при входе.
        Возвращает ссылку на себя, внутри оператора with будут доступны методы seek и write

        """
        return self 

    def __exit__(self, exception_type, exception_value, traceback):
        """
        Медод, вызываем менеджером контекста при выходе.
        Закрывает файл, если он был открыт

        """
        try:
            self.file.close()
        except:
            return False # сообщаем, что исключение обработано

    def seek(self, offset):
        """
        Медод перемещения указателя в файле. 

        :offset: позиция, куда нужно переместить указатель, тип int

        """
        try:
            self.file.seek(offset, 0) # перемещаем указатель в файле на offset байт от начала (параметр 0)
        except:
            # в случае неудачи - ошибка записи
            raise FileError(file_write_error.format(self.filename))

    def write(self, data):
        """
        Медод данных записи в файл. 

        :data: данные, которые будут записаны, тип sequence

        """
        try:
            return self.file.write(data) # пишем в файл
        except:
            # в случае неудачи - ошибка записи
            raise FileError(file_write_error.format(self.filename))




# Классы частей (объектов, помещаемых потоками в очередь)

class Part(metaclass=ABCMeta):

    """
    Базовый абстрактный класс части.
    Наследники обязаны реализовать метод process, который будет выполнять необходимые действия.

    """
    def __init__(self, name, status):

        """
        :name: имя зеркала, которое отправило часть, тип str
        :status: статус выполнения операции потоком, тип int

        """
        self.console = Console()
        self.name = name
        self.status = status

    @abstractmethod
    def process(self, manager): pass # метод, выполняющий действия в зависимости от типа части

class HeadPart(Part):

    """
    Заголовочная часть, содержит информацию о файле.
    
    """
    def __init__(self, name, status, file_size):

        """
        :name: имя зеркала, которое отправило часть, тип str
        :status: статус выполнения операции потоком, тип int
        :file_size: размер файла, тип int

        """
        Part.__init__(self, name, status)
        self.file_size = file_size

    def process(self, manager):
        """
        Выполняется в случае корректного соединения с сервером

        """
        manager.set_file_size(self) # указывает размер файла менеджеру

class RedirectPart(Part):

    """
    Часть перенаправления, содержит новую ссылку.
    
    """
    def __init__(self, name, status, location):

        """
        :name: имя зеркала, которое отправило часть, тип str
        :status: статус выполнения операции потоком, тип int
        :location: ссылка на новое место, тип URL

        """
        Part.__init__(self, name, status)
        self.location = location

    def process(self, manager):
        """
        Выполняется в случае перенаправления на другой адрес

        """
        manager.redirect(self) # перенаправляем

class HeadErrorPart(Part):

    """
    Часть ошибки подключения.
    
    """
    def process(self, manager):
        """
        Выполняется в случае ошибки подключения

        """
        manager.error(self) # обрабатываем ошибку

class ErrorPart(HeadErrorPart):

    """
    Часть ошибки скачивания.
    
    """
    def __init__(self, name, status, offset):

        """
        :name: имя зеркала, которое отправило часть, тип str
        :status: статус выполнения операции потоком, тип int
        :offset: смещение в задании, тип int

        """
        Part.__init__(self, name, status)
        self.offset = offset

    def process(self, manager):
        """
        Выполняется в случае ошибки скачивания

        """
        manager.add_failed_part(self.offset) # добавляем смещение части в список невыполненых
        HeadErrorPart.process(self, manager) # обрабатываем ошибку

class DataPart(ErrorPart):

    """
    Часть с данными.
    
    """
    def __init__(self, name, status, offset, fragment_offset, data, gotten_size):

        """
        :name: имя зеркала, которое отправило часть, тип str
        :status: статус выполнения операции потоком, тип int
        :offset: смещение в задании, тип int
        :fragment_offset: смещение данных относительно начала файла, тип int
        :data: данные, тип sequence
        ：gotten_size： количество данных, полученных за данный сеанс, тип int

        """
        ErrorPart.__init__(self, name, status, offset)
        self.data = data
        self.fragment_offset = fragment_offset
        self.gotten_size = gotten_size

    def process(self, manager):

        """
        Выполняется при получении данных

        """
        manager.write_data(self) # пишем данные

class FinalDataPart(DataPart):

    """
    Финальная часть с данными, задание выполнено.
    
    """
    def process(self, manager):

        """
        Выполняется при завершении задания

        """
        manager.task_done(self) # помечаем задание выполненым




# Класс менеджера скачивания

class Manager:

    """
    Класс менеджера скачивания. Создаёт зеркала ис списка URL, подключается к ним,
    раздаёт задания и обрабатывает результаты
    
    """
    data_queue = queue.Queue() # очередь частей (результатов) для синхронизации потоков

    def __init__(self, urls, block_size, filename, timeout):

        """
        :urls: список URL, тип iterable <URL>
        :block_size: размер блока, тип int
        :filename: имя файла, указанное пользователем, тип str
        :timeout: время ожидания ответа сервера, тип float

        """
        self.console = Console()
        self.block_size = block_size
        self.filename = filename
        self.given_filename = filename
        self.timeout = timeout
        self.mirrors = {} # зеркала
        self.gotten_sizes = {} # кол-во полученных байт в активных заданиях, необходимо для вычисления прогресса
        for url in urls:
            try:
                # пробуем создать зеркало
                mirror = Mirror.create(url, self.block_size, self.timeout) # XXX: переписать через Manager.create_mirror
                # если имя файла не проходит проверку
                if not self.check_filename(mirror):
                    # ошибка адреса
                    raise URLError(mirror.filename)
                self.mirrors[url.host] = mirror # добавляем зеркало в список
                self.gotten_sizes[url.host] = 0 # создаём элемент в списке прогресса активных заданий
            except URLError as e: # ошибка адреса
                self.console.error(str(e)) # выводим сообщение об ошибке
        if not self.mirrors: # если нет зеркал
            raise FatalError(no_mirrors_error) # критическая ошибка
        if self.filename == '': # если имя файла не определилось
            self.filename = 'out' # присваиваем имя out
        self.context = Context(self.filename) # создаём объект контекста
        self.outfile = OutputFile(self.filename) # создаём объект выходного файла
        self.offset = self.context.offset # текущее смещение равно смещению из контекста, продолжаем качать дальше
        self.written_bytes = self.context.written_bytes # кол-во записанных байт равно кол-ву записанных байт из контекста
        self.old_progress = self.written_bytes # сохраняем прогресс предыдущих сессий (необходимо для корректного вычисления скорости)
        self.failed_parts = deque(self.context.failed_parts) # загружаем из контекста список неудачных частей
        self.file_size = 0 # размер файла равен нулю, определится после соединения
        self.parts_in_progress = [] # список активных заданий

    def check_filename(self, mirror):

        """
        Проверяет имя файла на соответствие другим.

        :mirror: объект зеркала, тип Mirror

        """
        if self.given_filename: # если имя фйайла указано вручную
            return True # пропускаем проверку
        if self.filename == '': # если имя файла ещё не определено
            if mirror.filename == '': # если если зеркало не смонго определить имя файла
                self.console.warning(empty_filename_warning.format(mirror.name)) # выводим предупреждение что имя пустое
                return self.console.ask(anyway_download_question.format(mirror.name), False) # запрашиваем подтверждение на использование зеркала
            self.filename = mirror.filename # сохраняем имя файла
            return True # проверка пройдена
        if os.path.basename(self.filename) == mirror.filename: # если имя совпадает
            return True # проверка пройдена
        # иначе имя отдличается
        self.console.warning(other_filename_warning.format(mirror.name, self.filename)) # выводим предупреждение
        return self.console.ask(anyway_download_question.format(mirror.name), False) # запрашиваем подтверждение на использование зеркала

    def wait_connections(self):

        """
        Ожидает завершения потоков, в случае необходимости запускает подключение и раздаёт задания.

        """
        for name, mirror in self.mirrors.items():
            if mirror.wait_connection(): # если потоки зеркала зевершены
                if mirror.ready: # если зеркало готово получить задание
                    self.give_task(mirror) # даём задание
                elif mirror.need_connect: # если зеркало требует подключения
                    mirror.connect() # запускаем подключение

    def give_task(self, mirror):

        """
        Даёт задание зеркалу.

        :mirror: объект зеркала, тип Mirror

        """
        if self.failed_parts: # если есть неудачные части
            new_part = self.failed_parts.popleft() # извлекаем часть из списка неудачных
            mirror.download(new_part) # запускаем скачивание
            self.parts_in_progress.append(new_part) # добавляем задание в список активных
        elif self.offset < self.file_size or self.file_size == 0: # если ещё не скачано до конца
            mirror.download(self.offset) # запускаем скачивание с текущего смещения
            self.parts_in_progress.append(self.offset) # добавляем задание в список активных
            self.offset += self.block_size # увеличиваем текущее смещение на размер блока

    def download(self):

        """
        Выполняет скачивание файла.

        """
        with self.outfile: # открываем выходной файл
            while self.file_size == 0 or self.written_bytes < self.file_size: # пока скачивание не завершено
                self.wait_connections() # ждём готовность зеркал (соединения, раздача заданий)
                while True:
                    try:
                        # проверяем состояние очереди, ели она пуста - выбросится исключение
                        part = self.data_queue.get(False, 0.01)
                        try:
                            # выполняем действия, связанные с частью
                            part.process(self)
                        finally:
                            needle_parts = self.parts_in_progress.copy() # части, которые недокачаны
                            needle_parts.extend(self.failed_parts) # добавляем неудачные части
                            self.context.update(self.offset, self.written_bytes, needle_parts) # сохраняем контекст
                    except queue.Empty: # если очередь пуста
                        break # выходим из цикла (переходим к ожиданию зеркал)

            # цикл для завершения работы
            for mirror in self.mirrors.values():
                mirror.join() # ждём завершения потоков
                mirror.close() # закрываем соединение
            self.console.out() # выводим пустую строку в консоль
        self.context.delete() # удаляем файл контекста

    def del_active_part(self, offset):

        """
        Удаляет активное задание из списка.

        :offset: смещение части относительно начала файла, тип int

        """
        self.parts_in_progress.remove(offset)

    def add_failed_parts(self, offset):

        """
        Добавляет неудачное задание в список.

        :offset: смещение части относительно начала файла, тип int

        """
        self.del_active_part(offset) # неудачное задание более неактивно
        self.failed_parts.append(offset)

    def delete_mirror(self, name):

        """
        Удаляет зеркало.

        :name: имя зеркала, тип str

        """
        mirror = self.mirrors[name]
        mirror.join()
        del self.mirrors[name]
        # вместе с зеркалом обязательно создаётся соответствующий элемент в gotten_sizes
        # его тоже необходимо удалить
        del self.gotten_sizes[name]

    def set_file_size(self, part):

        """
        Устанавливает размер файла при первом вызове и
        резервирует место на HDD. При послебующих вызовах
        сравнивает с ним размеры файлов на других зеркалах.

        :part: часть, взятая из очереди, тип HeadPart

        """
        if self.file_size == 0: # первый вызов
            self.file_size = part.file_size
            self.console.progressbar.total = self.file_size
            self.outfile.seek(self.file_size - 1) # перемещаемся к последнему байту
            self.outfile.write(b'\x00') # пишем ноль
            self.console.out(downloading_msg.format(self.filename, self.file_size, calc_units(self.file_size)))
        elif self.file_size != part.file_size: # запуск не первый и размер файла отличается
            # значит файл "битый" или вообще другой
            # выводим сообщение об ошибке
            self.console.error(filesize_error.format(part.name, part.file_size, part.file_size))
            self.delete_mirror(part.name) # удаляем зеркало
            return # XXX заменить на исключение
        mirror = self.mirrors[part.name]
        mirror.file_size = part.file_size # зеркалу также сообщаем имя файла
        mirror.ready = True # зеркало готово качать следующую часть
        mirror.connect_message() # выводим сообщение о подключении

    def redirect(self, part):

        """
        Удаляет старое зеркало и создаёт новое
        с адресом из редиректа.

        :part: часть, взятая из очереди, тип RedirectPart

        """
        self.delete_mirror(part.name)
        mirror = Mirror.create(part.location, self.block_size, self.timeout) # XXX: переписать через Manager.create_mirror
        self.mirrors[mirror.name] = mirror # XXX: переписать через Manager.create_mirror
        self.gotten_sizes[mirror.name] = 0 # XXX: переписать через Manager.create_mirror
        self.console.out(redirect_msg.format(part.name, part.location.url))

    def error(self, part):

        """
        Выполняется в случае ошибки.

        :part: часть, взятая из очереди, тип Part

        """
        if part.status == 0: # ошибка соединения с сервером
            msg = connection_error.format(part.name)
        elif part.status == 200: # зеркало не поддерживает скачивание по частям
            msg = no_partial_error.format(part.name)
        else: # другая ошибка (вероятно HTTP 4xx/5xx)
            msg = http_error.format(part.status)
        self.console.error(msg)
        self.delete_mirror(part.name) # удаляем зеркало
        if not self.mirrors: # если не осталось зеркал
            # дальше качать невозможно, завершаем работу
            raise FatalError(download_impossible_error)

    def write_data(self, part):

        """
        Пишет данные в файл.

        :part: часть, взятая из очереди, тип DataPart

        """
        # обновляем кол-во скачанных байт с зеркала
        self.gotten_sizes[part.name] = part.gotten_size
        # перемещаемся к началу части + смещение внутри части
        self.outfile.seek(part.offset + part.fragment_offset)
        self.outfile.write(part.data) # пишем данные
        # прогресс равен ранее записанным данным + сумме скачаного
        # активными заданиями
        progress = self.written_bytes + sum(self.gotten_sizes.values())
        # обновляем прогресс в консоли, для вычисления скорости передаём
        # только скачанное за текущий сеанс
        self.console.progress(progress, progress - self.old_progress)

    def task_done(self, part):

        """
        Выполняется при обработке последнего фрагмента задания.

        :part: часть, взятая из очереди, тип FinalDataPart

        """
        self.del_active_part(part.offset) # часть более неактивна
        self.write_data(part) # пишем данные
        self.written_bytes += part.gotten_size # увеличиваем число записанных байт
        self.gotten_sizes[part.name] = 0 # обнуляем кол-во полученных байт активным зеркалом
        mirror = self.mirrors[part.name]
        mirror.done() # помечаем зеркало завершившим скачивание



# Класс контекста

@singleton
class Context:

    """
    Сохраняет в специальный файл и загружает из него в случае
    прерывания скачивания информацию о прогрессе скачивания,
    что позволяет продолжить качать с места рассоединения.

    Формат файла:

    Заголовок:
        смещение, тип int
        записанные байты, тип int
        кол-во неудачных частей, тип int
    Тело:
        список неудачных частей, тип int
    

    """
    def __init__(self, filename):

        """
        :filename: имя скачиваемого файла, тип str

        """
        self.filename = filename + '.mget' # имя файла контекста
        self.failed_parts = [] # части, которые всё ещё над оскачать
        self.offset = 0 # текущее смещение
        self.written_bytes = 0 # количество записанных байт
        try:
            with open(self.filename, 'rb') as f: # открываем файл контекста
                data = f.read(struct.calcsize('NNq')) # читаем заголовок
                # и распаковываем его
                self.offset, self.written_bytes, failed_parts_len = struct.unpack('NNq', data)
                # если есть неудачные части
                if failed_parts_len > 0:
                    data = f.read(struct.calcsize('N' * failed_parts_len)) # читаем их
                    # и распаковываем
                    self.failed_parts = struct.unpack('N' * failed_parts_len, data)
        except: # ошибка открытия файла
            self.exists = False # контекста не существует (прерывания скачивания не было)
        else: # ошибок не было
            self.exists = True # контекст существует (ранее скачивание было прервано)

    def modified(self, offset, written_bytes, failed_parts):

        """
        Проверяет, изменилось ли состояние процесса скачивания.

        :offset: текущее смещение, тип int
        :written_bytes: количество записанных байт, тип int
        :failed_parts: неудачные части, тип sequence (int)

        """
        # возвращаем True если хоть что-то отличается от контекста
        return self.offset != offset or self.written_bytes != written_bytes or set(self.failed_parts) ^ set(failed_parts)

    def update(self, offset, written_bytes, failed_parts):

        """
        Обновляет контекст.

        :offset: текущее смещение, тип int
        :written_bytes: количество записанных байт, тип int
        :failed_parts: неудачные части, тип sequence (int)

        """
        # если изменений нет
        if not self.modified(offset, written_bytes, failed_parts):
            # просто выходим
            return
        # иначе присваеваем новые значения
        self.offset = offset
        self.written_bytes = written_bytes
        self.failed_parts = failed_parts
        failed_parts_len = len(self.failed_parts)
        format = 'NNq' + 'N' * failed_parts_len # определяем формат в зависимости от количества неудачных частей
        # запаковываем даныне
        data = struct.pack(format, self.offset, self.written_bytes, failed_parts_len, *self.failed_parts)
        # пишем в файл
        with open(self.filename, 'wb') as f:
            f.write(data)

    def reset(self):

        """
        Обнуляет контекст.

        """
        self.update(0, 0, [])

    def delete(self):

        """
        Удаляет файл контекста.

        """
        try:
            os.remove(self.filename)
        except:
            pass # ошибки просто игнорируем, скорее всего файл не существует




# Класс парсера командной строки

class CommandLine:

    """
    Выбирает параметры командной строки и выполянет соответствующие действия.

    """
    def __init__(self, argv):

        """
        :argv: список параметров, тип sequence (str)

        """
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
        self.console.out(textwrap.dedent(help_msg.format(os.path.basename(__file__))))
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
            raise CommandLineError(wrong_commandline_error + wrong_param_format_error.format('block size', block_size))
        self.block_size = int(matches.group(1)) # присваиваем размеру блока числовуч часть параметра
        if matches.group(2): # если указана размерность
            if matches.group(2).lower() == 'k': # если k или K
                self.block_size *= 2**10 # значит в килобайты
            elif matches.group(2).lower() == 'm': # если m или M
                self.block_size *= 2**20 # значит мегабайты
            else:
                # иначе - ошибка командной строки
                raise CommandLineError(wrong_commandline_error + wrong_param_format_error.format('block size', block_size))

    def parse_timeout(self, timeout):

        """
        Парсит параметр времени ожидания.

        :timeout: значение параметра, тип str

        """
        if not timeout.isdigit(): # если параметр не число
            # ошибка командной строки
            raise CommandLineError(wrong_commandline_error + wrong_param_format_error.format('timeout', timeout))
        self.timeout = int(timeout) # присваиваем таймаут

    def parse_links_file(self, urls_file):

        """
        Парсит параметр файла со списком ссылок.

        :urls_file: значение параметра (имя файла), тип str

        """
        try:
            urls = []
            with open(urls_file, 'r') as links: # пробуем открыть файл
                for link in links: # каждую строку из файла
                    urls.append(link.strip('\r\n')) # добавляем в список, отбросив символы перевода строки
            self.urls.extend(urls) # дополняем список ссылок
        except FileNotFoundError: # файл не найден
            raise CommandLineError(file_not_found_error.format(urls_file))
        except PermissionError: # недостаточно прав
            raise CommandLineError(file_permission_error.format(urls_file))
        except UnicodeDecodeError: # неверная структура файла
            raise CommandLineError(file_is_corrupted_error.format(urls_file))
     
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
            elif arg == '-b':
                # парсим размер блока, передав ему следующий элемент
                self.parse_block_size(next(args_iterator))
            elif arg == '-T':
                # парсим время ожидания, передав ему следующий элемент
                self.parse_timeout(next(args_iterator))
            elif arg == '-l':
                # парсим файл со списком ссылок, передав ему следующий элемент
                self.parse_links_file(next(args_iterator))
            elif arg == '-o':
                # парсим имя выходного файла, передав ему следующий элемент
                self.parse_out_file(next(args_iterator))
            elif arg.startswith('--block-size='):
                # парсим размер блока, передав ему длинный параметр
                self.parse_block_size(self.parse_long_arg(arg))
            elif arg.startswith('--timeout='):
                # парсим время ожидания, передав ему длинный параметр
                self.parse_timeout(self.parse_long_arg(arg))
            elif arg.startswith('--links-file='):
                # парсим файл со списком ссылок, передав ему длинный параметр
                self.parse_links_file(self.parse_long_arg(arg))
            elif arg.startswith('--out-file='):
                # парсим имя выходного файла, передав ему длинный параметр
                self.parse_out_file(self.parse_long_arg(arg))
            elif self.url_re.match(arg): # параметр соответствует шаблону URL
                self.urls.append(arg) # добавляем его в список URL
            else:
                # если параметр не соответствует ничему вышеперечисленному
                # выводим предупреждение про неизвестный аргумент и пропускаем его
                self.console.warning(unknown_arg_warning.format(arg))

        # создадим из ссылок объекты URL,
        # предварительно отфильтровав их по шаблону
        self.urls = map(lambda url: URL(url), filter(lambda url: self.url_re.match(url), self.urls))




# выполняется при запуске сценария как самостоятельной программы

if __name__ == '__main__':

    console = Console() # создадим объект консоли
    console.out(start_msg.format(VERSION)) # выведем информацию о себе

    try:
        cl = CommandLine(sys.argv)
        cl.parse() # парсим командную строку
        manager = Manager(cl.urls, cl.block_size, cl.filename, cl.timeout) # создаём менеджер
        manager.download() # запускаем скачивание
    except CancelError as e: # если пользователь отменил скачивание
        console.out(str(e))
    except Exception as e: # любая другая ошибка
        console.error(str(e))
    
