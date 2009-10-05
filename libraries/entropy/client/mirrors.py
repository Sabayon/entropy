# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Download Mirrors Interface}.

"""

class StatusInterface(dict):

    def __init__(self):
        self.__last_mirrorname = None
        dict.__init__(self)

    def add_failing_mirror(self, mirrorname, increment = 1):
        if mirrorname not in self:
            self[mirrorname] = 0
        self[mirrorname] += increment
        return self[mirrorname]

    def get_failing_mirror_status(self, mirrorname):
        return self.get(mirrorname, 0)

    def set_failing_mirror_status(self, mirrorname, value):
        self[mirrorname] = value

    def set_working_mirror(self, mirrorname):
        self.__last_mirrorname = mirrorname

    def add_failing_working_mirror(self, value):
        if self.__last_mirrorname:
            self.add_failing_mirror(self.__last_mirrorname, value)

    def clear(self):
        self.__last_mirrorname = None
        return dict.clear(self)