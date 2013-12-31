# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Source Package Manager Plugins foundation classes}.
    @todo: define SpmPlugin API

"""
import os

from entropy.const import etpConst, etpSys, const_is_python3, \
    const_convert_to_rawstring
from entropy.exceptions import SPMError
from entropy.core import Singleton
from entropy.misc import LogFile
from entropy.core.settings.base import SystemSettings

import entropy.tools


class SpmPlugin(Singleton):
    """Base class for Source Package Manager plugins"""

    BASE_PLUGIN_API_VERSION = 12

    # this must be reimplemented by subclasses and value
    # must match BASE_PLUGIN_API_VERSION
    PLUGIN_API_VERSION = -1

    # match_package and match_installed_package supported match_type
    # argument values
    SUPPORTED_MATCH_TYPES = []

    # Name of your Spm Plugin
    PLUGIN_NAME = None

    # At least one of your SpmPlugin classes must be set as default
    # by setting IS_DEFAULT = True
    # There can't be more than _one_ default SPM plugin, in that case
    # the first (alphabetically) one will be automatically selected
    IS_DEFAULT = False

    # Environment dirs, whenever files are installed into this
    # directory during package install or removal, environment_update
    # is triggered
    ENV_DIRS = set()

    class Error(SPMError):
        """
        Base class for Source Package Manager exceptions.
        """

    class PhaseFailure(SPMError):
        """
        Exception raised when Source Package Manager phase
        execution fails with a return code != 0. These exceptions
        should be considered non-fatal.
        """

        def __init__(self, message, code):
            """
            Constructor.

            @param message: failure message
            @type message: string
            @param code: error code
            @type code: int
            """
            super(SpmPlugin.PhaseFailure, self).__init__(message)
            self.code = code
            self.message = message

    class PhaseError(Error):
        """
        Exception raised when executing a package phase.
        """

    class OutdatedPhaseError(PhaseError):
        """
        Exception raised when phase execution detected an outdated version
        of the Source Package Manager.
        """

    def init_singleton(self, output_interface):
        """
        Source Package Manager Plugin singleton method.
        This method must be reimplemented by subclasses.

        @param output_interface: Entropy output interface
        @type output_interface: entropy.output.TextInterface based instances
        @raise NotImplementedError(): when method is not reimplemented
        """
        raise NotImplementedError()

    @staticmethod
    def external_triggers_dir():
        """
        External Entropy triggers executable directory
        This path should be used by SPM to read the trigger for
        packages inside extract_package_metadata()
        """
        return os.path.join(
            etpConst['entropyworkdir'], "triggers", etpSys['arch'])

    @staticmethod
    def get_package_groups():
        """
        Return package groups available metadata (Spm categories are grouped
        into macro categories called "groups").
        """
        raise NotImplementedError()

    def package_metadata_keys(self):
        """
        Return a list of package metadata keys available.

        @return: list of package metadata
        @rtype: list
        """
        raise NotImplementedError()

    @staticmethod
    def package_phases():
        """
        Return a list of available and valid package build phases.
        Default value is ["setup", "preinstall", "postinstall", "preremove",
        "postremove"]

        @return: list of available and valid package build phases
        @rtype: list
        """
        return ["setup", "preinstall", "postinstall", "preremove",
            "postremove", "configure"]

    @staticmethod
    def package_phases_map():
        """
        Return a map of phases names between Entropy (as keys) and
        Source Package Manager.

        @return: map of package phases
        @rtype: dict
        """
        raise NotImplementedError()

    @staticmethod
    def config_files_map():
        """
        Return a map composed by configuration file identifiers and their
        path on disk. These configuration files are related to Source Package
        Manager.

        @return: configuration files map
        @rtype: dict
        """
        raise NotImplementedError()

    @staticmethod
    def binary_packages_extensions():
        """
        Return a list of file extensions belonging to binary packages.
        The list cannot be empty. Elements must be provided without the
        leading dot (for tar.gz, provide "tar.gz" and not ".tar.gz")

        @return: list of supported packages extensions
        @rtype: list
        """
        raise NotImplementedError()

    def get_cache_directory(self, root = None):
        """
        Return Source Package Manager cache directory path.

        @keyword root: specify an alternative root directory "/"
        @type root: string
        @return: cache directory
        @rtype: string
        """
        raise NotImplementedError()

    def get_package_metadata(self, package, key):
        """
        Return package metadata referenced by "key" argument from
        available packages repositories.

        @param package: package name
        @type package: string
        @param key: metadata key (name)
        @type key: string
        @return: package metadata value
        @rtype: string
        """
        raise NotImplementedError()

    def get_package_changelog(self, package):
        """
        Return ChangeLog content for given package.

        @param package: package name
        @type package: string
        @return: changelog
        @rtype: string or None
        """
        raise NotImplementedError()

    def get_package_build_script_path(self, package):
        """
        Return build script path for given package looking through available
        packages repositories.

        @param package: package name
        @type package: string
        @return: build script path
        @rtype: string
        """
        raise NotImplementedError()

    def get_installed_package_build_script_path(self, package, root = None):
        """
        Return build script path for given package looking into installed
        packages repository.

        @param package: package name
        @type package: string
        @keyword root: specify an alternative root directory "/"
        @type root: string
        @return: build script path
        @rtype: string
        """
        raise NotImplementedError()

    def get_installed_package_metadata(self, package, key, root = None):
        """
        Return package metadata referenced by "key" argument from
        installed packages repository.

        @param package: package identifier
        @type package: string
        @param key: metadata key (name)
        @type key: string
        @keyword root: specify an alternative root directory "/"
        @type root: string
        @return: package metadata value
        @rtype: string
        @raise KeyError: if package is not available
        """
        raise NotImplementedError()

    def get_system_packages(self):
        """
        Return list of core (system) packages. Core packages are usually
        consider vital for basic system operativity.

        @return: list of system packages
        @rtype: list
        """
        raise NotImplementedError()

    def get_package_categories(self):
        """
        Return list of package categories in available packages repositories.

        @return: list of package categories
        @rtype: list
        """
        raise NotImplementedError()

    def get_package_category_description_metadata(self, category):
        """
        Return metadata for given package category containing description in
        all the available languages. Data is returned in dict form, locale
        names as key, description text as value.

        @param category: package category name
        @type category: string
        @return: category description metadata
        @rtype: dict
        """
        raise NotImplementedError()

    def get_security_packages(self, security_property):
        """
        Return a list of packages affected by given security property argument.
        Valid security_property values are: affected, new, all.

        @param security_property: packages security property
        @type security_property: string
        @return: list of packages affected by given security property
        @rtype: list
        """
        raise NotImplementedError()

    def get_security_advisory_metadata(self, advisory_id):
        """
        Return Source Package Manager package security advisory metadata
        for given security advisory identifier.

        @param advisory_id: security advisory identifier
        @type advisory_id: string
        @return: advisory metadata
        @rtype: dict
        """
        raise NotImplementedError()

    def get_setting(self, key):
        """
        Return Source Package Manager setting referenced by "key"

        @param key: source package manager setting
        @type key: string
        @raise KeyError: if setting is not available
        """
        raise NotImplementedError()

    def get_user_installed_packages_file(self, root = None):
        """
        Return path to file containing list (one per line) of packages
        installed by user (in Portage world, this is the world file).

        @keyword root: specify an alternative root directory "/"
        @type root: string
        @return: path to installed packages list file
        @rtype: string
        """
        raise NotImplementedError()

    def get_merge_protected_paths(self):
        """
        Return a list of paths (either directories or files) whose are
        protected from direct merge requiring user approval.

        @return: list of protected paths
        @rtype: list
        """
        raise NotImplementedError()

    def get_merge_protected_paths_mask(self):
        """
        Return a list of unprotected paths (either directories or files) which
        reside inside a protected path (see get_merge_protected_paths()).
        """
        raise NotImplementedError()

    def get_download_mirrors(self, mirror_name):
        """
        Return list of download mirror URLs for given mirror name

        @param mirror_name: mirror name
        @type mirror_name: string
        @return: list of download URLs
        @rtype: list
        """
        raise NotImplementedError()

    def packages_repositories_metadata_update(self, actions):
        """
        Executes Source Package Manager available packages repositories
        metadata update.

        @param actions: a list of metadata update strings
        @type actions: list
        """
        raise NotImplementedError()

    def log_message(self, message):
        """
        Log message string to logfile.

        @param message: message string to log
        @type message: string
        """
        with LogFile(
            level = SystemSettings()['system']['log_level'],
            filename = etpConst['entropylogfile'], header = "[spm]") as log:
            log.write(message)

    def match_package(self, package, match_type = None):
        """
        Match a package looking through available packages repositories using
        the given match term argument (package) and match type (validity
        defined by subclasses).

        @param package: package string to match inside available repositories
        @type package: string
        @keyword match_type: match type
        @type match_type: string
        @return: matched package (atom) or None
        @rtype: string or list or None
        @raise KeyError: if match_type is not valid
        """
        raise NotImplementedError()

    def match_installed_package(self, package, match_all = False, root = None):
        """
        Match a package looking through installed packages repository using
        the given match term argument (package).

        @param package: package string to match inside installed packages
            repository
        @type package: string
        @keyword match_all: return all the matching packages, not just the best
        @type match_all: bool
        @keyword root: specify an alternative root directory "/"
        @type root: string
        @return: matched package (atom) or None
        @rtype: string or list or None
        @raise KeyError: if match_type is not valid
        """
        raise NotImplementedError()

    def generate_package(self, package, file_save_path, builtin_debug = False):
        """
        Generate package tarball files for given package, from running system.
        All the information is recomposed from system.

        @param package: package name
        @type package: string
        @param file_save_path: exact path (including file name and extension)
            where package file is saved
        @type file_save_path: string
        @keyword builtin_debug: embed debug files into the generated package
            file. If False, another package file is generated and appended to
            the return list.
        @type builtin_debug: bool
        @return: list of package file paths, the first is the main one, the
            second in list, if available, is the debug package. All these
            extra package files must end with etpConst['packagesextraext']
            extension.
        @rtype: list
        @raise entropy.exception.SPMError: if unable to satisfy the request
        """
        raise NotImplementedError()

    def extract_package_metadata(self, package_file, license_callback = None,
        restricted_callback = None):
        """
        Extract Source Package Manager package metadata from given file.

        @param package_file: path to valid SPM package file
        @type package_file: string
        @keyword license_callback: if not None, it will be used to determine
            if package_file can be considered free (as in freedom) or not.
            Please return True if so, otherwise false. The signature of
            the callback is: bool callback(pkg_metadata).
        @type license_callback: callable
        @keyword restricted_callback: if not None, it will be used to determine
            if package_file can be considered legal in all countries or not.
            Please return True if so, otherwise false. The signature of
            the callback is: bool callback(pkg_metadata).
        @type restricted_callback: callable
        @return: package metadata extracted
        @rtype: dict
        @raise entropy.exceptions.SPMError: when something went bad
        """
        raise NotImplementedError()

    def get_installed_package_content(self, package, root = None):
        """
        Return list of files/directories owned by package.

        @param package: package name
        @type package: string
        @keyword root: specify an alternative root directory "/"
        @type root: string
        @return: list of files/directories owned by package
        @rtype: list
        """
        raise NotImplementedError()

    def get_packages(self, categories = None, filter_reinstalls = False):
        """
        Return list of packages found in available repositories.
        Extra "filtering" arguments can be passed like "categories", which
        will make this method returning only packages found in given category
        list and "filter_reinstalls" which will actually filter out packages
        already installed (with no updates nor downgrades available).

        @keyword categories: list of package categories to look into
        @type categories: iterable
        @keyword filter_reinstalls: enable reinstall packages filter
        @type filter_reinstalls: bool
        @return: list of available packages found
        @rtype: list
        @todo: improve method, move filter_reinstalls to another function?
        """
        raise NotImplementedError()

    def compile_packages(self, packages, stdin = None, stdout = None,
        stderr = None, environ = None, pid_write_func = None,
        pretend = False, verbose = False, fetch_only = False,
        build_only = False, no_dependencies = False,
        ask = False, coloured_output = False, oneshot = False):
        """
        Compile given packages using given compile options. Extra compiler
        options can be set via environmental variables (CFLAGS, LDFLAGS, etc).
        By default, this function writes to stdout and can potentially interact
        with user via stdin/stdout/stderr.
        By default, when build_only=False, compiled packages are installed onto
        the running system.

        @param packages: list of Source Package Manager package names
        @type packages: list
        @keyword stdin: custom standard input
        @type stdin: file object or valid file descriptor number
        @keyword stdout: custom standard output
        @type stdout: file object or valid file descriptor number
        @keyword stderr: custom standard error
        @type stderr: file object or valid file descriptor number
        @keyword environ: dict
        @type environ: map of environmental variables
        @keyword pid_write_func: function to call with execution pid number
        @type pid_write_func: callable function, signature func(int_pid_number)
        @keyword pretend: just show what would be done
        @type pretend: bool
        @keyword verbose: execute compilation in verbose mode
        @type verbose: bool
        @keyword fetch_only: fetch source code only
        @type fetch_only: bool
        @keyword build_only: do not actually touch live system (don't install
            compiled
        @type build_only: bool
        @keyword no_dependencies: ignore possible build time dependencies
        @type no_dependencies: bool
        @keyword ask: ask user via stdin before executing the required tasks
        @type ask: bool
        @keyword coloured_output: allow coloured output
        @type coloured_output: bool
        @keyword oneshot: when compiled packages are intended to not get
            recorded into personal user compile preferences (if you are not
            using a Portage-based SPM, just ignore this)
        @type oneshot: bool
        @return: execution status
        @rtype: int
        """
        raise NotImplementedError()

    def print_build_environment_info(self, stdin = None, stdout = None,
        stderr = None, environ = None, pid_write_func = None,
        coloured_output = False):
        """
        Print build environment info to stdout.

        @keyword stdin: custom standard input
        @type stdin: file object or valid file descriptor number
        @keyword stdout: custom standard output
        @type stdout: file object or valid file descriptor number
        @keyword stderr: custom standard error
        @type stderr: file object or valid file descriptor number
        @keyword environ: dict
        @type environ: map of environmental variables
        @keyword pid_write_func: function to call with execution pid number
        @type pid_write_func: callable function, signature func(int_pid_number)
        @keyword coloured_output: allow coloured output
        @type coloured_output: bool
        @return: execution status
        @rtype: int
        """
        raise NotImplementedError()

    def environment_update(self):
        """
        Hook used by Entropy Client and Entropy Server to ask Source Package
        Manager to update /etc/profile* and other environment settings around.
        Since this is part of the Source Package Manager metaphor it must stay
        in this class.

        @return: execution status
        @rtype: int
        """
        raise NotImplementedError()

    def get_installed_packages(self, categories = None, root = None):
        """
        Return list of packages found in installed packages repository.
        Extra "filtering" arguments can be passed like "categories", which
        will make this method returning only packages found in given category
        list.

        @keyword categories: list of package categories to look into
        @type categories: iterable
        @keyword root: specify an alternative root directory "/"
        @type root: string
        @return: list of installed packages found
        @rtype: list
        """
        raise NotImplementedError()

    def get_package_sets(self, builtin_sets):
        """
        Package sets are groups of packages meant to ease user installation and
        removal of large amount of applications or libraries.
        The difference between package groups is that sets can be referenced
        anywhere inside Entropy, while the former is just a simple way to
        group pacakge categories, usually too hard to understand (for eg.
        "sys-apps" or "app-misc", where user has no clue about the meaning of
        these).
        Third party implementations of SPM can just return empty data if
        this feature is not wanted or implementable.

        @param builtin_sets: if True, also return SPM built-in package sets
        @type builtin_sets: bool
        @return: dictionary featuring set name as key, list (set) of package
            dependencies as value
        @rtype: dict
        """
        raise NotImplementedError()

    def assign_uid_to_installed_package(self, package, root = None):
        """
        Assign a new Unique Identifier to installed package and return it.

        @param package: package name
        @type package: string
        @keyword root: specify an alternative root directory "/"
        @type root: string
        @return: assigned Unique Identifier
        @rtype: int
        """
        raise NotImplementedError()

    def resolve_package_uid(self, entropy_repository,
        entropy_repository_package_id):
        """
        This is the bridge between Entropy package repository and its Source
        Package Manager backend. Given an EntropyRepository instance and its
        package identifier (which is available inside it). Return the package
        Unique Identifier that is bound to it, if available, otherwise return
        None. This function is used by EntropyRepository to regenerate
        Entropy<->Spm package bindings.

        @param entropy_repository: EntropyRepository instance
        @param entropy_repository_package_id: EntropyRepository instance package
            identifier
        @type entropy_repository: EntropyRepository
        @type entropy_repository_package_id: int
        @return: bound Source Package Manager Unique Identifier
        @rtype: int
        @raise SPMError: in case of critical issues
        """
        raise NotImplementedError()

    def resolve_spm_package_uid(self, package):
        """
        Given a Source Package Manager atom, return its UID.

        @param package: Source Package Manager atom
        @type package: string
        @return: Source Package Manager UID for package
        @rtype: int
        @raise KeyError: in case the package cannot be resolved into UID.
        """
        raise NotImplementedError()

    def convert_from_entropy_package_name(self, entropy_package_name):
        """
        This function should be able to convert an Entropy package name (atom)
        to a Source Package Manager one.

        @param entropy_package_name: Entropy package name string
        @type entropy_package_name: string
        @return: Source Package Manager package name string
        @rtype: string
        """
        raise NotImplementedError()

    def search_paths_owners(self, paths, exact_match = True):
        """
        Return list of packages owning provided list of paths.
        A dictionary is returned containing package name as key and list of
        matched paths as value.

        @param paths: list of paths to resolve
        @type paths: list
        @keyword exact_match: match paths exactly
        @type exact_match: bool
        @return: packages owning list of paths
        @rtype: dict
        """
        raise NotImplementedError()

    @staticmethod
    def execute_qa_tests(package_path):
        """
        Execute Source Package Manager based QA tests on Entropy package
        files. This method can be used to test Entropy produced packages
        to make sure that they are fine on this side too. It is called
        by Entropy QA module (entropy.qa).

        @param package_path: path to Entropy package
        @type package_path: string
        @return: tuple composed by error status and error message (if any).
            Error status is an int with != 0 values if error occurred.
        @rtype: tuple
        """
        raise NotImplementedError()

    @staticmethod
    def execute_system_qa_tests(entropy_output):
        """
        Execute Source Package Manager based QA tests on the whole system.
        This method can be used to make sure that at the time of pushing
        a new Entropy repository, the system is in consistent state.
        It is called by Entropy Server, during pre-repository upload QA
        checks. This method must return a tuple composed by exit status and
        error message. Error message is considered only if exit status != 0.

        @param entropy_output: a valid text output interface
        @type entropy_output: TextInterface object
        @return: tuple composed by error status and error message (if any).
            Error status is an int with != 0 values if error occurred.
        @rtype: tuple
        """
        raise NotImplementedError()

    def append_metadata_to_package(self, entropy_package_name, package_path):
        """
        Append Source Package Manager metadata bits to an Entropy package,
        known its name and path.

        @param entropy_package_name: Entropy package name
        @type entropy_package_name: string
        @param package_path: Entropy package path
        @type package_path: string
        @return: True, if metadata has been appended successfully
        @rtype: bool
        """
        raise NotImplementedError()

    @staticmethod
    def dump_package_metadata(entropy_package_path, metadata_path):
        """
        Extract raw Source Package Manager metadata from Entropy package.
        This is the opposite of "append_metadata_to_package()".
        This method must dump it's data to metadata_path and return True.

        @param entropy_package_path: path to Entropy package file
        @type entropy_package_path: string
        @param metadata_path: Entropy package path
        @type metadata_path: string
        @return: True, if metadata has been appended successfully
        @rtype: bool
        """
        raise NotImplementedError()

    @staticmethod
    def aggregate_package_metadata(entropy_package_path, metadata_path):
        """
        Aggregate raw Source Package Manager metadata contained in metadata_path
        to Entropy package.
        This is the opposite of "dump_package_metadata()".
        This method must dump it's data to entropy_package_path and return True.

        @param entropy_package_path: path to Entropy package file
        @type entropy_package_path: string
        @param metadata_path: Entropy package path
        @type metadata_path: string
        @return: True, if metadata has been appended successfully
        @rtype: bool
        """
        raise NotImplementedError()

    def package_names_update(self, entropy_repository, entropy_repository_id,
        entropy_server, entropy_branch):
        """
        WARNING: this is an Entropy Server functionality.
        Execute the synchronization (if needed) of Source Package Manager
        package names with Entropy ones, stored inside the passed
        EntropyRepository instance (entropy_repository) referenced by an unique
        identifier (entropy_repository_id) for the given Entropy packages branch
        (entropy_branch). This method must also take care of the Entropy package
        names update file returned by Entropy server instance (entropy_server)
        method "get_local_database_treeupdates_file".
        If your Source Package Manager packages are subject to name changes, you
        must implement this method to effectively keep Entropy aligned with it.

        @param entropy_repository: EntropyRepository instance
        @type entropy_repository: entropy.db.EntropyRepository
        @param entropy_repository_id: Entropy Repository unique identifier
        @type entropy_repository_id: string
        @param entropy_server: Entropy Server instance
        @type entropy_server: entropy.server.interfaces.Server instance
        @param entropy_branch: Entropy branch string (may be handy to selectively
            execute updates based on working branch)
        @type entropy_branch: string (SystemSettings['repositories']['branch'])
        """
        raise NotImplementedError()

    def execute_package_phase(self, action_metadata, package_metadata,
        action_name, phase_name):
        """
        Execute Source Package Manager package phase (postinstall, preinstall,
        preremove, postremove, etc).

        @param action_metadata: metadata bound to the action and not to the
            actual phase requested (for example, when updating a package,
            during the removal phase, action_metadata contains the new
            package -- being merged -- metadata)
        @type action_metadata: dict or None
        @param package_metadata: Entropy package phase metadata
        @type package_metadata: dict
        @param action_name: Entropy package action name, can be "install",
            "remove"
        @type action_name: string
        @param phase_name: name of the phase to call, must be a valid phase
            contained in package_phases() output.
        @type phase_name: string
        @raise KeyError: if phase is not available
        @raise SpmPlugin.PhaseFailure: when the phase executed but returned a
            non-zero exit status. These exceptions should be considered
            non-fatal
        @raise SpmPlugin.PhaseError: when the phase cannot be executed
        @raise SpmPlugin.OutdatedPhaseError: when Source Package Manager is
            too old to execute the phase. This is a subclass of PhaseError
        """
        raise NotImplementedError()

    @staticmethod
    def allocate_protected_file(package_file_path, destination_file_path):
        """
        Allocate a configuration protected file. This method returns a new
        destination_file_path value that is used by Entropy Client code to
        merge file at package_file_path to live system.
        This method offers basic support for Entropy ability to protect user
        configuration files against overwrites. Any subclass can hook code
        here in order to trigger extra actions on every acknowledged
        path modification.

        @param package_file_path: a valid file path pointing to the file
            that Entropy Client is going to move to destination_file_path
        @type package_file_path: string
        @param destination_file_path: the default destination path for given
            package_file_path. It points to the live system.
        @type destination_file_path: string
        @return: Tuple (of length 2) composed by (1) a new destination file
            path. Please note that it can be the same of the one passed
            (destination_file_path) if no protection is taken (for eg. when
            md5 of proposed_file_path and destination_file_path is the same)
            and (2) a bool informing if the function actually protected the
            destination file. Unfortunately, the bool bit is stil required
            in order to provide a valid new destination_file_path in any case.
        @rtype tuple
        """
        pkg_path_os = package_file_path
        dest_path_os = destination_file_path
        if not const_is_python3():
            pkg_path_os = const_convert_to_rawstring(package_file_path)
            dest_path_os = const_convert_to_rawstring(destination_file_path)

        if os.path.isfile(dest_path_os) and \
            os.path.isfile(pkg_path_os):
            old = entropy.tools.md5sum(package_file_path)
            new = entropy.tools.md5sum(destination_file_path)
            if old == new:
                return destination_file_path, False

        dest_dirname = os.path.dirname(destination_file_path)
        dest_basename = os.path.basename(destination_file_path)

        counter = -1
        newfile = ""
        newfile_os = newfile
        previousfile = ""
        previousfile_os = previousfile
        while True:

            counter += 1
            txtcounter = str(counter)
            oldtxtcounter = str(counter-1)
            txtcounter_len = 4-len(txtcounter)
            cnt = 0

            while cnt < txtcounter_len:
                txtcounter = "0"+txtcounter
                oldtxtcounter = "0"+oldtxtcounter
                cnt += 1

            newfile = os.path.join(dest_dirname,
                "._cfg%s_%s" % (txtcounter, dest_basename,))
            if counter > 0:
                previousfile = os.path.join(dest_dirname,
                    "._cfg%s_%s" % (oldtxtcounter, dest_basename,))
            else:
                previousfile = os.path.join(dest_dirname,
                    "._cfg0000_%s" % (dest_basename,))

            newfile_os = newfile
            if not const_is_python3():
                newfile_os = const_convert_to_rawstring(newfile)

            previousfile_os = previousfile
            if not const_is_python3():
                previousfile_os = const_convert_to_rawstring(previousfile)

            if not os.path.lexists(newfile_os):
                break

        if not newfile:
            newfile = os.path.join(dest_dirname,
                "._cfg0000_%s" % (dest_basename,))
        else:

            if os.path.exists(previousfile_os):

                # compare package_file_path with previousfile
                new = entropy.tools.md5sum(package_file_path)
                old = entropy.tools.md5sum(previousfile)
                if new == old:
                    return previousfile, False

                # compare old and new, if they match,
                # suggest previousfile directly
                new = entropy.tools.md5sum(destination_file_path)
                old = entropy.tools.md5sum(previousfile)
                if new == old:
                    return previousfile, False

        return newfile, True

    def add_installed_package(self, package_metadata):
        """
        Add package installed by Entropy to SPM database too.
        "package_metadata" is a dictionary featuring the following (relevant)
        keys:
            ['accept_license', 'imagedir', 'xpakpath', 'slot', 'pkgdbpath',
             'versiontag', 'version', 'xpakstatus', 'unpackdir', 'revision',
             'category', 'repository', 'xpakdir', 'name', 'install_source',
            ]

        @param package_metadata: Entropy package metadata
        @type package_metadata: dict
        @return: SPM installed package UID or -1
        @rtype: int
        """
        raise NotImplementedError()

    def remove_installed_package(self, atom, package_metadata):
        """
        Remove installed package from SPM database.
        "package_metadata" is a dictionary featuring the following (relevant)
        keys:
            ['accept_license', 'imagedir', 'xpakpath', 'slot', 'pkgdbpath',
             'versiontag', 'version', 'xpakstatus', 'unpackdir', 'revision',
             'category', 'repository', 'xpakdir', 'name', 'install_source',
            ]

        @param atom: the Entropy package atom
        @type atom: string
        @param package_metadata: Entropy package metadata
        @type package_metadata: dict
        @return: execution status
        @rtype: int
        """
        raise NotImplementedError()

    @staticmethod
    def entropy_client_post_repository_update_hook(entropy_client,
        entropy_repository_id):
        """
        This function is called by Entropy Client when updating Entropy
        repositories. Place here all your Source Package Manager bullshit and,
        remember to return an int form execution status.

        @param entropy_client: Entropy Client interface instance
        @type entropy_client: entropy.client.interfaces.Client.Client
        @param entropy_repository_id: Entropy Repository unique identifier
        @type: string
        @return: execution status
        @rtype: int
        """
        raise NotImplementedError()

    @staticmethod
    def entropy_install_setup_hook(entropy_client, package_metadata):
        """
        This function is called by Entropy Client during package metadata setup.
        It is intended to be used to inject additional metadata (that would be
        used afterwards in other entropy_install_* hooks) to entropy package
        install metadata.
        Note: for performance reasons, this is a static method !

        @param entropy_client: Entropy Client interface instance
        @type entropy_client: entropy.client.interfaces.Client.Client
        @param package_metadata: Entropy package metadata
        @type package_metadata: dict
        @return: execution status
        @rtype: int
        """
        raise NotImplementedError()


    @staticmethod
    def entropy_install_unpack_hook(entropy_client, package_metadata):
        """
        This function is called by Entropy Client during package installation,
        unpack phase. It is intended to be used to extract, if required,
        Source Package Manager metadata from Entropy packages useful for
        installing package into Source Package Manager plugin too.
        For example, PortagePlugin uses this hook to extract xpak metadata
        from entropy package files and setup Portage directories.
        Note: for performance reasons, this is a static method !

        @param entropy_client: Entropy Client interface instance
        @type entropy_client: entropy.client.interfaces.Client.Client
        @param package_metadata: Entropy package metadata
        @type package_metadata: dict
        @return: execution status
        @rtype: int
        """
        raise NotImplementedError()

    def installed_mtime(self, root = None):
        """
        Return the installed packages repository mtime that can be used
        for cache validation.

        @keyword root: specify an alternative root directory "/"
        @type root: string
        @return: the installed repository mtime value
        @rtype: float
        """
        raise NotImplementedError()

    def clear(self):
        """
        Clear any allocated resources or caches.
        """
        return
