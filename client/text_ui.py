# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""

########################################################
####
##   Packages user handling function
#
import os
import shutil

from entropy.exceptions import SystemDatabaseError
from entropy.const import etpConst, etpUi, const_convert_to_unicode
from entropy.output import red, blue, brown, darkred, bold, darkgreen, bold, \
    darkblue, purple, print_error, print_info, print_warning, writechar, \
    readtext, print_generic
from entropy.client.interfaces import Client
from entropy.i18n import _
from text_tools import countdown, enlightenatom

import entropy.tools
import entropy.dump

E_CLIENT = None
EQUO_CACHE_IDS = {
    'install': 'resume/resume_install', # resume cache (install)
    'remove': 'resume/resume_remove', # resume cache (remove)
    'world': 'resume/resume_world', # resume cache (world)
}

def get_file_pager():
    return os.getenv("PAGER")

def package(options):

    if not options:
        return 0

    # Options available for all the packages submodules
    myopts = options[1:]
    e_req_deps = True
    e_req_empty_deps = False
    e_req_only_fetch = False
    e_req_deep = False
    e_req_relaxed = False
    e_req_config_files = False
    e_req_replay = False
    e_req_resume = False
    e_req_skipfirst = False
    e_req_listfiles = False
    e_req_checksum = True
    e_req_sort_size = False
    e_req_save_here = False
    e_req_dump = False
    e_req_bdeps = False
    e_req_multifetch = 1
    rc = 0
    _myopts = []
    my_etp_pkg_paths = []
    get_pkgs_opts = ("install", "world", "upgrade", "source", "fetch")
    for opt in myopts:
        if not entropy.tools.is_valid_unicode(opt):
            print_error(red(" %s." % (_("Malformed command"),) ))
            return -10
        try:
            opt = const_convert_to_unicode(opt, 'utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError,):
            print_error(red(" %s." % (_("Malformed command"),) ))
            return -10
        if (opt == "--nodeps"):
            e_req_deps = False
        elif (opt == "--bdeps") and (options[0] in get_pkgs_opts):
            e_req_bdeps = True
        elif (opt == "--empty"):
            e_req_empty_deps = True
        elif (opt == "--relaxed"):
            e_req_relaxed = True
        elif (opt == "--fetch"):
            e_req_only_fetch = True
        elif (opt == "--deep"):
            e_req_deep = True
        elif (opt == "--dump"):
            e_req_dump = True
        elif (opt == "--listfiles"):
            e_req_listfiles = True
        elif (opt == "--configfiles"):
            e_req_config_files = True
        elif (opt == "--replay"):
            e_req_replay = True
        elif (opt == "--resume"):
            e_req_resume = True
        elif (opt == "--sortbysize"):
            e_req_sort_size = True
        elif (opt == "--savehere"):
            e_req_save_here = True
        elif (opt == "--multifetch"):
            e_req_multifetch = 3
        elif (opt.startswith("--multifetch=")):
            try:
                myn = int(opt[len("--multifetch="):])
            except ValueError:
                continue
            if myn not in list(range(2, 11)):
                myn = 10
            e_req_multifetch = myn
        elif (opt == "--nochecksum"):
            e_req_checksum = False
        elif (opt == "--skipfirst"):
            e_req_skipfirst = True
        elif (opt.startswith("--")):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return -10
        else:
            if opt.startswith("--"):
                continue
            etp_file = entropy.tools.is_entropy_package_file(opt)
            if etp_file:
                opt = os.path.abspath(opt)
                my_etp_pkg_paths.append(opt)
            elif opt.strip():
                _myopts.append(opt.strip())
    myopts = _myopts

    global E_CLIENT
    E_CLIENT = Client()

    try:
        if options[0] == "deptest":
            rc, garbage = dependencies_test()

        elif options[0] == "unusedpackages":
            rc, garbage = unused_packages_test(do_size_sort = e_req_sort_size)

        elif options[0] == "libtest":
            rc, garbage = libraries_test(listfiles = e_req_listfiles,
                dump = e_req_dump)

        elif options[0] == "source":

            if myopts or my_etp_pkg_paths:
                rc, status = download_sources(myopts, deps = e_req_deps,
                    deepdeps = e_req_deep, pkgs = my_etp_pkg_paths,
                    savecwd = e_req_save_here,
                    relaxed_deps = e_req_relaxed,
                    build_deps = e_req_bdeps)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif options[0] == "fetch":

            if myopts or my_etp_pkg_paths:
                rc, status = download_packages(myopts, deps = e_req_deps,
                    deepdeps = e_req_deep,
                    multifetch = e_req_multifetch,
                    dochecksum = e_req_checksum,
                    relaxed_deps = e_req_relaxed,
                    build_deps = e_req_bdeps)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif options[0] == "install":
            if myopts or my_etp_pkg_paths or e_req_resume:
                rc, garbage = install_packages(myopts, deps = e_req_deps,
                    emptydeps = e_req_empty_deps,
                    onlyfetch = e_req_only_fetch, deepdeps = e_req_deep,
                    config_files = e_req_config_files, pkgs = my_etp_pkg_paths,
                    resume = e_req_resume, skipfirst = e_req_skipfirst,
                    dochecksum = e_req_checksum,
                    multifetch = e_req_multifetch,
                    check_critical_updates = True,
                    relaxed_deps = e_req_relaxed,
                    build_deps = e_req_bdeps)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif options[0] in ("world", "upgrade"):
            if options[0] == "world": # print deprecation warning
                print_warning("")
                print_warning("'%s' %s: '%s'" % (
                    purple("equo world"),
                    blue(_("is deprecated, please use")),
                    darkgreen("equo upgrade"),))
                print_warning("")
            rc, status = upgrade_packages(onlyfetch = e_req_only_fetch,
                replay = (e_req_replay or e_req_empty_deps),
                resume = e_req_resume,
                skipfirst = e_req_skipfirst, human = True,
                dochecksum = e_req_checksum,
                multifetch = e_req_multifetch,
                build_deps = e_req_bdeps)

        elif options[0] == "hop":
            if myopts:
                rc, status = branch_hop(myopts[0])
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif options[0] == "remove":
            if myopts or e_req_resume:
                rc, status = remove_packages(myopts, deps = e_req_deps,
                deep = e_req_deep, remove_config_files = e_req_config_files,
                resume = e_req_resume)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif options[0] == "config":
            if myopts:
                rc, status = configure_packages(myopts)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif options[0] == "mask":
            if myopts:
                rc, status = mask_unmask_packages(myopts, options[0])
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif options[0] == "unmask":
            if myopts:
                rc, status = mask_unmask_packages(myopts, options[0])
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        else:
            rc = -10

        conf_cache_excl = ("hop", "fetch", "source", "deptest", "libtest",
            "unusedpackages", "mask", "unmask")
        if (options[0] not in conf_cache_excl) and (rc not in (125, 126, -10)) \
            and (not etpUi['pretend']) and (not etpUi['quiet']):
            show_config_files_to_update()

    finally:
        E_CLIENT.destroy()

    return rc

def show_config_files_to_update():

    if not etpUi['quiet']:
        print_info(red(" @@ ") + \
            blue(_("Scanning configuration files to update")), back = True)

    try:
        while True:
            try:
                scandata = E_CLIENT.FileUpdates.scanfs(dcache = True, quiet = True)
                break
            except KeyboardInterrupt:
                continue
    except:
        entropy.tools.print_traceback()
        if not etpUi['quiet']:
            print_warning(red(" @@ ") + \
                blue(_("Unable to scan configuration files to update.")))
        return

    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue(_("Configuration files scan complete.")))

    if scandata is None:
        return

    if len(scandata) > 0: # strict check
        if not etpUi['quiet']:
            mytxt = "%s %s %s." % (
                _("There are"),
                len(scandata),
                _("configuration file(s) needing update"),
            )
            print_warning(darkgreen(mytxt))
            mytxt = "%s: %s" % (red(_("Please run")), bold("equo conf update"))
            print_warning(mytxt)

