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
from clientConstants import *
from outputTools import *
from remoteTools import downloadData
from entropyTools import unpackGzip, compareMd5, bytesIntoHuman, convertUnixTimeToHumanTime, askquestion, getRandomNumber, dep_getcpv, isjustname, dep_getkey, compareVersions, catpkgsplit, filterDuplicatedEntries, extactDuplicatedEntries, isspecific
from databaseTools import etpDatabase

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
def atomMatchInRepository(atom,dbconn):
    
    # check for direction
    strippedAtom = dep_getcpv(atom)
    if atom.endswith("*"):
	strippedAtom += "*"
    direction = atom[0:len(atom)-len(strippedAtom)]
    #print direction

    #print strippedAtom
    #print isspecific(strippedAtom)
    #print strippedAtom
    
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
	results = dbconn.searchPackagesInBranchByName(pkgname,etpConst['branches'][idx])
	
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
	    #print "results == 1"
	    foundIDs.append(results[0])
	    break

    if (foundIDs):
	# now we have to handle direction
	if (direction):
	    # check if direction is used with justname, in this case, return an error
	    if (justname):
		#print "justname"
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
		#print newerPackage[1]
		return newerPackage[0],0
	
	    elif (direction.find(">") != -1) or (direction.find("<") != -1): # any revision within the version specified
		
		#print direction+" direction"
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
		#print newerPackage[1]
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
	    
	    if (len(similarPackages) > 1):
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
   @description: matches the package that user chose, using atomMatchInRepository searching in all available repositories.
   @input atom: user choosen package name
   @output: the matched selection, list: [package id,repository name] | if nothing found, returns: [ -1,1 ]
   @ exit errors:
	    -1 => repository cannot be fetched online
'''
def atomMatch(atom):
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
	dbfile = etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefile']
	dbconn = etpDatabase(readOnly = True, dbFile = dbfile)
	
	# search
	query = atomMatchInRepository(atom,dbconn)
	if query[1] == 0:
	    # package found, add to our dictionary
	    repoResults[repo] = query[0]
	
	dbconn.closeDB()

    # handle repoResults
    packageInformation = {}
    
    # nothing found
    if len(repoResults) == 0:
	return -1,1
    
    elif len(repoResults) == 1:
	# one result found
	for repo in repoResults:
	    return repoResults[repo],repo
    
    elif len(repoResults) > 1:
	# we have to decide which version should be taken
	
	# get package information for all the entries
	for repo in repoResults:
	    
	    # open database
	    dbfile = etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefile']
	    dbconn = etpDatabase(readOnly = True, dbFile = dbfile)
	
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
				    return [repoResults[repo],repo]
		    
		    else:
			# we are done!!!
		        reponame = ''
			#print conflictingTags
		        for x in conflictingTags:
		            if str(conflictingTags[x]['revision']) == str(newerRevision):
			        reponame = x
			        break
		        return repoResults[reponame],reponame
		
		else:
		    # we're finally done
		    reponame = ''
		    for x in conflictingEntries:
		        if conflictingEntries[x]['versiontag'] == newerTag:
			    reponame = x
			    break
		    return repoResults[reponame],reponame

	    else:
		# we are fine, the newerVersion is not one of the duplicated ones
		reponame = ''
		for x in packageInformation:
		    if packageInformation[x]['version'] == newerVersion:
			reponame = x
			break
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
   @input packageInfo: list composed by int(id) and str(repository name)
   @output: ordered dependency list
'''
def getDependencies(packageInfo):
    if len(packageInfo) != 2:
	raise Exception, "getDependencies: I need a list with two values in it." # bad bad bad bad
    idpackage = packageInfo[0]
    reponame = packageInfo[1]
    dbfile = etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasefile']
    dbconn = etpDatabase(readOnly = True, noUpload = True, dbFile = dbfile)
    
    # retrieve dependencies
    depend = dbconn.retrieveDependencies(idpackage)
    rundepend = dbconn.retrieveRunDependencies(idpackage)
    
    # filter |or| entries
    _depend = []
    for dep in depend:
	if dep.find("|or|") != -1: # FIXME: handle this correctly
	    deps = dep.split("|or|")
	    # find the best
	    versions = []
	    for x in deps:
		# FIXME: find the one in the database and add it back
		key = dep_getkey(deps[0])
		cat = key.split("/")[0]
		name = key.split("/")[1]
		result = dbconn.searchPackagesByNameAndCategory(name,cat)
		if (result):
		    _depend.append(x)
		    break
	else:
	    _depend.append(dep)
    depend = _depend
    
    _rundepend = rundepend[:]
    
    # filter the  two trees
    for dep in depend:
	dep = dep_getkey(dep)
	for rundep in _rundepend:
	    xtest = dep_getkey(rundep)
	    if xtest == dep:
		# drp it from rundependxt
		_rundepend.remove(rundep)
    rundepend = _rundepend
    
    # merge into depend
    for atom in rundepend:
	depend.append(">="+atom)
    del rundepend
    
    dbconn.closeDB()
    #print depend
    return depend


