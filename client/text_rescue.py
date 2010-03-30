# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
import os
import sys
import shutil
import tempfile

from entropy.const import etpConst, etpSys, etpUi
from entropy.output import red, bold, brown, blue, darkred, darkgreen, purple, \
    print_info, print_warning, print_error
from entropy.exceptions import SystemDatabaseError
import entropy.tools
from entropy.client.interfaces import Client
from entropy.i18n import _

# strictly depending on Portage atm
from entropy.spm.plugins.interfaces.portage_plugin import xpaktools

def _backup_client_repository():
    """
    docstring_title

    @return: 
    @rtype: 
    """
    if not os.path.isfile(etpConst['etpdatabaseclientfilepath']):
        return

    rnd = entropy.tools.get_random_number()
    source = etpConst['etpdatabaseclientfilepath']
    dest = etpConst['etpdatabaseclientfilepath']+".backup."+str(rnd)
    shutil.copy2(source, dest)
    user = os.stat(source)[4]
    group = os.stat(source)[5]
    os.chown(dest, user, group)
    shutil.copystat(source, dest)
    return dest

def test_spm(entropy_client):
    # test if portage is available
    try:
        return entropy_client.Spm()
    except Exception as err:
        entropy.tools.print_traceback()
        mytxt = _("Source Package Manager backend not available")
        print_error(darkred(" * ")+red("%s: %s" % (mytxt, err,)))
        return None

def test_clientdb(entropy_client):
    try:
        entropy_client.installed_repository().validateDatabase()
    except SystemDatabaseError:
        mytxt = _("Installed packages database not available")
        print_error(darkred(" * ")+red("%s !" % (mytxt,)))
        return 1

def database(options):

    if not options:
        return -10

    # check if I am root
    if not entropy.tools.is_root():
        mytxt = _("You are not root")
        print_error(red(mytxt+"."))
        return 1

    etp_client = Client(noclientdb = True)
    try:

        if options[0] == "generate":
            return _database_generate(etp_client)

        elif options[0] == "check":
            return _database_check(etp_client)

        elif options[0] == "resurrect":
            return _database_resurrect(etp_client)

        elif options[0] == "revdeps":
            return _database_revdeps(etp_client)

        elif options[0] in ("counters", "spmuids",):
            if options[0] == "counters":
                print_warning("")
                print_warning("'%s' %s: '%s'" % (
                    purple("equo database counters"),
                    blue(_("is deprecated, please use")),
                    darkgreen("equo database spmuids"),))
                print_warning("")
            return _database_counters(etp_client)

        elif options[0] in ("gentoosync", "spmsync",):
            if options[0] == "gentoosync":
                print_warning("")
                print_warning("'%s' %s: '%s'" % (
                    purple("equo database gentoosync"),
                    blue(_("is deprecated, please use")),
                    darkgreen("equo database spmsync"),))
                print_warning("")
            return _database_spmsync(etp_client)

        elif options[0] == "backup":
            status, err_msg = etp_client.backup_repository(
                etpConst['etpdatabaseclientfilepath'])
            if status:
                return 0
            return 1

        elif options[0] == "restore":
            return _database_restore(etp_client)

        elif options[0] == "vacuum":
            return _database_vacuum(etp_client)

        elif options[0] == "info":
            return _getinfo(etp_client)

    finally:
        etp_client.shutdown()

    return -10

def _database_vacuum(entropy_client):
    if entropy_client.installed_repository() is not None:
        print_info(red(" @@ ")+"%s..." % (blue(_("Vacuum cleaning System Database")),), back = True)
        entropy_client.installed_repository().dropAllIndexes()
        entropy_client.installed_repository().vacuum()
        entropy_client.installed_repository().commitChanges()
        print_info(red(" @@ ")+"%s." % (brown(_("Vacuum cleaned System Database")),))
        return 0
    print_warning(darkred(" !!! ")+blue("%s." % (_("No System Databases found"),)))
    return 1

