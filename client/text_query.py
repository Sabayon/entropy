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
from entropy.misc import Lifo
from entropy.client.interfaces import Client as EquoInterface
from entropy.i18n import _
import entropy.tools
from entropy.db.exceptions import DatabaseError

from text_tools import print_table, get_file_mime

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
        elif (opt == "--installed") and (first_opt in ("match", "mimetype", "associate",)):
            match_installed = True
        elif (opt == "--showrepo") and (first_opt == "match"):
            show_repo = True
        elif (opt == "--showdesc") and (first_opt == "match"):
            show_desc = True
        elif (opt == "--complete") and (first_opt in ("graph","revgraph")):
            complete_graph = True
        elif opt.startswith("--"):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return -10
        else:
            myopts.append(opt)

    if not myopts:
        return -10

    if myopts[0] == "match":
        rc_status = match_package(myopts[1:],
            multiMatch = multi_match,
            multiRepo = multi_repo,
            showRepo = show_repo,
            showDesc = show_desc,
            installed = match_installed)

    elif myopts[0] == "search":
        rc_status = search_package(myopts[1:])

    elif myopts[0] == "graph":
        rc_status = graph_packages(myopts[1:], complete = complete_graph)

    elif myopts[0] == "revgraph":
        rc_status = revgraph_packages(myopts[1:], complete = complete_graph)

    elif myopts[0] == "installed":
        rc_status = search_installed_packages(myopts[1:])

    elif myopts[0] == "belongs":
        rc_status = search_belongs(myopts[1:])

    elif myopts[0] == "changelog":
        rc_status = search_changelog(myopts[1:])

    elif myopts[0] == "revdeps":
        rc_status = search_reverse_dependencies(myopts[1:])

    elif myopts[0] == "files":
        rc_status = search_files(myopts[1:])

    elif myopts[0] == "needed":
        rc_status = search_needed_libraries(myopts[1:])

    elif myopts[0] in ("mimetype", "associate"):
        associate = myopts[0] == "associate"
        rc_status = search_mimetype(myopts[1:], installed = match_installed,
            associate = associate)

    elif myopts[0] == "required":
        rc_status = search_required_libraries(myopts[1:])

    elif myopts[0] == "removal":
        rc_status = search_removal_dependencies(myopts[1:], deep = do_deep)

    elif myopts[0] == "tags":
        rc_status = search_tagged_packages(myopts[1:])

    elif myopts[0] == "revisions":
        rc_status = search_rev_packages(myopts[1:])

    elif myopts[0] == "sets":
        rc_status = search_package_sets(myopts[1:])

    elif myopts[0] == "license":
        rc_status = search_licenses(myopts[1:])

    elif myopts[0] == "slot":
        if (len(myopts) > 1):
            rc_status = search_slotted_packages(myopts[1:])

    elif myopts[0] == "orphans":
        rc_status = search_orphaned_files()

    elif myopts[0] == "list":
        mylistopts = options[1:]
        if len(mylistopts) > 0:
            if mylistopts[0] == "installed":
                rc_status = list_installed_packages()
            elif mylistopts[0] == "available" and len(mylistopts) > 1:
                repoid = mylistopts[1]
                equo = EquoInterface()
                if repoid in equo.repositories():
                    repo_dbconn = equo.open_repository(repoid)
                    rc_status = list_installed_packages(dbconn = repo_dbconn)
                else:
                    rc_status = -10
            else:
                rc_status = -10

    elif myopts[0] == "description":
        rc_status = search_description(myopts[1:])

    else:
        rc_status = -10

    return rc_status

def get_installed_packages(packages, dbconn = None, entropy_intf = None):

    if entropy_intf is None:
        entropy_intf = EquoInterface()

    repo_db = dbconn
    if not dbconn:
        repo_db = entropy_intf.installed_repository()

    pkg_data = {}
    flat_results = set()
    for real_package in packages:
        pkg_data[real_package] = set()

        slot = entropy.tools.dep_getslot(real_package)
        tag = entropy.tools.dep_gettag(real_package)
        package = entropy.tools.remove_slot(real_package)
        package = entropy.tools.remove_tag(package)

        idpackages = repo_db.searchPackages(package, slot = slot, tag = tag,
            just_id = True)
        pkg_data[real_package].update(idpackages)
        flat_results.update(idpackages)

    return pkg_data, flat_results

def search_installed_packages(packages, dbconn = None, Equo = None):

    if not etpUi['quiet']:
        print_info(brown(" @@ ")+darkgreen("%s..." % (_("Searching"),) ))

    if Equo is None:
        Equo = EquoInterface()
    if dbconn is None:
        dbconn = Equo.installed_repository()

    if not packages:
        packages = [dbconn.retrieveAtom(x) for x in \
            dbconn.listAllPackageIds(order_by = "atom")]

    pkg_data, flat_data = get_installed_packages(packages, dbconn = dbconn,
        entropy_intf = Equo)

    key_sorter = lambda x: dbconn.retrieveAtom(x)
    for package in sorted(pkg_data):
        idpackages = pkg_data[package]

        for idpackage in sorted(idpackages, key = key_sorter):
            print_package_info(idpackage, dbconn, clientSearch = True,
                Equo = Equo, extended = etpUi['verbose'])

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Keyword")),), purple(package)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(idpackages), brown(_("entries")),)))
            print_table(toc)

    return 0

def revgraph_packages(packages, dbconn = None, complete = False):

    if dbconn is None:
        entropy_intf = EquoInterface()
        dbconn = entropy_intf.installed_repository()

    for package in packages:
        pkg_id, pkg_rc = dbconn.atomMatch(package)
        if pkg_rc == 1:
            continue
        if not etpUi['quiet']:
            print_info(brown(" @@ ")+darkgreen("%s %s..." % (
                _("Reverse graphing installed package"), purple(package),) ))

        g_pkg = dbconn.retrieveAtom(pkg_id)
        _revgraph_package(pkg_id, g_pkg, dbconn, show_complete = complete)

    return 0

