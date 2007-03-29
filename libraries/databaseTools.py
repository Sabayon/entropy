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
from entropyTools import *
from pysqlite2 import dbapi2 as sqlite
#import commands
#import re
import os
import sys


def database(options):
    if len(options) == 0:
	print_error(yellow(" * ")+red("Not enough parameters"))
	sys.exit(301)

    if (options[0] == "--initialize"):
	# initialize the database
	print_info(green(" * ")+red("Initializing Entropy database..."), back = True)
        # database file: etpConst['etpdatabasefile']
        if os.path.isfile(etpConst['etpdatabasefile']):
	    print_info(red(" * ")+bold("WARNING")+red(": database file already exists. Overwriting."))
	    rc = askquestion("\n     Do you want to continue ?")
	    if rc == "No":
	        sys.exit(0)
	    os.system("rm -f "+etpConst['etpdatabasefile'])

	# fill the database
        dbconn = etpDatabase()
	dbconn.initializeDatabase()
	
	print_info(green(" * ")+red("Reinitializing Entropy database using Portage database..."))
	# now run quickpkg for all the packages and then extract data
	installedAtoms, atomsnumber = getInstalledPackages()
	currCounter = 0
	import reagentTools
	for atom in installedAtoms:
	    currCounter += 1
	    print_info(green("  (")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(atom)+red(" ..."))
	    quickpkg(atom,etpConst['packagestmpdir'])
	    # file is etpConst['packagestmpdir']+"/atomscan/"+pkgnamever.tbz2
	    etpData = reagentTools.extractPkgData(etpConst['packagestmpdir']+"/"+atom.split("/")[1]+".tbz2")
	    # fill the db entry
	    dbconn.addPackage(etpData)
	    os.system("rm -rf "+etpConst['packagestmpdir']+"/"+atom.split("/")[1]+"*")
	    dbconn.commitChanges()
	dbconn.commitChanges()
	dbconn.closeDB()
	print_info(green(" * ")+red("Entropy database has been reinitialized using Portage database entries"))


    elif (options[0] == "search"):
	mykeywords = options[1:]
	if (len(mykeywords) == 0):
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(302)
	if (not os.path.isfile(etpConst['etpdatabasefile'])):
	    print_error(yellow(" * ")+red("Entropy Datbase does not exist"))
	    sys.exit(303)
	# search tool
	print_info(green(" * ")+red("Searching inside the Entropy database..."))
	dbconn = etpDatabase()
	for mykeyword in mykeywords:
	    results = dbconn.searchPackages(mykeyword)
	    for result in results:
		print 
		print_info(green(" * ")+bold(result[0]))   # package atom
		print_info(red("\t Name: ")+blue(result[1]))
		print_info(red("\t Installed version: ")+blue(result[2]))
		if (result[3]):
		    print_info(red("\t Description: ")+result[3])
		print_info(red("\t CHOST: ")+blue(result[5]))
		print_info(red("\t CFLAGS: ")+darkred(result[6]))
		print_info(red("\t CXXFLAGS: ")+darkred(result[7]))
		if (result[8]):
		    print_info(red("\t Website: ")+result[8])
		print_info(red("\t USE Flags: ")+blue(result[9]))
		print_info(red("\t License: ")+bold(result[10]))
		print_info(red("\t Source keywords: ")+darkblue(result[11]))
		print_info(red("\t Binary keywords: ")+green(result[12]))
		print_info(red("\t Package path: ")+result[13])
		print_info(red("\t Download relative URL: ")+result[14])
		print_info(red("\t Package Checksum: ")+green(result[15]))
		if (result[16]):
		    print_info(red("\t Sources"))
		    sources = result[16].split()
		    for source in sources:
			print_info(darkred("\t    # Source package: ")+yellow(source))
		if (result[17]):
		    print_info(red("\t Slot: ")+yellow(result[17]))
		#print_info(red("\t Blah: ")+result[18]) # I don't need to print mirrorlinks
		if (result[20]):
		    deps = result[20].split()
		    print_info(red("\t Dependencies"))
		    for dep in deps:
			print_info(darkred("\t    # Depends on: ")+dep)
		#print_info(red("\t Blah: ")+result[20]) --> it's a dup of [21]
		if (result[22]):
		    rundeps = result[22].split()
		    print_info(red("\t Built with runtime dependencies"))
		    for rundep in rundeps:
			print_info(darkred("\t    # Dependency: ")+rundep)
		if (result[23]):
		    print_info(red("\t Conflicts with"))
		    conflicts = result[23].split()
		    for conflict in conflicts:
			print_info(darkred("\t    # Conflict: ")+conflict)
		print_info(red("\t Entry API: ")+green(result[24]))
		print_info(red("\t Entry revision: ")+str(result[25]))
		#print result
	print
	dbconn.closeDB()

    elif (options[0] == "dump-package-info"):
	mypackages = options[1:]
	if (len(mypackages) == 0):
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(302)
	for package in mypackages:
	    print_info(green(" * ")+red("Searching package ")+bold(package)+red(" ..."))
	    if isjustname(package) or (package.find("/") == -1):
		print_warning(yellow(" * ")+red("Package ")+bold(package)+red(" is not a complete atom."))
		continue
	    # open db connection
	    dbconn = etpDatabase()
	    if (not dbconn.isPackageAvailable(package)):
		# package does not exist in the Entropy database
		print_warning(yellow(" * ")+red("Package ")+bold(package)+red(" does not exist in Entropy database."))
		dbconn.closeDB()
	        continue
	    etpData = dbconn.retrievePackageInfo(package)
	    print etpData
	    dbconn.closeDB()


