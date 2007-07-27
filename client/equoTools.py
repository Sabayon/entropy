#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equilibrium Library used by Python frontends

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

# RETURN STATUSES: 0-255
# NEVER USE SYS.EXIT !

import sys
import os
import re
sys.path.append('../libraries')
from entropyConstants import *
from outputTools import *
from remoteTools import downloadData
from entropyTools import unpackGzip, compareMd5, bytesIntoHuman, convertUnixTimeToHumanTime, askquestion, getRandomNumber, dep_getcpv, isjustname, dep_getkey, compareVersions, catpkgsplit

# Logging initialization
import logTools
equoLog = logTools.LogFile(level = etpConst['equologlevel'],filename = etpConst['equologfile'], header = "[Equo]")

########################################################
####
##   Repositories Tools
#

def repositories(options):
    
    # Options available for all the packages submodules
    myopts = options[1:]
    equoRequestAsk = False
    equoRequestPretend = False
    equoRequestPackagesCheck = False
    rc = 0
    for opt in myopts:
	if (opt == "--ask"):
	    equoRequestAsk = True
	elif (opt == "--pretend"):
	    equoRequestPretend = True

    if (options[0] == "sync"):
	rc = syncRepositories()

    if (options[0] == "status"):
	for repo in etpRepositories:
	    showRepositoryInfo(repo)

    if (options[0] == "show"):
	showRepositories()
    return rc

