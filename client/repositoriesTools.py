#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo repositories handling library

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

########################################################
####
##   Repositories Tools
#

import os
from entropyConstants import *
from clientConstants import *
from outputTools import *
import entropyTools
from remoteTools import downloadData, getOnlineContent
import dumpTools

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
    print_info(darkred(" * ")+darkgreen("Active Repositories:"))
    repoNumber = 0
    for repo in etpRepositories:
	repoNumber += 1
	print_info(blue("\t#"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
	sourcecount = 0
	for pkgrepo in etpRepositories[repo]['packages']:
	    sourcecount += 1
	    print_info(red("\t\tPackages Mirror #"+str(sourcecount)+" : ")+darkgreen(pkgrepo))
	print_info(red("\t\tDatabase URL: ")+darkgreen(etpRepositories[repo]['database']))
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
    print_info(darkgreen("\tStatus: ")+darkred(status))
    urlcount = 0
    for repourl in etpRepositories[reponame]['packages'][::-1]:
	urlcount += 1
        print_info(red("\tPackages URL #"+str(urlcount)+": ")+darkgreen(repourl))
    print_info(red("\tDatabase URL: ")+darkgreen(etpRepositories[reponame]['database']))
    print_info(red("\tRepository name: ")+bold(reponame))
    print_info(red("\tRepository database path: ")+blue(etpRepositories[reponame]['dbpath']))
    revision = getRepositoryRevision(reponame)
    mhash = getRepositoryDbFileHash(reponame)

    print_info(red("\tRepository database checksum: ")+mhash)
    print_info(red("\tRepository revision: ")+darkgreen(str(revision)))
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
    if (not entropyTools.isRoot()):
	print_error(red("\t You must run this application as root."))
	return 1

    # check etpRepositories
    if len(etpRepositories) == 0:
	if (not quiet):
	    print_error(darkred(" * ")+red("No repositories specified in ")+etpConst['repositoriesconf'])
	return 127

    if (not quiet):
        print_info(darkred(" @@ ")+darkgreen("Repositories syncronization..."))
    repoNumber = 0
    syncErrors = False
    
    if (reponames == []):
	for x in etpRepositories:
	    reponames.append(x)
    
    dbupdated = False
    
    # Test network connectivity
    conntest = getOnlineContent("http://svn.sabayonlinux.org")
    if conntest == False:
	print_info(darkred(" @@ ")+darkgreen("You are not connected to the Internet. You should do it."))
	return 2
    
    for repo in reponames:
	
	repoNumber += 1
	
	if (not quiet):
	    print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
	    print_info(red("\tDatabase URL: ")+darkgreen(etpRepositories[repo]['database']))
	    print_info(red("\tDatabase local path: ")+darkgreen(etpRepositories[repo]['dbpath']))
	
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
	
	# database is going to be updated
	dbupdated = True
	# clear database interface cache belonging to this repository
	dumpTools.dumpobj(etpCache['dbInfo']+repo,{})
	
	cmethod = etpConst['etpdatabasecompressclasses'].get(etpRepositories[repo]['dbcformat'])
	if cmethod == None: raise Exception
	
	# starting to download
	if (not quiet):
	    print_info(red("\tDownloading database ")+darkgreen(etpConst[cmethod[2]])+red(" ..."))
	# create dir if it doesn't exist
	if not os.path.isdir(etpRepositories[repo]['dbpath']):
	    if (not quiet):
	        print_info(red("\t\tCreating database directory..."))
	    os.makedirs(etpRepositories[repo]['dbpath'])
	# download
	downloadData(etpRepositories[repo]['database']+"/"+etpConst[cmethod[2]],etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[2]])
	
	if (not quiet):
	    print_info(red("\tUnpacking database to ")+darkgreen(etpConst['etpdatabasefile'])+red(" ..."))
	eval("entropyTools."+cmethod[1])(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[2]])
	# download etpdatabasehashfile
	if (not quiet):
	    print_info(red("\tDownloading checksum ")+darkgreen(etpConst['etpdatabasehashfile'])+red(" ..."))
	downloadData(etpRepositories[repo]['database']+"/"+etpConst['etpdatabasehashfile'],etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'])
	# checking checksum
	if (not quiet):
	    print_info(red("\tChecking downloaded database ")+darkgreen(etpConst['etpdatabasefile'])+red(" ..."), back = True)
	f = open(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
	md5hash = f.readline().strip()
	md5hash = md5hash.split()[0]
	f.close()
	rc = entropyTools.compareMd5(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefile'],md5hash)
	if rc:
	    if (not quiet):
	        print_info(red("\tDownloaded database status: ")+bold("OK"))
	else:
	    if (not quiet):
	        print_error(red("\tDownloaded database status: ")+darkred("ERROR"))
	        print_error(red("\t An error occured while checking database integrity"))
	    # delete all
	    if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile']):
		os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'])
	    if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[2]]):
		os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[2]])
	    if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile']):
		os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'])
	    syncErrors = True
	    continue
	
	# download etpdatabaserevisionfile
	if (not quiet):
	    print_info(red("\tDownloading revision ")+darkgreen(etpConst['etpdatabaserevisionfile'])+red(" ..."))
	downloadData(etpRepositories[repo]['database']+"/"+etpConst['etpdatabaserevisionfile'],etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'])
	
	if (not quiet):
	    print_info(red("\tUpdated repository revision: ")+bold(str(getRepositoryRevision(repo))))
	print_info(darkgreen("\tUpdate completed"))

    if syncErrors:
	if (not quiet):
	    print_warning(darkred(" @@ ")+red("Something bad happened. Please have a look."))
	return 128

    if (dbupdated):
	
	# safely clean ram caches
	atomMatchCache.clear()
	dumpTools.dumpobj(etpCache['atomMatch'],{})
	generateDependsTreeCache.clear()
	dumpTools.dumpobj(etpCache['generateDependsTree'],{})
	dbCacheStore.clear()
	
	# generate cache
        import cacheTools
        cacheTools.generateCache(quiet = quiet, depcache = True, configcache = False)

    return 0