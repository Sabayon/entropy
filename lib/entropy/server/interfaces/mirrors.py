# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server Mirrors Interfaces}.

"""
import os
import shutil
import time
import errno
import threading
import multiprocessing
import socket
import codecs
try:
    from Queue import Queue
except ImportError:
    from queue import Queue

from entropy.exceptions import EntropyPackageException
from entropy.output import red, darkgreen, bold, brown, blue, darkred, \
    darkblue, purple, teal
from entropy.const import etpConst, const_get_int, const_get_cpus, \
    const_mkdtemp, const_mkstemp, const_file_readable, const_dir_readable
from entropy.cache import EntropyCacher
from entropy.i18n import _
from entropy.misc import RSS, ParallelTask
from entropy.transceivers import EntropyTransceiver
from entropy.transceivers.uri_handlers.skel import EntropyUriHandler
from entropy.core.settings.base import SystemSettings
from entropy.server.interfaces.db import ServerPackagesRepository

import entropy.tools


class Server(object):

    SYSTEM_SETTINGS_PLG_ID = etpConst['system_settings_plugins_ids']['server_plugin']

    def __init__(self, server, repository_id):

        from entropy.server.transceivers import TransceiverServerHandler
        from entropy.server.interfaces.main import Server as MainServer

        if not isinstance(server, MainServer):
            raise AttributeError("entropy.server.interfaces.main.Server needed")

        self._entropy = server
        self.TransceiverServerHandler = TransceiverServerHandler
        self.Cacher = EntropyCacher()
        self._settings = SystemSettings()


    def _show_interface_status(self, repository_id):
        """
        Print Entropy Server Mirrors interface status.
        """
        mytxt = blue("%s:") % (_("Entropy Server Mirrors Interface loaded"),)
        self._entropy.output(
            mytxt,
            importance = 2,
            level = "info",
            header = red(" @@ ")
        )
        for mirror in self._entropy.remote_repository_mirrors(repository_id):
            mytxt = _("repository mirror")
            mirror = EntropyTransceiver.hide_sensible_data(mirror)
            self._entropy.output(
                "%s: %s" % (purple(mytxt), darkgreen(mirror),),
                importance = 0,
                level = "info",
                header = brown("   # ")
            )
        for mirror in self._entropy.remote_packages_mirrors(repository_id):
            mytxt = _("packages mirror")
            mirror = EntropyTransceiver.hide_sensible_data(mirror)
            self._entropy.output(
                blue("%s: %s") % (teal(mytxt), darkgreen(mirror),),
                importance = 0,
                level = "info",
                header = brown("   # ")
            )

    def _read_remote_file_in_branches(self, repository_id, filename,
        excluded_branches = None):
        """
        Reads a file remotely located in all the available branches, in
        repository directory.

        @param repository_id: repository identifier
        @type repository_id: string
        @param filename: name of the file that should be located inside
            repository database directory
        @type filename: string
        @keyword excluded_branches: list of branch identifiers excluded or None
        @type excluded_branches: list or None
        @return: dictionary with branches as key and raw file content as value:
            {'4': 'abcd\n', '5': 'defg\n'}
        @rtype: dict
        """
        if excluded_branches is None:
            excluded_branches = []

        branch_data = {}
        mirrors = self._entropy.remote_repository_mirrors(repository_id)
        for uri in mirrors:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            self._entropy.output(
                "[%s] %s: %s => %s" % (
                    brown(repository_id),
                    blue(_("looking for file in mirror")),
                    darkgreen(crippled_uri),
                    filename,
                ),
                importance = 1,
                level = "info",
                header = brown(" @@ ")
            )

            # not using override data on purpose (remote url can be
            # overridden...)
            branches_path = self._entropy._get_remote_repository_relative_path(
                repository_id)
            txc = self._entropy.Transceiver(uri)
            txc.set_verbosity(False)

            with txc as handler:

                branches = handler.list_content(branches_path)
                for branch in branches:

                    # is branch excluded ?
                    if branch in excluded_branches:
                        continue

                    if branch_data.get(branch) != None:
                        # already read
                        continue

                    mypath = os.path.join("/", branches_path, branch, filename)
                    if not handler.is_file(mypath):
                        # nothing to do, not a file
                        continue

                    tmp_dir = const_mkdtemp(prefix = "entropy.server")
                    down_path = os.path.join(tmp_dir,
                        os.path.basename(filename))
                    tries = 4
                    success = False
                    while tries:
                        downloaded = handler.download(mypath, down_path)
                        if not downloaded:
                            tries -= 1
                            continue # argh!
                        success = True
                        break

                    if success and os.path.isfile(down_path):
                        enc = etpConst['conf_encoding']
                        with codecs.open(down_path, "r", encoding=enc) \
                                as down_f:
                            branch_data[branch] = down_f.read()

                    shutil.rmtree(tmp_dir, True)

        return branch_data

    def lock_mirrors(self, repository_id, lock, mirrors = None,
        unlock_locally = True, quiet = False):
        """
        Lock remote mirrors for given repository. In this way repository
        will be locked for both Entropy Server and Entropy Client instances.

        @param repository_id: repository identifier
        @type repository_id: string
        @param lock: True, for lock, False for unlock
        @type lock: bool
        @keyword mirrors: provide a list of repository mirrors and override
            the current ones (which are stored inside repository metadata)
        @type mirrors: list
        @keyword unlock_locally: True, if local mirror lock file should be
            handled too (in case of shadow repos local lock file should not
            be touched)
        @type unlock_locally: bool
        @return: True, if action is successfull
        @rtype: bool
        """

        if mirrors is None:
            mirrors = self._entropy.remote_repository_mirrors(repository_id)

        done = True
        for uri in mirrors:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            if not quiet:
                lock_text = _("unlocking")
                if lock:
                    lock_text = _("locking")
                self._entropy.output(
                    "[%s|%s] %s %s" % (
                        brown(repository_id),
                        darkgreen(crippled_uri),
                        bold(lock_text),
                        blue("%s...") % (_("mirror"),),
                    ),
                    importance = 1,
                    level = "info",
                    header = brown(" * "),
                    back = True
                )

            repo_relative = \
                self._entropy._get_override_remote_repository_relative_path(
                    repository_id)
            if repo_relative is None:
                repo_relative = \
                    self._entropy._get_remote_repository_relative_path(
                        repository_id)
            base_path = os.path.join(repo_relative,
                self._settings['repositories']['branch'])
            lock_file = os.path.join(base_path,
                etpConst['etpdatabaselockfile'])

            txc = self._entropy.Transceiver(uri)
            txc.set_verbosity(False)
            if quiet:
                txc.set_silent(True)

            with txc as handler:

                if lock:
                    rc_lock = self._do_mirror_lock(
                        repository_id, uri, handler, quiet = quiet)
                else:
                    rc_lock = self._do_mirror_unlock(
                        repository_id, uri, handler,
                        unlock_locally = unlock_locally,
                        quiet = quiet)

            if not rc_lock:
                done = False

        if done:
            db_taint_file = self._entropy._get_local_repository_taint_file(
                repository_id)
            if os.path.isfile(db_taint_file):
                os.remove(db_taint_file)

        return done


    def lock_mirrors_for_download(self, repository_id, lock,
        mirrors = None, unlock_locally = True, quiet = False):
        """
        This functions makes Entropy clients unable to download the repository
        from given mirrors.

        @param repository_id: repository identifier
        @type repository_id: string
        @param lock: True, for lock, False for unlock
        @type lock: bool
        @keyword mirrors: provide a list of repository mirrors and override
            the current ones (which are stored inside repository metadata)
        @type mirrors: list
        @keyword unlock_locally: True, if local mirror lock file should be
            handled too (in case of shadow repos local lock file should not
            be touched)
        @type unlock_locally: bool
        @return: True, if action is successfull
        @rtype: bool
        """
        if mirrors is None:
            mirrors = self._entropy.remote_repository_mirrors(repository_id)

        done = True
        for uri in mirrors:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            if not quiet:
                lock_text = _("unlocking")
                if lock:
                    lock_text = _("locking")
                self._entropy.output(
                    "[%s|%s] %s %s..." % (
                        blue(repository_id),
                        red(crippled_uri),
                        bold(lock_text),
                        blue(_("mirror for download")),
                    ),
                    importance = 1,
                    level = "info",
                    header = red(" @@ "),
                    back = True
                )

            lock_file = etpConst['etpdatabasedownloadlockfile']
            repo_relative = \
                self._entropy._get_override_remote_repository_relative_path(
                    repository_id)
            if repo_relative is None:
                repo_relative = \
                    self._entropy._get_remote_repository_relative_path(
                        repository_id)
            my_path = os.path.join(repo_relative,
                self._settings['repositories']['branch'])
            lock_file = os.path.join(my_path, lock_file)

            txc = self._entropy.Transceiver(uri)
            txc.set_verbosity(False)
            if quiet:
                txc.set_silent(True)

            with txc as handler:

                if lock and handler.is_file(lock_file):
                    self._entropy.output(
                        "[%s|%s] %s" % (
                            blue(repository_id),
                            red(crippled_uri),
                            blue(_("mirror already locked for download")),
                        ),
                        importance = 1,
                        level = "info",
                        header = red(" @@ ")
                    )
                    continue

                elif not lock and not handler.is_file(lock_file):
                    self._entropy.output(
                        "[%s|%s] %s" % (
                            blue(repository_id),
                            red(crippled_uri),
                            blue(_("mirror already unlocked for download")),
                        ),
                        importance = 1,
                        level = "info",
                        header = red(" @@ ")
                    )
                    continue

                if lock:
                    rc_lock = self._do_mirror_lock(
                        repository_id, uri, handler,
                        dblock = False, quiet = quiet)
                else:
                    rc_lock = self._do_mirror_unlock(
                        repository_id, uri,
                        handler, dblock = False,
                        unlock_locally = unlock_locally,
                        quiet = quiet)
                if not rc_lock:
                    done = False

        return done

    def _do_mirror_lock(self, repository_id, uri, txc_handler,
        dblock = True, quiet = False):

        repo_relative = \
            self._entropy._get_override_remote_repository_relative_path(
                repository_id)
        if repo_relative is None:
            repo_relative = self._entropy._get_remote_repository_relative_path(
                repository_id)

        my_path = os.path.join(repo_relative,
            self._settings['repositories']['branch'])

        # create path to lock file if it doesn't exist
        if not txc_handler.is_dir(my_path):
            txc_handler.makedirs(my_path)

        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        lock_string = ''

        if dblock:
            self._entropy._create_local_repository_lockfile(repository_id)
            lock_file = self._entropy._get_repository_lockfile(repository_id)
        else:
            # locking/unlocking mirror1 for download
            lock_string = _('for download')
            self._entropy._create_local_repository_download_lockfile(
                repository_id)
            lock_file = self._entropy._get_repository_download_lockfile(
                repository_id)

        remote_path = os.path.join(my_path, os.path.basename(lock_file))

        rc_lock = txc_handler.lock(remote_path)
        if rc_lock:
            if not quiet:
                self._entropy.output(
                    "[%s|%s] %s %s" % (
                        blue(repository_id),
                        red(crippled_uri),
                        blue(_("mirror successfully locked")),
                        blue(lock_string),
                    ),
                    importance = 1,
                    level = "info",
                    header = red(" @@ ")
                )
        else:
            if not quiet:
                self._entropy.output(
                    "[%s|%s] %s: %s %s" % (
                        blue(repository_id),
                        red(crippled_uri),
                        blue("lock error"),
                        blue(_("mirror not locked")),
                        blue(lock_string),
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" * ")
                )
            self._entropy._remove_local_repository_lockfile(repository_id)

        return rc_lock


    def _do_mirror_unlock(self, repository_id, uri, txc_handler,
        dblock = True, unlock_locally = True, quiet = False):

        repo_relative = \
            self._entropy._get_override_remote_repository_relative_path(
                repository_id)
        if repo_relative is None:
            repo_relative = self._entropy._get_remote_repository_relative_path(
                repository_id)

        my_path = os.path.join(repo_relative,
            self._settings['repositories']['branch'])

        crippled_uri = EntropyTransceiver.get_uri_name(uri)

        if dblock:
            dbfile = etpConst['etpdatabaselockfile']
        else:
            dbfile = etpConst['etpdatabasedownloadlockfile']

        # make sure
        remote_path = os.path.join(my_path, os.path.basename(dbfile))

        if not txc_handler.is_file(remote_path):
            # once we locked a mirror, we're in a mutually exclusive
            # region. If we call unlock on a mirror already unlocked
            # that's fine for our semantics.
            rc_delete = True
        else:
            rc_delete = txc_handler.delete(remote_path)
        if rc_delete:
            if not quiet:
                self._entropy.output(
                    "[%s|%s] %s" % (
                        blue(repository_id),
                        red(crippled_uri),
                        blue(_("mirror successfully unlocked")),
                    ),
                    importance = 1,
                    level = "info",
                    header = darkgreen(" * ")
                )
            if unlock_locally:
                if dblock:
                    self._entropy._remove_local_repository_lockfile(
                        repository_id)
                else:
                    self._entropy._remove_local_repository_download_lockfile(
                        repository_id)
        else:
            if not quiet:
                self._entropy.output(
                    "[%s|%s] %s: %s - %s" % (
                        blue(repository_id),
                        red(crippled_uri),
                        blue(_("unlock error")),
                        rc_delete,
                        blue(_("mirror not unlocked")),
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" * ")
                )

        return rc_delete

    def download_package(self, repository_id, uri, pkg_relative_path):
        """
        Download a package given its mirror uri (uri) and its relative path
        (pkg_relative_path) on behalf of given repository.

        @param repository_id: repository identifier
        @type repository_id: string
        @param uri: mirror uri belonging to given repository identifier
        @type uri: string
        @param pkg_relative_path: relative path to package
        @type pkg_relative_path: string
        @return: download status, True for success, False for failure
        @rtype: bool
        """
        crippled_uri = EntropyTransceiver.get_uri_name(uri)

        tries = 0
        while tries < 5:

            tries += 1
            txc = self._entropy.Transceiver(uri)
            with txc as handler:

                self._entropy.output(
                    "[%s|%s|#%s] %s: %s" % (
                        brown(repository_id),
                        darkgreen(crippled_uri),
                        brown(str(tries)),
                        blue(_("connecting to download package")),
                        darkgreen(pkg_relative_path),
                    ),
                    importance = 1,
                    level = "info",
                    header = darkgreen(" * "),
                    back = True
                )

                remote_path = \
                    self._entropy.complete_remote_package_relative_path(
                        pkg_relative_path, repository_id)
                download_path = self._entropy.complete_local_package_path(
                    pkg_relative_path, repository_id)

                download_dir = os.path.dirname(download_path)

                self._entropy.output(
                    "[%s|%s|#%s] %s: %s" % (
                        brown(repository_id),
                        darkgreen(crippled_uri),
                        brown(str(tries)),
                        blue(_("downloading package")),
                        darkgreen(remote_path),
                    ),
                    importance = 1,
                    level = "info",
                    header = darkgreen(" * ")
                )

                if not const_dir_readable(download_dir):
                    self._entropy._ensure_dir_path(download_dir)

                rc_download = handler.download(remote_path, download_path)
                if not rc_download:
                    self._entropy.output(
                        "[%s|%s|#%s] %s: %s %s" % (
                            brown(repository_id),
                            darkgreen(crippled_uri),
                            brown(str(tries)),
                            blue(_("package")),
                            darkgreen(pkg_relative_path),
                            blue(_("does not exist")),
                        ),
                        importance = 1,
                        level = "error",
                        header = darkred(" !!! ")
                    )
                    return False

                dbconn = self._entropy.open_server_repository(repository_id,
                    read_only = True, no_upload = True)
                package_id = dbconn.getPackageIdFromDownload(pkg_relative_path)
                if package_id == -1:
                    self._entropy.output(
                        "[%s|%s|#%s] %s: %s %s" % (
                            brown(repository_id),
                            darkgreen(crippled_uri),
                            brown(str(tries)),
                            blue(_("package")),
                            darkgreen(pkg_relative_path),
                            blue(_("is not listed in the repository !")),
                        ),
                        importance = 1,
                        level = "error",
                        header = darkred(" !!! ")
                    )
                    return False

                storedmd5 = dbconn.retrieveDigest(package_id)
                self._entropy.output(
                    "[%s|%s|#%s] %s: %s" % (
                        brown(repository_id),
                        darkgreen(crippled_uri),
                        brown(str(tries)),
                        blue(_("verifying checksum of package")),
                        darkgreen(pkg_relative_path),
                    ),
                    importance = 1,
                    level = "info",
                    header = darkgreen(" * "),
                    back = True
                )

                md5check = entropy.tools.compare_md5(download_path, storedmd5)
                if md5check:
                    self._entropy.output(
                        "[%s|%s|#%s] %s: %s %s" % (
                            brown(repository_id),
                            darkgreen(crippled_uri),
                            brown(str(tries)),
                            blue(_("package")),
                            darkgreen(pkg_relative_path),
                            blue(_("downloaded successfully")),
                        ),
                        importance = 1,
                        level = "info",
                        header = darkgreen(" * ")
                    )
                    return True
                else:
                    self._entropy.output(
                        "[%s|%s|#%s] %s: %s %s" % (
                            brown(repository_id),
                            darkgreen(crippled_uri),
                            brown(str(tries)),
                            blue(_("package")),
                            darkgreen(pkg_relative_path),
                            blue(_("checksum does not match. re-downloading...")),
                        ),
                        importance = 1,
                        level = "warning",
                        header = darkred(" * ")
                    )
                    if os.path.isfile(download_path):
                        os.remove(download_path)

        # if we get here it means the files hasn't been downloaded properly
        self._entropy.output(
            "[%s|%s|#%s] %s: %s %s" % (
                brown(repository_id),
                darkgreen(crippled_uri),
                brown(str(tries)),
                blue(_("package")),
                darkgreen(pkg_relative_path),
                blue(_("seems broken. Consider to re-package it. Giving up!")),
            ),
            importance = 1,
            level = "error",
            header = darkred(" !!! ")
        )
        return False

    def _get_remote_db_status(self, uri, repo):

        sys_set = self._settings[Server.SYSTEM_SETTINGS_PLG_ID]['server']
        db_format = sys_set['database_file_format']
        cmethod = etpConst['etpdatabasecompressclasses'].get(db_format)
        if cmethod is None:
            raise AttributeError("Wrong repository compression method passed")

        repo_relative = \
            self._entropy._get_override_remote_repository_relative_path(
                repo)
        if repo_relative is None:
            repo_relative = self._entropy._get_remote_repository_relative_path(
                repo)
        remote_dir = os.path.join(repo_relative,
            self._settings['repositories']['branch'])

        # let raise exception if connection is impossible
        txc = self._entropy.Transceiver(uri)
        with txc as handler:

            compressedfile = etpConst[cmethod[2]]
            rc1 = handler.is_file(os.path.join(remote_dir, compressedfile))

            rev_file = self._entropy._get_local_repository_revision_file(repo)
            revfilename = os.path.basename(rev_file)
            rc2 = handler.is_file(os.path.join(remote_dir, revfilename))

            revision = 0
            if not (rc1 and rc2):
                return (uri, revision)

            tmp_fd, rev_tmp_path = const_mkstemp(prefix = "entropy.server")
            try:

                dlcount = 5
                dled = False
                while dlcount:
                    remote_rev_path = os.path.join(remote_dir, revfilename)
                    dled = handler.download(remote_rev_path, rev_tmp_path)
                    if dled:
                        break
                    dlcount -= 1

                crippled_uri = EntropyTransceiver.get_uri_name(uri)

                if const_file_readable(rev_tmp_path):

                    enc = etpConst['conf_encoding']
                    with codecs.open(rev_tmp_path, "r", encoding=enc) as f_rev:
                        try:
                            revision = int(f_rev.readline().strip())
                        except ValueError:
                            mytxt = _("mirror hasn't valid repository revision file")
                            self._entropy.output(
                                "[%s|%s] %s: %s" % (
                                    brown(repo),
                                    darkgreen(crippled_uri),
                                    blue(mytxt),
                                    bold(revision),
                                ),
                                importance = 1,
                                level = "error",
                                header = darkred(" !!! ")
                            )
                            revision = 0

                elif dlcount == 0:
                    self._entropy.output(
                        "[%s|%s] %s: %s" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            blue(_("unable to download repository revision")),
                            bold(revision),
                        ),
                        importance = 1,
                        level = "error",
                        header = darkred(" !!! ")
                    )
                    revision = 0

                else:
                    self._entropy.output(
                        "[%s|%s] %s: %s" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            blue(_("mirror doesn't have valid revision file")),
                            bold(revision),
                        ),
                        importance = 1,
                        level = "error",
                        header = darkred(" !!! ")
                    )
                    revision = 0

            finally:
                os.close(tmp_fd)
                os.remove(rev_tmp_path)

            return (uri, revision)

    def remote_repository_status(self, repository_id):
        """
        Return the repository status (revision) for every available mirror.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: dictionary, mirror URL (not URI) as key, revision as value
            (int)
        @rtype: dict
        """
        return dict(self._get_remote_db_status(uri, repository_id) for uri in \
            self._entropy.remote_repository_mirrors(repository_id))

    def mirrors_status(self, repository_id):
        """
        Return mirrors status for given repository identifier.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: list of tuples of length 3
            [(uri, upload_lock_status_bool, download_lock_status_bool)]
        @rtype: list
        """
        dbstatus = []
        repo_relative = \
            self._entropy._get_override_remote_repository_relative_path(
                repository_id)
        if repo_relative is None:
            repo_relative = self._entropy._get_remote_repository_relative_path(
                repository_id)
        remote_dir = os.path.join(repo_relative,
            self._settings['repositories']['branch'])
        lock_file = os.path.join(remote_dir, etpConst['etpdatabaselockfile'])
        down_lock_file = os.path.join(remote_dir,
            etpConst['etpdatabasedownloadlockfile'])

        for uri in self._entropy.remote_repository_mirrors(repository_id):
            down_status = False
            up_status = False

            # let raise exception if connection is impossible
            txc = self._entropy.Transceiver(uri)
            with txc as handler:
                if handler.is_file(lock_file):
                    # upload locked
                    up_status = True
                if handler.is_file(down_lock_file):
                    # download locked
                    down_status = True
                dbstatus.append((uri, up_status, down_status))

        return dbstatus

    def mirror_locked(self, repository_id, uri):
        """
        Return whether mirror is locked.

        @param repository_id: the repository identifier
        @type repository_id: string
        @param uri: mirror uri, as listed in repository metadata
        @type uri: string
        @return: True, if mirror is locked
        @rtype: bool
        """
        gave_up = False

        lock_file = self._entropy._get_repository_lockfile(repository_id)
        lock_filename = os.path.basename(lock_file)

        repo_relative = \
            self._entropy._get_override_remote_repository_relative_path(
                repository_id)
        if repo_relative is None:
            repo_relative = self._entropy._get_remote_repository_relative_path(
                repository_id)

        remote_dir = os.path.join(repo_relative,
            self._settings['repositories']['branch'])
        remote_lock_file = os.path.join(remote_dir, lock_filename)

        txc = self._entropy.Transceiver(uri)
        with txc as handler:

            if not os.path.isfile(lock_file) and \
                handler.is_file(remote_lock_file):

                crippled_uri = EntropyTransceiver.get_uri_name(uri)
                self._entropy.output(
                    "[%s|%s|%s] %s, %s" % (
                        brown(str(repository_id)),
                        darkgreen(crippled_uri),
                        red(_("locking")),
                        darkblue(_("mirror already locked")),
                        blue(_("waiting up to 2 minutes before giving up")),
                    ),
                    importance = 1,
                    level = "warning",
                    header = brown(" * "),
                    back = True
                )

                unlocked = False
                count = 0
                while count < 120:
                    count += 1
                    time.sleep(1)
                    if not handler.is_file(remote_lock_file):
                        self._entropy.output(
                            red("[%s|%s|%s] %s !" % (
                                    repository_id,
                                    crippled_uri,
                                    _("locking"),
                                    _("mirror unlocked"),
                                )
                            ),
                            importance = 1,
                            level = "info",
                            header = darkgreen(" * ")
                        )
                        unlocked = True
                        break

                if not unlocked:
                    gave_up = True

        return gave_up

    def _calculate_local_upload_files(self, repository_id):

        upload_dir = self._entropy._get_local_upload_directory(repository_id)

        # check if it exists
        if not os.path.isdir(upload_dir):
            return set()

        branch = self._settings['repositories']['branch']
        upload_packages = self._entropy._get_basedir_pkg_listing(
            upload_dir, etpConst['packagesext'], branch = branch)

        return set(upload_packages)

    def _calculate_local_package_files(self, repository_id, weak_files = False):

        base_dir = self._entropy._get_local_repository_base_directory(
            repository_id)

        # check if it exists
        if not os.path.isdir(base_dir):
            return set()

        branch = self._settings['repositories']['branch']
        pkg_ext = etpConst['packagesext']

        pkg_files = set(self._entropy._get_basedir_pkg_listing(
                base_dir, pkg_ext, branch = branch))

        weak_ext = etpConst['packagesweakfileext']
        weak_ext_len = len(weak_ext)
        weak_pkg_ext = pkg_ext + weak_ext

        def _map_weak_ext(path):
            return path[:-weak_ext_len]

        if weak_files:
            pkg_files |= set(
                map(
                    _map_weak_ext,
                    self._entropy._get_basedir_pkg_listing(
                        base_dir,
                        weak_pkg_ext,
                        branch = branch))
                )

        return pkg_files

    def _show_local_sync_stats(self, upload_files, local_files):
        self._entropy.output(
            "%s:" % (
                blue(_("Local statistics")),
            ),
            importance = 1,
            level = "info",
            header = red(" @@ ")
        )
        self._entropy.output(
            red("%s: %s %s" % (
                    blue(_("upload directory")),
                    bold(str(upload_files)),
                    red(_("files ready")),
                )
            ),
            importance = 0,
            level = "info",
            header = red(" @@ ")
        )
        self._entropy.output(
            red("%s: %s %s" % (
                    blue(_("packages directory")),
                    bold(str(local_files)),
                    red(_("files ready")),
                )
            ),
            importance = 0,
            level = "info",
            header = red(" @@ ")
        )

    def _show_sync_queues(self, upload, download, removal, copy, metainfo):

        branch = self._settings['repositories']['branch']

        # show stats
        for package, rel_pkg, size in upload:
            package = darkgreen(rel_pkg)
            size = blue(entropy.tools.bytes_into_human(size))
            self._entropy.output(
                "[%s|%s] %s [%s]" % (
                    brown(branch),
                    blue(_("upload")),
                    darkgreen(package),
                    size,
                ),
                importance = 0,
                level = "info",
                header = red("    # ")
            )
        key_sorter = lambda x: x[1]

        for package, rel_pkg, size in sorted(download, key = key_sorter):
            package = darkred(rel_pkg)
            size = blue(entropy.tools.bytes_into_human(size))
            self._entropy.output(
                "[%s|%s] %s [%s]" % (
                    brown(branch),
                    darkred(_("download")),
                    blue(package),
                    size,
                ),
                importance = 0,
                level = "info",
                header = red("    # ")
            )
        for package, rel_pkg, size in sorted(copy, key = key_sorter):
            package = darkblue(rel_pkg)
            size = blue(entropy.tools.bytes_into_human(size))
            self._entropy.output(
                "[%s|%s] %s [%s]" % (
                    brown(branch),
                    darkgreen(_("copy")),
                    brown(package),
                    size,
                ),
                importance = 0,
                level = "info",
                header = red("    # ")
            )
        for package, rel_pkg, size in sorted(removal, key = key_sorter):
            package = brown(rel_pkg)
            size = blue(entropy.tools.bytes_into_human(size))
            self._entropy.output(
                "[%s|%s] %s [%s]" % (
                    brown(branch),
                    red(_("remove")),
                    red(package),
                    size,
                ),
                importance = 0,
                level = "info",
                header = red("    # ")
            )

        self._entropy.output(
            "%s:  %s" % (
                blue(_("Packages to be removed")),
                darkred(str(len(removal))),
            ),
            importance = 0,
            level = "info",
            header = blue(" @@ ")
        )
        self._entropy.output(
            "%s:  %s" % (
                darkgreen(_("Packages to be moved locally")),
                darkgreen(str(len(copy))),
            ),
            importance = 0,
            level = "info",
            header = blue(" @@ ")
        )
        self._entropy.output(
            "%s:  %s" % (
                brown(_("Packages to be downloaded")),
                brown(str(len(download))),
            ),
            importance = 0,
            level = "info",
            header = blue(" @@ ")
        )
        self._entropy.output(
            "%s:  %s" % (
                bold(_("Packages to be uploaded")),
                bold(str(len(upload))),
            ),
            importance = 0,
            level = "info",
            header = blue(" @@ ")
        )

        self._entropy.output(
            "%s:  %s" % (
                darkred(_("Total removal size")),
                darkred(
                    entropy.tools.bytes_into_human(metainfo['removal'])
                ),
            ),
            importance = 0,
            level = "info",
            header = blue(" @@ ")
        )

        self._entropy.output(
            "%s:  %s" % (
                blue(_("Total upload size")),
                blue(entropy.tools.bytes_into_human(metainfo['upload'])),
            ),
            importance = 0,
            level = "info",
            header = blue(" @@ ")
        )
        self._entropy.output(
            "%s:  %s" % (
                brown(_("Total download size")),
                brown(entropy.tools.bytes_into_human(metainfo['download'])),
            ),
            importance = 0,
            level = "info",
            header = blue(" @@ ")
        )

    def _calculate_remote_package_files(self, repository_id, uri, txc_handler):

        remote_packages_data = {}
        remote_packages = []
        branch = self._settings['repositories']['branch']
        fifo_q = Queue()

        def get_content(lookup_dir):
            only_dir = self._entropy.complete_remote_package_relative_path(
                "", repository_id)
            db_url_dir = lookup_dir[len(only_dir):]

            # create path to lock file if it doesn't exist
            if not txc_handler.is_dir(lookup_dir):
                txc_handler.makedirs(lookup_dir)

            info = txc_handler.list_content_metadata(lookup_dir)

            dirs = []
            for path, size, user, group, perms in info:

                if perms.startswith("d"):
                    fifo_q.put(os.path.join(lookup_dir, path))
                else:
                    rel_path = os.path.join(db_url_dir, path)
                    remote_packages.append(rel_path)
                    remote_packages_data[rel_path] = int(size)

        # initialize the queue
        pkgs_dir_types = self._entropy._get_pkg_dir_names()
        for pkg_dir_type in pkgs_dir_types:

            remote_dir = self._entropy.complete_remote_package_relative_path(
                pkg_dir_type, repository_id)
            remote_dir = os.path.join(remote_dir, etpConst['currentarch'],
                branch)

            fifo_q.put(remote_dir)

        while not fifo_q.empty():
            get_content(fifo_q.get())

        return remote_packages, remote_packages_data

    def _calculate_packages_to_sync(self, repository_id, uri):

        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        upload_packages = self._calculate_local_upload_files(
            repository_id)
        local_packages = self._calculate_local_package_files(
            repository_id, weak_files = True)
        self._show_local_sync_stats(
            len(upload_packages), len(local_packages))

        self._entropy.output(
            "%s: %s" % (blue(_("Remote statistics for")), red(crippled_uri),),
            importance = 1,
            level = "info",
            header = red(" @@ ")
        )

        txc = self._entropy.Transceiver(uri)
        with txc as handler:
            (remote_packages,
             remote_packages_data) = self._calculate_remote_package_files(
                repository_id, uri, handler)

        self._entropy.output(
            "%s:  %s %s" % (
                blue(_("remote packages")),
                bold("%d" % (len(remote_packages),)),
                red(_("files stored")),
            ),
            importance = 0,
            level = "info",
            header = red(" @@ ")
        )

        mytxt = blue("%s ...") % (
            _("Calculating queues"),
        )
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = red(" @@ ")
        )

        upload_queue, download_queue, removal_queue, fine_queue = \
            self._calculate_sync_queues(repository_id, upload_packages,
                local_packages, remote_packages, remote_packages_data)
        return upload_queue, download_queue, removal_queue, fine_queue, \
            remote_packages_data

    def _calculate_sync_queues(self, repository_id, upload_packages,
        local_packages, remote_packages, remote_packages_data):

        upload_queue = set()
        extra_upload_queue = set()
        download_queue = set()
        extra_download_queue = set()
        removal_queue = set()
        fine_queue = set()
        branch = self._settings['repositories']['branch']
        pkg_ext = etpConst['packagesext']

        def _account_extra_packages(local_package, queue):
            repo = self._entropy.open_repository(repository_id)
            package_id = repo.getPackageIdFromDownload(local_package)
            # NOTE: package_id can be == -1 because there might have been
            # some packages in the queues that have been bumped more than
            # once, thus, not available in repository.
            if package_id != -1:
                extra_downloads = repo.retrieveExtraDownload(package_id)
                for extra_download in extra_downloads:
                    queue.add(extra_download['download'])

        for local_package in upload_packages:

            if not local_package.endswith(pkg_ext):
                continue

            if local_package in remote_packages:

                local_filepath = \
                    self._entropy.complete_local_upload_package_path(
                        local_package, repository_id)

                local_size = entropy.tools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(local_package)
                if remote_size is None:
                    remote_size = 0
                if local_size != remote_size:
                    # size does not match, adding to the upload queue
                    upload_queue.add(local_package)
                    _account_extra_packages(local_package, extra_upload_queue)
                else:
                    # just move from upload to packages
                    fine_queue.add(local_package)

            else:
                # always force upload of packages in uploaddir
                upload_queue.add(local_package)
                _account_extra_packages(local_package, extra_upload_queue)

        # if a package is in the packages directory but not online,
        # we have to upload it we have local_packages and remote_packages
        for local_package in local_packages:

            if not local_package.endswith(pkg_ext):
                continue
            # ignore file if its .weak alter-ego exists
            if self._weaken_file_exists(repository_id, local_package):
                continue

            if local_package in remote_packages:
                local_filepath = self._entropy.complete_local_package_path(
                    local_package, repository_id)
                local_size = entropy.tools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(local_package)
                if remote_size is None:
                    remote_size = 0
                if (local_size != remote_size) and (local_size != 0):
                    # size does not match, adding to the upload queue
                    if local_package not in fine_queue:
                        upload_queue.add(local_package)
                        _account_extra_packages(local_package,
                            extra_upload_queue)
            else:
                # this means that the local package does not exist
                # so, we need to download it
                upload_queue.add(local_package)
                _account_extra_packages(local_package, extra_upload_queue)

        # Fill download_queue and removal_queue
        for remote_package in remote_packages:

            if not remote_package.endswith(pkg_ext):
                continue

            if remote_package in local_packages:

                # ignore file if its .weak alter-ego exists
                if self._weaken_file_exists(repository_id, remote_package):
                    continue

                local_filepath = self._entropy.complete_local_package_path(
                    remote_package, repository_id)
                local_size = entropy.tools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(remote_package)
                if remote_size is None:
                    remote_size = 0
                if (local_size != remote_size) and (local_size != 0):
                    # size does not match, remove first
                    # do it only if the package has not been
                    # added to the upload_queue
                    if remote_package not in upload_queue:
                        # remotePackage == localPackage
                        # just remove something that differs
                        # from the content of the mirror
                        removal_queue.add(remote_package)
                        # then add to the download queue
                        download_queue.add(remote_package)
                        _account_extra_packages(remote_package,
                            extra_download_queue)
            else:
                # this means that the local package does not exist
                # so, we need to download it
                 # ignore .tmp files
                if not remote_package.endswith(
                    EntropyUriHandler.TMP_TXC_FILE_EXT):
                    download_queue.add(remote_package)
                    _account_extra_packages(remote_package,
                        extra_download_queue)

        # Collect packages that don't exist anymore in the database
        # so we can filter them out from the download queue
        dbconn = self._entropy.open_server_repository(repository_id,
            just_reading = True)
        db_files = dbconn.listAllDownloads(do_sort = False,
            full_path = True)
        db_files = set([x for x in db_files if \
            (self._entropy._get_branch_from_download_relative_uri(x) == branch)])

        """
        ### actually do not exclude files not available locally. This makes
        ### possible to repair broken tidy runs, downloading a pkg again
        ### makes it get flagged as expired afterwards
        exclude = set()
        for myfile in download_queue:
            if myfile.endswith(etpConst['packagesext']):
                if myfile not in db_files:
                    exclude.add(myfile)
        download_queue -= exclude
        """

        # filter out packages not in our repository
        upload_queue = set([x for x in upload_queue if x in db_files])
        # filter out weird moves, packages set for upload should not
        # be downloaded
        download_queue = set([x for x in download_queue if x not in \
            upload_queue])
        upload_queue |= extra_upload_queue
        download_queue |= extra_download_queue

        return upload_queue, download_queue, removal_queue, fine_queue

    def _expand_queues(self, upload_queue, download_queue, removal_queue,
        remote_packages_data, repo):

        metainfo = {
            'removal': 0,
            'download': 0,
            'upload': 0,
        }
        removal = []
        download = []
        do_copy = []
        upload = []

        for item in removal_queue:
            local_filepath = self._entropy.complete_local_package_path(
                item, repo)
            size = entropy.tools.get_file_size(local_filepath)
            metainfo['removal'] += size
            removal.append((local_filepath, item, size))

        for item in download_queue:

            local_filepath = self._entropy.complete_local_upload_package_path(
                item, repo)
            if not os.path.isfile(local_filepath):
                size = remote_packages_data.get(item)
                if size is None:
                    size = 0
                size = int(size)
                metainfo['removal'] += size
                download.append((local_filepath, item, size))
            else:
                size = entropy.tools.get_file_size(local_filepath)
                do_copy.append((local_filepath, item, size))

        for item in upload_queue:

            local_filepath = self._entropy.complete_local_upload_package_path(
                item, repo)

            local_filepath_pkgs = self._entropy.complete_local_package_path(
                item, repo)
            if os.path.isfile(local_filepath):
                size = entropy.tools.get_file_size(local_filepath)
                upload.append((local_filepath, item, size))
            else:
                size = entropy.tools.get_file_size(local_filepath_pkgs)
                upload.append((local_filepath_pkgs, item, size))
            metainfo['upload'] += size

        return upload, download, removal, do_copy, metainfo

    def _sync_run_removal_queue(self, repository_id, removal_queue):

        branch = self._settings['repositories']['branch']

        for remove_filepath, rel_path, size in removal_queue:

            remove_filename = os.path.basename(remove_filepath)
            remove_filepath_exp = remove_filepath + \
                etpConst['packagesexpirationfileext']

            self._entropy.output(
                "[%s|%s|%s] %s: %s [%s]" % (
                    brown(repository_id),
                    red("sync"),
                    brown(branch),
                    blue(_("removing package+hash")),
                    darkgreen(remove_filename),
                    blue(entropy.tools.bytes_into_human(size)),
                ),
                importance = 0,
                level = "info",
                header = darkred(" * ")
            )

            if os.path.isfile(remove_filepath):
                os.remove(remove_filepath)
            if os.path.isfile(remove_filepath_exp):
                os.remove(remove_filepath_exp)

        self._entropy.output(
            "[%s|%s|%s] %s" % (
                brown(repository_id),
                red(_("sync")),
                brown(branch),
                blue(_("removal complete")),
            ),
            importance = 0,
            level = "info",
            header = darkred(" * ")
        )


    def _sync_run_copy_queue(self, repository_id, copy_queue):

        branch = self._settings['repositories']['branch']
        for from_file, rel_file, size in copy_queue:

            to_file = self._entropy.complete_local_package_path(rel_file,
                repository_id)
            expiration_file = to_file+etpConst['packagesexpirationfileext']

            self._entropy.output(
                "[%s|%s|%s] %s: %s" % (
                    brown(repository_id),
                    red("sync"),
                    brown(branch),
                    blue(_("copying file+hash to repository")),
                    darkgreen(from_file),
                ),
                importance = 0,
                level = "info",
                header = darkred(" * ")
            )
            self._entropy._ensure_dir_path(os.path.dirname(to_file))

            shutil.copy2(from_file, to_file)

            # clear expiration file
            if os.path.isfile(expiration_file):
                os.remove(expiration_file)


    def _sync_run_upload_queue(self, repository_id, uri, upload_queue):

        branch = self._settings['repositories']['branch']
        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        queue_map = {}

        for upload_path, rel_path, size in upload_queue:
            rel_dir = os.path.dirname(rel_path)
            obj = queue_map.setdefault(rel_dir, [])
            obj.append(upload_path)

        errors = False
        m_fine_uris = set()
        m_broken_uris = set()
        for rel_path, myqueue in queue_map.items():

            remote_dir = self._entropy.complete_remote_package_relative_path(
                rel_path, repository_id)

            handlers_data = {
                'branch': branch,
                'download': rel_path,
            }
            uploader = self.TransceiverServerHandler(self._entropy, [uri],
                myqueue, critical_files = myqueue,
                txc_basedir = remote_dir, copy_herustic_support = True,
                handlers_data = handlers_data, repo = repository_id)

            xerrors, xm_fine_uris, xm_broken_uris = uploader.go()
            if xerrors:
                errors = True
            m_fine_uris.update(xm_fine_uris)
            m_broken_uris.update(xm_broken_uris)

        if errors:
            my_broken_uris = [
                (EntropyTransceiver.get_uri_name(x_uri), x_uri_rc) for \
                    x_uri, x_uri_rc in m_broken_uris]
            reason = my_broken_uris[0][1]
            self._entropy.output(
                "[%s] %s: %s, %s: %s" % (
                    brown(branch),
                    blue(_("upload errors")),
                    red(crippled_uri),
                    blue(_("reason")),
                    darkgreen(repr(reason)),
                ),
                importance = 1,
                level = "error",
                header = darkred(" !!! ")
            )
            return errors, m_fine_uris, m_broken_uris

        self._entropy.output(
            "[%s] %s: %s" % (
                brown(branch),
                blue(_("upload completed successfully")),
                red(crippled_uri),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )
        return errors, m_fine_uris, m_broken_uris


    def _sync_run_download_queue(self, repository_id, uri, download_queue):

        branch = self._settings['repositories']['branch']
        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        queue_map = {}

        for download_path, rel_path, size in download_queue:
            rel_dir = os.path.dirname(rel_path)
            obj = queue_map.setdefault(rel_dir, [])
            obj.append(download_path)

        errors = False
        m_fine_uris = set()
        m_broken_uris = set()
        for rel_path, myqueue in queue_map.items():

            remote_dir = self._entropy.complete_remote_package_relative_path(
                rel_path, repository_id)

            local_basedir = self._entropy.complete_local_package_path(rel_path,
                repository_id)
            if not os.path.isdir(local_basedir):
                self._entropy._ensure_dir_path(local_basedir)

            handlers_data = {
                'branch': branch,
                'download': rel_path,
            }
            downloader = self.TransceiverServerHandler(
                self._entropy, [uri], myqueue,
                critical_files = myqueue,
                txc_basedir = remote_dir, local_basedir = local_basedir,
                handlers_data = handlers_data, download = True,
                repo = repository_id)

            xerrors, xm_fine_uris, xm_broken_uris = downloader.go()
            if xerrors:
                errors = True
            m_fine_uris.update(xm_fine_uris)
            m_broken_uris.update(xm_broken_uris)

        if errors:
            my_broken_uris = [
                (EntropyTransceiver.get_uri_name(x_uri), x_uri_rc,) \
                    for x_uri, x_uri_rc in m_broken_uris]
            reason = my_broken_uris[0][1]
            self._entropy.output(
                "[%s|%s|%s] %s: %s, %s: %s" % (
                    brown(repository_id),
                    red(_("sync")),
                    brown(branch),
                    blue(_("download errors")),
                    darkgreen(crippled_uri),
                    blue(_("reason")),
                    reason,
                ),
                importance = 1,
                level = "error",
                header = darkred(" !!! ")
            )
            return errors, m_fine_uris, m_broken_uris

        self._entropy.output(
            "[%s|%s|%s] %s: %s" % (
                brown(repository_id),
                red(_("sync")),
                brown(branch),
                blue(_("download completed successfully")),
                darkgreen(crippled_uri),
            ),
            importance = 1,
            level = "info",
            header = darkgreen(" * ")
        )
        return errors, m_fine_uris, m_broken_uris

    def _run_package_files_qa_checks(self, repository_id, packages_list):

        my_qa = self._entropy.QA()
        qa_total = len(packages_list)
        qa_count = 0
        qa_some_faulty = []

        for upload_package in packages_list:
            qa_count += 1

            self._entropy.output(
                "%s: %s" % (
                    purple(_("QA checking package file")),
                    darkgreen(os.path.basename(upload_package)),
                ),
                importance = 0,
                level = "info",
                header = purple(" @@ "),
                back = True,
                count = (qa_count, qa_total,)
            )
            result = my_qa.entropy_package_checks(upload_package)
            if not result:
                qa_some_faulty.append(os.path.basename(upload_package))

        if qa_some_faulty:

            for qa_faulty_pkg in qa_some_faulty:
                self._entropy.output(
                    "[%s|%s] %s: %s" % (
                        brown(repository_id),
                        self._settings['repositories']['branch'],
                        red(_("faulty package file, please fix")),
                        blue(os.path.basename(qa_faulty_pkg)),
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" @@ ")
                )
            raise EntropyPackageException(
                'EntropyPackageException: cannot continue')

    def sync_repository(self, repository_id, enable_upload = True,
                        enable_download = True, force = False):
        """
        Synchronize the given repository identifier.

        @param repository_id: repository identifier
        @type repository_id: string
        @keyword enable_upload: enable upload in case it's required to push
            the repository remotely
        @type enable_upload: bool
        @keyword enable_download: enable download in case it's required to
            pull the repository remotely
        @type enable_download: bool
        @keyword force: force the repository push in case of QA errors
        @type force: bool
        @return: status code, 0 means all fine, non zero values mean error
        @rtype: int
        """
        return ServerPackagesRepository.update(self._entropy, repository_id,
            enable_upload, enable_download, force = force)

    def sync_packages(self, repository_id, ask = True, pretend = False,
        packages_check = False):
        """
        Synchronize packages in given repository, uploading, downloading,
        removing them. If changes were made locally, this function will do
        all the duties required to update the remote mirrors.

        @param repository_id: repository identifier
        @type repository_id: string
        @keyword ask: be interactive and ask user for confirmation
        @type ask: bool
        @keyword pretend: just execute without effectively change anything on
            mirrors
        @type pretend: bool
        @keyword packages_check: verify local packages after the sync.
        @type packages_check: bool
        @return: tuple composed by (mirrors_tainted (bool), mirror_errors(bool),
        successfull_mirrors (list), broken_mirrors (list), check_data (dict))
        @rtype: tuple
        @todo: improve return data documentation
        """
        self._entropy.output(
            "[%s|%s] %s" % (
                repository_id,
                red(_("sync")),
                darkgreen(_("starting packages sync")),
            ),
            importance = 1,
            level = "info",
            header = red(" @@ "),
            back = True
        )

        successfull_mirrors = set()
        broken_mirrors = set()
        check_data = ()
        upload_queue_qa_checked = set()
        mirrors_tainted = False
        mirror_errors = False
        mirrors_errors = False

        for uri in self._entropy.remote_packages_mirrors(repository_id):

            crippled_uri = EntropyTransceiver.get_uri_name(uri)
            mirror_errors = False

            self._entropy.output(
                "[%s|%s|%s] %s: %s" % (
                    repository_id,
                    red(_("sync")),
                    brown(self._settings['repositories']['branch']),
                    blue(_("packages sync")),
                    bold(crippled_uri),
                ),
                importance = 1,
                level = "info",
                header = red(" @@ ")
            )

            try:
                upload_queue, download_queue, removal_queue, fine_queue, \
                    remote_packages_data = self._calculate_packages_to_sync(
                        repository_id, uri)
            except socket.error as err:
                self._entropy.output(
                    "[%s|%s|%s] %s: %s, %s %s" % (
                        repository_id,
                        red(_("sync")),
                        self._settings['repositories']['branch'],
                        darkred(_("socket error")),
                        err,
                        darkred(_("on")),
                        crippled_uri,
                    ),
                    importance = 1,
                    level = "error",
                    header = darkgreen(" * ")
                )
                continue

            if (not upload_queue) and (not download_queue) and \
                (not removal_queue):
                self._entropy.output(
                    "[%s|%s|%s] %s: %s" % (
                        repository_id,
                        red(_("sync")),
                        self._settings['repositories']['branch'],
                        darkgreen(_("nothing to do on")),
                        crippled_uri,
                    ),
                    importance = 1,
                    level = "info",
                    header = darkgreen(" * ")
                )
                successfull_mirrors.add(uri)
                continue

            self._entropy.output(
                "%s:" % (blue(_("Expanding queues")),),
                importance = 1,
                level = "info",
                header = red(" ** ")
            )

            upload, download, removal, copy_q, metainfo = self._expand_queues(
                upload_queue, download_queue, removal_queue,
                remote_packages_data, repository_id)
            del upload_queue, download_queue, removal_queue, \
                remote_packages_data

            self._show_sync_queues(upload, download, removal, copy_q, metainfo)

            if not len(upload)+len(download)+len(removal)+len(copy_q):

                self._entropy.output(
                    "[%s|%s|%s] %s %s" % (
                        repository_id,
                        red(_("sync")),
                        self._settings['repositories']['branch'],
                        blue(_("nothing to sync for")),
                        crippled_uri,
                    ),
                    importance = 1,
                    level = "info",
                    header = darkgreen(" @@ ")
                )

                successfull_mirrors.add(uri)
                continue

            if pretend:
                successfull_mirrors.add(uri)
                continue

            if ask:
                rc_sync = self._entropy.ask_question(
                    _("Would you like to run the steps above ?"))
                if rc_sync == _("No"):
                    continue

            try:

                # QA checks
                pkg_ext = etpConst['packagesext']
                qa_package_files = [x[0] for x in upload if (x[0] \
                    not in upload_queue_qa_checked) and x[0].endswith(pkg_ext)]
                upload_queue_qa_checked |= set(qa_package_files)

                self._run_package_files_qa_checks(repository_id,
                    qa_package_files)

                if removal:
                    self._sync_run_removal_queue(repository_id, removal)

                if copy_q:
                    self._sync_run_copy_queue(repository_id, copy_q)

                if upload:
                    mirrors_tainted = True

                if upload:
                    d_errors, m_fine_uris, \
                        m_broken_uris = self._sync_run_upload_queue(
                            repository_id, uri, upload)

                    if d_errors:
                        mirror_errors = True

                if download:
                    d_errors, m_fine_uris, \
                        m_broken_uris = self._sync_run_download_queue(
                            repository_id, uri, download)

                    if d_errors:
                        mirror_errors = True
                if not mirror_errors:
                    successfull_mirrors.add(uri)
                else:
                    mirrors_errors = True

            except KeyboardInterrupt:
                self._entropy.output(
                    "[%s|%s|%s] %s" % (
                        repository_id,
                        red(_("sync")),
                        self._settings['repositories']['branch'],
                        darkgreen(_("keyboard interrupt !")),
                    ),
                    importance = 1,
                    level = "info",
                    header = darkgreen(" * ")
                )
                continue

            except EntropyPackageException as err:

                mirrors_errors = True
                broken_mirrors.add(uri)
                successfull_mirrors.clear()
                # so that people will realize this is a very bad thing
                self._entropy.output(
                    "[%s|%s|%s] %s: %s, %s: %s" % (
                        repository_id,
                        red(_("sync")),
                        self._settings['repositories']['branch'],
                        darkred(_("you must package them again")),
                        EntropyPackageException,
                        _("error"),
                        err,
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" !!! ")
                )
                return mirrors_tainted, mirrors_errors, successfull_mirrors, \
                    broken_mirrors, check_data

            except Exception as err:

                entropy.tools.print_traceback()
                mirrors_errors = True
                broken_mirrors.add(uri)
                self._entropy.output(
                    "[%s|%s|%s] %s: %s, %s: %s" % (
                        repository_id,
                        red(_("sync")),
                        self._settings['repositories']['branch'],
                        darkred(_("exception caught")),
                        Exception,
                        _("error"),
                        err,
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" !!! ")
                )

                exc_txt = entropy.tools.print_exception(
                    silent = True)
                for line in exc_txt:
                    self._entropy.output(
                        repr(line),
                        importance = 1,
                        level = "error",
                        header = darkred(":  ")
                    )

                if len(successfull_mirrors) > 0:
                    self._entropy.output(
                        "[%s|%s|%s] %s" % (
                            repository_id,
                            red(_("sync")),
                            self._settings['repositories']['branch'],
                            darkred(
                                _("at least one mirror synced properly!")),
                        ),
                        importance = 1,
                        level = "error",
                        header = darkred(" !!! ")
                    )
                continue

        # if at least one server has been synced successfully, move files
        if (len(successfull_mirrors) > 0) and not pretend:
            self._move_files_over_from_upload(repository_id)

        if packages_check:
            check_data = self._entropy._verify_local_packages(repository_id,
                [], ask = ask)

        return mirrors_tainted, mirrors_errors, successfull_mirrors, \
            broken_mirrors, check_data

    def _move_files_over_from_upload(self, repository_id):

        upload_dir = self._entropy._get_local_upload_directory(repository_id)
        basedir_list = []
        entropy.tools.recursive_directory_relative_listing(basedir_list,
            upload_dir)

        for pkg_rel in basedir_list:

            source_pkg = self._entropy.complete_local_upload_package_path(
                pkg_rel, repository_id)
            dest_pkg = self._entropy.complete_local_package_path(pkg_rel,
                repository_id)

            # clear expiration file
            dest_expiration = dest_pkg + etpConst['packagesexpirationfileext']
            if os.path.isfile(dest_expiration):
                os.remove(dest_expiration)

            self._entropy._ensure_dir_path(os.path.dirname(dest_pkg))

            try:
                os.rename(source_pkg, dest_pkg)
            except OSError as err: # on different hard drives?
                if err.errno != errno.EXDEV:
                    raise
                shutil.move(source_pkg, dest_pkg)

    def _is_package_expired(self, repository_id, package_rel, days):

        pkg_path = self._entropy.complete_local_package_path(package_rel,
            repository_id)
        exp_pkg_path = pkg_path + etpConst['packagesexpirationfileext']
        weak_pkg_path = pkg_path + etpConst['packagesweakfileext']

        # it is assumed that weakened package files are always marked
        # as expired first. So, if a .expired file exists, a .weak
        # does as well. However, we must also be fault tolerant and
        # cope with the situation in where .weak files exist but not
        # their .expired counterpart.
        # So, if a .weak file exists, we won't return straight away.
        # At the same time, if a .expired file exists, we will use that.

        expired_exists = os.path.lexists(exp_pkg_path)
        weak_exists = os.path.lexists(weak_pkg_path)

        test_pkg_path = None
        if expired_exists:
            test_pkg_path = exp_pkg_path
        elif weak_exists:
            # deal with corruption
            test_pkg_path = weak_pkg_path
        else:
            # package file not expired, return straight away
            return False

        mtime = os.path.getmtime(test_pkg_path)
        delta = days * 24 * 3600
        currmtime = time.time()
        file_delta = currmtime - mtime

        if file_delta > delta:
            return True
        return False

    def _expiration_file_exists(self, repository_id, package_rel):
        """
        Return whether the expiration file exists for the given package.

        @param repository_id: repository identifier
        @type repository_id: string
        @param package_rel: package relative url, as returned by
            EntropyRepository.retrieveDownloadURL
        @type package_rel: string
        """
        pkg_path = self._entropy.complete_local_package_path(package_rel,
            repository_id)

        pkg_path += etpConst['packagesexpirationfileext']
        return os.path.lexists(pkg_path)

    def _weaken_file_exists(self, repository_id, package_rel):
        """
        Return whether the weaken file exists for the given package.

        @param repository_id: repository identifier
        @type repository_id: string
        @param package_rel: package relative url, as returned by
            EntropyRepository.retrieveDownloadURL
        @type package_rel: string
        """
        pkg_path = self._entropy.complete_local_package_path(package_rel,
            repository_id)

        pkg_path += etpConst['packagesweakfileext']
        return os.path.lexists(pkg_path)

    def _create_expiration_file(self, repository_id, package_rel):
        """
        Mark the package file as expired by creating an .expired file
        if it does not exist. Please note that the created file mtime
        will be used to determine when the real package file will be
        removed.

        @param repository_id: repository identifier
        @type repository_id: string
        @param package_rel: package relative url, as returned by
            EntropyRepository.retrieveDownloadURL
        @type package_rel: string
        """
        pkg_path = self._entropy.complete_local_package_path(package_rel,
            repository_id)

        pkg_path += etpConst['packagesexpirationfileext']
        if os.path.lexists(pkg_path):
            # do not touch the file then, or mtime will be updated
            return

        self._entropy.output(
            "[%s] %s" % (
                blue(_("expire")),
                darkgreen(pkg_path),
            ),
            importance = 1,
            level = "info",
            header = brown(" @@ ")
        )

        with open(pkg_path, "w") as f_exp:
            f_exp.flush()

    def _collect_expiring_packages(self, repository_id, branch):

        repo = self._entropy.open_repository(repository_id)

        database_bins = set(repo.listAllDownloads(do_sort = False,
            full_path = True))
        extra_database_bins = set(repo.listAllExtraDownloads(do_sort = False))

        repo_basedir = self._entropy._get_local_repository_base_directory(
            repository_id)

        repo_bins = set(self._entropy._get_basedir_pkg_listing(repo_basedir,
            etpConst['packagesext'], branch = branch))
        extra_repo_bins = set(self._entropy._get_basedir_pkg_listing(
            repo_basedir, etpConst['packagesextraext'], branch = branch))

        # scan .weak files. This is part of the weak-package-files support.
        weak_ext = etpConst['packagesweakfileext']
        weak_ext_len = len(weak_ext)

        def _map_weak_ext(path):
            return path[:-weak_ext_len]

        repo_bins |= set(
            map(
                _map_weak_ext,
                self._entropy._get_basedir_pkg_listing(
                    repo_basedir,
                    etpConst['packagesext'] + weak_ext,
                    branch = branch))
            )
        extra_repo_bins |= set(
            map(
                _map_weak_ext,
                self._entropy._get_basedir_pkg_listing(
                    repo_basedir,
                    etpConst['packagesextraext'] + weak_ext,
                    branch = branch))
            )

        # convert to set, so that we can do fast thingszzsd
        repo_bins -= database_bins
        extra_repo_bins -= extra_database_bins
        return repo_bins, extra_repo_bins

    def _weaken_package_file(self, repository_id, package_rel):
        """
        Weaken the package file by creating a .weak file containing
        information about the to-be-removed package file.

        @param repository_id: repository identifier
        @type repository_id: string
        @param package_rel: package relative url, as returned by
            EntropyRepository.retrieveDownloadURL
        @type package_rel: string
        """
        pkg_path = self._entropy.complete_local_package_path(package_rel,
            repository_id)

        pkg_path += etpConst['packagesweakfileext']
        if os.path.lexists(pkg_path):
            # do not touch, or mtime will be updated
            return

        self._entropy.output(
            "[%s] %s" % (
                blue(_("weaken")),
                darkgreen(pkg_path),
            ),
            importance = 1,
            level = "info",
            header = brown(" @@ ")
        )

        with open(pkg_path, "w") as f_exp:
            f_exp.flush()

    def _remove_local_package(self, repository_id, package_rel,
                              remove_expired = True, remove_weak = True):
        """
        Remove a package file locally.

        @param repository_id: repository identifier
        @type repository_id: string
        @param package_rel: package relative url, as returned by
            EntropyRepository.retrieveDownloadURL
        @type package_rel: string
        @keyword remove_expired: remove the .expired file?
        @type remove_expired: bool
        @keyword remove_weak: remove the .weak file?
        @type remove_weak: bool
        """
        package_path = self._entropy.complete_local_package_path(
            package_rel, repository_id)
        # if package files are stuck in the upload/ directory
        # it means that the repository itself has never been pushed
        up_package_path = self._entropy.complete_local_upload_package_path(
            package_rel, repository_id)

        remove_list = [package_path, up_package_path]
        if remove_expired:
            package_path_expired = package_path + \
                etpConst['packagesexpirationfileext']
            remove_list.append(package_path_expired)

        if remove_weak:
            package_path_weak = package_path + \
                etpConst['packagesweakfileext']
            remove_list.append(package_path_weak)

        for path in remove_list:
            try:
                os.remove(path)
            except OSError as err:
                # handle race conditions
                if err.errno != errno.ENOENT:
                    raise
                continue
            self._entropy.output(
                "[%s] %s" % (
                    blue(_("remove")),
                    darkgreen(path),
                ),
                importance = 1,
                level = "info",
                header = brown(" @@ ")
            )

    def tidy_mirrors(self, repository_id, ask = True, pretend = False,
        expiration_days = None):
        """
        Cleanup package mirrors for given repository from outdated package
        files. A package file is considered outdated if the corresponding
        entry in the repository database has been removed and the removal is
        ETP_EXPIRATION_DAYS (env var) days old (default is given by:
        etpConst['packagesexpirationdays'] and can be changed in server.conf).

        @param repository_id: repository identifier
        @type repository_id: string
        @keyword ask: be interactive and ask user for confirmation
        @type ask: bool
        @keyword pretend: just execute without effectively change anything on
            mirrors
        @keyword expiration_days: days after a package is considered expired
        @type: int
        @type pretend: bool
        @return: True, if tidy went successful, False if not
        @rtype: bool
        """
        srv_set = self._settings[Server.SYSTEM_SETTINGS_PLG_ID]['server']
        if expiration_days is None:
            expiration_days = srv_set['packages_expiration_days']
        else:
            if not isinstance(expiration_days, const_get_int()):
                raise AttributeError("invalid expiration_days")
            if expiration_days < 0:
                raise AttributeError("invalid expiration_days")

        weak_package_files = srv_set['weak_package_files']

        self._entropy.output(
            "[%s|%s|%s] %s" % (
                brown(repository_id),
                red(_("tidy")),
                blue(self._settings['repositories']['branch']),
                blue(_("collecting expired packages")),
            ),
            importance = 1,
            level = "info",
            header = red(" @@ ")
        )

        branch_data = {}
        done = True
        branch = self._settings['repositories']['branch']

        self._entropy.output(
            "[%s] %s" % (
                brown(branch),
                blue(_("collecting expired packages in the selected branches")),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )

        # collect removed packages
        expiring_packages, extra_expiring_packages = \
            self._collect_expiring_packages(repository_id, branch)
        if expiring_packages:

            # filter expired packages used by other branches
            # this is done for the sake of consistency
            # --- read packages.db.pkglist, make sure your repository
            # has been ported to latest Entropy

            branch_pkglist_data = self._read_remote_file_in_branches(
                repository_id, etpConst['etpdatabasepkglist'],
                excluded_branches = [branch])
            # format data
            for key, val in list(branch_pkglist_data.items()):
                branch_pkglist_data[key] = val.split("\n")

            for other_branch in branch_pkglist_data:
                branch_pkglist = set(branch_pkglist_data[other_branch])
                expiring_packages -= branch_pkglist

        if extra_expiring_packages:

            # filter expired packages used by other branches
            # this is done for the sake of consistency
            # --- read packages.db.extra_pkglist, make sure your repository
            # has been ported to latest Entropy

            branch_extra_pkglist_data = self._read_remote_file_in_branches(
                repository_id, etpConst['etpdatabaseextrapkglist'],
                excluded_branches = [branch])
            # format data
            for key, val in list(branch_extra_pkglist_data.items()):
                branch_extra_pkglist_data[key] = val.split("\n")

            for other_branch in branch_extra_pkglist_data:
                branch_pkglist = set(branch_extra_pkglist_data[other_branch])
                extra_expiring_packages -= branch_pkglist

        remove = []
        expire = []
        weaken = []

        for package_rel in expiring_packages:
            expired = self._is_package_expired(repository_id, package_rel,
                expiration_days)
            if expired:
                remove.append(package_rel)
            else:
                if not self._expiration_file_exists(repository_id, package_rel):
                    expire.append(package_rel)
                if weak_package_files and not self._weaken_file_exists(
                    repository_id, package_rel):
                    weaken.append(package_rel)

        for extra_package_rel in extra_expiring_packages:
            expired = self._is_package_expired(repository_id, extra_package_rel,
                expiration_days)
            if expired:
                remove.append(extra_package_rel)
            else:
                if not self._expiration_file_exists(
                    repository_id, extra_package_rel):
                    expire.append(extra_package_rel)
                if weak_package_files and not self._weaken_file_exists(
                    repository_id, extra_package_rel):
                    weaken.append(extra_package_rel)

        if not (remove or weaken or expire):
            self._entropy.output(
                "[%s] %s" % (
                    brown(branch),
                    blue(_("nothing to clean on this branch")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            return done

        if remove:
            self._entropy.output(
                "[%s] %s:" % (
                    brown(branch),
                    blue(_("these will be removed")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
        for package in remove:
            self._entropy.output(
                "[%s] %s: %s" % (
                        brown(branch),
                        blue(_("remove")),
                        darkgreen(package),
                    ),
                importance = 1,
                level = "info",
                header = brown("    # ")
            )

        if expire:
            self._entropy.output(
                "[%s] %s:" % (
                    brown(branch),
                    blue(_("these will be marked as expired")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
        for package in expire:
            self._entropy.output(
                "[%s] %s: %s" % (
                        brown(branch),
                        blue(_("expire")),
                        darkgreen(package),
                    ),
                importance = 1,
                level = "info",
                header = brown("    # ")
            )

        if weaken:
            self._entropy.output(
                "[%s] %s:" % (
                    brown(branch),
                    blue(_("these will be removed and marked as weak")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
        for package in weaken:
            self._entropy.output(
                "[%s] %s: %s" % (
                        brown(branch),
                        blue(_("weaken")),
                        darkgreen(package),
                    ),
                importance = 1,
                level = "info",
                header = brown("    # ")
            )

        if pretend:
            return done

        if ask:
            rc_question = self._entropy.ask_question(
                _("Would you like to continue ?"))
            if rc_question == _("No"):
                return done

        for package_rel in expire:
            self._create_expiration_file(repository_id, package_rel)

        # split queue by remote directories to work on
        removal_map = {}
        dbconn = self._entropy.open_server_repository(repository_id,
            just_reading = True)
        for package_rel in remove:
            rel_path = self._entropy.complete_remote_package_relative_path(
                package_rel, repository_id)
            rel_dir = os.path.dirname(rel_path)
            obj = removal_map.setdefault(rel_dir, [])
            base_pkg = os.path.basename(package_rel)
            obj.append(base_pkg)

        for uri in self._entropy.remote_packages_mirrors(repository_id):

            ##
            # remove remotely
            ##

            uri_done = True
            m_fine_uris = set()
            m_broken_uris = set()
            for remote_dir, myqueue in removal_map.items():

                self._entropy.output(
                    "[%s] %s..." % (
                        brown(branch),
                        blue(_("removing packages remotely")),
                    ),
                    importance = 1,
                    level = "info",
                    header = blue(" @@ ")
                )

                destroyer = self.TransceiverServerHandler(
                    self._entropy,
                    [uri],
                    myqueue,
                    critical_files = [],
                    txc_basedir = remote_dir,
                    remove = True,
                    repo = repository_id
                )
                xerrors, xm_fine_uris, xm_broken_uris = destroyer.go()
                if xerrors:
                    uri_done = False
                m_fine_uris.update(xm_fine_uris)
                m_broken_uris.update(xm_broken_uris)

            if not uri_done:
                my_broken_uris = [
                    (EntropyTransceiver.get_uri_name(x_uri), x_uri_rc) \
                        for x_uri, x_uri_rc in m_broken_uris]

                reason = my_broken_uris[0][1]
                crippled_uri = EntropyTransceiver.get_uri_name(uri)
                self._entropy.output(
                    "[%s] %s: %s, %s: %s" % (
                        brown(branch),
                        blue(_("remove errors")),
                        red(crippled_uri),
                        blue(_("reason")),
                        reason,
                    ),
                    importance = 1,
                    level = "warning",
                    header = brown(" !!! ")
                )
                done = False

            self._entropy.output(
                "[%s] %s..." % (
                    brown(branch),
                    blue(_("removing packages locally")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )

        ##
        # remove locally
        ##

        for package_rel in remove:
            self._remove_local_package(repository_id, package_rel)

        for package_rel in weaken:
            self._weaken_package_file(repository_id, package_rel)
            self._remove_local_package(repository_id, package_rel,
                                       remove_expired = False,
                                       remove_weak = False)

        return done

    def download_notice_board(self, repository_id):
        """
        Download notice board for given repository identifier.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: True if download went successful.
        @rtype: bool
        """
        mirrors = self._entropy.remote_repository_mirrors(repository_id)
        rss_path = self._entropy._get_local_repository_notice_board_file(
            repository_id)
        mytmpdir = const_mkdtemp(prefix = "entropy.server")

        self._entropy.output(
            "[%s] %s %s" % (
                brown(repository_id),
                blue(_("downloading notice board from mirrors to")),
                red(rss_path),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )

        remote_dir = os.path.join(
            self._entropy._get_remote_repository_relative_path(repository_id),
                self._settings['repositories']['branch'])

        downloaded = False
        for uri in mirrors:
            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            downloader = self.TransceiverServerHandler(
                self._entropy, [uri],
                [rss_path], download = True,
                local_basedir = mytmpdir, critical_files = [rss_path],
                txc_basedir = remote_dir, repo = repository_id
            )
            errors, m_fine_uris, m_broken_uris = downloader.go()
            if not errors:
                self._entropy.output(
                    "[%s] %s: %s" % (
                        brown(repository_id),
                        blue(_("notice board downloaded successfully from")),
                        red(crippled_uri),
                    ),
                    importance = 1,
                    level = "info",
                    header = blue(" @@ ")
                )
                downloaded = True
                break

        if downloaded:
            shutil.move(os.path.join(mytmpdir, os.path.basename(rss_path)),
                rss_path)

        return downloaded

    def remove_notice_board(self, repository_id):
        """
        Remove notice board for given repository identifier.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: True if removal went successful.
        @rtype: bool
        """
        mirrors = self._entropy.remote_repository_mirrors(repository_id)
        rss_path = self._entropy._get_local_repository_notice_board_file(
            repository_id)
        rss_file = os.path.basename(rss_path)

        self._entropy.output(
            "[%s] %s %s" % (
                    brown(repository_id),
                    blue(_("removing notice board from")),
                    red(rss_file),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )

        remote_dir = os.path.join(
            self._entropy._get_remote_repository_relative_path(repository_id),
                self._settings['repositories']['branch'])

        destroyer = self.TransceiverServerHandler(
            self._entropy,
            mirrors,
            [rss_file],
            critical_files = [rss_file],
            remove = True,
            txc_basedir = remote_dir,
            repo = repository_id
        )
        errors, m_fine_uris, m_broken_uris = destroyer.go()
        if errors:
            m_broken_uris = sorted(m_broken_uris)
            m_broken_uris = [EntropyTransceiver.get_uri_name(x_uri) \
                for x_uri, x_uri_rc in m_broken_uris]
            self._entropy.output(
                "[%s] %s %s" % (
                        brown(repository_id),
                        blue(_("notice board removal failed on")),
                        red(', '.join(m_broken_uris)),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            return False
        self._entropy.output(
            "[%s] %s" % (
                    brown(repository_id),
                    blue(_("notice board removal success")),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )
        return True


    def upload_notice_board(self, repository_id):
        """
        Upload notice board for given repository identifier.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: True if upload went successful.
        @rtype: bool
        """
        mirrors = self._entropy.remote_repository_mirrors(repository_id)
        rss_path = self._entropy._get_local_repository_notice_board_file(
            repository_id)

        self._entropy.output(
            "[%s] %s %s" % (
                brown(repository_id),
                blue(_("uploading notice board from")),
                red(rss_path),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )

        remote_dir = os.path.join(
            self._entropy._get_remote_repository_relative_path(repository_id),
                self._settings['repositories']['branch'])

        uploader = self.TransceiverServerHandler(
            self._entropy,
            mirrors,
            [rss_path],
            critical_files = [rss_path],
            txc_basedir = remote_dir, repo = repository_id
        )
        errors, m_fine_uris, m_broken_uris = uploader.go()
        if errors:
            m_broken_uris = sorted(m_broken_uris)
            m_broken_uris = [EntropyTransceiver.get_uri_name(x_uri) \
                for x_uri, x_uri_rc in m_broken_uris]
            self._entropy.output(
                "[%s] %s %s" % (
                        brown(repository_id),
                        blue(_("notice board upload failed on")),
                        red(', '.join(m_broken_uris)),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            return False
        self._entropy.output(
            "[%s] %s" % (
                    brown(repository_id),
                    blue(_("notice board upload success")),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )
        return True


    def update_notice_board(self, repository_id, title, notice_text,
        link = None):
        """
        Update notice board adding a new entry, provided by a title and a
        body message (notice_text). Providing a link is optional.

        @param repository_id: repository identifier
        @type repository_id: string
        @param title: noticeboard new entry title
        @type title: string
        @param notice_text: noticeboard new entry text
        @type notice_text: string
        @keyword link: optional link to provide with the noticeboard entry
        @type link: string
        @return: True if update went successful.
        @rtype: bool
        """
        rss_title = "%s Notice Board" % (self._settings['system']['name'],)
        rss_description = "Inform about important distribution activities."
        rss_path = self._entropy._get_local_repository_notice_board_file(
            repository_id)
        srv_set = self._settings[Server.SYSTEM_SETTINGS_PLG_ID]['server']
        if not link:
            link = srv_set['rss']['website_url']

        self.download_notice_board(repository_id)
        rss_main = RSS(rss_path, rss_title, rss_description,
            maxentries = 20)
        rss_main.add_item(title, link, description = notice_text)
        rss_main.write_changes()
        dict_list, items = rss_main.get_entries()
        if items == 0:
            status = self.remove_notice_board(repository_id)
        else:
            status = self.upload_notice_board(repository_id)
        return status

    def read_notice_board(self, repository_id, do_download = True):
        """
        Read content of noticeboard for given repository. do_download, if True,
        fetches the noticeboard directly from the remote repository before
        returning its content. If noticeboard cannot be downloaded or
        do_download is False and there is any local cache, None will be
        returned.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: the output of entropy.misc.RSS.get_entries() or None
        @rtype: tuple or None
        """
        rss_path = self._entropy._get_local_repository_notice_board_file(
            repository_id)
        if do_download:
            self.download_notice_board(repository_id)
        if not const_file_readable(rss_path):
            return None
        rss_main = RSS(rss_path, '', '')
        return rss_main.get_entries()

    def remove_from_notice_board(self, repository_id, identifier):
        """
        Remove entry from noticeboard of given repository. read_notice_board()
        returns an object containing a list of entries, identifier here
        represents the index of that list, if it exists.

        @param repository_id: repository identifier
        @type repository_id: string
        @param identifier: notice board identifier
        @type identifier: int
        @return: True, if operation is successful, False otherwise
        @rtype: bool
        """
        rss_path = self._entropy._get_local_repository_notice_board_file(
            repository_id)
        rss_title = "%s Notice Board" % (self._settings['system']['name'],)
        rss_description = "Inform about important distribution activities."
        if not const_file_readable(rss_path):
            return False
        rss_main = RSS(rss_path, rss_title, rss_description)
        counter = rss_main.remove_entry(identifier)
        rss_main.write_changes()
        return True
