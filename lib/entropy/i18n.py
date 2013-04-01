# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
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

# make possible to override the default gettext domain
# from api users
_GETTEXT_DOMAIN = os.getenv("ETP_GETTEXT_DOMAIN", "entropy")

try:
    try:
        import __builtin__
    except ImportError:
        # python3
        import builtins as __builtin__
    import gettext
    localedir = "/usr/share/locale"
    # support for ENV TEXTDOMAINDIR
    envdir = os.getenv('TEXTDOMAINDIR')
    if envdir is not None:
        localedir = envdir
    kwargs = {"localedir": localedir}
    kwargs['names'] = ["ngettext"]
    if sys.hexversion < 0x3000000:
        kwargs['unicode'] = True
    gettext.install(_GETTEXT_DOMAIN, **kwargs)
    # do not use gettext.gettext because it returns str instead of unicode
    _ = __builtin__.__dict__['_']
    ngettext = __builtin__.__dict__['ngettext']

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

    def ngettext(singular, plural, n):
        """
        Plural aware version of _(). Fallback function in case
        gettext is not available, same syntax as gettext.ngettext.

        @param singular: the singular version of the string
        @type singular: string
        @param plural: the plural version of the string
        @type plural: string
        @param n: the number of elements
        @type n: int
        @return: translated string, either singular or plural
        basin on n
        """
        if n < 2:
            return singular
        return plural

def change_language(lang):
    """
    Change gettext language on the fly.

    @param lang: new language string (see `locale -a` for a list of
        supported ones)
    @type lang: string
    """
    try:
        import __builtin__
    except ImportError:
        # python3
        import builtins as __builtin__
    # change in environ
    for var in ("LANGUAGE", "LC_ALL", "LANG"):
        os.environ[var] = lang
    # reinstall gettext
    # remove _ from global scope so that gettext will readd it
    old_ = __builtin__.__dict__.get('_')
    __builtin__.__dict__.pop("_", None)
    localedir = "/usr/share/locale"
    # support for ENV TEXTDOMAINDIR
    envdir = os.getenv('TEXTDOMAINDIR')
    if envdir is not None:
        localedir = envdir
    kw_args = {"localedir": localedir}
    if sys.hexversion < 0x3000000:
        kw_args['unicode'] = True
    gettext.install(_GETTEXT_DOMAIN, **kw_args)
    _ = __builtin__.__dict__['_']
    # redeclare "_" in all loaded modules
    for module in list(sys.modules.values()):
        if not hasattr(module, "__dict__"):
            continue
        t_func = module.__dict__.get("_")
        if t_func is not old_:
            continue
        module.__dict__['_'] = _

# Define some constants that can be used externally.
ENCODING = "UTF-8"
RAW_ENCODING = "raw_unicode_escape"

# determine whether we have a valid locale configured and
# glibc is happy.
_FALLBACK_LOCALE = "en_US.UTF-8"
_DETECTED_ENC = sys.getfilesystemencoding()

_VALID_LOCALE = ENCODING.lower() == _DETECTED_ENC.lower()

# if locale is invalid, we call change_language and switch
# to a reliable one that we assume it's always present: _FALLBACK_LOCALE.
# Values different from UTF-8 are not supported and can cause
# massive system destruction. Unfortunately, there is no good way
# to ensure that a valid UTF-8 encoding is selected, but we try to do
# our best to automatically recover from this.
if not _VALID_LOCALE:
    default_locale = "en_US." + ENCODING
    sys.stderr.write("""\
invalid filesystem encoding %s, must be %s.
Make sure to set LC_ALL, LANG, LANGUAGE to valid %s values.
Please execute:
  LC_ALL=en_US.%s %s
Trying to force %s.
""" % (_DETECTED_ENC, ENCODING, ENCODING, ENCODING,
       " ".join(sys.argv), _FALLBACK_LOCALE))
    # switch to the FALLBACK_LOCALE
    change_language(_FALLBACK_LOCALE)
