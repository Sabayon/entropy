# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework SystemSettings module}.

    SystemSettings is a singleton, pluggable interface which contains
    all the runtime settings (mostly parsed from configuration files
    and inherited from entropy.const -- which contains almost all the
    default values).
    SystemSettings works as a I{dict} object. Due to limitations of
    multiple inherittance when using the Singleton class, SystemSettings
    ONLY mimics a I{dict} AND it's not a subclass of it.

"""
import codecs
import errno
import os
import sys
import threading

from entropy.const import etpConst, etpSys, const_setup_perms, \
    const_secure_config_file, const_set_nice_level, const_isunicode, \
    const_convert_to_unicode, const_convert_to_rawstring, \
    const_debug_write, const_is_python3
from entropy.core import Singleton, EntropyPluginStore, BaseConfigParser
from entropy.cache import EntropyCacher
from entropy.core.settings.plugins.skel import SystemSettingsPlugin

import entropy.tools


class RepositoryConfigParser(BaseConfigParser):
    """
    Entropy .ini-like repository configuration file parser.

    This is backward compatible with the previous repository
    implementation, in the sense that old repository syntax
    is just ignored. However, a mix of old and new statements
    may result in an undefined behaviour.

    This is an example of the new syntax (with a complete listing
    of the supported arguments):

    [sabayon-limbo]
    desc = Sabayon Linux Official Testing Repository
    repo = http://pkg.sabayon.org
    repo = http://pkg.repo.sabayon.org
    pkg = http://pkg.sabayon.org
    pkg = http://dl.sabayon.org/entropy
    enabled = <true/false>

    [sabayon-limbo]
    desc = This statement will be ignored.
    repo = This url will be ignored.
    pkg = http://some.more.mirror.org/entropy
    pkg = http://some.more.mirror.net/entropy

    As you can see, multiple statements for the same repository
    are allowed. However, only the first desc = statement will be
    considered, while there can be as many pkg = and repo = as you
    want.

    Statements description:
    - "desc": stands for description, the repository name description.
    - "repo": the repository database URL string, plus other parameters
              as supported in the previous configuration file syntax:
              <db url prefix>[#<compression>].
    - "pkg": the repository packages URL string. This must be a valid URL.
             The supported protocols are those supported by entropy.fetchers.
    - "enabled": if set, its value can be either "true" or "false". The default
                 value is "true". It indicates if a repository is configured
                 but currently disabled or enabled. Please take into account
                 that config files in /etc/entropy/repositories.conf.d/ starting
                 with "_" are considered to contain disabled repositories. This
                 is just provided for convienence.
    """

    _SUPPORTED_KEYS = ("desc", "repo", "pkg", "enabled")

    _DEFAULT_ENABLED_VALUE = True

    def __init__(self, encoding = None):
        super(RepositoryConfigParser, self).__init__(encoding = encoding)

    @classmethod
    def _validate_section(cls, match):
        """
        Reimpemented from BaseConfigParser.
        """
        # a new repository begins
        groups = match.groups()
        if not groups:
            return

        candidate = groups[0]
        # Note, candidate must not start with server=
        # as this is used for Entropy Server repositories.
        if not entropy.tools.validate_repository_id(candidate):
            return
        return candidate

    def write(self, path, repository_id, desc, repos, pkgs, enabled = True):
        """
        Write the repository configuration to the given file.
        """
        if enabled:
            enabled_str = "true"
        else:
            enabled_str = "false"

        repos_str = ""
        for repo_meta in repos:
            repos_str += "repo = %(uri)s#%(dbcformat)s\n" % repo_meta

        config = """\
# Repository configuration file automatically generated
# by Entropy on your behalf.

[%(repository_id)s]
desc = %(desc)s
%(repos)s
enabled = %(enabled)s
""" % {
            "repository_id": repository_id,
            "desc": desc,
            "repos": repos_str.rstrip(),
            "enabled": enabled_str,
            }
        for pkg in pkgs:
            config += "pkg = %s\n" % (pkg,)
        config += "\n"

        entropy.tools.atomic_write(path, config, self._encoding)

    def repositories(self):
        """
        Return a list of valid parsed repositories.

        A repository is considered valid iff it contains
        at least one "repo" and "pkg" parameter.
        """
        required_keys = set(("repo", "pkg"))
        repositories = []

        for repository_id in self._ordered_sections:
            repo_data = self[repository_id]
            remaining = required_keys - set(repo_data.keys())
            if not remaining:
                # then required_keys are there
                repositories.append(repository_id)

        return repositories

    def repo(self, repository_id):
        """
        Return the list of database URLs for the given repository.
        This includes the default one, which is the first element
        listed.

        @param repository_id: the repository identifier
        @type repository_id: string
        @raise KeyError: if repository_id is not found or
            metadata is not available
        @return: the list of repository URLs
        @rtype: list
        """
        return self[repository_id]["repo"]

    def pkgs(self, repository_id):
        """
        Return the list of package URLs for the given repository.

        @param repository_id: the repository identifier
        @type repository_id: string
        @raise KeyError: if repository_id is not found or
            metadata is not available
        @return: the package URLs
        @rtype: list
        """
        return self[repository_id]["pkg"]

    def desc(self, repository_id):
        """
        Return the description of the repository.

        @param repository_id: the repository identifier
        @type repository_id: string
        @raise KeyError: if repository_id is not found or
            metadata is not available
        @return: the repository description
        @rtype: string
        """
        return self[repository_id]["desc"][0]

    def enabled(self, repository_id):
        """
        Return whether the repository is enabled or disabled.

        @param repository_id: the repository identifier
        @type repository_id: string
        @return: the repository status
        @rtype: bool
        """
        try:
            enabled = self[repository_id]["enabled"][0]
            return enabled.strip().lower() == "true"
        except KeyError:
            return self._DEFAULT_ENABLED_VALUE


class SystemSettings(Singleton, EntropyPluginStore):

    """
    This is the place where all the Entropy settings are stored if
    they are not considered instance constants (etpConst).
    For example, here we store package masking cache information and
    settings, client-side, server-side and services settings.
    Also, this class mimics a dictionary (even if not inheriting it
    due to development choices).

    Sample code:

        >>> from entropy.core.settings.base import SystemSettings
        >>> system_settings = SystemSettings()
        >>> system_settings.clear()
        >>> system_settings.destroy()

    """

    class CachingList(list):
        """
        This object overrides a list, making possible to store
        cache information in the same place of the data to be
        cached.
        """
        def __init__(self, *args, **kwargs):
            list.__init__(self, *args, **kwargs)
            self.__cache = None
            self.__lock = threading.RLock()

        def __enter__(self):
            """
            Make possible to acquire the whole cache content in
            a thread-safe way.
            """
            self.__lock.acquire()

        def __exit__(self, exc_type, exc_value, traceback):
            """
            Make possible to add plugins without triggering parse() every time.
            Reload SystemSettings on exit
            """
            self.__lock.release()

        def get(self):
            """
            Get cache object
            """
            return self.__cache

        def set(self, cache_obj):
            """
            Set cache object
            """
            self.__cache = cache_obj

    # If set to True, enable in-RAM cache usage if
    # configuration files have the same mtime of
    # the last time they were read, during the same
    # process lifecycle. Any race condition between
    # reading the mtime and actually reading the file
    # content can be trascurable as long as the cache
    # data is stored in ram and not on-disk.
    DISK_DATA_CACHE = True

    def init_singleton(self):

        """
        Replaces __init__ because SystemSettings is a Singleton.
        see Singleton API reference for more information.

        """
        EntropyPluginStore.__init__(self)

        from entropy.core.settings.plugins.factory import get_available_plugins
        self.__get_external_plugins = get_available_plugins

        from threading import RLock
        self.__lock = RLock()
        self.__cacher = EntropyCacher()
        self.__data = {}
        self.__is_destroyed = False
        self.__cache_cleared = False
        self.__inside_with_stmt = 0
        self.__pkg_comment_tag = "##"

        self.__external_plugins = {}
        self.__setting_files_order = []
        self.__setting_files_pre_run = []
        self.__setting_files = {}
        self.__setting_dirs = {}
        self.__mtime_files = {}
        self.__mtime_cache = {}
        self.__persistent_settings = {
            'pkg_masking_reasons': etpConst['pkg_masking_reasons'].copy(),
            'pkg_masking_reference': etpConst['pkg_masking_reference'].copy(),
            'backed_up': {},
            # package masking, live
            'live_packagemasking': {
                'unmask_matches': set(),
                'mask_matches': set(),
            },
        }

        self.__setup_const()
        self.__scan()

    def __enter__(self):
        """
        Make possible to add plugins without triggering parse() every time.
        """
        self.__inside_with_stmt += 1

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Make possible to add plugins without triggering parse() every time.
        Reload SystemSettings on exit
        """
        self.__inside_with_stmt -= 1
        if self.__inside_with_stmt == 0:
            self.clear()

    def destroy(self):
        """
        Overloaded method from Singleton.
        "Destroys" the instance.

        @return: None
        @rtype: None
        """
        self.__is_destroyed = True

    def add_plugin(self, system_settings_plugin_instance):
        """
        This method lets you add custom parsers to SystemSettings.
        Mind that you are responsible of handling your plugin instance
        and remove it before it is destroyed. You can remove the plugin
        instance at any time by issuing remove_plugin.
        Every add_plugin or remove_plugin method will also issue clear()
        for you. This could be bad and it might be removed in future.

        @param system_settings_plugin_instance: valid SystemSettingsPlugin
            instance
        @type system_settings_plugin_instance: SystemSettingsPlugin instance
        @return: None
        @rtype: None
        """
        inst = system_settings_plugin_instance
        if not isinstance(inst, SystemSettingsPlugin):
            raise AttributeError("SystemSettings: expected valid " + \
                    "SystemSettingsPlugin instance")
        EntropyPluginStore.add_plugin(self, inst.get_id(), inst)
        if self.__inside_with_stmt == 0:
            self.clear()

    def remove_plugin(self, plugin_id):
        """
        This method lets you remove previously added custom parsers from
        SystemSettings through its plugin identifier. If plugin_id is not
        available, KeyError exception will be raised.
        Every add_plugin or remove_plugin method will also issue clear()
        for you. This could be bad and it might be removed in future.

        @param plugin_id: plugin identifier
        @type plugin_id: basestring
        @return: None
        @rtype: None
        """
        EntropyPluginStore.remove_plugin(self, plugin_id)
        self.clear()

    def get_updatable_configuration_files(self, repository_id):
        """
        Poll SystemSettings plugins and get a list of updatable configuration
        files. For "updatable" it is meant, configuration files that expose
        package matches (not just keys) at the beginning of new lines.
        This makes possible to implement automatic configuration files updates
        upon package name renames.

        @param repository_id: repository identifier, if needed to return
            a list of specific configuration files
        @type repository_id: string or None
        @return: list (set) of package files paths (must check for path avail)
        @rtype: set
        """
        own_list = set([
            self.__setting_files['keywords'],
            self.__setting_files['mask'],
            self.__setting_files['unmask'],
            self.__setting_files['system_mask'],
            self.__setting_files['splitdebug'],
        ])
        for setting_id, setting_data in self.__setting_dirs.items():
            conf_dir, dir_sett, skipped_sett, auto_update = setting_data
            if not auto_update:
                continue
            for conf_file, mtime_conf_file in dir_sett:
                own_list.add(conf_file)

        # poll plugins
        for plugin in self.get_plugins().values():
            files = plugin.get_updatable_configuration_files(repository_id)
            if files:
                own_list.update(files)

        for plugin in self.__external_plugins.values():
            files = plugin.get_updatable_configuration_files(repository_id)
            if files:
                own_list.update(files)

        return own_list

    @staticmethod
    def packages_config_directory():
        """
        Return the actual {ROOT}etc/entropy/packages path.

        @return: path
        @type: string
        """
        return os.path.join(etpConst['confdir'], "packages")

    @staticmethod
    def packages_sets_directory():
        """
        Return the actual {ROOT}etc/entropy/packages/sets path.

        @return: path
        @type: string
        """
        return os.path.join(
            SystemSettings.packages_config_directory(),
            etpConst['confsetsdirname'])

    def __setup_const(self):

        """
        Internal method. Does constants initialization.

        @return: None
        @rtype: None
        """

        del self.__setting_files_order[:]
        del self.__setting_files_pre_run[:]
        self.__setting_files.clear()
        self.__setting_dirs.clear()
        self.__mtime_files.clear()
        if not SystemSettings.DISK_DATA_CACHE:
            self.__mtime_cache.clear()
        self.__cache_cleared = False

        packages_dir = SystemSettings.packages_config_directory()
        self.__setting_files.update({
             # keywording configuration files
            'keywords': os.path.join(
                    packages_dir, "package.keywords"),
             # unmasking configuration files
            'unmask': os.path.join(
                    packages_dir, "package.unmask"),
             # masking configuration files
            'mask': os.path.join(packages_dir, "package.mask"),
            # selectively enable splitdebug for packages
            'splitdebug': os.path.join(
                    packages_dir, "package.splitdebug"),
            'splitdebug_mask': os.path.join(
                    packages_dir, "package.splitdebug.mask"),
             # masking configuration files
            'license_mask': os.path.join(
                    packages_dir, "license.mask"),
            'license_accept': os.path.join(
                    packages_dir, "license.accept"),
            'system_mask': os.path.join(
                    packages_dir, "system.mask"),
            'system_dirs': os.path.join(
                    etpConst['confdir'], "fsdirs.conf"),
            'system_dirs_mask': os.path.join(
                    etpConst['confdir'], "fsdirsmask.conf"),
            'extra_ldpaths': os.path.join(
                    etpConst['confdir'], "fsldpaths.conf"),
            'system_rev_symlinks': os.path.join(
                    etpConst['confdir'], "fssymlinks.conf"),
            'broken_syms': os.path.join(etpConst['confdir'], "brokensyms.conf"),
            'broken_libs_mask': os.path.join(
                    etpConst['confdir'], "brokenlibsmask.conf"),
            'broken_links_mask': os.path.join(
                    etpConst['confdir'], "brokenlinksmask.conf"),
            'hw_hash': os.path.join(etpConst['confdir'], ".hw.hash"),
            'system': os.path.join(etpConst['confdir'], "entropy.conf"),
            'repositories': os.path.join(
                    etpConst['confdir'], "repositories.conf"),
            'system_package_sets': {},
        })
        self.__setting_files_order.extend([
            'keywords', 'unmask', 'mask', 'license_mask',
            'license_accept', 'system_mask', 'system_package_sets',
            'system_dirs', 'system_dirs_mask', 'extra_ldpaths',
            'splitdebug', 'splitdebug_mask', 'system',
            'system_rev_symlinks', 'hw_hash', 'broken_syms',
            'broken_libs_mask', 'broken_links_mask'
        ])
        self.__setting_files_pre_run.extend(['repositories'])

        dmp_dir = etpConst['dumpstoragedir']
        self.__mtime_files.update({
            'keywords_mtime': os.path.join(dmp_dir, "keywords.mtime"),
            'unmask_mtime': os.path.join(dmp_dir, "unmask.mtime"),
            'mask_mtime': os.path.join(dmp_dir, "mask.mtime"),
            'license_mask_mtime': os.path.join(dmp_dir,
                                               "license_mask.mtime"),
            'license_accept_mtime': os.path.join(dmp_dir,
                                                 "license_accept.mtime"),
            'system_mask_mtime': os.path.join(dmp_dir,
                                              "system_mask.mtime"),
        })

        conf_d_descriptors = [
            ("mask_d", "package.mask.d",
                 packages_dir, True, True),
            ("unmask_d", "package.unmask.d",
                 packages_dir, True, True),
            ("license_mask_d", "license.mask.d",
                 packages_dir, False, True),
            ("license_accept_d", "license.accept.d",
                 packages_dir, False, True),
            ("system_mask_d", "system.mask.d",
                 packages_dir, True, True),
            # this will be parsed from inside _repositories_parser
            ("repositories_conf_d", "repositories.conf.d",
                 etpConst['confdir'], False, False),
        ]
        for setting_id, rel_dir, base_dir, auto_update, add_parser \
                in conf_d_descriptors:
            conf_dir = base_dir + os.path.sep + rel_dir
            self.__setting_dirs[setting_id] = [conf_dir, [], [], auto_update]
            if not (os.path.isdir(conf_dir) and \
                        os.access(conf_dir, os.R_OK)):
                continue

            conf_files = []
            try:
                conf_files += [os.path.join(conf_dir, x) for x in \
                                      os.listdir(conf_dir)]
            except (OSError, IOError):
                continue
            conf_files = [x for x in conf_files if \
                os.path.isfile(x) and os.access(x, os.R_OK) \
                and not os.path.basename(x).startswith(".keep") \
                and os.path.basename(x) != "README" \
                and not os.path.basename(x).endswith(".example")]
            # ignore files starting with _
            skipped_conf_files = [x for x in conf_files if \
                os.path.basename(x).startswith("_")]
            conf_files = [x for x in conf_files if not \
                              os.path.basename(x).startswith("_")]

            mtime_base_file = os.path.join(dmp_dir, rel_dir + "_")
            skipped_conf_files = [
                (x, mtime_base_file + os.path.basename(x) + ".mtime") for \
                    x in skipped_conf_files]
            conf_files = [
                (x, mtime_base_file + os.path.basename(x) + ".mtime") for \
                    x in conf_files]

            self.__setting_dirs[setting_id][1] += conf_files
            self.__setting_dirs[setting_id][2] += skipped_conf_files
            if add_parser:
                # this will make us call _<setting_id>_parser()
                # and that must return None, becase the outcome
                # has to be written into '<setting_id/_d>' metadata object
                # thus, these have to always run AFTER their alter-egos
                self.__setting_files_order.append(setting_id)

    def __scan(self):

        """
        Internal method. Scan settings and fill variables.

        @return: None
        @rtype: None
        """

        def enforce_persistent():
            # merge persistent settings back
            self.__data.update(self.__persistent_settings)
            # restore backed-up settings
            self.__data.update(self.__persistent_settings['backed_up'].copy())

        self.__parse()
        enforce_persistent()

        # plugins support
        local_plugins = self.get_plugins()
        for plugin_id in sorted(local_plugins):
            local_plugins[plugin_id].parse(self)

        # external plugins support
        external_plugins = self.__get_external_plugins()
        for external_plugin_id in sorted(external_plugins):
            external_plugin = external_plugins[external_plugin_id]()
            external_plugin.parse(self)
            self.__external_plugins[external_plugin_id] = external_plugin

        enforce_persistent()

        # run post-SystemSettings setup, plugins hook
        for plugin_id in sorted(local_plugins):
            local_plugins[plugin_id].post_setup(self)

        # run post-SystemSettings setup for external plugins too
        for external_plugin_id in sorted(self.__external_plugins):
            self.__external_plugins[external_plugin_id].post_setup(self)

    def __setitem__(self, mykey, myvalue):
        """
        dict method. See Python dict API reference.
        """
        # backup here too
        if mykey in self.__persistent_settings:
            self.__persistent_settings[mykey] = myvalue
        self.__data[mykey] = myvalue

    def __getitem__(self, mykey):
        """
        dict method. See Python dict API reference.
        """
        with self.__lock:
            return self.__data[mykey]

    def __delitem__(self, mykey):
        """
        dict method. See Python dict API reference.
        """
        with self.__lock:
            del self.__data[mykey]

    def __iter__(self):
        """
        dict method. See Python dict API reference.
        """
        return iter(self.__data)

    def __contains__(self, item):
        """
        dict method. See Python dict API reference.
        """
        return item in self.__data

    def __hash__(self):
        """
        dict method. See Python dict API reference.
        """
        return hash(self.__data)

    def __len__(self):
        """
        dict method. See Python dict API reference.
        """
        return len(self.__data)

    def get(self, *args, **kwargs):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.get(*args, **kwargs)

    def copy(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.copy()

    def fromkeys(self, *args, **kwargs):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.fromkeys(*args, **kwargs)

    def items(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.items()

    def iteritems(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.iteritems()

    def iterkeys(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.iterkeys()

    def keys(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.keys()

    def pop(self, *args, **kwargs):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.pop(*args, **kwargs)

    def popitem(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.popitem()

    def setdefault(self, *args, **kwargs):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.setdefault(*args, **kwargs)

    def update(self, kwargs):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.update(kwargs)

    def values(self):
        """
        dict method. See Python dict API reference.
        """
        return self.__data.values()

    def clear(self):
        """
        dict method. See Python dict API reference.
        Settings are also re-initialized here.

        @return None
        """
        with self.__lock:
            self.__data.clear()
            self.__setup_const()
            self.__scan()

    def set_persistent_setting(self, persistent_dict):
        """
        Make metadata persistent, the input dict will be merged
        with the base one at every reset call (clear()).

        @param persistent_dict: dictionary to merge
        @type persistent_dict: dict

        @return: None
        @rtype: None
        """
        self.__persistent_settings.update(persistent_dict)

    def unset_persistent_setting(self, persistent_key):
        """
        Remove dict key from persistent dictionary

        @param persistent_key: key to remove
        @type persistent_dict: dict

        @return: None
        @rtype: None
        """
        del self.__persistent_settings[persistent_key]
        del self.__data[persistent_key]

    def __setup_package_sets_vars(self):

        """
        This function setups the *files* dictionary about package sets
        that will be read and parsed afterwards by the respective
        internal parser.

        @return: None
        @rtype: None
        """

        # user defined package sets
        sets_dir = SystemSettings.packages_sets_directory()
        pkg_set_data = {}
        if (os.path.isdir(sets_dir) and os.access(sets_dir, os.R_OK)):
            set_files = [x for x in os.listdir(sets_dir) if \
                (os.path.isfile(os.path.join(sets_dir, x)) and \
                os.access(os.path.join(sets_dir, x), os.R_OK))]
            for set_file in set_files:
                try:
                    set_file = const_convert_to_unicode(
                        set_file, etpConst['conf_encoding'])
                except UnicodeDecodeError:
                    set_file = const_convert_to_unicode(set_file,
                        sys.getfilesystemencoding())

                path = os.path.join(sets_dir, set_file)
                if not const_is_python3():
                    path = const_convert_to_rawstring(
                        path, etpConst['conf_encoding'])
                pkg_set_data[set_file] = path

        self.__setting_files['system_package_sets'].update(pkg_set_data)

    def __parse(self):
        """
        This is the main internal parsing method.
        *files* and *mtimes* dictionaries are prepared and
        parsed just a few lines later.

        @return: None
        @rtype: None
        """
        # some parsers must be run BEFORE everything:
        for item in self.__setting_files_pre_run:
            myattr = '_%s_parser' % (item,)
            if not hasattr(self, myattr):
                continue
            func = getattr(self, myattr)
            self.__data[item] = func()

        # parse main settings
        self.__setup_package_sets_vars()

        for item in self.__setting_files_order:
            myattr = '_%s_parser' % (item,)
            if not hasattr(self, myattr):
                continue
            func = getattr(self, myattr)
            self.__data[item] = func()

    def get_setting_files_data(self):
        """
        Return a copy of the internal *files* dictionary.
        This dict contains config file paths and their identifiers.

        @return: dict __setting_files
        @rtype: dict
        """
        return self.__setting_files.copy()

    def get_setting_dirs_data(self):
        """
        Return a copy of the internal *dirs* dictionary.
        This dict contains *.d config dirs enclosing respective
        config files.

        @return: dict __setting_dirs
        @rtype: dict
        """
        return self.__setting_dirs.copy()

    def _keywords_parser(self):
        """
        Parser returning package keyword masking metadata
        read from package.keywords file.
        This file contains package mask or unmask directives
        based on package keywords.

        @return: parsed metadata
        @rtype: dict
        """
        keywords_conf = self.__setting_files['keywords']
        root = etpConst['systemroot']
        try:
            mtime = os.path.getmtime(keywords_conf)
        except (OSError, IOError):
            mtime = 0.0

        cache_key = (root, keywords_conf)
        cache_obj = self.__mtime_cache.get(cache_key)
        if cache_obj is not None:
            if cache_obj['mtime'] == mtime:
                return cache_obj['data']

        cache_obj = {'mtime': mtime,}

        # merge universal keywords
        data = {
                'universal': set(),
                'packages': {},
                'repositories': {},
        }

        self.validate_entropy_cache(keywords_conf,
            self.__mtime_files['keywords_mtime'])
        content = [x.split() for x in \
            self.__generic_parser(keywords_conf,
                comment_tag = self.__pkg_comment_tag) \
                if len(x.split()) < 4]
        for keywordinfo in content:
            # skip wrong lines
            if len(keywordinfo) > 3:
                continue
            # inversal keywording, check if it's not repo=
            if len(keywordinfo) == 1:
                if keywordinfo[0].startswith("repo="):
                    continue
                # convert into entropy format
                if keywordinfo[0] == "**":
                    keywordinfo[0] = ""
                data['universal'].add(keywordinfo[0])
                continue
            # inversal keywording, check if it's not repo=
            if len(keywordinfo) in (2, 3,):
                # repo=?
                if keywordinfo[0].startswith("repo="):
                    continue
                # add to repo?
                items = keywordinfo[1:]
                # convert into entropy format
                if keywordinfo[0] == "**":
                    keywordinfo[0] = ""
                reponame = [x for x in items if x.startswith("repo=") \
                    and (len(x.split("=")) == 2)]
                if reponame:
                    reponame = reponame[0].split("=")[1]
                    if reponame not in data['repositories']:
                        data['repositories'][reponame] = {}
                    # repository unmask or package in repository unmask?
                    if keywordinfo[0] not in data['repositories'][reponame]:
                        data['repositories'][reponame][keywordinfo[0]] = set()
                    if len(items) == 1:
                        # repository unmask
                        data['repositories'][reponame][keywordinfo[0]].add('*')
                    elif "*" not in \
                        data['repositories'][reponame][keywordinfo[0]]:

                        item = [x for x in items if not x.startswith("repo=")]
                        data['repositories'][reponame][keywordinfo[0]].add(
                            item[0])
                elif len(items) == 2:
                    # it's going to be a faulty line!!??
                    # can't have two items and no repo=
                    continue
                else:
                    # add keyword to packages
                    if keywordinfo[0] not in data['packages']:
                        data['packages'][keywordinfo[0]] = set()
                    data['packages'][keywordinfo[0]].add(items[0])

        # merge universal keywords
        etpConst['keywords'].clear()
        etpConst['keywords'].update(etpSys['keywords'])
        for keyword in data['universal']:
            etpConst['keywords'].add(keyword)

        cache_obj['data'] = data
        self.__mtime_cache[cache_key] = cache_obj
        return data


    def _unmask_parser(self):
        """
        Parser returning package unmasking metadata read from
        package.unmask file.
        This file contains package unmask directives, allowing
        to enable experimental or *secret* packages.

        @return: parsed metadata
        @rtype: dict
        """
        valid = self.validate_entropy_cache(self.__setting_files['unmask'],
            self.__mtime_files['unmask_mtime'])
        if (not valid) and (not self.__cache_cleared):
            # all the cache must be cleared (including upgrade and
            # repository match cache
            self.__cache_cleared = True
            EntropyCacher.clear_cache()
        return self.__generic_parser(self.__setting_files['unmask'],
            comment_tag = self.__pkg_comment_tag)

    def _mask_parser(self):
        """
        Parser returning package masking metadata read from
        package.mask file.
        This file contains package mask directives, allowing
        to disable experimental or *secret* packages.

        @return: parsed metadata
        @rtype: dict
        """
        valid = self.validate_entropy_cache(self.__setting_files['mask'],
            self.__mtime_files['mask_mtime'])
        if (not valid) and (not self.__cache_cleared):
            # all the cache must be cleared (including upgrade and
            # repository match cache
            self.__cache_cleared = True
            EntropyCacher.clear_cache()
        return self.__generic_parser(self.__setting_files['mask'],
            comment_tag = self.__pkg_comment_tag)

    def _mask_d_parser(self):
        """
        Parser returning package masking metadata read from
        packages/package.mask.d/* files (alpha sorting).
        It writes directly to __data['mask'] in append.
        """
        return self.__generic_d_parser("mask_d", "mask")

    def _unmask_d_parser(self):
        """
        Parser returning package masking metadata read from
        packages/package.unmask.d/* files (alpha sorting).
        It writes directly to __data['unmask'] in append.
        """
        return self.__generic_d_parser("unmask_d", "unmask")

    def _license_mask_d_parser(self):
        """
        Parser returning package masking metadata read from
        packages/license.mask.d/* files (alpha sorting).
        It writes directly to __data['license_mask'] in append.
        """
        return self.__generic_d_parser("license_mask_d", "license_mask")

    def _system_mask_d_parser(self):
        """
        Parser returning package masking metadata read from
        packages/system.mask.d/* files (alpha sorting).
        It writes directly to __data['system_mask'] in append.
        """
        return self.__generic_d_parser("system_mask_d", "system_mask")

    def _license_accept_d_parser(self):
        """
        Parser returning package masking metadata read from
        packages/license.accept.d/* files (alpha sorting).
        It writes directly to __data['license_accept'] in append.
        """
        return self.__generic_d_parser("license_accept_d", "license_accept")

    def __generic_d_parser(self, setting_dirs_id, setting_id,
                           validate = True, parse_skipped = False):
        """
        Generic parser used by _*_d_parser() functions.
        """
        conf_dir, setting_files, skipped_files, auto_upd = \
            self.__setting_dirs[setting_dirs_id]
        dmp_dir = etpConst['dumpstoragedir']
        dmp_mtime_dir_file = os.path.join(
            dmp_dir, os.path.basename(conf_dir) + ".mtime")

        if validate:
            valid = self.validate_entropy_cache(
                conf_dir, dmp_mtime_dir_file)
            if (not valid) and (not self.__cache_cleared):
                self.__cache_cleared = True
                EntropyCacher.clear_cache()

        content = []
        files = setting_files
        if parse_skipped:
            files = skipped_files
        for sett_file, mtime_sett_file in files:
            if validate:
                valid = self.validate_entropy_cache(
                    sett_file, mtime_sett_file)
                if (not valid) and (not self.__cache_cleared):
                    self.__cache_cleared = True
                    EntropyCacher.clear_cache()
            content += self.__generic_parser(sett_file,
                comment_tag = self.__pkg_comment_tag)
        if setting_id is not None:
            # Always push out CachingList objects if
            # metadata is not available in self.__data
            # It doesn't harm to have it like this since
            # CachingList is just a list().
            # Moreover, DO keep the same object and use
            # extend rather than throwing it away.
            self.__data.get(
                setting_id,
                SystemSettings.CachingList([])).extend(content)
        else:
            return content

    def _system_mask_parser(self):
        """
        Parser returning system packages mask metadata read from
        package.system_mask file.
        This file contains packages that should be always kept
        installed, extending the already defined (in repository database)
        set of atoms.

        @return: parsed metadata
        @rtype: dict
        """
        valid = self.validate_entropy_cache(self.__setting_files['system_mask'],
            self.__mtime_files['system_mask_mtime'])
        if (not valid) and (not self.__cache_cleared):
            # all the cache must be cleared (including upgrade and
            # repository match cache
            self.__cache_cleared = True
            EntropyCacher.clear_cache()
        return self.__generic_parser(self.__setting_files['system_mask'],
            comment_tag = self.__pkg_comment_tag)

    def _splitdebug_parser(self):
        """
        Parser returning packages for which the splitdebug feature
        should be enabled. Splitdebug is about installing /usr/lib/debug
        files into the system. If no entries are listed in here and
        splitdebug is enabled in client.conf, the feature will be considered
        enabled for any package.

        @return: parsed metadata
        @rtype: dict
        """
        return self.__generic_parser(self.__setting_files['splitdebug'],
            comment_tag = self.__pkg_comment_tag)

    def _splitdebug_mask_parser(self):
        """
        Parser returning packages for which the splitdebug feature
        should be always disabled. This takes the precedence over
        package.splitdebug.
        Splitdebug is about installing /usr/lib/debug files into the system.
        If no entries are listed in here and splitdebug is enabled in
        client.conf, the feature will be considered enabled for any package.

        @return: parsed metadata
        @rtype: dict
        """
        return self.__generic_parser(self.__setting_files['splitdebug_mask'],
            comment_tag = self.__pkg_comment_tag)

    def _license_mask_parser(self):
        """
        Parser returning packages masked by license metadata read from
        license.mask file.
        Packages shipped with licenses listed there will be masked.

        @return: parsed metadata
        @rtype: dict
        """
        valid = self.validate_entropy_cache(
            self.__setting_files['license_mask'],
                self.__mtime_files['license_mask_mtime'])
        if (not valid) and (not self.__cache_cleared):
            # all the cache must be cleared (including upgrade and
            # repository match cache
            self.__cache_cleared = True
            EntropyCacher.clear_cache()
        return self.__generic_parser(self.__setting_files['license_mask'])

    def _license_accept_parser(self):
        """
        Parser returning packages unmasked by license metadata read from
        license.mask file.
        Packages shipped with licenses listed there will be unmasked.

        @return: parsed metadata
        @rtype: dict
        """
        valid = self.validate_entropy_cache(
            self.__setting_files['license_accept'],
            self.__mtime_files['license_accept_mtime'])
        if (not valid) and (not self.__cache_cleared):
            # all the cache must be cleared (including upgrade and
            # repository match cache
            self.__cache_cleared = True
            EntropyCacher.clear_cache()
        return self.__generic_parser(self.__setting_files['license_accept'])

    def _extract_packages_from_set_file(self, filepath):
        """
        docstring_title

        @param filepath: 
        @type filepath: 
        @return: 
        @rtype: 
        """
        enc = etpConst['conf_encoding']
        f = None
        try:
            f = codecs.open(filepath, "r", encoding=enc)
            items = set()
            line = f.readline()
            while line:
                x = line.strip().rsplit("#", 1)[0]
                if x and (not x.startswith('#')):
                    items.add(x)
                line = f.readline()
        finally:
            if f is not None:
                f.close()
        return items

    def _system_package_sets_parser(self):
        """
        Parser returning system defined package sets read from
        /etc/entropy/packages/sets.

        @return: parsed metadata
        @rtype: dict
        """
        data = {}
        for set_name in self.__setting_files['system_package_sets']:
            set_filepath = self.__setting_files['system_package_sets'][set_name]
            set_elements = self._extract_packages_from_set_file(set_filepath)
            if set_elements:
                data[set_name] = set_elements.copy()
        return data

    def _extra_ldpaths_parser(self):
        """
        Parser returning directories considered part of the base system.

        @return: parsed metadata
        @rtype: dict
        """
        return self.__generic_parser(self.__setting_files['extra_ldpaths'])

    def _system_dirs_parser(self):
        """
        Parser returning directories considered part of the base system.

        @return: parsed metadata
        @rtype: dict
        """
        return self.__generic_parser(self.__setting_files['system_dirs'])

    def _system_dirs_mask_parser(self):
        """
        Parser returning directories NOT considered part of the base system.
        Settings here overlay system_dirs_parser.

        @return: parsed metadata
        @rtype: dict
        """
        return self.__generic_parser(self.__setting_files['system_dirs_mask'])

    def _broken_syms_parser(self):
        """
        Parser returning a list of shared objects symbols that can be used by
        QA tools to scan the filesystem or a subset of it.

        @return: parsed metadata
        @rtype: dict
        """
        return self.__generic_parser(self.__setting_files['broken_syms'])

    def _broken_libs_mask_parser(self):
        """
        Parser returning a list of broken shared libraries which are
        always considered sane.

        @return: parsed metadata
        @rtype: dict
        """
        return self.__generic_parser(self.__setting_files['broken_libs_mask'])

    def _broken_links_mask_parser(self):
        """
        Parser returning a list of broken library linking libraries which are
        always considered sane.

        @return: parsed metadata
        @rtype: dict
        """
        return self.__generic_parser(self.__setting_files['broken_links_mask'])

    def _hw_hash_parser(self):
        """
        Hardware hash metadata parser and generator. It returns a theorically
        unique SHA256 hash bound to the computer running this Framework.

        @return: string containing SHA256 hexdigest
        @rtype: string
        """
        hw_hash_file = self.__setting_files['hw_hash']
        root = etpConst['systemroot']
        try:
            mtime = os.path.getmtime(hw_hash_file)
        except (OSError, IOError):
            mtime = 0.0

        cache_key = (root, hw_hash_file)
        cache_obj = self.__mtime_cache.get(cache_key)
        if cache_obj is not None:
            if cache_obj['mtime'] == mtime:
                return cache_obj['data']

        cache_obj = {'mtime': mtime,}

        enc = etpConst['conf_encoding']
        try:
            with codecs.open(hw_hash_file, "r", encoding=enc) as hash_f:
                hash_data = hash_f.readline().strip()
            cache_obj['data'] = hash_data
            self.__mtime_cache[cache_key] = cache_obj
            return hash_data
        except IOError as err:
            if err.errno not in (errno.ENOENT, errno.EPERM):
                raise

        hash_file_dir = os.path.dirname(hw_hash_file)
        hw_hash_exec = etpConst['etp_hw_hash_gen']
        if os.access(hash_file_dir, os.W_OK) and \
            os.access(hw_hash_exec, os.X_OK | os.R_OK) and \
            os.path.isfile(hw_hash_exec):

            pipe = os.popen('{ ' + hw_hash_exec + '; } 2>&1', 'r')
            hash_data = pipe.read().strip()
            sts = pipe.close()
            if sts is not None:
                cache_obj['data'] = None
                self.__mtime_cache[cache_key] = cache_obj
                return None

            with codecs.open(hw_hash_file, "w", encoding=enc) as hash_f:
                hash_f.write(hash_data)
                hash_f.flush()
            cache_obj['data'] = hash_data
            self.__mtime_cache[cache_key] = cache_obj
            return hash_data

    def _system_rev_symlinks_parser(self):
        """
        Parser returning important system symlinks mapping. For example:
            {'/usr/lib': ['/usr/lib64']}
        Useful for reverse matching files belonging to packages.

        @return: dict containing the mapping
        @rtype: dict
        """
        setting_file = self.__setting_files['system_rev_symlinks']
        raw_data = self.__generic_parser(setting_file)
        data = {}
        for line in raw_data:
            line = line.split()
            if len(line) < 2:
                continue
            data[line[0]] = frozenset(line[1:])
        return data

    def _system_parser(self):

        """
        Parses Entropy system configuration file.

        @return: parsed metadata
        @rtype: dict
        """
        etp_conf = self.__setting_files['system']
        root = etpConst['systemroot']
        try:
            mtime = os.path.getmtime(etp_conf)
        except (OSError, IOError):
            mtime = 0.0

        cache_key = (root, etp_conf)
        cache_obj = self.__mtime_cache.get(cache_key)
        if cache_obj is not None:
            if cache_obj['mtime'] == mtime:
                return cache_obj['data']

        cache_obj = {'mtime': mtime,}

        data = {
            'proxy': etpConst['proxy'].copy(),
            'name': etpConst['systemname'],
            'log_level': etpConst['entropyloglevel'],
            'spm_backend': None,
        }

        if not (os.path.isfile(etp_conf) and \
            os.access(etp_conf, os.R_OK)):
            cache_obj['data'] = data
            self.__mtime_cache[cache_key] = cache_obj
            return data

        const_secure_config_file(etp_conf)
        enc = etpConst['conf_encoding']
        with codecs.open(etp_conf, "r", encoding=enc) as entropy_f:
            entropyconf = [x.strip() for x in entropy_f.readlines()  if \
                               x.strip() and not x.strip().startswith("#")]

        def _loglevel(setting):
            try:
                loglevel = int(setting)
            except ValueError:
                return
            if (loglevel > -1) and (loglevel < 3):
                data['log_level'] = loglevel

        def _ftp_proxy(setting):
            ftpproxy = setting.strip().split()
            if ftpproxy:
                data['proxy']['ftp'] = ftpproxy[-1]

        def _http_proxy(setting):
            httpproxy = setting.strip().split()
            if httpproxy:
                data['proxy']['http'] = httpproxy[-1]

        def _rsync_proxy(setting):
            rsyncproxy = setting.strip().split()
            if rsyncproxy:
                data['proxy']['rsync'] = rsyncproxy[-1]

        def _proxy_username(setting):
            username = setting.strip().split()
            if username:
                data['proxy']['username'] = username[-1]

        def _proxy_password(setting):
            password = setting.strip().split()
            if password:
                data['proxy']['password'] = password[-1]

        def _name(setting):
            data['name'] = setting.strip()

        def _spm_backend(setting):
            data['spm_backend'] = setting.strip()

        def _nice_level(setting):
            mylevel = setting.strip()
            try:
                mylevel = int(mylevel)
                if (mylevel >= -19) and (mylevel <= 19):
                    const_set_nice_level(mylevel)
            except (ValueError,):
                return

        settings_map = {
            'loglevel': _loglevel,
            'ftp-proxy': _ftp_proxy,
            'http-proxy': _http_proxy,
            'rsync-proxy': _rsync_proxy,
            'proxy-username': _proxy_username,
            'proxy-password': _proxy_password,
            'system-name': _name,
            'spm-backend': _spm_backend,
            'nice-level': _nice_level,
        }

        for line in entropyconf:

            key, value = entropy.tools.extract_setting(line)
            if key is None:
                continue

            func = settings_map.get(key)
            if func is None:
                continue
            func(value)

        cache_obj['data'] = data
        self.__mtime_cache[cache_key] = cache_obj
        return data

    def _analyze_client_repo_string(self, repostring, branch = None,
        product = None, _skip_repository_validation = False):
        """
        Extract repository information from the provided repository string,
        usually contained in the repository settings file, repositories.conf.

        @param repostring: valid repository identifier
        @type repostring: string
        @rtype: tuple (string, dict)
        @return: tuple composed by (repository identifier, extracted repository
            metadata)
        @raise AttributeError: when repostring passed is invalid.
        """
        if branch is None:
            branch = etpConst['branch']
        if product is None:
            product = etpConst['product']

        repo_key, repostring = entropy.tools.extract_setting(repostring)
        if repo_key != "repository":
            raise AttributeError("repostring must start with 'repository|'")

        repo_split = repostring.split("|")
        if len(repo_split) < 4:
            raise AttributeError("repostring must have at least 5 pipe separated parts")

        name = repo_split[0].strip()
        if not _skip_repository_validation:
            # validate repository id string
            if not entropy.tools.validate_repository_id(name):
                raise AttributeError("invalid repository identifier")

        desc = repo_split[1].strip()
        # protocol filter takes place inside entropy.fetchers
        packages = [x.strip() for x in repo_split[2].strip().split() \
                        if x.strip()]
        database = repo_split[3].strip()
        return name, self._generate_repository_metadata(
            name, desc, packages, [database], product, branch)

    def _generate_repository_metadata(self, name, desc, packages, databases,
                                      product, branch):
        """
        Given a set of raw repository metadata information, like name,
        description, a list of package urls and the database url, generate
        the appropriate metadata.
        """
        def _extract(database):
            # Support for custom database file compression
            dbformat = None
            for testno in range(2):
                dbformatcolon = database.rfind("#")
                if dbformatcolon == -1:
                    break

                try:
                    dbformat = database[dbformatcolon+1:]
                except (IndexError, ValueError, TypeError,):
                    pass
                database = database[:dbformatcolon]

            if dbformat not in etpConst['etpdatabasesupportedcformats']:
                # fallback to default
                dbformat = etpConst['etpdatabasefileformat']

            # strip off, if exists, the deprecated service_uri part (EAPI3 shit)
            uricol = database.rfind(",")
            if uricol != -1:
                database = database[:uricol]

            return database, dbformat

        data = {}
        data['repoid'] = name

        databases = [_extract(x) for x in databases]
        databases = [(x, y) for x, y in databases if \
                         entropy.tools.is_valid_uri(x)]
        if not databases:
            raise AttributeError("no valid repository database URLs")

        data['databases'] = []
        data['plain_databases'] = []
        for index, (database, dbformat) in enumerate(databases):

            database_expanded = entropy.tools.expand_plain_database_mirror(
                database, product, name, branch)
            if database_expanded is None:
                database_expanded = const_convert_to_unicode("")


            # XXX: backward compatibility support, consider the first
            # databases entry as "database".
            if index == 0:
                data['dbcformat'] = dbformat
                data['plain_database'] = database
                data['database'] = database_expanded

            data['databases'].append({
                    'uri': database_expanded,
                    'dbcformat': dbformat,
                    })
            data['plain_databases'].append({
                    'uri': database,
                    'dbcformat': dbformat,
                    })

        data['description'] = desc
        data['packages'] = []
        data['plain_packages'] = []

        data['dbpath'] = etpConst['etpdatabaseclientdir'] + os.path.sep + \
            name + os.path.sep + product + os.path.sep + \
            etpConst['currentarch'] + os.path.sep + branch

        data['notice_board'] = data['database'] + os.path.sep + \
            etpConst['rss-notice-board']

        data['local_notice_board'] = data['dbpath'] + os.path.sep + \
            etpConst['rss-notice-board']

        data['local_notice_board_userdata'] = data['dbpath'] + \
            os.path.sep + etpConst['rss-notice-board-userdata']

        data['dbrevision'] = "0"
        dbrevision_file = os.path.join(data['dbpath'],
            etpConst['etpdatabaserevisionfile'])
        if os.path.isfile(dbrevision_file) and \
            os.access(dbrevision_file, os.R_OK):
            enc = etpConst['conf_encoding']
            with codecs.open(dbrevision_file, "r", encoding=enc) as dbrev_f:
                data['dbrevision'] = dbrev_f.readline().strip()

        # setup GPG key path
        data['gpg_pubkey'] = data['dbpath'] + os.path.sep + \
            etpConst['etpdatabasegpgfile']

        # setup script paths
        data['post_branch_hop_script'] = data['dbpath'] + os.path.sep + \
            etpConst['etp_post_branch_hop_script']
        data['post_branch_upgrade_script'] = data['dbpath'] + \
            os.path.sep + etpConst['etp_post_branch_upgrade_script']
        data['post_repo_update_script'] = data['dbpath'] + os.path.sep + \
            etpConst['etp_post_repo_update_script']

        data['webservices_config'] = data['dbpath'] + os.path.sep + \
            etpConst['etpdatabasewebservicesfile']

        # initialize CONFIG_PROTECT
        # will be filled the first time the db will be opened
        data['configprotect'] = None
        data['configprotectmask'] = None

        for repo_package in packages:
            new_repo_package = entropy.tools.expand_plain_package_mirror(
                repo_package, product, name)
            if new_repo_package is None:
                continue
            data['plain_packages'].append(repo_package)
            data['packages'].append(new_repo_package)

        return data

    def _repositories_parser(self):
        """
        Setup Entropy Client repository settings reading them from
        the relative config file specified in /etc/entropy/repositories.conf

        @return: parsed metadata
        @rtype: dict
        """
        repo_conf = self.__setting_files['repositories']
        data = {
            'available': {},
            'excluded': {},
            'order': [],
            'product': etpConst['product'],
            'branch': etpConst['branch'],
            'arch': etpConst['currentarch'],
            'default_repository': etpConst['officialrepositoryid'],
            'transfer_limit': etpConst['downloadspeedlimit'],
            'timeout': etpConst['default_download_timeout'],
            'security_advisories_url': etpConst['securityurl'],
            'developer_repo': False,
            'differential_update': True,
        }

        if not (os.path.isfile(repo_conf) and os.access(repo_conf, os.R_OK)):
            return data

        enc = etpConst['conf_encoding']
        # TODO: repository = statements in repositories.conf
        # will be deprecated by mid 2014
        with codecs.open(repo_conf, "r", encoding=enc) as repo_f:
            repositoriesconf = [x.strip() for x in \
                                    repo_f.readlines() if x.strip()]
        repositories_d_conf = self.__generic_d_parser(
            "repositories_conf_d", None, validate=False)

        # add content of skipped (disabled) files as commented
        # out stuff
        skipped_conf = ["#" + x for x in self.__generic_d_parser(
            "repositories_conf_d", None,
            validate=False, parse_skipped=True)]
        repositories_d_conf += skipped_conf

        repoids = set()

        def _product_func(line, setting):
            data['product'] = setting

        def _branch_func(line, setting):
            data['branch'] = setting

        def _repository_func(line, setting):

            excluded = False
            my_repodata = data['available']

            if line.startswith("#"):
                excluded = True
                my_repodata = data['excluded']
                line = line.lstrip(" #")

            try:
                reponame, repodata = self._analyze_client_repo_string(line,
                    data['branch'], data['product'])
            except AttributeError:
                return

            # validate repository id string
            if not entropy.tools.validate_repository_id(reponame):
                sys.stderr.write("!!! invalid repository id '%s' in '%s'\n" % (
                    reponame, repo_conf))
                return

            repoids.add(reponame)
            obj = my_repodata.get(reponame)
            if obj is not None:

                obj['plain_packages'].extend(repodata['plain_packages'])
                obj['packages'].extend(repodata['packages'])

                if (not obj['plain_database']) and \
                    repodata['plain_database']:

                    obj['dbrevision'] = repodata['dbrevision']
                    obj['plain_database'] = repodata['plain_database']
                    obj['database'] = repodata['database']
                    obj['dbcformat'] = repodata['dbcformat']

            else:
                my_repodata[reponame] = repodata.copy()
                if not excluded:
                    data['order'].append(reponame)

        def _offrepoid(line, setting):
            data['default_repository'] = setting

        def _developer_repo(line, setting):
            bool_setting = entropy.tools.setting_to_bool(setting)
            if bool_setting is not None:
                data['developer_repo'] = bool_setting

        def _differential_update(line, setting):
            bool_setting = entropy.tools.setting_to_bool(setting)
            if bool_setting is not None:
                data['differential_update'] = bool_setting

        def _down_speed_limit(line, setting):
            data['transfer_limit'] = None
            try:
                myval = int(setting)
                if myval > 0:
                    data['transfer_limit'] = myval
            except ValueError:
                data['transfer_limit'] = None

        def _down_timeout(line, setting):
            try:
                data['timeout'] = int(setting)
            except ValueError:
                return

        def _security_url(setting):
            data['security_advisories_url'] = setting

        settings_map = {
            'product': _product_func,
            'branch': _branch_func,
            'repository': _repository_func,
            '#repository': _repository_func,
            # backward compatibility
            'officialrepositoryid': _offrepoid,
            'official-repository-id': _offrepoid,
            'developer-repo': _developer_repo,
            'differential-update': _differential_update,
            # backward compatibility
            'downloadspeedlimit': _down_speed_limit,
            'download-speed-limit': _down_speed_limit,
            # backward compatibility
            'downloadtimeout': _down_timeout,
            'download-timeout': _down_timeout,
            # backward compatibility
            'securityurl': _security_url,
            'security-url': _security_url,
        }

        # setup product and branch first
        for line in repositoriesconf:

            key, value = entropy.tools.extract_setting(line)
            if key is None:
                continue
            key = key.replace(" ", "")
            key = key.replace("\t", "")

            if key not in ("product", "branch"):
                continue

            func = settings_map.get(key)
            if func is None:
                continue
            func(line, value)

        for line in repositoriesconf:

            key, value = entropy.tools.extract_setting(line)
            if key is None:
                continue
            key = key.replace(" ", "")
            key = key.replace("\t", "")

            func = settings_map.get(key)
            if func is None:
                continue
            func(line, value)

        for line in repositories_d_conf:

            key, value = entropy.tools.extract_setting(line)
            if key is None:
                continue
            key = key.replace(" ", "")
            key = key.replace("\t", "")
            if key not in ("repository", "#repository"):
                # no other statements supported from here
                continue

            func = settings_map.get(key)
            if func is None:
                continue
            func(line, value)

        # .ini-like file support.
        _conf_dir, setting_files, _skipped_files, _auto_upd = \
            self.__setting_dirs["repositories_conf_d"]
        candidate_inis = [x for x, y in setting_files]

        ini_parser = RepositoryConfigParser(encoding = enc)
        try:
            ini_parser.read(candidate_inis)
        except (IOError, OSError) as err:
            sys.stderr.write("Cannot parse %s: %s\n" % (
                    " ".join(candidate_inis),
                    err))
            ini_parser = None

        if ini_parser:
            ini_repositories = ini_parser.repositories()
            for ini_repository in ini_repositories:
                if ini_repository in repoids:
                    # double syntax is not supported.
                    continue

                repoids.add(ini_repository)
                ini_dbs = ini_parser.repo(ini_repository)
                try:
                    ini_pkgs = ini_parser.pkgs(ini_repository)
                except KeyError:
                    ini_pkgs = []

                try:
                    ini_desc = ini_parser.desc(ini_repository)
                except KeyError:
                    ini_desc = _("No description")

                ini_excluded = not ini_parser.enabled(ini_repository)
                ini_data = self._generate_repository_metadata(
                    ini_repository, ini_desc, ini_pkgs, ini_dbs,
                    data['product'], data['branch'])
                if ini_excluded:
                    data['excluded'][ini_repository] = ini_data
                else:
                    data['available'][ini_repository] = ini_data
                    data['order'].append(ini_repository)

        try:
            tx_limit = int(os.getenv("ETP_DOWNLOAD_KB"))
        except (ValueError, TypeError,):
            tx_limit = None
        if tx_limit is not None:
            data['transfer_limit'] = tx_limit

        # validate using mtime
        dmp_path = etpConst['dumpstoragedir']
        for repoid in repoids:

            found_into = 'available'
            if repoid in data['available']:
                repo_data = data['available'][repoid]
            elif repoid in data['excluded']:
                repo_data = data['excluded'][repoid]
                found_into = 'excluded'
            else:
                continue

            # validate repository settings
            if not repo_data['plain_database'].strip():
                data[found_into].pop(repoid)
                if repoid in data['order']:
                    data['order'].remove(repoid)

            repo_db_path = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabasefile'])
            repo_mtime_fn = "%s_%s_%s.mtime" % (repoid, data['branch'],
                data['product'],)

            repo_db_path_mtime = os.path.join(dmp_path, repo_mtime_fn)
            if os.path.isfile(repo_db_path) and \
                os.access(repo_db_path, os.R_OK):
                valid = self.validate_entropy_cache(repo_db_path,
                    repo_db_path_mtime, repoid = repoid)
                if not valid:
                    EntropyCacher.clear_cache(excluded_items = ["db_match"])

        # insert extra packages mirrors directly from repository dirs
        # if they actually exist. use data['order'] because it reflects
        # the list of available repos.
        for repoid in data['order']:
            if repoid in data['available']:
                obj = data['available'][repoid]
            elif repoid in data['excluded']:
                obj = data['excluded'][repoid]
            else:
                continue

            mirrors_file = os.path.join(obj['dbpath'],
                etpConst['etpdatabasemirrorsfile'])

            raw_mirrors = []
            if (os.path.isfile(mirrors_file) and \
                os.access(mirrors_file, os.R_OK)):
                raw_mirrors = entropy.tools.generic_file_content_parser(
                    mirrors_file, encoding = etpConst['conf_encoding'])

            mirrors_data = []
            for mirror in raw_mirrors:
                expanded_mirror = entropy.tools.expand_plain_package_mirror(
                    mirror, data['product'], repoid)
                if expanded_mirror is None:
                    continue
                mirrors_data.append((mirror, expanded_mirror))

            # add in reverse order, at the beginning of the list
            mirrors_data.reverse()
            for mirror, expanded_mirror in mirrors_data:
                obj['plain_packages'].insert(0, mirror)
                obj['packages'].insert(0, expanded_mirror)

            # now use fallback mirrors information to properly sort
            # fallback mirrors, giving them the lowest priority even if
            # they are listed on top.
            fallback_mirrors_file = os.path.join(obj['dbpath'],
                etpConst['etpdatabasefallbackmirrorsfile'])
            fallback_mirrors = []
            if os.path.isfile(fallback_mirrors_file) and \
                os.access(fallback_mirrors_file, os.R_OK):
                fallback_mirrors = entropy.tools.generic_file_content_parser(
                    fallback_mirrors_file, encoding = etpConst['conf_encoding'])

            pkgs_map = {}
            if fallback_mirrors:
                for pkg_url in obj['plain_packages']:
                    urlobj = entropy.tools.spliturl(pkg_url)
                    try:
                        url_key = urlobj.netloc
                    except AttributeError as err:
                        const_debug_write(__name__,
                            "error splitting url: %s" % (err,))
                        url_key = None
                    if url_key is None:
                        break
                    map_obj = pkgs_map.setdefault(url_key, [])
                    map_obj.append(pkg_url)

            fallback_urls = []
            if pkgs_map:
                for fallback_mirror in fallback_mirrors:
                    belonging_urls = pkgs_map.get(fallback_mirror)
                    if belonging_urls is None:
                        # nothing to do
                        continue
                    fallback_urls.extend(belonging_urls)

            if fallback_urls:
                for fallback_url in fallback_urls:
                    expanded_fallback_url = \
                        entropy.tools.expand_plain_package_mirror(
                            fallback_url, data['product'], repoid)
                    while True:
                        try:
                            obj['plain_packages'].remove(fallback_url)
                        except ValueError:
                            break
                    while True:
                        try:
                            obj['packages'].remove(expanded_fallback_url)
                        except ValueError:
                            break
                    obj['plain_packages'].insert(0, fallback_url)
                    obj['packages'].insert(0, expanded_fallback_url)

        # override parsed branch from env
        override_branch = os.getenv('ETP_BRANCH')
        if override_branch is not None:
            data['branch'] = override_branch

        # remove repositories that are in excluded if they are in available
        for repoid in set(data['excluded']):
            if repoid in data['available']:
                try:
                    del data['excluded'][repoid]
                except KeyError:
                    continue

        return data

    def _clear_repository_cache(self, repoid = None):
        """
        Internal method, go away!
        """
        self.__cacher.discard()
        EntropyCacher.clear_cache(excluded_items = ["db_match", "world_update"])

        if repoid is not None:
            EntropyCacher.clear_cache_item("%s/%s/" % (
                EntropyCacher.CACHE_IDS['db_match'], repoid,))
            EntropyCacher.clear_cache_item("%s/%s/" % (
                EntropyCacher.CACHE_IDS['mask_filter'], repoid,))

    def __generic_parser(self, filepath, comment_tag = "#"):
        """
        Internal method. This is the generic file parser here.

        @param filepath: valid path
        @type filepath: string
        @keyword comment_tag: default comment tag (column where comments starts)
        @type: string
        @return: raw text extracted from file
        @rtype: list
        """
        root = etpConst['systemroot']
        try:
            mtime = os.path.getmtime(filepath)
        except (OSError, IOError):
            mtime = 0.0

        cache_key = (root, filepath)
        cache_obj = self.__mtime_cache.get(cache_key)
        if cache_obj is not None:
            if cache_obj['mtime'] == mtime:
                return SystemSettings.CachingList(cache_obj['data'])

        cache_obj = {'mtime': mtime,}

        enc = etpConst['conf_encoding']
        lines = []
        try:
            lines += entropy.tools.generic_file_content_parser(
                filepath, comment_tag = comment_tag, encoding = enc)
            data = SystemSettings.CachingList(lines)
        except IOError as err:
            const_debug_write(__name__, "IOError __generic_parser, %s: %s" % (
                    filepath, err,))
        except OSError as err:
            const_debug_write(__name__, "OSError __generic_parser, %s: %s" % (
                    filepath, err,))
        except UnicodeEncodeError as err:
            const_debug_write(__name__, "UEE __generic_parser, %s: %s" % (
                    filepath, err,))
        except UnicodeDecodeError as err:
            const_debug_write(__name__, "UDE __generic_parser, %s: %s" % (
                    filepath, err,))
        data = SystemSettings.CachingList(lines)
        # do not cache CachingList, because it contains cache that
        # shouldn't survive a clear()
        cache_obj['data'] = lines
        self.__mtime_cache[cache_key] = cache_obj
        return data

    def __remove_repo_cache(self, repoid = None):
        """
        Internal method. Remove repository cache, because not valid anymore.

        @keyword repoid: repository identifier or None
        @type repoid: string or None
        @return: None
        @rtype: None
        """
        if os.path.isdir(etpConst['dumpstoragedir']):
            if repoid:
                self._clear_repository_cache(repoid = repoid)
                return
            for repoid in self['repositories']['order']:
                self._clear_repository_cache(repoid = repoid)
        else:
            try:
                os.makedirs(etpConst['dumpstoragedir'])
            except IOError as e:
                if e.errno == errno.EROFS:
                    # readonly filesystem
                    # placeholder for possible future activities
                    pass
                return
            except OSError:
                return

    def __save_file_mtime(self, toread, tosaveinto):
        """
        Internal method. Save mtime of a file to another file.

        @param toread: file path to read
        @type toread: string
        @param tosaveinto: path where to save retrieved mtime information
        @type tosaveinto: string
        @return: None
        @rtype: None
        """
        try:
            currmtime = os.path.getmtime(toread)
        except (OSError, IOError):
            currmtime = 0.0

        if not os.path.isdir(etpConst['dumpstoragedir']):
            try:
                os.makedirs(etpConst['dumpstoragedir'], 0o775)
                const_setup_perms(etpConst['dumpstoragedir'],
                    etpConst['entropygid'])
            except IOError as e:
                if e.errno == errno.EROFS: # readonly filesystem
                    # readonly filesystem
                    # placeholder for possible future activities
                    pass
                return
            except (OSError,) as e:
                # unable to create the storage directory
                # useless to continue
                return

        enc = etpConst['conf_encoding']
        try:
            mtime_f = codecs.open(tosaveinto, "w", encoding=enc)
        except IOError as e: # unable to write?
            if e.errno == errno.EROFS: # readonly filesystem
                # readonly filesystem
                # placeholder for possible future activities
                pass
            return
        else:
            mtime_f.write(str(currmtime))
            mtime_f.flush()
            mtime_f.close()
            os.chmod(tosaveinto, 0o664)
            if etpConst['entropygid'] is not None:
                os.chown(tosaveinto, 0, etpConst['entropygid'])


    def validate_entropy_cache(self, settingfile, mtimefile, repoid = None):
        """
        Internal method. Validates Entropy Cache based on a setting file
        and its stored (cache bound) mtime.

        @param settingfile: path of the setting file
        @type settingfile: string
        @param mtimefile: path where to save retrieved mtime information
        @type mtimefile: string
        @keyword repoid: repository identifier or None
        @type repoid: string or None
        @return: None
        @rtype: None
        """

        def revalidate():
            try:
                self.__remove_repo_cache(repoid = repoid)
                self.__save_file_mtime(settingfile, mtimefile)
            except (OSError, IOError):
                return

        # handle on-disk cache validation
        # in this case, repositories cache
        # if file is changed, we must destroy cache
        if not os.path.isfile(mtimefile):
            # we can't know if it has been updated
            # remove repositories caches
            revalidate()
            return

        # check mtime
        enc = etpConst['conf_encoding']
        try:
            with codecs.open(mtimefile, "r", encoding=enc) as mtime_f:
                mtime = str(mtime_f.readline().strip())
        except (OSError, IOError,):
            mtime = "0.0"

        try:
            currmtime = str(os.path.getmtime(settingfile))
        except (OSError, IOError,):
            currmtime = "0.0"

        if mtime != currmtime:
            revalidate()
            return False
        return True
