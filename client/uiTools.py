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
import dumpTools
import shutil

import logTools
equoLog = logTools.LogFile(level = etpConst['equologlevel'],filename = etpConst['equologfile'], header = "[Equo]")
Equo = equoTools.EquoInterface()

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
    equoRequestChecksum = True
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
        elif (opt == "--nochecksum"):
            equoRequestChecksum = False
        elif (opt == "--skipfirst"):
            equoRequestSkipfirst = True
        else:
            if opt.startswith("--"):
                continue
            if (equoRequestUpgrade):
                equoRequestUpgradeTo = opt
            elif opt.endswith(".tbz2") and os.access(opt,os.R_OK) and Equo.entropyTools.isEntropyTbz2(opt):
                mytbz2paths.append(opt)
            else:
                _myopts.append(opt)
    myopts = _myopts

    if (options[0] == "deptest"):
        Equo.load_cache()
        rc, garbage = dependenciesTest()
        Equo.save_cache()

    elif (options[0] == "libtest"):
        rc, garbage = librariesTest(listfiles = equoRequestListfiles)

    elif (options[0] == "install"):
        if (myopts) or (mytbz2paths) or (equoRequestResume):
            Equo.load_cache()
            rc, status = installPackages(myopts, deps = equoRequestDeps, emptydeps = equoRequestEmptyDeps, onlyfetch = equoRequestOnlyFetch, deepdeps = equoRequestDeep, configFiles = equoRequestConfigFiles, tbz2 = mytbz2paths, resume = equoRequestResume, skipfirst = equoRequestSkipfirst, dochecksum = equoRequestChecksum)
            Equo.save_cache()
        else:
            print_error(red(" Nothing to do."))
            rc = 127

    elif (options[0] == "world"):
        Equo.load_cache()
        rc, status = worldUpdate(onlyfetch = equoRequestOnlyFetch, replay = (equoRequestReplay or equoRequestEmptyDeps), upgradeTo = equoRequestUpgradeTo, resume = equoRequestResume, skipfirst = equoRequestSkipfirst, human = True, dochecksum = equoRequestChecksum)
        Equo.save_cache()

    elif (options[0] == "remove"):
        if myopts or equoRequestResume:
            Equo.load_cache()
            rc, status = removePackages(myopts, deps = equoRequestDeps, deep = equoRequestDeep, configFiles = equoRequestConfigFiles, resume = equoRequestResume)
            Equo.save_cache()
        else:
            print_error(red(" Nothing to do."))
            rc = 127
    else:
        rc = -10

    return rc


def worldUpdate(onlyfetch = False, replay = False, upgradeTo = None, resume = False, skipfirst = False, human = False, dochecksum = True):

    # check if I am root
    if (not Equo.entropyTools.isRoot()):
        if not (etpUi['quiet']): print_warning(red("Running with ")+bold("--pretend")+red("..."))
        etpUi['pretend'] = True

    if not resume:

        # verify selected release (branch)
        if (upgradeTo):
            availbranches = Equo.listAllAvailableBranches()
            if (upgradeTo not in availbranches) or (upgradeTo == None):
                if not (etpUi['quiet']): print_error(red("Selected release: ")+bold(str(upgradeTo))+red(" is not available."))
                return 1,-2
            else:
                branch = upgradeTo
        else:
            branch = etpConst['branch']

        if (not etpUi['pretend']) and (upgradeTo):
            # update configuration
            Equo.entropyTools.writeNewBranch(upgradeTo)

        if not (etpUi['quiet']): print_info(red(" @@ ")+blue("Calculating world packages..."))
        update, remove, fine = Equo.calculate_world_updates(empty_deps = replay, branch = branch)

        if (etpUi['verbose'] or etpUi['pretend']):
            print_info(red(" @@ ")+darkgreen("Packages matching update:\t\t")+bold(str(len(update))))
            print_info(red(" @@ ")+darkred("Packages matching not available:\t\t")+bold(str(len(remove))))
            print_info(red(" @@ ")+blue("Packages matching already up to date:\t")+bold(str(len(fine))))

        del fine

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
            resume_cache['remove'] = remove
            dumpTools.dumpobj(etpCache['world'],resume_cache)

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = dumpTools.loadobj(etpCache['world'])
        if not resume_cache: # None or {}
            if not (etpUi['quiet']): print_error(red("Nothing to resume."))
            return 128,-1
        else:
            try:
                update = []
                remove = resume_cache['removed'].copy()
                etpUi['ask'] = resume_cache['ask']
                etpUi['verbose'] = resume_cache['verbose']
                onlyfetch = resume_cache['onlyfetch']
                dumpTools.dumpobj(etpCache['remove'],list(remove))
            except:
                if not (etpUi['quiet']): print_error(red("Resume cache corrupted."))
                dumpTools.dumpobj(etpCache['world'],{})
                dumpTools.dumpobj(etpCache['install'],{})
                dumpTools.dumpobj(etpCache['remove'],[])
                return 128,-1

    # disable collisions protection, better
    oldcollprotect = etpConst['collisionprotect']
    etpConst['collisionprotect'] = 0

    if (update) or (resume):
        rc = installPackages(atomsdata = update, onlyfetch = onlyfetch, resume = resume, skipfirst = skipfirst, dochecksum = dochecksum)
        if rc[1] != 0:
            return 1,rc[0]
    else:
        if not etpUi['quiet']: print_info(red(" @@ ")+blue("Nothing to update."))

    etpConst['collisionprotect'] = oldcollprotect

    # verify that client database idpackage still exist, validate here before passing removePackage() wrong info
    remove = [x for x in remove if Equo.clientDbconn.isIDPackageAvailable(x)]

    if (remove):
        remove = list(remove)
        remove.sort()
        if not (etpUi['quiet']): print_info(red(" @@ ")+blue("On the system there are packages that are not available anymore in the online repositories."))
        if not (etpUi['quiet']): print_info(red(" @@ ")+blue("Even if they are usually harmless, it is suggested to remove them."))

        if (not etpUi['pretend']):
            if human:
                rc = Equo.entropyTools.askquestion("     Would you like to query them ?")
                if rc == "No":
                    return 0,0

            # run removePackages with --nodeps
            removePackages(atomsdata = remove, deps = False, systemPackagesCheck = False, configFiles = True, resume = resume, human = human)
        else:
            if not etpUi['quiet']: print_info(red(" @@ ")+blue("Calculation complete."))

    else:
        if not etpUi['quiet']: print_info(red(" @@ ")+blue("Nothing to remove."))

    return 0,0

