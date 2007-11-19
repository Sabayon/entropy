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

# Never do "import portage" here, please use entropyTools binding
# EXIT STATUSES: 300-399

from entropyConstants import *
import entropyTools
from outputTools import *
# FIXME: we'll drop extra sqlite support before 1.0
try: # try with sqlite3 from python 2.5 - default one
    from sqlite3 import dbapi2 as sqlite
except ImportError: # fallback to embedded pysqlite
    from pysqlite2 import dbapi2 as sqlite
import dumpTools
import os

# Logging initialization
import logTools
dbLog = logTools.LogFile(level = etpConst['databaseloglevel'],filename = etpConst['databaselogfile'], header = "[DBase]")


############
# Functions and Classes
#####################################################################################

'''
   @description: open the repository database and returns the pointer
   @input repositoryName: name of the client database
   @output: database pointer or, -1 if error
'''
def openRepositoryDatabase(repositoryName, xcache = True):
    dbfile = etpRepositories[repositoryName]['dbpath']+"/"+etpConst['etpdatabasefile']
    if not os.path.isfile(dbfile):
	rc = fetchRepositoryIfNotAvailable(repositoryName)
	if (rc):
	    raise Exception, "openRepositoryDatabase: cannot sync repository "+repositoryName
    conn = etpDatabase(readOnly = True, dbFile = dbfile, clientDatabase = True, dbname = 'repo_'+repositoryName, xcache = xcache)
    # initialize CONFIG_PROTECT
    if (etpRepositories[repositoryName]['configprotect'] == None) or (etpRepositories[repositoryName]['configprotectmask'] == None):
        etpRepositories[repositoryName]['configprotect'] = conn.listConfigProtectDirectories()
        etpRepositories[repositoryName]['configprotectmask'] = conn.listConfigProtectDirectories(mask = True)
	etpRepositories[repositoryName]['configprotect'] += [x for x in etpConst['configprotect'] if x not in etpRepositories[repositoryName]['configprotect']]
	etpRepositories[repositoryName]['configprotectmask'] += [x for x in etpConst['configprotectmask'] if x not in etpRepositories[repositoryName]['configprotectmask']]
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
	# so quit
	print_error(red("Database file for '"+bold(etpRepositories[reponame]['description'])+red("' does not exist. Cannot search.")))
    return rc

'''
   @description: open the installed packages database and returns the pointer
   @output: database pointer or, -1 if error
'''
def openClientDatabase(xcache = True, generate = False):
    if (not generate) and (not os.path.isfile(etpConst['etpdatabaseclientfilepath'])):
	raise Exception,"openClientDatabase: installed packages database not found. At this stage, the only way to have it is to run 'equo database generate'. Please note: don't use Equo on a critical environment !!"
    else:
        conn = etpDatabase(readOnly = False, dbFile = etpConst['etpdatabaseclientfilepath'], clientDatabase = True, dbname = 'client', xcache = xcache)
	if (not etpConst['dbconfigprotect']):
	    # config protect not prepared
            if (not generate):
                etpConst['dbconfigprotect'] = conn.listConfigProtectDirectories()
                etpConst['dbconfigprotectmask'] = conn.listConfigProtectDirectories(mask = True)
                etpConst['dbconfigprotect'] += [x for x in etpConst['configprotect'] if x not in etpConst['dbconfigprotect']]
                etpConst['dbconfigprotectmask'] += [x for x in etpConst['configprotectmask'] if x not in etpConst['dbconfigprotectmask']]
	return conn

'''
   @description: open the entropy server database and returns the pointer. This function must be used only by reagent or activator
   @output: database pointer
'''
def openServerDatabase(readOnly = True, noUpload = True):
    conn = etpDatabase(readOnly = readOnly, dbFile = etpConst['etpdatabasefilepath'], noUpload = noUpload)
    return conn

'''
   @description: open a generic client database and returns the pointer.
   @output: database pointer
'''
def openGenericDatabase(dbfile, dbname = None):
    if dbname == None: dbname = "generic"
    conn = etpDatabase(readOnly = False, dbFile = dbfile, clientDatabase = True, dbname = dbname, xcache = False)
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
    return branches

