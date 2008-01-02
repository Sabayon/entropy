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

import time
import shutil
import gc
from entropyConstants import *
from clientConstants import *
from outputTools import *
import exceptionTools


'''
    Main Entropy (client side) package management class
'''
class EquoInterface(TextInterface):

    '''
        @input indexing(bool): enable/disable database tables indexing
        @input noclientdb(bool): if enabled, client database non-existance will be ignored
        @input xcache(bool): enable/disable database caching
    '''
    def __init__(self, indexing = True, noclientdb = False, xcache = True):

        # Logging initialization
        import logTools
        self.equoLog = logTools.LogFile(level = etpConst['equologlevel'],filename = etpConst['equologfile'], header = "[Equo]")

        import dumpTools
        self.dumpTools = dumpTools
        import databaseTools
        self.databaseTools = databaseTools
        import entropyTools
        self.entropyTools = entropyTools
        import confTools
        self.confTools = confTools
        import triggerTools
        self.triggerTools = triggerTools
        from remoteTools import urlFetcher
        self.urlFetcher = urlFetcher # in this way, can be reimplemented (so you can override updateProgress)
        self.indexing = indexing
        self.noclientdb = noclientdb
        self.xcache = xcache
        self.openClientDatabase()
        self.repoDbCache = {}

    def switchChroot(self, chroot = ""):
        # clean caches
        self.purge_cache()
        const_resetCache()
        if chroot.endswith("/"):
            chroot = chroot[:-1]
        etpSys['rootdir'] = chroot
        initConfig_entropyConstants(etpSys['rootdir'])
        initConfig_clientConstants()

    def reopenClientDbconn(self):
        self.clientDbconn.closeDB()
        self.openClientDatabase()

    def closeAllRepositoryDatabases(self):
        for item in self.repoDbCache:
            self.repoDbCache[item].closeDB()
            del self.repoDbCache[item]
        self.repoDbCache.clear()

    def openClientDatabase(self):
        self.clientDbconn = self.databaseTools.openClientDatabase(indexing = self.indexing, 
                                                                    generate = self.noclientdb, 
                                                                    xcache = self.xcache
                                                                )

    def openRepositoryDatabase(self, repoid):
        if not self.repoDbCache.has_key((repoid,etpConst['systemroot'])):
            dbconn = self.databaseTools.openRepositoryDatabase(repoid, xcache = self.xcache, indexing = self.indexing)
            self.repoDbCache[(repoid,etpConst['systemroot'])] = dbconn
            return dbconn
        else:
            return self.repoDbCache.get((repoid,etpConst['systemroot']))

    def openGenericDatabase(self, dbfile, dbname = None, xcache = None, readOnly = False):
        if xcache == None:
            xcache = self.xcache
        dbconn = self.databaseTools.openGenericDatabase(dbfile, 
                                                        dbname = dbname, 
                                                        xcache = xcache, 
                                                        indexing = self.indexing,
                                                        readOnly = readOnly
                                                    )
        return dbconn

    def listAllAvailableBranches(self):
        branches = set()
        for repo in etpRepositories:
            dbconn = self.openRepositoryDatabase(repo)
            branches.update(dbconn.listAllBranches())
        return branches


    '''
       Cache stuff :: begin
    '''
    def purge_cache(self):
        dumpdir = etpConst['dumpstoragedir']
        if not dumpdir.endswith("/"): dumpdir = dumpdir+"/"
        for key in etpCache:
            cachefile = dumpdir+etpCache[key]+"*.dmp"
            self.updateProgress(darkred("Cleaning %s...") % (cachefile,), importance = 1, type = "warning", back = True)
            try:
                os.system("rm -f "+cachefile)
            except:
                pass
        # reset dict cache
        self.updateProgress(darkgreen("Cache is now empty."), importance = 2, type = "info")
        const_resetCache()

    def generate_cache(self, depcache = True, configcache = True):
        # clean first of all
        self.purge_cache()
        if depcache:
            self.do_depcache()
        if configcache:
            self.do_configcache()

    def do_configcache(self):
        self.updateProgress(darkred("Configuration files"), importance = 2, type = "warning")
        self.updateProgress(red("Scanning hard disk"), importance = 1, type = "warning")
        self.confTools.scanfs(dcache = False)
        self.updateProgress(darkred("Cache generation complete."), importance = 2, type = "info")

    def do_depcache(self):
        self.updateProgress(darkred("Dependencies"), importance = 2, type = "warning")
        self.updateProgress(darkred("Scanning repositories"), importance = 2, type = "warning")
        names = set()
        keys = set()
        depends = set()
        atoms = set()
        for reponame in etpRepositories:
            self.updateProgress(darkgreen("Scanning %s" % (etpRepositories[reponame]['description'],)) , importance = 1, type = "info", back = True)
            # get all packages keys
            try:
                dbconn = self.openRepositoryDatabase(reponame)
            except exceptionTools.RepositoryError:
                self.updateProgress(darkred("Cannot download/access: %s" % (etpRepositories[reponame]['description'],)) , importance = 2, type = "error")
                continue
            pkgdata = dbconn.listAllPackages()
            pkgdata = set(pkgdata)
            for info in pkgdata:
                key = self.entropyTools.dep_getkey(info[0])
                keys.add(key)
                names.add(key.split("/")[1])
                atoms.add(info[0])
            # dependencies
            pkgdata = dbconn.listAllDependencies()
            for info in pkgdata:
                depends.add(info[1])
            dbconn.closeDB()
            del dbconn

        self.updateProgress(darkgreen("Resolving metadata"), importance = 1, type = "warning")
        atomMatchCache.clear()
        maxlen = len(names)
        cnt = 0
        for name in names:
            cnt += 1
            self.updateProgress(darkgreen("Resolving name: %s") % (
                                                name
                                        ), importance = 0, type = "info", back = True, count = (cnt, maxlen) )
            self.atomMatch(name)
        maxlen = len(keys)
        cnt = 0
        for key in keys:
            cnt += 1
            self.updateProgress(darkgreen("Resolving key: %s") % (
                                                key
                                        ), importance = 0, type = "info", back = True, count = (cnt, maxlen) )
            self.atomMatch(key)
        maxlen = len(atoms)
        cnt = 0
        for atom in atoms:
            cnt += 1
            self.updateProgress(darkgreen("Resolving atom: %s") % (
                                                atom
                                        ), importance = 0, type = "info", back = True, count = (cnt, maxlen) )
            self.atomMatch(atom)
        maxlen = len(depends)
        cnt = 0
        for depend in depends:
            cnt += 1
            self.updateProgress(darkgreen("Resolving dependency: %s") % (
                                                depend
                                        ), importance = 0, type = "info", back = True, count = (cnt, maxlen) )
            self.atomMatch(depend)
        self.updateProgress(darkred("Dependencies filled. Flushing to disk."), importance = 2, type = "warning")
        self.save_cache()

    def load_cache(self):

        if (etpConst['uid'] != 0) or (not self.xcache): # don't load cache as user
            return

        self.updateProgress(blue("Loading On-Disk Cache..."), importance = 2, type = "info")
        # atomMatch
        try:
            mycache = self.dumpTools.loadobj(etpCache['atomMatch'])
            if isinstance(mycache, dict):
                atomMatchCache.clear()
                atomMatchCache.update(mycache)
                del mycache
        except:
            atomMatchCache.clear()
            self.dumpTools.dumpobj(etpCache['atomMatch'],{})

        # removal dependencies
        try:
            mycache3 = self.dumpTools.loadobj(etpCache['generateDependsTree'])
            if isinstance(mycache3, dict):
                generateDependsTreeCache.clear()
                generateDependsTreeCache.update(mycache3)
                del mycache3
        except:
            generateDependsTreeCache.clear()
            self.dumpTools.dumpobj(etpCache['generateDependsTree'],{})

    def save_cache(self):

        if (etpConst['uid'] != 0): # don't save cache as user
            return

        self.dumpTools.dumpobj(etpCache['atomMatch'],atomMatchCache)
        if os.path.isfile(etpConst['dumpstoragedir']+"/"+etpCache['atomMatch']+".dmp"):
            if os.stat(etpConst['dumpstoragedir']+"/"+etpCache['atomMatch']+".dmp")[6] > etpCacheSizes['atomMatch']:
                # clean cache
                self.dumpTools.dumpobj(etpCache['atomMatch'],{})
        self.dumpTools.dumpobj(etpCache['generateDependsTree'],generateDependsTreeCache)
        if os.path.isfile(etpConst['dumpstoragedir']+"/"+etpCache['generateDependsTree']+".dmp"):
            if os.stat(etpConst['dumpstoragedir']+"/"+etpCache['generateDependsTree']+".dmp")[6] > etpCacheSizes['generateDependsTree']:
                # clean cache
                self.dumpTools.dumpobj(etpCache['generateDependsTree'],{})
        for dbinfo in dbCacheStore:
            self.dumpTools.dumpobj(dbinfo,dbCacheStore[dbinfo])
            # check size
            if os.path.isfile(etpConst['dumpstoragedir']+"/"+dbinfo+".dmp"):
                if dbinfo.startswith(etpCache['dbMatch']):
                    if os.stat(etpConst['dumpstoragedir']+"/"+dbinfo+".dmp")[6] > etpCacheSizes['dbMatch']:
                        # clean cache
                        self.dumpTools.dumpobj(dbinfo,{})
                elif dbinfo.startswith(etpCache['dbInfo']):
                    if os.stat(etpConst['dumpstoragedir']+"/"+dbinfo+".dmp")[6] > etpCacheSizes['dbInfo']:
                        # clean cache
                        self.dumpTools.dumpobj(dbinfo,{})
                elif dbinfo.startswith(etpCache['dbSearch']):
                    if os.stat(etpConst['dumpstoragedir']+"/"+dbinfo+".dmp")[6] > etpCacheSizes['dbSearch']:
                        # clean cache
                        self.dumpTools.dumpobj(dbinfo,{})

    '''
       Cache stuff :: end
    '''

    # tell if a new equo release is available, returns True or False
    def check_equo_updates(self):
        found = False
        matches = self.clientDbconn.searchPackages("app-admin/equo")
        if matches:
            equo_match = "<="+matches[0][0]
            equo_unsatisfied,x = self.filterSatisfiedDependencies([equo_match])
            del x
            if equo_unsatisfied:
                found = True
            del matches
            del equo_unsatisfied
        return found

    '''
    @description: matches the package that user chose, using dbconnection.atomMatch searching in all available repositories.
    @input atom: user choosen package name
    @output: the matched selection, list: [package id,repository name] | if nothing found, returns: ( -1,1 )
    @ exit errors:
                -1 => repository cannot be fetched online
    '''
    def atomMatch(self, atom, caseSentitive = True, matchSlot = None, matchBranches = ()):

        if self.xcache:
            cached = atomMatchCache.get(atom)
            if cached:
                if (cached['matchSlot'] == matchSlot) and (cached['matchBranches'] == matchBranches) and (cached['etpRepositories'] == etpRepositories):
                    return cached['result']

        repoResults = {}
        exitErrors = {}
        for repo in etpRepositories:
            # sync database if not available
            rc = self.databaseTools.fetchRepositoryIfNotAvailable(repo)
            if (rc != 0):
                exitErrors[repo] = -1
                continue
            # open database
            dbconn = self.databaseTools.openRepositoryDatabase(repo, xcache = self.xcache)

            # search
            query = dbconn.atomMatch(atom, caseSensitive = caseSentitive, matchSlot = matchSlot, matchBranches = matchBranches)
            #print "repo:",repo,"atom:",atom,"result:",query
            if query[1] == 0:
                # package found, add to our dictionary
                repoResults[repo] = query[0]

            dbconn.closeDB()
            del dbconn

        # handle repoResults
        packageInformation = {}

        # nothing found
        if not repoResults:
            atomMatchCache[atom] = {}
            atomMatchCache[atom]['result'] = -1,1
            atomMatchCache[atom]['matchSlot'] = matchSlot
            atomMatchCache[atom]['matchBranches'] = matchBranches
            atomMatchCache[atom]['etpRepositories'] = etpRepositories.copy()
            return -1,1

        elif len(repoResults) == 1:
            # one result found
            for repo in repoResults:
                atomMatchCache[atom] = {}
                atomMatchCache[atom]['result'] = repoResults[repo],repo
                atomMatchCache[atom]['matchSlot'] = matchSlot
                atomMatchCache[atom]['matchBranches'] = matchBranches
                atomMatchCache[atom]['etpRepositories'] = etpRepositories.copy()
                return repoResults[repo],repo

        elif len(repoResults) > 1:
            # we have to decide which version should be taken

            # .tbz2 repos have always the precedence, so if we find them, we should second what user wants, installing his tbz2
            tbz2repos = [x for x in repoResults if x.endswith(".tbz2")]
            if tbz2repos:
                del tbz2repos
                newrepos = repoResults.copy()
                for x in newrepos:
                    if not x.endswith(".tbz2"):
                        del repoResults[x]

            # get package information for all the entries
            for repo in repoResults:

                # open database
                dbconn = self.databaseTools.openRepositoryDatabase(repo, xcache = self.xcache)
                # search
                packageInformation[repo] = {}
                packageInformation[repo]['version'] = dbconn.retrieveVersion(repoResults[repo])
                packageInformation[repo]['versiontag'] = dbconn.retrieveVersionTag(repoResults[repo])
                packageInformation[repo]['revision'] = dbconn.retrieveRevision(repoResults[repo])
                dbconn.closeDB()
                del dbconn

            versions = []
            repoNames = []
            # compare versions
            for repo in packageInformation:
                repoNames.append(repo)
                versions.append(packageInformation[repo]['version'])

            # found duplicates, this mean that we have to look at the revision and then, at the version tag
            # if all this shait fails, get the uppest repository
            # if no duplicates, we're done
            filteredVersions = self.entropyTools.filterDuplicatedEntries(versions)
            if (len(versions) > len(filteredVersions)):
                # there are duplicated results, fetch them
                # get the newerVersion
                newerVersion = self.entropyTools.getNewerVersion(versions)
                newerVersion = newerVersion[0]
                # is newerVersion, the duplicated one?
                duplicatedEntries = self.entropyTools.extractDuplicatedEntries(versions)
                needFiltering = False
                if newerVersion in duplicatedEntries:
                    needFiltering = True

                if (needFiltering):
                    # we have to decide which one is good
                    # we have newerVersion
                    conflictingEntries = {}
                    for repo in packageInformation:
                        if packageInformation[repo]['version'] == newerVersion:
                            conflictingEntries[repo] = {}
                            conflictingEntries[repo]['versiontag'] = packageInformation[repo]['versiontag']
                            conflictingEntries[repo]['revision'] = packageInformation[repo]['revision']

                    # at this point compare tags
                    tags = []
                    for repo in conflictingEntries:
                        tags.append(conflictingEntries[repo]['versiontag'])
                    newerTag = self.entropyTools.getNewerVersionTag(tags)
                    newerTag = newerTag[0]

                    # is the chosen tag duplicated?
                    duplicatedTags = self.entropyTools.extractDuplicatedEntries(tags)
                    needFiltering = False
                    if newerTag in duplicatedTags:
                        needFiltering = True

                    if (needFiltering):
                        # yes, it is. we need to compare revisions
                        conflictingTags = {}
                        for repo in conflictingEntries:
                            if conflictingEntries[repo]['versiontag'] == newerTag:
                                conflictingTags[repo] = {}
                                conflictingTags[repo]['revision'] = conflictingEntries[repo]['revision']

                        revisions = []
                        for repo in conflictingTags:
                            revisions.append(str(conflictingTags[repo]['revision']))
                        newerRevision = max(revisions)
                        duplicatedRevisions = self.entropyTools.extractDuplicatedEntries(revisions)
                        needFiltering = False
                        if newerRevision in duplicatedRevisions:
                            needFiltering = True

                        if (needFiltering):
                            # ok, we must get the repository with the biggest priority
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
                                        atomMatchCache[atom]['etpRepositories'] = etpRepositories.copy()
                                        return repoResults[repo],repo
                        else:
                            # we are done!!!
                            reponame = ''
                            for x in conflictingTags:
                                if str(conflictingTags[x]['revision']) == str(newerRevision):
                                    reponame = x
                                    break
                            atomMatchCache[atom] = {}
                            atomMatchCache[atom]['result'] = repoResults[reponame],reponame
                            atomMatchCache[atom]['matchSlot'] = matchSlot
                            atomMatchCache[atom]['matchBranches'] = matchBranches
                            atomMatchCache[atom]['etpRepositories'] = etpRepositories.copy()
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
                        atomMatchCache[atom]['etpRepositories'] = etpRepositories.copy()
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
                    atomMatchCache[atom]['etpRepositories'] = etpRepositories.copy()
                    return repoResults[reponame],reponame
            else:
                # yeah, we're done, just return the info
                newerVersion = self.entropyTools.getNewerVersion(versions)
                # get the repository name
                newerVersion = newerVersion[0]
                reponame = ''
                for x in packageInformation:
                    if packageInformation[x]['version'] == newerVersion:
                        reponame = x
                        break
                atomMatchCache[atom] = {}
                atomMatchCache[atom]['result'] = repoResults[reponame],reponame
                atomMatchCache[atom]['matchSlot'] = matchSlot
                atomMatchCache[atom]['matchBranches'] = matchBranches
                atomMatchCache[atom]['etpRepositories'] = etpRepositories.copy()
                return repoResults[reponame],reponame

    '''
    @description: filter the already installed dependencies
    @input dependencies: list of dependencies to check
    @output: filtered list, aka the needed ones and the ones satisfied
    '''
    def filterSatisfiedDependencies(self, dependencies, deep_deps = False):

        unsatisfiedDeps = set()
        satisfiedDeps = set()

        for dependency in dependencies:

            depsatisfied = set()
            depunsatisfied = set()

            ''' caching '''
            cached = filterSatisfiedDependenciesCache.get(dependency)
            if cached:
                if (cached['deep_deps'] == deep_deps):
                    unsatisfiedDeps.update(cached['depunsatisfied'])
                    satisfiedDeps.update(cached['depsatisfied'])
                    continue

            ### conflict
            if dependency[0] == "!":
                testdep = dependency[1:]
                xmatch = self.clientDbconn.atomMatch(testdep)
                if xmatch[0] != -1:
                    unsatisfiedDeps.add(dependency)
                else:
                    satisfiedDeps.add(dependency)
                continue

            repoMatch = self.atomMatch(dependency)
            if repoMatch[0] != -1:
                dbconn = self.databaseTools.openRepositoryDatabase(repoMatch[1])
                repo_pkgver = dbconn.retrieveVersion(repoMatch[0])
                repo_pkgtag = dbconn.retrieveVersionTag(repoMatch[0])
                repo_pkgrev = dbconn.retrieveRevision(repoMatch[0])
                dbconn.closeDB()
                del dbconn
            else:
                # dependency does not exist in our database
                unsatisfiedDeps.add(dependency)
                continue

            clientMatch = self.clientDbconn.atomMatch(dependency)
            if clientMatch[0] != -1:

                installedVer = self.clientDbconn.retrieveVersion(clientMatch[0])
                installedTag = self.clientDbconn.retrieveVersionTag(clientMatch[0])
                installedRev = self.clientDbconn.retrieveRevision(clientMatch[0])
                if installedRev == 9999: # any revision is fine
                    repo_pkgrev = 9999

                if (deep_deps):
                    vcmp = self.entropyTools.entropyCompareVersions((repo_pkgver,repo_pkgtag,repo_pkgrev),(installedVer,installedTag,installedRev))
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
            filterSatisfiedDependenciesCache[dependency]['deep_deps'] = deep_deps

        return unsatisfiedDeps, satisfiedDeps


    '''
    @description: generates a dependency tree using unsatisfied dependencies
    @input package: atomInfo (idpackage,reponame)
    @output: dependency tree dictionary, plus status code
    '''
    def generate_dependency_tree(self, atomInfo, empty_deps = False, deep_deps = False, usefilter = False):

        if (not usefilter):
            matchFilter.clear()

        ''' caching '''
        cached = generateDependencyTreeCache.get(tuple(atomInfo))
        if cached:
            if (cached['empty_deps'] == empty_deps) and \
                (cached['deep_deps'] == deep_deps) and \
                (cached['usefilter'] == usefilter):
                return cached['result']

        #print atomInfo
        mydbconn = self.databaseTools.openRepositoryDatabase(atomInfo[1])
        myatom = mydbconn.retrieveAtom(atomInfo[0])
        mydbconn.closeDB()
        del mydbconn

        # caches
        treecache = set()
        matchcache = set()
        keyslotcache = set()
        # special events
        dependenciesNotFound = set()
        conflicts = set()

        mydep = (1,myatom)
        mybuffer = self.entropyTools.lifobuffer()
        deptree = set()
        if not ((atomInfo in matchFilter) and (usefilter)):
            mybuffer.push((1,myatom))
            #mytree.append((1,myatom))
            deptree.add((1,atomInfo))

        while mydep != None:

            # already analyzed in this call
            if mydep[1] in treecache:
                mydep = mybuffer.pop()
                continue

            # conflicts
            if mydep[1][0] == "!":
                xmatch = self.clientDbconn.atomMatch(mydep[1][1:])
                if xmatch[0] != -1:
                    conflicts.add(xmatch[0])
                mydep = mybuffer.pop()
                continue

            # atom found?
            match = self.atomMatch(mydep[1])
            if match[0] == -1:
                dependenciesNotFound.add(mydep[1])
                mydep = mybuffer.pop()
                continue

            # check if atom has been already pulled in
            matchdb = self.databaseTools.openRepositoryDatabase(match[1])
            matchatom = matchdb.retrieveAtom(match[0])
            matchslot = matchdb.retrieveSlot(match[0]) # used later
            matchdb.closeDB()
            del matchdb
            if matchatom in treecache:
                mydep = mybuffer.pop()
                continue
            else:
                treecache.add(matchatom)

            treecache.add(mydep[1])

            # check if key + slot has been already pulled in
            key = self.entropyTools.dep_getkey(matchatom)
            if (matchslot,key) in keyslotcache:
                mydep = mybuffer.pop()
                continue
            else:
                keyslotcache.add((matchslot,key))

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

            matchdb = self.databaseTools.openRepositoryDatabase(match[1])
            myundeps = matchdb.retrieveDependenciesList(match[0])
            matchdb.closeDB()
            del matchdb
            # in this way filterSatisfiedDependenciesCmpResults is alway consistent
            mytestdeps, xxx = self.filterSatisfiedDependencies(myundeps, deep_deps = deep_deps)
            if (not empty_deps):
                myundeps = mytestdeps
            for x in myundeps:
                mybuffer.push((treedepth,x))

            # handle possible library breakage
            action = filterSatisfiedDependenciesCmpResults.get(mydep[1])
            if action and ((action < 0) or (action > 0)): # do not use != 0 since action can be "None"
                i = self.clientDbconn.atomMatch(self.entropyTools.dep_getkey(mydep[1]), matchSlot = matchslot)
                if i[0] != -1:
                    oldneeded = self.clientDbconn.retrieveNeeded(i[0])
                    if oldneeded: # if there are needed
                        ndbconn = self.databaseTools.openRepositoryDatabase(match[1])
                        needed = ndbconn.retrieveNeeded(match[0])
                        ndbconn.closeDB()
                        del ndbconn
                        oldneeded = oldneeded - needed
                        if oldneeded:
                            # reverse lookup to find belonging package
                            for need in oldneeded:
                                myidpackages = self.clientDbconn.searchNeeded(need)
                                for myidpackage in myidpackages:
                                    myname = self.clientDbconn.retrieveName(myidpackage)
                                    mycategory = self.clientDbconn.retrieveCategory(myidpackage)
                                    myslot = self.clientDbconn.retrieveSlot(myidpackage)
                                    mykey = mycategory+"/"+myname
                                    mymatch = self.atomMatch(mykey, matchSlot = myslot) # search in our repo
                                    if mymatch[0] != -1:
                                        mydbconn = self.databaseTools.openRepositoryDatabase(mymatch[1])
                                        mynewatom = mydbconn.retrieveAtom(mymatch[0])
                                        mydbconn.closeDB()
                                        del mydbconn
                                        if (mymatch not in matchcache) and (mynewatom not in treecache) and (mymatch not in matchFilter):
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

        if (dependenciesNotFound):
            # Houston, we've got a problem
            flatview = list(dependenciesNotFound)
            return flatview,-2

        # conflicts
        newdeptree[0] = conflicts

        ''' caching '''
        generateDependencyTreeCache[tuple(atomInfo)] = {}
        generateDependencyTreeCache[tuple(atomInfo)]['result'] = newdeptree,0
        generateDependencyTreeCache[tuple(atomInfo)]['empty_deps'] = empty_deps
        generateDependencyTreeCache[tuple(atomInfo)]['deep_deps'] = deep_deps
        generateDependencyTreeCache[tuple(atomInfo)]['usefilter'] = usefilter
        treecache.clear()
        matchcache.clear()

        return newdeptree,0 # note: newtree[0] contains possible conflicts


    def get_required_packages(self, matched_atoms, empty_deps = False, deep_deps = False):

        deptree = {}
        deptree[0] = set()

        if not etpUi['quiet']: atomlen = len(matched_atoms); count = 0
        matchFilter.clear() # clear generateDependencyTree global filter

        for atomInfo in matched_atoms:

            if not etpUi['quiet']: count += 1; self.updateProgress(":: "+str(round((float(count)/atomlen)*100,1))+"% ::", importance = 0, type = "info", back = True)

            newtree, result = self.generate_dependency_tree(atomInfo, empty_deps, deep_deps, usefilter = True)

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
    def generate_depends_tree(self, idpackages, deep = False):

        ''' caching '''
        cached = generateDependsTreeCache.get(tuple(idpackages))
        if cached:
            if (cached['deep'] == deep):
                return cached['result']

        dependscache = {}
        dependsOk = False
        treeview = set(idpackages)
        treelevel = idpackages[:]
        tree = {}
        treedepth = 0 # I start from level 1 because level 0 is idpackages itself
        tree[treedepth] = set(idpackages)
        monotree = set(idpackages) # monodimensional tree

        # check if dependstable is sane before beginning
        self.clientDbconn.retrieveDepends(idpackages[0])

        while (not dependsOk):
            treedepth += 1
            tree[treedepth] = set()
            for idpackage in treelevel:

                passed = dependscache.get(idpackage,None)
                systempkg = self.clientDbconn.isSystemPackage(idpackage)
                if passed or systempkg:
                    try:
                        while 1: treeview.remove(idpackage)
                    except:
                        pass
                    continue

                # obtain its depends
                depends = self.clientDbconn.retrieveDepends(idpackage)
                # filter already satisfied ones
                depends = [x for x in depends if x not in list(monotree)]
                if (depends): # something depends on idpackage
                    for x in depends:
                        if x not in tree[treedepth]:
                            tree[treedepth].add(x)
                            monotree.add(x)
                            treeview.add(x)
                elif deep: # if deep, grab its dependencies and check
                    mydeps = set(self.clientDbconn.retrieveDependencies(idpackage))
                    _mydeps = set()
                    for x in mydeps:
                        match = self.clientDbconn.atomMatch(x)
                        if match and match[1] == 0:
                            _mydeps.add(match[0])
                    mydeps = _mydeps
                    # now filter them
                    mydeps = [x for x in mydeps if x not in list(monotree)]
                    for x in mydeps:
                        #print clientDbconn.retrieveAtom(x)
                        mydepends = self.clientDbconn.retrieveDepends(x)
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

        ''' caching '''
        generateDependsTreeCache[tuple(idpackages)] = {}
        generateDependsTreeCache[tuple(idpackages)]['result'] = newtree,0
        generateDependsTreeCache[tuple(idpackages)]['deep'] = deep
        return newtree,0 # treeview is used to show deps while tree is used to run the dependency code.

    def calculate_world_updates(self, empty_deps = False, branch = etpConst['branch']):

        update = set()
        remove = set()
        fine = set()

        # get all the installed packages
        packages = self.clientDbconn.listAllPackages()
        maxlen = len(packages)
        count = 0
        for package in packages:
            count += 1
            self.updateProgress("", importance = 0, type = "info", back = True, header = "::", count = (count,maxlen), percent = True, footer = "::")
            tainted = False
            atom = package[0]
            idpackage = package[1]
            name = self.clientDbconn.retrieveName(idpackage)
            category = self.clientDbconn.retrieveCategory(idpackage)
            revision = self.clientDbconn.retrieveRevision(idpackage)
            slot = self.clientDbconn.retrieveSlot(idpackage)
            atomkey = category+"/"+name
            # search in the packages
            match = self.atomMatch(atom)
            if match[0] == -1: # atom has been changed, or removed?
                tainted = True
            else: # not changed, is the revision changed?
                adbconn = self.openRepositoryDatabase(match[1])
                arevision = adbconn.retrieveRevision(match[0])
                # if revision is 9999, then any revision is fine
                if revision == 9999: arevision = 9999
                if revision != arevision:
                    tainted = True
                elif (empty_deps):
                    tainted = True
            if (tainted):
                # Alice! use the key! ... and the slot
                matchresults = self.atomMatch(atomkey, matchSlot = slot, matchBranches = (branch,))
                if matchresults[0] != -1:
                    mdbconn = self.openRepositoryDatabase(matchresults[1])
                    matchatom = mdbconn.retrieveAtom(matchresults[0])
                    update.add((matchatom,matchresults))
                else:
                    remove.add(idpackage)
                    # look for packages that would match key with any slot (for eg, gcc updates), slot changes handling
                    matchresults = self.atomMatch(atomkey, matchBranches = (branch,))
                    if matchresults[0] != -1:
                        mdbconn = self.openRepositoryDatabase(matchresults[1])
                        matchatom = mdbconn.retrieveAtom(matchresults[0])
                        # compare versions
                        unsatisfied, satisfied = self.filterSatisfiedDependencies((matchatom,))
                        if unsatisfied:
                            update.add((matchatom,matchresults))
            else:
                fine.add(atom)

        del packages
        return update, remove, fine

    # This is the function that should be used by third party applications
    # to retrieve a list of available updates, along with conflicts (removalQueue) and obsoletes
    # (removed)
    def retrieveWorldQueue(self, empty_deps = False, branch = etpConst['branch']):
        update, remove, fine = self.calculate_world_updates(empty_deps = empty_deps, branch = branch)
        del fine
        data = {}
        data['removed'] = list(remove)
        data['runQueue'] = []
        data['removalQueue'] = []
        status = -1
        if update:
            # calculate install+removal queues
            matched_atoms = [x[1] for x in update]
            install, removal, status = self.retrieveInstallQueue(matched_atoms, empty_deps, deep_deps = False)
            # update data['removed']
            data['removed'] = [x for x in data['removed'] if x not in removal]
            data['runQueue'] += install
            data['removalQueue'] += removal
        return data,status

    def retrieveInstallQueue(self, matched_atoms, empty_deps, deep_deps):

        install = []
        removal = []
        treepackages, result = self.get_required_packages(matched_atoms, empty_deps, deep_deps)

        if result == -2:
            return treepackages,removal,result

        # format
        for x in range(len(treepackages)):
            if x == 0:
                # conflicts
                for a in treepackages[x]:
                    removal.append(a)
            else:
                for a in treepackages[x]:
                    install.append(a)

        # filter out packages that are in actionQueue comparing key + slot
        if install and removal:
            myremmatch = {}
            for x in removal:
                myremmatch.update({(self.entropyTools.dep_getkey(self.clientDbconn.retrieveAtom(x)),self.clientDbconn.retrieveSlot(x)): x})
            for packageInfo in install:
                dbconn = self.openRepositoryDatabase(packageInfo[1])
                testtuple = (self.entropyTools.dep_getkey(dbconn.retrieveAtom(packageInfo[0])),dbconn.retrieveSlot(packageInfo[0]))
                if testtuple in myremmatch:
                    # remove from removalQueue
                    if myremmatch[testtuple] in removal:
                        removal.remove(myremmatch[testtuple])
                del testtuple
            del myremmatch

        del treepackages
        return install, removal, 0

    # this function searches into client database for a package matching provided key + slot
    # and returns its idpackage or -1 if none found
    def retrieveInstalledIdPackage(self, pkgkey, pkgslot):
        match = self.clientDbconn.atomMatch(pkgkey, matchSlot = pkgslot)
        if match[1] == 0:
            return match[0]
        return -1

    '''
        Package instantiation interface :: begin
    '''

    '''
    @description: check if Equo has to download the given package
    @input package: filename to check inside the packages directory -> file, checksum of the package -> checksum
    @output: -1 = should be downloaded, -2 = digest broken (not mandatory), remove & download, 0 = all fine, we don't need to download it
    '''
    def check_needed_package_download(self, filepath, checksum = None):
        # is the file available
        if os.path.isfile(etpConst['entropyworkdir']+"/"+filepath):
            if checksum is None:
                return 0
            else:
                # check digest
                md5res = self.entropyTools.compareMd5(etpConst['entropyworkdir']+"/"+filepath,checksum)
                if (md5res):
                    return 0
                else:
                    return -2
        else:
            return -1

    '''
    @description: download a package into etpConst['packagesbindir'] and check for digest if digest is not False
    @input package: url -> HTTP/FTP url, digest -> md5 hash of the file
    @output: -1 = download error (cannot find the file), -2 = digest error, 0 = all fine
    '''
    def fetch_file(self, url, digest = None):
        # remove old
        filename = os.path.basename(url)
        filepath = etpConst['packagesbindir']+"/"+etpConst['branch']+"/"+filename
        if os.path.exists(filepath):
            os.remove(filepath)
    
        # load class
        fetchConn = self.urlFetcher(url, filepath)
        # start to download
        data_transfer = 0
        try:
            fetchChecksum = fetchConn.download()
            data_transfer = fetchConn.datatransfer
        except KeyboardInterrupt:
            return -4, data_transfer
        except:
            return -1, data_transfer
        if fetchChecksum == "-3":
            return -3, data_transfer
    
        del fetchConn
        if (digest):
            #print digest+" <--> "+fetchChecksum
            if (fetchChecksum != digest):
                # not properly downloaded
                return -2, data_transfer
            else:
                return 0, data_transfer
        return 0, data_transfer

    def add_failing_mirror(self, mirrorname,increment = 1):
        item = etpRemoteFailures.get(mirrorname)
        if item == None:
            etpRemoteFailures[mirrorname] = increment
        else:
            etpRemoteFailures[mirrorname] += increment # add a failure
        return etpRemoteFailures[mirrorname]

    def get_failing_mirror_status(self, mirrorname):
        item = etpRemoteFailures.get(mirrorname)
        if item == None:
            return 0
        else:
            return item

    '''
    @description: download a package into etpConst['packagesbindir'] passing all the available mirrors
    @input package: repository -> name of the repository, filename -> name of the file to download, digest -> md5 hash of the file
    @output: 0 = all fine, -3 = error on all the available mirrors
    '''
    def fetch_file_on_mirrors(self, repository, filename, digest = False, verified = False):

        uris = etpRepositories[repository]['packages'][::-1]
        remaining = set(uris[:])

        if verified: # file is already in place, match_checksum set infoDict['verified'] to True
            return 0

        mirrorcount = 0
        for uri in uris:

            if not remaining:
                # tried all the mirrors, quitting for error
                return -3

            mirrorcount += 1
            mirrorCountText = "( mirror #"+str(mirrorcount)+" ) "
            url = uri+"/"+filename

            # check if uri is sane
            if self.get_failing_mirror_status(uri) >= 30:
                # ohohoh!
                etpRemoteFailures[uri] = 30 # set to 30 for convenience
                self.updateProgress(
                                        mirrorCountText+blue(" Mirror: ")+red(self.entropyTools.spliturl(url)[1])+" - maximum failure threshold reached.",
                                        importance = 1,
                                        type = "warning",
                                        header = red("   ## ")
                                    )

                if self.get_failing_mirror_status(uri) == 30:
                    self.add_failing_mirror(uri,45) # put to 75 then decrement by 4 so we won't reach 30 anytime soon ahahaha
                else:
                    # now decrement each time this point is reached, if will be back < 30, then equo will try to use it again
                    if self.get_failing_mirror_status(uri) > 31:
                        self.add_failing_mirror(uri,-4)
                    else:
                        # put to 0 - reenable mirror, welcome back uri!
                        etpRemoteFailures[uri] = 0

                remaining.remove(uri)
                continue

            # now fetch the new one
            self.updateProgress(
                                    mirrorCountText+blue("Downloading from: ")+red(self.entropyTools.spliturl(url)[1]),
                                    importance = 1,
                                    type = "warning",
                                    header = red("   ## ")
                                )
            rc, data_transfer = self.fetch_file(url, digest)
            if rc == 0:
                self.updateProgress(
                                    mirrorCountText+blue("Successfully downloaded from: ")+red(self.entropyTools.spliturl(url)[1])+blue(" at "+str(self.entropyTools.bytesIntoHuman(data_transfer))+"/sec"),
                                    importance = 1,
                                    type = "info",
                                    header = red("   ## ")
                                )
                return 0
            else:
                error_message = mirrorCountText+blue("Error downloading from: ")+red(self.entropyTools.spliturl(url)[1])
                # something bad happened
                if rc == -1:
                    error_message += " - file not available on this mirror."
                elif rc == -2:
                    self.add_failing_mirror(uri,1)
                    error_message += " - wrong checksum."
                elif rc == -3:
                    self.add_failing_mirror(uri,2)
                    error_message += " - not found."
                elif rc == -4:
                    error_message += blue(" - discarded download.")
                else:
                    self.add_failing_mirror(uri, 5)
                    error_message += " - unknown reason."
                self.updateProgress(
                                    error_message,
                                    importance = 1,
                                    type = "warning",
                                    header = red("   ## ")
                                )
                if rc == -4: # user discarded fetch
                    return 1
                remaining.remove(uri)


    def Package(self):
        conn = PackageInterface(EntropyInstance = self)
        return conn

    def instanceTest(self):
        return

