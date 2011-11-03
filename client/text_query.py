# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
import os
from entropy.const import etpUi, const_convert_to_unicode, \
    const_convert_to_rawstring, const_convert_to_unicode, etpConst
from entropy.output import darkgreen, darkred, red, blue, \
    brown, purple, bold, print_info, print_error, print_generic, \
    print_warning, teal
from entropy.exceptions import DependenciesNotRemovable
from entropy.misc import Lifo
from entropy.i18n import _
from entropy.cli import show_dependencies_legend, print_package_info, \
    graph_packages, revgraph_packages
import entropy.dep
import entropy.tools

from entropy.cli import print_table, get_file_mime, enlightenatom

def query(options):

    rc_status = 0

    if not options:
        return -10

    do_deep = False
    multi_match = False
    multi_repo = False
    show_repo = False
    show_desc = False
    complete_graph = False
    match_installed = False

    myopts = []
    first_opt = None
    for opt in options:
        try:
            opt = const_convert_to_unicode(opt, 'utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError,):
            print_error(red(" %s." % (_("Malformed command"),) ))
            return -10
        if first_opt is None:
            first_opt = opt

        if opt == "--deep":
            do_deep = True
        elif (opt == "--multimatch") and (first_opt == "match"):
            multi_match = True
        elif (opt == "--multirepo") and (first_opt == "match"):
            multi_repo = True
        elif (opt == "--installed") and (first_opt in ("match", "mimetype",
            "associate",)):
            match_installed = True
        elif (opt == "--showrepo") and (first_opt == "match"):
            show_repo = True
        elif (opt == "--showdesc") and (first_opt == "match"):
            show_desc = True
        elif (opt == "--complete") and (first_opt in ("graph","revgraph")):
            complete_graph = True
        else:
            myopts.append(opt)

    if not myopts:
        return -10

    cmd, args = myopts[0], myopts[1:]

    etp_client = None
    try:
        from entropy.client.interfaces import Client
        etp_client = Client()
        if cmd == "match":
            rc_status = match_package(args, etp_client,
                multi_match = multi_match,
                multi_repo = multi_repo,
                show_repo = show_repo,
                show_desc = show_desc,
                installed = match_installed)

        elif cmd == "search":
            rc_status = search_package(args, etp_client)

        elif cmd == "graph":
            rc_status = graph_packages(args, etp_client,
                complete = complete_graph, quiet = etpUi['quiet'])

        elif cmd == "revgraph":
            rc_status = revgraph_packages(args, etp_client,
                complete = complete_graph, quiet = etpUi['quiet'])

        elif cmd == "installed":
            rc_status = search_repository_packages(args, etp_client,
                etp_client.installed_repository())

        elif cmd == "belongs":
            rc_status = search_belongs(args, etp_client,
                etp_client.installed_repository(), quiet=etpUi['quiet'],
                                       verbose=etpUi['verbose'])

        elif cmd == "changelog":
            rc_status = search_changelog(args, etp_client,
                etp_client.installed_repository())

        elif cmd == "revdeps":
            rc_status = search_reverse_dependencies(args, etp_client,
                etp_client.installed_repository())

        elif cmd == "files":
            rc_status = search_files(args, etp_client,
                etp_client.installed_repository())

        elif cmd == "needed":
            rc_status = search_needed_libraries(args, etp_client,
                etp_client.installed_repository())

        elif cmd in ("mimetype", "associate"):
            associate = cmd == "associate"
            rc_status = search_mimetype(args, etp_client,
                installed = match_installed,
                associate = associate)

        elif cmd == "required":
            rc_status = search_required_libraries(args, etp_client,
                etp_client.installed_repository())

        elif cmd == "removal":
            rc_status = search_removal_dependencies(args, etp_client,
                etp_client.installed_repository(), deep = do_deep)

        elif cmd == "tags":
            rc_status = search_tagged_packages(args, etp_client)

        elif cmd == "revisions":
            rc_status = search_rev_packages(args, etp_client)

        elif cmd == "sets":
            rc_status = search_package_sets(args, etp_client)

        elif cmd == "license":
            rc_status = search_licenses(args, etp_client)

        elif cmd == "slot":
            if args:
                rc_status = search_slotted_packages(args, etp_client)
            else:
                rc_status = -10

        elif cmd == "orphans":
            rc_status = search_orphaned_files(etp_client)

        elif cmd == "list":
            mylistopts = options[1:]
            if len(mylistopts) > 0:
                if mylistopts[0] == "installed":

                    def by_user_filter(pkg_match):
                        pkg_id, pkg_repo = pkg_match
                        repo_db = etp_client.open_repository(pkg_repo)
                        source_id = repo_db.getInstalledPackageSource(
                            pkg_id)
                        return source_id == etpConst['install_sources']['user']

                    filter_func = None
                    if "--by-user" in mylistopts:
                        filter_func = by_user_filter

                    rc_status = list_packages(etp_client,
                        etp_client.installed_repository(),
                        filter_func = filter_func)

                elif mylistopts[0] == "available" and len(mylistopts) > 1:
                    repoid = mylistopts[1]
                    if repoid in etp_client.repositories():
                        repo_dbconn = etp_client.open_repository(repoid)
                        rc_status = list_packages(etp_client, repo_dbconn)
                    else:
                        rc_status = -10
                else:
                    rc_status = -10

        elif cmd == "description":
            rc_status = search_description(args, etp_client)

        else:
            rc_status = -10
    finally:
        if etp_client is not None:
            etp_client.shutdown()

    return rc_status

def search_repository_packages(packages, entropy_client, entropy_repository):

    if not etpUi['quiet']:
        print_info(brown(" @@ ")+darkgreen("%s..." % (_("Searching"),) ))

    if entropy_repository is None:
        if not etpUi['quiet']:
            print_warning(purple(" !!! ") + \
                teal(_("Repository is not available")))
        return 127

    if packages:
        pkg_data = {}
        for real_package in packages:
            obj = pkg_data.setdefault(real_package, set())

            slot = entropy.dep.dep_getslot(real_package)
            tag = entropy.dep.dep_gettag(real_package)
            package = entropy.dep.remove_slot(real_package)
            package = entropy.dep.remove_tag(package)

            pkg_ids = entropy_repository.searchPackages(package, slot = slot,
                tag = tag, just_id = True, order_by = "atom")
            obj.update(pkg_ids)
    else:
        pkg_data = dict((atom, (pkg_id,)) for atom, pkg_id, branch in \
            entropy_repository.listAllPackages())

    key_sorter = lambda x: entropy_repository.retrieveAtom(x)
    for package in sorted(pkg_data):
        pkg_ids = pkg_data[package]

        for pkg_id in sorted(pkg_ids, key = key_sorter):
            print_package_info(pkg_id, entropy_client, entropy_repository,
                installed_search = True, extended = etpUi['verbose'],
                quiet = etpUi['quiet'])

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Keyword")),), purple(package)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(pkg_ids), brown(_("entries")),)))
            print_table(toc)

    if (not pkg_data) and (not etpUi['quiet']):
        toc = []
        toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
            0, brown(_("entries")),)))
        print_table(toc)

    return 0