def _upgrade_package_handle_calculation(resume, replay, onlyfetch):
    if not resume:

        try:
            update, remove, fine, spm_fine = E_CLIENT.calculate_updates(
                empty_deps = replay)
        except SystemDatabaseError:
            # handled in equo.py
            raise

        if etpUi['verbose'] or etpUi['pretend']:
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

        # clear old resume information
        entropy.dump.dumpobj(EQUO_CACHE_IDS['world'], {})
        entropy.dump.dumpobj(EQUO_CACHE_IDS['install'], {})
        entropy.dump.dumpobj(EQUO_CACHE_IDS['remove'], [])
        if not etpUi['pretend']:
            # store resume information
            resume_cache = {}
            resume_cache['ask'] = etpUi['ask']
            resume_cache['verbose'] = etpUi['verbose']
            resume_cache['onlyfetch'] = onlyfetch
            resume_cache['remove'] = remove
            entropy.dump.dumpobj(EQUO_CACHE_IDS['world'], resume_cache)

        return update, remove, onlyfetch, True

    # check if there's something to resume
    resume_cache = entropy.dump.loadobj(EQUO_CACHE_IDS['world'])
    if (not resume_cache) or (not entropy.tools.is_root()): # None or {}
        print_error(red("%s." % (_("Nothing to resume"),) ))
        return None, None, None, False

    try:
        update = []
        remove = resume_cache['remove']
        etpUi['ask'] = resume_cache['ask']
        etpUi['verbose'] = resume_cache['verbose']
        onlyfetch = resume_cache['onlyfetch']
        entropy.dump.dumpobj(EQUO_CACHE_IDS['remove'], list(remove))
    except KeyError:
        print_error(red("%s." % (_("Resume cache corrupted"),) ))
        entropy.dump.dumpobj(EQUO_CACHE_IDS['world'], {})
        entropy.dump.dumpobj(EQUO_CACHE_IDS['install'], {})
        entropy.dump.dumpobj(EQUO_CACHE_IDS['remove'], [])
        onlyfetch = False
        return None, None, None, False

    return update, remove, onlyfetch, True

def upgrade_packages(onlyfetch = False, replay = False, resume = False,
    skipfirst = False, human = False, dochecksum = True, multifetch = 1,
    build_deps = False):

    # check if I am root
    if not entropy.tools.is_root():
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    print_info(red(" @@ ")+blue("%s..." % (_("Calculating System Updates"),) ))

    update, remove, onlyfetch, valid = _upgrade_package_handle_calculation(
        resume, replay, onlyfetch)
    if not valid:
        return 128, -1

    # disable collisions protection, better
    sys_set_client_plg_id = \
        etpConst['system_settings_plugins_ids']['client_plugin']
    equo_client_settings = E_CLIENT.SystemSettings[sys_set_client_plg_id]['misc']
    oldcollprotect = equo_client_settings['collisionprotect']
    equo_client_settings['collisionprotect'] = 1

    if update or resume:
        rc = install_packages(
            atomsdata = update,
            onlyfetch = onlyfetch,
            resume = resume,
            skipfirst = skipfirst,
            dochecksum = dochecksum,
            deepdeps = True,
            multifetch = multifetch,
            build_deps = build_deps
        )
        if rc[1] != 0:
            return rc
    else:
        print_info(red(" @@ ") + \
            blue("%s." % (_("Nothing to update"),) ))

    equo_client_settings['collisionprotect'] = oldcollprotect

    # verify that client database idpackage still exist,
    # validate here before passing removePackage() wrong info
    remove = [x for x in remove if E_CLIENT.clientDbconn.isIdpackageAvailable(x)]
    # Filter out packages installed from unavailable repositories, this is
    # mainly required to allow 3rd party packages installation without
    # erroneously inform user about unavailability.
    remove = [x for x in remove if \
        E_CLIENT.clientDbconn.getInstalledPackageRepository(x) in \
            E_CLIENT.validRepositories]

    if remove and E_CLIENT.validRepositories and (not onlyfetch):
        remove = sorted(remove)
        print_info(red(" @@ ") + \
            blue("%s." % (
                    _("On the system there are packages that are not available anymore in the online repositories"),
                )
            )
        )
        print_info(red(" @@ ")+blue(
            _("Even if they are usually harmless, it is suggested to remove them.")))

        do_run = True
        if not etpUi['pretend']:
            do_run = False
            if human:
                do_run = True
                rc = E_CLIENT.ask_question("     %s" % (
                    _("Would you like to scan them ?"),) )
                if rc == _("No"):
                    do_run = False

        if do_run:
            remove_packages(
                atomsdata = remove,
                deps = False,
                system_packages_check = False,
                remove_config_files = True,
                resume = resume,
                human = human
            )

    else:
        print_info(red(" @@ ")+blue("%s." % (_("Nothing to remove"),) ))

    # run post-branch upgrade hooks, if needed
    if not etpUi['pretend']:
        # this triggers post-branch upgrade function inside
        # Entropy Client SystemSettings plugin
        E_CLIENT.SystemSettings.clear()

    return 0, 0

def branch_hop(branch):

    # check if I am root
    if (not entropy.tools.is_root()):
        mytxt = "%s." % (darkred(_("Cannot switch branch as user")),)
        print_error(mytxt)
        return 1, -1

    # set the new branch
    if branch == E_CLIENT.SystemSettings['repositories']['branch']:
        mytxt = "%s %s: %s" % (bold(" !!! "),
            darkred(_("Already on branch")), purple(branch),)
        print_warning(mytxt)
        return 2, -1

    old_repo_paths = []
    avail_data = E_CLIENT.SystemSettings['repositories']['available']
    for repoid in sorted(avail_data):
        old_repo_paths.append(avail_data[repoid]['dbpath'][:])

    old_branch = E_CLIENT.SystemSettings['repositories']['branch'][:]
    E_CLIENT.set_branch(branch)
    status = True

    try:
        repo_intf = E_CLIENT.Repositories(None, force = False,
            fetch_security = False)
    except AttributeError as err:
        print_error(darkred(" * ")+red("%s %s [%s]" % (
            _("No repositories specified in"),
            etpConst['repositoriesconf'], err,)))
        status = False
    except Exception as e:
        print_error(darkred(" @@ ")+red("%s: %s" % (
            _("Unhandled exception"), e,)))
        status = False
    else:
        rc = repo_intf.sync()
        if rc and rc != 1:
            # rc != 1 means not all the repos have been downloaded
            status = False

    if status:

        E_CLIENT.clientDbconn.moveSpmUidsToBranch(branch)

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
                _("Now run 'equo upgrade' to upgrade your distribution to")),
            )
        print_info(mytxt)
        return 0, 0
    else:
        E_CLIENT.set_branch(old_branch)
        mytxt = "%s %s: %s" % (bold(" !!! "),
            darkred(_("Unable to switch to branch")), purple(branch),)
        print_error(mytxt)
        return 3, -2

