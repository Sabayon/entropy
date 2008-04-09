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

from entropyConstants import *
from outputTools import *
from entropy import ServerInterface
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

    mytbz2s = [(x,branch,True) for x in mytbz2s]
    idpackages = Entropy.add_packages_to_repository(mytbz2s)
    if idpackages:
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
                        packages.append((cat+"/"+name+"-"+version,0))

            if packages:
                toBeAdded |= set(packages)
            else:
                print_info(brown(" * ")+red("No valid packages to repackage."))


        # normal scanning
        print_info(brown(" * ")+red("Scanning database for differences..."))
        myadded, toBeRemoved, toBeInjected = Entropy.scan_package_changes()
        toBeAdded |= myadded

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
                mydbconn = Entropy.openServerDatabase(just_reading = True)
                for x in toBeInjected:
                    atom = mydbconn.retrieveAtom(x)
                    print_info(brown("   <> ")+blue("Transforming from database: ")+red(atom))
                    Entropy.transform_package_into_injected(x)
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
                Entropy.remove_packages(toBeRemoved)

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

    tbz2files = [(os.path.join(etpConst['packagesserverstoredir'],x),requested_branch,False) for x in tbz2files]
    idpackages = Entropy.add_packages_to_repository(tbz2files)

    if idpackages:
        # checking dependencies and print issues
        Entropy.dependencies_test()
    Entropy.close_server_databases()
    print_info(green(" * ")+red("Statistics: ")+blue("Entries handled: ")+bold(str(len(idpackages))))
    return 0


def database(options):

    databaseRequestNoAsk = False
    databaseRequestSync = False
    _options = []
    for opt in options:
        if opt.startswith("--noask"):
            databaseRequestNoAsk = True
        elif opt.startswith("--sync"):
            databaseRequestSync = True
        else:
            _options.append(opt)
    options = _options

    if not options:
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

        if (len(options) < 3):
            print_error(brown(" * ")+red("Not enough parameters"))
            return 1

        switchbranch = options[1]
        print_info(darkgreen(" * ")+red("Switching branch, be sure to have your packages in sync."))
        print_info(darkgreen(" * ")+red("Collecting packages that would be marked %s..." % (switchbranch,) ), back = True)
        dbconn = Entropy.openServerDatabase(read_only = True, no_upload = True)

        pkglist = set()
        myatoms = options[2:]
        if "world" in myatoms:
            pkglist |= dbconn.listAllIdpackages()
        else:
            for atom in myatoms:
                match = dbconn.atomMatch(atom)
                if match == -1:
                    print_warning(brown(" * ")+red("Cannot match: ")+bold(atom))
                else:
                    pkglist.add(match[0])

        if not pkglist:
            print_error(brown(" * ")+red("No packages found."))
            return 3

        print_info(darkgreen(" * ")+red("These are the packages that would be marked %s:" % (switchbranch,)))
        for idpackage in pkglist:
            atom = dbconn.retrieveAtom(idpackage)
            print_info(red("   # ")+bold(atom))

        rc = Entropy.askQuestion("Would you like to continue ?")
        if rc == "No":
            return 4

        switched, already_switched, ignored, not_found, no_checksum = Entropy.switch_packages_branch(pkglist, to_branch = switchbranch)
        if not_found or no_checksum:
            return 1
        return 0


    elif (options[0] == "remove"):

        print_info(darkgreen(" * ")+red("Matching packages to remove..."), back = True)
        myopts = []
        branch = None
        for opt in options[1:]:
            if (opt.startswith("--branch=")) and (len(opt.split("=")) == 2):
                branch = opt.split("=")[1]
            else:
                myopts.append(opt)

        if not myopts:
            print_error(brown(" * ")+red("Not enough parameters"))
            return 1

        dbconn = Entropy.openServerDatabase(read_only = True, no_upload = True)
        pkglist = set()
        for atom in myopts:
            if branch:
                pkg = dbconn.atomMatch(atom, matchBranches = (branch,), multiMatch = True)
            else:
                pkg = dbconn.atomMatch(atom, multiMatch = True)
            if pkg[1] == 0:
                for idpackage in pkg[0]:
                    pkglist.add(idpackage)

        if not pkglist:
            print_error(brown(" * ")+red("No packages found."))
            return 2

        print_info(darkgreen(" * ")+red("These are the packages that would be removed from the database:"))
        for idpackage in pkglist:
            pkgatom = dbconn.retrieveAtom(idpackage)
            branch = dbconn.retrieveBranch(idpackage)
            print_info(red("   # ")+blue("[")+red(branch)+blue("] ")+bold(pkgatom))


        rc = Entropy.askQuestion("Would you like to continue ?")
        if rc == "No":
            return 0

        print_info(darkgreen(" * ")+red("Removing selected packages..."))
        for idpackage in pkglist:
            pkgatom = dbconn.retrieveAtom(idpackage)
            print_info(darkgreen(" * ")+red("Removing package: ")+bold(pkgatom)+red("..."), back = True)
            Entropy.remove_package(idpackage)

        Entropy.close_server_database(dbconn)
        print_info(darkgreen(" * ")+red("Packages removed. To remove binary packages, run activator."))

        return 0

    elif (options[0] == "multiremove"):

        print_info(darkgreen(" * ")+red("Searching injected packages to remove..."), back = True)

        branch = etpConst['branch']
        atoms = []
        for opt in options[1:]:
            if (opt.startswith("--branch=")) and (len(opt.split("=")) == 2):
                branch = opt.split("=")[1]
            else:
                atoms.append(opt)

        dbconn = Entropy.openServerDatabase(read_only = True, no_upload = True)

        idpackages = set()
        if not atoms:
            allidpackages = dbconn.listAllIdpackages()
            for idpackage in allidpackages:
                if dbconn.isInjected(idpackage):
                    idpackages.add(idpackage)
        else:
            for atom in atoms:
                match = dbconn.atomMatch(atom, matchBranches = (branch,), multiMatch = True)
                if match[1] == 0:
                    for x in match[0]:
                        if dbconn.isInjected(x):
                            idpackages.add(x)

        if not idpackages:
            print_error(brown(" * ")+red("No packages found."))
            return 1

        print_info(darkgreen(" * ")+blue("These are the injected packages pulled in for removal:"))

        for idpackage in idpackages:
            pkgatom = dbconn.retrieveAtom(idpackage)
            branch = dbconn.retrieveBranch(idpackage)
            print_info(darkred("    # ")+blue("[")+red(branch)+blue("] ")+brown(pkgatom))

        # ask to continue
        rc = Entropy.askQuestion("Would you like to continue ?")
        if rc == "No":
            return 0

        print_info(green(" * ")+red("Removing selected packages ..."))
        for idpackage in idpackages:
            pkgatom = dbconn.retrieveAtom(idpackage)
            print_info(darkgreen(" * ")+red("Removing package: ")+bold(pkgatom)+red("..."), back = True)
            Entropy.remove_package(idpackage)

        Entropy.close_server_database(dbconn)
        print_info(darkgreen(" * ")+red("Packages removed. To remove binary packages, run activator."))
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
            Entropy.MirrorsService.sync_databases()

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
