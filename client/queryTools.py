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

import sys
import os
sys.path.append('../libraries')
from entropyConstants import *
from clientConstants import *
from outputTools import *
from databaseTools import etpDatabase
from entropyTools import dep_getkey
from equoTools import openClientDatabase, closeClientDatabase, openRepositoryDatabase, printPackageInfo, generateDependsTree # move them away?

########################################################
####
##   Query Tools
#

def query(options):

    rc = 0

    if len(options) < 1:
	return rc

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

    if options[0] == "installed":
	rc = searchInstalledPackages(myopts[1:], quiet = equoRequestQuiet)

    elif options[0] == "belongs":
	rc = searchBelongs(myopts[1:], quiet = equoRequestQuiet)

    elif options[0] == "depends":
	rc = searchDepends(myopts[1:], verbose = equoRequestVerbose, quiet = equoRequestQuiet)

    elif options[0] == "files":
	rc = searchFiles(myopts[1:], quiet = equoRequestQuiet)

    elif options[0] == "removal":
	rc = searchRemoval(myopts[1:], quiet = equoRequestQuiet, deep = equoRequestDeep)

    elif options[0] == "orphans":
	rc = searchOrphans(quiet = equoRequestQuiet)

    elif options[0] == "list":
	mylistopts = options[1:]
	if len(mylistopts) > 0:
	    if mylistopts[0] == "installed":
	        rc = searchInstalled(verbose = equoRequestVerbose, quiet = equoRequestQuiet)
	    # add more here

    elif options[0] == "description":
	rc = searchDescription(myopts[1:], quiet = equoRequestQuiet)

    return rc



def searchInstalledPackages(packages, idreturn = False, quiet = False):
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Searching..."))

    clientDbconn = openClientDatabase()
    dataInfo = [] # when idreturn is True
    
    for package in packages:
	result = clientDbconn.searchPackages(package)
	if (result):
	    # print info
	    if (not idreturn) and (not quiet):
	        print_info(blue("     Keyword: ")+bold("\t"+package))
	        print_info(blue("     Found:   ")+bold("\t"+str(len(result)))+red(" entries"))
	    for pkg in result:
		idpackage = pkg[1]
		atom = pkg[0]
		branch = clientDbconn.retrieveBranch(idpackage)
		if (idreturn):
		    dataInfo.append(idpackage)
		else:
		    printPackageInfo(idpackage, clientDbconn, clientSearch = True, quiet = quiet)
	
    closeClientDatabase(clientDbconn)

    if (idreturn):
	return dataInfo
    
    return 0


def searchBelongs(files, idreturn = False, quiet = False):
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Belong Search..."))

    clientDbconn = openClientDatabase()
    dataInfo = [] # when idreturn is True
    
    for file in files:
	like = False
	if file.find("*") != -1:
	    like = True
	    file = "%"+file+"%"
	result = clientDbconn.searchBelongs(file, like)
	if (result):
	    # print info
	    if (not idreturn) and (not quiet):
	        print_info(blue("     Keyword: ")+bold("\t"+file))
	        print_info(blue("     Found:   ")+bold("\t"+str(len(result)))+red(" entries"))
	    for idpackage in result:
		if (idreturn):
		    dataInfo.append(idpackage)
		elif (quiet):
		    print clientDbconn.retrieveAtom(idpackage)
		else:
		    printPackageInfo(idpackage, clientDbconn, clientSearch = True)
	
    closeClientDatabase(clientDbconn)

    if (idreturn):
	return dataInfo
    
    return 0



def searchDepends(atoms, idreturn = False, verbose = False, quiet = False):
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Depends Search..."))

    clientDbconn = openClientDatabase()

    dataInfo = [] # when idreturn is True
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
	    # print info
	    if (not idreturn) and (not quiet):
	        print_info(blue("     Keyword: ")+bold("\t"+atom))
		if (matchInRepo):
		    where = " from repository "+str(result[1])
		else:
		    where = " from installed packages database"
	        print_info(blue("     Found:   ")+bold("\t"+str(len(searchResults)))+red(" entries")+where)
	    for idpackage in searchResults:
		if (idreturn):
		    dataInfo.append(idpackage)
		else:
		    if (verbose):
		        printPackageInfo(idpackage, dbconn, clientSearch = True, quiet = quiet)
		    else:
		        printPackageInfo(idpackage, dbconn, clientSearch = True, strictOutput = True, quiet = quiet)
	else:
	    continue
	if (matchInRepo):
	    dbconn.closeDB()

    closeClientDatabase(clientDbconn)

    if (idreturn):
	return dataInfo
    
    return 0


