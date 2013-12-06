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
from entropy.fetchers import UrlFetcher
from entropy.i18n import _
from entropy.output import red, darkred, blue, purple, darkgreen
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
        metadata['atom'] = repo.retrieveAtom(self._package_id)
        metadata['slot'] = repo.retrieveSlot(self._package_id)

        inst_repo = self._entropy.installed_repository()
        metadata['installed_package_id'], _inst_rc = inst_repo.atomMatch(
            entropy.dep.dep_getkey(metadata['atom']),
            matchSlot = metadata['slot'])

        cl_id = etpConst['system_settings_plugins_ids']['client_plugin']
        edelta_support = self._settings[cl_id]['misc']['edelta_support']
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
        metadata['pkgpath'] = self._get_fetch_disk_path(
            metadata['download'], metadata)

        metadata['phases'] = []

        if not self._repository_id.endswith(etpConst['packagesext']):

            dl_check = self._check_package_path_download(
                metadata['download'], None, _metadata = metadata)
            dl_fetch = dl_check < 0

            if not dl_fetch:
                for extra_download in metadata['extra_download']:
                    dl_check = self._check_package_path_download(
                        extra_download['download'], None, _metadata = metadata)
                    if dl_check < 0:
                        # dl_check checked again right below
                        break

            if dl_check < 0:
                metadata['phases'].append(self._fetch)

            metadata['phases'].append(self._checksum)

        def _check_matching_size(download, size):
            d_path = self._get_fetch_disk_path(download, metadata)
            try:
                st = os.stat(d_path)
                return size == st.st_size
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise
                return False

        matching_size = _check_matching_size(metadata['download'],
            repo.retrieveSize(self._package_id))
        if matching_size:
            for extra_download in metadata['extra_download']:
                matching_size = _check_matching_size(
                    extra_download['download'],
                    extra_download['size'])
                if not matching_size:
                    break

        # downloading binary package
        # if file exists, first checksum then fetch
        if matching_size:
            metadata['phases'].reverse()

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

    def _get_fetch_disk_path(self, download, metadata):
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

    def _check_package_path_download(self, download, checksum,
                                     _metadata = None):
        """
        Internal function that verifies if a package tarball is already
        available locally and quickly computes its md5. Please note that
        stronger crypto hash functions are used during the real package
        validation phase.
        """
        if _metadata is None:
            _metadata = self._meta

        pkg_path = self._get_fetch_disk_path(download, _metadata)

        if not os.path.isfile(pkg_path):
            return -1
        if checksum is None:
            return 0

        if entropy.tools.compare_md5(pkg_path, checksum):
            return 0
        return -2

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

    def _approve_edelta(self, url, installed_package_id, package_digest):
        """
        Approve Entropy package delta support for given url, checking if
        a previously fetched package is available.

        @return: edelta URL to download and previously downloaded package path
        or None if edelta is not available
        @rtype: tuple of strings or None
        """
        inst_repo = self._entropy.installed_repository()
        download_url = inst_repo.retrieveDownloadURL(installed_package_id)
        installed_digest = inst_repo.retrieveDigest(installed_package_id)
        installed_fetch_path = self._get_fetch_disk_path(
            download_url, self._meta)

        edelta_local_approved = False
        try:
            edelta_local_approved = entropy.tools.compare_md5(
                installed_fetch_path, installed_digest)
        except (OSError, IOError) as err:
            const_debug_write(
                __name__, "_approve_edelta, error: %s" % (err,))
            return

        if edelta_local_approved:
            hash_tag = installed_digest + package_digest
            edelta_file_name = entropy.tools.generate_entropy_delta_file_name(
                os.path.basename(download_url),
                os.path.basename(url),
                hash_tag)
            edelta_url = os.path.join(
                os.path.dirname(url),
                etpConst['packagesdeltasubdir'],
                edelta_file_name)

            return edelta_url, installed_fetch_path

    def _setup_differential_download(self, fetcher, url, resume,
                                     fetch_path, repository, package_id):
        """
        Setup differential download in case of URL supporting it.
        Internal function.

        @param fetcher: UrlFetcher or MultipleUrlFetcher class
        @param url: URL to check differential download against
        @type url: string
        @param resume: resume support
        @type resume: bool
        @param fetch_path: path where package file will be saved
        @type fetch_path: string
        @param repository: repository identifier belonging to package file
        @type repository: string
        @param package_id: package identifier belonging to repository identifier
        @type package_id: int
        """
        # no resume? no party?
        if not resume:
            const_debug_write(__name__,
                "_setup_differential_download(%s) %s" % (
                    url, "resume disabled"))
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
        if os.path.isfile(fetch_path):
            const_debug_write(__name__,
                "_setup_differential_download(%s) %s" % (
                    url, "fetch path already exists, not overwriting"))
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
        installed_fetch_path = self._get_fetch_disk_path(
            download_url, self._meta)

        try:
            shutil.copyfile(installed_fetch_path, fetch_path)
        except (OSError, IOError, shutil.Error) as err:
            const_debug_write(
                __name__,
                "_setup_differential_download(%s), copyfile error: %s" % (
                    url, err))
            try:
                os.remove(fetch_path)
            except OSError:
                pass
            return

        try:
            user = os.stat(installed_fetch_path)[stat.ST_UID]
            group = os.stat(installed_fetch_path)[stat.ST_GID]
            os.chown(fetch_path, user, group)
        except (OSError, IOError) as err:
            const_debug_write(
                __name__,
                "_setup_differential_download(%s), chown error: %s" % (
                    url, err))
            return

        try:
            shutil.copystat(installed_fetch_path, fetch_path)
        except (OSError, IOError, shutil.Error) as err:
            const_debug_write(
                __name__,
                "_setup_differential_download(%s), copystat error: %s" % (
                    url, err))
            return

        const_debug_write(
            __name__,
            "_setup_differential_download(%s) copied to %s" % (
                url, fetch_path))

    def _try_edelta_fetch(self, installed_package_id, url, save_path,
                          checksum, resume):

        # no edelta support enabled
        if not self._meta.get('edelta_support'):
            return 1, 0.0
        # edelta enabled?
        if not entropy.tools.is_entropy_delta_available():
            return 1, 0.0

        # fresh install, cannot fetch edelta, edelta only works for installed
        # packages, by design.
        if installed_package_id is None or installed_package_id == -1:
            return 1, 0.0

        edelta_approve = self._approve_edelta(url, installed_package_id,
            checksum)

        if edelta_approve is None:
            # edelta not available, give up
            return 1, 0.0
        edelta_url, installed_fetch_path = edelta_approve

        # check if edelta file is available online
        edelta_save_path = save_path + etpConst['packagesdeltaext']

        max_tries = 2
        edelta_approved = False
        data_transfer = 0
        download_plan = [(edelta_url, edelta_save_path) for _x in \
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
            except KeyboardInterrupt:
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
            tmp_save_path = save_path + ".edelta_pkg_tmp"
            # yay, we can apply the delta and cook the new package file!
            try:
                entropy.tools.apply_entropy_delta(installed_fetch_path,
                    delta_save, tmp_save_path)
            except IOError:
                # make sure this points to the hell
                delta_resume = False
                # retry
                try:
                    os.remove(tmp_save_path)
                except (OSError, IOError):
                    pass
                continue

            os.rename(tmp_save_path, save_path)
            edelta_approved = True
            break

        if edelta_approved:
            # we can happily return
            return 0, data_transfer
        # error, give up with the edelta stuff
        return 1, data_transfer

    def _fetch_file(self, url, save_path, digest = None, resume = True,
                    download = None, package_id = None, repository = None,
                    installed_package_id = None):
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

        fetch_abort_function = self._meta.get('fetch_abort_function')
        filepath_dir = os.path.dirname(save_path)

        if not os.path.isdir(os.path.realpath(filepath_dir)):
            try:
                os.remove(filepath_dir)
            except OSError as err:
                const_debug_write(__name__,
                    "_fetch_file.remove, %s, error: %s" % (
                        filepath_dir, err))
            try:
                os.makedirs(filepath_dir, 0o755)
            except OSError as err:
                const_debug_write(__name__,
                    "_fetch_file.makedirs, %s, error: %s" % (
                        filepath_dir, err))
                return -1, 0, False

        exit_st, data_transfer = self._try_edelta_fetch(
            installed_package_id, url, save_path,
            digest, resume)
        if exit_st == 0:
            return exit_st, data_transfer, False
        elif exit_st < 0: # < 0 errors are unrecoverable
            return exit_st, data_transfer, False
        # otherwise, just fallback to package download

        existed_before = False
        if os.path.isfile(save_path) and os.path.exists(save_path):
            existed_before = True

        fetch_intf = self._entropy._url_fetcher(
            url, save_path, resume = resume,
            abort_check_func = fetch_abort_function)
        if (download is not None) and (package_id is not None) and \
            (repository is not None) and (exit_st == 0):
            fetch_path = self._get_fetch_disk_path(download, self._meta)
            self._setup_differential_download(
                self._entropy._url_fetcher, url,
                resume, fetch_path, repository, package_id)

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
        except KeyboardInterrupt:
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
                do_stfu_rm(save_path)
            return -1, data_transfer, resumed

        if fetch_checksum == UrlFetcher.GENERIC_FETCH_ERROR:
            # !! not found
            # maybe we already have it?
            # this handles the case where network is unavailable
            # but file is already downloaded
            fetch_checksum = do_get_md5sum(save_path)
            if (fetch_checksum != digest) or fetch_checksum is None:
                return -3, data_transfer, resumed

        elif fetch_checksum == UrlFetcher.TIMEOUT_FETCH_ERROR:
            # maybe we already have it?
            # this handles the case where network is unavailable
            # but file is already downloaded
            fetch_checksum = do_get_md5sum(save_path)
            if (fetch_checksum != digest) or fetch_checksum is None:
                return -4, data_transfer, resumed

        if digest and (fetch_checksum != digest):
            # not properly downloaded
            if (not existed_before) or (not resume):
                do_stfu_rm(save_path)
            return -2, data_transfer, resumed

        return 0, data_transfer, resumed

    def _download_package(self, package_id, repository_id, installed_package_id,
                          download, save_path, checksum, resume = True):

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

                exit_st, data_transfer, resumed = self._fetch_file(
                    url,
                    save_path,
                    download = download,
                    package_id = package_id,
                    repository = repository_id,
                    digest = checksum,
                    resume = do_resume,
                    installed_package_id = installed_package_id
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

    def _fetch(self):
        """
        Execute the package fetch phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Fetching"),
            os.path.basename(self._meta['download']),
        )
        self._entropy.set_title(xterm_title)

        def _fetch(download, checksum):
            txt = "%s: %s" % (
                blue(_("Downloading")),
                red(os.path.basename(download)),)
            self._entropy.output(
                txt,
                importance = 1,
                level = "info",
                header = red("   ## ")
            )
            pkg_disk_path = self._get_fetch_disk_path(download, self._meta)
            return self._download_package(
                self._package_id,
                self._repository_id,
                self._meta['installed_package_id'],
                download,
                pkg_disk_path,
                checksum
            )

        exit_st = _fetch(self._meta['download'], self._meta['checksum'])
        if exit_st == 0:
            # go ahead with extra_download
            for extra_download in self._meta['extra_download']:
                exit_st = _fetch(extra_download['download'],
                    extra_download['md5'])
                if exit_st != 0:
                    break

        if exit_st != 0:
            txt = "%s. %s: %s" % (
                red(_("Package cannot be fetched. Try to update repositories")),
                blue(_("Error")),
                exit_st,
            )
            self._entropy.output(
                txt,
                importance = 1,
                level = "error",
                header = darkred("   ## ")
            )

        return exit_st

    def _match_checksum(self, package_id, repository, installed_package_id,
                        checksum, download, signatures):
        """
        Verify package checksum and return an exit status code.
        """
        misc_settings = self._entropy.ClientSettings()['misc']
        enabled_hashes = misc_settings['packagehashes']

        pkg_disk_path = self._get_fetch_disk_path(download, self._meta)
        pkg_disk_path_mtime = pkg_disk_path + etpConst['packagemtimefileext']

        def do_mtime_validation():
            enc = etpConst['conf_encoding']
            try:
                with codecs.open(pkg_disk_path_mtime,
                                 "r", encoding=enc) as mt_f:
                    stored_mtime = mt_f.read().strip()
            except (OSError, IOError) as err:
                if err.errno != errno.ENOENT:
                    raise
                return 1

            try:
                cur_mtime = str(os.path.getmtime(pkg_disk_path))
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
                with codecs.open(pkg_disk_path_mtime,
                                 "w", encoding=enc) as mt_f:
                    cur_mtime = str(os.path.getmtime(pkg_disk_path))
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
                if not repo_sec.is_pubkey_available(repository):
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
                    repository, pkg_path, tmp_path)
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

                    self._entropy.output(
                        "%s: %s" % (
                            blue(_("Checking package signature")),
                            purple(hash_type.upper()),
                        ),
                        importance = 0,
                        level = "info",
                        header = red("   ## "),
                        back = True
                    )

                    valid = cmp_func(pkg_disk_path, hash_val)
                    if valid is None:
                        self._entropy.output(
                            "%s '%s' %s" % (
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
                            "%s: %s %s" % (
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
                        "%s %s" % (
                            purple(hash_type.upper()),
                            darkgreen(_("matches")),
                        ),
                        importance = 0,
                        level = "info",
                        header = "      : "
                    )

            return 0

        dlcount = 0
        match = False
        max_dlcount = 5

        while dlcount <= max_dlcount:

            self._entropy.output(
                blue(_("Checking package checksum...")),
                importance = 0,
                level = "info",
                header = red("   ## "),
                back = True
            )

            dlcheck = self._check_package_path_download(
                download, checksum)
            if dlcheck == 0:
                basef = os.path.basename(download)
                self._entropy.output(
                    "%s: %s" % (
                        blue(_("Package checksum matches")),
                        darkgreen(basef),
                    ),
                    importance = 0,
                    level = "info",
                    header = red("   ## ")
                )

                # check if package has been already checked
                dlcheck = do_mtime_validation()
                if dlcheck != 0:
                    dlcheck = do_signatures_validation(signatures)

                if dlcheck == 0:
                    do_store_mtime()
                    match = True
                    break # file downloaded successfully

            if dlcheck != 0:
                dlcount += 1
                mytxt = _("Checksum does not match. Download attempt #%s") % (
                    dlcount,
                )
                self._entropy.output(
                    darkred(mytxt),
                    importance = 0,
                    level = "warning",
                    header = darkred("   ## ")
                )

                # Unfortunately, disabling resume makes possible to recover
                # from bad download data. trying to resume would do more harm
                # than good in the majority of cases.
                fetch = self._download_package(
                    package_id,
                    repository,
                    installed_package_id,
                    download,
                    pkg_disk_path,
                    checksum,
                    resume = False
                )

                if fetch != 0:
                    self._entropy.output(
                        blue(_("Cannot properly fetch package! Quitting.")),
                        importance = 0,
                        level = "error",
                        header = darkred("   ## ")
                    )
                    return fetch

                # package is fetched, let's loop one more time
                # to make sure to run all the checksum checks
                continue

        if not match:
            txt = _("Cannot fetch package or checksum does not match")
            txt2 = _("Try to download latest repositories")
            for txt in (txt, txt2,):
                self._entropy.output(
                    "%s." % (
                        blue(txt),
                    ),
                    importance = 0,
                    level = "info",
                    header = red("   ## ")
                )
            return 1

        return 0

    def _checksum(self):
        """
        Execute the package checksum validation phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Verifying"),
            os.path.basename(self._meta['download']),
        )
        self._entropy.set_title(xterm_title)

        exit_st = self._match_checksum(
            self._package_id,
            self._repository_id,
            self._meta['installed_package_id'],
            self._meta['checksum'],
            self._meta['download'],
            self._meta['signatures'])
        if exit_st != 0:
            return exit_st

        for extra_download in self._meta['extra_download']:
            download = extra_download['download']
            checksum = extra_download['md5']
            signatures = {
                'sha1': extra_download['sha1'],
                'sha256': extra_download['sha256'],
                'sha512': extra_download['sha512'],
                'gpg': extra_download['gpg'],
            }
            exit_st = self._match_checksum(
                self._package_id,
                self._repository_id,
                self._meta['installed_package_id'],
                checksum,
                download, signatures)
            if exit_st != 0:
                return exit_st

        return 0
