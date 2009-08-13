# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Services Testing Interface}.

"""
from entropy.services.interfaces import SocketHost
from entropy.const import etpConst
from entropy.output import TextInterface

class Server(SocketHost):

    class FakeServiceInterface:
        def __init__(self, *args, **kwargs):
            self.Text = TextInterface()
            self.Text.updateProgress(":: FakeServiceInterface loaded ::")

    def __init__(self, do_ssl = False, stdout_logging = True,
        entropy_interface_kwargs = {}, **kwargs):

        from entropy.services.system.commands import Base
        if not kwargs.has_key('external_cmd_classes'):
            kwargs['external_cmd_classes'] = []
        kwargs['external_cmd_classes'].insert(0, Base)

        self.Text = TextInterface()
        SocketHost.__init__(
            self,
            self.FakeServiceInterface,
            sock_output = self.Text,
            ssl = do_ssl,
            **kwargs
        )
        self.stdout_logging = stdout_logging

