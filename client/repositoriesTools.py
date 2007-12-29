#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo repositories handling library

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
import entropyTools
import exceptionTools

def repositories(options):

    # Options available for all the packages submodules
    myopts = options[1:]
    equoRequestForceUpdate = False
    rc = 0
    for opt in myopts:
        if (opt == "--force"):
            equoRequestForceUpdate = True

    if (options[0] == "update"):
        rc = syncRepositories(forceUpdate = equoRequestForceUpdate)
    elif (options[0] == "status"):
        for repo in etpRepositories:
            showRepositoryInfo(repo)
    elif (options[0] == "repoinfo"):
        showRepositories()
    else:
        rc = -10
    return rc

# this function shows a list of enabled repositories
def showRepositories():
    print_info(darkred(" * ")+darkgreen("Active Repositories:"))
    repoNumber = 0
    for repo in etpRepositories:
        repoNumber += 1
        print_info(blue("\t#"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
        sourcecount = 0
        for pkgrepo in etpRepositories[repo]['packages']:
            sourcecount += 1
            print_info(red("\t\tPackages Mirror #"+str(sourcecount)+" : ")+darkgreen(pkgrepo))
        print_info(red("\t\tDatabase URL: ")+darkgreen(etpRepositories[repo]['database']))
        print_info(red("\t\tRepository name: ")+bold(repo))
        print_info(red("\t\tRepository database path: ")+blue(etpRepositories[repo]['dbpath']))
    return 0

def showRepositoryInfo(reponame):
    repoNumber = 0
    for repo in etpRepositories:
        repoNumber += 1
        if repo == reponame:
            break
    print_info(blue("#"+str(repoNumber))+bold(" "+etpRepositories[reponame]['description']))
    if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasefile']):
        status = "active"
    else:
        status = "never synced"
    print_info(darkgreen("\tStatus: ")+darkred(status))
    urlcount = 0
    for repourl in etpRepositories[reponame]['packages'][::-1]:
        urlcount += 1
        print_info(red("\tPackages URL #"+str(urlcount)+": ")+darkgreen(repourl))
    print_info(red("\tDatabase URL: ")+darkgreen(etpRepositories[reponame]['database']))
    print_info(red("\tRepository name: ")+bold(reponame))
    print_info(red("\tRepository database path: ")+blue(etpRepositories[reponame]['dbpath']))
    revision = getRepositoryRevision(reponame)
    mhash = getRepositoryDbFileHash(reponame)

    print_info(red("\tRepository database checksum: ")+mhash)
    print_info(red("\tRepository revision: ")+darkgreen(str(revision)))
    return 0

# @returns -1 if the file does not exist
# @returns int>0 if the file exists
def getRepositoryRevision(reponame):
    if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabaserevisionfile']):
        f = open(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'],"r")
        revision = int(f.readline().strip())
        f.close()
    else:
        revision = -1
    return revision

# @returns -1 if the file does not exist
# @returns int>0 if the file exists
def getRepositoryDbFileHash(reponame):
    if os.path.isfile(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasehashfile']):
        f = open(etpRepositories[reponame]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
        mhash = f.readline().strip().split()[0]
        f.close()
    else:
        mhash = "-1"
    return mhash

def syncRepositories(reponames = [], forceUpdate = False):

    # load repository class
    try:
        repoConn = repositoryController(reponames, forceUpdate)
    except exceptionTools.PermissionDenied:
        print_error(red("\t You must run this application as root."))
        return 1
    except exceptionTools.MissingParameter:
        print_error(darkred(" * ")+red("No repositories specified in ")+etpConst['repositoriesconf'])
        return 127
    except exceptionTools.OnlineMirrorError:
        print_error(darkred(" @@ ")+darkgreen("You are not connected to the Internet. You should."))
        return 126
    except Exception, e:
        print_error(darkred(" @@ ")+darkgreen("Unhandled exception: %s" % (str(e),)))
        return 2

    # let's dance!
    if (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("Repositories syncronization..."))

    repoNumber = 0
    for repo in repoConn.reponames:

        repoNumber += 1

        if (not etpUi['quiet']):
            print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))
            print_info(red("\tDatabase URL: ")+darkgreen(etpRepositories[repo]['database']))
            print_info(red("\tDatabase local path: ")+darkgreen(etpRepositories[repo]['dbpath']))

        # check if database is already updated to the latest revision
        update = repoConn.isRepositoryUpdatable(repo)
        if not update:
            if not etpUi['quiet']: print_info(bold("\tAttention: ")+red("database is already up to date."))
            continue

        # get database lock
        unlocked = repoConn.isRepositoryUnlocked(repo)
        if not unlocked:
            if not etpUi['quiet']: print_error(bold("\tATTENTION -> ")+red("repository is being updated. Try again in a few minutes."))
            continue

        # database is going to be updated
        repoConn.dbupdated = True
        # clear database interface cache belonging to this repository
        repoConn.clearRepositoryCache(repo)
        cmethod = repoConn.validateCompressionMethod(repo)
        repoConn.ensureRepositoryPath(repo)

        # starting to download
        if (not etpUi['quiet']):
            print_info(red("\tDownloading database ")+darkgreen(etpConst[cmethod[2]])+red(" ..."))

        down_status = repoConn.downloadItem("db", repo, cmethod)
        if not down_status:
            print_info(bold("\tAttention: ")+red("database does not exist online."))
            continue

        # unpack database
        if (not etpUi['quiet']):
            print_info(red("\tUnpacking database to ")+darkgreen(etpConst['etpdatabasefile'])+red(" ..."))
        # unpack database
        repoConn.unpackDownloadedDatabase(repo, cmethod)

        # download checksum
        if (not etpUi['quiet']):
            print_info(red("\tDownloading checksum ")+darkgreen(etpConst['etpdatabasehashfile'])+red(" ..."))
        down_status = repoConn.downloadItem("ck", repo)
        if not down_status:
            print_warning(red("\tCannot fetch checksum. Cannot verify database integrity !"))
        else:
            # verify checksum
            if (not etpUi['quiet']):
                print_info(red("\tChecking downloaded database ")+darkgreen(etpConst['etpdatabasefile'])+red(" ..."), back = True)
            db_status = repoConn.verifyDatabaseChecksum(repo)
            if db_status == -1:
                print_warning(red("\tCannot open digest. Cannot verify database integrity !"))
            elif db_status:
                if (not etpUi['quiet']):
                    print_info(red("\tDownloaded database status: ")+bold("OK"))
            else:
                if (not etpUi['quiet']):
                    print_error(red("\tDownloaded database status: ")+darkred("ERROR"))
                    print_error(red("\t An error occured while checking database integrity"))
                # delete all
                repoConn.removeRepositoryFiles(repo, cmethod[2])
                repoConn.syncErrors = True
                continue

        # download revision
        if (not etpUi['quiet']):
            print_info(red("\tDownloading revision ")+darkgreen(etpConst['etpdatabaserevisionfile'])+red(" ..."))
        rev_status = repoConn.downloadItem("rev", repo)
        if not rev_status:
            print_warning(red("\tCannot download repository revision, don't ask me why !"))
        else:
            if not etpUi['quiet']: print_info(red("\tUpdated repository revision: ")+bold(str(getRepositoryRevision(repo))))

        print_info(darkgreen("\tUpdate completed"))

    repoConn.closeTransactions()

    if repoConn.syncErrors:
        if (not etpUi['quiet']):
            print_warning(darkred(" @@ ")+red("Something bad happened. Please have a look."))
        del repoConn
        return 128

    # tell if a new equo release is available
    import equoTools
    from databaseTools import openClientDatabase
    try:
        clientDbconn = openClientDatabase(xcache = False)
    except exceptionTools.SystemDatabaseError:
        del repoConn
        return 0

    matches = clientDbconn.searchPackages("app-admin/equo")
    if matches:
        equo_match = "<="+matches[0][0]
        equo_unsatisfied,x = equoTools.filterSatisfiedDependencies([equo_match])
        del x
        if equo_unsatisfied:
            print_warning(darkred(" !! ")+blue("A new version of ")+bold("equo")+blue(" is available. Please ")+bold("install it")+blue(" before any other package."))
        del matches
        del equo_unsatisfied

    clientDbconn.closeDB()
    del clientDbconn
    del repoConn

    return 0

#
# repository control class, that's it
#
class repositoryController:

    def __init__(self, reponames = [], forceUpdate = False):

        self.reponames = reponames
        self.forceUpdate = forceUpdate
        self.syncErrors = False
        self.dbupdated = False

        import remoteTools
        import dumpTools
        self.remoteTools = remoteTools
        self.dumpTools = dumpTools

        # check if I am root
        if (not entropyTools.isRoot()):
            raise exceptionTools.PermissionDenied("PermissionDenied: not allowed as user.")

        # check etpRepositories
        if not etpRepositories:
            raise exceptionTools.MissingParameter("MissingParameter: no repositories specified in %s" % (etpConst['repositoriesconf'],))

        # Test network connectivity
        conntest = self.remoteTools.getOnlineContent("http://svn.sabayonlinux.org")
        if not conntest:
            raise exceptionTools.OnlineMirrorError("OnlineMirrorError: you are not connected to the Internet. You should.")

        if (not self.reponames):
            for x in etpRepositories:
                self.reponames.append(x)

    def validateRepositoryId(self, repoid):
        if repoid not in self.reponames:
            raise exceptionTools.InvalidData("InvalidData: repository is not listed in self.reponames")

    # @returns -1 if the file is not available
    # @returns int>0 if the revision has been retrieved
    def getOnlineRepositoryRevision(self, repo):

        self.validateRepositoryId(repo)

        url = etpRepositories[repo]['database']+"/"+etpConst['etpdatabaserevisionfile']
        status = self.remoteTools.getOnlineContent(url)
        if (status):
            status = status[0].strip()
            return int(status)
        else:
            return -1

    def isRepositoryUpdatable(self, repo):

        self.validateRepositoryId(repo)

        onlinestatus = self.getOnlineRepositoryRevision(repo)
        if (onlinestatus != -1):
            localstatus = getRepositoryRevision(repo)
            if (localstatus == onlinestatus) and (not self.forceUpdate):
                return False
        return True

    def isRepositoryUnlocked(self, repo):

        self.validateRepositoryId(repo)

        rc = self.downloadItem("lock", repo)
        if rc: # cannot download database
            self.syncErrors = True
            return False
        return True

    def clearRepositoryCache(self, repo):

        self.validateRepositoryId(repo)

        self.dumpTools.dumpobj(etpCache['dbInfo']+repo,{})

    def validateCompressionMethod(self, repo):

        self.validateRepositoryId(repo)

        cmethod = etpConst['etpdatabasecompressclasses'].get(etpRepositories[repo]['dbcformat'])
        if cmethod == None:
            raise exceptionTools.InvalidDataType("InvalidDataType: wrong database compression method passed.")
        return cmethod

    def ensureRepositoryPath(self, repo):

        self.validateRepositoryId(repo)

	# create dir if it doesn't exist
	if not os.path.isdir(etpRepositories[repo]['dbpath']):
	    os.makedirs(etpRepositories[repo]['dbpath'])

    def constructPaths(self, item, repo, cmethod):

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

    # this function can be reimplemented
    def downloadItem(self, item, repo, cmethod = None):

        self.validateRepositoryId(repo)
        url, filepath = self.constructPaths(item, repo, cmethod)

        fetchConn = self.remoteTools.urlFetcher(url, filepath)
	rc = fetchConn.download()
        if rc in ("-1","-2","-3"):
            del fetchConn
            return False
        del fetchConn
        return True

    def removeRepositoryFiles(self, repo, dbfilenameid):

        self.validateRepositoryId(repo)

        if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile']):
            os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'])
        if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst[dbfilenameid]):
            os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst[dbfilenameid])
        if os.path.isfile(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile']):
            os.remove(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabaserevisionfile'])

    def unpackDownloadedDatabase(self, repo, cmethod):

        self.validateRepositoryId(repo)

        import entropyTools
        path = eval("entropyTools."+cmethod[1])(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[2]])
        return path

    def verifyDatabaseChecksum(self, repo):

        self.validateRepositoryId(repo)

        import entropyTools
        try:
            f = open(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
            md5hash = f.readline().strip()
            md5hash = md5hash.split()[0]
            f.close()
        except:
            return -1
	rc = entropyTools.compareMd5(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasefile'],md5hash)
        return rc

    def closeTransactions(self):

        if not self.dbupdated:
            return

        # safely clean ram caches
        atomMatchCache.clear()
        self.dumpTools.dumpobj(etpCache['atomMatch'],{})
        generateDependsTreeCache.clear()
        self.dumpTools.dumpobj(etpCache['generateDependsTree'],{})
        for dbinfo in dbCacheStore:
            dbCacheStore[dbinfo].clear()
            self.dumpTools.dumpobj(dbinfo,{})
    
        # clean caches
        import cacheTools
        cacheTools.generateCache(depcache = True, configcache = False)
    
        # clean resume caches
        self.dumpTools.dumpobj(etpCache['install'],{})
        self.dumpTools.dumpobj(etpCache['world'],{})
        self.dumpTools.dumpobj(etpCache['remove'],[])
