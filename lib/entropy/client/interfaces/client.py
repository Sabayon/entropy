# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Core Interface}.

"""
import os
import codecs
import threading

from entropy.core import Singleton
from entropy.fetchers import UrlFetcher, MultipleUrlFetcher
from entropy.output import TextInterface, bold, red, darkred, blue
from entropy.client.interfaces.loaders import LoadersMixin
from entropy.client.interfaces.cache import CacheMixin
from entropy.client.interfaces.db import InstalledPackagesRepository
from entropy.client.interfaces.dep import CalculatorsMixin
from entropy.client.interfaces.methods import RepositoryMixin, MiscMixin, \
    MatchMixin
from entropy.client.interfaces.noticeboard import NoticeBoardMixin
from entropy.const import etpConst, const_debug_write, \
    const_convert_to_unicode, const_file_readable
from entropy.core.settings.base import SystemSettings
from entropy.core.settings.plugins.skel import SystemSettingsPlugin
from entropy.misc import LogFile
from entropy.exceptions import SystemDatabaseError, RepositoryError
from entropy.cache import EntropyCacher
from entropy.i18n import _

import entropy.dump
import entropy.dep
import entropy.tools

class ClientSystemSettingsPlugin(SystemSettingsPlugin):

    def __init__(self, plugin_id, helper_interface):
        SystemSettingsPlugin.__init__(self, plugin_id, helper_interface)
        self.__repos_files = {}
        self.__repos_mtime = {}
        self._mtime_cache = {}
        # Package repositories must be able to live across
        # SystemSettings.clear() calls, because they are very
        # special and 3rd-party (but even Sulfur) tools expect to always
        # have them there after having called Client.add_package_repository
        self.__package_repositories = []
        self.__package_repositories_meta = {}

    @staticmethod
    def client_conf_path():
        """
        Return current client.conf path, this takes into account the current
        configuration files directory path (which is affected by "root" path
        changes [default: /])
        """
        # path to /etc/entropy/server.conf (usually, depends on systemroot)
        return os.path.join(etpConst['confdir'], "client.conf")

    def _add_package_repository(self, repository_id, repository_metadata):
        """
        Internal method, used by Entropy Client. Add a package repository
        to this SystemSettings plugins to make  it able to live across
        SystemSettings.clear() calls.

        @param repository_id: repository identifier
        @type repository_id: string
        @param repository_metadata: a dict object that will be merged
            into SystemSettings['repositories'] when clear() will be called
        @type repository_metadata: dict
        @raise KeyError: if repository_id is already stored.
        """
        if repository_id in self.__package_repositories:
            raise KeyError("%s already added" % (repository_id,))
        self.__package_repositories.append(repository_id)
        self.__package_repositories_meta[repository_id] = repository_metadata

    def _drop_package_repository(self, repository_id):
        """
        Drop package repository previously added by calling
        _add_package_repository()

        @param repository_id: repository identifier
        @type repository_id: string
        @raise KeyError: if repository_id is not available
        """
        del self.__package_repositories_meta[repository_id]
        self.__package_repositories.remove(repository_id)

    def __setup_repos_files(self, system_settings):
        """
        This function collects available repositories configuration files
        by filling internal dict() __repos_files and __repos_mtime.

        @param system_settings: SystemSettings instance
        @type system_settings: instance of SystemSettings
        @return: None
        @rtype: None
        """

        self.__repos_mtime = {
            'repos_license_whitelist': {},
            'repos_mask': {},
            'repos_system_mask': {},
            'repos_critical_updates': {},
            'repos_keywords': {},
        }
        self.__repos_files = {
            'repos_license_whitelist': {},
            'repos_mask': {},
            'repos_system_mask': {},
            'repos_critical_updates': {},
            'repos_keywords': {},
        }

        dmp_dir = etpConst['dumpstoragedir']
        avail_data = system_settings['repositories']['available']
        for repoid in system_settings['repositories']['order']:

            repo_data = avail_data[repoid]
            if "__temporary__" in repo_data:
                continue

            repos_mask_setting = {}
            repos_mask_mtime = {}
            repos_lic_wl_setting = {}
            repos_lic_wl_mtime = {}
            repos_sm_mask_setting = {}
            repos_sm_mask_mtime = {}
            confl_tagged = {}
            repos_critical_updates_setting = {}
            repos_critical_updates_mtime = {}
            repos_keywords_setting = {}
            repos_keywords_mtime = {}

            maskpath = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabasemaskfile'])
            wlpath = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabaselicwhitelistfile'])
            sm_path = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabasesytemmaskfile'])
            critical_path = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabasecriticalfile'])
            keywords_path = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabasekeywordsfile'])

            if const_file_readable(maskpath):
                repos_mask_setting[repoid] = maskpath
                repos_mask_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabasemaskfile'] + ".mtime"

            if const_file_readable(wlpath):
                repos_lic_wl_setting[repoid] = wlpath
                repos_lic_wl_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabaselicwhitelistfile'] + \
                    ".mtime"

            if const_file_readable(sm_path):
                repos_sm_mask_setting[repoid] = sm_path
                repos_sm_mask_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabasesytemmaskfile'] + \
                    ".mtime"

            if const_file_readable(critical_path):
                repos_critical_updates_setting[repoid] = critical_path
                repos_critical_updates_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabasecriticalfile'] + \
                    ".mtime"

            if const_file_readable(keywords_path):
                repos_keywords_setting[repoid] = keywords_path
                repos_keywords_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabasekeywordsfile'] + \
                    ".mtime"

            self.__repos_files['repos_mask'].update(repos_mask_setting)
            self.__repos_mtime['repos_mask'].update(repos_mask_mtime)

            self.__repos_files['repos_license_whitelist'].update(
                repos_lic_wl_setting)
            self.__repos_mtime['repos_license_whitelist'].update(
                repos_lic_wl_mtime)

            self.__repos_files['repos_system_mask'].update(
                repos_sm_mask_setting)
            self.__repos_mtime['repos_system_mask'].update(
                repos_sm_mask_mtime)

            self.__repos_files['repos_critical_updates'].update(
                repos_critical_updates_setting)
            self.__repos_mtime['repos_critical_updates'].update(
                repos_critical_updates_mtime)

            self.__repos_files['repos_keywords'].update(
                repos_keywords_setting)
            self.__repos_mtime['repos_keywords'].update(
                repos_keywords_mtime)

    def __generic_parser(self, filepath):
        """
        Internal method. This is the generic file parser here.

        @param filepath: valid path
        @type filepath: string
        @return: raw text extracted from file
        @rtype: list
        """
        root = etpConst['systemroot']
        try:
            mtime = os.path.getmtime(filepath)
        except (OSError, IOError):
            mtime = 0.0

        cache_key = (root, filepath)
        cache_obj = self._mtime_cache.get(cache_key)
        if cache_obj is not None:
            if cache_obj['mtime'] == mtime:
                return cache_obj['data']

        cache_obj = {'mtime': mtime,}

        enc = etpConst['conf_encoding']
        data = entropy.tools.generic_file_content_parser(filepath,
            comment_tag = "##", encoding = enc)
        if SystemSettings.DISK_DATA_CACHE:
            cache_obj['data'] = data
            self._mtime_cache[cache_key] = cache_obj
        return data

    def __run_post_branch_migration_hooks(self, sys_settings_instance):

        # only root can do this
        if os.getuid() != 0:
            return

        old_branch_path = etpConst['etp_previous_branch_file']
        in_branch_upgrade_path = etpConst['etp_in_branch_upgrade_file']
        current_branch = sys_settings_instance['repositories']['branch']
        enc = etpConst['conf_encoding']

        def write_current_branch(branch):
            with codecs.open(old_branch_path, "w", encoding=enc) as old_brf:
                old_brf.write(branch)
                old_brf.flush()

        def write_in_branch_upgrade(branch):
            with codecs.open(in_branch_upgrade_path, "w", encoding=enc) as brf:
                brf.write("in branch upgrade: %s" % (branch,))
                brf.flush()

        if not os.path.isfile(old_branch_path):
            write_current_branch(current_branch)
            return

        with codecs.open(old_branch_path, "r", encoding=enc) as old_f:
            old_branch = old_f.readline().strip()

        if old_branch == current_branch: # all fine, no need to run
            return

        repos, err = self._helper._run_repositories_post_branch_switch_hooks(
            old_branch, current_branch)
        if not err:
            write_in_branch_upgrade(current_branch)
            write_current_branch(current_branch)

    def __run_post_branch_upgrade_hooks(self, sys_settings_instance):

        # only root can do this
        if os.getuid() != 0:
            return

        repos, errors = self._helper._run_repository_post_branch_upgrade_hooks(
            pretend = True)
        if not repos:
            # no scripts to run
            return

        # look for updates
        # critical_updates = False is needed to avoid
        # issues with metadata not being available
        try:
            outcome = self._helper.calculate_updates(critical_updates = False)
            update, remove = outcome['update'], outcome['remove']
            fine, spm_fine = outcome['fine'], outcome['spm_fine']
        except (ValueError, SystemDatabaseError, RepositoryError,):
            # RepositoryError is triggered when branch is hopped
            # SystemDatabaseError is triggered when no client db is avail
            # ValueError is triggered when repos are broken
            update = 1 # foo!

        def delete_in_branch_upgrade():
            br_path = etpConst['etp_in_branch_upgrade_file']
            try:
                os.remove(br_path)
            except OSError:
                pass

        # actually execute this only if
        # there are no updates left
        if not update:
            self._helper._run_repository_post_branch_upgrade_hooks()
            delete_in_branch_upgrade()

    def system_mask_parser(self, system_settings_instance):

        parser_data = {}
        # match installed packages of system_mask
        mask_installed = []
        mask_installed_keys = {}
        while (self._helper.installed_repository() != None):
            try:
                self._helper.installed_repository().validate()
            except SystemDatabaseError:
                break
            mc_cache = set()
            repos_mask_list = self.__repositories_system_mask(
                system_settings_instance)
            m_list = repos_mask_list + system_settings_instance['system_mask']
            for atom in m_list:
                m_ids, m_r = self._helper.installed_repository().atomMatch(atom,
                    multiMatch = True)
                if m_r != 0:
                    continue
                mykey = entropy.dep.dep_getkey(atom)
                obj = mask_installed_keys.setdefault(mykey, set())
                for m_id in m_ids:
                    if m_id in mc_cache:
                        continue
                    mc_cache.add(m_id)
                    mask_installed.append(m_id)
                    obj.add(m_id)
            break

        parser_data.update({
            'repos_installed': mask_installed,
            'repos_installed_keys': mask_installed_keys,
        })
        return parser_data

    def masking_validation_parser(self, system_settings_instance):
        data = {
            'cache': {}, # package masking validation cache
        }
        return data

    def __repositories_repos_keywords(self, repo_keywords_path):
        """
        Parser returning system packages mask metadata read from
        packages.db.keywords file inside the repository directory.
        This file contains maintainer supplied per-repository extra
        package keywords.
        """
        root = etpConst['systemroot']
        try:
            mtime = os.path.getmtime(repo_keywords_path)
        except (OSError, IOError):
            mtime = 0.0

        cache_key = (root, repo_keywords_path)
        cache_obj = self._mtime_cache.get(cache_key)
        if cache_obj is not None:
            if cache_obj['mtime'] == mtime:
                return cache_obj['data']

        cache_obj = {'mtime': mtime,}

        data = {
            # universal keywords: keywords added repository-wide to all
            # the available packages (in repo).
            'universal': set(),
            # per-package keywording, keys are atoms/dep (first line argument)
            # values are provided keywords
            'packages': {},
            'packages_ids': None, # reserved for entropy.db package validation
        }

        enc = etpConst['conf_encoding']
        entries = entropy.tools.generic_file_content_parser(
            repo_keywords_path, encoding = enc)

        # iterate over config file data
        for entry in entries:
            entry = entry.split()
            if len(entry) == 1:
                # universal keyword
                item = entry[0]
                if item == "**":
                    item = ''
                data['universal'].add(item)

            elif len(entry) > 1:
                # per package keyword
                pkg = entry[0]
                keywords = entry[1:]
                obj = data['packages'].setdefault(pkg, set())
                obj.update(keywords)

        if SystemSettings.DISK_DATA_CACHE:
            cache_obj['data'] = data
            self._mtime_cache[cache_key] = cache_obj
        return data

    def __repositories_system_mask(self, sys_settings_instance):
        """
        Parser returning system packages mask metadata read from
        packages.db.system_mask file inside the repository directory.
        This file contains packages that should be always kept
        installed, extending the already defined (in repository database)
        set of atoms.
        """
        system_mask = []
        enc = etpConst['conf_encoding']
        for repoid in self.__repos_files['repos_system_mask']:
            filepath = self.__repos_files['repos_system_mask'][repoid]
            mtimepath = self.__repos_mtime['repos_system_mask'][repoid]
            sys_settings_instance.validate_entropy_cache(
                filepath, mtimepath, repoid = repoid)

            entries = self.__generic_parser(filepath)
            system_mask += [x for x in entries if x not in system_mask]

        return system_mask

    def repositories_parser(self, sys_settings_instance):
        """
        Parser that generates repository settings metadata.

        @param sys_settings_instance: SystemSettings instance
        @type sys_settings_instance: instance of SystemSettings
        @return: parsed metadata
        @rtype: dict
        """

        # add back repository metadata to SystemSettings['repositories']
        avail_data = sys_settings_instance['repositories']['available']
        for repository_id in self.__package_repositories:
            if repository_id not in avail_data:
                repodata = self.__package_repositories_meta[repository_id]
                # if correct, this won't trigger a stack overflow
                # add_repository calling SystemSettings.clear() I mean
                added = self._helper.add_repository(repodata)
                if not added:
                    raise ValueError("wtf? cannot add repository")

        # fill repositories metadata dictionaries
        self.__setup_repos_files(sys_settings_instance)

        data = {
            'license_whitelist': {},
            'mask': {},
            'system_mask': [],
            'critical_updates': {},
            'repos_keywords': {},
        }

        # parse license whitelist
        # Parser returning licenses considered accepted by default
        # (= GPL compatibles) read from package.lic_whitelist.
        for repoid in self.__repos_files['repos_license_whitelist']:
            sys_settings_instance.validate_entropy_cache(
                self.__repos_files['repos_license_whitelist'][repoid],
                self.__repos_mtime['repos_license_whitelist'][repoid],
                repoid = repoid)

            data['license_whitelist'][repoid] = self.__generic_parser(
                self.__repos_files['repos_license_whitelist'][repoid])

        # package masking
        # Parser returning packages masked at repository level read from
        # packages.db.mask inside the repository database directory.
        for repoid in self.__repos_files['repos_mask']:
            sys_settings_instance.validate_entropy_cache(
                self.__repos_files['repos_mask'][repoid],
                self.__repos_mtime['repos_mask'][repoid], repoid = repoid)

            data['mask'][repoid] = self.__generic_parser(
                self.__repos_files['repos_mask'][repoid])

        # keywords masking
        # Parser returning packages masked at repository level read from
        # packages.db.keywords inside the repository database directory.
        for repoid in self.__repos_files['repos_keywords']:
            sys_settings_instance.validate_entropy_cache(
                self.__repos_files['repos_keywords'][repoid],
                self.__repos_mtime['repos_keywords'][repoid],
                repoid = repoid)

            data['repos_keywords'][repoid] = \
                self.__repositories_repos_keywords(
                    self.__repos_files['repos_keywords'][repoid])

        # system masking
        data['system_mask'] = self.__repositories_system_mask(
            sys_settings_instance)

        # critical updates
        # Parser returning critical packages list metadata read from
        # packages.db.critical file inside the repository directory.
        # This file contains packages that should be always updated
        # before anything else.
        for repoid in self.__repos_files['repos_critical_updates']:
            sys_settings_instance.validate_entropy_cache(
                self.__repos_files['repos_critical_updates'][repoid],
                self.__repos_mtime['repos_critical_updates'][repoid],
                repoid = repoid)

            data['critical_updates'][repoid] = self.__generic_parser(
                self.__repos_files['repos_critical_updates'][repoid])

        return data

    def misc_parser(self, sys_settings_instance):

        """
        Parses Entropy client system configuration file.

        @return dict data
        """

        data = {
            'filesbackup': etpConst['filesbackup'],
            'forcedupdates': etpConst['forcedupdates'],
            'packagehashes': etpConst['packagehashes'],
            'gpg': etpConst['client_gpg'],
            'ignore_spm_downgrades': False,
            'splitdebug': etpConst['splitdebug'],
            'splitdebug_dirs': etpConst['splitdebug_dirs'],
            'multifetch': 1,
            'collisionprotect': etpConst['collisionprotect'],
            'configprotect': etpConst['configprotect'][:],
            'configprotectmask': etpConst['configprotectmask'][:],
            'configprotectskip': etpConst['configprotectskip'][:],
            'autoprune_days': None, # disabled by default
            'edelta_support': False, # disabled by default
        }

        cli_conf = ClientSystemSettingsPlugin.client_conf_path()
        root = etpConst['systemroot']
        try:
            mtime = os.path.getmtime(cli_conf)
        except (OSError, IOError):
            mtime = 0.0

        cache_key = (root, cli_conf)
        cache_obj = self._mtime_cache.get(cache_key)
        if cache_obj is not None:
            if cache_obj['mtime'] == mtime:
                return cache_obj['data']

        cache_obj = {'mtime': mtime,}

        if not const_file_readable(cli_conf):
            if SystemSettings.DISK_DATA_CACHE:
                cache_obj['data'] = data
                self._mtime_cache[cache_key] = cache_obj
            return data

        def _filesbackup(setting):
            bool_setting = entropy.tools.setting_to_bool(setting)
            if bool_setting is not None:
                data['filesbackup'] = bool_setting

        def _forcedupdates(setting):
            bool_setting = entropy.tools.setting_to_bool(setting)
            if bool_setting is not None:
                data['forcedupdates'] = bool_setting

        def _autoprune(setting):
            int_setting = entropy.tools.setting_to_int(setting, 0, 365)
            if int_setting is not None:
                data['autoprune_days'] = int_setting

        def _packagesdelta(setting):
            bool_setting = entropy.tools.setting_to_bool(setting)
            if bool_setting is not None:
                data['edelta_support'] = bool_setting

        def _packagehashes(setting):
            setting = setting.lower().split()
            hashes = set()
            for opt in setting:
                if opt in etpConst['packagehashes']:
                    hashes.add(opt)
            if hashes:
                data['packagehashes'] = tuple(sorted(hashes))

        def _multifetch(setting):
            int_setting = entropy.tools.setting_to_int(setting, None, None)
            bool_setting = entropy.tools.setting_to_bool(setting)
            if int_setting is not None:
                if int_setting not in range(2, 11):
                    int_setting = 10
                data['multifetch'] = int_setting
            if bool_setting is not None:
                if bool_setting:
                    data['multifetch'] = 3

        def _gpg(setting):
            bool_setting = entropy.tools.setting_to_bool(setting)
            if bool_setting is not None:
                data['gpg'] = bool_setting

        def _spm_downgrades(setting):
            bool_setting = entropy.tools.setting_to_bool(setting)
            if bool_setting is not None:
                data['ignore_spm_downgrades'] = bool_setting

        def _splitdebug(setting):
            bool_setting = entropy.tools.setting_to_bool(setting)
            if bool_setting is not None:
                data['splitdebug'] = bool_setting

        def _collisionprotect(setting):
            int_setting = entropy.tools.setting_to_int(setting, 0, 2)
            if int_setting is not None:
                data['collisionprotect'] = int_setting

        def _configprotect(setting):
            for opt in setting.split():
                data['configprotect'].append(const_convert_to_unicode(opt))

        def _configprotectmask(setting):
            for opt in setting.split():
                data['configprotectmask'].append(const_convert_to_unicode(opt))

        def _configprotectskip(setting):
            for opt in setting.split():
                data['configprotectskip'].append(
                    etpConst['systemroot'] + const_convert_to_unicode(opt))

        settings_map = {
            # backward compatibility
            'filesbackup': _filesbackup,
            'files-backup': _filesbackup,
            # backward compatibility
            'forcedupdates': _forcedupdates,
            'forced-updates': _forcedupdates,
            'packages-autoprune-days': _autoprune,
            'packages-delta': _packagesdelta,
            # backward compatibility
            'packagehashes': _packagehashes,
            'package-hashes': _packagehashes,
            'multifetch': _multifetch,
            'gpg': _gpg,
            'ignore-spm-downgrades': _spm_downgrades,
            'splitdebug': _splitdebug,
            # backward compatibility
            'collisionprotect': _collisionprotect,
            'collision-protect': _collisionprotect,
            # backward compatibility
            'configprotect': _configprotect,
            'config-protect': _configprotect,
            # backward compatibility
            'configprotectmask': _configprotectmask,
            'config-protect-mask': _configprotectmask,
            # backward compatibility
            'configprotectskip': _configprotectskip,
            'config-protect-skip': _configprotectskip,
        }

        enc = etpConst['conf_encoding']
        with codecs.open(cli_conf, "r", encoding=enc) as client_f:
            clientconf = [x.strip() for x in client_f.readlines() if \
                              x.strip() and not x.strip().startswith("#")]
        for line in clientconf:

            key, value = entropy.tools.extract_setting(line)
            if key is None:
                continue

            func = settings_map.get(key)
            if func is None:
                continue
            func(value)

        # completely disable GPG feature
        if not data['gpg'] and ("gpg" in data['packagehashes']):
            data['packagehashes'] = tuple((x for x in data['packagehashes'] \
                if x != "gpg"))

        # support ETP_SPLITDEBUG
        split_debug = os.getenv("ETP_SPLITDEBUG")
        if split_debug is not None:
            _splitdebug(split_debug)

        if SystemSettings.DISK_DATA_CACHE:
            cache_obj['data'] = data
            self._mtime_cache[cache_key] = cache_obj
        return data

    def post_setup(self, system_settings_instance):
        """
        Reimplemented from SystemSettingsPlugin.
        """

        if self._helper._can_run_sys_set_hooks:
            # run post-branch migration scripts if branch setting got changed
            self.__run_post_branch_migration_hooks(system_settings_instance)
            # run post-branch upgrade migration scripts if the function
            # above created migration files to handle
            self.__run_post_branch_upgrade_hooks(system_settings_instance)


class Client(Singleton, TextInterface, LoadersMixin, CacheMixin,
             CalculatorsMixin, RepositoryMixin, MiscMixin,
             MatchMixin, NoticeBoardMixin):

    def init_singleton(self, indexing = True, installed_repo = None,
            xcache = True, user_xcache = False, repo_validation = True,
            url_fetcher = None, multiple_url_fetcher = None, **kwargs):
        """
        Entropy Client Singleton interface. Your hitchhikers' guide to the
        Galaxy.

        @keyword indexing: enable metadata indexing (default is True)
        @type indexing: bool
        @keyword installed_repo: open installed packages repository? (default
            is True). Accepted values: True = open, False = open but consider
            it not available, -1 = do not even try to open
        @type installed_repo: bool or int
        @keyword xcache: enable on-disk cache (default is True)
        @type xcache: bool
        @keyword user_xcache: enable on-disk cache even for users not in the
            entropy group (default is False). Dangerous, could lead to cache
            inconsistencies.
        @type user_xcache: bool
        @keyword repo_validation: validate all the available repositories
            and automatically exclude the faulty ones
        @type repo_validation: bool
        @keyword url_fetcher: override default entropy.fetchers.UrlFetcher
            class usage. Provide your own implementation of UrlFetcher using
            this argument.
        @type url_fetcher: class or None
        @keyword multiple_url_fetcher: override default
            entropy.fetchers.MultipleUrlFetcher class usage. Provide your own
            implementation of MultipleUrlFetcher using this argument.
        """
        self.__instance_destroyed = False
        self._repo_error_messages_cache = set()
        self._repodb_cache = {}
        self._repodb_cache_mutex = threading.RLock()
        self._memory_db_instances = {}
        self._installed_repository = None
        self._treeupdates_repos = set()
        self._can_run_sys_set_hooks = False
        const_debug_write(__name__, "debug enabled")
        self.sys_settings_client_plugin_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']

        self._enabled_repos = []
        self.safe_mode = 0
        self._indexing = indexing
        self._repo_validation = repo_validation

        # setup package settings (masking and other stuff)
        self._settings = SystemSettings()
        const_debug_write(__name__, "SystemSettings loaded")

        # class init
        LoadersMixin.__init__(self)

        self.logger = LogFile(
            level = self._settings['system']['log_level'],
            filename = etpConst['entropylogfile'], header = "[client]")

        self._multiple_url_fetcher = multiple_url_fetcher
        self._url_fetcher = url_fetcher
        if url_fetcher is None:
            self._url_fetcher = UrlFetcher
        if multiple_url_fetcher is None:
            self._multiple_url_fetcher = MultipleUrlFetcher

        self._cacher = EntropyCacher()

        # backward compatibility, will be removed after 2011
        if "noclientdb" in kwargs:
            noclientdb = kwargs.get("noclientdb")
            self._do_open_installed_repo = True
            self._installed_repo_enable = True
            if noclientdb in (True, 1):
                self._installed_repo_enable = False
            elif noclientdb in (False, 0):
                self._installed_repo_enable = True
            elif noclientdb == 2:
                self._installed_repo_enable = False
                self._do_open_installed_repo = False
        else:
            self._do_open_installed_repo = True
            self._installed_repo_enable = True
            if installed_repo in (True, None, 1):
                self._installed_repo_enable = True
            elif installed_repo in (False, 0):
                self._installed_repo_enable = False
            elif installed_repo == -1:
                self._installed_repo_enable = False
                self._do_open_installed_repo = False

        self.xcache = xcache
        shell_xcache = os.getenv("ETP_NOCACHE")
        if shell_xcache:
            self.xcache = False

        do_validate_repo_cache = False
        # now if we are on live, we should disable it
        # are we running on a livecd? (/proc/cmdline has "cdroot")
        if entropy.tools.islive():
            self.xcache = False
        elif (not entropy.tools.is_user_in_entropy_group()) and not user_xcache:
            self.xcache = False
        elif not user_xcache:
            do_validate_repo_cache = True

        if not self.xcache and (entropy.tools.is_user_in_entropy_group()):
            self.clear_cache()

        if self._do_open_installed_repo:
            self._open_installed_repository()

        # create our SystemSettings plugin
        self.sys_settings_client_plugin = ClientSystemSettingsPlugin(
            self.sys_settings_client_plugin_id, self)

        # needs to be started here otherwise repository cache will be
        # always dropped
        if self.xcache:
            self._cacher.start()
        else:
            # disable STASHING_CACHE or we leak
            EntropyCacher.STASHING_CACHE = False

        if do_validate_repo_cache:
            self._validate_repositories_cache()

        if self._repo_validation:
            self._validate_repositories()
        else:
            self._enabled_repos.extend(self._settings['repositories']['order'])

        # add our SystemSettings plugin
        # Make sure we connect Entropy Client plugin AFTER client db init
        self._settings.add_plugin(self.sys_settings_client_plugin)

        # enable System Settings hooks
        self._can_run_sys_set_hooks = True
        const_debug_write(__name__, "singleton loaded")

    def destroy(self, _from_shutdown = False):
        """
        Destroy this Singleton instance, closing repositories, removing
        SystemSettings plugins added during instance initialization.
        This method should be always called when instance is not used anymore.
        """
        self.__instance_destroyed = True
        if hasattr(self, '_installed_repository'):
            if self._installed_repository is not None:
                self._installed_repository.close(
                    _token = InstalledPackagesRepository.NAME)
        if hasattr(self, 'logger'):
            self.logger.close()
        if hasattr(self, '_settings') and \
            hasattr(self, 'sys_settings_client_plugin_id') and \
            hasattr(self._settings, 'remove_plugin'):

            if not _from_shutdown:
                # shutdown() will terminate the whole process
                # so there is no need to remove plugins from
                # SystemSettings, it wouldn't make any diff.
                try:
                    self._settings.remove_plugin(
                        self.sys_settings_client_plugin_id)
                except KeyError:
                    pass

        self.close_repositories(mask_clear = False)

    def shutdown(self):
        """
        This method should be called when the whole process is going to be
        killed. It calls destroy() and stops any running thread
        """
        self._cacher.sync()  # enforce, destroy() may kill the current content
        self.destroy(_from_shutdown = True)
        self._cacher.stop()
        entropy.tools.kill_threads()

    def repository_packages_spm_sync(self, repository_identifier, repo_db,
        force = False):
        """
        Service method used to sync package names with Source Package Manager
        via metadata stored in Repository dbs collected at server-time.
        Source Package Manager can change package names, categories or slot
        and Entropy repositories must be kept in sync.

        In other words, it checks for /usr/portage/profiles/updates changes,
        of course indirectly, since there is no way entropy.client can directly
        depend on Portage.

        @param repository_identifier: repository identifier which repo_db
            parameter is bound
        @type repository_identifier: string
        @param repo_db: repository database instance
        @type repo_db: entropy.db.EntropyRepository
        @return: bool stating if changes have been made
        @rtype: bool
        """
        if not self._installed_repository:
            # nothing to do if client db is not availabe
            return False

        self._treeupdates_repos.add(repository_identifier)

        do_rescan = False
        shell_rescan = os.getenv("ETP_TREEUPDATES_RESCAN")
        if shell_rescan:
            do_rescan = True

        # check database digest
        stored_digest = repo_db.retrieveRepositoryUpdatesDigest(
            repository_identifier)
        if stored_digest == -1:
            do_rescan = True

        # check stored value in client database
        client_digest = "0"
        if not do_rescan:
            client_digest = \
                self._installed_repository.retrieveRepositoryUpdatesDigest(
                    repository_identifier)

        if do_rescan or (str(stored_digest) != str(client_digest)) or force:

            # reset database tables
            self._installed_repository.clearTreeupdatesEntries(
                repository_identifier)

            # load updates
            update_actions = repo_db.retrieveTreeUpdatesActions(
                repository_identifier)
            # now filter the required actions
            update_actions = \
                self._installed_repository.filterTreeUpdatesActions(
                    update_actions)

            if update_actions:

                mytxt = "%s: %s." % (
                    bold(_("ATTENTION")),
                    red(_("forcing packages metadata update")),
                )
                self.output(
                    mytxt,
                    importance = 1,
                    level = "info",
                    header = darkred(" * ")
                )
                mytxt = "%s %s." % (
                    red(_("Updating system database using repository")),
                    blue(repository_identifier),
                )
                self.output(
                    mytxt,
                    importance = 1,
                    level = "info",
                    header = darkred(" * ")
                )
                # run stuff
                self._installed_repository.runTreeUpdatesActions(
                    update_actions)

            # store new digest into database
            self._installed_repository.setRepositoryUpdatesDigest(
                repository_identifier, stored_digest)
            # store new actions
            self._installed_repository.addRepositoryUpdatesActions(
                InstalledPackagesRepository.NAME, update_actions,
                    self._settings['repositories']['branch'])
            self._installed_repository.commit()
            # clear client cache
            self._installed_repository.clearCache()
            return True

    def is_destroyed(self):
        return self.__instance_destroyed
