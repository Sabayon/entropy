# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework internationalization module}

    This module contains Entropy Framework i18n functions and
    variables.

"""

import sys
import os
_LOCALE = None
_LOCALE_FULL = os.getenv('LC_ALL')
if _LOCALE_FULL == None:
    _LOCALE_FULL = os.getenv('LANG')
if _LOCALE_FULL == None:
    _LOCALE_FULL = os.getenv('LANGUAGE')

if _LOCALE_FULL:
    _LOCALE = _LOCALE_FULL.split('.')[0]
    _LOCALE = _LOCALE.split('_')[0]
    _LOCALE = _LOCALE.lower()

try:
    import gettext
    localedir = "/usr/share/locale"
    # support for ENV TEXTDOMAINDIR
    envdir = os.getenv('TEXTDOMAINDIR')
    if envdir is not None:
        localedir = envdir
    gettext.install('entropy', localedir = localedir, unicode = True)
    # do not use gettext.gettext because it returns str instead of unicode
    _ = _

except (ImportError, OSError,):
    def _(raw_string):
        """
        Fallback in case gettext is not available, same syntax
        for the gettext provided function.

        @param raw_string: raw untranslated string
        @type raw_string: string
        @return: translated string using environment locale
            setting (LC_ALL, LANG or LANGUAGE)
        @rtype: string
        """
        return raw_string

def change_language(lang):
    """
    Change gettext language on the fly.

    @param lang: new language string (see `locale -a` for a list of
        supported ones)
    @type lang: string
    """
    global _
    # change in environ
    for var in ("LANGUAGE", "LC_ALL", "LANG",):
        os.environ[var] = lang
    # reinstall gettext
    # remove _ from global scope so that gettext will readd it
    old_ = _
    del _
    gettext.install('entropy', localedir = localedir, unicode = True)
    _ = _
    # redeclare "_" in all loaded modules
    for module in list(sys.modules.values()):
        if not hasattr(module, "__dict__"):
            continue
        t_func = module.__dict__.get("_")
        if t_func is not old_:
            continue
        module._ = _
