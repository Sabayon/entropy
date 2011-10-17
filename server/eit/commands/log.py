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
import subprocess
import argparse

from entropy.i18n import _

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitLog(EitCommand):
    """
    Main Eit log command.
    """

    NAME = "log"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True

    def _get_parser(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitLog.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitLog.NAME))

        parser.add_argument("repo", nargs='?', default=None,
                            metavar="<repo>", help=_("repository"))

        return parser

    def parse(self):
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        return self._call_locked, [self._log, nsargs.repo]

    def _log(self, entropy_server):
        changelog_path = \
            entropy_server._get_local_repository_compressed_changelog_file(
                entropy_server.repository())

        if not (os.path.isfile(changelog_path) and \
                    os.access(changelog_path, os.R_OK)):
            entropy_server.output(
                _("log is not available"),
                importance=1, level="error")
            return 1

        proc = subprocess.Popen(
            "/bin/bzcat \"%s\" | ${PAGER:-/usr/bin/less}" % (
                changelog_path,), shell = True)
        return proc.wait()


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitLog,
        EitLog.NAME,
        _('show log for repository'))
    )
