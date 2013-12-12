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
from entropy.output import darkgreen, brown, purple, blue, darkred
from entropy.transceivers import EntropyTransceiver

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitLock(EitCommand):
    """
    Main Eit lock command.
    """

    NAME = "lock"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._repository_id = None
        self._action_lock = True
        self._client = False
        self._quiet = False
        self._name = EitLock.NAME

    def _get_parser(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitLock.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], self._name))

        parser.add_argument("repo", nargs=1, metavar="<repo>",
                            help=_("repository"))

        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--client", action="store_true", default=False,
            help=_('affect entropy clients only'))
        group.add_argument(
            "--status", action="store_true", default=False,
            help=_('show current status'))

        parser.add_argument("--quiet", "-q", action="store_true",
           default=self._quiet,
           help=_('quiet output, for scripting purposes'))

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
                return
        outcome += ["--client", "--status"]

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
Locking a repository is a way to prevent other Entropy Server
or Entropy Client instances (depending on given switches) from
accessing the remote repository.
In case of Entropy Server locking (default, --client switch not
provided), *eit lock* tries to acquire a remote lock on each configured
mirror that only involves other Entropy Server instances (you won't
be able to update your repositories if you don't own the remote lock).

When --client is provided instead, *eit lock* places a lock on remote
mirrors that prevents Entropy Clients from downloading the repository:
this is just a band aid that avoids users to get broken packages or
repositories.
*eit unlock* does the symmetrical job.
"""
    SEE_ALSO = "eit-unlock(1)"

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

        self._client = nsargs.client
        self._repository_id = nsargs.repo[0]
        self._quiet = nsargs.quiet
        if nsargs.status:
            return self._call_shared, [self._status, None]
        if self._client:
            return self._call_exclusive, [self._client_lock,
                                       self._repository_id]
        else:
            return self._call_exclusive, [self._lock, self._repository_id]

    def _status(self, entropy_server):
        """
        Actual Eit lock|unlock --status code. Just show repo status.
        """
        repositories = entropy_server.repositories()
        if self._repository_id not in repositories:
            entropy_server.output(
                "%s: %s" % (
                    _("Invalid Repository"),
                    self._repository_id),
                level="error",
                importance=1)
            return 1
        if not self._quiet:
            entropy_server.output(
                "%s:" % (darkgreen(_("Mirrors status")),),
                header=brown(" * "))

        dbstatus = entropy_server.Mirrors.mirrors_status(
            self._repository_id)
        for uri, server_lock, client_lock in dbstatus:

            host = EntropyTransceiver.get_uri_name(uri)
            if not self._quiet:
                entropy_server.output(
                    "[%s]" % (purple(host),),
                    header=darkgreen(" @@ "))

            if server_lock:
                lock_str = darkred(_("Locked"))
                quiet_lock_str = "locked"
            else:
                lock_str = darkgreen(_("Unlocked"))
                quiet_lock_str = "unlocked"
            if self._quiet:
                entropy_server.output(
                    "%s server %s" % (host, quiet_lock_str),
                    level="generic")
            else:
                entropy_server.output(
                    "%s: %s" % (blue(_("server")), lock_str),
                    header=brown("  # "))

            if client_lock:
                lock_str = darkred(_("Locked"))
                quiet_lock_str = "locked"
            else:
                lock_str = darkgreen(_("Unlocked"))
                quiet_lock_str = "unlocked"
            if self._quiet:
                entropy_server.output(
                    "%s client %s" % (host, quiet_lock_str),
                    level="generic")
            else:
                entropy_server.output(
                    "%s: %s" % (blue(_("client")), lock_str),
                    header=brown("  # "))

        return 0

    def _lock(self, entropy_server):
        """
        Actual Eit lock code. self._action_lock is determining if it's
        lock or unlock.
        """
        repositories = entropy_server.repositories()
        if self._repository_id not in repositories:
            entropy_server.output(
                "%s: %s" % (
                    _("Invalid Repository"),
                    self._repository_id),
                level="error",
                importance=1)
            return 1

        done = entropy_server.Mirrors.lock_mirrors(
            self._repository_id, self._action_lock,
            quiet = self._quiet)
        if not done:
            return 1
        return 0

    def _client_lock(self, entropy_server):
        """
        Actual Eit lock code (for --client only).
        """
        repositories = entropy_server.repositories()
        if self._repository_id not in repositories:
            entropy_server.output(
                "%s: %s" % (
                    _("Invalid Repository"),
                    self._repository_id),
                level="error",
                importance=1)
            return 1

        done = entropy_server.Mirrors.lock_mirrors_for_download(
            self._repository_id, self._action_lock,
            quiet = self._quiet)
        if not done:
            return 1
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitLock,
        EitLock.NAME,
        _('lock repository'))
    )


class EitUnlock(EitLock):
    """
    Main Eit unlock command.
    """

    NAME = "unlock"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True

    def __init__(self, args):
        EitLock.__init__(self, args)
        self._repository_id = None
        self._action_lock = False
        self._name = EitUnlock.NAME

    INTRODUCTION = """\
Unlocks previously locked repository.
See *eit lock* man page (SEE ALSO section) for more information.
"""
    SEE_ALSO = "eit-lock(1)"

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitUnlock,
        EitUnlock.NAME,
        _('unlock repository'))
    )
