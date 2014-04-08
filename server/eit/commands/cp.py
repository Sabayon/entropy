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
        self._ask = True
        self._packages = []
        self._copy = True
        # execute package name and slot updates
        self._conservative = False

    def _get_parser(self):
        """ Overridden from EitCp """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            self.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], self.NAME))

        parser.add_argument("source",
                            metavar="<source>",
                            help=_("source repository"))
        parser.add_argument("dest",
                            metavar="<dest>",
                            help=_("destination repository"))
        parser.add_argument("--conservative", action="store_true",
                            help=_("do not execute implicit package name "
                                   "and slot updates"),
                            default=self._conservative)
        parser.add_argument("--deps", action="store_true",
                            default=False,
                            help=_("include dependencies"))
        parser.add_argument("--quick", action="store_true",
                            default=not self._ask,
                            help=_("no stupid questions"))
        parser.add_argument("packages", nargs='*', metavar="<package>",
                            help=_("package dependency"))
        return parser

    def bashcomp(self, last_arg):
        """
        Overridden from EitCommand
        """
        import sys

        entropy_server = self._entropy(handle_uninitialized=False,
                                       installed_repo=-1)
        outcome = entropy_server.repositories()
        max_repos = 2
        for arg in self._args:
            if arg in outcome:
                max_repos -= 1
                if max_repos == 0:
                    # already given a repo
                    outcome = []
                    break
        outcome += ["--deps", "--conservative", "--quick"]

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
Copy packages from source repository to destination repository.
"""
    SEE_ALSO = "eit-mv(1)"

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        """ Overridden from EitCp """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            return parser.print_help, []

        self._source = nsargs.source
        self._dest = nsargs.dest
        self._deps = nsargs.deps
        self._ask = not nsargs.quick
        self._packages += nsargs.packages
        self._entropy_class()._inhibit_treeupdates = nsargs.conservative

        return self._call_exclusive, [self._move_copy, self._source]

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

        # make sure to open the repository in read/write in
        # order to trigger treeupdates, or the package ids
        # collected below may become stale and make entropy crash.
        entropy_server.open_server_repository(
            self._source, read_only=False)

        packages = entropy_server.packages_expand(self._packages)
        for package in packages:
            p_matches, p_rc = entropy_server.atom_match(package,
                match_repo = [self._source], multi_match = True)
            if not p_matches:
                entropy_server.output(
                    "%s: %s" % (
                        purple(_("Not matched")), teal(package)),
                    level="warning", importance=1)
            else:
                package_ids += [pkg_id for pkg_id, r_id in p_matches if \
                    (pkg_id not in package_ids)]

        if (not packages) and (not package_ids):
            entropy_server.output(
                purple(_("Considering all the packages")),
                importance=1, level="warning")
            repo = entropy_server.open_repository(self._source)
            package_ids = repo.listAllPackageIds()

        if not package_ids:
            return 1

        rc = False
        if self._copy:
            rc = entropy_server.copy_packages(
                package_ids, self._source,
                self._dest, pull_dependencies = self._deps,
                ask = self._ask)
        else:
            rc = entropy_server.move_packages(
                package_ids, self._source,
                self._dest, pull_dependencies = self._deps,
                ask = self._ask)
        if rc:
            return 0
        return 1


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitCp,
        EitCp.NAME,
        _('copy packages from a repository to another'))
    )
