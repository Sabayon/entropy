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
import sys
import shutil
import time
import subprocess
from entropy.i18n import _
from entropy.const import *
from entropy.exceptions import *
from entropy.db import dbapi2, LocalRepository
from entropy.output import purple, bold, red, blue, darkgreen, darkred, brown


class RepositoryMixin:

    __repo_error_messages_cache = set()
    __repodb_cache = {}
    _memory_db_instances = {}

    def validate_repositories(self):
        self.MirrorStatus.clear()
        self.__repo_error_messages_cache.clear()
        cl_id = self.sys_settings_client_plugin_id
        self.SystemSettings[cl_id]['masking_validation']['cache'].clear()
        # valid repositories
        del self.validRepositories[:]
        for repoid in self.SystemSettings['repositories']['order']:
            # open database
            try:
                dbc = self.open_repository(repoid)
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
        self.close_all_repositories(mask_clear = False)

    def init_generic_memory_repository(self, repoid, description, package_mirrors = []):
        dbc = self.open_memory_database(dbname = repoid)
        self._memory_db_instances[repoid] = dbc

        # add to self.SystemSettings['repositories']['available']
        repodata = {
            'repoid': repoid,
            'in_memory': True,
            'description': description,
            'packages': package_mirrors,
            'dbpath': ':memory:',
        }
        self.add_repository(repodata)
        return dbc

    def close_all_repositories(self, mask_clear = True):
        for item in self.__repodb_cache:
            self.__repodb_cache[item].closeDB()
        self.__repodb_cache.clear()
        if mask_clear: self.SystemSettings.clear()

    def is_repository_connection_cached(self, repoid):
        if (repoid,etpConst['systemroot'],) in self.__repodb_cache:
            return True
        return False

    def open_repository(self, repoid):

        key = (repoid, etpConst['systemroot'],)
        if not self.__repodb_cache.has_key(key):
            dbconn = self.load_repository_database(repoid, xcache = self.xcache,
                indexing = self.indexing)
            try:
                dbconn.checkDatabaseApi()
            except (self.dbapi2.OperationalError, TypeError,):
                pass
            self.__repodb_cache[key] = dbconn
            return dbconn
        return self.__repodb_cache.get(key)

    def load_repository_database(self, repoid, xcache = True, indexing = True):

        if isinstance(repoid,basestring):
            if repoid.endswith(etpConst['packagesext']):
                xcache = False

        if repoid not in self.SystemSettings['repositories']['available']:
            t = _("bad repository id specified")
            if repoid not in self.__repo_error_messages_cache:
                self.updateProgress(
                    darkred(t),
                    importance = 2,
                    type = "warning"
                )
                self.__repo_error_messages_cache.add(repoid)
            raise RepositoryError("RepositoryError: %s" % (t,))

        dbfile = self.SystemSettings['repositories']['available'][repoid]['dbpath']+"/"+etpConst['etpdatabasefile']
        if not os.path.isfile(dbfile):
            t = _("Repository %s hasn't been downloaded yet.") % (repoid,)
            if repoid not in self.__repo_error_messages_cache:
                self.updateProgress(
                    darkred(t),
                    importance = 2,
                    type = "warning"
                )
                self.__repo_error_messages_cache.add(repoid)
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
        repo_data = self.SystemSettings['repositories']['available'][repoid]
        if (repo_data['configprotect'] == None) or \
            (repo_data['configprotectmask'] == None):
            self.setup_repository_config(repoid, conn)

        if (repoid not in etpConst['client_treeupdatescalled']) and \
            (self.entropyTools.is_user_in_entropy_group()) and \
            (not repoid.endswith(etpConst['packagesext'])):
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
            self.SystemSettings['repositories']['available'][repoid]['configprotect'] = dbconn.listConfigProtectDirectories()
        except (self.dbapi2.OperationalError, self.dbapi2.DatabaseError):
            self.SystemSettings['repositories']['available'][repoid]['configprotect'] = []
        try:
            self.SystemSettings['repositories']['available'][repoid]['configprotectmask'] = dbconn.listConfigProtectDirectories(mask = True)
        except (self.dbapi2.OperationalError, self.dbapi2.DatabaseError):
            self.SystemSettings['repositories']['available'][repoid]['configprotectmask'] = []

        self.SystemSettings['repositories']['available'][repoid]['configprotect'] = [etpConst['systemroot']+x for \
            x in self.SystemSettings['repositories']['available'][repoid]['configprotect']]
        self.SystemSettings['repositories']['available'][repoid]['configprotectmask'] = [etpConst['systemroot']+x for \
            x in self.SystemSettings['repositories']['available'][repoid]['configprotectmask']]

        sys_set_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        conf_protect = self.SystemSettings[sys_set_plg_id]['misc']['configprotect']
        conf_protect_mask = self.SystemSettings[sys_set_plg_id]['misc']['configprotectmask']

        self.SystemSettings['repositories']['available'][repoid]['configprotect'] += [etpConst['systemroot']+x for \
            x in conf_protect if etpConst['systemroot']+x not \
                in self.SystemSettings['repositories']['available'][repoid]['configprotect']]
        self.SystemSettings['repositories']['available'][repoid]['configprotectmask'] += [etpConst['systemroot']+x for \
            x in conf_protect_mask if etpConst['systemroot']+x not \
                in self.SystemSettings['repositories']['available'][repoid]['configprotectmask']]

    def get_repository_revision(self, reponame):
        fname = self.SystemSettings['repositories']['available'][reponame]['dbpath']+"/"+etpConst['etpdatabaserevisionfile']
        revision = -1
        if os.path.isfile(fname) and os.access(fname,os.R_OK):
            with open(fname,"r") as f:
                try:
                    revision = int(f.readline().strip())
                except (OSError, IOError, ValueError,):
                    pass
        return revision

    def update_repository_revision(self, reponame):
        r = self.get_repository_revision(reponame)
        self.SystemSettings['repositories']['available'][reponame]['dbrevision'] = "0"
        if r != -1:
            self.SystemSettings['repositories']['available'][reponame]['dbrevision'] = str(r)

    def get_repository_db_file_checksum(self, reponame):
        fname = self.SystemSettings['repositories']['available'][reponame]['dbpath']+"/"+etpConst['etpdatabasehashfile']
        mhash = "-1"
        if os.path.isfile(fname) and os.access(fname,os.R_OK):
            with open(fname,"r") as f:
                try:
                    mhash = f.readline().strip().split()[0]
                except (OSError, IOError, IndexError,):
                    pass
        return mhash

    def add_repository(self, repodata):
        product = self.SystemSettings['repositories']['product']
        branch = self.SystemSettings['repositories']['branch']
        # update self.SystemSettings['repositories']['available']
        try:
            self.SystemSettings['repositories']['available'][repodata['repoid']] = {}
            self.SystemSettings['repositories']['available'][repodata['repoid']]['description'] = repodata['description']
            self.SystemSettings['repositories']['available'][repodata['repoid']]['configprotect'] = None
            self.SystemSettings['repositories']['available'][repodata['repoid']]['configprotectmask'] = None
        except KeyError:
            t = _("repodata dictionary is corrupted")
            raise InvalidData("InvalidData: %s" % (t,))

        if repodata['repoid'].endswith(etpConst['packagesext']) or repodata.get('in_memory'): # dynamic repository
            try:
                # no need # self.SystemSettings['repositories']['available'][repodata['repoid']]['plain_packages'] = repodata['plain_packages'][:]
                self.SystemSettings['repositories']['available'][repodata['repoid']]['packages'] = repodata['packages'][:]
                smart_package = repodata.get('smartpackage')
                if smart_package != None: self.SystemSettings['repositories']['available'][repodata['repoid']]['smartpackage'] = smart_package
                self.SystemSettings['repositories']['available'][repodata['repoid']]['dbpath'] = repodata.get('dbpath')
                self.SystemSettings['repositories']['available'][repodata['repoid']]['pkgpath'] = repodata.get('pkgpath')
            except KeyError:
                raise InvalidData("InvalidData: repodata dictionary is corrupted")
            # put at top priority, shift others
            self.SystemSettings['repositories']['order'].insert(0, repodata['repoid'])
        else:
            # XXX it's boring to keep this in sync with entropyConstants stuff, solutions?
            self.SystemSettings['repositories']['available'][repodata['repoid']]['plain_packages'] = repodata['plain_packages'][:]
            self.SystemSettings['repositories']['available'][repodata['repoid']]['packages'] = [x+"/"+product for x in repodata['plain_packages']]
            self.SystemSettings['repositories']['available'][repodata['repoid']]['plain_database'] = repodata['plain_database']
            self.SystemSettings['repositories']['available'][repodata['repoid']]['database'] = repodata['plain_database'] + \
                "/" + product + "/database/" + etpConst['currentarch'] + "/" + branch
            if not repodata['dbcformat'] in etpConst['etpdatabasesupportedcformats']:
                repodata['dbcformat'] = etpConst['etpdatabasesupportedcformats'][0]
            self.SystemSettings['repositories']['available'][repodata['repoid']]['dbcformat'] = repodata['dbcformat']
            self.SystemSettings['repositories']['available'][repodata['repoid']]['dbpath'] = etpConst['etpdatabaseclientdir'] + \
                "/" + repodata['repoid'] + "/" + product + "/" + etpConst['currentarch']  + "/" + branch
            # set dbrevision
            myrev = self.get_repository_revision(repodata['repoid'])
            if myrev == -1:
                myrev = 0
            self.SystemSettings['repositories']['available'][repodata['repoid']]['dbrevision'] = str(myrev)
            if repodata.has_key("position"):
                self.SystemSettings['repositories']['order'].insert(
                    repodata['position'], repodata['repoid'])
            else:
                self.SystemSettings['repositories']['order'].append(
                    repodata['repoid'])
            if not repodata.has_key("service_port"):
                repodata['service_port'] = int(etpConst['socket_service']['port'])
            if not repodata.has_key("ssl_service_port"):
                repodata['ssl_service_port'] = int(etpConst['socket_service']['ssl_port'])
            self.SystemSettings['repositories']['available'][repodata['repoid']]['service_port'] = repodata['service_port']
            self.SystemSettings['repositories']['available'][repodata['repoid']]['ssl_service_port'] = repodata['ssl_service_port']
            self.repository_move_clear_cache(repodata['repoid'])
            # save new self.SystemSettings['repositories']['available'] to file
            self.entropyTools.save_repository_settings(repodata)
            self.SystemSettings.clear()
            self.close_all_repositories()
        self.validate_repositories()

    def remove_repository(self, repoid, disable = False):

        # ensure that all dbs are closed
        self.close_all_repositories()

        done = False
        if self.SystemSettings['repositories']['available'].has_key(repoid):
            del self.SystemSettings['repositories']['available'][repoid]
            done = True

        if self.SystemSettings['repositories']['excluded'].has_key(repoid):
            del self.SystemSettings['repositories']['excluded'][repoid]
            done = True

        if done:

            if repoid in self.SystemSettings['repositories']['order']:
                self.SystemSettings['repositories']['order'].remove(repoid)

            self.repository_move_clear_cache(repoid)
            # save new self.SystemSettings['repositories']['available'] to file
            repodata = {}
            repodata['repoid'] = repoid
            if disable:
                self.entropyTools.save_repository_settings(repodata, disable = True)
            else:
                self.entropyTools.save_repository_settings(repodata, remove = True)
            self.SystemSettings.clear()

        # reset db cache
        self.close_all_repositories()
        self.validate_repositories()

    def shift_repository(self, repoid, toidx):
        # update self.SystemSettings['repositories']['order']
        self.SystemSettings['repositories']['order'].remove(repoid)
        self.SystemSettings['repositories']['order'].insert(toidx, repoid)
        self.entropyTools.write_ordered_repositories_entries(
            self.SystemSettings['repositories']['order'])
        self.SystemSettings.clear()
        self.close_all_repositories()
        self.repository_move_clear_cache(repoid)
        self.validate_repositories()

    def enable_repository(self, repoid):
        self.repository_move_clear_cache(repoid)
        # save new self.SystemSettings['repositories']['available'] to file
        repodata = {}
        repodata['repoid'] = repoid
        self.entropyTools.save_repository_settings(repodata, enable = True)
        self.SystemSettings.clear()
        self.close_all_repositories()
        self.validate_repositories()

    def disable_repository(self, repoid):
        # update self.SystemSettings['repositories']['available']
        done = False
        try:
            del self.SystemSettings['repositories']['available'][repoid]
            done = True
        except:
            pass

        if done:
            try:
                self.SystemSettings['repositories']['order'].remove(repoid)
            except (IndexError,):
                pass
            # it's not vital to reset
            # self.SystemSettings['repositories']['order'] counters

            self.repository_move_clear_cache(repoid)
            # save new self.SystemSettings['repositories']['available'] to file
            repodata = {}
            repodata['repoid'] = repoid
            self.entropyTools.save_repository_settings(repodata, disable = True)
            self.SystemSettings.clear()

        self.close_all_repositories()
        self.validate_repositories()

    def get_repository_settings(self, repoid):
        try:
            repodata = self.SystemSettings['repositories']['available'][repoid].copy()
        except KeyError:
            if not self.SystemSettings['repositories']['excluded'].has_key(repoid):
                raise
            repodata = self.SystemSettings['repositories']['excluded'][repoid].copy()
        return repodata

    # every tbz2 file that would be installed must pass from here
    def add_tbz2_to_repos(self, tbz2file):
        atoms_contained = []
        basefile = os.path.basename(tbz2file)
        cut_idx = -1*(len(etpConst['packagesext']))
        db_dir = etpConst['entropyunpackdir']+"/"+basefile[:cut_idx]
        if os.path.isdir(db_dir):
            shutil.rmtree(db_dir)
        os.makedirs(db_dir)
        dbfile = self.entropyTools.extract_edb(tbz2file,
            dbpath = db_dir+"/packages.db")
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

        mydbconn = self.open_generic_database(dbfile)
        # read all idpackages
        try:
            myidpackages = mydbconn.listAllIdpackages() # all branches admitted from external files
        except (AttributeError, self.dbapi2.DatabaseError, \
            self.dbapi2.IntegrityError, self.dbapi2.OperationalError,):
                return -2,atoms_contained
        if len(myidpackages) > 1:
            repodata[basefile]['smartpackage'] = True
        for myidpackage in myidpackages:
            compiled_arch = mydbconn.retrieveDownloadURL(myidpackage)
            if compiled_arch.find("/"+etpSys['arch']+"/") == -1:
                return -3,atoms_contained
            atoms_contained.append((int(myidpackage),basefile))

        self.add_repository(repodata)
        self.validate_repositories()
        if basefile not in self.validRepositories:
            self.remove_repository(basefile)
            return -4,atoms_contained
        mydbconn.closeDB()
        del mydbconn
        return 0,atoms_contained

    def reopen_client_repository(self):
        self.clientDbconn.closeDB()
        self.open_client_repository()
        # make sure settings are in sync
        self.SystemSettings.clear()

    def open_client_repository(self):

        def load_db_from_ram():
            self.safe_mode = etpConst['safemodeerrors']['clientdb']
            mytxt = "%s, %s" % (_("System database not found or corrupted"),
                _("running in safe mode using empty database from RAM"),)
            self.updateProgress(
                darkred(mytxt),
                importance = 1,
                type = "warning",
                header = bold("!!!"),
            )
            conn = self.open_memory_database(dbname = etpConst['clientdbid'])
            return conn

        db_dir = os.path.dirname(etpConst['etpdatabaseclientfilepath'])
        if not os.path.isdir(db_dir): os.makedirs(db_dir)

        db_path = etpConst['etpdatabaseclientfilepath']
        if (not self.noclientdb) and (not os.path.isfile(db_path)):
            conn = load_db_from_ram()
            self.entropyTools.print_traceback(f = self.clientLog)
        else:
            conn = LocalRepository(readOnly = False, dbFile = db_path,
                clientDatabase = True, dbname = etpConst['clientdbid'],
                xcache = self.xcache, indexing = self.indexing,
                OutputInterface = self, ServiceInterface = self
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
                    self.entropyTools.print_traceback(f = self.clientLog)
                    conn = load_db_from_ram()

        self.clientDbconn = conn
        return self.clientDbconn

    def client_repository_sanity_check(self):
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
                self.entropyTools.print_traceback()
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

    def open_generic_database(self, dbfile, dbname = None, xcache = None,
            readOnly = False, indexing_override = None, skipChecks = False):
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

    def open_memory_database(self, dbname = None):
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
            skipChecks = True,
            ServiceInterface = self
        )
        dbc.initializeDatabase()
        return dbc

    def backup_database(self, dbpath, backup_dir = None, silent = False, compress_level = 9):

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
                self.entropyTools.print_traceback()
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

    def restore_database(self, backup_path, db_destination, silent = False):

        bytes_required = 1024000*300
        db_dir = os.path.dirname(db_destination)
        if not (os.access(db_dir,os.W_OK) and os.path.isdir(db_dir) and \
            os.path.isfile(backup_path) and os.access(backup_path,os.R_OK) and \
            self.entropyTools.check_required_space(db_dir, bytes_required)):

                if not silent:
                    mytxt = "%s: %s, %s" % (darkred(_("Cannot restore selected backup")),
                        blue(backup_path),darkred(_("permission denied")),)
                    self.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "error",
                        header = red(" @@ ")
                    )
                return False, mytxt

        if not silent:
            mytxt = "%s: %s => %s ..." % (darkgreen(_("Restoring backed up database")),
                blue(os.path.basename(backup_path)),blue(db_destination),)
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
                self.entropyTools.print_traceback()
            return False, _("Unable to unpack")

        if not silent:
            mytxt = "%s: %s" % (darkgreen(_("Database restored successfully")),
                blue(db_destination),)
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

    """
        XXX deprecated XXX
    """

    def backupDatabase(self, *args, **kwargs):
        import warnings
        warnings.warn("deprecated, use backup_database instead")
        return self.backup_database(*args, **kwargs)

    def restoreDatabase(self, *args, **kwargs):
        import warnings
        warnings.warn("deprecated, use restore_database instead")
        return self.restore_database(*args, **kwargs)

    def openGenericDatabase(self, *args, **kwargs):
        import warnings
        warnings.warn("deprecated, use open_generic_database instead")
        return self.open_generic_database(*args, **kwargs)

    def openMemoryDatabase(self, *args, **kwargs):
        import warnings
        warnings.warn("deprecated, use open_memory_database instead")
        return self.open_memory_database(*args, **kwargs)

    def clientDatabaseSanityCheck(self):
        import warnings
        warnings.warn("deprecated, use client_repository_sanity_check instead")
        return self.client_repository_sanity_check()

    def openClientDatabase(self):
        import warnings
        warnings.warn("deprecated, use open_client_repository instead")
        return self.open_client_repository()

    def reopenClientDbconn(self):
        import warnings
        warnings.warn("deprecated, use reopen_client_repository instead")
        return self.reopen_client_repository()

    def openRepositoryDatabase(self, repoid):
        import warnings
        warnings.warn("deprecated, use open_repository instead")
        return self.open_repository(repoid)

    def closeAllRepositoryDatabases(self, mask_clear = True):
        import warnings
        warnings.warn("deprecated, use close_all_repositories instead")
        return self.close_all_repositories(mask_clear = mask_clear)

    def addRepository(self, repodata):
        import warnings
        warnings.warn("deprecated, use add_repository instead")
        return self.add_repository(repodata)

    def removeRepository(self, repoid, disable = False):
        import warnings
        warnings.warn("deprecated, use remove_repository instead")
        return self.remove_repository(repoid, disable = disable)

    def shiftRepository(self, repoid, toidx):
        import warnings
        warnings.warn("deprecated, use shift_repository instead")
        return self.shift_repository(repoid, toidx)

    def enableRepository(self, repoid):
        import warnings
        warnings.warn("deprecated, use enable_repository instead")
        return self.enable_repository(repoid)

    def disableRepository(self, repoid):
        import warnings
        warnings.warn("deprecated, use disable_repository instead")
        return self.disable_repository(repoid)


