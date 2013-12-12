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
from entropy.output import purple, darkgreen, brown, teal

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitRemove(EitCommand):
    """
    Main Eit remove command.
    """

    NAME = "remove"
    ALIASES = ["rm"]

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._packages = []
        self._from = None
        self._nodeps = False
        self._ask = True

    def _get_parser(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitRemove.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitRemove.NAME))

        parser.add_argument("packages", nargs='+', metavar="<package>",
                            help=_("package name"))
        parser.add_argument("--from", metavar="<repository>",
                            help=_("remove from given repository"),
                            dest="fromrepo", default=None)
        parser.add_argument("--nodeps", action="store_true",
                            help=_("do not include reverse dependencies"),
                            dest="nodeps", default=self._nodeps)
        parser.add_argument("--quick", action="store_true",
                            default=not self._ask,
                            help=_("no stupid questions"))

        return parser

    INTRODUCTION = """\
Remove a package from repository. It's no-brainer actually.
"""
    SEE_ALSO = "eit-add(1)"

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

        self._ask = not nsargs.quick
        self._nodeps = nsargs.nodeps
        self._from = nsargs.fromrepo
        self._packages += nsargs.packages
        return self._call_exclusive, [self._remove, self._from]

    def _remove(self, entropy_server):
        """
        Actual Eit remove code.
        """
        repository_id = entropy_server.repository()
        repo = entropy_server.open_repository(repository_id)
        pkg_matches = []
        for package in self._packages:
            pkg = repo.atomMatch(package, multiMatch = True)
            for pkg_id in pkg[0]:
                pkg_match = (pkg_id, repository_id)
                if pkg_match not in pkg_matches:
                    pkg_matches.append(pkg_match)

        if not pkg_matches:
            entropy_server.output(
                purple(_("No packages found")),
                importance=1, level="error")
            return 1

        if not self._nodeps:
            pkg_matches = entropy_server.get_reverse_queue(pkg_matches,
                system_packages = False)

        entropy_server.output(
            darkgreen(
                _("These are the packages that would be removed") + ":"),
            importance=1, header=brown(" @@ "))

        repo_map = {}
        for pkg_id, repo_id in pkg_matches:
            repo = entropy_server.open_repository(repo_id)
            pkgatom = repo.retrieveAtom(pkg_id)
            entropy_server.output(
                "[%s] %s" % (teal(repo_id), purple(pkgatom)),
                header=brown("   # "))
            obj = repo_map.setdefault(repo_id, [])
            obj.append(pkg_id)

        if self._ask:
            resp = entropy_server.ask_question(
                _("Would you like to continue ?"))
            if resp == _("No"):
                return 0

        for repo_id, pkg_ids in repo_map.items():
            entropy_server.remove_packages(repo_id, pkg_ids)

        return 0


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitRemove,
        EitRemove.NAME,
        _('remove packages from repository'))
    )