def _print_graph_item_deps(item, out_data = None, colorize = None):

    if out_data is None:
        out_data = {}

    if "cache" not in out_data:
        out_data['cache'] = set()
    if "lvl" not in out_data:
        out_data['lvl'] = 0
    item_translation_callback = out_data.get('txc_cb')
    show_already_pulled_in = out_data.get('show_already_pulled_in')

    out_val = repr(item.item())
    if item_translation_callback:
        out_val = item_translation_callback(item.item())

    endpoints = set()
    for arch in item.arches():
        if item.is_arch_outgoing(arch):
            endpoints |= arch.endpoints()

    valid_endpoints = [x for x in endpoints if x not in \
        out_data['cache']]
    cached_endpoints = [x for x in endpoints if x in \
        out_data['cache']]

    if colorize is None and not valid_endpoints:
        colorize = darkgreen
    elif colorize is None:
        colorize = purple

    ind_lvl = out_data['lvl']
    indent_txt = '[%s]\t' % (teal(str(ind_lvl)),) + '  ' * ind_lvl
    print_generic(indent_txt + colorize(out_val))
    if cached_endpoints and show_already_pulled_in:
        indent_txt = '[%s]\t' % (teal(str(ind_lvl)),) + '  ' * (ind_lvl + 1)
        for endpoint in sorted(cached_endpoints, key = lambda x: x.item()):
            endpoint_item = item_translation_callback(endpoint.item())
            print_generic(indent_txt + brown(endpoint_item))

    if valid_endpoints:
        out_data['lvl'] += 1
        out_data['cache'].update(valid_endpoints)
        for endpoint in sorted(valid_endpoints, key = lambda x: x.item()):
            _print_graph_item_deps(endpoint, out_data)
        out_data['lvl'] -= 1

def _show_graph_legend():
    print_info("%s:" % (purple(_("Legend")),))

    print_info("[%s] %s" % (blue("x"),
        blue(_("packages passed as arguments")),))

    print_info("[%s] %s" % (darkgreen("x"),
        darkgreen(_("packages with no further dependencies")),))

    print_info("[%s] %s" % (purple("x"),
        purple(_("packages with further dependencies (node)")),))

    print_info("[%s] %s" % (brown("x"),
        brown(_("packages already pulled in as dependency in upper levels (circularity)")),))

    print_generic("="*40)

def _show_dependencies_legend(indent = '', get_data = False):
    data = []
    for dep_id, dep_val in sorted(etpConst['dependency_type_ids'].items(),
        key = lambda x: x[0], reverse = True):

        dep_desc = etpConst['dependency_type_ids_desc'].get(dep_id, _("N/A"))
        txt = '%s%s%s%s %s' % (indent, teal("{"), dep_val, teal("}"), dep_desc,)
        if get_data:
            data.append(txt)
        else:
            print_info(txt)
    if get_data:
        return data

def _revgraph_package(installed_pkg_id, package, dbconn, show_complete = False):

    include_sys_pkgs = False
    show_already_pulled_in = False
    include_build_deps = False
    if show_complete:
        include_sys_pkgs = True
        show_already_pulled_in = True
        include_build_deps = True

    excluded_dep_types = [etpConst['dependency_type_ids']['bdepend_id']]
    if not include_build_deps:
        excluded_dep_types = None

    from entropy.graph import Graph
    from entropy.misc import Lifo
    graph = Graph()
    stack = Lifo()
    inst_item = (installed_pkg_id, package)
    stack.push(inst_item)
    stack_cache = set()
    # ensure package availability in graph, initialize now
    graph.add(inst_item, set())

    rev_pkgs_sorter = lambda x: dbconn.retrieveAtom(x)

    while stack.is_filled():

        item = stack.pop()
        if item in stack_cache:
            continue
        stack_cache.add(item)
        pkg_id, was_dep = item

        rev_deps = dbconn.retrieveReverseDependencies(pkg_id,
            exclude_deptypes = excluded_dep_types)

        graph_deps = []
        for rev_pkg_id in sorted(rev_deps, key = rev_pkgs_sorter):

            dep = dbconn.retrieveAtom(rev_pkg_id)
            do_include = True
            if not include_sys_pkgs:
                do_include = not dbconn.isSystemPackage(rev_pkg_id)

            g_item = (rev_pkg_id, dep)
            if do_include:
                stack.push(g_item)
            graph_deps.append(g_item)

        graph.add(item, graph_deps)

    def item_translation_func(match):
        return match[1]

    _graph_to_stdout(graph, graph.get_node(inst_item),
        item_translation_func, show_already_pulled_in)
    if not etpUi['quiet']:
        _show_graph_legend()

    del stack
    del graph
    return 0

def graph_packages(packages, entropy_intf = None, complete = False):

    if entropy_intf is None:
        entropy_intf = EquoInterface()

    for package in packages:
        match = entropy_intf.atom_match(package)
        if match[0] == -1:
            continue
        if not etpUi['quiet']:
            print_info(brown(" @@ ")+darkgreen("%s %s..." % (
                _("Graphing"), purple(package),) ))

        pkg_id, repo_id = match
        repodb = entropy_intf.open_repository(repo_id)
        g_pkg = repodb.retrieveAtom(pkg_id)
        _graph_package(match, g_pkg, entropy_intf, show_complete = complete)

    return 0

