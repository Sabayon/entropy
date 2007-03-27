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

    # For each URI do the same thing
    for uri in etpConst['activatoruploaduris']:
	ftp = activatorFTP(uri)
	print "Listing the content of: "+ftp.getFTPHost()
	print "at port: "+str(ftp.getFTPPort())
	print "in dir: "+ftp.getFTPDir()
	#print ftp.getFileSize("index.htm")
	list = ftp.getRoughList()
	
	#print ftp.spawnFTPCommand("mdtm index.htm")
	ftp.closeFTPConnection()

    sys.exit(0)

    # sync the local repository with the remote ones
    syncRemoteDatabases()

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




def packages(options):

    # Options available for all the packages submodules
    myopts = options[1:]
    activatorRequestAsk = False
    activatorRequestPretend = False
    for opt in myopts:
	if (opt == "--ask"):
	    activatorRequestAsk = True
	elif (opt == "--pretend"):
	    activatorRequestPretend = True

    if (options[0] == "sync"):
	print_info(green(" * ")+red("Starting ")+bold("binary")+yellow(" packages")+red(" syncronization across servers ..."))
	for uri in etpConst['activatoruploaduris']:

	    print_info(green(" * ")+yellow("Working on ")+bold(extractFTPHostFromUri(uri)+red(" mirror.")))
	    print_info(green(" * ")+yellow("Local Statistics"))
	    print_info(green(" * ")+red("Calculating packages in ")+bold(etpConst['packagessuploaddir'])+red(" ..."), back = True)
	    uploadCounter = 0
	    toBeUploaded = [] # parse etpConst['packagessuploaddir']
	    for tbz2 in os.listdir(etpConst['packagessuploaddir']):
		if tbz2.endswith(".tbz2"):
		    toBeUploaded.append(tbz2)
		    uploadCounter += 1
	    print_info(green(" * ")+red("Upload directory:\t\t")+bold(str(uploadCounter))+red(" files ready."))
	    toBeDownloaded = [] # parse etpConst['packagesbindir']
	    print_info(green(" * ")+red("Calculating packages in ")+bold(etpConst['packagesbindir'])+red(" ..."), back = True)
	    packageCounter = 0
	    for tbz2 in os.listdir(etpConst['packagesbindir']):
		if tbz2.endswith(".tbz2"):
		    toBeDownloaded.append(tbz2)
		    packageCounter += 1
	    print_info(green(" * ")+red("Packages directory:\t")+bold(str(packageCounter))+red(" files ready."))
	    
	    print_info(green(" * ")+yellow("Fetching remote statistics..."), back = True)
	    ftp = activatorFTP(uri)
	    ftp.setCWD(etpConst['binaryurirelativepath'])
	    remotePackages = ftp.listFTPdir()
	    remotePackagesInfo = ftp.getRoughList()
	    ftp.closeFTPConnection()

	    print_info(green(" * ")+yellow("Remote statistics"))
	    remoteCounter = 0
	    for tbz2 in remotePackages:
		if tbz2.endswith(".tbz2"):
		    remoteCounter += 1
	    print_info(green(" * ")+red("Remote packages:\t\t")+bold(str(remoteCounter))+red(" files stored."))
	    
	    print_info(green(" * ")+yellow("Calculating..."))
	    uploadQueue = []
	    downloadQueue = []
	    
	    # Fill uploadQueue and if something weird is found, add the packages to downloadQueue
	    # --> UPLOAD
	    for localPackage in toBeUploaded:
		pkgfound = False
		for remotePackage in remotePackages:
		    if localPackage == remotePackage:
			pkgfound = True
			# it's already on the mirror, but... is its size correct??
			localSize = int(os.stat(etpConst['packagessuploaddir']+"/"+localPackage)[6])
			remoteSize = 0
			for file in remotePackagesInfo:
			    if file.split()[8] == remotePackage:
				remoteSize = int(file.split()[4])
			if (localSize != remoteSize) and (localSize != 0):
			    # size does not match, adding to the upload queue
			    uploadQueue.append(localPackage)
			break
		
		if (not pkgfound):
		    # this means that the local package does not exist
		    # so, we need to download it
		    uploadQueue.append(localPackage)
	    
	    # Fill downloadQueue and if something weird is found, add the packages to uploadQueue
	    for remotePackage in remotePackages:
		pkgfound = False
		for localPackage in toBeDownloaded:
		    if localPackage == remotePackage:
			pkgfound = True
			# it's already on the mirror, but... is its size correct??
			localSize = int(os.stat(etpConst['packagesbindir']+"/"+localPackage)[6])
			remoteSize = 0
			for file in remotePackagesInfo:
			    if file.split()[8] == remotePackage:
				remoteSize = int(file.split()[4])
			if (localSize != remoteSize) and (localSize != 0):
			    # size does not match, adding to the download queue
			    downloadQueue.append(remotePackage)
			break
		
		if (not pkgfound):
		    # this means that the local package does not exist
		    # so, we need to download it
		    downloadQueue.append(remotePackage)
	    
	    # filter duplicates
	    uploadQueue = list(set(uploadQueue))
	    downloadQueue = list(set(downloadQueue))
	    moveQueue = []
	    
	    if (len(uploadQueue) == 0) and (len(downloadQueue) == 0):
		print_info(green(" * ")+red("Nothing to syncronize. Queues empty."))
		sys.exit(0)
	    
	    
	    totalUploadSize = 0
	    totalDownloadSize = 0
	    print_info(green(" * ")+yellow("Queue tasks:"))
	    detailedUploadQueue = []
	    detailedDownloadQueue = []
	    for item in uploadQueue:
		fileSize = os.stat(etpConst['packagessuploaddir']+"/"+item)[6]
		totalUploadSize += int(fileSize)
		print_info(bold("\t[") + red("UPLOAD") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(bytesIntoHuman(fileSize)))
		detailedUploadQueue.append([item,fileSize])
	    for item in downloadQueue:
		fileSize = "0"
		for remotePackage in remotePackagesInfo:
		    if remotePackage.split()[8] == item:
			fileSize = remotePackage.split()[4]
			break
		totalDownloadSize += int(fileSize)
		print_info(bold("\t[") + yellow("DOWNLOAD") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(bytesIntoHuman(fileSize)))
		detailedDownloadQueue.append([item,fileSize])
	    print_info(red(" * ")+blue("Packages that would be ")+red("uploaded:\t\t")+bold(str(len(uploadQueue))))
	    print_info(red(" * ")+blue("Packages that would be ")+yellow("downloaded:\t")+bold(str(len(downloadQueue))))
	    print_info(red(" * ")+blue("Total upload ")+red("size:\t\t\t")+bold(bytesIntoHuman(str(totalUploadSize))))
	    print_info(red(" * ")+blue("Total download ")+yellow("size:\t\t\t")+bold(bytesIntoHuman(str(totalDownloadSize))))
	    
	    if (activatorRequestAsk):
		rc = askquestion("\n     Would you like to run the steps above ?")
		if rc == "No":
		    print "\n"
		    continue
	    elif (activatorRequestPretend):
		continue
	    
	    # upload queue
	    if (detailedUploadQueue != []):
	        ftp = activatorFTP(uri)
	        ftp.setCWD(etpConst['binaryurirelativepath'])
		for item in detailedUploadQueue:
		    print_info(red(" * Uploading file ")+bold(item[0]) + red(" [")+blue(bytesIntoHuman(item[1]))+red("] to ")+ bold(extractFTPHostFromUri(uri)) +red(" ..."),back = True)
		    ftp.uploadFile(etpConst['packagessuploaddir']+"/"+item[0])
		    # now move the file into etpConst['packagesbindir']
		    os.system("mv "+etpConst['packagessuploaddir']+"/"+item[0]+" "+etpConst['packagesbindir']+"/")
		print_info(red(" * Upload completed for ")+bold(extractFTPHostFromUri(uri)))
		ftp.closeFTPConnection()

	    # for the download queue, also check in the upload directory
	    if (detailedDownloadQueue != []):
	        ftp = activatorFTP(uri)
	        ftp.setCWD(etpConst['binaryurirelativepath'])
		for item in detailedDownloadQueue:
		    if os.path.isfile(etpConst['packagessuploaddir']+"/"+item[0]):
			localSize = int(os.stat(etpConst['packagessuploaddir']+"/"+item[0])[6])
			remoteSize = int(item[1])
			if localSize == remoteSize:
			    print_info(red(" * Moving file ")+bold(item[0])+red(" to ")+bold(etpConst['packagesbindir'])+red(" ..."),back = True)
			    os.system("mv "+etpConst['packagessuploaddir']+"/"+item[0]+" "+etpConst['packagesbindir']+"/")
			    continue
			
		    print_info(red(" * Downloading file ")+bold(item[0]) + red(" [")+blue(bytesIntoHuman(item[1]))+red("] from ")+ bold(extractFTPHostFromUri(uri)) +red(" ..."),back = True)
		    ftp.downloadFile(item[0],etpConst['packagesbindir']+"/")
		print_info(red(" * Upload completed for ")+bold(extractFTPHostFromUri(uri)))
		ftp.closeFTPConnection()
	
	    # Now I should do some tidy
	    print "Now it should be time for some tidy...?"

