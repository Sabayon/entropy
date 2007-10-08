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
from equoTools import openClientDatabase, closeClientDatabase

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
def scanfs(quiet = True):
    # load etpConst['dbconfigprotect']
    clientDbconn = openClientDatabase()
    closeClientDatabase(clientDbconn)
    # etpConst['dbconfigprotect']
    if (not quiet): print_info(yellow(" @@ ")+darkgreen("Scanning filesystem..."))
    scandata = {}
    counter = 0
    for path in etpConst['dbconfigprotect']:
	# it's a file?
	if os.path.isfile(path):
	    # find inside basename
	    path = os.path.dirname(path)
	
	for currentdir,subdirs,files in os.walk(path):
	    for file in files:
		#if currentdir.startswith("/usr/share/X11"):
		#    print file
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
		    tofile = file[10:]
		    tofilepath = currentdir+"/"+tofile
		    scandata[filepath] = {}
		    scandata[filepath]['revision'] = number
		    scandata[filepath]['destination'] = tofilepath
		    if os.path.isfile(tofilepath):
			scandata[filepath]['automerge'] = False
		    else:
			scandata[filepath]['automerge'] = True
		    if (not scandata[filepath]['automerge']):
			# is it trivial?
			try:
			    result = commands.getoutput('diff -Nua '+filepath+' '+tofilepath+' | grep "^[+-][^+-]" | grep -v \'# .Header:.*\'')
			    if not result:
				scandata[filepath]['automerge'] = True
			except:
			    print "ERROR"
			    pass
		    counter += 1
		    try:
		        if (not quiet): print_info("("+blue(str(counter))+") "+red(" Found file: ")+filepath)
		    except:
			pass # possible encoding issues
    return scandata



'''
   @description: prints information about config files that should be updated
'''
def confinfo():
    
    print_info(yellow(" @@ ")+darkgreen("Loading information..."), back = True)
    data = scanfs(quiet = False)
    print len(data)
    return 0