def _graph_package(match, package, entropy_intf, show_complete = False):

    include_sys_pkgs = False
    show_already_pulled_in = False
    if show_complete:
        include_sys_pkgs = True
        show_already_pulled_in = True

    from entropy.graph import Graph
    from entropy.misc import Lifo
    graph = Graph()
    stack = Lifo()
    start_item = (match, package, None)
    stack.push(start_item)
    stack_cache = set()
    # ensure package availability in graph, initialize now
    graph.add(start_item, [])
    depsorter = lambda x: entropy.tools.dep_getcpv(x[0])

    while stack.is_filled():

        item = stack.pop()
        if item in stack_cache:
            continue
        stack_cache.add(item)
        ((pkg_id, repo_id,), was_dep, dep_type) = item

        # deps
        repodb = entropy_intf.open_repository(repo_id)
        deps = repodb.retrieveDependencies(pkg_id, extended = True)

        graph_deps = []
        for dep, x_dep_type in sorted(deps, key = depsorter):

            if dep.startswith("!"): # conflict
                continue

            dep_item = entropy_intf.atom_match(dep)
            if dep_item[0] == -1:
                continue
            do_include = True
            if not include_sys_pkgs:
                dep_repodb = entropy_intf.open_repository(dep_item[1])
                do_include = not dep_repodb.isSystemPackage(dep_item[0])

            g_item = (dep_item, dep, x_dep_type)
            if do_include:
                stack.push(g_item)
            graph_deps.append(g_item)

        graph.add(item, graph_deps)

    def item_translation_func(match):
        value = "%s" % (match[1],)
        if match[2] is not None:
            value += " %s%s%s" % (teal("{"), brown(str(match[2])), teal("}"),)
        return value

    _graph_to_stdout(graph, graph.get_node(start_item),
        item_translation_func, show_already_pulled_in)
    if not etpUi['quiet']:
        _show_graph_legend()
        _show_dependencies_legend()

    del stack
    del graph
    return 0

def _graph_to_stdout(graph, start_item, item_translation_callback,
    show_already_pulled_in):

    if not etpUi['quiet']:
        print_generic("="*40)

    sorted_data = graph.solve_nodes()
    stack = Lifo()
    for dep_level in sorted(sorted_data.keys(), reverse = True):
        stack.push(sorted_data[dep_level])
    # required to make sure that our first pkg is user required one
    stack.push((start_item,))

    out_data = {
        'cache': set(),
        'lvl': 0,
        'txc_cb': item_translation_callback,
        'show_already_pulled_in': show_already_pulled_in,
    }

    first_tree_item = True

    while stack.is_filled():

        stack_items = stack.pop()
        # cleanup already printed items
        items = [x for x in stack_items if x not in out_data['cache']]
        if not items:
            continue
        out_data['cache'].update(stack_items)

        # print items and its deps
        for item in items:
            old_level = out_data['lvl']
            _print_graph_item_deps(item, out_data, colorize = blue)
            out_data['lvl'] = old_level
            if first_tree_item:
                out_data['lvl'] += 1
            first_tree_item = False

    del stack

def search_belongs(files, dbconn = None, Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Belong Search"),)))

    if dbconn is None:
        dbconn = Equo.installed_repository()

    results = {}
    flatresults = {}
    reverse_symlink_map = Equo.Settings()['system_rev_symlinks']
    for xfile in files:
        like = False
        if xfile.find("*") != -1:
            xfile.replace("*", "%")
            like = True
        results[xfile] = set()
        idpackages = dbconn.searchBelongs(xfile, like)
        if not idpackages:
            # try real path if possible
            idpackages = dbconn.searchBelongs(
                os.path.realpath(xfile), like)
        if not idpackages:
            # try using reverse symlink mapping
            for sym_dir in reverse_symlink_map:
                if xfile.startswith(sym_dir):
                    for sym_child in reverse_symlink_map[sym_dir]:
                        my_file = sym_child+xfile[len(sym_dir):]
                        idpackages = dbconn.searchBelongs(my_file, like)
                        if idpackages:
                            break

        for idpackage in idpackages:
            if not flatresults.get(idpackage):
                results[xfile].add(idpackage)
                flatresults[idpackage] = True

    if results:

        key_sorter = lambda x: dbconn.retrieveAtom(x)
        for result in results:

            # print info
            xfile = result
            result = results[result]

            for idpackage in sorted(result, key = key_sorter):
                if etpUi['quiet']:
                    print_generic(dbconn.retrieveAtom(idpackage))
                else:
                    print_package_info(idpackage, dbconn,
                        clientSearch = True, Equo = Equo,
                        extended = etpUi['verbose'])
            if not etpUi['quiet']:
                toc = []
                toc.append(("%s:" % (blue(_("Keyword")),), purple(xfile)))
                toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                    len(result), brown(_("entries")),)))
                print_table(toc)

    return 0

def search_changelog(atoms, dbconn = None, Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("ChangeLog Search"),)))

    for atom in atoms:
        if dbconn != None:
            idpackage, rc = dbconn.atomMatch(atom)
            if rc != 0:
                print_info(darkred("%s: %s" % (_("No match for"), bold(atom),)))
                continue
        else:
            idpackage, r_id = Equo.atom_match(atom)
            if idpackage == -1:
                print_info(darkred("%s: %s" % (_("No match for"), bold(atom),)))
                continue
            dbconn = Equo.open_repository(r_id)

        db_atom = dbconn.retrieveAtom(idpackage)
        if etpUi['quiet']:
            print_generic("%s :" % (db_atom,))
        else:
            print_info(blue(" %s: " % (_("Atom"),) ) + bold(db_atom))

        changelog = dbconn.retrieveChangelog(idpackage)
        if not changelog:
            print_generic(_("No ChangeLog available"))
        else:
            print_generic(changelog)
        print_generic("="*80)

    if not etpUi['quiet']:
        # check developer repo mode
        dev_repo = Equo.Settings()['repositories']['developer_repo']
        if not dev_repo:
            print_warning(bold(" !!! ") + \
                brown("%s ! [%s]" % (
                    _("Attention: developer-repo option not enabled"),
                    blue(etpConst['repositoriesconf']),
                )))

    return 0


