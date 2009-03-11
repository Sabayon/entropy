# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''
from __future__ import with_statement
import os
import random
import subprocess
import time
import shutil
from entropy.core import Singleton
# print_info, print_error, print_warning for Python-based triggers
from entropy.output import TextInterface, brown, blue, bold, darkgreen, darkblue, red, purple, darkred, print_info, print_error, print_warning
from entropy.const import *
from entropy.exceptions import *
from entropy.i18n import _
from entropy.db import dbapi2, LocalRepository
from entropy.misc import TimeScheduled, Lifo

class Client(Singleton,TextInterface):

    def init_singleton(self, indexing = True, noclientdb = 0,
            xcache = True, user_xcache = False, repo_validation = True,
            load_ugc = True, url_fetcher = None,
            multiple_url_fetcher = None):

        self.__instance_destroyed = False
        # modules import
        import entropy.dump as dumpTools
        import entropy.tools as entropyTools
        self.dumpTools = dumpTools
        self.entropyTools = entropyTools

        self.atomMatchCacheKey = etpCache['atomMatch']
        self.dbapi2 = dbapi2 # export for third parties
        self.FileUpdates = None
        self.repoDbCache = {}
        self.securityCache = {}
        self.QACache = {}
        self.spmCache = {}
        self.repo_error_messages_cache = set()
        self.package_match_validator_cache = {}
        self.memoryDbInstances = {}
        self.validRepositories = []

        from entropy.misc import LogFile
        self.clientLog = LogFile(level = etpConst['equologlevel'],filename = etpConst['equologfile'], header = "[client]")

        # in this way, can be reimplemented (so you can override updateProgress)
        self.MultipleUrlFetcher = multiple_url_fetcher
        self.urlFetcher = url_fetcher
        if self.urlFetcher == None:
            from entropy.transceivers import urlFetcher
            self.urlFetcher = urlFetcher
        if self.MultipleUrlFetcher == None:
            from entropy.transceivers import MultipleUrlFetcher
            self.MultipleUrlFetcher = MultipleUrlFetcher

        # supporting external updateProgress stuff, you can point self.progress
        # to your progress bar and reimplement updateProgress
        self.progress = None

        self.clientDbconn = None
        self.safe_mode = 0
        self.indexing = indexing
        self.repo_validation = repo_validation
        self.noclientdb = False
        self.openclientdb = True
        if noclientdb in (False,0):
            self.noclientdb = False
        elif noclientdb in (True,1):
            self.noclientdb = True
        elif noclientdb == 2:
            self.noclientdb = True
            self.openclientdb = False
        self.xcache = xcache
        shell_xcache = os.getenv("ETP_NOCACHE")
        if shell_xcache:
            self.xcache = False
        from entropy.cache import EntropyCacher
        self.Cacher = EntropyCacher()

        do_validate_repo_cache = False
        # now if we are on live, we should disable it
        # are we running on a livecd? (/proc/cmdline has "cdroot")
        if self.entropyTools.islive():
            self.xcache = False
        elif (not self.entropyTools.is_user_in_entropy_group()) and not user_xcache:
            self.xcache = False
        elif not user_xcache:
            do_validate_repo_cache = True

        if not self.xcache and (self.entropyTools.is_user_in_entropy_group()):
            try: self.purge_cache(False)
            except: pass

        if self.openclientdb:
            self.openClientDatabase()
        from entropy.client.misc import FileUpdatesInterface
        self.FileUpdates = FileUpdatesInterface(EquoInstance = self)

        from entropy.client.mirrors import StatusInterface
        # mirror status interface
        self.MirrorStatus = StatusInterface()

        from entropy.core import SystemSettings
        # setup package settings (masking and other stuff)
        self.SystemSettings = SystemSettings(self)

        # needs to be started here otherwise repository cache will be
        # always dropped
        if self.xcache:
            self.Cacher.start()

        if do_validate_repo_cache:
            self.validate_repositories_cache()

        if self.repo_validation:
            self.validate_repositories()

        # load User Generated Content Interface
        self.UGC = None
        if load_ugc:
            from entropy.client.services.ugc.interfaces import Client
            self.UGC = Client(self)

    def destroy(self):
        self.__instance_destroyed = True
        if hasattr(self,'clientDbconn'):
            if self.clientDbconn != None:
                self.clientDbconn.closeDB()
                del self.clientDbconn
        if hasattr(self,'FileUpdates'):
            del self.FileUpdates
        if hasattr(self,'clientLog'):
            self.clientLog.close()
        if hasattr(self,'Cacher'):
            self.Cacher.stop()
        if hasattr(self,'SystemSettings'):
            if hasattr(self.SystemSettings,'destroy'):
                self.SystemSettings.destroy()

        self.closeAllRepositoryDatabases(mask_clear = False)
        self.closeAllSecurity()
        self.closeAllQA()

    def is_destroyed(self):
        return self.__instance_destroyed

    def __del__(self):
        self.destroy()

    def reload_constants(self):
        initConfig_entropyConstants(etpSys['rootdir'])
        initConfig_clientConstants()

    def validate_repositories(self):
        self.MirrorStatus.clear()
        self.repo_error_messages_cache.clear()
        self.package_match_validator_cache.clear()
        # valid repositories
        del self.validRepositories[:]
        for repoid in etpRepositoriesOrder:
            # open database
            try:
                dbc = self.openRepositoryDatabase(repoid)
                dbc.listConfigProtectDirectories()
                dbc.validateDatabase()
                self.validRepositories.append(repoid)
            except RepositoryError:
                t = _("Repository") + " " + repoid + " " + _("is not available") + ". " + _("Cannot validate")
                t2 = _("Please update your repositories now in order to remove this message!")
                self.updateProgress(
                    darkred(t),
                    importance = 1,
                    type = "warning"
                )
                self.updateProgress(
                    purple(t2),
                    header = bold("!!! "),
                    importance = 1,
                    type = "warning"
                )
                continue # repo not available
            except (self.dbapi2.OperationalError,self.dbapi2.DatabaseError,SystemDatabaseError,):
                t = _("Repository") + " " + repoid + " " + _("is corrupted") + ". " + _("Cannot validate")
                self.updateProgress(
                                    darkred(t),
                                    importance = 1,
                                    type = "warning"
                                   )
                continue
        # to avoid having zillions of open files when loading a lot of EquoInterfaces
        self.closeAllRepositoryDatabases(mask_clear = False)

    def init_generic_memory_repository(self, repoid, description, package_mirrors = []):
        dbc = self.openMemoryDatabase(dbname = repoid)
        self.memoryDbInstances[repoid] = dbc

        # add to etpRepositories
        repodata = {
            'repoid': repoid,
            'in_memory': True,
            'description': description,
            'packages': package_mirrors,
            'dbpath': ':memory:',
        }
        self.addRepository(repodata)

        return dbc

    def setup_default_file_perms(self, filepath):
        # setup file permissions
        os.chmod(filepath,0664)
        if etpConst['entropygid'] != None:
            os.chown(filepath,-1,etpConst['entropygid'])

    def _resources_run_create_lock(self):
        self.create_pid_file_lock(etpConst['locks']['using_resources'])

    def _resources_run_remove_lock(self):
        if os.path.isfile(etpConst['locks']['using_resources']):
            os.remove(etpConst['locks']['using_resources'])

    def _resources_run_check_lock(self):
        rc = self.check_pid_file_lock(etpConst['locks']['using_resources'])
        return rc

    def check_pid_file_lock(self, pidfile):
        if not os.path.isfile(pidfile):
            return False # not locked
        f = open(pidfile)
        s_pid = f.readline().strip()
        f.close()
        try:
            s_pid = int(s_pid)
        except ValueError:
            return False # not locked
        # is it our pid?
        mypid = os.getpid()
        if (s_pid != mypid) and os.path.isdir("%s/proc/%s" % (etpConst['systemroot'],s_pid,)):
            # is it running
            return True # locked
        return False

    def create_pid_file_lock(self, pidfile, mypid = None):
        lockdir = os.path.dirname(pidfile)
        if not os.path.isdir(lockdir):
            os.makedirs(lockdir,0775)
        const_setup_perms(lockdir,etpConst['entropygid'])
        if mypid == None:
            mypid = os.getpid()
        f = open(pidfile,"w")
        f.write(str(mypid))
        f.flush()
        f.close()

    def application_lock_check(self, silent = False):
        # check if another instance is running
        etpConst['applicationlock'] = False
        const_setupEntropyPid(just_read = True)
        locked = self.entropyTools.applicationLockCheck(option = None, gentle = True, silent = True)
        if locked:
            if not silent:
                self.updateProgress(
                    red(_("Another Entropy instance is currently active, cannot satisfy your request.")),
                    importance = 1,
                    type = "error",
                    header = darkred(" @@ ")
                )
            return True
        return False

    def lock_check(self, check_function):

        lock_count = 0
        max_lock_count = 600
        sleep_seconds = 0.5

        # check lock file
        while 1:
            locked = check_function()
            if not locked:
                if lock_count > 0:
                    self.updateProgress(
                        blue(_("Resources unlocked, let's go!")),
                        importance = 1,
                        type = "info",
                        header = darkred(" @@ ")
                    )
                break
            if lock_count >= max_lock_count:
                mycalc = max_lock_count*sleep_seconds/60
                self.updateProgress(
                    blue(_("Resources still locked after %s minutes, giving up!")) % (mycalc,),
                    importance = 1,
                    type = "warning",
                    header = darkred(" @@ ")
                )
                return True # gave up
            lock_count += 1
            self.updateProgress(
                blue(_("Resources locked, sleeping %s seconds, check #%s/%s")) % (
                        sleep_seconds,
                        lock_count,
                        max_lock_count,
                ),
                importance = 1,
                type = "warning",
                header = darkred(" @@ "),
                back = True
            )
            time.sleep(sleep_seconds)
        return False # yay!

    def validate_repositories_cache(self):
        # is the list of repos changed?
        cached = self.Cacher.pop(etpCache['repolist'])
        if cached == None:
            # invalidate matching cache
            try: self.repository_move_clear_cache()
            except IOError: pass
        elif isinstance(cached,tuple):
            difflist = [x for x in cached if x not in etpRepositoriesOrder]
            for repoid in difflist:
                try: self.repository_move_clear_cache(repoid)
                except IOError: pass
        self.store_repository_list_cache()

    def store_repository_list_cache(self):
        self.Cacher.push(etpCache['repolist'],tuple(etpRepositoriesOrder), async = False)

    def backup_setting(self, setting_name):
        if etpConst.has_key(setting_name):
            myinst = etpConst[setting_name]
            if type(etpConst[setting_name]) in (list,tuple):
                myinst = etpConst[setting_name][:]
            elif type(etpConst[setting_name]) in (dict,set):
                myinst = etpConst[setting_name].copy()
            else:
                myinst = etpConst[setting_name]
            etpConst['backed_up'].update({setting_name: myinst})
        else:
            t = _("Nothing to backup in etpConst with %s key") % (setting_name,)
            raise InvalidData("InvalidData: %s" % (t,))

    def set_priority(self, low = 0):
        return const_setNiceLevel(low)

    def reload_repositories_config(self, repositories = None):
        if repositories == None:
            repositories = self.validRepositories
        for repoid in repositories:
            dbconn = self.openRepositoryDatabase(repoid)
            self.setup_repository_config(repoid, dbconn)

    def switchChroot(self, chroot = ""):
        # clean caches
        self.purge_cache()
        self.closeAllRepositoryDatabases()
        if chroot.endswith("/"):
            chroot = chroot[:-1]
        etpSys['rootdir'] = chroot
        self.reload_constants()
        self.validate_repositories()
        self.reopenClientDbconn()
        if chroot:
            try: self.clientDbconn.resetTreeupdatesDigests()
            except: pass
        # I don't think it's safe to keep them open
        # isn't it?
        self.closeAllSecurity()
        self.closeAllQA()

    def Security(self):
        chroot = etpConst['systemroot']
        cached = self.securityCache.get(chroot)
        if cached != None:
            return cached
        from entropy.security import SecurityInterface
        cached = SecurityInterface(self)
        self.securityCache[chroot] = cached
        return cached

    def QA(self):
        chroot = etpConst['systemroot']
        cached = self.QACache.get(chroot)
        if cached != None:
            return cached
        from entropy.qa import QAInterface
        cached = QAInterface(self)
        self.QACache[chroot] = cached
        return cached

    def closeAllQA(self):
        self.QACache.clear()

    def closeAllSecurity(self):
        self.securityCache.clear()

    def reopenClientDbconn(self):
        self.clientDbconn.closeDB()
        self.openClientDatabase()

    def closeAllRepositoryDatabases(self, mask_clear = True):
        for item in self.repoDbCache:
            self.repoDbCache[item].closeDB()
        self.repoDbCache.clear()
        if mask_clear: self.SystemSettings.clear()

    def openClientDatabase(self):

        def load_db_from_ram():
            self.safe_mode = etpConst['safemodeerrors']['clientdb']
            mytxt = "%s, %s" % (_("System database not found or corrupted"),_("running in safe mode using empty database from RAM"),)
            self.updateProgress(
                darkred(mytxt),
                importance = 1,
                type = "warning",
                header = bold("!!!"),
            )
            conn = self.openMemoryDatabase(dbname = etpConst['clientdbid'])
            return conn

        if not os.path.isdir(os.path.dirname(etpConst['etpdatabaseclientfilepath'])):
            os.makedirs(os.path.dirname(etpConst['etpdatabaseclientfilepath']))

        if (not self.noclientdb) and (not os.path.isfile(etpConst['etpdatabaseclientfilepath'])):
            conn = load_db_from_ram()
            self.entropyTools.printTraceback(f = self.clientLog)
        else:
            conn = LocalRepository(
                readOnly = False,
                dbFile = etpConst['etpdatabaseclientfilepath'],
                clientDatabase = True,
                dbname = etpConst['clientdbid'],
                xcache = self.xcache,
                indexing = self.indexing,
                OutputInterface = self,
                ServiceInterface = self
            )
            # validate database
            if not self.noclientdb:
                try:
                    conn.validateDatabase()
                except SystemDatabaseError:
                    try:
                        conn.closeDB()
                    except:
                        pass
                    self.entropyTools.printTraceback(f = self.clientLog)
                    conn = load_db_from_ram()

        if not etpConst['dbconfigprotect']:

            if conn.doesTableExist('configprotect') and conn.doesTableExist('configprotectreference'):
                etpConst['dbconfigprotect'] = conn.listConfigProtectDirectories()
            if conn.doesTableExist('configprotectmask') and conn.doesTableExist('configprotectreference'):
                etpConst['dbconfigprotectmask'] = conn.listConfigProtectDirectories(mask = True)

            etpConst['dbconfigprotect'] = [etpConst['systemroot']+x for x in etpConst['dbconfigprotect']]
            etpConst['dbconfigprotectmask'] = [etpConst['systemroot']+x for x in etpConst['dbconfigprotect']]

            etpConst['dbconfigprotect'] += [etpConst['systemroot']+x for x in etpConst['configprotect'] if etpConst['systemroot']+x not in etpConst['dbconfigprotect']]
            etpConst['dbconfigprotectmask'] += [etpConst['systemroot']+x for x in etpConst['configprotectmask'] if etpConst['systemroot']+x not in etpConst['dbconfigprotectmask']]

        self.clientDbconn = conn
        return self.clientDbconn

    def clientDatabaseSanityCheck(self):
        self.updateProgress(
            darkred(_("Sanity Check") + ": " + _("system database")),
            importance = 2,
            type = "warning"
        )
        idpkgs = self.clientDbconn.listAllIdpackages()
        length = len(idpkgs)
        count = 0
        errors = False
        scanning_txt = _("Scanning...")
        for x in idpkgs:
            count += 1
            self.updateProgress(
                                    darkgreen(scanning_txt),
                                    importance = 0,
                                    type = "info",
                                    back = True,
                                    count = (count,length),
                                    percent = True
                                )
            try:
                self.clientDbconn.getPackageData(x)
            except Exception ,e:
                self.entropyTools.printTraceback()
                errors = True
                self.updateProgress(
                    darkred(_("Errors on idpackage %s, error: %s")) % (x,str(e)),
                    importance = 0,
                    type = "warning"
                )

        if not errors:
            t = _("Sanity Check") + ": %s" % (bold(_("PASSED")),)
            self.updateProgress(
                darkred(t),
                importance = 2,
                type = "warning"
            )
            return 0
        else:
            t = _("Sanity Check") + ": %s" % (bold(_("CORRUPTED")),)
            self.updateProgress(
                darkred(t),
                importance = 2,
                type = "warning"
            )
            return -1

    def openRepositoryDatabase(self, repoid):
        t_ident = 1 # thread.get_ident() disabled for now
        if not self.repoDbCache.has_key((repoid,etpConst['systemroot'],t_ident,)):
            dbconn = self.load_repository_database(repoid, xcache = self.xcache, indexing = self.indexing)
            try:
                dbconn.checkDatabaseApi()
            except:
                pass
            self.repoDbCache[(repoid,etpConst['systemroot'],t_ident,)] = dbconn
            return dbconn
        else:
            return self.repoDbCache.get((repoid,etpConst['systemroot'],t_ident,))

    def is_installed_idpackage_in_system_mask(self, idpackage):
        if idpackage in self.SystemSettings['repos_system_mask_installed']:
            return True
        return False

    '''
    @description: open the repository database
    @input repositoryName: name of the client database
    @input xcache: loads on-disk cache
    @input indexing: indexes SQL tables
    @output: database class instance
    NOTE: DO NOT USE THIS DIRECTLY, BUT USE EquoInterface.openRepositoryDatabase
    '''
    def load_repository_database(self, repoid, xcache = True, indexing = True):

        if isinstance(repoid,basestring):
            if repoid.endswith(etpConst['packagesext']):
                xcache = False

        if repoid not in etpRepositories:
            t = _("bad repository id specified")
            if repoid not in self.repo_error_messages_cache:
                self.updateProgress(
                    darkred(t),
                    importance = 2,
                    type = "warning"
                )
                self.repo_error_messages_cache.add(repoid)
            raise RepositoryError("RepositoryError: %s" % (t,))

        dbfile = etpRepositories[repoid]['dbpath']+"/"+etpConst['etpdatabasefile']
        if not os.path.isfile(dbfile):
            t = _("Repository %s hasn't been downloaded yet.") % (repoid,)
            if repoid not in self.repo_error_messages_cache:
                self.updateProgress(
                    darkred(t),
                    importance = 2,
                    type = "warning"
                )
                self.repo_error_messages_cache.add(repoid)
            raise RepositoryError("RepositoryError: %s" % (t,))

        conn = LocalRepository(
            readOnly = True,
            dbFile = dbfile,
            clientDatabase = True,
            dbname = etpConst['dbnamerepoprefix']+repoid,
            xcache = xcache,
            indexing = indexing,
            OutputInterface = self,
            ServiceInterface = self
        )
        # initialize CONFIG_PROTECT
        if (etpRepositories[repoid]['configprotect'] == None) or \
            (etpRepositories[repoid]['configprotectmask'] == None):
                self.setup_repository_config(repoid, conn)

        if (repoid not in etpConst['client_treeupdatescalled']) and (self.entropyTools.is_user_in_entropy_group()) and (not repoid.endswith(etpConst['packagesext'])):
            updated = False
            try:
                updated = conn.clientUpdatePackagesData(self.clientDbconn)
            except (self.dbapi2.OperationalError, self.dbapi2.DatabaseError):
                pass
            if updated:
                self.clear_dump_cache(etpCache['world_update'])
                self.clear_dump_cache(etpCache['world'])
                self.clear_dump_cache(etpCache['install'])
                self.clear_dump_cache(etpCache['remove'])
                self.calculate_world_updates(use_cache = False)
        return conn

    def setup_repository_config(self, repoid, dbconn):

        try:
            etpRepositories[repoid]['configprotect'] = dbconn.listConfigProtectDirectories()
        except (self.dbapi2.OperationalError, self.dbapi2.DatabaseError):
            etpRepositories[repoid]['configprotect'] = []
        try:
            etpRepositories[repoid]['configprotectmask'] = dbconn.listConfigProtectDirectories(mask = True)
        except (self.dbapi2.OperationalError, self.dbapi2.DatabaseError):
            etpRepositories[repoid]['configprotectmask'] = []

        etpRepositories[repoid]['configprotect'] = [etpConst['systemroot']+x for x in etpRepositories[repoid]['configprotect']]
        etpRepositories[repoid]['configprotectmask'] = [etpConst['systemroot']+x for x in etpRepositories[repoid]['configprotectmask']]

        etpRepositories[repoid]['configprotect'] += [etpConst['systemroot']+x for x in etpConst['configprotect'] if etpConst['systemroot']+x not in etpRepositories[repoid]['configprotect']]
        etpRepositories[repoid]['configprotectmask'] += [etpConst['systemroot']+x for x in etpConst['configprotectmask'] if etpConst['systemroot']+x not in etpRepositories[repoid]['configprotectmask']]

    def openGenericDatabase(self, dbfile, dbname = None, xcache = None, readOnly = False, indexing_override = None, skipChecks = False):
        if xcache == None:
            xcache = self.xcache
        if indexing_override != None:
            indexing = indexing_override
        else:
            indexing = self.indexing
        if dbname == None:
            dbname = etpConst['genericdbid']
        return LocalRepository(
            readOnly = readOnly,
            dbFile = dbfile,
            clientDatabase = True,
            dbname = dbname,
            xcache = xcache,
            indexing = indexing,
            OutputInterface = self,
            skipChecks = skipChecks
        )

    def openMemoryDatabase(self, dbname = None):
        if dbname == None:
            dbname = etpConst['genericdbid']
        dbc = LocalRepository(
            readOnly = False,
            dbFile = ':memory:',
            clientDatabase = True,
            dbname = dbname,
            xcache = False,
            indexing = False,
            OutputInterface = self,
            skipChecks = True
        )
        dbc.initializeDatabase()
        return dbc

    def backupDatabase(self, dbpath, backup_dir = None, silent = False, compress_level = 9):

        if compress_level not in range(1,10):
            compress_level = 9

        backup_dir = os.path.dirname(dbpath)
        if not backup_dir: backup_dir = os.path.dirname(dbpath)
        dbname = os.path.basename(dbpath)
        bytes_required = 1024000*300
        if not (os.access(backup_dir,os.W_OK) and \
                os.path.isdir(backup_dir) and os.path.isfile(dbpath) and \
                os.access(dbpath,os.R_OK) and self.entropyTools.check_required_space(backup_dir, bytes_required)):
            if not silent:
                mytxt = "%s: %s, %s" % (darkred(_("Cannot backup selected database")),blue(dbpath),darkred(_("permission denied")),)
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "error",
                    header = red(" @@ ")
                )
            return False, mytxt

        def get_ts():
            from datetime import datetime
            ts = datetime.fromtimestamp(time.time())
            return "%s%s%s_%sh%sm%ss" % (ts.year,ts.month,ts.day,ts.hour,ts.minute,ts.second)

        comp_dbname = "%s%s.%s.bz2" % (etpConst['dbbackupprefix'],dbname,get_ts(),)
        comp_dbpath = os.path.join(backup_dir,comp_dbname)
        if not silent:
            mytxt = "%s: %s ..." % (darkgreen(_("Backing up database to")),blue(comp_dbpath),)
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True
            )
        import bz2
        try:
            self.entropyTools.compress_file(dbpath, comp_dbpath, bz2.BZ2File, compress_level)
        except:
            if not silent:
                self.entropyTools.printTraceback()
            return False, _("Unable to compress")

        if not silent:
            mytxt = "%s: %s" % (darkgreen(_("Database backed up successfully")),blue(comp_dbpath),)
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True
            )
        return True, _("All fine")

    def restoreDatabase(self, backup_path, db_destination, silent = False):

        bytes_required = 1024000*300
        if not (os.access(os.path.dirname(db_destination),os.W_OK) and \
                os.path.isdir(os.path.dirname(db_destination)) and os.path.isfile(backup_path) and \
                os.access(backup_path,os.R_OK) and self.entropyTools.check_required_space(os.path.dirname(db_destination), bytes_required)):
            if not silent:
                mytxt = "%s: %s, %s" % (darkred(_("Cannot restore selected backup")),blue(backup_path),darkred(_("permission denied")),)
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "error",
                    header = red(" @@ ")
                )
            return False, mytxt

        if not silent:
            mytxt = "%s: %s => %s ..." % (darkgreen(_("Restoring backed up database")),blue(os.path.basename(backup_path)),blue(db_destination),)
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True
            )

        import bz2
        try:
            self.entropyTools.uncompress_file(backup_path, db_destination, bz2.BZ2File)
        except:
            if not silent:
                self.entropyTools.printTraceback()
            return False, _("Unable to unpack")

        if not silent:
            mytxt = "%s: %s" % (darkgreen(_("Database restored successfully")),blue(db_destination),)
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True
            )
        self.purge_cache()
        return True, _("All fine")

    def list_backedup_client_databases(self, client_dbdir = None):
        if not client_dbdir:
            client_dbdir = os.path.dirname(etpConst['etpdatabaseclientfilepath'])
        return [os.path.join(client_dbdir,x) for x in os.listdir(client_dbdir) \
                    if x.startswith(etpConst['dbbackupprefix']) and \
                    os.access(os.path.join(client_dbdir,x),os.R_OK)
        ]

    def get_branch_from_download_relative_uri(self, db_download_uri):
        return db_download_uri.split("/")[2]

    '''
       Cache stuff :: begin
    '''
    def purge_cache(self, showProgress = True, client_purge = True):
        if self.entropyTools.is_user_in_entropy_group():
            skip = set()
            if not client_purge:
                skip.add("/"+etpCache['dbMatch']+"/"+etpConst['clientdbid']) # it's ok this way
                skip.add("/"+etpCache['dbSearch']+"/"+etpConst['clientdbid']) # it's ok this way
            for key in etpCache:
                if showProgress:
                    self.updateProgress(
                        darkred(_("Cleaning %s => dumps...")) % (etpCache[key],),
                        importance = 1,
                        type = "warning",
                        back = True
                    )
                self.clear_dump_cache(etpCache[key], skip = skip)

            if showProgress:
                self.updateProgress(
                    darkgreen(_("Cache is now empty.")),
                    importance = 2,
                    type = "info"
                )

    def generate_cache(self, depcache = True, configcache = True, client_purge = True, install_queue = True):
        self.Cacher.stop()
        # clean first of all
        self.purge_cache(client_purge = client_purge)
        if depcache:
            self.do_depcache(do_install_queue = install_queue)
        if configcache:
            self.do_configcache()
        self.Cacher.start()

    def do_configcache(self):
        self.updateProgress(
            darkred(_("Configuration files")),
            importance = 2,
            type = "warning"
        )
        self.updateProgress(
            red(_("Scanning hard disk")),
            importance = 1,
            type = "warning"
        )
        self.FileUpdates.scanfs(dcache = False, quiet = True)
        self.updateProgress(
            darkred(_("Cache generation complete.")),
            importance = 2,
            type = "info"
        )

    def do_depcache(self, do_install_queue = True):

        self.updateProgress(
            darkgreen(_("Resolving metadata")),
            importance = 1,
            type = "warning"
        )
        # we can barely ignore any exception from here
        # especially cases where client db does not exist
        try:
            update, remove, fine = self.calculate_world_updates()
            del fine, remove
            if do_install_queue:
                self.retrieveInstallQueue(update, False, False)
            self.calculate_available_packages()
        except:
            pass

        self.updateProgress(
            darkred(_("Dependencies cache filled.")),
            importance = 2,
            type = "warning"
        )

    def clear_dump_cache(self, dump_name, skip = []):
        self.Cacher.sync(wait = True)
        dump_path = os.path.join(etpConst['dumpstoragedir'],dump_name)
        dump_dir = os.path.dirname(dump_path)
        #dump_file = os.path.basename(dump_path)
        for currentdir, subdirs, files in os.walk(dump_dir):
            path = os.path.join(dump_dir,currentdir)
            if skip:
                found = False
                for myskip in skip:
                    if path.find(myskip) != -1:
                        found = True
                        break
                if found: continue
            for item in files:
                if item.endswith(etpConst['cachedumpext']):
                    item = os.path.join(path,item)
                    try: os.remove(item)
                    except OSError: pass
            try:
                if not os.listdir(path):
                    os.rmdir(path)
            except OSError:
                pass

    '''
       Cache stuff :: end
    '''

    def unused_packages_test(self, dbconn = None):
        if dbconn == None: dbconn = self.clientDbconn
        return [x for x in dbconn.retrieveUnusedIdpackages() if self.validatePackageRemoval(x)]

    def dependencies_test(self, dbconn = None):

        if dbconn == None:
            dbconn = self.clientDbconn
        # get all the installed packages
        installedPackages = dbconn.listAllIdpackages()

        deps_not_matched = set()
        # now look
        length = len(installedPackages)
        count = 0
        for xidpackage in installedPackages:
            count += 1
            atom = dbconn.retrieveAtom(xidpackage)
            self.updateProgress(
                darkgreen(_("Checking %s") % (bold(atom),)),
                importance = 0,
                type = "info",
                back = True,
                count = (count,length),
                header = darkred(" @@ ")
            )

            xdeps = dbconn.retrieveDependencies(xidpackage)
            needed_deps = set()
            for xdep in xdeps:
                xmatch = dbconn.atomMatch(xdep)
                if xmatch[0] == -1:
                    needed_deps.add(xdep)

            deps_not_matched |= needed_deps

        return deps_not_matched

    def find_belonging_dependency(self, matched_atoms):
        crying_atoms = set()
        for atom in matched_atoms:
            for repo in self.validRepositories:
                rdbconn = self.openRepositoryDatabase(repo)
                riddep = rdbconn.searchDependency(atom)
                if riddep != -1:
                    ridpackages = rdbconn.searchIdpackageFromIddependency(riddep)
                    for i in ridpackages:
                        i,r = rdbconn.idpackageValidator(i)
                        if i == -1:
                            continue
                        iatom = rdbconn.retrieveAtom(i)
                        crying_atoms.add((iatom,repo))
        return crying_atoms

    def get_licenses_to_accept(self, install_queue):
        if not install_queue:
            return {}
        licenses = {}
        for match in install_queue:
            repoid = match[1]
            dbconn = self.openRepositoryDatabase(repoid)
            wl = self.SystemSettings['repos_license_whitelist'].get(repoid)
            if not wl:
                continue
            keys = dbconn.retrieveLicensedataKeys(match[0])
            for key in keys:
                if key not in wl:
                    found = self.clientDbconn.isLicenseAccepted(key)
                    if found:
                        continue
                    if not licenses.has_key(key):
                        licenses[key] = set()
                    licenses[key].add(match)
        return licenses

    def get_text_license(self, license_name, repoid):
        dbconn = self.openRepositoryDatabase(repoid)
        text = dbconn.retrieveLicenseText(license_name)
        tempfile = self.entropyTools.getRandomTempFile()
        f = open(tempfile,"w")
        f.write(text)
        f.flush()
        f.close()
        return tempfile

    def get_file_viewer(self):
        viewer = None
        if os.access("/usr/bin/less",os.X_OK):
            viewer = "/usr/bin/less"
        elif os.access("/bin/more",os.X_OK):
            viewer = "/bin/more"
        if not viewer:
            viewer = self.get_file_editor()
        return viewer

    def get_file_editor(self):
        editor = None
        if os.getenv("EDITOR"):
            editor = "$EDITOR"
        elif os.access("/bin/nano",os.X_OK):
            editor = "/bin/nano"
        elif os.access("/bin/vi",os.X_OK):
            editor = "/bin/vi"
        elif os.access("/usr/bin/vi",os.X_OK):
            editor = "/usr/bin/vi"
        elif os.access("/usr/bin/emacs",os.X_OK):
            editor = "/usr/bin/emacs"
        elif os.access("/bin/emacs",os.X_OK):
            editor = "/bin/emacs"
        return editor

    def libraries_test(self, dbconn = None, broken_symbols = False, task_bombing_func = None):

        if dbconn == None:
            dbconn = self.clientDbconn

        self.updateProgress(
            blue(_("Libraries test")),
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )

        if not etpConst['systemroot']:
            myroot = "/"
        else:
            myroot = etpConst['systemroot']+"/"
        # run ldconfig first
        subprocess.call("ldconfig -r %s &> /dev/null" % (myroot,), shell = True)
        # open /etc/ld.so.conf
        if not os.path.isfile(etpConst['systemroot']+"/etc/ld.so.conf"):
            self.updateProgress(
                blue(_("Cannot find "))+red(etpConst['systemroot']+"/etc/ld.so.conf"),
                importance = 1,
                type = "error",
                header = red(" @@ ")
            )
            return {},set(),-1

        ldpaths = set(self.entropyTools.collectLinkerPaths())
        ldpaths |= self.entropyTools.collectPaths()
        # speed up when /usr/lib is a /usr/lib64 symlink
        if "/usr/lib64" in ldpaths and "/usr/lib" in ldpaths:
            if os.path.realpath("/usr/lib64") == "/usr/lib":
                ldpaths.discard("/usr/lib")
        # some crappy packages put shit here too
        ldpaths.add("/usr/share")
        # always force /usr/libexec too
        ldpaths.add("/usr/libexec")

        executables = set()
        total = len(ldpaths)
        count = 0
        sys_root_len = len(etpConst['systemroot'])
        for ldpath in ldpaths:
            if callable(task_bombing_func): task_bombing_func()
            count += 1
            self.updateProgress(
                blue("Tree: ")+red(etpConst['systemroot']+ldpath),
                importance = 0,
                type = "info",
                count = (count,total),
                back = True,
                percent = True,
                header = "  "
            )
            ldpath = ldpath.encode(sys.getfilesystemencoding())
            mywalk_iter = os.walk(etpConst['systemroot']+ldpath)

            def mywimf(dt):

                currentdir, subdirs, files = dt

                def mymf(item):
                    filepath = os.path.join(currentdir,item)
                    if filepath in etpConst['libtest_files_blacklist']:
                        return 0
                    if not os.access(filepath,os.R_OK):
                        return 0
                    if not os.path.isfile(filepath):
                        return 0
                    if not self.entropyTools.is_elf_file(filepath):
                        return 0
                    return filepath[sys_root_len:]

                return set([x for x in map(mymf,files) if type(x) != int])

            for x in map(mywimf,mywalk_iter): executables |= x

        self.updateProgress(
            blue(_("Collecting broken executables")),
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )
        t = red(_("Attention")) + ": " + \
            blue(_("don't worry about libraries that are shown here but not later."))
        self.updateProgress(
            t,
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        myQA = self.QA()

        plain_brokenexecs = set()
        total = len(executables)
        count = 0
        scan_txt = blue("%s ..." % (_("Scanning libraries"),))
        for executable in executables:
            if callable(task_bombing_func): task_bombing_func()
            count += 1
            if (count%10 == 0) or (count == total) or (count == 1):
                self.updateProgress(
                    scan_txt,
                    importance = 0,
                    type = "info",
                    count = (count,total),
                    back = True,
                    percent = True,
                    header = "  "
                )
            myelfs = self.entropyTools.read_elf_dynamic_libraries(etpConst['systemroot']+executable)
            def mymf2(mylib):
                return not myQA.resolve_dynamic_library(mylib, executable)
            mylibs = set(filter(mymf2,myelfs))
            broken_sym_found = set()
            if broken_symbols and not mylibs: broken_sym_found |= self.entropyTools.read_elf_broken_symbols(etpConst['systemroot']+executable)
            if not (mylibs or broken_sym_found):
                continue

            if mylibs:
                alllibs = blue(' :: ').join(list(mylibs))
                self.updateProgress(
                    red(etpConst['systemroot']+executable)+" [ "+alllibs+" ]",
                    importance = 1,
                    type = "info",
                    percent = True,
                    count = (count,total),
                    header = "  "
                )
            elif broken_sym_found:
                allsyms = darkred(' :: ').join([brown(x) for x in list(broken_sym_found)])
                if len(allsyms) > 50: allsyms = brown(_('various broken symbols'))
                self.updateProgress(
                    red(etpConst['systemroot']+executable)+" { "+allsyms+" }",
                    importance = 1,
                    type = "info",
                    percent = True,
                    count = (count,total),
                    header = "  "
                )
            plain_brokenexecs.add(executable)

        del executables
        packagesMatched = {}

        if not etpSys['serverside']:

            self.updateProgress(
                blue(_("Matching broken libraries/executables")),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )
            matched = set()
            for brokenlib in plain_brokenexecs:
                idpackages = self.clientDbconn.searchBelongs(brokenlib)
                for idpackage in idpackages:
                    key, slot = self.clientDbconn.retrieveKeySlot(idpackage)
                    mymatch = self.atomMatch(key, matchSlot = slot)
                    if mymatch[0] == -1:
                        matched.add(brokenlib)
                        continue
                    cmpstat = self.get_package_action(mymatch)
                    if cmpstat == 0:
                        continue
                    if not packagesMatched.has_key(brokenlib):
                        packagesMatched[brokenlib] = set()
                    packagesMatched[brokenlib].add(mymatch)
                    matched.add(brokenlib)
            plain_brokenexecs -= matched

        return packagesMatched,plain_brokenexecs,0

    def move_to_branch(self, branch, pretend = False):
        if pretend: return 0
        if branch != etpConst['branch']:
            # update configuration
            self.entropyTools.writeNewBranch(branch)
            # reset treeupdatesactions
            self.clientDbconn.resetTreeupdatesDigests()
            # clean cache
            self.purge_cache(showProgress = False)
            # reopen Client Database, this will make treeupdates to be re-read
            self.closeAllRepositoryDatabases()
            etpConst['branch'] = branch
            self.reload_constants()
            etpConst['branch'] = branch
            self.validate_repositories()
            self.reopenClientDbconn()
        return 0

    # tell if a new equo release is available, returns True or False
    def check_equo_updates(self):
        found, match = self.check_package_update("app-admin/equo", deep = True)
        return found

    '''
        @input: matched atom (idpackage,repoid)
        @output:
                upgrade: int(2)
                install: int(1)
                reinstall: int(0)
                downgrade: int(-1)
    '''
    def get_package_action(self, match):
        dbconn = self.openRepositoryDatabase(match[1])
        pkgkey, pkgslot = dbconn.retrieveKeySlot(match[0])
        results = self.clientDbconn.searchKeySlot(pkgkey, pkgslot)
        if not results: return 1

        installed_idpackage = results[0][0]
        pkgver, pkgtag, pkgrev = dbconn.getVersioningData(match[0])
        installedVer, installedTag, installedRev = self.clientDbconn.getVersioningData(installed_idpackage)
        pkgcmp = self.entropyTools.entropyCompareVersions((pkgver,pkgtag,pkgrev),(installedVer,installedTag,installedRev))
        if pkgcmp == 0:
            return 0
        elif pkgcmp > 0:
            return 2
        return -1

    def get_meant_packages(self, search_term, from_installed = False, valid_repos = []):

        pkg_data = []
        atom_srch = False
        if "/" in search_term: atom_srch = True

        if not valid_repos: valid_repos = self.validRepositories
        if from_installed: valid_repos = [1]
        for repo in valid_repos:
            if isinstance(repo,basestring):
                dbconn = self.openRepositoryDatabase(repo)
            elif isinstance(repo,LocalRepository):
                dbconn = repo
            elif hasattr(self,'clientDbconn'):
                dbconn = self.clientDbconn
            else:
                continue
            pkg_data.extend([(x,repo,) for x in dbconn.searchSimilarPackages(search_term, atom = atom_srch)])

        return pkg_data

    # better to use key:slot
    def check_package_update(self, atom, deep = False):

        c_hash = "%s%s" % (etpCache['check_package_update'],hash("%s%s" % (atom,hash(deep),)),)
        if self.xcache:
            cached = self.Cacher.pop(c_hash)
            if cached != None:
                return cached

        found = False
        match = self.clientDbconn.atomMatch(atom)
        matched = None
        if match[0] != -1:
            myatom = self.clientDbconn.retrieveAtom(match[0])
            mytag = self.entropyTools.dep_gettag(myatom)
            myatom = self.entropyTools.remove_tag(myatom)
            myrev = self.clientDbconn.retrieveRevision(match[0])
            pkg_match = "="+myatom+"~"+str(myrev)
            if mytag != None:
                pkg_match += "#%s" % (mytag,)
            pkg_unsatisfied = self.get_unsatisfied_dependencies([pkg_match], deep_deps = deep)
            if pkg_unsatisfied:
                found = True
            del pkg_unsatisfied
            matched = self.atomMatch(pkg_match)
        del match

        if self.xcache:
            self.Cacher.push(c_hash,(found,matched))

        return found, matched


    # @returns -1 if the file does not exist or contains bad data
    # @returns int>0 if the file exists
    def get_repository_revision(self, reponame):
        if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabaserevisionfile']):
            f = open(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'],"r")
            try:
                revision = int(f.readline().strip())
            except:
                revision = -1
            f.close()
        else:
            revision = -1
        return revision

    def update_repository_revision(self, reponame):
        r = self.get_repository_revision(reponame)
        etpRepositories[reponame]['dbrevision'] = "0"
        if r != -1:
            etpRepositories[reponame]['dbrevision'] = str(r)

    # @returns -1 if the file does not exist
    # @returns int>0 if the file exists
    def get_repository_db_file_checksum(self, reponame):
        if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasehashfile']):
            f = open(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
            try:
                mhash = f.readline().strip().split()[0]
            except:
                mhash = "-1"
            f.close()
        else:
            mhash = "-1"
        return mhash

    def update_ugc_cache(self, repository):
        if not self.UGC.is_repository_eapi3_aware(repository):
            return None
        status = True

        votes_dict, err_msg = self.UGC.get_all_votes(repository)
        if isinstance(votes_dict,dict):
            self.UGC.UGCCache.save_vote_cache(repository, votes_dict)
        else:
            status = False

        downloads_dict, err_msg = self.UGC.get_all_downloads(repository)
        if isinstance(downloads_dict,dict):
            self.UGC.UGCCache.save_downloads_cache(repository, downloads_dict)
        else:
            status = False
        return status

    def __handle_multi_repo_matches(self, results, extended_results, valid_repos, server_inst):

        packageInformation = {}
        versionInformation = {}
        # .tbz2 repos have always the precedence, so if we find them,
        # we should second what user wants, installing his tbz2
        tbz2repos = [x for x in results if x.endswith(etpConst['packagesext'])]
        if tbz2repos:
            del tbz2repos
            newrepos = results.copy()
            for x in newrepos:
                if x.endswith(etpConst['packagesext']):
                    continue
                del results[x]

        version_duplicates = set()
        versions = set()
        for repo in results:
            packageInformation[repo] = {}
            if extended_results:
                version = results[repo][1]
                packageInformation[repo]['versiontag'] = results[repo][2]
                packageInformation[repo]['revision'] = results[repo][3]
            else:
                dbconn = self.__atom_match_open_db(repo, server_inst)
                packageInformation[repo]['versiontag'] = dbconn.retrieveVersionTag(results[repo])
                packageInformation[repo]['revision'] = dbconn.retrieveRevision(results[repo])
                version = dbconn.retrieveVersion(results[repo])
            packageInformation[repo]['version'] = version
            versionInformation[version] = repo
            if version in versions:
                version_duplicates.add(version)
            versions.add(version)

        newerVersion = self.entropyTools.getNewerVersion(list(versions))[0]
        # if no duplicates are found or newer version is not in duplicates we're done
        if (not version_duplicates) or (newerVersion not in version_duplicates):
            reponame = versionInformation.get(newerVersion)
            return (results[reponame],reponame)

        # we have two repositories with >two packages with the same version
        # check package tag

        conflictingEntries = {}
        tags_duplicates = set()
        tags = set()
        tagsInfo = {}
        for repo in packageInformation:
            if packageInformation[repo]['version'] != newerVersion:
                continue
            conflictingEntries[repo] = {}
            versiontag = packageInformation[repo]['versiontag']
            if versiontag in tags:
                tags_duplicates.add(versiontag)
            tags.add(versiontag)
            tagsInfo[versiontag] = repo
            conflictingEntries[repo]['versiontag'] = versiontag
            conflictingEntries[repo]['revision'] = packageInformation[repo]['revision']

        # tags will always be != []
        newerTag = sorted(list(tags), reverse = True)[0]
        if newerTag not in tags_duplicates:
            reponame = tagsInfo.get(newerTag)
            return (results[reponame],reponame)

        # in this case, we have >two packages with the same version and tag
        # check package revision

        conflictingRevisions = {}
        revisions = set()
        revisions_duplicates = set()
        revisionInfo = {}
        for repo in conflictingEntries:
            if conflictingEntries[repo]['versiontag'] == newerTag:
                conflictingRevisions[repo] = {}
                versionrev = conflictingEntries[repo]['revision']
                if versionrev in revisions:
                    revisions_duplicates.add(versionrev)
                revisions.add(versionrev)
                revisionInfo[versionrev] = repo
                conflictingRevisions[repo]['revision'] = versionrev

        newerRevision = max(revisions)
        if newerRevision not in revisions_duplicates:
            reponame = revisionInfo.get(newerRevision)
            return (results[reponame],reponame)

        # final step, in this case we have >two packages with the same version, tag and revision
        # get the repository with the biggest priority

        for reponame in valid_repos:
            if reponame in conflictingRevisions:
                return (results[reponame],reponame)

    def __validate_atom_match_cache(self, cached_obj, multiMatch, extendedResults, multiRepo, server_inst):

        data, rc = cached_obj
        if rc == 1: return cached_obj

        if multiRepo or multiMatch:
            matches = data # set([(14789, 'sabayonlinux.org'), (14479, 'sabayonlinux.org')])
            if extendedResults:
                # set([((14789, u'3.3.8b', u'', 0), 'sabayonlinux.org')])
                matches = [(x[0][0],x[1],) for x in data]
            for m_id, m_repo in matches:
                m_db = self.__atom_match_open_db(m_repo, server_inst)
                if not m_db.isIDPackageAvailable(m_id): return None
        else:
            m_id, m_repo = cached_obj # (14479, 'sabayonlinux.org')
            if extendedResults:
                # ((14479, u'4.4.2', u'', 0), 'sabayonlinux.org')
                m_id, m_repo = cached_obj[0][0],cached_obj[1]
            m_db = self.__atom_match_open_db(m_repo, server_inst)
            if not m_db.isIDPackageAvailable(m_id): return None

        return cached_obj

    def __atom_match_open_db(self, repoid, server_inst):
        if server_inst != None:
            dbconn = server_inst.openServerDatabase(just_reading = True, repo = repoid)
        else:
            dbconn = self.openRepositoryDatabase(repoid)
        return dbconn

    def atomMatch(self, atom, caseSensitive = True, matchSlot = None,
            matchBranches = (), matchTag = None, packagesFilter = True,
            multiMatch = False, multiRepo = False, matchRevision = None,
            matchRepo = None, server_repos = [], serverInstance = None,
            extendedResults = False, useCache = True):

        # support match in repository from shell
        # atom@repo1,repo2,repo3
        atom, repos = self.entropyTools.dep_get_match_in_repos(atom)
        if (matchRepo == None) and (repos != None):
            matchRepo = repos

        u_hash = ""
        m_hash = ""
        k_ms = "//"
        k_mt = "@#@"
        k_mr = "-1"
        if isinstance(matchRepo,(list,tuple,set,)): u_hash = hash(frozenset(matchRepo))
        if isinstance(matchBranches,(list,tuple,set,)): m_hash = hash(frozenset(matchBranches))
        if isinstance(matchSlot,basestring): k_ms = matchSlot
        if isinstance(matchTag,basestring): k_mt = matchTag
        if isinstance(matchRevision,basestring): k_mr = matchRevision

        c_hash = "|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s" % (
            atom,k_ms,k_mt,hash(packagesFilter),
            hash(frozenset(self.validRepositories)),
            hash(frozenset(etpRepositories)),
            hash(multiMatch),hash(multiRepo),hash(caseSensitive),
            k_mr,hash(extendedResults),
            u_hash, m_hash
        )
        c_hash = "%s%s" % (self.atomMatchCacheKey,hash(c_hash),)

        if self.xcache and useCache:
            cached = self.Cacher.pop(c_hash)
            if cached != None:
                try:
                    cached = self.__validate_atom_match_cache(cached, multiMatch, extendedResults, multiRepo, serverInstance)
                except (TypeError,ValueError,IndexError,KeyError,):
                    cached = None
            if cached != None:
                return cached

        if server_repos:
            if not serverInstance:
                t = _("server_repos needs serverInstance")
                raise IncorrectParameter("IncorrectParameter: %s" % (t,))
            valid_repos = server_repos[:]
        else:
            valid_repos = self.validRepositories
        if matchRepo and (type(matchRepo) in (list,tuple,set)):
            valid_repos = list(matchRepo)

        repoResults = {}
        for repo in valid_repos:

            # search
            dbconn = self.__atom_match_open_db(repo, serverInstance)
            use_cache = useCache
            while 1:
                try:
                    query_data, query_rc = dbconn.atomMatch(
                        atom,
                        caseSensitive = caseSensitive,
                        matchSlot = matchSlot,
                        matchBranches = matchBranches,
                        matchTag = matchTag,
                        packagesFilter = packagesFilter,
                        matchRevision = matchRevision,
                        extendedResults = extendedResults,
                        useCache = use_cache
                    )
                    if query_rc == 0:
                        # package found, add to our dictionary
                        if extendedResults:
                            repoResults[repo] = (query_data[0],query_data[2],query_data[3],query_data[4])
                        else:
                            repoResults[repo] = query_data
                except TypeError:
                    if not use_cache:
                        raise
                    use_cache = False
                    continue
                break

        dbpkginfo = (-1,1)
        if extendedResults:
            dbpkginfo = ((-1,None,None,None),1)

        if multiRepo and repoResults:

            data = set()
            for repoid in repoResults:
                data.add((repoResults[repoid],repoid))
            dbpkginfo = (data,0)

        elif len(repoResults) == 1:
            # one result found
            repo = repoResults.keys()[0]
            dbpkginfo = (repoResults[repo],repo)

        elif len(repoResults) > 1:

            # we have to decide which version should be taken
            mypkginfo = self.__handle_multi_repo_matches(repoResults, extendedResults, valid_repos, serverInstance)
            if mypkginfo != None: dbpkginfo = mypkginfo

        # multimatch support
        if multiMatch:

            if dbpkginfo[1] != 1: # can be "0" or a string, but 1 means failure
                if multiRepo:
                    data = set()
                    for q_id,q_repo in dbpkginfo[0]:
                        dbconn = self.__atom_match_open_db(q_repo, serverInstance)
                        query_data, query_rc = dbconn.atomMatch(
                            atom,
                            caseSensitive = caseSensitive,
                            matchSlot = matchSlot,
                            matchBranches = matchBranches,
                            matchTag = matchTag,
                            packagesFilter = packagesFilter,
                            multiMatch = True,
                            extendedResults = extendedResults
                        )
                        if extendedResults:
                            for item in query_data:
                                data.add(((item[0],item[2],item[3],item[4]),q_repo))
                        else:
                            for x in query_data: data.add((x,q_repo))
                    dbpkginfo = (data,0)
                else:
                    dbconn = self.__atom_match_open_db(dbpkginfo[1], serverInstance)
                    query_data, query_rc = dbconn.atomMatch(
                                                atom,
                                                caseSensitive = caseSensitive,
                                                matchSlot = matchSlot,
                                                matchBranches = matchBranches,
                                                matchTag = matchTag,
                                                packagesFilter = packagesFilter,
                                                multiMatch = True,
                                                extendedResults = extendedResults
                                               )
                    if extendedResults:
                        dbpkginfo = (set([((x[0],x[2],x[3],x[4]),dbpkginfo[1]) for x in query_data]),0)
                    else:
                        dbpkginfo = (set([(x,dbpkginfo[1]) for x in query_data]),0)

        if self.xcache and useCache:
            self.Cacher.push(c_hash,dbpkginfo)

        return dbpkginfo

    # expands package sets, and in future something more perhaps
    def packagesExpand(self, packages):
        new_packages = []

        for pkg_id in range(len(packages)):
            package = packages[pkg_id]

            # expand package sets
            if package.startswith(etpConst['packagesetprefix']):
                set_pkgs = sorted(list(self.packageSetExpand(package, raise_exceptions = False)))
                new_packages.extend([x for x in set_pkgs if x not in packages]) # atomMatch below will filter dupies
            else:
                new_packages.append(package)

        return new_packages

    def packageSetExpand(self, package_set, raise_exceptions = True):

        max_recursion_level = 50
        recursion_level = 0

        def do_expand(myset, recursion_level, max_recursion_level):
            recursion_level += 1
            if recursion_level > max_recursion_level:
                raise InvalidPackageSet('InvalidPackageSet: corrupted, too many recursions: %s' % (myset,))
            set_data, set_rc = self.packageSetMatch(myset[len(etpConst['packagesetprefix']):])
            if not set_rc:
                raise InvalidPackageSet('InvalidPackageSet: not found: %s' % (myset,))
            (set_from, package_set, mydata,) = set_data

            mypkgs = set()
            for fset in mydata: # recursively
                if fset.startswith(etpConst['packagesetprefix']):
                    mypkgs |= do_expand(fset, recursion_level, max_recursion_level)
                else:
                    mypkgs.add(fset)

            return mypkgs

        if not package_set.startswith(etpConst['packagesetprefix']):
            package_set = "%s%s" % (etpConst['packagesetprefix'],package_set,)

        try:
            mylist = do_expand(package_set, recursion_level, max_recursion_level)
        except InvalidPackageSet:
            if raise_exceptions: raise
            mylist = set()

        return mylist

    def packageSetList(self, server_repos = [], serverInstance = None, matchRepo = None):
        return self.packageSetMatch('', matchRepo = matchRepo, server_repos = server_repos, serverInstance = serverInstance, search = True)[0]

    def packageSetSearch(self, package_set, server_repos = [], serverInstance = None, matchRepo = None):
        # search support
        if package_set == '*': package_set = ''
        return self.packageSetMatch(package_set, matchRepo = matchRepo, server_repos = server_repos, serverInstance = serverInstance, search = True)[0]

    def __package_set_match_open_db(self, repoid, server_inst):
        if server_inst != None:
            dbconn = server_inst.openServerDatabase(just_reading = True, repo = repoid)
        else:
            dbconn = self.openRepositoryDatabase(repoid)
        return dbconn

    def packageSetMatch(self, package_set, multiMatch = False, matchRepo = None, server_repos = [], serverInstance = None, search = False):

        # support match in repository from shell
        # set@repo1,repo2,repo3
        package_set, repos = self.entropyTools.dep_get_match_in_repos(package_set)
        if (matchRepo == None) and (repos != None):
            matchRepo = repos

        if server_repos:
            if not serverInstance:
                t = _("server_repos needs serverInstance")
                raise IncorrectParameter("IncorrectParameter: %s" % (t,))
            valid_repos = server_repos[:]
        else:
            valid_repos = self.validRepositories

        if matchRepo and (type(matchRepo) in (list,tuple,set)):
            valid_repos = list(matchRepo)

        # if we search, we return all the matches available
        if search: multiMatch = True

        set_data = []

        while 1:

            # check inside SystemSettings
            if not server_repos:
                if search:
                    mysets = [x for x in self.SystemSettings['system_package_sets'].keys() if (x.find(package_set) != -1)]
                    for myset in mysets:
                        mydata = self.SystemSettings['system_package_sets'].get(myset)
                        set_data.append((etpConst['userpackagesetsid'], unicode(myset), mydata.copy(),))
                else:
                    mydata = self.SystemSettings['system_package_sets'].get(package_set)
                    if mydata != None:
                        set_data.append((etpConst['userpackagesetsid'], unicode(package_set), mydata,))
                        if not multiMatch: break

            for repoid in valid_repos:
                dbconn = self.__package_set_match_open_db(repoid, serverInstance)
                if search:
                    mysets = dbconn.searchSets(package_set)
                    for myset in mysets:
                        mydata = dbconn.retrievePackageSet(myset)
                        set_data.append((repoid, myset, mydata.copy(),))
                else:
                    mydata = dbconn.retrievePackageSet(package_set)
                    if mydata: set_data.append((repoid, package_set, mydata,))
                    if not multiMatch: break

            break

        if not set_data: return (),False
        if multiMatch: return set_data,True
        return set_data.pop(0),True

    def repository_move_clear_cache(self, repoid = None):
        self.clear_dump_cache(etpCache['world_available'])
        self.clear_dump_cache(etpCache['world_update'])
        self.clear_dump_cache(etpCache['check_package_update'])
        self.clear_dump_cache(etpCache['filter_satisfied_deps'])
        self.clear_dump_cache(self.atomMatchCacheKey)
        self.clear_dump_cache(etpCache['dep_tree'])
        if repoid != None:
            self.clear_dump_cache("%s/%s%s/" % (etpCache['dbMatch'],etpConst['dbnamerepoprefix'],repoid,))
            self.clear_dump_cache("%s/%s%s/" % (etpCache['dbSearch'],etpConst['dbnamerepoprefix'],repoid,))


    def addRepository(self, repodata):
        # update etpRepositories
        try:
            etpRepositories[repodata['repoid']] = {}
            etpRepositories[repodata['repoid']]['description'] = repodata['description']
            etpRepositories[repodata['repoid']]['configprotect'] = None
            etpRepositories[repodata['repoid']]['configprotectmask'] = None
        except KeyError:
            t = _("repodata dictionary is corrupted")
            raise InvalidData("InvalidData: %s" % (t,))

        if repodata['repoid'].endswith(etpConst['packagesext']) or repodata.get('in_memory'): # dynamic repository
            try:
                # no need # etpRepositories[repodata['repoid']]['plain_packages'] = repodata['plain_packages'][:]
                etpRepositories[repodata['repoid']]['packages'] = repodata['packages'][:]
                smart_package = repodata.get('smartpackage')
                if smart_package != None: etpRepositories[repodata['repoid']]['smartpackage'] = smart_package
                etpRepositories[repodata['repoid']]['dbpath'] = repodata.get('dbpath')
                etpRepositories[repodata['repoid']]['pkgpath'] = repodata.get('pkgpath')
            except KeyError:
                raise InvalidData("InvalidData: repodata dictionary is corrupted")
            # put at top priority, shift others
            etpRepositoriesOrder.insert(0,repodata['repoid'])
        else:
            # XXX it's boring to keep this in sync with entropyConstants stuff, solutions?
            etpRepositories[repodata['repoid']]['plain_packages'] = repodata['plain_packages'][:]
            etpRepositories[repodata['repoid']]['packages'] = [x+"/"+etpConst['product'] for x in repodata['plain_packages']]
            etpRepositories[repodata['repoid']]['plain_database'] = repodata['plain_database']
            etpRepositories[repodata['repoid']]['database'] = repodata['plain_database'] + \
                "/" + etpConst['product'] + "/database/" + etpConst['currentarch'] + "/" + etpConst['branch']
            if not repodata['dbcformat'] in etpConst['etpdatabasesupportedcformats']:
                repodata['dbcformat'] = etpConst['etpdatabasesupportedcformats'][0]
            etpRepositories[repodata['repoid']]['dbcformat'] = repodata['dbcformat']
            etpRepositories[repodata['repoid']]['dbpath'] = etpConst['etpdatabaseclientdir'] + \
                "/" + repodata['repoid'] + "/" + etpConst['product'] + "/" + etpConst['currentarch']  + "/" + etpConst['branch']
            # set dbrevision
            myrev = self.get_repository_revision(repodata['repoid'])
            if myrev == -1:
                myrev = 0
            etpRepositories[repodata['repoid']]['dbrevision'] = str(myrev)
            if repodata.has_key("position"):
                etpRepositoriesOrder.insert(repodata['position'],repodata['repoid'])
            else:
                etpRepositoriesOrder.append(repodata['repoid'])
            if not repodata.has_key("service_port"):
                repodata['service_port'] = int(etpConst['socket_service']['port'])
            if not repodata.has_key("ssl_service_port"):
                repodata['ssl_service_port'] = int(etpConst['socket_service']['ssl_port'])
            etpRepositories[repodata['repoid']]['service_port'] = repodata['service_port']
            etpRepositories[repodata['repoid']]['ssl_service_port'] = repodata['ssl_service_port']
            self.repository_move_clear_cache(repodata['repoid'])
            # save new etpRepositories to file
            self.entropyTools.saveRepositorySettings(repodata)
            self.reload_constants()
        self.validate_repositories()

    def removeRepository(self, repoid, disable = False):

        # ensure that all dbs are closed
        self.closeAllRepositoryDatabases()

        done = False
        if etpRepositories.has_key(repoid):
            del etpRepositories[repoid]
            done = True

        if etpRepositoriesExcluded.has_key(repoid):
            del etpRepositoriesExcluded[repoid]
            done = True

        if done:

            if repoid in etpRepositoriesOrder:
                etpRepositoriesOrder.remove(repoid)

            self.repository_move_clear_cache(repoid)
            # save new etpRepositories to file
            repodata = {}
            repodata['repoid'] = repoid
            if disable:
                self.entropyTools.saveRepositorySettings(repodata, disable = True)
            else:
                self.entropyTools.saveRepositorySettings(repodata, remove = True)
            self.reload_constants()

        self.validate_repositories()

    def shiftRepository(self, repoid, toidx):
        # update etpRepositoriesOrder
        etpRepositoriesOrder.remove(repoid)
        etpRepositoriesOrder.insert(toidx,repoid)
        self.entropyTools.writeOrderedRepositoriesEntries()
        self.reload_constants()
        self.repository_move_clear_cache(repoid)
        self.validate_repositories()

    def enableRepository(self, repoid):
        self.repository_move_clear_cache(repoid)
        # save new etpRepositories to file
        repodata = {}
        repodata['repoid'] = repoid
        self.entropyTools.saveRepositorySettings(repodata, enable = True)
        self.reload_constants()
        self.validate_repositories()

    def disableRepository(self, repoid):
        # update etpRepositories
        done = False
        try:
            del etpRepositories[repoid]
            done = True
        except:
            pass

        if done:
            try:
                etpRepositoriesOrder.remove(repoid)
            except:
                pass
            # it's not vital to reset etpRepositoriesOrder counters

            self.repository_move_clear_cache(repoid)
            # save new etpRepositories to file
            repodata = {}
            repodata['repoid'] = repoid
            self.entropyTools.saveRepositorySettings(repodata, disable = True)
            self.reload_constants()
        self.validate_repositories()

    def get_unsatisfied_dependencies(self, dependencies, deep_deps = False, depcache = None):

        if self.xcache:
            c_data = sorted(dependencies)
            client_checksum = self.clientDbconn.database_checksum()
            c_hash = hash("%s|%s|%s" % (c_data,deep_deps,client_checksum,))
            c_hash = "%s%s" % (etpCache['filter_satisfied_deps'],c_hash,)
            cached = self.dumpTools.loadobj(c_hash)
            if cached != None: return cached

        if not isinstance(depcache,dict):
            depcache = {}

        cdb_am = self.clientDbconn.atomMatch
        am = self.atomMatch
        open_repo = self.openRepositoryDatabase
        intf_error = self.dbapi2.InterfaceError
        cdb_getversioning = self.clientDbconn.getVersioningData
        #cdb_retrieveneededraw = self.clientDbconn.retrieveNeededRaw
        etp_cmp = self.entropyTools.entropyCompareVersions
        etp_get_rev = self.entropyTools.dep_get_entropy_revision
        #do_needed_check = False

        def fm_dep(dependency):

            cached = depcache.get(dependency)
            if cached != None: return cached

            ### conflict
            if dependency.startswith("!"):
                idpackage,rc = cdb_am(dependency[1:])
                if idpackage != -1:
                    depcache[dependency] = dependency
                    return dependency
                depcache[dependency] = 0
                return 0

            c_id,c_rc = cdb_am(dependency)
            if c_id == -1:
                depcache[dependency] = dependency
                return dependency

            #if not deep_deps and not do_needed_check:
            #    depcache[dependency] = 0
            #    return 0

            r_id,r_repo = am(dependency)
            if r_id == -1:
                depcache[dependency] = dependency
                return dependency

            #if do_needed_check:
            #    dbconn = open_repo(r_repo)
            #    installed_needed = cdb_retrieveneededraw(c_id)
            #    repo_needed = dbconn.retrieveNeededRaw(r_id)
            #    if installed_needed != repo_needed:
            #        return dependency
            #    #elif not deep_deps:
            #    #    return 0

            dbconn = open_repo(r_repo)
            try:
                repo_pkgver, repo_pkgtag, repo_pkgrev = dbconn.getVersioningData(r_id)
            except (intf_error,TypeError,):
                # package entry is broken
                return dependency

            try:
                installedVer, installedTag, installedRev = cdb_getversioning(c_id)
            except TypeError: # corrupted entry?
                installedVer = "0"
                installedTag = ''
                installedRev = 0

            # support for app-foo/foo-123~-1
            # -1 revision means, always pull the latest
            do_deep = deep_deps
            if not do_deep:
                string_rev = etp_get_rev(dependency)
                if string_rev == -1:
                    do_deep = True

            vcmp = etp_cmp((repo_pkgver,repo_pkgtag,repo_pkgrev,), (installedVer,installedTag,installedRev,))
            if vcmp != 0:
                if not do_deep and ((repo_pkgver,repo_pkgtag,) == (installedVer,installedTag,)) and (repo_pkgrev != installedRev):
                    depcache[dependency] = 0
                    return 0
                depcache[dependency] = dependency
                return dependency
            depcache[dependency] = 0
            return 0

        unsatisfied = map(fm_dep,dependencies)
        unsatisfied = set([x for x in unsatisfied if x != 0])

        if self.xcache:
            self.Cacher.push(c_hash,unsatisfied)

        return unsatisfied

    def get_masked_package_reason(self, match):
        idpackage, repoid = match
        dbconn = self.openRepositoryDatabase(repoid)
        idpackage, idreason = dbconn.idpackageValidator(idpackage)
        masked = False
        if idpackage == -1: masked = True
        return masked, idreason, self.SystemSettings['pkg_masking_reasons'].get(idreason)

    def get_masked_packages_tree(self, match, atoms = False, flat = False, matchfilter = None):

        if not isinstance(matchfilter,set):
            matchfilter = set()

        maskedtree = {}
        mybuffer = Lifo()
        depcache = set()
        treelevel = -1

        match_id, match_repo = match

        mydbconn = self.openRepositoryDatabase(match_repo)
        myatom = mydbconn.retrieveAtom(match_id)
        idpackage, idreason = mydbconn.idpackageValidator(match_id)
        if idpackage == -1:
            treelevel += 1
            if atoms:
                mydict = {myatom: idreason,}
            else:
                mydict = {match: idreason,}
            if flat:
                maskedtree.update(mydict)
            else:
                maskedtree[treelevel] = mydict

        mydeps = mydbconn.retrieveDependencies(match_id)
        for mydep in mydeps: mybuffer.push(mydep)
        mydep = mybuffer.pop()

        open_db = self.openRepositoryDatabase
        am = self.atomMatch
        while mydep:

            if mydep in depcache:
                mydep = mybuffer.pop()
                continue
            depcache.add(mydep)

            idpackage, repoid = am(mydep)
            if (idpackage, repoid) in matchfilter:
                mydep = mybuffer.pop()
                continue

            if idpackage != -1:
                # doing even here because atomMatch with packagesFilter = False can pull
                # something different
                matchfilter.add((idpackage, repoid))

            # collect masked
            if idpackage == -1:
                idpackage, repoid = am(mydep, packagesFilter = False)
                if idpackage != -1:
                    treelevel += 1
                    if not maskedtree.has_key(treelevel) and not flat:
                        maskedtree[treelevel] = {}
                    dbconn = open_db(repoid)
                    vidpackage, idreason = dbconn.idpackageValidator(idpackage)
                    if atoms:
                        mydict = {dbconn.retrieveAtom(idpackage): idreason}
                    else:
                        mydict = {(idpackage,repoid): idreason}
                    if flat: maskedtree.update(mydict)
                    else: maskedtree[treelevel].update(mydict)

            # push its dep into the buffer
            if idpackage != -1:
                matchfilter.add((idpackage, repoid))
                dbconn = open_db(repoid)
                owndeps = dbconn.retrieveDependencies(idpackage)
                for owndep in owndeps:
                    mybuffer.push(owndep)

            mydep = mybuffer.pop()

        return maskedtree


    def generate_dependency_tree(self, atomInfo, empty_deps = False, deep_deps = False, matchfilter = None, flat = False, filter_unsat_cache = None, treecache = None, keyslotcache = None):

        if not isinstance(matchfilter,set):
            matchfilter = set()
        if not isinstance(filter_unsat_cache,dict):
            filter_unsat_cache = {}
        if not isinstance(treecache,set):
            treecache = set()
        if not isinstance(keyslotcache,set):
            keyslotcache = set()

        mydbconn = self.openRepositoryDatabase(atomInfo[1])
        myatom = mydbconn.retrieveAtom(atomInfo[0])

        # caches
        # special events
        deps_not_found = set()
        conflicts = set()

        mydep = (1,myatom)
        mybuffer = Lifo()
        deptree = set()
        if atomInfo not in matchfilter:
            deptree.add((1,atomInfo))

        virgin = True
        open_repo = self.openRepositoryDatabase
        atom_match = self.atomMatch
        cdb_atom_match = self.clientDbconn.atomMatch
        lookup_conflict_replacement = self._lookup_conflict_replacement
        lookup_library_breakages = self._lookup_library_breakages
        lookup_inverse_dependencies = self._lookup_inverse_dependencies
        get_unsatisfied_deps = self.get_unsatisfied_dependencies

        def my_dep_filter(x):
            if x in treecache: return False
            if tuple(x.split(":")) in keyslotcache: return False
            return True

        while mydep:

            dep_level, dep_atom = mydep

            # already analyzed in this call
            if dep_atom in treecache:
                mydep = mybuffer.pop()
                continue
            treecache.add(dep_atom)

            if dep_atom == None: # corrupted entry
                mydep = mybuffer.pop()
                continue

            # conflicts
            if dep_atom[0] == "!":
                c_idpackage, xst = cdb_atom_match(dep_atom[1:])
                if c_idpackage != -1:
                    myreplacement = lookup_conflict_replacement(dep_atom[1:], c_idpackage, deep_deps = deep_deps)
                    if (myreplacement != None) and (myreplacement not in treecache):
                        mybuffer.push((dep_level+1,myreplacement))
                    else:
                        conflicts.add(c_idpackage)
                mydep = mybuffer.pop()
                continue

            # atom found?
            if virgin:
                virgin = False
                m_idpackage, m_repo = atomInfo
                dbconn = open_repo(m_repo)
                myidpackage, idreason = dbconn.idpackageValidator(m_idpackage)
                if myidpackage == -1: m_idpackage = -1
            else:
                m_idpackage, m_repo = atom_match(dep_atom)
            if m_idpackage == -1:
                deps_not_found.add(dep_atom)
                mydep = mybuffer.pop()
                continue

            # check if atom has been already pulled in
            matchdb = open_repo(m_repo)
            matchatom = matchdb.retrieveAtom(m_idpackage)
            matchkey, matchslot = matchdb.retrieveKeySlot(m_idpackage)
            if (dep_atom != matchatom) and (matchatom in treecache):
                mydep = mybuffer.pop()
                continue

            treecache.add(matchatom)

            # check if key + slot has been already pulled in
            if (matchslot,matchkey) in keyslotcache:
                mydep = mybuffer.pop()
                continue
            else:
                keyslotcache.add((matchslot,matchkey))

            match = (m_idpackage, m_repo,)
            # result already analyzed?
            if match in matchfilter:
                mydep = mybuffer.pop()
                continue

            # already analyzed by the calling function
            if match in matchfilter:
                mydep = mybuffer.pop()
                continue
            matchfilter.add(match)

            treedepth = dep_level+1

            # all checks passed, well done
            matchfilter.add(match)
            deptree.add((dep_level,match)) # add match

            # extra hooks
            cm_idpackage, cm_result = cdb_atom_match(matchkey, matchSlot = matchslot)
            if cm_idpackage != -1:
                broken_atoms = lookup_library_breakages(match, (cm_idpackage, cm_result,), deep_deps = deep_deps)
                inverse_deps = lookup_inverse_dependencies(match, (cm_idpackage, cm_result,))
                if inverse_deps:
                    deptree.remove((dep_level,match))
                    for ikey,islot in inverse_deps:
                        iks_str = '%s:%s' % (ikey,islot,)
                        if ((ikey,islot) not in keyslotcache) and (iks_str not in treecache):
                            mybuffer.push((dep_level,iks_str))
                            keyslotcache.add((ikey,islot))
                    deptree.add((treedepth,match))
                    treedepth += 1
                for x in broken_atoms:
                    if (tuple(x.split(":")) not in keyslotcache) and (x not in treecache):
                        mybuffer.push((treedepth,x))

            myundeps = filter(my_dep_filter,matchdb.retrieveDependenciesList(m_idpackage))
            if not empty_deps:
                myundeps = filter(my_dep_filter,get_unsatisfied_deps(myundeps, deep_deps, depcache = filter_unsat_cache))

            # PDEPENDs support
            if myundeps:
                post_deps = [x for x in matchdb.retrievePostDependencies(m_idpackage) if x in myundeps]
                myundeps = [x for x in myundeps if x not in post_deps]
                for x in post_deps: mybuffer.push((-1,x)) # always after the package itself

            for x in myundeps: mybuffer.push((treedepth,x))
            mydep = mybuffer.pop()

        if deps_not_found:
            return list(deps_not_found),-2

        if flat: return [x[1] for x in deptree],0

        newdeptree = {}
        for key,item in deptree:
            if key not in newdeptree: newdeptree[key] = set()
            newdeptree[key].add(item)
        # conflicts
        newdeptree[0] = conflicts

        return newdeptree,0 # note: newtree[0] contains possible conflicts


    def _lookup_system_mask_repository_deps(self):

        data = self.SystemSettings['repos_system_mask']
        if not data: return []
        mydata = []
        cached_items = set()
        for atom in data:
            mymatch = self.atomMatch(atom)
            if mymatch[0] == -1: # ignore missing ones intentionally
                continue
            if mymatch in cached_items:
                continue
            if mymatch not in mydata:
                # check if not found
                myaction = self.get_package_action(mymatch)
                # only if the package is not installed
                if myaction == 1: mydata.append(mymatch)
            cached_items.add(mymatch)
        return mydata

    def _lookup_conflict_replacement(self, conflict_atom, client_idpackage, deep_deps):
        if self.entropyTools.isjustname(conflict_atom):
            return None
        conflict_match = self.atomMatch(conflict_atom)
        mykey, myslot = self.clientDbconn.retrieveKeySlot(client_idpackage)
        new_match = self.atomMatch(mykey, matchSlot = myslot)
        if (conflict_match == new_match) or (new_match[1] == 1):
            return None
        action = self.get_package_action(new_match)
        if (action == 0) and (not deep_deps):
            return None
        return "%s:%s" % (mykey,myslot,)

    def _lookup_inverse_dependencies(self, match, clientmatch):

        cmpstat = self.get_package_action(match)
        if cmpstat == 0: return set()

        keyslots = set()
        mydepends = self.clientDbconn.retrieveDepends(clientmatch[0])
        am = self.atomMatch
        cdb_rdeps = self.clientDbconn.retrieveDependencies
        cdb_rks = self.clientDbconn.retrieveKeySlot
        gpa = self.get_package_action
        keyslots_cache = set()
        match_cache = {}

        for idpackage in mydepends:
            try:
                key, slot = cdb_rks(idpackage)
            except TypeError:
                continue
            if (key,slot) in keyslots_cache: continue
            keyslots_cache.add((key,slot))
            if (key,slot) in keyslots: continue
            # grab its deps
            mydeps = cdb_rdeps(idpackage)
            found = False
            for mydep in mydeps:
                mymatch = match_cache.get(mydep, 0)
                if mymatch == 0:
                    mymatch = am(mydep)
                    match_cache[mydep] = mymatch
                if mymatch == match:
                    found = True
                    break
            if not found:
                mymatch = am(key, matchSlot = slot)
                if mymatch[0] == -1: continue
                cmpstat = gpa(mymatch)
                if cmpstat == 0: continue
                keyslots.add((key,slot))

        return keyslots

    def _lookup_library_breakages(self, match, clientmatch, deep_deps = False):

        # there is no need to update this cache when "match" will be installed, because at that point
        # clientmatch[0] will differ.
        c_hash = "%s|%s|%s" % (hash(tuple(match)),hash(deep_deps),hash(tuple(clientmatch)),)
        c_hash = "%s%s" % (etpCache['library_breakage'],hash(c_hash),)
        if self.xcache:
            cached = self.Cacher.pop(c_hash)
            if cached != None: return cached

        # these should be pulled in before
        repo_atoms = set()
        # these can be pulled in after
        client_atoms = set()

        matchdb = self.openRepositoryDatabase(match[1])
        reponeeded = matchdb.retrieveNeeded(match[0], extended = True, format = True)
        clientneeded = self.clientDbconn.retrieveNeeded(clientmatch[0], extended = True, format = True)
        repo_split = [x.split(".so")[0] for x in reponeeded]
        client_split = [x.split(".so")[0] for x in clientneeded]
        client_side = [x for x in clientneeded if (x not in reponeeded) and (x.split(".so")[0] in repo_split)]
        repo_side = [x for x in reponeeded if (x not in clientneeded) and (x.split(".so")[0] in client_split)]
        del clientneeded,client_split,repo_split

        # all the packages in client_side should be pulled in and updated
        client_idpackages = set()
        for needed in client_side: client_idpackages |= self.clientDbconn.searchNeeded(needed)

        client_keyslots = set()
        def mymf(idpackage):
            if idpackage == clientmatch[0]: return 0
            return self.clientDbconn.retrieveKeySlot(idpackage)
        client_keyslots = set([x for x in map(mymf,client_idpackages) if x != 0])

        # all the packages in repo_side should be pulled in too
        repodata = {}
        for needed in repo_side:
            repodata[needed] = reponeeded[needed]
        del repo_side,reponeeded

        repo_dependencies = matchdb.retrieveDependencies(match[0])
        matched_deps = set()
        matched_repos = set()
        for dependency in repo_dependencies:
            depmatch = self.atomMatch(dependency)
            if depmatch[0] == -1:
                continue
            matched_repos.add(depmatch[1])
            matched_deps.add(depmatch)

        matched_repos = [x for x in etpRepositoriesOrder if x in matched_repos]
        found_matches = set()
        for needed in repodata:
            for myrepo in matched_repos:
                mydbc = self.openRepositoryDatabase(myrepo)
                solved_needed = mydbc.resolveNeeded(needed, elfclass = repodata[needed])
                found = False
                for idpackage,myfile in solved_needed:
                    x = (idpackage,myrepo)
                    if x in matched_deps:
                        found_matches.add(x)
                        found = True
                        break
                if found:
                    break

        for idpackage,repo in found_matches:
            if not deep_deps:
                cmpstat = self.get_package_action((idpackage,repo))
                if cmpstat == 0:
                    continue
            mydbc = self.openRepositoryDatabase(repo)
            repo_atoms.add(mydbc.retrieveAtom(idpackage))

        for key, slot in client_keyslots:
            idpackage, repo = self.atomMatch(key, matchSlot = slot)
            if idpackage == -1:
                continue
            if not deep_deps:
                cmpstat = self.get_package_action((idpackage, repo))
                if cmpstat == 0:
                    continue
            mydbc = self.openRepositoryDatabase(repo)
            client_atoms.add(mydbc.retrieveAtom(idpackage))

        client_atoms |= repo_atoms

        if self.xcache:
            self.Cacher.push(c_hash,client_atoms)

        return client_atoms


    def get_required_packages(self, matched_atoms, empty_deps = False, deep_deps = False, quiet = False):

        c_hash = "%s%s" % (etpCache['dep_tree'],hash("%s|%s|%s|%s" % (
            hash(frozenset(sorted(matched_atoms))),hash(empty_deps),
            hash(deep_deps),self.clientDbconn.database_checksum(),
        )),)
        if self.xcache:
            cached = self.Cacher.pop(c_hash)
            if cached != None: return cached

        deptree = {}
        deptree[0] = set()

        atomlen = len(matched_atoms); count = 0
        error_generated = 0
        error_tree = set()

        # check if there are repositories needing some mandatory packages
        forced_matches = self._lookup_system_mask_repository_deps()
        if forced_matches:
            if isinstance(matched_atoms, list):
                matched_atoms = forced_matches + [x for x in matched_atoms if x not in forced_matches]
            elif isinstance(matched_atoms, set): # we cannot do anything about the order here
                matched_atoms |= set(forced_matches)

        sort_dep_text = _("Sorting dependencies")
        filter_unsat_cache = {}
        treecache = set()
        keyslotcache = set()
        matchfilter = set()
        for atomInfo in matched_atoms:

            if not quiet:
                count += 1
                if (count%10 == 0) or (count == atomlen) or (count == 1):
                    self.updateProgress(sort_dep_text, importance = 0, type = "info", back = True, header = ":: ", footer = " ::", percent = True, count = (count,atomlen))

            if atomInfo in matchfilter: continue
            newtree, result = self.generate_dependency_tree(
                atomInfo, empty_deps, deep_deps,
                matchfilter = matchfilter, filter_unsat_cache = filter_unsat_cache, treecache = treecache,
                keyslotcache = keyslotcache
            )

            if result == -2: # deps not found
                error_generated = -2
                error_tree |= set(newtree) # it is a list, we convert it into set and update error_tree
            elif (result != 0):
                return newtree, result
            elif newtree:
                # add conflicts
                max_parent_key = max(deptree)
                deptree[0] |= newtree.pop(0)
                levelcount = 0
                for mylevel in sorted(newtree.keys(), reverse = True):
                    levelcount += 1
                    deptree[max_parent_key+levelcount] = newtree.get(mylevel)

        if error_generated != 0:
            return error_tree,error_generated

        if self.xcache:
            self.Cacher.push(c_hash,(deptree,0))

        return deptree,0

    def _filter_depends_multimatched_atoms(self, idpackage, depends, monotree):
        remove_depends = set()
        for d_idpackage in depends:
            mydeps = self.clientDbconn.retrieveDependencies(d_idpackage)
            for mydep in mydeps:
                matches, rslt = self.clientDbconn.atomMatch(mydep, multiMatch = True)
                if rslt == 1: continue
                if idpackage in matches and len(matches) > 1:
                    # are all in depends?
                    for mymatch in matches:
                        if mymatch not in depends and mymatch not in monotree:
                            remove_depends.add(d_idpackage)
                            break
        depends -= remove_depends
        return depends


    def generate_depends_tree(self, idpackages, deep = False):

        c_hash = "%s%s" % (etpCache['depends_tree'],hash("%s|%s" % (hash(tuple(sorted(idpackages))),hash(deep),),),)
        if self.xcache:
            cached = self.Cacher.pop(c_hash)
            if cached != None: return cached

        dependscache = set()
        treeview = set(idpackages)
        treelevel = set(idpackages)
        tree = {}
        treedepth = 0 # I start from level 1 because level 0 is idpackages itself
        tree[treedepth] = set(idpackages)
        monotree = set(idpackages) # monodimensional tree

        # check if dependstable is sane before beginning
        self.clientDbconn.retrieveDepends(idpackages[0])
        count = 0

        rem_dep_text = _("Calculating removable depends of")
        while 1:
            treedepth += 1
            tree[treedepth] = set()
            for idpackage in treelevel:

                count += 1
                p_atom = self.clientDbconn.retrieveAtom(idpackage)
                self.updateProgress(
                    blue(rem_dep_text + " %s" % (red(p_atom),)),
                    importance = 0,
                    type = "info",
                    back = True,
                    header = '|/-\\'[count%4]+" "
                )

                systempkg = not self.validatePackageRemoval(idpackage)
                if (idpackage in dependscache) or systempkg:
                    if idpackage in treeview:
                        treeview.remove(idpackage)
                    continue

                # obtain its depends
                depends = self.clientDbconn.retrieveDepends(idpackage)
                # filter already satisfied ones
                depends = set([x for x in depends if x not in monotree])
                depends = set([x for x in depends if self.validatePackageRemoval(x)])
                if depends:
                    depends = self._filter_depends_multimatched_atoms(idpackage, depends, monotree)
                if depends: # something depends on idpackage
                    tree[treedepth] |= depends
                    monotree |= depends
                    treeview |= depends
                elif deep: # if deep, grab its dependencies and check

                    mydeps = set()
                    for x in self.clientDbconn.retrieveDependencies(idpackage):
                        match = self.clientDbconn.atomMatch(x)
                        if match[0] != -1:
                            mydeps.add(match[0])

                    # now filter them
                    mydeps = [x for x in mydeps if x not in monotree and not (self.clientDbconn.isSystemPackage(x) or self.is_installed_idpackage_in_system_mask(x) )]
                    for x in mydeps:
                        mydepends = self.clientDbconn.retrieveDepends(x)
                        mydepends -= set([y for y in mydepends if y not in monotree])
                        if not mydepends:
                            tree[treedepth].add(x)
                            monotree.add(x)
                            treeview.add(x)

                dependscache.add(idpackage)
                if idpackage in treeview:
                    treeview.remove(idpackage)

            treelevel = treeview.copy()
            if not treelevel:
                if not tree[treedepth]:
                    del tree[treedepth] # probably the last one is empty then
                break

        # now filter newtree
        for count in sorted(tree.keys(), reverse = True):
            x = 0
            while x < count:
                tree[x] -= tree[count]
                x += 1

        if self.xcache:
            self.Cacher.push(c_hash,(tree,0))
        return tree,0 # treeview is used to show deps while tree is used to run the dependency code.

    def list_repo_categories(self):
        categories = set()
        for repo in self.validRepositories:
            dbconn = self.openRepositoryDatabase(repo)
            catsdata = dbconn.listAllCategories()
            categories.update(set([x[1] for x in catsdata]))
        return categories

    def list_repo_packages_in_category(self, category):
        pkg_matches = []
        for repo in self.validRepositories:
            dbconn = self.openRepositoryDatabase(repo)
            catsdata = dbconn.searchPackagesByCategory(category, branch = etpConst['branch'])
            pkg_matches.extend([(x[1],repo,) for x in catsdata if (x[1],repo,) not in pkg_matches])
        return pkg_matches

    def get_category_description_data(self, category):

        data = {}
        for repo in self.validRepositories:
            try:
                dbconn = self.openRepositoryDatabase(repo)
            except RepositoryError:
                continue
            try:
                data = dbconn.retrieveCategoryDescription(category)
            except (self.dbapi2.OperationalError, self.dbapi2.IntegrityError,):
                continue
            if data: break

        return data

    def list_installed_packages_in_category(self, category):
        pkg_matches = set([x[1] for x in self.clientDbconn.searchPackagesByCategory(category)])
        return pkg_matches

    def all_repositories_checksum(self):
        sum_hashes = ''
        for repo in self.validRepositories:
            try:
                dbconn = self.openRepositoryDatabase(repo)
            except (RepositoryError):
                continue # repo not available
            try:
                sum_hashes += dbconn.database_checksum()
            except self.dbapi2.OperationalError:
                pass
        return sum_hashes

    def get_available_packages_chash(self, branch):
        # client digest not needed, cache is kept updated
        return str(hash("%s%s%s" % (self.all_repositories_checksum(),branch,self.validRepositories,)))

    def get_available_packages_cache(self, branch = etpConst['branch'], myhash = None):
        if myhash == None: myhash = self.get_available_packages_chash(branch)
        return self.Cacher.pop("%s%s" % (etpCache['world_available'],myhash))

    # this function searches all the not installed packages available in the repositories
    def calculate_available_packages(self, use_cache = True):

        c_hash = self.get_available_packages_chash(etpConst['branch'])

        if use_cache and self.xcache:
            cached = self.get_available_packages_cache(myhash = c_hash)
            if cached != None:
                return cached

        available = []
        self.setTotalCycles(len(self.validRepositories))
        avail_dep_text = _("Calculating available packages for")
        for repo in self.validRepositories:
            try:
                dbconn = self.openRepositoryDatabase(repo)
                dbconn.validateDatabase()
            except (RepositoryError,SystemDatabaseError):
                self.cycleDone()
                continue
            idpackages = [  x for x in dbconn.listAllIdpackages(branch = etpConst['branch'], branch_operator = "<=", order_by = 'atom') \
                            if dbconn.idpackageValidator(x)[0] != -1  ]
            count = 0
            maxlen = len(idpackages)
            myavailable = []
            do_break = False
            for idpackage in idpackages:
                if do_break:
                    break
                count += 1
                if (count % 10 == 0) or (count == 1) or (count == maxlen):
                    self.updateProgress(
                        avail_dep_text + " %s" % (repo,),
                        importance = 0,
                        type = "info",
                        back = True,
                        header = "::",
                        count = (count,maxlen),
                        percent = True,
                        footer = " ::"
                    )
                # get key + slot
                try:
                    key, slot = dbconn.retrieveKeySlot(idpackage)
                    matches = self.clientDbconn.searchKeySlot(key, slot)
                except (self.dbapi2.DatabaseError,self.dbapi2.IntegrityError,self.dbapi2.OperationalError,):
                    self.cycleDone()
                    do_break = True
                    continue
                if not matches: myavailable.append((idpackage,repo))
            available += myavailable[:]
            self.cycleDone()

        if self.xcache:
            self.Cacher.push("%s%s" % (etpCache['world_available'],c_hash),available)
        return available

    def get_world_update_cache(self, empty_deps, branch = etpConst['branch'], db_digest = None, ignore_spm_downgrades = False):
        if self.xcache:
            if db_digest == None: db_digest = self.all_repositories_checksum()
            c_hash = "%s%s" % (etpCache['world_update'],self.get_world_update_cache_hash(db_digest, empty_deps, branch, ignore_spm_downgrades),)
            disk_cache = self.Cacher.pop(c_hash)
            if disk_cache != None:
                try:
                    return disk_cache['r']
                except (KeyError, TypeError):
                    return None

    def get_world_update_cache_hash(self, db_digest, empty_deps, branch, ignore_spm_downgrades):
        c_hash = "%s|%s|%s|%s|%s|%s" % ( 
            db_digest,empty_deps,self.validRepositories,
            etpRepositoriesOrder, branch, ignore_spm_downgrades,
        )
        return str(hash(c_hash))

    def calculate_world_updates(
            self,
            empty_deps = False,
            branch = etpConst['branch'],
            ignore_spm_downgrades = etpConst['spm']['ignore-spm-downgrades'],
            use_cache = True
        ):

        db_digest = self.all_repositories_checksum()
        if use_cache and self.xcache:
            cached = self.get_world_update_cache(empty_deps = empty_deps, branch = branch, db_digest = db_digest, ignore_spm_downgrades = ignore_spm_downgrades)
            if cached != None: return cached

        update = []
        remove = []
        fine = []

        # get all the installed packages
        idpackages = self.clientDbconn.listAllIdpackages(order_by = 'atom')
        maxlen = len(idpackages)
        count = 0
        mytxt = _("Calculating world packages")
        for idpackage in idpackages:

            count += 1
            if (count%10 == 0) or (count == maxlen) or (count == 1):
                self.updateProgress(
                    mytxt,
                    importance = 0,
                    type = "info",
                    back = True,
                    header = ":: ",
                    count = (count,maxlen),
                    percent = True,
                    footer = " ::"
                )

            mystrictdata = self.clientDbconn.getStrictData(idpackage)
            # check against broken entries, or removed during iteration
            if mystrictdata == None:
                continue
            use_match_cache = True
            do_continue = False
            while 1:
                try:
                    match = self.atomMatch(
                        mystrictdata[0],
                        matchSlot = mystrictdata[1],
                        matchBranches = (branch,),
                        extendedResults = True,
                        useCache = use_match_cache
                    )
                except self.dbapi2.OperationalError:
                    # ouch, but don't crash here
                    do_continue = True
                    break
                try:
                    m_idpackage = match[0][0]
                except TypeError:
                    if not use_match_cache: raise
                    use_match_cache = False
                    continue
                break
            if do_continue: continue
            # now compare
            # version: mystrictdata[2]
            # tag: mystrictdata[3]
            # revision: mystrictdata[4]
            if (m_idpackage != -1):
                repoid = match[1]
                version = match[0][1]
                tag = match[0][2]
                revision = match[0][3]
                if empty_deps:
                    if (m_idpackage,repoid) not in update:
                        update.append((m_idpackage,repoid))
                    continue
                elif (mystrictdata[2] != version):
                    # different versions
                    if (m_idpackage,repoid) not in update:
                        update.append((m_idpackage,repoid))
                    continue
                elif (mystrictdata[3] != tag):
                    # different tags
                    if (m_idpackage,repoid) not in update:
                        update.append((m_idpackage,repoid))
                    continue
                elif (mystrictdata[4] != revision):
                    # different revision
                    if mystrictdata[4] == 9999 and ignore_spm_downgrades:
                        # no difference, we're ignoring revision 9999
                        fine.append(mystrictdata[5])
                        continue
                    else:
                        if (m_idpackage,repoid) not in update:
                            update.append((m_idpackage,repoid))
                        continue
                else:
                    # no difference
                    fine.append(mystrictdata[5])
                    continue

            # don't take action if it's just masked
            maskedresults = self.atomMatch(mystrictdata[0], matchSlot = mystrictdata[1], matchBranches = (branch,), packagesFilter = False)
            if maskedresults[0] == -1:
                remove.append(idpackage)
                # look for packages that would match key with any slot (for eg: gcc, kernel updates)
                matchresults = self.atomMatch(mystrictdata[0], matchBranches = (branch,))
                if matchresults[0] != -1:
                    m_action = self.get_package_action(matchresults)
                    if m_action > 0 and (matchresults not in update):
                        update.append(matchresults)

        if self.xcache:
            c_hash = self.get_world_update_cache_hash(db_digest, empty_deps, branch, ignore_spm_downgrades)
            data = {
                'r': (update, remove, fine,),
                'empty_deps': empty_deps,
            }
            self.Cacher.push("%s%s" % (etpCache['world_update'],c_hash,), data, async = False)

        return update, remove, fine

    def get_match_conflicts(self, match):
        m_id, m_repo = match
        dbconn = self.openRepositoryDatabase(m_repo)
        conflicts = dbconn.retrieveConflicts(m_id)
        found_conflicts = set()
        for conflict in conflicts:
            my_m_id, my_m_rc = self.clientDbconn.atomMatch(conflict)
            if my_m_id != -1:
                # check if the package shares the same slot
                match_data = dbconn.retrieveKeySlot(m_id)
                installed_match_data = self.clientDbconn.retrieveKeySlot(my_m_id)
                if match_data != installed_match_data:
                    found_conflicts.add(my_m_id)
        return found_conflicts

    def is_match_masked(self, match, live_check = True):
        m_id, m_repo = match
        dbconn = self.openRepositoryDatabase(m_repo)
        idpackage, idreason = dbconn.idpackageValidator(m_id, live = live_check)
        if idpackage != -1:
            return False
        return True

    def is_match_masked_by_user(self, match, live_check = True):
        # (query_status,masked?,)
        m_id, m_repo = match
        if m_repo not in self.validRepositories: return False
        dbconn = self.openRepositoryDatabase(m_repo)
        idpackage, idreason = dbconn.idpackageValidator(m_id, live = live_check)
        if idpackage != -1: return False #,False
        myr = self.SystemSettings['pkg_masking_reference']
        user_masks = [myr['user_package_mask'],myr['user_license_mask'],myr['user_live_mask']]
        if idreason in user_masks:
            return True #,True
        return False #,True

    def is_match_unmasked_by_user(self, match, live_check = True):
        # (query_status,unmasked?,)
        m_id, m_repo = match
        if m_repo not in self.validRepositories: return False
        dbconn = self.openRepositoryDatabase(m_repo)
        idpackage, idreason = dbconn.idpackageValidator(m_id, live = live_check)
        if idpackage == -1: return False #,False
        myr = self.SystemSettings['pkg_masking_reference']
        user_masks = [
            myr['user_package_unmask'],myr['user_live_unmask'],myr['user_package_keywords'],
            myr['user_repo_package_keywords_all'], myr['user_repo_package_keywords']
        ]
        if idreason in user_masks:
            return True #,True
        return False #,True

    def mask_match(self, match, method = 'atom', dry_run = False, clean_all_cache = False):
        if self.is_match_masked(match, live_check = False): return True
        methods = {
            'atom': self.mask_match_by_atom,
            'keyslot': self.mask_match_by_keyslot,
        }
        rc = self._mask_unmask_match(match, method, methods, dry_run = dry_run, clean_all_cache = clean_all_cache)
        if dry_run: # inject if done "live"
            self.SystemSettings['live_packagemasking']['unmask_matches'].discard(match)
            self.SystemSettings['live_packagemasking']['mask_matches'].add(match)
        return rc

    def unmask_match(self, match, method = 'atom', dry_run = False, clean_all_cache = False):
        if not self.is_match_masked(match, live_check = False): return True
        methods = {
            'atom': self.unmask_match_by_atom,
            'keyslot': self.unmask_match_by_keyslot,
        }
        rc = self._mask_unmask_match(match, method, methods, dry_run = dry_run, clean_all_cache = clean_all_cache)
        if dry_run: # inject if done "live"
            self.SystemSettings['live_packagemasking']['unmask_matches'].add(match)
            self.SystemSettings['live_packagemasking']['mask_matches'].discard(match)
        return rc

    def _mask_unmask_match(self, match, method, methods_reference, dry_run = False, clean_all_cache = False):

        f = methods_reference.get(method)
        if not callable(f):
            raise IncorrectParameter('IncorrectParameter: %s: %s' % (_("not a valid method"),method,) )

        self.Cacher.sync(wait = True)
        done = f(match, dry_run)
        if done: self.SystemSettings.clear()

        # clear atomMatch cache anyway
        if clean_all_cache and not dry_run:
            self.clear_dump_cache(etpCache['world_available'])
            self.clear_dump_cache(etpCache['world_update'])

        self.clear_dump_cache(etpCache['check_package_update'])
        self.clear_dump_cache(etpCache['filter_satisfied_deps'])
        self.clear_dump_cache(self.atomMatchCacheKey)
        self.clear_dump_cache(etpCache['dep_tree'])
        self.clear_dump_cache("%s/%s%s/" % (etpCache['dbMatch'],etpConst['dbnamerepoprefix'],match[1],))
        self.clear_dump_cache("%s/%s%s/" % (etpCache['dbSearch'],etpConst['dbnamerepoprefix'],match[1],))

        self.package_match_validator_cache.clear()
        return done

    def unmask_match_by_atom(self, match, dry_run = False):
        m_id, m_repo = match
        dbconn = self.openRepositoryDatabase(m_repo)
        atom = dbconn.retrieveAtom(m_id)
        return self.unmask_match_generic(match, atom, dry_run = dry_run)

    def unmask_match_by_keyslot(self, match, dry_run = False):
        m_id, m_repo = match
        dbconn = self.openRepositoryDatabase(m_repo)
        keyslot = "%s:%s" % dbconn.retrieveKeySlot(m_id)
        return self.unmask_match_generic(match, keyslot, dry_run = dry_run)

    def mask_match_by_atom(self, match, dry_run = False):
        m_id, m_repo = match
        dbconn = self.openRepositoryDatabase(m_repo)
        atom = dbconn.retrieveAtom(m_id)
        return self.mask_match_generic(match, atom, dry_run = dry_run)

    def mask_match_by_keyslot(self, match, dry_run = False):
        m_id, m_repo = match
        dbconn = self.openRepositoryDatabase(m_repo)
        keyslot = "%s:%s" % dbconn.retrieveKeySlot(m_id)
        return self.mask_match_generic(match, keyslot, dry_run = dry_run)

    def unmask_match_generic(self, match, keyword, dry_run = False):
        self.clear_match_mask(match, dry_run)
        m_file = self.SystemSettings.etpSettingFiles['unmask']
        return self._mask_unmask_match_generic(keyword, m_file, dry_run = dry_run)

    def mask_match_generic(self, match, keyword, dry_run = False):
        self.clear_match_mask(match, dry_run)
        m_file = self.SystemSettings.etpSettingFiles['mask']
        return self._mask_unmask_match_generic(keyword, m_file, dry_run = dry_run)

    def _mask_unmask_match_generic(self, keyword, m_file, dry_run = False):
        exist = False
        if not os.path.isfile(m_file):
            if not os.access(os.path.dirname(m_file),os.W_OK):
                return False # cannot write
        elif not os.access(m_file, os.W_OK):
            return False
        elif not dry_run:
            exist = True

        if dry_run:
            return True

        content = []
        if exist:
            f = open(m_file,"r")
            content = [x.strip() for x in f.readlines()]
            f.close()
        content.append(keyword)
        m_file_tmp = m_file+".tmp"
        f = open(m_file_tmp,"w")
        for line in content:
            f.write(line+"\n")
        f.flush()
        f.close()
        shutil.move(m_file_tmp,m_file)
        return True

    def clear_match_mask(self, match, dry_run = False):
        masking_list = [self.SystemSettings.etpSettingFiles['mask'],self.SystemSettings.etpSettingFiles['unmask']]
        return self._clear_match_generic(match, masking_list = masking_list, dry_run = dry_run)

    def _clear_match_generic(self, match, masking_list = [], dry_run = False):

        self.SystemSettings['live_packagemasking']['unmask_matches'].discard(match)
        self.SystemSettings['live_packagemasking']['mask_matches'].discard(match)

        if dry_run: return

        for mask_file in masking_list:
            if not (os.path.isfile(mask_file) and os.access(mask_file,os.W_OK)): continue
            f = open(mask_file,"r")
            newf = self.entropyTools.open_buffer()
            line = f.readline()
            while line:
                line = line.strip()
                if line.startswith("#"):
                    newf.write(line+"\n")
                    line = f.readline()
                    continue
                elif not line:
                    newf.write("\n")
                    line = f.readline()
                    continue
                mymatch = self.atomMatch(line, packagesFilter = False)
                if mymatch == match:
                    line = f.readline()
                    continue
                newf.write(line+"\n")
                line = f.readline()
            f.close()
            tmpfile = mask_file+".w_tmp"
            f = open(tmpfile,"w")
            f.write(newf.getvalue())
            f.flush()
            f.close()
            newf.close()
            shutil.move(tmpfile,mask_file)

    def add_user_package_set(self, set_name, set_atoms):

        def _ensure_package_sets_dir():
            sets_dir = etpConst['confsetsdir']
            if not os.path.isdir(sets_dir):
                if os.path.lexists(sets_dir):
                    os.remove(sets_dir)
                os.makedirs(sets_dir,0775)
                const_setup_perms(sets_dir, etpConst['entropygid'])

        try:
            set_name = str(set_name)
        except (UnicodeEncodeError,UnicodeDecodeError,):
            raise InvalidPackageSet("InvalidPackageSet: %s %s" % (set_name,_("must be an ASCII string"),))

        if set_name.startswith(etpConst['packagesetprefix']):
            raise InvalidPackageSet("InvalidPackageSet: %s %s '%s'" % (set_name,_("cannot start with"),etpConst['packagesetprefix'],))
        set_match, rc = self.packageSetMatch(set_name)
        if rc: return -1,_("Name already taken")

        _ensure_package_sets_dir()
        set_file = os.path.join(etpConst['confsetsdir'],set_name)
        if os.path.isfile(set_file) and os.access(set_file,os.W_OK):
            try:
                os.remove(set_file)
            except OSError:
                return -2,_("Cannot remove the old element")
        if not os.access(os.path.dirname(set_file),os.W_OK):
            return -3,_("Cannot create the element")

        f = open(set_file,"w")
        for x in set_atoms: f.write("%s\n" % (x,))
        f.flush()
        f.close()
        self.SystemSettings['system_package_sets'][set_name] = set(set_atoms)
        return 0,_("All fine")

    def remove_user_package_set(self, set_name):

        try:
            set_name = str(set_name)
        except (UnicodeEncodeError,UnicodeDecodeError,):
            raise InvalidPackageSet("InvalidPackageSet: %s %s" % (set_name,_("must be an ASCII string"),))

        if set_name.startswith(etpConst['packagesetprefix']):
            raise InvalidPackageSet("InvalidPackageSet: %s %s '%s'" % (set_name,_("cannot start with"),etpConst['packagesetprefix'],))

        set_match, rc = self.packageSetMatch(set_name)
        if not rc: return -1,_("Already removed")
        set_id, set_x, set_y = set_match

        if set_id != etpConst['userpackagesetsid']:
            return -2,_("Not defined by user")
        set_file = os.path.join(etpConst['confsetsdir'],set_name)
        if os.path.isfile(set_file) and os.access(set_file,os.W_OK):
            os.remove(set_file)
            if set_name in self.SystemSettings['system_package_sets']:
                del self.SystemSettings['system_package_sets'][set_name]
            return 0,_("All fine")
        return -3,_("Set not found or unable to remove")

    # every tbz2 file that would be installed must pass from here
    def add_tbz2_to_repos(self, tbz2file):
        atoms_contained = []
        basefile = os.path.basename(tbz2file)
        if os.path.isdir(etpConst['entropyunpackdir']+"/"+basefile[:-5]):
            shutil.rmtree(etpConst['entropyunpackdir']+"/"+basefile[:-5])
        os.makedirs(etpConst['entropyunpackdir']+"/"+basefile[:-5])
        dbfile = self.entropyTools.extractEdb(tbz2file, dbpath = etpConst['entropyunpackdir']+"/"+basefile[:-5]+"/packages.db")
        if dbfile == None:
            return -1,atoms_contained
        etpSys['dirstoclean'].add(os.path.dirname(dbfile))
        # add dbfile
        repodata = {}
        repodata['repoid'] = basefile
        repodata['description'] = "Dynamic database from "+basefile
        repodata['packages'] = []
        repodata['dbpath'] = os.path.dirname(dbfile)
        repodata['pkgpath'] = os.path.realpath(tbz2file) # extra info added
        repodata['smartpackage'] = False # extra info added

        mydbconn = self.openGenericDatabase(dbfile)
        # read all idpackages
        try:
            myidpackages = mydbconn.listAllIdpackages() # all branches admitted from external files
        except (AttributeError, self.dbapi2.DatabaseError,self.dbapi2.IntegrityError,self.dbapi2.OperationalError,):
            return -2,atoms_contained
        if len(myidpackages) > 1:
            repodata[basefile]['smartpackage'] = True
        for myidpackage in myidpackages:
            compiled_arch = mydbconn.retrieveDownloadURL(myidpackage)
            if compiled_arch.find("/"+etpSys['arch']+"/") == -1:
                return -3,atoms_contained
            atoms_contained.append((int(myidpackage),basefile))

        self.addRepository(repodata)
        self.validate_repositories()
        if basefile not in self.validRepositories:
            self.removeRepository(basefile)
            return -4,atoms_contained
        mydbconn.closeDB()
        del mydbconn
        return 0,atoms_contained

    # This is the function that should be used by third party applications
    # to retrieve a list of available updates, along with conflicts (removalQueue) and obsoletes
    # (removed)
    def retrieveWorldQueue(self, empty_deps = False, branch = etpConst['branch']):
        update, remove, fine = self.calculate_world_updates(empty_deps = empty_deps, branch = branch)
        del fine
        data = {}
        data['removed'] = list(remove)
        data['runQueue'] = []
        data['removalQueue'] = []
        status = -1
        if update:
            # calculate install+removal queues
            install, removal, status = self.retrieveInstallQueue(update, empty_deps, deep_deps = False)
            # update data['removed']
            data['removed'] = [x for x in data['removed'] if x not in removal]
            data['runQueue'] += install
            data['removalQueue'] += removal
        return data,status

    def validatePackageRemoval(self, idpackage):

        pkgatom = self.clientDbconn.retrieveAtom(idpackage)
        pkgkey = self.entropyTools.dep_getkey(pkgatom)

        if self.is_installed_idpackage_in_system_mask(idpackage):
            idpackages = self.SystemSettings['repos_system_mask_installed_keys'].get(pkgkey)
            if not idpackages: return False
            if len(idpackages) > 1:
                return True
            return False # sorry!

        # did we store the bastard in the db?
        system_pkg = self.clientDbconn.isSystemPackage(idpackage)
        if not system_pkg: return True
        # check if the package is slotted and exist more than one installed first
        sysresults = self.clientDbconn.atomMatch(pkgkey, multiMatch = True)
        if sysresults[1] == 0:
            if len(sysresults[0]) < 2: return False
            return True
        return False


    def retrieveRemovalQueue(self, idpackages, deep = False):
        queue = []
        if not idpackages:
            return queue
        treeview, status = self.generate_depends_tree(idpackages, deep = deep)
        if status == 0:
            for x in range(len(treeview))[::-1]: queue.extend(treeview[x])
        return queue

    def retrieveInstallQueue(self, matched_atoms, empty_deps, deep_deps, quiet = False):

        install = []
        removal = []
        treepackages, result = self.get_required_packages(matched_atoms, empty_deps, deep_deps, quiet = quiet)

        if result == -2:
            return treepackages,removal,result

        # format
        removal = treepackages.pop(0, set())
        for x in sorted(treepackages.keys()): install.extend(treepackages[x])

        # filter out packages that are in actionQueue comparing key + slot
        if install and removal:
            myremmatch = {}
            for x in removal:
                atom = self.clientDbconn.retrieveAtom(x)
                # XXX check if users removed idpackage while this whole instance is running
                if atom == None: continue
                myremmatch[(self.entropyTools.dep_getkey(atom),self.clientDbconn.retrieveSlot(x),)] = x
            for pkg_id, pkg_repo in install:
                dbconn = self.openRepositoryDatabase(pkg_repo)
                testtuple = (self.entropyTools.dep_getkey(dbconn.retrieveAtom(pkg_id)),dbconn.retrieveSlot(pkg_id))
                removal.discard(myremmatch.get(testtuple))

        return install, sorted(removal), 0

    # this function searches into client database for a package matching provided key + slot
    # and returns its idpackage or -1 if none found
    def retrieveInstalledIdPackage(self, pkgkey, pkgslot):
        match = self.clientDbconn.atomMatch(pkgkey, matchSlot = pkgslot)
        if match[1] == 0:
            return match[0]
        return -1

    '''
        Package interface :: begin
    '''

    def check_needed_package_download(self, filepath, checksum = None):
        # is the file available
        if os.path.isfile(etpConst['entropyworkdir']+"/"+filepath):
            if checksum is None:
                return 0
            else:
                # check digest
                md5res = self.entropyTools.compareMd5(etpConst['entropyworkdir']+"/"+filepath,checksum)
                if (md5res):
                    return 0
                else:
                    return -2
        else:
            return -1

    def fetch_files(self, url_data_list, checksum = True, resume = True, fetch_file_abort_function = None):
        """
            Fetch multiple files simultaneously on URLs.

            @param url_data_list list
                [(url,dest_path [or None],checksum ['ab86fff46f6ec0f4b1e0a2a4a82bf323' or None],branch,),..]
            @param digest bool, digest check (checksum)
            @param resume bool enable resume support
            @param fetch_file_abort_function callable method that could raise exceptions
            @return general_status_code, {'url': (status_code,checksum,resumed,)}, data_transfer
        """
        pkgs_bindir = etpConst['packagesbindir']
        url_path_list = []
        checksum_map = {}
        count = 0
        for url, dest_path, cksum, branch in url_data_list:
            count += 1
            filename = os.path.basename(url)
            if dest_path == None:
                dest_path = os.path.join(pkgs_bindir,branch,filename,)

            dest_dir = os.path.dirname(dest_path)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir,0755)

            url_path_list.append((url,dest_path,))
            if cksum != None: checksum_map[count] = cksum

        # load class
        fetchConn = self.MultipleUrlFetcher(url_path_list, resume = resume,
            abort_check_func = fetch_file_abort_function, OutputInterface = self,
            urlFetcherClass = self.urlFetcher, checksum = checksum)
        try:
            data = fetchConn.download()
        except KeyboardInterrupt:
            return -100, {}, 0

        diff_map = {}
        if checksum_map and checksum: # verify checksums
            diff_map = dict((url_path_list[x-1][0],checksum_map.get(x)) for x in checksum_map \
                if checksum_map.get(x) != data.get(x))

        data_transfer = fetchConn.get_data_transfer()
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

    def fetch_files_on_mirrors(self, download_list, checksum = False, fetch_abort_function = None):
        """
            @param download_map list [(repository,branch,filename,checksum (digest),),..]
            @param checksum bool verify checksum?
            @param fetch_abort_function callable method that could raise exceptions
        """
        repo_uris = dict(((x[0],etpRepositories[x[0]]['packages'][::-1],) for x in download_list))
        remaining = repo_uris.copy()
        my_download_list = download_list[:]

        def get_best_mirror(repository):
            try:
                return remaining[repository][0]
            except IndexError:
                return None

        def update_download_list(down_list, failed_down):
            newlist = []
            for repo,branch,fname,cksum in down_list:
                myuri = get_best_mirror(repo)
                myuri = os.path.join(myuri,fname)
                if myuri not in failed_down:
                    continue
                newlist.append((repo,branch,fname,cksum,))
            return newlist

        # return True: for failing, return False: for fine
        def mirror_fail_check(repository, best_mirror):
            # check if uri is sane
            if not self.MirrorStatus.get_failing_mirror_status(best_mirror) >= 30:
                return False
            # set to 30 for convenience
            self.MirrorStatus.set_failing_mirror_status(best_mirror, 30)
            mirrorcount = repo_uris[repo].index(best_mirror)+1
            mytxt = "( mirror #%s ) " % (mirrorcount,)
            mytxt += blue(" %s: ") % (_("Mirror"),)
            mytxt += red(self.entropyTools.spliturl(best_mirror)[1])
            mytxt += " - %s." % (_("maximum failure threshold reached"),)
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = red("   ## ")
            )

            if self.MirrorStatus.get_failing_mirror_status(best_mirror) == 30:
                self.MirrorStatus.add_failing_mirror(best_mirror,45)
            elif self.MirrorStatus.get_failing_mirror_status(best_mirror) > 31:
                self.MirrorStatus.add_failing_mirror(best_mirror,-4)
            else:
                self.MirrorStatus.set_failing_mirror_status(best_mirror, 0)

            remaining[repository].discard(best_mirror)
            return True

        def show_download_summary(down_list):
            # fetch_files_list.append((myuri,None,cksum,branch,))
            for repo, branch, fname, cksum in down_list:
                best_mirror = get_best_mirror(repo)
                mirrorcount = repo_uris[repo].index(best_mirror)+1
                mytxt = "( mirror #%s ) " % (mirrorcount,)
                basef = os.path.basename(fname)
                mytxt += "[%s] %s " % (brown(basef),blue("@"),)
                mytxt += red(self.entropyTools.spliturl(best_mirror)[1])
                # now fetch the new one
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = red("   ## ")
                )

        def show_successful_download(down_list, data_transfer):
            for repo, branch, fname, cksum in down_list:
                best_mirror = get_best_mirror(repo)
                mirrorcount = repo_uris[repo].index(best_mirror)+1
                mytxt = "( mirror #%s ) " % (mirrorcount,)
                basef = os.path.basename(fname)
                mytxt += "[%s] %s %s " % (brown(basef),darkred(_("success")),blue("@"),)
                mytxt += red(self.entropyTools.spliturl(best_mirror)[1])
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = red("   ## ")
                )
            mytxt = " %s: %s%s%s" % (
                blue(_("Aggregated transfer rate")),
                bold(self.entropyTools.bytesIntoHuman(data_transfer)),
                darkred("/"),
                darkblue(_("second")),
            )
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red("   ## ")
            )

        def show_download_error(down_list, rc):
            for repo, branch, fname, cksum in down_list:
                best_mirror = get_best_mirror(repo)
                mirrorcount = repo_uris[repo].index(best_mirror)+1
                mytxt = "( mirror #%s ) " % (mirrorcount,)
                mytxt += blue("%s: %s") % (
                    _("Error downloading from"),
                    red(self.entropyTools.spliturl(best_mirror)[1]),
                )
                if rc == -1:
                    mytxt += " - %s." % (_("files not available on this mirror"),)
                elif rc == -2:
                    self.MirrorStatus.add_failing_mirror(best_mirror,1)
                    mytxt += " - %s." % (_("wrong checksum"),)
                elif rc == -3:
                    mytxt += " - %s." % (_("not found"),)
                elif rc == -4: # timeout!
                    mytxt += " - %s." % (_("timeout error"),)
                elif rc == -100:
                    mytxt += " - %s." % (_("discarded download"),)
                else:
                    self.MirrorStatus.add_failing_mirror(best_mirror, 5)
                    mytxt += " - %s." % (_("unknown reason"),)
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )

        def remove_failing_mirrors(repos):
            for repo in repos:
                best_mirror = get_best_mirror(repo)
                if remaining[repo]:
                    remaining[repo].pop(0)

        def check_remaining_mirror_failure(repos):
            return [x for x in repos if not remaining.get(x)]

        while 1:

            do_resume = True
            timeout_try_count = 50
            while 1:

                fetch_files_list = []
                for repo, branch, fname, cksum in my_download_list:
                    best_mirror = get_best_mirror(repo)
                    if best_mirror != None:
                        mirror_fail_check(repo, best_mirror)
                        best_mirror = get_best_mirror(repo)
                    if best_mirror == None:
                        # at least one package failed to download
                        # properly, give up with everything
                        return 3, my_download_list
                    myuri = os.path.join(best_mirror,fname)
                    fetch_files_list.append((myuri,None,cksum,branch,))

                try:

                    show_download_summary(my_download_list)
                    rc, failed_downloads, data_transfer = self.fetch_files(
                        fetch_files_list, checksum = checksum,
                        fetch_file_abort_function = fetch_abort_function,
                        resume = do_resume
                    )
                    if rc == 0:
                        show_successful_download(my_download_list, data_transfer)
                        return 0, []

                    # update my_download_list
                    my_download_list = update_download_list(my_download_list,failed_downloads)
                    if rc not in (-3,-4,-100,) and failed_downloads and do_resume:
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
                        myrepos = set([x[0] for x in my_download_list])
                        remove_failing_mirrors(myrepos)
                        # make sure we don't have nasty issues
                        remaining_failure = check_remaining_mirror_failure(myrepos)
                        if remaining_failure:
                            return 3, my_download_list
                        break
                except KeyboardInterrupt:
                    return 1, []
        return 0, []


    def fetch_file(self, url, branch, digest = None, resume = True, fetch_file_abort_function = None, filepath = None):

        filename = os.path.basename(url)
        if not filepath:
            filepath = os.path.join(etpConst['packagesbindir'],branch,filename)
        filepath_dir = os.path.dirname(filepath)
        if not os.path.isdir(filepath_dir):
            os.makedirs(filepath_dir,0755)

        # load class
        fetchConn = self.urlFetcher(url, filepath, resume = resume,
            abort_check_func = fetch_file_abort_function, OutputInterface = self)
        fetchConn.progress = self.progress

        # start to download
        data_transfer = 0
        resumed = False
        try:
            fetchChecksum = fetchConn.download()
            data_transfer = fetchConn.get_transfer_rate()
            resumed = fetchConn.is_resumed()
        except KeyboardInterrupt:
            return -100, data_transfer, resumed
        except NameError:
            raise
        except:
            if etpUi['debug']:
                self.updateProgress(
                    "fetch_file:",
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )
                self.entropyTools.printTraceback()
            return -1, data_transfer, resumed
        if fetchChecksum == "-3":
            # not found
            return -3, data_transfer, resumed
        elif fetchChecksum == "-4":
            # timeout
            return -4, data_transfer, resumed

        del fetchConn
        if digest:
            if fetchChecksum != digest:
                # not properly downloaded
                return -2, data_transfer, resumed
            else:
                return 0, data_transfer, resumed
        return 0, data_transfer, resumed


    def fetch_file_on_mirrors(self, repository, branch, filename,
            digest = False, fetch_abort_function = None):

        uris = etpRepositories[repository]['packages'][::-1]
        remaining = set(uris)

        mirrorcount = 0
        for uri in uris:

            if not remaining:
                # tried all the mirrors, quitting for error
                return 3

            mirrorcount += 1
            mirrorCountText = "( mirror #%s ) " % (mirrorcount,)
            url = uri+"/"+filename

            # check if uri is sane
            if self.MirrorStatus.get_failing_mirror_status(uri) >= 30:
                # ohohoh!
                # set to 30 for convenience
                self.MirrorStatus.set_failing_mirror_status(uri, 30)
                mytxt = mirrorCountText
                mytxt += blue(" %s: ") % (_("Mirror"),)
                mytxt += red(self.entropyTools.spliturl(uri)[1])
                mytxt += " - %s." % (_("maximum failure threshold reached"),)
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )

                if self.MirrorStatus.get_failing_mirror_status(uri) == 30:
                    # put to 75 then decrement by 4 so we
                    # won't reach 30 anytime soon ahahaha
                    self.MirrorStatus.add_failing_mirror(uri,45)
                elif self.MirrorStatus.get_failing_mirror_status(uri) > 31:
                    # now decrement each time this point is reached,
                    # if will be back < 30, then equo will try to use it again
                    self.MirrorStatus.add_failing_mirror(uri,-4)
                else:
                    # put to 0 - reenable mirror, welcome back uri!
                    self.MirrorStatus.set_failing_mirror_status(uri, 0)

                remaining.discard(uri)
                continue

            do_resume = True
            timeout_try_count = 50
            while 1:
                try:
                    mytxt = mirrorCountText
                    mytxt += blue("%s: ") % (_("Downloading from"),)
                    mytxt += red(self.entropyTools.spliturl(uri)[1])
                    # now fetch the new one
                    self.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "warning",
                        header = red("   ## ")
                    )
                    rc, data_transfer, resumed = self.fetch_file(
                        url,
                        branch,
                        digest,
                        do_resume,
                        fetch_file_abort_function = fetch_abort_function
                    )
                    if rc == 0:
                        mytxt = mirrorCountText
                        mytxt += blue("%s: ") % (_("Successfully downloaded from"),)
                        mytxt += red(self.entropyTools.spliturl(uri)[1])
                        mytxt += " %s %s/%s" % (_("at"),self.entropyTools.bytesIntoHuman(data_transfer),_("second"),)
                        self.updateProgress(
                            mytxt,
                            importance = 1,
                            type = "info",
                            header = red("   ## ")
                        )

                        return 0
                    elif resumed and rc not in (-3,-4,-100,):
                        do_resume = False
                        continue
                    else:
                        error_message = mirrorCountText
                        error_message += blue("%s: %s") % (
                            _("Error downloading from"),
                            red(self.entropyTools.spliturl(uri)[1]),
                        )
                        # something bad happened
                        if rc == -1:
                            error_message += " - %s." % (_("file not available on this mirror"),)
                        elif rc == -2:
                            self.MirrorStatus.add_failing_mirror(uri,1)
                            error_message += " - %s." % (_("wrong checksum"),)
                        elif rc == -3:
                            error_message += " - %s." % (_("not found"),)
                        elif rc == -4: # timeout!
                            timeout_try_count -= 1
                            if timeout_try_count > 0:
                                error_message += " - %s." % (_("timeout, retrying on this mirror"),)
                            else:
                                error_message += " - %s." % (_("timeout, giving up"),)
                        elif rc == -100:
                            error_message += " - %s." % (_("discarded download"),)
                        else:
                            self.MirrorStatus.add_failing_mirror(uri, 5)
                            error_message += " - %s." % (_("unknown reason"),)
                        self.updateProgress(
                            error_message,
                            importance = 1,
                            type = "warning",
                            header = red("   ## ")
                        )
                        if rc == -4: # timeout
                            if timeout_try_count > 0:
                                continue
                        elif rc == -100: # user discarded fetch
                            return 1
                        remaining.discard(uri)
                        # make sure we don't have nasty issues
                        if not remaining:
                            return 3
                        break
                except KeyboardInterrupt:
                    return 1
        return 0

    def quickpkg(self, atomstring, savedir = None):
        if savedir == None:
            savedir = etpConst['packagestmpdir']
            if not os.path.isdir(etpConst['packagestmpdir']):
                os.makedirs(etpConst['packagestmpdir'])
        # match package
        match = self.clientDbconn.atomMatch(atomstring)
        if match[0] == -1:
            return -1,None,None
        atom = self.clientDbconn.atomMatch(match[0])
        pkgdata = self.clientDbconn.getPackageData(match[0])
        resultfile = self.quickpkg_handler(pkgdata = pkgdata, dirpath = savedir)
        if resultfile == None:
            return -1,atom,None
        else:
            return 0,atom,resultfile

    def quickpkg_handler(self, pkgdata, dirpath, edb = True,
           portdbPath = None, fake = False, compression = "bz2", shiftpath = ""):

        import stat
        import tarfile

        if compression not in ("bz2","","gz"):
            compression = "bz2"

        # getting package info
        pkgtag = ''
        pkgrev = "~"+str(pkgdata['revision'])
        if pkgdata['versiontag']: pkgtag = "#"+pkgdata['versiontag']
        pkgname = pkgdata['name']+"-"+pkgdata['version']+pkgrev+pkgtag # + version + tag
        pkgcat = pkgdata['category']
        #pkgfile = pkgname+etpConst['packagesext']
        dirpath += "/"+pkgname+etpConst['packagesext']
        if os.path.isfile(dirpath):
            os.remove(dirpath)
        tar = tarfile.open(dirpath,"w:"+compression)

        if not fake:

            contents = sorted([x for x in pkgdata['content']])
            id_strings = {}

            # collect files
            for path in contents:
                # convert back to filesystem str
                encoded_path = path
                path = path.encode('raw_unicode_escape')
                path = shiftpath+path
                try:
                    exist = os.lstat(path)
                except OSError:
                    continue # skip file
                arcname = path[len(shiftpath):] # remove shiftpath
                if arcname.startswith("/"):
                    arcname = arcname[1:] # remove trailing /
                ftype = pkgdata['content'][encoded_path]
                if str(ftype) == '0': ftype = 'dir' # force match below, '0' means databases without ftype
                if 'dir' == ftype and \
                    not stat.S_ISDIR(exist.st_mode) and \
                    os.path.isdir(path): # workaround for directory symlink issues
                    path = os.path.realpath(path)

                tarinfo = tar.gettarinfo(path, arcname)
                tarinfo.uname = id_strings.setdefault(tarinfo.uid, str(tarinfo.uid))
                tarinfo.gname = id_strings.setdefault(tarinfo.gid, str(tarinfo.gid))

                if stat.S_ISREG(exist.st_mode):
                    tarinfo.type = tarfile.REGTYPE
                    f = open(path)
                    try:
                        tar.addfile(tarinfo, f)
                    finally:
                        f.close()
                else:
                    tar.addfile(tarinfo)

        tar.close()

        # appending xpak metadata
        if etpConst['gentoo-compat']:
            import entropy.xpak as xpak
            Spm = self.Spm()

            gentoo_name = self.entropyTools.remove_tag(pkgname)
            gentoo_name = self.entropyTools.remove_entropy_revision(gentoo_name)
            if portdbPath == None:
                dbdir = Spm.get_vdb_path()+"/"+pkgcat+"/"+gentoo_name+"/"
            else:
                dbdir = portdbPath+"/"+pkgcat+"/"+gentoo_name+"/"
            if os.path.isdir(dbdir):
                tbz2 = xpak.tbz2(dirpath)
                tbz2.recompose(dbdir)

        if edb:
            self.inject_entropy_database_into_package(dirpath, pkgdata)

        if os.path.isfile(dirpath):
            return dirpath
        return None

    def inject_entropy_database_into_package(self, package_filename, data, treeupdates_actions = None):
        dbpath = self.get_tmp_dbpath()
        dbconn = self.openGenericDatabase(dbpath)
        dbconn.initializeDatabase()
        dbconn.addPackage(data, revision = data['revision'])
        if treeupdates_actions != None:
            dbconn.bumpTreeUpdatesActions(treeupdates_actions)
        dbconn.commitChanges()
        dbconn.closeDB()
        self.entropyTools.aggregateEdb(tbz2file = package_filename, dbfile = dbpath)
        return dbpath

    def get_tmp_dbpath(self):
        dbpath = etpConst['packagestmpdir']+"/"+str(self.entropyTools.getRandomNumber())
        while os.path.isfile(dbpath):
            dbpath = etpConst['packagestmpdir']+"/"+str(self.entropyTools.getRandomNumber())
        return dbpath

    def Package(self):
        return Package(self)

    '''
        Package interface :: end
    '''

    '''
        Source Package Manager Interface :: begin
    '''
    def Spm(self):
        from entropy.spm import Spm
        myroot = etpConst['systemroot']
        cached = self.spmCache.get(myroot)
        if cached != None: return cached
        conn = Spm(self)
        self.spmCache[myroot] = conn.intf
        return conn.intf

    def _extract_pkg_metadata_generate_extraction_dict(self):
        data = {
            'chost': {
                'path': etpConst['spm']['xpak_entries']['chost'],
                'critical': True,
            },
            'description': {
                'path': etpConst['spm']['xpak_entries']['description'],
                'critical': False,
            },
            'homepage': {
                'path': etpConst['spm']['xpak_entries']['homepage'],
                'critical': False,
            },
            'slot': {
                'path': etpConst['spm']['xpak_entries']['slot'],
                'critical': False,
            },
            'cflags': {
                'path': etpConst['spm']['xpak_entries']['cflags'],
                'critical': False,
            },
            'cxxflags': {
                'path': etpConst['spm']['xpak_entries']['cxxflags'],
                'critical': False,
            },
            'category': {
                'path': etpConst['spm']['xpak_entries']['category'],
                'critical': True,
            },
            'rdepend': {
                'path': etpConst['spm']['xpak_entries']['rdepend'],
                'critical': False,
            },
            'pdepend': {
                'path': etpConst['spm']['xpak_entries']['pdepend'],
                'critical': False,
            },
            'depend': {
                'path': etpConst['spm']['xpak_entries']['depend'],
                'critical': False,
            },
            'use': {
                'path': etpConst['spm']['xpak_entries']['use'],
                'critical': False,
            },
            'iuse': {
                'path': etpConst['spm']['xpak_entries']['iuse'],
                'critical': False,
            },
            'license': {
                'path': etpConst['spm']['xpak_entries']['license'],
                'critical': False,
            },
            'provide': {
                'path': etpConst['spm']['xpak_entries']['provide'],
                'critical': False,
            },
            'sources': {
                'path': etpConst['spm']['xpak_entries']['src_uri'],
                'critical': False,
            },
            'eclasses': {
                'path': etpConst['spm']['xpak_entries']['inherited'],
                'critical': False,
            },
            'counter': {
                'path': etpConst['spm']['xpak_entries']['counter'],
                'critical': False,
            },
            'keywords': {
                'path': etpConst['spm']['xpak_entries']['keywords'],
                'critical': False,
            },
        }
        return data

    def _extract_pkg_metadata_content(self, content_file, package_path):

        pkg_content = {}

        if os.path.isfile(content_file):
            f = open(content_file,"r")
            content = f.readlines()
            f.close()
            outcontent = set()
            for line in content:
                line = line.strip().split()
                try:
                    datatype = line[0]
                    datafile = line[1:]
                    if datatype == 'obj':
                        datafile = datafile[:-2]
                        datafile = ' '.join(datafile)
                    elif datatype == 'dir':
                        datafile = ' '.join(datafile)
                    elif datatype == 'sym':
                        datafile = datafile[:-3]
                        datafile = ' '.join(datafile)
                    else:
                        myexc = "InvalidData: %s %s. %s." % (
                            datafile,
                            _("not supported"),
                            _("Probably Portage API has changed"),
                        )
                        raise InvalidData(myexc)
                    outcontent.add((datafile,datatype))
                except:
                    pass

            _outcontent = set()
            for i in outcontent:
                i = list(i)
                datatype = i[1]
                _outcontent.add((i[0],i[1]))
            outcontent = sorted(_outcontent)
            for i in outcontent:
                pkg_content[i[0]] = i[1]

        else:

            # CONTENTS is not generated when a package is emerged with portage and the option -B
            # we have to unpack the tbz2 and generate content dict
            mytempdir = etpConst['packagestmpdir']+"/"+os.path.basename(package_path)+".inject"
            if os.path.isdir(mytempdir):
                shutil.rmtree(mytempdir)
            if not os.path.isdir(mytempdir):
                os.makedirs(mytempdir)

            self.entropyTools.uncompressTarBz2(package_path, extractPath = mytempdir, catchEmpty = True)
            for currentdir, subdirs, files in os.walk(mytempdir):
                pkg_content[currentdir[len(mytempdir):]] = "dir"
                for item in files:
                    item = currentdir+"/"+item
                    if os.path.islink(item):
                        pkg_content[item[len(mytempdir):]] = "sym"
                    else:
                        pkg_content[item[len(mytempdir):]] = "obj"

            # now remove
            shutil.rmtree(mytempdir,True)
            try: os.rmdir(mytempdir)
            except (OSError,): pass

        return pkg_content

    def _extract_pkg_metadata_needed(self, needed_file):

        pkg_needed = set()
        lines = []

        try:
            f = open(needed_file,"r")
            lines = [x.strip() for x in f.readlines() if x.strip()]
            f.close()
        except IOError:
            return lines

        for line in lines:
            needed = line.split()
            if len(needed) == 2:
                ownlib = needed[0]
                ownelf = -1
                if os.access(ownlib,os.R_OK):
                    ownelf = self.entropyTools.read_elf_class(ownlib)
                for lib in needed[1].split(","):
                    #if lib.find(".so") != -1:
                    pkg_needed.add((lib,ownelf))

        return list(pkg_needed)

    def _extract_pkg_metadata_messages(self, log_dir, category, name, version, silent = False):

        pkg_messages = []

        if os.path.isdir(log_dir):

            elogfiles = os.listdir(log_dir)
            myelogfile = "%s:%s-%s" % (category, name, version,)
            foundfiles = [x for x in elogfiles if x.startswith(myelogfile)]
            if foundfiles:
                elogfile = foundfiles[0]
                if len(foundfiles) > 1:
                    # get the latest
                    mtimes = []
                    for item in foundfiles: mtimes.append((self.entropyTools.getFileUnixMtime(os.path.join(log_dir,item)),item))
                    mtimes = sorted(mtimes)
                    elogfile = mtimes[-1][1]
                messages = self.entropyTools.extractElog(os.path.join(log_dir,elogfile))
                for message in messages:
                    message = message.replace("emerge","install")
                    pkg_messages.append(message)

        elif not silent:

            mytxt = " %s, %s" % (_("not set"),_("have you configured make.conf properly?"),)
            self.updateProgress(
                red(log_dir)+mytxt,
                importance = 1,
                type = "warning",
                header = brown(" * ")
            )

        return pkg_messages

    def _extract_pkg_metadata_license_data(self, licenses_dir, license_string):

        pkg_licensedata = {}
        if licenses_dir and os.path.isdir(licenses_dir):
            licdata = [x.strip() for x in license_string.split() if x.strip() and self.entropyTools.is_valid_string(x.strip())]
            for mylicense in licdata:
                licfile = os.path.join(licenses_dir,mylicense)
                if os.access(licfile,os.R_OK):
                    if self.entropyTools.istextfile(licfile):
                        f = open(licfile)
                        pkg_licensedata[mylicense] = f.read()
                        f.close()

        return pkg_licensedata

    def _extract_pkg_metadata_mirror_links(self, Spm, sources_list):

        # =mirror://openoffice|link1|link2|link3
        pkg_links = []
        for i in sources_list:
            if i.startswith("mirror://"):
                # parse what mirror I need
                mirrorURI = i.split("/")[2]
                mirrorlist = Spm.get_third_party_mirrors(mirrorURI)
                pkg_links.append([mirrorURI,mirrorlist])
                # mirrorURI = openoffice and mirrorlist = [link1, link2, link3]

        return pkg_links

    def _extract_pkg_metadata_ebuild_entropy_tag(self, ebuild):
        search_tag = etpConst['spm']['ebuild_pkg_tag_var']
        ebuild_tag = ''
        f = open(ebuild,"r")
        tags = [x.strip() for x in f.readlines() if x.strip() and x.strip().startswith(search_tag)]
        f.close()
        if not tags: return ebuild_tag
        tag = tags[-1]
        tag = tag.split("=")[-1].strip('"').strip("'").strip()
        return tag

    # This function extracts all the info from a .tbz2 file and returns them
    def extract_pkg_metadata(self, package, etpBranch = etpConst['branch'], silent = False, inject = False):

        data = {}
        info_package = bold(os.path.basename(package))+": "

        if not silent:
            self.updateProgress(
                red(info_package+_("Extracting package metadata")+" ..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )

        filepath = package
        tbz2File = package
        package = package.split(etpConst['packagesext'])[0]
        package = self.entropyTools.remove_entropy_revision(package)
        package = self.entropyTools.remove_tag(package)
        # remove entropy category
        if package.find(":") != -1:
            package = ':'.join(package.split(":")[1:])

        # pkgcat is always == "null" here
        pkgcat, pkgname, pkgver, pkgrev = self.entropyTools.catpkgsplit(os.path.basename(package))
        if pkgrev != "r0": pkgver += "-%s" % (pkgrev,)

        # Fill Package name and version
        data['name'] = pkgname
        data['version'] = pkgver
        data['digest'] = self.entropyTools.md5sum(tbz2File)
        data['datecreation'] = str(self.entropyTools.getFileUnixMtime(tbz2File))
        data['size'] = str(self.entropyTools.get_file_size(tbz2File))

        tbz2TmpDir = etpConst['packagestmpdir']+"/"+data['name']+"-"+data['version']+"/"
        if not os.path.isdir(tbz2TmpDir):
            if os.path.lexists(tbz2TmpDir):
                os.remove(tbz2TmpDir)
            os.makedirs(tbz2TmpDir)
        self.entropyTools.extractXpak(tbz2File,tbz2TmpDir)

        data['injected'] = False
        if inject: data['injected'] = True
        data['branch'] = etpBranch

        portage_entries = self._extract_pkg_metadata_generate_extraction_dict()
        for item in portage_entries:
            value = ''
            try:
                f = open(os.path.join(tbz2TmpDir,portage_entries[item]['path']),"r")
                value = f.readline().strip()
                f.close()
            except IOError:
                if portage_entries[item]['critical']:
                    raise
            data[item] = value

        # setup vars
        data['eclasses'] = data['eclasses'].split()
        try:
            data['counter'] = int(data['counter'])
        except ValueError:
            data['counter'] = -2 # -2 values will be insterted as incremental negative values into the database
        data['keywords'] = [x.strip() for x in data['keywords'].split() if x.strip()]
        if not data['keywords']: data['keywords'].insert(0,"") # support for packages with no keywords
        needed_file = os.path.join(tbz2TmpDir,etpConst['spm']['xpak_entries']['needed'])
        data['needed'] = self._extract_pkg_metadata_needed(needed_file)
        content_file = os.path.join(tbz2TmpDir,etpConst['spm']['xpak_entries']['contents'])
        data['content'] = self._extract_pkg_metadata_content(content_file, filepath)
        data['disksize'] = self.entropyTools.sum_file_sizes(data['content'])

        # [][][] Kernel dependent packages hook [][][]
        data['versiontag'] = ''
        kernelstuff = False
        kernelstuff_kernel = False
        for item in data['content']:
            if item.startswith("/lib/modules/"):
                kernelstuff = True
                # get the version of the modules
                kmodver = item.split("/lib/modules/")[1]
                kmodver = kmodver.split("/")[0]

                lp = kmodver.split("-")[-1]
                if lp.startswith("r"):
                    kname = kmodver.split("-")[-2]
                    kver = kmodver.split("-")[0]+"-"+kmodver.split("-")[-1]
                else:
                    kname = kmodver.split("-")[-1]
                    kver = kmodver.split("-")[0]
                break
        # validate the results above
        if kernelstuff:
            matchatom = "linux-%s-%s" % (kname,kver,)
            if (matchatom == data['name']+"-"+data['version']):
                kernelstuff_kernel = True

            data['versiontag'] = kmodver
            if not kernelstuff_kernel:
                data['slot'] = kmodver # if you change this behaviour,
                                       # you must change "reagent update"
                                       # and "equo database gentoosync" consequentially

        file_ext = etpConst['spm']['ebuild_file_extension']
        ebuilds_in_path = [x for x in os.listdir(tbz2TmpDir) if x.endswith(".%s" % (file_ext,))]
        if not data['versiontag'] and ebuilds_in_path:
            # has the user specified a custom package tag inside the ebuild
            ebuild_path = os.path.join(tbz2TmpDir,ebuilds_in_path[0])
            data['versiontag'] = self._extract_pkg_metadata_ebuild_entropy_tag(ebuild_path)


        data['download'] = etpConst['packagesrelativepath'] + data['branch'] + "/"
        data['download'] += self.entropyTools.create_package_filename(data['category'], data['name'], data['version'], data['versiontag'])


        data['trigger'] = ""
        if os.path.isfile(etpConst['triggersdir']+"/"+data['category']+"/"+data['name']+"/"+etpConst['triggername']):
            f = open(etpConst['triggersdir']+"/"+data['category']+"/"+data['name']+"/"+etpConst['triggername'],"rb")
            data['trigger'] = f.read()
            f.close()

        Spm = self.Spm()

        # Get Spm ChangeLog
        pkgatom = "%s/%s-%s" % (data['category'],data['name'],data['version'],)
        try:
            data['changelog'] = Spm.get_package_changelog(pkgatom)
        except:
            data['changelog'] = None

        portage_metadata = Spm.calculate_dependencies(
            data['iuse'], data['use'], data['license'], data['depend'],
            data['rdepend'], data['pdepend'], data['provide'], data['sources']
        )

        data['provide'] = portage_metadata['PROVIDE'].split()
        data['license'] = portage_metadata['LICENSE']
        data['useflags'] = []
        for x in data['use'].split():
            if x.startswith("+"):
                x = x[1:]
            elif x.startswith("-"):
                x = x[1:]
            if (x in portage_metadata['USE']) or (x in portage_metadata['USE_MASK']):
                data['useflags'].append(x)
            else:
                data['useflags'].append("-"+x)
        data['sources'] = portage_metadata['SRC_URI'].split()
        data['dependencies'] = {}
        for x in portage_metadata['RDEPEND'].split():
            if x.startswith("!") or (x in ("(","||",")","")):
                continue
            data['dependencies'][x] = etpConst['spm']['(r)depend_id']
        for x in portage_metadata['PDEPEND'].split():
            if x.startswith("!") or (x in ("(","||",")","")):
                continue
            data['dependencies'][x] = etpConst['spm']['pdepend_id']
        data['conflicts'] = [x[1:] for x in portage_metadata['RDEPEND'].split()+portage_metadata['PDEPEND'].split() if x.startswith("!") and not x in ("(","||",")","")]

        if (kernelstuff) and (not kernelstuff_kernel):
            # add kname to the dependency
            data['dependencies']["=sys-kernel/linux-"+kname+"-"+kver+"~-1"] = etpConst['spm']['(r)depend_id']

        # Conflicting tagged packages support
        key = data['category']+"/"+data['name']
        confl_data = self.SystemSettings['conflicting_tagged_packages'].get(key)
        if confl_data != None:
            for conflict in confl_data: data['conflicts'].append(conflict)

        # Get License text if possible
        licenses_dir = os.path.join(Spm.get_spm_setting('PORTDIR'),'licenses')
        data['licensedata'] = self._extract_pkg_metadata_license_data(licenses_dir, data['license'])
        data['mirrorlinks'] = self._extract_pkg_metadata_mirror_links(Spm, data['sources'])

        # write only if it's a systempackage
        data['systempackage'] = False
        system_packages = [self.entropyTools.dep_getkey(x) for x in Spm.get_atoms_in_system()]
        if data['category']+"/"+data['name'] in system_packages:
            data['systempackage'] = True

        # write only if it's a systempackage
        protect, mask = Spm.get_config_protect_and_mask()
        data['config_protect'] = protect
        data['config_protect_mask'] = mask

        log_dir = etpConst['logdir']+"/elog"
        if not os.path.isdir(log_dir): os.makedirs(log_dir)
        data['messages'] = self._extract_pkg_metadata_messages(log_dir, data['category'], data['name'], data['version'], silent = silent)
        data['etpapi'] = etpConst['etpapi']

        # removing temporary directory
        shutil.rmtree(tbz2TmpDir,True)
        if os.path.isdir(tbz2TmpDir):
            try: os.remove(tbz2TmpDir)
            except OSError: pass

        if not silent:
            self.updateProgress(
                red(info_package+_("Package extraction complete")), importance = 0,
                type = "info", header = brown(" * "), back = True
            )
        return data

    '''
        Source Package Manager Interface :: end
    '''

    def Triggers(self, *args, **kwargs):
        return Trigger(self, *args, **kwargs)

    def Repositories(self, reponames = [], forceUpdate = False, noEquoCheck = False, fetchSecurity = True):
        return Repository(self, reponames = reponames,
            forceUpdate = forceUpdate, noEquoCheck = noEquoCheck,
            fetchSecurity = fetchSecurity)


class Package:

    import entropy.tools as entropyTools
    def __init__(self, EquoInstance):

        if not isinstance(EquoInstance,Client):
            mytxt = _("A valid Equo instance or subclass is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        self.Entropy = EquoInstance
        from entropy.cache import EntropyCacher
        self.Cacher = EntropyCacher()
        self.infoDict = {}
        self.prepared = False
        self.matched_atom = ()
        self.valid_actions = ("source","fetch","multi_fetch","remove",
            "remove_conflict","install","config"
        )
        self.action = None
        self.fetch_abort_function = None
        self.xterm_title = ''

    def kill(self):
        self.infoDict.clear()
        self.matched_atom = ()
        self.valid_actions = ()
        self.action = None
        self.prepared = False
        self.fetch_abort_function = None

    def error_on_prepared(self):
        if self.prepared:
            mytxt = _("Already prepared")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))

    def error_on_not_prepared(self):
        if not self.prepared:
            mytxt = _("Not yet prepared")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))

    def check_action_validity(self, action):
        if action not in self.valid_actions:
            mytxt = _("Action must be in")
            raise InvalidData("InvalidData: %s %s" % (mytxt,self.valid_actions,))

    def match_checksum(self, repository = None, checksum = None, download = None):
        self.error_on_not_prepared()

        if repository == None:
            repository = self.infoDict['repository']
        if checksum == None:
            checksum = self.infoDict['checksum']
        if download == None:
            download = self.infoDict['download']

        dlcount = 0
        match = False
        while dlcount <= 5:
            self.Entropy.updateProgress(
                blue(_("Checking package checksum...")),
                importance = 0,
                type = "info",
                header = red("   ## "),
                back = True
            )
            dlcheck = self.Entropy.check_needed_package_download(download, checksum = checksum)
            if dlcheck == 0:
                basef = os.path.basename(download)
                self.Entropy.updateProgress(
                    "%s: %s" % (blue(_("Package checksum matches")),darkgreen(basef),),
                    importance = 0,
                    type = "info",
                    header = red("   ## ")
                )
                self.infoDict['verified'] = True
                match = True
                break # file downloaded successfully
            else:
                dlcount += 1
                self.Entropy.updateProgress(
                    blue(_("Package checksum does not match. Redownloading... attempt #%s") % (dlcount,)),
                    importance = 0,
                    type = "info",
                    header = red("   ## "),
                    back = True
                )
                fetch = self.Entropy.fetch_file_on_mirrors(
                    repository,
                    self.Entropy.get_branch_from_download_relative_uri(download),
                    download,
                    checksum,
                    fetch_abort_function = self.fetch_abort_function
                )
                if fetch != 0:
                    self.Entropy.updateProgress(
                        blue(_("Cannot properly fetch package! Quitting.")),
                        importance = 0,
                        type = "info",
                        header = red("   ## ")
                    )
                    return fetch
                self.infoDict['verified'] = True
                match = True
                break
        if (not match):
            mytxt = _("Cannot properly fetch package or checksum does not match. Try download latest repositories.")
            self.Entropy.updateProgress(
                blue(mytxt),
                importance = 0,
                type = "info",
                header = red("   ## ")
            )
            return 1
        return 0

    def multi_match_checksum(self):
        rc = 0
        for repository, branch, download, digest in self.infoDict['multi_checksum_list']:
            rc = self.match_checksum(repository, digest, download)
            if rc != 0: break
        return rc

    '''
    @description: unpack the given package file into the unpack dir
    @input infoDict: dictionary containing package information
    @output: 0 = all fine, >0 = error!
    '''
    def __unpack_package(self):

        if not self.infoDict['merge_from']:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Unpacking package: "+str(self.infoDict['atom']))
        else:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Merging package: "+str(self.infoDict['atom']))

        if os.path.isdir(self.infoDict['unpackdir']):
            shutil.rmtree(self.infoDict['unpackdir'].encode('raw_unicode_escape'))
        elif os.path.isfile(self.infoDict['unpackdir']):
            os.remove(self.infoDict['unpackdir'].encode('raw_unicode_escape'))
        os.makedirs(self.infoDict['imagedir'])

        if not os.path.isfile(self.infoDict['pkgpath']) and not self.infoDict['merge_from']:
            if os.path.isdir(self.infoDict['pkgpath']):
                shutil.rmtree(self.infoDict['pkgpath'])
            if os.path.islink(self.infoDict['pkgpath']):
                os.remove(self.infoDict['pkgpath'])
            self.infoDict['verified'] = False
            rc = self.fetch_step()
            if rc != 0: return rc

        if not self.infoDict['merge_from']:
            unpack_tries = 3
            while 1:
                unpack_tries -= 1
                try:
                    rc = self.entropyTools.spawnFunction(
                        self.entropyTools.uncompressTarBz2,
                        self.infoDict['pkgpath'],
                        self.infoDict['imagedir'],
                        catchEmpty = True
                    )
                except EOFError:
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"EOFError on "+self.infoDict['pkgpath'])
                    rc = 1
                except (UnicodeEncodeError,UnicodeDecodeError,):
                    # this will make devs to actually catch the right exception and prepare a fix
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Raising Unicode Error for "+self.infoDict['pkgpath'])
                    rc = self.entropyTools.uncompressTarBz2(
                        self.infoDict['pkgpath'],self.infoDict['imagedir'],
                        catchEmpty = True
                    )
                if rc == 0:
                    break
                if unpack_tries <= 0:
                    return rc
                # otherwise, try to download it again
                self.infoDict['verified'] = False
                f_rc = self.fetch_step()
                if f_rc != 0: return f_rc
        else:
            pid = os.fork()
            if pid > 0:
                os.waitpid(pid, 0)
            else:
                self.__fill_image_dir(self.infoDict['merge_from'],self.infoDict['imagedir'])
                os._exit(0)

        # unpack xpak ?
        if etpConst['gentoo-compat']:
            if os.path.isdir(self.infoDict['xpakpath']):
                shutil.rmtree(self.infoDict['xpakpath'])
            try:
                os.rmdir(self.infoDict['xpakpath'])
            except OSError:
                pass

            # create data dir where we'll unpack the xpak
            os.makedirs(self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'],0755)
            #os.mkdir(self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'])
            xpakPath = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakfilename']

            if not self.infoDict['merge_from']:
                if (self.infoDict['smartpackage']):
                    # we need to get the .xpak from database
                    xdbconn = self.Entropy.openRepositoryDatabase(self.infoDict['repository'])
                    xpakdata = xdbconn.retrieveXpakMetadata(self.infoDict['idpackage'])
                    if xpakdata:
                        # save into a file
                        f = open(xpakPath,"wb")
                        f.write(xpakdata)
                        f.flush()
                        f.close()
                        self.infoDict['xpakstatus'] = self.entropyTools.unpackXpak(
                            xpakPath,
                            self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                        )
                    else:
                        self.infoDict['xpakstatus'] = None
                    del xpakdata
                else:
                    self.infoDict['xpakstatus'] = self.entropyTools.extractXpak(
                        self.infoDict['pkgpath'],
                        self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                    )
            else:
                # link xpakdir to self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                tolink_dir = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                if os.path.isdir(tolink_dir):
                    shutil.rmtree(tolink_dir,True)
                # now link
                os.symlink(self.infoDict['xpakdir'],tolink_dir)

            # create fake portage ${D} linking it to imagedir
            portage_db_fakedir = os.path.join(
                self.infoDict['unpackdir'],
                "portage/"+self.infoDict['category'] + "/" + self.infoDict['name'] + "-" + self.infoDict['version']
            )

            os.makedirs(portage_db_fakedir,0755)
            # now link it to self.infoDict['imagedir']
            os.symlink(self.infoDict['imagedir'],os.path.join(portage_db_fakedir,"image"))

        return 0

    def __configure_package(self):

        try: Spm = self.Entropy.Spm()
        except: return 1

        spm_atom = self.infoDict['key']+"-"+self.infoDict['version']
        myebuild = Spm.get_vdb_path()+spm_atom+"/"+self.infoDict['key'].split("/")[1]+"-"+self.infoDict['version']+etpConst['spm']['source_build_ext']
        if not os.path.isfile(myebuild):
            return 2

        self.Entropy.updateProgress(
            brown(" Ebuild: pkg_config()"),
            importance = 0,
            header = red("   ##")
        )

        try:
            rc = Spm.spm_doebuild(
                myebuild,
                mydo = "config",
                tree = "bintree",
                cpv = spm_atom
            )
            if rc == 1:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] ATTENTION Cannot properly run Spm pkg_config() for " + \
                    str(spm_atom)+". Something bad happened."
                )
                return 3
        except Exception, e:
            self.entropyTools.printTraceback()
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[PRE] ATTENTION Cannot run Spm pkg_config() for "+spm_atom+"!! "+str(type(Exception))+": "+str(e)
            )
            mytxt = "%s: %s %s. %s. %s: %s, %s" % (
                bold(_("QA")),
                brown(_("Cannot run Spm pkg_config() for")),
                bold(str(spm_atom)),
                brown(_("Please report it")),
                bold(_("Error")),
                type(Exception),
                e,
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return 1

        return 0


    def __remove_package(self):

        # clear on-disk cache
        self.__clear_cache()

        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing package: %s" % (self.infoDict['removeatom'],))

        # remove from database
        if self.infoDict['removeidpackage'] != -1:
            mytxt = "%s: " % (_("Removing from Entropy"),)
            self.Entropy.updateProgress(
                blue(mytxt) + red(self.infoDict['removeatom']),
                importance = 1,
                type = "info",
                header = red("   ## ")
            )
            self.__remove_package_from_database()

        # Handle gentoo database
        if (etpConst['gentoo-compat']):
            gentooAtom = self.entropyTools.remove_tag(self.infoDict['removeatom'])
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing from Portage: "+str(gentooAtom))
            self.__remove_package_from_gentoo_database(gentooAtom)
            del gentooAtom

        self.__remove_content_from_system()
        return 0

    def __remove_content_from_system(self):

        # load CONFIG_PROTECT and its mask
        # client database at this point has been surely opened,
        # so our dicts are already filled
        protect = etpConst['dbconfigprotect']
        mask = etpConst['dbconfigprotectmask']
        sys_root = etpConst['systemroot']
        col_protect = etpConst['collisionprotect']

        # remove files from system
        directories = set()
        for item in self.infoDict['removecontent']:
            # collision check
            if col_protect > 0:

                if self.Entropy.clientDbconn.isFileAvailable(item) and os.path.isfile(sys_root+item):
                    # in this way we filter out directories
                    mytxt = red(_("Collision found during removal of")) + " " + sys_root+item + " - "
                    mytxt += red(_("cannot overwrite"))
                    self.Entropy.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "warning",
                        header = red("   ## ")
                    )
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "Collision found during remove of "+sys_root+item+" - cannot overwrite"
                    )
                    continue

            protected = False
            if (not self.infoDict['removeconfig']) and (not self.infoDict['diffremoval']):
                protected_item_test = sys_root+item
                if isinstance(protected_item_test,unicode):
                    protected_item_test = protected_item_test.encode('utf-8')
                protected, x, do_continue = self._handle_config_protect(protect, mask, None, protected_item_test, do_allocation_check = False)
                if do_continue: protected = True

            if protected:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_VERBOSE,
                    "[remove] Protecting config file: "+sys_root+item
                )
                mytxt = "[%s] %s: %s" % (
                    red(_("remove")),
                    brown(_("Protecting config file")),
                    sys_root+item,
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )
            else:
                try:
                    os.lstat(sys_root+item)
                except OSError:
                    continue # skip file, does not exist
                except UnicodeEncodeError:
                    mytxt = brown(_("This package contains a badly encoded file !!!"))
                    self.Entropy.updateProgress(
                        red("QA: ")+mytxt,
                        importance = 1,
                        type = "warning",
                        header = darkred("   ## ")
                    )
                    continue # file has a really bad encoding

                if os.path.isdir(sys_root+item) and os.path.islink(sys_root+item):
                    # S_ISDIR returns False for directory symlinks, so using os.path.isdir
                    # valid directory symlink
                    directories.add((sys_root+item,"link"))
                elif os.path.isdir(sys_root+item):
                    # plain directory
                    directories.add((sys_root+item,"dir"))
                else: # files, symlinks or not
                    # just a file or symlink or broken directory symlink (remove now)
                    try:
                        os.remove(sys_root+item)
                        # add its parent directory
                        dirfile = os.path.dirname(sys_root+item)
                        if os.path.isdir(dirfile) and os.path.islink(dirfile):
                            directories.add((dirfile,"link"))
                        elif os.path.isdir(dirfile):
                            directories.add((dirfile,"dir"))
                    except OSError:
                        pass

        # now handle directories
        directories = sorted(list(directories), reverse = True)
        while 1:
            taint = False
            for directory, dirtype in directories:
                mydir = "%s%s" % (sys_root,directory,)
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
        del directories


    '''
    @description: remove package entry from Gentoo database
    @input gentoo package atom (cat/name+ver):
    @output: 0 = all fine, <0 = error!
    '''
    def __remove_package_from_gentoo_database(self, atom):

        # handle gentoo-compat
        try:
            Spm = self.Entropy.Spm()
        except:
            return -1 # no Spm support ??

        portDbDir = Spm.get_vdb_path()
        removePath = portDbDir+atom
        key = self.entropyTools.dep_getkey(atom)
        others_installed = Spm.search_keys(key)
        slot = self.infoDict['slot']
        tag = self.infoDict['versiontag']
        if (tag == slot) and tag: slot = "0"
        if os.path.isdir(removePath):
            shutil.rmtree(removePath,True)
        elif others_installed:
            for myatom in others_installed:
                myslot = Spm.get_installed_package_slot(myatom)
                if myslot != slot:
                    continue
                shutil.rmtree(portDbDir+myatom,True)

        if not others_installed:
            world_file = Spm.get_world_file()
            world_file_tmp = world_file+".entropy.tmp"
            if os.access(world_file,os.W_OK) and os.path.isfile(world_file):
                new = open(world_file_tmp,"w")
                old = open(world_file,"r")
                line = old.readline()
                while line:
                    if line.find(key) != -1:
                        line = old.readline()
                        continue
                    if line.find(key+":"+slot) != -1:
                        line = old.readline()
                        continue
                    new.write(line)
                    line = old.readline()
                new.flush()
                new.close()
                old.close()
                shutil.move(world_file_tmp,world_file)

        return 0

    '''
    @description: function that runs at the end of the package installation process, just removes data left by other steps
    @output: 0 = all fine, >0 = error!
    '''
    def _cleanup_package(self, unpack_dir):
        # remove unpack dir
        shutil.rmtree(unpack_dir,True)
        try: os.rmdir(unpack_dir)
        except OSError: pass
        return 0

    def __remove_package_from_database(self):
        self.error_on_not_prepared()
        self.Entropy.clientDbconn.removePackage(self.infoDict['removeidpackage'])
        return 0

    def __clear_cache(self):
        self.Entropy.clear_dump_cache(etpCache['advisories'])
        self.Entropy.clear_dump_cache(etpCache['filter_satisfied_deps'])
        self.Entropy.clear_dump_cache(etpCache['depends_tree'])
        self.Entropy.clear_dump_cache(etpCache['check_package_update'])
        self.Entropy.clear_dump_cache(etpCache['dep_tree'])
        self.Entropy.clear_dump_cache(etpCache['dbMatch']+etpConst['clientdbid']+"/")
        self.Entropy.clear_dump_cache(etpCache['dbSearch']+etpConst['clientdbid']+"/")

        self.__update_available_cache()
        try:
            self.__update_world_cache()
        except:
            self.Entropy.clear_dump_cache(etpCache['world_update'])

    def __update_world_cache(self):
        if self.Entropy.xcache and (self.action in ("install","remove",)):
            wc_dir = os.path.dirname(os.path.join(etpConst['dumpstoragedir'],etpCache['world_update']))
            wc_filename = os.path.basename(etpCache['world_update'])
            wc_cache_files = [os.path.join(wc_dir,x) for x in os.listdir(wc_dir) if x.startswith(wc_filename)]
            for cache_file in wc_cache_files:

                try:
                    data = self.Entropy.dumpTools.loadobj(cache_file, completePath = True)
                    (update, remove, fine) = data['r']
                    empty_deps = data['empty_deps']
                except:
                    self.Entropy.clear_dump_cache(etpCache['world_update'])
                    return

                if empty_deps:
                    continue

                if self.action == "install":
                    if self.matched_atom in update:
                        update.remove(self.matched_atom)
                        self.Entropy.dumpTools.dumpobj(
                            cache_file,
                            {'r':(update, remove, fine),'empty_deps': empty_deps},
                            completePath = True
                        )
                else:
                    key, slot = self.Entropy.clientDbconn.retrieveKeySlot(self.infoDict['removeidpackage'])
                    matches = self.Entropy.atomMatch(key, matchSlot = slot, multiMatch = True, multiRepo = True)
                    if matches[1] != 0:
                        # hell why! better to rip all off
                        self.Entropy.clear_dump_cache(etpCache['world_update'])
                        return
                    taint = False
                    for match in matches[0]:
                        if match in update:
                            taint = True
                            update.remove(match)
                        if match in remove:
                            taint = True
                            remove.remove(match)
                    if taint:
                        self.Entropy.dumpTools.dumpobj(
                            cache_file,
                            {'r':(update, remove, fine),'empty_deps': empty_deps},
                            completePath = True
                        )

        elif (not self.Entropy.xcache) or (self.action in ("install",)):
            self.Entropy.clear_dump_cache(etpCache['world_update'])

    def __update_available_cache(self):

        # update world available cache
        if self.Entropy.xcache and (self.action in ("remove","install")):

            disk_cache = self.Cacher.pop(etpCache['world_available'])
            if disk_cache != None:
                c_hash = self.Entropy.get_available_packages_chash(etpConst['branch'])
                try:
                    if disk_cache['chash'] == c_hash:

                        # remove and old install
                        if self.infoDict['removeidpackage'] != -1:
                            taint = False
                            key = self.entropyTools.dep_getkey(self.infoDict['removeatom'])
                            slot = self.infoDict['slot']
                            matches = self.Entropy.atomMatch(key, matchSlot = slot, multiRepo = True, multiMatch = True)
                            if matches[1] == 0:
                                for mymatch in matches[0]:
                                    if mymatch not in disk_cache['available']:
                                        disk_cache['available'].append(mymatch)
                                        taint = True
                            if taint:
                                mydata = {}
                                mylist = []
                                for myidpackage,myrepo in disk_cache['available']:
                                    mydbc = self.Entropy.openRepositoryDatabase(myrepo)
                                    mydata[mydbc.retrieveAtom(myidpackage)] = (myidpackage,myrepo)
                                mykeys = sorted(mydata.keys())
                                for mykey in mykeys:
                                    mylist.append(mydata[mykey])
                                disk_cache['available'] = mylist

                        # install, doing here because matches[0] could contain self.matched_atoms
                        if self.matched_atom in disk_cache['available']:
                            disk_cache['available'].remove(self.matched_atom)

                        self.Cacher.push(etpCache['world_available'],disk_cache)

                except KeyError:
                    self.Cacher.push(etpCache['world_available'],{})

        elif not self.Entropy.xcache:
            self.Entropy.clear_dump_cache(etpCache['world_available'])


    '''
    @description: install unpacked files, update database and also update gentoo db if requested
    @output: 0 = all fine, >0 = error!
    '''
    def __install_package(self):

        # clear on-disk cache
        self.__clear_cache()

        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "Installing package: %s" % (self.infoDict['atom'],)
        )

        # copy files over - install
        # use fork? (in this case all the changed structures need to be pushed back)
        rc = self.__move_image_to_system()
        if rc != 0:
            return rc

        # inject into database
        mytxt = "%s: %s" % (blue(_("Updating database")),red(self.infoDict['atom']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        newidpackage = self._install_package_into_database()

        # remove old files and gentoo stuff
        if (self.infoDict['removeidpackage'] != -1):
            # doing a diff removal
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Remove old package: %s" % (self.infoDict['removeatom'],)
            )
            self.infoDict['removeidpackage'] = -1 # disabling database removal

            if etpConst['gentoo-compat']:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "Removing Entropy and Gentoo database entry for %s" % (self.infoDict['removeatom'],)
                )
            else:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "Removing Entropy (only) database entry for %s" % (self.infoDict['removeatom'],)
                )

            self.Entropy.updateProgress(
                                    blue(_("Cleaning old package files...")),
                                    importance = 1,
                                    type = "info",
                                    header = red("   ## ")
                                )
            self.__remove_package()

        rc = 0
        if etpConst['gentoo-compat']:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Installing new Gentoo database entry: %s" % (self.infoDict['atom'],)
            )
            rc = self._install_package_into_gentoo_database(newidpackage)

        return rc

    '''
    @description: inject the database information into the Gentoo database
    @output: 0 = all fine, !=0 = error!
    '''
    def _install_package_into_gentoo_database(self, newidpackage):

        # handle gentoo-compat
        try:
            Spm = self.Entropy.Spm()
        except:
            return -1 # no Portage support
        portDbDir = Spm.get_vdb_path()
        if os.path.isdir(portDbDir):

            # extract xpak from unpackDir+etpConst['packagecontentdir']+"/"+package
            key = self.infoDict['category']+"/"+self.infoDict['name']
            atomsfound = set()
            dbdirs = os.listdir(portDbDir)
            if self.infoDict['category'] in dbdirs:
                catdirs = os.listdir(portDbDir+"/"+self.infoDict['category'])
                dirsfound = set([self.infoDict['category']+"/"+x for x in catdirs if \
                    key == self.entropyTools.dep_getkey(self.infoDict['category']+"/"+x)])
                atomsfound.update(dirsfound)

            ### REMOVE
            # parse slot and match and remove
            if atomsfound:
                pkgToRemove = ''
                for atom in atomsfound:
                    atomslot = Spm.get_installed_package_slot(atom)
                    # get slot from gentoo db
                    if atomslot == self.infoDict['slot']:
                        pkgToRemove = atom
                        break
                if (pkgToRemove):
                    removePath = portDbDir+pkgToRemove
                    shutil.rmtree(removePath,True)
                    try:
                        os.rmdir(removePath)
                    except OSError:
                        pass
            del atomsfound

            # we now install it
            if ((self.infoDict['xpakstatus'] != None) and \
                    os.path.isdir( self.infoDict['xpakpath'] + "/" + etpConst['entropyxpakdatarelativepath'])) or \
                    self.infoDict['merge_from']:

                if self.infoDict['merge_from']:
                    copypath = self.infoDict['xpakdir']
                    if not os.path.isdir(copypath):
                        return 0
                else:
                    copypath = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']

                if not os.path.isdir(portDbDir+self.infoDict['category']):
                    os.makedirs(portDbDir+self.infoDict['category'],0755)
                destination = portDbDir+self.infoDict['category']+"/"+self.infoDict['name']+"-"+self.infoDict['version']
                if os.path.isdir(destination):
                    shutil.rmtree(destination)

                try:
                    shutil.copytree(copypath,destination)
                except (IOError,), e:
                    mytxt = "%s: %s: %s: %s" % (red(_("QA")),
                        brown(_("Cannot update Portage database to destination")),
                        purple(destination),e,)
                    self.Entropy.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "warning",
                        header = darkred("   ## ")
                    )

                # test if /var/cache/edb/counter is fine
                if os.path.isfile(etpConst['edbcounter']):
                    try:
                        f = open(etpConst['edbcounter'],"r")
                        counter = int(f.readline().strip())
                        f.close()
                    except:
                        # need file recreation, parse gentoo tree
                        counter = Spm.refill_counter()
                else:
                    counter = Spm.refill_counter()

                # write new counter to file
                if os.path.isdir(destination):
                    counter += 1
                    f = open(destination+"/"+etpConst['spm']['xpak_entries']['counter'],"w")
                    f.write(str(counter))
                    f.flush()
                    f.close()
                    f = open(etpConst['edbcounter'],"w")
                    f.write(str(counter))
                    f.flush()
                    f.close()
                    # update counter inside clientDatabase
                    self.Entropy.clientDbconn.insertCounter(newidpackage,counter)
                else:
                    mytxt = brown(_("Cannot update Portage counter, destination %s does not exist.") % (destination,))
                    self.Entropy.updateProgress(
                        red("QA: ")+mytxt,
                        importance = 1,
                        type = "warning",
                        header = darkred("   ## ")
                    )

            # add to Portage world
            # key: key
            # slot: self.infoDict['slot']
            myslot = self.infoDict['slot']
            if (self.infoDict['versiontag'] == self.infoDict['slot']) and self.infoDict['versiontag']:
                # usually kernel packages
                myslot = "0"
            keyslot = key+":"+myslot
            world_file = Spm.get_world_file()
            world_atoms = set()

            if os.access(world_file,os.R_OK) and os.path.isfile(world_file):
                f = open(world_file,"r")
                world_atoms = set([x.strip() for x in f.readlines() if x.strip()])
                f.close()
            else:
                mytxt = brown(_("Cannot update Portage world file, destination %s does not exist.") % (world_file,))
                self.Entropy.updateProgress(
                    red("QA: ")+mytxt,
                    importance = 1,
                    type = "warning",
                    header = darkred("   ## ")
                )
                return 0

            try:
                if keyslot not in world_atoms and \
                    os.access(os.path.dirname(world_file),os.W_OK) and \
                    self.entropyTools.istextfile(world_file):
                        world_atoms.discard(key)
                        world_atoms.add(keyslot)
                        world_atoms = sorted(list(world_atoms))
                        world_file_tmp = world_file+".entropy_inst"
                        f = open(world_file_tmp,"w")
                        for item in world_atoms:
                            f.write(item+"\n")
                        f.flush()
                        f.close()
                        shutil.move(world_file_tmp,world_file)
            except (UnicodeDecodeError,UnicodeEncodeError), e:
                self.entropyTools.printTraceback(f = self.Entropy.clientLog)
                mytxt = brown(_("Cannot update Portage world file, destination %s is corrupted.") % (world_file,))
                self.Entropy.updateProgress(
                    red("QA: ")+mytxt+": "+unicode(e),
                    importance = 1,
                    type = "warning",
                    header = darkred("   ## ")
                )

        return 0

    '''
    @description: injects package info into the installed packages database
    @output: 0 = all fine, >0 = error!
    '''
    def _install_package_into_database(self):

        # fetch info
        dbconn = self.Entropy.openRepositoryDatabase(self.infoDict['repository'])
        data = dbconn.getPackageData(self.infoDict['idpackage'], content_insert_formatted = True)
        # open client db
        # always set data['injected'] to False
        # installed packages database SHOULD never have more than one package for scope (key+slot)
        data['injected'] = False
        data['counter'] = -1 # gentoo counter will be set in self._install_package_into_gentoo_database()

        idpackage, rev, x = self.Entropy.clientDbconn.handlePackage(
            etpData = data, forcedRevision = data['revision'],
            formattedContent = True)

        # update datecreation
        ctime = self.entropyTools.getCurrentUnixTime()
        self.Entropy.clientDbconn.setDateCreation(idpackage, str(ctime))

        # add idpk to the installedtable
        self.Entropy.clientDbconn.removePackageFromInstalledTable(idpackage)
        self.Entropy.clientDbconn.addPackageToInstalledTable(idpackage,self.infoDict['repository'])

        # clear depends table, this will make clientdb dependstable to be regenerated during the next request (retrieveDepends)
        self.Entropy.clientDbconn.clearDependsTable()
        return idpackage

    def __fill_image_dir(self, mergeFrom, imageDir):

        dbconn = self.Entropy.openRepositoryDatabase(self.infoDict['repository'])
        package_content = dbconn.retrieveContent(self.infoDict['idpackage'], extended = True, formatted = True)
        contents = sorted(package_content)

        # collect files
        for path in contents:
            # convert back to filesystem str
            encoded_path = path
            path = os.path.join(mergeFrom,encoded_path[1:])
            topath = os.path.join(imageDir,encoded_path[1:])
            path = path.encode('raw_unicode_escape')
            topath = topath.encode('raw_unicode_escape')

            try:
                exist = os.lstat(path)
            except OSError:
                continue # skip file
            ftype = package_content[encoded_path]
            if str(ftype) == '0': ftype = 'dir' # force match below, '0' means databases without ftype
            if 'dir' == ftype and \
                not stat.S_ISDIR(exist.st_mode) and \
                os.path.isdir(path): # workaround for directory symlink issues
                path = os.path.realpath(path)

            copystat = False
            # if our directory is a symlink instead, then copy the symlink
            if os.path.islink(path):
                tolink = os.readlink(path)
                if os.path.islink(topath):
                    os.remove(topath)
                os.symlink(tolink,topath)
            elif os.path.isdir(path):
                if not os.path.isdir(topath):
                    os.makedirs(topath)
                    copystat = True
            elif os.path.isfile(path):
                if os.path.isfile(topath):
                    os.remove(topath) # should never happen
                shutil.copy2(path,topath)
                copystat = True

            if copystat:
                user = os.stat(path)[stat.ST_UID]
                group = os.stat(path)[stat.ST_GID]
                os.chown(topath,user,group)
                shutil.copystat(path,topath)


    def __move_image_to_system(self):

        # load CONFIG_PROTECT and its mask
        protect = etpRepositories[self.infoDict['repository']]['configprotect']
        mask = etpRepositories[self.infoDict['repository']]['configprotectmask']
        sys_root = etpConst['systemroot']
        col_protect = etpConst['collisionprotect']
        items_installed = set()

        # setup imageDir properly
        imageDir = self.infoDict['imagedir']
        encoded_imageDir = imageDir.encode('utf-8')
        movefile = self.entropyTools.movefile

        # merge data into system
        for currentdir,subdirs,files in os.walk(encoded_imageDir):
            # create subdirs
            for subdir in subdirs:

                imagepathDir = "%s/%s" % (currentdir,subdir,)
                rootdir = "%s%s" % (sys_root,imagepathDir[len(imageDir):],)

                # handle broken symlinks
                if os.path.islink(rootdir) and not os.path.exists(rootdir):# broken symlink
                    os.remove(rootdir)

                # if our directory is a file on the live system
                elif os.path.isfile(rootdir): # really weird...!
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "WARNING!!! %s is a file when it should be a directory !! Removing in 20 seconds..." % (rootdir,)
                    )
                    mytxt = darkred(_("%s is a file when should be a directory !! Removing in 20 seconds...") % (rootdir,))
                    self.Entropy.updateProgress(
                        red("QA: ")+mytxt,
                        importance = 1,
                        type = "warning",
                        header = red(" !!! ")
                    )
                    self.entropyTools.ebeep(20)
                    os.remove(rootdir)

                # if our directory is a symlink instead, then copy the symlink
                if os.path.islink(imagepathDir) and not os.path.isdir(rootdir):
                    # for security we skip live items that are dirs
                    tolink = os.readlink(imagepathDir)
                    if os.path.islink(rootdir):
                        os.remove(rootdir)
                    os.symlink(tolink,rootdir)
                elif (not os.path.isdir(rootdir)) and (not os.access(rootdir,os.R_OK)):
                    try:
                        # we should really force a simple mkdir first of all
                        os.mkdir(rootdir)
                    except OSError:
                        os.makedirs(rootdir)

                if not os.path.islink(rootdir) and os.access(rootdir,os.W_OK):
                    # symlink doesn't need permissions, also until os.walk ends they might be broken
                    # XXX also, added os.access() check because there might be directories/files unwritable
                    # what to do otherwise?
                    user = os.stat(imagepathDir)[stat.ST_UID]
                    group = os.stat(imagepathDir)[stat.ST_GID]
                    os.chown(rootdir,user,group)
                    shutil.copystat(imagepathDir,rootdir)

                items_installed.add(os.path.join(os.path.realpath(os.path.dirname(rootdir)),os.path.basename(rootdir)))

            for item in files:

                fromfile = "%s/%s" % (currentdir,item,)
                tofile = "%s%s" % (sys_root,fromfile[len(imageDir):],)

                if col_protect > 1:
                    todbfile = fromfile[len(imageDir):]
                    myrc = self._handle_install_collision_protect(tofile, todbfile)
                    if not myrc:
                        continue

                protected, tofile, do_continue = self._handle_config_protect(protect, mask, fromfile, tofile)
                if do_continue:
                    continue

                try:

                    if os.path.realpath(fromfile) == os.path.realpath(tofile) and os.path.islink(tofile):
                        # there is a serious issue here, better removing tofile, happened to someone:
                        try: # try to cope...
                            os.remove(tofile)
                        except OSError:
                            pass

                    # if our file is a dir on the live system
                    if os.path.isdir(tofile) and not os.path.islink(tofile): # really weird...!
                        self.Entropy.clientLog.log(
                            ETP_LOGPRI_INFO,
                            ETP_LOGLEVEL_NORMAL,
                            "WARNING!!! %s is a directory when it should be a file !! Removing in 20 seconds..." % (tofile,)
                        )
                        mytxt = _("%s is a directory when it should be a file !! Removing in 20 seconds...") % (tofile,)
                        self.Entropy.updateProgress(
                            red("QA: ")+darkred(mytxt),
                            importance = 1,
                            type = "warning",
                            header = red(" !!! ")
                        )
                        self.entropyTools.ebeep(10)
                        time.sleep(20)
                        try:
                            shutil.rmtree(tofile, True)
                            os.rmdir(tofile)
                        except:
                            pass
                        try: # if it was a link
                            os.remove(tofile)
                        except OSError:
                            pass

                    # XXX
                    # XXX moving file using the raw format like portage does
                    # XXX
                    done = movefile(fromfile, tofile, src_basedir = encoded_imageDir)
                    if not done:
                        self.Entropy.clientLog.log(
                            ETP_LOGPRI_INFO,
                            ETP_LOGLEVEL_NORMAL,
                            "WARNING!!! Error during file move to system: %s => %s" % (fromfile,tofile,)
                        )
                        mytxt = "%s: %s => %s, %s" % (_("File move error"),fromfile,tofile,_("please report"),)
                        self.Entropy.updateProgress(
                            red("QA: ")+darkred(mytxt),
                            importance = 1,
                            type = "warning",
                            header = red(" !!! ")
                        )
                        return 4

                except IOError, e:
                    # try to move forward, sometimes packages might be
                    # fucked up and contain broken things
                    if e.errno != 2: raise

                items_installed.add(os.path.join(os.path.realpath(os.path.dirname(tofile)),os.path.basename(tofile)))
                if protected:
                    # add to disk cache
                    self.Entropy.FileUpdates.add_to_cache(tofile, quiet = True)

        # this is useful to avoid the removal of installed files by __remove_package just because
        # there's a difference in the directory path, perhaps, which is not handled correctly by
        # LocalRepository.contentDiff for obvious reasons (think about stuff in /usr/lib and /usr/lib64,
        # where the latter is just a symlink to the former)
        if self.infoDict.get('removecontent'):
            my_remove_content = set([x for x in self.infoDict['removecontent'] \
                if os.path.join(os.path.realpath(
                    os.path.dirname("%s%s" % (sys_root,x,))),os.path.basename(x)
                ) in items_installed])
            self.infoDict['removecontent'] -= my_remove_content

        return 0

    def _handle_config_protect(self, protect, mask, fromfile, tofile, do_allocation_check = True):

        protected = False
        tofile_before_protect = tofile
        do_continue = False

        try:
            encoded_protect = [x.encode('raw_unicode_escape') for x in protect]
            if tofile in encoded_protect:
                protected = True
            elif os.path.dirname(tofile) in encoded_protect:
                protected = True
            else:
                tofile_testdir = os.path.dirname(tofile)
                old_tofile_testdir = None
                while tofile_testdir != old_tofile_testdir:
                    if tofile_testdir in encoded_protect:
                        protected = True
                        break
                    old_tofile_testdir = tofile_testdir
                    tofile_testdir = os.path.dirname(tofile_testdir)

            if protected: # check if perhaps, file is masked, so unprotected
                newmask = [x.encode('raw_unicode_escape') for x in mask]
                if tofile in newmask:
                    protected = False
                elif os.path.dirname(tofile) in newmask:
                    protected = False

            if not os.path.lexists(tofile):
                protected = False # file doesn't exist

            # check if it's a text file
            if (protected) and os.path.isfile(tofile):
                protected = self.entropyTools.istextfile(tofile)
            else:
                protected = False # it's not a file

            # request new tofile then
            if protected:
                if tofile not in etpConst['configprotectskip']:
                    prot_status = True
                    if do_allocation_check:
                        tofile, prot_status = self.entropyTools.allocateMaskedFile(tofile, fromfile)
                    if not prot_status:
                        protected = False
                    else:
                        oldtofile = tofile
                        if oldtofile.find("._cfg") != -1:
                            oldtofile = os.path.dirname(oldtofile)+"/"+os.path.basename(oldtofile)[10:]
                        self.Entropy.clientLog.log(
                            ETP_LOGPRI_INFO,
                            ETP_LOGLEVEL_NORMAL,
                            "Protecting config file: %s" % (oldtofile,)
                        )
                        mytxt = red("%s: %s") % (_("Protecting config file"),oldtofile,)
                        self.Entropy.updateProgress(
                            mytxt,
                            importance = 1,
                            type = "warning",
                            header = darkred("   ## ")
                        )
                else:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "Skipping config file installation/removal, as stated in equo.conf: %s" % (tofile,)
                    )
                    mytxt = "%s: %s" % (_("Skipping file installation/removal"),tofile,)
                    self.Entropy.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "warning",
                        header = darkred("   ## ")
                    )
                    do_continue = True

        except Exception, e:
            self.entropyTools.printTraceback()
            protected = False # safely revert to false
            tofile = tofile_before_protect
            mytxt = darkred("%s: %s") % (_("Cannot check CONFIG PROTECTION. Error"),e,)
            self.Entropy.updateProgress(
                red("QA: ")+mytxt,
                importance = 1,
                type = "warning",
                header = darkred("   ## ")
            )

        return protected, tofile, do_continue


    def _handle_install_collision_protect(self, tofile, todbfile):
        avail = self.Entropy.clientDbconn.isFileAvailable(todbfile, get_id = True)
        if (self.infoDict['removeidpackage'] not in avail) and avail:
            mytxt = darkred(_("Collision found during install for"))
            mytxt += " %s - %s" % (blue(tofile),darkred(_("cannot overwrite")),)
            self.Entropy.updateProgress(
                red("QA: ")+mytxt,
                importance = 1,
                type = "warning",
                header = darkred("   ## ")
            )
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "WARNING!!! Collision found during install for %s - cannot overwrite" % (tofile,)
            )
            return False
        return True

    def sources_fetch_step(self):
        self.error_on_not_prepared()
        down_data = self.infoDict['download']
        d_cache = set()
        for key in sorted(down_data.keys()):
            rc = 1
            key_name = os.path.basename(key)
            if key_name in d_cache: continue
            # first fine wins
            for url in down_data[key]:
                file_name = os.path.basename(url)
                dest_file = os.path.join(self.infoDict['unpackdir'],file_name)
                rc = self._fetch_source(url, dest_file)
                if rc == 0: break
            if rc != 0: break
            d_cache.add(key_name)

        return rc

    def _fetch_source(self, url, dest_file):
        rc = 1
        try:
            mytxt = "%s: %s" % (blue(_("Downloading")),brown(url),)
            # now fetch the new one
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red("   ## ")
            )

            rc, data_transfer, resumed = self.Entropy.fetch_file(
                url,
                None,
                None,
                False,
                fetch_file_abort_function = self.fetch_abort_function,
                filepath = dest_file
            )
            if rc == 0:
                mytxt = blue("%s: ") % (_("Successfully downloaded from"),)
                mytxt += red(self.entropyTools.spliturl(url)[1])
                mytxt += " %s %s/%s" % (_("at"),self.entropyTools.bytesIntoHuman(data_transfer),_("second"),)
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = red("   ## ")
                )
                self.Entropy.updateProgress(
                    "%s: %s" % (blue(_("Local path")),brown(dest_file),),
                    importance = 1,
                    type = "info",
                    header = red("      # ")
                )
            else:
                error_message = blue("%s: %s") % (
                    _("Error downloading from"),
                    red(self.entropyTools.spliturl(url)[1]),
                )
                # something bad happened
                if rc == -1:
                    error_message += " - %s." % (_("file not available on this mirror"),)
                elif rc == -3:
                    error_message += " - not found."
                elif rc == -100:
                    error_message += " - %s." % (_("discarded download"),)
                else:
                    error_message += " - %s: %s" % (_("unknown reason"),rc,)
                self.Entropy.updateProgress(
                                    error_message,
                                    importance = 1,
                                    type = "warning",
                                    header = red("   ## ")
                                )
        except KeyboardInterrupt:
            pass
        return rc

    def fetch_step(self):
        self.error_on_not_prepared()
        mytxt = "%s: %s" % (blue(_("Downloading archive")),red(os.path.basename(self.infoDict['download'])),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )

        rc = 0
        if not self.infoDict['verified']:
            rc = self.Entropy.fetch_file_on_mirrors(
                self.infoDict['repository'],
                self.Entropy.get_branch_from_download_relative_uri(self.infoDict['download']),
                self.infoDict['download'],
                self.infoDict['checksum'],
                fetch_abort_function = self.fetch_abort_function
            )
        if rc != 0:
            mytxt = "%s. %s: %s" % (
                red(_("Package cannot be fetched. Try to update repositories and retry")),
                blue(_("Error")),
                rc,
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = darkred("   ## ")
            )
        return rc

    def multi_fetch_step(self):
        self.error_on_not_prepared()
        m_fetch_len = len(self.infoDict['multi_fetch_list'])
        mytxt = "%s: %s %s" % (blue(_("Downloading")),darkred(str(m_fetch_len)),_("archives"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        # fetch_files_on_mirrors(self, download_list, checksum = False, fetch_abort_function = None)
        rc, err_list = self.Entropy.fetch_files_on_mirrors(
            self.infoDict['multi_fetch_list'],
            self.infoDict['checksum'],
            fetch_abort_function = self.fetch_abort_function
        )
        if rc != 0:
            mytxt = "%s. %s: %s" % (
                red(_("Some packages cannot be fetched. Try to update repositories and retry")),
                blue(_("Error")),
                rc,
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = darkred("   ## ")
            )
            for repo,branch,fname,cksum in err_list:
                self.Entropy.updateProgress(
                    "[%s:%s|%s] %s" % (blue(repo),brown(branch),
                        darkgreen(cksum),darkred(fname),),
                    importance = 1,
                    type = "error",
                    header = darkred("    # ")
                )
        return rc

    def fetch_not_available_step(self):
        self.Entropy.updateProgress(
            blue(_("Fetch for the chosen package is not available, unknown error.")),
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        return 0

    def vanished_step(self):
        self.Entropy.updateProgress(
            blue(_("Installed package in queue vanished, skipping.")),
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        return 0

    def checksum_step(self):
        self.error_on_not_prepared()
        return self.match_checksum()

    def multi_checksum_step(self):
        self.error_on_not_prepared()
        return self.multi_match_checksum()

    def unpack_step(self):
        self.error_on_not_prepared()

        if not self.infoDict['merge_from']:
            mytxt = "%s: %s" % (blue(_("Unpacking package")),red(os.path.basename(self.infoDict['download'])),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red("   ## ")
        )
        else:
            mytxt = "%s: %s" % (blue(_("Merging package")),red(os.path.basename(self.infoDict['atom'])),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
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
                errormsg = "%s. %s. %s: %s" % (
                    red(_("An error occured while trying to unpack the package")),
                    red(_("Check if your system is healthy")),
                    blue(_("Error")),
                    rc,
                )
            self.Entropy.updateProgress(
                errormsg,
                importance = 1,
                type = "error",
                header = red("   ## ")
            )
        return rc

    def install_step(self):
        self.error_on_not_prepared()
        mytxt = "%s: %s" % (blue(_("Installing package")),red(self.infoDict['atom']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
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
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = red("   ## ")
            )
        return rc

    def remove_step(self):
        self.error_on_not_prepared()
        mytxt = "%s: %s" % (blue(_("Removing data")),red(self.infoDict['removeatom']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
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
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = red("   ## ")
            )
        return rc

    def cleanup_step(self):
        self.error_on_not_prepared()
        mytxt = "%s: %s" % (blue(_("Cleaning")),red(self.infoDict['atom']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        self._cleanup_package(self.infoDict['unpackdir'])
        # we don't care if cleanupPackage fails since it's not critical
        return 0

    def logmessages_step(self):
        for msg in self.infoDict['messages']:
            self.Entropy.clientLog.write(">>>  "+msg)
        return 0

    def messages_step(self):
        self.error_on_not_prepared()
        # get messages
        if self.infoDict['messages']:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Message from %s:" % (self.infoDict['atom'],)
            )
            mytxt = "%s:" % (darkgreen(_("Compilation messages")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "warning",
                header = brown("   ## ")
            )
        for msg in self.infoDict['messages']:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,msg)
            self.Entropy.updateProgress(
                msg,
                importance = 0,
                type = "warning",
                header = brown("   ## ")
            )
        if self.infoDict['messages']:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"End message.")

    def postinstall_step(self):
        self.error_on_not_prepared()
        pkgdata = self.infoDict['triggers'].get('install')
        if pkgdata:
            trigger = self.Entropy.Triggers('postinstall',pkgdata, self.action)
            trigger.prepare()
            trigger.run()
            trigger.kill()
        del pkgdata
        return 0

    def preinstall_step(self):
        self.error_on_not_prepared()
        pkgdata = self.infoDict['triggers'].get('install')
        if pkgdata:

            trigger = self.Entropy.Triggers('preinstall',pkgdata, self.action)
            trigger.prepare()
            if self.infoDict.get("diffremoval"):
                # diffremoval is true only when the
                # removal is triggered by a package install
                remdata = self.infoDict['triggers'].get('remove')
                if remdata:
                    r_trigger = self.Entropy.Triggers('preremove',remdata, self.action)
                    r_trigger.prepare()
                    r_trigger.triggers = [x for x in trigger.triggers if x not in r_trigger.triggers]
                    r_trigger.kill()
                del remdata
            trigger.run()
            trigger.kill()

        del pkgdata
        return 0

    def preremove_step(self):
        self.error_on_not_prepared()
        remdata = self.infoDict['triggers'].get('remove')
        if remdata:
            trigger = self.Entropy.Triggers('preremove',remdata, self.action)
            trigger.prepare()
            trigger.run()
            trigger.kill()
        del remdata
        return 0

    def postremove_step(self):
        self.error_on_not_prepared()
        remdata = self.infoDict['triggers'].get('remove')
        if remdata:

            trigger = self.Entropy.Triggers('postremove',remdata, self.action)
            trigger.prepare()
            if self.infoDict['diffremoval'] and (self.infoDict.get("atom") != None):
                # diffremoval is true only when the remove action is triggered by installPackages()
                pkgdata = self.infoDict['triggers'].get('install')
                if pkgdata:
                    i_trigger = self.Entropy.Triggers('postinstall',pkgdata, self.action)
                    i_trigger.prepare()
                    i_trigger.triggers = [x for x in trigger.triggers if x not in i_trigger.triggers]
                    i_trigger.kill()
                del pkgdata
            trigger.run()
            trigger.kill()

        del remdata
        return 0

    def removeconflict_step(self):
        self.error_on_not_prepared()
        for idpackage in self.infoDict['conflicts']:
            if not self.Entropy.clientDbconn.isIDPackageAvailable(idpackage):
                continue
            pkg = self.Entropy.Package()
            pkg.prepare((idpackage,),"remove_conflict", self.infoDict['remove_metaopts'])
            rc = pkg.run(xterm_header = self.xterm_title)
            pkg.kill()
            if rc != 0:
                return rc

        return 0

    def config_step(self):
        self.error_on_not_prepared()
        mytxt = "%s: %s" % (blue(_("Configuring package")),red(self.infoDict['atom']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        rc = self.__configure_package()
        if rc == 1:
            mytxt = "%s. %s. %s: %s" % (
                red(_("An error occured while trying to configure the package")),
                red(_("Make sure that your system is healthy")),
                blue(_("Error")),
                rc,
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = red("   ## ")
            )
        elif rc == 2:
            mytxt = "%s. %s. %s: %s" % (
                red(_("An error occured while trying to configure the package")),
                red(_("It seems that the Source Package Manager entry is missing")),
                blue(_("Error")),
                rc,
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = red("   ## ")
            )
        return rc

    def run_stepper(self, xterm_header):
        if xterm_header == None:
            xterm_header = ""

        if self.infoDict.has_key('remove_installed_vanished'):
            self.xterm_title += ' Installed package vanished'
            self.Entropy.setTitle(self.xterm_title)
            rc = self.vanished_step()
            return rc

        if self.infoDict.has_key('fetch_not_available'):
            self.xterm_title += ' Fetch not available'
            self.Entropy.setTitle(self.xterm_title)
            rc = self.fetch_not_available_step()
            return rc

        def do_fetch():
            self.xterm_title += ' %s: %s' % (_("Fetching"),os.path.basename(self.infoDict['download']),)
            self.Entropy.setTitle(self.xterm_title)
            return self.fetch_step()

        def do_multi_fetch():
            self.xterm_title += ' %s: %s %s' % (_("Multi Fetching"),
                len(self.infoDict['multi_fetch_list']),_("packages"),)
            self.Entropy.setTitle(self.xterm_title)
            return self.multi_fetch_step()

        def do_sources_fetch():
            self.xterm_title += ' %s: %s' % (_("Fetching sources"),os.path.basename(self.infoDict['atom']),)
            self.Entropy.setTitle(self.xterm_title)
            return self.sources_fetch_step()

        def do_checksum():
            self.xterm_title += ' %s: %s' % (_("Verifying"),os.path.basename(self.infoDict['download']),)
            self.Entropy.setTitle(self.xterm_title)
            return self.checksum_step()

        def do_multi_checksum():
            self.xterm_title += ' %s: %s %s' % (_("Multi Verification"),
                len(self.infoDict['multi_checksum_list']),_("packages"),)
            self.Entropy.setTitle(self.xterm_title)
            return self.multi_checksum_step()

        def do_unpack():
            if not self.infoDict['merge_from']:
                mytxt = _("Unpacking")
                self.xterm_title += ' %s: %s' % (mytxt,os.path.basename(self.infoDict['download']),)
            else:
                mytxt = _("Merging")
                self.xterm_title += ' %s: %s' % (mytxt,os.path.basename(self.infoDict['atom']),)
            self.Entropy.setTitle(self.xterm_title)
            return self.unpack_step()

        def do_remove_conflicts():
            return self.removeconflict_step()

        def do_install():
            self.xterm_title += ' %s: %s' % (_("Installing"),self.infoDict['atom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.install_step()

        def do_remove():
            self.xterm_title += ' %s: %s' % (_("Removing"),self.infoDict['removeatom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.remove_step()

        def do_showmessages():
            return self.messages_step()

        def do_logmessages():
            return self.logmessages_step()

        def do_cleanup():
            self.xterm_title += ' %s: %s' % (_("Cleaning"),self.infoDict['atom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.cleanup_step()

        def do_postinstall():
            self.xterm_title += ' %s: %s' % (_("Postinstall"),self.infoDict['atom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.postinstall_step()

        def do_preinstall():
            self.xterm_title += ' %s: %s' % (_("Preinstall"),self.infoDict['atom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.preinstall_step()

        def do_preremove():
            self.xterm_title += ' %s: %s' % (_("Preremove"),self.infoDict['removeatom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.preremove_step()

        def do_postremove():
            self.xterm_title += ' %s: %s' % (_("Postremove"),self.infoDict['removeatom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.postremove_step()

        def do_config():
            self.xterm_title += ' %s: %s' % (_("Configuring"),self.infoDict['atom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.config_step()

        steps_data = {
            "fetch": do_fetch,
            "multi_fetch": do_multi_fetch,
            "multi_checksum": do_multi_checksum,
            "sources_fetch": do_sources_fetch,
            "checksum": do_checksum,
            "unpack": do_unpack,
            "remove_conflicts": do_remove_conflicts,
            "install": do_install,
            "remove": do_remove,
            "showmessages": do_showmessages,
            "logmessages": do_logmessages,
            "cleanup": do_cleanup,
            "postinstall": do_postinstall,
            "preinstall": do_preinstall,
            "postremove": do_postremove,
            "preremove": do_preremove,
            "config": do_config,
        }

        rc = 0
        for step in self.infoDict['steps']:
            self.xterm_title = xterm_header
            rc = steps_data.get(step)()
            if rc != 0: break
        return rc


    '''
        @description: execute the requested steps
        @input xterm_header: purely optional
    '''
    def run(self, xterm_header = None):
        self.error_on_not_prepared()

        gave_up = self.Entropy.lock_check(self.Entropy._resources_run_check_lock)
        if gave_up:
            return 20

        locked = self.Entropy.application_lock_check()
        if locked:
            self.Entropy._resources_run_remove_lock()
            return 21

        # lock
        self.Entropy._resources_run_create_lock()

        try:
            rc = self.run_stepper(xterm_header)
        except:
            self.Entropy._resources_run_remove_lock()
            raise

        # remove lock
        self.Entropy._resources_run_remove_lock()

        if rc != 0:
            self.Entropy.updateProgress(
                blue(_("An error occured. Action aborted.")),
                importance = 2,
                type = "error",
                header = darkred("   ## ")
            )
        return rc

    '''
       Install/Removal process preparation function
       - will generate all the metadata needed to run the action steps, creating infoDict automatically
       @input matched_atom(tuple): is what is returned by EquoInstance.atomMatch:
            (idpackage,repoid):
            (2000,u'sabayonlinux.org')
            NOTE: in case of remove action, matched_atom must be:
            (idpackage,)
            NOTE: in case of multi_fetch, matched_atom can be a list of matches
        @input action(string): is an action to take, which must be one in self.valid_actions
    '''
    def prepare(self, matched_atom, action, metaopts = {}):

        self.error_on_prepared()
        self.check_action_validity(action)

        self.action = action
        self.matched_atom = matched_atom
        self.metaopts = metaopts
        # generate metadata dictionary
        self.generate_metadata()

    def generate_metadata(self):
        self.error_on_prepared()
        self.check_action_validity(self.action)

        if self.action == "fetch":
            self.__generate_fetch_metadata()
        elif self.action == "multi_fetch":
            self.__generate_multi_fetch_metadata()
        elif self.action in ("remove","remove_conflict"):
            self.__generate_remove_metadata()
        elif self.action == "install":
            self.__generate_install_metadata()
        elif self.action == "source":
            self.__generate_fetch_metadata(sources = True)
        elif self.action == "config":
            self.__generate_config_metadata()
        self.prepared = True

    def __generate_remove_metadata(self):
        self.infoDict.clear()
        idpackage = self.matched_atom[0]

        if not self.Entropy.clientDbconn.isIDPackageAvailable(idpackage):
            self.infoDict['remove_installed_vanished'] = True
            return 0

        self.infoDict['triggers'] = {}
        self.infoDict['removeatom'] = self.Entropy.clientDbconn.retrieveAtom(idpackage)
        self.infoDict['slot'] = self.Entropy.clientDbconn.retrieveSlot(idpackage)
        self.infoDict['versiontag'] = self.Entropy.clientDbconn.retrieveVersionTag(idpackage)
        self.infoDict['removeidpackage'] = idpackage
        self.infoDict['diffremoval'] = False
        removeConfig = False
        if self.metaopts.has_key('removeconfig'):
            removeConfig = self.metaopts.get('removeconfig')
        self.infoDict['removeconfig'] = removeConfig
        self.infoDict['removecontent'] = self.Entropy.clientDbconn.retrieveContent(idpackage)
        self.infoDict['triggers']['remove'] = self.Entropy.clientDbconn.getTriggerInfo(idpackage)
        self.infoDict['triggers']['remove']['removecontent'] = self.infoDict['removecontent']
        self.infoDict['steps'] = []
        self.infoDict['steps'].append("preremove")
        self.infoDict['steps'].append("remove")
        self.infoDict['steps'].append("postremove")

        return 0

    def __generate_config_metadata(self):
        self.infoDict.clear()
        idpackage = self.matched_atom[0]

        self.infoDict['atom'] = self.Entropy.clientDbconn.retrieveAtom(idpackage)
        key, slot = self.Entropy.clientDbconn.retrieveKeySlot(idpackage)
        self.infoDict['key'], self.infoDict['slot'] = key, slot
        self.infoDict['version'] = self.Entropy.clientDbconn.retrieveVersion(idpackage)
        self.infoDict['steps'] = []
        self.infoDict['steps'].append("config")

        return 0

    def __generate_install_metadata(self):
        self.infoDict.clear()

        idpackage, repository = self.matched_atom
        self.infoDict['idpackage'] = idpackage
        self.infoDict['repository'] = repository

        # fetch abort function
        if self.metaopts.has_key('fetch_abort_function'):
            self.fetch_abort_function = self.metaopts.pop('fetch_abort_function')

        # get package atom
        dbconn = self.Entropy.openRepositoryDatabase(repository)
        self.infoDict['triggers'] = {}
        self.infoDict['atom'] = dbconn.retrieveAtom(idpackage)
        self.infoDict['slot'] = dbconn.retrieveSlot(idpackage)
        self.infoDict['version'], self.infoDict['versiontag'], self.infoDict['revision'] = dbconn.getVersioningData(idpackage)
        self.infoDict['category'] = dbconn.retrieveCategory(idpackage)
        self.infoDict['download'] = dbconn.retrieveDownloadURL(idpackage)
        self.infoDict['name'] = dbconn.retrieveName(idpackage)
        self.infoDict['messages'] = dbconn.retrieveMessages(idpackage)
        self.infoDict['checksum'] = dbconn.retrieveDigest(idpackage)
        self.infoDict['accept_license'] = dbconn.retrieveLicensedataKeys(idpackage)
        self.infoDict['conflicts'] = self.Entropy.get_match_conflicts(self.matched_atom)

        # fill action queue
        self.infoDict['removeidpackage'] = -1
        removeConfig = False
        if self.metaopts.has_key('removeconfig'):
            removeConfig = self.metaopts.get('removeconfig')

        self.infoDict['remove_metaopts'] = {
            'removeconfig': True,
        }
        if self.metaopts.has_key('remove_metaopts'):
            self.infoDict['remove_metaopts'] = self.metaopts.get('remove_metaopts')

        self.infoDict['merge_from'] = None
        mf = self.metaopts.get('merge_from')
        if mf != None:
            self.infoDict['merge_from'] = unicode(mf)
        self.infoDict['removeconfig'] = removeConfig

        self.infoDict['removeidpackage'] = self.Entropy.retrieveInstalledIdPackage(
                                                self.entropyTools.dep_getkey(self.infoDict['atom']),
                                                self.infoDict['slot']
                                            )

        if self.infoDict['removeidpackage'] != -1:
            avail = self.Entropy.clientDbconn.isIDPackageAvailable(self.infoDict['removeidpackage'])
            if avail:
                self.infoDict['removeatom'] = self.Entropy.clientDbconn.retrieveAtom(self.infoDict['removeidpackage'])
            else:
                self.infoDict['removeidpackage'] = -1

        # smartpackage ?
        self.infoDict['smartpackage'] = False
        # set unpack dir and image dir
        if self.infoDict['repository'].endswith(etpConst['packagesext']):
            # do arch check
            compiled_arch = dbconn.retrieveDownloadURL(idpackage)
            if compiled_arch.find("/"+etpSys['arch']+"/") == -1:
                self.infoDict.clear()
                self.prepared = False
                return -1
            self.infoDict['smartpackage'] = etpRepositories[self.infoDict['repository']]['smartpackage']
            self.infoDict['pkgpath'] = etpRepositories[self.infoDict['repository']]['pkgpath']
        else:
            self.infoDict['pkgpath'] = etpConst['entropyworkdir']+"/"+self.infoDict['download']
        self.infoDict['unpackdir'] = etpConst['entropyunpackdir']+"/"+self.infoDict['download']
        self.infoDict['imagedir'] = etpConst['entropyunpackdir']+"/"+self.infoDict['download']+"/"+etpConst['entropyimagerelativepath']

        # gentoo xpak data
        if etpConst['gentoo-compat']:
            self.infoDict['xpakpath'] = etpConst['entropyunpackdir']+"/"+self.infoDict['download']+"/"+etpConst['entropyxpakrelativepath']
            if not self.infoDict['merge_from']:
                self.infoDict['xpakstatus'] = None
                self.infoDict['xpakdir'] = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
            else:
                self.infoDict['xpakstatus'] = True
                portdbdir = 'var/db/pkg' # XXX hard coded ?
                portdbdir = os.path.join(self.infoDict['merge_from'],portdbdir)
                portdbdir = os.path.join(portdbdir,self.infoDict['category'])
                portdbdir = os.path.join(portdbdir,self.infoDict['name']+"-"+self.infoDict['version'])
                self.infoDict['xpakdir'] = portdbdir

        # compare both versions and if they match, disable removeidpackage
        if self.infoDict['removeidpackage'] != -1:
            installedVer, installedTag, installedRev = self.Entropy.clientDbconn.getVersioningData(self.infoDict['removeidpackage'])
            pkgcmp = self.entropyTools.entropyCompareVersions(
                (self.infoDict['version'], self.infoDict['versiontag'], self.infoDict['revision'],),
                (installedVer, installedTag, installedRev,)
            )
            if pkgcmp == 0:
                self.infoDict['removeidpackage'] = -1
            else:
                # differential remove list
                self.infoDict['diffremoval'] = True
                self.infoDict['removeatom'] = self.Entropy.clientDbconn.retrieveAtom(self.infoDict['removeidpackage'])
                self.infoDict['removecontent'] = self.Entropy.clientDbconn.contentDiff(
                        self.infoDict['removeidpackage'],
                        dbconn,
                        idpackage
                )
                self.infoDict['triggers']['remove'] = self.Entropy.clientDbconn.getTriggerInfo(
                        self.infoDict['removeidpackage']
                )
                self.infoDict['triggers']['remove']['removecontent'] = self.infoDict['removecontent']

        # set steps
        self.infoDict['steps'] = []
        if self.infoDict['conflicts']:
            self.infoDict['steps'].append("remove_conflicts")
        # install
        self.infoDict['steps'].append("unpack")
        # preinstall placed before preremove in order
        # to respect Spm order
        self.infoDict['steps'].append("preinstall")
        if (self.infoDict['removeidpackage'] != -1):
            self.infoDict['steps'].append("preremove")
        self.infoDict['steps'].append("install")
        if (self.infoDict['removeidpackage'] != -1):
            self.infoDict['steps'].append("postremove")
        self.infoDict['steps'].append("postinstall")
        if not etpConst['gentoo-compat']: # otherwise gentoo triggers will show that
            self.infoDict['steps'].append("showmessages")
        else:
            self.infoDict['steps'].append("logmessages")
        self.infoDict['steps'].append("cleanup")

        self.infoDict['triggers']['install'] = dbconn.getTriggerInfo(idpackage)
        self.infoDict['triggers']['install']['accept_license'] = self.infoDict['accept_license']
        self.infoDict['triggers']['install']['unpackdir'] = self.infoDict['unpackdir']
        self.infoDict['triggers']['install']['imagedir'] = self.infoDict['imagedir']
        if etpConst['gentoo-compat']:
            #self.infoDict['triggers']['install']['xpakpath'] = self.infoDict['xpakpath']
            self.infoDict['triggers']['install']['xpakdir'] = self.infoDict['xpakdir']

        return 0

    def __generate_fetch_metadata(self, sources = False):
        self.infoDict.clear()

        idpackage, repository = self.matched_atom
        dochecksum = True

        # fetch abort function
        if self.metaopts.has_key('fetch_abort_function'):
            self.fetch_abort_function = self.metaopts.pop('fetch_abort_function')

        if self.metaopts.has_key('dochecksum'):
            dochecksum = self.metaopts.get('dochecksum')
        self.infoDict['repository'] = repository
        self.infoDict['idpackage'] = idpackage
        dbconn = self.Entropy.openRepositoryDatabase(repository)
        self.infoDict['atom'] = dbconn.retrieveAtom(idpackage)
        if sources:
            self.infoDict['download'] = dbconn.retrieveSources(idpackage, extended = True)
        else:
            self.infoDict['checksum'] = dbconn.retrieveDigest(idpackage)
            self.infoDict['download'] = dbconn.retrieveDownloadURL(idpackage)

        if not self.infoDict['download']:
            self.infoDict['fetch_not_available'] = True
            return 0

        self.infoDict['verified'] = False
        self.infoDict['steps'] = []
        if not repository.endswith(etpConst['packagesext']) and not sources:
            if self.Entropy.check_needed_package_download(self.infoDict['download'], None) < 0:
                self.infoDict['steps'].append("fetch")
            if dochecksum:
                self.infoDict['steps'].append("checksum")
        elif sources:
            self.infoDict['steps'].append("sources_fetch")

        if sources:
            # create sources destination directory
            unpack_dir = etpConst['entropyunpackdir']+"/sources/"+self.infoDict['atom']
            self.infoDict['unpackdir'] = unpack_dir
            if os.path.lexists(unpack_dir):
                if os.path.isfile(unpack_dir):
                    os.remove(unpack_dir)
                elif os.path.isdir(unpack_dir):
                    shutil.rmtree(unpack_dir,True)
            if not os.path.lexists(unpack_dir):
                os.makedirs(unpack_dir,0775)
            const_setup_perms(unpack_dir,etpConst['entropygid'])

        else:
            # if file exists, first checksum then fetch
            if os.path.isfile(os.path.join(etpConst['entropyworkdir'],self.infoDict['download'])):
                # check size first
                repo_size = dbconn.retrieveSize(idpackage)
                f = open(os.path.join(etpConst['entropyworkdir'],self.infoDict['download']),"r")
                f.seek(0,2)
                disk_size = f.tell()
                f.close()
                if repo_size == disk_size:
                    self.infoDict['steps'].reverse()
        return 0

    def __generate_multi_fetch_metadata(self):
        self.infoDict.clear()

        if not isinstance(self.matched_atom,list):
            raise IncorrectParameter("IncorrectParameter: "
                "matched_atom must be a list of tuples, not %s" % (type(self.matched_atom,))
            )

        dochecksum = True

        # meta options
        if self.metaopts.has_key('fetch_abort_function'):
            self.fetch_abort_function = self.metaopts.pop('fetch_abort_function')
        if self.metaopts.has_key('dochecksum'):
            dochecksum = self.metaopts.get('dochecksum')
        self.infoDict['checksum'] = dochecksum

        matches = self.matched_atom
        self.infoDict['matches'] = matches
        self.infoDict['atoms'] = []
        self.infoDict['repository_atoms'] = {}
        temp_fetch_list = []
        temp_checksum_list = []
        temp_already_downloaded_count = 0
        etp_workdir = etpConst['entropyworkdir']
        for idpackage, repository in matches:
            if repository.endswith(etpConst['packagesext']): continue

            dbconn = self.Entropy.openRepositoryDatabase(repository)
            myatom = dbconn.retrieveAtom(idpackage)

            # general purpose metadata
            self.infoDict['atoms'].append(myatom)
            if not self.infoDict['repository_atoms'].has_key(repository):
                self.infoDict['repository_atoms'][repository] = set()
            self.infoDict['repository_atoms'][repository].add(myatom)

            download = dbconn.retrieveDownloadURL(idpackage)
            #branch = dbconn.retrieveBranch(idpackage)
            digest = dbconn.retrieveDigest(idpackage)
            repo_size = dbconn.retrieveSize(idpackage)
            orig_branch = self.Entropy.get_branch_from_download_relative_uri(download)
            if self.Entropy.check_needed_package_download(download, None) < 0:
                temp_fetch_list.append((repository, orig_branch, download, digest))
                continue
            elif dochecksum:
                temp_checksum_list.append((repository, orig_branch, download, digest))
            down_path = os.path.join(etp_workdir,download)
            if os.path.isfile(down_path):
                with open(down_path,"r") as f:
                    f.seek(0,2)
                    disk_size = f.tell()
                if repo_size == disk_size:
                    temp_already_downloaded_count += 1

        self.infoDict['steps'] = []
        self.infoDict['multi_fetch_list'] = temp_fetch_list
        self.infoDict['multi_checksum_list'] = temp_checksum_list
        if self.infoDict['multi_fetch_list']:
            self.infoDict['steps'].append("multi_fetch")
        if self.infoDict['multi_checksum_list']:
            self.infoDict['steps'].append("multi_checksum")
        if temp_already_downloaded_count == len(temp_checksum_list):
            self.infoDict['steps'].reverse()

        return 0


class Repository:

    import entropy.dump as dumpTools
    import entropy.tools as entropyTools
    import socket
    def __init__(self, EquoInstance, reponames = [], forceUpdate = False, noEquoCheck = False, fetchSecurity = True):

        self.LockScanner = None
        if not isinstance(EquoInstance,Client):
            mytxt = _("A valid Equo instance or subclass is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        self.supported_download_items = (
            "db","rev","ck",
            "lock","mask","system_mask","dbdump", "conflicting_tagged",
            "dbdumpck","lic_whitelist","make.conf",
            "package.mask","package.unmask","package.keywords","profile.link",
            "package.use","server.cert","ca.cert","meta_file",
            "notice_board"
        )
        self.big_socket_timeout = 25
        self.Entropy = EquoInstance
        from entropy.cache import EntropyCacher
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
        self.valid_eapis = [1,2,3]
        self.reset_dbformat_eapi(None)
        self.current_repository_got_locked = False
        self.updated_repos = set()

        # check etpRepositories
        if not etpRepositories:
            mytxt = _("No repositories specified in %s") % (etpConst['repositoriesconf'],)
            raise MissingParameter("MissingParameter: %s" % (mytxt,))

        if not self.reponames:
            self.reponames.extend(etpRepositories.keys()[:])

    def __del__(self):
        if self.LockScanner != None:
            self.LockScanner.kill()

    def get_eapi3_connection(self, repository):
        # get database url
        dburl = etpRepositories[repository]['plain_database']
        if dburl.startswith("file://"):
            return None
        try:
            dburl = dburl.split("/")[2]
        except IndexError:
            return None
        port = etpRepositories[repository]['service_port']
        try:
            from entropy.services.ugc.interfaces import Client
            from entropy.client.services.ugc.commands import Client as CommandsClient
            eapi3_socket = Client(self.Entropy, CommandsClient, output_header = "\t")
            eapi3_socket.socket_timeout = self.big_socket_timeout
            eapi3_socket.connect(dburl, port)
            return eapi3_socket
        except (ConnectionError,self.socket.error,):
            return None

    def check_eapi3_availability(self, repository):
        conn = self.get_eapi3_connection(repository)
        if conn == None: return False
        try:
            conn.disconnect()
        except (self.socket.error,AttributeError,):
            return False
        return True

    def reset_dbformat_eapi(self, repository):

        self.dbformat_eapi = 2
        if repository != None:
            eapi_avail = self.check_eapi3_availability(repository)
            if eapi_avail:
                self.dbformat_eapi = 3

        # FIXME, find a way to do that without needing sqlite3 exec.
        if not os.access("/usr/bin/sqlite3",os.X_OK) or self.entropyTools.islive():
            self.dbformat_eapi = 1
        else:
            rc = subprocess.call("/usr/bin/sqlite3 -version &> /dev/null", shell = True)
            if rc != 0: self.dbformat_eapi = 1

        eapi_env = os.getenv("FORCE_EAPI")
        if eapi_env != None:
            try:
                myeapi = int(eapi_env)
            except (ValueError,TypeError,):
                return
            if myeapi in self.valid_eapis:
                self.dbformat_eapi = myeapi


    def __validate_repository_id(self, repoid):
        if repoid not in self.reponames:
            mytxt = _("Repository is not listed in self.reponames")
            raise InvalidData("InvalidData: %s" % (mytxt,))

    def __validate_compression_method(self, repo):

        self.__validate_repository_id(repo)

        cmethod = etpConst['etpdatabasecompressclasses'].get(etpRepositories[repo]['dbcformat'])
        if cmethod == None:
            mytxt = _("Wrong database compression method")
            raise InvalidDataType("InvalidDataType: %s" % (mytxt,))

        return cmethod

    def __ensure_repository_path(self, repo):

        self.__validate_repository_id(repo)

        # create dir if it doesn't exist
        if not os.path.isdir(etpRepositories[repo]['dbpath']):
            os.makedirs(etpRepositories[repo]['dbpath'],0775)

        const_setup_perms(etpConst['etpdatabaseclientdir'],etpConst['entropygid'])

    def _construct_paths(self, item, repo, cmethod):

        if item not in self.supported_download_items:
            mytxt = _("Supported items: %s") % (self.supported_download_items,)
            raise InvalidData("InvalidData: %s" % (mytxt,))
        if (item in ("db","dbdump", "dbdumpck",)) and (cmethod == None):
                mytxt = _("For %s, cmethod can't be None") % (item,)
                raise InvalidData("InvalidData: %s" % (mytxt,))

        repo_db = etpRepositories[repo]['database']
        repo_dbpath = etpRepositories[repo]['dbpath']
        ec_rev = etpConst['etpdatabaserevisionfile']
        ec_hash = etpConst['etpdatabasehashfile']
        ec_maskfile = etpConst['etpdatabasemaskfile']
        ec_sysmaskfile = etpConst['etpdatabasesytemmaskfile']
        ec_confl_taged = etpConst['etpdatabaseconflictingtaggedfile']
        make_conf_file = os.path.basename(etpConst['spm']['global_make_conf'])
        pkg_mask_file = os.path.basename(etpConst['spm']['global_package_mask'])
        pkg_unmask_file = os.path.basename(etpConst['spm']['global_package_unmask'])
        pkg_keywords_file = os.path.basename(etpConst['spm']['global_package_keywords'])
        pkg_use_file = os.path.basename(etpConst['spm']['global_package_use'])
        sys_profile_lnk = etpConst['spm']['global_make_profile_link_name']
        pkg_lic_wl_file = etpConst['etpdatabaselicwhitelistfile']
        repo_lock_file = etpConst['etpdatabasedownloadlockfile']
        ca_cert_file = etpConst['etpdatabasecacertfile']
        server_cert_file = etpConst['etpdatabaseservercertfile']
        notice_board_filename = os.path.basename(etpRepositories[repo]['notice_board'])
        meta_file = etpConst['etpdatabasemetafilesfile']
        ec_cm2 = None
        ec_cm3 = None
        ec_cm4 = None
        if cmethod != None:
            ec_cm2 = etpConst[cmethod[2]]
            ec_cm3 = etpConst[cmethod[3]]
            ec_cm4 = etpConst[cmethod[4]]

        mymap = {
            'db': ("%s/%s" % (repo_db,ec_cm2,),"%s/%s" % (repo_dbpath,ec_cm2,),),
            'dbdump': ("%s/%s" % (repo_db,ec_cm3,),"%s/%s" % (repo_dbpath,ec_cm3,),),
            'rev': ("%s/%s" % (repo_db,ec_rev,),"%s/%s" % (repo_dbpath,ec_rev,),),
            'ck': ("%s/%s" % (repo_db,ec_hash,),"%s/%s" % (repo_dbpath,ec_hash,),),
            'dbdumpck': ("%s/%s" % (repo_db,ec_cm4,),"%s/%s" % (repo_dbpath,ec_cm4,),),
            'mask': ("%s/%s" % (repo_db,ec_maskfile,),"%s/%s" % (repo_dbpath,ec_maskfile,),),
            'system_mask': ("%s/%s" % (repo_db,ec_sysmaskfile,),"%s/%s" % (repo_dbpath,ec_sysmaskfile,),),
            'conflicting_tagged': ("%s/%s" % (repo_db,ec_confl_taged,),"%s/%s" % (repo_dbpath,ec_confl_taged,),),
            'make.conf': ("%s/%s" % (repo_db,make_conf_file,),"%s/%s" % (repo_dbpath,make_conf_file,),),
            'package.mask': ("%s/%s" % (repo_db,pkg_mask_file,),"%s/%s" % (repo_dbpath,pkg_mask_file,),),
            'package.unmask': ("%s/%s" % (repo_db,pkg_unmask_file,),"%s/%s" % (repo_dbpath,pkg_unmask_file,),),
            'package.keywords': ("%s/%s" % (repo_db,pkg_keywords_file,),"%s/%s" % (repo_dbpath,pkg_keywords_file,),),
            'package.use': ("%s/%s" % (repo_db,pkg_use_file,),"%s/%s" % (repo_dbpath,pkg_use_file,),),
            'profile.link': ("%s/%s" % (repo_db,sys_profile_lnk,),"%s/%s" % (repo_dbpath,sys_profile_lnk,),),
            'lic_whitelist': ("%s/%s" % (repo_db,pkg_lic_wl_file,),"%s/%s" % (repo_dbpath,pkg_lic_wl_file,),),
            'lock': ("%s/%s" % (repo_db,repo_lock_file,),"%s/%s" % (repo_dbpath,repo_lock_file,),),
            'server.cert': ("%s/%s" % (repo_db,server_cert_file,),"%s/%s" % (repo_dbpath,server_cert_file,),),
            'ca.cert': ("%s/%s" % (repo_db,ca_cert_file,),"%s/%s" % (repo_dbpath,ca_cert_file,),),
            'notice_board': (etpRepositories[repo]['notice_board'],"%s/%s" % (repo_dbpath,notice_board_filename,),),
            'meta_file': ("%s/%s" % (repo_db,meta_file,),"%s/%s" % (repo_dbpath,meta_file,),),
        }

        return mymap.get(item)

    def __remove_repository_files(self, repo, cmethod):

        dbfilenameid = cmethod[2]
        self.__validate_repository_id(repo)
        repo_dbpath = etpRepositories[repo]['dbpath']

        def remove_eapi1(repo_dbpath, dbfilenameid):
            if os.path.isfile(repo_dbpath+"/"+etpConst['etpdatabasehashfile']):
                os.remove(repo_dbpath+"/"+etpConst['etpdatabasehashfile'])
            if os.path.isfile(repo_dbpath+"/"+etpConst[dbfilenameid]):
                os.remove(repo_dbpath+"/"+etpConst[dbfilenameid])
            if os.path.isfile(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile']):
                os.remove(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile'])

        if self.dbformat_eapi == 1:
            remove_eapi1(repo_dbpath, dbfilenameid)
        elif self.dbformat_eapi in (2,3,):
            remove_eapi1(repo_dbpath, dbfilenameid)
            if os.path.isfile(repo_dbpath+"/"+cmethod[4]):
                os.remove(repo_dbpath+"/"+cmethod[4])
            if os.path.isfile(repo_dbpath+"/"+etpConst[cmethod[3]]):
                os.remove(repo_dbpath+"/"+etpConst[cmethod[3]])
            if os.path.isfile(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile']):
                os.remove(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile'])
        else:
            mytxt = _("self.dbformat_eapi must be in (1,2)")
            raise InvalidData('InvalidData: %s' % (mytxt,))

    def __unpack_downloaded_database(self, repo, cmethod):

        self.__validate_repository_id(repo)
        rc = 0
        path = None

        if self.dbformat_eapi == 1:
            myfile = etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[2]]
            try:
                path = eval("self.entropyTools."+cmethod[1])(myfile)
            except EOFError:
                rc = 1
            if os.path.isfile(myfile):
                os.remove(myfile)
        elif self.dbformat_eapi == 2:
            myfile = etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[3]]
            try:
                path = eval("self.entropyTools."+cmethod[1])(myfile)
            except EOFError:
                rc = 1
            if os.path.isfile(myfile):
                os.remove(myfile)
        else:
            mytxt = _("self.dbformat_eapi must be in (1,2)")
            raise InvalidData('InvalidData: %s' % (mytxt,))

        if rc == 0:
            self.Entropy.setup_default_file_perms(path)

        return rc

    def __verify_database_checksum(self, repo, cmethod = None):

        self.__validate_repository_id(repo)

        if self.dbformat_eapi == 1:
            dbfile = etpConst['etpdatabasefile']
            try:
                f = open(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
                md5hash = f.readline().strip()
                md5hash = md5hash.split()[0]
                f.close()
            except:
                return -1
        elif self.dbformat_eapi == 2:
            dbfile = etpConst[cmethod[3]]
            try:
                f = open(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[4]],"r")
                md5hash = f.readline().strip()
                md5hash = md5hash.split()[0]
                f.close()
            except:
                return -1
        else:
            mytxt = _("self.dbformat_eapi must be in (1,2)")
            raise InvalidData('InvalidData: %s' % (mytxt,))

        rc = self.entropyTools.compareMd5(etpRepositories[repo]['dbpath']+"/"+dbfile,md5hash)
        return rc

    # @returns -1 if the file is not available
    # @returns int>0 if the revision has been retrieved
    def get_online_repository_revision(self, repo):

        self.__validate_repository_id(repo)

        url = etpRepositories[repo]['database']+"/"+etpConst['etpdatabaserevisionfile']
        status = self.entropyTools.get_remote_data(url)
        if (status):
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
        url = etpRepositories[repo]['database']+"/"+etpConst['etpdatabaseeapi3lockfile']
        data = self.entropyTools.get_remote_data(url)
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
        self.Entropy.clear_dump_cache("%s/%s%s/" % (etpCache['dbMatch'],etpConst['dbnamerepoprefix'],repo,))
        self.Entropy.clear_dump_cache("%s/%s%s/" % (etpCache['dbSearch'],etpConst['dbnamerepoprefix'],repo,))

    # this function can be reimplemented
    def download_item(self, item, repo, cmethod = None, lock_status_func = None, disallow_redirect = True):

        self.__validate_repository_id(repo)
        url, filepath = self._construct_paths(item, repo, cmethod)

        # to avoid having permissions issues
        # it's better to remove the file before,
        # otherwise new permissions won't be written
        if os.path.isfile(filepath):
            os.remove(filepath)
        filepath_dir = os.path.dirname(filepath)
        if not os.path.isdir(filepath_dir) and not os.path.lexists(filepath_dir):
            os.makedirs(filepath_dir,0775)
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
        if rc in ("-1","-2","-3","-4"):
            return False
        self.Entropy.setup_default_file_perms(filepath)
        return True

    def check_downloaded_database(self, repo, cmethod):
        dbfilename = etpConst['etpdatabasefile']
        if self.dbformat_eapi == 2:
            dbfilename = etpConst[cmethod[3]]
        # verify checksum
        mytxt = "%s %s %s" % (red(_("Checking downloaded database")),darkgreen(dbfilename),red("..."))
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            back = True,
            type = "info",
            header = "\t"
        )
        db_status = self.__verify_database_checksum(repo, cmethod)
        if db_status == -1:
            mytxt = "%s. %s !" % (red(_("Cannot open digest")),red(_("Cannot verify database integrity")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )
        elif db_status:
            mytxt = "%s: %s" % (red(_("Downloaded database status")),bold(_("OK")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = "\t"
            )
        else:
            mytxt = "%s: %s" % (red(_("Downloaded database status")),darkred(_("ERROR")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = "\t"
            )
            mytxt = "%s. %s" % (red(_("An error occured while checking database integrity")),red(_("Giving up")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = "\t"
            )
            return 1
        return 0


    def show_repository_information(self, repo, count_info):

        self.Entropy.updateProgress(
            bold("%s") % ( etpRepositories[repo]['description'] ),
            importance = 2,
            type = "info",
            count = count_info,
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database URL")),darkgreen(etpRepositories[repo]['database']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database local path")),darkgreen(etpRepositories[repo]['dbpath']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database EAPI")),darkgreen(str(self.dbformat_eapi)),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = blue("  # ")
        )

    def get_eapi3_local_database(self, repo):

        dbfile = os.path.join(etpRepositories[repo]['dbpath'],etpConst['etpdatabasefile'])
        mydbconn = None
        try:
            mydbconn = self.Entropy.openGenericDatabase(dbfile, xcache = False, indexing_override = False)
            mydbconn.validateDatabase()
        except (
            self.Entropy.dbapi2.OperationalError,
            self.Entropy.dbapi2.IntegrityError,
            SystemDatabaseError,
            IOError,
            OSError,):
                mydbconn = None
        return mydbconn

    def get_eapi3_database_differences(self, eapi3_interface, repo, idpackages, session):

        data = eapi3_interface.CmdInterface.differential_packages_comparison(
            session, idpackages, repo, etpConst['currentarch'], etpConst['product']
        )
        if isinstance(data,bool): # then it's probably == False
            return False,False,False
        elif not isinstance(data,dict):
            return None,None,None
        elif not data.has_key('added') or \
            not data.has_key('removed') or \
            not data.has_key('checksum'):
                return None,None,None
        return data['added'],data['removed'],data['checksum']

    def get_eapi3_database_treeupdates(self, eapi3_interface, repo, session):
        self.socket.setdefaulttimeout(self.big_socket_timeout)
        data = eapi3_interface.CmdInterface.get_repository_treeupdates(
            session, repo, etpConst['currentarch'], etpConst['product']
        )
        if not isinstance(data,dict): return None,None
        return data.get('digest'), data.get('actions')

    def get_eapi3_package_sets(self, eapi3_interface, repo, session):
        self.socket.setdefaulttimeout(self.big_socket_timeout)
        data = eapi3_interface.CmdInterface.get_package_sets(
            session, repo, etpConst['currentarch'], etpConst['product']
        )
        if not isinstance(data,dict): return {}
        return data

    def handle_eapi3_database_sync(self, repo, threshold = 1500, chunk_size = 12):

        def prepare_exit(mysock, session = None):
            try:
                if session != None:
                    mysock.close_session(session)
                mysock.disconnect()
            except (self.socket.error,):
                pass

        eapi3_interface = self.get_eapi3_connection(repo)
        if eapi3_interface == None: return False

        session = eapi3_interface.open_session()

        # AttributeError because mydbconn can be == None
        try:
            mydbconn = self.get_eapi3_local_database(repo)
            myidpackages = mydbconn.listAllIdpackages()
        except (self.dbapi2.DatabaseError,self.dbapi2.IntegrityError,self.dbapi2.OperationalError,AttributeError,):
            prepare_exit(eapi3_interface, session)
            return False

        added_ids, removed_ids, checksum = self.get_eapi3_database_differences(
            eapi3_interface, repo,
            myidpackages, session
        )
        if (None in (added_ids,removed_ids,checksum)) or \
            (not added_ids and not removed_ids and self.forceUpdate):
                mydbconn.closeDB()
                prepare_exit(eapi3_interface, session)
                return False

        elif not checksum: # {added_ids, removed_ids, checksum} == False
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            mytxt = "%s: %s" % ( blue(_("EAPI3 Service status")), darkred(_("remote database suddenly locked")),)
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
                blue(_("EAPI3 Service")), darkred(_("skipping differential sync")),
                brown(_("threshold")), blue(str(len(added_ids))), darkred(str(threshold)),
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
        for segment in added_segments:

            count += 1
            mytxt = "%s %s" % (blue(_("Fetching segments")), "...",)
            self.Entropy.updateProgress(
                mytxt, importance = 0, type = "info",
                header = "\t", back = True, count = (count,maxcount,)
            )
            fetch_count = 0
            max_fetch_count = 5

            while 1:

                # anti loop protection
                if fetch_count > max_fetch_count:
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return False

                fetch_count += 1
                pkgdata = eapi3_interface.CmdInterface.get_package_information(
                    session, segment, repo, etpConst['currentarch'], etpConst['product']
                )
                if pkgdata == None:
                    mytxt = "%s: %s" % ( blue(_("Fetch error on segment")), darkred(str(segment)),)
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "warning",
                        header = "\t", count = (count,maxcount,)
                    )
                    continue
                elif not pkgdata: # pkgdata == False
                    mytxt = "%s: %s" % (
                        blue(_("Service status")),
                        darkred("remote database suddenly locked"),
                    )
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "info",
                        header = "\t", count = (count,maxcount,)
                    )
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return None
                elif isinstance(pkgdata,tuple):
                    mytxt = "%s: %s, %s. %s" % ( blue(_("Service status")), pkgdata[0], pkgdata[1], darkred("Error processing the command"),)
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "info",
                        header = "\t", count = (count,maxcount,)
                    )
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return None

                try:
                    for idpackage in pkgdata:
                        self.dumpTools.dumpobj(
                            "%s%s" % (etpCache['eapi3_fetch'],idpackage,),
                            pkgdata[idpackage],
                            ignoreExceptions = False
                        )
                except (IOError,EOFError,OSError,), e:
                    mytxt = "%s: %s: %s." % ( blue(_("Local status")), darkred("Error storing data"), e,)
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "info",
                        header = "\t", count = (count,maxcount,)
                    )
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return None

                break

        del added_segments

        # get treeupdates stuff
        dbdigest, treeupdates_actions = self.get_eapi3_database_treeupdates(eapi3_interface, repo, session)
        if dbdigest == None:
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            mytxt = "%s: %s" % ( blue(_("EAPI3 Service status")), darkred(_("treeupdates data not available")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = blue("  # "),
            )
            return None

        try:
            mydbconn.setRepositoryUpdatesDigest(repo, dbdigest)
            mydbconn.bumpTreeUpdatesActions(treeupdates_actions)
        except (self.dbapi2.DatabaseError,self.dbapi2.IntegrityError,self.dbapi2.OperationalError,):
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            mytxt = "%s: %s" % (blue(_("EAPI3 Service status")), darkred(_("cannot update treeupdates data")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = blue("  # "),
            )
            return None


        # get updated package sets
        repo_sets = self.get_eapi3_package_sets(eapi3_interface, repo, session)
        try:
            mydbconn.clearPackageSets()
            mydbconn.insertPackageSets(repo_sets)
        except (self.dbapi2.DatabaseError,self.dbapi2.IntegrityError,self.dbapi2.OperationalError,):
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            mytxt = "%s: %s" % (blue(_("EAPI3 Service status")), darkred(_("cannot update package sets data")),)
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
            mydata = self.Cacher.pop("%s%s" % (etpCache['eapi3_fetch'],idpackage,))
            if mydata == None:
                mytxt = "%s: %s" % (
                    blue(_("Fetch error on segment while adding")),
                    darkred(str(segment)),
                )
                self.Entropy.updateProgress(
                    mytxt, importance = 1, type = "warning",
                    header = "\t", count = (count,maxcount,)
                )
                mydbconn.closeDB()
                return False

            mytxt = "%s %s" % (blue(_("Injecting package")), darkgreen(mydata['atom']),)
            self.Entropy.updateProgress(
                mytxt, importance = 0, type = "info",
                header = "\t", back = True, count = (count,maxcount,)
            )
            mydbconn.addPackage(
                mydata, revision = mydata['revision'],
                idpackage = idpackage, do_remove = False,
                do_commit = False, formatted_content = True
            )

        self.Entropy.updateProgress(
            blue(_("Packages injection complete")), importance = 0,
            type = "info", header = "\t",
        )

        # now remove
        maxcount = len(removed_ids)
        count = 0
        for idpackage in removed_ids:
            myatom = mydbconn.retrieveAtom(idpackage)
            count += 1
            mytxt = "%s: %s" % (blue(_("Removing package")), darkred(str(myatom)),)
            self.Entropy.updateProgress(
                mytxt, importance = 0, type = "info",
                header = "\t", back = True, count = (count,maxcount,)
            )
            mydbconn.removePackage(idpackage, do_cleanup = False, do_commit = False)

        self.Entropy.updateProgress(
            blue(_("Packages removal complete")),
            importance = 0, type = "info",
            header = "\t",
        )

        mydbconn.commitChanges()
        mydbconn.clearCache()
        # now verify if both checksums match
        result = False
        mychecksum = mydbconn.database_checksum(do_order = True, strict = False, strings = True)
        if checksum == mychecksum:
            result = True
        else:
            mytxt = "%s: %s: %s | %s: %s" % (
                blue(_("Database checksum doesn't match remote.")),
                darkgreen(_("local")), mychecksum,
                darkred(_("remote")), checksum,
            )
            self.Entropy.updateProgress(
                mytxt, importance = 0,
                type = "info", header = "\t",
            )

        mydbconn.closeDB()
        return result

    def run_sync(self):

        self.dbupdated = False
        repocount = 0
        repolength = len(self.reponames)
        for repo in self.reponames:

            repocount += 1
            self.reset_dbformat_eapi(repo)
            self.show_repository_information(repo, (repocount,repolength))

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
            db_down_status = False
            do_db_update_transfer = False
            rc = 0
            # some variables
            dumpfile = os.path.join(etpRepositories[repo]['dbpath'],etpConst['etpdatabasedump'])
            dbfile = os.path.join(etpRepositories[repo]['dbpath'],etpConst['etpdatabasefile'])
            dbfile_old = dbfile+".sync"
            cmethod = self.__validate_compression_method(repo)

            while 1:

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
                    db_down_status = self.handle_database_checksum_download(repo, cmethod)
                    break

                elif self.dbformat_eapi == 3 and not (os.path.isfile(dbfile) and os.access(dbfile,os.W_OK)):

                    do_db_update_transfer = None
                    self.dbformat_eapi -= 1
                    continue

                elif self.dbformat_eapi == 3:

                    status = False
                    try:
                        status = self.handle_eapi3_database_sync(repo)
                    except self.socket.error, e:
                        mytxt = "%s: %s" % (
                            blue(_("EAPI3 Service error")),
                            darkred(unicode(e)),
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

                    if status == None: # remote db not available anymore ?
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

            if self.dbformat_eapi in (1,2,):

                if self.dbformat_eapi == 2 and db_down_status:
                    rc = self.check_downloaded_database(repo, cmethod)
                    if rc != 0:
                        # delete all
                        self.__remove_repository_files(repo, cmethod)
                        self.syncErrors = True
                        self.Entropy.cycleDone()
                        continue

                if isinstance(do_db_update_transfer,bool) and not do_db_update_transfer:
                    if os.path.isfile(dbfile):
                        try:
                            shutil.move(dbfile,dbfile_old)
                            do_db_update_transfer = True
                        except:
                            pass

                # unpack database
                unpack_status = self.handle_downloaded_database_unpack(repo, cmethod)
                if not unpack_status:
                    # delete all
                    self.__remove_repository_files(repo, cmethod)
                    self.syncErrors = True
                    self.Entropy.cycleDone()
                    continue

                if self.dbformat_eapi == 1 and db_down_status:
                    rc = self.check_downloaded_database(repo, cmethod)
                    if rc != 0:
                        # delete all
                        self.__remove_repository_files(repo, cmethod)
                        self.syncErrors = True
                        self.Entropy.cycleDone()
                        if os.path.isfile(dbfile_old):
                            os.remove(dbfile_old)
                        continue

                # re-validate
                if not os.path.isfile(dbfile):
                    do_db_update_transfer = False
                elif os.path.isfile(dbfile) and not do_db_update_transfer and (self.dbformat_eapi != 1):
                    os.remove(dbfile)

                if self.dbformat_eapi == 2:
                    rc = self.do_eapi2_inject_downloaded_dump(dumpfile, dbfile, cmethod)

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

            if os.path.isfile(dbfile) and os.access(dbfile,os.W_OK):
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
            if (repo == etpConst['officialrepositoryid']):
                try:
                    self.run_config_files_updates(repo)
                except Exception, e:
                    self.entropyTools.printTraceback()
                    mytxt = "%s: %s" % (
                        blue(_("Configuration files update error, not critical, continuing")),
                        darkred(unicode(e)),
                    )
                    self.Entropy.updateProgress(mytxt, importance = 0, type = "info", header = blue("  # "),)
            self.updated_repos.add(repo)
            self.Entropy.cycleDone()

            # remove garbage
            if os.path.isfile(dbfile_old):
                os.remove(dbfile_old)

        # keep them closed
        self.Entropy.closeAllRepositoryDatabases()
        self.Entropy.validate_repositories()
        self.Entropy.closeAllRepositoryDatabases()

        # clean caches, fetch security
        if self.dbupdated:
            self.Entropy.generate_cache(
                depcache = self.Entropy.xcache,
                configcache = False,
                client_purge = False,
                install_queue = False
            )
            if self.fetchSecurity:
                self.do_update_security_advisories()
            # do treeupdates
            if isinstance(self.Entropy.clientDbconn,LocalRepository):
                for repo in self.reponames:
                    dbc = self.Entropy.openRepositoryDatabase(repo)
                    dbc.clientUpdatePackagesData(self.Entropy.clientDbconn)
                self.Entropy.closeAllRepositoryDatabases()

        if self.syncErrors:
            self.Entropy.updateProgress(
                red(_("Something bad happened. Please have a look.")),
                importance = 1,
                type = "warning",
                header = darkred(" @@ ")
            )
            self.syncErrors = True
            self.Entropy._resources_run_remove_lock()
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
        url, repo_make_conf = self._construct_paths("make.conf", repo, None)
        system_make_conf = etpConst['spm']['global_make_conf']
        make_conf_variables_check = ["CHOST"]

        if os.path.isfile(repo_make_conf) and os.access(repo_make_conf,os.R_OK):

            if not os.path.isfile(system_make_conf):
                self.Entropy.updateProgress(
                    "%s %s. %s." % (red(system_make_conf),blue(_("does not exist")),blue(_("Overwriting")),),
                    importance = 1,
                    type = "info",
                    header = blue(" @@ ")
                )
                if os.path.lexists(system_make_conf):
                    shutil.move(
                        system_make_conf,
                        "%s.backup_%s" % (system_make_conf,self.entropyTools.getRandomNumber(),)
                    )
                shutil.copy2(repo_make_conf,system_make_conf)

            elif os.access(system_make_conf,os.W_OK):

                repo_f = open(repo_make_conf,"r")
                sys_f = open(system_make_conf,"r")
                repo_make_c = [x.strip() for x in repo_f.readlines()]
                sys_make_c = [x.strip() for x in sys_f.readlines()]
                repo_f.close()
                sys_f.close()

                # read repository settings
                repo_data = {}
                for setting in make_conf_variables_check:
                    for line in repo_make_c:
                        if line.startswith(setting+"="):
                            # there can't be bash vars with a space after its name on declaration
                            repo_data[setting] = line
                            # I don't break, because there might be other overlapping settings

                differences = {}
                # update make.conf data in memory
                for setting in repo_data:
                    for idx in range(len(sys_make_c)):
                        line = sys_make_c[idx]
                        if line.startswith(setting+"=") and (line != repo_data[setting]):
                            # there can't be bash vars with a space after its name on declaration
                            self.Entropy.updateProgress(
                                "%s: %s %s. %s." % (
                                    red(system_make_conf), bold(unicode(setting)),
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
                        "%s: %s." % (red(system_make_conf), blue(_("updating critical variables")),),
                        importance = 1,
                        type = "info",
                        header = blue(" @@ ")
                    )
                    # backup user make.conf
                    shutil.copy2(system_make_conf,"%s.entropy_backup" % (system_make_conf,))

                    self.Entropy.updateProgress(
                        "%s: %s." % (
                            red(system_make_conf), darkgreen("writing changes to disk"),
                        ),
                        importance = 1,
                        type = "info",
                        header = blue(" @@ ")
                    )
                    # write to disk, safely
                    tmp_make_conf = "%s.entropy_write" % (system_make_conf,)
                    f = open(tmp_make_conf,"w")
                    for line in sys_make_c: f.write(line+"\n")
                    f.flush()
                    f.close()
                    shutil.move(tmp_make_conf,system_make_conf)

                # update environment
                for var in differences:
                    try:
                        myval = '='.join(differences[var].strip().split("=")[1:])
                        if myval:
                            if myval[0] in ("'",'"',): myval = myval[1:]
                            if myval[-1] in ("'",'"',): myval = myval[:-1]
                    except IndexError:
                        myval = ''
                    os.environ[var] = myval

    def _config_updates_make_profile(self, repo):
        url, repo_make_profile = self._construct_paths("profile.link", repo, None)
        system_make_profile = etpConst['spm']['global_make_profile']
        if not (os.path.isfile(repo_make_profile) and os.access(repo_make_profile,os.R_OK)):
            return
        f = open(repo_make_profile,"r")
        repo_profile_link_data = f.readline().strip()
        f.close()
        current_profile_link = ''
        if os.path.islink(system_make_profile) and os.access(system_make_profile,os.R_OK):
            current_profile_link = os.readlink(system_make_profile)
        if repo_profile_link_data != current_profile_link:
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
            os.symlink(repo_profile_link_data,system_make_profile+merge_sfx)
            if self.entropyTools.is_valid_path(system_make_profile+merge_sfx):
                os.rename(system_make_profile+merge_sfx,system_make_profile)
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
                rc = self.Entropy.check_equo_updates()
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
        mytxt = "%s %s %s" % (red(_("Unpacking database to")),darkgreen(file_to_unpack),red("..."),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = "\t"
        )

        myrc = self.__unpack_downloaded_database(repo, cmethod)
        if myrc != 0:
            mytxt = "%s %s !" % (red(_("Cannot unpack compressed package")),red(_("Skipping repository")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )
            return False
        return True


    def handle_database_checksum_download(self, repo, cmethod):

        hashfile = etpConst['etpdatabasehashfile']
        downitem = 'ck'
        if self.dbformat_eapi == 2: # EAPI = 2
            hashfile = etpConst[cmethod[4]]
            downitem = 'dbdumpck'

        mytxt = "%s %s %s" % (red(_("Downloading checksum")),darkgreen(hashfile),red("..."),)
        # download checksum
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = "\t"
        )

        db_down_status = self.download_item(downitem, repo, cmethod, disallow_redirect = True)
        if not db_down_status:
            mytxt = "%s %s !" % (red(_("Cannot fetch checksum")),red(_("Cannot verify database integrity")),)
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
        self.LockScanner = TimeScheduled(5, self.repository_lock_scanner, repo)
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
            mytxt = _("Current repository got suddenly locked. Download aborted.")
            raise RepositoryError('RepositoryError %s' % (mytxt,))

    def handle_database_download(self, repo, cmethod):

        def show_repo_locked_message():
            mytxt = "%s: %s." % (bold(_("Attention")),red(_("remote database got suddenly locked")),)
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
            down_status = self.download_item("dbdump", repo, cmethod, lock_status_func = self.repository_lock_scanner_status, disallow_redirect = True)
            if self.current_repository_got_locked:
                self.kill_previous_repository_lock_scanner()
                show_repo_locked_message()
                return False
        if not down_status: # fallback to old db
            # start a check in background
            self.load_background_repository_lock_check(repo)
            self.dbformat_eapi = 1
            down_status = self.download_item("db", repo, cmethod, lock_status_func = self.repository_lock_scanner_status, disallow_redirect = True)
            if self.current_repository_got_locked:
                self.kill_previous_repository_lock_scanner()
                show_repo_locked_message()
                return False

        if not down_status:
            mytxt = "%s: %s." % (bold(_("Attention")),red(_("database does not exist online")),)
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
            mytxt = "%s: %s." % (bold(_("Attention")),red(_("database is already up to date")),)
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
                mytxt = "%s: %s." % (bold(_("Attention")),red(_("database will be ready soon")),)
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

        dbconn = self.Entropy.openGenericDatabase(dbfile, xcache = False, indexing_override = False)
        old_dbconn = self.Entropy.openGenericDatabase(dbfile_old, xcache = False, indexing_override = False)
        upd_rc = 0
        try:
            upd_rc = old_dbconn.alignDatabases(dbconn, output_header = "\t")
        except (self.dbapi2.OperationalError,self.dbapi2.IntegrityError,):
            pass
        old_dbconn.closeDB()
        dbconn.closeDB()
        if upd_rc > 0:
            # -1 means no changes, == force used
            # 0 means too much hassle
            shutil.move(dbfile_old,dbfile)
        return upd_rc

    def do_eapi2_inject_downloaded_dump(self, dumpfile, dbfile, cmethod):

        # load the dump into database
        mytxt = "%s %s, %s %s" % (
            red(_("Injecting downloaded dump")),
            darkgreen(etpConst[cmethod[3]]),
            red(_("please wait")),
            red("..."),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = "\t"
        )
        dbconn = self.Entropy.openGenericDatabase(dbfile, xcache = False, indexing_override = False)
        rc = dbconn.doDatabaseImport(dumpfile, dbfile)
        dbconn.closeDB()
        return rc


    def do_update_security_advisories(self):
        # update Security Advisories
        try:
            securityConn = self.Entropy.Security()
            securityConn.fetch_advisories()
        except Exception, e:
            self.entropyTools.printTraceback(f = self.Entropy.clientLog)
            mytxt = "%s: %s" % (red(_("Advisories fetch error")),e,)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = darkred(" @@ ")
            )

    def do_standard_items_download(self, repo):

        g_make_conf = os.path.basename(etpConst['spm']['global_make_conf'])
        pkg_unmask = os.path.basename(etpConst['spm']['global_package_unmask'])
        pkg_keywords = os.path.basename(etpConst['spm']['global_package_keywords'])
        pkg_use = os.path.basename(etpConst['spm']['global_package_use'])
        profile_link = etpConst['spm']['global_make_profile_link_name']
        notice_board = os.path.basename(etpRepositories[repo]['local_notice_board'])

        objects_to_unpack = ("meta_file",)

        download_items = [
            (
                "meta_file",
                etpConst['etpdatabasemetafilesfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading repository metafile")),
                    darkgreen(etpConst['etpdatabasemetafilesfile']),
                    red("..."),
                )
            ),
            (
                "ca.cert",
                etpConst['etpdatabasecacertfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading SSL CA certificate")),
                    darkgreen(etpConst['etpdatabasecacertfile']),
                    red("..."),
                )
            ),
            (
                "server.cert",
                etpConst['etpdatabaseservercertfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading SSL Server certificate")),
                    darkgreen(etpConst['etpdatabaseservercertfile']),
                    red("..."),
                )
            ),
            (
                "mask",
                etpConst['etpdatabasemaskfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading package mask")),
                    darkgreen(etpConst['etpdatabasemaskfile']),
                    red("..."),
                )
            ),
            (
                "system_mask",
                etpConst['etpdatabasesytemmaskfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading packages system mask")),
                    darkgreen(etpConst['etpdatabasesytemmaskfile']),
                    red("..."),
                )
            ),
            (
                "conflicting_tagged",
                etpConst['etpdatabaseconflictingtaggedfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading conflicting tagged packages file")),
                    darkgreen(etpConst['etpdatabaseconflictingtaggedfile']),
                    red("..."),
                )
            ),
            (
                "lic_whitelist",
                etpConst['etpdatabaselicwhitelistfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading license whitelist")),
                    darkgreen(etpConst['etpdatabaselicwhitelistfile']),
                    red("..."),
                )
            ),
            (
                "rev",
                etpConst['etpdatabaserevisionfile'],
                False,
                "%s %s %s" % (
                    red(_("Downloading revision")),
                    darkgreen(etpConst['etpdatabaserevisionfile']),
                    red("..."),
                )
            ),
            (
                "make.conf",
                g_make_conf,
                True,
                "%s %s %s" % (
                    red(_("Downloading SPM global configuration")),
                    darkgreen(g_make_conf),
                    red("..."),
                )
            ),
            (
                "package.unmask",
                pkg_unmask,
                True,
                "%s %s %s" % (
                    red(_("Downloading SPM package unmasking configuration")),
                    darkgreen(pkg_unmask),
                    red("..."),
                )
            ),
            (
                "package.keywords",
                pkg_keywords,
                True,
                "%s %s %s" % (
                    red(_("Downloading SPM package keywording configuration")),
                    darkgreen(pkg_keywords),
                    red("..."),
                )
            ),
            (
                "package.use",
                pkg_use,
                True,
                "%s %s %s" % (
                    red(_("Downloading SPM package USE flags configuration")),
                    darkgreen(pkg_use),
                    red("..."),
                )
            ),
            (
                "profile.link",
                profile_link,
                True,
                "%s %s %s" % (
                    red(_("Downloading SPM Profile configuration")),
                    darkgreen(profile_link),
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
            )
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
                "%s: %s" % (darkgreen(_("unpacked meta file")),brown(fp),),
                header = blue(u"\t  << ")
            )

        downloaded_by_unpack = set()
        for item, myfile, ignorable, mytxt in download_items:

            # if it's been already downloaded, skip
            if myfile in downloaded_by_unpack: continue

            my_show_info(mytxt)
            mystatus = self.download_item(item, repo, disallow_redirect = True)
            mytype = 'info'

            # download failed, is it critical?
            if not mystatus:
                if ignorable:
                    message = "%s: %s." % (blue(myfile),red(_("not available, it's ok")))
                else:
                    mytype = 'warning'
                    message = "%s: %s." % (blue(myfile),darkred(_("not available, not much ok!")))
                my_show_down_status(message, mytype)
                continue

            myurl, mypath = self._construct_paths(item, repo, None)
            message = "%s: %s." % (blue(myfile),darkgreen(_("available, w00t!")))
            my_show_down_status(message, mytype)
            if item not in objects_to_unpack: continue
            if not (os.path.isfile(mypath) and os.access(mypath,os.R_OK)): continue

            while 1:
                tmpdir = os.path.join(os.path.dirname(mypath),"meta_unpack_%s" % (random.randint(1,10000),))
                if not os.path.lexists(tmpdir): break
            os.makedirs(tmpdir,0775)

            repo_dir = etpRepositories[repo]['dbpath']
            try:
                done = self.entropyTools.universal_uncompress(mypath, tmpdir, catch_empty = True)
                if not done: continue
                myfiles_to_move = set(os.listdir(tmpdir))

                # exclude files not available by default
                files_not_found_file = etpConst['etpdatabasemetafilesnotfound']
                if files_not_found_file in myfiles_to_move:
                    myfiles_to_move.remove(files_not_found_file)
                    try:
                        with open(os.path.join(tmpdir,files_not_found_file),"r") as f:
                            f_nf = [x.strip() for x in f.readlines()]
                            downloaded_by_unpack |= set(f_nf)
                    except IOError:
                        pass

                for myfile in sorted(myfiles_to_move):
                    from_mypath = os.path.join(tmpdir,myfile)
                    to_mypath = os.path.join(repo_dir,myfile)
                    try:
                        os.rename(from_mypath,to_mypath)
                        downloaded_by_unpack.add(myfile)
                        my_show_file_unpack(myfile)
                    except OSError:
                        continue

            finally:

                shutil.rmtree(tmpdir,True)
                try: os.rmdir(tmpdir)
                except OSError: pass


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
        dbconn = self.Entropy.openRepositoryDatabase(repo)
        dbconn.createAllIndexes()
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
        self.Entropy.closeAllRepositoryDatabases()

        # let's dance!
        mytxt = darkgreen("%s ...") % (_("Repositories synchronization"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = darkred(" @@ ")
        )

        gave_up = self.Entropy.lock_check(self.Entropy._resources_run_check_lock)
        if gave_up:
            return 3

        locked = self.Entropy.application_lock_check()
        if locked:
            self.Entropy._resources_run_remove_lock()
            return 4

        # lock
        self.Entropy._resources_run_create_lock()
        try:
            rc = self.run_sync()
        except:
            self.Entropy._resources_run_remove_lock()
            raise
        if rc: return rc

        # remove lock
        self.Entropy._resources_run_remove_lock()

        if (self.notAvailable >= len(self.reponames)):
            return 2
        elif (self.notAvailable > 0):
            return 1

        return 0


class Trigger:

    import entropy.tools as entropyTools
    def __init__(self, EquoInstance, phase, pkgdata, package_action = None):

        if not isinstance(EquoInstance,Client):
            mytxt = _("A valid Entropy Instance is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        self.Entropy = EquoInstance
        self.clientLog = self.Entropy.clientLog
        self.validPhases = ("preinstall","postinstall","preremove","postremove")
        self.pkgdata = pkgdata
        self.prepared = False
        self.triggers = set()
        self.gentoo_compat = etpConst['gentoo-compat']
	self.package_action = package_action

        '''
        @ description: Gentoo toolchain variables
        '''
        self.MODULEDB_DIR="/var/lib/module-rebuild/"
        self.INITSERVICES_DIR="/var/lib/init.d/"

        ''' portage stuff '''
        if self.gentoo_compat:
            try:
                Spm = self.Entropy.Spm()
                self.Spm = Spm
            except Exception, e:
                self.entropyTools.printTraceback()
                mytxt = darkred("%s, %s: %s, %s !") % (
                    _("Portage interface can't be loaded"),
                    _("Error"),
                    e,
                    _("please fix"),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = bold(" !!! ")
                )
                self.gentoo_compat = False

        self.phase = phase
        # validate phase
        self.phaseValidation()

    def phaseValidation(self):
        if self.phase not in self.validPhases:
            mytxt = "%s: %s" % (_("Valid phases"),self.validPhases,)
            raise InvalidData("InvalidData: %s" % (mytxt,))

    def prepare(self):
        func = getattr(self,self.phase)
        self.triggers = func()
        remove = set()
        for trigger in self.triggers:
            if trigger in etpUi[self.phase+'_triggers_disable']:
                remove.add(trigger)
        self.triggers = [x for x in self.triggers if x not in remove]
        del remove
        self.prepared = True

    def run(self):
        for trigger in self.triggers:
            fname = 'trigger_%s' % (trigger,)
            if not hasattr(self,fname): continue
            getattr(self,fname)()

    def kill(self):
        self.prepared = False
        del self.triggers[:]

    def postinstall(self):

        functions = []
        # Gentoo hook
        if self.gentoo_compat:
            functions.append('ebuild_postinstall')

        # equo purge cache
        if self.pkgdata['category']+"/"+self.pkgdata['name'] == "sys-apps/entropy":
            functions.append("purgecache")

        # binutils configuration
        if self.pkgdata['category']+"/"+self.pkgdata['name'] == "sys-devel/binutils":
            functions.append("binutilsswitch")

        # opengl configuration
        if (self.pkgdata['category'] == "x11-drivers") and \
            (self.pkgdata['name'].startswith("nvidia-") or \
            self.pkgdata['name'].startswith("ati-")):
                if "ebuild_postinstall" in functions:
                    # disabling gentoo postinstall since we reimplemented it
                    functions.remove("ebuild_postinstall")
                functions.append("openglsetup")

        # load linker paths
        ldpaths = self.Entropy.entropyTools.collectLinkerPaths()
        for x in self.pkgdata['content']:

            if (x.startswith("/etc/conf.d") or \
                x.startswith("/etc/init.d")) and \
                ("conftouch" not in functions):
                    functions.append('conftouch')

            if x.startswith('/lib/modules/') and ("kernelmod" not in functions):
                if "ebuild_postinstall" in functions:
                    # disabling gentoo postinstall since we reimplemented it
                    functions.remove("ebuild_postinstall")
                functions.append('kernelmod')

            if x.startswith('/boot/kernel-') and ("addbootablekernel" not in functions):
                functions.append('addbootablekernel')

            if x.startswith('/usr/src/') and ("createkernelsym" not in functions):
                functions.append('createkernelsym')

            if x.startswith('/etc/env.d/') and ("env_update" not in functions):
                functions.append('env_update')

            if (os.path.dirname(x) in ldpaths) and ("run_ldconfig" not in functions):
                if x.find(".so") > -1:
                    functions.append('run_ldconfig')

        if self.pkgdata['trigger']:
            functions.append('call_ext_postinstall')

        del ldpaths
        return functions

    def preinstall(self):

        functions = []

        # Gentoo hook
        if self.gentoo_compat:
            functions.append('ebuild_preinstall')

        for x in self.pkgdata['content']:
            if x.startswith("/etc/init.d/") and ("initinform" not in functions):
                functions.append('initinform')
            if x.startswith("/boot") and ("mountboot" not in functions):
                functions.append('mountboot')

        if self.pkgdata['trigger']:
            functions.append('call_ext_preinstall')

        return functions

    def postremove(self):

        functions = []

        # load linker paths
        ldpaths = self.Entropy.entropyTools.collectLinkerPaths()

        for x in self.pkgdata['removecontent']:
            if x.startswith('/boot/kernel-') and ("removebootablekernel" not in functions):
                functions.append('removebootablekernel')
            if x.startswith('/etc/init.d/') and ("initdisable" not in functions):
                functions.append('initdisable')
            if x.endswith('.py') and ("cleanpy" not in functions):
                functions.append('cleanpy')
            if x.startswith('/etc/env.d/') and ("env_update" not in functions):
                functions.append('env_update')
            if (os.path.dirname(x) in ldpaths) and ("run_ldconfig" not in functions):
                if x.find(".so") > -1:
                    functions.append('run_ldconfig')

        if self.pkgdata['trigger']:
            functions.append('call_ext_postremove')

        del ldpaths
        return functions


    def preremove(self):

        functions = []

        # Gentoo hook
        if self.gentoo_compat:
            functions.append('ebuild_preremove')
            functions.append('ebuild_postremove')
            # doing here because we need /var/db/pkg stuff in place and also because doesn't make any difference

        # opengl configuration
        if (self.pkgdata['category'] == "x11-drivers") and (self.pkgdata['name'].startswith("nvidia-") or self.pkgdata['name'].startswith("ati-")):
            if "ebuild_preremove" in functions:
                functions.remove("ebuild_preremove")
            if "ebuild_postremove" in functions:
                # disabling gentoo postinstall since we reimplemented it
                functions.remove("ebuild_postremove")
            if self.package_action not in ["remove_conflict"]:
                functions.append("openglsetup_xorg")

        for x in self.pkgdata['removecontent']:
            if x.startswith("/boot"):
                functions.append('mountboot')
                break

        if self.pkgdata['trigger']:
            functions.append('call_ext_preremove')

        return functions


    '''
        Real triggers
    '''
    def trigger_call_ext_preinstall(self):
        return self.trigger_call_ext_generic()

    def trigger_call_ext_postinstall(self):
        return self.trigger_call_ext_generic()

    def trigger_call_ext_preremove(self):
        return self.trigger_call_ext_generic()

    def trigger_call_ext_postremove(self):
        return self.trigger_call_ext_generic()

    def trigger_call_ext_generic(self):
        try:
            return self.do_trigger_call_ext_generic()
        except Exception, e:
            mykey = self.pkgdata['category']+"/"+self.pkgdata['name']
            tb = self.entropyTools.getTraceback()
            self.Entropy.updateProgress(tb, importance = 0, type = "error")
            self.Entropy.clientLog.write(tb)
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] ATTENTION Cannot run External trigger for "+mykey+"!! "+str(Exception)+": "+str(e)
            )
            mytxt = "%s: %s %s. %s." % (
                bold(_("QA")),
                brown(_("Cannot run External trigger for")),
                bold(mykey),
                brown(_("Please report it")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return 0

    class EntropyShSandbox:

        def __env_setup(self, stage, pkgdata):

            # mandatory variables
            category = pkgdata.get('category')
            if isinstance(category,unicode):
                category = category.encode('utf-8')

            pn = pkgdata.get('name')
            if isinstance(pn,unicode):
                pn = pn.encode('utf-8')

            pv = pkgdata.get('version')
            if isinstance(pv,unicode):
                pv = pv.encode('utf-8')

            pr = self.entropyTools.dep_get_portage_revision(pv)
            pvr = pv
            if pr == "r0": pvr += "-%s" % (pr,)

            pet = pkgdata.get('versiontag')
            if isinstance(pet,unicode):
                pet = pet.encode('utf-8')

            per = pkgdata.get('revision')
            if isinstance(per,unicode):
                per = per.encode('utf-8')

            etp_branch = pgkdata.get('branch')
            if isinstance(etp_branch,unicode):
                etp_branch = etp_branch.encode('utf-8')

            slot = pgkdata.get('slot')
            if isinstance(slot,unicode):
                slot = slot.encode('utf-8')

            pkgatom = pkgdata.get('atom')
            pkgkey = self.entropyTools.dep_getkey(pkgatom)
            pvrte = pkgatom[len(pkgkey)+1:]
            if isinstance(pvrte,unicode):
                pvrte = pvrte.encode('utf-8')

            etpapi = pkgdata.get('etpapi')
            if isinstance(etpapi,unicode):
                etpapi = etpapi.encode('utf-8')

            p = pkgatom
            if isinstance(p,unicode):
                p = p.encode('utf-8')

            chost, cflags, cxxflags = pkgdata.get('chost'), pkgdata.get('cflags'), pkgdata.get('cxxflags')

            chost = pkgdata.get('etpapi')
            if isinstance(chost,unicode):
                chost = chost.encode('utf-8')

            cflags = pkgdata.get('etpapi')
            if isinstance(cflags,unicode):
                cflags = cflags.encode('utf-8')

            cxxflags = pkgdata.get('etpapi')
            if isinstance(cxxflags,unicode):
                cxxflags = cxxflags.encode('utf-8')

            # Not mandatory variables

            eclasses = ' '.join(pkgdata.get('eclasses',[]))
            if isinstance(eclasses,unicode):
                eclasses = eclasses.encode('utf-8')

            unpackdir = pkgdata.get('unpackdir','')
            if isinstance(unpackdir,unicode):
                unpackdir = unpackdir.encode('utf-8')

            imagedir = pkgdata.get('imagedir','')
            if isinstance(imagedir,unicode):
                imagedir = imagedir.encode('utf-8')

            sb_dirs = [unpackdir,imagedir]
            sb_write = ':'.join(sb_dirs)

            myenv = {
                "ETP_API": etpSys['api'],
                "ETP_LOG": self.Entropy.clientLog.get_fpath(),
                "ETP_STAGE": stage, # entropy trigger stage
                "ETP_PHASE": self.__get_sh_stage(), # entropy trigger phase
                "ETP_BRANCH": etp_branch,
                "CATEGORY": category, # package category
                "PN": pn, # package name
                "PV": pv, # package version
                "PR": pr, # package revision (portage)
                "PVR": pvr, # package version+revision
                "PVRTE": pvrte, # package version+revision+entropy tag+entropy rev
                "PER": per, # package entropy revision
                "PET": pet, # package entropy tag
                "SLOT": slot, # package slot
                "PAPI": etpapi, # package entropy api
                "P": p, # complete package atom
                "WORKDIR": unpackdir, # temporary package workdir
                "B": unpackdir, # unpacked binary package directory?
                "D": imagedir, # package unpack destination (before merging to live)
                "ENTROPY_TMPDIR": etpConst['packagestmpdir'], # entropy temporary directory
                "CFLAGS": cflags, # compile flags
                "CXXFLAGS": cxxflags, # compile flags
                "CHOST": chost, # *nix CHOST
                "PORTAGE_ECLASSES": eclasses, # portage eclasses, " " separated
                "ROOT": etpConst['systemroot'],
                "SANDBOX_WRITE": sb_write,
            }
            sysenv = os.environ.copy()
            sysenv.update(myenv)
            return sysenv

        def __get_sh_stage(self, stage):
            mydict = {
                "preinstall": "pkg_preinst",
                "postinstall": "pkg_postinst",
                "preremove": "pkg_prerm",
                "postremove": "pkg_postrm",
            }
            return mydict.get(stage)

        def run(self, stage, pkgdata, trigger_file):
            env = self.__env_setup(stage, pkgdata)
            p = subprocess.Popen([trigger_file, stage],
                stdout = sys.stdout, stderr = sys.stderr,
                env = env
            )
            rc = p.wait()
            if os.path.isfile(trigger_file):
                os.remove(trigger_file)
            return rc

    class EntropyPySandbox:

        def run(self, stage, pkgdata, trigger_file):
            my_ext_status = 1
            if os.path.isfile(trigger_file):
                execfile(trigger_file)
            if os.path.isfile(trigger_file):
                os.remove(trigger_file)
            return my_ext_status

    def do_trigger_call_ext_generic(self):

        # if mute, supress portage output
        if etpUi['mute']:
            oldsystderr = sys.stderr
            oldsysstdout = sys.stdout
            stdfile = open("/dev/null","w")
            sys.stdout = stdfile
            sys.stderr = stdfile

        tg_pfx = "%s/trigger-" % (etpConst['entropyunpackdir'],)
        while 1:
            triggerfile = "%s%s" % (tg_pfx,self.Entropy.entropyTools.getRandomNumber(),)
            if not os.path.isfile(triggerfile): break

        triggerdir = os.path.dirname(triggerfile)
        if not os.path.isdir(triggerdir):
            os.makedirs(triggerdir)

        f = open(triggerfile,"w")
        chunk = 1024
        start = 0
        while 1:
            buf = self.pkgdata['trigger'][start:]
            if not buf: break
            f.write(buf)
            start += chunk
        f.flush()
        f.close()

        # if mute, restore old stdout/stderr
        if etpUi['mute']:
            sys.stderr = oldsystderr
            sys.stdout = oldsysstdout
            stdfile.close()

        f = open(triggerfile,"r")
        interpreter = f.readline().strip()
        f.close()
        entropy_sh = etpConst['trigger_sh_interpreter']
        if interpreter == "#!%s" % (entropy_sh,):
            os.chmod(triggerfile,0775)
            my = self.EntropyShSandbox()
        else:
            my = self.EntropyPySandbox()
        return my.run(self.phase, self.pkgdata, triggerfile)


    def trigger_purgecache(self):
        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "[POST] Purging Entropy cache..."
        )

        mytxt = "%s: %s." % (_("Please remember"),_("It is always better to leave Entropy updates isolated"),)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        mytxt = "%s ..." % (_("Purging Entropy cache"),)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        self.Entropy.purge_cache(False)

    def trigger_conftouch(self):
        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "[POST] Updating {conf.d,init.d} mtime..."
        )
        mytxt = "%s ..." % (_("Updating {conf.d,init.d} mtime"),)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        for item in self.pkgdata['content']:
            if not (item.startswith("/etc/conf.d") or item.startswith("/etc/conf.d")):
                continue
            if not os.path.isfile(item):
                continue
            if not os.access(item,os.W_OK):
                continue
            try:
                f = open(item,"abw")
                f.flush()
                f.close()
            except (OSError,IOError,):
                pass

    def trigger_binutilsswitch(self):
        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "[POST] Configuring Binutils Profile..."
        )
        mytxt = "%s ..." % (_("Configuring Binutils Profile"),)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        # get binutils profile
        pkgsplit = self.Entropy.entropyTools.catpkgsplit(
            self.pkgdata['category'] + "/" + self.pkgdata['name'] + "-" + self.pkgdata['version']
        )
        profile = self.pkgdata['chost']+"-"+pkgsplit[2]
        self.trigger_set_binutils_profile(profile)

    def trigger_kernelmod(self):
        if self.pkgdata['category'] != "sys-kernel":
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Updating moduledb..."
            )
            mytxt = "%s ..." % (_("Updating moduledb"),)
            self.Entropy.updateProgress(
                brown(mytxt),
                importance = 0,
                header = red("   ## ")
            )
            item = 'a:1:'+self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
            self.trigger_update_moduledb(item)
        mytxt = "%s ..." % (_("Running depmod"),)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        # get kernel modules dir name
        name = ''
        for item in self.pkgdata['content']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/lib/modules/"):
                name = item[len(etpConst['systemroot']):]
                name = name.split("/")[3]
                break
        if name:
            self.trigger_run_depmod(name)

    def trigger_initdisable(self):
        for item in self.pkgdata['removecontent']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/etc/init.d/") and os.path.isfile(item):
                myroot = "/"
                if etpConst['systemroot']:
                    myroot = etpConst['systemroot']+"/"
                runlevels_dir = etpConst['systemroot']+"/etc/runlevels"
                runlevels = []
                if os.path.isdir(runlevels_dir) and os.access(runlevels_dir,os.R_OK):
                    runlevels = [x for x in os.listdir(runlevels_dir) \
                        if os.path.isdir(os.path.join(runlevels_dir,x)) \
                        and os.path.isfile(os.path.join(runlevels_dir,x,os.path.basename(item)))
                    ]
                for runlevel in runlevels:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[POST] Removing boot service: %s, runlevel: %s" % (os.path.basename(item),runlevel,)
                    )
                    mytxt = "%s: %s : %s" % (brown(_("Removing boot service")),os.path.basename(item),runlevel,)
                    self.Entropy.updateProgress(
                        mytxt,
                        importance = 0,
                        header = red("   ## ")
                    )
                    cmd = 'ROOT="%s" rc-update del %s %s' % (myroot, os.path.basename(item), runlevel)
                    subprocess.call(cmd, shell = True)

    def trigger_initinform(self):
        for item in self.pkgdata['content']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/etc/init.d/") and not os.path.isfile(etpConst['systemroot']+item):
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] A new service will be installed: %s" % (item,)
                )
                mytxt = "%s: %s" % (brown(_("A new service will be installed")),item,)
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )

    def trigger_openglsetup(self):
        opengl = "xorg-x11"
        if self.pkgdata['name'] == "nvidia-drivers":
            opengl = "nvidia"
        elif self.pkgdata['name'] == "ati-drivers":
            opengl = "ati"
        # is there eselect ?
        eselect = subprocess.call("eselect opengl &> /dev/null", shell = True)
        if eselect == 0:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Reconfiguring OpenGL to %s ..." % (opengl,)
            )
            mytxt = "%s ..." % (brown(_("Reconfiguring OpenGL")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            quietstring = ''
            if etpUi['quiet']: quietstring = " &>/dev/null"
            if etpConst['systemroot']:
                subprocess.call('echo "eselect opengl set --use-old %s" | chroot %s %s' % (opengl,etpConst['systemroot'],quietstring,), shell = True)
            else:
                subprocess.call('eselect opengl set --use-old %s %s' % (opengl,quietstring,), shell = True)
        else:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Eselect NOT found, cannot run OpenGL trigger"
            )
            mytxt = "%s !" % (brown(_("Eselect NOT found, cannot run OpenGL trigger")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ##")
            )

    def trigger_openglsetup_xorg(self):
        eselect = subprocess.call("eselect opengl &> /dev/null", shell = True)
        if eselect == 0:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Reconfiguring OpenGL to fallback xorg-x11 ..."
            )
            mytxt = "%s ..." % (brown(_("Reconfiguring OpenGL")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            quietstring = ''
            if etpUi['quiet']: quietstring = " &>/dev/null"
            if etpConst['systemroot']:
                subprocess.call('echo "eselect opengl set xorg-x11" | chroot %s %s' % (etpConst['systemroot'],quietstring,), shell = True)
            else:
                subprocess.call('eselect opengl set xorg-x11 %s' % (quietstring,), shell = True)
        else:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Eselect NOT found, cannot run OpenGL trigger"
            )
            mytxt = "%s !" % (brown(_("Eselect NOT found, cannot run OpenGL trigger")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ##")
            )

    # FIXME: this only supports grub (no lilo support)
    def trigger_addbootablekernel(self):
        boot_mount = False
        if os.path.ismount("/boot"):
            boot_mount = True
        kernels = [x for x in self.pkgdata['content'] if x.startswith("/boot/kernel-")]
        if boot_mount:
            kernels = [x[len("/boot"):] for x in kernels]
        for kernel in kernels:
            mykernel = kernel.split('/kernel-')[1]
            initramfs = "/boot/initramfs-"+mykernel
            if initramfs not in self.pkgdata['content']:
                initramfs = ''
            elif boot_mount:
                initramfs = initramfs[len("/boot"):]

            # configure GRUB
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Configuring GRUB bootloader. Adding the new kernel..."
            )
            mytxt = "%s. %s ..." % (
                _("Configuring GRUB bootloader"),
                _("Adding the new kernel"),
            )
            self.Entropy.updateProgress(
                brown(mytxt),
                importance = 0,
                header = red("   ## ")
            )
            self.trigger_configure_boot_grub(kernel,initramfs)

    # FIXME: this only supports grub (no lilo support)
    def trigger_removebootablekernel(self):
        kernels = [x for x in self.pkgdata['content'] if x.startswith("/boot/kernel-")]
        for kernel in kernels:
            initramfs = "/boot/initramfs-"+kernel[13:]
            if initramfs not in self.pkgdata['content']:
                initramfs = ''
            # configure GRUB
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Configuring GRUB bootloader. Removing the selected kernel..."
            )
            mytxt = "%s. %s ..." % (
                _("Configuring GRUB bootloader"),
                _("Removing the selected kernel"),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            self.trigger_remove_boot_grub(kernel,initramfs)

    def trigger_mountboot(self):
        # is in fstab?
        if etpConst['systemroot']:
            return
        if os.path.isfile("/etc/fstab"):
            f = open("/etc/fstab","r")
            fstab = f.readlines()
            fstab = self.Entropy.entropyTools.listToUtf8(fstab)
            f.close()
            for line in fstab:
                fsline = line.split()
                if len(fsline) > 1:
                    if fsline[1] == "/boot":
                        if not os.path.ismount("/boot"):
                            # trigger mount /boot
                            rc = subprocess.call("mount /boot &> /dev/null", shell = True)
                            if rc == 0:
                                self.Entropy.clientLog.log(
                                    ETP_LOGPRI_INFO,
                                    ETP_LOGLEVEL_NORMAL,
                                    "[PRE] Mounted /boot successfully"
                                )
                                self.Entropy.updateProgress(
                                    brown(_("Mounted /boot successfully")),
                                    importance = 0,
                                    header = red("   ## ")
                                )
                            elif rc != 8192: # already mounted
                                self.Entropy.clientLog.log(
                                    ETP_LOGPRI_INFO,
                                    ETP_LOGLEVEL_NORMAL,
                                    "[PRE] Cannot mount /boot automatically !!"
                                )
                                self.Entropy.updateProgress(
                                    brown(_("Cannot mount /boot automatically !!")),
                                    importance = 0,
                                    header = red("   ## ")
                                )
                            break

    def trigger_cleanpy(self):
        pyfiles = [x for x in self.pkgdata['content'] if x.endswith(".py")]
        for item in pyfiles:
            item = etpConst['systemroot']+item
            if os.path.isfile(item+"o"):
                try: os.remove(item+"o")
                except OSError: pass
            if os.path.isfile(item+"c"):
                try: os.remove(item+"c")
                except OSError: pass

    def trigger_createkernelsym(self):
        for item in self.pkgdata['content']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/usr/src/"):
                # extract directory
                try:
                    todir = item[len(etpConst['systemroot']):]
                    todir = todir.split("/")[3]
                except:
                    continue
                if os.path.isdir(etpConst['systemroot']+"/usr/src/"+todir):
                    # link to /usr/src/linux
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[POST] Creating kernel symlink "+etpConst['systemroot']+"/usr/src/linux for /usr/src/"+todir
                    )
                    mytxt = "%s %s %s %s" % (
                        _("Creating kernel symlink"),
                        etpConst['systemroot']+"/usr/src/linux",
                        _("for"),
                        "/usr/src/"+todir,
                    )
                    self.Entropy.updateProgress(
                        brown(mytxt),
                        importance = 0,
                        header = red("   ## ")
                    )
                    if os.path.isfile(etpConst['systemroot']+"/usr/src/linux") or \
                        os.path.islink(etpConst['systemroot']+"/usr/src/linux"):
                            os.remove(etpConst['systemroot']+"/usr/src/linux")
                    if os.path.isdir(etpConst['systemroot']+"/usr/src/linux"):
                        mydir = etpConst['systemroot']+"/usr/src/linux."+str(self.Entropy.entropyTools.getRandomNumber())
                        while os.path.isdir(mydir):
                            mydir = etpConst['systemroot']+"/usr/src/linux."+str(self.Entropy.entropyTools.getRandomNumber())
                        shutil.move(etpConst['systemroot']+"/usr/src/linux",mydir)
                    try:
                        os.symlink(todir,etpConst['systemroot']+"/usr/src/linux")
                    except OSError: # not important in the end
                        pass
                    break

    def trigger_run_ldconfig(self):
        if not etpConst['systemroot']:
            myroot = "/"
        else:
            myroot = etpConst['systemroot']+"/"
        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "[POST] Running ldconfig"
        )
        mytxt = "%s %s" % (_("Regenerating"),"/etc/ld.so.cache",)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        subprocess.call("ldconfig -r %s &> /dev/null" % (myroot,), shell = True)

    def trigger_env_update(self):

        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "[POST] Running env-update"
        )
        if os.access(etpConst['systemroot']+"/usr/sbin/env-update",os.X_OK):
            mytxt = "%s ..." % (_("Updating environment"),)
            self.Entropy.updateProgress(
                brown(mytxt),
                importance = 0,
                header = red("   ## ")
            )
            if etpConst['systemroot']:
                subprocess.call("echo 'env-update --no-ldconfig' | chroot %s &> /dev/null" % (etpConst['systemroot'],), shell = True)
            else:
                subprocess.call('env-update --no-ldconfig &> /dev/null', shell = True)

    def trigger_ebuild_postinstall(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        oldstdout = sys.stdout
        sys.stderr = stdfile

        myebuild = [self.pkgdata['xpakdir']+"/"+x for x in os.listdir(self.pkgdata['xpakdir']) if x.endswith(etpConst['spm']['source_build_ext'])]
        if myebuild:
            myebuild = myebuild[0]
            portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
            self.Entropy.updateProgress(
                brown("Ebuild: pkg_postinst()"),
                importance = 0,
                header = red("   ## ")
            )
            try:

                if not os.path.isfile(self.pkgdata['unpackdir']+"/portage/"+portage_atom+"/temp/environment"):
                    # if environment is not yet created, we need to run pkg_setup()
                    sys.stdout = stdfile
                    rc = self.Spm.spm_doebuild(
                        myebuild,
                        mydo = "setup",
                        tree = "bintree",
                        cpv = portage_atom,
                        portage_tmpdir = self.pkgdata['unpackdir'],
                        licenses = self.pkgdata['accept_license']
                    )
                    if rc == 1:
                        self.Entropy.clientLog.log(
                            ETP_LOGPRI_INFO,
                            ETP_LOGLEVEL_NORMAL,
                            "[POST] ATTENTION Cannot properly run Gentoo postinstall (pkg_setup())"
                            " trigger for "+str(portage_atom)+". Something bad happened."
                        )
                    sys.stdout = oldstdout

                rc = self.Spm.spm_doebuild(
                    myebuild,
                    mydo = "postinst",
                    tree = "bintree",
                    cpv = portage_atom,
                    portage_tmpdir = self.pkgdata['unpackdir'],
                    licenses = self.pkgdata['accept_license']
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[POST] ATTENTION Cannot properly run Gentoo postinstall (pkg_postinst()) trigger for " + \
                        str(portage_atom) + ". Something bad happened."
                        )

            except Exception, e:
                sys.stdout = oldstdout
                self.entropyTools.printTraceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[POST] ATTENTION Cannot run Portage trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Portage trigger for")),
                    bold(str(portage_atom)),
                    brown(_("Please report it")),
                    bold(_("Attach this")),
                    darkred(etpConst['spmlogfile']),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
        sys.stderr = oldstderr
        sys.stdout = oldstdout
        stdfile.close()
        return 0

    def trigger_ebuild_preinstall(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        oldstdout = sys.stdout
        sys.stderr = stdfile

        myebuild = [self.pkgdata['xpakdir']+"/"+x for x in os.listdir(self.pkgdata['xpakdir']) if x.endswith(etpConst['spm']['source_build_ext'])]
        if myebuild:
            myebuild = myebuild[0]
            portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
            self.Entropy.updateProgress(
                brown(" Ebuild: pkg_preinst()"),
                importance = 0,
                header = red("   ##")
            )
            try:
                sys.stdout = stdfile
                rc = self.Spm.spm_doebuild(
                    myebuild,
                    mydo = "setup",
                    tree = "bintree",
                    cpv = portage_atom,
                    portage_tmpdir = self.pkgdata['unpackdir'],
                    licenses = self.pkgdata['accept_license']
                ) # create mysettings["T"]+"/environment"
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[PRE] ATTENTION Cannot properly run Portage preinstall (pkg_setup()) trigger for " + \
                        str(portage_atom) + ". Something bad happened."
                    )
                sys.stdout = oldstdout
                rc = self.Spm.spm_doebuild(
                    myebuild,
                    mydo = "preinst",
                    tree = "bintree",
                    cpv = portage_atom,
                    portage_tmpdir = self.pkgdata['unpackdir'],
                    licenses = self.pkgdata['accept_license']
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[PRE] ATTENTION Cannot properly run Gentoo preinstall (pkg_preinst()) trigger for " + \
                        str(portage_atom)+". Something bad happened."
                    )
            except Exception, e:
                sys.stdout = oldstdout
                self.entropyTools.printTraceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] ATTENTION Cannot run Gentoo preinst trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Portage trigger for")),
                    bold(str(portage_atom)),
                    brown(_("Please report it")),
                    bold(_("Attach this")),
                    darkred(etpConst['spmlogfile']),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
        sys.stderr = oldstderr
        sys.stdout = oldstdout
        stdfile.close()
        return 0

    def trigger_ebuild_preremove(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        sys.stderr = stdfile

        portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
        try:
            myebuild = self.Spm.get_vdb_path()+portage_atom+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']+etpConst['spm']['source_build_ext']
        except:
            myebuild = ''

        self.myebuild_moved = None
        if os.path.isfile(myebuild):
            try:
                myebuild = self._setup_remove_ebuild_environment(myebuild, portage_atom)
            except EOFError, e:
                sys.stderr = oldstderr
                stdfile.close()
                # stuff on system is broken, ignore it
                self.Entropy.updateProgress(
                    darkred("!!! Ebuild: pkg_prerm() failed, EOFError: ")+str(e)+darkred(" - ignoring"),
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )
                return 0
            except ImportError, e:
                sys.stderr = oldstderr
                stdfile.close()
                # stuff on system is broken, ignore it
                self.Entropy.updateProgress(
                    darkred("!!! Ebuild: pkg_prerm() failed, ImportError: ")+str(e)+darkred(" - ignoring"),
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )
                return 0

        if os.path.isfile(myebuild):

            self.Entropy.updateProgress(
                                    brown(" Ebuild: pkg_prerm()"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            try:
                rc = self.Spm.spm_doebuild(
                    myebuild,
                    mydo = "prerm",
                    tree = "bintree",
                    cpv = portage_atom,
                    portage_tmpdir = etpConst['entropyunpackdir'] + "/" + portage_atom
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[PRE] ATTENTION Cannot properly run Portage trigger for " + \
                        str(portage_atom)+". Something bad happened."
                    )
            except Exception, e:
                sys.stderr = oldstderr
                stdfile.close()
                self.entropyTools.printTraceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] ATTENTION Cannot run Portage preremove trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Portage trigger for")),
                    bold(str(portage_atom)),
                    brown(_("Please report it")),
                    bold(_("Attach this")),
                    darkred(etpConst['spmlogfile']),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
                return 0

        sys.stderr = oldstderr
        stdfile.close()
        self._remove_overlayed_ebuild()
        return 0

    def trigger_ebuild_postremove(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        sys.stderr = stdfile

        portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
        try:
            myebuild = self.Spm.get_vdb_path()+portage_atom+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']+etpConst['spm']['source_build_ext']
        except:
            myebuild = ''

        self.myebuild_moved = None
        if os.path.isfile(myebuild):
            try:
                myebuild = self._setup_remove_ebuild_environment(myebuild, portage_atom)
            except EOFError, e:
                sys.stderr = oldstderr
                stdfile.close()
                # stuff on system is broken, ignore it
                self.Entropy.updateProgress(
                    darkred("!!! Ebuild: pkg_postrm() failed, EOFError: ")+str(e)+darkred(" - ignoring"),
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )
                return 0
            except ImportError, e:
                sys.stderr = oldstderr
                stdfile.close()
                # stuff on system is broken, ignore it
                self.Entropy.updateProgress(
                    darkred("!!! Ebuild: pkg_postrm() failed, ImportError: ")+str(e)+darkred(" - ignoring"),
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )
                return 0

        if os.path.isfile(myebuild):
            self.Entropy.updateProgress(
                                    brown(" Ebuild: pkg_postrm()"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            try:
                rc = self.Spm.spm_doebuild(
                    myebuild,
                    mydo = "postrm",
                    tree = "bintree",
                    cpv = portage_atom,
                    portage_tmpdir = etpConst['entropyunpackdir']+"/"+portage_atom
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[PRE] ATTENTION Cannot properly run Gentoo postremove trigger for " + \
                        str(portage_atom)+". Something bad happened."
                    )
            except Exception, e:
                sys.stderr = oldstderr
                stdfile.close()
                self.entropyTools.printTraceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] ATTENTION Cannot run Gentoo postremove trigger for " + \
                    portage_atom+"!! "+str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Portage trigger for")),
                    bold(str(portage_atom)),
                    brown(_("Please report it")),
                    bold(_("Attach this")),
                    darkred(etpConst['spmlogfile']),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
                return 0

        sys.stderr = oldstderr
        stdfile.close()
        self._remove_overlayed_ebuild()
        return 0

    def _setup_remove_ebuild_environment(self, myebuild, portage_atom):

        ebuild_dir = os.path.dirname(myebuild)
        ebuild_file = os.path.basename(myebuild)

        # copy the whole directory in a safe place
        dest_dir = os.path.join(etpConst['entropyunpackdir'],"vardb/"+portage_atom)
        if os.path.exists(dest_dir):
            if os.path.isdir(dest_dir):
                shutil.rmtree(dest_dir,True)
            elif os.path.isfile(dest_dir) or os.path.islink(dest_dir):
                os.remove(dest_dir)
        os.makedirs(dest_dir)
        items = os.listdir(ebuild_dir)
        for item in items:
            myfrom = os.path.join(ebuild_dir,item)
            myto = os.path.join(dest_dir,item)
            shutil.copy2(myfrom,myto)

        newmyebuild = os.path.join(dest_dir,ebuild_file)
        if os.path.isfile(newmyebuild):
            myebuild = newmyebuild
            self.myebuild_moved = myebuild
            self._ebuild_env_setup_hook(myebuild)
        return myebuild

    def _ebuild_env_setup_hook(self, myebuild):
        ebuild_path = os.path.dirname(myebuild)
        if not etpConst['systemroot']:
            myroot = "/"
        else:
            myroot = etpConst['systemroot']+"/"

        # we need to fix ROOT= if it's set inside environment
        bz2envfile = os.path.join(ebuild_path,"environment.bz2")
        if os.path.isfile(bz2envfile) and os.path.isdir(myroot):
            import bz2
            envfile = self.Entropy.entropyTools.unpackBzip2(bz2envfile)
            bzf = bz2.BZ2File(bz2envfile,"w")
            f = open(envfile,"r")
            line = f.readline()
            while line:
                if line.startswith("ROOT="):
                    line = "ROOT=%s\n" % (myroot,)
                bzf.write(line)
                line = f.readline()
            f.close()
            bzf.close()
            os.remove(envfile)

    def _remove_overlayed_ebuild(self):
        if not self.myebuild_moved:
            return

        if os.path.isfile(self.myebuild_moved):
            mydir = os.path.dirname(self.myebuild_moved)
            shutil.rmtree(mydir,True)
            mydir = os.path.dirname(mydir)
            content = os.listdir(mydir)
            while not content:
                os.rmdir(mydir)
                mydir = os.path.dirname(mydir)
                content = os.listdir(mydir)

    '''
        Internal ones
    '''

    '''
    @description: set chosen gcc profile
    @output: returns int() as exit status
    '''
    def trigger_set_gcc_profile(self, profile):
        if os.access(etpConst['systemroot']+'/usr/bin/gcc-config',os.X_OK):
            redirect = ""
            if etpUi['quiet']:
                redirect = " &> /dev/null"
            if etpConst['systemroot']:
                subprocess.call("echo '/usr/bin/gcc-config %s' | chroot %s %s" % (profile,etpConst['systemroot'],redirect,), shell = True)
            else:
                subprocess.call('/usr/bin/gcc-config %s %s' % (profile,redirect,), shell = True)
        return 0

    '''
    @description: set chosen binutils profile
    @output: returns int() as exit status
    '''
    def trigger_set_binutils_profile(self, profile):
        if os.access(etpConst['systemroot']+'/usr/bin/binutils-config',os.X_OK):
            redirect = ""
            if etpUi['quiet']:
                redirect = " &> /dev/null"
            if etpConst['systemroot']:
                subprocess.call("echo '/usr/bin/binutils-config %s' | chroot %s %s" % (profile,etpConst['systemroot'],redirect,), shell = True)
            else:
                subprocess.call('/usr/bin/binutils-config %s %s' % (profile,redirect,), shell = True)
        return 0

    '''
    @description: updates moduledb
    @output: returns int() as exit status
    '''
    def trigger_update_moduledb(self, item):
        if os.access(etpConst['systemroot']+'/usr/sbin/module-rebuild',os.X_OK):
            if os.path.isfile(etpConst['systemroot']+self.MODULEDB_DIR+'moduledb'):
                f = open(etpConst['systemroot']+self.MODULEDB_DIR+'moduledb',"r")
                moduledb = f.readlines()
                moduledb = self.Entropy.entropyTools.listToUtf8(moduledb)
                f.close()
                avail = [x for x in moduledb if x.strip() == item]
                if (not avail):
                    f = open(etpConst['systemroot']+self.MODULEDB_DIR+'moduledb',"aw")
                    f.write(item+"\n")
                    f.flush()
                    f.close()
        return 0

    '''
    @description: insert kernel object into kernel modules db
    @output: returns int() as exit status
    '''
    def trigger_run_depmod(self, name):
        if os.access('/sbin/depmod',os.X_OK):
            if not etpConst['systemroot']:
                myroot = "/"
            else:
                myroot = etpConst['systemroot']+"/"
            subprocess.call('/sbin/depmod -a -b %s -r %s &> /dev/null' % (myroot,name,), shell = True)
        return 0

    def __get_entropy_kernel_grub_line(self, kernel):
        return "title="+etpConst['systemname']+" ("+os.path.basename(kernel)+")\n"

    '''
    @description: append kernel entry to grub.conf
    @output: returns int() as exit status
    '''
    def trigger_configure_boot_grub(self, kernel,initramfs):

        if not os.path.isdir(etpConst['systemroot']+"/boot/grub"):
            os.makedirs(etpConst['systemroot']+"/boot/grub")
        if os.path.isfile(etpConst['systemroot']+"/boot/grub/grub.conf"):
            # open in append
            grub = open(etpConst['systemroot']+"/boot/grub/grub.conf","aw")
            shutil.copy2(etpConst['systemroot']+"/boot/grub/grub.conf",etpConst['systemroot']+"/boot/grub/grub.conf.old.add")
            # get boot dev
            boot_dev = self.trigger_get_grub_boot_dev()
            # test if entry has been already added
            grubtest = open(etpConst['systemroot']+"/boot/grub/grub.conf","r")
            content = grubtest.readlines()
            content = [unicode(x,'raw_unicode_escape') for x in content]
            for line in content:
                if line.find(self.__get_entropy_kernel_grub_line(kernel)) != -1:
                    grubtest.close()
                    return
                # also check if we have the same kernel listed
                if (line.find("kernel") != 1) and (line.find(os.path.basename(kernel)) != -1) and not line.strip().startswith("#"):
                    grubtest.close()
                    return
        else:
            # create
            boot_dev = "(hd0,0)"
            grub = open(etpConst['systemroot']+"/boot/grub/grub.conf","w")
            # write header - guess (hd0,0)... since it is weird having a running system without a bootloader, at least, grub.
            grub_header = '''
default=0
timeout=10
            '''
            grub.write(grub_header)
        cmdline = ' '
        if os.path.isfile("/proc/cmdline"):
            f = open("/proc/cmdline","r")
            cmdline = " "+f.readline().strip()
            params = cmdline.split()
            if "dolvm" not in params: # support new kernels >= 2.6.23
                cmdline += " dolvm "
            f.close()
        grub.write(self.__get_entropy_kernel_grub_line(kernel))
        grub.write("\troot "+boot_dev+"\n")
        grub.write("\tkernel "+kernel+cmdline+"\n")
        if initramfs:
            grub.write("\tinitrd "+initramfs+"\n")
        grub.write("\n")
        grub.flush()
        grub.close()

    def trigger_remove_boot_grub(self, kernel,initramfs):
        if os.path.isdir(etpConst['systemroot']+"/boot/grub") and os.path.isfile(etpConst['systemroot']+"/boot/grub/grub.conf"):
            shutil.copy2(etpConst['systemroot']+"/boot/grub/grub.conf",etpConst['systemroot']+"/boot/grub/grub.conf.old.remove")
            f = open(etpConst['systemroot']+"/boot/grub/grub.conf","r")
            grub_conf = f.readlines()
            f.close()
            content = [unicode(x,'raw_unicode_escape') for x in grub_conf]
            try:
                kernel, initramfs = (unicode(kernel,'raw_unicode_escape'),unicode(initramfs,'raw_unicode_escape'))
            except TypeError:
                pass
            #kernelname = os.path.basename(kernel)
            new_conf = []
            skip = False
            for line in content:

                if (line.find(self.__get_entropy_kernel_grub_line(kernel)) != -1):
                    skip = True
                    continue

                if line.strip().startswith("title"):
                    skip = False

                if not skip or line.strip().startswith("#"):
                    new_conf.append(line)

            f = open(etpConst['systemroot']+"/boot/grub/grub.conf","w")
            for line in new_conf:
                try:
                    f.write(line)
                except UnicodeEncodeError:
                    f.write(line.encode('utf-8'))
            f.flush()
            f.close()

    def trigger_get_grub_boot_dev(self):
        if etpConst['systemroot']:
            return "(hd0,0)"
        import re
        df_avail = subprocess.call("which df &> /dev/null", shell = True)
        if df_avail != 0:
            mytxt = "%s: %s! %s. %s (hd0,0)." % (
                bold(_("QA")),
                brown(_("Cannot find df")),
                brown(_("Cannot properly configure the kernel")),
                brown(_("Defaulting to")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return "(hd0,0)"
        grub_avail = subprocess.call("which grub &> /dev/null", shell = True)
        if grub_avail != 0:
            mytxt = "%s: %s! %s. %s (hd0,0)." % (
                bold(_("QA")),
                brown(_("Cannot find grub")),
                brown(_("Cannot properly configure the kernel")),
                brown(_("Defaulting to")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return "(hd0,0)"

        from entropy.tools import getstatusoutput
        gboot = getstatusoutput("df /boot")[1].split("\n")[-1].split()[0]
        if gboot.startswith("/dev/"):
            # it's ok - handle /dev/md
            if gboot.startswith("/dev/md"):
                md = os.path.basename(gboot)
                if not md.startswith("md"):
                    md = "md"+md
                f = open("/proc/mdstat","r")
                mdstat = f.readlines()
                mdstat = [x for x in mdstat if x.startswith(md)]
                f.close()
                if mdstat:
                    mdstat = mdstat[0].strip().split()
                    mddevs = []
                    for x in mdstat:
                        if x.startswith("sd"):
                            mddevs.append(x[:-3])
                    mddevs = sorted(mddevs)
                    if mddevs:
                        gboot = "/dev/"+mddevs[0]
                    else:
                        gboot = "/dev/sda1"
                else:
                    gboot = "/dev/sda1"
            # get disk
            match = re.subn("[0-9]","",gboot)
            gdisk = match[0]
            if gdisk == '':

                mytxt = "%s: %s %s %s. %s! %s (hd0,0)." % (
                    bold(_("QA")),
                    brown(_("cannot match device")),
                    brown(str(gboot)),
                    brown(_("with a grub one")), # 'cannot match device /dev/foo with a grub one'
                    brown(_("Cannot properly configure the kernel")),
                    brown(_("Defaulting to")),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
                return "(hd0,0)"
            match = re.subn("[a-z/]","",gboot)
            try:
                gpartnum = str(int(match[0])-1)
            except ValueError:
                mytxt = "%s: %s: %s. %s. %s (hd0,0)." % (
                    bold(_("QA")),
                    brown(_("grub translation not supported for")),
                    brown(str(gboot)),
                    brown(_("Cannot properly configure grub.conf")),
                    brown(_("Defaulting to")),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
                return "(hd0,0)"
            # now match with grub
            device_map = etpConst['packagestmpdir']+"/grub.map"
            if os.path.isfile(device_map):
                os.remove(device_map)
            # generate device.map
            subprocess.call('echo "quit" | grub --device-map="%s" --no-floppy --batch &> /dev/null' % (device_map,), shell = True)
            if os.path.isfile(device_map):
                f = open(device_map,"r")
                device_map_file = f.readlines()
                f.close()
                grub_dev = [x for x in device_map_file if (x.find(gdisk) != -1)]
                if grub_dev:
                    grub_disk = grub_dev[0].strip().split()[0]
                    grub_dev = grub_disk[:-1]+","+gpartnum+")"
                    return grub_dev
                else:
                    mytxt = "%s: %s. %s! %s (hd0,0)." % (
                        bold(_("QA")),
                        brown(_("cannot match grub device with a Linux one")),
                        brown(_("Cannot properly configure the kernel")),
                        brown(_("Defaulting to")),
                    )
                    self.Entropy.updateProgress(
                        mytxt,
                        importance = 0,
                        header = red("   ## ")
                    )
                    return "(hd0,0)"
            else:
                mytxt = "%s: %s. %s! %s (hd0,0)." % (
                    bold(_("QA")),
                    brown(_("cannot find generated device.map")),
                    brown(_("Cannot properly configure the kernel")),
                    brown(_("Defaulting to")),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
                return "(hd0,0)"
        else:
            mytxt = "%s: %s. %s! %s (hd0,0)." % (
                bold(_("QA")),
                brown(_("cannot run df /boot")),
                brown(_("Cannot properly configure the kernel")),
                brown(_("Defaulting to")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return "(hd0,0)"
