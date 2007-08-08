#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo Library used by Python frontends

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
from clientConstants import *
from outputTools import *
from remoteTools import downloadData, getOnlineContent
from entropyTools import unpackGzip, compareMd5, bytesIntoHuman, convertUnixTimeToHumanTime, askquestion, getRandomNumber, dep_getcpv, isjustname, dep_getkey, compareVersions as entropyCompareVersions, catpkgsplit, filterDuplicatedEntries, extactDuplicatedEntries, isspecific, uncompressTarBz2, extractXpak, filterDuplicatedEntries
from databaseTools import etpDatabase
import xpak
import time

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
    equoRequestForceUpdate = False
    rc = 0
    for opt in myopts:
	if (opt == "--ask"):
	    equoRequestAsk = True
	elif (opt == "--pretend"):
	    equoRequestPretend = True
	elif (opt == "--force"):
	    equoRequestForceUpdate = True

    if (options[0] == "update"):
	rc = syncRepositories(forceUpdate = equoRequestForceUpdate)

    if (options[0] == "status"):
	for repo in etpRepositories:
	    showRepositoryInfo(repo)

    if (options[0] == "repoinfo"):
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

# @returns -1 if the file is not available
# @returns int>0 if the revision has been retrieved
def getOnlineRepositoryRevision(reponame):
    url = etpRepositories[reponame]['database']+"/"+etpConst['etpdatabaserevisionfile']
    status = getOnlineContent(url)
    if (status != False):
	status = status[0].strip()
	return int(status)
    else:
	return -1

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

def syncRepositories(reponames = [], forceUpdate = False):

    # check if I am root
    if (not checkRoot()):
	print_error(red("\t You must run this application as root."))
	return 1

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
	
	# check if database is already updated to the latest revision
	onlinestatus = getOnlineRepositoryRevision(repo)
	if (onlinestatus != -1):
	    localstatus = getRepositoryRevision(repo)
	    if (localstatus == onlinestatus) and (forceUpdate == False):
		print_info(bold("\tAttention: ")+red("database is already up to date."))
		continue
	
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

def fetchRepositoryIfNotAvailable(reponame):
    # open database
    rc = 0
    dbfile = etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasefile']
    if not os.path.isfile(dbfile):
	# sync
	rc = syncRepositories([reponame])
    if not os.path.isfile(dbfile):
	# so quit
	print_error(red("Database file for '"+bold(etpRepositories[reponame]['description'])+red("' does not exist. Cannot search.")))
    return rc

'''
   @description: check we're running this code as root
   @input atom: nothing
   @output: True for yes, False for no
'''
def checkRoot():
    import getpass
    if getpass.getuser() == "root":
	return True
    return False

########################################################
####
##   Dependency handling functions
#

'''
   @description: matches the user chosen package name+ver, if possibile, in a single repository
   @input atom: string
   @input dbconn: database connection
   @output: the package id, if found, otherwise -1 plus the status, 0 = ok, 1 = not found, 2 = need more info, 3 = cannot use direction without specifying version
'''
atomMatchInRepositoryCache = {}
def atomMatchInRepository(atom, dbconn, caseSensitive = True):
    
    cached = atomMatchInRepositoryCache.get(atom)
    if (cached):
	if (str(cached['dbconn']) == str(dbconn)):
	    return cached['result']
    
    # check for direction
    strippedAtom = dep_getcpv(atom)
    if atom.endswith("*"):
	strippedAtom += "*"
    direction = atom[0:len(atom)-len(strippedAtom)]
    #print direction

    #print strippedAtom
    #print isspecific(strippedAtom)
    #print direction
    
    justname = isjustname(strippedAtom)
    #print justname
    pkgversion = ''
    if (not justname):
	# strip tag
        if strippedAtom.split("-")[len(strippedAtom.split("-"))-1].startswith("t"):
            strippedAtom = string.join(strippedAtom.split("-t")[:len(strippedAtom.split("-t"))-1],"-t")
	# get version
	data = catpkgsplit(strippedAtom)
	pkgversion = data[2]+"-"+data[3]
	pkgtag = ''
	if atom.split("-")[len(atom.split("-"))-1].startswith("t"):
	    pkgtag = atom.split("-")[len(atom.split("-"))-1]
	    #print "TAG: "+pkgtag
	#print data
	#print pkgversion
	#print pkgtag
	

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
	#print "Searching into -> "+etpConst['branches'][idx]
	# search into the less stable, if found, break, otherwise continue
	results = dbconn.searchPackagesInBranchByName(pkgname, etpConst['branches'][idx], caseSensitive)
	
	#print results
	
	# if it's a PROVIDE, search with searchProvide
	if (not results):
	    results = dbconn.searchProvideInBranch(pkgkey,etpConst['branches'][idx])
	
	# now validate
	if (not results):
	    #print "results is empty"
	    continue # search into a stabler branch
	
	elif (len(results) > 1):
	
	    #print "results > 1"
	    # if it's because category differs, it's a problem
	    foundCat = ""
	    for result in results:
		idpackage = result[1]
		cat = dbconn.retrieveCategory(idpackage)
		if (foundCat):
		    if (cat != foundCat) and (pkgcat == "null"):
			# got the issue
			# gosh, return and complain
			atomMatchInRepositoryCache[atom] = {}
			atomMatchInRepositoryCache[atom]['dbconn'] = dbconn
			atomMatchInRepositoryCache[atom]['result'] = -1,2
			return -1,2
		else:
		    foundCat = cat
	
	    # I can use foundCat
	    pkgcat = foundCat
	    
	    # we need to search using the category
	    results = dbconn.searchPackagesInBranchByNameAndCategory(pkgname,pkgcat,etpConst['branches'][idx], caseSensitive)
	    # validate again
	    if (not results):
		continue  # search into a stabler branch
	
	    # if we get here, we have found the needed IDs
	    foundIDs = results
	    break

	else:
	    #print "results == 1"
	    foundIDs.append(results[0])
	    break

    if (foundIDs):
	# now we have to handle direction
	if (direction):
	    # check if direction is used with justname, in this case, return an error
	    if (justname):
		#print "justname"
		atomMatchInRepositoryCache[atom] = {}
		atomMatchInRepositoryCache[atom]['dbconn'] = dbconn
		atomMatchInRepositoryCache[atom]['result'] = -1,3
		return -1,3 # error, cannot use directions when not specifying version

	    if (direction == "~") or (direction == "="): # any revision within the version specified OR the specified version
		
		#print direction+" direction"
		# remove revision (-r0 if none)
		if (direction == "~") or ((direction == "=") and (pkgversion.split("-")[len(pkgversion.split("-"))-1] == "r0")):
		    pkgversion = string.join(pkgversion.split("-")[:len(pkgversion.split("-"))-1],"-")
		
		#print pkgversion
		dbpkginfo = []
		for list in foundIDs:
		    idpackage = list[1]
		    dbver = dbconn.retrieveVersion(idpackage)
		    if (direction == "~"):
		        if dbver.startswith(pkgversion):
			    # found
			    dbpkginfo.append([idpackage,dbver])
		    else:
			dbtag = dbconn.retrieveVersionTag(idpackage)
			#print pkgversion
			# media-libs/test-1.2* support
			if pkgversion.endswith("*"):
			    testpkgver = pkgversion[:len(pkgversion)-1]
			    combodb = dbtag+dbver
			    combopkg = pkgtag+testpkgver
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
			    dbver = dbconn.retrieveVersion(idpackage)
			    dbpkginfo.append([idpackage,dbver])
		
		if (not dbpkginfo):
		    atomMatchInRepositoryCache[atom] = {}
		    atomMatchInRepositoryCache[atom]['dbconn'] = dbconn
		    atomMatchInRepositoryCache[atom]['result'] = -1,1
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
	        similarPackages = dbconn.searchPackagesInBranchByNameAndVersionAndCategory(newerPkgName, newerPkgVersion, newerPkgCategory, newerPkgBranch, caseSensitive)
		
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
		#print newerPackage[1]
		atomMatchInRepositoryCache[atom] = {}
		atomMatchInRepositoryCache[atom]['dbconn'] = dbconn
		atomMatchInRepositoryCache[atom]['result'] = newerPackage[0],0
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
		    dbver = dbconn.retrieveVersion(idpackage)
		    cmp = entropyCompareVersions(pkgversion,dbver)
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
		    atomMatchInRepositoryCache[atom] = {}
		    atomMatchInRepositoryCache[atom]['dbconn'] = dbconn
		    atomMatchInRepositoryCache[atom]['result'] = -1,1
		    return -1,1
		
		versions = []
		for x in dbpkginfo:
		    versions.append(x[1])
		# who is newer ?
		versionlist = getNewerVersion(versions) ## FIXME: this is already running in --deep mode, maybe adding a function that is more gentle with pulling dependencies?
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
		#print newerPackage[1]
		atomMatchInRepositoryCache[atom] = {}
		atomMatchInRepositoryCache[atom]['dbconn'] = dbconn
		atomMatchInRepositoryCache[atom]['result'] = newerPackage[0],0
		return newerPackage[0],0

	    else:
		atomMatchInRepositoryCache[atom] = {}
		atomMatchInRepositoryCache[atom]['dbconn'] = dbconn
		atomMatchInRepositoryCache[atom]['result'] = -1,1
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
	    
	    if (len(similarPackages) > 1):
		# gosh, there are packages with the same name, version, category
		# we need to parse version tag
		versionTags = []
		for pkg in similarPackages:
		    versionTags.append(dbconn.retrieveVersionTag(pkg[1]))
		versiontaglist = getNewerVersionTag(versionTags)
		newerPackage = similarPackages[versionTags.index(versiontaglist[0])]
	    
	    atomMatchInRepositoryCache[atom] = {}
	    atomMatchInRepositoryCache[atom]['dbconn'] = dbconn
	    atomMatchInRepositoryCache[atom]['result'] = newerPackage[1],0
	    return newerPackage[1],0

    else:
	# package not found in any branch
	atomMatchInRepositoryCache[atom] = {}
	atomMatchInRepositoryCache[atom]['dbconn'] = dbconn
	atomMatchInRepositoryCache[atom]['result'] = -1,1
	return -1,1