def search_reverse_dependencies(atoms, dbconn = None, Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Inverse Dependencies Search"),) ))

    match_repo = True
    if not hasattr(Equo, 'atom_match'):
        match_repo = False

    if dbconn is None:
        dbconn = Equo.installed_repository()

    include_build_deps = False
    excluded_dep_types = None
    if include_build_deps:
        excluded_dep_types.append(etpConst['dependency_type_ids']['bdepend_id'])

    for atom in atoms:

        result = dbconn.atomMatch(atom)
        match_in_repo = False
        repo_masked = False

        if (result[0] == -1) and match_repo:
            match_in_repo = True
            result = Equo.atom_match(atom)

        if (result[0] == -1) and match_repo:
            result = Equo.atom_match(atom, mask_filter = False)
            if result[0] != -1:
                repo_masked = True

        if result[0] != -1:

            mdbconn = dbconn
            if match_in_repo:
                mdbconn = Equo.open_repository(result[1])
            key_sorter = lambda x: mdbconn.retrieveAtom(x)

            found_atom = mdbconn.retrieveAtom(result[0])
            if repo_masked:
                idpackage_masked, idmasking_reason = mdbconn.maskFilter(
                    result[0])

            search_results = mdbconn.retrieveReverseDependencies(result[0],
                exclude_deptypes = excluded_dep_types)
            for idpackage in sorted(search_results, key = key_sorter):
                print_package_info(idpackage, mdbconn, clientSearch = True,
                    strictOutput = etpUi['quiet'], Equo = Equo,
                    extended = etpUi['verbose'])

            # print info
            if not etpUi['quiet']:

                masking_reason = ''
                if repo_masked:
                    masking_reason = ", %s" % (
                        Equo.Settings()['pkg_masking_reasons'].get(
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

def search_needed_libraries(atoms, dbconn = None, Equo = None):

    if Equo is None:
        Equo = EquoInterface()


    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Needed Search"),) ))

    if dbconn is None:
        dbconn = Equo.installed_repository()

    for atom in atoms:
        match = dbconn.atomMatch(atom)
        if match[0] != -1:
            # print info
            myatom = dbconn.retrieveAtom(match[0])
            myneeded = dbconn.retrieveNeeded(match[0])
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

def search_required_libraries(libraries, dbconn = None, Equo = None):

    if Equo is None:
        Equo = EquoInterface()


    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Required Search"),)))

    if dbconn is None:
        dbconn = Equo.installed_repository()
    key_sorter = lambda x: dbconn.retrieveAtom(x)

    for library in libraries:
        results = dbconn.searchNeeded(library, like = True)
        for pkg_id in sorted(results, key = key_sorter):

            if etpUi['quiet']:
                print_generic(dbconn.retrieveAtom(pkg_id))
                continue

            print_package_info(pkg_id, dbconn, clientSearch = True,
                strictOutput = True, Equo = Equo,
                extended = etpUi['verbose'])

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Library")),), purple(library)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(results), brown(_("packages")),)))
            print_table(toc)

    return 0

def search_eclass(eclasses, dbconn = None, Equo = None):

    if Equo is None:
        Equo = EquoInterface()


    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Eclass Search"),)))

    if dbconn is None:
        dbconn = Equo.installed_repository()
    key_sorter = lambda x: dbconn.retrieveAtom(x[1])

    for eclass in eclasses:
        matches = dbconn.searchEclassedPackages(eclass, atoms = True)
        for match in sorted(matches, key = key_sorter):
            # print info
            myatom = match[0]
            idpackage = match[1]
            if etpUi['quiet']:
                print_generic(myatom)
                continue

            print_package_info(idpackage, dbconn, clientSearch = True,
                Equo = Equo, extended = etpUi['verbose'],
                strictOutput = not etpUi['verbose'])

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(matches), brown(_("packages")),)))
            print_table(toc)

    return 0

def search_files(atoms, dbconn = None, Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("Files Search..."))

    if not dbconn:
        dbconn = Equo.installed_repository()
    dict_results, results = get_installed_packages(atoms, dbconn = dbconn,
        entropy_intf = Equo)

    for result in results:
        if result == -1:
            continue

        files = dbconn.retrieveContent(result)
        atom = dbconn.retrieveAtom(result)
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



def search_orphaned_files(Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Orphans Search"),)))

    clientDbconn = Equo.installed_repository()

    # start to list all files on the system:
    dirs = Equo.Settings()['system_dirs']
    file_data = set()

    import re
    reverse_symlink_map = Equo.Settings()['system_rev_symlinks']
    system_dirs_mask = [x for x in Equo.Settings()['system_dirs_mask'] \
        if entropy.tools.is_valid_path(x)]
    system_dirs_mask_regexp = []
    for mask in Equo.Settings()['system_dirs_mask']:
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
            ' '.join(Equo.Settings()['system_dirs']))
        print_info(red(" @@ ") + blue("%s: " % (_("Masked directories"),) ) + \
            ' '.join(Equo.Settings()['system_dirs_mask']))
        print_info(red(" @@ ")+blue("%s: " % (
            _("Number of files collected on the filesystem"),) ) + \
            bold(str(totalfiles)))
        print_info(red(" @@ ")+blue("%s..." % (
            _("Now looking into Installed Packages database"),)))


    idpackages = clientDbconn.listAllPackageIds()
    length = str(len(idpackages))
    count = 0

    def gen_cont(idpackage):
        for path in clientDbconn.retrieveContent(idpackage):
            # reverse sym
            for sym_dir in reverse_symlink_map:
                if path.startswith(sym_dir):
                    for sym_child in reverse_symlink_map[sym_dir]:
                        yield sym_child+path[len(sym_dir):]
            # real path also
            dirname_real = os.path.realpath(os.path.dirname(path))
            yield os.path.join(dirname_real, os.path.basename(path))
            yield path

    for idpackage in idpackages:

        if not etpUi['quiet']:
            count += 1
            atom = clientDbconn.retrieveAtom(idpackage)
            txt = "["+str(count)+"/"+length+"] "
            print_info(red(" @@ ") + blue("%s: " % (
                _("Intersecting with content of the package"),) ) + txt + \
                bold(str(atom)), back = True)

        # remove from file_data
        file_data -= set(gen_cont(idpackage))

    orpanedfiles = len(file_data)

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

    fname = "/tmp/entropy-orphans.txt"
    f_out = open(fname, "wb")
    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue("%s: " % (_
            ("Writing file to disk"),)) + bold(fname))

    sizecount = 0
    file_data = list(file_data)
    file_data.sort(reverse = True)

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
    f_out.close()

    humansize = entropy.tools.bytes_into_human(sizecount)
    if not etpUi['quiet']:
        print_info(red(" @@ ") + \
            blue("%s: " % (_("Total wasted space"),) ) + bold(humansize))
    else:
        print_generic(humansize)

    return 0


