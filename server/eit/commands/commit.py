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
import collections

from entropy.i18n import _
from entropy.output import darkgreen, teal, brown, \
    darkred, bold, purple, blue, red

import entropy.tools

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitCommit(EitCommand):
    """
    Main Eit commit command.
    """

    NAME = "commit"
    ALIASES = ["ci"]

    def __init__(self, args):
        EitCommand.__init__(self, args)
        # ask user before any critical operation
        self._ask = True
        # interactively ask for packages to be staged, etc
        self._interactive = False
        # execute package name and slot updates
        self._conservative = False
        # list of package dependencies to re-package, if any
        self._repackage = []
        # execute actions only for given atoms, if any
        self._packages = []

    def _get_parser(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitCommit.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitCommit.NAME))

        parser.add_argument("repo", nargs='?', default=None,
                            metavar="<repo>", help=_("repository"))
        parser.add_argument("--conservative", action="store_true",
                            help=_("do not execute implicit package name "
                                   "and slot updates"),
                            default=self._conservative)
        parser.add_argument("--interactive", action="store_true",
                            default=False,
                            help=_("selectively pick changes"))
        parser.add_argument("--quick", action="store_true",
                            default=not self._ask,
                            help=_("no stupid questions"))

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
                outcome = []
                break
        outcome += ["--conservative", "--interactive", "--quick"]

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
Committing to a repository means adding all the unstaged packages
to the same. Unstaged packages are those packages that have just
been compiled but not yet added to any repository.
If you are familiar with git, this maps to *git commit -a*.
If you would like to selectively add certain packages, please see
*eit-add*(1).
"""
    SEE_ALSO = "eit-add(1), eit-repack(1)"

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
            return parser.print_help, []

        self._interactive = nsargs.interactive
        if not self._interactive:
            self._ask = not nsargs.quick
        self._entropy_class()._inhibit_treeupdates = nsargs.conservative

        return self._call_exclusive, [self._commit, nsargs.repo]

    def _repackage_scan(self, entropy_server):
        """
        If in repackage mode (self._repackage not empty), scan for packages
        to re-package and return them.
        """
        packages = set()
        spm = entropy_server.Spm()

        for dep in self._repackage:
            package_id, repository_id = entropy_server.atom_match(dep)

            if package_id == -1:
                entropy_server.output(
                    "%s: %s" % (
                        darkred(_("Cannot find package")),
                        bold(dep),
                        ),
                    header=darkred(" !!! "),
                    importance=1,
                    level="warning")
                continue

            repo = entropy_server.open_repository(repository_id)
            try:
                spm_uid = spm.resolve_package_uid(repo, package_id)
            except spm.Error as err:
                entropy_server.output(
                    "%s: %s, %s" % (
                        darkred(_("Cannot find package")),
                        bold(dep),
                        err,
                        ),
                    header=darkred(" !!! "),
                    importance=1,
                    level="warning")
                continue

            spm_name = spm.convert_from_entropy_package_name(
                repo.retrieveAtom(package_id))
            packages.add(spm_name)

        return packages

    def _compress_packages(self, entropy_server, repository_id, packages):
        """
        Compress (and generate package tarball) the list of given
        spm package names inside the given Entropy repository.
        """
        entropy_server.output(
            blue(_("Compressing packages")),
            header=brown(" @@ "))

        generated_packages = collections.deque()
        store_dir = entropy_server._get_local_store_directory(repository_id)

        if not os.path.isdir(store_dir):
            try:
                os.makedirs(store_dir)
            except (IOError, OSError) as err:
                entropy_server.output(
                    "%s: %s" % (_("Cannot create store directory"), err),
                    header=brown(" !!! "),
                    importance=1,
                    level="error")
                return generated_packages, 1

        for count, spm_name in enumerate(packages, 1):
            entropy_server.output(
                teal(spm_name),
                header=brown("  # "),
                count=(count, len(packages)))

            try:
                pkg_list = entropy_server.Spm().generate_package(spm_name,
                    store_dir)
                generated_packages.append(pkg_list)
            except OSError:
                entropy.tools.print_traceback()
                entropy_server.output(
                    bold(_("Ignoring broken Spm entry, please recompile it")),
                    header=brown("  !!! "),
                    importance=1,
                    level="warning")

        if not generated_packages:
            entropy_server.output(
                red(_("Nothing to do, check later.")),
                header=brown(" * "))
            return generated_packages, 0

        return generated_packages, None

    def _inject_packages(self, entropy_server, package_matches):
        """
        Mark the given Entropy packages as injected in the repository.
        """
        entropy_server.output(
            blue(_("These would be marked as injected")),
            header=brown(" @@ "))

        for package_id, repository_id in package_matches:
            repo = entropy_server.open_repository(repository_id)
            atom = repo.retrieveAtom(package_id)

            entropy_server.output(
                "[%s] %s" % (
                    blue(repository_id),
                    darkred(atom),
                    ),
                header=brown("    # "))

        if self._ask:
            rc = entropy_server.ask_question(
                _("Do it now ?"))
            if rc == _("No"):
                return

        for package_id, repository_id in package_matches:

            repo = entropy_server.open_repository(repository_id)
            atom = repo.retrieveAtom(package_id)
            entropy_server.output(
                "%s: %s" % (
                    blue(_("Transforming")),
                    red(atom)),
                header=brown("   <> "))

            entropy_server._transform_package_into_injected(
                package_id, repository_id)

        entropy_server.commit_repositories()

        entropy_server.output(blue(_("Action completed")),
            header=brown(" @@ "))

    def _add_packages(self, entropy_server, repository_id, packages):
        """
        Add the given Source Package Manager packages to the given
        Entropy repository.
        """
        def asker(spm_name):
            entropy_server.output(
                darkred(spm_name),
                header=brown("    # "))
            rc = entropy_server.ask_question(
                _("Add this package?"))
            return rc == _("Yes")

        if self._interactive:
            entropy_server.output(
                blue(_("Select packages to add")),
                header=brown(" @@ "))
            packages = list(filter(asker, packages))

        if not packages:
            entropy_server.output(
                red(_("Nothing to add")),
                header=brown(" @@ "),
                importance=1)
            return 0

        entropy_server.output(
            blue(_("These would be added or updated")),
            header=brown(" @@ "))

        for spm_name in packages:
            spm_name_txt = purple(spm_name)

            # TODO: this is a SPM package, we should use SPM functions
            spm_key = entropy.dep.dep_getkey(spm_name)
            try:
                spm_slot = entropy_server.Spm(
                    ).get_installed_package_metadata(spm_name, "SLOT")
                spm_repo = entropy_server.Spm(
                    ).get_installed_package_metadata(
                        spm_name, "repository")
            except KeyError:
                spm_slot = None
                spm_repo = None

            # inform user about SPM repository sources moves
            etp_repo = None
            if spm_repo is not None:
                pkg_id, repo_id = entropy_server.atom_match(spm_key,
                    match_slot = spm_slot)

                if pkg_id != -1:
                    repo_db = entropy_server.open_repository(repo_id)
                    etp_repo = repo_db.retrieveSpmRepository(pkg_id)

                    if (etp_repo is not None) and \
                            (etp_repo != spm_repo):
                        spm_name_txt += ' [%s {%s=>%s}]' % (
                            bold(_("warning")),
                            darkgreen(etp_repo), blue(spm_repo),)

            entropy_server.output(spm_name_txt, header=brown("  # "))

        if self._ask:
            rc = entropy_server.ask_question("%s (%s %s)" % (
                    _("Would you like to package them now ?"),
                    _("inside"),
                    repository_id,
                )
            )
            if rc == _("No"):
                return 0

        problems = entropy_server._check_config_file_updates()
        if problems:
            return 1

        generated, exit_st = self._compress_packages(
            entropy_server, repository_id, packages)
        if exit_st is not None:
            return exit_st

        etp_pkg_files = [(pkg_list, False) for pkg_list in generated]
        package_ids = entropy_server.add_packages_to_repository(
            repository_id, etp_pkg_files)

        entropy_server.commit_repositories()

        if package_ids:
            entropy_server.extended_dependencies_test([repository_id])

        entropy_server.output(
            "%s: %d" % (
                blue(_("Packages handled")),
                len(package_ids),),
            header=darkgreen(" * "))
        return 0

    def _remove_packages(self, entropy_server, package_matches):
        """
        Remove the given Entropy packages from their repositories.
        """

        def show_rm(pkg_id, pkg_repo):
            repo = entropy_server.open_repository(pkg_repo)
            atom = repo.retrieveAtom(pkg_id)
            exp_string = ''
            pkg_expired = entropy_server._is_match_expired(
                (pkg_id, pkg_repo,))
            if pkg_expired:
                exp_string = "|%s" % (purple(_("expired")),)

            entropy_server.output(
                "[%s%s] %s" % (
                    blue(pkg_repo),
                    exp_string,
                    darkred(atom),),
                header=brown("    # "))

        def asker(package_match):
            pkg_id, pkg_repo = package_match
            show_rm(pkg_id, pkg_repo)
            rc = entropy_server.ask_question(
                _("Remove this package?"))
            return rc == _("Yes")

        if self._interactive:
            entropy_server.output(
                blue(_("Select packages for removal")),
                header=brown(" @@ "))
            package_matches = list(filter(asker, package_matches))

        if not package_matches:
            return

        entropy_server.output(
            blue(_("These would be removed from repository")),
            header=brown(" @@ "))
        for package_id, repository_id in package_matches:
            show_rm(package_id, repository_id)

        if self._ask:
            rc = entropy_server.ask_question(
                _("Would you like to remove them now ?")
            )
            if rc == _("No"):
                return

        remdata = {}
        for package_id, repository_id in package_matches:
            obj = remdata.setdefault(repository_id, set())
            obj.add(package_id)

        for repository_id, packages in remdata.items():
            entropy_server.remove_packages(repository_id, packages)

        entropy_server.commit_repositories()

    def _commit(self, entropy_server):

        key_sorter = lambda x: entropy_server.open_repository(
            x[1]).retrieveAtom(x[0])

        repository_id = entropy_server.repository()
        # First of all, open the repository in write mode
        # in order to trigger package name updates on SPM.
        # Failing to do so would cause false positives on the
        # removal list.
        entropy_server.open_server_repository(
            repository_id, read_only=False,
            no_upload=True)

        to_be_added = set()
        to_be_removed = set()
        to_be_injected = set()

        entropy_server.output(
            brown(_("Scanning...")),
            importance=1)

        if self._repackage:
            repack_added = self._repackage_scan(entropy_server)
            if not repack_added:
                entropy_server.output(
                    red(_("No valid packages to repackage.")),
                    header=brown(" * "),
                    importance=1,
                    level="error")
                return 1
            to_be_added |= repack_added
        else:
            (scan_added,
             scan_removed,
             scan_injected) = entropy_server.scan_package_changes()

            to_be_added |= set((x[0] for x in scan_added))
            to_be_removed |= scan_removed
            to_be_injected |= scan_injected

        if self._packages:
            to_be_removed.clear()
            to_be_injected.clear()

            def pkg_filter(spm_name):
                if spm_name in to_be_added:
                    return spm_name

                try:
                    inst_spm_name = entropy_server.Spm(
                        ).match_installed_package(spm_name)
                except KeyError:
                    entropy_server.output(
                        "%s: %s" % (
                            darkred(_("Invalid package")),
                            bold(spm_name)),
                        header=darkred(" !!! "),
                        importance=1,
                        level="warning")
                    return None

                if inst_spm_name in to_be_added:
                    return inst_spm_name
                return None

            to_be_added = set(map(pkg_filter, self._packages))
            to_be_added.discard(None)

        if not (to_be_removed or to_be_added or to_be_injected):
            entropy_server.output(
                red(_("Zarro thinggz to do")),
                header=brown(" * "),
                importance=1)
            return 0

        exit_st = 0
        if to_be_injected:
            injected_s = sorted(to_be_injected, key=key_sorter)
            self._inject_packages(entropy_server, injected_s)

        if to_be_removed:
            removed_s = sorted(to_be_removed, key=key_sorter)
            self._remove_packages(entropy_server, removed_s)

        if to_be_added:
            # drop spm_uid, no longer needed
            added_s = sorted(to_be_added)
            exit_st = self._add_packages(entropy_server, repository_id, added_s)

        return exit_st


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitCommit,
        EitCommit.NAME,
        _("commit changes to repository"))
    )
