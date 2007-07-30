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
from pysqlite2 import dbapi2 as sqlite
#import commands
#import re
import os
import sys
import string

# Logging initialization
import logTools
dbLog = logTools.LogFile(level = etpConst['databaseloglevel'],filename = etpConst['databaselogfile'], header = "[DBase]")


# TIP OF THE DAY:
# never nest closeDB() and re-init inside a loop !!!!!!!!!!!! NEVER !

def database(options):

    import activatorTools
    import reagentTools
    import mirrorTools

    if len(options) == 0:
	print_error(yellow(" * ")+red("Not enough parameters"))
	sys.exit(301)

    if (options[0] == "--initialize"):
	
	# do some check, print some warnings
	print_info(green(" * ")+red("Initializing Entropy database..."), back = True)
        # database file: etpConst['etpdatabasefilepath']
        if os.path.isfile(etpConst['etpdatabasefilepath']):
	    print_info(red(" * ")+bold("WARNING")+red(": database file already exists. Overwriting."))
	    rc = entropyTools.askquestion("\n     Do you want to continue ?")
	    if rc == "No":
	        sys.exit(0)
	    entropyTools.spawnCommand("rm -f "+etpConst['etpdatabasefilepath'])

	# initialize the database
        dbconn = etpDatabase(readOnly = False, noUpload = True)
	dbconn.initializeDatabase()
	
	# sync packages directory
	activatorTools.packages(["sync","--ask"])
	
	# now fill the database
	pkglist = os.listdir(etpConst['packagesbindir'])
	# filter .md5
	_pkglist = []
	for i in pkglist:
	    if not i.endswith(etpConst['packageshashfileext']):
		_pkglist.append(i)
	pkglist = _pkglist

	print_info(green(" * ")+red("Reinitializing Entropy database using Packages in the repository ..."))
	currCounter = 0
	atomsnumber = len(pkglist)
	import reagentTools
	for pkg in pkglist:
	    print_info(green(" * ")+red("Analyzing: ")+bold(pkg), back = True)
	    currCounter += 1
	    print_info(green("  (")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(pkg)+red(" ..."))
	    etpData = reagentTools.extractPkgData(etpConst['packagesbindir']+"/"+pkg)
		
	    # remove shait
	    entropyTools.spawnCommand("rm -rf "+etpConst['packagestmpdir']+"/"+pkg)
	    # fill the db entry
	    dbconn.addPackage(etpData)
	    dbconn.commitChanges()
	
	dbconn.closeDB()
	print_info(green(" * ")+red("Entropy database has been reinitialized using binary packages available"))

    # used by reagent
    elif (options[0] == "search"):
	mykeywords = options[1:]
	if (len(mykeywords) == 0):
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(302)
	if (not os.path.isfile(etpConst['etpdatabasefilepath'])):
	    print_error(yellow(" * ")+red("Entropy Datbase does not exist"))
	    sys.exit(303)
	# search tool
	print_info(green(" * ")+red("Searching ..."))
	# open read only
	dbconn = etpDatabase(True)
	foundCounter = 0
	for mykeyword in mykeywords:
	    results = dbconn.searchPackages(mykeyword)
	    
	    for result in results:
		foundCounter += 1
		print 
		print_info(green(" * ")+bold(dbconn.retrieveCategory(result[1])+"/"+dbconn.retrieveName(result[1])))   # package atom
		
		print_info(red("\t Atom: ")+blue(result[0]))
		print_info(red("\t Name: ")+blue(dbconn.retrieveName(result[1])))
		print_info(red("\t Version: ")+blue(dbconn.retrieveVersion(result[1])))
		tag = dbconn.retrieveVersionTag(result[1])
		if (tag):
		    print_info(red("\t Tag: ")+blue(tag))
		
		description = dbconn.retrieveDescription(result[1])
		if (description):
		    print_info(red("\t Description: ")+description)
		
		flags = dbconn.retrieveCompileFlags(result[1])
		print_info(red("\t CHOST: ")+blue(flags[0]))
		print_info(red("\t CFLAGS: ")+darkred(flags[1]))
		print_info(red("\t CXXFLAGS: ")+darkred(flags[2]))
		
		website = dbconn.retrieveHomepage(result[1])
		if (website):
		    print_info(red("\t Website: ")+website)
		
		flags = string.join(dbconn.retrieveUseflags(result[1])," ")
		if (flags):
		    print_info(red("\t USE Flags: ")+blue(flags))
		
		print_info(red("\t License: ")+bold(dbconn.retrieveLicense(result[1])))
		keywords = string.join(dbconn.retrieveKeywords(result[1])," ")
		binkeywords = string.join(dbconn.retrieveBinKeywords(result[1])," ")
		print_info(red("\t Source keywords: ")+darkblue(keywords))
		print_info(red("\t Binary keywords: ")+green(binkeywords))
		print_info(red("\t Package branch: ")+dbconn.retrieveBranch(result[1]))
		print_info(red("\t Download relative URL: ")+dbconn.retrieveDownloadURL(result[1]))
		print_info(red("\t Package Checksum: ")+green(dbconn.retrieveDigest(result[1])))
		
		sources = dbconn.retrieveSources(result[1])
		if (sources):
		    print_info(red("\t Sources"))
		    for source in sources:
			print_info(darkred("\t    # Source package: ")+yellow(source))
		
		slot = dbconn.retrieveSlot(result[1])
		if (slot):
		    print_info(red("\t Slot: ")+yellow(slot))
		else:
		    print_info(red("\t Slot: ")+yellow("Not set"))
		
		'''
		mirrornames = []
		for x in sources:
		    if x.startswith("mirror://"):
		        mirrorname = x.split("/")[2]
		        mirrornames.append(mirrorname)
		for mirror in mirrornames:
		    mirrorlinks = dbconn.retrieveMirrorInfo(mirror)
		    print_info(red("\t mirror://"+mirror+" = ")+str(string.join(mirrorlinks," "))) # I don't need to print mirrorlinks
		'''
		
		dependencies = dbconn.retrieveDependencies(result[1])
		if (dependencies):
		    print_info(red("\t Dependencies"))
		    for dep in dependencies:
			print_info(darkred("\t    # Depends on: ")+dep)
		#print_info(red("\t Blah: ")+result[20]) --> it's a dup of [21]
		
		rundependencies = dbconn.retrieveRunDependencies(result[1])
		if (rundependencies):
		    print_info(red("\t Built with runtime dependencies"))
		    for rundep in rundependencies:
			print_info(darkred("\t    # Dependency: ")+rundep)
		
		conflicts = dbconn.retrieveConflicts(result[1])
		if (conflicts):
		    print_info(red("\t Conflicts with"))
		    for conflict in conflicts:
			print_info(darkred("\t    # Conflict: ")+conflict)
		
		api = dbconn.retrieveApi(result[1])
		print_info(red("\t Entry API: ")+green(str(api)))
		
		date = dbconn.retrieveDateCreation(result[1])
		print_info(red("\t Package Creation date: ")+str(entropyTools.convertUnixTimeToHumanTime(int(date))))
		
		neededlibs = dbconn.retrieveNeededlibs(result[1])
		if (neededlibs):
		    print_info(red("\t Built with needed libraries"))
		    for lib in neededlibs:
			print_info(darkred("\t    # Needed library: ")+lib)
		
		revision = dbconn.retrieveRevision(result[1])
		print_info(red("\t Entry revision: ")+str(revision))
		#print result
		
	dbconn.closeDB()
	if (foundCounter == 0):
	    print_warning(red(" * ")+red("Nothing found."))
	else:
	    print
    
    elif (options[0] == "restore-package-info"):
	mypackages = options[1:]
	if (len(mypackages) == 0):
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(302)

	# sync packages directory
	activatorTools.packages(["sync","--ask"])

	dbconn = etpDatabase(readOnly = False, noUpload = True)
	
	# validate entries
	_mypackages = []
	for pkg in mypackages:
	    if (dbconn.isPackageAvailable(pkg)):
		_mypackages.append(pkg)
	mypackages = _mypackages
	
	if len(mypackages) == 0:
	    print_error(yellow(" * ")+red("No valid package found. You must specify category/atom-version."))
	    sys.exit(303)
	
	print_info(green(" * ")+red("Reinitializing Entropy database using Packages in the repository ..."))
	
	# get the file list
	pkglist = []
	branches = []
	for pkg in mypackages:
	    # dump both branches if exist
	    if (dbconn.isSpecificPackageAvailable(pkg, branch = "stable")):
		branches.append("stable")
	    if (dbconn.isSpecificPackageAvailable(pkg, branch = "unstable")):
		branches.append("unstable")
	    for branch in branches:
		idpackage = dbconn.getIDPackage(pkg,branch)
		pkgfile = dbconn.retrieveDownloadURL(idpackage)
	        pkgfile = os.path.basename(pkgfile)
	        pkglist.append(pkgfile)

	# validate files
	_pkglist = []
	for file in pkglist:
	    if (not os.path.isfile(etpConst['packagesbindir']+"/"+file)):
	        print_info(yellow(" * ")+red("Attention: ")+bold(file)+red(" does not exist anymore."))
	    else:
		_pkglist.append(file)
	pkglist = _pkglist

	currCounter = 0
	atomsnumber = len(pkglist)
	for pkg in pkglist:
	    print_info(green(" * ")+red("Analyzing: ")+bold(pkg), back = True)
	    currCounter += 1
	    print_info(green("  (")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(pkg)+red(" ..."))
	    etpData = reagentTools.extractPkgData(etpConst['packagesbindir']+"/"+pkg)
	    # remove shait
	    entropyTools.spawnCommand("rm -rf "+etpConst['packagestmpdir']+"/"+pkg)
	    # fill the db entry
	    dbconn.handlePackage(etpData)
	    dbconn.commitChanges()

	dbconn.commitChanges()
	dbconn.closeDB()
	print_info(green(" * ")+red("Successfully restored database information for the chosen packages."))


    elif (options[0] == "create-empty-database"):
	mypath = options[1:]
	if len(mypath) == 0:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(303)
	if (os.path.dirname(mypath[0]) != '') and (not os.path.isdir(os.path.dirname(mypath[0]))):
	    print_error(green(" * ")+red("Supplied directory does not exist."))
	    sys.exit(304)
	print_info(green(" * ")+red("Initializing an empty database file with Entropy structure ..."),back = True)
	connection = sqlite.connect(mypath[0])
	cursor = connection.cursor()
	for sql in etpSQLInitDestroyAll.split(";"):
	    if sql:
	        cursor.execute(sql+";")
	del sql
	for sql in etpSQLInit.split(";"):
	    if sql:
		cursor.execute(sql+";")
	connection.commit()
	cursor.close()
	connection.close()
	print_info(green(" * ")+red("Entropy database file ")+bold(mypath[0])+red(" successfully initialized."))

    elif (options[0] == "stabilize") or (options[0] == "unstabilize"):

	if options[0] == "stabilize":
	    stable = True
	else:
	    stable = False
	
	if (stable):
	    print_info(green(" * ")+red("Collecting packages that would be marked stable ..."), back = True)
	else:
	    print_info(green(" * ")+red("Collecting packages that would be marked unstable ..."), back = True)
	
	myatoms = options[1:]
	if len(myatoms) == 0:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(303)
	# is world?
	if myatoms[0] == "world":
	    # open db in read only
	    dbconn = etpDatabase(readOnly = True)
	    if (stable):
	        pkglist = dbconn.listUnstablePackages()
	    else:
		pkglist = dbconn.listStablePackages()
	    # This is the list of all the packages available in Entropy
	    dbconn.closeDB()
	else:
	    pkglist = []
	    for atom in myatoms:
		# validate atom
		dbconn = etpDatabase(readOnly = True)
		if (stable):
		    pkg = dbconn.searchPackagesInBranch(atom,"unstable")
		else:
		    pkg = dbconn.searchPackagesInBranch(atom,"stable")
		for x in pkg:
		    pkglist.append(x[0])
	
	# filter dups
	pkglist = list(set(pkglist))
	# check if atoms were found
	if len(pkglist) == 0:
	    print
	    print_error(yellow(" * ")+red("No packages found."))
	    sys.exit(303)
	
	# show what would be done
	if (stable):
	    print_info(green(" * ")+red("These are the packages that would be marked stable:"))
	else:
	    print_info(green(" * ")+red("These are the packages that would be marked unstable:"))

	for pkg in pkglist:
	    print_info(red("\t (*) ")+bold(pkg))
	
	# ask to continue
	rc = entropyTools.askquestion("     Would you like to continue ?")
	if rc == "No":
	    sys.exit(0)
	
	# now mark them as stable
	print_info(green(" * ")+red("Marking selected packages ..."))

	# open db
	dbconn = etpDatabase(readOnly = False, noUpload = True)
	import re
	for pkg in pkglist:
	    print_info(green(" * ")+red("Marking package: ")+bold(pkg)+red(" ..."), back = True)
	    rc, action = dbconn.stabilizePackage(pkg,stable)
	    # @rc: True if updated, False if not
	    # @action: action taken: "stable" for stabilized package, "unstable" for unstabilized package
	    if (rc):
		
		print_info(green(" * ")+red("Package: ")+bold(pkg)+red(" needs to be marked ")+bold(action), back = True)
		
		# change download database parameter name
		download = dbconn.retrievePackageVar(pkg, "download", branch = action)
		# change action with the opposite:
		if action == "stable":
		    # move to unstable
		    oppositeAction = "unstable"
		else:
		    oppositeAction = "stable"
		
		oldpkgfilename = os.path.basename(download)
		download = re.subn("-"+oppositeAction,"-"+action, download)
		
		if download[1]: # if the name has been converted
		
		    newpkgfilename = os.path.basename(download[0])
		
		    # change download parameter in the database entry
		    dbconn.writePackageParameter(pkg, "download", download[0], action)
		
		    print_info(green("   * ")+yellow("Updating local package name"))
		
		    # change filename locally
		    if os.path.isfile(etpConst['packagesbindir']+"/"+oldpkgfilename):
		        os.rename(etpConst['packagesbindir']+"/"+oldpkgfilename,etpConst['packagesbindir']+"/"+newpkgfilename)
		
		    print_info(green("   * ")+yellow("Updating local package checksum"))
		
		    # update md5
		    if os.path.isfile(etpConst['packagesbindir']+"/"+oldpkgfilename+etpConst['packageshashfileext']):
			
		        f = open(etpConst['packagesbindir']+"/"+oldpkgfilename+etpConst['packageshashfileext'])
		        oldMd5 = f.readline().strip()
		        f.close()
		        newMd5 = re.subn(oldpkgfilename, newpkgfilename, oldMd5)
		        if newMd5[1]:
			    f = open(etpConst['packagesbindir']+"/"+newpkgfilename+etpConst['packageshashfileext'],"w")
			    f.write(newMd5[0]+"\n")
			    f.flush()
			    f.close()
		        # remove old
		        os.remove(etpConst['packagesbindir']+"/"+oldpkgfilename+etpConst['packageshashfileext'])
			
		    else: # old md5 does not exist
			
			entropyTools.createHashFile(etpConst['packagesbindir']+"/"+newpkgfilename)
			
		
		    print_info(green("   * ")+yellow("Updating remote package information"))
		
		    # change filename remotely
		    ftp = mirrorTools.handlerFTP(uri)
		    ftp.setCWD(etpConst['binaryurirelativepath'])
		    if (ftp.isFileAvailable(etpConst['packagesbindir']+"/"+oldpkgfilename)):
			# rename tbz2
			ftp.renameFile(oldpkgfilename,newpkgfilename)
			# remove old .md5
			ftp.deleteFile(oldpkgfilename+etpConst['packageshashfileext'])
			# upload new .md5 if found
			if os.path.isfile(etpConst['packagesbindir']+"/"+newpkgfilename+etpConst['packageshashfileext']):
			    ftp.uploadFile(etpConst['packagesbindir']+"/"+newpkgfilename+etpConst['packageshashfileext'],ascii = True)
		

	dbconn.commitChanges()
	print_info(green(" * ")+red("All the selected packages have been marked as requested. Have fun."))
	dbconn.closeDB()

    elif (options[0] == "sanity-check"):
	print_info(green(" * ")+red("Running sanity check on the database ... "), back = True)
	dbconn = etpDatabase(readOnly = True)
	dbconn.noopCycle()
	dbconn.closeDB()
	print_info(green(" * ")+red("Database sanity check passed."))

    elif (options[0] == "remove"):

	print_info(green(" * ")+red("Scanning packages that would be removed ..."), back = True)
	
	myopts = options[1:]
	_myopts = []
	branch = ''
	for opt in myopts:
	    if (opt.startswith("--branch=")) and (len(opt.split("=")) == 2):
		branch = opt.split("=")[1]
	    else:
		_myopts.append(opt)
	myopts = _myopts
	
	if len(myopts) == 0:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(303)

	pkglist = []
	dbconn = etpDatabase(readOnly = True)
	
	for atom in myopts:
	    if (branch):
		pkg = dbconn.searchPackagesInBranch(atom,branch)
	    else:
	        pkg = dbconn.searchPackages(atom)
	    for x in pkg:
		pkglist.append(x)

	# filter dups
	pkglist = list(set(pkglist))
	# check if atoms were found
	if len(pkglist) == 0:
	    print
	    dbconn.closeDB()
	    print_error(yellow(" * ")+red("No packages found."))
	    sys.exit(303)
	
	print_info(green(" * ")+red("These are the packages that would be removed from the database:"))

	for pkg in pkglist:
	    pkgatom = pkg[0]
	    pkgid = pkg[1]
	    branch = dbconn.retrieveBranch(pkgid)
	    print_info(red("\t (*) ")+bold(pkgatom)+blue("\t\t\tBRANCH: ")+bold(branch))

	dbconn.closeDB()

	# ask to continue
	rc = entropyTools.askquestion("     Would you like to continue ?")
	if rc == "No":
	    sys.exit(0)
	
	# now mark them as stable
	print_info(green(" * ")+red("Removing selected packages ..."))

	# open db
	dbconn = etpDatabase(readOnly = False, noUpload = True)
	for pkg in pkglist:
	    print_info(green(" * ")+red("Removing package: ")+bold(pkg[0])+red(" ..."), back = True)
	    dbconn.removePackage(pkg[1])
	dbconn.commitChanges()
	print_info(green(" * ")+red("All the selected packages have been removed as requested. To remove online binary packages, just run Activator."))
	dbconn.closeDB()

    # used by reagent
    elif (options[0] == "statistics"):
	print_info(green(" [LOCAL DB STATISTIC]\t\t")+red("Information"))
	# fetch total packages
	dbconn = etpDatabase(readOnly = True)
	totalpkgs = len(dbconn.listAllPackages())
	totalstablepkgs = len(dbconn.listStablePackages())
	totalunstablepkgs = len(dbconn.listUnstablePackages())
	print_info(green(" Total Installed Packages\t\t")+red(str(totalpkgs)))
	print_info(green(" Total Stable Packages\t\t")+red(str(totalstablepkgs)))
	print_info(green(" Total Unstable Packages\t\t")+red(str(totalunstablepkgs)))
	activatorTools.syncRemoteDatabases(justStats = True)
	dbconn.closeDB()

    # used by reagent
    # FIXME: complete this with some automated magic
    elif (options[0] == "md5check"):

	print_info(green(" * ")+red("Integrity verification of the selected packages:"))

	mypackages = options[1:]
	dbconn = etpDatabase(readOnly = True)
	
	# statistic vars
	pkgMatch = 0
	pkgNotMatch = 0
	pkgDownloadedSuccessfully = 0
	pkgDownloadedError = 0
	worldSelected = False
	
	if (len(mypackages) == 0):
	    # check world
	    # create packages list
	    worldSelected = True
	    pkgs2check = dbconn.listAllPackages()
	elif (mypackages[0] == "world"):
	    # check world
	    # create packages list
	    worldSelected = True
	    pkgs2check = dbconn.listAllPackages()
	else:
	    # catch the names
	    pkgs2check = []
	    for pkg in mypackages:
		results = dbconn.searchPackages(pkg)
		for i in results:
		    pkgs2check.append(i)

	# filter idpackage only
	_pkgs2check = []
	for x in pkgs2check:
	    _pkgs2check.append(x[1])
	pkgs2check = _pkgs2check

	# filter dups
	if (pkgs2check):
	    pkgs2check = entropyTools.filterDuplicatedEntries(pkgs2check)

	if (not worldSelected):
	    print_info(red("   This is the list of the packages that would be checked:"))
	else:
	    print_info(red("   All the packages in the Entropy Packages repository will be checked."))
	
	toBeDownloaded = []
	availList = []
	for id in pkgs2check:
	    pkgfile = dbconn.retrieveDownloadURL(id)
	    pkgfile = os.path.basename(pkgfile)
	    pkgatom = dbconn.retrieveAtom(id)
	    if (os.path.isfile(etpConst['packagesbindir']+"/"+pkgfile)):
		if (not worldSelected): print_info(green("   - [PKG AVAILABLE] ")+red(pkgatom)+" -> "+bold(pkgfile))
		availList.append(id)
	    elif (os.path.isfile(etpConst['packagessuploaddir']+"/"+pkgfile)):
		if (not worldSelected): print_info(green("   - [RUN ACTIVATOR] ")+darkred(pkgatom)+" -> "+bold(pkgfile))
	    else:
		if (not worldSelected): print_info(green("   - [MUST DOWNLOAD] ")+yellow(pkgatom)+" -> "+bold(pkgfile))
		toBeDownloaded.append([id,pkgfile])
	
	rc = entropyTools.askquestion("     Would you like to continue ?")
	if rc == "No":
	    sys.exit(0)

	notDownloadedPackages = []
	if (toBeDownloaded != []):
	    print_info(red("   Starting to download missing files..."))
	    for uri in etpConst['activatoruploaduris']:
		
		if (notDownloadedPackages != []):
		    print_info(red("   Trying to search missing or broken files on another mirror ..."))
		    toBeDownloaded = notDownloadedPackages
		    notDownloadedPackages = []
		
		for pkg in toBeDownloaded:
		    rc = activatorTools.downloadPackageFromMirror(uri,pkg[1])
		    if (rc is None):
			notDownloadedPackages.append(pkg[1])
		    if (rc == False):
			notDownloadedPackages.append(pkg[1])
		    if (rc == True):
			pkgDownloadedSuccessfully += 1
			availList.append(pkg[0])
		
		if (notDownloadedPackages == []):
		    print_info(red("   All the binary packages have been downloaded successfully."))
		    break
	
	    if (notDownloadedPackages != []):
		print_warning(red("   These are the packages that cannot be found online:"))
		for i in notDownloadedPackages:
		    pkgDownloadedError += 1
		    print_warning(red("    * ")+yellow(i))
		print_warning(red("   They won't be checked."))
	
	brokenPkgsList = []
	for pkg in availList:
	    pkgfile = dbconn.retrieveDownloadURL(pkg)
	    pkgfile = os.path.basename(pkgfile)
	    print_info(red("   Checking hash of ")+yellow(pkgfile)+red(" ..."), back = True)
	    storedmd5 = dbconn.retrieveDigest(pkg)
	    result = entropyTools.compareMd5(etpConst['packagesbindir']+"/"+pkgfile,storedmd5)
	    if (result):
		# match !
		pkgMatch += 1
		#print_info(red("   Package ")+yellow(pkg)+green(" is healthy. Checksum: ")+yellow(storedmd5), back = True)
	    else:
		pkgNotMatch += 1
		print_error(red("   Package ")+yellow(pkgfile)+red(" is _NOT_ healthy !!!! Stored checksum: ")+yellow(storedmd5))
		brokenPkgsList.append(pkgfile)

	dbconn.closeDB()

	if (brokenPkgsList != []):
	    print_info(blue(" *  This is the list of the BROKEN packages: "))
	    for bp in brokenPkgsList:
		print_info(red("    * Package file: ")+bold(bp))

	# print stats
	print_info(blue(" *  Statistics: "))
	print_info(yellow("     Number of checked packages:\t\t")+str(pkgMatch+pkgNotMatch))
	print_info(green("     Number of healthy packages:\t\t")+str(pkgMatch))
	print_info(red("     Number of broken packages:\t\t")+str(pkgNotMatch))
	if (pkgDownloadedSuccessfully > 0) or (pkgDownloadedError > 0):
	    print_info(green("     Number of downloaded packages:\t\t")+str(pkgDownloadedSuccessfully+pkgDownloadedError))
	    print_info(green("     Number of happy downloads:\t\t")+str(pkgDownloadedSuccessfully))
	    print_info(red("     Number of failed downloads:\t\t")+str(pkgDownloadedError))


