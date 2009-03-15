# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

from __future__ import with_statement
import os
import shutil
import time
from entropy.exceptions import *
from entropy.output import TextInterface, purple, green, red, darkgreen, bold, brown, blue, darkred, darkblue
from entropy.const import etpConst, etpSys

class Server:

    import socket
    import entropy.dump as dumpTools
    import entropy.tools as entropyTools
    def __init__(self,  ServerInstance, repo = None):

        from entropy.server.interfaces.main import Server as MainServer
        if not isinstance(ServerInstance,MainServer):
            mytxt = _("A valid entropy.server.interfaces.main.Server interface based instance is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        self.Entropy = ServerInstance
        from entropy.transceivers import FtpServerHandler
        self.FtpServerHandler = FtpServerHandler
        from entropy.cache import EntropyCacher
        self.Cacher = EntropyCacher()
        self.FtpInterface = self.Entropy.FtpInterface
        self.rssFeed = self.Entropy.rssFeed

        mytxt = blue("%s:") % (_("Entropy Server Mirrors Interface loaded"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )
        mytxt = _("mirror")
        for mirror in self.Entropy.get_remote_mirrors(repo):
            mirror = self.entropyTools.hide_ftp_password(mirror)
            self.Entropy.updateProgress(
                blue("%s: %s") % (mytxt,darkgreen(mirror),),
                importance = 0,
                type = "info",
                header = brown("   # ")
            )


    def lock_mirrors(self, lock = True, mirrors = [], repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        if not mirrors:
            mirrors = self.Entropy.get_remote_mirrors(repo)

        issues = False
        for uri in mirrors:

            crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)

            lock_text = _("unlocking")
            if lock: lock_text = _("locking")
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

            try:
                ftp = self.FtpInterface(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.print_traceback()
                return True # issues
            my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
            ftp.set_cwd(my_path, dodir = True)

            if lock and ftp.is_file_available(etpConst['etpdatabaselockfile']):
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
                ftp.close()
                continue
            elif not lock and not ftp.is_file_available(etpConst['etpdatabaselockfile']):
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
                ftp.close()
                continue

            if lock:
                rc = self.do_mirror_lock(uri, ftp, repo = repo)
            else:
                rc = self.do_mirror_unlock(uri, ftp, repo = repo)
            ftp.close()
            if not rc: issues = True

        if not issues:
            database_taint_file = self.Entropy.get_local_database_taint_file(repo)
            if os.path.isfile(database_taint_file):
                os.remove(database_taint_file)

        return issues

    # this functions makes entropy clients to not download anything from the chosen
    # mirrors. it is used to avoid clients to download databases while we're uploading
    # a new one.
    def lock_mirrors_for_download(self, lock = True, mirrors = [], repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        if not mirrors:
            mirrors = self.Entropy.get_remote_mirrors(repo)

        issues = False
        for uri in mirrors:

            crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)

            lock_text = _("unlocking")
            if lock: lock_text = _("locking")
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

            try:
                ftp = self.FtpInterface(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.print_traceback()
                return True # issues
            my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
            ftp.set_cwd(my_path, dodir = True)

            if lock and ftp.is_file_available(etpConst['etpdatabasedownloadlockfile']):
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
                ftp.close()
                continue
            elif not lock and not ftp.is_file_available(etpConst['etpdatabasedownloadlockfile']):
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
                ftp.close()
                continue

            if lock:
                rc = self.do_mirror_lock(uri, ftp, dblock = False, repo = repo)
            else:
                rc = self.do_mirror_unlock(uri, ftp, dblock = False, repo = repo)
            ftp.close()
            if not rc: issues = True

        return issues

    def do_mirror_lock(self, uri, ftp_connection = None, dblock = True, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
        if not ftp_connection:
            try:
                ftp_connection = self.FtpInterface(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.print_traceback()
                return False # issues
            ftp_connection.set_cwd(my_path, dodir = True)
        else:
            mycwd = ftp_connection.get_cwd()
            if mycwd != my_path:
                ftp_connection.set_basedir()
                ftp_connection.set_cwd(my_path, dodir = True)

        crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
        lock_string = ''
        if dblock:
            self.create_local_database_lockfile(repo)
            lock_file = self.get_database_lockfile(repo)
        else:
            lock_string = _('for download') # locking/unlocking mirror1 for download
            self.create_local_database_download_lockfile(repo)
            lock_file = self.get_database_download_lockfile(repo)

        rc = ftp_connection.upload_file(lock_file, ascii = True)
        if rc:
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
                            rc,
                            blue(_("mirror not locked")),
                            blue(lock_string),
                    ),
                importance = 1,
                type = "error",
                header = darkred(" * ")
            )
            self.remove_local_database_lockfile(repo)

        return rc


    def do_mirror_unlock(self, uri, ftp_connection, dblock = True, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
        if not ftp_connection:
            try:
                ftp_connection = self.FtpInterface(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.print_traceback()
                return False # issues
            ftp_connection.set_cwd(my_path)
        else:
            mycwd = ftp_connection.get_cwd()
            if mycwd != my_path:
                ftp_connection.set_basedir()
                ftp_connection.set_cwd(my_path)

        crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)

        if dblock:
            dbfile = etpConst['etpdatabaselockfile']
        else:
            dbfile = etpConst['etpdatabasedownloadlockfile']
        rc = ftp_connection.delete_file(dbfile)
        if rc:
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
                            rc,
                            blue(_("mirror not unlocked")),
                    ),
                importance = 1,
                type = "error",
                header = darkred(" * ")
            )

        return rc

    def get_database_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        return os.path.join(self.Entropy.get_local_database_dir(repo),etpConst['etpdatabaselockfile'])

    def get_database_download_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        return os.path.join(self.Entropy.get_local_database_dir(repo),etpConst['etpdatabasedownloadlockfile'])

    def create_local_database_download_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_download_lockfile(repo)
        f = open(lock_file,"w")
        f.write("download locked")
        f.flush()
        f.close()

    def create_local_database_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_lockfile(repo)
        f = open(lock_file,"w")
        f.write("database locked")
        f.flush()
        f.close()

    def remove_local_database_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_lockfile(repo)
        if os.path.isfile(lock_file):
            os.remove(lock_file)

    def remove_local_database_download_lockfile(self, repo = None):
        if repo == None:
            repo = self.Entropy.default_repository
        lock_file = self.get_database_download_lockfile(repo)
        if os.path.isfile(lock_file):
            os.remove(lock_file)

    def download_package(self, uri, pkg_relative_path, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)

        tries = 0
        while tries < 5:
            tries += 1

            pkg_to_join_path = '/'.join(pkg_relative_path.split('/')[2:])
            pkg_to_join_dirpath = os.path.dirname(pkg_to_join_path)
            pkgfile = os.path.basename(pkg_relative_path)

            self.Entropy.updateProgress(
                "[repo:%s|%s|#%s] %s: %s" % (
                    brown(repo),
                    darkgreen(crippled_uri),
                    brown(tries),
                    blue(_("connecting to download package")), # connecting to download package xyz
                    darkgreen(pkg_to_join_path),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * "),
                back = True
            )

            try:
                ftp = self.FtpInterface(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.print_traceback()
                return False # issues
            dirpath = os.path.join(self.Entropy.get_remote_packages_relative_path(repo),pkg_to_join_dirpath)
            ftp.set_cwd(dirpath, dodir = True)

            self.Entropy.updateProgress(
                "[repo:%s|%s|#%s] %s: %s" % (
                    brown(repo),
                    darkgreen(crippled_uri),
                    brown(tries),
                    blue(_("downloading package")),
                    darkgreen(pkg_to_join_path),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )

            download_path = os.path.join(self.Entropy.get_local_packages_directory(repo),pkg_to_join_dirpath)
            if (not os.path.isdir(download_path)) and (not os.access(download_path,os.R_OK)):
                os.makedirs(download_path)
            rc = ftp.download_file(pkgfile,download_path)
            if not rc:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|#%s] %s: %s %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        brown(tries),
                        blue(_("package")),
                        darkgreen(pkg_to_join_path),
                        blue(_("does not exist")),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                ftp.close()
                return rc

            dbconn = self.Entropy.open_server_repository(read_only = True, no_upload = True, repo = repo)
            idpackage = dbconn.getIDPackageFromDownload(pkg_relative_path)
            if idpackage == -1:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|#%s] %s: %s %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        brown(tries),
                        blue(_("package")),
                        darkgreen(pkgfile),
                        blue(_("is not listed in the current repository database!!")),
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                ftp.close()
                return False

            storedmd5 = dbconn.retrieveDigest(idpackage)
            self.Entropy.updateProgress(
                "[repo:%s|%s|#%s] %s: %s" % (
                    brown(repo),
                    darkgreen(crippled_uri),
                    brown(tries),
                    blue(_("verifying checksum of package")),
                    darkgreen(pkgfile),
                ),
                importance = 1,
                type = "info",
                header = darkgreen(" * "),
                back = True
            )

            pkg_path = os.path.join(download_path,pkgfile)
            md5check = self.entropyTools.compare_md5(pkg_path,storedmd5)
            if md5check:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|#%s] %s: %s %s" % (
                        brown(repo),
                        darkgreen(crippled_uri),
                        brown(tries),
                        blue(_("package")),
                        darkgreen(pkgfile),
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
                        brown(tries),
                        blue(_("package")),
                        darkgreen(pkgfile),
                        blue(_("checksum does not match. re-downloading...")),
                    ),
                    importance = 1,
                    type = "warning",
                    header = darkred(" * ")
                )
                if os.path.isfile(pkg_path):
                    os.remove(pkg_path)

            continue

        # if we get here it means the files hasn't been downloaded properly
        self.Entropy.updateProgress(
            "[repo:%s|%s|#%s] %s: %s %s" % (
                brown(repo),
                darkgreen(crippled_uri),
                brown(tries),
                blue(_("package")),
                darkgreen(pkgfile),
                blue(_("seems broken. Consider to re-package it. Giving up!")),
            ),
            importance = 1,
            type = "error",
            header = darkred(" !!! ")
        )
        return False


    def get_remote_databases_status(self, repo = None, mirrors = []):

        if repo == None:
            repo = self.Entropy.default_repository

        if not mirrors:
            mirrors = self.Entropy.get_remote_mirrors(repo)

        data = []
        for uri in mirrors:

            # let it raise an exception if connection is impossible
            ftp = self.FtpInterface(uri, self.Entropy)
            try:
                my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
                ftp.set_cwd(my_path, dodir = True)
            except ftp.ftplib.error_perm:
                crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
                self.Entropy.updateProgress(
                    "[repo:%s|%s] %s !" % (
                            brown(repo),
                            darkgreen(crippled_uri),
                            blue(_("mirror doesn't have a valid directory structure")),
                    ),
                    importance = 1,
                    type = "warning",
                    header = darkred(" !!! ")
                )
                ftp.close()
                continue
            cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
            if cmethod == None:
                raise InvalidDataType("InvalidDataType: %s." % (
                        _("Wrong database compression method passed"),
                    )
                )
            compressedfile = etpConst[cmethod[2]]

            revision = 0
            rc1 = ftp.is_file_available(compressedfile)
            revfilename = os.path.basename(self.Entropy.get_local_database_revision_file(repo))
            rc2 = ftp.is_file_available(revfilename)
            if rc1 and rc2:
                revision_localtmppath = os.path.join(etpConst['packagestmpdir'],revfilename)
                dlcount = 5
                while dlcount:
                    dled = ftp.download_file(revfilename,etpConst['packagestmpdir'],True)
                    if dled: break
                    dlcount -= 1

                crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
                try:
                    f = open(revision_localtmppath,"r")
                    revision = int(f.readline().strip())
                except IOError:
                    if dlcount == 0:
                        self.Entropy.updateProgress(
                            "[repo:%s|%s] %s: %s" % (
                                    brown(repo),
                                    darkgreen(crippled_uri),
                                    blue(_("unable to download remote mirror repository revision file, defaulting to 0")),
                                    bold(revision),
                            ),
                            importance = 1,
                            type = "error",
                            header = darkred(" !!! ")
                        )
                    else:
                        self.Entropy.updateProgress(
                            "[repo:%s|%s] %s: %s" % (
                                    brown(repo),
                                    darkgreen(crippled_uri),
                                    blue(_("mirror doesn't have a valid database revision file")),
                                    bold(revision),
                            ),
                            importance = 1,
                            type = "error",
                            header = darkred(" !!! ")
                        )
                    revision = 0
                except ValueError:
                    self.Entropy.updateProgress(
                        "[repo:%s|%s] %s: %s" % (
                                brown(repo),
                                darkgreen(crippled_uri),
                                blue(_("mirror doesn't have a valid database revision file")),
                                bold(revision),
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    revision = 0
                f.close()
                if os.path.isfile(revision_localtmppath):
                    os.remove(revision_localtmppath)

            info = [uri,revision]
            data.append(info)
            ftp.close()

        return data

    def is_local_database_locked(self, repo = None):
        x = repo
        if x == None:
            x = self.Entropy.default_repository
        lock_file = self.get_database_lockfile(x)
        return os.path.isfile(lock_file)

    def get_mirrors_lock(self, repo = None):

        dbstatus = []
        for uri in self.Entropy.get_remote_mirrors(repo):
            data = [uri,False,False]
            ftp = self.FtpInterface(uri, self.Entropy)
            try:
                my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
                ftp.set_cwd(my_path)
            except ftp.ftplib.error_perm:
                ftp.close()
                continue
            if ftp.is_file_available(etpConst['etpdatabaselockfile']):
                # upload locked
                data[1] = True
            if ftp.is_file_available(etpConst['etpdatabasedownloadlockfile']):
                # download locked
                data[2] = True
            ftp.close()
            dbstatus.append(data)
        return dbstatus

    def download_notice_board(self, repo = None):

        if repo == None: repo = self.Entropy.default_repository
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
            crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
            downloader = self.FtpServerHandler(
                self.FtpInterface, self.Entropy, [uri],
                [rss_path], download = True,
                local_basedir = mytmpdir, critical_files = [rss_path], repo = repo
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
            shutil.move(os.path.join(mytmpdir,os.path.basename(rss_path)),rss_path)

        return downloaded

    def upload_notice_board(self, repo = None):

        if repo == None: repo = self.Entropy.default_repository
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

        uploader = self.FtpServerHandler(
            self.FtpInterface,
            self.Entropy,
            mirrors,
            [rss_path],
            critical_files = [rss_path],
            repo = repo
        )
        errors, m_fine_uris, m_broken_uris = uploader.go()
        if errors:
            m_broken_uris = sorted(list(m_broken_uris))
            m_broken_uris = [self.entropyTools.extract_ftp_host_from_uri(x) for x in m_broken_uris]
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

        rss_title = "%s Notice Board" % (etpConst['systemname'],)
        rss_description = "Inform about important distribution activities."
        rss_path = self.Entropy.get_local_database_notice_board_file(repo)
        if not link: link = etpConst['rss-website-url']

        self.download_notice_board(repo)
        Rss = self.rssFeed(rss_path, rss_title, rss_description, maxentries = 20)
        Rss.addItem(title, link, description = notice_text)
        Rss.writeChanges()
        status = self.upload_notice_board(repo)
        return status

    def read_notice_board(self, do_download = True, repo = None):

        rss_path = self.Entropy.get_local_database_notice_board_file(repo)
        if do_download: self.download_notice_board(repo)
        if not (os.path.isfile(rss_path) and os.access(rss_path,os.R_OK)):
            return None
        Rss = self.rssFeed(rss_path, '', '')
        return Rss.getEntries()

    def remove_from_notice_board(self, identifier, repo = None):

        rss_path = self.Entropy.get_local_database_notice_board_file(repo)
        rss_title = "%s Notice Board" % (etpConst['systemname'],)
        rss_description = "Inform about important distribution activities."
        if not (os.path.isfile(rss_path) and os.access(rss_path,os.R_OK)):
            return 0
        Rss = self.rssFeed(rss_path, rss_title, rss_description)
        data = Rss.removeEntry(identifier)
        Rss.writeChanges()
        return data

    def update_rss_feed(self, repo = None):

        #db_dir = self.Entropy.get_local_database_dir(repo)
        rss_path = self.Entropy.get_local_database_rss_file(repo)
        rss_light_path = self.Entropy.get_local_database_rsslight_file(repo)
        rss_dump_name = etpConst['rss-dump-name']
        db_revision_path = self.Entropy.get_local_database_revision_file(repo)

        rss_title = "%s Online Repository Status" % (etpConst['systemname'],)
        rss_description = "Keep you updated on what's going on in the %s Repository." % (etpConst['systemname'],)
        Rss = self.rssFeed(rss_path, rss_title, rss_description, maxentries = etpConst['rss-max-entries'])
        # load dump
        db_actions = self.Cacher.pop(rss_dump_name)
        if db_actions:
            try:
                f = open(db_revision_path)
                revision = f.readline().strip()
                f.close()
            except (IOError, OSError):
                revision = "N/A"
            commitmessage = ''
            if self.Entropy.rssMessages['commitmessage']:
                commitmessage = ' :: '+self.Entropy.rssMessages['commitmessage']
            title = ": "+etpConst['systemname']+" "+etpConst['product'][0].upper()+etpConst['product'][1:]+" "+etpConst['branch']+" :: Revision: "+revision+commitmessage
            link = etpConst['rss-base-url']
            # create description
            added_items = db_actions.get("added")
            if added_items:
                for atom in added_items:
                    mylink = link+"?search="+atom.split("~")[0]+"&arch="+etpConst['currentarch']+"&product="+etpConst['product']
                    description = atom+": "+added_items[atom]['description']
                    Rss.addItem(title = "Added/Updated"+title, link = mylink, description = description)
            removed_items = db_actions.get("removed")
            if removed_items:
                for atom in removed_items:
                    description = atom+": "+removed_items[atom]['description']
                    Rss.addItem(title = "Removed"+title, link = link, description = description)
            light_items = db_actions.get('light')
            if light_items:
                rssLight = self.rssFeed(rss_light_path, rss_title, rss_description, maxentries = etpConst['rss-light-max-entries'])
                for atom in light_items:
                    mylink = link+"?search="+atom.split("~")[0]+"&arch="+etpConst['currentarch']+"&product="+etpConst['product']
                    description = light_items[atom]['description']
                    rssLight.addItem(title = "["+revision+"] "+atom, link = mylink, description = description)
                rssLight.writeChanges()

        Rss.writeChanges()
        self.Entropy.rssMessages.clear()
        self.dumpTools.removeobj(rss_dump_name)


    # f_out is a file instance
    def dump_database_to_file(self, db_path, destination_path, opener, repo = None):
        f_out = opener(destination_path, "wb")
        dbconn = self.Entropy.open_server_repository(db_path, just_reading = True, repo = repo)
        dbconn.doDatabaseExport(f_out)
        self.Entropy.close_server_database(dbconn)
        f_out.close()

    def create_file_checksum(self, file_path, checksum_path):
        mydigest = self.entropyTools.md5sum(file_path)
        f = open(checksum_path,"w")
        mystring = "%s  %s\n" % (mydigest,os.path.basename(file_path),)
        f.write(mystring)
        f.flush()
        f.close()

    def compress_file(self, file_path, destination_path, opener):
        f_out = opener(destination_path, "wb")
        f_in = open(file_path,"rb")
        data = f_in.read(8192)
        while data:
            f_out.write(data)
            data = f_in.read(8192)
        f_in.close()
        try:
            f_out.flush()
        except:
            pass
        f_out.close()

    def get_files_to_sync(self, cmethod, download = False, repo = None):

        critical = []
        extra_text_files = []
        data = {}
        data['database_revision_file'] = self.Entropy.get_local_database_revision_file(repo)
        extra_text_files.append(data['database_revision_file'])
        critical.append(data['database_revision_file'])

        database_package_mask_file = self.Entropy.get_local_database_mask_file(repo)
        extra_text_files.append(database_package_mask_file)
        if os.path.isfile(database_package_mask_file) or download:
            data['database_package_mask_file'] = database_package_mask_file
            if not download:
                critical.append(data['database_package_mask_file'])

        database_package_system_mask_file = self.Entropy.get_local_database_system_mask_file(repo)
        extra_text_files.append(database_package_system_mask_file)
        if os.path.isfile(database_package_system_mask_file) or download:
            data['database_package_system_mask_file'] = database_package_system_mask_file
            if not download:
                critical.append(data['database_package_system_mask_file'])

        database_package_confl_tagged_file = self.Entropy.get_local_database_confl_tagged_file(repo)
        extra_text_files.append(database_package_confl_tagged_file)
        if os.path.isfile(database_package_confl_tagged_file) or download:
            data['database_package_confl_tagged_file'] = database_package_confl_tagged_file
            if not download:
                critical.append(data['database_package_confl_tagged_file'])

        database_license_whitelist_file = self.Entropy.get_local_database_licensewhitelist_file(repo)
        extra_text_files.append(database_license_whitelist_file)
        if os.path.isfile(database_license_whitelist_file) or download:
            data['database_license_whitelist_file'] = database_license_whitelist_file
            if not download:
                critical.append(data['database_license_whitelist_file'])

        database_rss_file = self.Entropy.get_local_database_rss_file(repo)
        if os.path.isfile(database_rss_file) or download:
            data['database_rss_file'] = database_rss_file
            if not download:
                critical.append(data['database_rss_file'])
        database_rss_light_file = self.Entropy.get_local_database_rsslight_file(repo)
        extra_text_files.append(database_rss_light_file)
        if os.path.isfile(database_rss_light_file) or download:
            data['database_rss_light_file'] = database_rss_light_file
            if not download:
                critical.append(data['database_rss_light_file'])

        # EAPI 2,3
        if not download: # we don't need to get the dump
            data['metafiles_path'] = self.Entropy.get_local_database_compressed_metafiles_file(repo)
            critical.append(data['metafiles_path'])
            data['dump_path'] = os.path.join(self.Entropy.get_local_database_dir(repo),etpConst[cmethod[3]])
            critical.append(data['dump_path'])
            data['dump_path_digest'] = os.path.join(self.Entropy.get_local_database_dir(repo),etpConst[cmethod[4]])
            critical.append(data['dump_path_digest'])
            data['database_path'] = self.Entropy.get_local_database_file(repo)
            critical.append(data['database_path'])

        # EAPI 1
        data['compressed_database_path'] = os.path.join(self.Entropy.get_local_database_dir(repo),etpConst[cmethod[2]])
        critical.append(data['compressed_database_path'])
        data['compressed_database_path_digest'] = os.path.join(
            self.Entropy.get_local_database_dir(repo),etpConst['etpdatabasehashfile']
        )
        critical.append(data['compressed_database_path_digest'])

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
            (etpConst['spm']['global_make_conf'],"global_make_conf"),
            (etpConst['spm']['global_package_keywords'],"global_package_keywords"),
            (etpConst['spm']['global_package_use'],"global_package_use"),
            (etpConst['spm']['global_package_mask'],"global_package_mask"),
            (etpConst['spm']['global_package_unmask'],"global_package_unmask"),
        ]
        for myfile,myname in spm_files:
            if os.path.isfile(myfile) and os.access(myfile,os.R_OK):
                data[myname] = myfile
            extra_text_files.append(myfile)

        make_profile = etpConst['spm']['global_make_profile']
        mytmpdir = os.path.dirname(self.Entropy.entropyTools.get_random_temp_file())
        mytmpfile = os.path.join(mytmpdir,etpConst['spm']['global_make_profile_link_name'])
        extra_text_files.append(mytmpfile)
        if os.path.islink(make_profile):
            mylink = os.readlink(make_profile)
            f = open(mytmpfile,"w")
            f.write(mylink)
            f.flush()
            f.close()
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
        sets_data = self.Entropy.package_set_list(matchRepo = repo)
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
            "%s: %s" % (_("database path"),blue(database_path),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

    def _show_eapi2_upload_messages(self, crippled_uri, database_path, upload_data, cmethod, repo):

        if repo == None:
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
            "%s: %s" % (_("database path"),blue(database_path),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("dump"),blue(upload_data['dump_path']),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("dump checksum"),blue(upload_data['dump_path_digest']),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("opener"),blue(cmethod[0]),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

    def _show_eapi1_upload_messages(self, crippled_uri, database_path, upload_data, cmethod, repo):

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
            "%s: %s" % (_("database path"),blue(database_path),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("compressed database path"),blue(upload_data['compressed_database_path']),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("compressed checksum"),blue(upload_data['compressed_database_path_digest']),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            "%s: %s" % (_("opener"),blue(cmethod[0]),),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

    def _create_metafiles_file(self, compressed_dest_path, file_list, repo):
        found_file_list = [x for x in file_list if os.path.isfile(x) and \
            os.access(x,os.F_OK) and os.access(x,os.R_OK)]
        not_found_file_list = ["%s\n" % (os.path.basename(x),) for x in file_list if x not in found_file_list]
        metafile_not_found_file = self.Entropy.get_local_database_metafiles_not_found_file(repo)
        f = open(metafile_not_found_file,"w")
        f.writelines(not_found_file_list)
        f.flush()
        f.close()
        found_file_list.append(metafile_not_found_file)
        if os.path.isfile(compressed_dest_path):
            os.remove(compressed_dest_path)
        self.entropyTools.compress_files(compressed_dest_path, found_file_list)

    def create_mirror_directories(self, ftp_connection, path_to_create):
        bdir = ""
        for mydir in path_to_create.split("/"):
            bdir += "/"+mydir
            if not ftp_connection.is_file_available(bdir):
                try:
                    ftp_connection.mkdir(bdir)
                except Exception, e:
                    error = unicode(e)
                    if (error.find("550") == -1) and (error.find("File exist") == -1):
                        mytxt = "%s %s, %s: %s" % (
                            _("cannot create mirror directory"),
                            bdir,
                            _("error"),
                            e,
                        )
                        raise OnlineMirrorError("OnlineMirrorError:  %s" % (mytxt,))

    def mirror_lock_check(self, uri, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        gave_up = False
        crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
        try:
            ftp = self.FtpInterface(uri, self.Entropy)
        except ConnectionError:
            self.entropyTools.print_traceback()
            return True # gave up
        my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo),etpConst['branch'])
        ftp.set_cwd(my_path, dodir = True)

        lock_file = self.get_database_lockfile(repo)
        if not os.path.isfile(lock_file) and ftp.is_file_available(os.path.basename(lock_file)):
            self.Entropy.updateProgress(
                red("[repo:%s|%s|%s] %s, %s" % (
                    repo,
                    crippled_uri,
                    _("locking"),
                    _("mirror already locked"),
                    _("waiting up to 2 minutes before giving up"),
                )
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
                if not ftp.is_file_available(os.path.basename(lock_file)):
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

        ftp.close()
        return gave_up

    def shrink_database_and_close(self, repo = None):
        dbconn = self.Entropy.open_server_repository(read_only = False, no_upload = True, repo = repo, indexing = False)
        dbconn.dropAllIndexes()
        dbconn.vacuum()
        dbconn.vacuum()
        dbconn.commitChanges()
        self.Entropy.close_server_database(dbconn)

    def sync_database_treeupdates(self, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository
        dbconn = self.Entropy.open_server_repository(read_only = False, no_upload = True, repo = repo)
        # grab treeupdates from other databases and inject
        server_repos = etpConst['server_repositories'].keys()
        all_actions = set()
        for myrepo in server_repos:

            # avoid __default__
            if myrepo == etpConst['clientserverrepoid']:
                continue

            mydbc = self.Entropy.open_server_repository(just_reading = True, repo = myrepo)
            actions = mydbc.listAllTreeUpdatesActions(no_ids_repos = True)
            for data in actions:
                all_actions.add(data)
            if not actions:
                continue
        backed_up_entries = dbconn.listAllTreeUpdatesActions()
        try:
            # clear first
            dbconn.removeTreeUpdatesActions(repo)
            dbconn.insertTreeUpdatesActions(all_actions,repo)
        except Exception, e:
            self.entropyTools.print_traceback()
            mytxt = "%s, %s: %s. %s" % (
                _("Troubles with treeupdates"),
                _("error"),
                e,
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

    def upload_database(self, uris, lock_check = False, pretend = False, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        # doing some tests
        import gzip
        myt = type(gzip)
        del myt
        import bz2
        myt = type(bz2)
        del myt

        if etpConst['rss-feed']:
            self.update_rss_feed(repo = repo)

        upload_errors = False
        broken_uris = set()
        fine_uris = set()

        for uri in uris:

            cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
            if cmethod == None:
                raise InvalidDataType("InvalidDataType: %s." % (
                        _("wrong database compression method passed"),
                    )
                )

            crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
            database_path = self.Entropy.get_local_database_file(repo)
            upload_data, critical, text_files = self.get_files_to_sync(cmethod, repo = repo)

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
            backup_dbpath = old_dbpath+".up_backup"
            copy_back = False
            if not pretend:
                try:
                    if os.path.isfile(backup_dbpath):
                        os.remove(backup_dbpath)
                    shutil.copy2(old_dbpath,backup_dbpath)
                    copy_back = True
                except:
                    pass

            self.shrink_database_and_close(repo)

            # EAPI 3
            self._create_metafiles_file(upload_data['metafiles_path'], text_files, repo)
            self._show_eapi3_upload_messages(crippled_uri, database_path, repo)

            # EAPI 2
            self._show_eapi2_upload_messages(crippled_uri, database_path, upload_data, cmethod, repo)
            # create compressed dump + checksum
            self.dump_database_to_file(database_path, upload_data['dump_path'], eval(cmethod[0]), repo = repo)
            self.create_file_checksum(upload_data['dump_path'], upload_data['dump_path_digest'])

            # EAPI 1
            self._show_eapi1_upload_messages(crippled_uri, database_path, upload_data, cmethod, repo)
            # compress the database
            self.compress_file(database_path, upload_data['compressed_database_path'], eval(cmethod[0]))
            self.create_file_checksum(database_path, upload_data['compressed_database_path_digest'])

            if not pretend:
                # upload
                uploader = self.FtpServerHandler(
                    self.FtpInterface,
                    self.Entropy,
                    [uri],
                    [upload_data[x] for x in upload_data],
                    critical_files = critical,
                    repo = repo
                )
                errors, m_fine_uris, m_broken_uris = uploader.go()
                if errors:
                    #my_fine_uris = sorted([self.entropyTools.extract_ftp_host_from_uri(x) for x in m_fine_uris])
                    my_broken_uris = sorted([(self.entropyTools.extract_ftp_host_from_uri(x[0]),x[1]) for x in m_broken_uris])
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|%s] %s" % (
                            repo,
                            crippled_uri,
                            _("errors"),
                            _("failed to upload to mirror, not unlocking and continuing"),
                        ),
                        importance = 0,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    # get reason
                    reason = my_broken_uris[0][1]
                    self.Entropy.updateProgress(
                        blue("%s: %s" % (_("reason"),reason,)),
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
                    shutil.copy2(old_dbpath,further_backup_dbpath)
                    shutil.move(backup_dbpath,old_dbpath)

            # unlock
            self.lock_mirrors_for_download(False,[uri], repo = repo)
            fine_uris |= m_fine_uris

        if not fine_uris:
            upload_errors = True
        return upload_errors, broken_uris, fine_uris


    def download_database(self, uris, lock_check = False, pretend = False, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        # doing some tests
        import gzip
        myt = type(gzip)
        del myt
        import bz2
        myt = type(bz2)
        del myt

        download_errors = False
        broken_uris = set()
        fine_uris = set()

        for uri in uris:

            cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
            if cmethod == None:
                raise InvalidDataType("InvalidDataType: %s." % (
                        _("wrong database compression method passed"),
                    )
                )

            crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
            database_path = self.Entropy.get_local_database_file(repo)
            database_dir_path = os.path.dirname(self.Entropy.get_local_database_file(repo))
            download_data, critical, text_files = self.get_files_to_sync(cmethod, download = True, repo = repo)
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
                    "%s: %s" % (blue(_("download path")),brown(unicode(download_data[myfile])),),
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
            self.lock_mirrors(True,[uri], repo = repo)

            if not pretend:
                # download
                downloader = self.FtpServerHandler(
                    self.FtpInterface, self.Entropy, [uri],
                    [download_data[x] for x in download_data], download = True,
                    local_basedir = mytmpdir, critical_files = critical, repo = repo
                )
                errors, m_fine_uris, m_broken_uris = downloader.go()
                if errors:
                    #my_fine_uris = sorted([self.entropyTools.extract_ftp_host_from_uri(x) for x in m_fine_uris])
                    my_broken_uris = sorted([(self.entropyTools.extract_ftp_host_from_uri(x[0]),x[1]) for x in m_broken_uris])
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
                        blue("%s: %s" % (_("reason"),reason,)),
                        importance = 0,
                        type = "error",
                        header = blue("    # ")
                    )
                    download_errors = True
                    broken_uris |= m_broken_uris
                    self.lock_mirrors(False,[uri], repo = repo)
                    continue

                # all fine then, we need to move data from mytmpdir to database_dir_path

                # EAPI 1
                # unpack database
                compressed_db_filename = os.path.basename(download_data['compressed_database_path'])
                uncompressed_db_filename = os.path.basename(database_path)
                compressed_file = os.path.join(mytmpdir,compressed_db_filename)
                uncompressed_file = os.path.join(mytmpdir,uncompressed_db_filename)
                self.entropyTools.uncompress_file(compressed_file, uncompressed_file, eval(cmethod[0]))
                # now move
                for myfile in os.listdir(mytmpdir):
                    fromfile = os.path.join(mytmpdir,myfile)
                    tofile = os.path.join(database_dir_path,myfile)
                    shutil.move(fromfile,tofile)
                    self.Entropy.ClientService.setup_default_file_perms(tofile)

            if os.path.isdir(mytmpdir):
                shutil.rmtree(mytmpdir)
            if os.path.isdir(mytmpdir):
                os.rmdir(mytmpdir)


            fine_uris.add(uri)
            self.lock_mirrors(False,[uri], repo = repo)

        return download_errors, fine_uris, broken_uris

    def calculate_database_sync_queues(self, repo = None):

        if repo == None:
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
                for x in remote_status:
                    if x[1] == highest_remote_revision:
                        download_latest = x
                        break

            if download_latest:
                upload_queue = [x for x in remote_status if (x[1] < highest_remote_revision)]
            else:
                upload_queue = [x for x in remote_status if (x[1] < local_revision)]

        return download_latest, upload_queue

    def sync_databases(self, no_upload = False, unlock_mirrors = False, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        while 1:

            db_locked = False
            if self.is_local_database_locked(repo):
                db_locked = True

            lock_data = self.get_mirrors_lock(repo)
            mirrors_locked = [x for x in lock_data if x[1]]

            if not mirrors_locked and db_locked:
                # mirrors not locked remotely but only locally
                mylock_file = self.get_database_lockfile(repo)
                if os.path.isfile(mylock_file) and os.access(mylock_file,os.W_OK):
                    os.remove(mylock_file)
                    continue

            break

        if mirrors_locked and not db_locked:
            mytxt = "%s, %s %s" % (
                _("At the moment, mirrors are locked, someone is working on their databases"),
                _("try again later"),
                "...",
            )
            raise OnlineMirrorError("OnlineMirrorError: %s" % (mytxt,))

        download_latest, upload_queue = self.calculate_database_sync_queues(repo)

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
            download_errors, fine_uris, broken_uris = self.download_database([download_uri], repo = repo)
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
                return 1,fine_uris,broken_uris
            # XXX: reload revision settings?

        if upload_queue and not no_upload:

            deps_not_found = self.Entropy.dependencies_test()
            if deps_not_found and not self.Entropy.community_repo:
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
                return 3,set(),set()

            problems = self.Entropy.check_config_file_updates()
            if problems:
                return 4,set(),set()

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
            #             for x in scandata:
            #    

            uris = [x[0] for x in upload_queue]
            errors, fine_uris, broken_uris = self.upload_database(uris, repo = repo)
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
                return 2,fine_uris,broken_uris


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
        upload_dir = os.path.join(self.Entropy.get_local_upload_directory(repo),branch)

        for package in os.listdir(upload_dir):
            if package.endswith(etpConst['packagesext']) or package.endswith(etpConst['packageshashfileext']):
                upload_packages.add(package)
                if package.endswith(etpConst['packagesext']):
                    upload_files += 1

        return upload_files, upload_packages

    def calculate_local_package_files(self, branch, repo = None):
        local_files = 0
        local_packages = set()
        packages_dir = os.path.join(self.Entropy.get_local_packages_directory(repo),branch)

        if not os.path.isdir(packages_dir):
            os.makedirs(packages_dir)

        for package in os.listdir(packages_dir):
            if package.endswith(etpConst['packagesext']) or package.endswith(etpConst['packageshashfileext']):
                local_packages.add(package)
                if package.endswith(etpConst['packagesext']):
                    local_files += 1

        return local_files, local_packages


    def _show_local_sync_stats(self, upload_files, local_files):
        self.Entropy.updateProgress(
            "%s:" % ( blue(_("Local statistics")),),
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

    def _show_sync_queues(self, upload, download, removal, copy, metainfo, branch):

        # show stats
        for itemdata in upload:
            package = darkgreen(os.path.basename(itemdata[0]))
            size = blue(self.entropyTools.bytes_into_human(itemdata[1]))
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
        for itemdata in download:
            package = darkred(os.path.basename(itemdata[0]))
            size = blue(self.entropyTools.bytes_into_human(itemdata[1]))
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
        for itemdata in copy:
            package = darkblue(os.path.basename(itemdata[0]))
            size = blue(self.entropyTools.bytes_into_human(itemdata[1]))
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
        for itemdata in removal:
            package = brown(os.path.basename(itemdata[0]))
            size = blue(self.entropyTools.bytes_into_human(itemdata[1]))
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
                darkred(self.entropyTools.bytes_into_human(metainfo['removal'])),
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


    def calculate_remote_package_files(self, uri, branch, ftp_connection = None, repo = None):

        remote_files = 0
        close_conn = False
        remote_packages_data = {}

        my_path = os.path.join(self.Entropy.get_remote_packages_relative_path(repo),branch)
        if ftp_connection == None:
            close_conn = True
            # let it raise an exception if things go bad
            ftp_connection = self.FtpInterface(uri, self.Entropy)
        ftp_connection.set_cwd(my_path, dodir = True)

        remote_packages = ftp_connection.list_dir()
        remote_packages_info = ftp_connection.get_raw_list()
        if close_conn:
            ftp_connection.close()

        for tbz2 in remote_packages:
            if tbz2.endswith(etpConst['packagesext']):
                remote_files += 1

        for remote_package in remote_packages_info:
            remote_packages_data[remote_package.split()[8]] = int(remote_package.split()[4])

        return remote_files, remote_packages, remote_packages_data

    def calculate_packages_to_sync(self, uri, branch, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
        upload_files, upload_packages = self.calculate_local_upload_files(branch, repo)
        local_files, local_packages = self.calculate_local_package_files(branch, repo)
        self._show_local_sync_stats(upload_files, local_files)

        self.Entropy.updateProgress(
            "%s: %s" % (blue(_("Remote statistics for")),red(crippled_uri),),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )
        remote_files, remote_packages, remote_packages_data = self.calculate_remote_package_files(
            uri,
            branch,
            repo = repo
        )
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

        mytxt = blue("%s ...") % (_("Calculating queues"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        uploadQueue, downloadQueue, removalQueue, fineQueue = self.calculate_sync_queues(
                upload_packages,
                local_packages,
                remote_packages,
                remote_packages_data,
                branch,
                repo
        )
        return uploadQueue, downloadQueue, removalQueue, fineQueue, remote_packages_data

    def calculate_sync_queues(
            self,
            upload_packages,
            local_packages,
            remote_packages,
            remote_packages_data,
            branch,
            repo = None
        ):

        uploadQueue = set()
        downloadQueue = set()
        removalQueue = set()
        fineQueue = set()

        for local_package in upload_packages:
            if local_package in remote_packages:
                local_filepath = os.path.join(self.Entropy.get_local_upload_directory(repo),branch,local_package)
                local_size = self.entropyTools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(local_package)
                if remote_size == None:
                    remote_size = 0
                if (local_size != remote_size):
                    # size does not match, adding to the upload queue
                    uploadQueue.add(local_package)
                else:
                    fineQueue.add(local_package) # just move from upload to packages
            else:
                # always force upload of packages in uploaddir
                uploadQueue.add(local_package)

        # if a package is in the packages directory but not online, we have to upload it
        # we have local_packages and remotePackages
        for local_package in local_packages:
            if local_package in remote_packages:
                local_filepath = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,local_package)
                local_size = self.entropyTools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(local_package)
                if remote_size == None:
                    remote_size = 0
                if (local_size != remote_size) and (local_size != 0):
                    # size does not match, adding to the upload queue
                    if local_package not in fineQueue:
                        uploadQueue.add(local_package)
            else:
                # this means that the local package does not exist
                # so, we need to download it
                uploadQueue.add(local_package)

        # Fill downloadQueue and removalQueue
        for remote_package in remote_packages:
            if remote_package in local_packages:
                local_filepath = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,remote_package)
                local_size = self.entropyTools.get_file_size(local_filepath)
                remote_size = remote_packages_data.get(remote_package)
                if remote_size == None:
                    remote_size = 0
                if (local_size != remote_size) and (local_size != 0):
                    # size does not match, remove first
                    if remote_package not in uploadQueue: # do it only if the package has not been added to the uploadQueue
                        removalQueue.add(remote_package) # remotePackage == localPackage # just remove something that differs from the content of the mirror
                        # then add to the download queue
                        downloadQueue.add(remote_package)
            else:
                # this means that the local package does not exist
                # so, we need to download it
                if not remote_package.endswith(".tmp"): # ignore .tmp files
                    downloadQueue.add(remote_package)

        # Collect packages that don't exist anymore in the database
        # so we can filter them out from the download queue
        dbconn = self.Entropy.open_server_repository(just_reading = True, repo = repo)
        db_files = dbconn.listBranchPackagesTbz2(branch, do_sort = False, full_path = True)
        db_files = set([os.path.basename(x) for x in db_files if (self.Entropy.get_branch_from_download_relative_uri(x) == branch)])

        exclude = set()
        for myfile in downloadQueue:
            if myfile.endswith(etpConst['packagesext']):
                if myfile not in db_files:
                    exclude.add(myfile)
        downloadQueue -= exclude

        exclude = set()
        for myfile in uploadQueue:
            if myfile.endswith(etpConst['packagesext']):
                if myfile not in db_files:
                    exclude.add(myfile)
        uploadQueue -= exclude

        exclude = set()
        for myfile in downloadQueue:
            if myfile in uploadQueue:
                exclude.add(myfile)
        downloadQueue -= exclude

        return uploadQueue, downloadQueue, removalQueue, fineQueue


    def expand_queues(self, uploadQueue, downloadQueue, removalQueue, remote_packages_data, branch, repo):

        metainfo = {
            'removal': 0,
            'download': 0,
            'upload': 0,
        }
        removal = []
        download = []
        do_copy = []
        upload = []

        for item in removalQueue:
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,item)
            size = self.entropyTools.get_file_size(local_filepath)
            metainfo['removal'] += size
            removal.append((local_filepath,size))

        for item in downloadQueue:
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(self.Entropy.get_local_upload_directory(repo),branch,item)
            if not os.path.isfile(local_filepath):
                size = remote_packages_data.get(item)
                if size == None:
                    size = 0
                size = int(size)
                metainfo['removal'] += size
                download.append((local_filepath,size))
            else:
                size = self.entropyTools.get_file_size(local_filepath)
                do_copy.append((local_filepath,size))

        for item in uploadQueue:
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(self.Entropy.get_local_upload_directory(repo),branch,item)
            local_filepath_pkgs = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,item)
            if os.path.isfile(local_filepath):
                size = self.entropyTools.get_file_size(local_filepath)
                upload.append((local_filepath,size))
            else:
                size = self.entropyTools.get_file_size(local_filepath_pkgs)
                upload.append((local_filepath_pkgs,size))
            metainfo['upload'] += size


        return upload, download, removal, do_copy, metainfo


    def _sync_run_removal_queue(self, removal_queue, branch, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        for itemdata in removal_queue:

            remove_filename = itemdata[0]
            remove_filepath = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,remove_filename)
            remove_filepath_hash = remove_filepath+etpConst['packageshashfileext']
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

        if repo == None:
            repo = self.Entropy.default_repository

        for itemdata in copy_queue:

            from_file = itemdata[0]
            from_file_hash = from_file+etpConst['packageshashfileext']
            to_file = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,os.path.basename(from_file))
            to_file_hash = to_file+etpConst['packageshashfileext']
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

            shutil.copy2(from_file,to_file)
            if not os.path.isfile(from_file_hash):
                self.create_file_checksum(from_file, from_file_hash)
            shutil.copy2(from_file_hash,to_file_hash)

            # clear expiration file
            if os.path.isfile(expiration_file):
                os.remove(expiration_file)


    def _sync_run_upload_queue(self, uri, upload_queue, branch, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
        myqueue = []
        for itemdata in upload_queue:
            x = itemdata[0]
            hash_file = x+etpConst['packageshashfileext']
            if not os.path.isfile(hash_file):
                self.entropyTools.create_hash_file(x)
            myqueue.append(hash_file)
            myqueue.append(x)

        ftp_basedir = os.path.join(self.Entropy.get_remote_packages_relative_path(repo),branch)
        uploader = self.FtpServerHandler(self.FtpInterface,
            self.Entropy,
            [uri],
            myqueue,
            critical_files = myqueue,
            use_handlers = True,
            ftp_basedir = ftp_basedir,
            handlers_data = {'branch': branch },
            repo = repo
        )
        errors, m_fine_uris, m_broken_uris = uploader.go()
        if errors:
            my_broken_uris = [(self.entropyTools.extract_ftp_host_from_uri(x[0]),x[1]) for x in m_broken_uris]
            reason = my_broken_uris[0][1]
            self.Entropy.updateProgress(
                "[branch:%s] %s: %s, %s: %s" % (
                            brown(branch),
                            blue(_("upload errors")),
                            red(crippled_uri),
                            blue(_("reason")),
                            darkgreen(unicode(reason)),
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


    def _sync_run_download_queue(self, uri, download_queue, branch, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
        myqueue = []
        for itemdata in download_queue:
            x = itemdata[0]
            hash_file = x+etpConst['packageshashfileext']
            myqueue.append(x)
            myqueue.append(hash_file)

        ftp_basedir = os.path.join(self.Entropy.get_remote_packages_relative_path(repo),branch)
        local_basedir = os.path.join(self.Entropy.get_local_packages_directory(repo),branch)
        downloader = self.FtpServerHandler(
            self.FtpInterface,
            self.Entropy,
            [uri],
            myqueue,
            critical_files = myqueue,
            use_handlers = True,
            ftp_basedir = ftp_basedir,
            local_basedir = local_basedir,
            handlers_data = {'branch': branch },
            download = True,
            repo = repo
        )
        errors, m_fine_uris, m_broken_uris = downloader.go()
        if errors:
            my_broken_uris = [(self.entropyTools.extract_ftp_host_from_uri(x[0]),x[1]) for x in m_broken_uris]
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


    def sync_packages(self, ask = True, pretend = False, packages_check = False, repo = None):

        if repo == None:
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
        mirrors_tainted = False
        mirror_errors = False
        mirrors_errors = False

        for uri in self.Entropy.get_remote_mirrors(repo):

            crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
            mirror_errors = False

            self.Entropy.updateProgress(
                "[repo:%s|%s|branch:%s] %s: %s" % (
                    repo,
                    red(_("sync")),
                    brown(etpConst['branch']),
                    blue(_("packages sync")),
                    bold(crippled_uri),
                ),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )

            try:
                uploadQueue, downloadQueue, removalQueue, fineQueue, remote_packages_data = self.calculate_packages_to_sync(uri, etpConst['branch'], repo)
                del fineQueue
            except self.socket.error, e:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s: %s, %s %s" % (
                        repo,
                        red(_("sync")),
                        etpConst['branch'],
                        darkred(_("socket error")),
                        e,
                        darkred(_("on")),
                        crippled_uri,
                    ),
                    importance = 1,
                    type = "error",
                    header = darkgreen(" * ")
                )
                continue

            if (not uploadQueue) and (not downloadQueue) and (not removalQueue):
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s: %s" % (
                        repo,
                        red(_("sync")),
                        etpConst['branch'],
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
                        uploadQueue,
                        downloadQueue,
                        removalQueue,
                        remote_packages_data,
                        etpConst['branch'],
                        repo
            )
            del uploadQueue, downloadQueue, removalQueue, remote_packages_data
            self._show_sync_queues(upload, download, removal, copy, metainfo, etpConst['branch'])

            if not len(upload)+len(download)+len(removal)+len(copy):

                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s %s" % (
                        self.Entropy.default_repository,
                        red(_("sync")),
                        etpConst['branch'],
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
                rc = self.Entropy.askQuestion(_("Would you like to run the steps above ?"))
                if rc == "No":
                    continue

            try:

                if removal:
                    self._sync_run_removal_queue(removal, etpConst['branch'], repo)
                if copy:
                    self._sync_run_copy_queue(copy, etpConst['branch'], repo)
                if upload or download:
                    mirrors_tainted = True
                if upload:
                    d_errors, m_fine_uris, m_broken_uris = self._sync_run_upload_queue(uri, upload, etpConst['branch'], repo)
                    if d_errors: mirror_errors = True
                if download:
                    d_errors, m_fine_uris, m_broken_uris = self._sync_run_download_queue(uri, download, etpConst['branch'], repo)
                    if d_errors: mirror_errors = True
                if not mirror_errors:
                    successfull_mirrors.add(uri)
                else:
                    mirrors_errors = True

            except KeyboardInterrupt:
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s" % (
                        repo,
                        red(_("sync")),
                        etpConst['branch'],
                        darkgreen(_("keyboard interrupt !")),
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                continue

            except Exception, e:

                self.entropyTools.print_traceback()
                mirrors_errors = True
                broken_mirrors.add(uri)
                self.Entropy.updateProgress(
                    "[repo:%s|%s|branch:%s] %s: %s, %s: %s" % (
                        repo,
                        red(_("sync")),
                        etpConst['branch'],
                        darkred(_("exception caught")),
                        Exception,
                        _("error"),
                        e,
                    ),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )

                exc_txt = self.Entropy.entropyTools.print_exception(returndata = True)
                for line in exc_txt:
                    self.Entropy.updateProgress(
                        unicode(line),
                        importance = 1,
                        type = "error",
                        header = darkred(":  ")
                    )

                if len(successfull_mirrors) > 0:
                    self.Entropy.updateProgress(
                        "[repo:%s|%s|branch:%s] %s" % (
                            repo,
                            red(_("sync")),
                            etpConst['branch'],
                            darkred(_("at least one mirror has been sync'd properly, hooray!")),
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                continue

        # if at least one server has been synced successfully, move files
        if (len(successfull_mirrors) > 0) and not pretend:
            self.remove_expiration_files(etpConst['branch'], repo)

        if packages_check:
            check_data = self.Entropy.verify_local_packages([], ask = ask, repo = repo)

        return mirrors_tainted, mirrors_errors, successfull_mirrors, broken_mirrors, check_data

    def remove_expiration_files(self, branch, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        branch_dir = os.path.join(self.Entropy.get_local_upload_directory(repo),branch)
        branchcontent = os.listdir(branch_dir)
        for xfile in branchcontent:
            source = os.path.join(self.Entropy.get_local_upload_directory(repo),branch,xfile)
            destdir = os.path.join(self.Entropy.get_local_packages_directory(repo),branch)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)
            dest = os.path.join(destdir,xfile)
            shutil.move(source,dest)
            # clear expiration file
            dest_expiration = dest+etpConst['packagesexpirationfileext']
            if os.path.isfile(dest_expiration):
                os.remove(dest_expiration)


    def is_package_expired(self, package_file, branch, repo = None):
        pkg_path = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,package_file)
        pkg_path += etpConst['packagesexpirationfileext']
        if not os.path.isfile(pkg_path):
            return False
        mtime = self.entropyTools.get_file_unix_mtime(pkg_path)
        delta = int(etpConst['packagesexpirationdays'])*24*3600
        currmtime = time.time()
        file_delta = currmtime - mtime
        if file_delta > delta:
            return True
        return False

    def create_expiration_file(self, package_file, branch, repo = None, gentle = False):
        pkg_path = os.path.join(self.Entropy.get_local_packages_directory(repo),branch,package_file)
        pkg_path += etpConst['packagesexpirationfileext']
        if gentle and os.path.isfile(pkg_path):
            return
        f = open(pkg_path,"w")
        f.flush()
        f.close()


    def collect_expiring_packages(self, branch, repo = None):
        dbconn = self.Entropy.open_server_repository(just_reading = True, repo = repo)
        database_bins = dbconn.listBranchPackagesTbz2(branch, do_sort = False, full_path = True)
        bins_dir = os.path.join(self.Entropy.get_local_packages_directory(repo),branch)
        repo_bins = set()
        if os.path.isdir(bins_dir):
            repo_bins = os.listdir(bins_dir)
            repo_bins = set([os.path.join('packages',etpSys['arch'],branch,x) for x in repo_bins if x.endswith(etpConst['packagesext'])])
        repo_bins -= database_bins
        return set([os.path.basename(x) for x in repo_bins])


    def tidy_mirrors(self, ask = True, pretend = False, repo = None):

        if repo == None:
            repo = self.Entropy.default_repository

        self.Entropy.updateProgress(
            "[repo:%s|%s|branch:%s] %s" % (
                brown(repo),
                red(_("tidy")),
                blue(etpConst['branch']),
                blue(_("collecting expired packages")),
            ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        branch_data = {}
        errors = False

        branch_data['errors'] = False

        if etpConst['branch'] != etpConst['branches'][-1]:
            self.Entropy.updateProgress(
                "[branch:%s] %s" % (
                    brown(etpConst['branch']),
                    blue(_("not the latest branch, skipping tidy for consistence. This branch entered the maintenance mode.")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            branch_data['errors'] = True
            return True, branch_data

        self.Entropy.updateProgress(
            "[branch:%s] %s" % (
                brown(etpConst['branch']),
                blue(_("collecting expired packages in the selected branches")),
            ),
            importance = 1,
            type = "info",
            header = blue(" @@ ")
        )

        # collect removed packages
        expiring_packages = self.collect_expiring_packages(etpConst['branch'], repo)

        removal = []
        for package in expiring_packages:
            expired = self.is_package_expired(package, etpConst['branch'], repo)
            if expired:
                removal.append(package)
            else:
                self.create_expiration_file(package, etpConst['branch'], repo, gentle = True)

        # fill returning data
        branch_data['removal'] = removal[:]

        if not removal:
            self.Entropy.updateProgress(
                "[branch:%s] %s" % (
                        brown(etpConst['branch']),
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
                    brown(etpConst['branch']),
                    blue(_("these are the expired packages")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            for package in removal:
                self.Entropy.updateProgress(
                    "[branch:%s] %s: %s" % (
                                brown(etpConst['branch']),
                                blue(_("remove")),
                                darkgreen(package),
                        ),
                    importance = 1,
                    type = "info",
                    header = brown("    # ")
                )

        if pretend:
            return errors,branch_data

        if ask:
            rc = self.Entropy.askQuestion(_("Would you like to continue ?"))
            if rc == "No":
                return errors, branch_data

        myqueue = []
        for package in removal:
            myqueue.append(package+etpConst['packageshashfileext'])
            myqueue.append(package)
        ftp_basedir = os.path.join(self.Entropy.get_remote_packages_relative_path(repo),etpConst['branch'])
        for uri in self.Entropy.get_remote_mirrors(repo):

            self.Entropy.updateProgress(
                "[branch:%s] %s..." % (
                    brown(etpConst['branch']),
                    blue(_("removing packages remotely")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )

            crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
            destroyer = self.FtpServerHandler(
                self.FtpInterface,
                self.Entropy,
                [uri],
                myqueue,
                critical_files = [],
                ftp_basedir = ftp_basedir,
                remove = True,
                repo = repo
            )
            errors, m_fine_uris, m_broken_uris = destroyer.go()
            if errors:
                my_broken_uris = [(self.entropyTools.extract_ftp_host_from_uri(x[0]),x[1]) for x in m_broken_uris]
                reason = my_broken_uris[0][1]
                self.Entropy.updateProgress(
                    "[branch:%s] %s: %s, %s: %s" % (
                        brown(etpConst['branch']),
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
                        brown(etpConst['branch']),
                        blue(_("removing packages locally")),
                    ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )

            branch_data['removed'] = set()
            for package in removal:
                package_path = os.path.join(self.Entropy.get_local_packages_directory(repo),etpConst['branch'],package)
                package_path_hash = package_path+etpConst['packageshashfileext']
                package_path_expired = package_path+etpConst['packagesexpirationfileext']
                for myfile in [package_path_hash,package_path,package_path_expired]:
                    if os.path.isfile(myfile):
                        self.Entropy.updateProgress(
                            "[branch:%s] %s: %s" % (
                                        brown(etpConst['branch']),
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
