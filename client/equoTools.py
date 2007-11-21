#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo Library used by Python frontends

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

from sys import path, getfilesystemencoding
import os
import shutil
from entropyConstants import *
from clientConstants import *
from outputTools import *
from remoteTools import downloadData
from entropyTools import compareMd5, bytesIntoHuman, askquestion, getRandomNumber, dep_getkey, entropyCompareVersions, filterDuplicatedEntries, extractDuplicatedEntries, uncompressTarBz2, extractXpak, applicationLockCheck, countdown, isRoot, spliturl, remove_tag, dep_striptag, md5sum, allocateMaskedFile, istextfile, isnumber, extractEdb, getNewerVersion, getNewerVersionTag, unpackXpak, lifobuffer
from databaseTools import openRepositoryDatabase, openClientDatabase, openGenericDatabase, fetchRepositoryIfNotAvailable, listAllAvailableBranches
import triggerTools
import confTools
import dumpTools
import repositoriesTools

# Logging initialization
import logTools
equoLog = logTools.LogFile(level = etpConst['equologlevel'],filename = etpConst['equologfile'], header = "[Equo]")

### Caching functions

def loadCaches(quiet = False):
    if not quiet: print_info(darkred(" @@ ")+blue("Loading On-Disk Cache..."))
    # atomMatch
    try:
        mycache = dumpTools.loadobj(etpCache['atomMatch'])
	if isinstance(mycache, dict):
	    atomMatchCache = mycache.copy()
    except:
	atomMatchCache = {}
	dumpTools.dumpobj(etpCache['atomMatch'],{})

    # removal dependencies
    try:
        mycache3 = dumpTools.loadobj(etpCache['generateDependsTree'])
	if isinstance(mycache3, dict):
	    generateDependsTreeCache = mycache3.copy()
    except:
	generateDependsTreeCache = {}
	dumpTools.dumpobj(etpCache['generateDependsTree'],{})


def saveCaches():
    dumpTools.dumpobj(etpCache['atomMatch'],atomMatchCache)
    if os.path.isfile(etpConst['dumpstoragedir']+"/"+etpCache['atomMatch']+".dmp"):
	if os.stat(etpConst['dumpstoragedir']+"/"+etpCache['atomMatch']+".dmp")[6] > etpCacheSizes['atomMatch']:
	    # clean cache
	    dumpTools.dumpobj(etpCache['atomMatch'],{})
    dumpTools.dumpobj(etpCache['generateDependsTree'],generateDependsTreeCache)
    if os.path.isfile(etpConst['dumpstoragedir']+"/"+etpCache['generateDependsTree']+".dmp"):
	if os.stat(etpConst['dumpstoragedir']+"/"+etpCache['generateDependsTree']+".dmp")[6] > etpCacheSizes['generateDependsTree']:
	    # clean cache
	    dumpTools.dumpobj(etpCache['generateDependsTree'],{})
    for dbinfo in dbCacheStore:
	dumpTools.dumpobj(dbinfo,dbCacheStore[dbinfo])
	# check size
	if os.path.isfile(etpConst['dumpstoragedir']+"/"+dbinfo+".dmp"):
	    if dbinfo.startswith(etpCache['dbMatch']):
	        if os.stat(etpConst['dumpstoragedir']+"/"+dbinfo+".dmp")[6] > etpCacheSizes['dbMatch']:
		    # clean cache
		    dumpTools.dumpobj(dbinfo,{})
	    elif dbinfo.startswith(etpCache['dbInfo']):
	        if os.stat(etpConst['dumpstoragedir']+"/"+dbinfo+".dmp")[6] > etpCacheSizes['dbInfo']:
		    # clean cache
		    dumpTools.dumpobj(dbinfo,{})
	    elif dbinfo.startswith(etpCache['dbSearch']):
	        if os.stat(etpConst['dumpstoragedir']+"/"+dbinfo+".dmp")[6] > etpCacheSizes['dbSearch']:
		    # clean cache
		    dumpTools.dumpobj(dbinfo,{})


########################################################
####
##   Dependency handling functions
#

