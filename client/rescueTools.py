#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo integrity handling library

    Copyright (C) 2007 Fabio Erculiani

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

from entropyConstants import *
from clientConstants import *
from outputTools import *
from databaseTools import backupClientDatabase
import entropyTools
from equoInterface import EquoInterface
Equo = EquoInterface(noclientdb = True)

def database(options):

    if len(options) < 1:
        return -10

    # check if I am root
    if (not entropyTools.isRoot()):
        print_error(red("You are not ")+bold("root")+red("."))
        return 1

    if (options[0] == "generate"):

        # test if portage is available
        try:
            import portageTools
        except:
            print_error(darkred(" * ")+bold("Portage")+red(" is not available."))
            return 1

        
	print_warning(bold("ATTENTION: ")+red("The installed package database will be generated again using Gentoo one."))
	print_warning(red("If you dont know what you're doing just, don't do this. Really. I'm not joking."))
	rc = Equo.askQuestion("  Understood?")
	if rc == "No":
	    return 0
	rc = Equo.askQuestion("  Really?")
	if rc == "No":
	    return 0
	rc = Equo.askQuestion("  This is your last chance. Ok?")
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
	print_info(red(" @@ ")+blue("Creating backup of the previous database, if exists.")+red(" @@"))
	newfile = backupClientDatabase()
	if (newfile):
	    print_info(red(" @@ ")+blue("Previous database copied to file ")+newfile+red(" @@"))
	
	# Now reinitialize it
	print_info(darkred("  Initializing the new database at "+bold(etpConst['etpdatabaseclientfilepath'])), back = True)
        Equo.reopenClientDbconn()
	Equo.clientDbconn.initializeDatabase()
	print_info(darkgreen("  Database reinitialized correctly at "+bold(etpConst['etpdatabaseclientfilepath'])))
	
	# now collect packages in the system
	print_info(red("  Transductingactioningintactering databases..."))
	
	portagePackages = portageTools.getInstalledPackages()
	portagePackages = portagePackages[0]

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
            f.write("this is a fake ")
            f.flush()
            f.close()
            entropyTools.appendXpak(temptbz2,portagePackage)
            # now extract info
            try:
                mydata = entropyTools.extractPkgData(temptbz2, silent = True)
            except:
                print_warning(red("!!! An error occured while analyzing: ")+blue(portagePackage))
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
            
            idpk, rev, xx, status = Equo.clientDbconn.addPackage(etpData = mydata, revision = mydata['revision'])
            Equo.clientDbconn.addPackageToInstalledTable(idpk,"gentoo-db")
            os.remove(temptbz2)
	
	print_info(red("  All the Gentoo packages have been injected into Entropy database."))

	print_info(red("  Now generating depends caching table..."))
	Equo.clientDbconn.regenerateDependsTable()
	print_info(red("  Database reinitialized successfully."))
        return 0

    elif (options[0] == "resurrect"):
        
	print_warning(bold("####### ATTENTION -> ")+red("The installed package database will be resurrected, this will take a LOT of time."))
	print_warning(bold("####### ATTENTION -> ")+red("Please use this function ONLY if you are using an Entropy-enabled Sabayon distribution."))
	rc = Equo.askQuestion("     Can I continue ?")
	if rc == "No":
	    return 0
	rc = Equo.askQuestion("     Are you REALLY sure ?")
	if rc == "No":
	    return 0
	rc = Equo.askQuestion("     Do you even know what you're doing ?")
	if rc == "No":
	    return 0
	
	# clean caches
	Equo.purge_cache()

	# ok, he/she knows it... hopefully
	# if exist, copy old database
	print_info(red(" @@ ")+blue("Creating backup of the previous database, if exists.")+red(" @@"))
	newfile = backupClientDatabase()
	if (newfile):
	    print_info(red(" @@ ")+blue("Previous database copied to file ")+newfile+red(" @@"))
	
	# Now reinitialize it
	print_info(darkred("  Initializing the new database at "+bold(etpConst['etpdatabaseclientfilepath'])), back = True)
	Equo.clientDbconn.initializeDatabase()
	print_info(darkgreen("  Database reinitialized correctly at "+bold(etpConst['etpdatabaseclientfilepath'])))
	
	print_info(red("  Collecting installed files. Writing: "+etpConst['packagestmpfile']+" Please wait..."), back = True)
	
	# since we use find, see if it's installed
	find = os.system("which find &> /dev/null")
	if find != 0:
	    print_error(darkred("Attention: ")+red("You must have 'find' installed!"))
	    return
	# spawn process
	if os.path.isfile(etpConst['packagestmpfile']):
	    os.remove(etpConst['packagestmpfile'])
	os.system("find "+etpConst['systemroot']+"/ -mount 1> "+etpConst['packagestmpfile'])
	if not os.path.isfile(etpConst['packagestmpfile']):
	    print_error(darkred("Attention: ")+red("find couldn't generate an output file."))
	    return
	
	f = open(etpConst['packagestmpfile'],"r")
	# creating list of files
	filelist = set()
	item = f.readline().strip()
	while item:
	    filelist.add(item)
	    item = f.readline().strip()
	f.close()
	entries = len(filelist)
	
	print_info(red("  Found "+str(entries)+" files on the system. Assigning packages..."))
	atoms = {}
	pkgsfound = set()
	
	for repo in etpRepositories:
	    print_info(red("  Matching in repository: ")+etpRepositories[repo]['description'])
	    # get all idpackages
	    dbconn = Equo.openRepositoryDatabase(repo)
	    idpackages = dbconn.listAllIdpackages(branch = etpConst['branch'])
	    count = str(len(idpackages))
	    cnt = 0
	    for idpackage in idpackages:
		cnt += 1
		idpackageatom = dbconn.retrieveAtom(idpackage)
		print_info("  ("+str(cnt)+"/"+count+")"+red(" Matching files from packages..."), back = True)
		# content
		content = dbconn.retrieveContent(idpackage)
		for item in content:
		    if etpConst['systemroot']+item in filelist:
			pkgsfound.add((idpackage,repo))
			atoms[(idpackage,repo)] = idpackageatom
			filelist.difference_update(set([etpConst['systemroot']+x for x in content]))
			break
	
	print_info(red("  Found "+str(len(pkgsfound))+" packages. Filling database..."))
	count = str(len(pkgsfound))
	cnt = 0
	os.remove(etpConst['packagestmpfile'])
	
	for pkgfound in pkgsfound:
	    cnt += 1
	    print_info("  ("+str(cnt)+"/"+count+") "+red("Adding: ")+atoms[pkgfound], back = True)
            Package = Equo.Package()
            Package.prepare(tuple(pkgfound),"install", {})
            Package.__install_package_into_database()
            Package.kill()
            del Package

	print_info(red("  Database resurrected successfully."))
	print_warning(red("  Keep in mind that virtual/meta packages couldn't be matched. They don't own any files."))
        return 0

    elif (options[0] == "depends"):
	print_info(red("  Regenerating depends caching table..."))
	Equo.clientDbconn.regenerateDependsTable()
	print_info(red("  Depends caching table regenerated successfully."))
        return 0

    elif (options[0] == "counters"):
        
        try:
            import portageTools
        except:
            print_error(darkred(" * ")+bold("Portage")+red(" is not available."))
            return 1
        
	print_info(red("  Regenerating counters table. Please wait..."))
	Equo.clientDbconn.regenerateCountersTable(output = True)
	print_info(red("  Counters table regenerated. Check above for errors."))
        return 0

    elif (options[0] == "gentoosync"):
        
        try:
            import portageTools
        except:
            print_error(darkred(" * ")+bold("Portage")+red(" is not available."))
            return 1
        
	print_info(red(" Scanning Portage and Entropy databases for differences..."))

        # make it crash
        Equo.noclientdb = False
        Equo.reopenClientDbconn()

        # test if counters table exists, because if not, it's useless to run the diff scan
        try:
            Equo.clientDbconn.isCounterAvailable(1)
        except:
            print_error(darkred(" * ")+bold("Entropy database")+red(" has never been in sync with Portage one. So, you can't run this unless you run '")+bold("equo database generate")+red("' first. Sorry."))
            return 1

        import shutil
        from portageTools import getInstalledPackagesCounters, getPackageSlot
        print_info(red(" Collecting Portage counters..."), back = True)
        installedPackages = getInstalledPackagesCounters()
        print_info(red(" Collecting Entropy packages..."), back = True)
        installedCounters = set()
        toBeAdded = set()
        toBeRemoved = set()

        print_info(red(" Differential Scan..."), back = True)
        # packages to be added/updated (handle add/update later)
        for x in installedPackages[0]:
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
                    atomkey = entropyTools.dep_getkey(Equo.clientDbconn.retrieveAtom(x[1]))
                    atomslot = Equo.clientDbconn.retrieveSlot(x[1])
                    add = True
                    for pkgdata in toBeAdded:
                        addslot = getPackageSlot(pkgdata[0])
                        addkey = entropyTools.dep_getkey(pkgdata[0])
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
            print_info(red(" Databases already synced."))
            # then exit gracefully
            return 0
        
        if (toBeRemoved):
            print_info(brown(" @@ ")+blue("Someone removed these packages. Would be removed from the Entropy database:"))

            for x in toBeRemoved:
                atom = Equo.clientDbconn.retrieveAtom(x)
                print_info(brown("    # ")+red(atom))
            rc = "Yes"
            if etpUi['ask']: rc = Equo.askQuestion(">>   Continue with removal?")
            if rc == "Yes":
                queue = 0
                totalqueue = str(len(toBeRemoved))
                for x in toBeRemoved:
                    queue += 1
                    atom = Equo.clientDbconn.retrieveAtom(x)
                    print_info(red(" ++ ")+bold("(")+blue(str(queue))+"/"+red(totalqueue)+bold(") ")+">>> Removing "+darkgreen(atom))
                    Equo.clientDbconn.removePackage(x)
                print_info(brown(" @@ ")+blue("Database removal complete."))

        if (toBeAdded):
            print_info(brown(" @@ ")+blue("Someone added these packages. Would be added/updated into the Entropy database:"))
            for x in toBeAdded:
                print_info(darkgreen("   # ")+red(x[0]))
            rc = "Yes"
            if etpUi['ask']: rc = Equo.askQuestion(">>   Continue with adding?")
            if rc == "No":
                return 0
            # now analyze

            totalqueue = str(len(toBeAdded))
            queue = 0
            for item in toBeAdded:
                queue += 1
                counter = item[1]
                atom = item[0]
                print_info(red(" ++ ")+bold("(")+blue(str(queue))+"/"+red(totalqueue)+bold(") ")+">>> Adding "+darkgreen(atom))
                if not os.path.isdir(etpConst['entropyunpackdir']):
                    os.makedirs(etpConst['entropyunpackdir'])
                temptbz2 = etpConst['entropyunpackdir']+"/"+atom.split("/")[1]+".tbz2"
                if os.path.isfile(temptbz2):
                    os.remove(temptbz2)
                elif os.path.isdir(temptbz2):
                    shutil.rmtree(temptbz2)
                f = open(temptbz2,"wb")
                f.write("this is a fake ")
                f.flush()
                f.close()
                entropyTools.appendXpak(temptbz2,atom)
                # now extract info
                try:
                    mydata = entropyTools.extractPkgData(temptbz2, silent = True)
                except:
                    print_warning(red("!!! An error occured while analyzing: ")+blue(atom))
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

                idpk, rev, xx, status = Equo.clientDbconn.handlePackage(etpData = mydata, forcedRevision = mydata['revision'])
                Equo.clientDbconn.removePackageFromInstalledTable(idpk)
                Equo.clientDbconn.addPackageToInstalledTable(idpk,"gentoo-db")
                os.remove(temptbz2)

            print_info(brown(" @@ ")+blue("Database update completed."))

        return 0

    else:
        return -10