# this class simply describes the current database status
# FIXME: need a rewrite? simply using dicts, perhaps?
class databaseStatus:

    def __init__(self):
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus.__init__ called.")
	
	self.databaseBumped = False
	self.databaseInfoCached = False
	self.databaseLock = False
	#self.database
	self.databaseDownloadLock = False
	self.databaseAlreadyTainted = False
	
	if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile']):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: database tainted.")
	    self.databaseAlreadyTainted = True

    def isDatabaseAlreadyBumped(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: already bumped? "+str(self.databaseBumped))
	return self.databaseBumped

    def isDatabaseAlreadyTainted(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: tainted? "+str(self.databaseAlreadyTainted))
	return self.databaseAlreadyTainted

    def setDatabaseTaint(self,bool):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: setting database taint to: "+str(bool))
	self.databaseAlreadyTainted = bool

    def setDatabaseBump(self,bool):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: setting database bump to: "+str(bool))
	self.databaseBumped = bool

    def setDatabaseLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: Locking database (upload)")
	self.databaseLock = True

    def unsetDatabaseLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: Unlocking database (upload)")
	self.databaseLock = False

    def getDatabaseLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: getting database lock info (upload), status: "+str(self.databaseLock))
	return self.databaseLock

    def setDatabaseDownloadLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: Locking database (download)")
	self.databaseDownloadLock = True

    def unsetDatabaseDownloadLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: Unlocking database (download)")
	self.databaseDownloadLock = False

    def getDatabaseDownloadLock(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"DatabaseStatus: getting database lock info (download), status: "+str(self.databaseDownloadLock))
	return self.databaseDownloadLock

class etpDatabase:

    def __init__(self, readOnly = False, noUpload = False, dbFile = etpConst['etpdatabasefilepath'], clientDatabase = False, xcache = False, dbname = 'etpdb'):
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase.__init__ called.")
	
	self.readOnly = readOnly
	self.noUpload = noUpload
	self.packagesRemoved = False
	self.packagesAdded = False
	self.clientDatabase = clientDatabase
	self.xcache = xcache
	self.dbname = dbname
	
	# caching dictionaries
	if (self.xcache) and (dbname != 'etpdb'):
	    
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
		dbCacheStore[etpCache['dbInfo']+self.dbname] = {}
		dbCacheStore[etpCache['dbSearch']+self.dbname] = {}
		dumpTools.dumpobj(etpCache['dbMatch']+self.dbname,{})
		dumpTools.dumpobj(etpCache['dbInfo']+self.dbname,{})
		dumpTools.dumpobj(etpCache['dbSearch']+self.dbname,{})
		
	else:
	    self.xcache = False # setting this to be safe
	    dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
	    dbCacheStore[etpCache['dbInfo']+self.dbname] = {}
	    dbCacheStore[etpCache['dbSearch']+self.dbname] = {}
	
	if (self.clientDatabase):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase: database opened by Entropy client, file: "+str(dbFile))
	    # if the database is opened readonly, we don't need to lock the online status
	    self.connection = sqlite.connect(dbFile)
	    self.cursor = self.connection.cursor()
	    # set the table read only
	    return
	
	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase: database opened readonly, file: "+str(dbFile))
	    # if the database is opened readonly, we don't need to lock the online status
	    self.connection = sqlite.connect(dbFile)
	    self.cursor = self.connection.cursor()
	    # set the table read only
	    return
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase: database opened in read/write mode, file: "+str(dbFile))

	import mirrorTools
	import activatorTools

	# check if the database is locked locally
	if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']):
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"etpDatabase: database already locked")
	    print_info(red(" * ")+red("Entropy database is already locked by you :-)"))
	else:
	    # check if the database is locked REMOTELY
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"etpDatabase: starting to lock and sync database")
	    print_info(red(" * ")+red(" Locking and Syncing Entropy database ..."), back = True)
	    for uri in etpConst['activatoruploaduris']:
		dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase: connecting to "+uri)
	        ftp = mirrorTools.handlerFTP(uri)
                ftp.setCWD(etpConst['etpurirelativepath'])
	        if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])) and (not os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])):
		    import time
		    print_info(red(" * ")+bold("WARNING")+red(": online database is already locked. Waiting up to 2 minutes..."), back = True)
		    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"etpDatabase: online database already locked. Waiting 2 minutes")
		    unlocked = False
		    for x in range(120):
		        time.sleep(1)
		        if (not ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
			    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"etpDatabase: online database has been unlocked !")
			    print_info(red(" * ")+bold("HOORAY")+red(": online database has been unlocked. Locking back and syncing..."))
			    unlocked = True
			    break
		    if (unlocked):
		        break

		    dbLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"etpDatabase: online database has not been unlocked in time. Giving up.")
		    # time over
		    print_info(red(" * ")+bold("ERROR")+red(": online database has not been unlocked. Giving up. Who the hell is working on it? Damn, it's so frustrating for me. I'm a piece of python code with a soul dude!"))

		    print_info(yellow(" * ")+green("Mirrors status table:"))
		    dbstatus = activatorTools.getMirrorsLock()
		    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase: showing mirrors status table:")
		    for db in dbstatus:
		        if (db[1]):
	        	    db[1] = red("Locked")
	    	        else:
	        	    db[1] = green("Unlocked")
	    	        if (db[2]):
	        	    db[2] = red("Locked")
	                else:
	        	    db[2] = green("Unlocked")
			dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"   "+entropyTools.extractFTPHostFromUri(db[0])+": DATABASE: "+db[1]+" | DOWNLOAD: "+db[2])
	    	        print_info(bold("\t"+entropyTools.extractFTPHostFromUri(db[0])+": ")+red("[")+yellow("DATABASE: ")+db[1]+red("] [")+yellow("DOWNLOAD: ")+db[2]+red("]"))
	    
	            ftp.closeConnection()
	            from sys import exit
                    exit(320)

	    # if we arrive here, it is because all the mirrors are unlocked so... damn, LOCK!
	    activatorTools.lockDatabases(True)

	    # ok done... now sync the new db, if needed
	    activatorTools.syncRemoteDatabases(self.noUpload)
	
	self.connection = sqlite.connect(dbFile,timeout=300.0)
	self.cursor = self.connection.cursor()

    def closeDB(self):

	# if the class is opened readOnly, close and forget
	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"closeDB: closing database opened in readonly.")
	    #self.connection.rollback()
	    self.cursor.close()
	    self.connection.close()
	    return

	# if it's equo that's calling the function, just save changes and quit
	if (self.clientDatabase):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"closeDB: closing database opened by Entropy Client.")
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

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"closeDB: closing database opened in read/write.")
	
	if (entropyTools.dbStatus.isDatabaseAlreadyTainted()) and (not entropyTools.dbStatus.isDatabaseAlreadyBumped()):
	    # bump revision, setting DatabaseBump causes the session to just bump once
	    entropyTools.dbStatus.setDatabaseBump(True)
	    self.revisionBump()
	
	if (not entropyTools.dbStatus.isDatabaseAlreadyTainted()):
	    # we can unlock it, no changes were made
	    import activatorTools
	    activatorTools.lockDatabases(False)
	else:
	    print_info(yellow(" * ")+green("Mirrors have not been unlocked. Run activator."))
	
	self.cursor.close()
	self.connection.close()

    def commitChanges(self):
	if (not self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"commitChanges: writing changes to database.")
	    try:
	        self.connection.commit()
	    except:
		pass
	    self.taintDatabase()
	else:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"commitChanges: discarding changes to database (opened readonly).")
	    self.discardChanges() # is it ok?

    def taintDatabase(self):
	if (self.clientDatabase): # if it's equo to open it, this should be avoided
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"taintDatabase: called by Entropy client, won't do anything.")
	    return
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"taintDatabase: called.")
	# taint the database status
	f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile'],"w")
	f.write(etpConst['currentarch']+" database tainted\n")
	f.flush()
	f.close()
	entropyTools.dbStatus.setDatabaseTaint(True)

    def untaintDatabase(self):
	if (self.clientDatabase): # if it's equo to open it, this should be avoided
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"untaintDatabase: called by Entropy client, won't do anything.")
	    return
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"untaintDatabase: called.")
	entropyTools.dbStatus.setDatabaseTaint(False)
	# untaint the database status
	entropyTools.spawnCommand("rm -f "+etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile'])

    def revisionBump(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"revisionBump: called.")
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
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isDatabaseTainted: called.")
	if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile']):
	    return True
	return False

    def discardChanges(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"discardChanges: called.")
	self.connection.rollback()

    # never use this unless you know what you're doing
    def initializeDatabase(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"initializeDatabase: called.")
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
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlePackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

    # this function manages the submitted package
    # if it does not exist, it fires up addPackage
    # otherwise it fires up updatePackage
    def handlePackage(self, etpData, forcedRevision = -1):

	self.checkReadOnly()

	# build atom string
	versiontag = ''
	if etpData['versiontag']:
	    versiontag = '#'+etpData['versiontag']

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlePackage: called.")
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

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addPackage: called.")
	
	# we need to find other packages with the same key and slot, and remove them
	if (self.clientDatabase): # client database can't care about branch
	    searchsimilar = self.searchPackagesByNameAndCategory(name = etpData['name'], category = etpData['category'], sensitive = True)
	else: # server supports multiple branches inside a db
	    searchsimilar = self.searchPackagesByNameAndCategory(name = etpData['name'], category = etpData['category'], sensitive = True, branch = etpData['branch'])
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"addPackage: here is the list of similar packages (that will be removed) found for "+etpData['category']+"/"+etpData['name']+": "+str(searchsimilar))
	
	removelist = set()
	for oldpkg in searchsimilar:
	    # get the package slot
	    idpackage = oldpkg[1]
	    slot = self.retrieveSlot(idpackage)
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
        self.cursor.execute(
                'INSERT into baseinfo VALUES '
                '(NULL,?,?,?,?,?,?,?,?,?,?,?)'
                , (	etpData['category']+"/"+etpData['name']+"-"+etpData['version']+versiontag,
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
	for file in etpData['content']:
            contenttype = etpData['content'][file]
            try:
                self.cursor.execute(
                    'INSERT into content VALUES '
                    '(?,?,?)'
                    , (	idpackage,
                            file,
                            contenttype,
                            )
                )
            except:
                self.createContentTypeColumn()
                self.cursor.execute(
                    'INSERT into content VALUES '
                    '(?,?,?)'
                    , (	idpackage,
                            file,
                            contenttype,
                            )
                )

	# counter, if != -1
	if etpData['counter'] != -1:
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
	dbCacheStore[etpCache['dbInfo']+self.dbname] = {}
	dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
	dbCacheStore[etpCache['dbSearch']+self.dbname] = {}
	# dump to be sure
	dumpTools.dumpobj(etpCache['dbInfo']+self.dbname,{})
	dumpTools.dumpobj(etpCache['dbMatch']+self.dbname,{})
	dumpTools.dumpobj(etpCache['dbSearch']+self.dbname,{})

	self.packagesAdded = True
	self.commitChanges()
	
	return idpackage, revision, etpData, True

    # Update already available atom in db
    # returns True,revision if the package has been updated
    # returns False,revision if not
    def updatePackage(self, etpData, forcedRevision = -1):

	self.checkReadOnly()

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"updatePackage: called.")

	# build atom string
	versiontag = ''
	if etpData['versiontag']:
	    versiontag = '#'+etpData['versiontag']
	pkgatom = etpData['category'] + "/" + etpData['name'] + "-" + etpData['version']+versiontag

	# for client database - the atom if present, must be overwritten with the new one regardless its branch
	if (self.clientDatabase):
	    
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"updatePackage: client request. Removing duplicated entries.")
	    atomid = self.isPackageAvailable(pkgatom)
	    if atomid > -1:
		self.removePackage(atomid)
	    
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: removal complete. Now spawning addPackage.")
	    x,y,z,accepted = self.addPackage(etpData, revision = forcedRevision)
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: returned back from addPackage.")
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
	    
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: current revision set to "+str(curRevision))

	    # add the new one
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: complete. Now spawning addPackage.")
	    x,y,z,accepted = self.addPackage(etpData, revision = curRevision)
	    return x,y,z,accepted
	

    def removePackage(self,idpackage):

	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removePackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

	key = self.retrieveAtom(idpackage)
	branch = self.retrieveBranch(idpackage)

	idpackage = str(idpackage)
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"removePackage: trying to remove (if exists) -> "+idpackage+":"+str(key)+" | branch: "+branch)
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
	
	# Remove from installedtable if exists
	self.removePackageFromInstalledTable(idpackage)
	# Remove from dependstable if exists
	self.removePackageFromDependsTable(idpackage)
	# need a final cleanup
	self.packagesRemoved = True

	# clear caches
	dbCacheStore[etpCache['dbInfo']+self.dbname] = {}
	dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
	dbCacheStore[etpCache['dbSearch']+self.dbname] = {}
	# dump to be sure
	dumpTools.dumpobj(etpCache['dbInfo']+self.dbname,{})
	dumpTools.dumpobj(etpCache['dbMatch']+self.dbname,{})
	dumpTools.dumpobj(etpCache['dbSearch']+self.dbname,{})

	self.commitChanges()

    def removeMirrorEntries(self,mirrorname):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removeMirrors: removing entries for mirror -> "+str(mirrorname))
	self.cursor.execute('DELETE FROM mirrorlinks WHERE mirrorname = "'+mirrorname+'"')
	self.commitChanges()

    def addMirrors(self,mirrorname,mirrorlist):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addMirrors: adding Mirror list for "+str(mirrorname)+" -> "+str(mirrorlist))
	for x in mirrorlist:
	    self.cursor.execute(
		'INSERT into mirrorlinks VALUES '
		'(?,?)', (mirrorname,x,)
	    )
	self.commitChanges()

    def addCategory(self,category):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addCategory: adding Package Category -> "+str(category))
	self.cursor.execute(
		'INSERT into categories VALUES '
		'(NULL,?)', (category,)
	)
	# get info about inserted value and return
	cat = self.isCategoryAvailable(category)
	if cat != -1:
	    self.commitChanges()
	    return cat
	raise Exception, "I tried to insert a category but then, fetching it returned -1. There's something broken."

    def addProtect(self,protect):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addProtect: adding CONFIG_PROTECT/CONFIG_PROTECT_MASK -> "+str(protect))
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
	raise Exception, "I tried to insert a protect but then, fetching it returned -1. There's something broken."

    def addSource(self,source):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addSource: adding Package Source -> "+str(source))
	self.cursor.execute(
		'INSERT into sourcesreference VALUES '
		'(NULL,?)', (source,)
	)
	# get info about inserted value and return
	src = self.isSourceAvailable(source)
	if src != -1:
	    return src
	raise Exception, "I tried to insert a source but then, fetching it returned -1. There's something broken."

    def addDependency(self,dependency):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addDependency: adding Package Dependency -> "+str(dependency))
	self.cursor.execute(
		'INSERT into dependenciesreference VALUES '
		'(NULL,?)', (dependency,)
	)
	# get info about inserted value and return
	dep = self.isDependencyAvailable(dependency)
	if dep != -1:
	    return dep
	raise Exception, "I tried to insert a dependency but then, fetching it returned -1. There's something broken."

    def addKeyword(self,keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addKeyword: adding Keyword -> "+str(keyword))
	self.cursor.execute(
		'INSERT into keywordsreference VALUES '
		'(NULL,?)', (keyword,)
	)
	# get info about inserted value and return
	key = self.isKeywordAvailable(keyword)
	if key != -1:
	    return key
	raise Exception, "I tried to insert a keyword but then, fetching it returned -1. There's something broken."

    def addUseflag(self,useflag):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addUseflag: adding Keyword -> "+str(useflag))
	self.cursor.execute(
		'INSERT into useflagsreference VALUES '
		'(NULL,?)', (useflag,)
	)
	# get info about inserted value and return
	use = self.isUseflagAvailable(useflag)
	if use != -1:
	    return use
	raise Exception, "I tried to insert a useflag but then, fetching it returned -1. There's something broken."

    def addEclass(self,eclass):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addEclass: adding Eclass -> "+str(eclass))
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
	raise Exception, "I tried to insert an eclass but then, fetching it returned -1. There's something broken."

    def addNeeded(self,needed):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addNeeded: adding needed library -> "+str(needed))
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
	raise Exception, "I tried to insert a needed library but then, fetching it returned -1. There's something broken."

    def addLicense(self,license):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addLicense: adding License -> "+str(license))
	self.cursor.execute(
		'INSERT into licenses VALUES '
		'(NULL,?)', (license,)
	)
	# get info about inserted value and return
	lic = self.isLicenseAvailable(license)
	if lic != -1:
	    return lic
	raise Exception, "I tried to insert a license but then, fetching it returned -1. There's something broken."

    #addCompileFlags(etpData['chost'],etpData['cflags'],etpData['cxxflags'])
    def addCompileFlags(self,chost,cflags,cxxflags):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addCompileFlags: adding Flags -> "+chost+"|"+cflags+"|"+cxxflags)
	self.cursor.execute(
		'INSERT into flags VALUES '
		'(NULL,?,?,?)', (chost,cflags,cxxflags,)
	)
	# get info about inserted value and return
	idflag = self.areCompileFlagsAvailable(chost,cflags,cxxflags)
	if idflag != -1:
	    return idflag
	raise Exception, "I tried to insert a flag tuple but then, fetching it returned -1. There's something broken."

    def setDigest(self, idpackage, digest):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"setDigest: setting new digest for idpackage: "+str(idpackage)+" -> "+str(digest))
	self.cursor.execute('UPDATE extrainfo SET digest = "'+str(digest)+'" WHERE idpackage = "'+str(idpackage)+'"')

    def setCounter(self, idpackage, counter):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"setCounter: setting new counter for idpackage: "+str(idpackage)+" -> "+str(counter))
        try:
            self.cursor.execute('UPDATE counters SET counter = "'+str(counter)+'" WHERE idpackage = "'+str(idpackage)+'"')
        except:
            if self.dbname == "client":
                self.createCountersTable()
                self.cursor.execute(
                    'INSERT into counters VALUES '
                    '(?,?)', (counter,idpackage,)
                )

    def cleanupUseflags(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupUseflags: called.")
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
	
	# empty cursor
	x = self.cursor.fetchall()

    def cleanupSources(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupSources: called.")
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
	
	# empty cursor
	x = self.cursor.fetchall()

    def cleanupEclasses(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupEclasses: called.")
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
	
	# empty cursor
	x = self.cursor.fetchall()

    def cleanupNeeded(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupNeeded: called.")
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
	# empty cursor
	x = self.cursor.fetchall()

    def cleanupDependencies(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupDependencies: called.")
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
	# empty cursor
	x = self.cursor.fetchall()

    def getIDPackage(self, atom, branch = etpConst['branch']):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getIDPackage: retrieving package ID for "+atom+" | branch: "+branch)
	self.cursor.execute('SELECT "IDPACKAGE" FROM baseinfo WHERE atom = "'+atom+'" AND branch = "'+branch+'"')
	idpackage = -1
        idpackage = self.cursor.fetchone()
        if idpackage:
            idpackage = idpackage[0]
        else:
            idpackage = -1
	return idpackage

    def getIDPackageFromFileInBranch(self, file, branch = "unstable"):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getIDPackageFromFile: retrieving package ID for file "+file+" | branch: "+branch)
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
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getIDPackageFromFile: retrieving package ID for file "+file)
	self.cursor.execute('SELECT idpackage FROM content WHERE file = "'+file+'"')
	idpackages = []
	for row in self.cursor:
	    idpackages.append(row[0])
	return idpackages

    def getIDCategory(self, category):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getIDCategory: retrieving category ID for "+str(category))
	self.cursor.execute('SELECT "idcategory" FROM categories WHERE category = "'+str(category)+'"')
	idcat = -1
	for row in self.cursor:
	    idcat = int(row[0])
	    break
	return idcat

    def getIDPackageFromBinaryPackage(self,packageName):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getIDPackageFromBinaryPackage: retrieving package ID for "+atom+" | branch: "+branch)
	self.cursor.execute('SELECT "IDPACKAGE" FROM baseinfo WHERE download = "'+etpConst['binaryurirelativepath']+packageName+'"')
	idpackage = -1
	for row in self.cursor:
	    idpackage = int(row[0])
	    break
	return idpackage

    def getBaseData(self,idpackage):
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
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageData: retrieving etpData for package ID for "+str(idpackage))
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
	    for y in x:
		mycontent.add(y)
	return mycontent

    def fetchall2list(self, item):
	content = []
	for x in item:
	    for y in x:
		content.append(y)
	return content

    def fetchone2list(self, item):
	return list(item)

    def fetchone2set(self, item):
	return set(item)

    def fetchInfoCache(self,idpackage,function):
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage))
	    if cached != None:
		rslt = cached.get(function)
		if rslt != None:
		    return rslt
	return None

    def storeInfoCache(self,idpackage,function,data):
	if (self.xcache):
	    cache = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage))
	    if cache == None: dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)][function] = data

    def fetchSearchCache(self,searchdata,function):
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbSearch']+self.dbname].get(function)
	    if cached != None:
		rslt = cached.get(searchdata)
		if rslt != None:
		    return rslt
	return None

    def storeSearchCache(self,searchdata,function,data):
	if (self.xcache):
	    cache = dbCacheStore[etpCache['dbSearch']+self.dbname].get(function)
	    if cache == None: dbCacheStore[etpCache['dbSearch']+self.dbname][function] = {}
	    dbCacheStore[etpCache['dbSearch']+self.dbname][function][searchdata] = data

    def retrieveAtom(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveAtom: retrieving Atom for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveAtom')
	if cache != None: return cache

	self.cursor.execute('SELECT "atom" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	atom = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveAtom',atom)
	return atom

    def retrieveBranch(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveBranch: retrieving Branch for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveBranch')
	if cache != None: return cache

	self.cursor.execute('SELECT "branch" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	br = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveBranch',br)
	return br

    def retrieveTrigger(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveTrigger: retrieving Branch for package ID "+str(idpackage))

	#cache = self.fetchInfoCache(idpackage,'retrieveTrigger')
	#if cache != None: return cache
	
	try:
	    self.cursor.execute('SELECT "data" FROM triggers WHERE idpackage = "'+str(idpackage)+'"')
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
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDownloadURL: retrieving download URL for package ID "+str(idpackage))
	
	cache = self.fetchInfoCache(idpackage,'retrieveDownloadURL')
	if cache != None: return cache

	self.cursor.execute('SELECT "download" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	download = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveDownloadURL',download)
	return download

    def retrieveDescription(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDescription: retrieving description for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveDescription')
	if cache != None: return cache

	self.cursor.execute('SELECT "description" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	description = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveDescription',description)
	return description

    def retrieveHomepage(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveHomepage: retrieving Homepage for package ID "+str(idpackage))
	
	cache = self.fetchInfoCache(idpackage,'retrieveHomepage')
	if cache != None: return cache

	self.cursor.execute('SELECT "homepage" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	home = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveHomepage',home)
	return home

    def retrieveCounter(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveCounter: retrieving Counter for package ID "+str(idpackage))
	
	cache = self.fetchInfoCache(idpackage,'retrieveCounter')
	if cache != None: return cache
	
	counter = -1
	try:
	    self.cursor.execute('SELECT "counter" FROM counters WHERE idpackage = "'+str(idpackage)+'"')
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
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveMessages: retrieving messages for package ID "+str(idpackage))
	
	cache = self.fetchInfoCache(idpackage,'retrieveMessages')
	if cache != None: return cache

	messages = []
	try:
	    self.cursor.execute('SELECT "message" FROM messages WHERE idpackage = "'+str(idpackage)+'"')
	    messages = self.fetchall2list(self.cursor.fetchall())
	except:
	    pass

	self.storeInfoCache(idpackage,'retrieveMessages',messages)
	return messages

    # in bytes
    def retrieveSize(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSize: retrieving Size for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveSize')
	if cache != None: return cache

	self.cursor.execute('SELECT "size" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	size = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveSize',size)
	return size

    # in bytes
    def retrieveOnDiskSize(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveOnDiskSize: retrieving On Disk Size for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveOnDiskSize')
	if cache != None: return cache

	try:
	    self.cursor.execute('SELECT size FROM sizes WHERE idpackage = "'+str(idpackage)+'"')
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
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDigest: retrieving Digest for package ID "+str(idpackage))
	
	cache = self.fetchInfoCache(idpackage,'retrieveDigest')
	if cache != None: return cache

	self.cursor.execute('SELECT "digest" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	digest = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveDigest',digest)
	return digest

    def retrieveName(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveName: retrieving Name for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveName')
	if cache != None: return cache

	self.cursor.execute('SELECT "name" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	name = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveName',name)
	return name

    def retrieveVersion(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveVersion: retrieving Version for package ID "+str(idpackage))
	
	cache = self.fetchInfoCache(idpackage,'retrieveVersion')
	if cache != None: return cache
	
	self.cursor.execute('SELECT "version" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveVersion',ver)
	return ver

    def retrieveRevision(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveRevision: retrieving Revision for package ID "+str(idpackage))
	
	cache = self.fetchInfoCache(idpackage,'retrieveRevision')
	if cache != None: return cache

	self.cursor.execute('SELECT "revision" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	rev = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveRevision',rev)
	return rev

    def retrieveDateCreation(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDateCreation: retrieving Creation Date for package ID "+str(idpackage))
	
	cache = self.fetchInfoCache(idpackage,'retrieveDateCreation')
	if cache != None: return cache

	self.cursor.execute('SELECT "datecreation" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	date = self.cursor.fetchone()[0]
	if not date:
	    date = "N/A" #FIXME: to be removed?

	self.storeInfoCache(idpackage,'retrieveDateCreation',date)
	return date

    def retrieveApi(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveApi: retrieving Database API for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveApi')
	if cache != None: return cache

	self.cursor.execute('SELECT "etpapi" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	api = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveApi',api)
	return api

    def retrieveUseflags(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveUseflags: retrieving USE flags for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveUseflags')
	if cache != None: return cache

	self.cursor.execute('SELECT flagname FROM useflags,useflagsreference WHERE useflags.idpackage = "'+str(idpackage)+'" and useflags.idflag = useflagsreference.idflag')
	flags = self.fetchall2set(self.cursor.fetchall())
	

	self.storeInfoCache(idpackage,'retrieveUseflags',flags)
	return flags

    def retrieveEclasses(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveEclasses: retrieving eclasses for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveEclasses')
	if cache != None: return cache

	self.cursor.execute('SELECT classname FROM eclasses,eclassesreference WHERE eclasses.idpackage = "'+str(idpackage)+'" and eclasses.idclass = eclassesreference.idclass')
	classes = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveEclasses',classes)
	return classes

    def retrieveNeeded(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveNeeded: retrieving needed libraries for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveNeeded')
	if cache != None: return cache

	self.cursor.execute('SELECT library FROM needed,neededreference WHERE needed.idpackage = "'+str(idpackage)+'" and needed.idneeded = neededreference.idneeded')
	needed = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveNeeded',needed)
	return needed

    def retrieveConflicts(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveEclasses: retrieving Conflicts for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveConflicts')
	if cache != None: return cache

	self.cursor.execute('SELECT "conflict" FROM conflicts WHERE idpackage = "'+str(idpackage)+'"')
	confl = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveConflicts',confl)
	return confl

    def retrieveProvide(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveProvide: retrieving Provide for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveProvide')
	if cache != None: return cache

	self.cursor.execute('SELECT "atom" FROM provide WHERE idpackage = "'+str(idpackage)+'"')
	provide = self.fetchall2set(self.cursor.fetchall())
	
	self.storeInfoCache(idpackage,'retrieveProvide',provide)
	return provide

    def retrieveDependencies(self, idpackage):
	#dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDependencies: retrieving dependency for package ID "+str(idpackage)) # too slow?

	cache = self.fetchInfoCache(idpackage,'retrieveDependencies')
	if cache != None: return cache
	
	self.cursor.execute('SELECT dependenciesreference.dependency FROM dependencies,dependenciesreference WHERE idpackage = "'+str(idpackage)+'" and dependencies.iddependency = dependenciesreference.iddependency')
	deps = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveDependencies',deps)
	return deps

    def retrieveIdDependencies(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveIdDependencies: retrieving Dependencies for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveIdDependencies')
	if cache != None: return cache

	self.cursor.execute('SELECT iddependency FROM dependencies WHERE idpackage = "'+str(idpackage)+'"')
	iddeps = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveIdDependencies',iddeps)
	return iddeps

    def retrieveBinKeywords(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveBinKeywords: retrieving Binary Keywords for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveBinKeywords')
	if cache != None: return cache

	self.cursor.execute('SELECT keywordname FROM binkeywords,keywordsreference WHERE binkeywords.idpackage = "'+str(idpackage)+'" and binkeywords.idkeyword = keywordsreference.idkeyword')
	kw = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveBinKeywords',kw)
	return kw

    def retrieveKeywords(self, idpackage):

	cache = self.fetchInfoCache(idpackage,'retrieveKeywords')
	if cache != None: return cache

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveKeywords: retrieving Keywords for package ID "+str(idpackage))
	self.cursor.execute('SELECT keywordname FROM keywords,keywordsreference WHERE keywords.idpackage = "'+str(idpackage)+'" and keywords.idkeyword = keywordsreference.idkeyword')
	kw = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveKeywords',kw)
	return kw

    def retrieveProtect(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveProtect: retrieving CONFIG_PROTECT for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveProtect')
	if cache != None: return cache

	self.cursor.execute('SELECT protect FROM configprotect,configprotectreference WHERE configprotect.idpackage = "'+str(idpackage)+'" and configprotect.idprotect = configprotectreference.idprotect')
        protect = self.cursor.fetchone()
        if not protect:
            protect = ''
	else:
	    protect = protect[0]

	self.storeInfoCache(idpackage,'retrieveProtect',protect)
	return protect

    def retrieveProtectMask(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveProtectMask: retrieving CONFIG_PROTECT_MASK for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveProtectMask')
	if cache != None: return cache

	self.cursor.execute('SELECT protect FROM configprotectmask,configprotectreference WHERE idpackage = "'+str(idpackage)+'" and configprotectmask.idprotect= configprotectreference.idprotect')
	protect = self.cursor.fetchone()
        if not protect:
            protect = ''
	else:
	    protect = protect[0]
	
	self.storeInfoCache(idpackage,'retrieveProtectMask',protect)
	return protect

    def retrieveSources(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSources: retrieving Sources for package ID "+str(idpackage))

	''' caching 
	cache = self.fetchInfoCache(idpackage,'retrieveSources')
	if cache != None: return cache
	'''

	self.cursor.execute('SELECT sourcesreference.source FROM sources,sourcesreference WHERE idpackage = "'+str(idpackage)+'" and sources.idsource = sourcesreference.idsource')
	sources = self.fetchall2set(self.cursor.fetchall())

	''' caching
	self.storeInfoCache(idpackage,'retrieveSources',sources)
	'''
	return sources

    def retrieveContent(self, idpackage, extended = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveContent: retrieving Content for package ID "+str(idpackage))

        self.createContentIndex() # FIXME: remove this with 1.0

        extstring = ''
        if extended:
            extstring = ",type"

        try:
            self.cursor.execute('SELECT file'+extstring+' FROM content WHERE idpackage = "'+str(idpackage)+'"')
        except:
            if extended:
                self.createContentTypeColumn()
                self.cursor.execute('SELECT file'+extstring+' FROM content WHERE idpackage = "'+str(idpackage)+'"')
            else:
                raise
        if extended:
            fl = self.cursor.fetchall()
        else:
            fl = self.fetchall2set(self.cursor.fetchall())

	return fl

    def retrieveSlot(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSlot: retrieving Slot for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveSlot')
	if cache != None: return cache

	self.cursor.execute('SELECT "slot" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveSlot',ver)
	return ver
    
    def retrieveVersionTag(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveVersionTag: retrieving Version TAG for package ID "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveVersionTag')
	if cache != None: return cache

	self.cursor.execute('SELECT "versiontag" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveVersionTag',ver)
	return ver
    
    def retrieveMirrorInfo(self, mirrorname):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveMirrorInfo: retrieving Mirror info for mirror name "+str(mirrorname))

	self.cursor.execute('SELECT "mirrorlink" FROM mirrorlinks WHERE mirrorname = "'+str(mirrorname)+'"')
	mirrorlist = self.fetchall2set(self.cursor.fetchall())

	return mirrorlist

    def retrieveCategory(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveCategory: retrieving Category for package ID for "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveCategory')
	if cache != None: return cache

	self.cursor.execute('SELECT category FROM baseinfo,categories WHERE baseinfo.idpackage = "'+str(idpackage)+'" and baseinfo.idcategory = categories.idcategory ')
	cat = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveCategory',cat)
	return cat

    def retrieveLicense(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveLicense: retrieving License for package ID for "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveLicense')
	if cache != None: return cache

	self.cursor.execute('SELECT license FROM baseinfo,licenses WHERE baseinfo.idpackage = "'+str(idpackage)+'" and baseinfo.idlicense = licenses.idlicense')
	licname = self.cursor.fetchone()[0]

	self.storeInfoCache(idpackage,'retrieveLicense',licname)
	return licname

    def retrieveCompileFlags(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveCompileFlags: retrieving CHOST,CFLAGS,CXXFLAGS for package ID for "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveCompileFlags')
	if cache != None: return cache

	self.cursor.execute('SELECT "idflags" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	idflag = self.cursor.fetchone()[0]
	# now get the flags
	self.cursor.execute('SELECT chost,cflags,cxxflags FROM flags WHERE idflags = '+str(idflag))
        flags = self.cursor.fetchone()
        if not flags:
            flags = ("N/A","N/A","N/A")

	self.storeInfoCache(idpackage,'retrieveCompileFlags',flags)
	return flags

    def retrieveDepends(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDepends: called for idpackage "+str(idpackage))

	cache = self.fetchInfoCache(idpackage,'retrieveDepends')
	if cache != None: return cache

	# sanity check on the table
	sanity = self.isDependsTableSane()
	if (not sanity):
	    return -2 # table does not exist or is broken, please regenerate and re-run

	self.cursor.execute('SELECT dependencies.idpackage FROM dependstable,dependencies WHERE dependstable.idpackage = "'+str(idpackage)+'" and dependstable.iddependency = dependencies.iddependency')
	result = self.fetchall2set(self.cursor.fetchall())

	self.storeInfoCache(idpackage,'retrieveDepends',result)
	return result

    # You must provide the full atom to this function
    # WARNING: this function does not support branches !!!
    def isPackageAvailable(self,pkgkey):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isPackageAvailable: called.")
	pkgkey = entropyTools.removePackageOperators(pkgkey)
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE atom = "'+pkgkey+'"')
	result = self.cursor.fetchone()
	if result:
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isPackageAvailable: "+pkgkey+" available.")
	    return result[0]
	dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isPackageAvailable: "+pkgkey+" not available.")
	return -1

    def isIDPackageAvailable(self,idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isIDPackageAvailable: called.")
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isIDPackageAvailable: "+str(idpackage)+" not available.")
	    return False
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isIDPackageAvailable: "+str(idpackage)+" available.")
	return True

    # This version is more specific and supports branches
    def isSpecificPackageAvailable(self, pkgkey, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSpecificPackageAvailable: called.")
	pkgkey = entropyTools.removePackageOperators(pkgkey)
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE atom = "'+pkgkey+'" AND branch = "'+branch+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isSpecificPackageAvailable: "+pkgkey+" | branch: "+branch+" -> not found.")
	    return False
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSpecificPackageAvailable: "+pkgkey+" | branch: "+branch+" -> found !")
	return True

    def isCategoryAvailable(self,category):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCategoryAvailable: called.")
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = "'+category+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isCategoryAvailable: "+category+" not available.")
	    return -1
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCategoryAvailable: "+category+" available.")
	return result[0]

    def isProtectAvailable(self,protect):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isProtectAvailable: called.")
	self.cursor.execute('SELECT idprotect FROM configprotectreference WHERE protect = "'+protect+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isProtectAvailable: "+protect+" not available.")
	    return -1
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isProtectAvailable: "+protect+" available.")
	return result[0]

    def isFileAvailable(self,file):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isFileAvailable: called.")
        self.createContentIndex() # FIXME: remove this with 1.0
	self.cursor.execute('SELECT idpackage FROM content WHERE file = "'+file+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isFileAvailable: "+file+" not available.")
	    return False
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isFileAvailable: "+file+" available.")
	return True

    def isSourceAvailable(self,source):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSourceAvailable: called.")
	self.cursor.execute('SELECT idsource FROM sourcesreference WHERE source = "'+source+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isSourceAvailable: "+source+" not available.")
	    return -1
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSourceAvailable: "+source+" available.")
	return result[0]

    def isDependencyAvailable(self,dependency):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isDependencyAvailable: called.")
	self.cursor.execute('SELECT iddependency FROM dependenciesreference WHERE dependency = "'+dependency+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isDependencyAvailable: "+dependency+" not available.")
	    return -1
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isDependencyAvailable: "+dependency+" available.")
	return result[0]

    def isKeywordAvailable(self,keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isKeywordAvailable: called.")
	self.cursor.execute('SELECT idkeyword FROM keywordsreference WHERE keywordname = "'+keyword+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isKeywordAvailable: "+keyword+" not available.")
	    return -1
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isKeywordAvailable: "+keyword+" available.")
	return result[0]

    def isUseflagAvailable(self,useflag):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isUseflagAvailable: called.")
	self.cursor.execute('SELECT idflag FROM useflagsreference WHERE flagname = "'+useflag+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isUseflagAvailable: "+useflag+" not available.")
	    return -1
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isUseflagAvailable: "+useflag+" available.")
	return result[0]

    def isEclassAvailable(self,eclass):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isEclassAvailable: called.")
	self.cursor.execute('SELECT idclass FROM eclassesreference WHERE classname = "'+eclass+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isEclassAvailable: "+eclass+" not available.")
	    return -1
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isEclassAvailable: "+eclass+" available.")
	return result[0]

    def isNeededAvailable(self,needed):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isNeededAvailable: called.")
	self.cursor.execute('SELECT idneeded FROM neededreference WHERE library = "'+needed+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isNeededAvailable: "+needed+" not available.")
	    return -1
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isNeededAvailable: "+needed+" available.")
	return result[0]

    def isCounterAvailable(self,counter):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCounterAvailable: called.")
	result = False
	self.cursor.execute('SELECT counter FROM counters WHERE counter = "'+str(counter)+'"')
        result = self.cursor.fetchone()
        if result:
	    result = True
	if (result):
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isCounterAvailable: "+str(counter)+" available.")
	else:
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCounterAvailable: "+str(counter)+" not available.")
	return result

    def isLicenseAvailable(self,license):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isLicenseAvailable: called.")
	self.cursor.execute('SELECT idlicense FROM licenses WHERE license = "'+license+'"')
	result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isLicenseAvailable: "+license+" not available.")
	    return -1
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isLicenseAvailable: "+license+" available.")
	return result[0]

    def isSystemPackage(self,idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSystemPackage: called.")

	cache = self.fetchInfoCache(idpackage,'isSystemPackage')
	if cache != None: return cache

        try:
	    self.cursor.execute('SELECT idpackage FROM systempackages WHERE idpackage = "'+str(idpackage)+'"')
        except: # FIXME: remove this for 1.0
            self.createSystemPackagesTable()
            self.cursor.execute('SELECT idpackage FROM systempackages WHERE idpackage = "'+str(idpackage)+'"')
        
	result = self.cursor.fetchone()
	rslt = False
	if result:
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSystemPackage: package is in system.")
	    rslt = True
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSystemPackage: package is NOT in system.")

	self.storeInfoCache(idpackage,'isSystemPackage',rslt)
	return rslt

    def areCompileFlagsAvailable(self,chost,cflags,cxxflags):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"areCompileFlagsAvailable: called.")
	self.cursor.execute('SELECT idflags FROM flags WHERE chost = "'+chost+'" AND cflags = "'+cflags+'" AND cxxflags = "'+cxxflags+'"')
        result = self.cursor.fetchone()
	if not result:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"areCompileFlagsAvailable: flags tuple "+chost+"|"+cflags+"|"+cxxflags+" not available.")
	    return -1
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"areCompileFlagsAvailable: flags tuple "+chost+"|"+cflags+"|"+cxxflags+" available.")
	return result[0]

    def searchBelongs(self, file, like = False, branch = None):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchBelongs: called for "+file)
	
	branchstring = ''
	if branch:
	    branchstring = ' and baseinfo.branch = "'+branch+'"'

	if (like):
	    self.cursor.execute('SELECT content.idpackage FROM content,baseinfo WHERE file LIKE "'+file+'" and content.idpackage = baseinfo.idpackage '+branchstring)
	else:
	    self.cursor.execute('SELECT content.idpackage FROM content,baseinfo WHERE file = "'+file+'" and content.idpackage = baseinfo.idpackage '+branchstring)

	return self.fetchall2set(self.cursor.fetchall())

    ''' search packages whose versiontag matches the one provided '''
    def searchTaggedPackages(self, tag, atoms = False): # atoms = return atoms directly
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchTaggedPackages: called for "+tag)
	if atoms:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE versiontag = "'+tag+'"')
	    return self.cursor.fetchall()
	else:
	    self.cursor.execute('SELECT idpackage FROM baseinfo WHERE versiontag = "'+tag+'"')
	    return self.fetchall2set(self.cursor.fetchall())

    ''' search packages that need the specified library (in neededreference table) specified by keyword '''
    def searchNeeded(self, keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchNeeded: called for "+keyword)
	self.cursor.execute('SELECT needed.idpackage FROM needed,neededreference WHERE library = "'+keyword+'" and needed.idneeded = neededreference.idneeded')
	return self.fetchall2set(self.cursor.fetchall())

    ''' same as above but with branch support '''
    def searchNeededInBranch(self, keyword, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchNeeded: called for "+keyword+" and branch: "+branch)
	self.cursor.execute('SELECT needed.idpackage FROM needed,neededreference,baseinfo WHERE library = "'+keyword+'" and needed.idneeded = neededreference.idneeded and baseinfo.branch = "'+branch+'"')
	return self.fetchall2set(self.cursor.fetchall())


    ''' search dependency string inside dependenciesreference table and retrieve iddependency '''
    def searchDependency(self, dep):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchDependency: called for "+dep)
	self.cursor.execute('SELECT iddependency FROM dependenciesreference WHERE dependency = "'+dep+'"')
	iddep = self.cursor.fetchone()
	if iddep:
	    iddep = iddep[0]
	else:
            iddep = -1
	return iddep

    ''' search iddependency inside dependencies table and retrieve idpackages '''
    def searchIdpackageFromIddependency(self, iddep):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchIdpackageFromIddependency: called for "+str(iddep))
	self.cursor.execute('SELECT idpackage FROM dependencies WHERE iddependency = "'+str(iddep)+'"')
	return self.fetchall2set(self.cursor.fetchall())

    def searchPackages(self, keyword, sensitive = False, slot = None, tag = None, branch = None):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackages: called for "+keyword)
	
	slotstring = ''
	if slot:
	    slotstring = ' and slot = "'+slot+'"'
	tagstring = ''
	if tag:
	    tagstring = ' and versiontag = "'+tag+'"'
	branchstring = ''
	if branch:
	    branchstring = ' and branch = "'+branch+'"'
	
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo WHERE atom LIKE "%'+keyword+'%"'+slotstring+tagstring+branchstring)
	else:
	    self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo WHERE LOWER(atom) LIKE "%'+keyword.lower()+'%"'+slotstring+tagstring+branchstring)
	return self.cursor.fetchall()

    def searchProvide(self, keyword, slot = None, tag = None, branch = None):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchProvide: called for "+keyword)

	slotstring = ''
	if slot:
	    slotstring = ' and slot = "'+slot+'"'
	tagstring = ''
	if tag:
	    tagstring = ' and versiontag = "'+tag+'"'
	branchstring = ''
	if branch:
	    branchstring = ' and branch = "'+branch+'"'

	self.cursor.execute('SELECT idpackage FROM provide WHERE atom = "'+keyword+'"')
	idpackage = self.cursor.fetchone()
	if not idpackage:
	    return ()
	
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE idpackage = "'+str(idpackage[0])+'"'+slotstring+tagstring+branchstring)
	return self.cursor.fetchall()

    def searchPackagesByDescription(self, keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesByDescription: called for "+keyword)
	self.cursor.execute('SELECT idpackage FROM extrainfo WHERE LOWER(description) LIKE "%'+keyword.lower()+'%"')
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
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesByName: called for "+keyword)
	
	if (self.xcache):
	    cached = self.fetchSearchCache((keyword,sensitive,branch),'searchPackagesByName')
	    if cached != None: return cached
	
	branchstring = ''
	if branch:
	    branchstring = ' and branch = "'+branch+'"'
	
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+keyword+'"'+branchstring)
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+keyword.lower()+'"'+branchstring)
	
	results = self.cursor.fetchall()
	if (self.xcache):
	    self.storeSearchCache((keyword,sensitive,branch),'searchPackagesByName',results)
	return results

    def searchPackagesByNameAndCategory(self, name, category, sensitive = False, branch = None):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesByNameAndCategory: called for name: "+name+" and category: "+category)
	
	if (self.xcache):
	    cached = self.fetchSearchCache((name,category,sensitive,branch),'searchPackagesByNameAndCategory')
	    if cached != None: return cached
	
	# get category id
	idcat = -1
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = "'+category+'"')
	idcat = self.cursor.fetchone()
	if not idcat:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"searchPackagesByNameAndCategory: Category "+category+" not available.")
	    return ()
	else:
	    idcat = idcat[0]

	branchstring = ''
	if branch:
	    branchstring = ' and branch = "'+branch+'"'

	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+name+'" AND idcategory ='+str(idcat)+branchstring)
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+name.lower()+'" AND idcategory ='+str(idcat)+branchstring)
	
	results = self.cursor.fetchall()
	if (self.xcache):
	    self.storeSearchCache((name,category,sensitive,branch),'searchPackagesByNameAndCategory',results)
	return results

    def searchPackagesByNameAndVersionAndCategory(self, name, version, category, branch = None, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesByNameAndVersionAndCategory: called for "+name+" and version "+version+" and category "+category+" | branch "+branch)
	
	if (self.xcache):
	    cached = self.fetchSearchCache((name,version,category,branch,sensitive),'searchPackagesByNameAndVersionAndCategory')
	    if cached != None: return cached
	
	# get category id
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = "'+category+'"')
	idcat = self.cursor.fetchone()
	if not idcat:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"searchPackagesByNameAndVersionAndCategory: Category "+category+" not available.")
	    return ()
	else:
	    idcat = idcat[0]

	branchstring = ''
	if branch:
	    branchstring = ' and branch = "'+branch+'"'

	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+name+'" and version = "'+version+'" and idcategory = '+str(idcat)+branchstring)
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+name.lower()+'" and version = "'+version+'" and idcategory = '+str(idcat)+branchstring)

	results = self.cursor.fetchall()
	if (self.xcache):
	    self.storeSearchCache((name,version,category,branch,sensitive),'searchPackagesByNameAndVersionAndCategory',results)	
	return results

    def listAllPackages(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllPackages: called.")
	self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo')
	return self.cursor.fetchall()

    def listAllCounters(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllCounters: called.")
	self.cursor.execute('SELECT counter,idpackage FROM counters')
	return self.cursor.fetchall()

    def listAllIdpackages(self, branch = None):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllIdpackages: called.")
	branchstring = ''
	if branch:
	    branchstring = ' where branch = "'+branch+'"'
	self.cursor.execute('SELECT idpackage FROM baseinfo'+branchstring)
	return self.fetchall2set(self.cursor.fetchall())

    def listAllDependencies(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllDependencies: called.")
	self.cursor.execute('SELECT * FROM dependenciesreference')
	return self.cursor.fetchall()

    def listAllBranches(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllBranches: called.")
	self.cursor.execute('SELECT branch FROM baseinfo')
	return self.fetchall2set(self.cursor.fetchall())

    def listIdpackageDependencies(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listIdpackageDependencies: called.")
	self.cursor.execute('SELECT iddependency FROM dependencies where idpackage = "'+str(idpackage)+'"')
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
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listBranchPackagesTbz2: called with "+str(branch))
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
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listBranchPackages: called with "+str(branch))
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE branch = "'+str(branch)+'"')
	return self.cursor.fetchall()

    def listAllFiles(self, clean = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllFiles: called.")
	self.cursor.execute('SELECT file FROM content')
	if clean:
	    return self.fetchall2set(self.cursor.fetchall())
	else:
	    return self.fetchall2list(self.cursor.fetchall())

    def listConfigProtectDirectories(self, mask = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listConfigProtectDirectories: called.")
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

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"switchBranch: called for ID "+str(idpackage)+" | branch -> "+str(tobranch))
	
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
	self.cursor.execute('UPDATE baseinfo SET branch = "'+str(tobranch)+'" WHERE idpackage = "'+str(idpackage)+'"')
	self.cursor.execute('UPDATE extrainfo SET download = "'+newdownload+'" WHERE idpackage = "'+str(idpackage)+'"')
	self.commitChanges()
	# clean cursor - NEEDED?
	for row in self.cursor:
	    x = row


########################################################
####
##   Client Database API / but also used by server part
#

    def addPackageToInstalledTable(self, idpackage, repositoryName):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addPackageToInstalledTable: called for "+str(idpackage)+" and repository "+str(repositoryName))
	self.cursor.execute(
		'INSERT into installedtable VALUES '
		'(?,?)'
		, (	idpackage,
			repositoryName,
			)
	)
	self.commitChanges()

    def retrievePackageFromInstalledTable(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrievePackageFromInstalledTable: called. ")
	result = 'Not available'
	try:
	    self.cursor.execute('SELECT repositoryname FROM installedtable WHERE idpackage = "'+str(idpackage)+'"')
	    return self.cursor.fetchone()[0] # it's ok because it's inside try/except
	except:
	    pass
	return result

    def removePackageFromInstalledTable(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removePackageFromInstalledTable: called for "+str(idpackage))
	try:
	    self.cursor.execute('DELETE FROM installedtable WHERE idpackage = '+str(idpackage))
	    self.commitChanges()
	except:
	    self.createInstalledTable()

    def removePackageFromDependsTable(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removePackageFromDependsTable: called for "+str(idpackage))
	try:
	    self.cursor.execute('DELETE FROM dependstable WHERE idpackage = '+str(idpackage))
	    self.commitChanges()
	    return 0
	except:
	    return 1 # need reinit

    def removeDependencyFromDependsTable(self, iddependency):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removeDependencyFromDependsTable: called for "+str(iddependency))
	try:
	    self.cursor.execute('DELETE FROM dependstable WHERE iddependency = '+str(iddependency))
	    self.commitChanges()
	    return 0
	except:
	    return 1 # need reinit

    # temporary/compat functions
    def createDependsTable(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createDependsTable: called.")
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
	sane = True
	try:
	    self.cursor.execute('SELECT iddependency FROM dependstable WHERE iddependency = -1')
	except:
	    return False # table does not exist, please regenerate and re-run
	for row in self.cursor:
	    sane = False
	    break
	return sane

    def createXpakTable(self):
        self.cursor.execute('CREATE TABLE xpakdata ( idpackage INTEGER PRIMARY KEY, data BLOB );')
        self.commitChanges()

    def storeXpakMetadata(self, idpackage, blob):
        dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"storeXpakMetadata: called.")
	self.cursor.execute(
		'INSERT into xpakdata VALUES '
		'(?,?)', ( int(idpackage), buffer(blob), )
        )
        self.commitChanges()

    def retrieveXpakMetadata(self, idpackage):
        dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveXpakMetadata: called.")
        try:
            self.cursor.execute('SELECT data from xpakdata where idpackage = "'+str(idpackage)+'"')
            mydata = self.cursor.fetchone()
            if not mydata:
                return ""
            else:
                return mydata[0]
        except:
            return ""
            pass

    def createCountersTable(self):
        dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createCountersTable: called.")
        self.cursor.execute('DROP TABLE IF EXISTS counters;')
        self.cursor.execute('CREATE TABLE counters ( counter INTEGER PRIMARY KEY, idpackage INTEGER );')
        self.commitChanges()

    def createContentIndex(self):
        self.cursor.execute('CREATE INDEX IF NOT EXISTS contentindex ON content ( file )')

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

    #
    # FIXME: remove these when 1.0 will be out
    #
    
    def createSizesTable(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createSizesTable: called.")
	self.cursor.execute('DROP TABLE IF EXISTS sizes;')
	self.cursor.execute('CREATE TABLE sizes ( idpackage INTEGER, size INTEGER );')
	self.commitChanges()

    def createContentTypeColumn(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createContentTypeColumn: called.")
	self.cursor.execute('ALTER TABLE content ADD COLUMN type VARCHAR;')
	self.cursor.execute('UPDATE content SET type = "0"')
	self.commitChanges()

    def createTriggerTable(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createTriggerTable: called.")
	self.cursor.execute('CREATE TABLE triggers ( idpackage INTEGER PRIMARY KEY, data BLOB );')
	self.commitChanges()

    def createEclassesTable(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createEclassesTable: called.")
	self.cursor.execute('DROP TABLE IF EXISTS eclasses;')
	self.cursor.execute('DROP TABLE IF EXISTS eclassesreference;')
	self.cursor.execute('CREATE TABLE eclasses ( idpackage INTEGER, idclass INTEGER );')
	self.cursor.execute('CREATE TABLE eclassesreference ( idclass INTEGER PRIMARY KEY, classname VARCHAR );')
	self.commitChanges()

    def createNeededTable(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createNeededTable: called.")
	self.cursor.execute('DROP TABLE IF EXISTS needed;')
	self.cursor.execute('DROP TABLE IF EXISTS neededreference;')
	self.cursor.execute('CREATE TABLE needed ( idpackage INTEGER, idneeded INTEGER );')
	self.cursor.execute('CREATE TABLE neededreference ( idneeded INTEGER PRIMARY KEY, library VARCHAR );')
	self.commitChanges()
    
    def createSystemPackagesTable(self):
        dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createSystemPackagesTable: called.")
        self.cursor.execute('CREATE TABLE systempackages ( idpackage INTEGER );')
	self.commitChanges()
    
    def createProtectTable(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createProtectTable: called.")
	self.cursor.execute('DROP TABLE IF EXISTS configprotect;')
	self.cursor.execute('DROP TABLE IF EXISTS configprotectmask;')
	self.cursor.execute('DROP TABLE IF EXISTS configprotectreference;')
	self.cursor.execute('CREATE TABLE configprotect ( idpackage INTEGER, idprotect INTEGER );')
	self.cursor.execute('CREATE TABLE configprotectmask ( idpackage INTEGER, idprotect INTEGER );')
	self.cursor.execute('CREATE TABLE configprotectreference ( idprotect INTEGER PRIMARY KEY, protect VARCHAR );')
	self.commitChanges()

    def createInstalledTable(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createInstalledTable: called.")
	self.cursor.execute('DROP TABLE IF EXISTS installedtable;')
	self.cursor.execute('CREATE TABLE installedtable ( idpackage INTEGER, repositoryname VARCHAR );')
	self.commitChanges()

    def addDependRelationToDependsTable(self, iddependency, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addDependRelationToDependsTable: called for iddependency "+str(iddependency)+" and idpackage "+str(idpackage))
	self.cursor.execute(
		'INSERT into dependstable VALUES '
		'(?,?)'
		, (	iddependency,
			idpackage,
			)
	)
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

        # now validate dependstable
        self.sanitizeDependsTable()


########################################################
####
##   Dependency handling functions
#

    '''
       @description: matches the user chosen package name+ver, if possibile, in a single repository
       @input atom: string, atom to match
       @input caseSensitive: bool, should the atom be parsed case sensitive?
       @input matchSlot: string, match atoms with the provided slot
       @input multiMatch: bool, return all the available atoms
       @output: the package id, if found, otherwise -1 plus the status, 0 = ok, 1 = not found, 2 = need more info, 3 = cannot use direction without specifying version
    '''
    def atomMatch(self, atom, caseSensitive = True, matchSlot = None, multiMatch = False, matchBranches = (), matchTag = None):
        if (self.xcache):
            cached = dbCacheStore[etpCache['dbMatch']+self.dbname].get(atom)
            if cached:
		# check if matchSlot and multiMatch were the same
		if (matchSlot == cached['matchSlot']) \
			and (multiMatch == cached['multiMatch']) \
			and (caseSensitive == cached['caseSensitive']) \
			and (matchTag == cached['matchTag']) \
			and (matchBranches == cached['matchBranches']):
	            return cached['result']
	
	# check if tag is provided -> app-foo/foo-1.2.3:SLOT|TAG or app-foo/foo-1.2.3|TAG
	atomTag = entropyTools.dep_gettag(atom)
	atomSlot = entropyTools.dep_getslot(atom)

	atom = entropyTools.remove_tag(atom)
	if (matchTag == None) and (atomTag != None):
	    matchTag = atomTag
	
	# check if slot is provided -> app-foo/foo-1.2.3:SLOT
	atom = entropyTools.remove_slot(atom)
	if (matchSlot == None) and (atomSlot != None):
	    matchSlot = atomSlot

        # check for direction
        strippedAtom = entropyTools.dep_getcpv(atom)
        if atom[-1] == "*":
	    strippedAtom += "*"
        direction = atom[0:len(atom)-len(strippedAtom)]
	
        justname = entropyTools.isjustname(strippedAtom)
        pkgversion = ''
        if (not justname):
	    # strip tag
	    strippedAtom = entropyTools.remove_tag(strippedAtom)
	    
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
	        if atom.split("-")[-1].startswith("t"):
	            matchTag = atom.split("-")[-1]
	
        pkgkey = entropyTools.dep_getkey(strippedAtom)
	splitkey = pkgkey.split("/")
        if (len(splitkey) == 2):
            pkgname = splitkey[1]
            pkgcat = splitkey[0]
        else:
            pkgname = splitkey[0]
	    pkgcat = "null"

        #print dep_getkey(strippedAtom)
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

	    # if it's a PROVIDE, search with searchProvide
	    if (not results) and (mypkgcat == "virtual"):
	        virtuals = self.searchProvide(pkgkey, branch = idx)
		if (virtuals):
		    mypkgname = self.retrieveName(virtuals[0][1])
		    mypkgcat = self.retrieveCategory(virtuals[0][1])
		    results = virtuals

	    # now validate
	    if (not results):
	        #print "results is empty"
	        continue # search into a stabler branch
	
	    elif (len(results) > 1):
	
	        #print "results > 1"
	        # if it's because category differs, it's a problem
	        foundCat = ""
	        cats = set()
	        for result in results:
		    idpackage = result[1]
		    cat = self.retrieveCategory(idpackage)
		    cats.add(cat)
		    if (cat == mypkgcat):
		        foundCat = cat
		        break
	        # if I found something at least...
	        if (not foundCat) and (len(cats) == 1):
		    foundCat = list(cats)[0]
	        if (not foundCat) and (mypkgcat == "null"):
		    # got the issue
		    # gosh, return and complain
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,2
		    return -1,2
	
	        # I can use foundCat
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

        if (foundIDs):
	    # now we have to handle direction
	    if (direction) or (direction == '' and not justname) or (direction == '' and not justname and strippedAtom.endswith("*")):
	        # check if direction is used with justname, in this case, return an error
	        if (justname):
		    #print "justname"
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,3
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
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
			dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,1
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
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
			dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,1
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
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = similarPackages,0
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
		
		    #print newerPackage
		    #print newerPackage[1]
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = newerPackage[0],0
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
		        cmp = entropyTools.compareVersions(pkgversion,dbver)
		        if direction == ">": # the --deep mode should really act on this
		            if (cmp < 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        elif direction == "<":
		            if (cmp > 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        elif direction == ">=": # the --deep mode should really act on this
		            if (cmp <= 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        elif direction == "<=":
		            if (cmp >= 0):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		
		    if (not dbpkginfo):
		        # this version is not available
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
			dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,1
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
			return multiMatchList,0

		    if (not versions):
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
			dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,1
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
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
			dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = similarPackages,0
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
		
		    #print newerPackage
		    #print newerPackage[1]
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = newerPackage[0],0
		    return newerPackage[0],0

	        else:
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,1
		    return -1,1
		
	    else:
	    
	        #print foundIDs
	    
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
		    return multiMatchList,0
		
		if (not versionIDs):
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,1
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
	    
		dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
		dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
		dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = newerPackage[1],0
	        return newerPackage[1],0

        else:
	    # package not found in any branch
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchTag'] = matchTag
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,1
	    return -1,1
	