'''
   @description: matches the package that user chose, using dbconnection.atomMatch searching in all available repositories.
   @input atom: user choosen package name
   @output: the matched selection, list: [package id,repository name] | if nothing found, returns: ( -1,1 )
   @ exit errors:
	    -1 => repository cannot be fetched online
'''
def atomMatch(atom, caseSentitive = True, matchSlot = None, matchBranches = (), xcache = True):

    if xcache:
        cached = atomMatchCache.get(atom)
        if cached:
	    if (cached['matchSlot'] == matchSlot) and (cached['matchBranches'] == matchBranches):
	        return cached['result']

    repoResults = {}
    exitstatus = 0
    exitErrors = {}
    
    for repo in etpRepositories:
	# sync database if not available
	rc = fetchRepositoryIfNotAvailable(repo)
	if (rc != 0):
	    exitstatus = -1
	    exitErrors[repo] = -1
	    continue
	# open database
	dbconn = openRepositoryDatabase(repo, xcache = xcache)
	
	# search
	query = dbconn.atomMatch(atom, caseSensitive = caseSentitive, matchSlot = matchSlot, matchBranches = matchBranches)
	if query[1] == 0:
	    # package found, add to our dictionary
	    repoResults[repo] = query[0]
	
	dbconn.closeDB()

    # handle repoResults
    packageInformation = {}
    
    # nothing found
    if len(repoResults) == 0:
	atomMatchCache[atom] = {}
	atomMatchCache[atom]['result'] = -1,1
	atomMatchCache[atom]['matchSlot'] = matchSlot
	atomMatchCache[atom]['matchBranches'] = matchBranches
	return -1,1
    
    elif len(repoResults) == 1:
	# one result found
	for repo in repoResults:
	    atomMatchCache[atom] = {}
	    atomMatchCache[atom]['result'] = repoResults[repo],repo
	    atomMatchCache[atom]['matchSlot'] = matchSlot
	    atomMatchCache[atom]['matchBranches'] = matchBranches
	    return repoResults[repo],repo
    
    elif len(repoResults) > 1:
	# we have to decide which version should be taken
	
	# get package information for all the entries
	for repo in repoResults:
	    
	    # open database
	    dbconn = openRepositoryDatabase(repo)
	
	    # search
	    packageInformation[repo] = {}
	    packageInformation[repo]['version'] = dbconn.retrieveVersion(repoResults[repo])
	    packageInformation[repo]['versiontag'] = dbconn.retrieveVersionTag(repoResults[repo])
	    packageInformation[repo]['revision'] = dbconn.retrieveRevision(repoResults[repo])
	    dbconn.closeDB()

	versions = []
	repoNames = []
	# compare versions
	for repo in packageInformation:
	    repoNames.append(repo)
	    versions.append(packageInformation[repo]['version'])
	
	# found duplicates, this mean that we have to look at the revision and then, at the version tag
	# if all this shait fails, get the uppest repository
	# if no duplicates, we're done
	#print versions
	filteredVersions = filterDuplicatedEntries(versions)
	if (len(versions) > len(filteredVersions)):
	    # there are duplicated results, fetch them
	    # get the newerVersion
	    #print versions
	    newerVersion = getNewerVersion(versions)
	    newerVersion = newerVersion[0]
	    # is newerVersion, the duplicated one?
	    duplicatedEntries = extractDuplicatedEntries(versions)
	    needFiltering = False
	    if newerVersion in duplicatedEntries:
		needFiltering = True
	    
	    if (needFiltering):
		# we have to decide which one is good
		#print "need filtering"
		# we have newerVersion
		conflictingEntries = {}
		for repo in packageInformation:
		    if packageInformation[repo]['version'] == newerVersion:
			conflictingEntries[repo] = {}
			#conflictingEntries[repo]['version'] = packageInformation[repo]['version']
			conflictingEntries[repo]['versiontag'] = packageInformation[repo]['versiontag']
			conflictingEntries[repo]['revision'] = packageInformation[repo]['revision']
		
		# at this point compare tags
		tags = []
		for repo in conflictingEntries:
		    tags.append(conflictingEntries[repo]['versiontag'])
		newerTag = getNewerVersionTag(tags)
		newerTag = newerTag[0]
		
		# is the chosen tag duplicated?
		duplicatedTags = extractDuplicatedEntries(tags)
		needFiltering = False
		if newerTag in duplicatedTags:
		    needFiltering = True
		
		if (needFiltering):
		    #print "also tags match"
		    # yes, it is. we need to compare revisions
		    conflictingTags = {}
		    for repo in conflictingEntries:
		        if conflictingEntries[repo]['versiontag'] == newerTag:
			    conflictingTags[repo] = {}
			    #conflictingTags[repo]['version'] = conflictingEntries[repo]['version']
			    #conflictingTags[repo]['versiontag'] = conflictingEntries[repo]['versiontag']
			    conflictingTags[repo]['revision'] = conflictingEntries[repo]['revision']
		    
		    #print tags
		    #print conflictingTags
		    revisions = []
		    for repo in conflictingTags:
			revisions.append(str(conflictingTags[repo]['revision']))
		    newerRevision = getNewerVersionTag(revisions)
		    newerRevision = newerRevision[0]
		    duplicatedRevisions = extractDuplicatedEntries(revisions)
		    needFiltering = False
		    if newerRevision in duplicatedRevisions:
			needFiltering = True
		
		    if (needFiltering):
			# ok, we must get the repository with the biggest priority
			#print "d'oh"
		        # I'm pissed off, now I get the repository name and quit
                        myrepoorder = list(etpRepositoriesOrder)
                        myrepoorder.sort()
			for repository in myrepoorder:
			    for repo in conflictingTags:
				if repository[1] == repo:
				    # found it, WE ARE DOOONE!
				    atomMatchCache[atom] = {}
				    atomMatchCache[atom]['result'] = repoResults[repo],repo
				    atomMatchCache[atom]['matchSlot'] = matchSlot
				    atomMatchCache[atom]['matchBranches'] = matchBranches
				    return repoResults[repo],repo
		    
		    else:
			# we are done!!!
		        reponame = ''
			#print conflictingTags
		        for x in conflictingTags:
		            if str(conflictingTags[x]['revision']) == str(newerRevision):
			        reponame = x
			        break
			atomMatchCache[atom] = {}
			atomMatchCache[atom]['result'] = repoResults[reponame],reponame
			atomMatchCache[atom]['matchSlot'] = matchSlot
			atomMatchCache[atom]['matchBranches'] = matchBranches
		        return repoResults[reponame],reponame
		
		else:
		    # we're finally done
		    reponame = ''
		    for x in conflictingEntries:
		        if conflictingEntries[x]['versiontag'] == newerTag:
			    reponame = x
			    break
		    atomMatchCache[atom] = {}
		    atomMatchCache[atom]['result'] = repoResults[reponame],reponame
		    atomMatchCache[atom]['matchSlot'] = matchSlot
		    atomMatchCache[atom]['matchBranches'] = matchBranches
		    return repoResults[reponame],reponame

	    else:
		# we are fine, the newerVersion is not one of the duplicated ones
		reponame = ''
		for x in packageInformation:
		    if packageInformation[x]['version'] == newerVersion:
			reponame = x
			break
		atomMatchCache[atom] = {}
		atomMatchCache[atom]['result'] = repoResults[reponame],reponame
		atomMatchCache[atom]['matchSlot'] = matchSlot
		atomMatchCache[atom]['matchBranches'] = matchBranches
		return repoResults[reponame],reponame

	    #print versions
	
	else:
	    # yeah, we're done, just return the info
	    #print versions
	    newerVersion = getNewerVersion(versions)
	    # get the repository name
	    newerVersion = newerVersion[0]
	    reponame = ''
	    for x in packageInformation:
		if packageInformation[x]['version'] == newerVersion:
		    reponame = x
		    break
	    #print reponame
	    atomMatchCache[atom] = {}
	    atomMatchCache[atom]['result'] = repoResults[reponame],reponame
	    atomMatchCache[atom]['matchSlot'] = matchSlot
	    atomMatchCache[atom]['matchBranches'] = matchBranches
	    return repoResults[reponame],reponame


'''
   @description: generates the dependencies of a [id,repository name] combo.
   @input packageInfo: tuple composed by int(id) and str(repository name), if this one is int(0), the client database will be opened.
   @output: ordered dependency list
'''
getDependenciesCache = {}
def getDependencies(packageInfo):

    ''' caching '''
    cached = getDependenciesCache.get(tuple(packageInfo))
    if cached:
	return cached['result']

    idpackage = packageInfo[0]
    reponame = packageInfo[1]
    if reponame == 0:
	dbconn = openClientDatabase()
    else:
	dbconn = openRepositoryDatabase(reponame)
    
    # retrieve dependencies
    depend = dbconn.retrieveDependencies(idpackage)
    # and conflicts
    conflicts = dbconn.retrieveConflicts(idpackage)
    for x in conflicts:
	depend.add("!"+x)
    dbconn.closeDB()

    ''' caching '''
    getDependenciesCache[tuple(packageInfo)] = {}
    getDependenciesCache[tuple(packageInfo)]['result'] = depend

    return depend

