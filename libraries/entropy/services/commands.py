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

class phpBB3(SocketCommands):

    import dumpTools
    import entropyTools
    def __init__(self, HostInterface):

        SocketCommands.__init__(self, HostInterface, inst_name = "phpbb3-commands")

        self.valid_commands = {
            'is_user':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_is_user,
                'args': ["authenticator"],
                'as_user': False,
                'desc': "returns whether the username linked with the session belongs to a simple user",
                'syntax': "<SESSION_ID> is_user",
                'from': unicode(self), # from what class
            },
            'is_developer':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_is_developer,
                'args': ["authenticator"],
                'as_user': False,
                'desc': "returns whether the username linked with the session belongs to a developer",
                'syntax': "<SESSION_ID> is_developer",
                'from': unicode(self), # from what class
            },
            'is_moderator':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_is_moderator,
                'args': ["authenticator"],
                'as_user': False,
                'desc': "returns whether the username linked with the session belongs to a moderator",
                'syntax': "<SESSION_ID> is_moderator",
                'from': unicode(self), # from what class
            },
            'is_administrator':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_is_administrator,
                'args': ["authenticator"],
                'as_user': False,
                'desc': "returns whether the username linked with the session belongs to an administrator",
                'syntax': "<SESSION_ID> is_administrator",
                'from': unicode(self), # from what class
            },
        }

    def docmd_is_user(self, authenticator):
        return authenticator.is_user(),'ok'

    def docmd_is_developer(self, authenticator):
        return authenticator.is_developer(),'ok'

    def docmd_is_administrator(self, authenticator):
        return authenticator.is_administrator(),'ok'

    def docmd_is_moderator(self, authenticator):
        return authenticator.is_moderator(),'ok'
