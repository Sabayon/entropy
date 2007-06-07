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
# EXIT STATUSES: 400-499

from entropyConstants import *
from entropyTools import *
from outputTools import *

import sys
import os
import commands
import string
import time

# Logging initialization
import logTools
activatorLog = logTools.LogFile(level=etpConst['activatorloglevel'],filename = etpConst['activatorlogfile'], header = "[Activator]")
# example: activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"testFuncton: called.")

def sync(options, justTidy = False):

    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"sync: called with justTidy -> "+str(justTidy))

    print_info(green(" * ")+red("Starting to sync data across mirrors (packages/database) ..."))
    
    if (not justTidy):
        # firstly sync the packages
        rc = packages([ "sync" , "--ask" ])
        # then sync the database, if the packages sync completed successfully
        if (rc == False):
	    sys.exit(401)
	else:
            # if packages are ok, we can sync the database
	    database(["sync"])
	    # now check packages checksum
	    import databaseTools
	    databaseTools.database(['md5check'])
	    time.sleep(2)
	    # ask question
	    rc = askquestion("     Should I continue with the tidy procedure ?")
	    if rc == "No":
		sys.exit(0)
    
    print_info(green(" * ")+red("Starting to collect packages that would be removed from the repository ..."), back = True)
    
    # now it's time to do some tidy
    # collect all the binaries in the database
    import databaseTools
    dbconn = databaseTools.etpDatabase(readOnly = True)
    dbBinaries = dbconn.listAllPackagesTbz2()
    dbconn.closeDB()
    
    # list packages in the packages directory
    repoBinaries = os.listdir(etpConst['packagesbindir'])

    removeList = []
    # select packages
    for repoBin in repoBinaries:
	found = False
	for dbBin in dbBinaries:
	    if dbBin == repoBin:
		found = True
		break
	if (not found):
	    if (not repoBin.endswith(etpConst['packageshashfileext'])): # filter hash files
	        # then remove
	        removeList.append(repoBin)
    
    if (removeList == []):
	activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"sync: no packages to remove from the lirrors.")
	print_info(green(" * ")+red("No packages to remove from the mirrors."))
	print_info(green(" * ")+red("Syncronization across mirrors completed."))
	return
    
    print_info(green(" * ")+red("This is the list of the packages that would be removed from the mirrors: "))
    for file in removeList:
	print_info(green("\t* ")+yellow(file))
	
    # ask question
    rc = askquestion("     Would you like to continue ?")
    if rc == "No":
	sys.exit(0)

    # remove them!
    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"sync: starting to remove packages from mirrors.")
    for uri in etpConst['activatoruploaduris']:
	activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"sync: connecting to mirror "+extractFTPHostFromUri(uri))
	print_info(green(" * ")+red("Connecting to: ")+bold(extractFTPHostFromUri(uri)))
	ftp = mirrorTools.handlerFTP(uri)
	ftp.setCWD(etpConst['binaryurirelativepath'])
	for file in removeList:
	    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"sync: removing (remote) file "+file)
	    print_info(green(" * ")+red("Removing file: ")+bold(file), back = True)
	    # remove remotely
	    if (ftp.isFileAvailable(file)):
	        rc = ftp.deleteFile(file)
	        if (rc):
		    print_info(green(" * ")+red("Package file: ")+bold(file)+red(" removed successfully from ")+bold(extractFTPHostFromUri(uri)))
	        else:
		    print_warning(yellow(" * ")+red("ATTENTION: remote file ")+bold(file)+red(" cannot be removed."))
	    # remove locally
	    if os.path.isfile(etpConst['packagesbindir']+"/"+file):
		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"sync: removing (local) file "+file)
		print_info(green(" * ")+red("Package file: ")+bold(file)+red(" removed successfully from ")+bold(etpConst['packagesbindir']))
		os.remove(etpConst['packagesbindir']+"/"+file)
	ftp.closeFTPConnection()
	
    print_info(green(" * ")+red("Syncronization across mirrors completed."))


