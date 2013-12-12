# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
from entropy.const import etpConst, const_convert_to_unicode
from entropy.i18n import _
from entropy.output import darkgreen, purple, blue, \
    brown, bold, red, darkred, teal, decolorize, MESSAGE_HEADER
from entropy.graph import Graph
from entropy.misc import Lifo

import entropy.dep


def show_dependencies_legend(entropy_server, indent = '',
                             get_data = False):
    data = []
    dep_type_ids = etpConst['dependency_type_ids']
    for dep_id, dep_val in sorted(dep_type_ids.items(),
                                  key = lambda x: x[0], reverse = True):

        dep_desc = etpConst['dependency_type_ids_desc'].get(
            dep_id, _("N/A"))
        txt = '%s%s%s%s %s' % (
            indent, teal("{"), dep_val, teal("}"), dep_desc,)
        if get_data:
            data.append(txt)
        else:
            entropy_server.output(txt)
    if get_data:
        return data

def print_package_info(package_id, entropy_server, entropy_repository,
    installed_search = False, strict_output = False, extended = False,
    quiet = False, show_repo_if_quiet = False, show_desc_if_quiet = False,
    show_slot_if_quiet = False):
    """
    Print Entropy Package Metadata in a pretty and uniform way.
    """
    corrupted_str = _("corrupted")
    pkgatom = entropy_repository.retrieveAtom(package_id) or corrupted_str
    if quiet:
        repoinfo = ''
        desc = ''
        if show_repo_if_quiet:
            repoinfo = "[%s] " % (entropy_repository.repository_id(),)
        if show_desc_if_quiet:
            desc = ' %s' % (
                entropy_repository.retrieveDescription(package_id),)
        if not extended:
            pkgatom = entropy.dep.dep_getkey(pkgatom)
        if show_slot_if_quiet:
            pkgatom += etpConst['entropyslotprefix']
            pkgatom += entropy_repository.retrieveSlot(package_id)
        entropy_server.output(
            "%s%s%s" % (repoinfo, pkgatom, desc,),
            level="generic")
        return

    pkghome = entropy_repository.retrieveHomepage(package_id)
    if pkghome is None:
        pkghome = corrupted_str
    pkgslot = entropy_repository.retrieveSlot(package_id) \
        or corrupted_str
    pkgver = entropy_repository.retrieveVersion(package_id) \
        or corrupted_str
    pkgtag = entropy_repository.retrieveTag(package_id)
    if pkgtag is None:
        pkgtag = corrupted_str
    pkgrev = entropy_repository.retrieveRevision(package_id)
    if pkgrev is None:
        pkgrev = 0
    pkgdesc = entropy_repository.retrieveDescription(package_id)
    if pkgdesc is None:
        pkgdesc = corrupted_str
    pkgbranch = entropy_repository.retrieveBranch(package_id) \
        or corrupted_str
    if not pkgtag:
        pkgtag = "NoTag"

    installed_ver = _("Not installed")
    installed_tag = _("N/A")
    installed_rev = _("N/A")
    if not installed_search:

        # client info
        pkginstalled = entropy_server.installed_repository().atomMatch(
            entropy.dep.dep_getkey(pkgatom), matchSlot = pkgslot)
        if pkginstalled[1] == 0:
            idx = pkginstalled[0]
            # found
            installed_ver = entropy_server.installed_repository(
                ).retrieveVersion(idx) or corrupted_str
            installed_tag = entropy_server.installed_repository(
                ).retrieveTag(idx)
            if not installed_tag:
                installed_tag = "NoTag"
            installed_rev = entropy_server.installed_repository(
                ).retrieveRevision(idx)
            if installed_rev is None:
                installed_rev = const_convert_to_unicode("0")
            else:
                installed_rev = const_convert_to_unicode(installed_rev)

    toc = []

    entropy_server.output(red("     @@ %s: " % (_("Package"),) ) + \
        bold(pkgatom) + \
        " "+ blue("%s: " % (_("branch"),)) + bold(pkgbranch) + \
        ", [" + purple(str(entropy_repository.repository_id())) + "] ")
    if not strict_output and extended:
        pkgname = entropy_repository.retrieveName(package_id) \
            or corrupted_str
        pkgcat = entropy_repository.retrieveCategory(package_id) \
            or corrupted_str
        toc.append((darkgreen("       %s:" % (_("Category"),)),
            blue(pkgcat)))
        toc.append((darkgreen("       %s:" % (_("Name"),)),
            blue(pkgname)))

    if extended:

        pkgmasked = False
        masking_reason = ''
        # check if it's masked
        package_id_masked, idmasking_reason = \
            entropy_repository.maskFilter(package_id)
        if package_id_masked == -1:
            pkgmasked = True
            masking_reason = ", %s" % (
                entropy_server.Settings()['pkg_masking_reasons'].get(
                    idmasking_reason),)

        toc.append((darkgreen("       %s:" % (_("Masked"),)),
            blue(str(pkgmasked)) + masking_reason,))

    avail_str = _("Available")
    if installed_search:
        avail_str = _("Installed")
    toc.append((
        darkgreen("       %s:" % (avail_str,)),
        blue("%s: " % (_("version"),) ) + bold(pkgver) + blue(" ~ tag: ") + \
        bold(pkgtag) + blue(" ~ %s: " % (_("revision"),) ) + bold(str(pkgrev)),)
    )

    if not installed_search:
        toc.append((darkgreen("       %s:" % (_("Installed"),) ),
            blue("%s: " % (_("version"),) ) + bold(installed_ver) + \
            blue(" ~ tag: ") + bold(installed_tag) + \
            blue(" ~ %s: " % (_("revision"),) ) + bold(installed_rev),))

    if not strict_output:
        toc.append((darkgreen("       %s:" % (_("Slot"),) ),
            blue(pkgslot),))

        if extended:
            pkgsize = entropy_repository.retrieveSize(package_id)
            pkgsize = entropy.tools.bytes_into_human(pkgsize)
            pkgbin = entropy_repository.retrieveDownloadURL(package_id)
            if pkgbin is None:
                pkgbin = corrupted_str
            pkgdigest = entropy_repository.retrieveDigest(package_id) or \
                corrupted_str
            pkgsign = entropy_repository.retrieveSignatures(package_id)
            pkgdeps = entropy_repository.retrieveDependencies(package_id,
                extended = True, resolve_conditional_deps = False)
            pkgconflicts = entropy_repository.retrieveConflicts(package_id)
            depsorter = lambda x: entropy.dep.dep_getcpv(x[0])

            toc.append((darkgreen("       %s:" % (_("Size"),) ),
                blue(pkgsize),))
            toc.append((darkgreen("       %s:" % (_("Download"),) ),
                brown(pkgbin),))
            toc.append((darkgreen("       %s:" % (_("Checksum"),) ),
                brown(pkgdigest),))
            if pkgsign:
                sha1, sha256, sha512, gpg = pkgsign
                if not sha1:
                    sha1 = _("N/A")
                if not sha256:
                    sha256 = _("N/A")
                toc.append((darkgreen("       %s:" % (_("SHA1"),) ),
                            brown(sha1),))
                toc.append((darkgreen("       %s:" % (_("SHA256"),) ),
                            brown(sha256),))
                if gpg:
                    gpg_str = _("Yes")
                else:
                    gpg_str = _("No")
                toc.append((darkgreen("       %s:" % (_("GPG"),) ),
                            brown(gpg_str),))

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
                dep_leg = show_dependencies_legend(entropy_server,
                    indent = "", get_data = True)
                toc.extend([(len_txt, x) for x in dep_leg])


            if pkgconflicts:
                toc.append(darkred("       ##") + " " + \
                    darkgreen("%s:" % (_("Conflicts"),) ))
                for conflict in sorted(pkgconflicts, key = depsorter):
                    toc.append(("       %s" % (darkred("##"),),
                        brown(conflict),))

    home_txt = "       %s:" % (_("Homepage"),)
    home_lines = _formatted_print(
        entropy_server, pkghome, "", "", color = brown,
        min_chars = 15, get_data = True)
    for home_line in home_lines:
        toc.append((darkgreen(home_txt), home_line,))
        home_txt = " "

    if not strict_output:

        desc_txt = "       %s:" % (_("Description"),)
        desc_lines = _formatted_print(
            entropy_server, pkgdesc, "", "", get_data = True)
        for desc_line in desc_lines:
            toc.append((darkgreen(desc_txt), purple(desc_line)))
            desc_txt = " "

        if extended:
            pkguseflags = entropy_repository.retrieveUseflags(package_id)
            use_txt = "       %s:" % (_("USE flags"),)
            use_lines = _formatted_print(
                entropy_server,
                pkguseflags, "", "", color = teal,
                get_data = True)
            for use_line in use_lines:
                toc.append((darkgreen(use_txt), use_line))
                use_txt = " "

    if not strict_output:

        if extended:

            chost, cflags, cxxflags = \
                entropy_repository.retrieveCompileFlags(package_id)
            sources = entropy_repository.retrieveSources(package_id)
            etpapi = entropy_repository.retrieveApi(package_id)
            if etpapi is None:
                etpapi =  corrupted_str

            toc.append((darkgreen("       %s:" % (_("CHOST"),)),
                blue(chost)))
            toc.append((darkgreen("       %s:" % (_("CFLAGS"),)),
                blue(cflags)))
            toc.append((darkgreen("       %s:" % (_("CXXFLAGS"),)),
                blue(cxxflags)))

            if sources:
                sources_txt = "       %s:" % (_("Sources"),)
                toc.append(darkgreen(sources_txt))
                for source in sources:
                    toc.append((" ", source,))

            toc.append((darkgreen("       %s:" % (_("Entry API"),)),
                purple(str(etpapi))))
            toc.append((darkgreen("       %s:" % (_("Compiled with"),)),
                blue(cflags)))

            pkgkeywords = ' '.join(
                sorted(entropy_repository.retrieveKeywords(package_id)))
            keyword_txt = "       %s:" % (_("Keywords"),)
            keyword_lines = _formatted_print(
                entropy_server, pkgkeywords, "", "",
                color = brown, get_data = True)
            for keyword_line in keyword_lines:
                toc.append((darkgreen(keyword_txt), brown(keyword_line)))
                keyword_txt = " "

            mydate = entropy_repository.retrieveCreationDate(package_id)
            pkgcreatedate = "N/A"
            if mydate:
                pkgcreatedate = \
                    entropy.tools.convert_unix_time_to_human_time(
                        float(mydate))

            toc.append((darkgreen("       %s:" % (_("Created"),)),
                purple(pkgcreatedate)))

        pkglic = entropy_repository.retrieveLicense(package_id)
        if pkglic is None:
            pkglic = corrupted_str
        toc.append((darkgreen("       %s:" % (_("License"),)),
            teal(pkglic)))

    print_table(entropy_server, toc, cell_spacing = 3)

