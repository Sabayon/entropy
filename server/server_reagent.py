#!/usr/bin/python
'''
    # DESCRIPTION:
    # textual interface for reagent

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
from outputTools import *
from entropy import ServerInterface, FtpInterface
Entropy = ServerInterface()

def inject(options):

    branch = etpConst['branch']
    mytbz2s = []
    for opt in options:
        if opt.startswith("--branch=") and len(opt.split("=")) == 2:
            branch = opt.split("=")[1]
        else:
            if not os.path.isfile(opt) or not opt.endswith(".tbz2"):
                print_error(darkred(" * ")+bold(opt)+red(" is invalid."))
                return 1
            mytbz2s.append(opt)

    if not mytbz2s:
        print_error(red("no .tbz2 specified."))
        return 2

    for tbz2 in mytbz2s:
        print_info(red("Working on: ")+blue(tbz2))
        Entropy.add_package_to_repository(tbz2, branch, inject = True)

    Entropy.depends_table_initialize()
    # checking dependencies and print issues
    Entropy.dependencies_test()
    Entropy.close_server_databases()


def update(options):

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

    toBeAdded = set()
    toBeRemoved = set()
    toBeInjected = set()

    if not reagentRequestSeekStore:

        if repackageItems:

            appdb = Entropy.SpmService.get_vdb_path()
            packages = []
            dbconn = Entropy.openServerDatabase(read_only = True, no_upload = True)

            for item in repackageItems:
                match = dbconn.atomMatch(item)
                if match[0] == -1:
                    print_warning(darkred("  !!! ")+red("Cannot match ")+bold(item))
                else:
                    cat = dbconn.retrieveCategory(match[0])
                    name = dbconn.retrieveName(match[0])
                    version = dbconn.retrieveVersion(match[0])
                    if os.path.isdir(appdb+"/"+cat+"/"+name+"-"+version):
                        packages.append([cat+"/"+name+"-"+version,0])

            if packages:
                toBeAdded |= set(packages)
            else:
                print_info(brown(" * ")+red("No valid packages to repackage."))


        # normal scanning
        print_info(brown(" * ")+red("Scanning database for differences..."))
        myadded, toBeRemoved, toBeInjected = Entropy.scan_package_changes()
        toBeAdded =| myadded

        if not (len(toBeRemoved)+len(toBeAdded)+len(toBeInjected)):
            print_info(brown(" * ")+red("Zarro thinggz totoo."))
            return 0

        if toBeInjected:
            print_info(brown(" @@ ")+blue("These are the packages that would be changed to injected status:"))
            for x in toBeInjected:
                atom = dbconn.retrieveAtom(x)
                print_info(brown("    # ")+red(atom))
            if reagentRequestAsk:
                rc = Entropy.askQuestion(">>   Would you like to transform them now ?")
            else:
                rc = "Yes"
            if rc == "Yes":
                rwdbconn = Entropy.openServerDatabase(read_only = False, no_upload = True)
                for x in toBeInjected:
                    atom = rwdbconn.retrieveAtom(x)
                    print_info(brown("   <> ")+blue("Transforming from database: ")+red(atom))
                    # get new counter
                    counter = rwdbconn.getNewNegativeCounter()
                    rwdbconn.setCounter(x,counter)
                    rwdbconn.setInjected(x)
                rwdbconn.closeDB()
                print_info(brown(" @@ ")+blue("Database transform complete."))

        if toBeRemoved:
            print_info(brown(" @@ ")+blue("These are the packages that would be removed from the database:"))
            for x in toBeRemoved:
                atom = dbconn.retrieveAtom(x)
                print_info(brown("    # ")+red(atom))
            if reagentRequestAsk:
                rc = Entropy.askQuestion(">>   Would you like to remove them now ?")
            else:
                rc = "Yes"
            if rc == "Yes":
                rwdbconn = Entropy.openServerDatabase(read_only = False, no_upload = True)
                for x in toBeRemoved:
                    atom = rwdbconn.retrieveAtom(x)
                    print_info(brown(" @@ ")+blue("Removing from database: ")+red(atom), back = True)
                    rwdbconn.removePackage(x)
                rwdbconn.closeDB()
                print_info(brown(" @@ ")+blue("Database removal complete."))

        if toBeAdded:
            print_info(brown(" @@ ")+blue("These are the packages that would be added/updated to the add list:"))
            for x in toBeAdded:
                print_info(brown("    # ")+red(x[0]))
            if reagentRequestAsk:
                rc = Entropy.askQuestion(">>   Would you like to package them now ?")
                if rc == "No":
                    return 0

        # package them
        print_info(brown(" @@ ")+blue("Compressing packages..."))
        for x in toBeAdded:
            print_info(brown("    # ")+red(x[0]+"..."))
            Entropy.quickpkg(x[0],etpConst['packagesserverstoredir'])

    requested_branch = etpConst['branch']
    for i in options:
        if ( i.startswith("--branch=") and len(i.split("=")) == 2 ):
            mybranch = i.split("=")[1]
            if (mybranch):
                requested_branch = mybranch

    tbz2files = os.listdir(etpConst['packagesserverstoredir'])
    if not tbz2files:
        print_info(brown(" * ")+red("Nothing to do, check later."))
        # then exit gracefully
        return 0

    counter = 0
    maxcount = str(len(tbz2files))
    for tbz2 in tbz2files:
        counter += 1
        tbz2name = tbz2.split("/")[-1]
        print_info(" ("+str(counter)+"/"+maxcount+") Processing "+tbz2name)
        tbz2path = os.path.join(etpConst['packagesserverstoredir'],tbz2)
        Entropy.add_package_to_repository(tbz2path, requested_branch)

    # regen dependstable
    Entropy.depends_table_initialize(dbconn)
    # checking dependencies and print issues
    Entropy.dependencies_test()

    print_info(green(" * ")+red("Statistics: ")+blue("Entries handled: ")+bold(str(counter)))
    return 0


def database(options):

    import activatorTools

    databaseRequestNoAsk = False
    databaseRequestJustScan = False
    databaseRequestNoChecksum = False
    databaseRequestSync = False
    _options = []
    for opt in options:
        if opt.startswith("--noask"):
            databaseRequestNoAsk = True
        elif opt.startswith("--justscan"):
            databaseRequestJustScan = True
        elif opt.startswith("--nochecksum"):
            databaseRequestNoChecksum = True
        elif opt.startswith("--sync"):
            databaseRequestSync = True
        else:
            _options.append(opt)
    options = _options

    if len(options) == 0:
        print_error(brown(" * ")+red("Not enough parameters"))
        return 1

    if (options[0] == "--initialize"):

        rc = Entropy.initialize_server_database()
        if rc == 0:
            print_info(darkgreen(" * ")+red("Entropy database has been reinitialized using binary packages available"))

    elif (options[0] == "create-empty-database"):

        myopts = options[1:]
        dbpath = None
        if myopts:
            dbpath = myopts[0]

        print_info(darkgreen(" * ")+red("Creating empty database to: ")+dbpath)
        if os.path.isfile(dbpath):
            print_error(darkgreen(" * ")+red("Cannot overwrite already existing file: ")+dbpath)
            return 1
        Entropy.create_empty_database(dbpath)
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

        dbconn = Entropy.openServerDatabase(read_only = False, no_upload = True)
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
        dbconn = Entropy.openServerDatabase(read_only = False, no_upload = True)

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
        dbconn = Entropy.openServerDatabase(read_only = True, no_upload = True)
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
        dbconn = Entropy.openServerDatabase(read_only = False, no_upload = True)

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

        mypackages = options[1:]
        return Entropy.verify_local_packages(mypackages, ask = not databaseRequestNoAsk)

    # used by reagent
    elif (options[0] == "md5remote"):

        mypackages = options[1:]
        return Entropy.verify_remote_packages(mypackages, ask = not databaseRequestNoAsk)

    # bump tool
    elif (options[0] == "bump"):

        print_info(green(" * ")+red("Bumping the database..."))
        Entropy.bump_database()
        if databaseRequestSync:
            activatorTools.database(["sync"])

def spm(options):

    if len(options) < 2:
        return 0
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
        packages = Entropy.SpmService.get_available_packages(categories)
        packages = list(packages)
        packages.sort()
        if do_list:
            print ' '.join(["="+x for x in packages])
        else:
            os.system(etpConst['spm']['exec']+" "+etpConst['spm']['ask_cmd']+" "+etpConst['spm']['verbose_cmd']+" "+" ".join(["="+x for x in packages]))

