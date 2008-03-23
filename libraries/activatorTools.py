#!/usr/bin/python
'''
    # DESCRIPTION:
    # generic tools for enzyme application

    Copyright (C) 2007-2008 Fabio Erculiani

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

import time
import shutil
from entropyConstants import *
from serverConstants import *
from outputTools import *
from entropy import FtpInterface, EquoInterface, rssFeed, LogFile
import exceptionTools
Entropy = EquoInterface(noclientdb = 2)

# Logging initialization
activatorLog = LogFile(level=etpConst['activatorloglevel'],filename = etpConst['activatorlogfile'], header = "[Activator]")

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
            rc = packages(["sync"])
        else:
            ask = etpUi['ask']
            etpUi['ask'] = True
            rc = packages(["sync"])
            etpUi['ask'] = ask
        # then sync the database, if the packages sync completed successfully
        if rc:
            if (not activatorRequestNoAsk) and etpConst['rss-feed']:
                etpRSSMessages['commitmessage'] = readtext(">> Please insert a commit message: ")
            elif etpConst['rss-feed']:
                etpRSSMessages['commitmessage'] = "Autodriven Update"
            # if packages are ok, we can sync the database
            database(["sync"])
            if (not activatorRequestNoAsk):
                # ask question
                rc = Entropy.askQuestion("     Should I continue with the tidy procedure ?")
                if rc == "No":
                    sys.exit(0)

    print_info(green(" * ")+red("Starting to collect packages that would be removed from the repository ..."))
    for mybranch in etpConst['branches']:

        print_info(red(" * ")+blue("Switching to branch: ")+bold(mybranch))

        # now it's time to do some tidy
        # collect all the binaries in the database
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)
        dbBinaries = dbconn.listBranchPackagesTbz2(mybranch)
        dbconn.closeDB()

        # list packages in the packages directory
        repoBinaries = os.listdir(etpConst['packagesbindir']+"/"+mybranch)

        removeList = []
        # select packages
        for repoBin in repoBinaries:
            if (repoBin.endswith(".tbz2")):
                if repoBin not in dbBinaries:
                    # check if it's expired
                    filepath = etpConst['packagesbindir']+"/"+mybranch+"/"+repoBin
                    if os.path.isfile(filepath+etpConst['packagesexpirationfileext']):
                        # check mtime
                        mtime = Entropy.entropyTools.getFileUnixMtime(filepath+etpConst['packagesexpirationfileext'])
                        delta = int(etpConst['packagesexpirationdays'])*24*3600
                        currmtime = time.time()
                        if currmtime - mtime > delta: # if it's expired
                            removeList.append(repoBin)
                    else:
                        # create expiration file
                        f = open(filepath+etpConst['packagesexpirationfileext'],"w")
                        f.write("\n")
                        f.flush()
                        f.close()
                        # not expired.

        if (not removeList):
            activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"sync: no packages to remove from the lirrors.")
            print_info(green(" * ")+red("No packages to remove from the mirrors."))
            print_info(green(" * ")+red("Syncronization across mirrors completed."))
            continue

        print_info(green(" * ")+red("This is the list of files that would be removed from the mirrors: "))
        for xfile in removeList:
            print_info(green("\t* ")+brown(xfile))

        # ask question
        if (not activatorRequestNoAsk):
            rc = Entropy.askQuestion("     Would you like to continue ?")
            if rc == "No":
                sys.exit(0)

        # remove them!
        activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"sync: starting to remove packages from mirrors.")
        for uri in etpConst['activatoruploaduris']:
            activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"sync: connecting to mirror "+Entropy.entropyTools.extractFTPHostFromUri(uri))
            print_info(green(" * ")+red("Connecting to: ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)))
            ftp = FtpInterface(uri, Entropy)
            ftp.setCWD(etpConst['binaryurirelativepath']+"/"+mybranch)
            for xfile in removeList:

                activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"sync: removing (remote) file "+xfile)
                print_info(green(" * ")+red("Removing file: ")+bold(xfile), back = True)
                # remove remotely
                if (ftp.isFileAvailable(xfile)):
                    rc = ftp.deleteFile(xfile)
                    if (rc):
                        print_info(green(" * ")+red("Package file: ")+bold(xfile)+red(" removed successfully from ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)))
                    else:
                        print_warning(brown(" * ")+red("ATTENTION: remote file ")+bold(xfile)+red(" cannot be removed."))
                # checksum
                if (ftp.isFileAvailable(xfile+etpConst['packageshashfileext'])):
                    rc = ftp.deleteFile(xfile+etpConst['packageshashfileext'])
                    if (rc):
                        print_info(green(" * ")+red("Checksum file: ")+bold(xfile+etpConst['packageshashfileext'])+red(" removed successfully from ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)))
                    else:
                        print_warning(brown(" * ")+red("ATTENTION: remote checksum file ")+bold(xfile)+red(" cannot be removed."))
                # remove locally
                if os.path.isfile(etpConst['packagesbindir']+"/"+mybranch+"/"+xfile):
                    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"sync: removing (local) file "+xfile)
                    print_info(green(" * ")+red("Package file: ")+bold(xfile)+red(" removed successfully from ")+bold(etpConst['packagesbindir']+"/"+mybranch))
                    os.remove(etpConst['packagesbindir']+"/"+mybranch+"/"+xfile)
                    try:
                        os.remove(etpConst['packagesbindir']+"/"+mybranch+"/"+xfile+etpConst['packagesexpirationfileext'])
                    except OSError:
                        pass
                # checksum
                if os.path.isfile(etpConst['packagesbindir']+"/"+mybranch+"/"+xfile+etpConst['packageshashfileext']):
                    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"sync: removing (local) file "+xfile+etpConst['packageshashfileext'])
                    print_info(green(" * ")+red("Checksum file: ")+bold(xfile+etpConst['packageshashfileext'])+red(" removed successfully from ")+bold(etpConst['packagesbindir']+"/"+mybranch))
                    os.remove(etpConst['packagesbindir']+"/"+mybranch+"/"+xfile+etpConst['packageshashfileext'])
            ftp.closeConnection()

    print_info(green(" * ")+red("Syncronization across mirrors completed."))


def packages(options):

    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: called with options -> "+str(options))

    # Options available for all the packages submodules
    myopts = options[1:]
    activatorRequestPackagesCheck = False
    for opt in myopts:
        if (opt == "--do-packages-check"):
            activatorRequestPackagesCheck = True

    if not options:
        return

    if (options[0] == "sync"):

        print_info(green(" * ")+red("Starting ")+bold("binary")+brown(" packages")+red(" syncronization across servers ..."))

        totalUris = len(etpConst['activatoruploaduris'])
        currentUri = 0
        totalSuccessfulUri = 0
        mirrorsTainted = False

        activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: called sync.")

        for uri in etpConst['activatoruploaduris']:

            uriSuccessfulSync = 0
            currentUri += 1
            try:
                print_info(green(" * ")+brown("Working on ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)+red(" mirror.")))

                pkgbranches = os.listdir(etpConst['packagessuploaddir'])
                pkgbranches = [x for x in pkgbranches if os.path.isdir(etpConst['packagessuploaddir']+"/"+x)]

                for mybranch in pkgbranches:

                    print_info(red(" * ")+blue("Switching to branch: ")+bold(mybranch))
                    print_info(green(" * ")+brown("Local Statistics: "))
                    print_info(green(" * ")+red("Calculating packages in ")+bold(etpConst['packagessuploaddir']+"/"+mybranch)+red(" ..."), back = True)

                    uploadCounter = 0
                    toBeUploaded = set() # parse etpConst['packagessuploaddir']
                    for tbz2 in os.listdir(etpConst['packagessuploaddir']+"/"+mybranch):
                        if tbz2.endswith(".tbz2") or tbz2.endswith(etpConst['packageshashfileext']):
                            toBeUploaded.add(tbz2)
                            if tbz2.endswith(".tbz2"):
                                uploadCounter += 1

                    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: upload directory stats -> files: "+str(uploadCounter)+" | upload packages list: "+str(toBeUploaded))

                    print_info(green(" * ")+red("Upload directory:\t\t")+bold(str(uploadCounter))+red(" files ready."))
                    localPackagesRepository = set() # parse etpConst['packagesbindir']
                    print_info(green(" * ")+red("Calculating packages in ")+bold(etpConst['packagesbindir']+"/"+mybranch)+red(" ..."), back = True)
                    packageCounter = 0
                    for tbz2 in os.listdir(etpConst['packagesbindir']+"/"+mybranch):
                        if tbz2.endswith(".tbz2") or tbz2.endswith(etpConst['packageshashfileext']):
                            localPackagesRepository.add(tbz2)
                            if tbz2.endswith(".tbz2"):
                                packageCounter += 1

                    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: packages directory stats -> files: "+str(packageCounter)+" | download packages list (including md5): "+str(localPackagesRepository))

                    print_info(green(" * ")+red("Packages directory:\t")+bold(str(packageCounter))+red(" files ready."))

                    print_info(green(" * ")+brown("Fetching remote statistics..."), back = True)
                    ftp = FtpInterface(uri, Entropy)
                    try:
                        ftp.setCWD(etpConst['binaryurirelativepath'])
                    except:
                        bdir = ""
                        for mydir in etpConst['binaryurirelativepath'].split("/"):
                            bdir += "/"+mydir
                            if (not ftp.isFileAvailable(bdir)):
                                try:
                                    ftp.mkdir(bdir)
                                except Exception, e:
                                    if str(e).find("550") != -1:
                                        pass
                                    else:
                                        raise
                        ftp.setCWD(etpConst['binaryurirelativepath'])

                    if (not ftp.isFileAvailable(mybranch)):
                        ftp.mkdir(mybranch)
                    ftp.setCWD(mybranch)
                    remotePackages = ftp.listDir()
                    remotePackagesInfo = ftp.getRoughList()
                    ftp.closeConnection()

                    print_info(green(" * ")+brown("Remote statistics"))
                    remoteCounter = 0
                    for tbz2 in remotePackages:
                        if tbz2.endswith(".tbz2"):
                            remoteCounter += 1

                    remote_packages_metadata = {}
                    for remote_package in remotePackagesInfo:
                        remote_packages_metadata[remote_package.split()[8]] = int(remote_package.split()[4])

                    print_info(green(" * ")+red("Remote packages:\t\t")+bold(str(remoteCounter))+red(" files stored."))
                    print_info(green(" * ")+brown("Calculating..."))
                    uploadQueue = set()
                    downloadQueue = set()
                    removalQueue = set()

                    activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"packages: starting packages calculation...")

                    finePackages = set()
                    # Fill uploadQueue and if something weird is found, add the packages to downloadQueue
                    for localPackage in toBeUploaded:
                        if localPackage in remotePackages:
                            # it's already on the mirror, but... is its size correct??
                            localSize = int(os.stat(etpConst['packagessuploaddir']+"/"+mybranch+"/"+localPackage)[6])
                            remoteSize = remote_packages_metadata.get(localPackage)
                            if remoteSize == None:
                                remoteSize = 0
                            #print localPackage,"==>",localSize, remoteSize
                            if (localSize != remoteSize):
                                # size does not match, adding to the upload queue
                                uploadQueue.add(localPackage)
                            else:
                                finePackages.add(localPackage) # just move from upload to packages
                        else:
                            # always force upload of packages in uploaddir
                            uploadQueue.add(localPackage)

                    # if a package is in the packages directory but not online, we have to upload it
                    # we have localPackagesRepository and remotePackages
                    for localPackage in localPackagesRepository:
                        if localPackage in remotePackages:
                            # it's already on the mirror, but... is its size correct??
                            localSize = int(os.stat(etpConst['packagesbindir']+"/"+mybranch+"/"+localPackage)[6])
                            remoteSize = remote_packages_metadata.get(localPackage)
                            if remoteSize == None:
                                remoteSize = 0
                            if (localSize != remoteSize) and (localSize != 0):
                                # size does not match, adding to the upload queue
                                if localPackage not in finePackages:
                                    uploadQueue.add(localPackage)
                        else:
                            # this means that the local package does not exist
                            # so, we need to download it
                            uploadQueue.add(localPackage)

                    # Fill downloadQueue and removalQueue
                    for remotePackage in remotePackages:
                        if remotePackage in localPackagesRepository:
                            # it's already on the mirror, but... is its size correct??
                            localSize = int(os.stat(etpConst['packagesbindir']+"/"+mybranch+"/"+remotePackage)[6])
                            remoteSize = remote_packages_metadata.get(remotePackage)
                            if remoteSize == None:
                                remoteSize = 0
                            if (localSize != remoteSize) and (localSize != 0):
                                # size does not match, remove first
                                #print "removal of "+localPackage+" because its size differ"
                                if remotePackage not in uploadQueue: # do it only if the package has not been added to the uploadQueue
                                    removalQueue.add(remotePackage) # remotePackage == localPackage # just remove something that differs from the content of the mirror
                                    # then add to the download queue
                                    downloadQueue.add(remotePackage)
                        else:
                            # this means that the local package does not exist
                            # so, we need to download it
                            if not remotePackage.endswith(".tmp"): # ignore .tmp files
                                downloadQueue.add(remotePackage)

                    # Collect packages that don't exist anymore in the database
                    # so we can filter them out from the download queue
                    # Why downloading something that will be removed??
                    # the same thing for the uploadQueue...
                    dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)
                    dbFiles = dbconn.listBranchPackagesTbz2(mybranch)
                    dbconn.closeDB()

                    exclude = set()
                    for dlFile in downloadQueue:
                        if dlFile.endswith(".tbz2"):
                            if dlFile not in dbFiles:
                                exclude.add(dlFile)
                    downloadQueue.difference_update(exclude)

                    exclude = set()
                    for upFile in uploadQueue:
                        if upFile.endswith(".tbz2"):
                            if upFile not in dbFiles:
                                exclude.add(upFile)
                    uploadQueue.difference_update(exclude)

                    # now filter things
                    # packages in uploadQueue should be removed, if found, from downloadQueue
                    exclude = set()
                    for p in downloadQueue:
                        # search inside uploadQueue
                        if p in uploadQueue:
                            exclude.add(p)
                    downloadQueue.difference_update(exclude)

                    if (not uploadQueue) and (not downloadQueue) and (not removalQueue):
                        print_info(green(" * ")+red("Nothing to syncronize for ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)+red(". Queue empty.")))
                        uriSuccessfulSync += 1
                        if (uriSuccessfulSync == len(pkgbranches)):
                            totalSuccessfulUri += 1
                        continue

                    totalRemovalSize = 0
                    totalDownloadSize = 0
                    totalUploadSize = 0

                    print_info(green(" * ")+brown("Queue tasks:"))
                    detailedRemovalQueue = []
                    detailedDownloadQueue = []
                    detailedUploadQueue = []
                    # this below is used when a package has been already uploaded
                    # but something weird happened and it hasn't been moved to the packages dir
                    simpleCopyQueue = []

                    for item in removalQueue:
                        fileSize = os.stat(etpConst['packagesbindir']+"/"+mybranch+"/"+item)[6]
                        totalRemovalSize += int(fileSize)
                        print_info(bold("\t[") + red("LOCAL REMOVAL") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(Entropy.entropyTools.bytesIntoHuman(fileSize)))
                        detailedRemovalQueue.append([item,fileSize])

                    for item in downloadQueue:
                        # if the package is already in the upload directory, do not add the size
                        if not os.path.isfile(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item):
                            fileSize = remote_packages_metadata.get(item)
                            if fileSize == None:
                                fileSize = "0"
                            else:
                                fileSize = str(fileSize)
                            if not item.endswith(etpConst['packageshashfileext']): # do not show .md5 to upload
                                totalDownloadSize += int(fileSize)
                                print_info(bold("\t[") + brown("REMOTE DOWNLOAD") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(Entropy.entropyTools.bytesIntoHuman(fileSize)))
                            detailedDownloadQueue.append([item,fileSize])
                        else:
                            if (not item.endswith(etpConst['packageshashfileext'])):
                                fileSize = os.stat(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item)[6]
                                print_info(bold("\t[") + green("LOCAL COPY") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(Entropy.entropyTools.bytesIntoHuman(fileSize)))
                            # file exists locally and remotely (where is fine == fully uploaded)
                            simpleCopyQueue.append(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item)

                    for item in uploadQueue:
                        # if it is in the upload dir
                        if os.path.isfile(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item):
                            fileSize = os.stat(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item)[6]
                        else: # otherwise it is in the packages dir
                            fileSize = os.stat(etpConst['packagesbindir']+"/"+mybranch+"/"+item)[6]
                        if not item.endswith(etpConst['packageshashfileext']): # do not show .md5 to upload
                            print_info(bold("\t[") + red("REMOTE UPLOAD") + bold("] ") + red(item.split(".tbz2")[0]) + bold(".tbz2 ") + blue(Entropy.entropyTools.bytesIntoHuman(fileSize)))
                            totalUploadSize += int(fileSize)
                            detailedUploadQueue.append([item,fileSize])

                    # thanks
                    del remote_packages_metadata

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

                    print_info(red(" * ")+blue("Packages that would be ")+red("removed:\t\t\t")+bold(str(removalQueueLength)))
                    print_info(red(" * ")+blue("Packages that would be ")+brown("downloaded/moved locally:\t")+bold(str(downloadQueueLength)))
                    print_info(red(" * ")+blue("Packages that would be ")+green("uploaded:\t\t\t")+bold(str(uploadQueueLength)))
                    print_info(red(" * ")+blue("Total removal ")+red("size:\t\t\t\t")+bold(Entropy.entropyTools.bytesIntoHuman(str(totalRemovalSize))))
                    print_info(red(" * ")+blue("Total download ")+brown("size:\t\t\t\t")+bold(Entropy.entropyTools.bytesIntoHuman(str(totalDownloadSize))))
                    print_info(red(" * ")+blue("Total upload ")+green("size:\t\t\t\t")+bold(Entropy.entropyTools.bytesIntoHuman(str(totalUploadSize))))

                    if (etpUi['pretend']):
                        continue
                    if (not removalQueueLength and not downloadQueueLength and not uploadQueueLength):
                        print_info(green(" * ")+red("Nothing to syncronize for ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)+red(". Queue empty.")))
                        uriSuccessfulSync += 1
                        if (uriSuccessfulSync == len(pkgbranches)):
                            totalSuccessfulUri += 1
                        continue
                    if (etpUi['ask']):
                        rc = Entropy.askQuestion("\n     Would you like to run the steps above ?")
                        if rc == "No":
                            print "\n"
                            continue

                    # queues management
                    successfulUploadCounter = 0
                    successfulDownloadCounter = 0
                    uploadCounter = "0"
                    downloadCounter = "0"

                    # removal queue
                    if (detailedRemovalQueue):
                        for item in detailedRemovalQueue:
                            print_info(red(" * Removing file ")+bold(item[0]) + red(" [")+blue(Entropy.entropyTools.bytesIntoHuman(item[1]))+red("] from ")+ bold(etpConst['packagesbindir']+"/"+mybranch)+red(" ..."))
                            try:
                                os.remove(etpConst['packagesbindir']+"/"+mybranch+"/"+item[0])
                            except OSError:
                                pass
                            try:
                                os.remove(etpConst['packagesbindir']+"/"+mybranch+"/"+item[0]+etpConst['packageshashfileext'])
                            except OSError:
                                pass
                        print_info(red(" * Removal completed for ")+bold(etpConst['packagesbindir']+"/"+mybranch))

                    # simple copy queue
                    if (simpleCopyQueue):
                        for item in simpleCopyQueue:
                            print_info(red(" * Copying file from ") + bold(item) + red(" to ")+bold(etpConst['packagesbindir']+"/"+mybranch))
                            toitem = etpConst['packagesbindir']+"/"+mybranch+"/"+os.path.basename(item)
                            if not os.path.isdir(os.path.dirname(toitem)):
                                os.makedirs(os.path.dirname(toitem))
                            # md5 copy not needed, already in simpleCopyQueue
                            shutil.copy2(item,toitem)
                            if os.path.isfile(toitem+etpConst['packagesexpirationfileext']): # clear expiration file
                                os.remove(toitem+etpConst['packagesexpirationfileext'])


                    # upload queue
                    if (detailedUploadQueue):
                        mirrorsTainted = True
                        ftp = FtpInterface(uri, Entropy)
                        ftp.setCWD(etpConst['binaryurirelativepath']+"/"+mybranch)
                        uploadCounter = str(len(detailedUploadQueue))
                        currentCounter = 0
                        for item in detailedUploadQueue:
                            currentCounter += 1
                            counterInfo = bold(" (")+blue(str(currentCounter))+"/"+red(uploadCounter)+bold(")")
                            print_info(counterInfo+red(" Uploading file ")+bold(item[0]) + red(" [")+blue(Entropy.entropyTools.bytesIntoHuman(item[1]))+red("] to ")+ bold(Entropy.entropyTools.extractFTPHostFromUri(uri)) +red(" ..."))
                            # is the package in the upload queue?
                            if os.path.isfile(etpConst['packagessuploaddir']+"/"+mybranch+"/"+item[0]):
                                uploadItem = etpConst['packagessuploaddir']+"/"+mybranch+"/"+item[0]
                            else:
                                uploadItem = etpConst['packagesbindir']+"/"+mybranch+"/"+item[0]

                            ckOk = False
                            while not ckOk:
                                rc = ftp.uploadFile(uploadItem)
                                print_info("    "+red("   -> Verifying ")+green(item[0])+bold(" checksum")+red(" (if supported)"), back = True)
                                ck = Entropy.get_remote_package_checksum(Entropy.entropyTools.extractFTPHostFromUri(uri),item[0], mybranch)
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
                                            ckres = Entropy.entropyTools.compareMd5(uploadItem,ck)
                                            if (ckres):
                                                print_info("    "+red("   -> Package ")+bold(item[0])+red(" has been uploaded correctly."))
                                                ckOk = True
                                            else:
                                                print_warning("    "+red("   -> Package ")+bold(item[0])+brown(" has NOT been uploaded correctly. Reuploading..."))
                                        else:
                                            # hum, what the hell is this checksum!?!?!?!
                                            print_warning("    "+red("   -> Package ")+bold(item[0])+red(" does not have a proper checksum: "+str(ck)+". Reuploading..."))

                            if not os.path.isfile(uploadItem+etpConst['packageshashfileext']):
                                hashfile = Entropy.entropyTools.createHashFile(uploadItem)
                            else:
                                hashfile = uploadItem+etpConst['packageshashfileext']

                            # upload md5 hash
                            print_info("    "+red("   -> Uploading checksum of ")+bold(item[0]) + red(" to ") + bold(Entropy.entropyTools.extractFTPHostFromUri(uri)) +red(" ..."))
                            ckOk = False
                            while not ckOk:
                                rcmd5 = ftp.uploadFile(hashfile,ascii = True)
                                print_info("    "+red("   -> Verifying ")+green(item[0]+etpConst['packageshashfileext'])+bold(" checksum")+red(" (if supported)"), back = True)
                                ck = Entropy.get_remote_package_checksum(Entropy.entropyTools.extractFTPHostFromUri(uri),item[0]+etpConst['packageshashfileext'], mybranch)
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
                                            ckres = Entropy.entropyTools.compareMd5(hashfile,ck)
                                            if (ckres):
                                                print_info("    "+red("   -> Package ")+bold(item[0]+etpConst['packageshashfileext'])+red(" has been uploaded correctly."))
                                                ckOk = True
                                            else:
                                                print_warning("    "+red("   -> Package ")+bold(item[0]+etpConst['packageshashfileext'])+brown(" has NOT been uploaded correctly. Reuploading..."))
                                        else:
                                            # hum, what the hell is this checksum!?!?!?!
                                            print_warning("    "+red("   -> Package ")+bold(item[0]+etpConst['packageshashfileext'])+red(" does not have a proper checksum: "+str(ck)+" Reuploading..."))

                            # now check
                            if (rc) and (rcmd5):
                                successfulUploadCounter += 1
                        print_info(red(" * Upload completed for ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)))
                        ftp.closeConnection()

                    # download queue
                    if (detailedDownloadQueue):
                        ftp = FtpInterface(uri, Entropy)
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
                            print_info(counterInfo+red(" Downloading file ")+bold(item[0]) + red(" [")+blue(Entropy.entropyTools.bytesIntoHuman(item[1]))+red("] from ")+ bold(Entropy.entropyTools.extractFTPHostFromUri(uri)) +red(" ..."))

                            ckOk = False
                            while not ckOk:

                                if item[0].endswith(etpConst['packageshashfileext']):
                                    rc = ftp.downloadFile(item[0],etpConst['packagesbindir']+"/"+mybranch+"/", ascii = True)
                                else:
                                    rc = ftp.downloadFile(item[0],etpConst['packagesbindir']+"/"+mybranch+"/")

                                if not item[0].endswith(etpConst['packageshashfileext']):
                                    print_info(counterInfo+red("   -> Verifying ")+green(item[0])+bold(" checksum")+red(" (if supported)"), back = True)
                                    ck = Entropy.get_remote_package_checksum(Entropy.entropyTools.extractFTPHostFromUri(uri),item[0], mybranch)
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
                                                ckres = Entropy.entropyTools.compareMd5(filepath,ck)
                                                if (ckres):
                                                    print_info(counterInfo+red("   -> Package ")+bold(item[0])+red(" has been downloaded correctly."))
                                                    ckOk = True
                                                else:
                                                    print_warning(counterInfo+red("   -> Package ")+bold(item[0])+brown(" has NOT been downloaded correctly. Redownloading..."))
                                            else:
                                                # hum, what the hell is this checksum!?!?!?!
                                                print_warning(counterInfo+red("   -> Package ")+bold(item[0])+red(" does not have a proper checksum: "+str(ck)+" Redownloading..."))
                                else: # skip checking for .md5 files
                                    ckOk = True

                            if (rc):
                                successfulDownloadCounter += 1

                        print_info(red(" * Download completed for ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)))
                        ftp.closeConnection()

                    uploadCounter = int(uploadCounter)
                    downloadCounter = int(downloadCounter)

                    if (successfulUploadCounter == uploadCounter) and (successfulDownloadCounter == downloadCounter):
                        uriSuccessfulSync += 1

                    if (uriSuccessfulSync == len(pkgbranches)):
                        totalSuccessfulUri += 1

            # trap exceptions, failed to upload/download someting?
            except Exception, e: # FIXME: only trap proper ftp exceptions

                print_error(brown(" * ")+red("packages: Exception caught: ")+str(e)+red(" . Showing traceback:"))
                import traceback
                traceback.print_exc()

                # trap CTRL+C
                if (str(e) == "100"):
                    sys.exit(0)

                activatorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"packages: Exception caught: "+str(e)+" . Trying to continue if possible.")
                activatorLog.log(ETP_LOGPRI_WARNING,ETP_LOGLEVEL_NORMAL,"packages: cannot properly syncronize "+Entropy.entropyTools.extractFTPHostFromUri(uri)+". Trying to continue if possible.")

                # print warning cannot sync uri
                print_warning(brown(" * ")+red("ATTENTION: cannot properly syncronize ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Continuing if possible..."))

                # decide what to do
                if (totalSuccessfulUri > 0) or (etpUi['pretend']):
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
                        print_error(brown(" * ")+red("ERROR: no mirrors have been properly syncronized. Check network status and retry. Cannot continue."))
                        return False


        # if at least one server has been synced successfully, move files
        if (totalSuccessfulUri > 0):
            if etpUi['pretend']:
                return False
            activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"packages: all done. Now it's time to move packages to "+etpConst['packagesbindir'])
            pkgbranches = os.listdir(etpConst['packagessuploaddir'])
            pkgbranches = [x for x in pkgbranches if os.path.isdir(etpConst['packagessuploaddir']+"/"+x)]
            for branch in pkgbranches:
                branchcontent = os.listdir(etpConst['packagessuploaddir']+"/"+branch)
                for xfile in branchcontent:
                    source = etpConst['packagessuploaddir']+"/"+branch+"/"+xfile
                    destdir = etpConst['packagesbindir']+"/"+branch
                    if not os.path.isdir(destdir):
                        os.makedirs(destdir)
                    dest = destdir+"/"+xfile
                    shutil.move(source,dest)
                    if os.path.isfile(dest+etpConst['packagesexpirationfileext']): # clear expiration file
                        os.remove(dest+etpConst['packagesexpirationfileext'])
            return mirrorsTainted
        else:
            raise exceptionTools.OnlineMirrorError("OnlineMirrorError: neither a mirror has been properly sync'd.")

        # Now we should start to check all the packages in the packages directory
        if (activatorRequestPackagesCheck):
            import reagentTools
            reagentTools.database(['md5check'])

        return False


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
        print_info(brown(" * ")+green("Mirrors status table:"))
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
            print_info(bold("\t"+Entropy.entropyTools.extractFTPHostFromUri(db[0])+": ")+red("[")+brown("DATABASE: ")+db[1]+red("] [")+brown("DOWNLOAD: ")+db[2]+red("]"))

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
            ftp = FtpInterface(uri, Entropy)
            try:
                ftp.setCWD(etpConst['etpurirelativepath'])
            except:
                bdir = ""
                for mydir in etpConst['etpurirelativepath'].split("/"):
                    bdir += "/"+mydir
                    if (not ftp.isFileAvailable(bdir)):
                        try:
                            ftp.mkdir(bdir)
                        except Exception, e:
                            if str(e).find("550") != -1:
                                pass
                            else:
                                raise
                ftp.setCWD(etpConst['etpurirelativepath'])
            if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])) or (ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile'])):
                mirrorsLocked = True
                ftp.closeConnection()
                break

        if (mirrorsLocked):
            # if the mirrors are locked, we need to check if we have
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
                raise exceptionTools.OnlineMirrorError("OnlineMirrorError: At the moment, mirrors are locked, someone is working on their databases, try again later...")

        else:
            if (dbLockFile):
                activatorLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"database (sync inside activatorTools): Mirrors are not locked remotely but the local database is. It is a non-sense. Please remove the lock file "+etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])
                raise exceptionTools.OnlineMirrorError("OnlineMirrorError: Mirrors are not locked remotely but the local database is. It is a non-sense. Please remove the lock file "+etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])
            else:
                activatorLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"database (sync inside activatorTools): Mirrors are not locked. Fetching data...")
                print_info(green(" * ")+red("Mirrors are not locked. Fetching data..."))

            syncRemoteDatabases()

    else:
        print_error(red(" * ")+green("No valid tool specified."))

########################################################
####
##   Database handling functions
#

def syncRemoteDatabases(noUpload = False, justStats = False):

    remoteDbsStatus = getEtpRemoteDatabaseStatus()
    print_info(green(" * ")+red("Remote Entropy Database Repository Status:"))
    for dbstat in remoteDbsStatus:
        print_info(green("\t Host:\t")+bold(Entropy.entropyTools.extractFTPHostFromUri(dbstat[0])))
        print_info(red("\t  * Database revision: ")+blue(str(dbstat[1])))

    # check if the local DB or the revision file exist
    # in this way we can regenerate the db without messing the --initialize function with a new unwanted download
    etpDbLocalRevision = 0
    if os.path.isfile(etpConst['etpdatabasefilepath']):
        # file exist, get revision if we can
        if os.path.isfile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile']):
            f = open(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'],"r")
            etpDbLocalRevision = int(f.readline().strip())
            f.close()

    print_info(red("\t  * Database local revision currently at: ")+blue(str(etpDbLocalRevision)))

    if (justStats):
        return

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
                latestrevision = Entropy.entropyTools.alphaSorter(revisions)[len(revisions)-1]
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

            latestrevision = int(Entropy.entropyTools.alphaSorter(revisions)[len(revisions)-1])
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
            for xlist in uploadList:
                if xlist[0].startswith(uri):
                    _uploadList.append(uri)
                    break

        uploadDatabase(_uploadList)
        print_info(green(" * ")+red("All the mirrors have been updated."))

    remoteDbsStatus = getEtpRemoteDatabaseStatus()
    print_info(green(" * ")+red("Remote Entropy Database Repository Status:"))
    for dbstat in remoteDbsStatus:
        print_info(green("\t Host:\t")+bold(Entropy.entropyTools.extractFTPHostFromUri(dbstat[0])))
        print_info(red("\t  * Database revision: ")+blue(str(dbstat[1])))


def uploadDatabase(uris):

    import gzip
    import bz2

    ### PREPARE RSS FEED
    if etpConst['rss-feed']:
        rssClass = rssFeed(etpConst['etpdatabasedir'] + "/" + etpConst['rss-name'], maxentries = etpConst['rss-max-entries'])
        # load dump
        db_actions = Entropy.dumpTools.loadobj(etpConst['rss-dump-name'])
        if db_actions:
            try:
                f = open(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'])
                revision = f.readline().strip()
                f.close()
            except:
                revision = "N/A"
                pass
            commitmessage = ''
            if etpRSSMessages['commitmessage']:
                commitmessage = ' :: '+etpRSSMessages['commitmessage']
            title = ": "+etpConst['systemname']+" "+etpConst['product'][0].upper()+etpConst['product'][1:]+" "+etpConst['branch']+" :: Revision: "+revision+commitmessage
            link = etpConst['rss-base-url']
            # create description
            added_items = db_actions.get("added")
            if added_items:
                for atom in added_items:
                    mylink = link+"?search="+atom.split("~")[0]+"&arch="+etpConst['currentarch']+"&product="+etpConst['product']
                    description = atom+": "+added_items[atom]['description']
                    rssClass.addItem(title = "Added/Updated"+title, link = mylink, description = description)
            removed_items = db_actions.get("removed")
            if removed_items:
                for atom in removed_items:
                    description = atom+": "+removed_items[atom]['description']
                    rssClass.addItem(title = "Removed"+title, link = link, description = description)
            light_items = db_actions.get('light')
            if light_items:
                rssLight = rssFeed(etpConst['etpdatabasedir'] + "/" + etpConst['rss-light-name'], maxentries = etpConst['rss-light-max-entries'])
                for atom in light_items:
                    mylink = link+"?search="+atom.split("~")[0]+"&arch="+etpConst['currentarch']+"&product="+etpConst['product']
                    description = light_items[atom]['description']
                    rssLight.addItem(title = "["+revision+"] "+atom, link = mylink, description = description)
                rssLight.writeChanges()

        rssClass.writeChanges()
        # clean global vars
        etpRSSMessages.clear()
        Entropy.dumpTools.removeobj(etpConst['rss-dump-name'])

    for uri in uris:
        downloadLockDatabases(True,[uri])

        print_info(green(" * ")+red("Uploading database to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" ..."))
        print_info(green(" * ")+red("Connecting to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" ..."), back = True)
        ftp = FtpInterface(uri, Entropy)
        print_info(green(" * ")+red("Changing directory to ")+bold(etpConst['etpurirelativepath'])+red(" ..."), back = True)
        ftp.setCWD(etpConst['etpurirelativepath'])

        cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
        if cmethod == None: raise exceptionTools.InvalidDataType("InvalidDataType: wrong database compression method passed.")
        print_info(green(" * ")+red("Uploading file ")+bold(etpConst[cmethod[2]])+red(" ..."), back = True)

        dbfilec = eval(cmethod[0])(etpConst['etpdatabasedir'] + "/" + etpConst[cmethod[2]], "wb")

        dbpath = etpConst['etpdatabasefilepath']

        # dump the schema to a file
        schemafilename = etpConst['etpdatabasedir'] + "/" + etpConst[cmethod[3]]
        schemafilename_digest = etpConst['etpdatabasedir'] + "/" + etpConst[cmethod[4]]
        schemafile = eval(cmethod[0])(schemafilename, "w")
        dbconn = Entropy.openGenericDatabase(dbpath, xcache = False, indexing_override = False)
        dbconn.doDatabaseExport(schemafile)
        schemafile.close()
        dbconn.closeDB()
        del dbconn
        schema_hexdigest = Entropy.entropyTools.md5sum(schemafilename)

        # compress the database file first
        dbfile = open(dbpath,"rb")
        dbcont = dbfile.readlines()
        dbfile.close()
        for i in dbcont:
            dbfilec.write(i)
        dbfilec.close()
        del dbcont

        # uploading schema file
        rc = ftp.uploadFile(schemafilename)
        if (rc == True):
            print_info(green(" * ")+red("Upload of ")+bold(etpConst[cmethod[3]])+red(" completed."))
        else:
            print_warning(brown(" * ")+red("Cannot properly upload to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

        # uploading database file
        rc = ftp.uploadFile(etpConst['etpdatabasedir'] + "/" + etpConst[cmethod[2]])
        if (rc == True):
            print_info(green(" * ")+red("Upload of ")+bold(etpConst[cmethod[2]])+red(" completed."))
        else:
            print_warning(brown(" * ")+red("Cannot properly upload to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

        # remove the compressed file
        os.remove(etpConst['etpdatabasedir'] + "/" + etpConst[cmethod[2]])
        os.remove(schemafilename)

        # generate digest
        hexdigest = Entropy.entropyTools.md5sum(dbpath)
        f = open(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'],"w")
        f.write(hexdigest+"  "+etpConst['etpdatabasefile']+"\n")
        f.flush()
        f.close()

        # schema digest
        f = open(schemafilename_digest,"w")
        f.write(schema_hexdigest+"  "+etpConst[cmethod[3]]+"\n")
        f.flush()
        f.close()

        # upload schema digest
        print_info(green(" * ")+red("Uploading file ")+bold(etpConst[cmethod[4]])+red(" ..."), back = True)
        rc = ftp.uploadFile(schemafilename_digest,True)
        if (rc == True):
            print_info(green(" * ")+red("Upload of ")+bold(schemafilename_digest)+red(" completed."))
        else:
            print_warning(brown(" * ")+red("Cannot properly upload to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

        # upload digest
        print_info(green(" * ")+red("Uploading file ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'])+red(" ..."), back = True)
        rc = ftp.uploadFile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'],True)
        if (rc == True):
            print_info(green(" * ")+red("Upload of ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasehashfile'])+red(" completed."))
        else:
            print_warning(brown(" * ")+red("Cannot properly upload to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

        # uploading revision file
        print_info(green(" * ")+red("Uploading file ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'])+red(" ..."), back = True)
        rc = ftp.uploadFile(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'],True)
        if (rc == True):
            print_info(green(" * ")+red("Upload of ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile'])+red(" completed."))
        else:
            print_warning(brown(" * ")+red("Cannot properly upload to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

        # uploading package licenses whitelist (packages.db.lic_whitelist) file
        dblicwlfile = etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaselicwhitelistfile']
        if not os.path.isfile(dblicwlfile):
            f = open(dblicwlfile,"w")
            f.flush()
            f.close()
        print_info(green(" * ")+red("Uploading file ")+bold(dblicwlfile)+red(" ..."), back = True)
        rc = ftp.uploadFile(dblicwlfile,True)
        if (rc == True):
            print_info(green(" * ")+red("Upload of ")+bold(dblicwlfile)+red(" completed."))
        else:
            print_warning(brown(" * ")+red("Cannot properly upload to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

        # uploading packages mask list (packages.db.mask) file
        dbmaskfile = etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabasemaskfile']
        if not os.path.isfile(dbmaskfile):
            f = open(dbmaskfile,"w")
            f.flush()
            f.close()
        print_info(green(" * ")+red("Uploading file ")+bold(dbmaskfile)+red(" ..."), back = True)
        rc = ftp.uploadFile(dbmaskfile,True)
        if (rc == True):
            print_info(green(" * ")+red("Upload of ")+bold(dbmaskfile)+red(" completed."))
        else:
            print_warning(brown(" * ")+red("Cannot properly upload to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

        # uploading rss file (if enabled)
        if etpConst['rss-feed']:
            if os.path.isfile(etpConst['etpdatabasedir'] + "/" + etpConst['rss-name']):
                print_info(green(" * ")+red("Uploading file ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['rss-name'])+red(" ..."), back = True)
                rc = ftp.uploadFile(etpConst['etpdatabasedir'] + "/" + etpConst['rss-name'],True)
                if (rc == True):
                    print_info(green(" * ")+red("Upload of ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['rss-name'])+red(" completed."))
                else:
                    print_warning(brown(" * ")+red("Cannot properly upload to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

            if os.path.isfile(etpConst['etpdatabasedir'] + "/" + etpConst['rss-light-name']):
                print_info(green(" * ")+red("Uploading file ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['rss-light-name'])+red(" ..."), back = True)
                rc = ftp.uploadFile(etpConst['etpdatabasedir'] + "/" + etpConst['rss-light-name'],True)
                if (rc == True):
                    print_info(green(" * ")+red("Upload of ")+bold(etpConst['etpdatabasedir'] + "/" + etpConst['rss-light-name'])+red(" completed."))
                else:
                    print_warning(brown(" * ")+red("Cannot properly upload to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

        # close connection
        ftp.closeConnection()
        # unlock database
        downloadLockDatabases(False,[uri])

def downloadDatabase(uri):

    import gzip
    import bz2

    print_info(green(" * ")+red("Downloading database from ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" ..."))
    print_info(green(" * ")+red("Connecting to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" ..."), back = True)
    ftp = FtpInterface(uri, Entropy)
    print_info(green(" * ")+red("Changing directory to ")+bold(etpConst['etpurirelativepath'])+red(" ..."), back = True)
    ftp.setCWD(etpConst['etpurirelativepath'])

    cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
    if cmethod == None: raise exceptionTools.InvalidDataType("InvalidDataType: wrong database compression method passed.")

    unpackFunction = cmethod[1]
    dbfilename = etpConst[cmethod[2]]

    # downloading database file
    print_info(green(" * ")+red("Downloading file to ")+bold(dbfilename)+red(" ..."), back = True)
    rc = ftp.downloadFile(etpConst['etpdatabasedir'] + "/" + dbfilename,os.path.dirname(etpConst['etpdatabasefilepath']))
    if (rc == True):
        print_info(green(" * ")+red("Download of ")+bold(dbfilename)+red(" completed."))
    else:
        print_warning(brown(" * ")+red("Cannot properly download from ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

    # On the fly decompression
    print_info(green(" * ")+red("Decompressing ")+bold(dbfilename)+red(" ..."), back = True)

    eval(unpackFunction)(etpConst['etpdatabasedir'] + "/" + dbfilename)

    print_info(green(" * ")+red("Decompression of ")+bold(dbfilename)+red(" completed."))

    # downloading revision file
    print_info(green(" * ")+red("Downloading file to ")+bold(etpConst['etpdatabaserevisionfile'])+red(" ..."), back = True)
    rc = ftp.downloadFile(etpConst['etpdatabaserevisionfile'],os.path.dirname(etpConst['etpdatabasefilepath']),True)
    if (rc == True):
        print_info(green(" * ")+red("Download of ")+bold(etpConst['etpdatabaserevisionfile'])+red(" completed."))
    else:
        print_warning(brown(" * ")+red("Cannot properly download from ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

    # downloading package license whitelist (packages.db.lic_whitelist)
    print_info(green(" * ")+red("Downloading file to ")+bold(etpConst['etpdatabaselicwhitelistfile'])+red(" ..."), back = True)
    rc = ftp.downloadFile(etpConst['etpdatabaselicwhitelistfile'],os.path.dirname(etpConst['etpdatabasefilepath']),True)
    if (rc == True):
        print_info(green(" * ")+red("Download of ")+bold(etpConst['etpdatabaselicwhitelistfile'])+red(" completed."))
    else:
        print_warning(brown(" * ")+red("Cannot properly download from ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

    # downloading package mask list (packages.db.mask)
    print_info(green(" * ")+red("Downloading file to ")+bold(etpConst['etpdatabasemaskfile'])+red(" ..."), back = True)
    rc = ftp.downloadFile(etpConst['etpdatabasemaskfile'],os.path.dirname(etpConst['etpdatabasefilepath']),True)
    if (rc == True):
        print_info(green(" * ")+red("Download of ")+bold(etpConst['etpdatabasemaskfile'])+red(" completed."))
    else:
        print_warning(brown(" * ")+red("Cannot properly download from ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

    # downlading digest -> !!! FIXME !!! add digest verification
    print_info(green(" * ")+red("Downloading file to ")+bold(etpConst['etpdatabasehashfile'])+red(" ..."), back = True)
    rc = ftp.downloadFile(etpConst['etpdatabasehashfile'],os.path.dirname(etpConst['etpdatabasefilepath']),True)
    if (rc == True):
        print_info(green(" * ")+red("Download of ")+bold(etpConst['etpdatabasehashfile'])+red(" completed."))
    else:
        print_warning(brown(" * ")+red("Cannot properly download from ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

    # download RSS
    if etpConst['rss-feed']:

        for item in [etpConst['rss-name'],etpConst['rss-light-name']]:

            print_info(green(" * ")+red("Downloading file to ")+bold(item)+red(" ..."), back = True)
            try:
                rc = ftp.downloadFile(item,etpConst['etpdatabasedir'],True)
                if (rc == True):
                    print_info(green(" * ")+red("Download of ")+bold(item)+red(" completed."))
                else:
                    print_warning(brown(" * ")+red("Cannot properly download from ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))
            except:
                print_warning(brown(" * ")+red("Cannot properly download RSS file: "+item+" for: ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Please check."))

    try:
        os.remove(etpConst['etpdatabasedir'] + "/" + dbfilename)
    except OSError:
        pass
    # close connection
    ftp.closeConnection()

# Reports in a list form the lock status of the mirrors
# @ [ uri , True/False, True/False ] --> True = locked, False = unlocked
# @ the second parameter is referred to upload locks, while the second to download ones
def getMirrorsLock():

    # parse etpConst['activatoruploaduris']
    dbstatus = []
    for uri in etpConst['activatoruploaduris']:
        data = [ uri, False , False ]
        ftp = FtpInterface(uri, Entropy)
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

    uriDbInfo = []
    for uri in etpConst['activatoruploaduris']:
        ftp = FtpInterface(uri, Entropy)
        ftp.setCWD(etpConst['etpurirelativepath'])
        cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
        if cmethod == None: raise exceptionTools.InvalidDataType("InvalidDataType: wrong database compression method passed.")
        compressedfile = etpConst[cmethod[2]]
        rc = ftp.isFileAvailable(compressedfile)
        if (rc):
            # then get the file revision, if exists
            rc = ftp.isFileAvailable(etpConst['etpdatabaserevisionfile'])
            if (rc):
                # get the revision number
                ftp.downloadFile(etpConst['etpdatabaserevisionfile'],etpConst['packagestmpdir'],True)
                f = open( etpConst['packagestmpdir'] + "/" + etpConst['etpdatabaserevisionfile'],"r")
                revision = int(f.readline().strip())
                f.close()
                Entropy.entropyTools.spawnCommand("rm -f "+etpConst['packagestmpdir']+etpConst['etpdatabaserevisionfile'])
            else:
                revision = 0
        else:
            # then set mtime to 0 and quit
            revision = 0
        info = [uri+"/"+etpConst['etpurirelativepath']+compressedfile,revision]
        uriDbInfo.append(info)
        ftp.closeConnection()

    return uriDbInfo

def downloadPackageFromMirror(uri,pkgfile,branch):

    tries = 0
    maxtries = 5
    for i in range(maxtries):

        print_info(red("  * Connecting to ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)), back = True)
        # connect
        ftp = FtpInterface(uri, Entropy)
        ftp.setCWD(etpConst['binaryurirelativepath']+"/"+branch)
        # get the files
        print_info(red("  * Downloading ")+brown(pkgfile)+red(" from ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)))
        rc = ftp.downloadFile(pkgfile,etpConst['packagesbindir']+"/"+branch)
        if (rc is None):
            # file does not exist
            print_warning(red("  * File ")+brown(pkgfile)+red(" does not exist remotely on ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)))
            ftp.closeConnection()
            return None
        # check md5
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)
        idpackage = dbconn.getIDPackageFromDownload(pkgfile,branch)
        storedmd5 = dbconn.retrieveDigest(idpackage)
        dbconn.closeDB()
        print_info(red("  * Checking MD5 of ")+brown(pkgfile)+red(": should be ")+bold(storedmd5), back = True)
        md5check = Entropy.entropyTools.compareMd5(etpConst['packagesbindir']+"/"+branch+"/"+pkgfile,storedmd5)
        if (md5check):
            print_info(red("  * Package ")+brown(pkgfile)+red("downloaded successfully."))
            return True
        else:
            if (tries == maxtries):
                print_warning(red("  * Package ")+brown(pkgfile)+red(" checksum does not match. Please consider to download or repackage again. Giving up."))
                return False
            else:
                print_warning(red("  * Package ")+brown(pkgfile)+red(" checksum does not match. Trying to download it again..."))
                tries += 1
                if os.path.isfile(etpConst['packagesbindir']+"/"+branch+"/"+pkgfile):
                    os.remove(etpConst['packagesbindir']+"/"+branch+"/"+pkgfile)

def lockDatabases(lock = True, mirrorList = []):

    outstat = False
    if (mirrorList == []):
        mirrorList = etpConst['activatoruploaduris']
    for uri in mirrorList:

        if (lock):
            print_info(brown(" * ")+red("Locking ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" mirror..."),back = True)
        else:
            print_info(brown(" * ")+red("Unlocking ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" mirror..."),back = True)
        ftp = FtpInterface(uri, Entropy)
        # upload the lock file to database/%ARCH% directory
        ftp.setCWD(etpConst['etpurirelativepath'])
        # check if the lock is already there
        if (lock):
            if (ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
                print_info(green(" * ")+red("Mirror database at ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" already locked."))
                ftp.closeConnection()
                continue
        else:
            if (not ftp.isFileAvailable(etpConst['etpdatabaselockfile'])):
                print_info(green(" * ")+red("Mirror database at ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" already unlocked."))
                ftp.closeConnection()
                continue
        if (lock):
            f = open(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'],"w")
            f.write("database locked\n")
            f.flush()
            f.close()
            rc = ftp.uploadFile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'],ascii= True)
            if (rc == True):
                print_info(green(" * ")+red("Succesfully locked ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" mirror."))
            else:
                outstat = True
                print "\n"
                print_warning(red(" * ")+red("A problem occured while locking ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" mirror. Please have a look."))
                if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']):
                    os.remove(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])
        else:
            rc = ftp.deleteFile(etpConst['etpdatabaselockfile'])
            if (rc):
                print_info(green(" * ")+red("Succesfully unlocked ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" mirror."))
                if os.path.isfile(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile']):
                    os.remove(etpConst['etpdatabasedir']+"/"+etpConst['etpdatabaselockfile'])
            else:
                outstat = True
                print "\n"
                print_warning(red(" * ")+red("A problem occured while unlocking ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" mirror. Please have a look."))
        ftp.closeConnection()
    return outstat

def downloadLockDatabases(lock = True, mirrorList = []):

    outstat = False
    if (mirrorList == []):
        mirrorList = etpConst['activatoruploaduris']
    for uri in mirrorList:
        if (lock):
            print_info(brown(" * ")+red("Locking ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" download mirror..."),back = True)
        else:
            print_info(brown(" * ")+red("Unlocking ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" download mirror..."),back = True)
        ftp = FtpInterface(uri, Entropy)
        # upload the lock file to database/%ARCH% directory
        ftp.setCWD(etpConst['etpurirelativepath'])
        # check if the lock is already there
        if (lock):
            if (ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile'])):
                print_info(green(" * ")+red("Download mirror at ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" already locked."))
                ftp.closeConnection()
                continue
        else:
            if (not ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile'])):
                print_info(green(" * ")+red("Download mirror at ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" already unlocked."))
                ftp.closeConnection()
                continue
        if (lock):
            f = open(etpConst['packagestmpdir']+"/"+etpConst['etpdatabasedownloadlockfile'],"w")
            f.write("database locked\n")
            f.flush()
            f.close()
            rc = ftp.uploadFile(etpConst['packagestmpdir']+"/"+etpConst['etpdatabasedownloadlockfile'],ascii= True)
            if (rc == True):
                print_info(green(" * ")+red("Succesfully locked ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" download mirror."))
            else:
                outstat = True
                print "\n"
                print_warning(red(" * ")+red("A problem occured while locking ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" download mirror. Please have a look."))
        else:
            rc = ftp.deleteFile(etpConst['etpdatabasedownloadlockfile'])
            if (rc):
                print_info(green(" * ")+red("Succesfully unlocked ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" download mirror."))
            else:
                outstat = True
                print "\n"
                print_warning(red(" * ")+red("A problem occured while unlocking ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(" download mirror. Please have a look."))
        ftp.closeConnection()
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