'''
   @description: filter the already installed dependencies
   @input dependencies: list of dependencies to check
   @output: filtered list, aka the needed ones and the ones satisfied
'''
filterSatisfiedDependenciesCache = {}
filterSatisfiedDependenciesCmpResults = {} # 0: not installed, <0 a<b | >0 a>b
def filterSatisfiedDependencies(dependencies, deepdeps = False):

    unsatisfiedDeps = set()
    satisfiedDeps = set()
    # now create a list with the unsatisfied ones
    # query the installed packages database
    #print etpConst['etpdatabaseclientfilepath']
    clientDbconn = openClientDatabase()
    if (clientDbconn != -1):
        for dependency in dependencies:

	    depsatisfied = set()
	    depunsatisfied = set()

            ''' caching '''
	    cached = filterSatisfiedDependenciesCache.get(dependency)
	    if cached:
		if (cached['deepdeps'] == deepdeps):
		    unsatisfiedDeps.update(cached['depunsatisfied'])
		    satisfiedDeps.update(cached['depsatisfied'])
		    continue

	    ### conflict
	    if dependency[0] == "!":
		testdep = dependency[1:]
		xmatch = clientDbconn.atomMatch(testdep)
		if xmatch[0] != -1:
		    unsatisfiedDeps.add(dependency)
		else:
		    satisfiedDeps.add(dependency)
		continue

	    repoMatch = atomMatch(dependency)
	    if repoMatch[0] != -1:
		dbconn = openRepositoryDatabase(repoMatch[1])
		repo_pkgver = dbconn.retrieveVersion(repoMatch[0])
		repo_pkgtag = dbconn.retrieveVersionTag(repoMatch[0])
		repo_pkgrev = dbconn.retrieveRevision(repoMatch[0])
		dbconn.closeDB()
	    else:
		# dependency does not exist in our database
		unsatisfiedDeps.add(dependency)
		continue

	    clientMatch = clientDbconn.atomMatch(dependency)
	    if clientMatch[0] != -1:
		
		installedVer = clientDbconn.retrieveVersion(clientMatch[0])
		installedTag = clientDbconn.retrieveVersionTag(clientMatch[0])
		installedRev = clientDbconn.retrieveRevision(clientMatch[0])
                if installedRev == 9999: # any revision is fine
                    repo_pkgrev = 9999
		
		if (deepdeps):
		    vcmp = entropyCompareVersions((repo_pkgver,repo_pkgtag,repo_pkgrev),(installedVer,installedTag,installedRev))
		    if vcmp != 0:
			filterSatisfiedDependenciesCmpResults[dependency] = vcmp
	                depunsatisfied.add(dependency)
		    else:
		        depsatisfied.add(dependency)
		else:
		    depsatisfied.add(dependency)
	    else:
		# not installed
		filterSatisfiedDependenciesCmpResults[dependency] = 0
		depunsatisfied.add(dependency)
	
	    
	    unsatisfiedDeps.update(depunsatisfied)
	    satisfiedDeps.update(depsatisfied)
	    
	    ''' caching '''
	    filterSatisfiedDependenciesCache[dependency] = {}
	    filterSatisfiedDependenciesCache[dependency]['depunsatisfied'] = depunsatisfied
	    filterSatisfiedDependenciesCache[dependency]['depsatisfied'] = depsatisfied
	    filterSatisfiedDependenciesCache[dependency]['deepdeps'] = deepdeps
    
        clientDbconn.closeDB()

    return unsatisfiedDeps, satisfiedDeps

'''
   @description: generates a dependency tree using unsatisfied dependencies
   @input package: atomInfo (idpackage,reponame)
   @output: dependency tree dictionary, plus status code
'''
generateDependencyTreeCache = {}
matchFilter = set()
def generateDependencyTree(atomInfo, emptydeps = False, deepdeps = False, usefilter = False):

    if (not usefilter):
	matchFilter.clear()

    ''' caching '''
    cached = generateDependencyTreeCache.get(tuple(atomInfo))
    if cached:
	if (cached['emptydeps'] == emptydeps) and \
	    (cached['deepdeps'] == deepdeps) and \
	    (cached['usefilter'] == usefilter):
	    return cached['result']

    #print atomInfo
    mydbconn = openRepositoryDatabase(atomInfo[1])
    myatom = mydbconn.retrieveAtom(atomInfo[0])
    mydbconn.closeDB()

    # caches
    treecache = set()
    matchcache = set()
    # special events
    dependenciesNotFound = set()
    conflicts = set()

    mydep = (1,myatom)
    mybuffer = lifobuffer()
    deptree = set()
    if not ((atomInfo in matchFilter) and (usefilter)):
        mybuffer.push((1,myatom))
        #mytree.append((1,myatom))
        deptree.add((1,atomInfo))
    clientDbconn = openClientDatabase()

    
    while mydep != None:

        # already analyzed in this call
        if mydep[1] in treecache:
            mydep = mybuffer.pop()
            continue

        # conflicts
        if mydep[1][0] == "!":
            xmatch = clientDbconn.atomMatch(mydep[1][1:])
            if xmatch[0] != -1:
                conflicts.add(xmatch[0])
            mydep = mybuffer.pop()
            continue

        # atom found?
        match = atomMatch(mydep[1])
        if match[0] == -1:
            dependenciesNotFound.add(mydep[1])
            mydep = mybuffer.pop()
            continue

        # check if atom has been already pulled in
        matchdb = openRepositoryDatabase(match[1])
        matchatom = matchdb.retrieveAtom(match[0])
        matchdb.closeDB()
        if matchatom in treecache:
            mydep = mybuffer.pop()
            continue
        else:
            treecache.add(matchatom)

        treecache.add(mydep[1])

        # already analyzed by the calling function
        if (match in matchFilter) and (usefilter):
            mydep = mybuffer.pop()
            continue
        if usefilter: matchFilter.add(match)

        # result already analyzed?
        if match in matchcache:
            mydep = mybuffer.pop()
            continue

        treedepth = mydep[0]+1

        # all checks passed, well done
        matchcache.add(match)
        deptree.add((mydep[0],match)) # add match

        myundeps = getDependencies(match)
        # in this way filterSatisfiedDependenciesCmpResults is alway consistent
        mytestdeps, xxx = filterSatisfiedDependencies(myundeps, deepdeps = deepdeps)
        if (not emptydeps):
            myundeps = mytestdeps
        for x in myundeps:
            mybuffer.push((treedepth,x))

        # handle possible library breakage
        action = filterSatisfiedDependenciesCmpResults.get(mydep)
        if action and ((action < 0) or (action > 0)): # do not use != 0 since action can be "None"
            i = clientDbconn.atomMatch(mydep)
            if i[0] != -1:
                oldneeded = clientDbconn.retrieveNeeded(i[0])
                if oldneeded: # if there are needed
                    ndbconn = openRepositoryDatabase(atom[1])
                    needed = ndbconn.retrieveNeeded(atom[0])
                    ndbconn.closeDB()
                    oldneeded.difference_update(needed)
                    if oldneeded:
                        # reverse lookup to find belonging package
                        for need in oldneeded:
                            myidpackages = clientDbconn.searchNeeded(need)
                            for myidpackage in myidpackages:
                                myname = clientDbconn.retrieveName(myidpackage)
                                mycategory = clientDbconn.retrieveCategory(myidpackage)
                                myslot = clientDbconn.retrieveSlot(myidpackage)
                                mykey = mycategory+"/"+myname
                                mymatch = atomMatch(mykey, matchSlot = myslot) # search in our repo
                                if mymatch[0] != -1:
                                    mydbconn = openRepositoryDatabase(mymatch[1])
                                    mynewatom = mydbconn.retrieveAtom(mymatch[0])
                                    mydbconn.closeDB()
                                    if (mymatch not in matchcache) and (mynewatom not in treecache):
                                        mybuffer.push((treedepth,mynewatom))
                                else:
                                    # we bastardly ignore the missing library for now
                                    continue

        mydep = mybuffer.pop()

    newdeptree = {}
    for x in deptree:
        key = x[0]
        item = x[1]
        try:
            newdeptree[key].add(item)
        except:
            newdeptree[key] = set()
            newdeptree[key].add(item)
    del deptree
    
    clientDbconn.closeDB()
    
    if (dependenciesNotFound):
	# Houston, we've got a problem
	flatview = list(dependenciesNotFound)
	return flatview,-2

    # conflicts
    newdeptree[0] = conflicts

    ''' caching '''
    generateDependencyTreeCache[tuple(atomInfo)] = {}
    generateDependencyTreeCache[tuple(atomInfo)]['result'] = newdeptree,0
    generateDependencyTreeCache[tuple(atomInfo)]['emptydeps'] = emptydeps
    generateDependencyTreeCache[tuple(atomInfo)]['deepdeps'] = deepdeps
    generateDependencyTreeCache[tuple(atomInfo)]['usefilter'] = usefilter
    treecache.clear()
    matchcache.clear()
    
    return newdeptree,0 # note: newtree[0] contains possible conflicts


