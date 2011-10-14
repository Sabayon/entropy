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
        # text_query import augh
        from text_query import print_package_info
        self._pprinter = print_package_info
        self._repository_id = None

    def parse(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitMatch.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitMatch.NAME))

        parser.add_argument("packages", nargs='+', metavar="<package>",
                            help=_("package name"))
        parser.add_argument("--in", metavar="<repository>",
                            help=_("search packages in given repository"),
                            dest="inrepo", default=None)

        parser.add_argument("--quiet", action="store_true",
           default=self._quiet,
           help=_('quiet output, for scripting purposes'))

        try:
            nsargs = parser.parse_args(self._args)
        except IOError:
            return parser.print_help, []

        self._quiet = nsargs.quiet
        self._packages += nsargs.packages
        self._repository_id = nsargs.inrepo
        return self._call_unlocked, [self._match, self._repository_id]

    def _match(self, entropy_server):
        """
        Actual Eit match code.
        """
        if self._repository_id is None:
            repository_ids = entropy_server.repositories()
        else:
            repository_ids = [self._repository_id]

        for repository_id in repository_ids:
            repo = entropy_server.open_repository(repository_id)
            count = 0
            for package in self._packages:
                pkg_id, pkg_rc = repo.atomMatch(package)
                if pkg_id == -1:
                    continue

                count += 1
                self._pprinter(
                    pkg_id,
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
        EitMatch,
        EitMatch.NAME,
        _('match packages in repositories'))
    )