def _database_restore(entropy_client):

    dblist = entropy_client.installed_repository_backups()
    if not dblist:
        print_info(brown(" @@ ")+blue("%s." % (
            _("No backed up databases found"),)))
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
        data = entropy_client.input_box(
            red(_("Entropy installed packages database restore tool")),
                input_params, cancel_button = True)
        if data is None:
            return 1
        myid, dbx = data['db']
        try:
            dbpath = db_data.pop(myid-1)
        except IndexError:
            continue
        if not os.path.isfile(dbpath):
            continue
        break

    status, err_msg = entropy_client.restore_repository(dbpath,
        etpConst['etpdatabaseclientfilepath'])
    if status:
        return 0
    return 1


def _database_counters(entropy_client):
    Spm = test_spm(entropy_client)
    if Spm is None:
        return 1

    rc = test_clientdb(entropy_client)
    if rc is not None:
        return rc

    print_info(red("  %s..." % (_("Regenerating counters table"),) ))
    entropy_client.installed_repository().regenerateSpmUidTable(verbose = True)
    print_info(red("  %s" % (
        _("Counters table regenerated. Look above for errors."),) ))
    return 0

def _database_revdeps(entropy_client):
    rc = test_clientdb(entropy_client)
    if rc is not None:
        return rc

    print_info(red("  %s..." % (
        _("Regenerating reverse dependencies metadata"),) ))
    entropy_client.installed_repository().generateReverseDependenciesMetadata()
    print_info(red("  %s." % (
        _("Reverse dependencies metadata regenerated successfully"),) ))
    return 0

