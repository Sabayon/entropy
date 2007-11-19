#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo User interface library and functions

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
##   Packages user handling function
#

from entropyConstants import *
from clientConstants import *
from outputTools import *
import equoTools
import repositoriesTools
from databaseTools import openRepositoryDatabase, openClientDatabase, openGenericDatabase, listAllAvailableBranches
import entropyTools
import dumpTools
import shutil

import logTools
equoLog = logTools.LogFile(level = etpConst['equologlevel'],filename = etpConst['equologfile'], header = "[Equo]")

def package(options):

    if len(options) < 1:
	return 0

    # Options available for all the packages submodules
    myopts = options[1:]
    equoRequestAsk = False
    equoRequestPretend = False
    equoRequestPackagesCheck = False
    equoRequestVerbose = False
    equoRequestDeps = True
    equoRequestEmptyDeps = False
    equoRequestOnlyFetch = False
    equoRequestQuiet = False
    equoRequestDeep = False
    equoRequestConfigFiles = False
    equoRequestReplay = False
    equoRequestUpgrade = False
    equoRequestResume = False
    equoRequestUpgradeTo = ''
    rc = 0
    _myopts = []
    mytbz2paths = []
    for opt in myopts:
	if (opt == "--ask"):
	    equoRequestAsk = True
	elif (opt == "--pretend"):
	    equoRequestPretend = True
	elif (opt == "--verbose"):
	    equoRequestVerbose = True
	elif (opt == "--nodeps"):
	    equoRequestDeps = False
	elif (opt == "--empty"):
	    equoRequestEmptyDeps = True
	elif (opt == "--quiet"):
	    equoRequestQuiet = True
	elif (opt == "--fetch"):
	    equoRequestOnlyFetch = True
	elif (opt == "--deep"):
	    equoRequestDeep = True
	elif (opt == "--configfiles"):
	    equoRequestConfigFiles = True
	elif (opt == "--replay"):
	    equoRequestReplay = True
	elif (opt == "--upgrade"):
	    equoRequestUpgrade = True
	elif (opt == "--resume"):
	    equoRequestResume = True
	else:
            if (equoRequestUpgrade):
                equoRequestUpgradeTo = opt
	    elif opt.endswith(".tbz2") and os.access(opt,os.R_OK):
		mytbz2paths.append(opt)
	    else:
	        _myopts.append(opt)
    myopts = _myopts

    if (options[0] == "deptest"):
	equoTools.loadCaches()
	rc, garbage = dependenciesTest(quiet = equoRequestQuiet, ask = equoRequestAsk, pretend = equoRequestPretend)

    elif (options[0] == "install"):
	if (myopts) or (mytbz2paths) or (equoRequestResume):
	    equoTools.loadCaches()
	    rc, status = installPackages(myopts, ask = equoRequestAsk, pretend = equoRequestPretend, verbose = equoRequestVerbose, deps = equoRequestDeps, emptydeps = equoRequestEmptyDeps, onlyfetch = equoRequestOnlyFetch, deepdeps = equoRequestDeep, configFiles = equoRequestConfigFiles, tbz2 = mytbz2paths, resume = equoRequestResume)
	else:
	    print_error(red(" Nothing to do."))
	    rc = 127

    elif (options[0] == "world"):
	equoTools.loadCaches()
	rc, status = worldUpdate(ask = equoRequestAsk, pretend = equoRequestPretend, verbose = equoRequestVerbose, onlyfetch = equoRequestOnlyFetch, replay = (equoRequestReplay or equoRequestEmptyDeps), upgradeTo = equoRequestUpgradeTo, resume = equoRequestResume)

    elif (options[0] == "remove"):
	if myopts or equoRequestResume:
	    equoTools.loadCaches()
	    rc, status = removePackages(myopts, ask = equoRequestAsk, pretend = equoRequestPretend, verbose = equoRequestVerbose, deps = equoRequestDeps, deep = equoRequestDeep, configFiles = equoRequestConfigFiles, resume = equoRequestResume)
	else:
	    print_error(red(" Nothing to do."))
	    rc = 127
    else:
        rc = -10

    return rc


