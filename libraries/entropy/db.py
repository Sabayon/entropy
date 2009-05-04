# -*- coding: utf-8 -*-
"""
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
"""

from __future__ import with_statement
import os
import shutil
import subprocess
from entropy.const import etpConst, etpCache
from entropy.exceptions import IncorrectParameter, InvalidAtom, \
    SystemDatabaseError, OperationNotPermitted
from entropy.i18n import _
from entropy.output import brown, bold, red, blue, darkred, darkgreen, \
    TextInterface
from entropy.cache import EntropyCacher
from entropy.core import Singleton, SystemSettings

try: # try with sqlite3 from python 2.5 - default one
    from sqlite3 import dbapi2
except ImportError: # fallback to pysqlite
    try:
        from pysqlite2 import dbapi2
    except ImportError, e:
        raise SystemError(
            "%s. %s: %s" % (
                _("Entropy needs Python compiled with sqlite3 support"),
                _("Error"),
                e,
            )
        )

class Status(Singleton):

    def init_singleton(self):
        self.__data = {}

    def __create_if_necessary(self, db):
        if db not in self.__data:
            self.__data[db] = {}
            self.__data[db]['tainted'] = False
            self.__data[db]['bumped'] = False
            self.__data[db]['unlock_msg'] = False

    def set_unlock_msg(self, db):
        self.__create_if_necessary(db)
        self.__data[db]['unlock_msg'] = True

    def unset_unlock_msg(self, db):
        self.__create_if_necessary(db)
        self.__data[db]['unlock_msg'] = False

    def set_tainted(self, db):
        self.__create_if_necessary(db)
        self.__data[db]['tainted'] = True

    def unset_tainted(self, db):
        self.__create_if_necessary(db)
        self.__data[db]['tainted'] = False

    def set_bumped(self, db):
        self.__create_if_necessary(db)
        self.__data[db]['bumped'] = True

    def unset_bumped(self, db):
        self.__create_if_necessary(db)
        self.__data[db]['bumped'] = False

    def is_tainted(self, db):
        self.__create_if_necessary(db)
        return self.__data[db]['tainted']

    def is_bumped(self, db):
        self.__create_if_necessary(db)
        return self.__data[db]['bumped']

    def is_unlock_msg(self, db):
        self.__create_if_necessary(db)
        return self.__data[db]['unlock_msg']


class Schema:

    def get_init(self):
        return """
            CREATE TABLE baseinfo (
                idpackage INTEGER PRIMARY KEY AUTOINCREMENT,
                atom VARCHAR,
                idcategory INTEGER,
                name VARCHAR,
                version VARCHAR,
                versiontag VARCHAR,
                revision INTEGER,
                branch VARCHAR,
                slot VARCHAR,
                idlicense INTEGER,
                etpapi INTEGER,
                trigger INTEGER
            );

            CREATE TABLE extrainfo (
                idpackage INTEGER PRIMARY KEY,
                description VARCHAR,
                homepage VARCHAR,
                download VARCHAR,
                size VARCHAR,
                idflags INTEGER,
                digest VARCHAR,
                datecreation VARCHAR
            );

            CREATE TABLE content (
                idpackage INTEGER,
                file VARCHAR,
                type VARCHAR
            );

            CREATE TABLE provide (
                idpackage INTEGER,
                atom VARCHAR
            );

            CREATE TABLE dependencies (
                idpackage INTEGER,
                iddependency INTEGER,
                type INTEGER
            );

            CREATE TABLE dependenciesreference (
                iddependency INTEGER PRIMARY KEY AUTOINCREMENT,
                dependency VARCHAR
            );

            CREATE TABLE dependstable (
                iddependency INTEGER PRIMARY KEY,
                idpackage INTEGER
            );

            CREATE TABLE conflicts (
                idpackage INTEGER,
                conflict VARCHAR
            );

            CREATE TABLE mirrorlinks (
                mirrorname VARCHAR,
                mirrorlink VARCHAR
            );

            CREATE TABLE sources (
                idpackage INTEGER,
                idsource INTEGER
            );

            CREATE TABLE sourcesreference (
                idsource INTEGER PRIMARY KEY AUTOINCREMENT,
                source VARCHAR
            );

            CREATE TABLE useflags (
                idpackage INTEGER,
                idflag INTEGER
            );

            CREATE TABLE useflagsreference (
                idflag INTEGER PRIMARY KEY AUTOINCREMENT,
                flagname VARCHAR
            );

            CREATE TABLE keywords (
                idpackage INTEGER,
                idkeyword INTEGER
            );

            CREATE TABLE keywordsreference (
                idkeyword INTEGER PRIMARY KEY AUTOINCREMENT,
                keywordname VARCHAR
            );

            CREATE TABLE categories (
                idcategory INTEGER PRIMARY KEY AUTOINCREMENT,
                category VARCHAR
            );

            CREATE TABLE licenses (
                idlicense INTEGER PRIMARY KEY AUTOINCREMENT,
                license VARCHAR
            );

            CREATE TABLE flags (
                idflags INTEGER PRIMARY KEY AUTOINCREMENT,
                chost VARCHAR,
                cflags VARCHAR,
                cxxflags VARCHAR
            );

            CREATE TABLE configprotect (
                idpackage INTEGER PRIMARY KEY,
                idprotect INTEGER
            );

            CREATE TABLE configprotectmask (
                idpackage INTEGER PRIMARY KEY,
                idprotect INTEGER
            );

            CREATE TABLE configprotectreference (
                idprotect INTEGER PRIMARY KEY AUTOINCREMENT,
                protect VARCHAR
            );

            CREATE TABLE systempackages (
                idpackage INTEGER PRIMARY KEY
            );

            CREATE TABLE injected (
                idpackage INTEGER PRIMARY KEY
            );

            CREATE TABLE installedtable (
                idpackage INTEGER PRIMARY KEY,
                repositoryname VARCHAR,
                source INTEGER
            );

            CREATE TABLE sizes (
                idpackage INTEGER PRIMARY KEY,
                size INTEGER
            );

            CREATE TABLE messages (
                idpackage INTEGER,
                message VARCHAR
            );

            CREATE TABLE counters (
                counter INTEGER,
                idpackage INTEGER,
                branch VARCHAR,
                PRIMARY KEY(idpackage,branch)
            );

            CREATE TABLE trashedcounters (
                counter INTEGER
            );

            CREATE TABLE eclasses (
                idpackage INTEGER,
                idclass INTEGER
            );

            CREATE TABLE eclassesreference (
                idclass INTEGER PRIMARY KEY AUTOINCREMENT,
                classname VARCHAR
            );

            CREATE TABLE needed (
                idpackage INTEGER,
                idneeded INTEGER,
                elfclass INTEGER
            );

            CREATE TABLE neededreference (
                idneeded INTEGER PRIMARY KEY AUTOINCREMENT,
                library VARCHAR
            );

            CREATE TABLE treeupdates (
                repository VARCHAR PRIMARY KEY,
                digest VARCHAR
            );

            CREATE TABLE treeupdatesactions (
                idupdate INTEGER PRIMARY KEY AUTOINCREMENT,
                repository VARCHAR,
                command VARCHAR,
                branch VARCHAR,
                date VARCHAR
            );

            CREATE TABLE licensedata (
                licensename VARCHAR UNIQUE,
                text BLOB,
                compressed INTEGER
            );

            CREATE TABLE licenses_accepted (
                licensename VARCHAR UNIQUE
            );

            CREATE TABLE triggers (
                idpackage INTEGER PRIMARY KEY,
                data BLOB
            );

            CREATE TABLE entropy_misc_counters (
                idtype INTEGER PRIMARY KEY,
                counter INTEGER
            );

            CREATE TABLE categoriesdescription (
                category VARCHAR,
                locale VARCHAR,
                description VARCHAR
            );

            CREATE TABLE packagesets (
                setname VARCHAR,
                dependency VARCHAR
            );

            CREATE TABLE packagechangelogs (
                category VARCHAR,
                name VARCHAR,
                changelog BLOB,
                PRIMARY KEY (category, name)
            );

            CREATE TABLE automergefiles (
                idpackage INTEGER,
                configfile VARCHAR,
                md5 VARCHAR
            );

            CREATE TABLE packagesignatures (
                idpackage INTEGER PRIMARY KEY,
                sha1 VARCHAR,
                sha256 VARCHAR,
                sha512 VARCHAR
            );

            CREATE TABLE packagespmphases (
                idpackage INTEGER PRIMARY KEY,
                phases VARCHAR
            );

        """

