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
from entropy.output import blue, darkgreen, purple, teal
from entropy.server.interfaces import RepositoryConfigParser

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand
from eit.utils import print_table


class EitRepo(EitCommand):
    """
    Main Eit repo command.
    """

    NAME = "repo"
    ALIASES = []
    ALLOW_UNPRIVILEGED = False

    def __init__(self, args):
        super(EitRepo, self).__init__(args)
        self._nsargs = None

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitRepo.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitRepo.NAME))

        subparsers = parser.add_subparsers(
            title="action", description=_("manage repositories"),
            help=_("available commands"))

        show_parser = subparsers.add_parser(
            "show", help=_("show repositories and mirrors status"))
        show_parser.set_defaults(func=self._show)

        add_parser = subparsers.add_parser(
            "add", help=_("add a repository"))
        add_parser.add_argument(
            "id", metavar="<repository>",
            help=_("repository name"))
        add_parser.add_argument(
            "--desc", metavar="<description>", required=True,
            help=_("repository description"))
        add_parser.add_argument(
            "--repo", nargs='+',
            metavar="<repo uri>", required=True,
            help=_("synchronization URI for both packages and database"))
        add_parser.add_argument(
            "--repo-only", nargs='*', default=[],
            metavar="<database only uri>",
            help=_("synchronization URI for database only"))
        add_parser.add_argument(
            "--pkg-only", nargs='*', default=[],
            metavar="<packages only uri>",
            help=_("synchronization URI for packages only"))
        add_parser.add_argument(
            "--base", action="store_true", default=None,
            help=_("set this to make this repository the "
                   "'base' for all the others"))
        add_parser.set_defaults(func=self._add)

        remove_parser = subparsers.add_parser("remove",
            help=_("remove a repository"))
        remove_parser.add_argument(
            "id", nargs='+',
            metavar="<repository>",
            help=_("repository name"))
        remove_parser.set_defaults(func=self._remove)

        return parser

    INTRODUCTION = """\
Manage Entropy Server Repositories.
"""
    SEE_ALSO = "eit-status(1)"

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
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        # Python 3.3 bug #16308
        if not hasattr(nsargs, "func"):
            return parser.print_help, []

        self._nsargs = nsargs
        return self._call_exclusive, [nsargs.func, None]

    def _show(self, entropy_server):
        entropy_server._show_interface_status()
        entropy_server.Mirrors._show_interface_status(
            entropy_server.repository())
        return 0

    def _add(self, entropy_server):
        """
        Eit Repo Add command.
        """
        current_repos = entropy_server.repositories()
        repository_id = self._nsargs.id
        desc = self._nsargs.desc
        repos = self._nsargs.repo
        pkg_only = self._nsargs.pkg_only
        repo_only = self._nsargs.repo_only
        base = self._nsargs.base

        if repository_id in current_repos:
            entropy_server.output(
                "[%s] %s" % (
                    purple(repository_id),
                    blue(_("repository already configured")),),
                level="error", importance=1)
            return 1

        toc = []
        toc.append((
                purple(_("Repository id:")),
                teal(repository_id)))
        toc.append((
                darkgreen(_("Description:")),
                teal(desc)))
        base_str = _("Yes")
        if base is None:
            base_str = _("Unset")
        elif not base:
            base_str = _("No")
        toc.append((
                darkgreen(_("Base repository:")),
                teal(base_str)))

        for uri in repos:
            toc.append((purple(_("Packages + Database URI:")), uri))
        for uri in repo_only:
            toc.append((purple(_("Database only URI:")), uri))
        for uri in pkg_only:
            toc.append((purple(_("Packages only URI:")), uri))

        toc.append(" ")
        print_table(entropy_server, toc)

        parser = RepositoryConfigParser()
        added = parser.add(repository_id, desc, repos,
                           repo_only, pkg_only, base)
        if added:
            entropy_server.output(
                "[%s] %s" % (
                    purple(repository_id),
                    blue(_("repository added succesfully")),))
        else:
            entropy_server.output(
                "[%s] %s" % (
                    purple(repository_id),
                    blue(_("cannot add repository")),),
                level="warning", importance=1)

        return 0

    def _remove(self, entropy_server):
        """
        Eit Repo Remove command.
        """
        current_repos = entropy_server.repositories()

        exit_st = 0
        for repository_id in self._nsargs.id:

            if repository_id not in current_repos:
                entropy_server.output(
                    "[%s] %s" % (
                        purple(repository_id),
                        blue(_("repository not available")),),
                    level="warning", importance=1)
                exit_st = 1
                continue

            parser = RepositoryConfigParser()
            removed = parser.remove(repository_id)
            if not removed:
                exit_st = 1
                entropy_server.output(
                    "[%s] %s" % (
                        purple(repository_id),
                        blue(_("cannot remove repository")),),
                    level="warning", importance=1)
            else:
                entropy_server.output(
                    "[%s] %s" % (
                        purple(repository_id),
                        blue(_("repository removed succesfully")),))

        return exit_st


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitRepo,
        EitRepo.NAME,
        _("manage repositories"))
    )