'''
   @description: matches the package that user chose, using atomMatchInRepository searching in all available repositories.
   @input atom: user choosen package name
   @output: the matched selection, list: [package id,repository name] | if nothing found, returns: [ -1,1 ]
   @ exit errors:
	    -1 => repository cannot be fetched online
'''
atomMatchCache = {}
def atomMatch(atom, caseSentitive = True):

    cached = atomMatchCache.get(atom)
    if cached:
	return cached

    repoResults = {}
    exitstatus = 0
    exitErrors = {}
    
    for repo in etpRepositories:
	# sync database if not available
	rc = fetchRepositoryIfNotAvailable(repo)
	if (rc != 0):
	    exitstatus = -1
	    exitErrors[repo] = -1
	    continue
	# open database
	dbconn = openRepositoryDatabase(repo)
	
	# search
	query = atomMatchInRepository(atom,dbconn,caseSentitive)
	if query[1] == 0:
	    # package found, add to our dictionary
	    repoResults[repo] = query[0]
	
	dbconn.closeDB()

    # handle repoResults
    packageInformation = {}
    
    # nothing found
    if len(repoResults) == 0:
	atomMatchCache[atom] = -1,1
	return -1,1
    
    elif len(repoResults) == 1:
	# one result found
	for repo in repoResults:
	    atomMatchCache[atom] = repoResults[repo],repo
	    return repoResults[repo],repo
    
    elif len(repoResults) > 1:
	# we have to decide which version should be taken
	
	# get package information for all the entries
	for repo in repoResults:
	    
	    # open database
	    dbconn = openRepositoryDatabase(repo)
	
	    # search
	    packageInformation[repo] = {}
	    packageInformation[repo]['version'] = dbconn.retrieveVersion(repoResults[repo])
	    packageInformation[repo]['versiontag'] = dbconn.retrieveVersionTag(repoResults[repo])
	    packageInformation[repo]['revision'] = dbconn.retrieveRevision(repoResults[repo])
	    dbconn.closeDB()

	versions = []
	repoNames = []
	# compare versions
	for repo in packageInformation:
	    repoNames.append(repo)
	    versions.append(packageInformation[repo]['version'])
	
	# found duplicates, this mean that we have to look at the revision and then, at the version tag
	# if all this shait fails, get the uppest repository
	# if no duplicates, we're done
	#print versions
	filteredVersions = filterDuplicatedEntries(versions)
	if (len(versions) > len(filteredVersions)):
	    # there are duplicated results, fetch them
	    # get the newerVersion
	    #print versions
	    newerVersion = getNewerVersion(versions)
	    newerVersion = newerVersion[0]
	    # is newerVersion, the duplicated one?
	    duplicatedEntries = extactDuplicatedEntries(versions)
	    try:
		duplicatedEntries.index(newerVersion)
		needFiltering = True
	    except:
		needFiltering = False
	    
	    if (needFiltering):
		# we have to decide which one is good
		#print "need filtering"
		# we have newerVersion
		conflictingEntries = {}
		for repo in packageInformation:
		    if packageInformation[repo]['version'] == newerVersion:
			conflictingEntries[repo] = {}
			#conflictingEntries[repo]['version'] = packageInformation[repo]['version']
			conflictingEntries[repo]['versiontag'] = packageInformation[repo]['versiontag']
			conflictingEntries[repo]['revision'] = packageInformation[repo]['revision']
		
		# at this point compare tags
		tags = []
		for repo in conflictingEntries:
		    tags.append(conflictingEntries[repo]['versiontag'])
		newerTag = getNewerVersionTag(tags)
		newerTag = newerTag[0]
		
		# is the chosen tag duplicated?
		duplicatedTags = extactDuplicatedEntries(tags)
		try:
		    duplicatedTags.index(newerTag)
		    needFiltering = True
		except:
		    needFiltering = False
		
		print needFiltering
		
		if (needFiltering):
		    #print "also tags match"
		    # yes, it is. we need to compare revisions
		    conflictingTags = {}
		    for repo in conflictingEntries:
		        if conflictingEntries[repo]['versiontag'] == newerTag:
			    conflictingTags[repo] = {}
			    #conflictingTags[repo]['version'] = conflictingEntries[repo]['version']
			    #conflictingTags[repo]['versiontag'] = conflictingEntries[repo]['versiontag']
			    conflictingTags[repo]['revision'] = conflictingEntries[repo]['revision']
		    
		    #print tags
		    #print conflictingTags
		    revisions = []
		    for repo in conflictingTags:
			revisions.append(str(conflictingTags[repo]['revision']))
		    newerRevision = getNewerVersionTag(revisions)
		    newerRevision = newerRevision[0]
		    duplicatedRevisions = extactDuplicatedEntries(revisions)
		    print duplicatedRevisions
		    try:
			duplicatedRevisions.index(newerRevision)
			needFiltering = True
		    except:
			needFiltering = False
		
		    if (needFiltering):
			# ok, we must get the repository with the biggest priority
			print "d'oh"
		        # I'm pissed off, now I get the repository name and quit
			for repository in etpRepositoriesOrder:
			    for repo in conflictingTags:
				if repository == repo:
				    # found it, WE ARE DOOONE!
				    atomMatchCache[atom] = [repoResults[repo],repo]
				    return [repoResults[repo],repo]
		    
		    else:
			# we are done!!!
		        reponame = ''
			#print conflictingTags
		        for x in conflictingTags:
		            if str(conflictingTags[x]['revision']) == str(newerRevision):
			        reponame = x
			        break
			atomMatchCache[atom] = repoResults[reponame],reponame
		        return repoResults[reponame],reponame
		
		else:
		    # we're finally done
		    reponame = ''
		    for x in conflictingEntries:
		        if conflictingEntries[x]['versiontag'] == newerTag:
			    reponame = x
			    break
		    atomMatchCache[atom] = repoResults[reponame],reponame
		    return repoResults[reponame],reponame

	    else:
		# we are fine, the newerVersion is not one of the duplicated ones
		reponame = ''
		for x in packageInformation:
		    if packageInformation[x]['version'] == newerVersion:
			reponame = x
			break
		atomMatchCache[atom] = repoResults[reponame],reponame
		return repoResults[reponame],reponame

	    #print versions
	    
	    
	else:
	    # yeah, we're done, just return the info
	    #print versions
	    newerVersion = getNewerVersion(versions)
	    # get the repository name
	    newerVersion = newerVersion[0]
	    reponame = ''
	    for x in packageInformation:
		if packageInformation[x]['version'] == newerVersion:
		    reponame = x
		    break
	    #print reponame
	    atomMatchCache[atom] = repoResults[reponame],reponame
	    return repoResults[reponame],reponame


