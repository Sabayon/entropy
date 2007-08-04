#!/usr/bin/python
'''
    # DESCRIPTION:
    # Variables container for server side applications

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

import os
import commands
import string
import random
import sys
from entropyConstants import *


# configure layman.cfg properly
if (not os.path.isfile(etpConst['overlaysconffile'])):
    laymanConf = """
[MAIN]

#-----------------------------------------------------------
# Path to the config directory

config_dir: /etc/layman

#-----------------------------------------------------------
# Defines the directory where overlays should be installed

storage   : """+etpConst['overlaysdir']+"""

#-----------------------------------------------------------
# Remote overlay lists will be stored here
# layman will append _md5(url).xml to each filename

cache     : %(storage)s/cache

#-----------------------------------------------------------
# The list of locally installed overlays

local_list: %(storage)s/overlays.xml

#-----------------------------------------------------------
# Path to the make.conf file that should be modified by
# layman

make_conf : %(storage)s/make.conf

#-----------------------------------------------------------
# URLs of the remote lists of overlays (one per line) or
# local overlay definitions
#
#overlays  : http://www.gentoo.org/proj/en/overlays/layman-global.txt
#            http://dev.gentoo.org/~wrobel/layman/global-overlays.xml
#            http://mydomain.org/my-layman-list.xml
#            file:///usr/portage/local/layman/my-list.xml

overlays  : http://www.gentoo.org/proj/en/overlays/layman-global.txt

#-----------------------------------------------------------
# Proxy support
#
#proxy  : http://www.my-proxy.org:3128

#-----------------------------------------------------------
# Strict checking of overlay definitions
#
# Set either to "yes" or "no". If "no" layman will issue
# warnings if an overlay definition is missing either
# description or contact information.
#
nocheck  : yes
"""
    f = open(etpConst['overlaysconffile'],"w")
    f.writelines(laymanConf)
    f.flush()
    f.close()

# fill etpConst['overlays']
if os.path.isdir(etpConst['overlaysdir']):
    ovlst = os.listdir(etpConst['overlaysdir'])
    _ovlst = []
    for i in ovlst:
        if os.path.isdir(etpConst['overlaysdir']+"/"+i):
	    _ovlst.append(etpConst['overlaysdir']+"/"+i)
    etpConst['overlays'] = string.join(_ovlst," ")

# activator section
if (not os.path.isfile(etpConst['activatorconf'])):
    print "CRITICAL WARNING!!! "+etpConst['activatorconf']+" does not exist"
else:
    try:
	if (os.stat(etpConst['activatorconf'])[0] != 33152):
	    os.chmod(etpConst['activatorconf'],0600)
    except:
	print "ERROR: cannot chmod 0600 file: "+etpConst['activatorconf']
	sys.exit(50)
    # fill etpConst['activatoruploaduris'] and etpConst['activatordownloaduris']
    f = open(etpConst['activatorconf'],"r")
    actconffile = f.readlines()
    f.close()
    for line in actconffile:
	line = line.strip()
	if line.startswith("mirror-upload|") and (len(line.split("mirror-upload|")) == 2):
	    uri = line.split("mirror-upload|")[1]
	    if uri.endswith("/"):
		uri = uri[:len(uri)-1]
	    etpConst['activatoruploaduris'].append(uri)
	if line.startswith("mirror-download|") and (len(line.split("mirror-download|")) == 2):
	    uri = line.split("mirror-download|")[1]
	    if uri.endswith("/"):
		uri = uri[:len(uri)-1]
	    etpConst['activatordownloaduris'].append(uri)
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['activatorconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['activatorloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['activatorconf']
		import time
		time.sleep(5)

# enzyme section
if (not os.path.isfile(etpConst['enzymeconf'])):
    print "CRITICAL WARNING!!! "+etpConst['enzymeconf']+" does not exist"
else:
    f = open(etpConst['enzymeconf'],"r")
    enzymeconf = f.readlines()
    f.close()
    for line in enzymeconf:
	if line.startswith("distcc-status|") and (len(line.split("|")) == 2) and (line.strip().split("|")[1] == "enabled"):
	    etpConst['distcc-status'] = True
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['enzymeconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['enzymeloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['enzymeconf']
		import time
		time.sleep(5)
		

# reagent section
if (not os.path.isfile(etpConst['reagentconf'])):
    print "CRITICAL WARNING!!! "+etpConst['reagentconf']+" does not exist"
else:
    f = open(etpConst['reagentconf'],"r")
    reagentconf = f.readlines()
    f.close()
    for line in reagentconf:
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['reagentconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['reagentloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['reagentconf']
		import time
		time.sleep(5)

# mirrors section
if (not os.path.isfile(etpConst['mirrorsconf'])):
    print "CRITICAL WARNING!!! "+etpConst['mirrorsconf']+" does not exist"
else:
    f = open(etpConst['mirrorsconf'],"r")
    databaseconf = f.readlines()
    f.close()
    for line in databaseconf:
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['mirrorsconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['mirrorsloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['mirrorsconf']
		import time
		time.sleep(5)

# spmbackend section
if (not os.path.isfile(etpConst['spmbackendconf'])):
    print "CRITICAL WARNING!!! "+etpConst['spmbackendconf']+" does not exist"
else:
    f = open(etpConst['spmbackendconf'],"r")
    spmconf = f.readlines()
    f.close()
    for line in spmconf:
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['spmbackendconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['spmbackendloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['spmbackendconf']
		import time
		time.sleep(5)

# remote section
etpRemoteSupport = {}
if (not os.path.isfile(etpConst['remoteconf'])):
    print "ERROR: "+etpConst['remoteconf']+" does not exist"
    sys.exit(50)
else:
    f = open(etpConst['remoteconf'],"r")
    databaseconf = f.readlines()
    f.close()
    for line in databaseconf:
	if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
	    loglevel = line.split("loglevel|")[1]
	    try:
		loglevel = int(loglevel)
	    except:
		print "ERROR: invalid loglevel in: "+etpConst['remoteconf']
		sys.exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['remoteloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['remoteconf']
		import time
		time.sleep(5)

	if line.startswith("httphandler|") and (len(line.split("|")) > 2):
	    servername = line.split("|")[1].strip()
	    url = line.split("|")[2].strip()
	    if not url.endswith("/"):
		url = url+"/"
	    etpRemoteSupport[servername] = url