def _show_masked_pkg_info(package, from_user = True):

    masked_matches = E_CLIENT.atom_match(package, packagesFilter = False,
        multiMatch = True)
    if masked_matches[1] == 0:

        mytxt = "%s %s %s %s." % (
            bold("!!!"),
            # every package matching app-foo is masked
            red(_("Every package matching")),
            bold(package),
            red(_("is masked")),
        )
        print_warning(mytxt)

        m_reasons = {}
        for match in masked_matches[0]:
            masked, idreason, reason = E_CLIENT.get_masked_package_reason(
                match)
            if not masked:
                continue
            reason_obj = (idreason, reason,)
            obj = m_reasons.setdefault(reason_obj, [])
            obj.append(match)

        for idreason, reason in sorted(m_reasons.keys()):
            print_warning(bold("    # ")+red("Reason: ")+blue(reason))
            for m_idpackage, m_repo in m_reasons[(idreason, reason)]:
                dbconn = E_CLIENT.open_repository(m_repo)
                try:
                    m_atom = dbconn.retrieveAtom(m_idpackage)
                except TypeError:
                    m_atom = "idpackage: %s %s %s %s" % (
                        m_idpackage,
                        _("matching"),
                        package,
                        _("is broken"),
                    )
                print_warning("%s %s: %s %s %s" % (
                    blue("      <>"),
                    red(_("atom")),
                    brown(m_atom),
                    red(_("in")),
                    purple(m_repo),
                ))

    elif from_user:

        mytxt = "%s %s %s %s." % (
            bold("!!!"),
            red(_("No match for")),
            bold(package),
            red(_("in repositories")),
        )
        print_warning(mytxt)
        # search similar packages
        # you meant...?
        if len(package) > 3:
            _show_you_meant(package, False)

    else:
        print_error(red("    # ")+blue("%s: " % (_("Not found"),) ) + \
            brown(package))
        crying_atoms = E_CLIENT.find_belonging_dependency([package])
        if crying_atoms:
            print_error(red("      # ") + \
                blue("%s:" % (_("Probably needed by"),) ))
            for c_atom, c_repo in crying_atoms:
                print_error(red("        # ")+" ["+blue(_("from"))+":" + \
                    brown(c_repo)+"] "+darkred(c_atom))


def _scan_packages(packages, etp_pkg_files):

    found_pkg_atoms = []

    # expand package
    packages = E_CLIENT.packages_expand(packages)

    for package in packages:
        # clear masking reasons
        match = E_CLIENT.atom_match(package)
        if match[0] != -1:
            if match not in found_pkg_atoms:
                found_pkg_atoms.append(match)
            continue
        _show_masked_pkg_info(package)

    if etp_pkg_files:
        for pkg in etp_pkg_files:
            status, atomsfound = E_CLIENT.add_package_to_repos(pkg)
            if status == 0:
                found_pkg_atoms += atomsfound[:]
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
                raise AttributeError("invalid package %s" % (pkg,))

    return found_pkg_atoms

def _show_package_info(found_pkg_atoms, deps, action_name = None):

    if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
        # now print the selected packages
        print_info(red(" @@ ")+blue("%s:" % (_("These are the chosen packages"),) ))
        totalatoms = len(found_pkg_atoms)
        atomscounter = 0
        for idpackage, reponame in found_pkg_atoms:
            atomscounter += 1
            # open database
            dbconn = E_CLIENT.open_repository(reponame)

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
            pkginstalled = E_CLIENT.clientDbconn.atomMatch(
                entropy.tools.dep_getkey(pkgatom), matchSlot = pkgslot)
            if (pkginstalled[1] == 0):
                # found
                idx = pkginstalled[0]
                installedVer = E_CLIENT.clientDbconn.retrieveVersion(idx)
                installedTag = E_CLIENT.clientDbconn.retrieveVersionTag(idx)
                installedRepo = E_CLIENT.clientDbconn.getInstalledPackageRepository(idx)
                if installedRepo is None:
                    installedRepo = _("Not available")
                if not installedTag:
                    installedTag = "NoTag"
                installedRev = E_CLIENT.clientDbconn.retrieveRevision(idx)

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

            pkgcmp = E_CLIENT.get_package_action((idpackage, reponame))
            if (pkgcmp == 0) and is_installed:
                if installedRepo != reponame:
                    mytxt = " | %s: " % (_("Switch repo"),)
                    action = darkgreen(_("Reinstall"))+mytxt + \
                        blue(installedRepo)+" ===> "+darkgreen(reponame)
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
            print_info(red(" @@ ")+blue("%s: " % (_("Packages involved"),) ) + \
                str(totalatoms))

        if etpUi['ask']:
            if deps:
                rc = E_CLIENT.ask_question("     %s" % (
                    _("Would you like to continue with dependencies calculation ?"),) )
            else:
                rc = E_CLIENT.ask_question("     %s" % (
                    _("Would you like to continue ?"),) )
            if rc == _("No"):
                return True, (126, -1)

    return False, (0, 0)

def _show_you_meant(package, from_installed):
    items = E_CLIENT.get_meant_packages(package,
        from_installed = from_installed)
    if not items:
        return

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
        if from_installed:
            dbconn = E_CLIENT.clientDbconn
            idpackage = match[0]
        else:
            dbconn = E_CLIENT.open_repository(match[1])
            idpackage = match[0]
        key, slot = dbconn.retrieveKeySlot(idpackage)
        if (key, slot) not in items_cache:
            print_info(red("    # ")+blue(key)+":" + \
                brown(str(slot))+red(" ?"))
        items_cache.add((key, slot))

def _generate_run_queue(found_pkg_atoms, deps, emptydeps, deepdeps, relaxeddeps,
    builddeps):

    run_queue = []
    removal_queue = []

    if deps:
        print_info(red(" @@ ")+blue("%s ...") % (
            _("Calculating dependencies"),) )
        run_queue, removal_queue, status = E_CLIENT.get_install_queue(
            found_pkg_atoms, emptydeps, deepdeps, relaxed_deps = relaxeddeps,
            build_deps = builddeps)
        if status == -2:
            print_error(red(" @@ ") + blue("%s: " % (
                _("Cannot find needed dependencies"),) ))
            for package in run_queue:
                _show_masked_pkg_info(package, from_user = False)
            return True, (125, -1), []

    else:
        for atomInfo in found_pkg_atoms:
            run_queue.append(atomInfo)

    return False, run_queue, removal_queue

