# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
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
from entropy.db import dbapi2, EntropyRepository
from entropy.cache import EntropyCacher
from entropy.misc import TimeScheduled
from entropy.const import etpConst, etpCache, const_setup_perms, \
    const_debug_write
from entropy.exceptions import RepositoryError, SystemDatabaseError, \
    ConnectionError
from entropy.output import blue, darkred, red, darkgreen, purple, brown, bold
import entropy.tools
from entropy.dump import dumpobj

class Repository:

    def __init__(self, EquoInstance, reponames = [], forceUpdate = False,
        noEquoCheck = False, fetchSecurity = True):

        self.LockScanner = None
        from entropy.client.interfaces import Client
        if not isinstance(EquoInstance, Client):
            mytxt = "A valid Entropy Client instance or subclass is needed"
            raise AttributeError(mytxt)

        self.supported_download_items = (
            "db", "dblight", "ck", "cklight", "compck",
            "lock", "dbdump", "dbdumplight", "dbdumplightck", "dbdumpck",
            "meta_file", "notice_board"
        )
        self.big_socket_timeout = 10
        self.Entropy = EquoInstance
        self.Cacher = EntropyCacher()
        self.dbapi2 = dbapi2
        self.reponames = reponames
        self.forceUpdate = forceUpdate
        self.syncErrors = False
        self.dbupdated = False
        self.newEquo = False
        self.fetchSecurity = fetchSecurity
        self.noEquoCheck = noEquoCheck
        self.alreadyUpdated = 0
        self.notAvailable = 0
        self.valid_eapis = [1, 2, 3]
        self.reset_dbformat_eapi(None)
        self.current_repository_got_locked = False
        self.updated_repos = set()

        avail_data = self.Entropy.SystemSettings['repositories']['available']
        # check self.Entropy.SystemSettings['repositories']['available']
        if not avail_data:
            mytxt = "No repositories specified in %s" % (
                etpConst['repositoriesconf'],)
            raise AttributeError(mytxt)

        if not self.reponames:
            self.reponames.extend(list(avail_data.keys()))

    def __del__(self):
        if self.LockScanner != None:
            self.LockScanner.kill()

    def get_eapi3_connection(self, repository):
        # get database url
        avail_data = self.Entropy.SystemSettings['repositories']['available']
        dburl = avail_data[repository].get('service_uri')
        if dburl is None:
            return None

        port = avail_data[repository]['service_port']
        try:
            from entropy.services.ugc.interfaces import Client
            from entropy.client.services.ugc.commands import Client as \
                CommandsClient
            eapi3_socket = Client(self.Entropy, CommandsClient,
                output_header = "\t", socket_timeout = self.big_socket_timeout)
            eapi3_socket.connect(dburl, port)
            return eapi3_socket
        except (ConnectionError, socket.error,):
            return None

    def check_eapi3_availability(self, repository):
        conn = self.get_eapi3_connection(repository)
        if conn is None:
            return False
        try:
            conn.disconnect()
        except (socket.error, AttributeError,):
            return False
        return True

    def reset_dbformat_eapi(self, repository):

        self.dbformat_eapi = 2
        if repository != None:
            eapi_avail = self.check_eapi3_availability(repository)
            if eapi_avail:
                self.dbformat_eapi = 3

        # FIXME, find a way to do that without needing sqlite3 exec.
        if not os.access("/usr/bin/sqlite3", os.X_OK) or entropy.tools.islive():
            self.dbformat_eapi = 1
        else:
            rc = subprocess.call("/usr/bin/sqlite3 -version &> /dev/null",
                shell = True)
            if rc != 0: self.dbformat_eapi = 1

        eapi_env = os.getenv("FORCE_EAPI")
        if eapi_env != None:
            try:
                myeapi = int(eapi_env)
            except (ValueError, TypeError,):
                return
            if myeapi in self.valid_eapis:
                self.dbformat_eapi = myeapi


    def __validate_repository_id(self, repoid):
        if repoid not in self.reponames:
            mytxt = "Repository is not listed in self.reponames"
            raise AttributeError(mytxt)

    def __validate_compression_method(self, repo):

        self.__validate_repository_id(repo)

        repo_settings = self.Entropy.SystemSettings['repositories']
        dbc_format = repo_settings['available'][repo]['dbcformat']
        cmethod = etpConst['etpdatabasecompressclasses'].get(dbc_format)
        if cmethod is None:
            mytxt = "Wrong database compression method"
            raise AttributeError(mytxt)

        return cmethod

    def __ensure_repository_path(self, repo):

        self.__validate_repository_id(repo)

        avail_data = self.Entropy.SystemSettings['repositories']['available']
        repo_data = avail_data[repo]

        # create dir if it doesn't exist
        if not os.path.isdir(repo_data['dbpath']):
            os.makedirs(repo_data['dbpath'], 0o775)

        const_setup_perms(etpConst['etpdatabaseclientdir'],
            etpConst['entropygid'])

    def _construct_paths(self, item, repo, cmethod):

        if item not in self.supported_download_items:
            mytxt = "Supported items: %s" % (self.supported_download_items,)
            raise AttributeError(mytxt)

        items_needing_cmethod = (
            "db", "dblight", "cklight", "dbdump", "dbdumpck",
            "dbdumplight", "dbdumplightck", "compck",
        )
        if (item in items_needing_cmethod) and (cmethod is None):
                mytxt = "For %s, cmethod can't be None" % (item,)
                raise AttributeError(mytxt)

        avail_data = self.Entropy.SystemSettings['repositories']['available']
        repo_data = avail_data[repo]

        repo_db = repo_data['database']
        repo_dbpath = repo_data['dbpath']
        ec_hash = etpConst['etpdatabasehashfile']
        repo_lock_file = etpConst['etpdatabasedownloadlockfile']
        notice_board_filename = os.path.basename(repo_data['notice_board'])
        meta_file = etpConst['etpdatabasemetafilesfile']
        md5_ext = etpConst['packagesmd5fileext']
        ec_cm2 = None
        ec_cm3 = None
        ec_cm4 = None
        ec_cm5 = None
        ec_cm6 = None
        ec_cm7 = None
        ec_cm8 = None
        if cmethod != None:
            ec_cm2 = etpConst[cmethod[2]]
            ec_cm3 = etpConst[cmethod[3]]
            ec_cm4 = etpConst[cmethod[4]]
            ec_cm5 = etpConst[cmethod[5]]
            ec_cm6 = etpConst[cmethod[6]]
            ec_cm7 = etpConst[cmethod[7]]
            ec_cm8 = etpConst[cmethod[8]]

        mymap = {
            'db': ("%s/%s" % (repo_db, ec_cm2,), "%s/%s" % (repo_dbpath, ec_cm2,),),
            'dblight': ("%s/%s" % (repo_db, ec_cm7,), "%s/%s" % (repo_dbpath, ec_cm7,),),
            'dbdump': ("%s/%s" % (repo_db, ec_cm3,), "%s/%s" % (repo_dbpath, ec_cm3,),),
            'dbdumplight': ("%s/%s" % (repo_db, ec_cm5,), "%s/%s" % (repo_dbpath, ec_cm5,),),
            'ck': ("%s/%s" % (repo_db, ec_hash,), "%s/%s" % (repo_dbpath, ec_hash,),),
            'cklight': ("%s/%s" % (repo_db, ec_cm8,), "%s/%s" % (repo_dbpath, ec_cm8,),),
            'compck': ("%s/%s%s" % (repo_db, ec_cm2, md5_ext,), "%s/%s%s" % (repo_dbpath, ec_cm2, md5_ext,),),
            'dbdumpck': ("%s/%s" % (repo_db, ec_cm4,), "%s/%s" % (repo_dbpath, ec_cm4,),),
            'dbdumplightck': ("%s/%s" % (repo_db, ec_cm6,), "%s/%s" % (repo_dbpath, ec_cm6,),),
            'lock': ("%s/%s" % (repo_db, repo_lock_file,), "%s/%s" % (repo_dbpath, repo_lock_file,),),
            'notice_board': (repo_data['notice_board'], "%s/%s" % (repo_dbpath, notice_board_filename,),),
            'meta_file': ("%s/%s" % (repo_db, meta_file,), "%s/%s" % (repo_dbpath, meta_file,),),
        }

        return mymap.get(item)

    def __remove_repository_files(self, repo, cmethod):

        dbfilenameid = cmethod[2]
        dblightfilenameid = cmethod[7]
        self.__validate_repository_id(repo)
        repo_dbpath = self.Entropy.SystemSettings['repositories']['available'][repo]['dbpath']

        def remove_eapi1():

            if os.path.isfile(repo_dbpath+"/"+etpConst['etpdatabasehashfile']):
                os.remove(repo_dbpath+"/"+etpConst['etpdatabasehashfile'])
            if os.path.isfile(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile']):
                os.remove(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile'])

            if os.path.isfile(repo_dbpath + "/" + etpConst[dblightfilenameid]):
                os.remove(repo_dbpath + "/" + etpConst[dblightfilenameid])
            if os.path.isfile(repo_dbpath + "/" + etpConst[dblightfilenameid] + \
                    etpConst['packagesmd5fileext']):
                os.remove(repo_dbpath + "/" + etpConst[dblightfilenameid] + \
                    etpConst['packagesmd5fileext'])

            if os.path.isfile(repo_dbpath+"/"+etpConst[dbfilenameid]):
                os.remove(repo_dbpath+"/"+etpConst[dbfilenameid])
            if os.path.isfile(repo_dbpath + "/" + etpConst[dbfilenameid] + \
                    etpConst['packagesmd5fileext']):
                os.remove(repo_dbpath + "/" + etpConst[dbfilenameid] + \
                    etpConst['packagesmd5fileext'])

        if self.dbformat_eapi == 1:
            remove_eapi1()
        elif self.dbformat_eapi in (2, 3,):
            remove_eapi1()
            if os.path.isfile(repo_dbpath+"/"+cmethod[6]):
                os.remove(repo_dbpath+"/"+cmethod[6])
            if os.path.isfile(repo_dbpath+"/"+etpConst[cmethod[5]]):
                os.remove(repo_dbpath+"/"+etpConst[cmethod[5]])
            if os.path.isfile(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile']):
                os.remove(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile'])
        else:
            mytxt = "self.dbformat_eapi must be in (1,2,3,)"
            raise AttributeError(mytxt)

    def __unpack_downloaded_database(self, repo, cmethod):

        self.__validate_repository_id(repo)
        rc = 0
        path = None
        sys_set_repos = self.Entropy.SystemSettings['repositories']['available']
        repo_data = sys_set_repos[repo]
        myfile = repo_data['dbpath'] + "/" + etpConst[cmethod[7]]
        if self.dbformat_eapi == 2:
            myfile = repo_data['dbpath'] + "/" + etpConst[cmethod[5]]


        if self.dbformat_eapi in (1, 2,):
            try:

                myfunc = getattr(entropy.tools, cmethod[1])
                path = myfunc(myfile)
                # rename path correctly
                if self.dbformat_eapi == 1:
                    new_path = os.path.join(os.path.dirname(path),
                        etpConst['etpdatabasefile'])
                    os.rename(path, new_path)
                    path = new_path

            except (OSError, EOFError):
                rc = 1
            if os.path.isfile(myfile):
                os.remove(myfile)

        else:
            mytxt = "self.dbformat_eapi must be in (1,2)"
            raise AttributeError(mytxt)

        if rc == 0:
            self.Entropy.setup_default_file_perms(path)

        return rc

    def _verify_file_checksum(self, file_path, md5_checksum_path):
        ck_f = open(md5_checksum_path, "r")
        md5hash = ck_f.readline().strip()
        md5hash = md5hash.split()[0]
        ck_f.close()
        return entropy.tools.compare_md5(file_path, md5hash)

    def __verify_database_checksum(self, repo, cmethod = None):

        self.__validate_repository_id(repo)
        sys_settings_repos = self.Entropy.SystemSettings['repositories']
        avail_config = sys_settings_repos['available'][repo]

        sep = os.path.sep
        if self.dbformat_eapi == 1:
            dbfile = avail_config['dbpath'] + sep + etpConst[cmethod[7]]
            md5file = avail_config['dbpath'] + sep + etpConst[cmethod[8]]

        elif self.dbformat_eapi == 2:
            dbfile = avail_config['dbpath'] + sep + etpConst[cmethod[5]]
            md5file = avail_config['dbpath'] + sep + etpConst[cmethod[6]]

        else:
            mytxt = "self.dbformat_eapi must be in (1,2)"
            raise AttributeError(mytxt)

        if not (os.access(md5file, os.R_OK) and os.path.isfile(md5file)):
            return -1

        return self._verify_file_checksum(dbfile, md5file)

    # @returns -1 if the file is not available
    # @returns int>0 if the revision has been retrieved
    def get_online_repository_revision(self, repo):

        self.__validate_repository_id(repo)
        avail_data = self.Entropy.SystemSettings['repositories']['available']
        repo_data = avail_data[repo]

        url = repo_data['database'] + "/" + etpConst['etpdatabaserevisionfile']
        status = entropy.tools.get_remote_data(url,
            timeout = self.big_socket_timeout)
        if status:
            status = status[0].strip()
            try:
                status = int(status)
            except ValueError:
                status = -1
            return status
        else:
            return -1

    def get_online_eapi3_lock(self, repo):
        self.__validate_repository_id(repo)

        avail_data = self.Entropy.SystemSettings['repositories']['available']
        repo_data = avail_data[repo]

        url = repo_data['database'] + "/" + etpConst['etpdatabaseeapi3lockfile']
        data = entropy.tools.get_remote_data(url)
        if not data:
            return False
        return True

    def is_repository_eapi3_locked(self, repo):
        self.__validate_repository_id(repo)
        return self.get_online_eapi3_lock(repo)

    def is_repository_updatable(self, repo):

        self.__validate_repository_id(repo)

        onlinestatus = self.get_online_repository_revision(repo)
        if (onlinestatus != -1):
            localstatus = self.Entropy.get_repository_revision(repo)
            if (localstatus == onlinestatus) and (not self.forceUpdate):
                return False
        return True

    def is_repository_unlocked(self, repo):

        self.__validate_repository_id(repo)

        rc = self.download_item("lock", repo, disallow_redirect = True)
        if rc: # cannot download database
            self.syncErrors = True
            return False
        return True

    def clear_repository_cache(self, repo):
        self.__validate_repository_id(repo)
        self.Entropy.clear_dump_cache("%s/%s%s/" % (etpCache['dbMatch'],
            etpConst['dbnamerepoprefix'], repo,))
        self.Entropy.clear_dump_cache("%s/%s%s/" % (etpCache['dbSearch'],
            etpConst['dbnamerepoprefix'], repo,))

    def download_item(self, item, repo, cmethod = None, lock_status_func = None,
        disallow_redirect = True):

        self.__validate_repository_id(repo)
        url, filepath = self._construct_paths(item, repo, cmethod)

        # to avoid having permissions issues
        # it's better to remove the file before,
        # otherwise new permissions won't be written
        if os.path.isfile(filepath):
            os.remove(filepath)
        filepath_dir = os.path.dirname(filepath)
        if not os.path.isdir(filepath_dir) and not os.path.lexists(filepath_dir):
            os.makedirs(filepath_dir, 0o775)
            const_setup_perms(filepath_dir, etpConst['entropygid'])

        fetchConn = self.Entropy.urlFetcher(
            url,
            filepath,
            resume = False,
            abort_check_func = lock_status_func,
            disallow_redirect = disallow_redirect
        )
        fetchConn.progress = self.Entropy.progress

        rc = fetchConn.download()
        del fetchConn
        if rc in ("-1", "-2", "-3", "-4"):
            return False
        self.Entropy.setup_default_file_perms(filepath)
        return True

    def check_downloaded_database(self, repo, cmethod):

        dbfilename = etpConst[cmethod[7]]
        if self.dbformat_eapi == 2:
            dbfilename = etpConst[cmethod[5]]
        # verify checksum
        mytxt = "%s %s %s" % (
            red(_("Checking downloaded database")),
            darkgreen(dbfilename),
            red("..."),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            back = True,
            type = "info",
            header = "\t"
        )
        db_status = self.__verify_database_checksum(repo, cmethod)
        if db_status == -1:
            mytxt = "%s. %s !" % (
                red(_("Cannot open digest")),
                red(_("Cannot verify database integrity")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )
        elif db_status:
            mytxt = "%s: %s" % (
                red(_("Downloaded database status")),
                bold(_("OK")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = "\t"
            )
        else:
            mytxt = "%s: %s" % (
                red(_("Downloaded database status")),
                darkred(_("ERROR")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = "\t"
            )
            mytxt = "%s. %s" % (
                red(_("An error occured while checking database integrity")),
                red(_("Giving up")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = "\t"
            )
            return 1
        return 0


    def show_repository_information(self, repo, count_info):

        avail_data = self.Entropy.SystemSettings['repositories']['available']
        repo_data = avail_data[repo]

        self.Entropy.updateProgress(
            bold("%s") % ( repo_data['description'] ),
            importance = 2,
            type = "info",
            count = count_info,
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database URL")),
            darkgreen(repo_data['database']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database local path")),
            darkgreen(repo_data['dbpath']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database EAPI")),
            darkgreen(str(self.dbformat_eapi)),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = blue("  # ")
        )

    def get_eapi3_local_database(self, repo):

        avail_data = self.Entropy.SystemSettings['repositories']['available']
        repo_data = avail_data[repo]

        dbfile = os.path.join(repo_data['dbpath'], etpConst['etpdatabasefile'])
        mydbconn = None
        try:
            mydbconn = self.Entropy.open_generic_database(dbfile,
                xcache = False, indexing_override = False)
            mydbconn.validateDatabase()
        except (
            self.Entropy.dbapi2.OperationalError,
            self.Entropy.dbapi2.IntegrityError,
            SystemDatabaseError,
            IOError,
            OSError,):
                mydbconn = None
        return mydbconn

    def get_eapi3_database_differences(self, eapi3_interface, repo, idpackages,
        session):

        product = self.Entropy.SystemSettings['repositories']['product']
        data = eapi3_interface.CmdInterface.differential_packages_comparison(
            session, idpackages, repo, etpConst['currentarch'], product
        )
        if isinstance(data, bool): # then it's probably == False
            return False, False, False
        elif not isinstance(data, dict):
            return None, None, None
        elif 'added' not in data or \
            'removed' not in data or \
            'checksum' not in data:
                return None, None, None
        return data['added'], data['removed'], data['checksum']

    def get_eapi3_repository_metadata(self, eapi3_interface, repo, session):
        product = self.Entropy.SystemSettings['repositories']['product']
        data = eapi3_interface.CmdInterface.get_repository_metadata(
            session, repo, etpConst['currentarch'], product
        )
        if not isinstance(data, dict):
            return {}
        return data

    def handle_eapi3_database_sync(self, repo, threshold = 1500,
        chunk_size = 12):

        def prepare_exit(mysock, session = None):
            try:
                if session != None:
                    mysock.close_session(session)
                mysock.disconnect()
            except (socket.error,):
                pass

        eapi3_interface = self.get_eapi3_connection(repo)
        if eapi3_interface is None:
            return False

        session = eapi3_interface.open_session()

        # AttributeError because mydbconn can be is None
        try:
            mydbconn = self.get_eapi3_local_database(repo)
            myidpackages = mydbconn.listAllIdpackages()
        except (self.dbapi2.DatabaseError, self.dbapi2.IntegrityError,
            self.dbapi2.OperationalError, AttributeError,):

            prepare_exit(eapi3_interface, session)
            return False

        added_ids, removed_ids, checksum = self.get_eapi3_database_differences(
            eapi3_interface, repo,
            myidpackages, session
        )
        if (None in (added_ids, removed_ids, checksum)) or \
            (not added_ids and not removed_ids and self.forceUpdate):
                mydbconn.closeDB()
                prepare_exit(eapi3_interface, session)
                return False

        elif not checksum: # {added_ids, removed_ids, checksum} == False
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            mytxt = "%s: %s" % ( blue(_("EAPI3 Service status")),
                darkred(_("remote database suddenly locked")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
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
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = blue("  # "),
            )
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
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
        product = self.Entropy.SystemSettings['repositories']['product']
        for segment in added_segments:

            count += 1
            mytxt = "%s %s" % (blue(_("Fetching segments")), "...",)
            self.Entropy.updateProgress(
                mytxt, importance = 0, type = "info",
                header = "\t", back = True, count = (count, maxcount,)
            )
            fetch_count = 0
            max_fetch_count = 5

            while True:

                # anti loop protection
                if fetch_count > max_fetch_count:
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return False

                fetch_count += 1
                cmd_intf = eapi3_interface.CmdInterface
                pkgdata = cmd_intf.get_strict_package_information(
                    session, segment, repo, etpConst['currentarch'], product
                )
                if pkgdata is None:
                    mytxt = "%s: %s" % ( blue(_("Fetch error on segment")),
                        darkred(str(segment)),)
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "warning",
                        header = "\t", count = (count, maxcount,)
                    )
                    continue
                elif not pkgdata: # pkgdata == False
                    mytxt = "%s: %s" % (
                        blue(_("Service status")),
                        darkred("remote database suddenly locked"),
                    )
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "info",
                        header = "\t", count = (count, maxcount,)
                    )
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return None
                elif isinstance(pkgdata, tuple):
                    mytxt = "%s: %s, %s. %s" % (
                        blue(_("Service status")),
                        pkgdata[0], pkgdata[1],
                        darkred("Error processing the command"),
                    )
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "info",
                        header = "\t", count = (count, maxcount,)
                    )
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return None

                try:
                    for idpackage in pkgdata:
                        dumpobj(
                            "%s%s" % (etpCache['eapi3_fetch'], idpackage,),
                            pkgdata[idpackage],
                            ignore_exceptions = False
                        )
                except (IOError, EOFError, OSError,) as e:
                    mytxt = "%s: %s: %s." % (
                        blue(_("Local status")),
                        darkred("Error storing data"),
                        e,
                    )
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "info",
                        header = "\t", count = (count, maxcount,)
                    )
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return None

                break

        del added_segments

        repo_metadata = self.get_eapi3_repository_metadata(eapi3_interface,
            repo, session)
        metadata_elements = ("sets", "treeupdates_actions",
            "treeupdates_digest", "library_idpackages",)
        for elem in metadata_elements:
            if elem not in repo_metadata:
                mydbconn.closeDB()
                prepare_exit(eapi3_interface, session)
                mytxt = "%s: %s" % (
                    blue(_("EAPI3 Service status")),
                    darkred(_("cannot fetch repository metadata")),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    type = "info",
                    header = blue("  # "),
                )
                return None

        # update treeupdates
        try:
            mydbconn.setRepositoryUpdatesDigest(repo,
                repo_metadata['treeupdates_digest'])
            mydbconn.bumpTreeUpdatesActions(
                repo_metadata['treeupdates_actions'])
        except (self.dbapi2.Error,):
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            mytxt = "%s: %s" % (
                blue(_("EAPI3 Service status")),
                darkred(_("cannot update treeupdates data")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = blue("  # "),
            )
            return None

        # update package sets
        try:
            mydbconn.clearPackageSets()
            mydbconn.insertPackageSets(repo_metadata['sets'])
        except (self.dbapi2.Error,):
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            mytxt = "%s: %s" % (
                blue(_("EAPI3 Service status")),
                darkred(_("cannot update package sets data")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = blue("  # "),
            )
            return None

        # I don't need you anymore
        # disconnect socket
        prepare_exit(eapi3_interface, session)

        # now that we have all stored, add
        count = 0
        maxcount = len(added_ids)
        for idpackage in added_ids:
            count += 1
            mydata = self.Cacher.pop("%s%s" % (
                etpCache['eapi3_fetch'], idpackage,))
            if mydata is None:
                mytxt = "%s: %s" % (
                    blue(_("Fetch error on segment while adding")),
                    darkred(str(segment)),
                )
                self.Entropy.updateProgress(
                    mytxt, importance = 1, type = "warning",
                    header = "\t", count = (count, maxcount,)
                )
                mydbconn.closeDB()
                return False

            mytxt = "%s %s" % (
                blue(_("Injecting package")),
                darkgreen(mydata['atom']),
            )
            self.Entropy.updateProgress(
                mytxt, importance = 0, type = "info",
                header = "\t", back = True, count = (count, maxcount,)
            )
            try:
                mydbconn.addPackage(
                    mydata, revision = mydata['revision'],
                    idpackage = idpackage, do_commit = False,
                    formatted_content = True
                )
            except (self.dbapi2.Error,):
                self.Entropy.updateProgress(
                    blue(_("repository error while adding packages")),
                    importance = 1, type = "warning",
                    header = "\t", count = (count, maxcount,)
                )
                mydbconn.closeDB()
                return False

        self.Entropy.updateProgress(
            blue(_("Packages injection complete")), importance = 0,
            type = "info", header = "\t",
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
            self.Entropy.updateProgress(
                mytxt, importance = 0, type = "info",
                header = "\t", back = True, count = (count, maxcount,)
            )
            try:
                mydbconn.removePackage(idpackage, do_cleanup = False,
                    do_commit = False)
            except (self.dbapi2.Error,):
                self.Entropy.updateProgress(
                    blue(_("repository error while removing packages")),
                    importance = 1, type = "warning",
                    header = "\t", count = (count, maxcount,)
                )
                mydbconn.closeDB()
                return False

        self.Entropy.updateProgress(
            blue(_("Packages removal complete")),
            importance = 0, type = "info",
            header = "\t",
        )

        mydbconn.commitChanges()
        mydbconn.clearCache()
        # now verify if both checksums match
        result = False
        mychecksum = mydbconn.checksum(do_order = True,
            strict = False, strings = True)
        if checksum == mychecksum:
            result = True
        else:
            self.Entropy.updateProgress(
                blue(_("Database checksum doesn't match remote.")),
                importance = 0, type = "info", header = "\t",
            )
            mytxt = "%s: %s" % (_('local'), mychecksum,)
            self.Entropy.updateProgress(
                mytxt, importance = 0,
                type = "info", header = "\t",
            )
            mytxt = "%s: %s" % (_('remote'), checksum,)
            self.Entropy.updateProgress(
                mytxt, importance = 0,
                type = "info", header = "\t",
            )

        mydbconn.closeDB()
        return result

    def _run_post_update_repository_hook(self, repoid):
        my_repos = self.Entropy.SystemSettings['repositories']
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

    def run_sync(self):

        self.dbupdated = False
        repocount = 0
        repolength = len(self.reponames)
        for repo in self.reponames:

            repocount += 1
            self.reset_dbformat_eapi(repo)
            self.show_repository_information(repo, (repocount, repolength))

            if not self.forceUpdate:
                updated = self.handle_repository_update(repo)
                if updated:
                    self.Entropy.cycleDone()
                    self.alreadyUpdated += 1
                    continue

            locked = self.handle_repository_lock(repo)
            if locked:
                self.notAvailable += 1
                self.Entropy.cycleDone()
                continue

            # clear database interface cache belonging to this repository
            self.clear_repository_cache(repo)
            self.__ensure_repository_path(repo)

            # dealing with EAPI
            # setting some vars
            do_skip = False
            skip_this_repo = False
            db_checksum_down_status = False
            do_db_update_transfer = False
            rc = 0

            my_repos = self.Entropy.SystemSettings['repositories']
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

                if self.dbformat_eapi < 3:

                    down_status = self.handle_database_download(repo, cmethod)
                    if not down_status:
                        self.Entropy.cycleDone()
                        self.notAvailable += 1
                        do_skip = True
                        skip_this_repo = True
                        continue
                    db_checksum_down_status = \
                        self.handle_database_checksum_download(repo, cmethod)
                    break

                elif self.dbformat_eapi == 3 and not \
                    (os.path.isfile(dbfile) and os.access(dbfile, os.W_OK)):

                    do_db_update_transfer = None
                    self.dbformat_eapi -= 1
                    continue

                elif self.dbformat_eapi == 3:

                    status = False
                    try:
                        status = self.handle_eapi3_database_sync(repo)
                    except socket.error as err:
                        mytxt = "%s: %s" % (
                            blue(_("EAPI3 Service error")),
                            darkred(repr(err)),
                        )
                        self.Entropy.updateProgress(
                            mytxt,
                            importance = 0,
                            type = "info",
                            header = blue("  # "),
                        )
                    except:
                        # avoid broken entries, deal with every exception
                        self.__remove_repository_files(repo, cmethod)
                        raise

                    if status is None: # remote db not available anymore ?
                        time.sleep(5)
                        locked = self.handle_repository_lock(repo)
                        if locked:
                            self.Entropy.cycleDone()
                            self.notAvailable += 1
                            do_skip = True
                            skip_this_repo = True
                        else: # ah, well... dunno then...
                            do_db_update_transfer = None
                            self.dbformat_eapi -= 1
                        continue
                    elif not status: # (status == False)
                        # set to none and completely skip database alignment
                        do_db_update_transfer = None
                        self.dbformat_eapi -= 1
                        continue

                    break

            if skip_this_repo:
                continue

            if self.dbformat_eapi in (1, 2,):

                # new policy, always deny repository if
                # its database checksum cannot be fetched
                if not db_checksum_down_status:
                    # delete all
                    self.__remove_repository_files(repo, cmethod)
                    self.syncErrors = True
                    self.Entropy.cycleDone()
                    continue

                rc = self.check_downloaded_database(repo, cmethod)
                if rc != 0:
                    # delete all
                    self.__remove_repository_files(repo, cmethod)
                    self.syncErrors = True
                    self.Entropy.cycleDone()
                    continue

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

                unpack_status = self.handle_downloaded_database_unpack(repo,
                    cmethod)

                if not unpack_status:
                    # delete all
                    self.__remove_repository_files(repo, cmethod)
                    self.syncErrors = True
                    self.Entropy.cycleDone()
                    continue

                # re-validate
                if not os.path.isfile(dbfile):
                    do_db_update_transfer = False

                elif os.path.isfile(dbfile) and not do_db_update_transfer and \
                    (self.dbformat_eapi != 1):
                    os.remove(dbfile)

                if self.dbformat_eapi == 2:
                    rc = self.do_eapi2_inject_downloaded_dump(dumpfile,
                        dbfile, cmethod)

                if do_db_update_transfer:
                    self.do_eapi1_eapi2_databases_alignment(dbfile, dbfile_old)

                if self.dbformat_eapi == 2:
                    # remove the dump
                    os.remove(dumpfile)

            if rc != 0:
                # delete all
                self.__remove_repository_files(repo, cmethod)
                self.syncErrors = True
                self.Entropy.cycleDone()
                if os.path.isfile(dbfile_old):
                    os.remove(dbfile_old)
                continue

            if os.path.isfile(dbfile) and os.access(dbfile, os.W_OK):
                try:
                    self.Entropy.setup_default_file_perms(dbfile)
                except OSError: # notification applet
                    pass

            # database is going to be updated
            self.dbupdated = True
            self.do_standard_items_download(repo)
            self.Entropy.update_repository_revision(repo)
            if self.Entropy.indexing:
                self.do_database_indexing(repo)
            def_repoid = my_repos['default_repository']
            if repo == def_repoid:
                try:
                    self.run_config_files_updates(repo)
                except Exception as e:
                    entropy.tools.print_traceback()
                    mytxt = "%s: %s" % (
                        blue(_("Configuration files update error, not critical, continuing")),
                        darkred(repr(e)),
                    )
                    self.Entropy.updateProgress(mytxt, importance = 0,
                        type = "info", header = blue("  # "),)

            # execute post update repo hook
            self._run_post_update_repository_hook(repo)

            self.updated_repos.add(repo)
            self.Entropy.cycleDone()

            # remove garbage
            if os.access(dbfile_old, os.R_OK) and os.path.isfile(dbfile_old):
                os.remove(dbfile_old)

        # keep them closed
        self.Entropy.close_all_repositories()
        self.Entropy.validate_repositories()
        self.Entropy.close_all_repositories()

        # clean caches, fetch security
        if self.dbupdated:
            self.Entropy.purge_cache(client_purge = False)
            if self.fetchSecurity:
                self.do_update_security_advisories()
            # do treeupdates
            if isinstance(self.Entropy.clientDbconn, EntropyRepository) and \
                entropy.tools.is_root(): # only as root due to Portage
                for repo in self.reponames:
                    try:
                        dbc = self.Entropy.open_repository(repo)
                    except RepositoryError:
                        # download failed and repo is not available, skip!
                        continue
                    self.Entropy.repository_packages_spm_sync(repo, dbc)
                self.Entropy.close_all_repositories()

        if self.syncErrors:
            self.Entropy.updateProgress(
                red(_("Something bad happened. Please have a look.")),
                importance = 1,
                type = "warning",
                header = darkred(" @@ ")
            )
            self.syncErrors = True
            self.Entropy.resources_remove_lock()
            return 128

        if not self.noEquoCheck:
            self.check_entropy_updates()

        return 0

    def run_config_files_updates(self, repo):

        # are we root?
        if etpConst['uid'] != 0:
            self.Entropy.updateProgress(
                brown(_("Skipping configuration files update, you are not root.")),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            return

        # make.conf
        self._config_updates_make_conf(repo)
        self._config_updates_make_profile(repo)


    def _config_updates_make_conf(self, repo):

        ## WARNING: it doesn't handle multi-line variables, yet. remember this.
        system_make_conf = etpConst['spm']['global_make_conf']

        avail_data = self.Entropy.SystemSettings['repositories']['available']
        repo_dbpath = avail_data[repo]['dbpath']
        repo_make_conf = os.path.join(repo_dbpath,
            os.path.basename(system_make_conf))

        if not (os.path.isfile(repo_make_conf) and \
            os.access(repo_make_conf, os.R_OK)):
            return

        make_conf_variables_check = ["CHOST"]

        if not os.path.isfile(system_make_conf):
            self.Entropy.updateProgress(
                "%s %s. %s." % (
                    red(system_make_conf),
                    blue(_("does not exist")), blue(_("Overwriting")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            if os.path.lexists(system_make_conf):
                shutil.move(
                    system_make_conf,
                    "%s.backup_%s" % (system_make_conf,
                        entropy.tools.get_random_number(),)
                )
            shutil.copy2(repo_make_conf, system_make_conf)

        elif os.access(system_make_conf, os.W_OK):

            repo_f = open(repo_make_conf, "r")
            sys_f = open(system_make_conf, "r")
            repo_make_c = [x.strip() for x in repo_f.readlines()]
            sys_make_c = [x.strip() for x in sys_f.readlines()]
            repo_f.close()
            sys_f.close()

            # read repository settings
            repo_data = {}
            for setting in make_conf_variables_check:
                for line in repo_make_c:
                    if line.startswith(setting+"="):
                        # there can't be bash vars with a space
                        # after its name on declaration
                        repo_data[setting] = line
                        # I don't break, because there might be
                        # other overlapping settings

            differences = {}
            # update make.conf data in memory
            for setting in repo_data:
                for idx in range(len(sys_make_c)):
                    line = sys_make_c[idx]

                    if line.startswith(setting+"=") and \
                        (line != repo_data[setting]):

                        # there can't be bash vars with a
                        # space after its name on declaration
                        self.Entropy.updateProgress(
                            "%s: %s %s. %s." % (
                                red(system_make_conf), bold(repr(setting)),
                                blue(_("variable differs")), red(_("Updating")),
                            ),
                            importance = 1,
                            type = "info",
                            header = blue(" @@ ")
                        )
                        differences[setting] = repo_data[setting]
                        line = repo_data[setting]
                    sys_make_c[idx] = line

            if differences:

                self.Entropy.updateProgress(
                    "%s: %s." % (
                        red(system_make_conf),
                        blue(_("updating critical variables")),
                    ),
                    importance = 1,
                    type = "info",
                    header = blue(" @@ ")
                )
                # backup user make.conf
                shutil.copy2(system_make_conf,
                    "%s.entropy_backup" % (system_make_conf,))

                self.Entropy.updateProgress(
                    "%s: %s." % (
                        red(system_make_conf),
                        darkgreen("writing changes to disk"),
                    ),
                    importance = 1,
                    type = "info",
                    header = blue(" @@ ")
                )
                # write to disk, safely
                tmp_make_conf = "%s.entropy_write" % (system_make_conf,)
                f = open(tmp_make_conf, "w")
                for line in sys_make_c: f.write(line+"\n")
                f.flush()
                f.close()
                shutil.move(tmp_make_conf, system_make_conf)

            # update environment
            for var in differences:
                try:
                    myval = '='.join(differences[var].strip().split("=")[1:])
                    if myval:
                        if myval[0] in ("'", '"',): myval = myval[1:]
                        if myval[-1] in ("'", '"',): myval = myval[:-1]
                except IndexError:
                    myval = ''
                os.environ[var] = myval

    def _config_updates_make_profile(self, repo):

        avail_data = self.Entropy.SystemSettings['repositories']['available']
        repo_dbpath = avail_data[repo]['dbpath']
        profile_link_name = etpConst['spm']['global_make_profile_link_name']

        repo_make_profile = os.path.join(repo_dbpath, profile_link_name)

        if not (os.path.isfile(repo_make_profile) and \
            os.access(repo_make_profile, os.R_OK)):
            return

        system_make_profile = etpConst['spm']['global_make_profile']

        f = open(repo_make_profile, "r")
        repo_profile_link_data = f.readline().strip()
        f.close()
        current_profile_link = ''
        if os.path.islink(system_make_profile) and \
            os.access(system_make_profile, os.R_OK):

            current_profile_link = os.readlink(system_make_profile)

        if (repo_profile_link_data != current_profile_link) and \
            repo_profile_link_data:

            self.Entropy.updateProgress(
                "%s: %s %s. %s." % (
                    red(system_make_profile), blue("link"),
                    blue(_("differs")), red(_("Updating")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            merge_sfx = ".entropy_merge"
            os.symlink(repo_profile_link_data, system_make_profile+merge_sfx)
            if entropy.tools.is_valid_path(system_make_profile+merge_sfx):
                os.rename(system_make_profile+merge_sfx, system_make_profile)
            else:
                # revert change, link does not exist yet
                self.Entropy.updateProgress(
                    "%s: %s %s. %s." % (
                        red(system_make_profile), blue("new link"),
                        blue(_("does not exist")), red(_("Reverting")),
                    ),
                    importance = 1,
                    type = "info",
                    header = blue(" @@ ")
                )
                os.remove(system_make_profile+merge_sfx)


    def check_entropy_updates(self):
        rc = False
        if not self.noEquoCheck:
            try:
                rc, pkg_match = self.Entropy.check_package_update(
                    "sys-apps/entropy", deep = True)
            except:
                pass
        if rc:
            self.newEquo = True
            mytxt = "%s: %s. %s." % (
                bold("Equo/Entropy"),
                blue(_("a new release is available")),
                darkred(_("Mind to install it before any other package")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = bold(" !!! ")
            )

    def handle_downloaded_database_unpack(self, repo, cmethod):

        file_to_unpack = etpConst['etpdatabasedump']
        if self.dbformat_eapi == 1:
            file_to_unpack = etpConst['etpdatabasefile']
        mytxt = "%s %s %s" % (red(_("Unpacking database to")),
            darkgreen(file_to_unpack), red("..."),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = "\t"
        )

        myrc = self.__unpack_downloaded_database(repo, cmethod)
        if myrc != 0:
            mytxt = "%s %s !" % (red(_("Cannot unpack compressed package")),
                red(_("Skipping repository")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )
            return False
        return True


    def handle_database_checksum_download(self, repo, cmethod):

        hashfile = etpConst[cmethod[8]]
        downitem = 'cklight'
        if self.dbformat_eapi == 2: # EAPI = 2
            hashfile = etpConst[cmethod[6]]
            downitem = 'dbdumplightck'

        mytxt = "%s %s %s" % (
            red(_("Downloading checksum")),
            darkgreen(hashfile),
            red("..."),
        )
        # download checksum
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = "\t"
        )

        db_down_status = self.download_item(downitem, repo, cmethod,
            disallow_redirect = True)
        if not db_down_status and (downitem != 'cklight'):
            # fallback to old method, deprecated
            db_down_status = self.download_item('cklight', repo, cmethod,
                disallow_redirect = True)

        if not db_down_status:
            mytxt = "%s %s !" % (
                red(_("Cannot fetch checksum")),
                red(_("Cannot verify database integrity")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )
        return db_down_status

    def load_background_repository_lock_check(self, repo):
        # kill previous
        self.current_repository_got_locked = False
        self.kill_previous_repository_lock_scanner()
        self.LockScanner = TimeScheduled(30, self.repository_lock_scanner, repo)
        self.LockScanner.start()

    def kill_previous_repository_lock_scanner(self):
        if self.LockScanner != None:
            self.LockScanner.kill()

    def repository_lock_scanner(self, repo):
        locked = self.handle_repository_lock(repo)
        if locked:
            self.current_repository_got_locked = True

    def repository_lock_scanner_status(self):
        # raise an exception if repo got suddenly locked
        if self.current_repository_got_locked:
            mytxt = "Current repository got suddenly locked. Download aborted."
            raise RepositoryError('RepositoryError %s' % (mytxt,))

    def handle_database_download(self, repo, cmethod):

        def show_repo_locked_message():
            mytxt = "%s: %s." % (
                bold(_("Attention")),
                red(_("remote database got suddenly locked")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )

        # starting to download
        mytxt = "%s ..." % (red(_("Downloading repository database")),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = "\t"
        )

        down_status = False
        if self.dbformat_eapi == 2:
            # start a check in background
            self.load_background_repository_lock_check(repo)
            down_status = self.download_item("dbdumplight", repo, cmethod,
                lock_status_func = self.repository_lock_scanner_status,
                disallow_redirect = True)
            if self.current_repository_got_locked:
                self.kill_previous_repository_lock_scanner()
                show_repo_locked_message()
                return False
        if not down_status: # fallback to old db
            # start a check in background
            self.load_background_repository_lock_check(repo)
            self.dbformat_eapi = 1
            down_status = self.download_item("dblight", repo, cmethod,
                lock_status_func = self.repository_lock_scanner_status,
                disallow_redirect = True)
            if self.current_repository_got_locked:
                self.kill_previous_repository_lock_scanner()
                show_repo_locked_message()
                return False

        if not down_status:
            mytxt = "%s: %s." % (bold(_("Attention")),
                red(_("database does not exist online")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )

        self.kill_previous_repository_lock_scanner()
        return down_status

    def handle_repository_update(self, repo):
        # check if database is already updated to the latest revision
        update = self.is_repository_updatable(repo)
        if not update:
            mytxt = "%s: %s." % (bold(_("Attention")),
                red(_("database is already up to date")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = "\t"
            )
            return True
        # also check for eapi3 lock
        if self.dbformat_eapi == 3:
            locked = self.is_repository_eapi3_locked(repo)
            if locked:
                mytxt = "%s: %s." % (bold(_("Attention")),
                    red(_("database will be ready soon")),)
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = "\t"
                )
                return True
        return False

    def handle_repository_lock(self, repo):
        # get database lock
        unlocked = self.is_repository_unlocked(repo)
        if not unlocked:
            mytxt = "%s: %s. %s." % (
                bold(_("Attention")),
                red(_("Repository is being updated")),
                red(_("Try again in a few minutes")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )
            return True
        return False

    def do_eapi1_eapi2_databases_alignment(self, dbfile, dbfile_old):

        dbconn = self.Entropy.open_generic_database(dbfile, xcache = False,
            indexing_override = False)
        old_dbconn = self.Entropy.open_generic_database(dbfile_old,
            xcache = False, indexing_override = False)
        upd_rc = 0
        try:
            upd_rc = old_dbconn.alignDatabases(dbconn, output_header = "\t")
        except (self.dbapi2.OperationalError, self.dbapi2.IntegrityError,
            self.dbapi2.DatabaseError,):
            pass
        old_dbconn.closeDB()
        dbconn.closeDB()
        if upd_rc > 0:
            # -1 means no changes, == force used
            # 0 means too much hassle
            os.rename(dbfile_old, dbfile)
        return upd_rc

    def do_eapi2_inject_downloaded_dump(self, dumpfile, dbfile, cmethod):

        # load the dump into database
        mytxt = "%s %s, %s %s" % (
            red(_("Injecting downloaded dump")),
            darkgreen(etpConst[cmethod[5]]),
            red(_("please wait")),
            red("..."),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = "\t"
        )
        dbconn = self.Entropy.open_generic_database(dbfile,
            xcache = False, indexing_override = False)
        rc = dbconn.doDatabaseImport(dumpfile, dbfile)
        dbconn.closeDB()
        return rc

    def do_update_security_advisories(self):
        # update Security Advisories
        try:
            securityConn = self.Entropy.Security()
            securityConn.fetch_advisories()
        except Exception as e:
            entropy.tools.print_traceback(f = self.Entropy.clientLog)
            mytxt = "%s: %s" % (red(_("Advisories fetch error")), e,)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = darkred(" @@ ")
            )

    def do_standard_items_download(self, repo):

        repos_data = self.Entropy.SystemSettings['repositories']
        repo_data = repos_data['available'][repo]
        notice_board = os.path.basename(repo_data['local_notice_board'])

        objects_to_unpack = ("meta_file",)

        download_items = [
            (
                "meta_file",
                etpConst['etpdatabasemetafilesfile'],
                False,
                "%s %s %s" % (
                    red(_("Downloading repository metafile")),
                    darkgreen(etpConst['etpdatabasemetafilesfile']),
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
            self.Entropy.updateProgress(
                txt,
                importance = 0,
                type = "info",
                header = "\t",
                back = True
            )

        def my_show_down_status(message, mytype):
            self.Entropy.updateProgress(
                message,
                importance = 0,
                type = mytype,
                header = "\t"
            )

        def my_show_file_unpack(fp):
            self.Entropy.updateProgress(
                "%s: %s" % (darkgreen(_("unpacked meta file")), brown(fp),),
                header = blue("\t  << ")
            )

        def my_show_file_rm(fp):
            self.Entropy.updateProgress(
                "%s: %s" % (darkgreen(_("removed meta file")), purple(fp),),
                header = blue("\t  << ")
            )

        for item, myfile, ignorable, mytxt in download_items:

            my_show_info(mytxt)
            mystatus = self.download_item(item, repo, disallow_redirect = True)
            mytype = 'info'

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
                continue

            myurl, mypath = self._construct_paths(item, repo, None)
            message = "%s: %s." % (blue(myfile),
                darkgreen(_("available, w00t!")))
            my_show_down_status(message, mytype)
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
                                    pass

                for myfile in sorted(myfiles_to_move):
                    from_mypath = os.path.join(tmpdir, myfile)
                    to_mypath = os.path.join(repo_dir, myfile)
                    try:
                        os.rename(from_mypath, to_mypath)
                        my_show_file_unpack(myfile)
                    except OSError:
                        continue

            finally:
                shutil.rmtree(tmpdir, True)


        mytxt = "%s: %s" % (
            red(_("Repository revision")),
            bold(str(self.Entropy.get_repository_revision(repo))),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = "\t"
        )

    def do_database_indexing(self, repo):

        # renice a bit, to avoid eating resources
        old_prio = self.Entropy.set_priority(15)
        mytxt = red("%s ...") % (_("Indexing Repository metadata"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = "\t",
            back = True
        )
        dbconn = self.Entropy.open_repository(repo)
        dbconn.createAllIndexes()
        dbconn.commitChanges(force = True)
        # get list of indexes
        repo_indexes = dbconn.listAllIndexes()
        if self.Entropy.clientDbconn != None:
            try: # client db can be absent
                client_indexes = self.Entropy.clientDbconn.listAllIndexes()
                if repo_indexes != client_indexes:
                    self.Entropy.clientDbconn.createAllIndexes()
            except:
                pass
        self.Entropy.set_priority(old_prio)

    def sync(self):

        # close them
        self.Entropy.close_all_repositories()

        # let's dance!
        mytxt = darkgreen("%s ...") % (_("Repositories synchronization"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = darkred(" @@ ")
        )

        gave_up = self.Entropy.lock_check(self.Entropy.resources_check_lock)
        if gave_up:
            return 3

        locked = self.Entropy.application_lock_check()
        if locked:
            return 4

        # lock
        acquired = self.Entropy.resources_create_lock()
        if not acquired:
            return 4 # app locked during lock acquire
        try:
            rc = self.run_sync()
        finally:
            self.Entropy.resources_remove_lock()
        if rc:
            return rc

        # remove lock
        self.Entropy.resources_remove_lock()

        if (self.notAvailable >= len(self.reponames)):
            return 2
        elif (self.notAvailable > 0):
            return 1

        return 0
