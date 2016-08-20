#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re, platform
import threading
from http import client
import ftplib
from abc import ABCMeta, abstractmethod, abstractproperty

from pymget.task_info import *
from pymget.data_queue import DataQueue

VERSION = '1.34'

# Классы для работы с сетью

class URL:

    """
    Класс адреса URL. Поддерживаемые протоколы: HTTP/HTTPS/FTP

    """
    url_re = re.compile('^(https?|ftp)://([\w\.-]+(?::\d+)?)((?:/(.+?))?/([^\/]+)?)?$', re.I)

    def __init__(self, url):

        """
        :url: строка url, тип str

        """
        self.url = url

        # регулярное выражение проверяет правильность URL и разбивает её на составные части:
        # протокол, хост (с портом), путь к файлу, имя файла
        # путь в файлу + имя файла также объединяется в запрос
        matches = self.url_re.match(url)
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
    user_agent = 'PyMGet/{} ({} {}, {})'.format(VERSION, platform.uname().system, platform.uname().machine, platform.uname().release)

    def __init__(self):
        threading.Thread.__init__(self)
        self.data_queue = DataQueue()
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
        Помещает объект типа TaskInfo в очередь менеджера.

        """
        try:
            # объект info создаёт объект класса-наследника
            info = self.connect()
        except:
            # в случае ошибки создаёт объект типа TaskHeadError
            info = TaskHeadError(self.url.host, 0)
        finally:
            self.data_queue.put(info) # в конце помещаем часть в очередь
            self.ready.set() # и помечаем поток завершенным

    @abstractmethod
    def connect(self): pass # метод, выполняющий подключение, должен быть реализован в унаследованных классах. Возвращает объект типа TaskInfo

class HTTXThread(ConnectionThread):

    """
    Базовый класс для HTTP и HTTPS протоколов

    """
    def redirect(self, location, status):
        
        """
        Создаёт часть для перенаправления запроса.

        """
        url = ''
        # строка location может быть как полным адресом, так и частичным.
        # Кроме того, частичный адрес может начинаться с /, т.е. с корневого каталога сервера,
        # или же быть относительным текущего пути.
        # Поэтому location разбиваем на 3 части:
        # 1) хост с указанием протокола http(s)://site.com
        # 2) остальная часть ссылки (включая первый / если он есть)
        # 3) начальный / если есть
        redirect_re = re.compile('^(https?://[^/]+)?((/)?(?:.*))$', re.I)
        matches = redirect_re.match(location)
        if not matches:
            return TaskHeadError(self.url.host, status)
        if matches.group(1): # если location содержит хост
            url = location # значит путь полный, перенаправляем на него
        elif matches.group(3): # если location начинаеся с /
            # значит путь задан относительн окорня сервера
            # добавляем путь к хосту
            url = '{}://{}{}'.format(self.url.protocol, self.url.host, matches.group(2))
        else: # путь задан относительно текущего каталога
            # выделяем из запроса путь
            path = self.url.request.rsplit('/', 1)[0] + '/'
            # добавляем новый путь к текущему каталогу, а также хосту
            url = '{}://{}{}'.format(self.url.protocol, self.url.host, path + matches.group(2))
        return TaskRedirect(self.url.host, status, URL(url))

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
            return self.redirect(location, response.status)

        if response.status != 200: # ошибка HTTP(S)
            return TaskHeadError(self.url.host, response.status)

        file_size = int(response.getheader('Content-Length'))
        info = TaskHeadData(self.url.host, response.status, file_size)
        response.close()
        return info

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
        return TaskHeadData(self.url.host, 200, file_size) # устанавливаем код 200 для совместимости с HTTP




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
        self.url = url
        self.conn = conn
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
        headers = {'User-Agent': self.user_agent, 'Refferer': '{}://{}/'.format(self.url.protocol, self.url.host), 
                    'Range': 'bytes={}-{}'.format(self.offset, self.offset + self.block_size - 1)}
        status = 0 # изначально статус 0, что значит ошибку соединения
        try:
            self.conn.request('GET', self.url.request, headers=headers)
            response = self.conn.getresponse()
            # сервер не поддерживает скачивание по частям - ошибка
            if response.status != 206:
                status = response.status
                raise MirrorError
            part_size = int(response.getheader('Content-Length')) # столько байт сервер передал клиенту
            data = b'' # буфер для данных
            # цикл пока не получены все переданные байты
            while part_size > len(data):
                data_fragment = response.read(self.FRAGMENT_SIZE)
                data += data_fragment # добаляем данные в буффер
                # добавляем в очередь часть прогресса
                info = TaskProgress(self.url.host, response.status, len(data))
                self.data_queue.put(info)
            # после завершения цикла создаём часть с данными
            info = TaskData(self.url.host, response.status, self.offset, data)
            response.close()
        except:
            # в случае ошибки помещаем в очередь часть со статусом
            info = TaskError(self.url.host, status, self.offset)
        finally:
            self.data_queue.put(info) # отправляем часть с данными или ошибкой
            self.ready.set() # в конце помечаем поток завершенным

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
        self.file_size = file_size

    def run(self):

        """
        Функция скачивания, выполняется в отдельном потоке

        """
        data = b'' # буфер для данных
        try:
            sock = self.conn.transfercmd('RETR ' + self.url.filename, self.offset)
            # цикл пока получено байт меньше, чем размер блока
            # однако, последний блок может быть меньше этого размера, т.к. размер файла не обязательно кратен размеру блоку
            while len(data) < self.block_size:
                # получаем данные, но не более размера фрагмента 
                # и кол-ва данных, оставшихся до целого блока
                data_fragment = sock.recv(min(self.block_size - len(data), self.FRAGMENT_SIZE))
                if not data_fragment: # в случае отсутствия данных - ошибка
                    raise MirrorError
                data += data_fragment # добавляем данные в буфер
                info = TaskProgress(self.url.host, 206, len(data))
                self.data_queue.put(info)
                # считаем блок завершенным, если получено байт больше или равно размеру блоку
                # или если достингнут конец файла
                if self.block_size - len(data) <= 0 or self.file_size - self.offset - len(data) <= 0:
                    break
            # после завершения цикла создаём часть с данными
            info = TaskData(self.url.host, 206, self.offset, data)
            sock.close()
        except:
            # в случае ошибки создаём часть с кодом 0, т.е. ошибка подключения
            info = TaskError(self.url.host, 0, self.offset)
        finally:
            self.conn.close()
            self.data_queue.put(info) # помещаем в очередь часть с данными или ошибкой
            self.ready.set() # в конце помечаем поток завершенным
