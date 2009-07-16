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
from entropy.services.skel import SocketCommands

class Test(SocketCommands):

    import entropy.dump as dumpTools
    import entropy.tools as entropyTools
    def __init__(self, HostInterface):

        SocketCommands.__init__(self, HostInterface, inst_name = "test-commands")
        self.raw_commands = ['test:echo']

        self.valid_commands = {
            'test:echo': {
                'auth': False,
                'built_in': False,
                'cb': self.docmd_echo,
                'args': ["myargs"],
                'as_user': False,
                'desc': "print arguments echo",
                'syntax': "<SESSION_ID> test:echo <raw_data>",
                'from': unicode(self),
            },
        }


    def docmd_echo(self, myargs):

        if not myargs:
            return None, 'wrong arguments'

        return True, ' '.join(myargs)

