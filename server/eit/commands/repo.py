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
from entropy.output import darkgreen, teal

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitRepo(EitCommand):
    """
    Main Eit repo command.
    """

    NAME = "repo"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitRepo.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitRepo.NAME))
        return parser

    INTRODUCTION = """\
Show current repository, its branch and configured mirrors.
"""
    SEE_ALSO = "eit-status(1)"

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        """ Overridden from EitCommand """
        parser = self._get_parser()
        try:
            parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []
        return self._call_locked, [self._void, None]

    def _void(self, entropy_server):
        entropy_server._show_interface_status()
        entropy_server.Mirrors._show_interface_status(
            entropy_server.repository())
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitRepo,
        EitRepo.NAME,
        _('show current repository'))
    )
