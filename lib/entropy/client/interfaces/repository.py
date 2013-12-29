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
import errno
import time
import threading

from entropy.const import const_debug_write, etpConst, const_file_readable
from entropy.i18n import _, ngettext
from entropy.exceptions import RepositoryError, PermissionDenied
from entropy.output import blue, darkred, red, darkgreen, bold, purple, teal, \
    brown
from entropy.locks import ResourceLock

from entropy.db.exceptions import Error
from entropy.db.skel import EntropyRepositoryBase
from entropy.core.settings.base import SystemSettings

import entropy.tools


class RepositoriesUpdateResourcesLock(ResourceLock):
    """
    Repositories update resource lock that can be used to acquire exclusive
    access to the repositories update process.
    """

    def __init__(self, output=None):
        """
        Object constructor.

        @keyword output: a TextInterface interface
        @type output: entropy.output.TextInterface or None
        """
        super(RepositoriesUpdateResourcesLock, self).__init__(
            output=output)

    def path(self):
        """
        Return the path to the lock file.
        """
        return os.path.join(
            etpConst['entropyrundir'], "." + __name__ + ".lock")


class Repository(object):

    """
    Entropy Client Repositories management interface.
    """

    def __init__(self, entropy_client, repo_identifiers = None,
        force = False, fetch_security = True, gpg = True):
        """
        Entropy Client Repositories management interface constructor.

        @param entropy_client: a valid entropy.client.interfaces.client.Client
            instance
        @type entropy_client: entropy.client.interfaces.client.Client
        @keyword repo_identifiers: list of repository identifiers you want to
            take into consideration
        @type repo_identifiers: list
        @
        """

        if repo_identifiers is None:
            repo_identifiers = []
        self._entropy = entropy_client
        self._settings = SystemSettings()
        self._pkg_size_warning_th = 512*1024000 # 500mb
        repo_ids = repo_identifiers
        self.force = force
        self.sync_errors = False
        self.updated = False
        self.new_entropy = False
        self.need_packages_cleanup = False
        self.updated_repos = set()
        self.fetch_security = fetch_security
        self.already_updated = 0
        self.not_available = 0
        self._gpg_feature = gpg
        env_gpg = os.getenv('ETP_DISBLE_GPG')
        if env_gpg is not None:
            self._gpg_feature = False

        if not repo_ids:
            avail_repos = self._settings['repositories']['available'].keys()
            repo_ids.extend(list(avail_repos))
        # filter out package repositories
        self.repo_ids = self._entropy.filter_repositories(repo_ids)

    def _run_post_update_repository_hook(self, repository_id):

        my_repos = self._settings['repositories']
        branch = my_repos['branch']
        avail_data = my_repos['available']
        repo_data = avail_data[repository_id]
        post_update_script = repo_data['post_repo_update_script']
        if post_update_script is None:
            const_debug_write(__name__,
                "_run_post_update_repository_hook: not available")
            return 0

        if not const_file_readable(post_update_script):
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
        sts = EntropyRepositoryBase

        for repo in self.repo_ids:

            try:
                status = self._entropy.get_repository(repo).update(
                    self._entropy, repo, self.force, self._gpg_feature)
            except PermissionDenied:
                status = sts.REPOSITORY_PERMISSION_DENIED_ERROR

            if status == sts.REPOSITORY_ALREADY_UPTODATE:
                self.already_updated = True
            elif status == sts.REPOSITORY_NOT_AVAILABLE:
                self.not_available += 1
            elif status == sts.REPOSITORY_UPDATED_OK:
                self.updated = True
                self.updated_repos.add(repo)
            elif status == sts.REPOSITORY_PERMISSION_DENIED_ERROR:
                self.not_available += 1
                self.sync_errors = True
            else: # fallback
                self.not_available += 1

            if status == sts.REPOSITORY_UPDATED_OK:
                # execute post update repo hook
                self._run_post_update_repository_hook(repo)

        # keep them closed, but trigger schema updates
        self._entropy.close_repositories()
        self._entropy._validate_repositories()
        self._entropy.reopen_installed_repository()
        self._entropy.close_repositories()

        # clean caches, fetch security
        if self.updated:
            self._entropy.clear_cache()
            if self.fetch_security:
                self._update_security_advisories()

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
                        purple(ngettext("there is", "there are", number_of_pkgs)),
                        brown(str(number_of_pkgs)),
                        purple(ngettext("package file that could be removed",
                            "package files that could be removed",
                            number_of_pkgs)),
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

    def _set_last_successful_sync_time(self):
        """
        Store current time to mtime of last successful sync file.
        You can use Repository.get_last_successful_sync_time() for
        retrieval.
        """
        path = os.path.join(etpConst['etpdatabaseclientdir'], ".last_sync")
        with open(path, "w") as sync_f:
            sync_f.flush()

    # Days after when repository is considered old
    REPOSITORY_OLD_DAYS = 10

    @staticmethod
    def get_last_successful_sync_time():
        """
        Get last time (in epoch format) repositories have been
        updated successfully.

        @return: epoch if info is available, or None
        @rtype: float
        """
        path = os.path.join(etpConst['etpdatabaseclientdir'], ".last_sync")
        try:
            return os.path.getmtime(path)
        except OSError as err:
            if err.errno not in (errno.ENOENT, errno.EPERM):
                raise
            return None

    @staticmethod
    def are_repositories_old():
        """
        Return whether repositories are old and should be updated.

        @return: True, if old
        @rtype: bool
        """
        last_t = Repository.get_last_successful_sync_time()
        if last_t is None:
            return True
        delta = abs(time.time() - last_t)
        if delta > (Repository.REPOSITORY_OLD_DAYS * 86400):
            return True
        return False

    def _update_security_advisories(self):
        try:
            sec = self._entropy.Security()
            sec.update()
        except Exception as e:
            entropy.tools.print_traceback(f = self._entropy.logger)
            mytxt = "%s: %s" % (red(_("Advisories fetch error")), e,)
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = darkred(" @@ ")
            )

    def sync(self):
        """
        Start repository synchronization.

        @return: sync status (0 means all good; != 0 means error).
        @rtype: int
        """
        self._entropy.output(
            "%s ..." % (
                darkgreen(_("Repositories synchronization")),
            ),
            importance = 2,
            level = "info",
            header = darkred(" @@ ")
        )

        lock = RepositoriesUpdateResourcesLock(output=self._entropy)
        with lock.exclusive():

            self._entropy.close_repositories()

            rc = self._run_sync()
            if rc:
                return rc

            if self.not_available >= len(self.repo_ids):
                return 2
            elif self.not_available > 0:
                return 1

            self._set_last_successful_sync_time()

        return 0
