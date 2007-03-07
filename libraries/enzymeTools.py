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

# FIXME: move print() to our print function
# FIXME: add runtime dependencies packages quickpkg

    enzymeRequestVerbose = False
    enzymeRequestForceRepackage = False
    enzymeRequestForceRebuild = False
    enzymeRequestUpdate = False
    enzymeRequestPretendAll = False
    enzymeRequestIgnoreConflicts = False
    enzymeRequestInteraction = True
    enzymeRequestSimulation = False
    _atoms = []
    for i in atoms:
        if ( i == "--verbose" ) or ( i == "-v" ):
	    enzymeRequestVerbose = True
	elif ( i == "--force-repackage" ):
	    enzymeRequestForceRepackage = True
	elif ( i == "--force-rebuild" ):
	    enzymeRequestForceRebuild = True
	elif ( i == "--update" ):
	    enzymeRequestUpdate = True
	elif ( i == "--ignore-conflicts" ):
	    enzymeRequestIgnoreConflicts = True
	elif ( i == "--pretend" ):
	    enzymeRequestPretendAll = True
	elif ( i == "--no-interaction" ):
	    enzymeRequestInteraction = False
	elif ( i == "--simulate-building" ):
	    enzymeRequestSimulation = True
	else:
	    _atoms.append(i)
    atoms = _atoms
    
    #if (enzymeRequestVerbose): print "verbose: "+str(enzymeRequestVerbose)
    #if (enzymeRequestVerbose): print "force build: "+str(enzymeRequestForceRepackage)
    
    # translate dir variables
    etpConst['packagessuploaddir'] = translateArch(etpConst['packagessuploaddir'],getPortageEnv('CHOST'))
    etpConst['packagesstoredir'] = translateArch(etpConst['packagesstoredir'],getPortageEnv('CHOST'))
    etpConst['packagesbindir'] = translateArch(etpConst['packagesbindir'],getPortageEnv('CHOST'))
    
    validAtoms = []
    for i in atoms:
        if (enzymeRequestVerbose): print i+" is valid?: "+str(checkAtom(i))
	if (checkAtom(i)):
	    validAtoms.append(i)
	else:
	    print
	    print red("* >>> ")+yellow(i)+" is not a valid atom, it's masked or its name conflicts with something else."
	    if getBestAtom(i) == "!!conflicts":
		# it conflicts with something
		print red("* ^^^ ")+"Ambiguous package name. Please add category."

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
    toBeQuickpkg = []
    PackagesDependencies = []
    PackagesConflicting = []
    PackagesQuickpkg = []

    # check if the package is already installed
    for atom in validAtoms:
        # let's dance !!
        isAvailable = getInstalledAtom("="+atom)
	if (enzymeRequestVerbose): print "testing atom: "+atom
	if (isAvailable is not None) and (not enzymeRequestForceRepackage):
	    # package is available on the system
	    if (enzymeRequestVerbose): print "I'd like to keep a current copy of binary package "+atom+" but first I need to check if even this step has been already done"

	    tbz2Available = isTbz2PackageAvailable(atom, enzymeRequestVerbose)

	    if (tbz2Available == False) or (enzymeRequestForceRebuild):
		if (enzymeRequestVerbose): print "Do I really have to build "+bold(atom)+" ?"
	        toBeBuilt.append(atom)
	    else:
	        if (enzymeRequestVerbose): print "I will use this already precompiled package: "+tbz2Available
	else:
            if (enzymeRequestVerbose): print "I have to compile or quickpkg "+atom+" by myself..."
	    if (enzymeRequestForceRepackage) or (isAvailable is None):
		toBeBuilt.append(atom)
	    elif (not enzymeRequestForceRepackage) and (isAvailable is not None):
		wantedAtom = getBestAtom(atom)
		if (wantedAtom == isAvailable):
		    toBeQuickpkg.append(atom)
		else:
		    toBeBuilt.append(atom)
	    else:
		toBeBuilt.append(atom)


    # now we have to solve the dependencies and create the packages that need to be build
    for atom in toBeBuilt:
	# if this turns into true, we need to build the package because its dependencies do not match
	atomDepsTainted = False
	print
	# check its unsatisfied dependencies
	print "  Checking "+bold(atom)+" dependencies and conflicts..."
	atomdeps, atomconflicts = synthetizeRoughDependencies(getPackageDependencyList(atom))
	atomdeps = atomdeps.split()
	atomconflicts = atomconflicts.split()
	print "  Current installed release: "+bold(str(getInstalledAtom(dep_getkey(atom))))
	if(enzymeRequestVerbose): print
	if(enzymeRequestVerbose): print "\tfiltering "+atom+" dependencies..."
	# check if the dependency is satisfied
	
	for dep in atomdeps:
	    if(enzymeRequestVerbose): print "\tchecking for: "+red(dep)
	    # filter |or|
	    if dep.find(dbOR) != -1:
	        deps = dep.split(dbOR)
		for i in deps:
		    if getInstalledAtom(i) is not None:
		        dep = i
			break
	    wantedAtom = getBestAtom(dep)
	    if(enzymeRequestVerbose): print "\t\tI want: "+yellow(wantedAtom)
	    installedAtom = getInstalledAtom(dep)
	    if(enzymeRequestVerbose): print "\t\tIs installed: "+green(str(installedAtom))
	    if installedAtom is None:
		# then append - because it's not installed !
		if(enzymeRequestVerbose): print "\t\t"+dep+" is not installed, adding."
		atomDepsTainted = True # taint !
		PackagesDependencies.append(wantedAtom)
	    elif (wantedAtom != installedAtom):
		if (enzymeRequestUpdate):
		    PackagesDependencies.append(wantedAtom)
		    atomDepsTainted = True # taint !
		    if(enzymeRequestVerbose): print "\t\t"+dep+" versions differs, adding (pulled in by --update)."
		else:
		    if (isTbz2PackageAvailable(installedAtom) == False):
			# quickpkg'd
		        PackagesQuickpkg.append("quick|"+installedAtom)
		    else:
			# already available
		        PackagesQuickpkg.append("avail|"+installedAtom)
		    if(enzymeRequestVerbose): print "\t\t"+dep+" versions differs but not adding since the dependency is permissive."
	    else:
		if (isTbz2PackageAvailable(installedAtom) == False):
		    PackagesQuickpkg.append("quick|"+installedAtom)
		if(enzymeRequestVerbose): print "\t\t"+dep+" versions match, no need to build"
	print
	if atomconflicts != []:
	    if(enzymeRequestVerbose): print "\tfiltering "+atom+" conflicts..."
	for conflict in atomconflicts:
	    if(enzymeRequestVerbose): print "\tchecking for: "+red(conflict)
	    if getInstalledAtom(conflict) is not None:
		# damn, it's installed
		if(enzymeRequestVerbose): print "\t\t Package "+yellow(conflict)+" conflicts"
		PackagesConflicting.append(conflict)

	# Now check if its dependency list is empty, in the case, just quickpkg it
	if (enzymeRequestVerbose): print "\n\t"+red("*")+" Package dependencies of: "+atom+" are tainted? --> "+str(atomDepsTainted)
	# add to the packages that can be quickpkg'd
	if (not atomDepsTainted) and (not enzymeRequestForceRebuild) and ( atom == getInstalledAtom(dep_getkey(atom)) ):
	    toBeQuickpkg.append(getInstalledAtom(dep_getkey(atom))) # append the currently installed release ONLY!

    if (enzymeRequestVerbose): print; print

    # Clean out toBeBuilt by removing entries that are in toBeQuickpkg
    _toBeBuilt = []
    for i in toBeBuilt:
	_tbbfound = False
	for x in toBeQuickpkg:
	    if (i == x):
	        _tbbfound = True
	if (not _tbbfound):
	    _toBeBuilt.append(i)
    toBeBuilt = _toBeBuilt

    # Now clean toBeQuickpkg

    if toBeBuilt != []:
	print green("  *")+" This is the list of the packages that have been considered:"

	for i in toBeBuilt:
	    print yellow("     *")+" [BUILD] "+i
	for i in toBeQuickpkg:
	    print green("     *")+" [QUICK] "+i
    else:
	print
	print red("  *")+" No new packages to build, they're all already built or packaged."
    print

    if PackagesDependencies != []:
	print yellow("  *")+" These are their dependencies (pulled in):"
        for i in PackagesDependencies:
	    print red("     *")+bold(" [BUILD] ")+i
	for i in PackagesQuickpkg:
	    if i.startswith("quick|"):
	        print green("     *")+bold(" [QUICK] ")+i.split("quick|")[len(i.split("quick|"))-1]
	    elif i.startswith("avail|"):
	        print green("     *")+bold(" [AVAIL] ")+i.split("avail|")[len(i.split("avail|"))-1]
	    else:
		# I should never get here
	        print green("     *")+bold(" [MERGE] ")+i
        print
    else:
	print green("  *")+" No extra dependencies need to be built"

    
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

    if PackagesDependencies != []:
	print
	print yellow("  *")+" Building dependencies..."
	for dep in PackagesDependencies:
	    outfile = etpConst['packagestmpdir']+"/.emerge-"+str(getRandomNumber())
	    print green("  *")+" Compiling: "+red(dep)+" ... "
	    if (not enzymeRequestVerbose):
		print yellow("     *")+" redirecting output to: "+green(outfile)
		rc, outfile = emerge("="+dep, odbNodeps, outfile, "&>", enzymeRequestSimulation)
	    else:
		rc, outfile = emerge("="+dep,odbNodeps,None,None, enzymeRequestSimulation)
	    if (not rc):
		# compilation is fine
		print green("     *")+" Compiled successfully"
		PackagesQuickpkg.append("quick|"+dep)
		if os.path.isfile(outfile): os.remove(outfile)
	    else:
		print red("     *")+" Compile error"
		if (not enzymeRequestVerbose): print red("     *")+" Log file at: "+outfile
		print
		print
		print red("  ***")+" Cannot continue"
		sys.exit(250)
    
    if toBeBuilt != []:
	print
        print green("  *")+" Building packages..."
	for dep in toBeBuilt:
	    outfile = etpConst['packagestmpdir']+"/.emerge-"+str(getRandomNumber())
	    print green("  *")+" Compiling: "+red(dep)
	    if (not enzymeRequestVerbose):
		print yellow("     *")+" redirecting output to: "+green(outfile)
		rc, outfile = emerge("="+dep, odbNodeps, outfile, "&>", enzymeRequestSimulation)
	    else:
		rc, outfile = emerge("="+dep,odbNodeps, None, None, enzymeRequestSimulation)
	    if (not rc):
		# compilation is fine
		print green("     *")+" Compiled successfully"
		PackagesQuickpkg.append("quick|"+dep)
		if os.path.isfile(outfile): os.remove(outfile)
	    else:
		print red("     *")+" Compile error"
		if (not enzymeRequestVerbose): print red("     *")+" Log file at: "+outfile
		print
		print
		print red("  ***")+" Cannot continue"
		sys.exit(250)

    if (enzymeRequestInteraction):
	# interaction needed
	print green("   *")+" Running etc-update..."
	spawnCommand("etc-update")
    else:
	print green("  *")+" Auto-running etc-update..."
	spawnCommand("echo -5 | etc-update")

    print
    if (PackagesQuickpkg != []) or (toBeQuickpkg != []):
        print green("  *")+" Compressing installed packages..."

	for dep in toBeQuickpkg:
	    dep = dep.split("|")[len(dep.split("|"))-1]
	    print green("  *")+" Compressing: "+red(dep)
	    rc = quickpkg(dep,etpConst['packagesstoredir'])
	    if (rc is not None):
		packagesPaths.append(rc)
	    else:
		print red("      *")+" quickpkg error for "+red(dep)
		print red("  ***")+" Fatal error, cannot continue"
		sys.exit(251)

	for dep in PackagesQuickpkg:
	    dep = dep.split("|")[len(dep.split("|"))-1]
	    print green("  *")+" Compressing: "+red(dep)
	    rc = quickpkg(dep,etpConst['packagesstoredir'])
	    if (rc is not None):
		packagesPaths.append(rc)
	    else:
		print red("      *")+" quickpkg error for "+red(dep)
		print red("  ***")+" Fatal error, cannot continue"
		sys.exit(251)

    if packagesPaths != []:
	print
	print red("   *")+" These are the binary packages created:"
	for pkg in packagesPaths:
	    print green("      * ")+red(pkg)

    return packagesPaths


# World update tool
def world(options):

    myopts = options[1:]

    print "building world :P"

    enzymeRequestVerbose = False
    enzymeRequestRebuild = False
    for i in myopts:
        if ( i == "--verbose" ) or ( i == "-v" ):
	    enzymeRequestVerbose = True
	elif ( i == "--rebuild-all" ):
	    enzymeRequestRebuild = True
	elif ( i == "--update" ):
	    enzymeRequestUpdate = True
	else:
	    print red("  ***")+" Wrong parameters specified."
	    sys.exit(201)

    # translate dir variables
    etpConst['packagessuploaddir'] = translateArch(etpConst['packagessuploaddir'],getPortageEnv('CHOST'))
    etpConst['packagesstoredir'] = translateArch(etpConst['packagesstoredir'],getPortageEnv('CHOST'))
    etpConst['packagesbindir'] = translateArch(etpConst['packagesbindir'],getPortageEnv('CHOST'))

    print "ok... now?"

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

