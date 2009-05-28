#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo integrity handling library

    Copyright (C) 2007-2009 Fabio Erculiani

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

########################################################
####
##   Repositories Tools
#

from entropy.const import *
from entropy.output import *
from entropy.client.interfaces import Client
from entropy.exceptions import *
Equo = Client(noclientdb = True)
from entropy.i18n import _

def test_spm():
    # test if portage is available
    try:
        Spm = Equo.Spm()
        return Spm
    except Exception, e:
        Equo.entropyTools.print_traceback()
        mytxt = _("Source Package Manager backend not available")
        print_error(darkred(" * ")+red("%s: %s" % (mytxt,e,)))
        return None

def test_clientdb():
    try:
        Equo.clientDbconn.validateDatabase()
    except SystemDatabaseError:
        mytxt = _("Installed packages database not available")
        print_error(darkred(" * ")+red("%s !" % (mytxt,)))
        return 1

def database(options):

    if len(options) < 1:
        return -10

    # check if I am root
    if (not Equo.entropyTools.is_root()):
        mytxt = _("You are not root")
        print_error(red(mytxt+"."))
        return 1

    if (options[0] == "generate"):

        Spm = test_spm()
        if Spm == None:
            return 1

        mytxt = "%s: %s."  % (
            bold(_("ATTENTION")),
            red(_("The installed package database will be generated again using Gentoo one")),
        )
        print_warning(mytxt)
        print_warning(red(_("If you dont know what you're doing just, don't do this. Really. I'm not joking.")))
        rc = Equo.askQuestion("  %s" % (_("Understood ?"),))
        if rc == "No":
            return 0
        rc = Equo.askQuestion("  %s" % (_("Really ?"),) )
        if rc == "No":
            return 0
        rc = Equo.askQuestion("  %s. %s" % (_("This is your last chance"),_("Ok?"),) )
        if rc == "No":
            return 0

        # clean caches
        Equo.purge_cache()
        import shutil

        # try to collect current installed revisions if possible
        revisionsMatch = {}
        try:
            myids = Equo.clientDbconn.listAllIdpackages()
            for myid in myids:
                myatom = Equo.clientDbconn.retrieveAtom(myid)
                myrevision = Equo.clientDbconn.retrieveRevision(myid)
                revisionsMatch[myatom] = myrevision
        except:
            pass

        # ok, he/she knows it... hopefully
        # if exist, copy old database
        print_info(red(" @@ ")+blue(_("Creating backup of the previous database, if exists."))+red(" @@"))
        newfile = Equo.entropyTools.backup_client_repository()
        if (newfile):
            print_info(red(" @@ ")+blue(_("Previous database copied to file"))+" "+newfile+red(" @@"))

        # Now reinitialize it
        mytxt = darkred("  %s %s") % (_("Initializing the new database at"),bold(etpConst['etpdatabaseclientfilepath']),)
        print_info(mytxt, back = True)
        Equo.reopen_client_repository()
        dbfile = Equo.clientDbconn.dbFile
        Equo.clientDbconn.closeDB()
        if os.path.isfile(dbfile):
            os.remove(dbfile)
        Equo.open_client_repository()
        Equo.clientDbconn.initializeDatabase()
        mytxt = darkred("  %s %s") % (_("Database reinitialized correctly at"),bold(etpConst['etpdatabaseclientfilepath']),)
        print_info(mytxt)

        # now collect packages in the system
        print_info(red("  %s..." % (_("Transductingactioningintactering databases"),) ))

        portagePackages = Spm.get_installed_packages()
        portagePackages = portagePackages[0]

        Spm = Equo.Spm()

        # do for each database
        maxcount = str(len(portagePackages))
        count = 0
        for portagePackage in portagePackages:
            count += 1
            print_info(blue("(")+darkgreen(str(count))+"/"+darkred(maxcount)+blue(")")+red(" atom: ")+brown(portagePackage), back = True)
            temptbz2 = etpConst['entropyunpackdir']+"/"+portagePackage.split("/")[1]+".tbz2"
            if not os.path.isdir(etpConst['entropyunpackdir']):
                os.makedirs(etpConst['entropyunpackdir'])
            if os.path.isfile(temptbz2):
                os.remove(temptbz2)
            elif os.path.isdir(temptbz2):
                shutil.rmtree(temptbz2)
            f = open(temptbz2,"wb")
            f.flush()
            f.close()
            Equo.entropyTools.append_xpak(temptbz2,portagePackage)
            # now extract info
            try:
                mydata = Spm.extract_pkg_metadata(temptbz2, silent = True)
            except Exception, e:
                Equo.entropyTools.print_traceback()
                Equo.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "Database generation: Exception caught: %s: %s" % (str(Exception),str(e),)
                )
                print_warning( red("!!! %s: %s") % (_("An error occured while analyzing"),blue(portagePackage),) )
                print_warning("%s: %s: %s" % (_("Exception"),str(Exception),e,))
                continue

            # Try to see if it's possible to use the revision of a possible old db
            mydata['revision'] = 9999
            # create atom string
            myatom = mydata['category']+"/"+mydata['name']+"-"+mydata['version']
            if mydata['versiontag']:
                myatom += "#"+mydata['versiontag']
            # now see if a revision is available
            savedRevision = revisionsMatch.get(myatom)
            if savedRevision != None:
                try:
                    savedRevision = int(savedRevision) # cast to int for security
                    mydata['revision'] = savedRevision
                except:
                    pass

            idpk, rev, xx = Equo.clientDbconn.addPackage(etpData = mydata, revision = mydata['revision'])
            Equo.clientDbconn.addPackageToInstalledTable(idpk,"gentoo-db")
            os.remove(temptbz2)

        print_info(red("  %s." % (_("All the Gentoo packages have been injected into Entropy database"),) ))
        print_info(red("  %s..." % (_("Now checking dependency atoms validity"),) ))
        mydeps = Equo.clientDbconn.listAllDependencies()
        maxcount = str(len(mydeps))
        count = 0
        for depdata in mydeps:
            count += 1
            atom = depdata[1]
            iddependency = depdata[0]
            print_info(blue("(")+darkgreen(str(count))+"/"+darkred(maxcount)+blue(")")+red(" %s: " % (_("atom"),) )+brown(atom), back = True)
            try:
                Equo.clientDbconn.atomMatch(atom)
            except Exception, e:
                Equo.entropyTools.print_traceback()
                Equo.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "Database dependency atoms check: Exception caught: %s: %s" % (
                        str(Exception),
                        str(e),
                    )
                )
                print_warning(red("!!! %s: " % (_("An error occured while analyzing"),) )+blue(atom)+" - "+red(_("entry can be invalid!")))
                print_warning("%s: %s: %s" % (_("Exception"),str(Exception),str(e),))
                found_idpackages = Equo.clientDbconn.searchIdpackageFromIddependency(iddependency)
                if found_idpackages:
                    print_warning(red("%s:" % (_("These are the invalid entries"),) ))
                    for myidpackage in found_idpackages:
                        myatom = Equo.clientDbconn.retrieveAtom(myidpackage)
                        print_warning(darkred("   # ")+blue(myatom))
                    print_warning(red("%s..." % (_("Removing database information"),) ))
                    for myidpackage in found_idpackages:
                        Equo.clientDbconn.removePackage(myidpackage)

        print_info(red("  %s..." % (_("Now generating depends caching table"),) ))
        Equo.clientDbconn.regenerateDependsTable()
        print_info(red("  %s...") % (_("Now indexing tables"),) )
        Equo.clientDbconn.indexing = True
        Equo.clientDbconn.createAllIndexes()
        print_info(red("  %s." % (_("Database reinitialized successfully"),) ))
        return 0

    elif (options[0] == "check"):
        if Equo.clientDbconn.doesTableExist("baseinfo"):
            Equo.client_repository_sanity_check()
        else:
            mytxt = "# %s: %s" % (bold(_("ATTENTION")),red(_("database does not exist or is badly broken")),)
            print_warning(mytxt)
            return 1
        return 0

    elif (options[0] == "resurrect"):

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
        rc = Equo.askQuestion("     %s" % (_("Can I continue ?"),) )
        if rc == "No":
            return 0
        rc = Equo.askQuestion("     %s" % (_("Are you REALLY sure ?"),) )
        if rc == "No":
            return 0
        rc = Equo.askQuestion("     %s" % (_("Do you even know what you're doing ?"),) )
        if rc == "No":
            return 0

        # clean caches
        Equo.purge_cache()

        # ok, he/she knows it... hopefully
        # if exist, copy old database
        print_info(red(" @@ ")+blue(_("Creating backup of the previous database, if exists.")))
        newfile = Equo.entropyTools.backup_client_repository()
        if (newfile):
            print_info(red(" @@ ")+blue(_("Previous database copied to file"))+" "+newfile)

        # Now reinitialize it
        mytxt = "  %s %s" % (
            darkred(_("Initializing the new database at")),
            bold(etpConst['etpdatabaseclientfilepath']),
        )
        print_info(mytxt, back = True)
        dbpath = etpConst['etpdatabaseclientfilepath']
        if os.path.isfile(dbpath) and os.access(dbpath,os.W_OK):
            os.remove(dbpath)
        dbc = Equo.open_generic_database(dbpath, dbname = etpConst['clientdbid']) # don't do this at home
        dbc.initializeDatabase()
        dbc.commitChanges()
        Equo.clientDbconn = dbc
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
        rnd_num = Equo.entropyTools.get_random_number()
        tmpfile = os.path.join(etpConst['packagestmpdir'],"%s" % (rnd_num,))
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

        f = open(tmpfile,"r")
        # creating list of files
        filelist = set()
        item = f.readline().strip()
        while item:
            filelist.add(item)
            item = f.readline().strip()
        f.close()
        entries = len(filelist)

        mytxt = red("  %s...") % (_("Found %s files on the system. Assigning packages" % (entries,) ),)
        print_info(mytxt)
        atoms = {}
        pkgsfound = set()

        for repo in Equo.SystemSettings['repositories']['order']:
            mytxt = red("  %s: %s") % (_("Matching in repository"),Equo.SystemSettings['repositories']['available'][repo]['description'],)
            print_info(mytxt)
            # get all idpackages
            dbconn = Equo.open_repository(repo)
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
                        pkgsfound.add((idpackage,repo))
                        atoms[(idpackage,repo)] = idpackageatom
                        filelist.difference_update(set([etpConst['systemroot']+x for x in content]))
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
            print_info("  ("+str(cnt)+"/"+count+") "+red("%s: " % (_("Adding"),))+atoms[pkgfound], back = True)
            Package = Equo.Package()
            Package.prepare(tuple(pkgfound),"install", {})
            Package._install_package_into_database()
            Package.kill()
            del Package


        print_info(red("  %s." % (_("Database resurrected successfully"),)))

        print_info(red("  %s..." % (_("Now generating depends caching table"),)))
        Equo.clientDbconn.regenerateDependsTable()
        print_info(red("  %s..." % (_("Now indexing tables"),)))
        Equo.clientDbconn.indexing = True
        Equo.clientDbconn.createAllIndexes()
        print_info(red("  %s." % (_("Database reinitialized successfully"),)))

	print_warning(red("  %s" % (_("Keep in mind that virtual/meta packages couldn't be matched. They don't own any files."),) ))
        return 0

    elif (options[0] == "depends"):

        rc = test_clientdb()
        if rc != None:
            return rc

        print_info(red("  %s..." % (_("Regenerating depends caching table"),) ))
        Equo.clientDbconn.regenerateDependsTable()
        print_info(red("  %s." % (_("Depends caching table regenerated successfully"),) ))
        return 0

    elif (options[0] == "counters"):

        Spm = test_spm()
        if Spm == None:
            return 1

        rc = test_clientdb()
        if rc != None:
            return rc

        print_info(red("  %s..." % (_("Regenerating counters table"),) ))
        Equo.clientDbconn.regenerateCountersTable(Spm.get_vdb_path(), output = True)
        print_info(red("  %s" % (_("Counters table regenerated. Look above for errors."),) ))
        return 0

    elif (options[0] == "gentoosync"):

        Spm = test_spm()
        if Spm == None:
            return 1

        rc = test_clientdb()
        if rc != None:
            return rc

        print_info(red(" %s..." % (_("Scanning Portage and Entropy databases for differences"),)))

        # make it crash
        Equo.noclientdb = False
        Equo.reopen_client_repository()
        Equo.close_all_repositories()

        # test if counters table exists, because if not, it's useless to run the diff scan
        try:
            Equo.clientDbconn.isCounterAvailable(1)
        except:
            mytxt = "%s %s: %s %s." % (
                bold(_("Entropy database")),
                red(_("has never been in sync with Portage. So, you can't run this unless you run first")),
                bold("equo database generate"),
                red(_("Sorry")),
            )
            print_error(darkred(" * ")+mytxt)
            return 1

        import shutil
        print_info(red(" %s..." % (_("Collecting Portage counters"),) ), back = True)
        installed_packages = Spm.get_installed_packages_counter()
        print_info(red(" %s..." % (_("Collecting Entropy packages"),) ), back = True)
        installedCounters = set()
        toBeAdded = set()
        toBeRemoved = set()

        print_info(red(" %s..." % (_("Differential Scan"),)), back = True)
        # packages to be added/updated (handle add/update later)
        for x in installed_packages:
            installedCounters.add(x[1])
            counter = Equo.clientDbconn.isCounterAvailable(x[1])
            if (not counter):
                toBeAdded.add(tuple(x))

        # packages to be removed from the database
        databaseCounters = Equo.clientDbconn.listAllCounters()
        for x in databaseCounters:
            if x[0] < 0: # skip packages without valid counter
                continue
            if x[0] not in installedCounters:
                # check if the package is in toBeAdded
                if (toBeAdded):
                    atom = Equo.clientDbconn.retrieveAtom(x[1])
                    add = True
                    if atom:
                        atomkey = Equo.entropyTools.dep_getkey(atom)
                        atomslot = Equo.clientDbconn.retrieveSlot(x[1])
                        add = True
                        for pkgdata in toBeAdded:
                            try:
                                addslot = Spm.get_installed_package_slot(pkgdata[0])
                            except KeyError:
                                continue
                            addkey = Equo.entropyTools.dep_getkey(pkgdata[0])
                            # workaround for ebuilds not having slot
                            if addslot == None:
                                addslot = '0'
                            if (atomkey == addkey) and (str(atomslot) == str(addslot)):
                                # do not add to toBeRemoved
                                add = False
                                break
                    if add:
                        toBeRemoved.add(x[1])
                else:
                    toBeRemoved.add(x[1])

        if (not toBeRemoved) and (not toBeAdded):
            print_info(red(" %s." % (_("Databases already synced"),)))
            # then exit gracefully
            return 0

        # check lock file
        gave_up = Equo.lock_check(Equo.resources_check_lock)
        if gave_up:
            print_info(red(" %s." % (_("Entropy locked, giving up"),)))
            return 2

        rc = Equo.askQuestion(_("Are you ready ?"))
        if rc == "No":
            return 0

        Equo.resources_create_lock()

        if toBeRemoved:
            mytxt = blue("%s. %s:") % (
                _("Someone removed these packages"),
                _("They would be removed from the system database"),
            )
            print_info(brown(" @@ ")+mytxt)

            broken = set()
            for x in toBeRemoved:
                atom = Equo.clientDbconn.retrieveAtom(x)
                if not atom:
                    broken.add(x)
                    continue
                print_info(brown("    # ")+red(atom))
            toBeRemoved -= broken
            if toBeRemoved:
                rc = "Yes"
                if etpUi['ask']: rc = Equo.askQuestion(">>   %s" % (_("Continue with removal ?"),))
                if rc == "Yes":
                    queue = 0
                    totalqueue = str(len(toBeRemoved))
                    for x in toBeRemoved:
                        queue += 1
                        atom = Equo.clientDbconn.retrieveAtom(x)
                        mytxt = " %s (%s/%s) %s %s %s" % (
                            red("--"),
                            blue(str(queue)),
                            red(totalqueue),
                            brown(">>>"),
                            _("Removing"),
                            darkgreen(atom),
                        )
                        print_info(mytxt)
                        Equo.clientDbconn.removePackage(x)
                    print_info(brown(" @@ ")+blue("%s." % (_("Database removal complete"),) ))

        if toBeAdded:
            mytxt = blue("%s. %s:") % (
                _("Someone added these packages"),
                _("They would be added to the system database"),
            )
            print_info(brown(" @@ ")+mytxt)
            for x in toBeAdded:
                print_info(darkgreen("   # ")+red(x[0]))
            rc = "Yes"
            if etpUi['ask']: rc = Equo.askQuestion(">>   %s" % (_("Continue with adding ?"),) )
            if rc == "No":
                Equo.resources_remove_lock()
                return 0
            # now analyze

            totalqueue = str(len(toBeAdded))
            queue = 0
            for atom,counter in toBeAdded:
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
                if not os.path.isdir(etpConst['entropyunpackdir']):
                    os.makedirs(etpConst['entropyunpackdir'])
                temptbz2 = etpConst['entropyunpackdir']+"/"+atom.split("/")[1]+".tbz2"
                if os.path.isfile(temptbz2):
                    os.remove(temptbz2)
                elif os.path.isdir(temptbz2):
                    shutil.rmtree(temptbz2)
                f = open(temptbz2,"wb")
                f.flush()
                f.close()
                Equo.entropyTools.append_xpak(temptbz2,atom)
                # now extract info
                try:
                    mydata = Spm.extract_pkg_metadata(temptbz2, silent = True)
                except Exception, e:
                    Equo.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "Database gentoosync: Exception caught: %s: %s" % (
                            str(Exception),
                            str(e),
                        )
                    )
                    print_warning(red("!!! %s: " % (_("An error occured while analyzing")) )+blue(atom))
                    print_warning("%s: %s: %s" % (_("Exception"),str(Exception),str(e),))
                    continue

                # create atom string
                myatom = mydata['category']+"/"+mydata['name']+"-"+mydata['version']
                if mydata['versiontag']:
                    myatom += "#"+mydata['versiontag']

                # look for atom in client database
                oldidpackage = Equo.clientDbconn.getIDPackage(myatom)
                if oldidpackage != -1:
                    mydata['revision'] = Equo.clientDbconn.retrieveRevision(oldidpackage)
                else:
                    mydata['revision'] = 9999 # can't do much more

                idpk, rev, xx = Equo.clientDbconn.handlePackage(etpData = mydata, forcedRevision = mydata['revision'])
                Equo.clientDbconn.removePackageFromInstalledTable(idpk)
                Equo.clientDbconn.addPackageToInstalledTable(idpk,"gentoo-db")
                os.remove(temptbz2)

            print_info(brown(" @@ ")+blue("%s." % (_("Database update completed"),)))

        Equo.resources_remove_lock()
        return 0

    elif (options[0] == "backup"):

        status, err_msg = Equo.backup_database(etpConst['etpdatabaseclientfilepath'])
        if status:
            return 0
        return 1

    elif (options[0] == "restore"):

        dblist = Equo.list_backedup_client_databases()
        if not dblist:
            print_info(brown(" @@ ")+blue("%s." % (_("No backed up databases found"),)))
            return 1

        mydblist = []
        db_data = []
        for mydb in dblist:
            ts = Equo.entropyTools.get_file_unix_mtime(mydb)
            mytime = Equo.entropyTools.convert_unix_time_to_human_time(ts)
            mydblist.append("[%s] %s" % (mytime,mydb,))
            db_data.append(mydb)

        def fake_cb(s):
            return s

        input_params = [
            ('db',('combo',(_('Select the database you want to restore'),mydblist),),fake_cb,True)
        ]

        while 1:
            data = Equo.inputBox(red(_("Entropy installed packages database restore tool")), input_params, cancel_button = True)
            if data == None:
                return 1
            myid, dbx = data['db']
            try:
                dbpath = db_data.pop(myid)
            except IndexError:
                continue
            if not os.path.isfile(dbpath): continue
            break

        status, err_msg = Equo.restore_database(dbpath, etpConst['etpdatabaseclientfilepath'])
        if status:
            return 0
        return 1

    elif (options[0] == "vacuum"):

        if Equo.clientDbconn != None:
            print_info(red(" @@ ")+"%s..." % (blue(_("Vacuum cleaning System Database")),), back = True)
            Equo.clientDbconn.dropAllIndexes()
            Equo.clientDbconn.vacuum()
            Equo.clientDbconn.commitChanges()
            print_info(red(" @@ ")+"%s." % (brown(_("Vacuum cleaned System Database")),))
            return 0
        print_warning(darkred(" !!! ")+blue("%s." % (_("No System Databases found"),)))
        return 1

    else:
        return -10

