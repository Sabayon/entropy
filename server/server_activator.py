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
from entropyConstants import *
from outputTools import *
from entropy import FtpInterface, ServerInterface
Entropy = ServerInterface(noclientdb = 2)

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

    myopts = options[1:]
    do_pkg_check = False
    for opt in myopts:
        if (opt == "--do-packages-check"):
            do_pkg_check = True

    if not options:
        return

    if options[0] == "sync":
        Entropy.MirrorsService.sync_packages(ask = etpUi['ask'], pretend = etpUi['pretend'], packages_check = do_pkg_check)


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