class LocalRepository:

    import entropy.tools as entropyTools
    import entropy.dump as dumpTools
    import threading
    def __init__(self, readOnly = False, noUpload = False, dbFile = None,
        clientDatabase = False, xcache = False, dbname = etpConst['serverdbid'],
        indexing = True, OutputInterface = None, ServiceInterface = None,
        skipChecks = False, useBranch = None, lockRemote = True):

        self.SystemSettings = SystemSettings()
        self.srv_sys_settings_plugin = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        self.dbMatchCacheKey = etpCache['dbMatch']
        self.dbSearchCacheKey = etpCache['dbSearch']
        self.dbname = dbname
        self.lockRemote = lockRemote
        self.client_settings_plugin_id = etpConst['system_settings_plugins_ids']['client_plugin']
        self.db_branch = self.SystemSettings['repositories']['branch']
        if self.dbname == etpConst['clientdbid']:
            self.db_branch = None
        if useBranch != None: self.db_branch = useBranch

        if OutputInterface == None:
            OutputInterface = TextInterface()

        if dbFile == None:
            raise IncorrectParameter("IncorrectParameter: %s" % (
                _("valid database path needed"),) )

        self.Cacher = EntropyCacher()
        self.WriteLock = self.threading.Lock()
        self.dbapi2 = dbapi2
        # setup output interface
        self.OutputInterface = OutputInterface
        self.updateProgress = self.OutputInterface.updateProgress
        self.askQuestion = self.OutputInterface.askQuestion
        # setup service interface
        self.ServiceInterface = ServiceInterface
        self.readOnly = readOnly
        self.noUpload = noUpload
        self.clientDatabase = clientDatabase
        self.xcache = xcache
        self.indexing = indexing
        self.skipChecks = skipChecks
        if not self.skipChecks:
            if not self.entropyTools.is_user_in_entropy_group():
                # forcing since we won't have write access to db
                self.indexing = False
            # live systems don't like wasting RAM
            if self.entropyTools.islive():
                self.indexing = False
        self.dbFile = dbFile
        self.dbclosed = True
        self.server_repo = None

        if not self.clientDatabase:
            self.server_repo = self.dbname[len(etpConst['serverdbid']):]
            self.create_dbstatus_data()

        if not self.skipChecks:
            # no caching for non root and server connections
            if (self.dbname.startswith(etpConst['serverdbid'])) or \
                (not self.entropyTools.is_user_in_entropy_group()):
                self.xcache = False
        self.live_cache = {}

        # create connection
        self.connection = self.dbapi2.connect(dbFile, timeout=300.0,
            check_same_thread = False)
        self.cursor = self.connection.cursor()

        if not self.skipChecks:
            if os.access(self.dbFile, os.W_OK) and \
                self.doesTableExist('baseinfo') and \
                self.doesTableExist('extrainfo'):

                if self.entropyTools.islive() and etpConst['systemroot']:
                    self.databaseStructureUpdates()
                else:
                    self.databaseStructureUpdates()

        # now we can set this to False
        self.dbclosed = False

    def setCacheSize(self, size):
        self.cursor.execute('PRAGMA cache_size = '+str(size))

    def setDefaultCacheSize(self, size):
        self.cursor.execute('PRAGMA default_cache_size = '+str(size))


    def __del__(self):
        if not self.dbclosed:
            self.closeDB()

    def create_dbstatus_data(self):
        taint_file = self.ServiceInterface.get_local_database_taint_file(
            self.server_repo)
        if os.path.isfile(taint_file):
            dbs = Status()
            dbs.set_tainted(self.dbFile)
            dbs.set_bumped(self.dbFile)

    def closeDB(self):

        self.dbclosed = True

        # if the class is opened readOnly, close and forget
        if self.readOnly:
            self.cursor.close()
            self.connection.close()
            return

        if self.clientDatabase:
            if self.dbname == etpConst['clientdbid']:
                try:
                    self.doCleanups()
                except self.dbapi2.Error:
                    pass
            self.commitChanges()
            self.cursor.close()
            self.connection.close()
            return

        sts = Status()
        if not sts.is_tainted(self.dbFile):
            # we can unlock it, no changes were made
            self.ServiceInterface.MirrorsService.lock_mirrors(False,
                repo = self.server_repo)
        elif not sts.is_unlock_msg(self.dbFile):
            u_msg = _("Mirrors have not been unlocked. Remember to sync them.")
            self.updateProgress(
                darkgreen(u_msg),
                importance = 1,
                type = "info",
                header = brown(" * ")
            )
            sts.set_unlock_msg(self.dbFile) # avoid spamming

        self.commitChanges()
        self.cursor.close()
        self.connection.close()

    def vacuum(self):
        self.cursor.execute("vacuum")

    def commitChanges(self):

        if self.readOnly:
            return

        try:
            self.connection.commit()
        except self.dbapi2.Error:
            pass

        if not self.clientDatabase:
            self.taintDatabase()
            dbs = Status()
            if (dbs.is_tainted(self.dbFile)) and \
                (not dbs.is_bumped(self.dbFile)):
                # bump revision, setting DatabaseBump causes
                # the session to just bump once
                dbs.set_bumped(self.dbFile)
                self.revisionBump()

    def taintDatabase(self):
        # if it's equo to open it, this should be avoided
        if self.clientDatabase:
            return
        # taint the database status
        taint_file = self.ServiceInterface.get_local_database_taint_file(
            repo = self.server_repo)
        f = open(taint_file, "w")
        f.write(etpConst['currentarch']+" database tainted\n")
        f.flush()
        f.close()
        Status().set_tainted(self.dbFile)

    def untaintDatabase(self):
        # if it's equo to open it, this should be avoided
        if self.clientDatabase:
            return
        Status().unset_tainted(self.dbFile)
        # untaint the database status
        taint_file = self.ServiceInterface.get_local_database_taint_file(
            repo = self.server_repo)
        if os.path.isfile(taint_file):
            os.remove(taint_file)

    def revisionBump(self):
        revision_file = self.ServiceInterface.get_local_database_revision_file(
            repo = self.server_repo)
        if not os.path.isfile(revision_file):
            revision = 1
        else:
            f = open(revision_file, "r")
            revision = int(f.readline().strip())
            revision += 1
            f.close()
        f = open(revision_file, "w")
        f.write(str(revision)+"\n")
        f.flush()
        f.close()

    def isDatabaseTainted(self):
        taint_file = self.ServiceInterface.get_local_database_taint_file(
            repo = self.server_repo)
        if os.path.isfile(taint_file):
            return True
        return False

    # never use this unless you know what you're doing
    def initializeDatabase(self):
        self.checkReadOnly()
        my = Schema()
        for table in self.listAllTables():
            try:
                self.cursor.execute("DROP TABLE %s" % (table,))
            except self.dbapi2.OperationalError:
                # skip tables that can't be dropped
                continue
        self.cursor.executescript(my.get_init())
        self.databaseStructureUpdates()
        # set cache size
        self.setCacheSize(8192)
        self.setDefaultCacheSize(8192)
        self.commitChanges()

    def checkReadOnly(self):
        if self.readOnly:
            raise OperationNotPermitted("OperationNotPermitted: %s." % (
                    _("can't do that on a readonly database"),
                )
            )

    # check for /usr/portage/profiles/updates changes
    def serverUpdatePackagesData(self):

        etpConst['server_treeupdatescalled'].add(self.server_repo)

        repo_updates_file = self.ServiceInterface.get_local_database_treeupdates_file(self.server_repo)
        doRescan = False

        stored_digest = self.retrieveRepositoryUpdatesDigest(self.server_repo)
        if stored_digest == -1:
            doRescan = True

        # check portage files for changes if doRescan is still false
        portage_dirs_digest = "0"
        if not doRescan:

            treeupdates_dict = self.ServiceInterface.repository_treeupdate_digests

            if treeupdates_dict.has_key(self.server_repo):
                portage_dirs_digest = treeupdates_dict.get(self.server_repo)
            else:

                spm = self.ServiceInterface.SpmService
                # grab portdir
                updates_dir = etpConst['systemroot'] + \
                    spm.get_spm_setting("PORTDIR") + "/profiles/updates"
                if os.path.isdir(updates_dir):
                    # get checksum
                    mdigest = self.entropyTools.md5sum_directory(updates_dir,
                        get_obj = True)
                    # also checksum etpConst['etpdatabaseupdatefile']
                    if os.path.isfile(repo_updates_file):
                        f = open(repo_updates_file)
                        block = f.read(1024)
                        while block:
                            mdigest.update(block)
                            block = f.read(1024)
                        f.close()
                    portage_dirs_digest = mdigest.hexdigest()
                    treeupdates_dict[self.server_repo] = portage_dirs_digest
                del updates_dir

        if doRescan or (str(stored_digest) != str(portage_dirs_digest)):

            # force parameters
            self.readOnly = False
            self.noUpload = True

            # reset database tables
            self.clearTreeupdatesEntries(self.server_repo)

            spm = self.ServiceInterface.SpmService
            updates_dir = etpConst['systemroot'] + \
                spm.get_spm_setting("PORTDIR") + "/profiles/updates"
            update_files = self.entropyTools.sort_update_files(
                os.listdir(updates_dir))
            update_files = [os.path.join(updates_dir, x) for x in update_files]
            # now load actions from files
            update_actions = []
            for update_file in update_files:
                f = open(update_file, "r")
                mycontent = f.readlines()
                f.close()
                lines = [x.strip() for x in mycontent if x.strip()]
                update_actions.extend(lines)

            # add entropy packages.db.repo_updates content
            if os.path.isfile(repo_updates_file):
                f = open(repo_updates_file, "r")
                mycontent = f.readlines()
                f.close()
                lines = [x.strip() for x in mycontent if x.strip() and \
                    not x.strip().startswith("#")]
                update_actions.extend(lines)
            # now filter the required actions
            update_actions = self.filterTreeUpdatesActions(update_actions)
            if update_actions:

                mytxt = "%s: %s. %s %s" % (
                    bold(_("ATTENTION")),
                    red(_("forcing package updates")),
                    red(_("Syncing with")),
                    blue(updates_dir),
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = brown(" * ")
                )
                # lock database
                if self.lockRemote:
                    self.ServiceInterface.do_server_repository_sync_lock(
                        self.server_repo, self.noUpload)
                # now run queue
                try:
                    self.runTreeUpdatesActions(update_actions)
                except:
                    # destroy digest
                    self.setRepositoryUpdatesDigest(self.server_repo, "-1")
                    raise

                # store new actions
                self.addRepositoryUpdatesActions(
                    self.server_repo, update_actions, self.db_branch)

            # store new digest into database
            self.setRepositoryUpdatesDigest(
                self.server_repo, portage_dirs_digest)
            self.commitChanges()

    def clientUpdatePackagesData(self, clientDbconn, force = False):

        if clientDbconn == None:
            return

        repository = self.dbname[len(etpConst['dbnamerepoprefix']):]
        etpConst['client_treeupdatescalled'].add(repository)

        doRescan = False
        shell_rescan = os.getenv("ETP_TREEUPDATES_RESCAN")
        if shell_rescan: doRescan = True

        # check database digest
        stored_digest = self.retrieveRepositoryUpdatesDigest(repository)
        if stored_digest == -1:
            doRescan = True

        # check stored value in client database
        client_digest = "0"
        if not doRescan:
            client_digest = clientDbconn.retrieveRepositoryUpdatesDigest(
                repository)

        if doRescan or (str(stored_digest) != str(client_digest)) or force:

            # reset database tables
            clientDbconn.clearTreeupdatesEntries(repository)

            # load updates
            update_actions = self.retrieveTreeUpdatesActions(repository)
            # now filter the required actions
            update_actions = clientDbconn.filterTreeUpdatesActions(
                update_actions)

            if update_actions:

                mytxt = "%s: %s. %s %s" % (
                    bold(_("ATTENTION")),
                    red(_("forcing packages metadata update")),
                    red(_("Updating system database using repository id")),
                    blue(repository),
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = darkred(" * ")
                    )
                # run stuff
                clientDbconn.runTreeUpdatesActions(update_actions)

            # store new digest into database
            clientDbconn.setRepositoryUpdatesDigest(repository, stored_digest)
            # store new actions
            clientDbconn.addRepositoryUpdatesActions(etpConst['clientdbid'],
                update_actions, self.SystemSettings['repositories']['branch'])
            clientDbconn.commitChanges()
            # clear client cache
            clientDbconn.clearCache()
            return True

    # this functions will filter either data from /usr/portage/profiles/updates/*
    # or repository database returning only the needed actions
    def filterTreeUpdatesActions(self, actions):
        new_actions = []
        for action in actions:

            if action in new_actions: # skip dupies
                continue

            doaction = action.split()
            if doaction[0] == "slotmove":

                # slot move
                atom = doaction[1]
                from_slot = doaction[2]
                to_slot = doaction[3]
                atom_key = self.entropyTools.dep_getkey(atom)
                category = atom_key.split("/")[0]
                matches = self.atomMatch(atom, matchSlot = from_slot,
                    multiMatch = True)
                found = False
                if matches[1] == 0:
                    # found atoms, check category
                    for idpackage in matches[0]:
                        myslot = self.retrieveSlot(idpackage)
                        mycategory = self.retrieveCategory(idpackage)
                        if mycategory == category:
                            if  (myslot != to_slot) and \
                            (action not in new_actions):
                                new_actions.append(action)
                                found = True
                                break
                    if found:
                        continue
                # if we get here it means found == False
                # search into dependencies
                dep_atoms = self.searchDependency(atom_key, like = True,
                    multi = True, strings = True)
                dep_atoms = [x for x in dep_atoms if x.endswith(":"+from_slot) \
                    and self.entropyTools.dep_getkey(x) == atom_key]
                if dep_atoms:
                    new_actions.append(action)

            elif doaction[0] == "move":
                atom = doaction[1] # usually a key
                atom_key = self.entropyTools.dep_getkey(atom)
                category = atom_key.split("/")[0]
                matches = self.atomMatch(atom, multiMatch = True)
                found = False
                if matches[1] == 0:
                    for idpackage in matches[0]:
                        mycategory = self.retrieveCategory(idpackage)
                        if (mycategory == category) and (action \
                            not in new_actions):
                            new_actions.append(action)
                            found = True
                            break
                    if found:
                        continue
                # if we get here it means found == False
                # search into dependencies
                dep_atoms = self.searchDependency(atom_key, like = True,
                    multi = True, strings = True)
                dep_atoms = [x for x in dep_atoms if \
                    self.entropyTools.dep_getkey(x) == atom_key]
                if dep_atoms:
                    new_actions.append(action)
        return new_actions

    # this is the place to add extra actions support
    def runTreeUpdatesActions(self, actions):

        # just run fixpackages if gentoo-compat is enabled
        if etpConst['gentoo-compat']:

            mytxt = "%s: %s, %s." % (
                bold(_("SPM")),
                blue(_("Running fixpackages")),
                red(_("it could take a while")),
            )
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = darkred(" * ")
            )
            if self.clientDatabase:
                try:
                    spm = self.ServiceInterface.Spm()
                    spm.run_fixpackages()
                except:
                    pass
            else:
                self.ServiceInterface.SpmService.run_fixpackages()

        spm_moves = set()
        quickpkg_atoms = set()
        for action in actions:
            command = action.split()
            mytxt = "%s: %s: %s." % (
                bold(_("ENTROPY")),
                red(_("action")),
                blue(action),
            )
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = darkred(" * ")
            )
            if command[0] == "move":
                spm_moves.add(action)
                quickpkg_atoms |= self.runTreeUpdatesMoveAction(command[1:],
                    quickpkg_atoms)
            elif command[0] == "slotmove":
                quickpkg_atoms |= self.runTreeUpdatesSlotmoveAction(command[1:],
                    quickpkg_atoms)

        if quickpkg_atoms and not self.clientDatabase:
            # quickpkg package and packages owning it as a dependency
            try:
                self.runTreeUpdatesQuickpkgAction(quickpkg_atoms)
            except:
                self.entropyTools.print_traceback()
                mytxt = "%s: %s: %s, %s." % (
                    bold(_("WARNING")),
                    red(_("Cannot complete quickpkg for atoms")),
                    blue(str(list(quickpkg_atoms))),
                    _("do it manually"),
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = darkred(" * ")
                )
            self.commitChanges()

        if spm_moves:
            try:
                self.doTreeupdatesSpmCleanup(spm_moves)
            except Exception, e:
                mytxt = "%s: %s: %s, %s." % (
                    bold(_("WARNING")),
                    red(_("Cannot run SPM cleanup, error")),
                    Exception,
                    e,
                )
                self.entropyTools.print_traceback()

        # discard cache
        self.clearCache()


    # -- move action:
    # 1) move package key to the new name: category + name + atom
    # 2) update all the dependencies in dependenciesreference to the new key
    # 3) run fixpackages which will update /var/db/pkg files
    # 4) automatically run quickpkg() to build the new binary and
    #    tainted binaries owning tainted iddependency and taint database
    def runTreeUpdatesMoveAction(self, move_command, quickpkg_queue):

        key_from = move_command[0]
        key_to = move_command[1]
        cat_to = key_to.split("/")[0]
        name_to = key_to.split("/")[1]
        matches = self.atomMatch(key_from, multiMatch = True)
        iddependencies = set()

        if matches[1] == 0:

            for idpackage in matches[0]:

                slot = self.retrieveSlot(idpackage)
                old_atom = self.retrieveAtom(idpackage)
                new_atom = old_atom.replace(key_from, key_to)

                ### UPDATE DATABASE
                # update category
                self.setCategory(idpackage, cat_to)
                # update name
                self.setName(idpackage, name_to)
                # update atom
                self.setAtom(idpackage, new_atom)

                # look for packages we need to quickpkg again
                # note: quickpkg_queue is simply ignored if self.clientDatabase
                quickpkg_queue.add(key_to+":"+str(slot))

                if not self.clientDatabase:

                    # check for injection and warn the developer
                    injected = self.isInjected(idpackage)
                    if injected:
                        mytxt = "%s: %s %s. %s !!! %s." % (
                            bold(_("INJECT")),
                            blue(str(new_atom)),
                            red(_("has been injected")),
                            red(_("quickpkg manually to update embedded db")),
                            red(_("Repository database updated anyway")),
                        )
                        self.updateProgress(
                            mytxt,
                            importance = 1,
                            type = "warning",
                            header = darkred(" * ")
                        )

        iddeps = self.searchDependency(key_from, like = True, multi = True)
        for iddep in iddeps:
            # update string
            mydep = self.retrieveDependencyFromIddependency(iddep)
            mydep_key = self.entropyTools.dep_getkey(mydep)
            # avoid changing wrong atoms -> dev-python/qscintilla-python would
            # become x11-libs/qscintilla if we don't do this check
            if mydep_key != key_from:
                continue
            mydep = mydep.replace(key_from, key_to)
            # now update
            # dependstable on server is always re-generated
            self.setDependency(iddep, mydep)
            # we have to repackage also package owning this iddep
            iddependencies |= self.searchIdpackageFromIddependency(iddep)

        self.commitChanges()
        quickpkg_queue = list(quickpkg_queue)
        for x in range(len(quickpkg_queue)):
            myatom = quickpkg_queue[x]
            myatom = myatom.replace(key_from, key_to)
            quickpkg_queue[x] = myatom
        quickpkg_queue = set(quickpkg_queue)
        for idpackage_owner in iddependencies:
            myatom = self.retrieveAtom(idpackage_owner)
            myatom = myatom.replace(key_from, key_to)
            quickpkg_queue.add(myatom)
        return quickpkg_queue


    # -- slotmove action:
    # 1) move package slot
    # 2) update all the dependencies in dependenciesreference owning
    #    same matched atom + slot
    # 3) run fixpackages which will update /var/db/pkg files
    # 4) automatically run quickpkg() to build the new
    #    binary and tainted binaries owning tainted iddependency
    #    and taint database
    def runTreeUpdatesSlotmoveAction(self, slotmove_command, quickpkg_queue):

        atom = slotmove_command[0]
        atomkey = self.entropyTools.dep_getkey(atom)
        slot_from = slotmove_command[1]
        slot_to = slotmove_command[2]
        matches = self.atomMatch(atom, multiMatch = True)
        iddependencies = set()

        if matches[1] == 0:

            matched_idpackages = matches[0]
            for idpackage in matched_idpackages:

                ### UPDATE DATABASE
                # update slot
                self.setSlot(idpackage, slot_to)

                # look for packages we need to quickpkg again
                # note: quickpkg_queue is simply ignored if self.clientDatabase
                quickpkg_queue.add(atom+":"+str(slot_to))

                if not self.clientDatabase:

                    # check for injection and warn the developer
                    injected = self.isInjected(idpackage)
                    if injected:
                        mytxt = "%s: %s %s. %s !!! %s." % (
                            bold(_("INJECT")),
                            blue(str(atom)),
                            red(_("has been injected")),
                            red(_("quickpkg manually to update embedded db")),
                            red(_("Repository database updated anyway")),
                        )
                        self.updateProgress(
                            mytxt,
                            importance = 1,
                            type = "warning",
                            header = darkred(" * ")
                        )

            # only if we've found VALID matches !
            iddeps = self.searchDependency(atomkey, like = True, multi = True)
            for iddep in iddeps:
                # update string
                mydep = self.retrieveDependencyFromIddependency(iddep)
                mydep_key = self.entropyTools.dep_getkey(mydep)
                if mydep_key != atomkey:
                    continue
                if not mydep.endswith(":"+slot_from): # probably slotted dep
                    continue
                mydep_match = self.atomMatch(mydep)
                if mydep_match not in matched_idpackages:
                    continue
                mydep = mydep.replace(":"+slot_from, ":"+slot_to)
                # now update
                # dependstable on server is always re-generated
                self.setDependency(iddep, mydep)
                # we have to repackage also package owning this iddep
                iddependencies |= self.searchIdpackageFromIddependency(iddep)

        self.commitChanges()
        for idpackage_owner in iddependencies:
            myatom = self.retrieveAtom(idpackage_owner)
            quickpkg_queue.add(myatom)
        return quickpkg_queue

    def runTreeUpdatesQuickpkgAction(self, atoms):

        self.commitChanges()

        package_paths = set()
        runatoms = set()
        for myatom in atoms:
            mymatch = self.atomMatch(myatom)
            if mymatch[0] == -1:
                continue
            myatom = self.retrieveAtom(mymatch[0])
            runatoms.add(myatom)

        for myatom in runatoms:
            self.updateProgress(
                red("%s: " % (_("repackaging"),) )+blue(myatom),
                importance = 1,
                type = "warning",
                header = blue("  # ")
            )
            mydest = self.ServiceInterface.get_local_store_directory(
                repo = self.server_repo)
            try:
                mypath = self.ServiceInterface.quickpkg(myatom, mydest)
            except:
                # remove broken bin before raising
                mypath = os.path.join(mydest,
                    os.path.basename(myatom)+etpConst['packagesext'])
                if os.path.isfile(mypath):
                    os.remove(mypath)
                self.entropyTools.print_traceback()
                mytxt = "%s: %s: %s, %s." % (
                    bold(_("WARNING")),
                    red(_("Cannot complete quickpkg for atom")),
                    blue(myatom),
                    _("do it manually"),
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = darkred(" * ")
                )
                continue
            package_paths.add(mypath)
        packages_data = [(x, False,) for x in package_paths]
        idpackages = self.ServiceInterface.add_packages_to_repository(
            packages_data, repo = self.server_repo)

        if not idpackages:

            mytxt = "%s: %s. %s." % (
                bold(_("ATTENTION")),
                red(_("runTreeUpdatesQuickpkgAction did not run properly")),
                red(_("Please update packages manually")),
            )
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = darkred(" * ")
            )

    def doTreeupdatesSpmCleanup(self, spm_moves):

        # now erase Spm entries if necessary
        for action in spm_moves:
            command = action.split()
            if len(command) < 2:
                continue
            key = command[1]
            name = key.split("/")[1]
            if self.clientDatabase:
                try:
                    spm = self.ServiceInterface.Spm()
                except:
                    continue
            else:
                spm = self.ServiceInterface.SpmService
            vdb_path = spm.get_vdb_path()
            pkg_path = os.path.join(vdb_path, key.split("/")[0])
            try:
                mydirs = [os.path.join(pkg_path, x) for x in \
                    os.listdir(pkg_path) if x.startswith(name)]
            except OSError: # no dir, no party!
                continue
            mydirs = [x for x in mydirs if os.path.isdir(x)]
            # now move these dirs
            for mydir in mydirs:
                to_path = os.path.join(etpConst['packagestmpdir'],
                    os.path.basename(mydir))
                mytxt = "%s: %s '%s' %s '%s'" % (
                    bold(_("SPM")),
                    red(_("Moving old entry")),
                    blue(mydir),
                    red(_("to")),
                    blue(to_path),
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = darkred(" * ")
                )
                if os.path.isdir(to_path):
                    shutil.rmtree(to_path, True)
                    try:
                        os.rmdir(to_path)
                    except OSError:
                        pass
                shutil.move(mydir, to_path)


    def handlePackage(self, etpData, forcedRevision = -1,
        formattedContent = False):

        self.checkReadOnly()

        if self.clientDatabase:
            return self.addPackage(etpData, revision = forcedRevision,
                formatted_content = formattedContent)

        # build atom string, server side
        pkgatom = self.entropyTools.create_package_atom_string(
            etpData['category'], etpData['name'], etpData['version'],
            etpData['versiontag'])
        foundid = self.isPackageAvailable(pkgatom)
        if foundid < 0: # same atom doesn't exist in any branch
            return self.addPackage(etpData, revision = forcedRevision,
                formatted_content = formattedContent)

        idpackage = self.getIDPackage(pkgatom)
        curRevision = forcedRevision
        if forcedRevision == -1:
            curRevision = 0
            if idpackage != -1:
                curRevision = self.retrieveRevision(idpackage)

        # remove old package atom, we do it here because othersie
        if idpackage != -1:
            # injected packages wouldn't be removed by addPackages
            self.removePackage(idpackage)
            if forcedRevision == -1: curRevision += 1

        # add the new one
        return self.addPackage(etpData, revision = curRevision,
            formatted_content = formattedContent)

    def retrieve_packages_to_remove(self, name, category, slot, injected):

        removelist = set()

        # support for expiration-based packages handling, also internally
        # called Fat Scope.
        filter_similar = False
        srv_ss_plg = etpConst['system_settings_plugins_ids']['server_plugin']
        srv_ss_fs_plg = \
            etpConst['system_settings_plugins_ids']['server_plugin_fatscope']

        if not self.clientDatabase: # server-side db
            srv_plug_settings = self.SystemSettings.get(srv_ss_plg)
            if srv_plug_settings != None:
                if srv_plug_settings['server']['exp_based_scope']:
                    # in case support is enabled, return an empty set
                    filter_similar = True

        searchsimilar = self.searchPackagesByNameAndCategory(
            name = name,
            category = category,
            sensitive = True
        )
        if filter_similar:
            # filter out packages in the same scope that are allowed to stay
            idpkgs = self.SystemSettings[srv_ss_fs_plg]['repos'].get(
                self.server_repo)
            if idpkgs:
                if -1 in idpkgs:
                    del searchsimilar[:]
                else:
                    searchsimilar = [x for x in searchsimilar if x[1] \
                        not in idpkgs]

        if not injected:
            # read: if package has been injected, we'll skip
            # the removal of packages in the same slot,
            # usually used server side btw
            for atom, idpackage in searchsimilar:
                # get the package slot
                myslot = self.retrieveSlot(idpackage)
                # we merely ignore packages with
                # negative counters, since they're the injected ones
                if self.isInjected(idpackage): continue
                if slot == myslot:
                    # remove!
                    removelist.add(idpackage)

        return removelist

    def addPackage(self, etpData, revision = -1, idpackage = None,
        do_remove = True, do_commit = True, formatted_content = False):

        self.checkReadOnly()

        if revision == -1:
            try:
                revision = int(etpData['revision'])
            except (KeyError, ValueError):
                etpData['revision'] = 0 # revision not specified
                revision = 0
        elif not etpData.has_key('revision'):
            etpData['revision'] = revision

        manual_deps = set()
        if do_remove:
            removelist = self.retrieve_packages_to_remove(
                            etpData['name'],
                            etpData['category'],
                            etpData['slot'],
                            etpData['injected']
            )
            for r_idpackage in removelist:
                manual_deps |= self.retrieveManualDependencies(r_idpackage)
                self.removePackage(r_idpackage, do_cleanup = False,
                    do_commit = False)

        # create new category if it doesn't exist
        catid = self.isCategoryAvailable(etpData['category'])
        if catid == -1: catid = self.addCategory(etpData['category'])

        # create new license if it doesn't exist
        licid = self.isLicenseAvailable(etpData['license'])
        if licid == -1: licid = self.addLicense(etpData['license'])

        idprotect = self.isProtectAvailable(etpData['config_protect'])
        if idprotect == -1: idprotect = self.addProtect(
            etpData['config_protect'])

        idprotect_mask = self.isProtectAvailable(
            etpData['config_protect_mask'])
        if idprotect_mask == -1: idprotect_mask = self.addProtect(
            etpData['config_protect_mask'])

        idflags = self.areCompileFlagsAvailable(
            etpData['chost'],etpData['cflags'],etpData['cxxflags'])
        if idflags == -1: idflags = self.addCompileFlags(
            etpData['chost'],etpData['cflags'],etpData['cxxflags'])


        trigger = 0
        if etpData['trigger']:
            trigger = 1

        # baseinfo
        pkgatom = self.entropyTools.create_package_atom_string(
            etpData['category'], etpData['name'], etpData['version'],
            etpData['versiontag'])
        # add atom metadatum
        etpData['atom'] = pkgatom

        mybaseinfo_data = (pkgatom, catid, etpData['name'], etpData['version'],
            etpData['versiontag'], revision, etpData['branch'], etpData['slot'],
            licid, etpData['etpapi'], trigger,)

        myidpackage_string = 'NULL'
        if isinstance(idpackage, int):
            manual_deps |= self.retrieveManualDependencies(idpackage)
            # does it exist?
            self.removePackage(idpackage, do_cleanup = False,
                do_commit = False, do_rss = False)
            myidpackage_string = '?'
            mybaseinfo_data = (idpackage,)+mybaseinfo_data
        else:
            idpackage = None

        # merge old manual dependencies
        for manual_dep in manual_deps:
            if manual_dep in etpData['dependencies']: continue
            etpData['dependencies'][manual_dep] = etpConst['spm']['mdepend_id']

        with self.WriteLock:

            self.cursor.execute("""
            INSERT into baseinfo VALUES (%s,?,?,?,?,?,?,?,?,?,?,?)""" % (
                myidpackage_string,), mybaseinfo_data)
            if idpackage == None:
                idpackage = self.cursor.lastrowid

            # extrainfo
            self.cursor.execute(
                'INSERT into extrainfo VALUES (?,?,?,?,?,?,?,?)',
                (   idpackage,
                    etpData['description'],
                    etpData['homepage'],
                    etpData['download'],
                    etpData['size'],
                    idflags,
                    etpData['digest'],
                    etpData['datecreation'],
                )
            )
        ### other information iserted below are not as critical as these above

        # tables using a select
        self.insertEclasses(idpackage, etpData['eclasses'])
        self.insertNeeded(idpackage, etpData['needed'])
        self.insertDependencies(idpackage, etpData['dependencies'])
        self.insertSources(idpackage, etpData['sources'])
        self.insertUseflags(idpackage, etpData['useflags'])
        self.insertKeywords(idpackage, etpData['keywords'])
        self.insertLicenses(etpData['licensedata'])
        self.insertMirrors(etpData['mirrorlinks'])
        # package ChangeLog
        if etpData.get('changelog'):
            self.insertChangelog(etpData['category'], etpData['name'],
                etpData['changelog'])
        # package signatures
        if etpData.get('signatures'):
            self.insertSignatures(idpackage, etpData['signatures'])

        # spm phases
        if etpData.get('spm_phases') != None:
            self.insertSpmPhases(idpackage, etpData['spm_phases'])

        # not depending on other tables == no select done
        self.insertContent(idpackage, etpData['content'],
            already_formatted = formatted_content)
        etpData['counter'] = int(etpData['counter']) # cast to integer
        etpData['counter'] = self.insertPortageCounter(
                                idpackage,
                                etpData['counter'],
                                etpData['branch'],
                                etpData['injected']
        )
        self.insertOnDiskSize(idpackage, etpData['disksize'])
        if etpData['trigger']:
            self.insertTrigger(idpackage, etpData['trigger'])
        self.insertConflicts(idpackage, etpData['conflicts'])
        self.insertProvide(idpackage, etpData['provide'])
        self.insertMessages(idpackage, etpData['messages'])
        self.insertConfigProtect(idpackage, idprotect)
        self.insertConfigProtect(idpackage, idprotect_mask, mask = True)
        # injected?
        if etpData.get('injected'):
            self.setInjected(idpackage, do_commit = False)
        # is it a system package?
        if etpData.get('systempackage'):
            self.setSystemPackage(idpackage, do_commit = False)

        self.clearCache() # we do live_cache.clear() here too
        if do_commit:
            self.commitChanges()

        ### RSS Atom support
        ### dictionary will be elaborated by activator
        if self.SystemSettings.has_key(self.srv_sys_settings_plugin):
            if self.SystemSettings[self.srv_sys_settings_plugin]['server']['rss']['enabled'] and \
                not self.clientDatabase:

                self._write_rss_for_added_package(pkgatom, revision,
                    etpData['description'], etpData['homepage'])

        # Update category description
        if not self.clientDatabase:
            mycategory = etpData['category']
            descdata = {}
            try:
                descdata = self.get_category_description_from_disk(mycategory)
            except (IOError, OSError, EOFError,):
                pass
            if descdata:
                self.setCategoryDescription(mycategory, descdata)

        return idpackage, revision, etpData

    def _write_rss_for_added_package(self, pkgatom, revision, description,
        homepage):

        rssAtom = pkgatom+"~"+str(revision)
        rssObj = self.dumpTools.loadobj(etpConst['rss-dump-name'])
        if rssObj: self.ServiceInterface.rssMessages = rssObj.copy()
        if not isinstance(self.ServiceInterface.rssMessages, dict):
            self.ServiceInterface.rssMessages = {}
        if not self.ServiceInterface.rssMessages.has_key('added'):
            self.ServiceInterface.rssMessages['added'] = {}
        if not self.ServiceInterface.rssMessages.has_key('removed'):
            self.ServiceInterface.rssMessages['removed'] = {}
        if rssAtom in self.ServiceInterface.rssMessages['removed']:
            del self.ServiceInterface.rssMessages['removed'][rssAtom]

        self.ServiceInterface.rssMessages['added'][rssAtom] = {}
        self.ServiceInterface.rssMessages['added'][rssAtom]['description'] = \
            description
        self.ServiceInterface.rssMessages['added'][rssAtom]['homepage'] = \
            homepage
        self.ServiceInterface.rssMessages['light'][rssAtom] = {}
        self.ServiceInterface.rssMessages['light'][rssAtom]['description'] = \
            description
        self.dumpTools.dumpobj(etpConst['rss-dump-name'],
            self.ServiceInterface.rssMessages)

    def _write_rss_for_removed_package(self, idpackage):

        rssObj = self.dumpTools.loadobj(etpConst['rss-dump-name'])
        if rssObj: self.ServiceInterface.rssMessages = rssObj.copy()
        rssAtom = self.retrieveAtom(idpackage)
        rssRevision = self.retrieveRevision(idpackage)
        rssAtom += "~"+str(rssRevision)
        if not isinstance(self.ServiceInterface.rssMessages, dict):
            self.ServiceInterface.rssMessages = {}
        if not self.ServiceInterface.rssMessages.has_key('added'):
            self.ServiceInterface.rssMessages['added'] = {}
        if not self.ServiceInterface.rssMessages.has_key('removed'):
            self.ServiceInterface.rssMessages['removed'] = {}
        if rssAtom in self.ServiceInterface.rssMessages['added']:
            del self.ServiceInterface.rssMessages['added'][rssAtom]

        mydict = {}
        try:
            mydict['description'] = self.retrieveDescription(idpackage)
        except TypeError:
            mydict['description'] = "N/A"
        try:
            mydict['homepage'] = self.retrieveHomepage(idpackage)
        except TypeError:
            mydict['homepage'] = ""

        self.dumpTools.dumpobj(etpConst['rss-dump-name'],
            self.ServiceInterface.rssMessages)

        self.ServiceInterface.rssMessages['removed'][rssAtom] = mydict

    def removePackage(self, idpackage, do_cleanup = True, do_commit = True,
        do_rss = True):

        self.checkReadOnly()
        # clear caches
        self.clearCache()

        ### RSS Atom support
        ### dictionary will be elaborated by activator
        if self.SystemSettings.has_key(self.srv_sys_settings_plugin):
            if self.SystemSettings[self.srv_sys_settings_plugin]['server']['rss']['enabled'] and \
                (not self.clientDatabase) and do_rss:

                # store addPackage action
                self._write_rss_for_removed_package(idpackage)

        with self.WriteLock:

            r_tup = (idpackage,)*20
            self.cursor.executescript("""
                DELETE FROM baseinfo WHERE idpackage = %d;
                DELETE FROM extrainfo WHERE idpackage = %d;
                DELETE FROM dependencies WHERE idpackage = %d;
                DELETE FROM provide WHERE idpackage = %d;
                DELETE FROM conflicts WHERE idpackage = %d;
                DELETE FROM configprotect WHERE idpackage = %d;
                DELETE FROM configprotectmask WHERE idpackage = %d;
                DELETE FROM sources WHERE idpackage = %d;
                DELETE FROM useflags WHERE idpackage = %d;
                DELETE FROM keywords WHERE idpackage = %d;
                DELETE FROM content WHERE idpackage = %d;
                DELETE FROM messages WHERE idpackage = %d;
                DELETE FROM counters WHERE idpackage = %d;
                DELETE FROM sizes WHERE idpackage = %d;
                DELETE FROM eclasses WHERE idpackage = %d;
                DELETE FROM needed WHERE idpackage = %d;
                DELETE FROM triggers WHERE idpackage = %d;
                DELETE FROM systempackages WHERE idpackage = %d;
                DELETE FROM injected WHERE idpackage = %d;
                DELETE FROM installedtable WHERE idpackage = %d;
            """ % r_tup)

        # not yet possible to add these calls above
        try:
            self.removeAutomergefiles(idpackage)
        except self.dbapi2.OperationalError:
            pass
        try:
            self.removeSignatures(idpackage)
        except self.dbapi2.OperationalError:
            pass
        try:
            self.removeSpmPhases(idpackage)
        except self.dbapi2.OperationalError:
            pass

        # Remove from dependstable if exists
        self.removePackageFromDependsTable(idpackage)

        if do_cleanup:
            # Cleanups if at least one package has been removed
            self.doCleanups()

        if do_commit:
            self.commitChanges()

    def removeMirrorEntries(self, mirrorname):
        with self.WriteLock:
            self.cursor.execute("""
            DELETE FROM mirrorlinks WHERE mirrorname = (?)
            """,(mirrorname,))

    def addMirrors(self, mirrorname, mirrorlist):
        with self.WriteLock:
            data = [(mirrorname, x,) for x in mirrorlist]
            self.cursor.executemany("""
            INSERT into mirrorlinks VALUES (?,?)
            """, data)

    def addCategory(self, category):
        with self.WriteLock:
            self.cursor.execute("""
            INSERT into categories VALUES (NULL,?)
            """, (category,))
            return self.cursor.lastrowid

    def addProtect(self, protect):
        with self.WriteLock:
            self.cursor.execute("""
            INSERT into configprotectreference VALUES (NULL,?)
            """, (protect,))
            return self.cursor.lastrowid


    def addSource(self, source):
        with self.WriteLock:
            self.cursor.execute("""
            INSERT into sourcesreference VALUES (NULL,?)
            """, (source,))
            return self.cursor.lastrowid

    def addDependency(self, dependency):
        with self.WriteLock:
            self.cursor.execute('INSERT into dependenciesreference VALUES (NULL,?)', (dependency,))
            return self.cursor.lastrowid

    def addKeyword(self, keyword):
        with self.WriteLock:
            self.cursor.execute('INSERT into keywordsreference VALUES (NULL,?)', (keyword,))
            return self.cursor.lastrowid

    def addUseflag(self, useflag):
        with self.WriteLock:
            self.cursor.execute('INSERT into useflagsreference VALUES (NULL,?)', (useflag,))
            return self.cursor.lastrowid

    def addEclass(self, eclass):
        with self.WriteLock:
            self.cursor.execute('INSERT into eclassesreference VALUES (NULL,?)', (eclass,))
            return self.cursor.lastrowid

    def addNeeded(self, needed):
        with self.WriteLock:
            self.cursor.execute('INSERT into neededreference VALUES (NULL,?)', (needed,))
            return self.cursor.lastrowid

    def addLicense(self, pkglicense):
        if not self.entropyTools.is_valid_string(pkglicense):
            pkglicense = ' ' # workaround for broken license entries
        with self.WriteLock:
            self.cursor.execute('INSERT into licenses VALUES (NULL,?)', (pkglicense,))
            return self.cursor.lastrowid

    def addCompileFlags(self, chost, cflags, cxxflags):
        with self.WriteLock:
            self.cursor.execute('INSERT into flags VALUES (NULL,?,?,?)', (chost,cflags,cxxflags,))
            return self.cursor.lastrowid

    def setSystemPackage(self, idpackage, do_commit = True):
        with self.WriteLock:
            self.cursor.execute('INSERT into systempackages VALUES (?)', (idpackage,))
            if do_commit:
                self.commitChanges()

    def setInjected(self, idpackage, do_commit = True):
        with self.WriteLock:
            if not self.isInjected(idpackage):
                self.cursor.execute('INSERT into injected VALUES (?)', (idpackage,))
            if do_commit:
                self.commitChanges()

    # date expressed the unix way
    def setDateCreation(self, idpackage, date):
        with self.WriteLock:
            self.cursor.execute('UPDATE extrainfo SET datecreation = (?) WHERE idpackage = (?)', (str(date), idpackage,))
            self.commitChanges()

    def setDigest(self, idpackage, digest):
        with self.WriteLock:
            self.cursor.execute('UPDATE extrainfo SET digest = (?) WHERE idpackage = (?)', (digest, idpackage,))
            self.commitChanges()

    def setSignatures(self, idpackage, signatures):
        with self.WriteLock:
            sha1, sha256, sha512 = signatures['sha1'], signatures['sha256'], \
                signatures['sha512']
            self.cursor.execute("""
            UPDATE packagesignatures SET sha1 = (?), sha256 = (?), sha512 = (?)
            WHERE idpackage = (?)
            """, (sha1, sha256, sha512, idpackage))

    def setDownloadURL(self, idpackage, url):
        with self.WriteLock:
            self.cursor.execute('UPDATE extrainfo SET download = (?) WHERE idpackage = (?)', (url, idpackage,))
            self.commitChanges()

    def setCategory(self, idpackage, category):
        # create new category if it doesn't exist
        catid = self.isCategoryAvailable(category)
        if (catid == -1):
            # create category
            catid = self.addCategory(category)
        with self.WriteLock:
            self.cursor.execute('UPDATE baseinfo SET idcategory = (?) WHERE idpackage = (?)', (catid, idpackage,))
            self.commitChanges()

    def setCategoryDescription(self, category, description_data):
        with self.WriteLock:
            self.cursor.execute('DELETE FROM categoriesdescription WHERE category = (?)', (category,))
            for locale in description_data:
                mydesc = description_data[locale]
                #if type(mydesc) is unicode:
                #    mydesc = mydesc.encode('raw_unicode_escape')
                self.cursor.execute('INSERT INTO categoriesdescription VALUES (?,?,?)', (category, locale, mydesc,))
            self.commitChanges()

    def setName(self, idpackage, name):
        with self.WriteLock:
            self.cursor.execute('UPDATE baseinfo SET name = (?) WHERE idpackage = (?)', (name, idpackage,))
            self.commitChanges()

    def setDependency(self, iddependency, dependency):
        with self.WriteLock:
            self.cursor.execute('UPDATE dependenciesreference SET dependency = (?) WHERE iddependency = (?)', (dependency, iddependency,))
            self.commitChanges()

    def setAtom(self, idpackage, atom):
        with self.WriteLock:
            self.cursor.execute('UPDATE baseinfo SET atom = (?) WHERE idpackage = (?)', (atom, idpackage,))
            self.commitChanges()

    def setSlot(self, idpackage, slot):
        with self.WriteLock:
            self.cursor.execute('UPDATE baseinfo SET slot = (?) WHERE idpackage = (?)', (slot, idpackage,))
            self.commitChanges()

    def removeLicensedata(self, license_name):
        if not self.doesTableExist("licensedata"):
            return
        with self.WriteLock:
            self.cursor.execute('DELETE FROM licensedata WHERE licensename = (?)', (license_name,))

    def removeDependencies(self, idpackage):
        with self.WriteLock:
            self.cursor.execute("DELETE FROM dependencies WHERE idpackage = (?)", (idpackage,))
            self.commitChanges()

    def insertDependencies(self, idpackage, depdata):

        dcache = set()
        add_dep = self.addDependency
        is_dep_avail = self.isDependencyAvailable
        def mymf(dep):

            if dep in dcache: return 0
            iddep = is_dep_avail(dep)
            if iddep == -1: iddep = add_dep(dep)

            deptype = 0
            if isinstance(depdata, dict):
                deptype = depdata[dep]

            dcache.add(dep)
            return (idpackage, iddep, deptype,)

        # do not place inside the with statement, otherwise there'll be an obvious lockup
        deps = [x for x in map(mymf, depdata) if type(x) != int]
        with self.WriteLock:
            self.cursor.executemany('INSERT into dependencies VALUES (?,?,?)', deps)

    def insertManualDependencies(self, idpackage, manual_deps):
        mydict = {}
        for manual_dep in manual_deps:
            mydict[manual_dep] = etpConst['spm']['mdepend_id']
        return self.insertDependencies(idpackage, mydict)

    def removeContent(self, idpackage):
        with self.WriteLock:
            self.cursor.execute("DELETE FROM content WHERE idpackage = (?)", (idpackage,))
            self.commitChanges()

    def insertContent(self, idpackage, content, already_formatted = False):

        with self.WriteLock:
            if already_formatted:
                self.cursor.executemany('INSERT INTO content VALUES (?,?,?)',((idpackage, x, y,) for a, x, y in content))
                return
            def my_cmap(xfile):
                return (idpackage, xfile, content[xfile],)
            self.cursor.executemany('INSERT INTO content VALUES (?,?,?)',map(my_cmap, content))

    def insertAutomergefiles(self, idpackage, automerge_data):
        with self.WriteLock:
            self.cursor.executemany('INSERT INTO automergefiles VALUES (?,?,?)',
                ((idpackage, x, y,) for x, y in automerge_data))

    def removeAutomergefiles(self, idpackage):
        with self.WriteLock:
            self.cursor.execute('DELETE FROM automergefiles WHERE idpackage = (?)', (idpackage,))

    def removeSignatures(self, idpackage):
        with self.WriteLock:
            self.cursor.execute('DELETE FROM packagesignatures WHERE idpackage = (?)', (idpackage,))

    def removeSpmPhases(self, idpackage):
        with self.WriteLock:
            self.cursor.execute('DELETE FROM packagespmphases WHERE idpackage = (?)', (idpackage,))

    def insertChangelog(self, category, name, changelog_txt):
        with self.WriteLock:
            mytxt = changelog_txt.encode('raw_unicode_escape')
            self.cursor.execute('DELETE FROM packagechangelogs WHERE category = (?) AND name = (?)', (category, name,))
            self.cursor.execute('INSERT INTO packagechangelogs VALUES (?,?,?)', (category, name, buffer(mytxt),))

    def removeChangelog(self, category, name):
        with self.WriteLock:
            self.cursor.execute('DELETE FROM packagechangelogs WHERE category = (?) AND name = (?)', (category, name,))

    def insertLicenses(self, licenses_data):

        mylicenses = licenses_data.keys()
        is_lic_avail = self.isLicensedataKeyAvailable
        def my_mf(mylicense):
            return not is_lic_avail(mylicense)

        def my_mm(mylicense):
            lic_data = licenses_data.get(mylicense,u'')
            try:
                # support both utf8 and str input
                if isinstance(lic_data, unicode):
                    lic_data = lic_data.encode('raw_unicode_escape')
            except UnicodeDecodeError:
                lic_data = lic_data.encode('utf-8')
            return (mylicense, buffer(lic_data), 0,)

        with self.WriteLock:
            self.cursor.executemany('INSERT into licensedata VALUES (?,?,?)',map(my_mm, list(set(filter(my_mf, mylicenses)))))

    def insertConfigProtect(self, idpackage, idprotect, mask = False):

        mytable = 'configprotect'
        if mask: mytable += 'mask'
        with self.WriteLock:
            self.cursor.execute('INSERT into %s VALUES (?,?)' % (mytable,), (idpackage, idprotect,))

    def insertMirrors(self, mirrors):

        for mirrorname, mirrorlist in mirrors:
            # remove old
            self.removeMirrorEntries(mirrorname)
            # add new
            self.addMirrors(mirrorname, mirrorlist)

    def insertKeywords(self, idpackage, keywords):

        mydata = set()
        for key in keywords:
            idkeyword = self.isKeywordAvailable(key)
            if (idkeyword == -1):
                # create category
                idkeyword = self.addKeyword(key)
            mydata.add((idpackage, idkeyword,))

        with self.WriteLock:
            self.cursor.executemany('INSERT into keywords VALUES (?,?)', mydata)

    def insertUseflags(self, idpackage, useflags):

        mydata = set()
        for flag in useflags:
            iduseflag = self.isUseflagAvailable(flag)
            if (iduseflag == -1):
                # create category
                iduseflag = self.addUseflag(flag)
            mydata.add((idpackage, iduseflag,))

        with self.WriteLock:
            self.cursor.executemany('INSERT into useflags VALUES (?,?)', mydata)

    def insertSignatures(self, idpackage, signatures):
        with self.WriteLock:
            sha1, sha256, sha512 = signatures['sha1'], signatures['sha256'], \
                signatures['sha512']
            self.cursor.execute("""
            INSERT INTO packagesignatures VALUES (?,?,?,?)
            """, (idpackage, sha1, sha256, sha512))

    def insertSpmPhases(self, idpackage, phases):
        with self.WriteLock:
            self.cursor.execute("""
            INSERT INTO packagespmphases VALUES (?,?)
            """, (idpackage,phases,))

    def insertSources(self, idpackage, sources):

        mydata = set()
        for source in sources:
            if (not source) or (source == "") or (not self.entropyTools.is_valid_string(source)):
                continue
            idsource = self.isSourceAvailable(source)
            if (idsource == -1):
                # create category
                idsource = self.addSource(source)
            mydata.add((idpackage, idsource,))

        with self.WriteLock:
            self.cursor.executemany('INSERT into sources VALUES (?,?)', mydata)

    def insertConflicts(self, idpackage, conflicts):

        def myiter():
            for conflict in conflicts:
                yield (idpackage, conflict,)

        with self.WriteLock:
            self.cursor.executemany('INSERT into conflicts VALUES (?,?)', myiter())

    def insertMessages(self, idpackage, messages):

        def myiter():
            for message in messages:
                yield (idpackage, message,)

        with self.WriteLock:
            self.cursor.executemany('INSERT into messages VALUES (?,?)', myiter())

    def insertProvide(self, idpackage, provides):

        def myiter():
            for atom in provides:
                yield (idpackage, atom,)

        with self.WriteLock:
            self.cursor.executemany('INSERT into provide VALUES (?,?)', myiter())

    def insertNeeded(self, idpackage, neededs):

        mydata = set()
        for needed, elfclass in neededs:
            idneeded = self.isNeededAvailable(needed)
            if idneeded == -1:
                # create eclass
                idneeded = self.addNeeded(needed)
            mydata.add((idpackage, idneeded, elfclass))

        with self.WriteLock:
            self.cursor.executemany('INSERT into needed VALUES (?,?,?)', mydata)

    def insertEclasses(self, idpackage, eclasses):

        mydata = set()
        for eclass in eclasses:
            idclass = self.isEclassAvailable(eclass)
            if (idclass == -1):
                # create eclass
                idclass = self.addEclass(eclass)
            mydata.add((idpackage, idclass,))

        with self.WriteLock:
            self.cursor.executemany('INSERT into eclasses VALUES (?,?)', mydata)

    def insertOnDiskSize(self, idpackage, mysize):
        with self.WriteLock:
            self.cursor.execute('INSERT into sizes VALUES (?,?)', (idpackage, mysize,))

    def insertTrigger(self, idpackage, trigger):
        with self.WriteLock:
            self.cursor.execute('INSERT into triggers VALUES (?,?)', (idpackage, buffer(trigger),))

    def insertPortageCounter(self, idpackage, counter, branch, injected):

        if (counter != -1) and not injected:

            if counter <= -2:
                # special cases
                counter = self.getNewNegativeCounter()

            with self.WriteLock:
                try:
                    self.cursor.execute(
                    'INSERT into counters VALUES '
                    '(?,?,?)'
                    , ( counter,
                        idpackage,
                        branch,
                        )
                    )
                except self.dbapi2.IntegrityError: # we have a PRIMARY KEY we need to remove
                    self._migrateCountersTable()
                    self.cursor.execute(
                    'INSERT into counters VALUES '
                    '(?,?,?)'
                    , ( counter,
                        idpackage,
                        branch,
                        )
                    )
                except:
                    if self.dbname == etpConst['clientdbid']: # force only for client database
                        if self.doesTableExist("counters"):
                            raise
                        self.cursor.execute(
                        'INSERT into counters VALUES '
                        '(?,?,?)'
                        , ( counter,
                            idpackage,
                            branch,
                            )
                        )
                    elif self.dbname.startswith(etpConst['serverdbid']):
                        raise

        return counter

    def insertCounter(self, idpackage, counter, branch = None):
        if not branch: branch = self.db_branch
        if not branch: branch = self.SystemSettings['repositories']['branch']
        with self.WriteLock:
            self.cursor.execute("""
            DELETE FROM counters 
            WHERE (counter = (?) OR 
            idpackage = (?)) AND 
            branch = (?)""", (counter, idpackage, branch,))
            self.cursor.execute('INSERT INTO counters VALUES (?,?,?)', (counter, idpackage, branch,))
            self.commitChanges()

    def setTrashedCounter(self, counter):
        with self.WriteLock:
            self.cursor.execute('DELETE FROM trashedcounters WHERE counter = (?)', (counter,))
            self.cursor.execute('INSERT INTO trashedcounters VALUES (?)', (counter,))
            self.commitChanges()


    def setCounter(self, idpackage, counter, branch = None):

        branchstring = ''
        insertdata = [counter, idpackage]
        if branch:
            branchstring = ', branch = (?)'
            insertdata.insert(1, branch)

        with self.WriteLock:
            try:
                self.cursor.execute('UPDATE counters SET counter = (?) '+branchstring+' WHERE idpackage = (?)', insertdata)
                self.commitChanges()
            except:
                if self.dbname == etpConst['clientdbid']:
                    raise

    def contentDiff(self, idpackage, dbconn, dbconn_idpackage):
        self.connection.text_factory = lambda x: unicode(x, "raw_unicode_escape")
        # create a random table and fill
        randomtable = "cdiff%s" % (self.entropyTools.get_random_number(),)
        while self.doesTableExist(randomtable):
            randomtable = "cdiff%s" % (self.entropyTools.get_random_number(),)
        self.cursor.execute('CREATE TEMPORARY TABLE %s ( file VARCHAR )' % (randomtable,))

        try:
            dbconn.connection.text_factory = lambda x: unicode(x, "raw_unicode_escape")
            dbconn.cursor.execute('select file from content where idpackage = (?)', (dbconn_idpackage,))
            xfile = dbconn.cursor.fetchone()
            while xfile:
                self.cursor.execute('INSERT INTO %s VALUES (?)' % (randomtable,), (xfile[0],))
                xfile = dbconn.cursor.fetchone()

            # now compare
            self.cursor.execute("""
            SELECT file FROM content 
            WHERE content.idpackage = (?) AND 
            content.file NOT IN (SELECT file from %s)""" % (randomtable,), (idpackage,))
            diff = self.fetchall2set(self.cursor.fetchall())
            return diff
        finally:
            self.cursor.execute('DROP TABLE IF EXISTS %s' % (randomtable,))

    def doCleanups(self):
        self.cleanupUseflags()
        self.cleanupSources()
        self.cleanupEclasses()
        self.cleanupNeeded()
        self.cleanupDependencies()
        self.cleanupChangelogs()

    def cleanupUseflags(self):
        with self.WriteLock:
            self.cursor.execute("""
            DELETE FROM useflagsreference 
            WHERE idflag NOT IN (SELECT idflag FROM useflags)""")

    def cleanupSources(self):
        with self.WriteLock:
            self.cursor.execute("""
            DELETE FROM sourcesreference 
            WHERE idsource NOT IN (SELECT idsource FROM sources)""")

    def cleanupEclasses(self):
        with self.WriteLock:
            self.cursor.execute("""
            DELETE FROM eclassesreference 
            WHERE idclass NOT IN (SELECT idclass FROM eclasses)""")

    def cleanupNeeded(self):
        with self.WriteLock:
            self.cursor.execute("""
            DELETE FROM neededreference 
            WHERE idneeded NOT IN (SELECT idneeded FROM needed)""")

    def cleanupDependencies(self):
        with self.WriteLock:
            self.cursor.execute("""
            DELETE FROM dependenciesreference 
            WHERE iddependency NOT IN (SELECT iddependency FROM dependencies)""")

    def cleanupChangelogs(self):
        with self.WriteLock:
            self.cursor.execute("""
            DELETE FROM packagechangelogs 
            WHERE category || "/" || name NOT IN 
            (SELECT categories.category || "/" || baseinfo.name FROM baseinfo,categories 
                WHERE baseinfo.idcategory = categories.idcategory
            )""")

    def getNewNegativeCounter(self):
        counter = -2
        try:
            self.cursor.execute('SELECT min(counter) FROM counters')
            dbcounter = self.cursor.fetchone()
            mycounter = 0
            if dbcounter:
                mycounter = dbcounter[0]

            if mycounter >= -1:
                counter = -2
            else:
                counter = mycounter-1

        except:
            pass
        return counter

    def getApi(self):
        self.cursor.execute('SELECT max(etpapi) FROM baseinfo')
        api = self.cursor.fetchone()
        if api: api = api[0]
        else: api = -1
        return api

    def getCategory(self, idcategory):
        self.cursor.execute('SELECT category from categories WHERE idcategory = (?)', (idcategory,))
        cat = self.cursor.fetchone()
        if cat: cat = cat[0]
        return cat

    def get_category_description_from_disk(self, category):
        if not self.ServiceInterface:
            return {}
        return self.ServiceInterface.SpmService.get_category_description_data(category)

    def getIDPackage(self, atom, branch = None):
        branch_string = ''
        params = [atom]
        if branch:
            branch_string = ' AND branch = (?)'
            params.append(branch)
        self.cursor.execute('SELECT idpackage FROM baseinfo WHERE atom = (?)'+branch_string, params)
        idpackage = self.cursor.fetchone()
        if idpackage: return idpackage[0]
        return -1

    def getIDPackageFromDownload(self, download_relative_path, endswith = False):
        if endswith:
            self.cursor.execute("""
            SELECT baseinfo.idpackage FROM baseinfo,extrainfo 
            WHERE extrainfo.download LIKE (?)""", ("%"+download_relative_path,))
        else:
            self.cursor.execute("""
            SELECT baseinfo.idpackage FROM baseinfo,extrainfo 
            WHERE extrainfo.download = (?)""", (download_relative_path,))
        idpackage = self.cursor.fetchone()
        if idpackage: return idpackage[0]
        return -1

    def getIDPackagesFromFile(self, file):
        self.cursor.execute('SELECT idpackage FROM content WHERE file = (?)', (file,))
        return self.fetchall2list(self.cursor.fetchall())

    def getIDCategory(self, category):
        self.cursor.execute('SELECT "idcategory" FROM categories WHERE category = (?)', (category,))
        idcat = self.cursor.fetchone()
        if idcat: return idcat[0]
        return -1

    def getVersioningData(self, idpackage):
        self.cursor.execute('SELECT version,versiontag,revision FROM baseinfo WHERE idpackage = (?)', (idpackage,))
        return self.cursor.fetchone()

    def getStrictData(self, idpackage):
        self.cursor.execute("""
        SELECT categories.category || "/" || baseinfo.name,
        baseinfo.slot,baseinfo.version,baseinfo.versiontag,
        baseinfo.revision,baseinfo.atom FROM baseinfo,categories 
        WHERE baseinfo.idpackage = (?) AND 
        baseinfo.idcategory = categories.idcategory""", (idpackage,))
        return self.cursor.fetchone()

    def getStrictScopeData(self, idpackage):
        self.cursor.execute("""
        SELECT atom,slot,revision FROM baseinfo
        WHERE idpackage = (?)""", (idpackage,))
        rslt = self.cursor.fetchone()
        return rslt

    def getScopeData(self, idpackage):
        self.cursor.execute("""
        SELECT 
            baseinfo.atom,
            categories.category,
            baseinfo.name,
            baseinfo.version,
            baseinfo.slot,
            baseinfo.versiontag,
            baseinfo.revision,
            baseinfo.branch,
            baseinfo.etpapi
        FROM 
            baseinfo,
            categories
        WHERE 
            baseinfo.idpackage = (?)
            and baseinfo.idcategory = categories.idcategory
        """, (idpackage,))
        return self.cursor.fetchone()

    def getBaseData(self, idpackage):

        sql = """
        SELECT 
            baseinfo.atom,
            baseinfo.name,
            baseinfo.version,
            baseinfo.versiontag,
            extrainfo.description,
            categories.category,
            flags.chost,
            flags.cflags,
            flags.cxxflags,
            extrainfo.homepage,
            licenses.license,
            baseinfo.branch,
            extrainfo.download,
            extrainfo.digest,
            baseinfo.slot,
            baseinfo.etpapi,
            extrainfo.datecreation,
            extrainfo.size,
            baseinfo.revision
        FROM 
            baseinfo,
            extrainfo,
            categories,
            flags,
            licenses
        WHERE 
            baseinfo.idpackage = (?) 
            and baseinfo.idpackage = extrainfo.idpackage 
            and baseinfo.idcategory = categories.idcategory 
            and extrainfo.idflags = flags.idflags
            and baseinfo.idlicense = licenses.idlicense
        """
        self.cursor.execute(sql, (idpackage,))
        return self.cursor.fetchone()

    def getTriggerInfo(self, idpackage):

        atom, category, name, \
        version, slot, versiontag, \
        revision, branch, etpapi = self.getScopeData(idpackage)
        chost, cflags, cxxflags = self.retrieveCompileFlags(idpackage)

        data = {
            'atom': atom,
            'category': category,
            'name': name,
            'version': version,
            'versiontag': versiontag,
            'revision': revision,
            'branch': branch,
            'chost': chost,
            'cflags': cflags,
            'cxxflags': cxxflags,
            'etpapi': etpapi,
            'trigger': self.retrieveTrigger(idpackage),
            'eclasses': self.retrieveEclasses(idpackage),
            'content': self.retrieveContent(idpackage),
            'spm_phases': self.retrieveSpmPhases(idpackage),
        }
        return data

    def getPackageData(self, idpackage, get_content = True,
            content_insert_formatted = False, trigger_unicode = True):
        data = {}

        try:
            atom, name, version, versiontag, \
            description, category, chost, \
            cflags, cxxflags,homepage, \
            mylicense, branch, download, \
            digest, slot, etpapi, \
            datecreation, size, revision  = self.getBaseData(idpackage)
        except TypeError:
            return None

        content = {}
        if get_content:
            content = self.retrieveContent(
                idpackage, extended = True,
                formatted = True, insert_formatted = content_insert_formatted
            )

        sources = self.retrieveSources(idpackage)
        mirrornames = set()
        for x in sources:
            if x.startswith("mirror://"):
                mirrornames.add(x.split("/")[2])

        data = {
            'atom': atom,
            'name': name,
            'version': version,
            'versiontag':versiontag,
            'description': description,
            'category': category,
            'chost': chost,
            'cflags': cflags,
            'cxxflags': cxxflags,
            'homepage': homepage,
            'license': mylicense,
            'branch': branch,
            'download': download,
            'digest': digest,
            'slot': slot,
            'etpapi': etpapi,
            'datecreation': datecreation,
            'size': size,
            'revision': revision,
            # risky to add to the sql above, still
            'counter': self.retrieveCounter(idpackage),
            'messages': self.retrieveMessages(idpackage),
            'trigger': self.retrieveTrigger(idpackage, get_unicode = trigger_unicode),
            'disksize': self.retrieveOnDiskSize(idpackage),
            'changelog': self.retrieveChangelog(idpackage),
            'injected': self.isInjected(idpackage),
            'systempackage': self.isSystemPackage(idpackage),
            'config_protect': self.retrieveProtect(idpackage),
            'config_protect_mask': self.retrieveProtectMask(idpackage),
            'useflags': self.retrieveUseflags(idpackage),
            'keywords': self.retrieveKeywords(idpackage),
            'sources': sources,
            'eclasses': self.retrieveEclasses(idpackage),
            'needed': self.retrieveNeeded(idpackage, extended = True),
            'provide': self.retrieveProvide(idpackage),
            'conflicts': self.retrieveConflicts(idpackage),
            'licensedata': self.retrieveLicensedata(idpackage),
            'content': content,
            'dependencies': dict((x, y,) for x, y in \
                self.retrieveDependencies(idpackage, extended = True)),
            'mirrorlinks': [[x,self.retrieveMirrorInfo(x)] for x in mirrornames],
            'signatures': self.retrieveSignatures(idpackage),
            'spm_phases': self.retrieveSpmPhases(idpackage),
        }

        return data

    def fetchall2set(self, item):
        mycontent = set()
        for x in item:
            mycontent |= set(x)
        return mycontent

    def fetchall2list(self, item):
        content = []
        for x in item:
            content += list(x)
        return content

    def fetchone2list(self, item):
        return list(item)

    def fetchone2set(self, item):
        return set(item)

    def clearCache(self, depends = False):

        self.live_cache.clear()
        def do_clear(name):
            dump_path = os.path.join(etpConst['dumpstoragedir'], name)
            dump_dir = os.path.dirname(dump_path)
            if os.path.isdir(dump_dir):
                for item in os.listdir(dump_dir):
                    try: os.remove(os.path.join(dump_dir, item))
                    except OSError: pass

        do_clear("%s/%s/" % (self.dbMatchCacheKey, self.dbname,))
        do_clear("%s/%s/" % (self.dbSearchCacheKey, self.dbname,))
        if depends:
            do_clear(etpCache['depends_tree'])
            do_clear(etpCache['dep_tree'])
            do_clear(etpCache['filter_satisfied_deps'])

    def fetchSearchCache(self, key, function, extra_hash = 0):
        if self.xcache:
            c_hash = "%s/%s/%s/%s" % (self.dbSearchCacheKey, self.dbname, key, "%s%s" % (hash(function), extra_hash,),)
            cached = self.Cacher.pop(c_hash)
            if cached != None: return cached

    def storeSearchCache(self, key, function, search_cache_data, extra_hash = 0):
        if self.xcache:
            c_hash = "%s/%s/%s/%s" % (self.dbSearchCacheKey, self.dbname, key, "%s%s" % (hash(function), extra_hash,),)
            self.Cacher.push(c_hash, search_cache_data)

    def retrieveRepositoryUpdatesDigest(self, repository):
        if not self.doesTableExist("treeupdates"):
            return -1
        self.cursor.execute('SELECT digest FROM treeupdates WHERE repository = (?)', (repository,))
        mydigest = self.cursor.fetchone()
        if mydigest:
            return mydigest[0]
        else:
            return -1

    def listAllTreeUpdatesActions(self, no_ids_repos = False):
        if no_ids_repos:
            self.cursor.execute('SELECT command,branch,date FROM treeupdatesactions')
        else:
            self.cursor.execute('SELECT * FROM treeupdatesactions')
        return self.cursor.fetchall()

    def retrieveTreeUpdatesActions(self, repository, forbranch = None):

        if not self.doesTableExist("treeupdatesactions"): return []
        if forbranch == None: forbranch = self.db_branch
        params = [repository]
        branch_string = ''
        if forbranch:
            branch_string = 'and branch = (?)'
            params.append(forbranch)

        self.cursor.execute("""
        SELECT command FROM treeupdatesactions WHERE 
        repository = (?) %s order by date""" % (branch_string,), params)
        return self.fetchall2list(self.cursor.fetchall())

    # mainly used to restore a previous table, used by reagent in --initialize
    def bumpTreeUpdatesActions(self, updates):
        with self.WriteLock:
            self.cursor.execute('DELETE FROM treeupdatesactions')
            self.cursor.executemany('INSERT INTO treeupdatesactions VALUES (?,?,?,?,?)', updates)
            self.commitChanges()

    def removeTreeUpdatesActions(self, repository):
        with self.WriteLock:
            self.cursor.execute('DELETE FROM treeupdatesactions WHERE repository = (?)', (repository,))
            self.commitChanges()

    def insertTreeUpdatesActions(self, updates, repository):
        with self.WriteLock:
            myupdates = [[repository]+list(x) for x in updates]
            self.cursor.executemany('INSERT INTO treeupdatesactions VALUES (NULL,?,?,?,?)', myupdates)
            self.commitChanges()

    def setRepositoryUpdatesDigest(self, repository, digest):
        with self.WriteLock:
            self.cursor.execute('DELETE FROM treeupdates where repository = (?)', (repository,)) # doing it for safety
            self.cursor.execute('INSERT INTO treeupdates VALUES (?,?)', (repository, digest,))

    def addRepositoryUpdatesActions(self, repository, actions, branch):

        mytime = str(self.entropyTools.get_current_unix_time())
        with self.WriteLock:
            myupdates = [
                (repository, x, branch, mytime,) for x in actions \
                if not self.doesTreeupdatesActionExist(repository, x, branch)
            ]
            self.cursor.executemany('INSERT INTO treeupdatesactions VALUES (NULL,?,?,?,?)', myupdates)

    def doesTreeupdatesActionExist(self, repository, command, branch):
        self.cursor.execute("""
        SELECT * FROM treeupdatesactions 
        WHERE repository = (?) and command = (?) and branch = (?)""", (repository, command, branch,))
        result = self.cursor.fetchone()
        if result:
            return True
        return False

    def clearPackageSets(self):
        self.cursor.execute('DELETE FROM packagesets')

    def insertPackageSets(self, sets_data):

        mysets = []
        for setname in sorted(sets_data.keys()):
            for dependency in sorted(sets_data[setname]):
                try:
                    mysets.append((unicode(setname), unicode(dependency),))
                except (UnicodeDecodeError, UnicodeEncodeError,):
                    continue

        with self.WriteLock:
            self.cursor.executemany('INSERT INTO packagesets VALUES (?,?)', mysets)

    def retrievePackageSets(self):
        if not self.doesTableExist("packagesets"): return {}
        self.cursor.execute('SELECT setname,dependency FROM packagesets')
        data = self.cursor.fetchall()
        sets = {}
        for setname, dependency in data:
            if not sets.has_key(setname):
                sets[setname] = set()
            sets[setname].add(dependency)
        return sets

    def retrievePackageSet(self, setname):
        self.cursor.execute('SELECT dependency FROM packagesets WHERE setname = (?)', (setname,))
        return self.fetchall2set(self.cursor.fetchall())

    def retrieveSystemPackages(self):
        self.cursor.execute('SELECT idpackage FROM systempackages')
        return self.fetchall2set(self.cursor.fetchall())

    def retrieveAtom(self, idpackage):
        self.cursor.execute('SELECT atom FROM baseinfo WHERE idpackage = (?)', (idpackage,))
        atom = self.cursor.fetchone()
        if atom: return atom[0]

    def retrieveBranch(self, idpackage):
        self.cursor.execute('SELECT branch FROM baseinfo WHERE idpackage = (?)', (idpackage,))
        br = self.cursor.fetchone()
        if br: return br[0]

    def retrieveTrigger(self, idpackage, get_unicode = False):
        self.cursor.execute('SELECT data FROM triggers WHERE idpackage = (?)', (idpackage,))
        trigger = self.cursor.fetchone()
        if not trigger:
            return '' # FIXME backward compatibility with <=0.52.x
        if not get_unicode:
            return trigger[0]
        return unicode(trigger[0], 'raw_unicode_escape')

    def retrieveDownloadURL(self, idpackage):
        self.cursor.execute('SELECT download FROM extrainfo WHERE idpackage = (?)', (idpackage,))
        download = self.cursor.fetchone()
        if download: return download[0]

    def retrieveDescription(self, idpackage):
        self.cursor.execute('SELECT description FROM extrainfo WHERE idpackage = (?)', (idpackage,))
        description = self.cursor.fetchone()
        if description: return description[0]

    def retrieveHomepage(self, idpackage):
        self.cursor.execute('SELECT homepage FROM extrainfo WHERE idpackage = (?)', (idpackage,))
        home = self.cursor.fetchone()
        if home: return home[0]

    def retrieveCounter(self, idpackage):
        self.cursor.execute("""
        SELECT counters.counter FROM counters,baseinfo 
        WHERE counters.idpackage = (?) AND 
        baseinfo.idpackage = counters.idpackage AND 
        baseinfo.branch = counters.branch""", (idpackage,))
        mycounter = self.cursor.fetchone()
        if mycounter: return mycounter[0]
        return -1

    def retrieveMessages(self, idpackage):
        self.cursor.execute('SELECT message FROM messages WHERE idpackage = (?)', (idpackage,))
        return self.fetchall2list(self.cursor.fetchall())

    # in bytes
    def retrieveSize(self, idpackage):
        self.cursor.execute('SELECT size FROM extrainfo WHERE idpackage = (?)', (idpackage,))
        size = self.cursor.fetchone()
        if size: return size[0]

    # in bytes
    def retrieveOnDiskSize(self, idpackage):
        self.cursor.execute('SELECT size FROM sizes WHERE idpackage = (?)', (idpackage,))
        size = self.cursor.fetchone() # do not use [0]!
        if not size: size = 0
        else: size = size[0]
        return size

    def retrieveDigest(self, idpackage):
        self.cursor.execute('SELECT digest FROM extrainfo WHERE idpackage = (?)', (idpackage,))
        digest = self.cursor.fetchone()
        if digest: return digest[0]

    def retrieveSignatures(self, idpackage):
        mydict = {
            'sha1': None,
            'sha256': None,
            'sha512': None,
        }
        # FIXME: remove this check in future
        if self.doesTableExist('packagesignatures'):
            self.cursor.execute("""
            SELECT sha1, sha256, sha512 FROM packagesignatures 
            WHERE idpackage = (?)""", (idpackage,))
            data = self.cursor.fetchone()
            if data:
                mydict['sha1'], mydict['sha256'], mydict['sha512'] = data
        return mydict

    def retrieveName(self, idpackage):
        self.cursor.execute('SELECT name FROM baseinfo WHERE idpackage = (?)', (idpackage,))
        name = self.cursor.fetchone()
        if name: return name[0]

    def retrieveKeySlot(self, idpackage):
        self.cursor.execute("""
        SELECT categories.category || "/" || baseinfo.name,baseinfo.slot FROM baseinfo,categories 
        WHERE baseinfo.idpackage = (?) and baseinfo.idcategory = categories.idcategory""", (idpackage,))
        data = self.cursor.fetchone()
        return data

    def retrieveKeySlotAggregated(self, idpackage):
        self.cursor.execute("""
        SELECT categories.category || "/" || baseinfo.name || ":" || baseinfo.slot FROM baseinfo,categories 
        WHERE baseinfo.idpackage = (?) and baseinfo.idcategory = categories.idcategory""", (idpackage,))
        data = self.cursor.fetchone()
        if data: return data[0]

    def retrieveKeySlotTag(self, idpackage):
        self.cursor.execute("""
        SELECT categories.category || "/" || baseinfo.name,baseinfo.slot,baseinfo.versiontag FROM baseinfo,categories 
        WHERE baseinfo.idpackage = (?) and baseinfo.idcategory = categories.idcategory""", (idpackage,))
        data = self.cursor.fetchone()
        return data

    def retrieveVersion(self, idpackage):
        self.cursor.execute('SELECT version FROM baseinfo WHERE idpackage = (?)', (idpackage,))
        ver = self.cursor.fetchone()
        if ver: return ver[0]

    def retrieveRevision(self, idpackage):
        self.cursor.execute('SELECT revision FROM baseinfo WHERE idpackage = (?)', (idpackage,))
        rev = self.cursor.fetchone()
        if rev: return rev[0]

    def retrieveDateCreation(self, idpackage):
        self.cursor.execute('SELECT datecreation FROM extrainfo WHERE idpackage = (?)', (idpackage,))
        date = self.cursor.fetchone()
        if date: return date[0]

    def retrieveApi(self, idpackage):
        self.cursor.execute('SELECT etpapi FROM baseinfo WHERE idpackage = (?)', (idpackage,))
        api = self.cursor.fetchone()
        if api: return api[0]

    def retrieveUseflags(self, idpackage):
        self.cursor.execute("""
        SELECT flagname FROM useflags,useflagsreference 
        WHERE useflags.idpackage = (?) AND 
        useflags.idflag = useflagsreference.idflag""", (idpackage,))
        return self.fetchall2set(self.cursor.fetchall())

    def retrieveEclasses(self, idpackage):
        self.cursor.execute("""
        SELECT classname FROM eclasses,eclassesreference 
        WHERE eclasses.idpackage = (?) AND 
        eclasses.idclass = eclassesreference.idclass""", (idpackage,))
        return self.fetchall2set(self.cursor.fetchall())

    def retrieveSpmPhases(self, idpackage):
        # FIXME: remove this check in future:
        if not self.doesTableExist('packagespmphases'):
            return None
        self.cursor.execute("""
        SELECT phases FROM packagespmphases
        WHERE idpackage = (?)
        """, (idpackage,))
        rslt = self.cursor.fetchone()
        if rslt: return rslt[0]

    def retrieveNeededRaw(self, idpackage):
        self.cursor.execute("""
        SELECT library FROM needed,neededreference 
        WHERE needed.idpackage = (?) AND 
        needed.idneeded = neededreference.idneeded""", (idpackage,))
        return self.fetchall2set(self.cursor.fetchall())

    def retrieveNeeded(self, idpackage, extended = False, format = False):

        if extended:
            self.cursor.execute("""
            SELECT library,elfclass FROM needed,neededreference 
            WHERE needed.idpackage = (?) AND 
            needed.idneeded = neededreference.idneeded order by library""", (idpackage,))
            needed = self.cursor.fetchall()
        else:
            self.cursor.execute("""
            SELECT library FROM needed,neededreference 
            WHERE needed.idpackage = (?) AND 
            needed.idneeded = neededreference.idneeded ORDER BY library""", (idpackage,))
            needed = self.fetchall2list(self.cursor.fetchall())

        if extended and format:
            data = {}
            for lib, elfclass in needed:
                data[lib] = elfclass
            needed = data

        return needed

    def retrieveConflicts(self, idpackage):
        self.cursor.execute('SELECT conflict FROM conflicts WHERE idpackage = (?)', (idpackage,))
        return self.fetchall2set(self.cursor.fetchall())

    def retrieveProvide(self, idpackage):
        self.cursor.execute('SELECT atom FROM provide WHERE idpackage = (?)', (idpackage,))
        return self.fetchall2set(self.cursor.fetchall())

    def retrieveDependenciesList(self, idpackage):
        self.cursor.execute("""
        SELECT dependenciesreference.dependency FROM dependencies,dependenciesreference 
        WHERE dependencies.idpackage = (?) AND 
        dependencies.iddependency = dependenciesreference.iddependency 
        UNION SELECT "!" || conflict FROM conflicts 
        WHERE idpackage = (?)""", (idpackage, idpackage,))
        return self.fetchall2set(self.cursor.fetchall())

    def retrievePostDependencies(self, idpackage, extended = False):
        return self.retrieveDependencies(idpackage, extended = extended, deptype = etpConst['spm']['pdepend_id'])

    def retrieveManualDependencies(self, idpackage, extended = False):
        return self.retrieveDependencies(idpackage, extended = extended, deptype = etpConst['spm']['mdepend_id'])

    def retrieveDependencies(self, idpackage, extended = False, deptype = None,
        exclude_deptypes = None):

        searchdata = [idpackage]

        depstring = ''
        if deptype != None:
            depstring = ' and dependencies.type = (?)'
            searchdata.append(deptype)

        excluded_deptypes_query = ""
        if exclude_deptypes != None:
            for dep_type in exclude_deptypes:
                excluded_deptypes_query += " AND dependencies.type != %s" % (
                    dep_type,)

        if extended:
            self.cursor.execute("""
            SELECT dependenciesreference.dependency,dependencies.type 
            FROM dependencies,dependenciesreference 
            WHERE dependencies.idpackage = (?) AND 
            dependencies.iddependency = dependenciesreference.iddependency %s %s""" % (
                depstring,excluded_deptypes_query,), searchdata)
            deps = self.cursor.fetchall()
        else:
            self.cursor.execute("""
            SELECT dependenciesreference.dependency 
            FROM dependencies,dependenciesreference 
            WHERE dependencies.idpackage = (?) AND 
            dependencies.iddependency = dependenciesreference.iddependency %s %s""" % (
                depstring,excluded_deptypes_query,), searchdata)
            deps = self.fetchall2set(self.cursor.fetchall())

        return deps

    def retrieveIdDependencies(self, idpackage):
        self.cursor.execute('SELECT iddependency FROM dependencies WHERE idpackage = (?)', (idpackage,))
        return self.fetchall2set(self.cursor.fetchall())

    def retrieveDependencyFromIddependency(self, iddependency):
        self.cursor.execute('SELECT dependency FROM dependenciesreference WHERE iddependency = (?)', (iddependency,))
        dep = self.cursor.fetchone()
        if dep: dep = dep[0]
        return dep

    def retrieveKeywords(self, idpackage):
        self.cursor.execute("""
        SELECT keywordname FROM keywords,keywordsreference 
        WHERE keywords.idpackage = (?) AND 
        keywords.idkeyword = keywordsreference.idkeyword""", (idpackage,))
        return self.fetchall2set(self.cursor.fetchall())

    def retrieveProtect(self, idpackage):
        self.cursor.execute("""
        SELECT protect FROM configprotect,configprotectreference 
        WHERE configprotect.idpackage = (?) AND 
        configprotect.idprotect = configprotectreference.idprotect""", (idpackage,))
        protect = self.cursor.fetchone()
        if not protect: protect = ''
        else: protect = protect[0]
        return protect

    def retrieveProtectMask(self, idpackage):
        self.cursor.execute("""
        SELECT protect FROM configprotectmask,configprotectreference 
        WHERE idpackage = (?) AND 
        configprotectmask.idprotect = configprotectreference.idprotect""", (idpackage,))
        protect = self.cursor.fetchone()
        if not protect: protect = ''
        else: protect = protect[0]
        return protect

    def retrieveSources(self, idpackage, extended = False):
        self.cursor.execute("""
        SELECT sourcesreference.source FROM sources,sourcesreference 
        WHERE idpackage = (?) AND 
        sources.idsource = sourcesreference.idsource""", (idpackage,))
        sources = self.fetchall2set(self.cursor.fetchall())
        if not extended:
            return sources

        source_data = {}
        mirror_str = "mirror://"
        for source in sources:
            source_data[source] = set()
            if source.startswith(mirror_str):
                mirrorname = source.split("/")[2]
                mirror_url =  source.split("/", 3)[3:][0]
                source_data[source] |= set([os.path.join(url, mirror_url) for url in self.retrieveMirrorInfo(mirrorname)])
            else:
                source_data[source].add(source)

        return source_data

    def retrieveAutomergefiles(self, idpackage, get_dict = False):
        if not self.doesTableExist('automergefiles'):
            self.createAutomergefilesTable()
        # like portage does
        self.connection.text_factory = lambda x: unicode(x, "raw_unicode_escape")
        self.cursor.execute('SELECT configfile, md5 FROM automergefiles WHERE idpackage = (?)', (idpackage,))
        data = self.cursor.fetchall()
        if get_dict:
            data = dict(((x, y,) for x, y in data))
        return data

    def retrieveContent(self, idpackage, extended = False, contentType = None, formatted = False, insert_formatted = False, order_by = ''):

        extstring = ''
        if extended:
            extstring = ",type"
        extstring_idpackage = ''
        if insert_formatted:
            extstring_idpackage = 'idpackage,'

        searchkeywords = [idpackage]
        contentstring = ''
        if contentType:
            searchkeywords.append(contentType)
            contentstring = ' and type = (?)'

        order_by_string = ''
        if order_by:
            order_by_string = ' order by %s' % (order_by,)

        did_try = False
        while 1:
            try:

                self.cursor.execute('SELECT %s file%s FROM content WHERE idpackage = (?) %s%s' % (
                    extstring_idpackage, extstring, contentstring, order_by_string,),
                    searchkeywords)

                if extended and insert_formatted:
                    fl = self.cursor.fetchall()
                elif extended and formatted:
                    fl = {}
                    items = self.cursor.fetchone()
                    while items:
                        fl[items[0]] = items[1]
                        items = self.cursor.fetchone()
                elif extended:
                    fl = self.cursor.fetchall()
                else:
                    if order_by:
                        fl = self.fetchall2list(self.cursor.fetchall())
                    else:
                        fl = self.fetchall2set(self.cursor.fetchall())
                break
            except (self.dbapi2.OperationalError,):
                if did_try:
                    raise
                did_try = True
                # XXX support for old entropy db entries, which were
                # not inserted in utf-8
                self.connection.text_factory = lambda x: unicode(x, "raw_unicode_escape")
                continue
        return fl

    def retrieveChangelog(self, idpackage):
        if not self.doesTableExist('packagechangelogs'):
            return None
        self.cursor.execute("""
        SELECT packagechangelogs.changelog FROM packagechangelogs,baseinfo,categories 
        WHERE baseinfo.idpackage = (?) AND 
        baseinfo.idcategory = categories.idcategory AND 
        packagechangelogs.name = baseinfo.name AND 
        packagechangelogs.category = categories.category""", (idpackage,))
        changelog = self.cursor.fetchone()
        if changelog:
            changelog = changelog[0]
            try:
                return unicode(changelog, 'raw_unicode_escape')
            except UnicodeDecodeError:
                return unicode(changelog, 'utf-8')

    def retrieveChangelogByKey(self, category, name):
        if not self.doesTableExist('packagechangelogs'):
            return None
        self.connection.text_factory = lambda x: unicode(x, "raw_unicode_escape")
        self.cursor.execute('SELECT changelog FROM packagechangelogs WHERE category = (?) AND name = (?)', (category, name,))
        changelog = self.cursor.fetchone()
        if changelog: return unicode(changelog[0], 'raw_unicode_escape')

    def retrieveSlot(self, idpackage):
        self.cursor.execute('SELECT slot FROM baseinfo WHERE idpackage = (?)', (idpackage,))
        slot = self.cursor.fetchone()
        if slot: return slot[0]

    def retrieveVersionTag(self, idpackage):
        self.cursor.execute('SELECT versiontag FROM baseinfo WHERE idpackage = (?)', (idpackage,))
        vtag = self.cursor.fetchone()
        if vtag: return vtag[0]

    def retrieveMirrorInfo(self, mirrorname):
        self.cursor.execute('SELECT mirrorlink FROM mirrorlinks WHERE mirrorname = (?)', (mirrorname,))
        mirrorlist = self.fetchall2set(self.cursor.fetchall())
        return mirrorlist

    def retrieveCategory(self, idpackage):
        self.cursor.execute("""
        SELECT category FROM baseinfo,categories 
        WHERE baseinfo.idpackage = (?) AND 
        baseinfo.idcategory = categories.idcategory""", (idpackage,))
        cat = self.cursor.fetchone()
        if cat: return cat[0]

    def retrieveCategoryDescription(self, category):
        data = {}
        if not self.doesTableExist("categoriesdescription"):
            return data
        self.cursor.execute('SELECT description,locale FROM categoriesdescription WHERE category = (?)', (category,))
        description_data = self.cursor.fetchall()
        for description, locale in description_data:
            data[locale] = description
        return data

    def retrieveLicensedata(self, idpackage):

        # insert license information
        if not self.doesTableExist("licensedata"):
            return {}
        licenses = self.retrieveLicense(idpackage)
        if licenses == None:
            return {}
        licenses = licenses.split()
        licdata = {}
        for licname in licenses:
            licname = licname.strip()
            if not self.entropyTools.is_valid_string(licname):
                continue

            self.cursor.execute('SELECT text FROM licensedata WHERE licensename = (?)', (licname,))
            lictext = self.cursor.fetchone()
            if lictext != None:
                lictext = lictext[0]
                try:
                    licdata[licname] = unicode(lictext, 'raw_unicode_escape')
                except UnicodeDecodeError:
                    licdata[licname] = unicode(lictext, 'utf-8')

        return licdata

    def retrieveLicensedataKeys(self, idpackage):

        if not self.doesTableExist("licensedata"):
            return set()
        licenses = self.retrieveLicense(idpackage)
        if licenses == None:
            return set()
        licenses = licenses.split()
        licdata = set()
        for licname in licenses:
            licname = licname.strip()
            if not self.entropyTools.is_valid_string(licname):
                continue
            self.cursor.execute('SELECT licensename FROM licensedata WHERE licensename = (?)', (licname,))
            licidentifier = self.cursor.fetchone()
            if licidentifier:
                licdata.add(licidentifier[0])

        return licdata

    def retrieveLicenseText(self, license_name):

        if not self.doesTableExist("licensedata"):
            return None

        self.connection.text_factory = lambda x: unicode(x, "raw_unicode_escape")

        self.cursor.execute('SELECT text FROM licensedata WHERE licensename = (?)', (license_name,))
        text = self.cursor.fetchone()
        if not text:
            return None
        return str(text[0])

    def retrieveLicense(self, idpackage):
        self.cursor.execute("""
        SELECT license FROM baseinfo,licenses 
        WHERE baseinfo.idpackage = (?) AND 
        baseinfo.idlicense = licenses.idlicense""", (idpackage,))
        licname = self.cursor.fetchone()
        if licname: return licname[0]

    def retrieveCompileFlags(self, idpackage):
        self.cursor.execute("""
        SELECT chost,cflags,cxxflags FROM flags,extrainfo 
        WHERE extrainfo.idpackage = (?) AND 
        extrainfo.idflags = flags.idflags""", (idpackage,))
        flags = self.cursor.fetchone()
        if not flags:
            flags = ("N/A", "N/A", "N/A",)
        return flags

    def retrieveDepends(self, idpackage, atoms = False, key_slot = False,
        exclude_deptypes = None):

        # WARNING: never remove this, otherwise equo.db
        # (client database) dependstable will be always broken (trust me)
        # sanity check on the table
        if not self.isDependsTableSane(): # is empty, need generation
            self.regenerateDependsTable(output = False)

        excluded_deptypes_query = ""
        if exclude_deptypes != None:
            for dep_type in exclude_deptypes:
                excluded_deptypes_query += " AND dependencies.type != %s" % (
                    dep_type,)

        if atoms:
            self.cursor.execute("""
            SELECT baseinfo.atom FROM dependstable,dependencies,baseinfo 
            WHERE dependstable.idpackage = (?) AND 
            dependstable.iddependency = dependencies.iddependency AND 
            baseinfo.idpackage = dependencies.idpackage %s""" % (
                excluded_deptypes_query,), (idpackage,))
            result = self.fetchall2set(self.cursor.fetchall())
        elif key_slot:
            self.cursor.execute("""
            SELECT categories.category || "/" || baseinfo.name,baseinfo.slot 
            FROM baseinfo,categories,dependstable,dependencies 
            WHERE dependstable.idpackage = (?) AND 
            dependstable.iddependency = dependencies.iddependency AND 
            baseinfo.idpackage = dependencies.idpackage AND 
            categories.idcategory = baseinfo.idcategory %s""" % (
                excluded_deptypes_query,), (idpackage,))
            result = self.cursor.fetchall()
        else:
            self.cursor.execute("""
            SELECT dependencies.idpackage FROM dependstable,dependencies 
            WHERE dependstable.idpackage = (?) AND 
            dependstable.iddependency = dependencies.iddependency %s""" % (
                excluded_deptypes_query,), (idpackage,))
            result = self.fetchall2set(self.cursor.fetchall())

        return result

    def retrieveUnusedIdpackages(self):
        # WARNING: never remove this, otherwise equo.db (client database) dependstable will be always broken (trust me)
        # sanity check on the table
        if not self.isDependsTableSane(): # is empty, need generation
            self.regenerateDependsTable(output = False)
        self.cursor.execute("""
        SELECT idpackage FROM baseinfo 
        WHERE idpackage NOT IN (SELECT idpackage FROM dependstable) ORDER BY atom
        """)
        return self.fetchall2list(self.cursor.fetchall())

    # You must provide the full atom to this function
    # WARNING: this function does not support branches
    def isPackageAvailable(self, pkgatom):
        pkgatom = self.entropyTools.remove_package_operators(pkgatom)
        self.cursor.execute('SELECT idpackage FROM baseinfo WHERE atom = (?)', (pkgatom,))
        result = self.cursor.fetchone()
        if result: return result[0]
        return -1

    def isIDPackageAvailable(self, idpackage):
        self.cursor.execute('SELECT idpackage FROM baseinfo WHERE idpackage = (?)', (idpackage,))
        result = self.cursor.fetchone()
        if not result:
            return False
        return True

    def areIDPackagesAvailable(self, idpackages):
        sql = 'SELECT count(idpackage) FROM baseinfo WHERE idpackage IN (%s)' % (','.join([str(x) for x in set(idpackages)]),)
        self.cursor.execute(sql)
        count = self.cursor.fetchone()[0]
        if count != len(idpackages):
            return False
        return True

    def isCategoryAvailable(self, category):
        self.cursor.execute('SELECT idcategory FROM categories WHERE category = (?)', (category,))
        result = self.cursor.fetchone()
        if result: return result[0]
        return -1

    def isProtectAvailable(self, protect):
        self.cursor.execute('SELECT idprotect FROM configprotectreference WHERE protect = (?)', (protect,))
        result = self.cursor.fetchone()
        if result: return result[0]
        return -1

    def isFileAvailable(self, myfile, get_id = False):
        self.cursor.execute('SELECT idpackage FROM content WHERE file = (?)', (myfile,))
        result = self.cursor.fetchall()
        if get_id:
            return self.fetchall2set(result)
        elif result:
            return True
        return False

    def resolveNeeded(self, needed, elfclass = -1):

        cache = self.fetchSearchCache(needed, 'resolveNeeded')
        if cache != None: return cache

        ldpaths = self.entropyTools.collect_linker_paths()
        mypaths = [os.path.join(x, needed) for x in ldpaths]

        query = """
        SELECT idpackage,file FROM content WHERE content.file IN (%s)
        """ % ( ('?,'*len(mypaths))[:-1], )

        self.cursor.execute(query, mypaths)
        results = self.cursor.fetchall()

        if elfclass == -1:
            mydata = set(results)
        else:
            mydata = set()
            for data in results:
                if not os.access(data[1], os.R_OK):
                    continue
                myclass = self.entropyTools.read_elf_class(data[1])
                if myclass == elfclass:
                    mydata.add(data)

        self.storeSearchCache(needed, 'resolveNeeded', mydata)
        return mydata

    def isSourceAvailable(self, source):
        self.cursor.execute('SELECT idsource FROM sourcesreference WHERE source = (?)', (source,))
        result = self.cursor.fetchone()
        if result: return result[0]
        return -1

    def isDependencyAvailable(self, dependency):
        self.cursor.execute('SELECT iddependency FROM dependenciesreference WHERE dependency = (?)', (dependency,))
        result = self.cursor.fetchone()
        if result: return result[0]
        return -1

    def isKeywordAvailable(self, keyword):
        self.cursor.execute('SELECT idkeyword FROM keywordsreference WHERE keywordname = (?)', (keyword,))
        result = self.cursor.fetchone()
        if result: return result[0]
        return -1

    def isUseflagAvailable(self, useflag):
        self.cursor.execute('SELECT idflag FROM useflagsreference WHERE flagname = (?)', (useflag,))
        result = self.cursor.fetchone()
        if result: return result[0]
        return -1

    def isEclassAvailable(self, eclass):
        self.cursor.execute('SELECT idclass FROM eclassesreference WHERE classname = (?)', (eclass,))
        result = self.cursor.fetchone()
        if result: return result[0]
        return -1

    def isNeededAvailable(self, needed):
        self.cursor.execute('SELECT idneeded FROM neededreference WHERE library = (?)', (needed,))
        result = self.cursor.fetchone()
        if result: return result[0]
        return -1

    def isCounterAvailable(self, counter, branch = None, branch_operator = "="):
        params = [counter]
        branch_string = ''
        if branch:
            branch_string = ' and branch '+branch_operator+' (?)'
            params = [counter, branch]

        self.cursor.execute('SELECT counter FROM counters WHERE counter = (?)'+branch_string, params)
        result = self.cursor.fetchone()
        if result: return True
        return False

    def isCounterTrashed(self, counter):
        self.cursor.execute('SELECT counter FROM trashedcounters WHERE counter = (?)', (counter,))
        result = self.cursor.fetchone()
        if result: return True
        return False

    def isLicensedataKeyAvailable(self, license_name):
        if not self.doesTableExist("licensedata"):
            return True
        self.cursor.execute('SELECT licensename FROM licensedata WHERE licensename = (?)', (license_name,))
        result = self.cursor.fetchone()
        if not result:
            return False
        return True

    def isLicenseAccepted(self, license_name):
        self.cursor.execute('SELECT licensename FROM licenses_accepted WHERE licensename = (?)', (license_name,))
        result = self.cursor.fetchone()
        if not result:
            return False
        return True

    def acceptLicense(self, license_name):
        if self.readOnly or (not self.entropyTools.is_user_in_entropy_group()):
            return
        if self.isLicenseAccepted(license_name):
            return
        with self.WriteLock:
            self.cursor.execute('INSERT INTO licenses_accepted VALUES (?)', (license_name,))
            self.commitChanges()

    def isLicenseAvailable(self, pkglicense):
        if not self.entropyTools.is_valid_string(pkglicense):
            pkglicense = ' '
        self.cursor.execute('SELECT idlicense FROM licenses WHERE license = (?)', (pkglicense,))
        result = self.cursor.fetchone()
        if result: return result[0]
        return -1

    def isSystemPackage(self, idpackage):
        self.cursor.execute('SELECT idpackage FROM systempackages WHERE idpackage = (?)', (idpackage,))
        result = self.cursor.fetchone()
        if result:
            return True
        return False

    def isInjected(self, idpackage):
        self.cursor.execute('SELECT idpackage FROM injected WHERE idpackage = (?)', (idpackage,))
        result = self.cursor.fetchone()
        if result:
            return True
        return False

    def areCompileFlagsAvailable(self, chost, cflags, cxxflags):

        self.cursor.execute('SELECT idflags FROM flags WHERE chost = (?) AND cflags = (?) AND cxxflags = (?)',
            (chost, cflags, cxxflags,)
        )
        result = self.cursor.fetchone()
        if result: return result[0]
        return -1

    def searchBelongs(self, file, like = False, branch = None, branch_operator = "="):

        branchstring = ''
        searchkeywords = [file]
        if branch:
            searchkeywords.append(branch)
            branchstring = ' and baseinfo.branch '+branch_operator+' (?)'

        if like:
            self.cursor.execute("""
            SELECT content.idpackage FROM content,baseinfo 
            WHERE file LIKE (?) AND 
            content.idpackage = baseinfo.idpackage %s""" % (branchstring,), searchkeywords)
        else:
            self.cursor.execute("""SELECT content.idpackage FROM content,baseinfo 
            WHERE file = (?) AND 
            content.idpackage = baseinfo.idpackage %s""" % (branchstring,), searchkeywords)

        return self.fetchall2set(self.cursor.fetchall())

    ''' search packages that uses the eclass provided '''
    def searchEclassedPackages(self, eclass, atoms = False): # atoms = return atoms directly
        if atoms:
            self.cursor.execute("""
            SELECT baseinfo.atom,eclasses.idpackage FROM baseinfo,eclasses,eclassesreference 
            WHERE eclassesreference.classname = (?) AND 
            eclassesreference.idclass = eclasses.idclass AND 
            eclasses.idpackage = baseinfo.idpackage""", (eclass,))
            return self.cursor.fetchall()
        else:
            self.cursor.execute('SELECT idpackage FROM baseinfo WHERE versiontag = (?)', (eclass,))
            return self.fetchall2set(self.cursor.fetchall())

    ''' search packages whose versiontag matches the one provided '''
    def searchTaggedPackages(self, tag, atoms = False): # atoms = return atoms directly
        if atoms:
            self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE versiontag = (?)', (tag,))
            return self.cursor.fetchall()
        else:
            self.cursor.execute('SELECT idpackage FROM baseinfo WHERE versiontag = (?)', (tag,))
            return self.fetchall2set(self.cursor.fetchall())

    def searchLicenses(self, mylicense, caseSensitive = False, atoms = False):

        if not self.entropyTools.is_valid_string(mylicense):
            return []

        request = "baseinfo.idpackage"
        if atoms:
            request = "baseinfo.atom,baseinfo.idpackage"

        if caseSensitive:
            self.cursor.execute("""
            SELECT %s FROM baseinfo,licenses 
            WHERE licenses.license LIKE (?) AND 
            licenses.idlicense = baseinfo.idlicense""" % (request,), ("%"+mylicense+"%",))
        else:
            self.cursor.execute("""
            SELECT %s FROM baseinfo,licenses 
            WHERE LOWER(licenses.license) LIKE (?) AND 
            licenses.idlicense = baseinfo.idlicense""" % (request,), ("%"+mylicense+"%".lower(),))
        if atoms:
            return self.cursor.fetchall()
        return self.fetchall2set(self.cursor.fetchall())

    ''' search packages whose slot matches the one provided '''
    def searchSlottedPackages(self, slot, atoms = False): # atoms = return atoms directly
        if atoms:
            self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE slot = (?)', (slot,))
            return self.cursor.fetchall()
        else:
            self.cursor.execute('SELECT idpackage FROM baseinfo WHERE slot = (?)', (slot,))
            return self.fetchall2set(self.cursor.fetchall())

    def searchKeySlot(self, key, slot, branch = None):

        branchstring = ''
        cat, name = key.split("/")
        params = [cat, name, slot]
        if branch:
            params.append(branch)
            branchstring = 'and baseinfo.branch = (?)'

        self.cursor.execute("""
        SELECT idpackage FROM baseinfo,categories 
        WHERE baseinfo.idcategory = categories.idcategory AND 
        categories.category = (?) AND 
        baseinfo.name = (?) AND 
        baseinfo.slot = (?) %s""" % (branchstring,), params)
        return self.cursor.fetchall()

    ''' search packages that need the specified library (in neededreference table) specified by keyword '''
    def searchNeeded(self, keyword, like = False):
        if like:
            self.cursor.execute("""
            SELECT needed.idpackage FROM needed,neededreference 
            WHERE library LIKE (?) AND 
            needed.idneeded = neededreference.idneeded""", (keyword,))
        else:
            self.cursor.execute("""
            SELECT needed.idpackage FROM needed,neededreference 
            WHERE library = (?) AND 
            needed.idneeded = neededreference.idneeded""", (keyword,))
	return self.fetchall2set(self.cursor.fetchall())

    ''' search dependency string inside dependenciesreference table and retrieve iddependency '''
    def searchDependency(self, dep, like = False, multi = False, strings = False):
        sign = "="
        if like:
            sign = "LIKE"
            dep = "%"+dep+"%"
        item = 'iddependency'
        if strings:
            item = 'dependency'
        self.cursor.execute('SELECT %s FROM dependenciesreference WHERE dependency %s (?)' % (item, sign,), (dep,))
        if multi:
            return self.fetchall2set(self.cursor.fetchall())
        else:
            iddep = self.cursor.fetchone()
            if iddep:
                iddep = iddep[0]
            else:
                iddep = -1
            return iddep

    ''' search iddependency inside dependencies table and retrieve idpackages '''
    def searchIdpackageFromIddependency(self, iddep):
        self.cursor.execute('SELECT idpackage FROM dependencies WHERE iddependency = (?)', (iddep,))
        return self.fetchall2set(self.cursor.fetchall())

    def searchSets(self, keyword):
        self.cursor.execute('SELECT DISTINCT(setname) FROM packagesets WHERE setname LIKE (?)', ("%"+keyword+"%",))
        return self.fetchall2set(self.cursor.fetchall())

    def searchSimilarPackages(self, mystring, atom = False):
        s_item = 'name'
        if atom: s_item = 'atom'
        self.cursor.execute("""
        SELECT idpackage FROM baseinfo 
        WHERE soundex(%s) = soundex((?)) ORDER BY %s""" % (s_item, s_item,), (mystring,))
        return self.fetchall2list(self.cursor.fetchall())

    def searchPackages(self, keyword, sensitive = False, slot = None, tag = None, branch = None, order_by = 'atom', just_id = False):

        searchkeywords = ["%"+keyword+"%"]
        slotstring = ''
        if slot:
            searchkeywords.append(slot)
            slotstring = ' and slot = (?)'
        tagstring = ''
        if tag:
            searchkeywords.append(tag)
            tagstring = ' and versiontag = (?)'
        branchstring = ''
        if branch:
            searchkeywords.append(branch)
            branchstring = ' and branch = (?)'
        order_by_string = ''
        if order_by in ("atom", "idpackage", "branch",):
            order_by_string = ' order by %s' % (order_by,)

        search_elements = 'atom,idpackage,branch'
        if just_id: search_elements = 'idpackage'

        if sensitive:
            self.cursor.execute("""
            SELECT %s FROM baseinfo WHERE atom LIKE (?) %s %s %s %s""" %  (
                search_elements,slotstring,tagstring,branchstring,order_by_string,),
                searchkeywords
            )
        else:
            self.cursor.execute("""
            SELECT %s FROM baseinfo WHERE 
            LOWER(atom) LIKE (?) %s %s %s %s""" % (
                search_elements,slotstring,tagstring,branchstring,order_by_string,),
                searchkeywords
            )
        if just_id:
            return self.fetchall2list(self.cursor.fetchall())
        return self.cursor.fetchall()

    def searchProvide(self, keyword, slot = None, tag = None, branch = None, justid = False):

        slotstring = ''
        searchkeywords = [keyword]
        if slot:
            searchkeywords.append(slot)
            slotstring = ' and baseinfo.slot = (?)'
        tagstring = ''
        if tag:
            searchkeywords.append(tag)
            tagstring = ' and baseinfo.versiontag = (?)'
        branchstring = ''
        if branch:
            searchkeywords.append(branch)
            branchstring = ' and baseinfo.branch = (?)'
        atomstring = ''
        if not justid:
            atomstring = 'baseinfo.atom,'

        self.cursor.execute("""
        SELECT %s baseinfo.idpackage FROM baseinfo,provide 
        WHERE provide.atom = (?) AND 
        provide.idpackage = baseinfo.idpackage %s %s %s""" % (
            atomstring,slotstring,tagstring,branchstring,),
            searchkeywords
        )

        if justid:
            results = self.fetchall2list(self.cursor.fetchall())
        else:
            results = self.cursor.fetchall()
        return results

    def searchPackagesByDescription(self, keyword):
        self.cursor.execute("""
        SELECT baseinfo.atom,baseinfo.idpackage FROM extrainfo,baseinfo 
        WHERE LOWER(extrainfo.description) LIKE (?) AND 
        baseinfo.idpackage = extrainfo.idpackage""", ("%"+keyword.lower()+"%",))
        return self.cursor.fetchall()

    def searchPackagesByName(self, keyword, sensitive = False, branch = None, justid = False):

        if sensitive:
            searchkeywords = [keyword]
        else:
            searchkeywords = [keyword.lower()]
        branchstring = ''
        atomstring = ''
        if not justid:
            atomstring = 'atom,'
        if branch:
            searchkeywords.append(branch)
            branchstring = ' and branch = (?)'

        if sensitive:
            self.cursor.execute("""
            SELECT %s idpackage FROM baseinfo 
            WHERE name = (?) %s""" % (atomstring, branchstring,), searchkeywords)
        else:
            self.cursor.execute("""
            SELECT %s idpackage FROM baseinfo 
            WHERE LOWER(name) = (?) %s""" % (atomstring, branchstring,), searchkeywords)

        if justid:
            results = self.fetchall2list(self.cursor.fetchall())
        else:
            results = self.cursor.fetchall()
        return results


    def searchPackagesByCategory(self, keyword, like = False, branch = None):

        searchkeywords = [keyword]
        branchstring = ''
        if branch:
            searchkeywords.append(branch)
            branchstring = 'and branch = (?)'

        if like:
            self.cursor.execute("""
            SELECT baseinfo.atom,baseinfo.idpackage FROM baseinfo,categories 
            WHERE categories.category LIKE (?) AND 
            baseinfo.idcategory = categories.idcategory %s""" % (branchstring,), searchkeywords)
        else:
            self.cursor.execute("""
            SELECT baseinfo.atom,baseinfo.idpackage FROM baseinfo,categories 
            WHERE categories.category = (?) AND 
            baseinfo.idcategory = categories.idcategory %s""" % (branchstring,), searchkeywords)

        return self.cursor.fetchall()

    def searchPackagesByNameAndCategory(self, name, category, sensitive = False, branch = None, justid = False):

        myname = name
        mycat = category
        if not sensitive:
            myname = name.lower()
            mycat = category.lower()

        searchkeywords = [myname, mycat]
        branchstring = ''
        if branch:
            searchkeywords.append(branch)
            branchstring = ' and branch = (?)'
        atomstring = ''
        if not justid:
            atomstring = 'atom,'

        if sensitive:
            self.cursor.execute("""
            SELECT %s idpackage FROM baseinfo 
            WHERE name = (?) AND 
            idcategory IN (
                SELECT idcategory FROM categories 
                WHERE category = (?)
            ) %s""" % (atomstring, branchstring,), searchkeywords)
        else:
            self.cursor.execute("""
            SELECT %s idpackage FROM baseinfo 
            WHERE LOWER(name) = (?) AND 
            idcategory IN (
                SELECT idcategory FROM categories 
                WHERE LOWER(category) = (?)
            ) %s""" % (atomstring, branchstring,), searchkeywords)

        if justid:
            results = self.fetchall2list(self.cursor.fetchall())
        else:
            results = self.cursor.fetchall()
        return results

    def isPackageScopeAvailable(self, atom, slot, revision):
        searchdata = (atom, slot, revision,)
        self.cursor.execute('SELECT idpackage FROM baseinfo where atom = (?) and slot = (?) and revision = (?)', searchdata)
        rslt = self.cursor.fetchone()
        idreason = 0
        idpackage = -1
        if rslt:
            # check if it's masked
            idpackage, idreason = self.idpackageValidator(rslt[0])
        return idpackage, idreason

    def listAllPackages(self, get_scope = False, order_by = None, branch = None, branch_operator = "="):

        branchstring = ''
        searchkeywords = []
        if branch:
            searchkeywords = [branch]
            branchstring = ' where branch %s (?)' % (branch_operator,)

        order_txt = ''
        if order_by:
            order_txt = ' order by %s' % (order_by,)
        if get_scope:
            self.cursor.execute('SELECT idpackage,atom,slot,revision FROM baseinfo'+order_txt+branchstring, searchkeywords)
        else:
            self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo'+order_txt+branchstring, searchkeywords)
        return self.cursor.fetchall()

    def listAllInjectedPackages(self, justFiles = False):
        self.cursor.execute('SELECT idpackage FROM injected')
        injecteds = self.fetchall2set(self.cursor.fetchall())
        results = set()
        # get download
        for injected in injecteds:
            download = self.retrieveDownloadURL(injected)
            if justFiles:
                results.add(download)
            else:
                results.add((download, injected))
        return results

    def listAllCounters(self, onlycounters = False, branch = None, branch_operator = "="):

        branchstring = ''
        if branch:
            branchstring = ' WHERE branch '+branch_operator+' "'+str(branch)+'"'
        if onlycounters:
            self.cursor.execute('SELECT counter FROM counters'+branchstring)
            return self.fetchall2set(self.cursor.fetchall())
        else:
            self.cursor.execute('SELECT counter,idpackage FROM counters'+branchstring)
            return self.cursor.fetchall()

    def listAllIdpackages(self, branch = None, branch_operator = "=", order_by = None):

        branchstring = ''
        orderbystring = ''
        searchkeywords = []
        if branch:
            searchkeywords.append(branch)
            branchstring = ' where branch %s (?)' % (str(branch_operator),)
        if order_by:
            orderbystring = ' order by '+order_by

        self.cursor.execute('SELECT idpackage FROM baseinfo'+branchstring+orderbystring, searchkeywords)

        try:
            if order_by:
                results = self.fetchall2list(self.cursor.fetchall())
            else:
                results = self.fetchall2set(self.cursor.fetchall())
            return results
        except self.dbapi2.OperationalError:
            if order_by:
                return []
            return set()

    def listAllDependencies(self, only_deps = False):
        if only_deps:
            self.cursor.execute('SELECT dependency FROM dependenciesreference')
            return self.fetchall2set(self.cursor.fetchall())
        else:
            self.cursor.execute('SELECT * FROM dependenciesreference')
            return self.cursor.fetchall()

    def listAllBranches(self):

        cache = self.live_cache.get('listAllBranches')
        if cache != None:
            return cache

        self.cursor.execute('SELECT distinct branch FROM baseinfo')
        results = self.fetchall2set(self.cursor.fetchall())

        self.live_cache['listAllBranches'] = results.copy()
        return results

    def listIdPackagesInIdcategory(self, idcategory, order_by = 'atom'):
        order_by_string = ''
        if order_by in ("atom", "name", "version",):
            order_by_string = ' ORDER BY %s' % (order_by,)
        self.cursor.execute('SELECT idpackage FROM baseinfo where idcategory = (?)'+order_by_string, (idcategory,))
        return self.fetchall2set(self.cursor.fetchall())

    def listIdpackageDependencies(self, idpackage):
        self.cursor.execute("""
        SELECT dependenciesreference.iddependency,dependenciesreference.dependency FROM dependenciesreference,dependencies 
        WHERE dependencies.idpackage = (?) AND 
        dependenciesreference.iddependency = dependencies.iddependency""", (idpackage,))
        return set(self.cursor.fetchall())

    def listBranchPackagesTbz2(self, branch, do_sort = True, full_path = False):
        order_string = ''
        if do_sort: order_string = 'ORDER BY extrainfo.download'
        self.cursor.execute("""
        SELECT extrainfo.download FROM baseinfo,extrainfo 
        WHERE baseinfo.branch = (?) AND 
        baseinfo.idpackage = extrainfo.idpackage %s""" % (order_string,), (branch,))

        if do_sort: results = self.fetchall2list(self.cursor.fetchall())
        else: results = self.fetchall2set(self.cursor.fetchall())

        if not full_path: results = [os.path.basename(x) for x in results]
        if do_sort: return results
        return set(results)

    def listAllFiles(self, clean = False, count = False):
        self.connection.text_factory = lambda x: unicode(x, "raw_unicode_escape")
        if count:
            self.cursor.execute('SELECT count(file) FROM content')
        else:
            self.cursor.execute('SELECT file FROM content')
        if count:
            return self.cursor.fetchone()[0]
        else:
            if clean:
                return self.fetchall2set(self.cursor.fetchall())
            else:
                return self.fetchall2list(self.cursor.fetchall())

    def listAllCategories(self, order_by = ''):
        order_by_string = ''
        if order_by: order_by_string = ' order by %s' % (order_by,)
        self.cursor.execute('SELECT idcategory,category FROM categories %s' % (
            order_by_string,))
        return self.cursor.fetchall()

    def listConfigProtectDirectories(self, mask = False):
        mask_t = ''
        if mask: mask_t = 'mask'
        self.cursor.execute("""
        SELECT DISTINCT(protect) FROM configprotectreference 
        WHERE idprotect >= 1 AND 
        idprotect <= (SELECT max(idprotect) FROM configprotect%s) 
        ORDER BY protect""" % (mask_t,))
        results = self.fetchall2set(self.cursor.fetchall())
        dirs = set()
        for mystr in results:
            dirs |= set(map(unicode, mystr.split()))
        return sorted(list(dirs))

    def switchBranch(self, idpackage, tobranch):

        key, slot = self.retrieveKeySlot(idpackage)

        # if there are entries already, remove idpackage directly
        my_idpackage, result = self.atomMatch(key, matchSlot = slot,
            matchBranches = (tobranch,))
        if my_idpackage != -1: return False

        # otherwise, update the old one (set the new branch)
        with self.WriteLock:
            self.cursor.execute("""
            UPDATE baseinfo SET branch = (?) 
            WHERE idpackage = (?)""", (tobranch, idpackage,))
            self.commitChanges()
            self.clearCache()
        return True

    def databaseStructureUpdates(self):

        old_readonly = self.readOnly
        self.readOnly = False

        if not self.doesTableExist("licensedata"):
            self.createLicensedataTable()

        if not self.doesTableExist("licenses_accepted") and \
            (self.dbname == etpConst['clientdbid']):
            self.createLicensesAcceptedTable()

        if not self.doesTableExist("trashedcounters"):
            self.createTrashedcountersTable()

        if not self.doesTableExist("counters"):
            self.createCountersTable()

        if not self.doesTableExist("installedtable") and \
            (self.dbname == etpConst['clientdbid']):
            self.createInstalledTable()

        if self.doesTableExist("installedtable") and \
            not self.doesColumnInTableExist("installedtable","source"):
            self.createInstalledTableSource()

        if not self.doesTableExist("categoriesdescription"):
            self.createCategoriesdescriptionTable()

        if not self.doesTableExist('packagesets'):
            self.createPackagesetsTable()

        if not self.doesTableExist('packagechangelogs'):
            self.createPackagechangelogsTable()

        if not self.doesTableExist('automergefiles'):
            self.createAutomergefilesTable()

        if not self.doesTableExist('packagesignatures'):
            self.createPackagesignaturesTable()

        if not self.doesTableExist('packagespmphases'):
            self.createPackagespmphases()

        self.readOnly = old_readonly
        self.connection.commit()

    def validateDatabase(self):
        self.cursor.execute('select name from SQLITE_MASTER where type = (?) and name = (?)', ("table", "baseinfo"))
        rslt = self.cursor.fetchone()
        if rslt == None:
            mytxt = _("baseinfo table not found. Either does not exist or corrupted.")
            raise SystemDatabaseError("SystemDatabaseError: %s" % (mytxt,))
        self.cursor.execute('select name from SQLITE_MASTER where type = (?) and name = (?)', ("table", "extrainfo"))
        rslt = self.cursor.fetchone()
        if rslt == None:
            mytxt = _("extrainfo table not found. Either does not exist or corrupted.")
            raise SystemDatabaseError("SystemDatabaseError: %s" % (mytxt,))

    def getIdpackagesDifferences(self, foreign_idpackages):
        myids = self.listAllIdpackages()
        if isinstance(foreign_idpackages, (list, tuple,)):
            outids = set(foreign_idpackages)
        else:
            outids = foreign_idpackages
        added_ids = outids - myids
        removed_ids = myids - outids
        return added_ids, removed_ids

    def uniformBranch(self, branch):
        with self.WriteLock:
            self.cursor.execute('UPDATE baseinfo SET branch = (?)', (branch,))
            self.commitChanges()
            self.clearCache()

    def alignDatabases(self, dbconn, force = False, output_header = "  ", align_limit = 300):

        added_ids, removed_ids = self.getIdpackagesDifferences(dbconn.listAllIdpackages())

        if not force:
            if len(added_ids) > align_limit: # too much hassle
                return 0
            if len(removed_ids) > align_limit: # too much hassle
                return 0

        if not added_ids and not removed_ids:
            return -1

        mytxt = red("%s, %s ...") % (_("Syncing current database"), _("please wait"),)
        self.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = output_header,
            back = True
        )
        maxcount = len(removed_ids)
        mycount = 0
        for idpackage in removed_ids:
            mycount += 1
            mytxt = "%s: %s" % (red(_("Removing entry")), blue(str(self.retrieveAtom(idpackage))),)
            self.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = output_header,
                back = True,
                count = (mycount, maxcount)
            )
            self.removePackage(idpackage, do_cleanup = False, do_commit = False)

        maxcount = len(added_ids)
        mycount = 0
        for idpackage in added_ids:
            mycount += 1
            mytxt = "%s: %s" % (red(_("Adding entry")), blue(str(dbconn.retrieveAtom(idpackage))),)
            self.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = output_header,
                back = True,
                count = (mycount, maxcount)
            )
            mydata = dbconn.getPackageData(idpackage, get_content = True, content_insert_formatted = True)
            self.addPackage(
                mydata,
                revision = mydata['revision'],
                idpackage = idpackage,
                do_remove = False,
                do_commit = False,
                formatted_content = True
            )

        # do some cleanups
        self.doCleanups()
        # clear caches
        self.clearCache()
        self.commitChanges()
        self.regenerateDependsTable(output = False)
        dbconn.clearCache()

        # verify both checksums, if they don't match, bomb out
        mycheck = self.database_checksum(do_order = True, strict = False)
        outcheck = dbconn.database_checksum(do_order = True, strict = False)
        if mycheck == outcheck:
            return 1
        return 0

    def checkDatabaseApi(self):

        dbapi = self.getApi()
        if int(dbapi) > int(etpConst['etpapi']):
            self.updateProgress(
                red(_("Repository EAPI > Entropy EAPI. Please update Equo/Entropy as soon as possible !")),
                importance = 1,
                type = "warning",
                header = " * ! * ! * ! * "
            )

    def doDatabaseImport(self, dumpfile, dbfile):
        sqlite3_exec = "/usr/bin/sqlite3 %s < %s" % (dbfile, dumpfile,)
        retcode = subprocess.call(sqlite3_exec, shell = True)
        return retcode

    def doDatabaseExport(self, dumpfile, gentle_with_tables = True):

        dumpfile.write("BEGIN TRANSACTION;\n")
        self.cursor.execute("SELECT name, type, sql FROM sqlite_master WHERE sql NOT NULL AND type=='table'")
        for name, x, sql in self.cursor.fetchall():

            self.updateProgress(
                red("%s " % (_("Exporting database table"),) )+"["+blue(str(name))+"]",
                importance = 0,
                type = "info",
                back = True,
                header = "   "
            )

            if name == "sqlite_sequence":
                dumpfile.write("DELETE FROM sqlite_sequence;\n")
            elif name == "sqlite_stat1":
                dumpfile.write("ANALYZE sqlite_master;\n")
            elif name.startswith("sqlite_"):
                continue
            else:
                t_cmd = "CREATE TABLE"
                if sql.startswith(t_cmd) and gentle_with_tables:
                    sql = "CREATE TABLE IF NOT EXISTS"+sql[len(t_cmd):]
                dumpfile.write("%s;\n" % sql)

            self.cursor.execute("PRAGMA table_info('%s')" % name)
            cols = [str(r[1]) for r in self.cursor.fetchall()]
            q = "SELECT 'INSERT INTO \"%(tbl_name)s\" VALUES("
            q += ", ".join(["'||quote(" + x + ")||'" for x in cols])
            q += ")' FROM '%(tbl_name)s'"
            self.cursor.execute(q % {'tbl_name': name})
            self.connection.text_factory = lambda x: unicode(x, "raw_unicode_escape")
            for row in self.cursor:
                dumpfile.write("%s;\n" % str(row[0].encode('raw_unicode_escape')))

        self.cursor.execute("SELECT name, type, sql FROM sqlite_master WHERE sql NOT NULL AND type!='table' AND type!='meta'")
        for name, x, sql in self.cursor.fetchall():
            dumpfile.write("%s;\n" % sql)

        dumpfile.write("COMMIT;\n")
        try:
            dumpfile.flush()
        except:
            pass
        self.updateProgress(
            red(_("Database Export completed.")),
            importance = 0,
            type = "info",
            header = "   "
        )
        # remember to close the file

    def listAllTables(self):
        self.cursor.execute("""
        SELECT name FROM SQLITE_MASTER WHERE type = "table"
        """)
        return self.fetchall2list(self.cursor.fetchall())

    def doesTableExist(self, table):
        self.cursor.execute('select name from SQLITE_MASTER where type = "table" and name = (?)', (table,))
        rslt = self.cursor.fetchone()
        if rslt == None:
            return False
        return True

    def doesColumnInTableExist(self, table, column):
        self.cursor.execute('PRAGMA table_info( %s )' % (table,))
        rslt = (x[1] for x in self.cursor.fetchall())
        if column in rslt:
            return True
        return False

    def database_checksum(self, do_order = False, strict = True, strings = False):

        c_tup = ("database_checksum", do_order, strict, strings,)
        cache = self.live_cache.get(c_tup)
        if cache != None: return cache

        idpackage_order = ''
        category_order = ''
        license_order = ''
        flags_order = ''
        if do_order:
            idpackage_order = 'order by idpackage'
            category_order = 'order by category'
            license_order = 'order by license'
            flags_order = 'order by chost'

        def do_update_md5(m, cursor):
            mydata = cursor.fetchall()
            for record in mydata:
                for item in record:
                    m.update(str(item))

        if strings:
            import hashlib
            m = hashlib.md5()

        self.cursor.execute("""
        SELECT idpackage,atom,name,version,versiontag,
        revision,branch,slot,etpapi,trigger FROM 
        baseinfo %s""" % (idpackage_order,))
        if strings:
            do_update_md5(m, self.cursor)
        else:
            a_hash = hash(tuple(self.cursor.fetchall()))
        self.cursor.execute("""
        SELECT idpackage,description,homepage,
        download,size,digest,datecreation FROM 
        extrainfo %s""" % (idpackage_order,))
        if strings:
            do_update_md5(m, self.cursor)
        else:
            b_hash = hash(tuple(self.cursor.fetchall()))
        self.cursor.execute('select category from categories %s' % (category_order,))
        if strings:
            do_update_md5(m, self.cursor)
        else:
            c_hash = hash(tuple(self.cursor.fetchall()))
        d_hash = '0'
        e_hash = '0'
        if strict:
            self.cursor.execute('select * from licenses %s' % (license_order,))
            if strings:
                do_update_md5(m, self.cursor)
            else:
                d_hash = hash(tuple(self.cursor.fetchall()))
            self.cursor.execute('select * from flags %s' % (flags_order,))
            if strings:
                do_update_md5(m, self.cursor)
            else:
                e_hash = hash(tuple(self.cursor.fetchall()))

        if strings:
            result = m.hexdigest()
        else:
            result = "%s:%s:%s:%s:%s" % (a_hash, b_hash, c_hash, d_hash, e_hash,)

        self.live_cache[c_tup] = result[:]
        return result