def download_sources(packages = None, deps = True, deepdeps = False,
    pkgs = None, savecwd = False, relaxed_deps = False, build_deps = False):

    if packages is None:
        packages = []
    if pkgs is None:
        pkgs = []

    found_pkg_atoms = _scan_packages(packages, pkgs)
    # are there packages in found_pkg_atoms?
    if not found_pkg_atoms:
        print_error( red("%s." % (_("No packages found"),) ))
        return 125, -1

    action = darkgreen(_("Source code download"))
    abort, myrc = _show_package_info(found_pkg_atoms, deps, action_name = action)
    if abort:
        return myrc

    abort, run_queue, removal_queue = _generate_run_queue(found_pkg_atoms, deps,
        False, deepdeps, relaxed_deps, build_deps)
    if abort:
        return run_queue

    if etpUi['pretend']:
        return 0, 0

    totalqueue = str(len(run_queue))
    fetchqueue = 0
    metaopts = {}
    if savecwd:
        metaopts['fetch_path'] = os.getcwd()

    for match in run_queue:
        fetchqueue += 1

        Package = E_CLIENT.Package()

        Package.prepare(match, "source", metaopts)

        xterm_header = "equo ("+_("sources fetch")+") :: " + \
            str(fetchqueue)+" of "+totalqueue+" ::"
        print_info(red(" :: ")+bold("(")+blue(str(fetchqueue))+"/" + \
            red(totalqueue)+bold(") ")+">>> " + \
                darkgreen(Package.pkgmeta['atom']))

        rc = Package.run(xterm_header = xterm_header)
        if rc != 0:
            return -1, rc
        Package.kill()

        del Package

    return 0, 0

def _fetch_packages(run_queue, downdata, multifetch = 1, dochecksum = True):
    totalqueue = str(len(run_queue))

    fetchqueue = 0
    mymultifetch = multifetch
    if multifetch > 1:
        myqueue = []
        mystart = 0
        while True:
            mylist = run_queue[mystart:mymultifetch]
            if not mylist: break
            myqueue.append(mylist)
            mystart += multifetch
            mymultifetch += multifetch
        mytotalqueue = str(len(myqueue))

        for matches in myqueue:
            fetchqueue += 1

            metaopts = {}
            metaopts['dochecksum'] = dochecksum
            Package = E_CLIENT.Package()
            Package.prepare(matches, "multi_fetch", metaopts)
            myrepo_data = Package.pkgmeta['repository_atoms']
            for myrepo in myrepo_data:
                if myrepo not in downdata:
                    downdata[myrepo] = set()
                for myatom in myrepo_data[myrepo]:
                    downdata[myrepo].add(entropy.tools.dep_getkey(myatom))

            xterm_header = "E_CLIENT ("+_("fetch")+") :: "+str(fetchqueue)+" of "+mytotalqueue+" ::"
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
    for match in run_queue:
        fetchqueue += 1

        metaopts = {}
        metaopts['dochecksum'] = dochecksum
        Package = E_CLIENT.Package()
        Package.prepare(match, "fetch", metaopts)
        myrepo = Package.pkgmeta['repository']
        if myrepo not in downdata:
            downdata[myrepo] = set()
        downdata[myrepo].add(entropy.tools.dep_getkey(Package.pkgmeta['atom']))

        xterm_header = "E_CLIENT ("+_("fetch")+") :: "+str(fetchqueue)+" of "+totalqueue+" ::"
        print_info(red(" :: ")+bold("(")+blue(str(fetchqueue))+"/"+ \
                        red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.pkgmeta['atom']))

        rc = Package.run(xterm_header = xterm_header)
        if rc != 0:
            return -1, rc
        Package.kill()
        del metaopts
        del Package

    return 0, 0


def download_packages(packages = None, deps = True, deepdeps = False,
    multifetch = 1, dochecksum = True, relaxed_deps = False,
    build_deps = False):

    if packages is None:
        packages = []

    # check if I am root
    if (not entropy.tools.is_root()):
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True


    found_pkg_atoms = _scan_packages(packages, None)

    # are there packages in found_pkg_atoms?
    if not found_pkg_atoms:
        print_error( red("%s." % (_("No packages found"),) ))
        return 125, -1

    action = brown(_("Download"))
    abort, myrc = _show_package_info(found_pkg_atoms, deps,
        action_name = action)
    if abort:
        return myrc

    abort, run_queue, removal_queue = _generate_run_queue(found_pkg_atoms, deps,
        False, deepdeps, relaxed_deps, build_deps)
    if abort:
        return run_queue

    if etpUi['pretend']:
        return 0, 0

    downdata = {}
    func_rc, fetch_rc = _fetch_packages(run_queue, downdata, multifetch,
        dochecksum)
    if func_rc == 0:
        _spawn_ugc(downdata)
    return func_rc, fetch_rc

def _spawn_ugc(mykeys):
    if E_CLIENT.UGC is None:
        return
    for myrepo in mykeys:
        mypkgkeys = sorted(mykeys[myrepo])
        try:
            E_CLIENT.UGC.add_download_stats(myrepo, mypkgkeys)
        except:
            pass