############
# Functions and Classes
#####################################################################################

# this class simply describes the current database status

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

    def __init__(self, readOnly = False, noUpload = False, dbFile = etpConst['etpdatabasefilepath'], clientDatabase = False):
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase.__init__ called.")
	
	self.readOnly = readOnly
	self.noUpload = noUpload
	self.clientDatabase = clientDatabase
	
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
	    print_info(red(" * ")+red(" Entropy database is already locked by you :-)"))
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
		    # FIXME show the lock status

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
	            sys.exit(320)

	    # if we arrive here, it is because all the mirrors are unlocked so... damn, LOCK!
	    activatorTools.lockDatabases(True)

	    # ok done... now sync the new db, if needed
	    activatorTools.syncRemoteDatabases(self.noUpload)
	
	self.connection = sqlite.connect(dbFile)
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
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"closeDB: closing database opened in read/write.")
	
	
	# FIXME verify all this shit, for now it works...
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
	    self.connection.commit()
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

    # this function manages the submitted package
    # if it does not exist, it fires up addPackage
    # otherwise it fires up updatePackage
    def handlePackage(self, etpData, forceBump = False):

	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlePackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

        # prepare versiontag
	versiontag = ""
	if (etpData['versiontag']):
	    versiontag = "-"+etpData['versiontag']

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlePackage: called.")
	if (not self.isPackageAvailable(etpData['category']+"/"+etpData['name']+"-"+etpData['version']+versiontag)):
	    update, revision, etpDataUpdated = self.addPackage(etpData)
	else:
	    update, revision, etpDataUpdated = self.updatePackage(etpData,forceBump)
	return update, revision, etpDataUpdated

    # default add an unstable package
    def addPackage(self, etpData, revision = 0, wantedBranch = "unstable"):

	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addPackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addPackage: called.")
	
	# Handle package name
	etpData['download'] = etpData['download'].split(".tbz2")[0]
	# add branch name
	etpData['download'] += "-"+wantedBranch+".tbz2"

	# if a similar package, in the same branch exists, mark for removal
	searchsimilar = self.searchSimilarPackages(etpData['category']+"/"+etpData['name'], branch = wantedBranch)
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"addPackage: here is the list of similar packages (that will be removed) found for "+etpData['category']+"/"+etpData['name']+": "+str(searchsimilar))
	removelist = []
	for oldpkg in searchsimilar:
	    # get the package slot
	    idpackage = oldpkg[1]
	    slot = self.retrieveSlot(idpackage)
	    if (etpData['slot'] == slot):
		# remove!
		removelist.append(idpackage)
	
	for pkg in removelist:
	    self.removePackage(pkg)
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addPackage: inserting: ")
	for ln in etpData:
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"\t "+ln+": "+str(etpData[ln]))

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
	    versiontag = "-"+etpData['versiontag']

	# baseinfo
	self.cursor.execute(
		'INSERT into baseinfo VALUES '
		'(NULL,?,?,?,?,?,?,?,?,?,?)'
		, (	etpData['category']+"/"+etpData['name']+"-"+etpData['version']+versiontag,
			catid,
			etpData['name'],
			etpData['version'],
			etpData['versiontag'],
			revision,
			wantedBranch,
			etpData['slot'],
			licid,
			etpData['etpapi'],
			)
	)
	
	# I don't use lastrowid because the db must be multiuser aware
	idpackage = self.getIDPackage(etpData['category']+"/"+etpData['name']+"-"+etpData['version']+versiontag,wantedBranch)

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
	    self.cursor.execute(
		'INSERT into content VALUES '
		'(?,?)'
		, (	idpackage,
			file,
			)
	    )
	
	# dependencies, a list
	for dep in etpData['dependencies']:
	    self.cursor.execute(
		'INSERT into dependencies VALUES '
		'(?,?)'
		, (	idpackage,
			dep,
			)
	    )

	# rundependencies, a list
	for rdep in etpData['rundependencies']:
	    self.cursor.execute(
		'INSERT into rundependencies VALUES '
		'(?,?)'
		, (	idpackage,
			rdep,
			)
	    )

	# rundependenciesxt, a list
	for rdepxt in etpData['rundependenciesXT']:
	    self.cursor.execute(
		'INSERT into rundependenciesxt VALUES '
		'(?,?)'
		, (	idpackage,
			rdepxt,
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

	# neededlibs, a list
	for lib in etpData['neededlibs']:
	    self.cursor.execute(
		'INSERT into neededlibs VALUES '
		'(?,?)'
		, (	idpackage,
			lib,
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
	    self.cursor.execute(
		'INSERT into sources VALUES '
		'(?,?)'
		, (	idpackage,
			source,
			)
	    )

	# useflags, a list
	for flag in etpData['useflags']:
	    self.cursor.execute(
		'INSERT into useflags VALUES '
		'(?,?)'
		, (	idpackage,
			flag,
			)
	    )

	# keywords, a list
	for keyword in etpData['keywords']:
	    self.cursor.execute(
		'INSERT into keywords VALUES '
		'(?,?)'
		, (	idpackage,
			keyword,
			)
	    )

	# binkeywords, a list
	for binkeyword in etpData['binkeywords']:
	    self.cursor.execute(
		'INSERT into binkeywords VALUES '
		'(?,?)'
		, (	idpackage,
			binkeyword,
			)
	    )

	self.commitChanges()
	return True, revision, etpData

    # Update already available atom in db
    # returns True,revision if the package has been updated
    # returns False,revision if not
    def updatePackage(self, etpData, forceBump = False):

	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"updatePackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"updatePackage: called.")

        # prepare versiontag
	versiontag = ""
	if (etpData['versiontag']):
	    versiontag = "-"+etpData['versiontag']

	# are there any stable packages?
	searchsimilarStable = self.searchSimilarPackages(etpData['category']+"/"+etpData['name'], branch = "stable")
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: here is the list of similar stable packages found for "+etpData['category']+"/"+etpData['name']+": "+str(searchsimilarStable))
	# filter the one with the same version
	stableFound = False
	for pkg in searchsimilarStable:
	    # get version
	    idpackage = pkg[1]
	    dbStoredVer = self.retrieveVersion(idpackage)
	    dbStoredVerTag = self.retrieveVersionTag(idpackage)
	    if (etpData['version'] == dbStoredVer) and (etpData['versiontag'] == dbStoredVerTag):
	        # found it !
		stableFound = True
		break
	
	if (stableFound):
	    
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: found an old stable package, if etpData['neededlibs'] is equal, mark the branch of this updated package, stable too")
	    
	    # in this case, we should compare etpData['neededlibs'] with the db entry to see if there has been a API breakage
	    idpackage = self.getIDPackage(etpData['category'] + "/" + etpData['name'] + "-" + etpData['version']+versiontag,"stable")
	    dbStoredNeededLibs = self.retrieveNeededlibs(idpackage)
	    if (etpData['neededlibs'] == dbStoredNeededLibs):
		# it is safe to keep it as stable because of:
		# - name/version match
		# - same libraries requirements
		# setup etpData['branch'] accordingly
		etpData['branch'] = "stable"
		dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: yes, their etpData['neededlibs'] match, marking the new package stable.")


	# get selected package revision
	pkgatom = etpData['category'] + "/" + etpData['name'] + "-" + etpData['version']+versiontag
	idpackage = self.getIDPackage(pkgatom,etpData['branch'])
	
	if (idpackage != -1):
	    curRevision = self.retrieveRevision(idpackage)
	else:
	    curRevision = 0

	# do I really have to update the database entry? If the information are the same, drop all
	oldPkgAtom = etpData['category']+"/"+etpData['name']+"-"+etpData['version']+versiontag
	rc = self.comparePackagesData(etpData, oldPkgAtom, branchToQuery = etpData['branch'])
	if (rc) and (not forceBump):
	    return False, curRevision, etpData # in this case etpData content does not matter

	# OTHERWISE:
	# remove the current selected package, if exists
	if (idpackage != -1):
	    self.removePackage(idpackage)

	# bump revision nevertheless
	curRevision += 1

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: current revision set to "+str(curRevision))

	# add the new one
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: complete. Now spawning addPackage.")
	x,y,z = self.addPackage(etpData,curRevision,etpData['branch'])
	return x,y,z
	

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
	# rundependencies
	self.cursor.execute('DELETE FROM rundependencies WHERE idpackage = '+idpackage)
	# rundependenciesxt
	self.cursor.execute('DELETE FROM rundependenciesxt WHERE idpackage = '+idpackage)
	# conflicts
	self.cursor.execute('DELETE FROM conflicts WHERE idpackage = '+idpackage)
	# neededlibs
	self.cursor.execute('DELETE FROM neededlibs WHERE idpackage = '+idpackage)
	# sources
	self.cursor.execute('DELETE FROM sources WHERE idpackage = '+idpackage)
	# useflags
	self.cursor.execute('DELETE FROM useflags WHERE idpackage = '+idpackage)
	# keywords
	self.cursor.execute('DELETE FROM keywords WHERE idpackage = '+idpackage)
	# binkeywords
	self.cursor.execute('DELETE FROM binkeywords WHERE idpackage = '+idpackage)
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
	
    def addLicense(self,license):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addLicense: adding License -> "+str(license))
	self.cursor.execute(
		'INSERT into licenses VALUES '
		'(NULL,?)', (license,)
	)
	# get info about inserted value and return
	lic = self.isLicenseAvailable(license)
	if lic != -1:
	    self.commitChanges()
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
	    self.commitChanges()
	    return idflag
	raise Exception, "I tried to insert a flag tuple but then, fetching it returned -1. There's something broken."

    # WARNING: this function must be kept in sync with Entropy database schema
    # returns True if equal
    # returns False if not
    # FIXME: this must be fixed to work with branches
    def comparePackagesData(self, etpData, pkgAtomToQuery, branchToQuery = "unstable"):
	
	# fill content - get idpackage
	idpackage = self.getIDPackage(pkgAtomToQuery,branchToQuery)
	# get data
	myEtpData = self.getPackageData(idpackage)
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"comparePackagesData: called for "+str(etpData['name'])+" and "+str(myEtpData['name'])+" | branch: "+branchToQuery)
	
	for i in etpData:
	    if etpData[i] != myEtpData[i]:
		dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"comparePackagesData: they don't match")
		return False
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"comparePackagesData: they match")
	return True
    
    def getIDPackage(self, atom, branch = "unstable"):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getIDPackage: retrieving package ID for "+atom+" | branch: "+branch)
	self.cursor.execute('SELECT "IDPACKAGE" FROM baseinfo WHERE atom = "'+atom+'" AND branch = "'+branch+'"')
	idpackage = -1
	for row in self.cursor:
	    idpackage = int(row[0])
	    break
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

    def getPackageData(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getPackageData: retrieving etpData for package ID for "+str(idpackage))
	data = {}
	
	data['name'] = self.retrieveName(idpackage)
	data['version'] = self.retrieveVersion(idpackage)
	data['versiontag'] = self.retrieveVersionTag(idpackage)
	data['description'] = self.retrieveDescription(idpackage)
	data['category'] = self.retrieveCategory(idpackage)
	
	flags = self.retrieveCompileFlags(idpackage)
	data['chost'] = flags[0]
	data['cflags'] = flags[1]
	data['cxxflags'] = flags[2]
	
	data['homepage'] = self.retrieveHomepage(idpackage)
	data['useflags'] = self.retrieveUseflags(idpackage)
	data['license'] = self.retrieveLicense(idpackage)
	
	data['keywords'] = self.retrieveKeywords(idpackage)
	data['binkeywords'] = self.retrieveBinKeywords(idpackage)
	
	data['branch'] = self.retrieveBranch(idpackage)
	data['download'] = self.retrieveDownloadURL(idpackage)
	data['digest'] = self.retrieveDigest(idpackage)
	data['sources'] = self.retrieveSources(idpackage)
	
	mirrornames = []
	for x in data['sources']:
	    if x.startswith("mirror://"):
		mirrorname = x.split("/")[2]
		mirrornames.append(mirrorname)
	data['mirrorlinks'] = []
	for mirror in mirrornames:
	    mirrorlinks = self.retrieveMirrorInfo(mirror)
	    data['mirrorlinks'].append([mirror,mirrorlinks])
	
	data['slot'] = self.retrieveSlot(idpackage)
	data['content'] = self.retrieveContent(idpackage)
	
	data['dependencies'] = self.retrieveDependencies(idpackage)
	data['rundependencies'] = self.retrieveRunDependencies(idpackage)
	data['rundependenciesXT'] = self.retrieveRunDependenciesXt(idpackage)
	data['conflicts'] = self.retrieveConflicts(idpackage)
	
	data['etpapi'] = self.retrieveApi(idpackage)
	data['datecreation'] = self.retrieveDateCreation(idpackage)
	data['neededlibs'] = self.retrieveNeededlibs(idpackage)
	data['size'] = self.retrieveSize(idpackage)
	return data

    def retrieveAtom(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveAtom: retrieving Atom for package ID "+str(idpackage))
	self.cursor.execute('SELECT "atom" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	atom = ''
	for row in self.cursor:
	    atom = row[0]
	    break
	return atom

    def retrieveBranch(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveBranch: retrieving Branch for package ID "+str(idpackage))
	self.cursor.execute('SELECT "branch" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	atom = ''
	for row in self.cursor:
	    atom = row[0]
	    break
	return atom

    def retrieveDownloadURL(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDownloadURL: retrieving download URL for package ID "+str(idpackage))
	self.cursor.execute('SELECT "download" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	download = ''
	for row in self.cursor:
	    download = row[0]
	    break
	return download

    def retrieveDescription(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDescription: retrieving description for package ID "+str(idpackage))
	self.cursor.execute('SELECT "description" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	description = ''
	for row in self.cursor:
	    description = row[0]
	    break
	return description

    def retrieveHomepage(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveHomepage: retrieving Homepage for package ID "+str(idpackage))
	self.cursor.execute('SELECT "homepage" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	home = ''
	for row in self.cursor:
	    home = row[0]
	    break
	return home

    # in bytes
    def retrieveSize(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSize: retrieving Size for package ID "+str(idpackage))
	self.cursor.execute('SELECT "size" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	size = 'N/A'
	for row in self.cursor:
	    size = row[0]
	    break
	return size

    def retrieveDigest(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDigest: retrieving Digest for package ID "+str(idpackage))
	self.cursor.execute('SELECT "digest" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	digest = ''
	for row in self.cursor:
	    digest = row[0]
	    break
	return digest

    def retrieveName(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveName: retrieving Name for package ID "+str(idpackage))
	self.cursor.execute('SELECT "name" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	name = ''
	for row in self.cursor:
	    name = row[0]
	    break
	return name

    def retrieveVersion(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveVersion: retrieving Version for package ID "+str(idpackage))
	self.cursor.execute('SELECT "version" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = ''
	for row in self.cursor:
	    ver = row[0]
	    break
	return ver

    def retrieveRevision(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveRevision: retrieving Revision for package ID "+str(idpackage))
	self.cursor.execute('SELECT "revision" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	rev = ''
	for row in self.cursor:
	    rev = row[0]
	    break
	return rev

    def retrieveDateCreation(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDateCreation: retrieving Creation Date for package ID "+str(idpackage))
	self.cursor.execute('SELECT "datecreation" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	date = 'N/A'
	for row in self.cursor:
	    date = row[0]
	    break
	return date

    def retrieveApi(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"v: retrieving Database API for package ID "+str(idpackage))
	self.cursor.execute('SELECT "etpapi" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	api = -1
	for row in self.cursor:
	    api = row[0]
	    break
	return api
    
    def retrieveUseflags(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveUseflags: retrieving USE flags for package ID "+str(idpackage))
	self.cursor.execute('SELECT "flag" FROM useflags WHERE idpackage = "'+str(idpackage)+'"')
	flags = []
	for row in self.cursor:
	    flags.append(row[0])
	return flags

    def retrieveConflicts(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveConflicts: retrieving Conflicts for package ID "+str(idpackage))
	self.cursor.execute('SELECT "conflict" FROM conflicts WHERE idpackage = "'+str(idpackage)+'"')
	confl = []
	for row in self.cursor:
	    confl.append(row[0])
	return confl

    def retrieveDependencies(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDependencies: retrieving Dependencies for package ID "+str(idpackage))
	self.cursor.execute('SELECT "dependency" FROM dependencies WHERE idpackage = "'+str(idpackage)+'"')
	deps = []
	for row in self.cursor:
	    deps.append(row[0])
	return deps

    def retrieveRunDependencies(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveRunDependencies: retrieving Runtime Dependencies for package ID "+str(idpackage))
	self.cursor.execute('SELECT "dependency" FROM rundependencies WHERE idpackage = "'+str(idpackage)+'"')
	deps = []
	for row in self.cursor:
	    deps.append(row[0])
	return deps

    def retrieveRunDependenciesXt(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveRunDependenciesXt: retrieving Runtime Dependencies (+version) for package ID "+str(idpackage))
	self.cursor.execute('SELECT "dependency" FROM rundependenciesxt WHERE idpackage = "'+str(idpackage)+'"')
	deps = []
	for row in self.cursor:
	    deps.append(row[0])
	return deps

    def retrieveKeywords(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveKeywords: retrieving Keywords for package ID "+str(idpackage))
	self.cursor.execute('SELECT "keyword" FROM keywords WHERE idpackage = "'+str(idpackage)+'"')
	kw = []
	for row in self.cursor:
	    kw.append(row[0])
	return kw

    def retrieveBinKeywords(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveBinKeywords: retrieving Binary Keywords for package ID "+str(idpackage))
	self.cursor.execute('SELECT "binkeyword" FROM binkeywords WHERE idpackage = "'+str(idpackage)+'"')
	kw = []
	for row in self.cursor:
	    kw.append(row[0])
	return kw

    def retrieveSources(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSources: retrieving Sources for package ID "+str(idpackage))
	self.cursor.execute('SELECT "source" FROM sources WHERE idpackage = "'+str(idpackage)+'"')
	sw = []
	for row in self.cursor:
	    sw.append(row[0])
	return sw

    def retrieveContent(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveContent: retrieving Content for package ID "+str(idpackage))
	self.cursor.execute('SELECT "file" FROM content WHERE idpackage = "'+str(idpackage)+'"')
	fl = []
	for row in self.cursor:
	    fl.append(row[0])
	return fl

    def retrieveSlot(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSlot: retrieving Slot for package ID "+str(idpackage))
	self.cursor.execute('SELECT "slot" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = ''
	for row in self.cursor:
	    ver = row[0]
	    break
	return ver
    
    def retrieveVersionTag(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveVersionTag: retrieving Version TAG for package ID "+str(idpackage))
	self.cursor.execute('SELECT "versiontag" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = ''
	for row in self.cursor:
	    ver = row[0]
	    break
	return ver
    
    def retrieveNeededlibs(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveNeededlibs: retrieving Needed Libraries for package ID "+str(idpackage))
	self.cursor.execute('SELECT "library" FROM neededlibs WHERE idpackage = "'+str(idpackage)+'"')
	libs = []
	for row in self.cursor:
	    libs.append(row[0])
	return libs

    def retrieveMirrorInfo(self, mirrorname):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveMirrorInfo: retrieving Mirror info for mirror name "+str(mirrorname))
	self.cursor.execute('SELECT "mirrorlink" FROM mirrorlinks WHERE mirrorname = "'+str(mirrorname)+'"')
	mirrorlist = []
	for row in self.cursor:
	    mirrorlist.append(row[0])
	return mirrorlist

    def retrieveCategory(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveCategory: retrieving Category for package ID for "+str(idpackage))
	self.cursor.execute('SELECT "idcategory" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	cat = ''
	for row in self.cursor:
	    cat = row[0]
	    break
	# now get the category name
	self.cursor.execute('SELECT "category" FROM categories WHERE idcategory = '+str(cat))
	cat = -1
	for row in self.cursor:
	    cat = row[0]
	    break
	return cat

    def retrieveLicense(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveLicense: retrieving License for package ID for "+str(idpackage))
	self.cursor.execute('SELECT "idlicense" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	lic = -1
	for row in self.cursor:
	    lic = row[0]
	    break
	# now get the license name
	self.cursor.execute('SELECT "license" FROM licenses WHERE idlicense = '+str(lic))
	licname = ''
	for row in self.cursor:
	    licname = row[0]
	    break
	return licname

    def retrieveCompileFlags(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveCompileFlags: retrieving CHOST,CFLAGS,CXXFLAGS for package ID for "+str(idpackage))
	self.cursor.execute('SELECT "idflags" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	idflag = -1
	for row in self.cursor:
	    idflag = row[0]
	    break
	# now get the flags
	self.cursor.execute('SELECT chost,cflags,cxxflags FROM flags WHERE idflags = '+str(idflag))
	flags = ["N/A","N/A","N/A"]
	for row in self.cursor:
	    flags = row
	    break
	return flags

    # You must provide the full atom to this function
    # WARNING: this function does not support branches !!!
    def isPackageAvailable(self,pkgkey):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isPackageAvailable: called.")
	pkgkey = entropyTools.removePackageOperators(pkgkey)
	result = []
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE atom = "'+pkgkey+'"')
	for row in self.cursor:
	    result.append(row)
	if result == []:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isPackageAvailable: "+pkgkey+" not available.")
	    return False
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isPackageAvailable: "+pkgkey+" available.")
	return True

    def isIDPackageAvailable(self,idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isIDPackageAvailable: called.")
	result = []
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	for row in self.cursor:
	    result.append(row[0])
	if result == []:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isIDPackageAvailable: "+str(idpackage)+" not available.")
	    return False
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isIDPackageAvailable: "+str(idpackage)+" available.")
	return True

    # This version is more specific and supports branches
    def isSpecificPackageAvailable(self, pkgkey, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSpecificPackageAvailable: called.")
	pkgkey = entropyTools.removePackageOperators(pkgkey)
	result = []
	self.cursor.execute('SELECT idpackage FROM baseinfo WHERE atom = "'+pkgkey+'" AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row[0])
	if result == []:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isSpecificPackageAvailable: "+pkgkey+" | branch: "+branch+" -> not found.")
	    return False
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSpecificPackageAvailable: "+pkgkey+" | branch: "+branch+" -> found !")
	return True

    def isCategoryAvailable(self,category):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCategoryAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = "'+category+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isCategoryAvailable: "+category+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCategoryAvailable: "+category+" available.")
	return result

    def isLicenseAvailable(self,license):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isLicenseAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idlicense FROM licenses WHERE license = "'+license+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isLicenseAvailable: "+license+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isLicenseAvailable: "+license+" available.")
	return result

    def areCompileFlagsAvailable(self,chost,cflags,cxxflags):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"areCompileFlagsAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idflags FROM flags WHERE chost = "'+chost+'" AND cflags = "'+cflags+'" AND cxxflags = "'+cxxflags+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"areCompileFlagsAvailable: flags tuple "+chost+"|"+cflags+"|"+cxxflags+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"areCompileFlagsAvailable: flags tuple "+chost+"|"+cflags+"|"+cxxflags+" available.")
	return result

    def searchPackages(self, keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackages: called for "+keyword)
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE atom LIKE "%'+keyword+'%"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesInBranch(self, keyword, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesInBranch: called.")
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE atom LIKE "%'+keyword+'%" AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesByName(self, keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesByName: called for "+keyword)
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+keyword+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesInBranchByName(self, keyword, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesInBranchByName: called for "+keyword)
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+keyword+'" AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesInBranchByNameAndCategory(self, name, category, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesInBranchByNameAndCategory: called for "+name+" and category "+category)
	result = []
	# get category id
	idcat = -1
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = "'+category+'"')
	for row in self.cursor:
	    idcat = row[0]
	    break
	if idcat == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"searchPackagesInBranchByNameAndCategory: Category "+category+" not available.")
	    return result
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+name+'" AND idcategory = '+str(idcat)+' AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesInBranchByNameAndVersionAndCategory(self, name, version, category, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesInBranchByNameAndVersionAndCategoryAndTag: called for "+name+" and version "+version+" and category "+category+" | branch "+branch)
	result = []
	# get category id
	idcat = -1
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = "'+category+'"')
	for row in self.cursor:
	    idcat = row[0]
	    break
	if idcat == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"searchPackagesInBranchByNameAndVersionAndCategoryAndTag: Category "+category+" not available.")
	    return result
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+name+'" AND version = "'+version+'" AND idcategory = '+str(idcat)+' AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    # this function search packages with the same pkgcat/pkgname
    # you must provide something like: media-sound/amarok
    # optionally, you can add version too.
    def searchSimilarPackages(self, atom, branch = "unstable"):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchSimilarPackages: called for "+atom+" | branch: "+branch)
	category = atom.split("/")[0]
	name = atom.split("/")[1]
	# get category id
	idcategory = self.getIDCategory(category)
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE idcategory = "'+str(idcategory)+'" AND name = "'+name+'" AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    # NOTE: unstable and stable packages are pulled in
    # so, there might be duplicates! that's normal
    def listAllPackages(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllPackages: called.")
	self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo')
	result = []
	for row in self.cursor:
	    result.append(row)
	return result

    # FIXME: listAllPackages now retrieves branch too
    def listAllPackagesTbz2(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllPackagesTbz2: called.")
        result = []
        pkglist = self.listAllPackages()
        for pkg in pkglist:
	    idpackage = pkg[1]
	    url = self.retrieveDownloadURL(idpackage)
	    if url:
		result.append(os.path.basename(url))
        # filter dups?
	if (result):
            result = list(set(result))
	return result

    def listStablePackages(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listStablePackages: called.")
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE branch = "stable"')
	for row in self.cursor:
	    result.append(row)
	return result

    def listUnstablePackages(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listUnstablePackages: called. ")
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE branch = "unstable"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchStablePackages(self,atom):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchStablePackages: called for "+atom)
	category = atom.split("/")[0]
	name = atom.split("/")[1]
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE category = "'+category+'" AND name = "'+name+'" AND branch = "stable"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchUnstablePackages(self,atom):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchUnstablePackages: called for "+atom)
	category = atom.split("/")[0]
	name = atom.split("/")[1]
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE category = "'+category+'" AND name = "'+name+'" AND branch = "stable"')
	for row in self.cursor:
	    result.append(row)
	return result

    # useful to quickly retrieve (and trash) all the data
    # and look for problems.
    def noopCycle(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"noopCycle: called. ")
	self.cursor.execute('SELECT * FROM baseinfo')
	self.cursor.execute('SELECT * FROM extrainfo')
	self.cursor.execute('SELECT * FROM content')
	self.cursor.execute('SELECT * FROM dependencies')
	self.cursor.execute('SELECT * FROM rundependencies')
	self.cursor.execute('SELECT * FROM conflicts')
	self.cursor.execute('SELECT * FROM neededlibs')
	self.cursor.execute('SELECT * FROM mirrorlinks')
	self.cursor.execute('SELECT * FROM sources')
	self.cursor.execute('SELECT * FROM useflags')
	self.cursor.execute('SELECT * FROM keywords')
	self.cursor.execute('SELECT * FROM binkeywords')
	self.cursor.execute('SELECT * FROM categories')
	self.cursor.execute('SELECT * FROM licenses')
	self.cursor.execute('SELECT * FROM flags')
	

    def stabilizePackage(self,atom,stable = True):

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"stabilizePackage: called for "+atom+" | branch stable? -> "+str(stable))

	action = "unstable"
	removeaction = "stable"
	if (stable):
	    action = "stable"
	    removeaction = "unstable"
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"stabilizePackage: add action: "+action+" | remove action: "+removeaction)
	
	if (self.isSpecificPackageAvailable(atom, removeaction)):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"stabilizePackage: there's something old that needs to be removed.")
	    idpackage = self.getIDPackage(atom, branch = removeaction)
	    
	    pkgname = self.retrieveName(idpackage)
	    # get its pkgcat
	    category = self.retrieveCategory(idpackage)
	    # search packages with similar pkgcat/name marked as stable
	    slot = self.retrieveSlot(idpackage)
	    
	    # we need to get rid of them
	    results = self.searchStablePackages(category+"/"+pkgname)
	    
	    removelist = []
	    for result in results:
		myidpackage = result[1]
		# have a look if the slot matches
		#print result
		myslot = self.retrieveSlot(myidpackage)
		if (myslot == slot):
		    removelist.append(result[1])
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"stabilizePackage: removelist: "+str(removelist))
	    for pkg in removelist:
		self.removePackage(pkg)
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"stabilizePackage: updating "+atom+" setting branch: "+action)
	    
	    self.cursor.execute('UPDATE baseinfo SET branch = "'+action+'" WHERE idpackage = "'+idpackage+'"')
	    self.commitChanges()
	    
	    return True,action
	return False,action
	