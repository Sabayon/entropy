#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy Database Interface

    Copyright (C) 2007 Fabio Erculiani

    This program is free software; you can entropyTools.redistribute it and/or modify
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
from pysqlite2 import dbapi2 as sqlite
#import commands
#import re
import os
import sys
import string

# TIP OF THE DAY:
# never nest closeDB() and re-init inside a loop !!!!!!!!!!!! NEVER !

def database(options):
    if len(options) == 0:
	entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("Not enough parameters"))
	sys.exit(301)

    if (options[0] == "--initialize"):
	# initialize the database
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Initializing Entropy database..."), back = True)
        # database file: etpConst['etpdatabasefilepath']
        if os.path.isfile(etpConst['etpdatabasefilepath']):
	    entropyTools.print_info(entropyTools.red(" * ")+entropyTools.bold("WARNING")+entropyTools.red(": database file already exists. Overwriting."))
	    rc = entropyTools.askquestion("\n     Do you want to continue ?")
	    if rc == "No":
	        sys.exit(0)
	    os.system("rm -f "+etpConst['etpdatabasefilepath'])

	# fill the database
        dbconn = etpDatabase(readOnly = False, noUpload = True)
	dbconn.initializeDatabase()
	
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Reinitializing Entropy database using Portage database..."))
	from portageTools import getInstalledPackages, quickpkg
	# now run quickpkg for all the packages and then extract data
	installedAtoms, atomsnumber = getInstalledPackages()
	currCounter = 0
	import reagentTools
	for atom in installedAtoms:
	    currCounter += 1
	    entropyTools.print_info(entropyTools.green("  (")+ entropyTools.blue(str(currCounter))+"/"+entropyTools.red(str(atomsnumber))+entropyTools.green(") ")+entropyTools.red("Analyzing ")+entropyTools.bold(atom)+entropyTools.red(" ..."))
	    quickpkg(atom,etpConst['packagestmpdir'])
	    # file is etpConst['packagestmpdir']+"/atomscan/"+pkgnamever.tbz2
	    etpData = reagentTools.extractPkgData(etpConst['packagestmpdir']+"/"+atom.split("/")[1]+".tbz2")
	    # fill the db entry
	    dbconn.addPackage(etpData)
	    os.system("rm -rf "+etpConst['packagestmpdir']+"/"+atom.split("/")[1]+"*")
	
	dbconn.commitChanges()
	dbconn.closeDB()
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Entropy database has been reinitialized using Portage database entries"))

    # used by reagent
    elif (options[0] == "search"):
	mykeywords = options[1:]
	if (len(mykeywords) == 0):
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("Not enough parameters"))
	    sys.exit(302)
	if (not os.path.isfile(etpConst['etpdatabasefilepath'])):
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("Entropy Datbase does not exist"))
	    sys.exit(303)
	# search tool
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Searching ..."))
	# open read only
	dbconn = etpDatabase(True)
	foundCounter = 0
	for mykeyword in mykeywords:
	    results = dbconn.searchPackages(mykeyword)
	    for result in results:
		foundCounter += 1
		print 
		entropyTools.print_info(entropyTools.green(" * ")+entropyTools.bold(result[0]))   # package atom
		entropyTools.print_info(entropyTools.red("\t Name: ")+entropyTools.blue(result[1]))
		entropyTools.print_info(entropyTools.red("\t Installed version: ")+entropyTools.blue(result[2]))
		if (result[3]):
		    entropyTools.print_info(entropyTools.red("\t Description: ")+result[3])
		entropyTools.print_info(entropyTools.red("\t CHOST: ")+entropyTools.blue(result[5]))
		entropyTools.print_info(entropyTools.red("\t CFLAGS: ")+entropyTools.darkred(result[6]))
		entropyTools.print_info(entropyTools.red("\t CXXFLAGS: ")+entropyTools.darkred(result[7]))
		if (result[8]):
		    entropyTools.print_info(entropyTools.red("\t Website: ")+result[8])
		if (result[9]):
		    entropyTools.print_info(entropyTools.red("\t USE Flags: ")+entropyTools.blue(result[9]))
		entropyTools.print_info(entropyTools.red("\t License: ")+entropyTools.bold(result[10]))
		entropyTools.print_info(entropyTools.red("\t Source keywords: ")+entropyTools.darkblue(result[11]))
		entropyTools.print_info(entropyTools.red("\t Binary keywords: ")+entropyTools.green(result[12]))
		entropyTools.print_info(entropyTools.red("\t Package branch: ")+result[13])
		entropyTools.print_info(entropyTools.red("\t Download relative URL: ")+result[14])
		entropyTools.print_info(entropyTools.red("\t Package Checksum: ")+entropyTools.green(result[15]))
		if (result[16]):
		    entropyTools.print_info(entropyTools.red("\t Sources"))
		    sources = result[16].split()
		    for source in sources:
			entropyTools.print_info(entropyTools.darkred("\t    # Source package: ")+entropyTools.yellow(source))
		if (result[17]):
		    entropyTools.print_info(entropyTools.red("\t Slot: ")+entropyTools.yellow(result[17]))
		#entropyTools.print_info(entropyTools.red("\t Blah: ")+result[18]) # I don't need to print mirrorlinks
		if (result[20]):
		    deps = result[20].split()
		    entropyTools.print_info(entropyTools.red("\t Dependencies"))
		    for dep in deps:
			entropyTools.print_info(entropyTools.darkred("\t    # Depends on: ")+dep)
		#entropyTools.print_info(entropyTools.red("\t Blah: ")+result[20]) --> it's a dup of [21]
		if (result[22]):
		    rundeps = result[22].split()
		    entropyTools.print_info(entropyTools.red("\t Built with runtime dependencies"))
		    for rundep in rundeps:
			entropyTools.print_info(entropyTools.darkred("\t    # Dependency: ")+rundep)
		if (result[23]):
		    entropyTools.print_info(entropyTools.red("\t Conflicts with"))
		    conflicts = result[23].split()
		    for conflict in conflicts:
			entropyTools.print_info(entropyTools.darkred("\t    # Conflict: ")+conflict)
		entropyTools.print_info(entropyTools.red("\t Entry API: ")+entropyTools.green(result[24]))
		entropyTools.print_info(entropyTools.red("\t Entry creation date: ")+str(result[25]))
		entropyTools.print_info(entropyTools.red("\t Entry revision: ")+str(result[26]))
		#print result
	dbconn.closeDB()
	if (foundCounter == 0):
	    entropyTools.print_warning(entropyTools.red(" * ")+entropyTools.red("Nothing found."))
	else:
	    print
    
    # used by reagent
    elif (options[0] == "dump-package-info"):
	mypackages = options[1:]
	if (len(mypackages) == 0):
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("Not enough parameters"))
	    sys.exit(302)
	# open read only
	dbconn = etpDatabase(True)
	
	for package in mypackages:
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Searching package ")+entropyTools.bold(package)+entropyTools.red(" ..."))
	    if entropyTools.isjustpkgname(package) or (package.find("/") == -1):
		entropyTools.print_warning(entropyTools.yellow(" * ")+entropyTools.red("Package ")+entropyTools.bold(package)+entropyTools.red(" is not a complete atom."))
		continue
	    # open db connection
	    if (not dbconn.isPackageAvailable(package)):
		# package does not exist in the Entropy database
		entropyTools.print_warning(entropyTools.yellow(" * ")+entropyTools.red("Package ")+entropyTools.bold(package)+entropyTools.red(" does not exist in Entropy database."))
	        continue
	    
	    myEtpData = entropyTools.etpData.copy()
	    
	    # reset
	    for i in myEtpData:
	        myEtpData[i] = ""
	    
	    for i in myEtpData:
		myEtpData[i] = dbconn.retrievePackageVar(package,i)

	    # sort and print
	    etprevision = str(dbconn.retrievePackageVar(package,"revision"))
	    filepath = etpConst['packagestmpdir'] + "/" + dbconn.retrievePackageVar(package,"name") + "-" + dbconn.retrievePackageVar(package,"version")+"-"+"etp"+etprevision+".etp"
	    f = open(filepath,"w")
	    sortList = []
	    for i in myEtpData:
		sortList.append(i)
	    sortList = entropyTools.alphaSorter(sortList)
	    for i in sortList:
		if (myEtpData[i]):
		    f.write(i+": "+myEtpData[i]+"\n")
	    f.flush()
	    f.close()
	    
	    entropyTools.print_info(entropyTools.green("    * ")+entropyTools.red("Dump generated in ")+entropyTools.bold(filepath)+entropyTools.red(" ."))

	dbconn.closeDB()

    # used by reagent
    elif (options[0] == "inject-package-info"):
	if (len(options[1:]) == 0):
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("Not enough parameters"))
	    sys.exit(303)
	mypath = options[1:][0]
	if (not os.path.isfile(mypath)):
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("File does not exist."))
	    sys.exit(303)
	
	# revision is surely bumped
	etpDataOut = entropyTools.parseEtpDump(mypath)
	dbconn = etpDatabase(readOnly = False, noUpload = True)
	updated, revision = dbconn.handlePackage(etpDataOut)
	dbconn.closeDB()

	if (updated) and (revision != 0):
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Package ")+entropyTools.bold(etpDataOut['category']+"/"+etpDataOut['name']+"-"+etpDataOut['version'])+entropyTools.red(" entry has been updated. Revision: ")+entropyTools.bold(str(revision)))
	elif (updated) and (revision == 0):
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Package ")+entropyTools.bold(etpDataOut['category']+"/"+etpDataOut['name']+"-"+etpDataOut['version'])+entropyTools.red(" entry newly created."))
	else:
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Package ")+entropyTools.bold(etpDataOut['category']+"/"+etpDataOut['name']+"-"+etpDataOut['version'])+entropyTools.red(" does not need to be updated. Current revision: ")+entropyTools.bold(str(revision)))
	
	"""
	sortList = []
	for i in etpDataOut:
	    sortList.append(i)
	sortList = entropyTools.alphaSorter(sortList)
	"""
	# print out the changes before doing them?
	
    elif (options[0] == "restore-package-info"):
	mypackages = options[1:]
	if (len(mypackages) == 0):
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("Not enough parameters"))
	    sys.exit(302)
	
	dbconn = etpDatabase(readOnly = False, noUpload = True)
	
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Reinitializing Entropy database entries for the specified applications ..."))
	# now run quickpkg for all the packages and then extract data
	import reagentTools
	for atom in mypackages:
	    if (entropyTools.isjustpkgname(atom)) or (atom.find("/") == -1):
		entropyTools.print_info((entropyTools.red(" * Package ")+entropyTools.bold(atom)+entropyTools.red(" is not a complete atom, skipping ...")))
		continue
	    if (entropyTools.getInstalledAtom("="+atom) is None):
		entropyTools.print_info((entropyTools.red(" * Package ")+entropyTools.bold(atom)+entropyTools.red(" is not installed, skipping ...")))
		continue
	    entropyTools.print_info((entropyTools.red("Restoring entry for ")+entropyTools.bold(atom)+entropyTools.red(" ...")))
	    entropyTools.quickpkg(atom,etpConst['packagestmpdir'])
	    # file is etpConst['packagestmpdir']+"/atomscan/"+pkgnamever.tbz2
	    etpData = reagentTools.extractPkgData(etpConst['packagestmpdir']+"/"+atom.split("/")[1]+".tbz2")
	    # fill the db entry
	    dbconn.removePackage(etpData['category']+"/"+etpData['name']+"-"+etpData['version'])
	    dbconn.addPackage(etpData)
	    entropyTools.print_info((entropyTools.green(" * ")+entropyTools.red(" Successfully restored database information for ")+entropyTools.bold(atom)+entropyTools.red(" .")))
	    os.system("rm -rf "+etpConst['packagestmpdir']+"/"+atom.split("/")[1]+"*")
	
	dbconn.commitChanges()
	dbconn.closeDB()
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Done."))

    elif (options[0] == "create-empty-database"):
	mypath = options[1:]
	if len(mypath) == 0:
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("Not enough parameters"))
	    sys.exit(303)
	if (os.path.dirname(mypath[0]) != '') and (not os.path.isdir(os.path.dirname(mypath[0]))):
	    entropyTools.print_error(entropyTools.green(" * ")+entropyTools.red("Supplied directory does not exist."))
	    sys.exit(304)
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Initializing an empty database file with Entropy structure ..."),back = True)
	connection = sqlite.connect(mypath[0])
	cursor = connection.cursor()
	cursor.execute(etpSQLInitDestroyAll)
	cursor.execute(etpSQLInit)
	connection.commit()
	cursor.close()
	connection.close()
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Entropy database file ")+entropyTools.bold(mypath[0])+entropyTools.red(" successfully initialized."))

    elif (options[0] == "stabilize"):
	myatoms = options[1:]
	if len(myatoms) == 0:
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("Not enough parameters"))
	    sys.exit(303)
	# is world?
	if myatoms[0] == "world":
	    # open db in read only
	    dbconn = etpDatabase(readOnly = True)
	    worldPackages = dbconn.listAllPackages()
	    # This is the list of all the packages available in Entropy
	    print worldPackages
	    dbconn.closeDB()
	
	# filter dups
	myatoms = list(set(myatoms))
	
	print "DEBUG: Proposed atoms: "+str(myatoms)
	