'''
    Real package actions (install/remove) interface
'''
class PackageInterface:

    def __init__(self, EntropyInstance):
        self.Entropy = EntropyInstance
        try:
            self.Entropy.instanceTest()
        except:
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid Entropy Instance is needed")
        self.infoDict = {}
        self.prepared = False
        self.matched_atom = ()
        self.valid_actions = ("fetch","remove","install")
        self.action = None

    def kill(self):
        self.infoDict.clear()
        self.matched_atom = ()
        self.valid_actions = ()
        self.action = None
        self.prepared = False

    def error_on_prepared(self):
        if self.prepared:
            raise exceptionTools.PermissionDenied("PermissionDenied: already prepared")

    def error_on_not_prepared(self):
        if not self.prepared:
            raise exceptionTools.PermissionDenied("PermissionDenied: not yet prepared")

    def check_action_validity(self, action):
        if action not in self.valid_actions:
            raise exceptionTools.InvalidData("InvalidData: action must be in %s" % (str(self.valid_actions),))

    def match_checksum(self):
        self.error_on_not_prepared()
        dlcount = 0
        match = False
        while dlcount <= 5:
            self.Entropy.updateProgress(
                                    blue("Checking package checksum..."),
                                    importance = 0,
                                    type = "info",
                                    header = red("   ## "),
                                    back = True
                                )
            dlcheck = self.Entropy.check_needed_package_download(self.infoDict['download'], checksum = self.infoDict['checksum'])
            if dlcheck == 0:
                self.Entropy.updateProgress(
                                        blue("Package checksum matches."),
                                        importance = 0,
                                        type = "info",
                                        header = red("   ## ")
                                    )
                self.infoDict['verified'] = True
                match = True
                break # file downloaded successfully
            else:
                dlcount += 1
                self.Entropy.updateProgress(
                                        blue("Package checksum does not match. Redownloading... attempt #"+str(dlcount)),
                                        importance = 0,
                                        type = "info",
                                        header = red("   ## "),
                                        back = True
                                    )
                fetch = self.Entropy.fetch_file_on_mirrors(
                                            self.infoDict['repository'],
                                            self.infoDict['download'],
                                            self.infoDict['checksum']
                                        )
                if fetch != 0:
                    self.Entropy.updateProgress(
                                        blue("Cannot properly fetch package! Quitting."),
                                        importance = 0,
                                        type = "info",
                                        header = red("   ## ")
                                    )
                    return 1
                else:
                    self.infoDict['verified'] = True
        if (not match):
            self.Entropy.updateProgress(
                                            blue("Cannot properly fetch package or checksum does not match. Try download latest repositories."),
                                            importance = 0,
                                            type = "info",
                                            header = red("   ## ")
                                        )
            return 1
        return 0

    '''
    @description: unpack the given package file into the unpack dir
    @input infoDict: dictionary containing package information
    @output: 0 = all fine, >0 = error!
    '''
    def __unpack_package(self):
        self.error_on_not_prepared()
        self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Unpacking package: "+str(self.infoDict['atom']))

        if os.path.isdir(self.infoDict['unpackdir']):
            shutil.rmtree(self.infoDict['unpackdir'])
        os.makedirs(self.infoDict['imagedir'])

        rc = self.Entropy.entropyTools.uncompressTarBz2(
                                                            self.infoDict['pkgpath'],
                                                            self.infoDict['imagedir'],
                                                            catchEmpty = True
                                                        )
        if rc != 0:
            return rc
        if not os.path.isdir(self.infoDict['imagedir']):
            return 2

        # unpack xpak ?
        if etpConst['gentoo-compat']:
            if os.path.isdir(self.infoDict['xpakpath']):
                shutil.rmtree(self.infoDict['xpakpath'])
            try:
                os.rmdir(self.infoDict['xpakpath'])
            except OSError:
                pass
            os.makedirs(self.infoDict['xpakpath'])
            # create data dir where we'll unpack the xpak
            os.mkdir(self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'])
            # now unpack for real
            xpakPath = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakfilename']
    
            if (self.infoDict['smartpackage']):
                # we need to get the .xpak from database
                xdbconn = self.Entropy.openRepositoryDatabase(self.infoDict['repository'])
                xpakdata = xdbconn.retrieveXpakMetadata(self.infoDict['idpackage'])
                if xpakdata:
                    # save into a file
                    f = open(xpakPath,"wb")
                    f.write(xpakdata)
                    f.flush()
                    f.close()
                    self.infoDict['xpakstatus'] = self.Entropy.entropyTools.unpackXpak(
                                                    xpakPath,
                                                    self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                    )
                else:
                    self.infoDict['xpakstatus'] = None
                xdbconn.closeDB()
                del xdbconn
                del xpakdata
            else:
                self.infoDict['xpakstatus'] = self.Entropy.entropyTools.extractXpak(
                                                            self.infoDict['pkgpath'],
                                                            self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                )

            # create fake portage ${D} linking it to imagedir
            portage_db_fakedir = os.path.join(
                                                self.infoDict['unpackdir'],
                                                "portage/"+self.infoDict['category'] + "/" + self.infoDict['name'] + "-" + self.infoDict['version']
                                            )

            os.makedirs(portage_db_fakedir)
            # now link it to self.infoDict['imagedir']
            os.symlink(self.infoDict['imagedir'],os.path.join(portage_db_fakedir,"image"))

        return 0

    def __remove_package(self):

        self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing package: "+str(self.infoDict['removeatom']))
        # clear on-disk cache
        generateDependsTreeCache.clear()
        self.Entropy.dumpTools.dumpobj(etpCache['generateDependsTree'],generateDependsTreeCache)

        # remove from database
        if self.infoDict['removeidpackage'] != -1:
            self.Entropy.updateProgress(
                                    blue("Removing from database: ")+red(self.infoDict['removeatom']),
                                    importance = 1,
                                    type = "info",
                                    header = red("   ## ")
                                )
            self.__remove_package_from_database()

        # Handle gentoo database
        if (etpConst['gentoo-compat']):  # FIXME: remove dep_striptag asap
            gentooAtom = self.Entropy.entropyTools.dep_striptag(
                                        self.Entropy.entropyTools.remove_tag(self.infoDict['removeatom'])
            )
            self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing package from Gentoo database: "+str(gentooAtom))
            self.__remove_package_from_gentoo_database(gentooAtom)
            del gentooAtom

        self.__remove_content_from_system()
        return 0

    def __remove_content_from_system(self):

        # load CONFIG_PROTECT and its mask - client database at this point has been surely opened, so our dicts are already filled
        protect = etpConst['dbconfigprotect']
        mask = etpConst['dbconfigprotectmask']

        # remove files from system
        directories = set()
        for item in self.infoDict['removecontent']:
            # collision check
            if etpConst['collisionprotect'] > 0:

                if self.Entropy.clientDbconn.isFileAvailable(item) and os.path.isfile(etpConst['systemroot']+item):
                    # in this way we filter out directories
                    self.Entropy.updateProgress(
                                            red("Collision found during remove of ")+etpConst['systemroot']+item+red(" - cannot overwrite"),
                                            importance = 1,
                                            type = "warning",
                                            header = red("   ## ")
                                        )
                    self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Collision found during remove of "+etpConst['systemroot']+item+" - cannot overwrite")
                    continue

            protected = False
            if (not self.infoDict['removeconfig']) and (not self.infoDict['diffremoval']):
                try:
                    # -- CONFIGURATION FILE PROTECTION --
                    if os.access(etpConst['systemroot']+item,os.R_OK):
                        for x in protect:
                            if etpConst['systemroot']+item.startswith(x):
                                protected = True
                                break
                        if (protected):
                            for x in mask:
                                if etpConst['systemroot']+item.startswith(x):
                                    protected = False
                                    break
                        if (protected) and os.path.isfile(etpConst['systemroot']+item):
                            protected = self.Entropy.entropyTools.istextfile(etpConst['systemroot']+item)
                        else:
                            protected = False # it's not a file
                    # -- CONFIGURATION FILE PROTECTION --
                except:
                    pass # some filenames are buggy encoded


            if (protected):
                self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"[remove] Protecting config file: "+etpConst['systemroot']+item)
                self.Entropy.updateProgress(
                                        red("[remove] Protecting config file: ")+etpConst['systemroot']+item,
                                        importance = 1,
                                        type = "warning",
                                        header = red("   ## ")
                                    )
            else:
                try:
                    os.lstat(etpConst['systemroot']+item)
                except OSError:
                    continue # skip file, does not exist
                except UnicodeEncodeError:
                    self.Entropy.updateProgress(
                                            red("QA: ")+brown("this package contains a badly encoded file"),
                                            importance = 1,
                                            type = "warning",
                                            header = darkred("   ## ")
                                        )
                    continue # file has a really bad encoding

                if os.path.isdir(etpConst['systemroot']+item) and os.path.islink(etpConst['systemroot']+item): # S_ISDIR returns False for directory symlinks, so using os.path.isdir
                    # valid directory symlink
                    #print "symlink dir",file
                    directories.add((etpConst['systemroot']+item,"link"))
                elif os.path.isdir(etpConst['systemroot']+item):
                    # plain directory
                    #print "plain dir",file
                    directories.add((etpConst['systemroot']+item,"dir"))
                else: # files, symlinks or not
                    # just a file or symlink or broken directory symlink (remove now)
                    try:
                        #print "plain file",file
                        os.remove(etpConst['systemroot']+item)
                        # add its parent directory
                        dirfile = os.path.dirname(etpConst['systemroot']+item)
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
                mydir = etpConst['systemroot']+directory[0]
                if directory[1] == "link":
                    try:
                        mylist = os.listdir(mydir)
                        if not mylist:
                            try:
                                os.remove(mydir)
                                taint = True
                            except OSError:
                                pass
                    except OSError:
                        pass
                elif directory[1] == "dir":
                    try:
                        mylist = os.listdir(mydir)
                        if not mylist:
                            try:
                                os.rmdir(mydir)
                                taint = True
                            except OSError:
                                pass
                    except OSError:
                        pass

            if not taint:
                break
        del directories


    '''
    @description: remove package entry from Gentoo database
    @input gentoo package atom (cat/name+ver):
    @output: 0 = all fine, <0 = error!
    '''
    def __remove_package_from_gentoo_database(self, atom):

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
            key = self.Entropy.entropyTools.dep_getkey(atom)
            othersInstalled = _portage_getInstalledAtoms(key) #FIXME: really slow
            if othersInstalled == None: # FIXME: beautify this shit (skippedKey)
                # safest way (error free) is to use sed without loading the file
                # escape /
                skippedKey = ''
                for x in key:
                    if x == "/":
                        x = "\/"
                    skippedKey += x
                os.system("sed -i '/"+skippedKey+"/d' "+etpConst['systemroot']+"/var/lib/portage/world")
        return 0

    '''
    @description: function that runs at the end of the package installation process, just removes data left by other steps
    @output: 0 = all fine, >0 = error!
    '''
    def __cleanup_package(self):
        # remove unpack dir
        shutil.rmtree(self.infoDict['unpackdir'],True)
        try:
            os.rmdir(self.infoDict['unpackdir'])
        except OSError:
            pass
        return 0

    '''
    @description: remove the package from the installed packages database..
                    This function is a wrapper around databaseTools.removePackage that will let us to add our custom things
    @output: 0 = all fine, >0 = error!
    '''
    def __remove_package_from_database(self):
        self.error_on_not_prepared()
        self.Entropy.clientDbconn.removePackage(self.infoDict['removeidpackage'])
        return 0

    '''
    @description: install unpacked files, update database and also update gentoo db if requested
    @output: 0 = all fine, >0 = error!
    '''
    def __install_package(self):

        # clear on-disk cache
        generateDependsTreeCache.clear()
        self.Entropy.dumpTools.dumpobj(etpCache['generateDependsTree'],{})
        self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Installing package: "+str(self.infoDict['atom']))

        # copy files over - install
        rc = self.__move_image_to_system()
        if rc != 0:
            return rc

        # inject into database
        self.Entropy.updateProgress(
                                blue("Updating database with: ")+red(self.infoDict['atom']),
                                importance = 1,
                                type = "info",
                                header = red("   ## ")
                            )
        newidpackage = self.__install_package_into_database()

        # remove old files and gentoo stuff
        if (self.infoDict['removeidpackage'] != -1):
            # doing a diff removal
            self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Remove old package: "+str(self.infoDict['removeatom']))
            self.infoDict['removeidpackage'] = -1 # disabling database removal

            compatstring = ''
            if etpConst['gentoo-compat']:
                self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing Entropy and Gentoo database entry for "+str(self.infoDict['removeatom']))
                compatstring = " ## w/Gentoo compatibility"
            else:
                self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing Entropy (only) database entry for "+str(self.infoDict['removeatom']))

            self.Entropy.updateProgress(
                                    blue("Cleaning old package files...")+compatstring,
                                    importance = 1,
                                    type = "info",
                                    header = red("   ## ")
                                )
            self.__remove_package()

        rc = 0
        if (etpConst['gentoo-compat']):
            self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Installing new Gentoo database entry: "+str(self.infoDict['atom']))
            rc = self.__install_package_into_gentoo_database(newidpackage)

        return rc

    '''
    @description: inject the database information into the Gentoo database
    @output: 0 = all fine, >0 = error!
    '''
    def __install_package_into_gentoo_database(self, newidpackage = -1):

        # handle gentoo-compat
        _portage_avail = False
        try:
            import portageTools
            _portage_avail = True
        except:
            return -1 # no Portage support
        if (_portage_avail):
            portDbDir = portageTools.getPortageAppDbPath()
            # extract xpak from unpackDir+etpConst['packagecontentdir']+"/"+package
            key = self.infoDict['category']+"/"+self.infoDict['name']
            #print portageTools.getInstalledAtom(key)
            atomsfound = set()
            dbdirs = os.listdir(portDbDir)
            if self.infoDict['category'] in dbdirs:
                catdirs = os.listdir(portDbDir+"/"+self.infoDict['category'])
                dirsfound = set([self.infoDict['category']+"/"+x for x in catdirs if key == self.Entropy.entropyTools.dep_getkey(self.infoDict['category']+"/"+x)])
                atomsfound.update(dirsfound)

            ### REMOVE
            # parse slot and match and remove
            if atomsfound:
                pkgToRemove = ''
                for atom in atomsfound:
                    atomslot = portageTools.getPackageSlot(atom)
                    # get slot from gentoo db
                    if atomslot == self.infoDict['slot']:
                        #print "match slot, remove -> "+str(atomslot)
                        pkgToRemove = atom
                        break
                if (pkgToRemove):
                    removePath = portDbDir+pkgToRemove
                    shutil.rmtree(removePath,True)
                    try:
                        os.rmdir(removePath)
                    except OSError:
                        pass
                    #print "removing -> "+removePath
            del atomsfound

            # xpakstatus is perpared by unpackPackage()
            # we now install it
            if self.infoDict['xpakstatus'] != None and \
                                os.path.isdir(
                                        self.infoDict['xpakpath'] + "/" + etpConst['entropyxpakdatarelativepath']
                ):
                if not os.path.isdir(portDbDir+self.infoDict['category']):
                    os.makedirs(portDbDir+self.infoDict['category'])
                destination = portDbDir+self.infoDict['category']+"/"+self.infoDict['name']+"-"+self.infoDict['version']
                if os.path.isdir(destination):
                    shutil.rmtree(destination)

                shutil.copytree(self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'],destination)

                # test if /var/cache/edb/counter is fine
                if os.path.isfile(etpConst['edbcounter']):
                    try:
                        f = open(etpConst['edbcounter'],"r")
                        counter = int(f.readline().strip())
                        f.close()
                    except:
                        # need file recreation, parse gentoo tree
                        counter = portageTools.refillCounter()
                else:
                    counter = portageTools.refillCounter()

                # write new counter to file
                if os.path.isdir(destination):
                    counter += 1
                    f = open(destination+"/"+dbCOUNTER,"w")
                    f.write(str(counter))
                    f.flush()
                    f.close()
                    f = open(etpConst['edbcounter'],"w")
                    f.write(str(counter))
                    f.flush()
                    f.close()
                    # update counter inside clientDatabase
                    self.Entropy.clientDbconn.setCounter(newidpackage,counter)
                else:
                    print "DEBUG: WARNING!! "+destination+" DOES NOT EXIST, CANNOT UPDATE COUNTER!!"

        return 0

    '''
    @description: injects package info into the installed packages database
    @output: 0 = all fine, >0 = error!
    '''
    def __install_package_into_database(self):

        # fetch info
        dbconn = self.Entropy.openRepositoryDatabase(self.infoDict['repository'])
        data = dbconn.getPackageData(self.infoDict['idpackage'])
        # open client db
        # always set data['injected'] to False
        # installed packages database SHOULD never have more than one package for scope (key+slot)
        data['injected'] = False

        idpk, rev, x, status = self.Entropy.clientDbconn.handlePackage(etpData = data, forcedRevision = data['revision'])
        del x
        del data
        del status # if operation isn't successful, an error will be surely raised

        # add idpk to the installedtable
        self.Entropy.clientDbconn.removePackageFromInstalledTable(idpk)
        self.Entropy.clientDbconn.addPackageToInstalledTable(idpk,self.infoDict['repository'])
        # update dependstable
        try:
            depends = self.Entropy.clientDbconn.listIdpackageDependencies(idpk)
            #print depends
            for depend in depends:
                atom = depend[1]
                iddep = depend[0]
                match = self.Entropy.clientDbconn.atomMatch(atom)
                if (match[0] != -1):
                    self.Entropy.clientDbconn.removeDependencyFromDependsTable(iddep)
                    self.Entropy.clientDbconn.addDependRelationToDependsTable(iddep,match[0])
            del depends
        except:
            self.Entropy.clientDbconn.regenerateDependsTable()

        return idpk

    def __move_image_to_system(self):

        # load CONFIG_PROTECT and its mask
        protect = etpRepositories[self.infoDict['repository']]['configprotect']
        mask = etpRepositories[self.infoDict['repository']]['configprotectmask']
        # setup imageDir properly
        imageDir = self.infoDict['imagedir'].encode(sys.getfilesystemencoding())

        # merge data into system
        for currentdir,subdirs,files in os.walk(imageDir):
            # create subdirs
            for subdir in subdirs:

                imagepathDir = currentdir + "/" + subdir
                rootdir = etpConst['systemroot']+imagepathDir[len(imageDir):]
                #print rootdir

                # handle broken symlinks
                if os.path.islink(rootdir) and not os.path.exists(rootdir):# broken symlink
                    os.remove(rootdir)

                # if our directory is a file on the live system
                elif os.path.isfile(rootdir): # really weird...!
                    self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"WARNING!!! "+rootdir+" is a file when it should be a directory !! Removing in 20 seconds...")
                    self.Entropy.updateProgress(
                                            bold(rootdir)+red(" is a file when it should be a directory !! Removing in 20 seconds..."),
                                            importance = 1,
                                            type = "warning",
                                            header = red(" *** ")
                                        )
                    self.Entropy.entropyTools.ebeep(10)
                    time.sleep(20)
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

            for item in files:
                fromfile = currentdir+"/"+item
                tofile = etpConst['systemroot']+fromfile[len(imageDir):]
                #print tofile

                if etpConst['collisionprotect'] > 1:
                    todbfile = fromfile[len(imageDir):]
                    if self.Entropy.clientDbconn.isFileAvailable(todbfile):
                        self.Entropy.updateProgress(
                                                red("Collision found during install for ")+tofile+" - cannot overwrite",
                                                importance = 1,
                                                type = "warning",
                                                header = darkred("   ## ")
                                            )
                        self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"WARNING!!! Collision found during install for "+tofile+" - cannot overwrite")
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
                        protected = self.Entropy.entropyTools.istextfile(tofile)
                    else:
                        protected = False # it's not a file

                    # request new tofile then
                    if (protected):
                        if tofile not in etpConst['configprotectskip']:
                            tofile, prot_status = self.Entropy.entropyTools.allocateMaskedFile(tofile, fromfile)
                            if not prot_status:
                                protected = False
                            else:
                                oldtofile = tofile
                                if oldtofile.find("._cfg") != -1:
                                    oldtofile = os.path.dirname(oldtofile)+"/"+os.path.basename(oldtofile)[10:]
                                self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Protecting config file: "+oldtofile)
                                self.Entropy.updateProgress(
                                                        red("Protecting config file: ")+oldtofile,
                                                        importance = 1,
                                                        type = "warning",
                                                        header = darkred("   ## ")
                                                    )
                        else:
                            self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Skipping config file installation, as stated in equo.conf: "+tofile)
                            self.Entropy.updateProgress(
                                                    red("Skipping file installation: ")+tofile,
                                                    importance = 1,
                                                    type = "warning",
                                                    header = darkred("   ## ")
                                                )
                            continue

                    # -- CONFIGURATION FILE PROTECTION --

                except:
                    print "DEBUG !!!!: error in __move_image_to_system ?"
                    pass # some files are buggy encoded

                try:

                    if os.path.realpath(fromfile) == os.path.realpath(tofile) and os.path.islink(tofile):
                        # there is a serious issue here, better removing tofile, happened to someone:
                        '''
                            File \"/usr/lib/python2.4/shutil.py\", line 42, in copyfile
                            raise Error, \"`%s` and `%s` are the same file\" % (src, dst)
                            Error: `/var/tmp/entropy/packages/x86/3.5/mozilla-firefox-2.0.0.8.tbz2/image/usr/lib/mozilla-firefox/include/nsIURI.h` and `/usr/lib/mozilla-firefox/include/nsIURI.h` are the same file
                        '''
                        try: # try to cope...
                            os.remove(tofile)
                        except:
                            pass

                    # if our file is a dir on the live system
                    if os.path.isdir(tofile) and not os.path.islink(tofile): # really weird...!
                        self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"WARNING!!! "+tofile+" is a directory when it should be a file !! Removing in 20 seconds...")
                        self.Entropy.updateProgress(
                                                bold(tofile)+red(" is a directory when it should be a file !! Removing in 20 seconds..."),
                                                importance = 1,
                                                type = "warning",
                                                header = red(" *** ")
                                            )
                        self.Entropy.entropyTools.ebeep(10)
                        time.sleep(20)
                        try:
                            shutil.rmtree(tofile, True)
                            os.rmdir(tofile)
                        except:
                            pass
                        try: # if it was a link
                            os.remove(tofile)
                        except OSError:
                            pass

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
                try:
                    user = os.stat(fromfile)[4]
                    group = os.stat(fromfile)[5]
                    os.chown(tofile,user,group)
                    shutil.copystat(fromfile,tofile)
                except:
                    pass # sometimes, gentoo packages are fucked up and contain broken symlinks

                if (protected):
                    # add to disk cache
                    self.Entropy.confTools.addtocache(tofile)

        return 0


    def fetch_step(self):
        self.error_on_not_prepared()
        self.Entropy.updateProgress(
                                            blue("Fetching archive: ")+red(os.path.basename(self.infoDict['download'])),
                                            importance = 1,
                                            type = "info",
                                            header = red("   ## ")
                                    )
        rc = self.Entropy.fetch_file_on_mirrors(
                                                    self.infoDict['repository'],
                                                    self.infoDict['download'],
                                                    self.infoDict['checksum'],
                                                    self.infoDict['verified']
                                                )
        if rc < 0:
            self.Entropy.updateProgress(
                                            red("Package cannot be fetched. Try to update repositories and retry. Error: %s" % (str(rc),)),
                                            importance = 1,
                                            type = "error",
                                            header = darkred("   ## ")
                                    )
            return rc
        return 0

    def checksum_step(self):
        self.error_on_not_prepared()
        rc = self.match_checksum()
        return rc

    def unpack_step(self):
        self.error_on_not_prepared()
        self.Entropy.updateProgress(
                                            blue("Unpacking package: ")+red(os.path.basename(self.infoDict['download'])),
                                            importance = 1,
                                            type = "info",
                                            header = red("   ## ")
                                    )
        rc = self.__unpack_package()
        if rc != 0:
            if rc == 512:
                errormsg = red("You are running out of disk space. I bet, you're probably Michele. Error 512")
            else:
                errormsg = red("An error occured while trying to unpack the package. Check if your system is healthy. Error "+str(rc))
            self.Entropy.updateProgress(
                                            errormsg,
                                            importance = 1,
                                            type = "error",
                                            header = red("   ## ")
                                    )
        return rc

    def install_step(self):
        self.error_on_not_prepared()
        compatstring = ''
        if etpConst['gentoo-compat']:
            compatstring = " ## w/Gentoo compatibility"
        self.Entropy.updateProgress(
                                            blue("Installing package: ")+red(self.infoDict['atom'])+compatstring,
                                            importance = 1,
                                            type = "info",
                                            header = red("   ## ")
                                    )
        rc = self.__install_package()
        if rc != 0:
            self.Entropy.updateProgress(
                                            red("An error occured while trying to install the package. Check if your system is healthy. Error %s" % (str(rc),)),
                                            importance = 1,
                                            type = "error",
                                            header = red("   ## ")
                                    )
        return rc

    def remove_step(self):
        self.error_on_not_prepared()
        compatstring = ''
        if etpConst['gentoo-compat']:
            compatstring = " ## w/Gentoo compatibility"
        self.Entropy.updateProgress(
                                            blue("Removing installed package: ")+red(self.infoDict['removeatom'])+compatstring,
                                            importance = 1,
                                            type = "info",
                                            header = red("   ## ")
                                    )
        rc = self.__remove_package()
        if rc != 0:
            errormsg = red("An error occured while trying to remove the package. Check if you have enough disk space on your hard disk. Error %s " % (str(rc),))
            self.Entropy.updateProgress(
                                            errormsg,
                                            importance = 1,
                                            type = "error",
                                            header = red("   ## ")
                                    )
        return rc

    def cleanup_step(self):
        self.error_on_not_prepared()
        self.Entropy.updateProgress(
                                        blue('Cleaning temporary files for archive: ')+red(self.infoDict['atom']),
                                        importance = 1,
                                        type = "info",
                                        header = red("   ## ")
                                    )
        self.Entropy.entropyTools.parallelTask(self.__cleanup_package)
        # we don't care if cleanupPackage fails since it's not critical
        return 0

    def messages_step(self):
        self.error_on_not_prepared()
        # get messages
        if self.infoDict['messages']:
            self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Message from "+self.infoDict['atom']+" :")
            self.Entropy.updateProgress(
                                                darkgreen("Gentoo ebuild messages:"),
                                                importance = 0,
                                                type = "warning",
                                                header = brown("   ## ")
                                        )
        for msg in self.infoDict['messages']:
            self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,msg)
            self.Entropy.updateProgress(
                                                msg,
                                                importance = 0,
                                                type = "warning",
                                                header = brown("   ## ")
                                        )
        if self.infoDict['messages']:
            self.Entropy.equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"End message.")

    def postinstall_step(self):
        self.error_on_not_prepared()
        pkgdata = self.infoDict['triggers'].get('install')
        if pkgdata:
            triggers = self.Entropy.triggerTools.postinstall(pkgdata, self.Entropy)
            for trigger in triggers:
                if trigger not in etpUi['postinstall_triggers_disable']:
                    eval("self.Entropy.triggerTools."+trigger)(pkgdata)
            del triggers
        del pkgdata
        return 0

    def preinstall_step(self):
        self.error_on_not_prepared()
        pkgdata = self.infoDict['triggers'].get('install')
        if pkgdata:
            triggers = self.Entropy.triggerTools.preinstall(pkgdata, self.Entropy)

            if (self.infoDict.get("diffremoval") != None): # diffremoval is true only when the remove action is triggered by installPackages()
                if self.infoDict['diffremoval']:
                    remdata = self.infoDict['triggers'].get('remove')
                    if remdata:
                        itriggers = self.Entropy.triggerTools.preremove(remdata, self.Entropy) # remove duplicated triggers
                        triggers = triggers - itriggers
                        del itriggers
                    del remdata

            for trigger in triggers:
                if trigger not in etpUi['preinstall_triggers_disable']:
                    eval("self.Entropy.triggerTools."+trigger)(pkgdata)
            del triggers

        del pkgdata
        return 0

    def preremove_step(self):
        self.error_on_not_prepared()
        remdata = self.infoDict['triggers'].get('remove')
        if remdata:
            triggers = self.Entropy.triggerTools.preremove(remdata, self.Entropy)
            for trigger in triggers:
                if trigger not in etpUi['preremove_triggers_disable']:
                    eval("self.Entropy.triggerTools."+trigger)(remdata)
            del triggers
        del remdata
        return 0

    def postremove_step(self):
        self.error_on_not_prepared()
        remdata = self.infoDict['triggers'].get('remove')
        if remdata:
            triggers = self.Entropy.triggerTools.postremove(remdata, self.Entropy)
            if self.infoDict['diffremoval'] and (self.infoDict.get("atom") != None): # diffremoval is true only when the remove action is triggered by installPackages()
                pkgdata = self.infoDict['triggers'].get('install')
                if pkgdata:
                    itriggers = self.Entropy.triggerTools.postinstall(pkgdata, self.Entropy)
                    triggers = triggers - itriggers
                    del itriggers
                del pkgdata

            for trigger in triggers:
                if trigger not in etpUi['postremove_triggers_disable']:
                    eval("self.Entropy.triggerTools."+trigger)(remdata)
            del triggers

        del remdata
        return 0


    '''
        @description: execute the requested steps
        @input xterm_header: purely optional
    '''
    def run(self, xterm_header = None):
        self.error_on_not_prepared()

        if xterm_header == None:
            xterm_header = ""

        rc = 0
        for step in self.infoDict['steps']:
            self.xterm_title = xterm_header+' '

            if step == "fetch":
                self.xterm_title += 'Fetching archive: '+os.path.basename(self.infoDict['download'])
                xtermTitle(self.xterm_title)
                rc = self.fetch_step()

            elif step == "checksum":
                self.xterm_title += 'Verifying archive: '+os.path.basename(self.infoDict['download'])
                xtermTitle(self.xterm_title)
                rc = self.checksum_step()

            elif step == "unpack":
                self.xterm_title += 'Unpacking archive: '+os.path.basename(self.infoDict['download'])
                xtermTitle(self.xterm_title)
                rc = self.unpack_step()

            elif step == "install":
                compatstring = ''
                if etpConst['gentoo-compat']:
                    compatstring = " ## w/Gentoo compatibility"
                self.xterm_title += 'Installing archive: '+self.infoDict['atom']+compatstring
                xtermTitle(self.xterm_title)
                rc = self.install_step()

            elif step == "remove":
                compatstring = ''
                if etpConst['gentoo-compat']:
                    compatstring = " ## w/Gentoo compatibility"
                self.xterm_title += 'Removing archive: '+self.infoDict['removeatom']+compatstring
                xtermTitle(self.xterm_title)
                rc = self.remove_step()

            elif step == "showmessages":
                rc = self.messages_step()

            elif step == "cleanup":
                self.xterm_title += 'Cleaning archive: '+self.infoDict['atom']
                xtermTitle(self.xterm_title)
                rc = self.cleanup_step()

            elif step == "postinstall":
                self.xterm_title += 'Postinstall archive: '+self.infoDict['atom']
                xtermTitle(self.xterm_title)
                rc = self.postinstall_step()

            elif step == "preinstall":
                self.xterm_title += 'Preinstall archive: '+self.infoDict['atom']
                xtermTitle(self.xterm_title)
                rc = self.preinstall_step()

            elif step == "preremove":
                self.xterm_title += 'Preremove archive: '+self.infoDict['removeatom']
                xtermTitle(self.xterm_title)
                rc = self.preremove_step()

            elif step == "postremove":
                self.xterm_title += 'Postremove archive: '+self.infoDict['removeatom']
                xtermTitle(self.xterm_title)
                rc = self.postremove_step()

            if rc != 0:
                break

        if rc != 0:
            self.Entropy.updateProgress(
                                                blue("An error occured. Action aborted."),
                                                importance = 2,
                                                type = "error",
                                                header = darkred("   ## ")
                                        )
            return rc

        # clear garbage
        gc.collect()
        return rc

    '''
       Install/Removal process preparation function
       - will generate all the metadata needed to run the action steps, creating infoDict automatically
       @input matched_atom(tuple): is what is returned by EntropyInstance.atomMatch:
            (idpackage,repoid):
            (2000,u'sabayonlinux.org')
            NOTE: in case of remove action, matched_atom must be:
            (idpackage,)
        @input action(string): is an action to take, which must be one in self.valid_actions
    '''
    def prepare(self, matched_atom, action, metaopts = {}):
        self.error_on_prepared()
        self.check_action_validity(action)

        self.action = action
        self.matched_atom = matched_atom
        self.metaopts = metaopts
        # generate metadata dictionary
        self.generate_metadata()

    def generate_metadata(self):
        self.error_on_prepared()
        self.check_action_validity(self.action)

        if self.action == "fetch":
            self.__generate_fetch_metadata()
        elif self.action == "remove":
            self.__generate_remove_metadata()
        elif self.action == "install":
            self.__generate_install_metadata()
        self.prepared = True

    def __generate_remove_metadata(self):
        idpackage = self.matched_atom[0]
        self.infoDict.clear()
        self.infoDict['triggers'] = {}
        self.infoDict['removeatom'] = self.Entropy.clientDbconn.retrieveAtom(idpackage)
        self.infoDict['removeidpackage'] = idpackage
        self.infoDict['diffremoval'] = False
        removeConfig = False
        if self.metaopts.has_key('removeconfig'):
            removeConfig = self.metaopts.get('removeconfig')
        self.infoDict['removeconfig'] = removeConfig
        self.infoDict['removecontent'] = self.Entropy.clientDbconn.retrieveContent(idpackage)
        self.infoDict['triggers']['remove'] = self.Entropy.clientDbconn.getPackageData(idpackage)
        self.infoDict['triggers']['remove']['removecontent'] = self.infoDict['removecontent']
        self.infoDict['steps'] = []
        self.infoDict['steps'].append("preremove")
        self.infoDict['steps'].append("remove")
        self.infoDict['steps'].append("postremove")

    def __generate_install_metadata(self):
        self.infoDict.clear()

        idpackage = self.matched_atom[0]
        repository = self.matched_atom[1]
        self.infoDict['idpackage'] = idpackage
        self.infoDict['repository'] = repository
        # get package atom
        dbconn = self.Entropy.openRepositoryDatabase(repository)
        self.infoDict['triggers'] = {}
        self.infoDict['atom'] = dbconn.retrieveAtom(idpackage)
        self.infoDict['slot'] = dbconn.retrieveSlot(idpackage)
        self.infoDict['version'] = dbconn.retrieveVersion(idpackage)
        self.infoDict['versiontag'] = dbconn.retrieveVersionTag(idpackage)
        self.infoDict['revision'] = dbconn.retrieveRevision(idpackage)
        self.infoDict['category'] = dbconn.retrieveCategory(idpackage)
        self.infoDict['download'] = dbconn.retrieveDownloadURL(idpackage)
        self.infoDict['name'] = dbconn.retrieveName(idpackage)
        self.infoDict['messages'] = dbconn.retrieveMessages(idpackage)
        self.infoDict['checksum'] = dbconn.retrieveDigest(idpackage)
        # fill action queue
        self.infoDict['removeidpackage'] = -1
        removeConfig = False
        if self.metaopts.has_key('removeconfig'):
            removeConfig = self.metaopts.get('removeconfig')
        self.infoDict['removeconfig'] = removeConfig
        self.infoDict['removeidpackage'] = self.Entropy.retrieveInstalledIdPackage(
                                                self.Entropy.entropyTools.dep_getkey(self.infoDict['atom']),
                                                self.infoDict['slot']
                                            )
        if self.infoDict['removeidpackage'] != -1:
            self.infoDict['removeatom'] = self.Entropy.clientDbconn.retrieveAtom(self.infoDict['removeidpackage'])

        # smartpackage ?
        self.infoDict['smartpackage'] = False
        # set unpack dir and image dir
        if self.infoDict['repository'].endswith(".tbz2"):
            self.infoDict['smartpackage'] = etpRepositories[self.infoDict['repository']]['smartpackage']
            self.infoDict['pkgpath'] = etpRepositories[self.infoDict['repository']]['pkgpath']
        else:
            self.infoDict['pkgpath'] = etpConst['entropyworkdir']+"/"+self.infoDict['download']
        self.infoDict['unpackdir'] = etpConst['entropyunpackdir']+"/"+self.infoDict['download']
        self.infoDict['imagedir'] = etpConst['entropyunpackdir']+"/"+self.infoDict['download']+"/"+etpConst['entropyimagerelativepath']

        # gentoo xpak data
        if etpConst['gentoo-compat']:
            self.infoDict['xpakstatus'] = None
            self.infoDict['xpakpath'] = etpConst['entropyunpackdir']+"/"+self.infoDict['download']+"/"+etpConst['entropyxpakrelativepath']
            self.infoDict['xpakdir'] = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']

        # set steps
        self.infoDict['steps'] = []
        # install
        if (self.infoDict['removeidpackage'] != -1):
            self.infoDict['steps'].append("preremove")
        self.infoDict['steps'].append("unpack")
        self.infoDict['steps'].append("preinstall")
        self.infoDict['steps'].append("install")
        if (self.infoDict['removeidpackage'] != -1):
            self.infoDict['steps'].append("postremove")
        self.infoDict['steps'].append("postinstall")
        if not etpConst['gentoo-compat']: # otherwise gentoo triggers will show that
            self.infoDict['steps'].append("showmessages")
        self.infoDict['steps'].append("cleanup")

        # compare both versions and if they match, disable removeidpackage
        if self.infoDict['removeidpackage'] != -1:
            installedVer = self.Entropy.clientDbconn.retrieveVersion(self.infoDict['removeidpackage'])
            installedTag = self.Entropy.clientDbconn.retrieveVersionTag(self.infoDict['removeidpackage'])
            installedRev = self.Entropy.clientDbconn.retrieveRevision(self.infoDict['removeidpackage'])
            pkgcmp = self.Entropy.entropyTools.entropyCompareVersions(
                                                        (self.infoDict['version'],self.infoDict['versiontag'],self.infoDict['revision']),
                                                        (installedVer,installedTag,installedRev)
                                                    )
            if pkgcmp == 0:
                self.infoDict['removeidpackage'] = -1
            del pkgcmp

        # differential remove list
        if (self.infoDict['removeidpackage'] != -1):
            # is it still available?
            if self.Entropy.clientDbconn.isIDPackageAvailable(self.infoDict['removeidpackage']):
                self.infoDict['diffremoval'] = True
                self.infoDict['removeatom'] = self.Entropy.clientDbconn.retrieveAtom(self.infoDict['removeidpackage'])
                oldcontent = self.Entropy.clientDbconn.retrieveContent(self.infoDict['removeidpackage'])
                newcontent = dbconn.retrieveContent(idpackage)
                oldcontent = oldcontent - newcontent
                del newcontent
                self.infoDict['removecontent'] = oldcontent.copy()
                del oldcontent
                # XXX: too much memory
                self.infoDict['triggers']['remove'] = self.Entropy.clientDbconn.getPackageData(self.infoDict['removeidpackage'])
                self.infoDict['triggers']['remove']['removecontent'] = self.infoDict['removecontent']
            else:
                self.infoDict['removeidpackage'] = -1

        # XXX: too much memory used for this
        self.infoDict['triggers']['install'] = dbconn.getPackageData(idpackage)
        self.infoDict['triggers']['install']['unpackdir'] = self.infoDict['unpackdir']
        if etpConst['gentoo-compat']:
            self.infoDict['triggers']['install']['xpakpath'] = self.infoDict['xpakpath']
            self.infoDict['triggers']['install']['xpakdir'] = self.infoDict['xpakdir']


    def __generate_fetch_metadata(self):
        self.infoDict.clear()

        idpackage = self.matched_atom[0]
        repository = self.matched_atom[1]
        dochecksum = True
        if self.metaopts.has_key('dochecksum'):
            dochecksum = self.metaopts.get('dochecksum')
        self.infoDict['repository'] = repository
        self.infoDict['idpackage'] = idpackage
        dbconn = self.Entropy.openRepositoryDatabase(repository)
        self.infoDict['atom'] = dbconn.retrieveAtom(idpackage)
        self.infoDict['checksum'] = dbconn.retrieveDigest(idpackage)
        self.infoDict['download'] = dbconn.retrieveDownloadURL(idpackage)
        self.infoDict['verified'] = False
        self.infoDict['steps'] = []
        if not repository.endswith(".tbz2"):
            if self.Entropy.check_needed_package_download(self.infoDict['download'], None) < 0:
                self.infoDict['steps'].append("fetch")
            if dochecksum:
                self.infoDict['steps'].append("checksum")
        # if file exists, first checksum then fetch
        if os.path.isfile(os.path.join(etpConst['entropyworkdir'],self.infoDict['download'])):
            self.infoDict['steps'].reverse()
