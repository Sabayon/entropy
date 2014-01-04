# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Settings module}.

"""
import codecs
import hashlib
import os

from entropy.const import etpConst, const_file_readable, \
    const_convert_to_unicode, const_convert_to_rawstring
from entropy.core.settings.plugins.skel import SystemSettingsPlugin

from entropy.exceptions import SystemDatabaseError, RepositoryError

import entropy.dep
import entropy.tools


class ClientSystemSettingsPlugin(SystemSettingsPlugin):

    ID = etpConst['system_settings_plugins_ids']['client_plugin']

    def __init__(self, helper_interface):
        SystemSettingsPlugin.__init__(
            self, self.ID, helper_interface)
        self.__repos_files = {}
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
        by filling internal dict() __repos_files.

        @param system_settings: SystemSettings instance
        @type system_settings: instance of SystemSettings
        @return: None
        @rtype: None
        """
        self.__repos_files = {
            'repos_license_whitelist': {},
            'repos_mask': {},
            'repos_system_mask': {},
            'repos_critical_updates': {},
            'repos_keywords': {},
        }

        avail_data = system_settings['repositories']['available']
        for repoid in system_settings['repositories']['order']:

            repo_data = avail_data[repoid]
            if "__temporary__" in repo_data:
                continue

            repos_mask_setting = {}
            repos_lic_wl_setting = {}
            repos_sm_mask_setting = {}
            repos_critical_updates_setting = {}
            repos_keywords_setting = {}

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

            if const_file_readable(wlpath):
                repos_lic_wl_setting[repoid] = wlpath

            if const_file_readable(sm_path):
                repos_sm_mask_setting[repoid] = sm_path

            if const_file_readable(critical_path):
                repos_critical_updates_setting[repoid] = critical_path

            if const_file_readable(keywords_path):
                repos_keywords_setting[repoid] = keywords_path

            self.__repos_files['repos_mask'].update(repos_mask_setting)

            self.__repos_files['repos_license_whitelist'].update(
                repos_lic_wl_setting)

            self.__repos_files['repos_system_mask'].update(
                repos_sm_mask_setting)

            self.__repos_files['repos_critical_updates'].update(
                repos_critical_updates_setting)

            self.__repos_files['repos_keywords'].update(
                repos_keywords_setting)

    def __generic_parser(self, filepath):
        """
        Internal method. This is the generic file parser here.

        @param filepath: valid path
        @type filepath: string
        @return: raw text extracted from file
        @rtype: list
        """
        return entropy.tools.generic_file_content_parser(
            filepath,
            comment_tag = "##",
            encoding = etpConst['conf_encoding'])

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

        def write_in_branch_upgrade(branch):
            with codecs.open(in_branch_upgrade_path, "w", encoding=enc) as brf:
                brf.write("in branch upgrade: %s" % (branch,))

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
        for repoid in self.__repos_files['repos_system_mask']:
            filepath = self.__repos_files['repos_system_mask'][repoid]

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

            data['license_whitelist'][repoid] = self.__generic_parser(
                self.__repos_files['repos_license_whitelist'][repoid])

        # package masking
        # Parser returning packages masked at repository level read from
        # packages.db.mask inside the repository database directory.
        for repoid in self.__repos_files['repos_mask']:
            data['mask'][repoid] = self.__generic_parser(
                self.__repos_files['repos_mask'][repoid])

        # keywords masking
        # Parser returning packages masked at repository level read from
        # packages.db.keywords inside the repository database directory.
        for repoid in self.__repos_files['repos_keywords']:
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
            'configprotect': set(),
            'configprotectmask': set(),
            'configprotectskip': set(),
            'autoprune_days': None, # disabled by default
            'edelta_support': False, # disabled by default
        }

        cli_conf = ClientSystemSettingsPlugin.client_conf_path()

        if not const_file_readable(cli_conf):
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
                data['configprotect'].add(const_convert_to_unicode(opt))

        def _configprotectmask(setting):
            for opt in setting.split():
                data['configprotectmask'].add(const_convert_to_unicode(opt))

        def _configprotectskip(setting):
            for opt in setting.split():
                data['configprotectskip'].add(
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

    def packages_configuration_hash(self):
        """
        Return a SHA1 hash of the current packages configuration.
        This includes masking, unmasking, keywording of all the
        configured repositories.
        """
        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring("-begin-"))

        settings = self._helper.ClientSettings()
        repo_settings = settings['repositories']

        cache_key = "__packages_configuration_hash__"
        cached = repo_settings.get(cache_key)
        if cached is not None:
            return cached

        sha.update(const_convert_to_rawstring("-begin-mask-"))

        for repository_id in sorted(repo_settings['mask'].keys()):
            packages = repo_settings['mask'][repository_id]
            cache_s = "mask:%s:{%s}|" % (
                repository_id, ",".join(sorted(packages)),
                )

            sha.update(const_convert_to_rawstring(cache_s))

        sha.update(const_convert_to_rawstring("-end-mask-"))

        sha.update(const_convert_to_rawstring("-begin-keywords-"))
        for repository_id in sorted(repo_settings['repos_keywords'].keys()):
            data = repo_settings['repos_keywords'][repository_id]
            packages = data['packages']

            for package in sorted(packages.keys()):
                keywords = packages[package]
                cache_s = "repos_keywords:%s:%s:{%s}|" % (
                    repository_id,
                    package,
                    sorted(keywords),
                    )
                sha.update(const_convert_to_rawstring(cache_s))

        sha.update(const_convert_to_rawstring("-end-keywords-"))

        sha.update(const_convert_to_rawstring("-end-"))

        outcome = sha.hexdigest()
        repo_settings[cache_key] = outcome
        return outcome