def search_belongs(files, entropy_client, entropy_repository,
                   quiet = False, verbose = False):

    if not quiet:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Belong Search"),)))

    if entropy_repository is None:
        if not quiet:
            print_warning(purple(" !!! ") + \
                teal(_("Repository is not available")))
        return 127

    results = {}
    flatresults = {}
    reverse_symlink_map = entropy_client.Settings()['system_rev_symlinks']
    for xfile in files:
        results[xfile] = set()
        pkg_ids = entropy_repository.searchBelongs(xfile)
        if not pkg_ids:
            # try real path if possible
            pkg_ids = entropy_repository.searchBelongs(os.path.realpath(xfile))
        if not pkg_ids:
            # try using reverse symlink mapping
            for sym_dir in reverse_symlink_map:
                if xfile.startswith(sym_dir):
                    for sym_child in reverse_symlink_map[sym_dir]:
                        my_file = sym_child+xfile[len(sym_dir):]
                        pkg_ids = entropy_repository.searchBelongs(my_file)
                        if pkg_ids:
                            break

        for pkg_id in pkg_ids:
            if not flatresults.get(pkg_id):
                results[xfile].add(pkg_id)
                flatresults[pkg_id] = True

    if results:
        key_sorter = lambda x: entropy_repository.retrieveAtom(x)
        for result in results:

            # print info
            xfile = result
            result = results[result]

            for pkg_id in sorted(result, key = key_sorter):
                if quiet:
                    print_generic(entropy_repository.retrieveAtom(pkg_id))
                else:
                    print_package_info(pkg_id, entropy_client,
                        entropy_repository, installed_search = True,
                        extended = verbose, quiet = quiet)
            if not quiet:
                toc = []
                toc.append(("%s:" % (blue(_("Keyword")),), purple(xfile)))
                toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                    len(result), brown(_("entries")),)))
                print_table(toc)

    return 0

