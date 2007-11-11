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
from entropyConstants import *
from clientConstants import *
from outputTools import *
import entropyTools
import dumpTools
import equoTools

# test if diff is installed
difftest = entropyTools.spawnCommand("diff -v", redirect = "&> /dev/null")
if (difftest):
    print "ERROR: diff not found, cannot continue"

########################################################
####
##   Configuration Tools
#

def configurator(options):

    rc = 0
    if len(options) < 1:
	return rc

    equoRequestVerbose = False
    equoRequestQuiet = False
    myopts = []
    for opt in options:
	if (opt == "--verbose"):
	    equoRequestVerbose = True
	elif (opt == "--quiet"):
	    equoRequestQuiet = True
	else:
	    if not opt.startswith("-"):
	        myopts.append(opt)

    if myopts[0] == "info":
	rc = confinfo()

    elif myopts[0] == "update":
	rc = update()

    return rc


'''
   @description: scan for files that need to be merged
   @output: dictionary using filename as key
'''
def update():
    cache_status = False
    while 1:
	scandata = scanfs(quiet = False, dcache = cache_status)
	if (cache_status):
	    for x in scandata:
		print_info("("+blue(str(x))+") "+red(" file: ")+scandata[x]['source'])
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
		if not os.path.isfile(scandata[key]['source']):
		    scandata = removefromcache(scandata,key)
		    continue
		print_info(darkred("Configuration file: ")+darkgreen(scandata[key]['destination']))
		if cmd == -3:
		    rc = entropyTools.askquestion(">>   Overwrite ?")
		    if rc == "No":
			continue
		print_info(darkred("Moving ")+darkgreen(scandata[key]['source'])+darkred(" to ")+brown(scandata[key]['destination']))
		os.rename(scandata[key]['source'],scandata[key]['destination'])
		# remove from cache
		scandata = removefromcache(scandata,key)
	    break
	
	elif cmd in (-7,-9):
	    for key in keys:
		
		if not os.path.isfile(scandata[key]['source']):
		    scandata = removefromcache(scandata,key)
		    continue
		print_info(darkred("Configuration file: ")+darkgreen(scandata[key]['destination']))
		if cmd == -7:
		    rc = entropyTools.askquestion(">>   Discard ?")
		    if rc == "No":
			continue
		print_info(darkred("Discarding ")+darkgreen(scandata[key]['source']))
		try:
		    os.remove(scandata[key]['source'])
		except:
		    pass
		scandata = removefromcache(scandata,key)
		
	    break
	
	elif cmd > 0:
	    if scandata.get(cmd):
		
		# do files exist?
		if not os.path.isfile(scandata[cmd]['source']):
		    scandata = removefromcache(scandata,key)
		    continue
		if not os.path.isfile(scandata[cmd]['destination']):
		    print_info(darkred("Automerging file: ")+darkgreen(scandata[cmd]['source']))
		    os.rename(scandata[key]['source'],scandata[key]['destination'])
		    scandata = removefromcache(scandata,key)
		    continue
		# end check
		
		diff = showdiff(scandata[cmd]['destination'],scandata[cmd]['source'])
		if (not diff):
		    print_info(darkred("Automerging file ")+darkgreen(scandata[cmd]['source']))
		    os.rename(scandata[cmd]['source'],scandata[cmd]['destination'])
		    scandata = removefromcache(scandata,key)
		    continue
	        print_info(darkred("Selected file: ")+darkgreen(scandata[cmd]['source']))

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
			print_info(darkred("Replacing ")+darkgreen(scandata[cmd]['destination'])+darkred(" with ")+darkgreen(scandata[cmd]['source']))
			os.rename(scandata[cmd]['source'],scandata[cmd]['destination'])
			scandata = removefromcache(scandata,cmd)
			comeback = True
			break
		
		    elif action == 2:
			print_info(darkred("Deleting file ")+darkgreen(scandata[cmd]['source']))
			try:
			    os.remove(scandata[cmd]['source'])
			except:
			    pass
			scandata = removefromcache(scandata,cmd)
			comeback = True
			break
		
		    elif action == 3:
			print_info(darkred("Editing file ")+darkgreen(scandata[cmd]['source']))
			if os.getenv("EDITOR"):
			    os.system("$EDITOR "+scandata[cmd]['source'])
			elif os.access("/bin/nano",os.X_OK):
			    os.system("/bin/nano "+scandata[cmd]['source'])
			elif os.access("/bin/vi",os.X_OK):
			    os.system("/bin/vi "+scandata[cmd]['source'])
			elif os.access("/usr/bin/vi",os.X_OK):
			    os.system("/usr/bin/vi "+scandata[cmd]['source'])
			elif os.access("/usr/bin/emacs",os.X_OK):
			    os.system("/usr/bin/emacs "+scandata[cmd]['source'])
			elif os.access("/bin/emacs",os.X_OK):
			    os.system("/bin/emacs "+scandata[cmd]['source'])
			else:
			    print_error(" Cannot find a suitable editor. Can't edit file directly.")
			    comeback = True
			    break
			print_info(darkred("Edited file ")+darkgreen(scandata[cmd]['source'])+darkred(" - showing differencies:"))
			diff = showdiff(scandata[cmd]['source'],scandata[cmd]['destination'])
			if (not diff):
			    print_info(darkred("Automerging file ")+darkgreen(scandata[cmd]['source']))
			    os.rename(scandata[cmd]['source'],scandata[cmd]['destination'])
			    scandata = removefromcache(scandata, cmd)
			    comeback = True
			    break
			
			continue

		    elif action == 4:
			# show diffs again
			diff = showdiff(scandata[cmd]['source'],scandata[cmd]['destination'])
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
def scanfs(quiet = True, dcache = True):

    if (dcache):
	# can we load cache?
	try:
	    c = loadcache()
	    if c != None:
	        return c
	except:
	    pass

    # load etpConst['dbconfigprotect']
    clientDbconn = equoTools.openClientDatabase()
    clientDbconn.closeDB()
    # etpConst['dbconfigprotect']
    if (not quiet): print_info(yellow(" @@ ")+darkgreen("Scanning filesystem..."))
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
	    for file in files:
		
		if (scanfile):
		    if path != file:
			continue
		
		filepath = currentdir+"/"+file
		if file.startswith("._cfg"):
		    
		    # further check then
		    number = file[5:9]
		    try:
			int(number)
		    except:
			continue # not a valid etc-update file
		    if file[9] != "_": # no valid format provided
			continue
		    
		    mydict = generatedict(filepath)
		    if mydict['automerge']:
		        if (not quiet): print_info(darkred("Automerging file: ")+darkgreen(mydict['source']))
			if os.path.isfile(mydict['source']):
		            os.rename(mydict['source'],mydict['destination'])
			continue
		    else:
			counter += 1
		        scandata[counter] = mydict.copy()

		    try:
		        if (not quiet): print_info("("+blue(str(counter))+") "+red(" file: ")+os.path.dirname(filepath)+"/"+os.path.basename(filepath)[10:])
		    except:
			pass # possible encoding issues
    # store data
    try:
        dumpTools.dumpobj(etpCache['configfiles'],scandata)
    except:
	pass
    return scandata


