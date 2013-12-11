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

from entropy.const import etpConst, const_setup_directory
from entropy.i18n import _
from entropy.output import blue, red, brown

import entropy.dep
import entropy.tools


from .fetch import _PackageFetchAction


class _PackageSourceAction(_PackageFetchAction):
    """
    PackageAction used for package source code download.
    """

    NAME = "source"

    def __init__(self, entropy_client, package_match, opts = None):
        """
        Object constructor.
        """
        super(_PackageSourceAction, self).__init__(
            entropy_client, package_match, opts = opts)
        self._meta = None

    def finalize(self):
        """
        Finalize the object, release all its resources.
        """
        super(_PackageSourceAction, self).finalize()
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

        repo = self._entropy.open_repository(self._repository_id)

        metadata = {}
        metadata['phases'] = []
        metadata['download'] = repo.retrieveSources(
            self._package_id, extended = True)

        atom = repo.retrieveAtom(self._package_id)
        metadata['atom'] = atom

        unpack_dir = os.path.join(
            etpConst['entropyunpackdir'],
            "sources", atom)
        metadata['unpackdir'] = unpack_dir

        if not metadata['download']:
            metadata['phases'].append(self._fetch_not_available_phase)
            self._meta = metadata
            return

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

        metadata['phases'].append(self._fetch_phase)

        self._meta = metadata

    def _run(self):
        """
        Execute the action. Return an exit status.
        """
        self.setup()

        unpack_dir = self._meta['unpackdir']

        if not self._meta.get('fetch_path'):
            try:
                os.makedirs(unpack_dir, 0o755)
                const_setup_directory(unpack_dir)
            except (OSError, IOError) as err:
                if err.errno != errno.EEXIST:
                    self._entropy.output(
                        "%s: %s" % (
                            blue(_("Fetch path setup error")),
                            err,
                        ),
                        importance = 1,
                        level = "info",
                        header = red("   ## ")
                    )
                    return 1

        exit_st = 0
        for method in self._meta['phases']:
            exit_st = method()
            if exit_st != 0:
                break
        return exit_st

    def _fetch_not_available_phase(self):
        """
        Execute the fetch not available phase.
        """
        self._entropy.output(
            blue(_("Source code not available.")),
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        return 0

    def _fetch_source(self, url, download_path):
        """
        Fetch the source code tarball(s).
        """
        self._entropy.output(
            "%s: %s" % (
                blue(_("Downloading")),
                brown(url),
            ),
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        lock = None
        try:
            lock = self.path_lock(download_path)
            with lock.exclusive():
                exit_st, data_transfer, _resumed = self._download_file(
                    url, download_path, digest = None, resume = False)
        finally:
            if lock is not None:
                lock.close()

        if exit_st == 0:
            human_bytes = entropy.tools.bytes_into_human(data_transfer)
            txt = "%s: %s %s %s/%s" % (
                blue(_("Successfully downloaded from")),
                red(self._get_url_name(url)),
                _("at"),
                human_bytes,
                _("second"),
            )
            self._entropy.output(
                txt,
                importance = 1,
                level = "info",
                header = red("   ## ")
            )

            self._entropy.output(
                "%s: %s" % (
                    blue(_("Local path")),
                    brown(download_path),
                ),
                importance = 1,
                level = "info",
                header = red("      # ")
            )
            return exit_st

        error_message = "%s: %s" % (
            blue(_("Error downloading from")),
            red(self._get_url_name(url)),
        )
        if exit_st == -1:
            error_message += " - %s." % (
                _("file not available on this mirror"),
            )
        elif exit_st == -3:
            error_message += " - not found."
        elif exit_st == -100:
            error_message += " - %s." % (_("discarded download"),)
        else:
            error_message += " - %s: %s" % (
                _("unknown reason"), exit_st,
            )

        self._entropy.output(
            error_message,
            importance = 1,
            level = "warning",
            header = red("   ## ")
        )
        return exit_st

    def _fetch_phase(self):
        """
        Execute the source fetch phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Fetching sources"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        down_data = self._meta['download']
        down_keys = list(down_data.keys())
        d_cache = set()
        exit_st = 0
        key_cache = [os.path.basename(x) for x in down_keys]

        for key in sorted(down_keys):

            key_name = os.path.basename(key)
            if key_name in d_cache:
                continue
            # first fine wins

            keyboard_interrupt = False
            for url in down_data[key]:

                file_name = os.path.basename(url)
                if self._meta.get('fetch_path'):
                    download_path = os.path.join(
                        self._meta['fetch_path'],
                        file_name)
                else:
                    download_path = os.path.join(
                        self._meta['unpackdir'], file_name)

                try:
                    exit_st = self._fetch_source(url, download_path)
                except KeyboardInterrupt:
                    keyboard_interrupt = True
                    break

                if exit_st == -100:
                    keyboard_interrupt = True
                    break

                if exit_st == 0:
                    d_cache.add(key_name)
                    break

            if keyboard_interrupt:
                exit_st = 1
                break

            key_cache.remove(key_name)
            if exit_st != 0 and key_name not in key_cache:
                break

            exit_st = 0

        return exit_st
