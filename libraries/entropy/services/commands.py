# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Services Command Interfaces}.

"""
from entropy.services.skel import SocketCommands

class phpBB3(SocketCommands):

    import entropy.dump as dumpTools
    import entropy.tools as entropyTools
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
                'from': str(self), # from what class
            },
            'is_developer':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_is_developer,
                'args': ["authenticator"],
                'as_user': False,
                'desc': "returns whether the username linked with the session belongs to a developer",
                'syntax': "<SESSION_ID> is_developer",
                'from': str(self), # from what class
            },
            'is_moderator':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_is_moderator,
                'args': ["authenticator"],
                'as_user': False,
                'desc': "returns whether the username linked with the session belongs to a moderator",
                'syntax': "<SESSION_ID> is_moderator",
                'from': str(self), # from what class
            },
            'is_administrator':    {
                'auth': True,
                'built_in': False,
                'cb': self.docmd_is_administrator,
                'args': ["authenticator"],
                'as_user': False,
                'desc': "returns whether the username linked with the session belongs to an administrator",
                'syntax': "<SESSION_ID> is_administrator",
                'from': str(self), # from what class
            },
        }

    def docmd_is_user(self, authenticator):
        return authenticator.is_user(), 'ok'

    def docmd_is_developer(self, authenticator):
        return authenticator.is_developer(), 'ok'

    def docmd_is_administrator(self, authenticator):
        return authenticator.is_administrator(), 'ok'

    def docmd_is_moderator(self, authenticator):
        return authenticator.is_moderator(), 'ok'
