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
	if line.startswith("database-format|") and (len(line.split("database-format|")) == 2):
	    format = line.split("database-format|")[1]
	    if format in etpConst['etpdatabasesupportedcformats']:
		etpConst['etpdatabasefileformat'] = format
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