def search_changelog(atoms, entropy_client, entropy_repository):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("ChangeLog Search"),)))

    for atom in atoms:
        repo = entropy_repository
        if entropy_repository is not None:
            pkg_id, rc = entropy_repository.atomMatch(atom)
            if rc != 0:
                print_info(darkred("%s: %s" % (_("No match for"), bold(atom),)))
                continue
        else:
            pkg_id, r_id = entropy_client.atom_match(atom)
            if pkg_id == -1:
                print_info(darkred("%s: %s" % (_("No match for"), bold(atom),)))
                continue
            repo = entropy_client.open_repository(r_id)

        repo_atom = repo.retrieveAtom(pkg_id)
        if etpUi['quiet']:
            print_generic("%s :" % (repo_atom,))
        else:
            print_info(blue(" %s: " % (_("Package"),) ) + bold(repo_atom))

        changelog = repo.retrieveChangelog(pkg_id)
        if not changelog or (changelog == "None"):
            # == "None" is a bug, see:
            # 685b865453d552d37ce3a9559f4cefb9a88f8beb
            print_generic(_("No ChangeLog available"))
        else:
            print_generic(changelog)
        print_generic("="*80)

    if not etpUi['quiet']:
        # check developer repo mode
        repo_conf = entropy_client.Settings().get_setting_files_data(
            )['repositories']
        dev_repo = entropy_client.Settings()['repositories']['developer_repo']
        if not dev_repo:
            print_warning(bold(" !!! ") + \
                brown("%s ! [%s]" % (
                    _("Attention: developer-repo option not enabled"),
                    blue(repo_conf),
                )))

    return 0


def search_reverse_dependencies(atoms, entropy_client, entropy_repository):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Inverse Dependencies Search"),) ))

    include_build_deps = False
    excluded_dep_types = None
    if include_build_deps:
        excluded_dep_types.append(etpConst['dependency_type_ids']['bdepend_id'])

    for atom in atoms:

        result = entropy_repository.atomMatch(atom)
        match_in_repo = False
        repo_masked = False

        if result[0] == -1:
            match_in_repo = True
            result = entropy_client.atom_match(atom)

        if result[0] == -1:
            result = entropy_client.atom_match(atom, mask_filter = False)
            if result[0] != -1:
                repo_masked = True

        if result[0] != -1:

            repo = entropy_repository
            if match_in_repo:
                repo = entropy_client.open_repository(result[1])
            key_sorter = lambda x: repo.retrieveAtom(x)

            found_atom = repo.retrieveAtom(result[0])
            if repo_masked:
                package_id_masked, idmasking_reason = repo.maskFilter(result[0])

            search_results = repo.retrieveReverseDependencies(result[0],
                exclude_deptypes = excluded_dep_types)
            for pkg_id in sorted(search_results, key = key_sorter):
                print_package_info(pkg_id, entropy_client, repo,
                    installed_search = True, strict_output = etpUi['quiet'],
                    extended = etpUi['verbose'], quiet = etpUi['quiet'])

            # print info
            if not etpUi['quiet']:

                masking_reason = ''
                if repo_masked:
                    masking_reason = ", %s" % (
                        entropy_client.Settings()['pkg_masking_reasons'].get(
                            idmasking_reason),
                    )
                mask_str = bold(str(repo_masked)) + masking_reason

                toc = []
                toc.append(("%s:" % (blue(_("Keyword")),), purple(atom)))
                toc.append(("%s:" % (blue(_("Matched")),), teal(found_atom)))
                toc.append(("%s:" % (blue(_("Masked")),), mask_str))

                if match_in_repo:
                    where = "%s %s" % (_("from repository"), result[1],)
                else:
                    where = _("from installed packages database")

                toc.append(("%s:" % (blue(_("Found")),), "%s %s %s" % (
                    len(search_results), brown(_("entries")), where,)))

                print_table(toc)

    return 0

def search_needed_libraries(packages, entropy_client, entropy_repository):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Needed Search"),) ))

    if entropy_repository is None:
        if not etpUi['quiet']:
            print_warning(purple(" !!! ") + \
                teal(_("Repository is not available")))
        return 127

    for package in packages:
        pkg_id, pkg_rc = entropy_repository.atomMatch(package)
        if pkg_id == -1:
            continue

        # print info
        myatom = entropy_repository.retrieveAtom(pkg_id)
        myneeded = entropy_repository.retrieveNeeded(pkg_id)
        for needed in myneeded:
            if etpUi['quiet']:
                print_generic(needed)
            else:
                print_info(blue("       # ") + red(str(needed)))
        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Package")),), purple(myatom)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(myneeded), brown(_("libraries")),)))
            print_table(toc)

    return 0