class MiscMixin:

    def reload_constants(self):
        initconfig_entropy_constants(etpSys['rootdir'])
        self.SystemSettings.clear()

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
        const_setup_entropy_pid(just_read = True)
        locked = self.entropyTools.application_lock_check(option = None, gentle = True, silent = True)
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

    def backup_constant(self, constant_name):
        if etpConst.has_key(constant_name):
            myinst = etpConst[constant_name]
            if type(etpConst[constant_name]) in (list,tuple):
                myinst = etpConst[constant_name][:]
            elif type(etpConst[constant_name]) in (dict,set):
                myinst = etpConst[constant_name].copy()
            else:
                myinst = etpConst[constant_name]
            etpConst['backed_up'].update({constant_name: myinst})
        else:
            t = _("Nothing to backup in etpConst with %s key") % (constant_name,)
            raise InvalidData("InvalidData: %s" % (t,))

    def set_priority(self, low = 0):
        return const_set_nice_level(low)

    def reload_repositories_config(self, repositories = None):
        if repositories == None:
            repositories = self.validRepositories
        for repoid in repositories:
            dbconn = self.open_repository(repoid)
            self.setup_repository_config(repoid, dbconn)

    def switch_chroot(self, chroot = ""):
        # clean caches
        self.purge_cache()
        self.close_all_repositories()
        if chroot.endswith("/"):
            chroot = chroot[:-1]
        etpSys['rootdir'] = chroot
        self.reload_constants()
        self.validate_repositories()
        self.reopen_client_repository()
        # keep them closed, since SystemSettings.clear() is called
        # above on reopen_client_repository()
        self.close_all_repositories()
        if chroot:
            try:
                self.clientDbconn.resetTreeupdatesDigests()
            except:
                pass
        # I don't think it's safe to keep them open
        # isn't it?
        self.closeAllSecurity()
        self.closeAllQA()

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
        set_match, rc = self.package_set_match(set_name)
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

        set_match, rc = self.package_set_match(set_name)
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

    def is_installed_idpackage_in_system_mask(self, idpackage):
        client_plugin_id = etpConst['system_settings_plugins_ids']['client_plugin']
        mask_installed = self.SystemSettings[client_plugin_id]['system_mask']['repos_installed']
        if idpackage in mask_installed:
            return True
        return False

    def get_branch_from_download_relative_uri(self, db_download_uri):
        return db_download_uri.split("/")[2]

    def unused_packages_test(self, dbconn = None):
        if dbconn == None: dbconn = self.clientDbconn
        return [x for x in dbconn.retrieveUnusedIdpackages() if self.validate_package_removal(x)]

    def get_licenses_to_accept(self, install_queue):
        if not install_queue:
            return {}
        licenses = {}
        for match in install_queue:
            repoid = match[1]
            dbconn = self.open_repository(repoid)
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
        dbconn = self.open_repository(repoid)
        text = dbconn.retrieveLicenseText(license_name)
        tempfile = self.entropyTools.get_random_temp_file()
        f = open(tempfile,"w")
        f.write(text)
        f.flush()
        f.close()
        return tempfile

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

        ldpaths = set(self.entropyTools.collect_linker_paths())
        ldpaths |= self.entropyTools.collect_paths()
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
                    mymatch = self.atom_match(key, matchSlot = slot)
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

    def set_branch(self, branch):
        """
        Set new Entropy branch. This is NOT thread-safe.
        Please note that if you call this method all your
        repository instance references will become invalid.
        This is caused by close_all_repositories and SystemSettings
        clear methods.
        Once you changed branch, the repository databases won't be
        available until you fetch them (through Repositories class)

        @param branch -- new branch
        @type branch basestring
        @return None
        """
        self.Cacher.sync(wait = True)
        self.Cacher.stop()
        self.purge_cache(showProgress = False)
        self.close_all_repositories()
        # etpConst should be readonly but we override the rule here
        # this is also useful when no config file or parameter into it exists
        etpConst['branch'] = branch
        self.entropyTools.write_new_branch(branch)
        self.SystemSettings.clear()

        # reset treeupdatesactions
        self.reopen_client_repository()
        self.clientDbconn.resetTreeupdatesDigests()
        self.close_all_repositories()
        if self.xcache:
            self.Cacher.start()

    def get_meant_packages(self, search_term, from_installed = False, valid_repos = []):

        pkg_data = []
        atom_srch = False
        if "/" in search_term: atom_srch = True

        if not valid_repos: valid_repos = self.validRepositories
        if from_installed: valid_repos = [1]
        for repo in valid_repos:
            if isinstance(repo,basestring):
                dbconn = self.open_repository(repo)
            elif isinstance(repo,LocalRepository):
                dbconn = repo
            elif hasattr(self,'clientDbconn'):
                dbconn = self.clientDbconn
            else:
                continue
            pkg_data.extend([(x,repo,) for x in dbconn.searchSimilarPackages(search_term, atom = atom_srch)])

        return pkg_data

    def list_repo_categories(self):
        categories = set()
        for repo in self.validRepositories:
            dbconn = self.open_repository(repo)
            catsdata = dbconn.listAllCategories()
            categories.update(set([x[1] for x in catsdata]))
        return categories

    def list_repo_packages_in_category(self, category):
        pkg_matches = []
        for repo in self.validRepositories:
            dbconn = self.open_repository(repo)
            branch = self.SystemSettings['repositories']['branch']
            catsdata = dbconn.searchPackagesByCategory(category, branch = branch)
            pkg_matches.extend([(x[1],repo,) for x in catsdata if (x[1],repo,) not in pkg_matches])
        return pkg_matches

    def get_category_description_data(self, category):

        data = {}
        for repo in self.validRepositories:
            try:
                dbconn = self.open_repository(repo)
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

    def inject_entropy_database_into_package(self, package_filename, data, treeupdates_actions = None):
        dbpath = self.get_tmp_dbpath()
        dbconn = self.open_generic_database(dbpath)
        dbconn.initializeDatabase()
        dbconn.addPackage(data, revision = data['revision'])
        if treeupdates_actions != None:
            dbconn.bumpTreeUpdatesActions(treeupdates_actions)
        dbconn.commitChanges()
        dbconn.closeDB()
        self.entropyTools.aggregate_edb(tbz2file = package_filename, dbfile = dbpath)
        return dbpath

    def get_tmp_dbpath(self):
        dbpath = etpConst['packagestmpdir']+"/"+str(self.entropyTools.get_random_number())
        while os.path.isfile(dbpath):
            dbpath = etpConst['packagestmpdir']+"/"+str(self.entropyTools.get_random_number())
        return dbpath

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

    """
        XXX deprecated XXX
    """

    def switchChroot(self, *args, **kwargs):
        import warnings
        warnings.warn("deprecated, use switch_chroot instead")
        return self.switch_chroot(*args, **kwargs)


