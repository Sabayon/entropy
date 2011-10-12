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


class EitCheckout(EitCommand):
    """
    Main Eit checkout command.
    """

    NAME = "checkout"
    ALIASES = ["ci"]

    def parse(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitCheckout.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitCheckout.NAME))

        parser.add_argument("repo", metavar="<repo>",
                            help=_("repository"))

        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        return self._call_locked, [self._checkout, nsargs.repo]

    def _checkout(self, entropy_server):
        """
        Actual Entropy Repository checkout function
        """
        repository_id = entropy_server.repository()
        entropy_server.switch_default_repository(repository_id,
            save = True)
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitCheckout,
        EitCheckout.NAME,
        _('switch from a repository to another'))
    )
