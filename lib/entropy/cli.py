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
                print_generic(red(">>") + " " + what.encode('utf-8'), end = "")
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
    home_lines = _my_formatted_print(pkghome, "", "", color = brown,
        min_chars = 15, get_data = True)
    for home_line in home_lines:
        toc.append((darkgreen(home_txt), home_line,))
        home_txt = " "

    if not strict_output:

        desc_txt = "       %s:" % (_("Description"),)
        desc_lines = _my_formatted_print(pkgdesc, "", "", get_data = True)
        for desc_line in desc_lines:
            toc.append((darkgreen(desc_txt), purple(desc_line)))
            desc_txt = " "

        if extended:
            pkguseflags = entropy_repository.retrieveUseflags(package_id)
            use_txt = "       %s:" % (_("USE flags"),)
            use_lines = _my_formatted_print(
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
            keyword_lines = _my_formatted_print(pkgkeywords, "", "",
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

def _my_formatted_print(data, header, reset_columns, min_chars = 25,
    color = None, get_data = False):

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
                print_info(desc_text)
            desc_text = reset_columns

    if fcount > 0:
        if get_data:
            out_data.append(desc_text)
        else:
            print_info(desc_text)

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