'''
    @description: implementation of migration helper tools, like gentoo's python-updater
'''
def updater(options):

    if len(options) < 1:
        return -10

    # check if I am root
    if (not Equo.entropyTools.is_root()):
        mytxt = _("You are not") # you are not root
        print_error(red(mytxt)+bold("root")+red("."))
        return 1

    rc = 0
    if options[0] == "python-updater":
        rc = pythonUpdater()

    return rc


def pythonUpdater():
    import re
    import text_query
    import text_ui
    pattern = re.compile(r'^(python)[0-9](.)[0-9]$')
    print_info(brown(" @@ ")+blue(_("Looking for old Python directories...")), back = True)
    mydirs = [x for x in os.listdir("/usr/lib") if x.startswith("python") and pattern.match(x)]
    if len(mydirs) <= 1:
        print_info(brown(" @@ ")+blue(_("Your Python installation seems fine.")))
        return 0
    mydirs = sorted(mydirs)
    print_info(brown(" @@ ")+blue(_("Multiple Python directories found:")))
    for pdir in mydirs:
        print_info(red("    # ")+blue("/usr/lib/%s" % (pdir,) ))

    old_pdirs = mydirs[:-1]
    idpackages = set()
    for mydir in old_pdirs:
        old_pdir = os.path.join("/usr/lib/",mydir)
        print_info(brown(" @@ ")+blue("Scanning: %s" % (red(old_pdir),)))
        old_pdir = old_pdir.replace("/usr/lib","/usr/lib*")
        idpackages |= text_query.search_belongs(files = [old_pdir], idreturn = True, dbconn = Equo.clientDbconn)

    if not idpackages:
        mytxt = blue("%s: %s") % (
            _("There are no files belonging to your old Python installation in"),
            ', '.join(old_pdirs),
        )
        print_info(brown(" @@ ")+mytxt)
        return 0

    mytxt = blue("%s: %s") % (
        _("These are the installed packages with files in:"),
        ', '.join(old_pdirs),
    )
    print_info(brown(" @@ ")+mytxt)

    keyslots = set()
    for idpackage in idpackages:
        key, slot = Equo.clientDbconn.retrieveKeySlot(idpackage)
        keyslots.add((key,slot))
        print_info(red("    # ")+key+":"+slot)

    print_info(brown(" @@ ")+blue("%s..." % (_("Searching inside available repositories"),) ))
    matchedAtoms = set()
    for atomkey,slot in keyslots:
        print_info(brown("   @@ ")+red("%s " % (_("Matching"),) )+bold(atomkey)+red(":")+darkgreen(slot), back = True)
        match = Equo.atom_match(atomkey, matchSlot = slot)
        if match[0] != -1:
            matchedAtoms.add((atomkey+":"+slot,match))
    del idpackages

    # now show, then ask or exit (if pretend)
    if not matchedAtoms:
        mytxt = blue("%s: %s") % (
            _("There are no files belonging to your old Python installation stored in the repositories for"),
            ', '.join(old_pdirs),
        )
        print_info(brown(" @@ ")+mytxt)
        return 0

    rc = text_ui.installPackages(atomsdata = matchedAtoms)
    return rc