'''
   @description: reorder a version list
   @input versionlist: a list
   @output: the ordered list
   FIXME: using Bubble Sorting is not the fastest way
'''
def getNewerVersion(InputVersionlist):
    rc = False
    versionlist = InputVersionlist[:]
    while not rc:
	change = False
        for x in range(len(versionlist)):
	    pkgA = versionlist[x]
	    try:
	        pkgB = versionlist[x+1]
	    except:
	        pkgB = "0"
            result = entropyCompareVersions(pkgA,pkgB)
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
def getNewerVersionTag(InputVersionlist):
    rc = False
    versionlist = InputVersionlist[:]
    while not rc:
	change = False
        for x in range(len(versionlist)):
	    pkgA = versionlist[x]
	    if (not pkgA):
		pkgA = "0"
	    try:
	        pkgB = versionlist[x+1]
		if (not pkgB):
		    pkgB = "0"
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

'''
   @description: generates the dependencies of a [id,repository name] combo.
   @input packageInfo: list composed by int(id) and str(repository name), if this one is int(0), the client database will be opened.
   @output: ordered dependency list
'''
def getDependencies(packageInfo):
    if len(packageInfo) != 2:
	raise Exception, "getDependencies: I need a list with two values in it." # bad bad bad bad
    idpackage = packageInfo[0]
    reponame = packageInfo[1]
    if reponame == 0:
	dbconn = openClientDatabase()
    else:
	dbconn = openRepositoryDatabase(reponame)
    
    # retrieve dependencies
    depend = dbconn.retrieveDependencies(idpackage)
    
    # filter |or| entries
    _depend = []
    for dep in depend:
	
	if dep.startswith("!"):
	    continue # FIXME: add conflicts SUPPORT
	_depend.append(dep)
	
    depend = _depend
    
    dbconn.closeDB()
    return depend


'''
   @description: filter the already installed dependencies
   @input dependencies: list of dependencies to check
   @output: filtered list, aka the needed ones and the ones satisfied
'''
installed_depcache = {}
repo_test_depcache = {}
def filterSatisfiedDependencies(dependencies): # FIXME add force reinstall option

    unsatisfiedDeps = []
    satisfiedDeps = []
    # now create a list with the unsatisfied ones
    # query the installed packages database
    #print etpConst['etpdatabaseclientfilepath']
    clientDbconn = openClientDatabase()
    if (clientDbconn != -1):
        for dependency in dependencies:

	    ### caching
	    repo_cached = repo_test_depcache.get(dependency)
	    if repo_cached:
		repo_test_rc = repo_test_depcache[dependency]['repo_test_rc']
		if repo_test_rc[0] != -1:
		    repo_pkgver = repo_test_depcache[dependency]['pkgver']
		    repo_pkgtag = repo_test_depcache[dependency]['pkgtag']
		    repo_pkgrev = repo_test_depcache[dependency]['pkgrev']
		else:
		    continue # dependency does not exist in our database
	    else:
		repo_test_depcache[dependency] = {}
		repo_test_rc = atomMatch(dependency)
		repo_test_depcache[dependency]['repo_test_rc'] = repo_test_rc
		if repo_test_rc[0] != -1:
		    dbconn = openRepositoryDatabase(repo_test_rc[1])
		    repo_pkgver = dbconn.retrieveVersion(repo_test_rc[0])
		    repo_pkgtag = dbconn.retrieveVersionTag(repo_test_rc[0])
		    repo_pkgrev = dbconn.retrieveRevision(repo_test_rc[0])
		    repo_test_depcache[dependency]['pkgver'] = repo_pkgver
		    repo_test_depcache[dependency]['pkgtag'] = repo_pkgtag
		    repo_test_depcache[dependency]['pkgrev'] = repo_pkgrev
		    dbconn.closeDB()
		else:
		    # dependency does not exist in our database
		    unsatisfiedDeps.append(dependency)
		    continue


	    ### caching
	    ins_cached = installed_depcache.get(dependency)
	    if ins_cached:
		rc = installed_depcache[dependency]['rc']
		if rc[0] != -1:
		    installedVer = installed_depcache[dependency]['installedVer']
		    installedTag = installed_depcache[dependency]['installedTag']
		    installedRev = installed_depcache[dependency]['installedRev']
	    else:
		installed_depcache[dependency] = {}
		rc = atomMatchInRepository(dependency,clientDbconn)
		if rc[0] != -1:
		    installedVer = clientDbconn.retrieveVersion(rc[0])
		    installedTag = clientDbconn.retrieveVersionTag(rc[0])
		    installedRev = clientDbconn.retrieveRevision(rc[0])
		    installed_depcache[dependency]['installedVer'] = installedVer
		    installed_depcache[dependency]['installedTag'] = installedTag
		    installed_depcache[dependency]['installedRev'] = installedRev
		installed_depcache[dependency]['rc'] = rc
	    
	    if rc[0] != -1:
		cmp = compareVersions([repo_pkgver,repo_pkgtag,repo_pkgrev],[installedVer,installedTag,installedRev])
		if cmp != 0:
	            unsatisfiedDeps.append(dependency)
		satisfiedDeps.append(dependency)
	    else:
		#print " ----> "+dependency+" NOT installed."
		unsatisfiedDeps.append(dependency)
    
        clientDbconn.closeDB()

    return unsatisfiedDeps, satisfiedDeps

'''
   @description: generates a dependency tree using unsatisfied dependencies
   @input package: atomInfo [idpackage,reponame]
   @output: 	dependency tree dictionary, plus status code
'''
treecache = {}
def generateDependencyTree(atomInfo, emptydeps = False):

    unsatisfiedDeps = getDependencies(atomInfo)
    remainingDeps = unsatisfiedDeps[:]
    dependenciesNotFound = []
    treeview = []
    tree = {}
    treedepth = -1
    depsOk = False
    
    clientDbconn = openClientDatabase()
    if (clientDbconn == -1):
	return [],-1
    
    while (not depsOk):
	treedepth += 1
	tree[treedepth] = []
        for undep in unsatisfiedDeps:
	
	    passed = treecache.get(undep,None)
	    if passed:
		try:
		    while 1: remainingDeps.remove(undep)
		except:
		    pass
		continue
	
	    # FIXME: add support for conflicts
	    if undep.startswith("!"):
		try:
		    while 1: remainingDeps.remove(undep)
		except:
		    pass
		continue
	
	    # obtain its dependencies
	    atom = atomMatch(undep)
	    if atom[0] == -1:
		# wth, dependency not in database?
		dependenciesNotFound.append(undep)
		#print "not found"
		try:
		    while 1: remainingDeps.remove(undep)
		except:
		    pass
	    else:
		# found, get its deps
		mydeps = getDependencies(atom)
		if (emptydeps):
		    mydeps = filterSatisfiedDependencies(mydeps)
		for dep in mydeps:
		    remainingDeps.append(dep)
		xmatch = atomMatchInRepository(undep,clientDbconn)
		if (not emptydeps):
		    if xmatch[0] == -1:
		        tree[treedepth].append(undep)
		else:
		    tree[treedepth].append(undep)
		treecache[undep] = True
		try:
		    while 1: remainingDeps.remove(undep)
		except:
		    pass
	# merge back remainingDeps into unsatisfiedDeps
	remainingDeps = filterDuplicatedEntries(remainingDeps)
	#cnt = 0
        #for x in tree:
	#    cnt += len(tree[x])
	#print str(len(remainingDeps))+" "+str(cnt)
	unsatisfiedDeps = remainingDeps[:]
	
	if (not unsatisfiedDeps):
	    depsOk = True
	else:
	    depsOk = False

    clientDbconn.closeDB()

    if (dependenciesNotFound):
	# Houston, we've got a problem
	#print "error! DEPS NOT FOUND -> "+str(dependenciesNotFound)
	treeview = {}
	treeview[0] = {}
	treeview[0][0] = dependenciesNotFound
	return treeview,-2

    newtree = {} # tree list
    if (tree):
	for x in tree:
	    newtree[x] = []
	    for y in tree[x]:
		newtree[x].append(atomMatch(y))
	    if (newtree[x]):
	        newtree[x] = filterDuplicatedEntries(newtree[x])
	# now filter newtree
	treelength = len(newtree)
	for count in range(treelength)[::-1]:
	    x = 0
	    while x < count:
		# remove dups in this list
		for z in newtree[count]:
		    try:
			while 1:
			    newtree[x].remove(z)
			    #print "removing "+str(z)
		    except:
			pass
		x += 1
    del tree

    #print treeview
    return newtree,0 # treeview is used to show deps while tree is used to run the dependency code.


