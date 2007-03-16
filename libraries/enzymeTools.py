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
    myopts = options[1:]
    enzymeNoSyncBack = False
    enzymeOnlySyncBack = False
    enzymeNoOverlaySync = False
    syncMiscRedirect = "> /dev/null"

    # check if rsync is installed
    rsync = commands.getoutput("which rsync")
    if (not rsync.startswith("/")):
        print_error(red(bold("net-misc/rsync is not installed. Please install.")))
	sys.exit(100)

    for i in myopts:
        if ( i == "--verbose" ) or ( i == "-v" ):
	    syncMiscRedirect = None
	elif ( i == "--no-sync-back" ):
	    enzymeNoSyncBack = True
	elif ( i == "--only-sync-back" ):
	    enzymeOnlySyncBack = True
	elif ( i == "--no-overlay-sync" ):
	    enzymeNoOverlaySync = True

    if (not enzymeOnlySyncBack):
	print_info(green("Syncing Entropy Portage Tree at: "+etpConst['portagetreedir']))
	rc = spawnCommand(vdbPORTDIR+"="+etpConst['portagetreedir']+" "+cdbEMERGE+" --sync ", redirect = syncMiscRedirect) # redirect = "/dev/null"
	if (rc != 0):
	    print_error(red("an error occoured while syncing the Portage tree. Are you sure that your Internet connection works?"))
	    sys.exit(101)
	if (not enzymeNoOverlaySync):
	    # syncing overlays
	    rc = overlay(['overlay','sync'])
	    if (not rc):
	        print_warning(red("an error occoured while syncing the overlays. Please check if it's all fine."))
	
    else:
	print_info(green("Not syncing Entropy Portage Tree at: "+etpConst['portagetreedir']))

    if (not enzymeNoSyncBack):
	print_info(green("Syncing back Entropy Portage Tree at: ")+bold(etpConst['portagetreedir'])+green(" to the official Portage Tree"))
	# sync back to /usr/portage, but firstly, get user's PORTDIR
	if os.path.isfile("/etc/make.conf"):
	    f = open("/etc/make.conf","r")
	    makeConf = f.readlines()
	    f.close()
	    officialPortageTreeDir = "/usr/portage"
	    for line in makeConf:
		if line.startswith("PORTDIR="):
		    # found it !
		    line = line.strip()
		    officialPortageTreeDir = line.split('PORTDIR=')[1]
		    # remove quotes
		    if officialPortageTreeDir.startswith('"') and officialPortageTreeDir.endswith('"'):
			officialPortageTreeDir = officialPortageTreeDir.split('"')[1]
		    if officialPortageTreeDir.startswith("'") and officialPortageTreeDir.endswith("'"):
			officialPortageTreeDir = officialPortageTreeDir.split("'")[1]
	else:
	    officialPortageTreeDir = "/usr/portage"
	
	# officialPortageTreeDir must not end with /
	if officialPortageTreeDir.endswith("/"):
	    officialPortageTreeDir = officialPortageTreeDir[:len(officialPortageTreeDir)-1]
	
	# sync back
	rc = spawnCommand("rsync --recursive --links --safe-links --perms --times --force --whole-file --delete --delete-after --exclude=/distfiles --exclude=/packages "+etpConst['portagetreedir']+" "+officialPortageTreeDir, redirect = syncMiscRedirect)
	if (rc != 0):
	    print_error(red("an error occoured while syncing back the official Portage Tree."))
	    sys.exit(101)
    else:
	print_info(yellow("Official Portage Tree sync-back disabled"))


