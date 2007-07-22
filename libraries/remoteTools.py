#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy Mirrors interface

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

# Never do "import portage" here, please use entropyTools binding
# EXIT STATUSES: 700-799

from entropyConstants import *
from outputTools import *
import entropyTools

# Logging initialization
import logTools
remoteLog = logTools.LogFile(level=etpConst['remoteloglevel'],filename = etpConst['remotelogfile'], header = "[REMOTE/HTTP]")
# example: mirrorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"testFuncton: called.")

import timeoutsocket
import urllib2
timeoutsocket.setDefaultSocketTimeout(60)

# Get checksum of a package by running md5sum remotely (using php helpers)
# @returns hex: if the file exists
# @returns None: if the server does not support HTTP handlers
# @returns False: if the file is not found
def getRemotePackageChecksum(serverName,filename):
    remoteLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getRemotePackageChecksum: called.")
    # etpHandlers['md5sum'] is the command
    # create the request
    try:
	url = etpRemoteSupport[servername]
    except:
	# not found, does not support HTTP handlers
	return None
    
    request = url+etpHandlers['md5sum']+filename
    remoteLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getRemotePackageChecksum: requested url -> "+request)
    
    # now pray the server
    try:
        file = urllib2.urlopen(request)
        result = file.readline().strip()
        return result
    except: # no HTTP support?
	return None


###################################################
# HTTP/FTP equo/download functions
###################################################

def downloadData(url,pathToSave, bufferSize = 8192, checksum = True):
    remoteLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadFile: called.")
    
    try:
        remotefile = urllib2.urlopen(url)
    except Exception, e:
	remoteLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"downloadFile: Exception caught for: "+str(url)+" -> "+str(e))
	return "-3"
    try:
	maxsize = remotefile.headers.get("content-length")
    except:
	maxsize = 0
	pass
    localfile = open(pathToSave,"w")
    rsx = "x"
    while rsx != '':
	rsx = remotefile.read(bufferSize)
	__downloadFileCommitData(localfile,rsx,maxsize = maxsize)
    localfile.flush()
    localfile.close()
    #print_info("",back = True)
    if checksum:
	# return digest
	return entropyTools.md5sum(pathToSave)
    else:
	# return -2
	return "-2"

###################################################
# HTTP/FTP equo INTERNAL FUNCTIONS
###################################################
def __downloadFileCommitData(f, buf, output = True, maxsize = 0):
    # writing file buffer
    f.write(buf)
    # update progress
    if output:
        kbytecount = float(f.tell())/1024
	maxsize = int(maxsize)
	if maxsize > 0:
	    maxsize = float(int(maxsize))/1024
        # create text
        currentText = yellow("        <-> Downloading: ")+green(str(round(kbytecount,1)))+"/"+red(str(round(maxsize,1)))+" kB"
        # print !
        print_info(currentText,back = True)