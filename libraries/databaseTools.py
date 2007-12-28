#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy Database Interface

    Copyright (C) 2007 Fabio Erculiani

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

from entropyConstants import *
import entropyTools
from outputTools import *
# FIXME: add more python db apis
try: # try with sqlite3 from python 2.5 - default one
    from sqlite3 import dbapi2
except ImportError: # fallback to embedded pysqlite
    from pysqlite2 import dbapi2
import dumpTools
import exceptionTools

# Logging initialization
import logTools
dbLog = logTools.LogFile(level = etpConst['databaseloglevel'],filename = etpConst['databaselogfile'], header = "[DBase]")
_treeUpdatesCalled = False


############
# Functions and Classes
#####################################################################################

'''
   @description: open the repository database and returns the pointer
   @input repositoryName: name of the client database
   @output: database pointer or, -1 if error
'''
def openRepositoryDatabase(repositoryName, xcache = True, indexing = True):
    dbfile = etpRepositories[repositoryName]['dbpath']+"/"+etpConst['etpdatabasefile']
    if not os.path.isfile(dbfile):
	fetchRepositoryIfNotAvailable(repositoryName)
    conn = etpDatabase(readOnly = True, dbFile = dbfile, clientDatabase = True, dbname = etpConst['dbnamerepoprefix']+repositoryName, xcache = xcache, indexing = indexing)
    # initialize CONFIG_PROTECT
    if (etpRepositories[repositoryName]['configprotect'] == None) or (etpRepositories[repositoryName]['configprotectmask'] == None):
        
        etpRepositories[repositoryName]['configprotect'] = conn.listConfigProtectDirectories()
        etpRepositories[repositoryName]['configprotectmask'] = conn.listConfigProtectDirectories(mask = True)
        etpRepositories[repositoryName]['configprotect'] = [etpConst['systemroot']+x for x in etpRepositories[repositoryName]['configprotect']]
        etpRepositories[repositoryName]['configprotectmask'] = [etpConst['systemroot']+x for x in etpRepositories[repositoryName]['configprotectmask']]
        
	etpRepositories[repositoryName]['configprotect'] += [etpConst['systemroot']+x for x in etpConst['configprotect'] if etpConst['systemroot']+x not in etpRepositories[repositoryName]['configprotect']]
	etpRepositories[repositoryName]['configprotectmask'] += [etpConst['systemroot']+x for x in etpConst['configprotectmask'] if etpConst['systemroot']+x not in etpRepositories[repositoryName]['configprotectmask']]
    if not _treeUpdatesCalled and (etpConst['uid'] == 0):
        conn.clientUpdatePackagesData()
    return conn

def fetchRepositoryIfNotAvailable(reponame):
    # open database
    rc = 0
    dbfile = etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasefile']
    if not os.path.isfile(dbfile):
	# sync
        import repositoriesTools
	rc = repositoriesTools.syncRepositories([reponame])
    if not os.path.isfile(dbfile):
        raise exceptionTools.RepositoryError("RepositoryError: cannot fetch database for repo id: "+reponame)
    return rc

'''
   @description: open the installed packages database and returns the pointer
   @output: database pointer or, -1 if error
'''
def openClientDatabase(xcache = True, generate = False, indexing = True):
    if (not generate) and (not os.path.isfile(etpConst['etpdatabaseclientfilepath'])):
        raise exceptionTools.SystemDatabaseError("SystemDatabaseError: system database not found. Either does not exist or corrupted.")
    else:
        conn = etpDatabase(readOnly = False, dbFile = etpConst['etpdatabaseclientfilepath'], clientDatabase = True, dbname = 'client', xcache = xcache, indexing = indexing)
	if (not etpConst['dbconfigprotect']):
	    # config protect not prepared
            if (not generate):
                
                etpConst['dbconfigprotect'] = conn.listConfigProtectDirectories()
                etpConst['dbconfigprotectmask'] = conn.listConfigProtectDirectories(mask = True)
                etpConst['dbconfigprotect'] = [etpConst['systemroot']+x for x in etpConst['dbconfigprotect']]
                etpConst['dbconfigprotectmask'] = [etpConst['systemroot']+x for x in etpConst['dbconfigprotect']]
                
                etpConst['dbconfigprotect'] += [etpConst['systemroot']+x for x in etpConst['configprotect'] if etpConst['systemroot']+x not in etpConst['dbconfigprotect']]
                etpConst['dbconfigprotectmask'] += [etpConst['systemroot']+x for x in etpConst['configprotectmask'] if etpConst['systemroot']+x not in etpConst['dbconfigprotectmask']]
                
	return conn

'''
   @description: open the entropy server database and returns the pointer. This function must be used only by reagent or activator
   @output: database class instance
'''
def openServerDatabase(readOnly = True, noUpload = True):
    conn = etpDatabase(readOnly = readOnly, dbFile = etpConst['etpdatabasefilepath'], noUpload = noUpload)
    # verify if we need to update the database to sync with portage updates, we just ignore being readonly in the case
    if not _treeUpdatesCalled:
        conn.serverUpdatePackagesData()
    return conn

'''
   @description: open a generic client database and returns the pointer.
   @output: database pointer
'''
def openGenericDatabase(dbfile, dbname = None, xcache = False, indexing = True, readOnly = False):
    if dbname == None: dbname = "generic"
    conn = etpDatabase(readOnly = readOnly, dbFile = dbfile, clientDatabase = True, dbname = dbname, xcache = xcache, indexing = indexing)
    return conn

def backupClientDatabase():
    import shutil
    if os.path.isfile(etpConst['etpdatabaseclientfilepath']):
	rnd = entropyTools.getRandomNumber()
	source = etpConst['etpdatabaseclientfilepath']
	dest = etpConst['etpdatabaseclientfilepath']+".backup."+str(rnd)
	shutil.copy2(source,dest)
	user = os.stat(source)[4]
	group = os.stat(source)[5]
	os.chown(dest,user,group)
	shutil.copystat(source,dest)
	return dest
    return ""

def listAllAvailableBranches():
    branches = set()
    for repo in etpRepositories:
        dbconn = openRepositoryDatabase(repo)
        branches.update(dbconn.listAllBranches())
        dbconn.closeDB()
        del dbconn
    return branches

