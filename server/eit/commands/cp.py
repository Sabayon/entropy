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

from entropy.output import darkgreen, blue, brown, bold, red, purple, teal
from entropy.i18n import _

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitCp(EitCommand):
    """
    Main Eit cp command.
    """

    NAME = "cp"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._source = None
        self._dest = None
        self._deps = False
        self._packages = []
        self._copy = True

    def parse(self):
        """ Overridden from EitCp """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitCp.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitCp.NAME))

        parser.add_argument("source", nargs=1,
                            metavar="<source>",
                            help=_("source repository"))
        parser.add_argument("dest", nargs=1,
                            metavar="<dest>",
                            help=_("destination repository"))
        parser.add_argument("--deps", action="store_true",
                            default=False,
                            help=_("include dependencies"))
        parser.add_argument("package", nargs='+', metavar="<package>",
                            help=_("package dependency"))

        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        self._source = nsargs.source[0]
        self._dest = nsargs.dest[0]
        self._deps = nsargs.deps
        self._packages += nsargs.package
        return self._call_locked, [self._move_copy, self._source]

    def _move_copy(self, entropy_server):
        """
        Execute package move or copy (depending on self._copy) from
        source repository and destination repository. If deps is true,
        also dependencies are pulled in.
        """
        package_ids = []

        if self._source == self._dest:
            entropy_server.output(
                "%s: %s" % (purple(_("source equals destination")),
                            teal(self._dest)),
                importance=1,
                level="error")
            return 1
        if self._dest not in entropy_server.repositories():
            # destination repository not available
            entropy_server.output(
                "%s: %s" % (purple(_("repository not available")),
                            teal(self._dest)),
                importance=1,
                level="error")
            return 1

        # match
        for package in self._packages:
            p_matches, p_rc = entropy_server.atom_match(package,
                match_repo = [self._source], multi_match = True)
            if not p_matches:
                entropy_server.output(
                    red("%s: " % (_("Cannot match"),) ) + bold(package) + \
                    red(" %s " % (_("in"),) ) + bold(self._source) + \
                        red(" %s" % (_("repository"),)),
                    header=brown(" * "),
                    level="warning",
                    importance=1)
            else:
                package_ids += [pkg_id for pkg_id, r_id in p_matches if \
                    (pkg_id not in package_ids)]

        if not package_ids:
            return 1

        rc = False
        if self._copy:
            rc = entropy_server.copy_packages(package_ids, self._source,
                self._dest, pull_dependencies = self._deps)
        else:
            rc = entropy_server.move_packages(package_ids, self._source,
                self._dest, pull_dependencies = self._deps)
        if rc:
            return 0
        return 1


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitCp,
        EitCp.NAME,
        _('copy packages from a repository to another'))
    )
