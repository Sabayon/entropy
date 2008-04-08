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
import time
from entropyConstants import *
from outputTools import TextInterface, print_info, print_warning, print_error, red, brown, blue, green, darkgreen, darkred, bold, darkblue
import exceptionTools

class matchContainer:
    def __init__(self):
        self.data = set()

    def inside(self, match):
        if match in self.data:
            return True
        return False

    def add(self, match):
        self.data.add(match)

    def clear(self):
        self.data.clear()

'''
    Main Entropy (client side) package management class
'''
class EquoInterface(TextInterface):

    def __init__(self, indexing = True, noclientdb = 0, xcache = True, user_xcache = False, repo_validation = True):

        self.MaskingParser = None
        self.FileUpdates = None
        self.repoDbCache = {}
        self.securityCache = {}
        self.spmCache = {}

        self.clientLog = LogFile(level = etpConst['equologlevel'],filename = etpConst['equologfile'], header = "[client]")
        import dumpTools
        self.dumpTools = dumpTools
        import databaseTools
        self.databaseTools = databaseTools
        import entropyTools
        self.entropyTools = entropyTools
        self.urlFetcher = urlFetcher # in this way, can be reimplemented (so you can override updateProgress)
        self.progress = None # supporting external updateProgress stuff, you can point self.progress to your progress bar
                             # and reimplement updateProgress
        self.clientDbconn = None
        self.FtpInterface = FtpInterface # for convenience
        self.indexing = indexing
        self.repo_validation = repo_validation
        self.noclientdb = False
        self.openclientdb = True
        if noclientdb in (False,0):
            self.noclientdb = False
        elif noclientdb in (True,1):
            self.noclientdb = True
        elif noclientdb == 2:
            self.noclientdb = True
            self.openclientdb = False
        self.xcache = xcache
        if self.openclientdb:
            self.openClientDatabase()
        self.FileUpdates = self.FileUpdatesInterfaceLoader()

        # masking parser
        self.MaskingParser = self.PackageMaskingParserInterfaceLoader()

        self.validRepositories = []
        if self.repo_validation:
            self.validate_repositories()

        # now if we are on live, we should disable it
        # are we running on a livecd? (/proc/cmdline has "cdroot")
        if self.entropyTools.islive():
            self.xcache = False

        if (not self.entropyTools.is_user_in_entropy_group()) and not user_xcache:
            self.xcache = False
        elif not user_xcache:
            self.validate_repositories_cache()

        if not self.xcache and (self.entropyTools.is_user_in_entropy_group()):
            try:
                self.purge_cache(False)
            except:
                pass

    def __del__(self):
        if self.clientDbconn != None:
            del self.clientDbconn
        del self.MaskingParser
        del self.FileUpdates
        self.closeAllRepositoryDatabases()
        self.closeAllSecurity()


    def validate_repositories(self):
        # valid repositories
        del self.validRepositories[:]
        for repoid in etpRepositoriesOrder:
            # open database
            try:
                self.openRepositoryDatabase(repoid)
                self.validRepositories.append(repoid)
            except exceptionTools.RepositoryError:
                self.updateProgress(
                                    darkred("Repository %s is not available. Cannot validate" % (repoid,)),
                                    importance = 1,
                                    type = "warning"
                                   )
                continue # repo not available
            except self.databaseTools.dbapi2.OperationalError:
                self.updateProgress(
                                    darkred("Repository %s is corrupted. Cannot validate" % (repoid,)),
                                    importance = 1,
                                    type = "warning"
                                   )
                continue

    def setup_default_file_perms(self, filepath):
        # setup file permissions
        os.chmod(filepath,0664)
        if etpConst['entropygid'] != None:
            os.chown(filepath,-1,etpConst['entropygid'])

    def _resources_run_create_lock(self):
        self.create_pid_file_lock(etpConst['locks']['using_resources'])

    def _resources_run_remove_lock(self):
        if os.path.isfile(etpConst['locks']['using_resources']):
            os.remove(etpConst['locks']['using_resources'])

    def _resources_run_check_lock(self):
        rc = self.check_pid_file_lock(etpConst['locks']['using_resources'])
        return rc

    def check_pid_file_lock(self, pidfile):
        if not os.path.isfile(pidfile):
            return False # not locked
        f = open(pidfile)
        s_pid = f.readline().strip()
        f.close()
        try:
            s_pid = int(s_pid)
        except ValueError:
            return False # not locked
        # is it our pid?
        mypid = os.getpid()
        if (s_pid != mypid) and os.path.isdir("%s/proc/%s" % (etpConst['systemroot'],s_pid,)):
            # is it running
            return True # locked
        return False

    def create_pid_file_lock(self, pidfile, mypid = None):
        lockdir = os.path.dirname(pidfile)
        if not os.path.isdir(lockdir):
            os.makedirs(lockdir,0775)
        const_setup_perms(lockdir,etpConst['entropygid'])
        if mypid == None:
            mypid = os.getpid()
        f = open(pidfile,"w")
        f.write(str(mypid))
        f.flush()
        f.close()

    def sync_loop_check(self, check_function):

        lock_count = 0
        max_lock_count = 30
        sleep_seconds = 10

        # check lock file
        while 1:
            locked = check_function()
            if not locked:
                if lock_count > 0:
                    self.updateProgress(    blue("Synchronization unlocked, let's go!"),
                                                    importance = 1,
                                                    type = "info",
                                                    header = darkred(" @@ ")
                                        )
                break
            if lock_count >= max_lock_count:
                self.updateProgress(    blue("Synchronization still locked after %s minutes, giving up!") % (max_lock_count*sleep_seconds/60,),
                                                importance = 1,
                                                type = "warning",
                                                header = darkred(" @@ ")
                                    )
                return True # gave up
            lock_count += 1
            self.updateProgress(    blue("Synchronization locked, sleeping %s seconds, check #%s/%s") % (sleep_seconds,lock_count,max_lock_count,),
                                            importance = 1,
                                            type = "warning",
                                            header = darkred(" @@ "),
                                            back = True
                                )
            time.sleep(sleep_seconds)
        return False # yay!

    def validate_repositories_cache(self):
        # is the list of repos changed?
        cached = self.dumpTools.loadobj(etpCache['repolist'])
        if cached == None:
            # invalidate matching cache
            try:
                self.repository_move_clear_cache()
            except IOError:
                pass
        elif type(cached) is tuple:
            # compare
            myrepolist = tuple(etpRepositoriesOrder)
            if cached != myrepolist:
                cached = set(cached)
                myrepolist = set(myrepolist)
                difflist = cached - myrepolist # before minus now
                for repoid in difflist:
                    try:
                        self.repository_move_clear_cache(repoid)
                    except IOError:
                        pass
        try:
            self.dumpTools.dumpobj(etpCache['repolist'],tuple(etpRepositoriesOrder))
        except IOError:
            pass

    def backup_setting(self, setting_name):
        if etpConst.has_key(setting_name):
            myinst = etpConst[setting_name]
            if type(etpConst[setting_name]) in (list,tuple):
                myinst = etpConst[setting_name][:]
            elif type(etpConst[setting_name]) in (dict,set):
                myinst = etpConst[setting_name].copy()
            else:
                myinst = etpConst[setting_name]
            etpConst['backed_up'].update({setting_name: myinst})
        else:
            raise exceptionTools.InvalidData("InvalidData: nothing to backup in etpConst with %s key" % (setting_name,))

    def switchChroot(self, chroot = ""):
        # clean caches
        self.purge_cache()
        const_resetCache()
        self.closeAllRepositoryDatabases()
        if chroot.endswith("/"):
            chroot = chroot[:-1]
        etpSys['rootdir'] = chroot
        initConfig_entropyConstants(etpSys['rootdir'])
        initConfig_clientConstants()
        self.validate_repositories()
        self.reopenClientDbconn()
        if chroot:
            try:
                self.clientDbconn.resetTreeupdatesDigests()
            except:
                pass
        # I don't think it's safe to keep them open
        # isn't it?
        self.closeAllSecurity()

    def Security(self):
        chroot = etpConst['systemroot']
        cached = self.securityCache.get(chroot)
        if cached != None:
            return cached
        cached = SecurityInterface(self)
        self.securityCache[chroot] = cached
        return cached

    def closeAllSecurity(self):
        self.securityCache.clear()

    def reopenClientDbconn(self):
        self.clientDbconn.closeDB()
        self.openClientDatabase()

    def closeAllRepositoryDatabases(self):
        for item in self.repoDbCache:
            self.repoDbCache[item].closeDB()
        self.repoDbCache.clear()
        etpConst['packagemasking'] = None

    def openClientDatabase(self):
        if not os.path.isdir(os.path.dirname(etpConst['etpdatabaseclientfilepath'])):
            os.makedirs(os.path.dirname(etpConst['etpdatabaseclientfilepath']))
        if (not self.noclientdb) and (not os.path.isfile(etpConst['etpdatabaseclientfilepath'])):
            raise exceptionTools.SystemDatabaseError("SystemDatabaseError: system database not found or corrupted: %s" % (etpConst['etpdatabaseclientfilepath'],) )
        conn = self.databaseTools.etpDatabase(  readOnly = False,
                                                dbFile = etpConst['etpdatabaseclientfilepath'],
                                                clientDatabase = True,
                                                dbname = etpConst['clientdbid'],
                                                xcache = self.xcache,
                                                indexing = self.indexing,
                                                OutputInterface = self
                                                )
        # validate database
        if not self.noclientdb:
            conn.validateDatabase()
        if not etpConst['dbconfigprotect']:
            if not self.noclientdb:

                etpConst['dbconfigprotect'] = conn.listConfigProtectDirectories()
                etpConst['dbconfigprotectmask'] = conn.listConfigProtectDirectories(mask = True)
                etpConst['dbconfigprotect'] = [etpConst['systemroot']+x for x in etpConst['dbconfigprotect']]
                etpConst['dbconfigprotectmask'] = [etpConst['systemroot']+x for x in etpConst['dbconfigprotect']]

                etpConst['dbconfigprotect'] += [etpConst['systemroot']+x for x in etpConst['configprotect'] if etpConst['systemroot']+x not in etpConst['dbconfigprotect']]
                etpConst['dbconfigprotectmask'] += [etpConst['systemroot']+x for x in etpConst['configprotectmask'] if etpConst['systemroot']+x not in etpConst['dbconfigprotectmask']]
        self.clientDbconn = conn
        return self.clientDbconn

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
        if not self.repoDbCache.has_key((repoid,etpConst['systemroot'])) or (etpConst['packagemasking'] == None):
            if etpConst['packagemasking'] == None:
                self.closeAllRepositoryDatabases()
            dbconn = self.loadRepositoryDatabase(repoid, xcache = self.xcache, indexing = self.indexing)
            try:
                dbconn.checkDatabaseApi()
            except:
                pass
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

        # load the masking parser
        if etpConst['packagemasking'] == None:
            etpConst['packagemasking'] = self.MaskingParser.parse()
            # merge universal keywords
            for x in etpConst['packagemasking']['keywords']['universal']:
                etpConst['keywords'].add(x)

        if repositoryName.endswith(etpConst['packagesext']):
            xcache = False
        dbfile = etpRepositories[repositoryName]['dbpath']+"/"+etpConst['etpdatabasefile']
        if not os.path.isfile(dbfile):
            if repositoryName not in repo_error_messages_cache:
                self.updateProgress(darkred("Repository %s hasn't been downloaded yet !!!") % (repositoryName,), importance = 2, type = "warning")
                repo_error_messages_cache.add(repositoryName)
            raise exceptionTools.RepositoryError("RepositoryError: repository %s hasn't been downloaded yet." % (repositoryName,))
        conn = self.databaseTools.etpDatabase(readOnly = True, dbFile = dbfile, clientDatabase = True, dbname = etpConst['dbnamerepoprefix']+repositoryName, xcache = xcache, indexing = indexing, OutputInterface = self)
        # initialize CONFIG_PROTECT
        if (etpRepositories[repositoryName]['configprotect'] == None) or \
            (etpRepositories[repositoryName]['configprotectmask'] == None):

            etpRepositories[repositoryName]['configprotect'] = conn.listConfigProtectDirectories()
            etpRepositories[repositoryName]['configprotectmask'] = conn.listConfigProtectDirectories(mask = True)
            etpRepositories[repositoryName]['configprotect'] = [etpConst['systemroot']+x for x in etpRepositories[repositoryName]['configprotect']]
            etpRepositories[repositoryName]['configprotectmask'] = [etpConst['systemroot']+x for x in etpRepositories[repositoryName]['configprotectmask']]

            etpRepositories[repositoryName]['configprotect'] += [etpConst['systemroot']+x for x in etpConst['configprotect'] if etpConst['systemroot']+x not in etpRepositories[repositoryName]['configprotect']]
            etpRepositories[repositoryName]['configprotectmask'] += [etpConst['systemroot']+x for x in etpConst['configprotectmask'] if etpConst['systemroot']+x not in etpRepositories[repositoryName]['configprotectmask']]
        if not etpConst['treeupdatescalled'] and (self.entropyTools.is_user_in_entropy_group()) and (not repositoryName.endswith(etpConst['packagesext'])):
            conn.clientUpdatePackagesData(self.clientDbconn)
        return conn

    def openGenericDatabase(self, dbfile, dbname = None, xcache = None, readOnly = False, indexing_override = None):
        if xcache == None:
            xcache = self.xcache
        if indexing_override != None:
            indexing = indexing_override
        else:
            indexing = self.indexing
        if dbname == None:
            dbname = "generic"
        return self.databaseTools.etpDatabase(  readOnly = readOnly,
                                                dbFile = dbfile,
                                                clientDatabase = True,
                                                dbname = dbname,
                                                xcache = xcache,
                                                indexing = indexing,
                                                OutputInterface = self
                                             )

    def listAllAvailableBranches(self):
        branches = set()
        for repo in etpRepositories:
            dbconn = self.openRepositoryDatabase(repo)
            branches.update(dbconn.listAllBranches())
        return branches


    '''
       Cache stuff :: begin
    '''
    def purge_cache(self, showProgress = True, client_purge = True):
        const_resetCache()
        if self.entropyTools.is_user_in_entropy_group():
            skip = set()
            if not client_purge:
                skip.add("/"+etpCache['dbInfo']+"/"+etpConst['clientdbid']) # it's ok this way
                skip.add("/"+etpCache['dbMatch']+"/"+etpConst['clientdbid']) # it's ok this way
                skip.add("/"+etpCache['dbSearch']+"/"+etpConst['clientdbid']) # it's ok this way
            for key in etpCache:
                if showProgress: self.updateProgress(darkred("Cleaning %s => *.dmp...") % (etpCache[key],), importance = 1, type = "warning", back = True)
                self.clear_dump_cache(etpCache[key], skip = skip)

            if showProgress: self.updateProgress(darkgreen("Cache is now empty."), importance = 2, type = "info")

    def generate_cache(self, depcache = True, configcache = True, client_purge = True):
        # clean first of all
        self.purge_cache(client_purge = client_purge)
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

        self.updateProgress(darkgreen("Resolving metadata"), importance = 1, type = "warning")
        # we can barely ignore any exception from here
        # especially cases where client db does not exist
        try:
            update, remove, fine = self.calculate_world_updates()
            del fine, remove
            self.retrieveInstallQueue(update, False, False)
            self.calculate_available_packages()
        except:
            pass

        self.updateProgress(darkred("Dependencies cache filled."), importance = 2, type = "warning")

    def clear_dump_cache(self, dump_name, skip = []):
        dump_path = os.path.join(etpConst['dumpstoragedir'],dump_name)
        dump_dir = os.path.dirname(dump_path)
        #dump_file = os.path.basename(dump_path)
        for currentdir, subdirs, files in os.walk(dump_dir):
            path = os.path.join(dump_dir,currentdir)
            if skip:
                found = False
                for myskip in skip:
                    if path.find(myskip) != -1:
                        found = True
                        break
                if found: continue
            for item in files:
                if item.endswith(".dmp"):
                    item = os.path.join(path,item)
                    os.remove(item)
            if not os.listdir(path):
                os.rmdir(path)

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

    def find_belonging_dependency(self, matched_atoms):
        crying_atoms = set()
        for atom in matched_atoms:
            for repo in etpRepositories:
                rdbconn = self.openRepositoryDatabase(repo)
                riddep = rdbconn.searchDependency(atom)
                if riddep != -1:
                    ridpackages = rdbconn.searchIdpackageFromIddependency(riddep)
                    for i in ridpackages:
                        i,r = rdbconn.idpackageValidator(i)
                        if i == -1:
                            continue
                        iatom = rdbconn.retrieveAtom(i)
                        crying_atoms.add((iatom,repo))
        return crying_atoms

    def get_licenses_to_accept(self, install_queue):
        if not install_queue:
            return {}
        licenses = {}
        for match in install_queue:
            repoid = match[1]
            dbconn = self.openRepositoryDatabase(repoid)
            wl = etpConst['packagemasking']['repos_license_whitelist'].get(repoid)
            if not wl:
                continue
            keys = dbconn.retrieveLicensedataKeys(match[0])
            for key in keys:
                if key not in wl:
                    found = self.clientDbconn.isLicenseAccepted(key)
                    if found:
                        continue
                    if not licenses.has_key(key):
                        licenses[key] = set()
                    licenses[key].add(match)
        return licenses

    def get_text_license(self, license_name, repoid):
        dbconn = self.openRepositoryDatabase(repoid)
        text = dbconn.retrieveLicenseText(license_name)
        tempfile = self.entropyTools.getRandomTempFile()
        f = open(tempfile,"w")
        f.write(text)
        f.flush()
        f.close()
        return tempfile

    def get_file_viewer(self):
        viewer = None
        if os.access("/usr/bin/less",os.X_OK):
            viewer = "/usr/bin/less"
        elif os.access("/bin/more",os.X_OK):
            viewer = "/bin/more"
        if not viewer:
            viewer = self.get_file_editor()
        return viewer

    def get_file_editor(self):
        editor = None
        if os.getenv("EDITOR"):
            editor = "$EDITOR"
        elif os.access("/bin/nano",os.X_OK):
            editor = "/bin/nano"
        elif os.access("/bin/vi",os.X_OK):
            editor = "/bin/vi"
        elif os.access("/usr/bin/vi",os.X_OK):
            editor = "/usr/bin/vi"
        elif os.access("/usr/bin/emacs",os.X_OK):
            editor = "/usr/bin/emacs"
        elif os.access("/bin/emacs",os.X_OK):
            editor = "/bin/emacs"
        return editor

    def libraries_test(self, dbconn = None):

        if dbconn == None:
            dbconn = self.clientDbconn

        self.updateProgress(
                                blue("Libraries test"),
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
            return set(),set(),-1

        ldpaths = self.entropyTools.collectLinkerPaths()
        ldpaths |= self.entropyTools.collectPaths()
        # speed up when /usr/lib is a /usr/lib64 symlink
        if "/usr/lib64" in ldpaths and "/usr/lib" in ldpaths:
            if os.path.realpath("/usr/lib64") == "/usr/lib":
                ldpaths.remove("/usr/lib")

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
                    filepath = os.path.join(currentdir,item)
                    if filepath in etpConst['libtest_files_blacklist']:
                        continue
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
        plain_brokenexecs = set()
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
                    if etpSys['serverside']:
                        plain_brokenexecs.add(etpConst['systemroot']+executable)
                brokenlibs.update(mylibs)
                brokenexecs[executable] = mylibs.copy()
        del executables

        packagesMatched = set()

        if not etpSys['serverside']:

            self.updateProgress(
                                    blue("Trying to match packages"),
                                    importance = 1,
                                    type = "info",
                                    header = red(" @@ ")
                                )

            # match libraries
            for repoid in etpRepositoriesOrder:
                self.updateProgress(
                                        blue("Repository id: ")+darkgreen(repoid),
                                        importance = 1,
                                        type = "info",
                                        header = red(" @@ ")
                                    )
                if etpSys['serverside']:
                    rdbconn = dbconn
                else:
                    rdbconn = self.openRepositoryDatabase(repoid)
                libsfound = set()
                for lib in brokenlibs:
                    packages = rdbconn.searchBelongs(file = "%"+lib, like = True, branch = etpConst['branch'], branch_operator = "<=")
                    if packages:
                        for idpackage in packages:
                            key, slot = rdbconn.retrieveKeySlot(idpackage)
                            if key in etpConst['libtest_blacklist']:
                                continue
                            # retrieve content and really look if library is in ldpath
                            mycontent = rdbconn.retrieveContent(idpackage)
                            matching_libs = [x for x in mycontent if x.endswith(lib) and (os.path.dirname(x) in ldpaths)]
                            libsfound.add(lib)
                            if matching_libs:
                                packagesMatched.add((idpackage,repoid,lib))
                brokenlibs.difference_update(libsfound)

        if etpSys['serverside']:
            return packagesMatched,plain_brokenexecs,0
        return packagesMatched,brokenlibs,0

    def move_to_branch(self, branch, pretend = False):
        availbranches = self.listAllAvailableBranches()
        if branch not in availbranches:
            return 1
        if pretend:
            return 0
        if branch != etpConst['branch']:
            etpConst['branch'] = branch
            # update configuration
            self.entropyTools.writeNewBranch(branch)
            # reset treeupdatesactions
            self.clientDbconn.resetTreeupdatesDigests()
            # clean cache
            self.purge_cache(showProgress = False)
            # reopen Client Database, this will make treeupdates to be re-read
            self.reopenClientDbconn()
            self.closeAllRepositoryDatabases()
            self.validate_repositories()
            initConfig_entropyConstants(etpSys['rootdir'])
        return 0

    # tell if a new equo release is available, returns True or False
    def check_equo_updates(self):
        found, match = self.check_package_update("app-admin/equo", deep = True)
        return found

    '''
        @input: matched atom (idpackage,repoid)
        @output:
                upgrade: int(2)
                install: int(1)
                reinstall: int(0)
                downgrade: int(-1)
    '''
    def get_package_action(self, match):
        dbconn = self.openRepositoryDatabase(match[1])
        pkgkey, pkgslot = dbconn.retrieveKeySlot(match[0])
        results = self.clientDbconn.searchKeySlot(pkgkey, pkgslot)
        if not results:
            return 1

        installed_idpackage = results[0][0]
        pkgver = dbconn.retrieveVersion(match[0])
        pkgtag = dbconn.retrieveVersionTag(match[0])
        pkgrev = dbconn.retrieveRevision(match[0])
        installedVer = self.clientDbconn.retrieveVersion(installed_idpackage)
        installedTag = self.clientDbconn.retrieveVersionTag(installed_idpackage)
        installedRev = self.clientDbconn.retrieveRevision(installed_idpackage)
        pkgcmp = self.entropyTools.entropyCompareVersions((pkgver,pkgtag,pkgrev),(installedVer,installedTag,installedRev))
        if pkgcmp == 0:
            return 0
        elif pkgcmp > 0:
            return 2
        else:
            return -1

    def get_meant_packages(self, search_term):
        import re
        #match_string = ''.join(["(%s)?" % (x,) for x in search_term])
        match_string = ''
        for x in search_term:
            if x.isalpha():
                x = "(%s{1,})?" % (x,)
                match_string += x
        #print match_string
        match_exp = re.compile(match_string,re.IGNORECASE)

        matched = {}
        for repo in etpRepositories:
            dbconn = self.openRepositoryDatabase(repo)
            # get names
            idpackages = dbconn.listAllIdpackages(branch = etpConst['branch'], branch_operator = "<=")
            for idpackage in idpackages:
                name = dbconn.retrieveName(idpackage)
                if len(name) < len(search_term):
                    continue
                mymatches = match_exp.findall(name)
                found_matches = []
                for mymatch in mymatches:
                    items = len([x for x in mymatch if x != ""])
                    if items < 1:
                        continue
                    calc = float(items)/len(mymatch)
                    if calc > 0.0:
                        found_matches.append(calc)
                if not found_matches:
                    continue
                #print "found_matches",name,found_matches
                maxpoint = max(found_matches)
                if not matched.has_key(maxpoint):
                    matched[maxpoint] = set()
                matched[maxpoint].add((idpackage,repo))
        if matched:
            mydata = []
            while len(mydata) < 5:
                try:
                    most = max(matched.keys())
                    #print "most",most
                except ValueError:
                    break
                popped = matched.pop(most)
                mydata.extend(list(popped))
            return mydata
        return set()

    # better to use key:slot
    def check_package_update(self, atom, deep = False):

        if self.xcache:
            c_hash = str(hash(atom))+str(hash(deep))
            c_hash = str(hash(c_hash))
            cached = self.dumpTools.loadobj(etpCache['check_package_update']+c_hash)
            if cached != None:
                return cached

        found = False
        match = self.clientDbconn.atomMatch(atom)
        matched = None
        if match[0] != -1:
            myatom = self.clientDbconn.retrieveAtom(match[0])
            mytag = self.entropyTools.dep_gettag(myatom)
            myatom = self.entropyTools.remove_tag(myatom)
            myrev = self.clientDbconn.retrieveRevision(match[0])
            pkg_match = "="+myatom+"~"+str(myrev)
            if mytag != None:
                pkg_match += "#%s" % (mytag,)
            pkg_unsatisfied,x = self.filterSatisfiedDependencies([pkg_match], deep_deps = deep)
            del x
            if pkg_unsatisfied:
                found = True
            del pkg_unsatisfied
            matched = self.atomMatch(pkg_match)
        del match

        if self.xcache:
            try:
                self.dumpTools.dumpobj(etpCache['check_package_update']+c_hash,(found,matched))
            except:
                pass

        return found, matched


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

    def update_repository_revision(self, reponame):
        r = self.get_repository_revision(reponame)
        etpRepositories[reponame]['dbrevision'] = "0"
        if r != -1:
            etpRepositories[reponame]['dbrevision'] = str(r)

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
        if fetch_repository_if_not_available_cache.has_key(reponame):
            return fetch_repository_if_not_available_cache.get(reponame)
        # open database
        rc = 0
        dbfile = etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasefile']
        if not os.path.isfile(dbfile):
            # sync
            repoConn = self.Repositories(reponames = [reponame], noEquoCheck = True)
            rc = repoConn.sync()
            del repoConn
            if os.path.isfile(dbfile):
                rc = 0
        fetch_repository_if_not_available_cache[reponame] = rc
        return rc

    def atomMatch(self, atom, caseSensitive = True, matchSlot = None, matchBranches = (), packagesFilter = True, multiMatch = False, multiRepo = False, matchRevision = None, matchRepo = None):

        # support match in repository from shell
        # atom@repo1,repo2,repo3
        atom, repos = self.entropyTools.dep_get_match_in_repos(atom)
        if (matchRepo == None) and (repos != None):
            matchRepo = repos

        if self.xcache:

            if matchRepo and (type(matchRepo) in (list,tuple,set)):
                u_hash = hash(tuple(matchRepo))
            else:
                u_hash = hash(matchRepo)
            c_hash =    str(hash(atom)) + \
                        str(hash(matchSlot)) + \
                        str(hash(tuple(matchBranches))) + \
                        str(hash(packagesFilter)) + \
                        str(hash(tuple(self.validRepositories))) + \
                        str(hash(tuple(etpRepositories.keys()))) + \
                        str(hash(multiMatch)) + \
                        str(hash(multiRepo)) + \
                        str(hash(caseSensitive)) + \
                        str(hash(matchRevision)) + \
                        str(u_hash)
            c_hash = str(hash(c_hash))
            cached = self.dumpTools.loadobj(etpCache['atomMatch']+c_hash)
            if cached != None:
                return cached

        valid_repos = self.validRepositories
        if matchRepo and (type(matchRepo) in (list,tuple,set)):
            valid_repos = list(matchRepo)

        repoResults = {}
        for repo in valid_repos:

            # check if repo exists
            if not repo.endswith(etpConst['packagesext']):
                fetch = self.fetch_repository_if_not_available(repo)
                if fetch != 0:
                    continue # cannot fetch repo, excluding

            # search
            dbconn = self.openRepositoryDatabase(repo)
            query = dbconn.atomMatch(atom, caseSensitive = caseSensitive, matchSlot = matchSlot, matchBranches = matchBranches, packagesFilter = packagesFilter, matchRevision = matchRevision)
            if query[1] == 0:
                # package found, add to our dictionary
                repoResults[repo] = query[0]

        dbpkginfo = (-1,1)

        packageInformation = {}
        # nothing found
        if not repoResults:
            dbpkginfo = (-1,1)

        elif multiRepo:
            data = set()
            for repoid in repoResults:
                data.add((repoResults[repoid],repoid))
            dbpkginfo = (data,0)

        elif len(repoResults) == 1:
            # one result found
            repo = repoResults.keys()[0]
            dbpkginfo = (repoResults[repo],repo)

        elif len(repoResults) > 1:
            # we have to decide which version should be taken

            # .tbz2 repos have always the precedence, so if we find them,
            # we should second what user wants, installing his tbz2
            tbz2repos = [x for x in repoResults if x.endswith(etpConst['packagesext'])]
            if tbz2repos:
                del tbz2repos
                newrepos = repoResults.copy()
                for x in newrepos:
                    if not x.endswith(etpConst['packagesext']):
                        del repoResults[x]

            version_duplicates = set()
            versions = []
            for repo in repoResults:
                dbconn = self.openRepositoryDatabase(repo)
                packageInformation[repo] = {}
                version = dbconn.retrieveVersion(repoResults[repo])
                packageInformation[repo]['version'] = version
                if version in versions:
                    version_duplicates.add(version)
                versions.append(version)
                packageInformation[repo]['versiontag'] = dbconn.retrieveVersionTag(repoResults[repo])
                packageInformation[repo]['revision'] = dbconn.retrieveRevision(repoResults[repo])

            newerVersion = self.entropyTools.getNewerVersion(versions)[0]
            # if no duplicates are found, we're done
            if not version_duplicates:

                for reponame in packageInformation:
                    if packageInformation[reponame]['version'] == newerVersion:
                        break
                dbpkginfo = (repoResults[reponame],reponame)

            else:

                if newerVersion not in version_duplicates:

                    # we are fine, the newerVersion is not one of the duplicated ones
                    for reponame in packageInformation:
                        if packageInformation[reponame]['version'] == newerVersion:
                            break
                    dbpkginfo = (repoResults[reponame],reponame)

                else:

                    del version_duplicates
                    conflictingEntries = {}
                    tags_duplicates = set()
                    tags = []
                    for repo in packageInformation:
                        if packageInformation[repo]['version'] == newerVersion:
                            conflictingEntries[repo] = {}
                            versiontag = packageInformation[repo]['versiontag']
                            if versiontag in tags:
                                tags_duplicates.add(versiontag)
                            tags.append(versiontag)
                            conflictingEntries[repo]['versiontag'] = versiontag
                            conflictingEntries[repo]['revision'] = packageInformation[repo]['revision']

                    del packageInformation
                    newerTag = tags[:]
                    newerTag.reverse()
                    newerTag = newerTag[0]
                    if not newerTag in tags_duplicates:

                        # we're finally done
                        for reponame in conflictingEntries:
                            if conflictingEntries[reponame]['versiontag'] == newerTag:
                                break
                        dbpkginfo = (repoResults[reponame],reponame)

                    else:

                        # yes, it is. we need to compare revisions
                        conflictingRevisions = {}
                        revisions = []
                        revisions_duplicates = set()
                        for repo in conflictingEntries:
                            if conflictingEntries[repo]['versiontag'] == newerTag:
                                conflictingRevisions[repo] = {}
                                versionrev = conflictingEntries[repo]['revision']
                                if versionrev in revisions:
                                    revisions_duplicates.add(versionrev)
                                revisions.append(versionrev)
                                conflictingRevisions[repo]['revision'] = versionrev

                        del conflictingEntries
                        newerRevision = max(revisions)
                        if not newerRevision in revisions_duplicates:

                            for reponame in conflictingRevisions:
                                if conflictingRevisions[reponame]['revision'] == newerRevision:
                                    break
                            dbpkginfo = (repoResults[reponame],reponame)

                        else:

                            # ok, we must get the repository with the biggest priority
                            for reponame in valid_repos:
                                if reponame in conflictingRevisions:
                                    break
                            dbpkginfo = (repoResults[reponame],reponame)

        # multimatch support
        if multiMatch:

            if dbpkginfo[1] != 1: # can be "0" or a string, but 1 means failure
                if multiRepo:
                    data = set()
                    for match in dbpkginfo[0]:
                        dbconn = self.openRepositoryDatabase(match[1])
                        matches = dbconn.atomMatch(atom, caseSensitive = caseSensitive, matchSlot = matchSlot, matchBranches = matchBranches, packagesFilter = packagesFilter, multiMatch = True)
                        for repoidpackage in matches[0]:
                            data.add((repoidpackage,match[1]))
                    dbpkginfo = (data,0)
                else:
                    dbconn = self.openRepositoryDatabase(dbpkginfo[1])
                    matches = dbconn.atomMatch(atom, caseSensitive = caseSensitive, matchSlot = matchSlot, matchBranches = matchBranches, packagesFilter = packagesFilter, multiMatch = True)
                    dbpkginfo = (set([(x,dbpkginfo[1]) for x in matches[0]]),0)

        if self.xcache:
            try:
                self.dumpTools.dumpobj(etpCache['atomMatch']+c_hash,dbpkginfo)
            except IOError:
                pass

        return dbpkginfo


    def repository_move_clear_cache(self, repoid = None):
        self.clear_dump_cache(etpCache['world_available'])
        self.clear_dump_cache(etpCache['world_update'])
        self.clear_dump_cache(etpCache['check_package_update'])
        self.clear_dump_cache(etpCache['filter_satisfied_deps'])
        self.clear_dump_cache(etpCache['atomMatch'])
        self.clear_dump_cache(etpCache['dep_tree'])
        if repoid != None:
            self.clear_dump_cache(etpCache['dbMatch']+"/"+repoid+"/")
            self.clear_dump_cache(etpCache['dbInfo']+"/"+repoid+"/") # it also contains package masking information
            self.clear_dump_cache(etpCache['dbSearch']+"/"+repoid+"/")


    def addRepository(self, repodata):
        # update etpRepositories
        try:
            etpRepositories[repodata['repoid']] = {}
            etpRepositories[repodata['repoid']]['description'] = repodata['description']
            etpRepositories[repodata['repoid']]['configprotect'] = None
            etpRepositories[repodata['repoid']]['configprotectmask'] = None
        except KeyError:
            raise exceptionTools.InvalidData("InvalidData: repodata dictionary is corrupted")

        if repodata['repoid'].endswith(etpConst['packagesext']): # dynamic repository
            try:
                etpRepositories[repodata['repoid']]['packages'] = repodata['packages'][:]
                etpRepositories[repodata['repoid']]['smartpackage'] = repodata['smartpackage']
                etpRepositories[repodata['repoid']]['dbpath'] = repodata['dbpath']
                etpRepositories[repodata['repoid']]['pkgpath'] = repodata['pkgpath']
            except KeyError:
                raise exceptionTools.InvalidData("InvalidData: repodata dictionary is corrupted")
            # put at top priority, shift others
            etpRepositoriesOrder.insert(0,repodata['repoid'])
        else:
            # XXX it's boring to keep this in sync with entropyConstants stuff, solutions?
            etpRepositories[repodata['repoid']]['packages'] = [x+"/"+etpConst['product'] for x in repodata['packages']]
            etpRepositories[repodata['repoid']]['database'] = repodata['database'] + "/" + etpConst['product'] + "/database/" + etpConst['currentarch']
            etpRepositories[repodata['repoid']]['dbcformat'] = repodata['dbcformat']
            etpRepositories[repodata['repoid']]['dbpath'] = etpConst['etpdatabaseclientdir'] + "/" + repodata['repoid'] + "/" + etpConst['product'] + "/" + etpConst['currentarch']
            # set dbrevision
            myrev = self.get_repository_revision(repodata['repoid'])
            if myrev == -1:
                myrev = 0
            etpRepositories[repodata['repoid']]['dbrevision'] = str(myrev)
            if repodata.has_key("position"):
                etpRepositoriesOrder.insert(repodata['position'],repodata['repoid'])
            else:
                etpRepositoriesOrder.append(repodata['repoid'])
            self.repository_move_clear_cache(repodata['repoid'])
            # save new etpRepositories to file
            self.entropyTools.saveRepositorySettings(repodata)
            initConfig_entropyConstants(etpSys['rootdir'])

    def removeRepository(self, repoid, disable = False):

        done = False
        if etpRepositories.has_key(repoid):
            del etpRepositories[repoid]
            done = True

        if etpRepositoriesExcluded.has_key(repoid):
            del etpRepositoriesExcluded[repoid]
            done = True

        if done:

            if repoid in etpRepositoriesOrder:
                etpRepositoriesOrder.remove(repoid)

            self.repository_move_clear_cache(repoid)
            # save new etpRepositories to file
            repodata = {}
            repodata['repoid'] = repoid
            if disable:
                self.entropyTools.saveRepositorySettings(repodata, disable = True)
            else:
                self.entropyTools.saveRepositorySettings(repodata, remove = True)
            initConfig_entropyConstants(etpSys['rootdir'])

    def shiftRepository(self, repoid, toidx):
        # update etpRepositoriesOrder
        etpRepositoriesOrder.remove(repoid)
        etpRepositoriesOrder.insert(toidx,repoid)
        self.entropyTools.writeOrderedRepositoriesEntries()
        initConfig_entropyConstants(etpSys['rootdir'])
        self.repository_move_clear_cache(repoid)

    def enableRepository(self, repoid):
        self.repository_move_clear_cache(repoid)
        # save new etpRepositories to file
        repodata = {}
        repodata['repoid'] = repoid
        self.entropyTools.saveRepositorySettings(repodata, enable = True)
        initConfig_entropyConstants(etpSys['rootdir'])

    def disableRepository(self, repoid):
        # update etpRepositories
        done = False
        try:
            del etpRepositories[repoid]
            done = True
        except:
            pass

        if done:
            try:
                etpRepositoriesOrder.remove(repoid)
            except:
                pass
            # it's not vital to reset etpRepositoriesOrder counters

            self.repository_move_clear_cache(repoid)
            # save new etpRepositories to file
            repodata = {}
            repodata['repoid'] = repoid
            self.entropyTools.saveRepositorySettings(repodata, disable = True)
            initConfig_entropyConstants(etpSys['rootdir'])


    '''
    @description: filter the already installed dependencies
    @input dependencies: list of dependencies to check
    @output: filtered list, aka the needed ones and the ones satisfied
    '''
    def filterSatisfiedDependencies(self, dependencies, deep_deps = False):

        if self.xcache:
            c_data = list(dependencies)
            c_data.sort()
            client_checksum = self.clientDbconn.database_checksum()
            c_hash = str(hash(tuple(c_data)))+str(hash(deep_deps))+client_checksum
            c_hash = str(hash(c_hash))
            del c_data
            cached = self.dumpTools.loadobj(etpCache['filter_satisfied_deps']+c_hash)
            if cached != None:
                return cached

        unsatisfiedDeps = set()
        satisfiedDeps = set()

        for dependency in dependencies:

            depsatisfied = set()
            depunsatisfied = set()

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

                try:
                    installedVer = self.clientDbconn.retrieveVersion(clientMatch[0])
                    installedTag = self.clientDbconn.retrieveVersionTag(clientMatch[0])
                    installedRev = self.clientDbconn.retrieveRevision(clientMatch[0])
                except TypeError: # corrupted entry?
                    installedVer = "0"
                    installedTag = ''
                    installedRev = 0
                if installedRev == 9999: # any revision is fine
                    repo_pkgrev = 9999

                if (deep_deps):
                    vcmp = self.entropyTools.entropyCompareVersions((repo_pkgver,repo_pkgtag,repo_pkgrev),(installedVer,installedTag,installedRev))
                    if vcmp != 0:
                        depunsatisfied.add(dependency)
                    else:
                        # check if needed is the same?
                        depsatisfied.add(dependency)
                else:
                    depsatisfied.add(dependency)
            else:
                # not the same version installed
                depunsatisfied.add(dependency)

            if depsatisfied:
                # check if it's really satisfied by looking at needed
                installedNeeded = self.clientDbconn.retrieveNeeded(clientMatch[0])
                repo_needed = dbconn.retrieveNeeded(repoMatch[0])
                if installedNeeded != repo_needed:
                    depunsatisfied.update(depsatisfied)
                    depsatisfied.clear()

            unsatisfiedDeps.update(depunsatisfied)
            satisfiedDeps.update(depsatisfied)

        if self.xcache:
            try:
                self.dumpTools.dumpobj(etpCache['filter_satisfied_deps']+c_hash,(unsatisfiedDeps,satisfiedDeps))
            except IOError:
                pass

        return unsatisfiedDeps, satisfiedDeps


    '''
    @description: generates a dependency tree using unsatisfied dependencies
    @input package: atomInfo (idpackage,reponame)
    @output: dependency tree dictionary, plus status code
    '''
    def generate_dependency_tree(self, atomInfo, empty_deps = False, deep_deps = False, matchfilter = None):

        usefilter = False
        if matchfilter != None:
            usefilter = True

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
        if usefilter:
            if not matchfilter.inside(atomInfo):
                deptree.add((1,atomInfo))
        else:
            deptree.add((1,atomInfo))

        virgin = True
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
            if virgin:
                virgin = False
                match = atomInfo
            else:
                match = self.atomMatch(mydep[1])
            if match[0] == -1:
                dependenciesNotFound.add(mydep[1])
                mydep = mybuffer.pop()
                continue

            # check if atom has been already pulled in
            matchdb = self.openRepositoryDatabase(match[1])
            matchatom = matchdb.retrieveAtom(match[0])
            matchkey, matchslot = matchdb.retrieveKeySlot(match[0])
            if matchatom in treecache:
                mydep = mybuffer.pop()
                continue
            else:
                treecache.add(matchatom)

            treecache.add(mydep[1])

            # check if key + slot has been already pulled in
            if (matchslot,matchkey) in keyslotcache:
                mydep = mybuffer.pop()
                continue
            else:
                keyslotcache.add((matchslot,matchkey))

            # already analyzed by the calling function
            if usefilter:
                if matchfilter.inside(match):
                    mydep = mybuffer.pop()
                    continue
                matchfilter.add(match)

            # result already analyzed?
            if match in matchcache:
                mydep = mybuffer.pop()
                continue

            treedepth = mydep[0]+1

            # all checks passed, well done
            matchcache.add(match)
            deptree.add((mydep[0],match)) # add match

            # extra library breakages check
            clientmatch = self.clientDbconn.atomMatch(matchkey, matchSlot = matchslot)
            if clientmatch[0] != -1:
                broken_atoms = self._lookup_library_breakages(match, clientmatch, deep_deps = deep_deps)
                for x in broken_atoms:
                    if x not in treecache:
                        mybuffer.push((treedepth,x))

            myundeps = matchdb.retrieveDependenciesList(match[0])
            if (not empty_deps):
                myundeps, xxx = self.filterSatisfiedDependencies(myundeps, deep_deps = deep_deps)
                del xxx
            for x in myundeps:
                mybuffer.push((treedepth,x))

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

        treecache.clear()
        matchcache.clear()

        return newdeptree,0 # note: newtree[0] contains possible conflicts

    def _lookup_library_breakages(self, match, clientmatch, deep_deps = False):

        # there is no need to update this cache when "match" will be installed, because at that point
        # clientmatch[0] will differ.
        if self.xcache:
            c_hash = str(hash(tuple(match)))+str(hash(clientmatch[0]))+str(hash(deep_deps))
            c_hash = str(hash(c_hash))
            cached = self.dumpTools.loadobj(etpCache['library_breakage']+c_hash)
            if cached != None:
                return cached

        matchdb = self.openRepositoryDatabase(match[1])
        reponeeded = matchdb.retrieveNeeded(match[0])
        clientneeded = self.clientDbconn.retrieveNeeded(clientmatch[0])
        neededdiff = clientneeded - reponeeded
        #neededdiff |= reponeeded - clientneeded
        broken_atoms = set()
        if neededdiff:
            # test content
            repocontent = matchdb.retrieveContent(match[0])
            repocontent = set([x for x in repocontent if (x.find(".so") != -1)])
            repocontent = set([x for x in repocontent if (matchdb.isNeededAvailable(os.path.basename(x)) > 0)])
            clientcontent = self.clientDbconn.retrieveContent(clientmatch[0])
            clientcontent = set([x for x in clientcontent if (x.find(".so") != -1)])
            clientcontent = set([x for x in clientcontent if (self.clientDbconn.isNeededAvailable(os.path.basename(x)) > 0)])
            clientcontent -= repocontent
            del repocontent
            search_libs = set()
            linker_paths = self.entropyTools.collectLinkerPaths()
            for cfile in clientcontent:
                cpath = os.path.dirname(cfile)
                if cpath in linker_paths:
                    # there's a breakage
                    cfile = os.path.basename(cfile)
                    # search cfile
                    search_libs.add(cfile)
            #search_libs |= neededdiff
            del clientcontent
            search_matches = set()
            for x in search_libs:
                y = self.clientDbconn.searchNeeded(x)
                search_matches |= y
            del search_libs
            found_search_atoms = set()
            for x in search_matches:
                search_key, search_slot = self.clientDbconn.retrieveKeySlot(x)
                search_repo_match = self.atomMatch(search_key, matchSlot = search_slot)
                if search_repo_match[0] != -1:
                    found_search_atoms.add("%s:%s" % (search_key,str(search_slot),))
            if found_search_atoms:
                search_unsat, xxx = self.filterSatisfiedDependencies(found_search_atoms, deep_deps = deep_deps)
                broken_atoms |= search_unsat

        if self.xcache:
            try:
                self.dumpTools.dumpobj(etpCache['library_breakage']+c_hash,broken_atoms)
            except IOError:
                pass
        return broken_atoms

    def get_required_packages(self, matched_atoms, empty_deps = False, deep_deps = False):

        # clear masking reasons
        maskingReasonsStorage.clear()

        if self.xcache:
            c_data = list(matched_atoms)
            c_data.sort()
            client_checksum = self.clientDbconn.database_checksum()
            c_hash = str(hash(tuple(c_data)))+str(hash(empty_deps))+str(hash(deep_deps))+client_checksum
            c_hash = str(hash(c_hash))
            del c_data
            cached = self.dumpTools.loadobj(etpCache['dep_tree']+c_hash)
            if cached != None:
                return cached

        deptree = {}
        deptree[0] = set()

        atomlen = len(matched_atoms); count = 0
        matchfilter = matchContainer()
        error_generated = 0
        error_tree = set()

        for atomInfo in matched_atoms:

            count += 1
            if (count%10 == 0) or (count == atomlen) or (count == 1):
                self.updateProgress("Sorting dependencies", importance = 0, type = "info", back = True, header = ":: ", footer = " ::", percent = True, count = (count,atomlen))

            # check if atomInfo is in matchfilter
            newtree, result = self.generate_dependency_tree(atomInfo, empty_deps, deep_deps, matchfilter = matchfilter)

            if result == -2: # deps not found
                error_generated = -2
                error_tree |= set(newtree) # it is a list, we convert it into set and update error_tree
            elif (result != 0):
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

        matchfilter.clear()
        del matchfilter

        if error_generated != 0:
            return error_tree,error_generated

        if self.xcache:
            try:
                self.dumpTools.dumpobj(etpCache['dep_tree']+c_hash,(deptree,0))
            except IOError:
                pass
        return deptree,0

    '''
    @description: generates a depends tree using provided idpackages (from client database)
                    !!! you can see it as the function that generates the removal tree
    @input package: idpackages list
    @output: 	depends tree dictionary, plus status code
    '''
    def generate_depends_tree(self, idpackages, deep = False):

        if self.xcache:
            c_data = list(idpackages)
            c_data.sort()
            c_hash = str(hash(tuple(c_data))) + str(hash(deep))
            c_hash = str(hash(c_hash))
            del c_data
            cached = self.dumpTools.loadobj(etpCache['depends_tree']+c_hash)
            if cached != None:
                return cached

        dependscache = set()
        treeview = set(idpackages)
        treelevel = set(idpackages)
        tree = {}
        treedepth = 0 # I start from level 1 because level 0 is idpackages itself
        tree[treedepth] = set(idpackages)
        monotree = set(idpackages) # monodimensional tree

        # check if dependstable is sane before beginning
        self.clientDbconn.retrieveDepends(idpackages[0])
        count = 0

        while 1:
            treedepth += 1
            tree[treedepth] = set()
            for idpackage in treelevel:

                count += 1
                p_atom = self.clientDbconn.retrieveAtom(idpackage)
                self.updateProgress(blue("Calculating removable depends of %s") % (red(p_atom),), importance = 0, type = "info", back = True, header = '|/-\\'[count%4]+" ")

                systempkg = self.clientDbconn.isSystemPackage(idpackage)
                if (idpackage in dependscache) or systempkg:
                    if idpackage in treeview:
                        treeview.remove(idpackage)
                    continue

                # obtain its depends
                depends = self.clientDbconn.retrieveDepends(idpackage)
                # filter already satisfied ones
                depends = [x for x in depends if x not in monotree and not self.clientDbconn.isSystemPackage(x)]
                if depends: # something depends on idpackage
                    for x in depends:
                        if x not in tree[treedepth]:
                            tree[treedepth].add(x)
                            monotree.add(x)
                            treeview.add(x)
                elif deep: # if deep, grab its dependencies and check

                    mydeps = set()
                    for x in self.clientDbconn.retrieveDependencies(idpackage):
                        match = self.clientDbconn.atomMatch(x)
                        if match[0] != -1:
                            mydeps.add(match[0])

                    # now filter them
                    mydeps = [x for x in mydeps if x not in monotree and (not self.clientDbconn.isSystemPackage(x))]
                    for x in mydeps:
                        mydepends = self.clientDbconn.retrieveDepends(x)
                        mydepends = set([y for y in mydepends if y not in monotree])
                        if not mydepends:
                            tree[treedepth].add(x)
                            monotree.add(x)
                            treeview.add(x)

                dependscache.add(idpackage)
                if idpackage in treeview:
                    treeview.remove(idpackage)

            treelevel = treeview.copy()
            if not treelevel:
                if not tree[treedepth]:
                    del tree[treedepth] # probably the last one is empty then
                break

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

        if self.xcache:
            try:
                self.dumpTools.dumpobj(etpCache['depends_tree']+c_hash,(newtree,0))
            except IOError:
                pass
        return newtree,0 # treeview is used to show deps while tree is used to run the dependency code.

    def list_repo_categories(self):
        categories = set()
        for repo in etpRepositories:
            dbconn = self.openRepositoryDatabase(repo)
            catsdata = dbconn.listAllCategories()
            categories.update(set([x[1] for x in catsdata]))
        return categories

    def list_repo_packages_in_category(self, category):
        pkg_matches = set()
        for repo in etpRepositories:
            dbconn = self.openRepositoryDatabase(repo)
            catsdata = dbconn.searchPackagesByCategory(category, branch = etpConst['branch'])
            pkg_matches.update(set([(x[1],repo) for x in catsdata]))
        return pkg_matches

    def list_installed_packages_in_category(self, category):
        pkg_matches = set([x[1] for x in self.clientDbconn.searchPackagesByCategory(category)])
        return pkg_matches

    def all_repositories_checksum(self):
        sum_hashes = ''
        for repo in etpRepositories:
            try:
                dbconn = self.openRepositoryDatabase(repo)
            except exceptionTools.RepositoryError:
                continue # repo not available
            sum_hashes += dbconn.database_checksum()
        return sum_hashes

    def get_available_packages_chash(self, branch):
        repo_digest = self.all_repositories_checksum()
        # client digest not needed, cache is kept updated
        c_hash = str(hash(repo_digest)) + \
                 str(hash(branch)) + \
                 str(hash(tuple(etpRepositories))) + \
                 str(hash(tuple(etpRepositoriesOrder)))
        c_hash = str(hash(c_hash))
        return c_hash

    # this function searches all the not installed packages available in the repositories
    def calculate_available_packages(self):

        # clear masking reasons
        maskingReasonsStorage.clear()

        if self.xcache:
            c_hash = self.get_available_packages_chash(etpConst['branch'])
            disk_cache = self.dumpTools.loadobj(etpCache['world_available'])
            if disk_cache != None:
                try:
                    if disk_cache['chash'] == c_hash:
                        return disk_cache['available']
                except KeyError:
                    pass

        available = set()
        self.setTotalCycles(len(etpRepositoriesOrder))
        for repo in etpRepositoriesOrder:
            try:
                dbconn = self.openRepositoryDatabase(repo)
            except exceptionTools.RepositoryError:
                self.cycleDone()
                continue
            idpackages = dbconn.listAllIdpackages(branch = etpConst['branch'], branch_operator = "<=")
            count = 0
            maxlen = len(idpackages)
            for idpackage in idpackages:
                count += 1
                self.updateProgress("Calculating available packages for %s" % (repo,), importance = 0, type = "info", back = True, header = "::", count = (count,maxlen), percent = True, footer = " ::")
                # ignore masked packages
                idpackage, idreason = dbconn.idpackageValidator(idpackage)
                if idpackage == -1:
                    continue
                # get key + slot
                key, slot = dbconn.retrieveKeySlot(idpackage)
                matches = self.clientDbconn.searchKeySlot(key, slot)
                if not matches:
                    available.add((idpackage,repo))
            self.cycleDone()

        if self.xcache:
            try:
                data = {}
                data['chash'] = c_hash
                data['available'] = available
                self.dumpTools.dumpobj(etpCache['world_available'],data)
            except IOError:
                pass
        return available

    def get_world_update_cache(self, empty_deps, branch = etpConst['branch'], db_digest = None):
        if self.xcache:
            if db_digest == None:
                db_digest = self.all_repositories_checksum()
            c_hash = str(hash(db_digest)) + \
                     str(hash(empty_deps)) + \
                     str(hash(tuple(etpRepositories))) + \
                     str(hash(tuple(etpRepositoriesOrder))) + \
                     str(hash(branch))
            c_hash = str(hash(c_hash))
            disk_cache = self.dumpTools.loadobj(etpCache['world_update']+c_hash)
            if disk_cache != None:
                try:
                    return disk_cache['r']
                except (KeyError, TypeError):
                    return None

    def calculate_world_updates(self, empty_deps = False, branch = etpConst['branch']):

        # clear masking reasons
        maskingReasonsStorage.clear()

        db_digest = self.all_repositories_checksum()
        cached = self.get_world_update_cache(empty_deps = empty_deps, branch = branch, db_digest = db_digest)
        if cached != None:
            return cached

        update = set()
        remove = set()
        fine = set()

        # get all the installed packages
        idpackages = self.clientDbconn.listAllIdpackages()
        maxlen = len(idpackages)
        count = 0
        for idpackage in idpackages:
            count += 1
            if (count%10 == 0) or (count == maxlen) or (count == 1):
                self.updateProgress("Calculating world packages", importance = 0, type = "info", back = True, header = ":: ", count = (count,maxlen), percent = True, footer = " ::")
            tainted = False
            myscopedata = self.clientDbconn.getScopeData(idpackage)
            # check against broken entry
            if myscopedata == None:
                continue
            #atom = myscopedata[0]
            #category = myscopedata[1]
            #name = myscopedata[2]
            #slot = myscopedata[4]
            #revision = myscopedata[6]
            #atomkey = myscopedata[1]+"/"+myscopedata[2]
            # search in the packages
            match = self.atomMatch(myscopedata[0])
            if match[0] == -1: # atom has been changed, or removed?
                tainted = True
            else: # not changed, is the revision changed?
                adbconn = self.openRepositoryDatabase(match[1])
                arevision = adbconn.retrieveRevision(match[0])
                # if revision is 9999, then any revision is fine
                if myscopedata[6] == 9999: arevision = 9999
                if empty_deps:
                    tainted = True
                elif myscopedata[6] != arevision:
                    tainted = True
                elif (myscopedata[6] == arevision) and (arevision == 9999):
                    # check if "needed" are the same, otherwise, pull
                    # this will avoid having old packages installed just because user ran equo database generate (migrating from gentoo)
                    # also this helps in environments with multiple repositories, to avoid messing with libraries
                    aneeded = adbconn.retrieveNeeded(match[0])
                    needed = self.clientDbconn.retrieveNeeded(idpackage)
                    if needed != aneeded:
                        tainted = True
                    #'''
                    else:
                        # check use flags too
                        # it helps for the same reason above and when doing upgrades to different branches
                        auseflags = adbconn.retrieveUseflags(match[0])
                        useflags = self.clientDbconn.retrieveUseflags(idpackage)
                        if auseflags != useflags:
                            tainted = True
                    #'''
            if (tainted):
                # Alice! use the key! ... and the slot
                matchresults = self.atomMatch(myscopedata[1]+"/"+myscopedata[2], matchSlot = myscopedata[4], matchBranches = (branch,))
                if matchresults[0] != -1:
                    #mdbconn = self.openRepositoryDatabase(matchresults[1])
                    update.add(matchresults)
                else:
                    # don't take action if it's just masked
                    maskedresults = self.atomMatch(myscopedata[1]+"/"+myscopedata[2], matchSlot = myscopedata[4], matchBranches = (branch,), packagesFilter = False)
                    if maskedresults[0] == -1:
                        remove.add(idpackage)
                        # look for packages that would match key with any slot (for eg, gcc updates)
                        matchresults = self.atomMatch(myscopedata[1]+"/"+myscopedata[2], matchBranches = (branch,))
                        if matchresults[0] != -1:
                            update.add(matchresults)

            else:
                fine.add(myscopedata[0])

        del idpackages

        if self.xcache:
            c_hash = str(hash(db_digest)) + \
                     str(hash(empty_deps)) + \
                     str(hash(tuple(etpRepositories))) + \
                     str(hash(tuple(etpRepositoriesOrder))) + \
                     str(hash(branch))
            c_hash = str(hash(c_hash))
            data = {}
            data['r'] = (update, remove, fine)
            data['empty_deps'] = empty_deps
            try:
                self.dumpTools.dumpobj(etpCache['world_update']+c_hash, data)
            except IOError:
                pass
        return update, remove, fine

    def get_match_conflicts(self, match):
        dbconn = self.openRepositoryDatabase(match[1])
        conflicts = dbconn.retrieveConflicts(match[0])
        found_conflicts = set()
        for conflict in conflicts:
            match = self.clientDbconn.atomMatch(conflict)
            if match[0] != -1:
                found_conflicts.add(match[0])
        return found_conflicts

    def is_match_masked(self, match):
        dbconn = self.openRepositoryDatabase(match[1])
        idpackage, idreason = dbconn.idpackageValidator(match[0])
        if idpackage != -1:
            return False
        return True

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
        repodata = {}
        repodata['repoid'] = basefile
        repodata['description'] = "Dynamic database from "+basefile
        repodata['packages'] = []
        repodata['dbpath'] = os.path.dirname(dbfile)
        repodata['pkgpath'] = os.path.realpath(tbz2file) # extra info added
        repodata['smartpackage'] = False # extra info added
        self.addRepository(repodata)
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
            atoms_contained.append((int(myidpackage),basefile))
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
            install, removal, status = self.retrieveInstallQueue(update, empty_deps, deep_deps = False)
            # update data['removed']
            data['removed'] = [x for x in data['removed'] if x not in removal]
            data['runQueue'] += install
            data['removalQueue'] += removal
        return data,status

    def validatePackageRemoval(self, idpackage):
        system_pkg = self.clientDbconn.isSystemPackage(idpackage)
        if not system_pkg:
            return True # valid

        pkgatom = self.clientDbconn.retrieveAtom(idpackage)
        # check if the package is slotted and exist more than one installed first
        sysresults = self.clientDbconn.atomMatch(self.entropyTools.dep_getkey(pkgatom), multiMatch = True)
        slots = set()
        if sysresults[1] == 0:
            for x in sysresults[0]:
                slots.add(self.clientDbconn.retrieveSlot(x))
            if len(slots) < 2:
                return False
            return True # valid
        else:
            return False


    def retrieveRemovalQueue(self, idpackages, deep = False):
        queue = []
        treeview = self.generate_depends_tree(idpackages, deep = deep)
        for x in range(len(treeview[0]))[::-1]:
            for y in treeview[0][x]:
                queue.append(y)
        return queue

    def retrieveInstallQueue(self, matched_atoms, empty_deps, deep_deps):

        # clear masking reasons
        maskingReasonsStorage.clear()

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
                # XXX check if stupid users removed idpackage while this whole instance is running
                if not self.clientDbconn.isIDPackageAvailable(x):
                    continue
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

        # etpConst['handlers']['md5sum'] is the command
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
        request = url+etpConst['handlers']['md5sum']+filename+"&branch="+branch

        # now pray the server
        try:
            if etpConst['proxy']:
                proxy_support = urllib2.ProxyHandler(etpConst['proxy'])
                opener = urllib2.build_opener(proxy_support)
                urllib2.install_opener(opener)
            item = urllib2.urlopen(request)
            result = item.readline().strip()
            item.close()
            del item
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
    @output: 0 = all fine, !=0 = error on all the available mirrors
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
                return 3

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
                            #self.add_failing_mirror(uri,2)
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
        return 0

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
        resultfile = self.quickpkg_handler(pkgdata = pkgdata, dirpath = savedir)
        if resultfile == None:
            return -1,atom,None
        else:
            return 0,atom,resultfile

    def quickpkg_handler(
                                self,
                                pkgdata,
                                dirpath,
                                edb = True,
                                portdbPath = None,
                                fake = False,
                                compression = "bz2",
                                shiftpath = ""
                        ):

        import stat
        import tarfile

        if compression not in ("bz2","","gz"):
            compression = "bz2"

        # getting package info
        pkgtag = ''
        pkgrev = "~"+str(pkgdata['revision'])
        if pkgdata['versiontag']: pkgtag = "#"+pkgdata['versiontag']
        pkgname = pkgdata['name']+"-"+pkgdata['version']+pkgrev+pkgtag # + version + tag
        pkgcat = pkgdata['category']
        #pkgfile = pkgname+etpConst['packagesext']
        dirpath += "/"+pkgname+etpConst['packagesext']
        if os.path.isfile(dirpath):
            os.remove(dirpath)
        tar = tarfile.open(dirpath,"w:"+compression)

        if not fake:

            contents = [x for x in pkgdata['content']]
            id_strings = {}
            contents.sort()

            # collect files
            for path in contents:
                # convert back to filesystem str
                encoded_path = path
                path = path.encode('raw_unicode_escape')
                path = shiftpath+path
                try:
                    exist = os.lstat(path)
                except OSError:
                    continue # skip file
                arcname = path[len(shiftpath):] # remove shiftpath
                if arcname.startswith("/"):
                    arcname = arcname[1:] # remove trailing /
                ftype = pkgdata['content'][encoded_path]
                if str(ftype) == '0': ftype = 'dir' # force match below, '0' means databases without ftype
                if 'dir' == ftype and \
                    not stat.S_ISDIR(exist.st_mode) and \
                    os.path.isdir(path): # workaround for directory symlink issues
                    path = os.path.realpath(path)

                tarinfo = tar.gettarinfo(path, arcname)
                tarinfo.uname = id_strings.setdefault(tarinfo.uid, str(tarinfo.uid))
                tarinfo.gname = id_strings.setdefault(tarinfo.gid, str(tarinfo.gid))

                if stat.S_ISREG(exist.st_mode):
                    tarinfo.type = tarfile.REGTYPE
                    f = open(path)
                    try:
                        tar.addfile(tarinfo, f)
                    finally:
                        f.close()
                else:
                    tar.addfile(tarinfo)

        tar.close()

        # appending xpak metadata
        if etpConst['gentoo-compat']:
            import etpXpak
            Spm = self.Spm()

            gentoo_name = self.entropyTools.remove_tag(pkgname)
            gentoo_name = self.entropyTools.remove_entropy_revision(gentoo_name)
            if portdbPath == None:
                dbdir = Spm.get_vdb_path()+"/"+pkgcat+"/"+gentoo_name+"/"
            else:
                dbdir = portdbPath+"/"+pkgcat+"/"+gentoo_name+"/"
            if os.path.isdir(dbdir):
                tbz2 = etpXpak.tbz2(dirpath)
                tbz2.recompose(dbdir)

        if edb:
            self.inject_entropy_database_into_package(dirpath, pkgdata)

        if os.path.isfile(dirpath):
            return dirpath
        return None

    def inject_entropy_database_into_package(self, package_filename, data):
        dbpath = self.get_tmp_dbpath()
        dbconn = self.openGenericDatabase(dbpath)
        dbconn.initializeDatabase()
        dbconn.addPackage(data, revision = data['revision'])
        dbconn.commitChanges()
        dbconn.closeDB()
        self.entropyTools.aggregateEdb(tbz2file = package_filename, dbfile = dbpath)
        return dbpath

    def get_tmp_dbpath(self):
        dbpath = etpConst['packagestmpdir']+"/"+str(self.entropyTools.getRandomNumber())
        while os.path.isfile(dbpath):
            dbpath = etpConst['packagestmpdir']+"/"+str(self.entropyTools.getRandomNumber())
        return dbpath

    def Package(self):
        conn = PackageInterface(EquoInstance = self)
        return conn

    '''
        Package interface :: end
    '''

    '''
        Source Package Manager Interface :: begin
    '''
    def Spm(self):
        myroot = etpConst['systemroot']
        cached = self.spmCache.get(myroot)
        if cached != None:
            return cached
        conn = SpmInterface(self)
        self.spmCache[myroot] = conn.intf
        return conn.intf

    # This function extracts all the info from a .tbz2 file and returns them
    def extract_pkg_metadata(self, package, etpBranch = etpConst['branch'], silent = False, inject = False):

        data = {}
        info_package = bold(os.path.basename(package))+": "

        filepath = package
        if not silent:
            self.updateProgress(
                        red(info_package+"Getting package name/version..."),
                        importance = 0,
                        type = "info",
                        header = brown(" * "),
                        back = True
                    )
        tbz2File = package
        package = package.split(etpConst['packagesext'])[0]
        package = self.entropyTools.remove_entropy_revision(package)
        package = self.entropyTools.remove_tag(package)
        # remove category
        if package.find(":") != -1:
            package = ':'.join(package.split(":")[1:])

        package = package.split("-")
        pkgname = ""
        pkglen = len(package)
        if package[pkglen-1].startswith("r"):
            pkgver = package[pkglen-2]+"-"+package[pkglen-1]
            pkglen -= 2
        else:
            pkgver = package[-1]
            pkglen -= 1
        for i in range(pkglen):
            if i == pkglen-1:
                pkgname += package[i]
            else:
                pkgname += package[i]+"-"
        pkgname = pkgname.split("/")[-1]

        # Fill Package name and version
        data['name'] = pkgname
        data['version'] = pkgver

        if not silent:
            self.updateProgress(
                        red(info_package+"Getting package md5..."),
                        importance = 0,
                        type = "info",
                        header = brown(" * "),
                        back = True
                    )
        # .tbz2 md5
        data['digest'] = self.entropyTools.md5sum(tbz2File)

        if not silent:
            self.updateProgress(
                        red(info_package+"Getting package mtime..."),
                        importance = 0,
                        type = "info",
                        header = brown(" * "),
                        back = True
                    )
        data['datecreation'] = str(self.entropyTools.getFileUnixMtime(tbz2File))

        if not silent:
            self.updateProgress(
                        red(info_package+"Getting package size..."),
                        importance = 0,
                        type = "info",
                        header = brown(" * "),
                        back = True
                    )
        # .tbz2 byte size
        data['size'] = str(os.stat(tbz2File)[6])

        if not silent:
            self.updateProgress(
                        red(info_package+"Unpacking package data..."),
                        importance = 0,
                        type = "info",
                        header = brown(" * "),
                        back = True
                    )
        # unpack file
        tbz2TmpDir = etpConst['packagestmpdir']+"/"+data['name']+"-"+data['version']+"/"
        if not os.path.isdir(tbz2TmpDir):
            if os.path.lexists(tbz2TmpDir):
                os.remove(tbz2TmpDir)
            os.makedirs(tbz2TmpDir)
        self.entropyTools.extractXpak(tbz2File,tbz2TmpDir)

        if not silent:
            self.updateProgress(
                        red(info_package+"Getting package CHOST..."),
                        importance = 0,
                        type = "info",
                        header = brown(" * "),
                        back = True
                    )
        # Fill chost
        f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['chost'],"r")
        data['chost'] = f.readline().strip()
        f.close()

        if not silent:
            self.updateProgress(
                    red(info_package+"Setting package branch..."),
                    importance = 0,
                    type = "info",
                    header = brown(" * "),
                    back = True
                )
        data['branch'] = etpBranch

        if not silent:
            self.updateProgress(
                    red(info_package+"Getting package description..."),
                    importance = 0,
                    type = "info",
                    header = brown(" * "),
                    back = True
                )
        # Fill description
        data['description'] = ""
        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['description'],"r")
            data['description'] = f.readline().strip()
            f.close()
        except IOError:
            pass

        if not silent:
            self.updateProgress(
                    red(info_package+"Getting package homepage..."),
                    importance = 0,
                    type = "info",
                    header = brown(" * "),
                    back = True
                )
        # Fill homepage
        data['homepage'] = ""
        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['homepage'],"r")
            data['homepage'] = f.readline().strip()
            f.close()
        except IOError:
            pass

        if not silent:
            self.updateProgress(
                    red(info_package+"Getting package slot information..."),
                    importance = 0,
                    type = "info",
                    header = brown(" * "),
                    back = True
                )
        # fill slot, if it is
        data['slot'] = ""
        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['slot'],"r")
            data['slot'] = f.readline().strip()
            f.close()
        except IOError:
            pass

        if not silent:
            self.updateProgress(
                    red(info_package+"Getting package injection information..."),
                    importance = 0,
                    type = "info",
                    header = brown(" * "),
                    back = True
                )
        # fill slot, if it is
        if inject:
            data['injected'] = True
        else:
            data['injected'] = False

        if not silent:
            self.updateProgress(
                red(info_package+"Getting package eclasses information..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # fill eclasses list
        data['eclasses'] = []
        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['inherited'],"r")
            data['eclasses'] = f.readline().strip().split()
            f.close()
        except IOError:
            pass

        if not silent:
            self.updateProgress(
                red(info_package+"Getting package needed libraries information..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # fill needed list
        data['needed'] = set()
        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['needed'],"r")
            lines = f.readlines()
            f.close()
            for line in lines:
                line = line.strip()
                if line:
                    needed = line.split()
                    if len(needed) == 2:
                        libs = needed[1].split(",")
                        for lib in libs:
                            if (lib.find(".so") != -1):
                                data['needed'].add(lib)
        except IOError:
            pass
        data['needed'] = list(data['needed'])

        if not silent:
            self.updateProgress(
                red(info_package+"Getting package content..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        data['content'] = {}
        if os.path.isfile(tbz2TmpDir+etpConst['spm']['xpak_entries']['contents']):
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['contents'],"r")
            content = f.readlines()
            f.close()
            outcontent = set()
            for line in content:
                line = line.strip().split()
                try:
                    datatype = line[0]
                    datafile = line[1:]
                    if datatype == 'obj':
                        datafile = datafile[:-2]
                        datafile = ' '.join(datafile)
                    elif datatype == 'dir':
                        datafile = ' '.join(datafile)
                    elif datatype == 'sym':
                        datafile = datafile[:-3]
                        datafile = ' '.join(datafile)
                    else:
                        raise exceptionTools.InvalidData("InvalidData: "+str(datafile)+" not supported. Probably portage API changed.")
                    outcontent.add((datafile,datatype))
                except:
                    pass

            _outcontent = set()
            for i in outcontent:
                i = list(i)
                datatype = i[1]
                _outcontent.add((i[0],i[1]))
            outcontent = list(_outcontent)
            outcontent.sort()
            for i in outcontent:
                data['content'][i[0]] = i[1]

        else:
            # CONTENTS is not generated when a package is emerged with portage and the option -B
            # we have to unpack the tbz2 and generate content dict
            mytempdir = etpConst['packagestmpdir']+"/"+os.path.basename(filepath)+".inject"
            if os.path.isdir(mytempdir):
                shutil.rmtree(mytempdir)
            if not os.path.isdir(mytempdir):
                os.makedirs(mytempdir)
            self.entropyTools.uncompressTarBz2(filepath, extractPath = mytempdir, catchEmpty = True)

            for currentdir, subdirs, files in os.walk(mytempdir):
                data['content'][currentdir[len(mytempdir):]] = "dir"
                for item in files:
                    item = currentdir+"/"+item
                    if os.path.islink(item):
                        data['content'][item[len(mytempdir):]] = "sym"
                    else:
                        data['content'][item[len(mytempdir):]] = "obj"

            # now remove
            shutil.rmtree(mytempdir,True)
            try:
                os.rmdir(mytempdir)
            except:
                pass

        # files size on disk
        if (data['content']):
            data['disksize'] = 0
            for item in data['content']:
                try:
                    size = os.stat(item)[6]
                    data['disksize'] += size
                except:
                    pass
        else:
            data['disksize'] = 0

        # [][][] Kernel dependent packages hook [][][]
        data['versiontag'] = ''
        kernelstuff = False
        kernelstuff_kernel = False
        for item in data['content']:
            if item.startswith("/lib/modules/"):
                kernelstuff = True
                # get the version of the modules
                kmodver = item.split("/lib/modules/")[1]
                kmodver = kmodver.split("/")[0]

                lp = kmodver.split("-")[-1]
                if lp.startswith("r"):
                    kname = kmodver.split("-")[-2]
                    kver = kmodver.split("-")[0]+"-"+kmodver.split("-")[-1]
                else:
                    kname = kmodver.split("-")[-1]
                    kver = kmodver.split("-")[0]
                break
        # validate the results above
        if (kernelstuff):
            matchatom = "linux-%s-%s" % (kname,kver,)
            if (matchatom == data['name']+"-"+data['version']):
                kernelstuff_kernel = True

        if not silent:
            self.updateProgress(
                red(info_package+"Getting package category..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # Fill category
        f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['category'],"r")
        data['category'] = f.readline().strip()
        f.close()

        if not silent:
            self.updateProgress(
                red(info_package+"Getting package download URL..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # Fill download relative URI
        if (kernelstuff):
            data['versiontag'] = kmodver
            if not kernelstuff_kernel:
                data['slot'] = kmodver # if you change this behaviour,
                                       # you must change "reagent update"
                                       # and "equo database gentoosync" consequentially
            versiontag = "#"+data['versiontag']
        else:
            versiontag = ""
        data['download'] = etpConst['packagesrelativepath']+data['branch']+"/"+data['category']+":"+data['name']+"-"+data['version']+versiontag+etpConst['packagesext']

        if not silent:
            self.updateProgress(
                red(info_package+"Getting package counter..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # Fill counter
        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['counter'],"r")
            data['counter'] = int(f.readline().strip())
            f.close()
        except IOError:
            data['counter'] = -2 # -2 values will be insterted as incremental negative values into the database

        data['trigger'] = ""
        if not silent:
            self.updateProgress(
                red(info_package+"Getting package external trigger availability..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        if os.path.isfile(etpConst['triggersdir']+"/"+data['category']+"/"+data['name']+"/"+etpConst['triggername']):
            f = open(etpConst['triggersdir']+"/"+data['category']+"/"+data['name']+"/"+etpConst['triggername'],"rb")
            data['trigger'] = f.read()
            f.close()

        if not silent:
            self.updateProgress(
                red(info_package+"Getting package CFLAGS..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # Fill CFLAGS
        data['cflags'] = ""
        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['cflags'],"r")
            data['cflags'] = f.readline().strip()
            f.close()
        except IOError:
            pass

        if not silent:
            self.updateProgress(
                red(info_package+"Getting package CXXFLAGS..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # Fill CXXFLAGS
        data['cxxflags'] = ""
        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['cxxflags'],"r")
            data['cxxflags'] = f.readline().strip()
            f.close()
        except IOError:
            pass

        if not silent:
            self.updateProgress(
                red(info_package+"Getting source package supported ARCHs..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # fill KEYWORDS
        data['keywords'] = []
        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['keywords'],"r")
            cnt = f.readline().strip().split()
            if not cnt:
                data['keywords'].append("") # support for packages with no keywords
            else:
                for i in cnt:
                    if i:
                        data['keywords'].append(i)
            f.close()
        except IOError:
            pass

        if not silent:
            self.updateProgress(
                red(info_package+"Getting package dependencies..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )

        f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['rdepend'],"r")
        rdepend = f.readline().strip()
        f.close()

        f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['pdepend'],"r")
        pdepend = f.readline().strip()
        f.close()

        f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['depend'],"r")
        depend = f.readline().strip()
        f.close()

        f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['use'],"r")
        use = f.readline().strip()
        f.close()

        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['iuse'],"r")
            iuse = f.readline().strip()
            f.close()
        except IOError:
            iuse = ""

        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['license'],"r")
            lics = f.readline().strip()
            f.close()
        except IOError:
            lics = ""

        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['provide'],"r")
            provide = f.readline().strip()
        except IOError:
            provide = ""

        try:
            f = open(tbz2TmpDir+etpConst['spm']['xpak_entries']['src_uri'],"r")
            sources = f.readline().strip()
            f.close()
        except IOError:
            sources = ""

        Spm = self.Spm()

        if not silent:
            self.updateProgress(
                red(info_package+"Getting package metadata information..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        portage_metadata = Spm.calculate_dependencies(iuse, use, lics, depend, rdepend, pdepend, provide, sources)

        data['provide'] = portage_metadata['PROVIDE'].split()
        data['license'] = portage_metadata['LICENSE']
        data['useflags'] = []
        for x in use.split():
            if x in portage_metadata['USE']:
                data['useflags'].append(x)
            else:
                data['useflags'].append("-"+x)
        data['sources'] = portage_metadata['SRC_URI'].split()
        data['dependencies'] = [x for x in portage_metadata['RDEPEND'].split()+portage_metadata['PDEPEND'].split() if not x.startswith("!") and not x in ("(","||",")","")]
        data['conflicts'] = [x[1:] for x in portage_metadata['RDEPEND'].split()+portage_metadata['PDEPEND'].split() if x.startswith("!") and not x in ("(","||",")","")]

        if (kernelstuff) and (not kernelstuff_kernel):
            # add kname to the dependency
            data['dependencies'].append("=sys-kernel/linux-"+kname+"-"+kver)
            key = data['category']+"/"+data['name']
            if etpConst['conflicting_tagged_packages'].has_key(key):
                myconflicts = etpConst['conflicting_tagged_packages'][key]
                for conflict in myconflicts:
                    data['conflicts'].append(conflict)

        # Get License text if possible
        licenses_dir = os.path.join(Spm.get_spm_setting('PORTDIR'),'licenses')
        data['licensedata'] = {}
        if licenses_dir:
            licdata = [str(x.strip()) for x in data['license'].split() if str(x.strip()) and self.entropyTools.is_valid_string(x.strip())]
            for mylicense in licdata:

                licfile = os.path.join(licenses_dir,mylicense)
                if os.access(licfile,os.R_OK):
                    if self.entropyTools.istextfile(licfile):
                        f = open(licfile)
                        data['licensedata'][mylicense] = f.read()
                        f.close()

        if not silent:
            self.updateProgress(
                red(info_package+"Getting package mirrors list..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # manage data['sources'] to create data['mirrorlinks']
        # =mirror://openoffice|link1|link2|link3
        data['mirrorlinks'] = []
        for i in data['sources']:
            if i.startswith("mirror://"):
                # parse what mirror I need
                mirrorURI = i.split("/")[2]
                mirrorlist = Spm.get_third_party_mirrors(mirrorURI)
                data['mirrorlinks'].append([mirrorURI,mirrorlist]) # mirrorURI = openoffice and mirrorlist = [link1, link2, link3]

        if not silent:
            self.updateProgress(
                red(info_package+"Getting System Packages List..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # write only if it's a systempackage
        data['systempackage'] = ''
        systemPackages = Spm.get_atoms_in_system()
        for x in systemPackages:
            x = self.entropyTools.dep_getkey(x)
            y = data['category']+"/"+data['name']
            if x == y:
                # found
                data['systempackage'] = "xxx"
                break

        if not silent:
            self.updateProgress(
                red(info_package+"Getting CONFIG_PROTECT/CONFIG_PROTECT_MASK List..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # write only if it's a systempackage
        protect, mask = Spm.get_config_protect_and_mask()
        data['config_protect'] = protect
        data['config_protect_mask'] = mask

        # fill data['messages']
        # etpConst['logdir']+"/elog"
        if not os.path.isdir(etpConst['logdir']+"/elog"):
            os.makedirs(etpConst['logdir']+"/elog")
        data['messages'] = []
        if os.path.isdir(etpConst['logdir']+"/elog"):
            elogfiles = os.listdir(etpConst['logdir']+"/elog")
            myelogfile = data['category']+":"+data['name']+"-"+data['version']
            foundfiles = []
            for item in elogfiles:
                if item.startswith(myelogfile):
                    foundfiles.append(item)
            if foundfiles:
                elogfile = foundfiles[0]
                if len(foundfiles) > 1:
                    # get the latest
                    mtimes = []
                    for item in foundfiles:
                        mtimes.append((self.entropyTools.getFileUnixMtime(etpConst['logdir']+"/elog/"+item),item))
                    mtimes.sort()
                    elogfile = mtimes[len(mtimes)-1][1]
                messages = self.entropyTools.extractElog(etpConst['logdir']+"/elog/"+elogfile)
                for message in messages:
                    message = message.replace("emerge","install")
                    data['messages'].append(message)
        else:
            if not silent:
                self.updateProgress(
                    red(etpConst['logdir']+"/elog")+" not set, have you configured make.conf properly?",
                    importance = 1,
                    type = "warning",
                    header = brown(" * ")
                )

        if not silent:
            self.updateProgress(
                red(info_package+"Getting Entropy API version..."),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        # write API info
        data['etpapi'] = etpConst['etpapi']

        # removing temporary directory
        shutil.rmtree(tbz2TmpDir,True)
        if os.path.isdir(tbz2TmpDir):
            try:
                os.remove(tbz2TmpDir)
            except OSError:
                pass

        if not silent:
            self.updateProgress(
                red(info_package+"Done"),
                importance = 0,
                type = "info",
                header = brown(" * "),
                back = True
            )
        return data

    '''
        Source Package Manager Interface :: end
    '''

    '''
        Triggers interface :: begindatabaseStructureUpdates
    '''
    def Triggers(self, phase, pkgdata):
        conn = TriggerInterface(EquoInstance = self, phase = phase, pkgdata = pkgdata)
        return conn
    '''
        Triggers interface :: end
    '''

    '''
        Repository interface :: begin
    '''
    def Repositories(self, reponames = [], forceUpdate = False, noEquoCheck = False, fetchSecurity = True):
        conn = RepoInterface(EquoInstance = self, reponames = reponames, forceUpdate = forceUpdate, noEquoCheck = noEquoCheck, fetchSecurity = fetchSecurity)
        return conn
    '''
        Repository interface :: end
    '''

    '''
        Configuration files (updates, not entropy related) interface :: begin
    '''
    def FileUpdatesInterfaceLoader(self):
        conn = FileUpdatesInterface(EquoInstance = self)
        return conn
    '''
        Configuration files (updates, not entropy related) interface :: end
    '''

    def PackageMaskingParserInterfaceLoader(self):
        conn = PackageMaskingParser(EquoInstance = self)
        return conn

'''
    Real package actions (install/remove) interface
'''
class PackageInterface:

    def __init__(self, EquoInstance):

        if not isinstance(EquoInstance,EquoInterface):
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid Entropy Instance is needed")
        self.Entropy = EquoInstance
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
                    return fetch
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

        if not self.infoDict['merge_from']:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Unpacking package: "+str(self.infoDict['atom']))
        else:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Merging package: "+str(self.infoDict['atom']))

        if os.path.isdir(self.infoDict['unpackdir']):
            shutil.rmtree(self.infoDict['unpackdir'].encode('raw_unicode_escape'))
        elif os.path.isfile(self.infoDict['unpackdir']):
            os.remove(self.infoDict['unpackdir'].encode('raw_unicode_escape'))
        os.makedirs(self.infoDict['imagedir'])

        if not os.path.isfile(self.infoDict['pkgpath']) and not self.infoDict['merge_from']:
            if os.path.isdir(self.infoDict['pkgpath']):
                shutil.rmtree(self.infoDict['pkgpath'])
            if os.path.islink(self.infoDict['pkgpath']):
                os.remove(self.infoDict['pkgpath'])
            self.infoDict['verified'] = False
            self.fetch_step()

        if not self.infoDict['merge_from']:
            rc = self.Entropy.entropyTools.spawnFunction(
                        self.Entropy.entropyTools.uncompressTarBz2,
                        self.infoDict['pkgpath'],
                        self.infoDict['imagedir'],
                        catchEmpty = True
                )
            if rc != 0:
                return rc
        else:
            #self.__fill_image_dir(self.infoDict['merge_from'],self.infoDict['imagedir'])
            self.Entropy.entropyTools.spawnFunction(
                        self.__fill_image_dir,
                        self.infoDict['merge_from'],
                        self.infoDict['imagedir']
                )

        # unpack xpak ?
        if etpConst['gentoo-compat']:
            if os.path.isdir(self.infoDict['xpakpath']):
                shutil.rmtree(self.infoDict['xpakpath'])
            try:
                os.rmdir(self.infoDict['xpakpath'])
            except OSError:
                pass

            # create data dir where we'll unpack the xpak
            os.makedirs(self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'],0755)
            #os.mkdir(self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'])
            xpakPath = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakfilename']

            if not self.infoDict['merge_from']:
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
            else:
                # link xpakdir to self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                tolink_dir = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                if os.path.isdir(tolink_dir):
                    shutil.rmtree(tolink_dir,True)
                # now link
                os.symlink(self.infoDict['xpakdir'],tolink_dir)

            # create fake portage ${D} linking it to imagedir
            portage_db_fakedir = os.path.join(
                                                self.infoDict['unpackdir'],
                                                "portage/"+self.infoDict['category'] + "/" + self.infoDict['name'] + "-" + self.infoDict['version']
                                            )

            os.makedirs(portage_db_fakedir,0755)
            # now link it to self.infoDict['imagedir']
            os.symlink(self.infoDict['imagedir'],os.path.join(portage_db_fakedir,"image"))

        return 0

    def __remove_package(self):

        # clear on-disk cache
        self.__clear_cache()

        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing package: "+str(self.infoDict['removeatom']))

        # remove from database
        if self.infoDict['removeidpackage'] != -1:
            self.Entropy.updateProgress(
                                    blue("Removing from Entropy: ")+red(self.infoDict['removeatom']),
                                    importance = 1,
                                    type = "info",
                                    header = red("   ## ")
                                )
            self.__remove_package_from_database()

        # Handle gentoo database
        if (etpConst['gentoo-compat']):
            gentooAtom = self.Entropy.entropyTools.remove_tag(self.infoDict['removeatom'])
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing from Portage: "+str(gentooAtom))
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
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Collision found during remove of "+etpConst['systemroot']+item+" - cannot overwrite")
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
                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_VERBOSE,"[remove] Protecting config file: "+etpConst['systemroot']+item)
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
        try:
            Spm = self.Entropy.Spm()
        except:
            return -1 # no Spm support ??

        portDbDir = Spm.get_vdb_path()
        removePath = portDbDir+atom
        try:
            shutil.rmtree(removePath,True)
        except:
            pass
        key = self.Entropy.entropyTools.dep_getkey(atom)
        othersInstalled = Spm.get_installed_atoms(key) #FIXME: really slow
        if othersInstalled == None:
            world_file = os.path.join(etpConst['systemroot'],'var/lib/portage/world')
            world_file_tmp = world_file+".entropy.tmp"
            if os.access(world_file,os.W_OK):
                new = open(world_file_tmp,"w")
                old = open(world_file,"r")
                line = old.readline()
                while line:
                    if line.find(key) == -1:
                        new.write(line)
                    line = old.readline()
                new.flush()
                new.close()
                old.close()
                shutil.move(world_file_tmp,world_file)
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

    def __clear_cache(self):
        self.Entropy.clear_dump_cache(etpCache['advisories'])
        self.Entropy.clear_dump_cache(etpCache['filter_satisfied_deps'])
        self.Entropy.clear_dump_cache(etpCache['depends_tree'])
        self.Entropy.clear_dump_cache(etpCache['check_package_update'])
        self.Entropy.clear_dump_cache(etpCache['dep_tree'])
        self.Entropy.clear_dump_cache(etpCache['dbMatch']+etpConst['clientdbid']+"/")
        self.Entropy.clear_dump_cache(etpCache['dbSearch']+etpConst['clientdbid']+"/")
        if self.infoDict['removeidpackage'] != -1:
            self.Entropy.clear_dump_cache(etpCache['dbInfo']+"/"+etpConst['clientdbid']+"/"+str(self.infoDict['removeidpackage'])+"/")

        self.__update_available_cache()
        try:
            self.__update_world_cache()
        except:
            self.Entropy.clear_dump_cache(etpCache['world_update'])

    def __update_world_cache(self):
        if self.Entropy.xcache and (self.action in ("install","remove",)):
            wc_dir = os.path.dirname(os.path.join(etpConst['dumpstoragedir'],etpCache['world_update']))
            wc_filename = os.path.basename(etpCache['world_update'])
            wc_cache_files = [os.path.join(wc_dir,x) for x in os.listdir(wc_dir) if x.startswith(wc_filename)]
            for cache_file in wc_cache_files:

                try:
                    data = self.Entropy.dumpTools.loadobj(cache_file, completePath = True)
                    (update, remove, fine) = data['r']
                    empty_deps = data['empty_deps']
                except:
                    self.Entropy.clear_dump_cache(etpCache['world_update'])
                    return

                if empty_deps:
                    continue

                if self.action == "install":
                    if self.matched_atom in update:
                        update.remove(self.matched_atom)
                        self.Entropy.dumpTools.dumpobj(cache_file, {'r':(update, remove, fine),'empty_deps': empty_deps}, completePath = True)
                else:
                    key, slot = self.Entropy.clientDbconn.retrieveKeySlot(self.infoDict['removeidpackage'])
                    matches = self.Entropy.atomMatch(key, matchSlot = slot, multiMatch = True, multiRepo = True)
                    if matches[1] != 0:
                        # hell why! better to rip all off
                        self.Entropy.clear_dump_cache(etpCache['world_update'])
                        return
                    taint = False
                    for match in matches[0]:
                        if match in update:
                            taint = True
                            update.remove(match)
                        if match in remove:
                            taint = True
                            remove.remove(match)
                    if taint:
                        self.Entropy.dumpTools.dumpobj(cache_file, {'r':(update, remove, fine),'empty_deps': empty_deps}, completePath = True)

        elif (not self.Entropy.xcache) or (self.action in ("install",)):
            self.Entropy.clear_dump_cache(etpCache['world_update'])

    def __update_available_cache(self):

        # update world available cache
        if self.Entropy.xcache and (self.action in ("remove","install")):
            c_hash = self.Entropy.get_available_packages_chash(etpConst['branch'])
            disk_cache = self.Entropy.dumpTools.loadobj(etpCache['world_available'])
            if disk_cache != None:
                try:
                    if disk_cache['chash'] == c_hash:

                        # remove and old install
                        if self.infoDict['removeidpackage'] != -1:
                            key = self.Entropy.entropyTools.dep_getkey(self.infoDict['removeatom'])
                            slot = self.infoDict['slot']
                            matches = self.Entropy.atomMatch(key, matchSlot = slot, multiRepo = True, multiMatch = True)
                            if matches[1] == 0:
                                disk_cache['available'].update(matches[0])

                        # install, doing here because matches[0] could contain self.matched_atoms
                        if self.matched_atom in disk_cache['available']:
                            disk_cache['available'].remove(self.matched_atom)

                        self.Entropy.dumpTools.dumpobj(etpCache['world_available'],disk_cache)

                except KeyError:
                    try:
                        self.Entropy.dumpTools.dumpobj(etpCache['world_available'],{})
                    except IOError:
                        pass
        elif not self.Entropy.xcache:
            self.Entropy.clear_dump_cache(etpCache['world_available'])


    '''
    @description: install unpacked files, update database and also update gentoo db if requested
    @output: 0 = all fine, >0 = error!
    '''
    def __install_package(self):

        # clear on-disk cache
        self.__clear_cache()

        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Installing package: "+str(self.infoDict['atom']))

        # copy files over - install
        rc = self.__move_image_to_system()
        if rc != 0:
            return rc

        # inject into database
        self.Entropy.updateProgress(
                                blue("Updating database: ")+red(self.infoDict['atom']),
                                importance = 1,
                                type = "info",
                                header = red("   ## ")
                            )
        newidpackage = self._install_package_into_database()
        #newidpackage = self.Entropy.entropyTools.spawnFunction( self._install_package_into_database ) it hangs on live systems!

        # remove old files and gentoo stuff
        if (self.infoDict['removeidpackage'] != -1):
            # doing a diff removal
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Remove old package: "+str(self.infoDict['removeatom']))
            self.infoDict['removeidpackage'] = -1 # disabling database removal

            compatstring = ''
            if etpConst['gentoo-compat']:
                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing Entropy and Gentoo database entry for "+str(self.infoDict['removeatom']))
                compatstring = " ## w/Gentoo compatibility"
            else:
                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing Entropy (only) database entry for "+str(self.infoDict['removeatom']))

            self.Entropy.updateProgress(
                                    blue("Cleaning old package files...")+compatstring,
                                    importance = 1,
                                    type = "info",
                                    header = red("   ## ")
                                )
            self.__remove_package()

        rc = 0
        if (etpConst['gentoo-compat']):
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Installing new Gentoo database entry: "+str(self.infoDict['atom']))
            rc = self._install_package_into_gentoo_database(newidpackage)

        return rc

    '''
    @description: inject the database information into the Gentoo database
    @output: 0 = all fine, !=0 = error!
    '''
    def _install_package_into_gentoo_database(self, newidpackage):

        # handle gentoo-compat
        try:
            Spm = self.Entropy.Spm()
        except:
            return -1 # no Portage support
        portDbDir = Spm.get_vdb_path()
        if os.path.isdir(portDbDir):
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
                    atomslot = Spm.get_package_slot(atom)
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

            # we now install it
            if ((self.infoDict['xpakstatus'] != None) and \
                    os.path.isdir( self.infoDict['xpakpath'] + "/" + etpConst['entropyxpakdatarelativepath'])) or \
                    self.infoDict['merge_from']:

                if self.infoDict['merge_from']:
                    copypath = self.infoDict['xpakdir']
                    if not os.path.isdir(copypath):
                        return 0
                else:
                    copypath = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']

                if not os.path.isdir(portDbDir+self.infoDict['category']):
                    os.makedirs(portDbDir+self.infoDict['category'],0755)
                destination = portDbDir+self.infoDict['category']+"/"+self.infoDict['name']+"-"+self.infoDict['version']
                if os.path.isdir(destination):
                    shutil.rmtree(destination)

                shutil.copytree(copypath,destination)

                # test if /var/cache/edb/counter is fine
                if os.path.isfile(etpConst['edbcounter']):
                    try:
                        f = open(etpConst['edbcounter'],"r")
                        counter = int(f.readline().strip())
                        f.close()
                    except:
                        # need file recreation, parse gentoo tree
                        counter = Spm.refill_counter()
                else:
                    counter = Spm.refill_counter()

                # write new counter to file
                if os.path.isdir(destination):
                    counter += 1
                    f = open(destination+"/"+etpConst['spm']['xpak_entries']['counter'],"w")
                    f.write(str(counter))
                    f.flush()
                    f.close()
                    f = open(etpConst['edbcounter'],"w")
                    f.write(str(counter))
                    f.flush()
                    f.close()
                    # update counter inside clientDatabase
                    self.Entropy.clientDbconn.insertCounter(newidpackage,counter)
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
    def _install_package_into_database(self):

        # fetch info
        dbconn = self.Entropy.openRepositoryDatabase(self.infoDict['repository'])
        data = dbconn.getPackageData(self.infoDict['idpackage'])
        # open client db
        # always set data['injected'] to False
        # installed packages database SHOULD never have more than one package for scope (key+slot)
        data['injected'] = False
        data['counter'] = -1 # gentoo counter will be set in self._install_package_into_gentoo_database()

        idpk, rev, x = self.Entropy.clientDbconn.handlePackage(etpData = data, forcedRevision = data['revision'])
        del data

        # update datecreation
        ctime = self.Entropy.entropyTools.getCurrentUnixTime()
        self.Entropy.clientDbconn.setDateCreation(idpk, str(ctime))

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

    def __fill_image_dir(self, mergeFrom, imageDir):

        dbconn = self.Entropy.openRepositoryDatabase(self.infoDict['repository'])
        content = dbconn.retrieveContent(self.infoDict['idpackage'], extended = True)
        package_content = {}
        for cdata in content:
            package_content[cdata[0]] = cdata[1]
        del content
        contents = [x for x in package_content]
        contents.sort()

        # collect files
        for path in contents:
            # convert back to filesystem str
            encoded_path = path
            path = os.path.join(mergeFrom,encoded_path[1:])
            topath = os.path.join(imageDir,encoded_path[1:])
            path = path.encode('raw_unicode_escape')
            topath = topath.encode('raw_unicode_escape')

            try:
                exist = os.lstat(path)
            except OSError:
                continue # skip file
            ftype = package_content[encoded_path]
            if str(ftype) == '0': ftype = 'dir' # force match below, '0' means databases without ftype
            if 'dir' == ftype and \
                not stat.S_ISDIR(exist.st_mode) and \
                os.path.isdir(path): # workaround for directory symlink issues
                path = os.path.realpath(path)

            copystat = False
            # if our directory is a symlink instead, then copy the symlink
            if os.path.islink(path):
                tolink = os.readlink(path)
                if os.path.islink(topath):
                    os.remove(topath)
                os.symlink(tolink,topath)
            elif os.path.isdir(path):
                if not os.path.isdir(topath):
                    os.makedirs(topath)
                    copystat = True
            elif os.path.isfile(path):
                if os.path.isfile(topath):
                    os.remove(topath) # should never happen
                shutil.copy2(path,topath)
                copystat = True

            if copystat:
                user = os.stat(path)[4]
                group = os.stat(path)[5]
                os.chown(topath,user,group)
                shutil.copystat(path,topath)


    def __move_image_to_system(self):

        # load CONFIG_PROTECT and its mask
        protect = etpRepositories[self.infoDict['repository']]['configprotect']
        mask = etpRepositories[self.infoDict['repository']]['configprotectmask']

        # setup imageDir properly
        imageDir = self.infoDict['imagedir']
        # XXX Python 2.4 workaround
        if sys.version[:3] == "2.4":
            imageDir = imageDir.encode('raw_unicode_escape')
        # XXX Python 2.4 workaround

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
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"WARNING!!! "+rootdir+" is a file when it should be a directory !! Removing in 20 seconds...")
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
                    try:
                        # we should really force a simple mkdir first of all
                        os.mkdir(rootdir)
                    except OSError:
                        os.makedirs(rootdir)

                if not os.path.islink(rootdir) and os.access(rootdir,os.W_OK):
                    # symlink don't need permissions, also until os.walk ends they might be broken
                    # XXX also, added os.access() check because there might be directories/files unwriteable
                    # what to do otherwise?
                    user = os.stat(imagepathDir)[4]
                    group = os.stat(imagepathDir)[5]
                    os.chown(rootdir,user,group)
                    shutil.copystat(imagepathDir,rootdir)

            for item in files:

                fromfile = currentdir+"/"+item
                tofile = etpConst['systemroot']+fromfile[len(imageDir):]
                fromfile_encoded = fromfile
                #tofile_encoded = tofile
                # redecode to bytestring

                # XXX Python 2.4 bug workaround
                # If Python 2.4, .encode fails
                if sys.version[:3] != "2.4":
                    fromfile = fromfile.encode('raw_unicode_escape')
                    tofile = tofile.encode('raw_unicode_escape')
                # XXX Python 2.4 bug workaround

                if etpConst['collisionprotect'] > 1:
                    todbfile = fromfile[len(imageDir):]
                    if self.Entropy.clientDbconn.isFileAvailable(todbfile):
                        self.Entropy.updateProgress(
                                                red("Collision found during install for ")+tofile+" - cannot overwrite",
                                                importance = 1,
                                                type = "warning",
                                                header = darkred("   ## ")
                                            )
                        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"WARNING!!! Collision found during install for "+tofile+" - cannot overwrite")
                        continue

                # -- CONFIGURATION FILE PROTECTION --
                protected = False
                tofile_before_protect = tofile

                try:
                    for x in protect:
                        x = x.encode('raw_unicode_escape')
                        if tofile.startswith(x):
                            protected = True
                            break
                    if (protected): # check if perhaps, file is masked, so unprotected
                        for x in mask:
                            x = x.encode('raw_unicode_escape')
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
                                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Protecting config file: "+oldtofile)
                                self.Entropy.updateProgress(
                                                        red("Protecting config file: ")+oldtofile,
                                                        importance = 1,
                                                        type = "warning",
                                                        header = darkred("   ## ")
                                                    )
                        else:
                            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Skipping config file installation, as stated in equo.conf: "+tofile)
                            self.Entropy.updateProgress(
                                                    red("Skipping file installation: ")+tofile,
                                                    importance = 1,
                                                    type = "warning",
                                                    header = darkred("   ## ")
                                                )
                            continue

                    # -- CONFIGURATION FILE PROTECTION --

                except Exception, e:
                    protected = False # safely revert to false
                    tofile = tofile_before_protect
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
                        try: # try to cope...
                            os.remove(tofile)
                        except:
                            pass

                    # if our file is a dir on the live system
                    if os.path.isdir(tofile) and not os.path.islink(tofile): # really weird...!
                        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"WARNING!!! "+tofile+" is a directory when it should be a file !! Removing in 20 seconds...")
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
                    # XXX
                    # XXX moving file using the raw format like portage does
                    # XXX
                    shutil.move(fromfile_encoded,tofile)

                except IOError, e:
                    if e.errno == 2:
                        # better to pass away, sometimes gentoo packages are fucked up and contain broken things
                        pass
                    else:
                        rc = os.system("mv "+fromfile+" "+tofile)
                        if (rc != 0):
                            return 4
                if (protected):
                    # add to disk cache
                    oldquiet = etpUi['quiet']
                    etpUi['quiet'] = True
                    self.Entropy.FileUpdates.add_to_cache(tofile)
                    etpUi['quiet'] = oldquiet

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
        if rc != 0:
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

        if not self.infoDict['merge_from']:
            self.Entropy.updateProgress(
                                                blue("Unpacking package: ")+red(os.path.basename(self.infoDict['download'])),
                                                importance = 1,
                                                type = "info",
                                                header = red("   ## ")
                                        )
        else:
            self.Entropy.updateProgress(
                                                blue("Merging package: ")+red(os.path.basename(self.infoDict['atom'])),
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
                                            blue("Removing data: ")+red(self.infoDict['removeatom'])+compatstring,
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
                                        blue('Cleaning: ')+red(self.infoDict['atom']),
                                        importance = 1,
                                        type = "info",
                                        header = red("   ## ")
                                    )
        tdict = {}
        tdict['unpackdir'] = self.infoDict['unpackdir']
        task = self.Entropy.entropyTools.parallelTask(self.__cleanup_package, tdict)
        task.parallel_wait()
        task.start()
        # we don't care if cleanupPackage fails since it's not critical
        return 0

    def messages_step(self):
        self.error_on_not_prepared()
        # get messages
        if self.infoDict['messages']:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Message from "+self.infoDict['atom']+" :")
            self.Entropy.updateProgress(
                                                darkgreen("Gentoo ebuild messages:"),
                                                importance = 0,
                                                type = "warning",
                                                header = brown("   ## ")
                                        )
        for msg in self.infoDict['messages']:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,msg)
            self.Entropy.updateProgress(
                                                msg,
                                                importance = 0,
                                                type = "warning",
                                                header = brown("   ## ")
                                        )
        if self.infoDict['messages']:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"End message.")

    def postinstall_step(self):
        self.error_on_not_prepared()
        pkgdata = self.infoDict['triggers'].get('install')
        if pkgdata:
            Trigger = self.Entropy.Triggers('postinstall',pkgdata)
            Trigger.prepare()
            Trigger.run()
            Trigger.kill()
            del Trigger
        del pkgdata
        return 0

    def preinstall_step(self):
        self.error_on_not_prepared()
        pkgdata = self.infoDict['triggers'].get('install')
        if pkgdata:

            Trigger = self.Entropy.Triggers('preinstall',pkgdata)
            Trigger.prepare()
            if (self.infoDict.get("diffremoval") != None): # diffremoval is true only when the remove action is triggered by installPackages()
                if self.infoDict['diffremoval']:
                    remdata = self.infoDict['triggers'].get('remove')
                    if remdata:
                        rTrigger = self.Entropy.Triggers('preremove',remdata)
                        rTrigger.prepare()
                        Trigger.triggers = Trigger.triggers - rTrigger.triggers
                        rTrigger.kill()
                        del rTrigger
                    del remdata
            Trigger.run()
            Trigger.kill()
            del Trigger

        del pkgdata
        return 0

    def preremove_step(self):
        self.error_on_not_prepared()
        remdata = self.infoDict['triggers'].get('remove')
        if remdata:
            Trigger = self.Entropy.Triggers('preremove',remdata)
            Trigger.prepare()
            Trigger.run()
            Trigger.kill()
            del Trigger
        del remdata
        return 0

    def postremove_step(self):
        self.error_on_not_prepared()
        remdata = self.infoDict['triggers'].get('remove')
        if remdata:

            Trigger = self.Entropy.Triggers('postremove',remdata)
            Trigger.prepare()
            if self.infoDict['diffremoval'] and (self.infoDict.get("atom") != None):
                # diffremoval is true only when the remove action is triggered by installPackages()
                pkgdata = self.infoDict['triggers'].get('install')
                if pkgdata:
                    iTrigger = self.Entropy.Triggers('postinstall',pkgdata)
                    iTrigger.prepare()
                    Trigger.triggers = Trigger.triggers - iTrigger.triggers
                    iTrigger.kill()
                    del iTrigger
                del pkgdata
            Trigger.run()
            Trigger.kill()
            del Trigger

        del remdata
        return 0

    def removeconflict_step(self):

        for idpackage in self.infoDict['conflicts']:
            if not self.Entropy.clientDbconn.isIDPackageAvailable(idpackage):
                continue
            Package = self.Entropy.Package()
            Package.prepare((idpackage,),"remove", self.infoDict['remove_metaopts'])
            rc = Package.run(xterm_header = self.xterm_title)
            Package.kill()
            if rc != 0:
                return rc

        return 0

    def run_stepper(self, xterm_header):
        if xterm_header == None:
            xterm_header = ""

        rc = 0
        for step in self.infoDict['steps']:
            self.xterm_title = xterm_header

            if step == "fetch":
                self.xterm_title += ' Fetching: '+os.path.basename(self.infoDict['download'])
                self.Entropy.setTitle(self.xterm_title)
                rc = self.fetch_step()

            elif step == "checksum":
                self.xterm_title += ' Verifying: '+os.path.basename(self.infoDict['download'])
                self.Entropy.setTitle(self.xterm_title)
                rc = self.checksum_step()

            elif step == "unpack":
                if not self.infoDict['merge_from']:
                    self.xterm_title += ' Unpacking: '+os.path.basename(self.infoDict['download'])
                else:
                    self.xterm_title += ' Merging: '+os.path.basename(self.infoDict['atom'])
                self.Entropy.setTitle(self.xterm_title)
                rc = self.unpack_step()

            elif step == "remove_conflicts":
                rc = self.removeconflict_step()

            elif step == "install":
                self.xterm_title += ' Installing: '+self.infoDict['atom']
                self.Entropy.setTitle(self.xterm_title)
                rc = self.install_step()

            elif step == "remove":
                self.xterm_title += ' Removing: '+self.infoDict['removeatom']
                self.Entropy.setTitle(self.xterm_title)
                rc = self.remove_step()

            elif step == "showmessages":
                rc = self.messages_step()

            elif step == "cleanup":
                self.xterm_title += ' Cleaning: '+self.infoDict['atom']
                self.Entropy.setTitle(self.xterm_title)
                rc = self.cleanup_step()

            elif step == "postinstall":
                self.xterm_title += ' Postinstall: '+self.infoDict['atom']
                self.Entropy.setTitle(self.xterm_title)
                rc = self.postinstall_step()

            elif step == "preinstall":
                self.xterm_title += ' Preinstall: '+self.infoDict['atom']
                self.Entropy.setTitle(self.xterm_title)
                rc = self.preinstall_step()

            elif step == "preremove":
                self.xterm_title += ' Preremove: '+self.infoDict['removeatom']
                self.Entropy.setTitle(self.xterm_title)
                rc = self.preremove_step()

            elif step == "postremove":
                self.xterm_title += ' Postremove: '+self.infoDict['removeatom']
                self.Entropy.setTitle(self.xterm_title)
                rc = self.postremove_step()

            if rc != 0:
                break

        return rc


    '''
        @description: execute the requested steps
        @input xterm_header: purely optional
    '''
    def run(self, xterm_header = None):
        self.error_on_not_prepared()

        gave_up = self.Entropy.sync_loop_check(self.Entropy._resources_run_check_lock)
        if gave_up:
            return 20

        # lock
        self.Entropy._resources_run_create_lock()

        try:
            rc = self.run_stepper(xterm_header)
        except:
            self.Entropy._resources_run_remove_lock()
            raise

        # remove lock
        self.Entropy._resources_run_remove_lock()

        if rc != 0:
            self.Entropy.updateProgress(
                                                blue("An error occured. Action aborted."),
                                                importance = 2,
                                                type = "error",
                                                header = darkred("   ## ")
                                        )
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

        # clear masking reasons
        maskingReasonsStorage.clear()

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
        self.infoDict['slot'] = self.Entropy.clientDbconn.retrieveSlot(idpackage)
        self.infoDict['removeidpackage'] = idpackage
        self.infoDict['diffremoval'] = False
        removeConfig = False
        if self.metaopts.has_key('removeconfig'):
            removeConfig = self.metaopts.get('removeconfig')
        self.infoDict['removeconfig'] = removeConfig
        self.infoDict['removecontent'] = self.Entropy.clientDbconn.retrieveContent(idpackage)
        self.infoDict['triggers']['remove'] = self.Entropy.clientDbconn.getTriggerInfo(idpackage)
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
        self.infoDict['accept_license'] = dbconn.retrieveLicensedataKeys(idpackage)
        self.infoDict['conflicts'] = self.Entropy.get_match_conflicts(self.matched_atom)

        # fill action queue
        self.infoDict['removeidpackage'] = -1
        removeConfig = False
        if self.metaopts.has_key('removeconfig'):
            removeConfig = self.metaopts.get('removeconfig')

        self.infoDict['remove_metaopts'] = {
            'removeconfig': True,
        }
        if self.metaopts.has_key('remove_metaopts'):
            self.infoDict['remove_metaopts'] = self.metaopts.get('remove_metaopts')

        self.infoDict['merge_from'] = None
        mf = self.metaopts.get('merge_from')
        if mf != None:
            self.infoDict['merge_from'] = unicode(mf)
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
        if self.infoDict['repository'].endswith(etpConst['packagesext']):
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
            self.infoDict['xpakpath'] = etpConst['entropyunpackdir']+"/"+self.infoDict['download']+"/"+etpConst['entropyxpakrelativepath']
            if not self.infoDict['merge_from']:
                self.infoDict['xpakstatus'] = None
                self.infoDict['xpakdir'] = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
            else:
                self.infoDict['xpakstatus'] = True
                portdbdir = 'var/db/pkg' # XXX hard coded ?
                portdbdir = os.path.join(self.infoDict['merge_from'],portdbdir)
                portdbdir = os.path.join(portdbdir,self.infoDict['category'])
                portdbdir = os.path.join(portdbdir,self.infoDict['name']+"-"+self.infoDict['version'])
                self.infoDict['xpakdir'] = portdbdir

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
        if self.infoDict['removeidpackage'] != -1:
            # is it still available?
            if self.Entropy.clientDbconn.isIDPackageAvailable(self.infoDict['removeidpackage']):
                self.infoDict['diffremoval'] = True
                self.infoDict['removeatom'] = self.Entropy.clientDbconn.retrieveAtom(self.infoDict['removeidpackage'])
                self.infoDict['removecontent'] = self.Entropy.clientDbconn.contentDiff(self.infoDict['removeidpackage'], dbconn, idpackage)
                self.infoDict['triggers']['remove'] = self.Entropy.clientDbconn.getTriggerInfo(self.infoDict['removeidpackage'])
                self.infoDict['triggers']['remove']['removecontent'] = self.infoDict['removecontent']
            else:
                self.infoDict['removeidpackage'] = -1

        # set steps
        self.infoDict['steps'] = []
        if self.infoDict['conflicts']:
            self.infoDict['steps'].append("remove_conflicts")
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

        self.infoDict['triggers']['install'] = dbconn.getTriggerInfo(idpackage)
        self.infoDict['triggers']['install']['accept_license'] = self.infoDict['accept_license']
        self.infoDict['triggers']['install']['unpackdir'] = self.infoDict['unpackdir']
        if etpConst['gentoo-compat']:
            #self.infoDict['triggers']['install']['xpakpath'] = self.infoDict['xpakpath']
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
        if not repository.endswith(etpConst['packagesext']):
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
            if not isinstance(EquoInstance,EquoInterface):
                raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid Entropy Instance is needed")
            self.Entropy = EquoInstance

        self.scandata = None

    def merge_file(self, key):
        self.scanfs(dcache = True)
        self.do_backup(key)
        if os.access(etpConst['systemroot'] + self.scandata[key]['source'], os.R_OK):
            shutil.move(etpConst['systemroot'] + self.scandata[key]['source'], etpConst['systemroot'] + self.scandata[key]['destination'])
        self.remove_from_cache(key)

    def remove_file(self, key):
        self.scanfs(dcache = True)
        try:
            os.remove(etpConst['systemroot'] + self.scandata[key]['source'])
        except OSError:
            pass
        self.remove_from_cache(key)

    def do_backup(self, key):
        self.scanfs(dcache = True)
        if etpConst['filesbackup'] and os.path.isfile(etpConst['systemroot']+self.scandata[key]['destination']):
            bcount = 0
            backupfile = etpConst['systemroot'] + os.path.dirname(self.scandata[key]['destination']) + "/._equo_backup." + unicode(bcount) + "_" + os.path.basename(self.scandata[key]['destination'])
            while os.path.lexists(backupfile):
                bcount += 1
                backupfile = etpConst['systemroot'] + os.path.dirname(self.scandata[key]['destination']) + "/._equo_backup." + unicode(bcount) + "_" + os.path.basename(self.scandata[key]['destination'])
            try:
                shutil.copy2(etpConst['systemroot'] + self.scandata[key]['destination'],backupfile)
            except IOError:
                pass

    '''
    @description: scan for files that need to be merged
    @output: dictionary using filename as key
    '''
    def scanfs(self, dcache = True):

        if dcache:

            if self.scandata != None:
                return self.scandata

            # can we load cache?
            try:
                z = self.load_cache()
                if z != None:
                    self.scandata = z.copy()
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

                    filepath = os.path.join(currentdir,item)
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
                            self.Entropy.updateProgress(
                                                    darkred("Automerging file: %s") % ( darkgreen(etpConst['systemroot']+mydict['source']) ),
                                                    importance = 0,
                                                    type = "info"
                                                )
                            if os.path.isfile(etpConst['systemroot']+mydict['source']):
                                try:
                                    shutil.move(etpConst['systemroot']+mydict['source'],etpConst['systemroot']+mydict['destination'])
                                except IOError:
                                    self.Entropy.updateProgress(
                                                    darkred("I/O Error :: Cannot automerge file: %s") % ( darkgreen(etpConst['systemroot']+mydict['source']) ),
                                                    importance = 1,
                                                    type = "warning"
                                                )
                            continue
                        else:
                            counter += 1
                            scandata[counter] = mydict.copy()

                        try:
                            self.Entropy.updateProgress(
                                            "("+blue(str(counter))+") "+red(" file: ")+os.path.dirname(filepath)+"/"+os.path.basename(filepath)[10:],
                                            importance = 1,
                                            type = "info"
                                        )
                        except:
                            pass # possible encoding issues
        # store data
        try:
            self.Entropy.dumpTools.dumpobj(etpCache['configfiles'],scandata)
        except IOError:
            pass
        self.scandata = scandata.copy()
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
        self.scanfs(dcache = True)
        keys = self.scandata.keys()
        try:
            for key in keys:
                if self.scandata[key]['source'] == filepath[len(etpConst['systemroot']):]:
                    del self.scandata[key]
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
        self.scandata[index] = mydata.copy()
        self.Entropy.dumpTools.dumpobj(etpCache['configfiles'],self.scandata)

    def remove_from_cache(self, key):
        self.scanfs(dcache = True)
        try:
            del self.scandata[key]
        except:
            pass
        self.Entropy.dumpTools.dumpobj(etpCache['configfiles'],self.scandata)
        return self.scandata

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

    def __init__(self, EquoInstance, reponames = [], forceUpdate = False, noEquoCheck = False, fetchSecurity = True):

        if not isinstance(EquoInstance,EquoInterface):
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid Entropy Instance is needed")

        self.Entropy = EquoInstance
        self.reponames = reponames
        self.forceUpdate = forceUpdate
        self.syncErrors = False
        self.dbupdated = False
        self.newEquo = False
        self.fetchSecurity = fetchSecurity
        self.noEquoCheck = noEquoCheck
        self.alreadyUpdated = 0
        self.notAvailable = 0
        self.reset_dbformat_eapi()

        # check etpRepositories
        if not etpRepositories:
            raise exceptionTools.MissingParameter("MissingParameter: no repositories specified in %s" % (etpConst['repositoriesconf'],))

        # Test network connectivity
        conntest = self.Entropy.entropyTools.get_remote_data(etpConst['conntestlink'])
        if not conntest:
            raise exceptionTools.OnlineMirrorError("OnlineMirrorError: Cannot connect to %s" % (etpConst['conntestlink'],))

        if not self.reponames:
            for x in etpRepositories:
                self.reponames.append(x)

    def reset_dbformat_eapi(self):
        self.dbformat_eapi = 2
        # FIXME, find a way to do that without needing sqlite3 exec.
        if not os.access("/usr/bin/sqlite3",os.X_OK) or self.Entropy.entropyTools.islive():
            self.dbformat_eapi = 1
        else:
            import subprocess
            rc = subprocess.call("/usr/bin/sqlite3 -version &> /dev/null", shell = True)
            if rc != 0: self.dbformat_eapi = 1


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
            os.makedirs(etpRepositories[repo]['dbpath'],0775)

        const_setup_perms(etpConst['etpdatabaseclientdir'],etpConst['entropygid'])

    def __construct_paths(self, item, repo, cmethod):

        if item not in ("db","rev","ck","lock","mask","dbdump","dbdumpck","lic_whitelist"):
            raise exceptionTools.InvalidData("InvalidData: supported db, rev, ck, lock")

        if item == "db":
            if cmethod == None:
                raise exceptionTools.InvalidData("InvalidData: for db, cmethod can't be None")
            url = etpRepositories[repo]['database'] + "/" + etpConst[cmethod[2]]
            filepath = etpRepositories[repo]['dbpath'] + "/" + etpConst[cmethod[2]]
        elif item == "dbdump":
            if cmethod == None:
                raise exceptionTools.InvalidData("InvalidData: for db, cmethod can't be None")
            url = etpRepositories[repo]['database'] +   "/" + etpConst[cmethod[3]]
            filepath = etpRepositories[repo]['dbpath'] + "/" + etpConst[cmethod[3]]
        elif item == "rev":
            url = etpRepositories[repo]['database'] + "/" + etpConst['etpdatabaserevisionfile']
            filepath = etpRepositories[repo]['dbpath'] + "/" + etpConst['etpdatabaserevisionfile']
        elif item == "ck":
            url = etpRepositories[repo]['database'] + "/" + etpConst['etpdatabasehashfile']
            filepath = etpRepositories[repo]['dbpath'] + "/" + etpConst['etpdatabasehashfile']
        elif item == "dbdumpck":
            if cmethod == None:
                raise exceptionTools.InvalidData("InvalidData: for db, cmethod can't be None")
            url = etpRepositories[repo]['database'] + "/" + etpConst[cmethod[4]]
            filepath = etpRepositories[repo]['dbpath'] + "/" + etpConst[cmethod[4]]
        elif item == "mask":
            url = etpRepositories[repo]['database'] + "/" + etpConst['etpdatabasemaskfile']
            filepath = etpRepositories[repo]['dbpath'] + "/" + etpConst['etpdatabasemaskfile']
        elif item == "lic_whitelist":
            url = etpRepositories[repo]['database'] + "/" + etpConst['etpdatabaselicwhitelistfile']
            filepath = etpRepositories[repo]['dbpath'] + "/" + etpConst['etpdatabaselicwhitelistfile']
        elif item == "lock":
            url = etpRepositories[repo]['database']+"/"+etpConst['etpdatabasedownloadlockfile']
            filepath = "/dev/null"

        return url, filepath

    def __remove_repository_files(self, repo, cmethod):

        dbfilenameid = cmethod[2]
        self.__validate_repository_id(repo)

        if self.dbformat_eapi == 1:
            if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile']):
                os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'])
            if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst[dbfilenameid]):
                os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst[dbfilenameid])
            if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile']):
                os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'])
        elif self.dbformat_eapi == 2:
            if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+cmethod[4]):
                os.remove(etpRepositories[repo]['dbpath']+"/"+cmethod[4])
            if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[3]]):
                os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[3]])
            if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile']):
                os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'])
        else:
            raise exceptionTools.InvalidData('self.dbformat_eapi must be in (1,2)')

    def __unpack_downloaded_database(self, repo, cmethod):

        self.__validate_repository_id(repo)

        if self.dbformat_eapi == 1:
            path = eval("self.Entropy.entropyTools."+cmethod[1])(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[2]])
            os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[2]])
        elif self.dbformat_eapi == 2:
            path = eval("self.Entropy.entropyTools."+cmethod[1])(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[3]])
            os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[3]])
        else:
            raise exceptionTools.InvalidData('self.dbformat_eapi must be in (1,2)')

        self.Entropy.setup_default_file_perms(path)
        return path

    def __verify_database_checksum(self, repo, cmethod = None):

        self.__validate_repository_id(repo)

        if self.dbformat_eapi == 1:
            dbfile = etpConst['etpdatabasefile']
            try:
                f = open(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
                md5hash = f.readline().strip()
                md5hash = md5hash.split()[0]
                f.close()
            except:
                return -1
        elif self.dbformat_eapi == 2:
            dbfile = etpConst[cmethod[3]]
            try:
                f = open(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[4]],"r")
                md5hash = f.readline().strip()
                md5hash = md5hash.split()[0]
                f.close()
            except:
                return -1
        else:
            raise exceptionTools.InvalidData('self.dbformat_eapi must be in (1,2)')

        rc = self.Entropy.entropyTools.compareMd5(etpRepositories[repo]['dbpath']+"/"+dbfile,md5hash)
        return rc

    # @returns -1 if the file is not available
    # @returns int>0 if the revision has been retrieved
    def get_online_repository_revision(self, repo):

        self.__validate_repository_id(repo)

        url = etpRepositories[repo]['database']+"/"+etpConst['etpdatabaserevisionfile']
        status = self.Entropy.entropyTools.get_remote_data(url)
        if (status):
            status = status[0].strip()
            try:
                status = int(status)
            except ValueError:
                status = -1
            return status
        else:
            return -1

    def is_repository_updatable(self, repo):

        self.__validate_repository_id(repo)

        onlinestatus = self.get_online_repository_revision(repo)
        if (onlinestatus != -1):
            localstatus = self.Entropy.get_repository_revision(repo)
            if (localstatus == onlinestatus) and (not self.forceUpdate):
                return False
        else: # if == -1, means no repo found online
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
        self.Entropy.clear_dump_cache(etpCache['dbInfo']+"/"+repo+"/")
        self.Entropy.clear_dump_cache(etpCache['dbMatch']+repo+"/")
        self.Entropy.clear_dump_cache(etpCache['dbSearch']+repo+"/")

    # this function can be reimplemented
    def download_item(self, item, repo, cmethod = None):

        self.__validate_repository_id(repo)
        url, filepath = self.__construct_paths(item, repo, cmethod)

        # to avoid having permissions issues
        # it's better to remove the file before,
        # otherwise new permissions won't be written
        if os.path.isfile(filepath):
            os.remove(filepath)

        fetchConn = self.Entropy.urlFetcher(url, filepath, resume = False)
        fetchConn.progress = self.Entropy.progress

        rc = fetchConn.download()
        del fetchConn
        if rc in ("-1","-2","-3"):
            return False
        self.Entropy.setup_default_file_perms(filepath)
        return True

    def check_downloaded_database(self, repo, cmethod):
        dbfilename = etpConst['etpdatabasefile']
        if self.dbformat_eapi == 2:
            dbfilename = etpConst[cmethod[3]]
        # verify checksum
        self.Entropy.updateProgress(    red("Checking downloaded database ") + darkgreen(dbfilename)+red(" ..."),
                                        importance = 0,
                                        back = True,
                                        type = "info",
                                        header = "\t"
                        )
        db_status = self.__verify_database_checksum(repo, cmethod)
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
            return 1
        return 0


    def run_sync(self):
        self.dbupdated = False
        repocount = 0
        repolength = len(self.reponames)
        for repo in self.reponames:

            self.reset_dbformat_eapi()
            repocount += 1

            self.Entropy.updateProgress(    bold("%s") % ( etpRepositories[repo]['description'] ),
                                            importance = 2,
                                            type = "info",
                                            count = (repocount, repolength),
                                            header = blue("  # ")
                               )
            self.Entropy.updateProgress(    red("Database URL: ") + darkgreen(etpRepositories[repo]['database']),
                                            importance = 1,
                                            type = "info",
                                            header = blue("  # ")
                               )
            self.Entropy.updateProgress(    red("Database local path: ") + darkgreen(etpRepositories[repo]['dbpath']),
                                            importance = 0,
                                            type = "info",
                                            header = blue("  # ")
                               )

            # check if database is already updated to the latest revision
            update = self.is_repository_updatable(repo)
            if not update:
                self.Entropy.updateProgress(    bold("Attention: ") + red("database is already up to date."),
                                                importance = 1,
                                                type = "info",
                                                header = "\t"
                                )
                self.Entropy.cycleDone()
                self.alreadyUpdated += 1
                continue

            # get database lock
            unlocked = self.is_repository_unlocked(repo)
            if not unlocked:
                self.Entropy.updateProgress(    bold("Attention: ") + red("repository is being updated. Try again in a few minutes."),
                                                importance = 1,
                                                type = "warning",
                                                header = "\t"
                                )
                self.Entropy.cycleDone()
                continue

            # clear database interface cache belonging to this repository
            self.clear_repository_cache(repo)
            cmethod = self.__validate_compression_method(repo)
            self.__ensure_repository_path(repo)

            # starting to download
            self.Entropy.updateProgress(    red("Downloading repository database ..."),
                                            importance = 1,
                                            type = "info",
                                            header = "\t"
                            )
            down_status = False
            if self.dbformat_eapi == 2:
                down_status = self.download_item("dbdump", repo, cmethod)
            if not down_status: # fallback to old db
                self.dbformat_eapi = 1
                down_status = self.download_item("db", repo, cmethod)
            if not down_status:
                self.Entropy.updateProgress(    bold("Attention: ") + red("database does not exist online."),
                                                importance = 1,
                                                type = "warning",
                                                header = "\t"
                                )
                self.Entropy.cycleDone()
                self.notAvailable += 1
                continue

            hashfile = etpConst['etpdatabasehashfile']
            downitem = 'ck'
            if self.dbformat_eapi == 2: # EAPI = 2
                hashfile = etpConst[cmethod[4]]
                downitem = 'dbdumpck'

            # download checksum
            self.Entropy.updateProgress(    red("Downloading checksum ") + darkgreen(hashfile)+red(" ..."),
                                            importance = 0,
                                            type = "info",
                                            header = "\t"
                            )

            db_down_status = self.download_item(downitem, repo, cmethod)
            if not db_down_status:
                self.Entropy.updateProgress(    red("Cannot fetch checksum. Cannot verify database integrity !"),
                                                importance = 1,
                                                type = "warning",
                                                header = "\t"
                                )

            if self.dbformat_eapi == 2 and db_down_status:
                rc = self.check_downloaded_database(repo, cmethod)
                if rc != 0:
                    # delete all
                    self.__remove_repository_files(repo, cmethod)
                    self.syncErrors = True
                    self.Entropy.cycleDone()
                    continue

            file_to_unpack = etpConst['etpdatabasedump']
            if self.dbformat_eapi == 1:
                file_to_unpack = etpConst['etpdatabasefile']

            self.Entropy.updateProgress(    red("Unpacking database to ") + darkgreen(file_to_unpack)+red(" ..."),
                                            importance = 0,
                                            type = "info",
                                            header = "\t"
                                       )
            # unpack database
            self.__unpack_downloaded_database(repo, cmethod)

            if self.dbformat_eapi == 1 and db_down_status:
                rc = self.check_downloaded_database(repo, cmethod)
                if rc != 0:
                    # delete all
                    self.__remove_repository_files(repo, cmethod)
                    self.syncErrors = True
                    self.Entropy.cycleDone()
                    continue

            if self.dbformat_eapi == 2:
                # load the dump into database
                self.Entropy.updateProgress(    red("Injecting downloaded dump ") + darkgreen(etpConst[cmethod[3]])+red(", please wait ..."),
                                                importance = 0,
                                                type = "info",
                                                header = "\t"
                                )
                dbfile = os.path.join(etpRepositories[repo]['dbpath'],etpConst['etpdatabasefile'])
                dumpfile = os.path.join(etpRepositories[repo]['dbpath'],etpConst['etpdatabasedump'])
                if os.path.isfile(dbfile):
                    os.remove(dbfile)
                dbconn = self.Entropy.openGenericDatabase(dbfile, xcache = False, indexing_override = False)
                rc = dbconn.doDatabaseImport(dumpfile, dbfile)
                dbconn.closeDB()
                del dbconn
                # remove the dump
                os.remove(dumpfile)
                if rc != 0:
                    # delete all
                    self.__remove_repository_files(repo, cmethod)
                    self.syncErrors = True
                    self.Entropy.cycleDone()
                    continue
                if os.path.isfile(dbfile):
                    self.Entropy.setup_default_file_perms(dbfile)

            # database is going to be updated
            self.dbupdated = True

            # download packages.db.mask
            self.Entropy.updateProgress(    red("Downloading package mask ")+darkgreen(etpConst['etpdatabasemaskfile'])+red(" ..."),
                                            importance = 0,
                                            type = "info",
                                            header = "\t",
                                            back = True
                            )
            mask_status = self.download_item("mask", repo)
            if not mask_status:
                mask_message = red("No %s available. It's ok." % (etpConst['etpdatabasemaskfile'],))
            else:
                mask_message = red("Downloaded %s. Awesome :-)" % (etpConst['etpdatabasemaskfile'],))
            self.Entropy.updateProgress(    mask_message,
                                            importance = 0,
                                            type = "info",
                                            header = "\t"
                            )

            # download packages.db.lic_whitelist
            self.Entropy.updateProgress(    red("Downloading license whitelist ")+darkgreen(etpConst['etpdatabaselicwhitelistfile'])+red(" ..."),
                                            importance = 0,
                                            type = "info",
                                            header = "\t",
                                            back = True
                            )
            lic_status = self.download_item("lic_whitelist", repo)
            if not lic_status:
                lic_message = red("No %s available. It's ok." % (etpConst['etpdatabaselicwhitelistfile'],))
            else:
                lic_message = red("Downloaded %s. Cool :-)" % (etpConst['etpdatabaselicwhitelistfile'],))
            self.Entropy.updateProgress(    lic_message,
                                            importance = 0,
                                            type = "info",
                                            header = "\t"
                            )

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

                if self.Entropy.indexing:
                    self.Entropy.updateProgress(
                                                    red("Indexing Repository metadata ..."),
                                                    importance = 1,
                                                    type = "info",
                                                    header = "\t",
                                                    back = True
                                    )
                    dbconn = self.Entropy.openRepositoryDatabase(repo)
                    dbconn.createAllIndexes()
                    try: # client db can be absent
                        # XXX: once indexes will get close to final, remove this
                        self.Entropy.clientDbconn.dropAllIndexes()
                        self.Entropy.clientDbconn.createAllIndexes()
                    except:
                        pass
                # update revision in etpRepositories
                self.Entropy.update_repository_revision(repo)

            self.Entropy.cycleDone()

        # keep them closed
        self.Entropy.closeAllRepositoryDatabases()
        self.Entropy.validate_repositories()
        self.Entropy.closeAllRepositoryDatabases()

        # clean caches
        if self.dbupdated:
            self.Entropy.generate_cache(depcache = self.Entropy.xcache, configcache = False, client_purge = False)
            # update Security Advisories
            if self.fetchSecurity:
                try:
                    securityConn = self.Entropy.Security()
                    securityConn.fetch_advisories()
                except Exception, e:
                    self.Entropy.updateProgress(    red("Advisories fetch error: %s: %s.") % (str(Exception),str(e),),
                                                    importance = 1,
                                                    type = "warning",
                                                    header = darkred(" @@ ")
                                    )

        if self.syncErrors:
            self.Entropy.updateProgress(    red("Something bad happened. Please have a look."),
                                            importance = 1,
                                            type = "warning",
                                            header = darkred(" @@ ")
                            )
            self.syncErrors = True
            self.Entropy._resources_run_remove_lock()
            return 128

        rc = False
        if not self.noEquoCheck:
            try:
                rc = self.Entropy.check_equo_updates()
            except:
                pass

        if rc:
            self.newEquo = True
            self.Entropy.updateProgress(    blue("A new ")+bold("Equo")+blue(" release is available. Please ")+bold("install it")+blue(" before any other package."),
                                            importance = 1,
                                            type = "info",
                                            header = darkred(" !! ")
                            )
        return 0

    def sync(self):

        # close them
        self.Entropy.closeAllRepositoryDatabases()

        # let's dance!
        self.Entropy.updateProgress(    darkgreen("Repositories syncronization..."),
                                        importance = 2,
                                        type = "info",
                                        header = darkred(" @@ ")
                            )

        gave_up = self.Entropy.sync_loop_check(self.Entropy._resources_run_check_lock)
        if gave_up:
            return 3

        # lock
        self.Entropy._resources_run_create_lock()
        try:
            rc = self.run_sync()
        except:
            self.Entropy._resources_run_remove_lock()
            raise
        if rc: return rc

        # remove lock
        self.Entropy._resources_run_remove_lock()

        if (self.notAvailable >= len(self.reponames)):
            return 2
        elif (self.notAvailable > 0):
            return 1

        return 0

'''
   Entropy FTP interface
'''
class FtpInterface:

    # this must be run before calling the other functions
    def __init__(self, ftpuri, EntropyInterface):

        if not isinstance(EntropyInterface, (EquoInterface, TextInterface, ServerInterface)):
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid TextInterface based instance is needed")

        self.Entropy = EntropyInterface
        import entropyTools
        self.entropyTools = entropyTools
        import ftplib
        self.ftplib = ftplib
        import socket
        self.socket = socket

        self.oldprogress = 0.0

        # import FTP modules
        self.socket.setdefaulttimeout(60)

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
        self.socket.setdefaulttimeout(60)
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

    def updateProgress(self, buf_len):
        # get the buffer size
        self.mykByteCount += float(buf_len)/1024
        # create percentage
        myUploadPercentage = round((round(self.mykByteCount,1)/self.myFileSize)*100,1)
        currentprogress = myUploadPercentage
        myUploadSize = round(self.mykByteCount,1)
        if (currentprogress > self.oldprogress+0.5) and (myUploadPercentage < 100.1) and (myUploadSize <= self.myFileSize):
            myUploadPercentage = str(myUploadPercentage)+"%"

            # create text
            currentText = brown("    <-> Upload status: ")+green(str(myUploadSize))+"/"+red(str(self.myFileSize))+" kB "+brown("[")+str(myUploadPercentage)+brown("]")
            # print !
            print_info(currentText, back = True)
            # XXX too slow, reimplement self.updateProgress and do whatever you want
            #self.Entropy.updateProgress(currentText, importance = 0, type = "info", back = True)
            self.oldprogress = currentprogress

    def uploadFile(self,file,ascii = False):

        self.oldprogress = 0.0

        def uploadFileAndUpdateProgress(buf):
            self.updateProgress(len(buf))

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

    def downloadFile(self, filename, downloaddir, ascii = False):

        self.oldprogress = 0.0

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

        # look if the file exist
        if self.isFileAvailable(filename):
            self.mykByteCount = 0
            # get the file size
            self.myFileSize = self.getFileSizeCompat(filename)
            if (self.myFileSize):
                self.myFileSize = round(float(int(self.myFileSize))/1024,1)
                if (self.myFileSize == 0):
                    self.myFileSize = 1
            else:
                self.myFileSize = 0
            if (not ascii):
                f = open(downloaddir+"/"+filename,"wb")
                rc = self.ftpconn.retrbinary('RETR '+filename, downloadFileStoreAndUpdateProgress, 1024)
            else:
                f = open(downloaddir+"/"+filename,"w")
                rc = self.ftpconn.retrlines('RETR '+filename, f.write)
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


class urlFetcher:

    def __init__(self, url, pathToSave, checksum = True, showSpeed = True, resume = True):

        self.url = url
        self.resume = resume
        self.url = self.encodeUrl(self.url)
        self.pathToSave = pathToSave
        self.checksum = checksum
        self.showSpeed = showSpeed
        self.initVars()
        import entropyTools
        import socket
        self.entropyTools = entropyTools
        self.socket = socket
        self.progress = None

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
        import urllib
        url = os.path.join(os.path.dirname(url),urllib.quote(os.path.basename(url)))
        return url

    def initVars(self):
        self.resumed = False
        self.bufferSize = 8192
        self.status = None
        self.remotefile = None
        self.downloadedsize = 0
        self.average = 0
        self.remotesize = 0
        self.oldaverage = 0.0
        # transfer status data
        self.startingposition = 0
        self.datatransfer = 0
        self.time_remaining = "(infinite)"
        self.elapsed = 0.0
        self.updatestep = 0.2
        self.speedlimit = etpConst['downloadspeedlimit'] # kbytes/sec
        self.transferpollingtime = float(1)/4

    def download(self):
        self.initVars()
        self.speedUpdater = self.entropyTools.TimeScheduled(
                    self.updateSpeedInfo,
                    self.transferpollingtime
        )
        self.speedUpdater.setName("download::"+self.url+str(random.random())) # set unique ID to thread, hopefully
        self.speedUpdater.start()

        # set timeout
        self.socket.setdefaulttimeout(20)

        # get file size if available
        try:
            self.remotefile = urllib2.urlopen(self.url)
        except KeyboardInterrupt:
            self.close()
            raise
        except:
            self.close()
            self.status = "-3"
            return self.status

        try:
            self.remotesize = int(self.remotefile.headers.get("content-length"))
            self.remotefile.close()
        except KeyboardInterrupt:
            self.close()
            raise
        except:
            pass

        # handle user stupidity
        try:
            request = self.url
            if ((self.startingposition > 0) and (self.remotesize > 0)) and (self.startingposition < self.remotesize):
                try:
                    request = urllib2.Request(self.url, headers = { "Range" : "bytes=" + str(self.startingposition) + "-" + str(self.remotesize) })
                except KeyboardInterrupt:
                    self.close()
                    raise
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
            try:
                rsx = self.remotefile.read(self.bufferSize)
            except KeyboardInterrupt:
                self.close()
                raise
            except:
                # python 2.4 timeouts go here
                self.close()
                self.status = "-3"
                return self.status
            self.commitData(rsx)
            if self.showSpeed:
                self.updateProgress()
                self.oldaverage = self.average
            if self.speedlimit:
                while self.datatransfer > self.speedlimit*1024:
                    time.sleep(0.1)
                    if self.showSpeed:
                        self.updateProgress()
                        self.oldaverage = self.average

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

    def updateProgress(self):

        currentText = darkred("    Fetch: ")+darkgreen(str(round(float(self.downloadedsize)/1024,1)))+"/"+red(str(round(self.remotesize,1))) + " kB"
        # create progress bar
        barsize = 10
        bartext = "["
        curbarsize = 1
        if self.average > self.oldaverage+self.updatestep:
            averagesize = (self.average*barsize)/100
            while averagesize > 0:
                curbarsize += 1
                bartext += "="
                averagesize -= 1
            bartext += ">"
            diffbarsize = barsize-curbarsize
            while diffbarsize > 0:
                bartext += " "
                diffbarsize -= 1
            if self.showSpeed:
                bartext += "] => "+str(self.entropyTools.bytesIntoHuman(self.datatransfer))+"/sec ~ ETA: "+str(self.time_remaining)
            else:
                bartext += "]"
            average = str(self.average)
            if len(average) < 2:
                average = " "+average
            currentText += " <->  "+average+"% "+bartext
            print_info(currentText,back = True)


    def close(self):
        try:
            self.localfile.flush()
            self.localfile.close()
        except:
            pass
        try:
            self.remotefile.close()
        except:
            pass
        self.speedUpdater.kill()
        self.socket.setdefaulttimeout(2)

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
        self.feed_title = self.feed_title.strip()
        self.feed_description = "Keep you updated on what's going on in the Official "+etpConst['systemname']+" Repository."
        self.feed_language = "en-EN"
        self.feed_editor = etpConst['rss-managing-editor']
        self.feed_copyright = etpConst['systemname']+" (C) 2007-2009"

        self.file = filename
        self.items = {}
        self.itemscounter = 0
        self.maxentries = maxentries
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
            self.title = self.channel.getElementsByTagName("title")[0].firstChild.data.strip()
            self.link = self.channel.getElementsByTagName("link")[0].firstChild.data.strip()
            self.description = self.channel.getElementsByTagName("description")[0].firstChild.data.strip()
            self.language = self.channel.getElementsByTagName("language")[0].firstChild.data.strip()
            self.cright = self.channel.getElementsByTagName("copyright")[0].firstChild.data.strip()
            self.editor = self.channel.getElementsByTagName("managingEditor")[0].firstChild.data.strip()
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
                self.items[mycounter]['title'] = item.getElementsByTagName("title")[0].firstChild.data.strip()
                description = item.getElementsByTagName("description")[0].firstChild
                if description:
                    self.items[mycounter]['description'] = description.data.strip()
                else:
                    self.items[mycounter]['description'] = ""
                link = item.getElementsByTagName("link")[0].firstChild
                if link:
                    self.items[mycounter]['link'] = link.data.strip()
                else:
                    self.items[mycounter]['link'] = ""
                self.items[mycounter]['guid'] = item.getElementsByTagName("guid")[0].firstChild.data.strip()
                self.items[mycounter]['pubDate'] = item.getElementsByTagName("pubDate")[0].firstChild.data.strip()

    def addItem(self, title, link = '', description = ''):
        self.itemscounter += 1
        self.items[self.itemscounter] = {}
        self.items[self.itemscounter]['title'] = title
        self.items[self.itemscounter]['pubDate'] = time.strftime("%a, %d %b %Y %X +0000")
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
            if not self.items.has_key(key):
                self.removeEntry(key)
                continue
            k_error = False
            for item in ['title','link','guid','description','pubDate']:
                if not self.items[key].has_key(item):
                    k_error = True
                    break
            if k_error:
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

class TriggerInterface:

    def __init__(self, EquoInstance, phase, pkgdata):

        if not isinstance(EquoInstance,EquoInterface):
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid Entropy Instance is needed")

        self.Entropy = EquoInstance
        self.clientLog = self.Entropy.clientLog
        self.validPhases = ("preinstall","postinstall","preremove","postremove")
        self.pkgdata = pkgdata
        self.prepared = False
        self.triggers = set()
        self.gentoo_compat = etpConst['gentoo-compat']

        '''
        @ description: Gentoo toolchain variables
        '''
        self.MODULEDB_DIR="/var/lib/module-rebuild/"
        self.INITSERVICES_DIR="/var/lib/init.d/"

        ''' portage stuff '''
        if self.gentoo_compat:
            try:
                Spm = self.Entropy.Spm()
                self.Spm = Spm
            except Exception, e:
                self.Entropy.updateProgress(
                                        red("Portage interface can't be loaded due to %s: (%s), please fix it !" % (str(Exception),str(e)) ),
                                        importance = 0,
                                        header = bold(" !!! ")
                                    )
                self.gentoo_compat = False

        self.phase = phase
        # validate phase
        self.phaseValidation()

    def phaseValidation(self):
        if self.phase not in self.validPhases:
            raise exceptionTools.InvalidData("InvalidData: valid phases are %s" % (self.validPhases,))

    def prepare(self):
        self.triggers = eval("self."+self.phase)()
        remove = set()
        for trigger in self.triggers:
            if trigger in etpUi[self.phase+'_triggers_disable']:
                remove.add(trigger)
        self.triggers.difference_update(remove)
        del remove
        self.prepared = True

    def run(self):
        for trigger in self.triggers:
            eval("self.trigger_"+trigger)()

    def kill(self):
        self.prepared = False
        self.triggers.clear()

    def postinstall(self):

        functions = set()
        # Gentoo hook
        if self.gentoo_compat:
            functions.add('ebuild_postinstall')

        if self.pkgdata['trigger']:
            functions.add('call_ext_postinstall')

        # equo purge cache
        if self.pkgdata['category']+"/"+self.pkgdata['name'] == "app-admin/equo":
            functions.add("purgecache")

        # binutils configuration
        if self.pkgdata['category']+"/"+self.pkgdata['name'] == "sys-devel/binutils":
            functions.add("binutilsswitch")

        if (self.pkgdata['category']+"/"+self.pkgdata['name'] == "net-www/netscape-flash") and (etpSys['arch'] == "amd64"):
            functions.add("nspluginwrapper_fix_flash")

        # triggers that are not needed when gentoo-compat is enabled
        if not self.gentoo_compat:

            if "gnome2" in self.pkgdata['eclasses']:
                functions.add('iconscache')
                functions.add('gconfinstallschemas')
                functions.add('gconfreload')

            if self.pkgdata['name'] == "pygobject":
                functions.add('pygtksetup')

            # fonts configuration
            if self.pkgdata['category'] == "media-fonts":
                functions.add("fontconfig")

            # gcc configuration
            if self.pkgdata['category']+"/"+self.pkgdata['name'] == "sys-devel/gcc":
                functions.add("gccswitch")

            # kde package ?
            if "kde" in self.pkgdata['eclasses']:
                functions.add("kbuildsycoca")

            if "kde4-base" in self.pkgdata['eclasses'] or "kde4-meta" in self.pkgdata['eclasses']:
                functions.add("kbuildsycoca4")

            # update mime
            if "fdo-mime" in self.pkgdata['eclasses']:
                functions.add('mimeupdate')
                functions.add('mimedesktopupdate')

            if self.pkgdata['category']+"/"+self.pkgdata['name'] == "dev-db/sqlite":
                functions.add('sqliteinst')

            # python configuration
            if self.pkgdata['category']+"/"+self.pkgdata['name'] == "dev-lang/python":
                functions.add("pythoninst")

        # opengl configuration
        if (self.pkgdata['category'] == "x11-drivers") and (self.pkgdata['name'].startswith("nvidia-") or self.pkgdata['name'].startswith("ati-")):
            try:
                functions.remove("ebuild_postinstall") # disabling gentoo postinstall since we reimplemented it
            except:
                pass
            functions.add("openglsetup")

        # load linker paths
        ldpaths = self.Entropy.entropyTools.collectLinkerPaths()
        # prepare content
        for x in self.pkgdata['content']:
            if not self.gentoo_compat:
                if x.startswith("/usr/share/icons") and x.endswith("index.theme"):
                    functions.add('iconscache')
                if x.startswith("/usr/share/mime"):
                    functions.add('mimeupdate')
                if x.startswith("/usr/share/applications"):
                    functions.add('mimedesktopupdate')
                if x.startswith("/usr/share/omf"):
                    functions.add('scrollkeeper')
                if x.startswith("/etc/gconf/schemas"):
                    functions.add('gconfreload')
                if x == '/bin/su':
                    functions.add("susetuid")
                if x.startswith('/usr/share/java-config-2/vm/'):
                    functions.add('add_java_config_2')
            else:
                if x.startswith('/lib/modules/'):
                    try:
                        functions.remove("ebuild_postinstall") # disabling gentoo postinstall since we reimplemented it
                    except:
                        pass
                    functions.add('kernelmod')
                if x.startswith('/boot/kernel-'):
                    functions.add('addbootablekernel')
                if x.startswith('/usr/src/'):
                    functions.add('createkernelsym')
                if x.startswith('/etc/env.d/'):
                    functions.add('env_update')
                if os.path.dirname(x) in ldpaths:
                    if x.find(".so") > -1:
                        functions.add('run_ldconfig')
        del ldpaths
        return functions

    def preinstall(self):

        functions = set()
        if self.pkgdata['trigger']:
            functions.add('call_ext_preinstall')

        # Gentoo hook
        if self.gentoo_compat:
            functions.add('ebuild_preinstall')

        for x in self.pkgdata['content']:
            if x.startswith("/etc/init.d/"):
                functions.add('initinform')
            if x.startswith("/boot"):
                functions.add('mountboot')
        return functions

    def postremove(self):

        functions = set()

        if self.pkgdata['trigger']:
            functions.add('call_ext_postremove')

        if not self.gentoo_compat:

            # kde package ?
            if "kde" in self.pkgdata['eclasses']:
                functions.add("kbuildsycoca")

            if "kde4-base" in self.pkgdata['eclasses'] or "kde4-meta" in self.pkgdata['eclasses']:
                functions.add("kbuildsycoca4")

            if self.pkgdata['name'] == "pygtk":
                functions.add('pygtkremove')

            if self.pkgdata['category']+"/"+self.pkgdata['name'] == "dev-db/sqlite":
                functions.add('sqliteinst')

            # python configuration
            if self.pkgdata['category']+"/"+self.pkgdata['name'] == "dev-lang/python":
                functions.add("pythoninst")

            # fonts configuration
            if self.pkgdata['category'] == "media-fonts":
                functions.add("fontconfig")

        # load linker paths
        ldpaths = self.Entropy.entropyTools.collectLinkerPaths()

        for x in self.pkgdata['removecontent']:
            if not self.gentoo_compat:
                if x.startswith("/usr/share/icons") and x.endswith("index.theme"):
                    functions.add('iconscache')
                if x.startswith("/usr/share/mime"):
                    functions.add('mimeupdate')
                if x.startswith("/usr/share/applications"):
                    functions.add('mimedesktopupdate')
                if x.startswith("/usr/share/omf"):
                    functions.add('scrollkeeper')
                if x.startswith("/etc/gconf/schemas"):
                    functions.add('gconfreload')
            else:
                if x.startswith('/boot/kernel-'):
                    functions.add('removebootablekernel')
                if x.startswith('/etc/init.d/'):
                    functions.add('removeinit')
                if x.endswith('.py'):
                    functions.add('cleanpy')
                if x.startswith('/etc/env.d/'):
                    functions.add('env_update')
                if os.path.dirname(x) in ldpaths:
                    if x.find(".so") > -1:
                        functions.add('run_ldconfig')
        del ldpaths
        return functions


    def preremove(self):

        functions = set()

        if self.pkgdata['trigger']:
            functions.add('call_ext_preremove')

        # Gentoo hook
        if self.gentoo_compat:
            functions.add('ebuild_preremove')
            functions.add('ebuild_postremove') # doing here because we need /var/db/pkg stuff in place and also because doesn't make any difference

        # opengl configuration
        if (self.pkgdata['category'] == "x11-drivers") and (self.pkgdata['name'].startswith("nvidia-") or self.pkgdata['name'].startswith("ati-")):
            try:
                functions.remove("ebuild_preremove") # disabling gentoo postinstall since we reimplemented it
                functions.remove("ebuild_postremove")
            except:
                pass
            functions.add("openglsetup_xorg")

        for x in self.pkgdata['removecontent']:
            if x.startswith("/etc/init.d/"):
                functions.add('initdisable')
            if x.startswith("/boot"):
                functions.add('mountboot')

        return functions


    '''
        Real triggers
    '''
    def trigger_call_ext_preinstall(self):
        rc = self.trigger_call_ext_generic()
        return rc

    def trigger_call_ext_postinstall(self):
        rc = self.trigger_call_ext_generic()
        return rc

    def trigger_call_ext_preremove(self):
        rc = self.trigger_call_ext_generic()
        return rc

    def trigger_call_ext_postremove(self):
        rc = self.trigger_call_ext_generic()
        return rc

    def trigger_call_ext_generic(self):

        # if mute, supress portage output
        if etpUi['mute']:
            oldsystderr = sys.stderr
            oldsysstdout = sys.stdout
            stdfile = open("/dev/null","w")
            sys.stdout = stdfile
            sys.stderr = stdfile

        triggerfile = etpConst['entropyunpackdir']+"/trigger-"+str(self.Entropy.entropyTools.getRandomNumber())
        while os.path.isfile(triggerfile):
            triggerfile = etpConst['entropyunpackdir']+"/trigger-"+str(self.Entropy.entropyTools.getRandomNumber())
        f = open(triggerfile,"w")
        for x in self.pkgdata['trigger']:
            f.write(x)
        f.close()

        # if mute, restore old stdout/stderr
        if etpUi['mute']:
            sys.stderr = oldsystderr
            sys.stdout = oldsysstdout
            stdfile.close()

        stage = self.phase
        pkgdata = self.pkgdata
        my_ext_status = 0
        execfile(triggerfile)
        os.remove(triggerfile)
        return my_ext_status

    def trigger_nspluginwrapper_fix_flash(self):
        # check if nspluginwrapper is installed
        if os.access("/usr/bin/nspluginwrapper",os.X_OK):
            self.Entropy.updateProgress(
                                    brown(" Regenerating nspluginwrapper flash plugin"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            quietstring = ''
            if etpUi['quiet']: quietstring = " &>/dev/null"
            cmds = [
                "nspluginwrapper -r /usr/lib64/nsbrowser/plugins/npwrapper.libflashplayer.so"+quietstring,
                "nspluginwrapper -i /usr/lib32/nsbrowser/plugins/libflashplayer.so"+quietstring
            ]
            if not etpConst['systemroot']:
                for cmd in cmds:
                    os.system(cmd)
            else:
                for cmd in cmds:
                    os.system('echo "'+cmd+'" | chroot '+etpConst['systemroot']+quietstring)

    def trigger_purgecache(self):
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Purging Equo cache...")
        self.Entropy.updateProgress(
                                brown(" Remember: It is always better to leave Equo updates isolated."),
                                importance = 0,
                                header = red("   ##")
                            )
        self.Entropy.updateProgress(
                                brown(" Purging Equo cache..."),
                                importance = 0,
                                header = red("   ##")
                            )
        self.Entropy.purge_cache(False)

    def trigger_fontconfig(self):
        fontdirs = set()
        for xdir in self.pkgdata['content']:
            xdir = etpConst['systemroot']+xdir
            if xdir.startswith(etpConst['systemroot']+"/usr/share/fonts"):
                origdir = xdir[len(etpConst['systemroot'])+16:]
                if origdir:
                    if origdir.startswith("/"):
                        origdir = origdir.split("/")[1]
                        if os.path.isdir(xdir[:16]+"/"+origdir):
                            fontdirs.add(xdir[:16]+"/"+origdir)
        if (fontdirs):
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring fonts directory...")
            self.Entropy.updateProgress(
                                    brown(" Configuring fonts directory..."),
                                    importance = 0,
                                    header = red("   ##")
                                )
        for fontdir in fontdirs:
            self.trigger_setup_font_dir(fontdir)
            self.trigger_setup_font_cache(fontdir)
        del fontdirs

    def trigger_gccswitch(self):
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring GCC Profile...")
        self.Entropy.updateProgress(
                                brown(" Configuring GCC Profile..."),
                                importance = 0,
                                header = red("   ##")
                            )
        # get gcc profile
        pkgsplit = self.Entropy.entropyTools.catpkgsplit(self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version'])
        profile = self.pkgdata['chost']+"-"+pkgsplit[2]
        self.trigger_set_gcc_profile(profile)

    def trigger_iconscache(self):
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Updating icons cache...")
        self.Entropy.updateProgress(
                                brown(" Updating icons cache..."),
                                importance = 0,
                                header = red("   ##")
                            )
        for item in self.pkgdata['content']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/usr/share/icons") and item.endswith("index.theme"):
                cachedir = os.path.dirname(item)
                self.trigger_generate_icons_cache(cachedir)

    def trigger_mimeupdate(self):
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Updating shared mime info database...")
        self.Entropy.updateProgress(
                                brown(" Updating shared mime info database..."),
                                importance = 0,
                                header = red("   ##")
                            )
        self.trigger_update_mime_db()

    def trigger_mimedesktopupdate(self):
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Updating desktop mime database...")
        self.Entropy.updateProgress(
                                brown(" Updating desktop mime database..."),
                                importance = 0,
                                header = red("   ##")
                            )
        self.trigger_update_mime_desktop_db()

    def trigger_scrollkeeper(self):
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Updating scrollkeeper database...")
        self.Entropy.updateProgress(
                                brown(" Updating scrollkeeper database..."),
                                importance = 0,
                                header = red("   ##")
                            )
        self.trigger_update_scrollkeeper_db()

    def trigger_gconfreload(self):
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Reloading GConf2 database...")
        self.Entropy.updateProgress(
                                brown(" Reloading GConf2 database..."),
                                importance = 0,
                                header = red("   ##")
                            )
        self.trigger_reload_gconf_db()

    def trigger_binutilsswitch(self):
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring Binutils Profile...")
        self.Entropy.updateProgress(
                                brown(" Configuring Binutils Profile..."),
                                importance = 0,
                                header = red("   ##")
                            )
        # get binutils profile
        pkgsplit = self.Entropy.entropyTools.catpkgsplit(self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version'])
        profile = self.pkgdata['chost']+"-"+pkgsplit[2]
        self.trigger_set_binutils_profile(profile)

    def trigger_kernelmod(self):
        if self.pkgdata['category'] != "sys-kernel":
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Updating moduledb...")
            self.Entropy.updateProgress(
                                    brown(" Updating moduledb..."),
                                    importance = 0,
                                    header = red("   ##")
                                )
            item = 'a:1:'+self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
            self.trigger_update_moduledb(item)
        self.Entropy.updateProgress(
                                brown(" Running depmod..."),
                                importance = 0,
                                header = red("   ##")
                            )
        # get kernel modules dir name
        name = ''
        for item in self.pkgdata['content']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/lib/modules/"):
                name = item[len(etpConst['systemroot']):]
                name = name.split("/")[3]
                break
        if name:
            self.trigger_run_depmod(name)

    def trigger_pythoninst(self):
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring Python...")
        self.Entropy.updateProgress(
                                brown(" Configuring Python..."),
                                importance = 0,
                                header = red("   ##")
                            )
        self.trigger_python_update_symlink()

    def trigger_sqliteinst(self):
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring SQLite...")
        self.Entropy.updateProgress(
                                brown(" Configuring SQLite..."),
                                importance = 0,
                                header = red("   ##")
                            )
        self.trigger_sqlite_update_symlink()

    def trigger_initdisable(self):
        for item in self.pkgdata['removecontent']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/etc/init.d/") and os.path.isfile(item):
                # running?
                #running = os.path.isfile(etpConst['systemroot']+self.INITSERVICES_DIR+'/started/'+os.path.basename(item))
                if not etpConst['systemroot']:
                    myroot = "/"
                else:
                    myroot = etpConst['systemroot']+"/"
                scheduled = not os.system('ROOT="'+myroot+'" rc-update show | grep '+os.path.basename(item)+'&> /dev/null')
                self.trigger_initdeactivate(item, scheduled)

    def trigger_initinform(self):
        for item in self.pkgdata['content']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/etc/init.d/") and not os.path.isfile(etpConst['systemroot']+item):
                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] A new service will be installed: "+item)
                self.Entropy.updateProgress(
                                        brown(" A new service will be installed: ")+item,
                                        importance = 0,
                                        header = red("   ##")
                                    )

    def trigger_removeinit(self):
        for item in self.pkgdata['removecontent']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/etc/init.d/") and os.path.isfile(item):
                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Removing boot service: "+os.path.basename(item))
                self.Entropy.updateProgress(
                                        brown(" Removing boot service: ")+os.path.basename(item),
                                        importance = 0,
                                        header = red("   ##")
                                    )
                if not etpConst['systemroot']:
                    myroot = "/"
                else:
                    myroot = etpConst['systemroot']+"/"
                try:
                    os.system('ROOT="'+myroot+'" rc-update del '+os.path.basename(item)+' &> /dev/null')
                except:
                    pass

    def trigger_openglsetup(self):
        opengl = "xorg-x11"
        if self.pkgdata['name'] == "nvidia-drivers":
            opengl = "nvidia"
        elif self.pkgdata['name'] == "ati-drivers":
            opengl = "ati"
        # is there eselect ?
        eselect = os.system("eselect opengl &> /dev/null")
        if eselect == 0:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Reconfiguring OpenGL to "+opengl+" ...")
            self.Entropy.updateProgress(
                                    brown(" Reconfiguring OpenGL..."),
                                    importance = 0,
                                    header = red("   ##")
                                )
            quietstring = ''
            if etpUi['quiet']: quietstring = " &>/dev/null"
            if etpConst['systemroot']:
                os.system('echo "eselect opengl set --use-old '+opengl+'" | chroot '+etpConst['systemroot']+quietstring)
            else:
                os.system('eselect opengl set --use-old '+opengl+quietstring)
        else:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Eselect NOT found, cannot run OpenGL trigger")
            self.Entropy.updateProgress(
                                    brown(" Eselect NOT found, cannot run OpenGL trigger"),
                                    importance = 0,
                                    header = red("   ##")
                                )

    def trigger_openglsetup_xorg(self):
        eselect = os.system("eselect opengl &> /dev/null")
        if eselect == 0:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Reconfiguring OpenGL to fallback xorg-x11 ...")
            self.Entropy.updateProgress(
                                    brown(" Reconfiguring OpenGL..."),
                                    importance = 0,
                                    header = red("   ##")
                                )
            quietstring = ''
            if etpUi['quiet']: quietstring = " &>/dev/null"
            if etpConst['systemroot']:
                os.system('echo "eselect opengl set xorg-x11" | chroot '+etpConst['systemroot']+quietstring)
            else:
                os.system('eselect opengl set xorg-x11'+quietstring)
        else:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Eselect NOT found, cannot run OpenGL trigger")
            self.Entropy.updateProgress(
                                    brown(" Eselect NOT found, cannot run OpenGL trigger"),
                                    importance = 0,
                                    header = red("   ##")
                                )

    # FIXME: this only supports grub (no lilo support)
    def trigger_addbootablekernel(self):
        boot_mount = False
        if os.path.ismount("/boot"):
            boot_mount = True
        kernels = [x for x in self.pkgdata['content'] if x.startswith("/boot/kernel-")]
        if boot_mount:
            kernels = [x[len("/boot"):] for x in kernels]
        for kernel in kernels:
            mykernel = kernel.split('/kernel-')[1]
            initramfs = "/boot/initramfs-"+mykernel
            if initramfs not in self.pkgdata['content']:
                initramfs = ''
            elif boot_mount:
                initramfs = initramfs[len("/boot"):]

            # configure GRUB
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring GRUB bootloader. Adding the new kernel...")
            self.Entropy.updateProgress(
                                    brown(" Configuring GRUB bootloader. Adding the new kernel..."),
                                    importance = 0,
                                    header = red("   ##")
                                )
            self.trigger_configure_boot_grub(kernel,initramfs)
	

    # FIXME: this only supports grub (no lilo support)
    def trigger_removebootablekernel(self):
        kernels = [x for x in self.pkgdata['content'] if x.startswith("/boot/kernel-")]
        for kernel in kernels:
            initramfs = "/boot/initramfs-"+kernel[13:]
            if initramfs not in self.pkgdata['content']:
                initramfs = ''
            # configure GRUB
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring GRUB bootloader. Removing the selected kernel...")
            self.Entropy.updateProgress(
                                    brown(" Configuring GRUB bootloader. Removing the selected kernel..."),
                                    importance = 0,
                                    header = red("   ##")
                                )
            self.trigger_remove_boot_grub(kernel,initramfs)

    def trigger_mountboot(self):
        # is in fstab?
        if etpConst['systemroot']:
            return
        if os.path.isfile("/etc/fstab"):
            f = open("/etc/fstab","r")
            fstab = f.readlines()
            fstab = self.Entropy.entropyTools.listToUtf8(fstab)
            f.close()
            for line in fstab:
                fsline = line.split()
                if len(fsline) > 1:
                    if fsline[1] == "/boot":
                        if not os.path.ismount("/boot"):
                            # trigger mount /boot
                            rc = os.system("mount /boot &> /dev/null")
                            if rc == 0:
                                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] Mounted /boot successfully")
                                self.Entropy.updateProgress(
                                                        brown(" Mounted /boot successfully"),
                                                        importance = 0,
                                                        header = red("   ##")
                                                    )
                            elif rc != 8192: # already mounted
                                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] Cannot mount /boot automatically !!")
                                self.Entropy.updateProgress(
                                                        brown(" Cannot mount /boot automatically !!"),
                                                        importance = 0,
                                                        header = red("   ##")
                                                    )
                            break

    def trigger_kbuildsycoca(self):
        if etpConst['systemroot']:
            return
        kdedirs = ''
        try:
            kdedirs = os.environ['KDEDIRS']
        except:
            pass
        if kdedirs:
            dirs = kdedirs.split(":")
            for builddir in dirs:
                if os.access(builddir+"/bin/kbuildsycoca",os.X_OK):
                    if not os.path.isdir("/usr/share/services"):
                        os.makedirs("/usr/share/services")
                    os.chown("/usr/share/services",0,0)
                    os.chmod("/usr/share/services",0755)
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Running kbuildsycoca to build global KDE database")
                    self.Entropy.updateProgress(
                                            brown(" Running kbuildsycoca to build global KDE database"),
                                            importance = 0,
                                            header = red("   ##")
                                        )
                    os.system(builddir+"/bin/kbuildsycoca --global --noincremental &> /dev/null")

    def trigger_kbuildsycoca4(self):
        if etpConst['systemroot']:
            return
        kdedirs = ''
        try:
            kdedirs = os.environ['KDEDIRS']
        except:
            pass
        if kdedirs:
            dirs = kdedirs.split(":")
            for builddir in dirs:
                if os.access(builddir+"/bin/kbuildsycoca4",os.X_OK):
                    if not os.path.isdir("/usr/share/services"):
                        os.makedirs("/usr/share/services")
                    os.chown("/usr/share/services",0,0)
                    os.chmod("/usr/share/services",0755)
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Running kbuildsycoca4 to build global KDE4 database")
                    self.Entropy.updateProgress(
                                            brown(" Running kbuildsycoca to build global KDE database"),
                                            importance = 0,
                                            header = red("   ##")
                                        )
                    # do it
                    kbuild4cmd = """

                    # Thanks to the hard work of kde4 gentoo overlay maintainers

                    for i in $(dbus-launch); do
                            export "$i"
                    done

                    # This is needed because we support multiple kde versions installed together.
                    XDG_DATA_DIRS="/usr/share:${KDEDIRS}/share:/usr/local/share"
                    """+builddir+"""/bin/kbuildsycoca4 --global --noincremental &> /dev/null
                    kill ${DBUS_SESSION_BUS_PID}

                    """
                    os.system(kbuild4cmd)

    def trigger_gconfinstallschemas(self):
        gtest = os.system("which gconftool-2 &> /dev/null")
        if gtest == 0 or etpConst['systemroot']:
            schemas = [x for x in self.pkgdata['content'] if x.startswith("/etc/gconf/schemas") and x.endswith(".schemas")]
            self.Entropy.updateProgress(
                                    brown(" Installing GConf2 schemas..."),
                                    importance = 0,
                                    header = red("   ##")
                                )
            for schema in schemas:
                if not etpConst['systemroot']:
                    os.system("""
                    unset GCONF_DISABLE_MAKEFILE_SCHEMA_INSTALL
                    export GCONF_CONFIG_SOURCE=$(gconftool-2 --get-default-source)
                    gconftool-2 --makefile-install-rule """+schema+""" 1>/dev/null
                    """)
                else:
                    os.system(""" echo "
                    unset GCONF_DISABLE_MAKEFILE_SCHEMA_INSTALL
                    export GCONF_CONFIG_SOURCE=$(gconftool-2 --get-default-source)
                    gconftool-2 --makefile-install-rule """+schema+""" " | chroot """+etpConst['systemroot']+""" &>/dev/null
                    """)

    def trigger_pygtksetup(self):
        python_sym_files = [x for x in self.pkgdata['content'] if x.endswith("pygtk.py-2.0") or x.endswith("pygtk.pth-2.0")]
        for item in python_sym_files:
            item = etpConst['systemroot']+item
            filepath = item[:-4]
            sympath = os.path.basename(item)
            if os.path.isfile(item):
                try:
                    if os.path.lexists(filepath):
                        os.remove(filepath)
                    os.symlink(sympath,filepath)
                except OSError:
                    pass

    def trigger_pygtkremove(self):
        python_sym_files = [x for x in self.pkgdata['content'] if x.startswith("/usr/lib/python") and (x.endswith("pygtk.py-2.0") or x.endswith("pygtk.pth-2.0"))]
        for item in python_sym_files:
            item = etpConst['systemroot']+item
            if os.path.isfile(item[:-4]):
                os.remove(item[:-4])

    def trigger_susetuid(self):
        if os.path.isfile(etpConst['systemroot']+"/bin/su"):
            self.Entropy.updateProgress(
                                    brown(" Configuring '"+etpConst['systemroot']+"/bin/su' executable SETUID"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            os.chown(etpConst['systemroot']+"/bin/su",0,0)
            os.system("chmod 4755 "+etpConst['systemroot']+"/bin/su")
            #os.chmod("/bin/su",4755) #FIXME: probably there's something I don't know here since, masks?

    def trigger_cleanpy(self):
        pyfiles = [x for x in self.pkgdata['content'] if x.endswith(".py")]
        for item in pyfiles:
            item = etpConst['systemroot']+item
            if os.path.isfile(item+"o"):
                try: os.remove(item+"o")
                except OSError: pass
            if os.path.isfile(item+"c"):
                try: os.remove(item+"c")
                except OSError: pass

    def trigger_createkernelsym(self):
        for item in self.pkgdata['content']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/usr/src/"):
                # extract directory
                try:
                    todir = item[len(etpConst['systemroot']):]
                    todir = todir.split("/")[3]
                except:
                    continue
                if os.path.isdir(etpConst['systemroot']+"/usr/src/"+todir):
                    # link to /usr/src/linux
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Creating kernel symlink "+etpConst['systemroot']+"/usr/src/linux for /usr/src/"+todir)
                    self.Entropy.updateProgress(
                                            brown(" Creating kernel symlink "+etpConst['systemroot']+"/usr/src/linux for /usr/src/"+todir),
                                            importance = 0,
                                            header = red("   ##")
                                        )
                    if os.path.isfile(etpConst['systemroot']+"/usr/src/linux") or os.path.islink(etpConst['systemroot']+"/usr/src/linux"):
                        os.remove(etpConst['systemroot']+"/usr/src/linux")
                    if os.path.isdir(etpConst['systemroot']+"/usr/src/linux"):
                        mydir = etpConst['systemroot']+"/usr/src/linux."+str(self.Entropy.entropyTools.getRandomNumber())
                        while os.path.isdir(mydir):
                            mydir = etpConst['systemroot']+"/usr/src/linux."+str(self.Entropy.entropyTools.getRandomNumber())
                        shutil.move(etpConst['systemroot']+"/usr/src/linux",mydir)
                    try:
                        os.symlink(todir,etpConst['systemroot']+"/usr/src/linux")
                    except OSError: # not important in the end
                        pass
                    break

    def trigger_run_ldconfig(self):
        if not etpConst['systemroot']:
            myroot = "/"
        else:
            myroot = etpConst['systemroot']+"/"
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Running ldconfig")
        self.Entropy.updateProgress(
                                brown(" Regenerating /etc/ld.so.cache"),
                                importance = 0,
                                header = red("   ##")
                            )
        os.system("ldconfig -r "+myroot+" &> /dev/null")

    def trigger_env_update(self):
        # clear linker paths cache
        linkerPaths.clear()
        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Running env-update")
        if os.access(etpConst['systemroot']+"/usr/sbin/env-update",os.X_OK):
            self.Entropy.updateProgress(
                                    brown(" Updating environment using env-update"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            if etpConst['systemroot']:
                os.system("echo 'env-update --no-ldconfig' | chroot "+etpConst['systemroot']+" &> /dev/null")
            else:
                os.system('env-update --no-ldconfig &> /dev/null')

    def trigger_add_java_config_2(self):
        vms = set()
        for vm in self.pkgdata['content']:
            vm = etpConst['systemroot']+vm
            if vm.startswith(etpConst['systemroot']+"/usr/share/java-config-2/vm/") and os.path.isfile(vm):
                vms.add(vm)
        # sort and get the latter
        if vms:
            vms = list(vms)
            vms.reverse()
            myvm = vms[0].split("/")[-1]
            if myvm:
                if os.access(etpConst['systemroot']+"/usr/bin/java-config",os.X_OK):
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] Configuring JAVA using java-config with VM: "+myvm)
                    # set
                    self.Entropy.updateProgress(
                                            brown(" Setting system VM to ")+bold(myvm)+brown("..."),
                                            importance = 0,
                                            header = red("   ##")
                                        )
                    if not etpConst['systemroot']:
                        os.system("java-config -S "+myvm)
                    else:
                        os.system("echo 'java-config -S "+myvm+"' | chroot "+etpConst['systemroot']+" &> /dev/null")
                else:
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] ATTENTION /usr/bin/java-config does not exist. I was about to set JAVA VM: "+myvm)
                    self.Entropy.updateProgress(
                                            bold(" Attention: ")+brown("/usr/bin/java-config does not exist. Cannot set JAVA VM."),
                                            importance = 0,
                                            header = red("   ##")
                                        )
        del vms

    def trigger_ebuild_postinstall(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        oldstdout = sys.stdout
        sys.stderr = stdfile

        myebuild = [self.pkgdata['xpakdir']+"/"+x for x in os.listdir(self.pkgdata['xpakdir']) if x.endswith(".ebuild")]
        if myebuild:
            myebuild = myebuild[0]
            portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
            self.Entropy.updateProgress(
                                    brown(" Ebuild: pkg_postinst()"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            try:
                if not os.path.isfile(self.pkgdata['unpackdir']+"/portage/"+portage_atom+"/temp/environment"):
                    # if environment is not yet created, we need to run pkg_setup()
                    sys.stdout = stdfile
                    rc = self.Spm.spm_doebuild(myebuild, mydo = "setup", tree = "bintree", cpv = portage_atom, portage_tmpdir = self.pkgdata['unpackdir'], licenses = self.pkgdata['accept_license'])
                    if rc == 1:
                        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] ATTENTION Cannot properly run Gentoo postinstall (pkg_setup()) trigger for "+str(portage_atom)+". Something bad happened.")
                    sys.stdout = oldstdout
                rc = self.Spm.spm_doebuild(myebuild, mydo = "postinst", tree = "bintree", cpv = portage_atom, portage_tmpdir = self.pkgdata['unpackdir'], licenses = self.pkgdata['accept_license'])
                if rc == 1:
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] ATTENTION Cannot properly run Gentoo postinstall (pkg_postinst()) trigger for "+str(portage_atom)+". Something bad happened.")
            except Exception, e:
                sys.stdout = oldstdout
                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[POST] ATTENTION Cannot run Gentoo postinst trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e))
                self.Entropy.updateProgress(
                                        bold(" QA Warning: ")+brown("Cannot run Gentoo postint trigger for ")+bold(portage_atom)+brown(". Please report."),
                                        importance = 0,
                                        header = red("   ##")
                                    )
        sys.stderr = oldstderr
        sys.stdout = oldstdout
        stdfile.close()
        return 0

    def trigger_ebuild_preinstall(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        oldstdout = sys.stdout
        sys.stderr = stdfile

        myebuild = [self.pkgdata['xpakdir']+"/"+x for x in os.listdir(self.pkgdata['xpakdir']) if x.endswith(".ebuild")]
        if myebuild:
            myebuild = myebuild[0]
            portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
            self.Entropy.updateProgress(
                                    brown(" Ebuild: pkg_preinst()"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            try:
                sys.stdout = stdfile
                rc = self.Spm.spm_doebuild(myebuild, mydo = "setup", tree = "bintree", cpv = portage_atom, portage_tmpdir = self.pkgdata['unpackdir'], licenses = self.pkgdata['accept_license']) # create mysettings["T"]+"/environment"
                if rc == 1:
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] ATTENTION Cannot properly run Gentoo preinstall (pkg_setup()) trigger for "+str(portage_atom)+". Something bad happened.")
                sys.stdout = oldstdout
                rc = self.Spm.spm_doebuild(myebuild, mydo = "preinst", tree = "bintree", cpv = portage_atom, portage_tmpdir = self.pkgdata['unpackdir'], licenses = self.pkgdata['accept_license'])
                if rc == 1:
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] ATTENTION Cannot properly run Gentoo preinstall (pkg_preinst()) trigger for "+str(portage_atom)+". Something bad happened.")
            except Exception, e:
                sys.stdout = oldstdout
                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] ATTENTION Cannot run Gentoo preinst trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e))
                self.Entropy.updateProgress(
                                        bold(" QA Warning: ")+brown("Cannot run Gentoo preinst trigger for ")+bold(portage_atom)+brown(". Please report."),
                                        importance = 0,
                                        header = red("   ##")
                                    )
        sys.stderr = oldstderr
        sys.stdout = oldstdout
        stdfile.close()
        return 0

    def trigger_ebuild_preremove(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        sys.stderr = stdfile

        portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
        try:
            myebuild = self.Spm.get_vdb_path()+portage_atom+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']+".ebuild"
        except:
            myebuild = ''

        self.myebuild_moved = None
        if os.path.isfile(myebuild):
            myebuild = self._setup_remove_ebuild_environment(myebuild, portage_atom)

        if os.path.isfile(myebuild):

            self.Entropy.updateProgress(
                                    brown(" Ebuild: pkg_prerm()"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            try:
                rc = self.Spm.spm_doebuild(myebuild, mydo = "prerm", tree = "bintree", cpv = portage_atom, portage_tmpdir = etpConst['entropyunpackdir']+"/"+portage_atom)
                if rc == 1:
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] ATTENTION Cannot properly run Gentoo preremove trigger for "+str(portage_atom)+". Something bad happened.")
            except Exception, e:
                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] ATTENTION Cannot run Gentoo preremove trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e))
                self.Entropy.updateProgress(
                                        bold(" QA Warning: ")+brown("Cannot run Gentoo preremove trigger for ")+bold(portage_atom)+brown(". Please report."),
                                        importance = 0,
                                        header = red("   ##")
                                    )

        sys.stderr = oldstderr
        stdfile.close()

        self._remove_overlayed_ebuild()

        return 0

    def trigger_ebuild_postremove(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        sys.stderr = stdfile

        portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
        try:
            myebuild = self.Spm.get_vdb_path()+portage_atom+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']+".ebuild"
        except:
            myebuild = ''

        self.myebuild_moved = None
        if os.path.isfile(myebuild):
            myebuild = self._setup_remove_ebuild_environment(myebuild, portage_atom)

        if os.path.isfile(myebuild):
            self.Entropy.updateProgress(
                                    brown(" Ebuild: pkg_postrm()"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            try:
                rc = self.Spm.spm_doebuild(myebuild, mydo = "postrm", tree = "bintree", cpv = portage_atom, portage_tmpdir = etpConst['entropyunpackdir']+"/"+portage_atom)
                if rc == 1:
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] ATTENTION Cannot properly run Gentoo postremove trigger for "+str(portage_atom)+". Something bad happened.")
            except Exception, e:
                self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"[PRE] ATTENTION Cannot run Gentoo postremove trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e))
                self.Entropy.updateProgress(
                                        bold(" QA Warning: ")+brown("Cannot run Gentoo postremove trigger for ")+bold(portage_atom)+brown(". Please report."),
                                        importance = 0,
                                        header = red("   ##")
                                    )
        sys.stderr = oldstderr
        stdfile.close()

        self._remove_overlayed_ebuild()

        return 0

    def _setup_remove_ebuild_environment(self, myebuild, portage_atom):

        ebuild_dir = os.path.dirname(myebuild)
        ebuild_file = os.path.basename(myebuild)

        # copy the whole directory in a safe place
        dest_dir = os.path.join(etpConst['entropyunpackdir'],"vardb/"+portage_atom)
        if os.path.exists(dest_dir):
            if os.path.isdir(dest_dir):
                shutil.rmtree(dest_dir,True)
            elif os.path.isfile(dest_dir) or os.path.islink(dest_dir):
                os.remove(dest_dir)
        os.makedirs(dest_dir)
        items = os.listdir(ebuild_dir)
        for item in items:
            myfrom = os.path.join(ebuild_dir,item)
            myto = os.path.join(dest_dir,item)
            shutil.copy2(myfrom,myto)

        newmyebuild = os.path.join(dest_dir,ebuild_file)
        if os.path.isfile(newmyebuild):
            myebuild = newmyebuild
            self.myebuild_moved = myebuild
            self._ebuild_env_setup_hook(myebuild)
        return myebuild

    def _ebuild_env_setup_hook(self, myebuild):
        ebuild_path = os.path.dirname(myebuild)
        if not etpConst['systemroot']:
            myroot = "/"
        else:
            myroot = etpConst['systemroot']+"/"

        # we need to fix ROOT= if it's set inside environment
        bz2envfile = os.path.join(ebuild_path,"environment.bz2")
        if os.path.isfile(bz2envfile) and os.path.isdir(myroot):
            #print "found",bz2envfile,myroot
            import bz2
            envfile = self.Entropy.entropyTools.unpackBzip2(bz2envfile)
            bzf = bz2.BZ2File(bz2envfile,"w")
            f = open(envfile,"r")
            line = f.readline()
            while line:
                if line.startswith("ROOT="):
                    #print "found ROOT ::: ",line
                    line = "ROOT=%s\n" % (myroot,)
                    #print "CHANGED ROOT ::: ",line
                bzf.write(line)
                line = f.readline()
            f.close()
            bzf.close()
            os.remove(envfile)

    def _remove_overlayed_ebuild(self):
        if not self.myebuild_moved:
            return

        if os.path.isfile(self.myebuild_moved):
            mydir = os.path.dirname(self.myebuild_moved)
            shutil.rmtree(mydir,True)
            mydir = os.path.dirname(mydir)
            content = os.listdir(mydir)
            while not content:
                os.rmdir(mydir)
                mydir = os.path.dirname(mydir)
                content = os.listdir(mydir)

    '''
        Internal ones
    '''

    '''
    @description: creates Xfont files
    @output: returns int() as exit status
    '''
    def trigger_setup_font_dir(self, fontdir):
        # mkfontscale
        if os.access('/usr/bin/mkfontscale',os.X_OK):
            os.system('/usr/bin/mkfontscale '+unicode(fontdir))
        # mkfontdir
        if os.access('/usr/bin/mkfontdir',os.X_OK):
            os.system('/usr/bin/mkfontdir -e '+etpConst['systemroot']+'/usr/share/fonts/encodings -e '+etpConst['systemroot']+'/usr/share/fonts/encodings/large '+unicode(fontdir))
        return 0

    '''
    @description: creates font cache
    @output: returns int() as exit status
    '''
    def trigger_setup_font_cache(self, fontdir):
        # fc-cache -f gooooo!
        if os.access('/usr/bin/fc-cache',os.X_OK):
            os.system('/usr/bin/fc-cache -f '+unicode(fontdir))
        return 0

    '''
    @description: set chosen gcc profile
    @output: returns int() as exit status
    '''
    def trigger_set_gcc_profile(self, profile):
        if os.access(etpConst['systemroot']+'/usr/bin/gcc-config',os.X_OK):
            redirect = ""
            if etpUi['quiet']:
                redirect = " &> /dev/null"
            if etpConst['systemroot']:
                os.system("echo '/usr/bin/gcc-config "+profile+"' | chroot "+etpConst['systemroot']+redirect)
            else:
                os.system('/usr/bin/gcc-config '+profile+redirect)
        return 0

    '''
    @description: set chosen binutils profile
    @output: returns int() as exit status
    '''
    def trigger_set_binutils_profile(self, profile):
        if os.access(etpConst['systemroot']+'/usr/bin/binutils-config',os.X_OK):
            redirect = ""
            if etpUi['quiet']:
                redirect = " &> /dev/null"
            if etpConst['systemroot']:
                os.system("echo '/usr/bin/binutils-config "+profile+"' | chroot "+etpConst['systemroot']+redirect)
            else:
                os.system('/usr/bin/binutils-config '+profile+redirect)
        return 0

    '''
    @description: creates/updates icons cache
    @output: returns int() as exit status
    '''
    def trigger_generate_icons_cache(self, cachedir):
        if not etpConst['systemroot']:
            myroot = "/"
        else:
            myroot = etpConst['systemroot']+"/"
        if os.access('/usr/bin/gtk-update-icon-cache',os.X_OK):
            os.system('ROOT="'+myroot+'" /usr/bin/gtk-update-icon-cache -qf '+cachedir)
        return 0

    '''
    @description: updates /usr/share/mime database
    @output: returns int() as exit status
    '''
    def trigger_update_mime_db(self):
        if os.access(etpConst['systemroot']+'/usr/bin/update-mime-database',os.X_OK):
            if not etpConst['systemroot']:
                os.system('/usr/bin/update-mime-database /usr/share/mime')
            else:
                os.system("echo '/usr/bin/update-mime-database /usr/share/mime' | chroot "+etpConst['systemroot']+" &> /dev/null")
        return 0

    '''
    @description: updates /usr/share/applications database
    @output: returns int() as exit status
    '''
    def trigger_update_mime_desktop_db(self):
        if os.access(etpConst['systemroot']+'/usr/bin/update-desktop-database',os.X_OK):
            if not etpConst['systemroot']:
                os.system('/usr/bin/update-desktop-database -q /usr/share/applications')
            else:
                os.system("echo '/usr/bin/update-desktop-database -q /usr/share/applications' | chroot "+etpConst['systemroot']+" &> /dev/null")
        return 0

    '''
    @description: updates /var/lib/scrollkeeper database
    @output: returns int() as exit status
    '''
    def trigger_update_scrollkeeper_db(self):
        if os.access(etpConst['systemroot']+'/usr/bin/scrollkeeper-update',os.X_OK):
            if not os.path.isdir(etpConst['systemroot']+'/var/lib/scrollkeeper'):
                os.makedirs(etpConst['systemroot']+'/var/lib/scrollkeeper')
            if not etpConst['systemroot']:
                os.system('/usr/bin/scrollkeeper-update -q -p /var/lib/scrollkeeper')
            else:
                os.system("echo '/usr/bin/scrollkeeper-update -q -p /var/lib/scrollkeeper' | chroot "+etpConst['systemroot']+" &> /dev/null")
        return 0

    '''
    @description: respawn gconfd-2 if found
    @output: returns int() as exit status
    '''
    def trigger_reload_gconf_db(self):
        if etpConst['systemroot']:
            return 0
        rc = os.system('pgrep -x gconfd-2')
        if (rc == 0):
            pids = commands.getoutput('pgrep -x gconfd-2').split("\n")
            pidsstr = ''
            for pid in pids:
                if pid:
                    pidsstr += pid+' '
            pidsstr = pidsstr.strip()
            if pidsstr:
                os.system('kill -HUP '+pidsstr)
        return 0

    '''
    @description: updates moduledb
    @output: returns int() as exit status
    '''
    def trigger_update_moduledb(self, item):
        if os.access(etpConst['systemroot']+'/usr/sbin/module-rebuild',os.X_OK):
            if os.path.isfile(etpConst['systemroot']+self.MODULEDB_DIR+'moduledb'):
                f = open(etpConst['systemroot']+self.MODULEDB_DIR+'moduledb',"r")
                moduledb = f.readlines()
                moduledb = self.Entropy.entropyTools.listToUtf8(moduledb)
                f.close()
                avail = [x for x in moduledb if x.strip() == item]
                if (not avail):
                    f = open(etpConst['systemroot']+self.MODULEDB_DIR+'moduledb',"aw")
                    f.write(item+"\n")
                    f.flush()
                    f.close()
        return 0

    '''
    @description: insert kernel object into kernel modules db
    @output: returns int() as exit status
    '''
    def trigger_run_depmod(self, name):
        if os.access('/sbin/depmod',os.X_OK):
            if not etpConst['systemroot']:
                myroot = "/"
            else:
                myroot = etpConst['systemroot']+"/"
            os.system('/sbin/depmod -a -b '+myroot+' -r '+name+' &> /dev/null')
        return 0

    '''
    @description: update /usr/bin/python and /usr/bin/python2 symlink
    @output: returns int() as exit status
    '''
    def trigger_python_update_symlink(self):
        bins = [x for x in os.listdir("/usr/bin") if x.startswith("python2.")]
        if bins: # don't ask me why but it happened...
            bins.sort()
            latest = bins[-1]

            latest = etpConst['systemroot']+"/usr/bin/"+latest
            filepath = os.path.dirname(latest)+"/python"
            sympath = os.path.basename(latest)
            if os.path.isfile(latest):
                try:
                    if os.path.lexists(filepath):
                        os.remove(filepath)
                    os.symlink(sympath,filepath)
                except OSError:
                    pass
        return 0

    '''
    @description: update /usr/bin/lemon symlink
    @output: returns int() as exit status
    '''
    def trigger_sqlite_update_symlink(self):
        bins = [x for x in os.listdir("/usr/bin") if x.startswith("lemon-")]
        if bins:
            bins.sort()
            latest = bins[-1]
            latest = etpConst['systemroot']+"/usr/bin/"+latest

            filepath = os.path.dirname(latest)+"/lemon"
            sympath = os.path.basename(latest)
            if os.path.isfile(latest):
                try:
                    if os.path.lexists(filepath):
                        os.remove(filepath)
                    os.symlink(sympath,filepath)
                except OSError:
                    pass
        return 0

    '''
    @description: shuts down selected init script, and remove from runlevel
    @output: returns int() as exit status
    '''
    def trigger_initdeactivate(self, item, scheduled):
        if not etpConst['systemroot']:
            myroot = "/"
            '''
            causes WORLD to fall under
            if (running):
                os.system(item+' stop --quiet')
            '''
        else:
            myroot = etpConst['systemroot']+"/"
        if (scheduled):
            os.system('ROOT="'+myroot+'" rc-update del '+os.path.basename(item))
        return 0

    def __get_entropy_kernel_grub_line(self, kernel):
        return "title="+etpConst['systemname']+" ("+os.path.basename(kernel)+")\n"

    '''
    @description: append kernel entry to grub.conf
    @output: returns int() as exit status
    '''
    def trigger_configure_boot_grub(self, kernel,initramfs):

        if not os.path.isdir(etpConst['systemroot']+"/boot/grub"):
            os.makedirs(etpConst['systemroot']+"/boot/grub")
        if os.path.isfile(etpConst['systemroot']+"/boot/grub/grub.conf"):
            # open in append
            grub = open(etpConst['systemroot']+"/boot/grub/grub.conf","aw")
            shutil.copy2(etpConst['systemroot']+"/boot/grub/grub.conf",etpConst['systemroot']+"/boot/grub/grub.conf.old.add")
            # get boot dev
            boot_dev = self.trigger_get_grub_boot_dev()
            # test if entry has been already added
            grubtest = open(etpConst['systemroot']+"/boot/grub/grub.conf","r")
            content = grubtest.readlines()
            content = [unicode(x,'raw_unicode_escape') for x in content]
            for line in content:
                if line.find(self.__get_entropy_kernel_grub_line(kernel)) != -1:
                    grubtest.close()
                    return
                # also check if we have the same kernel listed
                if (line.find("kernel") != 1) and (line.find(os.path.basename(kernel)) != -1) and not line.strip().startswith("#"):
                    grubtest.close()
                    return
        else:
            # create
            boot_dev = "(hd0,0)"
            grub = open(etpConst['systemroot']+"/boot/grub/grub.conf","w")
            # write header - guess (hd0,0)... since it is weird having a running system without a bootloader, at least, grub.
            grub_header = '''
default=0
timeout=10
            '''
            grub.write(grub_header)
        cmdline = ' '
        if os.path.isfile("/proc/cmdline"):
            f = open("/proc/cmdline","r")
            cmdline = " "+f.readline().strip()
            params = cmdline.split()
            if "dolvm" not in params: # support new kernels >= 2.6.23
                cmdline += " dolvm "
            f.close()
        grub.write(self.__get_entropy_kernel_grub_line(kernel))
        grub.write("\troot "+boot_dev+"\n")
        grub.write("\tkernel "+kernel+cmdline+"\n")
        if initramfs:
            grub.write("\tinitrd "+initramfs+"\n")
        grub.write("\n")
        grub.flush()
        grub.close()

    def trigger_remove_boot_grub(self, kernel,initramfs):
        if os.path.isdir(etpConst['systemroot']+"/boot/grub") and os.path.isfile(etpConst['systemroot']+"/boot/grub/grub.conf"):
            shutil.copy2(etpConst['systemroot']+"/boot/grub/grub.conf",etpConst['systemroot']+"/boot/grub/grub.conf.old.remove")
            f = open(etpConst['systemroot']+"/boot/grub/grub.conf","r")
            grub_conf = f.readlines()
            f.close()
            content = [unicode(x,'raw_unicode_escape') for x in grub_conf]
            try:
                kernel, initramfs = (unicode(kernel,'raw_unicode_escape'),unicode(initramfs,'raw_unicode_escape'))
            except TypeError:
                pass
            #kernelname = os.path.basename(kernel)
            new_conf = []
            skip = False
            for line in content:

                if (line.find(self.__get_entropy_kernel_grub_line(kernel)) != -1):
                    skip = True
                    continue

                if line.strip().startswith("title"):
                    skip = False

                if not skip or line.strip().startswith("#"):
                    new_conf.append(line)

            f = open(etpConst['systemroot']+"/boot/grub/grub.conf","w")
            for line in new_conf:
                f.write(line)
            f.flush()
            f.close()

    def trigger_get_grub_boot_dev(self):
        if etpConst['systemroot']:
            return "(hd0,0)"
        import re
        df_avail = os.system("which df &> /dev/null")
        if df_avail != 0:
            self.Entropy.updateProgress(
                                    bold(" QA Warning: ")+brown("cannot find df!! Cannot properly configure kernel! Defaulting to (hd0,0)"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            return "(hd0,0)"
        grub_avail = os.system("which grub &> /dev/null")
        if grub_avail != 0:
            self.Entropy.updateProgress(
                                    bold(" QA Warning: ")+brown("cannot find grub!! Cannot properly configure kernel! Defaulting to (hd0,0)"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            return "(hd0,0)"

        gboot = commands.getoutput("df /boot").split("\n")[-1].split()[0]
        if gboot.startswith("/dev/"):
            # it's ok - handle /dev/md
            if gboot.startswith("/dev/md"):
                md = os.path.basename(gboot)
                if not md.startswith("md"):
                    md = "md"+md
                f = open("/proc/mdstat","r")
                mdstat = f.readlines()
                mdstat = [x for x in mdstat if x.startswith(md)]
                f.close()
                if mdstat:
                    mdstat = mdstat[0].strip().split()
                    mddevs = []
                    for x in mdstat:
                        if x.startswith("sd"):
                            mddevs.append(x[:-3])
                    mddevs.sort()
                    if mddevs:
                        gboot = "/dev/"+mddevs[0]
                    else:
                        gboot = "/dev/sda1"
                else:
                    gboot = "/dev/sda1"
            # get disk
            match = re.subn("[0-9]","",gboot)
            gdisk = match[0]
            if gdisk == '':
                self.Entropy.updateProgress(
                                        bold(" QA Warning: ") + brown("cannot match %s device with a GRUB one!! Cannot properly configure kernel! Defaulting to (hd0,0)") % (gboot,),
                                        importance = 0,
                                        header = red("   ##")
                                    )
                return "(hd0,0)"
            match = re.subn("[a-z/]","",gboot)
            gpartnum = str(int(match[0])-1)
            # now match with grub
            device_map = etpConst['packagestmpdir']+"/grub.map"
            if os.path.isfile(device_map):
                os.remove(device_map)
            # generate device.map
            os.system('echo "quit" | grub --device-map='+device_map+' --no-floppy --batch &> /dev/null')
            if os.path.isfile(device_map):
                f = open(device_map,"r")
                device_map_file = f.readlines()
                f.close()
                grub_dev = [x for x in device_map_file if (x.find(gdisk) != -1)]
                if grub_dev:
                    grub_disk = grub_dev[0].strip().split()[0]
                    grub_dev = grub_disk[:-1]+","+gpartnum+")"
                    return grub_dev
                else:
                    self.Entropy.updateProgress(
                                            bold(" QA Warning: ")+brown("cannot match grub device with linux one!! Cannot properly configure kernel! Defaulting to (hd0,0)"),
                                            importance = 0,
                                            header = red("   ##")
                                        )
                    return "(hd0,0)"
            else:
                self.Entropy.updateProgress(
                                        bold(" QA Warning: ")+brown("cannot find generated device.map!! Cannot properly configure kernel! Defaulting to (hd0,0)"),
                                        importance = 0,
                                        header = red("   ##")
                                    )
                return "(hd0,0)"
        else:
            self.Entropy.updateProgress(
                                    bold(" QA Warning: ")+brown("cannot run df /boot!! Cannot properly configure kernel! Defaulting to (hd0,0)"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            return "(hd0,0)"

class PackageMaskingParser:

    def __init__(self, EquoInstance):

        if not isinstance(EquoInstance,EquoInterface):
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid Entropy Instance is needed")
        self.Entropy = EquoInstance

    def parse(self):

        self.etpMaskFiles = {
            'keywords': etpConst['confdir']+"/packages/package.keywords", # keywording configuration files
            'unmask': etpConst['confdir']+"/packages/package.unmask", # unmasking configuration files
            'mask': etpConst['confdir']+"/packages/package.mask", # masking configuration files
            'license_mask': etpConst['confdir']+"/packages/license.mask", # masking configuration files
            'repos_mask': {},
            'repos_license_whitelist': {}
        }
        # append repositories mask files
        for repoid in etpRepositoriesOrder:
            maskpath = os.path.join(etpRepositories[repoid]['dbpath'],etpConst['etpdatabasemaskfile'])
            wlpath = os.path.join(etpRepositories[repoid]['dbpath'],etpConst['etpdatabaselicwhitelistfile'])
            if os.path.isfile(maskpath) and os.access(maskpath,os.R_OK):
                self.etpMaskFiles['repos_mask'][repoid] = maskpath
            if os.path.isfile(wlpath) and os.access(wlpath,os.R_OK):
                self.etpMaskFiles['repos_license_whitelist'][repoid] = wlpath

        self.etpMtimeFiles = {
            'keywords_mtime': etpConst['dumpstoragedir']+"/keywords.mtime",
            'unmask_mtime': etpConst['dumpstoragedir']+"/unmask.mtime",
            'mask_mtime': etpConst['dumpstoragedir']+"/mask.mtime",
            'license_mask_mtime': etpConst['dumpstoragedir']+"/license_mask.mtime",
            'repos_mask': {},
            'repos_license_whitelist': {}
        }
        # append repositories mtime files
        for repoid in etpRepositoriesOrder:
            if repoid in self.etpMaskFiles['repos_mask']:
                self.etpMtimeFiles['repos_mask'][repoid] = etpConst['dumpstoragedir']+"/repo_"+repoid+"_"+etpConst['etpdatabasemaskfile']+".mtime"
            if repoid in self.etpMaskFiles['repos_license_whitelist']:
                self.etpMtimeFiles['repos_license_whitelist'][repoid] = etpConst['dumpstoragedir']+"/repo_"+repoid+"_"+etpConst['etpdatabaselicwhitelistfile']+".mtime"

        data = {}
        for item in self.etpMaskFiles:
            data[item] = eval('self.'+item+'_parser')()
        return data


    '''
    parser of package.keywords file
    '''
    def keywords_parser(self):

        self.__validateEntropyCache(self.etpMaskFiles['keywords'],self.etpMtimeFiles['keywords_mtime'])

        data = {
                'universal': set(),
                'packages': {},
                'repositories': {},
        }
        if os.path.isfile(self.etpMaskFiles['keywords']):
            f = open(self.etpMaskFiles['keywords'],"r")
            content = f.readlines()
            f.close()
            # filter comments and white lines
            content = [x.strip() for x in content if not x.startswith("#") and x.strip()]
            for line in content:
                keywordinfo = line.split()
                # skip wrong lines
                if len(keywordinfo) > 3:
                    sys.stderr.write(">> "+line+" << is invalid!!")
                    continue
                if len(keywordinfo) == 1: # inversal keywording, check if it's not repo=
                    # repo=?
                    if keywordinfo[0].startswith("repo="):
                        sys.stderr.write(">> "+line+" << is invalid!!")
                        continue
                    # atom? is it worth it? it would take a little bit to parse uhm... >50 entries...!?
                    #kinfo = keywordinfo[0]
                    if keywordinfo[0] == "**": keywordinfo[0] = "" # convert into entropy format
                    data['universal'].add(keywordinfo[0])
                    continue # needed?
                if len(keywordinfo) in (2,3): # inversal keywording, check if it's not repo=
                    # repo=?
                    if keywordinfo[0].startswith("repo="):
                        sys.stderr.write(">> "+line+" << is invalid!!")
                        continue
                    # add to repo?
                    items = keywordinfo[1:]
                    if keywordinfo[0] == "**": keywordinfo[0] = "" # convert into entropy format
                    reponame = [x for x in items if x.startswith("repo=") and (len(x.split("=")) == 2)]
                    if reponame:
                        reponame = reponame[0].split("=")[1]
                        if reponame not in data['repositories']:
                            data['repositories'][reponame] = {}
                        # repository unmask or package in repository unmask?
                        if keywordinfo[0] not in data['repositories'][reponame]:
                            data['repositories'][reponame][keywordinfo[0]] = set()
                        if len(items) == 1:
                            # repository unmask
                            data['repositories'][reponame][keywordinfo[0]].add('*')
                        else:
                            if "*" not in data['repositories'][reponame][keywordinfo[0]]:
                                item = [x for x in items if not x.startswith("repo=")]
                                data['repositories'][reponame][keywordinfo[0]].add(item[0])
                    else:
                        # it's going to be a faulty line!!??
                        if len(items) == 2: # can't have two items and no repo=
                            sys.stderr.write(">> "+line+" << is invalid!!")
                            continue
                        # add keyword to packages
                        if keywordinfo[0] not in data['packages']:
                            data['packages'][keywordinfo[0]] = set()
                        data['packages'][keywordinfo[0]].add(items[0])
        return data


    def unmask_parser(self):
        self.__validateEntropyCache(self.etpMaskFiles['unmask'],self.etpMtimeFiles['unmask_mtime'])

        data = set()
        if os.path.isfile(self.etpMaskFiles['unmask']):
            f = open(self.etpMaskFiles['unmask'],"r")
            content = f.readlines()
            f.close()
            # filter comments and white lines
            content = [x.strip() for x in content if not x.startswith("#") and x.strip()]
            for line in content:
                data.add(line)
        return data

    def mask_parser(self):
        self.__validateEntropyCache(self.etpMaskFiles['mask'],self.etpMtimeFiles['mask_mtime'])

        data = set()
        if os.path.isfile(self.etpMaskFiles['mask']):
            f = open(self.etpMaskFiles['mask'],"r")
            content = f.readlines()
            f.close()
            # filter comments and white lines
            content = [x.strip() for x in content if not x.startswith("#") and x.strip()]
            for line in content:
                data.add(line)
        return data

    def license_mask_parser(self):
        self.__validateEntropyCache(self.etpMaskFiles['license_mask'],self.etpMtimeFiles['license_mask_mtime'])

        data = set()
        if os.path.isfile(self.etpMaskFiles['license_mask']):
            f = open(self.etpMaskFiles['license_mask'],"r")
            content = f.readlines()
            f.close()
            # filter comments and white lines
            content = [x.strip() for x in content if not x.startswith("#") and x.strip()]
            for line in content:
                data.add(line)
        return data

    def repos_license_whitelist_parser(self):
        data = {}
        for repoid in self.etpMaskFiles['repos_license_whitelist']:
            data[repoid] = set()

            self.__validateEntropyCache(self.etpMaskFiles['repos_license_whitelist'][repoid],self.etpMtimeFiles['repos_license_whitelist'][repoid], repoid = repoid)

            if os.path.isfile(self.etpMaskFiles['repos_license_whitelist'][repoid]):
                f = open(self.etpMaskFiles['repos_license_whitelist'][repoid],"r")
                content = f.readlines()
                f.close()
                # filter comments and white lines
                content = [x.strip() for x in content if not x.startswith("#") and x.strip()]
                for mylicense in content:
                    data[repoid].add(mylicense)
        return data

    def repos_mask_parser(self):

        data = {}
        for repoid in self.etpMaskFiles['repos_mask']:

            data[repoid] = {}
            data[repoid]['branch'] = {}
            data[repoid]['*'] = set()

            self.__validateEntropyCache(self.etpMaskFiles['repos_mask'][repoid],self.etpMtimeFiles['repos_mask'][repoid], repoid = repoid)
            if os.path.isfile(self.etpMaskFiles['repos_mask'][repoid]):
                f = open(self.etpMaskFiles['repos_mask'][repoid],"r")
                content = f.readlines()
                f.close()
                # filter comments and white lines
                content = [x.strip() for x in content if not x.startswith("#") and x.strip() and len(x.split()) <= 2]
                for line in content:
                    line = line.split()
                    if len(line) == 1:
                        data[repoid]['*'].add(line[0])
                    else:
                        if not data[repoid]['branch'].has_key(line[1]):
                            data[repoid]['branch'][line[1]] = set()
                        data[repoid]['branch'][line[1]].add(line[0])
        return data

    '''
    internal functions
    '''

    def __removeRepoCache(self, repoid = None):
        if os.path.isdir(etpConst['dumpstoragedir']):
            if repoid:
                self.Entropy.repository_move_clear_cache(repoid)
            else:
                for repoid in etpRepositoriesOrder:
                    self.Entropy.repository_move_clear_cache(repoid)
        else:
            os.makedirs(etpConst['dumpstoragedir'])

    def __saveFileMtime(self,toread,tosaveinto):

        if not os.path.isfile(toread):
            currmtime = 0.0
        else:
            currmtime = os.path.getmtime(toread)

        if not os.path.isdir(etpConst['dumpstoragedir']):
            os.makedirs(etpConst['dumpstoragedir'],0775)
            const_setup_perms(etpConst['dumpstoragedir'],etpConst['entropygid'])

        f = open(tosaveinto,"w")
        f.write(str(currmtime))
        f.flush()
        f.close()
        os.chmod(tosaveinto,0664)
        if etpConst['entropygid'] != None:
            os.chown(tosaveinto,0,etpConst['entropygid'])


    def __validateEntropyCache(self, maskfile, mtimefile, repoid = None):

        if os.getuid() != 0: # can't validate if running as user, moreover users can't make changes, so...
            return

        # handle on-disk cache validation
        # in this case, repositories cache
        # if package.keywords is changed, we must destroy cache
        if not os.path.isfile(mtimefile):
            # we can't know if package.keywords has been updated
            # remove repositories caches
            self.__removeRepoCache(repoid = repoid)
            self.__saveFileMtime(maskfile,mtimefile)
        else:
            # check mtime
            try:
                f = open(mtimefile,"r")
                mtime = float(f.readline().strip())
                # compare with current mtime
                try:
                    currmtime = os.path.getmtime(maskfile)
                except OSError:
                    currmtime = 0.0
                if mtime != currmtime:
                    self.__removeRepoCache(repoid = repoid)
                    self.__saveFileMtime(maskfile,mtimefile)
            except:
                self.__removeRepoCache(repoid = repoid)
                self.__saveFileMtime(maskfile,mtimefile)


class Callable:
    def __init__(self, anycallable):
        self.__call__ = anycallable

class MultipartPostHandler(urllib2.BaseHandler):
    handler_order = urllib2.HTTPHandler.handler_order - 10 # needs to run first

    def http_request(self, request):

        import urllib
        doseq = 1

        data = request.get_data()
        if data is not None and type(data) != str:
            v_files = []
            v_vars = []
            try:
                 for(key, value) in data.items():
                     if type(value) == file:
                         v_files.append((key, value))
                     else:
                         v_vars.append((key, value))
            except TypeError:
                systype, value, traceback = sys.exc_info()
                raise TypeError, "not a valid non-string sequence or mapping object", traceback

            if len(v_files) == 0:
                data = urllib.urlencode(v_vars, doseq)
            else:
                boundary, data = self.multipart_encode(v_vars, v_files)

                contenttype = 'multipart/form-data; boundary=%s' % boundary
                if(request.has_header('Content-Type')
                   and request.get_header('Content-Type').find('multipart/form-data') != 0):
                    print "Replacing %s with %s" % (request.get_header('content-type'), 'multipart/form-data')
                request.add_unredirected_header('Content-Type', contenttype)
            request.add_data(data)
        return request

    def multipart_encode(vars, files, boundary = None, buf = None):

        from cStringIO import StringIO
        import mimetools, mimetypes

        if boundary is None:
            boundary = mimetools.choose_boundary()
        if buf is None:
            buf = StringIO()
        for(key, value) in vars:
            buf.write('--%s\r\n' % boundary)
            buf.write('Content-Disposition: form-data; name="%s"' % key)
            buf.write('\r\n\r\n' + value + '\r\n')
        for(key, fd) in files:
            file_size = os.fstat(fd.fileno())[stat.ST_SIZE]
            filename = fd.name.split('/')[-1]
            contenttype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            buf.write('--%s\r\n' % boundary)
            buf.write('Content-Disposition: form-data; name="%s"; filename="%s"\r\n' % (key, filename))
            buf.write('Content-Type: %s\r\n' % contenttype)
            # buffer += 'Content-Length: %s\r\n' % file_size
            fd.seek(0)
            buf.write('\r\n' + fd.read() + '\r\n')
        buf.write('--' + boundary + '--\r\n\r\n')
        buf = buf.getvalue()
        return boundary, buf
    multipart_encode = Callable(multipart_encode)

    https_request = http_request

class ErrorReportInterface:

    def __init__(self, post_url = etpConst['handlers']['errorsend']):
        self.url = post_url
        self.opener = urllib2.build_opener(MultipartPostHandler)
        self.generated = False
        self.params = {}

        if etpConst['proxy']:
            proxy_support = urllib2.ProxyHandler(etpConst['proxy'])
            opener = urllib2.build_opener(proxy_support)
            urllib2.install_opener(opener)

    def prepare(self, tb_text, name, email, report_data = "", description = ""):
        self.params['arch'] = etpConst['currentarch']
        self.params['stacktrace'] = tb_text
        self.params['name'] = name
        self.params['email'] = email
        self.params['version'] = etpConst['entropyversion']
        self.params['errordata'] = report_data
        self.params['description'] = description
        self.params['arguments'] = ' '.join(sys.argv)
        self.params['uid'] = etpConst['uid']
        self.params['system_version'] = "N/A"
        if os.access(etpConst['systemreleasefile'],os.R_OK):
            f = open(etpConst['systemreleasefile'],"r")
            self.params['system_version'] = f.readlines()
            f.close()
        try:
            self.params['processes'] = commands.getoutput('ps auxf')
            self.params['lspci'] = commands.getoutput('lspci')
            self.params['dmesg'] = commands.getoutput('dmesg')
        except:
            pass
        self.generated = True

    # params is a dict, key(HTTP post item name): value
    def submit(self):
        if self.generated:
            result = self.opener.open(self.url, self.params).read()
            if result.strip() == "1":
                return True
            return False
        else:
            raise exceptionTools.PermissionDenied("PermissionDenied: not yet prepared")


'''
   ~~ GIVES YOU WINGS ~~
'''
class SecurityInterface:

    # thanks to Gentoo "gentoolkit" package, License below:

    # This program is licensed under the GPL, version 2

    # WARNING: this code is only tested by a few people and should NOT be used
    # on production systems at this stage. There are possible security holes and probably
    # bugs in this code. If you test it please report ANY success or failure to
    # me (genone@gentoo.org).

    # The following planned features are currently on hold:
    # - getting GLSAs from http/ftp servers (not really useful without the fixed ebuilds)
    # - GPG signing/verification (until key policy is clear)

    def __init__(self, EquoInstance):

        if not isinstance(EquoInstance,EquoInterface):
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid Entropy Instance is needed")
        self.Entropy = EquoInstance
        self.lastfetch = None
        self.previous_checksum = "0"
        self.advisories_changed = None
        self.adv_metadata = None
        self.affected_atoms = None

        from xml.dom import minidom
        self.minidom = minidom

        self.op_mappings = {
                            "le": "<=",
                            "lt": "<",
                            "eq": "=",
                            "gt": ">",
                            "ge": ">=",
                            "rge": ">=", # >=~
                            "rle": "<=", # <=~
                            "rgt": ">", # >~
                            "rlt": "<" # <~
        }

        self.unpackdir = os.path.join(etpConst['entropyunpackdir'],"security-"+str(self.Entropy.entropyTools.getRandomNumber()))
        self.security_url = etpConst['securityurl']
        self.unpacked_package = os.path.join(self.unpackdir,"glsa_package")
        self.security_url_checksum = etpConst['securityurl']+etpConst['packageshashfileext']
        self.download_package = os.path.join(self.unpackdir,os.path.basename(etpConst['securityurl']))
        self.download_package_checksum = self.download_package+etpConst['packageshashfileext']
        self.old_download_package_checksum = os.path.join(etpConst['dumpstoragedir'],os.path.basename(etpConst['securityurl']))+etpConst['packageshashfileext']

        self.security_package = os.path.join(etpConst['securitydir'],os.path.basename(etpConst['securityurl']))
        self.security_package_checksum = self.security_package+etpConst['packageshashfileext']

        try:
            if os.path.isfile(etpConst['securitydir']) or os.path.islink(etpConst['securitydir']):
                os.remove(etpConst['securitydir'])
            if not os.path.isdir(etpConst['securitydir']):
                os.makedirs(etpConst['securitydir'],0775)
        except OSError:
            pass
        const_setup_perms(etpConst['securitydir'],etpConst['entropygid'])

        if os.path.isfile(self.old_download_package_checksum):
            f = open(self.old_download_package_checksum)
            try:
                self.previous_checksum = f.readline().strip().split()[0]
            except:
                pass
            f.close()

    def __prepare_unpack(self):

        if os.path.isfile(self.unpackdir) or os.path.islink(self.unpackdir):
            os.remove(self.unpackdir)
        if os.path.isdir(self.unpackdir):
            shutil.rmtree(self.unpackdir,True)
            try:
                os.rmdir(self.unpackdir)
            except OSError:
                pass
        os.makedirs(self.unpackdir,0775)
        const_setup_perms(self.unpackdir,etpConst['entropygid'])

    def __download_glsa_package(self):
        return self.__generic_download(self.security_url, self.download_package)

    def __download_glsa_package_checksum(self):
        return self.__generic_download(self.security_url_checksum, self.download_package_checksum, showSpeed = False)

    def __generic_download(self, url, save_to, showSpeed = True):
        fetchConn = self.Entropy.urlFetcher(url, save_to, resume = False, showSpeed = showSpeed)
        fetchConn.progress = self.Entropy.progress
        rc = fetchConn.download()
        del fetchConn
        if rc in ("-1","-2","-3"):
            return False
        # setup permissions
        self.Entropy.setup_default_file_perms(save_to)
        return True

    def __verify_checksum(self):

        # read checksum
        if not os.path.isfile(self.download_package_checksum) or not os.access(self.download_package_checksum,os.R_OK):
            return 1

        f = open(self.download_package_checksum)
        try:
            checksum = f.readline().strip().split()[0]
            f.close()
        except:
            return 2

        if checksum == self.previous_checksum:
            self.advisories_changed = False
        else:
            self.advisories_changed = True
        md5res = self.Entropy.entropyTools.compareMd5(self.download_package,checksum)
        if not md5res:
            return 3
        return 0

    def __unpack_advisories(self):
        rc = self.Entropy.entropyTools.uncompressTarBz2(
                                                            self.download_package,
                                                            self.unpacked_package,
                                                            catchEmpty = True
                                                        )
        const_setup_perms(self.unpacked_package,etpConst['entropygid'])
        return rc

    def __clear_previous_advisories(self):
        if os.listdir(etpConst['securitydir']):
            shutil.rmtree(etpConst['securitydir'],True)
            if not os.path.isdir(etpConst['securitydir']):
                os.makedirs(etpConst['securitydir'],0775)
            const_setup_perms(self.unpackdir,etpConst['entropygid'])

    def __put_advisories_in_place(self):
        for advfile in os.listdir(self.unpacked_package):
            from_file = os.path.join(self.unpacked_package,advfile)
            to_file = os.path.join(etpConst['securitydir'],advfile)
            shutil.move(from_file,to_file)

    def __cleanup_garbage(self):
        shutil.rmtree(self.unpackdir,True)

    def clear(self, xcache = False):
        self.adv_metadata = None
        if xcache:
            self.Entropy.clear_dump_cache(etpCache['advisories'])

    def __get_advisories_cache(self):

        if self.adv_metadata != None:
            return self.adv_metadata

        if self.Entropy.xcache:
            dir_checksum = self.Entropy.entropyTools.md5sum_directory(etpConst['securitydir'])
            c_hash = str(hash(etpConst['branch'])) + \
                     str(hash(dir_checksum)) + \
                     str(hash(etpConst['systemroot']))
            c_hash = str(hash(c_hash))
            adv_metadata = self.Entropy.dumpTools.loadobj(etpCache['advisories']+c_hash)
            if adv_metadata != None:
                self.adv_metadata = adv_metadata.copy()
                return self.adv_metadata

    def __set_advisories_cache(self, adv_metadata):
        if self.Entropy.xcache:
            dir_checksum = self.Entropy.entropyTools.md5sum_directory(etpConst['securitydir'])
            c_hash = str(hash(etpConst['branch'])) + \
                     str(hash(dir_checksum)) + \
                     str(hash(etpConst['systemroot']))
            c_hash = str(hash(c_hash))
            try:
                self.Entropy.dumpTools.dumpobj(etpCache['advisories']+c_hash,adv_metadata)
            except IOError:
                pass

    def get_advisories_list(self):
        if not self.check_advisories_availability():
            return []
        xmls = os.listdir(etpConst['securitydir'])
        xmls = [x for x in xmls if x.endswith(".xml") and x.startswith("glsa-")]
        xmls.sort()
        return xmls

    def get_advisories_metadata(self):

        cached = self.__get_advisories_cache()
        if cached != None:
            return cached

        adv_metadata = {}
        xmls = self.get_advisories_list()
        maxlen = len(xmls)
        count = 0
        for xml in xmls:

            count += 1
            if not etpUi['quiet']: self.Entropy.updateProgress(":: "+str(round((float(count)/maxlen)*100,1))+"% ::", importance = 0, type = "info", back = True)

            xml_metadata = None
            exc_string = ""
            exc_err = ""
            try:
                xml_metadata = self.get_xml_metadata(xml)
            except KeyboardInterrupt:
                return {}
            except Exception, e:
                exc_string = str(Exception)
                exc_err = str(e)
            if xml_metadata == None:
                more_info = ""
                if exc_string:
                    more_info = " Error: %s: %s" % (exc_string,exc_err,)
                self.Entropy.updateProgress(
                                        blue("Warning: ")+bold(xml)+blue(" advisory is broken !") + more_info,
                                        importance = 1,
                                        type = "warning",
                                        header = red(" !!! ")
                                    )
                continue
            elif not xml_metadata:
                continue
            adv_metadata.update(xml_metadata)

        adv_metadata = self.filter_advisories(adv_metadata)
        self.__set_advisories_cache(adv_metadata)
        self.adv_metadata = adv_metadata.copy()
        return adv_metadata

    # this function filters advisories for packages that aren't
    # in the repositories. Note: only keys will be matched
    def filter_advisories(self, adv_metadata):
        keys = adv_metadata.keys()
        for key in keys:
            valid = True
            if adv_metadata[key]['affected']:
                affected = adv_metadata[key]['affected']
                affected_keys = affected.keys()
                valid = False
                skipping_keys = set()
                for a_key in affected_keys:
                    match = self.Entropy.atomMatch(a_key)
                    if match[0] != -1:
                        # it's in the repos, it's valid
                        valid = True
                    else:
                        skipping_keys.add(a_key)
                if not valid:
                    del adv_metadata[key]
                for a_key in skipping_keys:
                    try:
                        del adv_metadata[key]['affected'][a_key]
                    except KeyError:
                        pass
                try:
                    if not adv_metadata[key]['affected']:
                        del adv_metadata[key]
                except KeyError:
                    pass

        return adv_metadata

    def is_affected(self, adv_key, adv_data = {}):
        if not adv_data:
            adv_data = self.get_advisories_metadata()
        if adv_key not in adv_data:
            return False
        mydata = adv_data[adv_key].copy()
        del adv_data

        if not mydata['affected']:
            return False

        for key in mydata['affected']:

            vul_atoms = mydata['affected'][key][0]['vul_atoms']
            unaff_atoms = mydata['affected'][key][0]['unaff_atoms']
            unaffected_atoms = set()
            if not vul_atoms:
                return False
            # XXX: does multimatch work correctly?
            for atom in unaff_atoms:
                matches = self.Entropy.clientDbconn.atomMatch(atom, multiMatch = True)
                if matches[1] == 0:
                    for idpackage in matches[0]:
                        unaffected_atoms.add((idpackage,0))

            for atom in vul_atoms:
                match = self.Entropy.clientDbconn.atomMatch(atom)
                if (match[0] != -1) and (match not in unaffected_atoms):
                    if self.affected_atoms == None:
                        self.affected_atoms = set()
                    self.affected_atoms.add(atom)
                    return True
        return False

    def get_vulnerabilities(self):
        return self.get_affection()

    def get_fixed_vulnerabilities(self):
        return self.get_affection(affected = False)

    # if not affected: not affected packages will be returned
    # if affected: affected packages will be returned
    def get_affection(self, affected = True):
        adv_data = self.get_advisories_metadata()
        adv_data_keys = adv_data.keys()
        valid_keys = set()
        for adv in adv_data_keys:
            is_affected = self.is_affected(adv,adv_data)
            if affected == is_affected:
                valid_keys.add(adv)
        # we need to filter our adv_data and return
        for key in adv_data_keys:
            if key not in valid_keys:
                try:
                    del adv_data[key]
                except KeyError:
                    pass
        # now we need to filter packages in adv_dat
        for adv in adv_data:
            for key in adv_data[adv]['affected'].keys():
                #print key
                atoms = adv_data[adv]['affected'][key][0]['vul_atoms']
                #print atoms
                applicable = True
                for atom in atoms:
                    if atom in self.affected_atoms:
                        applicable = False
                        break
                if applicable == affected:
                    del adv_data[adv]['affected'][key]
        return adv_data

    def get_affected_atoms(self):
        adv_data = self.get_advisories_metadata()
        adv_data_keys = adv_data.keys()
        del adv_data
        self.affected_atoms = set()
        for key in adv_data_keys:
            self.is_affected(key)
        return self.affected_atoms

    def get_xml_metadata(self, xmlfilename):
        xml_data = {}
        xmlfile = os.path.join(etpConst['securitydir'],xmlfilename)
        try:
            xmldoc = self.minidom.parse(xmlfile)
        except:
            return None

        # get base data
        glsa_tree = xmldoc.getElementsByTagName("glsa")[0]
        glsa_product = glsa_tree.getElementsByTagName("product")[0]
        if glsa_product.getAttribute("type") != "ebuild":
            return {}

        glsa_id = glsa_tree.getAttribute("id")
        glsa_title = glsa_tree.getElementsByTagName("title")[0].firstChild.data
        glsa_synopsis = glsa_tree.getElementsByTagName("synopsis")[0].firstChild.data
        glsa_announced = glsa_tree.getElementsByTagName("announced")[0].firstChild.data
        glsa_revised = glsa_tree.getElementsByTagName("revised")[0].firstChild.data

        xml_data['filename'] = xmlfilename
        xml_data['title'] = glsa_title.strip()
        xml_data['synopsis'] = glsa_synopsis.strip()
        xml_data['announced'] = glsa_announced.strip()
        xml_data['revised'] = glsa_revised.strip()
        xml_data['bugs'] = [x.firstChild.data.strip() for x in glsa_tree.getElementsByTagName("bug")]
        xml_data['access'] = ""
        try:
            xml_data['access'] = glsa_tree.getElementsByTagName("access")[0].firstChild.data.strip()
        except IndexError:
            pass

        # references
        references = glsa_tree.getElementsByTagName("references")[0]
        xml_data['references'] = [x.getAttribute("link").strip() for x in references.getElementsByTagName("uri")]

        try:
            description = glsa_tree.getElementsByTagName("description")[0]
            xml_data['description'] = description.getElementsByTagName("p")[0].firstChild.data.strip()
        except IndexError:
            xml_data['description'] = ""
        try:
            workaround = glsa_tree.getElementsByTagName("workaround")[0]
            xml_data['workaround'] = workaround.getElementsByTagName("p")[0].firstChild.data.strip()
        except IndexError:
            xml_data['workaround'] = ""

        try:
            xml_data['resolution'] = []
            resolution = glsa_tree.getElementsByTagName("resolution")[0]
            p_elements = resolution.getElementsByTagName("p")
            for p_elem in p_elements:
                xml_data['resolution'].append(p_elem.firstChild.data.strip())
        except IndexError:
            xml_data['resolution'] = []

        try:
            impact = glsa_tree.getElementsByTagName("impact")[0]
            xml_data['impact'] = impact.getElementsByTagName("p")[0].firstChild.data.strip()
        except IndexError:
            xml_data['impact'] = ""
        xml_data['impacttype'] = glsa_tree.getElementsByTagName("impact")[0].getAttribute("type").strip()

        try:
            background = glsa_tree.getElementsByTagName("background")[0]
            xml_data['background'] = background.getElementsByTagName("p")[0].firstChild.data.strip()
        except IndexError:
            xml_data['background'] = ""

        # affection information
        affected = glsa_tree.getElementsByTagName("affected")[0]
        affected_packages = {}
        # we will then filter affected_packages using repositories information
        # if not affected_packages: advisory will be dropped
        for p in affected.getElementsByTagName("package"):
            name = p.getAttribute("name")
            if not affected_packages.has_key(name):
                affected_packages[name] = []

            pdata = {}
            pdata["arch"] = p.getAttribute("arch").strip()
            pdata["auto"] = (p.getAttribute("auto") == "yes")
            pdata["vul_vers"] = [self.__make_version(v) for v in p.getElementsByTagName("vulnerable")]
            pdata["unaff_vers"] = [self.__make_version(v) for v in p.getElementsByTagName("unaffected")]
            pdata["vul_atoms"] = [self.__make_atom(name, v) for v in p.getElementsByTagName("vulnerable")]
            pdata["unaff_atoms"] = [self.__make_atom(name, v) for v in p.getElementsByTagName("unaffected")]
            affected_packages[name].append(pdata)
        xml_data['affected'] = affected_packages.copy()

        return {glsa_id: xml_data}

    def __make_version(self, vnode):
        """
        creates from the information in the I{versionNode} a 
        version string (format <op><version>).

        @type	vnode: xml.dom.Node
        @param	vnode: a <vulnerable> or <unaffected> Node that
                                                    contains the version information for this atom
        @rtype:		String
        @return:	the version string
        """
        return self.op_mappings[vnode.getAttribute("range")] + vnode.firstChild.data.strip()

    def __make_atom(self, pkgname, vnode):
        """
        creates from the given package name and information in the 
        I{versionNode} a (syntactical) valid portage atom.

        @type	pkgname: String
        @param	pkgname: the name of the package for this atom
        @type	vnode: xml.dom.Node
        @param	vnode: a <vulnerable> or <unaffected> Node that
                                                    contains the version information for this atom
        @rtype:		String
        @return:	the portage atom
        """
        return str(self.op_mappings[vnode.getAttribute("range")] + pkgname + "-" + vnode.firstChild.data.strip())

    def check_advisories_availability(self):
        if not os.path.lexists(etpConst['securitydir']):
            return False
        if not os.path.isdir(etpConst['securitydir']):
            return False
        else:
            return True
        return False

    def fetch_advisories(self):

        self.Entropy.updateProgress(
                                blue("Testing ")+bold("Security Advisories")+blue(" service connection"),
                                importance = 2,
                                type = "info",
                                header = red("@@ "),
                                footer = red(" ...")
                            )

        # Test network connectivity
        conntest = self.Entropy.entropyTools.get_remote_data(etpConst['conntestlink'])
        if not conntest:
            raise exceptionTools.OnlineMirrorError("OnlineMirrorError: Cannot connect to %s" % (etpConst['conntestlink'],))

        self.Entropy.updateProgress(
                                blue("Getting the latest ")+bold("Security Advisories")+darkgreen(" (GLSAs)"),
                                importance = 2,
                                type = "info",
                                header = red("@@ "),
                                footer = red(" ...")
                            )

        gave_up = self.Entropy.sync_loop_check(self.Entropy._resources_run_check_lock)
        if gave_up:
            return 7

        # lock
        self.Entropy._resources_run_create_lock()
        try:
            rc = self.run_fetch()
        except:
            self.Entropy._resources_run_remove_lock()
            raise
        if rc != 0: return rc

        self.Entropy._resources_run_remove_lock()

        if self.advisories_changed:
            advtext = darkgreen("Security Advisories: updated successfully")
        else:
            advtext = darkred("Security Advisories: already up to date")

        self.Entropy.updateProgress(
                                advtext,
                                importance = 2,
                                type = "info",
                                header = red("@@ ")
                            )

        return 0

    def run_fetch(self):
        # prepare directories
        self.__prepare_unpack()

        # download package
        status = self.__download_glsa_package()
        self.lastfetch = status
        if not status:
            self.Entropy.updateProgress(
                                    blue("Security Advisories: unable to download package, sorry."),
                                    importance = 2,
                                    type = "error",
                                    header = red("   ## ")
                                )
            self.Entropy._resources_run_remove_lock()
            return 1

        self.Entropy.updateProgress(
                                blue("Verifying checksum"),
                                importance = 1,
                                type = "info",
                                header = red("   # "),
                                footer = red(" ..."),
                                back = True
                            )

        # download digest
        status = self.__download_glsa_package_checksum()
        if not status:
            self.Entropy.updateProgress(
                                    blue("Security Advisories: cannot download checksum, sorry."),
                                    importance = 2,
                                    type = "error",
                                    header = red("   ## ")
                                )
            self.Entropy._resources_run_remove_lock()
            return 2

        # verify digest
        status = self.__verify_checksum()

        if status == 1:
            self.Entropy.updateProgress(
                                    blue("Security Advisories: cannot open packages, sorry."),
                                    importance = 2,
                                    type = "error",
                                    header = red("   ## ")
                                )
            self.Entropy._resources_run_remove_lock()
            return 3
        elif status == 2:
            self.Entropy.updateProgress(
                                    blue("Security Advisories: cannot read checksum, sorry."),
                                    importance = 2,
                                    type = "error",
                                    header = red("   ## ")
                                )
            self.Entropy._resources_run_remove_lock()
            return 4
        elif status == 3:
            self.Entropy.updateProgress(
                                    blue("Security Advisories: digest verification failed, sorry."),
                                    importance = 2,
                                    type = "error",
                                    header = red("   ## ")
                                )
            self.Entropy._resources_run_remove_lock()
            return 5
        elif status == 0:
            self.Entropy.updateProgress(
                                    darkgreen("Verification Successful"),
                                    importance = 1,
                                    type = "info",
                                    header = red("   # ")
                                )
        else:
            raise exceptionTools.InvalidData("InvalidData: return status not valid.")

        # save downloaded md5
        if os.path.isfile(self.download_package_checksum) and os.path.isdir(etpConst['dumpstoragedir']):
            if os.path.isfile(self.old_download_package_checksum):
                os.remove(self.old_download_package_checksum)
            shutil.copy2(self.download_package_checksum,self.old_download_package_checksum)
            self.Entropy.setup_default_file_perms(self.old_download_package_checksum)

        # now unpack in place
        status = self.__unpack_advisories()
        if status != 0:
            self.Entropy.updateProgress(
                                    blue("Security Advisories: digest verification failed, try again later."),
                                    importance = 2,
                                    type = "error",
                                    header = red("   ## ")
                                )
            self.Entropy._resources_run_remove_lock()
            return 6

        self.Entropy.updateProgress(
                                darkgreen("Installing Security Advisories"),
                                importance = 1,
                                type = "info",
                                header = red("   # "),
                                footer = red(" ...")
                            )

        # clear previous
        self.__clear_previous_advisories()
        # copy over
        self.__put_advisories_in_place()
        # remove temp stuff
        self.__cleanup_garbage()
        return 0

class SpmInterface:

    def __init__(self, OutputInterface):
        if not isinstance(OutputInterface, (EquoInterface, TextInterface)):
            if OutputInterface == None:
                OutputInterface = TextInterface()
            else:
                raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid TextInterface based instance is needed")

        self.spm_backend = etpConst['spm']['backend']
        self.valid_backends = etpConst['spm']['available_backends']
        if self.spm_backend not in self.valid_backends:
            raise exceptionTools.IncorrectParameter("IncorrectParameter: invalid backend %s" % (self.spm_backend,))

        if self.spm_backend == "portage":
            self.intf = PortageInterface(OutputInterface)

    @staticmethod
    def get_spm_interface():
        backend = etpConst['spm']['backend']
        if backend == "portage":
            return PortageInterface

class PortageInterface:

    import entropyTools

    class paren_normalize(list):
        """Take a dependency structure as returned by paren_reduce or use_reduce
        and generate an equivalent structure that has no redundant lists."""
        def __init__(self, src):
            list.__init__(self)
            self._zap_parens(src, self)

        def _zap_parens(self, src, dest, disjunction=False):
            if not src:
                return dest
            i = iter(src)
            for x in i:
                if isinstance(x, basestring):
                    if x == '||':
                        x = self._zap_parens(i.next(), [], disjunction=True)
                        if len(x) == 1:
                            dest.append(x[0])
                        else:
                            dest.append("||")
                            dest.append(x)
                    elif x.endswith("?"):
                        dest.append(x)
                        dest.append(self._zap_parens(i.next(), []))
                    else:
                        dest.append(x)
                else:
                    if disjunction:
                        x = self._zap_parens(x, [])
                        if len(x) == 1:
                            dest.append(x[0])
                        else:
                            dest.append(x)
                    else:
                        self._zap_parens(x, dest)
            return dest

    def __init__(self, OutputInterface):
        if not isinstance(OutputInterface, (EquoInterface, TextInterface)):
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid TextInterface based instance is needed")

        # interface only needed OutputInterface functions
        self.updateProgress = OutputInterface.updateProgress
        self.askQuestion = OutputInterface.askQuestion

        # importing portage stuff
        import portage
        self.portage = portage
        try:
            import portage_const
        except ImportError:
            import portage.const as portage_const
        self.portage_const = portage_const

    def get_third_party_mirrors(self, mirrorname):
        x = []
        if self.portage.thirdpartymirrors.has_key(mirrorname):
            x = self.portage.thirdpartymirrors[mirrorname]
        return x

    def get_spm_setting(self, var):
        return self.portage.settings[var]

    # Packages in system (in the Portage language -> emerge system, remember?)
    def get_atoms_in_system(self):
        system = self.portage.settings.packages
        sysoutput = []
        for x in system:
            y = self.get_installed_atoms(x)
            if (y != None):
                for z in y:
                    sysoutput.append(z)
        sysoutput.extend(etpConst['spm']['system_packages']) # add our packages
        return sysoutput

    def get_config_protect_and_mask(self):
        config_protect = self.portage.settings['CONFIG_PROTECT']
        config_protect = config_protect.split()
        config_protect_mask = self.portage.settings['CONFIG_PROTECT_MASK']
        config_protect_mask = config_protect_mask.split()
        # explode
        protect = []
        for x in config_protect:
            x = os.path.expandvars(x)
            protect.append(x)
        mask = []
        for x in config_protect_mask:
            x = os.path.expandvars(x)
            mask.append(x)
        return ' '.join(protect),' '.join(mask)

    # resolve atoms automagically (best, not current!)
    # sys-libs/application --> sys-libs/application-1.2.3-r1
    def get_best_atom(self, atom, match = "bestmatch-visible"):
        try:
            return self.portage.portdb.xmatch(match,str(atom))
        except ValueError:
            return None

    # same as above but includes masked ebuilds
    def get_best_masked_atom(self, atom):
        atoms = self.portage.portdb.xmatch("match-all",str(atom))
        # find the best
        try:
            from portage_versions import best
        except ImportError:
            from portage.versions import best
        return best(atoms)

    def get_atom_category(self, atom):
        try:
            return self.portage.portdb.xmatch("match-all",str(atom))[0].split("/")[0]
        except:
            return None

    def _get_portage_vartree(self, root):

        if not etpConst['spm']['cache'].has_key('portage'):
            etpConst['spm']['cache']['portage'] = {}
        if not etpConst['spm']['cache']['portage'].has_key('vartree'):
            etpConst['spm']['cache']['portage']['vartree'] = {}

        cached = etpConst['spm']['cache']['portage']['vartree'].get(root)
        if cached != None:
            return cached

        mytree = self.portage.vartree(root=root)
        etpConst['spm']['cache']['portage']['vartree'][root] = mytree
        return mytree

    def _get_portage_config(self, config_root, root):

        if not etpConst['spm']['cache'].has_key('portage'):
            etpConst['spm']['cache']['portage'] = {}
        if not etpConst['spm']['cache']['portage'].has_key('config'):
            etpConst['spm']['cache']['portage']['config'] = {}

        cached = etpConst['spm']['cache']['portage']['config'].get((config_root,root))
        if cached != None:
            return cached

        mysettings = self.portage.config(config_root = config_root, target_root = root, config_incrementals = self.portage_const.INCREMENTALS)
        etpConst['spm']['cache']['portage']['config'][(config_root,root)] = mysettings
        return mysettings

    # please always force =pkgcat/pkgname-ver if possible
    def get_installed_atom(self, atom):
        mypath = etpConst['systemroot']+"/"
        mytree = self._get_portage_vartree(mypath)
        rc = mytree.dep_match(str(atom))
        if rc:
            return rc[-1]
        return None

    def get_package_slot(self, atom):
        mypath = etpConst['systemroot']+"/"
        mytree = self._get_portage_vartree(mypath)
        if atom.startswith("="):
            atom = atom[1:]
        rc = mytree.getslot(atom)
        if rc:
            return rc
        return None

    def get_installed_atoms(self, atom):
        mypath = etpConst['systemroot']+"/"
        mytree = self._get_portage_vartree(mypath)
        rc = mytree.dep_match(str(atom))
        if rc:
            return rc
        return None

    # create a .tbz2 file in the specified path
    def quickpkg(self, atom, dirpath):

        # getting package info
        pkgname = atom.split("/")[1]
        pkgcat = atom.split("/")[0]
        #pkgfile = pkgname+".tbz2"
        if not os.path.isdir(dirpath):
            os.makedirs(dirpath)
        dirpath += "/"+pkgname+etpConst['packagesext']
        dbdir = self.get_vdb_path()+"/"+pkgcat+"/"+pkgname+"/"

        import tarfile
        import stat
        trees = self.portage.db["/"]
        vartree = trees["vartree"]
        dblnk = self.portage.dblink(pkgcat, pkgname, "/", vartree.settings, treetype="vartree", vartree=vartree)
        dblnk.lockdb()
        tar = tarfile.open(dirpath,"w:bz2")

        contents = dblnk.getcontents()
        id_strings = {}
        paths = contents.keys()
        paths.sort()

        for path in paths:
            try:
                exist = os.lstat(path)
            except OSError:
                continue # skip file
            ftype = contents[path][0]
            lpath = path
            arcname = path[1:]
            if 'dir' == ftype and \
                not stat.S_ISDIR(exist.st_mode) and \
                os.path.isdir(lpath):
                lpath = os.path.realpath(lpath)
            tarinfo = tar.gettarinfo(lpath, arcname)
            tarinfo.uname = id_strings.setdefault(tarinfo.uid, str(tarinfo.uid))
            tarinfo.gname = id_strings.setdefault(tarinfo.gid, str(tarinfo.gid))

            if stat.S_ISREG(exist.st_mode):
                tarinfo.type = tarfile.REGTYPE
                f = open(path)
                try:
                    tar.addfile(tarinfo, f)
                finally:
                    f.close()
            else:
                tar.addfile(tarinfo)

        tar.close()

        # appending xpak informations
        import etpXpak
        tbz2 = etpXpak.tbz2(dirpath)
        tbz2.recompose(dbdir)

        dblnk.unlockdb()

        if os.path.isfile(dirpath):
            return dirpath
        else:
            raise exceptionTools.FileNotFound("FileNotFound: Spm:quickpkg error: %s not found" % (dirpath,))

    def get_useflags(self):
        return self.portage.settings['USE']

    def get_useflags_force(self):
        return self.portage.settings.useforce

    def get_useflags_mask(self):
        return self.portage.settings.usemask

    def get_package_setting(self, atom, setting):
        myatom = atom[:]
        if myatom.startswith("="):
            myatom = myatom[1:]
        return self.portage.portdb.aux_get(myatom,[setting])[0]

    def query_belongs(self, filename):
        mypath = etpConst['systemroot']+"/"
        mytree = self._get_portage_vartree(mypath)
        packages = mytree.dbapi.cpv_all()
        matches = set()
        for package in packages:
            mysplit = package.split("/")
            content = self.portage.dblink(mysplit[0], mysplit[1], mypath, self.portage.settings).getcontents()
            if filename in content:
                matches.add(package)
        return matches

    def calculate_dependencies(self, my_iuse, my_use, my_license, my_depend, my_rdepend, my_pdepend, my_provide, my_src_uri):
        metadata = {}
        metadata['USE'] = my_use
        metadata['IUSE'] = my_iuse
        metadata['LICENSE'] = my_license
        metadata['DEPEND'] = my_depend
        metadata['PDEPEND'] = my_pdepend
        metadata['RDEPEND'] = my_rdepend
        metadata['PROVIDE'] = my_provide
        metadata['SRC_URI'] = my_src_uri
        use = metadata['USE'].split()
        raw_use = use
        iuse = set(metadata['IUSE'].split())
        use = [f for f in use if f in iuse]
        use.sort()
        metadata['USE'] = " ".join(use)
        for k in "LICENSE", "RDEPEND", "DEPEND", "PDEPEND", "PROVIDE", "SRC_URI":
            try:
                deps = self.paren_reduce(metadata[k])
                deps = self.use_reduce(deps, uselist=raw_use)
                deps = self.paren_normalize(deps)
                if k == "LICENSE":
                    deps = self.paren_license_choose(deps)
                else:
                    deps = self.paren_choose(deps)
                deps = ' '.join(deps)
            except Exception, e:
                self.updateProgress(
                                        darkred("Error calculating Portage dependencies: %s: %s :: %s") % (str(Exception), k, str(e)) ,
                                        importance = 1,
                                        type = "error",
                                        header = red(" !!! ")
                                    )
                deps = ''
                continue
            metadata[k] = deps
        return metadata

    def paren_reduce(self, mystr,tokenize=1):
        """

            # deps.py -- Portage dependency resolution functions
            # Copyright 2003-2004 Gentoo Foundation
            # Distributed under the terms of the GNU General Public License v2
            # $Id: portage_dep.py 9174 2008-01-11 05:49:02Z zmedico $

        Take a string and convert all paren enclosed entities into sublists, optionally
        futher splitting the list elements by spaces.

        Example usage:
                >>> paren_reduce('foobar foo ( bar baz )',1)
                ['foobar', 'foo', ['bar', 'baz']]
                >>> paren_reduce('foobar foo ( bar baz )',0)
                ['foobar foo ', [' bar baz ']]

        @param mystr: The string to reduce
        @type mystr: String
        @param tokenize: Split on spaces to produces further list breakdown
        @type tokenize: Integer
        @rtype: Array
        @return: The reduced string in an array
        """
        mylist = []
        while mystr:
            left_paren = mystr.find("(")
            has_left_paren = left_paren != -1
            right_paren = mystr.find(")")
            has_right_paren = right_paren != -1
            if not has_left_paren and not has_right_paren:
                freesec = mystr
                subsec = None
                tail = ""
            elif mystr[0] == ")":
                return [mylist,mystr[1:]]
            elif has_left_paren and not has_right_paren:
                raise exceptionTools.InvalidDependString(
                        "missing right parenthesis: '%s'" % mystr)
            elif has_left_paren and left_paren < right_paren:
                freesec,subsec = mystr.split("(",1)
                subsec,tail = self.paren_reduce(subsec,tokenize)
            else:
                subsec,tail = mystr.split(")",1)
                if tokenize:
                    subsec = self.strip_empty(subsec.split(" "))
                    return [mylist+subsec,tail]
                return mylist+[subsec],tail
            mystr = tail
            if freesec:
                if tokenize:
                    mylist = mylist + self.strip_empty(freesec.split(" "))
                else:
                    mylist = mylist + [freesec]
            if subsec is not None:
                mylist = mylist + [subsec]
        return mylist

    def strip_empty(self, myarr):
        """

            # deps.py -- Portage dependency resolution functions
            # Copyright 2003-2004 Gentoo Foundation
            # Distributed under the terms of the GNU General Public License v2
            # $Id: portage_dep.py 9174 2008-01-11 05:49:02Z zmedico $

        Strip all empty elements from an array

        @param myarr: The list of elements
        @type myarr: List
        @rtype: Array
        @return: The array with empty elements removed
        """
        for x in range(len(myarr)-1, -1, -1):
                if not myarr[x]:
                        del myarr[x]
        return myarr

    def use_reduce(self, deparray, uselist=[], masklist=[], matchall=0, excludeall=[]):
        """

            # deps.py -- Portage dependency resolution functions
            # Copyright 2003-2004 Gentoo Foundation
            # Distributed under the terms of the GNU General Public License v2
            # $Id: portage_dep.py 9174 2008-01-11 05:49:02Z zmedico $

        Takes a paren_reduce'd array and reduces the use? conditionals out
        leaving an array with subarrays

        @param deparray: paren_reduce'd list of deps
        @type deparray: List
        @param uselist: List of use flags
        @type uselist: List
        @param masklist: List of masked flags
        @type masklist: List
        @param matchall: Resolve all conditional deps unconditionally.  Used by repoman
        @type matchall: Integer
        @rtype: List
        @return: The use reduced depend array
        """
        # Quick validity checks
        for x in range(len(deparray)):
            if deparray[x] in ["||","&&"]:
                if len(deparray) - 1 == x or not isinstance(deparray[x+1], list):
                    raise exceptionTools.InvalidDependString(deparray[x]+" missing atom list in \""+str(deparray)+"\"")
        if deparray and deparray[-1] and deparray[-1][-1] == "?":
            raise exceptionTools.InvalidDependString("Conditional without target in \""+str(deparray)+"\"")

        # This is just for use by emerge so that it can enable a backward compatibility
        # mode in order to gracefully deal with installed packages that have invalid
        # atoms or dep syntax.  For backward compatibility with api consumers, strict
        # behavior will be explicitly enabled as necessary.
        _dep_check_strict = False

        mydeparray = deparray[:]
        rlist = []
        while mydeparray:
            head = mydeparray.pop(0)

            if isinstance(head,list):
                additions = self.use_reduce(head, uselist, masklist, matchall, excludeall)
                if additions:
                    rlist.append(additions)
                elif rlist and rlist[-1] == "||":
                    #XXX: Currently some DEPEND strings have || lists without default atoms.
                    #	raise portage_exception.InvalidDependString("No default atom(s) in \""+paren_enclose(deparray)+"\"")
                    rlist.append([])
            else:
                if head[-1] == "?": # Use reduce next group on fail.
                    # Pull any other use conditions and the following atom or list into a separate array
                    newdeparray = [head]
                    while isinstance(newdeparray[-1], str) and newdeparray[-1][-1] == "?":
                        if mydeparray:
                            newdeparray.append(mydeparray.pop(0))
                        else:
                            raise ValueError, "Conditional with no target."

                    # Deprecation checks
                    warned = 0
                    if len(newdeparray[-1]) == 0:
                        self.updateProgress(
                                                darkred("PortageInterface.use_reduce(): Empty target in string. (Deprecated)"),
                                                importance = 0,
                                                type = "error",
                                                header = bold(" !!! ")
                                            )
                        warned = 1
                    if len(newdeparray) != 2:
                        self.updateProgress(
                                                darkred("PortageInterface.use_reduce(): Note: Nested use flags without parenthesis (Deprecated)"),
                                                importance = 0,
                                                type = "error",
                                                header = bold(" !!! ")
                                            )
                        warned = 1
                    if warned:
                        self.updateProgress(
                                                darkred("PortageInterface.use_reduce(): "+" ".join(map(str,[head]+newdeparray))),
                                                importance = 0,
                                                type = "error",
                                                header = bold(" !!! ")
                                            )

                    # Check that each flag matches
                    ismatch = True
                    missing_flag = False
                    for head in newdeparray[:-1]:
                        head = head[:-1]
                        if not head:
                            missing_flag = True
                            break
                        if head.startswith("!"):
                            head_key = head[1:]
                            if not head_key:
                                missing_flag = True
                                break
                            if not matchall and head_key in uselist or \
                                head_key in excludeall:
                                ismatch = False
                                break
                        elif head not in masklist:
                            if not matchall and head not in uselist:
                                    ismatch = False
                                    break
                        else:
                            ismatch = False
                    if missing_flag:
                        raise exceptionTools.InvalidDependString(
                                "Conditional without flag: \"" + \
                                str([head+"?", newdeparray[-1]])+"\"")

                    # If they all match, process the target
                    if ismatch:
                        target = newdeparray[-1]
                        if isinstance(target, list):
                            additions = self.use_reduce(target, uselist, masklist, matchall, excludeall)
                            if additions:
                                    rlist.append(additions)
                        elif not _dep_check_strict:
                            # The old deprecated behavior.
                            rlist.append(target)
                        else:
                            raise exceptionTools.InvalidDependString(
                                    "Conditional without parenthesis: '%s?'" % head)

                else:
                    rlist += [head]
        return rlist

    def paren_choose(self, dep_list):
        newlist = []
        do_skip = False
        for idx in range(len(dep_list)):

            if do_skip:
                do_skip = False
                continue

            item = dep_list[idx]
            if item == "||": # or
                next_item = dep_list[idx+1]
                if not next_item: # || ( asd? ( atom ) dsa? ( atom ) ) => [] if use asd and dsa are disabled
                    do_skip = True
                    continue
                item = self.dep_or_select(next_item) # must be a list
                if not item:
                    # no matches, transform to string and append, so reagent will fail
                    newlist.append(str(next_item))
                else:
                    newlist += item
                do_skip = True
            elif isinstance(item, list): # and
                item = self.dep_and_select(item)
                newlist += item
            else:
                newlist.append(item)

        return newlist

    def dep_and_select(self, and_list):
        do_skip = False
        newlist = []
        for idx in range(len(and_list)):

            if do_skip:
                do_skip = False
                continue

            x = and_list[idx]
            if x == "||":
                x = self.dep_or_select(and_list[idx+1])
                do_skip = True
                if not x:
                    x = str(and_list[idx+1])
                else:
                    newlist += x
            elif isinstance(x, list):
                x = self.dep_and_select(x)
                newlist += x
            else:
                newlist.append(x)

        # now verify if all are satisfied
        for x in newlist:
            match = self.get_installed_atom(x)
            if match == None:
                return []

        return newlist

    def dep_or_select(self, or_list):
        do_skip = False
        for idx in range(len(or_list)):
            if do_skip:
                do_skip = False
                continue
            x = or_list[idx]
            if x == "||": # or
                x = self.dep_or_select(or_list[idx+1])
                do_skip = True
            elif isinstance(x, list): # and
                x = self.dep_and_select(x)
                if not x:
                    continue
                # found
                return x
            else:
                x = [x]

            for y in x:
                match = self.get_installed_atom(y)
                if match != None:
                    return [y]

        return []

    def paren_license_choose(self, dep_list):

        newlist = set()
        for item in dep_list:

            if isinstance(item, list):
                # match the first
                data = set(self.paren_license_choose(item))
                newlist.update(data)
            else:
                if item not in ["||"]:
                    newlist.add(item)

        return list(newlist)

    def get_vdb_path(self):
        rc = etpConst['systemroot']+"/"+self.portage_const.VDB_PATH
        if (not rc.endswith("/")):
            return rc+"/"
        return rc

    def get_available_packages(self, categories = [], filter_reinstalls = True):
        mypath = etpConst['systemroot']+"/"
        mysettings = self._get_portage_config("/",mypath)
        portdb = self.portage.portdbapi(mysettings["PORTDIR"], mysettings = mysettings)
        cps = portdb.cp_all()
        visibles = set()
        for cp in cps:
            if categories and cp.split("/")[0] not in categories:
                continue
            # get slots
            slots = set()
            atoms = self.get_best_atom(cp, "match-visible")
            if atoms:
                for atom in atoms:
                    slots.add(portdb.aux_get(atom, ["SLOT"])[0])
                for slot in slots:
                    visibles.add(cp+":"+slot)
        del cps

        # now match visibles
        available = set()
        for visible in visibles:
            match = self.get_best_atom(visible)
            if match == None:
                continue
            if filter_reinstalls:
                installed = self.get_installed_atom(visible)
                # if not installed, installed == None
                if installed != match:
                    available.add(match)
            else:
                available.add(match)
        del visibles

        return available

    # Collect installed packages
    def get_installed_packages(self, dbdir = None):
        if not dbdir:
            appDbDir = self.get_vdb_path()
        else:
            appDbDir = dbdir
        dbDirs = os.listdir(appDbDir)
        installedAtoms = set()
        for pkgsdir in dbDirs:
            if os.path.isdir(appDbDir+pkgsdir):
                pkgdir = os.listdir(appDbDir+pkgsdir)
                for pdir in pkgdir:
                    pkgcat = pkgsdir.split("/")[len(pkgsdir.split("/"))-1]
                    pkgatom = pkgcat+"/"+pdir
                    if pkgatom.find("-MERGING-") == -1:
                        installedAtoms.add(pkgatom)
        return list(installedAtoms), len(installedAtoms)

    def get_installed_packages_counter(self, dbdir = None):
        if not dbdir:
            appDbDir = self.get_vdb_path()
        else:
            appDbDir = dbdir
        dbDirs = os.listdir(appDbDir)
        installedAtoms = set()
        for pkgsdir in dbDirs:
            if not os.path.isdir(appDbDir+pkgsdir):
                continue
            pkgdir = os.listdir(appDbDir+pkgsdir)
            for pdir in pkgdir:
                pkgcat = pkgsdir.split("/")[len(pkgsdir.split("/"))-1]
                pkgatom = pkgcat+"/"+pdir
                if pkgatom.find("-MERGING-") == -1:
                    # get counter
                    try:
                        f = open(appDbDir+pkgsdir+"/"+pdir+"/"+etpConst['spm']['xpak_entries']['counter'],"r")
                        counter = int(f.readline().strip())
                        f.close()
                    except IOError:
                        continue
                    except ValueError:
                        continue
                    installedAtoms.add((pkgatom,counter))
        return installedAtoms

    def refill_counter(self, dbdir = None):
        if not dbdir:
            appDbDir = self.get_vdb_path()
        else:
            appDbDir = dbdir
        counters = set()
        for catdir in os.listdir(appDbDir):
            catdir = appDbDir+catdir
            if not os.path.isdir(catdir):
                continue
            for pkgdir in os.listdir(catdir):
                pkgdir = catdir+"/"+pkgdir
                if not os.path.isdir(pkgdir):
                    continue
                counterfile = pkgdir+"/"+etpConst['spm']['xpak_entries']['counter']
                if not os.path.isfile(pkgdir+"/"+etpConst['spm']['xpak_entries']['counter']):
                    continue
                try:
                    f = open(counterfile,"r")
                    counter = int(f.readline().strip())
                    counters.add(counter)
                    f.close()
                except:
                    continue
        if counters:
            newcounter = max(counters)
        else:
            newcounter = 0
        if not os.path.isdir(os.path.dirname(etpConst['edbcounter'])):
            os.makedirs(os.path.dirname(etpConst['edbcounter']))
        try:
            f = open(etpConst['edbcounter'],"w")
        except IOError, e:
            if e[0] == 21:
                shutil.rmtree(etpConst['edbcounter'],True)
                try:
                    os.rmdir(etpConst['edbcounter'])
                except:
                    pass
            f = open(etpConst['edbcounter'],"w")
        f.write(str(newcounter))
        f.flush()
        f.close()
        del counters
        return newcounter


    def spm_doebuild(self, myebuild, mydo, tree, cpv, portage_tmpdir = None, licenses = []):

        rc = self.entropyTools.spawnFunction(    self._portage_doebuild,
                                            myebuild,
                                            mydo,
                                            tree,
                                            cpv,
                                            portage_tmpdir,
                                            licenses
                                        )
        return rc

    def _portage_doebuild(self, myebuild, mydo, tree, cpv, portage_tmpdir = None, licenses = []):
        # myebuild = path/to/ebuild.ebuild with a valid unpacked xpak metadata
        # tree = "bintree"
        # tree = "bintree"
        # cpv = atom
        '''
            # This is a demonstration that Sabayon team love Gentoo so much
            [01:46] <zmedico> if you want something to stay in mysettings
            [01:46] <zmedico> do mysettings.backup_changes("CFLAGS") for example
            [01:46] <zmedico> otherwise your change can get lost inside doebuild()
            [01:47] <zmedico> because it calls mysettings.reset()
            # ^^^ this is DA MAN!
        '''
        # mydbapi = portage.fakedbapi(settings=portage.settings)
        # vartree = portage.vartree(root=myroot)

        oldsystderr = sys.stderr
        f = open("/dev/null","w")
        sys.stderr = f

        ### SETUP ENVIRONMENT
        # if mute, supress portage output
        domute = False
        if etpUi['mute']:
            domute = True
            oldsysstdout = sys.stdout
            sys.stdout = f

        mypath = etpConst['systemroot']+"/"
        os.environ["SKIP_EQUO_SYNC"] = "1"
        os.environ["CD_ROOT"] = "/tmp" # workaround for scripts asking for user intervention
        os.environ["ROOT"] = mypath

        if licenses:
            os.environ["ACCEPT_LICENSE"] = str(' '.join(licenses)) # we already do this early

        # load metadata
        myebuilddir = os.path.dirname(myebuild)
        keys = self.portage.auxdbkeys
        metadata = {}

        for key in keys:
            mykeypath = os.path.join(myebuilddir,key)
            if os.path.isfile(mykeypath) and os.access(mykeypath,os.R_OK):
                f = open(mykeypath,"r")
                metadata[key] = f.readline().strip()
                f.close()

        ### END SETUP ENVIRONMENT

        # find config
        mysettings = self._get_portage_config("/",mypath)
        mysettings['EBUILD_PHASE'] = mydo

        try: # this is a >portage-2.1.4_rc11 feature
            mysettings._environ_whitelist = set(mysettings._environ_whitelist)
            # put our vars into whitelist
            mysettings._environ_whitelist.add("SKIP_EQUO_SYNC")
            mysettings._environ_whitelist.add("ACCEPT_LICENSE")
            mysettings._environ_whitelist.add("CD_ROOT")
            mysettings._environ_whitelist.add("ROOT")
            mysettings._environ_whitelist = frozenset(mysettings._environ_whitelist)
        except:
            pass

        cpv = str(cpv)
        mysettings.setcpv(cpv)
        portage_tmpdir_created = False # for pkg_postrm, pkg_prerm
        if portage_tmpdir:
            if not os.path.isdir(portage_tmpdir):
                os.makedirs(portage_tmpdir)
                portage_tmpdir_created = True
            mysettings['PORTAGE_TMPDIR'] = str(portage_tmpdir)
            mysettings.backup_changes("PORTAGE_TMPDIR")

        mydbapi = self.portage.fakedbapi(settings=mysettings)
        mydbapi.cpv_inject(cpv, metadata = metadata)

        # cached vartree class
        vartree = self._get_portage_vartree(mypath)

        rc = self.portage.doebuild(myebuild = str(myebuild), mydo = str(mydo), myroot = mypath, tree = tree, mysettings = mysettings, mydbapi = mydbapi, vartree = vartree, use_cache = 0)

        # if mute, restore old stdout/stderr
        if domute:
            sys.stdout = oldsysstdout

        sys.stderr = oldsystderr
        f.close()

        if portage_tmpdir_created:
            shutil.rmtree(portage_tmpdir,True)

        del mydbapi
        del metadata
        del keys
        return rc

class LogFile:
    def __init__ (self, level = 0, filename = None, header = "[LOG]"):
        self.handler = self.default_handler
        self.level = level
        self.header = header
        self.logFile = None
        self.open(filename)

    def close (self):
        try:
            self.logFile.close ()
        except:
            pass

    def open (self, file = None):
        if type(file) == type("hello"):
            try:
                self.logFile = open(file, "aw")
            except:
                self.logFile = open("/dev/null", "aw")
        elif file:
            self.logFile = file
        else:
            self.logFile = sys.stderr

    def getFile (self):
        return self.logFile.fileno ()

    def __call__(self, format, *args):
        self.handler (format % args)

    def default_handler (self, string):
        self.logFile.write ("* %s\n" % (string))
        self.logFile.flush ()

    def set_loglevel(self, level):
        self.level = level

    def log(self, messagetype, level, message):
        if self.level >= level and not etpUi['nolog']:
            self.handler(self.getTimeDateHeader()+messagetype+' '+self.header+' '+message)

    def getTimeDateHeader(self):
        return time.strftime('[%X %x %Z] ')

    def ladd(self, level, file, message):
        if self.level >= level:
            self.handler("++ %s \t%s" % (file, message))

    def ldel(self, level, file, message):
        if self.level >= level:
            self.handler("-- %s \t%s" % (file, message))

    def lch(self, level, file, message):
        if self.level >= level:
            self.handler("-+ %s \t%s" % (file, message))

class SocketHostInterface:

    import socket
    import SocketServer
    import entropyTools
    from threading import Thread

    class BasicPamAuthenticator:

        import entropyTools

        def __init__(self):
            self.valid_auth_types = [ "plain", "shadow", "md5" ]

        def docmd_login(self, arguments):

            # filter n00bs
            if not arguments or (len(arguments) != 3):
                return False,None,None,'wrong arguments'

            user = arguments[0]
            auth_type = arguments[1]
            auth_string = arguments[2]

            # check auth type validity
            if auth_type not in self.valid_auth_types:
                return False,user,None,'invalid auth type'

            import pwd
            # check user validty
            try:
                udata = pwd.getpwnam(user)
            except KeyError:
                return False,user,None,'invalid user'

            uid = udata[2]
            # check if user is in the Entropy group
            if not self.entropyTools.is_user_in_entropy_group(uid):
                return False,user,uid,'user not in %s group' % (etpConst['sysgroup'],)

            # now validate password
            valid = self.__validate_auth(user,auth_type,auth_string)
            if not valid:
                return False,user,uid,'auth failed'

            return True,user,uid,"ok"

        def __validate_auth(self, user, auth_type, auth_string):
            valid = False
            if auth_type == "plain":
                valid = self.__do_auth(user, auth_string)
            elif auth_type == "shadow":
                valid = self.__do_auth(user, auth_string, auth_type = "shadow")
            elif auth_type == "md5":
                valid = self.__do_auth(user, auth_string, auth_type = "md5")
            return valid

        def __do_auth(self, user, password, auth_type = None):
            import spwd

            try:
                enc_pass = spwd.getspnam(user)[1]
            except KeyError:
                return False

            if auth_type == None: # plain
                import crypt
                generated_pass = crypt.crypt(str(password), enc_pass)
            elif auth_type == "shadow":
                generated_pass = password
            elif auth_type == "md5": # md5
                import hashlib
                m = hashlib.md5()
                m.update(enc_pass)
                enc_pass = m.hexdigest()
                generated_pass = str(password)
            else: # haha, fuck!
                generated_pass = None

            if generated_pass == enc_pass:
                return True
            return False

        def docmd_logout(self, user):

            # filter n00bs
            if not user or (type(user) is not basestring):
                return False,None,None,"wrong user"

            return True,user,"ok"

        def set_exc_permissions(self, uid, gid):
            if gid != None:
                os.setgid(gid)
            if uid != None:
                os.setuid(uid)

        def hide_login_data(self, args):
            myargs = args[:]
            myargs[-1] = 'hidden'
            return myargs

    class HostServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):

        class ConnWrapper:
            '''
            Base class for implementing the rest of the wrappers in this module.
            Operates by taking a connection argument which is used when 'self' doesn't
            provide the functionality being requested.
            '''
            def __init__(self, connection) :
                self.connection = connection

            def __getattr__(self, function) :
                return getattr(self.connection, function)

        import socket
        import SocketServer
        # This means the main server will not do the equivalent of a
        # pthread_join() on the new threads.  With this set, Ctrl-C will
        # kill the server reliably.
        daemon_threads = True

        # By setting this we allow the server to re-bind to the address by
        # setting SO_REUSEADDR, meaning you don't have to wait for
        # timeouts when you kill the server and the sockets don't get
        # closed down correctly.
        allow_reuse_address = True

        def __init__(self, server_address, RequestHandlerClass, processor, HostInterface):

            self.processor = processor
            self.server_address = server_address
            self.HostInterface = HostInterface
            self.SSL = self.HostInterface.SSL
            self.real_sock = None

            if self.SSL:
                self.SocketServer.BaseServer.__init__(self, server_address, RequestHandlerClass)
                self.load_ssl_context()
                self.make_ssl_connection_alive()
            else:
                self.SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)

        def load_ssl_context(self):
            # setup an SSL context.
            self.context = self.SSL['m'].Context(self.SSL['m'].SSLv23_METHOD)
            self.context.set_verify(self.SSL['m'].VERIFY_PEER, self.verify_ssl_cb)
            # load up certificate stuff.
            self.context.use_privatekey_file(self.SSL['key'])
            self.context.use_certificate_file(self.SSL['cert'])
            self.HostInterface.updateProgress('SSL context loaded, key: %s - cert: %s' % (
                                        self.SSL['key'],
                                        self.SSL['cert'],
                                ))

        def make_ssl_connection_alive(self):
            self.real_sock = self.socket.socket(self.address_family, self.socket_type)
            self.socket = self.ConnWrapper(self.SSL['m'].Connection(self.context, self.real_sock))

            self.server_bind()
            self.server_activate()

        # this function should do the authentication checking to see that
        # the client is who they say they are.
        def verify_ssl_cb(self, conn, cert, errnum, depth, ok) :
            return ok

    class RequestHandler(SocketServer.BaseRequestHandler):

        import SocketServer
        import select
        import socket
        timed_out = False

        def __init__(self, request, client_address, server):
            self.SocketServer.BaseRequestHandler.__init__(self, request, client_address, server)

        def handle(self):

            self.default_timeout = self.server.processor.HostInterface.timeout
            ssl = self.server.processor.HostInterface.SSL
            ssl_exceptions = self.server.processor.HostInterface.SSL_exceptions

            if self.valid_connection:

                while 1:

                    if self.timed_out:
                        break
                    self.timed_out = True
                    ready_to_read, ready_to_write, in_error = self.select.select([self.request], [], [], self.default_timeout)

                    if len(ready_to_read) == 1 and ready_to_read[0] == self.request:

                        self.timed_out = False

                        try:
                            data = self.request.recv(8192)
                        except self.socket.timeout, e:
                            self.server.processor.HostInterface.updateProgress('interrupted: %s, reason: %s - from client: %s' % (self.server.server_address,e,self.client_address,))
                            break
                        except ssl_exceptions['WantReadError']:
                            continue
                        except ssl_exceptions['Error'], e:
                            self.server.processor.HostInterface.updateProgress('interrupted: SSL Error, reason: %s - from client: %s' % (e,self.client_address,))
                            break

                        if not data:
                            break

                        cmd = self.server.processor.process(data, self.request, self.client_address)
                        if cmd == 'close':
                            break

            self.request.close()

        def setup(self):

            self.valid_connection = True
            allowed = self.max_connections_check(   self.server.processor.HostInterface.connections,
                                                    self.server.processor.HostInterface.max_connections
                                                )
            if allowed:
                self.server.processor.HostInterface.connections += 1
                self.server.processor.HostInterface.updateProgress('[from: %s] connection established (%s of %s max connections)' % (
                                        self.client_address,
                                        self.server.processor.HostInterface.connections,
                                        self.server.processor.HostInterface.max_connections,
                                )
                )
                return True

            self.server.processor.HostInterface.updateProgress('[from: %s] connection refused (max connections reached: %s)' % (self.client_address, self.server.processor.HostInterface.max_connections,))
            return False

        def finish(self):
            self.server.processor.HostInterface.updateProgress('[from: %s] connection closed (%s of %s max connections)' % (
                    self.client_address,
                    self.server.processor.HostInterface.connections,
                    self.server.processor.HostInterface.max_connections,
                )
            )
            if self.valid_connection:
                self.server.processor.HostInterface.connections -= 1

        def max_connections_check(self, current, maximum):
            if current >= maximum:
                self.request.sendall(self.server.processor.HostInterface.answers['mcr'])
                self.valid_connection = False
                return False
            else:
                return True

    class CommandProcessor:

        import entropyTools

        def __init__(self, HostInterface):
            self.HostInterface = HostInterface
            self.Authenticator = self.HostInterface.Authenticator
            self.channel = None
            self.lastoutput = None

        def handle_termination_commands(self, data):
            if data.strip() in self.HostInterface.termination_commands:
                self.HostInterface.updateProgress('close: %s' % (self.client_address,))
                self.transmit(self.HostInterface.answers['cl'])
                return "close"

            if not data.strip():
                return "ignore"

        def handle_command_string(self, string):
            # validate command
            args = string.strip().split()
            session = args[0]
            if (session in self.HostInterface.initialization_commands) or len(args) < 2:
                cmd = args[0]
                session = None
            else:
                cmd = args[1]
                args = args[1:] # remove session

            myargs = []
            if len(args) > 1:
                myargs = args[1:]

            return cmd,myargs,session

        def handle_end_answer(self, cmd, whoops, valid_cmd):
            if not valid_cmd:
                self.transmit(self.HostInterface.answers['no'])
            elif whoops:
                self.transmit(self.HostInterface.answers['er'])
            elif cmd not in self.HostInterface.no_acked_commands:
                self.transmit(self.HostInterface.answers['ok'])
            self.channel.sendall(self.HostInterface.answers['eot'])

        def validate_command(self, cmd, args, session):

            # answer to invalid commands
            if (cmd not in self.HostInterface.valid_commands):
                return False,"not a valid command"

            if session == None:
                if cmd not in self.HostInterface.no_session_commands:
                    return False,"need a valid session"
            elif session not in self.HostInterface.sessions:
                return False,"session is not alive"

            # check if command needs authentication
            if session != None:
                auth = self.HostInterface.valid_commands[cmd]['auth']
                if auth:
                    # are we?
                    authed = self.HostInterface.sessions[session]['auth_uid']
                    if authed == None:
                        # nope
                        return False,"not authenticated"

            # keep session alive
            if session != None:
                self.HostInterface.set_session_running(session)
                self.HostInterface.update_session_time(session)

            return True,"all good"

        def load_service_interface(self, session):

            uid = None
            if session != None:
                uid = self.HostInterface.sessions[session]['auth_uid']

            intf = self.HostInterface.EntropyInstantiation[0]
            args = self.HostInterface.EntropyInstantiation[1]
            kwds = self.HostInterface.EntropyInstantiation[2]
            Entropy = intf(*args, **kwds)
            Entropy.urlFetcher = SocketUrlFetcher
            Entropy.updateProgress = self.remoteUpdateProgress
            Entropy.clientDbconn.updateProgress = self.remoteUpdateProgress
            Entropy.progress = self.remoteUpdateProgress
            return Entropy

        def process(self, data, channel, client_address):

            self.channel = channel
            self.client_address = client_address

            if data.strip():
                mycommand = data.strip().split()
                if mycommand[0] in self.HostInterface.login_pass_commands:
                    mycommand = self.Authenticator.hide_login_data(mycommand)
                self.HostInterface.updateProgress("[from: %s] call: %s" % (
                                self.client_address,
                                repr(' '.join(mycommand)),
                            )
                )

            term = self.handle_termination_commands(data)
            if term:
                return term

            cmd, args, session = self.handle_command_string(data)
            valid_cmd, reason = self.validate_command(cmd, args, session)

            p_args = args
            if cmd in self.HostInterface.login_pass_commands:
                p_args = self.Authenticator.hide_login_data(p_args)
            self.HostInterface.updateProgress('[from: %s] command validation :: called %s: args: %s, session: %s, valid: %s, reason: %s' % (self.client_address, cmd, p_args, session, valid_cmd, reason,))

            whoops = False
            if valid_cmd:
                Entropy = self.load_service_interface(session)
                try:
                    self.run_task(cmd, args, session, Entropy)
                except Exception, e:
                    # store error
                    self.HostInterface.updateProgress('[from: %s] command error: %s, type: %s' % (self.client_address,e,type(e),))
                    if session != None:
                        self.HostInterface.store_rc(str(e),session)
                    whoops = True

            if session != None:
                self.HostInterface.update_session_time(session)
                self.HostInterface.unset_session_running(session)
            self.handle_end_answer(cmd, whoops, valid_cmd)

        def duplicate_termination_cmd(self, data):
            if data.find(self.HostInterface.answers['eot']) != -1:
                data = data.replace(self.HostInterface.answers['eot'],self.HostInterface.answers['eot']*2)
            return data

        def transmit(self, data):
            data = self.duplicate_termination_cmd(data)
            self.channel.sendall(data)

        def remoteUpdateProgress(self, text, header = "", footer = "", back = False, importance = 0, type = "info", count = [], percent = False):
            if text != self.lastoutput:
                text = chr(27)+"[2K\r"+text
                if not back:
                    text += "\n"
                self.transmit(text)
            self.lastoutput = text

        def run_task(self, cmd, args, session, Entropy):

            p_args = args
            if cmd in self.HostInterface.login_pass_commands:
                p_args = self.Authenticator.hide_login_data(p_args)
            self.HostInterface.updateProgress('[from: %s] run_task :: called %s: args: %s, session: %s' % (self.client_address,cmd,p_args,session,))

            myargs, mykwargs = self._get_args_kwargs(args)

            rc = self.spawn_function(cmd, myargs, mykwargs, session, Entropy)
            if session != None and self.HostInterface.sessions.has_key(session):
                self.HostInterface.store_rc(rc, session)
            return rc

        def _get_args_kwargs(self, args):
            myargs = []
            mykwargs = {}
            for arg in args:
                if (arg.find("=") != -1) and not arg.startswith("="):
                    x = arg.split("=")
                    a = x[0]
                    b = ''.join(x[1:])
                    mykwargs[a] = eval(b)
                else:
                    try:
                        myargs.append(eval(arg))
                    except (NameError, SyntaxError):
                        myargs.append(str(arg))
            return myargs, mykwargs

        def spawn_function(self, cmd, myargs, mykwargs, session, Entropy):

            p_args = myargs
            if cmd in self.HostInterface.login_pass_commands:
                p_args = self.Authenticator.hide_login_data(p_args)
            self.HostInterface.updateProgress('[from: %s] called %s: args: %s, kwargs: %s' % (self.client_address,cmd,p_args,mykwargs,))
            return self.do_spawn(cmd, myargs, mykwargs, session, Entropy)

        def do_spawn(self, cmd, myargs, mykwargs, session, Entropy):

            cmd_data = self.HostInterface.valid_commands.get(cmd)
            do_fork = cmd_data['as_user']
            f = cmd_data['cb']
            func_args = []
            for arg in cmd_data['args']:
                try:
                    func_args.append(eval(arg))
                except (NameError, SyntaxError):
                    func_args.append(str(arg))

            if do_fork:
                myfargs = func_args[:]
                myfargs.extend(myargs)
                return self.fork_task(f, session, *myfargs, **mykwargs)
            else:
                return f(*func_args)

        def fork_task(self, f, session, *args, **kwargs):
            gid = None
            uid = None
            if session != None:
                logged_in = self.HostInterface.sessions[session]['auth_uid']
                if logged_in != None:
                    uid = logged_in
                    gid = etpConst['entropygid']
            return self.entropyTools.spawnFunction(self._do_fork, f, uid, gid, *args, **kwargs)

        def _do_fork(self, f, uid, gid, *args, **kwargs):
            self.Authenticator.set_exc_permissions(uid,gid)
            rc = f(*args,**kwargs)
            return rc

    class BuiltInCommands:

        import dumpTools

        def __str__(self):
            return self.inst_name

        def __init__(self, HostInterface, Authenticator):

            self.HostInterface = HostInterface
            self.Authenticator = Authenticator
            self.inst_name = "builtin"

            self.valid_commands = {
                'begin':    {
                                'auth': True, # does it need authentication ?
                                'built_in': True, # is it built-in ?
                                'cb': self.docmd_begin, # function to call
                                'args': ["self.transmit"], # arguments to be passed before *args and **kwards
                                'as_user': False, # do I have to fork the process and run it as logged user?
                                                  # needs auth = True
                                'desc': "instantiate a session", # description
                                'syntax': "begin", # syntax
                                'from': str(self), # from what class
                            },
                'end':      {
                                'auth': True,
                                'built_in': True,
                                'cb': self.docmd_end,
                                'args': ["self.transmit", "session"],
                                'as_user': False,
                                'desc': "end a session",
                                'syntax': "<SESSION_ID> end",
                                'from': str(self),
                            },
                'reposync': {
                                'auth': True,
                                'built_in': True,
                                'cb': self.docmd_reposync,
                                'args': ["Entropy"],
                                'as_user': True,
                                'desc': "update repositories",
                                'syntax': "<SESSION_ID> reposync (optionals: reponames=['repoid1'] forceUpdate=Bool noEquoCheck=Bool fetchSecurity=Bool",
                                'from': str(self),
                            },
                'rc':       {
                                'auth': True,
                                'built_in': True,
                                'cb': self.docmd_rc,
                                'args': ["self.transmit","session"],
                                'as_user': False,
                                'desc': "get data returned by the last valid command (streamed python object)",
                                'syntax': "<SESSION_ID> rc",
                                'from': str(self),
                            },
                'match':    {
                                'auth': False,
                                'built_in': True,
                                'cb': self.docmd_match,
                                'args': ["Entropy"],
                                'as_user': True,
                                'desc': "match an atom inside configured repositories",
                                'syntax': "<SESSION_ID> match app-foo/foo",
                                'from': str(self),
                            },
                'hello':    {
                                'auth': False,
                                'built_in': True,
                                'cb': self.docmd_hello,
                                'args': ["self.transmit"],
                                'as_user': False,
                                'desc': "get server status",
                                'syntax': "hello",
                                'from': str(self),
                            },
                'alive':    {
                                'auth': True,
                                'built_in': True,
                                'cb': self.docmd_alive,
                                'args': ["self.transmit","session"],
                                'as_user': False,
                                'desc': "check if a session is still alive",
                                'syntax': "<SESSION_ID> alive",
                                'from': str(self),
                            },
                'login':    {
                                'auth': False,
                                'built_in': True,
                                'cb': self.docmd_login,
                                'args': ["self.transmit", "session", "self.client_address", "myargs"],
                                'as_user': False,
                                'desc': "login on the running server (allows running extra commands)",
                                'syntax': "<SESSION_ID> login <USER> <AUTH_TYPE: plain,shadow,md5> <PASSWORD>",
                                'from': str(self),
                            },
                'logout':   {
                                'auth': True,
                                'built_in': True,
                                'cb': self.docmd_logout,
                                'args': ["self.transmit","session", "myargs"],
                                'as_user': False,
                                'desc': "logout on the running server",
                                'syntax': "<SESSION_ID> logout <USER>",
                                'from': str(self),
                            },
                'help':   {
                                'auth': False,
                                'built_in': True,
                                'cb': self.docmd_help,
                                'args': ["self.transmit"],
                                'as_user': False,
                                'desc': "this output",
                                'syntax': "help",
                                'from': str(self),
                            },

            }

            self.no_acked_commands = ["rc", "begin", "end", "hello", "alive", "login", "logout","help"]
            self.termination_commands = ["quit","close"]
            self.initialization_commands = ["begin"]
            self.login_pass_commands = ["login"]
            self.no_session_commands = ["begin","hello","alive","help"]

        def register(self, valid_commands, no_acked_commands, termination_commands, initialization_commands, login_pass_commads, no_session_commands):

            valid_commands.update(self.valid_commands)
            no_acked_commands.extend(self.no_acked_commands)
            termination_commands.extend(self.termination_commands)
            initialization_commands.extend(self.initialization_commands)
            login_pass_commads.extend(self.login_pass_commands)
            no_session_commands.extend(self.no_session_commands)

        def docmd_login(self, transmitter, session, client_address, myargs):

            # is already auth'd?
            auth_uid = self.HostInterface.sessions[session]['auth_uid']
            if auth_uid != None:
                return False,"already authenticated"

            status, user, uid, reason = self.Authenticator.docmd_login(myargs)
            if status:
                self.HostInterface.updateProgress('[from: %s] user %s logged in successfully, session: %s' % (client_address,user,session,))
                self.HostInterface.sessions[session]['auth_uid'] = uid
                transmitter(self.HostInterface.answers['ok'])
                return True,reason
            elif user == None:
                self.HostInterface.updateProgress('[from: %s] user -not specified- login failed, session: %s, reason: %s' % (client_address,session,reason,))
                transmitter(self.HostInterface.answers['no'])
                return False,reason
            else:
                self.HostInterface.updateProgress('[from: %s] user %s login failed, session: %s, reason: %s' % (client_address,user,session,reason,))
                transmitter(self.HostInterface.answers['no'])
                return False,reason

        def docmd_logout(self, transmitter, session, myargs):
            status, user, reason = self.Authenticator.docmd_logout(myargs)
            if status:
                self.HostInterface.updateProgress('[from: %s] user %s logged out successfully, session: %s, args: %s ' % (self.client_address,user,session,myargs,))
                self.HostInterface.sessions[session]['auth_uid'] = None
                transmitter(self.HostInterface.answers['ok'])
                return True,reason
            elif user == None:
                self.HostInterface.updateProgress('[from: %s] user -not specified- logout failed, session: %s, args: %s, reason: %s' % (self.client_address,session,myargs,reason,))
                transmitter(self.HostInterface.answers['no'])
                return False,reason
            else:
                self.HostInterface.updateProgress('[from: %s] user %s logout failed, session: %s, args: %s, reason: %s' % (self.client_address,user,session,myargs,reason,))
                transmitter(self.HostInterface.answers['no'])
                return False,reason

        def docmd_alive(self, transmitter, session):
            cmd = self.HostInterface.answers['no']
            if session in self.HostInterface.sessions:
                cmd = self.HostInterface.answers['ok']
            transmitter(cmd)

        def docmd_hello(self, transmitter):
            uname = os.uname()
            kern_string = uname[2]
            running_host = uname[1]
            running_arch = uname[4]
            load_stats = commands.getoutput('uptime').split("\n")[0]
            text = "Entropy Server %s, connections: %s ~ running on: %s ~ host: %s ~ arch: %s, kernel: %s, stats: %s\n" % (
                    etpConst['entropyversion'],
                    self.HostInterface.connections,
                    etpConst['systemname'],
                    running_host,
                    running_arch,
                    kern_string,
                    load_stats
                    )
            transmitter(text)

        def docmd_help(self, transmitter):
            text = '\nEntropy Socket Interface Help Menu\n' + \
                   'Available Commands:\n\n'
            valid_cmds = self.HostInterface.valid_commands.keys()
            valid_cmds.sort()
            for cmd in valid_cmds:
                if self.HostInterface.valid_commands[cmd].has_key('desc'):
                    desc = self.HostInterface.valid_commands[cmd]['desc']
                else:
                    desc = 'no description available'

                if self.HostInterface.valid_commands[cmd].has_key('syntax'):
                    syntax = self.HostInterface.valid_commands[cmd]['syntax']
                else:
                    syntax = 'no syntax available'
                if self.HostInterface.valid_commands[cmd].has_key('from'):
                    myfrom = self.HostInterface.valid_commands[cmd]['from']
                else:
                    myfrom = 'N/A'
                text += "[%s] %s\n   %s: %s\n   %s: %s\n\n" % ( myfrom, blue(cmd), red("description"), desc, darkgreen("syntax"), syntax, )
            transmitter(text)

        def docmd_end(self, transmitter, session):
            rc = self.HostInterface.destroy_session(session)
            cmd = self.HostInterface.answers['no']
            if rc: cmd = self.HostInterface.answers['ok']
            transmitter(cmd)
            return rc

        def docmd_begin(self, transmitter):
            session = self.HostInterface.get_new_session()
            transmitter(session)
            return session

        def docmd_rc(self, transmitter, session):
            rc = self.HostInterface.get_rc(session)
            try:
                import cStringIO as stringio
            except ImportError:
                import StringIO as stringio
            f = stringio.StringIO()
            self.dumpTools.serialize(rc, f)
            transmitter(f.getvalue())
            f.close()
            return rc

        def docmd_match(self, Entropy, *myargs, **mykwargs):
            return Entropy.atomMatch(*myargs, **mykwargs)

        def docmd_reposync(self, Entropy, *myargs, **mykwargs):
            repoConn = Entropy.Repositories(*myargs, **mykwargs)
            return repoConn.sync()

    def __init__(self, service_interface, *args, **kwds):

        self.args = args
        self.kwds = kwds
        self.socketLog = LogFile(level = 2, filename = etpConst['socketlogfile'], header = "[Socket]")

        # settings
        self.timeout = etpConst['socket_service']['timeout']
        self.hostname = etpConst['socket_service']['hostname']
        self.session_ttl = etpConst['socket_service']['session_ttl']
        if self.hostname == "*": self.hostname = ''
        self.port = etpConst['socket_service']['port']
        self.threads = etpConst['socket_service']['threads'] # maximum number of allowed sessions
        self.max_connections = etpConst['socket_service']['max_connections']
        self.disabled_commands = etpConst['socket_service']['disabled_cmds']
        self.connections = 0
        self.sessions = {}
        self.answers = etpConst['socket_service']['answers']
        self.Server = None
        self.Gc = None
        self.__output = None
        self.SSL = {}
        self.SSL_exceptions = {}
        self.SSL_exceptions['WantReadError'] = None
        self.SSL_exceptions['Error'] = []
        self.last_print = ''
        self.valid_commands = {}
        self.no_acked_commands = []
        self.termination_commands = []
        self.initialization_commands = []
        self.login_pass_commands = []
        self.no_session_commands = []
        self.command_classes = [self.BuiltInCommands]
        self.command_instances = []
        self.EntropyInstantiation = (service_interface, self.args, self.kwds)

        self.setup_external_command_classes()
        self.start_local_output_interface()
        self.start_authenticator()
        self.setup_hostname()
        self.setup_commands()
        self.disable_commands()
        self.start_session_garbage_collector()
        self.setup_ssl()



    def setup_ssl(self):

        do_ssl = False
        if self.kwds.has_key('ssl'):
            do_ssl = self.kwds.pop('ssl')

        if not do_ssl:
            return

        try:
            from OpenSSL import SSL
        except ImportError, e:
            self.updateProgress('Unable to load OpenSSL, error: %s' % (repr(e),))
            return
        self.SSL_exceptions['WantReadError'] = SSL.WantReadError
        self.SSL_exceptions['Error'] = SSL.Error
        self.SSL['m'] = SSL
        self.SSL['key'] = etpConst['socket_service']['ssl_key'] # openssl genrsa -out filename.key 1024
        self.SSL['cert'] = etpConst['socket_service']['ssl_cert'] # openssl req -new -days 365 -key filename.key -x509 -out filename.cert
        # change port
        self.port = etpConst['socket_service']['ssl_port']

        if not os.path.isfile(self.SSL['key']):
            raise exceptionTools.FileNotFound('FileNotFound: no %s found' % (self.SSL['key'],))
        if not os.path.isfile(self.SSL['cert']):
            raise exceptionTools.FileNotFound('FileNotFound: no %s found' % (self.SSL['cert'],))
        os.chmod(self.SSL['key'],0600)
        os.chown(self.SSL['key'],0,0)
        os.chmod(self.SSL['cert'],0644)
        os.chown(self.SSL['cert'],0,0)

    def setup_external_command_classes(self):

        if self.kwds.has_key('external_cmd_classes'):
            ext_commands = self.kwds.pop('external_cmd_classes')
            if type(ext_commands) is not list:
                raise exceptionTools.InvalidDataType("InvalidDataType: external_cmd_classes must be a list")
            self.command_classes += ext_commands

    def setup_commands(self):

        identifiers = set()
        for myclass in self.command_classes:
            myinst = myclass(self,self.Authenticator)
            if str(myinst) in identifiers:
                raise exceptionTools.PermissionDenied("PermissionDenied: another command instance is owning this name")
            identifiers.add(str(myinst))
            self.command_instances.append(myinst)
            # now register
            myinst.register(    self.valid_commands,
                                self.no_acked_commands,
                                self.termination_commands,
                                self.initialization_commands,
                                self.login_pass_commands,
                                self.no_session_commands
                            )

    def disable_commands(self):
        for cmd in self.disabled_commands:

            if cmd in self.valid_commands:
                self.valid_commands.pop(cmd)

            if cmd in self.no_acked_commands:
                self.no_acked_commands.remove(cmd)

            if cmd in self.termination_commands:
                self.termination_commands.remove(cmd)

            if cmd in self.initialization_commands:
                self.initialization_commands.remove(cmd)

            if cmd in self.login_pass_commands:
                self.login_pass_commands.remove(cmd)

            if cmd in self.no_session_commands:
                self.no_session_commands.remove(cmd)

    def start_local_output_interface(self):
        if self.kwds.has_key('sock_output'):
            outputIntf = self.kwds.pop('sock_output')
            self.__output = outputIntf

    def start_authenticator(self):

        auth_inst = (self.BasicPamAuthenticator, [], {}) # authentication class, args, keywords
        # external authenticator
        if self.kwds.has_key('sock_auth'):
            authIntf = self.kwds.pop('sock_auth')
            if type(authIntf) is tuple:
                if len(authIntf) == 3:
                    auth_inst = authIntf[:]
                else:
                    raise exceptionTools.IncorrectParameter("IncorrectParameter: wront authentication interface specified")
            else:
                raise exceptionTools.IncorrectParameter("IncorrectParameter: wront authentication interface specified")
            # initialize authenticator
        self.Authenticator = auth_inst[0](*auth_inst[1], **auth_inst[2])

    def start_session_garbage_collector(self):
        # do it every 30 seconds
        self.Gc = self.entropyTools.TimeScheduled( self.gc_clean, 5 )
        self.Gc.setName("Socket_GC::"+str(random.random()))
        self.Gc.start()

    def gc_clean(self):
        if not self.sessions:
            return

        for session_id in self.sessions.keys():
            sess_time = self.sessions[session_id]['t']
            is_running = self.sessions[session_id]['running']
            auth_uid = self.sessions[session_id]['auth_uid'] # is kept alive?
            if (is_running) or (auth_uid == -1):
                if auth_uid == -1:
                    self.updateProgress('not killing session %s, since it is kept alive by auth_uid=-1' % (session_id,) )
                continue
            cur_time = time.time()
            ttl = self.session_ttl
            check_time = sess_time + ttl
            if cur_time > check_time:
                self.updateProgress('killing session %s, ttl: %ss: no activity' % (session_id,ttl,) )
                self.destroy_session(session_id)

    def setup_hostname(self):
        if self.hostname:
            try:
                self.hostname = self.get_ip_address(self.hostname)
            except IOError: # it isn't a device name
                pass

    def get_ip_address(self, ifname):
        import fcntl
        import struct
        mysock = self.socket.socket ( self.socket.AF_INET, self.socket.SOCK_STREAM )
        return self.socket.inet_ntoa(fcntl.ioctl(mysock.fileno(), 0x8915, struct.pack('256s', ifname[:15]))[20:24])

    def get_new_session(self):
        if len(self.sessions) > self.threads:
            # fuck!
            return "0"
        rng = str(int(random.random()*100000000000)+1)
        while rng in self.sessions:
            rng = str(int(random.random()*100000000000)+1)
        self.sessions[rng] = {}
        self.sessions[rng]['running'] = False
        self.sessions[rng]['auth_uid'] = None
        self.sessions[rng]['t'] = time.time()
        return rng

    def update_session_time(self, session):
        if self.sessions.has_key(session):
            self.sessions[session]['t'] = time.time()
            self.updateProgress('session time updated for %s' % (session,) )

    def set_session_running(self, session):
        if self.sessions.has_key(session):
            self.sessions[session]['running'] = True

    def unset_session_running(self, session):
        if self.sessions.has_key(session):
            self.sessions[session]['running'] = False

    def destroy_session(self, session):
        if self.sessions.has_key(session):
            del self.sessions[session]
            return True
        return False

    def go(self):
        self.socket.setdefaulttimeout(self.timeout)
        while 1:
            try:
                self.Server = self.HostServer(
                                                (self.hostname, self.port),
                                                self.RequestHandler,
                                                self.CommandProcessor(self),
                                                self
                                            )
                break
            except self.socket.error, e:
                if e[0] == 98:
                    # Address already in use
                    self.updateProgress('address already in use (%s, port: %s), waiting 5 seconds...' % (self.hostname,self.port,))
                    time.sleep(5)
                    continue
                else:
                    raise
        self.updateProgress('server connected, listening on: %s, port: %s, timeout: %s' % (self.hostname,self.port,self.timeout,))
        self.Server.serve_forever()
        self.Gc.kill()

    def store_rc(self, rc, session):
        if type(rc) in (list,tuple,):
            rc_item = rc[:]
        elif type(rc) in (set,frozenset,dict,):
            rc_item = rc.copy()
        else:
            rc_item = rc
        self.sessions[session]['rc'] = rc_item

    def get_rc(self, session):
        return self.sessions[session]['rc']

    def updateProgress(self, *args, **kwargs):
        message = args[0]
        if message != self.last_print:
            self.socketLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,str(args[0]))
            if self.__output != None:
                self.__output.updateProgress(*args,**kwargs)
            self.last_print = message

class SocketUrlFetcher(urlFetcher):

    import entropyTools
    # reimplementing updateProgress
    def updateProgress(self):
        kbprogress = " (%s/%s kB @ %s)" % (
                                        str(round(float(self.downloadedsize)/1024,1)),
                                        str(round(self.remotesize,1)),
                                        str(self.entropyTools.bytesIntoHuman(self.datatransfer))+"/sec",
                                    )
        self.progress( "Fetching "+str((round(float(self.average),1)))+"%"+kbprogress, back = True )


class ServerInterface(TextInterface):

    def __init__(self, default_repository = None, save_repository = False):

        if etpConst['uid'] != 0:
            raise exceptionTools.PermissionDenied("PermissionDenied: Entropy ServerInterface must be run as root")

        self.serverLog = LogFile(level = etpConst['entropyloglevel'],filename = etpConst['entropylogfile'], header = "[server]")

        # settings
        etpSys['serverside'] = True
        self.indexing = False
        self.xcache = False
        self.MirrorsService = None
        self.FtpInterface = FtpInterface
        self.rssFeed = rssFeed
        self.serverDbCache = {}
        self.settings_to_backup = []
        self.do_save_repository = save_repository
        if default_repository != None:
            self.switch_default_repository(default_repository)
        else:
            self.default_repository = etpConst['officialrepositoryid']
            self.setup_services()

        if default_repository == None:
            self.updateProgress(
                blue("Entropy Server Interface Instance on repository: %s" % (self.default_repository,) ),
                importance = 2,
                type = "info",
                header = red(" @@ ")
            )

    def __del__(self):
        self.close_server_databases()

    def setup_services(self):
        self.setup_entropy_settings()
        self.ClientService = EquoInterface(indexing = self.indexing, xcache = self.xcache, repo_validation = False, noclientdb = 1)
        self.backup_entropy_settings()
        self.ClientService.FtpInterface = self.FtpInterface
        self.databaseTools = self.ClientService.databaseTools
        self.entropyTools = self.ClientService.entropyTools
        self.dumpTools = self.ClientService.dumpTools
        self.SpmService = self.ClientService.Spm()
        self.MirrorsService = ServerMirrorsInterface(self)

    def setup_entropy_settings(self):
        self.settings_to_backup.extend([
            'etpdatabaseclientfilepath',
            'clientdbid',
            'officialrepositoryid',
            'dbrepodir',
            'activatoruploaduris',
            'activatordownloaduris',
            'binaryurirelativepath',
            'etpurirelativepath',
            'handlers'
        ])
        # setup client database
        etpConst['etpdatabaseclientfilepath'] = etpConst['etpdatabasefilepath']
        etpConst['clientdbid'] = etpConst['serverdbid']
        const_createWorkingDirectories()

    def close_server_databases(self):
        for item in self.serverDbCache:
            del self.serverDbCache[item] # this will trigger closeDB()
        self.serverDbCache.clear()

    def close_server_database(self, dbinstance):
        for item in self.serverDbCache:
            if dbinstance == self.serverDbCache[item]:
                sameinst = self.serverDbCache.pop(item)
                del sameinst
                break

    def switch_default_repository(self, repoid):
        self.default_repository = repoid
        self.close_server_databases()

        etpConst['officialrepositoryid'] = repoid
        const_setupServerClientRepository()
        self.setup_services()
        if self.do_save_repository:
            self.save_default_repository(repoid)

        self.updateProgress(
                                blue("Entropy Server Interface Instance on repository: %s" % (self.default_repository,) ),
                                importance = 2,
                                type = "info",
                                header = red(" @@ ")
                            )


    def save_default_repository(self, repoid):
        if os.path.isfile(etpConst['repositoriesconf']):
            f = open(etpConst['repositoriesconf'],"r")
            content = f.readlines()
            f.close()
            content = [x.strip() for x in content]
            found = False
            new_content = []
            for line in content:
                if line.strip().startswith("officialrepositoryid|"):
                    line = "officialrepositoryid|%s" % (repoid,)
                    found = True
                new_content.append(line)
            if not found:
                new_content.append("officialrepositoryid|%s" % (repoid,))
            f = open(etpConst['repositoriesconf']+".save_default_repo_tmp","w")
            for line in new_content:
                f.write(line+"\n")
            f.flush()
            f.close()
            shutil.move(etpConst['repositoriesconf']+".save_default_repo_tmp",etpConst['repositoriesconf'])
        else:
            f = open(etpConst['repositoriesconf'],"w")
            f.write("officialrepositoryid|%s\n" % (repoid,))
            f.flush()
            f.close()


    def backup_entropy_settings(self):
        for setting in self.settings_to_backup:
            self.ClientService.backup_setting(setting)


    def openServerDatabase(self, read_only = True, no_upload = True, just_reading = False):

        if just_reading:
            read_only = True
            no_upload = True

        cached = self.serverDbCache.get((etpConst['systemroot'],read_only,no_upload,just_reading,))
        if cached != None:
            return cached

        if not os.path.isdir(os.path.dirname(etpConst['etpdatabasefilepath'])):
            os.makedirs(os.path.dirname(etpConst['etpdatabasefilepath']))

        conn = self.databaseTools.etpDatabase(readOnly = read_only, dbFile = etpConst['etpdatabasefilepath'], noUpload = no_upload, OutputInterface = self, ServiceInterface = self)
        # verify if we need to update the database to sync 
        # with portage updates, we just ignore being readonly in the case
        if not etpConst['treeupdatescalled'] and (not just_reading):
            # sometimes, when filling a new server db, we need to avoid tree updates
            valid = True
            try:
                conn.validateDatabase()
            except exceptionTools.SystemDatabaseError:
                valid = False
            if valid:
                conn.serverUpdatePackagesData()
            else:
                self.updateProgress(
                                        red("Entropy database is probably empty. If you don't agree with what I'm saying, then it's probably corrupted! I won't stop you here btw..."),
                                        importance = 1,
                                        type = "info",
                                        header = red(" * ")
                                    )
        # do not cache ultra-readonly dbs
        if not just_reading:
            self.serverDbCache[(etpConst['systemroot'],read_only,no_upload,just_reading,)] = conn
        return conn


    def dependencies_test(self):

        self.updateProgress(
                                blue("Running dependencies test..."),
                                importance = 2,
                                type = "info",
                                header = red(" @@ ")
                            )
        dbconn = self.openServerDatabase(read_only = True, no_upload = True)
        deps_not_matched = self.ClientService.dependencies_test(dbconn = dbconn)

        if deps_not_matched:

            crying_atoms = {}
            for atom in deps_not_matched:
                riddep = dbconn.searchDependency(atom)
                if riddep != -1:
                    ridpackages = dbconn.searchIdpackageFromIddependency(riddep)
                    for i in ridpackages:
                        iatom = dbconn.retrieveAtom(i)
                        if not crying_atoms.has_key(atom):
                            crying_atoms[atom] = set()
                        crying_atoms[atom].add(iatom)

            self.updateProgress(
                                    blue("These are the dependencies not found:"),
                                    importance = 1,
                                    type = "info",
                                    header = red(" @@ ")
                                )
            for atom in deps_not_matched:
                print_info("   # "+red(atom))
                if crying_atoms.has_key(atom):
                    self.updateProgress(
                                            red("Needed by:"),
                                            importance = 0,
                                            type = "info",
                                            header = blue("      # ")
                                        )
                    for x in crying_atoms[atom]:
                        self.updateProgress(
                                                darkgreen(x),
                                                importance = 0,
                                                type = "info",
                                                header = blue("      # ")
                                            )

        return deps_not_matched

    def libraries_test(self, get_files = False):

        # load db
        dbconn = self.openServerDatabase(read_only = True, no_upload = True)
        packagesMatched, brokenexecs, status = self.ClientService.libraries_test(dbconn = dbconn)
        if status != 0:
            return 1,None

        if get_files:
            return 0,brokenexecs

        if (not brokenexecs) and (not packagesMatched):
            self.updateProgress(
                                    blue("System is healthy."),
                                    importance = 2,
                                    type = "info",
                                    header = red(" @@ ")
                                )
            return 0,None

        self.updateProgress(
                                blue("Matching libraries with Spm:"),
                                importance = 1,
                                type = "info",
                                header = red(" @@ ")
                            )

        packages = set()
        for brokenexec in brokenexecs:
            self.updateProgress(
                                    red("Scanning: ")+darkgreen(brokenexec),
                                    importance = 0,
                                    type = "info",
                                    header = red(" @@ "),
                                    back = True
                                )
            packages |= self.SpmService.query_belongs(brokenexec)

        if packages:
            self.updateProgress(
                                    red("These are the matched packages:"),
                                    importance = 1,
                                    type = "info",
                                    header = red(" @@ ")
                                )
            for package in packages:
                self.updateProgress(
                                        blue(package),
                                        importance = 0,
                                        type = "info",
                                        header = red("     # ")
                                    )
        else:
            self.updateProgress(
                                    red("No matched packages"),
                                    importance = 1,
                                    type = "info",
                                    header = red(" @@ ")
                                )

        return 0,packages

    def depends_table_initialize(self):
        dbconn = self.openServerDatabase(read_only = False, no_upload = True)
        dbconn.regenerateDependsTable()
        dbconn.taintDatabase()
        dbconn.commitChanges()


    def create_empty_database(self, dbpath = None):
        if dbpath == None:
            dbpath = etpConst['etpdatabasefilepath']

        dbdir = os.path.dirname(dbpath)
        if not os.path.isdir(dbdir):
            os.makedirs(dbdir)

        self.updateProgress(
                                red("Initializing an empty database file with Entropy structure ..."),
                                importance = 1,
                                type = "info",
                                header = darkgreen(" * "),
                                back = True
                            )
        dbconn = self.ClientService.openGenericDatabase(dbpath)
        dbconn.initializeDatabase()
        dbconn.commitChanges()
        dbconn.closeDB()
        self.updateProgress(
                                red("Entropy database file ")+bold(dbpath)+red(" successfully initialized."),
                                importance = 1,
                                type = "info",
                                header = darkgreen(" * ")
                            )


    def package_injector(self, package_file, branch = etpConst['branch'], inject = False):

        dbconn = self.openServerDatabase(read_only = False, no_upload = True)
        self.updateProgress(
                                red("[repo: %s] adding package: %s" % (
                                            darkgreen(etpConst['officialrepositoryid']),
                                            bold(os.path.basename(package_file)),
                                        )
                                ),
                                importance = 1,
                                type = "info",
                                header = brown(" * "),
                                back = True
                            )
        mydata = self.ClientService.extract_pkg_metadata(package_file, etpBranch = branch, inject = inject)
        idpackage, revision, x = dbconn.handlePackage(mydata)
        del x

        # add package info to our current server repository
        dbconn.removePackageFromInstalledTable(idpackage)
        dbconn.addPackageToInstalledTable(idpackage,etpConst['officialrepositoryid'])
        dbconn.commitChanges()
        atom = dbconn.retrieveAtom(idpackage)

        self.updateProgress(

                                red("[repo: %s] added package: %s rev: %s" % (
                                            darkgreen(etpConst['officialrepositoryid']),
                                            bold(atom),
                                            bold(str(revision)),
                                        )
                                ),
                                importance = 1,
                                type = "info",
                                header = brown(" * ")
                            )

        return idpackage

    # this function changes the final repository package filename
    def _setup_repository_package_filename(self, idpackage):

        dbconn = self.openServerDatabase(read_only = False, no_upload = True)

        downloadurl = dbconn.retrieveDownloadURL(idpackage)
        packagerev = dbconn.retrieveRevision(idpackage)
        downloaddir = os.path.dirname(downloadurl)
        downloadfile = os.path.basename(downloadurl)
        # add revision
        downloadfile = downloadfile[:-5]+"~%s%s" % (packagerev,etpConst['packagesext'],)
        downloadurl = os.path.join(downloaddir,downloadfile)

        # update url
        dbconn.setDownloadURL(idpackage,downloadurl)

        return downloadurl

    def add_package_to_repository(self, package_filename, requested_branch, inject = False):

        upload_dir = os.path.join(etpConst['packagesserveruploaddir'],requested_branch)
        if not os.path.isdir(upload_dir):
            os.makedirs(upload_dir)

        # inject into database
        idpackage = self.package_injector(package_filename, branch = requested_branch, inject = inject)

        download_url = self._setup_repository_package_filename(idpackage)
        downloadfile = os.path.basename(download_url)
        destination_path = os.path.join(upload_dir,downloadfile)
        shutil.move(package_filename,destination_path)

        self.updateProgress(
                                red(
                                    "[repo: %s] injecting entropy metadata: %s" % (
                                            darkgreen(etpConst['officialrepositoryid']),
                                            bold(downloadfile),
                                        )
                                    ),
                                importance = 1,
                                type = "info",
                                header = brown(" * "),
                                back = True
                            )

        dbconn = self.openServerDatabase(read_only = True, no_upload = True)
        data = dbconn.getPackageData(idpackage)
        dbpath = self.ClientService.inject_entropy_database_into_package(destination_path, data)
        digest = self.entropyTools.md5sum(destination_path)
        # update digest
        dbconn.setDigest(idpackage,digest)
        self.entropyTools.createHashFile(destination_path)
        # remove garbage
        os.remove(dbpath)

        self.updateProgress(
                                red(
                                    "[repo: %s] injection complete: %s" % (
                                            darkgreen(etpConst['officialrepositoryid']),
                                            bold(downloadfile),
                                        )
                                    ),
                                importance = 1,
                                type = "info",
                                header = brown(" * ")
                            )
        dbconn.commitChanges()


    def quickpkg(self, atom,storedir):
        return self.SpmService.quickpkg(atom,storedir)


    def remove_packages(self, idpackages):
        dbconn = self.openServerDatabase(read_only = False, no_upload = True)
        for idpackage in idpackages:
            atom = dbconn.retrieveAtom(idpackage)
            self.updateProgress(
                    red("[repo:%s] removing package: %s" % (darkgreen(etpConst['officialrepositoryid']),atom,)),
                    importance = 1,
                    type = "info",
                    header = brown(" @@ "),
                    back = True
                )
            dbconn.removePackage(idpackage)
        self.close_server_database(dbconn)
        self.updateProgress(
                red("[repo:%s] removal complete" % (darkgreen(etpConst['officialrepositoryid']),)),
                importance = 1,
                type = "info",
                header = brown(" @@ ")
            )


    def bump_database(self):
        dbconn = self.openServerDatabase(read_only = False, no_upload = True)
        dbconn.taintDatabase()
        self.close_server_database(dbconn)

    def get_local_database_revision(self):
        dbrev_file = os.path.join(etpConst['etpdatabasedir'],etpConst['etpdatabaserevisionfile'])
        if os.path.isfile(dbrev_file):
            f = open(dbrev_file)
            rev = f.readline().strip()
            f.close()
            try:
                rev = int(rev)
            except ValueError:
                self.updateProgress(
                    red(
                        "[repo: %s] invalid database revision: %s - defaulting to 0" % (
                                darkgreen(etpConst['officialrepositoryid']),
                                bold(rev),
                            )
                        ),
                    importance = 2,
                    type = "error",
                    header = darkred(" !!! ")
                )
                rev = 0
            return rev
        else:
            return 0

    def scan_package_changes(self):

        dbconn = self.openServerDatabase(read_only = True, no_upload = True)

        installed_packages = self.SpmService.get_installed_packages_counter()
        installed_counters = set()
        toBeAdded = set()
        toBeRemoved = set()
        toBeInjected = set()

        # packages to be added
        for x in installed_packages:
            installed_counters.add(x[1])
            counter = dbconn.isCounterAvailable(x[1], branch = etpConst['branch'], branch_operator = "<=")
            if not counter:
                toBeAdded.add(tuple(x))

        # packages to be removed from the database
        database_counters = dbconn.listAllCounters(branch = etpConst['branch'], branch_operator = "<=")
        for x in database_counters:

            if x[0] < 0:
                continue # skip packages without valid counter

            if x[0] not in installed_counters:

                # check if the package is in toBeAdded
                if toBeAdded:

                    atom = dbconn.retrieveAtom(x[1])
                    atomkey = self.entropyTools.dep_getkey(atom)
                    atomtag = self.entropyTools.dep_gettag(atom)
                    atomslot = dbconn.retrieveSlot(x[1])

                    add = True
                    for pkgdata in toBeAdded:
                        addslot = self.SpmService.get_package_slot(pkgdata[0])
                        addkey = self.entropyTools.dep_getkey(pkgdata[0])
                        # workaround for ebuilds not having slot
                        if addslot == None:
                            addslot = '0'                                              # handle tagged packages correctly
                        if (atomkey == addkey) and ((str(atomslot) == str(addslot)) or (atomtag != None)):
                            # do not add to toBeRemoved
                            add = False
                            break
                    if add:
                        dbtag = dbconn.retrieveVersionTag(x[1])
                        if dbtag != '':
                            is_injected = dbconn.isInjected(x[1])
                            if not is_injected:
                                toBeInjected.add(x[1])
                        else:
                            toBeRemoved.add(x[1])

                else:

                    dbtag = dbconn.retrieveVersionTag(x[1])
                    if dbtag != '':
                        is_injected = dbconn.isInjected(x[1])
                        if not is_injected:
                            toBeInjected.add(x[1])
                    else:
                        toBeRemoved.add(x[1])

        return toBeAdded, toBeRemoved, toBeInjected


    def transform_package_into_injected(self, idpackage):
        dbconn = self.openServerDatabase(read_only = False, no_upload = True)
        counter = dbconn.getNewNegativeCounter()
        dbconn.setCounter(idpackage,counter)
        dbconn.setInjected(idpackage)

    def initialize_server_database(self):

        self.close_server_databases()
        revisions_match = {}
        treeupdates_actions = []
        injected_packages = set()
        idpackages = set()

        self.updateProgress(
                red("Initializing Entropy database..."),
                importance = 1,
                type = "info",
                header = darkgreen(" * "),
                back = True
            )

        if os.path.isfile(etpConst['etpdatabasefilepath']):

            dbconn = self.openServerDatabase(read_only = True, no_upload = True)

            if dbconn.doesTableExist("baseinfo") and dbconn.doesTableExist("extrainfo"):
                idpackages = dbconn.listAllIdpackages()

            if dbconn.doesTableExist("treeupdatesactions"):
                treeupdates_actions = dbconn.listAllTreeUpdatesActions()

            # save list of injected packages
            if dbconn.doesTableExist("injected") and dbconn.doesTableExist("extrainfo"):
                injected_packages = dbconn.listAllInjectedPackages(justFiles = True)
                injected_packages = set([os.path.basename(x) for x in injected_packages])

            for idpackage in idpackages:
                package = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
                branch = dbconn.retrieveBranch(idpackage)
                revision = dbconn.retrieveRevision(idpackage)
                revisions_match[package] = (branch,revision,)

            self.close_server_database(dbconn)

            self.updateProgress(
                bold("WARNING")+red(": database file already exists. Overwriting."),
                importance = 1,
                type = "warning",
                header = red(" * ")
            )

            rc = self.askQuestion("Do you want to continue ?")
            if rc == "No":
                return
            os.remove(etpConst['etpdatabasefilepath'])


        # initialize
        dbconn = self.openServerDatabase(read_only = False, no_upload = True)
        dbconn.initializeDatabase()

        revisions_file = "/entropy-revisions-dump.txt"
        # dump revisions - as a backup
        if revisions_match:
            self.updateProgress(
                red("Dumping current revisions to file %s") % (bold(revisions_file),),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
            f = open(revisions_file,"w")
            f.write(str(revisions_match))
            f.flush()
            f.close()

        # dump treeupdates - as a backup
        treeupdates_file = "/entropy-treeupdates-dump.txt"
        if treeupdates_actions:
            self.updateProgress(
                red("Dumping current tree updates actions to file %s") % (bold(treeupdates_file),),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
            f = open(treeupdates_file,"w")
            f.write(str(treeupdates_actions))
            f.flush()
            f.close()

        rc = self.askQuestion("Would you like to sync packages first (important if you don't have them synced) ?")
        if rc == "Yes":
            self.MirrorsService.sync_packages()

        # fill tree updates actions
        if treeupdates_actions:
            dbconn.addTreeUpdatesActions(treeupdates_actions)

        # now fill the database
        pkgbranches = list(self.list_all_branches())

        for mybranch in pkgbranches:

            pkglist = os.listdir(os.path.join(etpConst['packagesserverbindir'],mybranch))
            # filter .md5 and .expired packages
            pkglist = [x for x in pkglist if x[-5:] == etpConst['packagesext'] and not os.path.isfile(etpConst['packagesserverbindir']+"/"+mybranch+"/"+x+etpConst['packagesexpirationfileext'])]

            if not pkglist:
                continue

            self.updateProgress(
                red("Reinitializing Entropy database for branch %s using Packages in the repository..." % (bold(mybranch),)),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )

            counter = 0
            maxcount = str(len(pkglist))
            for pkg in pkglist:
                counter += 1

                self.updateProgress(
                    red("[repo: %s] [%s:%s/%s] analyzing: %s" % (etpConst['officialrepositoryid'],brown(mybranch),darkgreen(counter),blue(maxcount),bold(pkg),) ),
                    importance = 1,
                    type = "info",
                    header = " ",
                    back = True
                )

                doinject = False
                if pkg in injected_packages:
                    doinject = True

                mydata = self.ClientService.extract_pkg_metadata(etpConst['packagesserverbindir']+"/"+mybranch+"/"+pkg, mybranch, inject = doinject)

                # get previous revision
                revision_avail = revisions_match.get(pkg)
                addRevision = 0
                if (revision_avail != None):
                    if mybranch == revision_avail[0]:
                        addRevision = revision_avail[1]

                idpk, revision, mydata_upd = dbconn.addPackage(mydata, revision = addRevision)

                self.updateProgress(
                    red("[repo: %s] [%s:%s/%s] added package: %s, revision: %s" % (etpConst['officialrepositoryid'],brown(mybranch),darkgreen(counter),blue(maxcount),bold(pkg),mydata_upd['revision'],) ),
                    importance = 1,
                    type = "info",
                    header = " ",
                    back = True
                )

        dbconn.commitChanges()
        self.depends_table_initialize()
        self.close_server_databases()
        return 0

    def match_packages(self, packages):

        dbconn = self.openServerDatabase(read_only = True, no_upload = True)
        if "world" in packages:
            return dbconn.listAllIdpackages(),True
        else:
            idpackages = set()
            for package in packages:
                matches = dbconn.atomMatch(package, multiMatch = True, matchBranches = etpConst['branches'])
                if matches[1] == 0:
                    idpackages |= matches[0]
                else:
                    self.updateProgress(
                        red("Attention: cannot match: %s" % (bold(package),) ),
                        importance = 1,
                        type = "warning",
                        header = darkred(" !!! ")
                    )
            return idpackages,False

    def verify_remote_packages(self, packages, ask = True):

        self.updateProgress(
                red("[remote] Integrity verification of the selected packages:"),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
        )

        idpackages, world = self.match_packages(packages)
        dbconn = self.openServerDatabase(read_only = True, no_upload = True)

        if world:
            self.updateProgress(
                    red("All the packages in the Entropy Packages repository will be checked."),
                    importance = 1,
                    type = "info",
                    header = "    "
            )
        else:
            self.updateProgress(
                    red("This is the list of the packages that would be checked:"),
                    importance = 1,
                    type = "info",
                    header = "    "
            )
            for idpackage in idpackages:
                pkgatom = dbconn.retrieveAtom(idpackage)
                pkgbranch = dbconn.retrieveBranch(idpackage)
                pkgfile = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
                self.updateProgress(
                        red(pkgatom)+" -> "+bold(os.path.join(pkgbranch,pkgfile)),
                        importance = 1,
                        type = "info",
                        header = darkgreen("   - ")
                )

        if ask:
            rc = self.askQuestion("Would you like to continue ?")
            if rc == "No":
                return set(),set(),{}

        match = set()
        not_match = set()
        broken_packages = {}

        for uri in etpConst['activatoruploaduris']:

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
            self.updateProgress(
                red("[repo: %s] Working on mirror: %s" % (etpConst['officialrepositoryid'],brown(crippled_uri),) ),
                importance = 1,
                type = "info",
                header = green(" * ")
            )


            totalcounter = str(len(idpackages))
            currentcounter = 0

            for idpackage in idpackages:

                currentcounter += 1
                pkgfile = dbconn.retrieveDownloadURL(idpackage)
                pkgbranch = dbconn.retrieveBranch(idpackage)
                pkgfilename = os.path.basename(pkgfile)

                self.updateProgress(
                    red("[repo: %s|mirror: %s] [%s/%s] checking hash: %s" % (
                                    etpConst['officialrepositoryid'],
                                    brown(crippled_uri),
                                    currentcounter,
                                    totalcounter,
                                    blue(os.path.join(pkgbranch,pkgfilename)),
                                )
                    ),
                    importance = 1,
                    type = "info",
                    header = green(" * "),
                    back = True
                )

                ckOk = False
                ck = self.ClientService.get_remote_package_checksum(crippled_uri, pkgfilename, pkgbranch)
                if ck == None:
                    self.updateProgress(
                        red("digest verification of %s not supported" % (green(pkgfilename),)),
                        importance = 1,
                        type = "info",
                        header = "       -> "
                    )
                elif len(ck) == 32:
                    ckOk = True
                else:
                    self.updateProgress(
                        red("digest verification of %s failed for unknown reasons" % (green(pkgfilename),)),
                        importance = 1,
                        type = "info",
                        header = "       -> "
                    )

                if ckOk:
                    match.add(idpackage)
                else:
                    not_match.add(idpackage)
                    self.updateProgress(
                        red("[repo: %s|mirror: %s] [%s/%s] package: %s NOT healthy" % (
                                        etpConst['officialrepositoryid'],
                                        brown(crippled_uri),
                                        currentcounter,
                                        totalcounter,
                                        blue(os.path.join(pkgbranch,pkgfilename)),
                                    )
                        ),
                        importance = 1,
                        type = "warning",
                        header = darkred(" * ")
                    )
                    if not broken_packages.has_key(crippled_uri):
                        broken_packages[crippled_uri] = []
                    broken_packages[crippled_uri].append(os.path.join(pkgbranch,pkgfilename))

            if broken_packages:
                self.updateProgress(
                    blue("This is the list of broken packages:"),
                    importance = 1,
                    type = "info",
                    header = red(" * ")
                )
                for mirror in broken_packages.keys():
                    self.updateProgress(
                        brown("Mirror: %s") % (bold(mirror),),
                        importance = 1,
                        type = "info",
                        header = red("   <> ")
                    )
                    for bp in broken_packages[mirror]:
                        self.updateProgress(
                            blue(bp),
                            importance = 1,
                            type = "info",
                            header = red("      - ")
                        )

            self.updateProgress(
                red("[repo: %s|mirror: %s] Statistics:" % (
                                etpConst['officialrepositoryid'],
                                brown(crippled_uri),
                            )
                ),
                importance = 1,
                type = "info",
                header = red(" * ")
            )
            self.updateProgress(
                red("[repo: %s|mirror: %s] Number of checked packages: %s" % (
                                etpConst['officialrepositoryid'],
                                brown(crippled_uri),
                                len(match)+len(not_match),
                            )
                ),
                importance = 1,
                type = "info",
                header = red(" * ")
            )
            self.updateProgress(
                red("[repo: %s|mirror: %s] Number of healthy packages: %s" % (
                                etpConst['officialrepositoryid'],
                                brown(crippled_uri),
                                len(match),
                            )
                ),
                importance = 1,
                type = "info",
                header = red(" * ")
            )
            self.updateProgress(
                red("[repo: %s|mirror: %s] Number of broken packages: %s" % (
                                etpConst['officialrepositoryid'],
                                brown(crippled_uri),
                                len(not_match),
                            )
                ),
                importance = 1,
                type = "info",
                header = red(" * ")
            )

        return match,not_match,broken_packages


    def verify_local_packages(self, packages, ask = True):

        self.updateProgress(
                red("[local] Integrity verification of the selected packages:"),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
        )

        idpackages, world = self.match_packages(packages)
        dbconn = self.openServerDatabase(read_only = True, no_upload = True)

        to_download = set()
        available = set()
        for idpackage in idpackages:

            pkgatom = dbconn.retrieveAtom(idpackage)
            pkgbranch = dbconn.retrieveBranch(idpackage)
            pkgfile = dbconn.retrieveDownloadURL(idpackage)
            pkgfile = os.path.basename(pkgfile)

            bindir_path = os.path.join(etpConst['packagesserverbindir'],pkgbranch+"/"+pkgfile)
            uploaddir_path = os.path.join(etpConst['packagesserveruploaddir'],pkgbranch+"/"+pkgfile)

            if os.path.isfile(bindir_path) and not world:
                self.updateProgress(
                        red("[%s] %s :: %s" % (darkgreen("available"),pkgatom,pkgfile,)),
                        importance = 0,
                        type = "info",
                        header = darkgreen("   # ")
                )
                available.add(idpackage)
            elif os.path.isfile(uploaddir_path) and not world:
                self.updateProgress(
                        red("[%s] %s :: %s" % (darkred("upload/ignored"),pkgatom,pkgfile,)),
                        importance = 0,
                        type = "info",
                        header = darkgreen("   # ")
                )
            else:
                self.updateProgress(
                        red("[%s] %s :: %s" % (brown("download"),pkgatom,pkgfile,)),
                        importance = 0,
                        type = "info",
                        header = darkgreen("   # ")
                )
                to_download.add((idpackage,pkgfile,pkgbranch))

        if ask:
            rc = self.askQuestion("Would you like to continue ?")
            if rc == "No":
                return set(),set(),set(),set()


        fine = set()
        failed = set()
        downloaded_fine = set()
        downloaded_errors = set()

        if to_download:

            not_downloaded = set()
            self.updateProgress(
                    red("Starting to download missing files..."),
                    importance = 1,
                    type = "info",
                    header = "   "
            )
            for uri in etpConst['activatoruploaduris']:

                if not_downloaded:
                    self.updateProgress(
                            red("Trying to search missing or broken files on another mirror ..."),
                            importance = 1,
                            type = "info",
                            header = "   "
                    )
                    to_download = not_downloaded.copy()
                    not_downloaded = set()

                for pkg in to_download:
                    rc = self.MirrorsService.download_package(uri,pkg[1],pkg[2])
                    if rc == None:
                        not_downloaded.add((pkg[1],pkg[2]))
                    elif not rc:
                        not_downloaded.add((pkg[1],pkg[2]))
                    elif rc:
                        downloaded_fine.add(pkg[0])
                        available.add(pkg[0])

                if not not_downloaded:
                    self.updateProgress(
                            red("All the binary packages have been downloaded successfully."),
                            importance = 1,
                            type = "info",
                            header = "   "
                    )
                    break

            if not_downloaded:
                self.updateProgress(
                        red("These are the packages that cannot be found online:"),
                        importance = 1,
                        type = "info",
                        header = "   "
                )
                for i in not_downloaded:
                    downloaded_errors.add(i[0])
                    self.updateProgress(
                            brown(i[0])+" in "+blue(i[1]),
                            importance = 1,
                            type = "warning",
                            header = red("    * ")
                    )
                    downloaded_errors.add(i[0])
                self.updateProgress(
                        red("They won't be checked."),
                        importance = 1,
                        type = "warning",
                        header = "   "
                )

        totalcounter = str(len(available))
        currentcounter = 0
        for idpackage in available:
            currentcounter += 1
            pkgfile = dbconn.retrieveDownloadURL(idpackage)
            pkgbranch = dbconn.retrieveBranch(idpackage)
            pkgfile = os.path.basename(pkgfile)

            self.updateProgress(
                    red("[branch:%s] checking hash of %s" % (pkgbranch,pkgfile,)),
                    importance = 1,
                    type = "info",
                    header = "   ",
                    back = True,
                    count = (currentcounter,totalcounter,)
            )

            storedmd5 = dbconn.retrieveDigest(idpackage)
            pkgpath = os.path.join(etpConst['packagesserverbindir'],pkgbranch+"/"+pkgfile)
            result = self.entropyTools.compareMd5(pkgpath,storedmd5)
            if result:
                fine.add(idpackage)
            else:
                failed.add(idpackage)
                self.updateProgress(
                        red("[branch:%s] package %s is corrupted, stored checksum: %s" % (pkgbranch,pkgfile,brown(storedmd5),)),
                        importance = 1,
                        type = "info",
                        header = "   ",
                        count = (currentcounter,totalcounter,)
                )

        if failed:
            self.updateProgress(
                    blue("This is the list of the BROKEN packages:"),
                    importance = 1,
                    type = "warning",
                    header =  darkred("  # ")
            )
            for idpackage in failed:
                branch = dbconn.retrieveBranch(idpackage)
                dp = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
                self.updateProgress(
                        blue("[branch:%s] %s" % (branch,dp,)),
                        importance = 0,
                        type = "warning",
                        header =  brown("    # ")
                )

        # print stats
        self.updateProgress(
            red("Statistics:"),
            importance = 1,
            type = "info",
            header = blue(" * ")
        )
        self.updateProgress(
            blue("Number of checked packages: %s" % (len(fine)+len(failed),) ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            blue("Number of healthy packages: %s" % (len(fine),) ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            blue("Number of broken packages: %s" % (len(failed),) ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            blue("Number of downloaded packages: %s" % (len(downloaded_fine),) ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )
        self.updateProgress(
            blue("Number of failed downloads: %s" % (len(downloaded_errors),) ),
            importance = 0,
            type = "info",
            header = brown("   # ")
        )

        self.close_server_database(dbconn)
        return fine, failed, downloaded_fine, downloaded_errors


    def list_all_branches(self):
        dbconn = self.openServerDatabase(just_reading = True)
        branches = dbconn.listAllBranches()
        for branch in branches:
            branch_path = os.path.join(etpConst['packagesserveruploaddir'],branch)
            if not os.path.isdir(branch_path):
                os.makedirs(branch_path)
            branch_path = os.path.join(etpConst['packagesserverbindir'],branch)
            if not os.path.isdir(branch_path):
                os.makedirs(branch_path)


    def switch_packages_branch(self, idpackages, to_branch):

        self.updateProgress(
            red("Switching selected packages..."),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )
        dbconn = self.openServerDatabase(read_only = False, no_upload = True)

        already_switched = set()
        not_found = set()
        switched = set()
        ignored = set()
        no_checksum = set()

        for idpackage in idpackages:

            cur_branch = dbconn.retrieveBranch(idpackage)
            atom = dbconn.retrieveAtom(idpackage)
            if cur_branch == to_branch:
                already_switched.add(idpackage)
                self.updateProgress(
                    red("Ignoring %s, already in branch %s" % (bold(atom),cur_branch,)),
                    importance = 0,
                    type = "info",
                    header = darkgreen(" * ")
                )
                ignored.add(idpackage)
                continue
            old_filename = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
            # check if file exists
            frompath = os.path.join(etpConst['packagesserverbindir'],cur_branch+"/"+old_filename)
            if not os.path.isfile(frompath):
                self.updateProgress(
                    red("[%s=>%s] %s, cannot switch, package not found!" % (cur_branch,to_branch,atom,)),
                    importance = 0,
                    type = "warning",
                    header = darkred(" !!! ")
                )
                not_found.add(idpackage)
                continue

            self.updateProgress(
                red("[%s=>%s] %s, configuring package information..." % (cur_branch,to_branch,atom,)),
                importance = 0,
                type = "info",
                header = darkgreen(" * "),
                back = True
            )
            dbconn.switchBranch(idpackage,to_branch)
            dbconn.commitChanges()

            # LOCAL
            self.updateProgress(
                red("[%s -> %s] %s, moving file locally..." % (cur_branch,to_branch,atom,)),
                importance = 0,
                type = "info",
                header = darkgreen(" * "),
                back = True
            )
            new_filename = os.path.basename(dbconn.retrieveDownloadURL(idpackage))
            topath = os.path.join(etpConst['packagesserverbindir'],to_branch)
            if not os.path.isdir(topath):
                os.makedirs(topath)

            topath = os.path.join(topath,new_filename)
            shutil.move(frompath,topath)
            if os.path.isfile(frompath+etpConst['packageshashfileext']):
                shutil.move(frompath+etpConst['packageshashfileext'],topath+etpConst['packageshashfileext'])
            else:
                self.updateProgress(
                    red("[%s=>%s] %s, cannot find checksum to migrate!" % (cur_branch,to_branch,atom,)),
                    importance = 0,
                    type = "warning",
                    header = darkred(" !!! ")
                )
                no_checksum.add(idpackage)

            # REMOTE
            self.updateProgress(
                red("[%s=>%s] %s, moving file remotely..." % (cur_branch,to_branch,atom,)),
                importance = 0,
                type = "info",
                header = darkgreen(" * "),
                back = True
            )

            for uri in etpConst['activatoruploaduris']:

                crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
                self.updateProgress(
                    red("[%s=>%s] %s, moving file remotely on: %s" % (cur_branch,to_branch,atom,crippled_uri,)),
                    importance = 0,
                    type = "info",
                    header = darkgreen(" * "),
                    back = True
                )

                ftp = self.FtpInterface(uri, self)
                ftp.setCWD(etpConst['binaryurirelativepath'])
                # create directory if it doesn't exist
                if not ftp.isFileAvailable(to_branch):
                    ftp.mkdir(to_branch)

                fromuri = os.path.join(cur_branch,old_filename)
                touri = os.path.join(to_branch,new_filename)
                ftp.renameFile(fromuri,touri)
                ftp.renameFile(fromuri+etpConst['packageshashfileext'],touri+etpConst['packageshashfileext'])
                ftp.closeConnection()

            switched.add(idpackage)

        dbconn.commitChanges()
        self.close_server_database(dbconn)
        self.updateProgress(
            red("[%s=>%s] migration loop completed." % (cur_branch,to_branch,)),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )

        return switched, already_switched, ignored, not_found, no_checksum


class ServerMirrorsInterface:

    def __init__(self,  ServerInstance,
                        upload_mirrors = etpConst['activatoruploaduris'],
                        download_mirrors = etpConst['activatordownloaduris']):

        if not isinstance(ServerInstance,ServerInterface):
            raise exceptionTools.IncorrectParameter("IncorrectParameter: a valid ServerInterface instance is needed")

        self.Entropy = ServerInterface
        self.entropyTools = self.Entropy.entropyTools
        self.dumpTools = self.Entropy.dumpTools
        self.upload_mirrors = upload_mirrors[:]
        self.download_mirrors = download_mirrors[:]
        self.FtpInterface = self.Entropy.FtpInterface
        self.rssFeed = self.Entropy.rssFeed
        self.repository_directory = etpConst['etpdatabasedir']


    def set_upload_mirrors(self, mirrors):
        if not isinstance(mirrors,list):
            raise exceptionTools.InvalidDataType("InvalidDataType: set_upload_mirrors needs a list type")
        self.upload_mirrors = mirrors[:]

    def set_download_mirrors(self, mirrors):
        if not isinstance(mirrors,list):
            raise exceptionTools.InvalidDataType("InvalidDataType: set_download_mirrors needs a list type")
        self.download_mirrors = mirrors[:]

    def lock_mirrors(self, lock = True, mirrors = []):

        if not mirrors:
            mirrors = self.upload_mirrors[:]

        issues = False
        for uri in mirrors:

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)

            lock_text = "unlocking"
            if lock: lock_text = "locking"
            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s] %s mirror..." % (etpConst['officialrepositoryid'],crippled_uri,lock_text,)),
                importance = 1,
                type = "info",
                header = brown(" * "),
                back = True
            )

            ftp = self.FtpInterface(uri, self.Entropy)
            ftp.setCWD(etpConst['etpurirelativepath'])

            if lock and ftp.isFileAvailable(etpConst['etpdatabaselockfile']):
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s] mirror already locked" % (etpConst['officialrepositoryid'],crippled_uri,)),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                ftp.closeConnection()
                continue
            elif not lock and not ftp.isFileAvailable(etpConst['etpdatabaselockfile']):
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s] mirror already unlocked" % (etpConst['officialrepositoryid'],crippled_uri,)),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                ftp.closeConnection()
                continue

            if lock:
                rc = self.do_mirror_lock(uri, ftp)
            else:
                rc = self.do_mirror_unlock(uri, ftp)
            ftp.closeConnection()
            if not rc: issues = True

        if not issues:
            database_taint_file = os.path.join(etpConst['etpdatabasedir'],etpConst['etpdatabasetaintfile'])
            if os.path.isfile(database_taint_file):
                os.remove(database_taint_file)

        return issues

    # this functions makes entropy clients to not download anything from the chosen
    # mirrors. it is used to avoid clients to download databases while we're uploading
    # a new one.
    def lock_mirrors_for_download(self, lock = True, mirrors = []):

        if not mirrors:
            mirrors = self.upload_mirrors[:]

        issues = False
        for uri in mirrors:

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)

            lock_text = "unlocking"
            if lock: lock_text = "locking"
            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s] %s mirror for download..." % (etpConst['officialrepositoryid'],crippled_uri,lock_text,)),
                importance = 1,
                type = "info",
                header = brown(" * "),
                back = True
            )

            ftp = self.FtpInterface(uri, self.Entropy)
            ftp.setCWD(etpConst['etpurirelativepath'])

            if lock and ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile']):
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s] mirror already locked for download" % (etpConst['officialrepositoryid'],crippled_uri,)),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                ftp.closeConnection()
                continue
            elif not lock and not ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile']):
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s] mirror already unlocked for download" % (etpConst['officialrepositoryid'],crippled_uri,)),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                ftp.closeConnection()
                continue

            if lock:
                rc = self.do_mirror_lock(uri, ftp, dblock = False)
            else:
                rc = self.do_mirror_unlock(uri, ftp, dblock = False)
            ftp.closeConnection()
            if not rc: issues = True

        return issues

    def do_mirror_lock(self, uri, ftp_connection = None, dblock = True):

        if not ftp_connection:
            ftp_connection = self.FtpInterface(uri, self.Entropy)

        ftp_connection.setCWD(etpConst['etpurirelativepath'])
        crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
        lock_string = ''
        if dblock:
            self.create_local_database_lockfile()
            lock_file = self.get_database_lockfile()
        else:
            lock_string = 'for download'
            self.create_local_database_download_lockfile()
            lock_file = self.get_database_download_lockfile()

        rc = ftp_connection.uploadFile(lock_file, ascii = True)
        if rc:
            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s] mirror successfully locked %s" % (etpConst['officialrepositoryid'],crippled_uri,lock_string,)),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
        else:
            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s] lock error: %s - mirror not locked %s" % (etpConst['officialrepositoryid'],crippled_uri,rc,lock_string,)),
                importance = 1,
                type = "error",
                header = darkred(" * ")
            )
            self.remove_local_database_lockfile()

        return rc


    def do_mirror_unlock(self, uri, ftp_connection, dblock = True):

        if not ftp_connection:
            ftp_connection = self.FtpInterface(uri, self.Entropy)

        ftp_connection.setCWD(etpConst['etpurirelativepath'])
        crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)

        if dblock:
            dbfile = etpConst['etpdatabaselockfile']
        else:
            dbfile = etpConst['etpdatabasedownloadlockfile']
        rc = ftp_connection.deleteFile(dbfile)
        if rc:
            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s] mirror successfully unlocked" % (etpConst['officialrepositoryid'],crippled_uri,)),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
            if dblock:
                self.remove_local_database_lockfile()
            else:
                self.remove_local_database_download_lockfile()
        else:
            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s] unlock error: %s - mirror not unlocked" % (etpConst['officialrepositoryid'],crippled_uri,rc,)),
                importance = 1,
                type = "error",
                header = darkred(" * ")
            )

        return rc

    def get_database_lockfile(self):
        return os.path.join(self.repository_directory,etpConst['etpdatabaselockfile'])

    def get_database_download_lockfile(self):
        return os.path.join(self.repository_directory,etpConst['etpdatabasedownloadlockfile'])

    def create_local_database_download_lockfile(self):
        lock_file = self.get_database_download_lockfile()
        f = open(lock_file,"w")
        f.write("download locked")
        f.flush()
        f.close()

    def create_local_database_lockfile(self):
        lock_file = self.get_database_lockfile()
        f = open(lock_file,"w")
        f.write("database locked")
        f.flush()
        f.close()

    def remove_local_database_lockfile(self):
        lock_file = self.get_database_lockfile()
        if os.path.isfile(lock_file):
            os.remove(lock_file)

    def remove_local_database_download_lockfile(self):
        lock_file = self.get_database_download_lockfile()
        if os.path.isfile(lock_file):
            os.remove(lock_file)

    def download_package(self, uri, pkgfile, branch):

        crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)

        tries = 0
        while tries < 5:
            tries += 1

            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s|#%s] connecting to download package: %s" % (etpConst['officialrepositoryid'],crippled_uri,tries,pkgfile,)),
                importance = 1,
                type = "info",
                header = darkgreen(" * "),
                back = True
            )

            ftp = self.FtpInterface(uri, self.Entropy)
            dirpath = os.path.join(etpConst['binaryurirelativepath'],branch)
            ftp.setCWD(dirpath)

            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s|#%s] downloading package: %s" % (etpConst['officialrepositoryid'],crippled_uri,tries,pkgfile,)),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )

            download_path = os.path.join(etpConst['packagesserverbindir'],branch)
            rc = ftp.downloadFile(pkgfile,download_path)
            if not rc:
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s|#%s] package: %s does not exist" % (etpConst['officialrepositoryid'],crippled_uri,tries,pkgfile,)),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                ftp.closeConnection()
                return rc

            dbconn = self.Entropy.openServerDatabase(read_only = True, no_upload = True)
            idpackage = dbconn.getIDPackageFromDownload(pkgfile,branch)
            if idpackage == -1:
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s|#%s] package: %s is not listed in the current repository database!!" % (etpConst['officialrepositoryid'],crippled_uri,tries,pkgfile,)),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                ftp.closeConnection()
                return 0

            storedmd5 = dbconn.retrieveDigest(idpackage)
            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s|#%s] verifying checksum of package: %s" % (etpConst['officialrepositoryid'],crippled_uri,tries,pkgfile,)),
                importance = 1,
                type = "info",
                header = darkgreen(" * "),
                back = True
            )

            pkg_path = os.path.join(download_path,pkgfile)
            md5check = self.entropyTools.compareMd5(pkg_path,storedmd5)
            if md5check:
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s|#%s] package: %s downloaded successfully" % (etpConst['officialrepositoryid'],crippled_uri,tries,pkgfile,)),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )
                return True
            else:
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s|#%s] package: %s checksum does not match. re-downloading..." % (etpConst['officialrepositoryid'],crippled_uri,tries,pkgfile,)),
                    importance = 1,
                    type = "warning",
                    header = darkred(" * ")
                )
                if os.path.isfile(pkg_path):
                    os.remove(pkg_path)

            continue

        # if we get here it means the files hasn't been downloaded properly
        self.Entropy.updateProgress(
            red("[repo:%s|mirror:%s|#%s] package: %s seems broken. Consider to re-package it. Giving up!" % (etpConst['officialrepositoryid'],crippled_uri,tries,pkgfile,)),
            importance = 1,
            type = "error",
            header = darkred(" !!! ")
        )
        return False


    def get_remote_databases_status(self):

        data = []
        for uri in etpConst['activatoruploaduris']:

            ftp = self.FtpInterface(uri, self.Entropy)
            ftp.setCWD(etpConst['etpurirelativepath'])
            cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
            if cmethod == None:
                raise exceptionTools.InvalidDataType("InvalidDataType: wrong database compression method passed.")
            compressedfile = etpConst[cmethod[2]]

            revision = 0
            rc1 = ftp.isFileAvailable(compressedfile)
            rc2 = ftp.isFileAvailable(etpConst['etpdatabaserevisionfile'])
            if rc1 and rc2:
                revision_localtmppath = os.path.join(etpConst['packagestmpdir'],etpConst['etpdatabaserevisionfile'])
                ftp.downloadFile(etpConst['etpdatabaserevisionfile'],etpConst['packagestmpdir'],True)
                f = open(revision_localtmppath,"r")
                try:
                    revision = int(f.readline().strip())
                except ValueError:
                    crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
                    self.Entropy.updateProgress(
                        red("[repo:%s|mirror:%s] mirror doesn't have a valid database revision file: %s" % (etpConst['officialrepositoryid'],crippled_uri,revision,)),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    revision = 0
                f.close()
                if os.path.isfile(revision_localtmppath):
                    os.remove(revision_localtmppath)

            uripath = os.path.join(uri,etpConst['etpurirelativepath'],compressedfile)
            info = (uripath,revision)
            data.append(info)
            ftp.closeConnection()

        return data

    def is_local_database_locked(self):
        lock_file = self.get_database_lockfile()
        return os.path.isfile(lock_file)

    def get_mirrors_lock(self):

        dbstatus = []
        for uri in etpConst['activatoruploaduris']:
            data = [uri,False,False]
            ftp = FtpInterface(uri, self.Entropy)
            ftp.setCWD(etpConst['etpurirelativepath'])
            if ftp.isFileAvailable(etpConst['etpdatabaselockfile']):
                # upload locked
                data[1] = True
            if ftp.isFileAvailable(etpConst['etpdatabasedownloadlockfile']):
                # download locked
                data[2] = True
            ftp.closeConnection()
            dbstatus.append(data)
        return dbstatus

    def update_rss_feed(self):

        rss_path = etpConst['etpdatabasedir'] + "/" + etpConst['rss-name']
        rss_light_path = etpConst['etpdatabasedir'] + "/" + etpConst['rss-light-name']
        rss_dump_name = etpConst['rss-dump-name']
        db_revision_path = etpConst['etpdatabasedir'] + "/" + etpConst['etpdatabaserevisionfile']

        Rss = self.rssFeed(rss_path, maxentries = etpConst['rss-max-entries'])
        # load dump
        db_actions = self.dumpTools.loadobj(rss_dump_name)
        if db_actions:
            try:
                f = open(db_revision_path)
                revision = f.readline().strip()
                f.close()
            except (IOError, OSError):
                revision = "N/A"
            commitmessage = ''
            if etpRSSMessages['commitmessage']:
                commitmessage = ' :: '+etpRSSMessages['commitmessage']
            title = ": "+etpConst['systemname']+" "+etpConst['product'][0].upper()+etpConst['product'][1:]+" "+etpConst['branch']+" :: Revision: "+revision+commitmessage
            link = etpConst['rss-base-url']
            # create description
            added_items = db_actions.get("added")
            if added_items:
                for atom in added_items:
                    mylink = link+"?search="+atom.split("~")[0]+"&arch="+etpConst['currentarch']+"&product="+etpConst['product']
                    description = atom+": "+added_items[atom]['description']
                    Rss.addItem(title = "Added/Updated"+title, link = mylink, description = description)
            removed_items = db_actions.get("removed")
            if removed_items:
                for atom in removed_items:
                    description = atom+": "+removed_items[atom]['description']
                    Rss.addItem(title = "Removed"+title, link = link, description = description)
            light_items = db_actions.get('light')
            if light_items:
                rssLight = self.rssFeed(rss_light_path, maxentries = etpConst['rss-light-max-entries'])
                for atom in light_items:
                    mylink = link+"?search="+atom.split("~")[0]+"&arch="+etpConst['currentarch']+"&product="+etpConst['product']
                    description = light_items[atom]['description']
                    rssLight.addItem(title = "["+revision+"] "+atom, link = mylink, description = description)
                rssLight.writeChanges()

        Rss.writeChanges()
        etpRSSMessages.clear()
        self.dumpTools.removeobj(rss_dump_name)


    # f_out is a file instance
    def dump_database_to_file(self, db_path, destination_path, opener ):
        f_out = opener(destination_path, "wb")
        dbconn = self.Entropy.openServerDatabase(db_path, just_reading = True)
        dbconn.doDatabaseExport(f_out)
        self.Entropy.close_server_database(dbconn)
        f_out.close()

    def create_file_checksum(self, file_path, checksum_path):
        mydigest = self.entropyTools.md5sum(file_path)
        f = open(checksum_path,"w")
        mystring = "%s  %s\n" % (mydigest,os.path.basename(file_path),)
        f.write(mystring)
        f.flush()
        f.close()

    def compress_file(self, file_path, destination_path, opener):
        f_out = opener(destination_path, "wb")
        f_in = open(file_path,"rb")
        data = f_in.read(8192)
        while data:
            f_out.write(data)
            data = f_in.read(8192)
        f_in.close()
        try:
            f_out.flush()
        except:
            pass
        f_out.close()

    def uncompress_file(self, file_path, destination_path, opener):
        f_out = open(destination_path,"wb")
        f_in = opener(file_path,"rb")
        data = f_in.read(8192)
        while data:
            f_out.write(data)
            data = f_in.read(8192)
        f_out.flush()
        f_out.close()
        f_in.close()

    def get_files_to_sync(self, cmethod, download = False):

        critical = []
        data = {}
        data['database_revision_file'] = os.path.join(etpConst['etpdatabasedir'],etpConst['etpdatabaserevisionfile'])
        critical.append(data['database_revision_file'])
        database_package_mask_file = os.path.join(etpConst['etpdatabasedir'],etpConst['etpdatabasemaskfile'])
        if os.path.isfile(database_package_mask_file) or download:
            data['database_package_mask_file'] = os.path.join(etpConst['etpdatabasedir'],etpConst['etpdatabasemaskfile'])
            critical.append(data['database_package_mask_file'])

        database_license_whitelist_file = os.path.join(etpConst['etpdatabasedir'],etpConst['etpdatabaselicwhitelistfile'])
        if os.path.isfile(database_license_whitelist_file) or download:
            data['database_license_whitelist_file'] = database_license_whitelist_file
            if not download:
                critical.append(data['database_license_whitelist_file'])

        database_rss_file = os.path.join(etpConst['etpdatabasedir'],etpConst['rss-name'])
        if os.path.isfile(database_rss_file) or download:
            data['database_rss_file'] = database_rss_file
            if not download:
                critical.append(data['database_rss_file'])
        database_rss_light_file = os.path.join(etpConst['etpdatabasedir'],etpConst['rss-light-name'])
        if os.path.isfile(database_rss_light_file) or download:
            data['database_rss_light_file'] = database_rss_light_file
            if not download:
                critical.append(data['database_rss_light_file'])

        # EAPI 2
        if not download: # we don't need to get the dump
            data['dump_path'] = os.path.join(etpConst['etpdatabasedir'],etpConst[cmethod[3]])
            critical.append(data['dump_path'])
            data['dump_path_digest'] = os.path.join(etpConst['etpdatabasedir'],etpConst[cmethod[4]])
            critical.append(data['dump_path_digest'])

        # EAPI 1
        data['compressed_database_path'] = os.path.join(etpConst['etpdatabasedir'],etpConst[cmethod[2]])
        critical.append(data['compressed_database_path'])
        data['compressed_database_path_digest'] = os.path.join(etpConst['etpdatabasedir'],etpConst['etpdatabasehashfile'])
        critical.append(data['compressed_database_path_digest'])

        return data, critical

    class FileTransmitter:

        def __init__(   self,
                        ftp_interface,
                        entropy_interface,
                        uris,
                        files_to_upload,
                        download = False,
                        ftp_basedir = None,
                        local_basedir = None,
                        critical_files = [],
                        use_handlers = False,
                        handlers_data = {}
            ):

            self.FtpInterface = ftp_interface
            self.Entropy = entropy_interface
            if not isinstance(uris,list):
                raise exceptionTools.InvalidDataType("InvalidDataType: uris must be a list instance")
            if not isinstance(files_to_upload,(list,dict)):
                raise exceptionTools.InvalidDataType("InvalidDataType: files_to_upload must be a list or dict instance")
            self.uris = uris
            if isinstance(files_to_upload,list):
                self.myfiles = files_to_upload[:]
            else:
                self.myfiles = [x for x in files_to_upload]
                self.myfiles.sort()
            self.download = download
            if not ftp_basedir:
                self.ftp_basedir = str(etpConst['etpurirelativepath']) # default to database directory
            else:
                self.ftp_basedir = str(ftp_basedir)
            if not local_basedir:
                self.local_basedir = os.path.dirname(etpConst['etpdatabasefilepath']) # default to database directory
            else:
                self.local_basedir = str(local_basedir)
            self.critical_files = critical_files
            self.use_handlers = use_handlers
            self.handlers_data = handlers_data.copy()

        def handler_verify_upload(self, local_filepath, uri, ftp_connection, counter, maxcount):

            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s|%s|#%s|(%s/%s)] verifyng upload (if supported): %s" % (
                            etpConst['officialrepositoryid'],
                            crippled_uri,
                            action,
                            tries,
                            blue(str(counter)),
                            bold(str(maxcount)),
                            os.path.basename(local_filepath),
                    )
                ),
                importance = 0,
                type = "info",
                header = darkgreen(" * "),
                back = True
            )

            checksum = self.Entropy.ClientService.get_remote_package_checksum(
                        self.Entropy.entropyTools.extractFTPHostFromUri(uri),
                        os.path.basename(local_filepath),
                        self.handlers_data['branch']
            )
            if checksum == None:
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s|%s|#%s|(%s/%s)] digest verification: %s: %s" % (
                                etpConst['officialrepositoryid'],
                                crippled_uri,
                                action,
                                tries,
                                blue(str(counter)),
                                bold(str(maxcount)),
                                os.path.basename(local_filepath),
                                bold("not supported"),
                        )
                    ),
                    importance = 0,
                    type = "info",
                    header = darkgreen(" * ")
                )
                return True
            elif checksum == False:
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s|%s|#%s|(%s/%s)] digest verification: %s: %s" % (
                                etpConst['officialrepositoryid'],
                                crippled_uri,
                                action,
                                tries,
                                blue(str(counter)),
                                bold(str(maxcount)),
                                os.path.basename(local_filepath),
                                bold("file not found"),
                        )
                    ),
                    importance = 0,
                    type = "info",
                    header = darkgreen(" * ")
                )
                return False
            elif len(checksum) == 32:
                # valid? checking
                ckres = self.Entropy.entropyTools.compareMd5(local_filepath,checksum)
                if ckres:
                    self.Entropy.updateProgress(
                        red("[repo:%s|mirror:%s|%s|#%s|(%s/%s)] digest verification: %s: %s" % (
                                    etpConst['officialrepositoryid'],
                                    crippled_uri,
                                    action,
                                    tries,
                                    blue(str(counter)),
                                    bold(str(maxcount)),
                                    os.path.basename(local_filepath),
                                    darkgreen("so far, so good!"),
                            )
                        ),
                        importance = 0,
                        type = "info",
                        header = darkgreen(" * ")
                    )
                    return True
                else:
                    self.Entropy.updateProgress(
                        red("[repo:%s|mirror:%s|%s|#%s|(%s/%s)] digest verification: %s: %s" % (
                                    etpConst['officialrepositoryid'],
                                    crippled_uri,
                                    action,
                                    tries,
                                    blue(str(counter)),
                                    bold(str(maxcount)),
                                    os.path.basename(local_filepath),
                                    bold("invalid checksum"),
                            )
                        ),
                        importance = 0,
                        type = "info",
                        header = darkgreen(" * ")
                    )
                    return False
            else:
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s|%s|#%s|(%s/%s)] digest verification: %s: %s" % (
                                etpConst['officialrepositoryid'],
                                crippled_uri,
                                action,
                                tries,
                                blue(str(counter)),
                                bold(str(maxcount)),
                                os.path.basename(local_filepath),
                                bold("unknown data returned"),
                        )
                    ),
                    importance = 0,
                    type = "info",
                    header = darkgreen(" * ")
                )
                return False

        def go(self):

            broken_uris = set()
            fine_uris = set()
            errors = False
            action = 'upload'
            if self.download:
                action = 'download'

            for uri in self.uris:

                crippled_uri = self.Entropy.entropyTools.extractFTPHostFromUri(uri)
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s|%s] connecting to mirror..." % (etpConst['officialrepositoryid'],crippled_uri,action,)),
                    importance = 0,
                    type = "info",
                    header = darkgreen(" * "),
                    back = True
                )
                ftp = self.FtpInterface(uri, self.Entropy)
                self.Entropy.updateProgress(
                    red("[repo:%s|mirror:%s|%s] changing directory to %s..." % (etpConst['officialrepositoryid'],crippled_uri,bold(etpConst['etpurirelativepath']),action,)),
                    importance = 0,
                    type = "info",
                    header = darkgreen(" * "),
                    back = True
                )
                ftp.setCWD(self.ftp_basedir)

                maxcount = len(self.myfiles)
                counter = 0
                for mypath in self.myfiles:

                    syncer = ftp.uploadFile
                    myargs = [mypath]
                    if self.download:
                        syncer = ftp.downloadFile
                        myargs = [os.path.basename(mypath),self.local_basedir]

                    counter += 1
                    tries = 0
                    done = False
                    lastrc = None
                    while tries < 8:
                        tries += 1
                        self.Entropy.updateProgress(
                            red("[repo:%s|mirror:%s|%s|#%s|(%s/%s)] %sing: %s" % (
                                        etpConst['officialrepositoryid'],
                                        crippled_uri,
                                        action,
                                        tries,
                                        blue(str(counter)),
                                        bold(str(maxcount)),
                                        action,
                                        os.path.basename(mypath),
                                )
                            ),
                            importance = 0,
                            type = "info",
                            header = darkgreen(" * "),
                            back = True
                        )
                        rc = syncer(*myargs)
                        if rc and self.use_handlers and not self.download:
                            rc = self.handler_verify_upload(mypath, uri, ftp, counter, maxcount)
                        if rc:
                            self.Entropy.updateProgress(
                                red("[repo:%s|mirror:%s|%s|#%s|(%s/%s)] %s successfully: %s" % (
                                            etpConst['officialrepositoryid'],
                                            crippled_uri,
                                            action,
                                            tries,
                                            blue(str(counter)),
                                            bold(str(maxcount)),
                                            action,
                                            os.path.basename(mypath),
                                    )
                                ),
                                importance = 0,
                                type = "info",
                                header = darkgreen(" * ")
                            )
                            done = True
                            break
                        else:
                            self.Entropy.updateProgress(
                                red("[repo:%s|mirror:%s|%s|#%s|(%s/%s)] %s failed, retrying: %s" % (
                                            etpConst['officialrepositoryid'],
                                            crippled_uri,
                                            action,
                                            tries,
                                            blue(str(counter)),
                                            bold(str(maxcount)),
                                            action,
                                            os.path.basename(mypath),
                                    )
                                ),
                                importance = 0,
                                type = "warning",
                                header = brown(" * ")
                            )
                            lastrc = rc
                            continue

                    if not done:

                        # abort upload
                        self.Entropy.updateProgress(
                            red("[repo:%s|mirror:%s|%s|(%s/%s)] %s failed, giving up: %s - error: %s" % (
                                        etpConst['officialrepositoryid'],
                                        crippled_uri,
                                        action,
                                        blue(str(counter)),
                                        bold(str(maxcount)),
                                        action,
                                        os.path.basename(mypath),
                                        lastrc,
                                )
                            ),
                            importance = 1,
                            type = "error",
                            header = darkred(" !!! ")
                        )

                        if mypath not in self.critical_files:
                            self.Entropy.updateProgress(
                                red("[repo:%s|mirror:%s|%s|(%s/%s)] not critical: %s, continuing..." % (
                                            etpConst['officialrepositoryid'],
                                            crippled_uri,
                                            action,
                                            blue(str(counter)),
                                            bold(str(maxcount)),
                                            os.path.basename(mypath),
                                    )
                                ),
                                importance = 1,
                                type = "warning",
                                header = brown(" * ")
                            )
                            continue

                        ftp.closeConnection()
                        errors = True
                        broken_uris.add((uri,lastrc))
                        # next mirror
                        break

                # close connection
                ftp.closeConnection()
                fine_uris.add(uri)

            return errors,fine_uris,broken_uris

    def _show_eapi2_upload_messages(self, crippled_uri, database_path, upload_data, cmethod):

        self.Entropy.updateProgress(
            red("[repo:%s|mirror:%s|EAPI:2] creating compressed database dump + checksum" % (etpConst['officialrepositoryid'],crippled_uri,)),
            importance = 0,
            type = "info",
            header = darkgreen(" * ")
        )
        self.Entropy.updateProgress(
            blue("database path: %s" % (database_path,)),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            blue("dump: %s" % (upload_data['dump_path'],)),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            blue("dump checksum: %s" % (upload_data['dump_path_digest'],)),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            blue("opener: %s" % (cmethod[0],)),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

    def _show_eapi1_upload_messages(self, crippled_uri, database_path, upload_data, cmethod):

        self.Entropy.updateProgress(
            red("[repo:%s|mirror:%s|EAPI:1] compressing database + checksum" % (etpConst['officialrepositoryid'],crippled_uri,)),
            importance = 0,
            type = "info",
            header = darkgreen(" * "),
            back = True
        )
        self.Entropy.updateProgress(
            blue("database path: %s" % (database_path,)),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            blue("compressed database path: %s" % (upload_data['compressed_database_path'],)),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            blue("compressed checksum: %s" % (upload_data['compressed_database_path_digest'],)),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )
        self.Entropy.updateProgress(
            blue("opener: %s" % (cmethod[0],)),
            importance = 0,
            type = "info",
            header = brown("    # ")
        )

    def create_mirror_directories(self, ftp_connection, path_to_create):
        bdir = ""
        for mydir in path_to_create.split("/"):
            bdir += "/"+mydir
            if not ftp_connection.isFileAvailable(bdir):
                try:
                    ftp_connection.mkdir(bdir)
                except Exception, e:
                    error = str(e)
                    if (error.find("550") == -1) and (error.find("File exist") == -1):
                        raise exceptionTools.OnlineMirrorError("OnlineMirrorError: cannot create mirror directory %s, error: %s" % (bdir,e,))

    def mirror_lock_check(self, uri):

        gave_up = False
        crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
        ftp = self.FtpInterface(uri, self.Entropy)
        try:
            ftp.setCWD(etpConst['etpurirelativepath'])
        except:
            self.create_mirror_directories(ftp,etpConst['etpurirelativepath'])
            ftp.closeConnection()
            return gave_up # no errors, mirror is unlocked

        lock_file = self.get_database_lockfile()
        if not os.path.isfile(lock_file) and ftp.isFileAvailable(os.path.basename(lock_file)):
            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s|locking] mirror already locked, waiting up to 2 mins before giving up" % (
                                etpConst['officialrepositoryid'],
                                crippled_uri,
                        )
                ),
                importance = 1,
                type = "warning",
                header = brown(" * "),
                back = True
            )
            unlocked = False
            count = 0
            while count < 120:
                count += 1
                time.sleep(1)
                if not ftp.isFileAvailable(os.path.basename(lock_file)):
                    self.Entropy.updateProgress(
                        red("[repo:%s|mirror:%s|locking] mirror unlocked !" % (
                                etpConst['officialrepositoryid'],
                                crippled_uri,
                            )
                        ),
                        importance = 1,
                        type = "info",
                        header = darkgreen(" * ")
                    )
                    unlocked = True
                    break
            if not unlocked:
                gave_up = True

        ftp.closeConnection()
        return gave_up

    def upload_database(self, uris, lock_check = False, pretend = False):

        import gzip
        import bz2

        if etpConst['rss-feed']:
            self.update_rss_feed()

        upload_errors = False
        broken_uris = set()
        fine_uris = set()

        for uri in uris:

            cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
            if cmethod == None:
                raise exceptionTools.InvalidDataType("InvalidDataType: wrong database compression method passed.")

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
            database_path = etpConst['etpdatabasefilepath']
            upload_data, critical = self.get_files_to_sync(cmethod)

            if lock_check:
                given_up = self.mirror_lock_check(uri)
                if given_up:
                    upload_errors = True
                    broken_uris.add(uri)
                    continue

            self.lock_mirrors_for_download(True,[uri])

            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s|upload] preparing to upload database to mirror" % (etpConst['officialrepositoryid'],crippled_uri,)),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )

            # EAPI 2
            self._show_eapi2_upload_messages(crippled_uri, database_path, upload_data, cmethod)
            # create compressed dump + checksum
            self.dump_database_to_file(database_path, upload_data['dump_path'], eval(cmethod[0]))
            self.create_file_checksum(upload_data['dump_path'], upload_data['dump_path_digest'])


            # EAPI 1
            self._show_eapi1_upload_messages(crippled_uri, database_path, upload_data, cmethod)
            # compress the database
            self.compress_file(database_path, upload_data['compressed_database_path'], eval(cmethod[0]))
            self.create_file_checksum(database_path, upload_data['compressed_database_path_digest'])

            if not pretend:
                # upload
                uploader = self.FileTransmitter(self.FtpInterface, self.Entropy, [uri], upload_data, critical_files = critical)
                errors, m_fine_uris, m_broken_uris = uploader.go()
                if errors:
                    my_fine_uris = [self.entropyTools.extractFTPHostFromUri(x) for x in m_fine_uris]
                    my_fine_uris.sort()
                    my_broken_uris = [(self.entropyTools.extractFTPHostFromUri(x[0]),x[1]) for x in m_broken_uris]
                    my_broken_uris.sort()
                    self.Entropy.updateProgress(
                        red("[repo:%s|mirror:%s|errors] failed to upload to mirror, not unlocking and continuing" % (etpConst['officialrepositoryid'],crippled_uri,)),
                        importance = 0,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    # get reason
                    reason = my_broken_uris[0][1]
                    self.Entropy.updateProgress(
                        blue("reason: %s" % (reason,)),
                        importance = 0,
                        type = "error",
                        header = blue("    # ")
                    )
                    upload_errors = True
                    broken_uris |= m_broken_uris
                    continue

            # unlock
            self.lock_mirrors_for_download(False,[uri])
            fine_uris |= m_fine_uris

        if not fine_uris:
            upload_errors = True
        return upload_errors, broken_uris, fine_uris



    def download_database(self, uris, lock_check = False, pretend = False):

        import gzip
        import bz2

        download_errors = False
        broken_uris = set()
        fine_uris = set()

        for uri in uris:

            cmethod = etpConst['etpdatabasecompressclasses'].get(etpConst['etpdatabasefileformat'])
            if cmethod == None:
                raise exceptionTools.InvalidDataType("InvalidDataType: wrong database compression method passed.")

            crippled_uri = self.entropyTools.extractFTPHostFromUri(uri)
            database_path = etpConst['etpdatabasefilepath']
            database_dir_path = os.path.dirname(etpConst['etpdatabasefilepath'])
            download_data, critical = self.get_files_to_sync(cmethod, download = True)
            mytmpdir = self.Entropy.entropyTools.getRandomTempFile()
            os.makedirs(mytmpdir)

            self.Entropy.updateProgress(
                red("[repo:%s|mirror:%s|download] preparing to download database from mirror" % (etpConst['officialrepositoryid'],crippled_uri,)),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
            files_to_sync = download_data.keys()
            files_to_sync.sort()
            for myfile in files_to_sync:
                self.Entropy.updateProgress(
                    blue("download path: %s" % (myfile,)),
                    importance = 0,
                    type = "info",
                    header = brown("    # ")
                )

            if lock_check:
                given_up = self.mirror_lock_check(uri)
                if given_up:
                    download_errors = True
                    broken_uris.add(uri)
                    continue

            # avoid having others messing while we're downloading
            self.lock_mirrors(True,[uri])

            if not pretend:
                # download
                downloader = self.FileTransmitter(self.FtpInterface, self.Entropy, [uri], download_data, download = True, local_basedir = mytmpdir, critical_files = critical)
                errors, m_fine_uris, m_broken_uris = downloader.go()
                if errors:
                    my_fine_uris = [self.entropyTools.extractFTPHostFromUri(x) for x in m_fine_uris]
                    my_fine_uris.sort()
                    my_broken_uris = [(self.entropyTools.extractFTPHostFromUri(x[0]),x[1]) for x in m_broken_uris]
                    my_broken_uris.sort()
                    self.Entropy.updateProgress(
                        red("[repo:%s|mirror:%s|errors] failed to download from mirror" % (etpConst['officialrepositoryid'],crippled_uri,)),
                        importance = 0,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    # get reason
                    reason = my_broken_uris[0][1]
                    self.Entropy.updateProgress(
                        blue("reason: %s" % (reason,)),
                        importance = 0,
                        type = "error",
                        header = blue("    # ")
                    )
                    download_errors = True
                    broken_uris |= m_broken_uris
                    self.lock_mirrors(False,[uri])
                    continue

                # all fine then, we need to move data from mytmpdir to database_dir_path

                # EAPI 1
                # unpack database
                compressed_db_filename = os.path.basename(download_data['compressed_database_path'])
                uncompressed_db_filename = os.path.basename(database_path)
                compressed_file = os.path.join(mytmpdir,compressed_db_filename)
                uncompressed_file = os.path.join(mytmpdir,uncompressed_db_filename)
                self.uncompress_file(compressed_file, uncompressed_file, eval(cmethod[0]))
                # now move
                for myfile in os.listdir(mytmpdir):
                    fromfile = os.path.join(mytmpdir,myfile)
                    tofile = os.path.join(database_dir_path,myfile)
                    shutil.move(fromfile,tofile)
                    self.Entropy.ClientService.setup_default_file_perms(tofile)

            if os.path.isdir(mytmpdir):
                shutil.rmtree(mytmpdir)
            if os.path.isdir(mytmpdir):
                os.rmdir(mytmpdir)


            fine_uris.add(uri)
            self.lock_mirrors(False,[uri])

        return download_errors, fine_uris, broken_uris

    def calculate_database_sync_queues(self):
        remote_status =  self.get_remote_databases_status()
        local_revision = self.Entropy.get_local_database_revision()
        upload_queue = []
        download_latest = ()

        # all mirrors are empty ? I rule
        if not [x for x in remote_status if x[1]]:
            upload_queue = remote_status[:]
        else:
            highest_remote_revision = max([x[1] for x in remote_status])

            if local_revision < highest_remote_revision:
                for x in remote_status:
                    if x[1] == highest_remote_revision:
                        download_latest = x
                        break

            if download_latest:
                upload_queue = [x for x in remote_status if (x[1] < highest_remote_revision)]
            else:
                upload_queue = [x for x in remote_status if (x[1] < local_revision)]

        return download_latest, upload_queue

    def sync_databases(self, no_upload = False, unlock_mirrors = False):

        db_locked = False
        if self.is_local_database_locked():
            db_locked = True

        lock_data = self.get_mirrors_lock()
        mirrors_locked = [x for x in lock_data if x[1]]

        if not mirrors_locked and db_locked:
            raise exceptionTools.OnlineMirrorError("OnlineMirrorError: Mirrors are not locked remotely but the local database is. It is a non-sense. Please remove the lock file %s" % (self.get_database_lockfile(),) )

        if mirrors_locked and not db_locked:
            raise exceptionTools.OnlineMirrorError("OnlineMirrorError: At the moment, mirrors are locked, someone is working on their databases, try again later...")

        download_latest, upload_queue = self.calculate_database_sync_queues()

        if not download_latest and not upload_queue:
            self.Entropy.updateProgress(
                red("[repo:%s|sync] database already in sync" % (etpConst['officialrepositoryid'],)),
                importance = 1,
                type = "info",
                header = darkgreen(" * ")
            )
            return 0, set(), set()

        if download_latest:
            download_uri = download_latest[0]
            download_errors, fine_uris, broken_uris = self.download_database(download_uri)
            if download_errors:
                self.Entropy.updateProgress(
                    red("[repo:%s|sync] database sync failed: download issues" % (etpConst['officialrepositoryid'],)),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                return 1,fine_uris,broken_uris
            # XXX: reload revision settings?

        if upload_queue and not no_upload:

            uris = [x[0] for x in upload_queue]
            errors, fine_uris, broken_uris = self.upload_database(uris)
            if errors:
                self.Entropy.updateProgress(
                    red("[repo:%s|sync] database sync failed: upload issues" % (etpConst['officialrepositoryid'],)),
                    importance = 1,
                    type = "error",
                    header = darkred(" !!! ")
                )
                return 2,fine_uris,broken_uris


        self.Entropy.updateProgress(
            red("[repo:%s|sync] database sync completed successfully" % (etpConst['officialrepositoryid'],)),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )

        if unlock_mirrors:
            self.lock_mirrors(False)
        return 0, set(), set()





    def calculate_local_upload_files(self, branch):
        upload_files = 0
        upload_packages = set()
        upload_dir = os.path.join(etpConst['packagesserveruploaddir'],branch)

        for package in os.listdir(upload_dir):
            if package.endswith(etpConst['packagesext']) or package.endswith(etpConst['packageshashfileext']):
                upload_packages.add(package)
                if package.endswith(etpConst['packagesext']):
                    upload_files += 1

        return upload_files, upload_packages

    def calculate_local_package_files(self, branch):
        local_files = 0
        local_packages = set()
        packages_dir = os.path.join(etpConst['packagesserverbindir'],branch)

        for package in os.listdir(packages_dir):
            if package.endswith(etpConst['packagesext']) or package.endswith(etpConst['packageshashfileext']):
                local_packages.add(package)
                if package.endswith(etpConst['packagesext']):
                    local_files += 1

        return local_files, local_packages


    def _show_local_sync_stats(self, crippled_uri, branch, upload_files, local_files):
        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s|mirror:%s] local statistics:" % (
                    etpConst['officialrepositoryid'],
                    branch,
                    crippled_uri,
                )
            ),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )
        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s] upload directory: %s files ready" % (
                    etpConst['officialrepositoryid'],
                    branch,
                    upload_files,
                )
            ),
            importance = 0,
            type = "info",
            header = darkgreen(" * ")
        )
        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s] packages directory: %s files ready" % (
                    etpConst['officialrepositoryid'],
                    branch,
                    local_files,
                )
            ),
            importance = 0,
            type = "info",
            header = darkgreen(" * ")
        )

    def _show_sync_queues(self, upload, download, removal, copy, metainfo, branch):

        # show stats
        for itemdata in upload:
            package = darkgreen(os.path.basename(itemdata[0]))
            size = blue(self.Entropy.entropyTools.bytesIntoHuman(itemdata[1]))
            self.Entropy.updateProgress(
                red("[repo:%s|sync|branch:%s|%s] %s [%s]" % (
                        etpConst['officialrepositoryid'],
                        branch,bold("upload"),
                        package,
                        size,
                    )
                ),
                importance = 0,
                type = "info",
                header = bold("    # ")
            )
        for itemdata in download:
            package = darkred(os.path.basename(itemdata[0]))
            size = blue(self.Entropy.entropyTools.bytesIntoHuman(itemdata[1]))
            self.Entropy.updateProgress(
                red("[repo:%s|sync|branch:%s|%s] %s [%s]" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        brown("download"),
                        package,
                        size,
                    )
                ),
                importance = 0,
                type = "info",
                header = darkred("    # ")
            )
        for itemdata in copy:
            package = darkblue(os.path.basename(itemdata[0]))
            size = blue(self.Entropy.entropyTools.bytesIntoHuman(itemdata[1]))
            self.Entropy.updateProgress(
                red("[repo:%s|sync|branch:%s|%s] %s [%s]" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        darkgreen("copy"),
                        package,
                        size,
                    )
                ),
                importance = 0,
                type = "info",
                header = darkgreen("    # ")
            )
        for itemdata in removal:
            package = brown(os.path.basename(itemdata[0]))
            size = blue(self.Entropy.entropyTools.bytesIntoHuman(itemdata[1]))
            self.Entropy.updateProgress(
                red("[repo:%s|sync|branch:%s|%s] %s [%s]" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        darkred("remove"),
                        package,
                        size,
                    )
                ),
                importance = 0,
                type = "info",
                header = brown("    # ")
            )

        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s] %s: %s" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        blue("packages to be removed"),
                        len(removal),
                )
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )
        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s] %s: %s" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        darkgreen("packages to be moved locally"),
                        len(copy),
                )
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )
        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s] %s: %s" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        bold("packages to be uploaded"),
                        len(upload),
                )
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )

        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s] %s: %s" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        blue("total removal size"),
                        self.Entropy.entropyTools.bytesIntoHuman(metainfo['removal']),
                )
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )

        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s] %s: %s" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        bold("total upload size"),
                        self.Entropy.entropyTools.bytesIntoHuman(metainfo['upload']),
                )
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )
        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s] %s: %s" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        darkred("total download size"),
                        self.Entropy.entropyTools.bytesIntoHuman(metainfo['download']),
                )
            ),
            importance = 0,
            type = "info",
            header = blue(" @@ ")
        )


    def calculate_remote_package_files(self, uri, branch, ftp_connection = None):

        remote_files = 0
        close_conn = False
        remote_packages_data = {}

        def do_cwd():
            try:
                ftp_connection.setCWD(etpConst['binaryurirelativepath'])
            except:
                self.create_mirror_directories(ftp_connection,etpConst['etpurirelativepath'])
                ftp_connection.setCWD(etpConst['binaryurirelativepath'])
            if not ftp_connection.isFileAvailable(branch):
                ftp_connection.mkdir(branch)
            ftp_connection.setCWD(branch)

        if ftp_connection == None:
            close_conn = True
            ftp_connection = self.FtpInterface(uri, self.Entropy)
        do_cwd()

        remote_packages = ftp_connection.listDir()
        remote_packages_info = ftp_connection.getRoughList()
        if close_conn:
            ftp_connection.closeConnection()

        for tbz2 in remote_packages:
            if tbz2.endswith(etpConst['packagesext']):
                remote_files += 1

        for remote_package in remote_packages_info:
            remote_packages_data[remote_package.split()[8]] = int(remote_package.split()[4])

        return remote_files, remote_packages, remote_packages_data

    def calculate_packages_to_sync(self, uri, branch):

        crippled_uri = self.Entropy.entropyTools.extractFTPHostFromUri(uri)
        upload_files, upload_packages = self.calculate_local_upload_files(branch)
        local_files, local_packages = self.calculate_local_package_files(branch)
        self._show_local_sync_stats(crippled_uri, branch, upload_files, local_files)

        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s|mirror:%s] remote statistics:" % (etpConst['officialrepositoryid'],branch,crippled_uri,)),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )
        remote_files, remote_packages, remote_packages_data = self.calculate_remote_package_files(uri, branch)
        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s|mirror:%s] remote packages: %s files stored" % (etpConst['officialrepositoryid'],branch,crippled_uri,remote_files,)),
            importance = 0,
            type = "info",
            header = darkgreen(" * ")
        )

        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s|mirror:%s] calculating queues..." % (etpConst['officialrepositoryid'],branch,crippled_uri,)),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )

        return self.calculate_sync_queues(
                    upload_packages,
                    local_packages,
                    remote_packages,
                    remote_packages_data,
                    branch
        ),remote_packages_data

    def calculate_sync_queues(self, upload_packages, local_packages, remote_packages, remote_packages_data, branch):

        uploadQueue = set()
        downloadQueue = set()
        removalQueue = set()
        fineQueue = set()

        for local_package in upload_packages:
            if local_package in remote_packages:
                local_filepath = os.path.join(etpConst['packagesserveruploaddir'],branch,local_package)
                local_size = int(os.stat(local_filepath)[6])
                remote_size = remote_packages_data.get(local_package)
                if remote_size == None:
                    remote_size = 0
                if (local_size != remote_size):
                    # size does not match, adding to the upload queue
                    uploadQueue.add(local_package)
                else:
                    fineQueue.add(local_package) # just move from upload to packages
            else:
                # always force upload of packages in uploaddir
                uploadQueue.add(local_package)

        # if a package is in the packages directory but not online, we have to upload it
        # we have local_packages and remotePackages
        for local_package in local_packages:
            if local_package in remote_packages:
                local_filepath = os.path.join(etpConst['packagesserverbindir'],branch,local_package)
                local_size = int(os.stat(local_filepath)[6])
                remote_size = remote_packages_data.get(local_package)
                if remote_size == None:
                    remote_size = 0
                if (local_size != remote_size) and (local_size != 0):
                    # size does not match, adding to the upload queue
                    if local_package not in fineQueue:
                        uploadQueue.add(local_package)
            else:
                # this means that the local package does not exist
                # so, we need to download it
                uploadQueue.add(local_package)

        # Fill downloadQueue and removalQueue
        for remote_package in remote_packages:
            if remote_package in local_packages:
                local_filepath = os.path.join(etpConst['packagesserverbindir'],branch,remote_package)
                local_size = int(os.stat(local_filepath)[6])
                remote_size = remote_packages_data.get(remote_package)
                if remote_size == None:
                    remote_size = 0
                if (local_size != remote_size) and (local_size != 0):
                    # size does not match, remove first
                    #print "removal of "+localPackage+" because its size differ"
                    if remote_package not in uploadQueue: # do it only if the package has not been added to the uploadQueue
                        removalQueue.add(remote_package) # remotePackage == localPackage # just remove something that differs from the content of the mirror
                        # then add to the download queue
                        downloadQueue.add(remote_package)
            else:
                # this means that the local package does not exist
                # so, we need to download it
                if not remote_package.endswith(".tmp"): # ignore .tmp files
                    downloadQueue.add(remote_package)

        # Collect packages that don't exist anymore in the database
        # so we can filter them out from the download queue
        dbconn = self.Entropy.openServerDatabase(just_reading = True)
        db_files = dbconn.listBranchPackagesTbz2(branch)

        exclude = set()
        for myfile in downloadQueue:
            if myfile.endswith(etpConst['packagesext']):
                if myfile not in db_files:
                    exclude.add(myfile)
        downloadQueue -= exclude

        exclude = set()
        for myfile in uploadQueue:
            if myfile.endswith(etpConst['packagesext']):
                if myfile not in db_files:
                    exclude.add(myfile)
        uploadQueue -= exclude

        exclude = set()
        for myfile in downloadQueue:
            if myfile in uploadQueue:
                exclude.add(myfile)
        downloadQueue -= exclude

        return uploadQueue, downloadQueue, removalQueue, fineQueue


    def expand_queues(self, uploadQueue, downloadQueue, removalQueue, remote_packages_data, branch):

        metainfo = {
            'removal': 0,
            'download': 0,
            'upload': 0,
        }
        removal = []
        download = []
        copy = []
        upload = []

        for item in removalQueue:
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(etpConst['packagesserverbindir'],branch,item)
            size = int(os.stat(local_filepath)[6])
            metainfo['removal'] += size
            removal.append((local_filepath,size))

        for item in downloadQueue:
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(etpConst['packagesserveruploaddir'],branch,item)
            if not os.path.isfile(local_filepath):
                size = remote_packages_data.get(item)
                if size == None:
                    size = 0
                size = int(size)
                metainfo['removal'] += size
                download.append((local_filepath,size))
            else:
                size = int(os.stat(local_filepath)[6])
                copy.append((local_filepath,size))

        for item in uploadQueue:
            if not item.endswith(etpConst['packagesext']):
                continue
            local_filepath = os.path.join(etpConst['packagesserveruploaddir'],branch,item)
            local_filepath_pkgs = os.path.join(etpConst['packagesserverbindir'],branch,item)
            if os.path.isfile(local_filepath):
                size = int(os.stat(local_filepath)[6])
                upload.append((local_filepath,size))
            else:
                size = int(os.stat(local_filepath_pkgs)[6])
                upload.append((local_filepath_pkgs,size))
            metainfo['upload'] += size


        return upload, download, removal, copy, metainfo


    def _sync_run_removal_queue(self, removal_queue, branch):

        for itemdata in removal_queue:

            remove_filename = itemdata[0]
            remove_filepath = os.path.join(etpConst['packagesserverbindir'],branch,remove_filename)
            remove_filepath_hash = remove_filepath+etpConst['packageshashfileext']
            self.Entropy.updateProgress(
                red("[repo:%s|sync|branch:%s] removing package+hash: %s [%s]" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        remove_filename,
                        self.Entropy.entropyTools.bytesIntoHuman(itemdata[1]),
                    )
                ),
                importance = 0,
                type = "info",
                header = darkred(" * ")
            )

            if os.path.isfile(remove_filepath):
                os.remove(remove_filepath)
            if os.path.isfile(remove_filepath_hash):
                os.remove(remove_filepath_hash)

        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s] removal complete" % (
                    etpConst['officialrepositoryid'],
                    branch,
                )
            ),
            importance = 0,
            type = "info",
            header = darkred(" * ")
        )


    def _sync_run_copy_queue(self, copy_queue, branch):

        for itemdata in copy_queue:

            from_file = itemdata[0]
            from_file_hash = from_file+etpConst['packageshashfileext']
            to_file = os.path.join(etpConst['packagesserverbindir'],branch,os.path.basename(from_file))
            to_file_hash = to_file+etpConst['packageshashfileext']
            expiration_file = to_file+etpConst['packagesexpirationfileext']
            self.Entropy.updateProgress(
                red("[repo:%s|sync|branch:%s] copying file+hash to repository: %s" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        from_file,
                    )
                ),
                importance = 0,
                type = "info",
                header = darkred(" * ")
            )

            if not os.path.isdir(os.path.dirname(to_file)):
                os.makedirs(os.path.dirname(to_file))

            shutil.copy2(from_file,to_file)
            if not os.path.isfile(from_file_hash):
                self.create_file_checksum(from_file, from_file_hash)
            shutil.copy2(from_file_hash,to_file_hash)

            # clear expiration file
            if os.path.isfile(expiration_file):
                os.remove(expiration_file)


    def _sync_run_upload_queue(self, uri, upload_queue, branch):

        crippled_uri = self.Entropy.entropyTools.extractFTPHostFromUri(uri)
        myqueue = [x[0] for x in upload_queue]
        for itemdata in upload_queue:
            x = itemdata[0]
            hash_file = x+etpConst['packageshashfileext']
            if not os.path.isfile(hash_file):
                self.Entropy.entropyTools.createHashFile(x)
            myqueue.append(hash_file)
            myqueue.append(x)

        ftp_basedir = os.path.join(etpConst['binaryurirelativepath'],branch)
        uploader = self.FileTransmitter(    self.FtpInterface,
                                            self.Entropy,
                                            [uri],
                                            myqueue,
                                            critical_files = myqueue,
                                            use_handlers = True,
                                            ftp_basedir = ftp_basedir,
                                            handlers_data = {'branch': branch }
                                        )
        errors, m_fine_uris, m_broken_uris = uploader.go()
        if errors:
            my_broken_uris = [(self.Entropy.entropyTools.extractFTPHostFromUri(x[0]),x[1]) for x in m_broken_uris]
            reason = my_broken_uris[0][1]
            self.Entropy.updateProgress(
                red("[repo:%s|sync|branch:%s] upload errors: %s, reason: %s" % (
                            etpConst['officialrepositoryid'],
                            branch,
                            crippled_uri,
                            reason,
                    )
                ),
                importance = 1,
                type = "error",
                header = darkred(" !!! ")
            )
            return errors, m_fine_uris, m_broken_uris

        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s] upload completed successfully: %s" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        crippled_uri,
                )
            ),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )
        return errors, m_fine_uris, m_broken_uris


    def _sync_run_download_queue(self, uri, download_queue, branch):

        crippled_uri = self.Entropy.entropyTools.extractFTPHostFromUri(uri)
        myqueue = [x[0] for x in download_queue]
        for itemdata in download_queue:
            x = itemdata[0]
            hash_file = x+etpConst['packageshashfileext']
            myqueue.append(x)
            myqueue.append(hash_file)

        ftp_basedir = os.path.join(etpConst['binaryurirelativepath'],branch)
        local_basedir = os.path.join(etpConst['packagesserverbindir'],branch)
        downloader = self.FileTransmitter(    self.FtpInterface,
                                            self.Entropy,
                                            [uri],
                                            myqueue,
                                            critical_files = myqueue,
                                            use_handlers = True,
                                            ftp_basedir = ftp_basedir,
                                            local_basedir = local_basedir,
                                            handlers_data = {'branch': branch },
                                            download = True
                                        )
        errors, m_fine_uris, m_broken_uris = downloader.go()
        if errors:
            my_broken_uris = [(self.Entropy.entropyTools.extractFTPHostFromUri(x[0]),x[1]) for x in m_broken_uris]
            reason = my_broken_uris[0][1]
            self.Entropy.updateProgress(
                red("[repo:%s|sync|branch:%s] download errors: %s, reason: %s" % (
                            etpConst['officialrepositoryid'],
                            branch,
                            crippled_uri,
                            reason,
                    )
                ),
                importance = 1,
                type = "error",
                header = darkred(" !!! ")
            )
            return errors, m_fine_uris, m_broken_uris

        self.Entropy.updateProgress(
            red("[repo:%s|sync|branch:%s] download completed successfully: %s" % (
                        etpConst['officialrepositoryid'],
                        branch,
                        crippled_uri,
                )
            ),
            importance = 1,
            type = "info",
            header = darkgreen(" * ")
        )
        return errors, m_fine_uris, m_broken_uris


    def sync_packages(self, ask = True, pretend = False, packages_check = False):

        self.Entropy.updateProgress(
            red("[repo:%s|sync] starting packages sync" % (etpConst['officialrepositoryid'],)),
            importance = 1,
            type = "info",
            header = darkgreen(" * "),
            back = True
        )

        pkgbranches = list(self.Entropy.list_all_branches())
        successfull_mirrors = set()
        broken_mirrors = set()
        check_data = ()
        mirrors_tainted = False
        mirror_errors = False
        mirrors_errors = False

        for uri in etpConst['activatoruploaduris']:

            crippled_uri = self.Entropy.entropyTools.extractFTPHostFromUri(uri)
            mirror_errors = False

            for mybranch in pkgbranches:

                self.Entropy.updateProgress(
                    red("[repo:%s|sync|branch:%s] packages sync: %s" % (
                            etpConst['officialrepositoryid'],
                            mybranch,
                            crippled_uri,
                        )
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )

                uploadQueue, downloadQueue, removalQueue, fineQueue, remote_packages_data = self.calculate_packages_to_sync(uri, mybranch)
                del fineQueue

                if (not uploadQueue) and (not downloadQueue) and (not removalQueue):
                    self.Entropy.updateProgress(
                        red("[repo:%s|sync|branch:%s] nothing to do on: %s" % (
                                    etpConst['officialrepositoryid'],
                                    mybranch,
                                    crippled_uri,
                            )
                        ),
                        importance = 1,
                        type = "info",
                        header = darkgreen(" * ")
                    )
                    if pkgbranches[-1] == mybranch:
                        successfull_mirrors.add(uri)
                    continue

                self.Entropy.updateProgress(
                    red("[repo:%s|sync|branch:%s] calculating queue metadata:" % (
                                etpConst['officialrepositoryid'],
                                mybranch,
                        )
                    ),
                    importance = 1,
                    type = "info",
                    header = darkgreen(" * ")
                )

                upload, download, removal, copy, metainfo = self.expand_queues(
                            uploadQueue,
                            downloadQueue,
                            removalQueue,
                            remote_packages_data,
                            mybranch
                )
                del uploadQueue, downloadQueue, removalQueue, remote_packages_data
                self._show_sync_queues(upload, download, removal, copy, metainfo, mybranch)

                if not len(upload)+len(download)+len(removal)+len(copy):

                    self.Entropy.updateProgress(
                        red("[repo:%s|sync|branch:%s] nothing to sync for %s" % (
                                    etpConst['officialrepositoryid'],
                                    mybranch,
                                    crippled_uri,
                            )
                        ),
                        importance = 1,
                        type = "info",
                        header = darkgreen(" * ")
                    )

                    if pkgbranches[-1] == mybranch:
                        successfull_mirrors.add(uri)
                    continue

                if pretend:
                    if pkgbranches[-1] == mybranch:
                        successfull_mirrors.add(uri)
                    continue

                if ask:
                    rc = self.Entropy.askQuestion("Would you like to run the steps above ?")
                    if rc == "No":
                        continue

                try:

                    if removal:
                        self._sync_run_removal_queue(removal, mybranch)
                    if copy:
                        self._sync_run_copy_queue(copy, mybranch)
                    if upload or download:
                        mirrors_tainted = True
                    if upload:
                        d_errors, m_fine_uris, m_broken_uris = self._sync_run_upload_queue(uri, upload, mybranch)
                        if d_errors: mirror_errors = True
                    if download:
                        d_errors, m_fine_uris, m_broken_uris = self._sync_run_download_queue(uri, download, mybranch)
                        if d_errors: mirror_errors = True
                    if (pkgbranches[-1] == mybranch) and not mirror_errors:
                        successfull_mirrors.add(uri)
                    if mirror_errors:
                        mirrors_errors = True

                except KeyboardInterrupt:
                    self.Entropy.updateProgress(
                        red("[repo:%s|sync|branch:%s] keyboard interrupt !" % (etpConst['officialrepositoryid'],mybranch,)),
                        importance = 1,
                        type = "info",
                        header = darkgreen(" * ")
                    )
                    return mirrors_tainted, mirrors_errors, successfull_mirrors, broken_mirrors, check_data

                except Exception, e:
                    mirrors_errors = True
                    broken_mirrors.add(uri)
                    self.Entropy.updateProgress(
                        red("[repo:%s|sync|branch:%s] exception caught: %s, error: %s" % (
                                    etpConst['officialrepositoryid'],
                                    mybranch,
                                    Exception,
                                    e,
                            )
                        ),
                        importance = 1,
                        type = "error",
                        header = darkred(" !!! ")
                    )
                    if len(successfull_mirrors) > 0:
                        self.Entropy.updateProgress(
                            red("[repo:%s|sync|branch:%s] at least one mirror has been sync'd properly, hooray!" % (
                                        etpConst['officialrepositoryid'],
                                        mybranch,
                                )
                            ),
                            importance = 1,
                            type = "error",
                            header = darkred(" !!! ")
                        )
                    continue

        # if at least one server has been synced successfully, move files
        if (len(successfull_mirrors) > 0) and not pretend:
            for branch in pkgbranches:
                branch_dir = os.path.join(etpConst['packagesserveruploaddir'],branch)
                branchcontent = os.listdir(branch_dir)
                for xfile in branchcontent:
                    source = os.path.join(etpConst['packagesserveruploaddir'],branch,xfile)
                    destdir = os.path.join(etpConst['packagesserverbindir'],branch)
                    if not os.path.isdir(destdir):
                        os.makedirs(destdir)
                    dest = os.path.join(destdir,xfile)
                    shutil.move(source,dest)
                    # clear expiration file
                    dest_expiration = dest+etpConst['packagesexpirationfileext']
                    if os.path.isfile(dest_expiration):
                        os.remove(dest_expiration)

        if packages_check:
            check_data = self.Entropy.verify_local_packages([], ask = ask)

        return mirrors_tainted, mirrors_errors, successfull_mirrors, broken_mirrors, check_data


