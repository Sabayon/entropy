#!/usr/bin/python
'''
    # DESCRIPTION:
    # Packages configuration files handling function (etc-update alike)

    Copyright (C) 2007 Fabio Erculiani

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

from commands import getoutput
import shutil
from entropyConstants import *
from clientConstants import *
from outputTools import *
import exceptionTools
from equoInterface import EquoInterface
# FIXME: move all print_* to EquoInterface.updateProgress
Equo = EquoInterface()

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
def update():
    cache_status = False
    Text = TextInterface()
    while 1:
        scandata = scanfs(dcache = cache_status)
        if (cache_status):
            for x in scandata:
                print_info("("+blue(str(x))+") "+red(" file: ")+etpConst['systemroot']+scandata[x]['destination'])
        cache_status = True

        if (not scandata):
            print_info(darkred("All fine baby. Nothing to do!"))
            break

        keys = scandata.keys()
        cmd = selfile()
        try:
            cmd = int(cmd)
        except:
            print_error("You don't have typed a number.")
            continue

        # actions
        if cmd == -1:
            # exit
            return -1
        elif cmd in (-3,-5):
            # automerge files asking one by one
            for key in keys:
                if not os.path.isfile(etpConst['systemroot']+scandata[key]['source']):
                    scandata = removefromcache(scandata,key)
                    continue
                print_info(darkred("Configuration file: ")+darkgreen(etpConst['systemroot']+scandata[key]['destination']))
                if cmd == -3:
                    rc = Text.askQuestion(">>   Overwrite ?")
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
                scandata = removefromcache(scandata,key)
            break

        elif cmd in (-7,-9):
            for key in keys:

                if not os.path.isfile(etpConst['systemroot']+scandata[key]['source']):
                    scandata = removefromcache(scandata,key)
                    continue
                print_info(darkred("Configuration file: ")+darkgreen(etpConst['systemroot']+scandata[key]['destination']))
                if cmd == -7:
                    rc = Text.askQuestion(">>   Discard ?")
                    if rc == "No":
                        continue
                print_info(darkred("Discarding ")+darkgreen(etpConst['systemroot']+scandata[key]['source']))
                try:
                    os.remove(etpConst['systemroot']+scandata[key]['source'])
                except:
                    pass
                scandata = removefromcache(scandata,key)

            break

        elif cmd > 0:
            if scandata.get(cmd):

                # do files exist?
                if not os.path.isfile(etpConst['systemroot']+scandata[cmd]['source']):
                    scandata = removefromcache(scandata,key)
                    continue
                if not os.path.isfile(etpConst['systemroot']+scandata[cmd]['destination']):
                    print_info(darkred("Automerging file: ")+darkgreen(etpConst['systemroot']+scandata[cmd]['source']))
                    shutil.move(etpConst['systemroot']+scandata[key]['source'],etpConst['systemroot']+scandata[key]['destination'])
                    scandata = removefromcache(scandata,key)
                    continue
                # end check

                diff = showdiff(etpConst['systemroot']+scandata[cmd]['destination'],etpConst['systemroot']+scandata[cmd]['source'])
                if (not diff):
                    print_info(darkred("Automerging file ")+darkgreen(etpConst['systemroot']+scandata[cmd]['source']))
                    shutil.move(etpConst['systemroot']+scandata[cmd]['source'],etpConst['systemroot']+scandata[cmd]['destination'])
                    scandata = removefromcache(scandata,key)
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
                        scandata = removefromcache(scandata,cmd)
                        comeback = True
                        break

                    elif action == 2:
                        print_info(darkred("Deleting file ")+darkgreen(etpConst['systemroot']+scandata[cmd]['source']))
                        try:
                            os.remove(etpConst['systemroot']+scandata[cmd]['source'])
                        except:
                            pass
                        scandata = removefromcache(scandata,cmd)
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
                            scandata = removefromcache(scandata, cmd)
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
    output = getoutput(diffcmd).split("\n")
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
   @description: scan for files that need to be merged
   @output: dictionary using filename as key
'''
def scanfs(dcache = True):

    if (dcache):
	# can we load cache?
	try:
	    z = loadcache()
	    if z != None:
	        return z
	except:
	    pass

    # open client database to fill etpConst['dbconfigprotect']
    Equo
    if (not etpUi['quiet']): print_info(yellow(" @@ ")+darkgreen("Scanning filesystem..."))
    scandata = {}
    counter = 0
    for path in etpConst['dbconfigprotect']:
	# it's a file?
	scanfile = False
	if os.path.isfile(path):
	    # find inside basename
	    path = os.path.dirname(path)
	    scanfile = True
	
	for currentdir,subdirs,files in os.walk(path):
	    for item in files:
		
		if (scanfile):
		    if path != item:
			continue
		
		filepath = currentdir+"/"+item
		if item.startswith("._cfg"):
		    
		    # further check then
		    number = item[5:9]
		    try:
			int(number)
		    except:
			continue # not a valid etc-update file
		    if item[9] != "_": # no valid format provided
			continue
		    
		    mydict = generatedict(filepath)
		    if mydict['automerge']:
		        if (not etpUi['quiet']): print_info(darkred("Automerging file: ")+darkgreen(etpConst['systemroot']+mydict['source']))
			if os.path.isfile(etpConst['systemroot']+mydict['source']):
                            try:
                                shutil.move(etpConst['systemroot']+mydict['source'],etpConst['systemroot']+mydict['destination'])
                            except IOError:
                                if (not etpUi['quiet']): print_info(darkred("I/O Error :: Cannot automerge file: ")+darkgreen(etpConst['systemroot']+mydict['source']))
			continue
		    else:
			counter += 1
		        scandata[counter] = mydict.copy()

		    try:
		        if (not etpUi['quiet']): print_info("("+blue(str(counter))+") "+red(" file: ")+os.path.dirname(filepath)+"/"+os.path.basename(filepath)[10:])
		    except:
			pass # possible encoding issues
    # store data
    try:
        Equo.dumpTools.dumpobj(etpCache['configfiles'],scandata)
    except:
	pass
    return scandata


