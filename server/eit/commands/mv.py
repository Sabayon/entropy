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

    def _get_parser(self):
        """ Overridden from EitMv """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitMv.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitMv.NAME))

        parser.add_argument("source", metavar="<source>",
                            help=_("source repository"))
        parser.add_argument("dest", metavar="<dest>",
                            help=_("destination repository"))
        parser.add_argument("--conservative", action="store_true",
                            help=_("do not execute implicit package name "
                                   "and slot updates"),
                            default=self._conservative)
        parser.add_argument("--deps", action="store_true",
                            default=False,
                            help=_("include dependencies"))
        parser.add_argument("packages", nargs='*', metavar="<package>",
                           help=_("package names (all if none)"),
                            default=None)

        return parser

    INTRODUCTION = """\
Move packages from source repository to destination repository.
The operation is transactional, first package is copied to destination,
then is removed from source.
"""
    SEE_ALSO = "eit-cp(1)"

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._source = nsargs.source
        self._dest = nsargs.dest
        self._deps = nsargs.deps
        self._packages += nsargs.packages
        self._copy = False
        self._entropy_class()._inhibit_treeupdates = nsargs.conservative

        return self._call_locked, [self._move_copy, self._source]


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitMv,
        EitMv.NAME,
        _('move packages from a repository to another'))
    )
