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
from entropy.output import darkred, red, brown, purple, teal, blue, \
    darkgreen, bold
from entropy.misc import ParallelTask
from entropy.const import etpConst, const_debug_write
from entropy.services.client import WebService

import entropy.tools

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand

class SoloRepo(SoloCommand):
    """
    Main Solo Repo command.
    """

    NAME = "repo"
    ALIASES = []
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Manage Entropy Repositories.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._nsargs = None

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        self._real_command = sys.argv[0]
        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloRepo.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloRepo.NAME))

        subparsers = parser.add_subparsers(
            title="action", description=_("manage repositories"),
            help=_("available commands"))

        enable_parser = subparsers.add_parser("enable",
            help=_("enable repositories"))
        enable_parser.add_argument("repo", nargs='+',
                                   metavar="<repo>",
                                   help=_("repository name"))
        enable_parser.set_defaults(func=self._enable)

        disable_parser = subparsers.add_parser("disable",
            help=_("disable repositories"))
        disable_parser.add_argument("repo", nargs='+',
                                    metavar="<repo>",
                                    help=_("repository name"))
        disable_parser.set_defaults(func=self._disable)

        return parser

    def parse(self):
        """
        Parse command
        """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._nsargs = nsargs
        return self._call_locked, [nsargs.func]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        import sys

        entropy_client = self._entropy_bashcomp()
        repos = entropy_client.repositories()
        outcome = ["--force"] + repos
        return self._bashcomp(sys.stdout, last_arg, outcome)

    def _enable(self, entropy_client):
        """
        Solo Repo Enable command.
        """
        exit_st = 0
        for repo in self._nsargs.repo:
            _exit_st = self._enable_repo(entropy_client, repo)
            if _exit_st != 0:
                exit_st = _exit_st

        return exit_st

    def _enable_repo(self, entropy_client, repo):
        """
        Solo Repo Enable for given repository.
        """
        settings = entropy_client.Settings()
        excluded_repos = settings['repositories']['excluded']
        available_repos = settings['repositories']['available']

        if repo in available_repos:
            entropy_client.output(
                "[%s] %s" % (
                    purple(repo),
                    blue(_("repository already enabled")),),
                level="warning", importance=1)
            return 1

        if repo not in excluded_repos:
            entropy_client.output(
                "[%s] %s" % (
                    purple(repo),
                    blue(_("repository not available")),),
                level="warning", importance=1)
            return 1

        enabled = entropy_client.enable_repository(repo)
        if enabled:
            entropy_client.output(
                "[%s] %s" % (
                    teal(repo),
                    blue(_("repository enabled")),))
            return 0

        entropy_client.output(
            "[%s] %s" % (
                purple(repo),
                blue(_("cannot enable repository")),),
            level="warning", importance=1)
        return 1

    def _disable(self, entropy_client):
        """
        Solo Repo Disable command.
        """
        exit_st = 0
        for repo in self._nsargs.repo:
            _exit_st = self._disable_repo(entropy_client, repo)
            if _exit_st != 0:
                exit_st = _exit_st

        return exit_st

    def _disable_repo(self, entropy_client, repo):
        """
        Solo Repo Disable for given repository.
        """
        settings = entropy_client.Settings()
        excluded_repos = settings['repositories']['excluded']
        available_repos = settings['repositories']['available']

        if repo in excluded_repos:
            entropy_client.output(
                "[%s] %s" % (
                    purple(repo),
                    blue(_("repository already disabled")),),
                level="warning", importance=1)
            return 1

        if repo not in available_repos:
            entropy_client.output(
                "[%s] %s" % (
                    purple(repo),
                    blue(_("repository not available")),),
                level="warning", importance=1)
            return 1

        disabled = False
        try:
            disabled = entropy_client.disable_repository(repo)
        except ValueError:
            entropy_client.output(
                "[%s] %s" % (
                    purple(repo),
                    blue(_("cannot disable repository")),),
                level="warning", importance=1)
            return 1

        if disabled:
            entropy_client.output(
                "[%s] %s" % (
                    teal(repo),
                    blue(_("repository disabled")),))
            return 0

        entropy_client.output(
            "[%s] %s" % (
                purple(repo),
                blue(_("cannot disable repository")),),
            level="warning", importance=1)
        return 1


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloRepo,
        SoloRepo.NAME,
        _("manage repositories"))
    )