def database(options):

    # lock tool
    if (options[0] == "lock"):
	print_info(green(" * ")+green("Starting to lock mirrors' databases..."))
	rc = lockDatabases(lock = True)
	if (rc):
	    print_info(green(" * ")+green("A problem occured on at least one mirror..."))
	else:
	    print_info(green(" * ")+green("Databases lock complete"))

    # unlock tool
    elif (options[0] == "unlock"):
	print_info(green(" * ")+green("Starting to unlock mirrors' databases..."))
	rc = lockDatabases(lock = False)
	if (rc):
	    print_info(green(" * ")+green("A problem occured on at least one mirror..."))
	else:
	    print_info(green(" * ")+green("Databases unlock complete"))

    # download lock tool
    elif (options[0] == "download-lock"):
	print_info(green(" * ")+green("Starting to lock download mirrors' databases..."))
	rc = downloadLockDatabases(lock = True)
	if (rc):
	    print_info(green(" * ")+green("A problem occured on at least one mirror..."))
	else:
	    print_info(green(" * ")+green("Download mirrors lock complete"))

    # download unlock tool
    elif (options[0] == "download-unlock"):
	print_info(green(" * ")+green("Starting to unlock download mirrors' databases..."))
	rc = downloadLockDatabases(lock = False)
	if (rc):
	    print_info(green(" * ")+green("A problem occured on at least one mirror..."))
	else:
	    print_info(green(" * ")+green("Download mirrors unlock complete"))

    # download unlock tool
    elif (options[0] == "lock-status"):
	print_info(yellow(" * ")+green("Mirrors status table:"))
	dbstatus = getMirrorsLock()
	for db in dbstatus:
	    if (db[1]):
	        db[1] = red("Locked")
	    else:
	        db[1] = green("Unlocked")
	    if (db[2]):
	        db[2] = red("Locked")
	    else:
	        db[2] = green("Unlocked")
	    print_info(bold("\t"+extractFTPHostFromUri(db[0])+": ")+red("[")+yellow("DATABASE: ")+db[1]+red("] [")+yellow("DOWNLOAD: ")+db[2]+red("]"))

    else:
	print_error(green(" * ")+green("No valid tool specified."))
	sys.exit(100)

    '''
    # add package tool
    if (options[0] == "add-package"):
	print_info(yellow(" * ")+green("Add package tool"))

    # add package tool
    if (options[0] == "remove-package"):
	print_info(yellow(" * ")+green("Remove package tool"))

    # tidy package tool
    if (options[0] == "tidy-packages"):
	print_info(yellow(" * ")+green("Tidy package tool"))
    '''