def search_removal_dependencies(atoms, deep = False, Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    clientDbconn = Equo.installed_repository()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Removal Search"),) ))

    found_atoms = [clientDbconn.atomMatch(x) for x in atoms]
    found_atoms = [(x[0], etpConst['clientdbid']) for x \
        in found_atoms if x[1] == 0]

    if not found_atoms:
        print_error(red("%s." % (_("No packages found"),) ))
        return 127

    removal_queue = []
    if not etpUi['quiet']:
        print_info(red(" @@ ") + blue("%s..." % (
            _("Calculating removal dependencies, please wait"),) ), back = True)
    treeview = Equo._generate_reverse_dependency_tree(found_atoms, deep = deep,
        system_packages = True)
    for dep_lev in sorted(treeview, reverse = True):
        for dep_sub_el in treeview[dep_lev]:
            removal_queue.append(dep_sub_el)

    if removal_queue:
        if not etpUi['quiet']:
            print_info(red(" @@ ") + \
                blue("%s:" % (
                _("These are the packages that would added to the removal queue"),)))

        totalatoms = str(len(removal_queue))
        atomscounter = 0

        for idpackage in removal_queue:

            atomscounter += 1
            rematom = clientDbconn.retrieveAtom(idpackage)
            if etpUi['quiet']:
                print_generic(rematom)
                continue

            installedfrom = clientDbconn.getInstalledPackageRepository(
                idpackage)
            if installedfrom is None:
                installedfrom = _("Not available")
            repo_info = bold("[") + red("%s: " % (_("from"),)) + \
                brown(installedfrom)+bold("]")
            stratomscounter = str(atomscounter)
            while len(stratomscounter) < len(totalatoms):
                stratomscounter = " "+stratomscounter
            print_info("   # " + red("(") + bold(stratomscounter) + "/" + \
                blue(str(totalatoms)) + red(")") + repo_info + " " + \
                blue(rematom))

    return 0



def list_installed_packages(Equo = None, dbconn = None):

    if Equo is None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Installed Search"),)))

    clientDbconn = Equo.installed_repository()
    if dbconn:
        clientDbconn = dbconn

    inst_packages = clientDbconn.listAllPackages(order_by = "atom")

    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue("%s:" % (
            _("These are the installed packages"),) ))

    for atom, idpackage, branch in inst_packages:
        if not etpUi['verbose']:
            atom = entropy.tools.dep_getkey(atom)
        branchinfo = ""
        sizeinfo = ""
        if etpUi['verbose']:
            branchinfo = darkgreen(" [")+red(branch)+darkgreen("] ")
            mysize = clientDbconn.retrieveOnDiskSize(idpackage)
            mysize = entropy.tools.bytes_into_human(mysize)
            sizeinfo = brown(" [")+purple(mysize)+brown("]")
        if not etpUi['quiet']:
            print_info(red("  # ") + blue(str(idpackage)) + sizeinfo + \
                branchinfo + " " + atom)
        else:
            print_generic(atom)

    return 0


def search_package(packages, Equo = None, get_results = False,
    from_installed = False, ignore_installed = False):

    if Equo is None:
        Equo = EquoInterface()

    if not etpUi['quiet'] and not get_results:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Searching"),) ))

    def do_adv_search(dbconn, from_client = False):
        pkg_ids = set()
        for package in packages:
            slot = entropy.tools.dep_getslot(package)
            tag = entropy.tools.dep_gettag(package)
            package = entropy.tools.remove_slot(package)
            package = entropy.tools.remove_tag(package)

            try:
                result = set(dbconn.searchPackages(package, slot = slot,
                    tag = tag, just_id = True))
                if not result: # look for something else?
                    pkg_id, rc = dbconn.atomMatch(package, matchSlot = slot)
                    if pkg_id != -1:
                        result = set([pkg_id])
                pkg_ids |= result
            except DatabaseError:
                continue

        return pkg_ids

    search_data = set()
    found = False
    rc_results = []

    if not from_installed:
        for repo in Equo.repositories():

            dbconn = Equo.open_repository(repo)
            pkg_ids = do_adv_search(dbconn)
            if pkg_ids:
                found = True
            search_data.update(((x, repo) for x in pkg_ids))

    # try to actually match something in installed packages db
    if not found and (Equo.installed_repository() is not None) and not ignore_installed:
        pkg_ids = do_adv_search(Equo.installed_repository(), from_client = True)
        if pkg_ids:
            found = True
        search_data.update(((x, etpConst['clientdbid']) for x in pkg_ids))

    if get_results:
        return sorted((Equo.open_repository(y).retrieveAtom(x) for x, y in \
            search_data))

    key_sorter = lambda (x, y): Equo.open_repository(y).retrieveAtom(x)
    for pkg_id, pkg_repo in sorted(search_data, key = key_sorter):
        dbconn = Equo.open_repository(pkg_repo)
        from_client = pkg_repo == etpConst['clientdbid']
        print_package_info(pkg_id, dbconn, Equo = Equo,
            extended = etpUi['verbose'], clientSearch = from_client)

    if not etpUi['quiet']:
        toc = []
        toc.append(("%s:" % (blue(_("Keywords")),), purple(', '.join(packages))))
        toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
            len(search_data), brown(_("entries")),)))
        print_table(toc)

    return 0