def _database_resurrect(entropy_client):

    mytxt = "####### %s: %s" % (
        bold(_("ATTENTION")),
        red(_("The installed package database will be resurrected, this will take a LOT of time.")),
    )
    print_warning(mytxt)
    mytxt = "####### %s: %s" % (
        bold(_("ATTENTION")),
        red(_("Please use this function ONLY if you are using an Entropy-aware distribution.")),
    )
    print_warning(mytxt)
    rc = entropy_client.ask_question("     %s" % (
        _("Can I continue ?"),) )
    if rc == _("No"):
        return 0
    rc = entropy_client.ask_question("     %s" % (
        _("Are you REALLY sure ?"),) )
    if rc == _("No"):
        return 0
    rc = entropy_client.ask_question("     %s" % (
        _("Do you even know what you're doing ?"),) )
    if rc == _("No"):
        return 0

    # clean caches
    entropy_client.clear_cache()

    # ok, he/she knows it... hopefully
    # if exist, copy old database
    print_info(red(" @@ ") + \
        blue(_("Creating backup of the previous database, if exists.")))
    newfile = _backup_client_repository()
    if newfile is not None:
        print_info(red(" @@ ") + \
            blue(_("Previous database copied to file"))+" "+newfile)

    # Now reinitialize it
    mytxt = "  %s %s" % (
        darkred(_("Initializing the new database at")),
        bold(etpConst['etpdatabaseclientfilepath']),
    )
    print_info(mytxt, back = True)
    dbpath = etpConst['etpdatabaseclientfilepath']
    if os.path.isfile(dbpath) and os.access(dbpath, os.W_OK):
        os.remove(dbpath)
    dbc = entropy_client.open_generic_repository(dbpath,
        dbname = etpConst['clientdbid']) # don't do this at home
    dbc.initializeDatabase()
    dbc.commitChanges()
    entropy_client._installed_repository = dbc
    mytxt = "  %s %s" % (
        darkgreen(_("Database reinitialized correctly at")),
        bold(etpConst['etpdatabaseclientfilepath']),
    )
    print_info(mytxt)

    mytxt = red("  %s. %s. %s ...") % (
        _("Collecting installed files"),
        _("Writing to temporary file"),
        _("Please wait"),
    )
    print_info(mytxt, back = True)

    # since we use find, see if it's installed
    find = os.system("which find &> /dev/null")
    if find != 0:
        mytxt = "%s: %s!" % (
            darkred(_("Attention")),
            red(_("You must have 'find' installed")),
        )
        print_error(mytxt)
        return
    # spawn process
    rnd_num = entropy.tools.get_random_number()
    tmpfile = os.path.join(etpConst['packagestmpdir'], "%s" % (rnd_num,))
    if os.path.isfile(tmpfile):
        os.remove(tmpfile)
    os.system("find "+etpConst['systemroot']+"/ -mount 1> "+tmpfile)
    if not os.path.isfile(tmpfile):
        mytxt = "%s: %s!" % (
            darkred(_("Attention")),
            red(_("'find' couldn't generate an output file")),
        )
        print_error(mytxt)
        return

    f = open(tmpfile, "r")
    # creating list of files
    filelist = set()
    item = f.readline().strip()
    while item:
        filelist.add(item)
        item = f.readline().strip()
    f.close()
    entries = len(filelist)

    mytxt = red("  %s...") % (
        _("Found %s files on the system. Assigning packages" % (entries,) ),)
    print_info(mytxt)
    atoms = {}
    pkgsfound = set()

    repos_data = entropy_client.SystemSettings['repositories']

    for repo in repos_data['order']:
        mytxt = red("  %s: %s") % (_("Matching in repository"),
            repos_data['available'][repo]['description'],)
        print_info(mytxt)
        # get all idpackages
        dbconn = entropy_client.open_repository(repo)
        idpackages = dbconn.listAllIdpackages()
        count = str(len(idpackages))
        cnt = 0
        for idpackage in idpackages:
            cnt += 1
            idpackageatom = dbconn.retrieveAtom(idpackage)
            mytxt = "  (%s/%s) %s ..." % (
                cnt,
                count,
                red(_("Matching files from packages")),
            )
            print_info(mytxt, back = True)
            # content
            content = dbconn.retrieveContent(idpackage)
            for item in content:
                if etpConst['systemroot']+item in filelist:
                    pkgsfound.add((idpackage, repo))
                    atoms[(idpackage, repo)] = idpackageatom
                    filelist.difference_update(
                        set([etpConst['systemroot']+x for x in content]))
                    break

    mytxt = red("  %s. %s...") % (
        _("Found %s packages") % (bold(str(len(pkgsfound))),),
        _("Filling database"),
    )
    print_info(mytxt)
    count = str(len(pkgsfound))
    cnt = 0
    os.remove(tmpfile)

    for pkgfound in pkgsfound:
        cnt += 1
        print_info("  ("+str(cnt)+"/"+count+") "+red(
            "%s: " % (_("Adding"),))+atoms[pkgfound], back = True)
        etp_pkg = entropy_client.Package()
        etp_pkg.prepare(tuple(pkgfound), "install", {})
        etp_pkg.add_installed_package()
        etp_pkg.kill()
        del etp_pkg


    print_info(red("  %s." % (_("Database resurrected successfully"),)))

    print_info(red("  %s..." % (_("Now generating reverse dependencies metadata"),)))
    entropy_client.installed_repository().generateReverseDependenciesMetadata()
    print_info(red("  %s..." % (_("Now indexing tables"),)))
    entropy_client.installed_repository().indexing = True
    entropy_client.installed_repository().createAllIndexes()
    print_info(red("  %s." % (_("Database reinitialized successfully"),)))

    print_warning(red("  %s" % (_("Keep in mind that virtual packages couldn't be matched. They don't own any files."),) ))
    return 0

