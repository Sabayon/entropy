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
import urllib
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
    file = urllib.urlopen(request)
    result = file.readline().strip()
    return result
    