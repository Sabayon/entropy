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
import tempfile
import codecs

from entropy.const import etpConst, const_convert_to_unicode
from entropy.exceptions import OnlineMirrorError, RepositoryError
from entropy.i18n import _
from entropy.output import darkgreen, teal, red, darkred, brown, blue, \
    bold, purple
from entropy.transceivers import EntropyTransceiver
from entropy.server.interfaces import ServerSystemSettingsPlugin
from entropy.server.interfaces.rss import ServerRssMetadata
from entropy.client.interfaces.db import InstalledPackagesRepository

import entropy.tools

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand
from eit.commands.push import EitPush


class EitPull(EitCommand):
    """
    Main Eit reset command.
    """

    NAME = "pull"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._ask = True
        self._pretend = False
        self._all = False
        self._repositories = []
        self._cleanup_only = False
        self._conservative = False

    def _get_parser(self):
        self._real_command = sys.argv[0]
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitPull.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitPull.NAME))

        parser.add_argument("repo", nargs='?', default=None,
                            metavar="<repo>", help=_("repository"))
        parser.add_argument("--conservative", action="store_true",
                            help=_("do not execute implicit package name "
                                   "and slot updates"),
                            default=self._conservative)
        parser.add_argument("--quick", action="store_true",
                            default=False,
                            help=_("no stupid questions"))
        parser.add_argument("--pretend", action="store_true",
                            default=False,
                            help=_("show what would be done"))

        group = parser.add_mutually_exclusive_group()
        group.add_argument("--all", action="store_true",
                            default=False,
                            help=_("pull all the repositories"))

        return parser

    def bashcomp(self, last_arg):
        """
        Overridden from EitCommand
        """
        import sys

        entropy_server = self._entropy(handle_uninitialized=False,
                                       installed_repo=-1)
        outcome = entropy_server.repositories()
        for arg in self._args:
            if arg in outcome:
                outcome = []
                break
        outcome += ["--conservative", "--quick", "--all"]

        def _startswith(string):
            if last_arg is not None:
                if last_arg not in outcome:
                    return string.startswith(last_arg)
            return True

        if self._args:
            # only filter out if last_arg is actually
            # something after this.NAME.
            outcome = sorted(filter(_startswith, outcome))

        for arg in self._args:
            if arg in outcome:
                outcome.remove(arg)

        sys.stdout.write(" ".join(outcome) + "\n")
        sys.stdout.flush()

    INTRODUCTION = """\
Synchronize remote mirrors with local repository content (packages and
repository) by pulling updated data.
"""

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._ask = not nsargs.quick
        self._all = nsargs.all
        if nsargs.repo is not None:
            self._repositories.append(nsargs.repo)
        self._pretend = nsargs.pretend
        self._entropy_class()._inhibit_treeupdates = nsargs.conservative

        return self._call_exclusive, [self._pull, nsargs.repo]

    def _pull(self, entropy_server):
        """
        Main Eit push code.
        """
        if not self._repositories and (not self._all):
            # pick default if none specified
            self._repositories.append(entropy_server.repository())
        if not self._repositories and self._all:
            self._repositories.extend(entropy_server.repositories())

        for repository_id in self._repositories:
            # avoid __default__
            if repository_id == InstalledPackagesRepository.NAME:
                continue
            rc = self._pull_repo(entropy_server, repository_id)
            if rc != 0:
                return rc

        return 0

    def _pull_repo(self, entropy_server, repository_id):
        """
        Pull the damn repository.
        """
        rc = 0
        if not self._cleanup_only:
            rc = self.__pull_repo(entropy_server, repository_id)
        return rc

    def __sync_repo(self, entropy_server, repository_id):
        EitPush.print_repository_status(entropy_server, repository_id)
        try:
            sts = entropy_server.Mirrors.sync_repository(
                repository_id, enable_upload = False,
                enable_download = True)
        except OnlineMirrorError as err:
            entropy_server.output(
                "%s: %s" % (darkred(_("Error")), err.value),
                importance=1, level="error")
            return 1

        # try (best-effort) to generate the index of the newly
        # downloaded repository (indexing=True).
        repo = None
        try:
            if sts == 0:
                repo = entropy_server.open_server_repository(
                    repository_id, read_only=False, indexing=True,
                    lock_remote=False, do_treeupdates=False)
        except RepositoryError:
            repo = None
        finally:
            if repo is not None:
                repo.commit()
                entropy_server.close_repository(repo)

        EitPush.print_repository_status(entropy_server, repository_id)
        return sts

    def __pull_repo(self, entropy_server, repository_id):

        sts = self.__sync_repo(entropy_server, repository_id)
        if sts != 0:
            entropy_server.output(red(_("Aborting !")),
                importance=1, level="error", header=darkred(" !!! "))
            return sts

        mirrors_tainted, mirrors_errors, successfull_mirrors, \
            broken_mirrors, check_data = \
                entropy_server.Mirrors.sync_packages(
                    repository_id, ask = self._ask,
                    pretend = self._pretend)

        if mirrors_errors and not successfull_mirrors:
            entropy_server.output(red(_("Aborting !")),
                importance=1, level="error", header=darkred(" !!! "))
            return 1
        if not successfull_mirrors:
            return 0

        if self._ask:
            q_rc = entropy_server.ask_question(
                _("Should I cleanup old packages on mirrors ?"))
            if q_rc == _("No"):
                return 0
            # fall through

        done = entropy_server.Mirrors.tidy_mirrors(
            repository_id, ask = self._ask, pretend = self._pretend)
        if not done:
            return 1
        return 0


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitPull,
        EitPull.NAME,
        _('pull repository packages and metadata'))
    )
