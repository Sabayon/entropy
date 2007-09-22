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
from serverConstants import *
from entropyTools import *
from outputTools import *
import mirrorTools

import sys
import os
import commands
import string
import time


# Logging initialization
import logTools
activatorLog = logTools.LogFile(level=etpConst['activatorloglevel'],filename = etpConst['activatorlogfile'], header = "[Activator]")
# example: activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"testFuncton: called.")

import remoteTools

def sync(options, justTidy = False):
	
    activatorRequestNoAsk = False
    myopts = []
    for i in options:
        if ( i == "--noask" ):
	    activatorRequestNoAsk = True
	else:
	    myopts.append(i)
    options = myopts
	
    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"sync: called with justTidy -> "+str(justTidy))
    print_info(green(" * ")+red("Starting to sync data across mirrors (packages/database) ..."))
    
    if (not justTidy):
        # firstly sync the packages
	if (activatorRequestNoAsk):
	    rc = packages([ "sync" ])
	else:
	    rc = packages([ "sync" , "--ask" ])
        # then sync the database, if the packages sync completed successfully
        if (rc == False):
	    sys.exit(401)
	else:
            # if packages are ok, we can sync the database
	    database(["sync"])
	    # now check packages checksum
	    import databaseTools
	    databaseTools.database(['md5check','--noask'])
	    time.sleep(2)
	    if (not activatorRequestNoAsk):
	        # ask question
	        rc = askquestion("     Should I continue with the tidy procedure ?")
	        if rc == "No":
		    sys.exit(0)
    
    print_info(green(" * ")+red("Starting to collect packages that would be removed from the repository ..."), back = True)
    
    
    for mybranch in etpConst['branches']:
    
        print_info(red(" * ")+blue("Switching to branch: ")+bold(mybranch))
    
        # now it's time to do some tidy
        # collect all the binaries in the database
        import databaseTools
        dbconn = databaseTools.etpDatabase(readOnly = True)
        dbBinaries = dbconn.listBranchPackagesTbz2(mybranch)
        dbconn.closeDB()
    
        # list packages in the packages directory
	repoBinaries = os.listdir(etpConst['packagesbindir']+"/"+mybranch)

        removeList = []
        # select packages
        for repoBin in repoBinaries:
	    if (not repoBin.endswith(etpConst['packageshashfileext'])):
	        if repoBin not in dbBinaries:
		    removeList.append(repoBin)
    
        if (not removeList):
	    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"sync: no packages to remove from the lirrors.")
	    print_info(green(" * ")+red("No packages to remove from the mirrors."))
	    print_info(green(" * ")+red("Syncronization across mirrors completed."))
	    continue
    
        print_info(green(" * ")+red("This is the list of files that would be removed from the mirrors: "))
        for file in removeList:
	    print_info(green("\t* ")+yellow(file))
	
        # ask question
        if (not activatorRequestNoAsk):
            rc = askquestion("     Would you like to continue ?")
            if rc == "No":
	        sys.exit(0)

        # remove them!
        activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"sync: starting to remove packages from mirrors.")
        for uri in etpConst['activatoruploaduris']:
	    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"sync: connecting to mirror "+extractFTPHostFromUri(uri))
	    print_info(green(" * ")+red("Connecting to: ")+bold(extractFTPHostFromUri(uri)))
	    ftp = mirrorTools.handlerFTP(uri)
	    ftp.setCWD(etpConst['binaryurirelativepath']+"/"+mybranch)
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
	        # checksum
	        if (ftp.isFileAvailable(file+etpConst['packageshashfileext'])):
	            rc = ftp.deleteFile(file+etpConst['packageshashfileext'])
	            if (rc):
		        print_info(green(" * ")+red("Checksum file: ")+bold(file+etpConst['packageshashfileext'])+red(" removed successfully from ")+bold(extractFTPHostFromUri(uri)))
	            else:
		        print_warning(yellow(" * ")+red("ATTENTION: remote checksum file ")+bold(file)+red(" cannot be removed."))
	        # remove locally
	        if os.path.isfile(etpConst['packagesbindir']+"/"+mybranch+"/"+file):
		    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"sync: removing (local) file "+file)
		    print_info(green(" * ")+red("Package file: ")+bold(file)+red(" removed successfully from ")+bold(etpConst['packagesbindir']+"/"+mybranch))
		    os.remove(etpConst['packagesbindir']+"/"+mybranch+"/"+file)
	        # checksum
	        if os.path.isfile(etpConst['packagesbindir']+"/"+mybranch+"/"+file+etpConst['packageshashfileext']):
		    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"sync: removing (local) file "+file+etpConst['packageshashfileext'])
		    print_info(green(" * ")+red("Checksum file: ")+bold(file+etpConst['packageshashfileext'])+red(" removed successfully from ")+bold(etpConst['packagesbindir']+"/"+mybranch))
		    os.remove(etpConst['packagesbindir']+"/"+mybranch+"/"+file+etpConst['packageshashfileext'])
	    ftp.closeConnection()
	
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

    if len(options) == 0:
	return

    if (options[0] == "sync"):
	print_info(green(" * ")+red("Starting ")+bold("binary")+yellow(" packages")+red(" syncronization across servers ..."))
	
	totalUris = len(etpConst['activatoruploaduris'])
	currentUri = 0
	totalSuccessfulUri = 0
	
	activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: called sync.")
	
	for uri in etpConst['activatoruploaduris']:
		
	    uriSuccessfulSync = 0
	    currentUri += 1
	    try:
	        print_info(green(" * ")+yellow("Working on ")+bold(extractFTPHostFromUri(uri)+red(" mirror.")))
		
		pkgbranches = os.listdir(etpConst['packagessuploaddir'])
		pkgbranches = [x for x in pkgbranches if os.path.isdir(etpConst['packagessuploaddir']+"/"+x)]
		
		for mybranch in pkgbranches:

		    print_info(red(" * ")+blue("Switching to branch: ")+bold(mybranch))
	            print_info(green(" * ")+yellow("Local Statistics: "))
	            print_info(green(" * ")+red("Calculating packages in ")+bold(etpConst['packagessuploaddir']+"/"+mybranch)+red(" ..."), back = True)
		
	            uploadCounter = 0
	            toBeUploaded = [] # parse etpConst['packagessuploaddir']
	            for tbz2 in os.listdir(etpConst['packagessuploaddir']+"/"+mybranch):
		        if tbz2.endswith(".tbz2") or tbz2.endswith(etpConst['packageshashfileext']):
		            toBeUploaded.append(tbz2)
			    if tbz2.endswith(".tbz2"):
		                uploadCounter += 1
		
		    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: upload directory stats -> files: "+str(uploadCounter)+" | upload packages list: "+str(toBeUploaded))
		
	            print_info(green(" * ")+red("Upload directory:\t\t")+bold(str(uploadCounter))+red(" files ready."))
	            localPackagesRepository = [] # parse etpConst['packagesbindir']
	            print_info(green(" * ")+red("Calculating packages in ")+bold(etpConst['packagesbindir']+"/"+mybranch)+red(" ..."), back = True)
	            packageCounter = 0
	            for tbz2 in os.listdir(etpConst['packagesbindir']+"/"+mybranch):
		        if tbz2.endswith(".tbz2") or tbz2.endswith(etpConst['packageshashfileext']):
		            localPackagesRepository.append(tbz2)
			    if tbz2.endswith(".tbz2"):
		                packageCounter += 1
		
		    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: packages directory stats -> files: "+str(packageCounter)+" | download packages list (including md5): "+str(localPackagesRepository))
		
	            print_info(green(" * ")+red("Packages directory:\t")+bold(str(packageCounter))+red(" files ready."))
	    
	            print_info(green(" * ")+yellow("Fetching remote statistics..."), back = True)
	            ftp = mirrorTools.handlerFTP(uri)
	            ftp.setCWD(etpConst['binaryurirelativepath']+"/"+mybranch)
	            remotePackages = ftp.listDir()
	            remotePackagesInfo = ftp.getRoughList()
	            ftp.closeConnection()

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
			        localSize = int(os.stat(etpConst['packagesbindir']+"/"+mybranch+"/"+localPackage)[6])
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
			        localSize = int(os.stat(etpConst['packagessuploaddir']+"/"+mybranch+"/"+localPackage)[6])
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
			        localSize = int(os.stat(etpConst['packagesbindir']+"/"+mybranch+"/"+localPackage)[6])
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
		    dbFiles = dbconn.listBranchPackagesTbz2(mybranch)
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

	            # filter duplicates - filterDuplicatedEntries
		
	            removalQueue = filterDuplicatedEntries(removalQueue)
	            downloadQueue = filterDuplicatedEntries(downloadQueue)
	            uploadQueue = filterDuplicatedEntries(uploadQueue)

		

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
		        uriSuccessfulSync += 1
			if (uriSuccessfulSync == len(pkgbranches)):
			    totalSuccessfulUri += 1
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
		        fileSize = os.stat(etpConst['packagesbindir']+"/"+mybranch+"/"+item)[6]
		        totalRemovalSize += int(fileSize)
		        print_info(bold("\t[") + red("LOCAL REMOVAL") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(bytesIntoHuman(fileSize)))
		        detailedRemovalQueue.append([item,fileSize])

	            for item in downloadQueue:
		        # if the package is already in the upload directory, do not add the size
		        if not os.path.isfile(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item):
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
			        fileSize = os.stat(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item)[6]
			        print_info(bold("\t[") + green("LOCAL COPY") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(bytesIntoHuman(fileSize)))
			    # file exists locally and remotely (where is fine == fully uploaded)
			    simpleCopyQueue.append(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item)

	            for item in uploadQueue:
		        # if it is in the upload dir
		        if os.path.isfile(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item):
		            fileSize = os.stat(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item)[6]
		        else: # otherwise it is in the packages dir
			    fileSize = os.stat(etpConst['packagesbindir']+"/"+mybranch+"/"+item)[6]
		        if not item.endswith(etpConst['packageshashfileext']): # do not show .md5 to upload
		            totalUploadSize += int(fileSize)
		            print_info(bold("\t[") + red("REMOTE UPLOAD") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(bytesIntoHuman(fileSize)))
		            detailedUploadQueue.append([item,fileSize])

		    # queue length info
		    removalQueueLength = 0
		    for i in removalQueue:
		        if not i.endswith(etpConst['packageshashfileext']):
			    removalQueueLength += 1
		    downloadQueueLength = 0
		    for i in downloadQueue:
		        if not i.endswith(etpConst['packageshashfileext']):
			    downloadQueueLength += 1
		    uploadQueueLength = 0
		    for i in uploadQueue:
		        if not i.endswith(etpConst['packageshashfileext']):
			    uploadQueueLength += 1
		
	            print_info(red(" * ")+blue("Packages that would be ")+red("removed:\t\t")+bold(str(removalQueueLength)))
	            print_info(red(" * ")+blue("Packages that would be ")+yellow("downloaded:\t")+bold(str(downloadQueueLength)))
	            print_info(red(" * ")+blue("Packages that would be ")+green("uploaded:\t\t")+bold(str(uploadQueueLength)))
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
		            print_info(red(" * Removing file ")+bold(item[0]) + red(" [")+blue(bytesIntoHuman(item[1]))+red("] from ")+ bold(etpConst['packagesbindir']+"/"+mybranch)+red(" ..."))
		            spawnCommand("rm -f "+etpConst['packagesbindir']+"/"+mybranch+"/"+item[0])
			    spawnCommand("rm -f "+etpConst['packagesbindir']+"/"+mybranch+"/"+item[0]+etpConst['packageshashfileext'])
		        print_info(red(" * Removal completed for ")+bold(etpConst['packagesbindir']+"/"+mybranch))

		    # simple copy queue
		    if (simpleCopyQueue != []):
		        for item in simpleCopyQueue:
			    print_info(red(" * Copying file from ") + bold(item) + red(" to ")+bold(etpConst['packagesbindir']+"/"+mybranch))
			    spawnCommand("cp -p "+item+" "+etpConst['packagesbindir']+"/"+mybranch+"/", "> /dev/null")
			    # md5 copy not needed, already in simpleCopyQueue

	            # upload queue
	            if (detailedUploadQueue != []):
	                ftp = mirrorTools.handlerFTP(uri)
	                ftp.setCWD(etpConst['binaryurirelativepath']+"/"+mybranch)
		        uploadCounter = str(len(detailedUploadQueue))
		        currentCounter = 0
		        for item in detailedUploadQueue:
		            currentCounter += 1
		            counterInfo = bold(" (")+blue(str(currentCounter))+"/"+red(uploadCounter)+bold(")")
		            print_info(counterInfo+red(" Uploading file ")+bold(item[0]) + red(" [")+blue(bytesIntoHuman(item[1]))+red("] to ")+ bold(extractFTPHostFromUri(uri)) +red(" ..."))
			    # is the package in the upload queue?
			    if os.path.isfile(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item[0]):
			        uploadItem = etpConst['packagessuploaddir']+"/"+mybranch+"/"+item[0]
			    else:
			        uploadItem = etpConst['packagesbindir']+"/"+mybranch+"/"+item[0]
			
			    ckOk = False
			    while not ckOk:
			        rc = ftp.uploadFile(uploadItem)
			        # verify upload using remoteTools
			        print_info("    "+red("   -> Verifying ")+green(item[0])+bold(" checksum")+red(" (if supported)"), back = True)
			        ck = remoteTools.getRemotePackageChecksum(extractFTPHostFromUri(uri),item[0], mybranch)
			        if (ck == None):
				    print_warning("    "+red("   -> Digest verification of ")+green(item[0])+bold(" not supported"))
				    ckOk = True
			        else:
				    if (ck == False):
				        # file does not exist???
				        print_warning("    "+red("   -> Package ")+bold(item[0])+red(" does not exist remotely. Reuploading..."))
				    else:
				        if len(ck) == 32:
					    # valid checksum, checking
					    ckres = compareMd5(uploadItem,ck)
					    if (ckres):
					        print_info("    "+red("   -> Package ")+bold(item[0])+red(" has been uploaded correctly."))
					        ckOk = True
					    else:
					        print_warning("    "+red("   -> Package ")+bold(item[0])+yellow(" has NOT been uploaded correctly. Reuploading..."))
				        else:
					    # hum, what the hell is this checksum!?!?!?!
					    print_warning("    "+red("   -> Package ")+bold(item[0])+red(" does not have a proper checksum: "+str(ck)+". Reuploading..."))
			
			    if not os.path.isfile(uploadItem+etpConst['packageshashfileext']):
			        hashfile = createHashFile(uploadItem)
			    else:
			        hashfile = uploadItem+etpConst['packageshashfileext']

			    # upload md5 hash
			    print_info("    "+red("   -> Uploading checksum of ")+bold(item[0]) + red(" to ") + bold(extractFTPHostFromUri(uri)) +red(" ..."))
			    ckOk = False
			    while not ckOk:
			        rcmd5 = ftp.uploadFile(hashfile,ascii = True)
			        # verify upload using remoteTools
			        print_info("    "+red("   -> Verifying ")+green(item[0]+etpConst['packageshashfileext'])+bold(" checksum")+red(" (if supported)"), back = True)
			        ck = remoteTools.getRemotePackageChecksum(extractFTPHostFromUri(uri),item[0]+etpConst['packageshashfileext'], mybranch)
			        if (ck == None):
				    print_warning("    "+red("   -> Digest verification of ")+green(item[0]+etpConst['packageshashfileext'])+bold(" not supported"))
				    ckOk = True
			        else:
				    if (ck == False):
				        # file does not exist???
				        print_warning("    "+red("   -> Package ")+bold(item[0]+etpConst['packageshashfileext'])+red(" does not exist remotely. Reuploading..."))
				    else:
				        if len(ck) == 32:
					    # valid checksum, checking
					    ckres = compareMd5(hashfile,ck)
					    if (ckres):
					        print_info("    "+red("   -> Package ")+bold(item[0]+etpConst['packageshashfileext'])+red(" has been uploaded correctly."))
					        ckOk = True
					    else:
					        print_warning("    "+red("   -> Package ")+bold(item[0]+etpConst['packageshashfileext'])+yellow(" has NOT been uploaded correctly. Reuploading..."))
				        else:
					    # hum, what the hell is this checksum!?!?!?!
					    print_warning("    "+red("   -> Package ")+bold(item[0]+etpConst['packageshashfileext'])+red(" does not have a proper checksum: "+str(ck)+" Reuploading..."))

			    # now check
			    if (rc) and (rcmd5):
			        successfulUploadCounter += 1
		        print_info(red(" * Upload completed for ")+bold(extractFTPHostFromUri(uri)))
		        ftp.closeConnection()

	            # download queue
	            if (detailedDownloadQueue != []):
	                ftp = mirrorTools.handlerFTP(uri)
	                ftp.setCWD(etpConst['binaryurirelativepath']+"/"+mybranch)
		        downloadCounter = str(len(detailedDownloadQueue))
		        currentCounter = 0
		        for item in detailedDownloadQueue:
		            currentCounter += 1
		            counterInfo = bold(" (")+blue(str(currentCounter))+"/"+red(downloadCounter)+bold(")")
		            if os.path.isfile(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item[0]):
			        localSize = int(os.stat(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item[0])[6])
			        remoteSize = int(item[1])
			        if localSize == remoteSize:
			            # skip that, we'll move at the end of the mirrors sync
			            continue
		            print_info(counterInfo+red(" Downloading file ")+bold(item[0]) + red(" [")+blue(bytesIntoHuman(item[1]))+red("] from ")+ bold(extractFTPHostFromUri(uri)) +red(" ..."))
			
			    ckOk = False
			    while not ckOk:

			        if item[0].endswith(etpConst['packageshashfileext']):
				    rc = ftp.downloadFile(item[0],etpConst['packagesbindir']+"/"+mybranch+"/", ascii = True)
			        else:
				    rc = ftp.downloadFile(item[0],etpConst['packagesbindir']+"/"+mybranch+"/")

			        # verify upload using remoteTools
				if not item[0].endswith(etpConst['packageshashfileext']):
			            print_info(counterInfo+red("   -> Verifying ")+green(item[0])+bold(" checksum")+red(" (if supported)"), back = True)
			            ck = remoteTools.getRemotePackageChecksum(extractFTPHostFromUri(uri),item[0], mybranch)
			            if (ck == None):
				        print_warning(counterInfo+red("   -> Digest verification of ")+green(item[0])+bold(" not supported"))
				        ckOk = True
			            else:
				        if (ck == False):
				            # file does not exist???
				            print_warning(counterInfo+red("   -> Package ")+bold(item[0])+red(" does not exist remotely. Skipping ..."))
					    ckOk = True
				        else:
				            if len(ck) == 32:
					        # valid checksum, checking
					        filepath = etpConst['packagesbindir']+"/"+mybranch+"/"+item[0]
					        ckres = compareMd5(filepath,ck)
					        if (ckres):
					            print_info(counterInfo+red("   -> Package ")+bold(item[0])+red(" has been downloaded correctly."))
					            ckOk = True
					        else:
					            print_warning(counterInfo+red("   -> Package ")+bold(item[0])+yellow(" has NOT been downloaded correctly. Redownloading..."))
				            else:
					        # hum, what the hell is this checksum!?!?!?!
					        print_warning(counterInfo+red("   -> Package ")+bold(item[0])+red(" does not have a proper checksum: "+str(ck)+" Redownloading..."))
				else: # skip checking for .md5 files
				    ckOk = True
			
			    if (rc):
			        successfulDownloadCounter += 1
			
		        print_info(red(" * Download completed for ")+bold(extractFTPHostFromUri(uri)))
		        ftp.closeConnection()

		    uploadCounter = int(uploadCounter)
		    downloadCounter = int(downloadCounter)
		    
		    if (successfulUploadCounter == uploadCounter) and (successfulDownloadCounter == downloadCounter):
			uriSuccessfulSync += 1

		    if (uriSuccessfulSync == len(pkgbranches)):
		        totalSuccessfulUri += 1

	    # trap exceptions, failed to upload/download someting?
	    except Exception, e:
		
		print_error(yellow(" * ")+red("packages: Exception caught: ")+str(e)+red(" . Showing traceback:"))
		import traceback
		traceback.print_exc()
		
		# trap CTRL+C
		if (str(e) == "100"):
		    sys.exit(471)
		
		activatorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"packages: Exception caught: "+str(e)+" . Trying to continue if possible.")
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
	    import shutil
	    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"packages: all done. Now it's time to move packages to "+etpConst['packagesbindir'])
	    pkgbranches = os.listdir(etpConst['packagessuploaddir'])
	    pkgbranches = [x for x in pkgbranches if os.path.isdir(etpConst['packagessuploaddir']+"/"+x)]
	    for branch in pkgbranches:
		branchcontent = os.listdir(etpConst['packagessuploaddir']+"/"+branch)
		for file in branchcontent:
		    source = etpConst['packagessuploaddir']+"/"+branch+"/"+file
		    destdir = etpConst['packagesbindir']+"/"+branch
		    if not os.path.isdir(destdir):
		        os.makedirs(destdir)
		    dest = destdir+"/"+file
		    shutil.move(source,dest)
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
		ftp.closeConnection()
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


