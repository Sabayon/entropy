#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo on-disk caching tools

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

from entropyConstants import *
from clientConstants import *
from outputTools import *
import entropyTools
import equoTools
import confTools
from databaseTools import openRepositoryDatabase


def cache(options):
    rc = 0
    if len(options) < 1:
	return -10

    if options[0] == "clean":
	rc = cleanCache()
    elif options[0] == "generate":
	rc = generateCache()
    else:
        rc = -10

    return rc
    


'''
   @description: scan etpCache and remove all the on disk caching files
   @output: status code
'''
def cleanCache():
    dumpdir = etpConst['dumpstoragedir']
    if not dumpdir.endswith("/"): dumpdir = dumpdir+"/"
    for key in etpCache:
	cachefile = dumpdir+etpCache[key]+"*.dmp"
	if (not etpUi['quiet']): print_warning(blue("(")+bold("*")+blue(")")+darkred(" Cleaning "+cachefile)+" ...")
	try:
	    os.system("rm -f "+cachefile)
	except:
	    pass
    if (not etpUi['quiet']): print_info(blue("(")+bold("*")+blue(")")+darkred(" Cache is now empty."))
    return 0

'''
   @description: cache entropy data and scan packages to collect info and fill caches
   @output: status code
'''
def generateCache(depcache = True, configcache = True):
    cleanCache()
    const_resetCache()
    if (depcache):
        if (not etpUi['quiet']): print_warning(blue("(")+bold("@@")+blue(")")+darkred(" Dependencies"))
        # loading repo db
        if (not etpUi['quiet']): print_warning(blue("(")+bold("*")+blue(")")+darkred(" Scanning repositories"))
        names = set()
        keys = set()
        depends = set()
	atoms = set()
        for reponame in etpRepositories:
	    if (not etpUi['quiet']): print_info("  "+darkgreen("(")+bold("*")+darkgreen(")")+darkred(" Scanning ")+brown(etpRepositories[reponame]['description']), back = True)
	    # get all packages keys
	    dbconn = openRepositoryDatabase(reponame)
	    pkgdata = dbconn.listAllPackages()
	    pkgdata = set(pkgdata)
	    for info in pkgdata:
	        key = entropyTools.dep_getkey(info[0])
	        keys.add(key)
	        names.add(key.split("/")[1])
		atoms.add(info[0])
	    # dependencies
	    pkgdata = dbconn.listAllDependencies()
	    for info in pkgdata:
	        depends.add(info[1])
	    dbconn.closeDB()
            del dbconn
        if (not etpUi['quiet']): print_warning(blue("(")+bold("*")+blue(")")+darkred(" Resolving metadata"))
	atomMatchCache.clear()
	maxlen = str(len(names))
	cnt = 0
        for name in names:
	    cnt += 1
	    lenstat = str(cnt)+"/"+maxlen
	    if (not etpUi['quiet']): print_info("  "+darkgreen("(")+bold(lenstat)+darkgreen(")")+darkred(" Resolving name: ")+brown(name), back = not etpUi['verbose'])
	    equoTools.atomMatch(name)
	maxlen = str(len(keys))
	cnt = 0
        for key in keys:
	    cnt += 1
	    lenstat = str(cnt)+"/"+maxlen
	    if (not etpUi['quiet']): print_info("  "+darkgreen("(")+bold(lenstat)+darkgreen(")")+darkred(" Resolving key: ")+brown(key), back = not etpUi['verbose'])
	    equoTools.atomMatch(key)
	maxlen = str(len(atoms))
	cnt = 0
        for atom in atoms:
	    cnt += 1
	    lenstat = str(cnt)+"/"+maxlen
	    if (not etpUi['quiet']): print_info("  "+darkgreen("(")+bold(lenstat)+darkgreen(")")+darkred(" Resolving atom: ")+brown(atom), back = not etpUi['verbose'])
	    equoTools.atomMatch(atom)
	maxlen = str(len(depends))
	cnt = 0
        for depend in depends:
	    cnt += 1
	    lenstat = str(cnt)+"/"+maxlen
	    if (not etpUi['quiet']): print_info("  "+darkgreen("(")+bold(lenstat)+darkgreen(")")+darkred(" Resolving dependencies: ")+brown(depend), back = not etpUi['verbose'])
	    equoTools.atomMatch(depend)
        if (not etpUi['quiet']): print_warning(blue("(")+bold("@@")+blue(")")+darkred(" Dependencies filled. Flushing to disk."))
        equoTools.saveCaches()
    
    if (configcache):
        if (not etpUi['quiet']): print_warning(blue("(")+bold("@@")+blue(")")+darkred(" Configuration files"))
        if (not etpUi['quiet']): print_warning("  "+blue("(")+bold("*")+blue(")")+darkred(" Scanning hard disk"))
        confTools.scanfs(dcache = False)
        if (not etpUi['quiet']): print_info(darkred(" Cache generation complete."))
    
    return 0
