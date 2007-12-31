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
import random

# Logging initialization
import logTools
remoteLog = logTools.LogFile(level=etpConst['remoteloglevel'],filename = etpConst['remotelogfile'], header = "[REMOTE/HTTP]")

import socket
import urllib2

# Get checksum of a package by running md5sum remotely (using php helpers)
# @returns hex: if the file exists
# @returns None: if the server does not support HTTP handlers
# @returns None: if the file is not found
def getRemotePackageChecksum(servername, filename, branch):
    # etpHandlers['md5sum'] is the command
    # create the request
    try:
	url = etpRemoteSupport[servername]
    except:
	# not found, does not support HTTP handlers
	return None
    
    # does the package has "#" (== tag) ? hackish thing that works
    filename = filename.replace("#","%23")
    # "+"
    filename = filename.replace("+","%2b")
    
    request = url+etpHandlers['md5sum']+filename+"&branch="+branch
    
    # now pray the server
    try:
        if etpConst['proxy']:
            proxy_support = urllib2.ProxyHandler(etpConst['proxy'])
            opener = urllib2.build_opener(proxy_support)
            urllib2.install_opener(opener)
        item = urllib2.urlopen(request)
        result = item.readline().strip()
        return result
    except: # no HTTP support?
	return None

# Get the content of an online page
# @returns content: if the file exists
# @returns False: if the file is not found
def getOnlineContent(url):

    socket.setdefaulttimeout(60)
    # now pray the server
    try:
        if etpConst['proxy']:
            proxy_support = urllib2.ProxyHandler(etpConst['proxy'])
            opener = urllib2.build_opener(proxy_support)
            urllib2.install_opener(opener)
        item = urllib2.urlopen(url)
        result = item.readlines()
	if (not result):
            socket.setdefaulttimeout(2)
	    return False
        socket.setdefaulttimeout(2)
        return result
    except:
        socket.setdefaulttimeout(2)
	return False

# Error reporting function
# @input: error string (please use repr())
# @returns bool: True if ok. False if not.
# @returns False: if the file is not found
def reportApplicationError(errorstring):
    socket.setdefaulttimeout(60)
    outstring = ""
    for char in errorstring:
        if char == " ":
	    char = "%20"
	outstring += char
    outstring = outstring.split("\n")
    outstring = '<br>'.join(outstring)
    url = etpHandlers['errorsend']+outstring
    # now pray the server
    try:
        if etpConst['proxy']:
            proxy_support = urllib2.ProxyHandler(etpConst['proxy'])
            opener = urllib2.build_opener(proxy_support)
            urllib2.install_opener(opener)
        file = urllib2.urlopen(url)
        result = file.readlines()
	socket.setdefaulttimeout(2)
        return result
    except:
	socket.setdefaulttimeout(2)
	return False

###################################################
# HTTP/FTP equo packages download class
###################################################
# ATTENTION: this functions fills global variable etpFileTransferMetadata !!
# take care of that

class urlFetcher(TextInterface):

    def __init__(self, url, pathToSave, checksum = True, showSpeed = True):

        self.url = url
        self.url = self.encodeUrl(self.url)
        self.pathToSave = pathToSave
        self.checksum = checksum
        self.showSpeed = showSpeed
        self.bufferSize = 8192
        self.status = None
        self.remotefile = None
        self.localfile = None
        self.downloadedsize = 0
        self.average = 0
        self.remotesize = 0
        # transfer status data
        self.gather = 0
        self.datatransfer = 0
        self.elapsed = etpFileTransfer['elapsed']
        self.transferpollingtime = etpFileTransfer['transferpollingtime']

        # setup proxy, doing here because config is dynamic
        if etpConst['proxy']:
            proxy_support = urllib2.ProxyHandler(etpConst['proxy'])
            opener = urllib2.build_opener(proxy_support)
            urllib2.install_opener(opener)
        #FIXME else: unset opener??

    def encodeUrl(self, url):
        url = url.replace("#","%23")
        return url

    def download(self):
        if self.showSpeed:
            self.speedUpdater = entropyTools.TimeScheduled(
                        self.updateSpeedInfo,
                        self.transferpollingtime
            )
            self.speedUpdater.setName("download::"+self.url+str(random.random())) # set unique ID to thread, hopefully
            self.speedUpdater.start()

        # set timeout
        socket.setdefaulttimeout(60)

        # go download slave!

        # handle user stupidity
        try:
            self.remotefile = urllib2.urlopen(self.url)
        except KeyboardInterrupt:
            self.close()
            raise KeyboardInterrupt
        except Exception, e:
            self.close()
            self.status = "-3"
            return self.status

        # get file size if available
        try:
            self.remotesize = self.remotefile.headers.get("content-length")
        except:
            pass

        if self.remotesize > 0:
            self.remotesize = float(int(self.remotesize))/1024

        self.localfile = open(self.pathToSave,"w")
        rsx = "x"
        while rsx != '':
            rsx = self.remotefile.read(self.bufferSize)
            self.commitData(rsx)
            if self.showSpeed:
                self.updateProgress()
        self.localfile.flush()
        self.localfile.close()

        # kill thread
        self.close()

        if self.checksum:
            self.status = entropyTools.md5sum(self.pathToSave)
            return self.status
        else:
            self.status = "-2"
            return self.status

    def commitData(self, mybuffer):
        # writing file buffer
        self.localfile.write(mybuffer)
        # update progress info
        self.downloadedsize = self.localfile.tell()
        kbytecount = float(self.downloadedsize)/1024
        self.average = int((kbytecount/self.remotesize)*100)

    # reimplemented from TextInterface
    def updateProgress(self):

        currentText = darkred("    <-> Downloading: ")+darkgreen(str(round(float(self.downloadedsize)/1024,1)))+"/"+red(str(round(self.remotesize,1)))+" kB"
        # create progress bar
        barsize = 10
        bartext = "["
        curbarsize = 1
        #print average
        averagesize = (self.average*barsize)/100
        #print averagesize
        for y in range(averagesize):
            curbarsize += 1
            bartext += "="
        bartext += ">"
        diffbarsize = barsize-curbarsize
        for y in range(diffbarsize):
            bartext += " "
        if (self.showSpeed):
            self.gather = self.downloadedsize
            bartext += "] => "+str(entropyTools.bytesIntoHuman(self.datatransfer))+"/sec"
        else:
            bartext += "]"
        average = str(self.average)
        if len(average) < 2:
            average = " "+average
        currentText += "    <->  "+average+"% "+bartext
        # print !
        print_info(currentText,back = True)

    def close(self):
        if self.showSpeed:
            self.speedUpdater.kill()
        socket.setdefaulttimeout(2)

    def updateSpeedInfo(self):
        self.elapsed += self.transferpollingtime
        # we have the diff size
        self.datatransfer = self.gather / self.elapsed

