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
import commands
import re
from sys import exit,getfilesystemencoding,path
import os
from portageTools import synthetizeRoughDependencies, getThirdPartyMirrors, getPackagesInSystem, getConfigProtectAndMask

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
    etpData = extractPkgData(package, enzymeRequestBranch)
    
    if dbconnection is None:
	dbconn = databaseTools.openServerDatabase(readOnly = False, noUpload = True)
    else:
	dbconn = dbconnection

    idpk, revision, etpDataUpdated, accepted = dbconn.handlePackage(etpData)
    
    # add package info to our official repository etpConst['officialrepositoryname']
    if (accepted):
        dbconn.removePackageFromInstalledTable(idpk)
	dbconn.addPackageToInstalledTable(idpk,etpConst['officialrepositoryname'])
    
    # return back also the new possible package filename, so that we can make decisions on that
    newFileName = os.path.basename(etpDataUpdated['download'])
    
    if dbconnection is None:
	dbconn.commitChanges()
	dbconn.closeDB()

    if (accepted) and (revision != 0):
	reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"generator: entry for "+str(packagename)+" has been updated to revision: "+str(revision))
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" entry has been updated. Revision: ")+bold(str(revision)))
	return True, newFileName, idpk
    elif (accepted) and (revision == 0):
	reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"generator: entry for "+str(packagename)+" newly created or version bumped.")
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" entry newly created."))
	return True, newFileName, idpk
    else:
	reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"generator: entry for "+str(packagename)+" kept intact, no updates needed.")
	print_info(green(" * ")+red("Package ")+bold(packagename)+red(" does not need to be updated. Current revision: ")+bold(str(revision)))
	return False, newFileName, idpk