# this function shows a list of enabled repositories
def showRepositories():
    print_info(yellow(" * ")+green("Active Repositories:"))
    repoNumber = 0
    for repo in etpRepositories:
	repoNumber += 1
	print_info(blue("\t#"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
	print_info(red("\t\tPackages URL: ")+green(etpRepositories[repo]['packages']))
	print_info(red("\t\tDatabase URL: ")+green(etpRepositories[repo]['database']))
	print_info(red("\t\tRepository name: ")+bold(repo))
	print_info(red("\t\tRepository database path: ")+blue(etpRepositories[repo]['dbpath']))
    return 0

def showRepositoryInfo(reponame):
    repoNumber = 0
    for repo in etpRepositories:
	repoNumber += 1
	if repo == reponame:
	    break
    print_info(blue("#"+str(repoNumber))+bold(" "+etpRepositories[reponame]['description']))
    if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasefile']):
	status = "active"
    else:
	status = "never synced"
    print_info(red("\tStatus: ")+yellow(status))
    print_info(red("\tPackages URL: ")+green(etpRepositories[reponame]['packages']))
    print_info(red("\tDatabase URL: ")+green(etpRepositories[reponame]['database']))
    print_info(red("\tRepository name: ")+bold(reponame))
    print_info(red("\tRepository database path: ")+blue(etpRepositories[reponame]['dbpath']))
    revision = getRepositoryRevision(reponame)
    mhash = getRepositoryDbFileHash(reponame)

    print_info(red("\tRepository database checksum: ")+mhash)
    print_info(red("\tRepository revision: ")+green(str(revision)))
    return 0

# @returns -1 if the file does not exist
# @returns int>0 if the file exists
def getRepositoryRevision(reponame):
    if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabaserevisionfile']):
	f = open(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'],"r")
	revision = int(f.readline().strip())
	f.close()
    else:
	revision = -1
    return revision

# @returns -1 if the file does not exist
# @returns int>0 if the file exists
def getRepositoryDbFileHash(reponame):
    if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasehashfile']):
	f = open(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
	mhash = f.readline().strip().split()[0]
	f.close()
    else:
	mhash = "-1"
    return mhash

def syncRepositories(reponames = []):
    # check etpRepositories
    if len(etpRepositories) == 0:
	print_error(yellow(" * ")+red("No repositories specified in ")+etpConst['repositoriesconf'])
	return 127
    print_info(yellow(" @@ ")+green("Repositories syncronization..."))
    repoNumber = 0
    syncErrors = False
    
    if (reponames == []):
	for x in etpRepositories:
	    reponames.append(x)
    
    for repo in reponames:
	
	repoNumber += 1
	
	print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
	print_info(red("\tDatabase URL: ")+green(etpRepositories[repo]['database']))
	print_info(red("\tDatabase local path: ")+green(etpRepositories[repo]['dbpath']))
	
	# get database lock
	rc = downloadData(etpRepositories[repo]['database']+"/"+etpConst['etpdatabasedownloadlockfile'],"/dev/null")
	if rc != "-3": # cannot download database
	    print_error(bold("\tATTENTION -> ")+red("repository is being updated. Try again in few minutes."))
	    syncErrors = True
	    continue
	
	# starting to download
	print_info(red("\tDownloading database ")+green(etpConst['etpdatabasefilegzip'])+red(" ..."))
	# create dir if it doesn't exist
	if not os.path.isdir(etpRepositories[repo]['dbpath']):
	    print_info(red("\t\tCreating database directory..."))
	    os.makedirs(etpRepositories[repo]['dbpath'])
	# download
	downloadData(etpRepositories[repo]['database']+"/"+etpConst['etpdatabasefilegzip'],etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefilegzip'])
	
	print_info(red("\tUnpacking database to ")+green(etpConst['etpdatabasefile'])+red(" ..."))
	unpackGzip(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefilegzip'])
	# download etpdatabasehashfile
	print_info(red("\tDownloading checksum ")+green(etpConst['etpdatabasehashfile'])+red(" ..."))
	downloadData(etpRepositories[repo]['database']+"/"+etpConst['etpdatabasehashfile'],etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'])
	# checking checksum
	print_info(red("\tChecking downloaded database ")+green(etpConst['etpdatabasefile'])+red(" ..."), back = True)
	f = open(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
	md5hash = f.readline().strip()
	md5hash = md5hash.split()[0]
	f.close()
	rc = compareMd5(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefile'],md5hash)
	if rc:
	    print_info(red("\tDownloaded database status: ")+bold("OK"))
	else:
	    print_error(red("\tDownloaded database status: ")+yellow("ERROR"))
	    print_error(red("\t An error occured while checking database integrity"))
	    # delete all
	    if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile']):
		os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'])
	    if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefilegzip']):
		os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefilegzip'])
	    if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile']):
		os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'])
	    syncErrors = True
	    continue
	
	# download etpdatabaserevisionfile
	print_info(red("\tDownloading revision ")+green(etpConst['etpdatabaserevisionfile'])+red(" ..."))
	downloadData(etpRepositories[repo]['database']+"/"+etpConst['etpdatabaserevisionfile'],etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'])
	
	print_info(red("\tUpdated repository revision: ")+bold(str(getRepositoryRevision(repo))))
	print_info(yellow("\tUpdate completed"))

    if syncErrors:
	print_warning(yellow(" @@ ")+red("Something bad happened. Please have a look."))
	return 128

    return 0

def backupClientDatabase():
    if os.path.isfile(etpConst['etpdatabaseclientfilepath']):
	import shutil
	rnd = getRandomNumber()
	source = etpConst['etpdatabaseclientfilepath']
	dest = etpConst['etpdatabaseclientfilepath']+".backup."+str(rnd)
	shutil.copy2(source,dest)
	user = os.stat(source)[4]
	group = os.stat(source)[5]
	os.chown(dest,user,group)
	shutil.copystat(source,dest)
	return dest
    return ""

########################################################
####
##   Dependency handling functions
#

'''
   @description: matches the user chosen package name+ver, if possibile
   @input atom: string
   @input dbconn: database connection
   @output: the package id, if found, otherwise -1 plus the status, 0 = ok, 1 = not found, 2 = need more info, 3 = cannot use direction without specifying version
'''
def atomMatch(atom,dbconn):
    
    # check for direction
    strippedAtom = dep_getcpv(atom)
    direction = atom[0:len(atom)-len(strippedAtom)]

    #print strippedAtom
    #print isjustname(strippedAtom)
    justname = isjustname(strippedAtom)
    pkgversion = ''
    if (not justname):
	# strip tag
        if strippedAtom.split("-")[len(strippedAtom.split("-"))-1].startswith("t"):
            strippedAtom = string.join(strippedAtom.split("-t")[:len(strippedAtom.split("-t"))-1],"-t")
	# get version
	data = catpkgsplit(strippedAtom)
	pkgversion = data[2]+"-"+data[3]

    pkgkey = dep_getkey(strippedAtom)
    if len(pkgkey.split("/")) == 2:
        pkgname = pkgkey.split("/")[1]
        pkgcat = pkgkey.split("/")[0]
    else:
        pkgname = pkgkey.split("/")[0]
	pkgcat = "null"

    #print dep_getkey(strippedAtom)
    
    myBranchIndex = etpConst['branches'].index(etpConst['branch'])
    
    # IDs found in the database that match our search
    foundIDs = []
    
    for idx in range(myBranchIndex+1)[::-1]: # reverse order
	print "Searching into -> "+etpConst['branches'][idx]
	# search into the less stable, if found, break, otherwise continue
	results = dbconn.searchPackagesInBranchByName(pkgname,etpConst['branches'][idx])
	
	# now validate
	if (not results):
	    print "results is empty"
	    continue # search into a stabler branch
	
	elif (len(results) > 1):
	
	    print "results > 1"
	
	    # if it's because category differs, it's a problem
	    foundCat = ""
	    for result in results:
		idpackage = result[1]
		cat = dbconn.retrieveCategory(idpackage)
		if (foundCat):
		    if (cat != foundCat) and (pkgcat == "null"):
			# got the issue
			# gosh, return and complain
			return -1,2
		else:
		    foundCat = cat
	
	    # I can use foundCat
	    pkgcat = foundCat
	
	    # we need to search using the category
	    results = dbconn.searchPackagesInBranchByNameAndCategory(pkgname,pkgcat,etpConst['branches'][idx])
	    # validate again
	    if (not results):
		continue  # search into a stabler branch
	
	    # if we get here, we have found the needed IDs
	    foundIDs = results
	    break

	else:
	    print "results == 1"
	    foundIDs.append(results[0])
	    break

    if (foundIDs):
	# now we have to handle direction
	if (direction):
	    # check if direction is used with justname, in this case, return an error
	    if (justname):
		return -1,3 # error, cannot use directions when not specifying version

	    if (direction == "~") or (direction == "="): # any revision within the version specified OR the specified version
		
		print direction+" direction"
		# remove revision (-r0 if none)
		if (direction == "~") or ((direction == "=") and (pkgversion.split("-")[len(pkgversion.split("-"))-1] == "r0")):
		    pkgversion = string.join(pkgversion.split("-")[:len(pkgversion.split("-"))-1],"-")
		dbpkginfo = []
		for list in foundIDs:
		    idpackage = list[1]
		    dbver = dbconn.retrieveVersion(idpackage)
		    if (direction == "~"):
		        if dbver.startswith(pkgversion):
			    # found
			    dbpkginfo.append([idpackage,dbver])
		    else:
		        if (dbver == pkgversion):
			    # found
			    dbpkginfo.append([idpackage,dbver])
		
		if (not dbpkginfo):
		    # no version available
		    return -1,1
		
		versions = []
		for x in dbpkginfo:
		    versions.append(x[1])
		# who is newer ?
		versionlist = getNewerVersion(versions)
		newerPackage = dbpkginfo[versions.index(versionlist[0])]
		
	        # now look if there's another package with the same category, name, version, but different tag
	        newerPkgName = dbconn.retrieveName(newerPackage[0])
	        newerPkgCategory = dbconn.retrieveCategory(newerPackage[0])
	        newerPkgVersion = dbconn.retrieveVersion(newerPackage[0])
		newerPkgBranch = dbconn.retrieveBranch(newerPackage[0])
	        similarPackages = dbconn.searchPackagesInBranchByNameAndVersionAndCategory(newerPkgName, newerPkgVersion, newerPkgCategory, newerPkgBranch)
		
		#print newerPackage
		#print similarPackages
	        if (len(similarPackages) > 1):
		    # gosh, there are packages with the same name, version, category
		    # we need to parse version tag
		    versionTags = []
		    for pkg in similarPackages:
		        versionTags.append(dbconn.retrieveVersionTag(pkg[1]))
		    versiontaglist = getNewerVersionTag(versionTags)
		    newerPackage = similarPackages[versionTags.index(versiontaglist[0])]
		
		#print newerPackage
		print newerPackage[1]
		return newerPackage[0],0
	
	    elif (direction.find(">") != -1) or (direction.find("<") != -1): # any revision within the version specified
		
		print direction+" direction"
		# remove revision (-r0 if none)
		if pkgversion.split("-")[len(pkgversion.split("-"))-1] == "r0":
		    # remove
		    pkgversion = string.join(pkgversion.split("-")[:len(pkgversion.split("-"))-1],"-")

		dbpkginfo = []
		for list in foundIDs:
		    idpackage = list[1]
		    dbver = dbconn.retrieveVersion(idpackage)
		    cmp = compareVersions(pkgversion,dbver)
		    if direction == ">":
		        if (cmp < 0):
			    # found
			    dbpkginfo.append([idpackage,dbver])
		    elif direction == "<":
		        if (cmp > 0):
			    # found
			    dbpkginfo.append([idpackage,dbver])
		    elif direction == ">=":
		        if (cmp <= 0):
			    # found
			    dbpkginfo.append([idpackage,dbver])
		    elif direction == "<=":
		        if (cmp >= 0):
			    # found
			    dbpkginfo.append([idpackage,dbver])
		
		if (not dbpkginfo):
		    # this version is not available
		    return -1,1
		
		versions = []
		for x in dbpkginfo:
		    versions.append(x[1])
		# who is newer ?
		versionlist = getNewerVersion(versions)
		newerPackage = dbpkginfo[versions.index(versionlist[0])]
		
	        # now look if there's another package with the same category, name, version, but different tag
	        newerPkgName = dbconn.retrieveName(newerPackage[0])
	        newerPkgCategory = dbconn.retrieveCategory(newerPackage[0])
	        newerPkgVersion = dbconn.retrieveVersion(newerPackage[0])
		newerPkgBranch = dbconn.retrieveBranch(newerPackage[0])
	        similarPackages = dbconn.searchPackagesInBranchByNameAndVersionAndCategory(newerPkgName, newerPkgVersion, newerPkgCategory, newerPkgBranch)
		
		#print newerPackage
		#print similarPackages
	        if (len(similarPackages) > 1):
		    # gosh, there are packages with the same name, version, category
		    # we need to parse version tag
		    versionTags = []
		    for pkg in similarPackages:
		        versionTags.append(dbconn.retrieveVersionTag(pkg[1]))
		    versiontaglist = getNewerVersionTag(versionTags)
		    newerPackage = similarPackages[versionTags.index(versiontaglist[0])]
		
		#print newerPackage
		print newerPackage[1]
		return newerPackage[0],0

	    else:
		return -1,1
		
	else:
	    
	    # not set, just get the newer version
	    versionIDs = []
	    for list in foundIDs:
		versionIDs.append(dbconn.retrieveVersion(list[1]))
	    
	    versionlist = getNewerVersion(versionIDs)
	    newerPackage = foundIDs[versionIDs.index(versionlist[0])]
	    
	    # now look if there's another package with the same category, name, version, tag
	    newerPkgName = dbconn.retrieveName(newerPackage[1])
	    newerPkgCategory = dbconn.retrieveCategory(newerPackage[1])
	    newerPkgVersion = dbconn.retrieveVersion(newerPackage[1])
	    newerPkgBranch = dbconn.retrieveBranch(newerPackage[1])
	    similarPackages = dbconn.searchPackagesInBranchByNameAndVersionAndCategory(newerPkgName, newerPkgVersion, newerPkgCategory, newerPkgBranch)
	    
	    if (similarPackages):
		# gosh, there are packages with the same name, version, category
		# we need to parse version tag
		versionTags = []
		for pkg in similarPackages:
		    versionTags.append(dbconn.retrieveVersionTag(pkg[1]))
		versiontaglist = getNewerVersionTag(versionTags)
		newerPackage = similarPackages[versionTags.index(versiontaglist[0])]
	    
	    return newerPackage[1],0

    else:
	# package not found in any branch
	return -1,1


'''
   @description: reorder a version list
   @input versionlist: a list
   @output: the ordered list
   FIXME: using Bubble Sorting is not the fastest way
'''
def getNewerVersion(versionlist):
    rc = False
    while not rc:
	change = False
        for x in range(len(versionlist)):
	    pkgA = versionlist[x]
	    try:
	        pkgB = versionlist[x+1]
	    except:
	        pkgB = "0"
            result = compareVersions(pkgA,pkgB)
	    #print pkgA + "<->" +pkgB +" = " + str(result)
	    if result < 0:
	        # swap positions
	        versionlist[x] = pkgB
	        versionlist[x+1] = pkgA
		change = True
	if (not change):
	    rc = True
    return versionlist

'''
   @description: reorder a list of strings converted into ascii
   @input versionlist: a string list
   @output: the ordered string list
'''
def getNewerVersionTag(versionlist):
    rc = False
    while not rc:
	change = False
        for x in range(len(versionlist)):
	    pkgA = versionlist[x]
	    try:
	        pkgB = versionlist[x+1]
	    except:
	        pkgB = "0"
	    # translate pkgA into numeric string
	    if pkgA < pkgB:
	        # swap positions
	        versionlist[x] = pkgB
	        versionlist[x+1] = pkgA
		change = True
	if (not change):
	    rc = True
    return versionlist

########################################################
####
##   Database Tools
#

def package(options):

    if len(options) < 2:
	return 0

    # Options available for all the packages submodules
    myopts = options[1:]
    equoRequestAsk = False
    equoRequestPretend = False
    equoRequestPackagesCheck = False
    rc = 0
    _myopts = []
    for opt in myopts:
	if (opt == "--ask"):
	    equoRequestAsk = True
	elif (opt == "--pretend"):
	    equoRequestPretend = True
	else:
	    _myopts.append(opt)
    myopts = _myopts

    if (options[0] == "search"):
	if len(myopts) > 0:
	    rc = searchPackage(myopts)

    if (options[0] == "install"):
	if len(myopts) > 0:
	    rc,status = installPackages(myopts)

    return rc


def database(options):

    if len(options) < 1:
	return 0

    if (options[0] == "generate"):
	
	print_warning(bold("####### ATTENTION -> ")+red("The installed package database will be regenerated, this will take a LOT of time."))
	print_warning(bold("####### ATTENTION -> ")+red("Sabayon Linux Officially Repository MUST be on top of the repositories list in ")+etpConst['repositoriesconf'])
	print_warning(bold("####### ATTENTION -> ")+red("This method is only used for testing at the moment."))
	rc = askquestion("     Can I continue ?")
	if rc == "No":
	    sys.exit(0)
	rc = askquestion("     Are you REALLY sure ?")
	if rc == "No":
	    sys.exit(0)
	rc = askquestion("     Do you even know what you're doing ?")
	if rc == "No":
	    sys.exit(0)
	
	# ok, he/she knows it... hopefully
	# if exist, copy old database
	print_info(red(" @@ ")+blue("Creating backup of the previous database, if exists.")+red(" @@"))
	newfile = backupClientDatabase()
	if (newfile):
	    print_info(red(" @@ ")+blue("Previous database copied to file ")+newfile+red(" @@"))
	
	# Now reinitialize it
	from databaseTools import etpDatabase
	print_info(darkred("  Initializing the new database at "+bold(etpConst['etpdatabaseclientfilepath'])), back = True)
	clientDbconn = etpDatabase(readOnly = False, noUpload = True, dbFile = etpConst['etpdatabaseclientfilepath'], clientDatabase = True)
	clientDbconn.initializeDatabase()
	print_info(darkgreen("  Database reinitialized correctly at "+bold(etpConst['etpdatabaseclientfilepath'])))
	
	# now collect files in the system
	tmpfile = etpConst['packagestmpfile']+".diskanalyze"
	print_info(red("  Collecting installed files... Saving into ")+bold(tmpfile))
	
	'''
	f = open(tmpfile,"w")
	for dir in etpConst['filesystemdirs']:
	    if os.path.isdir(dir):
		for dir,subdirs,files in os.walk(dir):
		    print_info(darkgreen("  Analyzing directory "+bold(dir[:50]+"...")),back = True)
		    for file in files:
			file = dir+"/"+file
			f.write(file+"\n")
	
	f.flush()
	f.close()
	'''
	
	tmpfile = "/var/lib/entropy/tmp/.random-12859.tmp.diskanalyze"
	
	f = open(tmpfile,"r")
	systemFiles = []
	for x in f.readlines():
	    systemFiles.append(x.strip())
	f.close()
	
	orphanedFiles = []
	foundPackages = []
	
	print_info(red("  Now analyzing database content..."))
	# do for each database
	repocount = 0
	for repo in etpRepositories:
	
	    repocount += 1
	
	    print_info("("+blue(str(repocount))+"/"+darkblue(str(len(etpRepositories)))+") "+red("  Analyzing ")+bold(etpRepositories[repo]['description'])+"...", back = True)
	
	    # syncing if needed
	    dbfile = etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefile']
	    if not os.path.isfile(dbfile):
		# sync...
		syncRepositories([repo])
	    if not os.path.isfile(dbfile):
		print_error(red("Cannot find repository database")+bold(dbfile))
		return 129
	    
	    if (not orphanedFiles): # first cycle
	    
	        # open database
	        dbRepo = etpDatabase(readOnly = True, noUpload = True, dbFile = dbfile)
	    
	        # FIXME: add branch support
	        # search into database
	        for file in systemFiles:
		    pkgids = dbRepo.getIDPackageFromFile(file)
		    if (pkgids):
		        for pkg in pkgids:
		            foundPackages.append([repo,pkg])
		    else:
		        orphanedFiles.append(file)
	        dbRepo.closeDB()
	    
	    else:
		
		dbRepo = etpDatabase(readOnly = True, noUpload = True, dbFile = dbfile)
		_orphanedFiles = orphanedFiles
		orphanedFiles = []
		
	        for file in _orphanedFiles:
		    pkgids = dbRepo.getIDPackageFromFile(file)
		    if (pkgids):
		        for pkg in pkgids:
		            foundPackages.append([repo,pkg])
		    else:
		        orphanedFiles.append(file)
		
		dbRepo.closeDB()
		
	
	print_info(red("  ### Orphaned files:")+bold(str(len(orphanedFiles))))
	foundPackages = list(set(foundPackages))
	print_info(red("  ### Packages matching:")+bold(str(len(foundPackages))))
	
	#if os.path.isfile(tmpfile):
	#    os.remove(tmpfile)
	
	
	
	clientDbconn.closeDB()


def searchPackage(packages):
    from databaseTools import etpDatabase
    
    foundPackages = {}
    
    print_info(yellow(" @@ ")+darkgreen("Searching..."))
    # search inside each available database
    repoNumber = 0
    searchError = False
    for repo in etpRepositories:
	foundPackages[repo] = {}
	repoNumber += 1
	print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
	
	# open database
	dbfile = etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefile']
	if not os.path.isfile(dbfile):
	    # sync
	    syncRepositories([repo])
	if not os.path.isfile(dbfile):
	    # so quit
	    print_error(red("Database file for '"+bold(etpRepositories[repo]['description'])+red("' does not exist. Cannot search.")))
	    searchError = True
	    continue
	    
	dbconn = etpDatabase(readOnly = True, dbFile = dbfile)
	for package in packages:
	    result = dbconn.searchPackages(package)
	    
	    if (result):
		foundPackages[repo][package] = result
	        # print info
	        print_info(blue("     Keyword: ")+bold("\t"+package))
	        print_info(blue("     Found:   ")+bold("\t"+str(len(foundPackages[repo][package])))+red(" entries"))
	        for pkg in foundPackages[repo][package]:
		    id = pkg[1]
		    atom = pkg[0]
		    branch = dbconn.retrieveBranch(id)
		    # does the package exist in the selected branch?
		    if etpConst['branch'] != branch:
			# get branch name position in branches
			myBranchIndex = etpConst['branches'].index(etpConst['branch'])
			foundBranchIndex = etpConst['branches'].index(branch)
			if foundBranchIndex > myBranchIndex:
			    # package found in branch more unstable than the selected one, for us, it does not exist
			    continue
		
		    # now fetch essential info
		    pkgatom = dbconn.retrieveAtom(id)
		    pkgname = dbconn.retrieveName(id)
		    pkgcat = dbconn.retrieveCategory(id)
		    pkgver = dbconn.retrieveVersion(id)
		    pkgdesc = dbconn.retrieveDescription(id)
		    pkghome = dbconn.retrieveHomepage(id)
		    pkglic = dbconn.retrieveLicense(id)
		    pkgsize = dbconn.retrieveSize(id)
		    pkgbin = dbconn.retrieveDownloadURL(id)
		    pkgflags = dbconn.retrieveCompileFlags(id)
		    pkgkeywords = dbconn.retrieveBinKeywords(id)
		    pkgtag = dbconn.retrieveVersionTag(id)
		    pkgdigest = dbconn.retrieveDigest(id)
		    pkgcreatedate = convertUnixTimeToHumanTime(int(dbconn.retrieveDateCreation(id)))
		    if (not pkgtag):
			pkgtag = "Not tagged"
		    pkgsize = bytesIntoHuman(pkgsize)
		    
		    print_info(red("     @@ Package: ")+bold(pkgatom)+"\t\t"+blue("branch: ")+bold(branch))
		    print_info(darkgreen("       Category:\t\t")+darkblue(pkgcat))
		    print_info(darkgreen("       Name:\t\t\t")+darkblue(pkgname))
		    print_info(darkgreen("       Available version:\t")+blue(pkgver))
		    print_info(darkgreen("       Installed version:\t")+blue("N/A"))
		    print_info(darkgreen("       Available version tag:\t\t\t")+blue(pkgtag))
		    print_info(darkgreen("       Size:\t\t\t")+blue(str(pkgsize)))
		    print_info(darkgreen("       Download:\t\t")+brown(str(pkgbin)))
		    print_info(darkgreen("       Checksum:\t\t")+brown(str(pkgdigest)))
		    print_info(darkgreen("       Homepage:\t\t")+red(pkghome))
		    print_info(darkgreen("       Description:\t\t")+pkgdesc)
		    print_info(darkgreen("       Compiled with:\t")+blue(pkgflags[1]))
		    print_info(darkgreen("       Architectures:\t")+blue(string.join(pkgkeywords," ")))
		    print_info(darkgreen("       Created:\t\t")+pkgcreatedate)
		    print_info(darkgreen("       License:\t\t")+red(pkglic))
	
	dbconn.closeDB()

    #print foundPackages
    # choose the defaulted version

    if searchError:
	print_warning(yellow(" @@ ")+red("Something bad happened. Please have a look."))
	return 129
    return 0


########################################################
####
##   Actions Handling
#

# FIXME: must handle multiple results from multiple repositories
def installPackages(packages):
    print packages
    print "not working yet, but atom handling has been implemented"
    return "asd","asd"