# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import sys
import argparse

from entropy.output import darkgreen, blue
from entropy.i18n import _

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitBump(EitCommand):
    """
    Main Eit bump command.
    """

    NAME = "bump"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._sync = False

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitBump.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitBump.NAME))

        parser.add_argument("repo", nargs='?', default=None,
                            metavar="<repo>", help=_("repository"))
        parser.add_argument("--sync", action="store_true",
                            default=self._sync,
                            help=_("sync with remote repository"))
        return parser

    def parse(self):
        """ Overridden from EitCommand """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._sync = nsargs.sync
        return self._call_locked, [self._bump, nsargs.repo]

    def _bump(self, entropy_server):
        """
        Actual Entropy Repository bump function
        """
        entropy_server.output(darkgreen(" * ")+blue("%s..." % (
                    _("Bumping repository"),) ))
        entropy_server._bump_database(entropy_server.repository())
        if self._sync:
            errors = entropy_server.Mirrors.sync_repository(
                entropy_server.repository())
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitBump,
        EitBump.NAME,
        _('bump repository revision, force push'))
    )
