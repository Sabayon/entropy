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
        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring("0"))

        for repo in self.repositories():
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
