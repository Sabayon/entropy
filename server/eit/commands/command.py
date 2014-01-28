# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import argparse
import os

from entropy.i18n import _
from entropy.locks import EntropyResourcesLock
from entropy.output import darkgreen, print_error, print_generic
from entropy.exceptions import PermissionDenied
from entropy.server.interfaces import Server
from entropy.server.interfaces.db import ServerRepositoryStatus
from entropy.core.settings.base import SystemSettings

import entropy.tools


def _fix_argparse_print_help():
    """
    Fix argparse.ArgumentParser.print_help to always work
    with UTF-8 characters and pipes. See bug 4049.
    """
    class _Printer(object):

        @classmethod
        def write(self, string):
            print_generic(string)

    original_print_help = argparse.ArgumentParser.print_help

    def _print_help(zelf, file=None):
        if file is None:
            file = _Printer
        return original_print_help(zelf, file=file)

    argparse.ArgumentParser.print_help = _print_help


_fix_argparse_print_help()


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
    # Allow unprivileged access ?
    ALLOW_UNPRIVILEGED = False

    # These two class variables are used in the man page
    # generation. You also need to override man()
    INTRODUCTION = "No introduction available"
    SEE_ALSO = ""

    def __init__(self, args):
        self._args = args

    def _get_parser(self):
        """
        This is the argparse parser setup method, it shall return
        the ArgumentParser object that will be used by parse().
        """
        raise NotImplementedError()

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

    def bashcomp(self, last_arg):
        """
        Print to standard output the bash completion outcome
        for given arguments (self._args).
        Raise NotImplementedError() if not supported.

        @param last_arg: last argument in the argv. Useful
        for allowing its automagic completion.
        Can be None !!
        @type last_arg: string or None
        """
        raise NotImplementedError()

    def man(self):
        """
        Return a dictionary containing the following man
        entries (in a2x format), excluding the entry title:
        name, synopsis, introduction, options.
        Optional keys are: seealso.
        All of them are mandatory.
        """
        raise NotImplementedError()

    def _man(self):
        """
        Standard man page outcome generator that can be used
        to implement class-specific man() methods.
        You need to provide your own INTRODUCTION and
        SEE_ALSO class fields (see class-level variables).
        """
        parser = self._get_parser()
        prog = "%s %s" % ("eit", self.NAME)
        formatter = parser.formatter_class(prog=prog)
        usage = formatter._format_usage(parser.usage,
                            parser._actions,
                            parser._mutually_exclusive_groups,
                            "").rstrip()

        options_txt = []
        action_groups = parser._action_groups
        if action_groups:
            options_header = "\"eit " + self.NAME + "\" "
            options_header += "supports the following options which "
            options_header += "alters its behaviour.\n\n"
            options_txt.append(options_header)

        for group in action_groups:
            if group._group_actions:
                options_txt.append(group.title.upper())
                options_txt.append("~" * len(group.title))
            for action in group._group_actions:
                action_name = action.metavar

                option_strings = action.option_strings
                if not option_strings:
                    # positional args
                    if action_name is None:
                        # SubParsers
                        action_lst = []
                        for sub_action in action._get_subactions():
                            sub_action_str = "*" + sub_action.dest + "*::\n"
                            sub_action_str += "    " + sub_action.help + "\n"
                            action_lst.append(sub_action_str)
                        action_str = "\n".join(action_lst)
                    else:
                        action_str = "*" + action_name + "*::\n"
                        action_str += "    " + action.help + "\n"
                else:
                    action_str = ""
                    for option_str in option_strings:
                        action_str = "*" + option_str + "*"
                        if action_name:
                            action_str += "=" + action_name
                        action_str += "::\n"
                        action_str += "    " + action.help + "\n"
                options_txt.append(action_str)

        data = {
            'name': self.NAME,
            'description': parser.description,
            'introduction': self.INTRODUCTION,
            'seealso': self.SEE_ALSO,
            'synopsis': usage,
            'options': "\n".join(options_txt),
        }
        return data

    def _entropy(self, *args, **kwargs):
        """
        Return the Entropy Server object.
        This method is not thread safe.
        """
        return Server(*args, **kwargs)

    @classmethod
    def _entropy_class(cls):
        """
        Return the Entropy Server class object.
        This method is not thread safe.
        """
        return Server

    def _call_exclusive(self, func, repo):
        """
        Execute the given function at func after acquiring Entropy
        Resources Lock, for given repository at repo.
        The signature of func is: int func(entropy_server).
        """
        server = None
        server_class = None
        acquired = False
        lock = None

        # make possible to avoid dealing with the resources lock.
        # This is useful if the lock is already acquired by some
        # parent or controller process.
        skip_lock = os.getenv("EIT_NO_RESOURCES_LOCK") is not None

        try:
            try:
                server_class = self._entropy_class()
            except PermissionDenied as err:
                print_error(err.value)
                return 1

            if not skip_lock:
                lock = EntropyResourcesLock(output=server_class)
                acquired = lock.wait_exclusive()
                if not acquired:
                    server_class.output(
                        darkgreen(_("Another Entropy is currently running.")),
                        level="error", importance=1
                    )
                    return 1

            server = server_class(default_repository=repo)

            # make sure that repositories are closed now
            # to reset their internal states, which could have
            # become stale.
            # We cannot do this inside the API because we don't
            # know the lifecycle of EntropyRepository objects there.
            server.close_repositories()
            ServerRepositoryStatus().reset()

            return func(server)
        finally:
            if server is not None:
                server.shutdown()
            if acquired:
                lock.release()

    def _call_shared(self, func, repo):
        """
        Execute the given function at func after acquiring Entropy
        Resources Lock in shared mode, for given repository at repo.
        The signature of func is: int func(entropy_server).
        """
        server = None
        server_class = None
        acquired = False
        lock = None

        # make possible to avoid dealing with the resources lock.
        # This is useful if the lock is already acquired by some
        # parent or controller process.
        skip_lock = os.getenv("EIT_NO_RESOURCES_LOCK") is not None

        try:
            try:
                server_class = self._entropy_class()
            except PermissionDenied as err:
                print_error(err.value)
                return 1

            if not skip_lock:
                lock = EntropyResourcesLock(output=server_class)
                lock.acquire_shared()
                acquired = True

            if not acquired:
                server_class.output(
                    darkgreen(_("Another Entropy is currently running.")),
                    level="error", importance=1
                )
                return 1

            server = server_class(default_repository=repo)

            # make sure that repositories are closed now
            # to reset their internal states, which could have
            # become stale.
            # We cannot do this inside the API because we don't
            # know the lifecycle of EntropyRepository objects there.
            server.close_repositories()
            ServerRepositoryStatus().reset()

            return func(server)
        finally:
            if server is not None:
                server.shutdown()
            if acquired:
                lock.release()

    def _settings(self):
        """
        Return a SystemSettings instance.
        """
        return SystemSettings()
