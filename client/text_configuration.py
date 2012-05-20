# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
import os
import errno
import sys
import shutil
import tempfile
import subprocess

from entropy.const import const_is_python3

if const_is_python3():
    from subprocess import getoutput
else:
    from commands import getoutput

from entropy.const import etpConst
from entropy.output import red, darkred, brown, green, darkgreen, blue, \
    purple, teal, darkblue, print_info, print_error, print_warning, \
    readtext
from entropy.i18n import _

import entropy.tools


def configurator(options):

    rc = 0
    if not options:
        return -10

    # check if I am root
    if not entropy.tools.is_root():
        mytxt = _("You are not root")
        print_error(red(mytxt+"."))
        return 1

    from entropy.client.interfaces import Client
    etp_client = None
    acquired = False
    try:
        etp_client = Client()
        acquired = entropy.tools.acquire_entropy_locks(etp_client)
        if not acquired:
            print_error(darkgreen(_("Another Entropy is currently running.")))
            return 1

        cmd = options.pop(0)
        if cmd == "update":
            rc = update(etp_client)
        else:
            rc = -10
    finally:
        if acquired and (etp_client is not None):
            entropy.tools.release_entropy_locks(etp_client)
        if etp_client is not None:
            etp_client.shutdown()

    return rc


def update(entropy_client, cmd = None):

    docmd = False
    if cmd != None:
        docmd = True

    updates = entropy_client.ConfigurationUpdates()
    paths_map = {}
    first_pass = True

    while True:
        print_info(brown(" @@ ") + \
            darkgreen("%s ..." % (_("Scanning filesystem"),)))

        scandata = updates.get()
        if not scandata:
            print_info(darkred(_("All fine baby. Nothing to do!")))
            break
        root = scandata.root()

        if first_pass:
            paths_map.update(dict(enumerate(sorted(scandata.keys()), 1)))
        first_pass = False

        for idx in sorted(paths_map.keys()):
            x = paths_map[idx]
            try:
                obj = scandata[x]
            except KeyError:
                # duplicated entry?
                del paths_map[idx]
                continue
            file_path = root + obj['destination']
            print_info(
                "(" + blue(str(idx)) + ") " + \
                    red(" %s: " % (_("file"),) ) + \
                x)

        if not paths_map:
            print_info(darkred(_("All fine baby. Nothing to do!")))
            break

        if not docmd:
            cmd = selfile()
        else:
            docmd = False
        try:
            cmd = int(cmd)
        except:
            print_error(_("Type a number"))
            continue

        # actions
        if cmd == -1:
            # exit
            return -1

        elif cmd in (-3, -5):
            # automerge files asking one by one
            _automerge(cmd, entropy_client, root, paths_map, scandata)
            break

        elif cmd in (-7, -9):
            _autodiscard(cmd, entropy_client, root, paths_map, scandata)
            break

        elif cmd > 0:
            if _handle_command(
                cmd, entropy_client, root, paths_map, scandata):
                continue
            break

def _handle_command(idx, entropy_client, root, paths_map, scandata):
    """
    Execute > 0 commands.
    """
    try:
        source = paths_map[idx]
    except KeyError:
        return True

    source_path = root + source
    if not scandata.exists(source):
        print_info(
            "%s: %s" % (
                darkred(_("Discarding")),
                teal(source_path),)
            )
        scandata.remove(source)
        del paths_map[idx]
        return True

    dest = scandata[source]['destination']
    dest_path = root + dest
    if not scandata.exists(dest):
        print_info(
            "%s: %s" % (
                darkred(_("Automerging")),
                teal(source_path),)
            )
        scandata.merge(source)
        del paths_map[idx]
        return True

    diff = showdiff(dest_path, source_path)
    if not diff:
        print_info(
            "%s: %s" % (
                darkred(_("Automerging")),
                teal(source_path),)
            )
        scandata.merge(source)
        del paths_map[idx]
        return True

    mytxt = "%s: %s" % (
        darkred(_("Selected file")),
        darkgreen(source_path),
    )
    print_info(mytxt)

    comeback = False
    while True:
        action = selaction()
        try:
            action = int(action)
        except:
            print_error(_("Type a number"))
            continue

        # actions handling
        if action == -1:
            comeback = True
            break

        elif action == 1:
            print_info(
                _("Replacing %s with %s") % (
                    darkgreen(dest_path),
                    darkred(source_path),))

            merged = scandata.merge(source)
            if not merged:
                print_warning(
                    _("Cannot merge %s") % (
                        darkred(source_path),))
            del paths_map[idx]
            comeback = True
            break

        elif action == 2:
            print_info(
                _("Deleting %s") % (
                    darkgreen(source_path),))

            removed = scandata.remove(source)
            if not removed:
                print_warning(
                    _("Cannot remove %s") % (
                        darkred(source_path),))
            del paths_map[idx]
            comeback = True
            break

        elif action == 3:
            comeback, _continue = _edit_file(
                idx, entropy_client, root, source, dest,
                paths_map, scandata)
            if _continue:
                continue
            break

        elif action == 4:
            comeback, _continue = _interactive_merge(
                idx, entropy_client, root, source, dest,
                paths_map, scandata)
            if _continue:
                continue
            break

        elif action == 5:
            # show diff again
            diff = showdiff(dest_path, source_path)
            continue

    if comeback:
        return True
    return False