def search_required_libraries(libraries, entropy_client, entropy_repository):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Required Search"),)))

    key_sorter = lambda x: entropy_repository.retrieveAtom(x)

    for library in libraries:
        results = entropy_repository.searchNeeded(library, like = True)
        for pkg_id in sorted(results, key = key_sorter):

            if etpUi['quiet']:
                print_generic(entropy_repository.retrieveAtom(pkg_id))
                continue

            print_package_info(pkg_id, entropy_client, entropy_repository,
                installed_search = True, strict_output = True,
                extended = etpUi['verbose'], quiet = etpUi['quiet'])

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Library")),), purple(library)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(results), brown(_("packages")),)))
            print_table(toc)

    return 0

def search_files(packages, entropy_client, entropy_repository):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("Files Search..."))

    if entropy_repository is None:
        if not etpUi['quiet']:
            print_warning(purple(" !!! ") + \
                teal(_("Repository is not available")))
        return 127

    for package in packages:

        pkg_id, pkg_rc = entropy_repository.atomMatch(package)
        if pkg_id == -1:
            continue

        files = entropy_repository.retrieveContent(pkg_id)
        atom = entropy_repository.retrieveAtom(pkg_id)
        files = sorted(files)
        if etpUi['quiet']:
            for xfile in files:
                print_generic(xfile)
        else:
            for xfile in files:
                print_info(blue(" ### ") + red(xfile))

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Package")),), purple(atom)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(files), brown(_("files")),)))
            print_table(toc)

    return 0

