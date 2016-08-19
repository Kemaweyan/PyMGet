#!/usr/bin/env python3
# -*- coding: utf-8 -*-


import os, queue
from collections import deque

from messages import Messages
from errors import FatalError, URLError, FileSizeError
from console import Console
from outfile import OutputFile
from utils import calc_units
from mirrors import Mirror
from data_queue import DataQueue

# Класс менеджера скачивания

class Manager:

    """
    Класс менеджера скачивания. Создаёт зеркала из списка URL, подключается к ним,
    раздаёт задания и обрабатывает результаты
    
    """
    def __init__(self, urls, block_size, filename, timeout):

        """
        :urls: список URL, тип iterable <URL>
        :block_size: размер блока, тип int
        :filename: имя файла, указанное пользователем, тип str
        :timeout: время ожидания ответа сервера, тип float

        """
        self.lang = Messages()
        self.console = Console()
        self.data_queue = DataQueue()
        self.block_size = block_size
        self.timeout = timeout
        self.server_filename = '' # имя файла на серверах, пока неизвестно
        self.mirrors = {} # зеркала
        for url in urls:
            self.create_mirror(url) # пробуем создать зеркало
        if not self.mirrors: # если нет зеркал
            raise FatalError(self.lang.error.no_mirrors) # критическая ошибка
        if self.server_filename == '': # если имя файла не определилось
            self.server_filename = 'out' # присваиваем имя out
        self.outfile = OutputFile(self.server_filename, filename) # создаём объект выходного файла
        self.context = self.outfile.context # сохраняем объект контекста, связанный с файлом
        self.offset = self.context.offset # текущее смещение равно смещению из контекста, продолжаем качать дальше
        self.written_bytes = self.context.written_bytes # кол-во записанных байт равно кол-ву записанных байт из контекста
        self.old_progress = self.written_bytes # сохраняем прогресс предыдущих сессий (необходимо для корректного вычисления скорости)
        self.failed_parts = deque(self.context.failed_parts) # загружаем из контекста список неудачных частей
        self.file_size = 0 # размер файла равен нулю, определится после соединения
        self.parts_in_progress = [] # список активных заданий

    def create_mirror(self, url):

        """
        Создаёт зеркало и добавляет его в список.
        В случае неудачи выводит сообщение об ошибке.

        :url: объект URL, описывающий адрес для скачивания, тип URL

        """
        try:
            mirror = Mirror.create(url, self.block_size, self.timeout)
            # если имя файла не проходит проверку
            if not self.check_filename(mirror):
                raise URLError(mirror.filename) # ошибка адреса
        except URLError as e: # ошибка адреса
            self.console.error(str(e)) # выводим сообщение об ошибке
        else:
            self.mirrors[url.host] = mirror # добавляем зеркало в список

    def check_filename(self, mirror):

        """
        Проверяет имя файла на соответствие другим.

        :mirror: объект зеркала, тип Mirror

        """
        if self.server_filename == '': # если имя файла ещё не определено
            if mirror.filename == '': # если если зеркало не смогло определить имя файла
                self.console.warning(self.lang.warning.empty_filename.format(mirror.name)) # выводим предупреждение что имя пустое
                return self.console.ask(self.lang.question.anyway_download.format(mirror.name), False) # запрашиваем подтверждение на использование зеркала
            self.server_filename = mirror.filename # сохраняем имя файла
            return True # проверка пройдена
        if os.path.basename(self.server_filename) == mirror.filename: # если имя совпадает
            return True # проверка пройдена
        # иначе имя отдличается
        self.console.warning(self.lang.warning.other_filename.format(mirror.name, self.server_filename)) # выводим предупреждение
        return self.console.ask(self.lang.question.anyway_download.format(mirror.name), False) # запрашиваем подтверждение на использование зеркала

    def wait_connections(self):

        """
        Ожидает завершения потоков, в случае необходимости
        запускает подключение и раздаёт задания.

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
            self.console.out('\n' + self.lang.message.downloading.format(self.outfile.filename, self.file_size, calc_units(self.file_size)) + '\n')
        elif self.file_size != part.file_size: # запуск не первый и размер файла отличается
            raise FileSizeError # значит файл "битый" или вообще другой
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
        self.create_mirror(part.location)
        self.console.out('\n' + self.lang.message.redirect.format(part.name, part.location.url))

    def do_error(self, part):

        """
        Выполняется в случае ошибки.

        :part: часть, взятая из очереди, тип Part

        """
        if part.status == 0: # ошибка соединения с сервером
            msg = self.lang.error.unable_connect.format(part.name)
        elif part.status == 200: # зеркало не поддерживает скачивание по частям
            msg = self.lang.error.no_partial.format(part.name)
        else: # другая ошибка (вероятно HTTP 4xx/5xx)
            msg = self.lang.error.wrong_http_code.format(part.status)
        self.console.error(msg)
        self.delete_mirror(part.name) # удаляем зеркало
        if not self.mirrors: # если не осталось зеркал
            # дальше качать невозможно, завершаем работу
            raise FatalError(self.lang.error.unable_download)

    def set_progress(self, part):

        """
        Обновляет прогресс скачивания файла.

        :part: часть, взятая из очереди, тип ProgressPart

        """
        # обновляем проресс соответствующего зеркала
        mirror = self.mirrors[part.name]
        mirror.task_progress = part.task_progress
        # прогресс равен ранее записанным данным + сумме скачаного
        # активными заданиями
        progress = self.written_bytes + sum(map(lambda m: m.task_progress, self.mirrors.values()))
        # обновляем прогресс в консоли, для вычисления скорости передаём
        # только скачанное за текущий сеанс
        self.console.progress(progress, progress - self.old_progress)

    def write_data(self, part):

        """
        Пишет данные в файл, освобождает зеркало.

        :part: часть, взятая из очереди, тип DataPart

        """
        self.del_active_part(part.offset) # часть более неактивна
        self.outfile.seek(part.offset) # перемещаемся к началу части
        self.outfile.write(part.data) # пишем данные
        self.written_bytes += len(part.data) # увеличиваем число записанных байт
        mirror = self.mirrors[part.name]
        mirror.done() # помечаем зеркало завершившим скачивание
