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
if sys.hexversion >= 0x3000000:
    from subprocess import getoutput
else:
    from commands import getoutput

from entropy.const import etpConst
from entropy.output import red, darkred, brown, green, darkgreen, blue, \
    purple, darkblue, print_info, print_error, print_warning, readtext
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
        if cmd == "info":
            rc = confinfo(etp_client)
        elif cmd == "update":
            rc = update(etp_client)
        else:
            rc = -10
    finally:
        if acquired and (etp_client is not None):
            entropy.tools.release_entropy_locks(etp_client)
        if etp_client is not None:
            etp_client.shutdown()

    return rc


'''
   @description: scan for files that need to be merged
   @output: dictionary using filename as key
'''
def update(entropy_client, cmd = None):

    cache_status = False
    docmd = False
    if cmd != None:
        docmd = True

    file_updates = entropy_client.PackageFileUpdates()
    while True:
        print_info(brown(" @@ ") + \
            darkgreen("%s ..." % (_("Scanning filesystem"),)))
        scandata = file_updates.scan(dcache = cache_status)
        if cache_status:
            for x in scandata:
                print_info("("+blue(str(x))+") "+red(" %s: " % (_("file"),) ) + \
                    etpConst['systemroot'] + scandata[x]['destination'])
        cache_status = True

        if (not scandata):
            print_info(darkred(_("All fine baby. Nothing to do!")))
            break

        keys = list(scandata.keys())
        if not docmd:
            cmd = selfile()
        else:
            docmd = False
        try:
            cmd = int(cmd)
        except:
            print_error(_("Type a number."))
            continue

        # actions
        if cmd == -1:
            # exit
            return -1
        elif cmd in (-3, -5):
            # automerge files asking one by one
            for key in keys:
                if not os.path.isfile(etpConst['systemroot']+scandata[key]['source']):
                    file_updates.ignore(key)
                    scandata = file_updates.scan()
                    continue
                print_info(darkred("%s: " % (_("Configuration file"),) ) + \
                    darkgreen(etpConst['systemroot']+scandata[key]['destination']))
                if cmd == -3:
                    rc = entropy_client.ask_question(
                        ">>   %s" % (_("Overwrite ?"),) )
                    if rc == _("No"):
                        continue
                print_info(darkred("%s " % (_("Moving"),) ) + \
                    darkgreen(etpConst['systemroot'] + \
                    scandata[key]['source']) + \
                    darkred(" %s " % (_("to"),) ) + \
                    brown(etpConst['systemroot'] + \
                    scandata[key]['destination']))

                file_updates.merge(key)
                scandata = file_updates.scan()

            break

        elif cmd in (-7, -9):
            for key in keys:

                if not os.path.isfile(etpConst['systemroot']+scandata[key]['source']):
                    file_updates.ignore(key)
                    scandata = file_updates.scan()
                    continue

                print_info(darkred("%s: " % (_("Configuration file"),) ) + \
                    darkgreen(etpConst['systemroot']+scandata[key]['destination']))
                if cmd == -7:
                    rc = entropy_client.ask_question(
                        ">>   %s" % (_("Discard ?"),) )
                    if rc == _("No"):
                        continue
                print_info(darkred("%s " % (_("Discarding"),) ) + \
                    darkgreen(etpConst['systemroot']+scandata[key]['source']))

                file_updates.remove(key)
                scandata = file_updates.scan()

            break

        elif cmd > 0:
            if scandata.get(cmd):

                # do files exist?
                if not os.path.isfile(etpConst['systemroot']+scandata[cmd]['source']):

                    file_updates.ignore(cmd)
                    scandata = file_updates.scan()

                    continue
                if not os.path.isfile(etpConst['systemroot']+scandata[cmd]['destination']):
                    print_info(darkred("%s: " % (_("Automerging file"),) ) + \
                        darkgreen(etpConst['systemroot']+scandata[cmd]['source']))

                    file_updates.merge(cmd)
                    scandata = file_updates.scan()
                    continue

                # end check

                diff = showdiff(etpConst['systemroot']+scandata[cmd]['destination'],
                    etpConst['systemroot']+scandata[cmd]['source'])
                if (not diff):
                    print_info(darkred("%s " % (_("Automerging file"),) ) + \
                        darkgreen(etpConst['systemroot']+scandata[cmd]['source']))

                    file_updates.merge(cmd)
                    scandata = file_updates.scan()

                    continue

                mytxt = "%s: %s" % (
                    darkred(_("Selected file")),
                    darkgreen(etpConst['systemroot']+scandata[cmd]['source']),
                )
                print_info(mytxt)

                comeback = False
                while True:
                    action = selaction()
                    try:
                        action = int(action)
                    except:
                        print_error(_("You don't have typed a number."))
                        continue

                    # actions handling
                    if action == -1:
                        comeback = True
                        break
                    elif action == 1:
                        print_info(darkred("%s " % (_("Replacing"),) ) + darkgreen(etpConst['systemroot'] + \
                            scandata[cmd]['destination']) + darkred(" %s " % (_("with"),) ) + \
                            darkgreen(etpConst['systemroot'] + scandata[cmd]['source']))

                        file_updates.merge(cmd)
                        scandata = file_updates.scan()

                        comeback = True
                        break

                    elif action == 2:
                        print_info(darkred("%s " % (_("Deleting file"),) ) + \
                            darkgreen(etpConst['systemroot'] + \
                            scandata[cmd]['source'])
                        )

                        file_updates.remove(cmd)
                        scandata = file_updates.scan()

                        comeback = True
                        break

                    elif action == 3:
                        print_info(darkred("%s " % (_("Editing file"),) ) + \
                            darkgreen(etpConst['systemroot']+scandata[cmd]['source'])
                        )

                        entropy_client.edit_file(
                            etpConst['systemroot']+scandata[cmd]['source'])

                        print_info(darkred("%s " % (_("Edited file"),) ) + darkgreen(etpConst['systemroot'] + \
                            scandata[cmd]['source']) + darkred(" - %s:" % (_("showing differencies"),) )
                        )
                        diff = showdiff(etpConst['systemroot'] + scandata[cmd]['destination'], etpConst['systemroot'] + \
                            scandata[cmd]['source'])
                        if not diff:
                            print_info(darkred("%s " % (_("Automerging file"),) ) + \
                                darkgreen(scandata[cmd]['source']))

                            file_updates.merge(cmd)
                            scandata = file_updates.scan()

                            comeback = True
                            break

                        continue

                    elif action == 4:
                        source = etpConst['systemroot']+scandata[cmd]['source']
                        dest = etpConst['systemroot']+scandata[cmd]['destination']
                        print_info(darkred("%s " % (_("Interactively merge"),) ) + \
                            darkgreen(source)
                        )
                        merge_outcome_path, exit_status = interactive_merge(
                            source, dest)
                        if exit_status in (2, 130):
                            # quit
                            continue
                        else: # ok
                            try:
                                os.rename(merge_outcome_path, source)
                            except OSError:
                                shutil.move(merge_outcome_path, source)
                            file_updates.merge(cmd)
                            scandata = file_updates.scan()

                            comeback = True
                            break

                    elif action == 5:
                        # show diffs again
                        diff = showdiff(etpConst['systemroot'] + scandata[cmd]['destination'],
                            etpConst['systemroot'] + scandata[cmd]['source'])
                        continue

                if (comeback):
                    continue

                break

'''
   @description: show files commands and let the user to choose
   @output: action number
'''
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

'''
   @description: show actions for a chosen file
   @output: action number
'''
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
            line = red(line)
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
    except OSError:
        if err.errno != errno.ENOENT:
            raise
        rc = 2
        os.remove(tmp_path)
    finally:
        os.close(tmp_fd)

    return tmp_path, rc

'''
   @description: prints information about config files that should be updated
'''
def confinfo(entropy_client):
    print_info(brown(" @@ ")+darkgreen(_("These are the files that would be updated:")))
    data = entropy_client.PackageFileUpdates().scan(dcache = False)
    counter = 0
    for item in data:
        counter += 1
        print_info(" ("+blue(str(counter))+") "+"[auto:"+str(data[item]['automerge'])+"]"+red(" %s: " % (_("file"),) )+str(item))
    print_info(red(" @@ ")+brown("%s:\t\t" % (_("Unique files that would be update"),) )+red(str(len(data))))
    automerge = 0
    for x in data:
        if data[x]['automerge']:
            automerge += 1
    print_info(red(" @@ ")+brown("%s:\t\t" % (_("Unique files that would be automerged"),) )+green(str(automerge)))
    return 0