'''
   @description: generates a list cotaining the needed dependencies of a list requested atoms
   @input package: list of atoms that would be installed in list form, whose each element is composed by [idpackage,repository name]
   @output: list containing, for each element: [idpackage,repository name]
   		@ if dependencies couldn't be satisfied, the output will be -1
   @note: this is the function that should be used for 3rd party applications after using atomMatch()
'''
def getRequiredPackages(foundAtoms, emptydeps = False, deepdeps = False, spinning = False):
    deptree = {}
    deptree[0] = set()
    
    if spinning: atomlen = len(foundAtoms); count = 0
    matchFilter.clear() # clear generateDependencyTree global filter
    for atomInfo in foundAtoms:
	if spinning: count += 1; print_info(":: "+str(round((float(count)/atomlen)*100,1))+"% ::", back = True)
	#print depcount
	newtree, result = generateDependencyTree(atomInfo, emptydeps, deepdeps, usefilter = True)
	if (result != 0):
	    return newtree, result
	elif (newtree):
            parent_keys = deptree.keys()
            # add conflicts
            max_parent_key = parent_keys[-1]
            deptree[0].update(newtree[0])
            
            # reverse dict
            levelcount = 0
            reversetree = {}
            for key in newtree.keys()[::-1]:
                if key == 0:
                    continue
                levelcount += 1
                reversetree[levelcount] = newtree[key]
            del newtree
            
            for mylevel in reversetree.keys():
                deptree[max_parent_key+mylevel] = reversetree[mylevel].copy()
            del reversetree

    matchFilter.clear()
    
    return deptree,0


'''
   @description: generates a depends tree using provided idpackages (from client database)
   		 !!! you can see it as the function that generates the removal tree
   @input package: idpackages list
   @output: 	depends tree dictionary, plus status code
'''
def generateDependsTree(idpackages, deep = False):

    ''' caching '''
    cached = generateDependsTreeCache.get(tuple(idpackages))
    if cached:
	if (cached['deep'] == deep):
	    return cached['result']

    dependscache = {}
    clientDbconn = openClientDatabase()

    dependsOk = False
    treeview = set(idpackages)
    treelevel = idpackages[:]
    tree = {}
    treedepth = 0 # I start from level 1 because level 0 is idpackages itself
    tree[treedepth] = set(idpackages)
    monotree = set(idpackages) # monodimensional tree
    
    # check if dependstable is sane before beginning
    rx = clientDbconn.retrieveDepends(idpackages[0])
    if rx == -2:
	# generation needed
	clientDbconn.regenerateDependsTable(output = False)
        rx = clientDbconn.retrieveDepends(idpackages[0])
    
    while (not dependsOk):
	treedepth += 1
	tree[treedepth] = set()
        for idpackage in treelevel:

	    passed = dependscache.get(idpackage,None)
	    systempkg = clientDbconn.isSystemPackage(idpackage)
	    if passed or systempkg:
		try:
		    while 1: treeview.remove(idpackage)
		except:
		    pass
		continue

	    # obtain its depends
	    depends = clientDbconn.retrieveDepends(idpackage)
	    # filter already satisfied ones
	    depends = [x for x in depends if x not in list(monotree)]
	    if (depends): # something depends on idpackage
		for x in depends:
		    if x not in tree[treedepth]:
			tree[treedepth].add(x)
			monotree.add(x)
		        treeview.add(x)
	    elif deep: # if deep, grab its dependencies and check
		
	        mydeps = set(clientDbconn.retrieveDependencies(idpackage))
		_mydeps = set()
		for x in mydeps:
		    match = clientDbconn.atomMatch(x)
		    if match and match[1] == 0:
		        _mydeps.add(match[0])
		mydeps = _mydeps
		# now filter them
		mydeps = [x for x in mydeps if x not in list(monotree)]
		for x in mydeps:
		    #print clientDbconn.retrieveAtom(x)
		    mydepends = clientDbconn.retrieveDepends(x)
		    mydepends = [y for y in mydepends if y not in list(monotree)]
		    if (not mydepends):
			tree[treedepth].add(x)
			monotree.add(x)
			treeview.add(x)

	    dependscache[idpackage] = True
	    try:
		while 1: treeview.remove(idpackage)
	    except:
	        pass
	
	treelevel = list(treeview)[:]
	if (not treelevel):
	    if not tree[treedepth]:
		del tree[treedepth] # probably the last one is empty then
	    dependsOk = True

    newtree = tree.copy() # tree list
    if (tree):
	# now filter newtree
	treelength = len(newtree)
	for count in range(treelength)[::-1]:
	    x = 0
	    while x < count:
		# remove dups in this list
		for z in newtree[count]:
		    try:
			while 1:
			    newtree[x].remove(z)
			    #print "removing "+str(z)
		    except:
			pass
		x += 1
    
    del tree
    
    clientDbconn.closeDB()
    
    ''' caching '''
    generateDependsTreeCache[tuple(idpackages)] = {}
    generateDependsTreeCache[tuple(idpackages)]['result'] = newtree,0
    generateDependsTreeCache[tuple(idpackages)]['deep'] = deep
    return newtree,0 # treeview is used to show deps while tree is used to run the dependency code.


########################################################
####
##   Files handling
#

