# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Matter TinderBox Toolkit}.

    Basic implementation of a Binary Package Manager interface
    to Matter.

"""
import errno
import os
import shutil
import subprocess

from matter.output import print_info, print_warning


class BaseBinaryResourceLock(object):
    """
    This class exposes a Lock-like interface for acquiring PMS
    resources.
    """

    class NotAcquired(Exception):
        """ Raised when Lock cannot be acquired """

    def __init__(self, blocking):
        """
        BaseBinaryResourceLock constructor.

        @param blocking: acquire lock in blocking mode?
        @type blocking: bool
        """
        self._blocking = blocking

    def acquire(self):
        """
        Acquire the Resource Lock.
        """

    def release(self):
        """
        Release the Resource Lock.
        """

    def __enter__(self):
        """
        Acquire lock. Not thread-safe.
        """

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Release lock. Not thread-safe.
        """


class BaseBinaryPMS(object):
    """
    Base class for implementing a Binary Package Manager
    System for Matter.
    """

    available_pms = []
    DEFAULT = True
    NAME = "portage"


    @staticmethod
    def register(klass):
        """
        Register a Binary PMS object so that it can be loaded
        by Matter at initialization time.
        """
        BaseBinaryPMS.available_pms.append(klass)

    @staticmethod
    def extend_parser(parser):
        """
        Extend Matter ArgumentParser with extra arguments specific
        to this class.
        """
        group = parser.add_argument_group("Portage Binary PMS")
        group.add_argument(
            "--portage-pkgpush", metavar="<exec>", type=file,
            help="executable called during the binary packages "
            "push phase, it takes the committed packages directory "
            "path as first argument (a custom PKGDIR, see Portage "
            "documentation on that)", default=None)

    class BasePMSError(Exception):
        """ Base exception for all the BaseBinaryPMS exceptions. """

    class BinaryPMSLoadError(BasePMSError):
        """ Raised when the BinaryPMS system cannot be initalized. """

    class SpecParserError(BasePMSError):
        """ Raised when an invalid SpecParser object is found. """

    class SystemValidationError(BasePMSError):
        """ Raised when the System is not able to accept a Matter run. """

    class RepositoryCommitError(BasePMSError):
        """ Raised when a repository commit fails. """

    class RepositoryPushError(BasePMSError):
        """ Raised when a repository push fails. """

    def __init__(self, cwd, nsargs):
        """
        Constructor.

        @param cwd: currently working directory path
        @type cwd: string
        @param nsargs: ArgumentParser's parsed arguments
        @type nsargs: ArgumentParser
        """
        self._cwd = cwd
        self._nsargs = nsargs

        from _emerge.actions import load_emerge_config
        self._cfg_loader = load_emerge_config

        from _emerge.main import parse_opts
        self._parse_opts = parse_opts

    def _build_pkgdir(self, repository):
        """
        Build the repository PKGDIR environment variable.
        """
        return os.path.join("/usr/matter", repository, "packages")

    def get_resource_lock(self, blocking):
        """
        Return a Binary Package Manager resource lock
        object that Matter can use to acquire exclusive
        access to the PMS.
        The base implementation does not do anything.

        @param blocking: if True, the lock is acquired in
            blocking mode, otherise not. If lock cannot be
            acquired, a BaseBinaryResourceLock.NotAcquired
            exception is raised.
        @type blocking: bool
        @return: a BaseBinaryResourceLock based instance.
        @rtype: BaseBinaryResourceLock
        """
        return BaseBinaryResourceLock(blocking)

    def shutdown(self):
        """
        Shutdown the Binary Package Manager System.
        """

    def validate_spec(self, spec):
        """
        Validate Matter SpecParser's .spec file metadata.

        @param spec: a SpecParser object.
        @type spec: SpecParser
        @raises SpecParserError: if the SpecParser object contains
            invalid metadata.
        """

    def best_available(self, package):
        """
        Given a package dependency, return the best available match atom.
        The returned string must be in a Portage-readable atom string.
        Return None for no matches or unsupported feature.

        @param package: a package dependency.
        @type package: string or None
        """

    def check_preserved_libraries(self, emerge_config=None):
        """
        Ask Portage whether there are preserved libraries on the system.
        This usually indicates that Entropy packages should not be really
        committed.

        @keyword emerge_config: tuple returned by load_emerge_config(),
            -> (emerge_settings, emerge_trees, mtimedb)
        @type emerge_config: tuple
        @return: True, if preserved libraries are found
        @rtype: bool
        """
        if emerge_config is None:
            emerge_config = self.load_emerge_config()
        emerge_settings, emerge_trees, _mtimedb = emerge_config
        vardb = emerge_trees[emerge_settings["ROOT"]]["vartree"].dbapi
        vardb._plib_registry.load()
        return vardb._plib_registry.hasEntries()

    def load_emerge_config(self):
        """
        Call _emerge.load_emerge_config() to load Portage configuration
        and return it.
        """
        return self._cfg_loader()

    def validate_system(self):
        """
        Validate System status. Check whether system is ready
        to accept a Matter execution.
        If System is not ready, a SystemValidationError exception
        is raised.
        """
        if not self._nsargs.disable_preserved_libs:
            if self.check_preserved_libraries():
                raise BaseBinaryPMS.SystemValidationError(
                    "preserved libraries are found on "
                    "the system, aborting.")

    def _commit_build_only(self, spec, packages):
        """
        Commit packages that have been built with -B.
        Just move the Portage generated tbz2s to our PKGDIR.
        """
        repository = spec["repository"]
        matter_pkgdir = self._build_pkgdir(repository)

        print_info("committing build-only packages: %s, to PKGDIR: %s" % (
            ", ".join(sorted(packages)), matter_pkgdir,))

        settings, _trees, _db = self.load_emerge_config()
        pkgdir = settings["PKGDIR"]

        exit_st = 0
        for package in packages:
            tbz2_atom = package + ".tbz2"
            source_path = os.path.join(pkgdir, tbz2_atom)
            if not os.path.isfile(source_path):
                print_warning(
                    "cannot find package tarball: %s" % (source_path,))
                exit_st = 1
                continue

            dest_path = os.path.join(matter_pkgdir, tbz2_atom)
            dest_dir = os.path.dirname(dest_path)
            try:
                os.makedirs(dest_dir)
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise

            try:
                shutil.move(source_path, dest_path)
            except shutil.Error as err:
                raise BaseBinaryPMS.RepositoryCommitError(
                    "cannot commit packages, generic error: %s" % (
                        repr(err),))
            except (OSError, IOError) as err:
                raise BaseBinaryPMS.RepositoryCommitError(
                    "cannot commit packages, system error: %s" % (
                        repr(err),))

        return exit_st

    def _commit(self, spec, packages):
        """
        Commit packages that have been merged into the system.
        """
        repository = spec["repository"]
        pkgdir = self._build_pkgdir(repository)
        print_info("committing packages: %s, to PKGDIR: %s" % (
            ", ".join(sorted(packages)), pkgdir,))

        env = os.environ.copy()
        env["PKGDIR"] = pkgdir
        exit_st = subprocess.call(
            ["quickpkg", "--include-config=y"] + [
                "=" + x for x in packages], env=env)
        if exit_st != 0:
            raise BaseBinaryPMS.RepositoryCommitError(
                "cannot commit packages, exit status: %d" % (
                exit_st,))
        return exit_st

    def commit(self, spec, packages):
        """
        Commit packages to the BinaryPMS repository specified in the
        Spec object.
        """
        build_only = spec["build-only"] == "yes"
        if build_only:
            return self._commit_build_only(spec, packages)
        return self._commit(spec, packages)

    def push(self, repository):
        """
        Push all the packages built by PackageBuilder to the
        repository.
        """
        pkgpush_f = self._nsargs.portage_pkgpush
        if pkgpush_f is None:
            return 0

        hook_name = pkgpush_f.name
        if not hook_name.startswith("/"):
            # complete with current directory
            hook_name = os.path.join(self._cwd, hook_name)

        pkgdir = self._build_pkgdir(repository)
        env = os.environ.copy()
        env["PKGDIR"] = pkgdir

        exit_st = subprocess.call(
            [hook_name, pkgdir], env=env)
        if exit_st != 0:
            raise BaseBinaryPMS.RepositoryPushError(
                "cannot push packages, exit status: %d" % (
                    exit_st,))
        return exit_st

    def clear_cache(self):
        """
        Clear memory caches that could have become stale.
        """
        pass


BaseBinaryPMS.register(BaseBinaryPMS)