# This tool is used by Entropy after enzyme, it simply parses the content of etpConst['packagesstoredir']
def update(options):

    reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"update: called -> options: "+str(options))

    # differential checking
    # collect differences between the packages in the database and the ones on the system
    
    reagentRequestSeekStore = False
    reagentRequestRepackage = False
    repackageItems = []
    _options = []
    for opt in options:
	if opt.startswith("--seekstore"):
	    reagentRequestSeekStore = True
	elif opt.startswith("--repackage"):
	    reagentRequestRepackage = True
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
            print_info(yellow(" * ")+red("Scanning the database for differences..."))
            from portageTools import getInstalledPackagesCounters, quickpkg, getPackageSlot
            installedPackages = getInstalledPackagesCounters()
            installedCounters = {}
            databasePackages = dbconn.listAllPackages()
            toBeAdded = []
            toBeRemoved = []
	    
            # packages to be added
            for x in installedPackages[0]:
	        installedCounters[x[1]] = 1
	        counter = dbconn.isCounterAvailable(x[1])
	        if (not counter):
	            toBeAdded.append(x)

            # packages to be removed from the database
            databaseCounters = dbconn.listAllCounters()
            for x in databaseCounters:
	        match = installedCounters.get(x[0], None)
	        #print match
	        if (not match):
	            # check if the package is in toBeAdded
	            if (toBeAdded):
			#print x
	                atomkey = dep_getkey(dbconn.retrieveAtom(x[1]))
		        atomslot = dbconn.retrieveSlot(x[1])
		        add = True
		        for pkgdata in toBeAdded:
		            addslot = getPackageSlot(pkgdata[0])
		            addkey = dep_getkey(pkgdata[0])
		            # workaround for ebuilds not having slot
		            if addslot == None:
			        addslot = ''
		            if (atomkey == addkey) and (atomslot == addslot):
			        # do not add to toBeRemoved
			        add = False
			        break
		        if add:
		            toBeRemoved.append(x[1])
	            else:
	                toBeRemoved.append(x[1])

            if (not toBeRemoved) and (not toBeAdded):
	        print_info(yellow(" * ")+red("Nothing to do, check later."))
	        # then exit gracefully
	        exit(0)

            if (toBeRemoved):
	        print_info(yellow(" @@ ")+blue("These are the packages that would be removed from the database:"))
	        for x in toBeRemoved:
	            atom = dbconn.retrieveAtom(x)
	            print_info(yellow("    # ")+red(atom))
	        rc = askquestion(">>   Would you like to remove them now ?")
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
	        rc = askquestion(">>   Would you like to packetize them now ?")
	        if rc == "No":
	            exit(0)

	else:
	    if not repackageItems:
	        print_info(yellow(" * ")+red("Nothing to do, check later."))
	        # then exit gracefully
	        exit(0)
	    
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
	    
	    # FIXME: complete this
	    if not packages:
	        print_info(yellow(" * ")+red("Nothing to do, check later."))
	        # then exit gracefully
	        exit(0)
	    
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
	        exit(251)

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
	exit(0)

    # open db connection
    dbconn = databaseTools.openServerDatabase(readOnly = False, noUpload = True)

    counter = 0
    etpCreated = 0
    etpNotCreated = 0
    for tbz2 in tbz2files:
	counter += 1
	tbz2name = tbz2.split("/")[len(tbz2.split("/"))-1]
	print_info(" ("+str(counter)+"/"+str(totalCounter)+") Processing "+tbz2name)
	tbz2path = etpConst['packagesstoredir']+"/"+tbz2
	rc, newFileName, idpk = generator(tbz2path, dbconn, enzymeRequestBranch)
	if (rc):
	    etpCreated += 1
	    # move the file with its new name
	    spawnCommand("mv "+tbz2path+" "+etpConst['packagessuploaddir']+"/"+enzymeRequestBranch+"/"+newFileName+" -f")
	    print_info(yellow(" * ")+red("Injecting database information into ")+bold(newFileName)+red(", please wait..."), back = True)
	    
	    dbpath = etpConst['packagestmpdir']+"/"+"data.db"
	    # create db
	    pkgDbconn = databaseTools.etpDatabase(readOnly = False, noUpload = True, dbFile = dbpath, clientDatabase = True, xcache = False)
	    pkgDbconn.initializeDatabase()
	    data = dbconn.getPackageData(idpk)
	    rev = dbconn.retrieveRevision(idpk)
	    # inject
	    pkgDbconn.addPackage(data, revision = rev)
	    pkgDbconn.closeDB()
	    # append the database to the new file
	    aggregateEdb(tbz2file = etpConst['packagessuploaddir']+"/"+enzymeRequestBranch+"/"+newFileName, dbfile = dbpath)
	    
	    digest = md5sum(etpConst['packagessuploaddir']+"/"+enzymeRequestBranch+"/"+newFileName)
	    dbconn.setDigest(idpk,digest)
	    hashFilePath = createHashFile(etpConst['packagessuploaddir']+"/"+enzymeRequestBranch+"/"+newFileName)
	    # remove garbage
	    spawnCommand("rm -rf "+dbpath)
	    print_info(yellow(" * ")+red("Database injection complete for ")+newFileName)
	    
	else:
	    etpNotCreated += 1
	    spawnCommand("rm -rf "+tbz2path)
	dbconn.commitChanges()

    dbconn.commitChanges()
    
    # regen dependstable
    dependsTableInitialize(dbconn, False)
    
    dbconn.closeDB()

    print_info(green(" * ")+red("Statistics: ")+blue("Entries created/updated: ")+bold(str(etpCreated))+yellow(" - ")+darkblue("Entries discarded: ")+bold(str(etpNotCreated)))