def loadcache():
    try:
	sd = Equo.dumpTools.loadobj(etpCache['configfiles'])
	# check for corruption?
	if isinstance(sd, dict):
	    # quick test if data is reliable
	    try:
		taint = False
		for x in sd:
		    if not os.path.isfile(etpConst['systemroot']+sd[x]['source']):
			taint = True
			break
		if (not taint):
		    return sd
		else:
		    raise exceptionTools.CacheCorruptionError("CacheCorruptionError: cache is corrupted.")
	    except:
		raise exceptionTools.CacheCorruptionError("CacheCorruptionError: cache is corrupted.")
	else:
	    raise exceptionTools.CacheCorruptionError("CacheCorruptionError: cache is corrupted.")
    except:
	raise exceptionTools.CacheCorruptionError("CacheCorruptionError: cache is corrupted.")


def generatedict(filepath):
    item = os.path.basename(filepath)
    currentdir = os.path.dirname(filepath)
    tofile = item[10:]
    number = item[5:9]
    try:
	int(number)
    except:
	raise exceptionTools.InvalidDataType("InvalidDataType: invalid config file number '0000->9999'.")
    tofilepath = currentdir+"/"+tofile
    mydict = {}
    mydict['revision'] = number
    mydict['destination'] = tofilepath[len(etpConst['systemroot']):]
    mydict['source'] = filepath[len(etpConst['systemroot']):]
    mydict['automerge'] = False
    if not os.path.isfile(tofilepath):
        mydict['automerge'] = True
    if (not mydict['automerge']):
        # is it trivial?
        try:
            if not os.path.lexists(filepath): # if file does not even exist
                return mydict
	    if os.path.islink(filepath):
		# if it's broken, skip diff and automerge
		if not os.path.exists(filepath):
		    return mydict
	    result = getoutput('diff -Nua '+filepath+' '+tofilepath+' | grep "^[+-][^+-]" | grep -v \'# .Header:.*\'')
	    if not result:
	        mydict['automerge'] = True
        except:
	    pass
	# another test
	if (not mydict['automerge']):
	    try:
                if not os.path.lexists(filepath): # if file does not even exist
                    return mydict
	        if os.path.islink(filepath):
		    # if it's broken, skip diff and automerge
		    if not os.path.exists(filepath):
		        return mydict
		result = os.system('diff -Bbua '+filepath+' '+tofilepath+' | egrep \'^[+-]\' | egrep -v \'^[+-][\t ]*#|^--- |^\+\+\+ \' | egrep -qv \'^[-+][\t ]*$\'')
		if result == 1:
		    mydict['automerge'] = True
	    except:
		pass
    return mydict

'''
   @description: prints information about config files that should be updated
   @attention: please be sure that filepath is properly formatted before using this function
'''
def addtocache(filepath):
    try:
	scandata = loadcache()
    except:
	scandata = scanfs(dcache = False)
    keys = scandata.keys()
    try:
	for key in keys:
	    if scandata[key]['source'] == filepath[len(etpConst['systemroot']):]:
		del scandata[key]
    except:
	pass
    # get next counter
    if keys:
        keys.sort()
        index = keys[-1]
    else:
	index = 0
    index += 1
    mydata = generatedict(filepath)
    scandata[index] = mydata.copy()
    try:
        Equo.dumpTools.dumpobj(etpCache['configfiles'],scandata)
    except:
	pass

def removefromcache(sd,key):
    try:
        del sd[key]
    except:
	pass
    Equo.dumpTools.dumpobj(etpCache['configfiles'],sd)
    return sd

'''
   @description: prints information about config files that should be updated
'''
def confinfo():
    print_info(yellow(" @@ ")+darkgreen("These are the files that would be updated:"))
    data = scanfs(dcache = False)
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
