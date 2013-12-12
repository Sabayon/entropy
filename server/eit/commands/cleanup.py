# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import sys
import os
import argparse

from entropy.output import darkgreen, blue, purple
from entropy.i18n import _

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitCleanup(EitCommand):
    """
    Main Eit cleanup command.
    """

    NAME = "cleanup"
    ALIASES = ["cn", "clean"]

    def __init__(self, args):
        EitCommand.__init__(self, args)
        # ask user before any critical operation
        self._ask = True
        self._pretend = False
        self._days = None

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitCleanup.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitCleanup.NAME))

        parser.add_argument("repo", nargs='?', default=None,
                            metavar="<repo>", help=_("repository"))
        parser.add_argument("--quick", action="store_true",
                            default=False,
                            help=_("no stupid questions"))
        parser.add_argument("--pretend", action="store_true",
                            default=False,
                            help=_("show what would be done"))

        parser.add_argument('--days', type=int, default=self._days,
            help=_("expired since how many days"))
        return parser

    def bashcomp(self, last_arg):
        """
        Overridden from EitCommand
        """
        import sys

        entropy_server = self._entropy(handle_uninitialized=False,
                                       installed_repo=-1)
        outcome = entropy_server.repositories()
        for arg in self._args:
            if arg in outcome:
                # already given a repo
                outcome = []
                break
        outcome += ["--quick", "--days", "--pretend"]

        def _startswith(string):
            if last_arg is not None:
                if last_arg not in outcome:
                    return string.startswith(last_arg)
            return True

        if self._args:
            # only filter out if last_arg is actually
            # something after this.NAME.
            outcome = sorted(filter(_startswith, outcome))

        for arg in self._args:
            if arg in outcome:
                outcome.remove(arg)

        sys.stdout.write(" ".join(outcome) + "\n")
        sys.stdout.flush()

    INTRODUCTION = """\
Clean expired packages from remote mirrors. Usually, packages
have a default expiration timeout set to 15 days (entropy.const),
overridable via *ETP_EXPIRATION_DAYS* env variable.
Expiration date starts from when packages are removed from a repository
due to a version bump or simple removal.
During the final part of packages sync, expired ones are automatically
removed from remote mirrors.
This commands makes possible to manually force a cleanup.
"""

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        """ Overridden from EitCommand """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        self._ask = not nsargs.quick
        if nsargs.days is not None:
            self._days = nsargs.days
        self._pretend = nsargs.pretend
        return self._call_exclusive, [self._cleanup, nsargs.repo]

    def _cleanup(self, entropy_server):
        """
        Actual Entropy Repository cleanup function
        """
        if self._days is not None:
            entropy_server.output("", level="warning")
            entropy_server.output(
                purple(_("Removing unavailable packages overriding defaults")),
                importance=1,
                level="warning")
            entropy_server.output(
                purple(_("Users with older repositories will have to update")),
                importance=1,
                level="warning")
            entropy_server.output("", level="warning")

        repository_id = entropy_server.repository()
        entropy_server.Mirrors.tidy_mirrors(
            repository_id, ask = self._ask,
            pretend = self._pretend, expiration_days = self._days)
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitCleanup,
        EitCleanup.NAME,
        _('clean expired packages from a repository'))
    )

class EitVacuum(EitCleanup):
    """
    Main Eit vacuum command (kept for backward compat).
    """

    NAME = "vacuum"
    ALIASES = []

    def __init__(self, args):
        EitCleanup.__init__(self, args)
        # default is 0 here
        self._days = 0

    INTRODUCTION = """\
This is deprecated, please see *eit-cleanup(1)*.
"""
    SEE_ALSO = "eit-cleanup(1)"

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitVacuum,
        EitVacuum.NAME,
        _('clean expired packages from a repository'))
    )
