#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractproperty

from pymget.console import *
from pymget.messages import Messages
from pymget.networking import *

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
        self.lang = Messages()
        self.console = Console()
        self.url = url
        self.block_size = block_size
        self.timeout = timeout
        self.file_size = 0 # размер файла определяется после подключения
        self.task_progress = 0 # скачано в текущем задании
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
        self.task_progress = 0 # задание завершено, очищаем кол-во скачаного
        self.ready = True # зеркало готово качать очередную часть

    def connect_message(self):

        """
        Выводит сообщение о соединении с сервером

        """
        self.console.out(self.lang.message.connected.format(self.url.host))

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

class HTTXMirror(Mirror):

    """
    Абстрактный базовый класс для HTTP и HTTPS зеркал.

    """
    @property
    def download_thread(self):

        """
        Возвращает класс потока скачивания

        """
        return HTTXDownloadThread

class HTTPMirror(HTTXMirror):

    """
    Класс зеркала HTTP

    """
    @property
    def connection_thread(self):

        """
        Возвращает класс потока подключения

        """
        return HTTPThread

class HTTPSMirror(HTTXMirror):

    """
    Класс зеркала HTTPS

    """
    @property
    def connection_thread(self):

        """
        Возвращает класс потока подключения

        """
        return HTTPSThread

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
        Mirror.done(self)
        self.ready = False # в отличие от HTTX FTP сразу не готово качать следующую часть
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