def _formatted_print(entropy_server, data, header, reset_columns,
                     min_chars = 25, color = None, get_data = False):

    out_data = []

    if isinstance(data, (frozenset, set)):
        mydata = sorted(data)
    elif not isinstance(data, (list, tuple)):
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
                entropy_server.output(desc_text)
            desc_text = reset_columns

    if fcount > 0:
        if get_data:
            out_data.append(desc_text)
        else:
            entropy_server.output(desc_text)

    if get_data:
        return out_data

def print_table(entropy_server, lines_data,
                cell_spacing=2, cell_padding=0,
                side_color=darkgreen):
    """
    Print a table composed by len(lines_data[i]) columns and len(lines_data)
    rows.

    @param lines_data: list of row data
    @type lines_data: list
    @keyword cell_spacing: cell spacing
    @type cell_spacing: int
    @keyword cell_padding: cell padding
    @type cell_padding: int
    @keyword side_color: colorization callback function
    @type side_color: callable
    """
    column_sizes = {}
    padding_side = int((cell_padding / 2))
    col_n = 0
    for cols in lines_data:
        if not isinstance(cols, (list, tuple)):
            # can be a plain string
            continue
        col_n = 0
        for cell in cols:
            cell_len = len(" "*padding_side + decolorize(cell.split("\n")[0]) \
                 + " "*padding_side)
            cur_len = column_sizes.get(col_n)
            if cur_len is None:
                column_sizes[col_n] = cell_len
            elif cur_len < cell_len:
                column_sizes[col_n] = cell_len
            col_n += 1

    # now actually print
    if col_n > 0:
        column_sizes[col_n - 1] = 0
    for cols in lines_data:
        txt = side_color(MESSAGE_HEADER) + "  "

        if isinstance(cols, (list, tuple)):
            col_n = 0
            for cell in cols:
                max_len = column_sizes[col_n]
                cell = " "*padding_side + cell + " "*padding_side
                delta_len = max_len - \
                    len(decolorize(cell.split("\n")[0])) + \
                    cell_spacing
                if col_n == (len(cols) - 1):
                    txt += cell
                else:
                    txt += cell + " "*delta_len
                col_n += 1
        else:
            txt += cols
        entropy_server.output(txt, level="generic")

