# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Server transceivers module}.

"""
import os
import sys
import time
from entropy.const import const_isstring
from entropy.output import darkred, blue, brown, darkgreen, red, bold
from entropy.exceptions import *
from entropy.i18n import _
from entropy.core.settings.base import SystemSettings

class TransceiverServerHandler:

    import entropy.tools as entropyTools
    def __init__(self, txc_interface, entropy_interface, uris, files_to_upload,
        download = False, remove = False, txc_basedir = None, local_basedir = None,
        critical_files = [], use_handlers = False, handlers_data = {}, repo = None):

        self._txc = txc_interface
        self.Entropy = entropy_interface
        if not isinstance(uris, list):
            raise InvalidDataType("InvalidDataType: %s" % (_("uris must be a list instance"),))
        if not isinstance(files_to_upload, (list, dict)):
            raise InvalidDataType("InvalidDataType: %s" % (
                    _("files_to_upload must be a list or dict instance"),
                )
            )
        self.uris = uris
        if isinstance(files_to_upload, list):
            self.myfiles = files_to_upload[:]
        else:
            self.myfiles = sorted([x for x in files_to_upload])
        self.download = download
        self.remove = remove
        self.repo = repo
        if self.repo == None:
            self.repo = self.Entropy.default_repository
        self.use_handlers = use_handlers
        if self.remove:
            self.download = False
            self.use_handlers = False
        if not txc_basedir:
            # default to database directory
            branch = SystemSettings()['repositories']['branch']
            my_path = os.path.join(self.Entropy.get_remote_database_relative_path(repo), branch)
            self.txc_basedir = my_path
        else:
            self.txc_basedir = txc_basedir
        if not local_basedir:
            # default to database directory
            self.local_basedir = os.path.dirname(self.Entropy.get_local_database_file(self.repo))
        else:
            self.local_basedir = local_basedir
        self.critical_files = critical_files
        self.handlers_data = handlers_data.copy()

    def handler_verify_upload(self, local_filepath, uri, counter, maxcount,
            tries, remote_md5 = None):

        crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)

        self.Entropy.updateProgress(
            "[%s|#%s|(%s/%s)] %s: %s" % (
                blue(crippled_uri),
                darkgreen(str(tries)),
                blue(str(counter)),
                bold(str(maxcount)),
                darkgreen(_("verifying upload (if supported)")),
                blue(os.path.basename(local_filepath)),
            ),
            importance = 0,
            type = "info",
            header = red(" @@ "),
            back = True
        )

        valid_remote_md5 = True
        # if remote server supports MD5 commands, remote_md5 is filled
        if const_isstring(remote_md5):
            valid_md5 = self.entropyTools.is_valid_md5(remote_md5)
            ckres = False
            if valid_md5: # seems valid
                ckres = self.entropyTools.compare_md5(local_filepath,
                    remote_md5)
            if ckres:
                self.Entropy.updateProgress(
                    "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                        blue(crippled_uri),
                        darkgreen(str(tries)),
                        blue(str(counter)),
                        bold(str(maxcount)),
                        blue(_("digest verification")),
                        os.path.basename(local_filepath),
                        darkgreen(_("so far, so good!")),
                    ),
                    importance = 0,
                    type = "info",
                    header = red(" @@ ")
                )
                return True
            # ouch!
            elif not valid_md5:
                # mmmh... malformed md5, try with handlers
                self.Entropy.updateProgress(
                    "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                        blue(crippled_uri),
                        darkgreen(str(tries)),
                        blue(str(counter)),
                        bold(str(maxcount)),
                        blue(_("digest verification")),
                        os.path.basename(local_filepath),
                        bold(_("malformed md5 provided to function")),
                    ),
                    importance = 0,
                    type = "warning",
                    header = brown(" @@ ")
                )
            else: # it's really bad!
                self.Entropy.updateProgress(
                    "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                        blue(crippled_uri),
                        darkgreen(str(tries)),
                        blue(str(counter)),
                        bold(str(maxcount)),
                        blue(_("digest verification")),
                        os.path.basename(local_filepath),
                        bold(_("remote md5 is invalid")),
                    ),
                    importance = 0,
                    type = "warning",
                    header = brown(" @@ ")
                )
                valid_remote_md5 = False

        if not self.use_handlers:
            # handlers usage is disabled
            return valid_remote_md5 # always valid

        checksum = self.Entropy.get_remote_package_checksum(
            self.repo,
            os.path.basename(local_filepath),
            self.handlers_data['branch']
        )
        if checksum == None:
            self.Entropy.updateProgress(
                "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                    blue(crippled_uri),
                    darkgreen(str(tries)),
                    blue(str(counter)),
                    bold(str(maxcount)),
                    blue(_("digest verification")),
                    os.path.basename(local_filepath),
                    darkred(_("not supported")),
                ),
                importance = 0,
                type = "info",
                header = red(" @@ ")
            )
            return valid_remote_md5
        elif isinstance(checksum, bool) and not checksum:
            self.Entropy.updateProgress(
                "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                    blue(crippled_uri),
                    darkgreen(str(tries)),
                    blue(str(counter)),
                    bold(str(maxcount)),
                    blue(_("digest verification")),
                    os.path.basename(local_filepath),
                    bold(_("file not found")),
                ),
                importance = 0,
                type = "warning",
                header = brown(" @@ ")
            )
            return False
        elif self.entropyTools.is_valid_md5(checksum):
            # valid? checking
            ckres = self.entropyTools.compare_md5(local_filepath, checksum)
            if ckres:
                self.Entropy.updateProgress(
                    "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                        blue(crippled_uri),
                        darkgreen(str(tries)),
                        blue(str(counter)),
                        bold(str(maxcount)),
                        blue(_("digest verification")),
                        os.path.basename(local_filepath),
                        darkgreen(_("so far, so good!")),
                    ),
                    importance = 0,
                    type = "info",
                    header = red(" @@ ")
                )
                return True
            else:
                self.Entropy.updateProgress(
                    "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                        blue(crippled_uri),
                        darkgreen(str(tries)),
                        blue(str(counter)),
                        bold(str(maxcount)),
                        blue(_("digest verification")),
                        os.path.basename(local_filepath),
                        darkred(_("invalid checksum")),
                    ),
                    importance = 0,
                    type = "warning",
                    header = brown(" @@ ")
                )
                return False
        else:
            self.Entropy.updateProgress(
                "[%s|#%s|(%s/%s)] %s: %s: %s" % (
                    blue(crippled_uri),
                    darkgreen(str(tries)),
                    blue(str(counter)),
                    bold(str(maxcount)),
                    blue(_("digest verification")),
                    os.path.basename(local_filepath),
                    darkred(_("unknown data returned")),
                ),
                importance = 0,
                type = "warning",
                header = brown(" @@ ")
            )
            return valid_remote_md5

    def go(self):

        broken_uris = set()
        fine_uris = set()
        errors = False
        action = 'upload'
        if self.download:
            action = 'download'
        elif self.remove:
            action = 'remove'

        def ensure_ftp(ftp):
            try:
                ftp.set_basedir()
                ftp.set_cwd(self.txc_basedir, dodir = True)
            except ftp.ftplib.error_temp:
                ftp.reconnect_host()

        for uri in self.uris:

            crippled_uri = self.entropyTools.extract_ftp_host_from_uri(uri)
            self.Entropy.updateProgress(
                "[%s|%s] %s..." % (
                    blue(crippled_uri),
                    brown(action),
                    blue(_("connecting to mirror")),
                ),
                importance = 0,
                type = "info",
                header = blue(" @@ ")
            )
            try:
                ftp = self._txc(uri, self.Entropy)
            except ConnectionError:
                self.entropyTools.print_traceback()
                return True, fine_uris, broken_uris # issues
            branch = SystemSettings()['repositories']['branch']
            my_path = os.path.join(self.Entropy.get_remote_database_relative_path(self.repo), branch)
            self.Entropy.updateProgress(
                "[%s|%s] %s %s..." % (
                    blue(crippled_uri),
                    brown(action),
                    blue(_("changing directory to")),
                    darkgreen(my_path),
                ),
                importance = 0,
                type = "info",
                header = blue(" @@ ")
            )

            ftp.set_cwd(self.txc_basedir, dodir = True)
            maxcount = len(self.myfiles)
            counter = 0

            for mypath in self.myfiles:

                ensure_ftp(ftp)

                mycwd = None
                if isinstance(mypath, tuple):
                    if len(mypath) < 2:
                        continue
                    mycwd = mypath[0]
                    mypath = mypath[1]
                    ftp.set_cwd(mycwd, dodir = True)

                syncer = ftp.upload_file
                myargs = [mypath]
                if self.download:
                    syncer = ftp.download_file
                    myargs = [os.path.basename(mypath), self.local_basedir]
                elif self.remove:
                    syncer = ftp.delete_file

                counter += 1
                tries = 0
                done = False
                lastrc = None
                while tries < 5:
                    tries += 1
                    self.Entropy.updateProgress(
                        "[%s|#%s|(%s/%s)] %s: %s" % (
                            blue(crippled_uri),
                            darkgreen(str(tries)),
                            blue(str(counter)),
                            bold(str(maxcount)),
                            blue(action+"ing"),
                            red(os.path.basename(mypath)),
                        ),
                        importance = 0,
                        type = "info",
                        header = red(" @@ ")
                    )
                    rc = syncer(*myargs)
                    if rc and not self.download:
                        # try with "SITE MD5 command first"
                        # proftpd's mod_md5 supports it
                        remote_md5 = ftp.get_file_md5(os.path.basename(mypath))
                        rc = self.handler_verify_upload(mypath, uri,
                            counter, maxcount, tries, remote_md5 = remote_md5)
                    if rc:
                        self.Entropy.updateProgress(
                            "[%s|#%s|(%s/%s)] %s %s: %s" % (
                                        blue(crippled_uri),
                                        darkgreen(str(tries)),
                                        blue(str(counter)),
                                        bold(str(maxcount)),
                                        blue(action),
                                        _("successful"),
                                        red(os.path.basename(mypath)),
                            ),
                            importance = 0,
                            type = "info",
                            header = darkgreen(" @@ ")
                        )
                        done = True
                        break
                    else:
                        self.Entropy.updateProgress(
                            "[%s|#%s|(%s/%s)] %s %s: %s" % (
                                        blue(crippled_uri),
                                        darkgreen(str(tries)),
                                        blue(str(counter)),
                                        bold(str(maxcount)),
                                        blue(action),
                                        brown(_("failed, retrying")),
                                        red(os.path.basename(mypath)),
                                ),
                            importance = 0,
                            type = "warning",
                            header = brown(" @@ ")
                        )
                        lastrc = rc
                        continue

                if not done:

                    self.Entropy.updateProgress(
                        "[%s|(%s/%s)] %s %s: %s - %s: %s" % (
                                blue(crippled_uri),
                                blue(str(counter)),
                                bold(str(maxcount)),
                                blue(action),
                                darkred("failed, giving up"),
                                red(os.path.basename(mypath)),
                                _("error"),
                                lastrc,
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )

                    if mypath not in self.critical_files:
                        self.Entropy.updateProgress(
                            "[%s|(%s/%s)] %s: %s, %s..." % (
                                blue(crippled_uri),
                                blue(str(counter)),
                                bold(str(maxcount)),
                                blue(_("not critical")),
                                os.path.basename(mypath),
                                blue(_("continuing")),
                            ),
                            importance = 1,
                            type = "warning",
                            header = brown(" @@ ")
                        )
                        continue

                    ftp.close()
                    errors = True
                    broken_uris.add((uri, lastrc))
                    # next mirror
                    break

            # close connection
            ftp.close()
            fine_uris.add(uri)

        return errors, fine_uris, broken_uris
