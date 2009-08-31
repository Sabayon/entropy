# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Source Package Manager Plugins foundation classes}.
    @todo: define SpmPlugin API

"""

from entropy.const import etpConst
from entropy.core import Singleton
from entropy.misc import LogFile

class SpmPlugin(Singleton):
    """Base class for Source Package Manager plugins"""

    BASE_PLUGIN_API_VERSION = 0

    # this must be reimplemented by subclasses and value
    # must match BASE_PLUGIN_API_VERSION
    PLUGIN_API_VERSION = -1

    # match_package and match_installed_package supported match_type
    # argument values
    SUPPORTED_MATCH_TYPES = []

    def init_singleton(self, output_interface):
        """
        Source Package Manager Plugin singleton method.
        This method must be reimplemented by subclasses.
        At this stage, you should also consider to tweak etpConst['spm']
        content (importing etpConst from entropy.const).

        @param output_interface: Entropy output interface
        @type output_interface: entropy.output.TextInterface based instances
        @raise NotImplementedError(): when method is not reimplemented
        """
        raise NotImplementedError()

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

    def package_phases(self):
        """
        Return a list of available and valid package build phases.
        Default value is ["setup", "preinstall", "postinstall", "preremove",
        "postremove"]

        @return: list of available and valid package build phases
        @rtype: list
        """
        return ["setup", "preinstall", "postinstall", "preremove",
            "postremove", "configure"]

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

    def packages_repositories_metadata_update(self):
        """
        Executes Source Package Manager available packages repositories
        metadata update.
        """
        raise NotImplementedError()

    def log_message(self, message):
        """
        Log message string to logfile.

        @param message: message string to log
        @type message: string
        """
        log = LogFile(
            level = etpConst['spmloglevel'],
            filename = etpConst['spmlogfile'],
            header = "[spm]"
        )
        log.write(message)
        log.flush()
        log.close()

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

    def generate_package(self, package, file_save_path):
        """
        Generate a package tarball file for given package, from running system.
        All the information is recomposed from system.

        @param package: package name
        @type package: string
        @param file_save_path: exact path (including file name and extension)
            where package file is saved
        @type file_save_path: string
        @return: None
        @rtype: None
        @raise entropy.exception.SPMError: if unable to satisfy the request
        """
        raise NotImplementedError()

    def extract_package_metadata(self, package_file):
        """
        Extract Source Package Manager package metadata from given file.

        @param package_file: path to valid SPM package file
        @type package_file: string
        @return: package metadata extracted
        @rtype: dict
        @raise entropy.exceptions.SPMError: when something went bad
        """
        raise NotImplementedError()

    def enable_package_compile_options(self, package, options):
        """
        WARNING: this is an Entropy Server functionality.
        Enable compile options (also known as USE flags) for package.
        Compile options are intended to be features that package can
        expose to other packages or directly to user.

        @param package: package name
        @type package: string
        @param options: list of compile options to enable
        @type options: string
        @return: enable status, True if enabled, False if not
        @rtype: bool
        """
        raise NotImplementedError()

    def disable_package_compile_options(self, package, options):
        """
        WARNING: this is an Entropy Server functionality.
        Disable compile options (also known as USE flags) for package.
        Compile options are intended to be features that package can
        expose to other packages or directly to user.

        @param package: package name
        @type package: string
        @param options: list of compile options to disable
        @type options: string
        @return: enable status, True if disabled, False if not
        @rtype: bool
        """
        raise NotImplementedError()

    def get_package_compile_options(self, package):
        """
        WARNING: this is an Entropy Server functionality.
        Return currently configured compile options (also known as USE flags)
        for given package.
        There can be different kinds of compile options so a dictionary should
        be returned with compile options identifier as key and list of options
        as value.
        This method looks through available packages repositories.

        @param package: package name
        @type package: string
        @return: compile options
        @rtype: dict
        """
        raise NotImplementedError()

    def get_installed_package_compile_options(self, package, root = None):
        """
        WARNING: this is an Entropy Server functionality.
        Return currently configured compile options (also known as USE flags)
        for given package.
        There can be different kinds of compile options so a dictionary should
        be returned with compile options identifier as key and list of options
        as value.
        This method looks into installed packages repository.

        @param package: package name
        @type package: string
        @keyword root: specify an alternative root directory "/"
        @type root: string
        @return: compile options
        @rtype: dict
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

    def execute_package_phase(self, package, build_script_path, phase_name,
        work_dir = None, licenses_accepted = None):
        """
        Execute Source Package Manager package phase (postinstall, preinstall,
        preremove, postremove, etc).

        @param package: package name
        @type package: string
        @param build_script_path: path to Source Package Manager build script
            to call
        @type build_script_path: string
        @param phase_name: name of the phase to call, must be a valid phase
            contained in package_phases() output.
        @type phase_name: string
        @keyword work_dir: specify a work directory if required by your SPM
        @type work_dir: string
        @keyword licenses_accepted: list of license names already accepted
            that can be given to Source Package Manager (to skip its license
            acceptance verification stuff, for example)
        @type licenses_accepted: list
        @return: phase script exit status
        @rtype: int
        @raise KeyError: if phase is not available
        """
        raise NotImplementedError()

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

    def remove_installed_package(self, package_metadata):
        """
        Remove installed package from SPM database.
        "package_metadata" is a dictionary featuring the following (relevant)
        keys:
            ['accept_license', 'imagedir', 'xpakpath', 'slot', 'pkgdbpath',
             'versiontag', 'version', 'xpakstatus', 'unpackdir', 'revision',
             'category', 'repository', 'xpakdir', 'name', 'install_source',
             'removeatom'
            ]

        @param package_metadata: Entropy package metadata
        @type package_metadata: dict
        @return: execution status
        @rtype: int
        """
        raise NotImplementedError()

    def configure_installed_package(self, package_metadata):
        """
        Configure installed package. Some SPM require users to do manual
        stuff on packages.
        "package_metadata" is a dictionary featuring the following (relevant)
        keys:
            ['accept_license', 'imagedir', 'xpakpath', 'slot', 'pkgdbpath',
             'versiontag', 'version', 'xpakstatus', 'unpackdir', 'revision',
             'category', 'repository', 'xpakdir', 'name', 'install_source',
             'removeatom'
            ]

        @param package_metadata: Entropy package metadata
        @type package_metadata: dict
        @return: execution status
        @rtype: int
        """
        raise NotImplementedError()

