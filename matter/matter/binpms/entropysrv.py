# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Matter TinderBox Toolkit}.

    Entropy Server implementation of a Binary Package Manager interface
    to Matter.

"""
import os
import subprocess
import sys
import threading

from matter.binpms.base import BaseBinaryResourceLock, \
    BaseBinaryPMS
from matter.spec import MatterSpec, MatterSpecParser, GenericSpecFunctions
from matter.output import print_info, print_warning, print_error
from matter.utils import print_traceback


os.environ["ETP_GETTEXT_DOMAIN"] = "entropy-server"
# this application does not like interactivity
os.environ["ETP_NONITERACTIVE"] = "1"

sys.path.insert(0, "/usr/lib/entropy/lib")
sys.path.insert(0, "../../../lib")
sys.path.insert(0, "../lib")

from entropy.exceptions import PermissionDenied, OnlineMirrorError
from entropy.server.interfaces import Server
from entropy.locks import EntropyResourcesLock

import entropy.dep
import entropy.tools

import portage.dep


class EntropyResourceLock(BaseBinaryResourceLock):
    """
    This class exposes a Lock-like interface for acquiring Entropy Server
    resources.
    """

    class NotAcquired(BaseBinaryResourceLock.NotAcquired):
        """ Raised when Entropy Resource Lock cannot be acquired """

    def __init__(self, blocking):
        """
        EntropyResourceLock constructor.

        @param entropy_server: Entropy Server instance
        @type entropy_server: entropy.server.interfaces.Server
        @param blocking: acquire lock in blocking mode?
        @type blocking: bool
        """
        super(EntropyResourceLock, self).__init__(blocking)
        self.__inside_with_stmt = 0

    def acquire(self):
        """
        Overridden from BaseBinaryResourceLock.
        """
        lock = EntropyResourcesLock(output=Server)
        if self._blocking:
            lock.acquire_exclusive()
            acquired = True
        else:
            acquired = lock.wait_exclusive()
        if not acquired:
            raise EntropyResourceLock.NotAcquired(
                "unable to acquire lock")

    def release(self):
        """
        Overridden from BaseBinaryResourceLock.
        """
        lock = EntropyResourcesLock(output=Server)
        lock.release()

    def __enter__(self):
        """
        Acquire lock. Not thread-safe.
        """
        if self.__inside_with_stmt < 1:
            self.acquire()
        self.__inside_with_stmt += 1
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Release lock. Not thread-safe.
        """
        self.__inside_with_stmt -= 1
        if self.__inside_with_stmt < 1:
            self.release()