########################################################
####
##   Database handling functions
#

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
	f.write(hexdigest+"  "+etpConst['etpdatabasefile']+"\n")
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
	ftp.closeConnection()
	# unlock database
	downloadLockDatabases(False,[uri])

def downloadDatabase(uri):
    
    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadDatabase: called.")
    
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
    
    unpackGzip(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasefilegzip'])
    
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
    # downlading digest -> FIXME: add digest comparation
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
    ftp.closeConnection()

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
	ftp.closeConnection()
	dbstatus.append(data)
    return dbstatus

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
	ftp.closeConnection()

    return uriDbInfo

def downloadPackageFromMirror(uri,pkgfile,branch):

    entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: called for "+extractFTPHostFromUri(uri)+" and file -> "+str(pkgfile))

    tries = 0
    maxtries = 5
    for i in range(maxtries):
	
	entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: ("+str(tries)+"/"+str(maxtries)+") downloading -> "+pkgfile)
	
        print_info(red("  * Connecting to ")+bold(extractFTPHostFromUri(uri)), back = True)
        # connect
        ftp = mirrorTools.handlerFTP(uri)
        ftp.setCWD(etpConst['binaryurirelativepath']+"/"+branch)
        # get the files
        print_info(red("  * Downloading ")+yellow(pkgfile)+red(" from ")+bold(extractFTPHostFromUri(uri)))
        rc = ftp.downloadFile(pkgfile,etpConst['packagesbindir']+"/"+branch)
	if (rc is None):
	    entropyLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: ("+str(tries)+"/"+str(maxtries)+") Error. File not found. -> "+pkgfile)
	    # file does not exist
	    print_warning(red("  * File ")+yellow(pkgfile)+red(" does not exist remotely on ")+bold(extractFTPHostFromUri(uri)))
	    ftp.closeConnection()
	    return None
	entropyLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: ("+str(tries)+"/"+str(maxtries)+") checking md5 for -> "+pkgfile)
        # check md5
	dbconn = databaseTools.etpDatabase(readOnly = True)
	idpackage = dbconn.getIDPackageFromFileInBranch(pkgfile,branch)
	storedmd5 = dbconn.retrieveDigest(idpackage)
	dbconn.closeDB()
	print_info(red("  * Checking MD5 of ")+yellow(pkgfile)+red(": should be ")+bold(storedmd5), back = True)
	md5check = compareMd5(etpConst['packagesbindir']+"/"+branch+"/"+pkgfile,storedmd5)
	if (md5check):
	    print_info(red("  * Package ")+yellow(pkgfile)+red("downloaded successfully."))
	    return True
	else:
	    if (tries == maxtries):
		entropyLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: Max tries limit reached. Checksum does not match. Please consider to download or repackage again. Giving up.")
		print_warning(red("  * Package ")+yellow(pkgfile)+red(" checksum does not match. Please consider to download or repackage again. Giving up."))
		return False
	    else:
		entropyLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_VERBOSE,"downloadPackageFromMirror: Checksum does not match. Trying to download it again...")
		print_warning(red("  * Package ")+yellow(pkgfile)+red(" checksum does not match. Trying to download it again..."))
		tries += 1
		if os.path.isfile(etpConst['packagesbindir']+"/"+branch+"/"+pkgfile):
		    os.remove(etpConst['packagesbindir']+"/"+branch+"/"+pkgfile)

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
	        ftp.closeConnection()
	        continue
	else:
	    if (not ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
		entropyLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"lockDatabases: mirror "+extractFTPHostFromUri(uri)+" already unlocked.")
	        print_info(green(" * ")+red("Mirror database at ")+bold(extractFTPHostFromUri(uri))+red(" already unlocked."))
	        ftp.closeConnection()
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
	ftp.closeConnection()
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
	        ftp.closeConnection()
	        continue
	else:
	    if (not ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile'])):
		entropyLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_VERBOSE,"downloadLockDatabases: already unlocked -> "+extractFTPHostFromUri(uri))
	        print_info(green(" * ")+red("Download mirror at ")+bold(extractFTPHostFromUri(uri))+red(" already unlocked."))
	        ftp.closeConnection()
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
	ftp.closeConnection()
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
