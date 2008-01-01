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
import time
import shutil
from entropyConstants import *
from clientConstants import *
from outputTools import *
import remoteTools
import exceptionTools
from entropyTools import compareMd5, bytesIntoHuman, getRandomNumber, dep_getkey, uncompressTarBz2, extractXpak, applicationLockCheck, countdown, isRoot, spliturl, remove_tag, dep_striptag, md5sum, allocateMaskedFile, istextfile, isnumber, extractEdb, unpackXpak, lifobuffer, ebeep, parallelStep
from databaseTools import openRepositoryDatabase, openClientDatabase
import confTools
import dumpTools
import gc

# Logging initialization
import logTools
equoLog = logTools.LogFile(level = etpConst['equologlevel'],filename = etpConst['equologfile'], header = "[Equo]")


'''
    Main Entropy (client side) package management class
'''
class EquoInterface(TextInterface):

    '''
        @input indexing(bool): enable/disable database tables indexing
        @input noclientdb(bool): if enabled, client database non-existance will be ignored
        @input xcache(bool): enable/disable database caching
    '''
    def __init__(self, indexing = True, noclientdb = False, xcache = True, server = False, server_readonly = True, server_noupload = True):

        import dumpTools
        self.dumpTools = dumpTools
        import databaseTools
        self.databaseTools = databaseTools
        import entropyTools
        self.entropyTools = entropyTools
        import confTools
        self.confTools = confTools
        self.indexing = indexing
        self.noclientdb = noclientdb
        self.xcache = xcache
        if server:
            self.server_readonly = server_readonly
            self.server_noupload = server_noupload
            self.openServerDatabase()
        else:
            self.openClientDatabase()
        self.repoDbCache = {}
        # Packages installation stuff
        self.transaction_ready = False
        self.steps = []
        self.transaction_running = False

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
        self.openClientDatatabase()

    def reopenServerDbconn(self, readonly = True, noupload = True):
        self.serverDbconn.closeDB()
        self.server_readonly = readonly
        self.server_noupload = noupload
        self.openServerDatabase()

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

    def openServerDatabase(self):
        self.serverDbconn = self.databaseTools.openServerDatabase(readOnly = self.server_readonly,
                                                                    noUpload = self.server_noupload
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
        mybuffer = lifobuffer()
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
            self.updateProgress(":: "+str(round((float(count)/maxlen)*100,1))+"% ::", importance = 0, type = "info", back = True)
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
        Package actions interface :: begin
    '''
    # @input pkgdata(dict): dictionary containing all the information needed to run the steps
    # @input steps(list): list of steps to run
    def prepare_steps(self, pkgdata, steps):
        self.infoDict = pkgdata.copy()
        self.steps = steps[:]
        self.transaction_ready = True

    
    



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


def addFailingMirror(mirrorname,increment = 1):
    item = etpRemoteFailures.get(mirrorname)
    if item == None:
        etpRemoteFailures[mirrorname] = increment
    else:
        etpRemoteFailures[mirrorname] += increment # add a failure
    return etpRemoteFailures[mirrorname]

def getFailingMirrorStatus(mirrorname):
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
def fetchFileOnMirrors(repository, filename, digest = False, verified = False):

    uris = etpRepositories[repository]['packages'][::-1]
    remaining = set(uris[:])

    if verified: # file is already in place, matchChecksum set infoDict['verified'] to True
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
        if getFailingMirrorStatus(uri) >= 30:
            # ohohoh!
            etpRemoteFailures[uri] = 30 # set to 30 for convenience
            print_warning(red("   ## ")+mirrorCountText+blue(" Mirror: ")+red(spliturl(url)[1])+" - maximum failure threshold reached.")
            if getFailingMirrorStatus(uri) == 30:
                addFailingMirror(uri,45) # put to 75 then decrement by 4 so we won't reach 30 anytime soon ahahaha
            else:
                # now decrement each time this point is reached, if will be back < 30, then equo will try to use it again
                if getFailingMirrorStatus(uri) > 31:
                    addFailingMirror(uri,-4)
                else:
                    # put to 0 - reenable mirror, welcome back uri!
                    etpRemoteFailures[uri] = 0
            
            remaining.remove(uri)
            continue
        
        # now fetch the new one
	print_info(red("   ## ")+mirrorCountText+blue("Downloading from: ")+red(spliturl(url)[1]))
	rc, data_transfer = fetchFile(url, digest)
	if rc == 0:
	    print_info(red("   ## ")+mirrorCountText+blue("Successfully downloaded from: ")+red(spliturl(url)[1])+blue(" at "+str(bytesIntoHuman(data_transfer))+"/sec"))
	    return 0
	else:
	    # something bad happened
	    if rc == -1:
		print_warning(red("   ## ")+mirrorCountText+blue("Error downloading from: ")+red(spliturl(url)[1])+" - file not available on this mirror.")
	    elif rc == -2:
                addFailingMirror(uri,1)
		print_warning(red("   ## ")+mirrorCountText+blue("Error downloading from: ")+red(spliturl(url)[1])+" - wrong checksum.")
	    elif rc == -3:
                addFailingMirror(uri,2)
		print_warning(red("   ## ")+mirrorCountText+blue("Error downloading from: ")+red(spliturl(url)[1])+" - not found.")
	    elif rc == -4:
		print_warning(red("   ## ")+mirrorCountText+blue("Discarded download."))
		return -1
	    else:
                addFailingMirror(uri, 5)
		print_warning(red("   ## ")+mirrorCountText+blue("Error downloading from: ")+red(spliturl(url)[1])+" - unknown reason.")
	    remaining.remove(uri)

'''
   @description: download a package into etpConst['packagesbindir'] and check for digest if digest is not False
   @input package: url -> HTTP/FTP url, digest -> md5 hash of the file
   @output: -1 = download error (cannot find the file), -2 = digest error, 0 = all fine
'''
def fetchFile(url, digest = None):
    # remove old
    filename = os.path.basename(url)
    filepath = etpConst['packagesbindir']+"/"+etpConst['branch']+"/"+filename
    if os.path.exists(filepath):
        os.remove(filepath)

    # load class
    fetchConn = remoteTools.urlFetcher(url, filepath)
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

def matchChecksum(infoDict):
    dlcount = 0
    match = False
    while dlcount <= 5:
	print_info(red("   ## ")+blue("Checking package checksum..."), back = True)
	dlcheck = checkNeededDownload(infoDict['download'], checksum = infoDict['checksum'])
	if dlcheck == 0:
	    print_info(red("   ## ")+blue("Package checksum matches."))
            infoDict['verified'] = True
	    match = True
	    break # file downloaded successfully
	else:
	    dlcount += 1
	    print_info(red("   ## ")+blue("Package checksum does not match. Redownloading... attempt #"+str(dlcount)), back = True)
	    fetch = fetchFileOnMirrors(infoDict['repository'],infoDict['download'],infoDict['checksum'])
	    if fetch != 0:
		print_info(red("   ## ")+blue("Cannot properly fetch package! Quitting."))
		return 1
            else:
                infoDict['verified'] = True
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
	if not etpUi['quiet']: print_info(red("   ## ")+blue("Removing from database: ")+red(infoDict['removeatom']))
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
    for item in content:
        # collision check
        if etpConst['collisionprotect'] > 0:
            
            if clientDbconn.isFileAvailable(item) and os.path.isfile(etpConst['systemroot']+item): # in this way we filter out directories
                if not etpUi['quiet']: print_warning(darkred("   ## ")+red("Collision found during remove of ")+etpConst['systemroot']+item+red(" - cannot overwrite"))
                equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Collision found during remove of "+etpConst['systemroot']+item+" - cannot overwrite")
                continue
    
        protected = False
        if (not infoDict['removeconfig']) and (not infoDict['diffremoval']):
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
                        protected = istextfile(etpConst['systemroot']+item)
                    else:
                        protected = False # it's not a file
                # -- CONFIGURATION FILE PROTECTION --
            except:
                pass # some filenames are buggy encoded
        
        
        if (protected):
            equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"[remove] Protecting config file: "+etpConst['systemroot']+item)
            if not etpUi['quiet']: print_warning(darkred("   ## ")+red("[remove] Protecting config file: ")+etpConst['systemroot']+item)
        else:
            try:
                os.lstat(etpConst['systemroot']+item)
            except OSError:
                continue # skip file, does not exist
            except UnicodeEncodeError:
                print_warning(darkred("   ## ")+red("QA: ")+brown("this package contains a badly encoded file"))
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
    del content
    clientDbconn.closeDB()
    del clientDbconn
    return 0

'''
   @description: unpack the given package file into the unpack dir
   @input infoDict: dictionary containing package information
   @output: 0 = all fine, >0 = error!
'''
def unpackPackage(infoDict):

    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Unpacking package: "+str(infoDict['atom']))

    if os.path.isdir(infoDict['unpackdir']):
	shutil.rmtree(infoDict['unpackdir'])
    os.makedirs(infoDict['imagedir'])

    rc = uncompressTarBz2(infoDict['pkgpath'], infoDict['imagedir'], catchEmpty = True)
    if (rc != 0):
	return rc
    if not os.path.isdir(infoDict['imagedir']):
	return 2
    
    # unpack xpak ?
    if etpConst['gentoo-compat']:
        #os.remove(infoDict['xpakpath']+"/"+etpConst['entropyxpakfilename'])
        if os.path.isdir(infoDict['xpakpath']):
	    shutil.rmtree(infoDict['xpakpath'])
        try:
            os.rmdir(infoDict['xpakpath'])
        except OSError:
            pass
        os.makedirs(infoDict['xpakpath'])
        # create data dir where we'll unpack the xpak
        os.mkdir(infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'])
        # now unpack for real
        xpakPath = infoDict['xpakpath']+"/"+etpConst['entropyxpakfilename']

        if (infoDict['smartpackage']):
            # we need to get the .xpak from database
            xdbconn = openRepositoryDatabase(infoDict['repository'])
            xpakdata = xdbconn.retrieveXpakMetadata(infoDict['idpackage'])
            if xpakdata:
                # save into a file
                f = open(xpakPath,"wb")
                f.write(xpakdata)
                f.flush()
                f.close()
                infoDict['xpakstatus'] = unpackXpak(xpakPath,infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'])
            else:
                infoDict['xpakstatus'] = None
            xdbconn.closeDB()
            del xdbconn
            del xpakdata
        else:
            infoDict['xpakstatus'] = extractXpak(infoDict['pkgpath'],infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'])

        # create fake portage ${D} linking it to imagedir
        portage_db_fakedir = os.path.join(infoDict['unpackdir'],"portage/"+infoDict['category']+"/"+infoDict['name']+"-"+infoDict['version'])
        os.makedirs(portage_db_fakedir)
        # now link it to infoDict['imagedir']
        os.symlink(infoDict['imagedir'],os.path.join(portage_db_fakedir,"image"))

    
    return 0

'''
   @description: function that runs at the end of the package installation process, just removes data left by other steps
   @input infoDict: dictionary containing package information
   @output: 0 = all fine, >0 = error!
'''
def cleanupPackage(infoDict):

    # remove unpack dir
    shutil.rmtree(infoDict['unpackdir'],True)
    try:
        os.rmdir(infoDict['unpackdir'])
    except OSError:
        pass

    return 0

'''
   @description: install unpacked files, update database and also update gentoo db if requested
   @input infoDict: dictionary containing package information
   @output: 0 = all fine, >0 = error!
'''
def installPackage(infoDict):
    
    # clear on-disk cache
    generateDependsTreeCache.clear()
    dumpTools.dumpobj(etpCache['generateDependsTree'],{})

    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Installing package: "+str(infoDict['atom']))

    # load CONFIG_PROTECT and its mask
    protect = etpRepositories[infoDict['repository']]['configprotect']
    mask = etpRepositories[infoDict['repository']]['configprotectmask']

    # copy files over - install
    rc = moveImageToSystem(infoDict['imagedir'], protect, mask)
    if rc != 0:
        return rc

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

    rc = 0
    if (etpConst['gentoo-compat']):
	equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Installing new Gentoo database entry: "+str(infoDict['atom']))
	rc = installPackageIntoGentooDatabase(infoDict, newidpackage = newidpackage)
    
    return rc

def moveImageToSystem(imageDir, protect, mask):
    
    clientDbconn = openClientDatabase()

    # setup imageDir properly
    imageDir = imageDir.encode(getfilesystemencoding())
    
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
                equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"WARNING!!! "+rootdir+" is a file when it should be a directory !! Removing in 20 seconds...")
                print_warning(red(" *** ")+bold(rootdir)+red(" is a file when it should be a directory !! Removing in 20 seconds..."))
                ebeep(10)
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
		if clientDbconn.isFileAvailable(todbfile):
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
                            oldtofile = tofile
                            if oldtofile.find("._cfg") != -1:
                                oldtofile = os.path.dirname(oldtofile)+"/"+os.path.basename(oldtofile)[10:]
                            equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Protecting config file: "+oldtofile)
                            print_warning(darkred("   ## ")+red("Protecting config file: ")+oldtofile)
                    else:
                        equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Skipping config file installation, as stated in equo.conf: "+tofile)
                        print_warning(darkred("   ## ")+red("Skipping file installation: ")+tofile)
                        continue
	    
	        # -- CONFIGURATION FILE PROTECTION --
	
	    except:
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
                    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"WARNING!!! "+tofile+" is a directory when it should be a file !! Removing in 20 seconds...")
                    print_warning(red(" *** ")+bold(tofile)+red(" is a directory when it should be a file !! Removing in 20 seconds..."))
                    ebeep(10)
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
                confTools.addtocache(tofile)

    clientDbconn.closeDB()
    del clientDbconn
    return 0

    
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
	    os.system("sed -i '/"+skippedKey+"/d' "+etpConst['systemroot']+"/var/lib/portage/world")

    return 0

'''
   @description: inject the database information into the Gentoo database
   @input package: dictionary containing information collected by installPackages (important are atom, slot, category, name, version)
   @output: 0 = all fine, >0 = error!
'''
def installPackageIntoGentooDatabase(infoDict, newidpackage = -1):
    
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
	key = infoDict['category']+"/"+infoDict['name']
	#print portageTools.getInstalledAtom(key)
	atomsfound = set()
        dbdirs = os.listdir(portDbDir)
        if infoDict['category'] in dbdirs:
            catdirs = os.listdir(portDbDir+"/"+infoDict['category'])
            dirsfound = set([infoDict['category']+"/"+x for x in catdirs if key == dep_getkey(infoDict['category']+"/"+x)])
            atomsfound.update(dirsfound)
	
	### REMOVE
	# parse slot and match and remove
	if atomsfound:
	    pkgToRemove = ''
	    for atom in atomsfound:
	        atomslot = portageTools.getPackageSlot(atom)
		# get slot from gentoo db
	        if atomslot == infoDict['slot']:
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
        if infoDict['xpakstatus'] != None and os.path.isdir(infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']):
            if not os.path.isdir(portDbDir+infoDict['category']):
                os.makedirs(portDbDir+infoDict['category'])
            destination = portDbDir+infoDict['category']+"/"+infoDict['name']+"-"+infoDict['version']
            if os.path.isdir(destination):
                shutil.rmtree(destination)
            
            shutil.copytree(infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'],destination)
            
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
                clientDbconn = openClientDatabase()
                clientDbconn.setCounter(newidpackage,counter)
                clientDbconn.closeDB()
                del clientDbconn
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
    del dbconn
    #print data['dependencies']
    # open client db
    clientDbconn = openClientDatabase()
    # always set data['injected'] to False
    # installed packages database SHOULD never have more than one package for scope (key+slot)
    data['injected'] = False
    
    idpk, rev, x, status = clientDbconn.handlePackage(etpData = data, forcedRevision = data['revision'])
    del x
    del data
    
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
            #print depends
	    for depend in depends:
		atom = depend[1]
		iddep = depend[0]
		match = clientDbconn.atomMatch(atom)
		if (match[0] != -1):
		    clientDbconn.removeDependencyFromDependsTable(iddep)
		    clientDbconn.addDependRelationToDependsTable(iddep,match[0])
            del depends

	except:
	    clientDbconn.regenerateDependsTable()

    clientDbconn.closeDB()
    del clientDbconn
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
    del clientDbconn
    return 0



'''
    @description: execute the requested step (it is only used by the CLI client)
    @input: 	step -> name of the step to execute
    		infoDict -> dictionary containing all the needed information collected by installPackages() -> actionQueue[pkgatom]
                loopString -> used to print to xterm title bar something like "10/900 - equo"
    @output:	-1,"description" for error ; 0,True for no errors
'''
def stepExecutor(step, infoDict, loopString = None):

    import triggerTools

    clientDbconn = openClientDatabase()
    output = 0
    
    if loopString == None:
        loopString = ''
    
    if step == "fetch":
	print_info(red("   ## ")+blue("Fetching archive: ")+red(os.path.basename(infoDict['download'])))
        xtermTitle(loopString+' Fetching archive: '+os.path.basename(infoDict['download']))
	output = fetchFileOnMirrors(infoDict['repository'],infoDict['download'],infoDict['checksum'], infoDict['verified'])
	if output < 0:
	    print_error(red("Package cannot be fetched. Try to run: '")+bold("equo update")+red("' and this command again. Error "+str(output)))
    
    elif step == "checksum":
	output = matchChecksum(infoDict)

    elif step == "unpack":
	print_info(red("   ## ")+blue("Unpacking package: ")+red(os.path.basename(infoDict['atom'])))
        xtermTitle(loopString+' Unpacking package: '+os.path.basename(infoDict['atom']))
	output = unpackPackage(infoDict)
	if output != 0:
	    if output == 512:
	        errormsg = red("You are running out of disk space. I bet, you're probably Michele. Error 512")
	    else:
	        errormsg = red("An error occured while trying to unpack the package. Check if your system is healthy. Error "+str(output))
	    print_error(errormsg)

    elif step == "install":
        compatstring = ''
	if (etpConst['gentoo-compat']):
            compatstring = " ## w/Gentoo compatibility"
	print_info(red("   ## ")+blue("Installing package: ")+red(os.path.basename(infoDict['atom']))+compatstring)
        xtermTitle(loopString+' Installing package: '+os.path.basename(infoDict['atom'])+compatstring)
	output = installPackage(infoDict)
	if output != 0:
	    print_error(red("An error occured while trying to install the package. Check if your system is healthy. Error "+str(output)))
    
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
            print_warning(brown('   ## ')+darkgreen("Gentoo ebuild messages:"))
	for msg in infoDict['messages']:
	    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,msg)
	    print_warning(brown('   ## ')+msg)
	if infoDict['messages']:
	    equoLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"End message.")
    
    elif step == "postinstall":
	# analyze atom
	pkgdata = infoDict['triggers'].get('install')
	if pkgdata:
            pkgdata.update(infoDict)
	    triggers = triggerTools.postinstall(pkgdata)
	    for trigger in triggers:
                if trigger not in etpUi['postinstall_triggers_disable']:
                    eval("triggerTools."+trigger)(pkgdata)
            del triggers
        del pkgdata

    elif step == "preinstall":
	# analyze atom
	pkgdata = infoDict['triggers'].get('install')
	if pkgdata:
            pkgdata.update(infoDict)
	    triggers = triggerTools.preinstall(pkgdata)
            
	    if (infoDict.get("diffremoval") != None): # diffremoval is true only when the remove action is triggered by installPackages()
                if infoDict['diffremoval']:
                    remdata = infoDict['triggers'].get('remove')
                    if remdata:
                        itriggers = triggerTools.preremove(remdata) # remove duplicated triggers
                        triggers = triggers - itriggers
                        del itriggers
                    del remdata
            
	    for trigger in triggers:
                if trigger not in etpUi['preinstall_triggers_disable']:
                    eval("triggerTools."+trigger)(pkgdata)
            del triggers
        del pkgdata

    elif step == "preremove":
	# analyze atom
	remdata = infoDict['triggers'].get('remove')
	if remdata:
            remdata.update(infoDict)
	    triggers = triggerTools.preremove(remdata)
	    for trigger in triggers:
                if trigger not in etpUi['preremove_triggers_disable']:
                    eval("triggerTools."+trigger)(remdata)
            del triggers
        del remdata

    elif step == "postremove":
	# analyze atom
	remdata = infoDict['triggers'].get('remove')
	if remdata:
            remdata.update(infoDict)
	    triggers = triggerTools.postremove(remdata)
	    if infoDict['diffremoval'] and (infoDict.get("atom") != None): # diffremoval is true only when the remove action is triggered by installPackages()
		pkgdata = infoDict['triggers'].get('install')
		if pkgdata:
		    itriggers = triggerTools.postinstall(pkgdata)
		    triggers = triggers - itriggers
                    del itriggers
                del pkgdata
	    
	    for trigger in triggers:
                if trigger not in etpUi['postremove_triggers_disable']:
                    eval("triggerTools."+trigger)(remdata)
            del triggers
        del remdata

    elif step == "cleanup":
	print_info(red("   ## ")+blue("Cleaning temporary files for: ")+red(os.path.basename(infoDict['atom'])))
        xtermTitle(loopString+' Cleaning temporary files for: '+os.path.basename(infoDict['atom']))
        parallelStep(cleanupPackage,infoDict)
        # we don't care if cleanupPackage fails since it's not critical
        '''
	output = cleanupPackage(infoDict)
	if output != 0:
	    print_error(red("An error occured while trying to cleanup package temporary directories. Check if your system is healthy. Error "+str(output)))
        '''

    clientDbconn.closeDB()
    del clientDbconn
    
    # clear garbage
    gc.collect()
    
    return output
