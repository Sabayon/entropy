# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""

import shutil
import commands
from entropy.const import *
from entropy.output import *
from entropy.client.interfaces import Client
Equo = Client() # client db must be available, it is for a reason!
from entropy.i18n import _

########################################################
####
##   Configuration Tools
#

def configurator(options):

    rc = 0
    if len(options) < 1:
        return -10

    # check if I am root
    if (not Equo.entropyTools.is_root()):
        mytxt = _("You are not root")
        print_error(red(mytxt+"."))
        return 1

    if options[0] == "info":
        rc = confinfo()
    elif options[0] == "update":
        rc = update()
    else:
        rc = -10

    return rc


'''
   @description: scan for files that need to be merged
   @output: dictionary using filename as key
'''
def update(cmd = None):
    cache_status = False
    docmd = False
    if cmd != None:
        docmd = True
    while 1:
        print_info(brown(" @@ ")+darkgreen("%s ..." % (_("Scanning filesystem"),)))
        scandata = Equo.FileUpdates.scanfs(dcache = cache_status)
        if cache_status:
            for x in scandata:
                print_info("("+blue(str(x))+") "+red(" %s: " % (_("file"),) )+etpConst['systemroot']+scandata[x]['destination'])
        cache_status = True

        if (not scandata):
            print_info(darkred(_("All fine baby. Nothing to do!")))
            break

        keys = scandata.keys()
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
                    Equo.FileUpdates.remove_from_cache(key)
                    scandata = Equo.FileUpdates.scandata
                    continue
                print_info(darkred("%s: " % (_("Configuration file"),) )+darkgreen(etpConst['systemroot']+scandata[key]['destination']))
                if cmd == -3:
                    rc = Equo.askQuestion(">>   %s" % (_("Overwrite ?"),) )
                    if rc == _("No"):
                        continue
                print_info(darkred("%s " % (_("Moving"),) )+darkgreen(etpConst['systemroot']+scandata[key]['source'])+darkred(" %s " % (_("to"),) )+brown(etpConst['systemroot']+scandata[key]['destination']))

                Equo.FileUpdates.merge_file(key)
                scandata = Equo.FileUpdates.scandata

            break

        elif cmd in (-7, -9):
            for key in keys:

                if not os.path.isfile(etpConst['systemroot']+scandata[key]['source']):

                    Equo.FileUpdates.remove_from_cache(key)
                    scandata = Equo.FileUpdates.scandata

                    continue
                print_info(darkred("%s: " % (_("Configuration file"),) )+darkgreen(etpConst['systemroot']+scandata[key]['destination']))
                if cmd == -7:
                    rc = Equo.askQuestion(">>   %s" % (_("Discard ?"),) )
                    if rc == _("No"):
                        continue
                print_info(darkred("%s " % (_("Discarding"),) )+darkgreen(etpConst['systemroot']+scandata[key]['source']))

                Equo.FileUpdates.remove_file(key)
                scandata = Equo.FileUpdates.scandata

            break

        elif cmd > 0:
            if scandata.get(cmd):

                # do files exist?
                if not os.path.isfile(etpConst['systemroot']+scandata[cmd]['source']):

                    Equo.FileUpdates.remove_from_cache(cmd)
                    scandata = Equo.FileUpdates.scandata

                    continue
                if not os.path.isfile(etpConst['systemroot']+scandata[cmd]['destination']):
                    print_info(darkred("%s: " % (_("Automerging file"),) )+darkgreen(etpConst['systemroot']+scandata[cmd]['source']))

                    Equo.FileUpdates.merge_file(cmd)
                    scandata = Equo.FileUpdates.scandata

                    continue
                # end check

                diff = showdiff(etpConst['systemroot']+scandata[cmd]['destination'],etpConst['systemroot']+scandata[cmd]['source'])
                if (not diff):
                    print_info(darkred("%s " % (_("Automerging file"),) )+darkgreen(etpConst['systemroot']+scandata[cmd]['source']))

                    Equo.FileUpdates.merge_file(cmd)
                    scandata = Equo.FileUpdates.scandata

                    continue

                mytxt = "%s: %s" % (
                    darkred(_("Selected file")),
                    darkgreen(etpConst['systemroot']+scandata[cmd]['source']),
                )
                print_info(mytxt)

                comeback = False
                while 1:
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

                        Equo.FileUpdates.merge_file(cmd)
                        scandata = Equo.FileUpdates.scandata

                        comeback = True
                        break

                    elif action == 2:
                        print_info(darkred("%s " % (_("Deleting file"),) ) + darkgreen(etpConst['systemroot'] + \
                            scandata[cmd]['source'])
                        )

                        Equo.FileUpdates.remove_file(cmd)
                        scandata = Equo.FileUpdates.scandata

                        comeback = True
                        break

                    elif action == 3:
                        print_info(darkred("%s " % (_("Editing file"),) ) + \
                            darkgreen(etpConst['systemroot']+scandata[cmd]['source'])
                        )

                        editor = Equo.get_file_editor()
                        if editor == None:
                            print_error(" %s" % (_("Cannot find a suitable editor. Can't edit file directly."),) )
                            comeback = True
                            break
                        else:
                            os.system(editor+" "+etpConst['systemroot']+scandata[cmd]['source'])

                        print_info(darkred("%s " % (_("Edited file"),) ) + darkgreen(etpConst['systemroot'] + \
                            scandata[cmd]['source']) + darkred(" - %s:" % (_("showing differencies"),) )
                        )
                        diff = showdiff(etpConst['systemroot'] + scandata[cmd]['destination'],etpConst['systemroot'] + \
                            scandata[cmd]['source'])
                        if not diff:
                            print_info(darkred("%s " % (_("Automerging file"),) ) + darkgreen(scandata[cmd]['source']))

                            Equo.FileUpdates.merge_file(cmd)
                            scandata = Equo.FileUpdates.scandata

                            comeback = True
                            break

                        continue

                    elif action == 4:
                        # show diffs again
                        diff = showdiff(etpConst['systemroot'] + scandata[cmd]['destination'], etpConst['systemroot'] + scandata[cmd]['source'])
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
    print_info("  ("+blue("4")+") "+darkred(_("Show differences again")))
    # wait user interaction
    action = readtext(_("Your choice (type a number and press enter):")+" ")
    return action

def showdiff(fromfile,tofile):
    # run diff
    diffcmd = "diff -Nu "+fromfile+" "+tofile #+" | less --no-init --QUIT-AT-EOF"
    output = commands.getoutput(diffcmd).split("\n")
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
	coloured.append(line+"\n")
    f = open("/tmp/"+os.path.basename(fromfile),"w")
    f.writelines(coloured)
    f.flush()
    f.close()
    print
    os.system("cat \"%s\" | less --no-init --QUIT-AT-EOF" % ("/tmp/"+os.path.basename(fromfile),))
    try:
	os.remove("/tmp/"+os.path.basename(fromfile))
    except OSError:
	pass
    if output == ['']: output = [] #FIXME beautify
    return output


'''
   @description: prints information about config files that should be updated
'''
def confinfo():
    print_info(brown(" @@ ")+darkgreen(_("These are the files that would be updated:")))
    data = Equo.FileUpdates.scanfs(dcache = False)
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