def install_packages(packages = None, atomsdata = None, deps = True,
    emptydeps = False, onlyfetch = False, deepdeps = False,
    config_files = False, pkgs = None, resume = False, skipfirst = False,
    dochecksum = True, multifetch = 1, check_critical_updates = False,
    relaxed_deps = False, build_deps = False):

    if packages is None:
        packages = []
    if atomsdata is None:
        atomsdata = []
    if pkgs is None:
        pkgs = []

    # check if I am root
    if not entropy.tools.is_root():
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    explicit_user_packages = set()

    sys_set_client_plg_id = \
        etpConst['system_settings_plugins_ids']['client_plugin']
    equo_client_settings = E_CLIENT.SystemSettings[sys_set_client_plg_id]['misc']

    if check_critical_updates and equo_client_settings.get('forcedupdates'):
        crit_atoms, crit_matches = E_CLIENT.calculate_critical_updates()
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
            found_pkg_atoms = atomsdata
        else:
            found_pkg_atoms = _scan_packages(packages, pkgs)
            explicit_user_packages |= set(found_pkg_atoms)

        # are there packages in found_pkg_atoms?
        if (not found_pkg_atoms):
            print_error( red("%s." % (_("No packages found"),) ))
            return 125, -1

        abort, myrc = _show_package_info(found_pkg_atoms, deps)
        if abort:
            return myrc

        abort, run_queue, removal_queue = _generate_run_queue(found_pkg_atoms,
            deps, emptydeps, deepdeps, relaxed_deps, build_deps)
        if abort:
            return run_queue


        if ((not run_queue) and (not removal_queue)):
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
        pkgsToRemove = len(removal_queue)

        if run_queue:

            if (etpUi['ask'] or etpUi['pretend']):
                mytxt = "%s:" % (blue(_("These are the packages that would be installed")),)
                print_info(red(" @@ ")+mytxt)

            count = 0
            for idpackage, reponame in run_queue:
                count += 1

                dbconn = E_CLIENT.open_repository(reponame)
                pkgatom = dbconn.retrieveAtom(idpackage)
                if not pkgatom:
                    continue
                pkgver = dbconn.retrieveVersion(idpackage)
                pkgtag = dbconn.retrieveVersionTag(idpackage)
                pkgrev = dbconn.retrieveRevision(idpackage)
                pkgslot = dbconn.retrieveSlot(idpackage)
                pkgfile = dbconn.retrieveDownloadURL(idpackage)
                onDiskUsedSize += dbconn.retrieveOnDiskSize(idpackage)

                dl = E_CLIENT.check_needed_package_download(pkgfile, None) # we'll do a good check during installPackage
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
                pkginstalled = E_CLIENT.clientDbconn.atomMatch(
                    entropy.tools.dep_getkey(pkgatom), matchSlot = pkgslot)
                if pkginstalled[1] == 0:
                    # found an installed package
                    idx = pkginstalled[0]
                    installedVer = E_CLIENT.clientDbconn.retrieveVersion(idx)
                    installedTag = E_CLIENT.clientDbconn.retrieveVersionTag(idx)
                    installedRev = E_CLIENT.clientDbconn.retrieveRevision(idx)
                    installedRepo = E_CLIENT.clientDbconn.getInstalledPackageRepository(idx)
                    if installedRepo is None:
                        installedRepo = _("Not available")
                    onDiskFreedSize += E_CLIENT.clientDbconn.retrieveOnDiskSize(idx)

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
                pkgcmp = E_CLIENT.get_package_action((idpackage, reponame))
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

                print_info(darkred(" ##")+flags+repoinfo+enlightenatom(pkgatom)+"|"+red(str(pkgrev))+oldinfo)

        deltaSize = onDiskUsedSize - onDiskFreedSize
        neededSize = deltaSize
        if unpackSize > 0: neededSize += unpackSize

        if removal_queue:

            if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']) and removal_queue:
                mytxt = "%s (%s):" % (
                    blue(_("These are the packages that would be removed")),
                    bold(_("conflicting/substituted")),
                )
                print_info(red(" @@ ")+mytxt)

                for idpackage in removal_queue:
                    pkgatom = E_CLIENT.clientDbconn.retrieveAtom(idpackage)
                    if not pkgatom:
                        continue
                    onDiskFreedSize += E_CLIENT.clientDbconn.retrieveOnDiskSize(idpackage)
                    installedfrom = E_CLIENT.clientDbconn.getInstalledPackageRepository(idpackage)
                    if installedfrom is None:
                        installedfrom = _("Not available")
                    repoinfo = red("[")+brown("%s: " % (_("from"),) )+bold(installedfrom)+red("] ")
                    print_info(red("   ## ")+"["+red("W")+"] "+repoinfo+enlightenatom(pkgatom))

        if (run_queue) or (removal_queue) and not etpUi['quiet']:
            # show download info
            mytxt = "%s: %s" % (blue(_("Packages needing to be installed/updated/downgraded")), red(str(len(run_queue))),)
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
                mysize = str(entropy.tools.bytes_into_human(downloadSize))
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
                bold(str(entropy.tools.bytes_into_human(deltaSize))),
            )
            print_info(red(" @@ ")+mytxt)

            if neededSize < 0:
                neededSize = neededSize*-1

            mytxt = "%s: %s %s" % (
                blue(_("You need at least")),
                blue(str(entropy.tools.bytes_into_human(neededSize))),
                _("of free space"),
            )
            print_info(red(" @@ ")+mytxt)
            # check for disk space and print a warning
            ## unpackSize
            size_match = entropy.tools.check_required_space(etpConst['entropyunpackdir'], neededSize)
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
            rc = E_CLIENT.ask_question("     %s" % (_("Would you like to execute the queue ?"),) )
            if rc == _("No"):
                return 126, -1

        if etpUi['pretend']:
            return 0, 0

        try:
            # clear old resume information
            entropy.dump.dumpobj(EQUO_CACHE_IDS['install'], {})
            # store resume information
            if not pkgs: # entropy packages install resume not supported
                resume_cache = {}
                resume_cache['user_packages'] = explicit_user_packages
                resume_cache['run_queue'] = run_queue[:]
                resume_cache['onlyfetch'] = onlyfetch
                resume_cache['emptydeps'] = emptydeps
                resume_cache['deepdeps'] = deepdeps
                resume_cache['relaxed_deps'] = relaxed_deps
                entropy.dump.dumpobj(EQUO_CACHE_IDS['install'], resume_cache)
        except (IOError, OSError):
            pass

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = entropy.dump.loadobj(EQUO_CACHE_IDS['install'])
        if not resume_cache: # None or {}

            print_error(red("%s." % (_("Nothing to resume"),) ))
            return 128, -1

        else:

            try:
                explicit_user_packages = resume_cache['user_packages']
                run_queue = resume_cache['run_queue'][:]
                onlyfetch = resume_cache['onlyfetch']
                emptydeps = resume_cache['emptydeps']
                deepdeps = resume_cache['deepdeps']
                relaxed_deps = resume_cache['relaxed_deps']
                print_warning(red("%s..." % (_("Resuming previous operations"),) ))
            except (KeyError, TypeError, AttributeError,):
                print_error(red("%s." % (_("Resume cache corrupted"),) ))
                try:
                    entropy.dump.dumpobj(EQUO_CACHE_IDS['install'], {})
                except (IOError, OSError):
                    pass
                return 128, -1

            if skipfirst and run_queue:
                run_queue, x, status = E_CLIENT.get_install_queue(run_queue[1:],
                    emptydeps, deepdeps, relaxed_deps = relaxed_deps,
                    build_deps = build_deps)
                del x # was removal_queue
                # save new queues
                resume_cache['run_queue'] = run_queue
                try:
                    entropy.dump.dumpobj(EQUO_CACHE_IDS['install'], resume_cache)
                except (IOError, OSError):
                    pass

    # running tasks
    totalqueue = str(len(run_queue))
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
    licenses = E_CLIENT.get_licenses_to_accept(run_queue)
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
                dbconn = E_CLIENT.open_repository(match[1])
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
                    filename = E_CLIENT.get_text_license(key, match[1])
                    viewer = get_file_pager()
                    if viewer == None:
                        print_info(red("    %s ! %s %s " % (_("No file viewer"), _("License saved into"), filename,) ))
                        continue
                    os.system(viewer+" "+filename)
                    os.remove(filename)
                    continue
                elif choice == 2:
                    break
                elif choice == 3:
                    E_CLIENT.clientDbconn.acceptLicense(key)
                    break

    if not etpUi['clean'] or onlyfetch:
        mykeys = {}
        # Before starting the real install, fetch packages and verify checksum.
        func_rc, fetch_rc = _fetch_packages(run_queue, mykeys, multifetch,
            dochecksum)
        if func_rc != 0:
            print_info(red(" @@ ")+blue("%s." % (_("Download incomplete"),) ))
            return func_rc, fetch_rc
        _spawn_ugc(mykeys)

    if onlyfetch:
        print_info(red(" @@ ")+blue("%s." % (_("Download complete"),) ))
        return 0, 0

    for match in run_queue:
        currentqueue += 1

        metaopts = {}
        metaopts['removeconfig'] = config_files

        if match in explicit_user_packages:
            metaopts['install_source'] = etpConst['install_sources']['user']
        else:
            metaopts['install_source'] = etpConst['install_sources']['automatic_dependency']

        Package = E_CLIENT.Package()
        Package.prepare(match, "install", metaopts)

        xterm_header = "E_CLIENT ("+_("install")+") :: "+str(currentqueue)+" of "+totalqueue+" ::"
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
        if not pkgs: # pkgs caching not supported
            resume_cache['run_queue'].remove(match)
            try:
                entropy.dump.dumpobj(EQUO_CACHE_IDS['install'], resume_cache)
            except (IOError, OSError):
                pass

        Package.kill()
        del metaopts
        del Package


    del explicit_user_packages
    print_info(red(" @@ ")+blue("%s." % (_("Installation complete"),) ))
    try:
        # clear resume information
        entropy.dump.dumpobj(EQUO_CACHE_IDS['install'], {})
    except (IOError, OSError):
        pass
    return 0, 0