# This function extracts all the info from a .tbz2 file and returns them
def extractPkgData(package, etpBranch = etpConst['branch']):

    reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"extractPkgData: called -> package: "+str(package))

    info_package = bold(os.path.basename(package))+": "
    # Clean the variables
    for i in etpData:
	etpData[i] = u""

    print_info(yellow(" * ")+red(info_package+"Getting package name/version..."),back = True)
    tbz2File = package
    package = package.split(".tbz2")[0]
    package = remove_tag(package)
    
    # FIXME: deprecated - will be removed soonly
    if package.split("-")[len(package.split("-"))-1].startswith("t"):
        package = '-t'.join(package.split("-t")[:-1])
    
    package = package.split("-")
    pkgname = ""
    pkglen = len(package)
    if package[pkglen-1].startswith("r"):
        pkgver = package[pkglen-2]+"-"+package[pkglen-1]
	pkglen -= 2
    else:
	pkgver = package[len(package)-1]
	pkglen -= 1
    for i in range(pkglen):
	if i == pkglen-1:
	    pkgname += package[i]
	else:
	    pkgname += package[i]+"-"
    pkgname = pkgname.split("/")[len(pkgname.split("/"))-1]

    # Fill Package name and version
    etpData['name'] = pkgname
    etpData['version'] = pkgver

    print_info(yellow(" * ")+red(info_package+"Getting package md5..."),back = True)
    # .tbz2 md5
    etpData['digest'] = md5sum(tbz2File)

    print_info(yellow(" * ")+red(info_package+"Getting package mtime..."),back = True)
    # .tbz2 md5
    etpData['datecreation'] = str(getFileUnixMtime(tbz2File))
    
    print_info(yellow(" * ")+red(info_package+"Getting package size..."),back = True)
    # .tbz2 byte size
    etpData['size'] = str(os.stat(tbz2File)[6])
    
    print_info(yellow(" * ")+red(info_package+"Unpacking package data..."),back = True)
    # unpack file
    tbz2TmpDir = etpConst['packagestmpdir']+"/"+etpData['name']+"-"+etpData['version']+"/"
    extractXpak(tbz2File,tbz2TmpDir)

    print_info(yellow(" * ")+red(info_package+"Getting package CHOST..."),back = True)
    # Fill chost
    f = open(tbz2TmpDir+dbCHOST,"r")
    etpData['chost'] = f.readline().strip()
    f.close()

    print_info(yellow(" * ")+red(info_package+"Setting package branch..."),back = True)
    etpData['branch'] = etpBranch

    print_info(yellow(" * ")+red(info_package+"Getting package description..."),back = True)
    # Fill description
    etpData['description'] = ""
    try:
        f = open(tbz2TmpDir+dbDESCRIPTION,"r")
        etpData['description'] = f.readline().strip()
        f.close()
    except IOError:
        pass

    print_info(yellow(" * ")+red(info_package+"Getting package homepage..."),back = True)
    # Fill homepage
    etpData['homepage'] = ""
    try:
        f = open(tbz2TmpDir+dbHOMEPAGE,"r")
        etpData['homepage'] = f.readline().strip()
        f.close()
    except IOError:
        pass

    print_info(yellow(" * ")+red(info_package+"Getting package slot information..."),back = True)
    # fill slot, if it is
    etpData['slot'] = ""
    try:
        f = open(tbz2TmpDir+dbSLOT,"r")
        etpData['slot'] = f.readline().strip()
        f.close()
    except IOError:
        pass

    print_info(yellow(" * ")+red(info_package+"Getting package eclasses information..."),back = True)
    # fill eclasses list
    etpData['eclasses'] = []
    try:
        f = open(tbz2TmpDir+dbINHERITED,"r")
        etpData['eclasses'] = f.readline().strip().split()
        f.close()
    except IOError:
        pass

    print_info(yellow(" * ")+red(info_package+"Getting package needed libraries information..."),back = True)
    # fill needed list
    etpData['needed'] = set()
    try:
        f = open(tbz2TmpDir+dbNEEDED,"r")
	lines = f.readlines()
	f.close()
	for line in lines:
	    line = line.strip()
	    if line:
	        needed = line.split()
		if len(needed) == 2:
		    libs = needed[1].split(",")
		    for lib in libs:
			if (lib.find(".so") != -1):
			    etpData['needed'].add(lib)
    except IOError:
        pass
    etpData['needed'] = list(etpData['needed'])

    print_info(yellow(" * ")+red(info_package+"Getting package content..."),back = True)
    # dbCONTENTS
    etpData['content'] = []
    try:
        f = open(tbz2TmpDir+dbCONTENTS,"r")
        content = f.readlines()
        f.close()
	outcontent = []
	for line in content:
	    line = line.strip().split()
	    if (line[0] == "obj") or (line[0] == "sym"):
		# remove first object (obj or sym)
		datafile = line[1:]
		# remove checksum and mtime - obj and sym have it
		try:
		    if line[0] == "obj":
		        datafile = datafile[:len(datafile)-2]
		    else:
			datafile = datafile[:len(datafile)-3]
                    datafile = ' '.join(datafile)
		except:
		    datafile = datafile[0] # FIXME: handle shit better
		outcontent.append(datafile)
	# filter bad utf-8 chars
	_outcontent = []
	for i in outcontent:
	    try:
		i = i.encode(getfilesystemencoding())
		_outcontent.append(i)
	    except:
		pass
	outcontent = _outcontent
	for i in outcontent:
	    etpData['content'].append(i.encode("utf-8"))
	
    except IOError:
        pass

    # files size on disk
    if (etpData['content']):
	etpData['disksize'] = 0
	for file in etpData['content']:
	    try:
		size = os.stat(file)[6]
		etpData['disksize'] += size
	    except:
		pass
    else:
	etpData['disksize'] = 0

    # [][][] Kernel dependent packages hook [][][]
    kernelDependentModule = False
    kernelItself = False
    for file in etpData['content']:
	if file.find("/lib/modules/") != -1:
	    kernelDependentModule = True
	    # get the version of the modules
	    kmodver = file.split("/lib/modules/")[1]
	    kmodver = kmodver.split("/")[0]

	    lp = kmodver.split("-")[len(kmodver.split("-"))-1]
	    if lp.startswith("r"):
	        kname = kmodver.split("-")[len(kmodver.split("-"))-2]
	        kver = kmodver.split("-")[0]+"-"+kmodver.split("-")[len(kmodver.split("-"))-1]
	    else:
	        kname = kmodver.split("-")[len(kmodver.split("-"))-1]
	        kver = kmodver.split("-")[0]
	    break
    # validate the results above
    if (kernelDependentModule):
	matchatom = "linux-"+kname+"-"+kver
	if (matchatom == etpData['name']+"-"+etpData['version']):
	    # discard, it's the kernel itself, add other deps instead
	    kernelItself = True
	    kernelDependentModule = False

    # add strict kernel dependency
    # done below
    
    print_info(yellow(" * ")+red(info_package+"Getting package download URL..."),back = True)
    # Fill download relative URI
    if (kernelDependentModule):
	etpData['versiontag'] = kmodver
	# force slot == tag:
	etpData['slot'] = kmodver
	versiontag = "#"+etpData['versiontag']
    else:
	versiontag = ""
    etpData['download'] = etpConst['binaryurirelativepath']+etpData['branch']+"/"+etpData['name']+"-"+etpData['version']+versiontag+".tbz2"

    print_info(yellow(" * ")+red(info_package+"Getting package counter..."),back = True)
    # Fill counter
    f = open(tbz2TmpDir+dbCOUNTER,"r")
    etpData['counter'] = f.readline().strip()
    f.close()

    print_info(yellow(" * ")+red(info_package+"Getting package category..."),back = True)
    # Fill category
    f = open(tbz2TmpDir+dbCATEGORY,"r")
    etpData['category'] = f.readline().strip()
    f.close()
    
    etpData['trigger'] = ""
    print_info(yellow(" * ")+red(info_package+"Getting package external trigger availability..."),back = True)
    if os.path.isfile(etpConst['triggersdir']+"/"+etpData['category']+"/"+etpData['name']+"/"+etpConst['triggername']):
        f = open(etpConst['triggersdir']+"/"+etpData['category']+"/"+etpData['name']+"/"+etpConst['triggername'],"rb")
        f.seek(0,2)
        size = f.tell()
        f.seek(0)
	etpData['trigger'] = f.read(size)
        f.close()

    print_info(yellow(" * ")+red(info_package+"Getting package CFLAGS..."),back = True)
    # Fill CFLAGS
    etpData['cflags'] = ""
    try:
        f = open(tbz2TmpDir+dbCFLAGS,"r")
        etpData['cflags'] = f.readline().strip()
        f.close()
    except IOError:
        pass

    print_info(yellow(" * ")+red(info_package+"Getting package CXXFLAGS..."),back = True)
    # Fill CXXFLAGS
    etpData['cxxflags'] = ""
    try:
        f = open(tbz2TmpDir+dbCXXFLAGS,"r")
        etpData['cxxflags'] = f.readline().strip()
        f.close()
    except IOError:
        pass

    print_info(yellow(" * ")+red(info_package+"Getting package License information..."),back = True)
    # Fill license
    etpData['license'] = []
    try:
        f = open(tbz2TmpDir+dbLICENSE,"r")
	# strip away || ( )
	tmpLic = f.readline().strip().split()
	f.close()
	for x in tmpLic:
	    if x:
		if (not x.startswith("|")) and (not x.startswith("(")) and (not x.startswith(")")):
		    etpData['license'].append(x)
	etpData['license'] = ' '.join(etpData['license'])
    except IOError:
	etpData['license'] = ""
        pass

    print_info(yellow(" * ")+red(info_package+"Getting package USE flags..."),back = True)
    # Fill USE
    etpData['useflags'] = []
    f = open(tbz2TmpDir+dbUSE,"r")
    tmpUSE = f.readline().strip()
    f.close()

    try:
        f = open(tbz2TmpDir+dbIUSE,"r")
        tmpIUSE = f.readline().strip().split()
        f.close()
    except IOError:
        tmpIUSE = []

    PackageFlags = []
    for x in tmpUSE.split():
	if (x):
	    PackageFlags.append(x)

    for i in tmpIUSE:
	try:
	    PackageFlags.index(i)
	    etpData['useflags'].append(i)
	except:
	    etpData['useflags'].append("-"+i)

    print_info(yellow(" * ")+red(info_package+"Getting package provide content..."),back = True)
    # Fill Provide
    etpData['provide'] = []
    try:
        f = open(tbz2TmpDir+dbPROVIDE,"r")
        provide = f.readline().strip()
        f.close()
	if (provide):
	    provide = provide.split()
	    for x in provide:
		etpData['provide'].append(x)
    except:
        pass

    print_info(yellow(" * ")+red(info_package+"Getting package sources information..."),back = True)
    # Fill sources
    etpData['sources'] = []
    try:
        f = open(tbz2TmpDir+dbSRC_URI,"r")
	sources = f.readline().strip().split()
        f.close()
	tmpData = []
	cnt = -1
	skip = False
	etpData['sources'] = []
	
	for source in sources:
	    cnt += +1
	    if source.endswith("?"):
		# it's an use flag
		source = source[:len(source)-1]
		direction = True
		if source.startswith("!"):
		    direction = False
		    source = source[1:]
		# now get the useflag
		useflag = False
		try:
		    etpData['useflags'].index(source)
		    useflag = True
		except:
		    pass
		
		
		if (useflag) and (direction): # useflag is enabled and it's asking for sources or useflag is not enabled and it's not not (= True) asking for sources
		    # ack parsing from ( to )
		    skip = False
		elif (useflag) and (not direction):
		    # deny parsing from ( to )
		    skip = True
		elif (not useflag) and (direction):
		    # deny parsing from ( to )
		    skip = True
		else:
		    # ack parsing from ( to )
		    skip = False

	    elif source.startswith(")"):
		# reset skip
		skip = False

	    elif (not source.startswith("(")):
		if (not skip):
		    etpData['sources'].append(source)
    
    except IOError:
	pass

    print_info(yellow(" * ")+red(info_package+"Getting package mirrors list..."),back = True)
    # manage etpData['sources'] to create etpData['mirrorlinks']
    # =mirror://openoffice|link1|link2|link3
    etpData['mirrorlinks'] = []
    for i in etpData['sources']:
        if i.startswith("mirror://"):
	    # parse what mirror I need
	    mirrorURI = i.split("/")[2]
	    mirrorlist = getThirdPartyMirrors(mirrorURI)
            etpData['mirrorlinks'].append([mirrorURI,mirrorlist]) # mirrorURI = openoffice and mirrorlist = [link1, link2, link3]

    print_info(yellow(" * ")+red(info_package+"Getting source package supported ARCHs..."),back = True)
    # fill KEYWORDS
    etpData['keywords'] = []
    try:
        f = open(tbz2TmpDir+dbKEYWORDS,"r")
        cnt = f.readline().strip().split()
	for i in cnt:
	    if i:
		etpData['keywords'].append(i)
        f.close()
    except IOError:
	pass

    print_info(yellow(" * ")+red(info_package+"Getting package supported ARCHs..."),back = True)
    
    # fill ARCHs
    kwords = etpData['keywords']
    _kwords = []
    for i in kwords:
	if i.startswith("~"):
	    i = i[1:]
	_kwords.append(i)
    etpData['binkeywords'] = []
    for i in etpConst['supportedarchs']:
	try:
	    x = _kwords.index(i)
	    etpData['binkeywords'].append(i)
	except:
	    pass

    print_info(yellow(" * ")+red(info_package+"Getting package dependencies..."),back = True)
    # Fill dependencies
    # to fill dependencies we use *DEPEND files
    f = open(tbz2TmpDir+dbRDEPEND,"r")
    roughDependencies = f.readline().strip()
    f.close()
    if (not roughDependencies):
        f = open(tbz2TmpDir+dbDEPEND,"r")
        roughDependencies = f.readline().strip()
        f.close()
    f = open(tbz2TmpDir+dbPDEPEND,"r")
    roughDependencies += " "+f.readline().strip()
    f.close()
    roughDependencies = roughDependencies.split()
    
    # variables filled
    # etpData['dependencies'], etpData['conflicts']
    deps,conflicts = synthetizeRoughDependencies(roughDependencies,' '.join(PackageFlags))
    etpData['dependencies'] = []
    for i in deps.split():
	etpData['dependencies'].append(i)
    etpData['conflicts'] = []
    for i in conflicts.split():
	# check if i == PROVIDE
	if i not in etpData['provide']: # we handle these conflicts using emerge, so we can just filter them out
	    etpData['conflicts'].append(i)
    
    if (kernelDependentModule):
	# add kname to the dependency
	etpData['dependencies'].append("=sys-kernel/linux-"+kname+"-"+kver)

    if (kernelItself):
	# it's the kernel, add dependency on all tagged packages
	try:
	    etpData['dependencies'].append("=sys-kernel/linux-"+kname+"-modules-"+kver)
	except:
	    pass

    print_info(yellow(" * ")+red(info_package+"Getting System package List..."),back = True)
    # write only if it's a systempackage
    systemPackages = getPackagesInSystem()
    for x in systemPackages:
	x = dep_getkey(x)
	y = etpData['category']+"/"+etpData['name']
	if x == y:
	    # found
	    etpData['systempackage'] = "xxx"
	    break

    print_info(yellow(" * ")+red(info_package+"Getting CONFIG_PROTECT/CONFIG_PROTECT_MASK List..."),back = True)
    # write only if it's a systempackage
    protect, mask = getConfigProtectAndMask()
    etpData['config_protect'] = protect
    etpData['config_protect_mask'] = mask
    
    # fill etpData['messages']
    # etpConst['logdir']+"/elog"
    etpData['messages'] = []
    if os.path.isdir(etpConst['logdir']+"/elog"):
        elogfiles = os.listdir(etpConst['logdir']+"/elog")
	myelogfile = etpData['category']+":"+etpData['name']+"-"+etpData['version']
	foundfiles = []
	for file in elogfiles:
	    if file.startswith(myelogfile):
		foundfiles.append(file)
	if foundfiles:
	    elogfile = foundfiles[0]
	    if len(foundfiles) > 1:
		# get the latest
		mtimes = []
		for file in foundfiles:
		    mtimes.append((getFileUnixMtime(etpConst['logdir']+"/elog/"+file),file))
		mtimes.sort()
		elogfile = mtimes[len(mtimes)-1][1]
	    messages = extractElog(etpConst['logdir']+"/elog/"+elogfile)
	    for message in messages:
		out = re.subn("emerge","equo install",message)
		message = out[0]
		etpData['messages'].append(message)
    else:
	print_warning(red(etpConst['logdir']+"/elog")+" not set, have you configured make.conf properly?")

    print_info(yellow(" * ")+red(info_package+"Getting Entropy API version..."),back = True)
    # write API info
    etpData['etpapi'] = etpConst['etpapi']
    
    # removing temporary directory
    os.system("rm -rf "+tbz2TmpDir)

    print_info(yellow(" * ")+red(info_package+"Done"),back = True)
    return etpData


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


