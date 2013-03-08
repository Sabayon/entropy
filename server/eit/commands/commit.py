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
import functools

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
        outcome += ["--interactive", "--quick"]

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
            return functools.partial(self.print_help, parser), []

        self._interactive = nsargs.interactive
        if not self._interactive:
            self._ask = not nsargs.quick

        return self._call_locked, [self._commit, nsargs.repo]

    def _commit(self, entropy_server):

        to_be_added = set()
        to_be_removed = set()
        to_be_injected = set()

        key_sorter = lambda x: \
            entropy_server.open_repository(x[1]).retrieveAtom(x[0])
        repository_id = entropy_server.repository()
        generated_packages = []

        # First of all, open the repository in write mode
        # in order to trigger package name updates on SPM.
        # Failing to do so would cause false positives on the
        # removal list.
        entropy_server.open_server_repository(
            repository_id, read_only=False, no_upload=True)

        if self._repackage:

            packages = []
            dbconn = entropy_server.open_server_repository(
                repository_id, read_only = True,
                no_upload = True)

            spm = entropy_server.Spm()
            for item in self._repackage:
                match = dbconn.atomMatch(item)
                if match[0] == -1:
                    entropy_server.output(
                        red(_("Cannot match"))+" "+bold(item),
                        header=darkred("  !!! "),
                        importance=1,
                        level="warning")
                else:
                    cat = dbconn.retrieveCategory(match[0])
                    name = dbconn.retrieveName(match[0])
                    version = dbconn.retrieveVersion(match[0])
                    spm_pkg = os.path.join(cat, name + "-" + version)
                    spm_build = \
                        spm.get_installed_package_build_script_path(
                            spm_pkg)
                    spm_pkg_dir = os.path.dirname(spm_build)
                    if os.path.isdir(spm_pkg_dir):
                        packages.append((spm_pkg, 0))

            if packages:
                to_be_added |= set(packages)
            else:
                entropy_server.output(
                    red(_("No valid packages to repackage.")),
                    header=brown(" * "),
                    importance=1)

        # normal scanning
        entropy_server.output(
            brown(_("Scanning...")),
            importance=1)
        try:
            myadded, to_be_removed, to_be_injected = \
                entropy_server.scan_package_changes()
        except KeyboardInterrupt:
            return 1
        to_be_added |= myadded

        if self._packages:
            to_be_removed.clear()
            to_be_injected.clear()
            tba = dict(((x[0], x,) for x in to_be_added))
            tb_added_new = set()
            for myatom in self._packages:
                if myatom in tba:
                    tb_added_new.add(tba.get(myatom))
                    continue
                try:
                    inst_myatom = entropy_server.Spm(
                        ).match_installed_package(myatom)
                except KeyError:
                    entropy_server.output(
                        red(_("Invalid package"))+" "+bold(myatom),
                        header=darkred("  !!! "),
                        importance=1,
                        level="warning")
                    continue
                if inst_myatom in tba:
                    tb_added_new.add(tba.get(inst_myatom))
            to_be_added = tb_added_new

        if not (len(to_be_removed)+len(to_be_added)+len(to_be_injected)):
            entropy_server.output(
                red(_("Zarro thinggz to do")),
                header=brown(" * "),
                importance=1)
            return 0

        if to_be_injected:
            entropy_server.output(
                blue(_("These would be marked as injected")),
                header=brown(" @@ "))
            for idpackage, repoid in sorted(to_be_injected,
                                            key = key_sorter):
                dbconn = entropy_server.open_server_repository(repoid,
                    read_only = True, no_upload = True)
                atom = dbconn.retrieveAtom(idpackage)
                entropy_server.output("["+blue(repoid) + "] " + red(atom),
                    header=brown("    # "))

            if self._ask:
                rc = entropy_server.ask_question(
                    ">>   %s" % (_("Do it now ?"),))
            else:
                rc = _("Yes")

            if rc == _("Yes"):
                for idpackage, repoid in sorted(to_be_injected,
                                                key = key_sorter):
                    dbconn = entropy_server.open_server_repository(repoid,
                        read_only = True, no_upload = True)
                    atom = dbconn.retrieveAtom(idpackage)
                    entropy_server.output(
                        "%s: %s" % (blue(_("Transforming")),
                                    red(atom)),
                        header=brown("   <> "))
                    entropy_server._transform_package_into_injected(
                        idpackage, repoid)
                entropy_server.output(blue(_("Action completed")),
                    header=brown(" @@ "))

        def show_rm(idpackage, repoid):
            dbconn = entropy_server.open_server_repository(repoid,
                read_only = True, no_upload = True)
            atom = dbconn.retrieveAtom(idpackage)
            exp_string = ''
            pkg_expired = entropy_server._is_match_expired(
                (idpackage, repoid,))
            if pkg_expired:
                exp_string = "|%s" % (purple(_("expired")),)
            entropy_server.output(
                "["+blue(repoid) + exp_string + "] " + red(atom),
                header=brown("    # "))

        if self._interactive and to_be_removed:
            entropy_server.output(
                blue(_("Select packages for removal")),
                header=brown(" @@ "))
            new_to_be_removed = set()
            for idpackage, repoid in sorted(to_be_removed,
                                            key = key_sorter):
                show_rm(idpackage, repoid)
                rc = entropy_server.ask_question(
                    ">>   %s" % (_("Remove this package?"),))
                if rc == _("Yes"):
                    new_to_be_removed.add((idpackage, repoid,))
            to_be_removed = new_to_be_removed

        if to_be_removed:
            entropy_server.output(
                blue(_("These would be removed from repository")),
                header=brown(" @@ "))
            for idpackage, repoid in sorted(to_be_removed,
                                            key = key_sorter):
                show_rm(idpackage, repoid)

            if self._ask:
                rc = entropy_server.ask_question(
                    ">>   %s" % (
                        _("Would you like to remove them now ?"),) )
            else:
                rc = _("Yes")

            if rc == _("Yes"):
                remdata = {}
                for idpackage, repoid in to_be_removed:
                    if repoid not in remdata:
                        remdata[repoid] = set()
                    remdata[repoid].add(idpackage)
                for repoid in remdata:
                    entropy_server.remove_packages(repoid,
                                                   remdata[repoid])

        if self._interactive and to_be_added:
            entropy_server.output(
                blue(_("Select packages to add")),
                header=brown(" @@ "))
            new_to_be_added = set()
            for tb_atom, tb_counter in sorted(to_be_added,
                                              key = lambda x: x[0]):
                entropy_server.output(red(tb_atom),
                    header=brown("    # "))
                rc = entropy_server.ask_question(
                    ">>   %s" % (_("Add this package?"),))
                if rc == _("Yes"):
                    new_to_be_added.add((tb_atom, tb_counter,))
            to_be_added = new_to_be_added

        if to_be_added:

            entropy_server.output(
                blue(_("These would be added or updated")),
                header=brown(" @@ "))
            items = sorted([x[0] for x in to_be_added])
            for item in items:
                item_txt = purple(item)

                # this is a spm atom
                spm_key = entropy.dep.dep_getkey(item)
                try:
                    spm_slot = entropy_server.Spm(
                        ).get_installed_package_metadata(item, "SLOT")
                    spm_repo = entropy_server.Spm(
                        ).get_installed_package_metadata(
                            item, "repository")
                except KeyError:
                    spm_slot = None
                    spm_repo = None

                #
                # inform user about SPM repository sources moves !!
                #
                etp_repo = None
                if spm_repo is not None:
                    pkg_id, repo_id = entropy_server.atom_match(spm_key,
                        match_slot = spm_slot)
                    if repo_id != 1:
                        repo_db = entropy_server.open_server_repository(
                            repo_id, just_reading = True)
                        etp_repo = repo_db.retrieveSpmRepository(pkg_id)

                        if (etp_repo is not None) and \
                                (etp_repo != spm_repo):
                            item_txt += ' [%s {%s=>%s}]' % (
                                bold(_("warning")),
                                darkgreen(etp_repo), blue(spm_repo),)

                entropy_server.output(item_txt, header=brown("  # "))

            if self._ask:
                rc = entropy_server.ask_question(">>   %s (%s %s)" % (
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

        # package them
        entropy_server.output(
            blue(_("Compressing packages")),
            header=brown(" @@ "))
        store_dir = entropy_server._get_local_store_directory(
            repository_id)
        # user could have removed it. Oh dear lord!
        if not os.path.isdir(store_dir):
            try:
                os.makedirs(store_dir)
            except (IOError, OSError) as err:
                entropy_server.output(
                    "%s: %s" % (_("Cannot create store directory"), err),
                    header=brown(" !!! "),
                    importance=1,
                    level="error")
                return 1
        for x in sorted(to_be_added):
            entropy_server.output(teal(x[0]),
                                  header=brown("    # "))
            try:
                pkg_list = entropy_server.Spm().generate_package(x[0],
                    store_dir)
                generated_packages.append(pkg_list)
            except OSError:
                entropy.tools.print_traceback()
                entropy_server.output(
                    bold(_("Ignoring broken Spm entry, please recompile it")),
                    header=brown("    !!! "),
                    importance=1,
                    level="warning")

        if not generated_packages:
            entropy_server.output(
                red(_("Nothing to do, check later.")),
                header=brown(" * "))
            # then exit gracefully
            return 0

        etp_pkg_files = [(pkg_list, False) for pkg_list in \
                             generated_packages]
        idpackages = entropy_server.add_packages_to_repository(
            repository_id, etp_pkg_files)

        if idpackages:
            # checking dependencies and print issues
            entropy_server.extended_dependencies_test([repository_id])
        entropy_server.commit_repositories()
        entropy_server.output(red("%s: " % (_("Statistics"),) ) + \
            blue("%s: " % (_("Entries handled"),) ) + \
                bold(str(len(idpackages))),
            header=darkgreen(" * "))
        return 0


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitCommit,
        EitCommit.NAME,
        _("commit changes to repository"))
    )
