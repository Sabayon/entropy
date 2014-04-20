# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Core Interface}.

"""
import os
import shutil
import threading

from entropy.core import Singleton
from entropy.locks import EntropyResourcesLock
from entropy.fetchers import UrlFetcher, MultipleUrlFetcher
from entropy.output import TextInterface, bold, red, darkred, blue
from entropy.qa import QAInterface
from entropy.security import System, Repository as RepositorySecurity
from entropy.spm.plugins.factory import get_default_instance as get_spm, \
    get_default_class as get_spm_default_class

from entropy.client.interfaces.db import InstalledPackagesRepository
from entropy.client.interfaces.dep import CalculatorsMixin
from entropy.client.interfaces.methods import RepositoryMixin, MiscMixin, \
    MatchMixin
from entropy.client.interfaces.package import PackageActionFactory
from entropy.client.interfaces.repository import Repository

from entropy.client.interfaces.settings import ClientSystemSettingsPlugin
from entropy.client.interfaces.sets import Sets

from entropy.client.misc import sharedinstlock, ConfigurationUpdates

from entropy.client.services.interfaces import \
    ClientWebServiceFactory, RepositoryWebServiceFactory

from entropy.const import etpConst, const_debug_write, \
    const_convert_to_unicode, const_setup_perms
from entropy.core.settings.base import SystemSettings
from entropy.misc import LogFile
from entropy.cache import EntropyCacher
from entropy.i18n import _

import entropy.dump
import entropy.dep
import entropy.tools


class Client(Singleton, TextInterface, CalculatorsMixin,
             RepositoryMixin, MiscMixin, MatchMixin):

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
        self.__post_acquire_hook_idx = None
        self.__instance_destroyed = False
        self._repo_error_messages_cache = set()
        self._repodb_cache = {}
        self._repodb_cache_mutex = threading.RLock()
        self._memory_db_instances = {}
        self._real_installed_repository = None
        self._real_installed_repository_lock = threading.RLock()
        self._treeupdates_repos = set()
        self._can_run_sys_set_hooks = False
        const_debug_write(__name__, "debug enabled")

        self.safe_mode = 0
        self._indexing = indexing
        self._repo_validation = repo_validation

        self._real_cacher = None
        self._real_cacher_lock = threading.RLock()

        # setup package settings (masking and other stuff)
        self._real_settings = None
        self._real_settings_lock = threading.RLock()

        self._real_settings_client_plg = None
        self._real_settings_client_plg_lock = threading.RLock()

        self._real_logger = None
        self._real_logger_lock = threading.RLock()

        self._real_enabled_repos = None
        self._real_enabled_repos_lock = threading.RLock()

        self._multiple_url_fetcher = multiple_url_fetcher
        self._url_fetcher = url_fetcher
        if url_fetcher is None:
            self._url_fetcher = UrlFetcher
        if multiple_url_fetcher is None:
            self._multiple_url_fetcher = MultipleUrlFetcher

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

        # now if we are on live, we should disable it
        # are we running on a livecd? (/proc/cmdline has "cdroot")
        if entropy.tools.islive():
            self.xcache = False
        elif (not entropy.tools.is_user_in_entropy_group()) and not user_xcache:
            self.xcache = False

        # Add Entropy Resources Lock post-acquire hook that cleans
        # repository caches.
        hook_ref = EntropyResourcesLock.add_post_acquire_hook(
            self._resources_post_hook)
        self.__post_acquire_hook_idx = hook_ref

        # enable System Settings hooks
        self._can_run_sys_set_hooks = True
        const_debug_write(__name__, "singleton loaded")

    @property
    def _settings(self):
        """
        Return a SystemSettings object instance.
        """
        with self._real_settings_lock:
            if self._real_settings is None:
                self._real_settings = SystemSettings()
                const_debug_write(__name__, "SystemSettings loaded")

                # add our SystemSettings plugin
                # Make sure we connect Entropy Client plugin
                # AFTER client db init
                self._real_settings.add_plugin(
                    self._settings_client_plugin)

        return self._real_settings

    @property
    def _settings_client_plugin(self):
        """
        Return the SystemSettings Entropy Client plugin.
        """
        with self._real_settings_client_plg_lock:
            if self._real_settings_client_plg is None:
                plugin = ClientSystemSettingsPlugin(self)
                self._real_settings_client_plg = plugin

        return self._real_settings_client_plg

    @property
    def _cacher(self):
        """
        Return an EntropyCacher object instance.
        """
        with self._real_cacher_lock:

            if self._real_cacher is None:
                real_cacher = EntropyCacher()
                const_debug_write(__name__, "EntropyCacher loaded")

                # needs to be started here otherwise repository
                # cache will be always dropped
                if self.xcache:
                    real_cacher.start()
                else:
                    # disable STASHING_CACHE or we leak
                    EntropyCacher.STASHING_CACHE = False

                self._real_cacher = real_cacher

        return self._real_cacher

    @property
    def logger(self):
        """
        Return the Entropy Client Logger instance.
        """
        with self._real_logger_lock:
            if self._real_logger is None:
                real_logger = LogFile(
                    level = self._settings['system']['log_level'],
                    filename = etpConst['entropylogfile'],
                    header = "[client]")

                const_debug_write(__name__, "Logger loaded")
                self._real_logger = real_logger

        return self._real_logger

    @property
    def _enabled_repos(self):
        with self._real_enabled_repos_lock:

            if self._real_enabled_repos is None:
                real_enabled_repos = []

                if self._repo_validation:
                    self._validate_repositories(
                        enabled_repos = real_enabled_repos)
                else:
                    real_enabled_repos.extend(
                        self._settings['repositories']['order'])

                self._real_enabled_repos = real_enabled_repos

        return self._real_enabled_repos

    def _resources_post_hook(self):
        """
        Hook running after Entropy Resources Lock acquisition.
        This method takes care of the repository memory caches, by
        invalidating it.
        """
        with self._real_installed_repository_lock:
            if self._real_installed_repository is not None:
                self._real_installed_repository.clearCache()

        with self._repodb_cache_mutex:
            for repo in self._repodb_cache.values():
                repo.clearCache()

    def destroy(self, _from_shutdown = False):
        """
        Destroy this Singleton instance, closing repositories, removing
        SystemSettings plugins added during instance initialization.
        This method should be always called when instance is not used anymore.
        """
        self.__instance_destroyed = True

        if self.__post_acquire_hook_idx is not None:
            EntropyResourcesLock.remove_post_acquire_hook(
                self.__post_acquire_hook_idx)
            self.__post_acquire_hook_idx = None

        if hasattr(self, '_installed_repository'):
            inst_repo = self.installed_repository()
            if inst_repo is not None:
                inst_repo.close(_token = InstalledPackagesRepository.NAME)

        if hasattr(self, '_real_logger_lock'):
            with self._real_logger_lock:
                if self._real_logger is not None:
                    self._real_logger.close()

        if not _from_shutdown:
            if hasattr(self, '_real_settings') and \
                    hasattr(self._real_settings, 'remove_plugin'):

                # shutdown() will terminate the whole process
                # so there is no need to remove plugins from
                # SystemSettings, it wouldn't make any diff.
                if self._real_settings is not None:
                    try:
                        self._real_settings.remove_plugin(
                            ClientSystemSettingsPlugin.ID)
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

    @sharedinstlock
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
        inst_repo = self.installed_repository()

        if not inst_repo:
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
                inst_repo.retrieveRepositoryUpdatesDigest(
                    repository_identifier)

        if do_rescan or (str(stored_digest) != str(client_digest)) or force:

            # reset database tables
            inst_repo.clearTreeupdatesEntries(
                repository_identifier)

            # load updates
            update_actions = repo_db.retrieveTreeUpdatesActions(
                repository_identifier)
            # now filter the required actions
            update_actions = inst_repo.filterTreeUpdatesActions(
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
                inst_repo.runTreeUpdatesActions(
                    update_actions)

            # store new digest into database
            inst_repo.setRepositoryUpdatesDigest(
                repository_identifier, stored_digest)
            # store new actions
            inst_repo.addRepositoryUpdatesActions(
                InstalledPackagesRepository.NAME, update_actions,
                    self._settings['repositories']['branch'])
            inst_repo.commit()
            # clear client cache
            inst_repo.clearCache()
            return True

    def is_destroyed(self):
        return self.__instance_destroyed

    def clear_cache(self):
        """
        Clear all the Entropy default cache directory. This function is
        fault tolerant and will never return any exception.
        """
        with self._cacher:
            # no data is written while holding self._cacher by the balls
            # drop all the buffers then remove on-disk data
            self._cacher.discard()
            # clear repositories live cache
            inst_repo = self.installed_repository()
            if inst_repo is not None:
                inst_repo.clearCache()
            with self._repodb_cache_mutex:
                for repo in self._repodb_cache.values():
                    repo.clearCache()

            cache_dir = self._cacher.current_directory()
            try:
                shutil.rmtree(cache_dir, True)
            except (shutil.Error, IOError, OSError):
                return
            try:
                os.makedirs(cache_dir, 0o775)
            except (IOError, OSError):
                return
            try:
                const_setup_perms(cache_dir, etpConst['entropygid'])
            except (IOError, OSError):
                return

    def QA(self):
        """
        Load Entropy QA interface object

        @rtype: entropy.qa.QAInterface
        """
        qa_intf = QAInterface()
        qa_intf.output = self.output
        qa_intf.ask_question = self.ask_question
        qa_intf.input_box = self.input_box
        qa_intf.set_title = self.set_title
        return qa_intf

    def Settings(self):
        """
        Return SystemSettings instance object
        """
        return self._settings

    def ClientSettings(self):
        """
        Return SystemSettings Entropy Client plugin metadata dictionary
        """
        p_id = ClientSystemSettingsPlugin.ID
        return self._settings[p_id]

    def Cacher(self):
        """
        Return EntropyCacher instance object

        @return: EntropyCacher instance object
        @rtype: entropy.cache.EntropyCacher
        """
        return self._cacher

    def PackageActionFactory(self):
        """
        Load Entropy PackageActionFactory instance object
        """
        return PackageActionFactory(self)

    def ConfigurationUpdates(self):
        """
        Return Entropy Configuration File Updates management object.
        """
        return ConfigurationUpdates(self)

    def Spm(self):
        """
        Load Source Package Manager instance object
        """
        return get_spm(self)

    def Spm_class(self):
        """
        Load Source Package Manager default plugin class
        """
        return get_spm_default_class()

    def Repositories(self, *args, **kwargs):
        """
        Load Entropy Repositories manager instance object

        @return: Repository instance object
        @rtype: entropy.client.interfaces.repository.Repository
        """
        client_data = self.ClientSettings()['misc']
        kwargs['gpg'] = client_data['gpg']
        return Repository(self, *args, **kwargs)

    def Security(self, *args, **kwargs):
        """
        Load Entropy Security Advisories interface object

        @return: Repository Security instance object
        @rtype: entropy.security.System
        """
        return System(self, *args, **kwargs)

    def RepositorySecurity(self, keystore_dir = None):
        """
        Load Entropy Repository Security interface object

        @return: Repository Repository Security instance object
        @rtype: entropy.security.Repository
        @raise RepositorySecurity.GPGError: GPGError based instances in case
            of problems.
        """
        if keystore_dir is None:
            keystore_dir = etpConst['etpclientgpgdir']
        return RepositorySecurity(keystore_dir = keystore_dir)

    def Sets(self):
        """
        Load Package Sets interface object

        @return: Sets instance object
        @rtype: entropy.client.interfaces.sets.Sets
        """
        return Sets(self)

    def WebServices(self):
        """
        Load the Entropy Web Services Factory interface, that can be used
        to obtain a WebService object that is able to communicate with
        repository remote services, if available.

        @return: WebServicesFactory instance object
        @rtype: entropy.client.services.interfaces.WebServicesFactory
        """
        return ClientWebServiceFactory(self)

    def RepositoryWebServices(self):
        """
        Load the Repository Entropy Web Services Factory interface, that can
        be used to obtain a RepositoryWebService object that is able to
        communicate with repository remote services, querying for package
        metadata and general repository status.

        @return: RepositoryWebServiceFactory instance object
        @rtype: entropy.client.services.interfaces.RepositoryWebServiceFactory
        """
        return RepositoryWebServiceFactory(self)
