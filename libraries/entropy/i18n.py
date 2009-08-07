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
    gettext.bindtextdomain('entropy', '/usr/share/locale')
    gettext.textdomain('entropy')
    gettext.install('entropy', unicode=True)

    # do not use gettext.gettext because it returns str instead of unicode
    _ = _

except (ImportError,OSError,):
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
