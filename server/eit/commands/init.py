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


class EitInit(EitCommand):
    """
    Main Eit init command.
    """

    NAME = "init"
    ALIASES = []

    def _get_parser(self):
        """ Overridden from EitInit """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitInit.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitInit.NAME))

        parser.add_argument("repo", nargs=1, default=None,
                            metavar="<repo>", help=_("repository"))
        parser.add_argument("--quick", action="store_true",
                            default=False,
                            help=_("no stupid questions"))

        return parser

    def parse(self):
        """ Overridden from EitInit """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        self._ask = not nsargs.quick
        return self._call_locked, [self._init, nsargs.repo[0]]

    def _init(self, entropy_server):
        rc = entropy_server.initialize_repository(
            entropy_server.repository(), ask=self._ask)
        if rc == 0:
            entropy_server.output(
                teal(_("Entropy repository has been initialized")),
                header=darkgreen(" * "),
                importance=1)
            return 0
        return 1

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitInit,
        EitInit.NAME,
        _('initialize repository (erasing all its content)'))
    )
