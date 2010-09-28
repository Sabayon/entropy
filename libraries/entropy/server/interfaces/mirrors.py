# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server Mirrors Interfaces}.

"""
import os
import tempfile
import shutil
import time

from entropy.exceptions import OnlineMirrorError, EntropyPackageException
from entropy.output import red, darkgreen, bold, brown, blue, darkred, \
    darkblue, purple, teal
from entropy.const import etpConst, const_setup_file
from entropy.cache import EntropyCacher
from entropy.i18n import _
from entropy.misc import RSS
from entropy.server.interfaces.rss import ServerRssMetadata
from entropy.transceivers import EntropyTransceiver
from entropy.security import Repository as RepositorySecurity
from entropy.transceivers.uri_handlers.skel import EntropyUriHandler
from entropy.db.exceptions import Error
from entropy.core.settings.base import SystemSettings

import entropy.tools
import entropy.dump

class ServerNoticeBoardMixin:

    def download_notice_board(self, repo = None):

        if repo is None:
            repo = self._entropy.default_repository
        mirrors = self._entropy.get_remote_repository_mirrors(repo)
        rss_path = self._entropy._get_local_database_notice_board_file(repo)
        mytmpdir = tempfile.mkdtemp(prefix = "entropy.server")

        self._entropy.output(
            "[repo:%s] %s %s" % (
                brown(repo),
                blue(_("downloading notice board from mirrors to")),
                red(rss_path),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )

        downloaded = False
        for uri in mirrors:
            crippled_uri = EntropyTransceiver.get_uri_name(uri)
            downloader = self.TransceiverServerHandler(
                self._entropy, [uri],
                [rss_path], download = True,
                local_basedir = mytmpdir, critical_files = [rss_path],
                repo = repo
            )
            errors, m_fine_uris, m_broken_uris = downloader.go()
            if not errors:
                self._entropy.output(
                    "[repo:%s] %s: %s" % (
                        brown(repo),
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

    def remove_notice_board(self, repo = None):

        if repo is None:
            repo = self._entropy.default_repository
        mirrors = self._entropy.get_remote_repository_mirrors(repo)
        rss_path = self._entropy._get_local_database_notice_board_file(repo)
        rss_file = os.path.basename(rss_path)

        self._entropy.output(
            "[repo:%s] %s %s" % (
                    brown(repo),
                    blue(_("removing notice board from")),
                    red(rss_file),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )

        destroyer = self.TransceiverServerHandler(
            self._entropy,
            mirrors,
            [rss_file],
            critical_files = [rss_file],
            remove = True,
            repo = repo
        )
        errors, m_fine_uris, m_broken_uris = destroyer.go()
        if errors:
            m_broken_uris = sorted(m_broken_uris)
            m_broken_uris = [EntropyTransceiver.get_uri_name(x) \
                for x in m_broken_uris]
            self._entropy.output(
                "[repo:%s] %s %s" % (
                        brown(repo),
                        blue(_("notice board removal failed on")),
                        red(', '.join(m_broken_uris)),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            return False
        self._entropy.output(
            "[repo:%s] %s" % (
                    brown(repo),
                    blue(_("notice board removal success")),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )
        return True


    def upload_notice_board(self, repo = None):

        if repo is None:
            repo = self._entropy.default_repository
        mirrors = self._entropy.get_remote_repository_mirrors(repo)
        rss_path = self._entropy._get_local_database_notice_board_file(repo)

        self._entropy.output(
            "[repo:%s] %s %s" % (
                    brown(repo),
                    blue(_("uploading notice board from")),
                    red(rss_path),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )

        uploader = self.TransceiverServerHandler(
            self._entropy,
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
            self._entropy.output(
                "[repo:%s] %s %s" % (
                        brown(repo),
                        blue(_("notice board upload failed on")),
                        red(', '.join(m_broken_uris)),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            return False
        self._entropy.output(
            "[repo:%s] %s" % (
                    brown(repo),
                    blue(_("notice board upload success")),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )
        return True


    def update_notice_board(self, title, notice_text, link = None, repo = None):

        rss_title = "%s Notice Board" % (self._settings['system']['name'],)
        rss_description = "Inform about important distribution activities."
        rss_path = self._entropy._get_local_database_notice_board_file(repo)
        srv_set = self._settings[Server.SYSTEM_SETTINGS_PLG_ID]['server']
        if not link:
            link = srv_set['rss']['website_url']

        self.download_notice_board(repo)
        rss_main = RSS(rss_path, rss_title, rss_description,
            maxentries = 20)
        rss_main.add_item(title, link, description = notice_text)
        rss_main.write_changes()
        dict_list, items = rss_main.get_entries()
        if items == 0:
            status = self.remove_notice_board(repo = repo)
        else:
            status = self.upload_notice_board(repo = repo)
        return status

    def read_notice_board(self, do_download = True, repo = None):

        rss_path = self._entropy._get_local_database_notice_board_file(repo)
        if do_download:
            self.download_notice_board(repo)
        if not (os.path.isfile(rss_path) and os.access(rss_path, os.R_OK)):
            return None
        rss_main = RSS(rss_path, '', '')
        return rss_main.get_entries()

    def remove_from_notice_board(self, identifier, repo = None):

        rss_path = self._entropy._get_local_database_notice_board_file(repo)
        rss_title = "%s Notice Board" % (self._settings['system']['name'],)
        rss_description = "Inform about important distribution activities."
        if not (os.path.isfile(rss_path) and os.access(rss_path, os.R_OK)):
            return 0
        rss_main = RSS(rss_path, rss_title, rss_description)
        data = rss_main.remove_entry(identifier)
        rss_main.write_changes()
        return data

class Server(ServerNoticeBoardMixin):

    SYSTEM_SETTINGS_PLG_ID = etpConst['system_settings_plugins_ids']['server_plugin']

    import socket
    def __init__(self, server, repo = None):

        from entropy.server.transceivers import TransceiverServerHandler
        from entropy.server.interfaces.main import Server as MainServer

        if not isinstance(server, MainServer):
            raise AttributeError("entropy.server.interfaces.main.Server needed")

        self._entropy = server
        self.TransceiverServerHandler = TransceiverServerHandler
        self.Cacher = EntropyCacher()
        self._settings = SystemSettings()

        mytxt = blue("%s:") % (_("Entropy Server Mirrors Interface loaded"),)
        self._entropy.output(
            mytxt,
            importance = 2,
            level = "info",
            header = red(" @@ ")
        )
        for mirror in self._entropy.get_remote_repository_mirrors(repo = repo):
            mytxt = _("repository mirror")
            mirror = EntropyTransceiver.hide_sensible_data(mirror)
            self._entropy.output(
                "%s: %s" % (purple(mytxt), darkgreen(mirror),),
                importance = 0,
                level = "info",
                header = brown("   # ")
            )
        for mirror in self._entropy.get_remote_packages_mirrors(repo = repo):
            mytxt = _("packages mirror")
            mirror = EntropyTransceiver.hide_sensible_data(mirror)
            self._entropy.output(
                blue("%s: %s") % (teal(mytxt), darkgreen(mirror),),
                importance = 0,
                level = "info",
                header = brown("   # ")
            )

    def _read_remote_file_in_branches(self, filename, repo = None,
            excluded_branches = None):
        """
        Reads a file remotely located in all the available branches, in
        repository directory.

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
            repo = self._entropy.default_repository
        if excluded_branches is None:
            excluded_branches = []

        branch_data = {}
        mirrors = self._entropy.get_remote_repository_mirrors(repo)
        for uri in mirrors:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            self._entropy.output(
                "[repo:%s] %s: %s => %s" % (
                    brown(repo),
                    blue(_("looking for file in mirror")),
                    darkgreen(crippled_uri),
                    filename,
                ),
                importance = 1,
                level = "info",
                header = brown(" @@ ")
            )

            branches_path = self._entropy._get_remote_database_relative_path(
                repo)
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

                    tmp_dir = tempfile.mkdtemp(prefix = "entropy.server")
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
            repo = self._entropy.default_repository

        if not mirrors:
            mirrors = self._entropy.get_remote_repository_mirrors(repo)

        issues = False
        for uri in mirrors:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            lock_text = _("unlocking")
            if lock:
                lock_text = _("locking")
            self._entropy.output(
                "[repo:%s|%s] %s %s" % (
                    brown(repo),
                    darkgreen(crippled_uri),
                    bold(lock_text),
                    blue("%s...") % (_("mirror"),),
                ),
                importance = 1,
                level = "info",
                header = brown(" * "),
                back = True
            )

            base_path = os.path.join(
                self._entropy._get_remote_database_relative_path(repo),
                self._settings['repositories']['branch'])
            lock_file = os.path.join(base_path,
                etpConst['etpdatabaselockfile'])

            txc = self._entropy.Transceiver(uri)
            txc.set_verbosity(False)

            with txc as handler:

                if lock and handler.is_file(lock_file):
                    self._entropy.output(
                        "[repo:%s|%s] %s" % (
                                brown(repo),
                                darkgreen(crippled_uri),
                                blue(_("mirror already locked")),
                        ),
                        importance = 1,
                        level = "info",
                        header = darkgreen(" * ")
                    )
                    continue

                elif not lock and not handler.is_file(lock_file):
                    self._entropy.output(
                        "[repo:%s|%s] %s" % (
                                brown(repo),
                                darkgreen(crippled_uri),
                                blue(_("mirror already unlocked")),
                        ),
                        importance = 1,
                        level = "info",
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
            db_taint_file = self._entropy._get_local_database_taint_file(repo)
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
            repo = self._entropy.default_repository

        if not mirrors:
            mirrors = self._entropy.get_remote_repository_mirrors(repo)

        issues = False
        for uri in mirrors:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            lock_text = _("unlocking")
            if lock:
                lock_text = _("locking")
            self._entropy.output(
                "[repo:%s|%s] %s %s..." % (
                            blue(repo),
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
            my_path = os.path.join(
                self._entropy._get_remote_database_relative_path(repo),
                self._settings['repositories']['branch'])
            lock_file = os.path.join(my_path, lock_file)

            txc = self._entropy.Transceiver(uri)
            txc.set_verbosity(False)

            with txc as handler:

                if lock and handler.is_file(lock_file):
                    self._entropy.output(
                        "[repo:%s|%s] %s" % (
                            blue(repo),
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
                        "[repo:%s|%s] %s" % (
                            blue(repo),
                            red(crippled_uri),
                            blue(_("mirror already unlocked for download")),
                        ),
                        importance = 1,
                        level = "info",
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
            repo = self._entropy.default_repository

        my_path = os.path.join(
            self._entropy._get_remote_database_relative_path(repo),
            self._settings['repositories']['branch'])

        # create path to lock file if it doesn't exist
        if not txc_handler.is_dir(my_path):
            txc_handler.makedirs(my_path)

        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        lock_string = ''

        if dblock:
            self._entropy._create_local_database_lockfile(repo)
            lock_file = self._entropy._get_database_lockfile(repo)
        else:
            # locking/unlocking mirror1 for download
            lock_string = _('for download')
            self._entropy._create_local_database_download_lockfile(repo)
            lock_file = self._entropy._get_database_download_lockfile(repo)

        remote_path = os.path.join(my_path, os.path.basename(lock_file))

        rc_upload = txc_handler.upload(lock_file, remote_path)
        if rc_upload:
            self._entropy.output(
                "[repo:%s|%s] %s %s" % (
                    blue(repo),
                    red(crippled_uri),
                    blue(_("mirror successfully locked")),
                    blue(lock_string),
                ),
                importance = 1,
                level = "info",
                header = red(" @@ ")
            )
        else:
            self._entropy.output(
                "[repo:%s|%s] %s: %s - %s %s" % (
                    blue(repo),
                    red(crippled_uri),
                    blue("lock error"),
                    rc_upload,
                    blue(_("mirror not locked")),
                    blue(lock_string),
                ),
                importance = 1,
                level = "error",
                header = darkred(" * ")
            )
            self._entropy._remove_local_database_lockfile(repo)

        return rc_upload


    def _do_mirror_unlock(self, uri, txc_handler, dblock = True, repo = None):

        if repo is None:
            repo = self._entropy.default_repository

        my_path = os.path.join(
            self._entropy._get_remote_database_relative_path(repo),
            self._settings['repositories']['branch'])

        crippled_uri = EntropyTransceiver.get_uri_name(uri)

        if dblock:
            dbfile = etpConst['etpdatabaselockfile']
        else:
            dbfile = etpConst['etpdatabasedownloadlockfile']

        # make sure
        remote_path = os.path.join(my_path, os.path.basename(dbfile))

        rc_delete = txc_handler.delete(remote_path)
        if rc_delete:
            self._entropy.output(
                "[repo:%s|%s] %s" % (
                            blue(repo),
                            red(crippled_uri),
                            blue(_("mirror successfully unlocked")),
                    ),
                importance = 1,
                level = "info",
                header = darkgreen(" * ")
            )
            if dblock:
                self._entropy._remove_local_database_lockfile(repo)
            else:
                self._entropy._remove_local_database_download_lockfile(repo)
        else:
            self._entropy.output(
                "[repo:%s|%s] %s: %s - %s" % (
                    blue(repo),
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

    def download_package(self, uri, pkg_relative_path, repo = None):

        if repo is None:
            repo = self._entropy.default_repository

        crippled_uri = EntropyTransceiver.get_uri_name(uri)

        tries = 0
        while tries < 5:

            tries += 1
            txc = self._entropy.Transceiver(uri)
            with txc as handler:

                self._entropy.output(
                    "[repo:%s|%s|#%s] %s: %s" % (
                        brown(repo),
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
                        pkg_relative_path, repo = repo)
                download_path = self._entropy.complete_local_package_path(
                    pkg_relative_path, repo = repo)

                download_dir = os.path.dirname(download_path)

                self._entropy.output(
                    "[repo:%s|%s|#%s] %s: %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        brown(str(tries)),
                        blue(_("downloading package")),
                        darkgreen(remote_path),
                    ),
                    importance = 1,
                    level = "info",
                    header = darkgreen(" * ")
                )

                if (not os.path.isdir(download_dir)) and \
                    (not os.access(download_dir, os.R_OK)):
                    self._entropy._ensure_dir_path(download_dir)

                rc_download = handler.download(remote_path, download_path)
                if not rc_download:
                    self._entropy.output(
                        "[repo:%s|%s|#%s] %s: %s %s" % (
                            brown(repo),
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
                    return rc_download

                dbconn = self._entropy.open_server_repository(read_only = True,
                    no_upload = True, repo = repo)
                idpackage = dbconn.getPackageIdFromDownload(pkg_relative_path)
                if idpackage == -1:
                    self._entropy.output(
                        "[repo:%s|%s|#%s] %s: %s %s" % (
                            brown(repo),
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

                storedmd5 = dbconn.retrieveDigest(idpackage)
                self._entropy.output(
                    "[repo:%s|%s|#%s] %s: %s" % (
                        brown(repo),
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
                        "[repo:%s|%s|#%s] %s: %s %s" % (
                            brown(repo),
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
                        "[repo:%s|%s|#%s] %s: %s %s" % (
                            brown(repo),
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
            "[repo:%s|%s|#%s] %s: %s %s" % (
                brown(repo),
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
        remote_dir = os.path.join(
            self._entropy._get_remote_database_relative_path(repo),
            self._settings['repositories']['branch'])

        # let raise exception if connection is impossible
        txc = self._entropy.Transceiver(uri)
        with txc as handler:

            compressedfile = etpConst[cmethod[2]]
            rc1 = handler.is_file(os.path.join(remote_dir, compressedfile))

            rev_file = self._entropy._get_local_database_revision_file(repo)
            revfilename = os.path.basename(rev_file)
            rc2 = handler.is_file(os.path.join(remote_dir, revfilename))

            revision = 0
            if not (rc1 and rc2):
                return [uri, revision]

            tmp_fd, rev_tmp_path = tempfile.mkstemp(prefix = "entropy.server")
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

                if os.access(rev_tmp_path, os.R_OK) and \
                    os.path.isfile(rev_tmp_path):

                    f_rev = open(rev_tmp_path, "r")
                    try:
                        revision = int(f_rev.readline().strip())
                    except ValueError:
                        mytxt = _("mirror hasn't valid repository revision file")
                        self._entropy.output(
                            "[repo:%s|%s] %s: %s" % (
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
                    f_rev.close()

                elif dlcount == 0:
                    self._entropy.output(
                        "[repo:%s|%s] %s: %s" % (
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
                        "[repo:%s|%s] %s: %s" % (
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

            return [uri, revision]

    def get_remote_repositories_status(self, repo = None, mirrors = None):

        if repo is None:
            repo = self._entropy.default_repository
        if not mirrors:
            mirrors = self._entropy.get_remote_repository_mirrors(repo)

        data = []
        for uri in mirrors:
            data.append(self._get_remote_db_status(uri, repo))

        return data

    def _is_local_repository_locked(self, repo = None):
        local_repo = repo
        if local_repo is None:
            local_repo = self._entropy.default_repository
        lock_file = self._entropy._get_database_lockfile(local_repo)
        return os.path.isfile(lock_file)

    def _get_mirrors_lock(self, repo = None):

        dbstatus = []
        remote_dir = os.path.join(
            self._entropy._get_remote_database_relative_path(repo),
            self._settings['repositories']['branch'])
        lock_file = os.path.join(remote_dir, etpConst['etpdatabaselockfile'])
        down_lock_file = os.path.join(remote_dir,
            etpConst['etpdatabasedownloadlockfile'])

        for uri in self._entropy.get_remote_repository_mirrors(repo):
            data = [uri, False, False]

            # let raise exception if connection is impossible
            txc = self._entropy.Transceiver(uri)
            with txc as handler:
                if handler.is_file(lock_file):
                    # upload locked
                    data[1] = True
                if handler.is_file(down_lock_file):
                    # download locked
                    data[2] = True
                dbstatus.append(data)

        return dbstatus

    def _update_rss_feed(self, repo = None):

        if repo is None:
            repo = self._entropy.default_repository

        product = self._settings['repositories']['product']
        #db_dir = self._entropy._get_local_database_dir(repo)
        rss_path = self._entropy._get_local_database_rss_file(repo)
        rss_light_path = self._entropy._get_local_database_rsslight_file(repo)
        rss_dump_name = repo + etpConst['rss-dump-name']
        db_revision_path = self._entropy._get_local_database_revision_file(repo)

        rss_title = "%s Online Repository Status" % (
            self._settings['system']['name'],)
        rss_description = \
            "Keep you updated on what's going on in the %s Repository." % (
                self._settings['system']['name'],)

        srv_set = self._settings[Server.SYSTEM_SETTINGS_PLG_ID]['server']

        rss_main = RSS(rss_path, rss_title, rss_description,
            maxentries = srv_set['rss']['max_entries'])
        # load dump
        db_actions = self.Cacher.pop(rss_dump_name,
            cache_dir = self._entropy.CACHE_DIR)
        if db_actions:
            try:
                f_rev = open(db_revision_path)
                revision = f_rev.readline().strip()
                f_rev.close()
            except (IOError, OSError):
                revision = "N/A"
            commitmessage = ''
            if ServerRssMetadata()['commitmessage']:
                commitmessage = ' :: ' + \
                    ServerRssMetadata()['commitmessage']

            title = ": " + self._settings['system']['name'] + " " + \
                product[0].upper() + product[1:] + " " + \
                self._settings['repositories']['branch'] + \
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
        ServerRssMetadata().clear()
        EntropyCacher.clear_cache_item(rss_dump_name,
            cache_dir = self._entropy.CACHE_DIR)

    def _create_file_checksum(self, file_path, checksum_path):
        mydigest = entropy.tools.md5sum(file_path)
        f_ck = open(checksum_path, "w")
        mystring = "%s  %s\n" % (mydigest, os.path.basename(file_path),)
        f_ck.write(mystring)
        f_ck.flush()
        f_ck.close()

    def _compress_file(self, file_path, destination_path, opener):
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

    def _get_files_to_sync(self, cmethod, download = False, repo = None,
        disabled_eapis = None):

        if repo is None:
            repo = self._entropy.default_repository

        if disabled_eapis is None:
            disabled_eapis = []

        critical = []
        extra_text_files = []
        gpg_signed_files = []
        data = {}
        db_rev_file = self._entropy._get_local_database_revision_file(repo)
        # adding ~ at the beginning makes this file to be appended at the end
        # of the upload queue
        data['~database_revision_file'] = db_rev_file
        extra_text_files.append(db_rev_file)
        critical.append(db_rev_file)

        # branch migration support scripts
        post_branch_mig_file = self._entropy._get_local_post_branch_mig_script(
            repo)
        if os.path.isfile(post_branch_mig_file) or download:
            if download:
                data['database_post_branch_hop_script'] = post_branch_mig_file
            extra_text_files.append(post_branch_mig_file)

        post_branch_upg_file = self._entropy._get_local_post_branch_upg_script(
            repo)
        if os.path.isfile(post_branch_upg_file) or download:
            if download:
                data['database_post_branch_upgrade_script'] = \
                    post_branch_upg_file
            extra_text_files.append(post_branch_upg_file)

        post_repo_update_file = self._entropy._get_local_post_repo_update_script(
            repo)
        if os.path.isfile(post_repo_update_file) or download:
            if download:
                data['database_post_repo_update_script'] = post_repo_update_file
            extra_text_files.append(post_repo_update_file)

        database_ts_file = self._entropy._get_local_database_timestamp_file(repo)
        if os.path.isfile(database_ts_file) or download:
            data['database_timestamp_file'] = database_ts_file
            if not download:
                critical.append(database_ts_file)

        database_package_mask_file = \
            self._entropy._get_local_database_mask_file(repo)
        if os.path.isfile(database_package_mask_file) or download:
            if download:
                data['database_package_mask_file'] = database_package_mask_file
            extra_text_files.append(database_package_mask_file)

        database_package_system_mask_file = \
            self._entropy._get_local_database_system_mask_file(repo)
        if os.path.isfile(database_package_system_mask_file) or download:
            if download:
                data['database_package_system_mask_file'] = \
                    database_package_system_mask_file
            extra_text_files.append(database_package_system_mask_file)

        database_package_confl_tagged_file = \
            self._entropy._get_local_database_confl_tagged_file(repo)
        if os.path.isfile(database_package_confl_tagged_file) or download:
            if download:
                data['database_package_confl_tagged_file'] = \
                    database_package_confl_tagged_file
            extra_text_files.append(database_package_confl_tagged_file)

        database_license_whitelist_file = \
            self._entropy._get_local_database_licensewhitelist_file(repo)
        if os.path.isfile(database_license_whitelist_file) or download:
            if download:
                data['database_license_whitelist_file'] = \
                    database_license_whitelist_file
            extra_text_files.append(database_license_whitelist_file)

        exp_based_pkgs_removal_file = \
            self._entropy._get_local_exp_based_pkgs_rm_whitelist_file(repo)
        if os.path.isfile(exp_based_pkgs_removal_file) or download:
            if download:
                data['exp_based_pkgs_removal_file'] = \
                    exp_based_pkgs_removal_file
            extra_text_files.append(exp_based_pkgs_removal_file)

        database_rss_file = self._entropy._get_local_database_rss_file(repo)
        if os.path.isfile(database_rss_file) or download:
            data['database_rss_file'] = database_rss_file
            if not download:
                critical.append(data['database_rss_file'])
        database_rss_light_file = \
            self._entropy._get_local_database_rsslight_file(repo)

        if os.path.isfile(database_rss_light_file) or download:
            data['database_rss_light_file'] = database_rss_light_file
            if not download:
                critical.append(data['database_rss_light_file'])

        pkglist_file = self._entropy._get_local_pkglist_file(repo)
        data['pkglist_file'] = pkglist_file
        if not download:
            critical.append(data['pkglist_file'])

        critical_updates_file = self._entropy._get_local_critical_updates_file(
            repo)
        if os.path.isfile(critical_updates_file) or download:
            if download:
                data['critical_updates_file'] = critical_updates_file
            extra_text_files.append(critical_updates_file)

        restricted_file = self._entropy._get_local_restricted_file(repo)
        if os.path.isfile(restricted_file) or download:
            if download:
                data['restricted_file'] = restricted_file
            extra_text_files.append(restricted_file)

        keywords_file = self._entropy._get_local_database_keywords_file(
            repo)
        if os.path.isfile(keywords_file) or download:
            if download:
                data['keywords_file'] = keywords_file
            extra_text_files.append(keywords_file)

        gpg_file = self._entropy._get_local_database_gpg_signature_file(repo)
        if os.path.isfile(gpg_file) or download:
            data['gpg_file'] = gpg_file
            # no need to add to extra_text_files, it will be added
            # afterwards
            gpg_signed_files.append(gpg_file)

        # EAPI 2,3
        if not download: # we don't need to get the dump

            # always push metafiles file, it's cheap
            data['metafiles_path'] = \
                self._entropy._get_local_database_compressed_metafiles_file(repo)
            critical.append(data['metafiles_path'])
            gpg_signed_files.append(data['metafiles_path'])

            if 2 not in disabled_eapis:

                data['dump_path_light'] = os.path.join(
                    self._entropy._get_local_database_dir(repo),
                    etpConst[cmethod[5]])
                critical.append(data['dump_path_light'])
                gpg_signed_files.append(data['dump_path_light'])

                data['dump_path_digest_light'] = os.path.join(
                    self._entropy._get_local_database_dir(repo),
                    etpConst[cmethod[6]])
                critical.append(data['dump_path_digest_light'])
                gpg_signed_files.append(data['dump_path_digest_light'])

        # EAPI 1
        if 1 not in disabled_eapis:

            data['compressed_database_path'] = os.path.join(
                self._entropy._get_local_database_dir(repo), etpConst[cmethod[2]])
            critical.append(data['compressed_database_path'])
            gpg_signed_files.append(data['compressed_database_path'])

            data['compressed_database_path_light'] = os.path.join(
                self._entropy._get_local_database_dir(repo), etpConst[cmethod[7]])
            critical.append(data['compressed_database_path_light'])
            gpg_signed_files.append(data['compressed_database_path_light'])

            data['database_path_digest'] = os.path.join(
                self._entropy._get_local_database_dir(repo),
                etpConst['etpdatabasehashfile']
            )
            critical.append(data['database_path_digest'])
            gpg_signed_files.append(data['database_path_digest'])

            data['compressed_database_path_digest'] = os.path.join(
                self._entropy._get_local_database_dir(repo),
                etpConst[cmethod[2]] + etpConst['packagesmd5fileext']
            )
            critical.append(data['compressed_database_path_digest'])
            gpg_signed_files.append(data['compressed_database_path_digest'])

            data['compressed_database_path_digest_light'] = os.path.join(
                self._entropy._get_local_database_dir(repo),
                etpConst[cmethod[8]]
            )
            critical.append(data['compressed_database_path_digest_light'])
            gpg_signed_files.append(
                data['compressed_database_path_digest_light'])


        # SSL cert file, just for reference
        ssl_ca_cert = self._entropy._get_local_database_ca_cert_file()
        if os.path.isfile(ssl_ca_cert):
            if download:
                data['ssl_ca_cert_file'] = ssl_ca_cert
            extra_text_files.append(ssl_ca_cert)

        ssl_server_cert = self._entropy._get_local_database_server_cert_file()
        if os.path.isfile(ssl_server_cert):
            if download:
                data['ssl_server_cert_file'] = ssl_server_cert
            extra_text_files.append(ssl_server_cert)

        # Some information regarding how packages are built
        spm_files_map = self._entropy.Spm_class().config_files_map()
        spm_syms = {}
        for myname, myfile in spm_files_map.items():
            if os.path.islink(myfile):
                spm_syms[myname] = myfile
                continue # we don't want symlinks
            if os.path.isfile(myfile) and os.access(myfile, os.R_OK):
                if download:
                    data[myname] = myfile
                extra_text_files.append(myfile)

        # NOTE: for symlinks, we read their link and send a file with that
        # content. This is the default behaviour for now and allows to send
        # /etc/make.profile link pointer correctly.
        tmp_dirs = []
        for symname, symfile in spm_syms.items():

            mytmpdir = tempfile.mkdtemp(dir = etpConst['entropyunpackdir'])
            tmp_dirs.append(mytmpdir)
            mytmpfile = os.path.join(mytmpdir, os.path.basename(symfile))
            mylink = os.readlink(symfile)
            f_mkp = open(mytmpfile, "w")
            f_mkp.write(mylink)
            f_mkp.flush()
            f_mkp.close()

            if download:
                data[symname] = mytmpfile
            extra_text_files.append(mytmpfile)

        return data, critical, extra_text_files, tmp_dirs, gpg_signed_files

    def _show_package_sets_messages(self, repo):

        self._entropy.output(
            "[repo:%s] %s:" % (
                brown(repo),
                blue(_("configured package sets")),
            ),
            importance = 0,
            level = "info",
            header = darkgreen(" * ")
        )
        sets_data = self._entropy.sets_available(match_repo = [repo])
        if not sets_data:
            self._entropy.output(
                "%s" % (_("None configured"),),
                importance = 0,
                level = "info",
                header = brown("    # ")
            )
            return
        sorter = lambda (x, y, z): y
        for s_repo, s_name, s_sets in sorted(sets_data, key = sorter):
            self._entropy.output(
                blue("%s" % (s_name,)),
                importance = 0,
                level = "info",
                header = brown("    # ")
            )

    def _show_eapi3_upload_messages(self, crippled_uri, database_path, repo):

        self._entropy.output(
            "[repo:%s|%s|%s:%s] %s" % (
                brown(repo),
                darkgreen(crippled_uri),
                red("EAPI"),
                bold("3"),
                blue(_("preparing uncompressed repository for the upload")),
            ),
            importance = 0,
            level = "info",
            header = darkgreen(" * ")
        )
        self._entropy.output(
            "%s: %s" % (_("repository path"), blue(database_path),),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )

    def _show_eapi2_upload_messages(self, crippled_uri, database_path,
        upload_data, cmethod, repo):

        if repo is None:
            repo = self._entropy.default_repository

        self._entropy.output(
            "[repo:%s|%s|%s:%s] %s" % (
                brown(repo),
                darkgreen(crippled_uri),
                red("EAPI"),
                bold("2"),
                blue(_("creating compressed repository dump + checksum")),
            ),
            importance = 0,
            level = "info",
            header = darkgreen(" * ")
        )
        self._entropy.output(
            "%s: %s" % (_("repository path"), blue(database_path),),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (
                _("dump light"),
                blue(upload_data['dump_path_light']),
            ),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (
                _("dump light checksum"),
                blue(upload_data['dump_path_digest_light']),
            ),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )

        self._entropy.output(
            "%s: %s" % (_("opener"), blue(str(cmethod[0])),),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )

    def _show_eapi1_upload_messages(self, crippled_uri, database_path,
        upload_data, cmethod, repo):

        self._entropy.output(
            "[repo:%s|%s|%s:%s] %s" % (
                brown(repo),
                darkgreen(crippled_uri),
                red("EAPI"),
                bold("1"),
                blue(_("compressing repository + checksum")),
            ),
            importance = 0,
            level = "info",
            header = darkgreen(" * "),
            back = True
        )
        self._entropy.output(
            "%s: %s" % (_("repository path"), blue(database_path),),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (
                _("compressed repository path"),
                blue(upload_data['compressed_database_path']),
            ),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (
                _("repository checksum"),
                blue(upload_data['database_path_digest']),
            ),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (
                _("compressed checksum"),
                blue(upload_data['compressed_database_path_digest']),
            ),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (_("opener"), blue(str(cmethod[0])),),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )

    def __get_repo_security_intf(self, repo):
        try:
            repo_sec = RepositorySecurity()
            if not repo_sec.is_keypair_available(repo):
                raise KeyError("no key avail")
        except RepositorySecurity.KeyExpired:
            self._entropy.output("%s: %s" % (
                    darkred(_("Keys for repository are expired")),
                    bold(repo),
                ),
                level = "warning",
                header = bold(" !!! ")
            )
        except RepositorySecurity.GPGError:
            return
        except KeyError:
            return
        return repo_sec

    def __write_gpg_pubkey(self, repo_sec, repo):
        pubkey = repo_sec.get_pubkey(repo)
        # write pubkey to file and add to data upload
        gpg_path = self._entropy._get_local_database_gpg_signature_file(repo)
        with open(gpg_path, "w") as gpg_f:
            gpg_f.write(pubkey)
            gpg_f.flush()
        return gpg_path

    def _create_metafiles_file(self, compressed_dest_path, file_list, repo):

        found_file_list = [x for x in file_list if os.path.isfile(x) and \
            os.path.isfile(x) and os.access(x, os.R_OK)]

        not_found_file_list = ["%s\n" % (os.path.basename(x),) for x in \
            file_list if x not in found_file_list]

        # GPG, also pack signature.asc inside
        repo_sec = self.__get_repo_security_intf(repo)
        if repo_sec is not None:
            gpg_path = self.__write_gpg_pubkey(repo_sec, repo)
            if gpg_path is not None:
                found_file_list.append(gpg_path)
            else:
                gpg_path = \
                    self._entropy._get_local_database_gpg_signature_file(repo)
                not_found_file_list.append(gpg_path) # not found

        metafile_not_found_file = \
            self._entropy._get_local_database_metafiles_not_found_file(repo)
        f_meta = open(metafile_not_found_file, "w")
        f_meta.writelines(not_found_file_list)
        f_meta.flush()
        f_meta.close()
        found_file_list.append(metafile_not_found_file)
        if os.path.isfile(compressed_dest_path):
            os.remove(compressed_dest_path)

        entropy.tools.compress_files(compressed_dest_path, found_file_list)

    def _create_upload_gpg_signatures(self, upload_data, to_sign_files, repo):
        """
        This method creates .asc files for every path that is going to be
        uploaded. upload_data directly comes from _upload_database()
        """
        repo_sec = self.__get_repo_security_intf(repo)
        if repo_sec is None:
            return

        # for every item in upload_data, create a gpg signature
        gpg_upload_data = {}
        for item_id, item_path in upload_data.items():
            if item_path not in to_sign_files:
                continue
            if os.path.isfile(item_path) and os.access(item_path, os.R_OK):
                gpg_item_id = item_id + "_gpg_sign_part"
                if gpg_item_id in upload_data:
                    raise KeyError("wtf!")
                sign_path = repo_sec.sign_file(repo, item_path)
                gpg_upload_data[gpg_item_id] = sign_path
        upload_data.update(gpg_upload_data)

    def _mirror_lock_check(self, uri, repo = None):
        """
        Return whether mirror is locked.
        """

        if repo is None:
            repo = self._entropy.default_repository
        gave_up = False

        lock_file = self._entropy._get_database_lockfile(repo)
        lock_filename = os.path.basename(lock_file)

        remote_dir = os.path.join(
            self._entropy._get_remote_database_relative_path(repo),
            self._settings['repositories']['branch'])
        remote_lock_file = os.path.join(remote_dir, lock_filename)

        txc = self._entropy.Transceiver(uri)
        with txc as handler:

            if not os.path.isfile(lock_file) and \
                handler.is_file(remote_lock_file):

                crippled_uri = EntropyTransceiver.get_uri_name(uri)
                self._entropy.output(
                    "[repo:%s|%s|%s] %s, %s" % (
                        brown(str(repo)),
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
                            red("[repo:%s|%s|%s] %s !" % (
                                    repo,
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

    def _shrink_database_and_close(self, repo = None):
        dbconn = self._entropy.open_server_repository(read_only = False,
            no_upload = True, repo = repo, indexing = False,
            do_treeupdates = False)
        dbconn.clean()
        dbconn.dropAllIndexes()
        dbconn.vacuum()
        dbconn.vacuum()
        dbconn.commit()
        self._entropy.close_repository(dbconn)

    def _get_current_timestamp(self):
        from datetime import datetime
        return "%s" % (datetime.fromtimestamp(time.time()),)

    def _update_repository_timestamp(self, repo = None):
        if repo is None:
            repo = self._entropy.default_repository
        ts_file = self._entropy._get_local_database_timestamp_file(repo)
        current_ts = self._get_current_timestamp()
        ts_f = open(ts_file, "w")
        ts_f.write(current_ts)
        ts_f.flush()
        ts_f.close()

    def _sync_database_treeupdates(self, repo = None):

        if repo is None:
            repo = self._entropy.default_repository
        dbconn = self._entropy.open_server_repository(read_only = False,
            no_upload = True, repo = repo, do_treeupdates = False)
        # grab treeupdates from other databases and inject
        srv_set = self._settings[Server.SYSTEM_SETTINGS_PLG_ID]['server']
        server_repos = list(srv_set['repositories'].keys())
        all_actions = set()
        for myrepo in server_repos:

            # avoid __default__
            if myrepo == etpConst['clientserverrepoid']:
                continue

            mydbc = self._entropy.open_server_repository(just_reading = True,
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
        except Error as err:
            entropy.tools.print_traceback()
            mytxt = "%s, %s: %s. %s" % (
                _("Troubles with treeupdates"),
                _("error"),
                err,
                _("Bumping old data back"),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning"
            )
            # restore previous data
            dbconn.bumpTreeUpdatesActions(backed_up_entries)

        dbconn.commit()

    def _create_repository_pkglist(self, repo = None, branch = None):
        pkglist_file = self._entropy._get_local_pkglist_file(repo = repo,
            branch = branch)

        tmp_pkglist_file = pkglist_file + ".tmp"
        dbconn = self._entropy.open_server_repository(repo = repo,
            just_reading = True, do_treeupdates = False)
        pkglist = dbconn.listAllDownloads(do_sort = True, full_path = True)

        with open(tmp_pkglist_file, "w") as pkg_f:
            for pkg in pkglist:
                pkg_f.write(pkg + "\n")
            pkg_f.flush()

        os.rename(tmp_pkglist_file, pkglist_file)

    def _upload_database(self, uris, lock_check = False, pretend = False,
            repo = None):

        if repo is None:
            repo = self._entropy.default_repository

        srv_set = self._settings[Server.SYSTEM_SETTINGS_PLG_ID]['server']
        if srv_set['rss']['enabled']:
            self._update_rss_feed(repo = repo)

        upload_errors = False
        broken_uris = set()
        fine_uris = set()

        disabled_eapis = sorted(srv_set['disabled_eapis'])
        db_format = srv_set['database_file_format']
        cmethod = etpConst['etpdatabasecompressclasses'].get(db_format)
        if cmethod is None:
            raise AttributeError("wrong repository compression method passed")
        database_path = self._entropy._get_local_database_file(repo)

        if disabled_eapis:
            self._entropy.output(
                "[repo:%s|%s] %s: %s" % (
                    blue(repo),
                    darkgreen(_("upload")),
                    darkred(_("disabled EAPI")),
                    bold(', '.join([str(x) for x in disabled_eapis])),
                ),
                importance = 1,
                level = "warning",
                header = darkgreen(" * ")
            )

        # create/update timestamp file
        self._update_repository_timestamp(repo)
        # create pkglist service file
        self._create_repository_pkglist(repo)

        upload_data, critical, text_files, tmp_dirs, gpg_to_sign_files = \
            self._get_files_to_sync(cmethod, repo = repo,
                disabled_eapis = disabled_eapis)

        self._entropy.output(
            "[repo:%s|%s] %s" % (
                blue(repo),
                darkgreen(_("upload")),
                darkgreen(_("preparing to upload repository to mirror")),
            ),
            importance = 1,
            level = "info",
            header = darkgreen(" * ")
        )

        self._sync_database_treeupdates(repo)
        self._entropy._update_database_package_sets(repo)
        dbconn = self._entropy.open_server_repository(
            read_only = False, no_upload = True, repo = repo,
            do_treeupdates = False)
        dbconn.commit()
        # now we can safely copy it

        # Package Sets info
        self._show_package_sets_messages(repo)

        # backup current database to avoid re-indexing
        old_dbpath = self._entropy._get_local_database_file(repo)
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

        self._shrink_database_and_close(repo)

        if 2 not in disabled_eapis:
            self._show_eapi2_upload_messages("~all~", database_path,
                upload_data, cmethod, repo)

            # create compressed dump + checksum
            eapi2_dbfile = self._entropy._get_local_database_file(repo)
            temp_eapi2_dbfile = eapi2_dbfile+".light_eapi2.tmp"
            shutil.copy2(eapi2_dbfile, temp_eapi2_dbfile)
            # open and remove content table
            eapi2_tmp_dbconn = \
                self._entropy.open_generic_repository(
                    temp_eapi2_dbfile, indexing_override = False,
                    xcache = False)
            eapi2_tmp_dbconn.dropContent()
            eapi2_tmp_dbconn.dropChangelog()
            eapi2_tmp_dbconn.commit()

            # opener = cmethod[0]
            f_out = cmethod[0](upload_data['dump_path_light'], "wb")
            try:
                eapi2_tmp_dbconn.exportRepository(f_out)
            finally:
                f_out.close()
                eapi2_tmp_dbconn.close()

            os.remove(temp_eapi2_dbfile)
            self._create_file_checksum(upload_data['dump_path_light'],
                upload_data['dump_path_digest_light'])

        if 1 not in disabled_eapis:

            self._show_eapi1_upload_messages("~all~", database_path,
                upload_data, cmethod, repo)

            # compress the database and create uncompressed
            # database checksum -- DEPRECATED
            self._compress_file(database_path,
                upload_data['compressed_database_path'], cmethod[0])
            self._create_file_checksum(database_path,
                upload_data['database_path_digest'])

            # create compressed database checksum
            self._create_file_checksum(
                upload_data['compressed_database_path'],
                upload_data['compressed_database_path_digest'])

            # create light version of the compressed db
            eapi1_dbfile = self._entropy._get_local_database_file(repo)
            temp_eapi1_dbfile = eapi1_dbfile+".light"
            shutil.copy2(eapi1_dbfile, temp_eapi1_dbfile)
            # open and remove content table
            eapi1_tmp_dbconn = \
                self._entropy.open_generic_repository(
                    temp_eapi1_dbfile, indexing_override = False,
                    xcache = False)
            eapi1_tmp_dbconn.dropContent()
            eapi1_tmp_dbconn.dropChangelog()
            eapi1_tmp_dbconn.commit()
            eapi1_tmp_dbconn.vacuum()
            eapi1_tmp_dbconn.close()

            # compress
            self._compress_file(temp_eapi1_dbfile,
                upload_data['compressed_database_path_light'], cmethod[0])
            # go away, we don't need you anymore
            os.remove(temp_eapi1_dbfile)
            # create compressed light database checksum
            self._create_file_checksum(
                upload_data['compressed_database_path_light'],
                upload_data['compressed_database_path_digest_light'])

        # always upload metafile, it's cheap and also used by EAPI1,2
        self._create_metafiles_file(upload_data['metafiles_path'],
            text_files, repo)
        # Setup GPG signatures for files that are going to be uploaded
        self._create_upload_gpg_signatures(upload_data, gpg_to_sign_files,
            repo)

        for uri in uris:

            if lock_check:
                given_up = self._mirror_lock_check(uri, repo = repo)
                if given_up:
                    upload_errors = True
                    broken_uris.add(uri)
                    continue

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            # EAPI 3
            if 3 not in disabled_eapis:
                self._show_eapi3_upload_messages(crippled_uri, database_path,
                    repo)

            if not pretend:
                self.lock_mirrors_for_download(True, [uri], repo = repo)
                # upload
                uploader = self.TransceiverServerHandler(
                    self._entropy,
                    [uri],
                    [upload_data[x] for x in sorted(upload_data)],
                    critical_files = critical,
                    repo = repo
                )
                errors, m_fine_uris, m_broken_uris = uploader.go()
                if errors:
                    my_broken_uris = sorted([
                        (EntropyTransceiver.get_uri_name(x[0]),
                            x[1]) for x in m_broken_uris])
                    self._entropy.output(
                        "[repo:%s|%s|%s] %s" % (
                            repo,
                            crippled_uri,
                            _("errors"),
                            _("upload failed, not unlocking and continuing"),
                        ),
                        importance = 0,
                        level = "error",
                        header = darkred(" !!! ")
                    )
                    # get reason
                    reason = my_broken_uris[0][1]
                    self._entropy.output(
                        blue("%s: %s" % (_("reason"), reason,)),
                        importance = 0,
                        level = "error",
                        header = blue("    # ")
                    )
                    upload_errors = True
                    broken_uris |= m_broken_uris
                    continue

                # unlock
                self.lock_mirrors_for_download(False, [uri], repo = repo)

            fine_uris |= m_fine_uris

        if (not pretend) and copy_back and os.path.isfile(backup_dbpath):
            # copy db back
            self._entropy.close_repositories()
            further_backup_dbpath = old_dbpath+".security_backup"
            if os.path.isfile(further_backup_dbpath):
                os.remove(further_backup_dbpath)
            shutil.copy2(old_dbpath, further_backup_dbpath)
            shutil.move(backup_dbpath, old_dbpath)

        if not fine_uris:
            upload_errors = True

        # remove temporary directories
        for tmp_dir in tmp_dirs:
            try:
                shutil.rmtree(tmp_dir, True)
            except shutil.Error:
                continue

        return upload_errors, broken_uris, fine_uris


    def _download_database(self, uris, lock_check = False, pretend = False,
        repo = None):

        if repo is None:
            repo = self._entropy.default_repository

        download_errors = False
        broken_uris = set()
        fine_uris = set()
        srv_set = self._settings[Server.SYSTEM_SETTINGS_PLG_ID]['server']
        disabled_eapis = sorted(srv_set['disabled_eapis'])

        for uri in uris:

            db_format = srv_set['database_file_format']
            cmethod = etpConst['etpdatabasecompressclasses'].get(db_format)
            if cmethod is None:
                raise AttributeError("wrong repository compression method passed")

            crippled_uri = EntropyTransceiver.get_uri_name(uri)
            database_path = self._entropy._get_local_database_file(repo)
            database_dir_path = os.path.dirname(
                self._entropy._get_local_database_file(repo))

            download_data, critical, text_files, tmp_dirs, \
                gpg_to_verify_files = self._get_files_to_sync(cmethod,
                    download = True, repo = repo,
                        disabled_eapis = disabled_eapis)
            try:

                mytmpdir = tempfile.mkdtemp(prefix = "entropy.server")

                self._entropy.output(
                    "[repo:%s|%s|%s] %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        red(_("download")),
                        blue(_("preparing to download repository from mirror")),
                    ),
                    importance = 1,
                    level = "info",
                    header = darkgreen(" * ")
                )
                files_to_sync = sorted(download_data.keys())
                for myfile in files_to_sync:
                    self._entropy.output(
                        "%s: %s" % (
                            blue(_("download path")),
                            brown(download_data[myfile]),
                        ),
                        importance = 0,
                        level = "info",
                        header = brown("    # ")
                    )

                if lock_check:
                    given_up = self._mirror_lock_check(uri, repo = repo)
                    if given_up:
                        download_errors = True
                        broken_uris.add(uri)
                        continue

                # avoid having others messing while we're downloading
                self.lock_mirrors(True, [uri], repo = repo)

                if not pretend:
                    # download
                    downloader = self.TransceiverServerHandler(
                        self._entropy, [uri],
                        [download_data[x] for x in download_data], download = True,
                        local_basedir = mytmpdir, critical_files = critical,
                        repo = repo
                    )
                    errors, m_fine_uris, m_broken_uris = downloader.go()
                    if errors:
                        my_broken_uris = sorted([
                            (EntropyTransceiver.get_uri_name(x[0]),
                                x[1]) for x in m_broken_uris])
                        self._entropy.output(
                            "[repo:%s|%s|%s] %s" % (
                                brown(repo),
                                darkgreen(crippled_uri),
                                red(_("errors")),
                                blue(_("failed to download from mirror")),
                            ),
                            importance = 0,
                            level = "error",
                            header = darkred(" !!! ")
                        )
                        # get reason
                        reason = my_broken_uris[0][1]
                        self._entropy.output(
                            blue("%s: %s" % (_("reason"), reason,)),
                            importance = 0,
                            level = "error",
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
                        entropy.tools.uncompress_file(compressed_file,
                            uncompressed_file, cmethod[0])

                    # now move
                    for myfile in os.listdir(mytmpdir):
                        fromfile = os.path.join(mytmpdir, myfile)
                        tofile = os.path.join(database_dir_path, myfile)
                        shutil.move(fromfile, tofile)
                        const_setup_file(tofile, etpConst['entropygid'], 0o664)

                if os.path.isdir(mytmpdir):
                    shutil.rmtree(mytmpdir)
                if os.path.isdir(mytmpdir):
                    os.rmdir(mytmpdir)

                fine_uris.add(uri)
                self.lock_mirrors(False, [uri], repo = repo)

            finally:
                # remove temporary directories
                for tmp_dir in tmp_dirs:
                    try:
                        shutil.rmtree(tmp_dir, True)
                    except shutil.Error:
                        continue

        return download_errors, fine_uris, broken_uris

    def _calculate_database_sync_queues(self, repo = None):

        if repo is None:
            repo = self._entropy.default_repository

        remote_status =  self.get_remote_repositories_status(repo)
        local_revision = self._entropy.get_local_repository_revision(repo)
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
                        download_latest = remote_item
                        break

            if download_latest:
                upload_queue = [x for x in remote_status if \
                    (x[1] < highest_remote_revision)]
            else:
                upload_queue = [x for x in remote_status if \
                    (x[1] < local_revision)]

        return download_latest, upload_queue

    def sync_repositories(self, no_upload = False, unlock_mirrors = False,
        repo = None, conf_files_qa_test = True):

        if repo is None:
            repo = self._entropy.default_repository

        while True:

            db_locked = False
            if self._is_local_repository_locked(repo):
                db_locked = True

            lock_data = self._get_mirrors_lock(repo)
            mirrors_locked = [x for x in lock_data if x[1]]

            if not mirrors_locked and db_locked:
                # mirrors not locked remotely but only locally
                mylock_file = self._entropy._get_database_lockfile(repo)
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

        download_latest, upload_queue = self._calculate_database_sync_queues(
            repo)

        if not download_latest and not upload_queue:
            self._entropy.output(
                "[repo:%s|%s] %s" % (
                    brown(repo),
                    red(_("sync")), # something short please
                    blue(_("repository already in sync")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            return 0, set(), set()

        if download_latest:
            # close all the currently open repos
            self._entropy.close_repositories()
            download_uri = download_latest[0]
            download_errors, fine_uris, broken_uris = self._download_database(
                [download_uri], repo = repo)
            if download_errors:
                self._entropy.output(
                    "[repo:%s|%s] %s: %s" % (
                        brown(repo),
                        red(_("sync")),
                        blue(_("repository sync failed")),
                        red(_("download issues")),
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" !!! ")
                )
                return 1, fine_uris, broken_uris

        if upload_queue and not no_upload:

            # Some internal QA checks, make sure everything is fine
            # on the repo

            srv_set = self._settings[Server.SYSTEM_SETTINGS_PLG_ID]['server']
            base_repo = srv_set['base_repository_id']
            if base_repo is None:
                base_repo = repo

            base_deps_not_found = set()
            if base_repo != repo:
                base_deps_not_found = self._entropy.dependencies_test(
                    repo = base_repo)

            deps_not_found = self._entropy.dependencies_test(repo = repo)
            if (deps_not_found or base_deps_not_found) \
                and not self._entropy.community_repo:

                self._entropy.output(
                    "[repo:%s|%s] %s: %s" % (
                        brown(repo),
                        red(_("sync")),
                        blue(_("repository sync forbidden")),
                        red(_("dependencies_test() reported errors")),
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" !!! ")
                )
                return 3, set(), set()

            if conf_files_qa_test:
                problems = self._entropy._check_config_file_updates()
                if problems:
                    return 4, set(), set()

            self._entropy.output(
                "[repo:%s|%s] %s" % (
                    brown(repo),
                    red(_("config files")), # something short please
                    blue(_("no configuration files to commit. All fine.")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ "),
                back = True
            )

            uris = [x[0] for x in upload_queue]
            errors, fine_uris, broken_uris = self._upload_database(uris,
                repo = repo)
            if errors:
                self._entropy.output(
                    "[repo:%s|%s] %s: %s" % (
                        brown(repo),
                        red(_("sync")),
                        blue(_("repository sync failed")),
                        red(_("upload issues")),
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" !!! ")
                )
                return 2, fine_uris, broken_uris


        self._entropy.output(
            "[repo:%s|%s] %s" % (
                brown(repo),
                red(_("sync")),
                blue(_("repository sync completed successfully")),
            ),
            importance = 1,
            level = "info",
            header = darkgreen(" * ")
        )

        if unlock_mirrors:
            self.lock_mirrors(False, repo = repo)
        return 0, set(), set()

    def _calculate_local_upload_files(self, repo = None):
        upload_files = 0
        upload_packages = set()
        upload_dir = self._entropy._get_local_upload_directory(repo = repo)

        # check if it exists
        if not os.path.isdir(upload_dir):
            return upload_files, upload_packages

        branch = self._settings['repositories']['branch']
        upload_pkgs = self._entropy._get_basedir_pkg_listing(upload_dir,
            repo = repo, branch = branch)

        pkg_ext = etpConst['packagesext']
        pkg_md5_ext = etpConst['packagesmd5fileext']
        for package in upload_pkgs:
            if package.endswith(pkg_ext) or package.endswith(pkg_md5_ext):
                upload_packages.add(package)
                if package.endswith(pkg_ext):
                    upload_files += 1

        return upload_files, upload_packages

    def _calculate_local_package_files(self, repo = None):
        local_files = 0
        local_packages = set()
        base_dir = self._entropy._get_local_repository_base_directory(
            repo = repo)

        # check if it exists
        if not os.path.isdir(base_dir):
            return local_files, local_packages

        branch = self._settings['repositories']['branch']
        pkg_files = self._entropy._get_basedir_pkg_listing(base_dir,
            repo = repo, branch = branch)

        pkg_ext = etpConst['packagesext']
        pkg_md5_ext = etpConst['packagesmd5fileext']
        for package in pkg_files:
            if package.endswith(pkg_ext) or package.endswith(pkg_md5_ext):
                local_packages.add(package)
                if package.endswith(pkg_ext):
                    local_files += 1

        return local_files, local_packages


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
                "[branch:%s|%s] %s [%s]" % (
                    brown(branch),
                    blue(_("upload")),
                    darkgreen(package),
                    size,
                ),
                importance = 0,
                level = "info",
                header = red("    # ")
            )
        key_sorter = lambda (pkg, rel, size): rel

        for package, rel_pkg, size in sorted(download, key = key_sorter):
            package = darkred(rel_pkg)
            size = blue(entropy.tools.bytes_into_human(size))
            self._entropy.output(
                "[branch:%s|%s] %s [%s]" % (
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
                "[branch:%s|%s] %s [%s]" % (
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
                "[branch:%s|%s] %s [%s]" % (
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

    def _calculate_remote_package_files(self, uri, txc_handler, repo = None):

        remote_files = 0
        remote_packages_data = {}
        remote_packages = []
        branch = self._settings['repositories']['branch']

        pkgs_dir_types = self._entropy._get_pkg_dir_names()
        for pkg_dir_type in pkgs_dir_types:

            remote_dir = self._entropy.complete_remote_package_relative_path(
                pkg_dir_type, repo = repo)
            remote_dir = os.path.join(remote_dir, etpConst['currentarch'],
                branch)
            only_dir = self._entropy.complete_remote_package_relative_path("",
                repo = repo)
            db_url_dir = remote_dir[len(only_dir):]

            # create path to lock file if it doesn't exist
            if not txc_handler.is_dir(remote_dir):
                txc_handler.makedirs(remote_dir)

            remote_packages_info = txc_handler.list_content_metadata(remote_dir)
            remote_packages += [os.path.join(db_url_dir, x[0]) for x \
                in remote_packages_info]

            for pkg in remote_packages:
                if pkg.endswith(etpConst['packagesext']):
                    remote_files += 1

            my_remote_pkg_data = dict((os.path.join(db_url_dir, x[0]),
                int(x[1])) for x in remote_packages_info)
            remote_packages_data.update(my_remote_pkg_data)

        return remote_files, remote_packages, remote_packages_data

    def calculate_packages_to_sync(self, uri, repo = None):

        if repo is None:
            repo = self._entropy.default_repository

        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        upload_files, upload_packages = self._calculate_local_upload_files(repo)
        local_files, local_packages = self._calculate_local_package_files(repo)
        self._show_local_sync_stats(upload_files, local_files)

        self._entropy.output(
            "%s: %s" % (blue(_("Remote statistics for")), red(crippled_uri),),
            importance = 1,
            level = "info",
            header = red(" @@ ")
        )

        txc = self._entropy.Transceiver(uri)
        with txc as handler:
            remote_files, remote_packages, remote_packages_data = \
                self._calculate_remote_package_files(uri, handler, repo = repo)

        self._entropy.output(
            "%s:  %s %s" % (
                blue(_("remote packages")),
                bold(str(remote_files)),
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
            self._calculate_sync_queues(upload_packages, local_packages,
                remote_packages, remote_packages_data, repo)
        return upload_queue, download_queue, removal_queue, fine_queue, \
            remote_packages_data

    def _calculate_sync_queues(self, upload_packages, local_packages,
        remote_packages, remote_packages_data, repo = None):

        upload_queue = set()
        download_queue = set()
        removal_queue = set()
        fine_queue = set()
        branch = self._settings['repositories']['branch']

        for local_package in upload_packages:

            if not local_package.endswith(etpConst['packagesext']):
                continue

            if local_package in remote_packages:

                local_filepath = \
                    self._entropy.complete_local_upload_package_path(
                        local_package, repo = repo)

                local_size = entropy.tools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(local_package)
                if remote_size is None:
                    remote_size = 0
                if local_size != remote_size:
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

            if not local_package.endswith(etpConst['packagesext']):
                continue

            if local_package in remote_packages:
                local_filepath = self._entropy.complete_local_package_path(
                    local_package, repo = repo)
                local_size = entropy.tools.get_file_size(local_filepath)
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

            if not remote_package.endswith(etpConst['packagesext']):
                continue

            if remote_package in local_packages:
                local_filepath = self._entropy.complete_local_package_path(
                    remote_package, repo = repo)
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
            else:
                # this means that the local package does not exist
                # so, we need to download it
                 # ignore .tmp files
                if not remote_package.endswith(
                    EntropyUriHandler.TMP_TXC_FILE_EXT):
                    download_queue.add(remote_package)

        # Collect packages that don't exist anymore in the database
        # so we can filter them out from the download queue
        dbconn = self._entropy.open_server_repository(just_reading = True,
            repo = repo)
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
                item, repo = repo)
            size = entropy.tools.get_file_size(local_filepath)
            metainfo['removal'] += size
            removal.append((local_filepath, item, size))

        for item in download_queue:

            local_filepath = self._entropy.complete_local_upload_package_path(
                item, repo = repo)
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
                item, repo = repo)

            local_filepath_pkgs = self._entropy.complete_local_package_path(
                item, repo = repo)
            if os.path.isfile(local_filepath):
                size = entropy.tools.get_file_size(local_filepath)
                upload.append((local_filepath, item, size))
            else:
                size = entropy.tools.get_file_size(local_filepath_pkgs)
                upload.append((local_filepath_pkgs, item, size))
            metainfo['upload'] += size

        return upload, download, removal, do_copy, metainfo

    def _sync_run_removal_queue(self, removal_queue, repo = None):

        if repo is None:
            repo = self._entropy.default_repository
        branch = self._settings['repositories']['branch']

        for remove_filepath, rel_path, size in removal_queue:

            remove_filename = os.path.basename(remove_filepath)
            remove_filepath_hash = remove_filepath + \
                etpConst['packagesmd5fileext']
            remove_filepath_exp = remove_filepath + \
                etpConst['packagesexpirationfileext']

            self._entropy.output(
                "[repo:%s|%s|%s] %s: %s [%s]" % (
                    brown(repo),
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
            if os.path.isfile(remove_filepath_hash):
                os.remove(remove_filepath_hash)
            if os.path.isfile(remove_filepath_exp):
                os.remove(remove_filepath_exp)

        self._entropy.output(
            "[repo:%s|%s|%s] %s" % (
                brown(repo),
                red(_("sync")),
                brown(branch),
                blue(_("removal complete")),
            ),
            importance = 0,
            level = "info",
            header = darkred(" * ")
        )


    def _sync_run_copy_queue(self, copy_queue, repo = None):

        if repo is None:
            repo = self._entropy.default_repository
        branch = self._settings['repositories']['branch']

        for from_file, rel_file, size in copy_queue:
            from_file_hash = from_file + etpConst['packagesmd5fileext']

            to_file = self._entropy.complete_local_package_path(rel_file)
            to_file_hash = to_file+etpConst['packagesmd5fileext']
            expiration_file = to_file+etpConst['packagesexpirationfileext']

            self._entropy.output(
                "[repo:%s|%s|%s] %s: %s" % (
                    brown(repo),
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
            self._create_file_checksum(from_file, from_file_hash)
            shutil.copy2(from_file_hash, to_file_hash)

            # clear expiration file
            if os.path.isfile(expiration_file):
                os.remove(expiration_file)


    def _sync_run_upload_queue(self, uri, upload_queue, repo = None):

        if repo is None:
            repo = self._entropy.default_repository
        branch = self._settings['repositories']['branch']

        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        queue_map = {}

        for upload_path, rel_path, size in upload_queue:

            hash_file = upload_path + etpConst['packagesmd5fileext']
            if not os.path.isfile(hash_file):
                entropy.tools.create_md5_file(upload_path)

            rel_dir = os.path.dirname(rel_path)
            obj = queue_map.setdefault(rel_dir, [])
            obj.append(hash_file)
            obj.append(upload_path)

        errors = False
        m_fine_uris = set()
        m_broken_uris = set()
        for rel_path, myqueue in queue_map.items():

            remote_dir = self._entropy.complete_remote_package_relative_path(
                rel_path, repo = repo)

            uploader = self.TransceiverServerHandler(self._entropy, [uri],
                myqueue, critical_files = myqueue,
                txc_basedir = remote_dir,
                handlers_data = {'branch': branch }, repo = repo)

            xerrors, xm_fine_uris, xm_broken_uris = uploader.go()
            if xerrors:
                errors = True
            m_fine_uris.update(xm_fine_uris)
            m_broken_uris.update(xm_broken_uris)

        if errors:
            my_broken_uris = [
                (EntropyTransceiver.get_uri_name(x[0]), x[1]) for \
                    x in m_broken_uris]
            reason = my_broken_uris[0][1]
            self._entropy.output(
                "[branch:%s] %s: %s, %s: %s" % (
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
            "[branch:%s] %s: %s" % (
                brown(branch),
                blue(_("upload completed successfully")),
                red(crippled_uri),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )
        return errors, m_fine_uris, m_broken_uris


    def _sync_run_download_queue(self, uri, download_queue, repo = None):

        if repo is None:
            repo = self._entropy.default_repository
        branch = self._settings['repositories']['branch']

        crippled_uri = EntropyTransceiver.get_uri_name(uri)

        queue_map = {}

        for download_path, rel_path, size in download_queue:
            hash_file = download_path + etpConst['packagesmd5fileext']

            rel_dir = os.path.dirname(rel_path)
            obj = queue_map.setdefault(rel_dir, [])
            obj.append(hash_file)
            obj.append(download_path)

        errors = False
        m_fine_uris = set()
        m_broken_uris = set()
        for rel_path, myqueue in queue_map.items():

            remote_dir = self._entropy.complete_remote_package_relative_path(
                rel_path, repo = repo)

            local_basedir = self._entropy.complete_local_package_path(rel_path,
                repo = repo)
            if not os.path.isdir(local_basedir):
                self._entropy._ensure_dir_path(local_basedir)

            downloader = self.TransceiverServerHandler(
                self._entropy, [uri], myqueue,
                critical_files = myqueue,
                txc_basedir = remote_dir, local_basedir = local_basedir,
                handlers_data = {'branch': branch }, download = True,
                repo = repo)

            xerrors, xm_fine_uris, xm_broken_uris = downloader.go()
            if xerrors:
                errors = True
            m_fine_uris.update(xm_fine_uris)
            m_broken_uris.update(xm_broken_uris)

        if errors:
            my_broken_uris = [
                (EntropyTransceiver.get_uri_name(x), y,) \
                    for x, y in m_broken_uris]
            reason = my_broken_uris[0][1]
            self._entropy.output(
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
                level = "error",
                header = darkred(" !!! ")
            )
            return errors, m_fine_uris, m_broken_uris

        self._entropy.output(
            "[repo:%s|%s|%s] %s: %s" % (
                brown(repo),
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

    def _run_package_files_qa_checks(self, packages_list, repo = None):

        if repo is None:
            repo = self._entropy.default_repository

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
                # call wolfman-911
                qa_some_faulty.append(os.path.basename(upload_package))

        if qa_some_faulty:

            for qa_faulty_pkg in qa_some_faulty:
                self._entropy.output(
                    "[repo:%s|branch:%s] %s: %s" % (
                        brown(repo),
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


    def sync_packages(self, ask = True, pretend = False, packages_check = False,
        repo = None):

        if repo is None:
            repo = self._entropy.default_repository

        self._entropy.output(
            "[repo:%s|%s] %s" % (
                repo,
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

        for uri in self._entropy.get_remote_packages_mirrors(repo):

            crippled_uri = EntropyTransceiver.get_uri_name(uri)
            mirror_errors = False

            self._entropy.output(
                "[repo:%s|%s|branch:%s] %s: %s" % (
                    repo,
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
                    remote_packages_data = self.calculate_packages_to_sync(uri,
                        repo)
            except self.socket.error as err:
                self._entropy.output(
                    "[repo:%s|%s|branch:%s] %s: %s, %s %s" % (
                        repo,
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
                    "[repo:%s|%s|branch:%s] %s: %s" % (
                        repo,
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
                remote_packages_data, repo)
            del upload_queue, download_queue, removal_queue, \
                remote_packages_data
            self._show_sync_queues(upload, download, removal, copy_q, metainfo)

            if not len(upload)+len(download)+len(removal)+len(copy_q):

                self._entropy.output(
                    "[repo:%s|%s|branch:%s] %s %s" % (
                        self._entropy.default_repository,
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
                qa_package_files = [x[0] for x in upload if x[0] \
                    not in upload_queue_qa_checked]
                upload_queue_qa_checked |= set(qa_package_files)

                self._run_package_files_qa_checks(qa_package_files,
                    repo = repo)

                if removal:
                    self._sync_run_removal_queue(removal, repo)

                if copy_q:
                    self._sync_run_copy_queue(copy_q, repo)

                if upload:
                    mirrors_tainted = True

                if upload:
                    d_errors, m_fine_uris, \
                        m_broken_uris = self._sync_run_upload_queue(uri,
                            upload, repo)

                    if d_errors:
                        mirror_errors = True

                if download:
                    d_errors, m_fine_uris, \
                        m_broken_uris = self._sync_run_download_queue(uri,
                            download, repo)

                    if d_errors:
                        mirror_errors = True
                if not mirror_errors:
                    successfull_mirrors.add(uri)
                else:
                    mirrors_errors = True

            except KeyboardInterrupt:
                self._entropy.output(
                    "[repo:%s|%s|branch:%s] %s" % (
                        repo,
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
                    "[repo:%s|%s|branch:%s] %s: %s, %s: %s" % (
                        repo,
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
                    "[repo:%s|%s|branch:%s] %s: %s, %s: %s" % (
                        repo,
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
                        "[repo:%s|%s|branch:%s] %s" % (
                            repo,
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
            self._move_files_over_from_upload(repo)

        if packages_check:
            check_data = self._entropy.verify_local_packages([], ask = ask,
                repo = repo)

        return mirrors_tainted, mirrors_errors, successfull_mirrors, \
            broken_mirrors, check_data

    def _move_files_over_from_upload(self, repo = None):

        if repo is None:
            repo = self._entropy.default_repository

        upload_dir = self._entropy._get_local_upload_directory(repo = repo)
        basedir_list = self._entropy._get_basedir_pkg_listing(upload_dir,
            repo = repo)

        for pkg_rel in basedir_list:

            source_pkg = self._entropy.complete_local_upload_package_path(
                pkg_rel, repo = repo)
            dest_pkg = self._entropy.complete_local_package_path(pkg_rel,
                repo = repo)
            dest_pkg_dir = os.path.dirname(dest_pkg)
            self._entropy._ensure_dir_path(dest_pkg_dir)

            source_pkgs = [source_pkg]
            gpg_file = source_pkg + etpConst['etpgpgextension']
            md5_file = source_pkg + etpConst['packagesmd5fileext']
            if os.path.isfile(gpg_file):
                source_pkgs.append(gpg_file)
            if os.path.isfile(md5_file):
                source_pkgs.append(md5_file)

            for pkg_path in source_pkgs:
                dest_pkg_path = os.path.join(dest_pkg_dir,
                    os.path.basename(pkg_path))
                try:
                    os.rename(pkg_path, dest_pkg_path)
                except OSError: # on different hard drives?
                    shutil.move(pkg_path, dest_pkg_path)

            # clear expiration file
            dest_expiration = dest_pkg + etpConst['packagesexpirationfileext']
            if os.path.isfile(dest_expiration):
                os.remove(dest_expiration)

    def _is_package_expired(self, package_rel, repo = None):

        pkg_path = self._entropy.complete_local_package_path(package_rel,
            repo = repo)
        pkg_path += etpConst['packagesexpirationfileext']
        if not os.path.isfile(pkg_path):
            return False

        srv_set = self._settings[Server.SYSTEM_SETTINGS_PLG_ID]['server']
        mtime = os.path.getmtime(pkg_path)
        days = srv_set['packages_expiration_days']
        delta = int(days)*24*3600
        currmtime = time.time()
        file_delta = currmtime - mtime

        if file_delta > delta:
            return True
        return False

    def _create_expiration_file(self, package_rel, repo = None, gentle = False):

        pkg_path = self._entropy.complete_local_package_path(package_rel,
            repo = repo)
        pkg_path += etpConst['packagesexpirationfileext']
        if gentle and os.path.isfile(pkg_path):
            return
        f_exp = open(pkg_path, "w")
        f_exp.flush()
        f_exp.close()

    def _collect_expiring_packages(self, branch, repo = None):

        dbconn = self._entropy.open_server_repository(just_reading = True,
            repo = repo)

        database_bins = set(dbconn.listAllDownloads(do_sort = False,
            full_path = True))

        repo_basedir = self._entropy._get_local_repository_base_directory(
            repo = repo)

        repo_bins = self._entropy._get_basedir_pkg_listing(repo_basedir,
            repo = repo, branch = branch)

        # convert to set, so that we can do fast thingszzsd
        repo_bins = set(repo_bins)
        repo_bins -= database_bins
        return repo_bins


    def tidy_mirrors(self, ask = True, pretend = False, repo = None):

        if repo is None:
            repo = self._entropy.default_repository

        self._entropy.output(
            "[repo:%s|%s|branch:%s] %s" % (
                brown(repo),
                red(_("tidy")),
                blue(self._settings['repositories']['branch']),
                blue(_("collecting expired packages")),
            ),
            importance = 1,
            level = "info",
            header = red(" @@ ")
        )

        branch_data = {}
        errors = False
        branch_data['errors'] = False
        branch = self._settings['repositories']['branch']

        self._entropy.output(
            "[branch:%s] %s" % (
                brown(branch),
                blue(_("collecting expired packages in the selected branches")),
            ),
            importance = 1,
            level = "info",
            header = blue(" @@ ")
        )

        # collect removed packages
        expiring_packages = self._collect_expiring_packages(branch, repo)
        if expiring_packages:

            # filter expired packages used by other branches
            # this is done for the sake of consistency
            # --- read packages.db.pkglist, make sure your repository
            # has been ported to latest Entropy

            branch_pkglist_data = self._read_remote_file_in_branches(
                etpConst['etpdatabasepkglist'], repo = repo,
                excluded_branches = [branch])
            # format data
            for key, val in branch_pkglist_data.items():
                branch_pkglist_data[key] = val.split("\n")

            for other_branch in branch_pkglist_data:
                branch_pkglist = set(branch_pkglist_data[other_branch])
                expiring_packages -= branch_pkglist

        removal = []
        for package_rel in expiring_packages:
            expired = self._is_package_expired(package_rel, repo)
            if expired:
                removal.append(package_rel)
            else:
                self._create_expiration_file(package_rel, repo, gentle = True)

        # fill returning data
        branch_data['removal'] = removal[:]

        if not removal:
            self._entropy.output(
                "[branch:%s] %s" % (
                    brown(branch),
                    blue(_("nothing to remove on this branch")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            return errors, branch_data
        else:
            self._entropy.output(
                "[branch:%s] %s:" % (
                    brown(branch),
                    blue(_("these are the expired packages")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            for package in removal:
                self._entropy.output(
                    "[branch:%s] %s: %s" % (
                            brown(branch),
                            blue(_("remove")),
                            darkgreen(package),
                        ),
                    importance = 1,
                    level = "info",
                    header = brown("    # ")
                )

        if pretend:
            return errors, branch_data

        if ask:
            rc_question = self._entropy.ask_question(
                _("Would you like to continue ?"))
            if rc_question == _("No"):
                return errors, branch_data

        # split queue by remote directories to work on
        removal_map = {}
        for package_rel in removal:
            rel_path = self._entropy.complete_remote_package_relative_path(
                package_rel, repo = repo)
            rel_dir = os.path.dirname(rel_path)
            obj = removal_map.setdefault(rel_dir, [])
            base_pkg = os.path.basename(package_rel)
            obj.append(base_pkg)
            obj.append(base_pkg+etpConst['packagesmd5fileext'])

        for uri in self._entropy.get_remote_packages_mirrors(repo):

            ##
            # remove remotely
            ##

            errors = False
            m_fine_uris = set()
            m_broken_uris = set()
            for remote_dir, myqueue in removal_map.items():

                self._entropy.output(
                    "[branch:%s] %s..." % (
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
                    repo = repo
                )
                xerrors, xm_fine_uris, xm_broken_uris = destroyer.go()
                if xerrors:
                    errors = True
                m_fine_uris.update(xm_fine_uris)
                m_broken_uris.update(xm_broken_uris)

            if errors:
                my_broken_uris = [
                    (EntropyTransceiver.get_uri_name(x[0]), x[1]) \
                        for x in m_broken_uris]

                reason = my_broken_uris[0][1]
                crippled_uri = EntropyTransceiver.get_uri_name(uri)
                self._entropy.output(
                    "[branch:%s] %s: %s, %s: %s" % (
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
                branch_data['errors'] = True
                errors = True

            self._entropy.output(
                "[branch:%s] %s..." % (
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

            branch_data['removed'] = set()
            for package_rel in removal:

                package_path = self._entropy.complete_local_package_path(
                    package_rel, repo = repo)

                package_path_hash = package_path + \
                    etpConst['packagesmd5fileext']
                package_path_expired = package_path + \
                    etpConst['packagesexpirationfileext']

                my_rm_list = (package_path_hash, package_path,
                    package_path_expired)
                for myfile in my_rm_list:
                    if os.path.isfile(myfile):
                        self._entropy.output(
                            "[branch:%s] %s: %s" % (
                                brown(branch),
                                blue(_("removing")),
                                darkgreen(myfile),
                            ),
                            importance = 1,
                            level = "info",
                            header = brown(" @@ ")
                        )
                        os.remove(myfile)
                        branch_data['removed'].add(myfile)

        return errors, branch_data