'''
   @description: check if Equo has to download the given package
   @input package: filename to check inside the packages directory -> file, checksum of the package -> checksum
   @output: -1 = should be downloaded, -2 = digest broken (not mandatory), remove & download, 0 = all fine, we don't need to download it
'''
def checkNeededDownload(filepath,checksum = None):
    # is the file available
    if os.path.isfile(etpConst['entropyworkdir']+"/"+filepath):
	if checksum is None:
	    return 0
	else:
	    # check digest
	    md5res = compareMd5(etpConst['entropyworkdir']+"/"+filepath,checksum)
	    if (md5res):
		return 0
	    else:
		return -2
    else:
	return -1


'''
   @description: download a package into etpConst['packagesbindir'] passing all the available mirrors
   @input package: repository -> name of the repository, filename -> name of the file to download, digest -> md5 hash of the file
   @output: 0 = all fine, -3 = error on all the available mirrors
'''
def fetchFileOnMirrors(repository, filename, digest = False):

    uris = etpRepositories[repository]['packages'][::-1]
    remaining = set(uris[:])

    mirrorcount = 0
    for uri in uris:
	
	if not remaining:
	    # tried all the mirrors, quitting for error
	    return -3
	mirrorcount += 1
	mirrorCountText = "( mirror #"+str(mirrorcount)+" ) "
        # now fetch the new one
	url = uri+"/"+filename
	print_info(red("   ## ")+mirrorCountText+blue("Downloading from: ")+red(spliturl(url)[1]))
	rc = fetchFile(url, digest)
	if rc == 0:
	    print_info(red("   ## ")+mirrorCountText+blue("Successfully downloaded from: ")+red(spliturl(url)[1])+blue(" at "+str(bytesIntoHuman(etpFileTransfer['datatransfer']))+"/sec"))
	    return 0
	else:
	    # something bad happened
	    if rc == -1:
		print_info(red("   ## ")+mirrorCountText+blue("Error downloading from: ")+red(spliturl(url)[1])+" - file not available on this mirror.")
	    elif rc == -2:
		print_info(red("   ## ")+mirrorCountText+blue("Error downloading from: ")+red(spliturl(url)[1])+" - wrong checksum.")
	    elif rc == -3:
		print_info(red("   ## ")+mirrorCountText+blue("Error downloading from: ")+red(spliturl(url)[1])+" - not found.")
	    elif rc == -4:
		print_info(red("   ## ")+mirrorCountText+blue("Discarded download."))
		return -1
	    else:
		print_info(red("   ## ")+mirrorCountText+blue("Error downloading from: ")+red(spliturl(url)[1])+" - unknown reason.")
	    remaining.remove(uri)

'''
   @description: download a package into etpConst['packagesbindir'] and check for digest if digest is not False
   @input package: url -> HTTP/FTP url, digest -> md5 hash of the file
   @output: -1 = download error (cannot find the file), -2 = digest error, 0 = all fine
'''
def fetchFile(url, digest = False):
    # remove old
    filename = os.path.basename(url)
    filepath = etpConst['packagesbindir']+"/"+etpConst['branch']+"/"+filename
    if os.path.exists(filepath):
	os.remove(filepath)

    # now fetch the new one
    try:
        fetchChecksum = downloadData(url,filepath)
    except KeyboardInterrupt:
	return -4
    except:
	return -1
    if fetchChecksum == "-3":
	return -3
    if (digest != False):
	#print digest+" <--> "+fetchChecksum
	if (fetchChecksum != digest):
	    # not properly downloaded
	    return -2
	else:
	    return 0
    return 0

def matchChecksum(infoDict):
    dlcount = 0
    match = False
    while dlcount <= 5:
	print_info(red("   ## ")+blue("Checking package checksum..."), back = True)
	dlcheck = checkNeededDownload(infoDict['download'], checksum = infoDict['checksum'])
	if dlcheck == 0:
	    print_info(red("   ## ")+blue("Package checksum matches."))
	    match = True
	    break # file downloaded successfully
	else:
	    dlcount += 1
	    print_info(red("   ## ")+blue("Package checksum does not match. Redownloading... attempt #"+str(dlcount)), back = True)
	    fetch = fetchFileOnMirrors(infoDict['repository'],infoDict['download'],infoDict['checksum'])
	    if fetch != 0:
		print_info(red("   ## ")+blue("Cannot properly fetch package! Quitting."))
		return 1
    if (not match):
	print_info(red("   ## ")+blue("Cannot properly fetch package or checksum does not match. Try running again '")+bold("equo update")+blue("'"))
	return 1
    return 0

def removePackage(infoDict):
    
    atom = infoDict['removeatom']
    content = infoDict['removecontent']
    removeidpackage = infoDict['removeidpackage']
    clientDbconn = openClientDatabase()

    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing package: "+str(atom))

    # clear on-disk cache
    generateDependsTreeCache.clear()
    dumpTools.dumpobj(etpCache['generateDependsTree'],generateDependsTreeCache)

    # remove from database
    if removeidpackage != -1:
	print_info(red("   ## ")+blue("Removing from database: ")+red(infoDict['removeatom']))
	removePackageFromDatabase(removeidpackage)

    # Handle gentoo database
    if (etpConst['gentoo-compat']):
	gentooAtom = dep_striptag(remove_tag(atom)) # FIXME: remove dep_striptag asap
        equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing package from Gentoo database: "+str(gentooAtom))
	removePackageFromGentooDatabase(gentooAtom)

    # load CONFIG_PROTECT and its mask - client database at this point has been surely opened, so our dicts are already filled
    protect = etpConst['dbconfigprotect']
    mask = etpConst['dbconfigprotectmask']
    
    # remove files from system
    directories = set()
    for file in content:
        # collision check
        if etpConst['collisionprotect'] > 0:
            
            if clientDbconn.isFileAvailable(file) and os.path.isfile(file): # in this way we filter out directories
                print_warning(darkred("   ## ")+red("Collision found during remove for ")+file+red(" - cannot overwrite"))
                equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Collision found during remove for "+file+" - cannot overwrite")
                continue
    
        protected = False
        if (not infoDict['removeconfig']) and (not infoDict['diffremoval']):
            try:
                # -- CONFIGURATION FILE PROTECTION --
                if os.access(file,os.R_OK):
                    for x in protect:
                        if file.startswith(x):
                            protected = True
                            break
                    if (protected):
                        for x in mask:
                            if file.startswith(x):
                                protected = False
                                break
                    if (protected) and os.path.isfile(file):
                        protected = istextfile(file)
                    else:
                        protected = False # it's not a file
                # -- CONFIGURATION FILE PROTECTION --
            except:
                pass # some filenames are buggy encoded
        
        
        if (protected):
            equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"[remove] Protecting config file: "+file)
            print_warning(darkred("   ## ")+red("[remove] Protecting config file: ")+file)
        else:
            try:
                os.lstat(file)
            except OSError:
                continue # skip file, does not exist
            
            if os.path.isdir(file) and os.path.islink(file): # S_ISDIR returns False for directory symlinks, so using os.path.isdir
                # valid directory symlink
                #print "symlink dir",file
                directories.add((file,"link"))
            elif os.path.isdir(file):
                # plain directory
                #print "plain dir",file
                directories.add((file,"dir"))
            else: # files, symlinks or not
                # just a file or symlink or broken directory symlink (remove now)
                try:
                    #print "plain file",file
                    os.remove(file)
                    # add its parent directory
                    dirfile = os.path.dirname(file)
                    if os.path.isdir(dirfile) and os.path.islink(dirfile):
                        #print "symlink dir2",dirfile
                        directories.add((dirfile,"link"))
                    elif os.path.isdir(dirfile):
                        #print "plain dir2",dirfile
                        directories.add((dirfile,"dir"))
                except OSError:
                    pass

    # now handle directories
    directories = list(directories)
    directories.reverse()
    while 1:
        taint = False
        for directory in directories:
            if directory[1] == "link":
                try:
                    mylist = os.listdir(directory[0])
                    if not mylist:
                        try:
                            os.remove(directory[0])
                            taint = True
                        except OSError:
                            pass
                except OSError:
                    pass
            elif directory[1] == "dir":
                try:
                    mylist = os.listdir(directory[0])
                    if not mylist:
                        try:
                            os.rmdir(directory[0])
                            taint = True
                        except OSError:
                            pass
                except OSError:
                    pass

        if not taint:
            break

    clientDbconn.closeDB()
    return 0


