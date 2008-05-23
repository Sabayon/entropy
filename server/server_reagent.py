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
from entropy_i18n import _

def inject(options):

    branch = etpConst['branch']
    mytbz2s = []
    for opt in options:
        if opt.startswith("--branch=") and len(opt.split("=")) == 2:
            branch = opt.split("=")[1]
        else:
            if not os.path.isfile(opt) or not opt.endswith(etpConst['packagesext']):
                print_error(darkred(" * ")+bold(opt)+red(" is invalid."))
                return 1
            mytbz2s.append(opt)

    if not mytbz2s:
        print_error(red(_("no package specified.")))
        return 2

    mytbz2s = [(x,branch,True) for x in mytbz2s]
    idpackages = Entropy.add_packages_to_repository(mytbz2s)
    if idpackages:
        # checking dependencies and print issues
        Entropy.dependencies_test()
    Entropy.close_server_databases()

def repositories(options):

    repoid = None
    repoid_dest = None
    cmd = options[0]
    myopts = []
    for opt in options[1:]:
        if cmd in ["enable","disable"]:
            repoid = opt
        elif cmd == "move":
            if repoid == None:
                repoid = opt
            elif repoid_dest == None:
                repoid_dest = opt
            else:
                myopts.append(opt)
        elif cmd == "default":
            if repoid == None:
                repoid = opt
            else:
                myopts.append(opt)
        else:
            myopts.append(opt)

    if cmd in ["enable","disable","move","default"] and not repoid:
        print_error(darkred(" !!! ")+red(_("No valid repositories specified.")))
        return 2

    if cmd == "enable":
        print_info(brown(" @@ ")+red(_("Enabling"))+" "+bold(str(repoid))+red(" %s..." % (_("repository"),) ), back = True)
        rc = Entropy.toggle_repository(repoid, enable = True)
        if rc:
            print_info(brown(" @@ ")+red(_("Enabled"))+" "+bold(str(repoid))+red(" %s." % (_("repository"),) ))
            return 0
        elif rc == False:
            print_info(brown(" @@ ")+red(_("Repository"))+" "+bold(str(repoid))+red(" %s." % (_("already enabled"),) ))
            return 1
        else:
            print_info(brown(" @@ ")+red(_("Configuration file"))+" "+bold(etpConst['serverconf'])+red(" %s." % (_("not found"),) ))
            return 127
    elif cmd == "disable":
        print_info(brown(" @@ ")+red(_("Disabling"))+" "+bold(str(repoid))+red(" %s..." % (_("repository"),) ), back = True)
        rc = Entropy.toggle_repository(repoid, enable = False)
        if rc:
            print_info(brown(" @@ ")+red(_("Disabled"))+" "+bold(str(repoid))+red(" %s." % (_("repository"),) ))
            return 0
        elif rc == False:
            print_info(brown(" @@ ")+red(_("Repository"))+" "+bold(str(repoid))+red(" %s." % (_("already disabled"),) ))
            return 1
        else:
            print_info(brown(" @@ ")+red(_("Configuration file"))+" "+bold(etpConst['serverconf'])+red(" %s." % (_("not found"),) ))
            return 127
    elif cmd == "default":
        Entropy.switch_default_repository(repoid, save = True)
    elif cmd == "status":
        return 0
    elif cmd == "move":
        matches = []
        # from repo: repoid
        # to repo: repoid_dest
        # atoms: myopts
        if "world" not in myopts:
            # match
            for package in myopts:
                match = Entropy.atomMatch(package)
                if (match[1] == repoid):
                    matches.append(match)
                else:
                    print_warning(  brown(" * ") + \
                                    red("%s: " % (_("Cannot match"),) )+bold(package) + \
                                    red(" %s " % (_("in"),) )+bold(repoid)+red(" %s" % (_("repository"),) )
                                 )
            if not matches:
                return 1
        rc = Entropy.move_packages(matches, repoid_dest, repoid)
        if rc:
            return 0
        return 1

    return 1

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
                    print_warning(darkred("  !!! ")+red(_("Cannot match"))+" "+bold(item))
                else:
                    cat = dbconn.retrieveCategory(match[0])
                    name = dbconn.retrieveName(match[0])
                    version = dbconn.retrieveVersion(match[0])
                    if os.path.isdir(appdb+"/"+cat+"/"+name+"-"+version):
                        packages.append((cat+"/"+name+"-"+version,0))

            if packages:
                toBeAdded |= set(packages)
            else:
                print_info(brown(" * ")+red(_("No valid packages to repackage.")))


        # normal scanning
        print_info(brown(" * ")+red("%s..." % (_("Scanning database for differences"),) ))
        myadded, toBeRemoved, toBeInjected = Entropy.scan_package_changes()
        toBeAdded |= myadded

        if not (len(toBeRemoved)+len(toBeAdded)+len(toBeInjected)):
            print_info(brown(" * ")+red("%s." % (_("Zarro thinggz totoo"),) ))
            return 0

        if toBeInjected:
            print_info(brown(" @@ ")+blue("%s:" % (_("These are the packages that would be changed to injected status"),) ))
            for idpackage,repoid in toBeInjected:
                dbconn = Entropy.openServerDatabase(read_only = True, no_upload = True, repo = repoid)
                atom = dbconn.retrieveAtom(idpackage)
                print_info(brown("    # ")+"["+blue(repoid)+"] "+red(atom))
            if reagentRequestAsk:
                rc = Entropy.askQuestion(">>   %s" % (_("Would you like to transform them now ?"),) )
            else:
                rc = "Yes"
            if rc == "Yes":
                for idpackage,repoid in toBeInjected:
                    dbconn = Entropy.openServerDatabase(read_only = True, no_upload = True, repo = repoid)
                    atom = dbconn.retrieveAtom(idpackage)
                    print_info(brown("   <> ")+blue("%s: " % (_("Transforming from database"),) )+red(atom))
                    Entropy.transform_package_into_injected(idpackage, repo = repoid)
                print_info(brown(" @@ ")+blue("%s." % (_("Database transform complete"),) ))

        if toBeRemoved:
            print_info(brown(" @@ ")+blue("%s:" % (_("These are the packages that would be removed from the database"),) ))
            for idpackage,repoid in toBeRemoved:
                dbconn = Entropy.openServerDatabase(read_only = True, no_upload = True, repo = repoid)
                atom = dbconn.retrieveAtom(idpackage)
                print_info(brown("    # ")+"["+blue(repoid)+"] "+red(atom))
            if reagentRequestAsk:
                rc = Entropy.askQuestion(">>   %s" % (_("Would you like to remove them now ?"),) )
            else:
                rc = "Yes"
            if rc == "Yes":
                remdata = {}
                for idpackage,repoid in toBeRemoved:
                    if not remdata.has_key(repoid):
                        remdata[repoid] = set()
                    remdata[repoid].add(idpackage)
                for repoid in remdata:
                    Entropy.remove_packages(remdata[repoid], repo = repoid)

        if toBeAdded:
            print_info(brown(" @@ ")+blue("%s:" % (_("These are the packages that would be added/updated to the add list"),) ))
            for x in toBeAdded:
                print_info(brown("    # ")+red(x[0]))
            if reagentRequestAsk:
                rc = Entropy.askQuestion(">>   %s (%s %s)" % (
                        _("Would you like to package them now ?"),
                        _("inside"),
                        Entropy.default_repository,
                    )
                )
                if rc == "No":
                    return 0

        # package them
        print_info(brown(" @@ ")+blue("%s..." % (_("Compressing packages"),) ))
        for x in toBeAdded:
            print_info(brown("    # ")+red(x[0]+"..."))
            try:
                Entropy.quickpkg(x[0],Entropy.get_local_store_directory())
            except OSError:
                entropyTools.printTraceback()
                print_info(brown("    !!! ")+bold("%s..." % (_("Ignoring broken Spm entry, please recompile it"),) ))

    requested_branch = etpConst['branch']
    for i in options:
        if ( i.startswith("--branch=") and len(i.split("=")) == 2 ):
            mybranch = i.split("=")[1]
            if (mybranch):
                requested_branch = mybranch

    tbz2files = os.listdir(Entropy.get_local_store_directory())
    if not tbz2files:
        print_info(brown(" * ")+red(_("Nothing to do, check later.")))
        # then exit gracefully
        return 0

    tbz2files = [(os.path.join(Entropy.get_local_store_directory(),x),requested_branch,False) for x in tbz2files]
    idpackages = Entropy.add_packages_to_repository(tbz2files)

    if idpackages:
        # checking dependencies and print issues
        Entropy.dependencies_test()
    Entropy.close_server_databases()
    print_info(green(" * ")+red("%s: " % (_("Statistics"),) )+blue("%s: " % (_("Entries handled"),) )+bold(str(len(idpackages))))
    return 0


