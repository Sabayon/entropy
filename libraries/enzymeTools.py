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
import string


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
    enzymeNoSyncBack = True
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
	elif ( i == "--sync-back" ):
	    enzymeNoSyncBack = False
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


def build(atoms):
    # FIXME: add USE flags management:
    # packages with new USE flags must be pulled in
    # unless --ignore-new-use-flags is specified

    enzymeRequestVerbose = False
    enzymeRequestForceRepackage = False
    enzymeRequestForceRebuild = False
    enzymeRequestDeep = False
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
	elif ( i == "--ignore-conflicts" ):
	    enzymeRequestIgnoreConflicts = True
	elif ( i == "--pretend" ):
	    enzymeRequestPretendAll = True
	elif ( i == "--deep" ):
	    enzymeRequestDeep = True
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
    
    useFlags = getPortageEnv("USE")
    
    validAtoms = []
    for i in atoms:
        if (enzymeRequestVerbose): print_info(i+" is valid?: "+str(checkAtom(i)))
	if (checkAtom(i)):
	    validAtoms.append(i)
	else:
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
    PackagesDependencies = []
    PackagesConflicting = []
    PackagesQuickpkg = []

    # Check if a .tbz2 has already been done
    # control if --force-rebuild or --force-repackage has been provided
    # and filter the packages list accordingly to line 1
    for atom in validAtoms:
        # let's dance !!
        isAvailable = getInstalledAtom("="+atom)
	if (enzymeRequestVerbose): print_info("testing atom: "+atom)
	if (isAvailable is not None) and (not enzymeRequestForceRepackage):
	    # package is available on the system
	    if (enzymeRequestVerbose): print_info("I'd like to keep a current copy of binary package "+atom+" but first I need to check if even this step has been already done")

	    tbz2Available = isTbz2PackageAvailable(atom, enzymeRequestVerbose)

	    if (tbz2Available == False) or (enzymeRequestForceRebuild):
		if (enzymeRequestVerbose): print_info("Adding "+bold(atom)+" to the build list")
	        toBeBuilt.append(atom)
	    else:
		# no action needed, but showing for consistence
		PackagesQuickpkg.append("avail|"+atom)
	        if (enzymeRequestVerbose): print_info("This "+bold(atom)+" has already been built here: "+tbz2Available)
	else:
            if (enzymeRequestVerbose): print_info("I have to compile or quickpkg "+atom+" by myself...")
	    toBeBuilt.append(atom)

    # Check if they conflicts each others
    if len(toBeBuilt) > 1:
        atoms = string.join(toBeBuilt," =")
    else:
	atoms = "="+atoms[0]
    print_info(green("  Sanity check on packages..."))
    atomdeps, atomconflicts = calculateFullAtomsDependencies(atoms,enzymeRequestDeep)
    for conflict in atomconflicts:
	if getInstalledAtom(conflict) is not None:
	    # damn, it's installed
	    PackagesConflicting.append(conflict)
    if PackagesConflicting != []:
	print_info(red("   *")+" These are the conflicting packages:")
	for i in PackagesConflicting:
	    print_warning(red("      *")+bold(" [CONFL] ")+i)
	if (not enzymeRequestIgnoreConflicts):
	    print_error(red(" ***")+" Sorry, I can't continue. To force this, add --ignore-conflicts at your own risk.")
	    sys.exit(1)
	else:
	    import time
	    print_warning((" ***")+" You are using --ignore-conflicts at your own risk.")
	    time.sleep(5)

    for atom in toBeBuilt:
	print_info("  Analyzing package "+bold(atom)+" ...",back = True)
	atomdeps, atomconflicts = calculateFullAtomsDependencies("="+atom,enzymeRequestDeep)
	if(enzymeRequestVerbose): print_info("  Analyzing package: "+bold(atom))
	if(enzymeRequestVerbose): print_info("  Current installed release: "+bold(str(getInstalledAtom(dep_getkey(atom)))))
	if(enzymeRequestVerbose): print_info("\tfiltering "+atom+" related packages...")
	
	for dep in atomdeps:
	    dep = "="+dep
	    if(enzymeRequestVerbose): print_info("\tchecking for: "+red(dep[1:]))
	    wantedAtom = getBestAtom(dep_getkey(dep))
	    if(enzymeRequestVerbose): print_info("\t\tI want: "+yellow(wantedAtom))
	    installedAtom = getInstalledAtom(dep)
	    if(enzymeRequestVerbose): print_info("\t\tIs installed: "+green(str(installedAtom)))
	    if ( installedAtom is None ) or (enzymeRequestForceRebuild):
		# then append - because it's not installed !
		if(enzymeRequestVerbose) and (installedAtom is None): print_info("\t\t"+dep+" is not installed, adding")
		if(enzymeRequestVerbose) and (enzymeRequestForceRebuild): print_info("\t\t"+dep+" - rebuild forced")
		# do not taint if dep == atom
		PackagesDependencies.append(dep[1:])
	    else:
		if (wantedAtom == installedAtom):
		    if (isTbz2PackageAvailable(installedAtom) == False) or (enzymeRequestForceRepackage):
		        PackagesQuickpkg.append("quick|"+installedAtom)
		        if(enzymeRequestVerbose) and (enzymeRequestForceRepackage): print_info("\t\t"+dep+" versions match, repackaging")
		        if(enzymeRequestVerbose) and ( not enzymeRequestForceRepackage): print_info("\t\t"+dep+" versions match, no need to build")
		else:
		    # adding to the build list
		    if(enzymeRequestVerbose): print_info("\t\t"+dep+" versions not match, adding")
		    PackagesDependencies.append(dep[1:])

    # Clean out toBeBuilt by removing entries that are in PackagesQuickpkg
    _toBeBuilt = []
    for i in toBeBuilt:
	_tbbfound = False
	for x in PackagesQuickpkg:
	    if (i == x):
	        _tbbfound = True
	if (not _tbbfound):
	    _toBeBuilt.append(i)
    toBeBuilt = _toBeBuilt

    if PackagesDependencies != []:
	print_info(yellow("  *")+" These are the actions that will be taken, in order:")
        for i in PackagesDependencies:
	    #print "'"+i+"'"
	    pkgstatus = "[?]"
	    if (getInstalledAtom(dep_getkey(i)) == None):
		pkgstatus = green("[N]")
	    elif (compareAtoms(i,getInstalledAtom(dep_getkey(i))) == 0):
		pkgstatus = yellow("[R]")
	    elif (compareAtoms(i,getInstalledAtom(dep_getkey(i))) > 0):
		pkgstatus = blue("[U]")
	    elif (compareAtoms(i,getInstalledAtom(dep_getkey(i))) < 0):
		pkgstatus = darkblue("[D]")
	    print_info(red("     *")+bold(" [")+red("BUILD")+bold("] ")+pkgstatus+" "+i)
	
	for i in PackagesQuickpkg:
	    if i.startswith("quick|"):
	        print_info(green("     *")+bold(" [")+green("QUICK")+bold("] ")+yellow("[R] ") +i.split("quick|")[len(i.split("quick|"))-1])
	    elif i.startswith("avail|"):
	        print_info(yellow("     *")+bold(" [")+yellow("NOACT")+bold("] ")+yellow("[R] ")+i.split("avail|")[len(i.split("avail|"))-1])
	    else:
		# I should never get here
	        print_info(green("     *")+bold(" [?????] ")+i)
    else:
	print_info(green("  *")+" No extra dependencies need to be built")


    if (enzymeRequestPretendAll):
	sys.exit(0)
	
    # when the compilation ends, enzyme runs reagent
    packagesPaths = []

    if PackagesDependencies != []:
	#print
	print_info(yellow("  *")+" Building packages...")
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

    if (enzymeRequestInteraction):
	# interaction needed
	print_info(green("   *")+" Running etc-update...")
	spawnCommand("etc-update")
    else:
	print_info(green("  *")+" Auto-running etc-update...")
	spawnCommand("echo -5 | etc-update")

    # remove avail| packages from the list
    _PackagesQuickpkg = []
    for i in PackagesQuickpkg:
	if not dep.startswith("avail|"):
	    _PackagesQuickpkg.append(i)
    PackagesQuickpkg = _PackagesQuickpkg

    if (PackagesQuickpkg != []):
        print_info(green("  *")+" Compressing installed packages...")

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

    # Now we have packagesPaths that contains all the compressed packages
    # We need to run the runtime dependencies detection on them and quickpkg
    # the rest of the needed packages if they're not available in the store.
    # FIXME: add --no-runtime-dependencies
    runtimeDepsPackages = []
    runtimeDepsQuickpkg = []
    if packagesPaths != []:
	print_info(yellow("  *")+" Calculating runtime dependencies...")
        for file in packagesPaths:
	    print_info(red("   *")+green(" Calculating runtime dependencies for ")+bold(file.split("/")[len(file.split("/"))-1]))
            # unpack the .tbz2 file
            tbz2TmpDir = unpackTbz2(file)
            # parse, if exists, the NEEDED file
            runtimeNeededPackages, runtimeNeededPackagesXT = getPackageRuntimeDependencies(tbz2TmpDir+dbNEEDED)
	    for i in runtimeNeededPackagesXT:
		if (enzymeRequestVerbose): print_info(green("     * ")+yellow("depends on: "+bold(i)))
		runtimeDepsPackages.append(i)
	    os.system("rm -rf "+tbz2TmpDir)

    # filter dups
    runtimeDepsPackages = list(set(runtimeDepsPackages))
    # now it's time to check the packages that need to be compressed
    for atom in runtimeDepsPackages:
	if (not isTbz2PackageAvailable(atom)):
	    if (enzymeRequestVerbose): print_info(yellow("   * ")+"I would like to quickpkg "+bold(atom))
	    runtimeDepsQuickpkg.append(atom)

    if runtimeDepsQuickpkg != []:
	print_info(yellow("  *")+" Compressing runtime dependencies...")
	for atom in runtimeDepsQuickpkg:
	    # quickpkg!
	    print_info(yellow("   *")+" Compressing "+red(atom))
	    rc = quickpkg(atom,etpConst['packagesstoredir'])
	    if (rc is not None):
		packagesPaths.append(rc)
	    else:
		print_error(red("      *")+" quickpkg error for "+red(atom))
		print_error(red("  ***")+" Fatal error, cannot continue")
		sys.exit(251)

    if packagesPaths != []:
	#print
	print_info(red("  *")+" These are the binary packages created:")
	for pkg in packagesPaths:
	    print_info(green("     * ")+red(pkg))

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
    #FIXME: add sync-back to the official Portage Tree?
    
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

    # Filter extra commands
    enzymeRequestVerbose = False
    enzymeUninstallRedirect = "&>/dev/null"
    enzymeRequestSimulation = False
    enzymeRequestPrune = False
    _atoms = []
    for i in options:
        if ( i == "--verbose" ) or ( i == "-v" ):
	    enzymeRequestVerbose = True
	    enzymeUninstallRedirect = None
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
	if (checkAtom(i)):
	    if (getInstalledAtom(dep_getkey(i)) != None):
	        validAtoms.append(i)
	    else:
		print_info(red("* >>> ")+yellow(i)+" is not installed.")
	else:
	    #print
	    print_warning(red("* >>> ")+yellow(i)+" is not a valid atom, it's masked or its name conflicts with something else.")
	    if getBestAtom(i) == "!!conflicts":
		# it conflicts with something
		print_warning(red("* ^^^ ")+"Ambiguous package name. Please add category.")

    # Filter duplicates
    validAtoms = list(set(validAtoms))
    _validAtoms = []
    for atom in validAtoms:
	if (atom.find("/") == -1):
	    # add pkgcat
	    atom = getAtomCategory(atom)+"/"+atom
	_validAtoms.append(atom)
    validAtoms = _validAtoms

    uninstallText = yellow("   * ")+"Doing "

    # Now check if a package has been specified more than once
    _validAtoms = []
    for seedAtom in validAtoms:
	_dupAtom = False
	for subAtom in validAtoms:
	    if ((seedAtom.find(subAtom) != -1) or (subAtom.find(seedAtom) != -1)) and (seedAtom != subAtom):
		_dupAtom = True
	if (not _dupAtom):
	    _validAtoms.append(seedAtom)
	else:
	    print_warning(red("* >>> ")+"You have specified "+yellow(seedAtom)+" more than once. Removing from list.")
    validAtoms = _validAtoms

    if validAtoms == []:
        print_error(red(bold("no valid package names specified.")))
	sys.exit(102)

    if (not enzymeRequestPrune):
	uninstallText += bold("unmerge ")
	portageCmd = cdbRunEmerge+" -C "
	print_info(green("  *")+" This is the list of the packages that would be removed, if installed:")
	for i in validAtoms:
	    installedAtoms = getInstalledAtoms(i)
	    installedVers = []
	    for i in installedAtoms:
		pkgname, pkgver = extractPkgNameVer(i)
		installedVers.append(pkgver)
	    if len(installedVers) > 1:
		x = string.join(installedVers)
		print_info(yellow("     *")+" [REMOVE] "+bold(dep_getkey(i))+" [ selected: "+red(x)+" ]")
	    else:
		installedVer = installedVers[0]
		print_info(yellow("     *")+" [REMOVE] "+bold(dep_getkey(i))+" [ selected: "+red(installedVer)+" ]")
    else:
	uninstallText += bold("prune ")
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
		selected = atom
		protected = None
		omitted = None
		if isjustname(atom) == 1:
		    # if the user provide only the name, then parse the list of the packages
		    rc = commands.getoutput(portageCmd+" --quiet --pretend --color=n "+atom).split("\n")
		    for i in rc:
			if i.find("selected:") != -1:
			    selected = i.strip().split(":")[1][1:]
			if i.find("protected:") != -1:
			    protected = i.strip().split(":")[1][1:]
			if i.find("omitted:") != -1:
			    omitted = i.strip().split(":")[1][1:]
		print_info(yellow("     *")+" [PRUNE] "+bold(atom)+" [ selected: "+red(string.lower(str(selected)))+"; protected: "+green(string.lower(str(protected)))+"; omitted: "+yellow(string.lower(str(omitted)))+" ]")
	else:
	    print_info(green("  *")+" No packages to prune.")

    # if --pretend, end here
    if (enzymeRequestSimulation):
	sys.exit(0)

    for atom in validAtoms:
	print_info(uninstallText+red(atom))
        # now run the command
        rc = spawnCommand(portageCmd+"'"+atom+"'",enzymeUninstallRedirect)
	if (rc):
	    print_warning(yellow("  *** ")+red("Something weird happened while running the action on ")+bold(atom))
	    if (not enzymeRequestVerbose):
		print_warning(yellow("  *** ")+red("Please use --verbose and retry to see what was wrong. Continuing..."))
	else:
	    print_info(green("   * ")+bold(atom)+" worked out successfully.")

# Temporary files cleaner
def cleanup(options):

    toCleanDirs = [ etpConst['packagestmpdir'] ]
    counter = 0

    for dir in toCleanDirs:
        print_info(red(" * ")+"Cleaning "+yellow(dir)+" directory...", back = True)
	dircontent = os.listdir(dir)
	if dircontent != []:
	    for data in dircontent:
		os.system("rm -rf "+dir+"/"+data)
		counter += 1

    print_info(green(" * ")+"Cleaned: "+str(counter)+" files and directories")