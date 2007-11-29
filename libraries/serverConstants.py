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
from sys import exit
from entropyConstants import *

# activator section
if (os.path.isfile(etpConst['activatorconf'])):
    try:
	if (os.stat(etpConst['activatorconf'])[0] != 33152):
	    os.chmod(etpConst['activatorconf'],0600)
    except:
        pass
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
		exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['activatorloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['activatorconf']
		import time
		time.sleep(5)

# reagent section
if (os.path.isfile(etpConst['reagentconf'])):
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
		exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['reagentloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['reagentconf']
		import time
		time.sleep(5)

# mirrors section
if (os.path.isfile(etpConst['mirrorsconf'])):
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
		exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['mirrorsloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['mirrorsconf']
		import time
		time.sleep(5)


# spmbackend section
if (os.path.isfile(etpConst['spmbackendconf'])):
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
		exit(51)
	    if (loglevel > -1) and (loglevel < 3):
	        etpConst['spmbackendloglevel'] = loglevel
	    else:
		print "WARNING: invalid loglevel in: "+etpConst['spmbackendconf']
		import time
		time.sleep(5)


# generic settings section
if (os.path.isfile(etpConst['serverconf'])):
    f = open(etpConst['serverconf'],"r")
    spmconf = f.readlines()
    f.close()
    for line in spmconf:
	if line.startswith("branches|") and (len(line.split("branches|")) == 2):
	    branches = line.split("branches|")[1]
            etpConst['branches'] = []
            for branch in branches.split():
                etpConst['branches'].append(branch)
	    if etpConst['branch'] not in etpConst['branches']:
		etpConst['branches'].append(etpConst['branch'])
