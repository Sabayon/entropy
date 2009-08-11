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

import subprocess
from entropy.const import *
from entropy.output import *
from entropy.server.interfaces import Server
from entropy.i18n import _
Entropy = Server(community_repo = etpConst['community']['mode'])

def inject(options):

    mytbz2s = []
    for opt in options:
        opt = os.path.realpath(opt)
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

    valid_repos = Entropy.get_available_repositories()
    repoid = None
    repoid_dest = None
    pull_deps = False
    invalid_repos = False
    if not options: cmd = ""
    else: cmd = options[0]
    myopts = []
    for opt in options[1:]:
        if cmd in ["enable","disable"]:
            if opt not in valid_repos:
                invalid_repos = True
            repoid = opt
        elif cmd in ["move","copy"]:
            if repoid == None:
                repoid = opt
            elif repoid_dest == None:
                if opt not in valid_repos:
                    invalid_repos = True
                repoid_dest = opt
            elif opt == "--deps":
                pull_deps = True
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

    if invalid_repos:
        print_error(darkred(" !!! ")+red(_("Invalid repositories specified.")))
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

        sys_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        if repo not in Entropy.SystemSettings[sys_settings_plugin_id]['server']['repositories']:
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

        sys_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        if repo not in Entropy.SystemSettings[sys_settings_plugin_id]['server']['repositories']:
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
                if match in matches:
                    print_warning(  brown(" * ") + \
                        red("%s: " % (_("Package"),) ) + bold(package) + \
                        red(" %s " % (_("already pulled in"),))
                    )
                elif (match[1] == repoid):
                    matches.append(match)
                else:
                    print_warning(  brown(" * ") + \
                        red("%s: " % (_("Cannot match"),) )+bold(package) + \
                        red(" %s " % (_("in"),) )+bold(repoid)+red(" %s" % (_("repository"),) )
                    )
            if not matches:
                return 1
        if cmd == "move":
            rc = Entropy.move_packages(matches, repoid_dest, repoid,
                pull_deps = pull_deps)
        elif cmd == "copy":
            rc = Entropy.move_packages(matches, repoid_dest, repoid,
                do_copy = True, pull_deps = pull_deps)
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
    reagentRequestOnlyAtoms = False
    repackageItems = []
    onlyAtoms = []
    _options = []
    for opt in options:
        if opt == "--seekstore":
            reagentRequestSeekStore = True
        elif opt == "--repackage":
            reagentRequestRepackage = True
        elif opt == "--atoms":
            reagentRequestOnlyAtoms = True
        elif opt == "--noask":
            reagentRequestAsk = False
        else:
            if reagentRequestRepackage and (not opt.startswith("--")):
                if not opt in repackageItems:
                    repackageItems.append(opt)
                continue
            elif reagentRequestOnlyAtoms and (not opt.startswith("--")):
                if not opt in onlyAtoms:
                    onlyAtoms.append(opt)
                continue
            _options.append(opt)
    options = _options

    toBeAdded = set()
    toBeRemoved = set()
    toBeInjected = set()

    if not reagentRequestSeekStore:

        if repackageItems:

            appdb = Entropy.Spm().get_vdb_path()
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

        if onlyAtoms:
            toBeRemoved.clear()
            toBeInjected.clear()
            tba = dict(((x[0],x,) for x in toBeAdded))
            tb_added_new = set()
            for myatom in onlyAtoms:
                if myatom in tba:
                    tb_added_new.add(tba.get(myatom))
                    continue
                inst_myatom = Entropy.Spm().get_installed_atom(myatom)
                if inst_myatom in tba:
                    tb_added_new.add(tba.get(inst_myatom))
            toBeAdded = tb_added_new

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
                exp_string = ''
                pkg_expired = Entropy.is_match_expired((idpackage,repoid,))
                if pkg_expired:
                    exp_string = "|%s" % (purple(_("expired")),)
                print_info(brown("    # ")+"["+blue(repoid)+exp_string+"] "+red(atom))
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

        sys_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        for repoid in Entropy.SystemSettings[sys_settings_plugin_id]['server']['repositories']:

            print_info(darkgreen(" * ")+"%s %s %s: %s" % (
                blue(_("Collecting packages that would be marked")),
                bold(to_branch),blue(_("on")),purple(repoid),) )

            dbconn_old = Entropy.open_server_repository(read_only = True,
                no_upload = True, repo = repoid, use_branch = from_branch,
                do_treeupdates = False)
            pkglist = dbconn_old.listAllIdpackages()

            print_info(darkgreen(" * ")+"%s %s: %s %s" % (
                blue(_("These are the packages that would be marked")),
                bold(to_branch), len(pkglist), darkgreen(_("packages")),))

            rc = Entropy.askQuestion(_("Would you like to continue ?"))
            if rc == "No":
                return 4

            status = Entropy.switch_packages_branch(from_branch, to_branch,
                repo = repoid)
            if status == None:
                return 1

        switched, already_switched, ignored, not_found, no_checksum = status
        if not_found or no_checksum:
            return 1
        return 0

    elif (options[0] == "flushback"):

        if (len(options) < 2):
            print_error(brown(" * ")+red(_("Not enough parameters")))
            return 1

        from_branches = options[1:]
        status = Entropy.flushback_packages(from_branches)
        if status:
            return 0
        return 1

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
    do_rebuild = False
    do_dbsync = False
    do_dbupdate = False
    for opt in options:
        if opt == "--list":
            do_list = True
        elif opt == "--rebuild":
            do_rebuild = True
        elif opt == "--dbsync":
            do_dbsync = True
        elif opt == "--dbupdate":
            do_dbupdate = True
        elif opt.startswith("--"):
            continue
        else:
            opts.append(opt)
    options = opts[:]
    del opts

    action = options[0]

    if action == "compile":

        options = options[1:]
        if not options:
            return 1

        if options[0] == "categories":
            return spm_compile_categories(options[1:], do_list = do_list)
        elif options[0] == "pkgset":
            return spm_compile_pkgset(options[1:], do_rebuild = do_rebuild,
                do_dbupdate = do_dbupdate, do_dbsync = do_dbsync)

    elif action == "orphans":

        not_found = Entropy.orphaned_spm_packages_test()
        return 0


