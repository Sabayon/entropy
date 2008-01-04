#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2008 Fabio Erculiani

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

import shutil
import commands
import urllib2
import socket
import random
from entropyConstants import *
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
        import triggerTools
        import gc
        self.gcTool = gc
        self.triggerTools = triggerTools
        self.urlFetcher = urlFetcher # in this way, can be reimplemented (so you can override updateProgress)
        self.progress = None # supporting external updateProgress stuff, you can point self.progress to your progress bar
                             # and reimplement updateProgress
        self.FtpInterface = FtpInterface # for convenience
        self.indexing = indexing
        self.noclientdb = noclientdb
        self.xcache = xcache
        self.openClientDatabase()
        self.FileUpdates = self.__FileUpdates()
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
        self.clientDbconn = self.databaseTools.openClientDatabase(indexing = self.indexing, generate = self.noclientdb, xcache = self.xcache)
        return self.clientDbconn # just for reference

    def clientDatabaseSanityCheck(self):
        self.updateProgress(darkred("Sanity Check: system database"), importance = 2, type = "warning")
        idpkgs = self.clientDbconn.listAllIdpackages()
        length = len(idpkgs)
        count = 0
        errors = False
        for x in idpkgs:
            count += 1
            self.updateProgress(
                                    darkgreen("Scanning..."),
                                    importance = 0,
                                    type = "info",
                                    back = True,
                                    count = (count,length),
                                    percent = True
                                )
            try:
                self.clientDbconn.getPackageData(x)
            except Exception ,e:
                errors = True
                self.updateProgress(
                                        darkred("Errors on idpackage %s, exception: %s, error: %s") %  (str(x), str(Exception),str(e)),
                                        importance = 0,
                                        type = "warning"
                                   )

        if not errors:
            self.updateProgress(darkred("Sanity Check: %s") % (bold("PASSED"),), importance = 2, type = "warning")
            return 0
        else:
            self.updateProgress(darkred("Sanity Check: %s") % (bold("CORRUPUTED"),), importance = 2, type = "warning")
            return -1

    def openRepositoryDatabase(self, repoid):
        if not self.repoDbCache.has_key((repoid,etpConst['systemroot'])):
            dbconn = self.loadRepositoryDatabase(repoid, xcache = self.xcache, indexing = self.indexing)
            self.repoDbCache[(repoid,etpConst['systemroot'])] = dbconn
            return dbconn
        else:
            return self.repoDbCache.get((repoid,etpConst['systemroot']))

    '''
    @description: open the repository database
    @input repositoryName: name of the client database
    @input xcache: loads on-disk cache
    @input indexing: indexes SQL tables
    @output: database class instance
    NOTE: DO NOT USE THIS DIRECTLY, BUT USE EquoInterface.openRepositoryDatabase
    '''
    def loadRepositoryDatabase(self, repositoryName, xcache = True, indexing = True):
        dbfile = etpRepositories[repositoryName]['dbpath']+"/"+etpConst['etpdatabasefile']
        if not os.path.isfile(dbfile):
            self.fetch_repository_if_not_available(repositoryName)
        conn = self.databaseTools.etpDatabase(readOnly = True, dbFile = dbfile, clientDatabase = True, dbname = etpConst['dbnamerepoprefix']+repositoryName, xcache = xcache, indexing = indexing)
        # initialize CONFIG_PROTECT
        if (etpRepositories[repositoryName]['configprotect'] == None) or \
            (etpRepositories[repositoryName]['configprotectmask'] == None):

            etpRepositories[repositoryName]['configprotect'] = conn.listConfigProtectDirectories()
            etpRepositories[repositoryName]['configprotectmask'] = conn.listConfigProtectDirectories(mask = True)
            etpRepositories[repositoryName]['configprotect'] = [etpConst['systemroot']+x for x in etpRepositories[repositoryName]['configprotect']]
            etpRepositories[repositoryName]['configprotectmask'] = [etpConst['systemroot']+x for x in etpRepositories[repositoryName]['configprotectmask']]

            etpRepositories[repositoryName]['configprotect'] += [etpConst['systemroot']+x for x in etpConst['configprotect'] if etpConst['systemroot']+x not in etpRepositories[repositoryName]['configprotect']]
            etpRepositories[repositoryName]['configprotectmask'] += [etpConst['systemroot']+x for x in etpConst['configprotectmask'] if etpConst['systemroot']+x not in etpRepositories[repositoryName]['configprotectmask']]
        if not etpConst['treeupdatescalled'] and (etpConst['uid'] == 0):
            conn.clientUpdatePackagesData()
        return conn

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
        self.FileUpdates.scanfs(dcache = False)
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

    def dependencies_test(self, dbconn = None):

        if dbconn == None:
            dbconn = self.clientDbconn
        # get all the installed packages
        installedPackages = dbconn.listAllIdpackages()

        depsNotSatisfied = {}
        # now look
        length = str((len(installedPackages)))
        count = 0
        for xidpackage in installedPackages:
            count += 1
            atom = dbconn.retrieveAtom(xidpackage)
            self.updateProgress(
                                    darkgreen(" Checking ")+bold(atom),
                                    importance = 0,
                                    type = "info",
                                    back = True,
                                    count = (count,length),
                                    header = darkred(" @@ ")
                                )

            xdeps = dbconn.retrieveDependenciesList(xidpackage)
            needed_deps = set()
            for xdep in xdeps:
                if xdep[0] == "!": # filter conflicts
                    continue
                xmatch = dbconn.atomMatch(xdep)
                if xmatch[0] == -1:
                    needed_deps.add(xdep)

            if needed_deps:
                depsNotSatisfied[xidpackage] = set()
                depsNotSatisfied[xidpackage].update(needed_deps)

        depsNotMatched = set()
        if (depsNotSatisfied):
            for xidpackage in depsNotSatisfied:
                for dep in depsNotSatisfied[xidpackage]:
                    match = dbconn.atomMatch(dep)
                    if match[0] == -1: # ????
                        depsNotMatched.add(dep)
                        continue

        return depsNotMatched

    def libraries_test(self, dbconn = None, reagent = False):

        if dbconn == None:
            dbconn = self.clientDbconn

        self.updateProgress(
                                blue("Dependencies test"),
                                importance = 2,
                                type = "info",
                                header = red(" @@ ")
                            )

        if not etpConst['systemroot']:
            myroot = "/"
        else:
            myroot = etpConst['systemroot']+"/"
        # run ldconfig first
        os.system("ldconfig -r "+myroot+" &> /dev/null")
        # open /etc/ld.so.conf
        if not os.path.isfile(etpConst['systemroot']+"/etc/ld.so.conf"):
            self.updateProgress(
                                    blue("Cannot find ")+red(etpConst['systemroot']+"/etc/ld.so.conf"),
                                    importance = 1,
                                    type = "error",
                                    header = red(" @@ ")
                                )
            return (),(),-1

        ldpaths = self.entropyTools.collectLinkerPaths()

        executables = set()
        total = len(ldpaths)
        count = 0
        for ldpath in ldpaths:
            count += 1
            self.updateProgress(
                                    blue("Tree: ")+red(etpConst['systemroot']+ldpath),
                                    importance = 0,
                                    type = "info",
                                    count = (count,total),
                                    back = True,
                                    percent = True,
                                    header = "  "
                                )
            ldpath = ldpath.encode(sys.getfilesystemencoding())
            for currentdir,subdirs,files in os.walk(etpConst['systemroot']+ldpath):
                for item in files:
                    filepath = currentdir+"/"+item
                    if os.access(filepath,os.X_OK):
                        executables.add(filepath[len(etpConst['systemroot']):])

        self.updateProgress(
                                blue("Collecting broken executables"),
                                importance = 2,
                                type = "info",
                                header = red(" @@ ")
                            )
        self.updateProgress(
                                red("Attention: ")+blue("don't worry about libraries that are shown here but not later."),
                                importance = 1,
                                type = "info",
                                header = red(" @@ ")
                            )

        brokenlibs = set()
        brokenexecs = {}
        total = len(executables)
        count = 0
        for executable in executables:
            count += 1
            self.updateProgress(
                                    red(etpConst['systemroot']+executable),
                                    importance = 0,
                                    type = "info",
                                    count = (count,total),
                                    back = True,
                                    percent = True,
                                    header = "  "
                                )
            if not etpConst['systemroot']:
                stdin, stdouterr = os.popen4("ldd "+executable)
            else:
                if not os.access(etpConst['systemroot']+"/bin/sh",os.X_OK):
                    raise exceptionTools.FileNotFound("FileNotFound: /bin/sh not found.")
                stdin, stdouterr = os.popen4("echo 'ldd "+executable+"' | chroot "+etpConst['systemroot'])
            output = stdouterr.readlines()
            if '\n'.join(output).find("not found") != -1:
                # investigate
                mylibs = set()
                for row in output:
                    if row.find("not found") != -1:
                        try:
                            row = row.strip().split("=>")[0].strip()
                            mylibs.add(row)
                        except:
                            continue
                if mylibs:
                    alllibs = blue(' :: ').join(list(mylibs))
                    self.updateProgress(
                                            red(etpConst['systemroot']+executable)+" [ "+alllibs+" ]",
                                            importance = 1,
                                            type = "info",
                                            percent = True,
                                            count = (count,total),
                                            header = "  "
                                        )
                brokenlibs.update(mylibs)
                brokenexecs[executable] = mylibs.copy()
        del executables

        self.updateProgress(
                                blue("Trying to match packages"),
                                importance = 1,
                                type = "info",
                                header = red(" @@ ")
                            )


        packagesMatched = set()
        # now search packages that contain the found libs
        orderedRepos = list(etpRepositoriesOrder)
        orderedRepos.sort()

        # match libraries
        for repodata in orderedRepos:
            self.updateProgress(
                                    blue("Repository: ")+darkgreen(etpRepositories[repodata[1]]['description'])+" ["+red(repodata[1])+"]",
                                    importance = 1,
                                    type = "info",
                                    header = red(" @@ ")
                                )
            if reagent:
                rdbconn = dbconn
            else:
                rdbconn = self.openRepositoryDatabase(repodata[1])
            libsfound = set()
            for lib in brokenlibs:
                packages = rdbconn.searchBelongs(file = "%"+lib, like = True, branch = etpConst['branch'])
                if packages:
                    for idpackage in packages:
                        # retrieve content and really look if library is in ldpath
                        mycontent = rdbconn.retrieveContent(idpackage)
                        matching_libs = [x for x in mycontent if x.endswith(lib) and (os.path.dirname(x) in ldpaths)]
                        libsfound.add(lib)
                        if matching_libs:
                            packagesMatched.add((idpackage,repodata[1],lib))
            brokenlibs.difference_update(libsfound)

        return packagesMatched,brokenlibs,0

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

    # @returns -1 if the file does not exist or contains bad data
    # @returns int>0 if the file exists
    def get_repository_revision(self, reponame):
        if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabaserevisionfile']):
            f = open(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'],"r")
            try:
                revision = int(f.readline().strip())
            except:
                revision = -1
            f.close()
        else:
            revision = -1
        return revision

    # @returns -1 if the file does not exist
    # @returns int>0 if the file exists
    def get_repository_db_file_checksum(self, reponame):
        if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasehashfile']):
            f = open(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
            try:
                mhash = f.readline().strip().split()[0]
            except:
                mhash = "-1"
            f.close()
        else:
            mhash = "-1"
        return mhash

    def fetch_repository_if_not_available(self, reponame):
        # open database
        rc = 0
        dbfile = etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasefile']
        if not os.path.isfile(dbfile):
            # sync
            repoConn = self.Repositories(reponames = [reponame])
            rc = repoConn.sync()
            if rc != 0:
                raise exceptionTools.RepositoryError("RepositoryError: cannot fetch database for repo id: "+reponame)
            del repoConn
        if not os.path.isfile(dbfile):
            raise exceptionTools.RepositoryError("RepositoryError: cannot fetch database for repo id: "+reponame)
        return rc

    '''
    @description: matches the package that user chose, using dbconnection.atomMatch searching in all available repositories.
    @input atom: user choosen package name
    @output: the matched selection, list: [package id,repository name] | if nothing found, returns: ( -1,1 )
    @ exit errors:
                -1 => repository cannot be fetched online
    '''
    def atomMatch(self, atom, caseSensitive = True, matchSlot = None, matchBranches = ()):

        if self.xcache:
            cached = atomMatchCache.get(atom)
            if cached:
                try:
                    if (cached['matchSlot'] == matchSlot) and (cached['matchBranches'] == matchBranches) and (cached['etpRepositories'] == etpRepositories) and (cached['caseSensitive'] == caseSensitive):
                        return cached['result']
                except KeyError:
                    pass

        repoResults = {}
        exitErrors = {}
        for repo in etpRepositories:
            # sync database if not available
            rc = self.fetch_repository_if_not_available(repo)
            if (rc != 0):
                exitErrors[repo] = -1
                continue
            # open database
            dbconn = self.openRepositoryDatabase(repo)

            # search
            query = dbconn.atomMatch(atom, caseSensitive = caseSensitive, matchSlot = matchSlot, matchBranches = matchBranches)
            if query[1] == 0:
                # package found, add to our dictionary
                repoResults[repo] = query[0]

        # handle repoResults
        packageInformation = {}

        # nothing found
        if not repoResults:
            atomMatchCache[atom] = {}
            atomMatchCache[atom]['result'] = -1,1
            atomMatchCache[atom]['matchSlot'] = matchSlot
            atomMatchCache[atom]['matchBranches'] = matchBranches
            atomMatchCache[atom]['caseSensitive'] = caseSensitive
            atomMatchCache[atom]['etpRepositories'] = etpRepositories.copy()
            return -1,1

        elif len(repoResults) == 1:
            # one result found
            for repo in repoResults:
                atomMatchCache[atom] = {}
                atomMatchCache[atom]['result'] = repoResults[repo],repo
                atomMatchCache[atom]['matchSlot'] = matchSlot
                atomMatchCache[atom]['matchBranches'] = matchBranches
                atomMatchCache[atom]['caseSensitive'] = caseSensitive
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
                dbconn = self.openRepositoryDatabase(repo)
                # search
                packageInformation[repo] = {}
                packageInformation[repo]['version'] = dbconn.retrieveVersion(repoResults[repo])
                packageInformation[repo]['versiontag'] = dbconn.retrieveVersionTag(repoResults[repo])
                packageInformation[repo]['revision'] = dbconn.retrieveRevision(repoResults[repo])

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
                    tags = [conflictingEntries[x]['versiontag'] for x in conflictingEntries]
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
                                        atomMatchCache[atom]['caseSensitive'] = caseSensitive
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
                            atomMatchCache[atom]['caseSensitive'] = caseSensitive
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
                        atomMatchCache[atom]['caseSensitive'] = caseSensitive
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
                    atomMatchCache[atom]['caseSensitive'] = caseSensitive
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
                atomMatchCache[atom]['caseSensitive'] = caseSensitive
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
                dbconn = self.openRepositoryDatabase(repoMatch[1])
                repo_pkgver = dbconn.retrieveVersion(repoMatch[0])
                repo_pkgtag = dbconn.retrieveVersionTag(repoMatch[0])
                repo_pkgrev = dbconn.retrieveRevision(repoMatch[0])
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
                # not the same version installed
                filterSatisfiedDependenciesCmpResults[dependency] = 10
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

        mydbconn = self.openRepositoryDatabase(atomInfo[1])
        myatom = mydbconn.retrieveAtom(atomInfo[0])

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
            matchdb = self.openRepositoryDatabase(match[1])
            matchatom = matchdb.retrieveAtom(match[0])
            matchslot = matchdb.retrieveSlot(match[0]) # used later
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

            matchdb = self.openRepositoryDatabase(match[1])
            myundeps = matchdb.retrieveDependenciesList(match[0])
            if (not empty_deps):
                myundeps, xxx = self.filterSatisfiedDependencies(myundeps, deep_deps = deep_deps)
                del xxx
            for x in myundeps:
                mybuffer.push((treedepth,x))

            # handle possible library breakage
            self.filterSatisfiedDependencies([mydep[1]], deep_deps = deep_deps)
            action = filterSatisfiedDependenciesCmpResults.get(mydep[1])
            if action and ((action < 0) or (action > 0)): # do not use != 0 since action can be "None"
                i = self.clientDbconn.atomMatch(self.entropyTools.dep_getkey(mydep[1]), matchSlot = matchslot)
                if i[0] != -1:
                    oldneeded = self.clientDbconn.retrieveNeeded(i[0])
                    if oldneeded: # if there are needed
                        ndbconn = self.openRepositoryDatabase(match[1])
                        needed = ndbconn.retrieveNeeded(match[0])
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
                                        mydbconn = self.openRepositoryDatabase(mymatch[1])
                                        mynewatom = mydbconn.retrieveAtom(mymatch[0])
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
            myscopedata = self.clientDbconn.getScopeData(idpackage)
            category = myscopedata[0]
            name = myscopedata[1]
            slot = myscopedata[3]
            revision = myscopedata[5]
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
                elif (revision == arevision):
                    # check if "needed" are the same, otherwise, pull
                    # this will avoid having old packages installed just because user ran equo database generate (migrating from gentoo)
                    # also this helps in environments with multiple repositories, to avoid messing with libraries
                    aneeded = adbconn.retrieveNeeded(match[0])
                    needed = self.clientDbconn.retrieveNeeded(idpackage)
                    if needed != aneeded:
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

    # every tbz2 file that would be installed must pass from here
    def add_tbz2_to_repos(self, tbz2file):
        atoms_contained = []
        basefile = os.path.basename(tbz2file)
        if os.path.isdir(etpConst['entropyunpackdir']+"/"+basefile[:-5]):
            shutil.rmtree(etpConst['entropyunpackdir']+"/"+basefile[:-5])
        os.makedirs(etpConst['entropyunpackdir']+"/"+basefile[:-5])
        dbfile = self.entropyTools.extractEdb(tbz2file, dbpath = etpConst['entropyunpackdir']+"/"+basefile[:-5]+"/packages.db")
        if dbfile == None:
            return -1,atoms_contained
        etpSys['dirstoclean'].add(os.path.dirname(dbfile))
        # add dbfile
        etpRepositories[basefile] = {}
        etpRepositories[basefile]['description'] = "Dynamic database from "+basefile
        etpRepositories[basefile]['packages'] = []
        etpRepositories[basefile]['dbpath'] = os.path.dirname(dbfile)
        etpRepositories[basefile]['pkgpath'] = os.path.realpath(tbz2file) # extra info added
        etpRepositories[basefile]['configprotect'] = set()
        etpRepositories[basefile]['configprotectmask'] = set()
        etpRepositories[basefile]['smartpackage'] = False # extra info added
        # put at top priority, shift others
        myrepo_order = set([(x[0]+1,x[1]) for x in etpRepositoriesOrder])
        etpRepositoriesOrder.clear()
        etpRepositoriesOrder.update(myrepo_order)
        etpRepositoriesOrder.add((1,basefile))
        mydbconn = self.openGenericDatabase(dbfile)
        # read all idpackages
        try:
            myidpackages = mydbconn.listAllIdpackages() # all branches admitted from external files
        except:
            del etpRepositories[basefile]
            return -2,atoms_contained
        if len(myidpackages) > 1:
            etpRepositories[basefile]['smartpackage'] = True
        for myidpackage in myidpackages:
            compiled_arch = mydbconn.retrieveDownloadURL(myidpackage)
            if compiled_arch.find("/"+etpSys['arch']+"/") == -1:
                return -3,atoms_contained
            atoms_contained.append([tbz2file,(int(myidpackage),basefile)])
        mydbconn.closeDB()
        del mydbconn
        return 0,atoms_contained

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

    def retrieveRemovalQueue(self, idpackages, deep = False):
        queue = []
        treeview = self.generate_depends_tree(idpackages, deep = deep)
        treelength = len(treeview[0])
        if treelength > 1:
            treeview = treeview[0]
            for x in range(treelength)[::-1]:
                for y in treeview[x]:
                    queue.append(y)
        return queue

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
        Package interface :: begin
    '''

    # Get checksum of a package by running md5sum remotely (using php helpers)
    # @returns hex: if the file exists
    # @returns None: if the server does not support HTTP handlers
    # @returns None: if the file is not found
    # mainly used server side
    def get_remote_package_checksum(self, servername, filename, branch):

        # etpHandlers['md5sum'] is the command
        # create the request
        try:
            url = etpRemoteSupport[servername]
        except:
            # not found, does not support HTTP handlers
            return None

        # does the package has "#" (== tag) ? hackish thing that works
        filename = filename.replace("#","%23")
        # "+"
        filename = filename.replace("+","%2b")

        request = url+etpHandlers['md5sum']+filename+"&branch="+branch

        # now pray the server
        try:
            if etpConst['proxy']:
                proxy_support = urllib2.ProxyHandler(etpConst['proxy'])
                opener = urllib2.build_opener(proxy_support)
                urllib2.install_opener(opener)
            item = urllib2.urlopen(request)
            result = item.readline().strip()
            return result
        except: # no HTTP support?
            return None

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
    def fetch_file(self, url, digest = None, resume = True):
        # remove old
        filename = os.path.basename(url)
        filepath = etpConst['packagesbindir']+"/"+etpConst['branch']+"/"+filename

        # load class
        fetchConn = self.urlFetcher(url, filepath, resume = resume)
        fetchConn.progress = self.progress

        # start to download
        data_transfer = 0
        resumed = False
        try:
            fetchChecksum = fetchConn.download()
            data_transfer = fetchConn.datatransfer
            resumed = fetchConn.resumed
        except KeyboardInterrupt:
            return -4, data_transfer, resumed
        except NameError:
            raise
        except:
            return -1, data_transfer, resumed
        if fetchChecksum == "-3":
            return -3, data_transfer, resumed
    
        del fetchConn
        if (digest):
            if (fetchChecksum != digest):
                # not properly downloaded
                return -2, data_transfer, resumed
            else:
                return 0, data_transfer, resumed
        return 0, data_transfer, resumed

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

            do_resume = True
            while 1:
                try:
                    # now fetch the new one
                    self.updateProgress(
                                            mirrorCountText+blue("Downloading from: ")+red(self.entropyTools.spliturl(url)[1]),
                                            importance = 1,
                                            type = "warning",
                                            header = red("   ## ")
                                        )
                    rc, data_transfer, resumed = self.fetch_file(url, digest, do_resume)
                    if rc == 0:
                        self.updateProgress(
                                            mirrorCountText+blue("Successfully downloaded from: ")+red(self.entropyTools.spliturl(url)[1])+blue(" at "+str(self.entropyTools.bytesIntoHuman(data_transfer))+"/sec"),
                                            importance = 1,
                                            type = "info",
                                            header = red("   ## ")
                                        )
                        return 0
                    elif resumed:
                        do_resume = False
                        continue
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
                        break
                except KeyboardInterrupt:
                    break
                except:
                    raise

    def quickpkg(self, atomstring, savedir = None):
        if savedir == None:
            savedir = etpConst['packagestmpdir']
            if not os.path.isdir(etpConst['packagestmpdir']):
                os.makedirs(etpConst['packagestmpdir'])
        # match package
        match = self.clientDbconn.atomMatch(atomstring)
        if match[0] == -1:
            return -1,None,None
        atom = self.clientDbconn.atomMatch(match[0])
        pkgdata = self.clientDbconn.getPackageData(match[0])
        resultfile = self.entropyTools.quickpkg(pkgdata = pkgdata, dirpath = savedir)
        if resultfile == None:
            return -1,atom,None
        else:
            return 0,atom,resultfile

    def Package(self):
        conn = PackageInterface(EquoInstance = self)
        return conn

    def instanceTest(self):
        return

    '''
        Package interface :: end
    '''

    '''
        Repository interface :: begin
    '''
    def Repositories(self, reponames = [], forceUpdate = False):
        conn = RepoInterface(EquoInstance = self, reponames = reponames, forceUpdate = forceUpdate)
        return conn
    '''
        Repository interface :: end
    '''
    
    '''
        Configuration files (updates, not entropy related) interface :: begin
    '''
    def __FileUpdates(self):
        conn = FileUpdatesInterface(EquoInstance = self)
        return conn
    '''
        Configuration files (updates, not entropy related) interface :: end
    '''

'''
    Real package actions (install/remove) interface
'''
class PackageInterface:

    def __init__(self, EquoInstance):
        self.Entropy = EquoInstance
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
                    directories.add((etpConst['systemroot']+item,"link"))
                elif os.path.isdir(etpConst['systemroot']+item):
                    # plain directory
                    directories.add((etpConst['systemroot']+item,"dir"))
                else: # files, symlinks or not
                    # just a file or symlink or broken directory symlink (remove now)
                    try:
                        os.remove(etpConst['systemroot']+item)
                        # add its parent directory
                        dirfile = os.path.dirname(etpConst['systemroot']+item)
                        if os.path.isdir(dirfile) and os.path.islink(dirfile):
                            directories.add((dirfile,"link"))
                        elif os.path.isdir(dirfile):
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
    def __cleanup_package(self, data):
        # remove unpack dir
        shutil.rmtree(data['unpackdir'],True)
        try:
            os.rmdir(data['unpackdir'])
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
    @output: 0 = all fine, !=0 = error!
    '''
    def __install_package_into_gentoo_database(self, newidpackage):

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
                        pkgToRemove = atom
                        break
                if (pkgToRemove):
                    removePath = portDbDir+pkgToRemove
                    shutil.rmtree(removePath,True)
                    try:
                        os.rmdir(removePath)
                    except OSError:
                        pass
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
                    self.Entropy.updateProgress(
                                                red("QA: ")+brown("cannot update Gentoo counter, destination %s does not exist." % 
                                                        (destination,)
                                                ),
                                                importance = 1,
                                                type = "warning",
                                                header = darkred("   ## ")
                                        )

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
                    import time
                    time.sleep(20)
                    os.remove(rootdir)

                # if our directory is a symlink instead, then copy the symlink
                if os.path.islink(imagepathDir) and not os.path.isdir(rootdir): # for security we skip live items that are dirs
                    tolink = os.readlink(imagepathDir)
                    if os.path.islink(rootdir):
                        os.remove(rootdir)
                    os.symlink(tolink,rootdir)
                elif (not os.path.isdir(rootdir)) and (not os.access(rootdir,os.R_OK)):
                    os.makedirs(rootdir)

                if not os.path.islink(rootdir): # symlink don't need permissions, also until os.walk ends they might be broken
                    user = os.stat(imagepathDir)[4]
                    group = os.stat(imagepathDir)[5]
                    os.chown(rootdir,user,group)
                    shutil.copystat(imagepathDir,rootdir)

            for item in files:
                fromfile = currentdir+"/"+item
                tofile = etpConst['systemroot']+fromfile[len(imageDir):]

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

                except Exception, e:
                    self.Entropy.updateProgress(
                                                red("QA: ")+brown("cannot check CONFIG PROTECTION. Exception: %s :: error: %s" % (
                                                        str(Exception),
                                                        str(e),
                                                        )
                                                ),
                                                importance = 1,
                                                type = "warning",
                                                header = darkred("   ## ")
                                        )
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
                        import time
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
                    self.Entropy.FileUpdates.add_to_cache(tofile)

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
        tdict = {}
        tdict['unpackdir'] = self.infoDict['unpackdir']
        task = self.Entropy.entropyTools.parallelTask(self.__cleanup_package, tdict)
        task.start()
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
                self.xterm_title += 'Fetching: '+os.path.basename(self.infoDict['download'])
                xtermTitle(self.xterm_title)
                rc = self.fetch_step()

            elif step == "checksum":
                self.xterm_title += 'Verifying: '+os.path.basename(self.infoDict['download'])
                xtermTitle(self.xterm_title)
                rc = self.checksum_step()

            elif step == "unpack":
                self.xterm_title += 'Unpacking: '+os.path.basename(self.infoDict['download'])
                xtermTitle(self.xterm_title)
                rc = self.unpack_step()

            elif step == "install":
                self.xterm_title += 'Installing: '+self.infoDict['atom']
                xtermTitle(self.xterm_title)
                rc = self.install_step()

            elif step == "remove":
                self.xterm_title += 'Removing: '+self.infoDict['removeatom']
                xtermTitle(self.xterm_title)
                rc = self.remove_step()

            elif step == "showmessages":
                rc = self.messages_step()

            elif step == "cleanup":
                self.xterm_title += 'Cleaning: '+self.infoDict['atom']
                xtermTitle(self.xterm_title)
                rc = self.cleanup_step()

            elif step == "postinstall":
                self.xterm_title += 'Postinstall: '+self.infoDict['atom']
                xtermTitle(self.xterm_title)
                rc = self.postinstall_step()

            elif step == "preinstall":
                self.xterm_title += 'Preinstall: '+self.infoDict['atom']
                xtermTitle(self.xterm_title)
                rc = self.preinstall_step()

            elif step == "preremove":
                self.xterm_title += 'Preremove: '+self.infoDict['removeatom']
                xtermTitle(self.xterm_title)
                rc = self.preremove_step()

            elif step == "postremove":
                self.xterm_title += 'Postremove: '+self.infoDict['removeatom']
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
        self.Entropy.gcTool.collect()
        return rc

    '''
       Install/Removal process preparation function
       - will generate all the metadata needed to run the action steps, creating infoDict automatically
       @input matched_atom(tuple): is what is returned by EquoInstance.atomMatch:
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
        return 0

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
            # do arch check
            compiled_arch = dbconn.retrieveDownloadURL(idpackage)
            if compiled_arch.find("/"+etpSys['arch']+"/") == -1:
                self.infoDict.clear()
                self.prepared = False
                return -1
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

        return 0


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
            # check size first
            repo_size = dbconn.retrieveSize(idpackage)
            f = open(os.path.join(etpConst['entropyworkdir'],self.infoDict['download']),"r")
            f.seek(0,2)
            disk_size = f.tell()
            f.close()
            if repo_size == disk_size:
                self.infoDict['steps'].reverse()
        return 0

class FileUpdatesInterface:

    def __init__(self, EquoInstance = None):

        if EquoInstance == None:
            self.Entropy = TextInterface()
            import dumpTools
            self.Entropy.dumpTools = dumpTools
        else:
            self.Entropy = EquoInstance
            try:
                self.Entropy.instanceTest()
            except:
                raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid Entropy Instance is needed")

    '''
    @description: scan for files that need to be merged
    @output: dictionary using filename as key
    '''
    def scanfs(self, dcache = True):

        if (dcache):
            # can we load cache?
            try:
                z = self.load_cache()
                if z != None:
                    return z
            except:
                pass

        # open client database to fill etpConst['dbconfigprotect']
        scandata = {}
        counter = 0
        for path in etpConst['dbconfigprotect']:
            # it's a file?
            scanfile = False
            if os.path.isfile(path):
                # find inside basename
                path = os.path.dirname(path)
                scanfile = True

            for currentdir,subdirs,files in os.walk(path):
                for item in files:

                    if (scanfile):
                        if path != item:
                            continue

                    filepath = currentdir+"/"+item
                    if item.startswith("._cfg"):

                        # further check then
                        number = item[5:9]
                        try:
                            int(number)
                        except:
                            continue # not a valid etc-update file
                        if item[9] != "_": # no valid format provided
                            continue

                        mydict = self.generate_dict(filepath)
                        if mydict['automerge']:
                            self.updateProgress(
                                                    darkred("Automerging file: %s") % ( darkgreen(etpConst['systemroot']+mydict['source']) ),
                                                    importance = 0,
                                                    type = "info"
                                                )
                            if os.path.isfile(etpConst['systemroot']+mydict['source']):
                                try:
                                    shutil.move(etpConst['systemroot']+mydict['source'],etpConst['systemroot']+mydict['destination'])
                                except IOError:
                                    self.updateProgress(
                                                    darkred("I/O Error :: Cannot automerge file: %s") % ( darkgreen(etpConst['systemroot']+mydict['source']) ),
                                                    importance = 1,
                                                    type = "warning"
                                                )
                            continue
                        else:
                            counter += 1
                            scandata[counter] = mydict.copy()

                        try:
                            self.updateProgress(
                                            "("+blue(str(counter))+") "+red(" file: ")+os.path.dirname(filepath)+"/"+os.path.basename(filepath)[10:],
                                            importance = 1,
                                            type = "info"
                                        )
                        except:
                            pass # possible encoding issues
        # store data
        try:
            self.Entropy.dumpTools.dumpobj(etpCache['configfiles'],scandata)
        except:
            pass
        return scandata

    def load_cache(self):
        try:
            sd = self.Entropy.dumpTools.loadobj(etpCache['configfiles'])
            # check for corruption?
            if isinstance(sd, dict):
                # quick test if data is reliable
                try:
                    taint = False
                    for x in sd:
                        if not os.path.isfile(etpConst['systemroot']+sd[x]['source']):
                            taint = True
                            break
                    if (not taint):
                        return sd
                    else:
                        raise exceptionTools.CacheCorruptionError("CacheCorruptionError: cache is corrupted.")
                except:
                    raise exceptionTools.CacheCorruptionError("CacheCorruptionError: cache is corrupted.")
            else:
                raise exceptionTools.CacheCorruptionError("CacheCorruptionError: cache is corrupted.")
        except:
            raise exceptionTools.CacheCorruptionError("CacheCorruptionError: cache is corrupted.")

    '''
    @description: prints information about config files that should be updated
    @attention: please be sure that filepath is properly formatted before using this function
    '''
    def add_to_cache(self, filepath):
        try:
            scandata = self.load_cache()
        except:
            scandata = self.scanfs(dcache = False)
        keys = scandata.keys()
        try:
            for key in keys:
                if scandata[key]['source'] == filepath[len(etpConst['systemroot']):]:
                    del scandata[key]
        except:
            pass
        # get next counter
        if keys:
            keys.sort()
            index = keys[-1]
        else:
            index = 0
        index += 1
        mydata = self.generate_dict(filepath)
        scandata[index] = mydata.copy()
        try:
            self.Entropy.dumpTools.dumpobj(etpCache['configfiles'],scandata)
        except:
            pass

    def remove_from_cache(self, sd, key):
        try:
            del sd[key]
        except:
            pass
        self.Entropy.dumpTools.dumpobj(etpCache['configfiles'],sd)
        return sd

    def generate_dict(self, filepath):

        item = os.path.basename(filepath)
        currentdir = os.path.dirname(filepath)
        tofile = item[10:]
        number = item[5:9]
        try:
            int(number)
        except:
            raise exceptionTools.InvalidDataType("InvalidDataType: invalid config file number '0000->9999'.")
        tofilepath = currentdir+"/"+tofile
        mydict = {}
        mydict['revision'] = number
        mydict['destination'] = tofilepath[len(etpConst['systemroot']):]
        mydict['source'] = filepath[len(etpConst['systemroot']):]
        mydict['automerge'] = False
        if not os.path.isfile(tofilepath):
            mydict['automerge'] = True
        if (not mydict['automerge']):
            # is it trivial?
            try:
                if not os.path.lexists(filepath): # if file does not even exist
                    return mydict
                if os.path.islink(filepath):
                    # if it's broken, skip diff and automerge
                    if not os.path.exists(filepath):
                        return mydict
                result = commands.getoutput('diff -Nua '+filepath+' '+tofilepath+' | grep "^[+-][^+-]" | grep -v \'# .Header:.*\'')
                if not result:
                    mydict['automerge'] = True
            except:
                pass
            # another test
            if (not mydict['automerge']):
                try:
                    if not os.path.lexists(filepath): # if file does not even exist
                        return mydict
                    if os.path.islink(filepath):
                        # if it's broken, skip diff and automerge
                        if not os.path.exists(filepath):
                            return mydict
                    result = os.system('diff -Bbua '+filepath+' '+tofilepath+' | egrep \'^[+-]\' | egrep -v \'^[+-][\t ]*#|^--- |^\+\+\+ \' | egrep -qv \'^[-+][\t ]*$\'')
                    if result == 1:
                        mydict['automerge'] = True
                except:
                    pass
        return mydict

#
# repository control class, that's it
#
class RepoInterface:

    def __init__(self, EquoInstance, reponames = [], forceUpdate = False):

        self.Entropy = EquoInstance
        try:
            self.Entropy.instanceTest()
        except:
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid Entropy Instance is needed")

        self.reponames = reponames
        self.forceUpdate = forceUpdate
        self.syncErrors = False
        self.dbupdated = False

        # check if I am root
        if (not self.Entropy.entropyTools.isRoot()):
            raise exceptionTools.PermissionDenied("PermissionDenied: not allowed as user.")

        # check etpRepositories
        if not etpRepositories:
            raise exceptionTools.MissingParameter("MissingParameter: no repositories specified in %s" % (etpConst['repositoriesconf'],))

        # Test network connectivity
        conntest = self.Entropy.entropyTools.get_remote_data("http://svn.sabayonlinux.org")
        if not conntest:
            raise exceptionTools.OnlineMirrorError("OnlineMirrorError: you are not connected to the Internet. You should.")

        if not self.reponames:
            for x in etpRepositories:
                self.reponames.append(x)

    def __validate_repository_id(self, repoid):
        if repoid not in self.reponames:
            raise exceptionTools.InvalidData("InvalidData: repository is not listed in self.reponames")

    def __validate_compression_method(self, repo):

        self.__validate_repository_id(repo)

        cmethod = etpConst['etpdatabasecompressclasses'].get(etpRepositories[repo]['dbcformat'])
        if cmethod == None:
            raise exceptionTools.InvalidDataType("InvalidDataType: wrong database compression method passed.")
        return cmethod

    def __ensure_repository_path(self, repo):

        self.__validate_repository_id(repo)

	# create dir if it doesn't exist
	if not os.path.isdir(etpRepositories[repo]['dbpath']):
	    os.makedirs(etpRepositories[repo]['dbpath'])

    def __construct_paths(self, item, repo, cmethod):

        if item not in ("db","rev","ck", "lock"):
            raise exceptionTools.InvalidData("InvalidData: supported db, rev, ck, lock")

        if item == "db":
            if cmethod == None:
                raise exceptionTools.InvalidData("InvalidData: for db, cmethod can't be None")
            url = etpRepositories[repo]['database'] +   "/" + etpConst[cmethod[2]]
            filepath = etpRepositories[repo]['dbpath'] + "/" + etpConst[cmethod[2]]
        elif item == "rev":
            url = etpRepositories[repo]['database'] + "/" + etpConst['etpdatabaserevisionfile']
            filepath = etpRepositories[repo]['dbpath'] + "/" + etpConst['etpdatabaserevisionfile']
        elif item == "ck":
            url = etpRepositories[repo]['database'] + "/" + etpConst['etpdatabasehashfile']
            filepath = etpRepositories[repo]['dbpath'] + "/" + etpConst['etpdatabasehashfile']
        elif item == "lock":
            url = etpRepositories[repo]['database']+"/"+etpConst['etpdatabasedownloadlockfile']
            filepath = "/dev/null"

        return url, filepath

    def __remove_repository_files(self, repo, dbfilenameid):

        self.__validate_repository_id(repo)

        if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile']):
            os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'])
        if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst[dbfilenameid]):
            os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst[dbfilenameid])
        if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile']):
            os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'])

    def __unpack_downloaded_database(self, repo, cmethod):

        self.__validate_repository_id(repo)

        path = eval("self.Entropy.entropyTools."+cmethod[1])(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[2]])
        return path

    def __verify_database_checksum(self, repo):

        self.__validate_repository_id(repo)

        try:
            f = open(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
            md5hash = f.readline().strip()
            md5hash = md5hash.split()[0]
            f.close()
        except:
            return -1
        rc = self.Entropy.entropyTools.compareMd5(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefile'],md5hash)
        return rc

    # @returns -1 if the file is not available
    # @returns int>0 if the revision has been retrieved
    def get_online_repository_revision(self, repo):

        self.__validate_repository_id(repo)

        url = etpRepositories[repo]['database']+"/"+etpConst['etpdatabaserevisionfile']
        status = self.Entropy.entropyTools.get_remote_data(url)
        if (status):
            status = status[0].strip()
            return int(status)
        else:
            return -1

    def is_repository_updatable(self, repo):

        self.__validate_repository_id(repo)

        onlinestatus = self.get_online_repository_revision(repo)
        if (onlinestatus != -1):
            localstatus = self.Entropy.get_repository_revision(repo)
            if (localstatus == onlinestatus) and (not self.forceUpdate):
                return False
        return True

    def is_repository_unlocked(self, repo):

        self.__validate_repository_id(repo)

        rc = self.download_item("lock", repo)
        if rc: # cannot download database
            self.syncErrors = True
            return False
        return True

    def clear_repository_cache(self, repo):
        self.__validate_repository_id(repo)
        self.Entropy.dumpTools.dumpobj(etpCache['dbInfo']+repo,{})

    # this function can be reimplemented
    def download_item(self, item, repo, cmethod = None):

        self.__validate_repository_id(repo)
        url, filepath = self.__construct_paths(item, repo, cmethod)

        fetchConn = self.Entropy.urlFetcher(url, filepath)
        fetchConn.progress = self.Entropy.progress
	rc = fetchConn.download()
        del fetchConn
        if rc in ("-1","-2","-3"):
            return False
        return True

    def close_transactions(self):

        if not self.dbupdated:
            return

        # safely clean ram caches
        atomMatchCache.clear()
        self.Entropy.dumpTools.dumpobj(etpCache['atomMatch'],{})
        generateDependsTreeCache.clear()
        self.Entropy.dumpTools.dumpobj(etpCache['generateDependsTree'],{})
        for dbinfo in dbCacheStore:
            dbCacheStore[dbinfo].clear()
            self.Entropy.dumpTools.dumpobj(dbinfo,{})

        # clean resume caches
        self.Entropy.dumpTools.dumpobj(etpCache['install'],{})
        self.Entropy.dumpTools.dumpobj(etpCache['world'],{})
        self.Entropy.dumpTools.dumpobj(etpCache['remove'],[])

    def sync(self):

        # let's dance!
        print_info(darkred(" @@ ")+darkgreen("Repositories syncronization..."))

        repocount = 0
        repolength = len(self.reponames)
        for repo in self.reponames:

            repocount += 1

            self.Entropy.updateProgress(    bold("%s") % ( etpRepositories[repo]['description'] ),
                                            importance = 2,
                                            type = "info",
                                            count = (repocount, repolength),
                                            header = blue("  # ")
                               )
            self.Entropy.updateProgress(    red("Database URL:") + darkgreen(etpRepositories[repo]['database']),
                                            importance = 1,
                                            type = "info",
                                            header = blue("  # ")
                               )
            self.Entropy.updateProgress(    red("Database local path: ") + darkgreen(etpRepositories[repo]['dbpath']),
                                            importance = 0,
                                            type = "info",
                                            header = "\t"
                               )

            # check if database is already updated to the latest revision
            update = self.is_repository_updatable(repo)
            if not update:
                self.Entropy.updateProgress(    bold("Attention: ") + red("database is already up to date."),
                                                importance = 1,
                                                type = "info",
                                                header = "\t"
                                )
                self.cycleDone()
                continue

            # get database lock
            unlocked = self.is_repository_unlocked(repo)
            if not unlocked:
                self.Entropy.updateProgress(    bold("Attention: ") + red("repository is being updated. Try again in a few minutes."),
                                                importance = 1,
                                                type = "warning",
                                                header = "\t"
                                )
                self.cycleDone()
                continue

            # database is going to be updated
            self.dbupdated = True
            # clear database interface cache belonging to this repository
            self.clear_repository_cache(repo)
            cmethod = self.__validate_compression_method(repo)
            self.__ensure_repository_path(repo)

            # starting to download
            self.Entropy.updateProgress(    red("Downloading database ") + darkgreen(etpConst[cmethod[2]])+red(" ..."),
                                            importance = 1,
                                            type = "info",
                                            header = "\t"
                            )

            down_status = self.download_item("db", repo, cmethod)
            if not down_status:
                self.Entropy.updateProgress(    bold("Attention: ") + red("database does not exist online."),
                                                importance = 1,
                                                type = "warning",
                                                header = "\t"
                                )
                self.cycleDone()
                continue

            # unpack database
            self.Entropy.updateProgress(    red("Unpacking database to ") + darkgreen(etpConst['etpdatabasefile'])+red(" ..."),
                                            importance = 0,
                                            type = "info",
                                            header = "\t"
                            )
            # unpack database
            self.__unpack_downloaded_database(repo, cmethod)

            # download checksum
            self.Entropy.updateProgress(    red("Downloading checksum ") + darkgreen(etpConst['etpdatabasehashfile'])+red(" ..."),
                                            importance = 0,
                                            type = "info",
                                            header = "\t"
                            )
            down_status = self.download_item("ck", repo)
            if not down_status:
                self.Entropy.updateProgress(    red("Cannot fetch checksum. Cannot verify database integrity !"),
                                                importance = 1,
                                                type = "warning",
                                                header = "\t"
                                )
            else:
                # verify checksum
                self.Entropy.updateProgress(    red("Checking downloaded database ") + darkgreen(etpConst['etpdatabasefile'])+red(" ..."),
                                                importance = 0,
                                                back = True,
                                                type = "info",
                                                header = "\t"
                                )
                db_status = self.__verify_database_checksum(repo)
                if db_status == -1:
                    self.Entropy.updateProgress(    red("Cannot open digest. Cannot verify database integrity !"),
                                                    importance = 1,
                                                    type = "warning",
                                                    header = "\t"
                                    )
                elif db_status:
                    self.Entropy.updateProgress(    red("Downloaded database status: ")+bold("OK"),
                                                    importance = 1,
                                                    type = "info",
                                                    header = "\t"
                                    )
                else:
                    self.Entropy.updateProgress(    red("Downloaded database status: ")+darkred("ERROR"),
                                                    importance = 1,
                                                    type = "error",
                                                    header = "\t"
                                    )
                    self.Entropy.updateProgress(    red("An error occured while checking database integrity. Giving up."),
                                                    importance = 1,
                                                    type = "error",
                                                    header = "\t"
                                    )
                    # delete all
                    self.__remove_repository_files(repo, cmethod[2])
                    self.syncErrors = True
                    self.cycleDone()
                    continue

            # download revision
            self.Entropy.updateProgress(    red("Downloading revision ")+darkgreen(etpConst['etpdatabaserevisionfile'])+red(" ..."),
                                            importance = 0,
                                            type = "info",
                                            header = "\t"
                            )
            rev_status = self.download_item("rev", repo)
            if not rev_status:
                self.Entropy.updateProgress(    red("Cannot download repository revision, don't ask me why !"),
                                                importance = 1,
                                                type = "warning",
                                                header = "\t"
                                )
            else:
                self.Entropy.updateProgress(    red("Updated repository revision: ")+bold(str(self.Entropy.get_repository_revision(repo))),
                                                importance = 1,
                                                type = "info",
                                                header = "\t"
                                )

            self.cycleDone()

        self.close_transactions()

        # clean caches
        if self.dbupdated:
            self.Entropy.generate_cache(depcache = True, configcache = False)

        if self.syncErrors:
            self.Entropy.updateProgress(    red("Something bad happened. Please have a look."),
                                            importance = 1,
                                            type = "warning",
                                            header = darkred(" @@ ")
                            )
            return 128

        rc = False
        try:
            rc = self.Entropy.check_equo_updates()
        except:
            pass

        if rc:
            self.Entropy.updateProgress(    blue("A new ")+bold("Equo")+blue(" release is available. Please ")+bold("install it")+blue(" before any other package."),
                                            importance = 1,
                                            type = "info",
                                            header = darkred(" !! ")
                            )

        return 0

'''
   Entropy FTP interface
'''
class FtpInterface:

    # this must be run before calling the other functions
    def __init__(self, ftpuri, EntropyInterface):

        self.Entropy = EntropyInterface
        try:
            self.Entropy.outputInstanceTest()
        except:
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid TextInterface based Instance is needed")

        import entropyTools
        self.entropyTools = entropyTools
        import ftplib
        self.ftplib = ftplib

        # import FTP modules
        socket.setdefaulttimeout(60)

        self.ftpuri = ftpuri
        self.ftphost = self.entropyTools.extractFTPHostFromUri(self.ftpuri)

        self.ftpuser = ftpuri.split("ftp://")[len(ftpuri.split("ftp://"))-1].split(":")[0]
        if (self.ftpuser == ""):
            self.ftpuser = "anonymous@"
            self.ftppassword = "anonymous"
        else:
            self.ftppassword = ftpuri.split("@")[:len(ftpuri.split("@"))-1]
            if len(self.ftppassword) > 1:
                self.ftppassword = '@'.join(self.ftppassword)
                self.ftppassword = self.ftppassword.split(":")[len(self.ftppassword.split(":"))-1]
                if (self.ftppassword == ""):
                    self.ftppassword = "anonymous"
            else:
                self.ftppassword = self.ftppassword[0]
                self.ftppassword = self.ftppassword.split(":")[len(self.ftppassword.split(":"))-1]
                if (self.ftppassword == ""):
                    self.ftppassword = "anonymous"

        self.ftpport = ftpuri.split(":")[len(ftpuri.split(":"))-1]
        try:
            self.ftpport = int(self.ftpport)
        except:
            self.ftpport = 21

        self.ftpdir = ftpuri.split("ftp://")[len(ftpuri.split("ftp://"))-1]
        self.ftpdir = self.ftpdir.split("/")[len(self.ftpdir.split("/"))-1]
        self.ftpdir = self.ftpdir.split(":")[0]
        if self.ftpdir.endswith("/"):
            self.ftpdir = self.ftpdir[:len(self.ftpdir)-1]
        if self.ftpdir == "":
            self.ftpdir = "/"

        count = 10
        while 1:
            count -= 1
            try:
                self.ftpconn = self.ftplib.FTP(self.ftphost)
                break
            except:
                if not count:
                    raise
                continue

        self.ftpconn.login(self.ftpuser,self.ftppassword)
        # change to our dir
        self.ftpconn.cwd(self.ftpdir)
        self.currentdir = self.ftpdir

    # this can be used in case of exceptions
    def reconnectHost(self):
        # import FTP modules
        socket.setdefaulttimeout(60)
        counter = 10
        while 1:
            counter -= 1
            try:
                self.ftpconn = self.ftplib.FTP(self.ftphost)
                break
            except:
                if not counter:
                    raise
                continue
        self.ftpconn.login(self.ftpuser,self.ftppassword)
        # save curr dir
        #cur = self.currentdir
        #self.setCWD(self.ftpdir)
        self.setCWD(self.currentdir)

    def getHost(self):
        return self.ftphost

    def getPort(self):
        return self.ftpport

    def getDir(self):
        return self.ftpdir

    def getCWD(self):
        pwd = self.ftpconn.pwd()
        return pwd

    def setCWD(self,dir):
        self.ftpconn.cwd(dir)
        self.currentdir = self.getCWD()

    def setPASV(self,bool):
        self.ftpconn.set_pasv(bool)

    def setChmod(self,chmodvalue,file):
        return self.ftpconn.voidcmd("SITE CHMOD "+str(chmodvalue)+" "+str(file))

    def getFileMtime(self,path):
        rc = self.ftpconn.sendcmd("mdtm "+path)
        return rc.split()[len(rc.split())-1]

    def spawnCommand(self,cmd):
        return self.ftpconn.sendcmd(cmd)

    # list files and directory of a FTP
    # @returns a list
    def listDir(self):
        # directory is: self.ftpdir
        try:
            rc = self.ftpconn.nlst()
            _rc = []
            for i in rc:
                _rc.append(i.split("/")[len(i.split("/"))-1])
            rc = _rc
        except:
            return []
        return rc

    # list if the file is available
    # @returns True or False
    def isFileAvailable(self,filename):
        # directory is: self.ftpdir
        try:
            rc = self.ftpconn.nlst()
            _rc = []
            for i in rc:
                _rc.append(i.split("/")[len(i.split("/"))-1])
            rc = _rc
            for i in rc:
                if i == filename:
                    return True
            return False
        except:
            return False

    def deleteFile(self,file):
        try:
            rc = self.ftpconn.delete(file)
            if rc.startswith("250"):
                return True
            else:
                return False
        except:
            return False

    def mkdir(self,directory):
        # FIXME: add rc
        self.ftpconn.mkd(directory)

    # this function also supports callback, because storbinary doesn't
    def advancedStorBinary(self, cmd, fp, callback=None):
        ''' Store a file in binary mode. Our version supports a callback function'''
        self.ftpconn.voidcmd('TYPE I')
        conn = self.ftpconn.transfercmd(cmd)
        while 1:
            buf = fp.readline()
            if not buf: break
            conn.sendall(buf)
            if callback: callback(buf)
        conn.close()

        # that's another workaround
        #return "226"
        try:
            rc = self.ftpconn.voidresp()
        except:
            self.reconnectHost()
            return "226"
        return rc

    def uploadFile(self,file,ascii = False):

        def uploadFileAndUpdateProgress(buf):
            # get the buffer size
            self.mykByteCount += float(len(buf))/1024
            # create percentage
            myUploadPercentage = round((round(self.mykByteCount,1)/self.myFileSize)*100,1)
            myUploadSize = round(self.mykByteCount,1)
            if (myUploadPercentage < 100.1) and (myUploadSize <= self.myFileSize):
                myUploadPercentage = str(myUploadPercentage)+"%"

                # create text
                currentText = brown("    <-> Upload status: ")+green(str(myUploadSize))+"/"+red(str(self.myFileSize))+" kB "+yellow("[")+str(myUploadPercentage)+yellow("]")
                self.Entropy.updateProgress(currentText, importance = 0, type = "info", back = True)
                # print !
                print_info(currentText,back = True)

        for i in range(10): # ten tries
            filename = file.split("/")[len(file.split("/"))-1]
            try:
                f = open(file,"r")
                # get file size
                self.myFileSize = round(float(os.stat(file)[6])/1024,1)
                self.mykByteCount = 0

                if self.isFileAvailable(filename+".tmp"):
                    self.deleteFile(filename+".tmp")

                if (ascii):
                    rc = self.ftpconn.storlines("STOR "+filename+".tmp",f)
                else:
                    rc = self.advancedStorBinary("STOR "+filename+".tmp", f, callback = uploadFileAndUpdateProgress )

                # now we can rename the file with its original name
                self.renameFile(filename+".tmp",filename)
                f.close()

                if rc.find("226") != -1: # upload complete
                    return True
                else:
                    return False

            except Exception, e: # connection reset by peer
                import traceback
                traceback.print_exc()
                self.Entropy.updateProgress("", importance = 0, type = "info")
                self.Entropy.updateProgress(red("Upload issue: %s, retrying... #%s") % (str(e),str(i+1)),
                                    importance = 1,
                                    type = "warning",
                                    header = "  "
                                   )
                self.reconnectHost() # reconnect
                if self.isFileAvailable(filename):
                    self.deleteFile(filename)
                if self.isFileAvailable(filename+".tmp"):
                    self.deleteFile(filename+".tmp")
                pass

    def downloadFile(self,filepath,downloaddir,ascii = False):

        def downloadFileStoreAndUpdateProgress(buf):
            # writing file buffer
            f.write(buf)
            # update progress
            self.mykByteCount += float(len(buf))/1024
            # create text
            cnt = round(self.mykByteCount,1)
            currentText = brown("    <-> Download status: ")+green(str(cnt))+"/"+red(str(self.myFileSize))+" kB"
            # print !
            self.Entropy.updateProgress(currentText, importance = 0, type = "info", back = True, count = (cnt, self.myFileSize), percent = True )

        item = filepath.split("/")[len(filepath.split("/"))-1]
        # look if the file exist
        if self.isFileAvailable(item):
            self.mykByteCount = 0
            # get the file size
            self.myFileSize = self.getFileSizeCompat(item)
            if (self.myFileSize):
                self.myFileSize = round(float(int(self.myFileSize))/1024,1)
                if (self.myFileSize == 0):
                    self.myFileSize = 1
            else:
                self.myFileSize = 0
            if (not ascii):
                f = open(downloaddir+"/"+item,"wb")
                rc = self.ftpconn.retrbinary('RETR '+item, downloadFileStoreAndUpdateProgress, 1024)
            else:
                f = open(downloaddir+"/"+item,"w")
                rc = self.ftpconn.retrlines('RETR '+item, f.write)
            f.flush()
            f.close()
            if rc.find("226") != -1: # upload complete
                return True
            else:
                return False
        else:
            return None

    # also used to move files
    def renameFile(self,fromfile,tofile):
        rc = self.ftpconn.rename(fromfile,tofile)
        return rc

    # not supported by dreamhost.com
    def getFileSize(self,file):
        return self.ftpconn.size(file)

    def getFileSizeCompat(self,file):
        data = self.getRoughList()
        for item in data:
            if item.find(file) != -1:
                # extact the size
                return item.split()[4]
        return ""

    def bufferizer(self,buf):
        self.FTPbuffer.append(buf)

    def getRoughList(self):
        self.FTPbuffer = []
        self.ftpconn.dir(self.bufferizer)
        return self.FTPbuffer

    def closeConnection(self):
        self.ftpconn.quit()


'''
   Entropy FTP/HTTP download interface
'''
class urlFetcher:

    def __init__(self, url, pathToSave, checksum = True, showSpeed = True, resume = True):

        self.url = url
        self.resume = resume
        self.url = self.encodeUrl(self.url)
        self.pathToSave = pathToSave
        self.checksum = checksum
        self.resumed = False
        self.showSpeed = showSpeed
        self.bufferSize = 8192
        self.status = None
        self.remotefile = None
        self.downloadedsize = 0
        self.average = 0
        self.remotesize = 0
        # transfer status data
        self.startingposition = 0
        self.datatransfer = 0
        self.time_remaining = "(infinite)"
        self.elapsed = 0.0
        self.transferpollingtime = float(1)/4
        import entropyTools
        self.entropyTools = entropyTools

        # resume support
        if os.path.isfile(self.pathToSave) and os.access(self.pathToSave,os.R_OK) and self.resume:
            self.localfile = open(self.pathToSave,"awb")
            self.localfile.seek(0,2)
            self.startingposition = int(self.localfile.tell())
            self.resumed = True
        else:
            self.localfile = open(self.pathToSave,"wb")

        # setup proxy, doing here because config is dynamic
        if etpConst['proxy']:
            proxy_support = urllib2.ProxyHandler(etpConst['proxy'])
            opener = urllib2.build_opener(proxy_support)
            urllib2.install_opener(opener)
        #FIXME else: unset opener??

    def encodeUrl(self, url):
        url = url.replace("#","%23")
        return url

    def download(self):
        if self.showSpeed:
            self.speedUpdater = self.entropyTools.TimeScheduled(
                        self.updateSpeedInfo,
                        self.transferpollingtime
            )
            self.speedUpdater.setName("download::"+self.url+str(random.random())) # set unique ID to thread, hopefully
            self.speedUpdater.start()

        # set timeout
        socket.setdefaulttimeout(60)

        # get file size if available
        try:
            self.remotefile = urllib2.urlopen(self.url)
            self.remotesize = int(self.remotefile.headers.get("content-length"))
            self.remotefile.close()
        except:
            pass

        # handle user stupidity
        try:
            request = self.url
            if ((self.startingposition > 0) and (self.remotesize > 0)) and (self.startingposition < self.remotesize):
                try:
                    request = urllib2.Request(self.url, headers = { "Range" : "bytes=" + str(self.startingposition) + "-" + str(self.remotesize) })
                except:
                    pass
            elif (self.startingposition == self.remotesize):
                return self.prepare_return()
            else:
                self.localfile = open(self.pathToSave,"wb")
            self.remotefile = urllib2.urlopen(request)
        except KeyboardInterrupt:
            self.close()
            raise
        except:
            self.close()
            self.status = "-3"
            return self.status

        if self.remotesize > 0:
            self.remotesize = float(int(self.remotesize))/1024

        rsx = "x"
        while rsx != '':
            rsx = self.remotefile.read(self.bufferSize)
            self.commitData(rsx)
            if self.showSpeed:
                self.updateProgress()
        self.localfile.flush()
        self.localfile.close()

        # kill thread
        self.close()

        return self.prepare_return()


    def prepare_return(self):
        if self.checksum:
            self.status = self.entropyTools.md5sum(self.pathToSave)
            return self.status
        else:
            self.status = "-2"
            return self.status

    def commitData(self, mybuffer):
        # writing file buffer
        self.localfile.write(mybuffer)
        # update progress info
        self.downloadedsize = self.localfile.tell()
        kbytecount = float(self.downloadedsize)/1024
        self.average = int((kbytecount/self.remotesize)*100)

    # reimplemented from TextInterface
    def updateProgress(self):

        currentText = darkred("    <-> Downloading: ")+darkgreen(str(round(float(self.downloadedsize)/1024,1)))+"/"+red(str(round(self.remotesize,1))) + " kB"
        # create progress bar
        barsize = 10
        bartext = "["
        curbarsize = 1
        #print average
        averagesize = (self.average*barsize)/100
        #print averagesize
        for y in range(averagesize):
            curbarsize += 1
            bartext += "="
        bartext += ">"
        diffbarsize = barsize-curbarsize
        for y in range(diffbarsize):
            bartext += " "
        if (self.showSpeed):
            bartext += "] => "+str(self.entropyTools.bytesIntoHuman(self.datatransfer))+"/sec ~ ETA: "+str(self.time_remaining)
        else:
            bartext += "]"
        average = str(self.average)
        if len(average) < 2:
            average = " "+average
        currentText += "    <->  "+average+"% "+bartext
        # print !
        print_info(currentText,back = True)

    def close(self):
        if self.showSpeed:
            self.speedUpdater.kill()
        socket.setdefaulttimeout(2)

    def updateSpeedInfo(self):
        self.elapsed += self.transferpollingtime
        # we have the diff size
        self.datatransfer = (self.downloadedsize-self.startingposition) / self.elapsed
        try:
            self.time_remaining = int(round((int(round(self.remotesize*1024,0))-int(round(self.downloadedsize,0)))/self.datatransfer,0))
            self.time_remaining = self.entropyTools.convertSecondsToFancyOutput(self.time_remaining)
        except:
            self.time_remaining = "(infinite)"


class rssFeed:

    def __init__(self, filename, maxentries = 100):

        self.feed_title = etpConst['systemname']+" Online Repository Status"
        self.feed_description = "Keep you updated on what's going on in the Official "+etpConst['systemname']+" Repository."
        self.feed_language = "en-EN"
        self.feed_editor = etpConst['rss-managing-editor']
        self.feed_copyright = etpConst['systemname']+" (C) 2007-2009"

        self.file = filename
        self.items = {}
        self.itemscounter = 0
        self.maxentries = maxentries
        import time
        self.time = time
        from xml.dom import minidom
        self.minidom = minidom

        # sanity check
        broken = False
        if os.path.isfile(self.file):
            try:
                self.xmldoc = self.minidom.parse(self.file)
            except:
                #print "DEBUG: RSS broken, recreating in 5 seconds."
                #time.sleep(5)
                broken = True

        if not os.path.isfile(self.file) or broken:
            self.title = self.feed_title
            self.description = self.feed_description
            self.language = self.feed_language
            self.cright = self.feed_copyright
            self.editor = self.feed_editor
            self.link = etpConst['rss-website-url']
            f = open(self.file,"w")
            f.write('')
            f.close()
        else:
            # parse file
            self.rssdoc = self.xmldoc.getElementsByTagName("rss")[0]
            self.channel = self.rssdoc.getElementsByTagName("channel")[0]
            self.title = self.channel.getElementsByTagName("title")[0].firstChild.data
            self.link = self.channel.getElementsByTagName("link")[0].firstChild.data
            self.description = self.channel.getElementsByTagName("description")[0].firstChild.data
            self.language = self.channel.getElementsByTagName("language")[0].firstChild.data
            self.cright = self.channel.getElementsByTagName("copyright")[0].firstChild.data
            self.editor = self.channel.getElementsByTagName("managingEditor")[0].firstChild.data
            entries = self.channel.getElementsByTagName("item")
            self.itemscounter = len(entries)
            if self.itemscounter > self.maxentries:
                self.itemscounter = self.maxentries
            mycounter = self.itemscounter
            for item in entries:
                if mycounter == 0: # max entries reached
                    break
                mycounter -= 1
                self.items[mycounter] = {}
                self.items[mycounter]['title'] = item.getElementsByTagName("title")[0].firstChild.data
                description = item.getElementsByTagName("description")[0].firstChild
                if description:
                    self.items[mycounter]['description'] = description.data
                else:
                    self.items[mycounter]['description'] = ""
                link = item.getElementsByTagName("link")[0].firstChild
                if link:
                    self.items[mycounter]['link'] = link.data
                else:
                    self.items[mycounter]['link'] = ""
                self.items[mycounter]['guid'] = item.getElementsByTagName("guid")[0].firstChild.data
                self.items[mycounter]['pubDate'] = item.getElementsByTagName("pubDate")[0].firstChild.data

    def addItem(self, title, link = '', description = ''):
        self.itemscounter += 1
        self.items[self.itemscounter] = {}
        self.items[self.itemscounter]['title'] = title
        self.items[self.itemscounter]['pubDate'] = self.time.strftime("%a, %d %b %Y %X +0000")
        self.items[self.itemscounter]['description'] = description
        self.items[self.itemscounter]['link'] = link
        if link:
            self.items[self.itemscounter]['guid'] = link
        else:
            self.items[self.itemscounter]['guid'] = "sabayonlinux.org~"+description+str(self.itemscounter)
        return self.itemscounter

    def removeEntry(self, id):
        del self.items[id]
        self.itemscounter -= 1
        return len(self.itemscounter)

    def getEntries(self):
        return self.items, self.itemscounter

    def writeChanges(self):

        # filter entries to fit in maxentries
        if self.itemscounter > self.maxentries:
            tobefiltered = self.itemscounter - self.maxentries
            for index in range(tobefiltered):
                try:
                    del self.items[index]
                except KeyError:
                    pass

        doc = self.minidom.Document()

        rss = doc.createElement("rss")
        rss.setAttribute("version","2.0")
        rss.setAttribute("xmlns:atom","http://www.w3.org/2005/Atom")

        channel = doc.createElement("channel")

        # title
        title = doc.createElement("title")
        title_text = doc.createTextNode(unicode(self.title))
        title.appendChild(title_text)
        channel.appendChild(title)
        # link
        link = doc.createElement("link")
        link_text = doc.createTextNode(unicode(self.link))
        link.appendChild(link_text)
        channel.appendChild(link)
        # description
        description = doc.createElement("description")
        desc_text = doc.createTextNode(unicode(self.description))
        description.appendChild(desc_text)
        channel.appendChild(description)
        # language
        language = doc.createElement("language")
        lang_text = doc.createTextNode(unicode(self.language))
        language.appendChild(lang_text)
        channel.appendChild(language)
        # copyright
        cright = doc.createElement("copyright")
        cr_text = doc.createTextNode(unicode(self.cright))
        cright.appendChild(cr_text)
        channel.appendChild(cright)
        # managingEditor
        managingEditor = doc.createElement("managingEditor")
        ed_text = doc.createTextNode(unicode(self.editor))
        managingEditor.appendChild(ed_text)
        channel.appendChild(managingEditor)

        keys = self.items.keys()
        keys.reverse()
        for key in keys:

            # sanity check, you never know
            try:
                self.items[key]['title']
                self.items[key]['link']
                self.items[key]['guid']
                self.items[key]['description']
                self.items[key]['pubDate']
            except KeyError:
                self.removeEntry(key)
                continue

            # item
            item = doc.createElement("item")
            # title
            item_title = doc.createElement("title")
            item_title_text = doc.createTextNode(unicode(self.items[key]['title']))
            item_title.appendChild(item_title_text)
            item.appendChild(item_title)
            # link
            item_link = doc.createElement("link")
            item_link_text = doc.createTextNode(unicode(self.items[key]['link']))
            item_link.appendChild(item_link_text)
            item.appendChild(item_link)
            # guid
            item_guid = doc.createElement("guid")
            item_guid.setAttribute("isPermaLink","true")
            item_guid_text = doc.createTextNode(unicode(self.items[key]['guid']))
            item_guid.appendChild(item_guid_text)
            item.appendChild(item_guid)
            # description
            item_desc = doc.createElement("description")
            item_desc_text = doc.createTextNode(unicode(self.items[key]['description']))
            item_desc.appendChild(item_desc_text)
            item.appendChild(item_desc)
            # pubdate
            item_date = doc.createElement("pubDate")
            item_date_text = doc.createTextNode(unicode(self.items[key]['pubDate']))
            item_date.appendChild(item_date_text)
            item.appendChild(item_date)

            # add item to channel
            channel.appendChild(item)

        # add channel to rss
        rss.appendChild(channel)
        doc.appendChild(rss)
        f = open(self.file,"w")
        f.writelines(doc.toprettyxml(indent="    "))
        f.flush()
        f.close()
