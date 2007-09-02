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
from entropyTools import unpackGzip, compareMd5, bytesIntoHuman, convertUnixTimeToHumanTime, askquestion, getRandomNumber, dep_getcpv, isjustname, dep_getkey, compareVersions as entropyCompareVersions, catpkgsplit, filterDuplicatedEntries, extactDuplicatedEntries, isspecific, uncompressTarBz2, extractXpak, filterDuplicatedEntries, applicationLockCheck, countdown, dep_striptag, istagged
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

def syncRepositories(reponames = [], forceUpdate = False, quiet = False):

    # check if I am root
    if (not checkRoot()):
	if (not quiet):
	    print_error(red("\t You must run this application as root."))
	return 1

    # check etpRepositories
    if len(etpRepositories) == 0:
	if (not quiet):
	    print_error(yellow(" * ")+red("No repositories specified in ")+etpConst['repositoriesconf'])
	return 127

    if (not quiet):
        print_info(yellow(" @@ ")+green("Repositories syncronization..."))
    repoNumber = 0
    syncErrors = False
    
    if (reponames == []):
	for x in etpRepositories:
	    reponames.append(x)
    
    for repo in reponames:
	
	repoNumber += 1
	
	if (not quiet):
	    print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
	    print_info(red("\tDatabase URL: ")+green(etpRepositories[repo]['database']))
	    print_info(red("\tDatabase local path: ")+green(etpRepositories[repo]['dbpath']))
	
	# check if database is already updated to the latest revision
	onlinestatus = getOnlineRepositoryRevision(repo)
	if (onlinestatus != -1):
	    localstatus = getRepositoryRevision(repo)
	    if (localstatus == onlinestatus) and (forceUpdate == False):
		if (not quiet):
		    print_info(bold("\tAttention: ")+red("database is already up to date."))
		continue
	
	# get database lock
	rc = downloadData(etpRepositories[repo]['database']+"/"+etpConst['etpdatabasedownloadlockfile'],"/dev/null")
	if rc != "-3": # cannot download database
	    if (not quiet):
	        print_error(bold("\tATTENTION -> ")+red("repository is being updated. Try again in few minutes."))
	    syncErrors = True
	    continue
	
	# starting to download
	if (not quiet):
	    print_info(red("\tDownloading database ")+green(etpConst['etpdatabasefilegzip'])+red(" ..."))
	# create dir if it doesn't exist
	if not os.path.isdir(etpRepositories[repo]['dbpath']):
	    if (not quiet):
	        print_info(red("\t\tCreating database directory..."))
	    os.makedirs(etpRepositories[repo]['dbpath'])
	# download
	downloadData(etpRepositories[repo]['database']+"/"+etpConst['etpdatabasefilegzip'],etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefilegzip'])
	
	if (not quiet):
	    print_info(red("\tUnpacking database to ")+green(etpConst['etpdatabasefile'])+red(" ..."))
	unpackGzip(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefilegzip'])
	# download etpdatabasehashfile
	if (not quiet):
	    print_info(red("\tDownloading checksum ")+green(etpConst['etpdatabasehashfile'])+red(" ..."))
	downloadData(etpRepositories[repo]['database']+"/"+etpConst['etpdatabasehashfile'],etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'])
	# checking checksum
	if (not quiet):
	    print_info(red("\tChecking downloaded database ")+green(etpConst['etpdatabasefile'])+red(" ..."), back = True)
	f = open(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
	md5hash = f.readline().strip()
	md5hash = md5hash.split()[0]
	f.close()
	rc = compareMd5(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefile'],md5hash)
	if rc:
	    if (not quiet):
	        print_info(red("\tDownloaded database status: ")+bold("OK"))
	else:
	    if (not quiet):
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
	if (not quiet):
	    print_info(red("\tDownloading revision ")+green(etpConst['etpdatabaserevisionfile'])+red(" ..."))
	downloadData(etpRepositories[repo]['database']+"/"+etpConst['etpdatabaserevisionfile'],etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'])
	
	if (not quiet):
	    print_info(red("\tUpdated repository revision: ")+bold(str(getRepositoryRevision(repo))))
	print_info(yellow("\tUpdate completed"))

    if syncErrors:
	if (not quiet):
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
	    cats = []
	    for result in results:
		idpackage = result[1]
		cat = dbconn.retrieveCategory(idpackage)
		cats.append(cat)
		if (cat == pkgcat):
		    foundCat = cat
		    break
	    # if categories are the same...
	    if (not foundCat) and (len(cats) > 0):
		cats = filterDuplicatedEntries(cats)
		if len(cats) == 1:
		    foundCat = cats[0]
	    if (not foundCat) and (pkgcat == "null"):
		# got the issue
		# gosh, return and complain
		atomMatchInRepositoryCache[atom] = {}
		atomMatchInRepositoryCache[atom]['dbconn'] = dbconn
		atomMatchInRepositoryCache[atom]['result'] = -1,2
		return -1,2
	
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
	if (direction) or (direction == '' and not justname) or (direction == '' and not justname and strippedAtom.endswith("*")):
	    # check if direction is used with justname, in this case, return an error
	    if (justname):
		#print "justname"
		atomMatchInRepositoryCache[atom] = {}
		atomMatchInRepositoryCache[atom]['dbconn'] = dbconn
		atomMatchInRepositoryCache[atom]['result'] = -1,3
		return -1,3 # error, cannot use directions when not specifying version
	    
	    if (direction == "~") or (direction == "=") or (direction == '' and not justname) or (direction == '' and not justname and strippedAtom.endswith("*")): # any revision within the version specified OR the specified version
		
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

    #print atom

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
		    #print duplicatedRevisions
		    try:
			duplicatedRevisions.index(newerRevision)
			needFiltering = True
		    except:
			needFiltering = False
		
		    if (needFiltering):
			# ok, we must get the repository with the biggest priority
			#print "d'oh"
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
	raise Exception, "getDependencies: I need a list with two values in it."
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
def filterSatisfiedDependencies(dependencies):

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
		
		#xdb = openRepositoryDatabase(repo_test_rc[1])
		#print xdb.retrieveAtom(repo_test_rc[0])
		#xdb.closeDB()

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
		#print repo_pkgver+"<-->"+installedVer
		#print cmp
		if cmp != 0:
		    #print dependency
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
   @output: dependency tree dictionary, plus status code
'''
def generateDependencyTree(atomInfo, emptydeps = False):

    treecache = {}
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
		    while 1: remainingDeps.remove(undep) # FIXME: use sets
		except:
		    pass
	    else:

		# found, get its deps
		mydeps = getDependencies(atom)
		#print mydeps
		if (not emptydeps):
		    mydeps, xxx = filterSatisfiedDependencies(mydeps)
		for dep in mydeps:
		    remainingDeps.append(dep)
		xmatch = atomMatchInRepository(undep,clientDbconn)
		if (not emptydeps): # FIXME: fix emptydeps - must do something useful
		    if xmatch[0] == -1: # if dependency is not installed
		        tree[treedepth].append(undep)
		    else: # if it's installed, check if the version is ok
			unsatisfied, satisfied = filterSatisfiedDependencies([undep])
			if (unsatisfied):
			    tree[treedepth].append(undep)
		else:
		    tree[treedepth].append(undep)
		treecache[undep] = True
		try:
		    while 1: remainingDeps.remove(undep) # FIXME: use sets
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
   @description: generates a depends tree using provided idpackages (from client database)
   		 !!! you can see it as the function that generates the removal tree
   @input package: idpackages list
   @output: 	depends tree dictionary, plus status code
'''
def generateDependsTree(idpackages, dbconn = None):

    dependscache = {}
    closedb = False
    
    # database istance is passed?
    if dbconn == None:
	closedb = True
        clientDbconn = openClientDatabase()
    else:
	clientDbconn = dbconn

    dependsOk = False
    treeview = set(idpackages)
    treelevel = idpackages[:]
    tree = {}
    treedepth = 0 # I start from level 1 because level 0 is idpackages itself
    tree[treedepth] = idpackages[:]
    monotree = set(idpackages[:]) # monodimensional tree
    
    # check if dependstable is sane before beginning
    rx = clientDbconn.searchDepends(idpackages[0])
    if rx == -2:
	# generation needed
	regenerateDependsTable(clientDbconn, output = False)
    
    while (not dependsOk):
	treedepth += 1
	tree[treedepth] = set([])
        for idpackage in treelevel:

	    passed = dependscache.get(idpackage,None)
	    systempkg = clientDbconn.isSystemPackage(idpackage)
	    if passed or systempkg:
		try:
		    while 1: treeview.remove(idpackage)
		except:
		    pass
		continue

	    # obtain its depends
	    depends = clientDbconn.searchDepends(idpackage)
	    # filter already satisfied ones
	    depends = [x for x in depends if x not in list(monotree)]
	    if (depends): # something depends on idpackage
		for x in depends:
		    if x not in tree[treedepth]:
			tree[treedepth].add(x)
			monotree.add(x)
		        treeview.add(x)
	    else: # if no depends found, grab its dependencies and check
		
	        mydeps = set(clientDbconn.retrieveDependencies(idpackage))
		_mydeps = set([])
		for x in mydeps:
		    match = atomMatchInRepository(x,clientDbconn)
		    if match and match[1] == 0:
		        _mydeps.add(match[0])
		mydeps = _mydeps
		# now filter them
		mydeps = [x for x in mydeps if x not in list(monotree)]
		for x in mydeps:
		    #print clientDbconn.retrieveAtom(x)
		    mydepends = clientDbconn.searchDepends(x)
		    mydepends = [y for y in mydepends if y not in list(monotree)]
		    if (not mydepends):
			tree[treedepth].add(x)
			monotree.add(x)
			treeview.add(x)

	    dependscache[idpackage] = True
	    try:
		while 1: treeview.remove(idpackage)
	    except:
	        pass
	
	treelevel = list(treeview)[:]
	if (not treelevel):
	    if not tree[treedepth]:
		del tree[treedepth] # probably the last one is empty then
	    dependsOk = True

    newtree = tree.copy() # tree list
    if (tree):
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
    if closedb:
        clientDbconn.closeDB()
    return newtree,0 # treeview is used to show deps while tree is used to run the dependency code.


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
    if os.path.isfile(etpConst['entropyworkdir']+"/"+filepath):
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
   @description: remove files installed by idpackage from the client database
   @input int(idpackage): idpackage from client database
   @input clientDbconn: an already opened database connection (to the client one)
   @input newContent: if this function is called by installFile, newContent will contain the new package list and a differential removal will be run instead
   @output: 0 = all fine, >0 = error!
'''
def removeFile(idpackage, clientDbconn = None, newContent = []):
    import shutil
    closedb = False
    if (clientDbconn == None):
	closedb = True
	clientDbconn = openClientDatabase()
    content = clientDbconn.retrieveContent(idpackage)

    if (newContent):
	# doing a diff removal
	content = [x for x in content if x not in newContent]
	#print content

    # Handle gentoo database
    if (etpConst['gentoo-compat']):
	gentooAtom = clientDbconn.retrieveCategory(idpackage)+"/"+clientDbconn.retrieveName(idpackage)+"-"+clientDbconn.retrieveVersion(idpackage)
	removePackageFromGentooDatabase(gentooAtom)

    if (closedb):
	clientDbconn.closeDB()

    # merge data into system
    for file in content:
	file = file.encode(sys.getfilesystemencoding())
	try:
	    os.remove(file)
	    #print file
	except OSError:
	    try:
		os.removedirs(file) # is it a dir?, empty?
	        #print "debug: was a dir"
	    except:
		#print "debug: the dir wasn't empty? -> "+str(file)
		pass

    return 0


'''
   @description: unpack the given file on the system and also update gentoo db if requested
   @input package: package file (without path)
   @output: 0 = all fine, >0 = error!
'''
def installFile(infoDict, clientDbconn = None):
    import shutil
    package = os.path.basename(infoDict['download'])
    removePackage = infoDict['remove']

    closedb = False
    if (clientDbconn == None):
	closedb = True
	clientDbconn = openClientDatabase()
    
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
    
    packageContent = []
    
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
		# this also handles symlinks
		shutil.move(fromfile,tofile)
		packageContent.append(tofile)
	    except IOError,(errno,strerror):
		if errno == 2:
		    # better to pass away, sometimes gentoo packages are fucked up and contain broken things
		    pass
		else:
		    rc = os.system("mv "+fromfile+" "+tofile)
		    if (rc != 0):
		        return 4
		    packageContent.append(tofile)
	    try:
	        user = os.stat(fromfile)[4]
	        group = os.stat(fromfile)[5]
	        os.chown(tofile,user,group)
	        shutil.copystat(fromfile,tofile)
	    except:
		pass # sometimes, gentoo packages are fucked up and contain broken symlinks

    shutil.rmtree(imageDir,True) # rm and ignore errors
    
    if (removePackage != -1):
	# doing a diff removal
	if (etpConst['gentoo-compat']):
	    print_info(red("   ## ")+blue("Cleaning old package files...")+" ## w/Gentoo compatibility")
	else:
	    print_info(red("   ## ")+blue("Cleaning old package files..."))
	removeFile(removePackage, clientDbconn, packageContent)

    if (closedb):
	clientDbconn.closeDB()

    if (etpConst['gentoo-compat']):
	rc = installPackageIntoGentooDatabase(infoDict,unpackDir+etpConst['packagecontentdir']+"/"+package)
	if (rc >= 0):
	    shutil.rmtree(unpackDir,True)
	    return rc
    
    # remove unpack dir
    shutil.rmtree(unpackDir,True)
    return 0

'''
   @description: remove package entry from Gentoo database
   @input gentoo package atom (cat/name+ver):
   @output: 0 = all fine, <0 = error!
'''
def removePackageFromGentooDatabase(atom):

    if (isjustname(atom)):
	return -2

    # handle gentoo-compat
    import shutil
    _portage_avail = False
    try:
	from portageTools import getPortageAppDbPath as _portage_getPortageAppDbPath, getInstalledAtoms as _portage_getInstalledAtoms
	_portage_avail = True
    except:
	return -1 # no Portage support
    
    if (_portage_avail):
	portDbDir = _portage_getPortageAppDbPath()
	removePath = portDbDir+atom
	#print removePath
	try:
	    shutil.rmtree(removePath,True)
	except:
	    pass
	key = dep_getkey(atom)
	othersInstalled = _portage_getInstalledAtoms(key)
	if othersInstalled == None:
	    # safest way (error free) is to use sed without loading the file
	    # escape /
	    skippedKey = ''
	    for x in key:
		if x == "/":
		    x = "\/"
		skippedKey += x
	    os.system("sed -i '/"+skippedKey+"/d' /var/lib/portage/world")

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
   @description: injects package info into the installed packages database
   @input int(idpackage): idpackage matched into repository
   @input str(repository): name of the repository where idpackage is
   @input pointer(clientDbconn): client database connection pointer (optional)
   @output: 0 = all fine, >0 = error!
'''
def installPackageIntoDatabase(idpackage, repository, clientDbconn = None):
    # fetch info
    dbconn = openRepositoryDatabase(repository)
    data = dbconn.getPackageData(idpackage)
    # get current revision
    rev = dbconn.retrieveRevision(idpackage)
    branch = dbconn.retrieveBranch(idpackage)
    dbconn.closeDB()
    
    exitstatus = 0
    
    # inject
    closedb = False
    if clientDbconn == None:
	closedb = True
	clientDbconn = openClientDatabase()
    idpk, rev, x, status = clientDbconn.handlePackage(etpData = data, forcedRevision = rev, forcedBranch = True, addBranch = False)
    del x
    if (not status):
	clientDbconn.closeDB()
	print "DEBUG!!! Package "+str(idpk)+" has not been inserted, status: "+str(status)
	exitstatus = 1 # it hasn't been insterted ? why??
    else:
        # add idpk to the installedtable
        clientDbconn.removePackageFromInstalledTable(idpk)
        clientDbconn.addPackageToInstalledTable(idpk,repository)
    
    if (closedb):
        clientDbconn.closeDB()
    return exitstatus

'''
   @description: remove the package from the installed packages database..
   		 This function is a wrapper around databaseTools.removePackage that will let us to add our custom things
   @input int(idpackage): idpackage matched into repository
   @input pointer(clientDbconn): client database connection pointer (optional)
   @output: 0 = all fine, >0 = error!
'''
def removePackageFromDatabase(idpackage, clientDbconn = None):
    
    closedb = False
    if clientDbconn == None:
	closedb = True
	clientDbconn = openClientDatabase()

    clientDbconn.removePackage(idpackage)
    # also remove from dependstable
    x = clientDbconn.removePackageFromDependsTable(idpackage)
    if (x == 1): #`shit, needs regeneration
	regenerateDependsTable(clientDbconn, output = False)
    
    if (closedb):
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
	rc = searchRemoval(myopts[1:], quiet = equoRequestQuiet)

    elif options[0] == "orphans":
	rc = searchOrphans(quiet = equoRequestQuiet)

    elif options[0] == "description":
	rc = searchDescription(myopts[1:], quiet = equoRequestQuiet)

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
    equoRequestQuiet = False
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
	elif (opt == "--quiet"):
	    equoRequestQuiet = True
	elif (opt == "--fetch"):
	    equoRequestOnlyFetch = True
	else:
	    _myopts.append(opt)
    myopts = _myopts

    if (options[0] == "search"):
	if len(myopts) > 0:
	    rc = searchPackage(myopts)

    elif (options[0] == "deptest"):
	rc, garbage = dependenciesTest(quiet = equoRequestQuiet, ask = equoRequestAsk, pretend = equoRequestPretend)

    elif (options[0] == "install"):
	if len(myopts) > 0:
	    rc, status = installPackages(myopts, ask = equoRequestAsk, pretend = equoRequestPretend, verbose = equoRequestVerbose, deps = equoRequestDeps, emptydeps = equoRequestEmptyDeps, onlyfetch = equoRequestOnlyFetch)
	else:
	    print_error(red(" Nothing to do."))
	    rc = 127

    elif (options[0] == "world"):
	rc, status = worldUpdate(ask = equoRequestAsk, pretend = equoRequestPretend, verbose = equoRequestVerbose, onlyfetch = equoRequestOnlyFetch)

    elif (options[0] == "remove"):
	if len(myopts) > 0:
	    rc, status = removePackages(myopts, ask = equoRequestAsk, pretend = equoRequestPretend, verbose = equoRequestVerbose, deps = equoRequestDeps)
	else:
	    print_error(red(" Nothing to do."))
	    rc = 127

    return rc


def database(options):

    databaseExactMatch = False
    _options = []
    for opt in options:
	if opt == "--exact": # removed
	    databaseExactMatch = True
	else:
	    _options.append(opt)
    options = _options

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
	    data = atomMatch("~"+portagePackage)
	    if (data[0] != -1):
	        foundPackages.append(data)
		missingPackages.remove(portagePackage)
	
	notmatchingstatus = ''
	if len(missingPackages) > 0:
	    f = open("/tmp/equo-not-matching.txt","w")
	    for x in missingPackages:
		f.write(x+"\n")
	    f.flush()
	    f.close()
	    notmatchingstatus = " [wrote: /tmp/equo-not-matching.txt]"
	    
	
	print_info(red("  ### Packages matching: ")+bold(str(len(foundPackages))))
	print_info(red("  ### Packages not matching: ")+bold(str(len(missingPackages)))+notmatchingstatus)
	
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
	    # fill client database
	    idpk, rev, xx, status = clientDbconn.addPackage(atomInfo, wantedBranch = atomBranch, addBranch = False)
	    # now add the package to the installed table
	    clientDbconn.addPackageToInstalledTable(idpk,x[1])

	print_info(red("  Now generating depends caching table..."))
	regenerateDependsTable(clientDbconn)
	print_info(red("  Database reinitialized successfully."))

	clientDbconn.closeDB()

    elif (options[0] == "depends"):
	print_info(red("  Regenerating depends caching table..."))
	clientDbconn = openClientDatabase()
	regenerateDependsTable(clientDbconn)
	clientDbconn.closeDB()
	print_info(red("  Depends caching table regenerated successfully."))


def printPackageInfo(idpackage,dbconn, clientSearch = False, strictOutput = False, quiet = False):
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
		    printPackageInfo(idpackage,clientDbconn, clientSearch = True, quiet = quiet)
	
    clientDbconn.closeDB()

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
	
    clientDbconn.closeDB()

    if (idreturn):
	return dataInfo
    
    return 0


def searchDepends(atoms, idreturn = False, verbose = False, quiet = False):
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Depends Search..."))

    clientDbconn = openClientDatabase()

    dataInfo = [] # when idreturn is True
    for atom in atoms:
	result = atomMatchInRepository(atom,clientDbconn)
	matchInRepo = False
	if (result[0] == -1):
	    matchInRepo = True
	    result = atomMatch(atom)
	if (result[0] != -1):
	    if (matchInRepo):
	        dbconn = openRepositoryDatabase(result[1])
	    else:
		dbconn = clientDbconn
	    searchResults = dbconn.searchDepends(result[0])
	    if searchResults == -2:
		if (matchInRepo):
		    # run equo update
		    dbconn.closeDB()
		    syncRepositories([result[1]], forceUpdate = True)
		    dbconn = openRepositoryDatabase(result[1])
		else:
		    # I need to generate dependstable
		    regenerateDependsTable(dbconn)
	        searchResults = dbconn.searchDepends(result[0])
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
	
	if (matchInRepo):
	    dbconn.closeDB()

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

def searchOrphans(quiet = False):

    if (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Orphans Search..."))

    # start to list all files on the system:
    dirs = etpConst['filesystemdirs']
    foundFiles = set([])
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
	_content = set([])
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
	

def searchRemoval(atoms, idreturn = False, quiet = False):
    
    if (not idreturn) and (not quiet):
        print_info(yellow(" @@ ")+darkgreen("Removal Search..."))

    clientDbconn = openClientDatabase()
    foundAtoms = []
    for atom in atoms:
	match = atomMatchInRepository(atom,clientDbconn)
	if match[1] == 0:
	    foundAtoms.append(match[0])

    # are packages in foundAtoms?
    if (len(foundAtoms) == 0):
	print_error(red("No packages found."))
	return 127,-1

    choosenRemovalQueue = []
    if (not quiet):
        print_info(red(" @@ ")+blue("Calculating removal dependencies, please wait..."), back = True)
    treeview = generateDependsTree(foundAtoms,clientDbconn)
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


'''
   @description: recreate dependstable table in the chosen database, it's used for caching searchDepends requests
   @input Nothing
   @output: Nothing
'''
def regenerateDependsTable(dbconn, output = True):
    dbconn.createDependsTable()
    depends = dbconn.listAllDependencies()
    count = 0
    total = str(len(depends))
    for depend in depends:
	count += 1
	atom = depend[1]
	iddep = depend[0]
	if output:
	    print_info("  "+bold("(")+darkgreen(str(count))+"/"+blue(total)+bold(")")+red(" Resolving ")+bold(atom), back = True)
	match = atomMatchInRepository(atom,dbconn)
	if (match[0] != -1):
	    dbconn.addDependRelationToDependsTable(iddep,match[0])

    # now validate dependstable
    dbconn.sanitizeDependsTable()

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


def worldUpdate(ask = False, pretend = False, verbose = False, onlyfetch = False):

    # check if I am root
    if (not checkRoot()) and (not pretend):
	print_error(red("You must run this function as superuser."))
	return 1,-1

    # FIXME: handle version upgrades
    
    updateList = []
    syncRepositories()
    
    clientDbconn = openClientDatabase()
    # get all the installed packages
    # FIXME: add branch support
    packages = clientDbconn.listAllPackages()
    for package in packages:
	atom = package[0]
	idpackage = package[1]
	branch = package[2]
	name = clientDbconn.retrieveName(idpackage)
	category = clientDbconn.retrieveCategory(idpackage)
	atomkey = category+"/"+name
	# search in the packages
	match = atomMatch(atom)
	print "here's the list of the packages that would be updated"
	if match[0] == -1:
	    print atom
	    updateList.append(match)
    print "not implemented yet"
    return 0,0

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
	    print_warning(red("## ATTENTION: no match for ")+bold(" "+result[0]+" ")+red(" in database. If you omitted the category, try adding it."))

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
    
        if (deps):
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
    onDiskSize = 0
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
	    onDiskSize += dbconn.retrieveOnDiskSize(packageInfo[0])
	    
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
			    actionQueue[pkgatom]['removeatom'] = clientDbconn.retrieveAtom(idx)
		            break
	        clientDbconn.closeDB()

	    if not (ask or pretend or verbose):
		continue

	    flags = " ["
	    cmp = compareVersions([pkgver,pkgtag,pkgrev],[installedVer,installedTag,installedRev])
	    if (cmp == 0):
		pkgsToReinstall += 1
		actionQueue[pkgatom]['remove'] = -1 # disable removal, not needed
	        flags += red("R")
	    elif (cmp > 0):
	        if (installedVer == "0"):
		    pkgsToInstall += 1
		    actionQueue[pkgatom]['remove'] = -1 # disable removal, not needed
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
	print_info(red(" @@ ")+blue("Used disk space:\t\t\t")+bold(str(bytesIntoHuman(onDiskSize))))


    if (ask):
        rc = askquestion("     Would you like to continue with the installation ?")
        if rc == "No":
	    return 0,0
    if (pretend):
	return 0,0
    
    # running tasks
    totalqueue = str(len(runQueue))
    currentqueue = 0
    clientDbconn = openClientDatabase()
    
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
	    # install
	    steps.append("install")
	    steps.append("installdatabase")
	    steps.append("cleanup")
	
	#print "steps for "+pkgatom+" -> "+str(steps)
	print_info(red(" @@ ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(pkgatom))
	
	for step in steps:
	    rc = stepExecutor(step,actionQueue[pkgatom],clientDbconn)
	    if (rc != 0):
		clientDbconn.closeDB()
		return -1,rc

    # regenerate depends table
    print_info(red(" @@ ")+blue("Regenerating depends caching table..."), back = True)
    regenerateDependsTable(clientDbconn, output = False)
    print_info(red(" @@ ")+blue("Install Complete."))

    clientDbconn.closeDB()

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

    plainRemovalQueue = []
    
    lookForOrphanedPackages = True
    # now print the selected packages
    print_info(red(" @@ ")+blue("These are the chosen packages:"))
    totalatoms = len(foundAtoms)
    atomscounter = 0
    for atomInfo in foundAtoms:
	atomscounter += 1
	idpackage = atomInfo[0]
	systemPackage = clientDbconn.isSystemPackage(idpackage)

	# get needed info
	pkgatom = clientDbconn.retrieveAtom(idpackage)
	pkgver = clientDbconn.retrieveVersion(idpackage)
	pkgtag = clientDbconn.retrieveVersionTag(idpackage)
	if not pkgtag:
	    pkgtag = "NoTag"
	pkgrev = clientDbconn.retrieveRevision(idpackage)
	#pkgslot = clientDbconn.retrieveSlot(idpackage)
	installedfrom = clientDbconn.retrievePackageFromInstalledTable(idpackage)

	if (systemPackage):
	    print_warning(darkred("   # !!! ")+red("(")+bold(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+bold(pkgatom)+red(" is a vital package. Removal forbidden."))
	    continue
	plainRemovalQueue.append(idpackage)
	
	print_info("   # "+red("(")+bold(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+bold(pkgatom)+" | Installed from: "+red(installedfrom))
	print_info("\t"+red("Versioning:\t")+" "+red(pkgver)+" / "+blue(pkgtag)+" / "+(str(pkgrev)))

    if (verbose or ask or pretend):
        print_info(red(" @@ ")+blue("Number of packages: ")+str(totalatoms))
    
    if (ask):
        rc = askquestion("     Would you like to look for packages that can be removed along with the selected above?")
        if rc == "No":
	    lookForOrphanedPackages = False


    if (not plainRemovalQueue):
	print_error(red("Nothing to do."))
	return 127,-1

    removalQueue = []
    
    if (lookForOrphanedPackages):
	choosenRemovalQueue = []
	print_info(red(" @@ ")+blue("Calculating removal dependencies, please wait..."), back = True)
	treeview = generateDependsTree(plainRemovalQueue, clientDbconn)
	treelength = len(treeview[0])
	if treelength > 1:
	    treeview = treeview[0]
	    for x in range(treelength)[::-1]:
		for y in treeview[x]:
		    choosenRemovalQueue.append(y)
	
	    if (choosenRemovalQueue):
	        print_info(red(" @@ ")+blue("These are the packages that would added to the removal queue:"))
	        totalatoms = str(len(choosenRemovalQueue))
	        atomscounter = 0
	    
	        for idpackage in choosenRemovalQueue:
	            atomscounter += 1
	            rematom = clientDbconn.retrieveAtom(idpackage)
	            installedfrom = clientDbconn.retrievePackageFromInstalledTable(idpackage)
		    repositoryInfo = bold("[")+red("from: ")+brown(installedfrom)+bold("]")
		    stratomscounter = str(atomscounter)
		    while len(stratomscounter) < len(totalatoms):
			stratomscounter = " "+stratomscounter
	            print_info("   # "+red("(")+bold(stratomscounter)+"/"+blue(str(totalatoms))+red(")")+repositoryInfo+" "+blue(rematom))
	    
                if (ask):
                    rc = askquestion("     Would you like to add these packages to the removal queue?")
                    if rc != "No":
			print_info(red(" @@ ")+blue("Removal Queue updated."))
	                for x in choosenRemovalQueue:
			    removalQueue.append(x)
		else:
	            for x in choosenRemovalQueue:
			removalQueue.append(x)

    if (ask):
	print
        rc = askquestion("     I am going to start the removal. Are you sure?")
        if rc == "No":
	    clientDbconn.closeDB()
	    return 0,0
    else:
	countdown(what = red(" @@ ")+blue("Starting removal in "),back = True)
	

    for idpackage in plainRemovalQueue:
	removalQueue.append(idpackage)
    
    for idpackage in removalQueue:
	infoDict = {}
	infoDict['remove'] = idpackage
	steps = []
	steps.append("preremove") # not implemented
	steps.append("remove")
	steps.append("removedatabase")
	steps.append("postremove") # not implemented
	for step in steps:
	    rc = stepExecutor(step,infoDict,clientDbconn)
	    if (rc != 0):
		clientDbconn.closeDB()
		return -1,rc
    
    print_info(red(" @@ ")+blue("All done."))
    
    clientDbconn.closeDB()
    return 0,0


def dependenciesTest(quiet = False, ask = False, pretend = False):
    
    if (not quiet):
        print_info(red(" @@ ")+blue("Running dependency test..."))
    
    clientDbconn = openClientDatabase()
    # get all the installed packages
    installedPackages = clientDbconn.listAllIdpackages()
    
    depsNotFound = {}
    depsNotSatisfied = {}
    # now look
    length = str((len(installedPackages)))
    count = 0
    for xidpackage in installedPackages:
	count += 1
	atom = clientDbconn.retrieveAtom(xidpackage)
	if (not quiet):
	    print_info(darkred(" @@ ")+bold("(")+blue(str(count))+"/"+red(length)+bold(")")+darkgreen(" Checking ")+bold(atom), back = True)
	deptree, status = generateDependencyTree([xidpackage,0])

	if (status == 0):
	    depsNotSatisfied[xidpackage] = []
	    for x in range(len(deptree))[::-1]:
	        for z in deptree[x]:
		    depsNotSatisfied[xidpackage].append(z)
	    if (not depsNotSatisfied[xidpackage]):
		del depsNotSatisfied[xidpackage]
	
    packagesNeeded = []
    if (depsNotSatisfied):
        if (not quiet):
            print_info(red(" @@ ")+blue("These are the packages that lack dependencies: "))
	for dict in depsNotSatisfied:
	    pkgatom = clientDbconn.retrieveAtom(dict)
	    if (not quiet):
	        print_info(darkred("   ### ")+blue(pkgatom))
	    for dep in depsNotSatisfied[dict]:
		iddep = dep[0]
		repo = dep[1]
		dbconn = openRepositoryDatabase(repo)
		depatom = dbconn.retrieveAtom(iddep)
		dbconn.closeDB()
		if (not quiet):
		    print_info(bold("       :: ")+red(depatom))
		else:
		    print depatom
		packagesNeeded.append([depatom,dep])

    if (pretend):
	clientDbconn.closeDB()
	return 0, packagesNeeded

    if (packagesNeeded) and (not quiet):
        if (ask):
            rc = askquestion("     Would you like to install them?")
            if rc == "No":
		clientDbconn.closeDB()
	        return 0,packagesNeeded
	else:
	    print_info(red(" @@ ")+blue("Installing dependencies in ")+red("10 seconds")+blue("..."))
	    time.sleep(10)
	# install them
	packages = []
	for dep in packagesNeeded:
	    packages.append(dep[0])
	
	# check for equo.pid
	packages = filterDuplicatedEntries(packages)
	applicationLockCheck("install")
	installPackages(packages, deps = False, ask = ask)
	    

    print_info(red(" @@ ")+blue("All done."))
    clientDbconn.closeDB()
    return 0,packagesNeeded

'''
    @description: execute the requested step (it is only used by the CLI client)
    @input: 	step -> name of the step to execute
    		infoDict -> dictionary containing all the needed information collected by installPackages() -> actionQueue[pkgatom]
    @output:	-1,"description" for error ; 0,True for no errors
'''
def stepExecutor(step,infoDict, clientDbconn = None):

    closedb = False
    if clientDbconn == None:
	closedb = True
	clientDbconn = openClientDatabase()

    output = 0
    if step == "fetch":
	print_info(red("   ## ")+blue("Fetching package: ")+red(os.path.basename(infoDict['download'])))
	output = fetchFile(infoDict['download'],infoDict['checksum'])
	if output != 0:
	    if output == -1:
		errormsg = red("Cannot find the package file online. Try to run: ")+bold("equo repo sync")+red("' and this command again. Error "+str(output))
	    else:
		errormsg = red("Package checksum does not match. Try to run: '")+bold("equo repo sync")+red("' and this command again. Error "+str(output))
	    print_error(errormsg)
    elif step == "install":
	if (etpConst['gentoo-compat']):
	    print_info(red("   ## ")+blue("Installing package: ")+red(os.path.basename(infoDict['download']))+" ## w/Gentoo compatibility")
	else:
	    print_info(red("   ## ")+blue("Installing package: ")+red(os.path.basename(infoDict['download'])))
	output = installFile(infoDict, clientDbconn)
	if output != 0:
	    errormsg = red("An error occured while trying to install the package. Check if you have enough disk space on your hard disk. Error "+str(output))
	    print_error(errormsg)
    elif step == "remove":
	if (etpConst['gentoo-compat']):
	    print_info(red("   ## ")+blue("Removing installed package: ")+red(clientDbconn.retrieveAtom(infoDict['remove']))+" ## w/Gentoo compatibility")
	    output = removeFile(infoDict['remove'],clientDbconn)
	else:
	    print_info(red("   ## ")+blue("Removing installed package: ")+red(clientDbconn.retrieveAtom(infoDict['remove'])))
	    output = removeFile(infoDict['remove'],clientDbconn)
	if output != 0:
	    errormsg = red("An error occured while trying to remove the package. Check if you have enough disk space on your hard disk. Error "+str(output))
	    print_error(errormsg)
    elif step == "installdatabase":
	print_info(red("   ## ")+blue("Injecting into database: ")+red(infoDict['atom']))
	output = installPackageIntoDatabase(infoDict['idpackage'], infoDict['repository'], clientDbconn)
	if output != 0:
	    errormsg = red("An error occured while trying to add the package to the database. What have you done? Error "+str(output))
	    print_error(errormsg)
    elif step == "removedatabase":
	print_info(red("   ## ")+blue("Removing from database: ")+red(infoDict['removeatom']))
	output = removePackageFromDatabase(infoDict['remove'], clientDbconn)
	if output != 0:
	    errormsg = red("An error occured while trying to remove the package from database. What have you done? Error "+str(output))
	    print_error(errormsg)
    
    if (closedb):
	clientDbconn.closeDB()
    
    return output

