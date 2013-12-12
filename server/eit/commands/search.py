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


class EitSearch(EitCommand):
    """
    Main Eit search command.
    """

    NAME = "search"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._packages = []
        self._quiet = False
        self._repository_id = None

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitSearch.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitSearch.NAME))

        parser.add_argument("packages", nargs='+', metavar="<package>",
                            help=_("package name"))
        parser.add_argument("--in", metavar="<repository>",
                            help=_("search packages in given repository"),
                            dest="inrepo", default=None)

        parser.add_argument("--quiet", "-q", action="store_true",
           default=self._quiet,
           help=_('quiet output, for scripting purposes'))

        return parser

    INTRODUCTION = """\
Search a package into available repositories (unless *--in* is provided).
For example: *eit search app-foo/bar* will search any package name
containing the given string in its name.
If you are interested in dependency string matching, please see
*eit match*.
"""
    SEE_ALSO = "eit-match(1)"

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        """ Overridden from EitCommand """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError:
            return parser.print_help, []

        self._quiet = nsargs.quiet
        self._packages += nsargs.packages
        self._repository_id = nsargs.inrepo
        return self._call_shared, [self._search, self._repository_id]

    def _search(self, entropy_server):
        """
        Actual Eit search code.
        """
        if self._repository_id is None:
            repository_ids = entropy_server.repositories()
        else:
            repository_ids = [self._repository_id]

        for repository_id in repository_ids:
            repo = entropy_server.open_repository(repository_id)
            count = 0
            for package in self._packages:
                results = repo.searchPackages(
                    package, order_by = "atom")
                for result in results:
                    count += 1
                    print_package_info(
                        result[1],
                        entropy_server,
                        repo,
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
        EitSearch,
        EitSearch.NAME,
        _('search packages in repositories'))
    )