'''
   @description: generates a list of unsatisfied dependencies
   @input package: packageInfo: list composed by int(id) and str(repository name)
   @output: dependency tree (list)
'''
def getDependencyTree(packageInfo):
    # first of all, get dependencies
    dependencies = getDependencies(packageInfo)
    
    # now create a list with the unsatisfied ones
    # query the installed packages database
    #print etpConst['etpdatabaseclientfilepath']
    clientDbconn = etpDatabase(readOnly = False, noUpload = True, dbFile = etpConst['etpdatabaseclientfilepath'], clientDatabase = True)
    
    unsatisfiedDeps = []
    for dependency in dependencies:
	rc = atomMatchInRepository(dependency,clientDbconn)
	if rc[0] == -1:
	    unsatisfiedDeps.append(dependency)
    
    # FIXME: complete this
    
    
    print unsatisfiedDeps
    clientDbconn.closeDB()

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

    # FIXME: need SPEED and completion
    if (options[0] == "generate"):
	
	#import threading
	
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
	print_info(darkred("  Initializing the new database at "+bold(etpConst['etpdatabaseclientfilepath'])), back = True)
	clientDbconn = etpDatabase(readOnly = False, noUpload = True, dbFile = etpConst['etpdatabaseclientfilepath'], clientDatabase = True)
	clientDbconn.initializeDatabase()
	print_info(darkgreen("  Database reinitialized correctly at "+bold(etpConst['etpdatabaseclientfilepath'])))
	
	# now collect files in the system
	tmpfile = etpConst['packagestmpfile']+".diskanalyze"
	print_info(red("  Collecting installed files... Saving into ")+bold(tmpfile))
	

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

	    # sync if needed
	    rc = fetchRepositoryIfNotAvailable(repo)
	    if (rc != 0):
	        return 129

	    dbfile = etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefile']
	    if (not orphanedFiles): # first cycle
	    
	        # open database
	        dbRepo = etpDatabase(readOnly = True, noUpload = True, dbFile = dbfile)
	    
	        # FIXME: add branch support
	        # search into database
		cnt = 0
		totalcnt = len(systemFiles)
		
	        for file in systemFiles:
		    cnt += 1
		    print_info("    @@ "+red("(")+blue(str(cnt))+"/"+bold(str(totalcnt))+red(")")+red(" Analyzing files..."), back = True)
		    pkgids = dbRepo.getIDPackagesFromFile(file)
		    if (pkgids):
		        for pkg in pkgids:
			    try:
				foundPackages.index(int(pkg))
				# nothing to do
			    except:
				# FIXME: if we get here, we need to analyze branch and then add
		                foundPackages.append([repo,pkg])
		    else:
		        orphanedFiles.append(file)
		print_info(red("    @@ Completed."))
		dbRepo.closeDB()
	    
	    else:
		
		dbRepo = etpDatabase(readOnly = True, noUpload = True, dbFile = dbfile)
		_orphanedFiles = orphanedFiles
		orphanedFiles = []

		cnt = 0
		totalcnt = len(_orphanedFiles)
		
	        for file in _orphanedFiles:
		    cnt += 1
		    print_info("    @@ "+red("(")+blue(str(cnt))+"/"+bold(str(totalcnt))+red(")")+red(" Analyzing files..."), back = True)
		    pkgids = dbRepo.getIDPackagesFromFile(file)
		    if (pkgids):
		        for pkg in pkgids:
			    try:
				foundPackages.index(int(pkg))
				# nothing to do
			    except:
				# FIXME: if we get here, we need to analyze branch and then add
		                foundPackages.append([repo,pkg])
		    else:
		        orphanedFiles.append(file)
		print_info(red("    @@ Completed."))
		dbRepo.closeDB()
		
	
	print_info(red("  ### Orphaned files:")+bold(str(len(orphanedFiles))))
	foundPackages = list(set(foundPackages))
	print_info(red("  ### Packages matching:")+bold(str(len(foundPackages))))
	
	if os.path.isfile(tmpfile):
	    os.remove(tmpfile)
	
	clientDbconn.closeDB()


