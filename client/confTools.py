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

import sys
import commands
sys.path.append('../libraries')
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

    #elif options[0] == "belongs":
	#rc = searchBelongs(myopts[1:], quiet = equoRequestQuiet)

    return rc

'''
   @description: scan for files that need to be merged
   @output: dictionary using filename as key
'''
def scanfs(quiet = True, dcache = True):

    if (dcache):
	# can we load cache?
	try:
	    c = loadcache()
	    return c
	except:
	    pass

    # load etpConst['dbconfigprotect']
    clientDbconn = equoTools.openClientDatabase()
    equoTools.closeClientDatabase(clientDbconn)
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
		    scandata[filepath] = mydict.copy()

		    counter += 1
		    try:
		        if (not quiet): print_info("("+blue(str(counter))+") "+"[auto:"+str(scandata[filepath]['automerge'])+"]"+red(" file: ")+filepath)
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
		    if not os.path.isfile(x):
			taint = True
			break
		if (not taint):
		    return sd
		else:
		    raise Exception
	    except:
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
    mydict['automerge'] = False
    if not os.path.isfile(tofilepath):
        mydict['automerge'] = True
    if (not mydict['automerge']):
        # is it trivial?
        try:
	    result = commands.getoutput('diff -Nua '+filepath+' '+tofilepath+' | grep "^[+-][^+-]" | grep -v \'# .Header:.*\'')
	    if not result:
	        mydict['automerge'] = True
        except:
	    pass
    return mydict

'''
   @description: prints information about config files that should be updated
   @attention: please be sure that filepath is properly formatted before using this function
'''
# 
def addtocache(filepath):
    try:
	scandata = loadcache()
    except:
	scandata = scanfs(quiet = True, dcache = False)
    try:
	del scandata[filepath]
    except:
	pass
    mydata = generatedict(filepath)
    scandata[filepath] = mydata.copy()
    try:
        dumpTools.dumpobj(etpCache['configfiles'],scandata)
    except:
	pass

def removefromcache(filepath):
    try:
	scandata = loadcache()
    except:
	scandata = scanfs(quiet = True, dcache = False)
    try:
	del scandata[filepath]
	dumpTools.dumpobj(etpCache['configfiles'],scandata)
    except:
	pass

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
