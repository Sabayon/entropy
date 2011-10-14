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

from entropy.i18n import _
from entropy.output import teal, purple

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitVacuum(EitCommand):
    """
    Main Eit vacuum command.
    """

    NAME = "vacuum"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        # ask user before any critical operation
        self._ask = True
        self._pretend = False
        self._days = 0

    def parse(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitVacuum.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitVacuum.NAME))

        parser.add_argument("repo", nargs='?', default=None,
                            metavar="<repo>", help=_("repository"))
        parser.add_argument("--quick", action="store_true",
                            default=False,
                            help=_("no stupid questions"))
        parser.add_argument('--days', type=int, default=self._days,
            help=_("expired since how many days, default: 0"))

        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        self._ask = not nsargs.quick
        self._days = nsargs.days

        return self._call_locked, [self._vacuum, nsargs.repo]

    def _vacuum(self, entropy_server):
        """
        Actual vacuum code
        """
        entropy_server.output("", level="warning")
        entropy_server.output(
            purple(_("Removing unavailable packages overriding defaults")),
            importance=1,
            level="warning")
        entropy_server.output(
            purple(_("Users with old repositories will need to update")),
            importance=1,
            level="warning")
        entropy_server.output("", level="warning")
        rc = entropy_server.Mirrors.tidy_mirrors(
            entropy_server.repository(), ask = self._ask,
            pretend = self._pretend, expiration_days = self._days)
        if rc:
            return 0
        return 1


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitVacuum,
        EitVacuum.NAME,
        _('clean expired/removed packages from repository'))
    )
