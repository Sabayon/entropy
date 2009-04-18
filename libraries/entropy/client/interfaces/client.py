# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

from __future__ import with_statement
import os
from entropy.core import Singleton
from entropy.output import TextInterface
from entropy.db import dbapi2
from entropy.client.interfaces.loaders import LoadersMixin
from entropy.client.interfaces.cache import CacheMixin
from entropy.client.interfaces.dep import CalculatorsMixin
from entropy.client.interfaces.methods import RepositoryMixin, MiscMixin, \
    MatchMixin
from entropy.client.interfaces.fetch import FetchersMixin
from entropy.client.interfaces.metadata import ExtractorsMixin
from entropy.const import etpConst, etpCache
from entropy.core import SystemSettings, SystemSettingsPlugin
from entropy.exceptions import SystemDatabaseError, RepositoryError

class ClientSystemSettingsPlugin(SystemSettingsPlugin):

    import entropy.tools as entropyTools

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
            m_list = system_settings_instance['repos_system_mask'] + \
                system_settings_instance['system_mask']
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

    def repo_setup_parser(self, system_settings_instance):

        # this makes sure that repository metadata is initialized
        # in fact, CONFIG_PROTECT and CONFIG_PROTECT_MASK are stored
        # inside the database.
        # We won't care about load errors since db will be always
        # initialized
        avail_repos = system_settings_instance['repositories']['available']
        for repoid in avail_repos:
            if not self._helper.is_repository_connection_cached(repoid):
                continue
            try:
                dbconn = self._helper.open_repository(repoid)
                self._helper.setup_repository_config(repoid, dbconn)
            except RepositoryError:
                pass

class Client(Singleton, TextInterface, LoadersMixin, CacheMixin, CalculatorsMixin, \
        RepositoryMixin, MiscMixin, MatchMixin, FetchersMixin, ExtractorsMixin):

    def init_singleton(self, indexing = True, noclientdb = 0,
            xcache = True, user_xcache = False, repo_validation = True,
            load_ugc = True, url_fetcher = None,
            multiple_url_fetcher = None):

        self.__instance_destroyed = False
        self.atomMatchCacheKey = etpCache['atomMatch']
        self.dbapi2 = dbapi2 # export for third parties
        self.FileUpdates = None
        self._package_match_validator_cache = {}
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

        # modules import
        import entropy.dump as dumpTools
        import entropy.tools as entropyTools
        self.dumpTools = dumpTools
        self.entropyTools = entropyTools
        from entropy.misc import LogFile
        self.clientLog = LogFile(level = self.SystemSettings['system']['log_level'],
            filename = etpConst['equologfile'], header = "[client]")

        self.MultipleUrlFetcher = multiple_url_fetcher
        self.urlFetcher = url_fetcher
        if self.urlFetcher == None:
            from entropy.transceivers import urlFetcher
            self.urlFetcher = urlFetcher
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

        if noclientdb in (False,0):
            self.noclientdb = False
        elif noclientdb in (True,1):
            self.noclientdb = True
        elif noclientdb == 2:
            self.noclientdb = True
            self.openclientdb = False

        # load User Generated Content Interface
        if load_ugc:
            from entropy.client.services.ugc.interfaces import Client as ugcClient
            self.UGC = ugcClient(self)

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
        self.sys_settings_client_plugin_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        self.sys_settings_client_plugin = ClientSystemSettingsPlugin(
            self.sys_settings_client_plugin_id, self)
        # Make sure we connect Entropy Client plugin AFTER client db init
        self.SystemSettings.add_plugin(self.sys_settings_client_plugin)

        # needs to be started here otherwise repository cache will be
        # always dropped
        if self.xcache:
            self.Cacher.start()

        if do_validate_repo_cache:
            self.validate_repositories_cache()
        if self.repo_validation:
            self.validate_repositories()

    def destroy(self):
        self.__instance_destroyed = True
        if hasattr(self,'clientDbconn'):
            if self.clientDbconn != None:
                self.clientDbconn.closeDB()
                del self.clientDbconn
        if hasattr(self,'FileUpdates'):
            del self.FileUpdates
        if hasattr(self,'clientLog'):
            self.clientLog.close()
        if hasattr(self,'Cacher'):
            self.Cacher.stop()
        if hasattr(self,'SystemSettings') and \
            hasattr(self,'sys_settings_client_plugin_id'):

            if hasattr(self.SystemSettings,'remove_plugin'):
                self.SystemSettings.remove_plugin(
                    self.sys_settings_client_plugin_id)

        self.close_all_repositories(mask_clear = False)
        self.closeAllSecurity()
        self.closeAllQA()

    def is_destroyed(self):
        return self.__instance_destroyed

    def __del__(self):
        self.destroy()