def worldUpdate(ask = False, pretend = False, verbose = False, onlyfetch = False, replay = False, upgradeTo = '', resume = False):

    # check if I am root
    if (not entropyTools.isRoot()):
        print_warning(red("Running with ")+bold("--pretend")+red("..."))
	pretend = True

    if not resume:

        if not pretend:
            repositoriesTools.syncRepositories()
    
        # verify selected release (branch)
        if (upgradeTo):
            availbranches = listAllAvailableBranches()
            if upgradeTo not in availbranches:
                print_error(red("Selected release: ")+bold(upgradeTo)+red(" is not available."))
                return 1,-2
            else:
                branches = (upgradeTo,)
        else:
            branches = (etpConst['branch'],)
        
        if (not pretend) and (upgradeTo):
            # update configuration
            entropyTools.writeNewBranch(upgradeTo)
        
        updateList = set()
        fineList = set()
        removedList = set()
        clientDbconn = openClientDatabase()
        # get all the installed packages
        packages = clientDbconn.listAllPackages()
        
        print_info(red(" @@ ")+blue("Calculating world packages..."))
        for package in packages:
            tainted = False
            atom = package[0]
            idpackage = package[1]
            name = clientDbconn.retrieveName(idpackage)
            category = clientDbconn.retrieveCategory(idpackage)
            revision = clientDbconn.retrieveRevision(idpackage)
            slot = clientDbconn.retrieveSlot(idpackage)
            atomkey = category+"/"+name
            # search in the packages
            match = equoTools.atomMatch(atom)
            if match[0] == -1: # atom has been changed, or removed?
                tainted = True
            else: # not changed, is the revision changed?
                adbconn = openRepositoryDatabase(match[1])
                arevision = adbconn.retrieveRevision(match[0])
                # if revision is 9999, then any revision is fine
                if revision == 9999: arevision = 9999
                adbconn.closeDB()
                if revision != arevision:
                    tainted = True
                elif (replay):
                    tainted = True
            if (tainted):
                # Alice! use the key! ... and the slot
                matchresults = equoTools.atomMatch(atomkey, matchSlot = slot, matchBranches = branches)
                if matchresults[0] != -1:
                    mdbconn = openRepositoryDatabase(matchresults[1])
                    matchatom = mdbconn.retrieveAtom(matchresults[0])
                    mdbconn.closeDB()
                    updateList.add((matchatom,matchresults))
                else:
                    removedList.add(idpackage)
                    # look for packages that would match key with any slot (for eg, gcc updates), slot changes handling
                    matchresults = equoTools.atomMatch(atomkey, matchBranches = branches)
                    if matchresults[0] != -1:
                        mdbconn = openRepositoryDatabase(matchresults[1])
                        matchatom = mdbconn.retrieveAtom(matchresults[0])
                        mdbconn.closeDB()
                        # compare versions
                        unsatisfied, satisfied = equoTools.filterSatisfiedDependencies((matchatom,))
                        if unsatisfied:
                            updateList.add((matchatom,matchresults))
            else:
                fineList.add(idpackage)
    
        if (verbose or pretend):
            print_info(red(" @@ ")+darkgreen("Packages matching update:\t\t")+bold(str(len(updateList))))
            print_info(red(" @@ ")+darkred("Packages matching not available:\t\t")+bold(str(len(removedList))))
            print_info(red(" @@ ")+blue("Packages matching already up to date:\t")+bold(str(len(fineList))))
    
        # clear old resume information
        dumpTools.dumpobj(etpCache['world'],{})
        dumpTools.dumpobj(etpCache['install'],{})
        dumpTools.dumpobj(etpCache['remove'],[])
        if (not pretend):
            # store resume information
            resume_cache = {}
            resume_cache['ask'] = ask
            resume_cache['verbose'] = verbose
            resume_cache['onlyfetch'] = onlyfetch
            resume_cache['removedList'] = removedList
            dumpTools.dumpobj(etpCache['world'],resume_cache)

    else: # if resume, load cache if possible
        
        # check if there's something to resume
        resume_cache = dumpTools.loadobj(etpCache['world'])
        if not resume_cache: # None or {}
            print_error(red("Nothing to resume."))
            return 128,-1
        else:
            try:
                updateList = []
                removedList = resume_cache['removedList'].copy()
                ask = resume_cache['ask']
                verbose = resume_cache['verbose']
                onlyfetch = resume_cache['onlyfetch']
                # save removal stuff into etpCache['remove']
                dumpTools.dumpobj(etpCache['remove'],list(removedList))
            except:
                print_error(red("Resume cache corrupted."))
                dumpTools.dumpobj(etpCache['world'],{})
                dumpTools.dumpobj(etpCache['install'],{})
                dumpTools.dumpobj(etpCache['remove'],[])
                return 128,-1

    # disable collisions protection, better
    oldcollprotect = etpConst['collisionprotect']
    etpConst['collisionprotect'] = 0

    if (updateList) or (resume):
        rc = installPackages(atomsdata = updateList, ask = ask, pretend = pretend, verbose = verbose, onlyfetch = onlyfetch, resume = resume)
	if rc[0] != 0:
	    return rc
    else:
	print_info(red(" @@ ")+blue("Nothing to update."))

    etpConst['collisionprotect'] = oldcollprotect
    if (removedList):
	removedList = list(removedList)
	removedList.sort()
	print_info(red(" @@ ")+blue("On the system there are packages that are not available anymore in the online repositories."))
	print_info(red(" @@ ")+blue("Even if they are usually harmless, it is suggested to remove them."))
	
	if (not pretend):
	    if (ask):
	        rc = entropyTools.askquestion("     Would you like to query them ?")
	        if rc == "No":
		    clientDbconn.closeDB()
		    return 0,0
	    else:
		print_info(red(" @@ ")+blue("Running query in ")+red("5 seconds")+blue("..."))
		print_info(red(" @@ ")+blue(":: Hit CTRL+C to stop"))
		import time
	        time.sleep(5)
	
	    # run removePackages with --nodeps
	    removePackages(atomsdata = removedList, ask = ask, verbose = verbose, deps = False, systemPackagesCheck = False, configFiles = True, resume = resume)
	else:
	    print_info(red(" @@ ")+blue("Calculation complete."))

    else:
	print_info(red(" @@ ")+blue("Nothing to remove."))

    clientDbconn.closeDB()
    return 0,0