def revgraph_packages(packages, entropy_client, complete = False,
    repository_ids = None, quiet = False):

    if repository_ids is None:
        repository_ids = [entropy_client.installed_repository(
                ).repository_id()]

    found = False
    for repository_id in repository_ids:
        entropy_repository = entropy_client.open_repository(repository_id)
        for package in packages:
            pkg_id, pkg_rc = entropy_repository.atomMatch(package)
            if pkg_rc == 1:
                continue
            if not quiet:
                entropy_client.output(
                    darkgreen("%s %s..." % (
                            _("Reverse graphing installed package"),
                            purple(package),) ),
                    header=brown(" @@ "))

            found = True
            g_pkg = entropy_repository.retrieveAtom(pkg_id)
            _revgraph_package(entropy_client, pkg_id, g_pkg,
                              entropy_repository,
                              show_complete = complete, quiet = quiet)

    if not found:
        entropy_client.output(
            purple(_("No packages found")),
            level="warning", importance=1)
        return 1

    return 0

def _print_graph_item_deps(entropy_client, item, out_data = None,
                           colorize = None):

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
    entropy_client.output(indent_txt + colorize(out_val), level="generic")
    if cached_endpoints and show_already_pulled_in:
        indent_txt = '[%s]\t' % (teal(str(ind_lvl)),) + '  ' * (ind_lvl + 1)
        for endpoint in sorted(cached_endpoints, key = lambda x: x.item()):
            endpoint_item = item_translation_callback(endpoint.item())
            entropy_client.output(indent_txt + brown(endpoint_item),
                                  level="generic")

    if valid_endpoints:
        out_data['lvl'] += 1
        out_data['cache'].update(valid_endpoints)
        for endpoint in sorted(valid_endpoints, key = lambda x: x.item()):
            _print_graph_item_deps(entropy_client, endpoint, out_data)
        out_data['lvl'] -= 1

