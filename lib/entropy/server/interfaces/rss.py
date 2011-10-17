# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server Main Interfaces}.

"""
from entropy.core import Singleton

class ServerRssMetadata(Singleton, dict):

    _META = {
        'added': {},
        'removed': {},
        'commitmessage': "",
        'light': {},
    }

    def init_singleton(self):
        dict.__init__(self)
        self.update(ServerRssMetadata._META)