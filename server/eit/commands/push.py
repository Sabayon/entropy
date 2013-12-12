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
import codecs

from entropy.const import etpConst, const_convert_to_unicode, \
    const_mkstemp
from entropy.exceptions import OnlineMirrorError
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


class EitPush(EitCommand):
    """
    Main Eit reset command.
    """

    NAME = "push"
    ALIASES = ["sync"]
    DEFAULT_REPO_COMMIT_MSG = const_convert_to_unicode("""
# This is Entropy Server repository commit message handler.
# Please friggin' enter the commit message for your changes. Lines starting
# with '#' will be ignored. To avoid encoding issue, write stuff in plain ASCII.
""")

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._ask = True
        self._pretend = False
        self._all = False
        self._force = False
        self._repositories = []
        self._cleanup_only = False
        self._as_repository_id = None
        self._conservative = False

    def _get_parser(self):
        self._real_command = sys.argv[0]
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitPush.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitPush.NAME))

        parser.add_argument("repo", nargs='?', default=None,
                            metavar="<repo>", help=_("repository"))
        parser.add_argument("--conservative", action="store_true",
                            help=_("do not execute implicit package name "
                                   "and slot updates"),
                            default=self._conservative)
        parser.add_argument("--quick", action="store_true",
                            default=False,
                            help=_("no stupid questions"))
        parser.add_argument("--force", action="store_true",
                            default=False,
                            help=_("force push in case of QA errors"))

        group = parser.add_mutually_exclusive_group()
        group.add_argument("--all", action="store_true",
                            default=False,
                            help=_("push all the repositories"))
        group.add_argument("--as", metavar="<repo>", default=None,
                           help=_("push as fake repository"),
                           dest="asrepo")
        parser.add_argument("--pretend", action="store_true",
                            default=False,
                            help=_("show what would be done"))

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
                # already given a repo
                if last_arg != "--as":
                    outcome = []
                    break
        outcome += ["--conservative", "--quick", "--all", "--as", "--force"]

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
repository) by pushing updated data.
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
        self._as_repository_id = nsargs.asrepo
        self._pretend = nsargs.pretend
        self._force = nsargs.force
        self._entropy_class()._inhibit_treeupdates = nsargs.conservative

        return self._call_exclusive, [self._push, nsargs.repo]

    def _push(self, entropy_server):
        """
        Main Eit push code.
        """
        if not self._repositories and (not self._all):
            # pick default if none specified
            self._repositories.append(entropy_server.repository())
        if not self._repositories and self._all:
            self._repositories.extend(entropy_server.repositories())

        for repository_id in self._repositories:
            # avoid __system__
            if repository_id == InstalledPackagesRepository.NAME:
                continue
            rc = self._push_repo(entropy_server, repository_id)
            if rc != 0:
                return rc

        return 0

    def _push_repo(self, entropy_server, repository_id):
        """
        Push the damn repository.
        """
        rc = 0
        if not self._cleanup_only:
            rc = self.__push_repo(entropy_server, repository_id)
        return rc

    def _commit_message(self, entropy_server, successfull_mirrors):
        """
        Ask user to enter the commit message for data being pushed.
        Store inside rss metadata object.
        """
        enc = etpConst['conf_encoding']
        tmp_fd, tmp_commit_path = const_mkstemp(
            prefix="eit._push", suffix=".COMMIT_MSG")
        with entropy.tools.codecs_fdopen(tmp_fd, "w", enc) as tmp_f:
            tmp_f.write(EitPush.DEFAULT_REPO_COMMIT_MSG)
            if successfull_mirrors:
                tmp_f.write(const_convert_to_unicode(
                        "# Changes to be committed:\n"))
            for sf_mirror in sorted(successfull_mirrors):
                tmp_f.write(const_convert_to_unicode(
                        "#\t updated:   %s\n" % (sf_mirror,)))

        # spawn editor
        cm_msg_rc = entropy_server.edit_file(tmp_commit_path)
        commit_msg = None
        if not cm_msg_rc:
            # wtf?, fallback to old way
            def fake_callback(*args, **kwargs):
                return True

            input_params = [
                ('message', _("Commit message"), fake_callback, False)]
            commit_data = entropy_server.input_box(
                _("Enter the commit message"),
                input_params, cancel_button = True)
            if commit_data:
                commit_msg = const_convert_to_unicode(commit_data['message'])
        else:
            commit_msg = const_convert_to_unicode("")
            with codecs.open(tmp_commit_path, "r", encoding=enc) as tmp_f:
                for line in tmp_f.readlines():
                    if line.strip().startswith("#"):
                        continue
                    commit_msg += line
            entropy_server.output(commit_msg)

        os.remove(tmp_commit_path)
        return commit_msg

    @staticmethod
    def print_repository_status(entropy_server, repository_id):
        remote_db_status = entropy_server.Mirrors.remote_repository_status(
            repository_id)

        entropy_server.output(
            "%s:" % (brown(_("Entropy Repository Status")),),
            importance=1,
            header=darkgreen(" * ")
        )
        for url, revision in remote_db_status.items():
            host = EntropyTransceiver.get_uri_name(url)
            entropy_server.output(
                "%s: %s" % (darkgreen(_("Host")), bold(host)),
                header="    ")
            entropy_server.output(
                "%s: %s" % (purple(_("Remote")), blue(str(revision))),
                header="    ")

        local_revision = entropy_server.local_repository_revision(
            repository_id)
        entropy_server.output(
            "%s: %s" % (brown(_("Local")), teal(str(local_revision))),
            header="    ")

    def __sync_repo(self, entropy_server, repository_id):
        EitPush.print_repository_status(entropy_server, repository_id)
        # do the actual sync
        try:
            sts = entropy_server.Mirrors.sync_repository(
                repository_id, enable_upload = True,
                enable_download = False, force = self._force)
        except OnlineMirrorError as err:
            entropy_server.output(
                "%s: %s" % (darkred(_("Error")), err.value),
                importance=1, level="error")
            return 1
        EitPush.print_repository_status(entropy_server, repository_id)
        return sts

    def __push_repo(self, entropy_server, repository_id):
        sys_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        srv_data = self._settings()[sys_settings_plugin_id]['server']
        rss_enabled = srv_data['rss']['enabled']

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

        if mirrors_tainted and (self._as_repository_id is None):

            commit_msg = None
            if self._ask and rss_enabled:
                # expected unicode out of here
                commit_msg = self._commit_message(entropy_server,
                                               successfull_mirrors)
            elif rss_enabled:
                commit_msg = const_convert_to_unicode("Automatic update")

            if commit_msg is None:
                commit_msg = const_convert_to_unicode("no commit message")
            ServerRssMetadata()['commitmessage'] = commit_msg

        if self._as_repository_id is not None:
            # change repository push location
            ServerSystemSettingsPlugin.set_override_remote_repository(
                self._settings(), repository_id, self._as_repository_id)

        sts = self.__sync_repo(entropy_server, repository_id)
        if sts == 0:
            # do not touch locking
            entropy_server.Mirrors.lock_mirrors(repository_id, False,
                unlock_locally = (self._as_repository_id is None))

        if sts != 0:
            entropy_server.output(red(_("Aborting !")),
                importance=1, level="error", header=darkred(" !!! "))
            return sts

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
        EitPush,
        EitPush.NAME,
        _('push repository packages and metadata'))
    )