def packages(options):

    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: called with options -> "+str(options))

    # Options available for all the packages submodules
    myopts = options[1:]
    activatorRequestAsk = False
    activatorRequestPretend = False
    activatorRequestPackagesCheck = False
    for opt in myopts:
	if (opt == "--ask"):
	    activatorRequestAsk = True
	elif (opt == "--pretend"):
	    activatorRequestPretend = True
	elif (opt == "--do-packages-check"):
	    activatorRequestPackagesCheck = True

    if (options[0] == "sync"):
	print_info(green(" * ")+red("Starting ")+bold("binary")+yellow(" packages")+red(" syncronization across servers ..."))
	
	syncSuccessful = False
	totalUris = len(etpConst['activatoruploaduris'])
	currentUri = 0
	totalSuccessfulUri = 0
	
	activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: called sync.")
	
	for uri in etpConst['activatoruploaduris']:
	
	    currentUri += 1
	    try:
	        print_info(green(" * ")+yellow("Working on ")+bold(extractFTPHostFromUri(uri)+red(" mirror.")))
	        print_info(green(" * ")+yellow("Local Statistics"))
	        print_info(green(" * ")+red("Calculating packages in ")+bold(etpConst['packagessuploaddir'])+red(" ..."), back = True)
		
	        uploadCounter = 0
	        toBeUploaded = [] # parse etpConst['packagessuploaddir']
	        for tbz2 in os.listdir(etpConst['packagessuploaddir']):
		    if tbz2.endswith(".tbz2") or tbz2.endswith(etpConst['packageshashfileext']):
		        toBeUploaded.append(tbz2)
			if tbz2.endswith(".tbz2"):
		            uploadCounter += 1
		
		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: upload directory stats -> files: "+str(uploadCounter)+" | upload packages list: "+str(toBeUploaded))
		
	        print_info(green(" * ")+red("Upload directory:\t\t")+bold(str(uploadCounter))+red(" files ready."))
	        localPackagesRepository = [] # parse etpConst['packagesbindir']
	        print_info(green(" * ")+red("Calculating packages in ")+bold(etpConst['packagesbindir'])+red(" ..."), back = True)
	        packageCounter = 0
	        for tbz2 in os.listdir(etpConst['packagesbindir']):
		    if tbz2.endswith(".tbz2") or tbz2.endswith(etpConst['packageshashfileext']):
		        localPackagesRepository.append(tbz2)
			if tbz2.endswith(".tbz2"):
		            packageCounter += 1
		
		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: packages directory stats -> files: "+str(packageCounter)+" | download packages list (including md5): "+str(localPackagesRepository))
		
	        print_info(green(" * ")+red("Packages directory:\t")+bold(str(packageCounter))+red(" files ready."))
	    
	        print_info(green(" * ")+yellow("Fetching remote statistics..."), back = True)
	        ftp = mirrorTools.handlerFTP(uri)
	        ftp.setCWD(etpConst['binaryurirelativepath'])
	        remotePackages = ftp.listFTPdir()
	        remotePackagesInfo = ftp.getRoughList()
	        ftp.closeFTPConnection()

	        print_info(green(" * ")+yellow("Remote statistics"))
	        remoteCounter = 0
	        for tbz2 in remotePackages:
		    if tbz2.endswith(".tbz2"):
		        remoteCounter += 1
		
		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: remote packages stats -> files: "+str(remoteCounter))
		
	        print_info(green(" * ")+red("Remote packages:\t\t")+bold(str(remoteCounter))+red(" files stored."))

	        print_info(green(" * ")+yellow("Calculating..."))
	        uploadQueue = []
	        downloadQueue = []
	        removalQueue = []
		
		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: starting packages calculation...")
		
	        # if a package is in the packages directory but not online, we have to upload it
		# we have localPackagesRepository and remotePackages
	        for localPackage in localPackagesRepository:
		    pkgfound = False
		    for remotePackage in remotePackages:
		        if localPackage == remotePackage:
			    pkgfound = True
			    # it's already on the mirror, but... is its size correct??
			    localSize = int(os.stat(etpConst['packagesbindir']+"/"+localPackage)[6])
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
		
	        # Fill uploadQueue and if something weird is found, add the packages to downloadQueue
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
	    
	        # Fill downloadQueue and removalQueue
	        for remotePackage in remotePackages:
		    pkgfound = False
		    for localPackage in localPackagesRepository:
		        if localPackage == remotePackage:
			    pkgfound = True
			    # it's already on the mirror, but... is its size correct??
			    localSize = int(os.stat(etpConst['packagesbindir']+"/"+localPackage)[6])
			    remoteSize = 0
			    for file in remotePackagesInfo:
			        if file.split()[8] == remotePackage:
				    remoteSize = int(file.split()[4])
			    if (localSize != remoteSize) and (localSize != 0):
			        # size does not match, remove first
				#print "removal of "+localPackage+" because its size differ"
			        removalQueue.append(localPackage) # just remove something that differs from the content of the mirror
			        # then add to the download queue
			        downloadQueue.append(remotePackage)
			    break
		
		    if (not pkgfound):
		        # this means that the local package does not exist
		        # so, we need to download it
			if not remotePackage.endswith(".tmp"): # ignore .tmp files
			    downloadQueue.append(remotePackage)


		# Collect packages that don't exist anymore in the database
		# so we can filter them out from the download queue
		# Why downloading something that will be removed??
		# the same thing for the uploadQueue...
		import databaseTools
		dbconn = databaseTools.etpDatabase(readOnly = True)
		dbFiles = dbconn.listAllPackagesTbz2()
    		dbconn.closeDB()
		
		dlExcludeList = []
		for dlFile in downloadQueue:
		    if dlFile.endswith(".tbz2"):
		        dlFound = False
		        for dbFile in dbFiles:
			    if dbFile == dlFile:
			        dlFound = True
			        break
		        if (not dlFound):
			    dlExcludeList.append(dlFile)

		upExcludeList = []
		for upFile in uploadQueue:
		    if upFile.endswith(".tbz2"):
		        upFound = False
		        for dbFile in dbFiles:
			    if dbFile == upFile:
			        upFound = True
			        break
		        if (not upFound):
			    upExcludeList.append(upFile)
		
		# now clean downloadQueue
		if (dlExcludeList != []):
		    _downloadQueue = []
		    for dlFile in downloadQueue:
			exclusionFound = False
			for exclFile in dlExcludeList:
			    if dlFile.startswith(exclFile):
				exclusionFound = True
				break
			if (not exclusionFound):
			    _downloadQueue.append(dlFile)
		    downloadQueue = _downloadQueue

		# now clean uploadQueue
		if (upExcludeList != []):
		    _uploadQueue = []
		    for upFile in uploadQueue:
			exclusionFound = False
			for exclFile in upExcludeList:
			    if upFile.startswith(exclFile):
				exclusionFound = True
				break
			if (not exclusionFound):
			    _uploadQueue.append(upFile)
		    uploadQueue = _uploadQueue


	        # filter duplicates
	        removalQueue = filterDuplicatedEntries(removalQueue)
	        downloadQueue = filterDuplicatedEntries(downloadQueue)
	        uploadQueue = filterDuplicatedEntries(uploadQueue)
		
		# order alphabetically
		if (removalQueue != []):
		    removalQueue = alphaSorter(removalQueue)
		if (downloadQueue != []):
		    downloadQueue = alphaSorter(downloadQueue)
		if (uploadQueue != []):
		    uploadQueue = alphaSorter(uploadQueue)

		# now filter things
		# packages in uploadQueue should be removed, if found, from downloadQueue
		_downloadQueue = []
		for p in downloadQueue:
		    # search inside uploadQueue
		    found = False
		    for subp in uploadQueue:
			if (p == subp):
			    found = True
			    break
		    if (not found):
			_downloadQueue.append(p)
		downloadQueue = _downloadQueue

		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: removal queue -> "+str(removalQueue))
		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: download queue -> "+str(downloadQueue))
		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: upload queue -> "+str(uploadQueue))

	        if (len(uploadQueue) == 0) and (len(downloadQueue) == 0) and (len(removalQueue) == 0):
		    print_info(green(" * ")+red("Nothing to syncronize for ")+bold(extractFTPHostFromUri(uri)+red(". Queue empty.")))
		    totalSuccessfulUri += 1
		    syncSuccessful = True
		    continue

	        totalRemovalSize = 0
	        totalDownloadSize = 0
	        totalUploadSize = 0

	        print_info(green(" * ")+yellow("Queue tasks:"))
	        detailedRemovalQueue = []
	        detailedDownloadQueue = []
	        detailedUploadQueue = []
		# this below is used when a package has been already uploaded
		# but something weird happened and it hasn't been moved to the packages dir
		simpleCopyQueue = []

	        for item in removalQueue:
		    fileSize = os.stat(etpConst['packagesbindir']+"/"+item)[6]
		    totalRemovalSize += int(fileSize)
		    print_info(bold("\t[") + red("LOCAL REMOVAL") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(bytesIntoHuman(fileSize)))
		    detailedRemovalQueue.append([item,fileSize])

	        for item in downloadQueue:
		    # if the package is already in the upload directory, do not add the size
		    if not os.path.isfile(etpConst['packagessuploaddir']+"/"+item):
		        fileSize = "0"
		        for remotePackage in remotePackagesInfo:
		            if remotePackage.split()[8] == item:
			        fileSize = remotePackage.split()[4]
			        break
			if not item.endswith(etpConst['packageshashfileext']): # do not show .md5 to upload
		            totalDownloadSize += int(fileSize)
		            print_info(bold("\t[") + yellow("REMOTE DOWNLOAD") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(bytesIntoHuman(fileSize)))
		        detailedDownloadQueue.append([item,fileSize])
		    else:
			if (not item.endswith(etpConst['packageshashfileext'])):
			    fileSize = os.stat(etpConst['packagessuploaddir']+"/"+item)[6]
			    print_info(bold("\t[") + green("LOCAL COPY") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(bytesIntoHuman(fileSize)))
			# file exists locally and remotely (where is fine == fully uploaded)
			simpleCopyQueue.append(etpConst['packagessuploaddir']+"/"+item)

	        for item in uploadQueue:
		    # if it is in the upload dir
		    if os.path.isfile(etpConst['packagessuploaddir']+"/"+item):
		        fileSize = os.stat(etpConst['packagessuploaddir']+"/"+item)[6]
		    else: # otherwise it is in the packages dir
			fileSize = os.stat(etpConst['packagesbindir']+"/"+item)[6]
		    if not item.endswith(etpConst['packageshashfileext']): # do not show .md5 to upload
		        totalUploadSize += int(fileSize)
		        print_info(bold("\t[") + red("REMOTE UPLOAD") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(bytesIntoHuman(fileSize)))
		        detailedUploadQueue.append([item,fileSize])

	        print_info(red(" * ")+blue("Packages that would be ")+red("removed:\t\t")+bold(str(len(removalQueue))))
	        print_info(red(" * ")+blue("Packages that would be ")+yellow("downloaded:\t")+bold(str(len(downloadQueue))))
	        print_info(red(" * ")+blue("Packages that would be ")+green("uploaded:\t\t")+bold(str(len(uploadQueue))))
	        print_info(red(" * ")+blue("Total removal ")+red("size:\t\t\t")+bold(bytesIntoHuman(str(totalRemovalSize))))
	        print_info(red(" * ")+blue("Total download ")+yellow("size:\t\t\t")+bold(bytesIntoHuman(str(totalDownloadSize))))
	        print_info(red(" * ")+blue("Total upload ")+green("size:\t\t\t")+bold(bytesIntoHuman(str(totalUploadSize))))
	    
	        if (activatorRequestAsk):
		    rc = askquestion("\n     Would you like to run the steps above ?")
		    if rc == "No":
		        print "\n"
		        continue
	        elif (activatorRequestPretend):
		    continue

		# queues management
		successfulUploadCounter = 0
		successfulDownloadCounter = 0
		uploadCounter = "0"
		downloadCounter = "0"

		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: detailed removal queue -> "+str(detailedRemovalQueue))
		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: detailed simple copy queue -> "+str(simpleCopyQueue))
		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: detailed download queue -> "+str(detailedDownloadQueue))
		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: detailed upload queue -> "+str(detailedUploadQueue))
		

	        # removal queue
	        if (detailedRemovalQueue != []):
		    for item in detailedRemovalQueue:
		        print_info(red(" * Removing file ")+bold(item[0]) + red(" [")+blue(bytesIntoHuman(item[1]))+red("] from ")+ bold(etpConst['packagesbindir'])+red(" ..."))
		        spawnCommand("rm -f "+etpConst['packagesbindir']+"/"+item[0])
			spawnCommand("rm -f "+etpConst['packagesbindir']+"/"+item[0]+etpConst['packageshashfileext'])
		    print_info(red(" * Removal completed for ")+bold(etpConst['packagesbindir']))

		# simple copy queue
		if (simpleCopyQueue != []):
		    for item in simpleCopyQueue:
			print_info(red(" * Copying file from ") + bold(item) + red(" to ")+bold(etpConst['packagesbindir']))
			spawnCommand("cp -p "+item+" "+etpConst['packagesbindir']+"/", "> /dev/null")
			# md5 copy not needed, already in simpleCopyQueue

	        # upload queue
	        if (detailedUploadQueue != []):
	            ftp = mirrorTools.handlerFTP(uri)
	            ftp.setCWD(etpConst['binaryurirelativepath'])
		    uploadCounter = str(len(detailedUploadQueue))
		    currentCounter = 0
		    for item in detailedUploadQueue:
		        currentCounter += 1
		        counterInfo = bold(" (")+blue(str(currentCounter))+"/"+red(uploadCounter)+bold(")")
		        print_info(counterInfo+red(" Uploading file ")+bold(item[0]) + red(" [")+blue(bytesIntoHuman(item[1]))+red("] to ")+ bold(extractFTPHostFromUri(uri)) +red(" ..."))
			# is the package in the upload queue?
			if os.path.isfile(etpConst['packagessuploaddir']+"/"+item[0]):
			    uploadItem = etpConst['packagessuploaddir']+"/"+item[0]
			else:
			    uploadItem = etpConst['packagesbindir']+"/"+item[0]
			rc = ftp.uploadFile(uploadItem)
			if not os.path.isfile(uploadItem+etpConst['packageshashfileext']):
			    hashfile = createHashFile(uploadItem)
			else:
			    hashfile = uploadItem+etpConst['packageshashfileext']
			# upload md5 hash
			rcmd5 = ftp.uploadFile(hashfile,ascii = True)
			
			if (rc) and (rcmd5):
			    successfulUploadCounter += 1
		    print_info(red(" * Upload completed for ")+bold(extractFTPHostFromUri(uri)))
		    ftp.closeFTPConnection()

	        # download queue
	        if (detailedDownloadQueue != []):
	            ftp = mirrorTools.handlerFTP(uri)
	            ftp.setCWD(etpConst['binaryurirelativepath'])
		    downloadCounter = str(len(detailedDownloadQueue))
		    currentCounter = 0
		    for item in detailedDownloadQueue:
		        currentCounter += 1
		        counterInfo = bold(" (")+blue(str(currentCounter))+"/"+red(downloadCounter)+bold(")")
		        if os.path.isfile(etpConst['packagessuploaddir']+"/"+item[0]):
			    localSize = int(os.stat(etpConst['packagessuploaddir']+"/"+item[0])[6])
			    remoteSize = int(item[1])
			    if localSize == remoteSize:
			        # skip that, we'll move at the end of the mirrors sync
			        continue
		        print_info(counterInfo+red(" Downloading file ")+bold(item[0]) + red(" [")+blue(bytesIntoHuman(item[1]))+red("] from ")+ bold(extractFTPHostFromUri(uri)) +red(" ..."))
			
			# FIXME: test if the .md5 got downloaded
			if item[0].endswith(etpConst['packageshashfileext']):
			    rc = ftp.downloadFile(item[0],etpConst['packagesbindir']+"/", ascii = True)
			else:
		            rc = ftp.downloadFile(item[0],etpConst['packagesbindir']+"/")
			
			if (rc):
			    successfulDownloadCounter += 1
			
		    print_info(red(" * Download completed for ")+bold(extractFTPHostFromUri(uri)))
		    ftp.closeFTPConnection()

		uploadCounter = int(uploadCounter)
		downloadCounter = int(downloadCounter)

		if (successfulUploadCounter == uploadCounter) and (successfulDownloadCounter == downloadCounter):
		    totalSuccessfulUri += 1

	    # trap exceptions, failed to upload/download someting?
	    except:
		
		activatorLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"packages: cannot properly syncronize "+extractFTPHostFromUri(uri)+". Trying to continue if possible.")
		
		# print warning cannot sync uri
		print_warning(yellow(" * ")+red("ATTENTION: cannot properly syncronize ")+bold(extractFTPHostFromUri(uri))+red(". Continuing if possible..."))
		
		# decide what to do
		if (totalSuccessfulUri > 0) or (activatorRequestPretend):
		    # we're safe
		    activatorLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"packages: at least one mirror has been synced properly. I'm fine.")
		    print_info(green(" * ")+red("At least one mirror has been synced properly. I'm fine."))
		    continue
		else:
		    if (currentUri < totalUris):
			# we have another mirror to try
			continue
		    else:
			# no mirrors were synced properly
			# show error and return, do not move files from the upload dir
			activatorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"packages: no mirrors have been properly syncronized. Check network status and retry. Cannot continue.")
			print_error(yellow(" * ")+red("ERROR: no mirrors have been properly syncronized. Check network status and retry. Cannot continue."))
			return False


	# if at least one server has been synced successfully, move files
	if (totalSuccessfulUri > 0) and (not activatorRequestPretend):
	    # now we can store the files in upload/%ARCH% in packages/%ARCH%
	    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"packages: all done. Now it's time to move packages to "+etpConst['packagesbindir'])
	    spawnCommand("mv -f "+etpConst['packagessuploaddir']+"/* "+etpConst['packagesbindir']+"/", "&> /dev/null")
	    return True
	else:
	    sys.exit(470)

    # Now we should start to check all the packages in the packages directory
    if (activatorRequestPackagesCheck):
	import databaseTools
	databaseTools.database(['md5check'])
	

