#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import gettext

lang_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'i18n')

try:
    gettext.install('messages', lang_path)
except:
    _ = lambda t: t
