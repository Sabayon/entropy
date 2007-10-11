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
import commands
sys.path.append('../libraries')
from outputTools import *
import entropyTools

'''
   @ description: Gentoo toolchain variables
'''
MODULEDB_DIR="/var/lib/module-rebuild/"

'''
   @description: pkgdata parser that collects post-install scripts that would be run
'''
def postinstall(pkgdata):
    
    functions = set()
    
    # fonts configuration
    if pkgdata['category'] == "media-fonts":
	functions.append("fontconfig")

    # gcc configuration
    if pkgdata['category']+"/"+pkgdata['name'] == "sys-devel/gcc":
	functions.append("gccswitch")

    # binutils configuration
    if pkgdata['category']+"/"+pkgdata['name'] == "sys-devel/binutils":
	functions.append("binutilsswitch")

    # icons cache setup
    mycnt = set(pkgdata['content'])
    
    for x in mycnt:
	if x.startswith("/usr/share/icons") and x.endswith("index.theme"):
	    functions.add('iconscache')
	if x.startswith("/usr/share/mime"):
	    functions.add('mimeupdate')
	if x.startswith("/usr/share/applications"):
	    functions.add('mimedesktopupdate')
	if x.startswith("/usr/share/omf"):
	    functions.add('scrollkeeper')
	if x.startswith("/etc/gconf/schemas"):
	    functions.add('gconfreload')
	if x.startswith('/lib/modules/') and x.endswith('.ko'):
	    functions.add('kernelmod')

    return list(functions) # need a list??


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
	setup_font_dir(fontdir)
	setup_font_cache(fontdir)

def gccswitch(pkgdata):
    print_info(" "+brown("[POST] Configuring GCC Profile..."))
    # get gcc profile
    pkgsplit = entropyTools.catpkgsplit(pkgdata['category']+"/"+pkgdata['name']+"-"+pkgdata['version'])
    profile = pkgdata['chost']+"-"+pkgsplit[2]
    set_gcc_profile(profile)

def iconscache(pkgdata):
    print_info(" "+brown("[POST] Updating icons cache..."))
    mycnt = set(pkgdata['content'])
    for file in mycnt:
	if file.startswith("/usr/share/icons") and file.endswith("index.theme"):
	    cachedir = os.path.dirname(file)
	    generate_icons_cache(cachedir)

def mimeupdate(pkgdata):
    print_info(" "+brown("[POST] Updating shared mime info database..."))
    update_mime_db()

def mimedesktopupdate(pkgdata):
    print_info(" "+brown("[POST] Updating desktop mime database..."))
    update_mime_desktop_db()

def scrollkeeper(pkgdata):
    print_info(" "+brown("[POST] Updating scrollkeeper database..."))
    update_scrollkeeper_db()

def gconfreload(pkgdata):
    print_info(" "+brown("[POST] Reloading GConf2 database..."))
    reload_gconf_db()

def binutilsswitch(pkgdata):
    print_info(" "+brown("[POST] Configuring Binutils Profile..."))
    # get binutils profile
    pkgsplit = entropyTools.catpkgsplit(pkgdata['category']+"/"+pkgdata['name']+"-"+pkgdata['version'])
    profile = pkgdata['chost']+"-"+pkgsplit[2]
    set_binutils_profile(profile)

def kernelmod(pkgdata):
    print_info(" "+brown("[POST] Updating moduledb..."))
    item = 'a:1:'+pkgdata['category']+"/"+pkgdata['name']+"-"+pkgdata['version']
    update_moduledb(item)

########################################################
####
##   Internal functions
#

'''
   @description: creates Xfont files
   @output: returns int() as exit status
'''
def setup_font_dir(fontdir):
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
def setup_font_cache(fontdir):
    # fc-cache -f gooooo!
    if os.access('/usr/bin/fc-cache',os.X_OK):
	os.system('HOME="/root" /usr/bin/fc-cache -f '+unicode(fontdir))
    return 0

'''
   @description: set chosen gcc profile
   @output: returns int() as exit status
'''
def set_gcc_profile(profile):
    if os.access('/usr/bin/gcc-config',os.X_OK):
	os.system('/usr/bin/gcc-config '+profile)
    return 0

'''
   @description: set chosen binutils profile
   @output: returns int() as exit status
'''
def set_binutils_profile(profile):
    if os.access('/usr/bin/binutils-config',os.X_OK):
	os.system('/usr/bin/binutils-config '+profile)
    return 0

'''
   @description: creates/updates icons cache
   @output: returns int() as exit status
'''
def generate_icons_cache(cachedir):
    if os.access('/usr/bin/gtk-update-icon-cache',os.X_OK):
	os.system('/usr/bin/gtk-update-icon-cache -qf '+cachedir)
    return 0

'''
   @description: updates /usr/share/mime database
   @output: returns int() as exit status
'''
def update_mime_db():
    if os.access('/usr/bin/update-mime-database',os.X_OK):
	os.system('/usr/bin/update-mime-database /usr/share/mime')
    return 0

'''
   @description: updates /usr/share/applications database
   @output: returns int() as exit status
'''
def update_mime_desktop_db():
    if os.access('/usr/bin/update-desktop-database',os.X_OK):
	os.system('/usr/bin/update-desktop-database -q /usr/share/applications')
    return 0

'''
   @description: updates /var/lib/scrollkeeper database
   @output: returns int() as exit status
'''
def update_scrollkeeper_db():
    if os.access('/usr/bin/scrollkeeper-update',os.X_OK):
	if not os.path.isdir('/var/lib/scrollkeeper'):
	    os.makedirs('/var/lib/scrollkeeper')
	os.system('/usr/bin/scrollkeeper-update -q -p /var/lib/scrollkeeper')
    return 0

'''
   @description: respawn gconfd-2 if found
   @output: returns int() as exit status
'''
def reload_gconf_db():
    rc = os.system('pgrep -x gconfd-2')
    if (rc == 0):
	pids = commands.getoutput('pgrep -x gconfd-2').split("\n")
	pidsstr = ''
	for pid in pids:
	    if pid:
		pidsstr += pid+' '
	pidsstr = pidsstr.strip()
	if pidsstr:
	    os.system('kill -HUP '+pidsstr)
    return 0

'''
   @description: updates moduledb
   @output: returns int() as exit status
'''
def update_moduledb(item):
    if os.access('/usr/sbin/module-rebuild',os.X_OK):
	if os.path.isfile(MODULEDB_DIR+'moduledb'):
	    f = open(MODULEDB_DIR+'moduledb',"r")
	    moduledb = f.readlines()
	    f.close()
	    avail = [x for x in moduledb if x.strip() == item]
	    if (not avail):
		f = open(MODULEDB_DIR+'moduledb',"aw")
		f.write(item+"\n")
		f.flush()
		f.close()
    return 0