'''
   @description: generates a list cotaining the needed dependencies of a list requested atoms
   @input package: list of atoms that would be installed in list form, whose each element is composed by [idpackage,repository name]
   @output: list containing, for each element: [idpackage,repository name]
   		@ if dependencies couldn't be satisfied, the output will be -1
   @note: this is the function that should be used for 3rd party applications after using atomMatch()
'''
def getRequiredPackages(foundAtoms, emptydeps = False):
    deptree = {}
    depcount = -1
    
    for atomInfo in foundAtoms:
	depcount += 1
	newtree, result = generateDependencyTree(atomInfo, emptydeps)
	if (result != 0):
	    return newtree, result
	if (newtree):
	    deptree[depcount] = newtree.copy()
	    #print deptree[depcount]

    newdeptree = deptree.copy() # tree list
    if (deptree):
	# now filter newtree
	treelength = len(newdeptree)
	for count in range(treelength)[::-1]:
	    pkglist = []
	    #print count
	    for x in newdeptree[count]:
		for y in newdeptree[count][x]:
		    pkglist.append(y)
	    #print len(pkglist)
	    # remove dups in the other lists
	    for pkg in pkglist:
		x = 0
		while x < count:
		    #print x
		    for z in newdeptree[x]:
		        try:
		            while 1:
			        newdeptree[x][z].remove(pkg)
			        #print "removing "+str(pkg)
		        except:
			    pass
			    
		    x += 1
    del deptree

    return newdeptree,0


'''
   @description: generates a list of packages that can be added to the removal queue of atoms (list)
   @input package: atomInfo [idpackage,reponame]
   @output: removal tree dictionary, plus status code
'''
dictDeps = {}
def generateRemovalTree(atoms, output = False):

    clientDbconn = openClientDatabase()
    if (clientDbconn == -1):
	return [],-1
    
    dependencies = []
    atomsInfo = []
    treeview = []
    removeList = []
    # Initialize
    for atom in atoms:
        atomInfo = atomMatchInRepository(atom,clientDbconn)
	atomsInfo.append(atomInfo)
	xatom = clientDbconn.retrieveAtom(atomInfo[0])
	xdepends = clientDbconn.searchDepends(dep_getkey(xatom))
	dependencies.append(atomInfo[0])
	dictDeps[atomInfo[0]] = set(xdepends)
	# even add my depends?
	for x in xdepends:
	    #print x
	    treeview.append(x)

    remainingDeps = dependencies[:]
    dependencies = set(dependencies)
    for atomInfo in atomsInfo:
        treeview.append(atomInfo[0])
    depsOk = False
    
    #print treeview
    
    while (not depsOk):
	change = False
	for dep in remainingDeps:

	    if dep in removeList: # if it has been already removed
		try:
		    while 1: dependencies.remove(dep)
		except:
		    pass
		continue

            #myatom = clientDbconn.retrieveAtom(dep[0])
	    #key = dep_getkey(myatom)
	    depends = dictDeps[dep].copy()
	    #print "--------"
	    #print depends
	    #print clientDbconn.retrieveAtom(dep)
	    #print "--------"
	    
	    for depend in depends:
		if depend in treeview:
		    #print "changed"
		    change = True
		    try:
			while 1:
		            dictDeps[dep].remove(depend)
		    except:
			pass
	    
	    if (list(dictDeps[dep]) == []):

		#print "here"
		# I can safely add this
		change = True
		treeview.append(dep)
		removeList.append(dep)
		try:
		    while 1: dependencies.remove(dep)
		except:
		    pass
		if 1:
		    printatom = clientDbconn.retrieveAtom(dep)
		    print_info(red(" @@ Adding ")+bold(printatom))
		xdeps = getDependencies([dep,0])
		for x in xdeps:
		    xdep = atomMatchInRepository(x,clientDbconn)
		    mydepends = clientDbconn.searchDepends(dep_getkey(x))
		    dependencies.add(xdep[0])
		    dictDeps[xdep[0]] = set(mydepends)
		    
	    #print "--------"

	remainingDeps = list(dependencies)[:]
	if (change == False):
	    depsOk = True
	else:
	    depsOk = False

    treeview = filterDuplicatedEntries(treeview)
    # remove atomsInfo
    for atomInfo in atomsInfo:
	try:
	    while 1: treeview.remove(atomInfo[0])
	except:
	    pass
    for x in treeview:
        print clientDbconn.retrieveAtom(x)

    clientDbconn.closeDB()
    return treeview,0 # treeview is used to show deps while tree is used to run the dependency code.


'''
   @description: using given information (atom), retrieves idpackage of the installed atom
   @input package: package atom
   @output: list of idpackages of the atoms from the installed packages db
'''
def getInstalledAtoms(atom):

    clientDbconn = openClientDatabase()
    results = []
    
    if (clientDbconn != -1):
        if not isjustname(atom):
	    key = dep_getkey(atom)
        else:
	    key = atom[:]
        name = key.split("/")[1]
        cat = key.split("/")[0]
        rc = clientDbconn.searchPackagesByNameAndCategory(name,cat)
        if (rc):
	    for x in rc:
	        results.append(x[1])
        clientDbconn.closeDB()

    return results

'''
   @description: compare two lists composed by [version,tag,revision] and [version,tag],revision
   			if listA > listB --> positive number
			if listA == listB --> 0
			if listA < listB --> negative number	
   @input package: listA[version,tag,rev] and listB[version,tag,rev]
   @output: integer number
'''
def compareVersions(listA,listB):
    if len(listA) != 3 or len(listB) != 3:
	raise Exception, "compareVersions: listA and/or listB must be long 3"
    # start with version
    rc = entropyCompareVersions(listA[0],listB[0])
    
    if (rc == 0):
	# check tag
	if listA[1] > listB[1]:
	    return 1
	elif listA[1] < listB[1]:
	    return -1
	else:
	    # check rev
	    if listA[2] > listB[2]:
		return 1
	    elif listA[2] < listB[2]:
		return -1
	    else:
		return 0
    return rc


########################################################
####
##   Files handling
#

'''
   @description: check if Equo has to download the given package
   @input package: filename to check inside the packages directory -> file, checksum of the package -> checksum
   @output: -1 = should be downloaded, -2 = digest broken (not mandatory), remove & download, 0 = all fine, we don't need to download it
'''
def checkNeededDownload(filepath,checksum = None):
    # is the file available
    if os.path.isfile(etpConst['entropyworkdir']+"/"+filepath) and os.path.isfile(etpConst['entropyworkdir']+"/"+filepath+etpConst['packageshashfileext']):
	if checksum is None:
	    return 0
	else:
	    # check digest
	    md5res = compareMd5(etpConst['entropyworkdir']+"/"+filepath,checksum)
	    if (md5res):
		return 0
	    else:
		return -2
    else:
	return -1


'''
   @description: download a package into etpConst['packagesbindir'] and check for digest if digest is not False
   @input package: url -> HTTP/FTP url, digest -> md5 hash of the file
   @output: -1 = download error (cannot find the file), -2 = digest error, 0 = all fine
'''
def fetchFile(url,digest = False):
    # remove old
    filename = os.path.basename(url)
    filepath = etpConst['packagesbindir']+"/"+filename
    if os.path.isfile(filepath):
	os.system("rm -f "+filepath)
    # now fetch the new one
    try:
        fetchChecksum = downloadData(url,filepath)
    except:
	return -1
    if (digest != False):
	if (fetchChecksum != digest):
	    # not properly downloaded
	    return -2
	else:
	    return 0
    return 0