'''
   @description: unpack the given file on the system, update database and also update gentoo db if requested
   @input package: package file (without path)
   @output: 0 = all fine, >0 = error!
'''
def installPackage(infoDict):
    
    clientDbconn = openClientDatabase()
    package = infoDict['download']

    # clear on-disk cache
    generateDependsTreeCache.clear()
    dumpTools.dumpobj(etpCache['generateDependsTree'],{})

    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Installing package: "+str(infoDict['atom']))

    # unpack and install
    if infoDict['repository'].endswith(".tbz2"):
        pkgpath = etpRepositories[infoDict['repository']]['pkgpath']
    else:
        pkgpath = etpConst['entropyworkdir']+"/"+package
    unpackDir = etpConst['entropyunpackdir']+"/"+package
    if os.path.isdir(unpackDir):
	shutil.rmtree(unpackDir)
    imageDir = unpackDir+"/image"
    os.makedirs(imageDir)

    rc = uncompressTarBz2(pkgpath,imageDir, catchEmpty = True)
    if (rc != 0):
	return rc
    if not os.path.isdir(imageDir):
	return 2

    # load CONFIG_PROTECT and its mask
    protect = etpRepositories[infoDict['repository']]['configprotect']
    mask = etpRepositories[infoDict['repository']]['configprotectmask']

    packageContent = []
    # setup imageDir properly
    imageDir = imageDir.encode(getfilesystemencoding())
    
    # merge data into system
    for currentdir,subdirs,files in os.walk(imageDir):
	# create subdirs
        for dir in subdirs:
	    
            imagepathDir = currentdir + "/" + dir
	    rootdir = imagepathDir[len(imageDir):]
	    
            # handle broken symlinks
            if os.path.islink(rootdir) and not os.path.exists(rootdir):# broken symlink
                os.remove(rootdir)
            
            # if our directory is a file on the live system
            elif os.path.isfile(rootdir): # really weird...!
                equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"WARNING!!! "+rootdir+" is a file when it should be a directory !! Removing in 10 seconds...")
                print_warning(red(" *** ")+bold(rootdir)+red(" is a file when it should be a directory !! Removing in 10 seconds..."))
                import time
                time.sleep(10)
                os.remove(rootdir)
            
            # if our directory is a symlink instead, then copy the symlink
            if os.path.islink(imagepathDir) and not os.path.isdir(rootdir): # for security we skip live items that are dirs
                tolink = os.readlink(imagepathDir)
                if os.path.islink(rootdir):
                    os.remove(rootdir)
                os.symlink(tolink,rootdir)
            elif (not os.path.isdir(rootdir)) and (not os.access(rootdir,os.R_OK)):
                #print "creating dir "+rootdir
                os.makedirs(rootdir)
            
            if not os.path.islink(rootdir): # symlink don't need permissions, also until os.walk ends they might be broken
                user = os.stat(imagepathDir)[4]
                group = os.stat(imagepathDir)[5]
                os.chown(rootdir,user,group)
                shutil.copystat(imagepathDir,rootdir)
	
        for file in files:
	    fromfile = currentdir+"/"+file
	    tofile = fromfile[len(imageDir):]
	    
	    if etpConst['collisionprotect'] > 1:
		if clientDbconn.isFileAvailable(tofile):
		    print_warning(darkred("   ## ")+red("Collision found during install for ")+tofile+" - cannot overwrite")
    		    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"WARNING!!! Collision found during install for "+tofile+" - cannot overwrite")
    		    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[collision] Protecting config file: "+tofile)
		    print_warning(darkred("   ## ")+red("[collision] Protecting config file: ")+tofile)
		    continue

	    # -- CONFIGURATION FILE PROTECTION --
	    protected = False

	    try:
	        for x in protect:
		    if tofile.startswith(x):
		        protected = True
		        break
	        if (protected): # check if perhaps, file is masked, so unprotected
		    for x in mask:
		        if tofile.startswith(x):
			    protected = False
			    break
	    
	        if not os.path.lexists(tofile):
		    protected = False # file doesn't exist

	        # check if it's a text file
	        if (protected) and os.path.isfile(tofile):
		    protected = istextfile(tofile)
	        else:
		    protected = False # it's not a file

	        # request new tofile then
	        if (protected):
                    if tofile not in etpConst['configprotectskip']:
                        tofile, prot_status = allocateMaskedFile(tofile, fromfile)
                        if not prot_status:
                            protected = False
                        else:
                            equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Protecting config file: "+tofile)
                            print_warning(darkred("   ## ")+red("Protecting config file: ")+tofile)
                    else:
                        equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Skipping config file installation, as stated in equo.conf: "+tofile)
                        print_warning(darkred("   ## ")+red("Skipping file installation: ")+tofile)
                        continue
	    
	        # -- CONFIGURATION FILE PROTECTION --
	
	    except:
	        pass # some files are buggy encoded

	    try:
		# this also handles symlinks
		shutil.move(fromfile,tofile)
	    except IOError,(errno,strerror):
		if errno == 2:
		    # better to pass away, sometimes gentoo packages are fucked up and contain broken things
		    pass
		else:
		    rc = os.system("mv "+fromfile+" "+tofile)
		    if (rc != 0):
		        return 4
		    packageContent.append(tofile)
	    try:
	        user = os.stat(fromfile)[4]
	        group = os.stat(fromfile)[5]
	        os.chown(tofile,user,group)
	        shutil.copystat(fromfile,tofile)
	    except:
		pass # sometimes, gentoo packages are fucked up and contain broken symlinks
	    
	    if (protected):
		# add to disk cache
		confTools.addtocache(tofile)

    # inject into database
    print_info(red("   ## ")+blue("Updating database with: ")+red(infoDict['atom']))

    newidpackage = installPackageIntoDatabase(infoDict['idpackage'], infoDict['repository'])

    # remove old files and gentoo stuff
    if (infoDict['removeidpackage'] != -1):
	# doing a diff removal
	equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Remove old package: "+str(infoDict['removeatom']))
	infoDict['removeidpackage'] = -1 # disabling database removal
	if (etpConst['gentoo-compat']):
	    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing Gentoo database entry for "+str(infoDict['removeatom']))
	    print_info(red("   ## ")+blue("Cleaning old package files...")+" ## w/Gentoo compatibility")
	else:
	    print_info(red("   ## ")+blue("Cleaning old package files..."))
	removePackage(infoDict)

    clientDbconn.closeDB()

    rc = 0
    if (etpConst['gentoo-compat']):
	equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Installing new Gentoo database entry: "+str(infoDict['atom']))
	rc = installPackageIntoGentooDatabase(infoDict,pkgpath, newidpackage = newidpackage)
    
    # remove unpack dir
    shutil.rmtree(unpackDir,True)
    return rc

