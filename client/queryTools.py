#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy database query tools and library

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

import os
from entropyConstants import *
from clientConstants import *
from outputTools import *
from databaseTools import etpDatabase, openClientDatabase, openRepositoryDatabase
from entropyTools import dep_getkey, dep_getslot, remove_slot, dep_gettag, remove_tag, convertUnixTimeToHumanTime, bytesIntoHuman

########################################################
####
##   Query Tools
#

def query(options):

    rc = 0

    if len(options) < 1:
	return -10

    equoRequestVerbose = False
    equoRequestQuiet = False
    equoRequestDeep = False
    myopts = []
    for opt in options:
	if (opt == "--verbose"):
	    equoRequestVerbose = True
	elif (opt == "--quiet"):
	    equoRequestQuiet = True
	elif (opt == "--deep"):
	    equoRequestDeep = True
	else:
	    if not opt.startswith("-"):
	        myopts.append(opt)

    if myopts[0] == "installed":
	rc = searchInstalledPackages(myopts[1:], quiet = equoRequestQuiet)

    elif myopts[0] == "belongs":
	rc = searchBelongs(myopts[1:], quiet = equoRequestQuiet)

    elif myopts[0] == "depends":
	rc = searchDepends(myopts[1:], verbose = equoRequestVerbose, quiet = equoRequestQuiet)

    elif myopts[0] == "files":
	rc = searchFiles(myopts[1:], quiet = equoRequestQuiet)

    elif myopts[0] == "needed":
	rc = searchNeeded(myopts[1:], quiet = equoRequestQuiet)

    elif myopts[0] == "removal":
	rc = searchRemoval(myopts[1:], quiet = equoRequestQuiet, deep = equoRequestDeep)

    elif myopts[0] == "tags":
	if (len(myopts) > 1):
	    rc = searchTaggedPackages(myopts[1:], quiet = equoRequestQuiet)

    elif myopts[0] == "orphans":
	rc = searchOrphans(quiet = equoRequestQuiet)

    elif myopts[0] == "list":
	mylistopts = options[1:]
	if len(mylistopts) > 0:
	    if mylistopts[0] == "installed":
	        rc = searchInstalled(verbose = equoRequestVerbose, quiet = equoRequestQuiet)
    elif myopts[0] == "description":
	rc = searchDescription(myopts[1:], quiet = equoRequestQuiet)
    else:
        rc = -10

    return rc



def searchInstalledPackages(packages, idreturn = False, quiet = False):
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Searching..."))

    clientDbconn = openClientDatabase()
    dataInfo = set() # when idreturn is True
    
    for package in packages:
	slot = dep_getslot(package)
	tag = dep_gettag(package)
	package = remove_slot(package)
	package = remove_tag(package)
	
	result = clientDbconn.searchPackages(package, slot = slot, tag = tag)
	if (result):
	    for pkg in result:
		idpackage = pkg[1]
		atom = pkg[0]
		branch = clientDbconn.retrieveBranch(idpackage)
		if (idreturn):
		    dataInfo.add(idpackage)
		else:
		    printPackageInfo(idpackage, clientDbconn, clientSearch = True, quiet = quiet)
	    # print info
	    if (not idreturn) and (not quiet):
	        print_info(blue(" Keyword: ")+bold("\t"+package))
	        print_info(blue(" Found:   ")+bold("\t"+str(len(result)))+red(" entries"))
	
    clientDbconn.closeDB()

    if (idreturn):
	return dataInfo
    
    return 0


