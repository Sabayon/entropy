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
from output import *
from entropyConstants import *

import re
import sys
import random
import commands

# Instantiate the databaseStatus:
import databaseTools
dbStatus = databaseTools.databaseStatus()

# EXIT STATUSES: 100-199

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

def writechar(char):
	sys.stdout.write(char); sys.stdout.flush()

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
    return atom

# Tool to run commands
def spawnCommand(command, redirect = None):
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

    uriDbInfo = []
    for uri in etpConst['activatoruploaduris']:
	ftp = databaseTools.handlerFTP(uri)
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
		os.system("rm -f "+etpConst['packagestmpdir']+etpConst['etpdatabaserevisionfile'])
	    else:
		revision = 0
	else:
	    print "database file not avail"
	    # then set mtime to 0 and quit
	    revision = 0
	info = [uri+"/"+etpConst['etpurirelativepath']+etpConst['etpdatabasefilegzip'],revision]
	uriDbInfo.append(info)
	ftp.closeFTPConnection()

    return uriDbInfo

def syncRemoteDatabases(noUpload = False):

    print_info(green(" * ")+red("Checking the status of the remote Entropy Database Repository"))
    remoteDbsStatus = getEtpRemoteDatabaseStatus()
    print_info(green(" * ")+red("Remote Entropy Database Repository Status:"))
    for dbstat in remoteDbsStatus:
	print_info(green("\t Host:\t")+bold(extractFTPHostFromUri(dbstat[0])))
	print_info(red("\t  * Database revision: ")+blue(str(dbstat[1])))

    # check if the local DB exists
    if os.path.isfile(etpConst['etpdatabasefilepath']) and os.path.isfile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile']):
	# file exist, get revision
	f = open(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'],"r")
	etpDbLocalRevision = int(f.readline().strip())
	f.close()
    else:
	etpDbLocalRevision = 0
    
    downloadLatest = []
    uploadLatest = False
    uploadList = []
    
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
	print_info(green(" * ")+red("Online database does not need to be updated."))
        return

    # now run the selected task!
    if (downloadLatest != []):
	# match the proper URI
	for uri in etpConst['activatoruploaduris']:
	    if downloadLatest[0].startswith(uri):
		downloadLatest[0] = uri
	downloadDatabase(downloadLatest[0])
	
    if (uploadLatest) and (not noUpload):
	print_info(green(" * ")+red("Starting to update the needed mirrors ..."))
	_uploadList = []
	for uri in etpConst['activatoruploaduris']:
	    for list in uploadList:
		if list[0].startswith(uri):
		    list[0] = uri
		    break
	    _uploadList.append(list[0])
	
	uploadDatabase(_uploadList)
	print_info(green(" * ")+red("All the mirrors have been updated."))

    remoteDbsStatus = getEtpRemoteDatabaseStatus()
    print_info(green(" * ")+red("Remote Entropy Database Repository Status:"))
    for dbstat in remoteDbsStatus:
	print_info(green("\t Host:\t")+bold(extractFTPHostFromUri(dbstat[0])))
	print_info(red("\t  * Database revision: ")+blue(str(dbstat[1])))


def uploadDatabase(uris):

    # our fancy compressor :-)
    import gzip
    
    for uri in uris:
	downloadLockDatabases(True,[uri])
	
	print_info(green(" * ")+red("Uploading database to ")+bold(extractFTPHostFromUri(uri))+red(" ..."))
	print_info(green(" * ")+red("Connecting to ")+bold(extractFTPHostFromUri(uri))+red(" ..."), back = True)
	ftp = databaseTools.handlerFTP(uri)
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
	if (rc.startswith("226")):
	    print_info(green(" * ")+red("Upload of ")+bold(etpConst['etpdatabasefilegzip'])+red(" completed."))
	else:
	    print_warning(yellow(" * ")+red("Cannot properly upload to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
	
	# remove the gzip
	os.remove(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasefilegzip'])
	
	print_info(green(" * ")+red("Uploading file ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'])+red(" ..."), back = True)
	# uploading revision file
	rc = ftp.uploadFile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'],True)
	if (rc.startswith("226")):
	    print_info(green(" * ")+red("Upload of ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'])+red(" completed."))
	else:
	    print_warning(yellow(" * ")+red("Cannot properly upload to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))

	# generate digest
	hexdigest = digestFile(etpConst['etpdatabasefilepath'])
	f = open(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'],"w")
	f.write(hexdigest+"  "+etpConst['etpdatabasehashfile']+"\n")
	f.flush()
	f.close()

	# upload digest
	print_info(green(" * ")+red("Uploading file ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'])+red(" ..."), back = True)
	rc = ftp.uploadFile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'],True)
	if (rc.startswith("226")):
	    print_info(green(" * ")+red("Upload of ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'])+red(" completed. Disconnecting."))
	else:
	    print_warning(yellow(" * ")+red("Cannot properly upload to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
	
	downloadLockDatabases(False,[uri])


def downloadDatabase(uri):
    
    import gzip
    
    print_info(green(" * ")+red("Downloading database from ")+bold(extractFTPHostFromUri(uri))+red(" ..."))
    print_info(green(" * ")+red("Connecting to ")+bold(extractFTPHostFromUri(uri))+red(" ..."), back = True)
    ftp = databaseTools.handlerFTP(uri)
    print_info(green(" * ")+red("Changing directory to ")+bold(etpConst['etpurirelativepath'])+red(" ..."), back = True)
    ftp.setCWD(etpConst['etpurirelativepath'])
    
    
    # downloading database file
    print_info(green(" * ")+red("Downloading file to ")+bold(etpConst['etpdatabasefilegzip'])+red(" ..."), back = True)
    rc = ftp.downloadFile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasefilegzip'],os.path.dirname(etpConst['etpdatabasefilepath']))
    if (rc.startswith("226")):
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
    print_info(green(" * ")+red("Downloading file to ")+bold(etpConst['etpdatabaserevisionfile'])+red(" ..."), back = True)
    rc = ftp.downloadFile(etpConst['etpdatabaserevisionfile'],os.path.dirname(etpConst['etpdatabasefilepath']),True)
    if (rc.startswith("226")):
	print_info(green(" * ")+red("Download of ")+bold(etpConst['etpdatabaserevisionfile'])+red(" completed."))
    else:
	print_warning(yellow(" * ")+red("Cannot properly download to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))
    
    # downlading digest
    print_info(green(" * ")+red("Downloading file to ")+bold(etpConst['etpdatabasehashfile'])+red(" ..."), back = True)
    rc = ftp.downloadFile(etpConst['etpdatabasehashfile'],os.path.dirname(etpConst['etpdatabasefilepath']),True)
    if (rc.startswith("226")):
	print_info(green(" * ")+red("Download of ")+bold(etpConst['etpdatabasehashfile'])+red(" completed. Disconnecting."))
    else:
	print_warning(yellow(" * ")+red("Cannot properly download to ")+bold(extractFTPHostFromUri(uri))+red(". Please check."))

    os.system("rm -f " + etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasefilegzip']+" &> /dev/null")


# Reports in a list form the lock status of the mirrors
# @ [ uri , True/False, True/False ] --> True = locked, False = unlocked
# @ the second parameter is referred to upload locks, while the second to download ones
def getMirrorsLock():
    # parse etpConst['activatoruploaduris']
    dbstatus = []
    for uri in etpConst['activatoruploaduris']:
	data = [ uri, False , False ]
	ftp = databaseTools.handlerFTP(uri)
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


# tar.bz2 compress function...
def compressTarBz2(storepath,pathtocompress):
    cmd = "tar cjf "+storepath+" -C "+pathtocompress
    rc = os.system(cmd+" &> /dev/null")
    return rc

# tar.bz2 uncompress function...
def uncompressTarBz2(filepath, extractPath = None):
    if extractPath is None:
	extractPath = os.path.dirname(filepath)
    cmd = "tar xjf "+filepath+" -C "+extractPath
    rc = os.system(cmd+" &> /dev/null")
    return rc

# FIXME: improve support by reading a line at a time
def digestFile(filepath):
    import md5
    df = open(filepath,"r")
    content = df.readlines()
    df.close()
    digest = md5.new()
    for line in content:
	digest.update(line)
    return digest.hexdigest()

def bytesIntoHuman(bytes):
    bytes = str(bytes)
    kbytes = str(int(bytes)/1024)
    if len(kbytes) > 3:
	kbytes = str(int(kbytes)/1024)
	kbytes += "MB"
    else:
	kbytes += "kB"
    return kbytes

# hide password from full ftp URI
def hideFTPpassword(uri):
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
    outstat = False
    if (mirrorList == []):
	mirrorList = etpConst['activatoruploaduris']
    for uri in mirrorList:
	if (lock):
	    print_info(yellow(" * ")+red("Locking ")+bold(extractFTPHostFromUri(uri))+red(" mirror..."),back = True)
	else:
	    print_info(yellow(" * ")+red("Unlocking ")+bold(extractFTPHostFromUri(uri))+red(" mirror..."),back = True)
	ftp = databaseTools.handlerFTP(uri)
	# upload the lock file to database/%ARCH% directory
	ftp.setCWD(etpConst['etpurirelativepath'])
	# check if the lock is already there
	if (lock):
	    if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
	        print_info(green(" * ")+red("Mirror database at ")+bold(extractFTPHostFromUri(uri))+red(" already locked."))
	        ftp.closeFTPConnection()
	        continue
	else:
	    if (not ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
	        print_info(green(" * ")+red("Mirror database at ")+bold(extractFTPHostFromUri(uri))+red(" already unlocked."))
	        ftp.closeFTPConnection()
	        continue
	if (lock):
	    f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'],"w")
	    f.write("database locked\n")
	    f.flush()
	    f.close()
	    rc = ftp.uploadFile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'],ascii= True)
	    if (rc.startswith("226")):
	        print_info(green(" * ")+red("Succesfully locked ")+bold(extractFTPHostFromUri(uri))+red(" mirror."))
	    else:
	        outstat = True
	        print "\n"
	        print_warning(red(" * ")+red("A problem occured while locking ")+bold(extractFTPHostFromUri(uri))+red(" mirror. Please have a look."))
	        if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']):
		    os.remove(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])
	else:
	    rc = ftp.deleteFile(etpConst['etpdatabaselockfile'])
	    if (rc):
		print_info(green(" * ")+red("Succesfully unlocked ")+bold(extractFTPHostFromUri(uri))+red(" mirror."))
	        if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']):
		    os.remove(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])
	    else:
	        outstat = True
	        print "\n"
	        print_warning(red(" * ")+red("A problem occured while unlocking ")+bold(extractFTPHostFromUri(uri))+red(" mirror. Please have a look."))
	ftp.closeFTPConnection()
    return outstat

def downloadLockDatabases(lock = True, mirrorList = []):
    outstat = False
    if (mirrorList == []):
	mirrorList = etpConst['activatoruploaduris']
    for uri in mirrorList:
	if (lock):
	    print_info(yellow(" * ")+red("Locking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror..."),back = True)
	else:
	    print_info(yellow(" * ")+red("Unlocking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror..."),back = True)
	ftp = databaseTools.handlerFTP(uri)
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
	        print_info(green(" * ")+red("Download mirror at ")+bold(extractFTPHostFromUri(uri))+red(" already unlocked."))
	        ftp.closeFTPConnection()
	        continue
	if (lock):
	    f = open(etpConst['packagestmpdir']+"/"+etpConst['etpdatabasedownloadlockfile'],"w")
	    f.write("database locked\n")
	    f.flush()
	    f.close()
	    rc = ftp.uploadFile(etpConst['packagestmpdir']+"/"+etpConst['etpdatabasedownloadlockfile'],ascii= True)
	    if (rc.startswith("226")):
	        print_info(green(" * ")+red("Succesfully locked ")+bold(extractFTPHostFromUri(uri))+red(" download mirror."))
	    else:
	        outstat = True
	        print "\n"
	        print_warning(red(" * ")+red("A problem occured while locking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror. Please have a look."))
	else:
	    rc = ftp.deleteFile(etpConst['etpdatabasedownloadlockfile'])
	    if (rc):
		print_info(green(" * ")+red("Succesfully unlocked ")+bold(extractFTPHostFromUri(uri))+red(" download mirror."))
	    else:
	        outstat = True
	        print "\n"
	        print_warning(red(" * ")+red("A problem occured while unlocking ")+bold(extractFTPHostFromUri(uri))+red(" download mirror. Please have a look."))
	ftp.closeFTPConnection()
    return outstat

def getLocalDatabaseRevision():
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
    f = open(etpConst['enzymeconf'],"r")
    enzymeconf = f.readlines()
    f.close()
    hostslist = []
    for line in enzymeconf:
	if line.startswith("distcc-hosts|") and (len(line.split("|")) == 2):
	    line = line.strip().split("|")[1].split()
	    for host in line:
		hostslist.append(host)
	    return hostslist
    return []

# you must provide a list
def addDistCCHosts(hosts):
    
    # FIXME: add host validation
    hostslist = getDistCCHosts()
    for host in hosts:
	hostslist.append(host)

    # filter dupies
    hostslist = list(set(hostslist))
   
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
    
    # FIXME: add host validation
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
    rc = os.system("ping -c 1 "+ip+" &> /dev/null")
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

    toCleanDirs = [ etpConst['packagestmpdir'], etpConst['logdir'] ]
    counter = 0

    for dir in toCleanDirs:
        print_info(red(" * ")+"Cleaning "+yellow(dir)+" directory...", back = True)
	dircontent = os.listdir(dir)
	if dircontent != []:
	    for data in dircontent:
		os.system("rm -rf "+dir+"/"+data)
		counter += 1

    print_info(green(" * ")+"Cleaned: "+str(counter)+" files and directories")

def mountProc():
    # check if it's already mounted
    procfiles = os.listdir("/proc")
    if len(procfiles) > 2:
	return True
    else:
	os.system("mount -t proc proc /proc &> /dev/null")
	return True

def umountProc():
    # check if it's already mounted
    procfiles = os.listdir("/proc")
    if len(procfiles) > 2:
	os.system("umount /proc &> /dev/null")
	os.system("umount /proc &> /dev/null")
	os.system("umount /proc &> /dev/null")
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

def print_error(msg):
    print red(">>")+" "+msg

def print_info(msg, back = False):
    writechar("\r                                                                                                           \r")
    if (back):
	writechar("\r"+green(">>")+" "+msg)
	return
    print green(">>")+" "+msg

def print_warning(msg):
    print yellow(">>")+" "+msg

def print_generic(msg): # here we'll wrap any nice formatting
    print msg