def build(atoms):

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
    
    # translate dir variables
    etpConst['packagessuploaddir'] = translateArch(etpConst['packagessuploaddir'],getPortageEnv('CHOST'))
    etpConst['packagesstoredir'] = translateArch(etpConst['packagesstoredir'],getPortageEnv('CHOST'))
    etpConst['packagesbindir'] = translateArch(etpConst['packagesbindir'],getPortageEnv('CHOST'))
    
    validAtoms = []
    for i in atoms:
        if (enzymeRequestVerbose): print_info(i+" is valid?: "+str(checkAtom(i)))
	if (checkAtom(i)):
	    validAtoms.append(i)
	else:
	    #print
	    print_warning(red("* >>> ")+yellow(i)+" is not a valid atom, it's masked or its name conflicts with something else.")
	    if getBestAtom(i) == "!!conflicts":
		# it conflicts with something
		print_warning(red("* ^^^ ")+"Ambiguous package name. Please add category.")

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
	if (enzymeRequestVerbose): print_info("testing atom: "+atom)
	if (isAvailable is not None) and (not enzymeRequestForceRepackage):
	    # package is available on the system
	    if (enzymeRequestVerbose): print_info("I'd like to keep a current copy of binary package "+atom+" but first I need to check if even this step has been already done")

	    tbz2Available = isTbz2PackageAvailable(atom, enzymeRequestVerbose)

	    if (tbz2Available == False) or (enzymeRequestForceRebuild):
		if (enzymeRequestVerbose): print_info("Do I really have to build "+bold(atom)+" ?")
	        toBeBuilt.append(atom)
	    else:
	        if (enzymeRequestVerbose): print_info("I will use this already precompiled package: "+tbz2Available)
	else:
            if (enzymeRequestVerbose): print_info("I have to compile or quickpkg "+atom+" by myself...")
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
	#print
	# check its unsatisfied dependencies
	print_info("  Checking "+bold(atom)+" dependencies and conflicts...")
	atomdeps, atomconflicts = synthetizeRoughDependencies(getPackageDependencyList(atom))
	atomdeps = atomdeps.split()
	atomconflicts = atomconflicts.split()
	print_info("  Current installed release: "+bold(str(getInstalledAtom(dep_getkey(atom)))))
	#if(enzymeRequestVerbose): print
	if(enzymeRequestVerbose): print_info("\tfiltering "+atom+" dependencies...")
	# check if the dependency is satisfied
	
	for dep in atomdeps:
	    if(enzymeRequestVerbose): print_info("\tchecking for: "+red(dep))
	    # filter |or|
	    if dep.find(dbOR) != -1:
	        deps = dep.split(dbOR)
		for i in deps:
		    if getInstalledAtom(i) is not None:
		        dep = i
			break
	    wantedAtom = getBestAtom(dep)
	    if(enzymeRequestVerbose): print_info("\t\tI want: "+yellow(wantedAtom))
	    installedAtom = getInstalledAtom(dep)
	    if(enzymeRequestVerbose): print_info("\t\tIs installed: "+green(str(installedAtom)))
	    if installedAtom is None:
		# then append - because it's not installed !
		if(enzymeRequestVerbose): print_info("\t\t"+dep+" is not installed, adding.")
		atomDepsTainted = True # taint !
		PackagesDependencies.append(wantedAtom)
	    elif (wantedAtom != installedAtom):
		if (enzymeRequestUpdate):
		    PackagesDependencies.append(wantedAtom)
		    atomDepsTainted = True # taint !
		    if(enzymeRequestVerbose): print_info("\t\t"+dep+" versions differs, adding (pulled in by --update).")
		else:
		    if (isTbz2PackageAvailable(installedAtom) == False):
			# quickpkg'd
		        PackagesQuickpkg.append("quick|"+installedAtom)
		    else:
			# already available
		        PackagesQuickpkg.append("avail|"+installedAtom)
		    if(enzymeRequestVerbose): print_info("\t\t"+dep+" versions differs but not adding since the dependency is permissive.")
	    else:
		if (isTbz2PackageAvailable(installedAtom) == False):
		    PackagesQuickpkg.append("quick|"+installedAtom)
		if(enzymeRequestVerbose): print_info("\t\t"+dep+" versions match, no need to build")
	#print
	if atomconflicts != []:
	    if(enzymeRequestVerbose): print_info("\tfiltering "+atom+" conflicts...")
	for conflict in atomconflicts:
	    if(enzymeRequestVerbose): print_info("\tchecking for: "+red(conflict))
	    if getInstalledAtom(conflict) is not None:
		# damn, it's installed
		if(enzymeRequestVerbose): print_info("\t\t Package "+yellow(conflict)+" conflicts")
		PackagesConflicting.append(conflict)

	# Now check if its dependency list is empty, in the case, just quickpkg it
	if (enzymeRequestVerbose): print_info("\n\t"+red("*")+" Package dependencies of: "+atom+" are tainted? --> "+str(atomDepsTainted))
	# add to the packages that can be quickpkg'd
	if (not atomDepsTainted) and (not enzymeRequestForceRebuild) and ( atom == getInstalledAtom(dep_getkey(atom)) ):
	    toBeQuickpkg.append(getInstalledAtom(dep_getkey(atom))) # append the currently installed release ONLY!

    #if (enzymeRequestVerbose): print; print

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
	print_info(green("  *")+" This is the list of the packages that have been considered:")

	for i in toBeBuilt:
	    print_info(yellow("     *")+" [BUILD] "+i)
	for i in toBeQuickpkg:
	    print_info(green("     *")+" [QUICK] "+i)
    else:
	#print
	print_info(red("  *")+" No new packages to build, they're all already built or packaged.")
    #print

    if PackagesDependencies != []:
	print_info(yellow("  *")+" These are their dependencies (pulled in):")
        for i in PackagesDependencies:
	    print_info(red("     *")+bold(" [BUILD] ")+i)
	for i in PackagesQuickpkg:
	    if i.startswith("quick|"):
	        print_info(green("     *")+bold(" [QUICK] ")+i.split("quick|")[len(i.split("quick|"))-1])
	    elif i.startswith("avail|"):
	        print_info(green("     *")+bold(" [AVAIL] ")+i.split("avail|")[len(i.split("avail|"))-1])
	    else:
		# I should never get here
	        print_info(green("     *")+bold(" [MERGE] ")+i)
        #print
    else:
	print_info(green("  *")+" No extra dependencies need to be built")

    
    if PackagesConflicting != []:
	print_info(red("   *")+" These are the conflicting packages:")
	for i in PackagesConflicting:
	    print_warning(red("      *")+bold(" [CONFL] ")+i)
	if (not enzymeRequestIgnoreConflicts):
	    #print
	    #print
	    print_error(red(" ***")+" Sorry, I can't continue. To force this, add --ignore-conflicts at your own risk.")
	    sys.exit(1)
	else:
	    import time
	    #print
	    print_warning((" ***")+" You are using --ignore-conflicts at your own risk.")
	    #print
	    time.sleep(5)

    if (enzymeRequestPretendAll):
	sys.exit(0)
	
    # when the compilation ends, enzyme runs reagent
    packagesPaths = []

    if PackagesDependencies != []:
	#print
	print_info(yellow("  *")+" Building dependencies...")
	for dep in PackagesDependencies:
	    outfile = etpConst['packagestmpdir']+"/.emerge-"+str(getRandomNumber())
	    print_info(green("  *")+" Compiling: "+red(dep)+" ... ")
	    if (not enzymeRequestVerbose):
		print_info(yellow("     *")+" redirecting output to: "+green(outfile))
		rc, outfile = emerge("="+dep, odbNodeps, outfile, "&>", enzymeRequestSimulation)
	    else:
		rc, outfile = emerge("="+dep,odbNodeps,None,None, enzymeRequestSimulation)
	    if (not rc):
		# compilation is fine
		print_info(green("     *")+" Compiled successfully")
		PackagesQuickpkg.append("quick|"+dep)
		if os.path.isfile(outfile): os.remove(outfile)
	    else:
		print_error(red("     *")+" Compile error")
		if (not enzymeRequestVerbose): print_info(red("     *")+" Log file at: "+outfile)
		#print
		#print
		print_error(red("  ***")+" Cannot continue")
		sys.exit(250)
    
    if toBeBuilt != []:
	#print
        print_info(green("  *")+" Building packages...")
	for dep in toBeBuilt:
	    outfile = etpConst['packagestmpdir']+"/.emerge-"+str(getRandomNumber())
	    print_info(green("  *")+" Compiling: "+red(dep))
	    if (not enzymeRequestVerbose):
		print_info(yellow("     *")+" redirecting output to: "+green(outfile))
		rc, outfile = emerge("="+dep, odbNodeps, outfile, "&>", enzymeRequestSimulation)
	    else:
		rc, outfile = emerge("="+dep,odbNodeps, None, None, enzymeRequestSimulation)
	    if (not rc):
		# compilation is fine
		print_info(green("     *")+" Compiled successfully")
		PackagesQuickpkg.append("quick|"+dep)
		if os.path.isfile(outfile): os.remove(outfile)
	    else:
		print_error(red("     *")+" Compile error")
		if (not enzymeRequestVerbose): print_info(red("     *")+" Log file at: "+outfile)
		#print
		#print
		print_error(red("  ***")+" Cannot continue")
		sys.exit(250)

    if (enzymeRequestInteraction):
	# interaction needed
	print_info(green("   *")+" Running etc-update...")
	spawnCommand("etc-update")
    else:
	print_info(green("  *")+" Auto-running etc-update...")
	spawnCommand("echo -5 | etc-update")

    #print
    if (PackagesQuickpkg != []) or (toBeQuickpkg != []):
        print_info(green("  *")+" Compressing installed packages...")

	for dep in toBeQuickpkg:
	    dep = dep.split("|")[len(dep.split("|"))-1]
	    print_info(green("  *")+" Compressing: "+red(dep))
	    rc = quickpkg(dep,etpConst['packagesstoredir'])
	    if (rc is not None):
		packagesPaths.append(rc)
	    else:
		print_error(red("      *")+" quickpkg error for "+red(dep))
		print_error(red("  ***")+" Fatal error, cannot continue")
		sys.exit(251)

	for dep in PackagesQuickpkg:
	    dep = dep.split("|")[len(dep.split("|"))-1]
	    print_info(green("  *")+" Compressing: "+red(dep))
	    rc = quickpkg(dep,etpConst['packagesstoredir'])
	    if (rc is not None):
		packagesPaths.append(rc)
	    else:
		print_error(red("      *")+" quickpkg error for "+red(dep))
		print_error(red("  ***")+" Fatal error, cannot continue")
		sys.exit(251)

    if packagesPaths != []:
	#print
	print_info(red("   *")+" These are the binary packages created:")
	for pkg in packagesPaths:
	    print_info(green("      * ")+red(pkg))

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