def _interactive_merge(idx, entropy_client, root, source, dest,
               paths_map, scandata):
    """
    Interactively merge config file.
    """
    source_path = root + source
    dest_path = root + dest

    print_info(
        "%s: %s" % (
            darkred(_("Interactive merge")),
            darkgreen(source_path),)
        )

    merge_outcome_path, exit_status = interactive_merge(
        source_path, dest_path)
    if exit_status in (2, 130):
        # quit
        return False, True

    try:
        entropy.tools.rename_keep_permissions(
            merge_outcome_path, source_path)
    except OSError as err:
        print_error(
            "%s: %s" % (
                darkred(_("OSError during interactive merge")),
                repr(err),))
        return False, True
    except IOError as err:
        print_error(
            "%s: %s" % (
                darkred(_("IOError during interactive merge")),
                repr(err),))
        return False, True

    merged = scandata.merge(source)
    del paths_map[idx]
    if not merged:
        print_error(
            "%s: %s" % (
                darkred(_("Unable to merge file")),
                darkgreen(source_path),))
    return True, False


def _edit_file(idx, entropy_client, root, source, dest,
               paths_map, scandata):
    """
    Edit the given source file.
    """
    source_path = root + source
    dest_path = root + dest

    print_info(
        "%s: %s" % (
            darkred(_("Editing file")),
            darkgreen(source_path),))

    entropy_client.edit_file(source_path)

    print_info(
        "%s: %s, %s" % (
            darkred(_("Edited file")),
            darkgreen(source_path),
            darkred(_("showing difference")))
        )

    diff = showdiff(dest_path, source_path)
    if not diff:
        print_info(
            "%s: %s" % (
                darkred(_("Automerging")),
                teal(source_path),)
            )
        scandata.merge(source)
        del paths_map[idx]
        return True, False

    return False, True

def _automerge(cmd, entropy_client, root, paths_map, scandata):
    """
    Execute -3 and -5 actions.
    """
    idxs = sorted(paths_map.keys())
    for idx in idxs:
        _merge(cmd, entropy_client, root, paths_map, idx, scandata)

def _merge(cmd, entropy_client, root, paths_map, idx, scandata):
    """
    Execute the config file merge action.
    """
    try:
        source = paths_map[idx]
    except KeyError:
        # idiot
        return

    data = scandata.get(source)
    if data is None:
        return

    source_path = root + source
    destination_path = root + data['destination']

    print_info(
        "%s: %s" % (
            darkred(_("Source file")),
            teal(source_path),)
    )
    print_info(
        "%s: %s" % (
            darkred(_("Destination file")),
            purple(destination_path),)
    )
    if cmd == -3:
        rc = entropy_client.ask_question(
            ">>   %s" % (_("Overwrite ?"),) )
        if rc == _("No"):
            return

    merged = scandata.merge(source)
    del paths_map[idx]
    if not merged:
        print_warning(
            "%s: %s" % (
                darkred(_("Cannot merge")),
                brown(source_path),))

    print_info("--")