def searchFiles(atoms, idreturn = False, quiet = False):
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Files Search..."))

    results = searchInstalledPackages(atoms, idreturn = True)
    clientDbconn = openClientDatabase()
    dataInfo = [] # when idreturn is True
    for result in results:
	if (result != -1):
	    files = clientDbconn.retrieveContent(result)
	    atom = clientDbconn.retrieveAtom(result)
	    # print info
	    if (not idreturn) and (not quiet):
	        print_info(blue("     Package: ")+bold("\t"+atom))
	        print_info(blue("     Found:   ")+bold("\t"+str(len(files)))+red(" files"))
	    if (idreturn):
		dataInfo.append([result,files])
	    else:
		if quiet:
		    for file in files:
			print file
		else:
		    for file in files:
		        print_info(blue(" ### ")+red(str(file)))
	
    closeClientDatabase(clientDbconn)

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
	print_info(red(" @@ ")+blue("Analyzed directories: ")+string.join(etpConst['filesystemdirs']," "))
	print_info(red(" @@ ")+blue("Masked directories: ")+string.join(etpConst['filesystemdirsmask']," "))
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
    treeview = generateDependsTree(foundAtoms,clientDbconn, deep = deep)
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
	closeClientDatabase(clientDbconn)
	return 0
    else:
	idpackages = set()
	for x in installedPackages:
	    idpackages.add(package[1])
        closeClientDatabase(clientDbconn)
        return list(idpackages)


def searchPackage(packages, idreturn = False):
    
    foundPackages = {}
    
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
	dataInfo = [] # when idreturn is True
	for package in packages:
	    result = dbconn.searchPackages(package)
	    
	    if (not result): # look for provide
		provide = dbconn.searchProvide(package)
		if (provide):
		    result = [[provide[0],provide[1]]]
		
	    
	    if (result):
		foundPackages[repo][package] = result
	        # print info
		if (not idreturn):
	            print_info(blue("     Keyword: ")+bold("\t"+package))
	            print_info(blue("     Found:   ")+bold("\t"+str(len(foundPackages[repo][package])))+red(" entries"))
	        for pkg in foundPackages[repo][package]:
		    idpackage = pkg[1]
		    atom = pkg[0]
		    branch = dbconn.retrieveBranch(idpackage)
		    # does the package exist in the selected branch?
		    if etpConst['branch'] != branch:
			# get branch name position in branches
			myBranchIndex = etpConst['branches'].index(etpConst['branch'])
			foundBranchIndex = etpConst['branches'].index(branch)
			if foundBranchIndex > myBranchIndex:
			    # package found in branch more unstable than the selected one, for us, it does not exist
			    continue
		    if (idreturn):
			dataInfo.append([idpackage,repo])
		    else:
		        printPackageInfo(idpackage,dbconn)
	
	dbconn.closeDB()

    if (idreturn):
	return dataInfo

    if searchError:
	print_warning(yellow(" @@ ")+red("Something bad happened. Please have a look."))
	return 129
    return 0



def searchDescription(descriptions, idreturn = False, quiet = False):
    
    foundPackages = {}
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Description Search..."))
    # search inside each available database
    repoNumber = 0
    searchError = False
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
	        # print info
		if (not idreturn) and (not quiet):
	            print_info(blue("     Keyword: ")+bold("\t"+desc))
	            print_info(blue("     Found:   ")+bold("\t"+str(len(foundPackages[repo][desc])))+red(" entries"))
	        for pkg in foundPackages[repo][desc]:
		    idpackage = pkg[1]
		    atom = pkg[0]
		    if (idreturn):
			dataInfo.append([idpackage,repo])
		    elif (quiet):
			print dbconn.retrieveAtom(idpackage)
		    else:
		        printPackageInfo(idpackage,dbconn)
	
	dbconn.closeDB()

    if (idreturn):
	return dataInfo

    if searchError:
	print_warning(yellow(" @@ ")+red("Something bad happened. Please have a look."))
	return 129
    return 0