def uninstall(options):

    # FIXME: add --prune option? (--just-prune)
    
    # Filter extra commands
    enzymeRequestVerbose = False
    enzymeRequestSimulation = False
    enzymeRequestPrune = False
    _atoms = []
    for i in options:
        if ( i == "--verbose" ) or ( i == "-v" ):
	    enzymeRequestVerbose = True
	elif ( i == "--pretend" ):
	    enzymeRequestSimulation = True
	elif ( i == "--just-prune" ):
	    enzymeRequestPrune = True
	else:
	    _atoms.append(i)
    atoms = _atoms
    
    if (enzymeRequestVerbose): print_info(i+" is Pretend?: "+str(enzymeRequestSimulation))
    if (enzymeRequestVerbose): print_info(i+" is Prune?: "+str(enzymeRequestPrune))

    validAtoms = []
    for i in atoms:
        if (enzymeRequestVerbose): print_info(i+" is valid?: "+str(checkAtom(i)))
	if (checkAtom(i)) and (getInstalledAtom(dep_getkey(i)) != None):
	    validAtoms.append(i)
	else:
	    #print
	    print_warning(red("* >>> ")+yellow(i)+" is not a valid atom, it's masked or its name conflicts with something else.")
	    if getBestAtom(i) == "!!conflicts":
		# it conflicts with something
		print_warning(red("* ^^^ ")+"Ambiguous package name. Please add category.")

    # Filter duplicates
    validAtoms = list(set(validAtoms))

    if validAtoms == []:
        print_error(red(bold("no valid package names specified.")))
	sys.exit(102)

    if (not enzymeRequestPrune):
	portageCmd = cdbRunEmerge+" -C "
	print_info(green("  *")+" This is the list of the packages that would be removed, if installed:")
	for i in validAtoms:
	    installedAtoms = getInstalledAtoms(i)
	    installedVers = []
	    for i in installedAtoms:
		pkgname, pkgver = extractPkgNameVer(i)
		installedVers.append(pkgver)
	    if len(installedVers) > 1:
		import string
		x = string.join(installedVers)
		print_info(yellow("     *")+" [REMOVE] "+bold(i)+" [ selected: "+red(x)+" ]")
	    else:
		print_info(yellow("     *")+" [REMOVE] "+bold(i))
    else:
	# FIXME: rewrite this using Portage Python bindings directly?
	portageCmd = cdbRunEmerge+" -P "
	# filter unpruneable packages
	_validAtoms = []
	for atom in validAtoms:
	    rc = commands.getoutput(portageCmd+" --quiet --pretend "+atom)
	    if (rc != ''):
		_validAtoms.append(atom)
	validAtoms = _validAtoms
	if validAtoms != []:
	    print_info(green("  *")+" This is the list of the packages that would be pruned, if possible:")
	    for atom in validAtoms:
		if isjustname(atom) == 1:
		    # if the user provide only the name, then parse the list of the packages
		    rc = commands.getoutput(portageCmd+" --quiet --pretend --color=n "+atom).split("\n")
		    selected = None
		    protected = None
		    omitted = None
		    for i in rc:
			if i.find("selected:") != -1:
			    selected = i.strip().split(":")[1]
			if i.find("protected:") != -1:
			    protected = i.strip().split(":")[1]
			if i.find("omitted:") != -1:
			    omitted = i.strip().split(":")[1]
		print_info(yellow("     *")+" [PRUNE] "+bold(atom)+" [ selected:"+red(selected)+"; protected:"+green(protected)+"; omitted:"+yellow(omitted)+" ]")
	else:
	    print_info(green("  *")+" No packages to prune.")

    # if --pretend, end here
    if (enzymeRequestSimulation):
	sys.exit(0)

    
    # now wrap emerge -C
    