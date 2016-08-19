#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import struct

from console import *
from messages import Messages
from errors import FileError, CancelError

# Класс выходного файла

class OutputFile:

    """
    Класс выходного файла. Поддерживает менеджер контекста.

    seek: перемещает указатель файла
    write: пишет в файл

    """
    def __init__(self, filename, path):

        """
        :filename: имя файла на сервере, тип str
        :path: путь для сохранения файла, тип str

        """
        self.lang = Messages()
        self.console = Console()
        if not path: # пользователь не указал путь
            self.filename = filename # имя файла берём с сервера
            self.path = '' # путь пуст
            self.fullpath = filename # полный путь - просто имя файла
        elif os.path.isdir(path): # если пользователь указал путь к папке
            self.filename = filename # имя файла берём с сервера
            self.path = path # используем указанный пользователем путь
            self.fullpath = path.rstrip(os.sep) + os.sep + filename # полный путь для сохранения
        else: # если указанный пользователем путь - не папка
            self.filename = os.path.basename(path) # извлекаем из пути имя файла
            self.path = os.path.dirname(path) # и путь к файлу 
            self.fullpath = path # полный путь указан пользователем
            self.check_folders() # проверяем существование папок
        self.context = Context(self.fullpath)
        self.file = self.open_file(self.context.exists)

    def check_folders(self):
        
        """
        Проверяет существование каталогов в указанном пути.
        Если папка не существует - запрашивает создание.

        """
        if os.path.isdir(self.path): # папка существует
            return # ничего не делаем
        folders = self.path.split(os.sep) # разбиваем путь на составляющие
        for i in range(len(folders)):
            # для каждой подпапки в пути
            path = os.sep.join(folders[:i + 1])
            if not path: # если путь пустой
                # значит split "съел" первый /
                path = os.sep # и первая папка - корень
            if os.path.isdir(path): # если папка существует
                continue # поропускаем
            if os.path.isfile(path): # если это файл
                raise FileError(self.lang.error.dir_is_file.format(path)) # ошибка пути
            if not self.console.ask(self.lang.question.create_dir.format(path), True): # запрашиваем создание
                # и если пользователь ответил "нет" 
                raise CancelError(self.lang.message.cancel) # отмена скачивания
            try:
                os.mkdir(path) # создаём папку
            except:
                # не удалось создать папку
                raise FileError(self.lang.error.unable_create_dir.format(path, self.lang.error.permission_denied))

    def open_file(self, context_exists):

        """
        Открывает файл для записи или обновления.
        Проверяет наличие контекста (файл *.mget): если контекста нет - создаёт новый файл или запрашивает перезапись существующего.
        Если контекст есть, то открывает файл для обновления, если файла нет - запрашивает создание файла.

        :context_exists: флаг сущестования контекста, тип bool

        """
        if context_exists: # если контекст существует
            try:
                return open(self.fullpath, 'rb+') # открываем файл для обновления
            except:
                # в случае ошибки
                if os.path.isfile(self.fullpath): # если файл существует
                    raise FileError(self.lang.error.unable_open_file.format(self.fullpath, self.lang.error.permission_denied)) # ошибка доступа
                # если не существует
                if not self.console.ask(self.lang.question.create_file.format(self.fullpath), True): # запрашиваем создание
                    # и если пользователь ответил "нет" 
                    raise CancelError(self.lang.message.cancel) # отмена скачивания
                self.context.reset() # сбрасываем контекст
                return self.open_file(False) # и вызываем этот-же метод без контекста
        else: # если контекста нет         
            if os.path.isfile(self.fullpath): # если файл существует
                if not self.console.ask(self.lang.question.rewrite_file.format(self.fullpath), False): # запрашиваем пересоздание
                    # если пользователь ответил "нет"
                    raise CancelError(self.lang.message.cancel) # отмена скачивания
            try:
                return open(self.fullpath, 'wb') # открываем файл для записи (существующий файл будет перезаписан с нуля)
            except:
                # в случае ошибки - невозможно здать файл
                raise FileError(self.lang.error.unable_create_file.format(self.fullpath, self.lang.error.permission_denied))

    def __enter__(self):

        """
        Медод, вызываемый менеджером контекста при входе.
        Возвращает ссылку на себя, внутри оператора with будут доступны методы seek и write

        """
        return self 

    def __exit__(self, exception_type, exception_value, traceback):

        """
        Медод, вызываемый менеджером контекста при выходе.
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
            raise FileError(self.lang.error.unable_write.format(self.filename))

    def write(self, data):

        """
        Медод данных записи в файл. 

        :data: данные, которые будут записаны, тип sequence

        """
        try:
            return self.file.write(data) # пишем в файл
        except:
            # в случае неудачи - ошибка записи
            raise FileError(self.lang.error.unable_write.format(self.filename))



# Класс контекста

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
        self.filename = filename + '.pymget' # имя файла контекста
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