def search_orphaned_files(entropy_client):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Orphans Search"),)))

    sys_set = entropy_client.Settings()
    repo = entropy_client.installed_repository()
    # start to list all files on the system:
    dirs = sys_set['system_dirs']
    file_data = set()

    import re
    reverse_symlink_map = sys_set['system_rev_symlinks']
    system_dirs_mask = [x for x in sys_set['system_dirs_mask'] \
        if entropy.tools.is_valid_path(x)]
    system_dirs_mask_regexp = []
    for mask in sys_set['system_dirs_mask']:
        reg_mask = re.compile(mask)
        system_dirs_mask_regexp.append(reg_mask)

    count = 0
    for xdir in dirs:
        try:
            wd = os.walk(xdir)
        except RuntimeError: # maximum recursion?
            continue
        for currentdir, subdirs, files in wd:
            found_files = set()
            for filename in files:

                filename = os.path.join(currentdir, filename)

                # filter symlinks, broken ones will be reported
                if os.path.islink(filename) and os.path.lexists(filename):
                    continue

                do_cont = False
                for mask in system_dirs_mask:
                    if filename.startswith(mask):
                        do_cont = True
                        break
                if do_cont:
                    continue

                for mask in system_dirs_mask_regexp:
                    if mask.match(filename):
                        do_cont = True
                        break
                if do_cont:
                    continue

                count += 1
                if not etpUi['quiet'] and ((count == 0) or (count % 500 == 0)):
                    count = 0
                    fname = const_convert_to_unicode(filename[:50])
                    print_info(" %s %s: %s" % (
                            red("@@"),
                            blue(_("Analyzing")),
                            fname,
                        ),
                        back = True
                    )
                try:
                    found_files.add(const_convert_to_unicode(filename))
                except (UnicodeDecodeError, UnicodeEncodeError,) as e:
                    if etpUi['quiet']:
                        continue
                    print_generic("!!! error on", filename, "skipping:", repr(e))

            if found_files:
                file_data |= found_files

    totalfiles = len(file_data)

    if not etpUi['quiet']:
        print_info(red(" @@ ") + blue("%s: " % (_("Analyzed directories"),) )+ \
            ' '.join(sys_set['system_dirs']))
        print_info(red(" @@ ") + blue("%s: " % (_("Masked directories"),) ) + \
            ' '.join(sys_set['system_dirs_mask']))
        print_info(red(" @@ ")+blue("%s: " % (
            _("Number of files collected on the filesystem"),) ) + \
            bold(str(totalfiles)))
        print_info(red(" @@ ")+blue("%s..." % (
            _("Now looking into Installed Packages database"),)))


    pkg_ids = repo.listAllPackageIds()
    length = str(len(pkg_ids))
    count = 0

    def gen_cont(pkg_id):
        for path in repo.retrieveContent(pkg_id):
            # reverse sym
            for sym_dir in reverse_symlink_map:
                if path.startswith(sym_dir):
                    for sym_child in reverse_symlink_map[sym_dir]:
                        yield sym_child+path[len(sym_dir):]
            # real path also
            dirname_real = os.path.realpath(os.path.dirname(path))
            yield os.path.join(dirname_real, os.path.basename(path))
            yield path

    for pkg_id in pkg_ids:

        if not etpUi['quiet']:
            count += 1
            atom = repo.retrieveAtom(pkg_id)
            txt = "["+str(count)+"/"+length+"] "
            print_info(red(" @@ ") + blue("%s: " % (
                _("Intersecting with content of the package"),) ) + txt + \
                bold(str(atom)), back = True)

        # remove from file_data
        file_data -= set(gen_cont(pkg_id))

    orpanedfiles = len(file_data)

    fname = "/tmp/entropy-orphans.txt"
    if not etpUi['quiet']:
        print_info(red(" @@ ") + blue("%s: " % (
            _("Intersection completed. Showing statistics"),) ))
        print_info(red(" @@ ") + blue("%s: " % (
            _("Number of total files"),) ) + bold(str(totalfiles)))
        print_info(red(" @@ ") + blue("%s: " % (
            _("Number of matching files"),) ) + \
            bold(str(totalfiles - orpanedfiles)))
        print_info(red(" @@ ") + blue("%s: " % (
            _("Number of orphaned files"),) ) + bold(str(orpanedfiles)))
        print_info(red(" @@ ")+blue("%s: " % (_
            ("Writing file to disk"),)) + bold(fname))

    sizecount = 0
    file_data = list(file_data)
    file_data.sort(reverse = True)

    with open(fname, "wb") as f_out:

        for myfile in file_data:
            myfile = const_convert_to_rawstring(myfile)
            mysize = 0
            try:
                mysize += os.stat(myfile)[6]
            except OSError:
                mysize = 0
            sizecount += mysize

            f_out.write(myfile + const_convert_to_rawstring("\n"))
            if etpUi['quiet']:
                print_generic(myfile)

        f_out.flush()

    humansize = entropy.tools.bytes_into_human(sizecount)
    if not etpUi['quiet']:
        print_info(red(" @@ ") + \
            blue("%s: " % (_("Total wasted space"),) ) + bold(humansize))
    else:
        print_generic(humansize)

    return 0


def search_removal_dependencies(packages, entropy_client, entropy_repository,
    deep = False):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Removal Search"),) ))

    if entropy_repository is None:
        if not etpUi['quiet']:
            print_warning(purple(" !!! ") + \
                teal(_("Repository is not available")))
        return 127

    found_pkg_ids = [entropy_repository.atomMatch(x) for x in packages]
    found_matches = [(x[0], etpConst['clientdbid']) for x \
        in found_pkg_ids if x[1] == 0]

    if not found_matches:
        print_error(red("%s." % (_("No packages found"),) ))
        return 127

    try:
        removal_queue = entropy_client.get_reverse_queue(found_matches,
            deep = deep)
    except DependenciesNotRemovable as err:
        pkg_atoms = sorted([entropy_client.open_repository(x[1]).retrieveAtom(
            x[0]) for x in err.value])
        # otherwise we need to deny the request
        print_error("")
        print_error("  %s, %s:" % (
            purple(_("Ouch!")),
            brown(_("the following system packages were pulled in")),
            )
        )
        for pkg_atom in pkg_atoms:
            print_error("    %s %s" % (purple("#"), teal(pkg_atom),))
        print_error("")
        return 126

    if not removal_queue:
        if not etpUi['quiet']:
            print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))
        return 0

    totalatoms = str(len(removal_queue))
    atomscounter = 0

    for pkg_id, pkg_repo in removal_queue:

        atomscounter += 1
        repo = entropy_client.open_repository(pkg_repo)
        rematom = repo.retrieveAtom(pkg_id)
        if etpUi['quiet']:
            print_generic(rematom)
            continue

        installedfrom = repo.getInstalledPackageRepository(pkg_id)
        if installedfrom is None:
            installedfrom = _("Not available")
        repo_info = bold("[") + red("%s: " % (_("from"),)) + \
            brown(installedfrom)+bold("]")
        stratomscounter = str(atomscounter)
        while len(stratomscounter) < len(totalatoms):
            stratomscounter = " "+stratomscounter
        print_info("   # " + red("(") + bold(stratomscounter) + "/" + \
            blue(str(totalatoms)) + red(")") + repo_info + " " + \
            enlightenatom(rematom))

    if not etpUi['quiet']:
        toc = []
        toc.append(("%s:" % (blue(_("Keywords")),),
            purple(', '.join(packages))))
        toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
            atomscounter, brown(_("entries")),)))
        print_table(toc)

    return 0