def searchBelongs(files, idreturn = False, quiet = False):
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Belong Search..."))

    clientDbconn = openClientDatabase()
    dataInfo = set() # when idreturn is True
    
    results = {}
    flatresults = {}
    for file in files:
	like = False
	if file.find("*") != -1:
	    import re
	    out = re.subn("\*","%",file)
	    file = out[0]
	    like = True
	results[file] = set()
	idpackages = clientDbconn.searchBelongs(file, like)
	for idpackage in idpackages:
	    if not flatresults.get(idpackage):
		results[file].add(idpackage)
		flatresults[idpackage] = True
    
    if (results):
	for result in results:
	    # print info
	    file = result
	    result = results[result]
	    for idpackage in result:
		if (idreturn):
		    dataInfo.add(idpackage)
		elif (quiet):
		    print clientDbconn.retrieveAtom(idpackage)
		else:
		    printPackageInfo(idpackage, clientDbconn, clientSearch = True)
	    if (not idreturn) and (not quiet):
	        print_info(blue(" Keyword: ")+bold("\t"+file))
	        print_info(blue(" Found:   ")+bold("\t"+str(len(result)))+red(" entries"))
	
    clientDbconn.closeDB()

    if (idreturn):
	return dataInfo
    
    return 0



def searchDepends(atoms, idreturn = False, verbose = False, quiet = False):
    
    from equoTools import atomMatch
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Depends Search..."))

    clientDbconn = openClientDatabase()

    dataInfo = set() # when idreturn is True
    for atom in atoms:
	result = clientDbconn.atomMatch(atom)
	matchInRepo = False
	if (result[0] == -1):
	    matchInRepo = True
	    result = atomMatch(atom)
	if (result[0] != -1):
	    if (matchInRepo):
	        dbconn = openRepositoryDatabase(result[1])
	    else:
		dbconn = clientDbconn
	    searchResults = dbconn.retrieveDepends(result[0])
	    if searchResults == -2:
		if (matchInRepo):
		    # run equo update
		    dbconn.closeDB()
		    syncRepositories([result[1]], forceUpdate = True)
		    dbconn = openRepositoryDatabase(result[1])
		else:
		    # I need to generate dependstable
		    dbconn.regenerateDependsTable()
	        searchResults = dbconn.retrieveDepends(result[0])
	    for idpackage in searchResults:
		if (idreturn):
		    dataInfo.add(idpackage)
		else:
		    if (verbose):
		        printPackageInfo(idpackage, dbconn, clientSearch = True, quiet = quiet)
		    else:
		        printPackageInfo(idpackage, dbconn, clientSearch = True, strictOutput = True, quiet = quiet)
	    # print info
	    if (not idreturn) and (not quiet):
	        print_info(blue(" Keyword: ")+bold("\t"+atom))
		if (matchInRepo):
		    where = " from repository "+str(result[1])
		else:
		    where = " from installed packages database"
	        print_info(blue(" Found:   ")+bold("\t"+str(len(searchResults)))+red(" entries")+where)
	else:
	    continue
	if (matchInRepo):
	    dbconn.closeDB()

    clientDbconn.closeDB()

    if (idreturn):
	return dataInfo
    
    return 0

def searchNeeded(atoms, idreturn = False, quiet = False):
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Needed Search..."))

    clientDbconn = openClientDatabase()
    dataInfo = set() # when idreturn is True
    
    for atom in atoms:
	match = clientDbconn.atomMatch(atom)
	if (match[0] != -1):
	    # print info
	    myatom = clientDbconn.retrieveAtom(match[0])
	    myneeded = clientDbconn.retrieveNeeded(match[0])
	    for needed in myneeded:
		if (idreturn):
		    dataInfo.add(needed)
		elif (quiet):
		    print needed
		else:
		    print_info(blue("       # ")+red(str(needed)))
	    if (not idreturn) and (not quiet):
	        print_info(blue("     Atom: ")+bold("\t"+myatom))
	        print_info(blue(" Found:   ")+bold("\t"+str(len(myneeded)))+red(" libraries"))
	
    clientDbconn.closeDB()

    if (idreturn):
	return dataInfo
    
    return 0

