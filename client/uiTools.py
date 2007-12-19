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
    equoRequestDeps = True
    equoRequestEmptyDeps = False
    equoRequestOnlyFetch = False
    equoRequestDeep = False
    equoRequestConfigFiles = False
    equoRequestReplay = False
    equoRequestUpgrade = False
    equoRequestResume = False
    equoRequestSkipfirst = False
    equoRequestUpgradeTo = None
    equoRequestListfiles = False
    rc = 0
    _myopts = []
    mytbz2paths = []
    for opt in myopts:
	if (opt == "--nodeps"):
	    equoRequestDeps = False
	elif (opt == "--empty"):
	    equoRequestEmptyDeps = True
	elif (opt == "--fetch"):
	    equoRequestOnlyFetch = True
	elif (opt == "--deep"):
	    equoRequestDeep = True
	elif (opt == "--listfiles"):
	    equoRequestListfiles = True
	elif (opt == "--configfiles"):
	    equoRequestConfigFiles = True
	elif (opt == "--replay"):
	    equoRequestReplay = True
	elif (opt == "--upgrade"):
	    equoRequestUpgrade = True
	elif (opt == "--resume"):
	    equoRequestResume = True
	elif (opt == "--skipfirst"):
	    equoRequestSkipfirst = True
	else:
	    if opt.startswith("--"):
		continue
            if (equoRequestUpgrade):
                equoRequestUpgradeTo = opt
	    elif opt.endswith(".tbz2") and os.access(opt,os.R_OK) and entropyTools.isEntropyTbz2(opt):
		mytbz2paths.append(opt)
	    else:
	        _myopts.append(opt)
    myopts = _myopts

    if (options[0] == "deptest"):
	rc, garbage = dependenciesTest()

    elif (options[0] == "libtest"):
	rc, garbage = librariesTest(listfiles = equoRequestListfiles)

    elif (options[0] == "install"):
	if (myopts) or (mytbz2paths) or (equoRequestResume):
	    equoTools.loadCaches()
	    rc, status = installPackages(myopts, deps = equoRequestDeps, emptydeps = equoRequestEmptyDeps, onlyfetch = equoRequestOnlyFetch, deepdeps = equoRequestDeep, configFiles = equoRequestConfigFiles, tbz2 = mytbz2paths, resume = equoRequestResume, skipfirst = equoRequestSkipfirst)
	else:
	    print_error(red(" Nothing to do."))
	    rc = 127

    elif (options[0] == "world"):
	equoTools.loadCaches()
	rc, status = worldUpdate(onlyfetch = equoRequestOnlyFetch, replay = (equoRequestReplay or equoRequestEmptyDeps), upgradeTo = equoRequestUpgradeTo, resume = equoRequestResume, skipfirst = equoRequestSkipfirst, human = True)

    elif (options[0] == "remove"):
	if myopts or equoRequestResume:
	    equoTools.loadCaches()
	    rc, status = removePackages(myopts, deps = equoRequestDeps, deep = equoRequestDeep, configFiles = equoRequestConfigFiles, resume = equoRequestResume)
	else:
	    print_error(red(" Nothing to do."))
	    rc = 127
    else:
        rc = -10

    return rc


