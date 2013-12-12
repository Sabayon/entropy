# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import os
import sys
import argparse

from entropy.i18n import _, ngettext
from entropy.output import bold, purple, darkgreen, blue, teal

import entropy.tools

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitBranch(EitCommand):
    """
    Main Eit files command.
    """

    NAME = "branch"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._packages = []
        self._from_branch = None
        self._to_branch = None
        self._repository_id = None
        self._ask = True
        self._copy = True

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitBranch.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitBranch.NAME))

        parser.add_argument("--quick", action="store_true",
                            default=not self._ask,
                            help=_("no stupid questions"))
        parser.add_argument("branch", nargs='?',
                            metavar="<branch>",
                            help=_("switch to given branch"))
        parser.add_argument("repo", nargs='?',
                            metavar="<repo>",
                            help=_("repository"))
        parser.add_argument("--from", metavar="<branch>",
                            help=_("from branch"),
                            dest="frombranch", default=None)
        parser.add_argument("--no-copy", action="store_true",
                            default=not self._copy, dest="nocopy",
                            help=_("don't copy packages from branch"))
        return parser

    INTRODUCTION = """\
Switch to given branch. This will cause the creation of a
separate repository database on disk and remotely, taking the
name of the branch argument passed.
Only one branch should be used at the same time, but nothing
will prevent you from interleaving them.
Generally, this feature is used to switch the repository to a
new branch, copying all the packages over (default behaviour).
To just switch to an empty branch without copying the packages
over just use the *--no-copy* switch.
"""
    SEE_ALSO = ""

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
        except IOError:
            return parser.print_help, []

        self._from_branch = nsargs.frombranch
        self._to_branch = nsargs.branch
        self._repository_id = nsargs.repo
        self._ask = not nsargs.quick
        self._copy = not nsargs.nocopy
        return self._call_exclusive, [self._branch, self._repository_id]

    def _branch(self, entropy_server):
        """
        Eit branch code.
        """
        if self._to_branch is None:
            # show status then
            return self._status(entropy_server)

        repository_id = entropy_server.repository()
        from_branch = self._from_branch
        if from_branch is None:
            from_branch = self._settings()['repositories']['branch']
        else:
            if not entropy.tools.validate_branch_name(from_branch):
                entropy_server.output(
                    "%s: %s" % (
                        purple(_("Invalid branch")),
                        from_branch),
                    importance=1, level="error")
                return 1

        # validate to_branch
        if not entropy.tools.validate_branch_name(self._to_branch):
            entropy_server.output(
                "%s: %s" % (
                    purple(_("Invalid branch")),
                    self._to_branch),
                importance=1, level="error")
            return 1

        dbconn_old = entropy_server.open_server_repository(repository_id,
            read_only = True, no_upload = True, use_branch = from_branch,
            do_treeupdates = False)
        pkglist = dbconn_old.listAllPackageIds()

        if not pkglist:
            if self._copy:
                entropy_server.output(
                    purple(_("No packages to copy")),
                    importance=1, level="error")
        else:
            if self._copy:
                entropy_server.output(
                    "%s %s %s: %s" % (
                        len(pkglist),
                        darkgreen(ngettext("package", "packages", len(pkglist))),
                        blue(_("would be copied to branch")),
                        bold(self._to_branch),
                        ),
                    header=darkgreen(" @@ "))

        if self._ask and pkglist and self._copy:
            resp = entropy_server.ask_question(
                _("Would you like to continue ?"))
            if resp == _("No"):
                return 1

        # set branch to new branch first
        entropy_server.set_branch(self._to_branch)
        if (not pkglist) or (not self._copy):
            entropy_server.output(
                "[%s] %s: %s" % (
                    blue(entropy_server.repository()),
                    teal(_("switched to branch")),
                    purple(self._to_branch),
                    ),
                header=darkgreen(" @@ "))
            return 0

        status = None
        try:
            status = entropy_server._switch_packages_branch(
                repository_id, from_branch, self._to_branch)
            if status is None:
                return 1
        finally:
            if status is None:
                entropy_server.set_branch(from_branch)

        switched, already_switched, ignored, \
            not_found, no_checksum = status
        if not_found or no_checksum:
            return 1
        return 0

    def _status(self, entropy_server):
        """
        Show branch information (list of branches, current branch)
        """
        repository_id = entropy_server.repository()
        branch_dir = entropy_server._get_local_repository_dir(
            repository_id, branch="")
        branches = []
        if os.path.isdir(branch_dir):
            branches += [x for x in os.listdir(branch_dir) if \
                os.path.isdir(os.path.join(branch_dir, x))]
        current_branch = self._settings()['repositories']['branch']
        branches.sort()
        for branch in branches:
            cur_txt = ""
            if branch == current_branch:
                cur_txt = purple("*") + " "
            entropy_server.output("%s%s" % (cur_txt, branch))
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitBranch,
        EitBranch.NAME,
        _('manage repository branches'))
    )
