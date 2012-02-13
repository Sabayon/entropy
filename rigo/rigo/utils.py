# Copyright (C) 2009 Canonical
#
# Authors:
#  Michael Vogt
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

import logging
import time

class ExecutionTime(object):
    """
    Helper that can be used in with statements to have a simple
    measure of the timming of a particular block of code, e.g.
    with ExecutinTime("db flush"):
        db.flush()
    """
    def __init__(self, info=""):
        self.info = info

    def __enter__(self):
        self.now = time.time()

    def __exit__(self, type, value, stack):
        logger = logging.getLogger("softwarecenter.performance")
        logger.debug("%s: %s" % (self.info, time.time() - self.now))

def utf8(s):
    """
    Takes a string or unicode object and returns a utf-8 encoded
    string, errors are ignored
    FIXME: lxnay, drop this crap and use Entropy functions instead.
    """
    if s is None:
        return None
    if isinstance(s, unicode):
        return s.encode("utf-8", "ignore")
    return unicode(s, "utf8", "ignore").encode("utf8")
