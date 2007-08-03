#!/usr/bin/env python
"""i18n abstraction

License: GPL
Author: Vladimir Bormotov <bor@vb.dn.ua>

"""
# This file is a copy of the yum i18n.py file, modified to use
# yumex as translation domain.

try: 
    import gettext
    import sys
    if sys.version_info[0] == 2:
        t = gettext.translation('yumex')
        _ = t.gettext
    else:
        gettext.bindtextdomain('yumex', '/usr/share/locale')
        gettext.textdomain('yumex')
        _ = gettext.gettext

except:
    def _(str):
        """pass given string as-is"""
        return str

if __name__ == '__main__':
    pass