def database(options):

    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"database: called with -> "+str(options))

    # lock tool
    if (options[0] == "lock"):
	print_info(green(" * ")+green("Starting to lock mirrors' databases..."))
	rc = lockDatabases(lock = True)
	if (rc):
	    activatorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"database: (lock) A problem occured on at least one mirror !")
	    print_info(green(" * ")+red("A problem occured on at least one mirror !"))
	else:
	    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"database: Databases lock complete.")
	    print_info(green(" * ")+green("Databases lock complete"))

    # unlock tool
    elif (options[0] == "unlock"):
	print_info(green(" * ")+green("Starting to unlock mirrors' databases..."))
	rc = lockDatabases(lock = False)
	if (rc):
	    activatorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"database: (unlock) A problem occured on at least one mirror !")
	    print_info(green(" * ")+green("A problem occured on at least one mirror !"))
	else:
	    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"database: Databases lock complete.")
	    print_info(green(" * ")+green("Databases unlock complete"))

    # download lock tool
    elif (options[0] == "download-lock"):
	print_info(green(" * ")+green("Starting to lock download mirrors' databases..."))
	rc = downloadLockDatabases(lock = True)
	if (rc):
	    activatorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"database: (download-lock) A problem occured on at least one mirror !")
	    print_info(green(" * ")+green("A problem occured on at least one mirror !"))
	else:
	    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"database: Download mirrors lock complete.")
	    print_info(green(" * ")+green("Download mirrors lock complete"))

    # download unlock tool
    elif (options[0] == "download-unlock"):
	print_info(green(" * ")+green("Starting to unlock download mirrors' databases..."))
	rc = downloadLockDatabases(lock = False)
	if (rc):
	    activatorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"database: (download-unlock) A problem occured on at least one mirror !")
	    print_info(green(" * ")+green("A problem occured on at least one mirror..."))
	else:
	    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"database: Download mirrors unlock complete.")
	    print_info(green(" * ")+green("Download mirrors unlock complete"))

    # lock status tool
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

    # database sync tool
    elif (options[0] == "sync"):

	activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"database: database sync called.")

	print_info(green(" * ")+red("Checking database status ..."), back = True)
	
	dbLockFile = False
	# does the taint file exist?
	if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']):
	    dbLockFile = True
	
	# are online mirrors locked?
	mirrorsLocked = False
	for uri in etpConst['activatoruploaduris']:
	    ftp = mirrorTools.handlerFTP(uri)
	    ftp.setCWD(etpConst['etpurirelativepath'])
	    if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])) or (ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile'])):
		mirrorsLocked = True
		ftp.closeFTPConnection()
		break
	
	if (mirrorsLocked):
	    # if the mirrors are locked, we need to change if we have
	    # the taint file in place. Because in this case, the one
	    # that tainted the db, was me.
	    if (dbLockFile):
		print_info(green(" * ")+red("Updating mirrors with new information ..."))
		# it's safe to sync
	        syncRemoteDatabases()
		# remove the online lock file
		lockDatabases(False)
		# remove the taint file
		if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile']):
		    os.remove(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabasetaintfile'])
	    else:
		print
		activatorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"database (sync inside activatorTools): At the moment, mirrors are locked, someone is working on their databases, try again later...")
		print_error(green(" * ")+red("At the moment, mirrors are locked, someone is working on their databases, try again later..."))
		sys.exit(422)
	
	else:
	    if (dbLockFile):
		activatorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"database (sync inside activatorTools): Mirrors are not locked remotely but the local database is. It is a non-sense. Please remove the lock file "+etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])
		print_info(green(" * ")+red("Mirrors are not locked remotely but the local database is. It is a non-sense. Please remove the lock file "+etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']))
		sys.exit(423)
	    else:
		activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"database (sync inside activatorTools): Mirrors are not locked. Fetching data...")
		print_info(green(" * ")+red("Mirrors are not locked. Fetching data..."))
	    
	    syncRemoteDatabases()

    else:
	print_error(red(" * ")+green("No valid tool specified."))
	sys.exit(400)