def search_mimetype(mimetypes, Equo = None, installed = False,
    associate = False):

    if Equo is None:
        Equo = EquoInterface()

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
                Equo.search_installed_mimetype(mimetype)]
        else:
            matches = Equo.search_available_mimetype(mimetype)

        if matches:
            found = True

        key_sorter = lambda (x, y): Equo.open_repository(y).retrieveAtom(x)
        for pkg_id, pkg_repo in sorted(matches, key = key_sorter):
            dbconn = Equo.open_repository(pkg_repo)
            print_package_info(pkg_id, dbconn, Equo = Equo,
                extended = etpUi['verbose'])

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Keyword")),), purple(mimetype)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(matches), brown(_("entries")),)))
            print_table(toc)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def match_package(packages, multiMatch = False, multiRepo = False,
    showRepo = False, showDesc = False, Equo = None, get_results = False,
    installed = False):

    if Equo is None:
        Equo = EquoInterface()

    if not etpUi['quiet'] and not get_results:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Matching"),) ),
            back = True)
    found = False
    rc_results = []

    for package in packages:

        if not etpUi['quiet'] and not get_results:
            print_info("%s: %s" % (blue("  # "), bold(package),))

        if installed:
            inst_pkg_id, inst_rc = Equo.installed_repository().atomMatch(
                package, multiMatch = multiMatch)
            if inst_rc != 0:
                match = (-1, 1)
            else:
                if multiMatch:
                    match = ([(x, etpConst['clientdbid']) for x in inst_pkg_id],
                        0)
                else:
                    match = (inst_pkg_id, etpConst['clientdbid'])
        else:
            match = Equo.atom_match(package, multi_match = multiMatch,
                multi_repo = multiRepo, mask_filter = False)
        if match[1] != 1:

            if not multiMatch:
                if multiRepo:
                    matches = match[0]
                else:
                    matches = [match]
            else:
                matches = match[0]

            key_sorter = lambda (x, y): Equo.open_repository(y).retrieveAtom(x)
            for pkg_id, pkg_repo in sorted(matches, key = key_sorter):
                dbconn = Equo.open_repository(pkg_repo)
                if get_results:
                    rc_results.append(dbconn.retrieveAtom(pkg_id))
                else:
                    print_package_info(pkg_id, dbconn,
                        showRepoOnQuiet = showRepo,
                            showDescOnQuiet = showDesc, Equo = Equo,
                                extended = etpUi['verbose'])
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
    return 0

def search_slotted_packages(slots, Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Slot Search"),) ))

    # search inside each available database
    repo_number = 0
    for repo in Equo.repositories():
        repo_number += 1

        if not etpUi['quiet']:
            print_info(blue("  #"+str(repo_number)) + \
                bold(" " + Equo.Settings()['repositories']['available'][repo]['description']))

        dbconn = Equo.open_repository(repo)
        for slot in slots:

            results = dbconn.searchSlotted(slot, just_id = True)
            key_sorter = lambda x: dbconn.retrieveAtom(x)
            for idpackage in sorted(results, key = key_sorter):
                found = True
                print_package_info(idpackage, dbconn, Equo = Equo,
                    extended = etpUi['verbose'], strictOutput = etpUi['quiet'])

            if not etpUi['quiet']:
                toc = []
                toc.append(("%s:" % (blue(_("Keyword")),), purple(slot)))
                toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                    len(results), brown(_("entries")),)))
                print_table(toc)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_package_sets(items, Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (
            _("Package Set Search"),)))

    if not items:
        items.append('*')

    sets = Equo.Sets()

    matchNumber = 0
    for item in items:
        results = sets.search(item)
        key_sorter = lambda (x, y, z): y
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

