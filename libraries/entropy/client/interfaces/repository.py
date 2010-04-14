# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Repositories Management Interface}.

"""

import os
import sys
import time
import tempfile
import shutil
import subprocess
import socket

from entropy.i18n import _
from entropy.db import EntropyRepository
from entropy.cache import EntropyCacher
from entropy.misc import TimeScheduled
from entropy.const import etpConst, etpUi, const_setup_perms, \
    const_debug_write, const_set_nice_level
from entropy.exceptions import RepositoryError, SystemDatabaseError, \
    ConnectionError
from entropy.output import blue, darkred, red, darkgreen, purple, brown, bold
from entropy.dump import dumpobj
from entropy.security import Repository as RepositorySecurity
from entropy.db.exceptions import IntegrityError, OperationalError, Error, \
    DatabaseError
from entropy.core.settings.base import SystemSettings

import entropy.tools

class Repository:

    EAPI3_CACHE_ID = 'eapi3/segment_'

    def __init__(self, entropy_client_instance, repo_identifiers = None,
        force = False, entropy_updates_alert = True, fetch_security = True,
        gpg = True):

        if repo_identifiers is None:
            repo_identifiers = []

        self.__lock_scanner = None
        from entropy.client.interfaces import Client
        if not isinstance(entropy_client_instance, Client):
            mytxt = "A valid Entropy Client instance or subclass is needed"
            raise AttributeError(mytxt)

        self.supported_download_items = (
            "db", "dbck", "dblight", "ck", "cklight", "compck",
            "lock", "dbdump", "dbdumplight", "dbdumplightck", "dbdumpck",
            "meta_file", "meta_file_gpg", "notice_board"
        )
        self.__big_sock_timeout = 10
        self._entropy = entropy_client_instance
        self._cacher = EntropyCacher()
        self._settings = SystemSettings()
        self._last_revs = {}
        self.repo_ids = repo_identifiers
        self.force = force
        self.sync_errors = False
        self.updated = False
        self.new_entropy = False
        self.__current_repo_locked = False
        self.updated_repos = set()
        self.fetch_security = fetch_security
        self.entropy_updates_alert = entropy_updates_alert
        self.already_updated = 0
        self.not_available = 0
        self._valid_eapis = [1, 2, 3]
        self._gpg_feature = gpg
        self._repo_eapi = {}
        env_gpg = os.getenv('ETP_DISBLE_GPG')
        if env_gpg is not None:
            self._gpg_feature = False
        # Developer Repository mode enabled?
        sys_set = self._settings
        self._developer_repo = sys_set['repositories']['developer_repo']
        if self._developer_repo:
            const_debug_write(__name__, "__init__: developer repo mode enabled")

        avail_data = sys_set['repositories']['available']
        # check self._settings['repositories']['available']
        if not avail_data:
            mytxt = "No repositories specified in %s" % (
                etpConst['repositoriesconf'],)
            raise AttributeError(mytxt)

        if not self.repo_ids:
            self.repo_ids.extend(list(avail_data.keys()))
        self._setup_repo_eapi()

    def __del__(self):
        if self.__lock_scanner is not None:
            self.__lock_scanner.kill()

    def __get_eapi3_connection(self, repoid):
        # get database url
        avail_data = self._settings['repositories']['available']
        dburl = avail_data[repoid].get('service_uri')
        if dburl is None:
            return None

        port = avail_data[repoid]['service_port']
        try:
            from entropy.services.ugc.interfaces import Client
            from entropy.client.services.ugc.commands import Client as \
                CommandsClient
            eapi3_socket = Client(self._entropy, CommandsClient,
                output_header = "\t", socket_timeout = self.__big_sock_timeout)
            eapi3_socket.connect(dburl, port)
            return eapi3_socket
        except (ConnectionError, socket.error,):
            return None

    def __check_eapi3_availability(self, repoid):
        conn = self.__get_eapi3_connection(repoid)
        if conn is None:
            return False
        try:
            conn.disconnect()
        except (socket.error, AttributeError,):
            return False
        return True

    def _setup_repo_eapi(self):

        eapi_env = os.getenv("FORCE_EAPI")
        sqlite3_access = os.access("/usr/bin/sqlite3", os.X_OK)
        sqlite3_rc = subprocess.call("/usr/bin/sqlite3 -version &> /dev/null",
            shell = True)
        try:
            eapi_env_clear = int(eapi_env)
            if eapi_env_clear not in self._valid_eapis:
                raise ValueError()
        except (ValueError, TypeError,):
            eapi_env_clear = None

        for repoid in self.repo_ids:

            self._repo_eapi[repoid] = 2
            eapi_avail = self.__check_eapi3_availability(repoid)
            if eapi_avail:
                self._repo_eapi[repoid] = 3
            else:
                if not sqlite3_access or entropy.tools.islive():
                    self._repo_eapi[repoid] = 1
                elif sqlite3_rc != 0:
                    self._repo_eapi[repoid] = 1

            # check EAPI
            if eapi_env_clear is not None:
                self._repo_eapi[repoid] = eapi_env_clear

                # FORCE_EAPI is triggered, disable
                # developer_repo mode
                self._developer_repo = False
                const_debug_write(__name__,
                    "_setup_repo_eapi: developer repo mode disabled FORCE_EAPI")

            elif self._repo_eapi[repoid] > 1 and self._developer_repo:
                # enforce EAPI=1
                self._repo_eapi[repoid] = 1

    def __validate_repository_id(self, repoid):
        if repoid not in self.repo_ids:
            mytxt = "Repository is not listed in self.repo_ids"
            raise AttributeError(mytxt)

    def __validate_compression_method(self, repo):

        self.__validate_repository_id(repo)

        repo_settings = self._settings['repositories']
        dbc_format = repo_settings['available'][repo]['dbcformat']
        cmethod = etpConst['etpdatabasecompressclasses'].get(dbc_format)
        if cmethod is None:
            mytxt = "Wrong database compression method"
            raise AttributeError(mytxt)

        return cmethod

    def __ensure_repository_path(self, repo):

        self.__validate_repository_id(repo)

        avail_data = self._settings['repositories']['available']
        repo_data = avail_data[repo]

        # create dir if it doesn't exist
        if not os.path.isdir(repo_data['dbpath']):
            os.makedirs(repo_data['dbpath'], 0o775)

        const_setup_perms(etpConst['etpdatabaseclientdir'],
            etpConst['entropygid'])

    def _construct_paths(self, item, repo, cmethod, get_signature = False):

        if item not in self.supported_download_items:
            mytxt = "Supported items: %s" % (self.supported_download_items,)
            raise AttributeError(mytxt)

        items_needing_cmethod = (
            "db", "dbck", "dblight", "cklight", "dbdump", "dbdumpck",
            "dbdumplight", "dbdumplightck", "compck",
        )
        if (item in items_needing_cmethod) and (cmethod is None):
                mytxt = "For %s, cmethod can't be None" % (item,)
                raise AttributeError(mytxt)

        avail_data = self._settings['repositories']['available']
        repo_data = avail_data[repo]

        repo_db = repo_data['database']
        repo_dbpath = repo_data['dbpath']
        ec_hash = etpConst['etpdatabasehashfile']
        repo_lock_file = etpConst['etpdatabasedownloadlockfile']
        notice_board_filename = os.path.basename(repo_data['notice_board'])
        meta_file = etpConst['etpdatabasemetafilesfile']
        meta_file_gpg = etpConst['etpdatabasemetafilesfile'] + \
            etpConst['etpgpgextension']
        md5_ext = etpConst['packagesmd5fileext']
        ec_cm2 = None
        ec_cm3 = None
        ec_cm4 = None
        ec_cm5 = None
        ec_cm6 = None
        ec_cm7 = None
        ec_cm8 = None
        ec_cm9 = None
        if cmethod is not None:
            ec_cm2 = etpConst[cmethod[2]]
            ec_cm3 = etpConst[cmethod[3]]
            ec_cm4 = etpConst[cmethod[4]]
            ec_cm5 = etpConst[cmethod[5]]
            ec_cm6 = etpConst[cmethod[6]]
            ec_cm7 = etpConst[cmethod[7]]
            ec_cm8 = etpConst[cmethod[8]]
            ec_cm9 = etpConst[cmethod[9]]

        mymap = {
            'db': (
                "%s/%s" % (repo_db, ec_cm2,),
                "%s/%s" % (repo_dbpath, ec_cm2,),
            ),
            'dbck': (
                "%s/%s" % (repo_db, ec_cm9,),
                "%s/%s" % (repo_dbpath, ec_cm9,),
            ),
            'dblight': (
                "%s/%s" % (repo_db, ec_cm7,),
                "%s/%s" % (repo_dbpath, ec_cm7,),
            ),
            'dbdump': (
                "%s/%s" % (repo_db, ec_cm3,),
                "%s/%s" % (repo_dbpath, ec_cm3,),
            ),
            'dbdumplight': (
                "%s/%s" % (repo_db, ec_cm5,),
                "%s/%s" % (repo_dbpath, ec_cm5,),
            ),
            'ck': (
                "%s/%s" % (repo_db, ec_hash,),
                "%s/%s" % (repo_dbpath, ec_hash,),
            ),
            'cklight': (
                "%s/%s" % (repo_db, ec_cm8,),
                "%s/%s" % (repo_dbpath, ec_cm8,),
            ),
            'compck': (
                "%s/%s%s" % (repo_db, ec_cm2, md5_ext,),
                "%s/%s%s" % (repo_dbpath, ec_cm2, md5_ext,),
            ),
            'dbdumpck': (
                "%s/%s" % (repo_db, ec_cm4,),
                "%s/%s" % (repo_dbpath, ec_cm4,),
            ),
            'dbdumplightck': (
                "%s/%s" % (repo_db, ec_cm6,),
                "%s/%s" % (repo_dbpath, ec_cm6,),
            ),
            'lock': (
                "%s/%s" % (repo_db, repo_lock_file,),
                "%s/%s" % (repo_dbpath, repo_lock_file,),
            ),
            'notice_board': (
                repo_data['notice_board'],
                "%s/%s" % (repo_dbpath, notice_board_filename,),
            ),
            'meta_file': (
                "%s/%s" % (repo_db, meta_file,),
                "%s/%s" % (repo_dbpath, meta_file,),
            ),
            'meta_file_gpg': (
                "%s/%s" % (repo_db, meta_file_gpg,),
                "%s/%s" % (repo_dbpath, meta_file_gpg,),
            ),
        }

        url, path = mymap.get(item)
        if get_signature:
            url = self.__append_gpg_signature_to_path(url)
            path = self.__append_gpg_signature_to_path(path)

        return url, path

    def __remove_repository_files(self, repo):
        sys_set = self._settings
        repo_dbpath = sys_set['repositories']['available'][repo]['dbpath']
        shutil.rmtree(repo_dbpath, True)

    def __unpack_downloaded_database(self, down_item, repo, cmethod):

        self.__validate_repository_id(repo)
        rc = 0
        path = None
        sys_set_repos = self._settings['repositories']['available']
        repo_data = sys_set_repos[repo]

        garbage, myfile = self._construct_paths(down_item, repo, cmethod)

        if self._repo_eapi[repo] in (1, 2,):
            try:

                myfunc = getattr(entropy.tools, cmethod[1])
                path = myfunc(myfile)
                # rename path correctly
                if self._repo_eapi[repo] == 1:
                    new_path = os.path.join(os.path.dirname(path),
                        etpConst['etpdatabasefile'])
                    os.rename(path, new_path)
                    path = new_path

            except (OSError, EOFError):
                rc = 1

        else:
            mytxt = "invalid EAPI must be = 1 or 2"
            raise AttributeError(mytxt)

        if rc == 0:
            self._entropy.setup_file_permissions(path)

        return rc

    def __verify_file_checksum(self, file_path, md5_checksum_path):
        with open(md5_checksum_path, "r") as ck_f:
            md5hash = ck_f.readline().strip()
            md5hash = md5hash.split()[0]
        return entropy.tools.compare_md5(file_path, md5hash)

    def __verify_database_checksum(self, repo, cmethod = None):

        self.__validate_repository_id(repo)
        sys_settings_repos = self._settings['repositories']
        avail_config = sys_settings_repos['available'][repo]

        sep = os.path.sep
        if self._repo_eapi[repo] == 1:
            if self._developer_repo:
                remote_gb, dbfile = self._construct_paths('db', repo, cmethod)
                remote_gb, md5file = self._construct_paths('dbck', repo, cmethod)
            else:
                remote_gb, dbfile = self._construct_paths('dblight', repo, cmethod)
                remote_gb, md5file = self._construct_paths('cklight', repo, cmethod)

        elif self._repo_eapi[repo] == 2:
            remote_gb, dbfile = self._construct_paths('dbdumplight', repo, cmethod)
            remote_gb, md5file = self._construct_paths('dbdumplightck', repo, cmethod)

        else:
            mytxt = "EAPI must be = 1 or 2"
            raise AttributeError(mytxt)

        if not (os.access(md5file, os.R_OK) and os.path.isfile(md5file)):
            return -1

        return self.__verify_file_checksum(dbfile, md5file)

    def get_online_repository_revision(self, repo):

        self.__validate_repository_id(repo)

        if self._repo_eapi[repo] == 3:
            # ask UGC then
            eapi3_interface = self.__get_eapi3_connection(repo)
            if eapi3_interface is None:
                # EAPI3 not available now!
                self._repo_eapi[repo] -= 1
            else:
                session = eapi3_interface.open_session()
                repo_metadata = self.__get_eapi3_repository_metadata(
                    eapi3_interface, repo, session)
                self.__eapi3_close(eapi3_interface, session = session)
                repo_rev = repo_metadata.get('revision')
                if repo_rev is not None:
                    try:
                        repo_rev = int(repo_rev)
                    except (ValueError, TypeError):
                        repo_rev = None
                if repo_rev is None:
                    # cannot reliably detect revision in EAPI=3 world
                    # so we need to drop EAPI3 in favour of EAPI2
                    self._repo_eapi[repo] -= 1
                else:
                    self._last_revs[repo] = repo_rev
                    return repo_rev

        avail_data = self._settings['repositories']['available']
        repo_data = avail_data[repo]

        url = repo_data['database'] + "/" + etpConst['etpdatabaserevisionfile']
        status = entropy.tools.get_remote_data(url,
            timeout = self.__big_sock_timeout)
        if status:
            status = status[0].strip()
            try:
                status = int(status)
            except ValueError:
                status = -1
        else:
            status = -1

        self._last_revs[repo] = status
        return status


    def _is_repository_updatable(self, repo):

        self.__validate_repository_id(repo)

        onlinestatus = self.get_online_repository_revision(repo)
        if onlinestatus != -1:
            localstatus = self._entropy.get_repository_revision(repo)
            if (localstatus == onlinestatus) and (not self.force):
                return False
        return True

    def _is_repository_unlocked(self, repo):

        self.__validate_repository_id(repo)

        rc = self._download_item("lock", repo, disallow_redirect = True)
        if rc: # cannot download database
            self.sync_errors = True
            return False
        return True

    def __append_gpg_signature_to_path(self, path):
        return path + etpConst['etpgpgextension']

    def _download_item(self, item, repo, cmethod = None,
        lock_status_func = None, disallow_redirect = True,
        get_signature = False):

        self.__validate_repository_id(repo)
        url, filepath = self._construct_paths(item, repo, cmethod)

        if get_signature:
            url = self.__append_gpg_signature_to_path(url)
            filepath = self.__append_gpg_signature_to_path(filepath)

        # to avoid having permissions issues
        # it's better to remove the file before,
        # otherwise new permissions won't be written
        if os.path.isfile(filepath):
            os.remove(filepath)
        filepath_dir = os.path.dirname(filepath)
        if not os.path.isdir(filepath_dir) and not \
            os.path.lexists(filepath_dir):

            os.makedirs(filepath_dir, 0o775)
            const_setup_perms(filepath_dir, etpConst['entropygid'])

        fetchConn = self._entropy.urlFetcher(
            url,
            filepath,
            resume = False,
            abort_check_func = lock_status_func,
            disallow_redirect = disallow_redirect
        )

        rc = fetchConn.download()
        del fetchConn
        if rc in ("-1", "-2", "-3", "-4"):
            return False
        self._entropy.setup_file_permissions(filepath)
        return True

    def _check_downloaded_database(self, repo, cmethod):

        dbitem = 'dblight'
        if self._repo_eapi[repo] == 2:
            dbitem = 'dbdumplight'
        elif self._developer_repo:
            dbitem = 'db'
        garbage, dbfilename = self._construct_paths(dbitem, repo, cmethod)

        # verify checksum
        mytxt = "%s %s %s" % (
            red(_("Checking downloaded database")),
            darkgreen(os.path.basename(dbfilename)),
            red("..."),
        )
        self._entropy.output(
            mytxt,
            importance = 0,
            back = True,
            level = "info",
            header = "\t"
        )
        db_status = self.__verify_database_checksum(repo, cmethod)
        if db_status == -1:
            mytxt = "%s. %s !" % (
                red(_("Cannot open digest")),
                red(_("Cannot verify database integrity")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = "\t"
            )
        elif db_status:
            mytxt = "%s: %s" % (
                red(_("Downloaded database status")),
                bold(_("OK")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "info",
                header = "\t"
            )
        else:
            mytxt = "%s: %s" % (
                red(_("Downloaded database status")),
                darkred(_("ERROR")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "error",
                header = "\t"
            )
            mytxt = "%s. %s" % (
                red(_("An error occured while checking database integrity")),
                red(_("Giving up")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "error",
                header = "\t"
            )
            return 1
        return 0

    def _update_repository_revision(self, repo):
        cur_rev = self._entropy.get_repository_revision(repo)
        db_data = self._settings['repositories']['available'][repo]
        db_data['dbrevision'] = "0"
        if cur_rev != -1:
            db_data['dbrevision'] = str(cur_rev)

        # update repository revision file
        # self.get_online_repository_revision() output must be
        # written into packages.db.revision for consistency
        # otherwise EAPI3 sync when EAPI3 service is on a separate
        # server (and uses rsync) doesn't work at its best
        # self._last_revs
        downloaded_rev = self._last_revs.get(repo, -1) # must be always int
        rev_file = os.path.join(db_data['dbpath'],
            etpConst['etpdatabaserevisionfile'])
        with open(rev_file, "w") as rev_f:
            rev_f.write(str(downloaded_rev) + "\n")
            rev_f.flush()

    def _show_repository_information(self, repo, count_info):

        avail_data = self._settings['repositories']['available']
        repo_data = avail_data[repo]

        self._entropy.output(
            bold("%s") % ( repo_data['description'] ),
            importance = 2,
            level = "info",
            count = count_info,
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database URL")),
            darkgreen(repo_data['database']),)
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database local path")),
            darkgreen(repo_data['dbpath']),)
        self._entropy.output(
            mytxt,
            importance = 0,
            level = "info",
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database EAPI")),
            darkgreen(str(self._repo_eapi[repo])),)
        self._entropy.output(
            mytxt,
            importance = 0,
            level = "info",
            header = blue("  # ")
        )

    def __get_eapi3_local_database(self, repo):

        avail_data = self._settings['repositories']['available']
        repo_data = avail_data[repo]

        dbfile = os.path.join(repo_data['dbpath'], etpConst['etpdatabasefile'])
        mydbconn = None
        try:
            mydbconn = self._entropy.open_generic_repository(dbfile,
                xcache = False, indexing_override = False)
            mydbconn.validateDatabase()
        except (OperationalError, IntegrityError, SystemDatabaseError,
            IOError, OSError,):
                mydbconn = None
        return mydbconn

    def __get_eapi3_database_differences(self, eapi3_interface, repo, idpackages,
        session):

        product = self._settings['repositories']['product']
        data = eapi3_interface.CmdInterface.differential_packages_comparison(
            session, idpackages, repo, etpConst['currentarch'], product
        )
        if isinstance(data, bool): # then it's probably == False
            return False, False, False
        elif not isinstance(data, dict):
            return None, None, None
        elif 'added' not in data or \
            'removed' not in data or \
            'secure_checksum' not in data:
                return None, None, None
        return data['added'], data['removed'], data['secure_checksum']

    def __get_eapi3_repository_metadata(self, eapi3_interface, repo, session):
        product = self._settings['repositories']['product']
        data = eapi3_interface.CmdInterface.get_repository_metadata(
            session, repo, etpConst['currentarch'], product
        )
        if not isinstance(data, dict):
            return {}
        return data

    def __eapi3_close(self, eapi3_interface, session = None):
        try:
            if session is not None:
                eapi3_interface.close_session(session)
            eapi3_interface.disconnect()
        except (socket.error,):
            pass

    def _handle_eapi3_database_sync(self, repo, threshold = 600,
        chunk_size = 12):

        eapi3_interface = self.__get_eapi3_connection(repo)
        if eapi3_interface is None:
            return False

        session = eapi3_interface.open_session()

        try:
            mydbconn = self.__get_eapi3_local_database(repo)
            if mydbconn is None:
                raise AttributeError()
        except (DatabaseError, IntegrityError, OperationalError,
            AttributeError,):
            self.__eapi3_close(eapi3_interface, session)
            return False

        try:
            myidpackages = mydbconn.listAllIdpackages()
        except (DatabaseError, IntegrityError, OperationalError,):
            mydbconn.closeDB()
            self.__eapi3_close(eapi3_interface, session)
            return False

        added_ids, removed_ids, secure_checksum = \
            self.__get_eapi3_database_differences(eapi3_interface, repo,
                myidpackages, session)
        if (None in (added_ids, removed_ids, secure_checksum)) or \
            (not added_ids and not removed_ids and self.force):
                mydbconn.closeDB()
                self.__eapi3_close(eapi3_interface, session)
                return False

        elif not secure_checksum: # {added_ids, removed_ids, secure_checksum} == False
            mydbconn.closeDB()
            self.__eapi3_close(eapi3_interface, session)
            mytxt = "%s: %s" % ( blue(_("EAPI3 Service status")),
                darkred(_("remote database suddenly locked")),)
            self._entropy.output(
                mytxt,
                importance = 0,
                level = "info",
                header = blue("  # "),
            )
            return None

        # is it worth it?
        if len(added_ids) > threshold:
            mytxt = "%s: %s (%s: %s/%s)" % (
                blue(_("EAPI3 Service")),
                darkred(_("skipping differential sync")),
                brown(_("threshold")),
                blue(str(len(added_ids))),
                darkred(str(threshold)),
            )
            self._entropy.output(
                mytxt,
                importance = 0,
                level = "info",
                header = blue("  # "),
            )
            mydbconn.closeDB()
            self.__eapi3_close(eapi3_interface, session)
            return False

        count = 0
        added_segments = []
        mytmp = set()

        for idpackage in added_ids:
            count += 1
            mytmp.add(idpackage)
            if count % chunk_size == 0:
                added_segments.append(list(mytmp))
                mytmp.clear()
        if mytmp: added_segments.append(list(mytmp))
        del mytmp

        # fetch and store
        count = 0
        maxcount = len(added_segments)
        product = self._settings['repositories']['product']
        for segment in added_segments:

            count += 1
            mytxt = "%s %s" % (blue(_("Fetching segments")), "...",)
            self._entropy.output(
                mytxt, importance = 0, level = "info",
                header = "\t", back = True, count = (count, maxcount,)
            )
            fetch_count = 0
            max_fetch_count = 5

            while True:

                # anti loop protection
                if fetch_count > max_fetch_count:
                    mydbconn.closeDB()
                    self.__eapi3_close(eapi3_interface, session)
                    return False

                fetch_count += 1
                cmd_intf = eapi3_interface.CmdInterface
                pkgdata = cmd_intf.get_strict_package_information(
                    session, segment, repo, etpConst['currentarch'], product
                )
                if pkgdata is None:
                    mytxt = "%s: %s" % ( blue(_("Fetch error on segment")),
                        darkred(str(segment)),)
                    self._entropy.output(
                        mytxt, importance = 1, level = "warning",
                        header = "\t", count = (count, maxcount,)
                    )
                    continue
                elif not pkgdata: # pkgdata == False
                    mytxt = "%s: %s" % (
                        blue(_("Service status")),
                        darkred("remote database suddenly locked"),
                    )
                    self._entropy.output(
                        mytxt, importance = 1, level = "info",
                        header = "\t", count = (count, maxcount,)
                    )
                    mydbconn.closeDB()
                    self.__eapi3_close(eapi3_interface, session)
                    return None
                elif isinstance(pkgdata, tuple):
                    mytxt = "%s: %s, %s. %s" % (
                        blue(_("Service status")),
                        pkgdata[0], pkgdata[1],
                        darkred("Error processing the command"),
                    )
                    self._entropy.output(
                        mytxt, importance = 1, level = "info",
                        header = "\t", count = (count, maxcount,)
                    )
                    mydbconn.closeDB()
                    self.__eapi3_close(eapi3_interface, session)
                    return None

                try:
                    for idpackage in pkgdata:
                        dumpobj(
                            "%s%s" % (Repository.EAPI3_CACHE_ID, idpackage,),
                            pkgdata[idpackage],
                            ignore_exceptions = False
                        )
                except (IOError, EOFError, OSError,) as e:
                    mytxt = "%s: %s: %s." % (
                        blue(_("Local status")),
                        darkred("Error storing data"),
                        e,
                    )
                    self._entropy.output(
                        mytxt, importance = 1, level = "info",
                        header = "\t", count = (count, maxcount,)
                    )
                    mydbconn.closeDB()
                    self.__eapi3_close(eapi3_interface, session)
                    return None

                break

        del added_segments

        repo_metadata = self.__get_eapi3_repository_metadata(eapi3_interface,
            repo, session)
        metadata_elements = ("sets", "treeupdates_actions",
            "treeupdates_digest", "library_idpackages",)
        for elem in metadata_elements:
            if elem not in repo_metadata:
                mydbconn.closeDB()
                self.__eapi3_close(eapi3_interface, session)
                mytxt = "%s: %s" % (
                    blue(_("EAPI3 Service status")),
                    darkred(_("cannot fetch repository metadata")),
                )
                self._entropy.output(
                    mytxt,
                    importance = 0,
                    level = "info",
                    header = blue("  # "),
                )
                return None

        # update treeupdates
        try:
            mydbconn.setRepositoryUpdatesDigest(repo,
                repo_metadata['treeupdates_digest'])
            mydbconn.bumpTreeUpdatesActions(
                repo_metadata['treeupdates_actions'])
        except (Error,):
            mydbconn.closeDB()
            self.__eapi3_close(eapi3_interface, session)
            mytxt = "%s: %s" % (
                blue(_("EAPI3 Service status")),
                darkred(_("cannot update treeupdates data")),
            )
            self._entropy.output(
                mytxt,
                importance = 0,
                level = "info",
                header = blue("  # "),
            )
            return None

        # update package sets
        try:
            mydbconn.clearPackageSets()
            mydbconn.insertPackageSets(repo_metadata['sets'])
        except (Error,):
            mydbconn.closeDB()
            self.__eapi3_close(eapi3_interface, session)
            mytxt = "%s: %s" % (
                blue(_("EAPI3 Service status")),
                darkred(_("cannot update package sets data")),
            )
            self._entropy.output(
                mytxt,
                importance = 0,
                level = "info",
                header = blue("  # "),
            )
            return None

        # I don't need you anymore
        # disconnect socket
        self.__eapi3_close(eapi3_interface, session)

        # now that we have all stored, add
        count = 0
        maxcount = len(added_ids)
        for idpackage in added_ids:
            count += 1
            mydata = self._cacher.pop("%s%s" % (
                Repository.EAPI3_CACHE_ID, idpackage,))
            if mydata is None:
                mytxt = "%s: %s" % (
                    blue(_("Fetch error on segment while adding")),
                    darkred(str(segment)),
                )
                self._entropy.output(
                    mytxt, importance = 1, level = "warning",
                    header = "\t", count = (count, maxcount,)
                )
                mydbconn.closeDB()
                return False

            mytxt = "%s %s" % (
                blue(_("Injecting package")),
                darkgreen(mydata['atom']),
            )
            self._entropy.output(
                mytxt, importance = 0, level = "info",
                header = "\t", back = True, count = (count, maxcount,)
            )
            try:
                mydbconn.addPackage(
                    mydata, revision = mydata['revision'],
                    idpackage = idpackage, do_commit = False,
                    formatted_content = True
                )
            except (Error,) as err:
                if etpUi['debug']:
                    entropy.tools.print_traceback()
                self._entropy.output("%s: %s" % (
                    blue(_("repository error while adding packages")),
                    err,),
                    importance = 1, level = "warning",
                    header = "\t", count = (count, maxcount,)
                )
                mydbconn.closeDB()
                return False

        self._entropy.output(
            blue(_("Packages injection complete")), importance = 0,
            level = "info", header = "\t",
        )

        # now remove
        maxcount = len(removed_ids)
        count = 0
        # preload atoms names to improve speed during removePackage
        atoms_map = dict((x, mydbconn.retrieveAtom(x),) for x in removed_ids)
        for idpackage in removed_ids:
            myatom = atoms_map.get(idpackage)
            count += 1
            mytxt = "%s: %s" % (
                blue(_("Removing package")),
                darkred(str(myatom)),)
            self._entropy.output(
                mytxt, importance = 0, level = "info",
                header = "\t", back = True, count = (count, maxcount,)
            )
            try:
                mydbconn.removePackage(idpackage, do_cleanup = False,
                    do_commit = False)
            except (Error,):
                self._entropy.output(
                    blue(_("repository error while removing packages")),
                    importance = 1, level = "warning",
                    header = "\t", count = (count, maxcount,)
                )
                mydbconn.closeDB()
                return False

        self._entropy.output(
            blue(_("Packages removal complete")),
            importance = 0, level = "info",
            header = "\t",
        )

        mydbconn.commitChanges()
        mydbconn.clearCache()
        # now verify if both checksums match
        result = False
        mychecksum = mydbconn.checksum(do_order = True,
            strict = False, strings = True, include_signatures = True)
        if secure_checksum == mychecksum:
            result = True
        else:
            self._entropy.output(
                blue(_("Database checksum doesn't match remote.")),
                importance = 0, level = "info", header = "\t",
            )
            mytxt = "%s: %s" % (_('local'), mychecksum,)
            self._entropy.output(
                mytxt, importance = 0,
                level = "info", header = "\t",
            )
            mytxt = "%s: %s" % (_('remote'), secure_checksum,)
            self._entropy.output(
                mytxt, importance = 0,
                level = "info", header = "\t",
            )

        mydbconn.closeDB()
        return result

    def _run_post_update_repository_hook(self, repoid):
        my_repos = self._settings['repositories']
        branch = my_repos['branch']
        avail_data = my_repos['available']
        repo_data = avail_data[repoid]
        post_update_script = repo_data['post_repo_update_script']

        if not (os.path.isfile(post_update_script) and \
            os.access(post_update_script, os.R_OK)):
            # not found!
            const_debug_write(__name__,
                "_run_post_update_repository_hook: not found")
            return 0

        args = ["/bin/sh", post_update_script, repoid, 
            etpConst['systemroot'] + "/", branch]
        const_debug_write(__name__,
            "_run_post_update_repository_hook: run: %s" % (args,))
        proc = subprocess.Popen(args, stdin = sys.stdin,
            stdout = sys.stdout, stderr = sys.stderr)
        # it is possible to ignore errors because
        # if it's a critical thing, upstream dev just have to fix
        # the script and will be automagically re-run
        br_rc = proc.wait()
        const_debug_write(__name__,
            "_run_post_update_repository_hook: rc: %s" % (br_rc,))

        return br_rc

    def _install_gpg_key_if_available(self, repoid):

        my_repos = self._settings['repositories']
        avail_data = my_repos['available']
        repo_data = avail_data[repoid]
        gpg_path = repo_data['gpg_pubkey']

        if not (os.path.isfile(gpg_path) and os.access(gpg_path, os.R_OK)):
            return False # gpg key not available

        def do_warn_user(fingerprint):
            mytxt = purple(_("Make sure to verify the imported key and set an appropriate trust level"))
            self._entropy.output(
                mytxt + ":",
                level = "warning",
                header = "\t"
            )
            mytxt = brown("gpg --homedir '%s' --edit-key '%s'" % (
                etpConst['etpclientgpgdir'], fingerprint,)
            )
            self._entropy.output(
                "$ " + mytxt,
                level = "warning",
                header = "\t"
            )

        try:
            repo_sec = self._entropy.RepositorySecurity()
        except RepositorySecurity.GPGError:
            mytxt = "%s," % (
                purple(_("This repository suports GPG-signed packages")),
            )
            self._entropy.output(
                mytxt,
                level = "warning",
                header = "\t"
            )
            mytxt = purple(_("you may want to install GnuPG to take advantage of this feature"))
            self._entropy.output(
                mytxt,
                level = "warning",
                header = "\t"
            )
            return False # GPG not available

        pk_expired = False
        try:
            pk_avail = repo_sec.is_pubkey_available(repoid)
        except repo_sec.KeyExpired:
            pk_avail = False
            pk_expired = True

        if pk_avail:

            tmp_dir = tempfile.mkdtemp()
            repo_tmp_sec = self._entropy.RepositorySecurity(
                keystore_dir = tmp_dir)
            # try to install and get fingerprint
            try:
                downloaded_key_fp = repo_tmp_sec.install_key(repoid, gpg_path)
            except RepositorySecurity.GPGError:
                downloaded_key_fp = None

            fingerprint = repo_sec.get_key_metadata(repoid)['fingerprint']
            shutil.rmtree(tmp_dir, True)

            if downloaded_key_fp != fingerprint and \
                (downloaded_key_fp is not None):
                mytxt = "%s: %s !!!" % (
                    purple(_("GPG key changed for")),
                    bold(repoid),
                )
                self._entropy.output(
                    mytxt,
                    level = "warning",
                    header = "\t"
                )
                mytxt = "[%s => %s]" % (
                    darkgreen(fingerprint),
                    purple(downloaded_key_fp),
                )
                self._entropy.output(
                    mytxt,
                    level = "warning",
                    header = "\t"
                )
                do_warn_user(downloaded_key_fp)
            else:
                mytxt = "%s: %s" % (
                    purple(_("GPG key already installed for")),
                    bold(repoid),
                )
                self._entropy.output(
                    mytxt,
                    level = "info",
                    header = "\t"
                )
                do_warn_user(fingerprint)
                return True # already installed

        elif pk_expired:
            mytxt = "%s: %s" % (
                purple(_("GPG key EXPIRED for repository")),
                bold(repoid),
            )
            self._entropy.output(
                mytxt,
                level = "warning",
                header = "\t"
            )


        # actually install
        mytxt = "%s: %s" % (
            purple(_("Installing GPG key for repository")),
            brown(repoid),
        )
        self._entropy.output(
            mytxt,
            level = "info",
            header = "\t",
            back = True
        )
        try:
            fingerprint = repo_sec.install_key(repoid, gpg_path)
        except RepositorySecurity.GPGError as err:
            mytxt = "%s: %s" % (
                darkred(_("Error during GPG key installation")),
                err,
            )
            self._entropy.output(
                mytxt,
                level = "error",
                header = "\t"
            )
            return False

        mytxt = "%s: %s" % (
            purple(_("Successfully installed GPG key for repository")),
            brown(repoid),
        )
        self._entropy.output(
            mytxt,
            level = "info",
            header = "\t"
        )
        mytxt = "%s: %s" % (
            darkgreen(_("Fingerprint")),
            bold(fingerprint),
        )
        self._entropy.output(
            mytxt,
            level = "info",
            header = "\t"
        )
        do_warn_user(fingerprint)
        return True

    def _gpg_verify_downloaded_files(self, repo, downloaded_files):

        try:
            repo_sec = self._entropy.RepositorySecurity()
        except RepositorySecurity.GPGServiceNotAvailable:
            # wtf! it was available a while ago!
            return 0 # GPG not available

        gpg_sign_ext = etpConst['etpgpgextension']
        sign_files = [x for x in downloaded_files if x.endswith(gpg_sign_ext)]
        sign_files = [x for x in sign_files if os.path.isfile(x) and \
            os.access(x, os.R_OK)]

        to_be_verified = []

        for sign_path in sign_files:
            target_path = sign_path[:-len(gpg_sign_ext)]
            if os.path.isfile(target_path) and os.access(target_path, os.R_OK):
                to_be_verified.append((target_path, sign_path,))

        gpg_rc = 0

        for target_path, sign_path in to_be_verified:

            file_name = os.path.basename(target_path)

            mytxt = "%s: %s ..." % (
                darkgreen(_("Verifying GPG signature of")),
                brown(file_name),
            )
            self._entropy.output(
                mytxt,
                level = "info",
                header = blue("\t@@ "),
                back = True
            )

            is_valid, err_msg = repo_sec.verify_file(repo, target_path,
                sign_path)
            if is_valid:
                mytxt = "%s: %s" % (
                    darkgreen(_("Verified GPG signature of")),
                    brown(file_name),
                )
                self._entropy.output(
                    mytxt,
                    level = "info",
                    header = blue("\t@@ ")
                )
            else:
                mytxt = "%s: %s" % (
                    darkred(_("Error during GPG verification of")),
                    file_name,
                )
                self._entropy.output(
                    mytxt,
                    level = "error",
                    header = "\t%s " % (bold("!!!"),)
                )
                mytxt = "%s: %s" % (
                    purple(_("It could mean a potential security risk")),
                    err_msg,
                )
                self._entropy.output(
                    mytxt,
                    level = "error",
                    header = "\t%s " % (bold("!!!"),)
                )
                gpg_rc = 1

        return gpg_rc

    def _run_sync(self):

        self.updated = False
        repocount = 0
        repolength = len(self.repo_ids)
        for repo in self.repo_ids:

            repocount += 1
            self._show_repository_information(repo, (repocount, repolength))

            if not self.force:
                updated = self.__handle_repository_update(repo)
                if updated:
                    self.already_updated += 1
                    continue

            locked = self.__handle_repository_lock(repo)
            if locked:
                self.not_available += 1
                continue

            # clear database interface cache belonging to this repository
            self.__ensure_repository_path(repo)

            # dealing with EAPI
            # setting some vars
            do_skip = False
            skip_this_repo = False
            db_checksum_down_status = False
            do_db_update_transfer = False
            rc = 0

            my_repos = self._settings['repositories']
            avail_data = my_repos['available']
            repo_data = avail_data[repo]

            # some variables
            dumpfile = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabasedumplight'])
            dbfile = os.path.join(repo_data['dbpath'],
                etpConst['etpdatabasefile'])
            dbfile_old = dbfile+".sync"
            cmethod = self.__validate_compression_method(repo)

            while True:

                if do_skip:
                    break

                downloaded_db_item = None
                sig_down_status = False
                db_checksum_down_status = False
                if self._repo_eapi[repo] < 3:

                    down_status, sig_down_status, downloaded_db_item = \
                        self.__handle_database_download(repo, cmethod)
                    if not down_status:
                        self.not_available += 1
                        do_skip = True
                        skip_this_repo = True
                        continue
                    db_checksum_down_status = \
                        self.__handle_database_checksum_download(repo, cmethod)
                    break

                elif self._repo_eapi[repo] == 3 and not \
                    (os.path.isfile(dbfile) and os.access(dbfile, os.W_OK)):

                    do_db_update_transfer = None
                    self._repo_eapi[repo] -= 1
                    continue

                elif self._repo_eapi[repo] == 3:

                    status = False
                    try:
                        status = self._handle_eapi3_database_sync(repo)
                    except socket.error as err:
                        mytxt = "%s: %s" % (
                            blue(_("EAPI3 Service error")),
                            darkred(repr(err)),
                        )
                        self._entropy.output(
                            mytxt,
                            importance = 0,
                            level = "info",
                            header = blue("  # "),
                        )
                    except:
                        # avoid broken entries, deal with every exception
                        self.__remove_repository_files(repo)
                        raise

                    if status is None: # remote db not available anymore ?
                        time.sleep(5)
                        locked = self.__handle_repository_lock(repo)
                        if locked:
                            self.not_available += 1
                            do_skip = True
                            skip_this_repo = True
                        else: # ah, well... dunno then...
                            do_db_update_transfer = None
                            self._repo_eapi[repo] -= 1
                        continue
                    elif not status: # (status == False)
                        # set to none and completely skip database alignment
                        do_db_update_transfer = None
                        self._repo_eapi[repo] -= 1
                        continue

                    break

            if skip_this_repo:
                continue

            downloaded_files = self._standard_items_download(repo)
            # also add db file to downloaded item
            # and md5 check repository
            if downloaded_db_item is not None:

                durl, dpath = self._construct_paths(downloaded_db_item,
                    repo, cmethod)
                downloaded_files.append(dpath)
                if sig_down_status:
                    d_sig_path = self.__append_gpg_signature_to_path(dpath)
                    downloaded_files.append(d_sig_path)

                # 1. we're always in EAPI1 or 2 here
                # 2. new policy, always deny repository if
                #    its database checksum cannot be fetched
                if not db_checksum_down_status:
                    # delete all
                    self.__remove_repository_files(repo)
                    self.sync_errors = True
                    continue

                rc = self._check_downloaded_database(repo, cmethod)
                if rc != 0:
                    # delete all
                    self.__remove_repository_files(repo)
                    self.sync_errors = True
                    continue

            # GPG pubkey install hook
            if self._gpg_feature:
                gpg_available = self._install_gpg_key_if_available(repo)
                if gpg_available:
                    gpg_rc = self._gpg_verify_downloaded_files(repo,
                        downloaded_files)

            # Now we can unpack
            files_to_remove = []
            if self._repo_eapi[repo] in (1, 2,):

                # if do_db_update_transfer == False and not None
                if (do_db_update_transfer is not None) and not \
                    do_db_update_transfer:

                    if os.access(dbfile, os.R_OK | os.W_OK) and \
                        os.path.isfile(dbfile):
                        try:
                            os.rename(dbfile, dbfile_old)
                            do_db_update_transfer = True
                        except OSError:
                            do_db_update_transfer = False

                unpack_status, unpacked_item = \
                    self.__handle_downloaded_database_unpack(repo, cmethod)

                if not unpack_status:
                    # delete all
                    self.__remove_repository_files(repo)
                    self.sync_errors = True
                    continue

                unpack_url, unpack_path = self._construct_paths(unpacked_item,
                    repo, cmethod)
                files_to_remove.append(unpack_path)

                # re-validate
                if not os.path.isfile(dbfile):
                    do_db_update_transfer = False

                elif os.path.isfile(dbfile) and not do_db_update_transfer and \
                    (self._repo_eapi[repo] != 1):
                    os.remove(dbfile)

                if self._repo_eapi[repo] == 2:
                    rc = self.__eapi2_inject_downloaded_dump(dumpfile,
                        dbfile, cmethod)

                if do_db_update_transfer:
                    self.__eapi1_eapi2_databases_alignment(dbfile, dbfile_old)

                if self._repo_eapi[repo] == 2:
                    # remove the dump
                    files_to_remove.append(dumpfile)

            if rc != 0:
                # delete all
                self.__remove_repository_files(repo)
                self.sync_errors = True
                files_to_remove.append(dbfile_old)
                for path in files_to_remove:
                    try:
                        os.remove(path)
                    except OSError:
                        continue
                continue

            if os.path.isfile(dbfile) and os.access(dbfile, os.W_OK):
                self._entropy.setup_file_permissions(dbfile)

            # database has been updated
            self.updated = True

            # remove garbage left around
            for path in files_to_remove:
                try:
                    os.remove(path)
                except OSError:
                    continue

            self._update_repository_revision(repo)
            self._database_revdeps_setup(repo)
            if self._entropy.indexing:
                self._database_indexing(repo)

            try:
                spm_class = self._entropy.Spm_class()
                spm_class.entropy_client_post_repository_update_hook(
                    self._entropy, repo)
            except Exception as err:
                entropy.tools.print_traceback()
                mytxt = "%s: %s" % (
                    blue(_("Configuration files update error, not critical, continuing")),
                    err,
                )
                self._entropy.output(mytxt, importance = 0,
                    level = "info", header = blue("  # "),)

            # execute post update repo hook
            self._run_post_update_repository_hook(repo)

            self.updated_repos.add(repo)

            # remove garbage
            if os.access(dbfile_old, os.R_OK) and os.path.isfile(dbfile_old):
                os.remove(dbfile_old)

        # keep them closed
        self._entropy.close_repositories()
        self._entropy._validate_repositories()
        self._entropy.close_repositories()

        # clean caches, fetch security
        if self.updated:
            self._entropy.clear_cache()
            if self.fetch_security:
                self._update_security_advisories()
            # do treeupdates
            if isinstance(self._entropy.installed_repository(), EntropyRepository) and \
                entropy.tools.is_root(): # only as root due to Portage
                for repo in self.repo_ids:
                    try:
                        dbc = self._entropy.open_repository(repo)
                    except RepositoryError:
                        # download failed and repo is not available, skip!
                        continue
                    try:
                        self._entropy.repository_packages_spm_sync(repo, dbc)
                    except Error:
                        # EntropyRepository error, missing table?
                        continue
                self._entropy.close_repositories()

        if self.sync_errors:
            self._entropy.output(
                red(_("Something bad happened. Please have a look.")),
                importance = 1,
                level = "warning",
                header = darkred(" @@ ")
            )
            self.sync_errors = True
            return 128

        if self.entropy_updates_alert:
            self._check_entropy_updates()

        return 0

    def _check_entropy_updates(self):
        rc = False
        if self.entropy_updates_alert:
            try:
                rc, pkg_match = self._entropy.check_package_update(
                    "sys-apps/entropy", deep = True)
            except:
                pass
        if rc:
            self.new_entropy = True
            mytxt = "%s: %s. %s." % (
                bold("Entropy"),
                blue(_("a new release is available")),
                darkred(_("Mind to install it before any other package")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "info",
                header = bold(" !!! ")
            )

    def __handle_downloaded_database_unpack(self, repo, cmethod):

        file_to_unpack = etpConst['etpdatabasedump']
        if self._repo_eapi[repo] == 1:
            file_to_unpack = etpConst['etpdatabasefile']
        elif self._repo_eapi[repo] == 2:
            file_to_unpack = etpConst['etpdatabasedumplight']

        mytxt = "%s %s %s" % (red(_("Unpacking database to")),
            darkgreen(file_to_unpack), red("..."),)
        self._entropy.output(
            mytxt,
            importance = 0,
            level = "info",
            header = "\t"
        )

        myitem = 'dblight'
        if self._repo_eapi[repo] == 2:
            myitem = 'dbdumplight'
        elif self._developer_repo:
            myitem = 'db'

        myrc = self.__unpack_downloaded_database(myitem, repo, cmethod)
        if myrc != 0:
            mytxt = "%s %s !" % (red(_("Cannot unpack compressed package")),
                red(_("Skipping repository")),)
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = "\t"
            )
            return False, myitem
        return True, myitem


    def __handle_database_checksum_download(self, repo, cmethod):

        downitem = 'cklight'
        if self._developer_repo:
            downitem = 'dbck'
        if self._repo_eapi[repo] == 2: # EAPI = 2
            downitem = 'dbdumplightck'

        garbage_url, hashfile = self._construct_paths(downitem, repo, cmethod)
        mytxt = "%s %s %s" % (
            red(_("Downloading checksum")),
            darkgreen(os.path.basename(hashfile)),
            red("..."),
        )
        # download checksum
        self._entropy.output(
            mytxt,
            importance = 0,
            level = "info",
            header = "\t"
        )

        db_down_status = self._download_item(downitem, repo, cmethod,
            disallow_redirect = True)

        if not db_down_status and (downitem not in ('cklight', 'dbck',)):
            # fallback to old method
            retryitem = 'cklight'
            if self._developer_repo:
                retryitem = 'dbck'
            db_down_status = self._download_item(retryitem, repo, cmethod,
                disallow_redirect = True)

        if not db_down_status:
            mytxt = "%s %s !" % (
                red(_("Cannot fetch checksum")),
                red(_("Cannot verify database integrity")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = "\t"
            )
        return db_down_status

    def __load_background_repository_lock_check(self, repo):
        # kill previous
        self.__current_repo_locked = False
        self.__kill_previous___repository_lock_scanner()
        self.__lock_scanner = TimeScheduled(30, self.__repository_lock_scanner,
            repo)
        self.__lock_scanner.start()

    def __kill_previous___repository_lock_scanner(self):
        if self.__lock_scanner is not None:
            self.__lock_scanner.kill()

    def __repository_lock_scanner(self, repo):
        locked = self.__handle_repository_lock(repo)
        if locked:
            self.__current_repo_locked = True

    def __repository_lock_scanner_status(self):
        # raise an exception if repo got suddenly locked
        if self.__current_repo_locked:
            mytxt = "Current repository got suddenly locked. Download aborted."
            raise RepositoryError('RepositoryError %s' % (mytxt,))

    def __handle_database_download(self, repo, cmethod):

        def show_repo_locked_message():
            mytxt = "%s: %s." % (
                bold(_("Attention")),
                red(_("remote database got suddenly locked")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = "\t"
            )

        # starting to download
        mytxt = "%s ..." % (red(_("Downloading repository database")),)
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = "\t"
        )

        downloaded_item = None
        down_status = False
        sig_status = False
        if self._repo_eapi[repo] == 2:

            # start a check in background
            self.__load_background_repository_lock_check(repo)
            down_item = "dbdumplight"

            down_status = self._download_item(down_item, repo, cmethod,
                lock_status_func = self.__repository_lock_scanner_status,
                disallow_redirect = True)
            if down_status:
                # get GPG file if available
                sig_status = self._download_item(down_item, repo, cmethod,
                    lock_status_func = self.__repository_lock_scanner_status,
                    disallow_redirect = True, get_signature = True)

            downloaded_item = down_item
            if self.__current_repo_locked:
                self.__kill_previous___repository_lock_scanner()
                show_repo_locked_message()
                return False, sig_status, downloaded_item

        if not down_status: # fallback to old db

            # start a check in background
            self.__load_background_repository_lock_check(repo)
            self._repo_eapi[repo] = 1
            down_item = "dblight"
            if self._developer_repo:
                # if developer repo mode is enabled, fetch full-blown db
                down_item = "db"
                const_debug_write(__name__,
                    "__handle_database_download: developer repo mode enabled")

            down_status = self._download_item(down_item, repo, cmethod,
                lock_status_func = self.__repository_lock_scanner_status,
                disallow_redirect = True)
            if down_status:
                sig_status = self._download_item(down_item, repo, cmethod,
                    lock_status_func = self.__repository_lock_scanner_status,
                    disallow_redirect = True, get_signature = True)

            downloaded_item = down_item
            if self.__current_repo_locked:
                self.__kill_previous___repository_lock_scanner()
                show_repo_locked_message()
                return False, sig_status, downloaded_item

        if not down_status:
            mytxt = "%s: %s." % (bold(_("Attention")),
                red(_("database does not exist online")),)
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = "\t"
            )

        self.__kill_previous___repository_lock_scanner()
        return down_status, sig_status, downloaded_item

    def __handle_repository_update(self, repo):
        # check if database is already updated to the latest revision
        update = self._is_repository_updatable(repo)
        if not update:
            mytxt = "%s: %s." % (bold(_("Attention")),
                red(_("database is already up to date")),)
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "info",
                header = "\t"
            )
            return True
        return False

    def __handle_repository_lock(self, repo):
        # get database lock
        unlocked = self._is_repository_unlocked(repo)
        if not unlocked:
            mytxt = "%s: %s. %s." % (
                bold(_("Attention")),
                red(_("Repository is being updated")),
                red(_("Try again in a few minutes")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = "\t"
            )
            return True
        return False

    def __eapi1_eapi2_databases_alignment(self, dbfile, dbfile_old):

        dbconn = self._entropy.open_generic_repository(dbfile, xcache = False,
            indexing_override = False)
        old_dbconn = self._entropy.open_generic_repository(dbfile_old,
            xcache = False, indexing_override = False)
        upd_rc = 0
        try:
            upd_rc = old_dbconn.alignDatabases(dbconn, output_header = "\t")
        except (OperationalError, IntegrityError, DatabaseError,):
            pass
        old_dbconn.closeDB()
        dbconn.closeDB()
        if upd_rc > 0:
            # -1 means no changes, == force used
            # 0 means too much hassle
            os.rename(dbfile_old, dbfile)
        return upd_rc

    def __eapi2_inject_downloaded_dump(self, dumpfile, dbfile, cmethod):

        # load the dump into database
        mytxt = "%s %s, %s %s" % (
            red(_("Injecting downloaded dump")),
            darkgreen(etpConst['etpdatabasedumplight']),
            red(_("please wait")),
            red("..."),
        )
        self._entropy.output(
            mytxt,
            importance = 0,
            level = "info",
            header = "\t"
        )
        dbconn = self._entropy.open_generic_repository(dbfile,
            xcache = False, indexing_override = False)
        rc = dbconn.doDatabaseImport(dumpfile, dbfile)
        dbconn.closeDB()
        return rc

    def _update_security_advisories(self):
        # update Security Advisories
        try:
            security_intf = self._entropy.Security()
            security_intf.sync()
        except Exception as e:
            entropy.tools.print_traceback(f = self._entropy.clientLog)
            mytxt = "%s: %s" % (red(_("Advisories fetch error")), e,)
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = darkred(" @@ ")
            )

    def _standard_items_download(self, repo):

        repos_data = self._settings['repositories']
        repo_data = repos_data['available'][repo]
        notice_board = os.path.basename(repo_data['local_notice_board'])
        db_meta_file = etpConst['etpdatabasemetafilesfile']
        db_meta_file_gpg = etpConst['etpdatabasemetafilesfile'] + \
            etpConst['etpgpgextension']

        objects_to_unpack = ("meta_file",)

        download_items = [
            (
                "meta_file",
                db_meta_file,
                False,
                "%s %s %s" % (
                    red(_("Downloading repository metafile")),
                    darkgreen(db_meta_file),
                    red("..."),
                )
            ),
            (
                "meta_file_gpg",
                db_meta_file_gpg,
                True,
                "%s %s %s" % (
                    red(_("Downloading GPG signature of repository metafile")),
                    darkgreen(db_meta_file_gpg),
                    red("..."),
                )
            ),
            (
                "notice_board",
                notice_board,
                True,
                "%s %s %s" % (
                    red(_("Downloading Notice Board")),
                    darkgreen(notice_board),
                    red("..."),
                )
            ),
        ]

        def my_show_info(txt):
            self._entropy.output(
                txt,
                importance = 0,
                level = "info",
                header = "\t",
                back = True
            )

        def my_show_down_status(message, mytype):
            self._entropy.output(
                message,
                importance = 0,
                level = mytype,
                header = "\t"
            )

        def my_show_file_unpack(fp):
            self._entropy.output(
                "%s: %s" % (darkgreen(_("unpacked meta file")), brown(fp),),
                header = blue("\t  << ")
            )

        def my_show_file_rm(fp):
            self._entropy.output(
                "%s: %s" % (darkgreen(_("removed meta file")), purple(fp),),
                header = blue("\t  << ")
            )

        downloaded_files = []

        for item, myfile, ignorable, mytxt in download_items:

            my_show_info(mytxt)
            mystatus = self._download_item(item, repo, disallow_redirect = True)
            mytype = 'info'
            myurl, mypath = self._construct_paths(item, repo, None)

            # download failed, is it critical?
            if not mystatus:
                if ignorable:
                    message = "%s: %s." % (blue(myfile),
                        red(_("not available, it's ok")))
                else:
                    mytype = 'warning'
                    message = "%s: %s." % (blue(myfile),
                        darkred(_("not available, not very ok!")))
                my_show_down_status(message, mytype)

                # remove garbage
                if os.path.isfile(mypath):
                    try:
                        os.remove(mypath)
                    except OSError:
                        continue

                continue

            message = "%s: %s." % (blue(myfile),
                darkgreen(_("available, w00t!")))
            my_show_down_status(message, mytype)
            downloaded_files.append(mypath)

            if item not in objects_to_unpack:
                continue
            if not (os.path.isfile(mypath) and os.access(mypath, os.R_OK)):
                continue

            tmpdir = tempfile.mkdtemp()
            repo_dir = repo_data['dbpath']
            try:
                done = entropy.tools.universal_uncompress(mypath, tmpdir,
                    catch_empty = True)
                if not done:
                    mytype = 'warning'
                    message = "%s: %s." % (blue(myfile),
                        darkred(_("cannot be unpacked, not very ok!")))
                    my_show_down_status(message, mytype)
                    continue
                myfiles_to_move = set(os.listdir(tmpdir))

                # exclude files not available by default
                files_not_found_file = etpConst['etpdatabasemetafilesnotfound']
                if files_not_found_file in myfiles_to_move:
                    myfiles_to_move.remove(files_not_found_file)
                    fnf_path = os.path.join(tmpdir, files_not_found_file)

                    if os.path.isfile(fnf_path) and \
                        os.access(fnf_path, os.R_OK):
                        with open(fnf_path, "r") as f:
                            f_nf = [x.strip() for x in f.readlines()]

                        for myfile in f_nf:
                            myfile = os.path.basename(myfile) # avoid lamerz
                            myfpath = os.path.join(repo_dir, myfile)
                            if os.path.isfile(myfpath) and \
                                os.access(myfpath, os.W_OK):
                                try:
                                    os.remove(myfpath)
                                    my_show_file_rm(myfile)
                                except OSError:
                                    continue

                for myfile in sorted(myfiles_to_move):
                    from_mypath = os.path.join(tmpdir, myfile)
                    to_mypath = os.path.join(repo_dir, myfile)
                    try:
                        os.rename(from_mypath, to_mypath)
                        my_show_file_unpack(myfile)
                    except OSError:
                        # try non atomic way
                        try:
                            shutil.copy2(from_mypath, to_mypath)
                            my_show_file_unpack(myfile)
                            os.remove(from_mypath)
                        except (shutil.Error, IOError, OSError,):
                            continue
                        continue

            finally:
                shutil.rmtree(tmpdir, True)


        mytxt = "%s: %s" % (
            red(_("Repository revision")),
            bold(str(self._entropy.get_repository_revision(repo))),
        )
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = "\t"
        )

        return downloaded_files

    def _database_revdeps_setup(self, repo):
        dbconn = self._entropy.open_repository(repo)
        dbconn.generateReverseDependenciesMetadata(verbose = False)
        dbconn.commitChanges(force = True)

    def _database_indexing(self, repo):

        # renice a bit, to avoid eating resources
        old_prio = const_set_nice_level(15)
        mytxt = red("%s ...") % (_("Indexing Repository metadata"),)
        self._entropy.output(
            mytxt,
            importance = 1,
            level = "info",
            header = "\t"
        )
        dbconn = self._entropy.open_repository(repo)
        dbconn.createAllIndexes()
        dbconn.commitChanges(force = True)
        # get list of indexes
        repo_indexes = dbconn.listAllIndexes()
        if self._entropy.installed_repository() is not None:
            try: # client db can be absent
                client_indexes = self._entropy.installed_repository().listAllIndexes()
                if repo_indexes != client_indexes:
                    self._entropy.installed_repository().createAllIndexes()
            except:
                pass
        const_set_nice_level(old_prio)

    def sync(self):

        # close them
        self._entropy.close_repositories()

        # let's dance!
        mytxt = darkgreen("%s ...") % (_("Repositories synchronization"),)
        self._entropy.output(
            mytxt,
            importance = 2,
            level = "info",
            header = darkred(" @@ ")
        )

        gave_up = self._entropy.wait_resources()
        if gave_up:
            return 3

        locked = self._entropy.another_entropy_running()
        if locked:
            self._entropy.output(
                red(_("Another Entropy is currently running.")),
                importance = 1,
                level = "error",
                header = darkred(" @@ ")
            )
            return 4

        # lock
        acquired = self._entropy.lock_resources()
        if not acquired:
            return 4 # app locked during lock acquire
        try:
            rc = self._run_sync()
            if rc:
                return rc
        finally:
            self._entropy.unlock_resources()

        if (self.not_available >= len(self.repo_ids)):
            return 2
        elif (self.not_available > 0):
            return 1

        return 0
