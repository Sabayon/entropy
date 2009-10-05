# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Core Interface}.

"""

import os
import sys
from entropy.core import Singleton
from entropy.output import TextInterface, bold, red, darkred, blue
from entropy.db import dbapi2
from entropy.client.interfaces.loaders import LoadersMixin
from entropy.client.interfaces.cache import CacheMixin
from entropy.client.interfaces.dep import CalculatorsMixin
from entropy.client.interfaces.methods import RepositoryMixin, MiscMixin, \
    MatchMixin
from entropy.client.interfaces.fetch import FetchersMixin
from entropy.client.interfaces.noticeboard import NoticeBoardMixin
from entropy.const import etpConst, etpCache, etpUi, const_debug_write, \
    const_convert_to_unicode
from entropy.core.settings.base import SystemSettings
from entropy.core.settings.plugins.skel import SystemSettingsPlugin
from entropy.misc import LogFile
from entropy.exceptions import SystemDatabaseError, RepositoryError
from entropy.i18n import _

class ClientSystemSettingsPlugin(SystemSettingsPlugin):

    import entropy.tools as entropyTools

    def __init__(self, plugin_id, helper_interface):
        SystemSettingsPlugin.__init__(self, plugin_id, helper_interface)
        self.__repos_files = {}
        self.__repos_mtime = {}

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
            'conflicting_tagged_packages': {},
            'repos_critical_updates': {},
            'repos_keywords': {},
        }

        dmp_dir = etpConst['dumpstoragedir']
        for repoid in system_settings['repositories']['order']:

            repos_mask_setting = {}
            repos_mask_mtime = {}
            repos_lic_wl_setting = {}
            repos_lic_wl_mtime = {}
            repo_data = system_settings['repositories']['available'][repoid]
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
            ct_path = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabaseconflictingtaggedfile'])
            critical_path = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabasecriticalfile'])
            keywords_path = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabasekeywordsfile'])

            if os.access(maskpath, os.R_OK) and os.path.isfile(maskpath):
                repos_mask_setting[repoid] = maskpath
                repos_mask_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabasemaskfile'] + ".mtime"

            if os.access(wlpath, os.R_OK) and os.path.isfile(wlpath):
                repos_lic_wl_setting[repoid] = wlpath
                repos_lic_wl_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabaselicwhitelistfile'] + \
                    ".mtime"

            if os.access(sm_path, os.R_OK) and os.path.isfile(sm_path):
                repos_sm_mask_setting[repoid] = sm_path
                repos_sm_mask_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabasesytemmaskfile'] + \
                    ".mtime"
            if os.access(ct_path, os.R_OK) and os.path.isfile(ct_path):
                confl_tagged[repoid] = ct_path

            if os.access(critical_path, os.R_OK) and \
                os.path.isfile(critical_path):
                repos_critical_updates_setting[repoid] = critical_path
                repos_critical_updates_mtime[repoid] = dmp_dir + "/repo_" + \
                    repoid + "_" + etpConst['etpdatabasecriticalfile'] + \
                    ".mtime"

            if os.access(keywords_path, os.R_OK) and \
                os.path.isfile(keywords_path):
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

            self.__repos_files['conflicting_tagged_packages'].update(
                confl_tagged)

            self.__repos_files['repos_critical_updates'].update(
                repos_critical_updates_setting)
            self.__repos_mtime['repos_critical_updates'].update(
                repos_critical_updates_mtime)

            self.__repos_files['repos_keywords'].update(repos_keywords_setting)
            self.__repos_mtime['repos_keywords'].update(repos_keywords_mtime)

    def __run_post_branch_migration_hooks(self, sys_settings_instance):

        # only root can do this
        if os.getuid() != 0:
            return

        old_branch_path = etpConst['etp_previous_branch_file']
        in_branch_upgrade_path = etpConst['etp_in_branch_upgrade_file']
        current_branch = sys_settings_instance['repositories']['branch']

        def write_current_branch(branch):
            old_brf = open(old_branch_path, "w")
            old_brf.write(branch)
            old_brf.flush()
            old_brf.close()

        def write_in_branch_upgrade(branch):
            brf = open(in_branch_upgrade_path, "w")
            brf.write("in branch upgrade: %s" % (branch,))
            brf.flush()
            brf.close()

        if not os.path.isfile(old_branch_path):
            write_current_branch(current_branch)
            return

        old_f = open(old_branch_path, "r")
        old_branch = old_f.readline().strip()
        old_f.close()

        if old_branch == current_branch: # all fine, no need to run
            return

        repos, err = self._helper.run_repositories_post_branch_switch_hooks(
            old_branch, current_branch)
        if not err:
            write_in_branch_upgrade(current_branch)
            write_current_branch(current_branch)

    def __run_post_branch_upgrade_hooks(self, sys_settings_instance):

        # only root can do this
        if os.getuid() != 0:
            return

        repos, errors = self._helper.run_repository_post_branch_upgrade_hooks(
            pretend = True)
        if not repos:
            # no scripts to run
            return

        # look for updates
        # critical_updates = False is needed to avoid
        # issues with metadata not being available
        try:
            update, remove, fine, spm_fine = \
                self._helper.calculate_world_updates(
                    critical_updates = False)
        except (ValueError, SystemDatabaseError, RepositoryError,):
            # RepositoryError is triggered when branch is hopped
            # SystemDatabaseError is triggered when no client db is avail
            # ValueError is triggered when repos are broken
            update = 1 # foo!

        def delete_in_branch_upgrade():
            br_path = etpConst['etp_in_branch_upgrade_file']
            if os.access(br_path, os.W_OK) and os.path.isfile(br_path):
                os.remove(br_path)

        # actually execute this only if
        # there are no updates left
        if not update:
            self._helper.run_repository_post_branch_upgrade_hooks()
            delete_in_branch_upgrade()

    def system_mask_parser(self, system_settings_instance):

        parser_data = {}
        # match installed packages of system_mask
        mask_installed = []
        mask_installed_keys = {}
        while (self._helper.clientDbconn != None):
            try:
                self._helper.clientDbconn.validateDatabase()
            except SystemDatabaseError:
                break
            mc_cache = set()
            repos_mask_list = self.__repositories_system_mask(
                system_settings_instance)
            m_list = repos_mask_list + system_settings_instance['system_mask']
            for atom in m_list:
                m_ids, m_r = self._helper.clientDbconn.atomMatch(atom,
                    multiMatch = True)
                if m_r != 0:
                    continue
                mykey = self.entropyTools.dep_getkey(atom)
                if mykey not in mask_installed_keys:
                    mask_installed_keys[mykey] = set()
                for m_id in m_ids:
                    if m_id in mc_cache:
                        continue
                    mc_cache.add(m_id)
                    mask_installed.append(m_id)
                    mask_installed_keys[mykey].add(m_id)
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
        data = {
            # universal keywords: keywords added repository-wide to all
            # the available packages (in repo).
            'universal': set(),
            # per-package keywording, keys are atoms/dep (first line argument)
            # values are provided keywords
            'packages': {},
            'packages_ids': None, # reserved for entropy.db package validation
        }

        entries = self.entropyTools.generic_file_content_parser(
            repo_keywords_path)

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
            sys_settings_instance.validate_entropy_cache(
                self.__repos_files['repos_system_mask'][repoid],
                self.__repos_mtime['repos_system_mask'][repoid],
                repoid = repoid)
            system_mask += [x for x in \
                self.entropyTools.generic_file_content_parser(
                    self.__repos_files['repos_system_mask'][repoid]) if x \
                        not in system_mask]
        return system_mask

    def repositories_parser(self, sys_settings_instance):
        """
        Parser that generates repository settings metadata.

        @param sys_settings_instance: SystemSettings instance
        @type sys_settings_instance: instance of SystemSettings
        @return: parsed metadata
        @rtype: dict
        """

        # fill repositories metadata dictionaries
        self.__setup_repos_files(sys_settings_instance)

        data = {
            'license_whitelist': {},
            'mask': {},
            'system_mask': [],
            'critical_updates': {},
            'conflicting_tagged_packages': {},
            'repos_keywords': {},
        }

        # parse license whitelist
        """
        Parser returning licenses considered accepted by default
        (= GPL compatibles) read from package.lic_whitelist.
        """
        for repoid in self.__repos_files['repos_license_whitelist']:
            sys_settings_instance.validate_entropy_cache(
                self.__repos_files['repos_license_whitelist'][repoid],
                self.__repos_mtime['repos_license_whitelist'][repoid],
                repoid = repoid)

            data['license_whitelist'][repoid] = \
                self.entropyTools.generic_file_content_parser(
                    self.__repos_files['repos_license_whitelist'][repoid])

        # package masking
        """
        Parser returning packages masked at repository level read from
        packages.db.mask inside the repository database directory.
        """
        for repoid in self.__repos_files['repos_mask']:
            sys_settings_instance.validate_entropy_cache(
                self.__repos_files['repos_mask'][repoid],
                self.__repos_mtime['repos_mask'][repoid], repoid = repoid)

            data['mask'][repoid] = \
                self.entropyTools.generic_file_content_parser(
                    self.__repos_files['repos_mask'][repoid])

        # keywords masking
        """
        Parser returning packages masked at repository level read from
        packages.db.keywords inside the repository database directory.
        """
        for repoid in self.__repos_files['repos_keywords']:
            sys_settings_instance.validate_entropy_cache(
                self.__repos_files['repos_keywords'][repoid],
                self.__repos_mtime['repos_keywords'][repoid], repoid = repoid)

            data['repos_keywords'][repoid] = \
                self.__repositories_repos_keywords(
                    self.__repos_files['repos_keywords'][repoid])

        # system masking
        data['system_mask'] = self.__repositories_system_mask(
            sys_settings_instance)

        # critical updates
        """
        Parser returning critical packages list metadata read from
        packages.db.critical file inside the repository directory.
        This file contains packages that should be always updated
        before anything else.
        """
        for repoid in self.__repos_files['repos_critical_updates']:
            sys_settings_instance.validate_entropy_cache(
                self.__repos_files['repos_critical_updates'][repoid],
                self.__repos_mtime['repos_critical_updates'][repoid],
                repoid = repoid)
            data['critical_updates'][repoid] = \
                self.entropyTools.generic_file_content_parser(
                    self.__repos_files['repos_critical_updates'][repoid])


        # conflicts map
        """
        Parser returning packages that could have been installed because
        they aren't in the same scope, but ending up creating critical
        issues. You can see it as a configurable conflict map.
        """
        # keep priority order
        repoids = [x for x in sys_settings_instance['repositories']['order'] \
            if x in self.__repos_files['conflicting_tagged_packages']]
        for repoid in repoids:
            filepath = self.__repos_files['conflicting_tagged_packages'].get(
                repoid)
            if os.access(filepath, os.R_OK) and os.path.isfile(filepath):
                confl_f = open(filepath, "r")
                content = confl_f.readlines()
                confl_f.close()
                content = [x.strip().rsplit("#", 1)[0].strip().split() for x \
                    in content if not x.startswith("#") and x.strip()]
                for mydata in content:
                    if len(mydata) < 2:
                        continue
                    data['conflicting_tagged_packages'][mydata[0]] = mydata[1:]

        return data

    def misc_parser(self, sys_settings_instance):

        """
        Parses Entropy client system configuration file.

        @return dict data
        """

        data = {
            'filesbackup': etpConst['filesbackup'],
            'forcedupdates': etpConst['forcedupdates'],
            'ignore_spm_downgrades': etpConst['spm']['ignore-spm-downgrades'],
            'collisionprotect': etpConst['collisionprotect'],
            'configprotect': etpConst['configprotect'][:],
            'configprotectmask': etpConst['configprotectmask'][:],
            'configprotectskip': etpConst['configprotectskip'][:],
        }

        cli_conf = etpConst['clientconf']
        if not (os.path.isfile(cli_conf) and os.access(cli_conf, os.R_OK)):
            return data

        client_f = open(cli_conf, "r")
        clientconf = [x.strip() for x in client_f.readlines() if \
            x.strip() and not x.strip().startswith("#")]
        client_f.close()
        for line in clientconf:

            split_line = line.split("|")
            split_line_len = len(split_line)

            if line.startswith("filesbackup|") and (split_line_len == 2):

                compatopt = split_line[1].strip().lower()
                if compatopt in ("disable", "disabled", "false", "0", "no",):
                    data['filesbackup'] = False

            if line.startswith("forcedupdates|") and (split_line_len == 2):

                compatopt = split_line[1].strip().lower()
                if compatopt in ("disable", "disabled", "false", "0", "no",):
                    data['forcedupdates'] = False
                else:
                    data['forcedupdates'] = True

            elif line.startswith("ignore-spm-downgrades|") and \
                (split_line_len == 2):

                compatopt = split_line[1].strip().lower()
                if compatopt in ("enable", "enabled", "true", "1", "yes"):
                    data['ignore_spm_downgrades'] = True

            elif line.startswith("collisionprotect|") and (split_line_len == 2):

                collopt = split_line[1].strip()
                if collopt.lower() in ("0", "1", "2",):
                    data['collisionprotect'] = int(collopt)

            elif line.startswith("configprotect|") and (split_line_len == 2):

                configprotect = split_line[1].strip()
                for myprot in configprotect.split():
                    data['configprotect'].append(
                        const_convert_to_unicode(myprot))

            elif line.startswith("configprotectmask|") and \
                (split_line_len == 2):

                configprotect = split_line[1].strip()
                for myprot in configprotect.split():
                    data['configprotectmask'].append(
                        const_convert_to_unicode(myprot))

            elif line.startswith("configprotectskip|") and \
                (split_line_len == 2):

                configprotect = split_line[1].strip()
                for myprot in configprotect.split():
                    data['configprotectskip'].append(
                        etpConst['systemroot'] + \
                            const_convert_to_unicode(myprot))

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


class Client(Singleton, TextInterface, LoadersMixin, CacheMixin, CalculatorsMixin, \
        RepositoryMixin, MiscMixin, MatchMixin, FetchersMixin, NoticeBoardMixin):

    def init_singleton(self, indexing = True, noclientdb = 0,
            xcache = True, user_xcache = False, repo_validation = True,
            load_ugc = True, url_fetcher = None,
            multiple_url_fetcher = None):

        self._can_run_sys_set_hooks = False
        const_debug_write(__name__, "debug enabled")
        self.sys_settings_client_plugin_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        self.__instance_destroyed = False
        self.atomMatchCacheKey = etpCache['atomMatch']
        self.dbapi2 = dbapi2 # export for third parties
        self.FileUpdates = None
        self.validRepositories = []
        self.UGC = None
        # supporting external updateProgress stuff, you can point self.progress
        # to your progress bar and reimplement updateProgress
        self.progress = None
        self.clientDbconn = None
        self.safe_mode = 0
        self.indexing = indexing
        self.repo_validation = repo_validation
        self.noclientdb = False
        self.openclientdb = True

        # setup package settings (masking and other stuff)
        self.SystemSettings = SystemSettings()
        const_debug_write(__name__, "SystemSettings loaded")

        # modules import
        import entropy.dump as dumpTools
        import entropy.tools as entropyTools
        self.dumpTools = dumpTools
        self.entropyTools = entropyTools
        self.clientLog = LogFile(level = self.SystemSettings['system']['log_level'],
            filename = etpConst['equologfile'], header = "[client]")

        self.MultipleUrlFetcher = multiple_url_fetcher
        self.urlFetcher = url_fetcher
        if self.urlFetcher == None:
            from entropy.transceivers import UrlFetcher
            self.urlFetcher = UrlFetcher
        if self.MultipleUrlFetcher == None:
            from entropy.transceivers import MultipleUrlFetcher
            self.MultipleUrlFetcher = MultipleUrlFetcher

        from entropy.cache import EntropyCacher
        self.Cacher = EntropyCacher()

        from entropy.client.misc import FileUpdates
        self.FileUpdates = FileUpdates(self)

        from entropy.client.mirrors import StatusInterface
        # mirror status interface
        self.MirrorStatus = StatusInterface()

        if noclientdb in (False, 0):
            self.noclientdb = False
        elif noclientdb in (True, 1):
            self.noclientdb = True
        elif noclientdb == 2:
            self.noclientdb = True
            self.openclientdb = False

        # load User Generated Content Interface
        if load_ugc:
            from entropy.client.services.ugc.interfaces import Client as ugc_cl
            self.UGC = ugc_cl(self)

        # class init
        LoadersMixin.__init__(self)

        self.xcache = xcache
        shell_xcache = os.getenv("ETP_NOCACHE")
        if shell_xcache:
            self.xcache = False

        do_validate_repo_cache = False
        # now if we are on live, we should disable it
        # are we running on a livecd? (/proc/cmdline has "cdroot")
        if self.entropyTools.islive():
            self.xcache = False
        elif (not self.entropyTools.is_user_in_entropy_group()) and not user_xcache:
            self.xcache = False
        elif not user_xcache:
            do_validate_repo_cache = True

        if not self.xcache and (self.entropyTools.is_user_in_entropy_group()):
            try:
                self.purge_cache(False)
            except:
                pass

        if self.openclientdb:
            self.open_client_repository()

        # create our SystemSettings plugin
        self.sys_settings_client_plugin = ClientSystemSettingsPlugin(
            self.sys_settings_client_plugin_id, self)

        # needs to be started here otherwise repository cache will be
        # always dropped
        if self.xcache:
            self.Cacher.start()

        if do_validate_repo_cache:
            self.validate_repositories_cache()

        if self.repo_validation:
            self.validate_repositories()
        else:
            self.validRepositories.extend(
                self.SystemSettings['repositories']['order'])

        # add our SystemSettings plugin
        # Make sure we connect Entropy Client plugin AFTER client db init
        self.SystemSettings.add_plugin(self.sys_settings_client_plugin)

        # enable System Settings hooks
        self._can_run_sys_set_hooks = True
        const_debug_write(__name__, "singleton loaded")


    def destroy(self):
        self.__instance_destroyed = True
        if hasattr(self, 'clientDbconn'):
            if self.clientDbconn != None:
                self.clientDbconn.closeDB()
                del self.clientDbconn
        if hasattr(self, 'FileUpdates'):
            del self.FileUpdates
        if hasattr(self, 'clientLog'):
            self.clientLog.close()
        if hasattr(self, 'SystemSettings') and \
            hasattr(self, 'sys_settings_client_plugin_id'):

            if hasattr(self.SystemSettings, 'remove_plugin'):
                try:
                    self.SystemSettings.remove_plugin(
                        self.sys_settings_client_plugin_id)
                except KeyError:
                    pass

        self.close_all_repositories(mask_clear = False)
        self.closeAllSecurity()
        self.closeAllQA()

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
        if not self.clientDbconn:
            # nothing to do if client db is not availabe
            return False

        etpConst['client_treeupdatescalled'].add(repository_identifier)

        doRescan = False
        shell_rescan = os.getenv("ETP_TREEUPDATES_RESCAN")
        if shell_rescan:
            doRescan = True

        # check database digest
        stored_digest = repo_db.retrieveRepositoryUpdatesDigest(
            repository_identifier)
        if stored_digest == -1:
            doRescan = True

        # check stored value in client database
        client_digest = "0"
        if not doRescan:
            client_digest = self.clientDbconn.retrieveRepositoryUpdatesDigest(
                repository_identifier)

        if doRescan or (str(stored_digest) != str(client_digest)) or force:

            # reset database tables
            self.clientDbconn.clearTreeupdatesEntries(repository_identifier)

            # load updates
            update_actions = repo_db.retrieveTreeUpdatesActions(
                repository_identifier)
            # now filter the required actions
            update_actions = self.clientDbconn.filterTreeUpdatesActions(
                update_actions)

            if update_actions:

                mytxt = "%s: %s." % (
                    bold(_("ATTENTION")),
                    red(_("forcing packages metadata update")),
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = darkred(" * ")
                )
                mytxt = "%s %s." % (
                    red(_("Updating system database using repository")),
                    blue(repository_identifier),
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = darkred(" * ")
                )
                # run stuff
                self.clientDbconn.runTreeUpdatesActions(update_actions)

            # store new digest into database
            self.clientDbconn.setRepositoryUpdatesDigest(repository_identifier,
                stored_digest)
            # store new actions
            self.clientDbconn.addRepositoryUpdatesActions(etpConst['clientdbid'],
                update_actions, self.SystemSettings['repositories']['branch'])
            self.clientDbconn.commitChanges()
            # clear client cache
            self.clientDbconn.clearCache()
            return True

    def is_destroyed(self):
        return self.__instance_destroyed

    def __del__(self):
        self.destroy()

