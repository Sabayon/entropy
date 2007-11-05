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
from clientConstants import *
from outputTools import *
import entropyTools
import string

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
# @returns None: if the file is not found
def getRemotePackageChecksum(serverName,filename, branch):
    remoteLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getRemotePackageChecksum: called.")
    # etpHandlers['md5sum'] is the command
    # create the request
    try:
	url = etpRemoteSupport[servername]
    except:
	# not found, does not support HTTP handlers
	return None
    
    # does the package has "#" (== tag) ? hackish thing that works
    tag = entropyTools.dep_gettag(filename)
    tagstring = ''
    if tag:
	filename = entropyTools.remove_tag(filename)
	tagstring = "&tag="+tag
    
    request = url+etpHandlers['md5sum']+filename+"&branch="+branch+tagstring
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

def downloadData(url, pathToSave, bufferSize = 8192, checksum = True, showSpeed = True):
    remoteLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadFile: called.")

    import re
    # substitute tagged filenames with URL encoded code
    out = re.subn('#','%23',url)
    url = out[0]

    # start scheduler
    if (showSpeed):
	etpFileTransfer['datatransfer'] = 0
	etpFileTransfer['oldgather'] = 0
	etpFileTransfer['gather'] = 0
	speedUpdater = entropyTools.TimeScheduled(__updateSpeedInfo,etpFileTransfer['transferpollingtime'])
	speedUpdater.start()
    
    rc = "-1"
    try:
        remotefile = urllib2.urlopen(url)
    except Exception, e:
	remoteLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"downloadFile: Exception caught for: "+str(url)+" -> "+str(e))
	if (showSpeed):
	    speedUpdater.kill()
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
	__downloadFileCommitData(localfile, rsx, maxsize = maxsize, showSpeed = showSpeed)
    localfile.flush()
    localfile.close()
    #print_info("",back = True)
    if checksum:
	# return digest
	rc = entropyTools.md5sum(pathToSave)
    else:
	# return -2
	rc = "-2"

    if (showSpeed):
	speedUpdater.kill()

    return rc

# Get the content of an online page
# @returns content: if the file exists
# @returns False: if the file is not found
def getOnlineContent(url):
    remoteLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"getOnlineContent: called. Requested URL -> "+str(url))

    # now pray the server
    try:
        file = urllib2.urlopen(url)
        result = file.readlines()
	if (not result):
	    return False
        return result
    except:
	return False

# Error reporting function
# @input: error string (please use repr())
# @returns bool: True if ok. False if not.
# @returns False: if the file is not found
def reportApplicationError(errorstring):
    remoteLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"reportApplicationError: called. Requested string -> "+str(errorstring))
    outstring = ""
    for char in errorstring:
        if char == " ":
	    char = "%20"
	outstring += char
    outstring = outstring.split("\n")
    outstring = string.join(outstring,"<br>")
    url = etpHandlers['errorsend']+outstring
    # now pray the server
    try:
        file = urllib2.urlopen(url)
        result = file.readlines()
        return result
    except:
	return False

###################################################
# HTTP/FTP equo INTERNAL FUNCTIONS
###################################################
def __downloadFileCommitData(f, buf, output = True, maxsize = 0, showSpeed = True):
    # writing file buffer
    f.write(buf)
    # update progress
    if output:
        kbytecount = float(f.tell())/1024
	maxsize = int(maxsize)
	if maxsize > 0:
	    maxsize = float(int(maxsize))/1024
	average = int((kbytecount/maxsize)*100)
        # create text
        currentText = darkred("    <-> Downloading: ")+darkgreen(str(round(kbytecount,1)))+"/"+red(str(round(maxsize,1)))+" kB"
	# create progress bar
	barsize = 10
	bartext = "["
	curbarsize = 1
	#print average
	averagesize = (average*barsize)/100
	#print averagesize
	for y in range(averagesize):
	    curbarsize += 1
	    bartext += "="
	bartext += ">"
	diffbarsize = barsize-curbarsize
	for y in range(diffbarsize):
	    bartext += " "
	if (showSpeed):
	    etpFileTransfer['gather'] = f.tell()
	    bartext += "] => "+str(entropyTools.bytesIntoHuman(etpFileTransfer['datatransfer']))+"/sec"
	else:
	    bartext += "]"
	average = str(average)
	if len(average) < 2:
	    average = " "+average
	currentText += "    <->  "+average+"% "+bartext
        # print !
        print_info(currentText,back = True)


def __updateSpeedInfo():
    diff = etpFileTransfer['gather'] - etpFileTransfer['oldgather']
    # we have the diff size
    etpFileTransfer['datatransfer'] = diff / etpFileTransfer['transferpollingtime']
    etpFileTransfer['oldgather'] = etpFileTransfer['gather']