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
from entropy.db.exceptions import OperationalError, DatabaseError, \
    Error as EntropyRepositoryError


class CacheMixin:

    def _get_available_packages_hash(self):
        """
        Get available packages cache hash.
        """
        # client digest not needed, cache is kept updated
        c_hash = "%s|%s|%s" % (
            self._repositories_hash(),
            self.filter_repositories(self.repositories()),
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self._settings['repositories']['branch'])
        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring(repr(c_hash)))
        return sha.hexdigest()

    def _repositories_hash(self):
        """
        Return the checksum of all the available repositories, including
        package repos.
        """
        repository_ids = self.repositories()
        sha = hashlib.sha1()

        sha.update(const_convert_to_rawstring(",".join(repository_ids)))
        sha.update(const_convert_to_rawstring("-begin-"))

        for repository_id in repository_ids:

            mtime = None
            checksum = None

            try:
                repo = self.open_repository(repository_id)
            except RepositoryError:
                repo = None

            if repo is not None:
                try:
                    mtime = repo.mtime()
                except (EntropyRepositoryError, OSError, IOError):
                    pass

                try:
                    checksum = repo.checksum()
                except EntropyRepositoryError:
                    pass

            cache_s = "{%s:{%r;%s}}" % (repository_id, mtime, checksum)
            sha.update(const_convert_to_unicode(cache_s))

        sha.update(const_convert_to_rawstring("-end-"))

        return sha.hexdigest()