def worldUpdate(onlyfetch = False, replay = False, upgradeTo = None, resume = False, skipfirst = False, returnQueue = False, human = False):

    # check if I am root
    if (not entropyTools.isRoot()):
        if not (etpUi['quiet'] or returnQueue): print_warning(red("Running with ")+bold("--pretend")+red("..."))
	etpUi['pretend'] = True

    try:
        clientDbconn = openClientDatabase()
    except:
        if not (etpUi['quiet'] or returnQueue): print_error(red("You do not have a client database."))
        return 128,-1

    if not resume:

        # verify selected release (branch)
        if (upgradeTo):
            availbranches = listAllAvailableBranches()
            if (upgradeTo not in availbranches) or (upgradeTo == None):
                if not (etpUi['quiet'] or returnQueue): print_error(red("Selected release: ")+bold(str(upgradeTo))+red(" is not available."))
                return 1,-2
            else:
                branches = (upgradeTo,)
        else:
            branches = (etpConst['branch'],)
        
        if (not etpUi['pretend']) and (upgradeTo):
            # update configuration
            entropyTools.writeNewBranch(upgradeTo)
        
        updateList = set()
        fineList = set()
        removedList = set()
        # get all the installed packages
        packages = clientDbconn.listAllPackages()
        
        if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Calculating world packages..."))
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
                del adbconn
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
                    del mdbconn
                    updateList.add((matchatom,matchresults))
                else:
                    removedList.add(idpackage)
                    # look for packages that would match key with any slot (for eg, gcc updates), slot changes handling
                    matchresults = equoTools.atomMatch(atomkey, matchBranches = branches)
                    if matchresults[0] != -1:
                        mdbconn = openRepositoryDatabase(matchresults[1])
                        matchatom = mdbconn.retrieveAtom(matchresults[0])
                        mdbconn.closeDB()
                        del mdbconn
                        # compare versions
                        unsatisfied, satisfied = equoTools.filterSatisfiedDependencies((matchatom,))
                        if unsatisfied:
                            updateList.add((matchatom,matchresults))
            else:
                fineList.add(idpackage)
    
        if (etpUi['verbose'] or etpUi['pretend']):
            print_info(red(" @@ ")+darkgreen("Packages matching update:\t\t")+bold(str(len(updateList))))
            print_info(red(" @@ ")+darkred("Packages matching not available:\t\t")+bold(str(len(removedList))))
            print_info(red(" @@ ")+blue("Packages matching already up to date:\t")+bold(str(len(fineList))))
    
        # clear old resume information
        dumpTools.dumpobj(etpCache['world'],{})
        dumpTools.dumpobj(etpCache['install'],{})
        dumpTools.dumpobj(etpCache['remove'],[])
        if (not etpUi['pretend']):
            # store resume information
            resume_cache = {}
            resume_cache['ask'] = etpUi['ask']
            resume_cache['verbose'] = etpUi['verbose']
            resume_cache['onlyfetch'] = onlyfetch
            resume_cache['removedList'] = removedList
            dumpTools.dumpobj(etpCache['world'],resume_cache)

    else: # if resume, load cache if possible
        
        # check if there's something to resume
        resume_cache = dumpTools.loadobj(etpCache['world'])
        if not resume_cache: # None or {}
            if not (etpUi['quiet'] or returnQueue): print_error(red("Nothing to resume."))
            return 128,-1
        else:
            try:
                updateList = []
                removedList = resume_cache['removedList'].copy()
                etpUi['ask'] = resume_cache['ask']
                etpUi['verbose'] = resume_cache['verbose']
                onlyfetch = resume_cache['onlyfetch']
                # save removal stuff into etpCache['remove']
                dumpTools.dumpobj(etpCache['remove'],list(removedList))
            except:
                if not (etpUi['quiet'] or returnQueue): print_error(red("Resume cache corrupted."))
                dumpTools.dumpobj(etpCache['world'],{})
                dumpTools.dumpobj(etpCache['install'],{})
                dumpTools.dumpobj(etpCache['remove'],[])
                return 128,-1

    # disable collisions protection, better
    oldcollprotect = etpConst['collisionprotect']
    etpConst['collisionprotect'] = 0

    worldQueue = {}
    worldQueue['installPackages'] = {}
    worldQueue['removePackages'] = {}

    if (updateList) or (resume):
        worldQueue['installPackages'], rc = installPackages(atomsdata = updateList, onlyfetch = onlyfetch, resume = resume, skipfirst = skipfirst, returnQueue = returnQueue)
	if rc != 0:
	    return 1,rc
    else:
	if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Nothing to update."))

    etpConst['collisionprotect'] = oldcollprotect
    
    # verify that client database idpackage still exist, validate here before passing removePackage() wrong info
    removedList = [x for x in removedList if clientDbconn.isIDPackageAvailable(x)]
    
    if (removedList):
	removedList = list(removedList)
	removedList.sort()
	if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("On the system there are packages that are not available anymore in the online repositories."))
	if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Even if they are usually harmless, it is suggested to remove them."))
	
	if (not etpUi['pretend']):
            if human:
                rc = entropyTools.askquestion("     Would you like to query them ?")
                if rc == "No":
                    clientDbconn.closeDB()
                    del clientDbconn
                    return 0,0
	
	    # run removePackages with --nodeps
	    worldQueue['removePackages'], rc = removePackages(atomsdata = removedList, deps = False, systemPackagesCheck = False, configFiles = True, resume = resume, returnQueue = returnQueue, human = human)
	else:
	    if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Calculation complete."))

    else:
	if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Nothing to remove."))

    clientDbconn.closeDB()
    del clientDbconn
    
    if returnQueue:
        return worldQueue,0
    
    return 0,0