class MatchMixin:

    def get_package_action(self, match):
        """
            @input: matched atom (idpackage,repoid)
            @output:
                    upgrade: int(2)
                    install: int(1)
                    reinstall: int(0)
                    downgrade: int(-1)
        """
        dbconn = self.open_repository(match[1])
        pkgkey, pkgslot = dbconn.retrieveKeySlot(match[0])
        results = self.clientDbconn.searchKeySlot(pkgkey, pkgslot)
        if not results: return 1

        installed_idpackage = results[0][0]
        pkgver, pkgtag, pkgrev = dbconn.getVersioningData(match[0])
        installedVer, installedTag, installedRev = self.clientDbconn.getVersioningData(installed_idpackage)
        pkgcmp = self.entropyTools.entropy_compare_versions((pkgver,pkgtag,pkgrev),(installedVer,installedTag,installedRev))
        if pkgcmp == 0:
            return 0
        elif pkgcmp > 0:
            return 2
        return -1

    def get_masked_package_reason(self, match):
        idpackage, repoid = match
        dbconn = self.open_repository(repoid)
        idpackage, idreason = dbconn.idpackageValidator(idpackage)
        masked = False
        if idpackage == -1: masked = True
        return masked, idreason, self.SystemSettings['pkg_masking_reasons'].get(idreason)

    def get_match_conflicts(self, match):
        m_id, m_repo = match
        dbconn = self.open_repository(m_repo)
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
        dbconn = self.open_repository(m_repo)
        idpackage, idreason = dbconn.idpackageValidator(m_id, live = live_check)
        if idpackage != -1:
            return False
        return True

    def is_match_masked_by_user(self, match, live_check = True):
        # (query_status,masked?,)
        m_id, m_repo = match
        if m_repo not in self.validRepositories: return False
        dbconn = self.open_repository(m_repo)
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
        dbconn = self.open_repository(m_repo)
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
        if done:
            self.SystemSettings.clear()

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

        cl_id = self.sys_settings_client_plugin_id
        self.SystemSettings[cl_id]['masking_validation']['cache'].clear()
        return done

    def unmask_match_by_atom(self, match, dry_run = False):
        m_id, m_repo = match
        dbconn = self.open_repository(m_repo)
        atom = dbconn.retrieveAtom(m_id)
        return self.unmask_match_generic(match, atom, dry_run = dry_run)

    def unmask_match_by_keyslot(self, match, dry_run = False):
        m_id, m_repo = match
        dbconn = self.open_repository(m_repo)
        keyslot = "%s:%s" % dbconn.retrieveKeySlot(m_id)
        return self.unmask_match_generic(match, keyslot, dry_run = dry_run)

    def mask_match_by_atom(self, match, dry_run = False):
        m_id, m_repo = match
        dbconn = self.open_repository(m_repo)
        atom = dbconn.retrieveAtom(m_id)
        return self.mask_match_generic(match, atom, dry_run = dry_run)

    def mask_match_by_keyslot(self, match, dry_run = False):
        m_id, m_repo = match
        dbconn = self.open_repository(m_repo)
        keyslot = "%s:%s" % dbconn.retrieveKeySlot(m_id)
        return self.mask_match_generic(match, keyslot, dry_run = dry_run)

    def unmask_match_generic(self, match, keyword, dry_run = False):
        self.clear_match_mask(match, dry_run)
        m_file = self.SystemSettings.get_setting_files_data()['unmask']
        return self._mask_unmask_match_generic(keyword, m_file, dry_run = dry_run)

    def mask_match_generic(self, match, keyword, dry_run = False):
        self.clear_match_mask(match, dry_run)
        m_file = self.SystemSettings.get_setting_files_data()['mask']
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
        setting_data = self.SystemSettings.get_setting_files_data()
        masking_list = [setting_data['mask'],setting_data['unmask']]
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
                mymatch = self.atom_match(line, packagesFilter = False)
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
