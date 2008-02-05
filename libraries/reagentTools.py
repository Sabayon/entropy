#!/usr/bin/python
'''
    # DESCRIPTION:
    # generic tools for reagent application

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
import shutil
import time
from entropyConstants import *
from serverConstants import *
from outputTools import *
import exceptionTools
from entropy import EquoInterface
Entropy = EquoInterface(noclientdb = 2)

# Logging initialization
import logTools
reagentLog = logTools.LogFile(level=etpConst['reagentloglevel'],filename = etpConst['reagentlogfile'], header = "[Reagent]")

def generator(package, dbconnection = None, enzymeRequestBranch = etpConst['branch'], inject = False):

    # check if the provided package is valid
    if not os.path.isfile(package) or not package.endswith(".tbz2"):
        return False, -1
    packagename = os.path.basename(package)

    print_info(brown(" * ")+red("Processing: ")+bold(packagename)+red(", please wait..."))
    mydata = Entropy.entropyTools.extractPkgData(package, enzymeRequestBranch, inject = inject)

    if dbconnection is None:
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = False, noUpload = True)
    else:
        dbconn = dbconnection

    idpk, revision, etpDataUpdated, accepted = dbconn.handlePackage(mydata)

    # add package info to our official repository etpConst['officialrepositoryid']
    if (accepted):
        dbconn.removePackageFromInstalledTable(idpk)
        dbconn.addPackageToInstalledTable(idpk,etpConst['officialrepositoryid'])

    if dbconnection is None:
        dbconn.commitChanges()
        dbconn.closeDB()

    if (accepted) and (revision != 0):
        print_info(green(" * ")+red("Package ")+bold(os.path.basename(etpDataUpdated['download']))+red(" entry has been updated. Revision: ")+bold(str(revision)))
        return True, idpk
    elif (accepted) and (revision == 0):
        print_info(green(" * ")+red("Package ")+bold(os.path.basename(etpDataUpdated['download']))+red(" entry newly created."))
        return True, idpk
    else:
        print_error(red(" * Package ")+bold(packagename)+red(": something bad happened !!!"))
        return False, idpk

def inject(options):

    requestedBranch = etpConst['branch']
    mytbz2s = []
    for opt in options:
        if opt.startswith("--branch=") and len(opt.split("=")) == 2:
            requestedBranch = opt.split("=")[1]
        else:
            if not os.path.isfile(opt) or not opt.endswith(".tbz2"):
                print_error(darkred(" * ")+bold(opt)+red(" is invalid."))
                return 1
            mytbz2s.append(opt)

    if not mytbz2s:
        print_error(red("no .tbz2 specified."))
        return 2

    if not os.path.isdir(etpConst['packagessuploaddir']+"/"+requestedBranch):
        os.makedirs(etpConst['packagessuploaddir']+"/"+requestedBranch)

    dbconn = Entropy.databaseTools.openServerDatabase(readOnly = False, noUpload = True)
    for tbz2 in mytbz2s:
        print_info(red("Working on: ")+blue(tbz2))
        tbz2Handler(tbz2, dbconn, requestedBranch, inject = True)

    dbconn.commitChanges()
    dependsTableInitialize(dbconn, False)
    dbconn.closeDB()



def update(options):

    reagentLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"update: called -> options: "+str(options))

    # differential checking
    # collect differences between the packages in the database and the ones on the system

    reagentRequestSeekStore = False
    reagentRequestRepackage = False
    reagentRequestAsk = True
    repackageItems = []
    _options = []
    for opt in options:
        if opt.startswith("--seekstore"):
            reagentRequestSeekStore = True
        elif opt.startswith("--repackage"):
            reagentRequestRepackage = True
        elif opt.startswith("--noask"):
            reagentRequestAsk = False
        else:
            if (reagentRequestRepackage) and (not opt.startswith("--")):
                if not opt in repackageItems:
                    repackageItems.append(opt)
                continue
            _options.append(opt)
    options = _options

    if (not reagentRequestSeekStore):

        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)

        if (not reagentRequestRepackage):
            print_info(brown(" * ")+red("Scanning database for differences..."))
            from portageTools import getInstalledPackagesCounters, quickpkg, getPackageSlot
            installedPackages = getInstalledPackagesCounters()
            installedCounters = set()
            toBeAdded = set()
            toBeRemoved = set()

            # packages to be added
            for x in installedPackages[0]:
                installedCounters.add(x[1])
                counter = dbconn.isCounterAvailable(x[1])
                if (not counter):
                    toBeAdded.add(tuple(x))

            # packages to be removed from the database
            databaseCounters = dbconn.listAllCounters()
            for x in databaseCounters:
                if x[0] < 0:
                    continue # skip packages without valid counter
                if x[0] not in installedCounters:
                    # check if the package is in toBeAdded
                    if (toBeAdded):
                        #print x
                        atom = dbconn.retrieveAtom(x[1])
                        atomkey = Entropy.entropyTools.dep_getkey(atom)
                        atomtag = Entropy.entropyTools.dep_gettag(atom)
                        atomslot = dbconn.retrieveSlot(x[1])

                        add = True
                        for pkgdata in toBeAdded:
                            addslot = getPackageSlot(pkgdata[0])
                            addkey = Entropy.entropyTools.dep_getkey(pkgdata[0])
                            # workaround for ebuilds not having slot
                            if addslot == None:
                                addslot = '0'                                              # handle tagged packages correctly
                            if (atomkey == addkey) and ((str(atomslot) == str(addslot)) or (atomtag != None)):
                                # do not add to toBeRemoved
                                add = False
                                break
                        if add:
                            toBeRemoved.add(x[1])
                    else:
                        toBeRemoved.add(x[1])

            if (not toBeRemoved) and (not toBeAdded):
                print_info(brown(" * ")+red("Nothing to do, check later."))
                # then exit gracefully
                return 0

            if (toBeRemoved):
                print_info(brown(" @@ ")+blue("These are the packages that would be removed from the database:"))
                for x in toBeRemoved:
                    atom = dbconn.retrieveAtom(x)
                    print_info(brown("    # ")+red(atom))
                if reagentRequestAsk:
                    rc = Entropy.askQuestion(">>   Would you like to remove them now ?")
                else:
                    rc = "Yes"
                if rc == "Yes":
                    rwdbconn = Entropy.databaseTools.openServerDatabase(readOnly = False, noUpload = True)
                    for x in toBeRemoved:
                        atom = rwdbconn.retrieveAtom(x)
                        print_info(brown(" @@ ")+blue("Removing from database: ")+red(atom), back = True)
                        rwdbconn.removePackage(x)
                    rwdbconn.closeDB()
                    print_info(brown(" @@ ")+blue("Database removal complete."))

            if (toBeAdded):
                print_info(brown(" @@ ")+blue("These are the packages that would be added/updated to the add list:"))
                for x in toBeAdded:
                    print_info(brown("    # ")+red(x[0]))
                if reagentRequestAsk:
                    rc = Entropy.askQuestion(">>   Would you like to package them now ?")
                    if rc == "No":
                        return 0

        else:
            if not repackageItems:
                print_info(brown(" * ")+red("Nothing to do, check later."))
                # then exit gracefully
                return 0

            from portageTools import getPortageAppDbPath,quickpkg
            appdb = getPortageAppDbPath()

            packages = []
            for item in repackageItems:
                match = dbconn.atomMatch(item)
                if match[0] == -1:
                    print_warning(darkred("  !!! ")+red("Cannot match ")+bold(item))
                else:
                    cat = dbconn.retrieveCategory(match[0])
                    name = dbconn.retrieveName(match[0])
                    version = dbconn.retrieveVersion(match[0])
                    #slot = dbconn.retrieveSlot(match[0])
                    if os.path.isdir(appdb+"/"+cat+"/"+name+"-"+version):
                        packages.append([cat+"/"+name+"-"+version,0])

            if not packages:
                print_info(brown(" * ")+red("Nothing to do, check later."))
                # then exit gracefully
                return 0

            toBeAdded = packages

        # package them
        print_info(brown(" @@ ")+blue("Compressing packages..."))
        for x in toBeAdded:
            print_info(brown("    # ")+red(x[0]+"..."))
            rc = quickpkg(x[0],etpConst['packagesstoredir'])
            if (rc is None):
                reagentLog.log(ETP_LOGPRI_ERROR,ETP_LOGLEVEL_NORMAL,"update: "+str(x)+" -> quickpkg error. Cannot continue.")
                print_error(red("      *")+" quickpkg error for "+red(x))
                print_error(red("  ***")+" Fatal error, cannot continue")
                return 251

        dbconn.closeDB()

    enzymeRequestBranch = etpConst['branch']
    for i in options:
        if ( i.startswith("--branch=") and len(i.split("=")) == 2 ):
            mybranch = i.split("=")[1]
            if (mybranch):
                enzymeRequestBranch = mybranch

    if not os.path.isdir(etpConst['packagessuploaddir']+"/"+enzymeRequestBranch):
        os.makedirs(etpConst['packagessuploaddir']+"/"+enzymeRequestBranch)

    tbz2files = os.listdir(etpConst['packagesstoredir'])
    totalCounter = 0
    # counting the number of files
    for i in tbz2files:
        totalCounter += 1

    if (totalCounter == 0):
        print_info(brown(" * ")+red("Nothing to do, check later."))
        # then exit gracefully
        return 0

    # open db connection
    dbconn = Entropy.databaseTools.openServerDatabase(readOnly = False, noUpload = True)

    counter = 0
    etpCreated = 0
    for tbz2 in tbz2files:
        counter += 1
        etpCreated += 1
        tbz2name = tbz2.split("/")[-1]
        print_info(" ("+str(counter)+"/"+str(totalCounter)+") Processing "+tbz2name)
        tbz2path = etpConst['packagesstoredir']+"/"+tbz2
        tbz2Handler(tbz2path, dbconn, enzymeRequestBranch)
        dbconn.commitChanges()

    dbconn.commitChanges()
    # regen dependstable
    dependsTableInitialize(dbconn, False)
    dbconn.commitChanges()

    # checking dependencies and print issues
    dependenciesTest()

    dbconn.closeDB()

    print_info(green(" * ")+red("Statistics: ")+blue("Entries created/updated: ")+bold(str(etpCreated)))
    return 0


def tbz2Handler(tbz2path, dbconn, requested_branch, inject = False):
    rc, idpk = generator(tbz2path, dbconn, requested_branch, inject)
    if (rc): # still needed ?
        # add revision to package file
        downloadurl = dbconn.retrieveDownloadURL(idpk)
        packagerev = dbconn.retrieveRevision(idpk)
        downloaddir = os.path.dirname(downloadurl)
        downloadfile = os.path.basename(downloadurl)
        # remove tbz2 and add revision
        downloadfile = downloadfile[:-5]+"~"+str(packagerev)+".tbz2"
        downloadurl = downloaddir+"/"+downloadfile
        # update url
        dbconn.setDownloadURL(idpk,downloadurl)

        shutil.move(tbz2path,etpConst['packagessuploaddir']+"/"+requested_branch+"/"+downloadfile)
        print_info(brown(" * ")+red("Injecting database information into ")+bold(downloadfile)+red(", please wait..."), back = True)

        dbpath = etpConst['packagestmpdir']+"/"+str(Entropy.entropyTools.getRandomNumber())
        while os.path.isfile(dbpath):
            dbpath = etpConst['packagestmpdir']+"/"+str(Entropy.entropyTools.getRandomNumber())
        # create db
        pkgDbconn = Entropy.databaseTools.openGenericDatabase(dbpath)
        pkgDbconn.initializeDatabase()
        data = dbconn.getPackageData(idpk)
        rev = dbconn.retrieveRevision(idpk)
        # inject
        pkgDbconn.addPackage(data, revision = rev)
        pkgDbconn.closeDB()
        # append the database to the new file
        Entropy.entropyTools.aggregateEdb(tbz2file = etpConst['packagessuploaddir']+"/"+requested_branch+"/"+downloadfile, dbfile = dbpath)

        digest = Entropy.entropyTools.md5sum(etpConst['packagessuploaddir']+"/"+requested_branch+"/"+downloadfile)
        dbconn.setDigest(idpk,digest)
        Entropy.entropyTools.createHashFile(etpConst['packagessuploaddir']+"/"+requested_branch+"/"+downloadfile)
        # remove garbage
        os.remove(dbpath)
        print_info(brown(" * ")+red("Database injection complete for ")+downloadfile)
    else:
        raise exceptionTools.CorruptionError("CorruptionError: something bad happened, tbz2 not generated.")

def dependsTableInitialize(dbconn = None, runActivator = True):
    closedb = False
    if dbconn == None:
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = False, noUpload = True)
        closedb = True
    dbconn.regenerateDependsTable()
    # now taint
    dbconn.taintDatabase()
    if (closedb):
        dbconn.closeDB()
    # running activator
    if (runActivator):
        import activatorTools
        activatorTools.database(['sync'])
    return 0

def dependenciesTest():

    dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)

    print_info(red(" @@ ")+blue("Running dependency test..."))
    depsNotMatched = Entropy.dependencies_test(dbconn = dbconn)

    if depsNotMatched:

        crying_atoms = {}
        for atom in depsNotMatched:
            riddep = dbconn.searchDependency(atom)
            if riddep != -1:
                ridpackages = dbconn.searchIdpackageFromIddependency(riddep)
                for i in ridpackages:
                    iatom = dbconn.retrieveAtom(i)
                    if not crying_atoms.has_key(atom):
                        crying_atoms[atom] = set()
                    crying_atoms[atom].add(iatom)

        print_info(red(" @@ ")+blue("These are the dependencies not found:"))
        for atom in depsNotMatched:
            print_info("   # "+red(atom))
            if crying_atoms.has_key(atom):
                print_info(blue("      # ")+red("Needed by:"))
                for x in crying_atoms[atom]:
                    print_info(blue("      # ")+darkgreen(x))

    else:
        print

    return 0

def database(options):

    import activatorTools
    from entropy import FtpInterface

    databaseRequestNoAsk = False
    databaseRequestJustScan = False
    databaseRequestNoChecksum = False
    _options = []
    for opt in options:
        if opt.startswith("--noask"):
            databaseRequestNoAsk = True
        elif opt.startswith("--justscan"):
            databaseRequestJustScan = True
        elif opt.startswith("--nochecksum"):
            databaseRequestNoChecksum = True
        else:
            _options.append(opt)
    options = _options

    if len(options) == 0:
        print_error(brown(" * ")+red("Not enough parameters"))
        return 1

    if (options[0] == "--initialize"):

        # do some check, print some warnings
        print_info(green(" * ")+red("Initializing Entropy database..."), back = True)
        # database file: etpConst['etpdatabasefilepath']
        revisionsMatch = {}
        treeUpdatesActions = []
        injectedPackages = set()
        if os.path.isfile(etpConst['etpdatabasefilepath']):
            dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)
            idpackages = []
            try:
                idpackages = dbconn.listAllIdpackages()
            except:
                pass
            # save treeUpdatesActions
            try:
                treeUpdatesActions = dbconn.listAllTreeUpdatesActions()
            except:
                pass
            # save list of injected packages
            try:
                injectedPackages = dbconn.listAllInjectedPackages(justFiles = True)
            except:
                pass
            for idpackage in idpackages:
                try:
                    package = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
                    branch = dbconn.retrieveBranch(idpackage)
                    revision = dbconn.retrieveRevision(idpackage)
                    if revision < 0: # just to be sure
                        revision = 0
                    revisionsMatch[package] = [branch,revision]
                except:
                    pass
            dbconn.closeDB()
            print_info(red(" * ")+bold("WARNING")+red(": database file already exists. Overwriting."))
            rc = Entropy.askQuestion("\n     Do you want to continue ?")
            if rc == "No":
                return 0
            os.remove(etpConst['etpdatabasefilepath'])

        # initialize the database
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = False, noUpload = True)
        dbconn.initializeDatabase()

        # dump revisions - as a backup
        if revisionsMatch:
            print_info(green(" * ")+red("Dumping current revisions to file ")+"/entropy-revisions-dump.txt")
            f = open("/entropy-revisions-dump.txt","w")
            f.write(str(revisionsMatch)+"\n")
            f.flush()
            f.close()

        # dump treeupdates - as a backup
        if treeUpdatesActions:
            print_info(green(" * ")+red("Dumping current tree updates actions to file ")+"/entropy-treeupdates-dump.txt")
            f = open("/entropy-treeupdates-dump.txt","w")
            f.write(str(treeUpdatesActions)+"\n")
            f.flush()
            f.close()

        rc = Entropy.askQuestion("     Would you like to sync packages first (important if you don't have them synced) ?")
        if rc == "Yes":
            activatorTools.packages(["sync","--ask"])

        # fill tree updates actions
        if treeUpdatesActions:
            dbconn.addTreeUpdatesActions(treeUpdatesActions)

        # now fill the database
        pkgbranches = os.listdir(etpConst['packagesbindir'])
        pkgbranches = [x for x in pkgbranches if os.path.isdir(etpConst['packagesbindir']+"/"+x)]
        #print revisionsMatch
        for mybranch in pkgbranches:

            pkglist = os.listdir(etpConst['packagesbindir']+"/"+mybranch)
            # filter .md5 and .expired packages
            pkglist = [x for x in pkglist if x[-5:] == ".tbz2" and not os.path.isfile(etpConst['packagesbindir']+"/"+mybranch+"/"+x+etpConst['packagesexpirationfileext'])]

            if (not pkglist):
                continue

            print_info(green(" * ")+red("Reinitializing Entropy database for branch ")+bold(mybranch)+red(" using Packages in the repository ..."))
            currCounter = 0
            atomsnumber = len(pkglist)

            for pkg in pkglist:

                print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+red("Analyzing: ")+bold(pkg), back = True)
                currCounter += 1
                print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+green("(")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(pkg)+red(" ..."), back = True)

                doinject = False
                if os.path.join(etpConst['binaryurirelativepath'],mybranch+"/"+pkg) in injectedPackages:
                    doinject = True

                mydata = Entropy.entropyTools.extractPkgData(etpConst['packagesbindir']+"/"+mybranch+"/"+pkg, mybranch, inject = doinject)

                # get previous revision
                revisionAvail = revisionsMatch.get(os.path.basename(mydata['download']))
                addRevision = 0
                if (revisionAvail != None):
                    if mybranch == revisionAvail[0]:
                        addRevision = revisionAvail[1]
                # fill the db entry
                idpk, revision, etpDataUpdated, accepted = dbconn.addPackage(mydata, revision = addRevision)

                print_info(darkgreen(" [")+red(mybranch)+darkgreen("] ")+green("(")+ blue(str(currCounter))+"/"+red(str(atomsnumber))+green(") ")+red("Analyzing ")+bold(pkg)+red(". Revision: ")+blue(str(addRevision)))

            dbconn.commitChanges()

        # regen dependstable
        dependsTableInitialize(dbconn, False)

        dbconn.closeDB()
        print_info(green(" * ")+red("Entropy database has been reinitialized using binary packages available"))
        return 0

    # used by reagent
    elif (options[0] == "search"):

        from text_query import printPackageInfo

        mykeywords = options[1:]
        if (len(mykeywords) == 0):
            print_error(brown(" * ")+red("Not enough parameters"))
            return 2
        if (not os.path.isfile(etpConst['etpdatabasefilepath'])):
            print_error(brown(" * ")+red("Entropy Datbase does not exist"))
            return 3

        # search tool
        print_info(green(" * ")+red("Searching ..."))
        # open read only
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)

        foundCounter = 0
        for mykeyword in mykeywords:
            results = dbconn.searchPackages(mykeyword)

            for result in results:
                foundCounter += 1
                printPackageInfo(result[1],dbconn, clientSearch = True, extended = True, EquoConnection = Entropy)

        dbconn.closeDB()
        if (foundCounter == 0):
            print_warning(red(" * ")+red("Nothing found."))
        return 0

    elif (options[0] == "create-empty-database"):

        mypath = options[1:]
        if len(mypath) == 0:
            print_error(brown(" * ")+red("Not enough parameters"))
            return 4
        if (os.path.dirname(mypath[0]) != '') and (not os.path.isdir(os.path.dirname(mypath[0]))):
            print_error(green(" * ")+red("Supplied directory does not exist."))
            return 5
        print_info(green(" * ")+red("Initializing an empty database file with Entropy structure ..."),back = True)
        connection = Entropy.databaseTools.dbapi2.connect(mypath[0])
        cursor = connection.cursor()
        for sql in etpSQLInitDestroyAll.split(";"):
            if sql:
                cursor.execute(sql+";")
        del sql
        for sql in etpSQLInit.split(";"):
            if sql:
                cursor.execute(sql+";")
        connection.commit()
        cursor.close()
        connection.close()
        print_info(green(" * ")+red("Entropy database file ")+bold(mypath[0])+red(" successfully initialized."))
        return 0

    elif (options[0] == "switchbranch"):

        if (len(options) < 2):
            print_error(brown(" * ")+red("Not enough parameters"))
            return 6

        switchbranch = options[1]
        print_info(green(" * ")+red("Collecting packages that would be marked '"+switchbranch+"' ..."), back = True)

        myatoms = options[2:]
        if not myatoms:
            print_error(brown(" * ")+red("Not enough parameters"))
            return 7

        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = False, noUpload = True)
        # is world?
        if myatoms[0] == "world":
            pkglist = dbconn.listAllIdpackages()
        else:
            pkglist = set()
            for atom in myatoms:
                # validate atom
                match = dbconn.atomMatch(atom)
                if match == -1:
                    print_warning(brown(" * ")+red("Cannot match: ")+bold(atom))
                else:
                    pkglist.add(match[0])

        # check if atoms were found
        if not pkglist:
            print
            print_error(brown(" * ")+red("No packages found."))
            return 8

        # show what would be done
        print_info(green(" * ")+red("These are the packages that would be marked '"+switchbranch+"':"))

        for pkg in pkglist:
            atom = dbconn.retrieveAtom(pkg)
            print_info(red("  (*) ")+bold(atom))

        rc = Entropy.askQuestion("     Would you like to continue ?")
        if rc == "No":
            return 9

        # sync packages
        import activatorTools
        ask = etpUi['ask']
        etpUi['ask'] = True
        activatorTools.packages(["sync"])
        etpUi['ask'] = ask

        print_info(green(" * ")+red("Switching selected packages ..."))

        for pkg in pkglist:
            atom = dbconn.retrieveAtom(pkg)
            currentbranch = dbconn.retrieveBranch(pkg)
            currentdownload = dbconn.retrieveDownloadURL(pkg)

            if currentbranch == switchbranch:
                print_warning(green(" * ")+red("Ignoring ")+bold(atom)+red(" since it is already in the chosen branch"))
                continue

            print_info(green(" * ")+darkred(atom+": ")+red("Configuring package information..."), back = True)
            # change branch and download URL
            dbconn.switchBranch(pkg,switchbranch)

            # rename locally
            filename = os.path.basename(dbconn.retrieveDownloadURL(pkg))
            topath = etpConst['packagesbindir']+"/"+switchbranch
            if not os.path.isdir(topath):
                os.makedirs(topath)
            print_info(green(" * ")+darkred(atom+": ")+red("Moving file locally..."), back = True)
            #print etpConst['entropyworkdir']+"/"+currentdownload+" --> "+topath+"/"+newdownload
            os.rename(etpConst['entropyworkdir']+"/"+currentdownload,topath+"/"+filename)
            # md5
            os.rename(etpConst['entropyworkdir']+"/"+currentdownload+etpConst['packageshashfileext'],topath+"/"+filename+etpConst['packageshashfileext'])

            # XXX: we can barely ignore branch info injected into .tbz2 since they'll be ignored too

            # rename remotely
            print_info(green(" * ")+darkred(atom+": ")+red("Moving file remotely..."), back = True)
            # change filename remotely
            for uri in etpConst['activatoruploaduris']:

                print_info(green(" * ")+darkred(atom+": ")+red("Moving file remotely on: ")+Entropy.entropyTools.extractFTPHostFromUri(uri), back = True)

                ftp = FtpInterface(uri, Entropy)
                ftp.setCWD(etpConst['binaryurirelativepath'])
                # create directory if it doesn't exist
                if (not ftp.isFileAvailable(switchbranch)):
                    ftp.mkdir(switchbranch)
                # rename tbz2
                ftp.renameFile(currentbranch+"/"+filename,switchbranch+"/"+filename)
                # rename md5
                ftp.renameFile(currentbranch+"/"+filename+etpConst['packageshashfileext'],switchbranch+"/"+filename+etpConst['packageshashfileext'])
                ftp.closeConnection()

        dbconn.closeDB()
        print_info(green(" * ")+red("All the selected packages have been marked as requested. Remember to run activator."))
        return 0


    elif (options[0] == "remove"):

        print_info(green(" * ")+red("Scanning packages that would be removed ..."), back = True)

        myopts = options[1:]
        _myopts = []
        branch = None
        for opt in myopts:
            if (opt.startswith("--branch=")) and (len(opt.split("=")) == 2):
                branch = opt.split("=")[1]
            else:
                _myopts.append(opt)
        myopts = _myopts

        if len(myopts) == 0:
            print_error(brown(" * ")+red("Not enough parameters"))
            return 10

        pkglist = set()
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = False, noUpload = True)

        for atom in myopts:
            if (branch):
                pkg = dbconn.atomMatch(atom, matchBranches = (branch,))
            else:
                pkg = dbconn.atomMatch(atom)
            if pkg[0] != -1:
                pkglist.add(pkg[0])

        # check if atoms were found
        if not pkglist:
            print
            dbconn.closeDB()
            print_error(brown(" * ")+red("No packages found."))
            return 11

        print_info(green(" * ")+red("These are the packages that would be removed from the database:"))

        for pkg in pkglist:
            pkgatom = dbconn.retrieveAtom(pkg)
            branch = dbconn.retrieveBranch(pkg)
            print_info(red("\t (*) ")+bold(pkgatom)+blue(" [")+red(branch)+blue("]"))

        # ask to continue
        rc = Entropy.askQuestion("     Would you like to continue ?")
        if rc == "No":
            return 0

        # now mark them as stable
        print_info(green(" * ")+red("Removing selected packages ..."))

        # open db
        for pkg in pkglist:
            pkgatom = dbconn.retrieveAtom(pkg)
            print_info(green(" * ")+red("Removing package: ")+bold(pkgatom)+red(" ..."), back = True)
            dbconn.removePackage(pkg)
        print_info(green(" * ")+red("All the selected packages have been removed as requested. To remove online binary packages, just run Activator."))
        dbconn.closeDB()
        return 0

    elif (options[0] == "multiremove"):

        print_info(green(" * ")+red("Scanning packages that would be removed ..."), back = True)

        branch = etpConst['branch']
        atoms = []
        for opt in options[1:]:
            if (opt.startswith("--branch=")) and (len(opt.split("=")) == 2):
                branch = opt.split("=")[1]
            else:
                atoms.append(opt)

        pkglist = set()
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)
        allidpackages = dbconn.listAllIdpackages()

        idpackages = set()
        if not atoms:
            # choose all
            for idpackage in allidpackages:
                if dbconn.isInjected(idpackage):
                    idpackages.add(idpackage)
        else:
            for atom in atoms:
                match = dbconn.atomMatch(atom, matchBranches = (branch,), multiMatch = True, packagesFilter = False)
                if match[1] != 0:
                    print_warning(red("Attention, no match for: ")+bold(atom))
                else:
                    for x in match[0]:
                        if dbconn.isInjected(x):
                            idpackages.add(x)

        # check if atoms were found
        if not idpackages:
            dbconn.closeDB()
            print_error(brown(" * ")+red("No packages found."))
            return 11

        print_info(green(" * ")+blue("These are the packages that would be removed from the database:"))

        for idpackage in idpackages:
            pkgatom = dbconn.retrieveAtom(idpackage)
            branch = dbconn.retrieveBranch(idpackage)
            print_info(darkred("    (*) ")+blue("[")+red(branch)+blue("] ")+brown(pkgatom))

        # ask to continue
        rc = Entropy.askQuestion("     Would you like to continue ?")
        if rc == "No":
            return 0

        dbconn.closeDB()
        del dbconn
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = False, noUpload = True)

        print_info(green(" * ")+red("Removing selected packages ..."))

        # open db
        for idpackage in idpackages:
            pkgatom = dbconn.retrieveAtom(idpackage)
            print_info(green(" * ")+red("Removing package: ")+bold(pkgatom)+red(" ..."))
            dbconn.removePackage(idpackage)
        print_info(green(" * ")+red("All the selected packages have been removed as requested."))
        dbconn.closeDB()
        del dbconn
        return 0

    # used by reagent
    elif (options[0] == "md5check"):

        print_info(green(" * ")+red("Integrity verification of the selected packages:"))

        mypackages = options[1:]
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)

        # statistic vars
        pkgMatch = 0
        pkgNotMatch = 0
        pkgDownloadedSuccessfully = 0
        pkgDownloadedError = 0
        worldSelected = False

        if (len(mypackages) == 0):
            # check world
            # create packages list
            worldSelected = True
            pkgs2check = dbconn.listAllPackages()
        elif (mypackages[0] == "world"):
            # check world
            # create packages list
            worldSelected = True
            pkgs2check = dbconn.listAllPackages()
        else:
            # catch the names
            pkgs2check = []
            for pkg in mypackages:
                result = dbconn.atomMatch(pkg, multiMatch = True, matchBranches = etpConst['branches'])
                if result[1] == 0:
                    for idresult in result[0]:
                        iatom = dbconn.retrieveAtom(idresult)
                        ibranch = dbconn.retrieveBranch(idresult)
                        pkgs2check.append((iatom,idresult,ibranch))
                else:
                    print_warning(red("ATTENTION: ")+blue("cannot match: ")+bold(pkg))

        if (not worldSelected):
            print_info(red("   This is the list of the packages that would be checked:"))
        else:
            print_info(red("   All the packages in the Entropy Packages repository will be checked."))

        toBeDownloaded = []
        availList = []
        for pkginfo in pkgs2check:

            pkgatom = pkginfo[0]
            idpackage = pkginfo[1]
            pkgbranch = pkginfo[2]
            pkgfile = dbconn.retrieveDownloadURL(idpackage)
            pkgfile = os.path.basename(pkgfile)
            if (os.path.isfile(etpConst['packagesbindir']+"/"+pkgbranch+"/"+pkgfile)):
                if (not worldSelected): print_info(green("   - [PKG AVAILABLE] ")+red(pkgatom)+" -> "+bold(pkgfile))
                availList.append(idpackage)
            elif (os.path.isfile(etpConst['packagessuploaddir']+"/"+pkgbranch+"/"+pkgfile)):
                if (not worldSelected): print_info(green("   - [RUN ACTIVATOR] ")+darkred(pkgatom)+" -> "+bold(pkgfile))
            else:
                if (not worldSelected): print_info(green("   - [MUST DOWNLOAD] ")+brown(pkgatom)+" -> "+bold(pkgfile))
                toBeDownloaded.append([idpackage,pkgfile,pkgbranch])

        if (not databaseRequestNoAsk):
            rc = Entropy.askQuestion("     Would you like to continue ?")
            if rc == "No":
                return 0

        notDownloadedPackages = []
        if (toBeDownloaded != []):
            print_info(red("   Starting to download missing files..."))
            for uri in etpConst['activatoruploaduris']:

                if (notDownloadedPackages != []):
                    print_info(red("   Trying to search missing or broken files on another mirror ..."))
                    toBeDownloaded = notDownloadedPackages
                    notDownloadedPackages = []

                for pkg in toBeDownloaded:
                    rc = activatorTools.downloadPackageFromMirror(uri,pkg[1],pkg[2])
                    if (rc == None):
                        notDownloadedPackages.append([pkg[1],pkg[2]])
                    elif (not rc):
                        notDownloadedPackages.append([pkg[1],pkg[2]])
                    elif (rc):
                        pkgDownloadedSuccessfully += 1
                        availList.append(pkg[0])

                if (notDownloadedPackages == []):
                    print_info(red("   All the binary packages have been downloaded successfully."))
                    break

            if (notDownloadedPackages != []):
                print_warning(red("   These are the packages that cannot be found online:"))
                for i in notDownloadedPackages:
                    pkgDownloadedError += 1
                    print_warning(red("    * ")+brown(i[0])+" in "+blue(i[1]))
                print_warning(red("   They won't be checked."))

        brokenPkgsList = []
        totalcounter = str(len(availList))
        currentcounter = 0
        for pkg in availList:
            currentcounter += 1
            pkgfile = dbconn.retrieveDownloadURL(pkg)
            pkgbranch = dbconn.retrieveBranch(pkg)
            pkgfile = os.path.basename(pkgfile)
            print_info("  ("+red(str(currentcounter))+"/"+blue(totalcounter)+") "+red("Checking hash of ")+brown(pkgfile)+red(" in branch: ")+blue(pkgbranch)+red(" ..."), back = True)
            storedmd5 = dbconn.retrieveDigest(pkg)
            result = Entropy.entropyTools.compareMd5(etpConst['packagesbindir']+"/"+pkgbranch+"/"+pkgfile,storedmd5)
            if (result):
                # match !
                pkgMatch += 1
                #print_info(red("   Package ")+brown(pkg)+green(" is healthy. Checksum: ")+brown(storedmd5), back = True)
            else:
                pkgNotMatch += 1
                print_error(red("   Package ")+brown(pkgfile)+red(" in branch: ")+blue(pkgbranch)+red(" is _NOT_ healthy !!!! Stored checksum: ")+brown(storedmd5))
                brokenPkgsList.append([pkgfile,pkgbranch])

        dbconn.closeDB()

        if (brokenPkgsList != []):
            print_info(blue(" *  This is the list of the BROKEN packages: "))
            for bp in brokenPkgsList:
                print_info(red("    * Package file: ")+bold(bp[0])+red(" in branch: ")+blue(bp[1]))

        # print stats
        print_info(blue(" *  Statistics: "))
        print_info(brown("     Number of checked packages:\t\t")+str(pkgMatch+pkgNotMatch))
        print_info(green("     Number of healthy packages:\t\t")+str(pkgMatch))
        print_info(red("     Number of broken packages:\t\t")+str(pkgNotMatch))
        if (pkgDownloadedSuccessfully > 0) or (pkgDownloadedError > 0):
            print_info(green("     Number of downloaded packages:\t\t")+str(pkgDownloadedSuccessfully+pkgDownloadedError))
            print_info(green("     Number of happy downloads:\t\t")+str(pkgDownloadedSuccessfully))
        return 0


    # used by reagent
    elif (options[0] == "md5remote"):

        print_info(green(" * ")+red("Integrity verification of the selected packages:"))

        mypackages = options[1:]
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)
        worldSelected = False

        if (len(mypackages) == 0):
            # check world
            # create packages list
            worldSelected = True
            pkgs2check = dbconn.listAllIdpackages()
        elif (mypackages[0] == "world"):
            # check world
            # create packages list
            worldSelected = True
            pkgs2check = dbconn.listAllIdpackages()
        else:
            # catch the names
            pkgs2check = []
            for pkg in mypackages:
                result = dbconn.atomMatch(pkg, multiMatch = True, matchBranches = etpConst['branches'])
                if result[1] == 0:
                    for idresult in result[0]:
                        pkgs2check.append(idresult)
                else:
                    print_warning(red("ATTENTION: ")+blue("cannot match: ")+bold(pkg))

        if (not worldSelected):
            print_info(red("   This is the list of the packages that would be checked:"))
        else:
            print_info(red("   All the packages in the Entropy Packages repository will be checked."))


        if (not worldSelected):
            for idpackage in pkgs2check:
                pkgatom = dbconn.retrieveAtom(idpackage)
                pkgbranch = dbconn.retrieveBranch(idpackage)
                pkgfile = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
                print_info(green("   - ")+red(pkgatom)+" -> "+bold(str(pkgbranch)+"/"+pkgfile))

        if (not databaseRequestNoAsk):
            rc = Entropy.askQuestion("     Would you like to continue ?")
            if rc == "No":
                return 0

        for uri in etpConst['activatoruploaduris']:

            # statistic vars
            pkgMatch = 0
            pkgNotMatch = 0
            currentcounter = 0
            print_info(green(" * ")+brown("Working on ")+bold(Entropy.entropyTools.extractFTPHostFromUri(uri)+red(" mirror.")))
            brokenPkgsList = []
            totalcounter = str(len(pkgs2check))


            for idpackage in pkgs2check:

                currentcounter += 1
                pkgfile = dbconn.retrieveDownloadURL(idpackage)
                pkgbranch = dbconn.retrieveBranch(idpackage)
                pkgfilename = os.path.basename(pkgfile)

                print_info("  ("+red(str(currentcounter))+"/"+blue(totalcounter)+") "+red("Checking hash of ")+blue(pkgbranch+"/"+pkgfilename), back = True)
                ckOk = False
                ck = Entropy.get_remote_package_checksum(Entropy.entropyTools.extractFTPHostFromUri(uri),pkgfilename, pkgbranch)
                if ck == None:
                    print_warning("    "+red("   -> Digest verification of ")+green(pkgfilename)+bold(" not supported"))
                elif len(ck) == 32:
                    ckOk = True
                else:
                    print_warning("    "+red("   -> Digest verification of ")+green(pkgfilename)+bold(" failed for unknown reasons"))

                if (ckOk):
                    pkgMatch += 1
                else:
                    pkgNotMatch += 1
                    print_error(red("   Package ")+blue(pkgbranch+"/"+pkgfilename)+red(" is NOT healthy."))
                    brokenPkgsList.append(pkgbranch+"/"+pkgfilename)

            if (brokenPkgsList):
                print_info(blue(" *  This is the list of broken packages: "))
                for bp in brokenPkgsList:
                    print_info(red("    * Package: ")+bold(bp))

            # print stats
            print_info(blue(" *  Statistics for "+Entropy.entropyTools.extractFTPHostFromUri(uri)+":"))
            print_info(brown("     Number of checked packages:\t\t")+str(pkgMatch+pkgNotMatch))
            print_info(green("     Number of healthy packages:\t\t")+str(pkgMatch))
            print_info(red("     Number of broken packages:\t\t")+str(pkgNotMatch))

        dbconn.closeDB()
        return 0

    # FIXME: this function does not update metadata inside tbz2
    # Please implement this !!!
    elif (options[0] == "depsregen"):
        # first of all, sync and lock database
        if not databaseRequestJustScan:
            print_info(green(" * ")+red("Remember to flush all the pending uploads. It's always better having a fully synchronized system."))
            time.sleep(5)
            dbconn = Entropy.databaseTools.openServerDatabase(readOnly = False, noUpload = True)
        else:
            dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)
        print_info(green(" * ")+red("Starting to regenerate package dependencies in repository"))
        idpackages = dbconn.listAllIdpackages()
        maxcount = str(len(idpackages))
        count = 0
        stats = {}
        stats['updated'] = 0
        stats['not_found'] = 0
        stats['bad_digest'] = 0
        for idpackage in idpackages:
            count += 1
            atom = dbconn.retrieveAtom(idpackage)
            branch = dbconn.retrieveBranch(idpackage)
            download = dbconn.retrieveDownloadURL(idpackage)
            checksum = dbconn.retrieveDigest(idpackage)
            # start scanning
            countstring = green(" * ")+red("(")+blue(str(count))+"/"+darkgreen(maxcount)+red(") ")+red("[")+blue(branch)+red("] ")
            print_info(countstring+red("Scanning ")+brown(atom), back = True)
            download = os.path.join(etpConst['entropyworkdir'],download)
            download_upload = os.path.join(etpConst['packagessuploaddir'],branch)
            download_upload = os.path.join(download_upload,os.path.basename(download))
            if not os.path.isfile(download) and not os.path.isfile(download_upload):
                print_warning(countstring+red("  Package Error:"))
                print_warning(countstring+"    "+blue(download)+" not found!")
                print_warning(countstring+"    "+blue(download_upload)+" not found!")
                stats['not_found'] += 1
                continue
            if os.path.isfile(download_upload):
                download = download_upload
            # verify checksum before starting
            if not databaseRequestNoChecksum:
                print_info(countstring+red("Verifying checksum ")+brown(atom), back = True)
                status = Entropy.entropyTools.compareMd5(download,checksum)
                if not status:
                    print_warning(countstring+red("  Checksum Error:"))
                    print_warning(countstring+"    "+blue(download)+" is corrupted!")
                    stats['bad_digest'] += 1
                    continue
            # rescan package
            metadata = Entropy.entropyTools.extractPkgData(download, silent = True)
            db_deps = dbconn.retrieveDependencies(idpackage)
            found_deps = set([unicode(x) for x in metadata['dependencies']])
            del metadata
            if db_deps != found_deps:
                if databaseRequestJustScan:
                    # show difference
                    print_warning(countstring+red("  Dependencies difference for ")+brown(atom)+(":"))
                    print_warning(countstring+"    repository: "+str(db_deps))
                    print_warning(countstring+"    scanned: "+str(found_deps))
                else:
                    stats['updated'] += 1
                    print_info(countstring+red("  Updating dependencies for ")+brown(atom))
                    dbconn.removeDependencies(idpackage)
                    dbconn.insertDependencies(idpackage, found_deps)

        # done !
        print_info(blue(" *  Statistics:"))
        print_info(brown("     Number of checked packages:\t\t")+maxcount)
        print_info(green("     Number of updated packages:\t\t")+str(stats['updated']))
        print_info(red("     Number of broken packages:\t\t")+str(stats['bad_digest']))
        print_info(red("     Number of not found packages:\t\t")+str(stats['not_found']))

    # query tools
    elif (options[0] == "query"):

        import text_query
        myopts = options[1:]

        rc = 0
        dbconn = Entropy.databaseTools.openServerDatabase(readOnly = True, noUpload = True)

        if myopts[0] == "tags":
            if (len(myopts) > 1):
                rc = text_query.searchTaggedPackages(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

        if myopts[0] == "files":
            if (len(myopts) > 1):
                rc = text_query.searchFiles(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

        if myopts[0] == "belongs":
            if (len(myopts) > 1):
                rc = text_query.searchBelongs(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

        if myopts[0] == "description":
            if (len(myopts) > 1):
                text_query.__searchDescriptions(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

        if myopts[0] == "needed":
            if (len(myopts) > 1):
                text_query.searchNeeded(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

        if myopts[0] == "depends":
            if (len(myopts) > 1):
                text_query.searchDepends(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

        if myopts[0] == "eclass":
            if (len(myopts) > 1):
                text_query.searchEclass(myopts[1:], dbconn = dbconn, EquoConnection = Entropy)

        dbconn.closeDB()
        return rc

def spm(options):

    if len(options) < 2:
        return 0
    import portageTools
    options = options[1:]

    opts = []
    do_list = False
    for opt in options:
        if opt == "--list":
            do_list = True
        else:
            opts.append(opt)
    options = opts[:]
    del opts

    action = options[0]

    if action == "categories":
        if len(options) < 2:
            return 0
        categories = list(set(options[1:]))
        categories.sort()
        packages = portageTools.getAvailablePackages(categories)
        packages = list(packages)
        packages.sort()
        if do_list:
            print ' '.join(["="+x for x in packages])
        else:
            os.system(etpConst['spm']['exec']+" "+etpConst['spm']['ask_cmd']+" "+etpConst['spm']['verbose_cmd']+" "+" ".join(["="+x for x in packages]))