'''
    @description: implementation of migration helper tools, like gentoo's python-updater
'''
def updater(options):

    if len(options) < 1:
        return -10

    # check if I am root
    if (not entropyTools.isRoot()):
        print_error(red("You are not ")+bold("root")+red("."))
        return 1

    rc = 0
    if options[0] == "python-updater":
        rc = pythonUpdater()

    return rc


def pythonUpdater():
    import re
    import queryTools
    import uiTools
    pattern = re.compile(r'^(python)[0-9](.)[0-9]$')
    print_info(brown(" @@ ")+blue("Looking for old Python directories..."), back = True)
    dirs = [x for x in os.listdir("/usr/lib") if x.startswith("python") and pattern.match(x)]
    if len(dirs) <= 1:
        print_info(brown(" @@ ")+blue("Your Python installation seems fine."))
        return 0
    dirs.sort()
    print_info(brown(" @@ ")+blue("Multiple Python directories found:"))
    for pdir in dirs:
        print_info(red("    # ")+blue("/usr/lib/%s" % (pdir,) ))

    old_pdir = os.path.join("/usr/lib/",dirs[0])
    print_info(brown(" @@ ")+blue("Scanning: %s" % (red(old_pdir),)))

    old_pdir = old_pdir.replace("/usr/lib","/usr/lib*")
    idpackages = queryTools.searchBelongs(files = [old_pdir], idreturn = True, dbconn = Equo.clientDbconn)
    if not idpackages:
        print_info(brown(" @@ ")+blue("There are no files in %s whose belong to your old Python." % (old_pdir,)))
        return 0
    print_info(brown(" @@ ")+blue("These are the installed packages whose have files in %s:" % (red(old_pdir),)))

    atoms = set()
    for idpackage in idpackages:
        atom = Equo.clientDbconn.retrieveAtom(idpackage)
        atoms.add((atom, idpackage))
        print_info(red("    # ")+atom)

    print_info(brown(" @@ ")+blue("Searching inside available repositories..."))
    atoms = list(atoms)
    atoms.sort()
    matchedAtoms = set()
    for meta in atoms:
        atomkey = entropyTools.dep_getkey(meta[0])
        slot = Equo.clientDbconn.retrieveSlot(meta[1])
        print_info(brown("   @@ ")+red("Matching ")+bold(atomkey)+red(":")+darkgreen(slot), back = True)
        match = Equo.atomMatch(atomkey, matchSlot = slot)
        if match[0] != -1:
            matchedAtoms.add((atomkey+":"+slot,match))
    del atoms
    del idpackages

    # now show, then ask or exit (if pretend)
    if not matchedAtoms:
        print_info(brown(" @@ ")+blue("There are no files in %s whose belong to your old Python and are stored in configured repositories." % (old_pdir,)))
        return 0

    # run uiTools
    rc = uiTools.installPackages(atomsdata = matchedAtoms)
    return rc


