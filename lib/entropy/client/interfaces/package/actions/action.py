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
import stat
import sys

from entropy.const import etpConst, const_convert_to_unicode, \
    const_setup_directory
from entropy.i18n import _
from entropy.misc import FlockFile
from entropy.output import darkred, blue, darkgreen

import entropy.dep

from .. import _content as Content


class PackageAction(object):

    """
    Base PackageAction object. Do not instantiate this and its subclasses
    directly but rather use the PackageActionFactory.
    """

    _INFO_EXTS = (
        const_convert_to_unicode(".gz"),
        const_convert_to_unicode(".bz2")
        )

    # Set a valid action name in subclasses
    NAME = None

    def __init__(self, entropy_client, package_match, opts = None):
        self._entropy = entropy_client
        self._settings = self._entropy.Settings()
        self._package_match = package_match
        self._package_id, self._repository_id = package_match
        if opts is None:
            opts = {}
        self._opts = opts
        self._xterm_header = ""
        self._content_files = []

    def package_id(self):
        """
        Return the package identifier of this object.
        """
        return self._package_id

    def repository_id(self):
        """
        Return the repository identifier of this object.
        """
        return self._repository_id

    def atom(self):
        """
        Return the package atom string of this object.
        """
        repo = self._entropy.open_repository(self._repository_id)
        return repo.retrieveAtom(self._package_id)

    def set_xterm_header(self, header):
        """
        Set the xterm terminal header text that will prefix the activity title.

        @param header: the xterm header title
        @type header: string
        """
        self._xterm_header = header

    def path_lock(self, path):
        """
        Given a path, return a FlockFile object that can be used for
        inter-process synchronization purposes.

        @param path: path to protect with a file lock
        @type path: string
        @return: a FlockFile object instance
        @rtype: entropy.misc.FlockFile
        """
        lock_path = path + "._entropy_package.lock"
        path_dir = os.path.dirname(path)
        const_setup_directory(path_dir)

        def wait_msg_cb(obj, exclusive):
            if exclusive:
                msg = _("Acquiring exclusive lock on")
            else:
                msg = _("Acquiring shared lock on")

            self._entropy.output(
                "%s %s ..." % (
                    darkred(msg),
                    darkgreen(obj.get_path()),
                ),
                level = "warning", # use stderr, avoid breaking --quiet
                back = True,
                importance = 0)

        def acquired_msg_cb(obj, exclusive):
            if exclusive:
                msg = _("Acquired exclusive lock on")
            else:
                msg = _("Acquired shared lock on")
            self._entropy.output(
                "%s %s" % (
                    darkred(msg),
                    darkgreen(obj.get_path()),
                ),
                level = "warning", # use stderr, avoid breaking --quiet
                back = True,
                importance = 0)

        class PackageFlockFile(FlockFile):

            _ALLOWED_ERRORS = (errno.EPERM, errno.ENOSYS, errno.ENOLCK)

            def __init__(self, *args, **kwargs):
                super(PackageFlockFile, self).__init__(*args, **kwargs)
                self._wait_msg_cb = wait_msg_cb
                self._acquired_msg_cb = acquired_msg_cb

            def acquire_shared(self):
                """
                Avoid failures if lock cannot be acquired due to filesystem
                limitations (NFS?).
                """
                try:
                    return super(PackageFlockFile, self).acquire_shared()
                except (OSError, IOError) as err:
                    if err.errno not in self._ALLOWED_ERRORS:
                        raise
                    sys.stderr.write(
                        "PackageFlockFile(%s).shared: lock error: %s\n" % (
                            self._path, err))

            def try_acquire_shared(self):
                """
                Avoid failures if lock cannot be acquired due to filesystem
                limitations (NFS?).
                """
                try:
                    return super(PackageFlockFile, self).try_acquire_shared()
                except (OSError, IOError) as err:
                    if err.errno not in self._ALLOWED_ERRORS:
                        raise
                    sys.stderr.write(
                        "PackageFlockFile(%s).try_shared: lock error: %s\n" % (
                            self._path, err))
                    return True

            def acquire_exclusive(self):
                """
                Avoid failures if lock cannot be acquired due to filesystem
                limitations (NFS?).
                """
                try:
                    return super(PackageFlockFile, self).acquire_exclusive()
                except (OSError, IOError) as err:
                    if err.errno not in self._ALLOWED_ERRORS:
                        raise
                    sys.stderr.write(
                        "PackageFlockFile(%s).exclusive: lock error: %s\n" % (
                            self._path, err))

            def try_acquire_exclusive(self):
                """
                Avoid failures if lock cannot be acquired due to filesystem
                limitations (NFS?).
                """
                try:
                    return super(PackageFlockFile, self).try_acquire_exclusive()
                except (OSError, IOError) as err:
                    if err.errno not in self._ALLOWED_ERRORS:
                        raise
                    sys.stderr.write(
                        "PackageFlockFile(%s).try_excl: lock error: %s\n" % (
                            self._path, err))
                    return True


        return PackageFlockFile(lock_path)

    def _stat_path(self, path):
        """
        Return true whether path is a regular file (no symlinks allowed).
        """
        try:
            st = os.stat(path)
            return stat.S_ISREG(st.st_mode)
        except OSError:
            return False

    def setup(self):
        """
        Setup the action metadata. There is no need to call this directly,
        unless you want to pre-generate the whole PackageAction metadata.
        This method will be called by start() anyway.
        """
        raise NotImplementedError()

    def start(self):
        """
        Execute the action. Return an exit status.
        """
        acquired = False
        exit_st = self._run()
        if exit_st != 0:
            self._entropy.output(
                blue(_("An error occurred. Action aborted.")),
                importance = 2,
                level = "error",
                header = darkred("   ## ")
            )
        return exit_st

    def _run(self):
        """
        This method is called by start() and this is where subclasses
        must implement their "run()" logic.
        This method must return an exit status code (int).
        This method must call setup() at the beginning of its execution.
        """
        raise NotImplementedError()

    def finalize(self):
        """
        Finalize the object, release all its resources.
        Subclasses must call this method in their overridden ones.
        """
        # remove temporary content files
        for content_file in self._content_files:
            try:
                os.remove(content_file)
            except (OSError, IOError):
                pass

    def metadata(self):
        """
        Return the package metadata dict object for manipulation.
        """
        raise NotImplementedError()

    @classmethod
    def splitdebug_enabled(cls, entropy_client, pkg_match):
        """
        Return whether splitdebug is enabled for package.
        """
        settings = entropy_client.Settings()
        # this is a SystemSettings.CachingList object
        splitdebug = settings['splitdebug']
        splitdebug_mask = settings['splitdebug_mask']
        _pkg_id, pkg_repo = pkg_match

        def _generate_cache(lst_obj):
            # compute the package matching then
            pkg_matches = set()
            for dep in lst_obj:
                dep, repo_ids = entropy.dep.dep_get_match_in_repos(dep)
                if repo_ids is not None:
                    if pkg_repo not in repo_ids:
                        # skip entry, not me
                        continue
                dep_matches, _rc = entropy_client.atom_match(
                    dep, multi_match=True, multi_repo=True)
                pkg_matches |= dep_matches

            # set cache back
            lst_obj.set(pkg_matches)
            return pkg_matches

        enabled = False
        if not splitdebug:
            # no entries, consider splitdebug always enabled
            enabled = True
        else:
            # whitelist support
            pkg_matches = splitdebug.get()
            if pkg_matches is None:
                pkg_matches = _generate_cache(splitdebug)

            # determine if it's enabled then
            enabled = pkg_match in pkg_matches

        # if it's enabled, check whether it's blacklisted
        if enabled:
            # blacklist support
            pkg_matches = splitdebug_mask.get()
            if pkg_matches is None:
                # compute the package matching
                pkg_matches = _generate_cache(splitdebug_mask)

            enabled = pkg_match not in pkg_matches

        return enabled

    @classmethod
    def get_standard_fetch_disk_path(cls, download):
        """
        Return standard path where package is going to be downloaded.
        "download" argument passed must come from
        EntropyRepository.retrieveDownloadURL()
        """
        return os.path.join(etpConst['entropypackagesworkdir'], download)

    def __repr__(self):
        return "<%s at %s | metadata: %s" % (
            self.__class__.__name__,
            hex(id(self)),
            self.metadata())

    def __str__(self):
        return repr(self)

    def _get_info_directories(self):
        """
        Return a list of `info` directories as declared in the
        INFOPATH and INFODIR environment variable.
        """
        info_dirs = os.getenv("INFOPATH", "").split(":")
        info_dirs += os.getenv("INFODIR", "").split(":")
        info_dirs = [const_convert_to_unicode(
                os.path.normpath(x)) for x in info_dirs]
        info_dirs.sort()
        return info_dirs

    def _get_splitdebug_metadata(self):
        """
        Return package metadata related to split debug files support.
        """
        client_settings = self._entropy.ClientSettings()
        misc_data = client_settings['misc']
        splitdebug = misc_data['splitdebug']
        splitdebug_dirs = misc_data['splitdebug_dirs']

        metadata = {
            'splitdebug': splitdebug,
            'splitdebug_dirs': splitdebug_dirs,
        }
        return metadata

    def _package_splitdebug_enabled(self, pkg_match):
        """
        Determine if splitdebug is enabled for the package being installed
        or just fetched. This method should be called only if system-wide
        splitdebug setting in client.conf is enabled already.
        """
        return self.splitdebug_enabled(self._entropy, pkg_match)

    def _generate_content_file(self, content, package_id = None,
                               filter_splitdebug = False,
                               splitdebug = None,
                               splitdebug_dirs = None):
        """
        Generate a file containing the package content metadata.
        """
        content_path = None
        try:
            content_path = Content.generate_content_file(
                content, package_id = package_id,
                filter_splitdebug = filter_splitdebug,
                splitdebug = splitdebug,
                splitdebug_dirs = splitdebug_dirs)
            return content_path
        finally:
            if content_path is not None:
                self._content_files.append(content_path)

    def _generate_content_safety_file(self, content_safety):
        """
        Generate a file containing the package content safety metadata.
        """
        content_path = None
        try:
            content_path = Content.generate_content_safety_file(
                content_safety)
            return content_path
        finally:
            if content_path is not None:
                self._content_files.append(content_path)

    @classmethod
    def _get_url_name(cls, url):
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

    @classmethod
    def _get_licenses(cls, entropy_repository, package_id):
        """
        Return a set of license identifiers for the given package.
        """
        pkg_license = set()
        r_license = entropy_repository.retrieveLicense(package_id)
        if r_license is not None:
            pkg_license |= set(r_license.split())
        return pkg_license
