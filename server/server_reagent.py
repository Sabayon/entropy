# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server}.

"""
import os
import subprocess
from entropy.const import etpConst, etpUi
from entropy.output import red, bold, brown, purple, darkgreen, darkred, blue, \
    green, print_info, print_warning, print_error, print_generic, teal
from text_tools import print_table
from entropy.exceptions import InvalidAtom
from entropy.server.interfaces import Server
from entropy.core.settings.base import SystemSettings
from entropy.i18n import _

import entropy.tools
Entropy = Server(community_repo = etpConst['community']['mode'])
SYS_SET = SystemSettings()

def inject(options):

    etp_pkg_files = []
    for opt in options:
        opt = os.path.realpath(opt)
        if not (os.path.isfile(opt) and os.access(opt, os.R_OK)):
            print_error(darkred(" * ")+bold(opt)+red(" is invalid."))
            return 1
        etp_pkg_files.append(opt)

    if not etp_pkg_files:
        print_error(red(_("no package specified.")))
        return 2

    etp_pkg_files = [(x, True,) for x in etp_pkg_files]
    idpackages = Entropy.add_packages_to_repository(etp_pkg_files)
    if idpackages:
        # checking dependencies and print issues
        Entropy.dependencies_test()
    Entropy.close_repositories()

def repositories(options):

    valid_repos = Entropy.get_available_repositories()
    repoid = None
    repoid_dest = None
    pull_deps = False
    invalid_repos = False
    request_noask = False
    request_sync = False
    request_nodeps = False

    if not options:
        cmd = ""
    else:
        cmd = options[0]
    myopts = []
    for opt in options[1:]:

        if opt == "--sync":
            request_sync = True
        elif opt == "--noask":
            request_noask = True
        elif opt == "--nodeps":
            request_nodeps = True
        elif cmd in ["enable", "disable"]:
            if opt not in valid_repos:
                invalid_repos = True
            repoid = opt
        elif cmd in ["move", "copy"]:
            if repoid is None:
                repoid = opt
            elif repoid_dest is None:
                if opt not in valid_repos:
                    invalid_repos = True
                repoid_dest = opt
            elif opt == "--deps":
                pull_deps = True
            else:
                myopts.append(opt)
        elif cmd == "default":
            if repoid is None:
                repoid = opt
            else:
                myopts.append(opt)
        else:
            myopts.append(opt)

    if cmd in ["enable", "disable", "copy", "move", "default"] and not repoid:
        print_error(darkred(" !!! ")+red(_("No valid repositories specified.")))
        return 2

    if invalid_repos:
        print_error(darkred(" !!! ")+red(_("Invalid repositories specified.")))
        return 2

    if cmd == "enable":
        print_info(brown(" @@ ")+red(_("Enabling"))+" "+bold(str(repoid)) + \
            red(" %s..." % (_("repository"),) ), back = True)
        rc = Entropy.toggle_repository(repoid, enable = True)
        if rc:
            print_info(brown(" @@ ")+red(_("Enabled"))+" "+bold(str(repoid)) + \
                red(" %s." % (_("repository"),) ))
            return 0
        elif rc == False:
            print_info(brown(" @@ ")+red(_("Repository"))+" " + \
                bold(str(repoid)) + red(" %s." % (_("already enabled"),) ))
            return 1
        else:
            print_info(brown(" @@ ")+red(_("Configuration file"))+" " + \
                bold(etpConst['serverconf'])+red(" %s." % (_("not found"),) ))
            return 127

    elif cmd == "disable":
        print_info(brown(" @@ ")+red(_("Disabling"))+" "+bold(str(repoid)) + \
            red(" %s..." % (_("repository"),) ), back = True)
        rc = Entropy.toggle_repository(repoid, enable = False)
        if rc:
            print_info(brown(" @@ ")+red(_("Disabled"))+" " + \
                bold(str(repoid)) + red(" %s." % (_("repository"),) ))
            return 0
        elif rc == False:
            print_info(brown(" @@ ")+red(_("Repository"))+" " + \
                bold(str(repoid))+red(" %s." % (_("already disabled"),) ))
            return 1
        else:
            print_info(brown(" @@ ")+red(_("Configuration file"))+" " + \
                bold(etpConst['serverconf'])+red(" %s." % (_("not found"),) ))
            return 127

    elif cmd == "default":
        Entropy.switch_default_repository(repoid, save = True)
        return 0

    elif cmd == "package-tag":

        if len(myopts) < 3:
            return 1
        repo = myopts[0]

        sys_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        srv_set = SYS_SET[sys_settings_plugin_id]['server']
        if repo not in srv_set['repositories']:
            return 3

        tag_string = myopts[1]
        atoms = myopts[2:]
        # match
        idpackages = []
        for package in atoms:
            match = Entropy.atom_match(package + '#', match_repo = [repo])
            if (match[1] == repo):
                idpackages.append(match[0])
            else:
                print_warning(  brown(" * ") + \
                    red("%s: " % (_("Cannot match"),) )+bold(package) + \
                    red(" %s " % (_("in"),) )+bold(repo) + \
                        red(" %s" % (_("repository"),) )
                )
        if not idpackages:
            return 2
        status, data = Entropy.tag_packages(tag_string, idpackages, repo = repo)
        return status

    elif cmd == "package-dep":

        if len(myopts) < 2:
            return 1
        repo = myopts[0]

        sys_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        srv_set = SYS_SET[sys_settings_plugin_id]['server']
        if repo not in srv_set['repositories']:
            return 3

        atoms = myopts[1:]
        # match
        idpackages = []
        for package in atoms:
            match = Entropy.atom_match(package, match_repo = [repo])
            if match[1] == repo:
                idpackages.append(match[0])
            else:
                print_warning(  brown(" * ") + \
                    red("%s: " % (_("Cannot match"),) )+bold(package) + \
                    red(" %s " % (_("in"),) )+bold(repo) + \
                        red(" %s" % (_("repository"),) )
                )
        if not idpackages:
            return 2
        dbconn = Entropy.open_server_repository(repo = repo, just_reading = True)

        def _show_dependencies_legend(indent = ''):
            for dep_id, dep_val in sorted(etpConst['dependency_type_ids'].items(),
                key = lambda x: x[0], reverse = True):

                dep_desc = etpConst['dependency_type_ids_desc'].get(dep_id, _("N/A"))
                txt = '%s%s%s%s %s' % (indent, teal("{"), dep_val+1, teal("}"), dep_desc,)
                print_info(txt)

        def _print_pkg_deps(atom, orig_deps, partial = False):
            if not partial:
                print_info(brown(" @@ ")+"%s: %s:" % (blue(atom),
                    darkgreen(_("package dependencies")),))
            else:
                print_generic("")

            for dep_str, dep_id in orig_deps:
                print_info("%s [%s: %s] %s" % (
                    brown("  #"), brown(_("type")),
                    darkgreen(str(dep_id+1)), purple(dep_str),))
            if not orig_deps:
                print_info("%s %s" % (brown("    # "), _("No dependencies"),))
            else:
                _show_dependencies_legend("  ")

            if partial:
                print_generic("")

        avail_dep_type_desc = []
        d_type_ids = etpConst['dependency_type_ids']
        d_type_desc = etpConst['dependency_type_ids_desc']
        for dep_val, dep_id in sorted(d_type_ids.items(), key = lambda x: x[1]):
            avail_dep_type_desc.append(d_type_desc[dep_val])

        def pkg_dep_types_cb(s):
            try:
                avail_dep_type_desc.index(s[1])
            except IndexError:
                return False
            return True

        for idpackage in idpackages:

            atom = dbconn.retrieveAtom(idpackage)
            orig_deps = dbconn.retrieveDependencies(idpackage, extended = True)
            dep_type_map = dict(orig_deps)

            def dep_check_cb(s):

                input_params = [
                    ('dep_type', ('combo', (_("Dependency type"), avail_dep_type_desc),),
                        pkg_dep_types_cb, False)
                ]
                data = Entropy.input_box(
                    ("%s: %s" % (_('Select a dependency type for'), s,)),
                    input_params
                )
                if data is None:
                    return False

                rc_dep_type = avail_dep_type_desc.index(data['dep_type'][1])
                dep_type_map[s] = rc_dep_type
                changes_made_type_map = {s: rc_dep_type}

                _print_pkg_deps(atom, changes_made_type_map.items(),
                    partial = True)

                return True

            _print_pkg_deps(atom, orig_deps)

            print_generic("")
            current_deps = [x[0] for x in orig_deps]

            input_params = [
                ('new_deps', ('list', (_('Dependencies'), current_deps),),
                    dep_check_cb, True)
            ]
            data = Entropy.input_box(_("Dependencies editor"), input_params)
            if data is None:
                continue

            new_deps = data.get('new_deps', [])
            orig_deps = [(x, dep_type_map[x],) for x in new_deps]
            insert_deps = dict(orig_deps)

            _print_pkg_deps(atom, orig_deps)
            rc_ask = Entropy.ask_question(_("Confirm ?"))
            if rc_ask == _("No"):
                continue


            w_dbconn = Entropy.open_server_repository(repo = repo,
                read_only = False)

            # save new dependencies
            while True:
                try:
                    w_dbconn.removeDependencies(idpackage)
                    w_dbconn.insertDependencies(idpackage, insert_deps)
                    w_dbconn.commitChanges()
                except (KeyboardInterrupt, SystemExit,):
                    continue
                break

            # now bump, this makes EAPI=3 differential db sync happy
            old_pkg_data = w_dbconn.getPackageData(idpackage)
            w_dbconn.handlePackage(old_pkg_data)

            print_info(brown(" @@ ")+"%s: %s" % (blue(atom),
                darkgreen(_("dependencies updated successfully")),))

        Entropy.close_repositories()
        return 0

    elif cmd in ["move", "copy"]:
        matches = []
        # from repo: repoid
        # to repo: repoid_dest
        # atoms: myopts
        if myopts:
            # match
            for package in myopts:
                p_matches, p_rc = Entropy.atom_match(package,
                    match_repo = [repoid], multi_match = True)
                if not p_matches:
                    print_warning(  brown(" * ") + \
                        red("%s: " % (_("Cannot match"),) )+bold(package) + \
                        red(" %s " % (_("in"),) )+bold(repoid) + \
                            red(" %s" % (_("repository"),) )
                    )
                else:
                    matches += [x for x in p_matches if (x not in matches)]

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

    elif cmd == "remove":

        print_info(darkgreen(" * ") + \
            red("%s..." % (_("Matching packages to remove"),) ), back = True)

        if not myopts:
            print_error(brown(" * ")+red(_("Not enough parameters")))
            return 1

        def_repo = Entropy.default_repository
        dbconn = Entropy.open_repository(def_repo)
        pkglist = set()
        for atom in myopts:
            pkg = dbconn.atomMatch(atom, multiMatch = True)
            for idpackage in pkg[0]:
                pkglist.add(idpackage)

        pkg_matches = [(x, def_repo) for x in pkglist]
        if not request_nodeps:
            # Entropy.default_repository
            pkg_matches = Entropy.get_reverse_queue(pkg_matches,
                system_packages = False)

        if not pkg_matches:
            print_error(brown(" * ")+red("%s." % (_("No packages found"),) ))
            return 2

        print_info(darkgreen(" * ") + \
            red("%s:" % (_("These are the packages that would be removed from the database"),) ))
        repo_map = {}
        for idpackage, repo_id in pkg_matches:
            repo_db = Entropy.open_repository(repo_id)
            pkgatom = repo_db.retrieveAtom(idpackage)
            print_info(red("   # ") + blue("[") + teal(repo_id) + blue("] ") + \
                purple(pkgatom))
            obj = repo_map.setdefault(repo_id, [])
            obj.append(idpackage)

        rc = Entropy.ask_question(_("Would you like to continue ?"))
        if rc == _("No"):
            return 0

        print_info(darkgreen(" * ") + \
            red("%s..." % (_("Removing selected packages"),) ))
        for repo_id, idpackages in repo_map.items():
            Entropy.remove_packages(idpackages, repo = repo_id)
        print_info(darkgreen(" * ") + \
            red(_("Packages removed. To remove binary packages, run activator.")))

        return 0

    elif cmd == "multiremove":

        print_info(darkgreen(" * ") + \
            red("%s..." % (_("Searching injected packages to remove"),) ),
                back = True)

        dbconn = Entropy.open_server_repository(read_only = True,
            no_upload = True)

        idpackages = set()
        if not myopts:
            allidpackages = dbconn.listAllPackageIds()
            for idpackage in allidpackages:
                if dbconn.isInjected(idpackage):
                    idpackages.add(idpackage)
        else:
            for atom in myopts:
                match = dbconn.atomMatch(atom, multiMatch = True)
                for x in match[0]:
                    if dbconn.isInjected(x):
                        idpackages.add(x)

        if not idpackages:
            print_error(brown(" * ")+red("%s." % (_("No packages found"),) ))
            return 1

        print_info(darkgreen(" * ") + \
            blue("%s:" % (
                _("These are the injected packages pulled in for removal"),) ))

        for idpackage in idpackages:
            pkgatom = dbconn.retrieveAtom(idpackage)
            print_info(darkred("    # ")+brown(pkgatom))

        # ask to continue
        rc = Entropy.ask_question(_("Would you like to continue ?"))
        if rc == _("No"):
            return 0

        print_info(green(" * ")+red("%s ..." % (_("Removing selected packages"),) ))
        Entropy.remove_packages(idpackages)

        Entropy.close_repository(dbconn)
        print_info(darkgreen(" * ") + \
            red(_("Packages removed. To remove binary packages, run activator.")))
        return 0

    elif cmd == "--initialize":

        rc = Entropy.initialize_server_repository()
        if rc == 0:
            print_info(darkgreen(" * ") + \
                red(_("Entropy repository has been initialized")))

    elif cmd == "create-empty-database":

        dbpath = None
        if myopts:
            dbpath = myopts[0]
        print_info(darkgreen(" * ")+red("%s: " % (_("Creating empty database to"),) )+dbpath)
        if os.path.isfile(dbpath):
            print_error(darkgreen(" * ")+red("%s: " % (_("Cannot overwrite already existing file"),) )+dbpath)
            return 1
        Entropy.setup_empty_repository(dbpath)
        return 0

    elif cmd == "switchbranch":

        if (len(myopts) < 2):
            print_error(brown(" * ")+red(_("Not enough parameters")))
            return 1

        from_branch = myopts[0]
        to_branch = myopts[1]
        print_info(darkgreen(" * ")+red(_("Switching branch, be sure to have your packages in sync.")))

        sys_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['server_plugin']
        for repoid in SYS_SET[sys_settings_plugin_id]['server']['repositories']:

            print_info(darkgreen(" * ")+"%s %s %s: %s" % (
                blue(_("Collecting packages that would be marked")),
                bold(to_branch), blue(_("on")), purple(repoid),) )

            dbconn_old = Entropy.open_server_repository(read_only = True,
                no_upload = True, repo = repoid, use_branch = from_branch,
                do_treeupdates = False)
            pkglist = dbconn_old.listAllPackageIds()

            print_info(darkgreen(" * ")+"%s %s: %s %s" % (
                blue(_("These are the packages that would be marked")),
                bold(to_branch), len(pkglist), darkgreen(_("packages")),))

            rc = Entropy.ask_question(_("Would you like to continue ?"))
            if rc == _("No"):
                return 4

            status = Entropy.switch_packages_branch(from_branch, to_branch,
                repo = repoid)
            if status is None:
                return 1

        switched, already_switched, ignored, not_found, no_checksum = status
        if not_found or no_checksum:
            return 1
        return 0

    elif cmd == "flushback":

        if not myopts:
            print_error(brown(" * ")+red(_("Not enough parameters")))
            return 1

        status = Entropy.flushback_packages(myopts)
        if status:
            return 0
        return 1

    elif cmd == "md5remote":

        Entropy.verify_remote_packages(myopts, ask = not request_noask)
        return 0

    elif cmd == "bump":

        print_info(green(" * ")+red("%s..." % (_("Bumping Repository database"),) ))
        Entropy._bump_database()
        if request_sync:
            errors, fine, broken = Entropy.Mirrors.sync_repositories()
        return 0

    elif cmd == "backup":

        db_path = Entropy._get_local_database_file()
        rc, err_msg = Entropy.backup_repository(db_path,
            backup_dir = os.path.dirname(db_path))
        if not rc:
            print_info(darkred(" ** ")+red("%s: %s" % (_("Error"), err_msg,) ))
            return 1
        return 0

    elif cmd == "restore":


        db_file = Entropy._get_local_database_file()
        db_dir = os.path.dirname(db_file)
        dblist = Entropy.installed_repository_backups(
            client_dbdir = db_dir)
        if not dblist:
            print_info(brown(" @@ ")+blue("%s." % (_("No backed up databases found"),)))
            return 1

        mydblist = []
        db_data = []
        for mydb in dblist:
            ts = os.path.getmtime(mydb)
            mytime = entropy.tools.convert_unix_time_to_human_time(ts)
            mydblist.append("[%s] %s" % (mytime, mydb,))
            db_data.append(mydb)

        def fake_cb(s):
            return s

        input_params = [
            ('db', ('combo', (_('Select the database you want to restore'),
                mydblist),), fake_cb, True)
        ]

        while True:
            data = Entropy.input_box(
                red(_("Entropy installed packages database restore tool")),
                input_params, cancel_button = True)
            if data is None:
                return 1
            myid, dbx = data['db']
            print(dbx)
            try:
                dbpath = db_data.pop(myid)
            except IndexError:
                continue
            if not os.path.isfile(dbpath):
                continue
            break

        status, err_msg = Entropy.restore_repository(dbpath, db_file)
        if status:
            return 0
        return 1

    return -10

def update(options):

    # differential checking
    # collect differences between the packages in the database
    # and the ones on the system

    r_request_seek_store = False
    r_request_repackage = False
    r_request_ask = True
    r_request_only_atoms = False
    r_request_interactive = False

    repackage_items = []
    only_atoms = []
    _options = []
    for opt in options:
        if opt == "--seekstore":
            r_request_seek_store = True
        elif opt == "--repackage":
            r_request_repackage = True
        elif opt == "--atoms":
            r_request_only_atoms = True
        elif opt == "--noask":
            r_request_ask = False
        elif opt == "--interactive":
            r_request_interactive = True
        else:
            if r_request_repackage and (not opt.startswith("--")):
                if not opt in repackage_items:
                    repackage_items.append(opt)
                continue
            elif r_request_only_atoms and (not opt.startswith("--")):
                if not opt in only_atoms:
                    only_atoms.append(opt)
                continue
            _options.append(opt)
    options = _options

    to_be_added = set()
    to_be_removed = set()
    to_be_injected = set()

    if not r_request_seek_store:

        if repackage_items:

            packages = []
            dbconn = Entropy.open_server_repository(read_only = True,
                no_upload = True)

            spm = Entropy.Spm()
            for item in repackage_items:
                match = dbconn.atomMatch(item)
                if match[0] == -1:
                    print_warning(darkred("  !!! ") + \
                        red(_("Cannot match"))+" "+bold(item))
                else:
                    cat = dbconn.retrieveCategory(match[0])
                    name = dbconn.retrieveName(match[0])
                    version = dbconn.retrieveVersion(match[0])
                    spm_pkg = os.path.join(cat, name + "-" + version)
                    spm_build = spm.get_installed_package_build_script_path(
                        spm_pkg)
                    spm_pkg_dir = os.path.dirname(spm_build)
                    if os.path.isdir(spm_pkg_dir):
                        packages.append((spm_pkg, 0))

            if packages:
                to_be_added |= set(packages)
            else:
                print_info(brown(" * ") + \
                    red(_("No valid packages to repackage.")))


        # normal scanning
        print_info(brown(" * ") + \
            red("%s..." % (_("Scanning database for differences"),) ))
        try:
            myadded, to_be_removed, to_be_injected = \
                Entropy.scan_package_changes()
        except KeyboardInterrupt:
            return 1
        to_be_added |= myadded

        if only_atoms:
            to_be_removed.clear()
            to_be_injected.clear()
            tba = dict(((x[0], x,) for x in to_be_added))
            tb_added_new = set()
            for myatom in only_atoms:
                if myatom in tba:
                    tb_added_new.add(tba.get(myatom))
                    continue
                try:
                    inst_myatom = Entropy.Spm().match_installed_package(myatom)
                except InvalidAtom:
                    print_warning(darkred("  !!! ")+red(_("Invalid atom"))+" "+bold(myatom))
                    continue
                if inst_myatom in tba:
                    tb_added_new.add(tba.get(inst_myatom))
            to_be_added = tb_added_new

        if not (len(to_be_removed)+len(to_be_added)+len(to_be_injected)):
            print_info(brown(" * ")+red("%s." % (_("Zarro thinggz totoo"),) ))
            return 0

        if to_be_injected:
            print_info(brown(" @@ ")+blue("%s:" % (_("These are the packages that would be changed to injected status"),) ))
            for idpackage, repoid in to_be_injected:
                dbconn = Entropy.open_server_repository(read_only = True, no_upload = True, repo = repoid)
                atom = dbconn.retrieveAtom(idpackage)
                print_info(brown("    # ")+"["+blue(repoid)+"] "+red(atom))
            if r_request_ask:
                rc = Entropy.ask_question(">>   %s" % (_("Would you like to transform them now ?"),) )
            else:
                rc = _("Yes")
            if rc == _("Yes"):
                for idpackage, repoid in to_be_injected:
                    dbconn = Entropy.open_server_repository(read_only = True, no_upload = True, repo = repoid)
                    atom = dbconn.retrieveAtom(idpackage)
                    print_info(brown("   <> ")+blue("%s: " % (_("Transforming from database"),) )+red(atom))
                    Entropy._transform_package_into_injected(idpackage,
                        repo = repoid)
                print_info(brown(" @@ ")+blue("%s." % (_("Database transform complete"),) ))

        def show_rm(idpackage, repoid):
            dbconn = Entropy.open_server_repository(read_only = True,
                no_upload = True, repo = repoid)
            atom = dbconn.retrieveAtom(idpackage)
            exp_string = ''
            pkg_expired = Entropy._is_match_expired((idpackage, repoid,))
            if pkg_expired:
                exp_string = "|%s" % (purple(_("expired")),)
            print_info(brown("    # ")+"["+blue(repoid)+exp_string+"] "+red(atom))

        if r_request_interactive and to_be_removed:
            print_info(brown(" @@ ")+blue(_("So sweetheart, what packages do you want to remove ?")))
            new_to_be_removed = set()
            for idpackage, repoid in to_be_removed:
                show_rm(idpackage, repoid)
                rc = Entropy.ask_question(">>   %s" % (_("Remove this package?"),))
                if rc == _("Yes"):
                    new_to_be_removed.add((idpackage, repoid,))
            to_be_removed = new_to_be_removed

        if to_be_removed:

            print_info(brown(" @@ ")+blue("%s:" % (_("These are the packages that would be removed from the database"),) ))
            for idpackage, repoid in to_be_removed:
                show_rm(idpackage, repoid)

            if r_request_ask:
                rc = Entropy.ask_question(">>   %s" % (_("Would you like to remove them now ?"),) )
            else:
                rc = _("Yes")
            if rc == _("Yes"):
                remdata = {}
                for idpackage, repoid in to_be_removed:
                    if repoid not in remdata:
                        remdata[repoid] = set()
                    remdata[repoid].add(idpackage)
                for repoid in remdata:
                    Entropy.remove_packages(remdata[repoid], repo = repoid)

        if r_request_interactive and to_be_added:
            print_info(brown(" @@ ")+blue(_("So sweetheart, what packages do you want to add ?")))
            new_to_be_added = set()
            for tb_atom, tb_counter in to_be_added:
                print_info(brown("    # ")+red(tb_atom))
                rc = Entropy.ask_question(">>   %s" % (_("Add this package?"),))
                if rc == _("Yes"):
                    new_to_be_added.add((tb_atom, tb_counter,))
            to_be_added = new_to_be_added

        if to_be_added:

            print_info(brown(" @@ ")+blue("%s:" % (_("These are the packages that would be added/updated to the add list"),) ))
            items = sorted([x[0] for x in to_be_added])
            for item in items:
                item_txt = purple(item)


                # this is a spm atom
                try:
                    spm_slot = Entropy.Spm().get_installed_package_metadata(
                        item, "SLOT")
                    spm_repo = Entropy.Spm().get_installed_package_metadata(
                        item, "repository")
                    spm_key = entropy.tools.dep_getkey(item)
                except KeyError:
                    spm_slot = None
                    spm_key = None
                    spm_repo = None

                #
                # inform user about SPM repository sources moves !!
                #
                etp_repo = None
                if spm_repo is not None:
                    pkg_id, repo_id = Entropy.atom_match(spm_key,
                        match_slot = spm_slot)
                    if repo_id != 1:
                        repo_db = Entropy.open_server_repository(
                            repo = repo_id, just_reading = True)
                        etp_repo = repo_db.retrieveSpmRepository(pkg_id)

                        if (etp_repo is not None) and (etp_repo != spm_repo):
                            item_txt += ' [%s {%s=>%s}]' % (bold(_("warning")),
                                darkgreen(etp_repo), blue(spm_repo),)

                print_info(brown("  # ")+item_txt)

            if r_request_ask:
                rc = Entropy.ask_question(">>   %s (%s %s)" % (
                        _("Would you like to package them now ?"),
                        _("inside"),
                        Entropy.default_repository,
                    )
                )
                if rc == _("No"):
                    return 0

            problems = Entropy._check_config_file_updates()
            if problems:
                return 1

        # package them
        print_info(brown(" @@ ")+blue("%s..." % (_("Compressing packages"),) ))
        for x in to_be_added:
            print_info(brown("    # ")+red(x[0]+"..."))
            try:
                Entropy.Spm().generate_package(x[0],
                    Entropy._get_local_store_directory())
            except OSError:
                entropy.tools.print_traceback()
                print_info(brown("    !!! ")+bold("%s..." % (
                    _("Ignoring broken Spm entry, please recompile it"),) ))

    store_dir = Entropy._get_local_store_directory()
    etp_pkg_files = []
    if os.path.isdir(store_dir):
        etp_pkg_files = os.listdir(store_dir)
    if not etp_pkg_files:
        print_info(brown(" * ")+red(_("Nothing to do, check later.")))
        # then exit gracefully
        return 0

    etp_pkg_files = [(os.path.join(Entropy._get_local_store_directory(), x), False,) for x in etp_pkg_files]
    idpackages = Entropy.add_packages_to_repository(etp_pkg_files)

    if idpackages:
        # checking dependencies and print issues
        Entropy.dependencies_test()
    Entropy.close_repositories()
    print_info(green(" * ")+red("%s: " % (_("Statistics"),) )+blue("%s: " % (_("Entries handled"),) )+bold(str(len(idpackages))))
    return 0


def status():

    sys_settings_plugin_id = \
        etpConst['system_settings_plugins_ids']['server_plugin']
    repos_data = SYS_SET[sys_settings_plugin_id]['server']['repositories']

    for repo_id in sorted(repos_data):
        repo_data = repos_data[repo_id]
        repo_rev = Entropy.get_local_repository_revision(repo = repo_id)
        store_dir = Entropy._get_local_store_directory(repo = repo_id)
        upload_basedir = Entropy._get_local_upload_directory(repo = repo_id)
        upload_files, upload_packages = \
            Entropy.Mirrors._calculate_local_upload_files(repo = repo_id)
        local_files, local_packages = \
            Entropy.Mirrors._calculate_local_package_files(repo = repo_id)

        toc = []

        toc.append("[%s] %s" % (purple(repo_id),
            brown(repo_data['description']),))
        toc.append(("  %s:" % (blue(_("local revision")),),
            str(repo_rev),))
        toc.append(("  %s:" % (darkgreen(_("local packages")),),
            str(local_files),))

        store_pkgs = []
        if os.path.isdir(store_dir):
            store_pkgs = os.listdir(store_dir)

        toc.append(("  %s:" % (darkgreen(_("stored packages")),),
            str(len(store_pkgs)),))
        for pkg_rel in sorted(store_pkgs):
            toc.append((" ", brown(pkg_rel)))

        toc.append(("  %s:" % (darkgreen(_("upload packages")),),
            str(upload_files),))
        for pkg_rel in sorted(upload_packages):
            toc.append((" ", brown(pkg_rel)))

        print_table(toc)

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

    elif action == "new":
        spm = Entropy.Spm()
        spm_avail = spm.get_packages(categories = options)
        spm_installed = spm.get_installed_packages(categories = options)
        spm_avail_exp = set((x, spm.get_package_metadata(x, "SLOT")) for x \
            in spm_avail)
        spm_installed_exp = set((x, spm.get_installed_package_metadata(x,
            "SLOT")) for x in spm_installed)

        newly_available = sorted(spm_avail_exp - spm_installed_exp)

        print_info(brown(" @@ ")+blue("%s:" % (_("These are the newly available packages, either updatable or not installed"),) ))
        if etpUi['quiet']:
            print_generic(' '.join(["=%s:%s" % (x, y) for x, y in \
                newly_available]))
        else:
            for pkg, slot in newly_available:
                print_info(red("   # =") + teal(pkg) + blue(":") + purple(slot))

        return 0

    return -10

def spm_compile_categories(options, do_list = False):

    # --nooldslots support
    oldslots = "--nooldslots" not in options
    if not oldslots:
        while True:
            try:
                options.remove("--nooldslots")
            except ValueError:
                break

    spm = Entropy.Spm()
    categories = sorted(set(options))
    packages = spm.get_packages(categories)
    packages = sorted(packages)

    # remove older packages from list (through slot)
    if not oldslots:
        oldslots_meta = {}
        for package in packages:
            pkg_slot = spm.get_package_metadata(package, "SLOT")
            pkg_key = entropy.tools.dep_getkey(package)
            obj = oldslots_meta.setdefault(pkg_key, set())
            obj.add((pkg_slot, package,))
        del packages[:]
        for pkg_key in sorted(oldslots_meta):
            slots_data = sorted(oldslots_meta[pkg_key])
            packages.append(slots_data[-1][1])

    if do_list:
        print_generic(' '.join(["="+x for x in packages]))
    else:
        return spm.compile_packages(["="+x for x in packages],
            ask = True, verbose = True, coloured_output = True)
    return 0

def spm_compile_pkgset(pkgsets, do_rebuild = False, do_dbupdate = False,
    do_dbsync = False):

    if not pkgsets:
        print_error(bold(" !!! ")+darkred("%s." % (
            _("No package sets found"),) ))
        return 1

    # filter available sets
    avail_sets = Entropy.Spm().get_package_sets(False)
    for pkgset in pkgsets:
        if pkgset not in avail_sets:
            print_error(bold(" !!! ")+darkred("%s: %s" % (
                _("package set not found"), pkgset,) ))
            return 1

    spm = Entropy.Spm()

    done_atoms = set()

    # expand package sets
    for pkgset in pkgsets:

        set_atoms = [spm.match_package(x) for x in avail_sets[pkgset]]
        set_atoms = [x for x in set_atoms if x]

        if not do_rebuild:
            set_atoms = [x for x in set_atoms if not \
                spm.match_installed_package(x)]
        set_atoms = ["="+x for x in set_atoms]
        if not set_atoms:
            continue

        rc = spm.compile_packages(set_atoms, verbose = etpUi['verbose'],
            ask = etpUi['ask'], pretend = etpUi['pretend'],
            coloured_output = True)
        if rc != 0:
            return rc
        done_atoms.update(set_atoms)

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
        Entropy.close_repositories()
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
