#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractmethod

from console import Console
from errors import FileSizeError

# Классы частей (объектов, помещаемых потоками в очередь)

class TaskInfo(metaclass=ABCMeta):

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

class TaskHeadData(TaskInfo):

    """
    Заголовочная часть, содержит информацию о файле.
    
    """
    def __init__(self, name, status, file_size):

        """
        :name: имя зеркала, которое отправило часть, тип str
        :status: статус выполнения операции потоком, тип int
        :file_size: размер файла, тип int

        """
        TaskInfo.__init__(self, name, status)
        self.file_size = file_size

    def process(self, manager):
        """
        Выполняется в случае корректного соединения с сервером

        """
        try:
            manager.set_file_size(self) # указывает размер файла менеджеру
        except FileSizeError:
            self.console.error(filesize_error.format(self.name, self.file_size, manager.file_size))
            manager.delete_mirror(self.name) # удаляем зеркало

class TaskRedirect(TaskInfo):

    """
    Часть перенаправления, содержит новую ссылку.
    
    """
    def __init__(self, name, status, location):

        """
        :name: имя зеркала, которое отправило часть, тип str
        :status: статус выполнения операции потоком, тип int
        :location: ссылка на новое место, тип URL

        """
        TaskInfo.__init__(self, name, status)
        self.location = location

    def process(self, manager):
        """
        Выполняется в случае перенаправления на другой адрес

        """
        manager.redirect(self) # перенаправляем

class TaskProgress(TaskInfo):

    """
    Часть, сообщающая основному потоку прогресс скачивания.
    
    """
    def __init__(self, name, status, task_progress):

        """
        :name: имя зеркала, которое отправило часть, тип str
        :status: статус выполнения операции потоком, тип int
        ：task_progress： количество данных, полученных за данный сеанс, тип int

        """
        TaskInfo.__init__(self, name, status)
        self.task_progress = task_progress

    def process(self, manager):

        """
        Устанавливает прогресс текущего задания.

        """
        manager.set_progress(self) # помечаем задание выполненым

class TaskHeadError(TaskInfo):

    """
    Часть ошибки подключения.
    
    """
    def process(self, manager):
        """
        Выполняется в случае ошибки подключения

        """
        manager.do_error(self) # обрабатываем ошибку

class TaskError(TaskHeadError):

    """
    Часть ошибки скачивания.
    
    """
    def __init__(self, name, status, offset):

        """
        :name: имя зеркала, которое отправило часть, тип str
        :status: статус выполнения операции потоком, тип int
        :offset: смещение в задании, тип int

        """
        TaskHeadError.__init__(self, name, status)
        self.offset = offset

    def process(self, manager):
        """
        Выполняется в случае ошибки скачивания

        """
        manager.add_failed_parts(self.offset) # добавляем смещение части в список невыполненых
        TaskHeadError.process(self, manager) # обрабатываем ошибку

class TaskData(TaskError):

    """
    Часть с данными.
    
    """
    def __init__(self, name, status, offset, data):

        """
        :name: имя зеркала, которое отправило часть, тип str
        :status: статус выполнения операции потоком, тип int
        :offset: смещение в задании, тип int
        :data: данные, тип sequence

        """
        TaskError.__init__(self, name, status, offset)
        self.data = data

    def process(self, manager):

        """
        Выполняется при получении данных

        """
        manager.write_data(self) # пишем данные
