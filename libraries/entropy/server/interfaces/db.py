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
import tempfile
import time

from entropy.const import etpConst, const_setup_file
from entropy.core import Singleton
from entropy.db import EntropyRepository
from entropy.transceivers import EntropyTransceiver
from entropy.output import red, darkgreen, bold, brown, blue, darkred, teal, \
    purple
from entropy.misc import RSS
from entropy.cache import EntropyCacher
from entropy.exceptions import OnlineMirrorError
from entropy.security import Repository as RepositorySecurity
from entropy.client.interfaces.db import CachedRepository
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

    def __create_if_necessary(self, db):
        if db not in self.__data:
            self.__data[db] = {}
            self.__data[db]['tainted'] = False
            self.__data[db]['bumped'] = False
            self.__data[db]['unlock_msg'] = False

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

    def get_updates_log(self, db):
        """
        Return dict() object containing metadata related to package
        updates occured in a server-side repository.
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
    def update(entropy_client, repository_id, force, gpg):
        """
        Reimplemented from EntropyRepository
        """
        return ServerPackagesRepositoryUpdater(entropy_client, repository_id,
            force).update()

    def handlePackage(self, pkg_data, forcedRevision = -1,
        formattedContent = False):
        """
        Reimplemented from EntropyRepository.
        """

        # build atom string, server side
        pkgatom = entropy.dep.create_package_atom_string(
            pkg_data['category'], pkg_data['name'], pkg_data['version'],
            pkg_data['versiontag'])

        current_rev = forcedRevision

        manual_deps = set()
        # Remove entries in the same scope.
        for package_id in self.getPackageIds(pkgatom):

            if forcedRevision == -1:
                myrev = self.retrieveRevision(package_id)
                if myrev > current_rev:
                    current_rev = myrev

            #
            manual_deps |= self.retrieveManualDependencies(package_id,
                resolve_conditional_deps = False)
            # injected packages wouldn't be removed by addPackage
            self.removePackage(package_id, do_cleanup = False,
                do_commit = False)

        if forcedRevision == -1:
            current_rev += 1

        # manual dependencies handling
        removelist = self.getPackagesToRemove(
            pkg_data['name'], pkg_data['category'],
            pkg_data['slot'], pkg_data['injected']
        )

        for r_package_id in removelist:
            manual_deps |= self.retrieveManualDependencies(r_package_id,
                resolve_conditional_deps = False)
            self.removePackage(r_package_id, do_cleanup = False,
                do_commit = False)

        # inject old manual dependencies back to package metadata
        for manual_dep in manual_deps:
            if manual_dep in pkg_data['dependencies']:
                continue
            pkg_data['dependencies'][manual_dep] = \
                etpConst['dependency_type_ids']['mdepend_id']

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


class ServerPackagesRepositoryUpdater(object):

    """
    This class handles the repository update across all the configured mirrors.
    It is used by entropy.server.interfaces.mirrors module and called from
    inside ServerPackagesRepository class.
    """

    def __init__(self, entropy_server, repository_id, force):
        """
        ServerPackagesRepositoryUpdater constructor, called by
        ServerPackagesRepository.

        @param force: if True, repository will be uploaded for syncing if
            required
        @type force: bool
        """
        self._entropy = entropy_server
        self._mirrors = self._entropy.Mirrors
        self._settings = self._entropy.Settings()
        self._cacher = EntropyCacher()
        self._repository_id = repository_id
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
        with open(gpg_path, "w") as gpg_f:
            gpg_f.write(pubkey)
            gpg_f.flush()
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
            upload_queue = remote_status[:]
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
            if download:
                data['database_post_branch_hop_script'] = post_branch_mig_file
            extra_text_files.append(post_branch_mig_file)

        post_branch_upg_file = self._entropy._get_local_post_branch_upg_script(
            self._repository_id)
        if os.path.isfile(post_branch_upg_file) or download:
            if download:
                data['database_post_branch_upgrade_script'] = \
                    post_branch_upg_file
            extra_text_files.append(post_branch_upg_file)

        post_repo_update_file = \
            self._entropy._get_local_post_repo_update_script(
                self._repository_id)
        if os.path.isfile(post_repo_update_file) or download:
            if download:
                data['database_post_repo_update_script'] = post_repo_update_file
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
            if download:
                data['database_package_mask_file'] = database_package_mask_file
            extra_text_files.append(database_package_mask_file)

        database_package_system_mask_file = \
            self._entropy._get_local_repository_system_mask_file(
                self._repository_id)
        if os.path.isfile(database_package_system_mask_file) or download:
            if download:
                data['database_package_system_mask_file'] = \
                    database_package_system_mask_file
            extra_text_files.append(database_package_system_mask_file)

        database_package_confl_tagged_file = \
            self._entropy._get_local_repository_confl_tagged_file(
                self._repository_id)
        if os.path.isfile(database_package_confl_tagged_file) or download:
            if download:
                data['database_package_confl_tagged_file'] = \
                    database_package_confl_tagged_file
            extra_text_files.append(database_package_confl_tagged_file)

        database_license_whitelist_file = \
            self._entropy._get_local_repository_licensewhitelist_file(
                self._repository_id)
        if os.path.isfile(database_license_whitelist_file) or download:
            if download:
                data['database_license_whitelist_file'] = \
                    database_license_whitelist_file
            extra_text_files.append(database_license_whitelist_file)

        database_mirrors_file = \
            self._entropy._get_local_repository_mirrors_file(
                self._repository_id)
        if os.path.isfile(database_mirrors_file) or download:
            if download:
                data['database_mirrors_file'] = \
                    database_mirrors_file
            extra_text_files.append(database_mirrors_file)

        database_fallback_mirrors_file = \
            self._entropy._get_local_repository_fallback_mirrors_file(
                self._repository_id)
        if os.path.isfile(database_fallback_mirrors_file) or download:
            if download:
                data['database_fallback_mirrors_file'] = \
                    database_fallback_mirrors_file
            extra_text_files.append(database_fallback_mirrors_file)

        exp_based_pkgs_removal_file = \
            self._entropy._get_local_exp_based_pkgs_rm_whitelist_file(
                self._repository_id)
        if os.path.isfile(exp_based_pkgs_removal_file) or download:
            if download:
                data['exp_based_pkgs_removal_file'] = \
                    exp_based_pkgs_removal_file
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

        pkglist_file = self._entropy._get_local_pkglist_file(
            self._repository_id)
        data['pkglist_file'] = pkglist_file
        if not download:
            critical.append(data['pkglist_file'])

        critical_updates_file = self._entropy._get_local_critical_updates_file(
            self._repository_id)
        if os.path.isfile(critical_updates_file) or download:
            if download:
                data['critical_updates_file'] = critical_updates_file
            extra_text_files.append(critical_updates_file)

        restricted_file = self._entropy._get_local_restricted_file(
            self._repository_id)
        if os.path.isfile(restricted_file) or download:
            if download:
                data['restricted_file'] = restricted_file
            extra_text_files.append(restricted_file)

        keywords_file = self._entropy._get_local_repository_keywords_file(
            self._repository_id)
        if os.path.isfile(keywords_file) or download:
            if download:
                data['keywords_file'] = keywords_file
            extra_text_files.append(keywords_file)

        gpg_file = self._entropy._get_local_repository_gpg_signature_file(
            self._repository_id)
        if os.path.isfile(gpg_file) or download:
            data['gpg_file'] = gpg_file
            # no need to add to extra_text_files, it will be added
            # afterwards
            gpg_signed_files.append(gpg_file)

        # EAPI 2,3
        if not download: # we don't need to get the dump

            # upload eapi3 signal file
            something_new = os.path.join(
                self._entropy._get_local_repository_dir(self._repository_id),
                etpConst['etpdatabaseeapi3updates'])
            with open(something_new, "w") as sn_f:
                sn_f.flush()
            data['~~something_new'] = something_new
            critical.append(data['~~something_new'])

            # upload webinstall signal file
            something_new_webinstall = os.path.join(
                self._entropy._get_local_repository_dir(self._repository_id),
                etpConst['etpdatabasewebinstallupdates'])
            with open(something_new_webinstall, "w") as sn_f:
                sn_f.flush()
            data['~~something_new_web'] = something_new_webinstall
            critical.append(data['~~something_new_web'])

            # always push metafiles file, it's cheap
            data['metafiles_path'] = \
                self._entropy._get_local_repository_compressed_metafiles_file(
                    self._repository_id)
            critical.append(data['metafiles_path'])
            gpg_signed_files.append(data['metafiles_path'])

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

            data['compressed_database_path_light'] = os.path.join(
                self._entropy._get_local_repository_dir(self._repository_id),
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

            data['compressed_database_path_digest_light'] = os.path.join(
                self._entropy._get_local_repository_dir(self._repository_id),
                etpConst[cmethod[8]]
            )
            critical.append(data['compressed_database_path_digest_light'])
            gpg_signed_files.append(
                data['compressed_database_path_digest_light'])


        # SSL cert file, just for reference
        ssl_ca_cert = self._entropy._get_local_repository_ca_cert_file(
            self._repository_id)
        if os.path.isfile(ssl_ca_cert):
            if download:
                data['ssl_ca_cert_file'] = ssl_ca_cert
            extra_text_files.append(ssl_ca_cert)

        ssl_server_cert = self._entropy._get_local_repository_server_cert_file(
            self._repository_id)
        if os.path.isfile(ssl_server_cert):
            if download:
                data['ssl_server_cert_file'] = ssl_server_cert
            extra_text_files.append(ssl_server_cert)

        # Some information regarding how packages are built
        spm_files_map = self._entropy.Spm_class().config_files_map()
        spm_syms = {}
        for myname, myfile in spm_files_map.items():
            if os.path.islink(myfile):
                spm_syms[myname] = myfile
                continue # we don't want symlinks
            if os.path.isfile(myfile) and os.access(myfile, os.R_OK):
                if download:
                    data[myname] = myfile
                extra_text_files.append(myfile)

        # NOTE: for symlinks, we read their link and send a file with that
        # content. This is the default behaviour for now and allows to send
        # /etc/make.profile link pointer correctly.
        tmp_dirs = []
        for symname, symfile in spm_syms.items():

            mytmpdir = tempfile.mkdtemp(dir = etpConst['entropyunpackdir'])
            tmp_dirs.append(mytmpdir)
            mytmpfile = os.path.join(mytmpdir, os.path.basename(symfile))
            mylink = os.readlink(symfile)
            f_mkp = open(mytmpfile, "w")
            f_mkp.write(mylink)
            f_mkp.flush()
            f_mkp.close()

            if download:
                data[symname] = mytmpfile
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
        try:

            mytmpdir = tempfile.mkdtemp(prefix = "entropy.server")

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

            # download
            downloader = self._mirrors.TransceiverServerHandler(
                self._entropy, [uri],
                [download_data[x] for x in download_data],
                download = True, local_basedir = mytmpdir,
                critical_files = critical, repo = self._repository_id)
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
                return False

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

            self._mirrors.lock_mirrors(self._repository_id, False,
                mirrors = [uri])

        finally:
            # remove temporary directories
            for tmp_dir in tmp_dirs:
                try:
                    shutil.rmtree(tmp_dir, True)
                except shutil.Error:
                    continue

        return True

    def _update_rss_feed(self):

        product = self._settings['repositories']['product']
        rss_path = self._entropy._get_local_repository_rss_file(
            self._repository_id)
        rss_light_path = self._entropy._get_local_repository_rsslight_file(
            self._repository_id)
        rss_dump_name = self._repository_id + etpConst['rss-dump-name']
        db_revision_path = self._entropy._get_local_repository_revision_file(
            self._repository_id)

        rss_title = "%s Online Repository Status" % (
            self._settings['system']['name'],)
        rss_description = \
            "Keep you updated on what's going on in the %s Repository." % (
                self._settings['system']['name'],)

        plg_id = self._entropy.SYSTEM_SETTINGS_PLG_ID
        srv_set = self._settings[plg_id]['server']

        rss_main = RSS(rss_path, rss_title, rss_description,
            maxentries = srv_set['rss']['max_entries'])
        # load dump
        db_actions = self._cacher.pop(rss_dump_name,
            cache_dir = self._entropy.CACHE_DIR)
        if db_actions:
            if os.path.isfile(db_revision_path) and \
                os.access(db_revision_path, os.R_OK):
                with open(db_revision_path, "r") as f_rev:
                    revision = f_rev.readline().strip()
            else:
                revision = "N/A"

            commitmessage = ''
            if ServerRssMetadata()['commitmessage']:
                commitmessage = ' :: ' + \
                    ServerRssMetadata()['commitmessage']

            title = ": " + self._settings['system']['name'] + " " + \
                product[0].upper() + product[1:] + " " + \
                self._settings['repositories']['branch'] + \
                " :: Revision: " + revision + commitmessage

            link = srv_set['rss']['base_url']
            # create description
            added_items = db_actions.get("added")

            if added_items:
                for atom in sorted(added_items):
                    mylink = link + "?search=" + atom.split("~")[0] + \
                        "&arch=" + etpConst['currentarch'] + "&product="+product
                    description = atom + ": " + added_items[atom]['description']
                    rss_main.add_item(title = "Added/Updated" + title,
                        link = mylink, description = description)
            removed_items = db_actions.get("removed")

            if removed_items:
                for atom in sorted(removed_items):
                    description = atom + ": " + \
                        removed_items[atom]['description']
                    rss_main.add_item(title = "Removed" + title, link = link,
                        description = description)

            light_items = db_actions.get('light')
            if light_items:
                rss_light = RSS(rss_light_path, rss_title, rss_description,
                    maxentries = srv_set['rss']['light_max_entries'])
                for atom in sorted(light_items):
                    mylink = link + "?search=" + atom.split("~")[0] + \
                        "&arch=" + etpConst['currentarch'] + "&product=" + \
                        product
                    description = light_items[atom]['description']
                    rss_light.add_item(title = "[" + revision + "] " + atom,
                        link = mylink, description = description)
                rss_light.write_changes()

        rss_main.write_changes()
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
        with open(ts_file, "w") as ts_f:
            ts_f.write(current_ts)
            ts_f.flush()

    def _create_repository_pkglist(self):
        """
        Create the repository packages list file.
        """
        pkglist_file = self._entropy._get_local_pkglist_file(
            self._repository_id)

        tmp_pkglist_file = pkglist_file + ".tmp"
        dbconn = self._entropy.open_server_repository(
            self._repository_id, just_reading = True, do_treeupdates = False)
        pkglist = dbconn.listAllDownloads(do_sort = True, full_path = True)

        with open(tmp_pkglist_file, "w") as pkg_f:
            for pkg in pkglist:
                pkg_f.write(pkg + "\n")
            pkg_f.flush()

        os.rename(tmp_pkglist_file, pkglist_file)

    def _rewrite_treeupdates(self, entropy_repository):
        """
        Rewrite (and sync) packages category and name update metadata
        reading across all the available repositories and writing to the
        one being worked out.
        """
        # grab treeupdates from other databases and inject
        plg_id = self._entropy.SYSTEM_SETTINGS_PLG_ID
        srv_set = self._settings[plg_id]['server']
        server_repos = list(srv_set['repositories'].keys())

        all_actions = set()
        for myrepo in server_repos:

            # avoid __default__
            if myrepo == etpConst['clientserverrepoid']:
                continue

            mydbc = self._entropy.open_server_repository(myrepo,
                just_reading = True)
            actions = mydbc.listAllTreeUpdatesActions(no_ids_repos = True)
            for data in actions:
                all_actions.add(data)
            if not actions:
                continue

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
        f_ck = open(checksum_path, "w")
        mystring = "%s  %s\n" % (mydigest, os.path.basename(file_path),)
        f_ck.write(mystring)
        f_ck.flush()
        f_ck.close()

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
            if os.path.isfile(item_path) and os.access(item_path, os.R_OK):
                gpg_item_id = item_id + "_gpg_sign_part"
                if gpg_item_id in upload_data:
                    raise KeyError("wtf!")
                sign_path = repo_sec.sign_file(self._repository_id, item_path)
                gpg_upload_data[gpg_item_id] = sign_path
        upload_data.update(gpg_upload_data)

    def _create_metafiles_file(self, compressed_dest_path, file_list):

        found_file_list = [x for x in file_list if os.path.isfile(x) and \
            os.path.isfile(x) and os.access(x, os.R_OK)]

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
        with open(metafile_not_found_file, "w") as f_meta:
            f_meta.writelines(not_found_file_list)
            f_meta.flush()
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
        if srv_set['rss']['enabled']:
            self._update_rss_feed()

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
        self._entropy._update_package_sets(self._repository_id, dbconn)
        # Package Sets info
        self._show_package_sets_messages()

        dbconn.commit()
        # now we can safely copy it

        # backup current database to avoid re-indexing
        old_dbpath = self._entropy._get_local_repository_file(self._repository_id)
        backup_dbpath = old_dbpath + ".up_backup"
        try:
            if os.access(backup_dbpath, os.R_OK) and \
                os.path.isfile(backup_dbpath):
                os.remove(backup_dbpath)

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

        for uri in uris:

            crippled_uri = EntropyTransceiver.get_uri_name(uri)

            # EAPI 3
            if 3 not in disabled_eapis:
                self._show_eapi3_upload_messages(crippled_uri, database_path)

            uploader = self._mirrors.TransceiverServerHandler(
                self._entropy, [uri],
                [upload_data[x] for x in sorted(upload_data)],
                critical_files = critical,
                repo = self._repository_id
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

        if copy_back and os.path.isfile(backup_dbpath):
            # copy db back
            self._entropy.close_repositories()
            further_backup_dbpath = old_dbpath+".security_backup"
            if os.path.isfile(further_backup_dbpath):
                os.remove(further_backup_dbpath)
            shutil.copy2(old_dbpath, further_backup_dbpath)
            shutil.move(backup_dbpath, old_dbpath)

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

                if os.access(mylock_file, os.W_OK) and \
                    os.path.isfile(mylock_file):
                    os.remove(mylock_file)
                    continue

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

        if download_latest:
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
                    header = darkred(" !!! ")
                )
                return 1, set(), set([download_uri])

        if upload_queue and self._force:

            # Some internal QA checks, make sure everything is fine
            # on the repo
            plg_id = self._entropy.SYSTEM_SETTINGS_PLG_ID
            srv_set = self._settings[plg_id]['server']
            qa_sets = self._settings[plg_id]['qa_sets']
            base_repo = srv_set['base_repository_id']
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
                    return 5, set(), set()

            base_deps_not_found = set()
            if base_repo != self._repository_id:
                base_deps_not_found = self._entropy.dependencies_test(base_repo)

            # missing dependencies QA test
            deps_not_found = self._entropy.dependencies_test(
                self._repository_id)
            if (deps_not_found or base_deps_not_found) \
                and not self._entropy.community_repo:

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
                return 3, set(), set()

            # scan and report package changes
            _ignore_added, to_be_removed, _ignore_injected = \
                self._entropy.scan_package_changes()
            if to_be_removed:
                key_sorter = lambda x: \
                    self._entropy.open_repository(x[1]).retrieveAtom(x[0])
                rm_sorted_matches = sorted(to_be_removed, key = key_sorter)
                self._entropy.output(
                    "[%s] %s:" % (
                        red(_("sync")),
                        red(_("these packages haven't been removed yet")),
                    ),
                    importance = 1,
                    level = "warning",
                    header = darkred(" !!! ")
                )
                for rm_pkg_id, rm_repo_id in rm_sorted_matches:
                    rm_atom = self._entropy.open_repository(
                        rm_repo_id).retrieveAtom(rm_pkg_id)
                    self._entropy.output(
                        "[%s] %s" % (
                            brown(rm_repo_id),
                            purple(rm_atom),
                        ),
                        importance = 1,
                        level = "warning",
                        header = teal("   !! ")
                    )

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
                blue(_("repository sync completed successfully")),
            ),
            importance = 1,
            level = "info",
            header = darkgreen(" * ")
        )

        return 0, set(), set()