'''
   @description: unpack the given file on the system and also update gentoo db if requested
   @input package: package file (without path)
   @output: 0 = all fine, >0 = error!
'''
# FIXME: add gentoo db handling
def installFile(package, infoDict = None):
    import shutil
    pkgpath = etpConst['packagesbindir']+"/"+package
    if not os.path.isfile(pkgpath):
	return 1
    # unpack and install
    unpackDir = etpConst['entropyunpackdir']+"/"+package
    if os.path.isdir(unpackDir):
	os.system("rm -rf "+unpackDir)
    imageDir = unpackDir+"/image"
    os.makedirs(imageDir)
    
    rc = uncompressTarBz2(pkgpath,unpackDir)
    if (rc != 0):
	return rc
    rc = uncompressTarBz2(unpackDir+etpConst['packagecontentdir']+"/"+package,imageDir)
    if (rc != 0):
	return rc
    if not os.path.isdir(imageDir):
	return 2
    
    # setup imageDir properly
    imageDir = imageDir.encode(sys.getfilesystemencoding())
    # merge data into system
    for currentdir,subdirs,files in os.walk(imageDir):
	# create subdirs
        for dir in subdirs:
	    #dirpath += "/"+dir
	    imagepathDir = currentdir + "/" + dir
	    rootdir = imagepathDir[len(imageDir):]
	    # get info
	    if (rootdir):
		if os.path.islink(rootdir):
		    if not os.path.exists(rootdir): # broken symlink
			#print "I want to remove "+rootdir
			#print os.readlink(rootdir)
		        os.remove(rootdir)
		elif os.path.isfile(rootdir): # weird
		    print_warning(red(" *** ")+bold(rootdir)+red(" is a file when it should be a directory !! Removing in 10 seconds..."))
		    time.sleep(10)
		    os.remove(rootdir)
	        if (not os.path.isdir(rootdir)) and (not os.access(rootdir,os.R_OK)):
		    #print "creating dir "+rootdir
		    os.makedirs(rootdir)
	    user = os.stat(imagepathDir)[4]
	    group = os.stat(imagepathDir)[5]
	    os.chown(rootdir,user,group)
	    shutil.copystat(imagepathDir,rootdir)
	#dirpath = ''
	for file in files:
	    fromfile = currentdir+"/"+file
	    tofile = fromfile[len(imageDir):]
	    #print "copying file "+fromfile+" to "+tofile

	    if os.access(tofile,os.F_OK):
		try:
		    os.remove(tofile)
		except:
		    rc = os.system("rm -f "+tofile)
		    if (rc != 0):
			return 3
	    try:
		shutil.copy2(fromfile,tofile)
	    except IOError,(errno,strerror):
		if errno == 2:
		    # better to pass away, sometimes gentoo packages are fucked up and contain broken things
		    pass
		else:
		    rc = os.system("/bin/cp "+fromfile+" "+tofile)
		    if (rc != 0):
		        return 4
	    try:
	        user = os.stat(fromfile)[4]
	        group = os.stat(fromfile)[5]
	        os.chown(tofile,user,group)
	        shutil.copystat(fromfile,tofile)
	    except:
		pass # sometimes, gentoo packages are fucked up and contain broken symlinks

    os.system("rm -rf "+imageDir)

    if infoDict is not None:
	rc = installPackageIntoGentooDatabase(infoDict,unpackDir+etpConst['packagecontentdir']+"/"+package)
	if (rc >= 0):
	    os.system("rm -rf "+unpackDir)
	    return rc
    
    # remove unpack dir
    os.system("rm -rf "+unpackDir)
    return 0

'''
   @description: inject the database information into the Gentoo database
   @input package: dictionary containing information collected by installPackages (important are atom, slot, category, name, version)
   @output: 0 = all fine, >0 = error!
'''
def installPackageIntoGentooDatabase(infoDict,packageFile):
    # handle gentoo-compat
    
    _portage_avail = False
    try:
	from portageTools import getInstalledAtoms as _portage_getInstalledAtoms, getPackageSlot as _portage_getPackageSlot, getPortageAppDbPath as _portage_getPortageAppDbPath
	_portage_avail = True
    except:
	return -1 # no Portage support
    if (_portage_avail):
	portDbDir = _portage_getPortageAppDbPath()
	# extract xpak from unpackDir+etpConst['packagecontentdir']+"/"+package
	key = infoDict['category']+"/"+infoDict['name']
	#print _portage_getInstalledAtom(key)
	atomsfound = _portage_getInstalledAtoms(key)
	
	### REMOVE
	# parse slot and match and remove)
	if atomsfound is not None:
	    pkgToRemove = ''
	    for atom in atomsfound:
	        atomslot = _portage_getPackageSlot(atom)
	        if atomslot == infoDict['slot']:
		    #print "match slot, remove -> "+str(atomslot)
		    pkgToRemove = atom
		    break
	    if (pkgToRemove):
	        removePath = portDbDir+pkgToRemove
	        os.system("rm -rf "+removePath)
	        #print "removing -> "+removePath
	
	### INSTALL NEW
	extractPath = os.path.dirname(packageFile)
	extractPath += "/xpak"
	extractXpak(packageFile,extractPath)
	if not os.path.isdir(portDbDir+infoDict['category']):
	    os.makedirs(portDbDir+infoDict['category'])
	os.rename(extractPath,portDbDir+infoDict['category']+"/"+infoDict['name']+"-"+infoDict['version'])

    return 0

'''
   @description: unpack the given file on the system and also update gentoo db if requested
   @input package: package file (without path)
   @output: 0 = all fine, >0 = error!
'''
def installPackageIntoDatabase(idpackage,repository):
    # fetch info
    dbconn = openRepositoryDatabase(repository)
    data = dbconn.getPackageData(idpackage)
    # get current revision
    rev = dbconn.retrieveRevision(idpackage)
    branch = dbconn.retrieveBranch(idpackage)
    dbconn.closeDB()
    
    # inject
    clientDbconn = openClientDatabase()
    idpk, rev, x, status = clientDbconn.addPackage(data, revision = rev, wantedBranch = branch, addBranch = False)
    del x
    if (not status):
	clientDbconn.closeDB()
	return 1 # it hasn't been insterted ? why??
    
    # add idpk to the installedtable
    clientDbconn.removePackageFromInstalledTable(idpk)
    clientDbconn.addPackageToInstalledTable(idpk,repository)
    
    clientDbconn.closeDB()
    return 0


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
    myopts = []
    for opt in options:
	if (opt == "--verbose"):
	    equoRequestVerbose = True
	if (opt == "--quiet"):
	    equoRequestQuiet = True
	else:
	    myopts.append(opt)

    if options[0] == "installed":
	rc = searchInstalledPackages(myopts[1:])

    elif options[0] == "belongs":
	rc = searchBelongs(myopts[1:])

    elif options[0] == "depends":
	rc = searchDepends(myopts[1:], verbose = equoRequestVerbose)

    elif options[0] == "files":
	rc = searchFiles(myopts[1:], quiet = equoRequestQuiet)

    elif options[0] == "description":
	rc = searchDescription(myopts[1:])

    return rc

########################################################
####
##   Database Tools
#

def package(options):

    if len(options) < 1:
	return 0

    # Options available for all the packages submodules
    myopts = options[1:]
    equoRequestAsk = False
    equoRequestPretend = False
    equoRequestPackagesCheck = False
    equoRequestVerbose = False
    equoRequestDeps = True
    equoRequestEmptyDeps = False
    equoRequestOnlyFetch = False
    rc = 0
    _myopts = []
    for opt in myopts:
	if (opt == "--ask"):
	    equoRequestAsk = True
	elif (opt == "--pretend"):
	    equoRequestPretend = True
	elif (opt == "--verbose"):
	    equoRequestVerbose = True
	elif (opt == "--nodeps"):
	    equoRequestDeps = False
	elif (opt == "--empty"):
	    equoRequestEmptyDeps = True
	elif (opt == "--fetch"):
	    equoRequestOnlyFetch = True
	else:
	    _myopts.append(opt)
    myopts = _myopts

    if (options[0] == "search"):
	if len(myopts) > 0:
	    rc = searchPackage(myopts)

    if (options[0] == "install"):
	if len(myopts) > 0:
	    rc, status = installPackages(myopts, ask = equoRequestAsk, pretend = equoRequestPretend, verbose = equoRequestVerbose, deps = equoRequestDeps, emptydeps = equoRequestEmptyDeps, onlyfetch = equoRequestOnlyFetch)
	else:
	    print_error(red(" Nothing to do."))
	    rc = 127

    if (options[0] == "remove"):
	if len(myopts) > 0:
	    rc, status = removePackages(myopts, ask = equoRequestAsk, pretend = equoRequestPretend, verbose = equoRequestVerbose, deps = equoRequestDeps)
	else:
	    print_error(red(" Nothing to do."))
	    rc = 127

    return rc