############
# Functions
#####################################################################################



class etpDatabase:

    def __init__(self):
	# initialization open the database connection
	self.connection = sqlite.connect(etpConst['etpdatabasefile'])
	self.cursor = self.connection.cursor()

    def closeDB(self):
	self.cursor.close()
	self.connection.close()

    def commitChanges(self):
	self.taintDatabase()
	self.connection.commit()

    def taintDatabase(self):
	# taint the database status
	f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile'],"w")
	f.write(etpConst['currentarch']+" database tainted\n")
	f.flush()
	f.close()

    def untaintDatabase(self):
	# untaint the database status
	os.system("rm -f "+etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile'])

    def discardChanges(self):
	self.connection.rollback()

    # never use this unless you know what you're doing
    def initializeDatabase(self):
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
		'(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
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
			etpData['packagepath'],
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
			revision
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
	key = removePackageOperators(key)
	self.cursor.execute('DELETE FROM etpData WHERE atom = "'+key+'"')
	self.commitChanges()
	return result

    # WARNING: this function must be kept in sync with Entropy database schema
    # returns True if equal
    # returns False if not
    def comparePackagesData(self,etpData,dbPkgInfo):
	
	# reset before using the tmpEtpData dictionary
	for i in tmpEtpData:
	    tmpEtpData[i] = ""

	# fill content
	for i in tmpEtpData:
	    tmpEtpData[i] = self.retrievePackageVar(dbPkgInfo,i)

	"""
	oldEtpData['name'] = self.retrievePackageVar(dbPkgInfo,"name")
	oldEtpData['version'] = self.retrievePackageVar(dbPkgInfo,"version")
	oldEtpData['description'] = self.retrievePackageVar(dbPkgInfo,"description")
	oldEtpData['category'] = self.retrievePackageVar(dbPkgInfo,"category")
	oldEtpData['chost'] = self.retrievePackageVar(dbPkgInfo,"chost")
	oldEtpData['cflags'] = self.retrievePackageVar(dbPkgInfo,"cflags")
	oldEtpData['cxxflags'] = self.retrievePackageVar(dbPkgInfo,"cxxflags")
	oldEtpData['homepage'] = self.retrievePackageVar(dbPkgInfo,"homepage")
	oldEtpData['useflags'] = self.retrievePackageVar(dbPkgInfo,"useflags")
	oldEtpData['license'] = self.retrievePackageVar(dbPkgInfo,"license")
	oldEtpData['keywords'] = self.retrievePackageVar(dbPkgInfo,"keywords")
	oldEtpData['binkeywords'] = self.retrievePackageVar(dbPkgInfo,"binkeywords")
	oldEtpData['packagepath'] = self.retrievePackageVar(dbPkgInfo,"packagepath")
	oldEtpData['download'] = self.retrievePackageVar(dbPkgInfo,"download")
	oldEtpData['digest'] = self.retrievePackageVar(dbPkgInfo,"digest")
	oldEtpData['sources'] = self.retrievePackageVar(dbPkgInfo,"sources")
	oldEtpData['slot'] = self.retrievePackageVar(dbPkgInfo,"slot")
	oldEtpData['content'] = self.retrievePackageVar(dbPkgInfo,"content")
	oldEtpData['mirrorlinks'] = self.retrievePackageVar(dbPkgInfo,"mirrorlinks")
	oldEtpData['dependencies'] = self.retrievePackageVar(dbPkgInfo,"dependencies")
	oldEtpData['rundependencies'] = self.retrievePackageVar(dbPkgInfo,"rundependencies")
	oldEtpData['rundependenciesXT'] = self.retrievePackageVar(dbPkgInfo,"rundependenciesXT")
	oldEtpData['conflicts'] = self.retrievePackageVar(dbPkgInfo,"conflicts")
	oldEtpData['etpapi'] = self.retrievePackageVar(dbPkgInfo,"etpapi")
	"""

	for i in etpData:
	    if etpData[i] != tmpEtpData[i]:
		return False
	
	return True

    # You must provide the full atom to this function
    def retrievePackageInfo(self,pkgkey):
	pkgkey = removePackageOperators(pkgkey)
	result = []
	self.cursor.execute('SELECT * FROM etpData WHERE atom LIKE "'+pkgkey+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    # You must provide the full atom to this function
    def retrievePackageVar(self,pkgkey,pkgvar):
	pkgkey = removePackageOperators(pkgkey)
	result = []
	self.cursor.execute('SELECT '+pkgvar+' FROM etpData WHERE atom LIKE "'+pkgkey+'"')
	for row in self.cursor:
	    result.append(row)
	return result[0][0]

    # You must provide the full atom to this function
    def isPackageAvailable(self,pkgkey):
	pkgkey = removePackageOperators(pkgkey)
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