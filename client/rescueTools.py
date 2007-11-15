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

import os
from entropyConstants import *
from clientConstants import *
from outputTools import *
from databaseTools import etpDatabase, openRepositoryDatabase, openClientDatabase, backupClientDatabase
import entropyTools
import equoTools

def database(options):

    databaseExactMatch = False
    _options = []
    for opt in options:
	if opt == "--exact": # removed
	    databaseExactMatch = True
	else:
	    _options.append(opt)
    options = _options

    if len(options) < 1:
	return 0

    if (options[0] == "generate"):

        # test if portage is available
        try:
            import portageTools
        except:
            print_error(darkred(" * ")+bold("Portage")+red(" is not available."))
            return 1

	print_warning(bold("ATTENTION: ")+red("The installed package database will be generated again using Gentoo one."))
	print_warning(red("If you dont know what you're doing just, don't do this. Really. I'm not joking."))
	rc = entropyTools.askquestion("  Understood?")
	if rc == "No":
	    return 0
	rc = entropyTools.askquestion("  Really?")
	if rc == "No":
	    return 0
	rc = entropyTools.askquestion("  This is your last chance. Ok?")
	if rc == "No":
	    return 0

	# clean caches
	import cacheTools
	cacheTools.cleanCache(quiet = True)
	const_resetCache()
        import shutil
	
	# ok, he/she knows it... hopefully
	# if exist, copy old database
	print_info(red(" @@ ")+blue("Creating backup of the previous database, if exists.")+red(" @@"))
	newfile = backupClientDatabase()
	if (newfile):
	    print_info(red(" @@ ")+blue("Previous database copied to file ")+newfile+red(" @@"))
	
	# Now reinitialize it
	print_info(darkred("  Initializing the new database at "+bold(etpConst['etpdatabaseclientfilepath'])), back = True)
	clientDbconn = openClientDatabase(generate = True)
	clientDbconn.initializeDatabase()
	print_info(darkgreen("  Database reinitialized correctly at "+bold(etpConst['etpdatabaseclientfilepath'])))
	
	# now collect packages in the system
	print_info(red("  Transductingactioningintactering databases..."))
	
	portagePackages = portageTools.getInstalledPackages()
	portagePackages = portagePackages[0]

        appdb = portageTools.getPortageAppDbPath()

	# do for each database
	maxcount = str(len(portagePackages))
        count = 0
        for portagePackage in portagePackages:
            count += 1
	    print_info(blue("(")+darkgreen(str(count))+"/"+darkred(maxcount)+blue(")")+red(" atom: ")+brown(portagePackage))
            temptbz2 = etpConst['entropyunpackdir']+"/"+portagePackage.split("/")[1]+".tbz2"
            if os.path.lexists(temptbz2):
                shutil.rmtree(temptbz2)
            f = open(temptbz2,"wb")
            f.write("this is a fake ")
            f.flush()
            f.close()
            entropyTools.appendXpak(temptbz2,portagePackage)
            # now extract info
            mydata = entropyTools.extractPkgData(temptbz2)
            mydata['revision'] = 9999
            # FIXME also add counter?
            idpk, rev, xx, status = clientDbconn.addPackage(etpData = mydata, revision = mydata['revision'])
            clientDbconn.addPackageToInstalledTable(idpk,"gentoo-db")
            os.remove(temptbz2)
	
	print_info(red("  All the Gentoo packages have been injected into Entropy database."))

	print_info(red("  Now generating depends caching table..."))
	clientDbconn.regenerateDependsTable()
	print_info(red("  Database reinitialized successfully."))
	clientDbconn.closeDB()
        return 0

    elif (options[0] == "resurrect"):

	print_warning(bold("####### ATTENTION -> ")+red("The installed package database will be resurrected, this will take a LOT of time."))
	print_warning(bold("####### ATTENTION -> ")+red("Please use this function ONLY if you are using an Entropy-enabled Sabayon distribution."))
	rc = entropyTools.askquestion("     Can I continue ?")
	if rc == "No":
	    return 0
	rc = entropyTools.askquestion("     Are you REALLY sure ?")
	if rc == "No":
	    return 0
	rc = entropyTools.askquestion("     Do you even know what you're doing ?")
	if rc == "No":
	    return 0
	
	# clean caches
	import cacheTools
	cacheTools.cleanCache(quiet = True)
	const_resetCache()

	# ok, he/she knows it... hopefully
	# if exist, copy old database
	print_info(red(" @@ ")+blue("Creating backup of the previous database, if exists.")+red(" @@"))
	newfile = backupClientDatabase()
	if (newfile):
	    print_info(red(" @@ ")+blue("Previous database copied to file ")+newfile+red(" @@"))
	
	# Now reinitialize it
	print_info(darkred("  Initializing the new database at "+bold(etpConst['etpdatabaseclientfilepath'])), back = True)
	clientDbconn = openClientDatabase()
	clientDbconn.initializeDatabase()
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
	os.system("find / -mount 1> "+etpConst['packagestmpfile'])
	if not os.path.isfile(etpConst['packagestmpfile']):
	    print_error(darkred("Attention: ")+red("find couldn't generate an output file."))
	    return
	
	f = open(etpConst['packagestmpfile'],"r")
	# creating list of files
	filelist = set()
	file = f.readline().strip()
	while file:
	    filelist.add(file)
	    file = f.readline().strip()
	f.close()
	entries = len(filelist)
	
	print_info(red("  Found "+str(entries)+" files on the system. Assigning packages..."))
	atoms = {}
	pkgsfound = set()
	
	for repo in etpRepositories:
	    print_info(red("  Matching in repository: ")+etpRepositories[repo]['description'])
	    # get all idpackages
	    dbconn = openRepositoryDatabase(repo)
	    idpackages = dbconn.listAllIdpackages(branch = etpConst['branch'])
	    count = str(len(idpackages))
	    cnt = 0
	    for idpackage in idpackages:
		cnt += 1
		idpackageatom = dbconn.retrieveAtom(idpackage)
		print_info("  ("+str(cnt)+"/"+count+")"+red(" Matching files from packages..."), back = True)
		# content
		content = dbconn.retrieveContent(idpackage)
		for file in content:
		    if file in filelist:
			pkgsfound.add((idpackage,repo))
			atoms[(idpackage,repo)] = idpackageatom
			filelist.difference_update(set(content))
			break
	    dbconn.closeDB()
	
	print_info(red("  Found "+str(len(pkgsfound))+" packages. Filling database..."))
	count = str(len(pkgsfound))
	cnt = 0
	#XXXos.remove(etpConst['packagestmpfile'])
	
	for pkgfound in pkgsfound:
	    cnt += 1
	    print_info("  ("+str(cnt)+"/"+count+") "+red("Adding: ")+atoms[pkgfound], back = True)
	    equoTools.installPackageIntoDatabase(pkgfound[0],pkgfound[1])

	print_info(red("  Database resurrected successfully."))
	print_warning(red("  Keep in mind that virtual/meta packages couldn't be matched. They don't own any files."))
        return 0

    elif (options[0] == "depends"):
	print_info(red("  Regenerating depends caching table..."))
	clientDbconn = openClientDatabase()
	clientDbconn.regenerateDependsTable()
	clientDbconn.closeDB()
	print_info(red("  Depends caching table regenerated successfully."))
        return 0
    
    else:
        return -10


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
    info['Database Log Level'] = etpConst['databaseloglevel']
    info['entropyTools Log Level'] = etpConst['entropyloglevel']
    info['remoteTools Log Level'] = etpConst['remoteloglevel']
    info['Current branch'] = etpConst['branch']
    info['Available branches'] = etpConst['branches']
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
    
    # client database info
    conn = False
    try:
	clientDbconn = openClientDatabase()
	conn = True
    except:
	pass
    info['Installed database'] = conn
    if (conn):
	# print db info
	info['Removal internal protected directories'] = clientDbconn.listConfigProtectDirectories()
	info['Removal internal protected directory masks'] = clientDbconn.listConfigProtectDirectories(mask = True)
	info['Total installed packages'] = len(clientDbconn.listAllIdpackages())
	clientDbconn.closeDB()
    
    # repository databases info (if found on the system)
    info['Repository databases'] = {}
    for x in etpRepositories:
	dbfile = etpRepositories[x]['dbpath']+"/"+etpConst['etpdatabasefile']
	if os.path.isfile(dbfile):
	    # print info about this database
	    dbconn = openRepositoryDatabase(x)
	    info['Repository databases'][x] = {}
	    info['Repository databases'][x]['Installation internal protected directories'] = dbconn.listConfigProtectDirectories()
	    info['Repository databases'][x]['Installation internal protected directory masks'] = dbconn.listConfigProtectDirectories(mask = True)
	    info['Repository databases'][x]['Total available packages'] = len(dbconn.listAllIdpackages())
	    info['Repository databases'][x]['Database revision'] = repositoriesTools.getRepositoryRevision(x)
	    info['Repository databases'][x]['Database hash'] = repositoriesTools.getRepositoryDbFileHash(x)
	    dbconn.closeDB()
    
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