def installPackages(packages = [], atomsdata = [], ask = False, pretend = False, verbose = False, deps = True, emptydeps = False, onlyfetch = False, deepdeps = False, configFiles = False, tbz2 = [], resume = False):

    # check if I am root
    if (not entropyTools.isRoot()):
        print_warning(red("Running with ")+bold("--pretend")+red("..."))
	pretend = True

    dirsCleanup = set()
    def dirscleanup():
        for x in dirsCleanup:
            try:
                if os.path.isdir(x): shutil.rmtree(x)
            except:
                pass

    if not resume:
        
        if (atomsdata):
            foundAtoms = atomsdata
        else:
            foundAtoms = []
            for package in packages:
                foundAtoms.append([package,equoTools.atomMatch(package)])
            if tbz2:
                for pkg in tbz2:
                    # create a repository for each database
                    basefile = os.path.basename(pkg)
                    if os.path.isdir(etpConst['entropyunpackdir']+"/"+basefile[:-5]):
                        shutil.rmtree(etpConst['entropyunpackdir']+"/"+basefile[:-5])
                    os.makedirs(etpConst['entropyunpackdir']+"/"+basefile[:-5])
                    dbfile = entropyTools.extractEdb(pkg,dbpath = etpConst['entropyunpackdir']+"/"+basefile[:-5]+"/packages.db")
                    if dbfile == None:
                        print_warning(red("## ATTENTION:")+bold(" "+basefile+" ")+red(" is not a valid Entropy package. Skipping..."))
                        continue
                    dirsCleanup.add(os.path.dirname(dbfile))
                    # add dbfile
                    etpRepositories[basefile] = {}
                    etpRepositories[basefile]['description'] = "Dynamic database from "+basefile
                    etpRepositories[basefile]['packages'] = []
                    etpRepositories[basefile]['dbpath'] = os.path.dirname(dbfile)
                    etpRepositories[basefile]['pkgpath'] = os.path.realpath(pkg) # extra info added
                    etpRepositories[basefile]['configprotect'] = set()
                    etpRepositories[basefile]['configprotectmask'] = set()
                    etpRepositories[basefile]['smartpackage'] = False # extra info added
                    # get max count
                    repoordercount = [x[0] for x in etpRepositoriesOrder]
                    repoordercount.sort()
                    etpRepositoriesOrder.add((repoordercount[-1]+1,basefile))
                    mydbconn = openGenericDatabase(dbfile)
                    # read all idpackages
                    myidpackages = mydbconn.listAllIdpackages() # all branches admitted from external files
                    if len(myidpackages) > 1:
                        etpRepositories[basefile]['smartpackage'] = True
                    for myidpackage in myidpackages:
                        foundAtoms.append([pkg,(int(myidpackage),basefile)])
                    mydbconn.closeDB()

        # filter packages not found
        _foundAtoms = []
        for result in foundAtoms:
            exitcode = result[1][0]
            if (exitcode != -1):
                _foundAtoms.append(result[1])
            else:
                print_warning(red("## ATTENTION: no match for ")+bold(" "+result[0]+" ")+red(" in database. If you omitted the category, try adding it."))

        foundAtoms = _foundAtoms

        # are there packages in foundAtoms?
        if (not foundAtoms):
            print_error(red("No packages found"))
            dirscleanup()
            return 127,-1

        if (ask or pretend or verbose):
            # now print the selected packages
            print_info(red(" @@ ")+blue("These are the chosen packages:"))
            totalatoms = len(foundAtoms)
            atomscounter = 0
            for atomInfo in foundAtoms:
                atomscounter += 1
                idpackage = atomInfo[0]
                reponame = atomInfo[1]
                # open database
                dbconn = openRepositoryDatabase(reponame)
    
                # get needed info
                pkgatom = dbconn.retrieveAtom(idpackage)
                pkgver = dbconn.retrieveVersion(idpackage)
                pkgtag = dbconn.retrieveVersionTag(idpackage)
                if not pkgtag:
                    pkgtag = "NoTag"
                pkgrev = dbconn.retrieveRevision(idpackage)
                pkgslot = dbconn.retrieveSlot(idpackage)
            
                # client info
                installedVer = "Not installed"
                installedTag = "NoTag"
                installedRev = "NoRev"
                clientDbconn = openClientDatabase()
                if (clientDbconn != -1):
                    pkginstalled = clientDbconn.atomMatch(entropyTools.dep_getkey(pkgatom), matchSlot = pkgslot)
                    if (pkginstalled[1] == 0):
                        # found
                        idx = pkginstalled[0]
                        installedVer = clientDbconn.retrieveVersion(idx)
                        installedTag = clientDbconn.retrieveVersionTag(idx)
                        if not installedTag:
                            installedTag = "NoTag"
                        installedRev = clientDbconn.retrieveRevision(idx)
                    clientDbconn.closeDB()
    
                print_info("   # "+red("(")+bold(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+bold(pkgatom)+" >>> "+red(etpRepositories[reponame]['description']))
                print_info("\t"+red("Versioning:\t")+" "+blue(installedVer)+" / "+blue(installedTag)+" / "+blue(str(installedRev))+bold(" ===> ")+darkgreen(pkgver)+" / "+darkgreen(pkgtag)+" / "+darkgreen(str(pkgrev)))
                # tell wether we should update it
                if installedVer == "Not installed":
                    installedVer = "0"
                if installedTag == "NoTag":
                    installedTag == ''
                if installedRev == "NoRev":
                    installedRev == 0
                cmp = entropyTools.entropyCompareVersions((pkgver,pkgtag,pkgrev),(installedVer,installedTag,installedRev))
                if (cmp == 0):
                    action = darkgreen("No update needed")
                elif (cmp > 0):
                    if (installedVer == "0"):
                        action = darkgreen("Install")
                    else:
                        action = blue("Upgrade")
                else:
                    action = red("Downgrade")
                print_info("\t"+red("Action:\t\t")+" "+action)
            
                dbconn.closeDB()
    
            if (verbose or ask or pretend):
                print_info(red(" @@ ")+blue("Number of packages: ")+str(totalatoms))
        
            if (deps):
                if (ask):
                    rc = entropyTools.askquestion("     Would you like to continue with dependencies calculation ?")
                    if rc == "No":
                        dirscleanup()
                        return 0,0
    
        runQueue = []
        removalQueue = [] # aka, conflicts
        print_info(red(" @@ ")+blue("Calculating dependencies..."))
    
        if (deps):
            treepackages, result = equoTools.getRequiredPackages(foundAtoms, emptydeps, deepdeps, spinning = True)
            # add dependencies, explode them
            
            if (result == -2):
                print_error(red(" @@ ")+blue("Cannot find needed dependencies: ")+str(treepackages))
                for atom in treepackages:
                    for repo in etpRepositories:
                        rdbconn = openRepositoryDatabase(repo)
                        riddep = rdbconn.searchDependency(atom)
                        if riddep != -1:
                            ridpackages = rdbconn.searchIdpackageFromIddependency(riddep)
                            if ridpackages:
                                print_error(red(" @@ ")+blue("Dependency found and probably needed by:"))
                            for i in ridpackages:
                                iatom = rdbconn.retrieveAtom(i)
                                print_error(red("     # ")+" [from:"+repo+"] "+darkred(iatom))
                        rdbconn.closeDB()
                dirscleanup()
                return 130, -1
            
            elif (result == -1): # no database connection
                print_error(red(" @@ ")+blue("Cannot find the Installed Packages Database. It's needed to accomplish dependency resolving. Try to run ")+bold("equo database generate"))
                dirscleanup()
                return 200, -1
            
            for x in range(len(treepackages)):
                if x == 0:
                    # conflicts
                    for a in treepackages[x]:
                        removalQueue.append(a)
                else:
                    for a in treepackages[x]:
                        runQueue.append(a)
            del treepackages
        else:
            for atomInfo in foundAtoms:
                runQueue.append(atomInfo)
    
        downloadSize = 0
        onDiskUsedSize = 0
        onDiskFreedSize = 0
        pkgsToInstall = 0
        pkgsToUpdate = 0
        pkgsToReinstall = 0
        pkgsToDowngrade = 0
        pkgsToRemove = len(removalQueue)
        actionQueue = {}
    
        if (not runQueue) and (not removalQueue):
            print_error(red("Nothing to do."))
            dirscleanup()
            return 127,-1
    
        if (runQueue):
            if (ask or pretend):
                print_info(red(" @@ ")+blue("These are the packages that would be ")+bold("merged:"))
            
            if not (ask or pretend): count = 0
            atomlen = len(runQueue)
            for packageInfo in runQueue:
                if not (ask or pretend): count += 1; print_info(":: Collecting data: "+str(round((float(count)/atomlen)*100,1))+"% ::", back = True)
                dbconn = openRepositoryDatabase(packageInfo[1])
                mydata = dbconn.getBaseData(packageInfo[0])
                pkgatom = mydata[0]
                pkgver = mydata[2]
                pkgtag = mydata[3]
                pkgrev = mydata[18]
                pkgslot = mydata[14]
                pkgfile = mydata[12]
                pkgcat = mydata[5]
                pkgname = mydata[1]

                onDiskUsedSize += dbconn.retrieveOnDiskSize(packageInfo[0]) # still new
                
                # fill action queue
                actionQueue[pkgatom] = {}
                actionQueue[pkgatom]['repository'] = packageInfo[1]
                actionQueue[pkgatom]['idpackage'] = packageInfo[0]
                actionQueue[pkgatom]['slot'] = pkgslot
                actionQueue[pkgatom]['atom'] = pkgatom
                actionQueue[pkgatom]['version'] = pkgver
                actionQueue[pkgatom]['category'] = pkgcat
                actionQueue[pkgatom]['name'] = pkgname
                actionQueue[pkgatom]['removeidpackage'] = -1
                actionQueue[pkgatom]['download'] = pkgfile
                actionQueue[pkgatom]['removeconfig'] = configFiles
                dl = equoTools.checkNeededDownload(pkgfile, None) # we'll do a good check during installPackage
                actionQueue[pkgatom]['fetch'] = dl
                if dl < 0:
                    pkgsize = dbconn.retrieveSize(packageInfo[0])
                    downloadSize += int(pkgsize)
            
                # get installed package data
                installedVer = '0'
                installedTag = ''
                installedRev = 0
                clientDbconn = openClientDatabase()
                if (clientDbconn != -1):
                    pkginstalled = clientDbconn.atomMatch(entropyTools.dep_getkey(pkgatom), matchSlot = pkgslot)
                    if (pkginstalled[1] == 0):
                        # found
                        idx = pkginstalled[0]
                        installedVer = clientDbconn.retrieveVersion(idx)
                        installedTag = clientDbconn.retrieveVersionTag(idx)
                        installedRev = clientDbconn.retrieveRevision(idx)
                        actionQueue[pkgatom]['removeidpackage'] = idx
                        onDiskFreedSize += clientDbconn.retrieveOnDiskSize(idx)
                    clientDbconn.closeDB()
    
                if not (ask or pretend or verbose):
                    continue
    
                action = 0
                flags = " ["
                cmp = entropyTools.entropyCompareVersions((pkgver,pkgtag,pkgrev),(installedVer,installedTag,installedRev))
                if (cmp == 0):
                    pkgsToReinstall += 1
                    actionQueue[pkgatom]['removeidpackage'] = -1 # disable removal, not needed
                    flags += red("R")
                    action = 1
                elif (cmp > 0):
                    if (installedVer == "0"):
                        pkgsToInstall += 1
                        actionQueue[pkgatom]['removeidpackage'] = -1 # disable removal, not needed
                        flags += darkgreen("N")
                    else:
                        pkgsToUpdate += 1
                        flags += blue("U")
                        action = 2
                else:
                    pkgsToDowngrade += 1
                    flags += darkblue("D")
                    action = -1
                flags += "] "
    
                # disable removal for packages already in removalQueue
                if actionQueue[pkgatom]['removeidpackage'] in removalQueue:
                    actionQueue[pkgatom]['removeidpackage'] = -1
    
                repoinfo = red("[")+bold(packageInfo[1])+red("] ")
                oldinfo = ''
                if action != 0:
                    oldinfo = "   ["+blue(installedVer)+"/"+red(str(installedRev))
                    oldtag = "]"
                    if installedTag:
                        oldtag = "/"+darkred(installedTag)+oldtag
                    oldinfo += oldtag
    
                print_info(darkred(" ##")+flags+repoinfo+enlightenatom(str(pkgatom))+"/"+str(pkgrev)+oldinfo)
                dbconn.closeDB()
    
        if (removalQueue):
            
            # add depends to removalQueue that are not in runQueue
            clientDbconn = openClientDatabase()
            dependQueue = set()
            for idpackage in removalQueue:
                depends = clientDbconn.retrieveDepends(idpackage)
                if depends == -2:
                    clientDbconn.regenerateDependsTable(output = False)
                    depends = clientDbconn.retrieveDepends(idpackage)
                for depend in depends:
                    dependkey = clientDbconn.retrieveCategory(depend)+"/"+clientDbconn.retrieveName(depend)
                    dependslot = clientDbconn.retrieveSlot(depend)
                    # match in repositories
                    match = equoTools.atomMatch(dependkey, matchSlot = dependslot)
                    if match[0] != -1:
                        matchdbconn = openRepositoryDatabase(match[1])
                        matchatom = matchdbconn.retrieveAtom(match[0])
                        matchdbconn.closeDB()
                        if (matchatom not in actionQueue) and (depend not in removalQueue): # if the atom hasn't been pulled in, we need to remove depend
                            dependQueue.add(depend)
            for depend in dependQueue:
                removalQueue.append(depend)
            
            if (ask or pretend or verbose):
                print_info(red(" @@ ")+blue("These are the packages that would be ")+bold("removed")+blue(" (conflicting/substituted):"))
    
                for idpackage in removalQueue:
                    pkgatom = clientDbconn.retrieveAtom(idpackage)
                    onDiskFreedSize += clientDbconn.retrieveOnDiskSize(idpackage)
                    installedfrom = clientDbconn.retrievePackageFromInstalledTable(idpackage)
                    repoinfo = red("[")+brown("from: ")+bold(installedfrom)+red("] ")
                    print_info(red("   ## ")+"["+red("W")+"] "+repoinfo+enlightenatom(pkgatom))
    
            clientDbconn.closeDB()
        
        if (runQueue) or (removalQueue):
            # show download info
            print_info(red(" @@ ")+blue("Packages needing install:\t")+red(str(len(runQueue))))
            print_info(red(" @@ ")+blue("Packages needing removal:\t")+red(str(pkgsToRemove)))
            if (ask or verbose or pretend):
                print_info(red(" @@ ")+darkgreen("Packages needing install:\t")+darkgreen(str(pkgsToInstall)))
                print_info(red(" @@ ")+darkgreen("Packages needing reinstall:\t")+darkgreen(str(pkgsToReinstall)))
                print_info(red(" @@ ")+blue("Packages needing update:\t\t")+blue(str(pkgsToUpdate)))
                print_info(red(" @@ ")+red("Packages needing downgrade:\t")+red(str(pkgsToDowngrade)))
            print_info(red(" @@ ")+blue("Download size:\t\t\t")+bold(str(entropyTools.bytesIntoHuman(downloadSize))))
            deltaSize = onDiskUsedSize - onDiskFreedSize
            if (deltaSize > 0):
                print_info(red(" @@ ")+blue("Used disk space:\t\t\t")+bold(str(entropyTools.bytesIntoHuman(deltaSize))))
            else:
                print_info(red(" @@ ")+blue("Freed disk space:\t\t")+bold(str(entropyTools.bytesIntoHuman(abs(deltaSize)))))
    
        if (ask):
            rc = entropyTools.askquestion("     Would you like to run the queue ?")
            if rc == "No":
                dirscleanup()
                return 0,0
        if (pretend):
            dirscleanup()
            return 0,0
        
        # clear old resume information
        dumpTools.dumpobj(etpCache['install'],{})
        # store resume information
        if not tbz2: # .tbz2 install resume not supported
            resume_cache = {}
            resume_cache['removalQueue'] = removalQueue[:]
            resume_cache['runQueue'] = runQueue[:]
            resume_cache['actionQueue'] = actionQueue.copy()
            resume_cache['onlyfetch'] = onlyfetch
            dumpTools.dumpobj(etpCache['install'],resume_cache)

    else: # if resume, load cache if possible
        
        # check if there's something to resume
        resume_cache = dumpTools.loadobj(etpCache['install'])
        if not resume_cache: # None or {}
            print_error(red("Nothing to resume."))
            return 128,-1
        else:
            try:
                removalQueue = resume_cache['removalQueue'][:]
                runQueue = resume_cache['runQueue'][:]
                actionQueue = resume_cache['actionQueue'].copy()
                onlyfetch = resume_cache['onlyfetch']
                print_warning(red("Resuming previous operations..."))
            except:
                print_error(red("Resume cache corrupted."))
                dumpTools.dumpobj(etpCache['install'],{})
                return 128,-1

    # running tasks
    totalqueue = str(len(runQueue))
    totalremovalqueue = str(len(removalQueue))
    currentqueue = 0
    currentremovalqueue = 0
    clientDbconn = openClientDatabase()
    
    for idpackage in removalQueue:
        currentremovalqueue += 1
	infoDict = {}
	infoDict['removeatom'] = clientDbconn.retrieveAtom(idpackage)
	infoDict['removecontent'] = clientDbconn.retrieveContent(idpackage)
	infoDict['removeidpackage'] = idpackage
	infoDict['diffremoval'] = False
	infoDict['removeconfig'] = True # we need to completely wipe configuration of conflicts
	etpRemovalTriggers[infoDict['removeatom']] = clientDbconn.getPackageData(idpackage)
	etpRemovalTriggers[infoDict['removeatom']]['removecontent'] = infoDict['removecontent'].copy()
	etpRemovalTriggers[infoDict['removeatom']]['trigger'] = clientDbconn.retrieveTrigger(idpackage)
	steps = []
	steps.append("preremove")
	steps.append("remove")
	steps.append("postremove")
	for step in steps:
	    rc = equoTools.stepExecutor(step,infoDict,str(currentremovalqueue)+"/"+totalremovalqueue)
	    if (rc != 0):
		clientDbconn.closeDB()
                dirscleanup()
		return -1,rc
        
        # update resume cache
        if not tbz2: # tbz2 caching not supported
            resume_cache['removalQueue'].remove(idpackage)
            dumpTools.dumpobj(etpCache['install'],resume_cache)
        
    
    for packageInfo in runQueue:
	currentqueue += 1
	idpackage = packageInfo[0]
	repository = packageInfo[1]
	# get package atom
	dbconn = openRepositoryDatabase(repository)
	pkgatom = dbconn.retrieveAtom(idpackage)
        actionQueue[pkgatom]['messages'] = dbconn.retrieveMessages(idpackage)
        actionQueue[pkgatom]['checksum'] = dbconn.retrieveDigest(idpackage)

	steps = []
	# download
	if not repository.endswith(".tbz2"):
	    if (actionQueue[pkgatom]['fetch'] < 0):
	        steps.append("fetch")
	    steps.append("checksum")
	
	# differential remove list
	if (actionQueue[pkgatom]['removeidpackage'] != -1):
            # is it still available?
            if clientDbconn.isIDPackageAvailable(actionQueue[pkgatom]['removeidpackage']):
                oldcontent = clientDbconn.retrieveContent(actionQueue[pkgatom]['removeidpackage'])
                newcontent = dbconn.retrieveContent(idpackage)
                oldcontent.difference_update(newcontent)
                actionQueue[pkgatom]['removecontent'] = oldcontent
                actionQueue[pkgatom]['diffremoval'] = True
                actionQueue[pkgatom]['removeatom'] = clientDbconn.retrieveAtom(actionQueue[pkgatom]['removeidpackage'])
                etpRemovalTriggers[pkgatom] = clientDbconn.getPackageData(actionQueue[pkgatom]['removeidpackage'])
                etpRemovalTriggers[pkgatom]['removecontent'] = actionQueue[pkgatom]['removecontent'].copy()
                etpRemovalTriggers[pkgatom]['trigger'] = clientDbconn.retrieveTrigger(actionQueue[pkgatom]['removeidpackage'])
            else:
                actionQueue[pkgatom]['removeidpackage'] = -1

	# get data for triggerring tool
	etpInstallTriggers[pkgatom] = dbconn.getPackageData(idpackage)
        etpInstallTriggers[pkgatom]['trigger'] = dbconn.retrieveTrigger(idpackage)

	dbconn.closeDB()

	if (not onlyfetch):
	    # install
	    if (actionQueue[pkgatom]['removeidpackage'] != -1):
		steps.append("preremove")
	    steps.append("preinstall")
	    steps.append("install")
	    if (actionQueue[pkgatom]['removeidpackage'] != -1):
		steps.append("postremove")
	    steps.append("postinstall")
	    steps.append("showmessages")
	
	print_info(red(" @@ ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(pkgatom))
	
	for step in steps:
	    rc = equoTools.stepExecutor(step,actionQueue[pkgatom],str(currentqueue)+"/"+totalqueue)
	    if (rc != 0):
		clientDbconn.closeDB()
                dirscleanup()
		return -1,rc

        # update resume cache
        if not tbz2: # tbz2 caching not supported
            resume_cache['runQueue'].remove(packageInfo)
            dumpTools.dumpobj(etpCache['install'],resume_cache)

    if (onlyfetch):
	print_info(red(" @@ ")+blue("Fetch Complete."))
    else:
	print_info(red(" @@ ")+blue("Install Complete."))

    # clear resume information
    dumpTools.dumpobj(etpCache['install'],{})
    
    clientDbconn.closeDB()
    dirscleanup()
    return 0,0


def removePackages(packages = [], atomsdata = [], ask = False, pretend = False, verbose = False, deps = True, deep = False, systemPackagesCheck = True, configFiles = False, resume = False):
    
    # check if I am root
    if (not entropyTools.isRoot()):
        print_warning(red("Running with ")+bold("--pretend")+red("..."))
	pretend = True

    clientDbconn = openClientDatabase()

    if not resume:

        foundAtoms = []
        if (atomsdata):
            for idpackage in atomsdata:
                foundAtoms.append([clientDbconn.retrieveAtom(idpackage),(idpackage,0)])
        else:
            for package in packages:
                foundAtoms.append([package,clientDbconn.atomMatch(package)])
    
        # filter packages not found
        _foundAtoms = []
        for result in foundAtoms:
            exitcode = result[1][0]
            if (exitcode != -1):
                _foundAtoms.append(result[1])
            else:
                print_warning(red("## ATTENTION -> package")+bold(" "+result[0]+" ")+red("is not installed."))
    
        foundAtoms = _foundAtoms
        
        # are packages in foundAtoms?
        if (len(foundAtoms) == 0):
            print_error(red("No packages found"))
            return 127,-1
    
        plainRemovalQueue = []
        
        lookForOrphanedPackages = True
        # now print the selected packages
        print_info(red(" @@ ")+blue("These are the chosen packages:"))
        totalatoms = len(foundAtoms)
        atomscounter = 0
        for atomInfo in foundAtoms:
            atomscounter += 1
            idpackage = atomInfo[0]
            systemPackage = clientDbconn.isSystemPackage(idpackage)
    
            # get needed info
            pkgatom = clientDbconn.retrieveAtom(idpackage)
            installedfrom = clientDbconn.retrievePackageFromInstalledTable(idpackage)
    
            if (systemPackage) and (systemPackagesCheck):
                # check if the package is slotted and exist more than one installed first
                sysresults = clientDbconn.atomMatch(entropyTools.dep_getkey(pkgatom), multiMatch = True)
                slots = set()
                if sysresults[1] == 0:
                    for x in sysresults[0]:
                        slots.add(clientDbconn.retrieveSlot(x))
                    if len(slots) < 2:
                        print_warning(darkred("   # !!! ")+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+red(" is a vital package. Removal forbidden."))
                        continue
                else:
                    print_warning(darkred("   # !!! ")+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+red(" is a vital package. Removal forbidden."))
                    continue
            plainRemovalQueue.append(idpackage)
            
            print_info("   # "+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+" | Installed from: "+red(installedfrom))
    
        if (verbose or ask or pretend):
            print_info(red(" @@ ")+blue("Number of packages: ")+str(totalatoms))
        
        if (deps):
            question = "     Would you like to look for packages that can be removed along with the selected above?"
        else:
            question = "     Would you like to remove them now?"
            lookForOrphanedPackages = False
    
        if (ask):
            rc = entropyTools.askquestion(question)
            if rc == "No":
                lookForOrphanedPackages = False
                if (not deps):
                    clientDbconn.closeDB()
                    return 0,0
    
        if (not plainRemovalQueue):
            print_error(red("Nothing to do."))
            return 127,-1
    
        removalQueue = []
        
        if (lookForOrphanedPackages):
            choosenRemovalQueue = []
            print_info(red(" @@ ")+blue("Calculating..."))
            treeview = equoTools.generateDependsTree(plainRemovalQueue, deep = deep)
            treelength = len(treeview[0])
            if treelength > 1:
                treeview = treeview[0]
                for x in range(treelength)[::-1]:
                    for y in treeview[x]:
                        choosenRemovalQueue.append(y)
            
                if (choosenRemovalQueue):
                    print_info(red(" @@ ")+blue("These are the packages that would be added to the removal queue:"))
                    totalatoms = str(len(choosenRemovalQueue))
                    atomscounter = 0
                
                    for idpackage in choosenRemovalQueue:
                        atomscounter += 1
                        rematom = clientDbconn.retrieveAtom(idpackage)
                        installedfrom = clientDbconn.retrievePackageFromInstalledTable(idpackage)
                        repositoryInfo = bold("[")+red("from: ")+brown(installedfrom)+bold("]")
                        stratomscounter = str(atomscounter)
                        while len(stratomscounter) < len(totalatoms):
                            stratomscounter = " "+stratomscounter
                        print_info("   # "+red("(")+bold(stratomscounter)+"/"+blue(str(totalatoms))+red(")")+repositoryInfo+" "+blue(rematom))
                
                    if (ask):
                        rc = entropyTools.askquestion("     Would you like to add these packages to the removal queue?")
                        if rc != "No":
                            print_info(red(" @@ ")+blue("Removal Queue updated."))
                            for x in choosenRemovalQueue:
                                removalQueue.append(x)
                    else:
                        for x in choosenRemovalQueue:
                            removalQueue.append(x)
                else:
                    writechar("\n")
        if (ask):
            if (deps):
                rc = entropyTools.askquestion("     I am going to start the removal. Are you sure?")
                if rc == "No":
                    clientDbconn.closeDB()
                    return 0,0
        else:
            if (deps):
                entropyTools.countdown(what = red(" @@ ")+blue("Starting removal in "),back = True)
    
        for idpackage in plainRemovalQueue:
            removalQueue.append(idpackage)

        # clear old resume information
        dumpTools.dumpobj(etpCache['remove'],{})
        # store resume information
        resume_cache = {}
        resume_cache['removalQueue'] = removalQueue[:]
        dumpTools.dumpobj(etpCache['remove'],resume_cache)

    else: # if resume, load cache if possible
        
        # check if there's something to resume
        resume_cache = dumpTools.loadobj(etpCache['remove'])
        if not resume_cache: # None or {}
            print_error(red("Nothing to resume."))
            return 128,-1
        else:
            try:
                removalQueue = resume_cache['removalQueue'][:]
                print_warning(red("Resuming previous operations..."))
            except:
                print_error(red("Resume cache corrupted."))
                dumpTools.dumpobj(etpCache['remove'],{})
                return 128,-1
        # validate removalQueue
        invalid = []
        for idpackage in removalQueue:
            try:
                clientDbconn.retrieveAtom(idpackage)
            except TypeError:
                invalid.append(idpackage)
        removalQueue = [x for x in removalQueue if x not in invalid]

    currentqueue = 0
    for idpackage in removalQueue:
        currentqueue += 1
	infoDict = {}
	infoDict['removeidpackage'] = idpackage
	infoDict['removeatom'] = clientDbconn.retrieveAtom(idpackage)
	infoDict['removecontent'] = clientDbconn.retrieveContent(idpackage)
	infoDict['diffremoval'] = False
	infoDict['removeconfig'] = configFiles
	etpRemovalTriggers[infoDict['removeatom']] = clientDbconn.getPackageData(idpackage)
	etpRemovalTriggers[infoDict['removeatom']]['removecontent'] = infoDict['removecontent'].copy()
	etpRemovalTriggers[infoDict['removeatom']]['trigger'] = clientDbconn.retrieveTrigger(idpackage)
	steps = []
	steps.append("preremove")
	steps.append("remove")
	steps.append("postremove")
	for step in steps:
	    rc = equoTools.stepExecutor(step,infoDict,str(currentqueue)+"/"+str(len(removalQueue)))
	    if (rc != 0):
		clientDbconn.closeDB()
		return -1,rc
        
        # update resume cache
        resume_cache['removalQueue'].remove(idpackage)
        dumpTools.dumpobj(etpCache['remove'],resume_cache)
    
    print_info(red(" @@ ")+blue("All done."))
    
    clientDbconn.closeDB()
    return 0,0


def dependenciesTest(quiet = False, ask = False, pretend = False, clientDbconn = None, reagent = False):
    
    if (not quiet):
        print_info(red(" @@ ")+blue("Running dependency test..."))
    
    closedb = True
    if clientDbconn == None:
        closedb = False
        clientDbconn = openClientDatabase()
    # get all the installed packages
    installedPackages = clientDbconn.listAllIdpackages()
    
    depsNotFound = {}
    depsNotSatisfied = {}
    # now look
    length = str((len(installedPackages)))
    count = 0
    for xidpackage in installedPackages:
	count += 1
	atom = clientDbconn.retrieveAtom(xidpackage)
	if (not quiet):
	    print_info(darkred(" @@ ")+bold("(")+blue(str(count))+"/"+red(length)+bold(")")+darkgreen(" Checking ")+bold(atom), back = True)
        
        xdeps = equoTools.getDependencies((xidpackage,0))
        needed_deps = set()
        for xdep in xdeps:
            if xdep[0] == "!": # filter conflicts
                continue
            xmatch = clientDbconn.atomMatch(xdep)
            if xmatch[0] == -1:
                needed_deps.add(xdep)
        
        if needed_deps:
            depsNotSatisfied[xidpackage] = set()
            depsNotSatisfied[xidpackage].update(needed_deps)

    packagesNeeded = set()
    if (depsNotSatisfied):
        if (not quiet):
            print_info(red(" @@ ")+blue("These are the packages that lack dependencies: "))
	for xidpackage in depsNotSatisfied:
	    pkgatom = clientDbconn.retrieveAtom(xidpackage)
	    if (not quiet):
	        print_info(darkred("   ### ")+blue(pkgatom))
	    for dep in depsNotSatisfied[xidpackage]:
                if reagent:
                    match = clientDbconn.atomMatch(dep)
                else:
                    match = equoTools.atomMatch(dep)
                if match[0] == -1:
                    # FIXME
                    if (not quiet):
                        print_info(bold("       :x: NOT FOUND ")+red(dep))
                    else:
                        print dep,"--"
                    continue
		iddep = match[0]
		repo = match[1]
		dbconn = openRepositoryDatabase(repo)
		depatom = dbconn.retrieveAtom(iddep)
		dbconn.closeDB()
		if (not quiet):
		    print_info(bold("       :o: ")+red(depatom))
		else:
		    print pkgatom+" -> "+depatom
		packagesNeeded.add((depatom,dep))

    if (pretend):
	clientDbconn.closeDB()
	return 0, packagesNeeded

    if (packagesNeeded) and (not quiet) and (not reagent):
        if (ask):
            rc = entropyTools.askquestion("     Would you like to install the available packages?")
            if rc == "No":
		clientDbconn.closeDB()
	        return 0,packagesNeeded
	else:
	    print_info(red(" @@ ")+blue("Installing available packages in ")+red("10 seconds")+blue("..."))
	    import time
	    time.sleep(10)
	
        # organize
        packages = set([x[0] for x in packagesNeeded])
	
	entropyTools.applicationLockCheck("install")
	installPackages(packages, deps = False, ask = ask)

    print_info(red(" @@ ")+blue("All done."))
    if closedb:
        clientDbconn.closeDB()
    return 0,packagesNeeded