def _show_graph_legend(entropy_client):
    entropy_client.output("%s:" % (purple(_("Legend")),))

    entropy_client.output("[%s] %s" % (blue("x"),
        blue(_("packages passed as arguments")),))

    entropy_client.output("[%s] %s" % (darkgreen("x"),
        darkgreen(_("packages with no further dependencies")),))

    entropy_client.output("[%s] %s" % (purple("x"),
        purple(_("packages with further dependencies (node)")),))

    entropy_client.output("[%s] %s" % (brown("x"),
        brown(_("packages already pulled in as dependency in upper levels (circularity)")),))

    entropy_client.output("="*40, level="generic")

def _revgraph_package(entropy_client, installed_pkg_id, package, dbconn,
                      show_complete = False, quiet = False):

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

    graph = Graph()
    stack = Lifo()
    inst_item = (installed_pkg_id, package)
    stack.push(inst_item)
    stack_cache = set()
    # ensure package availability in graph, initialize now
    graph.add(inst_item, set())

    def rev_pkgs_sorter(_pkg_id):
        return dbconn.retrieveAtom(_pkg_id)

    while stack.is_filled():

        item = stack.pop()
        if item in stack_cache:
            continue
        stack_cache.add(item)
        pkg_id, _was_dep = item

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

    _graph_to_stdout(entropy_client, graph, graph.get_node(inst_item),
        item_translation_func, show_already_pulled_in, quiet)
    if not quiet:
        _show_graph_legend(entropy_client)

    del stack
    graph.destroy()
    return 0

def graph_packages(packages, entropy_client, complete = False,
    repository_ids = None, quiet = False):

    found = False
    for package in packages:
        match = entropy_client.atom_match(package, match_repo = repository_ids)
        if match[0] == -1:
            continue
        if not quiet:
            entropy_client.output(
                darkgreen("%s %s..." % (
                _("Graphing"), purple(package),) ),
                header=brown(" @@ "))

        found = True
        pkg_id, repo_id = match
        repodb = entropy_client.open_repository(repo_id)
        g_pkg = repodb.retrieveAtom(pkg_id)
        _graph_package(match, g_pkg, entropy_client,
                       show_complete = complete, quiet = quiet)

    if not found:
        entropy_client.output(
            purple(_("No packages found")),
            level="warning", importance=1)
        return 1

    return 0

def _graph_package(match, package, entropy_intf, show_complete = False,
                   quiet = False):

    include_sys_pkgs = False
    show_already_pulled_in = False
    if show_complete:
        include_sys_pkgs = True
        show_already_pulled_in = True

    graph = Graph()
    stack = Lifo()
    start_item = (match, package, None)
    stack.push(start_item)
    stack_cache = set()
    # ensure package availability in graph, initialize now
    graph.add(start_item, [])
    depsorter = lambda x: entropy.dep.dep_getcpv(x[0])

    while stack.is_filled():

        item = stack.pop()
        if item in stack_cache:
            continue
        stack_cache.add(item)
        ((pkg_id, repo_id,), _was_dep, _dep_type) = item

        # deps
        repodb = entropy_intf.open_repository(repo_id)
        deps = repodb.retrieveDependencies(pkg_id, extended = True,
            resolve_conditional_deps = False)

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

    _graph_to_stdout(entropy_intf, graph, graph.get_node(start_item),
        item_translation_func, show_already_pulled_in, quiet)
    if not quiet:
        _show_graph_legend(entropy_intf)
        show_dependencies_legend(entropy_intf)

    del stack
    graph.destroy()
    return 0

def _graph_to_stdout(entropy_client, graph, start_item,
                     item_translation_callback,
                     show_already_pulled_in, quiet):

    if not quiet:
        entropy_client.output("="*40, level="generic")

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
            _print_graph_item_deps(
                entropy_client, item, out_data, colorize = blue)
            out_data['lvl'] = old_level
            if first_tree_item:
                out_data['lvl'] += 1
            first_tree_item = False

    del stack
