# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy misc command line interface (CLI) module}.
    In this module are enclosed all the miscellaneous functions
    used by Command Line based applications.

"""
import sys
import os
import time
import subprocess

from entropy.const import etpConst, const_convert_to_unicode
from entropy.output import print_info, print_generic, writechar, blue, \
    red, bold, darkred, brown, darkblue, purple, teal, darkgreen, \
    decolorize
from entropy.graph import Graph
from entropy.misc import Lifo
from entropy.i18n import _

import entropy.dep

def acquire_entropy_locks(entropy_client):
    """@deprecated"""
    import warnings
    import entropy.tools
    warnings.warn("deprecated, please use entropy.tools module")
    return entropy.tools.acquire_entropy_locks(entropy_client)

def release_entropy_locks(entropy_client):
    """@deprecated"""
    import warnings
    import entropy.tools
    warnings.warn("deprecated, please use entropy.tools module")
    return entropy.tools.release_entropy_locks(entropy_client)

def cleanup(directories):
    """
    Temporary files cleaner.

    @param directories: list of directory paths
    @type directories: list
    @return: exit status
    @rtype: int
    """
    counter = 0
    for xdir in directories:
        if not os.path.isdir(xdir):
            continue
        print_info("%s %s %s..." % (_("Cleaning"), darkgreen(xdir),
            _("directory"),), back = True)
        for data in os.listdir(xdir):
            subprocess.call(["rm", "-rf", os.path.join(xdir, data)])
            counter += 1

    print_info("%s: %s %s" % (
        _("Cleaned"), counter, _("files and directories"),))
    return 0

def print_bashcomp(data, cmdline, cb_map):
    """
    Print bash completion string for readline consumption using Entropy
    menu declaration format.

    @param data: Entropy menu declaration format
    @type data: list
    @param cmdline: list of cmdline args
    @type cmdline: list
    @param cb_map: map of completed commands callbacks, signature:
        <list of args to append> cb_map_callback(cur_cmdline)
    @type cb_map: dict
    """
    cmdline = cmdline[1:]
    cmdline_len = len(cmdline) # drop --stuff

    comp_line = []
    previous_complete = False
    if cmdline:
        last_cmdline = cmdline[-1]
    else:
        last_cmdline = '###impossible'

    try:
        prev_cmdline = cmdline[-2]
    except IndexError:
        prev_cmdline = None
    cur_cb = cb_map.get(prev_cmdline)
    if cur_cb is not None:
        ext_comp_line = cur_cb(cmdline)
        if ext_comp_line:
            comp_line.extend(ext_comp_line)

    got_inside = False

    for item in data:

        if item is None:
            continue

        if item[0] == cmdline_len:

            if item[1].startswith("--") and \
                not last_cmdline.startswith("-"):
                # skip --opts
                continue

            got_inside = True
            if item[1] == last_cmdline:
                cmdline_len += 1
                previous_complete = True
                continue
            elif item[1].startswith(last_cmdline):
                comp_line.append(item[1])
            elif previous_complete:
                comp_line.append(item[1])

        if (item[0] < cmdline_len) and got_inside and previous_complete:
            break

    if comp_line:
        print_generic(' '.join(comp_line))

def print_menu(data, args = None):
    """
    Function used by Entropy text client (will be moved from here) to
    print the menu output given a properly formatted list.
    This method is not intended for general used and will be moved away from
    here.
    """
    if args == None:
        args = []

    def orig_myfunc(x):
        return x
    def orig_myfunc_desc(x):
        return x

    try:
        i = args.index("--help")
        del args[i]
        command = args.pop(0)
    except ValueError:
        command = None
    except IndexError:
        command = None
    section_found = False
    search_depth = 1


    for item in data:
        myfunc = orig_myfunc
        myfunc_desc = orig_myfunc_desc

        if not item:
            if command is None:
                writechar("\n")
        else:
            n_indent = item[0]
            name = item[1]
            n_d_ident = item[2]
            desc = item[3]
            if command is not None:
                name_strip = name.split()[0].strip()
                if name_strip == command and n_indent == search_depth:
                    try:
                        command = args.pop(0)
                        search_depth = n_indent + 1
                    except IndexError:
                        command = "##unused_from_now_on"
                        section_found = True
                        indent_level = n_indent
                elif section_found:
                    if n_indent <= indent_level:
                        return
                else:
                    continue

            if n_indent == 0:
                writechar("  ")
            # setup identation
            ind_th = 0
            if command is not None: # so that partial --help looks nicer
                ind_th = 1
            while n_indent > ind_th:
                n_indent -= 1
                writechar("\t")
            n_indent = item[0]

            # write name
            if n_indent == 0:
                myfunc = darkgreen
            elif n_indent == 1:
                myfunc = blue
                myfunc_desc = darkgreen
            elif n_indent == 2:
                if not name.startswith("--"):
                    myfunc = red
                myfunc_desc = brown
            elif n_indent == 3:
                myfunc = darkblue
                myfunc_desc = purple
            func_out = myfunc(name)
            print_generic(func_out, end = "")

            # write desc
            if desc:
                while n_d_ident > 0:
                    n_d_ident -= 1
                    writechar("\t")
                desc = myfunc_desc(desc)
                print_generic(desc, end = "")
            writechar("\n")

def print_table(lines_data, cell_spacing = 2, cell_padding = 0,
    side_color = darkgreen):
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
        print_generic(side_color(">>") + " ", end = " ")
        if isinstance(cols, (list, tuple)):
            col_n = 0
            for cell in cols:
                max_len = column_sizes[col_n]
                cell = " "*padding_side + cell + " "*padding_side
                delta_len = max_len - len(decolorize(cell.split("\n")[0])) + \
                    cell_spacing
                if col_n == (len(cols) - 1):
                    print_generic(cell)
                else:
                    print_generic(cell, end = " "*delta_len)
                col_n += 1
        else:
            print_generic(cols)

def countdown(secs = 5, what = "Counting...", back = False):
    """
    Print countdown.

    @keyword secs: countdown seconds
    @type secs: int
    @keyword what: countdown text
    @type what: string
    @keyword back: write \n at the end if True
    @type back: bool
    """
    if secs:
        if back:
            try:
                print_generic(red(">>") + " " + what, end = "")
            except UnicodeEncodeError:
                print_generic(red(">>") + " " + what.encode('utf-8'),
                              end = "")
        else:
            print_generic(what)
        for i in range(secs)[::-1]:
            sys.stdout.write(purple(str(i+1)+" "))
            sys.stdout.flush()
            time.sleep(1)

def enlightenatom(atom):
    """
    Colorize package atoms with standard colors.

    @param atom: atom string
    @type atom: string
    @return: colorized string
    @rtype: string
    """
    entropy_rev = entropy.dep.dep_get_entropy_revision(atom)
    if entropy_rev is None:
        entropy_rev = ''
    else:
        entropy_rev = '~%s' % (str(entropy_rev),)
    entropy_tag = entropy.dep.dep_gettag(atom)
    if entropy_tag is None:
        entropy_tag = ''
    else:
        entropy_tag = '#%s' % (entropy_tag,)
    clean_atom = entropy.dep.remove_entropy_revision(atom)
    clean_atom = entropy.dep.remove_tag(clean_atom)
    only_cpv = entropy.dep.dep_getcpv(clean_atom)
    operator = clean_atom[:len(clean_atom)-len(only_cpv)]
    cat, name, pv, rev = entropy.dep.catpkgsplit(only_cpv)
    if rev == "r0":
        rev = ''
    else:
        rev = '-%s' % (rev,)
    return "%s%s%s%s%s%s%s" % (purple(operator), teal(cat + "/"),
        darkgreen(name), purple("-"+pv), purple(rev), brown(entropy_tag),
        teal(entropy_rev),)

def read_equo_release():
    """
    Read Equo release.

    @rtype: None
    @return: None
    """
    # handle Entropy Version
    revision_file = "../client/revision"
    if not os.path.isfile(revision_file):
        revision_file = os.path.join(etpConst['installdir'],
            'client/revision')
    if os.path.isfile(revision_file) and \
        os.access(revision_file, os.R_OK):

        with open(revision_file, "r") as rev_f:
            myrev = rev_f.readline().strip()
            return myrev

    return "0"

def get_file_mime(file_path):
    if not os.path.isfile(file_path):
        return None
    try:
        import magic
    except ImportError:
        return None
    handle = magic.open(magic.MAGIC_MIME)
    handle.load()
    mime = handle.file(file_path)
    handle.close()
    if mime:
        mime = mime.split(";")[0]
    return mime

def _transfer_callback(transfered, total, download):
    if download:
        action = _("Downloading")
    else:
        action = _("Uploading")

    percent = 100
    if (total > 0) and (transfered <= total):
        percent = int(round((float(transfered)/total) * 100, 1))

    msg = "[%s%s] %s ..." % (purple(str(percent)), "%", teal(action))
    print_info(msg, back = True)

def get_entropy_webservice(entropy_client, repository_id, tx_cb = False):
    """
    Get Entropy Web Services service object (ClientWebService).

    @param entropy_client: Entropy Client interface
    @type entropy_client: entropy.client.interfaces.Client
    @param repository_id: repository identifier
    @type repository_id: string
    @return: the ClientWebService instance
    @rtype: entropy.client.services.interfaces.ClientWebService
    @raise WebService.UnsupportedService: if service is unsupported by
        repository
    """
    factory = entropy_client.WebServices()
    webserv = factory.new(repository_id)
    if tx_cb:
        webserv._set_transfer_callback(_transfer_callback)
    return webserv

def print_package_info(package_id, entropy_client, entropy_repository,
    installed_search = False, strict_output = False, extended = False,
    quiet = False, show_repo_if_quiet = False, show_desc_if_quiet = False):
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
        entropy_client.output(
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
        pkginstalled = entropy_client.installed_repository().atomMatch(
            entropy.dep.dep_getkey(pkgatom), matchSlot = pkgslot)
        if pkginstalled[1] == 0:
            idx = pkginstalled[0]
            # found
            installed_ver = entropy_client.installed_repository(
                ).retrieveVersion(idx) or corrupted_str
            installed_tag = entropy_client.installed_repository(
                ).retrieveTag(idx)
            if not installed_tag:
                installed_tag = "NoTag"
            installed_rev = entropy_client.installed_repository(
                ).retrieveRevision(idx)
            if installed_rev is None:
                installed_rev = const_convert_to_unicode("0")
            else:
                installed_rev = const_convert_to_unicode(installed_rev)

    toc = []

    entropy_client.output(red("     @@ %s: " % (_("Package"),) ) + \
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
                entropy_client.Settings()['pkg_masking_reasons'].get(
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
            blue(str(pkgslot)),))

        if extended:
            pkgsize = entropy_repository.retrieveSize(package_id)
            pkgsize = entropy.tools.bytes_into_human(pkgsize)
            pkgbin = entropy_repository.retrieveDownloadURL(package_id)
            if pkgbin is None:
                pkgbin = corrupted_str
            pkgdigest = entropy_repository.retrieveDigest(package_id) or \
                corrupted_str
            pkgdeps = entropy_repository.retrieveDependencies(package_id,
                extended = True, resolve_conditional_deps = False)
            pkgconflicts = entropy_repository.retrieveConflicts(package_id)
            depsorter = lambda x: entropy.dep.dep_getcpv(x[0])

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
                dep_leg = show_dependencies_legend(entropy_client,
                    indent = "", get_data = True)
                toc.extend([(len_txt, x) for x in dep_leg])


            if pkgconflicts:
                toc.append(darkred("       ##") + " " + \
                    darkgreen("%s:" % (_("Conflicts"),) ))
                for conflict in sorted(pkgconflicts, key = depsorter):
                    toc.append(("       %s" % (darkred("##"),),
                        brown(conflict),))

    home_txt = "       %s:" % (_("Homepage"),)
    home_lines = _my_formatted_print(
        entropy_client, pkghome, "", "", color = brown,
        min_chars = 15, get_data = True)
    for home_line in home_lines:
        toc.append((darkgreen(home_txt), home_line,))
        home_txt = " "

    if not strict_output:

        desc_txt = "       %s:" % (_("Description"),)
        desc_lines = _my_formatted_print(
            entropy_client, pkgdesc, "", "", get_data = True)
        for desc_line in desc_lines:
            toc.append((darkgreen(desc_txt), purple(desc_line)))
            desc_txt = " "

        if extended:
            pkguseflags = entropy_repository.retrieveUseflags(package_id)
            use_txt = "       %s:" % (_("USE flags"),)
            use_lines = _my_formatted_print(
                entropy_client,
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
            keyword_lines = _my_formatted_print(
                entropy_client, pkgkeywords, "", "",
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

    print_table(toc, cell_spacing = 3)

def _my_formatted_print(entropy_client, data, header, reset_columns,
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
                entropy_client.output(desc_text)
            desc_text = reset_columns

    if fcount > 0:
        if get_data:
            out_data.append(desc_text)
        else:
            entropy_client.output(desc_text)

    if get_data:
        return out_data

def show_dependencies_legend(entropy_client, indent = '',
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
            entropy_client.output(txt)
    if get_data:
        return data

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

    _graph_to_stdout(entropy_client, graph, graph.get_node(inst_item),
        item_translation_func, show_already_pulled_in, quiet)
    if not quiet:
        _show_graph_legend(entropy_client)

    del stack
    graph.destroy()
    del graph
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
        ((pkg_id, repo_id,), was_dep, dep_type) = item

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
    del graph
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
