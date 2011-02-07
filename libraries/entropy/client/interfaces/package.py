# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
import sys
import os
import errno
import stat
import shutil
import tempfile
import time

from entropy.const import etpConst, etpUi, const_setup_perms, \
    const_isunicode, const_convert_to_unicode, const_debug_write
from entropy.exceptions import PermissionDenied, SPMError
from entropy.i18n import _
from entropy.output import brown, blue, bold, darkgreen, \
    darkblue, red, purple, darkred, teal
from entropy.client.interfaces.client import Client
from entropy.client.mirrors import StatusInterface
from entropy.core.settings.base import SystemSettings
from entropy.security import Repository as RepositorySecurity

import entropy.dep
import entropy.tools

class Package:

    def __init__(self, entropy_client):

        if not isinstance(entropy_client, Client):
            mytxt = "A valid Client instance or subclass is needed"
            raise AttributeError(mytxt)
        self._entropy = entropy_client

        self._settings = SystemSettings()
        self.pkgmeta = {}
        self.__prepared = False
        self._package_match = ()
        self._valid_actions = ("source", "fetch", "multi_fetch", "remove",
            "remove_conflict", "install", "config"
        )
        self._action = None
        self._xterm_title = ''

    def __repr__(self):
        return "<%s.Package at %s | metadata: %s | action: %s, prepared: %s>" \
            % (__name__, hex(id(self)), self.pkgmeta, self._action,
                self.__prepared)

    def __str__(self):
        return repr(self)

    def __unicode__(self):
        return unicode(repr(self))

    def kill(self):
        self.pkgmeta.clear()

        self._package_match = ()
        self._valid_actions = ()
        self._action = None
        self.__prepared = False

    def _error_on_prepared(self):
        if self.__prepared:
            mytxt = _("Already prepared")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))

    def _error_on_not_prepared(self):
        if not self.__prepared:
            mytxt = _("Not yet prepared")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))

    def _check_action_validity(self, action):
        if action not in self._valid_actions:
            raise AttributeError("Action must be in %s" % (
                self._valid_actions,))

    @staticmethod
    def get_standard_fetch_disk_path(download):
        """
        Return standard path where package is going to be downloaded.
        "download" argument passed must come from
        EntropyRepository.retrieveDownloadURL()
        """
        return os.path.join(etpConst['entropypackagesworkdir'], download)

    def __get_fetch_disk_path(self, download):
        """
        Return proper Entropy package store path
        """
        if 'fetch_path' in self.pkgmeta:
            # only supported by fetch action, multifetch also unsupported
            pkg_disk_path = os.path.join(self.pkgmeta['fetch_path'],
                os.path.basename(download))
        else:
            pkg_disk_path = Package.get_standard_fetch_disk_path(download)
        return pkg_disk_path

    def __escape_path(self, path):
        """
        Some applications (like ld) don't like ":" in path, others just don't
        escape paths at all. So, it's better to avoid to use field separators
        in path.
        """
        path = path.replace(":", "_")
        path = path.replace("~", "_")
        return path

    def __check_pkg_path_download(self, download, checksum = None):
        # is the file available
        pkg_path = self.__get_fetch_disk_path(download)
        if os.path.isfile(pkg_path):

            if checksum is None:
                return 0
            # check digest
            md5res = entropy.tools.compare_md5(pkg_path, checksum)
            if md5res:
                return 0
            return -2

        return -1

    def __fetch_files(self, url_data_list, checksum = True, resume = True):

        def _generate_checksum_map(url_data):
            if not checksum:
                return {}
            ck_map = {}
            ck_map_id = 0
            for pkg_id, repo, url, dest_path, cksum in url_data:
                ck_map_id += 1
                if cksum is not None:
                    ck_map[ck_map_id] = cksum
            return ck_map

        fetch_abort_function = self.pkgmeta.get('fetch_abort_function')
        # avoid tainting data pointed by url_data_list
        url_data = url_data_list[:]
        diff_map = {}

        # setup directories
        for pkg_id, repo, url, dest_path, cksum in url_data:
            dest_dir = os.path.dirname(dest_path)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir, 0o775)
                const_setup_perms(dest_dir, etpConst['entropygid'])

        checksum_map = _generate_checksum_map(url_data)
        fetched_url_data, data_transfer, abort = self.__try_edelta_multifetch(
            url_data, resume)
        if abort:
            return -100, {}, 0

        for url_data_item in fetched_url_data:
            url_data.remove(url_data_item)

        # some packages haven't been downloaded using edelta
        if url_data:

            url_path_list = []
            for pkg_id, repo, url, dest_path, cksum in url_data:
                url_path_list.append((url, dest_path,))
                self._setup_differential_download(
                    self._entropy.MultipleUrlFetcher, url, resume, dest_path,
                        repo, pkg_id)

            # load class
            fetch_intf = self._entropy.MultipleUrlFetcher(url_path_list,
                resume = resume, abort_check_func = fetch_abort_function,
                url_fetcher_class = self._entropy.urlFetcher,
                checksum = checksum)
            try:
                data = fetch_intf.download()
            except KeyboardInterrupt:
                return -100, {}, 0
            # update transfer rate information
            data_transfer = fetch_intf.get_transfer_rate()

            checksum_map = _generate_checksum_map(url_data)
            # if checksum_map is empty, it means that checksum == False
            for ck_id in checksum_map:
                orig_checksum = checksum_map.get(ck_id)
                if orig_checksum != data.get(ck_id):
                    diff_map[url_path_list[ck_id-1][0]] = orig_checksum

        if diff_map:
            defval = -1
            for key, val in diff_map.items():
                if val == "-1": # general error
                    diff_map[key] = -1
                elif val == "-2":
                    diff_map[key] = -2
                elif val == "-4": # timeout
                    diff_map[key] = -4
                elif val == "-3": # not found
                    diff_map[key] = -3
                elif val == -100:
                    defval = -100
            return defval, diff_map, data_transfer

        return 0, diff_map, data_transfer

    def _get_url_name(self, url):
        """
        Given a mirror URL, returns a smaller string representing the URL name.

        @param url: URL string
        @type url: string
        @return: representative URL string
        @rtype: string
        """
        url_data = entropy.tools.spliturl(url)
        url_name = url_data.netloc
        url_scheme = url_data.scheme
        if not url_scheme:
            url_scheme = "unknown"
        return "%s://%s" % (url_scheme, url_name,)

    def _download_packages(self, download_list, checksum = False):

        avail_data = self._settings['repositories']['available']
        excluded_data = self._settings['repositories']['excluded']

        repo_uris = {}
        for pkg_id, repo, fname, cksum, signatures in download_list:
            repo_db = self._entropy.open_repository(repo)
            # grab original repo, if any and use it if available
            # this is done in order to support "equo repo merge" feature
            # allowing client-side repository package metadata moves.
            original_repo = repo_db.getInstalledPackageRepository(pkg_id)

            if original_repo in avail_data:
                uris = avail_data[original_repo]['packages'][::-1]
                uris += avail_data[repo]['packages'][::-1]
            elif original_repo in excluded_data:
                uris = excluded_data[original_repo]['packages'][::-1]
                uris += avail_data[repo]['packages'][::-1]
            else:
                uris = avail_data[repo]['packages'][::-1]
            obj = repo_uris.setdefault(repo, [])
            # append at the beginning
            new_ones = [x for x in uris if x not in obj][::-1]
            for new_obj in new_ones:
                obj.insert(0, new_obj)


        remaining = repo_uris.copy()
        my_download_list = download_list[:]
        mirror_status = StatusInterface()

        def get_best_mirror(repository):
            try:
                return remaining[repository][0]
            except IndexError:
                return None

        def update_download_list(down_list, failed_down):
            newlist = []
            for pkg_id, repo, fname, cksum, signatures in down_list:
                myuri = get_best_mirror(repo)
                myuri = os.path.join(myuri, fname)
                if myuri not in failed_down:
                    continue
                newlist.append((pkg_id, repo, fname, cksum, signatures,))
            return newlist

        # return True: for failing, return False: for fine
        def mirror_fail_check(repository, best_mirror):
            # check if uri is sane
            if not mirror_status.get_failing_mirror_status(best_mirror) >= 30:
                return False
            # set to 30 for convenience
            mirror_status.set_failing_mirror_status(best_mirror, 30)
            mirrorcount = repo_uris[repository].index(best_mirror)+1
            mytxt = "( mirror #%s ) " % (mirrorcount,)
            mytxt += blue(" %s: ") % (_("Mirror"),)
            mytxt += red(self._get_url_name(best_mirror))
            mytxt += " - %s." % (_("maximum failure threshold reached"),)
            self._entropy.output(
                mytxt,
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
                remaining[repository].remove(best_mirror)
            except ValueError:
                # ignore
                pass
            return True

        def show_download_summary(down_list):
            for pkg_id, repo, fname, cksum, signatures in down_list:
                best_mirror = get_best_mirror(repo)
                mirrorcount = repo_uris[repo].index(best_mirror)+1
                mytxt = "( mirror #%s ) " % (mirrorcount,)
                basef = os.path.basename(fname)
                mytxt += "[%s] %s " % (brown(basef), blue("@"),)
                mytxt += red(self._get_url_name(best_mirror))
                # now fetch the new one
                self._entropy.output(
                    mytxt,
                    importance = 1,
                    level = "info",
                    header = red("   ## ")
                )

        def show_successful_download(down_list, data_transfer):
            for pkg_id, repo, fname, cksum, signatures in down_list:
                best_mirror = get_best_mirror(repo)
                mirrorcount = repo_uris[repo].index(best_mirror)+1
                mytxt = "( mirror #%s ) " % (mirrorcount,)
                basef = os.path.basename(fname)
                mytxt += "[%s] %s %s " % (brown(basef),
                    darkred(_("success")), blue("@"),)
                mytxt += red(self._get_url_name(best_mirror))
                self._entropy.output(
                    mytxt,
                    importance = 1,
                    level = "info",
                    header = red("   ## ")
                )
            mytxt = " %s: %s%s%s" % (
                blue(_("Aggregated transfer rate")),
                bold(entropy.tools.bytes_into_human(data_transfer)),
                darkred("/"),
                darkblue(_("second")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "info",
                header = red("   ## ")
            )

        def show_download_error(down_list, rc):
            for pkg_id, repo, fname, cksum, signatures in down_list:
                best_mirror = get_best_mirror(repo)
                mirrorcount = repo_uris[repo].index(best_mirror)+1
                mytxt = "( mirror #%s ) " % (mirrorcount,)
                mytxt += blue("%s: %s") % (
                    _("Error downloading from"),
                    red(self._get_url_name(best_mirror)),
                )
                if rc == -1:
                    mytxt += " - %s." % (_("data not available on this mirror"),)
                elif rc == -2:
                    mirror_status.add_failing_mirror(best_mirror, 1)
                    mytxt += " - %s." % (_("wrong checksum"),)
                elif rc == -3:
                    mytxt += " - %s." % (_("not found"),)
                elif rc == -4: # timeout!
                    mytxt += " - %s." % (_("timeout error"),)
                elif rc == -100:
                    mytxt += " - %s." % (_("discarded download"),)
                else:
                    mirror_status.add_failing_mirror(best_mirror, 5)
                    mytxt += " - %s." % (_("unknown reason"),)
                self._entropy.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = red("   ## ")
                )

        def remove_failing_mirrors(repos):
            for repo in repos:
                best_mirror = get_best_mirror(repo)
                if remaining[repo]:
                    remaining[repo].pop(0)

        def check_remaining_mirror_failure(repos):
            return [x for x in repos if not remaining.get(x)]

        while True:

            do_resume = True
            timeout_try_count = 50
            while True:

                fetch_files_list = []
                for pkg_id, repo, fname, cksum, signatures in my_download_list:
                    best_mirror = get_best_mirror(repo)
                    # set working mirror, dont care if its None
                    mirror_status.set_working_mirror(best_mirror)
                    if best_mirror is not None:
                        mirror_fail_check(repo, best_mirror)
                        best_mirror = get_best_mirror(repo)
                    if best_mirror is None:
                        # at least one package failed to download
                        # properly, give up with everything
                        return 3, my_download_list
                    myuri = os.path.join(best_mirror, fname)
                    pkg_path = Package.get_standard_fetch_disk_path(fname)
                    fetch_files_list.append(
                        (pkg_id, repo, myuri, pkg_path, cksum,))

                try:

                    show_download_summary(my_download_list)
                    rc, failed_downloads, data_transfer = self.__fetch_files(
                        fetch_files_list, checksum = checksum,
                        resume = do_resume
                    )
                    if rc == 0:
                        show_successful_download(my_download_list,
                            data_transfer)
                        return 0, []

                    # update my_download_list
                    my_download_list = update_download_list(my_download_list,
                        failed_downloads)
                    if rc not in (-3, -4, -100,) and failed_downloads and \
                        do_resume:
                        # disable resume
                        do_resume = False
                        continue
                    else:
                        show_download_error(my_download_list, rc)
                        if rc == -4: # timeout
                            timeout_try_count -= 1
                            if timeout_try_count > 0:
                                continue
                        elif rc == -100: # user discarded fetch
                            return 1, []
                        myrepos = set([x[1] for x in my_download_list])
                        remove_failing_mirrors(myrepos)
                        # make sure we don't have nasty issues
                        remaining_failure = check_remaining_mirror_failure(
                            myrepos)
                        if remaining_failure:
                            return 3, my_download_list
                        break

                except KeyboardInterrupt:
                    return 1, []

        return 0, []

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
        installed_fetch_path = self.__get_fetch_disk_path(download_url)

        if os.path.isfile(installed_fetch_path) and \
            os.access(installed_fetch_path, os.R_OK | os.F_OK):
            copied = False
            try:
                shutil.copyfile(installed_fetch_path, fetch_path)
                user = os.stat(installed_fetch_path)[stat.ST_UID]
                group = os.stat(installed_fetch_path)[stat.ST_GID]
                os.chown(fetch_path, user, group)
                shutil.copystat(installed_fetch_path, fetch_path)
                copied = True
            except (OSError, IOError, shutil.Error):
                try:
                    os.remove(fetch_path)
                except OSError:
                    pass
            const_debug_write(__name__,
                "_setup_differential_download(%s) %s %s => %s" % (
                    url, "copied", copied, fetch_path))
        else:
            const_debug_write(__name__,
                "_setup_differential_download(%s) %s" % (
                    url, "no installed package file found"))

    def __approve_edelta(self, url, installed_package_id, package_digest):
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
        installed_fetch_path = self.__get_fetch_disk_path(download_url)

        if os.path.isfile(installed_fetch_path) and \
            os.access(installed_fetch_path, os.R_OK | os.F_OK):

            edelta_local_approved = entropy.tools.compare_md5(
                installed_fetch_path, installed_digest)

            if edelta_local_approved:
                hash_tag = installed_digest + package_digest
                edelta_file_name = \
                    entropy.tools.generate_entropy_delta_file_name(
                        os.path.basename(download_url),
                        os.path.basename(url), hash_tag)
                edelta_url = os.path.join(os.path.dirname(url),
                    etpConst['packagesdeltasubdir'], edelta_file_name)
                return edelta_url, installed_fetch_path

    def __try_edelta_multifetch(self, url_data, resume):

        # no edelta support enabled
        if not self.pkgmeta.get('edelta_support'):
            return [], 0.0, False
        # edelta enabled?
        if not entropy.tools.is_entropy_delta_available():
            return [], 0.0, False

        url_path_list = []
        url_data_map = {}
        url_data_map_idx = 0
        for pkg_id, repo, url, dest_path, cksum in url_data:

            repo_db = self._entropy.open_repository(repo)
            if cksum is None:
                # cannot setup edelta without checksum, get from repository
                cksum = repo_db.retrieveDigest(pkg_id)
                if cksum is None:
                    # still nothing
                    continue

            key_slot = repo_db.retrieveKeySlot(pkg_id)
            if key_slot is None:
                # wtf corrupted entry, skip
                continue

            pkg_key, pkg_slot = key_slot
            installed_package_id = self.__setup_package_to_remove(pkg_key,
                pkg_slot)
            if installed_package_id == -1:
                # package is not installed
                continue

            edelta_approve = self.__approve_edelta(url, installed_package_id,
                cksum)
            if edelta_approve is None:
                # no edelta support
                continue
            edelta_url, installed_fetch_path = edelta_approve

            edelta_save_path = dest_path + etpConst['packagesdeltaext']
            key = (edelta_url, edelta_save_path)
            url_path_list.append(key)
            url_data_map_idx += 1
            url_data_map[url_data_map_idx] = (pkg_id, repo, url, dest_path,
                cksum, edelta_url, edelta_save_path, installed_fetch_path)

        if not url_path_list:
            # no martini, no party!
            return [], 0.0, False

        fetch_abort_function = self.pkgmeta.get('fetch_abort_function')
        fetch_intf = self._entropy.MultipleUrlFetcher(url_path_list,
            resume = resume, abort_check_func = fetch_abort_function,
            url_fetcher_class = self._entropy.urlFetcher)
        try:
            data = fetch_intf.download()
        except KeyboardInterrupt:
            return [], 0.0, True
        data_transfer = fetch_intf.get_transfer_rate()

        valid_idxs = []
        for url_data_map_idx, cksum in data.items():

            if cksum.startswith("-"):
                # download failed => "-1", "-2", "-3", etc
                continue

            pkg_id, repo, url, dest_path, orig_cksum, edelta_url, \
                edelta_save_path, installed_fetch_path = \
                    url_data_map[url_data_map_idx]

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

        # now check md5
        fetched_url_data = []
        for url_data_map_idx in valid_idxs:
            pkg_id, repo, url, dest_path, orig_cksum, edelta_url, \
                edelta_save_path, installed_fetch_path = \
                    url_data_map[url_data_map_idx]

            try:
                valid = entropy.tools.compare_md5(dest_path, orig_cksum)
            except (IOError, OSError):
                valid = False

            if valid:
                url_data_item = (pkg_id, repo, url, dest_path, orig_cksum)
                fetched_url_data.append(url_data_item)

        return fetched_url_data, data_transfer, False


    def __try_edelta_fetch(self, url, save_path, resume):

        # no edelta support enabled
        if not self.pkgmeta.get('edelta_support'):
            return 1, 0.0
        # edelta enabled?
        if not entropy.tools.is_entropy_delta_available():
            return 1, 0.0

        # when called by __fetch_file, which is called by _download_package
        # which is called by _match_checksum, which is called by
        # multi_match_checksum, removeidpackage metadatum is not available
        # So, be fault tolerant.
        installed_package_id = self.pkgmeta.get('removeidpackage', -1)

        # fresh install, cannot fetch edelta, edelta only works for installed
        # packages, by design.
        if installed_package_id == -1:
            return 1, 0.0

        edelta_approve = self.__approve_edelta(url, installed_package_id,
            self.pkgmeta['checksum'])

        if edelta_approve is None:
            # edelta not available, give up
            return 1, 0.0
        edelta_url, installed_fetch_path = edelta_approve

        # check if edelta file is available online
        edelta_save_path = save_path + etpConst['packagesdeltaext']

        max_tries = 2
        edelta_approved = False
        data_transfer = 0
        download_plan = [(edelta_url, edelta_save_path) for x in \
            range(max_tries)]
        delta_resume = resume
        fetch_abort_function = self.pkgmeta.get('fetch_abort_function')

        for delta_url, delta_save in download_plan:

            delta_fetcher = self._entropy.urlFetcher(delta_url,
                delta_save, resume = delta_resume,
                abort_check_func = fetch_abort_function)

            try:
                delta_checksum = delta_fetcher.download()
                data_transfer = delta_fetcher.get_transfer_rate()
                del delta_fetcher
            except KeyboardInterrupt:
                return -100, data_transfer
            except NameError:
                raise
            except Exception:
                return -1, data_transfer

            # "-3", "-4", etc are considered errors, so give up.
            if delta_checksum.startswith("-"):
                # make sure this points to the hell
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

    def __fetch_file(self, url, save_path, digest = None, resume = True,
        download = None, package_id = None, repository = None):

        def do_stfu_rm(xpath):
            try:
                os.remove(xpath)
            except OSError:
                pass

        fetch_abort_function = self.pkgmeta.get('fetch_abort_function')
        filepath_dir = os.path.dirname(save_path)
        # symlink support
        if not os.path.isdir(os.path.realpath(filepath_dir)):
            try:
                os.remove(filepath_dir)
            except OSError:
                pass
            os.makedirs(filepath_dir, 0o755)

        rc, data_transfer = self.__try_edelta_fetch(url, save_path, resume)
        if rc == 0:
            return rc, data_transfer, False
        elif rc < 0: # < 0 errors are unrecoverable
            return rc, data_transfer, False
        # otherwise, just fallback to package download

        existed_before = False
        if os.path.isfile(save_path) and os.path.exists(save_path):
            existed_before = True

        fetch_intf = self._entropy.urlFetcher(url, save_path, resume = resume,
            abort_check_func = fetch_abort_function)
        if (download is not None) and (package_id is not None) and \
            (repository is not None):
            fetch_path = self.__get_fetch_disk_path(download)
            self._setup_differential_download(self._entropy.urlFetcher, url,
                resume, fetch_path, repository, package_id)

        # start to download
        data_transfer = 0
        resumed = False
        try:
            fetch_checksum = fetch_intf.download()
            data_transfer = fetch_intf.get_transfer_rate()
            resumed = fetch_intf.is_resumed()
        except KeyboardInterrupt:
            return -100, data_transfer, resumed
        except NameError:
            raise
        except:
            if etpUi['debug']:
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
        if fetch_checksum == "-3":
            # not found
            return -3, data_transfer, resumed
        elif fetch_checksum == "-4":
            # timeout
            return -4, data_transfer, resumed

        del fetch_intf

        if digest and (fetch_checksum != digest):
            # not properly downloaded
            if (not existed_before) or (not resume):
                do_stfu_rm(save_path)
            return -2, data_transfer, resumed

        return 0, data_transfer, resumed


    def _download_package(self, package_id, repository, download, save_path,
        digest = False, resume = True):

        avail_data = self._settings['repositories']['available']
        excluded_data = self._settings['repositories']['excluded']
        repo_db = self._entropy.open_repository(repository)
        # grab original repo, if any and use it if available
        # this is done in order to support "equo repo merge" feature
        # allowing client-side repository package metadata moves.
        original_repo = repo_db.getInstalledPackageRepository(package_id)
        if original_repo in avail_data:
            uris = avail_data[original_repo]['packages'][::-1]
            uris += avail_data[repository]['packages'][::-1]
        elif original_repo in excluded_data:
            uris = excluded_data[original_repo]['packages'][::-1]
            uris += avail_data[repository]['packages'][::-1]
        else:
            uris = avail_data[repository]['packages'][::-1]
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
                try:
                    mytxt = mirror_count_txt
                    mytxt += blue("%s: ") % (_("Downloading from"),)
                    mytxt += red(self._get_url_name(uri))
                    # now fetch the new one
                    self._entropy.output(
                        mytxt,
                        importance = 1,
                        level = "warning",
                        header = red("   ## ")
                    )
                    rc, data_transfer, resumed = \
                        self.__fetch_file(
                                url,
                                save_path,
                                download = download,
                                package_id = package_id,
                                repository = repository,
                                digest = digest,
                                resume = do_resume
                            )
                    if rc == 0:
                        mytxt = mirror_count_txt
                        mytxt += "%s: " % (
                            blue(_("Successfully downloaded from")),
                        )
                        mytxt += red(self._get_url_name(uri))
                        human_bytes = entropy.tools.bytes_into_human(
                            data_transfer)
                        mytxt += " %s %s/%s" % (_("at"),
                            human_bytes, _("second"),)
                        self._entropy.output(
                            mytxt,
                            importance = 1,
                            level = "info",
                            header = red("   ## ")
                        )

                        mirror_status.set_working_mirror(None)
                        return 0
                    elif resumed and (rc not in (-3, -4, -100,)):
                        do_resume = False
                        continue
                    else:
                        error_message = mirror_count_txt
                        error_message += blue("%s: %s") % (
                            _("Error downloading from"),
                            red(self._get_url_name(uri)),
                        )
                        # something bad happened
                        if rc == -1:
                            error_message += " - %s." % (
                                _("file not available on this mirror"),)
                        elif rc == -2:
                            mirror_status.add_failing_mirror(uri, 1)
                            error_message += " - %s." % (_("wrong checksum"),)
                            # If file is fetched (with no resume) and its complete
                            # better to enforce resume to False.
                            if (data_transfer < 1) and do_resume:
                                error_message += " %s." % (
                                    _("Disabling resume"),)
                                do_resume = False
                                continue
                        elif rc == -3:
                            mirror_status.add_failing_mirror(uri, 3)
                            error_message += " - %s." % (_("not found"),)
                        elif rc == -4: # timeout!
                            timeout_try_count -= 1
                            if timeout_try_count > 0:
                                error_message += " - %s." % (
                                    _("timeout, retrying on this mirror"),)
                            else:
                                error_message += " - %s." % (
                                    _("timeout, giving up"),)
                        elif rc == -100:
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
                        if rc == -4: # timeout
                            if timeout_try_count > 0:
                                continue
                        elif rc == -100: # user discarded fetch
                            mirror_status.set_working_mirror(None)
                            return 1
                        remaining.discard(uri)
                        # make sure we don't have nasty issues
                        if not remaining:
                            mirror_status.set_working_mirror(None)
                            return 3
                        break
                except KeyboardInterrupt:
                    mirror_status.set_working_mirror(None)
                    return 1

        mirror_status.set_working_mirror(None)
        return 0

    def _match_checksum(self, package_id, repository, checksum, download,
        signatures):

        sys_settings = self._settings
        sys_set_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        enabled_hashes = sys_settings[sys_set_plg_id]['misc']['packagehashes']

        pkg_disk_path = self.__get_fetch_disk_path(download)
        pkg_disk_path_mtime = pkg_disk_path + etpConst['packagemtimefileext']

        def do_mtime_validation():
            if not (os.path.isfile(pkg_disk_path_mtime) and \
                os.access(pkg_disk_path_mtime, os.R_OK)):
                return 1
            if not (os.path.isfile(pkg_disk_path) and \
                os.access(pkg_disk_path, os.R_OK)):
                return 2

            with open(pkg_disk_path_mtime, "r") as mt_f:
                stored_mtime = mt_f.read().strip()

            # get pkg mtime
            cur_mtime = str(os.path.getmtime(pkg_disk_path))
            if cur_mtime == stored_mtime:
                return 0
            return 1

        def do_store_mtime():
            if not (os.path.isfile(pkg_disk_path) and \
                os.access(pkg_disk_path, os.R_OK)):
                return
            with open(pkg_disk_path_mtime, "w") as mt_f:
                cur_mtime = str(os.path.getmtime(pkg_disk_path))
                mt_f.write(cur_mtime)
                mt_f.flush()

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
            tmp_fd, tmp_path = tempfile.mkstemp()
            with os.fdopen(tmp_fd, "wb") as tmp_f:
                tmp_f.write(hash_val)
                tmp_f.flush()

            try:
                # actually verify
                valid, err_msg = repo_sec.verify_file(repository, pkg_path,
                    tmp_path)
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
                        "%s: %s" % (blue(_("Checking package signature")),
                            purple(hash_type.upper()),),
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

            dlcheck = self.__check_pkg_path_download(download,
                checksum = checksum)
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
                    self.pkgmeta['verified'] = True
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
            mytxt = _("Cannot fetch package or checksum does not match")
            mytxt2 = _("Try to download latest repositories")
            for txt in (mytxt, mytxt2,):
                self._entropy.output(
                    "%s." % (blue(txt),),
                    importance = 0,
                    level = "info",
                    header = red("   ## ")
                )
            return 1

        return 0

    def multi_match_checksum(self):
        rc = 0
        for pkg_id, repository, download, digest, signatures in \
            self.pkgmeta['multi_checksum_list']:

            rc = self._match_checksum(pkg_id, repository, digest, download,
                signatures)
            if rc != 0:
                break

        return rc

    def __unpack_package(self):

        if not self.pkgmeta['merge_from']:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Unpacking package: %s" % (self.pkgmeta['atom'],)
            )
        else:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Merging package: %s" % (self.pkgmeta['atom'],)
            )

        unpack_dir = self.pkgmeta['unpackdir']
        unpack_dir_raw = self.pkgmeta['unpackdir'].encode('raw_unicode_escape')

        if os.path.isdir(unpack_dir):
            shutil.rmtree(unpack_dir_raw)
        elif os.path.isfile(unpack_dir):
            os.remove(unpack_dir_raw)
        os.makedirs(self.pkgmeta['imagedir'])

        if not os.path.isfile(self.pkgmeta['pkgpath']) and \
            not self.pkgmeta['merge_from']:

            if os.path.isdir(self.pkgmeta['pkgpath']):
                shutil.rmtree(self.pkgmeta['pkgpath'])
            if os.path.islink(self.pkgmeta['pkgpath']):
                os.remove(self.pkgmeta['pkgpath'])
            self.pkgmeta['verified'] = False
            rc = self._fetch_step()
            if rc != 0:
                return rc

        if not self.pkgmeta['merge_from']:

            # extract entropy database from package file
            # in order to avoid having to read content data
            # from the repository database, which, in future
            # is allowed to not provide such info.
            pkg_dbdir = os.path.dirname(self.pkgmeta['pkgdbpath'])
            if not os.path.isdir(pkg_dbdir):
                os.makedirs(pkg_dbdir, 0o755)

            # extract edb
            entropy.tools.dump_entropy_metadata(self.pkgmeta['pkgpath'],
                self.pkgmeta['pkgdbpath'])

            unpack_tries = 3
            while True:
                unpack_tries -= 1
                try:
                    rc = entropy.tools.spawn_function(
                        entropy.tools.uncompress_tarball,
                        self.pkgmeta['pkgpath'],
                        extract_path = self.pkgmeta['imagedir'],
                        catch_empty = True
                    )
                except EOFError:
                    self._entropy.logger.log(
                        "[Package]", etpConst['logging']['normal_loglevel_id'], 
                        "EOFError on " + self.pkgmeta['pkgpath']
                    )
                    rc = 1
                except:
                    # this will make devs to actually catch the
                    # right exception and prepare a fix
                    self._entropy.logger.log(
                        "[Package]",
                        etpConst['logging']['normal_loglevel_id'],
                        "Raising Unicode/Pickling Error for " + \
                            self.pkgmeta['pkgpath']
                    )
                    rc = entropy.tools.uncompress_tarball(
                        self.pkgmeta['pkgpath'],
                        extract_path = self.pkgmeta['imagedir'],
                        catch_empty = True
                    )
                if rc == 0:
                    break

                if unpack_tries <= 0:
                    return rc
                # otherwise, try to download it again
                self.pkgmeta['verified'] = False
                f_rc = self._fetch_step()
                if f_rc != 0:
                    return f_rc

        else:

            pid = os.fork()
            if pid > 0:
                os.waitpid(pid, 0)
            else:
                self.__fill_image_dir(self.pkgmeta['merge_from'],
                    self.pkgmeta['imagedir'])
                os._exit(0)

        spm_class = self._entropy.Spm_class()
        # call Spm unpack hook
        return spm_class.entropy_install_unpack_hook(self._entropy, self.pkgmeta)


    def __configure_package(self):

        try:
            Spm = self._entropy.Spm()
        except Exception as err:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Source Package Manager not available: %s | %s" % (
                    type(Exception), err,
                )
            )
            return 1

        self._entropy.output(
            "SPM: %s" % (brown(_("configuration phase")),),
            importance = 0,
            header = red("   ## ")
        )
        return Spm.execute_package_phase(self.pkgmeta, "configure")


    def __remove_package(self):

        self._entropy.clear_cache()

        self._entropy.logger.log("[Package]",
            etpConst['logging']['normal_loglevel_id'],
                "Removing package: %s" % (self.pkgmeta['removeatom'],))

        mytxt = "%s: %s" % (
            blue(_("Removing from Entropy")),
            red(self.pkgmeta['removeatom']),
        )
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        automerge_metadata = \
            self._entropy.installed_repository().retrieveAutomergefiles(
                self.pkgmeta['removeidpackage'], get_dict = True
            )
        self._entropy.installed_repository().removePackage(
            self.pkgmeta['removeidpackage'], do_commit = False,
            do_cleanup = False)

        # commit changes, to avoid users pressing CTRL+C and still having
        # all the db entries in, so we need to commit at every iteration
        self._entropy.installed_repository().commit()

        self._remove_content_from_system(self.pkgmeta['removeidpackage'],
            automerge_metadata)

        return 0

    def _remove_content_from_system(self, installed_package_id,
        automerge_metadata = None):
        """
        Remove installed package content (files/directories) from live system.

        @param installed_package_id: Entropy Repository package identifier
        @type installed_package_id: int
        @keyword automerge_metadata: Entropy "automerge metadata"
        @type automerge_metadata: dict
        """
        if automerge_metadata is None:
            automerge_metadata = {}

        sys_root = etpConst['systemroot']
        # load CONFIG_PROTECT and CONFIG_PROTECT_MASK
        sys_settings = self._settings
        protect = self.__get_installed_package_config_protect(
            installed_package_id)
        mask = self.__get_installed_package_config_protect(installed_package_id,
            mask = True)

        sys_set_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        col_protect = sys_settings[sys_set_plg_id]['misc']['collisionprotect']

        # remove files from system
        directories = set()
        directories_cache = set()
        not_removed_due_to_collisions = set()
        colliding_path_messages = set()

        remove_content = sorted(self.pkgmeta['removecontent'], reverse = True)
        for item in remove_content:

            if not item:
                continue # empty element??

            sys_root_item = sys_root + item

            # collision check
            if col_protect > 0:

                if self._entropy.installed_repository().isFileAvailable(item) \
                    and os.path.isfile(sys_root_item):

                    # in this way we filter out directories
                    colliding_path_messages.add(sys_root_item)
                    not_removed_due_to_collisions.add(item)
                    continue

            protected = False
            in_mask = False

            if (not self.pkgmeta['removeconfig']) and \
                (not self.pkgmeta['diffremoval']):

                protected_item_test = sys_root_item
                if const_isunicode(protected_item_test):
                    protected_item_test = protected_item_test.encode('utf-8')

                in_mask, protected, x, do_continue = \
                    self._handle_config_protect(
                        protect, mask, None, protected_item_test,
                        do_allocation_check = False, do_quiet = True
                    )

                if do_continue:
                    protected = True

            # when files have not been modified by the user
            # and they are inside a config protect directory
            # we could even remove them directly
            if in_mask:

                oldprot_md5 = automerge_metadata.get(item)
                if oldprot_md5 and os.path.exists(protected_item_test) and \
                    os.access(protected_item_test, os.R_OK):

                    in_system_md5 = entropy.tools.md5sum(
                        protected_item_test)

                    if oldprot_md5 == in_system_md5:
                        prot_msg = _("Removing config file, never modified")
                        mytxt = "%s: %s" % (
                            darkgreen(prot_msg),
                            blue(item),
                        )
                        self._entropy.output(
                            mytxt,
                            importance = 1,
                            level = "info",
                            header = red("   ## ")
                        )
                        protected = False
                        do_continue = False

            # Is file or directory a protected item?
            if protected:
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['verbose_loglevel_id'],
                    "[remove] Protecting config file: %s" % (sys_root_item,)
                )
                mytxt = "[%s] %s: %s" % (
                    red(_("remove")),
                    brown(_("Protecting config file")),
                    sys_root_item,
                )
                self._entropy.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = red("   ## ")
                )
                continue


            try:
                os.lstat(sys_root_item)

            except OSError:
                continue # skip file, does not exist

            except UnicodeEncodeError:
                msg = _("This package contains a badly encoded file !!!")
                mytxt = brown(msg)
                self._entropy.output(
                    red("QA: ")+mytxt,
                    importance = 1,
                    level = "warning",
                    header = darkred("   ## ")
                )
                continue # file has a really bad encoding

            if os.path.isdir(sys_root_item) and \
                os.path.islink(sys_root_item):
                # S_ISDIR returns False for directory symlinks,
                # so using os.path.isdir valid directory symlink
                if sys_root_item not in directories_cache:
                    directories.add((sys_root_item, "link"))
                    directories_cache.add(sys_root_item)
                continue

            if os.path.isdir(sys_root_item):
                # plain directory
                if sys_root_item not in directories_cache:
                    directories.add((sys_root_item, "dir"))
                    directories_cache.add(sys_root_item)
                continue

            # files, symlinks or not
            # just a file or symlink or broken
            # directory symlink (remove now)

            try:
                os.remove(sys_root_item)
            except OSError as err:
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "[remove] Unable to remove %s, error: %s" % (
                        sys_root_item, err,)
                )
                continue

            # add its parent directory
            dirobj = os.path.dirname(sys_root_item)
            if dirobj not in directories_cache:
                if os.path.isdir(dirobj) and os.path.islink(dirobj):
                    directories.add((dirobj, "link"))
                elif os.path.isdir(dirobj):
                    directories.add((dirobj, "dir"))

                directories_cache.add(dirobj)


        if colliding_path_messages:
            self._entropy.output(
                "%s:" % (_("Collision found during removal of"),),
                importance = 1,
                level = "warning",
                header = red("   ## ")
            )

        for path in sorted(colliding_path_messages):
            self._entropy.output(
                purple(path),
                importance = 0,
                level = "warning",
                header = red("   ## ")
            )
            self._entropy.logger.log("[Package]", etpConst['logging']['normal_loglevel_id'],
                "Collision found during removal of %s - cannot overwrite" % (
                    path,)
            )

        # removing files not removed from removecontent.
        # it happened that boot services not removed due to
        # collisions got removed from their belonging runlevels
        # by postremove step.
        # since this is a set, it is a mapped type, so every
        # other instance around will feature this update
        self.pkgmeta['removecontent'] -= not_removed_due_to_collisions

        # now handle directories
        directories = sorted(directories, reverse = True)
        while True:
            taint = False
            for directory, dirtype in directories:
                mydir = "%s%s" % (sys_root, directory,)
                if dirtype == "link":
                    try:
                        mylist = os.listdir(mydir)
                        if not mylist:
                            try:
                                os.remove(mydir)
                                taint = True
                            except OSError:
                                pass
                    except OSError:
                        pass
                elif dirtype == "dir":
                    try:
                        mylist = os.listdir(mydir)
                        if not mylist:
                            try:
                                os.rmdir(mydir)
                                taint = True
                            except OSError:
                                pass
                    except OSError:
                        pass

            if not taint:
                break

        del directories_cache
        del directories

    def _cleanup_package(self, unpack_dir):
        # shutil.rmtree wants raw strings... otherwise it will explode
        if const_isunicode(unpack_dir):
            unpack_dir = unpack_dir.encode('raw_unicode_escape')

        # remove unpack dir
        try:
            shutil.rmtree(unpack_dir, True)
        except Exception as err:
            # fault tolerance here dude
            self._entropy.logger.log(
                "[Package]", etpConst['logging']['normal_loglevel_id'],
                "WARNING!!! Failed to cleanup directory %s," \
                " error: %s" % (unpack_dir, err,))
        try:
            os.rmdir(unpack_dir)
        except OSError:
            pass
        return 0

    def __install_package(self):

        # clear on-disk cache
        self._entropy.clear_cache()

        self._entropy.logger.log(
            "[Package]",
            etpConst['logging']['normal_loglevel_id'],
            "Installing package: %s" % (self.pkgmeta['atom'],)
        )

        if self.pkgmeta['removeidpackage'] != -1:
            self.pkgmeta['already_protected_config_files'] = \
                self._entropy.installed_repository().retrieveAutomergefiles(
                    self.pkgmeta['removeidpackage'], get_dict = True
                )

        # copy files over - install
        # use fork? (in this case all the changed structures
        # need to be pushed back)
        rc = self._move_image_to_system()
        if rc != 0:
            return rc

        # inject into database
        mytxt = "%s: %s" % (
            blue(_("Updating database")),
            red(self.pkgmeta['atom']),
        )
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        self.pkgmeta['installed_package_id'] = self._add_installed_package()
        return 0

    def _spm_install_package(self, installed_package_id):
        """
        Call Source Package Manager interface and tell it to register our
        newly installed package.

        @param installed_package_id: Entropy repository package identifier
        @type installed_package_id: int
        @return: execution status
        @rtype: int
        """
        try:
            Spm = self._entropy.Spm()
        except Exception as err:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Source Package Manager not available: %s | %s" % (
                    type(Exception), err,
                )
            )
            return -1

        self._entropy.logger.log(
            "[Package]",
            etpConst['logging']['normal_loglevel_id'],
            "Installing new SPM entry: %s" % (self.pkgmeta['atom'],)
        )

        spm_uid = Spm.add_installed_package(self.pkgmeta)
        if spm_uid != -1:
            self._entropy.installed_repository().insertSpmUid(
                installed_package_id, spm_uid)

        return 0

    def _spm_update_package_uid(self, installed_package_id, entropy_atom):
        """
        Update Source Package Manager <-> Entropy package identifiers coupling.
        Entropy can handle multiple packages in the same scope from a SPM POV
        (see the "package tag" feature to provide linux kernel module packages
        for different kernel versions). This method just reassigns a new SPM
        unique package identifier to Entropy.

        @param installed_package_id: Entropy package identifier bound to
            given entropy_atom
        @type installed_package_id: int
        @param entropy_atom: Entropy package atom, must be converted to a valid
            SPM package atom.
        @type entropy_atom: string
        @return: execution status
        @rtype: int
        """
        try:
            Spm = self._entropy.Spm()
        except Exception as err:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Source Package Manager not available: %s | %s" % (
                    type(Exception), err,
                )
            )
            return -1

        spm_package = Spm.convert_from_entropy_package_name(entropy_atom)
        try:
            spm_uid = Spm.assign_uid_to_installed_package(spm_package)
        except (SPMError, KeyError,):
            # installed package not available, we must ignore it
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Spm uid not available for Spm package: %s (pkg not avail?)" % (
                    spm_package,
                )
            )
            return 0

        if spm_uid != -1:
            self._entropy.installed_repository().insertSpmUid(
                installed_package_id, spm_uid)

        return 0


    def _spm_remove_package(self):
        """
        Call Source Package Manager interface and tell it to remove our
        just removed package.

        @return: execution status
        @rtype: int
        """
        try:
            Spm = self._entropy.Spm()
        except Exception as err:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Source Package Manager not available: %s | %s" % (
                    type(Exception), err,
                )
            )
            return -1

        self._entropy.logger.log(
            "[Package]",
            etpConst['logging']['normal_loglevel_id'],
            "Removing from SPM: %s" % (self.pkgmeta['removeatom'],)
        )

        return Spm.remove_installed_package(self.pkgmeta)


    def _add_installed_package(self):
        """
        For internal use only.
        Copy package from repository to installed packages one.
        """

        # fetch info
        smart_pkg = self.pkgmeta['smartpackage']
        dbconn = self._entropy.open_repository(self.pkgmeta['repository'])

        if smart_pkg or self.pkgmeta['merge_from']:

            data = dbconn.getPackageData(self.pkgmeta['idpackage'],
                content_insert_formatted = True, get_changelog = False)

            if self.pkgmeta['removeidpackage'] != -1:
                self.pkgmeta['removecontent'].update(
                    self._entropy.installed_repository().contentDiff(
                        self.pkgmeta['removeidpackage'],
                        dbconn,
                        self.pkgmeta['idpackage']
                    )
                )

        else:

            # normal repositories
            data = dbconn.getPackageData(self.pkgmeta['idpackage'],
                get_content = False, get_changelog = False)

            # indexing_override = False : no need to index tables
            # xcache = False : no need to use on-disk cache
            # skipChecks = False : creating missing tables is unwanted,
            # and also no foreign keys update
            # readOnly = True: no need to open in write mode
            pkg_dbconn = self._entropy.open_generic_repository(
                self.pkgmeta['pkgdbpath'], skip_checks = True,
                indexing_override = False, read_only = True,
                xcache = False)

            # it is safe to consider that package dbs coming from repos
            # contain only one entry
            pkg_idpackage = sorted(pkg_dbconn.listAllPackageIds(),
                reverse = True)[0]
            content = pkg_dbconn.retrieveContent(
                pkg_idpackage, extended = True,
                formatted = True, insert_formatted = True
            )
            real_idpk = self.pkgmeta['idpackage']
            content = [(real_idpk, x, y,) for orig_idpk, x, y in content]
            data['content'] = content

            # setup content safety metadata, get from package
            data['content_safety'] = pkg_dbconn.retrieveContentSafety(
                pkg_idpackage)

            if self.pkgmeta['removeidpackage'] != -1:
                self.pkgmeta['removecontent'].update(
                    self._entropy.installed_repository().contentDiff(
                        self.pkgmeta['removeidpackage'],
                        pkg_dbconn,
                        pkg_idpackage
                    )
                )

            pkg_dbconn.close()

        # fix removecontent, need to check if we just installed files
        # that resolves at the same directory path (different symlink)
        my_remove_content = self.__filter_out_files_installed_on_diff_path(
            self.pkgmeta['removecontent'], self.pkgmeta['__items_installed'])
        self.pkgmeta['removecontent'] -= my_remove_content

        # filter out files not installed from content metadata
        self.__filter_out_items_not_installed_from_content(data)

        # this is needed to make postinstall trigger to work properly
        trigger_content = set((x[1] for x in data['content']))
        self.pkgmeta['triggers']['install']['content'] = trigger_content

        # open client db
        # always set data['injected'] to False
        # installed packages database SHOULD never have more
        # than one package for scope (key+slot)
        data['injected'] = False
        # spm counter will be set in self._install_package_into_spm_database()
        data['counter'] = -1
        # branch must be always set properly, it could happen it's not
        # when installing packages through their .tbz2s
        data['branch'] = self._settings['repositories']['branch']
        # there is no need to store needed paths into db
        if "needed_paths" in data:
            del data['needed_paths']
        # there is no need to store changelog data into db
        if "changelog" in data:
            del data['changelog']

        inst_repo = self._entropy.installed_repository()

        idpackage, rev, x = inst_repo.handlePackage(data,
            forcedRevision = data['revision'], formattedContent = True)

        # update datecreation
        ctime = time.time()
        inst_repo.setCreationDate(idpackage, str(ctime))

        # add idpk to the installedtable
        inst_repo.dropInstalledPackageFromStore(idpackage)
        inst_repo.storeInstalledPackage(idpackage,
            self.pkgmeta['repository'], self.pkgmeta['install_source'])

        automerge_data = self.pkgmeta.get('configprotect_data')
        if automerge_data:
            inst_repo.insertAutomergefiles(idpackage, automerge_data)

        return idpackage

    def __filter_out_items_not_installed_from_content(self, pkg_data):

        items_not_installed = self.pkgmeta.get('items_not_installed', set())

        # CONTENT metadata getting here is always already formatted
        # for EntropyRepository insertion
        def filter_content(content_item):
            pkg_id, pkg_path, path_type = content_item
            return pkg_path not in items_not_installed

        pkg_data['content'] = filter(filter_content, pkg_data['content'])

    def __fill_image_dir(self, merge_from, image_dir):

        dbconn = self._entropy.open_repository(self.pkgmeta['repository'])
        # this is triggered by merge_from pkgmeta metadata
        # even if repositories are allowed to not have content
        # metadata, in this particular case, it is mandatory
        package_content = dbconn.retrieveContent(
            self.pkgmeta['idpackage'], extended = True, formatted = True)
        contents = sorted(package_content)

        # collect files
        for path in contents:
            # convert back to filesystem str
            encoded_path = path
            path = os.path.join(merge_from, encoded_path[1:])
            topath = os.path.join(image_dir, encoded_path[1:])
            path = path.encode('raw_unicode_escape')
            topath = topath.encode('raw_unicode_escape')

            try:
                exist = os.lstat(path)
            except OSError:
                continue # skip file
            ftype = package_content[encoded_path]

            if 'dir' == ftype and \
                not stat.S_ISDIR(exist.st_mode) and \
                os.path.isdir(path):
                # workaround for directory symlink issues
                path = os.path.realpath(path)

            copystat = False
            # if our directory is a symlink instead, then copy the symlink
            if os.path.islink(path):
                tolink = os.readlink(path)
                if os.path.islink(topath):
                    os.remove(topath)
                os.symlink(tolink, topath)
            elif os.path.isdir(path):
                if not os.path.isdir(topath):
                    os.makedirs(topath)
                    copystat = True
            elif os.path.isfile(path):
                if os.path.isfile(topath):
                    os.remove(topath) # should never happen
                shutil.copy2(path, topath)
                copystat = True

            if copystat:
                user = os.stat(path)[stat.ST_UID]
                group = os.stat(path)[stat.ST_GID]
                os.chown(topath, user, group)
                shutil.copystat(path, topath)

    def __get_package_match_config_protect(self, mask = False):

        idpackage, repoid = self._package_match
        dbconn = self._entropy.open_repository(repoid)
        cl_id = etpConst['system_settings_plugins_ids']['client_plugin']
        misc_data = self._settings[cl_id]['misc']
        if mask:
            config_protect = set(dbconn.retrieveProtectMask(idpackage).split())
            config_protect |= set(misc_data['configprotectmask'])
        else:
            config_protect = set(dbconn.retrieveProtect(idpackage).split())
            config_protect |= set(misc_data['configprotect'])
        config_protect = [etpConst['systemroot']+x for x in config_protect]

        return sorted(config_protect)

    def __get_installed_package_config_protect(self, installed_package_id,
        mask = False):

        inst_repo = self._entropy.installed_repository()
        if inst_repo is None:
            return []

        cl_id = etpConst['system_settings_plugins_ids']['client_plugin']
        misc_data = self._settings[cl_id]['misc']
        if mask:
            _pmask = inst_repo.retrieveProtectMask(installed_package_id).split()
            config_protect = set(_pmask)
            config_protect |= set(misc_data['configprotectmask'])
        else:
            _protect = inst_repo.retrieveProtect(installed_package_id).split()
            config_protect = set(_protect)
            config_protect |= set(misc_data['configprotect'])
        config_protect = [etpConst['systemroot']+x for x in config_protect]

        return sorted(config_protect)

    def __get_sys_root(self):
        return self.pkgmeta.get('unittest_root', '') + \
            etpConst['systemroot']

    def _move_image_to_system(self):

        # load CONFIG_PROTECT and its mask
        protect = self.__get_package_match_config_protect()
        mask = self.__get_package_match_config_protect(mask = True)

        # support for unit testing settings
        sys_root = self.__get_sys_root()
        sys_set_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        misc_data = self._settings[sys_set_plg_id]['misc']
        col_protect = misc_data['collisionprotect']
        splitdebug, splitdebug_dirs = self.pkgmeta['splitdebug'], \
            self.pkgmeta['splitdebug_dirs']
        items_installed = set()
        self.pkgmeta['items_not_installed'] = set()

        # setup image_dir properly
        image_dir = self.pkgmeta['imagedir'][:]
        if sys.hexversion < 0x3000000:
            image_dir = image_dir.encode('utf-8')
        movefile = entropy.tools.movefile

        def workout_subdir(currentdir, subdir):

            imagepath_dir = os.path.join(currentdir, subdir)
            rootdir = sys_root + imagepath_dir[len(image_dir):]

            # splitdebug (.debug files) support
            # If splitdebug is not enabled, do not create splitdebug directories
            # and move on instead (return)
            if not splitdebug:
                for split_dir in splitdebug_dirs:
                    if rootdir.startswith(split_dir):
                        # also drop item from content metadata. In this way
                        # SPM has in sync information on what the package
                        # content really is.
                        self.pkgmeta['items_not_installed'].add(rootdir)
                        return

            # handle broken symlinks
            if os.path.islink(rootdir) and not os.path.exists(rootdir):
                # broken symlink
                os.remove(rootdir)

            # if our directory is a file on the live system
            elif os.path.isfile(rootdir): # really weird...!

                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! %s is a file when it should be " \
                    "a directory !! Removing in 20 seconds..." % (rootdir,)
                )
                mytxt = darkred(_("%s is a file when should be a " \
                "directory !! Removing in 20 seconds...") % (rootdir,))

                self._entropy.output(
                    red("QA: ")+mytxt,
                    importance = 1,
                    level = "warning",
                    header = red(" !!! ")
                )
                os.remove(rootdir)

            # if our directory is a symlink instead, then copy the symlink
            if os.path.islink(imagepath_dir):

                # if our live system features a directory instead of
                # a symlink, we should consider removing the directory
                if not os.path.islink(rootdir) and os.path.isdir(rootdir):
                    self._entropy.logger.log(
                        "[Package]",
                        etpConst['logging']['normal_loglevel_id'],
                        "WARNING!!! %s is a directory when it should be " \
                        "a symlink !! Removing in 20 seconds..." % (
                            rootdir,)
                    )
                    mytxt = "%s: %s" % (
                        _("directory expected, symlink found"),
                        rootdir,
                    )
                    mytxt2 = _("Removing in 20 seconds !!")
                    for txt in (mytxt, mytxt2,):
                        self._entropy.output(
                            darkred("QA: ") + darkred(txt),
                            importance = 1,
                            level = "warning",
                            header = red(" !!! ")
                        )

                    # fucking kill it in any case!
                    # rootdir must die! die die die die!
                    # /me brings chainsaw
                    try:
                        shutil.rmtree(rootdir, True)
                    except (shutil.Error, OSError,) as err:
                        self._entropy.logger.log(
                            "[Package]",
                            etpConst['logging']['normal_loglevel_id'],
                            "WARNING!!! Failed to rm %s " \
                            "directory ! [workout_subdir/1]: %s" % (
                                rootdir, err,
                            )
                        )

                tolink = os.readlink(imagepath_dir)
                live_tolink = None
                if os.path.islink(rootdir):
                    live_tolink = os.readlink(rootdir)

                if tolink != live_tolink:
                    _symfail = False
                    if os.path.lexists(rootdir):
                        # at this point, it must be a file
                        try:
                            os.remove(rootdir)
                        except OSError as err:
                            _symfail = True
                            # must be atomic, too bad if it fails
                            self._entropy.logger.log(
                                "[Package]",
                                etpConst['logging']['normal_loglevel_id'],
                                "WARNING!!! Failed to remove %s " \
                                "file ! [workout_file/0]: %s" % (
                                    rootdir, err,
                                )
                            )
                            msg = _("Cannot remove symlink")
                            mytxt = "%s: %s => %s" % (
                                purple(msg),
                                blue(rootdir),
                                repr(err),
                            )
                            self._entropy.output(
                                mytxt,
                                importance = 1,
                                level = "warning",
                                header = brown("   ## ")
                            )
                    if not _symfail:
                        os.symlink(tolink, rootdir)

            elif not os.path.isdir(rootdir) and not \
                os.access(rootdir, os.R_OK):
                # directory not found, we need to create it

                try:
                    # really force a simple mkdir first of all
                    os.mkdir(rootdir)
                except OSError:
                    os.makedirs(rootdir)


            if not os.path.islink(rootdir) and os.access(rootdir, os.W_OK):

                # symlink doesn't need permissions, also
                # until os.walk ends they might be broken
                # NOTE: also, added os.access() check because
                # there might be directories/files unwritable
                # what to do otherwise?
                user = os.stat(imagepath_dir)[stat.ST_UID]
                group = os.stat(imagepath_dir)[stat.ST_GID]
                os.chown(rootdir, user, group)
                shutil.copystat(imagepath_dir, rootdir)

            item_dir, item_base = os.path.split(rootdir)
            item_dir = os.path.realpath(item_dir)
            item_inst = os.path.join(item_dir, item_base)
            items_installed.add(item_inst)


        def workout_file(currentdir, item):

            fromfile = os.path.join(currentdir, item)
            tofile = sys_root + fromfile[len(image_dir):]

            # splitdebug (.debug files) support
            # If splitdebug is not enabled, do not create
            # splitdebug directories and move on instead (return)
            if not splitdebug:
                for split_dir in splitdebug_dirs:
                    if tofile.startswith(split_dir):
                        # also drop item from content metadata. In this way
                        # SPM has in sync information on what the package
                        # content really is.
                        self.pkgmeta['items_not_installed'].add(tofile)
                        return 0

            if col_protect > 1:
                todbfile = fromfile[len(image_dir):]
                myrc = self._handle_install_collision_protect(tofile,
                    todbfile)
                if not myrc:
                    return 0

            prot_old_tofile = tofile[len(sys_root):]
            pre_tofile = tofile[:]
            in_mask, protected, tofile, do_return = \
                self._handle_config_protect(protect, mask, fromfile, tofile)

            # collect new config automerge data
            if in_mask and os.path.exists(fromfile):
                try:
                    prot_md5 = entropy.tools.md5sum(fromfile)
                    self.pkgmeta['configprotect_data'].append(
                        (prot_old_tofile, prot_md5,))
                except (IOError,) as err:
                    self._entropy.logger.log(
                        "[Package]",
                        etpConst['logging']['normal_loglevel_id'],
                        "WARNING!!! Failed to get md5 of %s " \
                        "file ! [workout_file/1]: %s" % (
                            fromfile, err,
                        )
                    )

            # check if it's really necessary to protect file
            if protected:

                # second task
                oldprot_md5 = self.pkgmeta['already_protected_config_files'].get(
                    prot_old_tofile)

                if oldprot_md5 and os.path.exists(pre_tofile) and \
                    os.access(pre_tofile, os.R_OK):

                    try:
                        in_system_md5 = entropy.tools.md5sum(pre_tofile)
                    except (IOError,):
                        # which is a clearly invalid value
                        in_system_md5 = "0000"

                    if oldprot_md5 == in_system_md5:
                        # we can merge it, files, even if
                        # contains changes have not been modified
                        # by the user
                        msg = _("Automerging config file, never modified")
                        mytxt = "%s: %s" % (
                            darkgreen(msg),
                            blue(pre_tofile),
                        )
                        self._entropy.output(
                            mytxt,
                            importance = 1,
                            level = "info",
                            header = red("   ## ")
                        )
                        protected = False
                        do_return = False
                        tofile = pre_tofile

            if do_return:
                return 0

            try:
                from_r_path = os.path.realpath(fromfile)
            except RuntimeError:
                # circular symlink, fuck!
                # really weird...!
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! %s is a circular symlink !!!" % (fromfile,)
                )
                mytxt = "%s: %s" % (
                    _("Circular symlink issue"),
                    const_convert_to_unicode(fromfile),
                )
                self._entropy.output(
                    darkred("QA: ") + darkred(mytxt),
                    importance = 1,
                    level = "warning",
                    header = red(" !!! ")
                )
                from_r_path = fromfile

            try:
                to_r_path = os.path.realpath(tofile)
            except RuntimeError:
                # circular symlink, fuck!
                # really weird...!
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! %s is a circular symlink !!!" % (tofile,)
                )
                mytxt = "%s: %s" % (
                    _("Circular symlink issue"),
                    const_convert_to_unicode(tofile),
                )
                self._entropy.output(
                    darkred("QA: ") + darkred(mytxt),
                    importance = 1,
                    level = "warning",
                    header = red(" !!! ")
                )
                to_r_path = tofile

            if from_r_path == to_r_path and os.path.islink(tofile):
                # there is a serious issue here, better removing tofile,
                # happened to someone.

                try:
                    # try to cope...
                    os.remove(tofile)
                except (OSError, IOError,) as err:
                    self._entropy.logger.log(
                        "[Package]",
                        etpConst['logging']['normal_loglevel_id'],
                        "WARNING!!! Failed to cope to oddity of %s " \
                        "file ! [workout_file/2]: %s" % (
                            tofile, err,
                        )
                    )

            # if our file is a dir on the live system
            if os.path.isdir(tofile) and not os.path.islink(tofile):

                # really weird...!
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! %s is a directory when it should " \
                    "be a file !! Removing in 20 seconds..." % (tofile,)
                )

                mytxt = "%s: %s" % (
                    _("file expected, directory found"),
                    const_convert_to_unicode(tofile),
                )
                mytxt2 = _("Removing in 20 seconds !!")
                for txt in (mytxt, mytxt2,):
                    self._entropy.output(
                        darkred("QA: ") + darkred(txt),
                        importance = 1,
                        level = "warning",
                        header = red(" !!! ")
                    )

                try:
                    shutil.rmtree(tofile, True)
                except (shutil.Error, IOError,) as err:
                    self._entropy.logger.log(
                        "[Package]",
                        etpConst['logging']['normal_loglevel_id'],
                        "WARNING!!! Failed to cope to oddity of %s " \
                        "file ! [workout_file/3]: %s" % (
                            tofile, err,
                        )
                    )

            # moving file using the raw format
            try:
                done = movefile(fromfile, tofile,
                    src_basedir = image_dir)
            except (IOError,) as err:
                # try to move forward, sometimes packages might be
                # fucked up and contain broken things
                if err.errno not in (errno.ENOENT, errno.EACCES,):
                    raise

                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! Error during file move" \
                    " to system: %s => %s | IGNORED: %s" % (
                        const_convert_to_unicode(fromfile),
                        const_convert_to_unicode(tofile),
                        err,
                    )
                )
                done = True

            if not done:
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! Error during file move" \
                    " to system: %s => %s" % (fromfile, tofile,)
                )
                mytxt = "%s: %s => %s, %s" % (
                    _("File move error"),
                    const_convert_to_unicode(fromfile),
                    const_convert_to_unicode(tofile),
                    _("please report"),
                )
                self._entropy.output(
                    red("QA: ")+darkred(mytxt),
                    importance = 1,
                    level = "warning",
                    header = red(" !!! ")
                )
                return 4

            item_dir = os.path.realpath(os.path.dirname(tofile))
            item_inst = os.path.join(item_dir, os.path.basename(tofile))
            items_installed.add(item_inst)

            if protected:
                # add to disk cache
                file_updates = self._entropy.PackageFileUpdates()
                file_updates.add(tofile, quiet = True)

            return 0

        # merge data into system
        for currentdir, subdirs, files in os.walk(image_dir):

            # create subdirs
            for subdir in subdirs:
                workout_subdir(currentdir, subdir)

            for item in files:
                move_st = workout_file(currentdir, item)
                if move_st != 0:
                    return move_st

        # this is useful to avoid the removal of installed
        # files by __remove_package just because
        # there's a difference in the directory path, perhaps,
        # which is not handled correctly by
        # EntropyRepository.contentDiff for obvious reasons
        # (think about stuff in /usr/lib and /usr/lib64,
        # where the latter is just a symlink to the former)
        self.pkgmeta['__items_installed'] = items_installed
        if self.pkgmeta.get('removecontent'):
            my_remove_content = self.__filter_out_files_installed_on_diff_path(
                self.pkgmeta['removecontent'],
                self.pkgmeta['__items_installed'])
            self.pkgmeta['removecontent'] -= my_remove_content

        return 0

    def __filter_out_files_installed_on_diff_path(self, remove_content,
        installed_content):
        """
        Use case: if a package provided files in /lib then, a new version
        of that package moved the same files under /lib64, we need to check
        if both directory paths solve to the same inode and if so, add to our
        set that we're going to return.
        """
        sys_root = self.__get_sys_root()
        my_remove_content = set()
        for mypath in remove_content:

            if not mypath:
                continue # empty?

            item_dir = os.path.dirname("%s%s" % (sys_root, mypath,))
            item = os.path.join(os.path.realpath(item_dir),
                os.path.basename(mypath))

            if item in installed_content:
                my_remove_content.add(item)
                my_remove_content.add(mypath)

        return my_remove_content

    def _handle_config_protect(self, protect, mask, fromfile, tofile,
        do_allocation_check = True, do_quiet = False):
        """
        Handle configuration file protection. This method contains the logic
        for determining if a file should be protected from overwrite.
        """

        protected = False
        do_continue = False
        in_mask = False
        encoded_protect = [x.encode('raw_unicode_escape') for x in protect]

        if tofile in encoded_protect:
            protected = True
            in_mask = True

        elif os.path.dirname(tofile) in encoded_protect:
            protected = True
            in_mask = True

        else:
            tofile_testdir = os.path.dirname(tofile)
            old_tofile_testdir = None
            while tofile_testdir != old_tofile_testdir:
                if tofile_testdir in encoded_protect:
                    protected = True
                    in_mask = True
                    break
                old_tofile_testdir = tofile_testdir
                tofile_testdir = os.path.dirname(tofile_testdir)

        if protected: # check if perhaps, file is masked, so unprotected
            newmask = [x.encode('raw_unicode_escape') for x in mask]

            if tofile in newmask:
                protected = False
                in_mask = False

            elif os.path.dirname(tofile) in newmask:
                protected = False
                in_mask = False

            else:
                tofile_testdir = os.path.dirname(tofile)
                old_tofile_testdir = None
                while tofile_testdir != old_tofile_testdir:
                    if tofile_testdir in newmask:
                        protected = False
                        in_mask = False
                        break
                    old_tofile_testdir = tofile_testdir
                    tofile_testdir = os.path.dirname(tofile_testdir)

        if not os.path.lexists(tofile):
            protected = False # file doesn't exist

        # check if it's a text file
        if protected and os.path.isfile(tofile) and os.access(tofile, os.R_OK):
            protected = entropy.tools.istextfile(tofile)
            in_mask = protected
        else:
            protected = False # it's not a file

        if not protected:
            return in_mask, protected, tofile, do_continue

        ##                  ##
        # file is protected  #
        ##__________________##

        sys_set_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        client_settings = self._settings[sys_set_plg_id]
        misc_settings = client_settings['misc']

        # check if protection is disabled for this element
        if tofile in misc_settings['configprotectskip']:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Skipping config file installation/removal, " \
                "as stated in client.conf: %s" % (tofile,)
            )
            if not do_quiet:
                mytxt = "%s: %s" % (
                    _("Skipping file installation/removal"),
                    tofile,
                )
                self._entropy.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = darkred("   ## ")
                )
            do_continue = True
            return in_mask, protected, tofile, do_continue

        ##                      ##
        # file is protected (2)  #
        ##______________________##

        prot_status = True
        if do_allocation_check:
            spm_class = self._entropy.Spm_class()
            tofile, prot_status = spm_class.allocate_protected_file(fromfile,
                tofile)

        if not prot_status:
            # a protected file with the same content
            # is already in place, so not going to protect
            # the same file twice
            protected = False
            return in_mask, protected, tofile, do_continue

        ##                      ##
        # file is protected (3)  #
        ##______________________##

        oldtofile = tofile
        if oldtofile.find("._cfg") != -1:
            oldtofile = os.path.join(os.path.dirname(oldtofile),
                os.path.basename(oldtofile)[10:])

        if not do_quiet:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Protecting config file: %s" % (oldtofile,)
            )
            mytxt = red("%s: %s") % (_("Protecting config file"), oldtofile,)
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = darkred("   ## ")
            )

        return in_mask, protected, tofile, do_continue


    def _handle_install_collision_protect(self, tofile, todbfile):

        avail = self._entropy.installed_repository().isFileAvailable(
            const_convert_to_unicode(todbfile), get_id = True)

        if (self.pkgmeta['removeidpackage'] not in avail) and avail:
            mytxt = darkred(_("Collision found during install for"))
            mytxt += " %s - %s" % (
                blue(tofile),
                darkred(_("cannot overwrite")),
            )
            self._entropy.output(
                red("QA: ")+mytxt,
                importance = 1,
                level = "warning",
                header = darkred("   ## ")
            )
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "WARNING!!! Collision found during install " \
                "for %s - cannot overwrite" % (tofile,)
            )
            return False

        return True

    def _sources_fetch_step(self):

        down_data = self.pkgmeta['download']
        down_keys = list(down_data.keys())
        d_cache = set()
        rc = 0
        key_cache = [os.path.basename(x) for x in down_keys]

        for key in sorted(down_keys):

            key_name = os.path.basename(key)
            if key_name in d_cache:
                continue
            # first fine wins

            keyboard_interrupt = False
            for url in down_data[key]:

                file_name = os.path.basename(url)
                if self.pkgmeta.get('fetch_path'):
                    dest_file = os.path.join(self.pkgmeta['fetch_path'],
                        file_name)
                else:
                    dest_file = os.path.join(self.pkgmeta['unpackdir'],
                        file_name)

                try:
                    rc = self._fetch_source(url, dest_file)
                except KeyboardInterrupt:
                    keyboard_interrupt = True
                    break

                if rc == -100:
                    keyboard_interrupt = True
                    break

                if rc == 0:
                    d_cache.add(key_name)
                    break

            if keyboard_interrupt:
                rc = 1
                break

            key_cache.remove(key_name)
            if rc != 0 and key_name not in key_cache:
                break

            rc = 0

        return rc

    def _fetch_source(self, url, dest_file):
        rc = 1

        mytxt = "%s: %s" % (blue(_("Downloading")), brown(url),)
        # now fetch the new one
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        rc, data_transfer, resumed = self.__fetch_file(
            url,
            dest_file,
            digest = None,
            resume = False
        )
        if rc == 0:
            mytxt = blue("%s: ") % (_("Successfully downloaded from"),)
            mytxt += red(self._get_url_name(url))
            human_bytes = entropy.tools.bytes_into_human(data_transfer)
            mytxt += " %s %s/%s" % (_("at"), human_bytes, _("second"),)
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "info",
                header = red("   ## ")
            )
            self._entropy.output(
                "%s: %s" % (blue(_("Local path")), brown(dest_file),),
                importance = 1,
                level = "info",
                header = red("      # ")
            )
        else:
            error_message = blue("%s: %s") % (
                _("Error downloading from"),
                red(self._get_url_name(url)),
            )
            # something bad happened
            if rc == -1:
                error_message += " - %s." % (
                    _("file not available on this mirror"),
                )
            elif rc == -3:
                error_message += " - not found."
            elif rc == -100:
                error_message += " - %s." % (_("discarded download"),)
            else:
                error_message += " - %s: %s" % (_("unknown reason"), rc,)
            self._entropy.output(
                error_message,
                importance = 1,
                level = "warning",
                header = red("   ## ")
            )

        return rc

    def _fetch_step(self):

        mytxt = "%s: %s" % (blue(_("Downloading archive")),
            red(os.path.basename(self.pkgmeta['download'])),)
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        pkg_disk_path = self.__get_fetch_disk_path(self.pkgmeta['download'])

        rc = 0
        if not self.pkgmeta['verified']:

            rc = self._download_package(
                self.pkgmeta['idpackage'],
                self.pkgmeta['repository'],
                self.pkgmeta['download'],
                pkg_disk_path,
                self.pkgmeta['checksum']
            )

        if rc == 0:
            return 0

        mytxt = "%s. %s: %s" % (
            red(_("Package cannot be fetched. Try to update repositories")),
            blue(_("Error")),
            rc,
        )
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "error",
            header = darkred("   ## ")
        )

        return rc

    def _multi_fetch_step(self):

        m_fetch_len = len(self.pkgmeta['multi_fetch_list'])
        mytxt = "%s: %s %s" % (
            blue(_("Downloading")),
            darkred(str(m_fetch_len)),
            _("archives"),
        )

        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        rc, err_list = self._download_packages(
            self.pkgmeta['multi_fetch_list'],
            self.pkgmeta['checksum']
        )

        if rc == 0:
            return 0

        mytxt = _("Some packages cannot be fetched")
        mytxt2 = _("Try to update your repositories and retry")
        mytxt3 = "%s: %s" % (brown(_("Error")), bold(str(rc)),)
        for txt in (mytxt, mytxt2,):
            self._entropy.output(
                "%s." % (darkred(txt),),
                importance = 0,
                level = "info",
                header = red("   ## ")
            )
        self._entropy.output(
            mytxt3,
            importance = 0,
            level = "info",
            header = red("   ## ")
        )

        for pkg_id, repo, fname, cksum, signatures in err_list:
            self._entropy.output(
                "[%s|%s] %s" % (blue(repo), darkgreen(cksum), darkred(fname),),
                importance = 1,
                level = "error",
                header = darkred("    # ")
            )

        return rc

    def _fetch_not_available_step(self):
        self._entropy.output(
            blue(_("Package cannot be downloaded, unknown error.")),
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        return 0

    def _vanished_step(self):
        self._entropy.output(
            blue(_("Installed package in queue vanished, skipping.")),
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        return 0

    def _checksum_step(self):
        return self._match_checksum(self.pkgmeta['idpackage'],
            self.pkgmeta['repository'], self.pkgmeta['checksum'],
            self.pkgmeta['download'], self.pkgmeta['signatures'])

    def _multi_checksum_step(self):
        return self.multi_match_checksum()

    def _unpack_step(self):

        if not self.pkgmeta['merge_from']:
            mytxt = "%s: %s" % (
                blue(_("Unpacking package")),
                red(os.path.basename(self.pkgmeta['download'])),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "info",
                header = red("   ## ")
        )
        else:
            mytxt = "%s: %s" % (
                blue(_("Merging package")),
                red(os.path.basename(self.pkgmeta['atom'])),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "info",
                header = red("   ## ")
            )
        rc = self.__unpack_package()
        if rc != 0:
            if rc == 512:
                errormsg = "%s. %s. %s: 512" % (
                    red(_("You are running out of disk space")),
                    red(_("I bet, you're probably Michele")),
                    blue(_("Error")),
                )
            else:
                msg = _("An error occured while trying to unpack the package")
                errormsg = "%s. %s. %s: %s" % (
                    red(msg),
                    red(_("Check if your system is healthy")),
                    blue(_("Error")),
                    rc,
                )
            self._entropy.output(
                errormsg,
                importance = 1,
                level = "error",
                header = red("   ## ")
            )
        return rc

    def _install_step(self):
        mytxt = "%s: %s" % (
            blue(_("Installing package")),
            red(self.pkgmeta['atom']),
        )
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        if self.pkgmeta.get('description'):
            mytxt = "[%s]" % (purple(self.pkgmeta.get('description')),)
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "info",
                header = red("   ## ")
            )
        if self.pkgmeta['splitdebug']:
            mytxt = "[%s]" % (teal(_("<3 debug files installation enabled <3")),)
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "info",
                header = red("   ## ")
            )

        rc = self.__install_package()
        if rc != 0:
            mytxt = "%s. %s. %s: %s" % (
                red(_("An error occured while trying to install the package")),
                red(_("Check if your system is healthy")),
                blue(_("Error")),
                rc,
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "error",
                header = red("   ## ")
            )
        return rc

    def _remove_step(self):
        mytxt = "%s: %s" % (
            blue(_("Removing data")),
            red(self.pkgmeta['removeatom']),
        )
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        rc = self.__remove_package()
        if rc != 0:
            mytxt = "%s. %s. %s: %s" % (
                red(_("An error occured while trying to remove the package")),
                red(_("Check if you have enough disk space on your hard disk")),
                blue(_("Error")),
                rc,
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "error",
                header = red("   ## ")
            )
        return rc

    def _cleanup_step(self):
        mytxt = "%s: %s" % (
            blue(_("Cleaning")),
            red(self.pkgmeta['atom']),
        )
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        self._cleanup_package(self.pkgmeta['unpackdir'])
        # we don't care if cleanupPackage fails since it's not critical
        return 0

    def _post_install_step(self):
        pkgdata = self.pkgmeta['triggers'].get('install')
        if pkgdata:
            trigger = self._entropy.Triggers('postinstall', pkgdata, self._action)
            do = trigger.prepare()
            if do:
                trigger.run()
            trigger.kill()
        del pkgdata
        return 0

    def _pre_install_step(self):
        pkgdata = self.pkgmeta['triggers'].get('install')
        if pkgdata:

            trigger = self._entropy.Triggers('preinstall', pkgdata, self._action)
            do = trigger.prepare()
            if self.pkgmeta.get("diffremoval") and do:
                # diffremoval is true only when the
                # removal is triggered by a package install
                remdata = self.pkgmeta['triggers'].get('remove')
                if remdata:
                    r_trigger = self._entropy.Triggers('preremove', remdata,
                        self._action)
                    r_trigger.prepare()
                    r_trigger.triggers = [x for x in trigger.triggers if x \
                        not in r_trigger.triggers]
                    r_trigger.kill()
                del remdata
            if do:
                trigger.run()
            trigger.kill()

        del pkgdata
        return 0

    def _pre_remove_step(self):
        remdata = self.pkgmeta['triggers'].get('remove')
        if remdata:
            trigger = self._entropy.Triggers('preremove', remdata, self._action)
            do = trigger.prepare()
            if do:
                trigger.run()
                trigger.kill()
        del remdata
        return 0

    def _package_install_clean(self):
        """
        Cleanup package files not used anymore by newly installed version.
        This is part of the atomic install, which overwrites the live fs with
        new files and removes old afterwards.
        """
        self._entropy.output(
            blue(_("Cleaning previously installed application data.")),
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        self._remove_content_from_system(self.pkgmeta['removeidpackage'],
            automerge_metadata = self.pkgmeta['already_protected_config_files'])
        return 0

    def _post_remove_step_install(self):
        """
        Post-remove phase of package install, this step removes older SPM
        package entries from SPM db.
        """
        self._entropy.logger.log(
            "[Package]",
            etpConst['logging']['normal_loglevel_id'],
            "Remove old package (spm data): %s" % (self.pkgmeta['removeatom'],)
        )
        return self._spm_remove_package()

    def _post_remove_step_remove(self):
        """
        Post-remove phase of package remove action, this step removes SPM
        package entries if there are no other Entropy-tagged packages installed.
        """
        # remove pkg
        # -- now it's possible to remove SPM package entry.
        # if another package with the same atom is installed in
        # Entropy db, do not call SPM at all because it would cause
        # to get that package removed from there resulting in matching
        # inconsistencies.
        # -- of course, we need to drop versiontag before being able to look
        # for other pkgs with same atom but different tag (which is an
        # entropy-only metadatum)
        test_atom = entropy.dep.remove_tag(self.pkgmeta['removeatom'])
        others_installed = self._entropy.installed_repository().getPackageIds(
            test_atom)

        # It's obvious that clientdb cannot have more than one idpackage
        # featuring the same "atom" value, but still, let's be fault-tolerant.
        spm_rc = 0

        if not others_installed:
            spm_rc = self._spm_remove_package()

        for other_installed in others_installed:
            # we have one installed, we need to update SPM uid
            spm_rc = self._spm_update_package_uid(other_installed,
                self.pkgmeta['removeatom'])
            if spm_rc != 0:
                break # ohi ohi ohi

        return spm_rc

    def _post_remove_step(self):

        remdata = self.pkgmeta['triggers'].get('remove')
        if remdata:

            trigger = self._entropy.Triggers('postremove', remdata, self._action)
            do = trigger.prepare()
            if self.pkgmeta['diffremoval'] and \
                (self.pkgmeta.get("atom") is not None) and do:
                # diffremoval is true only when the remove
                # action is triggered by pkgs install
                pkgdata = self.pkgmeta['triggers'].get('install')
                if pkgdata:
                    i_trigger = self._entropy.Triggers('postinstall', pkgdata,
                        self._action)
                    i_trigger.prepare()
                    i_trigger.triggers = [x for x in trigger.triggers if x \
                        not in i_trigger.triggers]
                    i_trigger.kill()
                del pkgdata
            if do:
                trigger.run()
            trigger.kill()

        del remdata
        return 0

    def _removeconflict_step(self):

        inst_repo = self._entropy.installed_repository()
        confl_package_ids = [x for x in self.pkgmeta['conflicts'] if \
            inst_repo.isPackageIdAvailable(x)]
        if not confl_package_ids:
            return 0

        # calculate removal dependencies
        # system_packages must be False because we should not exclude
        # them from the dependency tree in any case. Also, we cannot trigger
        # DependenciesNotRemovable() exception, too.
        proposed_pkg_ids = self._entropy.get_removal_queue(confl_package_ids,
            system_packages = False)
        # we don't want to remove the whole inverse dependencies of course,
        # but just the conflicting ones, in a proper order
        package_ids = [x for x in proposed_pkg_ids if x in confl_package_ids]
        # make sure that every package is listed in package_ids before
        # proceeding, cannot keep packages behind anyway, and must be fault
        # tolerant. Besides, having missing packages here should never happen.
        package_ids += [x for x in confl_package_ids if x not in \
            package_ids]

        for package_id in package_ids:

            pkg = self._entropy.Package()
            pkg.prepare((package_id,), "remove_conflict",
                self.pkgmeta['remove_metaopts'])

            rc = pkg.run(xterm_header = self._xterm_title)
            pkg.kill()
            if rc != 0:
                return rc

        return 0

    def _config_step(self):

        mytxt = "%s: %s" % (
            blue(_("Configuring package")),
            red(self.pkgmeta['atom']),
        )
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        conf_rc = self.__configure_package()
        if conf_rc == 1:
            mytxt = _("An error occured while trying to configure the package")
            mytxt2 = "%s. %s: %s" % (
                red(_("Make sure that your system is healthy")),
                blue(_("Error")),
                conf_rc,
            )
            self._entropy.output(
                darkred(mytxt),
                importance = 1,
                level = "error",
                header = red("   ## ")
            )
            self._entropy.output(
                mytxt2,
                importance = 1,
                level = "error",
                header = red("   ## ")
            )

        elif conf_rc == 2:
            mytxt = _("An error occured while trying to configure the package")
            mytxt2 = "%s. %s: %s" % (
                red(_("It seems that Source Package Manager entry is missing")),
                blue(_("Error")),
                conf_rc,
            )
            self._entropy.output(
                darkred(mytxt),
                importance = 1,
                level = "error",
                header = red("   ## ")
            )
            self._entropy.output(
                mytxt2,
                importance = 1,
                level = "error",
                header = red("   ## ")
            )

        return conf_rc

    def _stepper(self, xterm_header):
        if xterm_header is None:
            xterm_header = ""

        if 'remove_installed_vanished' in self.pkgmeta:
            self._xterm_title += ' %s' % (_("Installed package vanished"),)
            self._entropy.set_title(self._xterm_title)
            rc = self._vanished_step()
            return rc

        if 'fetch_not_available' in self.pkgmeta:
            self._xterm_title += ' %s' % (_("Fetch not available"),)
            self._entropy.set_title(self._xterm_title)
            rc = self._fetch_not_available_step()
            return rc

        def do_fetch():
            self._xterm_title += ' %s: %s' % (
                _("Fetching"),
                os.path.basename(self.pkgmeta['download']),
            )
            self._entropy.set_title(self._xterm_title)
            return self._fetch_step()

        def do_multi_fetch():
            self._xterm_title += ' %s: %s %s' % (_("Multi Fetching"),
                len(self.pkgmeta['multi_fetch_list']), _("packages"),)
            self._entropy.set_title(self._xterm_title)
            return self._multi_fetch_step()

        def do_sources_fetch():
            self._xterm_title += ' %s: %s' % (
                _("Fetching sources"),
                os.path.basename(self.pkgmeta['atom']),)
            self._entropy.set_title(self._xterm_title)
            return self._sources_fetch_step()

        def do_checksum():
            self._xterm_title += ' %s: %s' % (_("Verifying"),
                os.path.basename(self.pkgmeta['download']),)
            self._entropy.set_title(self._xterm_title)
            return self._checksum_step()

        def do_multi_checksum():
            self._xterm_title += ' %s: %s %s' % (_("Multi Verification"),
                len(self.pkgmeta['multi_checksum_list']), _("packages"),)
            self._entropy.set_title(self._xterm_title)
            return self._multi_checksum_step()

        def do_unpack():
            if not self.pkgmeta['merge_from']:
                mytxt = _("Unpacking")
                self._xterm_title += ' %s: %s' % (
                    mytxt,
                    os.path.basename(self.pkgmeta['download']),
                )
            else:
                mytxt = _("Merging")
                self._xterm_title += ' %s: %s' % (
                    mytxt,
                    os.path.basename(self.pkgmeta['atom']),
                )
            self._entropy.set_title(self._xterm_title)
            return self._unpack_step()

        def do_remove_conflicts():
            return self._removeconflict_step()

        def do_install():
            self._xterm_title += ' %s: %s' % (
                _("Installing"),
                self.pkgmeta['atom'],
            )
            self._entropy.set_title(self._xterm_title)
            return self._install_step()

        def do_install_clean():
            return self._package_install_clean()

        def do_install_spm():
            return self._spm_install_package(
                self.pkgmeta['installed_package_id'])

        def do_remove():
            self._xterm_title += ' %s: %s' % (
                _("Removing"),
                self.pkgmeta['removeatom'],
            )
            self._entropy.set_title(self._xterm_title)
            return self._remove_step()

        def do_cleanup():
            self._xterm_title += ' %s: %s' % (
                _("Cleaning"),
                self.pkgmeta['atom'],
            )
            self._entropy.set_title(self._xterm_title)
            return self._cleanup_step()

        def do_postinstall():
            self._xterm_title += ' %s: %s' % (
                _("Postinstall"),
                self.pkgmeta['atom'],
            )
            self._entropy.set_title(self._xterm_title)
            return self._post_install_step()

        def do_preinstall():
            self._xterm_title += ' %s: %s' % (
                _("Preinstall"),
                self.pkgmeta['atom'],
            )
            self._entropy.set_title(self._xterm_title)
            return self._pre_install_step()

        def do_preremove():
            self._xterm_title += ' %s: %s' % (
                _("Preremove"),
                self.pkgmeta['removeatom'],
            )
            self._entropy.set_title(self._xterm_title)
            return self._pre_remove_step()

        def do_postremove():
            self._xterm_title += ' %s: %s' % (
                _("Postremove"),
                self.pkgmeta['removeatom'],
            )
            self._entropy.set_title(self._xterm_title)
            return self._post_remove_step()

        def do_postremove_install():
            return self._post_remove_step_install()

        def do_postremove_remove():
            return self._post_remove_step_remove()

        def do_config():
            self._xterm_title += ' %s: %s' % (
                _("Configuring"),
                self.pkgmeta['atom'],
            )
            self._entropy.set_title(self._xterm_title)
            return self._config_step()

        steps_data = {
            "fetch": do_fetch,
            "multi_fetch": do_multi_fetch,
            "multi_checksum": do_multi_checksum,
            "sources_fetch": do_sources_fetch,
            "checksum": do_checksum,
            "unpack": do_unpack,
            "remove_conflicts": do_remove_conflicts,
            "install": do_install,
            "install_spm": do_install_spm,
            "install_clean": do_install_clean,
            "remove": do_remove,
            "cleanup": do_cleanup,
            "postinstall": do_postinstall,
            "preinstall": do_preinstall,
            "postremove": do_postremove,
            "postremove_install": do_postremove_install,
            "postremove_remove": do_postremove_remove,
            "preremove": do_preremove,
            "config": do_config,
        }

        rc = 0
        for step in self.pkgmeta['steps']:
            self._xterm_title = xterm_header
            rc = steps_data.get(step)()
            if rc != 0:
                break
        return rc


    def run(self, xterm_header = None):
        self._error_on_not_prepared()

        gave_up = self._entropy.wait_resources()
        if gave_up:
            return 20

        locked = self._entropy.another_entropy_running()
        if locked:
            self._entropy.output(
                red(_("Another Entropy is currently running.")),
                importance = 1,
                level = "error",
                header = darkred(" @@ ")
            )
            return 21

        # lock
        acquired = self._entropy.lock_resources()
        if not acquired:
            self._entropy.output(
                blue(_("Cannot acquire Entropy resources lock.")),
                importance = 2,
                level = "error",
                header = darkred("   ## ")
            )
            return 4 # app locked during lock acquire
        try:
            rc = self._stepper(xterm_header)
        finally:
            self._entropy.unlock_resources()

        if rc != 0:
            self._entropy.output(
                blue(_("An error occured. Action aborted.")),
                importance = 2,
                level = "error",
                header = darkred("   ## ")
            )
        return rc

    def prepare(self, package_match, action, metaopts = None):
        self._error_on_prepared()

        self._check_action_validity(action)

        self._action = action
        self._package_match = package_match

        if metaopts is None:
            metaopts = {}
        self.metaopts = metaopts

        # generate metadata dictionary
        self._generate_metadata()

    def __get_base_metadata(self, action):
        def get_splitdebug_data():
            sys_set_plg_id = \
                etpConst['system_settings_plugins_ids']['client_plugin']
            misc_data = self._settings[sys_set_plg_id]['misc']
            splitdebug = misc_data['splitdebug']
            splitdebug_dirs = misc_data['splitdebug_dirs']
            return splitdebug, splitdebug_dirs

        splitdebug, splitdebug_dirs = get_splitdebug_data()
        metadata = {
            'splitdebug': splitdebug,
            'splitdebug_dirs': splitdebug_dirs,
        }
        return metadata

    def _generate_metadata(self):
        self._error_on_prepared()

        self._check_action_validity(self._action)
        self.pkgmeta.clear()
        self.pkgmeta.update(self.__get_base_metadata(self._action))

        if self._action == "fetch":
            self.__generate_fetch_metadata()
        elif self._action == "multi_fetch":
            self.__generate_multi_fetch_metadata()
        elif self._action in ("remove", "remove_conflict"):
            self.__generate_remove_metadata()
        elif self._action == "install":
            self.__generate_install_metadata()
        elif self._action == "source":
            self.__generate_fetch_metadata(sources = True)
        elif self._action == "config":
            self.__generate_config_metadata()

        self.__prepared = True

    def __generate_remove_metadata(self):

        idpackage = self._package_match[0]

        if not self._entropy.installed_repository().isPackageIdAvailable(
            idpackage):
            self.pkgmeta['remove_installed_vanished'] = True
            return 0

        self.pkgmeta['idpackage'] = idpackage
        self.pkgmeta['removeidpackage'] = idpackage
        self.pkgmeta['configprotect_data'] = []
        self.pkgmeta['triggers'] = {}
        self.pkgmeta['removeatom'] = \
            self._entropy.installed_repository().retrieveAtom(idpackage)
        self.pkgmeta['slot'] = \
            self._entropy.installed_repository().retrieveSlot(idpackage)
        self.pkgmeta['versiontag'] = \
            self._entropy.installed_repository().retrieveTag(idpackage)
        self.pkgmeta['diffremoval'] = False

        remove_config = False
        if 'removeconfig' in self.metaopts:
            remove_config = self.metaopts.get('removeconfig')
        self.pkgmeta['removeconfig'] = remove_config

        self.pkgmeta['removecontent'] = \
            self._entropy.installed_repository().retrieveContent(idpackage)
        self.pkgmeta['triggers']['remove'] = \
            self._entropy.installed_repository().getTriggerData(idpackage)
        if self.pkgmeta['triggers']['remove'] is None:
            self.pkgmeta['remove_installed_vanished'] = True
            return 0
        self.pkgmeta['triggers']['remove']['removecontent'] = \
            self.pkgmeta['removecontent']
        self.pkgmeta['triggers']['remove']['spm_repository'] = \
            self._entropy.installed_repository().retrieveSpmRepository(
                idpackage)
        self.pkgmeta['triggers']['remove'].update(
            self.__get_base_metadata(self._action))

        pkg_license = self._entropy.installed_repository().retrieveLicense(
            idpackage)
        if pkg_license is None:
            pkg_license = set()
        else:
            pkg_license = set(pkg_license.split())

        self.pkgmeta['triggers']['remove']['accept_license'] = pkg_license

        self.pkgmeta['steps'] = ["preremove", "remove", "postremove",
            "postremove_remove"]

        return 0

    def __generate_config_metadata(self):
        idpackage = self._package_match[0]

        self.pkgmeta['atom'] = \
            self._entropy.installed_repository().retrieveAtom(idpackage)
        key, slot = self._entropy.installed_repository().retrieveKeySlot(
            idpackage)
        self.pkgmeta['key'], self.pkgmeta['slot'] = key, slot
        self.pkgmeta['version'] = \
            self._entropy.installed_repository().retrieveVersion(idpackage)
        self.pkgmeta['category'] = \
            self._entropy.installed_repository().retrieveCategory(idpackage)
        self.pkgmeta['name'] = \
            self._entropy.installed_repository().retrieveName(idpackage)
        self.pkgmeta['spm_repository'] = \
            self._entropy.installed_repository().retrieveSpmRepository(
                idpackage)

        pkg_license = self._entropy.installed_repository().retrieveLicense(
            idpackage)
        if pkg_license is None:
            pkg_license = set()
        else:
            pkg_license = set(pkg_license.split())

        self.pkgmeta['accept_license'] = pkg_license
        self.pkgmeta['steps'] = []
        self.pkgmeta['steps'].append("config")

        return 0

    def __get_match_conflicts(self, match):
        m_id, m_repo = match

        dbconn = self._entropy.open_repository(m_repo)
        conflicts = dbconn.retrieveConflicts(m_id)
        found_conflicts = set()
        inst_repo = self._entropy.installed_repository()

        for conflict in conflicts:
            my_m_id, my_m_rc = inst_repo.atomMatch(conflict)
            if my_m_id != -1:
                # check if the package shares the same slot
                match_data = dbconn.retrieveKeySlot(m_id)
                installed_match_data = inst_repo.retrieveKeySlot(my_m_id)
                if match_data != installed_match_data:
                    found_conflicts.add(my_m_id)

        return found_conflicts

    def __setup_package_to_remove(self, package_key, slot):

        inst_repo = self._entropy.installed_repository()
        inst_idpackage, inst_rc = inst_repo.atomMatch(package_key,
            matchSlot = slot)

        if inst_idpackage != -1:
            avail = inst_repo.isPackageIdAvailable(inst_idpackage)
            if avail:
                inst_atom = inst_repo.retrieveAtom(inst_idpackage)
                self.pkgmeta['removeatom'] = inst_atom
            else:
                inst_idpackage = -1
        return inst_idpackage

    def __generate_install_metadata(self):

        idpackage, repository = self._package_match
        inst_repo = self._entropy.installed_repository()
        self.pkgmeta['idpackage'] = idpackage
        self.pkgmeta['repository'] = repository
        cl_id = etpConst['system_settings_plugins_ids']['client_plugin']
        edelta_support = self._settings[cl_id]['misc']['edelta_support']
        self.pkgmeta['edelta_support'] = edelta_support

        # fetch abort function
        self.pkgmeta['fetch_abort_function'] = \
            self.metaopts.get('fetch_abort_function')

        install_source = etpConst['install_sources']['unknown']
        meta_inst_source = self.metaopts.get('install_source', install_source)
        if meta_inst_source in list(etpConst['install_sources'].values()):
            install_source = meta_inst_source
        self.pkgmeta['install_source'] = install_source

        self.pkgmeta['already_protected_config_files'] = {}
        self.pkgmeta['configprotect_data'] = []
        dbconn = self._entropy.open_repository(repository)
        self.pkgmeta['triggers'] = {}
        self.pkgmeta['atom'] = dbconn.retrieveAtom(idpackage)
        self.pkgmeta['slot'] = dbconn.retrieveSlot(idpackage)

        ver, tag, rev = dbconn.getVersioningData(idpackage)
        self.pkgmeta['version'] = ver
        self.pkgmeta['versiontag'] = tag
        self.pkgmeta['revision'] = rev

        self.pkgmeta['category'] = dbconn.retrieveCategory(idpackage)
        self.pkgmeta['download'] = dbconn.retrieveDownloadURL(idpackage)
        self.pkgmeta['name'] = dbconn.retrieveName(idpackage)
        self.pkgmeta['checksum'] = dbconn.retrieveDigest(idpackage)
        sha1, sha256, sha512, gpg = dbconn.retrieveSignatures(idpackage)
        signatures = {
            'sha1': sha1,
            'sha256': sha256,
            'sha512': sha512,
            'gpg': gpg,
        }
        self.pkgmeta['signatures'] = signatures
        self.pkgmeta['conflicts'] = self.__get_match_conflicts(
            self._package_match)

        description = dbconn.retrieveDescription(idpackage)
        if description:
            if len(description) > 74:
                description = description[:74].strip()
                description += "..."
        self.pkgmeta['description'] = description

        # this is set by __install_package() and required by spm_install
        # phase
        self.pkgmeta['installed_package_id'] = None
        # fill action queue
        self.pkgmeta['removeidpackage'] = -1
        remove_config = False
        if 'removeconfig' in self.metaopts:
            remove_config = self.metaopts.get('removeconfig')

        self.pkgmeta['remove_metaopts'] = {
            'removeconfig': True,
        }
        if 'remove_metaopts' in self.metaopts:
            self.pkgmeta['remove_metaopts'] = \
                self.metaopts.get('remove_metaopts')

        self.pkgmeta['merge_from'] = None
        mf = self.metaopts.get('merge_from')
        if mf != None:
            self.pkgmeta['merge_from'] = const_convert_to_unicode(mf)
        self.pkgmeta['removeconfig'] = remove_config

        self.pkgmeta['removeidpackage'] = self.__setup_package_to_remove(
            entropy.dep.dep_getkey(self.pkgmeta['atom']), self.pkgmeta['slot'])
        # filled later...
        self.pkgmeta['removecontent'] = set()

        # smartpackage ?
        self.pkgmeta['smartpackage'] = False
        # set unpack dir and image dir
        if self.pkgmeta['repository'].endswith(etpConst['packagesext']):

            try:
                compiled_arch = dbconn.getSetting("arch")
                arch_fine = compiled_arch == etpConst['currentarch']
            except KeyError:
                arch_fine = True # sorry, old db, cannot check

            if not arch_fine:
                self.__prepared = False
                return -1

            repo_data = self._settings['repositories']
            repo_meta = repo_data['available'][self.pkgmeta['repository']]
            self.pkgmeta['smartpackage'] = repo_meta['smartpackage']
            self.pkgmeta['pkgpath'] = repo_meta['pkgpath']

        else:
            self.pkgmeta['pkgpath'] = self.__get_fetch_disk_path(
                self.pkgmeta['download'])

        self.pkgmeta['unpackdir'] = etpConst['entropyunpackdir'] + \
            os.path.sep + self.__escape_path(self.pkgmeta['download'])

        self.pkgmeta['imagedir'] = self.pkgmeta['unpackdir'] + os.path.sep + \
            etpConst['entropyimagerelativepath']

        self.pkgmeta['pkgdbpath'] = os.path.join(self.pkgmeta['unpackdir'],
            "edb/pkg.db")

        # compare both versions and if they match, disable removeidpackage
        if self.pkgmeta['removeidpackage'] != -1:

            trigger_data = inst_repo.getTriggerData(
                self.pkgmeta['removeidpackage'])
            if trigger_data is None:
                # installed repository entry is corrupted
                self.pkgmeta['removeidpackage'] = -1
            else:

                # differential remove list
                self.pkgmeta['diffremoval'] = True
                self.pkgmeta['removeatom'] = inst_repo.retrieveAtom(
                    self.pkgmeta['removeidpackage'])

                self.pkgmeta['triggers']['remove'] = trigger_data
                # pass reference, not copy! nevva!
                self.pkgmeta['triggers']['remove']['removecontent'] = \
                    self.pkgmeta['removecontent']
                self.pkgmeta['triggers']['remove']['spm_repository'] = \
                    inst_repo.retrieveSpmRepository(idpackage)
                self.pkgmeta['triggers']['remove'].update(
                    self.__get_base_metadata(self._action))

                pkg_rm_license = inst_repo.retrieveLicense(
                    self.pkgmeta['removeidpackage'])
                if pkg_rm_license is None:
                    pkg_rm_license = set()
                else:
                    pkg_rm_license = set(pkg_rm_license.split())
                self.pkgmeta['triggers']['remove']['accept_license'] = \
                    pkg_rm_license

        # set steps
        self.pkgmeta['steps'] = []
        if self.pkgmeta['conflicts']:
            self.pkgmeta['steps'].append("remove_conflicts")
        # install
        self.pkgmeta['steps'].append("unpack")
        # preinstall placed before preremove in order
        # to respect Spm order
        self.pkgmeta['steps'].append("preinstall")
        self.pkgmeta['steps'].append("install")
        if (self.pkgmeta['removeidpackage'] != -1):
            self.pkgmeta['steps'].append("preremove")
        self.pkgmeta['steps'].append("install_clean")
        if (self.pkgmeta['removeidpackage'] != -1):
            self.pkgmeta['steps'].append("postremove")
            self.pkgmeta['steps'].append("postremove_install")
        self.pkgmeta['steps'].append("install_spm")
        self.pkgmeta['steps'].append("postinstall")
        self.pkgmeta['steps'].append("cleanup")

        self.pkgmeta['triggers']['install'] = dbconn.getTriggerData(idpackage)
        if self.pkgmeta['triggers']['install'] is None:
            # wtf!?
            return 1
        pkg_license = dbconn.retrieveLicense(idpackage)
        if pkg_license is None:
            pkg_license = set()
        else:
            pkg_license = set(pkg_license.split())
        self.pkgmeta['accept_license'] = pkg_license
        self.pkgmeta['triggers']['install']['accept_license'] = pkg_license
        self.pkgmeta['triggers']['install']['unpackdir'] = \
            self.pkgmeta['unpackdir']
        self.pkgmeta['triggers']['install']['imagedir'] = \
            self.pkgmeta['imagedir']
        self.pkgmeta['triggers']['install']['spm_repository'] = \
            dbconn.retrieveSpmRepository(idpackage)
        self.pkgmeta['triggers']['install'].update(
            self.__get_base_metadata(self._action))

        spm_class = self._entropy.Spm_class()
        # call Spm setup hook
        return spm_class.entropy_install_setup_hook(self._entropy, self.pkgmeta)

    def __generate_fetch_metadata(self, sources = False):

        idpackage, repository = self._package_match
        dochecksum = True

        # fetch abort function
        self.pkgmeta['fetch_abort_function'] = \
            self.metaopts.get('fetch_abort_function')

        if 'dochecksum' in self.metaopts:
            dochecksum = self.metaopts.get('dochecksum')

        # NOTE: if you want to implement download-to-dir feature in your
        # client, you've found what you were looking for.
        # fetch_path is the path where data should be downloaded
        # it overrides default path
        if 'fetch_path' in self.metaopts:
            fetch_path = self.metaopts.get('fetch_path')
            if entropy.tools.is_valid_path(fetch_path):
                self.pkgmeta['fetch_path'] = fetch_path

        self.pkgmeta['repository'] = repository
        self.pkgmeta['idpackage'] = idpackage
        dbconn = self._entropy.open_repository(repository)
        self.pkgmeta['atom'] = dbconn.retrieveAtom(idpackage)
        self.pkgmeta['slot'] = dbconn.retrieveSlot(idpackage)
        self.pkgmeta['removeidpackage'] = self.__setup_package_to_remove(
            entropy.dep.dep_getkey(self.pkgmeta['atom']), self.pkgmeta['slot'])

        if sources:
            self.pkgmeta['edelta_support'] = False
            self.pkgmeta['download'] = dbconn.retrieveSources(idpackage,
                extended = True)
        else:
            cl_id = etpConst['system_settings_plugins_ids']['client_plugin']
            edelta_support = self._settings[cl_id]['misc']['edelta_support']
            self.pkgmeta['edelta_support'] = edelta_support
            self.pkgmeta['checksum'] = dbconn.retrieveDigest(idpackage)
            sha1, sha256, sha512, gpg = dbconn.retrieveSignatures(idpackage)
            signatures = {
                'sha1': sha1,
                'sha256': sha256,
                'sha512': sha512,
                'gpg': gpg,
            }
            self.pkgmeta['signatures'] = signatures
            self.pkgmeta['download'] = dbconn.retrieveDownloadURL(idpackage)

        if not self.pkgmeta['download']:
            self.pkgmeta['fetch_not_available'] = True
            return 0

        self.pkgmeta['verified'] = False
        self.pkgmeta['steps'] = []
        if not repository.endswith(etpConst['packagesext']) and not sources:
            dl_check = self.__check_pkg_path_download(self.pkgmeta['download'],
                None)

            if dl_check < 0:
                self.pkgmeta['steps'].append("fetch")
            if dochecksum:
                self.pkgmeta['steps'].append("checksum")

        elif sources:
            self.pkgmeta['steps'].append("sources_fetch")

        if sources:
            # create sources destination directory
            unpack_dir = os.path.join(etpConst['entropyunpackdir'],
                "sources", self.pkgmeta['atom'])
            self.pkgmeta['unpackdir'] = unpack_dir

            if not self.pkgmeta.get('fetch_path'):
                if os.path.lexists(unpack_dir):
                    if os.path.isfile(unpack_dir):
                        os.remove(unpack_dir)
                    elif os.path.isdir(unpack_dir):
                        shutil.rmtree(unpack_dir, True)
                if not os.path.lexists(unpack_dir):
                    os.makedirs(unpack_dir, 0o755)
                const_setup_perms(unpack_dir, etpConst['entropygid'],
                    recursion = False, uid = etpConst['uid'])
            return 0

        # downloading binary package
        # if file exists, first checksum then fetch
        down_path = self.__get_fetch_disk_path(self.pkgmeta['download'])
        self.pkgmeta['pkgpath'] = down_path # provide for convenience
        # and uniformity with "install" action
        if os.access(down_path, os.R_OK) and os.path.isfile(down_path):

            # check size first
            repo_size = dbconn.retrieveSize(idpackage)
            f = open(down_path, "r")
            f.seek(0, os.SEEK_END)
            disk_size = f.tell()
            f.close()
            if repo_size == disk_size:
                self.pkgmeta['steps'].reverse()

        return 0

    def __generate_multi_fetch_metadata(self):

        if not isinstance(self._package_match, list):
            raise AttributeError(
                "package_match must be a list of tuples, not %s" % (
                    type(self._package_match,)
                )
            )

        dochecksum = True

        # meta options
        self.pkgmeta['fetch_abort_function'] = \
            self.metaopts.get('fetch_abort_function')

        if 'dochecksum' in self.metaopts:
            dochecksum = self.metaopts.get('dochecksum')
        self.pkgmeta['checksum'] = dochecksum

        matches = self._package_match
        cl_id = etpConst['system_settings_plugins_ids']['client_plugin']
        edelta_support = self._settings[cl_id]['misc']['edelta_support']
        self.pkgmeta['edelta_support'] = edelta_support
        self.pkgmeta['matches'] = matches
        self.pkgmeta['atoms'] = []
        self.pkgmeta['repository_atoms'] = {}
        temp_fetch_list = []
        temp_checksum_list = []
        temp_already_downloaded_count = 0
        for idpackage, repository in matches:

            if repository.endswith(etpConst['packagesext']):
                continue

            dbconn = self._entropy.open_repository(repository)
            myatom = dbconn.retrieveAtom(idpackage)

            # general purpose metadata
            self.pkgmeta['atoms'].append(myatom)
            if repository not in self.pkgmeta['repository_atoms']:
                self.pkgmeta['repository_atoms'][repository] = set()
            self.pkgmeta['repository_atoms'][repository].add(myatom)

            download = dbconn.retrieveDownloadURL(idpackage)
            digest = dbconn.retrieveDigest(idpackage)

            sha1, sha256, sha512, gpg = dbconn.retrieveSignatures(idpackage)
            signatures = {
                'sha1': sha1,
                'sha256': sha256,
                'sha512': sha512,
                'gpg': gpg,
            }


            if dochecksum:
                obj = (idpackage, repository, download, digest, signatures,)
                temp_checksum_list.append(obj)

            repo_size = dbconn.retrieveSize(idpackage)
            if self.__check_pkg_path_download(download, None) < 0:
                obj = (idpackage, repository, download, digest, signatures,)
                temp_fetch_list.append(obj)
                continue

            down_path = self.__get_fetch_disk_path(download)
            if os.path.isfile(down_path):
                with open(down_path, "r") as f:
                    f.seek(0, os.SEEK_END)
                    disk_size = f.tell()
                if repo_size == disk_size:
                    temp_already_downloaded_count += 1

        self.pkgmeta['steps'] = []
        self.pkgmeta['multi_fetch_list'] = temp_fetch_list
        self.pkgmeta['multi_checksum_list'] = temp_checksum_list
        if self.pkgmeta['multi_fetch_list']:
            self.pkgmeta['steps'].append("multi_fetch")
        if self.pkgmeta['multi_checksum_list']:
            self.pkgmeta['steps'].append("multi_checksum")
        if temp_already_downloaded_count == len(temp_checksum_list):
            self.pkgmeta['steps'].reverse()

        return 0
