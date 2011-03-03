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
import hashlib

from entropy.i18n import _
from entropy.output import purple
from entropy.const import etpConst, const_setup_perms, \
    const_convert_to_unicode, const_convert_to_rawstring
from entropy.exceptions import RepositoryError
from entropy.cache import EntropyCacher
from entropy.db.exceptions import OperationalError, DatabaseError

class CacheMixin:

    REPO_LIST_CACHE_ID = 'repos/repolist'

    def _validate_repositories_cache(self):
        # is the list of repos changed?
        cached = self._cacher.pop(CacheMixin.REPO_LIST_CACHE_ID)
        if cached != self._settings['repositories']['order']:
            # invalidate matching cache
            try:
                self._settings._clear_repository_cache(repoid = None)
            except IOError:
                pass
            self._store_repository_list_cache()

    def _store_repository_list_cache(self):
        self._cacher.push(CacheMixin.REPO_LIST_CACHE_ID,
            self._settings['repositories']['order'],
            async = False)

    def clear_cache(self):
        started = self._cacher.is_started()
        self._cacher.stop()
        try:
            shutil.rmtree(etpConst['dumpstoragedir'], True)
            os.makedirs(etpConst['dumpstoragedir'], 0o775)
            const_setup_perms(etpConst['dumpstoragedir'],
                etpConst['entropygid'])
            self._clear_repositories_live_cache()
        except (shutil.Error, IOError, OSError,):
            pass # ignore cache purge errors?
        finally:
            if started:
                self._cacher.start()

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

    def is_ugc_cached(self, repository):
        """
        Determine whether User Generated Content cache is available for
        given repository.

        @param repository: Entropy repository identifier
        @type repository: string
        @return: True if available
        @rtype: bool
        """
        down_cache = self.UGC.UGCCache.get_downloads_cache(repository)
        if down_cache is None:
            return False

        vote_cache = self.UGC.UGCCache.get_vote_cache(repository)
        if vote_cache is None:
            return False

        return True

    def _clear_repositories_live_cache(self):
        if self._installed_repository is not None:
            self._installed_repository.clearCache()
        for repo_db in self._repodb_cache.values():
            repo_db.clearCache()

    def _get_available_packages_chash(self):
        # client digest not needed, cache is kept updated
        c_hash = "%s|%s|%s" % (
            self._all_repositories_checksum(),
            self._filter_available_repositories(),
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self._settings['repositories']['branch'])
        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring(repr(c_hash)))
        return sha.hexdigest()

    def _repositories_checksum(self):
        """
        Return the checksum of available repositories, excluding package ones.
        """
        enabled_repos = self._filter_available_repositories()
        return self.__repositories_checksum(enabled_repos)

    def __repositories_checksum(self, repositories):
        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring("0"))
        for repo in repositories:
            try:
                dbconn = self.open_repository(repo)
            except (RepositoryError):
                continue # repo not available
            try:
                sha.update(const_convert_to_rawstring(repr(dbconn.mtime())))
            except (OperationalError, DatabaseError, OSError, IOError):
                txt = _("Repository") + " " + const_convert_to_unicode(repo) \
                    + " " + _("is corrupted") + ". " + \
                    _("Cannot calculate the checksum")
                self.output(
                    purple(txt),
                    importance = 1,
                    level = "warning"
                )
        return sha.hexdigest()

    def _all_repositories_checksum(self):
        """
        Return the checksum of all the available repositories, including
        package repos.
        """
        return self.__repositories_checksum(self._enabled_repos)

    def _get_available_packages_cache(self, myhash = None):
        if myhash is None:
            myhash = self._get_available_packages_chash()
        return self._cacher.pop("%s%s" % (
            EntropyCacher.CACHE_IDS['world_available'], myhash))

    def _get_updates_cache(self, empty_deps, db_digest = None):

        misc_settings = self._settings[self.sys_settings_client_plugin_id]['misc']
        ignore_spm_downgrades = misc_settings['ignore_spm_downgrades']

        if self.xcache:

            if db_digest is None:
                db_digest = self._repositories_checksum()

            c_hash = self._get_updates_cache_hash(db_digest, empty_deps,
                ignore_spm_downgrades)

            disk_cache = self._cacher.pop(c_hash)
            if isinstance(disk_cache, tuple):
                return disk_cache

    def _filter_available_repositories(self):
        """ Filter out package repositories """
        enabled_repos = [x for x in self._enabled_repos if not \
            x.endswith(etpConst['packagesext_webinstall'])]
        enabled_repos = [x for x in enabled_repos if not \
            x.endswith(etpConst['packagesext'])]
        return enabled_repos

    def _get_updates_cache_hash(self, db_digest, empty_deps,
        ignore_spm_downgrades):

        enabled_repos = self._filter_available_repositories()
        repo_order = [x for x in self._settings['repositories']['order'] if
            x in enabled_repos]

        c_hash = "%s|%s|%s|%s|%s|%s" % (
            db_digest, empty_deps, enabled_repos,
            repo_order,
            ignore_spm_downgrades,
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self._settings['repositories']['branch'],
        )
        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring(repr(c_hash)))
        return "%s_%s" % (EntropyCacher.CACHE_IDS['world_update'],
            sha.hexdigest(),)

    def _get_critical_updates_cache(self, db_digest = None):

        if self.xcache:
            if db_digest is None:
                db_digest = self._repositories_checksum()
            c_hash = "%s%s" % (EntropyCacher.CACHE_IDS['critical_update'],
                self._get_critical_update_cache_hash(db_digest),)

            return self._cacher.pop(c_hash)

    def _get_critical_update_cache_hash(self, db_digest):
        enabled_repos = self._filter_available_repositories()
        repo_order = [x for x in self._settings['repositories']['order'] if
            x in enabled_repos]
        c_hash = "%s|%s|%s|%s" % (
            db_digest, enabled_repos,
            repo_order,
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self._settings['repositories']['branch'],
        )
        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring(repr(c_hash)))
        return sha.hexdigest()
