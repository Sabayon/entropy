# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
from entropy.i18n import _
from entropy.const import etpConst
from entropy.output import darkgreen, print_error
from entropy.exceptions import PermissionDenied
from entropy.server.interfaces import Server
from entropy.core.settings.base import SystemSettings

import entropy.tools

class EitCommand(object):
    """
    Base class for Eit commands
    """

    # Set this to the command name from where this object
    # gets triggered (for eit help, "help" is the NAME
    # that should be set).
    NAME = None
    # Set this to a list of aliases for NAME
    ALIASES = []
    # Set this to True if command is a catch-all (fallback)
    CATCH_ALL = False

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

    def _call_locked(self, func, repo):
        """
        Execute the given function at func after acquiring Entropy
        Resources Lock, for given repository at repo.
        The signature of func is: int func(entropy_server).
        """
        server = None
        acquired = False
        try:
            try:
                server = self._entropy(default_repository=repo)
            except PermissionDenied as err:
                print_error(err.value)
                return 1
            acquired = entropy.tools.acquire_entropy_locks(server)
            if not acquired:
                server.output(
                    darkgreen(_("Another Entropy is currently running.")),
                    level="error", importance=1
                )
                return 1
            return func(server)
        finally:
            if server is not None:
                if acquired:
                    entropy.tools.release_entropy_locks(server)
                server.shutdown()

    def _settings(self):
        """
        Return a SystemSettings instance.
        """
        return SystemSettings()
