
#!/usr/bin/python
'''
    # DESCRIPTION:
    # Packages configuration files handling function (etc-update alike)

    Copyright (C) 2007-2008 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

import shutil
import commands
from entropyConstants import *
from outputTools import *
import exceptionTools
from entropy import EquoInterface
Equo = EquoInterface() # client db must be available, it is for a reason!

# test if diff is installed
difftest = Equo.entropyTools.spawnCommand("diff -v", redirect = "&> /dev/null")
if (difftest):
    raise exceptionTools.FileNotFound("FileNotFound: can't find diff")

########################################################
####
##   Configuration Tools
#

def configurator(options):

    rc = 0
    if len(options) < 1:
        return -10

    # check if I am root
    if (not Equo.entropyTools.isRoot()):
        print_error(red("You are not ")+bold("root")+red("."))
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
    while 1:
        print_info(yellow(" @@ ")+darkgreen("Scanning filesystem..."))
        scandata = Equo.FileUpdates.scanfs(dcache = cache_status)
        if (cache_status):
            for x in scandata:
                print_info("("+blue(str(x))+") "+red(" file: ")+etpConst['systemroot']+scandata[x]['destination'])
        cache_status = True

        if (not scandata):
            print_info(darkred("All fine baby. Nothing to do!"))
            break

        keys = scandata.keys()
        if not cmd:
            cmd = selfile()
        try:
            cmd = int(cmd)
        except:
            print_error("Type a number.")
            continue

        # actions
        if cmd == -1:
            # exit
            return -1
        elif cmd in (-3,-5):
            # automerge files asking one by one
            for key in keys:
                if not os.path.isfile(etpConst['systemroot']+scandata[key]['source']):
                    scandata = Equo.FileUpdates.remove_from_cache(scandata,key)
                    continue
                print_info(darkred("Configuration file: ")+darkgreen(etpConst['systemroot']+scandata[key]['destination']))
                if cmd == -3:
                    rc = Equo.askQuestion(">>   Overwrite ?")
                    if rc == "No":
                        continue
                print_info(darkred("Moving ")+darkgreen(etpConst['systemroot']+scandata[key]['source'])+darkred(" to ")+brown(etpConst['systemroot']+scandata[key]['destination']))

                # old file backup
                if etpConst['filesbackup'] and os.path.isfile(etpConst['systemroot']+scandata[key]['destination']):
                    bcount = 0
                    backupfile = etpConst['systemroot']+os.path.dirname(scandata[key]['destination'])+"/._equo_backup."+unicode(bcount)+"_"+os.path.basename(scandata[key]['destination'])
                    while os.path.lexists(backupfile):
                        bcount += 1
                        backupfile = etpConst['systemroot']+os.path.dirname(scandata[key]['destination'])+"/._equo_backup."+unicode(bcount)+"_"+os.path.basename(scandata[key]['destination'])
                    try:
                        shutil.copy2(etpConst['systemroot']+scandata[key]['destination'],backupfile)
                    except IOError:
                        pass

                shutil.move(etpConst['systemroot']+scandata[key]['source'],etpConst['systemroot']+scandata[key]['destination'])
                # remove from cache
                scandata = Equo.FileUpdates.remove_from_cache(scandata,key)
            break

        elif cmd in (-7,-9):
            for key in keys:

                if not os.path.isfile(etpConst['systemroot']+scandata[key]['source']):
                    scandata = Equo.FileUpdates.remove_from_cache(scandata,key)
                    continue
                print_info(darkred("Configuration file: ")+darkgreen(etpConst['systemroot']+scandata[key]['destination']))
                if cmd == -7:
                    rc = Equo.askQuestion(">>   Discard ?")
                    if rc == "No":
                        continue
                print_info(darkred("Discarding ")+darkgreen(etpConst['systemroot']+scandata[key]['source']))
                try:
                    os.remove(etpConst['systemroot']+scandata[key]['source'])
                except:
                    pass
                scandata = Equo.FileUpdates.remove_from_cache(scandata,key)

            break

        elif cmd > 0:
            if scandata.get(cmd):

                # do files exist?
                if not os.path.isfile(etpConst['systemroot']+scandata[cmd]['source']):
                    scandata = Equo.FileUpdates.remove_from_cache(scandata,key)
                    continue
                if not os.path.isfile(etpConst['systemroot']+scandata[cmd]['destination']):
                    print_info(darkred("Automerging file: ")+darkgreen(etpConst['systemroot']+scandata[cmd]['source']))
                    shutil.move(etpConst['systemroot']+scandata[key]['source'],etpConst['systemroot']+scandata[key]['destination'])
                    scandata = Equo.FileUpdates.remove_from_cache(scandata,key)
                    continue
                # end check

                diff = showdiff(etpConst['systemroot']+scandata[cmd]['destination'],etpConst['systemroot']+scandata[cmd]['source'])
                if (not diff):
                    print_info(darkred("Automerging file ")+darkgreen(etpConst['systemroot']+scandata[cmd]['source']))
                    shutil.move(etpConst['systemroot']+scandata[cmd]['source'],etpConst['systemroot']+scandata[cmd]['destination'])
                    scandata = Equo.FileUpdates.remove_from_cache(scandata,key)
                    continue
                print_info(darkred("Selected file: ")+darkgreen(etpConst['systemroot']+scandata[cmd]['source']))

                comeback = False
                while 1:
                    action = selaction()
                    try:
                        action = int(action)
                    except:
                        print_error("You don't have typed a number.")
                        continue

                    # actions handling
                    if action == -1:
                        comeback = True
                        break
                    elif action == 1:
                        print_info(darkred("Replacing ")+darkgreen(etpConst['systemroot']+scandata[cmd]['destination'])+darkred(" with ")+darkgreen(etpConst['systemroot']+scandata[cmd]['source']))

                        # old file backup
                        if etpConst['filesbackup'] and os.path.isfile(etpConst['systemroot']+scandata[cmd]['destination']):
                            bcount = 0
                            backupfile = etpConst['systemroot']+os.path.dirname(scandata[cmd]['destination'])+"/._equo_backup."+unicode(bcount)+"_"+os.path.basename(scandata[cmd]['destination'])
                            while os.path.lexists(backupfile):
                                bcount += 1
                                backupfile = etpConst['systemroot']+os.path.dirname(scandata[cmd]['destination'])+"/._equo_backup."+unicode(bcount)+"_"+os.path.basename(scandata[cmd]['destination'])
                            try:
                                shutil.copy2(etpConst['systemroot']+scandata[cmd]['destination'],backupfile)
                            except IOError:
                                pass

                        shutil.move(etpConst['systemroot']+scandata[cmd]['source'],etpConst['systemroot']+scandata[cmd]['destination'])
                        scandata = Equo.FileUpdates.remove_from_cache(scandata,cmd)
                        comeback = True
                        break

                    elif action == 2:
                        print_info(darkred("Deleting file ")+darkgreen(etpConst['systemroot']+scandata[cmd]['source']))
                        try:
                            os.remove(etpConst['systemroot']+scandata[cmd]['source'])
                        except:
                            pass
                        scandata = Equo.FileUpdates.remove_from_cache(scandata,cmd)
                        comeback = True
                        break

                    elif action == 3:
                        print_info(darkred("Editing file ")+darkgreen(etpConst['systemroot']+scandata[cmd]['source']))
                        if os.getenv("EDITOR"):
                            os.system("$EDITOR "+etpConst['systemroot']+scandata[cmd]['source'])
                        elif os.access("/bin/nano",os.X_OK):
                            os.system("/bin/nano "+etpConst['systemroot']+scandata[cmd]['source'])
                        elif os.access("/bin/vi",os.X_OK):
                            os.system("/bin/vi "+etpConst['systemroot']+scandata[cmd]['source'])
                        elif os.access("/usr/bin/vi",os.X_OK):
                            os.system("/usr/bin/vi "+etpConst['systemroot']+scandata[cmd]['source'])
                        elif os.access("/usr/bin/emacs",os.X_OK):
                            os.system("/usr/bin/emacs "+etpConst['systemroot']+scandata[cmd]['source'])
                        elif os.access("/bin/emacs",os.X_OK):
                            os.system("/bin/emacs "+etpConst['systemroot']+scandata[cmd]['source'])
                        else:
                            print_error(" Cannot find a suitable editor. Can't edit file directly.")
                            comeback = True
                            break
                        print_info(darkred("Edited file ")+darkgreen(etpConst['systemroot']+scandata[cmd]['source'])+darkred(" - showing differencies:"))
                        diff = showdiff(etpConst['systemroot']+scandata[cmd]['destination'],etpConst['systemroot']+scandata[cmd]['source'])
                        if (not diff):
                            print_info(darkred("Automerging file ")+darkgreen(scandata[cmd]['source']))
                            shutil.move(etpConst['systemroot']+scandata[cmd]['source'],etpConst['systemroot']+scandata[cmd]['destination'])
                            scandata = Equo.FileUpdates.remove_from_cache(scandata, cmd)
                            comeback = True
                            break

                        continue

                    elif action == 4:
                        # show diffs again
                        diff = showdiff(etpConst['systemroot']+scandata[cmd]['destination'],etpConst['systemroot']+scandata[cmd]['source'])
                        continue

                if (comeback):
                    continue

                break

'''
   @description: show files commands and let the user to choose
   @output: action number
