#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import locale
import xml.etree.ElementTree as ET
from utils import singleton
from errors import FatalError

class LangParser:

    def __init__(self, lang):
        tree = ET.parse('i18n/{}.xml'.format(lang))
        self.root = tree.getroot()

    def get_messages(self, section_name):
        section = self.root.find(section_name)
        if not section:
            raise StopIteration
        for msg in section.findall('msg'):
            name = msg.get('name')
            text = msg.text
            yield name, text

class Language:

    def __init__(self, lang):
        parser = LangParser(lang)
        self.common = self.fill_dict(parser.get_messages('common'))
        self.messages = self.fill_dict(parser.get_messages('messages'))
        self.warnings = self.fill_dict(parser.get_messages('warnings'))
        self.errors = self.fill_dict(parser.get_messages('errors'))
        self.questions = self.fill_dict(parser.get_messages('questions'))

    @staticmethod
    def fill_dict(items):
        return {name: text for (name, text) in items}

class MsgList:

    def __init__(self, system, default):
        self.system = system
        self.default = default

    def __getattr__(self, name):
        try:
            return self.system[name]
        except:
            try:
                return self.default[name]
            except:
                return ''

@singleton
class Messages:

    default_lang = 'en'

    def __init__(self):
        system = None
        default = self.load_lang(self.default_lang)
        if not default:
            raise FatalError('Default language not found')

        sys_locale = locale.getlocale()
        lang = sys_locale[0].split('_')[0]
        if lang != self.default_lang:
            system = self.load_lang(lang)
        if not system:
            system = default

        self.common = MsgList(system.common, default.common)
        self.message = MsgList(system.messages, default.messages)
        self.warning = MsgList(system.warnings, default.warnings)
        self.error = MsgList(system.errors, default.errors)
        self.question = MsgList(system.questions, default.questions)

    @staticmethod
    def load_lang(lang):
        try:
            return Language(lang)
        except:
            return None
