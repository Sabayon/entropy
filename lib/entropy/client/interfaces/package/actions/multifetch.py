# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
import contextlib
import errno
import os
import threading

from entropy.const import etpConst, const_setup_perms, const_mkstemp
from entropy.client.mirrors import StatusInterface
from entropy.exceptions import InterruptError
from entropy.fetchers import UrlFetcher
from entropy.output import blue, darkblue, bold, red, darkred, brown, darkgreen
from entropy.i18n import _, ngettext

import entropy.dep
import entropy.tools


from .fetch import _PackageFetchAction


class _PackageMultiFetchAction(_PackageFetchAction):
    """
    PackageAction used for package source code download.

    As opposed to the other PackageAction classes, this class
    expects a list of package matches instead of just one.
    """

    NAME = "multi_fetch"

    def __init__(self, entropy_client, package_matches, opts = None):
        """
        Object constructor.
        """
        super(_PackageMultiFetchAction, self).__init__(
            entropy_client, (None, None), opts = opts)

        self._package_matches = package_matches
        self._meta = None

    def finalize(self):
        """
        Finalize the object, release all its resources.
        """
        super(_PackageMultiFetchAction, self).finalize()
        if self._meta is not None:
            meta = self._meta
            self._meta = None
            meta.clear()

    def metadata(self):
        """
        Return the package metadata dict object for manipulation.
        """
        return self._meta

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

        misc_settings = self._entropy.ClientSettings()['misc']
        metadata['edelta_support'] = misc_settings['edelta_support']

        metadata['matches'] = self._package_matches

        download_list = []

        for package_id, repository_id in self._package_matches:

            if self._entropy._is_package_repository(repository_id):
                continue

            repo = self._entropy.open_repository(repository_id)
            download = repo.retrieveDownloadURL(package_id)
            digest = repo.retrieveDigest(package_id)
            sha1, sha256, sha512, gpg = repo.retrieveSignatures(package_id)
            extra_downloads = repo.retrieveExtraDownload(package_id)

            signatures = {
                'sha1': sha1,
                'sha256': sha256,
                'sha512': sha512,
                'gpg': gpg,
            }

            obj = (package_id, repository_id, download, digest, signatures)
            download_list.append(obj)

            splitdebug = metadata['splitdebug']
            # if splitdebug is enabled, check if it's also enabled
            # via package.splitdebug
            if splitdebug:
                splitdebug = self._package_splitdebug_enabled(
                    (package_id, repository_id))

            if not splitdebug:
                extra_downloads = [
                    x for x in extra_downloads if x['type'] != "debug"]

            for extra_download in extra_downloads:
                download = extra_download['download']
                digest = extra_download['md5']
                signatures = {
                    'sha1': extra_download['sha1'],
                    'sha256': extra_download['sha256'],
                    'sha512': extra_download['sha512'],
                    'gpg': extra_download['gpg'],
                }

                obj = (package_id, repository_id, download, digest, signatures)
                download_list.append(obj)

        metadata['multi_fetch_list'] = download_list

        metadata['phases'] = []
        if metadata['multi_fetch_list']:
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

    def _setup_url_directories(self, url_data):
        """
        Create the directories needed to download the files in url_data.
        """
        for _pkg_id, _repository_id, _url, dest_path, _cksum, _sig in url_data:
            dest_dir = os.path.dirname(dest_path)
            try:
                os.makedirs(dest_dir, 0o775)
                const_setup_perms(dest_dir, etpConst['entropygid'])
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise

    def _try_edelta_multifetch(self, url_data, resume):
        """
        Attempt to download and use the edelta file.
        """
        # no edelta support enabled
        if not self._meta.get('edelta_support'):
            return [], 0.0, 0

        if not entropy.tools.is_entropy_delta_available():
            return [], 0.0, 0

        self._setup_url_directories(url_data)

        edelta_approvals = []
        inst_repo = self._entropy.installed_repository()
        with inst_repo.shared():

            for (pkg_id, repository_id, url, download_path,
                 cksum, signs) in url_data:

                repo = self._entropy.open_repository(repository_id)
                if cksum is None:
                    # cannot setup edelta without checksum, get from repository
                    cksum = repo.retrieveDigest(pkg_id)
                    if cksum is None:
                        # still nothing
                        continue

                key_slot = repo.retrieveKeySlotAggregated(pkg_id)
                if key_slot is None:
                    # wtf corrupted entry, skip
                    continue

                installed_package_id, _inst_rc = inst_repo.atomMatch(key_slot)
                if installed_package_id == -1:
                    # package is not installed
                    continue

                installed_url = inst_repo.retrieveDownloadURL(
                    installed_package_id)
                installed_checksum = inst_repo.retrieveDigest(
                    installed_package_id)
                installed_download_path = self.get_standard_fetch_disk_path(
                    installed_url)

                if installed_download_path == download_path:
                    # collision between what we need locally and what we need
                    # remotely, definitely edelta fetch is not going to work.
                    # Abort here.
                    continue

                edelta_approvals.append(
                    (pkg_id, repository_id,
                     url, cksum, signs, download_path, installed_url,
                     installed_checksum, installed_download_path))

        if not edelta_approvals:
            return [], 0.0, 0

        url_path_list = []
        url_data_map = {}
        url_data_map_idx = 0

        for tup in edelta_approvals:

            (pkg_id, repository_id, url,
             cksum, signs, download_path, installed_url,
             installed_checksum, installed_download_path) = tup

            # installed_download_path is read in a fault-tolerant mode
            # so, there is no need for locking.
            edelta_download_path = download_path
            edelta_download_path += etpConst['packagesdeltaext']

            edelta_url = self._approve_edelta_unlocked(
                url, cksum, installed_url, installed_checksum,
                installed_download_path)
            if edelta_url is None:
                # no edelta support
                continue

            key = (edelta_url, edelta_download_path)

            url_path_list.append(key)
            url_data_map_idx += 1
            url_data_map[url_data_map_idx] = (
                pkg_id, repository_id, url,
                download_path, cksum, signs, edelta_url,
                edelta_download_path, installed_download_path)

        if not url_path_list:
            # no martini, no party!
            return [], 0.0, 0

        return self._try_edelta_multifetch_internal(
            url_path_list, url_data_map, resume)

    def _try_edelta_multifetch_internal(self, url_path_list,
                                        url_data_map, resume):
        """
        _try_edelta_multifetch(), assuming that the relevant file locks
        are held.
        """
        @contextlib.contextmanager
        def download_context(path):
            lock = None
            try:
                lock = self.path_lock(path)
                with lock.exclusive():
                    yield
            finally:
                if lock is not None:
                    lock.close()

        def pre_download_hook(path, _download_id):
            # assume that, if path is available, it's been
            # downloaded already. checksum verification will
            # happen afterwards.
            if self._stat_path(path):
                # this is not None and not an established
                # UrlFetcher return code code
                return self

        fetch_abort_function = self._meta.get('fetch_abort_function')
        fetch_intf = self._entropy._multiple_url_fetcher(
            url_path_list, resume = resume,
            abort_check_func = fetch_abort_function,
            url_fetcher_class = self._entropy._url_fetcher,
            download_context_func = download_context,
            pre_download_hook = pre_download_hook)
        try:
            # make sure that we don't need to abort already
            # doing the check here avoids timeouts
            if fetch_abort_function != None:
                fetch_abort_function()

            data = fetch_intf.download()
        except (KeyboardInterrupt, InterruptError):
            return [], 0.0, -100
        data_transfer = fetch_intf.get_transfer_rate()

        fetch_errors = (
            UrlFetcher.TIMEOUT_FETCH_ERROR,
            UrlFetcher.GENERIC_FETCH_ERROR,
            UrlFetcher.GENERIC_FETCH_WARN,
        )

        valid_idxs = []
        for url_data_map_idx, cksum in tuple(data.items()):

            if cksum in fetch_errors:
                # download failed
                continue

            (pkg_id, repository_id, url, dest_path,
             orig_cksum, _signs, _edelta_url, edelta_download_path,
             installed_download_path) = url_data_map[url_data_map_idx]

            dest_path_dir = os.path.dirname(dest_path)

            lock = None
            try:
                lock = self.path_lock(edelta_download_path)
                with lock.shared():

                    tmp_fd, tmp_path = None, None
                    try:
                        tmp_fd, tmp_path = const_mkstemp(
                            dir=dest_path_dir, suffix=".edelta_pkg_tmp")

                        try:
                            entropy.tools.apply_entropy_delta(
                                installed_download_path,  # best effort read
                                edelta_download_path,  # shared lock
                                tmp_path)  # atomically created path
                        except IOError:
                            continue

                        os.rename(tmp_path, dest_path)
                        valid_idxs.append(url_data_map_idx)

                    finally:
                        if tmp_fd is not None:
                            try:
                                os.close(tmp_fd)
                            except OSError:
                                pass
                        if tmp_path is not None:
                            try:
                                os.remove(tmp_path)
                            except OSError:
                                pass

            finally:
                if lock is not None:
                    lock.close()

        fetched_url_data = []
        for url_data_map_idx in valid_idxs:
            (pkg_id, repository_id, url, dest_path,
             orig_cksum, signs, _edelta_url, edelta_download_path,
             installed_download_path) = url_data_map[url_data_map_idx]

            try:
                valid = entropy.tools.compare_md5(dest_path, orig_cksum)
            except (IOError, OSError):
                valid = False

            if valid:
                url_data_item = (
                    pkg_id, repository_id, url,
                    dest_path, orig_cksum, signs
                )
                fetched_url_data.append(url_data_item)

        return fetched_url_data, data_transfer, 0

    def _download_files(self, url_data, resume = True):
        """
        Effectively fetch the package files.
        """
        self._setup_url_directories(url_data)

        @contextlib.contextmanager
        def download_context(path):
            lock = None
            try:
                lock = self.path_lock(path)
                with lock.exclusive():
                    yield  # hooks running inside here
            finally:
                if lock is not None:
                    lock.close()

        # set of paths that have been verified and don't need any
        # firther match_checksum() call.
        validated_download_ids_lock = threading.Lock()
        validated_download_ids = set()

        # Note: the following two hooks are running in separate threads.

        def pre_download_hook(path, download_id):
            path_data = url_data[download_id - 1]
            (_hook_package_id, hook_repository_id, _hook_url,
             hook_download_path, hook_cksum, hook_signs) = path_data

            if self._stat_path(hook_download_path):
                verify_st = self._match_checksum(
                    hook_download_path,
                    hook_repository_id,
                    hook_cksum,
                    hook_signs)
                if verify_st == 0:
                    # UrlFetcher returns the md5 checksum on success
                    with validated_download_ids_lock:
                        validated_download_ids.add(download_id)
                    return hook_cksum

            # request the download
            return None

        def post_download_hook(_path, _status, download_id):
            path_data = url_data[download_id - 1]
            (_hook_package_id, hook_repository_id, _hook_url,
             hook_download_path, hook_cksum, hook_signs) = path_data

            with validated_download_ids_lock:
                if hook_download_path in validated_download_ids:
                    # nothing to check, path already verified
                    return

            if not self._stat_path(hook_download_path):
                return

            verify_st = self._match_checksum(
                hook_download_path,
                hook_repository_id,
                hook_cksum,
                hook_signs)
            if verify_st == 0:
                with validated_download_ids_lock:
                    validated_download_ids.add(download_id)

        url_path_list = []
        for pkg_id, repository_id, url, download_path, _cksum, _sig in url_data:
            url_path_list.append((url, download_path))

            lock = None
            try:
                # hold a lock against the download path, like fetch.py does.
                lock = self.path_lock(download_path)
                with lock.exclusive():

                    self._setup_differential_download(
                        self._entropy._multiple_url_fetcher, url,
                        resume, download_path,
                        repository_id, pkg_id)

            finally:
                if lock is not None:
                    lock.close()

        fetch_abort_function = self._meta.get('fetch_abort_function')
        fetch_intf = self._entropy._multiple_url_fetcher(
            url_path_list, resume = resume,
            abort_check_func = fetch_abort_function,
            url_fetcher_class = self._entropy._url_fetcher,
            download_context_func = download_context,
            pre_download_hook = pre_download_hook,
            post_download_hook = post_download_hook)
        try:
            # make sure that we don't need to abort already
            # doing the check here avoids timeouts
            if fetch_abort_function != None:
                fetch_abort_function()

            data = fetch_intf.download()
        except (KeyboardInterrupt, InterruptError):
            return -100, {}, 0

        failed_map = {}
        for download_id, tup in enumerate(url_data, 1):

            if download_id in validated_download_ids:
                # valid, nothing to do
                continue

            (_pkg_id, repository_id, _url,
             _download_path, _ignore_checksum, signatures) = tup

            # use the outcome returned by download(), it
            # contains an error code if download failed.
            val = data.get(download_id)
            failed_map[url_path_list[download_id - 1][0]] = (
                val, signatures)

        exit_st = 0
        if failed_map:
            exit_st = -1
        # determine if we got a -100, KeyboardInterrupt
        for _key, (val, _signs) in tuple(failed_map.items()):
            if val == -100:
                exit_st = -100
                break

        return exit_st, failed_map, fetch_intf.get_transfer_rate()

    def _download_packages(self, download_list):
        """
        Internal function. Download packages.
        """
        avail_data = self._settings['repositories']['available']
        excluded_data = self._settings['repositories']['excluded']

        repo_uris = {}
        for pkg_id, repository_id, fname, cksum, _signatures in download_list:
            repo = self._entropy.open_repository(repository_id)

            # grab original repo, if any and use it if available
            # this is done in order to support "equo repo merge" feature
            # allowing client-side repository package metadata moves.
            original_repo = repo.getInstalledPackageRepository(pkg_id)

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
                    uris += avail_data[repository_id]['packages'][::-1]
                elif original_repo in excluded_data:
                    uris = excluded_data[original_repo]['packages'][::-1]
                    uris += avail_data[repository_id]['packages'][::-1]
                else:
                    uris = avail_data[repository_id]['packages'][::-1]

            obj = repo_uris.setdefault(repository_id, [])
            # append at the beginning
            new_ones = [x for x in uris if x not in obj][::-1]
            for new_obj in new_ones:
                obj.insert(0, new_obj)

        remaining = repo_uris.copy()
        mirror_status = StatusInterface()

        def get_best_mirror(repository_id):
            try:
                return remaining[repository_id][0]
            except IndexError:
                return None

        def update_download_list(down_list, failed_down):
            newlist = []
            for pkg_id, repository_id, fname, cksum, signatures in down_list:
                p_uri = get_best_mirror(repository_id)
                p_uri = os.path.join(p_uri, fname)
                if p_uri not in failed_down:
                    continue
                newlist.append(
                    (pkg_id, repository_id, fname, cksum, signatures)
                )
            return newlist

        # return True: for failing, return False: for fine
        def mirror_fail_check(repository_id, best_mirror):
            # check if uri is sane
            if not mirror_status.get_failing_mirror_status(best_mirror) >= 30:
                return False

            # set to 30 for convenience
            mirror_status.set_failing_mirror_status(best_mirror, 30)

            mirrorcount = repo_uris[repository_id].index(best_mirror) + 1
            txt = "( mirror #%s ) %s %s - %s" % (
                mirrorcount,
                blue(_("Mirror")),
                red(self._get_url_name(best_mirror)),
                _("maximum failure threshold reached"),
            )
            self._entropy.output(
                txt,
                importance = 1,
                level = "warning",
                header = red("   ## ")
            )

            if mirror_status.get_failing_mirror_status(best_mirror) == 30:
                mirror_status.add_failing_mirror(best_mirror, 45)
            elif mirror_status.get_failing_mirror_status(best_mirror) > 31:
                mirror_status.add_failing_mirror(best_mirror, -4)
            else:
                mirror_status.set_failing_mirror_status(best_mirror, 0)

            try:
                remaining[repository_id].remove(best_mirror)
            except ValueError:
                # ignore
                pass
            return True

        def show_download_summary(down_list):
            for _pkg_id, repository_id, fname, _cksum, _signatures in down_list:
                best_mirror = get_best_mirror(repository_id)
                mirrorcount = repo_uris[repository_id].index(best_mirror) + 1
                basef = os.path.basename(fname)

                txt = "( mirror #%s ) [%s] %s %s" % (
                    mirrorcount,
                    brown(basef),
                    blue("@"),
                    red(self._get_url_name(best_mirror)),
                )
                self._entropy.output(
                    txt,
                    importance = 1,
                    level = "info",
                    header = red("   ## ")
                )

        def show_successful_download(down_list, data_transfer):
            for _pkg_id, repository_id, fname, _cksum, _signatures in down_list:
                best_mirror = get_best_mirror(repository_id)
                mirrorcount = repo_uris[repository_id].index(best_mirror) + 1
                basef = os.path.basename(fname)

                txt = "( mirror #%s ) [%s] %s %s %s" % (
                    mirrorcount,
                    brown(basef),
                    darkred(_("success")),
                    blue("@"),
                    red(self._get_url_name(best_mirror)),
                )
                self._entropy.output(
                    txt,
                    importance = 1,
                    level = "info",
                    header = red("   ## ")
                )

            if data_transfer:
                txt = " %s: %s%s%s" % (
                    blue(_("Aggregated transfer rate")),
                    bold(entropy.tools.bytes_into_human(data_transfer)),
                    darkred("/"),
                    darkblue(_("second")),
                )
                self._entropy.output(
                    txt,
                    importance = 1,
                    level = "info",
                    header = red("   ## ")
                )

        def show_download_error(down_list, p_exit_st):
            for _pkg_id, repository_id, _fname, _cksum, _signs in down_list:
                best_mirror = get_best_mirror(repository_id)
                mirrorcount = repo_uris[repository_id].index(best_mirror) + 1

                txt = "( mirror #%s ) %s: %s" % (
                    mirrorcount,
                    blue(_("Error downloading from")),
                    red(self._get_url_name(best_mirror)),
                )
                if p_exit_st == -1:
                    txt += " - %s." % (
                        _("data not available on this mirror"),)
                elif p_exit_st == -2:
                    mirror_status.add_failing_mirror(best_mirror, 1)
                    txt += " - %s." % (_("wrong checksum"),)

                elif p_exit_st == -3:
                    txt += " - %s." % (_("not found"),)

                elif p_exit_st == -4: # timeout!
                    txt += " - %s." % (_("timeout error"),)

                elif p_exit_st == -100:
                    txt += " - %s." % (_("discarded download"),)

                else:
                    mirror_status.add_failing_mirror(best_mirror, 5)
                    txt += " - %s." % (_("unknown reason"),)

                self._entropy.output(
                    txt,
                    importance = 1,
                    level = "warning",
                    header = red("   ## ")
                )

        def remove_failing_mirrors(repos):
            for repository_id in repos:
                get_best_mirror(repository_id)
                if remaining[repository_id]:
                    remaining[repository_id].pop(0)

        def check_remaining_mirror_failure(repos):
            return [x for x in repos if not remaining.get(x)]

        d_list = download_list[:]

        while True:
            do_resume = True
            timeout_try_count = 50

            while True:
                fetch_files_list = []

                for pkg_id, repository_id, fname, cksum, signs in d_list:
                    best_mirror = get_best_mirror(repository_id)
                    # set working mirror, dont care if its None
                    mirror_status.set_working_mirror(best_mirror)
                    if best_mirror is not None:
                        mirror_fail_check(repository_id, best_mirror)
                        best_mirror = get_best_mirror(repository_id)

                    if best_mirror is None:
                        # at least one package failed to download
                        # properly, give up with everything
                        return 3, d_list

                    myuri = os.path.join(best_mirror, fname)
                    pkg_path = self.get_standard_fetch_disk_path(fname)
                    fetch_files_list.append(
                        (pkg_id, repository_id, myuri, pkg_path, cksum, signs)
                    )

                show_download_summary(d_list)

                (edelta_fetch_files_list, data_transfer,
                 exit_st) = self._try_edelta_multifetch(
                     fetch_files_list, do_resume)

                failed_downloads = None

                if exit_st == 0:
                    # O(nm) but both lists are very small...
                    updated_fetch_files_list = [
                        x for x in fetch_files_list if x not in
                        edelta_fetch_files_list]

                    if updated_fetch_files_list:
                        (exit_st, failed_downloads,
                         data_transfer) = self._download_files(
                             updated_fetch_files_list,
                             resume = do_resume)

                if exit_st == 0:
                    show_successful_download(
                        d_list, data_transfer)
                    return 0, []

                if failed_downloads:
                    d_list = update_download_list(
                        d_list, failed_downloads)

                if exit_st not in (-3, -4, -100,) and failed_downloads and \
                    do_resume:
                    # disable resume
                    do_resume = False
                    continue

                show_download_error(d_list, exit_st)

                if exit_st == -4: # timeout
                    timeout_try_count -= 1
                    if timeout_try_count > 0:
                        continue

                elif exit_st == -100: # user discarded fetch
                    return 1, []

                myrepos = set([x[1] for x in d_list])
                remove_failing_mirrors(myrepos)

                # make sure we don't have nasty issues
                remaining_failure = check_remaining_mirror_failure(
                    myrepos)

                if remaining_failure:
                    return 3, d_list

                break

        return 0, []

    def _fetch_phase(self):
        """
        Execute the fetch phase.
        """
        m_fetch_len = len(self._meta['multi_fetch_list']) / 2
        xterm_title = "%s: %s %s" % (
            _("Downloading"),
            m_fetch_len,
            ngettext("package", "packages", m_fetch_len),
        )
        self._entropy.set_title(xterm_title)

        m_fetch_len = len(self._meta['multi_fetch_list'])
        txt = "%s: %s %s" % (
            blue(_("Downloading")),
            darkred("%s" % (m_fetch_len,)),
            ngettext("package", "packages", m_fetch_len),
        )
        self._entropy.output(
            txt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        exit_st, err_list = self._download_packages(
            self._meta['multi_fetch_list'])
        if exit_st == 0:
            return 0

        txt = _("Some packages cannot be fetched")
        txt2 = _("Try to update your repositories and retry")
        for txt in (txt, txt2,):
            self._entropy.output(
                "%s." % (
                    darkred(txt),
                ),
                importance = 0,
                level = "info",
                header = red("   ## ")
            )

        self._entropy.output(
            "%s: %s" % (
                brown(_("Error")),
                exit_st,
            ),
            importance = 0,
            level = "info",
            header = red("   ## ")
        )

        for _pkg_id, repo, fname, cksum, _signatures in err_list:
            self._entropy.output(
                "[%s|%s] %s" % (
                    blue(repo),
                    darkgreen(cksum),
                    darkred(fname),
                ),
                importance = 1,
                level = "error",
                header = darkred("    # ")
            )

        return exit_st