def mask_unmask_packages(packages, action):

    # check if I am root
    if not entropy.tools.is_root():
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    found_pkg_atoms = []
    for package in packages:
        idpackage, repoid = E_CLIENT.atom_match(package, packagesFilter = False)
        if idpackage == -1:
            mytxt = "## %s: %s %s." % (
                red(_("ATTENTION")),
                bold(const_convert_to_unicode(package)),
                red(_("is not available")),
            )
            print_warning(mytxt)
            if len(package) > 3:
                _show_you_meant(package, from_installed = False)
            continue
        found_pkg_atoms.append(package)

    if not found_pkg_atoms:
        print_error(red("%s." % (_("No packages found"),) ))
        return 125, -1

    if etpUi['ask'] or etpUi['pretend']:
        mytxt = "%s:" % (blue(_("These are the packages that would be masked")),)
        print_info(red(" @@ ")+mytxt)

    match_data = {}

    for package in found_pkg_atoms:
        matches, rc = E_CLIENT.atom_match(package, multiMatch = True,
            multiRepo = True, packagesFilter = False)
        match_data[package] = matches


        flags = darkgreen(" [")
        if action == "mask":
            flags += brown("M")
        else:
            flags += red("U")
        flags += darkgreen("] ")
        print_info(darkred(" ##")+flags+purple(package))

        if rc == 0:
            # also show found pkgs
            for idpackage, repoid in matches:
                dbconn = E_CLIENT.open_repository(repoid)
                pkgatom = dbconn.retrieveAtom(idpackage)
                print_info("    -> "+enlightenatom(pkgatom))

    if etpUi['pretend']:
        return 0, 0

    if etpUi['ask']:
        answer = E_CLIENT.ask_question(_("Would you like to continue?"))
        if answer == _("No"):
            return 0, 0

    for package, matches in match_data.items():
        for match in matches:
            # effectively do action
            if action == "mask":
                done = E_CLIENT.mask_match_generic(match, package)
            else:
                done = E_CLIENT.unmask_match_generic(match, package)
            if not done:
                mytxt = "## %s: %s %s." % (
                    red(_("ATTENTION")),
                    bold(const_convert_to_unicode(package)),
                    red(_("action not executed")),
                )
                print_warning(mytxt)

    print_info("Have a nice day.")

    return 0, 0

def configure_packages(packages):

    # check if I am root
    if not entropy.tools.is_root():
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    found_pkg_atoms = []
    packages = E_CLIENT.packages_expand(packages)

    for package in packages:
        idpackage, result = E_CLIENT.clientDbconn.atomMatch(package)
        if idpackage == -1:
            mytxt = "## %s: %s %s." % (
                red(_("ATTENTION")),
                bold(const_convert_to_unicode(package)),
                red(_("is not installed")),
            )
            print_warning(mytxt)
            if len(package) > 3:
                _show_you_meant(package, True)
            continue
        found_pkg_atoms.append(idpackage)

    if not found_pkg_atoms:
        print_error(red("%s." % (_("No packages found"),) ))
        return 125, -1

    atomscounter = 0
    totalatoms = len(found_pkg_atoms)
    for idpackage in found_pkg_atoms:
        atomscounter += 1

        # get needed info
        pkgatom = E_CLIENT.clientDbconn.retrieveAtom(idpackage)
        if not pkgatom:
            continue

        installedfrom = E_CLIENT.clientDbconn.getInstalledPackageRepository(
            idpackage)
        if installedfrom is None:
            installedfrom = _("Not available")
        mytxt = " | %s: " % (_("Installed from"),)
        print_info("   # " + red("(") + brown(str(atomscounter)) + "/" + \
            blue(str(totalatoms))+red(")") + " " + \
            enlightenatom(pkgatom) + mytxt + red(installedfrom))

    if etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']:
        print_info(red(" @@ ")+blue("%s: " % (_("Packages involved"),) ) + \
            str(totalatoms))

    if etpUi['ask']:
        rc = E_CLIENT.ask_question(question = "     %s" % (
            _("Would you like to configure them now ?"),))
        if rc == _("No"):
            return 0, 0

    totalqueue = str(len(found_pkg_atoms))
    currentqueue = 0
    for idpackage in found_pkg_atoms:
        currentqueue += 1
        xterm_header = "Entropy (%s) :: " % (_("configure"),) + \
            str(currentqueue) + " of " + totalqueue + " ::"
        Package = E_CLIENT.Package()
        Package.prepare((idpackage,), "config")
        rc = Package.run(xterm_header = xterm_header)
        if rc not in (0, 3,):
            return -1, rc
        Package.kill()

    return 0, 0

