# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import os
import sys
import argparse

from entropy.i18n import _
from entropy.const import const_convert_to_unicode, \
    const_convert_to_rawstring
from entropy.locks import EntropyResourcesLock
from entropy.output import darkgreen, teal, purple, print_error, \
    print_generic, bold, brown
from entropy.exceptions import PermissionDenied
from entropy.client.interfaces import Client
from entropy.core.settings.base import SystemSettings

import entropy.tools

from solo.utils import enlightenatom


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


def sharedlock(func):
    """
    Solo command methods decorator that acquires the Installed
    Packages Repository lock in shared mode and calls the wrapped
    function with an extra argument (the Installed Packages
    Repository object instance).
    """
    def wrapped(zelf, entropy_client, *args, **kwargs):
        inst_repo = entropy_client.installed_repository()
        with inst_repo.shared():
            return func(zelf, entropy_client, inst_repo, *args, **kwargs)

    return wrapped


def exclusivelock(func):
    """
    Solo command methods decorator that acquires the Installed
    Packages Repository lock in exclusive mode and calls the wrapped
    function with an extra argument (the Installed Packages
    Repository object instance).
    """
    def wrapped(zelf, entropy_client, *args, **kwargs):
        inst_repo = entropy_client.installed_repository()
        with inst_repo.exclusive():
            return func(zelf, entropy_client, inst_repo, *args, **kwargs)

    return wrapped


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

        # see bug 3873, requires raw string
        msg = const_convert_to_rawstring(
            msg, from_enctype="utf-8")
        raise argparse.ArgumentTypeError(msg)

    def _argparse_is_valid_entropy_package(self, string):
        """
        To be used with argparse add_argument() type parameter for
        validating entropy package paths.
        """
        if os.path.isfile(string) and os.path.exists(string):
            if entropy.tools.is_entropy_package_file(string):
                return string
        msg = "%s: %s" % (_("not a valid Entropy package file"), string)
        raise argparse.ArgumentTypeError(msg)

    def _setup_verbose_quiet_parser(self, parser):
        """
        Add --verbose and --quiet switches to parser.
        """
        parser.add_argument(
            "--verbose", "-v", action="store_true", default=False,
            help=_("verbose output"))
        parser.add_argument(
            "--quiet", "-q", action="store_true", default=False,
            help=_("quiet output"))

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

    def _hierarchical_bashcomp(self, last_arg, outcome, commands):
        """
        This method implements bash completion through
        a hierarchical (commands) dictionary object.
        """
        # navigate through commands, finding the list of commands
        _commands = commands

        if not self._args:
            # show all the commands
            outcome += sorted(commands.keys())

        for index, item in enumerate(self._args):
            if item in _commands:
                _commands = commands[item]
                if index == (len(self._args) - 1):
                    # if this is the last one, generate
                    # proper outcome elements.
                    outcome += sorted(_commands.keys())
                    # reset last_arg so that outcome list
                    # won't be filtered
                    last_arg = ""
            elif index == (len(self._args) - 1):
                # if this is the last one, and item
                # is not in _commands, outcome becomes
                # _commands.keys()
                outcome += sorted(_commands.keys())
                # no need to break here
            else:
                # item not in commands, but that's not the
                # last one, we must generate proper outcome
                # elements and stop right after
                outcome += sorted(_commands.keys())
                break

        return self._bashcomp(sys.stdout, last_arg, outcome)

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

    def _entropy_class(self):
        """
        Return the Entropy Client class object.
        """
        return Client

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

    def _call_exclusive(self, func):
        """
        Execute the given function at func after acquiring Entropy
        Resources Lock, for given repository at repo.
        The signature of func is: int func(entropy_client).
        """
        client_class = None
        client = None
        acquired = False
        lock = None
        try:
            try:
                client_class = self._entropy_class()
            except PermissionDenied as err:
                print_error(err.value)
                return 1
            blocking = os.getenv("__EQUO_LOCKS_BLOCKING__")
            if blocking:
                client_class.output(darkgreen(
                        _("Acquiring Entropy Resources "
                          "Lock, please wait...")),
                              back=True)

            lock = EntropyResourcesLock(output=client_class)
            if blocking:
                lock.acquire_exclusive()
                acquired = True
            else:
                acquired = lock.wait_exclusive()
            if not acquired:
                client_class.output(
                    darkgreen(_("Another Entropy is currently running.")),
                    level="error", importance=1
                )
                return 1

            client = client_class()
            return func(client)
        finally:
            if client is not None:
                client.shutdown()
            if acquired:
                lock.release()

    def _call_shared(self, func):
        """
        Execute the given function at func after acquiring Entropy
        Resources Lock in shared mode, for given repository at repo.
        The signature of func is: int func(entropy_client).
        """
        client_class = None
        client = None
        acquired = False
        lock = None
        try:
            try:
                client_class = self._entropy_class()
            except PermissionDenied as err:
                print_error(err.value)
                return 1

            lock = EntropyResourcesLock(output=client_class)
            lock.acquire_shared()
            acquired = True

            client = client_class()
            return func(client)
        finally:
            if client is not None:
                client.shutdown()
            if acquired:
                lock.release()

    def _settings(self):
        """
        Return a SystemSettings instance.
        """
        return SystemSettings()

    def _show_did_you_mean(self, entropy_client, package, from_installed):
        """
        Show "Did you mean?" results for the given package name.
        """
        items = entropy_client.get_meant_packages(
            package, from_installed=from_installed)
        if not items:
            return

        mytxt = "%s %s %s %s %s" % (
            bold(const_convert_to_unicode("   ?")),
            teal(_("When you wrote")),
            bold(const_convert_to_unicode(package)),
            darkgreen(_("You Meant(tm)")),
            teal(_("one of these below?")),
        )
        entropy_client.output(mytxt)

        _cache = set()
        for pkg_id, repo_id in items:
            if from_installed:
                repo = entropy_client.installed_repository()
            else:
                repo = entropy_client.open_repository(repo_id)

            key_slot = repo.retrieveKeySlotAggregated(pkg_id)
            if key_slot not in _cache:
                entropy_client.output(
                    enlightenatom(key_slot),
                    header=brown("    # "))
                _cache.add(key_slot)