'''
    @description: prints entropy configuration information
    @input: dict (bool) -> if True, returns a dictionary with packed info. if False, just print to STDOUT
    @output:	dictionary or STDOUT
'''
def getinfo(dict = False):
    import repositoriesTools
    # sysinfo
    info = {}
    osinfo = os.uname()
    info['OS'] = osinfo[0]
    info['Kernel'] = osinfo[2]
    info['Architecture'] = osinfo[4]
    info['Entropy version'] = etpConst['entropyversion']
    
    # variables
    info['User protected directories'] = etpConst['configprotect']
    info['Collision Protection'] = etpConst['collisionprotect']
    info['Gentoo Compatibility'] = etpConst['gentoo-compat']
    info['Equo Log Level'] = etpConst['equologlevel']
    info['entropyTools Log Level'] = etpConst['entropyloglevel']
    info['Current branch'] = etpConst['branch']
    info['Entropy configuration directory'] = etpConst['confdir']
    info['Entropy work directory'] = etpConst['entropyworkdir']
    info['Entropy unpack directory'] = etpConst['entropyunpackdir']
    info['Entropy packages directory'] = etpConst['packagesbindir']
    info['Entropy logging directory'] = etpConst['logdir']
    info['Entropy Official Repository name'] = etpConst['officialrepositoryname']
    info['Entropy API'] = etpConst['etpapi']
    info['Equo pidfile'] = etpConst['pidfile']
    info['Entropy database tag'] = etpConst['databasestarttag']
    info['Repositories'] = etpRepositories
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
    for x in etpRepositories:
	dbfile = etpRepositories[x]['dbpath']+"/"+etpConst['etpdatabasefile']
	if os.path.isfile(dbfile):
	    # print info about this database
	    dbconn = Equo.openRepositoryDatabase(x)
	    info['Repository databases'][x] = {}
	    info['Repository databases'][x]['Installation internal protected directories'] = dbconn.listConfigProtectDirectories()
	    info['Repository databases'][x]['Installation internal protected directory masks'] = dbconn.listConfigProtectDirectories(mask = True)
	    info['Repository databases'][x]['Total available packages'] = len(dbconn.listAllIdpackages())
	    info['Repository databases'][x]['Database revision'] = repositoriesTools.getRepositoryRevision(x)
	    info['Repository databases'][x]['Database hash'] = repositoriesTools.getRepositoryDbFileHash(x)
    
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
