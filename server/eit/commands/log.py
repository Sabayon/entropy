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

from entropy.const import const_file_readable
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

    INTRODUCTION = """\
Show log for given repository (if any, otherwise the current working one).
This commands opens repository ChangeLog.bz2 using *bzless*.
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

        return self._call_exclusive, [self._log, nsargs.repo]

    def _log(self, entropy_server):
        changelog_path = \
            entropy_server._get_local_repository_compressed_changelog_file(
                entropy_server.repository())

        if not const_file_readable(changelog_path):
            entropy_server.output(
                _("log is not available"),
                importance=1, level="error")
            return 1

        proc = subprocess.Popen(["bzless", changelog_path])
        return proc.wait()


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitLog,
        EitLog.NAME,
        _('show log for repository'))
    )
