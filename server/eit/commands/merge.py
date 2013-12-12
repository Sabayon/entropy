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
from eit.commands.command import EitCommand


class EitMerge(EitCommand):
    """
    Main Eit merge command.
    """

    NAME = "merge"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._merge_branch = None
        self._ask = True

    def _get_parser(self):
        """ Overridden from EitCommit """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitMerge.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitMerge.NAME))

        parser.add_argument("branch", metavar="<branch>",
                            help=_("repository branch"))
        parser.add_argument("--in", metavar="<repository>",
                            help=_("work inside given repository"),
                            default=None, dest="into")
        parser.add_argument("--quick", action="store_true",
                            default=not self._ask,
                            help=_("no stupid questions"))

        return parser

    INTRODUCTION = """\
When a repository is switched to a new branch, remote packages,
for mirror size optimization reasons, are kept in current folders exposing
the old branch as sub-directory and referenced from there until
they get replaced into the repository. At some point in the future btw,
older branches would be dismissed and packages in repository on the
current branch referencing packages in older branches should be merged
back in. This tool does exactly this.
"""

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        """ Overridden from EitCommit """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._ask = not nsargs.quick
        self._merge_branch = nsargs.branch
        return self._call_exclusive, [self._branch, nsargs.into]

    def _branch(self, entropy_server):
        """
        Eit branch code.
        """
        return entropy_server.flushback_packages(
            entropy_server.repository(),
            [self._merge_branch], ask = self._ask)

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitMerge,
        EitMerge.NAME,
        _('merge packages on other branches into current'))
    )
