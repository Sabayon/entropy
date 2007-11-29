#!/usr/bin/python
'''
    # DESCRIPTION:
    # generic tools for reagent application

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

# EXIT STATUSES: 500-599

from entropyConstants import *
from serverConstants import *
from entropyTools import *
import os
import shutil
import databaseTools

# Logging initialization
import logTools
reagentLog = logTools.LogFile(level=etpConst['reagentloglevel'],filename = etpConst['reagentlogfile'], header = "[Reagent]")

# reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"testFunction: example. ")

def generator(package, dbconnection = None, enzymeRequestBranch = etpConst['branch']):

    reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"generator: called -> Package: "+str(package)+" | dbconnection: "+str(dbconnection))

    # check if the package provided is valid
    validFile = False
    if os.path.isfile(package) and package.endswith(".tbz2"):
	validFile = True
    if (not validFile):
	print_warning(package+" does not exist !")

    packagename = os.path.basename(package)
    print_info(yellow(" * ")+red("Processing: ")+bold(packagename)+red(", please wait..."))
    mydata = extractPkgData(package, enzymeRequestBranch)
    
    if dbconnection is None:
	dbconn = databaseTools.openServerDatabase(readOnly = False, noUpload = True)
    else:
	dbconn = dbconnection
    
    idpk, revision, etpDataUpdated, accepted = dbconn.handlePackage(mydata)
    
    # add package info to our official repository etpConst['officialrepositoryname']
    if (accepted):
        dbconn.removePackageFromInstalledTable(idpk)
	dbconn.addPackageToInstalledTable(idpk,etpConst['officialrepositoryname'])
    
    if dbconnection is None:
	dbconn.commitChanges()
	dbconn.closeDB()

    packagename = packagename[:-5]+"~"+str(revision)+".tbz2"

    if (accepted) and (revision != 0):
	reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"generator: entry for "+str(packagename)+" has been updated to revision: "+str(revision))
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" entry has been updated. Revision: ")+bold(str(revision)))
	return True, idpk
    elif (accepted) and (revision == 0):
	reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"generator: entry for "+str(packagename)+" newly created or version bumped.")
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" entry newly created."))
	return True, idpk
    else:
	reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"generator: entry for "+str(packagename)+" kept intact, no updates needed.")
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" does not need to be updated. Current revision: ")+bold(str(revision)))
	return False, idpk


# This tool is used by Entropy after enzyme, it simply parses the content of etpConst['packagesstoredir']
def update(options):

    reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"update: called -> options: "+str(options))

    # differential checking
    # collect differences between the packages in the database and the ones on the system
    
    reagentRequestSeekStore = False
    reagentRequestRepackage = False
    reagentRequestAsk = True
    repackageItems = []
    _options = []
    for opt in options:
	if opt.startswith("--seekstore"):
	    reagentRequestSeekStore = True
	elif opt.startswith("--repackage"):
	    reagentRequestRepackage = True
	elif opt.startswith("--noask"):
	    reagentRequestAsk = False
	else:
	    if (reagentRequestRepackage) and (not opt.startswith("--")):
		if not opt in repackageItems:
		    repackageItems.append(opt)
		continue
	    _options.append(opt)
    options = _options

    if (not reagentRequestSeekStore):

        dbconn = databaseTools.openServerDatabase(readOnly = True, noUpload = True)
	
	if (not reagentRequestRepackage):
            print_info(yellow(" * ")+red("Scanning database for differences..."))
            from portageTools import getInstalledPackagesCounters, quickpkg, getPackageSlot
            installedPackages = getInstalledPackagesCounters()
            installedCounters = set()
            databasePackages = dbconn.listAllPackages()
            toBeAdded = set()
            toBeRemoved = set()
	    
            # packages to be added
            for x in installedPackages[0]:
	        installedCounters.add(x[1])
	        counter = dbconn.isCounterAvailable(x[1])
	        if (not counter):
	            toBeAdded.add(tuple(x))

            # packages to be removed from the database
            databaseCounters = dbconn.listAllCounters()
            for x in databaseCounters:
                if x[0] not in installedCounters:
	            # check if the package is in toBeAdded
	            if (toBeAdded):
			#print x
                        atom = dbconn.retrieveAtom(x[1])
	                atomkey = dep_getkey(atom)
                        atomtag = dep_gettag(atom)
		        atomslot = dbconn.retrieveSlot(x[1])
 
		        add = True
		        for pkgdata in toBeAdded:
		            addslot = getPackageSlot(pkgdata[0])
		            addkey = dep_getkey(pkgdata[0])
		            # workaround for ebuilds not having slot
		            if addslot == None:
			        addslot = '0'                                              # handle tagged packages correctly
		            if (atomkey == addkey) and ((str(atomslot) == str(addslot)) or (atomtag != None)):
			        # do not add to toBeRemoved
			        add = False
			        break
		        if add:
		            toBeRemoved.add(x[1])
	            else:
	                toBeRemoved.add(x[1])

            if (not toBeRemoved) and (not toBeAdded):
	        print_info(yellow(" * ")+red("Nothing to do, check later."))
	        # then exit gracefully
	        return 0

            if (toBeRemoved):
	        print_info(yellow(" @@ ")+blue("These are the packages that would be removed from the database:"))
	        for x in toBeRemoved:
	            atom = dbconn.retrieveAtom(x)
	            print_info(yellow("    # ")+red(atom))
                if reagentRequestAsk:
                    rc = askquestion(">>   Would you like to remove them now ?")
                else:
                    rc = "Yes"
	        if rc == "Yes":
	            rwdbconn = databaseTools.openServerDatabase(readOnly = False, noUpload = True)
	            for x in toBeRemoved:
		        atom = rwdbconn.retrieveAtom(x)
		        print_info(yellow(" @@ ")+blue("Removing from database: ")+red(atom), back = True)
		        rwdbconn.removePackage(x)
	            rwdbconn.closeDB()
	            print_info(yellow(" @@ ")+blue("Database removal complete."))

            if (toBeAdded):
	        print_info(yellow(" @@ ")+blue("These are the packages that would be added/updated to the add list:"))
	        for x in toBeAdded:
	            print_info(yellow("    # ")+red(x[0]))
                if reagentRequestAsk:
	            rc = askquestion(">>   Would you like to package them now ?")
                    if rc == "No":
                        return 0

	else:
	    if not repackageItems:
	        print_info(yellow(" * ")+red("Nothing to do, check later."))
	        # then exit gracefully
	        return 0
	    
	    from portageTools import getPortageAppDbPath,quickpkg
	    appdb = getPortageAppDbPath()
	    
	    packages = []
	    for item in repackageItems:
		match = dbconn.atomMatch(item)
		if match[0] == -1:
		    print_warning(darkred("  !!! ")+red("Cannot match ")+bold(item))
		else:
		    cat = dbconn.retrieveCategory(match[0])
		    name = dbconn.retrieveName(match[0])
		    version = dbconn.retrieveVersion(match[0])
		    slot = dbconn.retrieveSlot(match[0])
		    if os.path.isdir(appdb+"/"+cat+"/"+name+"-"+version):
		        packages.append([cat+"/"+name+"-"+version,0])
	    
	    if not packages:
	        print_info(yellow(" * ")+red("Nothing to do, check later."))
	        # then exit gracefully
	        return 0
	    
	    toBeAdded = packages

        # package them
        print_info(yellow(" @@ ")+blue("Compressing packages..."))
        for x in toBeAdded:
	    print_info(yellow("    # ")+red(x[0]+"..."))
	    rc = quickpkg(x[0],etpConst['packagesstoredir'])
	    if (rc is None):
	        reagentLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"update: "+str(dep)+" -> quickpkg error. Cannot continue.")
	        print_error(red("      *")+" quickpkg error for "+red(dep))
	        print_error(red("  ***")+" Fatal error, cannot continue")
	        return 251

        dbconn.closeDB()

    enzymeRequestBranch = etpConst['branch']
    #_atoms = []
    for i in options:
        if ( i == "--branch=" and len(i.split("=")) == 2 ):
	    mybranch = i.split("=")[1]
	    if (mybranch):
	        enzymeRequestBranch = mybranch

    tbz2files = os.listdir(etpConst['packagesstoredir'])
    totalCounter = 0
    # counting the number of files
    for i in tbz2files:
	totalCounter += 1

    if (totalCounter == 0):
	print_info(yellow(" * ")+red("Nothing to do, check later."))
	# then exit gracefully
	return 0

    # open db connection
    dbconn = databaseTools.openServerDatabase(readOnly = False, noUpload = True)

    counter = 0
    etpCreated = 0
    etpNotCreated = 0
    for tbz2 in tbz2files:
	counter += 1
	tbz2name = tbz2.split("/")[-1]
	print_info(" ("+str(counter)+"/"+str(totalCounter)+") Processing "+tbz2name)
	tbz2path = etpConst['packagesstoredir']+"/"+tbz2
	rc, idpk = generator(tbz2path, dbconn, enzymeRequestBranch)
	if (rc):
	    etpCreated += 1
            
            # add revision to package file
            downloadurl = dbconn.retrieveDownloadURL(idpk)
            packagerev = dbconn.retrieveRevision(idpk)
            downloaddir = os.path.dirname(downloadurl)
            downloadfile = os.path.basename(downloadurl)
            # remove tbz2 and add revision
            downloadfile = downloadfile[:-5]+"~"+str(packagerev)+".tbz2"
            downloadurl = downloaddir+"/"+downloadfile
            # update url
            dbconn.setDownloadURL(idpk,downloadurl)
            
            shutil.move(tbz2path,etpConst['packagessuploaddir']+"/"+enzymeRequestBranch+"/"+downloadfile)
	    print_info(yellow(" * ")+red("Injecting database information into ")+bold(downloadfile)+red(", please wait..."), back = True)
            
            dbpath = etpConst['packagestmpdir']+"/"+str(getRandomNumber())
            while os.path.isfile(dbpath):
                dbpath = etpConst['packagestmpdir']+"/"+str(getRandomNumber())
	    # create db
            pkgDbconn = databaseTools.openGenericDatabase(dbpath)
	    pkgDbconn.initializeDatabase()
	    data = dbconn.getPackageData(idpk)
	    rev = dbconn.retrieveRevision(idpk)
	    # inject
	    pkgDbconn.addPackage(data, revision = rev)
	    pkgDbconn.closeDB()
	    # append the database to the new file
	    aggregateEdb(tbz2file = etpConst['packagessuploaddir']+"/"+enzymeRequestBranch+"/"+downloadfile, dbfile = dbpath)
	    
	    digest = md5sum(etpConst['packagessuploaddir']+"/"+enzymeRequestBranch+"/"+downloadfile)
	    dbconn.setDigest(idpk,digest)
	    hashFilePath = createHashFile(etpConst['packagessuploaddir']+"/"+enzymeRequestBranch+"/"+downloadfile)
	    # remove garbage
	    os.remove(dbpath)
	    print_info(yellow(" * ")+red("Database injection complete for ")+downloadfile)
	    
	else:
	    etpNotCreated += 1
	    spawnCommand("rm -rf "+tbz2path)
	dbconn.commitChanges()

    dbconn.commitChanges()
    
    # regen dependstable
    dependsTableInitialize(dbconn, False)
    
    dbconn.closeDB()

    print_info(green(" * ")+red("Statistics: ")+blue("Entries created/updated: ")+bold(str(etpCreated))+yellow(" - ")+darkblue("Entries discarded: ")+bold(str(etpNotCreated)))
    return 0


def dependsTableInitialize(dbconn = None, runActivator = True):
    closedb = False
    if dbconn == None:
	dbconn = databaseTools.openServerDatabase(readOnly = False, noUpload = True)
	closedb = True
    dbconn.regenerateDependsTable()
    # now taint
    dbconn.taintDatabase()
    if (closedb):
        dbconn.closeDB()
    # running activator
    if (runActivator):
	import activatorTools
	activatorTools.database(['sync'])
    return 0

def dependenciesTest(options):

    reagentRequestQuiet = False
    for opt in options:
	if opt.startswith("--quiet"):
	    reagentRequestQuiet = True

    import uiTools
    
    dbconn = databaseTools.openServerDatabase(readOnly = True, noUpload = True)
    rc = uiTools.dependenciesTest(quiet = reagentRequestQuiet, clientDbconn = dbconn, reagent = True)

    return rc

def database(options):

    import activatorTools
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
	return 1

    if (options[0] == "--initialize"):
	
	# do some check, print some warnings
	print_info(green(" * ")+red("Initializing Entropy database..."), back = True)
        # database file: etpConst['etpdatabasefilepath']
	revisionsMatch = {}
        if os.path.isfile(etpConst['etpdatabasefilepath']):
	    dbconn = databaseTools.openServerDatabase(readOnly = True, noUpload = True)
            idpackages = []
            try:
                idpackages = dbconn.listAllIdpackages()
            except:
                pass
	    for idpackage in idpackages:
		try:
		    package = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
		    branch = dbconn.retrieveBranch(idpackage)
		    revision = dbconn.retrieveRevision(idpackage)
		    if revision < 0: # just to be sure
			revision = 0
		    revisionsMatch[package] = [branch,revision]
		except:
		    pass
	    dbconn.closeDB()
	    print_info(red(" * ")+bold("WARNING")+red(": database file already exists. Overwriting."))
	    rc = askquestion("\n     Do you want to continue ?")
	    if rc == "No":
	        return 0
	    os.remove(etpConst['etpdatabasefilepath'])

	# initialize the database
        dbconn = databaseTools.openServerDatabase(readOnly = False, noUpload = True)
	dbconn.initializeDatabase()

	# sync packages directory
        if revisionsMatch:
            print_info(green(" * ")+red("Dumping current revisions to file ")+"/entropy-revisions-dump.txt")
            f = open("/entropy-revisions-dump.txt","w")
            f.write(str(revisionsMatch)+"\n")
            f.flush()
            f.close()

	rc = askquestion("     Would you like to sync packages first (important if you don't have them synced) ?")
        if rc == "Yes":
            activatorTools.packages(["sync","--ask"])
	
	# now fill the database
	pkgbranches = os.listdir(etpConst['packagesbindir'])
	pkgbranches = [x for x in pkgbranches if os.path.isdir(etpConst['packagesbindir']+"/"+x)]
	#print revisionsMatch
	for mybranch in pkgbranches:
	
	    pkglist = os.listdir(etpConst['packagesbindir']+"/"+mybranch)
	    pkglist = [x for x in pkglist if x[-5:] == ".tbz2"]
	
	    if (not pkglist):
		continue

	    print_info(green(" * ")+red("Reinitializing Entropy database for branch ")+bold(mybranch)+red(" using Packages in the repository ..."))
	    currCounter = 0
	    atomsnumber = len(pkglist)
	    
	    for pkg in pkglist:
		
	        print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+red("Analyzing: ")+bold(pkg), back = True)
	        currCounter += 1
	        print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+green("(")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(pkg)+red(" ..."), back = True)
		
	        mydata = extractPkgData(etpConst['packagesbindir']+"/"+mybranch+"/"+pkg, mybranch)
	        # get previous revision
		revisionAvail = revisionsMatch.get(os.path.basename(mydata['download']))
		addRevision = 0
		if (revisionAvail != None):
		    if mybranch == revisionAvail[0]:
			addRevision = revisionAvail[1]
	        # fill the db entry
	        idpk, revision, etpDataUpdated, accepted = dbconn.addPackage(mydata, revision = addRevision)
		
		print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+green("(")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(pkg)+red(". Revision: ")+blue(str(addRevision)))
	    
	    dbconn.commitChanges()
	
	# regen dependstable
        dependsTableInitialize(dbconn, False)
	
	dbconn.closeDB()
	print_info(green(" * ")+red("Entropy database has been reinitialized using binary packages available"))
        return 0

    # used by reagent
    elif (options[0] == "search"):
	mykeywords = options[1:]
	if (len(mykeywords) == 0):
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    return 2
	if (not os.path.isfile(etpConst['etpdatabasefilepath'])):
	    print_error(yellow(" * ")+red("Entropy Datbase does not exist"))
	    return 3
	
	# search tool
	print_info(green(" * ")+red("Searching ..."))
	# open read only
	dbconn = databaseTools.openServerDatabase(readOnly = True, noUpload = True)
	from queryTools import printPackageInfo
	foundCounter = 0
	for mykeyword in mykeywords:
	    results = dbconn.searchPackages(mykeyword)
	    
	    for result in results:
		foundCounter += 1
		print
		printPackageInfo(result[1],dbconn, clientSearch = True, extended = True)
		
	dbconn.closeDB()
	if (foundCounter == 0):
	    print_warning(red(" * ")+red("Nothing found."))
	else:
	    print
        return 0

    elif (options[0] == "create-empty-database"):
	
        mypath = options[1:]
	if len(mypath) == 0:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    return 4
	if (os.path.dirname(mypath[0]) != '') and (not os.path.isdir(os.path.dirname(mypath[0]))):
	    print_error(green(" * ")+red("Supplied directory does not exist."))
	    return 5
	print_info(green(" * ")+red("Initializing an empty database file with Entropy structure ..."),back = True)
	connection = databaseTools.sqlite.connect(mypath[0])
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
        return 0

    elif (options[0] == "switchbranch"):
	
	if (len(options) < 2):
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    return 6

	switchbranch = options[1]
	print_info(green(" * ")+red("Collecting packages that would be marked '"+switchbranch+"' ..."), back = True)

	myatoms = options[2:]
	if not myatoms:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    return 7
	
	dbconn = databaseTools.openServerDatabase(readOnly = False, noUpload = True)
	# is world?
	if myatoms[0] == "world":
	    pkglist = dbconn.listAllIdpackages()
	else:
	    pkglist = set()
	    for atom in myatoms:
		# validate atom
		match = dbconn.atomMatch(atom)
		if match == -1:
		    print_warning(yellow(" * ")+red("Cannot match: ")+bold(atom))
		else:
		    pkglist.add(match[0])
	
	# check if atoms were found
	if not pkglist:
	    print
	    print_error(yellow(" * ")+red("No packages found."))
	    return 8
	
	# show what would be done
	print_info(green(" * ")+red("These are the packages that would be marked '"+switchbranch+"':"))

	for pkg in pkglist:
	    atom = dbconn.retrieveAtom(pkg)
	    print_info(red("  (*) ")+bold(atom))

	rc = askquestion("     Would you like to continue ?")
	if rc == "No":
	    return 9
	
	# sync packages
	import activatorTools
	activatorTools.packages(["sync","--ask"])
	
	print_info(green(" * ")+red("Switching selected packages ..."))
	import re
	
	for pkg in pkglist:
	    atom = dbconn.retrieveAtom(pkg)
	    currentbranch = dbconn.retrieveBranch(pkg)
	    currentdownload = dbconn.retrieveDownloadURL(pkg)
	    
	    if currentbranch == switchbranch:
		print_warning(green(" * ")+red("Ignoring ")+bold(atom)+red(" since it is already in the chosen branch"))
		continue
	    
	    print_info(green(" * ")+darkred(atom+": ")+red("Configuring package information..."), back = True)
	    # change branch and download URL
	    dbconn.switchBranch(pkg,switchbranch)
	    
	    # rename locally
	    filename = os.path.basename(dbconn.retrieveDownloadURL(pkg))
	    topath = etpConst['packagesbindir']+"/"+switchbranch
	    if not os.path.isdir(topath):
		os.makedirs(topath)
	    print_info(green(" * ")+darkred(atom+": ")+red("Moving file locally..."), back = True)
	    #print etpConst['entropyworkdir']+"/"+currentdownload+" --> "+topath+"/"+newdownload
	    os.rename(etpConst['entropyworkdir']+"/"+currentdownload,topath+"/"+filename)
	    # md5
	    os.rename(etpConst['entropyworkdir']+"/"+currentdownload+etpConst['packageshashfileext'],topath+"/"+filename+etpConst['packageshashfileext'])
	    
	    # XXX: we can barely ignore branch info injected into .tbz2 since they'll be ignored too
	    
	    # rename remotely
	    print_info(green(" * ")+darkred(atom+": ")+red("Moving file remotely..."), back = True)
	    # change filename remotely
	    for uri in etpConst['activatoruploaduris']:
		
		print_info(green(" * ")+darkred(atom+": ")+red("Moving file remotely on: ")+extractFTPHostFromUri(uri), back = True)
		
	        ftp = mirrorTools.handlerFTP(uri)
	        ftp.setCWD(etpConst['binaryurirelativepath'])
	        # create directory if it doesn't exist
	        if (not ftp.isFileAvailable(switchbranch)):
		    ftp.mkdir(switchbranch)
	        # rename tbz2
	        ftp.renameFile(currentbranch+"/"+filename,switchbranch+"/"+filename)
	        # rename md5
	        ftp.renameFile(currentbranch+"/"+filename+etpConst['packageshashfileext'],switchbranch+"/"+filename+etpConst['packageshashfileext'])
	        ftp.closeConnection()
	    
	dbconn.closeDB()
	print_info(green(" * ")+red("All the selected packages have been marked as requested. Remember to run activator."))
        return 0


    elif (options[0] == "remove"):

	print_info(green(" * ")+red("Scanning packages that would be removed ..."), back = True)
	
	myopts = options[1:]
	_myopts = []
	branch = None
	for opt in myopts:
	    if (opt.startswith("--branch=")) and (len(opt.split("=")) == 2):
		branch = opt.split("=")[1]
	    else:
		_myopts.append(opt)
	myopts = _myopts
	
	if len(myopts) == 0:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    return 10

	pkglist = set()
	dbconn = databaseTools.openServerDatabase(readOnly = False, noUpload = True)
	
	for atom in myopts:
	    if (branch):
	        pkg = dbconn.atomMatch(atom, matchBranches = (branch,))
	    else:
	        pkg = dbconn.atomMatch(atom)
	    if pkg[0] != -1:
	        pkglist.add(pkg[0])

	# check if atoms were found
	if not pkglist:
	    print
	    dbconn.closeDB()
	    print_error(yellow(" * ")+red("No packages found."))
	    return 11
	
	print_info(green(" * ")+red("These are the packages that would be removed from the database:"))

	for pkg in pkglist:
	    pkgatom = dbconn.retrieveAtom(pkg)
	    branch = dbconn.retrieveBranch(pkg)
	    print_info(red("\t (*) ")+bold(pkgatom)+blue(" [")+red(branch)+blue("]"))

	# ask to continue
	rc = askquestion("     Would you like to continue ?")
	if rc == "No":
	    return 0
	
	# now mark them as stable
	print_info(green(" * ")+red("Removing selected packages ..."))

	# open db
	for pkg in pkglist:
	    pkgatom = dbconn.retrieveAtom(pkg)
	    print_info(green(" * ")+red("Removing package: ")+bold(pkgatom)+red(" ..."), back = True)
	    dbconn.removePackage(pkg)
	print_info(green(" * ")+red("All the selected packages have been removed as requested. To remove online binary packages, just run Activator."))
	dbconn.closeDB()
        return 0

    # used by reagent
    elif (options[0] == "md5check"):

	print_info(green(" * ")+red("Integrity verification of the selected packages:"))

	mypackages = options[1:]
	dbconn = databaseTools.openServerDatabase(readOnly = True, noUpload = True)
	
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
		result = dbconn.atomMatch(pkg, multiMatch = True, matchBranches = etpConst['branches'])
                if result[1] == 0:
                    for idresult in result[0]:
                        iatom = dbconn.retrieveAtom(idresult)
                        ibranch = dbconn.retrieveBranch(idresult)
                        pkgs2check.append((iatom,idresult,ibranch))
                else:
                    print_warning(red("ATTENTION: ")+blue("cannot match: ")+bold(pkg))

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
	    rc = askquestion("     Would you like to continue ?")
	    if rc == "No":
	        return 0

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
	    result = compareMd5(etpConst['packagesbindir']+"/"+pkgbranch+"/"+pkgfile,storedmd5)
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
        return 0


    # used by reagent
    elif (options[0] == "md5remote"):

	print_info(green(" * ")+red("Integrity verification of the selected packages:"))

	mypackages = options[1:]
	dbconn = databaseTools.openServerDatabase(readOnly = True, noUpload = True)
	worldSelected = False
	
	if (len(mypackages) == 0):
	    # check world
	    # create packages list
	    worldSelected = True
	    pkgs2check = dbconn.listAllIdpackages()
	elif (mypackages[0] == "world"):
	    # check world
	    # create packages list
	    worldSelected = True
	    pkgs2check = dbconn.listAllIdpackages()
	else:
	    # catch the names
	    pkgs2check = []
	    for pkg in mypackages:
		result = dbconn.atomMatch(pkg, multiMatch = True, matchBranches = etpConst['branches'])
                if result[1] == 0:
                    for idresult in result[0]:
                        pkgs2check.append(idresult)
                else:
                    print_warning(red("ATTENTION: ")+blue("cannot match: ")+bold(pkg))

	if (not worldSelected):
	    print_info(red("   This is the list of the packages that would be checked:"))
	else:
	    print_info(red("   All the packages in the Entropy Packages repository will be checked."))
	
	
        if (not worldSelected):
	    for idpackage in pkgs2check:
	        pkgatom = dbconn.retrieveAtom(idpackage)
                pkgbranch = dbconn.retrieveBranch(idpackage)
                pkgfile = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
                print_info(green("   - ")+red(pkgatom)+" -> "+bold(str(pkgbranch)+"/"+pkgfile))
	
	if (not databaseRequestNoAsk):
	    rc = askquestion("     Would you like to continue ?")
	    if rc == "No":
	        return 0

        import remoteTools
        for uri in etpConst['activatoruploaduris']:

            # statistic vars
            pkgMatch = 0
            pkgNotMatch = 0
            currentcounter = 0
            print_info(green(" * ")+yellow("Working on ")+bold(extractFTPHostFromUri(uri)+red(" mirror.")))
            brokenPkgsList = []
            totalcounter = str(len(pkgs2check))


            for idpackage in pkgs2check:

                currentcounter += 1
                pkgfile = dbconn.retrieveDownloadURL(idpackage)
                pkgbranch = dbconn.retrieveBranch(idpackage)
                pkgfilename = os.path.basename(pkgfile)

                print_info("  ("+red(str(currentcounter))+"/"+blue(totalcounter)+") "+red("Checking hash of ")+blue(pkgbranch+"/"+pkgfilename), back = True)
                ckOk = False
                ck = remoteTools.getRemotePackageChecksum(extractFTPHostFromUri(uri),pkgfilename, pkgbranch)
                if ck == None:
                    print_warning("    "+red("   -> Digest verification of ")+green(pkgfilename)+bold(" not supported"))
                elif len(ck) == 32:
                    ckOk = True
                else:
                    print_warning("    "+red("   -> Digest verification of ")+green(pkgfilename)+bold(" failed for unknown reasons"))

                if (ckOk):
                    pkgMatch += 1
                else:
                    pkgNotMatch += 1
                    print_error(red("   Package ")+blue(pkgbranch+"/"+pkgfilename)+red(" is NOT healthy."))
                    brokenPkgsList.append(pkgbranch+"/"+pkgfilename)

            if (brokenPkgsList):
                print_info(blue(" *  This is the list of broken packages: "))
                for bp in brokenPkgsList:
                    print_info(red("    * Package: ")+bold(bp))

            # print stats
            print_info(blue(" *  Statistics for "+extractFTPHostFromUri(uri)+":"))
            print_info(yellow("     Number of checked packages:\t\t")+str(pkgMatch+pkgNotMatch))
            print_info(green("     Number of healthy packages:\t\t")+str(pkgMatch))
            print_info(red("     Number of broken packages:\t\t")+str(pkgNotMatch))

        dbconn.closeDB()
        return 0