def database(options):

    if len(options) < 1:
	return 0

    # FIXME: need SPEED and completion
    if (options[0] == "generate"):
	
	print_warning(bold("####### ATTENTION -> ")+red("The installed package database will be regenerated, this will take a LOT of time."))
	print_warning(bold("####### ATTENTION -> ")+red("Sabayon Linux Officially Repository MUST be on top of the repositories list in ")+etpConst['repositoriesconf'])
	print_warning(bold("####### ATTENTION -> ")+red("This method is only used for testing at the moment and you need Portage installed. Don't worry about Portage warnings."))
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
	print_info(darkred("  Initializing the new database at "+bold(etpConst['etpdatabaseclientfilepath'])), back = True)
	# we can't use openClientDatabase
	clientDbconn = etpDatabase(readOnly = False, noUpload = True, dbFile = etpConst['etpdatabaseclientfilepath'], clientDatabase = True)
	clientDbconn.initializeDatabase()
	print_info(darkgreen("  Database reinitialized correctly at "+bold(etpConst['etpdatabaseclientfilepath'])))
	
	# now collect packages in the system
	from portageTools import getInstalledPackages as _portage_getInstalledPackages
	print_info(red("  Collecting installed packages..."))
	
	portagePackages = _portage_getInstalledPackages()
	portagePackages = portagePackages[0]
	
	print_info(red("  Now analyzing database content..."))

	foundPackages = []

	# do for each database
	missingPackages = portagePackages[:]
	for portagePackage in portagePackages: # for portagePackage in remainingPackages
	    print_info(red("  Analyzing ")+bold(portagePackage), back = True)
	    
	    data = atomMatch(portagePackage)
	    if (data[0] != -1):
	        foundPackages.append(data)
		missingPackages.remove(portagePackage)
		
	print_info(red("  ### Packages matching: ")+bold(str(len(foundPackages))))
	print_info(red("  ### Packages not matching: ")+bold(str(len(missingPackages))))
	
	print_info(red("  Now filling the new database..."))
	
	count = 0
	total = str(len(foundPackages))
	
	for x in foundPackages:
	    # open its database
	    count += 1
	    dbconn = openRepositoryDatabase(x[1])
	    
	    atomName = dbconn.retrieveAtom(x[0])
	    atomInfo = dbconn.getPackageData(x[0])
	    atomBranch = dbconn.retrieveBranch(x[0])
	    dbconn.closeDB()
	    # filling
	    print_info("  "+bold("(")+darkgreen(str(count))+"/"+blue(total)+bold(")")+red(" Injecting ")+bold(atomName), back = True)
	    # fill clientDbconn # FIXME write a general client side addPackage function
	    clientDbconn.addPackage(atomInfo, wantedBranch = atomBranch, addBranch = False)
	    # now add the package
	    clientDbconn.addPackageToInstalledTable(x[0],x[1])

	print_info(red("  Database reinitialized successfully."))

	clientDbconn.closeDB()


def printPackageInfo(idpackage,dbconn, clientSearch = False, strictOutput = False):
    # now fetch essential info
    pkgatom = dbconn.retrieveAtom(idpackage)
    if (not strictOutput):
        pkgname = dbconn.retrieveName(idpackage)
        pkgcat = dbconn.retrieveCategory(idpackage)
        pkglic = dbconn.retrieveLicense(idpackage)
        pkgsize = dbconn.retrieveSize(idpackage)
        pkgbin = dbconn.retrieveDownloadURL(idpackage)
        pkgflags = dbconn.retrieveCompileFlags(idpackage)
        pkgkeywords = dbconn.retrieveBinKeywords(idpackage)
        pkgdigest = dbconn.retrieveDigest(idpackage)
        pkgcreatedate = convertUnixTimeToHumanTime(int(dbconn.retrieveDateCreation(idpackage)))
        pkgsize = bytesIntoHuman(pkgsize)
	pkgdeps = dbconn.retrieveDependencies(idpackage)

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
            clientDbconn = etpDatabase(readOnly = True, noUpload = True, dbFile = etpConst['etpdatabaseclientfilepath'], clientDatabase = True)
            pkginstalled = getInstalledAtoms(pkgatom)
            if (pkginstalled):
	        # we need to match slot
	        for idx in pkginstalled:
	            islot = clientDbconn.retrieveSlot(idx)
	            if islot == pkgslot:
		        # found
		        installedVer = clientDbconn.retrieveVersion(idx)
		        installedTag = clientDbconn.retrieveVersionTag(idx)
		        if not installedTag:
		            installedTag = "NoTag"
		        installedRev = clientDbconn.retrieveRevision(idx)
		        break
            clientDbconn.closeDB()


    print_info(red("     @@ Package: ")+bold(pkgatom)+"\t\t"+blue("branch: ")+bold(pkgbranch))
    if (not strictOutput):
        print_info(darkgreen("       Category:\t\t")+darkblue(pkgcat))
        print_info(darkgreen("       Name:\t\t\t")+darkblue(pkgname))
    print_info(darkgreen("       Available:\t\t")+darkblue("version: ")+bold(pkgver)+darkblue(" ~ tag: ")+bold(pkgtag)+darkblue(" ~ revision: ")+bold(str(pkgrev)))
    if (not clientSearch):
        print_info(darkgreen("       Installed:\t\t")+darkblue("version: ")+bold(installedVer)+darkblue(" ~ tag: ")+bold(installedTag)+darkblue(" ~ revision: ")+bold(str(installedRev)))
    if (not strictOutput):
        print_info(darkgreen("       Slot:\t\t\t")+blue(str(pkgslot)))
        print_info(darkgreen("       Size:\t\t\t")+blue(str(pkgsize)))
        print_info(darkgreen("       Download:\t\t")+brown(str(pkgbin)))
        print_info(darkgreen("       Checksum:\t\t")+brown(str(pkgdigest)))
	if (pkgdeps):
	    print_info(darkred("       ##")+darkgreen(" Dependencies:"))
	    for pdep in pkgdeps:
		print_info(darkred("       ## \t\t\t")+brown(pdep))
    print_info(darkgreen("       Homepage:\t\t")+red(pkghome))
    print_info(darkgreen("       Description:\t\t")+pkgdesc)
    if (not strictOutput):
	print_info(darkgreen("       Compiled with:\t")+blue(pkgflags[1]))
        print_info(darkgreen("       Architectures:\t")+blue(string.join(pkgkeywords," ")))
        print_info(darkgreen("       Created:\t\t")+pkgcreatedate)
        print_info(darkgreen("       License:\t\t")+red(pkglic))


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
	
	rc = fetchRepositoryIfNotAvailable(repo)
	if (rc != 0):
	    searchError = True
	    continue
	
	dbconn = openRepositoryDatabase(repo)
	dataInfo = [] # when idreturn is True
	for package in packages:
	    result = dbconn.searchPackages(package)
	    
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


def searchInstalledPackages(packages, idreturn = False):
    
    if (not idreturn):
        print_info(yellow(" @@ ")+darkgreen("Searching..."))

    clientDbconn = openClientDatabase()
    dataInfo = [] # when idreturn is True
    
    for package in packages:
	result = clientDbconn.searchPackages(package)
	if (result):
	    # print info
	    if (not idreturn):
	        print_info(blue("     Keyword: ")+bold("\t"+package))
	        print_info(blue("     Found:   ")+bold("\t"+str(len(result)))+red(" entries"))
	    for pkg in result:
		idpackage = pkg[1]
		atom = pkg[0]
		branch = clientDbconn.retrieveBranch(idpackage)
		if (idreturn):
		    dataInfo.append(idpackage)
		else:
		    printPackageInfo(idpackage,clientDbconn, clientSearch = True)
	
    clientDbconn.closeDB()

    if (idreturn):
	return dataInfo
    
    return 0


def searchBelongs(files, idreturn = False):
    
    if (not idreturn):
        print_info(yellow(" @@ ")+darkgreen("Belong Search..."))

    clientDbconn = openClientDatabase()
    dataInfo = [] # when idreturn is True
    
    for file in files:
	result = clientDbconn.searchBelongs(file)
	if (result):
	    # print info
	    if (not idreturn):
	        print_info(blue("     Keyword: ")+bold("\t"+file))
	        print_info(blue("     Found:   ")+bold("\t"+str(len(result)))+red(" entries"))
	    for idpackage in result:
		if (idreturn):
		    dataInfo.append(idpackage)
		else:
		    printPackageInfo(idpackage, clientDbconn, clientSearch = True)
	
    clientDbconn.closeDB()

    if (idreturn):
	return dataInfo
    
    return 0


def searchDepends(atoms, idreturn = False, verbose = False):
    
    if (not idreturn):
        print_info(yellow(" @@ ")+darkgreen("Depends Search..."))

    # validate atoms
    '''
    _atoms = []
    for atom in atoms:
	try:
	    key = dep_getkey(atom)
	    _atoms.append(key)
	except:
	    print_warning(red("  !! ")+bold(atom)+red(" is not valid."))
	    pass
    atoms = _atoms
    '''
    #packages = searchPackage(atoms,idreturn = True)

    clientDbconn = openClientDatabase()
    dataInfo = [] # when idreturn is True
    for atom in atoms:
	result = clientDbconn.searchDepends(atom)
	if (result):
	    # print info
	    if (not idreturn):
	        print_info(blue("     Keyword: ")+bold("\t"+atom))
	        print_info(blue("     Found:   ")+bold("\t"+str(len(result)))+red(" entries"))
	    for idpackage in result:
		if (idreturn):
		    dataInfo.append(idpackage)
		else:
		    if (verbose):
		        printPackageInfo(idpackage, clientDbconn, clientSearch = True)
		    else:
		        printPackageInfo(idpackage, clientDbconn, clientSearch = True, strictOutput = True)
	
    clientDbconn.closeDB()

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
	
    clientDbconn.closeDB()

    if (idreturn):
	return dataInfo
    
    return 0

