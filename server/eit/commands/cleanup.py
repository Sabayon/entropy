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

from entropy.output import darkgreen, blue
from entropy.i18n import _

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitCleanup(EitCommand):
    """
    Main Eit cleanup command.
    """

    NAME = "cleanup"
    ALIASES = ["cn"]

    def parse(self):
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

        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        self._ask = not nsargs.quick
        return self._call_locked, [self._cleanup, nsargs.repo]

    def _cleanup(self, entropy_server):
        """
        Actual Entropy Repository cleanup function
        """
        repository_id = entropy_server.repository()
        entropy_server.Mirrors.tidy_mirrors(repository_id,
                                            ask = self._ask)
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitCleanup,
        EitCleanup.NAME,
        _('clean expired packages from a repository'))
    )
