# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Client text-based tools}.

"""
import sys
import os
import time
import subprocess

from entropy.const import etpConst
from entropy.output import print_info, print_generic, writechar, blue, red, \
    brown, darkblue, purple, teal, darkgreen, decolorize
from entropy.i18n import _

import entropy.tools

# Temporary files cleaner
def cleanup(directories = None):

    if not directories:
        directories = [etpConst['packagestmpdir'], etpConst['logdir']]

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
    padding_side = cell_padding / 2
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
    entropy_rev = entropy.tools.dep_get_entropy_revision(atom)
    if entropy_rev is None:
        entropy_rev = ''
    else:
        entropy_rev = '~%s' % (str(entropy_rev),)
    entropy_tag = entropy.tools.dep_gettag(atom)
    if entropy_tag is None:
        entropy_tag = ''
    else:
        entropy_tag = '#%s' % (entropy_tag,)
    clean_atom = entropy.tools.remove_entropy_revision(atom)
    clean_atom = entropy.tools.remove_tag(clean_atom)
    only_cpv = entropy.tools.dep_getcpv(clean_atom)
    operator = entropy.tools.get_operator(clean_atom)
    if operator is None:
        operator = ''
    cat, name, pv, rev = entropy.tools.catpkgsplit(only_cpv)
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