def searchDescription(descriptions, idreturn = False):
    
    foundPackages = {}
    
    if (not idreturn):
        print_info(yellow(" @@ ")+darkgreen("Description Search..."))
    # search inside each available database
    repoNumber = 0
    searchError = False
    for repo in etpRepositories:
	foundPackages[repo] = {}
	repoNumber += 1
	
	if (not idreturn):
	    print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
	
	rc = fetchRepositoryIfNotAvailable(repo)
	if (rc != 0):
	    searchError = True
	    continue
	
	dbconn = openRepositoryDatabase(repo)
	dataInfo = [] # when idreturn is True
	for desc in descriptions:
	    result = dbconn.searchPackagesByDescription(desc)
	    if (result):
		foundPackages[repo][desc] = result
	        # print info
		if (not idreturn):
	            print_info(blue("     Keyword: ")+bold("\t"+desc))
	            print_info(blue("     Found:   ")+bold("\t"+str(len(foundPackages[repo][desc])))+red(" entries"))
	        for pkg in foundPackages[repo][desc]:
		    idpackage = pkg[1]
		    atom = pkg[0]
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


'''
   @description: open the repository database and returns the pointer
   @input repositoryName: name of the client database
   @output: database pointer or, -1 if error
'''
def openRepositoryDatabase(repositoryName):
    dbfile = etpRepositories[repositoryName]['dbpath']+"/"+etpConst['etpdatabasefile']
    if not os.path.isfile(dbfile):
	rc = fetchRepositoryIfNotAvailable(repositoryName)
	if (rc):
	    raise Exception, "openRepositoryDatabase: cannot sync repository "+repositoryName
    conn = etpDatabase(readOnly = True, dbFile = dbfile, clientDatabase = True)
    return conn

'''
   @description: open the installed packages database and returns the pointer
   @output: database pointer or, -1 if error
'''
def openClientDatabase():
    if os.path.isfile(etpConst['etpdatabaseclientfilepath']):
        conn = etpDatabase(readOnly = False, dbFile = etpConst['etpdatabaseclientfilepath'], clientDatabase = True)
	return conn
    else:
	raise Exception,"openClientDatabase: installed packages database not found. At this stage, the only way to have it is to run 'equo database generate'."


########################################################
####
##   Actions Handling
#