def _database_spmsync(entropy_client):

    Spm = test_spm(entropy_client)
    if Spm is None:
        return 1

    rc = test_clientdb(entropy_client)
    if rc is not None:
        return rc

    print_info(red(" %s..." % (
        _("Scanning Source Package Manager and Entropy databases for differences"),)))

    # make it crash
    entropy_client.noclientdb = False
    entropy_client.reopen_installed_repository()
    entropy_client.close_repositories()

    print_info(red(" %s..." % (
        _("Collecting Source Package Manager metadata"),) ), back = True)
    spm_packages = Spm.get_installed_packages()
    installed_packages = []
    for spm_package in spm_packages:
        try:
            pkg_counter = Spm.get_installed_package_metadata(spm_package,
                "COUNTER")
        except KeyError:
            continue
        try:
            pkg_counter = int(pkg_counter)
        except ValueError:
            continue
        installed_packages.append((spm_package, pkg_counter,))

    print_info(red(" %s..." % (
        _("Collecting Entropy packages"),) ), back = True)
    installed_spm_uids = set()
    to_be_added = set()
    to_be_removed = set()

    print_info(red(" %s..." % (_("Differential Scan"),)), back = True)
    # packages to be added/updated (handle add/update later)
    for x in installed_packages:
        installed_spm_uids.add(x[1])
        counter = entropy_client.installed_repository().isSpmUidAvailable(x[1])
        if (not counter):
            to_be_added.add(tuple(x))

    # packages to be removed from the database
    repo_spm_uids = entropy_client.installed_repository().listAllSpmUids()
    for x in repo_spm_uids:
        if x[0] < 0: # skip packages without valid counter
            continue
        if x[0] not in installed_spm_uids:
            # check if the package is in to_be_added
            if (to_be_added):
                atom = entropy_client.installed_repository().retrieveAtom(x[1])
                add = True
                if atom:
                    atomkey = entropy.tools.dep_getkey(atom)
                    atomslot = entropy_client.installed_repository().retrieveSlot(x[1])
                    add = True
                    for pkgdata in to_be_added:
                        try:
                            addslot = Spm.get_installed_package_metadata(
                                pkgdata[0], "SLOT")
                        except KeyError:
                            continue
                        addkey = entropy.tools.dep_getkey(pkgdata[0])
                        # workaround for ebuilds not having slot
                        if addslot is None:
                            addslot = '0'
                        if (atomkey == addkey) and (str(atomslot) == str(addslot)):
                            # do not add to to_be_removed
                            add = False
                            break
                if add:
                    to_be_removed.add(x[1])
            else:
                to_be_removed.add(x[1])

    if (not to_be_removed) and (not to_be_added):
        print_info(red(" %s." % (_("Databases already synced"),)))
        # then exit gracefully
        return 0

    # check lock file
    gave_up = entropy_client.wait_resources()
    if gave_up:
        print_info(red(" %s." % (_("Entropy locked, giving up"),)))
        return 2

    rc = entropy_client.ask_question(_("Are you ready ?"))
    if rc == _("No"):
        return 0

    acquired = entropy_client.lock_resources()
    if not acquired:
        print_info(red(" %s." % (_("Entropy locked during lock acquire"),)))
        return 2

    if to_be_removed:
        mytxt = blue("%s. %s:") % (
            _("Someone removed these packages"),
            _("They would be removed from the system database"),
        )
        print_info(brown(" @@ ")+mytxt)

        broken = set()
        for x in to_be_removed:
            atom = entropy_client.installed_repository().retrieveAtom(x)
            if not atom:
                broken.add(x)
                continue
            print_info(brown("    # ")+red(atom))
        to_be_removed -= broken
        if to_be_removed:
            rc = _("Yes")
            if etpUi['ask']:
                rc = entropy_client.ask_question(">>   %s" % (
                    _("Continue with removal ?"),))
            if rc == _("Yes"):
                queue = 0
                totalqueue = str(len(to_be_removed))
                for x in to_be_removed:
                    queue += 1
                    atom = entropy_client.installed_repository().retrieveAtom(x)
                    mytxt = " %s (%s/%s) %s %s %s" % (
                        red("--"),
                        blue(str(queue)),
                        red(totalqueue),
                        brown(">>>"),
                        _("Removing"),
                        darkgreen(atom),
                    )
                    print_info(mytxt)
                    entropy_client.installed_repository().removePackage(x)
                print_info(brown(" @@ ") + \
                    blue("%s." % (_("Database removal complete"),) ))

    if to_be_added:
        mytxt = blue("%s. %s:") % (
            _("Someone added these packages"),
            _("They would be added to the system database"),
        )
        print_info(brown(" @@ ")+mytxt)
        for x in to_be_added:
            print_info(darkgreen("   # ")+red(x[0]))
        rc = _("Yes")
        if etpUi['ask']:
            rc = entropy_client.ask_question(">>   %s" % (
                _("Continue with adding ?"),) )
        if rc == _("No"):
            entropy_client.unlock_resources()
            return 0
        # now analyze

        totalqueue = str(len(to_be_added))
        queue = 0
        for atom, counter in to_be_added:
            queue += 1
            mytxt = " %s (%s/%s) %s %s %s" % (
                red("++"),
                blue(str(queue)),
                red(totalqueue),
                brown(">>>"),
                _("Adding"),
                darkgreen(atom),
            )
            print_info(mytxt)

            tmp_fd, temp_pkg_path = tempfile.mkstemp()
            os.close(tmp_fd)
            xpaktools.append_xpak(temp_pkg_path, atom)
            # now extract info
            try:
                mydata = Spm.extract_package_metadata(temp_pkg_path)
            except Exception as err:
                entropy.tools.print_traceback()
                entropy_client.clientLog.log(
                    "[spm sync]",
                    etpConst['logging']['normal_loglevel_id'],
                    "Database spmsync: Exception caught: %s" % (
                        str(err),
                    )
                )
                print_warning(red("!!! %s: " % (
                    _("An error occured while analyzing")) ) + blue(atom))
                print_warning("%s: %s" % (_("Exception"), str(err),))
                continue

            # create atom string
            myatom = entropy.tools.create_package_atom_string(mydata['category'],
                mydata['name'], mydata['version'], mydata['versiontag'])

            # look for atom in client database
            idpkgs = entropy_client.installed_repository().getIdpackages(myatom)
            oldidpackages = sorted(idpkgs)
            oldidpackage = None
            if oldidpackages:
                oldidpackage = oldidpackages[-1]

            mydata['revision'] = 9999 # can't do much more
            if oldidpackage:
                mydata['revision'] = \
                    entropy_client.installed_repository().retrieveRevision(oldidpackage)

            idpk, rev, xx = entropy_client.installed_repository().handlePackage(mydata,
                forcedRevision = mydata['revision'])
            entropy_client.installed_repository().dropInstalledPackageFromStore(idpk)
            entropy_client.installed_repository().storeInstalledPackage(idpk, "spm-db")
            os.remove(temp_pkg_path)

        print_info(brown(" @@ ") + \
            blue("%s." % (_("Database update completed"),)))

    entropy_client.unlock_resources()
    return 0