'''
   @description: remove package entry from Gentoo database
   @input gentoo package atom (cat/name+ver):
   @output: 0 = all fine, <0 = error!
'''
def removePackageFromGentooDatabase(atom):

    # handle gentoo-compat
    _portage_avail = False
    try:
	from portageTools import getPortageAppDbPath as _portage_getPortageAppDbPath, getInstalledAtoms as _portage_getInstalledAtoms
	_portage_avail = True
    except:
	return -1 # no Portage support

    if (_portage_avail):
	portDbDir = _portage_getPortageAppDbPath()
	removePath = portDbDir+atom
	#print removePath
	try:
	    shutil.rmtree(removePath,True)
	except:
	    pass
	key = dep_getkey(atom)
	othersInstalled = _portage_getInstalledAtoms(key) #FIXME: really slow
	if othersInstalled == None:
	    # safest way (error free) is to use sed without loading the file
	    # escape /
	    skippedKey = ''
	    for x in key:
		if x == "/":
		    x = "\/"
		skippedKey += x
	    os.system("sed -i '/"+skippedKey+"/d' /var/lib/portage/world")

    return 0

'''
   @description: inject the database information into the Gentoo database
   @input package: dictionary containing information collected by installPackages (important are atom, slot, category, name, version)
   @output: 0 = all fine, >0 = error!
'''
def installPackageIntoGentooDatabase(infoDict,packageFile, newidpackage = -1):
    
    # handle gentoo-compat
    _portage_avail = False
    try:
	from portageTools import getPackageSlot as _portage_getPackageSlot, getPortageAppDbPath as _portage_getPortageAppDbPath, refillCounter as _portage_refillCounter
	_portage_avail = True
    except:
	return -1 # no Portage support
    if (_portage_avail):
	portDbDir = _portage_getPortageAppDbPath()
	# extract xpak from unpackDir+etpConst['packagecontentdir']+"/"+package
	key = infoDict['category']+"/"+infoDict['name']
	#print _portage_getInstalledAtom(key)
	atomsfound = set()
	for xdir in os.listdir(portDbDir):
	    if (xdir == infoDict['category']):
		for ydir in os.listdir(portDbDir+"/"+xdir):
		    if (key == dep_getkey(xdir+"/"+ydir)):
			atomsfound.add(xdir+"/"+ydir)
	
	# atomsfound = _portage_getInstalledAtoms(key) too slow!
	
	### REMOVE
	# parse slot and match and remove)
	if atomsfound:
	    pkgToRemove = ''
	    for atom in atomsfound:
	        atomslot = _portage_getPackageSlot(atom)
		# get slot from gentoo db
	        if atomslot == infoDict['slot']:
		    #print "match slot, remove -> "+str(atomslot)
		    pkgToRemove = atom
		    break
	    if (pkgToRemove):
	        removePath = portDbDir+pkgToRemove
	        os.system("rm -rf "+removePath)
	        #print "removing -> "+removePath
	
	### INSTALL NEW
	extractPath = etpConst['entropyunpackdir']+"/"+os.path.basename(packageFile)+"/xpak"
        if os.path.isfile(etpConst['entropyunpackdir']+"/"+os.path.basename(packageFile)):
            os.remove(etpConst['entropyunpackdir']+"/"+os.path.basename(packageFile))
	if os.path.isdir(extractPath):
	    shutil.rmtree(extractPath)
	else:
	    os.makedirs(extractPath)
        
        smartpackage = False
        if infoDict['repository'].endswith(".tbz2"):
            smartpackage = etpRepositories[infoDict['repository']]['smartpackage']
        
        if (smartpackage):
            # we need to get the .xpak from database
            xdbconn = openRepositoryDatabase(infoDict['repository'])
            xpakdata = xdbconn.retrieveXpakMetadata(infoDict['idpackage'])
            if xpakdata:
                # save into a file
                f = open(extractPath+".xpak","wb")
                f.write(xpakdata)
                f.flush()
                f.close()
                xpakstatus = unpackXpak(extractPath+".xpak",extractPath)
            else:
                xpakstatus = None
            xdbconn.closeDB()
        else:
            xpakstatus = extractXpak(packageFile,extractPath)
        if xpakstatus != None:
            if not os.path.isdir(portDbDir+infoDict['category']):
                os.makedirs(portDbDir+infoDict['category'])
            destination = portDbDir+infoDict['category']+"/"+infoDict['name']+"-"+infoDict['version']
            if os.path.isdir(destination):
                shutil.rmtree(destination)
            
            os.rename(extractPath,destination)
            
            # test if /var/cache/edb/counter is fine
            if os.path.isfile(edbCOUNTER):
                try:
                    f = open(edbCOUNTER,"r")
                    counter = int(f.readline().strip())
                    f.close()
                except:
                    # need file recreation, parse gentoo tree
                    counter = _portage_refillCounter()
            else:
                counter = _portage_refillCounter()
            
            # write new counter to file
            if os.path.isdir(destination):
                counter += 1
                f = open(destination+"/"+dbCOUNTER,"w")
                f.write(str(counter)+"\n")
                f.flush()
                f.close()
                f = open(edbCOUNTER,"w")
                f.write(str(counter))
                f.flush()
                f.close()
                # update counter inside clientDatabase
                clientDbconn = openClientDatabase()
                clientDbconn.setCounter(newidpackage,counter)
                clientDbconn.closeDB()
            else:
                print "DEBUG: WARNING!! "+destination+" DOES NOT EXIST, CANNOT UPDATE COUNTER!!"

    return 0

