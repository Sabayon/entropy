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
from eit.commands.cp import EitCp


class EitMv(EitCp):
    """
    Main Eit mv command.
    """

    NAME = "mv"
    ALIASES = []

    def parse(self):
        """ Overridden from EitMv """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitMv.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitMv.NAME))

        parser.add_argument("source", nargs=1,
                            metavar="<source>",
                            help=_("source repository"))
        parser.add_argument("dest", nargs=1,
                            metavar="<dest>",
                            help=_("destination repository"))
        parser.add_argument("--deps", action="store_true",
                            default=False,
                            help=_("include dependencies"))
        parser.add_argument("package", nargs='+', metavar="<package>",
                            help=_("package dependency"))

        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        self._source = nsargs.source[0]
        self._dest = nsargs.dest[0]
        self._deps = nsargs.deps
        self._packages += nsargs.package
        self._copy = False
        return self._call_locked, [self._move_copy, self._source]


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitMv,
        EitMv.NAME,
        _('move packages from a repository to another'))
    )