def remove_packages(packages = None, atomsdata = None, deps = True,
    deep = False, system_packages_check = True, remove_config_files = False,
    resume = False, human = False):

    if packages is None:
        packages = []
    if atomsdata is None:
        atomsdata = []

    # check if I am root
    if (not entropy.tools.is_root()):
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True

    doSelectiveRemoval = False

    if not resume:

        found_pkg_atoms = []
        if atomsdata:
            for idpackage in atomsdata:
                if not E_CLIENT.clientDbconn.isIdpackageAvailable(idpackage):
                    continue
                found_pkg_atoms.append(idpackage)
        else:

            # expand package
            packages = E_CLIENT.packages_expand(packages)

            for package in packages:
                idpackage, result = E_CLIENT.clientDbconn.atomMatch(package)
                if idpackage == -1:
                    mytxt = "## %s: %s %s." % (
                        red(_("ATTENTION")),
                        bold(const_convert_to_unicode(package)),
                        red(_("is not installed")),
                    )
                    print_warning(mytxt)
                    if len(package) > 3:
                        _show_you_meant(package, True)
                    continue
                found_pkg_atoms.append(idpackage)

        if not found_pkg_atoms:
            print_error(red("%s." % (_("No packages found"),) ))
            return 125, -1

        plain_removal_queue = []
        package_sizes = {}

        look_for_orphaned_packages = True
        # now print the selected packages
        print_info(red(" @@ ")+blue("%s:" % (
            _("These are the chosen packages"),) ))
        totalatoms = len(found_pkg_atoms)
        atomscounter = 0
        for idpackage in found_pkg_atoms:
            atomscounter += 1

            # get needed info
            pkgatom = E_CLIENT.clientDbconn.retrieveAtom(idpackage)
            if not pkgatom:
                continue

            if system_packages_check:
                valid = E_CLIENT.validate_package_removal(idpackage)
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

            plain_removal_queue.append(idpackage)

            installedfrom = E_CLIENT.clientDbconn.getInstalledPackageRepository(
                idpackage)
            if installedfrom is None:
                installedfrom = _("Not available")
            on_disk_size = E_CLIENT.clientDbconn.retrieveOnDiskSize(idpackage)
            pkg_size = E_CLIENT.clientDbconn.retrieveSize(idpackage)
            disksize = entropy.tools.bytes_into_human(on_disk_size)
            disksizeinfo = " [%s]" % (bold(str(disksize)),)

            print_info("   # " + red("(") + brown(str(atomscounter)) + "/" + \
                blue(str(totalatoms)) + red(")") + \
                " [%s] " % (brown(installedfrom),) + \
                enlightenatom(pkgatom) + disksizeinfo)

            if idpackage not in package_sizes:
                package_sizes[idpackage] = on_disk_size, pkg_size

        if etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']:
            print_info(red(" @@ ") + \
                blue("%s: " % (_("Packages involved"),) ) + str(totalatoms))

        if not plain_removal_queue:
            print_error(red("%s." % (_("Nothing to do"),) ))
            return 126, -1

        if deps:
            question = "     %s" % (
                _("Would you like to calculate dependencies ?"),
            )
        else:
            question = "     %s" % (_("Would you like to remove them now ?"),)
            look_for_orphaned_packages = False

        if etpUi['ask'] and not etpUi['pretend']:
            rc = E_CLIENT.ask_question(question)
            if rc == _("No"):
                look_for_orphaned_packages = False
                if not deps:
                    return 0, 0

        removal_queue = []
        atomscounter = len(plain_removal_queue)

        if look_for_orphaned_packages:
            choosen_removal_queue = E_CLIENT.get_removal_queue(
                plain_removal_queue, deep = deep)
            if choosen_removal_queue:

                print_info(red(" @@ ") + \
                    blue("%s:" % (_("This is the new removal queue"),) ))
                totalatoms = str(len(choosen_removal_queue))

                atomscounter = 0
                for idpackage in choosen_removal_queue:

                    atomscounter += 1
                    rematom = E_CLIENT.clientDbconn.retrieveAtom(idpackage)
                    if not rematom:
                        continue

                    installedfrom = \
                        E_CLIENT.clientDbconn.getInstalledPackageRepository(
                            idpackage)
                    if installedfrom is None:
                        installedfrom = _("Not available")

                    on_disk_size = E_CLIENT.clientDbconn.retrieveOnDiskSize(
                        idpackage)
                    pkg_size = E_CLIENT.clientDbconn.retrieveSize(idpackage)
                    disksize = entropy.tools.bytes_into_human(on_disk_size)
                    repositoryInfo = bold("[") + brown(installedfrom) \
                        + bold("]")
                    stratomscounter = str(atomscounter)

                    while len(stratomscounter) < len(totalatoms):
                        stratomscounter = " "+stratomscounter
                    disksizeinfo = bold(" [")+brown(str(disksize))+bold("]")
                    print_info(darkred(" ## ")+repositoryInfo+" " + \
                        enlightenatom(rematom)+disksizeinfo)

                    if idpackage not in package_sizes:
                        package_sizes[idpackage] = on_disk_size, pkg_size

                removal_queue = choosen_removal_queue

            else:
                writechar("\n")

        mytxt = "%s: %s" % (
            blue(_("Packages needing to be removed")),
            red(str(atomscounter)),
        )
        print_info(red(" @@ ")+mytxt)

        total_removal_size = 0
        total_pkg_size = 0
        for on_disk_size, pkg_size in package_sizes.values():
            total_removal_size += on_disk_size
            total_pkg_size += pkg_size
        human_removal_size = entropy.tools.bytes_into_human(total_removal_size)
        human_pkg_size = entropy.tools.bytes_into_human(total_pkg_size)

        mysizetxt = _("Freed disk space")
        mytxt = "%s: %s" % (
            blue(mysizetxt),
            bold(str(human_removal_size)),
        )
        print_info(red(" @@ ")+mytxt)

        mysizetxt = _("Total bandwidth wasted")
        mytxt = "%s: %s" % (
            blue(mysizetxt),
            bold(str(human_pkg_size)),
        )
        print_info(red(" @@ ")+mytxt)

        if etpUi['pretend']:
            return 0, 0

        if etpUi['ask'] or human:
            question = "     %s" % (
                _("Would you like to proceed ?"),)
            if human:
                question = "     %s" % (
                    _("Would you like to proceed with a selective removal ?"),)
            rc = E_CLIENT.ask_question(question)
            if rc == _("No") and not human:
                return 0, 0
            elif rc == _("Yes") and human:
                doSelectiveRemoval = True
            elif rc == _("No") and human:
                rc = E_CLIENT.ask_question("     %s" % (
                    _("Would you like to skip this step then ?"),))
                if rc == _("Yes"):
                    return 0, 0
        elif deps:
            countdown(
                what = red(" @@ ")+blue("%s " % (_("Starting removal in"),)),
                back = True
            )

        # append at the end requested packages if not in queue
        for idpackage in plain_removal_queue:
            if idpackage not in removal_queue:
                removal_queue.append(idpackage)

        # clear old resume information
        try:
            entropy.dump.dumpobj(EQUO_CACHE_IDS['remove'], {})
            # store resume information
            resume_cache = {}
            resume_cache['doSelectiveRemoval'] = doSelectiveRemoval
            resume_cache['removal_queue'] = removal_queue
            entropy.dump.dumpobj(EQUO_CACHE_IDS['remove'], resume_cache)
        except (OSError, IOError, EOFError):
            pass

    else: # if resume, load cache if possible

        # check if there's something to resume
        resume_cache = entropy.dump.loadobj(EQUO_CACHE_IDS['remove'])
        if not resume_cache: # None or {}
            print_error(red("%s." % (_("Nothing to resume"),) ))
            return 128, -1
        else:
            try:
                removal_queue = resume_cache['removal_queue'][:]
                doSelectiveRemoval = resume_cache['doSelectiveRemoval']
                print_warning(red("%s..." % (_("Resuming previous operations"),) ))
            except:
                print_error(red("%s." % (_("Resume cache corrupted"),) ))
                try:
                    entropy.dump.dumpobj(EQUO_CACHE_IDS['remove'], {})
                except (OSError, IOError):
                    pass
                return 128, -1

    if etpUi['pretend']:
        return 0, 0

    # validate removal_queue
    invalid = set()
    for idpackage in removal_queue:
        try:
            E_CLIENT.clientDbconn.retrieveAtom(idpackage)
        except TypeError:
            invalid.add(idpackage)
    removal_queue = [x for x in removal_queue if x not in invalid]

    totalqueue = str(len(removal_queue))
    currentqueue = 0

    # ask which ones to remove
    if human:
        ignored = []
        for idpackage in removal_queue:
            currentqueue += 1
            atom = E_CLIENT.clientDbconn.retrieveAtom(idpackage)
            if not atom:
                continue
            print_info(red(" -- ")+bold("(")+blue(str(currentqueue)) + "/" + \
                red(totalqueue)+bold(") ")+">>> "+darkgreen(atom))
            if doSelectiveRemoval:
                rc = E_CLIENT.ask_question("     %s" % (_("Remove this one ?"),) )
                if rc == _("No"):
                    # update resume cache
                    ignored.append(idpackage)
        removal_queue = [x for x in removal_queue if x not in ignored]

    totalqueue = str(len(removal_queue))
    currentqueue = 0
    for idpackage in removal_queue:
        currentqueue += 1

        metaopts = {}
        metaopts['removeconfig'] = remove_config_files
        Package = E_CLIENT.Package()
        Package.prepare((idpackage,), "remove", metaopts)
        if 'remove_installed_vanished' not in Package.pkgmeta:

            xterm_header = "E_CLIENT (%s) :: " % (_("remove"),) + \
                str(currentqueue)+" of " + totalqueue+" ::"
            print_info(red(" -- ")+bold("(")+blue(str(currentqueue))+"/" + \
                red(totalqueue)+bold(") ") + ">>> " + \
                darkgreen(Package.pkgmeta['removeatom']))

            rc = Package.run(xterm_header = xterm_header)
            if rc != 0:
                return -1, rc

        # update resume cache
        if idpackage in resume_cache['removal_queue']:
            resume_cache['removal_queue'].remove(idpackage)
        try:
            entropy.dump.dumpobj(EQUO_CACHE_IDS['remove'], resume_cache)
        except (OSError, IOError, EOFError):
            pass

        Package.kill()
        del metaopts
        del Package

    print_info(red(" @@ ")+blue("%s." % (_("All done"),) ))
    return 0, 0