########################################################
####
##   Client Database API / but also used by server part
#

    def updateInstalledTableSource(self, idpackage, source):
        with self.WriteLock:
            self.cursor.execute("""
            UPDATE installedtable SET source = (?) WHERE idpackage = (?)
            """, (source, idpackage,))

    def addPackageToInstalledTable(self, idpackage, repoid, source = 0):
        with self.WriteLock:
            self.cursor.execute('INSERT into installedtable VALUES (?,?,?)',
                (idpackage, repoid, source,))
            # self.commitChanges()

    def retrievePackageFromInstalledTable(self, idpackage):
        with self.WriteLock:
            try:
                self.cursor.execute("""
                SELECT repositoryname FROM installedtable 
                WHERE idpackage = (?)""", (idpackage,))
                return self.cursor.fetchone()[0]
            except (self.dbapi2.OperationalError,TypeError,):
                return 'Not available'

    def removePackageFromInstalledTable(self, idpackage):
        with self.WriteLock:
            self.cursor.execute("""
            DELETE FROM installedtable
            WHERE idpackage = (?)""", (idpackage,))

    def removePackageFromDependsTable(self, idpackage):
        with self.WriteLock:
            try:
                self.cursor.execute('DELETE FROM dependstable WHERE idpackage = (?)', (idpackage,))
                return 0
            except (self.dbapi2.OperationalError,):
                return 1 # need reinit

    def createDependsTable(self):
        with self.WriteLock:
            self.cursor.executescript("""
                DROP TABLE IF EXISTS dependstable;
                CREATE TABLE dependstable ( iddependency INTEGER PRIMARY KEY, idpackage INTEGER );
                INSERT into dependstable VALUES (-1,-1);
            """)
            if self.indexing:
                self.cursor.execute('CREATE INDEX IF NOT EXISTS dependsindex_idpackage ON dependstable ( idpackage )')
            self.commitChanges()

    def sanitizeDependsTable(self):
        with self.WriteLock:
            self.cursor.execute('DELETE FROM dependstable where iddependency = -1')
            self.commitChanges()

    def isDependsTableSane(self):
        try:
            self.cursor.execute('SELECT iddependency FROM dependstable WHERE iddependency = -1')
        except (self.dbapi2.OperationalError,):
            return False # table does not exist, please regenerate and re-run
        status = self.cursor.fetchone()
        if status: return False

        self.cursor.execute('select count(*) from dependstable')
        dependstable_count = self.cursor.fetchone()
        if dependstable_count < 2:
            return False
        return True

    def createXpakTable(self):
        with self.WriteLock:
            self.cursor.execute('CREATE TABLE xpakdata ( idpackage INTEGER PRIMARY KEY, data BLOB );')
            self.commitChanges()

    def storeXpakMetadata(self, idpackage, blob):
        with self.WriteLock:
            self.cursor.execute('INSERT into xpakdata VALUES (?,?)', (int(idpackage), buffer(blob),))
            self.commitChanges()

    def retrieveXpakMetadata(self, idpackage):
        try:
            self.cursor.execute('SELECT data from xpakdata where idpackage = (?)', (idpackage,))
            mydata = self.cursor.fetchone()
            if not mydata:
                return ""
            return mydata[0]
        except:
            return ""

    def createCountersTable(self):
        with self.WriteLock:
            self.cursor.execute("CREATE TABLE IF NOT EXISTS counters ( counter INTEGER, idpackage INTEGER PRIMARY KEY, branch VARCHAR );")

    def dropAllIndexes(self):
        self.cursor.execute('SELECT name FROM SQLITE_MASTER WHERE type = "index"')
        indexes = self.fetchall2set(self.cursor.fetchall())
        with self.WriteLock:
            for index in indexes:
                if not index.startswith("sqlite"):
                    self.cursor.execute('DROP INDEX IF EXISTS %s' % (index,))

    def listAllIndexes(self, only_entropy = True):
        self.cursor.execute('SELECT name FROM SQLITE_MASTER WHERE type = "index"')
        indexes = self.fetchall2set(self.cursor.fetchall())
        if not only_entropy:
            return indexes
        myindexes = set()
        for index in indexes:
            if index.startswith("sqlite"):
                continue
            myindexes.add(index)
        return myindexes


    def createAllIndexes(self):
        self.createContentIndex()
        self.createBaseinfoIndex()
        self.createKeywordsIndex()
        self.createDependenciesIndex()
        self.createProvideIndex()
        self.createConflictsIndex()
        self.createExtrainfoIndex()
        self.createNeededIndex()
        self.createUseflagsIndex()
        self.createLicensedataIndex()
        self.createLicensesIndex()
        self.createConfigProtectReferenceIndex()
        self.createMessagesIndex()
        self.createSourcesIndex()
        self.createCountersIndex()
        self.createEclassesIndex()
        self.createCategoriesIndex()
        self.createCompileFlagsIndex()
        self.createPackagesetsIndex()
        self.createAutomergefilesIndex()

    def createPackagesetsIndex(self):
        if self.indexing:
            with self.WriteLock:
                try:
                    self.cursor.execute('CREATE INDEX IF NOT EXISTS packagesetsindex ON packagesets ( setname )')
                    self.commitChanges()
                except self.dbapi2.OperationalError:
                    pass

    def createAutomergefilesIndex(self):
        if self.indexing:
            with self.WriteLock:
                try:
                    self.cursor.execute("""
                        CREATE INDEX IF NOT EXISTS automergefiles_idpackage 
                        ON automergefiles ( idpackage )
                    """)
                    self.cursor.execute("""
                        CREATE INDEX IF NOT EXISTS automergefiles_file_md5 
                        ON automergefiles ( configfile, md5 )
                    """)
                except self.dbapi2.OperationalError:
                    pass

    def createNeededIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS neededindex ON neededreference ( library );
                    CREATE INDEX IF NOT EXISTS neededindex_idneeded ON needed ( idneeded );
                    CREATE INDEX IF NOT EXISTS neededindex_idpackage ON needed ( idpackage );
                    CREATE INDEX IF NOT EXISTS neededindex_elfclass ON needed ( elfclass );
                """)

    def createMessagesIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.execute('CREATE INDEX IF NOT EXISTS messagesindex ON messages ( idpackage )')

    def createCompileFlagsIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.execute('CREATE INDEX IF NOT EXISTS flagsindex ON flags ( chost,cflags,cxxflags )')

    def createUseflagsIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS useflagsindex_useflags_idpackage ON useflags ( idpackage );
                    CREATE INDEX IF NOT EXISTS useflagsindex_useflags_idflag ON useflags ( idflag );
                    CREATE INDEX IF NOT EXISTS useflagsindex ON useflagsreference ( flagname );
                """)

    def createContentIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS contentindex_couple ON content ( idpackage );
                    CREATE INDEX IF NOT EXISTS contentindex_file ON content ( file );
                """)

    def createConfigProtectReferenceIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.execute('CREATE INDEX IF NOT EXISTS configprotectreferenceindex ON configprotectreference ( protect )')

    def createBaseinfoIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS baseindex_atom ON baseinfo ( atom );
                    CREATE INDEX IF NOT EXISTS baseindex_branch_name ON baseinfo ( name,branch );
                    CREATE INDEX IF NOT EXISTS baseindex_branch_name_idcategory ON baseinfo ( name,idcategory,branch );
                    CREATE INDEX IF NOT EXISTS baseindex_idcategory ON baseinfo ( idcategory );
                """)

    def createLicensedataIndex(self):
        if self.indexing:
            if not self.doesTableExist("licensedata"):
                return
            with self.WriteLock:
                self.cursor.execute('CREATE INDEX IF NOT EXISTS licensedataindex ON licensedata ( licensename )')

    def createLicensesIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.execute('CREATE INDEX IF NOT EXISTS licensesindex ON licenses ( license )')

    def createCategoriesIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.execute('CREATE INDEX IF NOT EXISTS categoriesindex_category ON categories ( category )')

    def createKeywordsIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS keywordsreferenceindex ON keywordsreference ( keywordname );
                    CREATE INDEX IF NOT EXISTS keywordsindex_idpackage ON keywords ( idpackage );
                    CREATE INDEX IF NOT EXISTS keywordsindex_idkeyword ON keywords ( idkeyword );
                """)

    def createDependenciesIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS dependenciesindex_idpackage ON dependencies ( idpackage );
                    CREATE INDEX IF NOT EXISTS dependenciesindex_iddependency ON dependencies ( iddependency );
                    CREATE INDEX IF NOT EXISTS dependenciesreferenceindex_dependency ON dependenciesreference ( dependency );
                """)

    def createCountersIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS countersindex_idpackage ON counters ( idpackage );
                    CREATE INDEX IF NOT EXISTS countersindex_counter ON counters ( counter );
                """)

    def createSourcesIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS sourcesindex_idpackage ON sources ( idpackage );
                    CREATE INDEX IF NOT EXISTS sourcesindex_idsource ON sources ( idsource );
                    CREATE INDEX IF NOT EXISTS sourcesreferenceindex_source ON sourcesreference ( source );
                """)

    def createProvideIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS provideindex_idpackage ON provide ( idpackage );
                    CREATE INDEX IF NOT EXISTS provideindex_atom ON provide ( atom );
                """)

    def createConflictsIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS conflictsindex_idpackage ON conflicts ( idpackage );
                    CREATE INDEX IF NOT EXISTS conflictsindex_atom ON conflicts ( conflict );
                """)

    def createExtrainfoIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.execute('CREATE INDEX IF NOT EXISTS extrainfoindex ON extrainfo ( description )')
                self.cursor.execute('CREATE INDEX IF NOT EXISTS extrainfoindex_pkgindex ON extrainfo ( idpackage )')

    def createEclassesIndex(self):
        if self.indexing:
            with self.WriteLock:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS eclassesindex_idpackage ON eclasses ( idpackage );
                    CREATE INDEX IF NOT EXISTS eclassesindex_idclass ON eclasses ( idclass );
                    CREATE INDEX IF NOT EXISTS eclassesreferenceindex_classname ON eclassesreference ( classname );
                """)

    def regenerateCountersTable(self, vdb_path, output = False):
        self.createCountersTable()
        # this is necessary now, counters table should be empty
        self.cursor.execute("DELETE FROM counters;")
        # assign a counter to an idpackage
        myids = self.listAllIdpackages()
        counter_path = etpConst['spm']['xpak_entries']['counter']
        for myid in myids:
            # get atom
            myatom = self.retrieveAtom(myid)
            mybranch = self.retrieveBranch(myid)
            myatom = self.entropyTools.remove_tag(myatom)
            myatomcounterpath = "%s%s/%s" % (vdb_path, myatom, counter_path,)
            if os.path.isfile(myatomcounterpath):
                try:
                    with open(myatomcounterpath, "r") as f:
                        counter = int(f.readline().strip())
                except:
                    if output:
                        mytxt = "%s: %s: %s" % (
                            bold(_("ATTENTION")),
                            red(_("cannot open Spm counter file for")),
                            bold(myatom),
                        )
                        self.updateProgress(
                            mytxt,
                            importance = 1,
                            type = "warning"
                        )
                    continue
                # insert id+counter
                with self.WriteLock:
                    try:
                        self.cursor.execute(
                                'INSERT into counters VALUES '
                                '(?,?,?)', ( counter, myid, mybranch )
                        )
                    except self.dbapi2.IntegrityError:
                        if output:
                            mytxt = "%s: %s: %s" % (
                                bold(_("ATTENTION")),
                                red(_("counter for atom is duplicated, ignoring")),
                                bold(myatom),
                            )
                            self.updateProgress(
                                mytxt,
                                importance = 1,
                                type = "warning"
                            )
                        continue
                        # don't trust counters, they might not be unique

        self.commitChanges()

    def clearTreeupdatesEntries(self, repository):
        if not self.doesTableExist("treeupdates"):
            self.createTreeupdatesTable()
        # treeupdates
        with self.WriteLock:
            self.cursor.execute("DELETE FROM treeupdates WHERE repository = (?)", (repository,))
            self.commitChanges()

    def resetTreeupdatesDigests(self):
        with self.WriteLock:
            self.cursor.execute('UPDATE treeupdates SET digest = "-1"')
            self.commitChanges()

    def migrateCountersTable(self):
        with self.WriteLock:
            self._migrateCountersTable()

    def _migrateCountersTable(self):
        self.cursor.execute('DROP TABLE IF EXISTS counterstemp;')
        self.cursor.execute('CREATE TABLE counterstemp ( counter INTEGER, idpackage INTEGER, branch VARCHAR, PRIMARY KEY(idpackage,branch) );')
        self.cursor.execute('select * from counters')
        countersdata = self.cursor.fetchall()
        self.cursor.executemany('INSERT INTO counterstemp VALUES (?,?,?)', countersdata)
        self.cursor.execute('DROP TABLE counters')
        self.cursor.execute('ALTER TABLE counterstemp RENAME TO counters')
        self.commitChanges()

    def createInstalledTableSource(self):
        with self.WriteLock:
            self.cursor.execute('ALTER TABLE installedtable ADD source INTEGER;')
            self.cursor.execute("""
            UPDATE installedtable SET source = (?)
            """, (etpConst['install_sources']['unknown'],))

    def createPackagechangelogsTable(self):
        with self.WriteLock:
            self.cursor.execute('CREATE TABLE packagechangelogs ( category VARCHAR, name VARCHAR, changelog BLOB, PRIMARY KEY (category, name));')

    def createAutomergefilesTable(self):
        with self.WriteLock:
            self.cursor.execute('CREATE TABLE automergefiles ( idpackage INTEGER, configfile VARCHAR, md5 VARCHAR );')

    def createPackagesignaturesTable(self):
        with self.WriteLock:
            self.cursor.execute('CREATE TABLE packagesignatures ( idpackage INTEGER PRIMARY KEY, sha1 VARCHAR, sha256 VARCHAR, sha512 VARCHAR );')

    def createPackagespmphases(self):
        with self.WriteLock:
            self.cursor.execute("""
                CREATE TABLE packagespmphases (
                    idpackage INTEGER PRIMARY KEY,
                    phases VARCHAR
                );
            """)

    def createPackagesetsTable(self):
        with self.WriteLock:
            self.cursor.execute('CREATE TABLE packagesets ( setname VARCHAR, dependency VARCHAR );')

    def createCategoriesdescriptionTable(self):
        with self.WriteLock:
            self.cursor.execute('CREATE TABLE categoriesdescription ( category VARCHAR, locale VARCHAR, description VARCHAR );')

    def createTreeupdatesTable(self):
        with self.WriteLock:
            self.cursor.execute('CREATE TABLE treeupdates ( repository VARCHAR PRIMARY KEY, digest VARCHAR );')

    def createLicensedataTable(self):
        with self.WriteLock:
            self.cursor.execute('CREATE TABLE licensedata ( licensename VARCHAR UNIQUE, text BLOB, compressed INTEGER );')

    def createLicensesAcceptedTable(self):
        with self.WriteLock:
            self.cursor.execute('CREATE TABLE licenses_accepted ( licensename VARCHAR UNIQUE );')

    def createTrashedcountersTable(self):
        with self.WriteLock:
            self.cursor.execute('CREATE TABLE trashedcounters ( counter INTEGER );')

    def createInstalledTable(self):
        with self.WriteLock:
            self.cursor.execute('DROP TABLE IF EXISTS installedtable;')
            self.cursor.execute('CREATE TABLE installedtable ( idpackage INTEGER PRIMARY KEY, repositoryname VARCHAR, source INTEGER );')

    def addDependsRelationToDependsTable(self, iterable):
        with self.WriteLock:
            self.cursor.executemany('INSERT into dependstable VALUES (?,?)', iterable)
            if (self.entropyTools.is_user_in_entropy_group()) and \
                (self.dbname.startswith(etpConst['serverdbid'])):
                    # force commit even if readonly, this will allow to automagically fix dependstable server side
                    self.connection.commit() # we don't care much about syncing the database since it's quite trivial

    def clearDependsTable(self):
        if not self.doesTableExist("dependstable"): return
        self.cursor.execute("DROP TABLE IF EXISTS dependstable")

    '''
       @description: recreate dependstable table in the chosen database, it's used for caching searchDepends requests
       @input Nothing
       @output: Nothing
    '''
    def regenerateDependsTable(self, output = True):

        depends = self.listAllDependencies()
        self.createDependsTable()
        count = 0
        total = len(depends)
        mydata = set()
        am = self.atomMatch
        up = self.updateProgress
        for iddep, atom in depends:
            count += 1
            if output and ((count == 0) or (count % 150 == 0) or \
                (count == total)):

                up( red("Resolving %s") % (atom,), importance = 0,
                    type = "info", back = True, count = (count, total)
                )
            idpackage, rc = am(atom)
            if idpackage == -1: continue
            mydata.add((iddep, idpackage))

        if mydata: self.addDependsRelationToDependsTable(mydata)

        # now validate dependstable
        self.sanitizeDependsTable()

    def moveCountersToBranch(self, to_branch):
        with self.WriteLock:
            self.cursor.execute('UPDATE counters SET branch = (?)', to_branch)
            self.commitChanges()
            self.clearCache()

    def atomMatchFetchCache(self, *args):
        if self.xcache:
            cached = self.dumpTools.loadobj("%s/%s/%s" % (self.dbMatchCacheKey, self.dbname, hash(tuple(args)),))
            if cached != None: return cached

    def atomMatchStoreCache(self, *args, **kwargs):
        if self.xcache:
            self.Cacher.push("%s/%s/%s" % (
                self.dbMatchCacheKey,self.dbname,hash(tuple(args)),),
                kwargs.get('result')
            )

    def atomMatchValidateCache(self, cached_obj, multiMatch, extendedResults):

        # time wasted for a reason
        data, rc = cached_obj
        if rc != 0: return cached_obj

        if (not extendedResults) and (not multiMatch):
            if not self.isIDPackageAvailable(data): return None
        elif extendedResults and (not multiMatch):
            # ((idpackage,0,version,versiontag,revision,),0)
            if not self.isIDPackageAvailable(data[0]): return None
        elif extendedResults and multiMatch:
            # (set([(idpackage,0,version,version_tag,revision) for x in dbpkginfo]),0)
            idpackages = set([x[0] for x in data])
            if not self.areIDPackagesAvailable(idpackages): return None
        elif (not extendedResults) and multiMatch:
            # (set([x[0] for x in dbpkginfo]),0)
            idpackages = set(data)
            if not self.areIDPackagesAvailable(idpackages): return None

        return cached_obj

    def _idpackageValidator_live(self, idpackage, reponame):
        if (idpackage, reponame) in self.SystemSettings['live_packagemasking']['mask_matches']:
            # do not cache this
            return -1, self.SystemSettings['pkg_masking_reference']['user_live_mask']
        elif (idpackage, reponame) in self.SystemSettings['live_packagemasking']['unmask_matches']:
            return idpackage, self.SystemSettings['pkg_masking_reference']['user_live_unmask']

    def _idpackageValidator_user_package_mask(self, idpackage, reponame, live):
        # check if user package.mask needs it masked

        mykw = "%smask_ids" % (reponame,)
        user_package_mask_ids = self.SystemSettings.get(mykw)
        if not isinstance(user_package_mask_ids, set):
            user_package_mask_ids = set()
            for atom in self.SystemSettings['mask']:
                matches, r = self.atomMatch(atom, multiMatch = True, packagesFilter = False)
                if r != 0: continue
                user_package_mask_ids |= set(matches)
            self.SystemSettings[mykw] = user_package_mask_ids
        if idpackage in user_package_mask_ids:
            # sorry, masked
            myr = self.SystemSettings['pkg_masking_reference']['user_package_mask']
            try:
                validator_cache = self.SystemSettings[self.client_settings_plugin_id]['masking_validation']['cache']
                validator_cache[(idpackage, reponame, live)] = -1, myr
            except KeyError: # system settings client plugin not found
                pass
            return -1, myr

    def _idpackageValidator_user_package_unmask(self, idpackage, reponame, live):
        # see if we can unmask by just lookin into user package.unmask stuff -> self.SystemSettings['unmask']
        mykw = "%sunmask_ids" % (reponame,)
        user_package_unmask_ids = self.SystemSettings.get(mykw)
        if not isinstance(user_package_unmask_ids, set):
            user_package_unmask_ids = set()
            for atom in self.SystemSettings['unmask']:
                matches, r = self.atomMatch(atom, multiMatch = True, packagesFilter = False)
                if r != 0: continue
                user_package_unmask_ids |= set(matches)
            self.SystemSettings[mykw] = user_package_unmask_ids
        if idpackage in user_package_unmask_ids:
            myr = self.SystemSettings['pkg_masking_reference']['user_package_unmask']
            try:
                validator_cache = self.SystemSettings[self.client_settings_plugin_id]['masking_validation']['cache']
                validator_cache[(idpackage, reponame, live)] = idpackage, myr
            except KeyError: # system settings client plugin not found
                pass
            return idpackage, myr

    def _idpackageValidator_packages_db_mask(self, idpackage, reponame, live):
        # check if repository packages.db.mask needs it masked
        repos_mask = self.SystemSettings['repos_mask']
        repomask = repos_mask.get(reponame)
        if isinstance(repomask, set):
            # first, seek into generic masking, all branches
            mask_repo_id = "%s_ids@@:of:%s" % (reponame, reponame,) # avoid issues with repository names
            repomask_ids = repos_mask.get(mask_repo_id)
            if not isinstance(repomask_ids, set):
                repomask_ids = set()
                for atom in repomask:
                    matches, r = self.atomMatch(atom, multiMatch = True, packagesFilter = False)
                    if r != 0: continue
                    repomask_ids |= set(matches)
                repos_mask[mask_repo_id] = repomask_ids
            if idpackage in repomask_ids:
                myr = self.SystemSettings['pkg_masking_reference']['repository_packages_db_mask']
                try:
                    validator_cache = self.SystemSettings[self.client_settings_plugin_id]['masking_validation']['cache']
                    validator_cache[(idpackage, reponame, live)] = -1, myr
                except KeyError: # system settings client plugin not found
                    pass
                return -1, myr

    def _idpackageValidator_package_license_mask(self, idpackage, reponame, live):
        if self.SystemSettings['license_mask']:
            mylicenses = self.retrieveLicense(idpackage)
            mylicenses = mylicenses.strip().split()
            lic_mask = self.SystemSettings['license_mask']
            for mylicense in mylicenses:
                if mylicense not in lic_mask: continue
                myr = self.SystemSettings['pkg_masking_reference']['user_license_mask']
                try:
                    validator_cache = self.SystemSettings[self.client_settings_plugin_id]['masking_validation']['cache']
                    validator_cache[(idpackage, reponame, live)] = -1, myr
                except KeyError: # system settings client plugin not found
                    pass
                return -1, myr

    def _idpackageValidator_keyword_mask(self, idpackage, reponame, live):

        mykeywords = self.retrieveKeywords(idpackage)
        # WORKAROUND for buggy entries
        if not mykeywords: mykeywords = [''] # ** is fine then
        # firstly, check if package keywords are in etpConst['keywords']
        # (universal keywords have been merged from package.mask)
        for key in etpConst['keywords']:
            if key not in mykeywords: continue
            myr = self.SystemSettings['pkg_masking_reference']['system_keyword']
            try:
                validator_cache = self.SystemSettings[self.client_settings_plugin_id]['masking_validation']['cache']
                validator_cache[(idpackage, reponame, live)] = idpackage, myr
            except KeyError: # system settings client plugin not found
                pass
            return idpackage, myr

        # if we get here, it means we didn't find mykeywords in etpConst['keywords']
        # we need to seek self.SystemSettings['keywords']
        # seek in repository first
        if reponame in self.SystemSettings['keywords']['repositories']:
            for keyword in self.SystemSettings['keywords']['repositories'][reponame]:
                if keyword not in mykeywords: continue
                keyword_data = self.SystemSettings['keywords']['repositories'][reponame].get(keyword)
                if not keyword_data: continue
                if "*" in keyword_data: # all packages in this repo with keyword "keyword" are ok
                    myr = self.SystemSettings['pkg_masking_reference']['user_repo_package_keywords_all']
                    try:
                        validator_cache = self.SystemSettings[self.client_settings_plugin_id]['masking_validation']['cache']
                        validator_cache[(idpackage, reponame, live)] = idpackage, myr
                    except KeyError: # system settings client plugin not found
                        pass
                    return idpackage, myr
                kwd_key = "%s_ids" % (keyword,)
                keyword_data_ids = self.SystemSettings['keywords']['repositories'][reponame].get(kwd_key)
                if not isinstance(keyword_data_ids, set):
                    keyword_data_ids = set()
                    for atom in keyword_data:
                        matches, r = self.atomMatch(atom, multiMatch = True, packagesFilter = False)
                        if r != 0: continue
                        keyword_data_ids |= matches
                    self.SystemSettings['keywords']['repositories'][reponame][kwd_key] = keyword_data_ids
                if idpackage in keyword_data_ids:
                    myr = self.SystemSettings['pkg_masking_reference']['user_repo_package_keywords']
                    try:
                        validator_cache = self.SystemSettings[self.client_settings_plugin_id]['masking_validation']['cache']
                        validator_cache[(idpackage, reponame, live)] = idpackage, myr
                    except KeyError: # system settings client plugin not found
                        pass
                    return idpackage, myr

        # if we get here, it means we didn't find a match in repositories
        # so we scan packages, last chance
        for keyword in self.SystemSettings['keywords']['packages']:
            # first of all check if keyword is in mykeywords
            if keyword not in mykeywords: continue
            keyword_data = self.SystemSettings['keywords']['packages'].get(keyword)
            if not keyword_data: continue
            kwd_key = "%s_ids" % (keyword,)
            keyword_data_ids = self.SystemSettings['keywords']['packages'].get(reponame+kwd_key)
            if not isinstance(keyword_data_ids, set):
                keyword_data_ids = set()
                for atom in keyword_data:
                    # match atom
                    matches, r = self.atomMatch(atom, multiMatch = True, packagesFilter = False)
                    if r != 0: continue
                    keyword_data_ids |= matches
                self.SystemSettings['keywords']['packages'][reponame+kwd_key] = keyword_data_ids
            if idpackage in keyword_data_ids:
                # valid!
                myr = self.SystemSettings['pkg_masking_reference']['user_package_keywords']
                try:
                    validator_cache = self.SystemSettings[self.client_settings_plugin_id]['masking_validation']['cache']
                    validator_cache[(idpackage, reponame, live)] = idpackage, myr
                except KeyError: # system settings client plugin not found
                    pass
                return idpackage, myr



    # function that validate one atom by reading keywords settings
    # validator_cache = self.SystemSettings[self.client_settings_plugin_id]['masking_validation']['cache']
    def idpackageValidator(self, idpackage, live = True):

        if self.dbname == etpConst['clientdbid']:
            return idpackage, 0
        elif self.dbname.startswith(etpConst['serverdbid']):
            return idpackage, 0

        reponame = self.dbname[len(etpConst['dbnamerepoprefix']):]
        try:
            validator_cache = self.SystemSettings[self.client_settings_plugin_id]['masking_validation']['cache']
            cached = validator_cache.get((idpackage, reponame, live))
            if cached != None:
                return cached
            # avoid memleaks
            if len(validator_cache) > 10000:
                validator_cache.clear()
        except KeyError: # plugin does not exist
            pass

        if live:
            data = self._idpackageValidator_live(idpackage, reponame)
            if data: return data

        data = self._idpackageValidator_user_package_mask(idpackage, reponame, live)
        if data: return data

        data = self._idpackageValidator_user_package_unmask(idpackage, reponame, live)
        if data: return data

        data = self._idpackageValidator_packages_db_mask(idpackage, reponame, live)
        if data: return data

        data = self._idpackageValidator_package_license_mask(idpackage, reponame, live)
        if data: return data

        data = self._idpackageValidator_keyword_mask(idpackage, reponame, live)
        if data: return data

        # holy crap, can't validate
        myr = self.SystemSettings['pkg_masking_reference']['completely_masked']
        validator_cache[(idpackage, reponame, live)] = -1, myr
        return -1, myr

    # packages filter used by atomMatch, input must me foundIDs, a list like this:
    # [608,1867]
    def packagesFilter(self, results):
        # keywordsFilter ONLY FILTERS results if
        # self.dbname.startswith(etpConst['dbnamerepoprefix']) => repository database is open
        if not self.dbname.startswith(etpConst['dbnamerepoprefix']):
            return results

        newresults = set()
        for idpackage in results:
            idpackage, reason = self.idpackageValidator(idpackage)
            if idpackage == -1: continue
            newresults.add(idpackage)
        return newresults

    def __filterSlot(self, idpackage, slot):
        if slot == None:
            return idpackage
        dbslot = self.retrieveSlot(idpackage)
        if str(dbslot) == str(slot):
            return idpackage

    def __filterTag(self, idpackage, tag, operators):
        if tag == None:
            return idpackage
        dbtag = self.retrieveVersionTag(idpackage)
        compare = cmp(tag, dbtag)
        if not operators or operators == "=":
            if compare == 0:
                return idpackage
        else:
            return self.__do_operator_compare(idpackage, operators, compare)

    def __filterUse(self, idpackage, use):
        if not use:
            return idpackage
        pkguse = self.retrieveUseflags(idpackage)
        disabled = set([x[1:] for x in use if x.startswith("-")])
        enabled = set([x for x in use if not x.startswith("-")])
        enabled_not_satisfied = enabled - pkguse
        # check enabled
        if enabled_not_satisfied:
            return None
        # check disabled
        disabled_not_satisfied = disabled - pkguse
        if len(disabled_not_satisfied) != len(disabled):
            return None
        return idpackage

    def __do_operator_compare(self, token, operators, compare):
        if operators == ">" and compare == -1:
            return token
        elif operators == ">=" and compare < 1:
            return token
        elif operators == "<" and compare == 1:
            return token
        elif operators == "<=" and compare > -1:
            return token

    def __filterSlotTagUse(self, foundIDs, slot, tag, use, operators):

        def myfilter(idpackage):

            idpackage = self.__filterSlot(idpackage, slot)
            if not idpackage:
                return False

            idpackage = self.__filterUse(idpackage, use)
            if not idpackage:
                return False

            idpackage = self.__filterTag(idpackage, tag, operators)
            if not idpackage:
                return False

            return True

        return set(filter(myfilter, foundIDs))

    '''
       @description: matches the user chosen package name+ver, if possibile, in a single repository
       @input atom: string, atom to match
       @input caseSensitive: bool, should the atom be parsed case sensitive?
       @input matchSlot: string, match atoms with the provided slot
       @input multiMatch: bool, return all the available atoms
       @input matchBranches: tuple or list, match packages only in the specified branches
       @input matchTag: match packages only for the specified tag
       @input matchUse: match packages only if it owns the specified use flags
       @input packagesFilter: enable/disable package.mask/.keywords/.unmask filter
       @output: the package id, if found, otherwise -1 plus the status, 0 = ok, 1 = error
    '''
    def atomMatch(self, atom, caseSensitive = True, matchSlot = None, multiMatch = False,
            matchBranches = (), matchTag = None, matchUse = (), packagesFilter = True,
            matchRevision = None, extendedResults = False, useCache = True ):

        if not atom:
            return -1, 1

        if useCache:
            cached = self.atomMatchFetchCache(
                atom, caseSensitive, matchSlot,
                multiMatch, matchBranches, matchTag,
                matchUse, packagesFilter, matchRevision,
                extendedResults
            )
            if isinstance(cached, tuple):
                try:
                    cached = self.atomMatchValidateCache(cached, multiMatch, extendedResults)
                except (TypeError, ValueError, IndexError, KeyError,):
                    cached = None
            if isinstance(cached, tuple):
                return cached

        atomTag = self.entropyTools.dep_gettag(atom)
        try:
            atomUse = self.entropyTools.dep_getusedeps(atom)
        except InvalidAtom:
            atomUse = ()
        atomSlot = self.entropyTools.dep_getslot(atom)
        atomRev = self.entropyTools.dep_get_entropy_revision(atom)
        if isinstance(atomRev, (int, long,)):
            if atomRev < 0: atomRev = None

        # use match
        scan_atom = self.entropyTools.remove_usedeps(atom)
        if (not matchUse) and (atomUse):
            matchUse = atomUse

        # tag match
        scan_atom = self.entropyTools.remove_tag(scan_atom)
        if (matchTag == None) and (atomTag != None):
            matchTag = atomTag

        # slot match
        scan_atom = self.entropyTools.remove_slot(scan_atom)
        if (matchSlot == None) and (atomSlot != None):
            matchSlot = atomSlot

        # revision match
        scan_atom = self.entropyTools.remove_entropy_revision(scan_atom)
        if (matchRevision == None) and (atomRev != None):
            matchRevision = atomRev

        branch_list = ()
        direction = ''
        justname = True
        pkgkey = ''
        strippedAtom = ''
        foundIDs = []
        dbpkginfo = set()

        if scan_atom:

            while 1:
                pkgversion = ''
                # check for direction
                strippedAtom = self.entropyTools.dep_getcpv(scan_atom)
                if scan_atom[-1] == "*":
                    strippedAtom += "*"
                direction = scan_atom[0:len(scan_atom)-len(strippedAtom)]

                justname = self.entropyTools.isjustname(strippedAtom)
                pkgkey = strippedAtom
                if justname == 0:
                    # get version
                    data = self.entropyTools.catpkgsplit(strippedAtom)
                    if data == None: break # badly formatted
                    pkgversion = data[2]+"-"+data[3]
                    pkgkey = self.entropyTools.dep_getkey(strippedAtom)

                splitkey = pkgkey.split("/")
                if (len(splitkey) == 2):
                    pkgname = splitkey[1]
                    pkgcat = splitkey[0]
                else:
                    pkgname = splitkey[0]
                    pkgcat = "null"

                branch_list = (self.db_branch,)
                if matchBranches:
                    # force to tuple for security
                    branch_list = tuple(matchBranches)
                break


        if branch_list:
            # IDs found in the database that match our search
            foundIDs = self.__generate_found_ids_match(branch_list, pkgkey, pkgname, pkgcat, caseSensitive, multiMatch)

        ### FILTERING
        # filter slot and tag
        if foundIDs:
            foundIDs = self.__filterSlotTagUse(foundIDs, matchSlot, matchTag, matchUse, direction)
            if packagesFilter:
                foundIDs = self.packagesFilter(foundIDs)
        ### END FILTERING

        if foundIDs:
            dbpkginfo = self.__handle_found_ids_match(foundIDs, direction, matchTag, matchRevision, justname, strippedAtom, pkgversion)

        if not dbpkginfo:
            if extendedResults:
                x = (-1, 1, None, None, None,)
                self.atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchBranches, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (x, 1)
                )
                return x, 1
            else:
                self.atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchBranches, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (-1, 1)
                )
                return -1, 1

        if multiMatch:
            if extendedResults:
                x = set([(x[0], 0, x[1], self.retrieveVersionTag(x[0]), self.retrieveRevision(x[0])) for x in dbpkginfo])
                self.atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchBranches, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (x, 0)
                )
                return x, 0
            else:
                x = set([x[0] for x in dbpkginfo])
                self.atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchBranches, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (x, 0)
                )
                return x, 0

        if len(dbpkginfo) == 1:
            x = dbpkginfo.pop()
            if extendedResults:
                x = (x[0], 0, x[1], self.retrieveVersionTag(x[0]), self.retrieveRevision(x[0]))
                self.atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchBranches, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (x, 0)
                )
                return x, 0
            else:
                self.atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchBranches, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (x[0], 0)
                )
                return x[0], 0

        dbpkginfo = list(dbpkginfo)
        pkgdata = {}
        versions = set()
        for x in dbpkginfo:
            info_tuple = (x[1], self.retrieveVersionTag(x[0]), self.retrieveRevision(x[0]))
            versions.add(info_tuple)
            pkgdata[info_tuple] = x[0]
        newer = self.entropyTools.get_entropy_newer_version(list(versions))[0]
        x = pkgdata[newer]
        if extendedResults:
            x = (x, 0, newer[0], newer[1], newer[2])
            self.atomMatchStoreCache(
                atom, caseSensitive, matchSlot,
                multiMatch, matchBranches, matchTag,
                matchUse, packagesFilter, matchRevision,
                extendedResults, result = (x, 0)
            )
            return x, 0
        else:
            self.atomMatchStoreCache(
                atom, caseSensitive, matchSlot,
                multiMatch, matchBranches, matchTag,
                matchUse, packagesFilter, matchRevision,
                extendedResults, result = (x, 0)
            )
            return x, 0

    def __generate_found_ids_match(self, branch_list, pkgkey, pkgname, pkgcat, caseSensitive, multiMatch):
        foundIDs = set()
        for idx in branch_list:

            if pkgcat == "null":
                results = self.searchPackagesByName(
                    pkgname, sensitive = caseSensitive,
                    branch = idx, justid = True
                )
            else:
                results = self.searchPackagesByNameAndCategory(
                    name = pkgname, category = pkgcat, branch = idx,
                    sensitive = caseSensitive, justid = True
                )

            mypkgcat = pkgcat
            mypkgname = pkgname
            virtual = False
            # if it's a PROVIDE, search with searchProvide
            # there's no package with that name
            if (not results) and (mypkgcat == "virtual"):
                virtuals = self.searchProvide(pkgkey, branch = idx, justid = True)
                if virtuals:
                    virtual = True
                    mypkgname = self.retrieveName(virtuals[0])
                    mypkgcat = self.retrieveCategory(virtuals[0])
                    results = virtuals

            # now validate
            if not results:
                continue # search into a stabler branch

            elif (len(results) > 1):

                # if it's because category differs, it's a problem
                foundCat = None
                cats = set()
                for idpackage in results:
                    cat = self.retrieveCategory(idpackage)
                    cats.add(cat)
                    if (cat == mypkgcat) or ((not virtual) and (mypkgcat == "virtual") and (cat == mypkgcat)):
                        # in case of virtual packages only (that they're not stored as provide)
                        foundCat = cat

                # if we found something at least...
                if (not foundCat) and (len(cats) == 1) and (mypkgcat in ("virtual", "null")):
                    foundCat = sorted(cats)[0]

                if not foundCat:
                    # got the issue
                    continue

                # we can use foundCat
                mypkgcat = foundCat

                # we need to search using the category
                if (not multiMatch) and (pkgcat == "null" or virtual):
                    # we searched by name, we need to search using category
                    results = self.searchPackagesByNameAndCategory(
                        name = mypkgname, category = mypkgcat,
                        branch = idx, sensitive = caseSensitive, justid = True
                    )

                # validate again
                if not results:
                    continue  # search into another branch

                # if we get here, we have found the needed IDs
                foundIDs |= set(results)
                break

            else:

                idpackage = results[0]
                # if mypkgcat is virtual, we can force
                if (mypkgcat == "virtual") and (not virtual):
                    # in case of virtual packages only (that they're not stored as provide)
                    mypkgcat = self.retrieveCategory(idpackage)

                # check if category matches
                if mypkgcat != "null":
                    foundCat = self.retrieveCategory(idpackage)
                    if mypkgcat == foundCat:
                        foundIDs.add(idpackage)
                    continue
                foundIDs.add(idpackage)
                break

        return foundIDs


    def __handle_found_ids_match(self, foundIDs, direction, matchTag, matchRevision, justname, strippedAtom, pkgversion):

        dbpkginfo = set()
        # now we have to handle direction
        if ((direction) or ((not direction) and (not justname)) or ((not direction) and (not justname) and strippedAtom.endswith("*"))) and foundIDs:

            if (not justname) and \
                ((direction == "~") or (direction == "=") or \
                (direction == '' and not justname) or (direction == '' and not justname and strippedAtom.endswith("*"))):
                # any revision within the version specified OR the specified version

                if (direction == '' and not justname):
                    direction = "="

                # remove gentoo revision (-r0 if none)
                if (direction == "="):
                    if (pkgversion.split("-")[-1] == "r0"):
                        pkgversion = self.entropyTools.remove_revision(pkgversion)
                if (direction == "~"):
                    pkgrevision = self.entropyTools.dep_get_portage_revision(pkgversion)
                    pkgversion = self.entropyTools.remove_revision(pkgversion)

                for idpackage in foundIDs:

                    dbver = self.retrieveVersion(idpackage)
                    if (direction == "~"):
                        myrev = self.entropyTools.dep_get_portage_revision(dbver)
                        myver = self.entropyTools.remove_revision(dbver)
                        if myver == pkgversion and pkgrevision <= myrev:
                            # found
                            dbpkginfo.add((idpackage, dbver))
                    else:
                        # media-libs/test-1.2* support
                        if pkgversion[-1] == "*":
                            if dbver.startswith(pkgversion[:-1]):
                                dbpkginfo.add((idpackage, dbver))
                        elif (matchRevision != None) and (pkgversion == dbver):
                            dbrev = self.retrieveRevision(idpackage)
                            if dbrev == matchRevision:
                                dbpkginfo.add((idpackage, dbver))
                        elif (pkgversion == dbver) and (matchRevision == None):
                            dbpkginfo.add((idpackage, dbver))

            elif (direction.find(">") != -1) or (direction.find("<") != -1):

                if not justname:

                    # remove revision (-r0 if none)
                    if pkgversion.endswith("r0"):
                        # remove
                        self.entropyTools.remove_revision(pkgversion)

                    for idpackage in foundIDs:

                        revcmp = 0
                        tagcmp = 0
                        if matchRevision != None:
                            dbrev = self.retrieveRevision(idpackage)
                            revcmp = cmp(matchRevision, dbrev)
                        if matchTag != None:
                            dbtag = self.retrieveVersionTag(idpackage)
                            tagcmp = cmp(matchTag, dbtag)
                        dbver = self.retrieveVersion(idpackage)
                        pkgcmp = self.entropyTools.compare_versions(pkgversion, dbver)
                        if pkgcmp == None:
                            import warnings
                            warnings.warn("WARNING, invalid version string stored in %s: %s <-> %s" % (self.dbname, pkgversion, dbver,))
                            continue
                        if direction == ">":
                            if pkgcmp < 0:
                                dbpkginfo.add((idpackage, dbver))
                            elif (matchRevision != None) and pkgcmp <= 0 and revcmp < 0:
                                dbpkginfo.add((idpackage, dbver))
                            elif (matchTag != None) and tagcmp < 0:
                                dbpkginfo.add((idpackage, dbver))
                        elif direction == "<":
                            if pkgcmp > 0:
                                dbpkginfo.add((idpackage, dbver))
                            elif (matchRevision != None) and pkgcmp >= 0 and revcmp > 0:
                                dbpkginfo.add((idpackage, dbver))
                            elif (matchTag != None) and tagcmp > 0:
                                dbpkginfo.add((idpackage, dbver))
                        elif direction == ">=":
                            if (matchRevision != None) and pkgcmp <= 0:
                                if pkgcmp == 0:
                                    if revcmp <= 0:
                                        dbpkginfo.add((idpackage, dbver))
                                else:
                                    dbpkginfo.add((idpackage, dbver))
                            elif pkgcmp <= 0 and matchRevision == None:
                                dbpkginfo.add((idpackage, dbver))
                            elif (matchTag != None) and tagcmp <= 0:
                                dbpkginfo.add((idpackage, dbver))
                        elif direction == "<=":
                            if (matchRevision != None) and pkgcmp >= 0:
                                if pkgcmp == 0:
                                    if revcmp >= 0:
                                        dbpkginfo.add((idpackage, dbver))
                                else:
                                    dbpkginfo.add((idpackage, dbver))
                            elif pkgcmp >= 0 and matchRevision == None:
                                dbpkginfo.add((idpackage, dbver))
                            elif (matchTag != None) and tagcmp >= 0:
                                dbpkginfo.add((idpackage, dbver))

        else: # just the key

            dbpkginfo = set([(x, self.retrieveVersion(x),) for x in foundIDs])

        return dbpkginfo
