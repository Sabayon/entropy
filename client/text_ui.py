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

from entropyConstants import *
from outputTools import *
from entropy import EquoInterface
Equo = EquoInterface()
from entropy_i18n import _

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
            elif opt.endswith(".tbz2") and \
                os.path.isabs(opt) and \
                os.access(opt,os.R_OK) and \
                Equo.entropyTools.isEntropyTbz2(opt):
                    mytbz2paths.append(opt)
            elif opt.endswith(".tbz2"):
                continue
            elif opt.strip():
                _myopts.append(opt.strip())
    myopts = _myopts

    if (options[0] == "deptest"):
        rc, garbage = dependenciesTest()

    elif (options[0] == "libtest"):
        rc, garbage = librariesTest(listfiles = equoRequestListfiles)

    elif (options[0] == "install"):
        if (myopts) or (mytbz2paths) or (equoRequestResume):
            status, rc = installPackages(myopts, deps = equoRequestDeps, emptydeps = equoRequestEmptyDeps, onlyfetch = equoRequestOnlyFetch, deepdeps = equoRequestDeep, configFiles = equoRequestConfigFiles, tbz2 = mytbz2paths, resume = equoRequestResume, skipfirst = equoRequestSkipfirst, dochecksum = equoRequestChecksum)
        else:
            print_error(red(" %s." % (_("Nothing to do"),) ))
            rc = 127

    elif (options[0] == "world"):
        status, rc = worldUpdate(onlyfetch = equoRequestOnlyFetch, replay = (equoRequestReplay or equoRequestEmptyDeps), upgradeTo = equoRequestUpgradeTo, resume = equoRequestResume, skipfirst = equoRequestSkipfirst, human = True, dochecksum = equoRequestChecksum)

    elif (options[0] == "remove"):
        if myopts or equoRequestResume:
            status, rc = removePackages(myopts, deps = equoRequestDeps, deep = equoRequestDeep, configFiles = equoRequestConfigFiles, resume = equoRequestResume)
        else:
            print_error(red(" %s." % (_("Nothing to do"),) ))
            rc = 127
    else:
        rc = -10

    return rc


