# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server Main Interfaces}.

    I{ServerRepositoryStatus} is a singleton containing the status of
    server-side repositories. It is used to determine if repository has
    been modified (tainted) or has been revision bumped already.
    Revision bumps are automatic and happen on the very first data "commit".
    Every repository features a revision number which is stored into the
    "packages.db.revision" file. Only server-side (or community) repositories
    are subject to this automation (revision file update on commit).

"""
import errno
import os
import shutil
import time
import bz2
import codecs
import threading

from entropy.const import etpConst, const_setup_file, const_mkdtemp, \
    const_mkstemp, const_convert_to_unicode, const_file_readable
from entropy.core import Singleton
from entropy.db import EntropyRepository
from entropy.transceivers import EntropyTransceiver
from entropy.output import red, darkgreen, bold, brown, blue, darkred, teal, \
    purple
from entropy.misc import FastRSS
from entropy.cache import EntropyCacher
from entropy.exceptions import OnlineMirrorError
from entropy.security import Repository as RepositorySecurity
from entropy.client.interfaces.db import InstalledPackagesRepository, \
    CachedRepository
from entropy.i18n import _

from entropy.server.interfaces.rss import ServerRssMetadata

import entropy.dep
import entropy.tools

class ServerRepositoryStatus(Singleton):

    """
    Server-side Repositories status information container.
    """

    def init_singleton(self):
        """ Singleton "constructor" """
        self.__data = {}
        self.__updates_log = {}

    def reset(self):
        """
        Reset the object to its initial state.
        """
        self.__data.clear()
        self.__updates_log.clear()

    def __create_if_necessary(self, db):
        if db not in self.__data:
            self.__data[db] = {}
            self.__data[db]['tainted'] = False
            self.__data[db]['bumped'] = False
            self.__data[db]['unlock_msg'] = False
            self.__data[db]['sets_synced'] = False

    def set_unlock_msg(self, db):
        """
        Set bit which determines if the unlock warning has been already
        printed to user.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['unlock_msg'] = True

    def unset_unlock_msg(self, db):
        """
        Unset bit which determines if the unlock warning has been already
        printed to user.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['unlock_msg'] = False

    def set_tainted(self, db):
        """
        Set bit which determines if the repository which db points to has been
        modified.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['tainted'] = True

    def unset_tainted(self, db):
        """
        Unset bit which determines if the repository which db points to has been
        modified.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['tainted'] = False

    def set_bumped(self, db):
        """
        Set bit which determines if the repository which db points to has been
        revision bumped.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['bumped'] = True

    def unset_bumped(self, db):
        """
        Unset bit which determines if the repository which db points to has been
        revision bumped.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['bumped'] = False

    def set_synced_sets(self, db):
        """
        Set bit which determines that package sets have been synchronized with
        Source Package Manager.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        self.__data[db]['sets_synced'] = True

    def is_tainted(self, db):
        """
        Return whether repository which db points to has been modified.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        return self.__data[db]['tainted']

    def is_bumped(self, db):
        """
        Return whether repository which db points to has been revision bumped.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        return self.__data[db]['bumped']

    def is_unlock_msg(self, db):
        """
        Return whether repository which db points to has outputed the unlock
        warning message.

        @param db: database identifier
        @type db: string
        """
        self.__create_if_necessary(db)
        return self.__data[db]['unlock_msg']

    def are_sets_synced(self, db):
        """
        Return whether package sets in repository have been already synchronized
        with Source Package Manager.
        """
        self.__create_if_necessary(db)
        return self.__data[db]['sets_synced']

    def get_updates_log(self, db):
        """
        Return dict() object containing metadata related to package
        updates occurred in a server-side repository.
        """
        if db not in self.__updates_log:
            self.__updates_log[db] = {}
        return self.__updates_log[db]


class ServerPackagesRepository(CachedRepository):
    """
    This class represents the installed packages repository and is a direct
    subclass of EntropyRepository.
    """

    @staticmethod
    def revision(repository_id):
        """
        Reimplemented from EntropyRepository
        """
        from entropy.server.interfaces import Server
        srv = Server()
        return srv.local_repository_revision(repository_id)

    @staticmethod
    def remote_revision(repository_id):
        """
        Reimplemented from EntropyRepository
        """
        from entropy.server.interfaces import Server
        srv = Server()
        return srv.remote_repository_revision(repository_id)

    @staticmethod
    def update(entropy_client, repository_id, enable_upload, enable_download,
               force = False):
        """
        Reimplemented from EntropyRepository
        """
        return ServerPackagesRepositoryUpdater(entropy_client, repository_id,
            enable_upload, enable_download, force = force).update()

    def _runConfigurationFilesUpdate(self, actions, files,
        protect_overwrite = False):
        """
        Overridden from EntropyRepositoryBase.
        Force protect_overwrite to always False. Per-repository config files
        cannot be protected since their dirs are not listed inside the
        configuration protected list.
        """
        return super(ServerPackagesRepository, self)._runConfigurationFilesUpdate(
            actions, files, protect_overwrite = False)

    def handlePackage(self, pkg_data, revision = None,
                      formattedContent = False):
        """
        Reimplemented from EntropyRepository.
        """

        # build atom string, server side
        pkgatom = entropy.dep.create_package_atom_string(
            pkg_data['category'], pkg_data['name'], pkg_data['version'],
            pkg_data['versiontag'])

        increase_revision = False
        if revision is None:
            current_rev = max(
                pkg_data.get('revision', 0),
                0)
        else:
            current_rev = revision

        manual_deps = set()
        # Remove entries in the same scope.
        for package_id in self.getPackageIds(pkgatom):

            if revision is None:
                pkg_revision = self.retrieveRevision(package_id)
                if pkg_revision >= current_rev:
                    current_rev = pkg_revision
                    increase_revision = True

            manual_deps |= self.retrieveManualDependencies(package_id,
                resolve_conditional_deps = False)
            # injected packages wouldn't be removed by addPackage
            self.removePackage(package_id)

        if increase_revision:
            current_rev += 1

        # manual dependencies handling
        removelist = self.getPackagesToRemove(
            pkg_data['name'], pkg_data['category'],
            pkg_data['slot'], pkg_data['injected']
        )

        for r_package_id in removelist:
            manual_deps |= self.retrieveManualDependencies(r_package_id,
                resolve_conditional_deps = False)
            self.removePackage(r_package_id)

        # inject old manual dependencies back to package metadata
        m_dep_id = etpConst['dependency_type_ids']['mdepend_id']
        for manual_dep in manual_deps:
            pkg_data['pkg_dependencies'] += ((manual_dep, m_dep_id),)

        # add the new one
        return self.addPackage(pkg_data, revision = current_rev,
            formatted_content = formattedContent)

    def setReadonly(self, readonly):
        """
        Set or unset the repository as read-only.

        @param readonly: True, enable read-only
        @type readonly: bool
        """
        self._readonly = bool(readonly)

    _CONNECTION_POOL = {}
    _CONNECTION_POOL_MUTEX = threading.RLock()
    _CURSOR_POOL = {}
    _CURSOR_POOL_MUTEX = threading.RLock()

    def _connection_pool(self):
        """
        Overridden from EntropyRepository.
        """
        return ServerPackagesRepository._CONNECTION_POOL

    def _connection_pool_mutex(self):
        """
        Overridden from EntropyRepository.
        """
        return ServerPackagesRepository._CONNECTION_POOL_MUTEX

    def _cursor_pool(self):
        """
        Overridden from EntropyRepository.
        """
        return ServerPackagesRepository._CURSOR_POOL

    def _cursor_pool_mutex(self):
        """
        Overridden from EntropyRepository.
        """
        return ServerPackagesRepository._CURSOR_POOL_MUTEX


