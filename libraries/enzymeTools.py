#!/usr/bin/python
'''
    # DESCRIPTION:
    # generic tools for enzyme application

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

# Never do "import portage" here, please use entropyTools binding

from entropyConstants import *
from entropyTools import *

import sys
import os
import commands



# Stolen from Porthole 0.5.0 - thanks for your help :-)

def getSyncTime():
    """gets and returns the timestamp info saved during
       the last portage tree sync"""
    lastSync = None
    try:
        f = open(etpConst['portagetreedir'] + "/metadata/timestamp")
        data = f.read()
	f.close()
        if data:
            try:
                lastSync = (str(data).decode('utf_8').encode("utf_8",'replace'))
            except:
                try:
                    lastSync = (str(data).decode('iso-8859-1').encode('utf_8', 'replace'))
                except:
                    print_warning("getSyncTime(): unknown encoding")
        else:
            print_warning("getSyncTime(): nothing to read")
    except:
        print_warning("getSyncTime(): empty Portage tree (first run?) or no timestamp to read")

def listOverlays():
    # NOTE: this function does not directly check if
    #       layman is installed !!!!
    lst = os.listdir(etpConst['overlaysdir'])
    _lst = []
    for i in lst:
        if os.path.isdir(etpConst['overlaysdir']+"/"+i):
	    _lst.append(i)
    lst = _lst
    return lst

# fetch the latest updates from Gentoo rsync mirrors
def sync(options):
    syncMiscRedirect = "> /dev/null"
    for i in options:
        if i.startswith("--verbose") or i.startswith("-v"):
	    syncMiscRedirect = None
    print_info(green("syncing the Portage tree at: "+etpConst['portagetreedir']))
    rc = spawnCommand(vdbPORTDIR+"="+etpConst['portagetreedir']+" "+cdbEMERGE+" --sync ", redirect = syncMiscRedirect) # redirect = "/dev/null"
    if (rc != 0):
        print_error(red("an error occoured while syncing the Portage tree. Are you sure that your Internet connection works?"))
	sys.exit(101)


def build(atoms): # FIXME: remember to use listOverlay() as PORTDIR_OVERLAY variable
    validAtoms = []
    for i in atoms:
        print i+" is valid?: "+str(checkAtom(i))
	if (checkAtom(i)):
	    validAtoms.append(i)
    if validAtoms == []:
        print_error(red(bold("no valid package names specified.")))
	sys.exit(102)

    # resolve atom name with the best package available
    _validAtoms = []
    for i in validAtoms:
        _validAtoms.append(getBestAtom(i))
    validAtoms = _validAtoms
    
    toBeBuilt = []
    # check if the package is already installed, if yes, check also::
    for atom in validAtoms:
        isAvailable = getInstalledAtom("="+atom)
	if isAvailable is not None:
	    # package is available on the system
	    # FIXME: add an option to force all the compilations
	    print "I'd like to quickpkg "+atom+" but first I need to check if even this step has been already done"
        else:
            print "I have to compile "+atom+" by mysel..."

        # check, one by one, if the package have been already built
        # 1. check if the .tbz2 file is in:
        #    etpConst['packagessuploaddir']
        #    etpConst['packagesstoredir']
        #    etpConst['packagesbindir']
        # save the path
    
        # then extract the info using xpak

    # otherwise, add it to the build list

def overlay(options):
    # etpConst['overlaysconffile'] --> layman.cfg

    # check if the portage tree is configured
    if (not os.path.isfile(etpConst['portagetreedir']+"/metadata/timestamp")):
        print_error(red(bold("Entropy Portage tree is not yet prepared. Use the 'sync' tool first.")))
	return False

    # check if layman is installed
    layman = commands.getoutput("which layman")
    if (not layman.startswith("/")):
        print_error(red(bold("app-portage/layman is not installed. Please install.")))
	return False

    myopts = options[1:]

    # be verbose?
    verbosity = "> /dev/null"
    for x in myopts:
        if x.startswith("--verbose") or x.startswith("-v"):
	    verbosity = None

    # filter garbage
    _myopts = []
    for x in myopts:
        # --verbose, -v
	if (x != "--verbose" ) and (x != "-v" ):
	    _myopts.append(x)
    myopts = _myopts

    if (myopts == []):
        print_error(red(bold("not enough parameters.")))
	return False

    # starting Test Case
    if (myopts[0] == "add"):
        # add overlay
	myownopts = list(set(myopts[1:]))
	for i in myownopts:
	    print_info(green("adding overlay: ")+bold(i))
	    rc = spawnCommand(layman+" --config="+etpConst['overlaysconffile']+" -f -a "+i, redirect = verbosity)
	    if (rc != 0):
	        print_warning(red(bold("a problem occoured adding "+i+" overlay.")))
    elif (myopts[0] == "remove"):
        # remove overlay
	myownopts = list(set(myopts[1:]))
	for i in myownopts:
	    print_info(green("removing overlay: ")+bold(i))
	    rc = spawnCommand(layman+" --config="+etpConst['overlaysconffile']+" -d "+i, redirect = verbosity)
	    if (rc != 0):
	        print_warning(red(bold("a problem occoured removing "+i+" overlay.")))
	return True
    elif (myopts[0] == "sync"):
        # sync an overlay
	myownopts = list(set(myopts[1:]))
	if (myownopts == []):
	    # sync all
	    print_info(green("syncing all the overlays"))
	    rc = spawnCommand(layman+" --config="+etpConst['overlaysconffile']+" -S ", redirect = verbosity)
	    if (rc != 0):
	        print_warning(red(bold("a problem occoured syncing all the overlays.")))
	    else:
		print_info(green("sync completed."))
	else:
	    # sync each overlay
	    for i in myownopts:
		print_info(green("syncing overlay: ")+bold(i))
	        rc = spawnCommand(layman+" --config="+etpConst['overlaysconffile']+" -s "+i, redirect = verbosity)
	        if (rc != 0):
	            print_warning(red(bold("a problem occoured syncing "+i+" overlay.")))
		else:
		    print_info(green("synced overlay: ")+bold(i))
	return True
    elif (myopts[0] == "list"):
        # add an overlay
	listing = listOverlays()
	if (listing == []):
	    print_info(green("no overlays."))
	else:
	    for i in listing:
	        print_info(green(i)+" overlay is added.")
    else:
        # error !
	print_error(red(bold("wrong synthax.")))
	return False
    
    return True