def _autodiscard(cmd, entropy_client, root, paths_map, scandata):
    """
    Execute -7 and -9 actions.
    """
    idxs = sorted(paths_map.keys())
    for idx in idxs:
        _discard(cmd, entropy_client, root, paths_map, idx, scandata)

def _discard(cmd, entropy_client, root, paths_map, idx, scandata):
    """
    Execute the config file discard action.
    """
    try:
        source = paths_map[idx]
    except KeyError:
        # idiot
        return

    data = scandata.get(source)
    if data is None:
        return

    source_path = root + source
    destination_path = root + data['destination']

    print_info(
        "%s: %s" % (
            darkred(_("Source file")),
            teal(source_path),)
    )
    print_info(
        "%s: %s" % (
            darkred(_("Destination file")),
            purple(destination_path),)
    )
    if cmd == -3:
        rc = entropy_client.ask_question(
            ">>   %s" % (_("Discard ?"),) )
        if rc == _("No"):
            return

    print_info(
        "%s: %s" % (
            darkred(_("Discarding")),
            teal(source_path),)
    )

    removed = scandata.remove(source)
    del paths_map[idx]
    if not removed:
        print_warning(
            "%s: %s" % (
                darkred(_("Cannot remove")),
                brown(source_path),))

    print_info("--")

def selfile():
    print_info(darkred(_("Please choose a file to update by typing its identification number.")))
    print_info(darkred(_("Other options are:")))
    print_info("  ("+blue("-1")+") "+darkgreen(_("Exit")))
    print_info("  ("+blue("-3")+") "+brown(_("Automerge all the files asking you one by one")))
    print_info("  ("+blue("-5")+") "+darkred(_("Automerge all the files without questioning")))
    print_info("  ("+blue("-7")+") "+brown(_("Discard all the files asking you one by one")))
    print_info("  ("+blue("-9")+") "+darkred(_("Discard all the files without questioning")))
    # wait user interaction
    action = readtext(_("Your choice (type a number and press enter):")+" ")
    return action


def selaction():
    print_info(darkred(_("Please choose an action to take for the selected file.")))
    print_info("  ("+blue("-1")+") "+darkgreen(_("Come back to the files list")))
    print_info("  ("+blue("1")+") "+brown(_("Replace original with update")))
    print_info("  ("+blue("2")+") "+darkred(_("Delete update, keeping original as is")))
    print_info("  ("+blue("3")+") "+brown(_("Edit proposed file and show diffs again")))
    print_info("  ("+blue("4")+") "+brown(_("Interactively merge original with update")))
    print_info("  ("+blue("5")+") "+darkred(_("Show differences again")))
    # wait user interaction
    action = readtext(_("Your choice (type a number and press enter):")+" ")
    return action

def showdiff(fromfile, tofile):

    args = ["diff", "-Nu", "'"+fromfile+"'", "'"+tofile+"'"]
    output = getoutput(' '.join(args)).split("\n")

    coloured = []
    for line in output:
        if line.startswith("---"):
            line = darkred(line)
        elif line.startswith("+++"):
            line = darkgreen(line)
        elif line.startswith("@@"):
            line = brown(line)
        elif line.startswith("-"):
            line = blue(line)
        elif line.startswith("+"):
            line = darkgreen(line)
        coloured.append(line + "\n")

    fd, tmp_path = tempfile.mkstemp()
    with os.fdopen(fd, "w") as f:
        f.writelines(coloured)
        f.flush()

    print("")
    pager = os.getenv("PAGER", "/usr/bin/less")
    if os.access(pager, os.X_OK):
        if pager == "/usr/bin/less":
            args = [pager, "-R", "--no-init", "--QUIT-AT-EOF", tmp_path]
        else:
            args = [pager, tmp_path]
    else:
        args = ["/bin/cat", tmp_path]
    try:
        subprocess.call(args)
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise
        args = ["/bin/cat", tmp_path]
        subprocess.call(args)

    os.remove(tmp_path)

    if output == ['']:
        return []
    return output

def interactive_merge(source, destination):
    tmp_fd, tmp_path = tempfile.mkstemp()
    args = ("/usr/bin/sdiff", "-o", tmp_path, source, destination)
    try:
        rc = subprocess.call(args)
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise
        rc = 2
        os.remove(tmp_path)
    finally:
        os.close(tmp_fd)
    return tmp_path, rc