def list_packages(entropy_client, entropy_repository, filter_func = None):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Listing Packages"),)))

    if entropy_repository is None:
        if not etpUi['quiet']:
            print_warning(purple(" !!! ") + \
                teal(_("Repository is not available")))
        return 127

    pkg_ids = entropy_repository.listAllPackageIds(order_by = "atom")
    if filter_func is not None:
        pkg_mtc = filter(filter_func, [(x, entropy_repository.repository_id()) \
            for x in pkg_ids])
        pkg_ids = [x[0] for x in pkg_mtc]

    for pkg_id in pkg_ids:
        atom = entropy_repository.retrieveAtom(pkg_id)
        if atom is None:
            continue
        if not etpUi['verbose']:
            atom = entropy.dep.dep_getkey(atom)

        branchinfo = ""
        sizeinfo = ""
        if etpUi['verbose']:
            branch = entropy_repository.retrieveBranch(pkg_id)
            branchinfo = darkgreen(" [")+red(branch)+darkgreen("] ")
            mysize = entropy_repository.retrieveOnDiskSize(pkg_id)
            mysize = entropy.tools.bytes_into_human(mysize)
            sizeinfo = brown(" [")+purple(mysize)+brown("]")

        if not etpUi['quiet']:
            print_info(red("  # ") + blue(str(pkg_id)) + sizeinfo + \
                branchinfo + " " + atom)
        else:
            print_generic(atom)

    if not pkg_ids and not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0


def search_package(packages, entropy_client, get_results = False,
    from_installed = False, ignore_installed = False):

    if not etpUi['quiet'] and not get_results:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Searching"),) ))

    def do_adv_search(dbconn, from_client = False):
        pkg_ids = set()
        for package in packages:
            slot = entropy.dep.dep_getslot(package)
            tag = entropy.dep.dep_gettag(package)
            package = entropy.dep.remove_slot(package)
            package = entropy.dep.remove_tag(package)

            result = set(dbconn.searchPackages(package, slot = slot,
                tag = tag, just_id = True, order_by = "atom"))
            if not result: # look for something else?
                pkg_id, rc = dbconn.atomMatch(package, matchSlot = slot)
                if pkg_id != -1:
                    result = set([pkg_id])
            pkg_ids |= result

        return pkg_ids

    search_data = set()
    found = False
    rc_results = []

    if not from_installed:
        for repo in entropy_client.repositories():

            dbconn = entropy_client.open_repository(repo)
            pkg_ids = do_adv_search(dbconn)
            if pkg_ids:
                found = True
            search_data.update(((x, repo) for x in pkg_ids))

    # try to actually match something in installed packages db
    if not found and (entropy_client.installed_repository() is not None) \
        and not ignore_installed:
        pkg_ids = do_adv_search(entropy_client.installed_repository(),
            from_client = True)
        if pkg_ids:
            found = True
        search_data.update(((x, etpConst['clientdbid']) for x in pkg_ids))

    if get_results:
        return sorted((entropy_client.open_repository(y).retrieveAtom(x) for \
            x, y in search_data))

    key_sorter = lambda x: \
        entropy_client.open_repository(x[1]).retrieveAtom(x[0])
    for pkg_id, pkg_repo in sorted(search_data, key = key_sorter):
        dbconn = entropy_client.open_repository(pkg_repo)
        from_client = pkg_repo == etpConst['clientdbid']
        print_package_info(pkg_id, entropy_client, dbconn,
            extended = etpUi['verbose'], installed_search = from_client,
            quiet = etpUi['quiet'])

    if not etpUi['quiet']:
        toc = []
        toc.append(("%s:" % (blue(_("Keywords")),),
            purple(', '.join(packages))))
        toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
            len(search_data), brown(_("entries")),)))
        print_table(toc)

    return 0