'''
def selfile():
    print_info(darkred("Please choose a file to update by typing its identification number."))
    print_info(darkred("Other options are:"))
    print_info("  ("+blue("-1")+")"+darkgreen(" Exit"))
    print_info("  ("+blue("-3")+")"+brown(" Automerge all the files asking you one by one"))
    print_info("  ("+blue("-5")+")"+darkred(" Automerge all the files without questioning"))
    print_info("  ("+blue("-7")+")"+brown(" Discard all the files asking you one by one"))
    print_info("  ("+blue("-9")+")"+darkred(" Discard all the files without questioning"))
    # wait user interaction
    action = readtext("Your choice (type a number and press enter): ")
    return action

'''
   @description: show actions for a chosen file
   @output: action number
'''
def selaction():
    print_info(darkred("Please choose an action to take for the selected file."))
    print_info("  ("+blue("-1")+")"+darkgreen(" Come back to the files list"))
    print_info("  ("+blue("1")+")"+brown(" Replace original with update"))
    print_info("  ("+blue("2")+")"+darkred(" Delete update, keeping original as is"))
    print_info("  ("+blue("3")+")"+brown(" Edit proposed file and show diffs again"))
    print_info("  ("+blue("4")+")"+darkred(" Show differences again"))
    # wait user interaction
    action = readtext("Your choice (type a number and press enter): ")
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
    os.system("cat /tmp/"+os.path.basename(fromfile)+" | less --no-init --QUIT-AT-EOF")
    try:
	os.remove("/tmp/"+os.path.basename(fromfile))
    except:
	pass
    if output == ['']: output = [] #FIXME beautify
    return output


'''
   @description: prints information about config files that should be updated
'''
def confinfo():
    print_info(yellow(" @@ ")+darkgreen("These are the files that would be updated:"))
    data = Equo.FileUpdates.scanfs(dcache = False)
    counter = 0
    for item in data:
	counter += 1
	print_info(" ("+blue(str(counter))+") "+"[auto:"+str(data[item]['automerge'])+"]"+red(" file: ")+str(item))
    print_info(red(" @@ ")+brown("Unique files that would be update:\t\t")+red(str(len(data))))
    automerge = 0
    for x in data:
	if data[x]['automerge']:
	    automerge += 1
    print_info(red(" @@ ")+brown("Unique files that would be automerged:\t\t")+green(str(automerge)))
    return 0
