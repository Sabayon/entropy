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

from entropy.const import *
from entropy.output import *
from entropy.server.interfaces import Server
from entropy.i18n import _
Entropy = Server(community_repo = etpConst['community']['mode'])

def inject(options):

    mytbz2s = []
    for opt in options:
        if not os.path.isfile(opt) or not opt.endswith(etpConst['packagesext']):
            print_error(darkred(" * ")+bold(opt)+red(" is invalid."))
            return 1
        mytbz2s.append(opt)

    if not mytbz2s:
        print_error(red(_("no package specified.")))
        return 2

    mytbz2s = [(x,True,) for x in mytbz2s]
    idpackages = Entropy.add_packages_to_repository(mytbz2s)
    if idpackages:
        # checking dependencies and print issues
        Entropy.dependencies_test()
    Entropy.close_server_databases()

def repositories(options):

    repoid = None
    repoid_dest = None
    if not options: cmd = ""
    else: cmd = options[0]
    myopts = []
    for opt in options[1:]:
        if cmd in ["enable","disable"]:
            repoid = opt
        elif cmd in ["move","copy"]:
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

    if cmd in ["enable","disable","copy","move","default"] and not repoid:
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
    elif cmd == "package-tag":

        if len(myopts) < 3:
            return 1
        repo = myopts[0]

        if repo not in etpConst['server_repositories']:
            return 3

        tag_string = myopts[1]
        atoms = myopts[2:]
        # match
        idpackages = []
        for package in atoms:
            match = Entropy.atom_match(package, matchRepo = [repo], matchTag = '')
            if (match[1] == repo):
                idpackages.append(match[0])
            else:
                print_warning(  brown(" * ") + \
                    red("%s: " % (_("Cannot match"),) )+bold(package) + \
                    red(" %s " % (_("in"),) )+bold(repo)+red(" %s" % (_("repository"),) )
                )
        if not idpackages: return 2
        status, data = Entropy.tag_packages(tag_string, idpackages, repo = repo)
        return status

    elif cmd == "manual-deps":

        if len(myopts) < 2:
            return 1
        repo = myopts[0]

        if repo not in etpConst['server_repositories']:
            return 3

        atoms = myopts[1:]
        # match
        idpackages = []
        for package in atoms:
            match = Entropy.atom_match(package, matchRepo = [repo], matchTag = '')
            if match[1] == repo:
                idpackages.append(match[0])
            else:
                print_warning(  brown(" * ") + \
                    red("%s: " % (_("Cannot match"),) )+bold(package) + \
                    red(" %s " % (_("in"),) )+bold(repo)+red(" %s" % (_("repository"),) )
                )
        if not idpackages: return 2
        dbconn = Entropy.open_server_repository(repo = repo, just_reading = True)

        def dep_check_cb(s):
            return Entropy.entropyTools.isvalidatom(s)

        for idpackage in idpackages:
            atom = dbconn.retrieveAtom(idpackage)
            orig_deps = dbconn.retrieveDependencies(idpackage, extended = True)
            atom_deps = [x for x in orig_deps if x[1] != etpConst['spm']['mdepend_id']]
            atom_manual_deps = [x for x in orig_deps if x not in atom_deps]
            print_info(brown(" @@ ")+"%s: %s:" % (blue(atom),darkgreen(_("package dependencies")),))
            for dep_str, dep_id in atom_deps:
                print_info("%s [type:%s] %s" % (brown("    # "),darkgreen(str(dep_id)),darkred(dep_str),))
            if not atom_deps:
                print_info("%s %s" % (brown("    # "),_("No dependencies"),))
            print_info(brown(" @@ ")+"%s: %s:" % (blue(atom),darkgreen(_("package manual dependencies")),))
            for dep_str, dep_id in atom_manual_deps:
                print_info("%s [type:%s] %s" % (brown("    # "),darkgreen(str(dep_id)),purple(dep_str),))
            if not atom_manual_deps:
                print_info("%s %s" % (brown("    # "),_("No dependencies"),))
            print
            current_mdeps = sorted([x[0] for x in atom_manual_deps])
            input_params = [
                ('new_mdeps',('list',('Manual dependencies',current_mdeps),),dep_check_cb,True)
            ]
            data = Entropy.inputBox(_("Manual dependencies editor"),input_params)
            if data == None: return 4
            new_mdeps = sorted(data.get('new_mdeps',[]))

            if current_mdeps == new_mdeps:
                print_info(brown(" @@ ")+blue("%s: %s" % (atom,_("no changes made"),) ))
                continue

            w_dbconn = Entropy.open_server_repository(repo = repo, read_only = False)
            atom_deps += [(x,etpConst['spm']['mdepend_id'],) for x in new_mdeps]
            deps_dict = {}
            for atom_dep, dep_id in atom_deps:
                deps_dict[atom_dep] = dep_id

            while 1:
                try:
                    w_dbconn.removeDependencies(idpackage)
                    w_dbconn.insertDependencies(idpackage, deps_dict)
                    w_dbconn.commitChanges()
                except (KeyboardInterrupt, SystemExit,):
                    continue
                break
            print_info(brown(" @@ ")+"%s: %s" % (blue(atom),darkgreen(_("manual dependencies added successfully")),))

        Entropy.close_server_databases()
        return 0

    elif cmd in ["move","copy"]:
        matches = []
        # from repo: repoid
        # to repo: repoid_dest
        # atoms: myopts
        if "world" not in myopts:
            # match
            for package in myopts:
                match = Entropy.atom_match(package, matchRepo = [repoid])
                if (match[1] == repoid):
                    matches.append(match)
                else:
                    print_warning(  brown(" * ") + \
                        red("%s: " % (_("Cannot match"),) )+bold(package) + \
                        red(" %s " % (_("in"),) )+bold(repoid)+red(" %s" % (_("repository"),) )
                    )
            if not matches:
                return 1
        if cmd == "move":
            rc = Entropy.move_packages(matches, repoid_dest, repoid)
        elif cmd == "copy":
            rc = Entropy.move_packages(matches, repoid_dest, repoid, do_copy = True)
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
            dbconn = Entropy.open_server_repository(read_only = True, no_upload = True)

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
                dbconn = Entropy.open_server_repository(read_only = True, no_upload = True, repo = repoid)
                atom = dbconn.retrieveAtom(idpackage)
                print_info(brown("    # ")+"["+blue(repoid)+"] "+red(atom))
            if reagentRequestAsk:
                rc = Entropy.askQuestion(">>   %s" % (_("Would you like to transform them now ?"),) )
            else:
                rc = "Yes"
            if rc == "Yes":
                for idpackage,repoid in toBeInjected:
                    dbconn = Entropy.open_server_repository(read_only = True, no_upload = True, repo = repoid)
                    atom = dbconn.retrieveAtom(idpackage)
                    print_info(brown("   <> ")+blue("%s: " % (_("Transforming from database"),) )+red(atom))
                    Entropy.transform_package_into_injected(idpackage, repo = repoid)
                print_info(brown(" @@ ")+blue("%s." % (_("Database transform complete"),) ))

        if toBeRemoved:
            print_info(brown(" @@ ")+blue("%s:" % (_("These are the packages that would be removed from the database"),) ))
            for idpackage,repoid in toBeRemoved:
                dbconn = Entropy.open_server_repository(read_only = True, no_upload = True, repo = repoid)
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
            items = sorted([x[0] for x in toBeAdded])
            for item in items:
                print_info(brown("    # ")+red(item))
            if reagentRequestAsk:
                rc = Entropy.askQuestion(">>   %s (%s %s)" % (
                        _("Would you like to package them now ?"),
                        _("inside"),
                        Entropy.default_repository,
                    )
                )
                if rc == "No":
                    return 0

            problems = Entropy.check_config_file_updates()
            if problems:
                return 1

        # package them
        print_info(brown(" @@ ")+blue("%s..." % (_("Compressing packages"),) ))
        for x in toBeAdded:
            print_info(brown("    # ")+red(x[0]+"..."))
            try:
                Entropy.quickpkg(x[0],Entropy.get_local_store_directory())
            except OSError:
                Entropy.entropyTools.print_traceback()
                print_info(brown("    !!! ")+bold("%s..." % (_("Ignoring broken Spm entry, please recompile it"),) ))

    tbz2files = os.listdir(Entropy.get_local_store_directory())
    if not tbz2files:
        print_info(brown(" * ")+red(_("Nothing to do, check later.")))
        # then exit gracefully
        return 0

    tbz2files = [(os.path.join(Entropy.get_local_store_directory(),x),False,) for x in tbz2files]
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

        from_branch = options[1]
        to_branch = options[2]
        print_info(darkgreen(" * ")+red(_("Switching branch, be sure to have your packages in sync.")))
        print_info(darkgreen(" * ")+red("%s %s..." % (_("Collecting packages that would be marked"),to_branch,) ), back = True)
        dbconn = Entropy.open_server_repository(read_only = True, no_upload = True)

        pkglist = dbconn.listAllIdpackages(branch = from_branch)
        #myatoms = options[3:]

        print_info(darkgreen(" * ")+red("%s %s: %s %s" % (_("These are the packages that would be marked"),to_branch,len(pkglist),_("packages"),)))

        rc = Entropy.askQuestion(_("Would you like to continue ?"))
        if rc == "No":
            return 4

        status = Entropy.switch_packages_branch(pkglist, from_branch, to_branch)
        if status == None:
            return 1
        switched, already_switched, ignored, not_found, no_checksum = status
        if not_found or no_checksum:
            return 1
        return 0


    elif (options[0] == "remove"):

        print_info(darkgreen(" * ")+red("%s..." % (_("Matching packages to remove"),) ), back = True)
        myopts = []
        for opt in options[1:]:
            myopts.append(opt)

        if not myopts:
            print_error(brown(" * ")+red(_("Not enough parameters")))
            return 1

        dbconn = Entropy.open_server_repository(read_only = True, no_upload = True)
        pkglist = set()
        for atom in myopts:
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

        atoms = []
        for opt in options[1:]:
            atoms.append(opt)

        dbconn = Entropy.open_server_repository(read_only = True, no_upload = True)

        idpackages = set()
        if not atoms:
            allidpackages = dbconn.listAllIdpackages()
            for idpackage in allidpackages:
                if dbconn.isInjected(idpackage):
                    idpackages.add(idpackage)
        else:
            for atom in atoms:
                match = dbconn.atomMatch(atom, multiMatch = True)
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
            print_info(darkred("    # ")+brown(pkgatom))

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

    elif (options[0] == "backup"):

        db_path = Entropy.get_local_database_file()
        rc, err_msg = Entropy.ClientService.backup_database(db_path, backup_dir = os.path.dirname(db_path))
        if not rc:
            print_info(darkred(" ** ")+red("%s: %s" % (_("Error"),err_msg,) ))
            return 1
        return 0

    elif (options[0] == "restore"):


        db_file = Entropy.get_local_database_file()
        db_dir = os.path.dirname(db_file)
        dblist = Entropy.ClientService.list_backedup_client_databases(client_dbdir = db_dir)
        if not dblist:
            print_info(brown(" @@ ")+blue("%s." % (_("No backed up databases found"),)))
            return 1

        mydblist = []
        db_data = []
        for mydb in dblist:
            ts = Entropy.entropyTools.get_file_unix_mtime(mydb)
            mytime = Entropy.entropyTools.convert_unix_time_to_human_time(ts)
            mydblist.append("[%s] %s" % (mytime,mydb,))
            db_data.append(mydb)

        def fake_cb(s):
            return s

        input_params = [
            ('db',('combo',(_('Select the database you want to restore'),mydblist),),fake_cb,True)
        ]

        while 1:
            data = Entropy.inputBox(red(_("Entropy installed packages database restore tool")), input_params, cancel_button = True)
            if data == None:
                return 1
            myid, dbx = data['db']
            print dbx
            try:
                dbpath = db_data.pop(myid)
            except IndexError:
                continue
            if not os.path.isfile(dbpath): continue
            break

        status, err_msg = Entropy.ClientService.restore_database(dbpath, db_file)
        if status:
            return 0
        return 1


def spm(options):

    if not options:
        return 0

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

    if action == "compile":

        options = options[1:]
        if not options:
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

    elif action == "orphans":

        not_found = Entropy.orphaned_spm_packages_test()
        return 0
