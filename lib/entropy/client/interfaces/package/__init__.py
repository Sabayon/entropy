# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
import sys
import os
import errno
import stat
import shutil
import time
import codecs
import collections

from entropy.const import etpConst, const_setup_perms, const_mkstemp, \
    const_isunicode, const_convert_to_unicode, const_debug_write, \
    const_debug_enabled, const_convert_to_rawstring, const_is_python3
from entropy.exceptions import EntropyException, PermissionDenied, SPMError
from entropy.i18n import _, ngettext
from entropy.output import brown, blue, bold, darkgreen, \
    darkblue, red, purple, darkred, teal
from entropy.client.mirrors import StatusInterface
from entropy.core.settings.base import SystemSettings
from entropy.security import Repository as RepositorySecurity
from entropy.fetchers import UrlFetcher

import entropy.dep
import entropy.tools

from . import _content as Content

from .actions.action import PackageAction
from .actions.config import _PackageConfigAction
from .actions.fetch import _PackageFetchAction
from .actions.install import _PackageInstallAction
from .actions.multifetch import _PackageMultiFetchAction
from .actions.remove import _PackageRemoveAction
from .actions.source import _PackageSourceAction


class PackageActionFactory(object):
    """
    Package action factory.

    This factory object returns PackageAction instances
    that can be used to perform a specific activity (like,
    for instance, the removal, installation or download of a
    single package).

    Example code:

    >>> factory = PackageActionFactory(entropy_client)
    >>> install = PackageActionFactory.INSTALL_ACTION
    >>> obj = factory.get(install, (123, "sabayon-weekly"))
    >>> exit_status = obj.start()
    >>> obj.finalize()

    You can reuse the factory as many times as you want.
    If you pass an invalid action string, InvalidAction() will be raised.
    The PackageAction objects (well, their methods) are not thread-safe.

    This API is process and thread safe with regards to the Installed
    Packages Repository. There is no need to do external locking on it.
    """

    class InvalidAction(EntropyException):
        """
        Raised when the factory is passed an invalid action string.
        """

    INSTALL_ACTION = _PackageInstallAction.NAME
    REMOVE_ACTION = _PackageRemoveAction.NAME
    CONFIG_ACTION = _PackageConfigAction.NAME
    FETCH_ACTION = _PackageFetchAction.NAME
    MULTI_FETCH_ACTION = _PackageMultiFetchAction.NAME
    SOURCE_ACTION = _PackageSourceAction.NAME

    def __init__(self, entropy_client):
        """
        Object constructor.

        @param entropy_client: a valid Client instance.
        @type entropy_client: entropy.client.interfaces.Client
        """
        self._entropy = entropy_client
        self._actions = {
            self.SOURCE_ACTION: _PackageSourceAction,
            self.FETCH_ACTION: _PackageFetchAction,
            self.MULTI_FETCH_ACTION: _PackageMultiFetchAction,
            self.REMOVE_ACTION: _PackageRemoveAction,
            self.INSTALL_ACTION: _PackageInstallAction,
            self.CONFIG_ACTION: _PackageConfigAction,
        }
        self._action_instance = None

    def supported_actions(self):
        """
        Return a list of supported actions.

        @return: a list of supported actions
        @rtype: list
        """
        return sorted(self._actions.keys())

    def get(self, action, package_match, opts = None):
        """
        Return the PackageAction instance associated with the given action.

        @param action: the action string, see supported_actions()
        @type action: string
        @param package_match: an Entropy package match tuple
            (package_id, repository_id)
        @type package_match: tuple
        @keyword opts: metadata options to pass to the PackageAction
            instance
        @type opts: dict
        """
        action_class = self._actions.get(action)
        if action_class is None:
            raise PackageActionFactory.InvalidAction(
                "action does not exist")
        return action_class(self._entropy, package_match, opts = opts)


class PackageActionFactoryWrapper(PackageActionFactory):
    """
    Compatibility class that provides the old Entropy Package() interface.
    It will be dropped at the end of 2014 (hopefully).
    """

    def __init__(self, entropy_client):
        super(PackageActionFactoryWrapper, self).__init__(entropy_client)
        self._action_instance = None
        self.pkgmeta = {}
        self.metaopts = {}

    def prepare(self, package_match, action, metaopts = None):
        """
        Backward compatible method.
        """
        if action in ("remove", "remove_conflict", "config"):
            # the old API only required a tuple with just the
            # installed package id. the new API requires the
            # repository name (id) in every case.
            if action == "remove_conflict":
                action = "remove"
            package_match = (
                package_match[0],
                self._entropy.installed_repository().name)

        self._action_instance = self.get(
            action, package_match, opts = metaopts)
        inst = self._action_instance

        inst.setup()
        self.pkgmeta = inst.metadata()

        # these are required by the old PackageKit backend
        self.pkgmeta['repository'] = self._action_instance.repository_id()

        self.metaopts = metaopts

    def run(self, xterm_header = None):
        """
        Backward compatible method.
        """
        if self._action_instance is None:
            raise PermissionDenied("Not prepared")
        if xterm_header is None:
            xterm_header = ""
        self._action_instance.set_xterm_header(xterm_header)
        return self._action_instance.start()

    def kill(self):
        """
        Backward compatible method.
        """
        if self._action_instance is None:
            raise PermissionDenied("Not prepared")
        return self._action_instance.finalize()

    @classmethod
    def splitdebug_enabled(cls, entropy_client, pkg_match):
        """
        Backward compatible method.
        """
        return PackageAction.splitdebug_enabled(entropy_client, pkg_match)

    @classmethod
    def get_standard_fetch_disk_path(cls, download):
        """
        Backward compatible method.
        """
        return PackageAction.get_standard_fetch_disk_path(download)

# Complete the backward compatibility support bits
Package = PackageActionFactoryWrapper