def spm_compile_categories(options, do_list = False):

    categories = sorted(set(options))
    packages = Entropy.Spm().get_available_packages(categories)
    packages = sorted(packages)
    if do_list:
        print ' '.join(["="+x for x in packages])
    else:
        args = [etpConst['spm']['exec'], etpConst['spm']['ask_cmd'],
            etpConst['spm']['verbose_cmd']]
        args.extend(["="+x for x in packages])
        return subprocess.call(args)
    return 0

def spm_compile_pkgset(pkgsets, do_rebuild = False, do_dbupdate = False,
    do_dbsync = False):

    if not pkgsets:
        print_error(bold(" !!! ")+darkred("%s." % (
            _("No package sets found"),) ))
        return 1

    # filter available sets
    avail_sets = Entropy.Spm().get_sets(False)
    avail_pkgsets = dict(((x,avail_sets.get(x),) for x in pkgsets \
        if x in avail_sets))
    for pkgset in pkgsets:
        if pkgset not in avail_sets:
            print_error(bold(" !!! ")+darkred("%s: %s" % (
                _("package set not found"),pkgset,) ))
            return 1

    extra_args = []
    if etpUi['ask']:
        extra_args.append(etpConst['spm']['ask_cmd'])
    if etpUi['verbose']:
        extra_args.append(etpConst['spm']['verbose_cmd'])
    if etpUi['pretend']:
        extra_args.append(etpConst['spm']['pretend_cmd'])

    done_atoms = set()

    # expand package sets
    for pkgset in pkgsets:

        set_pkgs = [str(x) for x in Entropy.Spm().get_set_atoms(pkgset)]
        set_atoms = [Entropy.Spm().get_best_atom(x) for x in set_pkgs]
        set_atoms = [x for x in set_atoms if x != None]

        if not do_rebuild:
            set_atoms = [x for x in set_atoms if not \
                Entropy.Spm().get_installed_atom(x)]
        set_atoms = ["="+x for x in set_atoms]
        if not set_atoms:
            continue

        args = [etpConst['spm']['exec']]
        args.extend(extra_args)
        args.extend(set_atoms)
        rc = subprocess.call(args)
        if rc != 0:
            return rc
        done_atoms |= set(set_atoms)

    if not done_atoms:
        print_warning(red(" @@ ")+blue("%s." % (
            _("Nothing to do"),) ))
        return 0

    # compilation went fine, now push into entropy
    if do_dbsync:
        do_dbupdate = True

    if do_dbupdate:
        dbopts = []
        if not etpUi['ask']:
            dbopts.append("--noask")
        dbopts.append("--atoms")
        dbopts.extend(sorted(done_atoms))
        rc = update(dbopts)
        Entropy.close_server_databases()
        if rc != 0:
            return rc

    if do_dbsync:
        import server_activator
        actopts = []
        if not etpUi['ask']:
            actopts.append("--noask")
        rc = server_activator.sync(actopts)
        if rc != 0:
            return rc

    return 0