class ServerPackagesRepositoryUpdater(object):

    """
    This class handles the repository update across all the configured mirrors.
    It is used by entropy.server.interfaces.mirrors module and called from
    inside ServerPackagesRepository class.
    """

    def __init__(self, entropy_server, repository_id, enable_upload,
                 enable_download, force = False):
        """
        ServerPackagesRepositoryUpdater constructor, called by
        ServerPackagesRepository.

        @param enable_upload: if True, repository will be uploaded for syncing if
            required
        @type enable_upload: bool
        @param enable_download: if True, repository will be downloaded for syncing
            if required
        @type enable_download: bool
        """
        self._entropy = entropy_server
        self._mirrors = self._entropy.Mirrors
        self._settings = self._entropy.Settings()
        self._cacher = EntropyCacher()
        self._repository_id = repository_id
        self._enable_upload = enable_upload
        self._enable_download = enable_download
        self._force = force

    def __get_repo_security_intf(self):
        try:
            repo_sec = RepositorySecurity()
            if not repo_sec.is_keypair_available(self._repository_id):
                raise KeyError("no key avail")
        except RepositorySecurity.KeyExpired:
            self._entropy.output("%s: %s" % (
                    darkred(_("Keys for repository are expired")),
                    bold(self._repository_id),
                ),
                level = "warning",
                header = bold(" !!! ")
            )
        except RepositorySecurity.GPGError:
            return
        except KeyError:
            return
        return repo_sec

    def __write_gpg_pubkey(self, repo_sec):
        pubkey = repo_sec.get_pubkey(self._repository_id)
        # write pubkey to file and add to data upload
        gpg_path = self._entropy._get_local_repository_gpg_signature_file(
            self._repository_id)
        enc = etpConst['conf_encoding']
        with codecs.open(gpg_path, "w", encoding=enc) as gpg_f:
            gpg_f.write(pubkey)

        return gpg_path

    def update(self):
        """
        Executes the repository update.
        """
        rc, fine_uris, broken_uris = self._sync()
        return rc

    def _is_local_repository_locked(self):
        """
        Return whether repository is locally locked (already).
        """
        lock_file = self._entropy._get_repository_lockfile(self._repository_id)
        return os.path.isfile(lock_file)

    def _calculate_sync_queues(self):

        remote_status = self._mirrors.remote_repository_status(
            self._repository_id).items()
        local_revision = self._entropy.local_repository_revision(
            self._repository_id)
        upload_queue = []
        download_latest = ()

        # all mirrors are empty ? I rule
        if not [x for x in remote_status if x[1]]:
            upload_queue = [x for x in remote_status]
        else:
            highest_remote_revision = max([x[1] for x in remote_status])

            if local_revision < highest_remote_revision:
                for remote_item in remote_status:
                    if remote_item[1] == highest_remote_revision:
                        download_latest = remote_item
                        break

            if download_latest:
                upload_queue = [x for x in remote_status if \
                    (x[1] < highest_remote_revision)]
            else:
                upload_queue = [x for x in remote_status if \
                    (x[1] < local_revision)]

        return download_latest, upload_queue

    def _get_files_to_sync(self, cmethod, download = False,
        disabled_eapis = None):

        if disabled_eapis is None:
            disabled_eapis = []

        critical = []
        extra_text_files = []
        gpg_signed_files = []
        data = {}
        db_rev_file = self._entropy._get_local_repository_revision_file(
            self._repository_id)
        # adding ~ at the beginning makes this file to be appended at the end
        # of the upload queue
        data['~database_revision_file'] = db_rev_file
        extra_text_files.append(db_rev_file)
        critical.append(db_rev_file)

        # branch migration support scripts
        post_branch_mig_file = self._entropy._get_local_post_branch_mig_script(
            self._repository_id)
        if os.path.isfile(post_branch_mig_file) or download:
            extra_text_files.append(post_branch_mig_file)

        post_branch_upg_file = self._entropy._get_local_post_branch_upg_script(
            self._repository_id)
        if os.path.isfile(post_branch_upg_file) or download:
            extra_text_files.append(post_branch_upg_file)

        post_repo_update_file = \
            self._entropy._get_local_post_repo_update_script(
                self._repository_id)
        if os.path.isfile(post_repo_update_file) or download:
            extra_text_files.append(post_repo_update_file)

        database_ts_file = self._entropy._get_local_repository_timestamp_file(
            self._repository_id)
        if os.path.isfile(database_ts_file) or download:
            data['database_timestamp_file'] = database_ts_file
            if not download:
                critical.append(database_ts_file)

        database_package_mask_file = \
            self._entropy._get_local_repository_mask_file(self._repository_id)
        if os.path.isfile(database_package_mask_file) or download:
            extra_text_files.append(database_package_mask_file)

        database_package_system_mask_file = \
            self._entropy._get_local_repository_system_mask_file(
                self._repository_id)
        if os.path.isfile(database_package_system_mask_file) or download:
            extra_text_files.append(database_package_system_mask_file)

        database_license_whitelist_file = \
            self._entropy._get_local_repository_licensewhitelist_file(
                self._repository_id)
        if os.path.isfile(database_license_whitelist_file) or download:
            extra_text_files.append(database_license_whitelist_file)

        database_mirrors_file = \
            self._entropy._get_local_repository_mirrors_file(
                self._repository_id)
        if os.path.isfile(database_mirrors_file) or download:
            extra_text_files.append(database_mirrors_file)

        database_fallback_mirrors_file = \
            self._entropy._get_local_repository_fallback_mirrors_file(
                self._repository_id)
        if os.path.isfile(database_fallback_mirrors_file) or download:
            extra_text_files.append(database_fallback_mirrors_file)

        exp_based_pkgs_removal_file = \
            self._entropy._get_local_exp_based_pkgs_rm_whitelist_file(
                self._repository_id)
        if os.path.isfile(exp_based_pkgs_removal_file) or download:
            extra_text_files.append(exp_based_pkgs_removal_file)

        database_rss_file = self._entropy._get_local_repository_rss_file(
            self._repository_id)
        if os.path.isfile(database_rss_file) or download:
            data['database_rss_file'] = database_rss_file
            if not download:
                critical.append(data['database_rss_file'])
        database_rss_light_file = \
            self._entropy._get_local_repository_rsslight_file(
                self._repository_id)

        if os.path.isfile(database_rss_light_file) or download:
            data['database_rss_light_file'] = database_rss_light_file
            if not download:
                critical.append(data['database_rss_light_file'])

        database_changelog = \
            self._entropy._get_local_repository_changelog_file(
                self._repository_id)
        compressed_database_changelog = \
            self._entropy._get_local_repository_compressed_changelog_file(
                self._repository_id)
        if os.path.isfile(database_changelog) or download:
            data['database_changelog_file'] = compressed_database_changelog
            if not download:
                critical.append(data['database_changelog_file'])

        pkglist_file = self._entropy._get_local_pkglist_file(
            self._repository_id)
        data['pkglist_file'] = pkglist_file
        if not download:
            critical.append(data['pkglist_file'])
        extra_pkglist_file = self._entropy._get_local_extra_pkglist_file(
            self._repository_id)
        data['extra_pkglist_file'] = extra_pkglist_file
        if not download:
            critical.append(data['extra_pkglist_file'])

        critical_updates_file = self._entropy._get_local_critical_updates_file(
            self._repository_id)
        if os.path.isfile(critical_updates_file) or download:
            extra_text_files.append(critical_updates_file)

        restricted_file = self._entropy._get_local_restricted_file(
            self._repository_id)
        if os.path.isfile(restricted_file) or download:
            extra_text_files.append(restricted_file)

        keywords_file = self._entropy._get_local_repository_keywords_file(
            self._repository_id)
        if os.path.isfile(keywords_file) or download:
            extra_text_files.append(keywords_file)

        webserv_file = self._entropy._get_local_repository_webserv_file(
            self._repository_id)
        if os.path.isfile(webserv_file) or download:
            data['webserv_file'] = webserv_file
            extra_text_files.append(webserv_file)

        gpg_file = self._entropy._get_local_repository_gpg_signature_file(
            self._repository_id)
        if os.path.isfile(gpg_file) or download:
            data['gpg_file'] = gpg_file
            # no need to add to extra_text_files, it will be added
            # afterwards
            gpg_signed_files.append(gpg_file)

        # always sync metafiles file, it's cheap
        data['metafiles_path'] = \
            self._entropy._get_local_repository_compressed_metafiles_file(
                self._repository_id)
        critical.append(data['metafiles_path'])
        gpg_signed_files.append(data['metafiles_path'])

        # EAPI 2,3
        if not download: # we don't need to get the dump

            # upload eapi3 signal file
            something_new = os.path.join(
                self._entropy._get_local_repository_dir(self._repository_id),
                etpConst['etpdatabaseeapi3updates'])
            with open(something_new, "wb") as sn_f:
                pass
            data['~~something_new'] = something_new
            critical.append(data['~~something_new'])

            # upload webinstall signal file
            something_new_webinstall = os.path.join(
                self._entropy._get_local_repository_dir(self._repository_id),
                etpConst['etpdatabasewebinstallupdates'])
            with open(something_new_webinstall, "wb") as sn_f:
                pass
            data['~~something_new_web'] = something_new_webinstall
            critical.append(data['~~something_new_web'])

            if 2 not in disabled_eapis:

                data['dump_path_light'] = os.path.join(
                    self._entropy._get_local_repository_dir(
                        self._repository_id), etpConst[cmethod[5]])
                critical.append(data['dump_path_light'])
                gpg_signed_files.append(data['dump_path_light'])

                data['dump_path_digest_light'] = os.path.join(
                    self._entropy._get_local_repository_dir(
                        self._repository_id), etpConst[cmethod[6]])
                critical.append(data['dump_path_digest_light'])
                gpg_signed_files.append(data['dump_path_digest_light'])

        # EAPI 1
        if 1 not in disabled_eapis:

            data['compressed_database_path'] = os.path.join(
                self._entropy._get_local_repository_dir(self._repository_id),
                etpConst[cmethod[2]])
            critical.append(data['compressed_database_path'])
            gpg_signed_files.append(data['compressed_database_path'])

            if not download:
                data['compressed_database_path_light'] = os.path.join(
                    self._entropy._get_local_repository_dir(
                        self._repository_id),
                    etpConst[cmethod[7]])
                critical.append(data['compressed_database_path_light'])
                gpg_signed_files.append(data['compressed_database_path_light'])

            data['database_path_digest'] = os.path.join(
                self._entropy._get_local_repository_dir(self._repository_id),
                etpConst['etpdatabasehashfile']
            )
            critical.append(data['database_path_digest'])
            gpg_signed_files.append(data['database_path_digest'])

            data['compressed_database_path_digest'] = os.path.join(
                self._entropy._get_local_repository_dir(self._repository_id),
                etpConst[cmethod[2]] + etpConst['packagesmd5fileext']
            )
            critical.append(data['compressed_database_path_digest'])
            gpg_signed_files.append(data['compressed_database_path_digest'])

            if not download:
                data['compressed_database_path_digest_light'] = os.path.join(
                    self._entropy._get_local_repository_dir(
                        self._repository_id),
                    etpConst[cmethod[8]]
                    )
                critical.append(data['compressed_database_path_digest_light'])
                gpg_signed_files.append(
                    data['compressed_database_path_digest_light'])

        # Some information regarding how packages are built
        spm_files_map = self._entropy.Spm_class().config_files_map()
        spm_syms = {}
        for myname, myfile in spm_files_map.items():
            if os.path.islink(myfile):
                spm_syms[myname] = myfile
                continue # we don't want symlinks
            if const_file_readable(myfile):
                extra_text_files.append(myfile)

        # NOTE: for symlinks, we read their link and send a file with that
        # content. This is the default behaviour for now and allows to send
        # /etc/make.profile link pointer correctly.
        tmp_dirs = []
        enc = etpConst['conf_encoding']
        for symname, symfile in spm_syms.items():

            mytmpdir = const_mkdtemp(prefix="entropy.server._get_files_to_sync")
            tmp_dirs.append(mytmpdir)
            mytmpfile = os.path.join(mytmpdir, os.path.basename(symfile))
            mylink = os.readlink(symfile)
            with codecs.open(mytmpfile, "w", encoding=enc) as f_mkp:
                f_mkp.write(mylink)

            extra_text_files.append(mytmpfile)

        return data, critical, extra_text_files, tmp_dirs, gpg_signed_files

    def _download(self, uri):
        """
        Download repository metadata from given repository URI.

        @param uri: repository URI
        @type uri: string
        @return: True, if download is successful, otherwise False
        @rtype: bool
        """
        plg_id = self._entropy.SYSTEM_SETTINGS_PLG_ID
        srv_set = self._settings[plg_id]['server']
        disabled_eapis = sorted(srv_set['disabled_eapis'])

        db_format = srv_set['database_file_format']
        cmethod = etpConst['etpdatabasecompressclasses'].get(db_format)
        if cmethod is None:
            raise AttributeError("wrong repository compression method")

        crippled_uri = EntropyTransceiver.get_uri_name(uri)
        database_path = self._entropy._get_local_repository_file(
            self._repository_id)
        database_dir_path = os.path.dirname(
            self._entropy._get_local_repository_file(self._repository_id))

        download_data, critical, text_files, tmp_dirs, \
            gpg_to_verify_files = self._get_files_to_sync(cmethod,
                download = True, disabled_eapis = disabled_eapis)
        broken_uris = set()

        try:

            mytmpdir = const_mkdtemp(prefix="entropy.server._download")

            self._entropy.output(
                "[repo:%s|%s|%s] %s" % (
                    brown(self._repository_id),
                    darkgreen(crippled_uri),
                    red(_("download")),
                    blue(_("preparing to download repository from mirror")),
                ),
                importance = 1,
                level = "info",
                header = darkgreen(" * ")
            )
            for myfile in sorted(download_data.keys()):
                self._entropy.output(
                    "%s: %s" % (
                        blue(_("download path")),
                        brown(download_data[myfile]),
                    ),
                    importance = 0,
                    level = "info",
                    header = brown("    # ")
                )

            # avoid having others messing while we're downloading
            self._mirrors.lock_mirrors(self._repository_id, True,
                mirrors = [uri])

            repo_relative = \
                self._entropy._get_override_remote_repository_relative_path(
                    self._repository_id)
            if repo_relative is None:
                repo_relative = \
                    self._entropy._get_remote_repository_relative_path(
                        self._repository_id)
            remote_dir = os.path.join(repo_relative,
                self._settings['repositories']['branch'])

            # download
            downloader = self._mirrors.TransceiverServerHandler(
                self._entropy, [uri],
                [download_data[x] for x in sorted(download_data)],
                download = True, local_basedir = mytmpdir,
                critical_files = critical,
                txc_basedir = remote_dir, repo = self._repository_id)
            errors, m_fine_uris, m_broken_uris = downloader.go()
            if errors:
                x_uri, reason = m_broken_uris.pop()
                self._entropy.output(
                    "[repo:%s|%s|%s] %s" % (
                        brown(self._repository_id),
                        darkgreen(crippled_uri),
                        red(_("errors")),
                        blue(_("failed to download from mirror")),
                    ),
                    importance = 0,
                    level = "error",
                    header = darkred(" !!! ")
                )
                self._entropy.output(
                    blue("%s: %s" % (_("reason"), reason,)),
                    importance = 0,
                    level = "error",
                    header = blue("    # ")
                )
                self._mirrors.lock_mirrors(self._repository_id, False,
                    mirrors = [uri])
                broken_uris |= m_broken_uris
                return broken_uris

            # all fine then, we need to move data from mytmpdir
            # to database_dir_path

            # EAPI 1 -- unpack database
            if 1 not in disabled_eapis:
                compressed_db_filename = os.path.basename(
                    download_data['compressed_database_path'])
                uncompressed_db_filename = os.path.basename(
                    database_path)
                compressed_file = os.path.join(mytmpdir,
                    compressed_db_filename)
                uncompressed_file = os.path.join(mytmpdir,
                    uncompressed_db_filename)
                entropy.tools.uncompress_file(compressed_file,
                    uncompressed_file, cmethod[0])

            # uncompress changelog
            uncompressed_changelog_name = \
                os.path.basename(
                    self._entropy._get_local_repository_changelog_file(
                        self._repository_id))
            compressed_changelog_name = \
                os.path.basename(
                self._entropy._get_local_repository_compressed_changelog_file(
                    self._repository_id))

            uncompressed_changelog = os.path.join(mytmpdir,
                uncompressed_changelog_name)
            compressed_changelog = os.path.join(mytmpdir,
                compressed_changelog_name)
            if os.path.isfile(compressed_changelog):
                entropy.tools.uncompress_file(compressed_changelog,
                    uncompressed_changelog, bz2.BZ2File)

            # unpack metafiles file
            metafiles_path_name = os.path.basename(
                download_data['metafiles_path'])
            metafiles_path = os.path.join(mytmpdir,
                metafiles_path_name)
            metafiles_unpack_done = entropy.tools.universal_uncompress(
                metafiles_path, mytmpdir,
                    catch_empty = True)
            if not metafiles_unpack_done:
                self._entropy.output(
                    "[repo:%s|%s|%s] %s %s" % (
                        brown(self._repository_id),
                        darkgreen(crippled_uri),
                        red(_("errors")),
                        blue(_("failed to unpack")),
                        os.path.basename(metafiles_path_name),
                    ),
                    importance = 0,
                    level = "error",
                    header = darkred(" !!! ")
                )
                broken_uris.add(uri)
                return broken_uris

            # now move
            for myfile in os.listdir(mytmpdir):
                fromfile = os.path.join(mytmpdir, myfile)
                tofile = os.path.join(database_dir_path, myfile)
                try:
                    os.rename(fromfile, tofile)
                except OSError as err:
                    if err.errno != errno.EXDEV:
                        raise
                    shutil.move(fromfile, tofile)
                const_setup_file(tofile, etpConst['entropygid'], 0o664)

            if os.path.isdir(mytmpdir):
                shutil.rmtree(mytmpdir)
            if os.path.isdir(mytmpdir):
                os.rmdir(mytmpdir)

            # we must unlock all the mirrors not just the one we
            # downloaded from, or it will be stuck in locked state.
            remote_uris = self._entropy.remote_repository_mirrors(
                self._repository_id)
            self._mirrors.lock_mirrors(self._repository_id, False,
                mirrors = remote_uris)

        finally:
            # remove temporary directories
            for tmp_dir in tmp_dirs:
                try:
                    shutil.rmtree(tmp_dir, True)
                except shutil.Error:
                    continue

        return broken_uris

    def _update_feeds(self):

        plg_id = self._entropy.SYSTEM_SETTINGS_PLG_ID
        srv_set = self._settings[plg_id]['server']

        if (not srv_set['rss']['enabled']) and (not srv_set['changelog']):
            # nothing enabled, no reason to stay here more
            return

        enc = etpConst['conf_encoding']
        url = srv_set['rss']['base_url']
        editor = srv_set['rss']['editor']
        product = self._settings['repositories']['product']
        rss_title = "%s Online Repository Status" % (
            self._settings['system']['name'],)
        rss_description = \
            const_convert_to_unicode(
            "Keep you updated on what's going on in the %s Repository." % (
                self._settings['system']['name'],))
        rss_dump_name = self._repository_id + etpConst['rss-dump-name']
        db_revision_path = self._entropy._get_local_repository_revision_file(
            self._repository_id)
        # load dump
        db_actions = self._cacher.pop(rss_dump_name,
            cache_dir = self._entropy.CACHE_DIR)

        try:
            with codecs.open(db_revision_path, "r", encoding=enc) as f_rev:
                revision = f_rev.readline().strip()
        except IOError as err:
            if err.errno != errno.ENOENT:
                raise
            revision = const_convert_to_unicode("N/A")

        commit_msg = ServerRssMetadata()['commitmessage'] or \
            const_convert_to_unicode("no commit message")

        if srv_set['rss']['enabled']:

            rss_path = self._entropy._get_local_repository_rss_file(
                self._repository_id)

            rss_main = FastRSS(rss_path)
            rss_main.set_title(rss_title).set_description(
                rss_description).set_max_entries(
                    srv_set['rss']['max_entries']).set_url(url).set_editor(
                        editor)

            if db_actions:

                title = const_convert_to_unicode(": ")
                title += self._settings['system']['name']
                title += const_convert_to_unicode(" ")
                title += self._settings['repositories']['branch']
                title += const_convert_to_unicode(" ")
                title += product.title()
                title += const_convert_to_unicode(" :: Revision: ")
                title += revision
                title += const_convert_to_unicode(" :: ")
                title += commit_msg

                link = srv_set['rss']['base_url']
                # create description
                added_items = db_actions.get("added")

                if added_items:
                    for atom in sorted(added_items):
                        mylink = link + entropy.dep.remove_entropy_revision(
                            atom)
                        description = atom
                        description += const_convert_to_unicode(": ")
                        description += const_convert_to_unicode(
                            added_items[atom]['description'])
                        atom_title = const_convert_to_unicode("Added/Updated ")
                        atom_title += title
                        rss_main.append(atom_title,
                            mylink, description, None)
                removed_items = db_actions.get("removed")

                if removed_items:
                    for atom in sorted(removed_items):
                        mylink = link + entropy.dep.remove_entropy_revision(
                            atom)
                        description = atom
                        description += const_convert_to_unicode(": ")
                        description += const_convert_to_unicode(
                            removed_items[atom]['description'])
                        atom_title = const_convert_to_unicode("Removed ")
                        atom_title += title
                        rss_main.append(atom_title,
                            mylink, description, None)

                rss_main.commit()

                rss_light_path = \
                    self._entropy._get_local_repository_rsslight_file(
                        self._repository_id)
                light_items = db_actions.get('light', {})

                rss_light = FastRSS(rss_light_path)
                rss_light.set_title(rss_title).set_description(
                    rss_description).set_max_entries(
                        srv_set['rss']['light_max_entries']).set_url(
                            url).set_editor(editor)

                for atom in sorted(light_items):
                    mylink = link + entropy.dep.remove_entropy_revision(
                        atom)
                    description = light_items[atom]['description']
                    atom_title = const_convert_to_unicode("[%s] " % (revision,))
                    atom_title += atom
                    rss_light.append(atom_title,
                        mylink, description, None)

                if light_items:
                    rss_light.commit()

        _uname = os.uname()
        msg = const_convert_to_unicode("\n    ").join(
            commit_msg.split(const_convert_to_unicode("\n")))
        msg = msg.rstrip()

        def _write_changelog_entry(changelog_f, atom, pkg_meta):
            this_time = time.strftime(etpConst['changelog_date_format'])
            changelog_str = const_convert_to_unicode("""\
commit %s; %s; %s
Machine: %s; %s; %s
Date:    %s
Name:    %s

    """ % (revision, pkg_meta['package_id'], pkg_meta['time_hash'],
            _uname[1], _uname[2], _uname[4], this_time, atom,))
            changelog_str += msg
            changelog_str += const_convert_to_unicode("\n\n")

            # append at the bottom and don't care here
            changelog_f.write(changelog_str)

        if db_actions is None:
            light_items = None
        else:
            light_items = db_actions.get('light')
        if srv_set['changelog'] and db_actions and light_items:
            changelog_path = \
                self._entropy._get_local_repository_changelog_file(
                    self._repository_id)
            enc = etpConst['conf_encoding']

            tmp_fd, tmp_path = const_mkstemp(
                dir=os.path.dirname(changelog_path))

            with entropy.tools.codecs_fdopen(tmp_fd, "w", enc) as tmp_f:

                # write new changelog entries here
                atoms = list(light_items.keys())
                atoms.sort()
                for atom in atoms:
                    pkg_meta = light_items[atom]
                    _write_changelog_entry(tmp_f, atom, pkg_meta)

                # append the rest of the file
                try:
                    with codecs.open(changelog_path, "r", encoding=enc) \
                            as changelog_f:
                        chunk = changelog_f.read(16384)
                        while chunk:
                            tmp_f.write(chunk)
                            chunk = changelog_f.read(16384)
                except IOError as err:
                    if err.errno != errno.ENOENT:
                        raise
                    # otherwise ignore append, there is no file yet

            # someday unprivileged users will be able to push stuff
            const_setup_file(tmp_path, etpConst['entropygid'], 0o664)
            # atomicity
            os.rename(tmp_path, changelog_path)

        ServerRssMetadata().clear()
        EntropyCacher.clear_cache_item(rss_dump_name,
            cache_dir = self._entropy.CACHE_DIR)

    def _update_repository_timestamp(self):
        """
        Update the repository timestamp file.
        """
        from datetime import datetime
        ts_file = self._entropy._get_local_repository_timestamp_file(
            self._repository_id)
        current_ts = "%s" % (datetime.fromtimestamp(time.time()),)
        enc = etpConst['conf_encoding']
        with codecs.open(ts_file, "w", encoding=enc) as ts_f:
            ts_f.write(current_ts)

    def _create_repository_pkglist(self):
        """
        Create the repository packages list file.
        """
        pkglist_file = self._entropy._get_local_pkglist_file(
            self._repository_id)
        extra_pkglist_file = self._entropy._get_local_extra_pkglist_file(
            self._repository_id)

        tmp_pkglist_file = pkglist_file + ".tmp"
        tmp_extra_pkglist_file = extra_pkglist_file + ".tmp"
        dbconn = self._entropy.open_server_repository(
            self._repository_id, just_reading = True, do_treeupdates = False)
        pkglist = dbconn.listAllDownloads(do_sort = True, full_path = True)
        extra_pkglist = dbconn.listAllExtraDownloads(do_sort = True)

        enc = etpConst['conf_encoding']
        with codecs.open(tmp_pkglist_file, "w", encoding=enc) as pkg_f:
            for pkg in pkglist:
                pkg_f.write(pkg)
                pkg_f.write("\n")

        os.rename(tmp_pkglist_file, pkglist_file)

        with codecs.open(tmp_extra_pkglist_file, "w", encoding=enc) as pkg_f:
            for pkg in extra_pkglist:
                pkg_f.write(pkg)
                pkg_f.write("\n")

        os.rename(tmp_extra_pkglist_file, extra_pkglist_file)

    def _cleanup_trashed_spm_uids(self, entropy_repository):
        """
        Cleanup the list of SPM package UIDs marked as trashed.
        """
        # generate in-memory map
        uids_map = {}
        spm = self._entropy.Spm()
        spm_packages = spm.get_installed_packages()
        for pkg in spm_packages:
            try:
                uid = spm.resolve_spm_package_uid(pkg)
            except KeyError:
                uid = None
            uids_map[uid] = pkg

        uids_map_keys = set(uids_map.keys())
        dead_uids = entropy_repository.listAllTrashedSpmUids()
        really_dead = dead_uids - uids_map_keys

        # then cycle all the repositories looking for
        # uids still alive
        spm_uids = set()
        for repository_id in self._entropy.repositories():
            repo = self._entropy.open_repository(repository_id)
            spm_uids |= set([x for x, y in repo.listAllSpmUids()])
        really_dead -= spm_uids

        if really_dead:
            entropy_repository.removeTrashedUids(really_dead)

    def _rewrite_treeupdates(self, entropy_repository):
        """
        Rewrite (and sync) packages category and name update metadata
        reading across all the available repositories and writing to the
        one being worked out.
        """
        all_actions_cache = set()
        all_actions = []
        for repository_id in self._entropy.repositories():

            # avoid __default__
            if repository_id == InstalledPackagesRepository.NAME:
                continue

            repo = self._entropy.open_repository(repository_id)
            actions = repo.listAllTreeUpdatesActions(no_ids_repos = True)
            for command, branch, date in actions:
                # filter duplicates and respect the original order
                # keep the first entry.
                key = (command, branch)
                if key in all_actions_cache:
                    continue
                all_actions_cache.add(key)
                all_actions.append((command, branch, date))

        backed_up_entries = entropy_repository.listAllTreeUpdatesActions()
        # clear first
        entropy_repository.removeTreeUpdatesActions(self._repository_id)
        try:
            entropy_repository.insertTreeUpdatesActions(all_actions,
                self._repository_id)
        except Exception as err:
            entropy_repository.rollback()
            entropy.tools.print_traceback()
            mytxt = "%s, %s: %s. %s" % (
                _("Troubles with treeupdates"),
                _("error"),
                err,
                _("Bumping old data back"),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning"
            )
            entropy_repository.bumpTreeUpdatesActions(backed_up_entries)

    def _show_package_sets_messages(self):

        self._entropy.output(
            "[repo:%s] %s:" % (
                brown(self._repository_id),
                blue(_("configured package sets")),
            ),
            importance = 0,
            level = "info",
            header = darkgreen(" * ")
        )
        sets_data = self._entropy.sets_available(
            match_repo = [self._repository_id])
        if not sets_data:
            self._entropy.output(
                "%s" % (_("None configured"),),
                importance = 0,
                level = "info",
                header = brown("    # ")
            )
            return
        sorter = lambda x: x[1]
        for s_repo, s_name, s_sets in sorted(sets_data, key = sorter):
            self._entropy.output(
                blue("%s" % (s_name,)),
                importance = 0,
                level = "info",
                header = brown("    # ")
            )

    def _shrink_and_close(self, entropy_repository):
        """
        Helper method that shinks, cleans and eventually close an Entropy
        Repository instance.
        """
        entropy_repository.clean()
        entropy_repository.dropAllIndexes()
        # NOTE: this takes a huge amount of space and it's not needed
        # anymore at this point, since all this data went to package files
        # directly. It is safe to consider a complete drop at this point, then.
        entropy_repository.dropContentSafety()
        entropy_repository.vacuum()
        entropy_repository.vacuum()
        entropy_repository.commit()
        self._entropy.close_repository(entropy_repository)

    def _show_eapi2_upload_messages(self, crippled_uri, database_path,
        upload_data, cmethod):

        self._entropy.output(
            "[repo:%s|%s|%s:%s] %s" % (
                brown(self._repository_id),
                darkgreen(crippled_uri),
                red("EAPI"),
                bold("2"),
                blue(_("creating compressed repository dump + checksum")),
            ),
            importance = 0,
            level = "info",
            header = darkgreen(" * ")
        )
        self._entropy.output(
            "%s: %s" % (_("repository path"), blue(database_path),),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (
                _("dump light"),
                blue(upload_data['dump_path_light']),
            ),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (
                _("dump light checksum"),
                blue(upload_data['dump_path_digest_light']),
            ),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )

        self._entropy.output(
            "%s: %s" % (_("opener"), blue(str(cmethod[0])),),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )

    def _show_eapi1_upload_messages(self, crippled_uri, database_path,
        upload_data, cmethod):

        self._entropy.output(
            "[repo:%s|%s|%s:%s] %s" % (
                brown(self._repository_id),
                darkgreen(crippled_uri),
                red("EAPI"),
                bold("1"),
                blue(_("compressing repository + checksum")),
            ),
            importance = 0,
            level = "info",
            header = darkgreen(" * "),
            back = True
        )
        self._entropy.output(
            "%s: %s" % (_("repository path"), blue(database_path),),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (
                _("compressed repository path"),
                blue(upload_data['compressed_database_path']),
            ),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (
                _("repository checksum"),
                blue(upload_data['database_path_digest']),
            ),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (
                _("compressed checksum"),
                blue(upload_data['compressed_database_path_digest']),
            ),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )
        self._entropy.output(
            "%s: %s" % (_("opener"), blue(str(cmethod[0])),),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )

    def _show_eapi3_upload_messages(self, crippled_uri, database_path):

        self._entropy.output(
            "[repo:%s|%s|%s:%s] %s" % (
                brown(self._repository_id),
                darkgreen(crippled_uri),
                red("EAPI"),
                bold("3"),
                blue(_("preparing uncompressed repository for the upload")),
            ),
            importance = 0,
            level = "info",
            header = darkgreen(" * ")
        )
        self._entropy.output(
            "%s: %s" % (_("repository path"), blue(database_path),),
            importance = 0,
            level = "info",
            header = brown("    # ")
        )

    def _create_file_checksum(self, file_path, checksum_path):
        """
        Similar to entropy.tools.create_md5_file.
        """
        mydigest = entropy.tools.md5sum(file_path)
        enc = etpConst['conf_encoding']
        with codecs.open(checksum_path, "w", encoding=enc) as f_ck:
            fname = os.path.basename(file_path)
            f_ck.write(mydigest)
            f_ck.write("  ")
            f_ck.write(fname)
            f_ck.write("\n")


    def _compress_file(self, file_path, destination_path, opener):
        """
        Compress a file using compressor at opener.
        """
        f_out = opener(destination_path, "wb")
        try:
            with open(file_path, "rb") as f_in:
                data = f_in.read(8192)
                while data:
                    f_out.write(data)
                    data = f_in.read(8192)
        finally:
            if hasattr(f_out, 'flush'):
                f_out.flush()
            f_out.close()

    def _create_upload_gpg_signatures(self, upload_data, to_sign_files):
        """
        This method creates .asc files for every path that is going to be
        uploaded. upload_data directly comes from _upload_database()
        """
        repo_sec = self.__get_repo_security_intf()
        if repo_sec is None:
            return

        # for every item in upload_data, create a gpg signature
        gpg_upload_data = {}
        for item_id, item_path in upload_data.items():
            if item_path not in to_sign_files:
                continue
            if const_file_readable(item_path):
                gpg_item_id = item_id + "_gpg_sign_part"
                if gpg_item_id in upload_data:
                    raise KeyError("wtf!")
                sign_path = repo_sec.sign_file(self._repository_id, item_path)
                gpg_upload_data[gpg_item_id] = sign_path
        upload_data.update(gpg_upload_data)

    def _create_metafiles_file(self, compressed_dest_path, file_list):

        found_file_list = [x for x in file_list if os.path.isfile(x) and \
            const_file_readable(x)]

        not_found_file_list = ["%s\n" % (os.path.basename(x),) for x in \
            file_list if x not in found_file_list]

        # GPG, also pack signature.asc inside
        repo_sec = self.__get_repo_security_intf()
        if repo_sec is not None:
            gpg_path = self.__write_gpg_pubkey(repo_sec)
            if gpg_path is not None:
                found_file_list.append(gpg_path)
            else:
                gpg_path = \
                    self._entropy._get_local_repository_gpg_signature_file(
                        self._repository_id)
                not_found_file_list.append(gpg_path) # not found

        metafile_not_found_file = \
            self._entropy._get_local_repository_metafiles_not_found_file(
                self._repository_id)
        enc = etpConst['conf_encoding']
        with codecs.open(metafile_not_found_file, "w", encoding=enc) as f_meta:
            f_meta.writelines(not_found_file_list)

        found_file_list.append(metafile_not_found_file)
        if os.path.isfile(compressed_dest_path):
            os.remove(compressed_dest_path)

        entropy.tools.compress_files(compressed_dest_path, found_file_list)

    def _upload(self, uris):
        """
        Upload repository metadata to given repository URIs.

        @param uri: repository URIs
        @type uri: list of string
        @return: list (set) of broken uris
        @rtype: set of string
        """
        plg_id = self._entropy.SYSTEM_SETTINGS_PLG_ID
        srv_set = self._settings[plg_id]['server']
        self._update_feeds()

        broken_uris = set()
        disabled_eapis = sorted(srv_set['disabled_eapis'])
        db_format = srv_set['database_file_format']
        cmethod = etpConst['etpdatabasecompressclasses'].get(db_format)
        if cmethod is None:
            raise AttributeError("wrong repository compression method passed")
        database_path = self._entropy._get_local_repository_file(
            self._repository_id)

        if disabled_eapis:
            self._entropy.output(
                "[repo:%s|%s] %s: %s" % (
                    blue(self._repository_id),
                    darkgreen(_("upload")),
                    darkred(_("disabled EAPI")),
                    bold(', '.join([str(x) for x in disabled_eapis])),
                ),
                importance = 1,
                level = "warning",
                header = darkgreen(" * ")
            )

        # create/update timestamp file
        self._update_repository_timestamp()
        # create pkglist service file
        self._create_repository_pkglist()

        upload_data, critical, text_files, tmp_dirs, gpg_to_sign_files = \
            self._get_files_to_sync(cmethod, disabled_eapis = disabled_eapis)

        self._entropy.output(
            "[repo:%s|%s] %s" % (
                blue(self._repository_id),
                darkgreen(_("upload")),
                darkgreen(_("preparing to upload repository to mirror")),
            ),
            importance = 1,
            level = "info",
            header = darkgreen(" * ")
        )

        dbconn = self._entropy.open_server_repository(self._repository_id,
            read_only = False, no_upload = True, do_treeupdates = False)
        self._rewrite_treeupdates(dbconn)
        self._cleanup_trashed_spm_uids(dbconn)
        self._entropy._update_package_sets(self._repository_id, dbconn)
        # Package Sets info
        self._show_package_sets_messages()

        dbconn.commit()
        # now we can safely copy it

        # backup current database to avoid re-indexing
        old_dbpath = self._entropy._get_local_repository_file(
            self._repository_id)
        backup_dbpath = old_dbpath + ".up_backup"
        try:
            try:
                os.remove(backup_dbpath)
            except (OSError, IOError) as err:
                if err.errno != errno.ENOENT:
                    raise

            shutil.copy2(old_dbpath, backup_dbpath)
            copy_back = True
        except shutil.Error:
            copy_back = False

        self._shrink_and_close(dbconn)

        if 2 not in disabled_eapis:
            self._show_eapi2_upload_messages("~all~", database_path,
                upload_data, cmethod)

            # create compressed dump + checksum
            eapi2_dbfile = self._entropy._get_local_repository_file(
                self._repository_id)
            temp_eapi2_dbfile = eapi2_dbfile+".light_eapi2.tmp"
            shutil.copy2(eapi2_dbfile, temp_eapi2_dbfile)
            # open and remove content table
            eapi2_tmp_dbconn = \
                self._entropy.open_generic_repository(
                    temp_eapi2_dbfile, indexing_override = False,
                    xcache = False)
            eapi2_tmp_dbconn.dropContent()
            eapi2_tmp_dbconn.dropChangelog()
            eapi2_tmp_dbconn.commit()

            # opener = cmethod[0]
            f_out = cmethod[0](upload_data['dump_path_light'], "wb")
            try:
                eapi2_tmp_dbconn.exportRepository(f_out)
            finally:
                f_out.close()
                eapi2_tmp_dbconn.close()

            os.remove(temp_eapi2_dbfile)
            self._create_file_checksum(upload_data['dump_path_light'],
                upload_data['dump_path_digest_light'])

        if 1 not in disabled_eapis:

            self._show_eapi1_upload_messages("~all~", database_path,
                upload_data, cmethod)

            # compress the database and create uncompressed
            # database checksum -- DEPRECATED
            self._compress_file(database_path,
                upload_data['compressed_database_path'], cmethod[0])
            self._create_file_checksum(database_path,
                upload_data['database_path_digest'])

            # create compressed database checksum
            self._create_file_checksum(
                upload_data['compressed_database_path'],
                upload_data['compressed_database_path_digest'])

            # create light version of the compressed db
            eapi1_dbfile = self._entropy._get_local_repository_file(
                self._repository_id)
            temp_eapi1_dbfile = eapi1_dbfile+".light"
            shutil.copy2(eapi1_dbfile, temp_eapi1_dbfile)
            # open and remove content table
            eapi1_tmp_dbconn = \
                self._entropy.open_generic_repository(
                    temp_eapi1_dbfile, indexing_override = False,
                    xcache = False)
            eapi1_tmp_dbconn.dropContent()
            eapi1_tmp_dbconn.dropChangelog()
            eapi1_tmp_dbconn.commit()
            eapi1_tmp_dbconn.vacuum()
            eapi1_tmp_dbconn.close()

            # compress
            self._compress_file(temp_eapi1_dbfile,
                upload_data['compressed_database_path_light'], cmethod[0])
            # go away, we don't need you anymore
            os.remove(temp_eapi1_dbfile)
            # create compressed light database checksum
            self._create_file_checksum(
                upload_data['compressed_database_path_light'],
                upload_data['compressed_database_path_digest_light'])

        # always upload metafile, it's cheap and also used by EAPI1,2
        self._create_metafiles_file(upload_data['metafiles_path'],
            text_files)
        # Setup GPG signatures for files that are going to be uploaded
        self._create_upload_gpg_signatures(upload_data, gpg_to_sign_files)

        # compress changelog
        uncompressed_changelog = \
            self._entropy._get_local_repository_changelog_file(
                self._repository_id)
        compressed_changelog = upload_data.get('database_changelog_file')
        if compressed_changelog is not None:
            self._compress_file(uncompressed_changelog,
                compressed_changelog, bz2.BZ2File)

        for uri in uris:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            # EAPI 3
            if 3 not in disabled_eapis:
                self._show_eapi3_upload_messages(crippled_uri, database_path)

            repo_relative = \
                self._entropy._get_override_remote_repository_relative_path(
                    self._repository_id)
            if repo_relative is None:
                repo_relative = \
                    self._entropy._get_remote_repository_relative_path(
                        self._repository_id)
            remote_dir = os.path.join(repo_relative,
                self._settings['repositories']['branch'])

            uploader = self._mirrors.TransceiverServerHandler(
                self._entropy, [uri],
                [upload_data[x] for x in sorted(upload_data)],
                critical_files = critical,
                txc_basedir = remote_dir, repo = self._repository_id
            )
            errors, m_fine_uris, m_broken_uris = uploader.go()
            if errors:
                self._entropy.output(
                    "[repo:%s|%s|%s] %s" % (
                        self._repository_id,
                        crippled_uri,
                        _("errors"),
                        _("upload failed, locking and continuing"),
                    ),
                    importance = 0,
                    level = "error",
                    header = darkred(" !!! ")
                )
                # get reason
                my_broken_uris = sorted([
                    (EntropyTransceiver.get_uri_name(x_uri),
                        x_uri_rc) for x_uri, x_uri_rc in m_broken_uris])
                reason = my_broken_uris[0][1]
                self._entropy.output(
                    blue("%s: %s" % (_("reason"), reason,)),
                    importance = 0,
                    level = "error",
                    header = blue("    # ")
                )
                broken_uris |= m_broken_uris
                self._mirrors.lock_mirrors_for_download(self._repository_id,
                    True, mirrors = [uri])
                continue

        if copy_back:
            # copy db back
            self._entropy.close_repositories()
            os.rename(backup_dbpath, old_dbpath)

        # remove temporary directories
        for tmp_dir in tmp_dirs:
            try:
                shutil.rmtree(tmp_dir, True)
            except shutil.Error:
                continue

        return broken_uris

    def _sync(self):

        while True:

            db_locked = False
            if self._is_local_repository_locked():
                db_locked = True

            lock_data = self._mirrors.mirrors_status(self._repository_id)
            mirrors_locked = [x for x in lock_data if x[1]]

            if not mirrors_locked and db_locked:
                # mirrors not locked remotely but only locally
                mylock_file = self._entropy._get_repository_lockfile(
                    self._repository_id)

                try:
                    os.remove(mylock_file)
                    continue
                except (OSError, IOError) as err:
                    if err.errno != errno.ENOENT:
                        raise

            break

        if mirrors_locked and not db_locked:
            raise OnlineMirrorError("mirrors are locked by an external source.")

        download_latest, upload_queue = self._calculate_sync_queues()

        if not download_latest and not upload_queue:
            self._entropy.output(
                "[repo:%s|%s] %s" % (
                    brown(self._repository_id),
                    red(_("sync")), # something short please
                    blue(_("repository already in sync")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            return 0, set(), set()

        if download_latest and not self._enable_download:
            self._entropy.output(
                "[repo:%s|%s] %s" % (
                    brown(self._repository_id),
                    red(_("sync")), # something short please
                    blue(_("remote repository newer than local, please pull.")),
                ),
                importance = 1,
                level = "error",
                header = darkred(" @@ ")
            )
            return 1, set(), set([download_latest[0]])

        if download_latest and self._enable_download:
            # close all the currently open repos
            self._entropy.close_repositories()
            download_uri = download_latest[0]
            error = self._download(download_uri)
            if error:
                self._entropy.output(
                    "[repo:%s|%s] %s: %s" % (
                        brown(self._repository_id),
                        red(_("sync")),
                        blue(_("repository sync failed")),
                        red(_("download issues")),
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" @@ ")
                )
                return 1, set(), set([download_uri])

        if upload_queue and not self._enable_upload:
            self._entropy.output(
                "[repo:%s|%s] %s" % (
                    brown(self._repository_id),
                    red(_("sync")), # something short please
                    blue(_("local repository newer than remote, please push.")),
                ),
                importance = 1,
                level = "error",
                header = darkred(" @@ ")
            )
            return 1, set(), set(upload_queue)

        elif upload_queue and self._enable_upload:

            # Some internal QA checks, make sure everything is fine
            # on the repo
            plg_id = self._entropy.SYSTEM_SETTINGS_PLG_ID
            srv_set = self._settings[plg_id]['server']
            qa_sets = self._settings[plg_id]['qa_sets']
            base_repo = srv_set['base_repository_id']
            community_mode = srv_set['community_mode']
            if base_repo is None:
                base_repo = self._repository_id

            # check against missing package sets
            pkg_sets_required = qa_sets.get(self._repository_id)
            if pkg_sets_required is not None:
                sets_resynced = False
                while True:
                    sets_data = self._entropy.sets_available(
                        match_repo = (self._repository_id,))
                    if not sets_data:
                        break

                    current_sets = set([s_name for \
                        s_repo, s_name, s_sets in sets_data])
                    missing_sets = pkg_sets_required - current_sets
                    if not missing_sets:
                        break

                    if not sets_resynced:
                        # try to re-sync and check agains
                        sets_resynced = True
                        self._entropy._sync_package_sets(
                            self._entropy.open_server_repository(
                                self._repository_id, indexing = False,
                                do_treeupdates = False))
                        continue

                    missing_sets = sorted(missing_sets)
                    self._entropy.output(
                        "[repo:%s|%s] %s, %s:" % (
                            brown(self._repository_id),
                            red(_("sync")),
                            blue(_("repository sync forbidden")),
                            red(_("missing package sets")),
                        ),
                        importance = 1,
                        level = "error",
                        header = darkred(" !! ")
                    )
                    for missing_set in missing_sets:
                        self._entropy.output(
                            teal(missing_set),
                            importance = 0,
                            level = "error",
                            header = brown("  # ")
                        )

                    if not self._force:
                        return 5, set(), set()

            # missing dependencies QA test
            deps_not_found = self._entropy.extended_dependencies_test(
                [self._repository_id])
            if deps_not_found and not community_mode:

                self._entropy.output(
                    "[repo:%s|%s] %s: %s" % (
                        brown(self._repository_id),
                        red(_("sync")),
                        blue(_("repository sync forbidden")),
                        red(_("dependencies test reported errors")),
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" !!! ")
                )
                if not self._force:
                    return 3, set(), set()

            # ask Spm to scan system
            spm_class = self._entropy.Spm_class()
            exit_st, err_msg = spm_class.execute_system_qa_tests(self._entropy)
            if exit_st != 0:
                self._entropy.output(
                    "[repo:%s|%s] %s: %s" % (
                        brown(self._repository_id),
                        red(_("sync")),
                        blue(_("repository sync forbidden")),
                        red(err_msg),
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" !!! ")
                )
                # do not use self._force, because packages are badly broken if
                # we get here.
                return 4, set(), set()

            uris = [x[0] for x in upload_queue]
            broken_uris = self._upload(uris)
            if broken_uris:
                self._entropy.output(
                    "[repo:%s|%s] %s: %s" % (
                        brown(self._repository_id),
                        red(_("sync")),
                        blue(_("repository sync failed")),
                        red(_("upload issues")),
                    ),
                    importance = 1,
                    level = "error",
                    header = darkred(" !!! ")
                )
                return 2, (set(uris) - broken_uris), broken_uris


        self._entropy.output(
            "[repo:%s|%s] %s" % (
                brown(self._repository_id),
                red(_("sync")),
                blue(_("repository sync completed")),
            ),
            importance = 1,
            level = "info",
            header = darkgreen(" * ")
        )

        return 0, set(), set()
