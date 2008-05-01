#!/usr/bin/env python
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

"""i18n abstraction

License: GPL
Author: Vladimir Bormotov <bor@vb.dn.ua>

"""
# This file is a copy of the yum i18n.py file, modified to use
# yumex as translation domain.

_LOCALE = None
try:
    import gettext
    import sys, os
    if sys.version_info[0] == 2:
        t = gettext.translation('spritz')
        _ = t.gettext
    else:
        gettext.bindtextdomain('spritz', '/usr/share/locale')
        gettext.textdomain('spritz')
        _ = gettext.gettext

    _LOCALE_FULL = os.getenv('LC_ALL')
    if _LOCALE_FULL == None:
        _LOCALE_FULL = os.getenv('LANG')
    if _LOCALE_FULL == None:
        _LOCALE_FULL = os.getenv('LANGUANGE')

    if _LOCALE_FULL:
        _LOCALE = _LOCALE_FULL.split('.')[0]
        _LOCALE = _LOCALE.split('_')[0]
        _LOCALE = _LOCALE.lower()

except:
    def _(mystr):
        """pass given string as-is"""
        return mystr