'''
    @description: prints entropy configuration information
    @input: dict (bool) -> if True, returns a dictionary with packed info. if False, just print to STDOUT
    @output:	dictionary or STDOUT
'''
def getinfo(dict = False):

    # sysinfo
    info = {}
    osinfo = os.uname()
    info['OS'] = osinfo[0]
    info['Kernel'] = osinfo[2]
    info['Architecture'] = osinfo[4]
    info['Entropy version'] = etpConst['entropyversion']

    from entropy.core import SystemSettings
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
    info['Entropy packages directory'] = etpConst['packagesbindir']
    info['Entropy logging directory'] = etpConst['logdir']
    info['Entropy Official Repository identifier'] = SysSettings['repositories']['default_repository']
    info['Entropy API'] = etpConst['etpapi']
    info['Equo pidfile'] = etpConst['pidfile']
    info['Entropy database tag'] = etpConst['databasestarttag']
    info['Repositories'] = SysSettings['repositories']['available']
    info['System Config'] = etpSys
    info['UI Config'] = etpUi

    # client database info
    conn = False
    try:
        Equo.clientDbconn.listAllIdPackages()
        conn = True
    except:
        pass
    info['Installed database'] = conn
    if (conn):
        # print db info
        info['Removal internal protected directories'] = Equo.clientDbconn.listConfigProtectDirectories()
        info['Removal internal protected directory masks'] = Equo.clientDbconn.listConfigProtectDirectories(mask = True)
        info['Total installed packages'] = len(Equo.clientDbconn.listAllIdpackages())

    # repository databases info (if found on the system)
    info['Repository databases'] = {}
    for x in SysSettings['repositories']['order']:
        dbfile = SysSettings['repositories']['available'][x]['dbpath']+"/"+etpConst['etpdatabasefile']
        if os.path.isfile(dbfile):
            # print info about this database
            dbconn = Equo.open_repository(x)
            info['Repository databases'][x] = {}
            info['Repository databases'][x]['Installation internal protected directories'] = dbconn.listConfigProtectDirectories()
            info['Repository databases'][x]['Installation internal protected directory masks'] = dbconn.listConfigProtectDirectories(mask = True)
            info['Repository databases'][x]['Total available packages'] = len(dbconn.listAllIdpackages())
            info['Repository databases'][x]['Database revision'] = Equo.get_repository_revision(x)
            info['Repository databases'][x]['Database hash'] = Equo.get_repository_db_file_checksum(x)

    if (dict):
        return info

    import types
    keys = info.keys()
    keys.sort()
    for x in keys:
        #print type(info[x])
        if type(info[x]) is types.DictType:
            toptext = x
            ykeys = info[x].keys()
            ykeys.sort()
            for y in ykeys:
                if type(info[x][y]) is types.DictType:
                    topsubtext = y
                    zkeys = info[x][y].keys()
                    zkeys.sort()
                    for z in zkeys:
                        print red(toptext)+": "+blue(topsubtext)+" => "+darkgreen(z)+" => "+str(info[x][y][z])
                else:
                    print red(toptext)+": "+blue(y)+" => "+str(info[x][y])
            #print info[x]
        else:
            print red(x)+": "+str(info[x])
