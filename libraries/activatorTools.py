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
from outputTools import *
from entropy import FtpInterface, ServerInterface, rssFeed
import exceptionTools
Entropy = ServerInterface(noclientdb = 2)

# Logging initialization

def sync(options, justTidy = False):

    activatorRequestNoAsk = False
    myopts = []
    for i in options:
        if ( i == "--noask" ):
            activatorRequestNoAsk = True
        else:
            myopts.append(i)
    options = myopts

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
            if not activatorRequestNoAsk:
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
        for uri in etpConst['activatoruploaduris']:
            print_info(green(" * ")+red("Connecting to: ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)))
            ftp = FtpInterface(uri, Entropy)
            ftp.setCWD(etpConst['binaryurirelativepath']+"/"+mybranch)
            for xfile in removeList:

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
                    print_info(green(" * ")+red("Package file: ")+bold(xfile)+red(" removed successfully from ")+bold(etpConst['packagesbindir']+"/"+mybranch))
                    os.remove(etpConst['packagesbindir']+"/"+mybranch+"/"+xfile)
                    try:
                        os.remove(etpConst['packagesbindir']+"/"+mybranch+"/"+xfile+etpConst['packagesexpirationfileext'])
                    except OSError:
                        pass
                # checksum
                if os.path.isfile(etpConst['packagesbindir']+"/"+mybranch+"/"+xfile+etpConst['packageshashfileext']):
                    print_info(green(" * ")+red("Checksum file: ")+bold(xfile+etpConst['packageshashfileext'])+red(" removed successfully from ")+bold(etpConst['packagesbindir']+"/"+mybranch))
                    os.remove(etpConst['packagesbindir']+"/"+mybranch+"/"+xfile+etpConst['packageshashfileext'])
            ftp.closeConnection()

    print_info(green(" * ")+red("Syncronization across mirrors completed."))


def packages(options):

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


                    print_info(green(" * ")+red("Upload directory:\t\t")+bold(str(uploadCounter))+red(" files ready."))
                    localPackagesRepository = set() # parse etpConst['packagesbindir']
                    print_info(green(" * ")+red("Calculating packages in ")+bold(etpConst['packagesbindir']+"/"+mybranch)+red(" ..."), back = True)
                    packageCounter = 0
                    for tbz2 in os.listdir(etpConst['packagesbindir']+"/"+mybranch):
                        if tbz2.endswith(".tbz2") or tbz2.endswith(etpConst['packageshashfileext']):
                            localPackagesRepository.add(tbz2)
                            if tbz2.endswith(".tbz2"):
                                packageCounter += 1


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


                # print warning cannot sync uri
                print_warning(brown(" * ")+red("ATTENTION: cannot properly syncronize ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri))+red(". Continuing if possible..."))

                # decide what to do
                if (totalSuccessfulUri > 0) or (etpUi['pretend']):
                    # we're safe
                    print_info(green(" * ")+red("At least one mirror has been synced properly. I'm fine."))
                    continue
                else:
                    if (currentUri < totalUris):
                        # we have another mirror to try
                        continue
                    else:
                        # no mirrors were synced properly
                        # show error and return, do not move files from the upload dir
                        print_error(brown(" * ")+red("ERROR: no mirrors have been properly syncronized. Check network status and retry. Cannot continue."))
                        return False


        # if at least one server has been synced successfully, move files
        if (totalSuccessfulUri > 0):
            if etpUi['pretend']:
                return False
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
        if activatorRequestPackagesCheck:
            Entropy.verify_local_packages([], ask = True)

        return False


def database(options):

    cmd = options[0]

    if cmd == "lock":

        print_info(green(" * ")+green("Starting to lock mirrors' databases..."))
        rc = Entropy.MirrorsService.lock_mirrors(lock = True)
        if rc:
            print_info(green(" * ")+red("A problem occured on at least one mirror !"))
        else:
            print_info(green(" * ")+green("Databases lock complete"))
        return rc

    elif cmd == "unlock":

        print_info(green(" * ")+green("Starting to unlock mirrors' databases..."))
        rc = Entropy.MirrorsService.lock_mirrors(lock = False)
        if rc:
            print_info(green(" * ")+green("A problem occured on at least one mirror !"))
        else:
            print_info(green(" * ")+green("Databases unlock complete"))
        return rc

    elif cmd == "download-lock":

        print_info(green(" * ")+green("Starting to lock download mirrors' databases..."))
        rc = Entropy.MirrorsService.lock_mirrors_for_download(lock = True)
        if rc:
            print_info(green(" * ")+green("A problem occured on at least one mirror !"))
        else:
            print_info(green(" * ")+green("Download mirrors lock complete"))
        return rc

    elif cmd == "download-unlock":

        print_info(green(" * ")+green("Starting to unlock download mirrors' databases..."))
        rc = Entropy.MirrorsService.lock_mirrors_for_download(lock = False)
        if rc:
            print_info(green(" * ")+green("A problem occured on at least one mirror..."))
        else:
            print_info(green(" * ")+green("Download mirrors unlock complete"))
        return rc

    elif cmd == "lock-status":

        print_info(brown(" * ")+green("Mirrors status table:"))
        dbstatus = Entropy.MirrorsService.get_mirrors_lock()
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
        return 0

    elif cmd == "sync":

        print_info(green(" * ")+red("Syncing databases ..."))
        errors, fine, broken = sync_remote_databases()
        if errors:
            print_error(darkred(" !!! ")+green("Database sync errors, cannot continue."))
            return 1
        return 0


def sync_remote_databases(noUpload = False, justStats = False):

    remoteDbsStatus = Entropy.MirrorsService.get_remote_databases_status()
    print_info(green(" * ")+red("Remote Entropy Database Repository Status:"))
    for dbstat in remoteDbsStatus:
        print_info(green("\t Host:\t")+bold(Entropy.entropyTools.extractFTPHostFromUri(dbstat[0])))
        print_info(red("\t  * Database revision: ")+blue(str(dbstat[1])))

    local_revision = Entropy.get_local_database_revision()
    print_info(red("\t  * Database local revision currently at: ")+blue(str(local_revision)))

    if justStats:
        return 0,set(),set()

    # do the rest
    errors, fine_uris, broken_uris = Entropy.MirrorsService.sync_databases(no_upload = noUpload)
    remote_status = Entropy.MirrorsService.get_remote_databases_status()
    print_info(darkgreen(" * ")+red("Remote Entropy Database Repository Status:"))
    for dbstat in remote_status:
        print_info(darkgreen("\t Host:\t")+bold(Entropy.entropyTools.extractFTPHostFromUri(dbstat[0])))
        print_info(red("\t  * Database revision: ")+blue(str(dbstat[1])))

    return errors, fine_uris, broken_uris
