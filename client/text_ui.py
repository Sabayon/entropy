# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""

########################################################
####
##   Packages user handling function
#

import shutil
from entropy.exceptions import *
from entropy.const import *
from entropy.output import *
from entropy.client.interfaces import Client
from entropy.misc import ParallelTask
from entropy.i18n import _
Equo = Client()

def package(options):

    if len(options) < 1:
        return 0

    # Options available for all the packages submodules
    myopts = options[1:]
    equoRequestDeps = True
    equoRequestEmptyDeps = False
    equoRequestOnlyFetch = False
    equoRequestDeep = False
    equoRequestRelaxed = False
    equoRequestConfigFiles = False
    equoRequestReplay = False
    equoRequestResume = False
    equoRequestSkipfirst = False
    equoRequestListfiles = False
    equoRequestChecksum = True
    equoRequestSortSize = False
    equoRequestSaveHere = False
    equoRequestDump = False
    equoRequestMultifetch = 1
    rc = 0
    _myopts = []
    mytbz2paths = []
    for opt in myopts:
        if not Equo.entropyTools.is_valid_unicode(opt):
            print_error(red(" %s." % (_("Malformed command"),) ))
            return -10
        try:
            opt = const_convert_to_unicode(opt, 'utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError,):
            print_error(red(" %s." % (_("Malformed command"),) ))
            return -10
        if (opt == "--nodeps"):
            equoRequestDeps = False
        elif (opt == "--empty"):
            equoRequestEmptyDeps = True
        elif (opt == "--relaxed"):
            equoRequestRelaxed = True
        elif (opt == "--fetch"):
            equoRequestOnlyFetch = True
        elif (opt == "--deep"):
            equoRequestDeep = True
        elif (opt == "--dump"):
            equoRequestDump = True
        elif (opt == "--listfiles"):
            equoRequestListfiles = True
        elif (opt == "--configfiles"):
            equoRequestConfigFiles = True
        elif (opt == "--replay"):
            equoRequestReplay = True
        elif (opt == "--resume"):
            equoRequestResume = True
        elif (opt == "--sortbysize"):
            equoRequestSortSize = True
        elif (opt == "--savehere"):
            equoRequestSaveHere = True
        elif (opt == "--multifetch"):
            equoRequestMultifetch = 3
        elif (opt.startswith("--multifetch=")):
            try:
                myn = int(opt[len("--multifetch="):])
            except ValueError:
                continue
            if myn not in list(range(2, 11)):
                myn = 10
            equoRequestMultifetch = myn
        elif (opt == "--nochecksum"):
            equoRequestChecksum = False
        elif (opt == "--skipfirst"):
            equoRequestSkipfirst = True
        elif (opt.startswith("--")):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return -10
        else:
            if opt.startswith("--"):
                continue
            etp_file = Equo.entropyTools.is_entropy_package_file(opt)
            if etp_file:
                opt = os.path.abspath(opt)
                mytbz2paths.append(opt)
            elif opt.strip():
                _myopts.append(opt.strip())
    myopts = _myopts

    if (options[0] == "deptest"):
        rc, garbage = dependenciesTest()

    elif (options[0] == "unusedpackages"):
        rc, garbage = unusedPackagesTest(do_size_sort = equoRequestSortSize)

    elif (options[0] == "libtest"):
        rc, garbage = librariesTest(listfiles = equoRequestListfiles,
            dump = equoRequestDump)

    elif (options[0] == "source"):

        if myopts or mytbz2paths:
            status, rc = downloadSources(myopts, deps = equoRequestDeps,
                deepdeps = equoRequestDeep, tbz2 = mytbz2paths,
                savecwd = equoRequestSaveHere,
                relaxed_deps = equoRequestRelaxed)
        else:
            print_error(red(" %s." % (_("Nothing to do"),) ))
            rc = 126

    elif (options[0] == "fetch"):

        if myopts or mytbz2paths:
            status, rc = downloadPackages(myopts, deps = equoRequestDeps,
                deepdeps = equoRequestDeep,
                multifetch = equoRequestMultifetch,
                dochecksum = equoRequestChecksum,
                relaxed_deps = equoRequestRelaxed)
        else:
            print_error(red(" %s." % (_("Nothing to do"),) ))
            rc = 126

    elif (options[0] == "install"):
        if (myopts) or (mytbz2paths) or (equoRequestResume):
            rc, garbage = installPackages(myopts, deps = equoRequestDeps,
                emptydeps = equoRequestEmptyDeps,
                onlyfetch = equoRequestOnlyFetch, deepdeps = equoRequestDeep,
                config_files = equoRequestConfigFiles, tbz2 = mytbz2paths,
                resume = equoRequestResume, skipfirst = equoRequestSkipfirst,
                dochecksum = equoRequestChecksum,
                multifetch = equoRequestMultifetch,
                check_critical_updates = True,
                relaxed_deps = equoRequestRelaxed)
        else:
            print_error(red(" %s." % (_("Nothing to do"),) ))
            rc = 126

    elif (options[0] in ("world", "upgrade",)):
        status, rc = worldUpdate(onlyfetch = equoRequestOnlyFetch,
            replay = (equoRequestReplay or equoRequestEmptyDeps),
            resume = equoRequestResume,
            skipfirst = equoRequestSkipfirst, human = True,
            dochecksum = equoRequestChecksum,
            multifetch = equoRequestMultifetch)

    elif (options[0] == "hop"):
        if myopts:
            status, rc = branchHop(myopts[0])
        else:
            print_error(red(" %s." % (_("Nothing to do"),) ))
            rc = 126

    elif (options[0] == "remove"):
        if myopts or equoRequestResume:
            status, rc = removePackages(myopts, deps = equoRequestDeps,
            deep = equoRequestDeep, configFiles = equoRequestConfigFiles,
            resume = equoRequestResume)
        else:
            print_error(red(" %s." % (_("Nothing to do"),) ))
            rc = 126

    elif (options[0] == "config"):
        if myopts:
            status, rc = configurePackages(myopts)
        else:
            print_error(red(" %s." % (_("Nothing to do"),) ))
            rc = 126

    else:
        rc = -10

    return rc


def worldUpdate(onlyfetch = False, replay = False, resume = False,
    skipfirst = False, human = False, dochecksum = True, multifetch = 1):

    # check if I am root
    if (not Equo.entropyTools.is_root()):
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    if not resume:

        print_info(red(" @@ ")+blue("%s..." % (_("Calculating System Updates"),) ))
        try:
            update, remove, fine, spm_fine = Equo.calculate_world_updates(
                empty_deps = replay)
        except SystemDatabaseError:
            # handled in equo.py
            raise

        if (etpUi['verbose'] or etpUi['pretend']):
            print_info(red(" @@ ") + "%s => %s" % (
                    bold(str(len(update))),
                    darkgreen(_("Packages matching update")),
                )
            )
            print_info(red(" @@ ") + "%s => %s" % (
                    bold(str(len(remove))),
                    darkred(_("Packages matching not available")),
                )
            )
            print_info(red(" @@ ") + "%s => %s" % (
                    bold(str(len(fine))),
                    blue(_("Packages matching already up to date")),
                )
            )

        del fine

        # clear old resume information
        if etpConst['uid'] == 0:
            try:
                Equo.dumpTools.dumpobj(etpCache['world'], {})
                Equo.dumpTools.dumpobj(etpCache['install'], {})
                Equo.dumpTools.dumpobj(etpCache['remove'], [])
                if (not etpUi['pretend']):
                    # store resume information
                    resume_cache = {}
                    resume_cache['ask'] = etpUi['ask']
                    resume_cache['verbose'] = etpUi['verbose']
                    resume_cache['onlyfetch'] = onlyfetch
                    resume_cache['remove'] = remove
                    Equo.dumpTools.dumpobj(etpCache['world'], resume_cache)
            except (OSError, IOError):
                pass

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = Equo.dumpTools.loadobj(etpCache['world'])
        if (not resume_cache) or (etpConst['uid'] != 0): # None or {}
            print_error(red("%s." % (_("Nothing to resume"),) ))
            return 128, -1
        else:
            try:
                update = []
                remove = resume_cache['remove']
                etpUi['ask'] = resume_cache['ask']
                etpUi['verbose'] = resume_cache['verbose']
                onlyfetch = resume_cache['onlyfetch']
                Equo.dumpTools.dumpobj(etpCache['remove'], list(remove))
            except (OSError, IOError, KeyError):
                print_error(red("%s." % (_("Resume cache corrupted"),) ))
                try:
                    Equo.dumpTools.dumpobj(etpCache['world'], {})
                    Equo.dumpTools.dumpobj(etpCache['install'], {})
                    Equo.dumpTools.dumpobj(etpCache['remove'], [])
                except (OSError, IOError):
                    pass
                return 128, -1

    # disable collisions protection, better
    sys_set_client_plg_id = \
        etpConst['system_settings_plugins_ids']['client_plugin']
    equo_client_settings = Equo.SystemSettings[sys_set_client_plg_id]['misc']
    oldcollprotect = equo_client_settings['collisionprotect']
    equo_client_settings['collisionprotect'] = 1

    if (update) or (resume):
        rc = installPackages(
            atomsdata = update,
            onlyfetch = onlyfetch,
            resume = resume,
            skipfirst = skipfirst,
            dochecksum = dochecksum,
            deepdeps = True,
            multifetch = multifetch
        )
        if rc[1] != 0:
            return 1, rc[0]
    else:
        print_info(red(" @@ ")+blue("%s." % (_("Nothing to update"),) ))

    equo_client_settings['collisionprotect'] = oldcollprotect

    # verify that client database idpackage still exist, validate here before passing removePackage() wrong info
    remove = [x for x in remove if Equo.clientDbconn.isIdpackageAvailable(x)]

    if remove and Equo.validRepositories and (not onlyfetch):
        remove = sorted(remove)
        print_info(red(" @@ ") + \
            blue("%s." % (
                    _("On the system there are packages that are not available anymore in the online repositories"),
                )
            )
        )
        print_info(red(" @@ ")+blue(_("Even if they are usually harmless, it is suggested to remove them.")))

        if not etpUi['pretend']:
            do_run = False
            if human:
                do_run = True
                rc = Equo.askQuestion("     %s" % (_("Would you like to scan them ?"),) )
                if rc == _("No"):
                    do_run = False

            if do_run:
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

    # run post-branch upgrade hooks, if needed
    if not etpUi['pretend']:
        # this triggers post-branch upgrade function inside
        # Entropy Client SystemSettings plugin
        Equo.SystemSettings.clear()

    return 0, 0

def branchHop(branch):

    # check if I am root
    if (not Equo.entropyTools.is_root()):
        mytxt = "%s." % (darkred(_("Cannot switch branch as user")),)
        print_error(mytxt)
        return 1, -1

    # set the new branch
    if branch == Equo.SystemSettings['repositories']['branch']:
        mytxt = "%s %s: %s" % (bold(" !!! "),
            darkred(_("Already on branch")), purple(branch),)
        print_warning(mytxt)
        return 2, -1

    old_repo_paths = []
    avail_data = Equo.SystemSettings['repositories']['available']
    for repoid in sorted(avail_data):
        old_repo_paths.append(avail_data[repoid]['dbpath'][:])

    old_branch = Equo.SystemSettings['repositories']['branch'][:]
    Equo.set_branch(branch)
    status = True

    try:
        repoConn = Equo.Repositories([], forceUpdate = False,
            fetchSecurity = False)
    except PermissionDenied:
        mytxt = darkred(_("You must be either root or in the %s group.")) % (
            etpConst['sysgroup'],)
        print_error("\t"+mytxt)
        status = False
    except MissingParameter:
        print_error(darkred(" * ")+red("%s %s" % (
            _("No repositories specified in"), etpConst['repositoriesconf'],)))
        status = False
    except Exception as e:
        print_error(darkred(" @@ ")+red("%s: %s" % (
            _("Unhandled exception"), e,)))
        status = False
    else:
        rc = repoConn.sync()
        if rc and rc != 1:
            # rc != 1 means not all the repos have been downloaded
            status = False

    if status:

        Equo.clientDbconn.moveSpmUidsToBranch(branch)

        # remove old repos
        for repo_path in old_repo_paths:
            try:
                shutil.rmtree(repo_path, True)
            except shutil.Error:
                continue

        mytxt = "%s %s: %s" % (red(" @@ "),
            darkgreen(_("Succesfully switched to branch")), purple(branch),)
        print_info(mytxt)
        mytxt = "%s %s" % (brown(" ?? "),
            darkgreen(
                _("Now run 'equo world' to upgrade your distribution to")),
            )
        print_info(mytxt)
        return 0, 0
    else:
        Equo.set_branch(old_branch)
        mytxt = "%s %s: %s" % (bold(" !!! "),
            darkred(_("Unable to switch to branch")), purple(branch),)
        print_error(mytxt)
        return 3, -2

def _scanPackages(packages, tbz2):

    foundAtoms = []

    # expand package
    packages = Equo.packages_expand(packages)

    for package in packages:
        # clear masking reasons
        match = Equo.atom_match(package)
        if match[0] == -1:
            masked_matches = Equo.atom_match(package, packagesFilter = False, multiMatch = True)
            if masked_matches[1] == 0:

                mytxt = "%s %s %s %s." % (
                    bold("!!!"),
                    red(_("Every package matching")), # every package matching app-foo is masked
                    bold(package),
                    red(_("is masked")),
                )
                print_warning(mytxt)

                m_reasons = {}
                for match in masked_matches[0]:
                    masked, idreason, reason = Equo.get_masked_package_reason(match)
                    if not masked: continue
                    if (idreason, reason,) not in m_reasons:
                        m_reasons[(idreason, reason,)] = []
                    m_reasons[(idreason, reason,)].append(match)

                for idreason, reason in sorted(m_reasons.keys()):
                    print_warning(bold("    # ")+red("Reason: ")+blue(reason))
                    for m_idpackage, m_repo in m_reasons[(idreason, reason)]:
                        dbconn = Equo.open_repository(m_repo)
                        try:
                            m_atom = dbconn.retrieveAtom(m_idpackage)
                        except TypeError:
                            m_atom = "idpackage: %s %s %s %s" % (
                                m_idpackage,
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
                    mytxt = "%s %s %s %s %s" % (
                        bold("   ?"),
                        red(_("When you wrote")),
                        bold(package),
                        darkgreen(_("You Meant(tm)")),
                        red(_("one of these below?")),
                    )
                    print_info(mytxt)
                    for m_idpackage, m_repo in items:
                        dbc = Equo.open_repository(m_repo)
                        key, slot = dbc.retrieveKeySlot(m_idpackage)
                        if (key, slot) not in items_cache:
                            print_info(red("    # ")+blue(key)+":"+brown(str(slot))+red(" ?"))
                        items_cache.add((key, slot))
                    del items_cache
            continue
        if match not in foundAtoms:
            foundAtoms.append(match)

    if tbz2:
        for pkg in tbz2:
            status, atomsfound = Equo.add_package_to_repos(pkg)
            if status == 0:
                foundAtoms += atomsfound[:]
                del atomsfound
            elif status in (-1, -2, -3, -4,):
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
                raise InvalidDataType("InvalidDataType: ??????")

    return foundAtoms

def _showPackageInfo(foundAtoms, deps, action_name = None):

    if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
        # now print the selected packages
        print_info(red(" @@ ")+blue("%s:" % (_("These are the chosen packages"),) ))
        totalatoms = len(foundAtoms)
        atomscounter = 0
        for idpackage, reponame in foundAtoms:
            atomscounter += 1
            # open database
            dbconn = Equo.open_repository(reponame)

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
                installedRepo = Equo.clientDbconn.getInstalledPackageRepository(idx)
                if installedRepo is None:
                    installedRepo = _("Not available")
                if not installedTag:
                    installedTag = "NoTag"
                installedRev = Equo.clientDbconn.retrieveRevision(idx)

            mytxt = "   # %s%s/%s%s [%s] %s" % (
                red("("),
                bold(str(atomscounter)),
                blue(str(totalatoms)),
                red(")"),
                red(reponame),
                bold(pkgatom),
            )
            print_info(mytxt)
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

            pkgcmp = Equo.get_package_action((idpackage, reponame))
            if (pkgcmp == 0) and is_installed:
                if installedRepo != reponame:
                    mytxt = " | %s: " % (_("Switch repo"),)
                    action = darkgreen(_("Reinstall"))+mytxt+blue(installedRepo)+" ===> "+darkgreen(reponame)
                else:
                    action = darkgreen(_("Reinstall"))
            elif pkgcmp == 1:
                action = darkgreen(_("Install"))
            elif pkgcmp == 2:
                action = blue(_("Upgrade"))
            else:
                action = red(_("Downgrade"))

            # support for caller provided action name
            if action_name is not None:
                action = action_name

            print_info("\t"+red("%s:\t\t" % (_("Action"),) )+" "+action)

        if (etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']):
            print_info(red(" @@ ")+blue("%s: " % (_("Packages involved"),) )+str(totalatoms))

        if etpUi['ask']:
            if deps:
                rc = Equo.askQuestion("     %s" % (_("Would you like to continue with dependencies calculation ?"),) )
            else:
                rc = Equo.askQuestion("     %s" % (_("Would you like to continue ?"),) )
            if rc == _("No"):
                return True, (0, 0)

    return False, (0, 0)

def _generateRunQueue(foundAtoms, deps, emptydeps, deepdeps, relaxeddeps):

    runQueue = []
    removalQueue = []

    if deps:
        print_info(red(" @@ ")+blue("%s ...") % (_("Calculating dependencies"),) )
        runQueue, removalQueue, status = Equo.get_install_queue(foundAtoms, emptydeps, deepdeps,
            relaxed_deps = relaxeddeps)
        if status == -2:

            print_error(red(" @@ ")+blue("%s: " % (_("Cannot find needed dependencies"),) ))
            for package in runQueue:

                masked_matches = Equo.atom_match(package, packagesFilter = False, multiMatch = True)
                if masked_matches[1] == 0:

                    mytxt = "%s %s %s %s." % (
                        bold("!!!"),
                        red(_("Every package matching")), # every package matching app-foo is masked
                        bold(package),
                        red(_("is masked")),
                    )
                    print_warning(mytxt)

                    m_reasons = {}
                    for match in masked_matches[0]:
                        masked, idreason, reason = Equo.get_masked_package_reason(match)
                        if not masked: continue
                        if (idreason, reason,) not in m_reasons:
                            m_reasons[(idreason, reason,)] = []
                        m_reasons[(idreason, reason,)].append(match)

                    for idreason, reason in sorted(m_reasons.keys()):
                        print_warning(bold("    # ")+red("Reason: ")+blue(reason))
                        for m_idpackage, m_repo in m_reasons[(idreason, reason)]:
                            dbconn = Equo.open_repository(m_repo)
                            try:
                                m_atom = dbconn.retrieveAtom(m_idpackage)
                            except TypeError:
                                m_atom = "idpackage: %s %s %s %s" % (
                                    m_idpackage,
                                    _("matching"),
                                    package,
                                    _("is broken"),
                                )
                            print_warning(blue("      <> ")+red("%s: " % (_("atom"),) )+brown(m_atom))

                else:

                    print_error(red("    # ")+blue("%s: " % (_("Not found"),) )+brown(package))
                    crying_atoms = Equo.find_belonging_dependency([package])
                    if crying_atoms:
                        print_error(red("      # ")+blue("%s:" % (_("Probably needed by"),) ))
                        for crying_atomdata in crying_atoms:
                            print_error(red("        # ")+" ["+blue(_("from"))+":"+brown(crying_atomdata[1])+"] "+darkred(crying_atomdata[0]))

            return True, (125, -1), []
    else:
        for atomInfo in foundAtoms:
            runQueue.append(atomInfo)

    return False, runQueue, removalQueue

def downloadSources(packages = None, deps = True, deepdeps = False, tbz2 = None,
    savecwd = False, relaxed_deps = False):

    if packages is None:
        packages = []
    if tbz2 is None:
        tbz2 = []

    foundAtoms = _scanPackages(packages, tbz2)
    # are there packages in foundAtoms?
    if not foundAtoms:
        print_error( red("%s." % (_("No packages found"),) ))
        return 125, -1

    action = darkgreen(_("Source code download"))
    abort, myrc = _showPackageInfo(foundAtoms, deps, action_name = action)
    if abort:
        return myrc

    abort, runQueue, removalQueue = _generateRunQueue(foundAtoms, deps,
        False, deepdeps, relaxed_deps)
    if abort:
        return runQueue

    if etpUi['pretend']:
        return 0, 0

    totalqueue = str(len(runQueue))
    fetchqueue = 0
    metaopts = {}
    if savecwd:
        metaopts['fetch_path'] = os.getcwd()

    for match in runQueue:
        fetchqueue += 1

        Package = Equo.Package()

        Package.prepare(match, "source", metaopts)

        xterm_header = "Equo ("+_("sources fetch")+") :: "+str(fetchqueue)+" of "+totalqueue+" ::"
        print_info(red(" :: ")+bold("(")+blue(str(fetchqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.pkgmeta['atom']))

        rc = Package.run(xterm_header = xterm_header)
        if rc != 0:
            return -1, rc
        Package.kill()

        del Package

    return 0, 0

def _fetchPackages(runQueue, multifetch = 1, dochecksum = True):
    totalqueue = str(len(runQueue))

    fetchqueue = 0
    mykeys = {}
    mymultifetch = multifetch
    if multifetch > 1:
        myqueue = []
        mystart = 0
        while True:
            mylist = runQueue[mystart:mymultifetch]
            if not mylist: break
            myqueue.append(mylist)
            mystart += multifetch
            mymultifetch += multifetch
        mytotalqueue = str(len(myqueue))

        for matches in myqueue:
            fetchqueue += 1

            metaopts = {}
            metaopts['dochecksum'] = dochecksum
            Package = Equo.Package()
            Package.prepare(matches, "multi_fetch", metaopts)
            myrepo_data = Package.pkgmeta['repository_atoms']
            for myrepo in myrepo_data:
                if myrepo not in mykeys:
                    mykeys[myrepo] = set()
                for myatom in myrepo_data[myrepo]:
                    mykeys[myrepo].add(Equo.entropyTools.dep_getkey(myatom))

            xterm_header = "Equo ("+_("fetch")+") :: "+str(fetchqueue)+" of "+mytotalqueue+" ::"
            print_info(red(" :: ")+bold("(")+blue(str(fetchqueue))+"/"+ \
                           red(mytotalqueue)+bold(") ")+">>> "+darkgreen(str(len(matches)))+" "+_("packages"))

            rc = Package.run(xterm_header = xterm_header)
            if rc != 0:
                return -1, rc
            Package.kill()
            del metaopts
            del Package

        return 0, 0

    # normal fetch
    for match in runQueue:
        fetchqueue += 1

        metaopts = {}
        metaopts['dochecksum'] = dochecksum
        Package = Equo.Package()
        Package.prepare(match, "fetch", metaopts)
        myrepo = Package.pkgmeta['repository']
        if myrepo not in mykeys:
            mykeys[myrepo] = set()
        mykeys[myrepo].add(Equo.entropyTools.dep_getkey(Package.pkgmeta['atom']))

        xterm_header = "Equo ("+_("fetch")+") :: "+str(fetchqueue)+" of "+totalqueue+" ::"
        print_info(red(" :: ")+bold("(")+blue(str(fetchqueue))+"/"+ \
                        red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.pkgmeta['atom']))

        rc = Package.run(xterm_header = xterm_header)
        if rc != 0:
            return -1, rc
        Package.kill()
        del metaopts
        del Package

    return 0, 0


def downloadPackages(packages = None, deps = True, deepdeps = False,
    multifetch = 1, dochecksum = True, relaxed_deps = False):

    if packages is None:
        packages = []

    # check if I am root
    if (not Equo.entropyTools.is_root()):
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True


    foundAtoms = _scanPackages(packages, None)

    # are there packages in foundAtoms?
    if not foundAtoms:
        print_error( red("%s." % (_("No packages found"),) ))
        return 125, -1

    action = brown(_("Download"))
    abort, myrc = _showPackageInfo(foundAtoms, deps, action_name = action)
    if abort:
        return myrc

    abort, runQueue, removalQueue = _generateRunQueue(foundAtoms, deps,
        False, deepdeps, relaxed_deps)
    if abort:
        return runQueue

    if etpUi['pretend']:
        return 0, 0

    return _fetchPackages(runQueue, multifetch, dochecksum)

def installPackages(packages = None, atomsdata = None, deps = True,
    emptydeps = False, onlyfetch = False, deepdeps = False,
    config_files = False, tbz2 = None, resume = False, skipfirst = False,
    dochecksum = True, multifetch = 1, check_critical_updates = False,
    relaxed_deps = False):

    if packages is None:
        packages = []
    if atomsdata is None:
        atomsdata = []
    if tbz2 is None:
        tbz2 = []

    # check if I am root
    if (not Equo.entropyTools.is_root()):
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    explicit_user_packages = set()

    sys_set_client_plg_id = \
        etpConst['system_settings_plugins_ids']['client_plugin']
    equo_client_settings = Equo.SystemSettings[sys_set_client_plg_id]['misc']

    if check_critical_updates and equo_client_settings.get('forcedupdates'):
        crit_atoms, crit_matches = Equo.calculate_critical_updates()
        if crit_atoms:
            print_info("")
            print_info("")
            mytxt = "%s: %s" % (
                purple(_("Please update the following critical packages")),
                '\n'+'\n'.join(
                    [darkred('>>\t# ') + brown(x) for x in sorted(crit_atoms)]
                ),
            )
            print_warning(red(" !!! ")+mytxt)
            mytxt = _("You should install them as soon as possible")
            print_warning(red(" !!! ")+darkgreen(mytxt))
            print_info("")
            print_info("")

    if not resume:

        if atomsdata:
            foundAtoms = atomsdata
        else:
            foundAtoms = _scanPackages(packages, tbz2)
            explicit_user_packages |= set(foundAtoms)

        # are there packages in foundAtoms?
        if (not foundAtoms):
            print_error( red("%s." % (_("No packages found"),) ))
            return 125, -1

        abort, myrc = _showPackageInfo(foundAtoms, deps)
        if abort:
            return myrc

        abort, runQueue, removalQueue = _generateRunQueue(foundAtoms, deps,
            emptydeps, deepdeps, relaxed_deps)
        if abort:
            return runQueue


        if ((not runQueue) and (not removalQueue)):
            print_error(red("%s." % (_("Nothing to do"),) ))
            return 126, -1

        downloadSize = 0
        unpackSize = 0
        onDiskUsedSize = 0
        onDiskFreedSize = 0
        pkgsToInstall = 0
        pkgsToUpdate = 0
        pkgsToReinstall = 0
        pkgsToDowngrade = 0
        pkgsToRemove = len(removalQueue)

        if runQueue:

            if (etpUi['ask'] or etpUi['pretend']):
                mytxt = "%s:" % (blue(_("These are the packages that would be installed")),)
                print_info(red(" @@ ")+mytxt)

            count = 0
            for idpackage, reponame in runQueue:
                count += 1

                dbconn = Equo.open_repository(reponame)
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
                        f = open(etpConst['entropyworkdir']+"/"+pkgfile, "r")
                        f.seek(0, 2)
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
                installedRepo = None
                pkginstalled = Equo.clientDbconn.atomMatch(Equo.entropyTools.dep_getkey(pkgatom), matchSlot = pkgslot)
                if (pkginstalled[1] == 0):
                    # found an installed package
                    idx = pkginstalled[0]
                    installedVer = Equo.clientDbconn.retrieveVersion(idx)
                    installedTag = Equo.clientDbconn.retrieveVersionTag(idx)
                    installedRev = Equo.clientDbconn.retrieveRevision(idx)
                    installedRepo = Equo.clientDbconn.getInstalledPackageRepository(idx)
                    if installedRepo is None:
                        installedRepo = _("Not available")
                    onDiskFreedSize += Equo.clientDbconn.retrieveOnDiskSize(idx)

                if not (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
                    continue

                inst_meta = (installedVer, installedTag, installedRev,)
                avail_meta = (pkgver, pkgtag, pkgrev,)

                action = 0
                repoSwitch = False
                if (reponame != installedRepo) and (installedRepo is not None):
                    repoSwitch = True
                if repoSwitch:
                    flags = darkred(" [")
                else:
                    flags = " ["
                if installedRepo is None:
                    installedRepo = _('Not available')
                pkgcmp = Equo.get_package_action((idpackage, reponame))
                if pkgcmp == 0:
                    pkgsToReinstall += 1
                    flags += red("R")
                    action = 1
                elif pkgcmp == 1:
                    pkgsToInstall += 1
                    flags += darkgreen("N")
                elif pkgcmp == 2:
                    pkgsToUpdate += 1
                    if avail_meta == inst_meta:
                        flags += blue("U") + red("R")
                    else:
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
                mytxt = "%s (%s):" % (
                    blue(_("These are the packages that would be removed")),
                    bold(_("conflicting/substituted")),
                )
                print_info(red(" @@ ")+mytxt)

                for idpackage in removalQueue:
                    pkgatom = Equo.clientDbconn.retrieveAtom(idpackage)
                    if not pkgatom:
                        continue
                    onDiskFreedSize += Equo.clientDbconn.retrieveOnDiskSize(idpackage)
                    installedfrom = Equo.clientDbconn.getInstalledPackageRepository(idpackage)
                    if installedfrom is None:
                        installedfrom = _("Not available")
                    repoinfo = red("[")+brown("%s: " % (_("from"),) )+bold(installedfrom)+red("] ")
                    print_info(red("   ## ")+"["+red("W")+"] "+repoinfo+enlightenatom(pkgatom))

        if (runQueue) or (removalQueue) and not etpUi['quiet']:
            # show download info
            mytxt = "%s: %s" % (blue(_("Packages needing to be installed/updated/downgraded")), red(str(len(runQueue))),)
            print_info(red(" @@ ")+mytxt)
            mytxt = "%s: %s" % (blue(_("Packages needing to be removed")), red(str(pkgsToRemove)),)
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
                    red(str(pkgsToDowngrade)),
                )
                print_info(red(" @@ ")+mytxt)

            if downloadSize > 0:
                mysize = str(Equo.entropyTools.bytes_into_human(downloadSize))
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
                bold(str(Equo.entropyTools.bytes_into_human(deltaSize))),
            )
            print_info(red(" @@ ")+mytxt)

            if neededSize < 0:
                neededSize = neededSize*-1

            mytxt = "%s: %s %s" % (
                blue(_("You need at least")),
                blue(str(Equo.entropyTools.bytes_into_human(neededSize))),
                _("of free space"),
            )
            print_info(red(" @@ ")+mytxt)
            # check for disk space and print a warning
            ## unpackSize
            size_match = Equo.entropyTools.check_required_space(etpConst['entropyunpackdir'], neededSize)
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

        if etpUi['ask']:
            rc = Equo.askQuestion("     %s" % (_("Would you like to execute the queue ?"),) )
            if rc == _("No"):
                return 0, 0

        if etpUi['pretend']:
            return 0, 0

        try:
            # clear old resume information
            Equo.dumpTools.dumpobj(etpCache['install'], {})
            # store resume information
            if not tbz2: # .tbz2 install resume not supported
                resume_cache = {}
                resume_cache['user_packages'] = explicit_user_packages
                resume_cache['runQueue'] = runQueue[:]
                resume_cache['onlyfetch'] = onlyfetch
                resume_cache['emptydeps'] = emptydeps
                resume_cache['deepdeps'] = deepdeps
                resume_cache['relaxed_deps'] = relaxed_deps
                Equo.dumpTools.dumpobj(etpCache['install'], resume_cache)
        except (IOError, OSError):
            pass

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = Equo.dumpTools.loadobj(etpCache['install'])
        if not resume_cache: # None or {}

            print_error(red("%s." % (_("Nothing to resume"),) ))
            return 128, -1

        else:

            try:
                explicit_user_packages = resume_cache['user_packages']
                runQueue = resume_cache['runQueue'][:]
                onlyfetch = resume_cache['onlyfetch']
                emptydeps = resume_cache['emptydeps']
                deepdeps = resume_cache['deepdeps']
                relaxed_deps = resume_cache['relaxed_deps']
                print_warning(red("%s..." % (_("Resuming previous operations"),) ))
            except (KeyError, TypeError, AttributeError,):
                print_error(red("%s." % (_("Resume cache corrupted"),) ))
                try:
                    Equo.dumpTools.dumpobj(etpCache['install'], {})
                except (IOError, OSError):
                    pass
                return 128, -1

            if skipfirst and runQueue:
                runQueue, x, status = Equo.get_install_queue(runQueue[1:],
                    emptydeps, deepdeps, relaxed_deps = relaxed_deps)
                del x # was removalQueue
                # save new queues
                resume_cache['runQueue'] = runQueue
                try:
                    Equo.dumpTools.dumpobj(etpCache['install'], resume_cache)
                except (IOError, OSError):
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
        keys = sorted(licenses.keys())
        for key in keys:
            print_info(red("    :: %s: " % (_("License"),) )+bold(key)+red(", %s:" % (_("needed by"),) ))
            for match in licenses[key]:
                dbconn = Equo.open_repository(match[1])
                atom = dbconn.retrieveAtom(match[0])
                print_info(blue("       ## ")+"["+brown(_("from"))+":"+red(match[1])+"] "+bold(atom))
            while True:
                choice = read_lic_selection()
                try:
                    choice = int(choice)
                except (ValueError, EOFError, TypeError):
                    continue
                if choice not in (0, 1, 2, 3):
                    continue
                if choice == 0:
                    return 0, 0
                elif choice == 1: # read
                    filename = Equo.get_text_license(key, match[1])
                    viewer = Equo.get_file_viewer()
                    if viewer == None:
                        print_info(red("    %s ! %s %s " % (_("No file viewer"), _("License saved into"), filename,) ))
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
        # Before starting the real install, fetch packages and verify checksum.
        func_rc, fetch_rc = _fetchPackages(runQueue, multifetch, dochecksum)
        if func_rc != 0:
            print_info(red(" @@ ")+blue("%s." % (_("Download incomplete"),) ))
            return func_rc, fetch_rc

        def spawn_ugc():
            try:
                if Equo.UGC != None:
                    for myrepo in mykeys:
                        mypkgkeys = sorted(mykeys[myrepo])
                        Equo.UGC.add_download_stats(myrepo, mypkgkeys)
            except:
                pass
        spawn_ugc()

    if onlyfetch:
        print_info(red(" @@ ")+blue("%s." % (_("Download complete"),) ))
        return 0, 0

    for match in runQueue:
        currentqueue += 1

        metaopts = {}
        metaopts['removeconfig'] = config_files

        if match in explicit_user_packages:
            metaopts['install_source'] = etpConst['install_sources']['user']
        else:
            metaopts['install_source'] = etpConst['install_sources']['automatic_dependency']

        Package = Equo.Package()
        Package.prepare(match, "install", metaopts)

        xterm_header = "Equo ("+_("install")+") :: "+str(currentqueue)+" of "+totalqueue+" ::"
        print_info(red(" ++ ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.pkgmeta['atom']))

        rc = Package.run(xterm_header = xterm_header)
        if rc != 0:
            return 1, rc

        # there's a buffer inside, better remove otherwise cPickle will complain
        del Package.pkgmeta['triggers']

        if etpUi['clean']: # remove downloaded package
            if os.path.isfile(Package.pkgmeta['pkgpath']):
                os.remove(Package.pkgmeta['pkgpath'])

        # update resume cache
        if not tbz2: # tbz2 caching not supported
            resume_cache['runQueue'].remove(match)
            try:
                Equo.dumpTools.dumpobj(etpCache['install'], resume_cache)
            except (IOError, OSError):
                pass

        Package.kill()
        del metaopts
        del Package


    del explicit_user_packages
    print_info(red(" @@ ")+blue("%s." % (_("Installation complete"),) ))
    try:
        # clear resume information
        Equo.dumpTools.dumpobj(etpCache['install'], {})
    except (IOError, OSError):
        pass
    return 0, 0

def configurePackages(packages = None):

    if packages is None:
        packages = []

    # check if I am root
    if (not Equo.entropyTools.is_root()):
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    foundAtoms = []
    packages = Equo.packages_expand(packages)

    for package in packages:
        idpackage, result = Equo.clientDbconn.atomMatch(package)
        if idpackage == -1:
            mytxt = "## %s: %s %s." % (
                red(_("ATTENTION")),
                bold(const_convert_to_unicode(package)),
                red(_("is not installed")),
            )
            print_warning(mytxt)
            if len(package) < 4:
                continue
            items = Equo.get_meant_packages(package, from_installed = True)
            if items:
                items_cache = set()
                mytxt = "%s %s %s %s %s" % (
                    bold("   ?"),
                    red(_("When you wrote")),
                    bold(package),
                    darkgreen(_("You Meant(tm)")),
                    red(_("one of these below?")),
                )
                print_info(mytxt)
                for match in items:
                    key, slot = Equo.clientDbconn.retrieveKeySlot(match[0])
                    if (key, slot) not in items_cache:
                        print_info(red("    # ")+blue(key)+":"+brown(str(slot))+red(" ?"))
                    items_cache.add((key, slot))
                del items_cache
            continue
        foundAtoms.append(idpackage)

    if not foundAtoms:
        print_error(red("%s." % (_("No packages found"),) ))
        return 125, -1

    atomscounter = 0
    totalatoms = len(foundAtoms)
    for idpackage in foundAtoms:
        atomscounter += 1

        # get needed info
        pkgatom = Equo.clientDbconn.retrieveAtom(idpackage)
        if not pkgatom: continue

        installedfrom = Equo.clientDbconn.getInstalledPackageRepository(idpackage)
        if installedfrom is None:
            installedfrom = _("Not available")
        mytxt = " | %s: " % (_("Installed from"),)
        print_info("   # "+red("(")+brown(str(atomscounter))+"/"+blue(str(totalatoms))+red(")")+" "+enlightenatom(pkgatom)+mytxt+red(installedfrom))

    if etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']:
        print_info(red(" @@ ")+blue("%s: " % (_("Packages involved"),) )+str(totalatoms))

    if etpUi['ask']:
        rc = Equo.askQuestion(question = "     %s" % (_("Would you like to configure them now ?"),))
        if rc == _("No"):
            return 0, 0

    totalqueue = str(len(foundAtoms))
    currentqueue = 0
    for idpackage in foundAtoms:
        currentqueue += 1
        xterm_header = "Equo (configure) :: "+str(currentqueue)+" of "+totalqueue+" ::"
        Package = Equo.Package()
        Package.prepare((idpackage,), "config")
        rc = Package.run(xterm_header = xterm_header)
        if rc not in (0, 3,): return -1, rc
        Package.kill()

    return 0, 0

def removePackages(packages = None, atomsdata = None, deps = True, deep = False,
    systemPackagesCheck = True, configFiles = False, resume = False,
    human = False):

    if packages is None:
        packages = []
    if atomsdata is None:
        atomsdata = []

    # check if I am root
    if (not Equo.entropyTools.is_root()):
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    doSelectiveRemoval = False

    if not resume:

        foundAtoms = []
        if atomsdata:
            for idpackage in atomsdata:
                if not Equo.clientDbconn.isIdpackageAvailable(idpackage):
                    continue
                foundAtoms.append(idpackage)
        else:

            # expand package
            packages = Equo.packages_expand(packages)

            for package in packages:
                idpackage, result = Equo.clientDbconn.atomMatch(package)
                if idpackage == -1:
                    mytxt = "## %s: %s %s." % (
                        red(_("ATTENTION")),
                        bold(const_convert_to_unicode(package)),
                        red(_("is not installed")),
                    )
                    print_warning(mytxt)
                    if len(package) < 4:
                        continue

                    items = Equo.get_meant_packages(package,
                        from_installed = True)

                    if items:
                        items_cache = set()
                        mytxt = "%s %s %s %s %s" % (
                            bold("   ?"),
                            red(_("When you wrote")),
                            bold(package),
                            darkgreen(_("You Meant(tm)")),
                            red(_("one of these below?")),
                        )
                        print_info(mytxt)
                        for match in items:
                            key, slot = Equo.clientDbconn.retrieveKeySlot(match[0])
                            if (key, slot) not in items_cache:
                                print_info(red("    # ") + blue(key) + ":" + \
                                    brown(str(slot)) + red(" ?"))
                            items_cache.add((key, slot))
                        del items_cache
                    continue
                foundAtoms.append(idpackage)

        if not foundAtoms:
            print_error(red("%s." % (_("No packages found"),) ))
            return 125, -1

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
                valid = Equo.validate_package_removal(idpackage)
                if not valid:
                    mytxt = "   %s (%s/%s) %s: %s. %s." % (
                        bold("!!!"),
                        brown(str(atomscounter)),
                        blue(str(totalatoms)),
                        # every package matching app-foo is masked
                        enlightenatom(pkgatom),
                        red(_("vital package")),
                        red(_("Removal forbidden")),
                    )
                    print_warning(mytxt)
                    continue

            plainRemovalQueue.append(idpackage)

            installedfrom = Equo.clientDbconn.getInstalledPackageRepository(
                idpackage)
            if installedfrom is None:
                installedfrom = _("Not available")
            disksize = Equo.clientDbconn.retrieveOnDiskSize(idpackage)
            disksize = Equo.entropyTools.bytes_into_human(disksize)
            disksizeinfo = " | %s: %s" % (blue(_("Disk size")),
                bold(str(disksize)),)
            mytxt = " | %s: " % (_("Installed from"),)
            print_info("   # " + red("(") + brown(str(atomscounter)) + "/" + \
                blue(str(totalatoms)) + red(")") + " " + \
                enlightenatom(pkgatom) + mytxt + red(installedfrom) + \
                disksizeinfo)

        if (etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']):
            print_info(red(" @@ ") + \
                blue("%s: " % (_("Packages involved"),) ) + str(totalatoms))

        if (not plainRemovalQueue):
            print_error(red("%s." % (_("Nothing to do"),) ))
            return 126, -1

        if deps:
            question = "     %s" % (
                _("Would you like to calculate dependencies ?"),
            )
        else:
            question = "     %s" % (_("Would you like to remove them now ?"),)
            lookForOrphanedPackages = False

        if etpUi['ask']:
            rc = Equo.askQuestion(question)
            if rc == _("No"):
                lookForOrphanedPackages = False
                if (not deps):
                    return 0, 0

        removalQueue = []

        if lookForOrphanedPackages:
            choosenRemovalQueue = []
            choosenRemovalQueue = Equo.get_removal_queue(plainRemovalQueue, deep = deep)
            if choosenRemovalQueue:
                print_info(red(" @@ ")+blue("%s:" % (_("This is the new removal queue"),) ))
                totalatoms = str(len(choosenRemovalQueue))
                atomscounter = 0

                for idpackage in choosenRemovalQueue:
                    atomscounter += 1
                    rematom = Equo.clientDbconn.retrieveAtom(idpackage)
                    if not rematom:
                        continue
                    installedfrom = Equo.clientDbconn.getInstalledPackageRepository(idpackage)
                    if installedfrom is None:
                        installedfrom = _("Not available")
                    disksize = Equo.clientDbconn.retrieveOnDiskSize(idpackage)
                    disksize = Equo.entropyTools.bytes_into_human(disksize)
                    repositoryInfo = bold("[")+darkgreen("%s:" % (_("from"),) )+brown(installedfrom)+bold("]")
                    stratomscounter = str(atomscounter)
                    while len(stratomscounter) < len(totalatoms):
                        stratomscounter = " "+stratomscounter
                    disksizeinfo = bold(" [")+red(str(disksize))+bold("]")
                    print_info("   # "+red("(")+bold(stratomscounter)+"/"+blue(str(totalatoms))+red(")")+repositoryInfo+" "+blue(rematom)+disksizeinfo)

                removalQueue = choosenRemovalQueue

            else:
                writechar("\n")

        if etpUi['ask'] or human:
            question = "     %s" % (_("Would you like to proceed ?"),)
            if human:
                question = "     %s" % (_("Would you like to proceed with a selective removal ?"),)
            rc = Equo.askQuestion(question)
            if rc == _("No") and not human:
                return 0, 0
            elif rc == _("Yes") and human:
                doSelectiveRemoval = True
            elif rc == _("No") and human:
                rc = Equo.askQuestion("     %s" % (_("Would you like to skip this step then ?"),))
                if rc == _("Yes"):
                    return 0, 0
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
            Equo.dumpTools.dumpobj(etpCache['remove'], {})
            # store resume information
            resume_cache = {}
            resume_cache['doSelectiveRemoval'] = doSelectiveRemoval
            resume_cache['removalQueue'] = removalQueue
            Equo.dumpTools.dumpobj(etpCache['remove'], resume_cache)
        except (OSError, IOError, EOFError):
            pass

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = Equo.dumpTools.loadobj(etpCache['remove'])
        if not resume_cache: # None or {}
            print_error(red("%s." % (_("Nothing to resume"),) ))
            return 128, -1
        else:
            try:
                removalQueue = resume_cache['removalQueue'][:]
                doSelectiveRemoval = resume_cache['doSelectiveRemoval']
                print_warning(red("%s..." % (_("Resuming previous operations"),) ))
            except:
                print_error(red("%s." % (_("Resume cache corrupted"),) ))
                try:
                    Equo.dumpTools.dumpobj(etpCache['remove'], {})
                except (OSError, IOError):
                    pass
                return 128, -1

    if etpUi['pretend']:
        return 0, 0

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
                if rc == _("No"):
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
        Package.prepare((idpackage,), "remove", metaopts)
        if 'remove_installed_vanished' not in Package.pkgmeta:

            xterm_header = "Equo (remove) :: "+str(currentqueue)+" of "+totalqueue+" ::"
            print_info(red(" -- ")+bold("(")+blue(str(currentqueue))+"/"+red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.pkgmeta['removeatom']))

            rc = Package.run(xterm_header = xterm_header)
            if rc != 0:
                return -1, rc

        # update resume cache
        if idpackage in resume_cache['removalQueue']:
            resume_cache['removalQueue'].remove(idpackage)
        try:
            Equo.dumpTools.dumpobj(etpCache['remove'], resume_cache)
        except (OSError, IOError, EOFError):
            pass

        Package.kill()
        del metaopts
        del Package

    print_info(red(" @@ ")+blue("%s." % (_("All done"),) ))
    return 0, 0

def unusedPackagesTest(do_size_sort = False):
    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue("%s ..." % (
            _("Running unused packages test, pay attention, there are false positives"),) ))

    unused = Equo.unused_packages_test()
    data = [(Equo.clientDbconn.retrieveOnDiskSize(x), x, \
        Equo.clientDbconn.retrieveAtom(x),) for x in unused]

    if do_size_sort:
        data = sorted(data, key = lambda x: x[0])

    if etpUi['quiet']:
        print_generic('\n'.join([x[2] for x in data]))
    else:
        for disk_size, idpackage, atom in data:
            disk_size = Equo.entropyTools.bytes_into_human(disk_size)
            print_info("# %s%s%s %s" % (
                blue("["), brown(disk_size), blue("]"), darkgreen(atom),))

    return 0, 0

def dependenciesTest():

    print_info(red(" @@ ")+blue("%s ..." % (_("Running dependency test"),) ))
    depsNotMatched = Equo.dependencies_test()

    if depsNotMatched:

        crying_atoms = {}
        found_deps = set()
        for dep in depsNotMatched:

            riddep = Equo.clientDbconn.searchDependency(dep)
            if riddep != -1:
                ridpackages = Equo.clientDbconn.searchIdpackageFromIddependency(riddep)
                for i in ridpackages:
                    iatom = Equo.clientDbconn.retrieveAtom(i)
                    if dep not in crying_atoms:
                        crying_atoms[dep] = set()
                    crying_atoms[dep].add(iatom)

            match = Equo.atom_match(dep)
            if match[0] != -1:
                found_deps.add(dep)
                continue
            else:
                iddep = Equo.clientDbconn.searchDependency(dep)
                if iddep == -1: continue
                c_idpackages = Equo.clientDbconn.searchIdpackageFromIddependency(iddep)
                for c_idpackage in c_idpackages:
                    key, slot = Equo.clientDbconn.retrieveKeySlot(c_idpackage)
                    key_slot = "%s:%s" % (key, slot,)
                    match = Equo.atom_match(key, matchSlot = slot)

                    cmpstat = 0
                    if match[0] != -1:
                        cmpstat = Equo.get_package_action(match)
                    if cmpstat != 0:
                        found_deps.add(key_slot)
                        continue

        print_info(red(" @@ ")+blue("%s:" % (_("These are the dependencies not found"),) ))
        for atom in depsNotMatched:
            print_info("   # "+red(atom))
            if atom in crying_atoms:
                print_info(blue("      # ")+red("%s:" % (_("Needed by"),) ))
                for x in crying_atoms[atom]:
                    print_info(blue("      # ")+darkgreen(x))

        if (etpUi['ask']):
            rc = Equo.askQuestion("     %s"  % (_("Would you like to install the available packages ?"),) )
            if rc == _("No"):
                return 0, 0
        else:
            mytxt = "%s %s %s" % (
                blue(_("Installing available packages in")),
                red(_("10 seconds")),
                blue("..."),
            )
            print_info(red(" @@ ")+mytxt)
            import time
            time.sleep(10)

        installPackages(list(found_deps))

    return 0, 0

def librariesTest(listfiles = False, dump = False):

    def restore_qstats():
        etpUi['mute'] = mstat
        etpUi['quiet'] = mquiet

    mstat = etpUi['mute']
    mquiet = etpUi['quiet']
    if listfiles:
        etpUi['mute'] = True
        etpUi['quiet'] = True

    QA = Equo.QA()
    packagesMatched, brokenlibs, status = QA.test_shared_objects(Equo.clientDbconn,
        dump_results_to_file = dump)
    if status != 0:
        restore_qstats()
        return -1, 1

    if listfiles:
        for x in brokenlibs:
            print(x)
        restore_qstats()
        return 0, 0

    if (not brokenlibs) and (not packagesMatched):
        if not etpUi['quiet']: print_info(red(" @@ ")+blue("%s." % (_("System is healthy"),) ))
        restore_qstats()
        return 0, 0

    atomsdata = set()
    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("%s:" % (_("Libraries/Executables statistics"),) ))
        if brokenlibs:
            print_info(brown(" ## ")+red("%s:" % (_("Not matched"),) ))
            brokenlibs = sorted(brokenlibs)
            for lib in brokenlibs:
                print_info(darkred("    => ")+red(lib))
        print_info(darkgreen(" ## ")+red("%s:" % (_("Matched"),) ))
        for mylib in packagesMatched:
            for idpackage, repoid in packagesMatched[mylib]:
                dbconn = Equo.open_repository(repoid)
                myatom = dbconn.retrieveAtom(idpackage)
                atomsdata.add((idpackage, repoid))
                print_info("   "+red(mylib)+" => "+brown(myatom)+" ["+red(repoid)+"]")
    else:
        for mylib in packagesMatched:
            for idpackage, repoid in packagesMatched[mylib]:
                dbconn = Equo.open_repository(repoid)
                myatom = dbconn.retrieveAtom(idpackage)
                atomsdata.add((idpackage, repoid))
                print(myatom)
        restore_qstats()
        return 0, atomsdata

    if (etpUi['pretend']):
        restore_qstats()
        return 0, atomsdata

    if (atomsdata):
        if (etpUi['ask']):
            rc = Equo.askQuestion("     %s" % (_("Would you like to install them ?"),) )
            if rc == _("No"):
                restore_qstats()
                return 0, atomsdata
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
            return 0, atomsdata
        else:
            restore_qstats()
            return rc[0], atomsdata

    restore_qstats()
    return 0, atomsdata
