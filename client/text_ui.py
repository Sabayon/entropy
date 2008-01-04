#!/usr/bin/python
'''
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

########################################################
####
##   Packages user handling function
#

import shutil
from entropyConstants import *
from outputTools import *
from entropy import EquoInterface
Equo = EquoInterface()

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
        print_warning(red("Running with ")+bold("--pretend")+red("..."))
        etpUi['pretend'] = True

    if not resume:

        # verify selected release (branch)
        if (upgradeTo):
            availbranches = Equo.listAllAvailableBranches()
            if (upgradeTo not in availbranches) or (upgradeTo == None):
                print_error(red("Selected release: ")+bold(str(upgradeTo))+red(" is not available."))
                return 1,-2
            else:
                branch = upgradeTo
        else:
            branch = etpConst['branch']

        if (not etpUi['pretend']) and (upgradeTo):
            # update configuration
            Equo.entropyTools.writeNewBranch(upgradeTo)

        print_info(red(" @@ ")+blue("Calculating world packages..."))
        update, remove, fine = Equo.calculate_world_updates(empty_deps = replay, branch = branch)

        if (etpUi['verbose'] or etpUi['pretend']):
            print_info(red(" @@ ")+darkgreen("Packages matching update:\t\t")+bold(str(len(update))))
            print_info(red(" @@ ")+darkred("Packages matching not available:\t\t")+bold(str(len(remove))))
            print_info(red(" @@ ")+blue("Packages matching already up to date:\t")+bold(str(len(fine))))

        del fine

        # clear old resume information
        if etpConst['uid'] == 0:
            Equo.dumpTools.dumpobj(etpCache['world'],{})
            Equo.dumpTools.dumpobj(etpCache['install'],{})
            Equo.dumpTools.dumpobj(etpCache['remove'],[])
            if (not etpUi['pretend']):
                # store resume information
                resume_cache = {}
                resume_cache['ask'] = etpUi['ask']
                resume_cache['verbose'] = etpUi['verbose']
                resume_cache['onlyfetch'] = onlyfetch
                resume_cache['remove'] = remove
                Equo.dumpTools.dumpobj(etpCache['world'],resume_cache)

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = Equo.dumpTools.loadobj(etpCache['world'])
        if (not resume_cache) or (etpConst['uid'] != 0): # None or {}
            print_error(red("Nothing to resume."))
            return 128,-1
        else:
            try:
                update = []
                remove = resume_cache['removed'].copy()
                etpUi['ask'] = resume_cache['ask']
                etpUi['verbose'] = resume_cache['verbose']
                onlyfetch = resume_cache['onlyfetch']
                Equo.dumpTools.dumpobj(etpCache['remove'],list(remove))
            except:
                print_error(red("Resume cache corrupted."))
                Equo.dumpTools.dumpobj(etpCache['world'],{})
                Equo.dumpTools.dumpobj(etpCache['install'],{})
                Equo.dumpTools.dumpobj(etpCache['remove'],[])
                return 128,-1

    # disable collisions protection, better
    oldcollprotect = etpConst['collisionprotect']
    etpConst['collisionprotect'] = 0

    if (update) or (resume):
        rc = installPackages(atomsdata = update, onlyfetch = onlyfetch, resume = resume, skipfirst = skipfirst, dochecksum = dochecksum)
        if rc[1] != 0:
            return 1,rc[0]
    else:
        print_info(red(" @@ ")+blue("Nothing to update."))

    etpConst['collisionprotect'] = oldcollprotect

    # verify that client database idpackage still exist, validate here before passing removePackage() wrong info
    remove = [x for x in remove if Equo.clientDbconn.isIDPackageAvailable(x)]

    if (remove):
        remove = list(remove)
        remove.sort()
        print_info(red(" @@ ")+blue("On the system there are packages that are not available anymore in the online repositories."))
        print_info(red(" @@ ")+blue("Even if they are usually harmless, it is suggested to remove them."))

        if (not etpUi['pretend']):
            if human:
                rc = Equo.askQuestion("     Would you like to query them ?")
                if rc == "No":
                    return 0,0

            # run removePackages with --nodeps
            removePackages(atomsdata = remove, deps = False, systemPackagesCheck = False, configFiles = True, resume = resume, human = human)
        else:
            print_info(red(" @@ ")+blue("Calculation complete."))

    else:
        print_info(red(" @@ ")+blue("Nothing to remove."))

    return 0,0

def installPackages(packages = [], atomsdata = [], deps = True, emptydeps = False, onlyfetch = False, deepdeps = False, configFiles = False, tbz2 = [], resume = False, skipfirst = False, dochecksum = True):

    # check if I am root
    if (not Equo.entropyTools.isRoot()):
        print_warning(red("Running with ")+bold("--pretend")+red("..."))
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
                        print_warning(red("## ATTENTION:")+bold(" "+basefile+" ")+red(" is not a valid Entropy package. Skipping..."))
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
                print_warning(bold("!!!")+red(" No match for ")+bold(result[0])+red(" in database. If you omitted the category, try adding it."))
                print_warning(red("    Also, if package is masked, you need to unmask it. See ")+bold(etpConst['confdir']+"/packages/*")+red(" files for help."))

        foundAtoms = _foundAtoms

        # are there packages in foundAtoms?
        if (not foundAtoms):
            print_error(red("No packages found"))
            dirscleanup()
            return 127,-1

        if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
            # now print the selected packages
            print_info(red(" @@ ")+blue("These are the chosen packages:"))
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

                print_info("   # "+red("(")+bold(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+bold(pkgatom)+" >>> "+red(etpRepositories[reponame]['description']))
                print_info("\t"+red("Versioning:\t")+" "+blue(installedVer)+" / "+blue(installedTag)+" / "+blue(str(installedRev))+bold(" ===> ")+darkgreen(pkgver)+" / "+darkgreen(pkgtag)+" / "+darkgreen(str(pkgrev)))
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
                print_info("\t"+red("Action:\t\t")+" "+action)

            if (etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']):
                print_info(red(" @@ ")+blue("Number of packages: ")+str(totalatoms))

            if (deps):
                if (etpUi['ask']):
                    rc = Equo.askQuestion("     Would you like to continue with dependencies calculation ?")
                    if rc == "No":
                        dirscleanup()
                        return 0,0

        runQueue = []
        removalQueue = [] # aka, conflicts

        if deps:
            print_info(red(" @@ ")+blue("Calculating dependencies..."))
            runQueue, removalQueue, status = Equo.retrieveInstallQueue(foundAtoms, emptydeps, deepdeps)
            if status == -2:
                print_error(red(" @@ ")+blue("Cannot find needed dependencies: ")+str(runQueue))
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
                    print_error(red(" @@ ")+blue("Probably needed by:"))
                    for crying_atomdata in crying_atoms:
                        print_error(red("     # ")+" [from:"+crying_atomdata[1]+"] "+darkred(crying_atomdata[0]))

                dirscleanup()
                return 130, -1
        else:
            for atomInfo in foundAtoms:
                runQueue.append(atomInfo)

        if ((not runQueue) and (not removalQueue)):
            print_error(red("Nothing to do."))
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

        if (runQueue):
            if (etpUi['ask'] or etpUi['pretend']):
                print_info(red(" @@ ")+blue("These are the packages that would be ")+bold("merged:"))

            count = 0
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

                dl = Equo.check_needed_package_download(pkgfile, None) # we'll do a good check during installPackage
                if dl < 0:
                    pkgsize = dbconn.retrieveSize(packageInfo[0])
                    downloadSize += int(pkgsize)
                else:
                    try:
                        f = open(etpConst['entropyworkdir']+"/"+pkgfile,"r")
                        f.seek(0,2)
                        currsize = f.tell()
                        pkgsize = dbconn.retrieveSize(packageInfo[0])
                        downloadSize += int(pkgsize)-int(currsize)
                        f.close()
                    except:
                        pass

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

                print_info(darkred(" ##")+flags+repoinfo+enlightenatom(str(pkgatom))+"/"+str(pkgrev)+oldinfo)

        if (removalQueue):

            if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']) and removalQueue:
                print_info(red(" @@ ")+blue("These are the packages that would be ")+bold("removed")+blue(" (conflicting/substituted):"))

                for idpackage in removalQueue:
                    pkgatom = Equo.clientDbconn.retrieveAtom(idpackage)
                    onDiskFreedSize += Equo.clientDbconn.retrieveOnDiskSize(idpackage)
                    installedfrom = Equo.clientDbconn.retrievePackageFromInstalledTable(idpackage)
                    repoinfo = red("[")+brown("from: ")+bold(installedfrom)+red("] ")
                    print_info(red("   ## ")+"["+red("W")+"] "+repoinfo+enlightenatom(pkgatom))

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
            rc = Equo.askQuestion("     Would you like to run the queue ?")
            if rc == "No":
                dirscleanup()
                return 0,0
        if (etpUi['pretend']):
            dirscleanup()
            return 0,0

        # clear old resume information
        Equo.dumpTools.dumpobj(etpCache['install'],{})
        # store resume information
        if not tbz2: # .tbz2 install resume not supported
            resume_cache = {}
            resume_cache['removalQueue'] = removalQueue[:]
            resume_cache['runQueue'] = runQueue[:]
            resume_cache['onlyfetch'] = onlyfetch
            resume_cache['emptydeps'] = emptydeps
            resume_cache['deepdeps'] = deepdeps
            Equo.dumpTools.dumpobj(etpCache['install'],resume_cache)

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = Equo.dumpTools.loadobj(etpCache['install'])
        if not resume_cache: # None or {}

            print_error(red("Nothing to resume."))
            return 128,-1

        else:

            try:
                removalQueue = resume_cache['removalQueue'][:]
                runQueue = resume_cache['runQueue'][:]
                onlyfetch = resume_cache['onlyfetch']
                emptydeps = resume_cache['emptydeps']
                deepdeps = resume_cache['deepdeps']
                print_warning(red("Resuming previous operations..."))
            except:
                print_error(red("Resume cache corrupted."))
                Equo.dumpTools.dumpobj(etpCache['install'],{})
                return 128,-1

            if skipfirst and runQueue:
                runQueue, removalQueue, status = Equo.retrieveInstallQueue(runQueue[1:], emptydeps, deepdeps)
                # save new queues
                resume_cache['runQueue'] = runQueue[:]
                resume_cache['removalQueue'] = removalQueue[:]
                Equo.dumpTools.dumpobj(etpCache['install'],resume_cache)


    # running tasks
    totalqueue = str(len(runQueue))
    totalremovalqueue = str(len(removalQueue))
    currentqueue = 0
    currentremovalqueue = 0

    ### Before starting the real install, fetch packages and verify checksum.
    fetchqueue = 0
    for packageInfo in runQueue:
        fetchqueue += 1

        metaopts = {}
        metaopts['dochecksum'] = dochecksum
        Package = Equo.Package()
        Package.prepare(packageInfo,"fetch", metaopts)

        xterm_header = "Equo (fetch) :: "+str(fetchqueue)+" of "+totalqueue+" ::"
        print_info(red(" :: ")+bold("(")+blue(str(fetchqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.infoDict['atom']))

        rc = Package.run(xterm_header = xterm_header)
        if rc != 0:
            dirscleanup()
            return -1,rc
        Package.kill()

        del metaopts
        del Package

    if onlyfetch:
        print_info(red(" @@ ")+blue("Fetch Complete."))
        return 0,0

    for idpackage in removalQueue:
        currentremovalqueue += 1

        metaopts = {}
        metaopts['removeconfig'] = True
        Package = Equo.Package()
        Package.prepare((idpackage,),"remove", metaopts)

        xterm_header = "Equo (remove) :: "+str(currentremovalqueue)+" of "+totalremovalqueue+" ::"
        print_info(red(" -- ")+bold("(")+blue(str(currentremovalqueue))+"/"+red(totalremovalqueue)+bold(") ")+">>> "+darkgreen(Package.infoDict['removeatom']))

        rc = Package.run(xterm_header = xterm_header)
        if rc != 0:
            dirscleanup()
            return -1,rc

        # update resume cache
        if not tbz2: # tbz2 caching not supported
            resume_cache['removalQueue'].remove(Package.infoDict['removeidpackage'])
            Equo.dumpTools.dumpobj(etpCache['install'],resume_cache)

        Package.kill()
        del metaopts
        del Package

    for packageInfo in runQueue:
        currentqueue += 1

        metaopts = {}
        metaopts['removeconfig'] = configFiles
        Package = Equo.Package()
        Package.prepare(packageInfo,"install", metaopts)

        xterm_header = "Equo (install) :: "+str(currentqueue)+" of "+totalqueue+" ::"
        print_info(red(" ++ ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.infoDict['atom']))

        rc = Package.run(xterm_header = xterm_header)
        if rc != 0:
            dirscleanup()
            return -1,rc

        # there's a buffer inside, better remove otherwise cPickle will complain
        del Package.infoDict['triggers']

        # update resume cache
        if not tbz2: # tbz2 caching not supported
            resume_cache['runQueue'].remove(packageInfo)
            Equo.dumpTools.dumpobj(etpCache['install'],resume_cache)

        Package.kill()
        del metaopts
        del Package


    print_info(red(" @@ ")+blue("Install Complete."))
    # clear resume information
    Equo.dumpTools.dumpobj(etpCache['install'],{})
    dirscleanup()
    return 0,0


def removePackages(packages = [], atomsdata = [], deps = True, deep = False, systemPackagesCheck = True, configFiles = False, resume = False, human = False):

    # check if I am root
    if (not Equo.entropyTools.isRoot()):
        print_warning(red("Running with ")+bold("--pretend")+red("..."))
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
                print_warning(red("## ATTENTION -> package")+bold(" "+result[0]+" ")+red("is not installed."))
        foundAtoms = _foundAtoms

        # are packages in foundAtoms?
        if (not foundAtoms):
            print_error(red("No packages found"))
            return 125,-1

        plainRemovalQueue = []

        lookForOrphanedPackages = True
        # now print the selected packages
        print_info(red(" @@ ")+blue("These are the chosen packages:"))
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
                        print_warning(darkred("   # !!! ")+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+red(" is a vital package. Removal forbidden."))
                        continue
                else:
                    print_warning(darkred("   # !!! ")+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+red(" is a vital package. Removal forbidden."))
                    continue
            plainRemovalQueue.append(idpackage)

            print_info("   # "+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+" | Installed from: "+red(installedfrom))

        if (etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']):
            print_info(red(" @@ ")+blue("Number of packages: ")+str(totalatoms))

        if (not plainRemovalQueue):
            print_error(red("Nothing to do."))
            return 126,-1

        if (deps):
            question = "     Would you like to look for packages that can be removed along with the selected above?"
        else:
            question = "     Would you like to remove them now?"
            lookForOrphanedPackages = False

        if (etpUi['ask']):
            rc = Equo.askQuestion(question)
            if rc == "No":
                lookForOrphanedPackages = False
                if (not deps):
                    return 0,0

        removalQueue = []

        if (lookForOrphanedPackages):
            choosenRemovalQueue = []
            print_info(red(" @@ ")+blue("Calculating..."))
            choosenRemovalQueue = Equo.retrieveRemovalQueue(plainRemovalQueue, deep = deep)
            if choosenRemovalQueue:
                print_info(red(" @@ ")+blue("This is the new removal queue:"))
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

                removalQueue += choosenRemovalQueue

            else:
                writechar("\n")

        if (etpUi['ask']) or human:
            question = "     Would you like to proceed?"
            if human:
                question = "     Would you like to proceed with a selective removal ?"
            rc = Equo.askQuestion(question)
            if rc == "No":
                return 0,0
        elif (deps):
            Equo.entropyTools.countdown(what = red(" @@ ")+blue("Starting removal in "),back = True)

        for idpackage in plainRemovalQueue: # append at the end requested packages if not in queue
            if idpackage not in removalQueue:
                removalQueue.append(idpackage)

        # clear old resume information
        Equo.dumpTools.dumpobj(etpCache['remove'],{})
        # store resume information
        resume_cache = {}
        resume_cache['removalQueue'] = removalQueue[:]
        Equo.dumpTools.dumpobj(etpCache['remove'],resume_cache)

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = Equo.dumpTools.loadobj(etpCache['remove'])
        if not resume_cache: # None or {}
            print_error(red("Nothing to resume."))
            return 128,-1
        else:
            try:
                removalQueue = resume_cache['removalQueue'][:]
                print_warning(red("Resuming previous operations..."))
            except:
                print_error(red("Resume cache corrupted."))
                Equo.dumpTools.dumpobj(etpCache['remove'],{})
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

        metaopts = {}
        metaopts['removeconfig'] = configFiles
        Package = Equo.Package()
        Package.prepare((idpackage,),"remove", metaopts)

        xterm_header = "Equo (remove) :: "+str(currentqueue)+" of "+totalqueue+" ::"
        print_info(red(" -- ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.infoDict['removeatom']))

        # if human
        if human:
            rc = Equo.askQuestion("     Remove this one ?")
            if rc == "No":
                # update resume cache
                resume_cache['removalQueue'].remove(Package.infoDict['idpackage'])
                Equo.dumpTools.dumpobj(etpCache['remove'],resume_cache)
                Package.kill()
                del metaopts
                del Package
                continue

        rc = Package.run(xterm_header = xterm_header)
        if rc != 0:
            return -1,rc

        # update resume cache
        resume_cache['removalQueue'].remove(Package.infoDict['removeidpackage'])
        Equo.dumpTools.dumpobj(etpCache['remove'],resume_cache)

        Package.kill()
        del metaopts
        del Package

    print_info(red(" @@ ")+blue("All done."))
    return 0,0


def dependenciesTest():

    print_info(red(" @@ ")+blue("Running dependency test..."))
    depsNotMatched = Equo.dependencies_test()

    if depsNotMatched:
        print_info(red(" @@ ")+blue("These are the dependencies not found:"))
        for dep in depsNotMatched:
            print_info("   # "+red(dep))
        if (etpUi['ask']):
            rc = Equo.askQuestion("     Would you like to install the available packages?")
            if rc == "No":
                return 0,0
        else:
            print_info(red(" @@ ")+blue("Installing available packages in ")+red("10 seconds")+blue("..."))
            import time
            time.sleep(10)

        Equo.entropyTools.applicationLockCheck("install")
        installPackages(depsNotMatched)

    return 0,0

def librariesTest(listfiles = False):

    def restore_qstats():
        etpUi['mute'] = mstat
        etpUi['quiet'] = mquiet

    mstat = etpUi['mute']
    mquiet = etpUi['quiet']
    if listfiles:
        etpUi['mute'] = True
        etpUi['quiet'] = True

    packagesMatched, brokenlibs, status = Equo.libraries_test()
    if status != 0:
        restore_qstats()
        return -1,1

    if listfiles:
        for x in brokenlibs:
            print x
        restore_qstats()
        return 0,0

    if (not brokenlibs) and (not packagesMatched):
        if not etpUi['quiet']: print_info(red(" @@ ")+blue("System is healthy."))
        restore_qstats()
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
        restore_qstats()
        return 0,atomsdata

    if (etpUi['pretend']):
        restore_qstats()
        return 0,atomsdata

    if (atomsdata):
        if (etpUi['ask']):
            rc = Equo.askQuestion("     Would you like to install them?")
            if rc == "No":
                restore_qstats()
                return 0,atomsdata
        else:
            print_info(red(" @@ ")+blue("Installing found packages in ")+red("10 seconds")+blue("..."))
            import time
            time.sleep(10)

        Equo.entropyTools.applicationLockCheck("install")
        rc = installPackages(atomsdata = list(atomsdata))
        if rc[0] == 0:
            restore_qstats()
            return 0,atomsdata
        else:
            restore_qstats()
            return rc[0],atomsdata

    restore_qstats()
    return 0,atomsdata
