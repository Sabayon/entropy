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


class EitAdd(EitCommit):
    """
    Main Eit add command.
    """

    NAME = "add"
    ALIASES = []

    INTRODUCTION = """\
Selectively add unstaged packages to repository.
If you are familiar with git, this maps to *git commit <path>*.
Packages in the repository sharing the same scope are going to
be replaced, unless marked as (manually) injected.
Entropy package scope is given by the following tuple:
    (*package key*, *package slot*, *package tag*)
"""
    SEE_ALSO = "eit-commit(1), eit-repack(1)"

    def _get_parser(self):
        """ Overridden from EitCommit """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitAdd.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitAdd.NAME))

        parser.add_argument("packages", nargs='+', metavar="<package>",
                            help=_("package names"))
        parser.add_argument("--conservative", action="store_true",
                            help=_("do not execute implicit package name "
                                   "and slot updates"),
                            default=self._conservative)
        parser.add_argument("--to", metavar="<repository>",
                            help=_("add to given repository"),
                            default=None)
        parser.add_argument("--quick", action="store_true",
                            default=not self._ask,
                            help=_("no stupid questions"))
        return parser

    def parse(self):
        """ Overridden from EitCommit """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        # setup atoms variable before spawning commit
        self._ask = not nsargs.quick
        self._entropy_class()._inhibit_treeupdates = nsargs.conservative
        self._packages = nsargs.packages[:]
        return self._call_exclusive, [self._commit, nsargs.to]

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitAdd,
        EitAdd.NAME,
        _('commit to repository the provided packages'))
    )