def installPackages(packages, ask = False, pretend = False, verbose = False, deps = True, emptydeps = False, onlyfetch = False):

    # check if I am root
    if (not checkRoot()) and (not pretend):
	print_error(red("You must run this function as superuser."))
	return 1,-1
    
    foundAtoms = []
    for package in packages:
	foundAtoms.append([package,atomMatch(package)])

    # filter packages not found
    _foundAtoms = []
    for result in foundAtoms:
	exitcode = result[1][0]
	if (exitcode != -1):
	    _foundAtoms.append(result[1])
	else:
	    print_warning(red("## ATTENTION -> package")+bold(" "+result[0]+" ")+red("not found in database"))

    foundAtoms = _foundAtoms
    
    # are packages in foundAtoms?
    if (len(foundAtoms) == 0):
	print_error(red("No packages found"))
	return 127,-1

    if (ask or pretend or verbose):
        # now print the selected packages
        print_info(red(" @@ ")+blue("These are the chosen packages:"))
        totalatoms = len(foundAtoms)
        atomscounter = 0
        for atomInfo in foundAtoms:
	    atomscounter += 1
	    idpackage = atomInfo[0]
	    reponame = atomInfo[1]
	    # open database
	    dbconn = openRepositoryDatabase(reponame)

	    # get needed info
	    pkgatom = dbconn.retrieveAtom(idpackage)
	    pkgver = dbconn.retrieveVersion(idpackage)
	    pkgtag = dbconn.retrieveVersionTag(idpackage)
	    if not pkgtag:
	        pkgtag = "NoTag"
	    pkgrev = dbconn.retrieveRevision(idpackage)
	    pkgslot = dbconn.retrieveSlot(idpackage)
	
	    # client info
	    installedVer = "Not installed"
	    installedTag = "NoTag"
	    installedRev = "NoRev"
	    clientDbconn = openClientDatabase()
	    if (clientDbconn != -1):
	        pkginstalled = getInstalledAtoms(pkgatom)
	        if (pkginstalled):
	            # we need to match slot
	            for idx in pkginstalled:
	                islot = clientDbconn.retrieveSlot(idx)
		        if islot == pkgslot:
		            # found
		            installedVer = clientDbconn.retrieveVersion(idx)
		            installedTag = clientDbconn.retrieveVersionTag(idx)
		            if not installedTag:
			        installedTag = "NoTag"
		            installedRev = clientDbconn.retrieveRevision(idx)
		            break
	        clientDbconn.closeDB()

	    print_info("   # "+red("(")+bold(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+bold(pkgatom)+" >>> "+red(etpRepositories[reponame]['description']))
	    print_info("\t"+red("Versioning:\t")+" "+blue(installedVer)+" / "+blue(installedTag)+" / "+blue(str(installedRev))+bold(" ===> ")+darkgreen(pkgver)+" / "+darkgreen(pkgtag)+" / "+darkgreen(str(pkgrev)))
	    # tell wether we should update it
	    if installedVer == "Not installed":
	        installedVer = "0"
	    if installedTag == "NoTag":
	        installedTag == ''
	    if installedRev == "NoRev":
	        installedRev == 0
	    cmp = compareVersions([pkgver,pkgtag,pkgrev],[installedVer,installedTag,installedRev])
	    if (cmp == 0):
	        action = darkgreen("No update needed")
	    elif (cmp > 0):
	        if (installedVer == "0"):
		    action = darkgreen("Install")
	        else:
	            action = blue("Upgrade")
	    else:
	        action = red("Downgrade")
	    print_info("\t"+red("Action:\t\t")+" "+action)
	
	    dbconn.closeDB()

	if (verbose or ask or pretend):
            print_info(red(" @@ ")+blue("Number of packages: ")+str(totalatoms))
    
        if (ask):
            rc = askquestion("     Would you like to continue with dependencies calculation ?")
            if rc == "No":
	        return 0,0

    runQueue = []

    print_info(red(" @@ ")+blue("Calculating..."))

    if (deps):
        treepackages, result = getRequiredPackages(foundAtoms, emptydeps)
        # add dependencies, explode them
	if (result == -2):
	    print_error(red(" @@ ")+blue("Cannot find needed dependencies: ")+str(treepackages))
	    return 130, -1
	elif (result == -1): # no database connection
	    print_error(red(" @@ ")+blue("Cannot find the Installed Packages Database. It's needed to accomplish dependency resolving. Try to run ")+bold("equo database generate"))
	    return 200, -1
	pkgs = []
	for x in range(len(treepackages))[::-1]:
	    #print x
	    for z in treepackages[x]:
		#print treepackages[x][z]
		for a in treepackages[x][z]:
		    pkgs.append(a)
	#print pkgs
        for dep in pkgs:
	    runQueue.append(dep)
    
    # remove duplicates
    runQueue = [x for x in runQueue if x not in foundAtoms]
    
    # add our requested packages at the end
    for atomInfo in foundAtoms:
	runQueue.append(atomInfo)

    downloadSize = 0
    actionQueue = {}

    if (not runQueue):
	print_error(red("Nothing to do."))
	return 127,-1

    if (runQueue):
	pkgsToInstall = 0
	pkgsToUpdate = 0
	pkgsToReinstall = 0
	pkgsToDowngrade = 0
	if (ask or pretend):
	    print_info(red(" @@ ")+blue("These are the packages that would be merged:"))
	for packageInfo in runQueue:
	    dbconn = openRepositoryDatabase(packageInfo[1])
	    
	    pkgatom = dbconn.retrieveAtom(packageInfo[0])
	    pkgver = dbconn.retrieveVersion(packageInfo[0])
	    pkgtag = dbconn.retrieveVersionTag(packageInfo[0])
	    pkgrev = dbconn.retrieveRevision(packageInfo[0])
	    pkgslot = dbconn.retrieveSlot(packageInfo[0])
	    pkgdigest = dbconn.retrieveDigest(packageInfo[0])
	    pkgfile = dbconn.retrieveDownloadURL(packageInfo[0])
	    pkgcat = dbconn.retrieveCategory(packageInfo[0])
	    pkgname = dbconn.retrieveName(packageInfo[0])
	    
	    # fill action queue
	    actionQueue[pkgatom] = {}
	    actionQueue[pkgatom]['repository'] = packageInfo[1]
	    actionQueue[pkgatom]['idpackage'] = packageInfo[0]
	    actionQueue[pkgatom]['slot'] = pkgslot
	    actionQueue[pkgatom]['atom'] = pkgatom
	    actionQueue[pkgatom]['version'] = pkgver
	    actionQueue[pkgatom]['category'] = pkgcat
	    actionQueue[pkgatom]['name'] = pkgname
	    actionQueue[pkgatom]['remove'] = -1
	    actionQueue[pkgatom]['download'] = etpRepositories[packageInfo[1]]['packages']+"/"+os.path.basename(pkgfile)
	    actionQueue[pkgatom]['checksum'] = pkgdigest
	    dl = checkNeededDownload(pkgfile, pkgdigest)
	    actionQueue[pkgatom]['fetch'] = dl
	    if dl < 0:
		pkgsize = dbconn.retrieveSize(packageInfo[0])
		downloadSize += int(pkgsize)
	
	    # get installed package data
	    installedVer = '0'
	    installedTag = ''
	    installedRev = 0
	    clientDbconn = openClientDatabase()
	    if (clientDbconn != -1):
	        pkginstalled = getInstalledAtoms(pkgatom)
	        if (pkginstalled):
	            # we need to match slot
	            for idx in pkginstalled:
			#print clientDbconn.retrieveAtom(idx)
	                islot = clientDbconn.retrieveSlot(idx)
		        if islot == pkgslot:
		            # found
		            installedVer = clientDbconn.retrieveVersion(idx)
		            installedTag = clientDbconn.retrieveVersionTag(idx)
		            if not installedTag:
			        installedTag = ''
		            installedRev = clientDbconn.retrieveRevision(idx)
			    actionQueue[pkgatom]['remove'] = idx
		            break
	        clientDbconn.closeDB()

	    if not (ask or pretend or verbose):
		continue

	    flags = " ["
	    cmp = compareVersions([pkgver,pkgtag,pkgrev],[installedVer,installedTag,installedRev])
	    if (cmp == 0):
		pkgsToReinstall += 1
	        flags += red("R")
	    elif (cmp > 0):
	        if (installedVer == "0"):
		    pkgsToInstall += 1
	            flags += darkgreen("N")
	        else:
		    pkgsToUpdate += 1
		    flags += blue("U")
	    else:
		pkgsToDowngrade += 1
	        flags += darkblue("D")
	    flags += "] "

	    repoinfo = red("[")+brown("from: ")+bold(packageInfo[1])+red("] ")

	    print_info(red("   ##")+flags+repoinfo+blue(enlightenatom(str(pkgatom))))
	    dbconn.closeDB()

	# show download info
	print_info(red(" @@ ")+blue("Total number of packages:\t")+red(str(len(runQueue))))
	if (ask or verbose or pretend):
	    print_info(red(" @@ ")+green("Packages needing install:\t")+green(str(pkgsToInstall)))
	    print_info(red(" @@ ")+darkgreen("Packages needing reinstall:\t")+darkgreen(str(pkgsToReinstall)))
	    print_info(red(" @@ ")+blue("Packages needing update:\t\t")+blue(str(pkgsToUpdate)))
	    print_info(red(" @@ ")+red("Packages needing downgrade:\t")+red(str(pkgsToDowngrade)))
	print_info(red(" @@ ")+blue("Download size:\t\t\t")+bold(str(bytesIntoHuman(downloadSize))))


    if (ask):
        rc = askquestion("     Would you like to continue with the installation ?")
        if rc == "No":
	    return 0,0
    if (pretend):
	return 0,0
    
    # running tasks
    totalqueue = str(len(runQueue))
    currentqueue = 0
    for packageInfo in runQueue:
	currentqueue += 1
	idpackage = packageInfo[0]
	repository = packageInfo[1]
	# get package atom
	dbconn = openRepositoryDatabase(repository)
	pkgatom = dbconn.retrieveAtom(idpackage)
	dbconn.closeDB()
	#print actionQueue[pkgatom]
	
	# fill steps
	steps = [] # fetch, remove, (preinstall, install postinstall), database, gentoo-sync, cleanup
	# download
	if (actionQueue[pkgatom]['fetch'] < 0):
	    steps.append("fetch")
	
	if (not onlyfetch):
	    # remove old
	    if (actionQueue[pkgatom]['remove'] != -1):
	        steps.append("remove")
	    # install
	    steps.append("install")
	    steps.append("database")
	    steps.append("cleanup")
	
	#print "steps for "+pkgatom+" -> "+str(steps)
	print_info(red(" @@ ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(pkgatom))
	
	for step in steps:
	    rc = stepExecutor(step,actionQueue[pkgatom])
	    if (rc != 0):
		return -1,rc
    return 0,0


def removePackages(packages, ask = False, pretend = False, verbose = False, deps = True):
    
    # check if I am root
    if (not checkRoot()) and (not pretend):
	print_error(red("You must run this function as superuser."))
	return 1,-1
    
    clientDbconn = openClientDatabase()
    
    foundAtoms = []
    for package in packages:
	foundAtoms.append([package,atomMatchInRepository(package,clientDbconn)])

    # filter packages not found
    _foundAtoms = []
    for result in foundAtoms:
	exitcode = result[1][0]
	if (exitcode != -1):
	    _foundAtoms.append(result[1])
	else:
	    print_warning(red("## ATTENTION -> package")+bold(" "+result[0]+" ")+red("is not installed."))

    foundAtoms = _foundAtoms
    
    # are packages in foundAtoms?
    if (len(foundAtoms) == 0):
	print_error(red("No packages found"))
	return 127,-1
    
    print packages
    generateRemovalTree(packages)
    print "not yet implemented"
    return 0,0



'''
    @description: execute the requested step (it is only used by the CLI client)
    @input: 	step -> name of the step to execute
    		infoDict -> dictionary containing all the needed information collected by installPackages() -> actionQueue[pkgatom]
    @output:	-1,"description" for error ; 0,True for no errors
'''
def stepExecutor(step,infoDict):
    output = 0
    if step == "fetch":
	print_info(red("     ## ")+blue("Fetching package: ")+red(os.path.basename(infoDict['download'])))
	output = fetchFile(infoDict['download'],infoDict['checksum'])
	if output != 0:
	    if output == -1:
		errormsg = red("Cannot find the package file online. Try to run: ")+bold("equo repo sync")+red("' and this command again. Error "+str(output))
	    else:
		errormsg = red("Package checksum does not match. Try to run: '")+bold("equo repo sync")+red("' and this command again. Error "+str(output))
	    print_error(errormsg)
	    return output
	# otherwise fetch md5 too
	print_info(red("     ## ")+blue("Fetching package checksum: ")+red(os.path.basename(infoDict['download']+etpConst['packageshashfileext'])))
	output = fetchFile(infoDict['download']+etpConst['packageshashfileext'],False)
	if output != 0:
	    errormsg = red("Cannot find the checksum file online. Try to run: ")+bold("equo repo sync")+red("' and this command again. Error "+str(output))
	    print_error(errormsg)
	    return output
    elif step == "install":
	if (etpConst['gentoo-compat']):
	    print_info(red("     ## ")+blue("Installing package: ")+red(os.path.basename(infoDict['download']))+" ## w/Gentoo compatibility")
	    output = installFile(os.path.basename(infoDict['download']),infoDict)
	else:
	    print_info(red("     ## ")+blue("Installing package: ")+red(os.path.basename(infoDict['download'])))
	    output = installFile(os.path.basename(infoDict['download']))
	if output != 0:
	    errormsg = red("An error occured while trying to install the package. Check if you have enough disk space on your hard disk. Error "+str(output))
	    print_error(errormsg)
	    return output
    elif step == "database":
	print_info(red("     ## ")+blue("Injecting into database: ")+red(os.path.basename(infoDict['download'])))
	output = installPackageIntoDatabase(infoDict['idpackage'],infoDict['repository'])
	if output != 0:
	    errormsg = red("An error occured while trying to add the package to the database. What have you done? Error "+str(output))
	    print_error(errormsg)
	    return output
    
    return output

