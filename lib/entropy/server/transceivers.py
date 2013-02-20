# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Server transceivers module}.

"""
import os

from entropy.const import const_isstring, const_isnumber, etpConst
from entropy.output import darkred, blue, brown, darkgreen, red, bold
from entropy.transceivers.exceptions import TransceiverConnectionError
from entropy.i18n import _
from entropy.client.interfaces.db import InstalledPackagesRepository
from entropy.core.settings.base import SystemSettings
from entropy.transceivers import EntropyTransceiver
from entropy.tools import print_traceback, is_valid_md5, compare_md5, md5sum

class TransceiverServerHandler:

    def __init__(self, entropy_interface, uris, files_to_upload,
        download = False, remove = False, txc_basedir = None,
        local_basedir = None, critical_files = None,
        handlers_data = None, repo = None, copy_herustic_support = False):

        if critical_files is None:
            critical_files = []
        if handlers_data is None:
            handlers_data = {}

        self._entropy = entropy_interface
        if not isinstance(uris, list):
            raise AttributeError("uris must be a list instance")
        if not isinstance(files_to_upload, (list, dict)):
            raise AttributeError(
                "files_to_upload must be a list or dict instance")
        self.uris = uris
        if isinstance(files_to_upload, list):
            self.myfiles = files_to_upload[:]
        else:
            self.myfiles = sorted([x for x in files_to_upload])

        self._settings = SystemSettings()
        self.sys_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        srv_set = self._settings[self.sys_settings_plugin_id]['server']

        # server-side speed limit
        self.speed_limit = srv_set['sync_speed_limit']
        self.download = download
        self.remove = remove
        self.repo = repo
        if self.repo == None:
            self.repo = self._entropy.repository()
        if self.remove:
            self.download = False
        self._copy_herustic = copy_herustic_support
        if self._copy_herustic and (self.download or self.remove):
            raise AttributeError(
                "copy_herustic_support can be enabled only for uploads")

        if not txc_basedir:
            raise AttributeError("invalid txc_basedir passed")
        self.txc_basedir = txc_basedir

        if not local_basedir:
            # default to database directory
            self.local_basedir = os.path.dirname(
                self._entropy._get_local_repository_file(self.repo))
        else:
            self.local_basedir = local_basedir

        self.critical_files = critical_files
        self.handlers_data = handlers_data.copy()

    def handler_verify_upload(self, local_filepath, uri, counter, maxcount,
        tries, remote_md5 = None):

        crippled_uri = EntropyTransceiver.get_uri_name(uri)

        self._entropy.output(
            "[%s|#%s|(%s/%s)] %s: %s" % (
                blue(crippled_uri),
                darkgreen(str(tries)),
                blue(str(counter)),
                bold(str(maxcount)),
                darkgreen(_("verifying upload (if supported)")),
                blue(os.path.basename(local_filepath)),
            ),
            importance = 0,
            level = "info",
            header = red(" @@ "),
            back = True
        )

        valid_remote_md5 = True
        # if remote server supports MD5 commands, remote_md5 is filled
        if const_isstring(remote_md5):
            valid_md5 = is_valid_md5(remote_md5)
            ckres = False
            if valid_md5: # seems valid
                ckres = compare_md5(local_filepath, remote_md5)
            if ckres:
                self._entropy.output(
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
                    level = "info",
                    header = red(" @@ ")
                )
                return True
            # ouch!
            elif not valid_md5:
                # mmmh... malformed md5, try with handlers
                self._entropy.output(
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
                    level = "warning",
                    header = brown(" @@ ")
                )
            else: # it's really bad!
                self._entropy.output(
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
                    level = "warning",
                    header = brown(" @@ ")
                )
                valid_remote_md5 = False

        return valid_remote_md5 # always valid

    def _transceive(self, uri):

        fine = set()
        broken = set()
        fail = False
        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        action = 'push'
        if self.download:
            action = 'pull'
        elif self.remove:
            action = 'remove'

        try:
            txc = EntropyTransceiver(uri)
            if const_isnumber(self.speed_limit):
                txc.set_speed_limit(self.speed_limit)
            txc.set_output_interface(self._entropy)
        except TransceiverConnectionError:
            print_traceback()
            return True, fine, broken # issues

        maxcount = len(self.myfiles)
        counter = 0

        with txc as handler:

            for mypath in self.myfiles:

                base_dir = self.txc_basedir

                if isinstance(mypath, tuple):
                    if len(mypath) < 2:
                        continue
                    base_dir, mypath = mypath

                if not handler.is_dir(base_dir):
                    handler.makedirs(base_dir)

                mypath_fn = os.path.basename(mypath)
                remote_path = os.path.join(base_dir, mypath_fn)

                syncer = handler.upload
                myargs = (mypath, remote_path)
                if self.download:
                    syncer = handler.download
                    local_path = os.path.join(self.local_basedir, mypath_fn)
                    myargs = (remote_path, local_path)
                elif self.remove:
                    syncer = handler.delete
                    myargs = (remote_path,)

                fallback_syncer, fallback_args = None, None
                # upload -> remote copy herustic support
                # if a package file might have been already uploaded
                # to remote mirror, try to look in other repositories'
                # package directories if a file, with the same md5 and name
                # is already available. In this case, use remote copy instead
                # of upload to save bandwidth.
                if self._copy_herustic and (syncer == handler.upload):
                    # copy herustic support enabled
                    # we are uploading
                    new_syncer, new_args = self._copy_herustic_support(
                        handler, mypath, base_dir, remote_path)
                    if new_syncer is not None:
                        fallback_syncer, fallback_args = syncer, myargs
                        syncer, myargs = new_syncer, new_args
                        action = "copy"

                counter += 1
                tries = 0
                done = False
                lastrc = None

                while tries < 5:
                    tries += 1
                    self._entropy.output(
                        "[%s|#%s|(%s/%s)] %s: %s" % (
                            blue(crippled_uri),
                            darkgreen(str(tries)),
                            blue(str(counter)),
                            bold(str(maxcount)),
                            blue(action),
                            red(os.path.basename(mypath)),
                        ),
                        importance = 0,
                        level = "info",
                        header = red(" @@ ")
                    )
                    rc = syncer(*myargs)
                    if (not rc) and (fallback_syncer is not None):
                        # if we have a fallback syncer, try it first
                        # before giving up.
                        rc = fallback_syncer(*myargs)

                    if rc and not (self.download or self.remove):
                        remote_md5 = handler.get_md5(remote_path)
                        rc = self.handler_verify_upload(mypath, uri,
                            counter, maxcount, tries, remote_md5 = remote_md5)
                    if rc:
                        self._entropy.output(
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
                            level = "info",
                            header = darkgreen(" @@ ")
                        )
                        done = True
                        fine.add(uri)
                        break
                    else:
                        self._entropy.output(
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
                            level = "warning",
                            header = brown(" @@ ")
                        )
                        lastrc = rc
                        continue

                if not done:

                    self._entropy.output(
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
                        level = "error",
                        header = darkred(" !!! ")
                    )

                    if mypath not in self.critical_files:
                        self._entropy.output(
                            "[%s|(%s/%s)] %s: %s, %s..." % (
                                blue(crippled_uri),
                                blue(str(counter)),
                                bold(str(maxcount)),
                                blue(_("not critical")),
                                os.path.basename(mypath),
                                blue(_("continuing")),
                            ),
                            importance = 1,
                            level = "warning",
                            header = brown(" @@ ")
                        )
                        continue

                    fail = True
                    broken.add((uri, lastrc))
                    # next mirror
                    break

        return fail, fine, broken

    def _copy_herustic_support(self, handler, local_path,
            txc_basedir, remote_path):
        """
        Determine if it's possible to remote copy the package from other
        configured repositories to save bandwidth.
        This herustic only works with package files, not repository db files.
        Thus, it should be only enabled for these kind of uploads.
        """
        pkg_download = self.handlers_data.get('download')
        if pkg_download is None:
            # unsupported, we need at least package "download" metadatum
            # to be able to reconstruct a valid remote URI
            return None, None

        current_repository_id = self.repo
        available_repositories = self._entropy.available_repositories()
        test_repositories = []
        for repository_id, repo_meta in available_repositories.items():
            if current_repository_id == repository_id:
                # not me
                continue
            if repository_id == InstalledPackagesRepository.NAME:
                # __system__ repository doesn't have anything remotely
                # it's a fake repo, skip
                continue
            # In order to take advantage of remote copy, it is also required
            # that current working uri (handler.get_uri()) is also a packages
            # mirror of the other repository.
            if handler.get_uri() not in repo_meta['pkg_mirrors']:
                # no way
                continue
            test_repositories.append(repository_id)

        if not test_repositories:
            # sorry!
            return None, None

        test_repositories.sort()

        local_path_filename = os.path.basename(local_path)
        local_md5 = None
        for repository_id in test_repositories:
            repo_txc_basedir = \
                self._entropy.complete_remote_package_relative_path(
                    pkg_download, repository_id)
            test_remote_path = repo_txc_basedir + "/" + local_path_filename
            if not handler.is_file(test_remote_path):
                # not found on this packages mirror
                continue
            # then check md5 and compare
            remote_md5 = handler.get_md5(test_remote_path)
            if not const_isstring(remote_md5):
                # transceiver or remote server doesn't support md5sum()
                # so cannot verify the integrity
                continue
            if local_md5 is None:
                local_md5 = md5sum(local_path)
            if local_md5 == remote_md5:
                # yay! we can copy over!
                return handler.copy, (test_remote_path, remote_path)

        return None, None

    def go(self):

        broken_uris = set()
        fine_uris = set()
        errors = False
        action = 'push'
        if self.download:
            action = 'pull'
        elif self.remove:
            action = 'remove'

        for uri in self.uris:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)
            self._entropy.output(
                "[%s|%s] %s..." % (
                    blue(crippled_uri),
                    brown(action),
                    blue(_("connecting to mirror")),
                ),
                importance = 0,
                level = "info",
                header = blue(" @@ ")
            )

            self._entropy.output(
                "[%s|%s] %s %s..." % (
                    blue(crippled_uri),
                    brown(action),
                    blue(_("setting directory to")),
                    darkgreen(self.txc_basedir),
                ),
                importance = 0,
                level = "info",
                header = blue(" @@ ")
            )

            fail, fine, broken = self._transceive(uri)
            fine_uris |= fine
            broken_uris |= broken
            if fail:
                errors = True

        return errors, fine_uris, broken_uris