def _database_generate(entropy_client):

    Spm = test_spm(entropy_client)
    if Spm is None:
        return 1

    mytxt = "%s: %s."  % (
        bold(_("ATTENTION")),
        red(_("The installed package repository will be regenerated using Source Package Manager")),
    )
    print_warning(mytxt)
    print_warning(red(_("If you dont know what you're doing just, don't do this. Really. I'm not joking.")))
    rc = entropy_client.ask_question("  %s" % (_("Understood ?"),))
    if rc == _("No"):
        return 0
    rc = entropy_client.ask_question("  %s" % (_("Really ?"),) )
    if rc == _("No"):
        return 0
    rc = entropy_client.ask_question("  %s. %s" % (
        _("This is your last chance"), _("Ok?"),) )
    if rc == _("No"):
        return 0

    # clean caches
    entropy_client.clear_cache()

    # try to collect current installed revisions if possible
    revisions_match = {}
    try:
        myids = entropy_client.installed_repository().listAllIdpackages()
        for myid in myids:
            myatom = entropy_client.installed_repository().retrieveAtom(myid)
            myrevision = entropy_client.installed_repository().retrieveRevision(myid)
            revisions_match[myatom] = myrevision
    except:
        pass

    # ok, he/she knows it... hopefully
    # if exist, copy old database
    print_info(red(" @@ ") + \
        blue(_("Creating backup of the previous database, if exists.")) + \
        red(" @@"))
    newfile = _backup_client_repository()
    if newfile is not None:
        print_info(red(" @@ ") + blue(_("Previous database copied to file")) + \
            " " + newfile+red(" @@"))

    # Now reinitialize it
    mytxt = darkred("  %s %s") % (
        _("Initializing the new database at"),
        bold(etpConst['etpdatabaseclientfilepath']),
    )
    print_info(mytxt, back = True)
    entropy_client.reopen_installed_repository()
    dbfile = entropy_client.installed_repository().dbFile
    entropy_client.installed_repository().closeDB()
    if os.path.isfile(dbfile):
        os.remove(dbfile)
    entropy_client._open_installed_repository()
    entropy_client.installed_repository().initializeDatabase()
    mytxt = darkred("  %s %s") % (
        _("Database reinitialized correctly at"),
        bold(etpConst['etpdatabaseclientfilepath']),
    )
    print_info(mytxt)

    # now collect packages in the system
    print_info(red("  %s..." % (
        _("Transductingactioningintactering databases"),) ))

    spm_packages = Spm.get_installed_packages()

    # do for each database
    maxcount = str(len(spm_packages))
    count = 0
    for spm_package in spm_packages:
        count += 1
        print_info(blue("(") + darkgreen(str(count)) + "/" + \
            darkred(maxcount) + blue(")") + red(" :: ") + brown(spm_package),
            back = True)

        tmp_fd, temp_pkg_path = tempfile.mkstemp()
        os.close(tmp_fd)

        xpaktools.append_xpak(temp_pkg_path, spm_package)
        # now extract info
        try:
            mydata = Spm.extract_package_metadata(temp_pkg_path)
        except Exception as err:
            entropy.tools.print_traceback()
            entropy_client.clientLog.log(
                "[spm sync]",
                etpConst['logging']['normal_loglevel_id'],
                "Database generation: Exception caught: %s" % (str(err),)
            )
            print_warning( red("!!! %s: %s") % (
                _("An error occured while analyzing"), blue(spm_package),) )
            print_warning("%s: %s: %s" % (
                _("Exception"), str(Exception), err,))
            continue

        # Try to see if it's possible to use the revision of a possible old db
        mydata['revision'] = 9999
        # create atom string
        myatom = entropy.tools.create_package_atom_string(mydata['category'],
            mydata['name'], mydata['version'], mydata['versiontag'])

        # now see if a revision is available
        saved_rev = revisions_match.get(myatom)
        if saved_rev is not None:
            saved_rev = saved_rev
            mydata['revision'] = saved_rev

        idpk, rev, xx = entropy_client.installed_repository().addPackage(mydata,
            revision = mydata['revision'], do_commit = False)
        entropy_client.installed_repository().storeInstalledPackage(idpk, "spm-db")
        os.remove(temp_pkg_path)

    print_info(red("  %s." % (_("All the Source Package Manager packages have been injected into Entropy database"),) ))

    print_info(red("  %s..." % (
        _("Now generating reverse dependencies metadata"),) ))
    entropy_client.installed_repository().generateReverseDependenciesMetadata()
    print_info(red("  %s...") % (_("Now indexing tables"),) )
    entropy_client.installed_repository().indexing = True
    entropy_client.installed_repository().createAllIndexes()
    print_info(red("  %s." % (_("Database reinitialized successfully"),) ))
    return 0

