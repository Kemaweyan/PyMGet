#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, locale
import xml.etree.ElementTree as ET

from pymget.utils import singleton
from pymget.errors import FatalError

class LangParser:

    """
    Parses localization XML file from i18n folder.

    XML file structure:

    Root tag:

        <language>

    Sections (child tags of <language>):

        <common>    contains common strings used by Console object
        <messages>  contains strings for information messages
        <errors>    contains strings for error messages
        <warnings>  contains strings for warning messages
        <questions> contains strings for questions

    Each string constant format:

        <msg name='NAME'>TEXT</msg>

        NAME is a name of constant used by program
        TEXT is a text viewed instead of the constant

    """
    def __init__(self, lang):

        """
        :lang: name of the language to parse, type str

        """
        # get path to this module
        path = os.path.dirname(os.path.realpath(__file__))
        # add to the path path to language XML file
        fullpath = os.sep.join([path, 'i18n/{}.xml'.format(lang)])
        tree = ET.parse(fullpath) # parse XML
        self.root = tree.getroot() # get root tag object

    def get_messages(self, section_name):

        """
        Returns generator object that generates
        tuples (name, text) where 'name' is a name of
        string constant and 'text' is a text of it.

        :section_name: a name of the section to read, type str

        """
        # find requested section
        section = self.root.find(section_name)
        # if there is no section with this name or
        # if the section is empty, then stop iteration
        if not section:
            raise StopIteration
        # fing all msg tags in the section
        for msg in section.findall('msg'):
            name = msg.get('name') # a name of the constant
            text = msg.text # its text
            yield name, text

class Language:

    """
    Creates and fill dictionaries with
    string constants for each section
    using LangParser object.

    """
    def __init__(self, lang):

        """
        :lang: a anme of the language, type str

        """
        parser = LangParser(lang) # create parser object
        # dictionaries for sections
        self.common = self.fill_dict(parser.get_messages('common'))
        self.messages = self.fill_dict(parser.get_messages('messages'))
        self.warnings = self.fill_dict(parser.get_messages('warnings'))
        self.errors = self.fill_dict(parser.get_messages('errors'))
        self.questions = self.fill_dict(parser.get_messages('questions'))

    @staticmethod
    def fill_dict(items):

        """
        Creates and fills a dictionary using
        gotten iterable object 'items'

        :items: iterable object that generates tuples (name, text)

        """
        return {name: text for (name, text) in items}

class MsgList:

    """
    Proxy object to access dictionaries
    with system localization and default
    language. It returns string constant
    from default language it there is not
    such constant in system localization.
    If there is no such constant in default
    language, the object returns empty string.

    """
    def __init__(self, system, default):

        """
        :system: Language object with the system localisation
        :default: default Language object

        """
        self.system = system
        self.default = default

    def __getattr__(self, name):

        """
        Returns string constant. To access
        a constant use appropriate attribute:

        obj.something returns constant with the name 'something'

        """
        try:
            # at first search in system dictionary
            return self.system[name]
        except:
            try:
                # if can't find in system
                # search in default
                return self.default[name]
            except:
                # it there is no constant in default too
                # return empty string
                return ''

@singleton
class Messages:

    """
    Loads default language file and system
    localization file if it presents.
    Creates MsgList objects for each section.

    Access to string constants:

    Messages().SECTION.CONSTANT

    SECTION is a name of the section where the constant is located
    CONSTAN is a name of constant you want to access

    """
    default_lang = 'en' # default language is English

    def __init__(self):
        # initialize system language as None
        # if that is the same as default language,
        # there is no need to load it twice
        system = None
        # load default language
        default = self.load_lang(self.default_lang)
        # if loading failed, shut down program
        if not default:
            raise FatalError('Default language not found')

        sys_locale = locale.getlocale() # get system locale
        # get language name from a tuple that contains
        # a language name and encoding. Format of first element
        # of the tuple is aa_BB but we need the first part of it only.
        lang = sys_locale[0].split('_')[0]
        # system localisation differs with default language
        if lang != self.default_lang:
            system = self.load_lang(lang) # then load system language
        # if system still is None, it means that system language is
        # the same as default or the system localization file not found
        if not system:
            # then use default as system
            system = default

        # MsgList objects for each section
        self.common = MsgList(system.common, default.common)
        self.message = MsgList(system.messages, default.messages)
        self.warning = MsgList(system.warnings, default.warnings)
        self.error = MsgList(system.errors, default.errors)
        self.question = MsgList(system.questions, default.questions)

    @staticmethod
    def load_lang(lang):

        """
        Creates Language object for requested language.

        :language: the language name, type str

        """
        try:
            # try to load a language
            return Language(lang)
        except:
            # if failed return None
            return None
