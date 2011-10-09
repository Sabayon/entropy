# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
from entropy.const import etpConst
from entropy.server.interfaces import Server
from entropy.core.settings.base import SystemSettings

class EitCommand(object):
    """
    Base class for Eit commands
    """

    # Set this to the command name from where this object
    # gets triggered (for eit help, "help" is the NAME
    # that should be set).
    NAME = None

    def __init__(self, args):
        self._args = args

    def parse(self):
        """
        Parse the actual arguments and return
        the function that should be called and
        its arguments. The function signature is:
          int function([list of args])
        The return value represents the exit status
        of the "command"
        """
        raise NotImplementedError()

    def _entropy(self, *args, **kwargs):
        """
        Return the Entropy Server object.
        This method is not thread safe.
        """
        if "community_repo" not in kwargs:
            kwargs["community_repo"] = etpConst['community']['mode']
        return Server(*args, **kwargs)

    def _settings(self):
        """
        Return a SystemSettings instance.
        """
        return SystemSettings()