def _database_check(entropy_client):

    def client_repository_sanity_check():
        entropy_client.output(
            darkred(_("Sanity Check") + ": " + _("system database")),
            importance = 2,
            type = "warning"
        )
        idpkgs = entropy_client.installed_repository().listAllIdpackages()
        length = len(idpkgs)
        count = 0
        errors = False
        scanning_txt = _("Scanning...")
        for x in idpkgs:
            count += 1
            entropy_client.output(
                darkgreen(scanning_txt),
                importance = 0,
                type = "info",
                back = True,
                count = (count, length),
                percent = True
            )
            try:
                entropy_client.installed_repository().getPackageData(x)
            except Exception as e:
                entropy.tools.print_traceback()
                errors = True
                entropy_client.output(
                    darkred(_("Errors on idpackage %s, error: %s")) % (x, e),
                    importance = 0,
                    type = "warning"
                )

        if not errors:
            t = _("Sanity Check") + ": %s" % (bold(_("PASSED")),)
            entropy_client.output(
                darkred(t),
                importance = 2,
                type = "warning"
            )
            return 0
        else:
            t = _("Sanity Check") + ": %s" % (bold(_("CORRUPTED")),)
            entropy_client.output(
                darkred(t),
                importance = 2,
                type = "warning"
            )
            return -1

    try:
        valid = True
        entropy_client.installed_repository().validateDatabase()
    except SystemDatabaseError:
        valid = False
    if valid:
        client_repository_sanity_check()
    else:
        mytxt = "# %s: %s" % (bold(_("ATTENTION")),
            red(_("database does not exist or is badly broken")),)
        print_warning(mytxt)
        return 1
    return 0

