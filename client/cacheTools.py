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


def cache(options):
    rc = 0
    if len(options) < 1:
	return rc

    equoRequestVerbose = False
    equoRequestQuiet = False
    myopts = []
    for opt in options:
	if (opt == "--verbose"):
	    equoRequestVerbose = True
	elif (opt == "--quiet"):
	    equoRequestQuiet = True
	else:
	    myopts.append(opt)

    if myopts[0] == "clean":
	rc = cleanCache()

    if myopts[0] == "generate":
	rc = generateCache(quiet = equoRequestQuiet, verbose = equoRequestVerbose)

    return rc
    


'''
   @description: scan etpCache and remove all the on disk caching files
   @output: status code
'''
def cleanCache(quiet = False):
    dumpdir = etpConst['dumpstoragedir']
    if not dumpdir.endswith("/"): dumpdir = dumpdir+"/"
    for key in etpCache:
	cachefile = dumpdir+etpCache[key]+"*.dmp"
	if (not quiet): print_warning(blue("(")+bold("*")+blue(")")+darkred(" Cleaning "+cachefile)+" ...")
	try:
	    os.system("rm -f "+cachefile)
	except:
	    pass
    if (not quiet): print_info(blue("(")+bold("*")+blue(")")+darkred(" Cache in now empty."))
    return 0

'''
   @description: cache entropy data and scan packages to collect info and fill caches
   @output: status code
'''
def generateCache(quiet = False, verbose = False, depcache = True, configcache = True):
    cleanCache(quiet = True)
    const_resetCache()
    if (depcache):
        if (not quiet): print_warning(blue("(")+bold("@@")+blue(")")+darkred(" Dependencies"))
        # loading repo db
        if (not quiet): print_warning(blue("(")+bold("*")+blue(")")+darkred(" Scanning repositories"))
        names = set()
        keys = set()
        depends = set()
	atoms = set()
        for reponame in etpRepositories:
	    if (not quiet): print_info("  "+darkgreen("(")+bold("*")+darkgreen(")")+darkred(" Scanning ")+brown(etpRepositories[reponame]['description']), back = True)
	    # get all packages keys
	    dbconn = equoTools.openRepositoryDatabase(reponame)
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
        if (not quiet): print_warning(blue("(")+bold("*")+blue(")")+darkred(" Resolving metadata"))
	atomMatchCache.clear()
	maxlen = str(len(names))
	cnt = 0
        for name in names:
	    cnt += 1
	    lenstat = str(cnt)+"/"+maxlen
	    if (not quiet): print_info("  "+darkgreen("(")+bold(lenstat)+darkgreen(")")+darkred(" Resolving name: ")+brown(name), back = not verbose)
	    equoTools.atomMatch(name)
	maxlen = str(len(keys))
	cnt = 0
        for key in keys:
	    cnt += 1
	    lenstat = str(cnt)+"/"+maxlen
	    if (not quiet): print_info("  "+darkgreen("(")+bold(lenstat)+darkgreen(")")+darkred(" Resolving key: ")+brown(key), back = not verbose)
	    equoTools.atomMatch(key)
	maxlen = str(len(atoms))
	cnt = 0
        for atom in atoms:
	    cnt += 1
	    lenstat = str(cnt)+"/"+maxlen
	    if (not quiet): print_info("  "+darkgreen("(")+bold(lenstat)+darkgreen(")")+darkred(" Resolving atom: ")+brown(atom), back = not verbose)
	    equoTools.atomMatch(atom)
	maxlen = str(len(depends))
	cnt = 0
        for depend in depends:
	    cnt += 1
	    lenstat = str(cnt)+"/"+maxlen
	    if (not quiet): print_info("  "+darkgreen("(")+bold(lenstat)+darkgreen(")")+darkred(" Resolving dependencies: ")+brown(depend), back = not verbose)
	    equoTools.atomMatch(depend)
        if (not quiet): print_warning(blue("(")+bold("@@")+blue(")")+darkred(" Dependencies filled. Flushing to disk."))
        equoTools.saveCaches()
    
    if (configcache):
        if (not quiet): print_warning(blue("(")+bold("@@")+blue(")")+darkred(" Configuration files"))
        if (not quiet): print_warning("  "+blue("(")+bold("*")+blue(")")+darkred(" Scanning hard disk"))
        confTools.scanfs(quiet = not verbose, dcache = False)
        if (not quiet): print_info(darkred(" Cache generation complete."))
    
    return 0
