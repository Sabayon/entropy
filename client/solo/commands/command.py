# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import os
import argparse

from entropy.i18n import _
from entropy.output import darkgreen, print_error
from entropy.exceptions import PermissionDenied
from entropy.client.interfaces import Client
from entropy.core.settings.base import SystemSettings

import entropy.tools

class SoloCommand(object):
    """
    Base class for Solo commands
    """

    # Set this to the command name from where this object
    # gets triggered (for equo help, "help" is the NAME
    # that should be set).
    NAME = None
    # Set this to a list of aliases for NAME
    ALIASES = []
    # Set this to True if command is a catch-all (fallback)
    CATCH_ALL = False
    # Allow unprivileged access ?
    ALLOW_UNPRIVILEGED = False

    # If True, the command is not shown in the help output
    HIDDEN = False

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

    def _argparse_is_valid_directory(self, string):
        """
        To be used with argparse add_argument() type parameter for
        validating directory paths.
        """
        if os.path.isdir(string) and os.path.exists(string):
            # cope with broken symlinks
            return string
        msg = "%s: %s" % (_("not a valid directory"), string)
        raise argparse.ArgumentTypeError(msg)

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

    def _bashcomp(self, stdout, last_arg, available_args):
        """
        This method must be called from inside bashcomp() and
        does the actual bash-completion rendering on stdout.
        """
        def _startswith(string):
            if last_arg is not None:
                if last_arg not in available_args:
                    return string.startswith(last_arg)
            return True

        if self._args:
            # only filter out if last_arg is actually
            # something after this.NAME.
            available_args = sorted(filter(_startswith, available_args))

        for arg in self._args:
            if arg in available_args:
                available_args.remove(arg)

        stdout.write(" ".join(available_args) + "\n")
        stdout.flush()

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
        prog = "%s %s" % ("equo", self.NAME)
        formatter = parser.formatter_class(prog=prog)
        usage = formatter._format_usage(parser.usage,
                            parser._actions,
                            parser._mutually_exclusive_groups,
                            "").rstrip()

        options_txt = []
        action_groups = parser._action_groups
        if action_groups:
            options_header = "\"equo " + self.NAME + "\" "
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
        Return the Entropy Client object.
        This method is not thread safe.
        """
        return Client(*args, **kwargs)

    def _entropy_bashcomp(self):
        """
        Return an Entropy Client object that MUST
        be used only inside bashcomp methods.
        This object is faster to load than the standard
        Entropy object loaded by _entropy() at the cost
        of less consistency checks.
        """
        return Client(indexing=False, repo_validation=False)

    def _entropy_ws(self, entropy_client, repository_id, tx_cb=False):
        """
        Initialize an Entropy Web Services object for the given
        Repository name.

        @param entropy_client: Entropy Client interface
        @type entropy_client: entropy.client.interfaces.Client
        @param repository_id: repository identifier
        @type repository_id: string
        @return: the ClientWebService instance
        @rtype: entropy.client.services.interfaces.ClientWebService
        @raise WebService.UnsupportedService: if service is unsupported by
            repository
        """
        def _transfer_callback(transfered, total, download):
            if download:
                action = _("Downloading")
            else:
                action = _("Uploading")
            percent = 100
            if (total > 0) and (transfered <= total):
                percent = int(round((float(transfered)/total) * 100, 1))
            msg = "[%s%s] %s ..." % (
                purple(str(percent)), "%", teal(action))
            entropy_client.output(msg, back=True)

        factory = entropy_client.WebServices()
        webserv = factory.new(repository_id)
        if tx_cb:
            webserv._set_transfer_callback(_transfer_callback)
        return webserv

    def _call_locked(self, func):
        """
        Execute the given function at func after acquiring Entropy
        Resources Lock, for given repository at repo.
        The signature of func is: int func(entropy_client).
        """
        client = None
        acquired = False
        try:
            try:
                client = self._entropy()
            except PermissionDenied as err:
                print_error(err.value)
                return 1
            acquired = entropy.tools.acquire_entropy_locks(client)
            if not acquired:
                client.output(
                    darkgreen(_("Another Entropy is currently running.")),
                    level="error", importance=1
                )
                return 1
            return func(client)
        finally:
            if client is not None:
                if acquired:
                    entropy.tools.release_entropy_locks(client)
                client.shutdown()

    def _call_unlocked(self, func):
        """
        Execute the given function at func after acquiring Entropy
        Resources Lock in shared mode, for given repository at repo.
        The signature of func is: int func(entropy_client).
        """
        client = None
        acquired = False
        try:
            try:
                client = self._entropy()
            except PermissionDenied as err:
                print_error(err.value)
                return 1
            # use blocking mode to avoid tainting stdout
            acquired = entropy.tools.acquire_entropy_locks(
                client, blocking=True, shared=True)
            if not acquired:
                client.output(
                    darkgreen(_("Another Entropy is currently running.")),
                    level="error", importance=1
                )
                return 1
            return func(client)
        finally:
            if client is not None:
                if acquired:
                    entropy.tools.release_entropy_locks(client)
                client.shutdown()

    def _settings(self):
        """
        Return a SystemSettings instance.
        """
        return SystemSettings()