def _getinfo(entropy_client):

    # sysinfo
    info = {}
    osinfo = os.uname()
    info['OS'] = osinfo[0]
    info['Kernel'] = osinfo[2]
    info['Architecture'] = osinfo[4]
    info['Entropy version'] = etpConst['entropyversion']

    from entropy.core.settings.base import SystemSettings
    SysSettings = SystemSettings()
    sys_set_client_plg_id = \
        etpConst['system_settings_plugins_ids']['client_plugin']
    # variables
    info['User protected directories'] = SysSettings[sys_set_client_plg_id]['misc']['configprotect']
    info['Collision Protection'] = SysSettings[sys_set_client_plg_id]['misc']['collisionprotect']
    info['Entropy Log Level'] = SysSettings['system']['log_level']
    info['Current branch'] = SysSettings['repositories']['branch']
    info['Entropy configuration directory'] = etpConst['confdir']
    info['Entropy work directory'] = etpConst['entropyworkdir']
    info['Entropy unpack directory'] = etpConst['entropyunpackdir']
    info['Entropy logging directory'] = etpConst['logdir']
    info['Entropy Official Repository identifier'] = SysSettings['repositories']['default_repository']
    info['Entropy API'] = etpConst['etpapi']
    info['Entropy pidfile'] = etpConst['pidfile']
    info['Entropy database tag'] = etpConst['databasestarttag']
    info['Repositories'] = SysSettings['repositories']['available']
    info['System Config'] = etpSys
    info['UI Config'] = etpUi

    # client database info
    cdbconn = entropy_client.installed_repository()
    info['Installed database'] = cdbconn
    if cdbconn is not None:
        # print db info
        info['Removal internal protected directories'] = cdbconn.listConfigProtectEntries()
        info['Removal internal protected directory masks'] = cdbconn.listConfigProtectEntries(mask = True)
        info['Total installed packages'] = len(cdbconn.listAllIdpackages())

    # repository databases info (if found on the system)
    info['Repository databases'] = {}
    for x in SysSettings['repositories']['order']:
        dbfile = SysSettings['repositories']['available'][x]['dbpath']+"/"+etpConst['etpdatabasefile']
        if os.path.isfile(dbfile):
            # print info about this database
            dbconn = entropy_client.open_repository(x)
            info['Repository databases'][x] = {}
            info['Repository databases'][x]['Installation internal protected directories'] = dbconn.listConfigProtectEntries()
            info['Repository databases'][x]['Installation internal protected directory masks'] = dbconn.listConfigProtectEntries(mask = True)
            info['Repository databases'][x]['Total available packages'] = len(dbconn.listAllIdpackages())
            info['Repository databases'][x]['Database revision'] = entropy_client.get_repository_revision(x)

    keys = sorted(info)
    for x in keys:
        #print type(info[x])
        if isinstance(info[x], dict):
            toptext = x
            ykeys = sorted(info[x].keys())
            for y in ykeys:
                if isinstance(info[x][y], dict):
                    topsubtext = y
                    zkeys = sorted(info[x][y].keys())
                    for z in zkeys:
                        sys.stdout.write(red(toptext) + ": " + \
                            blue(topsubtext) + " => " + darkgreen(z) + \
                            " => " + str(info[x][y][z]) + "\n")
                else:
                    sys.stdout.write(red(toptext) + ": "+blue(y) + " => " + \
                        str(info[x][y]) + "\n")
        else:
            sys.stdout.write(red(x) + ": " + str(info[x]) + "\n")
