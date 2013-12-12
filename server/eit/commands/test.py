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
from entropy.output import teal, purple
from entropy.server.interfaces import Server

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitTest(EitCommand):
    """
    Main Eit test command.
    """

    NAME = "test"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._nsargs = None
        self._ask = False

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitTest.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitTest.NAME))

        subparsers = parser.add_subparsers(
            title="test", description=_("run given test"),
            help=_("available tests"))

        deps_parser = subparsers.add_parser("deps",
            help=_("dependencies test"))
        deps_parser.set_defaults(func=self._deptest)

        libs_parser = subparsers.add_parser("libs",
            help=_("libraries test"))
        libs_parser.add_argument("--dump", action="store_true",
            default=False, help=_("dump results to file"))
        libs_parser.set_defaults(func=self._libtest)

        links_parser = subparsers.add_parser("links",
            help=_("library linking test (using repository metadata)"))
        links_parser.add_argument("excllibs", nargs='*', default=None,
                                  metavar="<excluded lib>",
                                  help=_("excluded soname"))
        links_parser.set_defaults(func=self._linktest)

        pkglibs_parser = subparsers.add_parser("pkglibs",
            help=_("library linking test (using live system)"))
        pkglibs_parser.add_argument("packages", nargs='+', default=None,
                                  metavar="<package>",
                                  help=_("package names"))
        pkglibs_parser.set_defaults(func=self._pkglibs)

        pkgs_parser = subparsers.add_parser("local",
            help=_("verify local packages integrity"))
        pkgs_parser.add_argument("repo", nargs='?', default=None,
                                 metavar="<repo>", help=_("repository"))
        pkgs_parser.add_argument("--quick", action="store_true",
                                 default=not self._ask,
                                 help=_("no stupid questions"))
        pkgs_parser.set_defaults(func=self._pkgtest)

        rempkgs_parser = subparsers.add_parser("remote",
            help=_("verify remote packages integrity"))
        rempkgs_parser.add_argument("repo", nargs='?', default=None,
                                    metavar="<repo>", help=_("repository"))
        rempkgs_parser.add_argument("--quick", action="store_true",
                                    default=not self._ask,
                                    help=_("no stupid questions"))
        rempkgs_parser.set_defaults(func=self._rem_pkgtest)

        return parser

    INTRODUCTION = """\
Toolset containing all the Entropy Server built-in QA tests available.
"""

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
        except IOError as err:
            return parser.print_help, []

        # Python 3.3 bug #16308
        if not hasattr(nsargs, "func"):
            return parser.print_help, []

        self._nsargs = nsargs
        return self._call_exclusive, [nsargs.func, None]

    def _deptest(self, entropy_server):
        missing_deps = entropy_server.extended_dependencies_test(
            entropy_server.repositories())
        if not missing_deps:
            return 0
        return 1

    def _libtest(self, entropy_server):
        rc = entropy_server.test_shared_objects(
            entropy_server.repository(),
            dump_results_to_file = self._nsargs.dump)
        return rc

    def _linktest(self, entropy_server):
        srv_set = self._settings()[Server.SYSTEM_SETTINGS_PLG_ID]['server']
        base_repository_id = srv_set['base_repository_id']
        qa = entropy_server.QA()
        rc = 0
        for repository_id in entropy_server.repositories():
            repo = entropy_server.open_repository(repository_id)
            found_something = qa.test_missing_runtime_libraries(
                entropy_server,
                [(x, repository_id) for x in repo.listAllPackageIds()],
                base_repository_id = base_repository_id,
                excluded_libraries = self._nsargs.excllibs)
            if found_something:
                rc = 1
        return rc

    def _pkglibs(self, entropy_server):
        pkg_matches = []
        for package in self._nsargs.packages:
            pkg_id, pkg_repo = entropy_server.atom_match(package)
            if pkg_id == -1:
                entropy_server.output(
                    "%s: %s" % (
                        purple(_("Not matched")), teal(package)),
                    level="error", importance=1)
                return 1
            pkg_matches.append((pkg_id, pkg_repo))

        entropy_server.missing_runtime_dependencies_test(
            pkg_matches, bump_packages = True)
        return 0

    def _pkgtest(self, entropy_server):
        repository_id = self._nsargs.repo
        if repository_id is None:
            repository_id = entropy_server.repository()
        if repository_id not in entropy_server.repositories():
            entropy_server.output(
                "%s: %s" % (
                    purple(_("Invalid repository")),
                    teal(repository_id)),
                importance=1, level="error")
            return 1

        fine, failed, dl_fine, dl_err = \
            entropy_server._verify_local_packages(
                repository_id, [], ask = not self._nsargs.quick)
        if failed:
            return 1
        return 0

    def _rem_pkgtest(self, entropy_server):
        repository_id = self._nsargs.repo
        if repository_id is None:
            repository_id = entropy_server.repository()
        entropy_server._verify_remote_packages(repository_id, [],
            ask = self._ask)
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitTest,
        EitTest.NAME,
        _('run QA tests'))
    )
