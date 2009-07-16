# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''
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