def searchFiles(atoms, idreturn = False, quiet = False):
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Files Search..."))

    results = searchInstalledPackages(atoms, idreturn = True)
    clientDbconn = openClientDatabase()
    dataInfo = set() # when idreturn is True
    for result in results:
	if (result != -1):
	    files = clientDbconn.retrieveContent(result)
	    atom = clientDbconn.retrieveAtom(result)
            files = list(files)
            files.sort()
	    # print info
	    if (idreturn):
		dataInfo.add((result,files))
	    else:
		if quiet:
		    for file in files:
			print file
		else:
		    for file in files:
		        print_info(blue(" ### ")+red(file))
	    if (not idreturn) and (not quiet):
	        print_info(blue(" Package: ")+bold("\t"+atom))
	        print_info(blue(" Found:   ")+bold("\t"+str(len(files)))+red(" files"))
	
    clientDbconn.closeDB()

    if (idreturn):
	return dataInfo
    
    return 0



def searchOrphans(quiet = False):

    if (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Orphans Search..."))

    # start to list all files on the system:
    dirs = etpConst['filesystemdirs']
    foundFiles = set()
    for dir in dirs:
	for currentdir,subdirs,files in os.walk(dir):
	    for filename in files:
		file = currentdir+"/"+filename
		# filter python compiled objects?
		if filename.endswith(".pyo") or filename.startswith(".pyc") or filename == '.keep':
		    continue
		mask = [x for x in etpConst['filesystemdirsmask'] if file.startswith(x)]
		if (not mask):
		    if (not quiet):
		        print_info(red(" @@ ")+blue("Looking: ")+bold(file[:50]+"..."), back = True)
	            foundFiles.add(file)
    totalfiles = len(foundFiles)
    if (not quiet):
	print_info(red(" @@ ")+blue("Analyzed directories: ")+' '.join(etpConst['filesystemdirs']))
	print_info(red(" @@ ")+blue("Masked directories: ")+' '.join(etpConst['filesystemdirsmask']))
        print_info(red(" @@ ")+blue("Number of files collected on the filesystem: ")+bold(str(totalfiles)))
        print_info(red(" @@ ")+blue("Now looking into Installed Packages database..."))

    # list all idpackages
    clientDbconn = openClientDatabase()
    idpackages = clientDbconn.listAllIdpackages()
    # create content list
    length = str(len(idpackages))
    count = 0
    for idpackage in idpackages:
	if (not quiet):
	    count += 1
	    atom = clientDbconn.retrieveAtom(idpackage)
	    txt = "["+str(count)+"/"+length+"] "
	    print_info(red(" @@ ")+blue("Intersecting content of package: ")+txt+bold(atom), back = True)
	content = clientDbconn.retrieveContent(idpackage)
	_content = set()
	for x in content:
	    if x.startswith("/usr/lib64"):
		x = "/usr/lib"+x[len("/usr/lib64"):]
	    _content.add(x)
	# remove from foundFiles
	del content
	foundFiles.difference_update(_content)
    if (not quiet):
        print_info(red(" @@ ")+blue("Intersection completed. Showing statistics: "))
	print_info(red(" @@ ")+blue("Number of total files: ")+bold(str(totalfiles)))
	print_info(red(" @@ ")+blue("Number of matching files: ")+bold(str(totalfiles - len(foundFiles))))
	print_info(red(" @@ ")+blue("Number of orphaned files: ")+bold(str(len(foundFiles))))

    # order
    foundFiles = list(foundFiles)
    foundFiles.sort()
    if (not quiet):
	print_info(red(" @@ ")+blue("Writing file to disk: ")+bold("/tmp/equo-orphans.txt"))
        f = open("/tmp/equo-orphans.txt","w")
        for x in foundFiles:
	    f.write(x+"\n")
        f.flush()
        f.close()
	return 0
    else:
	for x in foundFiles:
	    print x

    return 0


def searchRemoval(atoms, idreturn = False, quiet = False, deep = False):
    
    from equoTools import generateDependsTree
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Removal Search..."))

    clientDbconn = openClientDatabase()
    foundAtoms = []
    for atom in atoms:
	match = clientDbconn.atomMatch(atom)
	if match[1] == 0:
	    foundAtoms.append(match[0])

    # are packages in foundAtoms?
    if (len(foundAtoms) == 0):
	print_error(red("No packages found."))
	return 127,-1

    choosenRemovalQueue = []
    if (not quiet):
        print_info(red(" @@ ")+blue("Calculating removal dependencies, please wait..."), back = True)
    treeview = generateDependsTree(foundAtoms, deep = deep)
    treelength = len(treeview[0])
    if treelength > 1:
	treeview = treeview[0]
	for x in range(treelength)[::-1]:
	    for y in treeview[x]:
		choosenRemovalQueue.append(y)
	
    if (choosenRemovalQueue):
	if (not quiet):
	    print_info(red(" @@ ")+blue("These are the packages that would added to the removal queue:"))
	totalatoms = str(len(choosenRemovalQueue))
	atomscounter = 0
	
	for idpackage in choosenRemovalQueue:
	    atomscounter += 1
	    rematom = clientDbconn.retrieveAtom(idpackage)
	    if (not quiet):
	        installedfrom = clientDbconn.retrievePackageFromInstalledTable(idpackage)
	        repositoryInfo = bold("[")+red("from: ")+brown(installedfrom)+bold("]")
	        stratomscounter = str(atomscounter)
	        while len(stratomscounter) < len(totalatoms):
		    stratomscounter = " "+stratomscounter
	        print_info("   # "+red("(")+bold(stratomscounter)+"/"+blue(str(totalatoms))+red(")")+repositoryInfo+" "+blue(rematom))
	    else:
		print rematom


    if (idreturn):
	return treeview
    
    return 0



def searchInstalled(idreturn = False, verbose = False, quiet = False):
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Installed Search..."))

    clientDbconn = openClientDatabase()
    installedPackages = clientDbconn.listAllPackages()
    installedPackages.sort()
    if (not idreturn):
        if (not quiet):
	    print_info(red(" @@ ")+blue("These are the installed packages:"))
        for package in installedPackages:
	    if (not verbose):
	        atom = dep_getkey(package[0])
	    else:
	        atom = package[0]
	    branchinfo = ""
	    if (verbose):
	        branchinfo = darkgreen(" [")+red(package[2])+darkgreen("]")
	    if (not quiet):
	        print_info(red("  #")+blue(str(package[1]))+branchinfo+" "+atom)
	    else:
	        print atom
	clientDbconn.closeDB()
	return 0
    else:
	idpackages = set()
	for x in installedPackages:
	    idpackages.add(package[1])
        clientDbconn.closeDB()
        return list(idpackages)


def searchPackage(packages, idreturn = False):
    
    foundPackages = {}
    dataInfo = set() # when idreturn is True
    
    if (not idreturn):
        print_info(yellow(" @@ ")+darkgreen("Searching..."))
    # search inside each available database
    repoNumber = 0
    searchError = False
    for repo in etpRepositories:
	foundPackages[repo] = {}
	repoNumber += 1
	
	if (not idreturn):
	    print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
	
	dbconn = openRepositoryDatabase(repo)
	for package in packages:
	    slot = dep_getslot(package)
	    tag = dep_gettag(package)
	    package = remove_slot(package)
	    package = remove_tag(package)
	    result = dbconn.searchPackages(package, slot = slot, tag = tag)
	    
	    if (not result): # look for provide
		result = dbconn.searchProvide(package, slot = slot, tag = tag)
	    
	    if (result):
		foundPackages[repo][package] = result
	        # print info
	        for pkg in foundPackages[repo][package]:
		    idpackage = pkg[1]
		    atom = pkg[0]
		    branch = dbconn.retrieveBranch(idpackage)
		    if (idreturn):
			dataInfo.add((idpackage,repo))
		    else:
		        printPackageInfo(idpackage,dbconn)
		if (not idreturn):
	            print_info(blue(" Keyword: ")+bold("\t"+package))
	            print_info(blue(" Found:   ")+bold("\t"+str(len(foundPackages[repo][package])))+red(" entries"))
	
	dbconn.closeDB()

    if (idreturn):
	return dataInfo

    return 0

def searchTaggedPackages(tags, datareturn = False, quiet = False):
    
    foundPackages = {}
    
    if (not datareturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Tag Search..."))
    # search inside each available database
    repoNumber = 0
    for repo in etpRepositories:
	foundPackages[repo] = {}
	repoNumber += 1
	
	if (not datareturn) and (not quiet):
	    print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
	
	dbconn = openRepositoryDatabase(repo)
	for tag in tags:
	    results = dbconn.searchTaggedPackages(tag, atoms = True)
	    for result in results:
		foundPackages[repo][result[1]] = result[0]
	        # print info
		if (not datareturn):
		    printPackageInfo(result[1],dbconn, quiet = quiet)
	    if (not datareturn) and (not quiet):
	        print_info(blue(" Keyword: ")+bold("\t"+tag))
	        print_info(blue(" Found:   ")+bold("\t"+str(len(results)))+red(" entries"))
	
	dbconn.closeDB()

    if (datareturn):
	return foundPackages

    return 0

def searchDescription(descriptions, idreturn = False, quiet = False):
    
    foundPackages = {}
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Description Search..."))
    # search inside each available database
    repoNumber = 0
    for repo in etpRepositories:
	foundPackages[repo] = {}
	repoNumber += 1
	
	if (not idreturn) and (not quiet):
	    print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
	
	dbconn = openRepositoryDatabase(repo)
	dataInfo = [] # when idreturn is True
	for desc in descriptions:
	    result = dbconn.searchPackagesByDescription(desc)
	    if (result):
		foundPackages[repo][desc] = result
	        for pkg in foundPackages[repo][desc]:
		    idpackage = pkg[1]
		    atom = pkg[0]
		    if (idreturn):
			dataInfo.append([idpackage,repo])
		    elif (quiet):
			print dbconn.retrieveAtom(idpackage)
		    else:
		        printPackageInfo(idpackage,dbconn)
	        # print info
		if (not idreturn) and (not quiet):
	            print_info(blue(" Keyword: ")+bold("\t"+desc))
	            print_info(blue(" Found:   ")+bold("\t"+str(len(foundPackages[repo][desc])))+red(" entries"))
	
	dbconn.closeDB()

    if (idreturn):
	return dataInfo

    return 0



'''
   Internal functions
'''

def printPackageInfo(idpackage, dbconn, clientSearch = False, strictOutput = False, quiet = False, extended = False):
    # now fetch essential info
    pkgatom = dbconn.retrieveAtom(idpackage)
    if (quiet):
	print pkgatom
	return
    
    if (not strictOutput):
        pkgname = dbconn.retrieveName(idpackage)
        pkgcat = dbconn.retrieveCategory(idpackage)
        pkglic = dbconn.retrieveLicense(idpackage)
        pkgsize = dbconn.retrieveSize(idpackage)
        pkgbin = dbconn.retrieveDownloadURL(idpackage)
        pkgflags = dbconn.retrieveCompileFlags(idpackage)
        pkgkeywords = dbconn.retrieveBinKeywords(idpackage)
        pkgdigest = dbconn.retrieveDigest(idpackage)
        pkgcreatedate = convertUnixTimeToHumanTime(float(dbconn.retrieveDateCreation(idpackage)))
        pkgsize = bytesIntoHuman(pkgsize)
	pkgdeps = dbconn.retrieveDependencies(idpackage)
	pkgconflicts = dbconn.retrieveConflicts(idpackage)

    pkghome = dbconn.retrieveHomepage(idpackage)
    pkgslot = dbconn.retrieveSlot(idpackage)
    pkgver = dbconn.retrieveVersion(idpackage)
    pkgtag = dbconn.retrieveVersionTag(idpackage)
    pkgrev = dbconn.retrieveRevision(idpackage)
    pkgdesc = dbconn.retrieveDescription(idpackage)
    pkgbranch = dbconn.retrieveBranch(idpackage)
    if (not pkgtag):
        pkgtag = "NoTag"

    if (not clientSearch):
        # client info
        installedVer = "Not installed"
        installedTag = "N/A"
        installedRev = "N/A"
        clientDbconn = openClientDatabase()
        if (clientDbconn != -1):
            pkginstalled = clientDbconn.atomMatch(dep_getkey(pkgatom), matchSlot = pkgslot)
            if (pkginstalled[1] == 0):
		idx = pkginstalled[0]
	        # found
		installedVer = clientDbconn.retrieveVersion(idx)
		installedTag = clientDbconn.retrieveVersionTag(idx)
		if not installedTag:
		    installedTag = "NoTag"
		installedRev = clientDbconn.retrieveRevision(idx)
	    clientDbconn.closeDB()


    print_info(red("     @@ Package: ")+bold(pkgatom)+"\t\t"+blue("branch: ")+bold(pkgbranch))
    if (not strictOutput):
        print_info(darkgreen("       Category:\t\t")+blue(pkgcat))
        print_info(darkgreen("       Name:\t\t\t")+blue(pkgname))
    print_info(darkgreen("       Available:\t\t")+blue("version: ")+bold(pkgver)+blue(" ~ tag: ")+bold(pkgtag)+blue(" ~ revision: ")+bold(str(pkgrev)))
    if (not clientSearch):
        print_info(darkgreen("       Installed:\t\t")+blue("version: ")+bold(installedVer)+blue(" ~ tag: ")+bold(installedTag)+blue(" ~ revision: ")+bold(str(installedRev)))
    if (not strictOutput):
        print_info(darkgreen("       Slot:\t\t\t")+blue(str(pkgslot)))
        print_info(darkgreen("       Size:\t\t\t")+blue(str(pkgsize)))
        print_info(darkgreen("       Download:\t\t")+brown(str(pkgbin)))
        print_info(darkgreen("       Checksum:\t\t")+brown(str(pkgdigest)))
	if (pkgdeps):
	    print_info(darkred("       ##")+darkgreen(" Dependencies:"))
	    for pdep in pkgdeps:
		print_info(darkred("       ## \t\t\t")+brown(pdep))
	if (pkgconflicts):
	    print_info(darkred("       ##")+darkgreen(" Conflicts:"))
	    for conflict in pkgconflicts:
		print_info(darkred("       ## \t\t\t")+brown(conflict))
    print_info(darkgreen("       Homepage:\t\t")+red(pkghome))
    print_info(darkgreen("       Description:\t\t")+pkgdesc)
    if (not strictOutput):
	if (extended):
	    print_info(darkgreen("       CHOST:\t\t")+blue(pkgflags[0]))
	    print_info(darkgreen("       CFLAGS:\t\t")+red(pkgflags[1]))
	    print_info(darkgreen("       CXXFLAGS:\t\t")+blue(pkgflags[2]))
	    skeys = dbconn.retrieveKeywords(idpackage)
	    bkeys = dbconn.retrieveBinKeywords(idpackage)
	    sources = dbconn.retrieveSources(idpackage)
	    etpapi = dbconn.retrieveApi(idpackage)
	    print_info(darkgreen("       Source keywords:\t")+red(' '.join(skeys)))
	    print_info(darkgreen("       Binary keywords:\t")+blue(' '.join(bkeys)))
	    if (sources):
		print_info(darkgreen("       Sources:"))
		for source in sources:
		    print_info(darkred("         # Source: ")+blue(source))
	    print_info(darkgreen("       Entry API:\t\t")+red(str(etpapi)))
	else:
	    print_info(darkgreen("       Compiled with:\t")+blue(pkgflags[1]))
        print_info(darkgreen("       Architectures:\t")+blue(' '.join(pkgkeywords)))
        print_info(darkgreen("       Created:\t\t")+pkgcreatedate)
        print_info(darkgreen("       License:\t\t")+red(pkglic))