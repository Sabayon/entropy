# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server Mirrors Interfaces}.

"""
import os
import tempfile
import shutil
import time
from entropy.exceptions import OnlineMirrorError, IncorrectParameter, \
    ConnectionError, InvalidDataType, EntropyPackageException, TransceiverError
from entropy.output import red, darkgreen, bold, brown, blue, darkred, \
    darkblue, purple
from entropy.const import etpConst, etpSys
from entropy.i18n import _
from entropy.misc import RSS
from entropy.transceivers import EntropyTransceiver
from entropy.db import dbapi2

class Server:

    import socket
    import entropy.dump as dumpTools
    import entropy.tools as entropyTools
    def __init__(self,  ServerInstance, repo = None):

        from entropy.cache import EntropyCacher
        from entropy.server.transceivers import TransceiverServerHandler
        from entropy.server.interfaces.main import Server as MainServer

        if not isinstance(ServerInstance, MainServer):
            mytxt = _("entropy.server.interfaces.main.Server needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        self.Entropy = ServerInstance
        self.TransceiverServerHandler = TransceiverServerHandler
        self.Cacher = EntropyCacher()
        self.sys_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        self.SystemSettings = self.Entropy.SystemSettings

        mytxt = blue("%s:") % (_("Entropy Server Mirrors Interface loaded"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )
        mytxt = _("mirror")
        for mirror in self.Entropy.get_remote_mirrors(repo):
            mirror = EntropyTransceiver.hide_sensible_data(mirror)
            self.Entropy.updateProgress(
                blue("%s: %s") % (mytxt, darkgreen(mirror),),
                importance = 0,
                type = "info",
                header = brown("   # ")
            )

    def get_remote_branches(self, repo = None):
        """
        Returns a list of remotely available branches for the provided
        repository identifier.

        @keyword repo: repository identifier
        @type repo: string
        @return: list of valid, available remote branches
        @rtype: set
        """

        if repo is None:
            repo = self.Entropy.default_repository

        remote_branches = set()
        # this is used to validate Entropy repository path
        ts_file = etpConst['etpdatabasetimestampfile']
        mirrors = self.Entropy.get_remote_mirrors(repo)
        for uri in mirrors:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            self.Entropy.updateProgress(
                "[repo:%s] %s: %s" % (
                    brown(repo),
                    blue(_("listing branches in mirror")),
                    darkgreen(crippled_uri),
                ),
                importance = 1,
                type = "info",
                header = brown(" @@ ")
            )

            txc = self.Entropy.Transceiver(uri)
            txc.set_verbosity(False)
            with txc as handler:
                branches_path = self.Entropy.get_remote_database_relative_path(
                    repo)

                try:
                    branches = handler.list_content(branches_path)
                except ValueError:
                    branches = [] # dir is empty

                for branch in branches:
                    mypath = os.path.join("/", branches_path, branch)
                    if handler.is_dir(mypath):
                        remote_branches.add(branch)

        return remote_branches

    def read_remote_file_in_branches(self, filename, repo = None,
            excluded_branches = None):
        """
        Reads a file remotely located in all the available branches.

        @param filename: name of the file that should be located inside
            repository database directory
        @type filename: string
        @keyword repo: repository identifier
        @type repo: string
        @keyword excluded_branches: list of branch identifiers excluded or None
        @type excluded_branches: list or None
        @return: dictionary with branches as key and raw file content as value:
            {'4': 'abcd\n', '5': 'defg\n'}
        @rtype: dict
        """
        if repo is None:
            repo = self.Entropy.default_repository
        if excluded_branches is None:
            excluded_branches = []

        branch_data = {}
        mirrors = self.Entropy.get_remote_mirrors(repo)
        for uri in mirrors:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            self.Entropy.updateProgress(
                "[repo:%s] %s: %s => %s" % (
                    brown(repo),
                    blue(_("looking for file in mirror")),
                    darkgreen(crippled_uri),
                    filename,
                ),
                importance = 1,
                type = "info",
                header = brown(" @@ ")
            )

            branches_path = self.Entropy.get_remote_database_relative_path(repo)
            txc = self.Entropy.Transceiver(uri)
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

                    tmp_dir = tempfile.mkdtemp()
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
                        down_f = open(down_path)
                        branch_data[branch] = down_f.read()
                        down_f.close()

                    shutil.rmtree(tmp_dir, True)

        return branch_data

    def lock_mirrors(self, lock = True, mirrors = None, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        if not mirrors:
            mirrors = self.Entropy.get_remote_mirrors(repo)

        issues = False
        for uri in mirrors:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            lock_text = _("unlocking")
            if lock:
                lock_text = _("locking")
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s %s" % (
                    brown(repo),
                    darkgreen(crippled_uri),
                    bold(lock_text),
                    blue("%s...") % (_("mirror"),),
                ),
                importance = 1,
                type = "info",
                header = brown(" * "),
                back = True
            )

            base_path = os.path.join(
                self.Entropy.get_remote_database_relative_path(repo),
                self.SystemSettings['repositories']['branch'])
            lock_file = os.path.join(base_path,
                etpConst['etpdatabaselockfile'])

            txc = self.Entropy.Transceiver(uri)
            txc.set_verbosity(False)

            with txc as handler:

                if lock and handler.is_file(lock_file):
                    self.Entropy.updateProgress(
                        "[repo:%s|%s] %s" % (
                                brown(repo),
                                darkgreen(crippled_uri),
                                blue(_("mirror already locked")),
                        ),
                        importance = 1,
                        type = "info",
                        header = darkgreen(" * ")
                    )
                    continue

                elif not lock and not handler.is_file(lock_file):
                    self.Entropy.updateProgress(
                        "[repo:%s|%s] %s" % (
                                brown(repo),
                                darkgreen(crippled_uri),
                                blue(_("mirror already unlocked")),
                        ),
                        importance = 1,
                        type = "info",
                        header = darkgreen(" * ")
                    )
                    continue

                if lock:
                    rc_lock = self._do_mirror_lock(uri, handler, repo = repo)
                else:
                    rc_lock = self._do_mirror_unlock(uri, handler, repo = repo)

            if not rc_lock:
                issues = True

        if not issues:
            db_taint_file = self.Entropy.get_local_database_taint_file(repo)
            if os.path.isfile(db_taint_file):
                os.remove(db_taint_file)

        return issues


    def lock_mirrors_for_download(self, lock = True, mirrors = None,
        repo = None):
        """
        This functions makes entropy clients to not download anything
        from the chosen mirrors. it is used to avoid clients to
        download databases while we're uploading a new one
        """

        if mirrors is None:
            mirrors = []

        if repo is None:
            repo = self.Entropy.default_repository

        if not mirrors:
            mirrors = self.Entropy.get_remote_mirrors(repo)

        issues = False
        for uri in mirrors:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            lock_text = _("unlocking")
            if lock:
                lock_text = _("locking")
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s %s..." % (
                            blue(repo),
                            red(crippled_uri),
                            bold(lock_text),
                            blue(_("mirror for download")),
                    ),
                importance = 1,
                type = "info",
                header = red(" @@ "),
                back = True
            )

            lock_file = etpConst['etpdatabasedownloadlockfile']
            my_path = os.path.join(
                self.Entropy.get_remote_database_relative_path(repo),
                self.SystemSettings['repositories']['branch'])
            lock_file = os.path.join(my_path, lock_file)

            txc = self.Entropy.Transceiver(uri)
            txc.set_verbosity(False)

            with txc as handler:

                if lock and handler.is_file(lock_file):
                    self.Entropy.updateProgress(
                        "[repo:%s|%s] %s" % (
                            blue(repo),
                            red(crippled_uri),
                            blue(_("mirror already locked for download")),
                        ),
                        importance = 1,
                        type = "info",
                        header = red(" @@ ")
                    )
                    continue

                elif not lock and not handler.is_file(lock_file):
                    self.Entropy.updateProgress(
                        "[repo:%s|%s] %s" % (
                            blue(repo),
                            red(crippled_uri),
                            blue(_("mirror already unlocked for download")),
                        ),
                        importance = 1,
                        type = "info",
                        header = red(" @@ ")
                    )
                    continue

                if lock:
                    rc_lock = self._do_mirror_lock(uri, handler, dblock = False,
                        repo = repo)
                else:
                    rc_lock = self._do_mirror_unlock(uri, handler,
                        dblock = False, repo = repo)
                if not rc_lock:
                    issues = True

        return issues

    def _do_mirror_lock(self, uri, txc_handler, dblock = True, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        my_path = os.path.join(
            self.Entropy.get_remote_database_relative_path(repo),
            self.SystemSettings['repositories']['branch'])

        # create path to lock file if it doesn't exist
        if not txc_handler.is_dir(my_path):
            txc_handler.makedirs(my_path)

        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        lock_string = ''

        if dblock:
            self.create_local_database_lockfile(repo)
            lock_file = self.get_database_lockfile(repo)
        else:
            # locking/unlocking mirror1 for download
            lock_string = _('for download')
            self.create_local_database_download_lockfile(repo)
            lock_file = self.get_database_download_lockfile(repo)

        remote_path = os.path.join(my_path, os.path.basename(lock_file))

        rc_upload = txc_handler.upload(lock_file, remote_path)
        if rc_upload:
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s %s" % (
                    blue(repo),
                    red(crippled_uri),
                    blue(_("mirror successfully locked")),
                    blue(lock_string),
                ),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )
        else:
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s: %s - %s %s" % (
                    blue(repo),
                    red(crippled_uri),
                    blue("lock error"),
                    rc_upload,
                    blue(_("mirror not locked")),
                    blue(lock_string),
                ),
                importance = 1,
                type = "error",
                header = darkred(" * ")
            )
            self.remove_local_database_lockfile(repo)

        return rc_upload


    def _do_mirror_unlock(self, uri, txc_handler, dblock = True, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        my_path = os.path.join(
            self.Entropy.get_remote_database_relative_path(repo),
            self.SystemSettings['repositories']['branch'])

        crippled_uri = EntropyTransceiver.get_uri_name(uri)

        if dblock:
            dbfile = etpConst['etpdatabaselockfile']
        else:
            dbfile = etpConst['etpdatabasedownloadlockfile']

        # make sure
        remote_path = os.path.join(my_path, os.path.basename(dbfile))

        rc_delete = txc_handler.delete(remote_path)
        if rc_delete:
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s" % (
                            blue(repo),
                            red(crippled_uri),
                            blue(_("mirror successfully unlocked")),
                    ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
            if dblock:
                self.remove_local_database_lockfile(repo)
            else:
                self.remove_local_database_download_lockfile(repo)
        else:
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s: %s - %s" % (
                    blue(repo),
                    red(crippled_uri),
                    blue(_("unlock error")),
                    rc_delete,
                    blue(_("mirror not unlocked")),
                ),
                importance = 1,
                type = "error",
                header = darkred(" * ")
            )

        return rc_delete

    def get_database_lockfile(self, repo = None):
        if repo is None:
            repo = self.Entropy.default_repository
        return os.path.join(self.Entropy.get_local_database_dir(repo),
            etpConst['etpdatabaselockfile'])

    def get_database_download_lockfile(self, repo = None):
        if repo is None:
            repo = self.Entropy.default_repository
        return os.path.join(self.Entropy.get_local_database_dir(repo),
            etpConst['etpdatabasedownloadlockfile'])

    def create_local_database_download_lockfile(self, repo = None):
        if repo is None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_download_lockfile(repo)
        f_lock = open(lock_file, "w")
        f_lock.write("download locked")
        f_lock.flush()
        f_lock.close()

    def create_local_database_lockfile(self, repo = None):
        if repo is None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_lockfile(repo)
        f_lock = open(lock_file, "w")
        f_lock.write("database locked")
        f_lock.flush()
        f_lock.close()

    def remove_local_database_lockfile(self, repo = None):
        if repo is None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_lockfile(repo)
        if os.path.isfile(lock_file):
            os.remove(lock_file)

    def remove_local_database_download_lockfile(self, repo = None):
        if repo is None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_download_lockfile(repo)
        if os.path.isfile(lock_file):
            os.remove(lock_file)

    def download_package(self, uri, pkg_relative_path, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        pkg_to_join_path = '/'.join(pkg_relative_path.split('/')[2:])
        pkgfile = os.path.basename(pkg_relative_path)
        crippled_uri = EntropyTransceiver.get_uri_name(uri)

        tries = 0
        while tries < 5:

            tries += 1
            txc = self.Entropy.Transceiver(uri)
            with txc as handler:

                self.Entropy.updateProgress(
                    "[repo:%s|%s|#%s] %s: %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        brown(str(tries)),
                        blue(_("connecting to download package")),
                        darkgreen(pkg_to_join_path),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * "),
                    back = True
                )

                remote_path = os.path.join(
                    self.Entropy.get_remote_packages_relative_path(repo),
                    pkg_to_join_path)
                download_path = os.path.join(
                    self.Entropy.get_local_packages_directory(repo),
                    pkg_to_join_path)
                download_dir = os.path.dirname(download_path)

                self.Entropy.updateProgress(
                    "[repo:%s|%s|#%s] %s: %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        brown(str(tries)),
                        blue(_("downloading package")),
                        darkgreen(remote_path),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )

                if (not os.path.isdir(download_dir)) and \
                    (not os.access(download_dir, os.R_OK)):
                    os.makedirs(download_dir)

                rc_download = handler.download(remote_path, download_path)
                if not rc_download:
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|#%s] %s: %s %s" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            brown(str(tries)),
                            blue(_("package")),
                            darkgreen(pkg_to_join_path),
                            blue(_("does not exist")),
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    return rc_download

                dbconn = self.Entropy.open_server_repository(read_only = True,
                    no_upload = True, repo = repo)
                idpackage = dbconn.getIDPackageFromDownload(pkg_relative_path)
                if idpackage == -1:
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|#%s] %s: %s %s" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            brown(str(tries)),
                            blue(_("package")),
                            darkgreen(pkg_relative_path),
                            blue(_("is not listed in the repository !")),
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    return False

                storedmd5 = dbconn.retrieveDigest(idpackage)
                self.Entropy.updateProgress(
                    "[repo:%s|%s|#%s] %s: %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        brown(str(tries)),
                        blue(_("verifying checksum of package")),
                        darkgreen(pkg_relative_path),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * "),
                    back = True
                )

                md5check = self.entropyTools.compare_md5(download_path, storedmd5)
                if md5check:
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|#%s] %s: %s %s" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            brown(str(tries)),
                            blue(_("package")),
                            darkgreen(pkg_relative_path),
                            blue(_("downloaded successfully")),
                        ),
                        importance = 1,
                        type = "info",
                        header = darkgreen(" * ")
                    )
                    return True
                else:
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|#%s] %s: %s %s" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            brown(str(tries)),
                            blue(_("package")),
                            darkgreen(pkg_relative_path),
                            blue(_("checksum does not match. re-downloading...")),
                        ),
                        importance = 1,
                        type = "warning",
                        header = darkred(" * ")
                    )
                    if os.path.isfile(download_path):
                        os.remove(download_path)

        # if we get here it means the files hasn't been downloaded properly
        self.Entropy.updateProgress(
            "[repo:%s|%s|#%s] %s: %s %s" % (
                brown(repo),
                darkgreen(crippled_uri),
                brown(str(tries)),
                blue(_("package")),
                darkgreen(pkg_relative_path),
                blue(_("seems broken. Consider to re-package it. Giving up!")),
            ),
            importance = 1,
            type = "error",
            header = darkred(" !!! ")
        )
        return False

    def _get_remote_db_status(self, uri, repo):

        sys_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        db_format = sys_set['database_file_format']
        cmethod = etpConst['etpdatabasecompressclasses'].get(db_format)
        if cmethod is None:
            raise InvalidDataType("InvalidDataType: %s." % (
                    _("Wrong database compression method passed"),
                )
            )
        remote_dir = os.path.join(
            self.Entropy.get_remote_database_relative_path(repo),
            self.SystemSettings['repositories']['branch'])

        # let raise exception if connection is impossible
        txc = self.Entropy.Transceiver(uri)
        with txc as handler:

            compressedfile = etpConst[cmethod[2]]
            rc1 = handler.is_file(os.path.join(remote_dir, compressedfile))

            rev_file = self.Entropy.get_local_database_revision_file(repo)
            revfilename = os.path.basename(rev_file)
            rc2 = handler.is_file(os.path.join(remote_dir, revfilename))

            revision = 0
            if not (rc1 and rc2):
                return [uri, revision]

            tmp_fd, rev_tmp_path = tempfile.mkstemp()

            dlcount = 5
            dled = False
            while dlcount:
                remote_rev_path = os.path.join(remote_dir, revfilename)
                dled = handler.download(remote_rev_path, rev_tmp_path)
                if dled:
                    break
                dlcount -= 1
            os.close(tmp_fd)

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            if os.access(rev_tmp_path, os.R_OK) and \
                os.path.isfile(rev_tmp_path):

                f_rev = open(rev_tmp_path, "r")
                try:
                    revision = int(f_rev.readline().strip())
                except ValueError:
                    mytxt = _("mirror hasn't valid database revision file")
                    self.Entropy.updateProgress(
                        "[repo:%s|%s] %s: %s" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            blue(mytxt),
                            bold(revision),
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    revision = 0
                f_rev.close()

            elif dlcount == 0:
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s: %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        blue(_("unable to download repository revision")),
                        bold(revision),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                revision = 0

            else:
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s: %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        blue(_("mirror doesn't have valid revision file")),
                        bold(revision),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                revision = 0

            os.remove(rev_tmp_path)
            return [uri, revision]

    def get_remote_databases_status(self, repo = None, mirrors = None):

        if repo is None:
            repo = self.Entropy.default_repository
        if not mirrors:
            mirrors = self.Entropy.get_remote_mirrors(repo)

        data = []
        for uri in mirrors:
            data.append(self._get_remote_db_status(uri, repo))

        return data

    def is_local_database_locked(self, repo = None):
        local_repo = repo
        if local_repo is None:
            local_repo = self.Entropy.default_repository
        lock_file = self.get_database_lockfile(local_repo)
        return os.path.isfile(lock_file)

    def get_mirrors_lock(self, repo = None):

        dbstatus = []
        remote_dir = os.path.join(
            self.Entropy.get_remote_database_relative_path(repo),
            self.SystemSettings['repositories']['branch'])
        lock_file = os.path.join(remote_dir, etpConst['etpdatabaselockfile'])
        down_lock_file = os.path.join(remote_dir,
            etpConst['etpdatabasedownloadlockfile'])

        for uri in self.Entropy.get_remote_mirrors(repo):
            data = [uri, False, False]

            # let raise exception if connection is impossible
            txc = self.Entropy.Transceiver(uri)
            with txc as handler:
                if handler.is_file(lock_file):
                    # upload locked
                    data[1] = True
                if handler.is_file(down_lock_file):
                    # download locked
                    data[2] = True
                dbstatus.append(data)

        return dbstatus

    def download_notice_board(self, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository
        mirrors = self.Entropy.get_remote_mirrors(repo)
        rss_path = self.Entropy.get_local_database_notice_board_file(repo)
        mytmpdir = self.entropyTools.get_random_temp_file()
        os.makedirs(mytmpdir)

        self.Entropy.updateProgress(
            "[repo:%s] %s %s" % (
                brown(repo),
                blue(_("downloading notice board from mirrors to")),
                red(rss_path),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )

        downloaded = False
        for uri in mirrors:
            crippled_uri = EntropyTransceiver.get_uri_name(uri)
            downloader = self.TransceiverServerHandler(
                self.Entropy, [uri],
                [rss_path], download = True,
                local_basedir = mytmpdir, critical_files = [rss_path],
                repo = repo
            )
            errors, m_fine_uris, m_broken_uris = downloader.go()
            if not errors:
                self.Entropy.updateProgress(
                    "[repo:%s] %s: %s" % (
                        brown(repo),
                        blue(_("notice board downloaded successfully from")),
                        red(crippled_uri),
                    ),
                    importance = 1,
                    type = "info",
                    header = blue(" @@ ")
                )
                downloaded = True
                break

        if downloaded:
            shutil.move(os.path.join(mytmpdir, os.path.basename(rss_path)),
                rss_path)

        return downloaded

    def upload_notice_board(self, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository
        mirrors = self.Entropy.get_remote_mirrors(repo)
        rss_path = self.Entropy.get_local_database_notice_board_file(repo)

        self.Entropy.updateProgress(
            "[repo:%s] %s %s" % (
                    brown(repo),
                    blue(_("uploading notice board from")),
                    red(rss_path),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )

        uploader = self.TransceiverServerHandler(
            self.Entropy,
            mirrors,
            [rss_path],
            critical_files = [rss_path],
            repo = repo
        )
        errors, m_fine_uris, m_broken_uris = uploader.go()
        if errors:
            m_broken_uris = sorted(m_broken_uris)
            m_broken_uris = [EntropyTransceiver.get_uri_name(x) \
                for x in m_broken_uris]
            self.Entropy.updateProgress(
                "[repo:%s] %s %s" % (
                        brown(repo),
                        blue(_("notice board upload failed on")),
                        red(', '.join(m_broken_uris)),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            return False
        self.Entropy.updateProgress(
            "[repo:%s] %s" % (
                    brown(repo),
                    blue(_("notice board upload success")),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )
        return True


    def update_notice_board(self, title, notice_text, link = None, repo = None):

        rss_title = "%s Notice Board" % (self.SystemSettings['system']['name'],)
        rss_description = "Inform about important distribution activities."
        rss_path = self.Entropy.get_local_database_notice_board_file(repo)
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if not link:
            link = srv_set['rss']['website_url']

        self.download_notice_board(repo)
        rss_main = RSS(rss_path, rss_title, rss_description,
            maxentries = 20)
        rss_main.add_item(title, link, description = notice_text)
        rss_main.write_changes()
        status = self.upload_notice_board(repo)
        return status

    def read_notice_board(self, do_download = True, repo = None):

        rss_path = self.Entropy.get_local_database_notice_board_file(repo)
        if do_download:
            self.download_notice_board(repo)
        if not (os.path.isfile(rss_path) and os.access(rss_path, os.R_OK)):
            return None
        rss_main = RSS(rss_path, '', '')
        return rss_main.get_entries()

    def remove_from_notice_board(self, identifier, repo = None):

        rss_path = self.Entropy.get_local_database_notice_board_file(repo)
        rss_title = "%s Notice Board" % (self.SystemSettings['system']['name'],)
        rss_description = "Inform about important distribution activities."
        if not (os.path.isfile(rss_path) and os.access(rss_path, os.R_OK)):
            return 0
        rss_main = RSS(rss_path, rss_title, rss_description)
        data = rss_main.remove_entry(identifier)
        rss_main.write_changes()
        return data

    def update_rss_feed(self, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        product = self.SystemSettings['repositories']['product']
        #db_dir = self.Entropy.get_local_database_dir(repo)
        rss_path = self.Entropy.get_local_database_rss_file(repo)
        rss_light_path = self.Entropy.get_local_database_rsslight_file(repo)
        rss_dump_name = repo + etpConst['rss-dump-name']
        db_revision_path = self.Entropy.get_local_database_revision_file(repo)

        rss_title = "%s Online Repository Status" % (
            self.SystemSettings['system']['name'],)
        rss_description = \
            "Keep you updated on what's going on in the %s Repository." % (
                self.SystemSettings['system']['name'],)

        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']

        rss_main = RSS(rss_path, rss_title, rss_description,
            maxentries = srv_set['rss']['max_entries'])
        # load dump
        db_actions = self.Cacher.pop(rss_dump_name)
        if db_actions:
            try:
                f_rev = open(db_revision_path)
                revision = f_rev.readline().strip()
                f_rev.close()
            except (IOError, OSError):
                revision = "N/A"
            commitmessage = ''
            if self.Entropy.rssMessages['commitmessage']:
                commitmessage = ' :: ' + \
                    self.Entropy.rssMessages['commitmessage']

            title = ": " + self.SystemSettings['system']['name'] + " " + \
                product[0].upper() + product[1:] + " " + \
                self.SystemSettings['repositories']['branch'] + \
                " :: Revision: " + revision + commitmessage

            link = srv_set['rss']['base_url']
            # create description
            added_items = db_actions.get("added")

            if added_items:
                for atom in sorted(added_items):
                    mylink = link + "?search=" + atom.split("~")[0] + \
                        "&arch=" + etpConst['currentarch'] + "&product="+product
                    description = atom + ": " + added_items[atom]['description']
                    rss_main.add_item(title = "Added/Updated" + title,
                        link = mylink, description = description)
            removed_items = db_actions.get("removed")

            if removed_items:
                for atom in sorted(removed_items):
                    description = atom + ": " + \
                        removed_items[atom]['description']
                    rss_main.add_item(title = "Removed" + title, link = link,
                        description = description)

            light_items = db_actions.get('light')
            if light_items:
                rss_light = RSS(rss_light_path, rss_title, rss_description,
                    maxentries = srv_set['rss']['light_max_entries'])
                for atom in sorted(light_items):
                    mylink = link + "?search=" + atom.split("~")[0] + \
                        "&arch=" + etpConst['currentarch'] + "&product=" + \
                        product
                    description = light_items[atom]['description']
                    rss_light.add_item(title = "[" + revision + "] " + atom,
                        link = mylink, description = description)
                rss_light.write_changes()

        rss_main.write_changes()
        self.Entropy.rssMessages.clear()
        self.dumpTools.removeobj(rss_dump_name)


    def dump_database_to_file(self, db_path, destination_path, opener,
        exclude_tables = None, repo = None):

        if not exclude_tables:
            exclude_tables = []

        f_out = opener(destination_path, "wb")
        dbconn = self.Entropy.open_server_repository(db_path,
            just_reading = True, repo = repo, do_treeupdates = False)
        dbconn.doDatabaseExport(f_out, exclude_tables = exclude_tables)
        self.Entropy.close_server_database(dbconn)
        f_out.close()

    def create_file_checksum(self, file_path, checksum_path):
        mydigest = self.entropyTools.md5sum(file_path)
        f_ck = open(checksum_path, "w")
        mystring = "%s  %s\n" % (mydigest, os.path.basename(file_path),)
        f_ck.write(mystring)
        f_ck.flush()
        f_ck.close()

    def compress_file(self, file_path, destination_path, opener):
        f_out = opener(destination_path, "wb")
        f_in = open(file_path, "rb")
        data = f_in.read(8192)
        while data:
            f_out.write(data)
            data = f_in.read(8192)
        f_in.close()
        if hasattr(f_out, 'flush'):
            f_out.flush()
        f_out.close()

    def get_files_to_sync(self, cmethod, download = False, repo = None,
        disabled_eapis = None):

        if disabled_eapis is None:
            disabled_eapis = []

        critical = []
        extra_text_files = []
        data = {}
        data['database_revision_file'] = \
            self.Entropy.get_local_database_revision_file(repo)
        extra_text_files.append(data['database_revision_file'])
        critical.append(data['database_revision_file'])


        # branch migration support scripts
        post_branch_mig_file = self.Entropy.get_local_post_branch_mig_script(
            repo)
        if os.path.isfile(post_branch_mig_file) or download:
            data['database_post_branch_hop_script'] = post_branch_mig_file
            extra_text_files.append(data['database_post_branch_hop_script'])

        post_branch_upg_file = self.Entropy.get_local_post_branch_upg_script(
            repo)
        if os.path.isfile(post_branch_upg_file) or download:
            data['database_post_branch_upgrade_script'] = post_branch_upg_file
            extra_text_files.append(data['database_post_branch_upgrade_script'])


        database_ts_file = self.Entropy.get_local_database_timestamp_file(repo)
        if os.path.isfile(database_ts_file) or download:
            data['database_timestamp_file'] = database_ts_file
            if not download:
                critical.append(database_ts_file)

        database_package_mask_file = \
            self.Entropy.get_local_database_mask_file(repo)
        extra_text_files.append(database_package_mask_file)
        if os.path.isfile(database_package_mask_file) or download:
            data['database_package_mask_file'] = database_package_mask_file
            if not download:
                critical.append(data['database_package_mask_file'])

        database_package_system_mask_file = \
            self.Entropy.get_local_database_system_mask_file(repo)
        extra_text_files.append(database_package_system_mask_file)
        if os.path.isfile(database_package_system_mask_file) or download:
            data['database_package_system_mask_file'] = \
                database_package_system_mask_file
            if not download:
                critical.append(data['database_package_system_mask_file'])

        database_package_confl_tagged_file = \
            self.Entropy.get_local_database_confl_tagged_file(repo)
        extra_text_files.append(database_package_confl_tagged_file)
        if os.path.isfile(database_package_confl_tagged_file) or download:
            data['database_package_confl_tagged_file'] = \
                database_package_confl_tagged_file
            if not download:
                critical.append(data['database_package_confl_tagged_file'])

        database_license_whitelist_file = \
            self.Entropy.get_local_database_licensewhitelist_file(repo)
        extra_text_files.append(database_license_whitelist_file)
        if os.path.isfile(database_license_whitelist_file) or download:
            data['database_license_whitelist_file'] = \
                database_license_whitelist_file
            if not download:
                critical.append(data['database_license_whitelist_file'])

        exp_based_pkgs_removal_file = \
            self.Entropy.get_local_exp_based_pkgs_rm_whitelist_file(repo)
        extra_text_files.append(exp_based_pkgs_removal_file)
        if os.path.isfile(exp_based_pkgs_removal_file) or download:
            data['exp_based_pkgs_removal_file'] = exp_based_pkgs_removal_file
            if not download:
                critical.append(data['exp_based_pkgs_removal_file'])

        database_rss_file = self.Entropy.get_local_database_rss_file(repo)
        if os.path.isfile(database_rss_file) or download:
            data['database_rss_file'] = database_rss_file
            if not download:
                critical.append(data['database_rss_file'])
        database_rss_light_file = \
            self.Entropy.get_local_database_rsslight_file(repo)

        extra_text_files.append(database_rss_light_file)
        if os.path.isfile(database_rss_light_file) or download:
            data['database_rss_light_file'] = database_rss_light_file
            if not download:
                critical.append(data['database_rss_light_file'])

        pkglist_file = self.Entropy.get_local_pkglist_file(repo)
        data['pkglist_file'] = pkglist_file
        if not download:
            critical.append(data['pkglist_file'])

        critical_updates_file = self.Entropy.get_local_critical_updates_file(
            repo)
        if os.path.isfile(critical_updates_file) or download:
            data['critical_updates_file'] = critical_updates_file
            extra_text_files.append(data['critical_updates_file'])
            if not download:
                critical.append(data['critical_updates_file'])

        keywords_file = self.Entropy.get_local_database_keywords_file(
            repo)
        if os.path.isfile(keywords_file) or download:
            data['keywords_file'] = keywords_file
            extra_text_files.append(data['keywords_file'])
            if not download:
                critical.append(data['keywords_file'])

        # EAPI 2,3
        if not download: # we don't need to get the dump

            if 3 not in disabled_eapis:

                data['metafiles_path'] = \
                    self.Entropy.get_local_database_compressed_metafiles_file(
                        repo)
                critical.append(data['metafiles_path'])

            if 2 not in disabled_eapis:

                data['dump_path_light'] = os.path.join(
                    self.Entropy.get_local_database_dir(repo),
                    etpConst[cmethod[5]])
                critical.append(data['dump_path_light'])

                data['dump_path_digest_light'] = os.path.join(
                    self.Entropy.get_local_database_dir(repo),
                    etpConst[cmethod[6]])
                critical.append(data['dump_path_digest_light'])

        # EAPI 1
        if 1 not in disabled_eapis:

            data['compressed_database_path'] = os.path.join(
                self.Entropy.get_local_database_dir(repo), etpConst[cmethod[2]])
            critical.append(data['compressed_database_path'])
            data['compressed_database_path_light'] = os.path.join(
                self.Entropy.get_local_database_dir(repo), etpConst[cmethod[7]])

            data['database_path_digest'] = os.path.join(
                self.Entropy.get_local_database_dir(repo),
                etpConst['etpdatabasehashfile']
            )
            critical.append(data['database_path_digest'])

            data['compressed_database_path_digest'] = os.path.join(
                self.Entropy.get_local_database_dir(repo),
                etpConst[cmethod[2]] + etpConst['packagesmd5fileext']
            )
            critical.append(data['compressed_database_path_digest'])

            data['compressed_database_path_digest_light'] = os.path.join(
                self.Entropy.get_local_database_dir(repo),
                etpConst[cmethod[8]]
            )
            critical.append(data['compressed_database_path_digest_light'])


        # SSL cert file, just for reference
        ssl_ca_cert = self.Entropy.get_local_database_ca_cert_file()
        extra_text_files.append(ssl_ca_cert)
        if os.path.isfile(ssl_ca_cert):
            data['ssl_ca_cert_file'] = ssl_ca_cert
            if not download:
                critical.append(ssl_ca_cert)
        ssl_server_cert = self.Entropy.get_local_database_server_cert_file()
        extra_text_files.append(ssl_server_cert)
        if os.path.isfile(ssl_server_cert):
            data['ssl_server_cert_file'] = ssl_server_cert
            if not download:
                critical.append(ssl_server_cert)

        # Some information regarding how packages are built
        spm_files = [
            (etpConst['spm']['global_make_conf'], "global_make_conf"),
            (etpConst['spm']['global_package_keywords'],
                "global_package_keywords"),
            (etpConst['spm']['global_package_use'], "global_package_use"),
            (etpConst['spm']['global_package_mask'], "global_package_mask"),
            (etpConst['spm']['global_package_unmask'], "global_package_unmask"),
        ]
        for myfile, myname in spm_files:
            if os.path.isfile(myfile) and os.access(myfile, os.R_OK):
                data[myname] = myfile
            extra_text_files.append(myfile)

        make_profile = etpConst['spm']['global_make_profile']
        rnd_tmp_file = self.Entropy.entropyTools.get_random_temp_file()
        mytmpdir = os.path.dirname(rnd_tmp_file)
        mytmpfile = os.path.join(mytmpdir,
            etpConst['spm']['global_make_profile_link_name'])
        extra_text_files.append(mytmpfile)

        if os.path.islink(make_profile):
            mylink = os.readlink(make_profile)
            f_mkp = open(mytmpfile, "w")
            f_mkp.write(mylink)
            f_mkp.flush()
            f_mkp.close()
            data['global_make_profile'] = mytmpfile

        return data, critical, extra_text_files

    def _show_package_sets_messages(self, repo):

        self.Entropy.updateProgress(
            "[repo:%s] %s:" % (
                brown(repo),
                blue(_("configured package sets")),
            ),
            importance = 0,
            type = "info",
            header = darkgreen(" * ")
        )
        sets_data = self.Entropy.package_set_list(matchRepo = [repo])
        if not sets_data:
            self.Entropy.updateProgress(
                "%s" % (_("None configured"),),
                importance = 0,
                type = "info",
                header = brown("    # ")
            )
            return
        for s_repo, s_name, s_sets in sets_data:
            self.Entropy.updateProgress(
                blue("%s" % (s_name,)),
                importance = 0,
                type = "info",
                header = brown("    # ")
            )

    def _show_eapi3_upload_messages(self, crippled_uri, database_path, repo):

        self.Entropy.updateProgress(
            "[repo:%s|%s|%s:%s] %s" % (
                brown(repo),
                darkgreen(crippled_uri),
                red("EAPI"),
                bold("3"),
                blue(_("preparing uncompressed database for the upload")),
            ),
            importance = 0,
            type = "info",
            header = darkgreen(" * ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("database path"), blue(database_path),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

    def _show_eapi2_upload_messages(self, crippled_uri, database_path,
        upload_data, cmethod, repo):

        if repo is None:
            repo = self.Entropy.default_repository

        self.Entropy.updateProgress(
            "[repo:%s|%s|%s:%s] %s" % (
                brown(repo),
                darkgreen(crippled_uri),
                red("EAPI"),
                bold("2"),
                blue(_("creating compressed database dump + checksum")),
            ),
            importance = 0,
            type = "info",
            header = darkgreen(" * ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("database path"), blue(database_path),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (
                _("dump light"),
                blue(upload_data['dump_path_light']),
            ),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (
                _("dump light checksum"),
                blue(upload_data['dump_path_digest_light']),
            ),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

        self.Entropy.updateProgress(
            "%s: %s" % (_("opener"), blue(str(cmethod[0])),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

    def _show_eapi1_upload_messages(self, crippled_uri, database_path,
        upload_data, cmethod, repo):

        self.Entropy.updateProgress(
            "[repo:%s|%s|%s:%s] %s" % (
                brown(repo),
                darkgreen(crippled_uri),
                red("EAPI"),
                bold("1"),
                blue(_("compressing database + checksum")),
            ),
            importance = 0,
            type = "info",
            header = darkgreen(" * "),
            back = True
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("database path"), blue(database_path),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (
                _("compressed database path"),
                blue(upload_data['compressed_database_path']),
            ),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (
                _("database checksum"),
                blue(upload_data['database_path_digest']),
            ),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (
                _("compressed checksum"),
                blue(upload_data['compressed_database_path_digest']),
            ),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("opener"), blue(str(cmethod[0])),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

    def _create_metafiles_file(self, compressed_dest_path, file_list, repo):

        found_file_list = [x for x in file_list if os.path.isfile(x) and \
            os.path.isfile(x) and os.access(x, os.R_OK)]
        not_found_file_list = ["%s\n" % (os.path.basename(x),) for x in \
            file_list if x not in found_file_list]
        metafile_not_found_file = \
            self.Entropy.get_local_database_metafiles_not_found_file(repo)

        f_meta = open(metafile_not_found_file, "w")
        f_meta.writelines(not_found_file_list)
        f_meta.flush()
        f_meta.close()
        found_file_list.append(metafile_not_found_file)
        if os.path.isfile(compressed_dest_path):
            os.remove(compressed_dest_path)
        self.entropyTools.compress_files(compressed_dest_path, found_file_list)

    def mirror_lock_check(self, uri, repo = None):
        """
        Return whether mirror is locked.
        """

        if repo is None:
            repo = self.Entropy.default_repository
        gave_up = False

        lock_file = self.get_database_lockfile(repo)
        lock_filename = os.path.basename(lock_file)

        remote_dir = os.path.join(
            self.Entropy.get_remote_database_relative_path(repo),
            self.SystemSettings['repositories']['branch'])
        remote_lock_file = os.path.join(remote_dir, lock_filename)

        txc = self.Entropy.Transceiver(uri)
        with txc as handler:

            if not os.path.isfile(lock_file) and \
                handler.is_file(remote_lock_file):

                crippled_uri = EntropyTransceiver.get_uri_name(uri)
                self.Entropy.updateProgress(
                    "[repo:%s|%s|%s] %s, %s" % (
                        brown(str(repo)),
                        darkgreen(crippled_uri),
                        red(_("locking")),
                        darkblue(_("mirror already locked")),
                        blue(_("waiting up to 2 minutes before giving up")),
                    ),
                    importance = 1,
                    type = "warning",
                    header = brown(" * "),
                    back = True
                )

                unlocked = False
                count = 0
                while count < 120:
                    count += 1
                    time.sleep(1)
                    if not handler.is_file(remote_lock_file):
                        self.Entropy.updateProgress(
                            red("[repo:%s|%s|%s] %s !" % (
                                    repo,
                                    crippled_uri,
                                    _("locking"),
                                    _("mirror unlocked"),
                                )
                            ),
                            importance = 1,
                            type = "info",
                            header = darkgreen(" * ")
                        )
                        unlocked = True
                        break

                if not unlocked:
                    gave_up = True

        return gave_up

    def shrink_database_and_close(self, repo = None):
        dbconn = self.Entropy.open_server_repository(read_only = False,
            no_upload = True, repo = repo, indexing = False,
            do_treeupdates = False)
        dbconn.dropAllIndexes()
        dbconn.vacuum()
        dbconn.vacuum()
        dbconn.commitChanges()
        self.Entropy.close_server_database(dbconn)

    def update_repository_timestamp(self, repo = None):
        if repo is None:
            repo = self.Entropy.default_repository
        ts_file = self.Entropy.get_local_database_timestamp_file(repo)
        current_ts = self.Entropy.get_current_timestamp()
        ts_f = open(ts_file, "w")
        ts_f.write(current_ts)
        ts_f.flush()
        ts_f.close()

    def sync_database_treeupdates(self, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository
        dbconn = self.Entropy.open_server_repository(read_only = False,
            no_upload = True, repo = repo, do_treeupdates = False)
        # grab treeupdates from other databases and inject
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        server_repos = list(srv_set['repositories'].keys())
        all_actions = set()
        for myrepo in server_repos:

            # avoid __default__
            if myrepo == etpConst['clientserverrepoid']:
                continue

            mydbc = self.Entropy.open_server_repository(just_reading = True,
                repo = myrepo)
            actions = mydbc.listAllTreeUpdatesActions(no_ids_repos = True)
            for data in actions:
                all_actions.add(data)
            if not actions:
                continue
        backed_up_entries = dbconn.listAllTreeUpdatesActions()
        try:
            # clear first
            dbconn.removeTreeUpdatesActions(repo)
            dbconn.insertTreeUpdatesActions(all_actions, repo)
        except dbapi2.Error as err:
            self.entropyTools.print_traceback()
            mytxt = "%s, %s: %s. %s" % (
                _("Troubles with treeupdates"),
                _("error"),
                err,
                _("Bumping old data back"),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning"
            )
            # restore previous data
            dbconn.bumpTreeUpdatesActions(backed_up_entries)

        dbconn.commitChanges()
        self.Entropy.close_server_database(dbconn)

    def upload_database(self, uris, lock_check = False, pretend = False,
            repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        if srv_set['rss']['enabled']:
            self.update_rss_feed(repo = repo)

        upload_errors = False
        broken_uris = set()
        fine_uris = set()

        disabled_eapis = sorted(srv_set['disabled_eapis'])

        for uri in uris:

            db_format = srv_set['database_file_format']
            cmethod = etpConst['etpdatabasecompressclasses'].get(db_format)
            if cmethod is None:
                raise InvalidDataType("InvalidDataType: %s." % (
                        _("wrong database compression method passed"),
                    )
                )

            crippled_uri = EntropyTransceiver.get_uri_name(uri)
            database_path = self.Entropy.get_local_database_file(repo)

            if disabled_eapis:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|%s] %s: %s" % (
                        blue(repo),
                        red(crippled_uri),
                        darkgreen(_("upload")),
                        darkred(_("disabled EAPI")),
                        bold(', '.join([str(x) for x in disabled_eapis])),
                    ),
                    importance = 1,
                    type = "warning",
                    header = darkgreen(" * ")
                )

            # create/update timestamp file
            self.update_repository_timestamp(repo)
            # create pkglist service file
            self.Entropy.create_repository_pkglist(repo)

            upload_data, critical, text_files = self.get_files_to_sync(cmethod,
                repo = repo, disabled_eapis = disabled_eapis)

            if lock_check:
                given_up = self.mirror_lock_check(uri, repo = repo)
                if given_up:
                    upload_errors = True
                    broken_uris.add(uri)
                    continue

            self.lock_mirrors_for_download(True, [uri], repo = repo)

            self.Entropy.updateProgress(
                "[repo:%s|%s|%s] %s" % (
                    blue(repo),
                    red(crippled_uri),
                    darkgreen(_("upload")),
                    darkgreen(_("preparing to upload database to mirror")),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )

            # Package Sets info
            self._show_package_sets_messages(repo)
            self.sync_database_treeupdates(repo)
            self.Entropy.update_database_package_sets(repo)
            self.Entropy.close_server_databases()

            # backup current database to avoid re-indexing
            old_dbpath = self.Entropy.get_local_database_file(repo)
            backup_dbpath = old_dbpath + ".up_backup"
            copy_back = False
            if not pretend:
                try:
                    if os.access(backup_dbpath, os.R_OK) and \
                        os.path.isfile(backup_dbpath):
                        os.remove(backup_dbpath)

                    shutil.copy2(old_dbpath, backup_dbpath)
                    copy_back = True
                except shutil.Error:
                    copy_back = False

            self.shrink_database_and_close(repo)

            # EAPI 3
            if 3 not in disabled_eapis:
                self._create_metafiles_file(upload_data['metafiles_path'],
                    text_files, repo)
                self._show_eapi3_upload_messages(crippled_uri, database_path,
                    repo)

            # EAPI 2
            if 2 not in disabled_eapis:
                self._show_eapi2_upload_messages(crippled_uri, database_path,
                    upload_data, cmethod, repo)

                # create compressed dump + checksum
                self.dump_database_to_file(database_path,
                    upload_data['dump_path_light'], cmethod[0],
                    exclude_tables = ["content"], repo = repo)
                self.create_file_checksum(upload_data['dump_path_light'],
                    upload_data['dump_path_digest_light'])


            # EAPI 1
            if 1 not in disabled_eapis:
                self._show_eapi1_upload_messages(crippled_uri, database_path,
                    upload_data, cmethod, repo)

                # compress the database and create uncompressed
                # database checksum -- DEPRECATED
                self.compress_file(database_path,
                    upload_data['compressed_database_path'], cmethod[0])
                self.create_file_checksum(database_path,
                    upload_data['database_path_digest'])

                # create compressed database checksum
                self.create_file_checksum(
                    upload_data['compressed_database_path'],
                    upload_data['compressed_database_path_digest'])

                # create light version of the compressed db
                eapi1_dbfile = self.Entropy.get_local_database_file(repo)
                temp_eapi1_dbfile = eapi1_dbfile+".light"
                shutil.copy2(eapi1_dbfile, temp_eapi1_dbfile)
                # open and remove content table
                eapi1_tmp_dbconn = \
                    self.Entropy.ClientService.open_generic_database(
                        temp_eapi1_dbfile, indexing_override = False,
                        xcache = False)
                eapi1_tmp_dbconn.dropContent()
                eapi1_tmp_dbconn.commitChanges()
                eapi1_tmp_dbconn.vacuum()
                eapi1_tmp_dbconn.closeDB()

                # compress
                self.compress_file(temp_eapi1_dbfile,
                    upload_data['compressed_database_path_light'], cmethod[0])
                # go away, we don't need you anymore
                os.remove(temp_eapi1_dbfile)
                # create compressed light database checksum
                self.create_file_checksum(
                    upload_data['compressed_database_path_light'],
                    upload_data['compressed_database_path_digest_light'])

            if not pretend:
                # upload
                uploader = self.TransceiverServerHandler(
                    self.Entropy,
                    [uri],
                    [upload_data[x] for x in upload_data],
                    critical_files = critical,
                    repo = repo
                )
                errors, m_fine_uris, m_broken_uris = uploader.go()
                if errors:
                    my_broken_uris = sorted([
                        (EntropyTransceiver.get_uri_name(x[0]),
                            x[1]) for x in m_broken_uris])
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|%s] %s" % (
                            repo,
                            crippled_uri,
                            _("errors"),
                            _("upload failed, not unlocking and continuing"),
                        ),
                        importance = 0,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    # get reason
                    reason = my_broken_uris[0][1]
                    self.Entropy.updateProgress(
                        blue("%s: %s" % (_("reason"), reason,)),
                        importance = 0,
                        type = "error",
                        header = blue("    # ")
                    )
                    upload_errors = True
                    broken_uris |= m_broken_uris
                    continue

                # copy db back
                if copy_back and os.path.isfile(backup_dbpath):
                    self.Entropy.close_server_databases()
                    further_backup_dbpath = old_dbpath+".security_backup"
                    if os.path.isfile(further_backup_dbpath):
                        os.remove(further_backup_dbpath)
                    shutil.copy2(old_dbpath, further_backup_dbpath)
                    shutil.move(backup_dbpath, old_dbpath)

            # unlock
            self.lock_mirrors_for_download(False, [uri], repo = repo)
            fine_uris |= m_fine_uris

        if not fine_uris:
            upload_errors = True
        return upload_errors, broken_uris, fine_uris


    def download_database(self, uris, lock_check = False, pretend = False,
        repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        download_errors = False
        broken_uris = set()
        fine_uris = set()
        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        disabled_eapis = sorted(srv_set['disabled_eapis'])

        for uri in uris:

            db_format = srv_set['database_file_format']
            cmethod = etpConst['etpdatabasecompressclasses'].get(db_format)
            if cmethod is None:
                raise InvalidDataType("InvalidDataType: %s." % (
                        _("wrong database compression method passed"),
                    )
                )

            crippled_uri = EntropyTransceiver.get_uri_name(uri)
            database_path = self.Entropy.get_local_database_file(repo)
            database_dir_path = os.path.dirname(
                self.Entropy.get_local_database_file(repo))
            download_data, critical, text_files = self.get_files_to_sync(
                cmethod, download = True,
                repo = repo, disabled_eapis = disabled_eapis)
            mytmpdir = self.entropyTools.get_random_temp_file()
            os.makedirs(mytmpdir)

            self.Entropy.updateProgress(
                "[repo:%s|%s|%s] %s" % (
                    brown(repo),
                    darkgreen(crippled_uri),
                    red(_("download")),
                    blue(_("preparing to download database from mirror")),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
            files_to_sync = sorted(download_data.keys())
            for myfile in files_to_sync:
                self.Entropy.updateProgress(
                    "%s: %s" % (
                        blue(_("download path")),
                        brown(download_data[myfile]),
                    ),
                    importance = 0,
                    type = "info",
                    header = brown("    # ")
                )

            if lock_check:
                given_up = self.mirror_lock_check(uri, repo = repo)
                if given_up:
                    download_errors = True
                    broken_uris.add(uri)
                    continue

            # avoid having others messing while we're downloading
            self.lock_mirrors(True, [uri], repo = repo)

            if not pretend:
                # download
                downloader = self.TransceiverServerHandler(
                    self.Entropy, [uri],
                    [download_data[x] for x in download_data], download = True,
                    local_basedir = mytmpdir, critical_files = critical,
                    repo = repo
                )
                errors, m_fine_uris, m_broken_uris = downloader.go()
                if errors:
                    my_broken_uris = sorted([
                        (EntropyTransceiver.get_uri_name(x[0]),
                            x[1]) for x in m_broken_uris])
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|%s] %s" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            red(_("errors")),
                            blue(_("failed to download from mirror")),
                        ),
                        importance = 0,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    # get reason
                    reason = my_broken_uris[0][1]
                    self.Entropy.updateProgress(
                        blue("%s: %s" % (_("reason"), reason,)),
                        importance = 0,
                        type = "error",
                        header = blue("    # ")
                    )
                    download_errors = True
                    broken_uris |= m_broken_uris
                    self.lock_mirrors(False, [uri], repo = repo)
                    continue

                # all fine then, we need to move data from mytmpdir
                # to database_dir_path

                # EAPI 1 -- unpack database
                if 1 not in disabled_eapis:
                    compressed_db_filename = os.path.basename(
                        download_data['compressed_database_path'])
                    uncompressed_db_filename = os.path.basename(database_path)
                    compressed_file = os.path.join(mytmpdir,
                        compressed_db_filename)
                    uncompressed_file = os.path.join(mytmpdir,
                        uncompressed_db_filename)
                    self.entropyTools.uncompress_file(compressed_file,
                        uncompressed_file, cmethod[0])

                # now move
                for myfile in os.listdir(mytmpdir):
                    fromfile = os.path.join(mytmpdir, myfile)
                    tofile = os.path.join(database_dir_path, myfile)
                    shutil.move(fromfile, tofile)
                    self.Entropy.ClientService.setup_default_file_perms(tofile)

            if os.path.isdir(mytmpdir):
                shutil.rmtree(mytmpdir)
            if os.path.isdir(mytmpdir):
                os.rmdir(mytmpdir)


            fine_uris.add(uri)
            self.lock_mirrors(False, [uri], repo = repo)

        return download_errors, fine_uris, broken_uris

    def calculate_database_sync_queues(self, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        remote_status =  self.get_remote_databases_status(repo)
        local_revision = self.Entropy.get_local_database_revision(repo)
        upload_queue = []
        download_latest = ()

        # all mirrors are empty ? I rule
        if not [x for x in remote_status if x[1]]:
            upload_queue = remote_status[:]
        else:
            highest_remote_revision = max([x[1] for x in remote_status])

            if local_revision < highest_remote_revision:
                for remote_item in remote_status:
                    if remote_item[1] == highest_remote_revision:
                        download_latest = x
                        break

            if download_latest:
                upload_queue = [x for x in remote_status if \
                    (x[1] < highest_remote_revision)]
            else:
                upload_queue = [x for x in remote_status if \
                    (x[1] < local_revision)]

        return download_latest, upload_queue

    def sync_databases(self, no_upload = False, unlock_mirrors = False,
        repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        while True:

            db_locked = False
            if self.is_local_database_locked(repo):
                db_locked = True

            lock_data = self.get_mirrors_lock(repo)
            mirrors_locked = [x for x in lock_data if x[1]]

            if not mirrors_locked and db_locked:
                # mirrors not locked remotely but only locally
                mylock_file = self.get_database_lockfile(repo)
                if os.access(mylock_file, os.W_OK) and \
                    os.path.isfile(mylock_file):

                    os.remove(mylock_file)
                    continue

            break

        if mirrors_locked and not db_locked:
            mytxt = "%s, %s %s" % (
                _("Mirrors are locked, someone is working on the repository"),
                _("try again later"),
                "...",
            )
            raise OnlineMirrorError("OnlineMirrorError: %s" % (mytxt,))

        download_latest, upload_queue = self.calculate_database_sync_queues(
            repo)

        if not download_latest and not upload_queue:
            self.Entropy.updateProgress(
                "[repo:%s|%s] %s" % (
                    brown(repo),
                    red(_("sync")), # something short please
                    blue(_("database already in sync")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            return 0, set(), set()

        if download_latest:
            download_uri = download_latest[0]
            download_errors, fine_uris, broken_uris = self.download_database(
                [download_uri], repo = repo)
            if download_errors:
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s: %s" % (
                        brown(repo),
                        red(_("sync")),
                        blue(_("database sync failed")),
                        red(_("download issues")),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                return 1, fine_uris, broken_uris

        if upload_queue and not no_upload:

            # XXX QA checks,
            # please group them into entropy.qa

            srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
            base_repo = srv_set['base_repository_id']
            if base_repo is None:
                base_repo = repo

            base_deps_not_found = set()
            if base_repo != repo:
                base_deps_not_found = self.Entropy.dependencies_test(
                    repo = repo)

            deps_not_found = self.Entropy.dependencies_test(repo = repo)
            if (deps_not_found or base_deps_not_found) \
                and not self.Entropy.community_repo:

                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s: %s" % (
                        brown(repo),
                        red(_("sync")),
                        blue(_("database sync forbidden")),
                        red(_("dependencies_test() reported errors")),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                return 3, set(), set()

            problems = self.Entropy.check_config_file_updates()
            if problems:
                return 4, set(), set()

            self.Entropy.updateProgress(
                "[repo:%s|%s] %s" % (
                    brown(repo),
                    red(_("config files")), # something short please
                    blue(_("no configuration files to commit. All fine.")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True
            )

            uris = [x[0] for x in upload_queue]
            errors, fine_uris, broken_uris = self.upload_database(uris,
                repo = repo)
            if errors:
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s: %s" % (
                        brown(repo),
                        red(_("sync")),
                        blue(_("database sync failed")),
                        red(_("upload issues")),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                return 2, fine_uris, broken_uris


        self.Entropy.updateProgress(
            "[repo:%s|%s] %s" % (
                brown(repo),
                red(_("sync")),
                blue(_("database sync completed successfully")),
            ),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )

        if unlock_mirrors:
            self.lock_mirrors(False, repo = repo)
        return 0, set(), set()


    def calculate_local_upload_files(self, branch, repo = None):
        upload_files = 0
        upload_packages = set()
        upload_dir = os.path.join(self.Entropy.get_local_upload_directory(repo),
            branch)

        # check if it exists
        if not os.path.isdir(upload_dir):
            return upload_files, upload_packages

        pkg_ext = etpConst['packagesext']
        pkg_md5_ext = etpConst['packagesmd5fileext']
        for package in os.listdir(upload_dir):
            if package.endswith(pkg_ext) or package.endswith(pkg_md5_ext):
                upload_packages.add(package)
                if package.endswith(pkg_ext):
                    upload_files += 1

        return upload_files, upload_packages

    def calculate_local_package_files(self, branch, repo = None):
        local_files = 0
        local_packages = set()
        packages_dir = os.path.join(
            self.Entropy.get_local_packages_directory(repo), branch)

        if not os.path.isdir(packages_dir):
            os.makedirs(packages_dir)

        pkg_ext = etpConst['packagesext']
        pkg_md5_ext = etpConst['packagesmd5fileext']
        for package in os.listdir(packages_dir):
            if package.endswith(pkg_ext) or package.endswith(pkg_md5_ext):
                local_packages.add(package)
                if package.endswith(pkg_ext):
                    local_files += 1

        return local_files, local_packages


    def _show_local_sync_stats(self, upload_files, local_files):
        self.Entropy.updateProgress(
            "%s:" % (
                blue(_("Local statistics")),
            ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )
        self.Entropy.updateProgress(
            red("%s:\t\t%s %s" % (
                    blue(_("upload directory")),
                    bold(str(upload_files)),
                    red(_("files ready")),
                )
            ),
            importance = 0,
            type = "info",
            header = red(" @@ ")
        )
        self.Entropy.updateProgress(
            red("%s:\t\t%s %s" % (
                    blue(_("packages directory")),
                    bold(str(local_files)),
                    red(_("files ready")),
                )
            ),
            importance = 0,
            type = "info",
            header = red(" @@ ")
        )

    def _show_sync_queues(self, upload, download, removal, copy, metainfo,
        branch):

        # show stats
        for package, size in upload:
            package = darkgreen(os.path.basename(package))
            size = blue(self.entropyTools.bytes_into_human(size))
            self.Entropy.updateProgress(
                "[branch:%s|%s] %s [%s]" % (
                    brown(branch),
                    blue(_("upload")),
                    darkgreen(package),
                    size,
                ),
                importance = 0,
                type = "info",
                header = red("    # ")
            )
        for package, size in download:
            package = darkred(os.path.basename(package))
            size = blue(self.entropyTools.bytes_into_human(size))
            self.Entropy.updateProgress(
                "[branch:%s|%s] %s [%s]" % (
                    brown(branch),
                    darkred(_("download")),
                    blue(package),
                    size,
                ),
                importance = 0,
                type = "info",
                header = red("    # ")
            )
        for package, size in copy:
            package = darkblue(os.path.basename(package))
            size = blue(self.entropyTools.bytes_into_human(size))
            self.Entropy.updateProgress(
                "[branch:%s|%s] %s [%s]" % (
                    brown(branch),
                    darkgreen(_("copy")),
                    brown(package),
                    size,
                ),
                importance = 0,
                type = "info",
                header = red("    # ")
            )
        for package, size in removal:
            package = brown(os.path.basename(package))
            size = blue(self.entropyTools.bytes_into_human(size))
            self.Entropy.updateProgress(
                "[branch:%s|%s] %s [%s]" % (
                    brown(branch),
                    red(_("remove")),
                    red(package),
                    size,
                ),
                importance = 0,
                type = "info",
                header = red("    # ")
            )

        self.Entropy.updateProgress(
            "%s:\t\t\t%s" % (
                blue(_("Packages to be removed")),
                darkred(str(len(removal))),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )
        self.Entropy.updateProgress(
            "%s:\t\t%s" % (
                darkgreen(_("Packages to be moved locally")),
                darkgreen(str(len(copy))),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )
        self.Entropy.updateProgress(
            "%s:\t\t\t%s" % (
                bold(_("Packages to be uploaded")),
                bold(str(len(upload))),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )

        self.Entropy.updateProgress(
            "%s:\t\t\t%s" % (
                darkred(_("Total removal size")),
                darkred(
                    self.entropyTools.bytes_into_human(metainfo['removal'])
                ),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )

        self.Entropy.updateProgress(
            "%s:\t\t\t%s" % (
                blue(_("Total upload size")),
                blue(self.entropyTools.bytes_into_human(metainfo['upload'])),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )
        self.Entropy.updateProgress(
            "%s:\t\t\t%s" % (
                brown(_("Total download size")),
                brown(self.entropyTools.bytes_into_human(metainfo['download'])),
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )

    def _calculate_remote_package_files(self, uri, branch, txc_handler,
        repo = None):

        remote_dir = os.path.join(
            self.Entropy.get_remote_packages_relative_path(repo), branch)

        # create path to lock file if it doesn't exist
        if not txc_handler.is_dir(remote_dir):
            txc_handler.makedirs(remote_dir)

        remote_packages_info = txc_handler.list_content_metadata(remote_dir)
        remote_packages = [x[0] for x in remote_packages_info]

        remote_files = 0
        for pkg in remote_packages:
            if pkg.endswith(etpConst['packagesext']):
                remote_files += 1

        remote_packages_data = {}
        for pkg in remote_packages_info:
            remote_packages_data[pkg[0]] = int(pkg[1])

        return remote_files, remote_packages, remote_packages_data

    def calculate_packages_to_sync(self, uri, branch, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        upload_files, upload_packages = self.calculate_local_upload_files(
            branch, repo)
        local_files, local_packages = self.calculate_local_package_files(branch,
            repo)
        self._show_local_sync_stats(upload_files, local_files)

        self.Entropy.updateProgress(
            "%s: %s" % (blue(_("Remote statistics for")), red(crippled_uri),),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        txc = self.Entropy.Transceiver(uri)
        with txc as handler:
            remote_files, remote_packages, remote_packages_data = \
                self._calculate_remote_package_files(uri, branch, handler,
                    repo = repo)

        self.Entropy.updateProgress(
            "%s:\t\t\t%s %s" % (
                blue(_("remote packages")),
                bold(str(remote_files)),
                red(_("files stored")),
            ),
            importance = 0,
            type = "info",
            header = red(" @@ ")
        )

        mytxt = blue("%s ...") % (
            _("Calculating queues"),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        upload_queue, download_queue, removal_queue, fine_queue = \
            self.calculate_sync_queues(upload_packages, local_packages,
                remote_packages, remote_packages_data, branch, repo)
        return upload_queue, download_queue, removal_queue, fine_queue, \
            remote_packages_data

    def calculate_sync_queues(
            self,
            upload_packages,
            local_packages,
            remote_packages,
            remote_packages_data,
            branch,
            repo = None
        ):

        upload_queue = set()
        download_queue = set()
        removal_queue = set()
        fine_queue = set()

        for local_package in upload_packages:
            if local_package in remote_packages:

                local_filepath = os.path.join(
                    self.Entropy.get_local_upload_directory(repo), branch,
                    local_package)

                local_size = self.entropyTools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(local_package)
                if remote_size is None:
                    remote_size = 0
                if (local_size != remote_size):
                    # size does not match, adding to the upload queue
                    upload_queue.add(local_package)
                else:
                    # just move from upload to packages
                    fine_queue.add(local_package)
            else:
                # always force upload of packages in uploaddir
                upload_queue.add(local_package)

        # if a package is in the packages directory but not online,
        # we have to upload it we have local_packages and remote_packages
        for local_package in local_packages:
            if local_package in remote_packages:
                local_filepath = os.path.join(
                    self.Entropy.get_local_packages_directory(repo), branch,
                    local_package)
                local_size = self.entropyTools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(local_package)
                if remote_size is None:
                    remote_size = 0
                if (local_size != remote_size) and (local_size != 0):
                    # size does not match, adding to the upload queue
                    if local_package not in fine_queue:
                        upload_queue.add(local_package)
            else:
                # this means that the local package does not exist
                # so, we need to download it
                upload_queue.add(local_package)

        # Fill download_queue and removal_queue
        for remote_package in remote_packages:
            if remote_package in local_packages:
                local_filepath = os.path.join(
                    self.Entropy.get_local_packages_directory(repo), branch,
                    remote_package)
                local_size = self.entropyTools.get_file_size(local_filepath)
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
            else:
                # this means that the local package does not exist
                # so, we need to download it
                 # ignore .tmp files
                if not remote_package.endswith(".tmp"):
                    download_queue.add(remote_package)

        # Collect packages that don't exist anymore in the database
        # so we can filter them out from the download queue
        dbconn = self.Entropy.open_server_repository(just_reading = True,
            repo = repo)
        db_files = dbconn.listAllDownloads(do_sort = False,
            full_path = True)
        db_files = set([os.path.basename(x) for x in db_files if \
            (self.Entropy.get_branch_from_download_relative_uri(x) == branch)])

        exclude = set()
        for myfile in download_queue:
            if myfile.endswith(etpConst['packagesext']):
                if myfile not in db_files:
                    exclude.add(myfile)
        download_queue -= exclude

        exclude = set()
        for myfile in upload_queue:
            if myfile.endswith(etpConst['packagesext']):
                if myfile not in db_files:
                    exclude.add(myfile)
        upload_queue -= exclude

        exclude = set()
        for myfile in download_queue:
            if myfile in upload_queue:
                exclude.add(myfile)
        download_queue -= exclude

        return upload_queue, download_queue, removal_queue, fine_queue


    def expand_queues(self, upload_queue, download_queue, removal_queue,
        remote_packages_data, branch, repo):

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
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(
                self.Entropy.get_local_packages_directory(repo), branch, item)
            size = self.entropyTools.get_file_size(local_filepath)
            metainfo['removal'] += size
            removal.append((local_filepath, size))

        for item in download_queue:
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(
                self.Entropy.get_local_upload_directory(repo), branch, item)
            if not os.path.isfile(local_filepath):
                size = remote_packages_data.get(item)
                if size is None:
                    size = 0
                size = int(size)
                metainfo['removal'] += size
                download.append((local_filepath, size))
            else:
                size = self.entropyTools.get_file_size(local_filepath)
                do_copy.append((local_filepath, size))

        for item in upload_queue:
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(
                self.Entropy.get_local_upload_directory(repo), branch, item)
            local_filepath_pkgs = os.path.join(
                self.Entropy.get_local_packages_directory(repo), branch, item)
            if os.path.isfile(local_filepath):
                size = self.entropyTools.get_file_size(local_filepath)
                upload.append((local_filepath, size))
            else:
                size = self.entropyTools.get_file_size(local_filepath_pkgs)
                upload.append((local_filepath_pkgs, size))
            metainfo['upload'] += size

        return upload, download, removal, do_copy, metainfo


    def _sync_run_removal_queue(self, removal_queue, branch, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        for itemdata in removal_queue:

            remove_filename = itemdata[0]
            remove_filepath = os.path.join(
                self.Entropy.get_local_packages_directory(repo), branch,
                remove_filename)
            remove_filepath_hash = remove_filepath + \
                etpConst['packagesmd5fileext']
            self.Entropy.updateProgress(
                "[repo:%s|%s|%s] %s: %s [%s]" % (
                    brown(repo),
                    red("sync"),
                    brown(branch),
                    blue(_("removing package+hash")),
                    darkgreen(remove_filename),
                    blue(self.entropyTools.bytes_into_human(itemdata[1])),
                ),
                importance = 0,
                type = "info",
                header = darkred(" * ")
            )

            if os.path.isfile(remove_filepath):
                os.remove(remove_filepath)
            if os.path.isfile(remove_filepath_hash):
                os.remove(remove_filepath_hash)

        self.Entropy.updateProgress(
            "[repo:%s|%s|%s] %s" % (
                brown(repo),
                red(_("sync")),
                brown(branch),
                blue(_("removal complete")),
            ),
            importance = 0,
            type = "info",
            header = darkred(" * ")
        )


    def _sync_run_copy_queue(self, copy_queue, branch, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        for itemdata in copy_queue:

            from_file = itemdata[0]
            from_file_hash = from_file + etpConst['packagesmd5fileext']
            to_file = os.path.join(
                self.Entropy.get_local_packages_directory(repo), branch,
                os.path.basename(from_file))
            to_file_hash = to_file+etpConst['packagesmd5fileext']
            expiration_file = to_file+etpConst['packagesexpirationfileext']
            self.Entropy.updateProgress(
                "[repo:%s|%s|%s] %s: %s" % (
                    brown(repo),
                    red("sync"),
                    brown(branch),
                    blue(_("copying file+hash to repository")),
                    darkgreen(from_file),
                ),
                importance = 0,
                type = "info",
                header = darkred(" * ")
            )

            if not os.path.isdir(os.path.dirname(to_file)):
                os.makedirs(os.path.dirname(to_file))

            shutil.copy2(from_file, to_file)
            if not os.path.isfile(from_file_hash):
                self.create_file_checksum(from_file, from_file_hash)
            shutil.copy2(from_file_hash, to_file_hash)

            # clear expiration file
            if os.path.isfile(expiration_file):
                os.remove(expiration_file)


    def _sync_run_upload_queue(self, uri, upload_queue, branch, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        myqueue = []
        for itemdata in upload_queue:
            upload_item = itemdata[0]
            hash_file = upload_item + etpConst['packagesmd5fileext']
            if not os.path.isfile(hash_file):
                self.entropyTools.create_md5_file(upload_item)
            myqueue.append(hash_file)
            myqueue.append(upload_item)

        remote_dir = os.path.join(
            self.Entropy.get_remote_packages_relative_path(repo), branch)

        uploader = self.TransceiverServerHandler(self.Entropy, [uri],
            myqueue, critical_files = myqueue,
            txc_basedir = remote_dir,
            handlers_data = {'branch': branch }, repo = repo)

        errors, m_fine_uris, m_broken_uris = uploader.go()
        if errors:
            my_broken_uris = [
                (EntropyTransceiver.get_uri_name(x[0]), x[1]) for \
                    x in m_broken_uris]
            reason = my_broken_uris[0][1]
            self.Entropy.updateProgress(
                "[branch:%s] %s: %s, %s: %s" % (
                    brown(branch),
                    blue(_("upload errors")),
                    red(crippled_uri),
                    blue(_("reason")),
                    darkgreen(repr(reason)),
                ),
                importance = 1,
                type = "error",
                header = darkred(" !!! ")
            )
            return errors, m_fine_uris, m_broken_uris

        self.Entropy.updateProgress(
            "[branch:%s] %s: %s" % (
                brown(branch),
                blue(_("upload completed successfully")),
                red(crippled_uri),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )
        return errors, m_fine_uris, m_broken_uris


    def _sync_run_download_queue(self, uri, download_queue, branch,
            repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        myqueue = []
        for package in download_queue:
            hash_file = package + etpConst['packagesmd5fileext']
            myqueue.append(package)
            myqueue.append(hash_file)

        remote_dir = os.path.join(
            self.Entropy.get_remote_packages_relative_path(repo), branch)
        local_basedir = os.path.join(
            self.Entropy.get_local_packages_directory(repo), branch)
        downloader = self.TransceiverServerHandler(
            self.Entropy, [uri], myqueue,
            critical_files = myqueue,
            txc_basedir = remote_dir, local_basedir = local_basedir,
            handlers_data = {'branch': branch }, download = True, repo = repo)

        errors, m_fine_uris, m_broken_uris = downloader.go()
        if errors:
            my_broken_uris = [
                (EntropyTransceiver.get_uri_name(x), y,) \
                    for x, y in m_broken_uris]
            reason = my_broken_uris[0][1]
            self.Entropy.updateProgress(
                "[repo:%s|%s|%s] %s: %s, %s: %s" % (
                    brown(repo),
                    red(_("sync")),
                    brown(branch),
                    blue(_("download errors")),
                    darkgreen(crippled_uri),
                    blue(_("reason")),
                    reason,
                ),
                importance = 1,
                type = "error",
                header = darkred(" !!! ")
            )
            return errors, m_fine_uris, m_broken_uris

        self.Entropy.updateProgress(
            "[repo:%s|%s|%s] %s: %s" % (
                brown(repo),
                red(_("sync")),
                brown(branch),
                blue(_("download completed successfully")),
                darkgreen(crippled_uri),
            ),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )
        return errors, m_fine_uris, m_broken_uris

    def run_package_files_qa_checks(self, packages_list, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        my_qa = self.Entropy.QA()

        qa_total = len(packages_list)
        qa_count = 0
        qa_some_faulty = []

        for upload_package in packages_list:
            qa_count += 1

            self.Entropy.updateProgress(
                "%s: %s" % (
                    purple(_("QA checking package file")),
                    darkgreen(os.path.basename(upload_package)),
                ),
                importance = 0,
                type = "info",
                header = purple(" @@ "),
                back = True,
                count = (qa_count, qa_total,)
            )

            result = my_qa.entropy_package_checks(upload_package)
            if not result:
                # call wolfman-911
                qa_some_faulty.append(os.path.basename(upload_package))

        if qa_some_faulty:

            for qa_faulty_pkg in qa_some_faulty:
                self.Entropy.updateProgress(
                    "[repo:%s|branch:%s] %s: %s" % (
                        brown(repo),
                        self.SystemSettings['repositories']['branch'],
                        red(_("faulty package file, please fix")),
                        blue(os.path.basename(qa_faulty_pkg)),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" @@ ")
                )
            raise EntropyPackageException(
                'EntropyPackageException: cannot continue')


    def sync_packages(self, ask = True, pretend = False, packages_check = False,
        repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        self.Entropy.updateProgress(
            "[repo:%s|%s] %s" % (
                repo,
                red(_("sync")),
                darkgreen(_("starting packages sync")),
            ),
            importance = 1,
            type = "info",
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

        for uri in self.Entropy.get_remote_mirrors(repo):

            crippled_uri = EntropyTransceiver.get_uri_name(uri)
            mirror_errors = False

            self.Entropy.updateProgress(
                "[repo:%s|%s|branch:%s] %s: %s" % (
                    repo,
                    red(_("sync")),
                    brown(self.SystemSettings['repositories']['branch']),
                    blue(_("packages sync")),
                    bold(crippled_uri),
                ),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )

            try:
                upload_queue, download_queue, removal_queue, fine_queue, \
                    remote_packages_data = self.calculate_packages_to_sync(uri,
                        self.SystemSettings['repositories']['branch'], repo)
            except self.socket.error as err:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s: %s, %s %s" % (
                        repo,
                        red(_("sync")),
                        self.SystemSettings['repositories']['branch'],
                        darkred(_("socket error")),
                        err,
                        darkred(_("on")),
                        crippled_uri,
                    ),
                    importance = 1,
                    type = "error",
                    header = darkgreen(" * ")
                )
                continue

            if (not upload_queue) and (not download_queue) and \
                (not removal_queue):
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s: %s" % (
                        repo,
                        red(_("sync")),
                        self.SystemSettings['repositories']['branch'],
                        darkgreen(_("nothing to do on")),
                        crippled_uri,
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                successfull_mirrors.add(uri)
                continue

            self.Entropy.updateProgress(
                "%s:" % (blue(_("Expanding queues")),),
                importance = 1,
                type = "info",
                header = red(" ** ")
            )

            upload, download, removal, copy, metainfo = self.expand_queues(
                        upload_queue,
                        download_queue,
                        removal_queue,
                        remote_packages_data,
                        self.SystemSettings['repositories']['branch'],
                        repo
            )
            del upload_queue, download_queue, removal_queue, \
                remote_packages_data
            self._show_sync_queues(upload, download, removal, copy, metainfo,
                self.SystemSettings['repositories']['branch'])

            if not len(upload)+len(download)+len(removal)+len(copy):

                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s %s" % (
                        self.Entropy.default_repository,
                        red(_("sync")),
                        self.SystemSettings['repositories']['branch'],
                        blue(_("nothing to sync for")),
                        crippled_uri,
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" @@ ")
                )

                successfull_mirrors.add(uri)
                continue

            if pretend:
                successfull_mirrors.add(uri)
                continue

            if ask:
                rc_sync = self.Entropy.askQuestion(
                    _("Would you like to run the steps above ?"))
                if rc_sync == _("No"):
                    continue

            try:

                # QA checks
                qa_package_files = [x[0] for x in upload if x[0] \
                    not in upload_queue_qa_checked]
                upload_queue_qa_checked |= set(qa_package_files)

                self.run_package_files_qa_checks(qa_package_files, repo = repo)

                if removal:
                    self._sync_run_removal_queue(removal,
                        self.SystemSettings['repositories']['branch'], repo)

                if copy:
                    self._sync_run_copy_queue(copy,
                        self.SystemSettings['repositories']['branch'], repo)

                if upload or download:
                    mirrors_tainted = True

                if upload:
                    d_errors, m_fine_uris, \
                        m_broken_uris = self._sync_run_upload_queue(
                            uri, upload,
                            self.SystemSettings['repositories']['branch'], repo)

                    if d_errors:
                        mirror_errors = True

                if download:
                    my_downlist = [x[0] for x in download]
                    d_errors, m_fine_uris, \
                        m_broken_uris = self._sync_run_download_queue(
                            uri, my_downlist,
                            self.SystemSettings['repositories']['branch'], repo)

                    if d_errors:
                        mirror_errors = True
                if not mirror_errors:
                    successfull_mirrors.add(uri)
                else:
                    mirrors_errors = True

            except KeyboardInterrupt:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s" % (
                        repo,
                        red(_("sync")),
                        self.SystemSettings['repositories']['branch'],
                        darkgreen(_("keyboard interrupt !")),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                continue

            except EntropyPackageException as err:

                mirrors_errors = True
                broken_mirrors.add(uri)
                successfull_mirrors.clear()
                # so that people will realize this is a very bad thing
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s: %s, %s: %s" % (
                        repo,
                        red(_("sync")),
                        self.SystemSettings['repositories']['branch'],
                        darkred(_("you must package them again")),
                        EntropyPackageException,
                        _("error"),
                        err,
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                return mirrors_tainted, mirrors_errors, successfull_mirrors, \
                    broken_mirrors, check_data

            except Exception as err:

                self.entropyTools.print_traceback()
                mirrors_errors = True
                broken_mirrors.add(uri)
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s: %s, %s: %s" % (
                        repo,
                        red(_("sync")),
                        self.SystemSettings['repositories']['branch'],
                        darkred(_("exception caught")),
                        Exception,
                        _("error"),
                        err,
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )

                exc_txt = self.Entropy.entropyTools.print_exception(
                    returndata = True)
                for line in exc_txt:
                    self.Entropy.updateProgress(
                        repr(line),
                        importance = 1,
                        type = "error",
                        header = darkred(":  ")
                    )

                if len(successfull_mirrors) > 0:
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|branch:%s] %s" % (
                            repo,
                            red(_("sync")),
                            self.SystemSettings['repositories']['branch'],
                            darkred(
                                _("at least one mirror synced properly!")),
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                continue

        # if at least one server has been synced successfully, move files
        if (len(successfull_mirrors) > 0) and not pretend:
            self.remove_expiration_files(
                self.SystemSettings['repositories']['branch'], repo)

        if packages_check:
            check_data = self.Entropy.verify_local_packages([], ask = ask,
                repo = repo)

        return mirrors_tainted, mirrors_errors, successfull_mirrors, \
            broken_mirrors, check_data

    def remove_expiration_files(self, branch, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        branch_dir = os.path.join(
            self.Entropy.get_local_upload_directory(repo), branch)

        # check if it exists
        if not os.path.isdir(branch_dir):
            return None

        branchcontent = os.listdir(branch_dir)
        for xfile in branchcontent:
            source = os.path.join(self.Entropy.get_local_upload_directory(repo),
                branch, xfile)
            destdir = os.path.join(
                self.Entropy.get_local_packages_directory(repo), branch)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)
            dest = os.path.join(destdir, xfile)
            shutil.move(source, dest)
            # clear expiration file
            dest_expiration = dest + etpConst['packagesexpirationfileext']
            if os.path.isfile(dest_expiration):
                os.remove(dest_expiration)


    def is_package_expired(self, package_file, branch, repo = None):

        pkg_path = os.path.join(
            self.Entropy.get_local_packages_directory(repo), branch,
            package_file)
        pkg_path += etpConst['packagesexpirationfileext']
        if not os.path.isfile(pkg_path):
            return False

        srv_set = self.SystemSettings[self.sys_settings_plugin_id]['server']
        mtime = self.entropyTools.get_file_unix_mtime(pkg_path)
        days = srv_set['packages_expiration_days']
        delta = int(days)*24*3600
        currmtime = time.time()
        file_delta = currmtime - mtime

        if file_delta > delta:
            return True
        return False

    def create_expiration_file(self, package_file, branch, repo = None,
        gentle = False):

        pkg_path = os.path.join(
            self.Entropy.get_local_packages_directory(repo), branch,
            package_file)
        pkg_path += etpConst['packagesexpirationfileext']
        if gentle and os.path.isfile(pkg_path):
            return
        f_exp = open(pkg_path, "w")
        f_exp.flush()
        f_exp.close()


    def collect_expiring_packages(self, branch, repo = None):

        dbconn = self.Entropy.open_server_repository(just_reading = True,
            repo = repo)
        database_bins = dbconn.listAllDownloads(do_sort = False,
            full_path = True)
        bins_dir = os.path.join(
            self.Entropy.get_local_packages_directory(repo), branch)
        repo_bins = set()

        if os.path.isdir(bins_dir):
            repo_bins = os.listdir(bins_dir)
            repo_bins = set([
                os.path.join('packages', etpSys['arch'], branch, x) for x \
                    in repo_bins if x.endswith(etpConst['packagesext'])])
        repo_bins -= database_bins

        return set([os.path.basename(x) for x in repo_bins])


    def tidy_mirrors(self, ask = True, pretend = False, repo = None):

        if repo is None:
            repo = self.Entropy.default_repository

        self.Entropy.updateProgress(
            "[repo:%s|%s|branch:%s] %s" % (
                brown(repo),
                red(_("tidy")),
                blue(self.SystemSettings['repositories']['branch']),
                blue(_("collecting expired packages")),
            ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        branch_data = {}
        errors = False
        branch_data['errors'] = False
        branch = self.SystemSettings['repositories']['branch']

        self.Entropy.updateProgress(
            "[branch:%s] %s" % (
                brown(branch),
                blue(_("collecting expired packages in the selected branches")),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )

        # collect removed packages
        expiring_packages = self.collect_expiring_packages(branch, repo)
        if expiring_packages:

            # filter expired packages used by other branches
            # this is done for the sake of consistency
            # --- read packages.db.pkglist, make sure your repository
            # has been ported to latest Entropy

            branch_pkglist_data = self.read_remote_file_in_branches(
                etpConst['etpdatabasepkglist'], repo = repo,
                excluded_branches = [branch])
            # format data
            for key, val in list(branch_pkglist_data.items()):
                branch_pkglist_data[key] = val.split("\n")


            remote_relpath = os.path.join(etpConst['packagesrelativepath'],
                branch)
            my_expiring_pkgs = set([os.path.join(remote_relpath, x) for x in \
                expiring_packages])

            for other_branch in branch_pkglist_data:
                branch_pkglist = set(branch_pkglist_data[other_branch])
                my_expiring_pkgs -= branch_pkglist

            # fallback to normality, set new expiring packages var
            expiring_packages = [os.path.basename(x) for x in my_expiring_pkgs]

        removal = []
        for package in expiring_packages:
            expired = self.is_package_expired(package, branch, repo)
            if expired:
                removal.append(package)
            else:
                self.create_expiration_file(package, branch, repo,
                    gentle = True)

        # fill returning data
        branch_data['removal'] = removal[:]

        if not removal:
            self.Entropy.updateProgress(
                "[branch:%s] %s" % (
                    brown(branch),
                    blue(_("nothing to remove on this branch")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            return errors, branch_data
        else:
            self.Entropy.updateProgress(
                "[branch:%s] %s:" % (
                    brown(branch),
                    blue(_("these are the expired packages")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            for package in removal:
                self.Entropy.updateProgress(
                    "[branch:%s] %s: %s" % (
                            brown(branch),
                            blue(_("remove")),
                            darkgreen(package),
                        ),
                    importance = 1,
                    type = "info",
                    header = brown("    # ")
                )

        if pretend:
            return errors, branch_data

        if ask:
            rc_question = self.Entropy.askQuestion(
                _("Would you like to continue ?"))
            if rc_question == _("No"):
                return errors, branch_data

        myqueue = []
        for package in removal:
            myqueue.append(package+etpConst['packagesmd5fileext'])
            myqueue.append(package)

        remote_dir = os.path.join(
            self.Entropy.get_remote_packages_relative_path(repo), branch)
        for uri in self.Entropy.get_remote_mirrors(repo):

            self.Entropy.updateProgress(
                "[branch:%s] %s..." % (
                    brown(branch),
                    blue(_("removing packages remotely")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )

            crippled_uri = EntropyTransceiver.get_uri_name(uri)
            destroyer = self.TransceiverServerHandler(
                self.Entropy,
                [uri],
                myqueue,
                critical_files = [],
                txc_basedir = remote_dir,
                remove = True,
                repo = repo
            )
            errors, m_fine_uris, m_broken_uris = destroyer.go()
            if errors:
                my_broken_uris = [
                    (EntropyTransceiver.get_uri_name(x[0]), x[1]) \
                        for x in m_broken_uris]

                reason = my_broken_uris[0][1]
                self.Entropy.updateProgress(
                    "[branch:%s] %s: %s, %s: %s" % (
                        brown(branch),
                        blue(_("remove errors")),
                        red(crippled_uri),
                        blue(_("reason")),
                        reason,
                    ),
                    importance = 1,
                    type = "warning",
                    header = brown(" !!! ")
                )
                branch_data['errors'] = True
                errors = True

            self.Entropy.updateProgress(
                "[branch:%s] %s..." % (
                    brown(branch),
                    blue(_("removing packages locally")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )

            branch_data['removed'] = set()
            for package in removal:
                package_path = os.path.join(
                    self.Entropy.get_local_packages_directory(repo),
                    branch, package)
                package_path_hash = package_path + \
                    etpConst['packagesmd5fileext']
                package_path_expired = package_path + \
                    etpConst['packagesexpirationfileext']

                my_rm_list = (package_path_hash, package_path,
                    package_path_expired)
                for myfile in my_rm_list:
                    if os.path.isfile(myfile):
                        self.Entropy.updateProgress(
                            "[branch:%s] %s: %s" % (
                                brown(branch),
                                blue(_("removing")),
                                darkgreen(myfile),
                            ),
                            importance = 1,
                            type = "info",
                            header = brown(" @@ ")
                        )
                        os.remove(myfile)
                        branch_data['removed'].add(myfile)

        return errors, branch_data
