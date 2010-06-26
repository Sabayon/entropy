# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Repositories Management Interface}.

"""

import os
import sys
import subprocess

from entropy.i18n import _
from entropy.const import etpConst, const_debug_write
from entropy.exceptions import RepositoryError
from entropy.output import blue, darkred, red, darkgreen, bold

from entropy.db.exceptions import Error
from entropy.db.skel import EntropyRepositoryBase
from entropy.core.settings.base import SystemSettings

import entropy.tools

class Repository:

    def __init__(self, entropy_client_instance, repo_identifiers = None,
        force = False, entropy_updates_alert = True, fetch_security = True,
        gpg = True):

        if repo_identifiers is None:
            repo_identifiers = []

        from entropy.client.interfaces import Client
        if not isinstance(entropy_client_instance, Client):
            mytxt = "A valid Entropy Client instance or subclass is needed"
            raise AttributeError(mytxt)

        self._entropy = entropy_client_instance
        self._settings = SystemSettings()
        self.repo_ids = repo_identifiers
        self.force = force
        self.sync_errors = False
        self.updated = False
        self.new_entropy = False
        self.updated_repos = set()
        self.fetch_security = fetch_security
        self.entropy_updates_alert = entropy_updates_alert
        self.already_updated = 0
        self.not_available = 0
        self._gpg_feature = gpg
        env_gpg = os.getenv('ETP_DISBLE_GPG')
        if env_gpg is not None:
            self._gpg_feature = False

        avail_data = self._settings['repositories']['available']
        if not self.repo_ids:
            self.repo_ids.extend(list(avail_data.keys()))

    def _run_sync(self):

        self.updated = False
        repolength = len(self.repo_ids)
        for repo in self.repo_ids:

            # handle
            status = self._entropy.get_repository(repo).update(self._entropy,
                repo, self.force, self._gpg_feature)
            if status == EntropyRepositoryBase.REPOSITORY_ALREADY_UPTODATE:
                self.already_updated = True
            elif status == EntropyRepositoryBase.REPOSITORY_NOT_AVAILABLE:
                self.not_available += 1
            elif status == EntropyRepositoryBase.REPOSITORY_UPDATED_OK:
                self.updated = True
                self.updated_repos.add(repo)

        # keep them closed
        self._entropy.close_repositories()
        self._entropy._validate_repositories()
        self._entropy.close_repositories()

        # clean caches, fetch security
        if self.updated:
            self._entropy.clear_cache()
            if self.fetch_security:
                self._update_security_advisories()
            # do treeupdates
            if isinstance(self._entropy.installed_repository(),
                EntropyRepositoryBase) and entropy.tools.is_root():
                # only as root due to bad SPM
                for repo in self.repo_ids:
                    try:
                        dbc = self._entropy.open_repository(repo)
                    except RepositoryError:
                        # download failed and repo is not available, skip!
                        continue
                    try:
                        self._entropy.repository_packages_spm_sync(repo, dbc)
                    except Error:
                        # EntropyRepository error, missing table?
                        continue
                self._entropy.close_repositories()

        if self.sync_errors:
            self._entropy.output(
                red(_("Something bad happened. Please have a look.")),
                importance = 1,
                level = "warning",
                header = darkred(" @@ ")
            )
            self.sync_errors = True
            return 128

        if self.entropy_updates_alert:
            self._check_entropy_updates()

        return 0

    def _check_entropy_updates(self):
        rc = False
        if self.entropy_updates_alert:
            try:
                rc, pkg_match = self._entropy.check_package_update(
                    "sys-apps/entropy", deep = True)
            except:
                pass
        if rc:
            self.new_entropy = True
            mytxt = "%s: %s. %s." % (
                bold("Entropy"),
                blue(_("a new release is available")),
                darkred(_("Mind to install it before any other package")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "info",
                header = bold(" !!! ")
            )

    def _update_security_advisories(self):
        # update Security Advisories
        try:
            security_intf = self._entropy.Security()
            security_intf.sync()
        except Exception as e:
            entropy.tools.print_traceback(f = self._entropy.clientLog)
            mytxt = "%s: %s" % (red(_("Advisories fetch error")), e,)
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = darkred(" @@ ")
            )

    def sync(self):

        # close them
        self._entropy.close_repositories()

        # let's dance!
        mytxt = darkgreen("%s ...") % (_("Repositories synchronization"),)
        self._entropy.output(
            mytxt,
            importance = 2,
            level = "info",
            header = darkred(" @@ ")
        )

        gave_up = self._entropy.wait_resources()
        if gave_up:
            return 3

        locked = self._entropy.another_entropy_running()
        if locked:
            self._entropy.output(
                red(_("Another Entropy is currently running.")),
                importance = 1,
                level = "error",
                header = darkred(" @@ ")
            )
            return 4

        # lock
        acquired = self._entropy.lock_resources()
        if not acquired:
            return 4 # app locked during lock acquire
        try:
            rc = self._run_sync()
            if rc:
                return rc
        finally:
            self._entropy.unlock_resources()

        if (self.not_available >= len(self.repo_ids)):
            return 2
        elif (self.not_available > 0):
            return 1

        return 0
