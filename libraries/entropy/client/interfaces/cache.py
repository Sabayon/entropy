# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Cache Interface}.

"""
import os
import shutil
from entropy.const import etpConst, const_setup_perms
from entropy.exceptions import RepositoryError
from entropy.output import red, darkred, darkgreen
from entropy.i18n import _

class CacheMixin:

    REPO_LIST_CACHE_ID = 'repos/repolist'

    def _validate_repositories_cache(self):
        # is the list of repos changed?
        cached = self.Cacher.pop(CacheMixin.REPO_LIST_CACHE_ID)
        if cached != self.SystemSettings['repositories']['order']:
            # invalidate matching cache
            try:
                self.SystemSettings._clear_repository_cache(repoid = None)
            except IOError:
                pass
            self._store_repository_list_cache()

    def _store_repository_list_cache(self):
        self.Cacher.push(CacheMixin.REPO_LIST_CACHE_ID,
            self.SystemSettings['repositories']['order'],
            async = False)

    def _purge_cache(self):
        self.Cacher.stop()
        try:
            shutil.rmtree(etpConst['dumpstoragedir'], True)
            os.makedirs(etpConst['dumpstoragedir'], 0o775)
            const_setup_perms(etpConst['dumpstoragedir'],
                etpConst['entropygid']) 
        except (shutil.Error, IOError):
            pass # ignore cache purge errors?
        finally:
            self.Cacher.start()

    def clear_dump_cache(self, dump_name, skip = None):
        if skip is None:
            skip = []
        self.Cacher.discard()
        self.SystemSettings._clear_dump_cache(dump_name, skip = skip)

    def update_ugc_cache(self, repository):
        if not self.UGC.is_repository_eapi3_aware(repository):
            return None
        status = True

        votes_dict, err_msg = self.UGC.get_all_votes(repository)
        if isinstance(votes_dict, dict):
            self.UGC.UGCCache.save_vote_cache(repository, votes_dict)
        else:
            status = False

        downloads_dict, err_msg = self.UGC.get_all_downloads(repository)
        if isinstance(downloads_dict, dict):
            self.UGC.UGCCache.save_downloads_cache(repository, downloads_dict)
        else:
            status = False
        return status

    def _get_available_packages_chash(self):
        # client digest not needed, cache is kept updated
        return str(hash("%s|%s|%s" % (
            self._all_repositories_checksum(),
            self.validRepositories,
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self.SystemSettings['repositories']['branch'],
            )
        ))

    def _all_repositories_checksum(self):
        sum_hashes = ''
        for repo in self.validRepositories:
            try:
                dbconn = self.open_repository(repo)
            except (RepositoryError):
                continue # repo not available
            try:
                sum_hashes += dbconn.checksum()
            except self.dbapi2.OperationalError:
                pass
        return sum_hashes

    def _get_available_packages_cache(self, myhash = None):
        if myhash is None:
            myhash = self._get_available_packages_chash()
        return self.Cacher.pop("%s%s" % (
            etpConst['cache_ids']['world_available'], myhash))

    def _get_updates_cache(self, empty_deps, db_digest = None):

        misc_settings = self.SystemSettings[self.sys_settings_client_plugin_id]['misc']
        ignore_spm_downgrades = misc_settings['ignore_spm_downgrades']

        if self.xcache:

            if db_digest is None:
                db_digest = self._all_repositories_checksum()

            c_hash = self._get_updates_cache_hash(db_digest, empty_deps,
                ignore_spm_downgrades)

            disk_cache = self.Cacher.pop(c_hash)
            if isinstance(disk_cache, tuple):
                return disk_cache

    def _get_updates_cache_hash(self, db_digest, empty_deps,
        ignore_spm_downgrades):

        c_hash = str(hash("%s|%s|%s|%s|%s|%s" % (
            db_digest, empty_deps, self.validRepositories,
            self.SystemSettings['repositories']['order'],
            ignore_spm_downgrades,
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self.SystemSettings['repositories']['branch'],
        )))
        return "%s%s" % (etpConst['cache_ids']['world_update'], c_hash,)

    def _get_critical_updates_cache(self, db_digest = None):

        if self.xcache:
            if db_digest is None:
                db_digest = self._all_repositories_checksum()
            c_hash = "%s%s" % (etpConst['cache_ids']['critical_update'],
                self._get_critical_update_cache_hash(db_digest),)

            return self.Cacher.pop(c_hash)

    def _get_critical_update_cache_hash(self, db_digest):

        return str(hash("%s|%s|%s|%s" % (
            db_digest, self.validRepositories,
            self.SystemSettings['repositories']['order'],
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self.SystemSettings['repositories']['branch'],
        )))
