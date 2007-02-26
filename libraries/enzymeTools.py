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
    lst = etpConst['overlays'].split()
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


def build(atoms): 

# FIXME: remember to use listOverlay() as PORTDIR_OVERLAY variable
# FIXME: move print() to our print function
    
    enzymeRequestVerbose = False
    enzymeRequestForce = False
    #enzymeRequestForceRepackage = False
    enzymeRequestUpdate = False
    enzymeRequestPretendAll = False
    enzymeRequestIgnoreConflicts = False
    enzymeRequestInteraction = True
    _atoms = []
    for i in atoms:
        if ( i == "--verbose" ) or ( i == "-v" ):
	    enzymeRequestVerbose = True
	elif ( i == "--force-build" ):
	    enzymeRequestForce = True
	#elif ( i == "--force-repackage" ):
	#    enzymeRequestForceRepackage = True
	elif ( i == "--update" ):
	    enzymeRequestUpdate = True
	elif ( i == "--ignore-conflicts" ):
	    enzymeRequestIgnoreConflicts = True
	elif ( i == "--pretend" ):
	    enzymeRequestPretendAll = True
	elif ( i == "--no-interaction" ):
	    enzymeRequestInteraction = False
	else:
	    _atoms.append(i)
    atoms = _atoms
    
    if (enzymeRequestVerbose): print "verbose: "+str(enzymeRequestVerbose)
    if (enzymeRequestVerbose): print "force build: "+str(enzymeRequestForce)
    
    # translate dir variables
    etpConst['packagessuploaddir'] = translateArch(etpConst['packagessuploaddir'],getPortageEnv('CHOST'))
    etpConst['packagesstoredir'] = translateArch(etpConst['packagesstoredir'],getPortageEnv('CHOST'))
    etpConst['packagesbindir'] = translateArch(etpConst['packagesbindir'],getPortageEnv('CHOST'))
    
    validAtoms = []
    for i in atoms:
        if (enzymeRequestVerbose): print i+" is valid?: "+str(checkAtom(i))
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

    buildCmd = None
    toBeBuilt = []
    PackagesDependencies = []
    PackagesConflicting = []
    PackagesQuickpkg = []

    # check if the package is already installed
    for atom in validAtoms:
        # let's dance !!
        isAvailable = getInstalledAtom("="+atom)
	if (enzymeRequestVerbose): print "testing atom: "+atom
	if (isAvailable is not None) and (not enzymeRequestForce):
	    # package is available on the system
	    if (enzymeRequestVerbose): print "I'd like to keep a current copy of binary package "+atom+" but first I need to check if even this step has been already done"

	    tbz2Available = isTbz2PackageAvailable(atom, enzymeRequestVerbose)

	    if (tbz2Available == False):
		if (enzymeRequestVerbose): print "I'll have to build: "+atom
	        toBeBuilt.append(atom)
	    else:
	        if (enzymeRequestVerbose): print "I will use this already precompiled package: "+tbz2Available
	else:
            if (enzymeRequestVerbose): print "I have to compile or quickpkg "+atom+" by myself..."
	    if (enzymeRequestForce) or (isAvailable is None):
		toBeBuilt.append(atom)
	    elif (not enzymeRequestForce) and (isAvailable is not None):
		wantedAtom = getBestAtom(atom)
		if (wantedAtom == isAvailable):
		    PackagesQuickpkg.append("quick|"+atom)
		else:
		    toBeBuilt.append(atom)
	    else:
		toBeBuilt.append(atom)
	    
    
    # now we have to solve the dependencies and create the packages that need to be build
    for atom in toBeBuilt:
	print
	# check its unsatisfied dependencies
	print "  Checking "+bold(atom)+" dependencies and conflicts..."
	print
	atomdeps, atomconflicts = synthetizeRoughDependencies(getPackageDependencyList(atom))
	atomdeps = atomdeps.split()
	atomconflicts = atomconflicts.split()
	print "\tfiltering "+atom+" dependencies..."
	# check if the dependency is satisfied
	
	for dep in atomdeps:
	    print "\tchecking for: "+red(dep)
	    # filter |or|
	    if dep.find(dbOR) != -1:
	        deps = dep.split(dbOR)
		for i in deps:
		    if getInstalledAtom(i) is not None:
		        dep = i
			break
	    wantedAtom = getBestAtom(dep)
	    print "\t\tI want: "+yellow(wantedAtom)
	    installedAtom = getInstalledAtom(dep)
	    print "\t\tIs installed: "+green(str(installedAtom))
	    if installedAtom is None:
		# then append - because it's not installed !
		print "\t\t"+dep+" is not installed, adding."
		PackagesDependencies.append(wantedAtom)
	    elif (wantedAtom != installedAtom):
		if (enzymeRequestUpdate):
		    PackagesDependencies.append(wantedAtom)
		    print "\t\t"+dep+" versions differs, adding (pulled in by --update)."
		else:
		    if (isTbz2PackageAvailable(installedAtom) == False):
			# quickpkg'd
		        PackagesQuickpkg.append("quick|"+installedAtom)
		    else:
			# already available
		        PackagesQuickpkg.append("avail|"+installedAtom)
		    print "\t\t"+dep+" versions differs but not adding since the dependency is permissive."
	    else:
		if (isTbz2PackageAvailable(installedAtom) == False):
		    PackagesQuickpkg.append("quick|"+installedAtom)
		print "\t\t"+dep+" versions match, no need to build"
	print
	if atomconflicts != []:
	    print "\tfiltering "+atom+" conflicts..."
	for conflict in atomconflicts:
	    print "\tchecking for: "+red(conflict)
	    if getInstalledAtom(conflict) is not None:
		# damn, it's installed
		print "\t\t Package "+yellow(conflict)+" conflicts"
		PackagesConflicting.append(conflict)
	#FIXME: DO THIS PART check if there are conflicts

    print

    print
    if toBeBuilt != []:
	print green("   *")+" This is the list of the packages that needs to be built:"
        for i in toBeBuilt:
	    print yellow("      *")+" "+i
    else:
	print red("   *")+" No packages to build"
    print

    if PackagesDependencies != []:
	print yellow("   *")+" These are their dependencies (pulled in):"
        for i in PackagesDependencies:
	    print red("      *")+bold(" [COMPI] ")+i
	for i in PackagesQuickpkg:
	    if i.startswith("quick|"):
	        print green("      *")+bold(" [QUICK] ")+i.split("quick|")[len(i.split("quick|"))-1]
	    elif i.startswith("avail|"):
	        print green("      *")+bold(" [AVAIL] ")+i.split("avail|")[len(i.split("avail|"))-1]
	    else:
		# I should never get here
	        print green("      *")+bold(" [MERGE] ")+i
    else:
	print green("   *")+" No extra dependencies required"
    print
    
    if PackagesConflicting != []:
	print red("   *")+" These are the conflicting packages:"
	for i in PackagesConflicting:
	    print red("      *")+bold(" [CONFL] ")+i
	if (not enzymeRequestIgnoreConflicts):
	    print
	    print
	    print red(" ***")+" Sorry, I can't continue. To force this, add --ignore-conflicts at your own risk."
	    sys.exit(1)
	else:
	    import time
	    print
	    print yellow(" ***")+" You are using --ignore-conflicts at your own risk."
	    print
	    time.sleep(5)

    if (enzymeRequestPretendAll):
	sys.exit(0)
	
    # when the compilation ends, enzyme runs reagent
    packagesPaths = []
    
    print
    if PackagesDependencies != []:
        print yellow("  *")+" Building dependencies..."
	for dep in PackagesDependencies:
	    outfile = etpConst['packagestmpdir']+"/.emerge-"+str(getRandomNumber())
	    print green("  *")+" Compiling: "+red(dep)+" ... "
	    if (not enzymeRequestVerbose):
		print yellow("     *")+" redirecting output to: "+green(outfile)
		rc, outfile = emerge("="+dep,odbNodeps,outfile)
	    else:
		rc, outfile = emerge("="+dep,odbNodeps,None,None)
	    if (not rc):
		# compilation is fine
		print green("     *")+" Compiled successfully"
		PackagesQuickpkg.append("quick|"+dep)
		os.remove(outfile)
	    else:
		print red("     *")+" Compile error"
		if (not enzymeRequestVerbose): print red("     *")+" Log file at: "+outfile
		print
		print
		print red("  ***")+" Cannot continue"
		sys.exit(250)
	    # FIXME: move the .tbz2 to the proper directory
	    
	    # FIXME: complete this by adding to packagesPaths the path of the file
    
    if toBeBuilt != []:
        print green("  *")+" Building packages..."
	for dep in toBeBuilt:
	    outfile = etpConst['packagestmpdir']+"/.emerge-"+str(getRandomNumber())
	    print green("  *")+" Compiling: "+red(dep)
	    if (not enzymeRequestVerbose):
		print yellow("     *")+" redirecting output to: "+green(outfile)
		rc, outfile = emerge("="+dep,odbNodeps,outfile)
	    else:
		rc, outfile = emerge("="+dep,odbNodeps,None,None)
	    if (not rc):
		# compilation is fine
		print green("     *")+" Compiled successfully"
		PackagesQuickpkg.append("quick|"+dep)
		os.remove(outfile)
	    else:
		print red("     *")+" Compile error"
		if (not enzymeRequestVerbose): print red("     *")+" Log file at: "+outfile
		print
		print
		print red("  ***")+" Cannot continue"
		sys.exit(250)

    # FIXME: before running quickpkg or qpkg PLEASE run etc-update interactively
    # FIXME: parse --no-interaction option

    print
    if PackagesQuickpkg != []:
        print green("  *")+" Compressing already installed packages..."
	for dep in PackagesQuickpkg:
	    # running emerge and detect:
	    # - errors
	    # - log files
	    # - etc update?
	    dep = dep.split("|")[len(dep.split("|"))-1]
	    print green("  *")+" Compressing: "+red(dep)
	    # FIXME: complete and add path to packagesPaths

    if packagesPaths != []:
	print red("   *")+" These are the binary packages created:"
	for pkg in packagesPaths:
	    print green("      *")+red(pkg)

    return packagesPaths

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