def loadcache():
    try:
	sd = dumpTools.loadobj(etpCache['configfiles'])
	# check for corruption?
	if isinstance(sd, dict):
	    # quick test if data is reliable
	    try:
		taint = False
		for x in sd:
		    if not os.path.isfile(sd[x]['source']):
			taint = True
			break
		if (not taint):
		    return sd
		else:
		    raise Exception
	    except:
		raise Exception
	else:
	    raise Exception
    except:
	raise Exception


def generatedict(filepath):
    file = os.path.basename(filepath)
    currentdir = os.path.dirname(filepath)
    tofile = file[10:]
    number = file[5:9]
    try:
	int(number)
    except:
	raise Exception,"bad formatted filepath"
    tofilepath = currentdir+"/"+tofile
    mydict = {}
    mydict['revision'] = number
    mydict['destination'] = tofilepath
    mydict['source'] = filepath
    mydict['automerge'] = False
    if not os.path.isfile(tofilepath):
        mydict['automerge'] = True
    if (not mydict['automerge']):
        # is it trivial?
        try:
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
	scandata = scanfs(quiet = True, dcache = False)
    keys = scandata.keys()
    try:
	for key in keys:
	    if scandata[key]['source'] == filepath:
		del scandata[key]
    except:
	pass
    # get next counter
    if keys:
        keys.sort()
        index = keys[len(keys)-1]
    else:
	index = 0
    index += 1
    mydata = generatedict(filepath)
    scandata[index] = mydata.copy()
    try:
        dumpTools.dumpobj(etpCache['configfiles'],scandata)
    except:
	pass

def removefromcache(sd,key):
    try:
        del sd[key]
    except:
	pass
    dumpTools.dumpobj(etpCache['configfiles'],sd)
    return sd

'''
   @description: prints information about config files that should be updated
'''
def confinfo():
    print_info(yellow(" @@ ")+darkgreen("These are the files that would be updated:"))
    data = scanfs(quiet = True, dcache = False)
    counter = 0
    for file in data:
	counter += 1
	print_info(" ("+blue(str(counter))+") "+"[auto:"+str(data[file]['automerge'])+"]"+red(" file: ")+file)
    print_info(red(" @@ ")+brown("Unique files that would be update:\t\t")+red(str(len(data))))
    automerge = 0
    for x in data:
	if data[x]['automerge']:
	    automerge += 1
    print_info(red(" @@ ")+brown("Unique files that would be automerged:\t\t")+green(str(automerge)))
    return 0
