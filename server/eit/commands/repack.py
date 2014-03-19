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

from entropy.i18n import _

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.commit import EitCommit


class EitRepack(EitCommit):
    """
    Main Eit repack command.
    """

    NAME = "repack"
    ALIASES = ["rp"]

    INTRODUCTION = """\
Recrate the whole Entropy package from live system through
the Source Package Manager. This allows the latter to regenerate
its metadata (useful in case of dependency changes).
The package must be already available in the queried repository.
"""
    SEE_ALSO = "eit-add(1), eit-commit(1)"

    def _get_parser(self):
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
        return parser

    def parse(self):
        """ Overridden from EitCommit """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        # setup atoms variable before spawning commit
        self._repackage = nsargs.packages[:]
        return self._call_exclusive, [self._commit, nsargs.into]

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitRepack,
        EitRepack.NAME,
        _('rebuild packages in repository'))
    )
