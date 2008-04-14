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

"""
License: GPL
Author: Fabio Erculiani <lxnay@sabayonlinux.org>
"""

try:
    import gettext
    import sys
    if sys.version_info[0] == 2:
        t = gettext.translation('entropy')
        _ = t.gettext
    else:
        gettext.bindtextdomain('entropy', '/usr/share/locale')
        gettext.textdomain('entropy')
        _ = gettext.gettext
except:
    def _(s):
        return s
