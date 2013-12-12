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
from entropy.output import purple

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand
from eit.utils import print_package_info


class EitMatch(EitCommand):
    """
    Main Eit match command.
    """

    NAME = "match"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._packages = []
        self._quiet = False

    def _get_parser(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitMatch.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitMatch.NAME))

        parser.add_argument("packages", nargs='+', metavar="<package>",
                            help=_("package name"))

        parser.add_argument("--quiet", "-q", action="store_true",
           default=self._quiet,
           help=_('quiet output, for scripting purposes'))

        return parser

    INTRODUCTION = """\
Match a dependency string against the available repositories.
For example: *eit match app-foo/bar:2::repo* will match any version
of app-foo/bar having SLOT=2 in the "repo" repository.
If you are interested in a simple text search, please see *eit search*.
"""
    SEE_ALSO = "eit-search(1)"

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError:
            return parser.print_help, []

        self._quiet = nsargs.quiet
        self._packages += nsargs.packages
        return self._call_shared, [self._match, None]

    def _match(self, entropy_server):
        """
        Actual Eit match code.
        """
        count = 0
        for package in self._packages:
            pkg_id, pkg_repo = entropy_server.atom_match(package)
            if pkg_id == -1:
                continue

            count += 1
            print_package_info(
                pkg_id,
                entropy_server,
                entropy_server.open_repository(pkg_repo),
                installed_search = True,
                extended = True,
                quiet = self._quiet
            )

        if not count and not self._quiet:
            entropy_server.output(
                purple(_("Nothing found")),
                importance=1, level="warning")
        return 0


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitMatch,
        EitMatch.NAME,
        _('match packages in repositories'))
    )