'''
   @description: injects package info into the installed packages database
   @input int(idpackage): idpackage matched into repository
   @input str(repository): name of the repository where idpackage is
   @output: 0 = all fine, >0 = error!
'''
def installPackageIntoDatabase(idpackage, repository):

    # fetch info
    dbconn = openRepositoryDatabase(repository)
    data = dbconn.getPackageData(idpackage)
    dbconn.closeDB()
    # open client db
    clientDbconn = openClientDatabase()

    idpk, rev, x, status = clientDbconn.handlePackage(etpData = data, forcedRevision = data['revision'])
    del x
    
    if (not status):
	print "DEBUG!!! THIS SHOULD NOT NEVER HAPPEN. Package "+str(idpk)+" has not been inserted, status: "+str(status)
	idpk = -1 # it hasn't been insterted ? why??
    else: # all fine

        # add idpk to the installedtable
        clientDbconn.removePackageFromInstalledTable(idpk)
        clientDbconn.addPackageToInstalledTable(idpk,repository)
	# update dependstable
	try:
	    depends = clientDbconn.listIdpackageDependencies(idpk)
	    for depend in depends:
		atom = depend[1]
		iddep = depend[0]
		match = clientDbconn.atomMatch(atom)
		if (match[0] != -1):
		    clientDbconn.removeDependencyFromDependsTable(iddep)
		    clientDbconn.addDependRelationToDependsTable(iddep,match[0])

	except:
	    clientDbconn.regenerateDependsTable()

    clientDbconn.closeDB()
    return idpk

'''
   @description: remove the package from the installed packages database..
   		 This function is a wrapper around databaseTools.removePackage that will let us to add our custom things
   @input int(idpackage): idpackage matched into repository
   @output: 0 = all fine, >0 = error!
'''
def removePackageFromDatabase(idpackage):
    
    clientDbconn = openClientDatabase()
    clientDbconn.removePackage(idpackage)
    clientDbconn.closeDB()
    return 0



'''
    @description: execute the requested step (it is only used by the CLI client)
    @input: 	step -> name of the step to execute
    		infoDict -> dictionary containing all the needed information collected by installPackages() -> actionQueue[pkgatom]
                loopString -> used to print to xterm title bar something like "10/900 - equo"
    @output:	-1,"description" for error ; 0,True for no errors
'''
def stepExecutor(step, infoDict, loopString = None):

    clientDbconn = openClientDatabase()
    output = 0
    
    if step == "fetch":
	print_info(red("   ## ")+blue("Fetching archive: ")+red(os.path.basename(infoDict['download'])))
        xtermTitle(loopString+' Fetching archive: '+os.path.basename(infoDict['download']))
	output = fetchFileOnMirrors(infoDict['repository'],infoDict['download'],infoDict['checksum'])
	if output < 0:
	    print_error(red("Package cannot be fetched. Try to run: '")+bold("equo update")+red("' and this command again. Error "+str(output)))
    
    elif step == "checksum":
	output = matchChecksum(infoDict)
    
    elif step == "install":
        compatstring = ''
	if (etpConst['gentoo-compat']):
            compatstring = " ## w/Gentoo compatibility"
	print_info(red("   ## ")+blue("Installing package: ")+red(os.path.basename(infoDict['atom']))+compatstring)
        xtermTitle(loopString+' Installing package: '+os.path.basename(infoDict['atom'])+compatstring)
	output = installPackage(infoDict)
	if output != 0:
	    if output == 512:
	        errormsg = red("You are running out of disk space. I bet, you're probably Michele. Error 512")
	    else:
	        errormsg = red("An error occured while trying to install the package. Check if your hard disk is healthy. Error "+str(output))
	    print_error(errormsg)
    
    elif step == "remove":
	gcompat = ""
	if (etpConst['gentoo-compat']):
	    gcompat = " ## w/Gentoo compatibility"
	print_info(red("   ## ")+blue("Removing installed package: ")+red(infoDict['removeatom'])+gcompat)
        xtermTitle(loopString+' Removing installed package: '+os.path.basename(infoDict['removeatom'])+gcompat)
	output = removePackage(infoDict)
	if output != 0:
	    errormsg = red("An error occured while trying to remove the package. Check if you have enough disk space on your hard disk. Error "+str(output))
	    print_error(errormsg)
    
    elif step == "showmessages":
	# get messages
	if infoDict['messages']:
	    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Message from "+infoDict['atom']+" :")
	for msg in infoDict['messages']:
	    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,msg)
	    print_warning(brown('   ## ')+msg)
	if infoDict['messages']:
	    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"End message.")
    
    elif step == "postinstall":
	# analyze atom
	pkgdata = etpInstallTriggers.get(infoDict['atom'])
	if pkgdata:
	    triggers = triggerTools.postinstall(pkgdata)
	    for trigger in triggers: # code reuse, we'll fetch triggers list on the GUI client and run each trigger by itself
		eval("triggerTools."+trigger)(pkgdata)

    elif step == "preinstall":
	# analyze atom
	pkgdata = etpInstallTriggers.get(infoDict['atom'])
	if pkgdata:
	    triggers = triggerTools.preinstall(pkgdata)
	    for trigger in triggers: # code reuse, we'll fetch triggers list on the GUI client and run each trigger by itself
		eval("triggerTools."+trigger)(pkgdata)

    elif step == "preremove":
	# analyze atom
	remdata = etpRemovalTriggers.get(infoDict['removeatom'])
	if remdata:
	    triggers = triggerTools.preremove(remdata)

	    if infoDict['diffremoval']: # diffremoval is true only when the remove action is triggered by installPackages()
		pkgdata = etpRemovalTriggers.get(infoDict['atom'])
		if pkgdata:
	            # preinstall script shouldn't doulbe run on preremove
		    itriggers = triggerTools.preinstall(pkgdata)
		    triggers.difference_update(itriggers)

	    for trigger in triggers: # code reuse, we'll fetch triggers list on the GUI client and run each trigger by itself
		eval("triggerTools."+trigger)(remdata)

    elif step == "postremove":
	# analyze atom
	remdata = etpRemovalTriggers.get(infoDict['removeatom'])
	if remdata:
	    triggers = triggerTools.postremove(remdata)
	    
	    if infoDict['diffremoval']: # diffremoval is true only when the remove action is triggered by installPackages()
		pkgdata = etpRemovalTriggers.get(infoDict['atom'])
		if pkgdata:
	            # postinstall script shouldn't doulbe run on postremove
		    itriggers = triggerTools.postinstall(pkgdata)
		    triggers.difference_update(itriggers)
	    
	    for trigger in triggers: # code reuse, we'll fetch triggers list on the GUI client and run each trigger by itself
		eval("triggerTools."+trigger)(remdata)
    
    clientDbconn.closeDB()
    
    return output
