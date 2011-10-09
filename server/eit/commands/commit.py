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

from entropy.const import etpConst
from entropy.i18n import _
from entropy.exceptions import PermissionDenied
from entropy.output import print_info, print_warning, print_error, \
    darkgreen, teal, brown, darkred, bold, purple, blue, red, green

from text_tools import print_table

import entropy.tools

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitCommit(EitCommand):
    """
    Main Eit commit command.
    """

    NAME = "commit"

    def __init__(self, args):
        EitCommand.__init__(self, args)
        # ask user before any critical operation
        self._ask = True
        # interactively ask for packages to be staged, etc
        self._interactive = False
        # list of package dependencies to re-package, if any
        self._repackage = []
        # execute actions only for given atoms, if any
        self._atoms = []

    def parse(self):
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitCommit.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitCommit.NAME))

        parser.add_argument("repo", nargs='?', default=None,
                            metavar="<repo>", help="repository id")
        parser.add_argument("--interactive", action="store_true",
                            default=False,
                            help=_("selectively pick changes"))
        parser.add_argument("--quick", action="store_true",
                            default=False,
                            help=_("no stupid questions"))

        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            print_error("error: %s" % (err.strerror,))
            return parser.print_help, []

        self._interactive = nsargs.interactive
        if not self._interactive:
            self._ask = not nsargs.quick

        return self._commit, [nsargs.repo]

    def _commit(self, repo):
        """
        Commit command body.
        """
        server = None
        acquired = False
        try:
            try:
                server = self._entropy(default_repository=repo)
            except PermissionDenied as err:
                print_error(err.value)
                return 1
            acquired = entropy.tools.acquire_entropy_locks(server)
            if not acquired:
                print_error(
                    darkgreen(_("Another Entropy is currently running."))
                )
                return 1
            return self.__commit(server)
        finally:
            if server is not None:
                if acquired:
                    entropy.tools.release_entropy_locks(server)
                server.shutdown()

    def __commit(self, entropy_server):
        to_be_added = set()
        to_be_removed = set()
        to_be_injected = set()

        key_sorter = lambda x: \
            entropy_server.open_repository(x[1]).retrieveAtom(x[0])
        repository_id = entropy_server.repository()
        generated_packages = []

        if self._repackage:

            packages = []
            dbconn = entropy_server.open_server_repository(
                repository_id, read_only = True,
                no_upload = True)

            spm = entropy_server.Spm()
            for item in self._repackage:
                match = dbconn.atomMatch(item)
                if match[0] == -1:
                    print_warning(darkred("  !!! ") + \
                        red(_("Cannot match"))+" "+bold(item))
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
                print_info(brown(" * ") + \
                    red(_("No valid packages to repackage.")))

        # normal scanning
        print_info(brown(" * ") + \
            red("%s..." % (_("Scanning database for differences"),) ))
        try:
            myadded, to_be_removed, to_be_injected = \
                entropy_server.scan_package_changes()
        except KeyboardInterrupt:
            return 1
        to_be_added |= myadded

        if self._atoms:
            to_be_removed.clear()
            to_be_injected.clear()
            tba = dict(((x[0], x,) for x in to_be_added))
            tb_added_new = set()
            for myatom in self._atoms:
                if myatom in tba:
                    tb_added_new.add(tba.get(myatom))
                    continue
                try:
                    inst_myatom = entropy_server.Spm(
                        ).match_installed_package(myatom)
                except KeyError:
                    print_warning(darkred("  !!! ") + \
                        red(_("Invalid package")) + " " + bold(myatom))
                    continue
                if inst_myatom in tba:
                    tb_added_new.add(tba.get(inst_myatom))
            to_be_added = tb_added_new

        if not (len(to_be_removed)+len(to_be_added)+len(to_be_injected)):
            print_info(brown(" * ") + \
                red("%s." % (_("Zarro thinggz totoo"),)))
            return 0

        if to_be_injected:
            print_info(brown(" @@ ") + \
                blue("%s:" % (
                    _("These would be marked as injected"),) ))
            for idpackage, repoid in sorted(to_be_injected,
                                            key = key_sorter):
                dbconn = entropy_server.open_server_repository(repoid,
                    read_only = True, no_upload = True)
                atom = dbconn.retrieveAtom(idpackage)
                print_info(brown("    # ") + "["+blue(repoid) + "] " + \
                               red(atom))
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
                    print_info(brown("   <> ") + \
                        blue("%s: " % (_("Transforming"),) )+red(atom))
                    entropy_server._transform_package_into_injected(
                        idpackage, repoid)
                print_info(brown(" @@ ") + \
                    blue("%s." % (_("Transform complete"),) ))

        def show_rm(idpackage, repoid):
            dbconn = entropy_server.open_server_repository(repoid,
                read_only = True, no_upload = True)
            atom = dbconn.retrieveAtom(idpackage)
            exp_string = ''
            pkg_expired = entropy_server._is_match_expired(
                (idpackage, repoid,))
            if pkg_expired:
                exp_string = "|%s" % (purple(_("expired")),)
            print_info(brown("    # ") + "["+blue(repoid) + \
                           exp_string + "] " + red(atom))

        if self._interactive and to_be_removed:
            print_info(brown(" @@ ") + \
                blue(_("What packages do you want to remove ?")))
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

            print_info(brown(" @@ ") + blue("%s:" % (
                _("These would be removed from repository"),) ))
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
            print_info(brown(" @@ ") + \
                           blue(_("What packages do you want to add ?")))
            new_to_be_added = set()
            for tb_atom, tb_counter in sorted(to_be_added,
                                              key = lambda x: x[0]):
                print_info(brown("    # ") + red(tb_atom))
                rc = entropy_server.ask_question(
                    ">>   %s" % (_("Add this package?"),))
                if rc == _("Yes"):
                    new_to_be_added.add((tb_atom, tb_counter,))
            to_be_added = new_to_be_added

        if to_be_added:

            print_info(brown(" @@ ") + \
                blue("%s:" % (
                    _("These would be added or updated"),) ))
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

                print_info(brown("  # ") + item_txt)

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
        print_info(brown(" @@ ") + \
                       blue("%s..." % (_("Compressing packages"),) ))
        store_dir = entropy_server._get_local_store_directory(
            repository_id)
        for x in sorted(to_be_added):
            print_info(brown("    # ") + teal(x[0]))
            try:
                pkg_list = entropy_server.Spm().generate_package(x[0],
                    store_dir)
                generated_packages.append(pkg_list)
            except OSError:
                entropy.tools.print_traceback()
                print_info(brown("    !!! ")+bold("%s..." % (
                    _("Ignoring broken Spm entry, please recompile it"),) )
                )

        if not generated_packages:
            print_info(brown(" * ")+red(_("Nothing to do, check later.")))
            # then exit gracefully
            return 0

        etp_pkg_files = [(pkg_list, False) for pkg_list in \
                             generated_packages]
        idpackages = entropy_server.add_packages_to_repository(
            repository_id, etp_pkg_files)

        if idpackages:
            # checking dependencies and print issues
            entropy_server.extended_dependencies_test([repository_id])
        entropy_server.close_repositories()
        print_info(green(" * ") + red("%s: " % (_("Statistics"),) ) + \
            blue("%s: " % (_("Entries handled"),) ) + \
                       bold(str(len(idpackages))))
        return 0


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitCommit,
        EitCommit.NAME,
        _("commit changes to repository"))
    )
