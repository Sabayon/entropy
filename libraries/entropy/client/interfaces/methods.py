# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Miscellaneous functions Interface}.

"""
import os
import stat
import fcntl
import errno
import sys
import shutil
import time
import subprocess
import tempfile
from entropy.i18n import _
from entropy.const import *
from entropy.exceptions import *
from entropy.db import dbapi2, EntropyRepository, EntropyRepository
from entropy.output import purple, bold, red, blue, darkgreen, darkred, brown


class RepositoryMixin:

    __repo_error_messages_cache = set()
    __repodb_cache = {}
    _memory_db_instances = {}

    def validate_repositories(self, quiet = False):
        self.MirrorStatus.clear()
        self.__repo_error_messages_cache.clear()

        # clear live masking validation cache, if exists
        cl_id = self.sys_settings_client_plugin_id
        client_metadata = self.SystemSettings.get(cl_id, {})
        if "masking_validation" in client_metadata:
            client_metadata['masking_validation']['cache'].clear()

        # valid repositories
        del self.validRepositories[:]
        for repoid in self.SystemSettings['repositories']['order']:
            # open database
            try:

                dbc = self.open_repository(repoid)
                dbc.listConfigProtectEntries()
                dbc.validateDatabase()
                self.validRepositories.append(repoid)

            except RepositoryError:

                if quiet:
                    continue

                t = _("Repository") + " " + repoid + " " + \
                    _("is not available") + ". " + _("Cannot validate")
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
            except (self.dbapi2.OperationalError,
                self.dbapi2.DatabaseError,SystemDatabaseError,):

                if quiet:
                    continue

                t = _("Repository") + " " + repoid + " " + \
                    _("is corrupted") + ". " + _("Cannot validate")
                self.updateProgress(
                                    darkred(t),
                                    importance = 1,
                                    type = "warning"
                                   )
                continue

        # to avoid having zillions of open files when loading a lot of EquoInterfaces
        self.close_all_repositories(mask_clear = False)

    def __get_repository_cache_key(self, repoid):
        return (repoid, etpConst['systemroot'],)

    def init_generic_memory_repository(self, repoid, description, package_mirrors = []):
        dbc = self.open_memory_database(dbname = repoid)
        repo_key = self.__get_repository_cache_key(repoid)
        self._memory_db_instances[repo_key] = dbc

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
            # in-memory repositories cannot be closed
            # otherwise everything will be lost, to
            # effectively close these repos you
            # must call remove_repository method
            if item in self._memory_db_instances:
                continue
            self.__repodb_cache[item].closeDB()
        self.__repodb_cache.clear()

        # disable hooks during SystemSettings cleanup
        # otherwise it makes entropy.client.interfaces.repository crazy
        old_value = self._can_run_sys_set_hooks
        self._can_run_sys_set_hooks = False
        if mask_clear:
            self.SystemSettings.clear()
        self._can_run_sys_set_hooks = old_value


    def is_repository_connection_cached(self, repoid):
        if (repoid,etpConst['systemroot'],) in self.__repodb_cache:
            return True
        return False

    def open_repository(self, repoid):

        key = self.__get_repository_cache_key(repoid)
        if key not in self.__repodb_cache:
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

        repo_data = self.SystemSettings['repositories']['available']
        if repoid not in repo_data:
            t = _("bad repository id specified")
            if repoid not in self.__repo_error_messages_cache:
                self.updateProgress(
                    darkred(t),
                    importance = 2,
                    type = "warning"
                )
                self.__repo_error_messages_cache.add(repoid)
            raise RepositoryError("RepositoryError: %s" % (t,))

        if repo_data[repoid].get('in_memory'):
            repo_key = self.__get_repository_cache_key(repoid)
            conn = self._memory_db_instances.get(repo_key)
        else:
            dbfile = repo_data[repoid]['dbpath']+"/"+etpConst['etpdatabasefile']
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

            conn = EntropyRepository(
                readOnly = True,
                dbFile = dbfile,
                clientDatabase = True,
                dbname = etpConst['dbnamerepoprefix']+repoid,
                xcache = xcache,
                indexing = indexing,
                OutputInterface = self
            )

        if (repoid not in etpConst['client_treeupdatescalled']) and \
            (self.entropyTools.is_root()) and \
            (not repoid.endswith(etpConst['packagesext'])):
                # only as root due to Portage
                try:
                    updated = self.repository_packages_spm_sync(repoid, conn)
                except (self.dbapi2.OperationalError, self.dbapi2.DatabaseError):
                    updated = False
                if updated:
                    self.clear_dump_cache(etpCache['world_update'])
                    self.clear_dump_cache(etpCache['critical_update'])
                    self.clear_dump_cache(etpCache['world'])
                    self.clear_dump_cache(etpCache['install'])
                    self.clear_dump_cache(etpCache['remove'])
        return conn

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
        except KeyError:
            t = _("repodata dictionary is corrupted")
            raise InvalidData("InvalidData: %s" % (t,))

        if repodata['repoid'].endswith(etpConst['packagesext']) or repodata.get('in_memory'): # dynamic repository
            try:
                # no need # self.SystemSettings['repositories']['available'][repodata['repoid']]['plain_packages'] = repodata['plain_packages'][:]
                self.SystemSettings['repositories']['available'][repodata['repoid']]['packages'] = repodata['packages'][:]
                smart_package = repodata.get('smartpackage')
                if smart_package != None:
                    self.SystemSettings['repositories']['available'][repodata['repoid']]['smartpackage'] = smart_package
            except KeyError:
                raise InvalidData("InvalidData: repodata dictionary is corrupted")
            self.SystemSettings['repositories']['available'][repodata['repoid']]['dbpath'] = repodata.get('dbpath')
            self.SystemSettings['repositories']['available'][repodata['repoid']]['pkgpath'] = repodata.get('pkgpath')
            self.SystemSettings['repositories']['available'][repodata['repoid']]['in_memory'] = repodata.get('in_memory')
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
            if "position" in repodata:
                self.SystemSettings['repositories']['order'].insert(
                    repodata['position'], repodata['repoid'])
            else:
                self.SystemSettings['repositories']['order'].append(
                    repodata['repoid'])
            if "service_port" not in repodata:
                repodata['service_port'] = int(etpConst['socket_service']['port'])
            if "ssl_service_port" not in repodata:
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

        done = False
        if repoid in self.SystemSettings['repositories']['available']:
            del self.SystemSettings['repositories']['available'][repoid]
            done = True

        if repoid in self.SystemSettings['repositories']['excluded']:
            del self.SystemSettings['repositories']['excluded'][repoid]
            done = True

        # also early remove from validRepositories to avoid
        # issues when reloading SystemSettings which is bound to Entropy Client
        # SystemSettings plugin, which triggers calculate_world_updates, which
        # triggers all_repositories_checksum, which triggers open_repository,
        # which triggers load_repository_database, which triggers an unwanted
        # output message => "bad repository id specified"
        if repoid in self.validRepositories:
            self.validRepositories.remove(repoid)

        # ensure that all dbs are closed
        self.close_all_repositories()

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

        repo_mem_key = self.__get_repository_cache_key(repoid)
        mem_inst = self._memory_db_instances.pop(repo_mem_key, None)
        if isinstance(mem_inst, EntropyRepository):
            mem_inst.closeDB()

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
            if repoid not in self.SystemSettings['repositories']['excluded']:
                raise
            repodata = self.SystemSettings['repositories']['excluded'][repoid].copy()
        return repodata

    # every tbz2 file that would be installed must pass from here
    def add_package_to_repos(self, pkg_file):
        atoms_contained = []
        basefile = os.path.basename(pkg_file)
        db_dir = tempfile.mkdtemp()
        dbfile = self.entropyTools.extract_edb(pkg_file,
            dbpath = db_dir+"/packages.db")
        if dbfile == None:
            return -1, atoms_contained
        # add dbfile
        repodata = {}
        repodata['repoid'] = basefile
        repodata['description'] = "Dynamic database from " + basefile
        repodata['packages'] = []
        repodata['dbpath'] = os.path.dirname(dbfile)
        repodata['pkgpath'] = os.path.realpath(pkg_file) # extra info added
        repodata['smartpackage'] = False # extra info added

        mydbconn = self.open_generic_database(dbfile)
        # read all idpackages
        try:
            myidpackages = mydbconn.listAllIdpackages() # all branches admitted from external files
        except (AttributeError, self.dbapi2.DatabaseError, \
            self.dbapi2.IntegrityError, self.dbapi2.OperationalError,):
                return -2, atoms_contained
        if len(myidpackages) > 1:
            repodata[basefile]['smartpackage'] = True
        for myidpackage in myidpackages:
            compiled_arch = mydbconn.retrieveDownloadURL(myidpackage)
            if compiled_arch.find("/"+etpSys['arch']+"/") == -1:
                return -3, atoms_contained
            atoms_contained.append((int(myidpackage), basefile))

        self.add_repository(repodata)
        self.validate_repositories()
        if basefile not in self.validRepositories:
            self.remove_repository(basefile)
            return -4, atoms_contained
        mydbconn.closeDB()
        del mydbconn
        return 0, atoms_contained

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
            try:
                conn = EntropyRepository(readOnly = False, dbFile = db_path,
                    clientDatabase = True, dbname = etpConst['clientdbid'],
                    xcache = self.xcache, indexing = self.indexing,
                    OutputInterface = self
                )
            except (self.dbapi2.DatabaseError,):
                self.entropyTools.print_traceback(f = self.clientLog)
                conn = load_db_from_ram()
            else:
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
            except Exception as e:
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
        return EntropyRepository(
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
        dbc = EntropyRepository(
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

    def backup_database(self, dbpath, backup_dir = None, silent = False, compress_level = 9):

        if compress_level not in list(range(1,10)):
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

    def run_repositories_post_branch_switch_hooks(self, old_branch, new_branch):
        """
        This method is called whenever branch is successfully switched by user.
        Branch is switched when user wants to upgrade the OS to a new
        major release.
        Any repository can be shipped with a sh script which if available,
        handles system configuration to ease the migration.

        @param old_branch: previously set branch
        @type old_branch: string
        @param new_branch: newly set branch
        @type new_branch: string
        @return: tuple composed by (1) list of repositories whose script has
        been run and (2) bool describing if scripts exited with error
        @rtype: tuple(set, bool)
        """

        const_debug_write(__name__,
            "run_repositories_post_branch_switch_hooks: called")

        client_dbconn = self.clientDbconn
        hooks_ran = set()
        if client_dbconn is None:
            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: clientdb not avail")
            return hooks_ran, True

        errors = False
        repo_data = self.SystemSettings['repositories']['available']
        repo_data_excl = self.SystemSettings['repositories']['available']
        all_repos = sorted(set(list(repo_data.keys()) + list(repo_data_excl.keys())))

        for repoid in all_repos:

            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: %s" % (
                    repoid,)
            )

            mydata = repo_data.get(repoid)
            if mydata is None:
                mydata = repo_data_excl.get(repoid)

            if mydata is None:
                const_debug_write(__name__,
                    "run_repositories_post_branch_switch_hooks: skipping %s" % (
                        repoid,)
                )
                continue

            branch_mig_script = mydata['post_branch_hop_script']
            branch_mig_md5sum = '0'
            if os.access(branch_mig_script, os.R_OK) and \
                os.path.isfile(branch_mig_script):
                branch_mig_md5sum = self.entropyTools.md5sum(branch_mig_script)

            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: script md5: %s" % (
                    branch_mig_md5sum,)
            )

            # check if it is needed to run post branch migration script
            status_md5sums = client_dbconn.isBranchMigrationAvailable(
                repoid, old_branch, new_branch)
            if status_md5sums:
                if branch_mig_md5sum == status_md5sums[0]: # its stored md5
                    const_debug_write(__name__,
                        "run_repositories_post_branch_switch_hooks: skip %s" % (
                            branch_mig_script,)
                    )
                    continue # skipping, already ran the same script

            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: preparing run: %s" % (
                    branch_mig_script,)
                )

            if branch_mig_md5sum != '0':
                args = ["/bin/sh", branch_mig_script, repoid, 
                    etpConst['systemroot'] + "/", old_branch, new_branch]
                const_debug_write(__name__,
                    "run_repositories_post_branch_switch_hooks: run: %s" % (
                        args,)
                )
                proc = subprocess.Popen(args, stdin = sys.stdin,
                    stdout = sys.stdout, stderr = sys.stderr)
                # it is possible to ignore errors because
                # if it's a critical thing, upstream dev just have to fix
                # the script and will be automagically re-run
                br_rc = proc.wait()
                const_debug_write(__name__,
                    "run_repositories_post_branch_switch_hooks: rc: %s" % (
                        br_rc,)
                )
                if br_rc != 0:
                    errors = True

            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: done")

            # update metadata inside database
            # overriding post branch upgrade md5sum is INTENDED
            # here but NOT on the other function
            # this will cause the post-branch upgrade migration
            # script to be re-run also.
            client_dbconn.insertBranchMigration(repoid, old_branch, new_branch,
                branch_mig_md5sum, '0')

            const_debug_write(__name__,
                "run_repositories_post_branch_switch_hooks: db data: %s" % (
                    (repoid, old_branch, new_branch, branch_mig_md5sum, '0',),)
            )

            hooks_ran.add(repoid)

        return hooks_ran, errors

    def run_repository_post_branch_upgrade_hooks(self, pretend = False):
        """
        This method is called whenever branch is successfully switched by user
        and all the updates have been installed (also look at:
        run_repositories_post_branch_switch_hooks()).
        Any repository can be shipped with a sh script which if available,
        handles system configuration to ease the migration.

        @param pretend: do not run hooks but just return list of repos whose
            scripts should be run
        @type pretend: bool
        @return: tuple of length 2 composed by list of repositories whose
            scripts have been run and errors boolean)
        @rtype: tuple
        """

        const_debug_write(__name__,
            "run_repository_post_branch_upgrade_hooks: called"
        )

        client_dbconn = self.clientDbconn
        hooks_ran = set()
        if client_dbconn is None:
            return hooks_ran, True

        repo_data = self.SystemSettings['repositories']['available']
        branch = self.SystemSettings['repositories']['branch']
        errors = False

        for repoid in self.validRepositories:

            const_debug_write(__name__,
                "run_repository_post_branch_upgrade_hooks: repoid: %s" % (
                    (repoid,),
                )
            )

            mydata = repo_data.get(repoid)
            if mydata is None:
                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: repo data N/A")
                continue

            # check if branch upgrade script exists
            branch_upg_script = mydata['post_branch_upgrade_script']
            branch_upg_md5sum = '0'
            if os.access(branch_upg_script, os.R_OK) and \
                os.path.isfile(branch_upg_script):
                branch_upg_md5sum = self.entropyTools.md5sum(branch_upg_script)

            if branch_upg_md5sum == '0':
                # script not found, skip completely
                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                        repoid, "branch upgrade script not avail",)
                )
                continue

            const_debug_write(__name__,
                "run_repository_post_branch_upgrade_hooks: script md5: %s" % (
                    branch_upg_md5sum,)
            )

            upgrade_data = client_dbconn.retrieveBranchMigration(branch)
            if upgrade_data.get(repoid) is None:
                # no data stored for this repository, skipping
                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                        repoid, "branch upgrade data not avail",)
                )
                continue
            repo_upgrade_data = upgrade_data[repoid]

            const_debug_write(__name__,
                "run_repository_post_branch_upgrade_hooks: upgrade data: %s" % (
                    repo_upgrade_data,)
            )

            for from_branch in sorted(repo_upgrade_data):

                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: upgrade: %s" % (
                        from_branch,)
                )

                # yeah, this is run for every branch even if script
                # which md5 is checked against is the same
                # this makes the code very flexible
                post_mig_md5, post_upg_md5 = repo_upgrade_data[from_branch]
                if branch_upg_md5sum == post_upg_md5:
                    # md5 is equal, this means that it's been already run
                    const_debug_write(__name__,
                        "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                            "already run for from_branch", from_branch,)
                    )
                    continue

                hooks_ran.add(repoid)

                if pretend:
                    const_debug_write(__name__,
                        "run_repository_post_branch_upgrade_hooks: %s: %s => %s" % (
                            "pretend enabled, not actually running",
                            repoid, from_branch,
                        )
                    )
                    continue

                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                        "running upgrade script from_branch:", from_branch,)
                )

                args = ["/bin/sh", branch_upg_script, repoid,
                    etpConst['systemroot'] + "/", from_branch, branch]
                proc = subprocess.Popen(args, stdin = sys.stdin,
                    stdout = sys.stdout, stderr = sys.stderr)
                mig_rc = proc.wait()

                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                        "upgrade script exit status", mig_rc,)
                )

                if mig_rc != 0:
                    errors = True

                # save branch_upg_md5sum in db
                client_dbconn.setBranchMigrationPostUpgradeMd5sum(repoid,
                    from_branch, branch, branch_upg_md5sum)

                const_debug_write(__name__,
                    "run_repository_post_branch_upgrade_hooks: %s: %s" % (
                        "saved upgrade data",
                        (repoid, from_branch, branch, branch_upg_md5sum,),
                    )
                )

        return hooks_ran, errors


class MiscMixin:

    # resources lock file object container
    RESOURCES_LOCK_F_REF = None
    RESOURCES_LOCK_F_COUNT = 0

    def reload_constants(self):
        initconfig_entropy_constants(etpSys['rootdir'])
        self.SystemSettings.clear()

    def setup_default_file_perms(self, filepath):
        # setup file permissions
        os.chmod(filepath,0o664)
        if etpConst['entropygid'] != None:
            os.chown(filepath,-1,etpConst['entropygid'])

    def resources_create_lock(self):
        acquired = self.create_pid_file_lock(
            etpConst['locks']['using_resources'])
        if acquired:
            MiscMixin.RESOURCES_LOCK_F_COUNT += 1
        return acquired

    def resources_remove_lock(self):

        # decrement lock counter
        if MiscMixin.RESOURCES_LOCK_F_COUNT > 0:
            MiscMixin.RESOURCES_LOCK_F_COUNT -= 1

        # if lock counter > 0, still locked
        # waiting for other upper-level calls
        if MiscMixin.RESOURCES_LOCK_F_COUNT > 0:
            return

        f_obj = MiscMixin.RESOURCES_LOCK_F_REF
        if f_obj is not None:
            fcntl.flock(f_obj.fileno(), fcntl.LOCK_UN)

            if f_obj is not None:
                f_obj.close()
            MiscMixin.RESOURCES_LOCK_F_REF = None

        if os.path.isfile(etpConst['locks']['using_resources']):
            os.remove(etpConst['locks']['using_resources'])

    def resources_check_lock(self):
        return self.check_pid_file_lock(etpConst['locks']['using_resources'])

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
        if (s_pid != mypid) and const_pid_exists(s_pid):
            # is it running
            return True # locked
        return False

    def create_pid_file_lock(self, pidfile, mypid = None):

        if MiscMixin.RESOURCES_LOCK_F_REF is not None:
            # already locked, reentrant lock
            return True

        lockdir = os.path.dirname(pidfile)
        if not os.path.isdir(lockdir):
            os.makedirs(lockdir,0o775)
        const_setup_perms(lockdir,etpConst['entropygid'])
        if mypid == None:
            mypid = os.getpid()

        pid_f = open(pidfile, "w")
        try:
            fcntl.flock(pid_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as err:
            if err.errno not in (errno.EACCES, errno.EAGAIN,):
                # ouch, wtf?
                raise
            pid_f.close()
            return False # lock already acquired

        pid_f.write(str(mypid))
        pid_f.flush()
        MiscMixin.RESOURCES_LOCK_F_REF = pid_f
        return True

    def application_lock_check(self, silent = False):
        # check if another instance is running
        etpConst['applicationlock'] = False
        const_setup_entropy_pid(just_read = True)
        locked = self.entropyTools.application_lock_check(gentle = True)
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
                    # wait for other process to exit
                    # 5 seconds should be enough
                    time.sleep(5)
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
        if constant_name in etpConst:
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
        if repositories is None:
            repositories = self.validRepositories
        for repoid in repositories:
            self.open_repository(repoid)

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
                os.makedirs(sets_dir,0o775)
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

    def swap_branch_in_download_relative_uri(self, new_branch, db_download_uri):
        cur_branch = self.get_branch_from_download_relative_uri(db_download_uri)
        return db_download_uri.replace("/%s/" % (cur_branch,),
            "/%s/" % (new_branch,))

    def unused_packages_test(self, dbconn = None):
        if dbconn == None: dbconn = self.clientDbconn
        return [x for x in dbconn.retrieveUnusedIdpackages() if self.validate_package_removal(x)]

    def get_licenses_to_accept(self, install_queue):
        if not install_queue:
            return {}
        licenses = {}
        cl_id = self.sys_settings_client_plugin_id
        repo_sys_data = self.SystemSettings[cl_id]['repositories']

        for match in install_queue:
            repoid = match[1]
            dbconn = self.open_repository(repoid)
            wl = repo_sys_data['license_whitelist'].get(repoid)
            if not wl:
                continue
            keys = dbconn.retrieveLicensedataKeys(match[0])
            for key in keys:
                if key not in wl:
                    found = self.clientDbconn.isLicenseAccepted(key)
                    if found:
                        continue
                    if key not in licenses:
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
        self.Cacher.discard()
        self.Cacher.stop()
        self.purge_cache(showProgress = False)
        self.close_all_repositories()
        # etpConst should be readonly but we override the rule here
        # this is also useful when no config file or parameter into it exists
        etpConst['branch'] = branch
        self.entropyTools.write_new_branch(branch)
        # there are no valid repos atm
        del self.validRepositories[:]
        self.SystemSettings.clear()

        # reset treeupdatesactions
        self.reopen_client_repository()
        self.clientDbconn.resetTreeupdatesDigests()
        self.validate_repositories(quiet = True)
        self.close_all_repositories()
        if self.xcache:
            self.Cacher.start()

    def get_meant_packages(self, search_term, from_installed = False,
        valid_repos = None):

        if valid_repos is None:
            valid_repos = []

        pkg_data = []
        atom_srch = False
        if "/" in search_term:
            atom_srch = True

        if from_installed:
            if hasattr(self, 'clientDbconn'):
                if self.clientDbconn is not None:
                    valid_repos.append(self.clientDbconn)

        elif not valid_repos:
            valid_repos.extend(self.validRepositories[:])

        for repo in valid_repos:
            if isinstance(repo, basestring):
                dbconn = self.open_repository(repo)
            elif isinstance(repo, EntropyRepository):
                dbconn = repo
            else:
                continue
            pkg_data.extend([(x,repo,) for x in \
                dbconn.searchSimilarPackages(search_term, atom = atom_srch)])

        return pkg_data

    def get_package_groups(self):
        """
        Return Entropy Package Groups metadata. The returned dictionary
        contains information to make Entropy Client users to group packages
        into "macro" categories.

        @return: Entropy Package Groups metadata
        @rtype: dict
        """
        from entropy.spm.plugins.factory import get_default_class
        spm = get_default_class()
        groups = spm.get_package_groups().copy()

        # expand metadata
        categories = self.list_repo_categories()
        for data in list(groups.values()):

            exp_cats = set()
            for g_cat in data['categories']:
                exp_cats.update([x for x in categories if x.startswith(g_cat)])
            data['categories'] = sorted(exp_cats)

        return groups

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

    def get_package_match_config_protect(self, match, mask = False):

        idpackage, repoid = match
        dbconn = self.open_repository(repoid)
        cl_id = self.sys_settings_client_plugin_id
        misc_data = self.SystemSettings[cl_id]['misc']
        if mask:
            config_protect = set(dbconn.retrieveProtectMask(idpackage).split())
            config_protect |= set(misc_data['configprotectmask'])
        else:
            config_protect = set(dbconn.retrieveProtect(idpackage).split())
            config_protect |= set(misc_data['configprotect'])
        config_protect = [etpConst['systemroot']+x for x in config_protect]

        return sorted(config_protect)

    def get_installed_package_config_protect(self, idpackage, mask = False):

        if self.clientDbconn == None:
            return []
        cl_id = self.sys_settings_client_plugin_id
        misc_data = self.SystemSettings[cl_id]['misc']
        if mask:
            _pmask = self.clientDbconn.retrieveProtectMask(idpackage).split()
            config_protect = set(_pmask)
            config_protect |= set(misc_data['configprotectmask'])
        else:
            _protect = self.clientDbconn.retrieveProtect(idpackage).split()
            config_protect = set(_protect)
            config_protect |= set(misc_data['configprotect'])
        config_protect = [etpConst['systemroot']+x for x in config_protect]

        return sorted(config_protect)

    def get_system_config_protect(self, mask = False):

        if self.clientDbconn == None:
            return []

        # FIXME: workaround because this method is called
        # before misc_parser
        cl_id = self.sys_settings_client_plugin_id
        misc_data = self.SystemSettings[cl_id]['misc']
        if mask:
            _pmask = self.clientDbconn.listConfigProtectEntries(mask = True)
            config_protect = set(_pmask)
            config_protect |= set(misc_data['configprotectmask'])
        else:
            _protect = self.clientDbconn.listConfigProtectEntries()
            config_protect = set(_protect)
            config_protect |= set(misc_data['configprotect'])
        config_protect = [etpConst['systemroot']+x for x in config_protect]

        return sorted(config_protect)

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

        import tarfile

        if compression not in ("bz2","","gz"):
            compression = "bz2"

        # getting package info
        pkgtag = ''
        pkgrev = "~"+str(pkgdata['revision'])
        if pkgdata['versiontag']: pkgtag = "#"+pkgdata['versiontag']
        pkgname = pkgdata['name']+"-"+pkgdata['version']+pkgrev+pkgtag # + version + tag
        pkgcat = pkgdata['category']
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
                    tarinfo.mode = stat.S_IMODE(exist.st_mode)
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
        import entropy.xpak as xpak
        Spm = self.Spm()

        spm_name = self.entropyTools.remove_tag(pkgname)
        spm_name = self.entropyTools.remove_entropy_revision(spm_name)
        if portdbPath is None:
            spm_pkg = os.path.join(pkgcat, spm_name)
            dbbuild = Spm.get_installed_package_build_script_path(spm_pkg)
            dbdir = os.path.dirname(dbbuild)
        else:
            dbdir = os.path.join(portdbPath, pkgcat, spm_name)

        if os.path.isdir(dbdir):
            tbz2 = xpak.tbz2(dirpath)
            tbz2.recompose(dbdir)

        if edb:
            self.inject_entropy_database_into_package(dirpath, pkgdata)

        if os.path.isfile(dirpath):
            return dirpath
        return None


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
        if not hasattr(f, '__call__'):
            raise IncorrectParameter('IncorrectParameter: %s: %s' % (_("not a valid method"),method,) )

        self.Cacher.discard()
        done = f(match, dry_run)
        if done and not dry_run:
            self.SystemSettings.clear()

        # clear atomMatch cache anyway
        if clean_all_cache and not dry_run:
            self.clear_dump_cache(etpCache['world_available'])
            self.clear_dump_cache(etpCache['world_update'])
            self.clear_dump_cache(etpCache['critical_update'])

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