def search_tagged_packages(tags, Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Tag Search"),)))

    repo_number = 0
    for repo in Equo.repositories():
        repo_number += 1

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repo_number)) + \
                bold(" " + Equo.Settings()['repositories']['available'][repo]['description']))

        dbconn = Equo.open_repository(repo)
        key_sorter = lambda x: dbconn.retrieveAtom(x[1])
        for tag in tags:
            results = dbconn.searchTaggedPackages(tag, atoms = True)
            found = True
            for result in sorted(results, key = key_sorter):
                print_package_info(result[1], dbconn, Equo = Equo,
                    extended = etpUi['verbose'], strictOutput = etpUi['quiet'])

            if not etpUi['quiet']:
                toc = []
                toc.append(("%s:" % (blue(_("Keyword")),), purple(tag)))
                toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                    len(results), brown(_("entries")),)))
                print_table(toc)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_rev_packages(revisions, Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Revision Search"),)))
        print_info(bold(_("Installed packages repository")))

    dbconn = Equo.installed_repository()
    key_sorter = lambda x: dbconn.retrieveAtom(x)

    for revision in revisions:
        results = dbconn.searchRevisionedPackages(revision)
        found = True
        for idpackage in sorted(results, key = key_sorter):
            print_package_info(idpackage, dbconn, Equo = Equo,
                extended = etpUi['verbose'], strictOutput = etpUi['quiet'],
                clientSearch = True)

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Keyword")),), purple(revision)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(results), brown(_("entries")),)))
            print_table(toc)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_licenses(licenses, Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("License Search"),)))

    # search inside each available database
    repo_number = 0
    for repo in Equo.repositories():
        repo_number += 1

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repo_number)) + \
                bold(" " + Equo.Settings()['repositories']['available'][repo]['description']))

        dbconn = Equo.open_repository(repo)
        key_sorter = lambda x: dbconn.retrieveAtom(x)

        for mylicense in licenses:

            results = dbconn.searchLicense(mylicense, just_id = True)
            if not results:
                continue
            found = True
            for idpackage in sorted(results, key = key_sorter):
                print_package_info(idpackage, dbconn, Equo = Equo,
                    extended = etpUi['verbose'], strictOutput = etpUi['quiet'])

            if not etpUi['quiet']:
                toc = []
                toc.append(("%s:" % (blue(_("Keyword")),), purple(mylicense)))
                toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                    len(results), brown(_("entries")),)))
                print_table(toc)

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_description(descriptions, Equo = None):

    if Equo is None:
        Equo = EquoInterface()

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Description Search"),) ))

    repo_number = 0
    for repo in Equo.repositories():
        repo_number += 1

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repo_number)) + \
                bold(" " + Equo.Settings()['repositories']['available'][repo]['description']))

        dbconn = Equo.open_repository(repo)
        descdata = search_descriptions(descriptions, dbconn, Equo = Equo)
        if descdata:
            found = True

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_descriptions(descriptions, dbconn, Equo = None):

    key_sorter = lambda x: dbconn.retrieveAtom(x[1])
    mydescdata = {}
    for desc in descriptions:

        result = dbconn.searchDescription(desc)
        if not result:
            continue

        mydescdata[desc] = result
        for pkg in sorted(mydescdata[desc], key = key_sorter):
            idpackage = pkg[1]
            if (etpUi['quiet']):
                print_generic(dbconn.retrieveAtom(idpackage))
            else:
                print_package_info(idpackage, dbconn, Equo = Equo,
                    extended = etpUi['verbose'], strictOutput = etpUi['quiet'])

        if not etpUi['quiet']:
            toc = []
            toc.append(("%s:" % (blue(_("Keyword")),), purple(desc)))
            toc.append(("%s:" % (blue(_("Found")),), "%s %s" % (
                len(mydescdata[desc]), brown(_("entries")),)))
            print_table(toc)

    return mydescdata

