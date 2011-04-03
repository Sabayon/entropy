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
import tempfile

from entropy.exceptions import SystemDatabaseError, DependenciesNotRemovable, \
    EntropyPackageException
from entropy.db.exceptions import OperationalError
from entropy.const import etpConst, etpUi, const_convert_to_unicode
from entropy.output import red, blue, brown, darkred, bold, darkgreen, bold, \
    darkblue, purple, teal, print_error, print_info, print_warning, writechar, \
    readtext, print_generic
from entropy.client.interfaces import Client
from entropy.client.interfaces.package import Package as ClientPkg
from entropy.i18n import _
from text_tools import countdown, enlightenatom

import entropy.dep
import entropy.tools
import entropy.dump

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
    cmd = options[0]
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
    e_req_recursive = True
    e_req_system_packages_check = True
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
        elif (opt == "--bdeps") and (cmd in get_pkgs_opts):
            e_req_bdeps = True
        elif (opt == "--empty"):
            e_req_empty_deps = True
        elif (opt == "--relaxed"):
            e_req_relaxed = True
        elif (opt == "--fetch"):
            e_req_only_fetch = True
        elif (opt == "--deep"):
            e_req_deep = True
        elif (opt == "--no-recursive"):
            e_req_recursive = False
        elif (opt == "--dump"):
            e_req_dump = True
        elif (opt == "--listfiles"):
            e_req_listfiles = True
        elif (opt == "--configfiles"):
            e_req_config_files = True
        elif (opt == "--force-system"):
            e_req_system_packages_check = False
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
            if myn not in range(2, 11):
                myn = 10
            e_req_multifetch = myn
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

    entropy_client = None
    acquired = False
    try:
        entropy_client = Client()
        acquired = entropy.tools.acquire_entropy_locks(entropy_client)
        if not acquired:
            print_error(darkgreen(_("Another Entropy is currently running.")))
            return 1

        if cmd == "deptest":
            rc, garbage = _dependencies_test(entropy_client)

        elif cmd == "unusedpackages":
            rc, garbage = _unused_packages_test(entropy_client,
                do_size_sort = e_req_sort_size)

        elif cmd == "libtest":
            rc, garbage = _libraries_test(entropy_client,
                listfiles = e_req_listfiles, dump = e_req_dump)

        elif cmd == "source":

            if myopts or my_etp_pkg_paths:
                rc, status = _download_sources(entropy_client,
                    packages = myopts, deps = e_req_deps,
                    deepdeps = e_req_deep, pkgs = my_etp_pkg_paths,
                    savecwd = e_req_save_here,
                    relaxed_deps = e_req_relaxed,
                    build_deps = e_req_bdeps,
                    recursive = e_req_recursive)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif cmd == "fetch":

            if myopts:
                rc, status = _download_packages(entropy_client,
                    packages = myopts,
                    deps = e_req_deps,
                    deepdeps = e_req_deep,
                    multifetch = e_req_multifetch,
                    dochecksum = e_req_checksum,
                    relaxed_deps = e_req_relaxed,
                    build_deps = e_req_bdeps,
                    recursive = e_req_recursive)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif cmd == "install":
            if myopts or my_etp_pkg_paths or e_req_resume:
                rc, garbage = install_packages(entropy_client,
                    packages = myopts, deps = e_req_deps,
                    emptydeps = e_req_empty_deps,
                    onlyfetch = e_req_only_fetch, deepdeps = e_req_deep,
                    config_files = e_req_config_files, pkgs = my_etp_pkg_paths,
                    resume = e_req_resume, skipfirst = e_req_skipfirst,
                    dochecksum = e_req_checksum,
                    multifetch = e_req_multifetch,
                    check_critical_updates = True,
                    relaxed_deps = e_req_relaxed,
                    build_deps = e_req_bdeps,
                    recursive = e_req_recursive)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif cmd in ("world", "upgrade"):
            if cmd == "world": # print deprecation warning
                print_warning("")
                print_warning("'%s' %s: '%s'" % (
                    purple("equo world"),
                    blue(_("is deprecated, please use")),
                    darkgreen("equo upgrade"),))
                print_warning("")
            rc, status = upgrade_packages(entropy_client,
                onlyfetch = e_req_only_fetch,
                replay = (e_req_replay or e_req_empty_deps),
                resume = e_req_resume,
                skipfirst = e_req_skipfirst,
                dochecksum = e_req_checksum,
                multifetch = e_req_multifetch,
                build_deps = e_req_bdeps)

        elif cmd == "hop":
            if myopts:
                rc, status = branch_hop(entropy_client, myopts[0])
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif cmd == "remove":
            if myopts or e_req_resume:
                rc, status = remove_packages(entropy_client,
                packages = myopts, deps = e_req_deps,
                deep = e_req_deep, remove_config_files = e_req_config_files,
                resume = e_req_resume, recursive = e_req_recursive,
                system_packages_check = e_req_system_packages_check,
                empty = e_req_empty_deps)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif cmd == "config":
            if myopts:
                rc, status = _configure_packages(entropy_client, myopts)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif cmd == "mask":
            if myopts:
                rc, status = _mask_unmask_packages(entropy_client,
                    myopts, cmd)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        elif cmd == "unmask":
            if myopts:
                rc, status = _mask_unmask_packages(entropy_client,
                    myopts, cmd)
            else:
                print_error(red(" %s." % (_("Nothing to do"),) ))
                rc = 126

        else:
            rc = -10

        conf_cache_excl = ("hop", "fetch", "source", "deptest", "libtest",
            "unusedpackages", "mask", "unmask")
        if (cmd not in conf_cache_excl) and (rc not in (125, 126, -10)) \
            and (not etpUi['pretend']) and (not etpUi['quiet']):
            show_config_files_to_update(entropy_client)

    finally:
        if acquired and (entropy_client is not None):
            entropy.tools.release_entropy_locks(entropy_client)
        if entropy_client is not None:
            entropy_client.shutdown()

    return rc

def show_config_files_to_update(entropy_client):

    if not etpUi['quiet']:
        print_info(red(" @@ ") + \
            blue(_("Scanning configuration files to update")), back = True)

    try:
        file_updates = entropy_client.PackageFileUpdates()
        while True:
            try:
                scandata = file_updates.scan(dcache = True, quiet = True)
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

