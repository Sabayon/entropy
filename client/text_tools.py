# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Client text-based tools}.

"""
import os
import subprocess

from entropy.const import etpConst
from entropy.output import print_info, darkgreen
from entropy.i18n import _

# Temporary files cleaner
def cleanup(directories = None):

    if not directories:
        directories = [etpConst['packagestmpdir'], etpConst['logdir']]

    counter = 0
    for xdir in directories:
        if not os.path.isdir(xdir):
            continue
        print_info("%s %s %s..." % (_("Cleaning"), darkgreen(xdir),
            _("directory"),), back = True)
        for data in os.listdir(xdir):
            subprocess.call(["rm", "-rf", os.path.join(xdir, data)])
            counter += 1

    print_info("%s: %s %s" % (
        _("Cleaned"), counter, _("files and directories"),))
    return 0