def doServerDatabaseSyncLock(noUpload):
    
    import mirrorTools
    import activatorTools

    # check if the database is locked locally
    if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']):
        print_info(red(" * ")+red("Entropy database is already locked by you :-)"))
    else:
        # check if the database is locked REMOTELY
        print_info(red(" * ")+red(" Locking and Syncing Entropy database ..."), back = True)
        for uri in etpConst['activatoruploaduris']:
            ftp = mirrorTools.handlerFTP(uri)
            try:
                ftp.setCWD(etpConst['etpurirelativepath'])
            except:
                bdir = ""
                for mydir in etpConst['etpurirelativepath'].split("/"):
                    bdir += "/"+mydir
                    if (not ftp.isFileAvailable(bdir)):
                        try:
                            ftp.mkdir(bdir)
                        except Exception, e:
                            if str(e).find("550") != -1:
                                pass
                            raise
                ftp.setCWD(etpConst['etpurirelativepath'])
            if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])) and (not os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])):
                import time
                print_info(red(" * ")+bold("WARNING")+red(": online database is already locked. Waiting up to 2 minutes..."), back = True)
                unlocked = False
                count = 120
                while count:
                    time.sleep(1)
                    count -= 1
                    if (not ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
                        print_info(red(" * ")+bold("HOORAY")+red(": online database has been unlocked. Locking back and syncing..."))
                        unlocked = True
                        break
                if (unlocked):
                    break

                print_info(yellow(" * ")+green("Mirrors status table:"))
                dbstatus = activatorTools.getMirrorsLock()
                for db in dbstatus:
                    
                    db[1] = green("Unlocked")
                    if (db[1]):
                        db[1] = red("Locked")
                    db[2] = green("Unlocked")
                    if (db[2]):
                        db[2] = red("Locked")
                    
                    print_info(bold("\t"+entropyTools.extractFTPHostFromUri(db[0])+": ")+red("[")+yellow("DATABASE: ")+db[1]+red("] [")+yellow("DOWNLOAD: ")+db[2]+red("]"))
        
                ftp.closeConnection()
                print
                raise exceptionTools.OnlineMirrorError("OnlineMirrorError: cannot lock mirror "+entropyTools.extractFTPHostFromUri(uri))

        # if we arrive here, it is because all the mirrors are unlocked so... damn, LOCK!
        activatorTools.lockDatabases(True)

        # ok done... now sync the new db, if needed
        activatorTools.syncRemoteDatabases(noUpload)

class etpDatabase:

    def __init__(self, readOnly = False, noUpload = False, dbFile = etpConst['etpdatabasefilepath'], clientDatabase = False, xcache = False, dbname = 'etpdb', indexing = True):
        
        self.readOnly = readOnly
        self.noUpload = noUpload
        self.packagesRemoved = False
        self.packagesAdded = False
        self.clientDatabase = clientDatabase
        self.xcache = xcache
        self.dbname = dbname
        self.indexing = indexing
        if etpConst['uid'] > 0: # forcing since we won't have write access to db
            self.indexing = False
        self.dbFile = dbFile
        
        # load db on disk cache?
        self.loadDatabaseCache()

        # create connection
        self.connection = dbapi2.connect(dbFile,timeout=300.0)
        self.cursor = self.connection.cursor()

        if not ((self.clientDatabase) or (self.readOnly)):
            # server side is calling
            # lock mirror remotely and ensure to have latest database revision
            doServerDatabaseSyncLock(self.noUpload)


    def closeDB(self):

        # if the class is opened readOnly, close and forget
        if (self.readOnly):
            #self.connection.rollback()
            self.cursor.close()
            self.connection.close()
            return

        # if it's equo that's calling the function, just save changes and quit
        if (self.clientDatabase):
            self.commitChanges()
            self.cursor.close()
            self.connection.close()
            return
    
        # Cleanups if at least one package has been removed
        # Please NOTE: the client database does not need it
        if (self.packagesRemoved):
            self.cleanupUseflags()
            self.cleanupSources()
            try:
                self.cleanupEclasses()
            except:
                self.createEclassesTable()
                self.cleanupEclasses()
            try:
                self.cleanupNeeded()
            except:
                self.createNeededTable()
                self.cleanupNeeded()
            self.cleanupDependencies()
        
        if (etpDbStatus[etpConst['etpdatabasefilepath']]['tainted']) and (not etpDbStatus[etpConst['etpdatabasefilepath']]['bumped']):
            # bump revision, setting DatabaseBump causes the session to just bump once
            etpDbStatus[etpConst['etpdatabasefilepath']]['bumped'] = True
            self.revisionBump()
        
        if (not etpDbStatus[etpConst['etpdatabasefilepath']]['tainted']):
            # we can unlock it, no changes were made
            import activatorTools
            activatorTools.lockDatabases(False)
        else:
            print_info(yellow(" * ")+green("Mirrors have not been unlocked. Run activator."))
        
        # run vacuum cleaner
        self.cursor.execute("vacuum")
        self.connection.commit()
        
        self.cursor.close()
        self.connection.close()

    def commitChanges(self):
        if (not self.readOnly):
            try:
                self.connection.commit()
            except:
                pass
            self.taintDatabase()
        else:
            self.discardChanges() # is it ok?

    def taintDatabase(self):
        if (self.clientDatabase): # if it's equo to open it, this should be avoided
            return
        # taint the database status
        f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile'],"w")
        f.write(etpConst['currentarch']+" database tainted\n")
        f.flush()
        f.close()
        etpDbStatus[etpConst['etpdatabasefilepath']]['tainted'] = True

    def untaintDatabase(self):
        if (self.clientDatabase): # if it's equo to open it, this should be avoided
            return
        etpDbStatus[etpConst['etpdatabasefilepath']]['tainted'] = False
        # untaint the database status
        if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile']):
            os.remove(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile'])

    def revisionBump(self):
        if (not os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaserevisionfile'])):
            revision = 0
        else:
            f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaserevisionfile'],"r")
            revision = int(f.readline().strip())
            revision += 1
            f.close()
        f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaserevisionfile'],"w")
        f.write(str(revision)+"\n")
        f.flush()
        f.close()

    def isDatabaseTainted(self):
        if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile']):
            return True
        return False

    def discardChanges(self):
        self.connection.rollback()

    # never use this unless you know what you're doing
    def initializeDatabase(self):
        for sql in etpSQLInitDestroyAll.split(";"):
            if sql:
                self.cursor.execute(sql+";")
        del sql
        for sql in etpSQLInit.split(";"):
            if sql:
                self.cursor.execute(sql+";")
        self.commitChanges()

    def checkReadOnly(self):
        if (self.readOnly):
            raise exceptionTools.OperationNotPermitted("OperationNotPermitted: can't do that on a readonly database.")

    # check for /usr/portage/profiles/updates changes
    def serverUpdatePackagesData(self):

        global _treeUpdatesCalled
        _treeUpdatesCalled = True

        repository = etpConst['officialrepositoryname']
        doRescan = False

        if repositoryUpdatesDigestCache_db.has_key(repository):
            stored_digest = repositoryUpdatesDigestCache_db.get(repository)
        else:
            # check database digest
            stored_digest = self.retrieveRepositoryUpdatesDigest(repository)
            repositoryUpdatesDigestCache_db[repository] = stored_digest
            if stored_digest == -1:
                doRescan = True

        # check portage files for changes if doRescan is still false
        portage_dirs_digest = "0"
        if not doRescan:

            if repositoryUpdatesDigestCache_disk.has_key(repository):
                portage_dirs_digest = repositoryUpdatesDigestCache_disk.get(repository)
            else:
                import portageTools
                # grab portdir
                updates_dir = etpConst['systemroot']+portageTools.getPortageEnv("PORTDIR")+"/profiles/updates"
                if os.path.isdir(updates_dir):
                    # get checksum
                    portage_dirs_digest = entropyTools.md5sum_directory(updates_dir)
                    repositoryUpdatesDigestCache_disk[repository] = portage_dirs_digest
                del updates_dir
                del portageTools

        if doRescan or (str(stored_digest) != str(portage_dirs_digest)):
            #print stored_digest, portage_dirs_digest

            # force parameters
            self.readOnly = False
            self.noUpload = True

            # reset database tables
            self.clearTreeupdatesEntries(repository)

            import portageTools
            updates_dir = etpConst['systemroot']+portageTools.getPortageEnv("PORTDIR")+"/profiles/updates"
            update_files = entropyTools.sortUpdateFiles(os.listdir(updates_dir))
            update_files = [os.path.join(updates_dir,x) for x in update_files]
            # now load actions from files
            update_actions = []
            for update_file in update_files:
                f = open(update_file,"r")
                lines = [x.strip() for x in f.readlines() if x.strip()]
                for line in lines:
                    update_actions.append(line)
                del lines
            # now filter the required actions
            update_actions = self.filterTreeUpdatesActions(update_actions)
            if update_actions:

                # print information
                print_warning("")
                print_warning(darkred(" * ")+bold("ATTENTION: ")+red("forcing package updates. Syncing with %s" % (blue(updates_dir),)))
                print_warning("")
                # lock database
                doServerDatabaseSyncLock(self.noUpload)
                # now run queue
                self.runTreeUpdatesActions(update_actions)

            # store new actions
            self.addRepositoryUpdatesActions(repository,update_actions)
            # store new digest into database
            self.setRepositoryUpdatesDigest(repository, portage_dirs_digest)

    # client side, no portage dependency
    # lxnay: it is indeed very similar to serverUpdatePackagesData() but I prefer keeping both separate
    # also, we reuse the same caching dictionaries of the server function
    # repositoryUpdatesDigestCache_db -> repository cache
    # repositoryUpdatesDigestCache_disk -> client database cache
    # check for repository packages updates
    # this will read database treeupdates* tables and do
    # changes required if running as root.
    def clientUpdatePackagesData(self):

        global _treeUpdatesCalled
        _treeUpdatesCalled = True

        repository = self.dbname[len(etpConst['dbnamerepoprefix']):]
        doRescan = False

        if repositoryUpdatesDigestCache_db.has_key(repository):
            stored_digest = repositoryUpdatesDigestCache_db.get(repository)
        else:
            # check database digest
            stored_digest = self.retrieveRepositoryUpdatesDigest(repository)
            repositoryUpdatesDigestCache_db[repository] = stored_digest
            if stored_digest == -1:
                doRescan = True

        try:
            clientDbconn = openClientDatabase(xcache = False, indexing = False)
        except exceptionTools.SystemDatabaseError:
            return # don't run anything for goodness' sake

        # check stored value in client database
        client_digest = "0"
        if not doRescan:

            if repositoryUpdatesDigestCache_disk.has_key(etpConst['systemroot']):
                client_digest = repositoryUpdatesDigestCache_disk.get(etpConst['systemroot'])
            else:
                client_digest = clientDbconn.retrieveRepositoryUpdatesDigest(repository)

        if doRescan or (str(stored_digest) != str(client_digest)):
            #print stored_digest, portage_dirs_digest

            # reset database tables
            clientDbconn.clearTreeupdatesEntries(repository)

            # load updates
            update_actions = self.retrieveTreeUpdatesActions(repository)
            # now filter the required actions
            update_actions = clientDbconn.filterTreeUpdatesActions(update_actions)

            if update_actions:

                # print information
                print_warning("")
                print_warning(darkred(" * ")+bold("ATTENTION: ")+red("forcing packages metadata update. Updating system database using repository id: %s" % (blue(repository),)))
                # run stuff
                clientDbconn.runTreeUpdatesActions(update_actions)
                print_warning("")

            # store new digest into database
            clientDbconn.setRepositoryUpdatesDigest(repository, stored_digest)

            # clear client cache
            dbCacheStore[etpCache['dbMatch']+"client"] = {}
            dbCacheStore[etpCache['dbSearch']+"client"] = {}
            dumpTools.dumpobj(etpCache['dbMatch']+"client",{})
            dumpTools.dumpobj(etpCache['dbSearch']+"client",{})
            clientDbconn.clearInfoCache()

        clientDbconn.closeDB()
        del clientDbconn


    # this functions will filter either data from /usr/portage/profiles/updates/*
    # or repository database returning only the needed actions
    def filterTreeUpdatesActions(self, actions):
        new_actions = []
        for action in actions:
            doaction = action.split()
            if doaction[0] == "slotmove":
                # slot move
                atom = doaction[1]
                from_slot = doaction[2]
                to_slot = doaction[3]
                matches = self.atomMatch(atom, multiMatch = True)
                if matches[1] == 0:
                    # found atom, check slot
                    for idpackage in matches[0]:
                        myslot = str(self.retrieveSlot(idpackage))
                        if (myslot == from_slot) and (myslot != to_slot):
                            new_actions.append(action)
            elif doaction[0] == "move":
                atom = doaction[1]
                matches = self.atomMatch(atom, multiMatch = True)
                if matches[1] == 0:
                    for idpackage in matches[0]:
                        new_actions.append(action)
        return new_actions

    # this is the place to add extra actions support
    def runTreeUpdatesActions(self, actions):

        # just run fixpackages if gentoo-compat is enabled
        if etpConst['gentoo-compat']:
            ## FIXME: beautify
            print_warning(darkred(" * ")+bold("GENTOO: ")+red("Running fixpackages, could take a while."))
            if self.clientDatabase:
                os.system("fixpackages &> /dev/null")
            else:
                os.system("fixpackages")

        for action in actions:
            command = action.split()
            if command[0] == "move":
                print_warning(darkred(" * ")+bold("ENTROPY: ")+red("action: %s" % (blue(action),)))
                self.runTreeUpdatesMoveAction(command[1:])
            elif command[0] == "slotmove":
                print_warning(darkred(" * ")+bold("ENTROPY: ")+red("action: %s" % (blue(action),)))
                self.runTreeUpdatesSlotmoveAction(command[1:])

        # discard cache
        dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
        dbCacheStore[etpCache['dbSearch']+self.dbname] = {}
        dumpTools.dumpobj(etpCache['dbMatch']+self.dbname,{})
        dumpTools.dumpobj(etpCache['dbSearch']+self.dbname,{})
        self.clearInfoCache()


    # -- move action:
    # 1) move package key to the new name: category + name + atom
    # 2) update all the dependencies in dependenciesreference to the new key
    # 3) run fixpackages which will update /var/db/pkg files
    # 4) automatically run quickpkg() to build the new binary and tainted binaries owning tainted iddependency and taint database (LOL)
    def runTreeUpdatesMoveAction(self, move_command):
        key_from = move_command[0]
        key_to = move_command[1]
        cat_to = key_to.split("/")[0]
        name_to = key_to.split("/")[1]
        matches = self.atomMatch(key_from, multiMatch = True)
        for idpackage in matches[0]:

            slot = self.retrieveSlot(idpackage)
            old_atom = self.retrieveAtom(idpackage)
            new_atom = old_atom.replace(key_from,key_to)
            
            ### UPDATE DATABASE
            # update category
            self.setCategory(idpackage, cat_to)
            # update name
            self.setName(idpackage, name_to)
            # update atom
            self.setAtom(idpackage, new_atom)

            # look for packages we need to quickpkg again
            # note: quickpkg_queue is simply ignored if self.clientDatabase
            quickpkg_queue = [key_to+":"+str(slot)]
            iddeps = self.searchDependency(key_from, like = True, multi = True)
            for iddep in iddeps:
                # update string
                mydep = self.retrieveDependencyFromIddependency(iddep)
                mydep = mydep.replace(key_from,key_to)

                # now update
                # dependstable on server is always re-generated
                self.setDependency(iddep, mydep)

                if self.clientDatabase:
                    continue # ignore quickpkg stuff

                # we have to repackage also package owning this iddep
                iddep_owners = self.searchIdpackageFromIddependency(iddep)
                for idpackage_owner in iddep_owners:
                    quickpkg_queue.append(self.retrieveAtom(idpackage_owner))

            if not self.clientDatabase:

                # check for injection and warn the developer
                injected = self.isInjected(idpackage)
                if injected:
                    print_warning(darkred(" * ")+bold("INJECT: ")+red("Package %s has been injected. You need to quickpkg it manually to update embedded database !!! Repository database will be updated anyway." % (blue(new_atom),)))

                # quickpkg package and packages owning it as a dependency
                self.runTreeUpdatesQuickpkgAction(quickpkg_queue)


        self.commitChanges()

    # -- slotmove action:
    # 1) move package slot
    # 2) update all the dependencies in dependenciesreference owning same matched atom + slot
    # 3) run fixpackages which will update /var/db/pkg files
    # 4) automatically run quickpkg() to build the new binary and tainted binaries owning tainted iddependency and taint database (LOL)
    def runTreeUpdatesSlotmoveAction(self, slotmove_command):
        atom = slotmove_command[0]
        atomkey = entropyTools.dep_getkey(atom)
        slot_from = slotmove_command[1]
        slot_to = slotmove_command[2]
        matches = self.atomMatch(atom, multiMatch = True)
        for idpackage in matches[0]:

            ### UPDATE DATABASE
            # update slot
            self.setSlot(idpackage, slot_to)

            # look for packages we need to quickpkg again
            # note: quickpkg_queue is simply ignored if self.clientDatabase
            quickpkg_queue = [atom+":"+str(slot_to)]
            iddeps = self.searchDependency(atomkey, like = True, multi = True)
            for iddep in iddeps:
                # update string
                mydep = self.retrieveDependencyFromIddependency(iddep)
                if mydep.find(":"+str(slot_from)) != -1: # probably slotted dep
                    mydep = mydep.replace(":"+str(slot_from),":"+str(slot_to))
                else:
                    continue # it's fine

                # now update
                # dependstable on server is always re-generated
                self.setDependency(iddep, mydep)

                if self.clientDatabase:
                    continue # ignore quickpkg stuff

                # we have to repackage also package owning this iddep
                iddep_owners = self.searchIdpackageFromIddependency(iddep)
                for idpackage_owner in iddep_owners:
                    quickpkg_queue.append(self.retrieveAtom(idpackage_owner))

            if not self.clientDatabase:

                # check for injection and warn the developer
                injected = self.isInjected(idpackage)
                if injected:
                    print_warning(darkred(" * ")+bold("INJECT: ")+red("Package %s has been injected. You need to quickpkg it manually to update embedded database !!! Repository database will be updated anyway." % (blue(atom),)))

                # quickpkg package and packages owning it as a dependency
                self.runTreeUpdatesQuickpkgAction(quickpkg_queue)

        self.commitChanges()


    def runTreeUpdatesQuickpkgAction(self, atoms):
        import reagentTools
        reagent_cmds = ["--repackage"]
        reagent_cmds += atoms
        
        # ask branch question
        rc = entropyTools.askquestion("     Would you like to continue with the default branch \"%s\" ?" % (etpConst['branch'],))
        if rc == "No":
            # ask which
            mybranch = etpConst['branch']
            while 1:
                mybranch = readtext("Type your branch: ")
                if mybranch not in self.listAllBranches():
                    print_warning(darkred(" * ")+bold("ATTENTION: ")+red("Specified branch %s does not exist." % (blue(mybranch),)))
                    continue
                # ask to confirm
                rc = entropyTools.askquestion("     Confirm %s ?" % (mybranch,))
                if rc == "Yes":
                    break
            reagent_cmds.append("--branch=%s" % (mybranch,))
        
        rc = reagentTools.update(reagent_cmds)
        if rc != 0:
            print_warning(darkred(" * ")+bold("ATTENTION: ")+red("reagent update did not run properly. Update packages manually"))


    def loadDatabaseCache(self):

        if (self.xcache) and (self.dbname != 'etpdb') and (etpConst['uid'] == 0):

            ''' database query cache '''
            broken1 = False
            dbinfo = dbCacheStore.get(etpCache['dbInfo']+self.dbname)
            if dbinfo == None:
                try:
                    dbCacheStore[etpCache['dbInfo']+self.dbname] = dumpTools.loadobj(etpCache['dbInfo']+self.dbname)
                    if dbCacheStore[etpCache['dbInfo']+self.dbname] == None:
                        broken1 = True
                        dbCacheStore[etpCache['dbInfo']+self.dbname] = {}
                except:
                    broken1 = True
                    pass
    
            ''' database atom dependencies cache '''
            dbmatch = dbCacheStore.get(etpCache['dbMatch']+self.dbname)
            broken2 = False
            if dbmatch == None:
                try:
                    dbCacheStore[etpCache['dbMatch']+self.dbname] = dumpTools.loadobj(etpCache['dbMatch']+self.dbname)
                    if dbCacheStore[etpCache['dbMatch']+self.dbname] == None:
                        broken2 = True
                        dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
                except:
                    broken2 = True
                    pass
    
            ''' database search cache '''
            dbmatch = dbCacheStore.get(etpCache['dbSearch']+self.dbname)
            broken3 = False
            if dbmatch == None:
                try:
                    dbCacheStore[etpCache['dbSearch']+self.dbname] = dumpTools.loadobj(etpCache['dbSearch']+self.dbname)
                    if dbCacheStore[etpCache['dbSearch']+self.dbname] == None:
                        broken3 = True
                        dbCacheStore[etpCache['dbSearch']+self.dbname] = {}
                except:
                    broken3 = True
                    pass
    
            if (broken1 or broken2 or broken3):
                # discard both caches
                dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
                dbCacheStore[etpCache['dbSearch']+self.dbname] = {}
                dumpTools.dumpobj(etpCache['dbMatch']+self.dbname,{})
                dumpTools.dumpobj(etpCache['dbSearch']+self.dbname,{})
                self.clearInfoCache()
                
        else:
            self.xcache = False # setting this to be safe
            dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
            try:
                self.clearInfoCache()
            except: # if it's not possible to write cache
                pass
            dbCacheStore[etpCache['dbSearch']+self.dbname] = {}


    # this function manages the submitted package
    # if it does not exist, it fires up addPackage
    # otherwise it fires up updatePackage
    def handlePackage(self, etpData, forcedRevision = -1):

	self.checkReadOnly()

	# build atom string
	versiontag = ''
	if etpData['versiontag']:
	    versiontag = '#'+etpData['versiontag']

	foundid = self.isPackageAvailable(etpData['category']+"/"+etpData['name']+"-"+etpData['version']+versiontag)
	if (foundid < 0): # same atom doesn't exist
	    idpk, revision, etpDataUpdated, accepted = self.addPackage(etpData, revision = forcedRevision)
	else:
	    idpk, revision, etpDataUpdated, accepted = self.updatePackage(etpData, forcedRevision) # only when the same atom exists
	return idpk, revision, etpDataUpdated, accepted


    def addPackage(self, etpData, revision = -1):

	self.checkReadOnly()
	
	if revision == -1:
            try:
	       revision = etpData['revision']
            except:
                etpData['revision'] = 0 # revision not specified
                revision = 0

	# we need to find other packages with the same key and slot, and remove them
	if (self.clientDatabase): # client database can't care about branch
	    searchsimilar = self.searchPackagesByNameAndCategory(name = etpData['name'], category = etpData['category'], sensitive = True)
	else: # server supports multiple branches inside a db
	    searchsimilar = self.searchPackagesByNameAndCategory(name = etpData['name'], category = etpData['category'], sensitive = True, branch = etpData['branch'])
	
	removelist = set()
        if not etpData['injected']: # read: if package has been injected, we'll skip the removal of packages in the same slot, usually used server side btw
            for oldpkg in searchsimilar:
                # get the package slot
                idpackage = oldpkg[1]
                slot = self.retrieveSlot(idpackage)
                isinjected = self.isInjected(idpackage)
                if isinjected:
                    continue # we merely ignore packages with negative counters, since they're the injected ones
                if (etpData['slot'] == slot):
                    # remove!
                    removelist.add(idpackage)
	
	for pkg in removelist:
	    self.removePackage(pkg)
	
	# create new category if it doesn't exist
	catid = self.isCategoryAvailable(etpData['category'])
	if (catid == -1):
	    # create category
	    catid = self.addCategory(etpData['category'])

	# create new license if it doesn't exist
	licid = self.isLicenseAvailable(etpData['license'])
	if (licid == -1):
	    # create category
	    licid = self.addLicense(etpData['license'])

	# look for configured versiontag
	versiontag = ""
	if (etpData['versiontag']):
	    versiontag = "#"+etpData['versiontag']
        
        trigger = 0
        if etpData['trigger']:
            trigger = 1
        
	# baseinfo
        pkgatom = etpData['category']+"/"+etpData['name']+"-"+etpData['version']+versiontag
        try:
            self.cursor.execute(
                    'INSERT into baseinfo VALUES '
                    '(NULL,?,?,?,?,?,?,?,?,?,?,?)'
                    , (	pkgatom,
                            catid,
                            etpData['name'],
                            etpData['version'],
                            etpData['versiontag'],
                            revision,
                            etpData['branch'],
                            etpData['slot'],
                            licid,
                            etpData['etpapi'],
                            trigger,
                            )
            )
        except: # workaround for old tables
            self.createTriggerColumn() # FIXME: will be removed before 1.0
            self.cursor.execute(
                    'INSERT into baseinfo VALUES '
                    '(NULL,?,?,?,?,?,?,?,?,?,?,?)'
                    , (	pkgatom,
                            catid,
                            etpData['name'],
                            etpData['version'],
                            etpData['versiontag'],
                            revision,
                            etpData['branch'],
                            etpData['slot'],
                            licid,
                            etpData['etpapi'],
                            trigger,
                            )
            )
        
	self.connection.commit()
	idpackage = self.cursor.lastrowid

        ### RSS Atom support
        ### dictionary will be elaborated by activator
        if etpConst['rss-feed'] and not self.clientDatabase:
            rssAtom = pkgatom+"~"+str(revision)
            # store addPackage action
            rssObj = dumpTools.loadobj(etpConst['rss-dump-name'])
            if rssObj:
                global etpRSSMessages
                etpRSSMessages = rssObj.copy()
            if rssAtom in etpRSSMessages['removed']:
                del etpRSSMessages['removed'][rssAtom]
            etpRSSMessages['added'][rssAtom] = {}
            etpRSSMessages['added'][rssAtom]['description'] = etpData['description']
            etpRSSMessages['added'][rssAtom]['homepage'] = etpData['homepage']
            # save
            dumpTools.dumpobj(etpConst['rss-dump-name'],etpRSSMessages)

	# create new idflag if it doesn't exist
	idflags = self.areCompileFlagsAvailable(etpData['chost'],etpData['cflags'],etpData['cxxflags'])
	if (idflags == -1):
	    # create category
	    idflags = self.addCompileFlags(etpData['chost'],etpData['cflags'],etpData['cxxflags'])

	# extrainfo
	self.cursor.execute(
		'INSERT into extrainfo VALUES '
		'(?,?,?,?,?,?,?,?)'
		, (	idpackage,
			etpData['description'],
			etpData['homepage'],
			etpData['download'],
			etpData['size'],
			idflags,
			etpData['digest'],
			etpData['datecreation'],
			)
	)

	# content, a list
	for xfile in etpData['content']:
            contenttype = etpData['content'][xfile]
            try:
                self.cursor.execute(
                    'INSERT into content VALUES '
                    '(?,?,?)'
                    , (	idpackage,
                            xfile,
                            contenttype,
                            )
                )
            except:
                self.createContentTypeColumn()
                self.cursor.execute(
                    'INSERT into content VALUES '
                    '(?,?,?)'
                    , ( idpackage,
                            xfile,
                            contenttype,
                            )
                )

        etpData['counter'] = int(etpData['counter']) # cast to integer
	if etpData['counter'] != -1 and not (etpData['injected']):
            
            if etpData['counter'] <= -2:
                # special cases
                
                try:
                    mycounters = list(self.listAllCounters(onlycounters = True))
                    mycounter = min(mycounters)
                    if mycounter >= -1:
                        etpData['counter'] = -2
                    else:
                        etpData['counter'] = mycounter-1
                except:
                    etpData['counter'] = -2
            
            try:
                self.cursor.execute(
                'INSERT into counters VALUES '
                '(?,?)'
                , ( etpData['counter'],
                    idpackage,
                    )
                )
            except:
                if self.dbname == "client": # force only for client database
                    self.createCountersTable()
                    self.cursor.execute(
                    'INSERT into counters VALUES '
                    '(?,?)'
                    , ( etpData['counter'],
                        idpackage,
                        )
                    )
                elif self.dbname == "etpdb":
                    raise
	
	# on disk size
	try:
	    self.cursor.execute(
	    'INSERT into sizes VALUES '
	    '(?,?)'
	    , (	idpackage,
		etpData['disksize'],
		)
	    )
	except:
	    # create sizes table, temp hack
	    self.createSizesTable()
	    self.cursor.execute(
	    'INSERT into sizes VALUES '
	    '(?,?)'
	    , (	idpackage,
		etpData['disksize'],
		)
	    )

        # trigger blob
        try:
	    self.cursor.execute(
	    'INSERT into triggers VALUES '
	    '(?,?)'
	    , (	idpackage,
		buffer(etpData['trigger']),
	    ))
        except:
	    # create trigggers table, temp hack
	    self.createTriggerTable()
	    self.cursor.execute(
	    'INSERT into triggers VALUES '
	    '(?,?)'
	    , (	idpackage,
		buffer(etpData['trigger']),
	    ))

	# eclasses table
	for var in etpData['eclasses']:
	    
	    try:
	        idclass = self.isEclassAvailable(var)
	    except:
		self.createEclassesTable()
		idclass = self.isEclassAvailable(var)
	    
	    if (idclass == -1):
	        # create eclass
	        idclass = self.addEclass(var)
	    
	    self.cursor.execute(
		'INSERT into eclasses VALUES '
		'(?,?)'
		, (	idpackage,
			idclass,
			)
	    )

	# needed table
	for var in etpData['needed']:
	    
	    try:
	        idneeded = self.isNeededAvailable(var)
	    except:
		self.createNeededTable()
		idneeded = self.isNeededAvailable(var)
	    
	    if (idneeded == -1):
	        # create eclass
	        idneeded = self.addNeeded(var)
	    
	    self.cursor.execute(
		'INSERT into needed VALUES '
		'(?,?)'
		, (	idpackage,
			idneeded,
			)
	    )
	
	# dependencies, a list
	for dep in etpData['dependencies']:
	
	    iddep = self.isDependencyAvailable(dep)
	    if (iddep == -1):
	        # create category
	        iddep = self.addDependency(dep)
	
	    self.cursor.execute(
		'INSERT into dependencies VALUES '
		'(?,?)'
		, (	idpackage,
			iddep,
			)
	    )

	# provide
	for atom in etpData['provide']:
	    self.cursor.execute(
		'INSERT into provide VALUES '
		'(?,?)'
		, (	idpackage,
			atom,
			)
	    )

        # injected?
        if etpData['injected']:
            try:
                self.cursor.execute(
                    'INSERT into injected VALUES '
                    '(?)'
                    , ( idpackage, )
                )
            except: # FIXME: remove this before 1.0
                self.createInjectedTable()
                self.cursor.execute(
                    'INSERT into injected VALUES '
                    '(?)'
                    , ( idpackage, )
                )

	# compile messages
	try:
	    for message in etpData['messages']:
	        self.cursor.execute(
		'INSERT into messages VALUES '
		'(?,?)'
		, (	idpackage,
			message,
			)
	        )
	except:
	    # FIXME: temp workaround, create messages table
	    self.cursor.execute("CREATE TABLE messages ( idpackage INTEGER, message VARCHAR);")
	    for message in etpData['messages']:
	        self.cursor.execute(
		'INSERT into messages VALUES '
		'(?,?)'
		, (	idpackage,
			message,
			)
	        )
	
        try:
            # is it a system package?
            if etpData['systempackage']:
                self.cursor.execute(
                    'INSERT into systempackages VALUES '
                    '(?)'
                    , (	idpackage,
                            )
                )
        except:
            # FIXME: temp workaround, create systempackages table
            self.createSystemPackagesTable()
            # is it a system package?
            if etpData['systempackage']:
                self.cursor.execute(
                    'INSERT into systempackages VALUES '
                    '(?)'
                    , (	idpackage,
                            )
                )

	# create new protect if it doesn't exist
	try:
	    idprotect = self.isProtectAvailable(etpData['config_protect'])
	except:
	    self.createProtectTable()
	    idprotect = self.isProtectAvailable(etpData['config_protect'])
	if (idprotect == -1):
	    # create category
	    idprotect = self.addProtect(etpData['config_protect'])
	# fill configprotect
	self.cursor.execute(
		'INSERT into configprotect VALUES '
		'(?,?)'
		, (	idpackage,
			idprotect,
			)
	)
	
	idprotect = self.isProtectAvailable(etpData['config_protect_mask'])
	if (idprotect == -1):
	    # create category
	    idprotect = self.addProtect(etpData['config_protect_mask'])
	# fill configprotect
	self.cursor.execute(
		'INSERT into configprotectmask VALUES '
		'(?,?)'
		, (	idpackage,
			idprotect,
			)
	)

	# conflicts, a list
	for conflict in etpData['conflicts']:
	    self.cursor.execute(
		'INSERT into conflicts VALUES '
		'(?,?)'
		, (	idpackage,
			conflict,
			)
	    )

	# mirrorlinks, always update the table
	for mirrordata in etpData['mirrorlinks']:
	    mirrorname = mirrordata[0]
	    mirrorlist = mirrordata[1]
	    # remove old
	    self.removeMirrorEntries(mirrorname)
	    # add new
	    self.addMirrors(mirrorname,mirrorlist)

	# sources, a list
	for source in etpData['sources']:
	    
	    idsource = self.isSourceAvailable(source)
	    if (idsource == -1):
	        # create category
	        idsource = self.addSource(source)
	    
	    self.cursor.execute(
		'INSERT into sources VALUES '
		'(?,?)'
		, (	idpackage,
			idsource,
			)
	    )

	# useflags, a list
	for flag in etpData['useflags']:
	    
	    iduseflag = self.isUseflagAvailable(flag)
	    if (iduseflag == -1):
	        # create category
	        iduseflag = self.addUseflag(flag)
	    
	    self.cursor.execute(
		'INSERT into useflags VALUES '
		'(?,?)'
		, (	idpackage,
			iduseflag,
			)
	    )

	# create new keyword if it doesn't exist
	for key in etpData['keywords']:

	    idkeyword = self.isKeywordAvailable(key)
	    if (idkeyword == -1):
	        # create category
	        idkeyword = self.addKeyword(key)

	    self.cursor.execute(
		'INSERT into keywords VALUES '
		'(?,?)'
		, (	idpackage,
			idkeyword,
			)
	    )

	for key in etpData['binkeywords']:

	    idbinkeyword = self.isKeywordAvailable(key)
	    if (idbinkeyword == -1):
	        # create category
	        idbinkeyword = self.addKeyword(key)

	    self.cursor.execute(
		'INSERT into binkeywords VALUES '
		'(?,?)'
		, (	idpackage,
			idbinkeyword,
			)
	    )

	# clear caches
	dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
	dbCacheStore[etpCache['dbSearch']+self.dbname] = {}
	# dump to be sure
	dumpTools.dumpobj(etpCache['dbMatch']+self.dbname,{})
	dumpTools.dumpobj(etpCache['dbSearch']+self.dbname,{})
        self.clearInfoCache()

	self.packagesAdded = True
	self.commitChanges()
	
	return idpackage, revision, etpData, True

    # Update already available atom in db
    # returns True,revision if the package has been updated
    # returns False,revision if not
    def updatePackage(self, etpData, forcedRevision = -1):

	self.checkReadOnly()

	# build atom string
	versiontag = ''
	if etpData['versiontag']:
	    versiontag = '#'+etpData['versiontag']
	pkgatom = etpData['category'] + "/" + etpData['name'] + "-" + etpData['version']+versiontag

	# for client database - the atom if present, must be overwritten with the new one regardless its branch
	if (self.clientDatabase):
	    
	    atomid = self.isPackageAvailable(pkgatom)
	    if atomid > -1:
		self.removePackage(atomid)
	    
	    x,y,z,accepted = self.addPackage(etpData, revision = forcedRevision)
	    return x,y,z,accepted
	    
	else:
	    # update package in etpData['branch']
	    # get its package revision
	    idpackage = self.getIDPackage(pkgatom,etpData['branch'])
	    if (forcedRevision == -1):
	        if (idpackage != -1):
	            curRevision = self.retrieveRevision(idpackage)
	        else:
	            curRevision = 0
	    else:
		curRevision = forcedRevision

	    if (idpackage != -1): # remove old package in branch
	        self.removePackage(idpackage)
		if (forcedRevision == -1):
		    curRevision += 1
	    
	    # add the new one
	    x,y,z,accepted = self.addPackage(etpData, revision = curRevision)
	    return x,y,z,accepted
	

    def removePackage(self,idpackage):

	self.checkReadOnly()

        ### RSS Atom support
        ### dictionary will be elaborated by activator
        if etpConst['rss-feed'] and not self.clientDatabase:
            # store addPackage action
            rssObj = dumpTools.loadobj(etpConst['rss-dump-name'])
            if rssObj:
                global etpRSSMessages
                etpRSSMessages = rssObj.copy()
            rssAtom = self.retrieveAtom(idpackage)
            rssRevision = self.retrieveRevision(idpackage)
            rssAtom += "~"+str(rssRevision)
            if rssAtom in etpRSSMessages['added']:
                del etpRSSMessages['added'][rssAtom]
            etpRSSMessages['removed'][rssAtom] = {}
            try:
                etpRSSMessages['removed'][rssAtom]['description'] = self.retrieveDescription(idpackage)
            except:
                etpRSSMessages['removed'][rssAtom]['description'] = "N/A"
            try:
                etpRSSMessages['removed'][rssAtom]['homepage'] = self.retrieveHomepage(idpackage)
            except:
                etpRSSMessages['removed'][rssAtom]['homepage'] = ""
            # save
            dumpTools.dumpobj(etpConst['rss-dump-name'],etpRSSMessages)

	idpackage = str(idpackage)
	# baseinfo
	self.cursor.execute('DELETE FROM baseinfo WHERE idpackage = '+idpackage)
	# extrainfo
	self.cursor.execute('DELETE FROM extrainfo WHERE idpackage = '+idpackage)
	# content
	self.cursor.execute('DELETE FROM content WHERE idpackage = '+idpackage)
	# dependencies
	self.cursor.execute('DELETE FROM dependencies WHERE idpackage = '+idpackage)
	# provide
	self.cursor.execute('DELETE FROM provide WHERE idpackage = '+idpackage)
	# conflicts
	self.cursor.execute('DELETE FROM conflicts WHERE idpackage = '+idpackage)
	# protect
	self.cursor.execute('DELETE FROM configprotect WHERE idpackage = '+idpackage)
	# protect_mask
	self.cursor.execute('DELETE FROM configprotectmask WHERE idpackage = '+idpackage)
	# sources
	self.cursor.execute('DELETE FROM sources WHERE idpackage = '+idpackage)
	# useflags
	self.cursor.execute('DELETE FROM useflags WHERE idpackage = '+idpackage)
	# keywords
	self.cursor.execute('DELETE FROM keywords WHERE idpackage = '+idpackage)
	# binkeywords
	self.cursor.execute('DELETE FROM binkeywords WHERE idpackage = '+idpackage)
	
	#
	# WARNING: exception won't be handled anymore with 1.0
	#
	
	try:
	    # messages
	    self.cursor.execute('DELETE FROM messages WHERE idpackage = '+idpackage)
	except:
	    pass
        try:
	    # systempackage
	    self.cursor.execute('DELETE FROM systempackages WHERE idpackage = '+idpackage)
        except:
            pass
	try:
	    # counter
	    self.cursor.execute('DELETE FROM counters WHERE idpackage = '+idpackage)
	except:
            if self.dbname == "client":
                self.createCountersTable()
	try:
	    # on disk sizes
	    self.cursor.execute('DELETE FROM sizes WHERE idpackage = '+idpackage)
	except:
	    pass
	try:
	    # eclasses
	    self.cursor.execute('DELETE FROM eclasses WHERE idpackage = '+idpackage)
	except:
	    pass
	try:
	    # needed
	    self.cursor.execute('DELETE FROM needed WHERE idpackage = '+idpackage)
	except:
	    pass
	try:
	    # triggers
	    self.cursor.execute('DELETE FROM triggers WHERE idpackage = '+idpackage)
	except:
	    pass
	try:
	    # inject table
	    self.cursor.execute('DELETE FROM injected WHERE idpackage = '+idpackage)
	except:
	    pass
	
	# Remove from installedtable if exists
	self.removePackageFromInstalledTable(idpackage)
	# Remove from dependstable if exists
	self.removePackageFromDependsTable(idpackage)
	# need a final cleanup
	self.packagesRemoved = True

	# clear caches
	dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
	dbCacheStore[etpCache['dbSearch']+self.dbname] = {}
	# dump to be sure
	dumpTools.dumpobj(etpCache['dbMatch']+self.dbname,{})
	dumpTools.dumpobj(etpCache['dbSearch']+self.dbname,{})
        self.clearInfoCache()

	self.commitChanges()

    def removeMirrorEntries(self,mirrorname):
	self.cursor.execute('DELETE FROM mirrorlinks WHERE mirrorname = "'+mirrorname+'"')
	self.commitChanges()

    def addMirrors(self,mirrorname,mirrorlist):
	for x in mirrorlist:
	    self.cursor.execute(
		'INSERT into mirrorlinks VALUES '
		'(?,?)', (mirrorname,x,)
	    )
	self.commitChanges()

    def addCategory(self,category):
	self.cursor.execute(
		'INSERT into categories VALUES '
		'(NULL,?)', (category,)
	)
	# get info about inserted value and return
	cat = self.isCategoryAvailable(category)
	if cat != -1:
	    self.commitChanges()
	    return cat
        raise exceptionTools.CorruptionError("CorruptionError: I tried to insert a category but then, fetching it returned -1. There's something broken.")

    def addProtect(self,protect):
	self.cursor.execute(
		'INSERT into configprotectreference VALUES '
		'(NULL,?)', (protect,)
	)
	# get info about inserted value and return
	try:
	    prt = self.isProtectAvailable(protect)
	except:
	    self.createProtectTable()
	    prt = self.isProtectAvailable(protect)
	if prt != -1:
	    return prt
        raise exceptionTools.CorruptionError("CorruptionError: I tried to insert a protect but then, fetching it returned -1. There's something broken.")

    def addSource(self,source):
	self.cursor.execute(
		'INSERT into sourcesreference VALUES '
		'(NULL,?)', (source,)
	)
	# get info about inserted value and return
	src = self.isSourceAvailable(source)
	if src != -1:
	    return src
        raise exceptionTools.CorruptionError("CorruptionError: I tried to insert a source but then, fetching it returned -1. There's something broken.")

    def addDependency(self,dependency):
	self.cursor.execute(
		'INSERT into dependenciesreference VALUES '
		'(NULL,?)', (dependency,)
	)
	# get info about inserted value and return
	dep = self.isDependencyAvailable(dependency)
	if dep != -1:
	    return dep
        raise exceptionTools.CorruptionError("CorruptionError: I tried to insert a dependency but then, fetching it returned -1. There's something broken.")

    def addKeyword(self,keyword):
	self.cursor.execute(
		'INSERT into keywordsreference VALUES '
		'(NULL,?)', (keyword,)
	)
	# get info about inserted value and return
	key = self.isKeywordAvailable(keyword)
	if key != -1:
	    return key
        raise exceptionTools.CorruptionError("CorruptionError: I tried to insert a keyword but then, fetching it returned -1. There's something broken.")

    def addUseflag(self,useflag):
	self.cursor.execute(
		'INSERT into useflagsreference VALUES '
		'(NULL,?)', (useflag,)
	)
	# get info about inserted value and return
	use = self.isUseflagAvailable(useflag)
	if use != -1:
	    return use
        raise exceptionTools.CorruptionError("CorruptionError: I tried to insert a use flag but then, fetching it returned -1. There's something broken.")

    def addEclass(self,eclass):
	self.cursor.execute(
		'INSERT into eclassesreference VALUES '
		'(NULL,?)', (eclass,)
	)
	# get info about inserted value and return
	try:
	    myclass = self.isEclassAvailable(eclass)
	except:
	    self.createEclassesTable()
	    myclass = self.isEclassAvailable(eclass)
	if myclass != -1:
	    return myclass
        raise exceptionTools.CorruptionError("CorruptionError: I tried to insert an eclass but then, fetching it returned -1. There's something broken.")

    def addNeeded(self,needed):
	self.cursor.execute(
		'INSERT into neededreference VALUES '
		'(NULL,?)', (needed,)
	)
	# get info about inserted value and return
	try:
	    myneeded = self.isNeededAvailable(needed)
	except:
	    self.createNeededTable()
	    myneeded = self.isNeededAvailable(needed)
	if myneeded != -1:
	    return myneeded
        raise exceptionTools.CorruptionError("CorruptionError: I tried to insert a needed library but then, fetching it returned -1. There's something broken.")

    def addLicense(self,pkglicense):
        if not pkglicense:
            pkglicense = ' ' # workaround for broken license entries
	self.cursor.execute(
		'INSERT into licenses VALUES '
		'(NULL,?)', (pkglicense,)
	)
	# get info about inserted value and return
	lic = self.isLicenseAvailable(pkglicense)
	if lic != -1:
	    return lic
        raise exceptionTools.CorruptionError("CorruptionError: I tried to insert a license but then, fetching it returned -1. There's something broken.")

    #addCompileFlags(etpData['chost'],etpData['cflags'],etpData['cxxflags'])
    def addCompileFlags(self,chost,cflags,cxxflags):
        self.cursor.execute(
                'INSERT into flags VALUES '
                '(NULL,?,?,?)', (chost,cflags,cxxflags,)
        )
        self.commitChanges()
        # get info about inserted value and return
        idflag = self.areCompileFlagsAvailable(chost,cflags,cxxflags)
        if idflag != -1:
            return idflag
        raise exceptionTools.CorruptionError("CorruptionError: I tried to insert compile flags but then, fetching it returned -1. There's something broken.")

    def setDigest(self, idpackage, digest):
        self.cursor.execute('UPDATE extrainfo SET digest = (?) WHERE idpackage = (?)', (digest,idpackage,))
    
    def setDownloadURL(self, idpackage, url):
        self.cursor.execute('UPDATE extrainfo SET download = (?) WHERE idpackage = (?)', (url,idpackage,))

    def setCategory(self, idpackage, category):
        # create new category if it doesn't exist
        catid = self.isCategoryAvailable(category)
        if (catid == -1):
            # create category
            catid = self.addCategory(category)
        self.cursor.execute('UPDATE baseinfo SET idcategory = (?) WHERE idpackage = (?)', (catid,idpackage,))
        self.commitChanges()

    def setName(self, idpackage, name):
	self.cursor.execute('UPDATE baseinfo SET name = (?) WHERE idpackage = (?)', (name,idpackage,))
        self.commitChanges()

    def setDependency(self, iddependency, dependency):
	self.cursor.execute('UPDATE dependenciesreference SET dependency = (?) WHERE iddependency = (?)', (dependency,iddependency,))
        self.commitChanges()

    def setAtom(self, idpackage, atom):
	self.cursor.execute('UPDATE baseinfo SET atom = (?) WHERE idpackage = (?)', (atom,idpackage,))
        self.commitChanges()

    def setSlot(self, idpackage, slot):
	self.cursor.execute('UPDATE baseinfo SET slot = (?) WHERE idpackage = (?)', (slot,idpackage,))
        self.commitChanges()

    def setCounter(self, idpackage, counter):
        try:
            self.cursor.execute('UPDATE counters SET counter = (?) WHERE idpackage = (?)', (counter,idpackage,))
        except:
            if self.dbname == "client":
                self.createCountersTable()
                self.cursor.execute(
                    'INSERT into counters VALUES '
                    '(?,?)', (counter,idpackage,)
                )

    def cleanupUseflags(self):
	self.cursor.execute('SELECT idflag FROM useflagsreference')
	idflags = self.fetchall2set(self.cursor.fetchall())
	# now parse them into useflags table
	orphanedFlags = idflags.copy()
	
	foundflags = set()
	query = 'WHERE idflag = '
	counter = 0
	run = False
	for idflag in idflags:
	    run = True
	    counter += 1
	    query += str(idflag)+' OR idflag = '
	    if counter > 25:
		counter = 0
		query = query[:-13]
		self.cursor.execute('SELECT idflag FROM useflags '+query)
		foundflags.update(self.fetchall2set(self.cursor.fetchall()))
		query = 'WHERE idflag = '
		run = False
	
	if (run):
	    query = query[:-13]
	    self.cursor.execute('SELECT idflag FROM useflags '+query)
	    foundflags.update(self.fetchall2set(self.cursor.fetchall()))
	orphanedFlags.difference_update(foundflags)
	
	for idflag in orphanedFlags:
	    self.cursor.execute('DELETE FROM useflagsreference WHERE idflag ='+str(idflag))

    def cleanupSources(self):
	self.cursor.execute('SELECT idsource FROM sourcesreference')
	idsources = self.fetchall2set(self.cursor.fetchall())
	# now parse them into useflags table
	orphanedSources = idsources.copy()

	foundsources = set()
	query = 'WHERE idsource = '
	counter = 0
	run = False
	for idsource in idsources:
	    run = True
	    counter += 1
	    query += str(idsource)+' OR idsource = '
	    if counter > 25:
		counter = 0
		query = query[:-15]
		self.cursor.execute('SELECT idsource FROM sources '+query)
		foundsources.update(self.fetchall2set(self.cursor.fetchall()))
		query = 'WHERE idsource = '
		run = False
	
	if (run):
	    query = query[:-15]
	    self.cursor.execute('SELECT idsource FROM sources '+query)
	    foundsources.update(self.fetchall2set(self.cursor.fetchall()))
	orphanedSources.difference_update(foundsources)
	
	for idsource in orphanedSources:
	    self.cursor.execute('DELETE FROM sourcesreference WHERE idsource = '+str(idsource))

    def cleanupEclasses(self):
	self.cursor.execute('SELECT idclass FROM eclassesreference')
	idclasses = self.fetchall2set(self.cursor.fetchall())
	# now parse them into useflags table
	orphanedClasses = idclasses.copy()

	foundclasses = set()
	query = 'WHERE idclass = '
	counter = 0
	run = False
	for idclass in idclasses:
	    run = True
	    counter += 1
	    query += str(idclass)+' OR idclass = '
	    if counter > 25:
		counter = 0
		query = query[:-14]
		self.cursor.execute('SELECT idclass FROM eclasses '+query)
		foundclasses.update(self.fetchall2set(self.cursor.fetchall()))
		query = 'WHERE idclass = '
		run = False
	
	if (run):
	    query = query[:-14]
	    self.cursor.execute('SELECT idclass FROM eclasses '+query)
	    foundclasses.update(self.fetchall2set(self.cursor.fetchall()))
	orphanedClasses.difference_update(foundclasses)
	
	for idclass in orphanedClasses:
	    self.cursor.execute('DELETE FROM eclassesreference WHERE idclass = '+str(idclass))

    def cleanupNeeded(self):
	self.cursor.execute('SELECT idneeded FROM neededreference')
	idneededs = self.fetchall2set(self.cursor.fetchall())
	# now parse them into useflags table
	orphanedNeededs = idneededs.copy()

	foundneeded = set()
	query = 'WHERE idneeded = '
	counter = 0
	run = False
	for idneeded in idneededs:
	    run = True
	    counter += 1
	    query += str(idneeded)+' OR idneeded = '
	    if counter > 25:
		counter = 0
		query = query[:-15]
		self.cursor.execute('SELECT idneeded FROM needed '+query)
		foundneeded.update(self.fetchall2set(self.cursor.fetchall()))
		query = 'WHERE idneeded = '
		run = False
	
	if (run):
	    query = query[:-15]
	    self.cursor.execute('SELECT idneeded FROM needed '+query)
	    foundneeded.update(self.fetchall2set(self.cursor.fetchall()))
	orphanedNeededs.difference_update(foundneeded)
	
	for idneeded in orphanedNeededs:
	    self.cursor.execute('DELETE FROM neededreference WHERE idneeded = '+str(idneeded))


    def cleanupDependencies(self):
	self.cursor.execute('SELECT iddependency FROM dependenciesreference')
	iddeps = self.fetchall2set(self.cursor.fetchall())
	# now parse them into useflags table
	orphanedDeps = iddeps.copy()

	founddeps = set()
	query = 'WHERE iddependency = '
	counter = 0
	run = False
	for iddep in iddeps:
	    run = True
	    counter += 1
	    query += str(iddep)+' OR iddependency = '
	    if counter > 25:
		counter = 0
		query = query[:-19]
		self.cursor.execute('SELECT iddependency FROM dependencies '+query)
		founddeps.update(self.fetchall2set(self.cursor.fetchall()))
		query = 'WHERE iddependency = '
		run = False
	
	if (run):
	    query = query[:-19]
	    self.cursor.execute('SELECT iddependency FROM dependencies '+query)
	    founddeps.update(self.fetchall2set(self.cursor.fetchall()))
	orphanedDeps.difference_update(founddeps)

	for iddep in orphanedDeps:
	    self.cursor.execute('DELETE FROM dependenciesreference WHERE iddependency = '+str(iddep))

    def getIDPackage(self, atom, branch = etpConst['branch']):
	self.cursor.execute('SELECT "IDPACKAGE" FROM baseinfo WHERE atom = "'+atom+'" AND branch = "'+branch+'"')
	idpackage = -1
        idpackage = self.cursor.fetchone()
        if idpackage:
            idpackage = idpackage[0]
        else:
            idpackage = -1
	return idpackage

    def getIDPackageFromFileInBranch(self, file, branch = "unstable"):
	self.cursor.execute('SELECT idpackage FROM content WHERE file = "'+file+'"')
	idpackages = []
	for row in self.cursor:
	    idpackages.append(row[0])
	result = []
	for pkg in idpackages:
	    self.cursor.execute('SELECT idpackage FROM baseinfo WHERE idpackage = "'+str(pkg)+'" and branch = "'+branch+'"')
	    for row in self.cursor:
		result.append(row[0])
	return result

    def getIDPackagesFromFile(self, file):
	self.cursor.execute('SELECT idpackage FROM content WHERE file = "'+file+'"')
	idpackages = []
	for row in self.cursor:
	    idpackages.append(row[0])
	return idpackages

    def getIDCategory(self, category):
	self.cursor.execute('SELECT "idcategory" FROM categories WHERE category = "'+str(category)+'"')
	idcat = -1
	for row in self.cursor:
	    idcat = int(row[0])
	    break
	return idcat

    def getIDPackageFromBinaryPackage(self,packageName):
	self.cursor.execute('SELECT "IDPACKAGE" FROM baseinfo WHERE download = "'+etpConst['binaryurirelativepath']+packageName+'"')
	idpackage = -1
	for row in self.cursor:
	    idpackage = int(row[0])
	    break
	return idpackage

    def getBaseData(self,idpackage):
        
        self.createBaseinfoIndex()
        self.createExtrainfoIndex()
        
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
			baseinfo.idpackage = '"""+str(idpackage)+"""' 
			and baseinfo.idpackage = extrainfo.idpackage 
			and baseinfo.idcategory = categories.idcategory 
			and extrainfo.idflags = flags.idflags
			and baseinfo.idlicense = licenses.idlicense
	"""
	self.cursor.execute(sql)
	return self.cursor.fetchone()
	

    def getPackageData(self, idpackage):
	data = {}

	mydata = self.getBaseData(idpackage)
	
	data['name'] = mydata[1]
	data['version'] = mydata[2]
	data['versiontag'] = mydata[3]
	data['description'] = mydata[4]
	data['category'] = mydata[5]
	
	data['chost'] = mydata[6]
	data['cflags'] = mydata[7]
	data['cxxflags'] = mydata[8]
	
	data['homepage'] = mydata[9]
	data['useflags'] = self.retrieveUseflags(idpackage)
	data['license'] = mydata[10]
	
	data['keywords'] = self.retrieveKeywords(idpackage)
	data['binkeywords'] = self.retrieveBinKeywords(idpackage)
	
	data['branch'] = mydata[11]
	data['download'] = mydata[12]
	data['digest'] = mydata[13]
	data['sources'] = self.retrieveSources(idpackage)
	data['counter'] = self.retrieveCounter(idpackage) # cannot insert into the sql above
	data['messages'] = self.retrieveMessages(idpackage)
	data['trigger'] = self.retrieveTrigger(idpackage) #FIXME: needed for now because of new column
	
	if (self.isSystemPackage(idpackage)):
	    data['systempackage'] = 'xxx'
	else:
	    data['systempackage'] = ''
	
	# FIXME: this will be removed when 1.0 will be out
	try:
	    data['config_protect'] = self.retrieveProtect(idpackage)
	    data['config_protect_mask'] = self.retrieveProtectMask(idpackage)
	except:
	    self.createProtectTable()
	    data['config_protect'] = self.retrieveProtect(idpackage)
	    data['config_protect_mask'] = self.retrieveProtectMask(idpackage)
	try:
	    data['eclasses'] = self.retrieveEclasses(idpackage)
	except:
	    self.createEclassesTable()
	    data['eclasses'] = self.retrieveEclasses(idpackage)
	try:
	    data['needed'] = self.retrieveNeeded(idpackage)
	except:
	    self.createNeededTable()
	    data['needed'] = self.retrieveNeeded(idpackage)
	
	mirrornames = set()
	for x in data['sources']:
	    if x.startswith("mirror://"):
		mirrorname = x.split("/")[2]
		mirrornames.add(mirrorname)
	data['mirrorlinks'] = []
	for mirror in mirrornames:
	    mirrorlinks = self.retrieveMirrorInfo(mirror)
	    data['mirrorlinks'].append([mirror,mirrorlinks])
	
	data['slot'] = mydata[14]
        data['injected'] = self.isInjected(idpackage)
        mycontent = self.retrieveContent(idpackage, extended = True)
        data['content'] = {}
        for cdata in mycontent:
            data['content'][cdata[0]] = cdata[1]
	
	data['dependencies'] = self.retrieveDependencies(idpackage)
	data['provide'] = self.retrieveProvide(idpackage)
	data['conflicts'] = self.retrieveConflicts(idpackage)
	
	data['etpapi'] = mydata[15]
	data['datecreation'] = mydata[16]
	data['size'] = mydata[17]
	data['revision'] = mydata[18]
	data['disksize'] = self.retrieveOnDiskSize(idpackage) # cannot do this too, for backward compat
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

    def clearInfoCache(self):
        # clear caches
        dbCacheStore[etpCache['dbInfo']+self.dbname] = {}
        # dump to be sure
        dumpTools.dumpobj(etpCache['dbInfo']+self.dbname,{})

    def fetchInfoCache(self,idpackage,function):
	if (self.xcache):
            try:
                cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage))
            except KeyError: # dict does not exist?
                self.clearInfoCache()
                return None
	    if cached != None:
		rslt = cached.get(function)
		if rslt != None:
                    if (type(rslt) is dict) or (type(rslt) is set): # needed ?
                        return rslt.copy()
                    elif (type(rslt) is list):
                        return rslt[:]
                    else:
                        return rslt
	return None

    def storeInfoCache(self,idpackage,function,info_cache_data):
	if (self.xcache):
            try:
                cache = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage))
            except KeyError: # something bad happened even here, reset cache
                self.clearInfoCache()
                cache = None
	    if cache == None: dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}
            if (type(info_cache_data) is set) or (type(info_cache_data) is dict):
                dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)][function] = info_cache_data.copy()
            elif (type(info_cache_data) is list):
                dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)][function] = info_cache_data[:]
            else:
                dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)][function] = info_cache_data

    def fetchSearchCache(self,searchdata,function):
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbSearch']+self.dbname].get(function)
	    if cached != None:
		rslt = cached.get(searchdata)
		if rslt != None:
                    if (type(rslt) is dict) or (type(rslt) is set): # needed ?
                        return rslt.copy()
                    elif (type(rslt) is list):
                        return rslt[:]
                    else:
                        return rslt
	return None

    def storeSearchCache(self,searchdata,function,data):
	if (self.xcache):
	    cache = dbCacheStore[etpCache['dbSearch']+self.dbname].get(function)
	    if cache == None: dbCacheStore[etpCache['dbSearch']+self.dbname][function] = {}
            if (type(data) is set) or (type(data) is dict):
	        dbCacheStore[etpCache['dbSearch']+self.dbname][function][searchdata] = data.copy()
            else:
	        dbCacheStore[etpCache['dbSearch']+self.dbname][function][searchdata] = data

    def retrieveRepositoryUpdatesDigest(self, repository):
        try:
            self.cursor.execute('SELECT digest FROM treeupdates WHERE repository = (?)', (repository,))
        except:
            self.createTreeupdatesTable()
            self.cursor.execute('SELECT digest FROM treeupdates WHERE repository = (?)', (repository,))
        mydigest = self.cursor.fetchone()
        if mydigest:
            return mydigest[0]
        else:
            return -1
    
    def listAllTreeUpdatesActions(self):
        try:
            self.cursor.execute('SELECT * FROM treeupdatesactions')
        except:
            self.createTreeupdatesactionsTable()
            self.cursor.execute('SELECT * FROM treeupdatesactions')
        return self.cursor.fetchall()
    
    def retrieveTreeUpdatesActions(self, repository):
        try:
            self.cursor.execute('SELECT command FROM treeupdatesactions where repository = (?)', (repository,))
            return self.fetchall2set(self.cursor.fetchall())
        except:
            self.createTreeupdatesactionsTable()
            return set()
    
    # mainly used to restore a previous table, used by reagent in --initialize
    def addTreeUpdatesActions(self, updates):
        for update in updates:
            idupdate = update[0]
            repository = update[1]
            command = update[2]
            self.cursor.execute('INSERT INTO treeupdatesactions VALUES (?,?,?)', (idupdate,repository,command,))
    
    def setRepositoryUpdatesDigest(self, repository, digest):
        try:
            self.cursor.execute('DELETE FROM treeupdates where repository = (?)', (repository,)) # doing it for safety
        except:
            self.createTreeupdatesTable()
        self.cursor.execute('INSERT INTO treeupdates VALUES (?,?)', (repository,digest,))
    
    def addRepositoryUpdatesActions(self, repository, actions):
        for command in actions:
            try:
                self.cursor.execute('INSERT INTO treeupdatesactions VALUES (NULL,?,?)', (repository,command,))
            except:
                self.createTreeupdatesactionsTable()
                self.cursor.execute('INSERT INTO treeupdatesactions VALUES (NULL,?,?)', (repository,command,))

    def retrieveAtom(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveAtom')
	if cache != None: return cache

	self.cursor.execute('SELECT atom FROM baseinfo WHERE idpackage = (?)', (idpackage,))
	atom = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveAtom',atom)
	return atom

    def retrieveBranch(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveBranch')
	if cache != None: return cache

	self.cursor.execute('SELECT branch FROM baseinfo WHERE idpackage = (?)', (idpackage,))
	br = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveBranch',br)
	return br

    def retrieveTrigger(self, idpackage):

	#cache = self.fetchInfoCache(idpackage,'retrieveTrigger')
	#if cache != None: return cache
	
	try:
	    self.cursor.execute('SELECT data FROM triggers WHERE idpackage = (?)', (idpackage,))
	    trigger = self.cursor.fetchone()
            if trigger:
                trigger = trigger[0]
            else:
                trigger = ''
	except:
	    # generate trigger column
	    self.createTriggerTable()
	    trigger = ''
	    pass
	
	#self.storeInfoCache(idpackage,'retrieveTrigger',trigger)
	return trigger

    def retrieveDownloadURL(self, idpackage):
	
	cache = self.fetchInfoCache(idpackage,'retrieveDownloadURL')
	if cache != None: return cache

	self.cursor.execute('SELECT download FROM extrainfo WHERE idpackage = (?)', (idpackage,))
	download = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveDownloadURL',download)
	return download

    def retrieveDescription(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveDescription')
	if cache != None: return cache

	self.cursor.execute('SELECT description FROM extrainfo WHERE idpackage = (?)', (idpackage,))
	description = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveDescription',description)
	return description

    def retrieveHomepage(self, idpackage):
	
	cache = self.fetchInfoCache(idpackage,'retrieveHomepage')
	if cache != None: return cache

	self.cursor.execute('SELECT homepage FROM extrainfo WHERE idpackage = (?)', (idpackage,))
	home = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveHomepage',home)
	return home

    def retrieveCounter(self, idpackage):
	
	cache = self.fetchInfoCache(idpackage,'retrieveCounter')
	if cache != None: return cache
	
	counter = -1
	try:
	    self.cursor.execute('SELECT counter FROM counters WHERE idpackage = (?)', (idpackage,))
	    mycounter = self.cursor.fetchone()
	    if mycounter:
	        counter = mycounter[0]
	except:
            if self.dbname == "client":
                self.createCountersTable()
                counter = self.retrieveCounter(idpackage)
	
	self.storeInfoCache(idpackage,'retrieveCounter',int(counter))
	return int(counter)

    def retrieveMessages(self, idpackage):
	
	cache = self.fetchInfoCache(idpackage,'retrieveMessages')
	if cache != None: return cache

	messages = []
	try:
	    self.cursor.execute('SELECT message FROM messages WHERE idpackage = (?)', (idpackage,))
	    messages = self.fetchall2list(self.cursor.fetchall())
	except:
	    pass

	self.storeInfoCache(idpackage,'retrieveMessages',messages)
	return messages

    # in bytes
    def retrieveSize(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveSize')
	if cache != None: return cache

	self.cursor.execute('SELECT size FROM extrainfo WHERE idpackage = (?)', (idpackage,))
	size = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveSize',size)
	return size

    # in bytes
    def retrieveOnDiskSize(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveOnDiskSize')
	if cache != None: return cache

	try:
	    self.cursor.execute('SELECT size FROM sizes WHERE idpackage = (?)', (idpackage,))
	except:
	    self.createSizesTable()
	    # table does not exist?
	    return 0
	size = self.cursor.fetchone() # do not use [0]!
	if not size:
	    size = 0
	else:
	    size = size[0]

	self.storeInfoCache(idpackage,'retrieveOnDiskSize',size)
	return size

    def retrieveDigest(self, idpackage):
	
	cache = self.fetchInfoCache(idpackage,'retrieveDigest')
	if cache != None: return cache

	self.cursor.execute('SELECT "digest" FROM extrainfo WHERE idpackage = (?)', (idpackage,))
	digest = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveDigest',digest)
	return digest

    def retrieveName(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveName')
	if cache != None: return cache

	self.cursor.execute('SELECT "name" FROM baseinfo WHERE idpackage = (?)', (idpackage,))
	name = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveName',name)
	return name

    def retrieveVersion(self, idpackage):
	
	cache = self.fetchInfoCache(idpackage,'retrieveVersion')
	if cache != None: return cache
	
	self.cursor.execute('SELECT "version" FROM baseinfo WHERE idpackage = (?)', (idpackage,))
	ver = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveVersion',ver)
	return ver

    def retrieveRevision(self, idpackage):
	
	cache = self.fetchInfoCache(idpackage,'retrieveRevision')
	if cache != None: return cache

	self.cursor.execute('SELECT "revision" FROM baseinfo WHERE idpackage = (?)', (idpackage,))
	rev = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveRevision',rev)
	return rev

    def retrieveDateCreation(self, idpackage):
	
	cache = self.fetchInfoCache(idpackage,'retrieveDateCreation')
	if cache != None: return cache

	self.cursor.execute('SELECT "datecreation" FROM extrainfo WHERE idpackage = (?)', (idpackage,))
	date = self.cursor.fetchone()[0]
	if not date:
	    date = "N/A" #FIXME: to be removed?

	self.storeInfoCache(idpackage,'retrieveDateCreation',date)
	return date

    def retrieveApi(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveApi')
	if cache != None: return cache

	self.cursor.execute('SELECT "etpapi" FROM baseinfo WHERE idpackage = (?)', (idpackage,))
	api = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveApi',api)
	return api

    def retrieveUseflags(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveUseflags')
	if cache != None: return cache

	self.cursor.execute('SELECT flagname FROM useflags,useflagsreference WHERE useflags.idpackage = (?) and useflags.idflag = useflagsreference.idflag', (idpackage,))
	flags = self.fetchall2set(self.cursor.fetchall())
	

	self.storeInfoCache(idpackage,'retrieveUseflags',flags)
	return flags

    def retrieveEclasses(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveEclasses')
	if cache != None: return cache

	self.cursor.execute('SELECT classname FROM eclasses,eclassesreference WHERE eclasses.idpackage = (?) and eclasses.idclass = eclassesreference.idclass', (idpackage,))
	classes = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveEclasses',classes)
	return classes

    def retrieveNeeded(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveNeeded')
	if cache != None: return cache

	self.cursor.execute('SELECT library FROM needed,neededreference WHERE needed.idpackage = (?) and needed.idneeded = neededreference.idneeded', (idpackage,))
	needed = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveNeeded',needed)
	return needed

    def retrieveConflicts(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveConflicts')
	if cache != None: return cache

	self.cursor.execute('SELECT "conflict" FROM conflicts WHERE idpackage = (?)', (idpackage,))
	confl = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveConflicts',confl)
	return confl

    def retrieveProvide(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveProvide')
	if cache != None: return cache

	self.cursor.execute('SELECT "atom" FROM provide WHERE idpackage = (?)', (idpackage,))
	provide = self.fetchall2set(self.cursor.fetchall())
	
	self.storeInfoCache(idpackage,'retrieveProvide',provide)
	return provide

    def retrieveDependencies(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveDependencies')
	if cache != None: return cache
        
        self.createDependenciesIndex()
	
	self.cursor.execute('SELECT dependenciesreference.dependency FROM dependencies,dependenciesreference WHERE dependencies.idpackage = (?) and dependencies.iddependency = dependenciesreference.iddependency', (idpackage,))
        
	deps = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveDependencies',deps)
	return deps

    def retrieveIdDependencies(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveIdDependencies')
	if cache != None: return cache

	self.cursor.execute('SELECT iddependency FROM dependencies WHERE idpackage = (?)', (idpackage,))
	iddeps = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveIdDependencies',iddeps)
	return iddeps

    def retrieveDependencyFromIddependency(self, iddependency):
	self.cursor.execute('SELECT dependency FROM dependenciesreference WHERE iddependency = (?)', (iddependency,))
        return self.cursor.fetchone()[0]

    def retrieveBinKeywords(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveBinKeywords')
	if cache != None: return cache

	self.cursor.execute('SELECT keywordname FROM binkeywords,keywordsreference WHERE binkeywords.idpackage = (?) and binkeywords.idkeyword = keywordsreference.idkeyword', (idpackage,))
	kw = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveBinKeywords',kw)
	return kw

    def retrieveKeywords(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveKeywords')
	if cache != None: return cache

	self.cursor.execute('SELECT keywordname FROM keywords,keywordsreference WHERE keywords.idpackage = (?) and keywords.idkeyword = keywordsreference.idkeyword', (idpackage,))
	kw = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveKeywords',kw)
	return kw

    def retrieveProtect(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveProtect')
	if cache != None: return cache

	self.cursor.execute('SELECT protect FROM configprotect,configprotectreference WHERE configprotect.idpackage = (?) and configprotect.idprotect = configprotectreference.idprotect', (idpackage,))
        protect = self.cursor.fetchone()
        if not protect:
            protect = ''
	else:
	    protect = protect[0]

	self.storeInfoCache(idpackage,'retrieveProtect',protect)
	return protect

    def retrieveProtectMask(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveProtectMask')
	if cache != None: return cache

	self.cursor.execute('SELECT protect FROM configprotectmask,configprotectreference WHERE idpackage = (?) and configprotectmask.idprotect= configprotectreference.idprotect', (idpackage,))
	protect = self.cursor.fetchone()
        if not protect:
            protect = ''
	else:
	    protect = protect[0]
	
	self.storeInfoCache(idpackage,'retrieveProtectMask',protect)
	return protect

    def retrieveSources(self, idpackage):

	''' caching 
	cache = self.fetchInfoCache(idpackage,'retrieveSources')
	if cache != None: return cache
	'''

	self.cursor.execute('SELECT sourcesreference.source FROM sources,sourcesreference WHERE idpackage = (?) and sources.idsource = sourcesreference.idsource', (idpackage,))
	sources = self.fetchall2set(self.cursor.fetchall())

	''' caching
	self.storeInfoCache(idpackage,'retrieveSources',sources)
	'''
	return sources

    def retrieveContent(self, idpackage, extended = False, contentType = None):

        self.createContentIndex() # FIXME: remove this with 1.0
        
        # protect user from having a bad day
        # developers can solve bad utf-8 data (and MUST), so we won't skip bad chars for them
        if self.clientDatabase:
            self.connection.text_factory = lambda x: unicode(x, "utf-8", "ignore")
        
        extstring = ''
        if extended:
            extstring = ",type"
        
        searchkeywords = [idpackage]
        contentstring = ''
        if contentType:
            searchkeywords.append(contentType)
            contentstring = ' and type = (?)'

        try:
            self.cursor.execute('SELECT file'+extstring+' FROM content WHERE idpackage = (?) '+contentstring, searchkeywords)
        except:
            if extended:
                self.createContentTypeColumn()
                self.cursor.execute('SELECT file'+extstring+' FROM content WHERE idpackage = (?) '+contentstring, searchkeywords)
            else:
                raise
        if extended:
            fl = self.cursor.fetchall()
        else:
            fl = self.fetchall2set(self.cursor.fetchall())

	return fl

    def retrieveSlot(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveSlot')
	if cache != None: return cache

	self.cursor.execute('SELECT "slot" FROM baseinfo WHERE idpackage = (?)', (idpackage,))
	ver = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveSlot',ver)
	return ver
    
    def retrieveVersionTag(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveVersionTag')
	if cache != None: return cache

	self.cursor.execute('SELECT "versiontag" FROM baseinfo WHERE idpackage = (?)', (idpackage,))
	ver = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveVersionTag',ver)
	return ver
    
    def retrieveMirrorInfo(self, mirrorname):

	self.cursor.execute('SELECT "mirrorlink" FROM mirrorlinks WHERE mirrorname = (?)', (mirrorname,))
	mirrorlist = self.fetchall2set(self.cursor.fetchall())

	return mirrorlist

    def retrieveCategory(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveCategory')
	if cache != None: return cache

	self.cursor.execute('SELECT category FROM baseinfo,categories WHERE baseinfo.idpackage = (?) and baseinfo.idcategory = categories.idcategory', (idpackage,))
	cat = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveCategory',cat)
	return cat

    def retrieveLicense(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveLicense')
	if cache != None: return cache

	self.cursor.execute('SELECT license FROM baseinfo,licenses WHERE baseinfo.idpackage = (?) and baseinfo.idlicense = licenses.idlicense', (idpackage,))
	licname = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveLicense',licname)
	return licname

    def retrieveCompileFlags(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveCompileFlags')
	if cache != None: return cache

	self.cursor.execute('SELECT "idflags" FROM extrainfo WHERE idpackage = (?)', (idpackage,))
	idflag = self.cursor.fetchone()[0]
	# now get the flags
	self.cursor.execute('SELECT chost,cflags,cxxflags FROM flags WHERE idflags = (?)', (idflag,))
        flags = self.cursor.fetchone()
        if not flags:
            flags = ("N/A","N/A","N/A")

	self.storeInfoCache(idpackage,'retrieveCompileFlags',flags)
	return flags

    def retrieveDepends(self, idpackage):

	#cache = self.fetchInfoCache(idpackage,'retrieveDepends')
	#if cache != None: return cache

	# sanity check on the table
	sanity = self.isDependsTableSane()
	if (not sanity): # is empty, need generation
            self.regenerateDependsTable(output = False)

	self.cursor.execute('SELECT dependencies.idpackage FROM dependstable,dependencies WHERE dependstable.idpackage = (?) and dependstable.iddependency = dependencies.iddependency', (idpackage,))
	result = self.fetchall2set(self.cursor.fetchall())

	#self.storeInfoCache(idpackage,'retrieveDepends',result)
	return result

    # You must provide the full atom to this function
    # WARNING: this function does not support branches !!!
    def isPackageAvailable(self,pkgkey):
	pkgkey = entropyTools.removePackageOperators(pkgkey)
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE atom = "'+pkgkey+'"')
	result = self.cursor.fetchone()
	if result:
	    return result[0]
	return -1

    def isIDPackageAvailable(self,idpackage):
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE idpackage = (?)', (idpackage,))
	result = self.cursor.fetchone()
	if not result:
	    return False
	return True

    # This version is more specific and supports branches
    def isSpecificPackageAvailable(self, pkgkey, branch):
	pkgkey = entropyTools.removePackageOperators(pkgkey)
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE atom = (?) AND branch = (?)', (pkgkey,branch,))
	result = self.cursor.fetchone()
	if not result:
	    return False
	return True

    def isCategoryAvailable(self,category):
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = (?)', (category,))
	result = self.cursor.fetchone()
	if not result:
	    return -1
	return result[0]

    def isProtectAvailable(self,protect):
	self.cursor.execute('SELECT idprotect FROM configprotectreference WHERE protect = (?)', (protect,))
	result = self.cursor.fetchone()
	if not result:
	    return -1
	return result[0]

    def isFileAvailable(self, file, extended = False):
        self.createContentIndex() # FIXME: remove this with 1.0
        if extended:
            self.cursor.execute('SELECT * FROM content WHERE file = (?)', (file,))
        else:
            self.cursor.execute('SELECT idpackage FROM content WHERE file = (?)', (file,))
	result = self.cursor.fetchone()
	if not result:
            if extended:
                return False,()
            else:
                return False
        if extended:
            return True,result
        else:
            return True

    def isSourceAvailable(self,source):
	self.cursor.execute('SELECT idsource FROM sourcesreference WHERE source = "'+source+'"')
	result = self.cursor.fetchone()
	if not result:
	    return -1
	return result[0]

    def isDependencyAvailable(self,dependency):
	self.cursor.execute('SELECT iddependency FROM dependenciesreference WHERE dependency = (?)', (dependency,))
	result = self.cursor.fetchone()
	if not result:
	    return -1
	return result[0]

    def isKeywordAvailable(self,keyword):
	self.cursor.execute('SELECT idkeyword FROM keywordsreference WHERE keywordname = (?)', (keyword,))
	result = self.cursor.fetchone()
	if not result:
	    return -1
	return result[0]

    def isUseflagAvailable(self,useflag):
	self.cursor.execute('SELECT idflag FROM useflagsreference WHERE flagname = (?)', (useflag,))
	result = self.cursor.fetchone()
	if not result:
	    return -1
	return result[0]

    def isEclassAvailable(self,eclass):
	self.cursor.execute('SELECT idclass FROM eclassesreference WHERE classname = (?)', (eclass,))
	result = self.cursor.fetchone()
	if not result:
	    return -1
	return result[0]

    def isNeededAvailable(self,needed):
	self.cursor.execute('SELECT idneeded FROM neededreference WHERE library = (?)', (needed,))
	result = self.cursor.fetchone()
	if not result:
	    return -1
	return result[0]

    def isCounterAvailable(self,counter):
	result = False
	self.cursor.execute('SELECT counter FROM counters WHERE counter = (?)', (counter,))
        result = self.cursor.fetchone()
        if result:
	    result = True
	return result

    def isLicenseAvailable(self,pkglicense):
        if not pkglicense: # workaround for packages without a license but just garbage
            pkglicense = ' '
	self.cursor.execute('SELECT idlicense FROM licenses WHERE license = (?)', (pkglicense,))
	result = self.cursor.fetchone()
	if not result:
	    return -1
	return result[0]

    def isSystemPackage(self,idpackage):

	cache = self.fetchInfoCache(idpackage,'isSystemPackage')
	if cache != None: return cache

        try:
	    self.cursor.execute('SELECT idpackage FROM systempackages WHERE idpackage = (?)', (idpackage,))
        except: # FIXME: remove this for 1.0
            try:
                self.createSystemPackagesTable()
            except:
                # readonly database?
                return False
            self.cursor.execute('SELECT idpackage FROM systempackages WHERE idpackage = (?)', (idpackage,))
        
	result = self.cursor.fetchone()
	rslt = False
	if result:
	    rslt = True

	self.storeInfoCache(idpackage,'isSystemPackage',rslt)
	return rslt

    def isInjected(self,idpackage):

	cache = self.fetchInfoCache(idpackage,'isInjected')
	if cache != None: return cache

        try:
	    self.cursor.execute('SELECT idpackage FROM injected WHERE idpackage = (?)', (idpackage,))
        except: # FIXME: remove this for 1.0
            try:
                self.createInjectedTable()
            except:
                # readonly database?
                return False
            self.cursor.execute('SELECT idpackage FROM injected WHERE idpackage = (?)', (idpackage,))
        
	result = self.cursor.fetchone()
	rslt = False
	if result:
	    rslt = True

	self.storeInfoCache(idpackage,'isInjected',rslt)
	return rslt

    def areCompileFlagsAvailable(self,chost,cflags,cxxflags):
        
	self.cursor.execute('SELECT idflags FROM flags WHERE chost in (?) AND cflags in (?) AND cxxflags in (?)', (chost,cflags,cxxflags,))
        result = self.cursor.fetchone()
	if not result:
	    return -1
	return result[0]

    def searchBelongs(self, file, like = False, branch = None):
	
	branchstring = ''
        searchkeywords = [file]
	if branch:
            searchkeywords.append(branch)
	    branchstring = ' and baseinfo.branch = (?)'

	if (like):
	    self.cursor.execute('SELECT content.idpackage FROM content,baseinfo WHERE file LIKE (?) and content.idpackage = baseinfo.idpackage '+branchstring, searchkeywords)
	else:
	    self.cursor.execute('SELECT content.idpackage FROM content,baseinfo WHERE file = (?) and content.idpackage = baseinfo.idpackage '+branchstring, searchkeywords)

	return self.fetchall2set(self.cursor.fetchall())

    ''' search packages that uses the eclass provided '''
    def searchEclassedPackages(self, eclass, atoms = False): # atoms = return atoms directly
	if atoms:
	    self.cursor.execute('SELECT baseinfo.atom,eclasses.idpackage FROM baseinfo,eclasses,eclassesreference WHERE eclassesreference.classname = (?) and eclassesreference.idclass = eclasses.idclass and eclasses.idpackage = baseinfo.idpackage', (eclass,))
	    return self.cursor.fetchall()
	else:
	    self.cursor.execute('SELECT idpackage FROM baseinfo WHERE versiontag = in (?)', (eclass,))
	    return self.fetchall2set(self.cursor.fetchall())

    ''' search packages whose versiontag matches the one provided '''
    def searchTaggedPackages(self, tag, atoms = False): # atoms = return atoms directly
	if atoms:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE versiontag in (?)', (tag,))
	    return self.cursor.fetchall()
	else:
	    self.cursor.execute('SELECT idpackage FROM baseinfo WHERE versiontag = in (?)', (tag,))
	    return self.fetchall2set(self.cursor.fetchall())

    ''' search packages whose slot matches the one provided '''
    def searchSlottedPackages(self, slot, atoms = False): # atoms = return atoms directly
	if atoms:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE slot in (?)', (slot,))
	    return self.cursor.fetchall()
	else:
	    self.cursor.execute('SELECT idpackage FROM baseinfo WHERE slot = in (?)', (slot,))
	    return self.fetchall2set(self.cursor.fetchall())

    ''' search packages that need the specified library (in neededreference table) specified by keyword '''
    def searchNeeded(self, keyword, like = False):
        if like:
            self.cursor.execute('SELECT needed.idpackage FROM needed,neededreference WHERE library LIKE (?) and needed.idneeded = neededreference.idneeded', (keyword,))
        else:
            self.cursor.execute('SELECT needed.idpackage FROM needed,neededreference WHERE library = (?) and needed.idneeded = neededreference.idneeded', (keyword,))
	return self.fetchall2set(self.cursor.fetchall())

    # FIXME: deprecate and add functionalities to the function above
    ''' same as above but with branch support '''
    def searchNeededInBranch(self, keyword, branch):
	self.cursor.execute('SELECT needed.idpackage FROM needed,neededreference,baseinfo WHERE library = (?) and needed.idneeded = neededreference.idneeded and baseinfo.branch = (?)', (keyword,branch,))
	return self.fetchall2set(self.cursor.fetchall())

    ''' search dependency string inside dependenciesreference table and retrieve iddependency '''
    def searchDependency(self, dep, like = False, multi = False):
        sign = "="
        if like:
            sign = "LIKE"
            dep = "%"+dep+"%"
        self.cursor.execute('SELECT iddependency FROM dependenciesreference WHERE dependency '+sign+' (?)', (dep,))
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

    def searchPackages(self, keyword, sensitive = False, slot = None, tag = None, branch = None):
	
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
	
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo WHERE atom LIKE (?)'+slotstring+tagstring+branchstring, searchkeywords)
	else:
	    self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo WHERE LOWER(atom) LIKE (?)'+slotstring+tagstring+branchstring, searchkeywords)
	return self.cursor.fetchall()

    def searchProvide(self, keyword, slot = None, tag = None, branch = None):

	self.cursor.execute('SELECT idpackage FROM provide WHERE atom = (?)', (keyword,))
	idpackage = self.cursor.fetchone()
	if not idpackage:
	    return ()

	slotstring = ''
        searchkeywords = [idpackage[0]]
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

	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE idpackage = (?)'+slotstring+tagstring+branchstring, searchkeywords)
	return self.cursor.fetchall()

    def searchPackagesByDescription(self, keyword):
	self.cursor.execute('SELECT idpackage FROM extrainfo WHERE LOWER(description) LIKE (?)', ("%"+keyword.lower()+"%",))
	idpkgs = self.fetchall2set(self.cursor.fetchall())
	if not idpkgs:
	    return ()

	result = set()
	query = 'WHERE idpackage = '
	counter = 0
	run = False
	for idpkg in idpkgs:
	    run = True
	    counter += 1
	    query += str(idpkg)+' OR idpackage = '
	    if counter > 25:
		counter = 0
		query = query[:-16]
		self.cursor.execute('SELECT atom,idpackage FROM baseinfo '+query)
		qry = self.cursor.fetchall()
		for x in qry:
		    result.add(x)
		query = 'WHERE idpackage = '
		run = False
	
	if (run):
	    query = query[:-16]
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo '+query)
	    qry = self.cursor.fetchall()
	    for x in qry:
		result.add(x)
	
	return result

    def searchPackagesByName(self, keyword, sensitive = False, branch = None):
	
	if (self.xcache):
	    cached = self.fetchSearchCache((keyword,sensitive,branch),'searchPackagesByName')
	    if cached != None: return cached
	
        if sensitive:
            searchkeywords = [keyword]
        else:
            searchkeywords = [keyword.lower()]
	branchstring = ''
	if branch:
            searchkeywords.append(branch)
	    branchstring = ' and branch = (?)'
	
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = (?)'+branchstring, searchkeywords)
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = (?)'+branchstring, searchkeywords)
	
	results = self.cursor.fetchall()
	if (self.xcache):
	    self.storeSearchCache((keyword,sensitive,branch),'searchPackagesByName',results)
	return results


    def searchPackagesByCategory(self, keyword, like = False, branch = None):
	
	if (self.xcache):
	    cached = self.fetchSearchCache((keyword,branch),'searchPackagesByCategory')
	    if cached != None: return cached
	
        searchkeywords = [keyword]
	branchstring = ''
	if branch:
            searchkeywords.append(branch)
	    branchstring = ' and branch = (?)'
	
        if like:
            self.cursor.execute('SELECT baseinfo.atom,baseinfo.idpackage FROM baseinfo,categories WHERE categories.category LIKE (?) and baseinfo.idcategory = categories.idcategory '+branchstring, searchkeywords)
        else:
            self.cursor.execute('SELECT baseinfo.atom,baseinfo.idpackage FROM baseinfo,categories WHERE categories.category = (?) and baseinfo.idcategory = categories.idcategory '+branchstring, searchkeywords)
	
	results = self.cursor.fetchall()
	if (self.xcache):
	    self.storeSearchCache((keyword,branch),'searchPackagesByCategory',results)
	return results

    def searchPackagesByNameAndCategory(self, name, category, sensitive = False, branch = None):
	
	if (self.xcache):
	    cached = self.fetchSearchCache((name,category,sensitive,branch),'searchPackagesByNameAndCategory')
	    if cached != None: return cached
	
	# get category id
	idcat = -1
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = (?)', (category,))
	idcat = self.cursor.fetchone()
	if not idcat:
	    return ()
	else:
	    idcat = idcat[0]

        searchkeywords = []
        if sensitive:
            searchkeywords.append(name)
        else:
            searchkeywords.append(name.lower())
        
        searchkeywords.append(idcat)
        
	branchstring = ''
	if branch:
            searchkeywords.append(branch)
	    branchstring = ' and branch = (?)'

	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = (?) AND idcategory = (?) '+branchstring, searchkeywords)
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = (?) AND idcategory = (?) '+branchstring, searchkeywords)
	
	results = self.cursor.fetchall()
	if (self.xcache):
	    self.storeSearchCache((name,category,sensitive,branch),'searchPackagesByNameAndCategory',results)
	return results

    def searchPackagesByNameAndVersionAndCategory(self, name, version, category, branch = None, sensitive = False):
	
	if (self.xcache):
	    cached = self.fetchSearchCache((name,version,category,branch,sensitive),'searchPackagesByNameAndVersionAndCategory')
	    if cached != None: return cached
	
	# get category id
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = (?)', (category,))
	idcat = self.cursor.fetchone()
	if not idcat:
	    return ()
	else:
	    idcat = idcat[0]

        searchkeywords = []
        if sensitive:
            searchkeywords.append(name)
        else:
            searchkeywords.append(name.lower())
        
        searchkeywords.append(version)
        searchkeywords.append(idcat)

	branchstring = ''
	if branch:
            searchkeywords.append(branch)
	    branchstring = ' and branch = (?)'

	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = (?) and version = (?) and idcategory = (?) '+branchstring, searchkeywords)
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = (?) and version = (?) and idcategory =  (?) '+branchstring, searchkeywords)

	results = self.cursor.fetchall()
	if (self.xcache):
	    self.storeSearchCache((name,version,category,branch,sensitive),'searchPackagesByNameAndVersionAndCategory',results)
	return results

    def listAllPackages(self):
	self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo')
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
                results.add((download,injected))
        return results

    def listAllCounters(self, onlycounters = False):
        if onlycounters:
            self.cursor.execute('SELECT counter FROM counters')
            return self.fetchall2set(self.cursor.fetchall())
        else:
            self.cursor.execute('SELECT counter,idpackage FROM counters')
            return self.cursor.fetchall()

    def listAllIdpackages(self, branch = None):
	branchstring = ''
        searchkeywords = []
	if branch:
            searchkeywords.append(branch)
	    branchstring = ' where branch = (?)'
	self.cursor.execute('SELECT idpackage FROM baseinfo'+branchstring, searchkeywords)
	return self.fetchall2set(self.cursor.fetchall())

    def listAllDependencies(self):
	self.cursor.execute('SELECT * FROM dependenciesreference')
	return self.cursor.fetchall()

    def listAllBranches(self):

	if (self.xcache):
	    cached = self.fetchSearchCache((None,),'listAllBranches')
	    if cached != None: return cached

	self.cursor.execute('SELECT branch FROM baseinfo')
        results = self.fetchall2set(self.cursor.fetchall())

	if (self.xcache):
	    self.storeSearchCache((None,),'listAllBranches',results)
	return results

    def listIdPackagesInIdcategory(self,idcategory):
	self.cursor.execute('SELECT idpackage FROM baseinfo where idcategory = (?)', (idcategory,))
	return self.fetchall2set(self.cursor.fetchall())

    def listIdpackageDependencies(self, idpackage):
	self.cursor.execute('SELECT iddependency FROM dependencies where idpackage = (?)', (idpackage,))
	iddeps = self.fetchall2set(self.cursor.fetchall())
	if not iddeps:
	    return ()
	
	result = set()
	query = 'WHERE iddependency = '
	counter = 0
	run = False
	for iddep in iddeps:
	    run = True
	    counter += 1
	    query += str(iddep)+' OR iddependency = '
	    if counter > 25:
		counter = 0
		query = query[:-19]
		self.cursor.execute('SELECT iddependency,dependency FROM dependenciesreference '+query)
		qry = self.cursor.fetchall()
		for x in qry:
		    result.add(x)
		query = 'WHERE iddependency = '
		run = False
	
	if (run):
	    query = query[:-19]
	    self.cursor.execute('SELECT iddependency,dependency FROM dependenciesreference '+query)
	    qry = self.cursor.fetchall()
	    for x in qry:
		result.add(x)

	return result

    def listBranchPackagesTbz2(self, branch):
        result = set()
        pkglist = self.listBranchPackages(branch)
        for pkg in pkglist:
	    idpackage = pkg[1]
	    url = self.retrieveDownloadURL(idpackage)
	    if url:
		result.add(os.path.basename(url))
	if (result):
            result = list(result)
	    result.sort()
	return result

    def listBranchPackages(self, branch):
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE branch = (?)', (branch,))
	return self.cursor.fetchall()

    def listAllFiles(self, clean = False):
	self.cursor.execute('SELECT file FROM content')
	if clean:
	    return self.fetchall2set(self.cursor.fetchall())
	else:
	    return self.fetchall2list(self.cursor.fetchall())

    def listAllCategories(self):
	self.cursor.execute('SELECT idcategory,category FROM categories')
	return self.cursor.fetchall()

    def listConfigProtectDirectories(self, mask = False):
	dirs = set()
	query = 'SELECT idprotect FROM configprotect'
	if mask:
	    query += 'mask'
	try:
	    self.cursor.execute(query)
	except:
	    self.createProtectTable()
	    self.cursor.execute(query)
	idprotects = self.fetchall2set(self.cursor.fetchall())
	
	if not idprotects:
	    return []
	
	results = set()
	query = 'WHERE idprotect = '
	counter = 0
	run = False
	for idprotect in idprotects:
	    run = True
	    counter += 1
	    query += str(idprotect)+' OR idprotect = '
	    if counter > 25:
		counter = 0
		query = query[:-16]
		self.cursor.execute('SELECT protect FROM configprotectreference '+query)
		results.update(self.fetchall2set(self.cursor.fetchall()))
		query = 'WHERE idprotect = '
		run = False
	
	if (run):
	    query = query[:-16]
	    self.cursor.execute('SELECT protect FROM configprotectreference '+query)
	    results.update(self.fetchall2set(self.cursor.fetchall()))
	
	for result in results:
	    for x in result.split():
		dirs.add(x)
	dirs = list(dirs)
	dirs.sort()
	return dirs
    
    def switchBranch(self, idpackage, tobranch):

	mycat = self.retrieveCategory(idpackage)
	myname = self.retrieveName(idpackage)
	myslot = self.retrieveSlot(idpackage)
	mybranch = self.retrieveBranch(idpackage)
	mydownload = self.retrieveDownloadURL(idpackage)
	import re
	out = re.subn('/'+mybranch+'/','/'+tobranch+'/',mydownload)
	newdownload = out[0]
	
	# remove package with the same key+slot and tobranch if exists
	match = self.atomMatch(mycat+"/"+myname, matchSlot = myslot, matchBranches = (tobranch,))
	if match[0] != -1:
	    self.removePackage(match[0])
	
	# now switch selected idpackage to the new branch
	self.cursor.execute('UPDATE baseinfo SET branch = (?) WHERE idpackage = (?)', (tobranch,idpackage,))
	self.cursor.execute('UPDATE extrainfo SET download = (?) WHERE idpackage = (?)', (newdownload,idpackage,))
	self.commitChanges()
        


########################################################
####
##   Client Database API / but also used by server part
#

    def addPackageToInstalledTable(self, idpackage, repositoryName):
	self.cursor.execute(
		'INSERT into installedtable VALUES '
		'(?,?)'
		, (	idpackage,
			repositoryName,
			)
	)
	self.commitChanges()

    def retrievePackageFromInstalledTable(self, idpackage):
	result = 'Not available'
	try:
	    self.cursor.execute('SELECT repositoryname FROM installedtable WHERE idpackage = (?)', (idpackage,))
	    return self.cursor.fetchone()[0] # it's ok because it's inside try/except
	except:
	    pass
	return result

    def removePackageFromInstalledTable(self, idpackage):
	try:
	    self.cursor.execute('DELETE FROM installedtable WHERE idpackage = (?)', (idpackage,))
	    self.commitChanges()
	except:
	    self.createInstalledTable()

    def removePackageFromDependsTable(self, idpackage):
	try:
	    self.cursor.execute('DELETE FROM dependstable WHERE idpackage = (?)', (idpackage,))
	    self.commitChanges()
	    return 0
	except:
	    return 1 # need reinit

    def removeDependencyFromDependsTable(self, iddependency):
	try:
	    self.cursor.execute('DELETE FROM dependstable WHERE iddependency = (?)',(iddependency,))
	    self.commitChanges()
	    return 0
	except:
	    return 1 # need reinit

    # temporary/compat functions
    def createDependsTable(self):
	self.cursor.execute('DROP TABLE IF EXISTS dependstable;')
	self.cursor.execute('CREATE TABLE dependstable ( iddependency INTEGER PRIMARY KEY, idpackage INTEGER );')
	# this will be removed when dependstable is refilled properly
	self.cursor.execute(
		'INSERT into dependstable VALUES '
		'(?,?)'
		, (	-1,
			-1,
			)
	)
	self.commitChanges()

    def sanitizeDependsTable(self):
	self.cursor.execute('DELETE FROM dependstable where iddependency = -1')
	self.commitChanges()

    def isDependsTableSane(self):
	try:
	    self.cursor.execute('SELECT iddependency FROM dependstable WHERE iddependency = -1')
	except:
	    return False # table does not exist, please regenerate and re-run
        status = self.cursor.fetchone()
        if status:
            return False
        
        # also check that dependenciesreference length matches dependstable length
        self.cursor.execute('select count(*) from dependenciesreference')
        dependenciesreference_count = self.cursor.fetchone()
        self.cursor.execute('select count(*) from dependstable')
        dependstable_count = self.cursor.fetchone()
        if dependenciesreference_count and dependstable_count:
            try:
                if dependenciesreference_count[0] == dependstable_count[0]:
                    return True
                else:
                    return False
            except:
                return False

        return False

    def createXpakTable(self):
        self.cursor.execute('CREATE TABLE xpakdata ( idpackage INTEGER PRIMARY KEY, data BLOB );')
        self.commitChanges()

    def storeXpakMetadata(self, idpackage, blob):
	self.cursor.execute(
		'INSERT into xpakdata VALUES '
		'(?,?)', ( int(idpackage), buffer(blob), )
        )
        self.commitChanges()

    def retrieveXpakMetadata(self, idpackage):
        try:
            self.cursor.execute('SELECT data from xpakdata where idpackage = (?)', (idpackage,))
            mydata = self.cursor.fetchone()
            if not mydata:
                return ""
            else:
                return mydata[0]
        except:
            return ""
            pass

    def createCountersTable(self):
        self.cursor.execute('DROP TABLE IF EXISTS counters;')
        self.cursor.execute('CREATE TABLE counters ( counter INTEGER PRIMARY KEY, idpackage INTEGER );')
        self.commitChanges()

    def createContentIndex(self):
        if self.dbname != "etpdb" and self.indexing:
            self.cursor.execute('CREATE INDEX IF NOT EXISTS contentindex ON content ( file )')

    def createBaseinfoIndex(self):
        if self.dbname != "etpdb" and self.indexing:
            self.cursor.execute('CREATE INDEX IF NOT EXISTS baseindex ON baseinfo ( idpackage, atom, name, version, slot, branch, revision )')

    def createDependenciesIndex(self):
        if self.dbname != "etpdb" and self.indexing:
            self.cursor.execute('CREATE INDEX IF NOT EXISTS dependenciesindex ON dependencies ( idpackage, iddependency )')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS dependenciesreferenceindex ON dependenciesreference ( iddependency, dependency )')

    def createExtrainfoIndex(self):
        if self.dbname != "etpdb" and self.indexing:
            self.cursor.execute('CREATE INDEX IF NOT EXISTS extrainfoindex ON extrainfo ( idpackage, description, homepage, download, digest, datecreation, size )')

    def regenerateCountersTable(self, output = False):
        self.createCountersTable()
        # assign a counter to an idpackage
        try:
            from portageTools import getPortageAppDbPath # only if Portage is found
        except:
            return
        appdbpath = getPortageAppDbPath()
        myids = self.listAllIdpackages()
        for myid in myids:
            # get atom
            myatom = self.retrieveAtom(myid)
            myatom = entropyTools.remove_tag(myatom)
            myatomcounterpath = appdbpath+myatom+"/"+dbCOUNTER
            if os.path.isfile(myatomcounterpath):
                try:
                    f = open(myatomcounterpath,"r")
                    counter = int(f.readline().strip())
                    f.close()
                except:
                    if output: print "Attention: Cannot open Gentoo counter file for: "+myatom
                    continue
                # insert id+counter
                try:
                    self.cursor.execute(
                            'INSERT into counters VALUES '
                            '(?,?)', ( counter, myid, )
                    )
                except:
                    if output: print "Attention: counter for atom "+str(myatom)+" is duplicated. Ignoring."
                    continue # don't trust counters, they might not be unique

    def clearTreeupdatesEntries(self, repository):
        # treeupdates
        try:
            self.cursor.execute("DELETE FROM treeupdates WHERE repository = (?)", (repository,))
        except:
            self.createTreeupdatesTable()

    #
    # FIXME: remove these when 1.0 will be out
    #
    
    def createTreeupdatesTable(self):
	self.cursor.execute('DROP TABLE IF EXISTS treeupdates;')
	self.cursor.execute('CREATE TABLE treeupdates ( repository VARCHAR PRIMARY KEY, digest VARCHAR );')
	self.commitChanges()
    
    def createTreeupdatesactionsTable(self):
	self.cursor.execute('DROP TABLE IF EXISTS treeupdatesactions;')
	self.cursor.execute('CREATE TABLE treeupdatesactions ( idupdate INTEGER PRIMARY KEY, repository VARCHAR, command VARCHAR );')
	self.commitChanges()
    
    def createSizesTable(self):
	self.cursor.execute('DROP TABLE IF EXISTS sizes;')
	self.cursor.execute('CREATE TABLE sizes ( idpackage INTEGER, size INTEGER );')
	self.commitChanges()

    def createContentTypeColumn(self):
        try: # if database disk image is malformed, won't raise exception here
            self.cursor.execute('ALTER TABLE content ADD COLUMN type VARCHAR;')
            self.cursor.execute('UPDATE content SET type = "0"')
        except:
            pass
	self.commitChanges()

    def createTriggerTable(self):
	self.cursor.execute('CREATE TABLE triggers ( idpackage INTEGER PRIMARY KEY, data BLOB );')
	self.commitChanges()

    def createTriggerColumn(self):
	self.cursor.execute('ALTER TABLE baseinfo ADD COLUMN trigger INTEGER;')
	self.cursor.execute('UPDATE baseinfo SET trigger = 0')
	self.commitChanges()

    def createEclassesTable(self):
	self.cursor.execute('DROP TABLE IF EXISTS eclasses;')
	self.cursor.execute('DROP TABLE IF EXISTS eclassesreference;')
	self.cursor.execute('CREATE TABLE eclasses ( idpackage INTEGER, idclass INTEGER );')
	self.cursor.execute('CREATE TABLE eclassesreference ( idclass INTEGER PRIMARY KEY, classname VARCHAR );')
	self.commitChanges()

    def createNeededTable(self):
	self.cursor.execute('DROP TABLE IF EXISTS needed;')
	self.cursor.execute('DROP TABLE IF EXISTS neededreference;')
	self.cursor.execute('CREATE TABLE needed ( idpackage INTEGER, idneeded INTEGER );')
	self.cursor.execute('CREATE TABLE neededreference ( idneeded INTEGER PRIMARY KEY, library VARCHAR );')
	self.commitChanges()
    
    def createSystemPackagesTable(self):
        self.cursor.execute('CREATE TABLE systempackages ( idpackage INTEGER PRIMARY KEY );')
	self.commitChanges()
    
    def createInjectedTable(self):
        self.cursor.execute('CREATE TABLE injected ( idpackage INTEGER PRIMARY KEY );')
	self.commitChanges()
    
    def createProtectTable(self):
	self.cursor.execute('DROP TABLE IF EXISTS configprotect;')
	self.cursor.execute('DROP TABLE IF EXISTS configprotectmask;')
	self.cursor.execute('DROP TABLE IF EXISTS configprotectreference;')
	self.cursor.execute('CREATE TABLE configprotect ( idpackage INTEGER PRIMARY KEY, idprotect INTEGER );')
	self.cursor.execute('CREATE TABLE configprotectmask ( idpackage INTEGER PRIMARY KEY, idprotect INTEGER );')
	self.cursor.execute('CREATE TABLE configprotectreference ( idprotect INTEGER PRIMARY KEY, protect VARCHAR );')
	self.commitChanges()

    def createInstalledTable(self):
	self.cursor.execute('DROP TABLE IF EXISTS installedtable;')
	self.cursor.execute('CREATE TABLE installedtable ( idpackage INTEGER PRIMARY KEY, repositoryname VARCHAR );')
	self.commitChanges()

    def addDependRelationToDependsTable(self, iddependency, idpackage):
	self.cursor.execute(
		'INSERT into dependstable VALUES '
		'(?,?)'
		, (	iddependency,
			idpackage,
			)
	)
        if etpConst['uid'] == 0 and self.dbname == "etpdb": # force commit even if readonly, this will allow to automagically fix dependstable server side
            self.connection.commit()                        # we don't care much about syncing the database since it's quite trivial
	self.commitChanges()

    '''
       @description: recreate dependstable table in the chosen database, it's used for caching searchDepends requests
       @input Nothing
       @output: Nothing
    '''
    def regenerateDependsTable(self, output = True):
        self.createDependsTable()
        depends = self.listAllDependencies()
        count = 0
        total = str(len(depends))
        for depend in depends:
	    count += 1
	    atom = depend[1]
	    iddep = depend[0]
	    if output:
	        print_info("  "+bold("(")+darkgreen(str(count))+"/"+blue(total)+bold(")")+red(" Resolving ")+bold(atom), back = True)
	    match = self.atomMatch(atom)
	    if (match[0] != -1):
	        self.addDependRelationToDependsTable(iddep,match[0])
        del depends
        
        # now validate dependstable
        self.sanitizeDependsTable()


########################################################
####
##   Dependency handling functions
#

    def atomMatchFetchCache(self, atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter):
        if (self.xcache):
            try:
                cache_tuple = (atom,matchSlot,matchTag,multiMatch,caseSensitive,matchBranches,packagesFilter)
                cached = dbCacheStore[etpCache['dbMatch']+self.dbname].get((cache_tuple))
                if cached:
                    return cached
                else:
                    return None
            except KeyError: # issues with dictionaries?
                return None
        else:
            return None

    def atomMatchStoreCache(self, result, atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter):
        try:
            #print "CACHING",result,atom,self.dbname
            cache_tuple = (atom,matchSlot,matchTag,multiMatch,caseSensitive,matchBranches,packagesFilter)
            dbCacheStore[etpCache['dbMatch']+self.dbname][cache_tuple] = result
        except KeyError: # againnn, issues with dicts??
            pass

    # function that validate one atom by reading keywords settings
    # idpackageValidatorCache = {} >> function cache
    def idpackageValidator(self,idpackage):
        
        reponame = self.dbname[5:]
        cached = idpackageValidatorCache.get((idpackage,reponame))
        if cached != None: return cached
        
        # check if package.mask need it masked
        for atom in etpConst['packagemasking']['mask']:
            matches = self.atomMatch(atom, multiMatch = True, packagesFilter = False)
            if idpackage in matches[0]:
                # sorry, masked
                idpackageValidatorCache[(idpackage,reponame)] = -1
                return -1
        
        mykeywords = self.retrieveKeywords(idpackage)
        # XXX WORKAROUND
        if not mykeywords: mykeywords = [''] # ** is fine then
        # firstly, check if package keywords are in etpConst['keywords'] (universal keywords have been merged from package.mask)
        for key in etpConst['keywords']:
            if key in mykeywords:
                # found! all fine
                idpackageValidatorCache[(idpackage,reponame)] = idpackage
                return idpackage
        
        #### IT IS MASKED!!
        
        # see if we can unmask by just lookin into package.unmask stuff -> etpConst['packagemasking']['unmask']
        for atom in etpConst['packagemasking']['unmask']:
            matches = self.atomMatch(atom, multiMatch = True, packagesFilter = False)
            if idpackage in matches[0]:
                idpackageValidatorCache[(idpackage,reponame)] = idpackage
                return idpackage
        
        # if we get here, it means we didn't find mykeywords in etpConst['keywords'], we need to seek etpConst['packagemasking']['keywords']
        # seek in repository first
        if reponame in etpConst['packagemasking']['keywords']['repositories']:
            for keyword in etpConst['packagemasking']['keywords']['repositories'][reponame]:
                if keyword in mykeywords:
                    keyword_data = etpConst['packagemasking']['keywords']['repositories'][reponame].get(keyword)
                    for atom in keyword_data:
                        if atom == "*": # all packages in this repo with keyword "keyword" are ok
                            return idpackage
                        matches = self.atomMatch(atom, multiMatch = True, packagesFilter = False)
                        if idpackage in matches[0]:
                            idpackageValidatorCache[(idpackage,reponame)] = idpackage
                            return idpackage

        # if we get here, it means we didn't find a match in repositories
        # so we scan packages, last chance
        for keyword in etpConst['packagemasking']['keywords']['packages']:
            # first of all check if keyword is in mykeywords
            if keyword in mykeywords:
                #print "found",keyword
                keyword_data = etpConst['packagemasking']['keywords']['packages'].get(keyword)
                # check for relation
                for atom in keyword_data:
                    # match atom
                    matches = self.atomMatch(atom, multiMatch = True, packagesFilter = False)
                    if idpackage in matches[0]:
                        # valid!
                        idpackageValidatorCache[(idpackage,reponame)] = idpackage
                        return idpackage
        
        # holy crap, can't validate
        idpackageValidatorCache[(idpackage,reponame)] = -1
        return -1

    # packages filter used by atomMatch, input must me foundIDs, a list like this:
    # [(u'x11-libs/qt-4.3.2', 608), (u'x11-libs/qt-3.3.8-r4', 1867)]
    def packagesFilter(self,results):
        
        # keywordsFilter ONLY FILTERS results if self.dbname.startswith(etpConst['dbnamerepoprefix']), repository database is open
        if not self.dbname.startswith(etpConst['dbnamerepoprefix']):
            return results

        newresults = []
        for item in results:
            rc = self.idpackageValidator(item[1])
            if rc != -1:
                newresults.append(item)
        
        return newresults

    '''
       @description: matches the user chosen package name+ver, if possibile, in a single repository
       @input atom: string, atom to match
       @input caseSensitive: bool, should the atom be parsed case sensitive?
       @input matchSlot: string, match atoms with the provided slot
       @input multiMatch: bool, return all the available atoms
       @input matchBranches: tuple or list, match packages only in the specified branches
       @input matchTag: match packages only for the specified tag
       @input packagesFilter: enable/disable package.mask/.keywords/.unmask filter
       @output: the package id, if found, otherwise -1 plus the status, 0 = ok, 1 = not found, 2 = need more info, 3 = cannot use direction without specifying version
    '''
    def atomMatch(self, atom, caseSensitive = True, matchSlot = None, multiMatch = False, matchBranches = (), matchTag = None, packagesFilter = True):

        cached = self.atomMatchFetchCache(atom,caseSensitive,matchSlot,multiMatch,matchBranches,matchTag,packagesFilter)
        if cached != None:
            return cached
	
	# check if tag is provided -> app-foo/foo-1.2.3:SLOT|TAG or app-foo/foo-1.2.3|TAG
	atomTag = entropyTools.dep_gettag(atom)
	atomSlot = entropyTools.dep_getslot(atom)

	scan_atom = entropyTools.remove_tag(atom)
	if (matchTag == None) and (atomTag != None):
	    matchTag = atomTag
	
	# check if slot is provided -> app-foo/foo-1.2.3:SLOT
	scan_atom = entropyTools.remove_slot(scan_atom)
	if (matchSlot == None) and (atomSlot != None):
	    matchSlot = atomSlot

        # check for direction
        strippedAtom = entropyTools.dep_getcpv(scan_atom)
        if scan_atom[-1] == "*":
	    strippedAtom += "*"
        direction = scan_atom[0:len(scan_atom)-len(strippedAtom)]
	
        justname = entropyTools.isjustname(strippedAtom)
        pkgversion = ''
        if (not justname):
	    
	    # FIXME: deprecated - will be removed soonly
            if strippedAtom.split("-")[-1][0] == "t":
                strippedAtom = '-t'.join(strippedAtom.split("-t")[:-1])
	    
	    # get version
	    data = entropyTools.catpkgsplit(strippedAtom)
	    if data == None:
	        return -1,3 # atom is badly formatted
	    pkgversion = data[2]+"-"+data[3]
	    
	    # FIXME: deprecated - will be removed soonly
	    if not matchTag:
	        if scan_atom.split("-")[-1].startswith("t"):
	            matchTag = scan_atom.split("-")[-1]
	
        pkgkey = entropyTools.dep_getkey(strippedAtom)
	splitkey = pkgkey.split("/")
        if (len(splitkey) == 2):
            pkgname = splitkey[1]
            pkgcat = splitkey[0]
        else:
            pkgname = splitkey[0]
	    pkgcat = "null"

	if (matchBranches):
	    myBranchIndex = tuple(matchBranches) # force to tuple for security
	else:
	    if (self.dbname == 'client'):
		# collect all available branches
		myBranchIndex = tuple(self.listAllBranches())
	    else:
	        myBranchIndex = (etpConst['branch'],)

        # IDs found in the database that match our search
        foundIDs = []
        
        for idx in myBranchIndex:
	    results = self.searchPackagesByName(pkgname, sensitive = caseSensitive, branch = idx)
	    
            mypkgcat = pkgcat
	    mypkgname = pkgname
            
            virtual = False
	    # if it's a PROVIDE, search with searchProvide
            # there's no package with that name
	    if (not results) and (mypkgcat == "virtual"):
	        virtuals = self.searchProvide(pkgkey, branch = idx)
		if (virtuals):
                    virtual = True
		    mypkgname = self.retrieveName(virtuals[0][1])
		    mypkgcat = self.retrieveCategory(virtuals[0][1])
		    results = virtuals

	    # now validate
	    if (not results):
	        continue # search into a stabler branch
	
	    elif (len(results) > 1):

	        # if it's because category differs, it's a problem
	        foundCat = ""
	        cats = set()
	        for result in results:
		    idpackage = result[1]
		    cat = self.retrieveCategory(idpackage)
		    cats.add(cat)
		    if (cat == mypkgcat) or ((not virtual) and (mypkgcat == "virtual") and (cat == mypkgcat)): # in case of virtual packages only (that they're not stored as provide)
		        foundCat = cat

                # if we found something at least...
	        if (not foundCat) and (len(cats) == 1) and (mypkgcat in ("virtual","null")):
		    foundCat = list(cats)[0]
	        if (not foundCat):
		    # got the issue
		    # gosh, return and complain
                    self.atomMatchStoreCache((-1,2), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
		    return -1,2
	
	        # we can use foundCat
	        mypkgcat = foundCat

	        # we need to search using the category
		if (not multiMatch):
	            results = self.searchPackagesByNameAndCategory(name = mypkgname, category = mypkgcat, branch = idx, sensitive = caseSensitive)
	        # validate again
	        if (not results):
		    continue  # search into another branch
	
	        # if we get here, we have found the needed IDs
	        foundIDs = results
	        break

	    else:
                
                # if mypkgcat is virtual, we can force
                if (mypkgcat == "virtual") and (not virtual): # in case of virtual packages only (that they're not stored as provide)
                    mypkgcat = entropyTools.dep_getkey(results[0][0]).split("/")[0]
                
		# check if category matches
		if mypkgcat != "null":
		    foundCat = self.retrieveCategory(results[0][1])
		    if mypkgcat == foundCat:
			foundIDs.append(results[0])
		    else:
			continue
		else:
	            foundIDs.append(results[0])
	            break
        
        if packagesFilter: # keyword filtering
            foundIDs = self.packagesFilter(foundIDs)

        if (foundIDs):
	    # now we have to handle direction
	    if (direction) or (direction == '' and not justname) or (direction == '' and not justname and strippedAtom.endswith("*")):
	        # check if direction is used with justname, in this case, return an error
	        if (justname):
		    #print "justname"
                    self.atomMatchStoreCache((-1,3), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
		    return -1,3 # error, cannot use directions when not specifying version
	    
	        if (direction == "~") or (direction == "=") or (direction == '' and not justname) or (direction == '' and not justname and strippedAtom.endswith("*")): # any revision within the version specified OR the specified version
		
		    if (direction == '' and not justname):
		        direction = "="
		
		    #print direction+" direction"
		    # remove revision (-r0 if none)
		    if (direction == "="):
		        if (pkgversion.split("-")[-1] == "r0"):
                            pkgversion = "-".join(pkgversion.split("-")[:-1])
		    if (direction == "~"):
		        pkgversion = entropyTools.remove_revision(pkgversion)
		
		    #print pkgversion
		    dbpkginfo = []
		    for data in foundIDs:
		        idpackage = data[1]
		        dbver = self.retrieveVersion(idpackage)
		        if (direction == "~"):
			    myver = entropyTools.remove_revision(dbver)
                            if myver == pkgversion:
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        else:
			    # media-libs/test-1.2* support
			    if pkgversion[-1] == "*":
			        if dbver.startswith(pkgversion[:-1]):
				    dbpkginfo.append([idpackage,dbver])
			    else:
				# do versions matches?
				if pkgversion == dbver:
				    dbpkginfo.append([idpackage,dbver])

		    if (not dbpkginfo):
                        self.atomMatchStoreCache((-1,1), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
		        return -1,1
		
		    versions = []
		    for x in dbpkginfo:
			if (matchSlot != None):
			    mslot = self.retrieveSlot(x[0])
			    if (str(mslot) != str(matchSlot)):
				continue
			if (matchTag != None):
			    if matchTag != self.retrieveVersionTag(x[0]):
				continue
		        versions.append(x[1])
		
		    if (not versions):
                        self.atomMatchStoreCache((-1,1), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
			return -1,1
		
		    # who is newer ?
		    versionlist = entropyTools.getNewerVersion(versions)
		    newerPackage = dbpkginfo[versions.index(versionlist[0])]
		
	            # now look if there's another package with the same category, name, version, but different tag
	            newerPkgName = self.retrieveName(newerPackage[0])
	            newerPkgCategory = self.retrieveCategory(newerPackage[0])
	            newerPkgVersion = self.retrieveVersion(newerPackage[0])
		    newerPkgBranch = self.retrieveBranch(newerPackage[0])
	            similarPackages = self.searchPackagesByNameAndVersionAndCategory(name = newerPkgName, version = newerPkgVersion, category = newerPkgCategory, branch = newerPkgBranch)
		    
		    if (multiMatch):
                        # filter only valid keywords
                        similarPackages = set([x[1] for x in similarPackages])
                        self.atomMatchStoreCache((similarPackages,0), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
			return similarPackages,0
		    
		    #print newerPackage
		    #print similarPackages
	            if (len(similarPackages) > 1):
		        # gosh, there are packages with the same name, version, category
		        # we need to parse version tag
		        versionTags = []
		        for pkg in similarPackages:
		            versionTags.append(self.retrieveVersionTag(pkg[1]))
			versiontaglist = entropyTools.getNewerVersionTag(versionTags)
		        newerPackage = similarPackages[versionTags.index(versiontaglist[0])]
                        newerPackage = newerPackage[1],None # so will return correctly
		
                    # filter only valid keywords
                    self.atomMatchStoreCache((newerPackage[0],0), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
		    return newerPackage[0],0

	        elif (direction.find(">") != -1) or (direction.find("<") != -1):
		
		    #print direction+" direction"
		    # remove revision (-r0 if none)
		    if pkgversion.split("-")[-1] == "r0":
		        # remove
                        pkgversion = '-'.join(pkgversion.split("-")[:-1])

		    dbpkginfo = []
		    for data in foundIDs:
		        idpackage = data[1]
		        dbver = self.retrieveVersion(idpackage)
		        pkgcmp = entropyTools.compareVersions(pkgversion,dbver)
		        if direction == ">": # the --deep mode should really act on this
		            if (pkgcmp < 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        elif direction == "<":
		            if (pkgcmp > 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        elif direction == ">=": # the --deep mode should really act on this
		            if (pkgcmp <= 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        elif direction == "<=":
		            if (pkgcmp >= 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		
		    if (not dbpkginfo):
		        # this version is not available
                        self.atomMatchStoreCache((-1,1), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
		        return -1,1
		
		    versions = []
		    multiMatchList = set()
		    _dbpkginfo = []
		    for x in dbpkginfo:
			if (matchSlot != None):
			    mslot = self.retrieveSlot(x[0])
			    if (str(matchSlot) != str(mslot)):
				continue
			if (matchTag != None):
			    if matchTag != self.retrieveVersionTag(x[0]):
				continue
			if (multiMatch):
			    multiMatchList.add(x[0])
		        versions.append(x[1])
			_dbpkginfo.append(x)
		    dbpkginfo = _dbpkginfo
		    
		    if (multiMatch):
                        self.atomMatchStoreCache((multiMatchList,0), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
			return multiMatchList,0

		    if (not versions):
                        self.atomMatchStoreCache((-1,1), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
			return -1,1

		    # who is newer ?
		    versionlist = entropyTools.getNewerVersion(versions)
		    newerPackage = dbpkginfo[versions.index(versionlist[0])]
		
	            # now look if there's another package with the same category, name, version, but different tag
	            newerPkgName = self.retrieveName(newerPackage[0])
	            newerPkgCategory = self.retrieveCategory(newerPackage[0])
	            newerPkgVersion = self.retrieveVersion(newerPackage[0])
		    newerPkgBranch = self.retrieveBranch(newerPackage[0])
	            similarPackages = self.searchPackagesByNameAndVersionAndCategory(name = newerPkgName, version = newerPkgVersion, category = newerPkgCategory, branch = newerPkgBranch)

		    if (multiMatch):
                        similarPackages = set([x[1] for x in similarPackages])
                        self.atomMatchStoreCache((similarPackages,0), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
			return similarPackages,0

		    #print newerPackage
		    #print similarPackages
	            if (len(similarPackages) > 1):
		        # gosh, there are packages with the same name, version, category
		        # we need to parse version tag
		        versionTags = []
		        for pkg in similarPackages:
		            versionTags.append(self.retrieveVersionTag(pkg[1]))
		        versiontaglist = entropyTools.getNewerVersionTag(versionTags)
		        newerPackage = similarPackages[versionTags.index(versiontaglist[0])]
                        newerPackage = newerPackage[1],None
		

                    self.atomMatchStoreCache((newerPackage[0],0), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
		    return newerPackage[0],0

	        else:
                    self.atomMatchStoreCache((-1,1), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
		    return -1,1
		
	    else:
	    
	        # not set, just get the newer version, matching slot choosen if matchSlot != None
	        versionIDs = []
		#print foundIDs
		multiMatchList = set()
		_foundIDs = []
	        for data in foundIDs:
		    if (matchSlot == None) and (matchTag == None):
		        versionIDs.append(self.retrieveVersion(data[1]))
			if (multiMatch):
			    multiMatchList.add(data[1])
		    else:
			if (matchSlot != None):
			    foundslot = self.retrieveSlot(data[1])
			    if (str(foundslot) != str(matchSlot)):
			        continue
			if (matchTag != None):
			    if matchTag != self.retrieveVersionTag(data[1]):
				continue
			versionIDs.append(self.retrieveVersion(data[1]))
			if (multiMatch):
			    multiMatchList.add(data[1])
		    _foundIDs.append(data)
		foundIDs = _foundIDs

		if (multiMatch):
                    self.atomMatchStoreCache((multiMatchList,0), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
		    return multiMatchList,0
		
		if (not versionIDs):
                    self.atomMatchStoreCache((-1,1), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
		    return -1,1
		
	        versionlist = entropyTools.getNewerVersion(versionIDs)
	        newerPackage = foundIDs[versionIDs.index(versionlist[0])]
	    
	        # now look if there's another package with the same category, name, version, tag
	        newerPkgName = self.retrieveName(newerPackage[1])
	        newerPkgCategory = self.retrieveCategory(newerPackage[1])
	        newerPkgVersion = self.retrieveVersion(newerPackage[1])
	        newerPkgBranch = self.retrieveBranch(newerPackage[1])
	        similarPackages = self.searchPackagesByNameAndVersionAndCategory(name = newerPkgName, version = newerPkgVersion, category = newerPkgCategory, branch = newerPkgBranch)

	        if (len(similarPackages) > 1):
		    # gosh, there are packages with the same name, version, category
		    # we need to parse version tag
		    versionTags = []
		    for pkg in similarPackages:
		        versionTags.append(self.retrieveVersionTag(pkg[1]))
		    versiontaglist = entropyTools.getNewerVersionTag(versionTags)
		    newerPackage = similarPackages[versionTags.index(versiontaglist[0])]

                self.atomMatchStoreCache((newerPackage[1],0), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
	        return newerPackage[1],0

        else:
	    # package not found in any branch
            self.atomMatchStoreCache((-1,1), atom, caseSensitive, matchSlot, multiMatch, matchBranches, matchTag, packagesFilter)
	    return -1,1
