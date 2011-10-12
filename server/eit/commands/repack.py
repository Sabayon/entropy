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

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.commit import EitCommit


class EitRepack(EitCommit):
    """
    Main Eit repack command.
    """

    NAME = "repack"
    ALIASES = ["rp"]

    def parse(self):
        """ Overridden from EitCommit """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitRepack.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitRepack.NAME))

        parser.add_argument("packages", nargs='+', metavar="<package>",
                            help=_("package names"))
        parser.add_argument("--in", metavar="<repository>",
                            help=_("repack to given repository"),
                            default=None, dest="into")

        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        # setup atoms variable before spawning commit
        self._packages = nsargs.packages[:]
        self._repackage = self._packages
        return self._call_locked, [self._commit, nsargs.into]

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitRepack,
        EitRepack.NAME,
        _('rebuild packages in repository'))
    )
