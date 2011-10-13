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
from entropy.output import darkgreen, teal
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

    def parse(self):
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
        deps_parser.add_argument("repo", nargs='?', default=None,
                            metavar="<repo>", help=_("repository"))
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

        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        self._nsargs = nsargs
        return self._call_locked, [nsargs.func, None]

    def _deptest(self, entropy_server):
        entropy_server.extended_dependencies_test(
            entropy_server.repositories())
        return 0

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


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitTest,
        EitTest.NAME,
        _('run QA tests'))
    )
