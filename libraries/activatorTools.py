#!/usr/bin/python
'''
    # DESCRIPTION:
    # generic tools for enzyme application

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

from entropyConstants import *
from entropyTools import *

import sys
import os
import commands
import string

def sync(options):

    # translate %ARCH%
    etpConst['packagessuploaddir'] = translateArchFromUname(etpConst['packagessuploaddir'])
    etpConst['packagesdatabasedir'] = translateArchFromUname(etpConst['packagesdatabasedir'])
    etpConst['packagesbindir'] = translateArchFromUname(etpConst['packagesbindir'])
    etpConst['binaryurirelativepath'] = translateArchFromUname(etpConst['binaryurirelativepath'])
    etpConst['etpurirelativepath'] = translateArchFromUname(etpConst['etpurirelativepath'])

    print_info(green(" * ")+red("Collecting local binary packages..."),back = True)
    localtbz2counter = 0
    localTbz2Files = []
    for file in os.listdir(etpConst['packagessuploaddir']):
	if file.endswith(".tbz2"):
	    localTbz2Files.append([ file , getFileTimeStamp(etpConst['packagessuploaddir']+"/"+file) ])
	    localtbz2counter += 1
    print_info(green(" * ")+red("Packages directory:\t")+bold(str(localtbz2counter))+red(" packages ready for the upload."))

    # INFO: the Entropy repository will be, synced to the latest on the server, compressed, uploaded and kept there?
    print_info(green(" * ")+red("Collecting local Entropy repository entries..."),back = True)
    localtetpcounter = 0
    localEtpFiles = []
    for (dir, sub, files) in os.walk(etpConst['packagesdatabasedir']):
	localEtpFiles.append(dir)
	for file in files:
	    localEtpFiles.append(dir+"/"+file)
	    if file.endswith(etpConst['extension']):
		localtetpcounter += 1
    print_info(green(" * ")+red("Entropy directory:\t")+bold(str(localtetpcounter))+red(" specification files available."))

    # packages relative uri: etpConst['binaryurirelativepath']
    # entropy relative uri : etpConst['etpurirelativepath']
    #print "deleting file: XML-XSLT-0.48.tbz2"
    #rc = ftp.deleteFile("XML-XSLT-0.48.tbz2")
    #print rc
    #print "uploading file..."
    #rc = ftp.uploadFile("/var/lib/entropy/store/x86/alsa-lib-1.0.14_rc3.tbz2")
    #print str(rc)

    # For each URI do the same thing
    for uri in etpConst['activatoruploaduris']:
	ftp = activatorFTP(uri)
	print "Listing the content of: "+ftp.getFTPHost()
	print "at port: "+str(ftp.getFTPPort())
	print "in dir: "+ftp.getFTPDir()
	print ftp.listFTPdir()
	print ftp.spawnFTPCommand("mdtm index.htm")
	ftp.closeFTPConnection()