def search_mimetype(mimetypes, entropy_client, installed = False,
    associate = False):

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (
            _("Searching mimetype"),) ), back = True)
    found = False

    for mimetype in mimetypes:

        if associate:
            # consider mimetype a file path
            mimetype = get_file_mime(mimetype)
            if mimetype is None:
                continue

        if not etpUi['quiet']:
            print_info("%s: %s" % (blue("  # "), bold(mimetype),))

        if installed:
            matches = [(x, etpConst['clientdbid']) for x in \
                entropy_client.search_installed_mimetype(mimetype)]
        else:
            matches = entropy_client.search_available_mimetype(mimetype)

        if matches:
            found = True

        key_sorter = lambda x: \
            entropy_client.open_repository(x[1]).retrieveAtom(x[0])
        for pkg_id, pkg_repo in sorted(matches, key = key_sorter):
            repo = entropy_client.open_repository(pkg_repo)
            print_package_info(pkg_id, entropy_client, repo,
                extended = etpUi['verbose'], quiet = etpUi['quiet'])

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Keyword")),), purple(mimetype)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(matches), brown(_("entries")),)))
            print_table(toc)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def match_package(packages, entropy_client, multi_match = False,
    multi_repo = False, show_repo = False, show_desc = False,
    get_results = False, installed = False):

    if not etpUi['quiet'] and not get_results:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Matching"),) ),
            back = True)
    found = False
    rc_results = []

    for package in packages:

        if not etpUi['quiet'] and not get_results:
            print_info("%s: %s" % (blue("  # "), bold(package),))

        if installed:
            inst_pkg_id, inst_rc = entropy_client.installed_repository(
                ).atomMatch(package, multiMatch = multi_match)
            if inst_rc != 0:
                match = (-1, 1)
            else:
                if multi_match:
                    match = ([(x, etpConst['clientdbid']) for x in inst_pkg_id],
                        0)
                else:
                    match = (inst_pkg_id, etpConst['clientdbid'])
        else:
            match = entropy_client.atom_match(package,
                multi_match = multi_match, multi_repo = multi_repo,
                    mask_filter = False)
        if match[1] != 1:

            if not multi_match:
                if multi_repo:
                    matches = match[0]
                else:
                    matches = [match]
            else:
                matches = match[0]

            key_sorter = lambda x: entropy_client.open_repository(x[1]).retrieveAtom(x[0])
            for pkg_id, pkg_repo in sorted(matches, key = key_sorter):
                dbconn = entropy_client.open_repository(pkg_repo)
                if get_results:
                    rc_results.append(dbconn.retrieveAtom(pkg_id))
                else:
                    print_package_info(pkg_id, entropy_client, dbconn,
                        show_repo_if_quiet = show_repo,
                            show_desc_if_quiet = show_desc,
                                extended = etpUi['verbose'],
                                quiet = etpUi['quiet'])
                found = True

            if not etpUi['quiet'] and not get_results:
                toc = []
                toc.append(("%s:" % (blue(_("Keyword")),), purple(package)))
                toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                    len(matches), brown(_("entries")),)))
                print_table(toc)

    if not etpUi['quiet'] and not found and not get_results:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    if get_results:
        return rc_results
    if not found:
        return 1
    return 0