def printPackageInfo(idpackage,dbconn):
    # now fetch essential info
    pkgatom = dbconn.retrieveAtom(idpackage)
    pkgname = dbconn.retrieveName(idpackage)
    pkgcat = dbconn.retrieveCategory(idpackage)
    pkgver = dbconn.retrieveVersion(idpackage)
    pkgdesc = dbconn.retrieveDescription(idpackage)
    pkghome = dbconn.retrieveHomepage(idpackage)
    pkglic = dbconn.retrieveLicense(idpackage)
    pkgsize = dbconn.retrieveSize(idpackage)
    pkgbin = dbconn.retrieveDownloadURL(idpackage)
    pkgflags = dbconn.retrieveCompileFlags(idpackage)
    pkgkeywords = dbconn.retrieveBinKeywords(idpackage)
    pkgtag = dbconn.retrieveVersionTag(idpackage)
    pkgdigest = dbconn.retrieveDigest(idpackage)
    pkgbranch = dbconn.retrieveBranch(idpackage)
    pkgcreatedate = convertUnixTimeToHumanTime(int(dbconn.retrieveDateCreation(idpackage)))
    if (not pkgtag):
        pkgtag = "Not tagged"
    pkgsize = bytesIntoHuman(pkgsize)

    print_info(red("     @@ Package: ")+bold(pkgatom)+"\t\t"+blue("branch: ")+bold(pkgbranch))
    print_info(darkgreen("       Category:\t\t")+darkblue(pkgcat))
    print_info(darkgreen("       Name:\t\t\t")+darkblue(pkgname))
    print_info(darkgreen("       Available version:\t")+blue(pkgver))
    print_info(darkgreen("       Installed version:\t")+blue("N/A"))
    print_info(darkgreen("       Available ver. tag:\t")+blue(pkgtag))
    print_info(darkgreen("       Size:\t\t\t")+blue(str(pkgsize)))
    print_info(darkgreen("       Download:\t\t")+brown(str(pkgbin)))
    print_info(darkgreen("       Checksum:\t\t")+brown(str(pkgdigest)))
    print_info(darkgreen("       Homepage:\t\t")+red(pkghome))
    print_info(darkgreen("       Description:\t\t")+pkgdesc)
    print_info(darkgreen("       Compiled with:\t")+blue(pkgflags[1]))
    print_info(darkgreen("       Architectures:\t")+blue(string.join(pkgkeywords," ")))
    print_info(darkgreen("       Created:\t\t")+pkgcreatedate)
    print_info(darkgreen("       License:\t\t")+red(pkglic))


def searchPackage(packages):
    
    foundPackages = {}
    
    print_info(yellow(" @@ ")+darkgreen("Searching..."))
    # search inside each available database
    repoNumber = 0
    searchError = False
    for repo in etpRepositories:
	foundPackages[repo] = {}
	repoNumber += 1
	print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
	
	rc = fetchRepositoryIfNotAvailable(repo)
	if (rc != 0):
	    searchError = True
	    continue
	
	dbfile = etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasefile']
	    
	dbconn = etpDatabase(readOnly = True, dbFile = dbfile)
	for package in packages:
	    result = dbconn.searchPackages(package)
	    
	    if (result):
		foundPackages[repo][package] = result
	        # print info
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
		    printPackageInfo(idpackage,dbconn)
	
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
def installPackages(packages, autoDrive = False):
    print packages

    # check if I am root
    if (not checkRoot()):
	print_error(red("\t You must run this function as root."))
	return 1,-1
    
    foundAtoms = []
    for package in packages:
	foundAtoms.append([package,atomMatch(package)])

    # filter not found packages
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

    # now print the selected packages
    print_info(red(" @@ ")+blue("These are the chosen packages:"))
    totalatoms = len(foundAtoms)
    atomscounter = 0
    totalDownloadSize = 0
    for atomInfo in foundAtoms:
	atomscounter += 1
	idpackage = atomInfo[0]
	reponame = atomInfo[1]
	# open database
	dbfile = etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasefile']
	dbconn = etpDatabase(readOnly = True, dbFile = dbfile)

	# get needed info
	pkgatom = dbconn.retrieveAtom(idpackage)
	pkgsize = dbconn.retrieveSize(idpackage)
	pkgver = dbconn.retrieveVersion(idpackage)
	pkgtag = dbconn.retrieveVersionTag(idpackage)
	if not pkgtag:
	    pkgtag = "NoTag"
	pkgrev = dbconn.retrieveRevision(idpackage)
	totalDownloadSize += int(pkgsize)
	pkgsize = bytesIntoHuman(pkgsize)

	print_info("   # "+red("(")+bold(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+bold(pkgatom))
	print_info("\t\t"+red("Repository:\t\t")+" "+darkred(etpRepositories[reponame]['description']))
	print_info("\t\t"+red("Available:\t\t")+" "+blue("version: ")+bold(pkgver)+blue(" ~ tag: ")+bold(pkgtag)+blue(" ~ revision: ")+bold(str(pkgrev)))
	print_info("\t\t"+red("Installed:\t\t")+" "+darkred("Not implemented"))
	print_info("\t\t"+red("Download Size:\t\t")+" "+brown(pkgsize))
	
	dbconn.closeDB()

    print_info(red(" @@ ")+blue("Number of packages: ")+str(totalatoms))
    # FIXME: add only if the packages have not been downloaded
    print_info(red(" @@ ")+blue("Total Packages Size: ")+str(bytesIntoHuman(totalDownloadSize)))
    
    if (not autoDrive):
        rc = askquestion("     Would you like to continue with dependencies calculation ?")
        if rc == "No":
	    return 0,0
	
    for atomInfo in foundAtoms:
	getDependencyTree(atomInfo)
    
    print "not working yet :-) ahaha!"
    return 0,0