############
# Functions and Classes
#####################################################################################

# this class simply describes the current database status

class databaseStatus:

    def __init__(self):
	self.databaseBumped = False
	self.databaseInfoCached = False
	self.databaseLock = False
	#self.database
	self.databaseDownloadLocl = False
	self.databaseAlreadyTainted = False
	
	if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile']):
	    self.databaseAlreadyTainted = True

    def isDatabaseAlreadyBumped(self):
	return self.databaseBumped

    def isDatabaseAlreadyTainted(self):
	return self.databaseAlreadyTainted

    def setDatabaseTaint(self,bool):
	self.databaseAlreadyTainted = bool

    def setDatabaseBump(self,bool):
	self.databaseBumped = bool

    def setDatabaseLock(self):
	self.databaseLock = True

    def unsetDatabaseLock(self):
	self.databaseLock = False

    def getDatabaseLock(self):
	return self.databaseLock

    def setDatabaseDownloadLock(self):
	self.databaseDownloadLock = True

    def unsetDatabaseDownloadLock(self):
	self.databaseDownloadLock = False

    def getDatabaseDownloadLock(self):
	return self.databaseDownloadLock

class etpDatabase:

    def __init__(self, readOnly = False, noUpload = False):
	
	self.readOnly = readOnly
	self.noUpload = noUpload
	
	if (self.readOnly):
	    # if the database is opened readonly, we don't need to lock the online status
	    # FIXME: add code for locking the table
	    self.connection = sqlite.connect(etpConst['etpdatabasefilepath'])
	    self.cursor = self.connection.cursor()
	    # set the table read only
	    return

	# check if the database is locked REMOTELY
	# FIXME: this does not work
	entropyTools.print_info(entropyTools.red(" * ")+entropyTools.red(" Locking and Sync Entropy database ..."), back = True)
	for uri in etpConst['activatoruploaduris']:
	    ftp = handlerFTP(uri)
	    ftp.setCWD(etpConst['etpurirelativepath'])
	    if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])) and (not os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])):
		import time
		entropyTools.print_info(entropyTools.red(" * ")+entropyTools.bold("WARNING")+entropyTools.red(": online database is already locked. Waiting up to 2 minutes..."), back = True)
		unlocked = False
		for x in range(120):
		    time.sleep(1)
		    if (not ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
			entropyTools.print_info(entropyTools.red(" * ")+entropyTools.bold("HOORAY")+entropyTools.red(": online database has been unlocked. Locking back and syncing..."))
			unlocked = True
			break
		if (unlocked):
		    break

		# time over
		entropyTools.print_info(entropyTools.red(" * ")+entropyTools.bold("ERROR")+entropyTools.red(": online database has not been unlocked. Giving up. Who the hell is working on it? Damn, it's so frustrating for me. I'm a piece of python code with a soul dude!"))
		# FIXME show the lock status

		entropyTools.print_info(entropyTools.yellow(" * ")+entropyTools.green("Mirrors status table:"))
		dbstatus = entropyTools.getMirrorsLock()
		for db in dbstatus:
		    if (db[1]):
	        	db[1] = entropyTools.red("Locked")
	    	    else:
	        	db[1] = entropyTools.green("Unlocked")
	    	    if (db[2]):
	        	db[2] = entropyTools.red("Locked")
	            else:
	        	db[2] = entropyTools.green("Unlocked")
	    	    entropyTools.print_info(entropyTools.bold("\t"+entropyTools.extractFTPHostFromUri(db[0])+": ")+entropyTools.red("[")+entropyTools.yellow("DATABASE: ")+db[1]+entropyTools.red("] [")+entropyTools.yellow("DOWNLOAD: ")+db[2]+entropyTools.red("]"))
	    
	        ftp.closeFTPConnection()
	        sys.exit(320)

		
	# if we arrive here, it is because all the mirrors are unlocked so... damn, LOCK!
	entropyTools.lockDatabases(True)
	
	# ok done... now sync the new db, if needed
	entropyTools.syncRemoteDatabases(self.noUpload)
	
	self.connection = sqlite.connect(etpConst['etpdatabasefilepath'])
	self.cursor = self.connection.cursor()

    def closeDB(self):
	
	# if the class is opened readOnly, close and forget
	if (self.readOnly):
	    self.cursor.close()
	    self.connection.close()
	    return
	
	# FIXME verify all this shit, for now it works...
	if (entropyTools.dbStatus.isDatabaseAlreadyTainted()) and (not entropyTools.dbStatus.isDatabaseAlreadyBumped()):
	    # bump revision, setting DatabaseBump causes the session to just bump once
	    entropyTools.dbStatus.setDatabaseBump(True)
	    self.revisionBump()
	
	if (not entropyTools.dbStatus.isDatabaseAlreadyTainted()):
	    # we can unlock it, no changes were made
	    entropyTools.lockDatabases(False)
	else:
	    entropyTools.print_info(entropyTools.yellow(" * ")+entropyTools.green(" Mirrors have not been unlocked. Run activator."))
	
	self.cursor.close()
	self.connection.close()

    def commitChanges(self):
	if (not self.readOnly):
	    self.connection.commit()
	    self.taintDatabase()
	else:
	    self.connection.rollback() # is it ok?

    def taintDatabase(self):
	# taint the database status
	f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile'],"w")
	f.write(etpConst['currentarch']+" database tainted\n")
	f.flush()
	f.close()
	entropyTools.dbStatus.setDatabaseTaint(True)

    def untaintDatabase(self):
	entropyTools.dbStatus.setDatabaseTaint(False)
	# untaint the database status
	os.system("rm -f "+etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile'])

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
	self.cursor.execute(etpSQLInitDestroyAll)
	self.cursor.execute(etpSQLInit)
	self.commitChanges()

    # this function manages the submitted package
    # if it does not exist, it fires up addPackage
    # otherwise it fires up updatePackage
    def handlePackage(self,etpData,forceBump = False):
	if (not self.isPackageAvailable(etpData['category']+"/"+etpData['name']+"-"+etpData['version'])):
	    update, revision = self.addPackage(etpData)
	else:
	    update, revision = self.updatePackage(etpData,forceBump)
	return update, revision

    def addPackage(self,etpData, revision = 0):
	self.cursor.execute(
		'INSERT into etpData VALUES '
		'(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
		, (	etpData['category']+"/"+etpData['name']+"-"+etpData['version'],
			etpData['name'],
			etpData['version'],
			etpData['description'],
			etpData['category'],
			etpData['chost'],
			etpData['cflags'],
			etpData['cxxflags'],
			etpData['homepage'],
			etpData['useflags'],
			etpData['license'],
			etpData['keywords'],
			etpData['binkeywords'],
			etpData['branch'],
			etpData['download'],
			etpData['digest'],
			etpData['sources'],
			etpData['slot'],
			etpData['content'],
			etpData['mirrorlinks'],
			etpData['dependencies'],
			etpData['rundependencies'],
			etpData['rundependenciesXT'],
			etpData['conflicts'],
			etpData['etpapi'],
			etpData['datecreation'],
			revision,
			)
	)
	self.commitChanges()
	return True,revision

    # Update already available atom in db
    # returns True,revision if the package has been updated
    # returns False,revision if not
    def updatePackage(self,etpData,forceBump = False):
	# check if the data correspond
	# if not, update, else drop
	curRevision = self.retrievePackageVar(etpData['category']+"/"+etpData['name']+"-"+etpData['version'],"revision")
	# FIXME: I don't know if this works
	oldPkgInfo = etpData['category']+"/"+etpData['name']+"-"+etpData['version']
	rc = self.comparePackagesData(etpData,oldPkgInfo)
	if (not rc) or (forceBump):
	    # update !
	    curRevision += 1
	    # remove the table
	    self.removePackage(etpData['category']+"/"+etpData['name']+"-"+etpData['version'])
	    # readd table
	    self.addPackage(etpData,curRevision)
	    self.commitChanges()
	    return True, curRevision
	else:
	    return False,curRevision

    # You must provide the full atom to this function
    def removePackage(self,key):
	key = entropyTools.removePackageOperators(key)
	self.cursor.execute('DELETE FROM etpData WHERE atom = "'+key+'"')
	self.commitChanges()

    # WARNING: this function must be kept in sync with Entropy database schema
    # returns True if equal
    # returns False if not
    def comparePackagesData(self,etpData,dbPkgInfo):
	
	myEtpData = etpData.copy()
	
	# reset before using the myEtpData dictionary
	for i in myEtpData:
	    myEtpData[i] = ""

	# fill content
	for i in myEtpData:
	    myEtpData[i] = self.retrievePackageVar(dbPkgInfo,i)
	
	for i in etpData:
	    if etpData[i] != myEtpData[i]:
		return False
	
	return True

    # You must provide the full atom to this function
    def retrievePackageInfo(self,pkgkey):
	pkgkey = entropyTools.removePackageOperators(pkgkey)
	result = []
	self.cursor.execute('SELECT * FROM etpData WHERE atom LIKE "'+pkgkey+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    # You must provide the full atom to this function
    def retrievePackageVar(self,pkgkey,pkgvar):
	pkgkey = entropyTools.removePackageOperators(pkgkey)
	result = []
	self.cursor.execute('SELECT '+pkgvar+' FROM etpData WHERE atom LIKE "'+pkgkey+'"')
	for row in self.cursor:
	    result.append(row)
	return result[0][0]

    # You must provide the full atom to this function
    def isPackageAvailable(self,pkgkey):
	pkgkey = entropyTools.removePackageOperators(pkgkey)
	result = []
	self.cursor.execute('SELECT * FROM etpData WHERE atom LIKE "'+pkgkey+'"')
	for row in self.cursor:
	    result.append(row)
	if result == []:
	    return False
	return True

    def searchPackages(self,keyword):
	result = []
	self.cursor.execute('SELECT * FROM etpData WHERE atom LIKE "%'+keyword+'%"')
	for row in self.cursor:
	    result.append(row)
	return result

    def listAllPackages(self):
	result = []
	self.cursor.execute('SELECT * FROM etpData')
	for row in self.cursor:
	    result.append(row[0])
	return result

    def listStablePackages(self):
	result = []
	self.cursor.execute('SELECT * FROM etpData WHERE branch = "stable"')
	for row in self.cursor:
	    result.append(row[0])
	return result

    def listUnstablePackages(self):
	result = []
	self.cursor.execute('SELECT * FROM etpData WHERE branch = "unstable"')
	for row in self.cursor:
	    result.append(row[0])
	return result

# ------ BEGIN: activator tools ------

class handlerFTP:

    # ftp://linuxsabayon:asdasd@silk.dreamhost.com/sabayon.org
    # this must be run before calling the other functions
    def __init__(self, ftpuri):
	
	from ftplib import FTP
	
	self.ftpuri = ftpuri
	
	self.ftphost = entropyTools.extractFTPHostFromUri(self.ftpuri)
	
	self.ftpuser = ftpuri.split("ftp://")[len(ftpuri.split("ftp://"))-1].split(":")[0]
	if (self.ftpuser == ""):
	    self.ftpuser = "anonymous@"
	    self.ftppassword = "anonymous"
	else:
	    self.ftppassword = ftpuri.split("@")[:len(ftpuri.split("@"))-1]
	    if len(self.ftppassword) > 1:
		import string
		self.ftppassword = string.join(self.ftppassword,"@")
		self.ftppassword = self.ftppassword.split(":")[len(self.ftppassword.split(":"))-1]
		if (self.ftppassword == ""):
		    self.ftppassword = "anonymous"
	    else:
		self.ftppassword = self.ftppassword[0]
		self.ftppassword = self.ftppassword.split(":")[len(self.ftppassword.split(":"))-1]
		if (self.ftppassword == ""):
		    self.ftppassword = "anonymous"
	
	self.ftpport = ftpuri.split(":")[len(ftpuri.split(":"))-1]
	try:
	    self.ftpport = int(self.ftpport)
	except:
	    self.ftpport = 21
	
	self.ftpdir = ftpuri.split("ftp://")[len(ftpuri.split("ftp://"))-1]
	self.ftpdir = self.ftpdir.split("/")[len(self.ftpdir.split("/"))-1]
	self.ftpdir = self.ftpdir.split(":")[0]
	if self.ftpdir.endswith("/"):
	    self.ftpdir = self.ftpdir[:len(self.ftpdir)-1]

	self.ftpconn = FTP(self.ftphost)
	self.ftpconn.login(self.ftpuser,self.ftppassword)
	# change to our dir
	self.ftpconn.cwd(self.ftpdir)
	self.currentdir = self.ftpdir


    # this can be used in case of exceptions
    def reconnectHost(self):
	self.ftpconn = FTP(self.ftphost)
	self.ftpconn.login(self.ftpuser,self.ftppassword)
	self.ftpconn.cwd(self.currentdir)

    def getFTPHost(self):
	return self.ftphost

    def getFTPPort(self):
	return self.ftpport

    def getFTPDir(self):
	return self.ftpdir

    def getCWD(self):
	return self.ftpconn.pwd()

    def setCWD(self,dir):
	self.ftpconn.cwd(dir)
	self.currentdir = dir

    def getFileMtime(self,path):
	rc = self.ftpconn.sendcmd("mdtm "+path)
	return rc.split()[len(rc.split())-1]

    def spawnFTPCommand(self,cmd):
	rc = self.ftpconn.sendcmd(cmd)
	return rc

    # list files and directory of a FTP
    # @returns a list
    def listFTPdir(self):
	# directory is: self.ftpdir
	try:
	    rc = self.ftpconn.nlst()
	    _rc = []
	    for i in rc:
		_rc.append(i.split("/")[len(i.split("/"))-1])
	    rc = _rc
	except:
	    return []
	return rc

    # list if the file is available
    # @returns True or False
    def isFileAvailable(self,filename):
	# directory is: self.ftpdir
	try:
	    rc = self.ftpconn.nlst()
	    _rc = []
	    for i in rc:
		_rc.append(i.split("/")[len(i.split("/"))-1])
	    rc = _rc
	    for i in rc:
		if i == filename:
		    return True
	    return False
	except:
	    return False

    def deleteFile(self,file):
	try:
	    rc = self.ftpconn.delete(file)
	    if rc.startswith("250"):
		return True
	    else:
		return False
	except:
	    return False

    def uploadFile(self,file,ascii = False):
	for i in range(10): # ten tries
	    f = open(file)
	    filename = file.split("/")[len(file.split("/"))-1]
	    try:
		if (ascii):
		    rc = self.ftpconn.storlines("STOR "+filename+".tmp",f)
		else:
		    rc = self.ftpconn.storbinary("STOR "+filename+".tmp",f)
		# now we can rename the file with its original name
		self.renameFile(filename+".tmp",filename)
	        return rc
	    except socket.error: # connection reset by peer
		entropyTools.print_info(entropyTools.red("Upload issue, retrying..."))
		self.reconnectHost() # reconnect
		self.deleteFile(filename)
		self.deleteFile(filename+".tmp")
		f.close()
		continue

    def downloadFile(self,filepath,downloaddir,ascii = False):
	file = filepath.split("/")[len(filepath.split("/"))-1]
	if (not ascii):
	    f = open(downloaddir+"/"+file,"wb")
	    rc = self.ftpconn.retrbinary('RETR '+file,f.write)
	else:
	    f = open(downloaddir+"/"+file,"w")
	    rc = self.ftpconn.retrlines('RETR '+file,f.write)
	f.flush()
	f.close()
	return rc

    # also used to move files
    # FIXME: beautify !
    def renameFile(self,fromfile,tofile):
	self.ftpconn.rename(fromfile,tofile)

    # not supported by dreamhost.com
    def getFileSize(self,file):
	return self.ftpconn.size(file)
    
    def getFileSizeCompat(self,file):
	list = getRoughList()
	for item in list:
	    if item.find(file) != -1:
		# extact the size
		return item.split()[4]
	return ""

    def bufferizer(self,buf):
	self.FTPbuffer.append(buf)

    def getRoughList(self):
	self.FTPbuffer = []
	self.ftpconn.dir(self.bufferizer)
	return self.FTPbuffer

    def closeFTPConnection(self):
	self.ftpconn.quit()

# ------ END: activator tools ------

