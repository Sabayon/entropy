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

from entropy.const import const_debug_write, etpConst
from entropy.i18n import _
from entropy.exceptions import RepositoryError, PermissionDenied
from entropy.output import blue, darkred, red, darkgreen, bold, purple, teal, \
    brown

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
        self._entropy = entropy_client_instance
        self._settings = SystemSettings()
        self._pkg_size_warning_th = 512*1024000 # 500mb
        self.repo_ids = repo_identifiers
        self.force = force
        self.sync_errors = False
        self.updated = False
        self.new_entropy = False
        self.need_packages_cleanup = False
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

    def _run_post_update_repository_hook(self, repository_id):

        my_repos = self._settings['repositories']
        branch = my_repos['branch']
        avail_data = my_repos['available']
        repo_data = avail_data[repository_id]
        post_update_script = repo_data['post_repo_update_script']

        if not (os.path.isfile(post_update_script) and \
            os.access(post_update_script, os.R_OK)):
            # not found!
            const_debug_write(__name__,
                "_run_post_update_repository_hook: not found")
            return 0

        args = ["/bin/sh", post_update_script, repository_id,
            etpConst['systemroot'] + os.path.sep, branch]
        const_debug_write(__name__,
            "_run_post_update_repository_hook: run: %s" % (args,))
        proc = subprocess.Popen(args, stdin = sys.stdin,
            stdout = sys.stdout, stderr = sys.stderr)
        # it is possible to ignore errors because
        # if it's a critical thing, upstream dev just have to fix
        # the script and will be automagically re-run
        br_rc = proc.wait()
        const_debug_write(__name__,
            "_run_post_update_repository_hook: rc: %s" % (br_rc,))

        return br_rc

    def _run_sync(self):

        self.updated = False
        for repo in self.repo_ids:

            # handle
            try:
                status = self._entropy.get_repository(repo).update(self._entropy,
                    repo, self.force, self._gpg_feature)
            except PermissionDenied:
                status = EntropyRepositoryBase.REPOSITORY_PERMISSION_DENIED_ERROR

            if status == EntropyRepositoryBase.REPOSITORY_ALREADY_UPTODATE:
                self.already_updated = True
            elif status == EntropyRepositoryBase.REPOSITORY_NOT_AVAILABLE:
                self.not_available += 1
            elif status == EntropyRepositoryBase.REPOSITORY_UPDATED_OK:
                self.updated = True
                self.updated_repos.add(repo)
            elif status == EntropyRepositoryBase.REPOSITORY_PERMISSION_DENIED_ERROR:
                self.not_available += 1
                self.sync_errors = True
            else: # fallback
                self.not_available += 1

            if status == EntropyRepositoryBase.REPOSITORY_UPDATED_OK:
                # execute post update repo hook
                self._run_post_update_repository_hook(repo)

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

        if self.updated:
            pkgs = self._entropy.clean_downloaded_packages(dry_run = True)
            number_of_pkgs = len(pkgs)
            if number_of_pkgs > 0:
                pkgs_size = entropy.tools.sum_file_sizes(pkgs)
                if pkgs_size > self._pkg_size_warning_th:
                    self.need_packages_cleanup = True
                    pkg_dirs = set((os.path.dirname(x) for x in pkgs))
                    human_size = entropy.tools.bytes_into_human(pkgs_size)
                    mytxt = "%s: %s %s %s." % (
                        teal("Packages"),
                        purple(_("there are")),
                        brown(str(number_of_pkgs)),
                        purple(_("package files that could be removed")),
                    )
                    self._entropy.output(
                        mytxt,
                        importance = 1,
                        level = "info",
                        header = bold(" !!! ")
                    )
                    mytxt = "%s %s. %s:" % (
                        teal("They are taking up to"),
                        brown(human_size),
                        purple(_("Packages are stored in")),
                    )
                    self._entropy.output(
                        mytxt,
                        importance = 1,
                        level = "info",
                        header = bold(" !!! ")
                    )
                    for pkg_dir in pkg_dirs:
                        self._entropy.output(
                            brown(pkg_dir),
                            importance = 1,
                            level = "info",
                            header = bold("     ")
                        )

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
