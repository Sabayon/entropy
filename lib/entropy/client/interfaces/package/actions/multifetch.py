# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
import errno
import os

from entropy.const import etpConst, const_setup_perms
from entropy.client.mirrors import StatusInterface
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

        temp_fetch_list = []
        temp_checksum_list = []
        temp_already_downloaded_count = 0

        def _setup_download(download, size, package_id, repository_id, digest,
                signatures):

            inst_repo = self._entropy.installed_repository()
            installed_package_id = None

            repo = self._entropy.open_repository(repository_id)
            key_slot = repo.retrieveKeySlotAggregated(package_id)
            if key_slot:
                installed_package_id, _inst_rc = inst_repo.atomMatch(key_slot)

            obj = (package_id, repository_id, download, digest, signatures)
            temp_checksum_list.append(obj)

            down_path = self.get_standard_fetch_disk_path(download)
            try:
                down_st = os.lstat(down_path)
                st_size = down_st.st_size
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise
                st_size = None

            if st_size is not None:
                if st_size == size:
                    return 1
            else:
                obj = (package_id, repository_id, download, digest, signatures)
                temp_fetch_list.append(obj)

            return 0

        for package_id, repository_id in self._package_matches:

            if repository_id.endswith(etpConst['packagesext']):
                continue

            repo = self._entropy.open_repository(repository_id)
            atom = repo.retrieveAtom(package_id)

            download = repo.retrieveDownloadURL(package_id)
            digest = repo.retrieveDigest(package_id)
            sha1, sha256, sha512, gpg = repo.retrieveSignatures(package_id)
            size = repo.retrieveSize(package_id)
            signatures = {
                'sha1': sha1,
                'sha256': sha256,
                'sha512': sha512,
                'gpg': gpg,
            }
            temp_already_downloaded_count += _setup_download(
                download, size, package_id, repository_id, digest, signatures)

            extra_downloads = repo.retrieveExtraDownload(package_id)

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
                size = extra_download['size']
                digest = extra_download['md5']
                signatures = {
                    'sha1': extra_download['sha1'],
                    'sha256': extra_download['sha256'],
                    'sha512': extra_download['sha512'],
                    'gpg': extra_download['gpg'],
                }
                temp_already_downloaded_count += _setup_download(
                    download, size, package_id, repository_id,
                    digest, signatures)

        metadata['multi_fetch_list'] = temp_fetch_list
        metadata['multi_checksum_list'] = temp_checksum_list

        metadata['phases'] = []
        if metadata['multi_fetch_list']:
            metadata['phases'].append(self._fetch)

        if metadata['multi_checksum_list']:
            metadata['phases'].append(self._checksum)

        if temp_already_downloaded_count == len(temp_checksum_list):
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

    def _try_edelta_multifetch(self, url_data, resume):
        """
        Attempt to download and use the edelta file.
        """
        # no edelta support enabled
        if not self._meta.get('edelta_support'):
            return [], 0.0, False

        if not entropy.tools.is_entropy_delta_available():
            return [], 0.0, False

        url_path_list = []
        url_data_map = {}
        url_data_map_idx = 0
        inst_repo = self._entropy.installed_repository()
        for pkg_id, repository_id, url, dest_path, cksum in url_data:

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

            edelta_url = self._approve_edelta_unlocked(
                url, cksum, installed_url, installed_checksum,
                installed_download_path)
            if edelta_url is None:
                # no edelta support
                continue

            edelta_save_path = dest_path + etpConst['packagesdeltaext']
            key = (edelta_url, edelta_save_path)
            url_path_list.append(key)
            url_data_map_idx += 1
            url_data_map[url_data_map_idx] = (
                pkg_id, repository_id, url,
                dest_path, cksum, edelta_url,
                edelta_save_path, installed_download_path)

        if not url_path_list:
            # no martini, no party!
            return [], 0.0, False

        fetch_abort_function = self._meta.get('fetch_abort_function')
        fetch_intf = self._entropy._multiple_url_fetcher(url_path_list,
            resume = resume, abort_check_func = fetch_abort_function,
            url_fetcher_class = self._entropy._url_fetcher)
        try:
            # make sure that we don't need to abort already
            # doing the check here avoids timeouts
            if fetch_abort_function != None:
                fetch_abort_function()

            data = fetch_intf.download()
        except KeyboardInterrupt:
            return [], 0.0, True
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
             orig_cksum, edelta_url, edelta_save_path,
             installed_fetch_path) = url_data_map[url_data_map_idx]

            # now check
            tmp_dest_path = dest_path + ".edelta_pkg_tmp"
            # yay, we can apply the delta and cook the new package file!
            try:
                entropy.tools.apply_entropy_delta(installed_fetch_path,
                    edelta_save_path, tmp_dest_path)
            except IOError:
                # give up with this edelta
                try:
                    os.remove(tmp_dest_path)
                except (OSError, IOError):
                    pass
                continue

            os.rename(tmp_dest_path, dest_path)
            valid_idxs.append(url_data_map_idx)

        fetched_url_data = []
        for url_data_map_idx in valid_idxs:
            (pkg_id, repository_id, url, dest_path,
             orig_cksum, edelta_url, edelta_save_path,
             installed_fetch_path) = url_data_map[url_data_map_idx]

            try:
                valid = entropy.tools.compare_md5(dest_path, orig_cksum)
            except (IOError, OSError):
                valid = False

            if valid:
                url_data_item = (pkg_id, repository_id, url,
                                 dest_path, orig_cksum)
                fetched_url_data.append(url_data_item)

        return fetched_url_data, data_transfer, False

    def _fetch_files(self, url_data_list, resume = True):
        """
        Effectively fetch the package files.
        """

        def _generate_checksum_map(url_data):
            ck_map = {}
            ck_map_id = 0
            for _pkg_id, _repository_id, _url, _dest_path, cksum in url_data:
                ck_map_id += 1
                if cksum is not None:
                    ck_map[ck_map_id] = cksum
            return ck_map

        fetch_abort_function = self._meta.get('fetch_abort_function')
        # avoid tainting data pointed by url_data_list
        url_data = url_data_list[:]
        diff_map = {}

        # setup directories
        for pkg_id, repository_id, url, dest_path, _cksum in url_data:
            dest_dir = os.path.dirname(dest_path)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir, 0o775)
                const_setup_perms(dest_dir, etpConst['entropygid'])

        checksum_map = _generate_checksum_map(url_data)
        fetched_url_data, data_transfer, abort = self._try_edelta_multifetch(
            url_data, resume)
        if abort:
            return -100, {}, 0

        for url_data_item in fetched_url_data:
            url_data.remove(url_data_item)

        # some packages haven't been downloaded using edelta
        if url_data:

            url_path_list = []
            for pkg_id, repository_id, url, dest_path, _cksum in url_data:
                url_path_list.append((url, dest_path,))
                self._setup_differential_download(
                    self._entropy._multiple_url_fetcher, url, resume, dest_path,
                        repository_id, pkg_id)

            # load class
            fetch_intf = self._entropy._multiple_url_fetcher(
                url_path_list, resume = resume,
                abort_check_func = fetch_abort_function,
                url_fetcher_class = self._entropy._url_fetcher,
                checksum = True)
            try:
                # make sure that we don't need to abort already
                # doing the check here avoids timeouts
                if fetch_abort_function != None:
                    fetch_abort_function()

                data = fetch_intf.download()
            except KeyboardInterrupt:
                return -100, {}, 0

            data_transfer = fetch_intf.get_transfer_rate()
            checksum_map = _generate_checksum_map(url_data)
            for ck_id in checksum_map:
                orig_checksum = checksum_map.get(ck_id)
                if orig_checksum != data.get(ck_id):
                    diff_map[url_path_list[ck_id-1][0]] = orig_checksum

        if diff_map:
            defval = -1
            for key, val in tuple(diff_map.items()):
                if val == UrlFetcher.GENERIC_FETCH_WARN:
                    diff_map[key] = -2
                elif val == UrlFetcher.TIMEOUT_FETCH_ERROR:
                    diff_map[key] = -4
                elif val == UrlFetcher.GENERIC_FETCH_ERROR:
                    diff_map[key] = -3
                elif val == -100:
                    defval = -100

            return defval, diff_map, data_transfer

        return 0, diff_map, data_transfer

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

                for pkg_id, repository_id, fname, cksum, _signs in d_list:
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
                        (pkg_id, repository_id, myuri, pkg_path, cksum,)
                    )

                show_download_summary(d_list)
                (exit_st, failed_downloads,
                 data_transfer) = self._fetch_files(
                     fetch_files_list, resume = do_resume)

                if exit_st == 0:
                    show_successful_download(
                        d_list, data_transfer)
                    return 0, []

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

    def _fetch(self):
        """
        Execute the fetch phase.
        """
        m_fetch_len = len(self._meta['multi_fetch_list']) / 2
        xterm_title = "%s: %s %s" % (
            _("Multi Fetching"),
            m_fetch_len,
            ngettext("package", "packages", m_fetch_len),
        )
        self._entropy.set_title(xterm_title)

        m_fetch_len = len(self._meta['multi_fetch_list'])
        txt = "%s: %s %s" % (
            blue(_("Downloading")),
            darkred("%s" % (m_fetch_len,)),
            ngettext("archive", "archives", m_fetch_len),
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

    def _checksum(self):
        """
        Execute the checksum verification phase.
        """
        m_len = len(self._meta['multi_checksum_list'])
        xterm_title = "%s: %s %s" % (
            _("Multi Verification"),
            m_len,
            ngettext("package", "packages", m_len),
        )
        self._entropy.set_title(xterm_title)

        exit_st = 0
        ck_list = self._meta['multi_checksum_list']

        for (pkg_id, repository_id, download, digest, signatures) in ck_list:
            download_path = self.get_standard_fetch_disk_path(download)
            exit_st = self._match_checksum(
                download_path, repository_id, digest, signatures)
            if exit_st != 0:
                break

        return exit_st