def search_slotted_packages(slots, entropy_client):

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Slot Search"),) ))

    # search inside each available database
    repo_number = 0
    sys_set = entropy_client.Settings()
    for repo_id in entropy_client.repositories():
        repo_number += 1
        repo_data = sys_set['repositories']['available'][repo_id]

        if not etpUi['quiet']:
            print_info(blue("  #"+str(repo_number)) + \
                bold(" " + repo_data['description']))

        repo = entropy_client.open_repository(repo_id)
        for slot in slots:

            results = repo.searchSlotted(slot, just_id = True)
            key_sorter = lambda x: repo.retrieveAtom(x)
            for pkg_id in sorted(results, key = key_sorter):
                found = True
                print_package_info(pkg_id, entropy_client, repo,
                    extended = etpUi['verbose'], strict_output = etpUi['quiet'],
                    quiet = etpUi['quiet'])

            if not etpUi['quiet']:
                toc = []
                toc.append(("%s:" % (blue(_("Keyword")),), purple(slot)))
                toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                    len(results), brown(_("entries")),)))
                print_table(toc)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_package_sets(items, entropy_client):

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (
            _("Package Set Search"),)))

    if not items:
        items.append('*')

    sets = entropy_client.Sets()

    matchNumber = 0
    for item in items:
        results = sets.search(item)
        key_sorter = lambda x: x[1]
        for repo, set_name, set_data in sorted(results, key = key_sorter):
            matchNumber += 1
            found = True
            if not etpUi['quiet']:
                print_info(blue("  #" + str(matchNumber)) + \
                    bold(" " + set_name))
                elements = sorted(set_data)
                for element in elements:
                    print_info(brown("    "+element))
            else:
                for element in sorted(set_data):
                    print_generic(element)

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Keyword")),), purple(item)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                matchNumber, brown(_("entries")),)))
            print_table(toc)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_tagged_packages(tags, entropy_client):

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Tag Search"),)))

    repo_number = 0
    sys_set = entropy_client.Settings()

    for repo_id in entropy_client.repositories():
        repo_number += 1
        repo_data = sys_set['repositories']['available'][repo_id]

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repo_number)) + \
                bold(" " + repo_data['description']))

        repo = entropy_client.open_repository(repo_id)
        key_sorter = lambda x: repo.retrieveAtom(x[1])
        for tag in tags:
            results = repo.searchTaggedPackages(tag, atoms = True)
            found = True
            for result in sorted(results, key = key_sorter):
                print_package_info(result[1], entropy_client, repo,
                    extended = etpUi['verbose'],
                    strict_output = etpUi['quiet'], quiet = etpUi['quiet'])

            if not etpUi['quiet']:
                toc = []
                toc.append(("%s:" % (blue(_("Keyword")),), purple(tag)))
                toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                    len(results), brown(_("entries")),)))
                print_table(toc)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_rev_packages(revisions, entropy_client):

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Revision Search"),)))
        print_info(bold(_("Installed packages repository")))

    repo = entropy_client.installed_repository()
    key_sorter = lambda x: repo.retrieveAtom(x)

    for revision in revisions:
        results = repo.searchRevisionedPackages(revision)
        found = True
        for pkg_id in sorted(results, key = key_sorter):
            print_package_info(pkg_id, entropy_client, repo,
                extended = etpUi['verbose'], strict_output = etpUi['quiet'],
                installed_search = True, quiet = etpUi['quiet'])

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Keyword")),), purple(revision)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(results), brown(_("entries")),)))
            print_table(toc)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_licenses(licenses, entropy_client):

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("License Search"),)))

    # search inside each available database
    repo_number = 0
    sys_set = entropy_client.Settings()
    for repo_id in entropy_client.repositories():
        repo_number += 1
        repo_data = sys_set['repositories']['available'][repo_id]

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repo_number)) + \
                bold(" " + repo_data['description']))

        repo = entropy_client.open_repository(repo_id)
        key_sorter = lambda x: repo.retrieveAtom(x)

        for mylicense in licenses:

            results = repo.searchLicense(mylicense, just_id = True)
            if not results:
                continue
            found = True
            for pkg_id in sorted(results, key = key_sorter):
                print_package_info(pkg_id, entropy_client, repo,
                    extended = etpUi['verbose'],
                    strict_output = etpUi['quiet'], quiet = etpUi['quiet'])

            if not etpUi['quiet']:
                toc = []
                toc.append(("%s:" % (blue(_("Keyword")),), purple(mylicense)))
                toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                    len(results), brown(_("entries")),)))
                print_table(toc)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_description(descriptions, entropy_client):

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Description Search"),) ))

    repo_number = 0
    sys_set = entropy_client.Settings()
    for repo_id in entropy_client.repositories():
        repo_number += 1
        repo_data = sys_set['repositories']['available'][repo_id]

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repo_number)) + \
                bold(" " + repo_data['description']))

        repo = entropy_client.open_repository(repo_id)
        found = search_descriptions(descriptions, entropy_client, repo)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_descriptions(descriptions, entropy_client, entropy_repository):

    key_sorter = lambda x: entropy_repository.retrieveAtom(x)
    found = 0
    for desc in descriptions:

        pkg_ids = entropy_repository.searchDescription(desc, just_id = True)
        if not pkg_ids:
            continue

        found += len(pkg_ids)
        for pkg_id in sorted(pkg_ids, key = key_sorter):
            if etpUi['quiet']:
                print_generic(entropy_repository.retrieveAtom(pkg_id))
            else:
                print_package_info(pkg_id, entropy_client, entropy_repository,
                    extended = etpUi['verbose'], strict_output = False,
                    quiet = False)

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Keyword")),), purple(desc)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(pkg_ids), brown(_("entries")),)))
            print_table(toc)

    return found

