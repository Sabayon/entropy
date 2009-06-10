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
import sys
from entropy.core import Singleton
from entropy.output import TextInterface
from entropy.db import dbapi2
from entropy.client.interfaces.loaders import LoadersMixin
from entropy.client.interfaces.cache import CacheMixin
from entropy.client.interfaces.dep import CalculatorsMixin
from entropy.client.interfaces.methods import RepositoryMixin, MiscMixin, \
    MatchMixin
from entropy.client.interfaces.fetch import FetchersMixin
from entropy.const import etpConst, etpCache, etpUi, const_debug_write
from entropy.core import SystemSettings, SystemSettingsPlugin
from entropy.misc import LogFile
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

    def masking_validation_parser(self, system_settings_instance):
        data = {
            'cache': {}, # package masking validation cache
        }
        return data

    def misc_parser(self, sys_settings_instance):

        """
        Parses Entropy client system configuration file.

        @return dict data
        """

        data = {
            'filesbackup': etpConst['filesbackup'],
            'ignore_spm_downgrades': etpConst['spm']['ignore-spm-downgrades'],
            'collisionprotect': etpConst['collisionprotect'],
            'configprotect': etpConst['configprotect'][:],
            'configprotectmask': etpConst['configprotectmask'][:],
            'configprotectskip': etpConst['configprotectskip'][:],
        }

        cli_conf = etpConst['clientconf']
        if not (os.path.isfile(cli_conf) and os.access(cli_conf, os.R_OK)):
            return data

        client_f = open(cli_conf,"r")
        clientconf = [x.strip() for x in client_f.readlines() if \
            x.strip() and not x.strip().startswith("#")]
        client_f.close()
        for line in clientconf:

            split_line = line.split("|")
            split_line_len = len(split_line)

            if line.startswith("filesbackup|") and (split_line_len == 2):

                compatopt = split_line[1].strip().lower()
                if compatopt in ("disable", "disabled","false", "0", "no",):
                    data['filesbackup'] = False

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
                        unicode(myprot,'raw_unicode_escape'))

            elif line.startswith("configprotectmask|") and \
                (split_line_len == 2):

                configprotect = split_line[1].strip()
                for myprot in configprotect.split():
                    data['configprotectmask'].append(
                        unicode(myprot,'raw_unicode_escape'))

            elif line.startswith("configprotectskip|") and \
                (split_line_len == 2):

                configprotect = split_line[1].strip()
                for myprot in configprotect.split():
                    data['configprotectskip'].append(
                        etpConst['systemroot']+unicode(myprot,
                            'raw_unicode_escape'))

        return data


class Client(Singleton, TextInterface, LoadersMixin, CacheMixin, CalculatorsMixin, \
        RepositoryMixin, MiscMixin, MatchMixin, FetchersMixin):

    def init_singleton(self, indexing = True, noclientdb = 0,
            xcache = True, user_xcache = False, repo_validation = True,
            load_ugc = True, url_fetcher = None,
            multiple_url_fetcher = None):

        const_debug_write(__name__, "debug enabled")
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
        else:
            self.validRepositories.extend(
                self.SystemSettings['repositories']['order'])

        const_debug_write(__name__, "singleton loaded")

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
                try:
                    self.SystemSettings.remove_plugin(
                        self.sys_settings_client_plugin_id)
                except KeyError:
                    pass

        self.close_all_repositories(mask_clear = False)
        self.closeAllSecurity()
        self.closeAllQA()

    def is_destroyed(self):
        return self.__instance_destroyed

    def __del__(self):
        self.destroy()