def installPackages(packages = [], atomsdata = [], deps = True, emptydeps = False, onlyfetch = False, deepdeps = False, configFiles = False, tbz2 = [], resume = False, skipfirst = False, returnQueue = False):

    # check if I am root
    if (not entropyTools.isRoot()):
        if not (etpUi['quiet'] or returnQueue): print_warning(red("Running with ")+bold("--pretend")+red("..."))
	etpUi['pretend'] = True

    dirsCleanup = set()
    def dirscleanup():
        for x in dirsCleanup:
            try:
                if os.path.isdir(x): shutil.rmtree(x)
            except:
                pass

    try:
        clientDbconn = openClientDatabase()
    except:
        if not (etpUi['quiet'] or returnQueue): print_error(red("You do not have a client database."))
        return 128,-1

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
                        if not (etpUi['quiet'] or returnQueue): print_warning(red("## ATTENTION:")+bold(" "+basefile+" ")+red(" is not a valid Entropy package. Skipping..."))
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
                    # put at top priority, shift others
                    myrepo_order = set([(x[0]+1,x[1]) for x in etpRepositoriesOrder])
                    etpRepositoriesOrder.clear()
                    etpRepositoriesOrder.update(myrepo_order)
                    etpRepositoriesOrder.add((1,basefile))
                    mydbconn = openGenericDatabase(dbfile)
                    # read all idpackages
                    try:
                        myidpackages = mydbconn.listAllIdpackages() # all branches admitted from external files
                    except:
                        if not (etpUi['quiet'] or returnQueue): print_warning(red("## ATTENTION:")+bold(" "+basefile+" ")+red(" is not a valid Entropy package. Skipping..."))
                        del etpRepositories[basefile]
                        if returnQueue:
                            raise
                        continue
                    if len(myidpackages) > 1:
                        etpRepositories[basefile]['smartpackage'] = True
                    for myidpackage in myidpackages:
                        foundAtoms.append([pkg,(int(myidpackage),basefile)])
                    mydbconn.closeDB()
                    del mydbconn

        # filter packages not found
        _foundAtoms = []
        for result in foundAtoms:
            exitcode = result[1][0]
            if (exitcode != -1):
                _foundAtoms.append(result[1])
            else:
                if not (etpUi['quiet'] or returnQueue): print_warning(bold("!!!")+red(" No match for ")+bold(result[0])+red(" in database. If you omitted the category, try adding it."))
                if not (etpUi['quiet'] or returnQueue): print_warning(red("    Also, if package is masked, you need to unmask it. See ")+bold(etpConst['confdir']+"/packages/*")+red(" files for help."))

        foundAtoms = _foundAtoms

        # are there packages in foundAtoms?
        if (not foundAtoms):
            if not (etpUi['quiet'] or returnQueue): print_error(red("No packages found"))
            dirscleanup()
            return 127,-1

        if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
            # now print the selected packages
            if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("These are the chosen packages:"))
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
                pkginstalled = clientDbconn.atomMatch(entropyTools.dep_getkey(pkgatom), matchSlot = pkgslot)
                if (pkginstalled[1] == 0):
                    # found
                    idx = pkginstalled[0]
                    installedVer = clientDbconn.retrieveVersion(idx)
                    installedTag = clientDbconn.retrieveVersionTag(idx)
                    if not installedTag:
                        installedTag = "NoTag"
                    installedRev = clientDbconn.retrieveRevision(idx)
    
                if not (etpUi['quiet'] or returnQueue): print_info("   # "+red("(")+bold(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+bold(pkgatom)+" >>> "+red(etpRepositories[reponame]['description']))
                if not (etpUi['quiet'] or returnQueue): print_info("\t"+red("Versioning:\t")+" "+blue(installedVer)+" / "+blue(installedTag)+" / "+blue(str(installedRev))+bold(" ===> ")+darkgreen(pkgver)+" / "+darkgreen(pkgtag)+" / "+darkgreen(str(pkgrev)))
                # tell wether we should update it
                if installedVer == "Not installed":
                    installedVer = "0"
                if installedRev == "NoRev":
                    installedRev = 0
                pkgcmp = entropyTools.entropyCompareVersions((pkgver,pkgtag,pkgrev),(installedVer,installedTag,installedRev))
                if (pkgcmp == 0):
                    action = darkgreen("Reinstall")
                elif (pkgcmp > 0):
                    if (installedVer == "0"):
                        action = darkgreen("Install")
                    else:
                        action = blue("Upgrade")
                else:
                    action = red("Downgrade")
                if not (etpUi['quiet'] or returnQueue): print_info("\t"+red("Action:\t\t")+" "+action)
            
                dbconn.closeDB()
                del dbconn
    
            if (etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']):
                if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Number of packages: ")+str(totalatoms))
        
            if (deps):
                if (etpUi['ask']):
                    rc = entropyTools.askquestion("     Would you like to continue with dependencies calculation ?")
                    if rc == "No":
                        dirscleanup()
                        return 0,0
    
        runQueue = []
        removalQueue = [] # aka, conflicts
        if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Calculating dependencies..."))

        if (deps):
            spinning = False
            if not (etpUi['quiet'] or returnQueue): spinning = True
            treepackages, result = equoTools.getRequiredPackages(foundAtoms, emptydeps, deepdeps, spinning = spinning)
            # add dependencies, explode them
            
            if (result == -2):
                if not (etpUi['quiet'] or returnQueue): print_error(red(" @@ ")+blue("Cannot find needed dependencies: ")+str(treepackages))
                crying_atoms = set()
                for atom in treepackages:
                    for repo in etpRepositories:
                        rdbconn = openRepositoryDatabase(repo)
                        riddep = rdbconn.searchDependency(atom)
                        if riddep != -1:
                            ridpackages = rdbconn.searchIdpackageFromIddependency(riddep)
                            for i in ridpackages:
                                iatom = rdbconn.retrieveAtom(i)
                                crying_atoms.add((iatom,repo))
                        rdbconn.closeDB()
                        del rdbconn
                if crying_atoms:
                    if not (etpUi['quiet'] or returnQueue): print_error(red(" @@ ")+blue("Dependency found and probably needed by:"))
                    for crying_atomdata in crying_atoms:
                        if not (etpUi['quiet'] or returnQueue): print_error(red("     # ")+" [from:"+crying_atomdata[1]+"] "+darkred(crying_atomdata[0]))

                dirscleanup()
                return 130, -1
            
            elif (result == -1): # no database connection
                if not (etpUi['quiet'] or returnQueue): print_error(red(" @@ ")+blue("Cannot find the Installed Packages Database. It's needed to accomplish dependency resolving. Try to run ")+bold("equo database generate"))
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
        
        if ((not runQueue) and (not removalQueue)):
            if not (etpUi['quiet'] or returnQueue): print_error(red("Nothing to do."))
            dirscleanup()
            return 126,-1

        if (runQueue):
            if (etpUi['ask'] or etpUi['pretend']):
                if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("These are the packages that would be ")+bold("merged:"))
            
            count = 0
            atomlen = len(runQueue)
            for packageInfo in runQueue:
                count += 1
                
                if not (etpUi['quiet'] or returnQueue):
                    if not (etpUi['ask'] or etpUi['pretend']): print_info(":: Collecting data: "+str(round((float(count)/atomlen)*100,1))+"% ::", back = True)
                dbconn = openRepositoryDatabase(packageInfo[1])
                mydata = dbconn.getBaseData(packageInfo[0])
                pkgatom = mydata[0]
                pkgver = mydata[2]
                pkgtag = mydata[3]
                pkgrev = mydata[18]
                pkgslot = mydata[14]
                pkgfile = mydata[12]

                onDiskUsedSize += dbconn.retrieveOnDiskSize(packageInfo[0]) # still new
                
                # fill action queue
                actionQueue[pkgatom] = {}
                actionQueue[pkgatom]['removeidpackage'] = -1
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
                pkginstalled = clientDbconn.atomMatch(entropyTools.dep_getkey(pkgatom), matchSlot = pkgslot)
                if (pkginstalled[1] == 0):
                    # found
                    idx = pkginstalled[0]
                    installedVer = clientDbconn.retrieveVersion(idx)
                    installedTag = clientDbconn.retrieveVersionTag(idx)
                    installedRev = clientDbconn.retrieveRevision(idx)
                    actionQueue[pkgatom]['removeidpackage'] = idx
                    onDiskFreedSize += clientDbconn.retrieveOnDiskSize(idx)
    
                if not (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
                    continue
    
                action = 0
                flags = " ["
                pkgcmp = entropyTools.entropyCompareVersions((pkgver,pkgtag,pkgrev),(installedVer,installedTag,installedRev))
                if (pkgcmp == 0):
                    pkgsToReinstall += 1
                    actionQueue[pkgatom]['removeidpackage'] = -1 # disable removal, not needed
                    flags += red("R")
                    action = 1
                elif (pkgcmp > 0):
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
    
                if not (etpUi['quiet'] or returnQueue): print_info(darkred(" ##")+flags+repoinfo+enlightenatom(str(pkgatom))+"/"+str(pkgrev)+oldinfo)
                dbconn.closeDB()
                del dbconn
    
        if (removalQueue):
            
            # filter out packages that are in actionQueue comparing key + slot
            if runQueue:
                myremmatch = {}
                [myremmatch.update({(entropyTools.dep_getkey(clientDbconn.retrieveAtom(x)),clientDbconn.retrieveSlot(x)): x}) for x in removalQueue]
                for packageInfo in runQueue:
                    dbconn = openRepositoryDatabase(packageInfo[1])
                    testtuple = (entropyTools.dep_getkey(dbconn.retrieveAtom(packageInfo[0])),dbconn.retrieveSlot(packageInfo[0]))
                    if testtuple in myremmatch:
                        # remove from removalQueue
                        if myremmatch[testtuple] in removalQueue:
                            removalQueue.remove(myremmatch[testtuple])
                    del testtuple
                del myremmatch
            
            '''
            
            FIXME: it's broken, on equo world it pulls in depends that shouldn't be removed
            fix, or remove and forget
            
            # add depends to removalQueue that are not in runQueue
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
                        del matchdbconn
                        if (matchatom not in actionQueue) and (depend not in removalQueue): # if the atom hasn't been pulled in, we need to remove depend
                            # check if the atom is already up to date
                            mymatch = equoTools.atomMatch(matchatom)
                            print mymatch
                            #print matchatom
                            dependQueue.add(depend)

            for depend in dependQueue:
                removalQueue.append(depend)
            '''
            
            if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
                if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("These are the packages that would be ")+bold("removed")+blue(" (conflicting/substituted):"))
    
                for idpackage in removalQueue:
                    pkgatom = clientDbconn.retrieveAtom(idpackage)
                    onDiskFreedSize += clientDbconn.retrieveOnDiskSize(idpackage)
                    installedfrom = clientDbconn.retrievePackageFromInstalledTable(idpackage)
                    repoinfo = red("[")+brown("from: ")+bold(installedfrom)+red("] ")
                    if not (etpUi['quiet'] or returnQueue): print_info(red("   ## ")+"["+red("W")+"] "+repoinfo+enlightenatom(pkgatom))
        
        if (runQueue) or (removalQueue):
            # show download info
            if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Packages needing install:\t")+red(str(len(runQueue))))
            if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Packages needing removal:\t")+red(str(pkgsToRemove)))
            if (etpUi['ask'] or etpUi['verbose'] or etpUi['pretend']):
                if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+darkgreen("Packages needing install:\t")+darkgreen(str(pkgsToInstall)))
                if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+darkgreen("Packages needing reinstall:\t")+darkgreen(str(pkgsToReinstall)))
                if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Packages needing update:\t\t")+blue(str(pkgsToUpdate)))
                if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+red("Packages needing downgrade:\t")+red(str(pkgsToDowngrade)))
            if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Download size:\t\t\t")+bold(str(entropyTools.bytesIntoHuman(downloadSize))))
            deltaSize = onDiskUsedSize - onDiskFreedSize
            if (deltaSize > 0):
                if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Used disk space:\t\t\t")+bold(str(entropyTools.bytesIntoHuman(deltaSize))))
            else:
                if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Freed disk space:\t\t")+bold(str(entropyTools.bytesIntoHuman(abs(deltaSize)))))
    
        if (etpUi['ask']):
            rc = entropyTools.askquestion("     Would you like to run the queue ?")
            if rc == "No":
                dirscleanup()
                return 0,0
        if (etpUi['pretend']):
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
            if not (etpUi['quiet'] or returnQueue): print_error(red("Nothing to resume."))
            return 128,-1
        else:
            try:
                removalQueue = resume_cache['removalQueue'][:]
                runQueue = resume_cache['runQueue'][:]
                actionQueue = resume_cache['actionQueue'].copy()
                onlyfetch = resume_cache['onlyfetch']
                if not (etpUi['quiet'] or returnQueue): print_warning(red("Resuming previous operations..."))
            except:
                if not (etpUi['quiet'] or returnQueue): print_error(red("Resume cache corrupted."))
                dumpTools.dumpobj(etpCache['install'],{})
                return 128,-1
            if skipfirst:
                if runQueue:
                    # regenerate removalQueue
                    runQueue = runQueue[1:]
                    rconflicts_match = set()
                    # now look for the rest
                    for item in runQueue:
                        rdbconn = openRepositoryDatabase(item[1])
                        rconflicts = rdbconn.retrieveConflicts(item[0])
                        rdbconn.closeDB()
                        del rdbconn
                        for rconflict in rconflicts:
                            rmatch = clientDbconn.atomMatch(rconflict)
                            if rmatch[0] != -1:
                                rconflicts_match.add(rmatch[0])
                    removalQueue = [x for x in rconflicts_match]
                    del rconflicts_match
                    # save new queues
                    resume_cache['runQueue'] = runQueue[:]
                    resume_cache['removalQueue'] = removalQueue[:]
                    dumpTools.dumpobj(etpCache['install'],resume_cache)
                    

    if returnQueue:
        # prepare return dictionary
        returnActionQueue = {}
        returnActionQueue['etpRepositories'] = etpRepositories.copy()
        returnActionQueue['etpRepositoriesOrder'] = etpRepositoriesOrder.copy()
        returnActionQueue['removalQueue'] = {}
        returnActionQueue['removalQueue']['queue'] = removalQueue[:]
        returnActionQueue['removalQueue']['data'] = {}
        returnActionQueue['runQueue'] = {}
        returnActionQueue['runQueue']['queue'] = runQueue[:]
        returnActionQueue['runQueue']['data'] = {}
        returnActionQueue['extrainfo'] = {}
        try:
            dsize = deltaSize
        except:
            dsize = 0
        returnActionQueue['extrainfo']['deltaSize'] = dsize
        

    # running tasks
    totalqueue = str(len(runQueue))
    totalremovalqueue = str(len(removalQueue))
    currentqueue = 0
    currentremovalqueue = 0
    
    ### Before starting the real install, fetch packages and verify checksum.
    if not returnQueue:
        fetchqueue = 0
        for packageInfo in runQueue:
            
            fetchqueue += 1
            idpackage = packageInfo[0]
            repository = packageInfo[1]
            dbconn = openRepositoryDatabase(repository)
            pkgatom = dbconn.retrieveAtom(idpackage)
            
            infoDict = actionQueue[pkgatom].copy()
            
            infoDict['repository'] = packageInfo[1]
            infoDict['idpackage'] = packageInfo[0]
            infoDict['checksum'] = dbconn.retrieveDigest(idpackage)
            infoDict['download'] = dbconn.retrieveDownloadURL(idpackage)
            
            dbconn.closeDB()
            del dbconn
            
            steps = []
            
            if not repository.endswith(".tbz2"):
                if (actionQueue[pkgatom]['fetch'] < 0):
                    steps.append("fetch")
                steps.append("checksum")
            
            if not (etpUi['quiet'] or returnQueue): print_info(red(" :: ")+bold("(")+blue(str(fetchqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(pkgatom))
            
            for step in steps:
                rc = equoTools.stepExecutor(step,infoDict,str(fetchqueue)+"/"+totalqueue)
                if (rc != 0):
                    clientDbconn.closeDB()
                    del clientDbconn
                    dirscleanup()
                    return -1,rc
            
            # disable fetch now, file fetched
            del infoDict
            
        del fetchqueue
    
    for idpackage in removalQueue:
        currentremovalqueue += 1
	infoDict = {}
	infoDict['removeatom'] = clientDbconn.retrieveAtom(idpackage)
	infoDict['removeidpackage'] = idpackage
	infoDict['diffremoval'] = False
	infoDict['removeconfig'] = True # we need to completely wipe configuration of conflicts
        if not returnQueue: # must be loaded manually
	    infoDict['removecontent'] = clientDbconn.retrieveContent(idpackage)
	    etpRemovalTriggers[infoDict['removeatom']] = clientDbconn.getPackageData(idpackage)
	    etpRemovalTriggers[infoDict['removeatom']]['removecontent'] = infoDict['removecontent'].copy()
	    etpRemovalTriggers[infoDict['removeatom']]['trigger'] = clientDbconn.retrieveTrigger(idpackage)
	steps = []
	steps.append("preremove")
	steps.append("remove")
	steps.append("postremove")
        
        if returnQueue:
            
            returnActionQueue['removalQueue']['data'][idpackage] = {}
            returnActionQueue['removalQueue']['data'][idpackage]['infoDict'] = infoDict.copy()
            returnActionQueue['removalQueue']['data'][idpackage]['steps'] = steps[:]
            
        else:
        
            if not (etpUi['quiet'] or returnQueue): print_info(red(" -- ")+bold("(")+blue(str(currentremovalqueue))+"/"+red(totalremovalqueue)+bold(") ")+">>> "+darkgreen(infoDict['removeatom']))
        
            for step in steps:
                rc = equoTools.stepExecutor(step,infoDict,str(currentremovalqueue)+"/"+totalremovalqueue)
                if (rc != 0):
                    clientDbconn.closeDB()
                    del clientDbconn
                    dirscleanup()
                    return -1,rc

        # update resume cache
        if not tbz2: # tbz2 caching not supported
            resume_cache['removalQueue'].remove(idpackage)
            dumpTools.dumpobj(etpCache['install'],resume_cache)
        
        # unload dict
        if not returnQueue:
            del etpRemovalTriggers[infoDict['removeatom']]

    for packageInfo in runQueue:
        
	currentqueue += 1
	idpackage = packageInfo[0]
	repository = packageInfo[1]
	# get package atom
	dbconn = openRepositoryDatabase(repository)
	pkgatom = dbconn.retrieveAtom(idpackage)
        
	steps = []
        
	# setup download stuff
        if returnQueue:
            if not repository.endswith(".tbz2"):
                if (actionQueue[pkgatom]['fetch'] < 0):
                    steps.append("fetch")
                steps.append("checksum")

	# differential remove list
	if (actionQueue[pkgatom]['removeidpackage'] != -1):
            # is it still available?
            if clientDbconn.isIDPackageAvailable(actionQueue[pkgatom]['removeidpackage']):
                actionQueue[pkgatom]['diffremoval'] = True
                actionQueue[pkgatom]['removeatom'] = clientDbconn.retrieveAtom(actionQueue[pkgatom]['removeidpackage'])
                if not returnQueue: # must be loaded manually
                    oldcontent = clientDbconn.retrieveContent(actionQueue[pkgatom]['removeidpackage'])
                    newcontent = dbconn.retrieveContent(idpackage)
                    oldcontent.difference_update(newcontent)
                    del newcontent
                    actionQueue[pkgatom]['removecontent'] = oldcontent.copy()
                    etpRemovalTriggers[actionQueue[pkgatom]['removeatom']] = clientDbconn.getPackageData(actionQueue[pkgatom]['removeidpackage'])
                    etpRemovalTriggers[actionQueue[pkgatom]['removeatom']]['removecontent'] = actionQueue[pkgatom]['removecontent'].copy()
                    etpRemovalTriggers[actionQueue[pkgatom]['removeatom']]['trigger'] = clientDbconn.retrieveTrigger(actionQueue[pkgatom]['removeidpackage'])
            else:
                actionQueue[pkgatom]['removeidpackage'] = -1

        if not returnQueue: # must be loaded manually
            actionQueue[pkgatom]['atom'] = pkgatom
            actionQueue[pkgatom]['slot'] = dbconn.retrieveSlot(idpackage)
            actionQueue[pkgatom]['download'] = dbconn.retrieveDownloadURL(idpackage)
            actionQueue[pkgatom]['version'] = dbconn.retrieveVersion(idpackage)
            actionQueue[pkgatom]['category'] = dbconn.retrieveCategory(idpackage)
            actionQueue[pkgatom]['name'] = dbconn.retrieveName(idpackage)
            actionQueue[pkgatom]['repository'] = packageInfo[1]
            actionQueue[pkgatom]['idpackage'] = packageInfo[0]
            
            actionQueue[pkgatom]['messages'] = dbconn.retrieveMessages(idpackage)
            actionQueue[pkgatom]['checksum'] = dbconn.retrieveDigest(idpackage)
            # get data for triggerring tool
            etpInstallTriggers[pkgatom] = dbconn.getPackageData(idpackage)
            etpInstallTriggers[pkgatom]['trigger'] = dbconn.retrieveTrigger(idpackage)

	dbconn.closeDB()
        del dbconn

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
	
	if not (etpUi['quiet'] or returnQueue): print_info(red(" ++ ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(pkgatom))

        if returnQueue:

            returnActionQueue['runQueue']['data'][pkgatom] = {}
            returnActionQueue['runQueue']['data'][pkgatom]['infoDict'] = actionQueue[pkgatom].copy()
            returnActionQueue['runQueue']['data'][pkgatom]['steps'] = steps[:]

        else:

            for step in steps:
                rc = equoTools.stepExecutor(step,actionQueue[pkgatom],str(currentqueue)+"/"+totalqueue)
                if (rc != 0):
                    clientDbconn.closeDB()
                    del clientDbconn
                    dirscleanup()
                    return -1,rc

        # update resume cache
        if not tbz2: # tbz2 caching not supported
            resume_cache['runQueue'].remove(packageInfo)
            dumpTools.dumpobj(etpCache['install'],resume_cache)
        
        # unload dict
        try:
            del etpRemovalTriggers[actionQueue[pkgatom]['removeatom']]
        except:
            pass
        del actionQueue[pkgatom]
        if not returnQueue:
            del etpInstallTriggers[pkgatom]
        


    if (onlyfetch):
	if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Fetch Complete."))
    else:
	if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Install Complete."))

    # clear resume information
    dumpTools.dumpobj(etpCache['install'],{})
    
    clientDbconn.closeDB()
    del clientDbconn
    dirscleanup()
    
    if returnQueue:
        return returnActionQueue,0
    
    return 0,0


def removePackages(packages = [], atomsdata = [], deps = True, deep = False, systemPackagesCheck = True, configFiles = False, resume = False, returnQueue = False, human = False):
    
    # check if I am root
    if (not entropyTools.isRoot()):
        if not (etpUi['quiet'] or returnQueue): print_warning(red("Running with ")+bold("--pretend")+red("..."))
	etpUi['pretend'] = True

    try:
        clientDbconn = openClientDatabase()
    except:
        if not (etpUi['quiet'] or returnQueue): print_error(red("You do not have a client database."))
        return 128,-1

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
                if not (etpUi['quiet'] or returnQueue): print_warning(red("## ATTENTION -> package")+bold(" "+result[0]+" ")+red("is not installed."))
    
        foundAtoms = _foundAtoms
        
        # are packages in foundAtoms?
        if (not foundAtoms):
            if not (etpUi['quiet'] or returnQueue): print_error(red("No packages found"))
            return 125,-1
    
        plainRemovalQueue = []
        
        lookForOrphanedPackages = True
        # now print the selected packages
        if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("These are the chosen packages:"))
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
                        if not (etpUi['quiet'] or returnQueue): print_warning(darkred("   # !!! ")+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+red(" is a vital package. Removal forbidden."))
                        continue
                else:
                    if not (etpUi['quiet'] or returnQueue): print_warning(darkred("   # !!! ")+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+red(" is a vital package. Removal forbidden."))
                    continue
            plainRemovalQueue.append(idpackage)
            
            if not (etpUi['quiet'] or returnQueue): print_info("   # "+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+" | Installed from: "+red(installedfrom))
    
        if (etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']):
            if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Number of packages: ")+str(totalatoms))
        
        
        if (deps):
            question = "     Would you like to look for packages that can be removed along with the selected above?"
        else:
            question = "     Would you like to remove them now?"
            lookForOrphanedPackages = False
    
        if (etpUi['ask']):
            rc = entropyTools.askquestion(question)
            if rc == "No":
                lookForOrphanedPackages = False
                if (not deps):
                    clientDbconn.closeDB()
                    del clientDbconn
                    return 0,0
    
        if (not plainRemovalQueue):
            if not (etpUi['quiet'] or returnQueue): print_error(red("Nothing to do."))
            return 126,-1
    
        removalQueue = []
        
        if (lookForOrphanedPackages):
            choosenRemovalQueue = []
            if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("Calculating..."))
            treeview = equoTools.generateDependsTree(plainRemovalQueue, deep = deep)
            treelength = len(treeview[0])
            if treelength > 1:
                treeview = treeview[0]
                for x in range(treelength)[::-1]:
                    for y in treeview[x]:
                        choosenRemovalQueue.append(y)
            
                if (choosenRemovalQueue):
                    if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("This is the new removal queue:"))
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

                    for x in choosenRemovalQueue:
                        removalQueue.append(x)

                else:
                    if not (etpUi['quiet'] or returnQueue): writechar("\n")
        if (etpUi['ask']) or human:
            question = "     Would you like to proceed?"
            if human:
                question = "     Would you like to proceed with a selective removal ?"
            rc = entropyTools.askquestion(question)
            if rc == "No":
                clientDbconn.closeDB()
                del clientDbconn
                return 0,0
        elif (deps):
            if not (etpUi['quiet'] or returnQueue): entropyTools.countdown(what = red(" @@ ")+blue("Starting removal in "),back = True)

        for idpackage in plainRemovalQueue: # append at the end requested packages if not in queue
            if idpackage not in removalQueue:
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
            if not (etpUi['quiet'] or returnQueue): print_error(red("Nothing to resume."))
            return 128,-1
        else:
            try:
                removalQueue = resume_cache['removalQueue'][:]
                if not (etpUi['quiet'] or returnQueue): print_warning(red("Resuming previous operations..."))
            except:
                if not (etpUi['quiet'] or returnQueue): print_error(red("Resume cache corrupted."))
                dumpTools.dumpobj(etpCache['remove'],{})
                return 128,-1

    # validate removalQueue
    invalid = set()
    for idpackage in removalQueue:
        try:
            clientDbconn.retrieveAtom(idpackage)
        except TypeError:
            invalid.add(idpackage)
    removalQueue = [x for x in removalQueue if x not in invalid]

    if returnQueue:
        returnActionQueue = {}
        returnActionQueue['queue'] = removalQueue[:]
        returnActionQueue['data'] = {}

    totalqueue = str(len(removalQueue))
    currentqueue = 0
    for idpackage in removalQueue:
        currentqueue += 1
	infoDict = {}
	infoDict['removeidpackage'] = idpackage
        try:
            infoDict['removeatom'] = clientDbconn.retrieveAtom(idpackage)
        except TypeError: # resume cache issues?
            try:
                # force database removal and forget about the rest
                if not (etpUi['quiet'] or returnQueue): print "DEBUG: attention! entry broken probably due to a resume cache issue, forcing removal from database"
                clientDbconn.removePackage(idpackage)
                clientDbconn.removePackageFromInstalledTable(idpackage)
            except:
                pass
            # update resume cache
            resume_cache['removalQueue'].remove(idpackage)
            dumpTools.dumpobj(etpCache['remove'],resume_cache)
            continue
        
	infoDict['diffremoval'] = False
	infoDict['removeconfig'] = configFiles

        if not returnQueue: # must be loaded manually
	    infoDict['removecontent'] = clientDbconn.retrieveContent(idpackage)
	    etpRemovalTriggers[infoDict['removeatom']] = clientDbconn.getPackageData(idpackage)
	    etpRemovalTriggers[infoDict['removeatom']]['removecontent'] = infoDict['removecontent'].copy()
	    etpRemovalTriggers[infoDict['removeatom']]['trigger'] = clientDbconn.retrieveTrigger(idpackage)

	steps = []
	steps.append("preremove")
	steps.append("remove")
	steps.append("postremove")
        
        if returnQueue:
            
            returnActionQueue['data'][idpackage] = {}
            returnActionQueue['data'][idpackage]['infoDict'] = infoDict.copy()
            returnActionQueue['data'][idpackage]['steps'] = steps[:]
            
        else:
        
            # if human
            if not (etpUi['quiet'] or returnQueue): print_info(red(" -- ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(infoDict['removeatom']))
            if human:
                rc = entropyTools.askquestion("     Remove this one ?")
                if rc == "No":
                    # update resume cache
                    resume_cache['removalQueue'].remove(idpackage)
                    dumpTools.dumpobj(etpCache['remove'],resume_cache)
                    # unload dict
                    if not returnQueue:
                        del etpRemovalTriggers[infoDict['removeatom']]
                    continue
        
            for step in steps:
                rc = equoTools.stepExecutor(step,infoDict,str(currentqueue)+"/"+str(len(removalQueue)))
                if (rc != 0):
                    clientDbconn.closeDB()
                    del clientDbconn
                    return -1,rc

        # update resume cache
        resume_cache['removalQueue'].remove(idpackage)
        dumpTools.dumpobj(etpCache['remove'],resume_cache)
        
        # unload dict
        if not returnQueue:
            del etpRemovalTriggers[infoDict['removeatom']]

    if not (etpUi['quiet'] or returnQueue): print_info(red(" @@ ")+blue("All done."))
    
    clientDbconn.closeDB()
    del clientDbconn
    
    if returnQueue:
        return returnActionQueue,0
    
    return 0,0


def dependenciesTest(clientDbconn = None, reagent = False):
    
    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("Running dependency test..."))
    
    closedb = True
    if clientDbconn == None:
        closedb = False
        clientDbconn = openClientDatabase()
    # get all the installed packages
    installedPackages = clientDbconn.listAllIdpackages()
    
    depsNotSatisfied = {}
    # now look
    length = str((len(installedPackages)))
    count = 0
    for xidpackage in installedPackages:
	count += 1
	atom = clientDbconn.retrieveAtom(xidpackage)
	if (not etpUi['quiet']):
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
        if (not etpUi['quiet']):
            print_info(red(" @@ ")+blue("These are the packages that lack dependencies: "))
	for xidpackage in depsNotSatisfied:
	    pkgatom = clientDbconn.retrieveAtom(xidpackage)
	    if (not etpUi['quiet']):
	        print_info(darkred("   ### ")+blue(pkgatom))
	    for dep in depsNotSatisfied[xidpackage]:
                if reagent:
                    match = clientDbconn.atomMatch(dep)
                else:
                    match = equoTools.atomMatch(dep)
                if match[0] == -1:
                    # FIXME
                    if (not etpUi['quiet']):
                        print_info(bold("       :x: NOT FOUND ")+red(dep))
                    else:
                        print dep,"--"
                    continue
		iddep = match[0]
		repo = match[1]
		dbconn = openRepositoryDatabase(repo)
		depatom = dbconn.retrieveAtom(iddep)
		dbconn.closeDB()
                del dbconn
		if (not etpUi['quiet']):
		    print_info(bold("       :o: ")+red(depatom))
		else:
		    print pkgatom+" -> "+depatom
		packagesNeeded.add((depatom,dep))

    if (etpUi['pretend']):
	clientDbconn.closeDB()
        del clientDbconn
	return 0, packagesNeeded

    if (packagesNeeded) and (not etpUi['quiet']) and (not reagent):
        if (etpUi['ask']):
            rc = entropyTools.askquestion("     Would you like to install the available packages?")
            if rc == "No":
		clientDbconn.closeDB()
                del clientDbconn
	        return 0,packagesNeeded
	else:
	    print_info(red(" @@ ")+blue("Installing available packages in ")+red("10 seconds")+blue("..."))
	    import time
	    time.sleep(10)
	
        # organize
        packages = set([x[0] for x in packagesNeeded])
	
	entropyTools.applicationLockCheck("install")
	installPackages(packages, deps = False)

    if not etpUi['quiet']: print_info(red(" @@ ")+blue("All done."))
    if closedb:
        clientDbconn.closeDB()
        del clientDbconn
    return 0,packagesNeeded

def librariesTest(clientDbconn = None, reagent = False, listfiles = False):
    
    qstat = etpUi['quiet']
    if listfiles:
        etpUi['quiet'] = True
    
    import sys
    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("Running libraries test..."))
    
    closedb = True
    if clientDbconn == None:
        closedb = False
        clientDbconn = openClientDatabase()

    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("Collecting linker paths..."))
    
    if not etpConst['systemroot']:
        myroot = "/"
    else:
        myroot = etpConst['systemroot']+"/"
    # run ldconfig first
    os.system("ldconfig -r "+myroot+" &> /dev/null")
    # open /etc/ld.so.conf
    if not os.path.isfile(etpConst['systemroot']+"/etc/ld.so.conf"):
        if not etpUi['quiet']:
            print_error(red(" @@ ")+blue("Cannot find ")+red(etpConst['systemroot']+"/etc/ld.so.conf"))
        return 1,-1
    
    ldpaths = entropyTools.collectLinkerPaths()

    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("Collecting executables files..."))

    executables = set()
    total = len(ldpaths)
    count = 0
    for ldpath in ldpaths:
        count += 1
        if not etpUi['quiet']: print_info("  ["+str((round(float(count)/total*100,1)))+"%] "+blue("Tree: ")+red(etpConst['systemroot']+ldpath), back = True)
        ldpath = ldpath.encode(sys.getfilesystemencoding())
        for currentdir,subdirs,files in os.walk(etpConst['systemroot']+ldpath):
            for item in files:
                filepath = currentdir+"/"+item
                if os.access(filepath,os.X_OK):
                    executables.add(filepath[len(etpConst['systemroot']):])

    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("Collecting broken executables..."))
        print_info(red(" @@ Attention: ")+blue("don't worry about libraries that are shown here but not later."))

    brokenlibs = set()
    total = len(executables)
    count = 0
    for executable in executables:
        count += 1
        if not etpUi['quiet']: print_info("  ["+str((round(float(count)/total*100,1)))+"%] "+red(etpConst['systemroot']+executable), back = True)
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
            if not etpUi['quiet']:
                if mylibs:
                    alllibs = blue(' :: ').join(list(mylibs))
                    print_info("  ["+str((round(float(count)/total*100,1)))+"%] "+red(etpConst['systemroot']+executable)+" [ "+alllibs+" ]")
            brokenlibs.update(mylibs)
    del executables
    
    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("Trying to match packages..."))

    packagesMatched = set()
    # now search packages that contain the found libs
    orderedRepos = list(etpRepositoriesOrder)
    orderedRepos.sort()
    for repodata in orderedRepos:
        if not etpUi['quiet']: print_info(red(" @@ ")+blue("Repository: ")+darkgreen(etpRepositories[repodata[1]]['description'])+" ["+red(repodata[1])+"]")
        dbconn = openRepositoryDatabase(repodata[1])
        libsfound = set()
        for lib in brokenlibs:
            packages = dbconn.searchBelongs(file = "%"+lib, like = True, branch = etpConst['branch'])
            if packages:
                for idpackage in packages:
                    # retrieve content and really look if library is in ldpath
                    mycontent = dbconn.retrieveContent(idpackage)
                    matching_libs = [x for x in mycontent if x.endswith(lib) and (os.path.dirname(x) in ldpaths)]
                    libsfound.add(lib)
                    if matching_libs:
                        packagesMatched.add((idpackage,repodata[1],lib))
        brokenlibs.difference_update(libsfound)
        dbconn.closeDB()
        del dbconn

    if listfiles:
        etpUi['quiet'] = qstat
        for x in brokenlibs:
            print x
        return 0,0

    if (not brokenlibs) and (not packagesMatched):
        if not etpUi['quiet']: print_info(red(" @@ ")+blue("System is healthy."))
        return 0,0

    atomsdata = set()
    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("Libraries statistics:"))
        if brokenlibs:
            print_info(brown(" ## ")+red("Not matched:"))
            for lib in brokenlibs:
                print_info(darkred("    => ")+red(lib))
        print_info(darkgreen(" ## ")+red("Matched:"))
        for packagedata in packagesMatched:
            dbconn = openRepositoryDatabase(packagedata[1])
            myatom = dbconn.retrieveAtom(packagedata[0])
            atomsdata.add((myatom,(packagedata[0],packagedata[1])))
            print_info("   "+red(packagedata[2])+" => "+brown(myatom)+" ["+red(packagedata[1])+"]")
            dbconn.closeDB()
            del dbconn
    else:
        for packagedata in packagesMatched:
            dbconn = openRepositoryDatabase(packagedata[1])
            myatom = dbconn.retrieveAtom(packagedata[0])
            atomsdata.add((myatom,(packagedata[0],packagedata[1])))
            print myatom
            dbconn.closeDB()
            del dbconn
        clientDbconn.closeDB()
        del clientDbconn
        return 0,atomsdata

    if (etpUi['pretend']):
	clientDbconn.closeDB()
        del clientDbconn
	return 0,atomsdata

    if (atomsdata) and (not reagent):
        if (etpUi['ask']):
            rc = entropyTools.askquestion("     Would you like to install them?")
            if rc == "No":
		clientDbconn.closeDB()
                del clientDbconn
	        return 0,atomsdata
	else:
	    print_info(red(" @@ ")+blue("Installing found packages in ")+red("10 seconds")+blue("..."))
	    import time
	    time.sleep(10)
        
	entropyTools.applicationLockCheck("install")
        rc = installPackages(atomsdata = list(atomsdata))
        if closedb:
            clientDbconn.closeDB()
            del clientDbconn
        if rc[0] == 0:
            return 0,atomsdata
        else:
            return rc[0],atomsdata

    if closedb:
        clientDbconn.closeDB()
        del clientDbconn
    return 0,atomsdata
