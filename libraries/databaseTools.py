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
	dbconn.closeDB()
	print_info(green(" * ")+red("Entropy database initialized."))

    elif (options[0] == "search"):
	mykeywords = options[1:]
	if (len(mykeywords) == 0):
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(302)
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
		if (result[19]):
		    deps = result[19].split()
		    print_info(red("\t Dependencies"))
		    for dep in deps:
			print_info(darkred("\t    # Depends on: ")+dep)
		#print_info(red("\t Blah: ")+result[20]) --> it's a dup of [21]
		if (result[21]):
		    rundeps = result[21].split()
		    print_info(red("\t Built with runtime dependencies"))
		    for rundep in rundeps:
			print_info(darkred("\t    # Dependency: ")+rundep)
		if (result[22]):
		    print_info(red("\t Conflicts with"))
		    conflicts = result[22].split()
		    for conflict in conflicts:
			print_info(darkred("\t    # Conflict: ")+conflict)
		print_info(red("\t Entry API: ")+green(result[23]))
		print_info(red("\t Entry revision: ")+str(result[24]))
		#print result
	print
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
	self.connection.commit()

    def discardChanges(self):
	self.connection.rollback()

    # never use this unless you know what you're doing
    def initializeDatabase(self):
	self.cursor.execute(etpSQLInit)
	self.commitChanges()

    # this function manages the submitted package
    # if it does not exist, it fires up addPackage
    # otherwise it fires up updatePackage
    def handlePackage(self,etpData):
	if (not isPackageAvailable(etpData['category']+"/"+etpData['name']+"-"+etpData['version'])):
	    self.addPackage(etpData)
	else:
	    self.updatePackage(etpData)

    def addPackage(self,etpData, revision = 0):
	self.cursor.execute(
		'INSERT into etpData VALUES '
		'(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
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

    # Update already available atom in db
    # returns True,revision if the package has been updated
    # returns False,revision if not
    def updatePackage(self,etpData):
	# check if the data correspond
	# if not, update, else drop
	curRevision = dbconn.retrievePackageVar(etpData['category']+"/"+etpData['name']+"-"+etpData['version'],"revision")
	oldPkgInfo = retrievePackageInfo(etpData['category']+"/"+etpData['name']+"-"+etpData['version'])
	if etpData != oldPkgInfo:
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