def dependenciesTest(options):

    reagentRequestQuiet = False
    for opt in options:
	if opt.startswith("--quiet"):
	    reagentRequestQuiet = True

    if (not reagentRequestQuiet):
        print_info(red(" @@ ")+blue("ATTENTION: you need to have equo.conf properly configured only for your running repository !!"))
        print_info(red(" @@ ")+blue("Running dependency test..."))

    dbconn = databaseTools.openServerDatabase(readOnly = True, noUpload = True)
    
    # hey Equo, how are you?
    path.append('../client')
    import equoTools
    equoTools.syncRepositories(quiet = reagentRequestQuiet)

    # get all the installed packages
    installedPackages = dbconn.listAllIdpackages()
    
    depsNotFound = {}
    depsNotSatisfied = {}
    # now look
    length = str((len(installedPackages)))
    count = 0
    for xidpackage in installedPackages:
	count += 1
	atom = dbconn.retrieveAtom(xidpackage)
	if (not reagentRequestQuiet):
	    print_info(darkred(" @@ ")+bold("(")+blue(str(count))+"/"+red(length)+bold(")")+darkgreen(" Checking ")+bold(atom), back = True)
	deptree, status = equoTools.generateDependencyTree((xidpackage,0))
	
	if (status == -2): # dependencies not found
	    depsNotFound[xidpackage] = []
	    if (deptree):
	        for x in deptree:
	            depsNotFound[xidpackage].append(x)

	elif (status == 0):

	    # FIXME: add conflicts handling (aka, show up something!)
	    conflicts = deptree.get(0,None)
	    if (conflicts):
		print conflicts
	        deptree[0] = []

	    depsNotSatisfied[xidpackage] = []
	    for x in range(len(deptree))[::-1]:
	        for z in deptree[x]:
		    depsNotSatisfied[xidpackage].append(z)
	    if (not depsNotSatisfied[xidpackage]):
		del depsNotSatisfied[xidpackage]
	
    packagesNeeded = []
    if (depsNotSatisfied):
	if (not reagentRequestQuiet):
            print_info(red(" @@ ")+blue("These are the packages that lack dependencies: "))
	for dict in depsNotSatisfied:
	    pkgatom = dbconn.retrieveAtom(dict)
	    if (not reagentRequestQuiet):
	        print_info(darkred("   ### ")+blue(pkgatom))
	    for dep in depsNotSatisfied[dict]:
		depatom = dbconn.retrieveAtom(dep)
		if (not reagentRequestQuiet):
		    print_info(bold("       :: ")+red(depatom))
		packagesNeeded.append([depatom,dep])

    packagesNotFound = []
    if (depsNotFound):
	if (not reagentRequestQuiet):
            print_info(red(" @@ ")+blue("These are the packages not found, that respective packages in repository need:"))
	for dict in depsNotFound:
	    pkgatom = dbconn.retrieveAtom(dict)
	    if (not reagentRequestQuiet):
	        print_info(darkred("   ### ")+blue(pkgatom))
	    for pkg in depsNotFound[dict]:
		if (not reagentRequestQuiet):
	            print_info(bold("       :: ")+red(pkg))
	        packagesNotFound.append(pkg)

    packagesNotFound = filterDuplicatedEntries(packagesNotFound)

    if (reagentRequestQuiet):
	for x in packagesNotFound:
	    print x

    dbconn.closeDB()
    return 0,packagesNeeded,packagesNotFound


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
	exit(301)

    if (options[0] == "--initialize"):
	
	# do some check, print some warnings
	print_info(green(" * ")+red("Initializing Entropy database..."), back = True)
        # database file: etpConst['etpdatabasefilepath']
	revisionsMatch = {}
        if os.path.isfile(etpConst['etpdatabasefilepath']):
	    dbconn = databaseTools.openServerDatabase(readOnly = True, noUpload = True)
	    idpackages = dbconn.listAllIdpackages()
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
	        exit(0)
	    os.remove(etpConst['etpdatabasefilepath'])

	# initialize the database
        dbconn = databaseTools.openServerDatabase(readOnly = False, noUpload = True)
	dbconn.initializeDatabase()
	
	# sync packages directory
	print "Revisions dump:"
	print revisionsMatch
	#activatorTools.packages(["sync","--ask"])
	
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
		
	        etpData = extractPkgData(etpConst['packagesbindir']+"/"+mybranch+"/"+pkg, mybranch)
	        # get previous revision
		revisionAvail = revisionsMatch.get(os.path.basename(etpData['download']))
		addRevision = 0
		if (revisionAvail != None):
		    if mybranch == revisionAvail[0]:
			addRevision = revisionAvail[1]
	        # fill the db entry
	        idpk, revision, etpDataUpdated, accepted = dbconn.addPackage(etpData, revision = addRevision)
		
		print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+green("(")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(pkg)+red(". Revision: ")+blue(str(addRevision)))
	    
	    dbconn.commitChanges()
	
	# regen dependstable
        dependsTableInitialize(dbconn, False)
	
	dbconn.closeDB()
	print_info(green(" * ")+red("Entropy database has been reinitialized using binary packages available"))

    # used by reagent
    elif (options[0] == "search"):
	mykeywords = options[1:]
	if (len(mykeywords) == 0):
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    exit(302)
	if (not os.path.isfile(etpConst['etpdatabasefilepath'])):
	    print_error(yellow(" * ")+red("Entropy Datbase does not exist"))
	    exit(303)
	
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

    elif (options[0] == "create-empty-database"):
	mypath = options[1:]
	if len(mypath) == 0:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    exit(303)
	if (os.path.dirname(mypath[0]) != '') and (not os.path.isdir(os.path.dirname(mypath[0]))):
	    print_error(green(" * ")+red("Supplied directory does not exist."))
	    exit(304)
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

    elif (options[0] == "switchbranch"):
	
	if (len(options) < 2):
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    exit(302)

	switchbranch = options[1]
	print_info(green(" * ")+red("Collecting packages that would be marked '"+switchbranch+"' ..."), back = True)

	myatoms = options[2:]
	if not myatoms:
	    print_error(yellow(" * ")+red("Not enough parameters"))
	    exit(303)
	
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
	    exit(303)
	
	# show what would be done
	print_info(green(" * ")+red("These are the packages that would be marked '"+switchbranch+"':"))

	for pkg in pkglist:
	    atom = dbconn.retrieveAtom(pkg)
	    print_info(red("  (*) ")+bold(atom))

	rc = askquestion("     Would you like to continue ?")
	if rc == "No":
	    exit(0)
	
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
	    exit(303)

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
	    exit(303)
	
	print_info(green(" * ")+red("These are the packages that would be removed from the database:"))

	for pkg in pkglist:
	    pkgatom = dbconn.retrieveAtom(pkg)
	    branch = dbconn.retrieveBranch(pkg)
	    print_info(red("\t (*) ")+bold(pkgatom)+blue(" [")+red(branch)+blue("]"))

	# ask to continue
	rc = askquestion("     Would you like to continue ?")
	if rc == "No":
	    exit(0)
	
	# now mark them as stable
	print_info(green(" * ")+red("Removing selected packages ..."))

	# open db
	for pkg in pkglist:
	    pkgatom = dbconn.retrieveAtom(pkg)
	    print_info(green(" * ")+red("Removing package: ")+bold(pkgatom)+red(" ..."), back = True)
	    dbconn.removePackage(pkg)
	print_info(green(" * ")+red("All the selected packages have been removed as requested. To remove online binary packages, just run Activator."))
	dbconn.closeDB()

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
	        exit(0)

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
	    print_info(red("     Number of failed downloads:\t\t")+str(pkgDownloadedError))


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
	        exit(0)

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