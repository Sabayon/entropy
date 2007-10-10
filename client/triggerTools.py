#!/usr/bin/python
'''
    # DESCRIPTION:
    # Equo general purpose triggering scripts for pre/post install and remove 

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
import os
sys.path.append('../libraries')
from outputTools import *
import entropyTools


'''
   @description: pkgdata parser that collects post-install scripts that would be run
'''
def postinstall(pkgdata):
    
    functions = []
    
    # fonts configuration
    if pkgdata['category'] == "media-fonts":
	functions.append("fontconfig")

    # gcc configuration
    if pkgdata['category']+"/"+pkgdata['name'] == "sys-devel/gcc":
	functions.append("gccswitch")

    # icons cache setup
    mycnt = set(pkgdata['content'])
    for file in mycnt:
	if file.startswith("/usr/share/icons") and file.endswith("index.theme"):
	    functions.append('iconscache')
	    break

    return functions


########################################################
####
##   Public functions
#

def fontconfig(pkgdata):
    fontdirs = set()
    for xdir in pkgdata['content']:
	if xdir.startswith("/usr/share/fonts"):
	    origdir = xdir[16:]
	    if origdir:
		if origdir.startswith("/"):
		    origdir = origdir.split("/")[1]
		    if os.path.isdir(xdir[:16]+"/"+origdir):
		        fontdirs.add(xdir[:16]+"/"+origdir)
    if (fontdirs):
	print_info(" "+brown("[POST] Configuring fonts directory..."))
    for fontdir in fontdirs:
	setupfontdir(fontdir)
	setupfontcache(fontdir)

def gccswitch(pkgdata):
    print_info(" "+brown("[POST] Configuring GCC Profile..."))
    # get gcc profile
    pkgsplit = entropyTools.catpkgsplit(pkgdata['category']+"/"+pkgdata['name']+"-"+pkgdata['version'])
    profile = pkgdata['chost']+"-"+pkgsplit[2]
    setgccprofile(profile)

def iconscache(pkgdata):
    print_info(" "+brown("[POST] Updating icons cache..."))
    mycnt = set(pkgdata['content'])
    for file in mycnt:
	if file.startswith("/usr/share/icons") and file.endswith("index.theme"):
	    cachedir = os.path.dirname(file)
	    generateiconscache(cachedir)

########################################################
####
##   Internal functions
#

'''
   @description: creates Xfont files
   @output: returns int() as exit status
'''
def setupfontdir(fontdir):
    # mkfontscale
    if os.access('/usr/bin/mkfontscale',os.X_OK):
	os.system('/usr/bin/mkfontscale '+unicode(fontdir))
    # mkfontdir
    if os.access('/usr/bin/mkfontdir',os.X_OK):
	os.system('/usr/bin/mkfontdir -e /usr/share/fonts/encodings -e /usr/share/fonts/encodings/large '+unicode(fontdir))
    return 0

'''
   @description: creates font cache
   @output: returns int() as exit status
'''
def setupfontcache(fontdir):
    # fc-cache -f gooooo!
    if os.access('/usr/bin/fc-cache',os.X_OK):
	os.system('HOME="/root" /usr/bin/fc-cache -f '+unicode(fontdir))
    return 0

'''
   @description: set chosen gcc profile
   @output: returns int() as exit status
'''
def setgccprofile(profile):
    if os.access('/usr/bin/gcc-config',os.X_OK):
	os.system('/usr/bin/gcc-config '+profile)
    return 0

'''
   @description: creates/updates icons cache
   @output: returns int() as exit status
'''
def generateiconscache(cachedir):
    if os.access('/usr/bin/gtk-update-icon-cache',os.X_OK):
	os.system('/usr/bin/gtk-update-icon-cache -qf '+cachedir)
    return 0