class EntropyBinaryPMS(BaseBinaryPMS):
    """
    Class implementing a Binary Package Manager
    System for Matter based on Entropy.
    """

    # Set myself as the default PMS
    DEFAULT = True
    NAME = "entropy"

    class BinaryPMSLoadError(BaseBinaryPMS.BinaryPMSLoadError):
        """ Raised when the BinaryPMS system cannot be initalized. """

    class SpecParserError(BaseBinaryPMS.SpecParserError):
        """ Raised when an invalid SpecParser object is found. """

    class SystemValidationError(BaseBinaryPMS.SystemValidationError):
        """ Raised when the System is not able to accept a Matter run. """

    class RepositoryCommitError(BaseBinaryPMS.RepositoryCommitError):
        """ Raised when a repository push fails. """

    class RepositoryPushError(BaseBinaryPMS.RepositoryPushError):
        """ Raised when a repository push fails. """

    @staticmethod
    def extend_parser(parser):
        """
        Extend Matter ArgumentParser with extra arguments specific
        to this class.
        """
        group = parser.add_argument_group("Entropy Binary PMS")
        group.add_argument(
            "--entropy-community",
            help="enable Community Repository mode",
            action="store_true")

    def __init__(self, cwd, nsargs):
        """
        Constructor.
        """
        if nsargs.entropy_community:
            os.environ['ETP_COMMUNITY_MODE'] = "1"
        super(EntropyBinaryPMS, self).__init__(cwd, nsargs)

        self._real_entropy = None
        self._real_entropy_lock = threading.Lock()

    @property
    def _entropy(self):
        """
        Return the Entropy Server instance object.
        """
        with self._real_entropy_lock:
            if self._real_entropy is None:
                try:
                    self._real_entropy = Server()
                except PermissionDenied as err:
                    raise EntropyBinaryPMS.BinaryPMSLoadError(err)

        return self._real_entropy

    def get_resource_lock(self, blocking):
        """
        Overridden from BaseBinaryPMS.
        """
        return EntropyResourceLock(blocking)

    def shutdown(self):
        """
        Overridden from BaseBinaryPMS.
        """
        with self._real_entropy_lock:
            if self._real_entropy is not None:
                self._real_entropy.shutdown()

    def validate_spec(self, spec):
        """
        Overridden from BaseBinaryPMS.
        """
        repositories = self._entropy.repositories()
        spec_repo = spec["repository"]
        if spec_repo not in repositories:
            raise EntropyBinaryPMS.SpecParserError(
                "invalid repository: %s" % (spec_repo,))

    def validate_system(self):
        """
        Overridden from BaseBinaryPMS.
        """
        super(EntropyBinaryPMS, self).validate_system()

        if self._nsargs.gentle:
            # check if there is something to do
            to_be_added, _to_be_removed, _to_be_injected = \
                self._entropy.scan_package_changes()
            if to_be_added: # only check this, others we can ignore
                to_be_added = [x[0] for x in to_be_added]
                to_be_added.sort()
                err_msg = "--gentle specified, and "
                err_msg += "unstaged packages found:\n"
                for name in to_be_added:
                    err_msg += "  %s\n" % (name,)
                raise EntropyBinaryPMS.SystemValidationError(err_msg)

            # also check for uncommitted configuration files changed
            problems = self._entropy._check_config_file_updates()
            if problems:
                err_msg = "some configuration files have "
                err_msg += "to be merged manually"
                raise EntropyBinaryPMS.SystemValidationError(err_msg)

    def best_available(self, package):
        """
        Overridden from BaseBinaryPMS.
        """
        package_id, repository_id = self._entropy.atom_match(package)
        if package_id == -1:
            return
        atom = self._entropy.open_repository(
            repository_id).retrieveAtom(package_id)
        # revert any entropy related mangling
        atom = entropy.dep.remove_tag(atom)
        return atom

    def _push_packages(self, repository):
        """
        Upload newly built packages.
        """
        (_mirrors_tainted, mirrors_errors,
         successfull_mirrors,
         _broken_mirrors, _check_data) = \
             self._entropy.Mirrors.sync_packages(
                 repository, ask=False, pretend=False)
        if mirrors_errors and not successfull_mirrors:
            return 1
        return 0

    def _push_repository(self, repository):
        """
        Update remote repository.
        """
        return self._entropy.Mirrors.sync_repository(repository)

    def _commit_build_only(self, spec, packages):
        """
        Commit packages that have been built with -B.
        Overridden from BaseBinaryPMS.
        """
        settings, _trees, _db = self.load_emerge_config()
        pkgdir = settings["PKGDIR"]
        repository = spec["repository"]
        drop_old_injected = spec["drop-old-injected"] == "yes"

        print_info("committing build-only packages: %s, to repository: %s" % (
            ", ".join(sorted(packages)), repository,))

        exit_st = 0
        package_files = []
        for package in packages:
            tbz2_atom = package + ".tbz2"
            source_path = os.path.join(pkgdir, tbz2_atom)
            if not os.path.isfile(source_path):
                print_warning(
                    "cannot find package tarball: %s" % (source_path,))
                exit_st = 1
                continue
            package_files.append(source_path)

        pkg_files = [([x], True) for x in package_files]
        package_ids = self._entropy.add_packages_to_repository(
            repository, pkg_files, ask=False)
        self._entropy.commit_repositories()

        if package_ids:

            # drop old injected packages if they are in the
            # same key + slot of the newly added ones.
            # This is not atomic, but we don't actually care.
            if drop_old_injected:
                repo = self._entropy.open_repository(repository)

                key_slots = set()
                for package_id in package_ids:
                    key, slot = repo.retrieveKeySlot(package_id)
                    key_slots.add((key, slot))

                key_slot_package_ids = set()
                for key, slot in key_slots:
                    ks_package_ids = [x for x in repo.searchKeySlot(key, slot) \
                                          if repo.isInjected(x)]
                    key_slot_package_ids.update(ks_package_ids)
                # remove the newly added packages, of course
                key_slot_package_ids -= package_ids
                key_slot_package_ids = sorted(key_slot_package_ids)
                if key_slot_package_ids:
                    print_info("removing old injected packages, "
                               "as per drop-old-injected:")
                    for package_id in key_slot_package_ids:
                        atom = repo.retrieveAtom(package_id)
                        print_info("  %s" % (atom,))
                    self._entropy.remove_packages(
                        repository, key_slot_package_ids)

            self._entropy.dependencies_test(repository)

        return exit_st

    def _commit(self, spec, packages):
        """
        Commit packages that have been merged into the system.
        Overridden from BaseBinaryPMS.
        """
        repository = spec["repository"]
        spm = self._entropy.Spm()
        spm_atoms = set()
        exit_st = 0

        print_info("committing packages: %s, to repository: %s" % (
            ", ".join(sorted(packages)), repository,))

        # if we get here, something has been compiled
        # successfully
        for package in packages:
            try:
                spm_atom = spm.match_installed_package(package)
                spm_atoms.add(spm_atom)
            except KeyError:
                exit_st = 1
                print_warning(
                    "cannot find installed package: %s" % (
                        package,))
                continue

        if not spm_atoms:
            return exit_st

        print_info("about to commit:")
        spm_packages = sorted(spm_atoms)

        for atom in spm_packages:
            item_txt = atom

            # this is a spm atom
            spm_key = portage.dep.dep_getkey("=%s" % (atom,))
            try:
                spm_slot = spm.get_installed_package_metadata(
                    atom, "SLOT")
                spm_repo = spm.get_installed_package_metadata(
                    atom, "repository")
            except KeyError:
                spm_slot = None
                spm_repo = None

            etp_repo = None
            if spm_repo is not None:
                pkg_id, repo_id = self._entropy.atom_match(spm_key,
                    match_slot = spm_slot)
                if repo_id != 1:
                    repo_db = self._entropy.open_repository(repo_id)
                    etp_repo = repo_db.retrieveSpmRepository(pkg_id)

                    if (etp_repo is not None) and (etp_repo != spm_repo):
                        item_txt += ' [%s {%s=>%s}]' % ("warning",
                            etp_repo, spm_repo,)

            print_info(item_txt)

        # always stuff new configuration files here
        # if --gentle was specified, the uncommitted stuff here belongs
        # to our packages.
        # if --gentle was NOT specified, we just don't give a shit
        # Due to bug #2480 -- sometimes (app-misc/tracker)
        # _check_config_file_updates() doesn't return all the files
        subprocess.call("echo -5 | etc-update", shell = True)
        uncommitted = self._entropy._check_config_file_updates()
        if uncommitted:
            # ouch, wtf? better aborting
            print_error("tried to commit configuration file changes and failed")
            return 1

        print_info("about to compress:")

        store_dir = self._entropy._get_local_store_directory(repository)
        package_paths = []
        for atom in spm_packages:
            print_info(atom)
            try:
                pkg_list = spm.generate_package(atom, store_dir)
            except OSError:
                print_traceback()
                print_error("problem during package generation, aborting")
                return 1
            except Exception:
                print_traceback()
                print_error("problem during package generation (2), aborting")
                return 1
            package_paths.append(pkg_list)

        etp_pkg_files = [(pkg_list, False) for pkg_list in package_paths]
        # NOTE: any missing runtime dependency will be added
        # (beside those blacklisted), since this execution is not interactive
        try:
            package_ids = self._entropy.add_packages_to_repository(
                repository, etp_pkg_files, ask=False)
        except OnlineMirrorError as err:
            print_traceback()
            print_error("problem during package commit: %s" % (err,))
            return 1

        self._entropy.commit_repositories()

        if package_ids:
            self._entropy.dependencies_test(repository)

        return exit_st

    def push(self, repository):
        """
        Overridden from BaseBinaryPMS.
        """
        exit_st = self._push_packages(repository)
        if exit_st != 0:
            raise EntropyBinaryPMS.RepositoryPushError(
                "ouch during packages push")

        exit_st = self._push_repository(repository)
        if exit_st != 0:
            raise EntropyBinaryPMS.RepositoryPushError(
                "ouch during repo push")

        return exit_st

    def clear_cache(self):
        """
        Overridden from BaseBinaryPMS.
        """
        for repository_id in self._entropy.repositories():
            repo = self._entropy.open_repository(repository_id)
            repo.clearCache()


BaseBinaryPMS.register(EntropyBinaryPMS)
BaseBinaryPMS.DEFAULT = False


class EntropySpecParser(MatterSpecParser):
    """
    External .spec parser object which implements
    extra .spec parameters support.
    """

    def __init__(self):
        super(EntropySpecParser, self).__init__()
        self._funcs = GenericSpecFunctions()

    def vital_parameters(self):
        """
        Overridden from MatterSpecParser.
        """
        return []

    def data(self):
        """
        Overridden from MatterSpecParser.
        """
        return {
            "drop-old-injected": {
                "cb": self._funcs.valid_yes_no,
                "ve": self._funcs.ve_string_stripper,
                "default": "no",
                "desc": "Drop older packages in the same slot when\n "
                "adding an injected package. Injected packages come\n "
                "into play when 'build-only: yes'",
                },
            }


MatterSpec.register_parser(EntropySpecParser())