def print_package_info(idpackage, dbconn, clientSearch = False,
    strictOutput = False, extended = False, Equo = None,
    showRepoOnQuiet = False, showDescOnQuiet = False):

    if Equo is None:
        Equo = EquoInterface()

    # now fetch essential info
    pkgatom = dbconn.retrieveAtom(idpackage)
    if etpUi['quiet']:
        repoinfo = ''
        desc = ''
        if showRepoOnQuiet:
            repoinfo = "[%s] " % (dbconn.reponame,)
        if showDescOnQuiet:
            desc = ' %s' % (dbconn.retrieveDescription(idpackage),)
        print_generic("%s%s%s" % (repoinfo, pkgatom, desc,))
        return

    pkghome = dbconn.retrieveHomepage(idpackage)
    pkgslot = dbconn.retrieveSlot(idpackage)
    pkgver = dbconn.retrieveVersion(idpackage)
    pkgtag = dbconn.retrieveTag(idpackage)
    pkgrev = dbconn.retrieveRevision(idpackage)
    pkgdesc = dbconn.retrieveDescription(idpackage)
    pkgbranch = dbconn.retrieveBranch(idpackage)
    if not pkgtag:
        pkgtag = "NoTag"

    if not clientSearch:

        # client info
        installedVer = _("Not installed")
        installedTag = _("N/A")
        installedRev = _("N/A")
        try:
            pkginstalled = Equo.installed_repository().atomMatch(
                entropy.tools.dep_getkey(pkgatom), matchSlot = pkgslot)
            if pkginstalled[1] == 0:
                idx = pkginstalled[0]
                # found
                installedVer = Equo.installed_repository().retrieveVersion(idx)
                installedTag = Equo.installed_repository().retrieveTag(idx)
                if not installedTag:
                    installedTag = "NoTag"
                installedRev = Equo.installed_repository().retrieveRevision(idx)
        except:
            clientSearch = True

    toc = []

    print_info(red("     @@ %s: " % (_("Package"),) ) + bold(pkgatom) + \
        " "+ blue("%s: " % (_("branch"),)) + bold(pkgbranch) + \
        ", [" + purple(str(dbconn.reponame)) + "] ")
    if not strictOutput and extended:
        pkgname = dbconn.retrieveName(idpackage)
        pkgcat = dbconn.retrieveCategory(idpackage)
        toc.append((darkgreen("       %s:" % (_("Category"),)),
            blue(pkgcat)))
        toc.append((darkgreen("       %s:" % (_("Name"),)),
            blue(pkgname)))

    if extended:

        pkgmasked = False
        masking_reason = ''
        # check if it's masked
        idpackage_masked, idmasking_reason = dbconn.maskFilter(idpackage)
        if idpackage_masked == -1:
            pkgmasked = True
            masking_reason = ", %s" % (
                Equo.Settings()['pkg_masking_reasons'].get(
                    idmasking_reason),)

        toc.append((darkgreen("       %s:" % (_("Masked"),)),
            blue(str(pkgmasked)) + masking_reason,))

    avail_str = _("Available")
    if clientSearch:
        avail_str = _("Installed")
    toc.append((
        darkgreen("       %s:" % (avail_str,)),
        blue("%s: " % (_("version"),) ) + bold(pkgver) + blue(" ~ tag: ") + \
        bold(pkgtag) + blue(" ~ %s: " % (_("revision"),) ) + bold(str(pkgrev)),)
    )

    if not clientSearch:
        toc.append((darkgreen("       %s:" % (_("Installed"),) ),
            blue("%s: " % (_("version"),) ) + bold(installedVer) + \
            blue(" ~ tag: ") + bold(installedTag) + \
            blue(" ~ %s: " % (_("revision"),) ) + bold(str(installedRev)),))

    if not strictOutput:
        toc.append((darkgreen("       %s:" % (_("Slot"),) ),
            blue(str(pkgslot)),))

        if extended:
            pkgsize = dbconn.retrieveSize(idpackage)
            pkgsize = entropy.tools.bytes_into_human(pkgsize)
            pkgbin = dbconn.retrieveDownloadURL(idpackage)
            pkgdigest = dbconn.retrieveDigest(idpackage)
            pkgdeps = dbconn.retrieveDependencies(idpackage, extended = True)
            pkgconflicts = dbconn.retrieveConflicts(idpackage)
            depsorter = lambda x: entropy.tools.dep_getcpv(x[0])

            toc.append((darkgreen("       %s:" % (_("Size"),) ),
                blue(str(pkgsize)),))

            toc.append((darkgreen("       %s:" % (_("Download"),) ),
                brown(str(pkgbin)),))

            toc.append((darkgreen("       %s:" % (_("Checksum"),) ),
                brown(str(pkgdigest)),))

            if pkgdeps:
                toc.append(darkred("       ##") + " " + \
                    darkgreen("%s:" % (_("Dependencies"),) ))

                for pdep, p_id in sorted(pkgdeps, key = depsorter):
                    toc.append(("       %s    " % (brown("##"),),
                        "%s%s%s %s" % (blue("["), p_id, blue("]"),
                        brown(pdep),)))

                # show legend
                len_txt = "       %s" % (brown("##"),)
                toc.append((len_txt, "%s:" % (blue(_("Legend")),),))
                dep_leg = _show_dependencies_legend(
                    indent = "", get_data = True)
                toc.extend([(len_txt, x) for x in dep_leg])


            if pkgconflicts:
                toc.append(darkred("       ##") + " " + \
                    darkgreen("%s:" % (_("Conflicts"),) ))
                for conflict in sorted(pkgconflicts, key = depsorter):
                    toc.append(("       %s" % (darkred("##"),),
                        brown(conflict),))

    home_txt = "       %s:" % (_("Homepage"),)
    home_lines = _my_formatted_print(pkghome, "", "", color = brown,
        min_chars = 15, get_data = True)
    for home_line in home_lines:
        toc.append((darkgreen(home_txt), home_line,))
        home_txt = " "

    if not strictOutput:

        desc_txt = "       %s:" % (_("Description"),)
        desc_lines = _my_formatted_print(pkgdesc, "", "", get_data = True)
        for desc_line in desc_lines:
            toc.append((darkgreen(desc_txt), purple(desc_line)))
            desc_txt = " "

        if extended:
            pkguseflags = dbconn.retrieveUseflags(idpackage)
            use_txt = "       %s:" % (_("USE flags"),)
            use_lines = _my_formatted_print(pkguseflags, "", "", color = teal,
                get_data = True)
            for use_line in use_lines:
                toc.append((darkgreen(use_txt), use_line))
                use_txt = " "

    if not strictOutput:

        if extended:

            chost, cflags, cxxflags = dbconn.retrieveCompileFlags(idpackage)
            sources = dbconn.retrieveSources(idpackage)
            eclasses = dbconn.retrieveEclasses(idpackage)
            etpapi = dbconn.retrieveApi(idpackage)

            toc.append((darkgreen("       %s:" % (_("CHOST"),)),
                blue(chost)))
            toc.append((darkgreen("       %s:" % (_("CFLAGS"),)),
                blue(cflags)))
            toc.append((darkgreen("       %s:" % (_("CXXFLAGS"),)),
                blue(cxxflags)))

            eclass_txt = "       %s:" % (_("Portage eclasses"),)
            eclass_lines = _my_formatted_print(eclasses, "", "", color = red,
                get_data = True)
            for eclass_line in eclass_lines:
                toc.append((darkgreen(eclass_txt), eclass_line))
                eclass_txt = " "

            if sources:
                sources_txt = "       %s:" % (_("Sources"),)
                toc.append(darkgreen(sources_txt))
                for source in sources:
                    toc.append((" ", source,))

            toc.append((darkgreen("       %s:" % (_("Entry API"),)),
                purple(str(etpapi))))
            toc.append((darkgreen("       %s:" % (_("Compiled with"),)),
                blue(cflags)))

            pkgkeywords = ' '.join(sorted(dbconn.retrieveKeywords(idpackage)))
            keyword_txt = "       %s:" % (_("Keywords"),)
            keyword_lines = _my_formatted_print(pkgkeywords, "", "",
                color = brown, get_data = True)
            for keyword_line in keyword_lines:
                toc.append((darkgreen(keyword_txt), brown(keyword_line)))
                keyword_txt = " "

            mydate = dbconn.retrieveCreationDate(idpackage)
            pkgcreatedate = "N/A"
            if mydate:
                pkgcreatedate = entropy.tools.convert_unix_time_to_human_time(
                    float(mydate))

            toc.append((darkgreen("       %s:" % (_("Created"),)),
                purple(pkgcreatedate)))

        pkglic = dbconn.retrieveLicense(idpackage)
        toc.append((darkgreen("       %s:" % (_("License"),)),
            teal(pkglic)))

    print_table(toc, cell_spacing = 3)

def _my_formatted_print(data, header, reset_columns, min_chars = 25,
    color = None, get_data = False):

    out_data = []

    if isinstance(data, set):
        mydata = list(data)
    elif not isinstance(data, list):
        mydata = data.split()
    else:
        mydata = data

    fcount = 0
    desc_text = header
    for item in mydata:
        fcount += len(item)
        if color:
            desc_text += color(item)+" "
        else:
            desc_text += item+" "
        if fcount > min_chars:
            fcount = 0
            if get_data:
                out_data.append(desc_text)
            else:
                print_info(desc_text)
            desc_text = reset_columns

    if fcount > 0:
        if get_data:
            out_data.append(desc_text)
        else:
            print_info(desc_text)

    if get_data:
        return out_data
