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
import mirrorTools
from pysqlite2 import dbapi2 as sqlite
#import commands
#import re
import os
import sys
import string

# load the log file
import logTools
log = logTools.LogFile(level=2,filename = etpConst['databaselogfile'])

# TIP OF THE DAY:
# never nest closeDB() and re-init inside a loop !!!!!!!!!!!! NEVER !

def database(options):
    if len(options) == 0:
	entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("Not enough parameters"))
	sys.exit(301)

    if (options[0] == "--initialize"):
	
	# do some check, print some warnings
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Initializing Entropy database..."), back = True)
	log.log(0,"[DB OP] Called database --initialize")
        # database file: etpConst['etpdatabasefilepath']
        if os.path.isfile(etpConst['etpdatabasefilepath']):
	    entropyTools.print_info(entropyTools.red(" * ")+entropyTools.bold("WARNING")+entropyTools.red(": database file already exists. Overwriting."))
	    rc = entropyTools.askquestion("\n     Do you want to continue ?")
	    if rc == "No":
	        sys.exit(0)
	    os.system("rm -f "+etpConst['etpdatabasefilepath'])
	    log.log(0,"[DB OP] Removed old database file")

	# initialize the database
	log.log(0,"[DB OP] Connecting to the database")
        dbconn = etpDatabase(readOnly = False, noUpload = True)
	dbconn.initializeDatabase()
	
	# sync packages directory
	log.log(0,"Syncing binary packages")
	import activatorTools
	activatorTools.packages(["sync","--ask"])
	
	# now fill the database
	pkglist = os.listdir(etpConst['packagesbindir'])

	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Reinitializing Entropy database using Packages in the repository ..."))
	log.log(0,"[DB OP] Preparing to start reinitialization")
	currCounter = 0
	atomsnumber = len(pkglist)
	import reagentTools
	for pkg in pkglist:
	    log.log(0,"[DB OP] Analyzing "+str(pkg))
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Analyzing: ")+entropyTools.bold(pkg), back = True)
	    currCounter += 1
	    entropyTools.print_info(entropyTools.green("  (")+ entropyTools.blue(str(currCounter))+"/"+entropyTools.red(str(atomsnumber))+entropyTools.green(") ")+entropyTools.red("Analyzing ")+entropyTools.bold(pkg)+entropyTools.red(" ..."))
	    etpData = reagentTools.extractPkgData(etpConst['packagesbindir']+"/"+pkg)
	    log.log(3,"[DB OP] etpData status (should be properly filled now):")
	    for i in etpData:
		log.log(3,i+": "+etpData[i])
		
	    # remove shait
	    os.system("rm -rf "+etpConst['packagestmpdir']+"/"+pkg)
	    # fill the db entry
	    log.log(0,"[DB OP] Launching etpDatabase.addPackage()")
	    dbconn.addPackage(etpData)
	    dbconn.commitChanges()
	
	log.close()
	dbconn.closeDB()
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Entropy database has been reinitialized using binary packages available"))

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
		entropyTools.print_info(entropyTools.red("\t Entry creation date: ")+str(entropyTools.convertUnixTimeToHumanTime(int(result[25]))))
		if (result[26]):
		    entropyTools.print_info(entropyTools.red("\t Built with needed libraries"))
		    libs = result[26].split()
		    for lib in libs:
			entropyTools.print_info(entropyTools.darkred("\t    # Needed library: ")+lib)
		entropyTools.print_info(entropyTools.red("\t Entry revision: ")+str(result[27]))
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

	# sync packages directory
	import activatorTools
	activatorTools.packages(["sync","--ask"])

	dbconn = etpDatabase(readOnly = False, noUpload = True)
	
	# validate entries
	_mypackages = []
	for pkg in mypackages:
	    if (dbconn.isPackageAvailable(pkg)):
		_mypackages.append(pkg)
	mypackages = _mypackages
	
	if len(mypackages) == 0:
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("No valid package found. You must specify category/atom-version."))
	    sys.exit(303)
	
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Reinitializing Entropy database using Packages in the repository ..."))
	
	# get the file list
	pkglist = []
	for pkg in mypackages:
	    pkgfile = dbconn.retrievePackageVar(pkg,"download")
	    pkgfile = pkgfile.split("/")[len(pkgfile.split("/"))-1]
	    pkglist.append(pkgfile)
	
	# validate files
	_pkglist = []
	for file in pkglist:
	    if (not os.path.isfile(etpConst['packagesbindir']+"/"+file)):
	        entropyTools.print_info(entropyTools.yellow(" * ")+entropyTools.red("Attention: ")+entropyTools.bold(file)+entropyTools.red(" does not exist anymore."))
	    else:
		_pkglist.append(file)
	pkglist = _pkglist
	
	currCounter = 0
	atomsnumber = len(pkglist)
	import reagentTools
	for pkg in pkglist:
	    
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Analyzing: ")+entropyTools.bold(pkg), back = True)
	    currCounter += 1
	    entropyTools.print_info(entropyTools.green("  (")+ entropyTools.blue(str(currCounter))+"/"+entropyTools.red(str(atomsnumber))+entropyTools.green(") ")+entropyTools.red("Analyzing ")+entropyTools.bold(pkg)+entropyTools.red(" ..."))
	    etpData = reagentTools.extractPkgData(etpConst['packagesbindir']+"/"+pkg)
	    # remove shait
	    os.system("rm -rf "+etpConst['packagestmpdir']+"/"+pkg)
	    # fill the db entry
	    dbconn.handlePackage(etpData)
	    dbconn.commitChanges()

	dbconn.commitChanges()
	dbconn.closeDB()
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Successfully restored database information for the chosen packages."))


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

    elif (options[0] == "stabilize") or (options[0] == "unstabilize"):

	if options[0] == "stabilize":
	    stable = True
	else:
	    stable = False
	
	if (stable):
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Collecting packages that would be marked stable ..."), back = True)
	else:
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Collecting packages that would be marked unstable ..."), back = True)
	
	myatoms = options[1:]
	if len(myatoms) == 0:
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("Not enough parameters"))
	    sys.exit(303)
	# is world?
	if myatoms[0] == "world":
	    # open db in read only
	    dbconn = etpDatabase(readOnly = True)
	    pkglist = dbconn.listAllPackages()
	    # This is the list of all the packages available in Entropy
	    dbconn.closeDB()
	else:
	    pkglist = []
	    for atom in myatoms:
		# validate atom
		dbconn = etpDatabase(readOnly = True)
		pkg = dbconn.searchPackages(atom)
		try:
		    for x in pkg:
		        pkglist.append(x[0])
		except:
		    pass
	
	# filter dups
	pkglist = list(set(pkglist))
	# check if atoms were found
	if len(pkglist) == 0:
	    print
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("No packages found."))
	    sys.exit(303)
	
	# show what would be done
	if (stable):
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("These are the packages that would be marked stable:"))
	else:
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("These are the packages that would be marked unstable:"))

	for pkg in pkglist:
	    entropyTools.print_info(entropyTools.red("\t (*) ")+entropyTools.bold(pkg))
	
	# ask to continue
	rc = entropyTools.askquestion("     Would you like to continue ?")
	if rc == "No":
	    sys.exit(0)
	
	# now mark them as stable
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Marking selected packages ..."))

	# open db
	dbconn = etpDatabase(readOnly = False, noUpload = True)
	for pkg in pkglist:
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Marking package: ")+entropyTools.bold(pkg)+entropyTools.red(" ..."), back = True)
	    dbconn.stabilizePackage(pkg,stable)
	dbconn.commitChanges()
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("All the selected packages have been marked as requested. Have fun."))
	dbconn.closeDB()

    # FIXME: not working function... remove?
    elif (options[0] == "orphans"):
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Collecting files in database..."))
	# FIXME: complete this!
	dbconn = etpDatabase(readOnly = True)
	pkglist = dbconn.listAllPackages()
	
	filesList = []
	for pkg in pkglist:
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Collecting files in package: ")+entropyTools.bold(pkg)+entropyTools.red(" ..."), back = True)
	    files = dbconn.retrievePackageVar(pkg,"content").split()
	    for file in files:
	        filesList.append(file)
	
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Database data collected."))
	dbconn.closeDB()
	
	# remove dups
	filesList = list(set(filesList))
	
	# now list all the files in the computer
	import commands
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Collecting files on the system ..."), back = True)
	rootFilesList = commands.getoutput("find /").split("\n")
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("System data collected."))
	
	# remove dups
	rootFilesList = list(set(rootFilesList))
	
	allowedDirs = [
		"/bin",
		"/etc",
		"/lib",
		"/lib32",
		"/lib64",
		"/emul",
		"/opt",
		"/sbin",
		"/usr",
	]
	
	# remove unwanted files
	_filesList = []
	for file in filesList:
	    for allowedDir in allowedDirs:
		if file.startswith(allowedDir):
		    _filesList.append(file)
	filesList = _filesList
	del _filesList

	_rootFilesList = []
	for file in rootFilesList:
	    for allowedDir in allowedDirs:
		if file.startswith(allowedDir):
		    _rootFilesList.append(file)
	rootFilesList = _rootFilesList
	del _rootFilesList
	
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Calculating ..."), back = True)
	orphanList = []
	# FIXME: now parse them!!!
	for rootFile in rootFilesList:
	    for file in filesList:
		if (file == rootFile):
		    orphanList.append(file)
		    break
	
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Orphaned files:")+entropyTools.bold(len(orphanList)))
	f = open(etpConst['packagestmpdir']+"/orphaned-files.txt","w")
	for line in orphanList:
	    f.write(line+"\n")
	f.flush()
	f.close()
	entropyTools.print_info(entropyTools.green(" --> ")+entropyTools.red("Dump saved in: ")+entropyTools.bold(etpConst['packagestmpdir']+"/orphaned-files.txt"))



    elif (options[0] == "sanity-check"):
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Running sanity check on the database ... "), back = True)
	dbconn = etpDatabase(readOnly = True)
	dbconn.noopCycle()
	dbconn.closeDB()
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Database sanity check passed."))

    elif (options[0] == "remove"):

	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Scanning packages that would be removed ..."), back = True)
	
	myatoms = options[1:]
	if len(myatoms) == 0:
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("Not enough parameters"))
	    sys.exit(303)

	pkglist = []
	for atom in myatoms:
	    # validate atom
	    dbconn = etpDatabase(readOnly = True)
	    pkg = dbconn.searchPackages(atom)
	    try:
		for x in pkg:
		    pkglist.append(x[0])
	    except:
		pass

	# filter dups
	pkglist = list(set(pkglist))
	# check if atoms were found
	if len(pkglist) == 0:
	    print
	    entropyTools.print_error(entropyTools.yellow(" * ")+entropyTools.red("No packages found."))
	    sys.exit(303)
	
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("These are the packages that would be removed from the database:"))

	for pkg in pkglist:
	    entropyTools.print_info(entropyTools.red("\t (*) ")+entropyTools.bold(pkg))
	
	# ask to continue
	rc = entropyTools.askquestion("     Would you like to continue ?")
	if rc == "No":
	    sys.exit(0)
	
	# now mark them as stable
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Removing selected packages ..."))

	# open db
	dbconn = etpDatabase(readOnly = False, noUpload = True)
	for pkg in pkglist:
	    entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Removing package: ")+entropyTools.bold(pkg)+entropyTools.red(" ..."), back = True)
	    dbconn.removePackage(pkg)
	dbconn.commitChanges()
	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("All the selected packages have been removed as requested. Have fun."))
	dbconn.closeDB()

    # used by reagent
    elif (options[0] == "statistics"):
	entropyTools.print_info(entropyTools.green(" [LOCAL DB STATISTIC]\t\t")+entropyTools.red("Information"))
	# fetch total packages
	dbconn = etpDatabase(readOnly = True)
	totalpkgs = len(dbconn.listAllPackages())
	totalstablepkgs = len(dbconn.listStablePackages())
	totalunstablepkgs = len(dbconn.listUnstablePackages())
	entropyTools.print_info(entropyTools.green(" Total Installed Packages\t\t")+entropyTools.red(str(totalpkgs)))
	entropyTools.print_info(entropyTools.green(" Total Stable Packages\t\t")+entropyTools.red(str(totalstablepkgs)))
	entropyTools.print_info(entropyTools.green(" Total Unstable Packages\t\t")+entropyTools.red(str(totalunstablepkgs)))
	entropyTools.syncRemoteDatabases(justStats = True)
	dbconn.closeDB()

    # used by reagent
    elif (options[0] == "md5check"):

	entropyTools.print_info(entropyTools.green(" * ")+entropyTools.red("Integrity verification of the selected packages:"))

	mypackages = options[1:]
	dbconn = etpDatabase(readOnly = True)
	
	if (len(mypackages) == 0):
	    # check world
	    # create packages list
	    pkgs2check = dbconn.listAllPackages()
	elif (mypackages[0] == "world"):
	    # check world
	    # create packages list
	    pkgs2check = dbconn.listAllPackages()
	else:
	    # catch the names
	    pkgs2check = []
	    for pkg in mypackages:
		results = dbconn.searchPackages(pkg)
		for i in results:
		    pkgs2check.append(i[0])

	entropyTools.print_info(entropyTools.red("   This is the list of the packages that would be checked:"))
	
	toBeDownloaded = []
	availList = []
	for i in pkgs2check:
	    pkgfile = dbconn.retrievePackageVar(i,"download")
	    pkgfile = pkgfile.split("/")[len(pkgfile.split("/"))-1]
	    if (os.path.isfile(etpConst['packagesbindir']+"/"+pkgfile)):
		entropyTools.print_info(entropyTools.green("   - [PKG AVAILABLE] ")+entropyTools.red(i))
		availList.append(pkgfile)
	    elif (os.path.isfile(etpConst['packagessuploaddir']+"/"+pkgfile)):
		entropyTools.print_info(entropyTools.green("   - [RUN ACTIVATOR] ")+entropyTools.darkred(i))
	    else:
		entropyTools.print_info(entropyTools.green("   - [MUST DOWNLOAD] ")+entropyTools.yellow(i))
		toBeDownloaded.append(pkgfile)
	
	# FIXME add download support
	# FIXME complete this
	
	
	dbconn.closeDB()

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

	# check if the database is locked locally
	if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']):
	    entropyTools.print_info(entropyTools.red(" * ")+entropyTools.red(" Entropy database is already locked by you :-)"))
	else:
	    # check if the database is locked REMOTELY
	    entropyTools.print_info(entropyTools.red(" * ")+entropyTools.red(" Locking and Sync Entropy database ..."), back = True)
	    for uri in etpConst['activatoruploaduris']:
	        ftp = mirrorTools.handlerFTP(uri)
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
	    entropyTools.print_info(entropyTools.yellow(" * ")+entropyTools.green("Mirrors have not been unlocked. Run activator."))
	
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
    def handlePackage(self, etpData, forceBump = False):
	if (not self.isPackageAvailable(etpData['category']+"/"+etpData['name']+"-"+etpData['version'])):
	    update, revision = self.addPackage(etpData)
	else:
	    update, revision = self.updatePackage(etpData,forceBump)
	return update, revision

    # default add an unstable package
    def addPackage(self, etpData, revision = 0, wantedBranch = "unstable"):
	# check if the package is slotted
	
	log.log(2,"[DB] Adding package: "+etpData['category']+"/"+etpData['name']+"-"+etpData['version'])
	log.log(2,"    which slot is: "+etpData['slot'])
	# if a similar package exist, enter here
	searchsimilar = self.searchSimilarPackages(etpData['category']+"/"+etpData['name'])
	if (searchsimilar != []):
	    log.log(2,"    which searchsimilar is not empty")
	    # there are other packages with the same category/name
	    # do we have to remove anything?
	    removelist = []
	    for oldpkg in searchsimilar:
		# if it's the same, skip
	        # get the package slot
	        slot = self.retrievePackageVar(oldpkg,"slot")
		branch = self.retrievePackageVar(oldpkg,"branch")
		log.log(2,"    there is: "+oldpkg+" which slot is: "+slot+" and branch: "+branch)
		if (etpData['slot'] == slot) and (wantedBranch == branch):
		    # remove!
		    log.log(2,"    unfortunately,"+etpData['category']+"/"+etpData['name']+"-"+etpData['version']+" is similar to "+oldpkg+"because their slot is: "+etpData['slot']+" and branch: "+wantedBranch+". So REMOVING.")
		    removelist.append(oldpkg)
	    for pkg in removelist:
		self.removePackage(pkg)
	
	# wantedBranch = etpData['branch']
	self.cursor.execute(
		'INSERT into etpData VALUES '
		'(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)'
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
			wantedBranch,
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
			etpData['neededlibs'],
			revision,
			)
	)
	self.commitChanges()
	return True,revision

    # Update already available atom in db
    # returns True,revision if the package has been updated
    # returns False,revision if not
    def updatePackage(self, etpData, forceBump = False):
	# check if the data correspond
	# if not, update, else drop
	curRevision = self.retrievePackageVar(etpData['category']+"/"+etpData['name']+"-"+etpData['version'],"revision")
	curBranch = self.retrievePackageVar(etpData['category']+"/"+etpData['name']+"-"+etpData['version'],"branch")
	oldPkgInfo = etpData['category']+"/"+etpData['name']+"-"+etpData['version']
	rc = self.comparePackagesData(etpData,oldPkgInfo)
	if (not rc) or (forceBump):
	    # update !
	    curRevision += 1
	    # remove the table
	    self.removePackage(etpData['category']+"/"+etpData['name']+"-"+etpData['version'])
	    # readd table
	    self.addPackage(etpData,curRevision,curBranch)
	    self.commitChanges()
	    return True, curRevision
	else:
	    self.commitChanges()
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
	self.cursor.execute('SELECT "'+pkgvar+'" FROM etpData WHERE atom = "'+pkgkey+'"')
	for row in self.cursor:
	    result.append(row[0])
	return result[0]

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

    # this function search packages with the same pkgcat/pkgname
    # you must provide something like: media-sound/amarok
    # optionally, you can add version too.
    def searchSimilarPackages(self,atom):
	category = atom.split("/")[0]
	name = atom.split("/")[1]
	result = []
	self.cursor.execute('SELECT atom FROM etpData WHERE category = "'+category+'" AND name = "'+name+'"')
	for row in self.cursor:
	    result.append(row[0])
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

    def searchStablePackages(self,atom):
	category = atom.split("/")[0]
	name = atom.split("/")[1]
	result = []
	self.cursor.execute('SELECT atom FROM etpData WHERE category = "'+category+'" AND name = "'+name+'" AND branch = "stable"')
	for row in self.cursor:
	    result.append(row[0])
	return result

    def searchUnstablePackages(self,atom):
	category = atom.split("/")[0]
	name = atom.split("/")[1]
	result = []
	self.cursor.execute('SELECT atom FROM etpData WHERE category = "'+category+'" AND name = "'+name+'" AND branch = "stable"')
	for row in self.cursor:
	    result.append(row[0])
	return result

    # useful to quickly retrieve (and trash) all the data
    # and look for problems.
    def noopCycle(self):
	self.cursor.execute('SELECT * FROM etpData')

    def stabilizePackage(self,atom,stable = True):
	if (stable):
	    # ! Get rid of old entries with the same slot, pkgcat/name that
	    # were already marked "stable"
	    # get its pkgname
	    pkgname = self.retrievePackageVar(atom,"name")
	    # get its pkgcat
	    category = self.retrievePackageVar(atom,"category")
	    # search packages with similar pkgcat/name marked as stable
	    slot = self.retrievePackageVar(atom,"slot")
	    # we need to get rid of them
	    results = self.searchStablePackages(category+"/"+pkgname)
	    removelist = []
	    for result in results:
		# have a look if the slot matches
		#print result
		myslot = self.retrievePackageVar(result,"slot")
		if (myslot == slot):
		    removelist.append(result)
	    for pkg in removelist:
		self.removePackage(pkg)
	    
	    self.cursor.execute('UPDATE etpData SET branch = "stable" WHERE atom = "'+atom+'"')
	else:
	    self.cursor.execute('UPDATE etpData SET branch = "unstable" WHERE atom = "'+atom+'"')

    def writePackageParameter(self,atom,field,what):
	self.cursor.execute('UPDATE etpData SET '+field+' = "'+what+'" WHERE atom = "'+atom+'"')
