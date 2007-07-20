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
sys.path.append('../libraries')
from entropyConstants import *
from outputTools import *
from remoteTools import downloadData
from entropyTools import unpackGzip,compareMd5

def repositories(options):
    
    # Options available for all the packages submodules
    myopts = options[1:]
    equoRequestAsk = False
    equoRequestPretend = False
    equoRequestPackagesCheck = False
    for opt in myopts:
	if (opt == "--ask"):
	    equoRequestAsk = True
	elif (opt == "--pretend"):
	    equoRequestPretend = True

    if (options[0] == "sync"):
	syncRepositories()

    if (options[0] == "status"):
	for repo in etpRepositories:
	    showRepositoryInfo(repo)

    if (options[0] == "show"):
	showRepositories()

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

def syncRepositories():
    # check etpRepositories
    if len(etpRepositories) == 0:
	print_error(yellow(" * ")+red("No repositories specified in ")+etpConst['repositoriesconf'])
	return 127
    print_info(yellow(" @@ ")+green("Repositories syncronization..."))
    repoNumber = 0
    syncErrors = False
    for repo in etpRepositories:
	
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


