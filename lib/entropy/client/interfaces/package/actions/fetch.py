# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
import codecs
import errno
import os
import shutil
import stat

from entropy.const import etpConst, const_debug_write, const_debug_enabled, \
    const_mkstemp
from entropy.client.mirrors import StatusInterface
from entropy.exceptions import InterruptError
from entropy.fetchers import UrlFetcher
from entropy.i18n import _
from entropy.output import red, darkred, blue, purple, darkgreen, brown
from entropy.security import Repository as RepositorySecurity

import entropy.dep
import entropy.tools

from .action import PackageAction


class _PackageFetchAction(PackageAction):
    """
    PackageAction used for package download.
    """

    NAME = "fetch"

    def __init__(self, entropy_client, package_match, opts = None):
        """
        Object constructor.
        """
        super(_PackageFetchAction, self).__init__(
            entropy_client, package_match, opts = opts)
        self._meta = None

    def finalize(self):
        """
        Finalize the object, release all its resources.
        """
        super(_PackageFetchAction, self).finalize()
        if self._meta is not None:
            meta = self._meta
            self._meta = None
            meta.clear()

    def metadata(self):
        """
        Return the package metadata dict object for manipulation.
        """
        return self._meta

    def package_path(self):
        """
        Return the path to the download package file.
        Please note that the path returned is only related to the main
        package tarball file, extra-downloads and debug packages are ignored.
        This method is mainly for PackageKit consumption.
        """
        return self._meta['pkgpath']

    def setup(self):
        """
        Setup the PackageAction.
        """
        if self._meta is not None:
            # already configured
            return

        metadata = {}
        splitdebug_metadata = self._get_splitdebug_metadata()
        metadata.update(splitdebug_metadata)

        metadata['fetch_abort_function'] = self._opts.get(
            'fetch_abort_function')

        # NOTE: if you want to implement download-to-dir feature in your
        # client, you've found what you were looking for.
        # fetch_path is the path where data should be downloaded
        # it overrides default path
        fetch_path = self._opts.get('fetch_path', None)
        if fetch_path is not None:
            if entropy.tools.is_valid_path(fetch_path):
                metadata['fetch_path'] = fetch_path

        # if splitdebug is enabled, check if it's also enabled
        # via package.splitdebug
        splitdebug = metadata['splitdebug']
        if splitdebug:
            splitdebug = self._package_splitdebug_enabled(
                self._package_match)

        repo = self._entropy.open_repository(self._repository_id)
        edelta_support = self._entropy.ClientSettings(
            )['misc']['edelta_support']
        metadata['edelta_support'] = edelta_support
        metadata['checksum'] = repo.retrieveDigest(self._package_id)
        sha1, sha256, sha512, gpg = repo.retrieveSignatures(
            self._package_id)
        signatures = {
            'sha1': sha1,
            'sha256': sha256,
            'sha512': sha512,
            'gpg': gpg,
        }
        metadata['signatures'] = signatures
        extra_download = repo.retrieveExtraDownload(self._package_id)
        if not splitdebug:
            extra_download = [x for x in extra_download if \
                x['type'] != "debug"]
        metadata['extra_download'] = extra_download
        metadata['download'] = repo.retrieveDownloadURL(
            self._package_id)

        # export main package download path to metadata
        # this is actually used by PackageKit backend in order
        # to signal downloaded package files
        metadata['pkgpath'] = self._get_download_path(
            metadata['download'], metadata)

        metadata['phases'] = []

        if not self._entropy._is_package_repository(self._repository_id):
            metadata['phases'].append(self._fetch_phase)

        self._meta = metadata

    def _run(self):
        """
        Execute the action. Return an exit status.
        """
        self.setup()

        exit_st = 0
        for method in self._meta['phases']:
            exit_st = method()
            if exit_st != 0:
                break
        return exit_st

    def _get_download_path(self, download, metadata):
        """
        Return proper Entropy package store path.
        """
        if 'fetch_path' in metadata:
            # only supported by fetch action, multifetch also unsupported
            pkg_disk_path = os.path.join(metadata['fetch_path'],
                os.path.basename(download))
        else:
            pkg_disk_path = self.get_standard_fetch_disk_path(download)
        return pkg_disk_path

    def _build_uris_list(self, original_repo, repository_id):
        """
        Build a list of possible download URIs for the given repository.
        Handle fallback to the original repository (the one originally
        containing the package).
        """
        avail_data = self._settings['repositories']['available']
        product = self._settings['repositories']['product']
        uris = []

        plain_packages = avail_data[repository_id]['plain_packages']
        for uri in plain_packages:
            expanded_uri = entropy.tools.expand_plain_package_mirror(
                uri, product, original_repo)
            uris.append(expanded_uri)

        uris.reverse()
        uris.extend(avail_data[repository_id]['packages'][::-1])

        return uris

    def _approve_edelta_unlocked(self, url, checksum, installed_url,
                                 installed_checksum, installed_download_path):
        """
        Approve Entropy package delta support for given url, checking if
        a previously fetched package is available.

        @return: edelta URL to download and previously downloaded package path
        or None if edelta is not available
        @rtype: tuple of strings or None
        """
        edelta_local_approved = False
        try:
            edelta_local_approved = entropy.tools.compare_md5(
                installed_download_path, installed_checksum)
        except (OSError, IOError) as err:
            const_debug_write(
                __name__, "_approve_edelta_unlocked, error: %s" % (err,))
            return

        if not edelta_local_approved:
            return

        hash_tag = installed_checksum + checksum
        edelta_file_name = entropy.tools.generate_entropy_delta_file_name(
            os.path.basename(installed_url),
            os.path.basename(url),
            hash_tag)
        edelta_url = os.path.join(
            os.path.dirname(url),
            etpConst['packagesdeltasubdir'],
            edelta_file_name)

        return edelta_url

    def _setup_differential_download(self, fetcher, url, resume,
                                     download_path, repository, package_id):
        """
        Setup differential download in case of URL supporting it.
        Internal function.

        @param fetcher: UrlFetcher or MultipleUrlFetcher class
        @param url: URL to check differential download against
        @type url: string
        @param resume: resume support
        @type resume: bool
        @param download_path: path where package file will be saved
        @type download_path: string
        @param repository: repository identifier belonging to package file
        @type repository: string
        @param package_id: package identifier belonging to repository identifier
        @type package_id: int
        """
        # no resume? no party?
        if not resume:
            const_debug_write(__name__,
                "_setup_differential_download(%s) %s" % (
                    download_path, "resume disabled"))
            return

        if not fetcher.supports_differential_download(url):
            # no differential download support
            const_debug_write(__name__,
                "_setup_differential_download(%s) %s" % (
                    url, "no differential download support"))
            return

        # this is the fetch path of the file that is going to be downloaded
        # not going to overwrite it if a file is located there because
        # user would want a resume for sure in first place
        if os.path.isfile(download_path):
            const_debug_write(__name__,
                "_setup_differential_download(%s) %s %s" % (
                    url, download_path,
                    "download path already exists, not overwriting"))
            return

        pkg_repo = self._entropy.open_repository(repository)
        keyslot = pkg_repo.retrieveKeySlot(package_id)
        if keyslot is None:
            # fucked up entry, not dealing with it here
            const_debug_write(__name__,
                "_setup_differential_download(%s) %s" % (
                    url, "key, slot fucked up"))
            return

        key, slot = keyslot
        inst_repo = self._entropy.installed_repository()
        with inst_repo.shared():

            pkg_ids = inst_repo.searchKeySlot(key, slot)
            if not pkg_ids:
                # not installed, nothing to use as diff download
                const_debug_write(__name__,
                    "_setup_differential_download(%s) %s" % (
                        url, "no installed packages"))
                return

            # grab the highest, we don't know if user was able to mess up
            # its installed packages repository
            pkg_id = max(pkg_ids)
            download_url = inst_repo.retrieveDownloadURL(pkg_id)
            installed_download_path = self.get_standard_fetch_disk_path(
                download_url)

        if installed_download_path == download_path:
            # collision between what we need locally and what we need
            # remotely, definitely differential download is not going
            # to help. Abort here.
            return

        # do not hold the lock on installed_download_path since it may
        # cause a deadlock, rather hold an exclusive lock on the temporary
        # file and be tolerant on failures on installed_download_path
        tmp_download_path = download_path + ".setup_differential_download"
        lock = None
        try:
            lock = self.path_lock(tmp_download_path)

            with lock.exclusive():
                self._setup_differential_download_internal(
                    tmp_download_path, download_path,
                    installed_download_path)

                try:
                    os.remove(tmp_download_path)
                except (OSError, IOError):
                    pass

        finally:
            if lock is not None:
                lock.close()

    def _setup_differential_download_internal(self, tmp_download_path,
                                              download_path,
                                              installed_download_path):
        """
        _setup_differential_download() assuming that the installed packages
        repository lock is held.
        """
        try:
            shutil.copyfile(installed_download_path, tmp_download_path)
        except (OSError, IOError, shutil.Error) as err:
            const_debug_write(
                __name__,
                "_setup_differential_download2(%s), %s copyfile error: %s" % (
                    installed_download_path, tmp_download_path, err))
            return False

        try:
            user = os.stat(installed_download_path)[stat.ST_UID]
            group = os.stat(installed_download_path)[stat.ST_GID]
            os.chown(download_path, user, group)
        except (OSError, IOError) as err:
            const_debug_write(
                __name__,
                "_setup_differential_download2(%s), chown error: %s" % (
                    installed_download_path, err))
            return False

        try:
            shutil.copystat(installed_download_path, tmp_download_path)
        except (OSError, IOError, shutil.Error) as err:
            const_debug_write(
                __name__,
                "_setup_differential_download2(%s), %s copystat error: %s" % (
                    installed_download_path, tmp_download_path, err))
            return False

        try:
            os.rename(tmp_download_path, download_path)
        except (OSError, IOError) as err:
            const_debug_write(
                __name__,
                "_setup_differential_download2(%s), %s rename error: %s" % (
                    installed_download_path, tmp_download_path, err))
            return False

        const_debug_write(
            __name__,
            "_setup_differential_download2(%s) copied to %s" % (
                installed_download_path, download_path))

        return True

    def _try_edelta_fetch(self, url, download_path, checksum, resume):

        # no edelta support enabled
        if not self._meta.get('edelta_support'):
            return 1, 0.0
        # edelta enabled?
        if not entropy.tools.is_entropy_delta_available():
            return 1, 0.0

        repo = self._entropy.open_repository(self._repository_id)
        inst_repo = self._entropy.installed_repository()
        with inst_repo.shared():

            key_slot = repo.retrieveKeySlotAggregated(self._package_id)
            if key_slot is None:
                # wtf corrupted entry, skip
                return 1, 0.0

            installed_package_id, _inst_rc = inst_repo.atomMatch(key_slot)
            if installed_package_id == -1:
                # package is not installed
                return 1, 0.0

            installed_url = inst_repo.retrieveDownloadURL(installed_package_id)
            installed_checksum = inst_repo.retrieveDigest(installed_package_id)
            installed_download_path = self.get_standard_fetch_disk_path(
                installed_url)

        if installed_download_path == download_path:
            # collision between what we need locally and what we need
            # remotely, definitely edelta fetch is not going to work.
            # Abort here.
            return 1, 0.0

        download_path_dir = os.path.dirname(download_path)
        try:
            os.makedirs(download_path_dir, 0o755)
        except OSError as err:
            if err.errno != errno.EEXIST:
                const_debug_write(
                    __name__,
                    "_try_edelta_fetch.makedirs, %s, error: %s" % (
                        download_path_dir, err))
                return -1, 0.0

        # installed_download_path is read in a fault-tolerant mode
        # so, there is no need for locking.
        edelta_download_path = download_path
        edelta_download_path += etpConst['packagesdeltaext']
        lock = None
        try:
            lock = self.path_lock(edelta_download_path)
            with lock.exclusive():

                edelta_url = self._approve_edelta_unlocked(
                    url, checksum, installed_url, installed_checksum,
                    installed_download_path)

                if edelta_url is None:
                    # edelta not available, give up
                    return 1, 0.0

                return self._try_edelta_fetch_unlocked(
                    edelta_url, edelta_download_path, download_path,
                    installed_download_path, resume)

        finally:
            if lock is not None:
                lock.close()

    def _try_edelta_fetch_unlocked(self, edelta_url, edelta_download_path,
                                   download_path, installed_download_path,
                                   resume):
        """
        _try_edelta_fetch(), assuming that the relevant file locks are held.
        """
        max_tries = 2
        edelta_approved = False
        data_transfer = 0
        download_plan = [(edelta_url, edelta_download_path) for _x in \
            range(max_tries)]

        delta_resume = resume
        fetch_abort_function = self._meta.get('fetch_abort_function')
        fetch_errors = (
            UrlFetcher.TIMEOUT_FETCH_ERROR,
            UrlFetcher.GENERIC_FETCH_ERROR,
            UrlFetcher.GENERIC_FETCH_WARN,
        )

        for delta_url, delta_save in download_plan:

            delta_fetcher = self._entropy._url_fetcher(delta_url,
                delta_save, resume = delta_resume,
                abort_check_func = fetch_abort_function)

            try:
                # make sure that we don't need to abort already
                # doing the check here avoids timeouts
                if fetch_abort_function != None:
                    fetch_abort_function()

                delta_checksum = delta_fetcher.download()
                data_transfer = delta_fetcher.get_transfer_rate()
                del delta_fetcher
            except (KeyboardInterrupt, InterruptError):
                return -100, data_transfer

            except NameError:
                raise

            except Exception:
                return -1, data_transfer

            if delta_checksum in fetch_errors:
                # make sure this points to hell
                delta_resume = False
                # retry
                continue

            # now check
            tmp_download_path = download_path + ".edelta_pkg_tmp"
            # yay, we can apply the delta and cook the new package file!
            try:
                entropy.tools.apply_entropy_delta(
                    installed_download_path,
                    delta_save, tmp_download_path)
            except IOError:
                # make sure this points to the hell
                delta_resume = False
                # retry
                try:
                    os.remove(tmp_download_path)
                except (OSError, IOError):
                    pass
                continue

            os.rename(tmp_download_path, download_path)
            edelta_approved = True
            break

        if edelta_approved:
            # we can happily return
            return 0, data_transfer
        # error, give up with the edelta stuff
        return 1, data_transfer

    def _download_file(self, url, download_path, digest = None,
                       resume = True, package_id = None,
                       repository_id = None):
        """
        Internal method. Try to download the package file.
        """

        def do_stfu_rm(xpath):
            try:
                os.remove(xpath)
            except OSError:
                pass

        def do_get_md5sum(path):
            try:
                return entropy.tools.md5sum(path)
            except IOError:
                return None
            except OSError:
                return None

        download_path_dir = os.path.dirname(download_path)
        try:
            os.makedirs(download_path_dir, 0o755)
        except OSError as err:
            if err.errno != errno.EEXIST:
                const_debug_write(
                    __name__,
                    "_download_file.makedirs, %s, error: %s" % (
                        download_path_dir, err))
                return -1, 0, False

        fetch_abort_function = self._meta.get('fetch_abort_function')
        existed_before = False
        if os.path.isfile(download_path) and os.path.exists(download_path):
            existed_before = True

        fetch_intf = self._entropy._url_fetcher(
            url, download_path, resume = resume,
            abort_check_func = fetch_abort_function)

        if (package_id is not None) and (repository_id is not None):
            self._setup_differential_download(
                self._entropy._url_fetcher, url,
                resume, download_path, repository_id, package_id)

        data_transfer = 0
        resumed = False
        try:
            # make sure that we don't need to abort already
            # doing the check here avoids timeouts
            if fetch_abort_function != None:
                fetch_abort_function()

            fetch_checksum = fetch_intf.download()
            data_transfer = fetch_intf.get_transfer_rate()
            resumed = fetch_intf.is_resumed()
        except (KeyboardInterrupt, InterruptError):
            return -100, data_transfer, resumed

        except NameError:
            raise

        except:
            if const_debug_enabled():
                self._entropy.output(
                    "fetch_file:",
                    importance = 1,
                    level = "warning",
                    header = red("   ## ")
                )
                entropy.tools.print_traceback()
            if (not existed_before) or (not resume):
                do_stfu_rm(download_path)
            return -1, data_transfer, resumed

        if fetch_checksum == UrlFetcher.GENERIC_FETCH_ERROR:
            # !! not found
            # maybe we already have it?
            # this handles the case where network is unavailable
            # but file is already downloaded
            fetch_checksum = do_get_md5sum(download_path)
            if (fetch_checksum != digest) or fetch_checksum is None:
                return -3, data_transfer, resumed

        elif fetch_checksum == UrlFetcher.TIMEOUT_FETCH_ERROR:
            # maybe we already have it?
            # this handles the case where network is unavailable
            # but file is already downloaded
            fetch_checksum = do_get_md5sum(download_path)
            if (fetch_checksum != digest) or fetch_checksum is None:
                return -4, data_transfer, resumed

        if digest and (fetch_checksum != digest):
            # not properly downloaded
            if (not existed_before) or (not resume):
                do_stfu_rm(download_path)
            return -2, data_transfer, resumed

        return 0, data_transfer, resumed

    def _download_package(self, package_id, repository_id, download,
                          download_path, checksum, resume = True):

        avail_data = self._settings['repositories']['available']
        excluded_data = self._settings['repositories']['excluded']
        repo = self._entropy.open_repository(repository_id)
        # grab original repo, if any and use it if available
        # this is done in order to support "equo repo merge" feature
        # allowing client-side repository package metadata moves.
        original_repo = repo.getInstalledPackageRepository(package_id)

        if (original_repo != repository_id) and (
                original_repo not in avail_data) and (
                    original_repo is not None):
            # build up a new uris list, at least try, hoping that
            # repository is just shadowing original_repo
            # for example: original_repo got copied to repository, without
            # copying packages, which would be useless. like it happens
            # with sabayon-weekly
            uris = self._build_uris_list(original_repo, repository_id)
        else:
            if original_repo in avail_data:
                uris = avail_data[original_repo]['packages'][::-1]
                if repository_id in avail_data:
                    uris += avail_data[repository_id]['packages'][::-1]
            elif original_repo in excluded_data:
                uris = excluded_data[original_repo]['packages'][::-1]
                if repository_id in avail_data:
                    uris += avail_data[repository_id]['packages'][::-1]
            else:
                uris = avail_data[repository_id]['packages'][::-1]

        remaining = set(uris)
        mirror_status = StatusInterface()

        mirrorcount = 0
        for uri in uris:

            if not remaining:
                # tried all the mirrors, quitting for error
                mirror_status.set_working_mirror(None)
                return 3

            mirror_status.set_working_mirror(uri)
            mirrorcount += 1
            mirror_count_txt = "( mirror #%s ) " % (mirrorcount,)
            url = uri + "/" + download

            # check if uri is sane
            if mirror_status.get_failing_mirror_status(uri) >= 30:
                # ohohoh!
                # set to 30 for convenience
                mirror_status.set_failing_mirror_status(uri, 30)
                mytxt = mirror_count_txt
                mytxt += blue(" %s: ") % (_("Mirror"),)
                mytxt += red(self._get_url_name(uri))
                mytxt += " - %s." % (_("maximum failure threshold reached"),)
                self._entropy.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = red("   ## ")
                )

                if mirror_status.get_failing_mirror_status(uri) == 30:
                    # put to 75 then decrement by 4 so we
                    # won't reach 30 anytime soon ahahaha
                    mirror_status.add_failing_mirror(uri, 45)
                elif mirror_status.get_failing_mirror_status(uri) > 31:
                    # now decrement each time this point is reached,
                    # if will be back < 30, then equo will try to use it again
                    mirror_status.add_failing_mirror(uri, -4)
                else:
                    # put to 0 - reenable mirror, welcome back uri!
                    mirror_status.set_failing_mirror_status(uri, 0)

                remaining.discard(uri)
                continue

            do_resume = resume
            timeout_try_count = 50

            while True:

                txt = mirror_count_txt
                txt += blue("%s: ") % (_("Downloading from"),)
                txt += red(self._get_url_name(uri))
                self._entropy.output(
                    txt,
                    importance = 1,
                    level = "warning",
                    header = red("   ## ")
                )

                resumed = False
                exit_st, data_transfer = self._try_edelta_fetch(
                    url, download_path, checksum, do_resume)
                if exit_st > 0:
                    # fallback to package file download
                    exit_st, data_transfer, resumed = self._download_file(
                        url,
                        download_path,
                        package_id = package_id,
                        repository_id = repository_id,
                        digest = checksum,
                        resume = do_resume
                    )

                if exit_st == 0:
                    txt = mirror_count_txt
                    txt += "%s: " % (
                        blue(_("Successfully downloaded from")),
                    )
                    txt += red(self._get_url_name(uri))
                    human_bytes = entropy.tools.bytes_into_human(
                        data_transfer)
                    txt += " %s %s/%s" % (_("at"),
                        human_bytes, _("second"),)
                    self._entropy.output(
                        txt,
                        importance = 1,
                        level = "info",
                        header = red("   ## ")
                    )

                    mirror_status.set_working_mirror(None)
                    return 0

                elif resumed and (exit_st not in (-3, -4, -100,)):
                    do_resume = False
                    continue

                error_message = mirror_count_txt
                error_message += blue("%s: %s") % (
                    _("Error downloading from"),
                    red(self._get_url_name(uri)),
                )

                # something bad happened
                if exit_st == -1:
                    error_message += " - %s." % (
                        _("file not available on this mirror"),)

                elif exit_st == -2:
                    mirror_status.add_failing_mirror(uri, 1)
                    error_message += " - %s." % (_("wrong checksum"),)

                    # If file is fetched (with no resume) and its
                    # complete better to enforce resume to False.
                    if (data_transfer < 1) and do_resume:
                        error_message += " %s." % (
                            _("Disabling resume"),)
                        do_resume = False
                        continue

                elif exit_st == -3:
                    mirror_status.add_failing_mirror(uri, 3)
                    error_message += " - %s." % (_("not found"),)

                elif exit_st == -4: # timeout!
                    timeout_try_count -= 1
                    if timeout_try_count > 0:
                        error_message += " - %s." % (
                            _("timeout, retrying on this mirror"),)
                    else:
                        error_message += " - %s." % (
                            _("timeout, giving up"),)

                elif exit_st == -100:
                    error_message += " - %s." % (
                        _("discarded download"),)
                else:
                    mirror_status.add_failing_mirror(uri, 5)
                    error_message += " - %s." % (_("unknown reason"),)

                self._entropy.output(
                    error_message,
                    importance = 1,
                    level = "warning",
                    header = red("   ## ")
                )

                if exit_st == -4: # timeout
                    if timeout_try_count > 0:
                        continue

                elif exit_st == -100: # user discarded fetch
                    mirror_status.set_working_mirror(None)
                    return 1

                remaining.discard(uri)
                # make sure we don't have nasty issues
                if not remaining:
                    mirror_status.set_working_mirror(None)
                    return 3

                break

        mirror_status.set_working_mirror(None)
        return 0

    def _fetch_phase(self):
        """
        Execute the package fetch phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Downloading"),
            os.path.basename(self._meta['download']),
        )
        self._entropy.set_title(xterm_title)

        def _download_error(exit_st):
            txt = "%s. %s: %s" % (
                red(_("Package cannot be downloaded. "
                      "Try to update repositories")),
                blue(_("Error")),
                exit_st,
            )
            self._entropy.output(
                txt,
                importance = 1,
                level = "error",
                header = darkred("   ## ")
            )

        def _fetch(path, download, checksum):
            txt = "%s: %s" % (
                blue(_("Downloading")),
                red(os.path.basename(download)),)
            self._entropy.output(
                txt,
                importance = 1,
                level = "info",
                header = red("   ## ")
            )
            return self._download_package(
                self._package_id,
                self._repository_id,
                download,
                path,
                checksum
            )

        locks = []
        try:
            download_path = self._get_download_path(
                self._meta['download'], self._meta)
            lock = self.path_lock(download_path)
            locks.append(lock)

            with lock.exclusive():

                verify_st = 1
                if self._stat_path(download_path):
                    verify_st = self._match_checksum(
                        download_path,
                        self._repository_id,
                        self._meta['checksum'],
                        self._meta['signatures'])

                if verify_st != 0:
                    download_st = _fetch(
                        download_path,
                        self._meta['download'],
                        self._meta['checksum'])

                    if download_st == 0:
                        verify_st = self._match_checksum(
                            download_path,
                            self._repository_id,
                            self._meta['checksum'],
                            self._meta['signatures'])

                if verify_st != 0:
                    _download_error(verify_st)
                    return verify_st

            for extra_download in self._meta['extra_download']:

                download_path = self._get_download_path(
                    extra_download['download'], self._meta)
                signatures = {
                    'sha1': extra_download['sha1'],
                    'sha256': extra_download['sha256'],
                    'sha512': extra_download['sha512'],
                    'gpg': extra_download['gpg'],
                }

                extra_lock = self.path_lock(download_path)
                locks.append(extra_lock)

                with extra_lock.exclusive():

                    verify_st = 1
                    if self._stat_path(download_path):
                        verify_st = self._match_checksum(
                            download_path,
                            self._repository_id,
                            extra_download['md5'],
                            signatures)

                    if verify_st != 0:
                        download_st = _fetch(
                            download_path,
                            extra_download['download'],
                            extra_download['md5'])

                        if download_st == 0:
                            verify_st = self._match_checksum(
                                download_path,
                                self._repository_id,
                                extra_download['md5'],
                                signatures)

                    if verify_st != 0:
                        _download_error(verify_st)
                        return verify_st

            return 0

        finally:
            for l in locks:
                l.close()

    def _match_checksum(self, download_path, repository_id,
                        checksum, signatures):
        """
        Verify package checksum and return an exit status code.
        """
        download_path_mtime = download_path + etpConst['packagemtimefileext']

        misc_settings = self._entropy.ClientSettings()['misc']
        enabled_hashes = misc_settings['packagehashes']

        def do_mtime_validation():
            enc = etpConst['conf_encoding']
            try:
                with codecs.open(download_path_mtime,
                                 "r", encoding=enc) as mt_f:
                    stored_mtime = mt_f.read().strip()
            except (OSError, IOError) as err:
                if err.errno != errno.ENOENT:
                    raise
                return 1

            try:
                cur_mtime = str(os.path.getmtime(download_path))
            except (OSError, IOError) as err:
                if err.errno != errno.ENOENT:
                    raise
                return 2

            if cur_mtime == stored_mtime:
                return 0
            return 1

        def do_store_mtime():
            enc = etpConst['conf_encoding']
            try:
                with codecs.open(download_path_mtime,
                                 "w", encoding=enc) as mt_f:
                    cur_mtime = str(os.path.getmtime(download_path))
                    mt_f.write(cur_mtime)
            except (OSError, IOError) as err:
                if err.errno != errno.ENOENT:
                    raise

        def do_compare_gpg(pkg_path, hash_val):

            try:
                repo_sec = self._entropy.RepositorySecurity()
            except RepositorySecurity.GPGServiceNotAvailable:
                return None

            # check if we have repository pubkey
            try:
                if not repo_sec.is_pubkey_available(repository_id):
                    return None
            except repo_sec.KeyExpired:
                # key is expired
                return None

            # write gpg signature to disk for verification
            tmp_fd, tmp_path = const_mkstemp(prefix="do_compare_gpg")
            with os.fdopen(tmp_fd, "w") as tmp_f:
                tmp_f.write(hash_val)

            try:
                # actually verify
                valid, err_msg = repo_sec.verify_file(
                    repository_id, pkg_path, tmp_path)
            finally:
                os.remove(tmp_path)

            if valid:
                return True

            if err_msg:
                self._entropy.output(
                    "%s: %s, %s" % (
                        darkred(_("Package signature verification error for")),
                        purple("GPG"),
                        err_msg,
                    ),
                    importance = 0,
                    level = "error",
                    header = darkred("   ## ")
                )
            return False

        signature_vry_map = {
            'sha1': entropy.tools.compare_sha1,
            'sha256': entropy.tools.compare_sha256,
            'sha512': entropy.tools.compare_sha512,
            'gpg': do_compare_gpg,
        }

        def do_signatures_validation(signatures):
            # check signatures, if available
            if isinstance(signatures, dict):
                for hash_type in sorted(signatures):

                    hash_val = signatures[hash_type]
                    # NOTE: workaround bug on unreleased
                    # entropy versions
                    if hash_val in signatures:
                        continue
                    if hash_val is None:
                        continue
                    if hash_type not in enabled_hashes:
                        self._entropy.output(
                            "%s %s" % (
                                purple(hash_type.upper()),
                                darkgreen(_("disabled")),
                            ),
                            importance = 0,
                            level = "info",
                            header = "      : "
                        )
                        continue

                    cmp_func = signature_vry_map.get(hash_type)
                    if cmp_func is None:
                        continue

                    down_name = os.path.basename(download_path)

                    valid = cmp_func(download_path, hash_val)
                    if valid is None:
                        self._entropy.output(
                            "[%s] %s '%s' %s" % (
                                brown(down_name),
                                darkred(_("Package signature verification")),
                                purple(hash_type.upper()),
                                darkred(_("temporarily unavailable")),
                            ),
                            importance = 0,
                            level = "warning",
                            header = darkred("   ## ")
                        )
                        continue

                    if not valid:
                        self._entropy.output(
                            "[%s] %s: %s %s" % (
                                brown(down_name),
                                darkred(_("Package signature")),
                                purple(hash_type.upper()),
                                darkred(_("does not match the recorded one")),
                            ),
                            importance = 0,
                            level = "error",
                            header = darkred("   ## ")
                        )
                        return 1

                    self._entropy.output(
                        "[%s] %s %s" % (
                            brown(down_name),
                            purple(hash_type.upper()),
                            darkgreen(_("validated")),
                        ),
                        importance = 0,
                        level = "info",
                        header = "      : "
                    )

            return 0

        self._entropy.output(
            blue(_("Checking package checksum...")),
            importance = 0,
            level = "info",
            header = red("   ## ")
        )

        download_name = os.path.basename(download_path)
        valid_checksum = False
        try:
            valid_checksum = entropy.tools.compare_md5(download_path, checksum)
        except (OSError, IOError) as err:
            valid_checksum = False
            const_debug_write(
                __name__,
                "_match_checksum: %s checksum validation error: %s" % (
                    download_path, err))

            txt = "%s: %s, %s" % (
                red(_("Checksum validation error")),
                blue(download_name),
                err,
            )
            self._entropy.output(
                txt,
                importance = 1,
                level = "error",
                header = darkred("   ## ")
            )
            return 1

        if not valid_checksum:
            txt = "%s: %s" % (
                red(_("Invalid checksum")),
                blue(download_name),
            )
            self._entropy.output(
                txt,
                importance = 1,
                level = "warning",
                header = red("   ## ")
            )
            return 1

        # check if package has been already checked
        validated = True
        if do_mtime_validation() != 0:
            validated = do_signatures_validation(signatures) == 0

        if not validated:
            txt = "%s: %s" % (
                red(_("Invalid signatures")),
                blue(download_name),
            )
            self._entropy.output(
                txt,
                importance = 1,
                level = "warning",
                header = red("   ## ")
            )
            return 1

        do_store_mtime()
        return 0
