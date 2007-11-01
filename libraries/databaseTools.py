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
import sys
import string

# Logging initialization
import logTools
dbLog = logTools.LogFile(level = etpConst['databaseloglevel'],filename = etpConst['databaselogfile'], header = "[DBase]")


def database(options):

    import activatorTools
    import reagentTools
    import mirrorTools

    databaseRequestNoAsk = False
    _options = []
    for opt in options:
	if opt.startswith("--noask"):
	    databaseRequestNoAsk = True
	else:
	    _options.append(opt)
    options = _options

    if len(options) == 0:
	print_error(yellow(" * ")+red("Not enough parameters"))
	sys.exit(301)

    if (options[0] == "--initialize"):
	
	# do some check, print some warnings
	print_info(green(" * ")+red("Initializing Entropy database..."), back = True)
        # database file: etpConst['etpdatabasefilepath']
	revisionsMatch = {}
        if os.path.isfile(etpConst['etpdatabasefilepath']):
	    try:
		dbconn = etpDatabase(readOnly = True, noUpload = True)
		idpackages = dbconn.listAllIdpackages()
		for idpackage in idpackages:
		    package = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
		    branch = dbconn.retrieveBranch(idpackage)
		    revision = dbconn.retrieveRevision(idpackage)
		    revisionsMatch[package] = [branch,revision]
		dbconn.closeDB()
	    except:
		pass
	    print_info(red(" * ")+bold("WARNING")+red(": database file already exists. Overwriting."))
	    rc = entropyTools.askquestion("\n     Do you want to continue ?")
	    if rc == "No":
	        sys.exit(0)
	    os.remove(etpConst['etpdatabasefilepath'])

	# initialize the database
        dbconn = etpDatabase(readOnly = False, noUpload = True)
	dbconn.initializeDatabase()
	
	# sync packages directory
	print "Revisions dump:"
	print revisionsMatch
	activatorTools.packages(["sync","--ask"])
	
	# now fill the database
	pkgbranches = os.listdir(etpConst['packagesbindir'])
	pkgbranches = [x for x in pkgbranches if os.path.isdir(etpConst['packagesbindir']+"/"+x)]
	#print revisionsMatch
	for mybranch in pkgbranches:
	
	    pkglist = os.listdir(etpConst['packagesbindir']+"/"+mybranch)
	
	    # filter .md5
	    _pkglist = []
	    for i in pkglist:
	        if not i.endswith(etpConst['packageshashfileext']):
		    _pkglist.append(i)
	    pkglist = _pkglist
	    if (not pkglist):
		continue

	    print_info(green(" * ")+red("Reinitializing Entropy database for branch ")+bold(mybranch)+red(" using Packages in the repository ..."))
	    currCounter = 0
	    atomsnumber = len(pkglist)
	    import reagentTools
	    
	    for pkg in pkglist:
		
	        print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+red("Analyzing: ")+bold(pkg), back = True)
	        currCounter += 1
	        print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+green("(")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(pkg)+red(" ..."), back = True)
		
	        etpData = reagentTools.extractPkgData(etpConst['packagesbindir']+"/"+mybranch+"/"+pkg, mybranch)
	        # get previous revision
		revisionAvail = revisionsMatch.get(os.path.basename(etpData['download']),None)
		addRevision = 0
		if (revisionAvail):
		    if mybranch == revisionAvail[0]:
			addRevision = revisionAvail[1]
	        # fill the db entry
	        idpk, revision, etpDataUpdated, accepted = dbconn.addPackage(etpData, revision = addRevision, wantedBranch = mybranch)
		
		print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+green("(")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(pkg)+red(". Revision: ")+blue(str(addRevision)))
	    
	    dbconn.commitChanges()
	
	# regen dependstable
        reagentTools.dependsTableInitialize(dbconn, False)
	
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
		
		conflicts = dbconn.retrieveConflicts(result[1])
		if (conflicts):
		    print_info(red("\t Conflicts with"))
		    for conflict in conflicts:
			print_info(darkred("\t    # Conflict: ")+conflict)
		
		api = dbconn.retrieveApi(result[1])
		print_info(red("\t Entry API: ")+green(str(api)))
		
		date = dbconn.retrieveDateCreation(result[1])
		print_info(red("\t Package Creation date: ")+str(entropyTools.convertUnixTimeToHumanTime(float(date))))
		
		revision = dbconn.retrieveRevision(result[1])
		print_info(red("\t Entry revision: ")+str(revision))
		#print result
		
	dbconn.closeDB()
	if (foundCounter == 0):
	    print_warning(red(" * ")+red("Nothing found."))
	else:
	    print

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

    elif (options[0] == "stabilize") or (options[0] == "unstabilize"): # FIXME: adapt to the new branches structure

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

    elif (options[0] == "remove"):

	print_info(green(" * ")+red("Scanning packages that would be removed ..."), back = True)
	
	myopts = options[1:]
	_myopts = []
	branch = ''
	for opt in myopts:
	    if (opt.startswith("--branch=")) and (len(opt.split("=")) == 2):
		
		try:
		    branch = opt.split("=")[1]
		    idx = etpConst['branches'].index(branch)
		    etpConst['branch'] = branch
		except:
		    pass
	    else:
		_myopts.append(opt)
	myopts = _myopts
	
	if len(myopts) == 0:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    sys.exit(303)

	pkglist = []
	dbconn = etpDatabase(readOnly = True)
	
	for atom in myopts:
	    pkg = dbconn.atomMatch(atom)
	    if pkg[0] != -1:
	        pkglist.append(pkg[0])

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
	    pkgatom = dbconn.retrieveAtom(pkg)
	    branch = dbconn.retrieveBranch(pkg)
	    print_info(red("\t (*) ")+bold(pkgatom)+blue(" [")+red(branch)+blue("]"))

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
	    pkgatom = dbconn.retrieveAtom(pkg)
	    print_info(green(" * ")+red("Removing package: ")+bold(pkgatom)+red(" ..."), back = True)
	    dbconn.removePackage(pkg)
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

	if (not worldSelected):
	    print_info(red("   This is the list of the packages that would be checked:"))
	else:
	    print_info(red("   All the packages in the Entropy Packages repository will be checked."))
	
	toBeDownloaded = []
	availList = []
	for pkginfo in pkgs2check:
	
	    pkgatom = pkginfo[0]
	    idpackage = pkginfo[1]
	    pkgbranch = pkginfo[2]
	    pkgfile = dbconn.retrieveDownloadURL(idpackage)
	    pkgfile = os.path.basename(pkgfile)
	    if (os.path.isfile(etpConst['packagesbindir']+"/"+pkgbranch+"/"+pkgfile)):
		if (not worldSelected): print_info(green("   - [PKG AVAILABLE] ")+red(pkgatom)+" -> "+bold(pkgfile))
		availList.append(idpackage)
	    elif (os.path.isfile(etpConst['packagessuploaddir']+"/"+pkgbranch+"/"+pkgfile)):
		if (not worldSelected): print_info(green("   - [RUN ACTIVATOR] ")+darkred(pkgatom)+" -> "+bold(pkgfile))
	    else:
		if (not worldSelected): print_info(green("   - [MUST DOWNLOAD] ")+yellow(pkgatom)+" -> "+bold(pkgfile))
		toBeDownloaded.append([idpackage,pkgfile,pkgbranch])
	
	if (not databaseRequestNoAsk):
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
		    rc = activatorTools.downloadPackageFromMirror(uri,pkg[1],pkg[2])
		    if (rc is None):
			notDownloadedPackages.append([pkg[1],pkg[2]])
		    if (rc == False):
			notDownloadedPackages.append([pkg[1],pkg[2]])
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
		    print_warning(red("    * ")+yellow(i[0])+" in "+blue(i[1]))
		print_warning(red("   They won't be checked."))
	
	brokenPkgsList = []
	totalcounter = str(len(availList))
	currentcounter = 0
	for pkg in availList:
	    currentcounter += 1
	    pkgfile = dbconn.retrieveDownloadURL(pkg)
	    pkgbranch = dbconn.retrieveBranch(pkg)
	    pkgfile = os.path.basename(pkgfile)
	    print_info("  ("+red(str(currentcounter))+"/"+blue(totalcounter)+") "+red("Checking hash of ")+yellow(pkgfile)+red(" in branch: ")+blue(pkgbranch)+red(" ..."), back = True)
	    storedmd5 = dbconn.retrieveDigest(pkg)
	    result = entropyTools.compareMd5(etpConst['packagesbindir']+"/"+pkgbranch+"/"+pkgfile,storedmd5)
	    if (result):
		# match !
		pkgMatch += 1
		#print_info(red("   Package ")+yellow(pkg)+green(" is healthy. Checksum: ")+yellow(storedmd5), back = True)
	    else:
		pkgNotMatch += 1
		print_error(red("   Package ")+yellow(pkgfile)+red(" in branch: ")+blue(pkgbranch)+red(" is _NOT_ healthy !!!! Stored checksum: ")+yellow(storedmd5))
		brokenPkgsList.append([pkgfile,pkgbranch])

	dbconn.closeDB()

	if (brokenPkgsList != []):
	    print_info(blue(" *  This is the list of the BROKEN packages: "))
	    for bp in brokenPkgsList:
		print_info(red("    * Package file: ")+bold(bp[0])+red(" in branch: ")+blue(bp[1]))

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

    def __init__(self, readOnly = False, noUpload = False, dbFile = etpConst['etpdatabasefilepath'], clientDatabase = False, xcache = True, dbname = 'etpdb'):
	
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"etpDatabase.__init__ called.")
	
	self.readOnly = readOnly
	self.noUpload = noUpload
	self.packagesRemoved = False
	self.packagesAdded = False
	self.clientDatabase = clientDatabase
	self.xcache = xcache
	self.dbname = dbname
	
	# caching dictionaries
	
	if self.xcache:
	    ''' database query cache '''
	    broken1 = False
	    dbinfo = dbCacheStore.get(etpCache['dbInfo']+self.dbname)
	    if dbinfo == None:
		dbCacheStore[etpCache['dbInfo']+self.dbname] = dumpTools.loadobj(etpCache['dbInfo']+self.dbname)
	        if dbCacheStore[etpCache['dbInfo']+self.dbname] == None:
		    broken1 = True
		    dbCacheStore[etpCache['dbInfo']+self.dbname] = {}

	    ''' database atom dependencies cache '''
	    dbmatch = dbCacheStore.get(etpCache['dbMatch']+self.dbname)
	    broken2 = False
	    if dbmatch == None:
	        dbCacheStore[etpCache['dbMatch']+self.dbname] = dumpTools.loadobj(etpCache['dbMatch']+self.dbname)
	        if dbCacheStore[etpCache['dbMatch']+self.dbname] == None:
		    broken2 = True
		    dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
	
	    if (broken1 or broken2):
		# discard both caches
		dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
		dbCacheStore[etpCache['dbInfo']+self.dbname] = {}
		dumpTools.dumpobj(etpCache['dbMatch']+self.dbname,{})
		dumpTools.dumpobj(etpCache['dbInfo']+self.dbname,{})
		
	else:
	    dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
	    dbCacheStore[etpCache['dbInfo']+self.dbname] = {}

	
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

    # this function manages the submitted package
    # if it does not exist, it fires up addPackage
    # otherwise it fires up updatePackage
    def handlePackage(self, etpData, forcedRevision = -1, forcedBranch = False):

	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlePackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

        # prepare versiontag
	versiontag = ""
	if (etpData['versiontag']):
	    versiontag = "-"+etpData['versiontag']

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"handlePackage: called.")
	if (not self.isPackageAvailable(etpData['category']+"/"+etpData['name']+"-"+etpData['version']+versiontag)):
	    if (forcedRevision < 0):
		forcedRevision = 0
	    if (forcedBranch):
	        idpk, revision, etpDataUpdated, accepted = self.addPackage(etpData, revision = forcedRevision, wantedBranch = etpData['branch'])
	    else:
		idpk, revision, etpDataUpdated, accepted = self.addPackage(etpData, revision = forcedRevision)
	else:
	    idpk, revision, etpDataUpdated, accepted = self.updatePackage(etpData, forcedRevision) # branch and revision info will be overwritten
	return idpk, revision, etpDataUpdated, accepted


    def addPackage(self, etpData, revision = 0, wantedBranch = etpConst['branch']):

	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addPackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addPackage: called.")
	
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
	    self.cursor.execute(
		'INSERT into content VALUES '
		'(?,?)'
		, (	idpackage,
			file,
			)
	    )
	
	# counter, if != -1
	try:
	    if etpData['counter'] != -1:
	        self.cursor.execute(
	        'INSERT into counters VALUES '
	        '(?,?)'
	        , (	etpData['counter'],
		    idpackage,
		    )
	        )
	except:
	    pass # FIXME: temp woraround, add check for clientDbconn
	
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
	# dump to be sure
	dumpTools.dumpobj(etpCache['dbInfo']+self.dbname,{})
	dumpTools.dumpobj(etpCache['dbMatch']+self.dbname,{})

	self.packagesAdded = True
	self.commitChanges()
	
	return idpackage, revision, etpData, True

    # Update already available atom in db
    # returns True,revision if the package has been updated
    # returns False,revision if not
    def updatePackage(self, etpData, forcedRevision = -1):

	if (self.readOnly):
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"updatePackage: Cannot handle this in read only.")
	    raise Exception, "What are you trying to do?"

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"updatePackage: called.")

        # prepare versiontag
	versiontag = ""
	if (etpData['versiontag']):
	    versiontag = "-"+etpData['versiontag']
	# build atom string
	pkgatom = etpData['category'] + "/" + etpData['name'] + "-" + etpData['version']+versiontag

	# if client opened the database, before starting the update, remove previous entries - same atom, all branches
	if (self.clientDatabase):
	    
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"updatePackage: client request. Removing duplicated entries.")
	    atomInfos = self.searchPackages(pkgatom)
	    for atomInfo in atomInfos:
		idpackage = atomInfo[1]
		self.removePackage(idpackage)
	    
	    if (forcedRevision < 0):
		forcedRevision = 0 # FIXME: this shouldn't happen
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"updatePackage: removal complete. Now spawning addPackage.")
	    x,y,z,accepted = self.addPackage(etpData, revision = forcedRevision, wantedBranch = etpData['branch'])
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
	    x,y,z,accepted = self.addPackage(etpData, revision = curRevision, wantedBranch = etpData['branch'])
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
	# systempackage
	self.cursor.execute('DELETE FROM systempackages WHERE idpackage = '+idpackage)
	try:
	    # counter
	    self.cursor.execute('DELETE FROM counters WHERE idpackage = '+idpackage)
	except:
	    pass
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
	
	# Remove from installedtable if exists
	self.removePackageFromInstalledTable(idpackage)
	# Remove from dependstable if exists
	self.removePackageFromDependsTable(idpackage)
	# need a final cleanup
	self.packagesRemoved = True

	# clear caches
	dbCacheStore[etpCache['dbInfo']+self.dbname] = {}
	dbCacheStore[etpCache['dbMatch']+self.dbname] = {}
	# dump to be sure
	dumpTools.dumpobj(etpCache['dbInfo']+self.dbname,{})
	dumpTools.dumpobj(etpCache['dbMatch']+self.dbname,{})

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
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"setChecksum: setting new digest for idpackage: "+str(idpackage)+" -> "+str(digest))
	self.cursor.execute('UPDATE extrainfo SET digest = "'+str(digest)+'" WHERE idpackage = "'+str(idpackage)+'"')

    def cleanupUseflags(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupUseflags: called.")
	self.cursor.execute('SELECT idflag FROM useflagsreference')
	idflags = set([])
	for row in self.cursor:
	    idflags.add(row[0])
	# now parse them into useflags table
	orphanedFlags = idflags.copy()
	for idflag in idflags:
	    self.cursor.execute('SELECT idflag FROM useflags WHERE idflag = '+str(idflag))
	    for row in self.cursor:
		orphanedFlags.remove(row[0])
		break
	# now we have orphans that can be removed safely
	for idoflag in orphanedFlags:
	    self.cursor.execute('DELETE FROM useflagsreference WHERE idflag = '+str(idoflag))
	for row in self.cursor:
	    x = row # really necessary ?

    def cleanupSources(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupSources: called.")
	self.cursor.execute('SELECT idsource FROM sourcesreference')
	idsources = set([])
	for row in self.cursor:
	    idsources.add(row[0])
	# now parse them into useflags table
	orphanedSources = idsources.copy()
	for idsource in idsources:
	    self.cursor.execute('SELECT idsource FROM sources WHERE idsource = '+str(idsource))
	    for row in self.cursor:
		orphanedSources.remove(row[0])
		break
	# now we have orphans that can be removed safely
	for idosrc in orphanedSources:
	    self.cursor.execute('DELETE FROM sourcesreference WHERE idsource = '+str(idosrc))
	for row in self.cursor:
	    x = row # really necessary ?

    def cleanupEclasses(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupEclasses: called.")
	self.cursor.execute('SELECT idclass FROM eclassesreference')
	idclasses = set([])
	for row in self.cursor:
	    idclasses.add(row[0])
	# now parse them into eclasses table
	orphanedClasses = idclasses.copy()
	for idclass in idclasses:
	    self.cursor.execute('SELECT idclass FROM eclasses WHERE idclass = '+str(idclass))
	    for row in self.cursor:
		orphanedClasses.remove(row[0])
		break
	# now we have orphans that can be removed safely
	for idoclass in orphanedClasses:
	    self.cursor.execute('DELETE FROM eclassesreference WHERE idclass = '+str(idoclass))
	for row in self.cursor:
	    x = row # really necessary ?

    def cleanupNeeded(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupNeeded: called.")
	self.cursor.execute('SELECT idneeded FROM neededreference')
	idneededs = set([])
	for row in self.cursor:
	    idneededs.add(row[0])
	# now parse them into needed table
	orphanedNeededs = idneededs.copy()
	for idneeded in idneededs:
	    self.cursor.execute('SELECT idneeded FROM needed WHERE idneeded = '+str(idneeded))
	    for row in self.cursor:
		orphanedNeededs.remove(row[0])
		break
	# now we have orphans that can be removed safely
	for idoneeded in orphanedNeededs:
	    self.cursor.execute('DELETE FROM neededreference WHERE idneeded = '+str(idoneeded))
	for row in self.cursor:
	    x = row # really necessary ?

    def cleanupDependencies(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanupDependencies: called.")
	self.cursor.execute('SELECT iddependency FROM dependenciesreference')
	iddeps = set([])
	for row in self.cursor:
	    iddeps.add(row[0])
	# now parse them into useflags table
	orphanedDeps = iddeps.copy()
	for iddep in iddeps:
	    self.cursor.execute('SELECT iddependency FROM dependencies WHERE iddependency = '+str(iddep))
	    for row in self.cursor:
		orphanedDeps.remove(row[0])
		break
	# now we have orphans that can be removed safely
	for idodep in orphanedDeps:
	    self.cursor.execute('DELETE FROM dependenciesreference WHERE iddependency = '+str(idodep))
	for row in self.cursor:
	    x = row # really necessary ?

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

    def getPackageData(self, idpackage): # FIXME: add caching
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
	data['counter'] = self.retrieveCounter(idpackage)
	data['messages'] = self.retrieveMessages(idpackage)
	
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
	data['provide'] = self.retrieveProvide(idpackage)
	data['conflicts'] = self.retrieveConflicts(idpackage)
	
	data['etpapi'] = self.retrieveApi(idpackage)
	data['datecreation'] = self.retrieveDateCreation(idpackage)
	data['size'] = self.retrieveSize(idpackage)
	data['disksize'] = self.retrieveOnDiskSize(idpackage)
	return data

    def retrieveAtom(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveAtom: retrieving Atom for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveAtom',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "atom" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	atom = ''
	for row in self.cursor:
	    atom = row[0]
	    break
	
	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveAtom'] = atom
	return atom

    def retrieveBranch(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveBranch: retrieving Branch for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveBranch',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "branch" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	br = ''
	for row in self.cursor:
	    br = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveBranch'] = br
	return br

    def retrieveDownloadURL(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDownloadURL: retrieving download URL for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveDownloadURL',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "download" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	download = ''
	for row in self.cursor:
	    download = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveDownloadURL'] = download
	return download

    def retrieveDescription(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDescription: retrieving description for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveDescription',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "description" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	description = ''
	for row in self.cursor:
	    description = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveDescription'] = description
	return description

    def retrieveHomepage(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveHomepage: retrieving Homepage for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveHomepage',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "homepage" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	home = ''
	for row in self.cursor:
	    home = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveHomepage'] = home
	return home

    def retrieveCounter(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveCounter: retrieving Counter for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveCounter',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	counter = -1
	try:
	    self.cursor.execute('SELECT "counter" FROM counters WHERE idpackage = "'+str(idpackage)+'"')
	    for row in self.cursor:
	        counter = row[0]
	        break
	except:
	    pass

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveCounter'] = counter
	return counter

    def retrieveMessages(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveMessages: retrieving messages for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveMessages',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	messages = []
	try:
	    self.cursor.execute('SELECT "message" FROM messages WHERE idpackage = "'+str(idpackage)+'"')
	    for row in self.cursor:
	        messages.append(row[0])
	except:
	    pass

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveMessages'] = messages
	return messages

    # in bytes
    def retrieveSize(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSize: retrieving Size for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveSize',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "size" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	size = 'N/A'
	for row in self.cursor:
	    size = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveSize'] = size
	return size

    # in bytes
    def retrieveOnDiskSize(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveOnDiskSize: retrieving On Disk Size for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveOnDiskSize',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	try:
	    self.cursor.execute('SELECT size FROM sizes WHERE idpackage = "'+str(idpackage)+'"')
	except:
	    # table does not exist?
	    return 0
	size = 0
	for row in self.cursor:
	    size = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveOnDiskSize'] = size
	return size

    def retrieveDigest(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDigest: retrieving Digest for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveDigest',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "digest" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	digest = ''
	for row in self.cursor:
	    digest = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveDigest'] = digest
	return digest

    def retrieveName(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveName: retrieving Name for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveName',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "name" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	name = ''
	for row in self.cursor:
	    name = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveName'] = name
	return name

    def retrieveVersion(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveVersion: retrieving Version for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveVersion',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}
	
	self.cursor.execute('SELECT "version" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = ''
	for row in self.cursor:
	    ver = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveVersion'] = ver
	return ver

    def retrieveRevision(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveRevision: retrieving Revision for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveRevision',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "revision" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	rev = ''
	for row in self.cursor:
	    rev = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveRevision'] = rev
	return rev

    def retrieveDateCreation(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDateCreation: retrieving Creation Date for package ID "+str(idpackage))
	
	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveDateCreation',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "datecreation" FROM extrainfo WHERE idpackage = "'+str(idpackage)+'"')
	date = 'N/A'
	for row in self.cursor:
	    date = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveDateCreation'] = date
	return date

    def retrieveApi(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveApi: retrieving Database API for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveApi',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "etpapi" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	api = -1
	for row in self.cursor:
	    api = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveApi'] = api
	return api

    def retrieveUseflags(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveUseflags: retrieving USE flags for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveUseflags',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "idflag" FROM useflags WHERE idpackage = "'+str(idpackage)+'"')
	idflgs = []
	for row in self.cursor:
	    idflgs.append(row[0])
	flags = []
	for idflg in idflgs:
	    self.cursor.execute('SELECT "flagname" FROM useflagsreference WHERE idflag = "'+str(idflg)+'"')
	    for row in self.cursor:
	        flags.append(row[0])

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveUseflags'] = flags
	return flags

    def retrieveEclasses(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveEclasses: retrieving eclasses for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveEclasses',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "idclass" FROM eclasses WHERE idpackage = "'+str(idpackage)+'"')
	idclasses = []
	for row in self.cursor:
	    idclasses.append(row[0])
	classes = []
	for idclass in idclasses:
	    self.cursor.execute('SELECT "classname" FROM eclassesreference WHERE idclass = "'+str(idclass)+'"')
	    for row in self.cursor:
	        classes.append(row[0])

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveEclasses'] = classes
	return classes

    def retrieveNeeded(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveNeeded: retrieving needed libraries for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveNeeded',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "idneeded" FROM needed WHERE idpackage = "'+str(idpackage)+'"')
	idneededs = set()
	for row in self.cursor:
	    idneededs.add(row[0])
	needed = set()
	for idneeded in idneededs:
	    self.cursor.execute('SELECT "library" FROM neededreference WHERE idneeded = "'+str(idneeded)+'"')
	    for row in self.cursor:
	        needed.add(row[0])

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveNeeded'] = needed
	return needed

    def retrieveConflicts(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveEclasses: retrieving Conflicts for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveConflicts',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "conflict" FROM conflicts WHERE idpackage = "'+str(idpackage)+'"')
	confl = []
	for row in self.cursor:
	    confl.append(row[0])

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveConflicts'] = confl
	return confl

    def retrieveProvide(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveProvide: retrieving Provide for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveProvide',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "atom" FROM provide WHERE idpackage = "'+str(idpackage)+'"')
	provide = []
	for row in self.cursor:
	    provide.append(row[0])
	
	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveProvide'] = provide
	return provide

    def retrieveDependencies(self, idpackage):
	#dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDependencies: retrieving dependency for package ID "+str(idpackage)) # too slow?

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveDependencies',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}
	
	self.cursor.execute('SELECT iddependency FROM dependencies WHERE idpackage = "'+str(idpackage)+'"')
	iddeps = []
	for row in self.cursor:
	    iddeps.append(row[0])
	deps = []
	for iddep in iddeps:
	    self.cursor.execute('SELECT dependency FROM dependenciesreference WHERE iddependency = "'+str(iddep)+'"')
	    for row in self.cursor:
		deps.append(row[0])
	
	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveDependencies'] = deps
	return deps

    def retrieveIdDependencies(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveIdDependencies: retrieving Dependencies for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveIdDependencies',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT iddependency FROM dependencies WHERE idpackage = "'+str(idpackage)+'"')
	iddeps = []
	for row in self.cursor:
	    iddeps.append(row[0])

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveIdDependencies'] = iddeps
	return iddeps

    def retrieveBinKeywords(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveBinKeywords: retrieving Binary Keywords for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveBinKeywords',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "idkeyword" FROM binkeywords WHERE idpackage = "'+str(idpackage)+'"')
	idkws = []
	for row in self.cursor:
	    idkws.append(row[0])
	kw = []
	for idkw in idkws:
	    self.cursor.execute('SELECT "keywordname" FROM keywordsreference WHERE idkeyword = "'+str(idkw)+'"')
	    for row in self.cursor:
	        kw.append(row[0])

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveBinKeywords'] = kw
	return kw

    def retrieveKeywords(self, idpackage):

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveKeywords',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveKeywords: retrieving Keywords for package ID "+str(idpackage))
	self.cursor.execute('SELECT "idkeyword" FROM keywords WHERE idpackage = "'+str(idpackage)+'"')
	idkws = []
	for row in self.cursor:
	    idkws.append(row[0])
	kw = []
	for idkw in idkws:
	    self.cursor.execute('SELECT "keywordname" FROM keywordsreference WHERE idkeyword = "'+str(idkw)+'"')
	    for row in self.cursor:
	        kw.append(row[0])

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveKeywords'] = kw
	return kw

    def retrieveProtect(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveProtect: retrieving CONFIG_PROTECT for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveProtect',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "idprotect" FROM configprotect WHERE idpackage = "'+str(idpackage)+'"')
	idprotect = -1
	for row in self.cursor:
	    idprotect = row[0]
	    break
	protect = ''
	if idprotect == -1:
	    return protect
	self.cursor.execute('SELECT "protect" FROM configprotectreference WHERE idprotect = "'+str(idprotect)+'"')
	for row in self.cursor:
	    protect = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveProtect'] = protect
	return protect

    def retrieveProtectMask(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveProtectMask: retrieving CONFIG_PROTECT_MASK for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveProtectMask',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "idprotect" FROM configprotectmask WHERE idpackage = "'+str(idpackage)+'"')
	idprotect = -1
	for row in self.cursor:
	    idprotect = row[0]
	    break
	protect = ''
	if idprotect == -1:
	    return protect
	self.cursor.execute('SELECT "protect" FROM configprotectreference WHERE idprotect = "'+str(idprotect)+'"')
	for row in self.cursor:
	    protect = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveProtectMask'] = protect
	return protect

    def retrieveSources(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSources: retrieving Sources for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveSources',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT idsource FROM sources WHERE idpackage = "'+str(idpackage)+'"')
	idsources = []
	for row in self.cursor:
	    idsources.append(row[0])
	sources = []
	for idsource in idsources:
	    self.cursor.execute('SELECT source FROM sourcesreference WHERE idsource = "'+str(idsource)+'"')
	    for row in self.cursor:
		sources.append(row[0])

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveSources'] = sources
	return sources

    def retrieveContent(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveContent: retrieving Content for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveContent',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "file" FROM content WHERE idpackage = "'+str(idpackage)+'"')
	fl = []
	for row in self.cursor:
	    fl.append(row[0])

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveContent'] = fl
	return fl

    def retrieveSlot(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveSlot: retrieving Slot for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveSlot',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "slot" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = ''
	for row in self.cursor:
	    ver = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveSlot'] = ver
	return ver
    
    def retrieveVersionTag(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveVersionTag: retrieving Version TAG for package ID "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveVersionTag',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	self.cursor.execute('SELECT "versiontag" FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	ver = ''
	for row in self.cursor:
	    ver = row[0]
	    break

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveVersionTag'] = ver
	return ver
    
    def retrieveMirrorInfo(self, mirrorname):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveMirrorInfo: retrieving Mirror info for mirror name "+str(mirrorname))

	self.cursor.execute('SELECT "mirrorlink" FROM mirrorlinks WHERE mirrorname = "'+str(mirrorname)+'"')
	mirrorlist = []
	for row in self.cursor:
	    mirrorlist.append(row[0])

	return mirrorlist

    def retrieveCategory(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveCategory: retrieving Category for package ID for "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveCategory',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

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

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveCategory'] = cat
	return cat

    def retrieveLicense(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveLicense: retrieving License for package ID for "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveLicense',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

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

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveLicense'] = licname
	return licname

    def retrieveCompileFlags(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveCompileFlags: retrieving CHOST,CFLAGS,CXXFLAGS for package ID for "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('retrieveCompileFlags',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

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

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['retrieveCompileFlags'] = flags
	return flags

    def retrieveDepends(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"retrieveDepends: called for idpackage "+str(idpackage))

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('searchDepends',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	# sanity check on the table
	sanity = self.isDependsTableSane() #FIXME: perhaps running this only on a client database?
	if (not sanity):
	    return -2 # table does not exist or is broken, please regenerate and re-run

	iddeps = []
	self.cursor.execute('SELECT iddependency FROM dependstable WHERE idpackage = "'+str(idpackage)+'"')
	for row in self.cursor:
	    iddeps.append(row[0])
	result = []
	for iddep in iddeps:
	    #print iddep
	    self.cursor.execute('SELECT idpackage FROM dependencies WHERE iddependency = "'+str(iddep)+'"')
	    for row in self.cursor:
	        result.append(row[0])

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['searchDepends'] = result

	return result

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

    def isProtectAvailable(self,protect):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isProtectAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idprotect FROM configprotectreference WHERE protect = "'+protect+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isProtectAvailable: "+protect+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isProtectAvailable: "+protect+" available.")
	return result

    def isSourceAvailable(self,source):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSourceAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idsource FROM sourcesreference WHERE source = "'+source+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isSourceAvailable: "+source+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSourceAvailable: "+source+" available.")
	return result

    def isDependencyAvailable(self,dependency):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isDependencyAvailable: called.")
	result = -1
	self.cursor.execute('SELECT iddependency FROM dependenciesreference WHERE dependency = "'+dependency+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isDependencyAvailable: "+dependency+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isDependencyAvailable: "+dependency+" available.")
	return result

    def isKeywordAvailable(self,keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isKeywordAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idkeyword FROM keywordsreference WHERE keywordname = "'+keyword+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isKeywordAvailable: "+keyword+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isKeywordAvailable: "+keyword+" available.")
	return result

    def isUseflagAvailable(self,useflag):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isUseflagAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idflag FROM useflagsreference WHERE flagname = "'+useflag+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isUseflagAvailable: "+useflag+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isUseflagAvailable: "+useflag+" available.")
	return result

    def isEclassAvailable(self,eclass):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isEclassAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idclass FROM eclassesreference WHERE classname = "'+eclass+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isEclassAvailable: "+eclass+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isEclassAvailable: "+eclass+" available.")
	return result

    def isNeededAvailable(self,needed):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isNeededAvailable: called.")
	result = -1
	self.cursor.execute('SELECT idneeded FROM neededreference WHERE library = "'+needed+'"')
	for row in self.cursor:
	    result = row[0]
	if result == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isNeededAvailable: "+needed+" not available.")
	    return result
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isNeededAvailable: "+needed+" available.")
	return result

    def isCounterAvailable(self,counter):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCounterAvailable: called.")
	result = False
	self.cursor.execute('SELECT counter FROM counters WHERE counter = "'+str(counter)+'"')
	for row in self.cursor:
	    result = True
	if (result):
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"isCounterAvailable: "+str(counter)+" not available.")
	else:
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isCounterAvailable: "+str(counter)+" available.")
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

    def isSystemPackage(self,idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSystemPackage: called.")

	''' caching '''
	if (self.xcache):
	    cached = dbCacheStore[etpCache['dbInfo']+self.dbname].get(int(idpackage), None)
	    if cached:
	        rslt = dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)].get('isSystemPackage',None)
	        if rslt:
		    return rslt
	    else:
	        dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)] = {}

	result = -1
	self.cursor.execute('SELECT idpackage FROM systempackages WHERE idpackage = "'+str(idpackage)+'"')
	for row in self.cursor:
	    result = row[0]
	    break
	rslt = False
	if result != -1:
	    dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSystemPackage: package is in system.")
	    rslt = True
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isSystemPackage: package is NOT in system.")

	''' caching '''
	if (self.xcache):
	    dbCacheStore[etpCache['dbInfo']+self.dbname][int(idpackage)]['isSystemPackage'] = rslt
	
	return rslt

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

    def searchBelongs(self, file, like = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchBelongs: called for "+file)
	result = []
	if (like):
	    self.cursor.execute('SELECT idpackage FROM content WHERE file LIKE "'+file+'"')
	else:
	    self.cursor.execute('SELECT idpackage FROM content WHERE file = "'+file+'"')
	for row in self.cursor:
	    result.append(row[0])
	return result

    ''' search packages that need the specified library (in neededreference table) specified by keyword '''
    def searchNeeded(self, keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchNeeded: called for "+keyword)
	idpackages = set()
	self.cursor.execute('SELECT needed.idpackage FROM needed,neededreference WHERE library = "'+keyword+'" and needed.idneeded = neededreference.idneeded')
	for row in self.cursor:
	    idpackages.add(row[0])
	return idpackages

    ''' same as above but with branch support '''
    def searchNeededInBranch(self, keyword, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchNeeded: called for "+keyword+" and branch: "+branch)
	idpackages = set()
	self.cursor.execute('SELECT needed.idpackage FROM needed,neededreference,baseinfo WHERE library = "'+keyword+'" and needed.idneeded = neededreference.idneeded and baseinfo.branch = "'+branch+'"')
	for row in self.cursor:
	    idpackages.add(row[0])
	return idpackages


    ''' search dependency string inside dependenciesreference table and retrieve iddependency '''
    def searchDependency(self, dep):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchDependency: called for "+dep)
	iddep = -1
	self.cursor.execute('SELECT iddependency FROM dependenciesreference WHERE dependency = "'+dep+'"')
	for row in self.cursor:
	    iddep = row[0]
	return iddep

    ''' search iddependency inside dependencies table and retrieve idpackages '''
    def searchIdpackageFromIddependency(self, iddep):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchIdpackageFromIddependency: called for "+str(iddep))
	result = set()
	self.cursor.execute('SELECT idpackage FROM dependencies WHERE iddependency = "'+str(iddep)+'"')
	for row in self.cursor:
	    result.add(row[0])
	return result

    def searchPackages(self, keyword, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackages: called for "+keyword)
	result = []
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo WHERE atom LIKE "%'+keyword+'%"')
	else:
	    self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo WHERE LOWER(atom) LIKE "%'+string.lower(keyword)+'%"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchProvide(self, keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchProvide: called for "+keyword)

	idpackage = []
	self.cursor.execute('SELECT idpackage FROM provide WHERE atom = "'+keyword+'"')
	for row in self.cursor:
	    idpackage = row[0]
	    break
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	result = []
	for row in self.cursor:
	    result = row
	    break

	return result

    def searchProvideInBranch(self, keyword, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchProvideInBranch: called for "+keyword+" and branch: "+branch)
	idpackages = []
	self.cursor.execute('SELECT idpackage FROM provide WHERE atom = "'+keyword+'"')
	for row in self.cursor:
	    idpackages.append(row[0])
	results = []
	for idpackage in idpackages:
	    self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo WHERE idpackage = "'+str(idpackage)+'"')
	    for row in self.cursor:
	        data = row
		atom = data[0]
	        idpackage = data[1]
	        pkgbranch = data[2]
	        if (branch == pkgbranch):
		    results.append((atom,idpackage))
	return results

    def searchPackagesInBranch(self, keyword, branch, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesInBranch: called.")
	result = []
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE atom LIKE "%'+keyword+'%" AND branch = "'+branch+'"')
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(atom) LIKE "%'+string.lower(keyword)+'%" AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesByDescription(self, keyword):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesByDescription: called for "+keyword)
	idpkgs = []
	self.cursor.execute('SELECT idpackage FROM extrainfo WHERE LOWER(description) LIKE "%'+string.lower(keyword)+'%"')
	for row in self.cursor:
	    idpkgs.append(row[0])
	result = []
	for idpk in idpkgs:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE idpackage = "'+str(idpk)+'"')
	    for row in self.cursor:
	        result.append(row)
	return result

    def searchPackagesByName(self, keyword, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesByName: called for "+keyword)
	result = []
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+keyword+'"')
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+string.lower(keyword)+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesByNameAndCategory(self, name, category, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesByNameAndCategory: called for name: "+name+" and category: "+category)
	result = []
	# get category id
	idcat = -1
	self.cursor.execute('SELECT idcategory FROM categories WHERE category = "'+category+'"')
	for row in self.cursor:
	    idcat = row[0]
	    break
	if idcat == -1:
	    dbLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"searchPackagesByNameAndCategory: Category "+category+" not available.")
	    return result
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+name+'" AND idcategory ='+str(idcat))
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+string.lower(name)+'" AND idcategory ='+str(idcat))
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesInBranchByName(self, keyword, branch, sensitive = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"searchPackagesInBranchByName: called for "+keyword)
	result = []
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+keyword+'" AND branch = "'+branch+'"')
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+string.lower(keyword)+'" AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesInBranchByNameAndCategory(self, name, category, branch, sensitive = False):
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
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+name+'" AND idcategory = '+str(idcat)+' AND branch = "'+branch+'"')
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+string.lower(name)+'" AND idcategory = '+str(idcat)+' AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def searchPackagesInBranchByNameAndVersionAndCategory(self, name, version, category, branch, sensitive = False):
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
	if (sensitive):
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE name = "'+name+'" AND version = "'+version+'" AND idcategory = '+str(idcat)+' AND branch = "'+branch+'"')
	else:
	    self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE LOWER(name) = "'+string.lower(name)+'" AND version = "'+version+'" AND idcategory = '+str(idcat)+' AND branch = "'+branch+'"')
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
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE idcategory = "'+str(idcategory)+'" AND LOWER(name) = "'+string.lower(name)+'" AND branch = "'+branch+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def listAllPackages(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllPackages: called.")
	self.cursor.execute('SELECT atom,idpackage,branch FROM baseinfo')
	result = []
	for row in self.cursor:
	    result.append(row)
	return result

    def listAllCounters(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllCounters: called.")
	self.cursor.execute('SELECT counter,idpackage FROM counters')
	result = []
	for row in self.cursor:
	    result.append(row)
	return result

    def listAllIdpackages(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllIdpackages: called.")
	self.cursor.execute('SELECT idpackage FROM baseinfo')
	result = []
	for row in self.cursor:
	    result.append(row[0])
	return result

    def listAllDependencies(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllDependencies: called.")
	self.cursor.execute('SELECT * FROM dependenciesreference')
	result = []
	for row in self.cursor:
	    result.append(row)
	return result

    def listIdpackageDependencies(self, idpackage):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listIdpackageDependencies: called.")
	self.cursor.execute('SELECT iddependency FROM dependencies where idpackage = "'+str(idpackage)+'"')
	iddeps = []
	for row in self.cursor:
	    iddeps.append(row[0])
	result = []
	for iddep in iddeps:
	    self.cursor.execute('SELECT iddependency,dependency FROM dependenciesreference where iddependency = "'+str(iddep)+'"')
	    for row in self.cursor:
	        result.append(row)
	return result

    #FIXME: DEPRECATED
    def listAllPackagesTbz2(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllPackagesTbz2: called.")
        result = []
        pkglist = self.listAllPackages()
        for pkg in pkglist:
	    idpackage = pkg[1]
	    url = self.retrieveDownloadURL(idpackage)
	    if url:
		result.append(url)
        # filter dups?
	if (result):
            result = list(set(result))
	    result.sort()
	return result

    def listBranchPackagesTbz2(self, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listBranchPackagesTbz2: called with "+str(branch))
        result = []
        pkglist = self.listBranchPackages(branch)
        for pkg in pkglist:
	    idpackage = pkg[1]
	    url = self.retrieveDownloadURL(idpackage)
	    if url:
		result.append(os.path.basename(url))
        # filter dups?
	if (result):
            result = list(set(result))
	    result.sort()
	return result

    def listBranchPackages(self, branch):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listBranchPackages: called with "+str(branch))
	result = []
	self.cursor.execute('SELECT atom,idpackage FROM baseinfo WHERE branch = "'+str(branch)+'"')
	for row in self.cursor:
	    result.append(row)
	return result

    def listAllFiles(self, clean = False):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listAllFiles: called.")
	if clean:
	    result = set()
	else:
	    result = []
	self.cursor.execute('SELECT file FROM content')
	for row in self.cursor:
	    if clean:
	        result.add(row[0])
		continue
	    result.append(row[0])
	return result

    def listConfigProtectDirectories(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listConfigProtectDirectories: called.")
	dirs = set()
	idprotects = set()
	try:
	    self.cursor.execute('SELECT idprotect FROM configprotect')
	except:
	    self.createProtectTable()
	    self.cursor.execute('SELECT idprotect FROM configprotect')
	for row in self.cursor:
	    idprotects.add(row[0])
	for idprotect in idprotects:
	    self.cursor.execute('SELECT protect FROM configprotectreference WHERE idprotect = "'+str(idprotect)+'"')
	    for row in self.cursor:
	        var = row[0]
	        for x in var.split():
		    dirs.add(x)
	dirs = list(dirs)
	dirs.sort()
	return dirs

    def listConfigProtectMaskDirectories(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"listConfigProtectMaskDirectories: called.")
	dirs = set()
	idprotects = set()
	try:
	    self.cursor.execute('SELECT idprotect FROM configprotectmask')
	except:
	    self.createProtectTable()
	    self.cursor.execute('SELECT idprotect FROM configprotect')
	for row in self.cursor:
	    idprotects.add(row[0])
	for idprotect in idprotects:
	    self.cursor.execute('SELECT protect FROM configprotectreference WHERE idprotect = "'+str(idprotect)+'"')
	    for row in self.cursor:
	        var = row[0]
	        for x in var.split():
		    dirs.add(x)
	dirs = list(dirs)
	dirs.sort()
	return dirs
    
    # FIXME: get it working with the new branch layout
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
	    for row in self.cursor:
	        result = row[0]
	        break
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

    #
    # FIXME: remove these when 1.0 will be out
    #
    
    def createSizesTable(self):
	dbLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createSizesTable: called.")
	self.cursor.execute('DROP TABLE IF EXISTS sizes;')
	self.cursor.execute('CREATE TABLE sizes ( idpackage INTEGER, size INTEGER );')
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
    def atomMatch(self, atom, caseSensitive = True, matchSlot = None, multiMatch = False, matchBranches = []):
        if (self.xcache):
            cached = dbCacheStore[etpCache['dbMatch']+self.dbname].get(atom)
            if cached:
		# check if matchSlot and multiMatch were the same
		if (matchSlot == cached['matchSlot']) \
			and (multiMatch == cached['multiMatch']) \
			and (caseSensitive == cached['caseSensitive']) \
			and (matchBranches == cached['matchBranches']):
	            return cached['result']
	
	# check if slot is provided -> app-foo/foo-1.2.3:SLOT
	atomSlot = entropyTools.dep_getslot(atom)
	# then remove
	atom = entropyTools.remove_slot(atom)
	if (matchSlot == None) and (atomSlot != None): # new slotdeps support
	    matchSlot = atomSlot
	
        # check for direction
        strippedAtom = entropyTools.dep_getcpv(atom)
        if atom.endswith("*"):
	    strippedAtom += "*"
        direction = atom[0:len(atom)-len(strippedAtom)]
        #print direction
	
        #print strippedAtom
        #print entropyTools.isspecific(strippedAtom)
        #print direction
	
        justname = entropyTools.isjustname(strippedAtom)
        #print justname
        pkgversion = ''
        if (not justname):
	    # strip tag
            if strippedAtom.split("-")[-1].startswith("t"):
                strippedAtom = string.join(strippedAtom.split("-t")[:len(strippedAtom.split("-t"))-1],"-t")
	    # get version
	    data = entropyTools.catpkgsplit(strippedAtom)
	    if data == None:
	        return -1,3 # atom is badly formatted
	    pkgversion = data[2]+"-"+data[3]
	    pkgtag = ''
	    if atom.split("-")[len(atom.split("-"))-1].startswith("t"):
	        pkgtag = atom.split("-")[len(atom.split("-"))-1]
	        #print "TAG: "+pkgtag
	    #print data
	    #print pkgversion
	    #print pkgtag
	
        pkgkey = entropyTools.dep_getkey(strippedAtom)
        if len(pkgkey.split("/")) == 2:
            pkgname = pkgkey.split("/")[1]
            pkgcat = pkgkey.split("/")[0]
        else:
            pkgname = pkgkey.split("/")[0]
	    pkgcat = "null"

        #print dep_getkey(strippedAtom)
	if (matchBranches):
	    myBranchIndex = matchBranches
	else:
	    myBranchIndex = [etpConst['branch']]
    
        # IDs found in the database that match our search
        foundIDs = []
	
        for idx in myBranchIndex: # myBranchIndex is ordered by importance
	    #print "Searching into -> "+etpConst['branches'][idx]
	    # search into the less stable, if found, break, otherwise continue
	    results = self.searchPackagesInBranchByName(pkgname, idx, caseSensitive)
	    
	    mypkgcat = pkgcat
	    mypkgname = pkgname
	    
	    # if it's a PROVIDE, search with searchProvide
	    if mypkgcat == "virtual":
	        virtuals = self.searchProvideInBranch(pkgkey,idx)
		if (virtuals):
		    for virtual in virtuals:
			mypkgname = self.retrieveName(virtual[1])
			mypkgcat = self.retrieveCategory(virtual[1])
			break
		    results = virtuals
			
	    # now validate
	    if (not results):
	        #print "results is empty"
	        continue # search into a stabler branch
	
	    elif (len(results) > 1):
	
	        #print "results > 1"
	        # if it's because category differs, it's a problem
	        foundCat = ""
	        cats = []
	        for result in results:
		    idpackage = result[1]
		    cat = self.retrieveCategory(idpackage)
		    cats.append(cat)
		    if (cat == mypkgcat):
		        foundCat = cat
		        break
	        # if categories are the same...
	        if (not foundCat) and (len(cats) > 0):
		    cats = entropyTools.filterDuplicatedEntries(cats)
		    if len(cats) == 1:
		        foundCat = cats[0]
	        if (not foundCat) and (mypkgcat == "null"):
		    # got the issue
		    # gosh, return and complain
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,2
		    return -1,2
	
	        # I can use foundCat
	        mypkgcat = foundCat

	        # we need to search using the category
		if (not multiMatch):
	            results = self.searchPackagesInBranchByNameAndCategory(mypkgname, mypkgcat, idx, caseSensitive)
	        # validate again
	        if (not results):
		    continue  # search into a stabler branch
	
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
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,3
		    return -1,3 # error, cannot use directions when not specifying version
	    
	        if (direction == "~") or (direction == "=") or (direction == '' and not justname) or (direction == '' and not justname and strippedAtom.endswith("*")): # any revision within the version specified OR the specified version
		# FIXME: add slot scopes
		
		    if (direction == '' and not justname):
		        direction = "="
		
		    #print direction+" direction"
		    # remove revision (-r0 if none)
		    if (direction == "="):
		        if (pkgversion.split("-")[len(pkgversion.split("-"))-1] == "r0"):
		            pkgversion = string.join(pkgversion.split("-")[:len(pkgversion.split("-"))-1],"-")
		    if (direction == "~"):
		        pkgversion = string.join(pkgversion.split("-")[:len(pkgversion.split("-"))-1],"-")
		
		    #print pkgversion
		    dbpkginfo = []
		    for list in foundIDs:
		        idpackage = list[1]
		        dbver = self.retrieveVersion(idpackage)
		        if (direction == "~"):
		            if dbver.startswith(pkgversion):
			        # found
			        dbpkginfo.append([idpackage,dbver])
		        else:
			    dbtag = self.retrieveVersionTag(idpackage)
			    #print pkgversion
			    # media-libs/test-1.2* support
			    if pkgversion.endswith("*"):
			        testpkgver = pkgversion[:len(pkgversion)-1]
			        #print testpkgver
			        combodb = dbver+dbtag
			        combopkg = testpkgver+pkgtag
			        #print combodb
			        #print combopkg
			        if combodb.startswith(combopkg):
				    dbpkginfo.append([idpackage,dbver])
			    else:
		                if (dbver+dbtag == pkgversion+pkgtag):
			            # found
			            dbpkginfo.append([idpackage,dbver])
		
		    if (not dbpkginfo):
		        # no version available
		        if (direction == "~"): # if the atom with the same version (any rev) is not found, fallback to the first available
			    for list in foundIDs:
			        idpackage = list[1]
			        dbver = self.retrieveVersion(idpackage)
			        dbpkginfo.append([idpackage,dbver])
		
		    if (not dbpkginfo):
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
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
		        versions.append(x[1])
		
		    if (not versions):
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
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
	            similarPackages = self.searchPackagesInBranchByNameAndVersionAndCategory(newerPkgName, newerPkgVersion, newerPkgCategory, newerPkgBranch, caseSensitive)
		    
		    if (multiMatch):
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
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
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = newerPackage[0],0
		    return newerPackage[0],0
	
	        elif (direction.find(">") != -1) or (direction.find("<") != -1): # FIXME: add slot scopes
		
		    #print direction+" direction"
		    # remove revision (-r0 if none)
		    if pkgversion.split("-")[len(pkgversion.split("-"))-1] == "r0":
		        # remove
		        pkgversion = string.join(pkgversion.split("-")[:len(pkgversion.split("-"))-1],"-")

		    dbpkginfo = []
		    for list in foundIDs:
		        idpackage = list[1]
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
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,1
		        return -1,1
		
		    versions = []
		    multiMatchList = []
		    _dbpkginfo = []
		    for x in dbpkginfo:
			if (matchSlot != None):
			    mslot = self.retrieveSlot(x[0])
			    if (str(matchSlot) != str(mslot)):
				continue
			if (multiMatch):
			    multiMatchList.append(x[0])
		        versions.append(x[1])
			_dbpkginfo.append(x)
		    dbpkginfo = _dbpkginfo
		    
		    if (multiMatch):
			return multiMatchList,0

		    if (not versions):
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
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
	            similarPackages = self.searchPackagesInBranchByNameAndVersionAndCategory(newerPkgName, newerPkgVersion, newerPkgCategory, newerPkgBranch)

		    if (multiMatch):
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		        dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
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
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = newerPackage[0],0
		    return newerPackage[0],0

	        else:
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
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
		multiMatchList = []
		_foundIDs = []
	        for list in foundIDs:
		    if (matchSlot == None):
		        versionIDs.append(self.retrieveVersion(list[1]))
			if (multiMatch):
			    multiMatchList.append(list[1])
		    else:
			foundslot = self.retrieveSlot(list[1])
			if (str(foundslot) != str(matchSlot)):
			    continue
			versionIDs.append(self.retrieveVersion(list[1]))
			if (multiMatch):
			    multiMatchList.append(list[1])
		    _foundIDs.append(list)
		foundIDs = _foundIDs
	    
		if (multiMatch):
		    return multiMatchList,0
		
		if (not versionIDs):
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
		    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
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
	        similarPackages = self.searchPackagesInBranchByNameAndVersionAndCategory(newerPkgName, newerPkgVersion, newerPkgCategory, newerPkgBranch)

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
		dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
		dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
		dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
		dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = newerPackage[1],0
	        return newerPackage[1],0

        else:
	    # package not found in any branch
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom] = {}
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchSlot'] = matchSlot
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['multiMatch'] = multiMatch
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['caseSensitive'] = caseSensitive
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['matchBranches'] = matchBranches
	    dbCacheStore[etpCache['dbMatch']+self.dbname][atom]['result'] = -1,1
	    return -1,1
	