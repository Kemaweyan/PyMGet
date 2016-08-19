#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, platform, time
from messages import Messages
from utils import *

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
        if platform.system() == 'Windows':
            self.WIDTH -= 1 # в Windows надо уменьшить на 1, иначе перебрасывает на новую строку

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
        self.lang = Messages()

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
            self.out('\n' + self.lang.common.error + text, end)

    def warning(self, text, end='\n'):

        """
        Выводит предупреждение. 

        :text: текст, котоорый будет выведен, тип str
        :end: завершающий символ, по-умолчанию перевод строки, тип str

        """
        if text:
            self.out('\n' + self.lang.common.warning + text, end)

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
