#!/usr/bin/python
'''
    # DESCRIPTION:
    # generic tools for all the handlers applications

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

def initializePortageTree():
    portage.settings.unlock()
    portage.settings['PORTDIR'] = etpConst['portagetreedir']
    portage.settings.lock()
    portage.portdb.__init__(etpConst['portagetreedir'])

import portage
import portage_const
from portage_dep import isvalidatom, isjustname, dep_getkey
from entropyConstants import *
initializePortageTree()

# colours support
import output
from output import bold, colorize, green, red, yellow
import re

def isRoot():
    import getpass
    if (getpass.getuser() == "root"):
        return True
    return False

def getPortageEnv(var):
    return portage.config(clone=portage.settings).environ()[var]

def getThirdPartyMirrors(mirrorname):
    return portage.thirdpartymirrors[mirrorname]

# resolve atoms automagically (best, not current!)
# sys-libs/application --> sys-libs/application-1.2.3-r1
def getBestAtom(atom):
    return portage.portdb.xmatch("bestmatch-visible",str(atom))

def getArchFromChost(chost):
	# when we'll add new archs, we'll have to add a testcase here
	if chost.startswith("x86_64"):
	    resultingArch = "amd64"
	elif chost.split("-")[0].startswith("i") and chost.split("-")[0].endswith("86"):
	    resultingArch = "x86"
	else:
	    resultingArch = "ERROR"
	
	return resultingArch

def translateArch(string,chost):
    if string.find(ETP_ARCH_CONST) != -1:
        # substitute %ARCH%
        resultingArch = getArchFromChost(chost)
	return re.subn(ETP_ARCH_CONST,resultingArch, string)[0]
    else:
	return string

def getInstalledAtom(atom):
    rc = portage.db['/']['vartree'].dep_match(str(atom))
    if (rc != []):
        return rc[len(rc)-1]
    else:
        return None
    

def checkAtom(atom):
    if (isvalidatom(atom) == 1) or ( getBestAtom(atom) != ""):
        return True
    return False

def removeSpaceAtTheEnd(string):
    if string.endswith(" "):
        return string[:len(string)-1]
    else:
	return string

def md5sum(filepath):
    import md5
    m = md5.new()
    readfile = file(filepath)
    block = readfile.read(1024)
    while block:
        m.update(block)
	block = readfile.read(1024)
    return m.hexdigest()

# Tool to run commands
def spawnCommand(command, redirect = None):
    if redirect is not None:
        command += " "+redirect
    rc = os.system(command)
    return rc

def getPackageDependencyList(atom):
    pkgSplittedDeps = []
    tmp = portage.portdb.aux_get(atom, ["DEPEND"])[0].split()
    for i in tmp:
	pkgSplittedDeps.append(i)
    tmp = portage.portdb.aux_get(atom, ["RDEPEND"])[0].split()
    for i in tmp:
	pkgSplittedDeps.append(i)
    tmp = portage.portdb.aux_get(atom, ["PDEPEND"])[0].split()
    for i in tmp:
	pkgSplittedDeps.append(i)
    return pkgSplittedDeps

def getUSEFlags():
    return getPortageEnv('USE')

def synthetizeRoughDependencies(roughDependencies, useflags = None):
    if useflags is None:
        useflags = getUSEFlags()
    # returns dependencies, conflicts

    useMatch = False
    openParenthesis = 0
    openOr = False
    useFlagQuestion = False
    dependencies = ""
    conflicts = ""
    for atom in roughDependencies:

	if atom.endswith("?"):
	    # we need to see if that useflag is enabled
	    useFlag = atom.split("?")[0]
	    useFlagQuestion = True
	    for i in useflags.split():
		if i.startswith("!"):
		    if (i != useFlag):
			useMatch = True
			break
		else:
		    if (i == useFlag):
		        useMatch = True
		        break

        if atom.startswith("("):
	    openParenthesis += 1

        if atom.startswith(")"):
	    if (openOr):
		# remove last "_or_" from dependencies
		openOr = False
		if dependencies.endswith(dbOR):
		    dependencies = dependencies[:len(dependencies)-len(dbOR)]
		    dependencies += " "
	    openParenthesis -= 1
	    if (openParenthesis == 0):
		useFlagQuestion = False
		useMatch = False

        if atom.startswith("||"):
	    openOr = True
	
	if atom.find("/") != -1 and (not atom.startswith("!")) and (not atom.endswith("?")):
	    # it's a package name <pkgcat>/<pkgname>-???
	    if ((useFlagQuestion) and (useMatch)) or ((not useFlagQuestion) and (not useMatch)):
	        # check if there's an OR
		dependencies += atom
		if (openOr):
		    dependencies += dbOR
                else:
		    dependencies += " "

        if atom.startswith("!") and (not atom.endswith("?")):
	    if ((useFlagQuestion) and (useMatch)) or ((not useFlagQuestion) and (not useMatch)):
		conflicts += atom
		if (openOr):
		    conflicts += dbOR
                else:
		    conflicts += " "
		

    # format properly
    tmpConflicts = list(set(conflicts.split()))
    conflicts = ''
    for i in tmpConflicts:
	i = i[1:] # remove "!"
	conflicts += i+" "
    conflicts = removeSpaceAtTheEnd(conflicts)

    tmpDeps = list(set(dependencies.split()))
    dependencies = ''
    for i in tmpDeps:
	dependencies += i+" "
    dependencies = removeSpaceAtTheEnd(dependencies)

    return dependencies, conflicts


def print_error(msg):
    print "* erro *  : "+msg

def print_info(msg):
    print "* info *  : "+msg

def print_warning(msg):
    print "* warn *  : "+msg

def print_generic(msg): # here we'll wrap any nice formatting
    print msg