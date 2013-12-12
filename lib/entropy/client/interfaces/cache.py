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

    def _get_available_packages_hash(self):
        """
        Get available packages cache hash.
        """
        # client digest not needed, cache is kept updated
        c_hash = "%s|%s|%s" % (
            self._repositories_hash(),
            self._filter_available_repositories(),
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self._settings['repositories']['branch'])
        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring(repr(c_hash)))
        return sha.hexdigest()

    def _repositories_hash(self):
        """
        Return the checksum of available repositories, excluding package ones.
        """
        enabled_repos = self._filter_available_repositories()
        return self.__repositories_hash(enabled_repos)

    def __repositories_hash(self, repositories):
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

    def _all_repositories_hash(self):
        """
        Return the checksum of all the available repositories, including
        package repos.
        """
        return self.__repositories_hash(self._enabled_repos)

    def _get_available_packages_cache(self, chash):
        """
        Return the on-disk cached object for all the available packages.

        @param chash: cache hash
        @type chash: string
        @return: list of available packages (if cache hit) otherwise None
        @rtype: list or None
        """
        return self._cacher.pop("%s%s" % (
            EntropyCacher.CACHE_IDS['world_available'], chash))

    def _get_updates_cache(self, empty_deps, repo_hash = None):
        """
        Get available updates on-disk cache, if available, otherwise return None
        """
        misc_settings = self.ClientSettings()['misc']
        ignore_spm_downgrades = misc_settings['ignore_spm_downgrades']

        if self.xcache:

            if repo_hash is None:
                repo_hash = self._repositories_hash()

            c_hash = self._get_updates_cache_hash(repo_hash, empty_deps,
                ignore_spm_downgrades)

            disk_cache = self._cacher.pop(c_hash)
            if isinstance(disk_cache, tuple):
                return disk_cache

    def _filter_available_repositories(self, _enabled_repos = None):
        """
        Filter out package repositories from the list of available,
        enabled ones

        @keyword _enabled_repos: an alternative list of enabled repository
            identifiers
        @type _enabled_repos: list
        """
        if _enabled_repos is None:
            _enabled_repos = self._enabled_repos
        enabled_repos = [x for x in _enabled_repos if not \
            x.endswith(etpConst['packagesext_webinstall'])]
        enabled_repos = [x for x in enabled_repos if not \
            x.endswith(etpConst['packagesext'])]
        return enabled_repos

    def _get_updates_cache_hash(self, repo_hash, empty_deps,
        ignore_spm_downgrades):
        """
        Get package updates cache hash that can be used to retrieve the on-disk
        cached object.
        """
        enabled_repos = self._filter_available_repositories()
        repo_order = [x for x in self._settings['repositories']['order'] if
            x in enabled_repos]

        inst_repo = self.installed_repository()

        cache_s = "%s|%s|%s|%s|%s|%s|%s|%s|%s|v3" % (
            repo_hash,
            empty_deps,
            enabled_repos,
            inst_repo.checksum(),
            self._all_repositories_hash(),
            ";".join(sorted(self._settings['repositories']['available'])),
            repo_order,
            ignore_spm_downgrades,
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self._settings['repositories']['branch'],
        )
        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring(cache_s))
        return "%s%s" % (
            EntropyCacher.CACHE_IDS['world_update'],
            sha.hexdigest(),)

    def _get_critical_updates_cache(self, repo_hash = None):
        """
        Get critical package updates cache object, if available, otherwise
        return None.
        """
        if self.xcache:
            if repo_hash is None:
                repo_hash = self._repositories_hash()
            c_hash = "%s%s" % (
                EntropyCacher.CACHE_IDS['critical_update'],
                self._get_critical_update_cache_hash(repo_hash),)

            return self._cacher.pop(c_hash)

    def _get_critical_update_cache_hash(self, repo_hash):
        """
        Get critical package updates cache hash that can be used to retrieve
        the on-disk cached object.
        """
        inst_repo = self.installed_repository()

        enabled_repos = self._filter_available_repositories()
        repo_order = [x for x in self._settings['repositories']['order'] if
            x in enabled_repos]

        c_hash = "%s|%s|%s|%s|%s|%s|%s|v2" % (
            repo_hash,
            enabled_repos,
            inst_repo.checksum(),
            self._all_repositories_hash(),
            ";".join(sorted(self._settings['repositories']['available'])),
            repo_order,
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self._settings['repositories']['branch'],
        )
        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring(repr(c_hash)))
        return sha.hexdigest()
