#!/usr/bin/python
'''
    # DESCRIPTION:
    # generic tools for all the handlers applications

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

# FIXME: this depends on portage, should be moved from here ASAP
from outputTools import *
from entropyConstants import *

import re
import sys
import random
import commands

# Instantiate the databaseStatus:
import databaseTools
import mirrorTools
dbStatus = databaseTools.databaseStatus()

# Logging initialization
import logTools
entropyLog = logTools.LogFile(level=etpConst['entropyloglevel'],filename = etpConst['entropylogfile'], header = "[Entropy]")
# example: entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"testFuncton: called.")

# EXIT STATUSES: 100-199

global __etp_debug
__etp_debug = False
def enableDebug():
    __etp_debug = True
    import pdb
    pdb.set_trace()

def getDebug():
    return __etp_debug

def isRoot():
    import getpass
    if (getpass.getuser() == "root"):
        return True
    return False

def getRandomNumber():
    return int(str(random.random())[2:7])

def countdown(secs=5,what="Counting..."):
    import time
    if secs:
	print what
        for i in range(secs):
            sys.stdout.write(str(i)+" ")
            sys.stdout.flush()
	    time.sleep(1)

def spinner(rotations, interval, message=''):
	for x in xrange(rotations):
		writechar(message + '|/-\\'[x%4] + '\r')
		time.sleep(interval)
	writechar(' ')
	for i in xrange(len(message)): print ' ',
	writechar('\r')

def removeSpaceAtTheEnd(string):
    if string.endswith(" "):
        return string[:len(string)-1]
    else:
	return string

def md5sum(filepath):
    import md5
    m = md5.new()
    readfile = file(filepath)
    block = readfile.read(1024)
    while block:
        m.update(block)
	block = readfile.read(1024)
    return m.hexdigest()

# This function creates the .hash file related to the given package file
# @returns the complete hash file path
# FIXME: add more hashes, SHA1 for example
def createHashFile(tbz2filepath):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"createHashFile: for "+tbz2filepath)
    md5hash = md5sum(tbz2filepath)
    hashfile = tbz2filepath+etpConst['packageshashfileext']
    f = open(hashfile,"w")
    tbz2name = os.path.basename(tbz2filepath)
    f.write(md5hash+"  "+tbz2name+"\n")
    f.flush()
    f.close()
    return hashfile

def compareMd5(filepath,checksum):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"compareMd5: called. ")
    checksum = str(checksum)
    result = md5sum(filepath)
    result = str(result)
    if checksum == result:
        entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"compareMd5: match. ")
	return True
    entropyLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"compareMd5: no match. ")
    return False

def md5string(string):
    import md5
    m = md5.new()
    m.update(string)
    return m.hexdigest()

# Imported from Gentoo portage_dep.py
# Copyright 2003-2004 Gentoo Foundation
# done to avoid the import of portage_dep here
ver_regexp = re.compile("^(cvs\\.)?(\\d+)((\\.\\d+)*)([a-z]?)((_(pre|p|beta|alpha|rc)\\d*)*)(-r(\\d+))?$")
def isjustpkgname(mypkg):
    myparts = mypkg.split('-')
    for x in myparts:
	if ververify(x):
	    return 0
    return 1

def ververify(myver, silent=1):
    if ver_regexp.match(myver):
	return 1
    else:
	if not silent:
	    print "!!! syntax error in version: %s" % myver
	return 0

def removePackageOperators(atom):
    if atom.startswith(">") or atom.startswith("<"):
	atom = atom[1:]
    if atom.startswith("="):
	atom = atom[1:]
    if atom.startswith("~"):
	atom = atom[1:]
    return atom

# Version compare function taken from portage_versions.py
# portage_versions.py -- core Portage functionality
# Copyright 1998-2006 Gentoo Foundation
def compareVersions(ver1, ver2, silent=1):
	
	if ver1 == ver2:
		return 0
	mykey=ver1+":"+ver2
	try:
		return vercmp_cache[mykey]
	except KeyError:
		pass
	match1 = ver_regexp.match(ver1)
	match2 = ver_regexp.match(ver2)
	
	# shortcut for cvs ebuilds (new style)
	#if match1.group(1) and not match2.group(1):
	#	vercmp_cache[mykey] = 1
	#	return 1
	#elif match2.group(1) and not match1.group(1):
	#	vercmp_cache[mykey] = -1
	#	return -1
	
	# building lists of the version parts before the suffix
	# first part is simple
	list1 = [int(match1.group(2))]
	list2 = [int(match2.group(2))]

	# this part would greatly benefit from a fixed-length version pattern
	if len(match1.group(3)) or len(match2.group(3)):
		vlist1 = match1.group(3)[1:].split(".")
		vlist2 = match2.group(3)[1:].split(".")
		for i in range(0, max(len(vlist1), len(vlist2))):
			# Implcit .0 is given a value of -1, so that 1.0.0 > 1.0, since it
			# would be ambiguous if two versions that aren't literally equal
			# are given the same value (in sorting, for example).
			if len(vlist1) <= i or len(vlist1[i]) == 0:
				list1.append(-1)
				list2.append(int(vlist2[i]))
			elif len(vlist2) <= i or len(vlist2[i]) == 0:
				list1.append(int(vlist1[i]))
				list2.append(-1)
			# Let's make life easy and use integers unless we're forced to use floats
			elif (vlist1[i][0] != "0" and vlist2[i][0] != "0"):
				list1.append(int(vlist1[i]))
				list2.append(int(vlist2[i]))
			# now we have to use floats so 1.02 compares correctly against 1.1
			else:
				list1.append(float("0."+vlist1[i]))
				list2.append(float("0."+vlist2[i]))

	# and now the final letter
	if len(match1.group(5)):
		list1.append(ord(match1.group(5)))
	if len(match2.group(5)):
		list2.append(ord(match2.group(5)))

	for i in range(0, max(len(list1), len(list2))):
		if len(list1) <= i:
			return -1
		elif len(list2) <= i:
			return 1
		elif list1[i] != list2[i]:
			return list1[i] - list2[i]
	
	# main version is equal, so now compare the _suffix part
	list1 = match1.group(6).split("_")[1:]
	list2 = match2.group(6).split("_")[1:]
	
	for i in range(0, max(len(list1), len(list2))):
		if len(list1) <= i:
			s1 = ("p","0")
		else:
			s1 = suffix_regexp.match(list1[i]).groups()
		if len(list2) <= i:
			s2 = ("p","0")
		else:
			s2 = suffix_regexp.match(list2[i]).groups()
		if s1[0] != s2[0]:
			return suffix_value[s1[0]] - suffix_value[s2[0]]
		if s1[1] != s2[1]:
			# it's possible that the s(1|2)[1] == ''
			# in such a case, fudge it.
			try:			r1 = int(s1[1])
			except ValueError:	r1 = 0
			try:			r2 = int(s2[1])
			except ValueError:	r2 = 0
			return r1 - r2
	
	# the suffix part is equal to, so finally check the revision
	if match1.group(10):
		r1 = int(match1.group(10))
	else:
		r1 = 0
	if match2.group(10):
		r2 = int(match2.group(10))
	else:
		r2 = 0
	vercmp_cache[mykey] = r1 - r2
	return r1 - r2

def isnumber(x):
    try:
	t = int(x)
	return True
    except:
	return False

# this functions removes duplicates without breaking the list order
# nameslist: a list that contains duplicated names
# @returns filtered list
def filterDuplicatedEntries(nameslist):
    _nameslist = nameslist
    for name in _nameslist:
	try:
	    first = nameslist.index(name)
	    nameslist[first] = "x"+nameslist[first]
	    try:
		while 1:
		    nameslist.remove(name)
	    except:
		pass
	    nameslist[first] = nameslist[first][1:]
	except:
	    pass
    return nameslist

# Tool to run commands
def spawnCommand(command, redirect = None):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"spawnCommand: called for: "+command)
    if redirect is not None:
        command += " "+redirect
    rc = os.system(command)
    return rc

def extractFTPHostFromUri(uri):
    ftphost = uri.split("ftp://")[len(uri.split("ftp://"))-1]
    ftphost = ftphost.split("@")[len(ftphost.split("@"))-1]
    ftphost = ftphost.split("/")[0]
    ftphost = ftphost.split(":")[0]
    return ftphost

# This function check the Entropy online database status
def getEtpRemoteDatabaseStatus():

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getEtpRemoteDatabaseStatus: called.")

    uriDbInfo = []
    for uri in etpConst['activatoruploaduris']:
	ftp = mirrorTools.handlerFTP(uri)
	ftp.setCWD(etpConst['etpurirelativepath'])
	rc = ftp.isFileAvailable(etpConst['etpdatabasefilegzip'])
	if (rc):
	    # then get the file revision, if exists
	    rc = ftp.isFileAvailable(etpConst['etpdatabaserevisionfile'])
	    if (rc):
		# get the revision number
		ftp.downloadFile(etpConst['etpdatabaserevisionfile'],etpConst['packagestmpdir'],True)
		f = open( etpConst['packagestmpdir'] + "/" + etpConst['etpdatabaserevisionfile'],"r")
		revision = int(f.readline().strip())
		f.close()
		spawnCommand("rm -f "+etpConst['packagestmpdir']+etpConst['etpdatabaserevisionfile'])
	    else:
		revision = 0
	else:
	    # then set mtime to 0 and quit
	    revision = 0
	info = [uri+"/"+etpConst['etpurirelativepath']+etpConst['etpdatabasefilegzip'],revision]
	uriDbInfo.append(info)
	ftp.closeFTPConnection()

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getEtpRemoteDatabaseStatus: dump -> "+str(uriDbInfo))

    return uriDbInfo

def syncRemoteDatabases(noUpload = False, justStats = False):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"syncRemoteDatabases: called.")

    remoteDbsStatus = getEtpRemoteDatabaseStatus()
    print_info(green(" * ")+red("Remote Entropy Database Repository Status:"))
    for dbstat in remoteDbsStatus:
	print_info(green("\t Host:\t")+bold(extractFTPHostFromUri(dbstat[0])))
	print_info(red("\t  * Database revision: ")+blue(str(dbstat[1])))

    # check if the local DB or the revision file exist
    # in this way we can regenerate the db without messing the --initialize function with a new unwanted download
    if os.path.isfile(etpConst['etpdatabasefilepath']) or os.path.isfile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile']):
	# file exist, get revision
	f = open(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'],"r")
	etpDbLocalRevision = int(f.readline().strip())
	f.close()
    else:
	etpDbLocalRevision = 0

    print_info(red("\t  * Database local revision currently at: ")+blue(str(etpDbLocalRevision)))
    
    if (justStats):
	return
    
    downloadLatest = []
    uploadLatest = False
    uploadList = []
    
    #print str(etpDbLocalRevision)
    
    # if the local DB does not exist, get the latest
    if (etpDbLocalRevision == 0):
	# seek mirrors
	latestRemoteDb = []
	etpDbRemotePaths = []
	for dbstat in remoteDbsStatus:
	    if ( dbstat[1] != 0 ):
		# collect
		etpDbRemotePaths.append(dbstat)
	if etpDbRemotePaths == []:
	    #print "DEBUG: generate and upload"
	    # (to all!)
	    uploadLatest = True
	    uploadList = remoteDbsStatus
	else:
	    #print "DEBUG: get the latest ?"
	    revisions = []
	    for dbstat in etpDbRemotePaths:
		revisions.append(dbstat[1])
	    if len(revisions) > 1:
		latestrevision = alphaSorter(revisions)[len(revisions)-1]
	    else:
		latestrevision = revisions[0]
	    for dbstat in etpDbRemotePaths:
		if dbstat[1] == latestrevision:
		    # found !
		    downloadLatest = dbstat
		    break
	    # Now check if we need to upload back the files to the other mirrors
	    #print "DEBUG: check the others, if they're also updated, quit"
	    for dbstat in remoteDbsStatus:
		if (downloadLatest[1] != dbstat[1]):
		    uploadLatest = True
		    uploadList.append(dbstat)
    else:
	# while if it exists
	# seek mirrors
	latestRemoteDb = []
	etpDbRemotePaths = []
	for dbstat in remoteDbsStatus:
	    if ( dbstat[1] != 0 ):
		# collect
		etpDbRemotePaths.append(dbstat)
	if etpDbRemotePaths == []:
	    #print "DEBUG: upload our version"
	    uploadLatest = True
	    # upload to all !
	    uploadList = remoteDbsStatus
	else:
	    #print "DEBUG: get the latest?"
	    revisions = []
	    for dbstat in etpDbRemotePaths:
		revisions.append(str(dbstat[1]))
	    
	    latestrevision = int(alphaSorter(revisions)[len(revisions)-1])
	    for dbstat in etpDbRemotePaths:
		if dbstat[1] == latestrevision:
		    # found !
		    latestRemoteDb = dbstat
		    break
	    # now compare downloadLatest with our local db revision
	    #print "data revisions:"
	    #print str(latestRemoteDb[1])
	    #print str(etpDbLocalRevision)
	    if (etpDbLocalRevision < latestRemoteDb[1]):
		# download !
		#print "appending a download"
		downloadLatest = latestRemoteDb
	    elif (etpDbLocalRevision > latestRemoteDb[1]):
		# upload to all !
		#print str(etpDbLocalRevision)
		#print str(latestRemoteDb[1])
		#print "appending the upload to all"
		uploadLatest = True
		uploadList = remoteDbsStatus

	    # If the uploadList is not filled, this means that the other mirror might need an update
	    if (not uploadLatest):
	        for dbstat in remoteDbsStatus:
		    if (latestRemoteDb[1] != dbstat[1]):
		        uploadLatest = True
		        uploadList.append(dbstat)
    
    if (downloadLatest == []) and (not uploadLatest):
	entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"syncRemoteDatabases: online database does not need to be updated.")
	print_info(green(" * ")+red("Online database does not need to be updated."))
        return

    # now run the selected task!
    if (downloadLatest != []):
	entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"syncRemoteDatabases: download latest database needed.")
	# match the proper URI
	for uri in etpConst['activatoruploaduris']:
	    if downloadLatest[0].startswith(uri):
		downloadLatest[0] = uri
	downloadDatabase(downloadLatest[0])
	
    if (uploadLatest) and (not noUpload):
	entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"syncRemoteDatabases: some mirrors don't have the latest database.")
	print_info(green(" * ")+red("Starting to update the needed mirrors ..."))
	_uploadList = []
	for uri in etpConst['activatoruploaduris']:
	    for list in uploadList:
		if list[0].startswith(uri):
		    _uploadList.append(uri)
		    break
	
	uploadDatabase(_uploadList)
	print_info(green(" * ")+red("All the mirrors have been updated."))

    remoteDbsStatus = getEtpRemoteDatabaseStatus()
    print_info(green(" * ")+red("Remote Entropy Database Repository Status:"))
    for dbstat in remoteDbsStatus:
	print_info(green("\t Host:\t")+bold(extractFTPHostFromUri(dbstat[0])))
	print_info(red("\t  * Database revision: ")+blue(str(dbstat[1])))


def uploadDatabase(uris):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"uploadDatabase: called.")

    # our fancy compressor :-)
    import gzip
    
    for uri in uris:
	downloadLockDatabases(True,[uri])
	
	entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"uploadDatabase: uploading data to: "+extractFTPHostFromUri(uri))
	
	print_info(green(" * ")+red("Uploading database to ")+bold(extractFTPHostFromUri(uri))+red(" ..."))
	print_info(green(" * ")+red("Connecting to ")+bold(extractFTPHostFromUri(uri))+red(" ..."), back = True)
	ftp = mirrorTools.handlerFTP(uri)
	print_info(green(" * ")+red("Changing directory to ")+bold(etpConst['etpurirelativepath'])+red(" ..."), back = True)
	ftp.setCWD(etpConst['etpurirelativepath'])
	
	print_info(green(" * ")+red("Uploading file ")+bold(etpConst['etpdatabasefilegzip'])+red(" ..."), back = True)
	
	# compress the database file first
	dbfile = open(etpConst['etpdatabasefilepath'],"rb")
	dbcont = dbfile.readlines()
	dbfile.close()
	dbfilegz = gzip.GzipFile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasefilegzip'],"wb")
	for i in dbcont:
	    dbfilegz.write(i)
	dbfilegz.close()
	del dbcont
	
	# uploading database file
	rc = ftp.uploadFile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasefilegzip'])
	if (rc == True):
	    print_info(green(" * ")+red("Upload of ")+bold(etpConst['etpdatabasefilegzip'])+red(" completed."))
	else:
	    print_warning(yellow(" * ")+red("Cannot properly upload to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
	
	# remove the gzip
	os.remove(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasefilegzip'])
	
	print_info(green(" * ")+red("Uploading file ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'])+red(" ..."), back = True)
	# uploading revision file
	rc = ftp.uploadFile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'],True)
	if (rc == True):
	    print_info(green(" * ")+red("Upload of ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'])+red(" completed."))
	else:
	    print_warning(yellow(" * ")+red("Cannot properly upload to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))

	# generate digest
	hexdigest = md5sum(etpConst['etpdatabasefilepath'])
	f = open(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'],"w")
	f.write(hexdigest+"  "+etpConst['etpdatabasehashfile']+"\n")
	f.flush()
	f.close()

	# upload digest
	print_info(green(" * ")+red("Uploading file ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'])+red(" ..."), back = True)
	rc = ftp.uploadFile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'],True)
	if (rc == True):
	    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"uploadDatabase: uploading to: "+extractFTPHostFromUri(uri)+" successfull.")
	    print_info(green(" * ")+red("Upload of ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'])+red(" completed. Disconnecting."))
	else:
	    entropyLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"uploadDatabase: uploading to: "+extractFTPHostFromUri(uri)+" UNSUCCESSFUL! ERROR!.")
	    print_warning(yellow(" * ")+red("Cannot properly upload to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
	
	# close connection
	ftp.closeFTPConnection()
	# unlock database
	downloadLockDatabases(False,[uri])


def downloadDatabase(uri):
    
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadDatabase: called.")
    
    import gzip
    
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadDatabase: downloading from -> "+extractFTPHostFromUri(uri))
    
    print_info(green(" * ")+red("Downloading database from ")+bold(extractFTPHostFromUri(uri))+red(" ..."))
    print_info(green(" * ")+red("Connecting to ")+bold(extractFTPHostFromUri(uri))+red(" ..."), back = True)
    ftp = mirrorTools.handlerFTP(uri)
    print_info(green(" * ")+red("Changing directory to ")+bold(etpConst['etpurirelativepath'])+red(" ..."), back = True)
    ftp.setCWD(etpConst['etpurirelativepath'])
    
    
    # downloading database file
    print_info(green(" * ")+red("Downloading file to ")+bold(etpConst['etpdatabasefilegzip'])+red(" ..."), back = True)
    rc = ftp.downloadFile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasefilegzip'],os.path.dirname(etpConst['etpdatabasefilepath']))
    if (rc == True):
	print_info(green(" * ")+red("Download of ")+bold(etpConst['etpdatabasefilegzip'])+red(" completed."))
    else:
	print_warning(yellow(" * ")+red("Cannot properly download to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))

    # On the fly decompression
    print_info(green(" * ")+red("Decompressing ")+bold(etpConst['etpdatabasefilegzip'])+red(" ..."), back = True)
    dbfile = open(etpConst['etpdatabasefilepath'],"wb")
    dbfilegz = gzip.GzipFile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasefilegzip'],"rb")
    dbcont = dbfilegz.readlines()
    dbfilegz.close()
    dbfile.writelines(dbcont)
    dbfile.flush()
    dbfile.close()
    del dbcont
    print_info(green(" * ")+red("Decompression of ")+bold(etpConst['etpdatabasefilegzip'])+red(" completed."))
    
    # downloading revision file
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadDatabase: downloading revision file for "+extractFTPHostFromUri(uri))
    print_info(green(" * ")+red("Downloading file to ")+bold(etpConst['etpdatabaserevisionfile'])+red(" ..."), back = True)
    rc = ftp.downloadFile(etpConst['etpdatabaserevisionfile'],os.path.dirname(etpConst['etpdatabasefilepath']),True)
    if (rc == True):
	print_info(green(" * ")+red("Download of ")+bold(etpConst['etpdatabaserevisionfile'])+red(" completed."))
    else:
	print_warning(yellow(" * ")+red("Cannot properly download to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
    
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadDatabase: downloading digest file for "+extractFTPHostFromUri(uri))
    # downlading digest
    print_info(green(" * ")+red("Downloading file to ")+bold(etpConst['etpdatabasehashfile'])+red(" ..."), back = True)
    rc = ftp.downloadFile(etpConst['etpdatabasehashfile'],os.path.dirname(etpConst['etpdatabasefilepath']),True)
    if (rc == True):
	print_info(green(" * ")+red("Download of ")+bold(etpConst['etpdatabasehashfile'])+red(" completed. Disconnecting."))
    else:
	entropyLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"downloadDatabase: Cannot properly download from "+extractFTPHostFromUri(uri)+". Please check.")
	print_warning(yellow(" * ")+red("Cannot properly download from ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadDatabase: do some tidy.")
    spawnCommand("rm -f " + etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasefilegzip'], "&> /dev/null")
    # close connection
    ftp.closeFTPConnection()

# Reports in a list form the lock status of the mirrors
# @ [ uri , True/False, True/False ] --> True = locked, False = unlocked
# @ the second parameter is referred to upload locks, while the second to download ones
def getMirrorsLock():

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getMirrorsLock: called.")

    # parse etpConst['activatoruploaduris']
    dbstatus = []
    for uri in etpConst['activatoruploaduris']:
	data = [ uri, False , False ]
	ftp = mirrorTools.handlerFTP(uri)
	ftp.setCWD(etpConst['etpurirelativepath'])
	if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
	    # Upload is locked
	    data[1] = True
	if (ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile'])):
	    # Upload is locked
	    data[2] = True
	ftp.closeFTPConnection()
	dbstatus.append(data)
    return dbstatus


def downloadPackageFromMirror(uri,pkgfile):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: called for "+extractFTPHostFromUri(uri)+" and file -> "+pkgfile)

    tries = 0
    maxtries = 5
    for i in range(maxtries):
	
	entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: ("+tries+"/"+maxtries+") downloading -> "+pkgfile)
	
	pkgfilename = pkgfile.split("/")[len(pkgfile.split("/"))-1]
        print_info(red("  * Connecting to ")+bold(extractFTPHostFromUri(uri)), back = True)
        # connect
        ftp = mirrorTools.handlerFTP(uri)
        ftp.setCWD(etpConst['binaryurirelativepath'])
        # get the files
        print_info(red("  * Downloading ")+yellow(pkgfilename)+red(" from ")+bold(extractFTPHostFromUri(uri)))
        rc = ftp.downloadFile(pkgfilename,etpConst['packagesbindir'])
	if (rc is None):
	    entropyLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: ("+tries+"/"+maxtries+") Error. File not found. -> "+pkgfile)
	    # file does not exist
	    print_warning(red("  * File ")+yellow(pkgfilename)+red(" does not exist remotely on ")+bold(extractFTPHostFromUri(uri)))
	    ftp.closeFTPConnection()
	    return None
	entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: ("+tries+"/"+maxtries+") checking md5 for -> "+pkgfile)
        # check md5
	dbconn = databaseTools.etpDatabase(readOnly = True)
	storedmd5 = dbconn.retrievePackageVarFromBinaryPackage(pkgfilename,"digest")
	dbconn.closeDB()
	print_info(red("  * Checking MD5 of ")+yellow(pkgfilename)+red(": should be ")+bold(storedmd5), back = True)
	md5check = compareMd5(etpConst['packagesbindir']+"/"+pkgfilename,storedmd5)
	if (md5check):
	    print_info(red("  * Package ")+yellow(pkgfilename)+red("downloaded successfully."))
	    return True
	else:
	    if (tries == maxtries):
		entropyLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: Max tries limit reached. Checksum does not match. Please consider to download or repackage again. Giving up.")
		print_warning(red("  * Package ")+yellow(pkgfilename)+red(" checksum does not match. Please consider to download or repackage again. Giving up."))
		return False
	    else:
		entropyLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: Checksum does not match. Trying to download it again...")
		print_warning(red("  * Package ")+yellow(pkgfilename)+red(" checksum does not match. Trying to download it again..."))
		tries += 1
		if os.path.isfile(etpConst['packagesbindir']+"/"+pkgfilename):
		    os.remove(etpConst['packagesbindir']+"/"+pkgfilename)


# tar.bz2 compress function...
def compressTarBz2(storepath,pathtocompress):
    
    cmd = "tar cjf "+storepath+" ."
    rc = spawnCommand(
    		"cd "+pathtocompress+";"
    		""+cmd, "&> /dev/null"
		)
    return rc

# tar.bz2 uncompress function...
def uncompressTarBz2(filepath, extractPath = None):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"uncompressTarBz2: called. ")
    if extractPath is None:
	extractPath = os.path.dirname(filepath)
    cmd = "tar xjf "+filepath+" -C "+extractPath
    rc = spawnCommand(cmd, "&> /dev/null")
    return rc

def bytesIntoHuman(bytes):
    size = str(round(float(bytes)/1024,1))
    if bytes < 1024:
	size = str(bytes)+"b"
    elif bytes < 1023999:
	size += "kB"
    elif bytes > 1023999:
	size = str(round(float(size)/1024,1))
	size += "MB"
    return size

# hide password from full ftp URI
def hideFTPpassword(uri):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"hideFTPpassword: called. ")
    ftppassword = uri.split("@")[:len(uri.split("@"))-1]
    if len(ftppassword) > 1:
	import string
	ftppassword = string.join(ftppassword,"@")
	ftppassword = ftppassword.split(":")[len(ftppassword.split(":"))-1]
	if (ftppassword == ""):
	    return uri
    else:
	ftppassword = ftppassword[0]
	ftppassword = ftppassword.split(":")[len(ftppassword.split(":"))-1]
	if (ftppassword == ""):
	    return uri

    newuri = re.subn(ftppassword,"xxxxxxxx",uri)[0]
    return newuri

def lockDatabases(lock = True, mirrorList = []):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"lockDatabases: called. ")

    outstat = False
    if (mirrorList == []):
	mirrorList = etpConst['activatoruploaduris']
    for uri in mirrorList:
	
	entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"lockDatabases: locking? "+str(lock)+" for: "+extractFTPHostFromUri(uri))
	
	if (lock):
	    print_info(yellow(" * ")+red("Locking ")+bold(extractFTPHostFromUri(uri))+red(" mirror..."),back = True)
	else:
	    print_info(yellow(" * ")+red("Unlocking ")+bold(extractFTPHostFromUri(uri))+red(" mirror..."),back = True)
	ftp = mirrorTools.handlerFTP(uri)
	# upload the lock file to database/%ARCH% directory
	ftp.setCWD(etpConst['etpurirelativepath'])
	# check if the lock is already there
	if (lock):
	    if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
		entropyLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"lockDatabases: mirror "+extractFTPHostFromUri(uri)+" already locked.")
	        print_info(green(" * ")+red("Mirror database at ")+bold(extractFTPHostFromUri(uri))+red(" already locked."))
	        ftp.closeFTPConnection()
	        continue
	else:
	    if (not ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
		entropyLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"lockDatabases: mirror "+extractFTPHostFromUri(uri)+" already unlocked.")
	        print_info(green(" * ")+red("Mirror database at ")+bold(extractFTPHostFromUri(uri))+red(" already unlocked."))
	        ftp.closeFTPConnection()
	        continue
	if (lock):
	    f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'],"w")
	    f.write("database locked\n")
	    f.flush()
	    f.close()
	    rc = ftp.uploadFile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'],ascii= True)
	    if (rc == True):
		entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"lockDatabases: mirror "+extractFTPHostFromUri(uri)+" successfully locked.")
	        print_info(green(" * ")+red("Succesfully locked ")+bold(extractFTPHostFromUri(uri))+red(" mirror."))
	    else:
	        outstat = True
	        print "\n"
		entropyLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"lockDatabases: mirror "+extractFTPHostFromUri(uri)+" had an unknown issue while locking.")
	        print_warning(red(" * ")+red("A problem occured while locking ")+bold(extractFTPHostFromUri(uri))+red(" mirror. Please have a look."))
	        if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']):
		    os.remove(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])
	else:
	    rc = ftp.deleteFile(etpConst['etpdatabaselockfile'])
	    if (rc):
		entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"lockDatabases: mirror "+extractFTPHostFromUri(uri)+" successfully unlocked.")
		print_info(green(" * ")+red("Succesfully unlocked ")+bold(extractFTPHostFromUri(uri))+red(" mirror."))
	        if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']):
		    os.remove(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])
	    else:
		entropyLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"lockDatabases: mirror "+extractFTPHostFromUri(uri)+" had an unknown issue while unlocking.")
	        outstat = True
	        print "\n"
	        print_warning(red(" * ")+red("A problem occured while unlocking ")+bold(extractFTPHostFromUri(uri))+red(" mirror. Please have a look."))
	ftp.closeFTPConnection()
    return outstat

def downloadLockDatabases(lock = True, mirrorList = []):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadLockDatabases: called. ")

    outstat = False
    if (mirrorList == []):
	mirrorList = etpConst['activatoruploaduris']
    for uri in mirrorList:
	if (lock):
	    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadLockDatabases: download locking -> "+extractFTPHostFromUri(uri))
	    print_info(yellow(" * ")+red("Locking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror..."),back = True)
	else:
	    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadLockDatabases: download unlocking -> "+extractFTPHostFromUri(uri))
	    print_info(yellow(" * ")+red("Unlocking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror..."),back = True)
	ftp = mirrorTools.handlerFTP(uri)
	# upload the lock file to database/%ARCH% directory
	ftp.setCWD(etpConst['etpurirelativepath'])
	# check if the lock is already there
	if (lock):
	    if (ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile'])):
	        print_info(green(" * ")+red("Download mirror at ")+bold(extractFTPHostFromUri(uri))+red(" already locked."))
	        ftp.closeFTPConnection()
	        continue
	else:
	    if (not ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile'])):
		entropyLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"downloadLockDatabases: already unlocked -> "+extractFTPHostFromUri(uri))
	        print_info(green(" * ")+red("Download mirror at ")+bold(extractFTPHostFromUri(uri))+red(" already unlocked."))
	        ftp.closeFTPConnection()
	        continue
	if (lock):
	    f = open(etpConst['packagestmpdir']+"/"+etpConst['etpdatabasedownloadlockfile'],"w")
	    f.write("database locked\n")
	    f.flush()
	    f.close()
	    rc = ftp.uploadFile(etpConst['packagestmpdir']+"/"+etpConst['etpdatabasedownloadlockfile'],ascii= True)
	    if (rc == True):
		entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadLockDatabases: successfully locked -> "+extractFTPHostFromUri(uri))
	        print_info(green(" * ")+red("Succesfully locked ")+bold(extractFTPHostFromUri(uri))+red(" download mirror."))
	    else:
		entropyLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"downloadLockDatabases: a problem occured while trying to download lock -> "+extractFTPHostFromUri(uri))
	        outstat = True
	        print "\n"
	        print_warning(red(" * ")+red("A problem occured while locking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror. Please have a look."))
	else:
	    rc = ftp.deleteFile(etpConst['etpdatabasedownloadlockfile'])
	    if (rc):
		entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadLockDatabases: successfully unlocked -> "+extractFTPHostFromUri(uri))
		print_info(green(" * ")+red("Succesfully unlocked ")+bold(extractFTPHostFromUri(uri))+red(" download mirror."))
	    else:
		entropyLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"downloadLockDatabases: a problem occured while trying to download unlock -> "+extractFTPHostFromUri(uri))
	        outstat = True
	        print "\n"
	        print_warning(red(" * ")+red("A problem occured while unlocking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror. Please have a look."))
	ftp.closeFTPConnection()
    return outstat

def getLocalDatabaseRevision():
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getLocalDatabaseRevision: called. ")
    if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaserevisionfile']):
	f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaserevisionfile'])
	rev = f.readline().strip()
	f.close()
	rev = int(rev)
	return rev
    else:
	return 0

# parse a dumped .etp file and returns etpData
def parseEtpDump(file):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"parseEtpDump: called. ")

    myEtpData = etpData.copy()
    # reset
    for i in myEtpData:
	myEtpData[i] = ""
    f = open(file,"r")
    myDump = f.readlines()
    f.close()
    for line in myDump:
	line = line.strip()
	var = line.split(":")[0]
	myEtpData[var] = line.split(var+": ")[1:][0]

    return myEtpData


# Distcc check status function
def setDistCC(status = True):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"setDistCC: called. ")
    
    f = open(etpConst['enzymeconf'],"r")
    enzymeconf = f.readlines()
    f.close()
    if (status):
	distccSwitch = "enabled"
    else:
	distccSwitch = "disabled"
    newenzymeconf = []
    for line in enzymeconf:
	if line.startswith("distcc-status|"):
	    line = "distcc-status|"+distccSwitch+"\n"
	newenzymeconf.append(line)
    f = open(etpConst['enzymeconf'],"w")
    f.writelines(newenzymeconf)
    f.flush()
    f.close()

def getDistCCHosts():

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getDistCCHosts: called.")

    f = open(etpConst['enzymeconf'],"r")
    enzymeconf = f.readlines()
    f.close()
    hostslist = []
    for line in enzymeconf:
	if line.startswith("distcc-hosts|") and (len(line.split("|")) == 2):
	    line = line.strip().split("|")[1].split()
	    for host in line:
		hostslist.append(host)
	    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getDistCCHosts: hosts list dump -> "+str(hostslist))
	    return hostslist
    entropyLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"getDistCCHosts: hosts list EMPTY.")
    return []

# @returns True if validIP (type: string) is a valid IP
# @param validIP: IP string
def isValidIP(validIP):
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getDistCCHosts: called. ")
    validIPExpr = re.compile('(([0-9]|[01]?[0-9]{2}|2([0-4][0-9]|5[0-5]))\.){3}([0-9]|[01]?[0-9]{2}|2([0-4][0-9]|5[0-5]))$')
    result = validIPExpr.match(validIP)

    if (result != None):
	return True
    return False

# you must provide a list
def addDistCCHosts(hosts):
    
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addDistCCHosts: called.")
    
    hostslist = getDistCCHosts()
    for host in hosts:
	hostslist.append(host)

    # filter dupies
    hostslist = list(set(hostslist))

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"addDistCCHosts: hostslist dump -> "+str(hostslist))

    # write back to file
    f = open(etpConst['enzymeconf'],"r")
    enzymeconf = f.readlines()
    f.close()
    newenzymeconf = []
    distcchostslinefound = False
    for line in enzymeconf:
	if line.startswith("distcc-hosts|"):
	    distcchostslinefound = True
    if (distcchostslinefound):
	for line in enzymeconf:
	    if line.startswith("distcc-hosts|"):
		hostsline = string.join(hostslist," ")
		line = "distcc-hosts|"+hostsline+"\n"
	    newenzymeconf.append(line)
    else:
	newenzymeconf = enzymeconf
	hostsline = string.join(hostslist," ")
	newenzymeconf.append("distcc-hosts|"+hostsline+"\n")

    # write distcc config file too
    f = open(etpConst['distccconf'],"w")
    f.write(hostsline+"\n")
    f.flush()
    f.close()

    f = open(etpConst['enzymeconf'],"w")
    f.writelines(newenzymeconf)
    f.flush()
    f.close()

# you must provide a list
def removeDistCCHosts(hosts):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removeDistCCHosts: called. ")

    hostslist = getDistCCHosts()
    cleanedhosts = []
    for host in hostslist:
	rmfound = False
	for rmhost in hosts:
	    if (rmhost == host):
		# remove
		rmfound = True
	if (not rmfound):
	    cleanedhosts.append(host)


    # filter dupies
    cleanedhosts = list(set(cleanedhosts))
    
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"removeDistCCHosts: cleanedhosts dump: "+cleanedhosts)
   
    # write back to file
    f = open(etpConst['enzymeconf'],"r")
    enzymeconf = f.readlines()
    f.close()
    newenzymeconf = []
    distcchostslinefound = False
    for line in enzymeconf:
	if line.startswith("distcc-hosts|"):
	    distcchostslinefound = True
    if (distcchostslinefound):
	for line in enzymeconf:
	    if line.startswith("distcc-hosts|"):
		hostsline = string.join(cleanedhosts," ")
		line = "distcc-hosts|"+hostsline+"\n"
	    newenzymeconf.append(line)
    else:
	newenzymeconf = enzymeconf
	hostsline = string.join(cleanedhosts," ")
	newenzymeconf.append("distcc-hosts|"+hostsline+"\n")

    # write distcc config file too
    f = open(etpConst['distccconf'],"w")
    f.write(hostsline+"\n")
    f.flush()
    f.close()

    f = open(etpConst['enzymeconf'],"w")
    f.writelines(newenzymeconf)
    f.flush()
    f.close()

def getDistCCStatus():
    return etpConst['distcc-status']

def isIPAvailable(ip):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"isIPAvailable: called. ")

    rc = spawnCommand("ping -c 1 "+ip, "&> /dev/null")
    if (rc):
	return False
    return True

def getFileUnixMtime(path):
    return os.path.getmtime(path)

def getFileTimeStamp(path):
    from datetime import datetime
    # used in this way for convenience
    unixtime = os.path.getmtime(path)
    humantime = datetime.fromtimestamp(unixtime)
    # format properly
    humantime = str(humantime)
    outputtime = ""
    for chr in humantime:
	if chr != "-" and chr != " " and chr != ":":
	    outputtime += chr
    return outputtime

def convertUnixTimeToMtime(unixtime):
    from datetime import datetime
    humantime = str(datetime.fromtimestamp(unixtime))
    outputtime = ""
    for chr in humantime:
	if chr != "-" and chr != " " and chr != ":":
	    outputtime += chr
    return outputtime

def convertUnixTimeToHumanTime(unixtime):
    from datetime import datetime
    humantime = str(datetime.fromtimestamp(unixtime))
    return humantime

# get a list, returns a sorted list
def alphaSorter(seq):
    def stripter(s, goodchrs):
        badchrs = set(s)
        for c in goodchrs:
            if c in badchrs:
                badchrs.remove(c)
        badchrs = ''.join(badchrs)
        return s.strip(badchrs)
    
    def chr_index(value, sortorder):
        result = []
        for c in stripter(value, order):
            cindex = sortorder.find(c)
            if cindex == -1:
                cindex = len(sortorder)+ord(c)
            result.append(cindex)
        return result
    
    order = ( '0123456789AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz' )
    deco = [(chr_index(a, order), a) for a in seq]
    deco.sort()
    return list(x[1] for x in deco)

# Temporary files cleaner
def cleanup(options):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"cleanup: with options: "+str(options))

    toCleanDirs = [ etpConst['packagestmpdir'], etpConst['logdir'] ]
    counter = 0

    for dir in toCleanDirs:
        print_info(red(" * ")+"Cleaning "+yellow(dir)+" directory...", back = True)
	dircontent = os.listdir(dir)
	if dircontent != []:
	    for data in dircontent:
		spawnCommand("rm -rf "+dir+"/"+data)
		counter += 1

    print_info(green(" * ")+"Cleaned: "+str(counter)+" files and directories")

def mountProc():
    # check if it's already mounted
    procfiles = os.listdir("/proc")
    if len(procfiles) > 2:
	return True
    else:
	spawnCommand("mount -t proc proc /proc", "&> /dev/null")
	return True

def umountProc():
    # check if it's already mounted
    procfiles = os.listdir("/proc")
    if len(procfiles) > 2:
	spawnCommand("umount /proc", " &> /dev/null")
	spawnCommand("umount /proc", " &> /dev/null")
	spawnCommand("umount /proc", " &> /dev/null")
	return True
    else:
	return True

def askquestion(prompt):
    responses, colours = ["Yes", "No"], [green, red]
    print green(prompt),
    try:
	while True:
	    response=raw_input("["+"/".join([colours[i](responses[i]) for i in range(len(responses))])+"] ")
	    for key in responses:
		# An empty response will match the first value in responses.
		if response.upper()==key[:len(response)].upper():
		    return key
		    print "I cannot understand '%s'" % response,
    except (EOFError, KeyboardInterrupt):
	print "Interrupted."
	sys.exit(100)