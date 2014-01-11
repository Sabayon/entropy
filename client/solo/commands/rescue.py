# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import os
import errno
import sys
import argparse

from entropy.i18n import _
from entropy.output import red, bold, brown, blue, darkred, darkgreen, \
    purple, teal
from entropy.const import etpConst, const_mkstemp
from entropy.exceptions import SystemDatabaseError
from entropy.db.exceptions import OperationalError, DatabaseError
from entropy.client.interfaces.db import InstalledPackagesRepository

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand, sharedlock, exclusivelock

import entropy.tools


class SoloRescue(SoloCommand):
    """
    Main Solo Rescue command.
    """

    NAME = "rescue"
    ALIASES = []
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Tools to rescue the running system.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._nsargs = None
        self._commands = {}

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = {}

        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloRescue.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloRescue.NAME))

        subparsers = parser.add_subparsers(
            title="action",
            description=_("execute advanced tasks on packages"),
            help=_("available commands"))

        def _add_ask_to_parser(p, _cmd_dict):
            p.add_argument(
                "--ask", "-a", action="store_true",
                default=False,
                help=_("ask before making any changes"))
            _cmd_dict["--ask"] = {}
            _cmd_dict["-a"] = {}

        def _add_pretend_to_parser(p, _cmd_dict):
            p.add_argument(
                "--pretend", "-p", action="store_true",
                default=False,
                help=_("show what would be done"))
            _cmd_dict["--pretend"] = {}
            _cmd_dict["-p"] = {}

        check_parser = subparsers.add_parser(
            "check", help=_("check installed packages "
                            "repository for errors"))
        check_parser.set_defaults(func=self._check)
        _commands["check"] = {}

        vacuum_parser = subparsers.add_parser(
            "vacuum",
            help=_("compact the installed packages repository"))
        vacuum_parser.set_defaults(func=self._vacuum)
        _commands["vacuum"] = {}

        generate_parser = subparsers.add_parser(
            "generate",
            help=_("re-generate the installed packages repository"
                   " using the Source Package Manager"))
        generate_parser.set_defaults(func=self._generate)
        _commands["generate"] = {}

        spmuids_parser = subparsers.add_parser(
            "spmuids",
            help=_("re-generate SPM<->Entropy package UIDs mapping"))
        spmuids_parser.set_defaults(func=self._spmuids)
        _commands["spmuids"] = {}

        spmsync_parser = subparsers.add_parser(
            "spmsync",
            help=_("update Entropy installed packages repository "
                   "merging Source Package Manager changes"))
        _cmd_dict = {}
        _commands["spmsync"] = _cmd_dict
        mg_group = spmsync_parser.add_mutually_exclusive_group()
        _add_ask_to_parser(mg_group, _cmd_dict)
        _add_pretend_to_parser(mg_group, _cmd_dict)
        spmsync_parser.set_defaults(func=self._spmsync)

        backup_parser = subparsers.add_parser(
            "backup",
            help=_("create a backup of the installed packages repository"))
        backup_parser.set_defaults(func=self._backup)
        _commands["backup"] = {}

        restore_parser = subparsers.add_parser(
            "restore",
            help=_("restore a backup of the installed "
                   "packages repository"))
        restore_parser.set_defaults(func=self._restore)
        _commands["restore"] = {}

        self._commands = _commands
        return parser

    def parse(self):
        """
        Parse command
        """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        # Python 3.3 bug #16308
        if not hasattr(nsargs, "func"):
            return parser.print_help, []

        self._nsargs = nsargs
        return self._call_exclusive, [nsargs.func]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        self._get_parser() # this will generate self._commands
        return self._hierarchical_bashcomp(last_arg, [], self._commands)

    def _check_repository(self, entropy_client, repo):
        """
        Sanity check the Installed Packages repository.
        """
        try:
            repo.validate()
            repo.integrity_check()
        except SystemDatabaseError as err:
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("Repository error")),
                    err,),
                level="warning"
                )
            return 1

        entropy_client.output(
            "%s: %s" % (
                brown(_("Sanity Check")),
                darkgreen(_("installed packages repository")),
            ),
            importance=1,
            level="info"
        )

        scanning_txt = _("Scanning...")
        count = 0
        length = 0
        package_ids = None

        try:
            package_ids = repo.listAllPackageIds()
            length = len(package_ids)
        except DatabaseError as err:
            entropy.tools.print_traceback()
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("Error")),
                    err,
                    ),
                importance=1,
                level="warning"
                )
            return 1

        _errors = False
        for package_id in package_ids:
            count += 1
            entropy_client.output(
                darkgreen(scanning_txt),
                level="info",
                back=True,
                count=(count, length),
                percent=True
            )
            try:
                repo.getPackageData(package_id)
            except Exception as err:
                entropy.tools.print_traceback()
                entropy_client.output(
                    "%s: %s" % (
                        darkred(_("Error checking package")),
                        err,
                    ),
                    level="warning"
                )
                _errors = True

        if _errors:
            entropy_client.output(
                "%s: %s" % (
                    brown(_("Sanity Check")),
                    bold(_("corrupted"))),
                importance=1,
                level="warning"
            )
            return 1

        entropy_client.output(
            "%s: %s" % (
                brown(_("Sanity Check")),
                bold(_("passed"))),
            importance=1,
            level="info"
            )
        return 0

    @sharedlock
    def _check(self, entropy_client, inst_repo):
        """
        Solo Smart Check command.
        """
        return self._check_repository(
            entropy_client,
            inst_repo)

    @sharedlock
    def _vacuum(self, entropy_client, inst_repo):
        """
        Solo Smart Vacuum command.
        """
        entropy_client.output(
            "%s..." % (
                brown(_("Compacting the Installed Packages repository")),
            ),
            importance=1,
            level="info",
            header=darkgreen(" @@ "),
            back=True
            )
        inst_repo.dropAllIndexes()
        inst_repo.vacuum()
        inst_repo.commit()

        entropy_client.output(
            "%s." % (
                brown(_("Compaction complete")),
            ),
            importance=1,
            level="info",
            header=darkgreen(" @@ ")
            )
        return 0

    def _backup_repository(self, entropy_client, repo, path):
        """
        Create a backup of the given Repository.
        """
        if not os.path.isfile(path):
            # return True if the repository is not available
            return True, None
        repo_dir = os.path.dirname(path)

        backed_up, msg = entropy_client.backup_repository(
            repo.repository_id(), repo_dir)
        return backed_up, msg

    @exclusivelock
    def _generate(self, entropy_client, inst_repo):
        """
        Solo Smart Generate command.
        """
        mytxt = "%s: %s"  % (
            brown(_("Attention")),
            darkred(_("the Installed Packages repository "
                      "will be re-generated using the "
                      "Source Package Manager")),
            )
        entropy_client.output(
            mytxt,
            level="warning",
            importance=1)

        mytxt = "%s: %s"  % (
            brown(_("Attention")),
            darkred(_("I am not joking, this is quite disruptive")),
            )
        entropy_client.output(
            mytxt,
            level="warning",
            importance=1)

        rc = entropy_client.ask_question(
            "  %s" % (_("Understood ?"),))
        if rc == _("No"):
            return 1
        rc = entropy_client.ask_question(
            "  %s" % (_("Really ?"),) )
        if rc == _("No"):
            return 1
        rc = entropy_client.ask_question(
            "  %s. %s" % (
                _("This is your last chance"),
                _("Ok?"),)
            )
        if rc == _("No"):
            return 1

        # clean caches
        spm = entropy_client.Spm()
        entropy_client.clear_cache()

        # try to get a list of current package ids, if possible
        try:
            package_ids = inst_repo.listAllPackageIds()
        except Exception as err:
            entropy.tools.print_traceback()
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("Cannot read metadata")),
                    err,
                    ),
                level="warning"
            )
            package_ids = []

        # try to collect current installed revisions if possible
        # and do the same for digest
        revisions_match = {}
        digest_match = {}
        for package_id in package_ids:
            try:
                atom = inst_repo.retrieveAtom(
                    package_id)
                revisions_match[atom] = inst_repo.retrieveRevision(
                    package_id)
                digest_match[atom] = inst_repo.retrieveDigest(
                    package_id)
            except Exception as err:
                entropy.tools.print_traceback()
                entropy_client.output(
                    "%s: %s" % (
                        darkred(_("Cannot read metadata")),
                        err,
                        ),
                    level="warning"
                )

        repo_path = entropy_client.installed_repository_path()
        entropy_client.output(
            darkgreen(_("Creating a backup of the current repository")),
            level="info",
            importance=1,
            header=darkred(" @@ "))
        entropy_client.output(
            repo_path,
            header="  ")

        inst_repo.commit()
        backed_up, msg = self._backup_repository(
            entropy_client, inst_repo, repo_path)
        if not backed_up:
            mytxt = "%s: %s" % (
                darkred(_("Cannot backup the repository")),
                brown("%s" % msg),)
            entropy_client.output(
                mytxt,
                level="error",
                importance=1,
                header=darkred(" @@ "))
            return 1

        entropy_client.close_installed_repository()
        # repository will be re-opened automagically
        # at the next access.
        try:
            os.remove(repo_path)
        except OSError as err:
            if err.errno != errno.ENOENT:
                mytxt = "%s: %s" % (
                    purple(_("Cannot delete old repository")),
                    brown("%s" % err),)
                entropy_client.output(
                    mytxt,
                    level="warning",
                    importance=1,
                    header=darkred(" @@ "))
                return 1

        entropy_client.output(
            purple(_("Initializing a new repository")),
            importance=1,
            header=darkred(" @@ "))
        entropy_client.output(
            brown(repo_path),
            header="  ")

        # open a repository at the old path, if repo_path is
        # not in place, Entropy will forward us to the in-RAM
        # database (for sqlite), which is not what we want.
        inst_repo.initializeRepository()
        inst_repo.commit()

        entropy_client.output(
            purple(_("Repository initialized, generating metadata")),
            importance=1,
            header=darkred(" @@ "))

        spm_packages = spm.get_installed_packages()
        total = len(spm_packages)
        count = 0
        # perf: reuse temp file
        tmp_fd, tmp_path = const_mkstemp(
            prefix="equo.rescue.generate")
        os.close(tmp_fd)

        for spm_package in spm_packages:
            count += 1

            # make sure the file is empty
            with open(tmp_path, "w") as tmp_f:
                tmp_f.flush()

            entropy_client.output(
                teal(spm_package),
                count=(count, total),
                back=True,
                header=brown(" @@ "))

            appended = spm.append_metadata_to_package(
                spm_package, tmp_path)
            if not appended:
                entropy_client.output(
                    "%s: %s" % (
                        purple(_("Invalid package")),
                        teal(spm_package),),
                    importance=1,
                    header=darkred(" @@ "))
                continue

            try:
                data = spm.extract_package_metadata(tmp_path)
            except Exception as err:
                entropy.tools.print_traceback()
                entropy_client.output(
                    "%s, %s: %s" % (
                        teal(spm_package),
                        purple(_("Metadata generation error")),
                        err,
                        ),
                    level="warning",
                    importance=1,
                    header=darkred(" @@ ")
                    )
                continue

            # Try to see if it's possible to use
            # the revision of a possible old db
            data['revision'] = etpConst['spmetprev']
            # create atom string
            atom = entropy.dep.create_package_atom_string(
                data['category'],
                data['name'],
                data['version'],
                data['versiontag'])

            # now see if a revision is available
            saved_rev = revisions_match.get(atom)
            if saved_rev is not None:
                saved_rev = saved_rev
                data['revision'] = saved_rev

            # set digest to "0" to disable entropy dependencies
            # calculation check that forces the pkg to
            # be pulled in if digest differs from the one on the repo
            saved_digest = digest_match.get(atom, "0")
            data['digest'] = saved_digest

            package_id = inst_repo.addPackage(data,
                revision = data['revision'])
            inst_repo.storeInstalledPackage(package_id,
                etpConst['spmdbid'])

        try:
            os.remove(tmp_path)
        except OSError:
            pass

        entropy_client.output(
            purple(_("Indexing metadata, please wait...")),
            header=darkgreen(" @@ "), back=True
            )
        inst_repo.createAllIndexes()
        inst_repo.commit()
        entropy_client.output(
            purple(_("Repository metadata generation complete")),
            header=darkgreen(" @@ ")
            )
        return 0

    @exclusivelock
    def _spmsync(self, entropy_client, inst_repo):
        """
        Solo Smart Spmsync command.
        """
        ask = self._nsargs.ask
        pretend = self._nsargs.pretend
        spm = entropy_client.Spm()

        entropy_client.output(
            "%s..." % (
                teal(_("Scanning Source Package Manager repository")),),
            header=brown(" @@ "),
            back=True)

        spm_packages = spm.get_installed_packages()
        installed_packages = []
        for spm_package in spm_packages:

            try:
                spm_package_id = spm.resolve_spm_package_uid(
                    spm_package)
            except KeyError as err:
                entropy_client.output(
                    "%s: %s, %s" % (
                        darkred(_("Cannot find package")),
                        purple(spm_package),
                        err,),
                    level="warning",
                    importance=1)
                continue

            installed_packages.append(
                (spm_package, spm_package_id,))

        entropy_client.output(
            "%s..." % (
                teal(_("Scanning Entropy repository")),),
            header=brown(" @@ "),
            back=True)

        installed_spm_uids = set()
        to_be_added = set()
        to_be_removed = set()

        # collect new packages
        for spm_package, spm_package_id in installed_packages:
            installed_spm_uids.add(spm_package_id)
            if not inst_repo.isSpmUidAvailable(spm_package_id):
                to_be_added.add((spm_package, spm_package_id))

        # do some memoization to speed up the scanning
        _spm_key_slot_map = {}
        for _spm_pkg, _spm_pkg_id in to_be_added:
            key = entropy.dep.dep_getkey(_spm_pkg)
            obj = _spm_key_slot_map.setdefault(key, set())

            try:
                slot = spm.get_installed_package_metadata(
                    _spm_pkg, "SLOT")
                # workaround for ebuilds without SLOT
                if slot is None:
                    slot = '0'
                obj.add(slot)
            except KeyError:
                continue

        # packages to be removed from the database
        repo_spm_uids = inst_repo.listAllSpmUids()
        for spm_package_id, package_id in repo_spm_uids:
            # skip packages without valid counter
            if spm_package_id < 0:
                continue

            if spm_package_id in installed_spm_uids:
                # legit, package is still there, skipskipskip
                continue

            if not to_be_added:
                # there is nothing to check in to_be_added
                to_be_removed.add(package_id)
                continue

            atom = inst_repo.retrieveAtom(package_id)
            add = True
            if atom:
                atomkey = entropy.dep.dep_getkey(atom)
                atomslot = inst_repo.retrieveSlot(package_id)

                spm_slots = _spm_key_slot_map.get(atomkey)
                if spm_slots is not None:
                    if atomslot in spm_slots:
                        # do not add to to_be_removed
                        add = False

            if add:
                to_be_removed.add(package_id)

        if not to_be_removed and not to_be_added:
            entropy_client.output(
                darkgreen(_("Nothing to do")),
                importance=1)
            return 0

        if to_be_removed:
            entropy_client.output(
                "%s:" % (
                    purple(_("These packages were removed")),
                ),
                importance=1,
                header=brown(" @@ "))

        broken = set()
        for package_id in to_be_removed:
            atom = inst_repo.retrieveAtom(package_id)
            if not atom:
                broken.add(package_id)
                continue

            entropy_client.output(
                darkred(atom),
                header=brown("    # "))
        to_be_removed -= broken

        if to_be_removed and not pretend:
            rc = _("Yes")
            accepted = True
            if ask:
                rc = entropy_client.ask_question(
                    _("Continue ?"))
                if rc != _("Yes"):
                    accepted = False

            if accepted:
                counter = 0
                total = len(to_be_removed)
                for package_id in to_be_removed:
                    counter += 1
                    atom = inst_repo.retrieveAtom(package_id)
                    entropy_client.output(
                        teal(atom),
                        count=(counter, total),
                        header=darkred(" --- "))

                    inst_repo.removePackage(package_id)

                inst_repo.commit()
                entropy_client.output(
                    darkgreen(_("Removal complete")),
                    importance=1,
                    header=brown(" @@ "))

        if to_be_added:
            entropy_client.output(
                "%s:" % (
                    purple(_("These packages were added")),
                ),
                importance=1,
                header=brown(" @@ "))

            for _spm_package, _spm_package_id in to_be_added:
                entropy_client.output(
                    darkgreen(_spm_package),
                    header=brown("    # "))

        if to_be_added and not pretend:

            if ask:
                rc = entropy_client.ask_question(_("Continue ?"))
                if rc != _("Yes"):
                    return 1

            total = len(to_be_added)
            counter = 0
            # perf: only create temp file once
            tmp_fd, tmp_path = const_mkstemp(
                prefix="equo.rescue.spmsync")
            os.close(tmp_fd)

            for _spm_package, _spm_package_id in to_be_added:
                counter += 1
                entropy_client.output(
                    teal(_spm_package),
                    count=(counter, total),
                    header=darkgreen(" +++ "))

                # make sure the file is empty
                with open(tmp_path, "w") as tmp_f:
                    tmp_f.flush()

                appended = spm.append_metadata_to_package(
                    _spm_package, tmp_path)
                if not appended:
                    entropy_client.output(
                        "%s: %s" % (
                            purple(_("Invalid package")),
                            teal(_spm_package),),
                        importance=1,
                        header=darkred(" @@ "))
                    continue

                # now extract info
                try:
                    data = spm.extract_package_metadata(tmp_path)
                except Exception as err:
                    entropy.tools.print_traceback()
                    entropy_client.output(
                        "%s, %s: %s" % (
                            teal(spm_package),
                            purple(_("Metadata generation error")),
                            err,
                            ),
                        level="warning",
                        importance=1,
                        header=darkred(" @@ ")
                        )
                    continue

                # create atom string
                atom = entropy.dep.create_package_atom_string(
                    data['category'],
                    data['name'],
                    data['version'],
                    data['versiontag'])

                # look for atom in client database
                package_ids = inst_repo.getPackageIds(atom)
                old_package_ids = sorted(package_ids)
                try:
                    _package_id = old_package_ids.pop()
                    data['revision'] = inst_repo.retrieveRevision(
                        _package_id)
                except IndexError:
                    data['revision'] = etpConst['spmetprev']

                # cleanup stale info
                if "original_repository" in data:
                    del data['original_repository']

                new_package_id = inst_repo.handlePackage(
                    data, revision = data['revision'])
                inst_repo.storeInstalledPackage(new_package_id,
                    etpConst['spmdbid'])

            inst_repo.commit()
            try:
                os.remove(tmp_path)
            except OSError:
                pass

            entropy_client.output(
                darkgreen(_("Update complete")),
                importance=1,
                header=brown(" @@ "))

        return 0

    @exclusivelock
    def _spmuids(self, entropy_client, inst_repo):
        """
        Solo Smart Spmuids command.
        """
        entropy_client.output(
            "%s..." % (
                purple(_("Re-generating packages mapping")),),
            header=brown(" @@ "),
            back=True)

        inst_repo.regenerateSpmUidMapping()

        entropy_client.output(
            "%s..." % (
                purple(_("Packages mapping re-generated")),),
            header=brown(" @@ "))
        return 0

    @sharedlock
    def _backup(self, entropy_client, inst_repo):
        """
        Solo Smart Backup command.
        """
        path = entropy_client.installed_repository_path()
        dir_path = os.path.dirname(path)

        status, _err_msg = entropy_client.backup_repository(
            inst_repo.repository_id(), dir_path)
        if status:
            return 0
        return 1

    @exclusivelock
    def _restore(self, entropy_client, inst_repo):
        """
        Solo Smart Restore command.
        """
        path = entropy_client.installed_repository_path()

        repo_list = entropy_client.installed_repository_backups()
        if not repo_list:
            entropy_client.output(
                darkred(_("No backups found")),
                header=brown(" @@ "),
                level="warning",
                importance=1)
            return 1

        repo_list_new = []
        repo_data = []
        for repo_path in repo_list:
            try:
                ts = os.path.getmtime(repo_path)
            except OSError as err:
                entropy.tools.print_traceback()
                continue
            h_ts = entropy.tools.convert_unix_time_to_human_time(ts)
            repo_list_new.append("[%s] %s" % (h_ts, repo_path,))
            repo_data.append(repo_path)

        def fake_cb(s):
            return s

        input_params = [
            ('db', ('combo', (_('Select the repository to restore'),
                repo_list_new),), fake_cb, True)
        ]

        while True:
            data = entropy_client.input_box(
                darkred(
                    _("Entropy Installed Packages Repository backups")),
                    input_params, cancel_button = True)
            if data is None:
                return 1

            myid, dbx = data['db']
            try:
                backup_path = repo_data.pop(myid-1)
            except IndexError:
                continue
            if not os.path.isfile(backup_path):
                continue
            break

        inst_repo.commit()
        status, err_msg = entropy_client.restore_repository(
            backup_path, path, inst_repo.repository_id())
        if status:
            return 0
        return 1

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloRescue,
        SoloRescue.NAME,
        _("tools to rescue the running system"))
    )