def database(options):

    databaseRequestNoAsk = False
    databaseRequestSync = False
    databaseRequestEmpty = False
    repo = None
    _options = []
    for opt in options:
        if opt.startswith("--noask"):
            databaseRequestNoAsk = True
        elif opt.startswith("--sync"):
            databaseRequestSync = True
        elif opt.startswith("--empty"):
            databaseRequestEmpty = True
        elif opt.startswith("--repo=") and len(opt.split("=")) == 2:
            repo = opt.split("=")[1]
            databaseRequestEmpty = True
        else:
            _options.append(opt)
    options = _options

    if not options:
        print_error(brown(" * ")+red(_("Not enough parameters")))
        return 1

    if (options[0] == "--initialize"):

        rc = Entropy.initialize_server_database(empty = databaseRequestEmpty, repo = repo)
        if rc == 0:
            print_info(darkgreen(" * ")+red(_("Entropy database has been reinitialized using binary packages available")))

    elif (options[0] == "create-empty-database"):

        myopts = options[1:]
        dbpath = None
        if myopts:
            dbpath = myopts[0]
        print_info(darkgreen(" * ")+red("%s: " % (_("Creating empty database to"),) )+dbpath)
        if os.path.isfile(dbpath):
            print_error(darkgreen(" * ")+red("%s: " % (_("Cannot overwrite already existing file"),) )+dbpath)
            return 1
        Entropy.create_empty_database(dbpath)
        return 0

    elif (options[0] == "switchbranch"):

        if (len(options) < 3):
            print_error(brown(" * ")+red(_("Not enough parameters")))
            return 1

        switchbranch = options[1]
        print_info(darkgreen(" * ")+red(_("Switching branch, be sure to have your packages in sync.")))
        print_info(darkgreen(" * ")+red("%s %s..." % (_("Collecting packages that would be marked"),switchbranch,) ), back = True)
        dbconn = Entropy.openServerDatabase(read_only = True, no_upload = True)

        pkglist = set()
        myatoms = options[2:]
        if "world" in myatoms:
            pkglist |= dbconn.listAllIdpackages()
        else:
            for atom in myatoms:
                match = dbconn.atomMatch(atom)
                if match == -1:
                    print_warning(brown(" * ")+red("%s: " % (_("Cannot match"),) )+bold(atom))
                else:
                    pkglist.add(match[0])

        if not pkglist:
            print_error(brown(" * ")+red("%s." % (_("No packages found"),) ))
            return 3

        print_info(darkgreen(" * ")+red("%s %s:" % (_("These are the packages that would be marked"),switchbranch,)))
        for idpackage in pkglist:
            atom = dbconn.retrieveAtom(idpackage)
            print_info(red("   # ")+bold(atom))

        rc = Entropy.askQuestion(_("Would you like to continue ?"))
        if rc == "No":
            return 4

        switched, already_switched, ignored, not_found, no_checksum = Entropy.switch_packages_branch(pkglist, to_branch = switchbranch)
        if not_found or no_checksum:
            return 1
        return 0


    elif (options[0] == "remove"):

        print_info(darkgreen(" * ")+red("%s..." % (_("Matching packages to remove"),) ), back = True)
        myopts = []
        branch = None
        for opt in options[1:]:
            if (opt.startswith("--branch=")) and (len(opt.split("=")) == 2):
                branch = opt.split("=")[1]
            else:
                myopts.append(opt)

        if not myopts:
            print_error(brown(" * ")+red(_("Not enough parameters")))
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
            print_error(brown(" * ")+red("%s." % (_("No packages found"),) ))
            return 2

        print_info(darkgreen(" * ")+red("%s:" % (_("These are the packages that would be removed from the database"),) ))
        for idpackage in pkglist:
            pkgatom = dbconn.retrieveAtom(idpackage)
            branch = dbconn.retrieveBranch(idpackage)
            print_info(red("   # ")+blue("[")+red(branch)+blue("] ")+bold(pkgatom))


        rc = Entropy.askQuestion(_("Would you like to continue ?"))
        if rc == "No":
            return 0

        print_info(darkgreen(" * ")+red("%s..." % (_("Removing selected packages"),) ))
        Entropy.remove_packages(pkglist)
        print_info(darkgreen(" * ")+red(_("Packages removed. To remove binary packages, run activator.")))

        return 0

    elif (options[0] == "multiremove"):

        print_info(darkgreen(" * ")+red("%s..." % (_("Searching injected packages to remove"),) ), back = True)

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
            print_error(brown(" * ")+red("%s." % (_("No packages found"),) ))
            return 1

        print_info(darkgreen(" * ")+blue("%s:" % (_("These are the injected packages pulled in for removal"),) ))

        for idpackage in idpackages:
            pkgatom = dbconn.retrieveAtom(idpackage)
            branch = dbconn.retrieveBranch(idpackage)
            print_info(darkred("    # ")+blue("[")+red(branch)+blue("] ")+brown(pkgatom))

        # ask to continue
        rc = Entropy.askQuestion(_("Would you like to continue ?"))
        if rc == "No":
            return 0

        print_info(green(" * ")+red("%s ..." % (_("Removing selected packages"),) ))
        Entropy.remove_packages(idpackages)

        Entropy.close_server_database(dbconn)
        print_info(darkgreen(" * ")+red(_("Packages removed. To remove binary packages, run activator.")))
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

        print_info(green(" * ")+red("%s..." % (_("Bumping Repository database"),) ))
        Entropy.bump_database()
        if databaseRequestSync:
            errors, fine, broken = Entropy.MirrorsService.sync_databases()

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
