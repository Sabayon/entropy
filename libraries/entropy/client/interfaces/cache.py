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
from entropy.const import *
from entropy.exceptions import *
from entropy.output import red, darkred, darkgreen
from entropy.i18n import _

class CacheMixin:

    def validate_repositories_cache(self):
        # is the list of repos changed?
        cached = self.Cacher.pop(etpCache['repolist'])
        if cached == None:
            # invalidate matching cache
            try:
                self.repository_move_clear_cache()
            except IOError:
                pass
        elif isinstance(cached,tuple):
            difflist = [x for x in cached if x not in \
                self.SystemSettings['repositories']['order']]
            for repoid in difflist:
                try: self.repository_move_clear_cache(repoid)
                except IOError: pass
        self.store_repository_list_cache()

    def store_repository_list_cache(self):
        self.Cacher.push(etpCache['repolist'],
            tuple(self.SystemSettings['repositories']['order']),
            async = False)

    def generate_cache(self, depcache = True, configcache = True,
        client_purge = True, install_queue = True):

        # clean first of all
        self.purge_cache(client_purge = client_purge)
        if depcache:
            self.do_depcache(do_install_queue = install_queue)
        if configcache:
            self.do_configcache()

    def do_configcache(self):
        self.updateProgress(
            darkred(_("Configuration files")),
            importance = 2,
            type = "warning"
        )
        self.updateProgress(
            red(_("Scanning hard disk")),
            importance = 1,
            type = "warning"
        )
        self.FileUpdates.scanfs(dcache = False, quiet = True)
        self.updateProgress(
            darkred(_("Cache generation complete.")),
            importance = 2,
            type = "info"
        )

    def do_depcache(self, do_install_queue = True):

        self.updateProgress(
            darkgreen(_("Resolving metadata")),
            importance = 1,
            type = "warning"
        )
        # we can barely ignore any exception from here
        # especially cases where client db does not exist
        try:
            update, remove, fine, spm_fine = self.calculate_world_updates()
            del fine, spm_fine, remove
            if do_install_queue:
                self.get_install_queue(update, False, False)
            self.calculate_available_packages()
        except: # except SystemDatabaseError @ calculate_world_updates
            pass

        self.updateProgress(
            darkred(_("Dependencies cache filled.")),
            importance = 2,
            type = "warning"
        )

    def purge_cache(self, showProgress = True, client_purge = True):
        if self.entropyTools.is_user_in_entropy_group():
            self.Cacher.stop()
            try:
                skip = set()
                if not client_purge:
                    skip.add("/"+etpCache['dbMatch']+"/"+etpConst['clientdbid']) # it's ok this way
                    skip.add("/"+etpCache['dbSearch']+"/"+etpConst['clientdbid']) # it's ok this way
                for key in etpCache:
                    if showProgress:
                        self.updateProgress(
                            darkred(_("Cleaning %s => dumps...")) % (etpCache[key],),
                            importance = 1,
                            type = "warning",
                            back = True
                        )
                    self.clear_dump_cache(etpCache[key], skip = skip)

                if showProgress:
                    self.updateProgress(
                        darkgreen(_("Cache is now empty.")),
                        importance = 2,
                        type = "info"
                    )
            finally:
                self.Cacher.start()

    def clear_dump_cache(self, dump_name, skip = []):
        self.Cacher.discard()
        self.SystemSettings._clear_dump_cache(dump_name, skip = skip)

    def update_ugc_cache(self, repository):
        if not self.UGC.is_repository_eapi3_aware(repository):
            return None
        status = True

        votes_dict, err_msg = self.UGC.get_all_votes(repository)
        if isinstance(votes_dict,dict):
            self.UGC.UGCCache.save_vote_cache(repository, votes_dict)
        else:
            status = False

        downloads_dict, err_msg = self.UGC.get_all_downloads(repository)
        if isinstance(downloads_dict,dict):
            self.UGC.UGCCache.save_downloads_cache(repository, downloads_dict)
        else:
            status = False
        return status

    def repository_move_clear_cache(self, repoid = None):
        return self.SystemSettings._clear_repository_cache(repoid = repoid)

    def get_available_packages_chash(self):
        # client digest not needed, cache is kept updated
        return str(hash("%s|%s|%s" % (
            self.all_repositories_checksum(),
            self.validRepositories,
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self.SystemSettings['repositories']['branch'],
            )
        ))

    def all_repositories_checksum(self):
        sum_hashes = ''
        for repo in self.validRepositories:
            try:
                dbconn = self.open_repository(repo)
            except (RepositoryError):
                continue # repo not available
            try:
                sum_hashes += dbconn.database_checksum()
            except self.dbapi2.OperationalError:
                pass
        return sum_hashes

    def get_available_packages_cache(self, myhash = None):
        if myhash == None:
            myhash = self.get_available_packages_chash()
        return self.Cacher.pop("%s%s" % (etpCache['world_available'], myhash))

    def get_world_update_cache(self, empty_deps, db_digest = None):

        misc_settings = self.SystemSettings[self.sys_settings_client_plugin_id]['misc']
        ignore_spm_downgrades = misc_settings['ignore_spm_downgrades']

        if self.xcache:

            if db_digest == None:
                db_digest = self.all_repositories_checksum()

            c_hash = "%s%s" % (etpCache['world_update'],
                self.get_world_update_cache_hash(db_digest, empty_deps,
                    ignore_spm_downgrades),)

            disk_cache = self.Cacher.pop(c_hash)
            if isinstance(disk_cache, tuple):
                return disk_cache

    def get_world_update_cache_hash(self, db_digest, empty_deps,
        ignore_spm_downgrades):

        return str(hash("%s|%s|%s|%s|%s|%s" % (
            db_digest, empty_deps, self.validRepositories,
            self.SystemSettings['repositories']['order'],
            ignore_spm_downgrades,
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self.SystemSettings['repositories']['branch'],
        )))

    def get_critical_updates_cache(self, db_digest = None):

        if self.xcache:

            if db_digest == None:
                db_digest = self.all_repositories_checksum()

            c_hash = "%s%s" % (etpCache['critical_update'],
                self.get_critical_update_cache_hash(db_digest),)

            return self.Cacher.pop(c_hash)

    def get_critical_update_cache_hash(self, db_digest):

        return str(hash("%s|%s|%s|%s" % (
            db_digest, self.validRepositories,
            self.SystemSettings['repositories']['order'],
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self.SystemSettings['repositories']['branch'],
        )))