def installPackages(packages = [], atomsdata = [], deps = True, emptydeps = False, onlyfetch = False, deepdeps = False, configFiles = False, tbz2 = [], resume = False, skipfirst = False, dochecksum = True):

    # check if I am root
    if (not Equo.entropyTools.isRoot()):
        if not etpUi['quiet']: print_warning(red("Running with ")+bold("--pretend")+red("..."))
        etpUi['pretend'] = True

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
                foundAtoms.append([package,Equo.atomMatch(package)])
            if tbz2:
                for pkg in tbz2:
                    # create a repository for each database
                    basefile = os.path.basename(pkg)
                    if os.path.isdir(etpConst['entropyunpackdir']+"/"+basefile[:-5]):
                        shutil.rmtree(etpConst['entropyunpackdir']+"/"+basefile[:-5])
                    os.makedirs(etpConst['entropyunpackdir']+"/"+basefile[:-5])
                    dbfile = Equo.entropyTools.extractEdb(pkg,dbpath = etpConst['entropyunpackdir']+"/"+basefile[:-5]+"/packages.db")
                    if dbfile == None:
                        if not (etpUi['quiet']): print_warning(red("## ATTENTION:")+bold(" "+basefile+" ")+red(" is not a valid Entropy package. Skipping..."))
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
                    mydbconn = Equo.openGenericDatabase(dbfile)
                    # read all idpackages
                    try:
                        myidpackages = mydbconn.listAllIdpackages() # all branches admitted from external files
                    except:
                        if not (etpUi['quiet']): print_warning(red("## ATTENTION:")+bold(" "+basefile+" ")+red(" is not a valid Entropy package. Skipping..."))
                        del etpRepositories[basefile]
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
                if not (etpUi['quiet']): print_warning(bold("!!!")+red(" No match for ")+bold(result[0])+red(" in database. If you omitted the category, try adding it."))
                if not (etpUi['quiet']): print_warning(red("    Also, if package is masked, you need to unmask it. See ")+bold(etpConst['confdir']+"/packages/*")+red(" files for help."))

        foundAtoms = _foundAtoms

        # are there packages in foundAtoms?
        if (not foundAtoms):
            if not (etpUi['quiet']): print_error(red("No packages found"))
            dirscleanup()
            return 127,-1

        if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
            # now print the selected packages
            if not (etpUi['quiet']): print_info(red(" @@ ")+blue("These are the chosen packages:"))
            totalatoms = len(foundAtoms)
            atomscounter = 0
            for atomInfo in foundAtoms:
                atomscounter += 1
                idpackage = atomInfo[0]
                reponame = atomInfo[1]
                # open database
                dbconn = Equo.openRepositoryDatabase(reponame)

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
                pkginstalled = Equo.clientDbconn.atomMatch(Equo.entropyTools.dep_getkey(pkgatom), matchSlot = pkgslot)
                if (pkginstalled[1] == 0):
                    # found
                    idx = pkginstalled[0]
                    installedVer = Equo.clientDbconn.retrieveVersion(idx)
                    installedTag = Equo.clientDbconn.retrieveVersionTag(idx)
                    if not installedTag:
                        installedTag = "NoTag"
                    installedRev = Equo.clientDbconn.retrieveRevision(idx)

                if not (etpUi['quiet']): print_info("   # "+red("(")+bold(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+bold(pkgatom)+" >>> "+red(etpRepositories[reponame]['description']))
                if not (etpUi['quiet']): print_info("\t"+red("Versioning:\t")+" "+blue(installedVer)+" / "+blue(installedTag)+" / "+blue(str(installedRev))+bold(" ===> ")+darkgreen(pkgver)+" / "+darkgreen(pkgtag)+" / "+darkgreen(str(pkgrev)))
                # tell wether we should update it
                if installedVer == "Not installed":
                    installedVer = "0"
                if installedRev == "NoRev":
                    installedRev = 0
                pkgcmp = Equo.entropyTools.entropyCompareVersions((pkgver,pkgtag,pkgrev),(installedVer,installedTag,installedRev))
                if (pkgcmp == 0):
                    action = darkgreen("Reinstall")
                elif (pkgcmp > 0):
                    if (installedVer == "0"):
                        action = darkgreen("Install")
                    else:
                        action = blue("Upgrade")
                else:
                    action = red("Downgrade")
                if not (etpUi['quiet']): print_info("\t"+red("Action:\t\t")+" "+action)

            if (etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']):
                if not (etpUi['quiet']): print_info(red(" @@ ")+blue("Number of packages: ")+str(totalatoms))

            if (deps):
                if (etpUi['ask']):
                    rc = Equo.entropyTools.askquestion("     Would you like to continue with dependencies calculation ?")
                    if rc == "No":
                        dirscleanup()
                        return 0,0

        runQueue = []
        removalQueue = [] # aka, conflicts

        if deps:
            print_info(red(" @@ ")+blue("Calculating dependencies..."))
            runQueue, removalQueue, status = Equo.retrieveInstallQueue(foundAtoms, emptydeps, deepdeps)
            if status == -2:
                if not (etpUi['quiet']): print_error(red(" @@ ")+blue("Cannot find needed dependencies: ")+str(runQueue))
                crying_atoms = set()
                for atom in runQueue:
                    for repo in etpRepositories:
                        rdbconn = Equo.openRepositoryDatabase(repo)
                        riddep = rdbconn.searchDependency(atom)
                        if riddep != -1:
                            ridpackages = rdbconn.searchIdpackageFromIddependency(riddep)
                            for i in ridpackages:
                                iatom = rdbconn.retrieveAtom(i)
                                crying_atoms.add((iatom,repo))
                if crying_atoms:
                    if not (etpUi['quiet']): print_error(red(" @@ ")+blue("Probably needed by:"))
                    for crying_atomdata in crying_atoms:
                        if not (etpUi['quiet']): print_error(red("     # ")+" [from:"+crying_atomdata[1]+"] "+darkred(crying_atomdata[0]))

                dirscleanup()
                return 130, -1
        else:
            for atomInfo in foundAtoms:
                runQueue.append(atomInfo)

        if ((not runQueue) and (not removalQueue)):
            if not (etpUi['quiet']): print_error(red("Nothing to do."))
            dirscleanup()
            return 126,-1

        downloadSize = 0
        onDiskUsedSize = 0
        onDiskFreedSize = 0
        pkgsToInstall = 0
        pkgsToUpdate = 0
        pkgsToReinstall = 0
        pkgsToDowngrade = 0
        pkgsToRemove = len(removalQueue)
        actionQueue = {}

        if (runQueue):
            if (etpUi['ask'] or etpUi['pretend']):
                if not (etpUi['quiet']): print_info(red(" @@ ")+blue("These are the packages that would be ")+bold("merged:"))

            count = 0
            atomlen = len(runQueue)
            for packageInfo in runQueue:
                count += 1

                dbconn = Equo.openRepositoryDatabase(packageInfo[1])
                pkgatom = dbconn.retrieveAtom(packageInfo[0])
                pkgver = dbconn.retrieveVersion(packageInfo[0])
                pkgtag = dbconn.retrieveVersionTag(packageInfo[0])
                pkgrev = dbconn.retrieveRevision(packageInfo[0])
                pkgslot = dbconn.retrieveSlot(packageInfo[0])
                pkgfile = dbconn.retrieveDownloadURL(packageInfo[0])
                onDiskUsedSize += dbconn.retrieveOnDiskSize(packageInfo[0])

                dl = equoTools.checkNeededDownload(pkgfile, None) # we'll do a good check during installPackage
                if dl < 0:
                    pkgsize = dbconn.retrieveSize(packageInfo[0])
                    downloadSize += int(pkgsize)

                # get installed package data
                installedVer = '0'
                installedTag = ''
                installedRev = 0
                pkginstalled = Equo.clientDbconn.atomMatch(Equo.entropyTools.dep_getkey(pkgatom), matchSlot = pkgslot)
                if (pkginstalled[1] == 0):
                    # found an installed package
                    idx = pkginstalled[0]
                    installedVer = Equo.clientDbconn.retrieveVersion(idx)
                    installedTag = Equo.clientDbconn.retrieveVersionTag(idx)
                    installedRev = Equo.clientDbconn.retrieveRevision(idx)
                    onDiskFreedSize += Equo.clientDbconn.retrieveOnDiskSize(idx)

                if not (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
                    continue

                action = 0
                flags = " ["
                pkgcmp = Equo.entropyTools.entropyCompareVersions((pkgver,pkgtag,pkgrev),(installedVer,installedTag,installedRev))
                if (pkgcmp == 0):
                    pkgsToReinstall += 1
                    flags += red("R")
                    action = 1
                elif (pkgcmp > 0):
                    if (installedVer == "0"):
                        pkgsToInstall += 1
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

                repoinfo = red("[")+bold(packageInfo[1])+red("] ")
                oldinfo = ''
                if action != 0:
                    oldinfo = "   ["+blue(installedVer)+"/"+red(str(installedRev))
                    oldtag = "]"
                    if installedTag:
                        oldtag = "/"+darkred(installedTag)+oldtag
                    oldinfo += oldtag

                if not (etpUi['quiet']): print_info(darkred(" ##")+flags+repoinfo+enlightenatom(str(pkgatom))+"/"+str(pkgrev)+oldinfo)

        if (removalQueue):

            if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']) and removalQueue:
                if not (etpUi['quiet']): print_info(red(" @@ ")+blue("These are the packages that would be ")+bold("removed")+blue(" (conflicting/substituted):"))

                for idpackage in removalQueue:
                    pkgatom = Equo.clientDbconn.retrieveAtom(idpackage)
                    onDiskFreedSize += Equo.clientDbconn.retrieveOnDiskSize(idpackage)
                    installedfrom = Equo.clientDbconn.retrievePackageFromInstalledTable(idpackage)
                    repoinfo = red("[")+brown("from: ")+bold(installedfrom)+red("] ")
                    if not (etpUi['quiet']): print_info(red("   ## ")+"["+red("W")+"] "+repoinfo+enlightenatom(pkgatom))

        if (runQueue) or (removalQueue) and not etpUi['quiet']:
            # show download info
            print_info(red(" @@ ")+blue("Packages needing install:\t")+red(str(len(runQueue))))
            print_info(red(" @@ ")+blue("Packages needing removal:\t")+red(str(pkgsToRemove)))
            if (etpUi['ask'] or etpUi['verbose'] or etpUi['pretend']):
                print_info(red(" @@ ")+darkgreen("Packages needing install:\t")+darkgreen(str(pkgsToInstall)))
                print_info(red(" @@ ")+darkgreen("Packages needing reinstall:\t")+darkgreen(str(pkgsToReinstall)))
                print_info(red(" @@ ")+blue("Packages needing update:\t\t")+blue(str(pkgsToUpdate)))
                print_info(red(" @@ ")+red("Packages needing downgrade:\t")+red(str(pkgsToDowngrade)))
            print_info(red(" @@ ")+blue("Download size:\t\t\t")+bold(str(Equo.entropyTools.bytesIntoHuman(downloadSize))))
            deltaSize = onDiskUsedSize - onDiskFreedSize
            if (deltaSize > 0):
                print_info(red(" @@ ")+blue("Used disk space:\t\t\t")+bold(str(Equo.entropyTools.bytesIntoHuman(deltaSize))))
            else:
                print_info(red(" @@ ")+blue("Freed disk space:\t\t")+bold(str(Equo.entropyTools.bytesIntoHuman(abs(deltaSize)))))

        if (etpUi['ask']):
            rc = Equo.entropyTools.askquestion("     Would you like to run the queue ?")
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
            resume_cache['onlyfetch'] = onlyfetch
            resume_cache['emptydeps'] = emptydeps
            resume_cache['deepdeps'] = deepdeps
            dumpTools.dumpobj(etpCache['install'],resume_cache)

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = dumpTools.loadobj(etpCache['install'])
        if not resume_cache: # None or {}

            if not (etpUi['quiet']): print_error(red("Nothing to resume."))
            return 128,-1

        else:

            try:
                removalQueue = resume_cache['removalQueue'][:]
                runQueue = resume_cache['runQueue'][:]
                onlyfetch = resume_cache['onlyfetch']
                emptydeps = resume_cache['emptydeps']
                deepdeps = resume_cache['deepdeps']
                if not (etpUi['quiet']): print_warning(red("Resuming previous operations..."))
            except:
                if not (etpUi['quiet']): print_error(red("Resume cache corrupted."))
                dumpTools.dumpobj(etpCache['install'],{})
                return 128,-1

            if skipfirst and runQueue:
                runQueue, removalQueue, status = Equo.retrieveInstallQueue(runQueue[1:], emptydeps, deepdeps)
                # save new queues
                resume_cache['runQueue'] = runQueue[:]
                resume_cache['removalQueue'] = removalQueue[:]
                dumpTools.dumpobj(etpCache['install'],resume_cache)


    # running tasks
    totalqueue = str(len(runQueue))
    totalremovalqueue = str(len(removalQueue))
    currentqueue = 0
    currentremovalqueue = 0
    
    ### Before starting the real install, fetch packages and verify checksum.
    fetchqueue = 0
    for packageInfo in runQueue:
        fetchqueue += 1
        idpackage = packageInfo[0]
        repository = packageInfo[1]
        dbconn = Equo.openRepositoryDatabase(repository)
        pkgatom = dbconn.retrieveAtom(idpackage)

        # create infoDict
        infoDict = {}
        infoDict['repository'] = packageInfo[1]
        infoDict['idpackage'] = packageInfo[0]
        infoDict['checksum'] = dbconn.retrieveDigest(idpackage)
        infoDict['download'] = dbconn.retrieveDownloadURL(idpackage)
        infoDict['verified'] = False

        steps = []
        if not repository.endswith(".tbz2"):
            if equoTools.checkNeededDownload(pkgfile, None) < 0:
                steps.append("fetch")
            if dochecksum:
                steps.append("checksum")

        # if file exists, first checksum then fetch
        if os.path.isfile(os.path.join(etpConst['entropyworkdir'],infoDict['download'])):
            steps.reverse()

        if not (etpUi['quiet']): print_info(red(" :: ")+bold("(")+blue(str(fetchqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(pkgatom))

        for step in steps:
            rc = equoTools.stepExecutor(step,infoDict,str(fetchqueue)+"/"+totalqueue)
            if (rc != 0):
                dirscleanup()
                return -1,rc
        del infoDict

    if onlyfetch:
        if not etpUi['quiet']: print_info(red(" @@ ")+blue("Fetch Complete."))
        return 0,0

    for idpackage in removalQueue:
        currentremovalqueue += 1
        infoDict = {}
        infoDict['triggers'] = {}
        infoDict['removeatom'] = Equo.clientDbconn.retrieveAtom(idpackage)
        infoDict['removeidpackage'] = idpackage
        infoDict['diffremoval'] = False
        infoDict['removeconfig'] = True # we need to completely wipe configuration of conflicts
        infoDict['removecontent'] = Equo.clientDbconn.retrieveContent(idpackage)
        infoDict['triggers']['remove'] = Equo.clientDbconn.getPackageData(idpackage)
        steps = []
        steps.append("preremove")
        steps.append("remove")
        steps.append("postremove")

        if not (etpUi['quiet']): print_info(red(" -- ")+bold("(")+blue(str(currentremovalqueue))+"/"+red(totalremovalqueue)+bold(") ")+">>> "+darkgreen(infoDict['removeatom']))

        for step in steps:
            rc = equoTools.stepExecutor(step,infoDict, str(currentremovalqueue)+"/"+totalremovalqueue)
            if (rc != 0):
                dirscleanup()
                return -1,rc

        del infoDict['triggers']

        # update resume cache
        if not tbz2: # tbz2 caching not supported
            resume_cache['removalQueue'].remove(idpackage)
            dumpTools.dumpobj(etpCache['install'],resume_cache)

    for packageInfo in runQueue:

        currentqueue += 1
        idpackage = packageInfo[0]
        repository = packageInfo[1]
        # get package atom
        dbconn = Equo.openRepositoryDatabase(repository)
        pkgatom = dbconn.retrieveAtom(idpackage)

        infoDict = {}
        infoDict['triggers'] = {}
        infoDict['atom'] = pkgatom
        infoDict['idpackage'] = idpackage
        infoDict['repository'] = repository
        infoDict['slot'] = dbconn.retrieveSlot(idpackage)
        infoDict['version'] = dbconn.retrieveVersion(idpackage)
        infoDict['versiontag'] = dbconn.retrieveVersionTag(idpackage)
        infoDict['revision'] = dbconn.retrieveRevision(idpackage)
        infoDict['category'] = dbconn.retrieveCategory(idpackage)
        infoDict['download'] = dbconn.retrieveDownloadURL(idpackage)
        infoDict['name'] = dbconn.retrieveName(idpackage)
        infoDict['messages'] = dbconn.retrieveMessages(idpackage)
        infoDict['checksum'] = dbconn.retrieveDigest(idpackage)
        # fill action queue
        infoDict['removeidpackage'] = -1
        infoDict['removeconfig'] = configFiles
        infoDict['removeidpackage'] = Equo.retrieveInstalledIdPackage(
                                                Equo.entropyTools.dep_getkey(infoDict['atom']),
                                                infoDict['slot']
                                            )
        # set unpack dir and image dir
        if infoDict['repository'].endswith(".tbz2"):
            infoDict['pkgpath'] = etpRepositories[infoDict['repository']]['pkgpath']
        else:
            infoDict['pkgpath'] = etpConst['entropyworkdir']+"/"+infoDict['download']
        infoDict['unpackdir'] = etpConst['entropyunpackdir']+"/"+infoDict['download']
        infoDict['imagedir'] = etpConst['entropyunpackdir']+"/"+infoDict['download']+"/"+etpConst['entropyimagerelativepath']

        # is it a smart package?
        infoDict['smartpackage'] = False
        if infoDict['repository'].endswith(".tbz2"):
            infoDict['smartpackage'] = etpRepositories[infoDict['repository']]['smartpackage']

        # gentoo xpak data
        if etpConst['gentoo-compat']:
            infoDict['xpakstatus'] = None
            infoDict['xpakpath'] = etpConst['entropyunpackdir']+"/"+infoDict['download']+"/"+etpConst['entropyxpakrelativepath']
            infoDict['xpakdir'] = infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']

        # set steps
        infoDict['steps'] = []
        # install
        if (infoDict['removeidpackage'] != -1):
            infoDict['steps'].append("preremove")
        infoDict['steps'].append("unpack")
        infoDict['steps'].append("preinstall")
        infoDict['steps'].append("install")
        if (infoDict['removeidpackage'] != -1):
            infoDict['steps'].append("postremove")
        infoDict['steps'].append("postinstall")
        if not etpConst['gentoo-compat']: # otherwise gentoo triggers will show that
            infoDict['steps'].append("showmessages")
        infoDict['steps'].append("cleanup")

        # disable removal for packages already in removalQueue
        if infoDict['removeidpackage'] in removalQueue:
            infoDict['removeidpackage'] = -1

        # compare both versions and if they match, disable removeidpackage
        if infoDict['removeidpackage'] != -1:
            installedVer = Equo.clientDbconn.retrieveVersion(infoDict['removeidpackage'])
            installedTag = Equo.clientDbconn.retrieveVersionTag(infoDict['removeidpackage'])
            installedRev = Equo.clientDbconn.retrieveRevision(infoDict['removeidpackage'])
            pkgcmp = Equo.entropyTools.entropyCompareVersions(
                                                        (infoDict['version'],infoDict['versiontag'],infoDict['revision']),
                                                        (installedVer,installedTag,installedRev)
                                                    )
            if pkgcmp == 0:
                infoDict['removeidpackage'] = -1
            del pkgcmp

        # differential remove list
        if (infoDict['removeidpackage'] != -1):
            # is it still available?
            if Equo.clientDbconn.isIDPackageAvailable(infoDict['removeidpackage']):
                infoDict['diffremoval'] = True
                infoDict['removeatom'] = Equo.clientDbconn.retrieveAtom(infoDict['removeidpackage'])
                oldcontent = Equo.clientDbconn.retrieveContent(infoDict['removeidpackage'])
                newcontent = dbconn.retrieveContent(idpackage)
                oldcontent = oldcontent - newcontent
                del newcontent
                infoDict['removecontent'] = oldcontent.copy()
                del oldcontent
                infoDict['triggers']['remove'] = Equo.clientDbconn.getPackageData(infoDict['removeidpackage'])
            else:
                infoDict['removeidpackage'] = -1

        # XXX: too much memory used for this
        infoDict['triggers']['install'] = dbconn.getPackageData(idpackage)

        if not (etpUi['quiet']): print_info(red(" ++ ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(pkgatom))

        for step in infoDict['steps']:
            rc = equoTools.stepExecutor(step,infoDict,str(currentqueue)+"/"+totalqueue)
            if (rc != 0):
                dirscleanup()
                return -1,rc

        del infoDict['triggers']

        # update resume cache
        if not tbz2: # tbz2 caching not supported
            resume_cache['runQueue'].remove(packageInfo)
            dumpTools.dumpobj(etpCache['install'],resume_cache)

        # unload dict
        del infoDict


    if not etpUi['quiet']: print_info(red(" @@ ")+blue("Install Complete."))
    # clear resume information
    dumpTools.dumpobj(etpCache['install'],{})
    dirscleanup()
    return 0,0


def removePackages(packages = [], atomsdata = [], deps = True, deep = False, systemPackagesCheck = True, configFiles = False, resume = False, human = False):

    # check if I am root
    if (not Equo.entropyTools.isRoot()):
        if not etpUi['quiet']: print_warning(red("Running with ")+bold("--pretend")+red("..."))
        etpUi['pretend'] = True

    if not resume:

        foundAtoms = []
        if (atomsdata):
            for idpackage in atomsdata:
                foundAtoms.append([Equo.clientDbconn.retrieveAtom(idpackage),(idpackage,0)])
        else:
            for package in packages:
                foundAtoms.append([package,Equo.clientDbconn.atomMatch(package)])

        # filter packages not found
        _foundAtoms = []
        for result in foundAtoms:
            exitcode = result[1][0]
            if (exitcode != -1):
                _foundAtoms.append(result[1])
            else:
                if not (etpUi['quiet']): print_warning(red("## ATTENTION -> package")+bold(" "+result[0]+" ")+red("is not installed."))

        foundAtoms = _foundAtoms

        # are packages in foundAtoms?
        if (not foundAtoms):
            if not (etpUi['quiet']): print_error(red("No packages found"))
            return 125,-1

        plainRemovalQueue = []

        lookForOrphanedPackages = True
        # now print the selected packages
        if not (etpUi['quiet']): print_info(red(" @@ ")+blue("These are the chosen packages:"))
        totalatoms = len(foundAtoms)
        atomscounter = 0
        for atomInfo in foundAtoms:
            atomscounter += 1
            idpackage = atomInfo[0]
            systemPackage = Equo.clientDbconn.isSystemPackage(idpackage)

            # get needed info
            pkgatom = Equo.clientDbconn.retrieveAtom(idpackage)
            installedfrom = Equo.clientDbconn.retrievePackageFromInstalledTable(idpackage)

            if (systemPackage) and (systemPackagesCheck):
                # check if the package is slotted and exist more than one installed first
                sysresults = Equo.clientDbconn.atomMatch(Equo.entropyTools.dep_getkey(pkgatom), multiMatch = True)
                slots = set()
                if sysresults[1] == 0:
                    for x in sysresults[0]:
                        slots.add(Equo.clientDbconn.retrieveSlot(x))
                    if len(slots) < 2:
                        if not (etpUi['quiet']): print_warning(darkred("   # !!! ")+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+red(" is a vital package. Removal forbidden."))
                        continue
                else:
                    if not (etpUi['quiet']): print_warning(darkred("   # !!! ")+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+red(" is a vital package. Removal forbidden."))
                    continue
            plainRemovalQueue.append(idpackage)

            if not (etpUi['quiet']): print_info("   # "+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+" | Installed from: "+red(installedfrom))

        if (etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']):
            if not (etpUi['quiet']): print_info(red(" @@ ")+blue("Number of packages: ")+str(totalatoms))

        if (deps):
            question = "     Would you like to look for packages that can be removed along with the selected above?"
        else:
            question = "     Would you like to remove them now?"
            lookForOrphanedPackages = False

        if (etpUi['ask']):
            rc = Equo.entropyTools.askquestion(question)
            if rc == "No":
                lookForOrphanedPackages = False
                if (not deps):
                    return 0,0

        if (not plainRemovalQueue):
            if not (etpUi['quiet']): print_error(red("Nothing to do."))
            return 126,-1

        removalQueue = []

        if (lookForOrphanedPackages):
            choosenRemovalQueue = []
            if not (etpUi['quiet']): print_info(red(" @@ ")+blue("Calculating..."))
            treeview = Equo.generate_depends_tree(plainRemovalQueue, deep = deep)
            treelength = len(treeview[0])
            if treelength > 1:
                treeview = treeview[0]
                for x in range(treelength)[::-1]:
                    for y in treeview[x]:
                        choosenRemovalQueue.append(y)

                if (choosenRemovalQueue):
                    if not (etpUi['quiet']): print_info(red(" @@ ")+blue("This is the new removal queue:"))
                    totalatoms = str(len(choosenRemovalQueue))
                    atomscounter = 0

                    for idpackage in choosenRemovalQueue:
                        atomscounter += 1
                        rematom = Equo.clientDbconn.retrieveAtom(idpackage)
                        installedfrom = Equo.clientDbconn.retrievePackageFromInstalledTable(idpackage)
                        repositoryInfo = bold("[")+red("from: ")+brown(installedfrom)+bold("]")
                        stratomscounter = str(atomscounter)
                        while len(stratomscounter) < len(totalatoms):
                            stratomscounter = " "+stratomscounter
                        print_info("   # "+red("(")+bold(stratomscounter)+"/"+blue(str(totalatoms))+red(")")+repositoryInfo+" "+blue(rematom))

                    for x in choosenRemovalQueue:
                        removalQueue.append(x)

                else:
                    if not (etpUi['quiet']): writechar("\n")
        if (etpUi['ask']) or human:
            question = "     Would you like to proceed?"
            if human:
                question = "     Would you like to proceed with a selective removal ?"
            rc = Equo.entropyTools.askquestion(question)
            if rc == "No":
                return 0,0
        elif (deps):
            if not (etpUi['quiet']): Equo.entropyTools.countdown(what = red(" @@ ")+blue("Starting removal in "),back = True)

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
            if not (etpUi['quiet']): print_error(red("Nothing to resume."))
            return 128,-1
        else:
            try:
                removalQueue = resume_cache['removalQueue'][:]
                if not (etpUi['quiet']): print_warning(red("Resuming previous operations..."))
            except:
                if not (etpUi['quiet']): print_error(red("Resume cache corrupted."))
                dumpTools.dumpobj(etpCache['remove'],{})
                return 128,-1

    # validate removalQueue
    invalid = set()
    for idpackage in removalQueue:
        try:
            Equo.clientDbconn.retrieveAtom(idpackage)
        except TypeError:
            invalid.add(idpackage)
    removalQueue = [x for x in removalQueue if x not in invalid]

    totalqueue = str(len(removalQueue))
    currentqueue = 0
    for idpackage in removalQueue:
        currentqueue += 1
        infoDict = {}
        infoDict['triggers'] = {}
        infoDict['removeidpackage'] = idpackage
        try:
            infoDict['removeatom'] = Equo.clientDbconn.retrieveAtom(idpackage)
        except TypeError: # resume cache issues?
            try:
                # force database removal and forget about the rest
                if not (etpUi['quiet']): print "DEBUG: attention! entry broken probably due to a resume cache issue, forcing removal from database"
                Equo.clientDbconn.removePackage(idpackage)
                Equo.clientDbconn.removePackageFromInstalledTable(idpackage)
            except:
                pass
            # update resume cache
            resume_cache['removalQueue'].remove(idpackage)
            dumpTools.dumpobj(etpCache['remove'],resume_cache)
            continue

        infoDict['diffremoval'] = False
        infoDict['removeconfig'] = configFiles
        infoDict['removecontent'] = Equo.clientDbconn.retrieveContent(idpackage)
        infoDict['triggers']['remove'] = Equo.clientDbconn.getPackageData(idpackage)

        steps = []
        steps.append("preremove")
        steps.append("remove")
        steps.append("postremove")

        # if human
        if not (etpUi['quiet']): print_info(red(" -- ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(infoDict['removeatom']))
        if human:
            rc = Equo.entropyTools.askquestion("     Remove this one ?")
            if rc == "No":
                # update resume cache
                resume_cache['removalQueue'].remove(idpackage)
                dumpTools.dumpobj(etpCache['remove'],resume_cache)
                # unload dict
                del infoDict['triggers']
                continue

        for step in steps:
            rc = equoTools.stepExecutor(step,infoDict,str(currentqueue)+"/"+str(len(removalQueue)))
            if (rc != 0):
                return -1,rc

        # unload dict
        del infoDict['triggers']

        # update resume cache
        resume_cache['removalQueue'].remove(idpackage)
        dumpTools.dumpobj(etpCache['remove'],resume_cache)

    if not (etpUi['quiet']): print_info(red(" @@ ")+blue("All done."))

    return 0,0


def dependenciesTest(clientDbconn = None, reagent = False):

    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("Running dependency test..."))

    if clientDbconn == None:
        clientDbconn = Equo.clientDbconn
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


        xdeps = clientDbconn.retrieveDependenciesList(xidpackage)
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
                    match = Equo.atomMatch(dep)
                if match[0] == -1:
                    # FIXME
                    if (not etpUi['quiet']):
                        print_info(bold("       :x: NOT FOUND ")+red(dep))
                    else:
                        print dep,"--"
                    continue
                iddep = match[0]
                repo = match[1]
                dbconn = Equo.openRepositoryDatabase(repo)
                depatom = dbconn.retrieveAtom(iddep)
                if (not etpUi['quiet']):
                    print_info(bold("       :o: ")+red(depatom))
                else:
                    print pkgatom+" -> "+depatom
                packagesNeeded.add((depatom,dep))

    if (etpUi['pretend']):
        return 0, packagesNeeded

    if (packagesNeeded) and (not etpUi['quiet']) and (not reagent):
        if (etpUi['ask']):
            rc = Equo.entropyTools.askquestion("     Would you like to install the available packages?")
            if rc == "No":
                return 0,packagesNeeded
        else:
            print_info(red(" @@ ")+blue("Installing available packages in ")+red("10 seconds")+blue("..."))
            import time
            time.sleep(10)

        # organize
        packages = set([x[0] for x in packagesNeeded])

        Equo.entropyTools.applicationLockCheck("install")
        installPackages(packages, deps = False)

    if not etpUi['quiet']: print_info(red(" @@ ")+blue("All done."))
    return 0,packagesNeeded

def librariesTest(clientDbconn = None, reagent = False, listfiles = False):

    qstat = etpUi['quiet']
    if listfiles:
        etpUi['quiet'] = True

    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("Running libraries test..."))

    if clientDbconn == None:
        clientDbconn = Equo.clientDbconn

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

    ldpaths = Equo.entropyTools.collectLinkerPaths()

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
        dbconn = Equo.openRepositoryDatabase(repodata[1])
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
            dbconn = Equo.openRepositoryDatabase(packagedata[1])
            myatom = dbconn.retrieveAtom(packagedata[0])
            atomsdata.add((myatom,(packagedata[0],packagedata[1])))
            print_info("   "+red(packagedata[2])+" => "+brown(myatom)+" ["+red(packagedata[1])+"]")
    else:
        for packagedata in packagesMatched:
            dbconn = Equo.openRepositoryDatabase(packagedata[1])
            myatom = dbconn.retrieveAtom(packagedata[0])
            atomsdata.add((myatom,(packagedata[0],packagedata[1])))
            print myatom
        return 0,atomsdata

    if (etpUi['pretend']):
        return 0,atomsdata

    if (atomsdata) and (not reagent):
        if (etpUi['ask']):
            rc = Equo.entropyTools.askquestion("     Would you like to install them?")
            if rc == "No":
                return 0,atomsdata
        else:
            print_info(red(" @@ ")+blue("Installing found packages in ")+red("10 seconds")+blue("..."))
            import time
            time.sleep(10)

        Equo.entropyTools.applicationLockCheck("install")
        rc = installPackages(atomsdata = list(atomsdata))
        if rc[0] == 0:
            return 0,atomsdata
        else:
            return rc[0],atomsdata

    return 0,atomsdata