def _upgrade_package_handle_calculation(entropy_client, resume, replay, onlyfetch):
    if not resume:

        with entropy_client.Cacher():
            try:
                update, remove, fine, \
                    spm_fine = entropy_client.calculate_updates(empty = replay)
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

def upgrade_packages(entropy_client, onlyfetch = False, replay = False,
    resume = False, skipfirst = False, dochecksum = True, multifetch = 1,
    build_deps = False):

    # check if I am root
    if not entropy.tools.is_root():
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True
        etpUi['ask'] = False

    print_info(red(" @@ ")+blue("%s..." % (_("Calculating System Updates"),) ))

    update, remove, onlyfetch, valid = _upgrade_package_handle_calculation(
        entropy_client, resume, replay, onlyfetch)
    if not valid:
        return 128, -1

    # disable collisions protection, better
    sys_set_client_plg_id = \
        etpConst['system_settings_plugins_ids']['client_plugin']
    equo_client_settings = entropy_client.Settings()[sys_set_client_plg_id]['misc']
    oldcollprotect = equo_client_settings['collisionprotect']
    equo_client_settings['collisionprotect'] = 1

    if update or resume:
        rc = install_packages(
            entropy_client,
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
    remove = [x for x in remove if entropy_client.installed_repository().isPackageIdAvailable(x)]
    # Filter out packages installed from unavailable repositories, this is
    # mainly required to allow 3rd party packages installation without
    # erroneously inform user about unavailability.
    unavail_pkgs = [x for x in remove if \
        entropy_client.installed_repository().getInstalledPackageRepository(x) \
        not in entropy_client.repositories()]
    remove = [x for x in remove if x not in unavail_pkgs]
    # drop system packages for automatic removal, user has to do it manually.
    system_unavail_pkgs = [x for x in remove if \
        not entropy_client.validate_package_removal(x)]
    remove = [x for x in remove if x not in system_unavail_pkgs]

    allow_run = entropy_client.repositories() and (not onlyfetch)

    if (unavail_pkgs or remove or system_unavail_pkgs) and allow_run:
        remove.sort()
        unavail_pkgs.sort()
        system_unavail_pkgs.sort()

        print_info(red(" @@ ") + \
            blue("%s." % (
                    _("On the system there are packages that are not available anymore in the online repositories"),
                )
            )
        )
        print_info(red(" @@ ")+blue(
            _("Even if they are usually harmless, it is suggested (after proper verification) to remove them.")))

        if unavail_pkgs:
            _show_package_removal_info(entropy_client, unavail_pkgs, manual = True)
        if system_unavail_pkgs:
            _show_package_removal_info(entropy_client, system_unavail_pkgs, manual = True)
        if remove:
            _show_package_removal_info(entropy_client, remove)

    if remove and allow_run:

        do_run = True
        if not etpUi['pretend']:

            rc = 1
            if not os.getenv("ETP_NONINTERACTIVE"):
                rm_options = [_("Yes"), _("No"), _("Selective")]
                def fake_callback(s):
                    return s

                input_params = [('answer',
                    ('combo', (_('Repository'), rm_options),),
                        fake_callback, False)]
                data = entropy_client.input_box(
                    _('Would you like to remove them?'),
                    input_params
                )
                if data is None:
                    return 0, 0
                rc = data.get('answer', 2)[0]

            if rc == 2: # no
                do_run = False
            elif rc == 3: # selective
                new_remove = []
                c_repo = entropy_client.installed_repository()
                for idpackage in remove:
                    c_atom = c_repo.retrieveAtom(idpackage)
                    if c_atom is None:
                        continue
                    c_atom = purple(c_atom)
                    r_rc = entropy_client.ask_question("[%s] %s" % (
                        c_atom, _("Remove this?"),))
                    if r_rc == _("Yes"):
                        new_remove.append(idpackage)
                remove = new_remove

        if do_run and remove:
            remove_packages(
                entropy_client,
                atomsdata = remove,
                deps = False,
                system_packages_check = False,
                remove_config_files = True,
                resume = resume
            )

    else:
        print_info(red(" @@ ")+blue("%s." % (_("Nothing to remove"),) ))

    # run post-branch upgrade hooks, if needed
    if not etpUi['pretend']:
        # this triggers post-branch upgrade function inside
        # Entropy Client SystemSettings plugin
        entropy_client.Settings().clear()

    return 0, 0

def branch_hop(entropy_client, branch):

    # check if I am root
    if (not entropy.tools.is_root()):
        mytxt = "%s." % (darkred(_("Cannot switch branch as user")),)
        print_error(mytxt)
        return 1, -1

    # set the new branch
    if branch == entropy_client.Settings()['repositories']['branch']:
        mytxt = "%s %s: %s" % (bold(" !!! "),
            darkred(_("Already on branch")), purple(branch),)
        print_warning(mytxt)
        return 2, -1

    old_repo_paths = []
    avail_data = entropy_client.Settings()['repositories']['available']
    for repoid in sorted(avail_data):
        old_repo_paths.append(avail_data[repoid]['dbpath'][:])

    old_branch = entropy_client.Settings()['repositories']['branch'][:]
    entropy_client.set_branch(branch)
    status = True

    try:
        repo_intf = entropy_client.Repositories(None, force = False,
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

        entropy_client.installed_repository().moveSpmUidsToBranch(branch)

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
        entropy_client.set_branch(old_branch)
        mytxt = "%s %s: %s" % (bold(" !!! "),
            darkred(_("Unable to switch to branch")), purple(branch),)
        print_error(mytxt)
        return 3, -2

def _show_masked_pkg_info(entropy_client, package, from_user = True):

    def find_belonging_dependency(package_atoms):
        crying_atoms = set()
        for atom in package_atoms:
            for repo in entropy_client.repositories():
                rdbconn = entropy_client.open_repository(repo)
                riddep = rdbconn.searchDependency(atom)
                if riddep == -1:
                    continue
                ridpackages = rdbconn.searchPackageIdFromDependencyId(riddep)
                for i in ridpackages:
                    i, r = rdbconn.maskFilter(i)
                    if i == -1:
                        continue
                    iatom = rdbconn.retrieveAtom(i)
                    crying_atoms.add((iatom, repo))
        return crying_atoms

    def get_masked_package_reason(match):
        idpackage, repoid = match
        dbconn = entropy_client.open_repository(repoid)
        idpackage, idreason = dbconn.maskFilter(idpackage)
        masked = False
        if idpackage == -1:
            masked = True
        settings = entropy_client.Settings()
        return masked, idreason, settings['pkg_masking_reasons'].get(idreason)

    masked_matches = entropy_client.atom_match(package, mask_filter = False,
        multi_match = True)
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
            masked, idreason, reason = get_masked_package_reason(match)
            if not masked:
                continue
            reason_obj = (idreason, reason,)
            obj = m_reasons.setdefault(reason_obj, [])
            obj.append(match)

        for idreason, reason in sorted(m_reasons.keys()):
            print_warning(bold("    # ")+red("Reason: ")+blue(reason))
            for m_idpackage, m_repo in m_reasons[(idreason, reason)]:
                dbconn = entropy_client.open_repository(m_repo)
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
            _show_you_meant(entropy_client, package, False)

    else:
        print_error(red("    # ")+blue("%s: " % (_("Not found"),) ) + \
            brown(package))
        crying_atoms = find_belonging_dependency([package])
        if crying_atoms:
            print_error(red("      # ") + \
                blue("%s:" % (_("Probably needed by"),) ))
            for c_atom, c_repo in crying_atoms:
                print_error(red("        # ")+" ["+blue(_("from"))+":" + \
                    brown(c_repo)+"] "+darkred(c_atom))

def _scan_packages_expand_tag(entropy_client, packages):
    """
    This function assists the user automatically adding package tags to
    package names passed in order to correctly select installed packages
    in case of multiple package tags available.
    A real-world example is kernel-dependent packages. We don't want to
    implicitly propose user new packages using newer kernels.
    """
    inst_repo = entropy_client.installed_repository()

    def expand_package(dep):
        tag = entropy.dep.dep_gettag(dep)
        if tag is not None:
            # do not override packages already providing a tag
            return dep

        # can dep be resolved as it is?
        pkg_match, pkg_repo = entropy_client.atom_match(dep)
        if pkg_repo == 1:
            # no, ignoring
            return dep

        pkg_ids, rc = inst_repo.atomMatch(dep, multiMatch = True)
        if rc != 0:
            # not doing anything then
            return dep

        tags = set()
        for pkg_id in pkg_ids:
            pkg_tag = inst_repo.retrieveTag(pkg_id)
            if not pkg_tag:
                # at least one not tagged, abort
                return dep
            tags.add(pkg_tag)

        best_tag = entropy.dep.sort_entropy_package_tags(
            tags)[-1]

        proposed_dep = "%s%s%s" % (dep, etpConst['entropytagprefix'], best_tag)
        # make sure this can be resolved == if package is still available
        pkg_match, repo_id = entropy_client.atom_match(proposed_dep)
        if repo_id == 1:
            return dep

        return proposed_dep

    return list(map(expand_package, packages))

def _scan_packages(entropy_client, packages, etp_pkg_files):

    found_pkg_atoms = []

    # expand package
    packages = entropy_client.packages_expand(packages)

    for package in _scan_packages_expand_tag(entropy_client, packages):
        # clear masking reasons
        match = entropy_client.atom_match(package)
        if match[0] != -1:
            if match not in found_pkg_atoms:
                found_pkg_atoms.append(match)
            continue
        _show_masked_pkg_info(entropy_client, package)

    if etp_pkg_files:
        for pkg in etp_pkg_files:
            try:
                atomsfound = entropy_client.add_package_repository(pkg)
            except EntropyPackageException as err:
                mytxt = "%s: %s %s. %s ..." % (
                    purple(_("Warning")),
                    teal(const_convert_to_unicode(os.path.basename(pkg))),
                    repr(err),
                    teal(_("Skipped")),
                )
                print_warning(mytxt)
                continue
            found_pkg_atoms += atomsfound[:]

    return found_pkg_atoms

def _show_package_removal_info(entropy_client, package_identifiers, manual = False):

    if manual:
        print_info(red(" @@ ") + \
            blue("%s:" % (_("These are the packages that should be MANUALLY removed"),) ))
    else:
        print_info(red(" @@ ") + \
            blue("%s:" % (_("These are the packages that would be removed"),) ))
    totalatoms = str(len(package_identifiers))

    atomscounter = 0
    for idpackage in package_identifiers:

        atomscounter += 1
        rematom = entropy_client.installed_repository().retrieveAtom(idpackage)
        if not rematom:
            continue

        installedfrom = \
            entropy_client.installed_repository().getInstalledPackageRepository(
                idpackage)
        if installedfrom is None:
            installedfrom = _("Not available")

        on_disk_size = entropy_client.installed_repository().retrieveOnDiskSize(
            idpackage)
        pkg_size = entropy_client.installed_repository().retrieveSize(idpackage)
        disksize = entropy.tools.bytes_into_human(on_disk_size)
        repositoryInfo = bold("[") + brown(installedfrom) \
            + bold("]")
        stratomscounter = str(atomscounter)

        while len(stratomscounter) < len(totalatoms):
            stratomscounter = " "+stratomscounter
        disksizeinfo = bold(" [")+brown(str(disksize))+bold("]")
        print_info(darkred(" ## ")+repositoryInfo+" " + \
            enlightenatom(rematom)+disksizeinfo)

def _show_package_info(entropy_client, found_pkg_atoms, deps, action_name = None):

    if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']):
        # now print the selected packages
        print_info(red(" @@ ")+blue("%s:" % (_("These are the chosen packages"),) ))
        totalatoms = len(found_pkg_atoms)
        atomscounter = 0
        for idpackage, reponame in found_pkg_atoms:
            atomscounter += 1
            # open database
            dbconn = entropy_client.open_repository(reponame)

            # get needed info
            pkgatom = dbconn.retrieveAtom(idpackage)
            if not pkgatom:
                continue

            pkgver = dbconn.retrieveVersion(idpackage)
            pkgtag = dbconn.retrieveTag(idpackage)
            if not pkgtag:
                pkgtag = "NoTag"
            pkgrev = dbconn.retrieveRevision(idpackage)
            pkgslot = dbconn.retrieveSlot(idpackage)

            # client info
            installedVer = _("Not installed")
            installedTag = "NoTag"
            installedRev = "NoRev"
            installedRepo = _("Not available")
            pkginstalled = entropy_client.installed_repository().atomMatch(
                entropy.dep.dep_getkey(pkgatom), matchSlot = pkgslot)
            if (pkginstalled[1] == 0):
                # found
                idx = pkginstalled[0]
                installedVer = entropy_client.installed_repository().retrieveVersion(idx)
                installedTag = entropy_client.installed_repository().retrieveTag(idx)
                installedRepo = entropy_client.installed_repository().getInstalledPackageRepository(idx)
                if installedRepo is None:
                    installedRepo = _("Not available")
                if not installedTag:
                    installedTag = "NoTag"
                installedRev = entropy_client.installed_repository().retrieveRevision(idx)

            mytxt = "   # %s%s/%s%s [%s] %s" % (
                red("("),
                bold(str(atomscounter)),
                blue(str(totalatoms)),
                red(")"),
                red(reponame),
                bold(pkgatom),
            )
            print_info(mytxt)
            mytxt = "    %s: %s / %s / %s %s %s / %s / %s" % (
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

            pkgcmp = entropy_client.get_package_action((idpackage, reponame))
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
                rc = entropy_client.ask_question("     %s" % (
                    _("Would you like to continue with dependencies calculation ?"),) )
            else:
                rc = entropy_client.ask_question("     %s" % (
                    _("Would you like to continue ?"),) )
            if rc == _("No"):
                return True, (126, -1)

    return False, (0, 0)

def _show_you_meant(entropy_client, package, from_installed):
    items = entropy_client.get_meant_packages(package,
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
            dbconn = entropy_client.installed_repository()
            idpackage = match[0]
        else:
            dbconn = entropy_client.open_repository(match[1])
            idpackage = match[0]
        key, slot = dbconn.retrieveKeySlot(idpackage)
        if (key, slot) not in items_cache:
            print_info(red("    # ")+blue(key)+":" + \
                brown(str(slot))+red(" ?"))
        items_cache.add((key, slot))

def _generate_run_queue(entropy_client, found_pkg_atoms, deps, emptydeps,
    deepdeps, relaxeddeps, builddeps, recursive):

    run_queue = []
    removal_queue = []

    if deps:
        print_info(red(" @@ ")+blue("%s ...") % (
            _("Calculating dependencies"),) )
        run_queue, removal_queue, status = entropy_client.get_install_queue(
            found_pkg_atoms, emptydeps, deepdeps, relaxed = relaxeddeps,
            build = builddeps, recursive = recursive)
        if status == -2:
            # dependencies not found
            print_error(red(" @@ ") + blue("%s: " % (
                _("Cannot find needed dependencies"),) ))
            for package in run_queue:
                _show_masked_pkg_info(entropy_client, package,
                    from_user = False)
            return True, (125, -1), []
        elif status == -3:
            # colliding dependencies
            print_error(red(" @@ ") + blue("%s: " % (
                _("Conflicting packages were pulled in"),) ))
            # run_queue is a list of sets
            print_warning("")
            for pkg_matches in run_queue:
                for pkg_id, pkg_repo in pkg_matches:
                    repo_db = entropy_client.open_repository(pkg_repo)
                    print_warning(
                        "%s %s" % (brown("  # "),
                            teal(repo_db.retrieveAtom(pkg_id)),))
                print_warning("")
            print_error("%s %s: %s" % (red(" @@ "),
                purple(_("Please mask conflicts using")),
                bold("equo mask <package>"),))
            return True, (125, -1), []

    else:
        for atomInfo in found_pkg_atoms:
            run_queue.append(atomInfo)

    return False, run_queue, removal_queue

def _download_sources(entropy_client, packages = None, deps = True,
    deepdeps = False, pkgs = None, savecwd = False, relaxed_deps = False,
    build_deps = False, recursive = True):

    if packages is None:
        packages = []
    if pkgs is None:
        pkgs = []

    found_pkg_atoms = _scan_packages(entropy_client, packages, pkgs)
    # are there packages in found_pkg_atoms?
    if not found_pkg_atoms:
        print_error( red("%s." % (_("No packages found"),) ))
        return 125, -1

    action = darkgreen(_("Source code download"))
    abort, myrc = _show_package_info(entropy_client, found_pkg_atoms, deps,
        action_name = action)
    if abort:
        return myrc

    abort, run_queue, removal_queue = _generate_run_queue(entropy_client,
        found_pkg_atoms, deps, False, deepdeps, relaxed_deps, build_deps,
        recursive)
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

        Package = entropy_client.Package()

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

def _fetch_packages(entropy_client, run_queue, downdata, multifetch = 1,
    dochecksum = True):

    totalqueue = str(len(run_queue))
    fetchqueue = 0

    sys_set_client_plg_id = \
        etpConst['system_settings_plugins_ids']['client_plugin']
    equo_client_settings = entropy_client.Settings()[sys_set_client_plg_id]['misc']

    if multifetch <= 1:
        multifetch = equo_client_settings.get('multifetch', 1)

    mymultifetch = multifetch
    if multifetch > 1:
        myqueue = []
        mystart = 0
        while True:
            mylist = run_queue[mystart:mymultifetch]
            if not mylist:
                break
            myqueue.append(mylist)
            mystart += multifetch
            mymultifetch += multifetch
        mytotalqueue = str(len(myqueue))

        for matches in myqueue:
            fetchqueue += 1

            metaopts = {}
            metaopts['dochecksum'] = dochecksum
            Package = entropy_client.Package()
            Package.prepare(matches, "multi_fetch", metaopts)
            myrepo_data = Package.pkgmeta['repository_atoms']
            for myrepo in myrepo_data:
                if myrepo not in downdata:
                    downdata[myrepo] = set()
                for myatom in myrepo_data[myrepo]:
                    downdata[myrepo].add(entropy.dep.dep_getkey(myatom))

            xterm_header = "equo ("+_("fetch")+") :: "+str(fetchqueue)+" of "+mytotalqueue+" ::"
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
        Package = entropy_client.Package()
        Package.prepare(match, "fetch", metaopts)
        myrepo = Package.pkgmeta['repository']
        if myrepo not in downdata:
            downdata[myrepo] = set()
        downdata[myrepo].add(entropy.dep.dep_getkey(Package.pkgmeta['atom']))

        xterm_header = "equo ("+_("fetch")+") :: "+str(fetchqueue)+" of "+totalqueue+" ::"
        print_info(red(" :: ")+bold("(")+blue(str(fetchqueue))+"/"+ \
                        red(totalqueue)+bold(") ")+">>> "+darkgreen(Package.pkgmeta['atom']))

        rc = Package.run(xterm_header = xterm_header)
        if rc != 0:
            return -1, rc
        Package.kill()
        del metaopts
        del Package

    return 0, 0


def _download_packages(entropy_client, packages = None, deps = True,
    deepdeps = False, multifetch = 1, dochecksum = True, relaxed_deps = False,
    build_deps = False, recursive = True):

    if packages is None:
        packages = []

    # check if I am root
    if not entropy.tools.is_root():
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True
        etpUi['ask'] = False


    found_pkg_atoms = _scan_packages(entropy_client, packages, None)

    # are there packages in found_pkg_atoms?
    if not found_pkg_atoms:
        print_error( red("%s." % (_("No packages found"),) ))
        return 125, -1

    action = brown(_("Download"))
    abort, myrc = _show_package_info(entropy_client, found_pkg_atoms, deps,
        action_name = action)
    if abort:
        return myrc

    abort, run_queue, removal_queue = _generate_run_queue(entropy_client,
        found_pkg_atoms, deps, False, deepdeps, relaxed_deps, build_deps,
        recursive)
    if abort:
        return run_queue

    if etpUi['pretend']:
        print_info(red(" @@ ")+blue("%s." % (_("All done"),) ))
        return 0, 0

    downdata = {}
    func_rc, fetch_rc = _fetch_packages(entropy_client, run_queue, downdata,
        multifetch, dochecksum)
    if func_rc == 0:
        _spawn_ugc(entropy_client, downdata)
    return func_rc, fetch_rc

def _spawn_ugc(entropy_client, mykeys):
    if entropy_client.UGC is None:
        return
    for myrepo in mykeys:
        mypkgkeys = sorted(mykeys[myrepo])
        try:
            entropy_client.UGC.add_download_stats(myrepo, mypkgkeys)
        except:
            pass

def install_packages(entropy_client,
    packages = None, atomsdata = None, deps = True,
    emptydeps = False, onlyfetch = False, deepdeps = False,
    config_files = False, pkgs = None, resume = False, skipfirst = False,
    dochecksum = True, multifetch = 1, check_critical_updates = False,
    relaxed_deps = False, build_deps = False, recursive = True):

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
        etpUi['ask'] = False

    explicit_user_packages = set()

    sys_set_client_plg_id = \
        etpConst['system_settings_plugins_ids']['client_plugin']
    equo_client_settings = entropy_client.Settings()[sys_set_client_plg_id]['misc']

    if check_critical_updates and equo_client_settings.get('forcedupdates'):
        crit_atoms, crit_matches = entropy_client.calculate_critical_updates()
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
            found_pkg_atoms = _scan_packages(entropy_client, packages, pkgs)
            explicit_user_packages |= set(found_pkg_atoms)

        # are there packages in found_pkg_atoms?
        if (not found_pkg_atoms):
            print_error( red("%s." % (_("No packages found"),) ))
            return 125, -1

        abort, myrc = _show_package_info(entropy_client, found_pkg_atoms, deps)
        if abort:
            return myrc

        abort, run_queue, removal_queue = _generate_run_queue(entropy_client,
            found_pkg_atoms, deps, emptydeps, deepdeps, relaxed_deps,
            build_deps, recursive)
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

                dbconn = entropy_client.open_repository(reponame)
                pkgatom = dbconn.retrieveAtom(idpackage)
                if not pkgatom:
                    continue
                pkgver = dbconn.retrieveVersion(idpackage)
                pkgtag = dbconn.retrieveTag(idpackage)
                pkgrev = dbconn.retrieveRevision(idpackage)
                pkgslot = dbconn.retrieveSlot(idpackage)
                pkgfile = dbconn.retrieveDownloadURL(idpackage)
                onDiskUsedSize += dbconn.retrieveOnDiskSize(idpackage)

                pkgsize = dbconn.retrieveSize(idpackage)
                unpackSize += int(pkgsize)*2

                fetch_path = ClientPkg.get_standard_fetch_disk_path(pkgfile)
                if not os.path.exists(fetch_path):
                    downloadSize += int(pkgsize)
                else:
                    try:
                        f_size = entropy.tools.get_file_size(fetch_path)
                    except OSError:
                        f_size = 0
                    downloadSize += pkgsize - f_size

                # get installed package data
                installedVer = '-1'
                installedTag = ''
                installedRev = 0
                installedRepo = None
                pkginstalled = entropy_client.installed_repository().atomMatch(
                    entropy.dep.dep_getkey(pkgatom), matchSlot = pkgslot)
                if pkginstalled[1] == 0:
                    # found an installed package
                    idx = pkginstalled[0]
                    installedVer = entropy_client.installed_repository().retrieveVersion(idx)
                    installedTag = entropy_client.installed_repository().retrieveTag(idx)
                    installedRev = entropy_client.installed_repository().retrieveRevision(idx)
                    installedRepo = entropy_client.installed_repository().getInstalledPackageRepository(idx)
                    if installedRepo is None:
                        installedRepo = _("Not available")
                    onDiskFreedSize += entropy_client.installed_repository().retrieveOnDiskSize(idx)

                if etpUi['quiet']:
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
                pkgcmp = entropy_client.get_package_action((idpackage, reponame))
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
        if unpackSize > 0:
            neededSize += unpackSize

        if removal_queue:

            if (etpUi['ask'] or etpUi['pretend'] or etpUi['verbose']) and removal_queue:
                mytxt = "%s (%s):" % (
                    blue(_("These are the packages that would be removed")),
                    bold(_("conflicting/substituted")),
                )
                print_info(red(" @@ ")+mytxt)

                for idpackage in removal_queue:
                    pkgatom = entropy_client.installed_repository().retrieveAtom(idpackage)
                    if not pkgatom:
                        continue
                    onDiskFreedSize += entropy_client.installed_repository().retrieveOnDiskSize(idpackage)
                    installedfrom = entropy_client.installed_repository().getInstalledPackageRepository(idpackage)
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
            target_dir = etpConst['entropyunpackdir']
            while not os.path.isdir(target_dir):
                target_dir = os.path.dirname(target_dir)
            size_match = entropy.tools.check_required_space(target_dir,
                neededSize)
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
            rc = entropy_client.ask_question("     %s" % (_("Would you like to execute the queue ?"),) )
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
                resume_cache['recursive'] = recursive
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
                recursive = resume_cache['recursive']
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
                run_queue, x, status = entropy_client.get_install_queue(run_queue[1:],
                    emptydeps, deepdeps, relaxed = relaxed_deps,
                    build = build_deps)
                if status != 0:
                    # wtf! do not save anything
                    print_error(red("%s." % (_("Resume cache no longer valid"),) ))
                    return 128, -1
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

    licenses = {}
    if not os.getenv("ETP_NONINTERACTIVE"):
        ### Before even starting the fetch, make sure that the user accepts their licenses
        licenses = entropy_client.get_licenses_to_accept(run_queue)
        # is there ACCEPT_LICENSE in ENV?
        myaccept_license = os.getenv("ACCEPT_LICENSE")
        if myaccept_license:
            myaccept_license = myaccept_license.split()
            for mylic in myaccept_license:
                if mylic in licenses:
                    licenses.pop(mylic)

    def get_text_license(license_name, repoid):
        dbconn = entropy_client.open_repository(repoid)
        text = dbconn.retrieveLicenseText(license_name)
        tmp_fd, tmp_path = tempfile.mkstemp()
        tmp_f = os.fdopen(tmp_fd, "w")
        tmp_f.write(text)
        tmp_f.flush()
        tmp_f.close()
        return tmp_path

    if licenses:
        print_info(red(" @@ ")+blue("%s:" % (_("You need to accept the licenses below"),) ))
        keys = sorted(licenses.keys())
        for key in keys:
            print_info(red("    :: %s: " % (_("License"),) )+bold(key)+red(", %s:" % (_("needed by"),) ))
            for match in licenses[key]:
                dbconn = entropy_client.open_repository(match[1])
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
                    filename = get_text_license(key, match[1])
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
                    entropy_client.installed_repository().acceptLicense(key)
                    break

    if not etpUi['clean'] or onlyfetch:
        mykeys = {}
        # Before starting the real install, fetch packages and verify checksum.
        func_rc, fetch_rc = _fetch_packages(entropy_client, run_queue, mykeys,
            multifetch, dochecksum)
        if func_rc != 0:
            print_info(red(" @@ ")+blue("%s." % (_("Download incomplete"),) ))
            return func_rc, fetch_rc
        _spawn_ugc(entropy_client, mykeys)

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

        Package = entropy_client.Package()
        Package.prepare(match, "install", metaopts)

        xterm_header = "equo ("+_("install")+") :: "+str(currentqueue)+" of "+totalqueue+" ::"
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

def _mask_unmask_packages(entropy_client, packages, action):

    # check if I am root
    if not entropy.tools.is_root():
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True
        etpUi['ask'] = False

    found_pkg_atoms = []
    for package in packages:
        idpackage, repoid = entropy_client.atom_match(package,
            mask_filter = False)
        if idpackage == -1:
            mytxt = "!!! %s: %s %s." % (
                purple(_("Warning")),
                teal(const_convert_to_unicode(package)),
                purple(_("is not available")),
            )
            print_warning("!!!")
            print_warning(mytxt)
            print_warning("!!!")
            if len(package) > 3:
                _show_you_meant(entropy_client, package, from_installed = False)
                print_warning("!!!")
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
        matches, rc = entropy_client.atom_match(
            package, multi_match = True, multi_repo = True,
                mask_filter = False)
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
                dbconn = entropy_client.open_repository(repoid)
                pkgatom = dbconn.retrieveAtom(idpackage)
                print_info("    -> "+enlightenatom(pkgatom))

    if etpUi['pretend']:
        return 0, 0

    if etpUi['ask']:
        answer = entropy_client.ask_question(_("Would you like to continue?"))
        if answer == _("No"):
            return 0, 0

    for package, matches in match_data.items():
        for match in matches:
            # effectively do action
            if action == "mask":
                done = entropy_client.mask_package_generic(match, package)
            else:
                done = entropy_client.unmask_package_generic(match, package)
            if not done:
                mytxt = "!!! %s: %s %s." % (
                    purple(_("Warning")),
                    teal(const_convert_to_unicode(package)),
                    purple(_("action not executed")),
                )
                print_warning("!!!")
                print_warning(mytxt)
                print_warning("!!!")

    print_info("Have a nice day.")

    return 0, 0

def _configure_packages(entropy_client, packages):

    # check if I am root
    if not entropy.tools.is_root():
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True
        etpUi['ask'] = False

    found_pkg_atoms = []
    packages = entropy_client.packages_expand(packages)

    for package in packages:
        idpackage, result = entropy_client.installed_repository().atomMatch(package)
        if idpackage == -1:
            mytxt = "!!! %s: %s %s." % (
                purple(_("Warning")),
                teal(const_convert_to_unicode(package)),
                purple(_("is not installed")),
            )
            print_warning("!!!")
            print_warning(mytxt)
            print_warning("!!!")
            warning_shown = True
            if len(package) > 3:
                _show_you_meant(entropy_client, package, True)
                print_warning("!!!")
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
        pkgatom = entropy_client.installed_repository().retrieveAtom(idpackage)
        if not pkgatom:
            continue

        installedfrom = entropy_client.installed_repository().getInstalledPackageRepository(
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
        rc = entropy_client.ask_question(question = "     %s" % (
            _("Would you like to configure them now ?"),))
        if rc == _("No"):
            return 0, 0

    if etpUi['pretend']:
        return 0, 0

    totalqueue = str(len(found_pkg_atoms))
    currentqueue = 0
    for idpackage in found_pkg_atoms:
        currentqueue += 1
        xterm_header = "equo (%s) :: " % (_("configure"),) + \
            str(currentqueue) + " of " + totalqueue + " ::"
        Package = entropy_client.Package()
        Package.prepare((idpackage,), "config")
        rc = Package.run(xterm_header = xterm_header)
        if rc not in (0, 3,):
            return -1, rc
        Package.kill()

    return 0, 0

def remove_packages(entropy_client, packages = None, atomsdata = None,
    deps = True, deep = False, system_packages_check = True,
    remove_config_files = False, resume = False, recursive = True,
    empty = False):

    if packages is None:
        packages = []
    if atomsdata is None:
        atomsdata = []

    if not entropy.tools.is_root():
        mytxt = "%s %s %s" % (_("Running with"), bold("--pretend"), red("..."),)
        print_warning(mytxt)
        etpUi['pretend'] = True
        etpUi['ask'] = False

    installed_repo = entropy_client.installed_repository()

    if not resume:

        found_pkg_atoms = []
        if atomsdata:
            for idpackage in atomsdata:
                if not installed_repo.isPackageIdAvailable(idpackage):
                    continue
                found_pkg_atoms.append(idpackage)
        else:

            # expand package
            packages = entropy_client.packages_expand(packages)

            for package in packages:
                idpackage, result = installed_repo.atomMatch(package)
                if idpackage == -1:
                    mytxt = "!!! %s: %s %s." % (
                        purple(_("Warning")),
                        teal(const_convert_to_unicode(package)),
                        purple(_("is not installed")),
                    )
                    print_warning("!!!")
                    print_warning(mytxt)
                    print_warning("!!!")
                    if len(package) > 3:
                        _show_you_meant(entropy_client, package, True)
                        print_warning("!!!")
                    continue
                found_pkg_atoms.append(idpackage)

        if not found_pkg_atoms:
            print_error(red("%s." % (_("No packages found"),) ))
            return 125, -1

        plain_removal_queue = []
        look_for_orphaned_packages = True

        # now print the selected packages
        print_info(red(" @@ ")+blue("%s:" % (
            _("These are the chosen packages"),) ))
        totalatoms = len(found_pkg_atoms)
        atomscounter = 0
        for idpackage in found_pkg_atoms:
            atomscounter += 1

            # get needed info
            pkgatom = installed_repo.retrieveAtom(idpackage)
            if not pkgatom:
                continue

            if system_packages_check:
                valid = entropy_client.validate_package_removal(idpackage)
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

            installedfrom = installed_repo.getInstalledPackageRepository(
                idpackage)
            if installedfrom is None:
                installedfrom = _("Not available")
            on_disk_size = installed_repo.retrieveOnDiskSize(idpackage)
            pkg_size = installed_repo.retrieveSize(idpackage)
            disksize = entropy.tools.bytes_into_human(on_disk_size)
            disksizeinfo = " [%s]" % (bold(str(disksize)),)

            print_info("   # " + red("(") + brown(str(atomscounter)) + "/" + \
                blue(str(totalatoms)) + red(")") + \
                " [%s] " % (brown(installedfrom),) + \
                enlightenatom(pkgatom) + disksizeinfo)

        if etpUi['verbose'] or etpUi['ask'] or etpUi['pretend']:
            print_info(red(" @@ ") + \
                blue("%s: " % (_("Packages involved"),) ) + str(totalatoms))

        if not plain_removal_queue:
            print_error(red("%s." % (_("Nothing to do"),) ))
            return 126, -1

        if etpUi['ask'] and not etpUi['pretend']:
            if deps:
                question = "     %s" % (
                    _("Would you like to calculate dependencies ?"),
                )
                rc = entropy_client.ask_question(question)
                if rc == _("No"):
                    return 0, 0
            else:
                question = "     %s" % (
                    _("Would you like to remove them now ?"),)
                look_for_orphaned_packages = False
                rc = entropy_client.ask_question(question)
                if rc == _("No"):
                    return 0, 0

        removal_queue = []

        if look_for_orphaned_packages:
            try:
                removal_queue += entropy_client.get_removal_queue(
                    plain_removal_queue, deep = deep, recursive = recursive,
                    empty = empty, system_packages = system_packages_check)
            except DependenciesNotRemovable as err:
                non_rm_pkg_ids = sorted([x[0] for x in err.value],
                    key = lambda x: \
                    entropy_client.installed_repository().retrieveAtom(x))
                # otherwise we need to deny the request
                print_error("")
                print_error("  %s, %s:" % (
                    purple(_("Ouch!")),
                    brown(_("the following system packages were pulled in")),
                    )
                )
                for pkg_in in non_rm_pkg_ids:
                    pkg_name = entropy_client.installed_repository().retrieveAtom(pkg_in)
                    print_error("    %s %s" % (purple("#"), teal(pkg_name),))
                print_error("")
                return 128, -1

            except OperationalError:
                if entropy.tools.is_root():
                    raise
                # otherwise we need to deny the request
                print_error("%s: %s." % (
                    purple(_("Cannot calculate dependencies")),
                    blue(_("please run equo as superuser")),
                    )
                )
                return 128, -1

        removal_queue += [x for x in plain_removal_queue if x \
            not in removal_queue]
        atomscounter = len(removal_queue)
        _show_package_removal_info(entropy_client, removal_queue)

        mytxt = "%s: %s" % (
            blue(_("Packages needing to be removed")),
            red(str(atomscounter)),
        )
        print_info(red(" @@ ")+mytxt)

        total_removal_size = 0
        total_pkg_size = 0

        for idpackage in set(removal_queue):
            on_disk_size = installed_repo.retrieveOnDiskSize(idpackage)
            pkg_size = installed_repo.retrieveSize(idpackage)
            if on_disk_size is not None:
                total_removal_size += on_disk_size
            if pkg_size is not None:
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

        if etpUi['ask']:
            question = "     %s" % (
                _("Would you like to proceed ?"),)
            rc = entropy_client.ask_question(question)
            if rc == _("No"):
                return 0, 0
        elif deps:
            countdown(
                what = red(" @@ ")+blue("%s " % (_("Starting removal in"),)),
                back = True
            )

        # clear old resume information
        try:
            entropy.dump.dumpobj(EQUO_CACHE_IDS['remove'], {})
            # store resume information
            resume_cache = {}
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
            installed_repo.retrieveAtom(idpackage)
        except TypeError:
            invalid.add(idpackage)
    removal_queue = [x for x in removal_queue if x not in invalid]

    totalqueue = str(len(removal_queue))
    currentqueue = 0

    totalqueue = str(len(removal_queue))
    currentqueue = 0
    for idpackage in removal_queue:
        currentqueue += 1

        metaopts = {}
        metaopts['removeconfig'] = remove_config_files
        Package = entropy_client.Package()
        Package.prepare((idpackage,), "remove", metaopts)
        if 'remove_installed_vanished' not in Package.pkgmeta:

            xterm_header = "equo (%s) :: " % (_("remove"),) + \
                str(currentqueue)+" of " + totalqueue+" ::"
            print_info(red(" -- ")+bold("(")+blue(str(currentqueue))+"/" + \
                red(totalqueue)+bold(") ") + ">>> " + \
                darkgreen(Package.pkgmeta['removeatom']))

            rc = Package.run(xterm_header = xterm_header)
            if rc != 0:
                # generate reverse dependencies metadata now that's done
                # so we have fresh meat when queried with user privs
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

def _unused_packages_test(entropy_client, do_size_sort = False):
    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue("%s ..." % (
            _("Running unused packages test, pay attention, there are false positives"),) ))

    def unused_packages_test():
        inst_repo = entropy_client.installed_repository()
        return [x for x in inst_repo.retrieveUnusedPackageIds() if \
            entropy_client.validate_package_removal(x)]

    data = [(entropy_client.installed_repository().retrieveOnDiskSize(x), x, \
        entropy_client.installed_repository().retrieveAtom(x),) for x in \
            unused_packages_test()]

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

def _dependencies_test(entropy_client):

    print_info(red(" @@ ")+blue("%s ..." % (_("Running dependency test"),) ))
    deps_not_matched = entropy_client.dependencies_test()

    if deps_not_matched:

        crying_atoms = {}
        found_deps = set()
        inst_repo = entropy_client.installed_repository()
        for dep in deps_not_matched:

            riddep = inst_repo.searchDependency(dep)
            if riddep != -1:
                ridpackages = inst_repo.searchPackageIdFromDependencyId(riddep)
                for i in ridpackages:
                    iatom = inst_repo.retrieveAtom(i)
                    if iatom:
                        obj = crying_atoms.setdefault(dep, set())
                        obj.add(iatom)

            match = entropy_client.atom_match(dep)
            if match[0] != -1:
                found_deps.add(dep)
                continue
            else:
                iddep = inst_repo.searchDependency(dep)
                if iddep == -1:
                    continue
                c_idpackages = inst_repo.searchPackageIdFromDependencyId(iddep)
                for c_idpackage in c_idpackages:
                    if not inst_repo.isPackageIdAvailable(c_idpackage):
                        continue
                    key, slot = inst_repo.retrieveKeySlot(c_idpackage)
                    key_slot = "%s%s%s" % (key, etpConst['entropyslotprefix'],
                        slot,)
                    match = entropy_client.atom_match(key, match_slot = slot)

                    cmpstat = 0
                    if match[0] != -1:
                        cmpstat = entropy_client.get_package_action(match)
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
            rc = entropy_client.ask_question("     %s"  % (_("Would you like to install the available packages ?"),) )
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

        install_packages(entropy_client, packages = sorted(found_deps))

    else:
        print_generic("") # make sure to get back

    return 0, 0

def _libraries_test(entropy_client, listfiles = False, dump = False):

    def restore_qstats():
        etpUi['mute'] = mstat
        etpUi['quiet'] = mquiet

    mstat = etpUi['mute']
    mquiet = etpUi['quiet']
    if listfiles:
        etpUi['mute'] = True
        etpUi['quiet'] = True

    QA = entropy_client.QA()
    pkgs_matched, brokenlibs, status = QA.test_shared_objects(
        entropy_client.installed_repository(), dump_results_to_file = dump)
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

    if pkgs_matched:

        # filter out reinstalls
        def _reinstall_filter(_match):
            _action = entropy_client.get_package_action(_match)
            if _action == 0:
                # maybe notify this to user in future?
                return False
            return True

        for mylib in list(pkgs_matched.keys()):
            pkgs_matched[mylib] = list(filter(_reinstall_filter,
                pkgs_matched[mylib]))
            if not pkgs_matched[mylib]:
                pkgs_matched.pop(mylib)

    atomsdata = set()
    if not etpUi['quiet']:
        print_info(darkgreen(" @@ ")+purple("%s:" % (_("Libraries/Executables statistics"),) ))
        if brokenlibs:
            print_info(brown(" ## ")+teal("%s:" % (_("Not matched"),) ))
            brokenlibs = sorted(brokenlibs)
            for lib in brokenlibs:
                print_info(purple("    => ")+brown(lib))

        if pkgs_matched:

            print_info(brown(" ## ")+teal("%s:" % (_("Matched"),) ))
            for mylib in pkgs_matched:
                for idpackage, repoid in pkgs_matched[mylib]:
                    dbconn = entropy_client.open_repository(repoid)
                    myatom = dbconn.retrieveAtom(idpackage)
                    atomsdata.add((idpackage, repoid))
                    print_info("   "+darkgreen(mylib)+" => "+teal(myatom)+" ["+purple(repoid)+"]")
    else:

        for mylib in pkgs_matched:
            for idpackage, repoid in pkgs_matched[mylib]:
                dbconn = entropy_client.open_repository(repoid)
                myatom = dbconn.retrieveAtom(idpackage)
                atomsdata.add((idpackage, repoid))
                print(myatom)
        restore_qstats()
        return 0, atomsdata

    if etpUi['pretend']:
        restore_qstats()
        return 0, atomsdata

    if atomsdata:
        if etpUi['ask']:
            rc = entropy_client.ask_question("     %s" % (_("Would you like to install them ?"),) )
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

        rc = install_packages(entropy_client, atomsdata = list(atomsdata))
        if rc[0] == 0:
            restore_qstats()
            return 0, atomsdata
        else:
            restore_qstats()
            return rc[0], atomsdata

    restore_qstats()
    return 0, atomsdata