def unused_packages_test(do_size_sort = False):
    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue("%s ..." % (
            _("Running unused packages test, pay attention, there are false positives"),) ))

    unused = E_CLIENT.unused_packages_test()
    data = [(E_CLIENT.clientDbconn.retrieveOnDiskSize(x), x, \
        E_CLIENT.clientDbconn.retrieveAtom(x),) for x in unused]

    if do_size_sort:
        data = sorted(data, key = lambda x: x[0])

    if etpUi['quiet']:
        print_generic('\n'.join([x[2] for x in data]))
    else:
        for disk_size, idpackage, atom in data:
            disk_size = entropy.tools.bytes_into_human(disk_size)
            print_info("# %s%s%s %s" % (
                blue("["), brown(disk_size), blue("]"), darkgreen(atom),))

    return 0, 0

def dependencies_test():

    print_info(red(" @@ ")+blue("%s ..." % (_("Running dependency test"),) ))
    deps_not_matched = E_CLIENT.dependencies_test()

    if deps_not_matched:

        crying_atoms = {}
        found_deps = set()
        for dep in deps_not_matched:

            riddep = E_CLIENT.clientDbconn.searchDependency(dep)
            if riddep != -1:
                ridpackages = E_CLIENT.clientDbconn.searchIdpackageFromIddependency(riddep)
                for i in ridpackages:
                    iatom = E_CLIENT.clientDbconn.retrieveAtom(i)
                    if dep not in crying_atoms:
                        crying_atoms[dep] = set()
                    crying_atoms[dep].add(iatom)

            match = E_CLIENT.atom_match(dep)
            if match[0] != -1:
                found_deps.add(dep)
                continue
            else:
                iddep = E_CLIENT.clientDbconn.searchDependency(dep)
                if iddep == -1:
                    continue
                c_idpackages = E_CLIENT.clientDbconn.searchIdpackageFromIddependency(iddep)
                for c_idpackage in c_idpackages:
                    key, slot = E_CLIENT.clientDbconn.retrieveKeySlot(c_idpackage)
                    key_slot = "%s%s%s" % (key, etpConst['entropyslotprefix'],
                        slot,)
                    match = E_CLIENT.atom_match(key, matchSlot = slot)

                    cmpstat = 0
                    if match[0] != -1:
                        cmpstat = E_CLIENT.get_package_action(match)
                    if cmpstat != 0:
                        found_deps.add(key_slot)
                        continue

        print_info(red(" @@ ")+blue("%s:" % (_("These are the dependencies not found"),) ))
        for atom in deps_not_matched:
            print_info("   # "+red(atom))
            if atom in crying_atoms:
                print_info(blue("      # ")+red("%s:" % (_("Needed by"),) ))
                for x in crying_atoms[atom]:
                    print_info(blue("      # ")+darkgreen(x))

        if etpUi['ask']:
            rc = E_CLIENT.ask_question("     %s"  % (_("Would you like to install the available packages ?"),) )
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

        install_packages(list(found_deps))

    else:
        print_generic("") # make sure to get back

    return 0, 0

def libraries_test(listfiles = False, dump = False):

    def restore_qstats():
        etpUi['mute'] = mstat
        etpUi['quiet'] = mquiet

    mstat = etpUi['mute']
    mquiet = etpUi['quiet']
    if listfiles:
        etpUi['mute'] = True
        etpUi['quiet'] = True

    QA = E_CLIENT.QA()
    pkgs_matched, brokenlibs, status = QA.test_shared_objects(E_CLIENT.clientDbconn,
        dump_results_to_file = dump)
    if status != 0:
        restore_qstats()
        return -1, 1

    if listfiles:
        for x in brokenlibs:
            print(x)
        restore_qstats()
        return 0, 0

    if (not brokenlibs) and (not pkgs_matched):
        if not etpUi['quiet']:
            print_info(red(" @@ ")+blue("%s." % (_("System is healthy"),) ))
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
        for mylib in pkgs_matched:
            for idpackage, repoid in pkgs_matched[mylib]:
                dbconn = E_CLIENT.open_repository(repoid)
                myatom = dbconn.retrieveAtom(idpackage)
                atomsdata.add((idpackage, repoid))
                print_info("   "+red(mylib)+" => "+brown(myatom)+" ["+red(repoid)+"]")
    else:
        for mylib in pkgs_matched:
            for idpackage, repoid in pkgs_matched[mylib]:
                dbconn = E_CLIENT.open_repository(repoid)
                myatom = dbconn.retrieveAtom(idpackage)
                atomsdata.add((idpackage, repoid))
                print(myatom)
        restore_qstats()
        return 0, atomsdata

    if (etpUi['pretend']):
        restore_qstats()
        return 0, atomsdata

    if atomsdata:
        if (etpUi['ask']):
            rc = E_CLIENT.ask_question("     %s" % (_("Would you like to install them ?"),) )
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

        rc = install_packages(atomsdata = list(atomsdata))
        if rc[0] == 0:
            restore_qstats()
            return 0, atomsdata
        else:
            restore_qstats()
            return rc[0], atomsdata

    restore_qstats()
    return 0, atomsdata