def worldUpdate(onlyfetch = False, replay = False, upgradeTo = None, resume = False, skipfirst = False, human = False, dochecksum = True):

    # check if I am root
    if (not Equo.entropyTools.isRoot()):
        mytxt = "%s %s %s" % (_("Running with"),bold("--pretend"),red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    if not resume:

        # verify selected release (branch)
        if upgradeTo:
            # set the new branch
            result = Equo.move_to_branch(upgradeTo, pretend = etpUi['pretend'])
            if result == 1:
                print_error(red("%s: " % (_("Selected release"),) ) + bold(str(upgradeTo)) + \
                    red(" %s." % (_("is not available"),) )
                )
                return 1,-2
            branch = upgradeTo
        else:
            branch = etpConst['branch']

        print_info(red(" @@ ")+blue("%s..." % (_("Calculating System Updates"),) ))
        update, remove, fine = Equo.calculate_world_updates(empty_deps = replay, branch = branch)

        if (etpUi['verbose'] or etpUi['pretend']):
            print_info(red(" @@ ")+darkgreen("%s:\t\t" % (_("Packages matching update"),) )+bold(str(len(update))))
            print_info(red(" @@ ")+darkred("%s:\t\t" % (_("Packages matching not available"),) )+bold(str(len(remove))))
            print_info(red(" @@ ")+blue("%s:\t" % (_("Packages matching already up to date"),) )+bold(str(len(fine))))

        del fine

        # clear old resume information
        if etpConst['uid'] == 0:
            try:
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
            except (OSError,IOError):
                pass

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = Equo.dumpTools.loadobj(etpCache['world'])
        if (not resume_cache) or (etpConst['uid'] != 0): # None or {}
            print_error(red("%s." % (_("Nothing to resume"),) ))
            return 128,-1
        else:
            try:
                update = []
                remove = resume_cache['remove']
                etpUi['ask'] = resume_cache['ask']
                etpUi['verbose'] = resume_cache['verbose']
                onlyfetch = resume_cache['onlyfetch']
                Equo.dumpTools.dumpobj(etpCache['remove'],list(remove))
            except (OSError,IOError,KeyError):
                print_error(red("%s." % (_("Resume cache corrupted"),) ))
                try:
                    Equo.dumpTools.dumpobj(etpCache['world'],{})
                    Equo.dumpTools.dumpobj(etpCache['install'],{})
                    Equo.dumpTools.dumpobj(etpCache['remove'],[])
                except (OSError,IOError):
                    pass
                return 128,-1

    # disable collisions protection, better
    oldcollprotect = etpConst['collisionprotect']
    etpConst['collisionprotect'] = 1

    if (update) or (resume):
        rc = installPackages(atomsdata = update, onlyfetch = onlyfetch, resume = resume, skipfirst = skipfirst, dochecksum = dochecksum)
        if rc[1] != 0:
            return 1,rc[0]
    else:
        print_info(red(" @@ ")+blue("%s." % (_("Nothing to update"),) ))

    etpConst['collisionprotect'] = oldcollprotect

    # verify that client database idpackage still exist, validate here before passing removePackage() wrong info
    remove = [x for x in remove if Equo.clientDbconn.isIDPackageAvailable(x)]

    if (remove):
        remove = list(remove)
        remove.sort()
        print_info(red(" @@ ") + \
            blue("%s." % (
                    _("On the system there are packages that are not available anymore in the online repositories"),
                )
            )
        )
        print_info(red(" @@ ")+blue(_("Even if they are usually harmless, it is suggested to remove them.")))

        if (not etpUi['pretend']):
            if human:
                rc = Equo.askQuestion("     %s" % (_("Would you like to scan them ?"),) )
                if rc == "No":
                    return 0,0

            # run removePackages with --nodeps
            removePackages(
                atomsdata = remove,
                deps = False,
                systemPackagesCheck = False,
                configFiles = True,
                resume = resume,
                human = human
            )
        else:
            print_info(red(" @@ ")+blue("%s." % (_("Calculation complete"),) ))

    else:
        print_info(red(" @@ ")+blue("%s." % (_("Nothing to remove"),) ))

    return 0,0

def installPackages(packages = [], atomsdata = [], deps = True, emptydeps = False, onlyfetch = False, deepdeps = False, configFiles = False, tbz2 = [], resume = False, skipfirst = False, dochecksum = True):

    # check if I am root
    if (not Equo.entropyTools.isRoot()):
        mytxt = "%s %s %s" % (_("Running with"),bold("--pretend"),red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    etpSys['dirstoclean'].clear()
    def dirscleanup():
        for x in etpSys['dirstoclean']:
            try:
                if os.path.isdir(x): Equo.shutil.rmtree(x)
            except:
                pass
        etpSys['dirstoclean'].clear()

    if not resume:

        if (atomsdata):
            foundAtoms = atomsdata
        else:
            foundAtoms = []
            for package in packages:
                # clear masking reasons
                maskingReasonsStorage.clear()
                match = Equo.atomMatch(package)
                if match[0] == -1:
                    reasons = maskingReasonsStorage.get(package)
                    if reasons != None:
                        keyreasons = reasons.keys()
                        mytxt = "%s %s %s %s." % (
                            bold("!!!"),
                            red(_("Every package matching")), # every package matching app-foo is masked
                            bold(package),
                            red(_("is masked")),
                        )
                        print_warning(mytxt)
                        for key in keyreasons:
                            reason = etpConst['packagemaskingreasons'][key]
                            print_warning(bold("    # ")+red("Reason: ")+blue(reason))
                            masked_packages = reasons[key]
                            for m_match in masked_packages:
                                dbconn = Equo.openRepositoryDatabase(m_match[1])
                                try:
                                    m_atom = dbconn.retrieveAtom(m_match[0])
                                except TypeError:
                                    m_atom = "idpackage: %s %s %s %s" % (
                                        m_match[0],
                                        _("matching"),
                                        package,
                                        _("is broken"),
                                    )
                                print_warning(blue("      <> ")+red("%s: " % (_("atom"),) )+brown(m_atom))
                    else:
                        mytxt = "%s %s %s %s." % (
                            bold("!!!"),
                            red(_("No match for")),
                            bold(package),
                            red(_("in repositories")),
                        )
                        print_warning(mytxt)
                        # search similar packages
                        # you meant...?
                        if len(package) < 4:
                            continue
                        items = Equo.get_meant_packages(package)
                        if items:
                            items_cache = set()
                            mytxt = "%s %s %s %s %s." % (
                                bold("   ?"),
                                red(_("When you wrote")),
                                bold(package),
                                darkgreen(_("You Meant(tm)")),
                                red(_("one of these below?")),
                            )
                            print_info(mytxt)
                            for match in items:
                                dbc = Equo.openRepositoryDatabase(match[1])
                                key, slot = dbc.retrieveKeySlot(match[0])
                                if (key,slot) not in items_cache:
                                    print_info(red("    # ")+blue(key)+":"+brown(str(slot))+red(" ?"))
                                items_cache.add((key, slot))
                            del items_cache
                    continue
                foundAtoms.append(match)
            if tbz2:
                for pkg in tbz2:
                    status, atomsfound = Equo.add_tbz2_to_repos(pkg)
                    if status == 0:
                        foundAtoms += atomsfound[:]
                        del atomsfound
                    elif status in (-1,-2,-3,):
                        errtxt = _("is not a valid Entropy package")
                        if status == -3:
                            errtxt = _("is not compiled with the same architecture of the system")
                        mytxt = "## %s: %s %s. %s ..." % (
                            red(_("ATTENTION")),
                            bold(os.path.basename(pkg)),
                            red(errtxt),
                            red(_("Skipped")),
                        )
                        print_warning(mytxt)
                        continue
                    else:
                        raise exceptionTools.InvalidDataType("InvalidDataType: ??????")

        # are there packages in foundAtoms?
        if (not foundAtoms):
            print_error( red("%s." % (_("No packages found"),) ))
            dirscleanup()
            return 127,-1

        if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
            # now print the selected packages
            print_info(red(" @@ ")+blue("%s:" % (_("These are the chosen packages"),) ))
            totalatoms = len(foundAtoms)
            atomscounter = 0
            for idpackage,reponame in foundAtoms:
                atomscounter += 1
                # open database
                dbconn = Equo.openRepositoryDatabase(reponame)

                # get needed info
                pkgatom = dbconn.retrieveAtom(idpackage)
                if not pkgatom:
                    continue

                pkgver = dbconn.retrieveVersion(idpackage)
                pkgtag = dbconn.retrieveVersionTag(idpackage)
                if not pkgtag:
                    pkgtag = "NoTag"
                pkgrev = dbconn.retrieveRevision(idpackage)
                pkgslot = dbconn.retrieveSlot(idpackage)

                # client info
                installedVer = _("Not installed")
                installedTag = "NoTag"
                installedRev = "NoRev"
                installedRepo = _("Not available")
                pkginstalled = Equo.clientDbconn.atomMatch(Equo.entropyTools.dep_getkey(pkgatom), matchSlot = pkgslot)
                if (pkginstalled[1] == 0):
                    # found
                    idx = pkginstalled[0]
                    installedVer = Equo.clientDbconn.retrieveVersion(idx)
                    installedTag = Equo.clientDbconn.retrieveVersionTag(idx)
                    installedRepo = Equo.clientDbconn.retrievePackageFromInstalledTable(idx)
                    if not installedTag:
                        installedTag = "NoTag"
                    installedRev = Equo.clientDbconn.retrieveRevision(idx)

                print_info("   # "+red("(")+bold(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+bold(pkgatom)+" >>> "+red(etpRepositories[reponame]['description']))
                mytxt = "\t%s:\t %s / %s / %s %s %s / %s / %s" % (
                    red(_("Versions")),
                    blue(installedVer),
                    blue(installedTag),
                    blue(str(installedRev)),
                    bold("===>"),
                    darkgreen(pkgver),
                    darkgreen(pkgtag),
                    darkgreen(str(pkgrev)),
                )
                print_info(mytxt)
                # tell wether we should update it
                is_installed = True
                if installedVer == _("Not installed"):
                    is_installed = False
                    installedVer = "0"
                if installedRev == "NoRev":
                    installedRev = 0
                pkgcmp = Equo.entropyTools.entropyCompareVersions(
                    (pkgver,pkgtag,pkgrev,),
                    (installedVer,installedTag,installedRev,)
                )
                if (pkgcmp == 0):
                    if installedRepo != reponame:
                        mytxt = " | %s: " % (_("Switch repo"),)
                        action = darkgreen(_("Reinstall"))+mytxt+blue(installedRepo)+" ===> "+darkgreen(reponame)
                    else:
                        action = darkgreen(_("Reinstall"))
                elif (pkgcmp > 0) or (not is_installed):
                    if (installedVer == "0"):
                        action = darkgreen(_("Install"))
                    else:
                        action = blue(_("Upgrade"))
                else:
                    action = red(_("Downgrade"))
                print_info("\t"+red("%s:\t\t" % (_("Action"),) )+" "+action)

            if (etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']):
                print_info(red(" @@ ")+blue("%s: " % (_("Packages involved"),) )+str(totalatoms))

            if deps:
                if (etpUi['ask']):
                    rc = Equo.askQuestion("     %s" % (_("Would you like to continue with dependencies calculation ?"),) )
                    if rc == "No":
                        dirscleanup()
                        return 0,0

        runQueue = []
        removalQueue = [] # aka, conflicts

        if deps:
            print_info(red(" @@ ")+blue("%s ...") % (_("Calculating dependencies"),) )
            runQueue, removalQueue, status = Equo.retrieveInstallQueue(foundAtoms, emptydeps, deepdeps)
            if status == -2:

                print_error(red(" @@ ")+blue("%s: " % (_("Cannot find needed dependencies"),) ))
                for x in runQueue:
                    reasons = maskingReasonsStorage.get(x)
                    if reasons != None:
                        keyreasons = reasons.keys()
                        for key in keyreasons:
                            reason = etpConst['packagemaskingreasons'][key]
                            print_warning(bold("    # ")+red("%s: " % (_("Reason"),) )+blue(reason))
                            masked_packages = reasons[key]
                            for m_match in masked_packages:
                                dbconn = Equo.openRepositoryDatabase(m_match[1])
                                m_atom = dbconn.retrieveAtom(m_match[0])
                                print_warning(blue("      <> ")+red("%s: " % (_("atom"),) )+brown(m_atom))
                    else:
                        print_error(red("    # ")+blue("%s: " % (_("Not found"),) )+brown(x))
                        crying_atoms = Equo.find_belonging_dependency([x])
                        if crying_atoms:
                            print_error(red("      # ")+blue("%s:" % (_("Probably needed by"),) ))
                            for crying_atomdata in crying_atoms:
                                print_error(red("        # ")+" ["+blue(_("from"))+":"+brown(crying_atomdata[1])+"] "+darkred(crying_atomdata[0]))

                dirscleanup()
                return 127, -1
        else:
            for atomInfo in foundAtoms:
                runQueue.append(atomInfo)

        if ((not runQueue) and (not removalQueue)):
            print_error(red("%s." % (_("Nothing to do"),) ))
            dirscleanup()
            return 126,-1

        downloadSize = 0
        unpackSize = 0
        onDiskUsedSize = 0
        onDiskFreedSize = 0
        pkgsToInstall = 0
        pkgsToUpdate = 0
        pkgsToReinstall = 0
        pkgsToDowngrade = 0
        pkgsToRemove = len(removalQueue)

        if (runQueue):
            if (etpUi['ask'] or etpUi['pretend']):
                mytxt = "%s %s:" % (blue(_("These are the packages that would be")),bold(_("merged")),)
                print_info(red(" @@ ")+mytxt)

            count = 0
            for idpackage,reponame in runQueue:
                count += 1

                dbconn = Equo.openRepositoryDatabase(reponame)
                pkgatom = dbconn.retrieveAtom(idpackage)
                if not pkgatom:
                    continue
                pkgver = dbconn.retrieveVersion(idpackage)
                pkgtag = dbconn.retrieveVersionTag(idpackage)
                pkgrev = dbconn.retrieveRevision(idpackage)
                pkgslot = dbconn.retrieveSlot(idpackage)
                pkgfile = dbconn.retrieveDownloadURL(idpackage)
                onDiskUsedSize += dbconn.retrieveOnDiskSize(idpackage)

                dl = Equo.check_needed_package_download(pkgfile, None) # we'll do a good check during installPackage
                pkgsize = dbconn.retrieveSize(idpackage)
                unpackSize += int(pkgsize)*2
                if dl < 0:
                    downloadSize += int(pkgsize)
                else:
                    try:
                        f = open(etpConst['entropyworkdir']+"/"+pkgfile,"r")
                        f.seek(0,2)
                        currsize = f.tell()
                        pkgsize = dbconn.retrieveSize(idpackage)
                        downloadSize += int(pkgsize)-int(currsize)
                        f.close()
                    except:
                        pass

                # get installed package data
                installedVer = '-1'
                installedTag = ''
                installedRev = 0
                installedRepo = _('Not available')
                pkginstalled = Equo.clientDbconn.atomMatch(Equo.entropyTools.dep_getkey(pkgatom), matchSlot = pkgslot)
                if (pkginstalled[1] == 0):
                    # found an installed package
                    idx = pkginstalled[0]
                    installedVer = Equo.clientDbconn.retrieveVersion(idx)
                    installedTag = Equo.clientDbconn.retrieveVersionTag(idx)
                    installedRev = Equo.clientDbconn.retrieveRevision(idx)
                    installedRepo = Equo.clientDbconn.retrievePackageFromInstalledTable(idx)
                    onDiskFreedSize += Equo.clientDbconn.retrieveOnDiskSize(idx)

                if not (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
                    continue

                action = 0
                repoSwitch = False
                if reponame != installedRepo:
                    repoSwitch = True
                if repoSwitch:
                    flags = darkred(" [")
                else:
                    flags = " ["
                pkgcmp = Equo.entropyTools.entropyCompareVersions((pkgver,pkgtag,pkgrev),(installedVer,installedTag,installedRev))
                if (pkgcmp == 0):
                    pkgsToReinstall += 1
                    flags += red("R")
                    action = 1
                elif (pkgcmp > 0):
                    if (installedVer == "-1"):
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
                if repoSwitch:
                    flags += darkred("] ")
                else:
                    flags += "] "

                if repoSwitch:
                    repoinfo = "["+brown(installedRepo)+"->"+darkred(reponame)+"] "
                else:
                    repoinfo = "["+brown(reponame)+"] "
                oldinfo = ''
                if action != 0:
                    oldinfo = "   ["+blue(installedVer)+"|"+red(str(installedRev))
                    oldtag = "]"
                    if installedTag:
                        oldtag = "|"+darkred(installedTag)+oldtag
                    oldinfo += oldtag

                print_info(darkred(" ##")+flags+repoinfo+blue(pkgatom)+"|"+red(str(pkgrev))+oldinfo)

        deltaSize = onDiskUsedSize - onDiskFreedSize
        neededSize = deltaSize
        if unpackSize > 0: neededSize += unpackSize

        if removalQueue:

            if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']) and removalQueue:
                mytxt = "%s %s (%s):" % (
                    blue(_("These are the packages that would be")),
                    bold(_("removed")),
                    blue(_("conflicting/substituted")),
                )
                print_info(red(" @@ ")+mytxt)

                for idpackage in removalQueue:
                    pkgatom = Equo.clientDbconn.retrieveAtom(idpackage)
                    if not pkgatom:
                        continue
                    onDiskFreedSize += Equo.clientDbconn.retrieveOnDiskSize(idpackage)
                    installedfrom = Equo.clientDbconn.retrievePackageFromInstalledTable(idpackage)
                    repoinfo = red("[")+brown("%s: " % (_("from"),) )+bold(installedfrom)+red("] ")
                    print_info(red("   ## ")+"["+red("W")+"] "+repoinfo+enlightenatom(pkgatom))

        if (runQueue) or (removalQueue) and not etpUi['quiet']:
            # show download info
            mytxt = "%s: %s" % (blue(_("Packages needing to be installed/updated/downgraded")),red(str(len(runQueue))),)
            print_info(red(" @@ ")+mytxt)
            mytxt = "%s: %s" % (blue(_("Packages needing to be removed")),red(str(pkgsToRemove)),)
            print_info(red(" @@ ")+mytxt)
            if (etpUi['ask'] or etpUi['verbose'] or etpUi['pretend']):
                mytxt = "%s: %s" % (
                    darkgreen(_("Packages needing to be installed")),
                    darkgreen(str(pkgsToInstall)),
                )
                print_info(red(" @@ ")+mytxt)
                mytxt = "%s: %s" % (
                    brown(_("Packages needing to be reinstalled")),
                    brown(str(pkgsToReinstall)),
                )
                print_info(red(" @@ ")+mytxt)
                mytxt = "%s: %s" % (
                    blue(_("Packages needing to be updated")),
                    blue(str(pkgsToUpdate)),
                )
                print_info(red(" @@ ")+mytxt)
                mytxt = "%s: %s" % (
                    red(_("Packages needing to be downgraded")),
                    red(str(pkgsToUpdate)),
                )
                print_info(red(" @@ ")+mytxt)

            if downloadSize > 0:
                mysize = str(Equo.entropyTools.bytesIntoHuman(downloadSize))
            else:
                mysize = "0b"
            mytxt = "%s: %s" % (
                blue(_("Download size")),
                bold(mysize),
            )
            print_info(red(" @@ ")+mytxt)

            if deltaSize > 0:
                mysizetxt = _("Used disk space")
            else:
                mysizetxt = _("Freed disk space")
                deltaSize = deltaSize*-1
            mytxt = "%s: %s" % (
                blue(mysizetxt),
                bold(str(Equo.entropyTools.bytesIntoHuman(deltaSize))),
            )
            print_info(red(" @@ ")+mytxt)

            mytxt = "%s: %s %s" % (
                blue(_("You need at least")),
                blue(str(Equo.entropyTools.bytesIntoHuman(neededSize))),
                _("of free space"),
            )
            print_info(red(" @@ ")+mytxt)
            # check for disk space and print a warning
            ## unpackSize
            size_match = Equo.entropyTools.check_required_space(etpConst['entropyunpackdir'],neededSize)
            if not size_match:
                mytxt = "%s: %s" % (
                    _("You don't have enough space for the installation. Free some space into"),
                    etpConst['entropyunpackdir'],
                )
                print_info(darkred(" !!! ")+bold(_("Attention")))
                print_info(darkred(" !!! ")+bold(_("Attention")))
                print_info(darkred(" !!! ")+blue(mytxt))
                print_info(darkred(" !!! ")+bold(_("Attention")))
                print_info(darkred(" !!! ")+bold(_("Attention")))

        if (etpUi['ask']):
            rc = Equo.askQuestion("     %s" % (_("Would you like to execute the queue ?"),) )
            if rc == "No":
                dirscleanup()
                return 0,0
        if (etpUi['pretend']):
            dirscleanup()
            return 0,0

        try:
            # clear old resume information
            Equo.dumpTools.dumpobj(etpCache['install'],{})
            # store resume information
            if not tbz2: # .tbz2 install resume not supported
                resume_cache = {}
                #resume_cache['removalQueue'] = removalQueue[:]
                resume_cache['runQueue'] = runQueue[:]
                resume_cache['onlyfetch'] = onlyfetch
                resume_cache['emptydeps'] = emptydeps
                resume_cache['deepdeps'] = deepdeps
                Equo.dumpTools.dumpobj(etpCache['install'],resume_cache)
        except (IOError,OSError):
            pass

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = Equo.dumpTools.loadobj(etpCache['install'])
        if not resume_cache: # None or {}

            print_error(red("%s." % (_("Nothing to resume"),) ))
            return 128,-1

        else:

            try:
                #removalQueue = resume_cache['removalQueue'][:]
                runQueue = resume_cache['runQueue'][:]
                onlyfetch = resume_cache['onlyfetch']
                emptydeps = resume_cache['emptydeps']
                deepdeps = resume_cache['deepdeps']
                print_warning(red("%s..." % (_("Resuming previous operations"),) ))
            except:
                print_error(red("%s." % (_("Resume cache corrupted"),) ))
                try:
                    Equo.dumpTools.dumpobj(etpCache['install'],{})
                except (IOError,OSError):
                    pass
                return 128,-1

            if skipfirst and runQueue:
                runQueue, x, status = Equo.retrieveInstallQueue(runQueue[1:], emptydeps, deepdeps)
                del x # was removalQueue
                # save new queues
                resume_cache['runQueue'] = runQueue
                try:
                    Equo.dumpTools.dumpobj(etpCache['install'],resume_cache)
                except (IOError,OSError):
                    pass

    # running tasks
    totalqueue = str(len(runQueue))
    currentqueue = 0

    def read_lic_selection():
        print_info(darkred("    %s" % (_("Please select an option"),) ))
        print_info("      ("+blue("1")+")"+darkgreen(" %s" % (_("Read the license"),) ))
        print_info("      ("+blue("2")+")"+brown(" %s" % (_("Accept the license (I've read it)"),) ))
        print_info("      ("+blue("3")+")"+darkred(" %s" % (_("Accept the license and don't ask anymore (I've read it)"),) ))
        print_info("      ("+blue("0")+")"+bold(" %s" % (_("Quit"),) ))
        # wait user interaction
        action = readtext("       %s: " % (_("Your choice (type a number and press enter)"),) )
        return action

    ### Before even starting the fetch, make sure that the user accepts their licenses
    licenses = Equo.get_licenses_to_accept(runQueue)
    # is there ACCEPT_LICENSE in ENV?
    myaccept_license = os.getenv("ACCEPT_LICENSE")
    if myaccept_license:
        myaccept_license = myaccept_license.split()
        for mylic in myaccept_license:
            if mylic in licenses:
                licenses.pop(mylic)
    if licenses:
        print_info(red(" @@ ")+blue("%s:" % (_("You need to accept the licenses below"),) ))
        keys = licenses.keys()
        keys.sort()
        for key in keys:
            print_info(red("    :: %s: " % (_("License"),) )+bold(key)+red(", %s:" % (_("needed by"),) ))
            for match in licenses[key]:
                dbconn = Equo.openRepositoryDatabase(match[1])
                atom = dbconn.retrieveAtom(match[0])
                print_info(blue("       ## ")+"["+brown(_("from"))+":"+red(match[1])+"] "+bold(atom))
            while 1:
                choice = read_lic_selection()
                try:
                    choice = int(choice)
                except (ValueError,EOFError,TypeError):
                    continue
                if choice not in (0,1,2,3):
                    continue
                if choice == 0:
                    dirscleanup()
                    return 0,0
                elif choice == 1: # read
                    filename = Equo.get_text_license(key, match[1])
                    viewer = Equo.get_file_viewer()
                    if viewer == None:
                        print_info(red("    %s ! %s %s " % (_("No file viewer"),_("License saved into"),filename,) ))
                        continue
                    os.system(viewer+" "+filename)
                    os.remove(filename)
                    continue
                elif choice == 2:
                    break
                elif choice == 3:
                    Equo.clientDbconn.acceptLicense(key)
                    break

    if not etpUi['clean'] or onlyfetch:
        ### Before starting the real install, fetch packages and verify checksum.
        fetchqueue = 0
        for packageInfo in runQueue:
            fetchqueue += 1

            metaopts = {}
            metaopts['dochecksum'] = dochecksum
            Package = Equo.Package()
            Package.prepare(packageInfo,"fetch", metaopts)

            xterm_header = "Equo ("+_("fetch")+") :: "+str(fetchqueue)+" of "+totalqueue+" ::"
            print_info(red(" :: ")+bold("(")+blue(str(fetchqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.infoDict['atom']))

            rc = Package.run(xterm_header = xterm_header)
            if rc != 0:
                dirscleanup()
                return -1,rc
            Package.kill()

            del metaopts
            del Package

    if onlyfetch:
        print_info(red(" @@ ")+blue("%s." % (_("Download completed"),) ))
        return 0,0

    for packageInfo in runQueue:
        currentqueue += 1

        metaopts = {}
        metaopts['removeconfig'] = configFiles
        Package = Equo.Package()
        Package.prepare(packageInfo,"install", metaopts)

        xterm_header = "Equo ("+_("install")+") :: "+str(currentqueue)+" of "+totalqueue+" ::"
        print_info(red(" ++ ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.infoDict['atom']))

        rc = Package.run(xterm_header = xterm_header)
        if rc != 0:
            dirscleanup()
            return -1,rc

        # there's a buffer inside, better remove otherwise cPickle will complain
        del Package.infoDict['triggers']

        if etpUi['clean']: # remove downloaded package
            if os.path.isfile(Package.infoDict['pkgpath']):
                os.remove(Package.infoDict['pkgpath'])

        # update resume cache
        if not tbz2: # tbz2 caching not supported
            resume_cache['runQueue'].remove(packageInfo)
            try:
                Equo.dumpTools.dumpobj(etpCache['install'],resume_cache)
            except (IOError,OSError):
                pass

        Package.kill()
        del metaopts
        del Package


    print_info(red(" @@ ")+blue("%s." % (_("Installation completed"),) ))
    try:
        # clear resume information
        Equo.dumpTools.dumpobj(etpCache['install'],{})
    except (IOError,OSError):
        pass
    dirscleanup()
    return 0,0


def removePackages(packages = [], atomsdata = [], deps = True, deep = False, systemPackagesCheck = True, configFiles = False, resume = False, human = False):

    # check if I am root
    if (not Equo.entropyTools.isRoot()):
        mytxt = "%s %s %s" % (_("Running with"),bold("--pretend"),red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    doSelectiveRemoval = False

    if not resume:

        foundAtoms = []
        if atomsdata:
            for idpackage in atomsdata:
                if not Equo.clientDbconn.isIDPackageAvailable(idpackage):
                    continue
                foundAtoms.append(idpackage)
        else:
            for package in packages:
                idpackage, result = Equo.clientDbconn.atomMatch(package)
                if idpackage == -1:
                    mytxt = "## %s: %s %s." % (
                        red(_("ATTENTION")),
                        bold(package),
                        red(_("is not installed")),
                    )
                    print_warning(mytxt)
                    continue
                foundAtoms.append(idpackage)

        if not foundAtoms:
            print_error(red("%s." % (_("No packages found"),) ))
            return 125,-1

        plainRemovalQueue = []

        lookForOrphanedPackages = True
        # now print the selected packages
        print_info(red(" @@ ")+blue("%s:" % (_("These are the chosen packages"),) ))
        totalatoms = len(foundAtoms)
        atomscounter = 0
        for idpackage in foundAtoms:
            atomscounter += 1

            # get needed info
            pkgatom = Equo.clientDbconn.retrieveAtom(idpackage)
            if not pkgatom:
                continue

            if systemPackagesCheck:
                valid = Equo.validatePackageRemoval(idpackage)
                if not valid:
                    mytxt = "   %s (%s/%s) %s: %s. %s." % (
                        bold("!!!"),
                        brown(str(atomscounter)),
                        blue(str(totalatoms)),
                        enlightenatom(pkgatom), # every package matching app-foo is masked
                        red(_("vital package")),
                        red(_("Removal forbidden")),
                    )
                    print_warning(mytxt)
                    continue

            plainRemovalQueue.append(idpackage)

            installedfrom = Equo.clientDbconn.retrievePackageFromInstalledTable(idpackage)
            disksize = Equo.clientDbconn.retrieveOnDiskSize(idpackage)
            disksize = Equo.entropyTools.bytesIntoHuman(disksize)
            disksizeinfo = " | %s: %s" % (blue(_("Disk size")),bold(str(disksize)),)
            mytxt = " | %s: " % (_("Installed from"),)
            print_info("   # "+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+mytxt+red(installedfrom)+disksizeinfo)

        if (etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']):
            print_info(red(" @@ ")+blue("%s: " % (_("Packages involved"),) )+str(totalatoms))

        if (not plainRemovalQueue):
            print_error(red("%s." % (_("Nothing to do"),) ))
            return 126,-1

        if (deps):
            question = "     %s" % (
                _("Would you like to look for packages that can be removed along with the selected above ?"),
            )
        else:
            question = "     %s" % (_("Would you like to remove them now ?"),)
            lookForOrphanedPackages = False

        if (etpUi['ask']):
            rc = Equo.askQuestion(question)
            if rc == "No":
                lookForOrphanedPackages = False
                if (not deps):
                    return 0,0

        removalQueue = []

        if lookForOrphanedPackages:
            choosenRemovalQueue = []
            choosenRemovalQueue = Equo.retrieveRemovalQueue(plainRemovalQueue, deep = deep)
            if choosenRemovalQueue:
                print_info(red(" @@ ")+blue("%s:" % (_("This is the new removal queue"),) ))
                totalatoms = str(len(choosenRemovalQueue))
                atomscounter = 0

                for idpackage in choosenRemovalQueue:
                    atomscounter += 1
                    rematom = Equo.clientDbconn.retrieveAtom(idpackage)
                    if not rematom:
                        continue
                    installedfrom = Equo.clientDbconn.retrievePackageFromInstalledTable(idpackage)
                    disksize = Equo.clientDbconn.retrieveOnDiskSize(idpackage)
                    disksize = Equo.entropyTools.bytesIntoHuman(disksize)
                    repositoryInfo = bold("[")+darkgreen("%s:" % (_("from"),) )+brown(installedfrom)+bold("]")
                    stratomscounter = str(atomscounter)
                    while len(stratomscounter) < len(totalatoms):
                        stratomscounter = " "+stratomscounter
                    disksizeinfo = bold(" [")+red(str(disksize))+bold("]")
                    print_info("   # "+red("(")+bold(stratomscounter)+"/"+blue(str(totalatoms))+red(")")+repositoryInfo+" "+blue(rematom)+disksizeinfo)

                removalQueue = choosenRemovalQueue

            else:
                writechar("\n")

        if (etpUi['ask']) or human:
            question = "     %s" % (_("Would you like to proceed ?"),)
            if human:
                question = "     %s" % (_("Would you like to proceed with a selective removal ?"),)
            rc = Equo.askQuestion(question)
            if rc == "No" and not human:
                return 0,0
            elif rc == "Yes" and human:
                doSelectiveRemoval = True
            elif rc == "No" and human:
                rc = Equo.askQuestion("     %s") % (_("Would you like to skip this step then ?"),)
                if rc == "Yes":
                    return 0,0
        elif deps:
            Equo.entropyTools.countdown(
                what = red(" @@ ")+blue("%s " % (_("Starting removal in"),)),
                back = True
            )

        for idpackage in plainRemovalQueue: # append at the end requested packages if not in queue
            if idpackage not in removalQueue:
                removalQueue.append(idpackage)

        # clear old resume information
        try:
            Equo.dumpTools.dumpobj(etpCache['remove'],{})
            # store resume information
            resume_cache = {}
            resume_cache['doSelectiveRemoval'] = doSelectiveRemoval
            resume_cache['removalQueue'] = removalQueue
            Equo.dumpTools.dumpobj(etpCache['remove'],resume_cache)
        except (OSError, IOError, EOFError):
            pass

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = Equo.dumpTools.loadobj(etpCache['remove'])
        if not resume_cache: # None or {}
            print_error(red("%s." % (_("Nothing to resume"),) ))
            return 128,-1
        else:
            try:
                removalQueue = resume_cache['removalQueue'][:]
                doSelectiveRemoval = resume_cache['doSelectiveRemoval']
                print_warning(red("%s..." % (_("Resuming previous operations"),) ))
            except:
                print_error(red("%s." % (_("Resume cache corrupted"),) ))
                try:
                    Equo.dumpTools.dumpobj(etpCache['remove'],{})
                except (OSError, IOError):
                    pass
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

    # ask which ones to remove
    if human:
        ignored = []
        for idpackage in removalQueue:
            currentqueue += 1
            atom = Equo.clientDbconn.retrieveAtom(idpackage)
            if not atom:
                continue
            print_info(red(" -- ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(atom))
            if doSelectiveRemoval:
                rc = Equo.askQuestion("     %s" % (_("Remove this one ?"),) )
                if rc == "No":
                    # update resume cache
                    ignored.append(idpackage)
        removalQueue = [x for x in removalQueue if x not in ignored]

    totalqueue = str(len(removalQueue))
    currentqueue = 0
    for idpackage in removalQueue:
        currentqueue += 1

        metaopts = {}
        metaopts['removeconfig'] = configFiles
        Package = Equo.Package()
        Package.prepare((idpackage,),"remove", metaopts)
        if not Package.infoDict.has_key('remove_installed_vanished'):

            xterm_header = "Equo (remove) :: "+str(currentqueue)+" of "+totalqueue+" ::"
            print_info(red(" -- ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.infoDict['removeatom']))

            rc = Package.run(xterm_header = xterm_header)
            if rc != 0:
                return -1,rc

        # update resume cache
        if idpackage in resume_cache['removalQueue']:
            resume_cache['removalQueue'].remove(idpackage)
        try:
            Equo.dumpTools.dumpobj(etpCache['remove'],resume_cache)
        except (OSError,IOError,EOFError):
            pass

        Package.kill()
        del metaopts
        del Package

    print_info(red(" @@ ")+blue("%s." % (_("All done"),) ))
    return 0,0


def dependenciesTest():

    print_info(red(" @@ ")+blue("%s ..." % (_("Running dependency test"),) ))
    depsNotMatched = Equo.dependencies_test()

    if depsNotMatched:

        crying_atoms = {}
        for atom in depsNotMatched:
            riddep = Equo.clientDbconn.searchDependency(atom)
            if riddep != -1:
                ridpackages = Equo.clientDbconn.searchIdpackageFromIddependency(riddep)
                for i in ridpackages:
                    iatom = Equo.clientDbconn.retrieveAtom(i)
                    if not crying_atoms.has_key(atom):
                        crying_atoms[atom] = set()
                    crying_atoms[atom].add(iatom)

        print_info(red(" @@ ")+blue("%s:" % (_("These are the dependencies not found"),) ))
        for atom in depsNotMatched:
            print_info("   # "+red(atom))
            if crying_atoms.has_key(atom):
                print_info(blue("      # ")+red("%s:" % (_("Needed by"),) ))
                for x in crying_atoms[atom]:
                    print_info(blue("      # ")+darkgreen(x))

        if (etpUi['ask']):
            rc = Equo.askQuestion("     %s"  % (_("Would you like to install the available packages ?"),) )
            if rc == "No":
                return 0,0
        else:
            mytxt = "%s %s %s" % (
                blue(_("Installing available packages in")),
                red(_("10 seconds")),
                blue("..."),
            )
            print_info(red(" @@ ")+mytxt)
            import time
            time.sleep(10)

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
        if not etpUi['quiet']: print_info(red(" @@ ")+blue("%s." % (_("System is healthy"),) ))
        restore_qstats()
        return 0,0

    atomsdata = set()
    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("%s:" % (_("Libraries statistics"),) ))
        if brokenlibs:
            print_info(brown(" ## ")+red("%s:" % (_("Not matched"),) ))
            for lib in brokenlibs:
                print_info(darkred("    => ")+red(lib))
        print_info(darkgreen(" ## ")+red("%s:" % (_("Matched"),) ))
        for packagedata in packagesMatched:
            dbconn = Equo.openRepositoryDatabase(packagedata[1])
            myatom = dbconn.retrieveAtom(packagedata[0])
            atomsdata.add((packagedata[0],packagedata[1]))
            print_info("   "+red(packagedata[2])+" => "+brown(myatom)+" ["+red(packagedata[1])+"]")
    else:
        for packagedata in packagesMatched:
            dbconn = Equo.openRepositoryDatabase(packagedata[1])
            myatom = dbconn.retrieveAtom(packagedata[0])
            atomsdata.add((packagedata[0],packagedata[1]))
            print myatom
        restore_qstats()
        return 0,atomsdata

    if (etpUi['pretend']):
        restore_qstats()
        return 0,atomsdata

    if (atomsdata):
        if (etpUi['ask']):
            rc = Equo.askQuestion("     %s" % (_("Would you like to install them ?"),) )
            if rc == "No":
                restore_qstats()
                return 0,atomsdata
        else:
            mytxt = "%s %s %s" % (
                blue(_("Installing available packages in")),
                red(_("10 seconds")),
                blue("..."),
            )
            print_info(red(" @@ ")+mytxt)
            import time
            time.sleep(10)

        rc = installPackages(atomsdata = list(atomsdata))
        if rc[0] == 0:
            restore_qstats()
            return 0,atomsdata
        else:
            restore_qstats()
            return rc[0],atomsdata

    restore_qstats()
    return 0,atomsdata
