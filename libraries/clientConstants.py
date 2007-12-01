#!/usr/bin/python
'''
    # DESCRIPTION:
    # Variables container for client side applications

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
import sys
from entropyConstants import *

### Equo triggering functions for pre/post-install scripts
### index: package atom, content: name of the function to call
etpInstallTriggers = {}

### Equo triggering functions for pre/post-remove scripts
### structure same as above
etpRemovalTriggers = {}

def initConfig_clientConstants():
    # equo section
    if (os.path.isfile(etpConst['equoconf'])):
        f = open(etpConst['equoconf'],"r")
        equoconf = f.readlines()
        f.close()
        for line in equoconf:
            if line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
                loglevel = line.split("loglevel|")[1]
                try:
                    loglevel = int(loglevel)
                except:
                    print "ERROR: invalid loglevel in: "+etpConst['equoconf']
                    sys.exit(51)
                if (loglevel > -1) and (loglevel < 3):
                    etpConst['equologlevel'] = loglevel
                else:
                    print "WARNING: invalid loglevel in: "+etpConst['equoconf']
                    import time
                    time.sleep(5)
    
            if line.startswith("gentoo-compat|") and (len(line.split("|")) == 2):
                compatopt = line.split("|")[1].strip()
                if compatopt == "disable":
                    etpConst['gentoo-compat'] = False
                else:
                    etpConst['gentoo-compat'] = True
    
            if line.startswith("collisionprotect|") and (len(line.split("|")) == 2):
                collopt = line.split("|")[1].strip()
                if collopt == "0" or collopt == "1" or collopt == "2":
                    etpConst['collisionprotect'] = int(collopt)
                else:
                    print "WARNING: invalid collisionprotect in: "+etpConst['equoconf']
    
            if line.startswith("configprotect|") and (len(line.split("|")) == 2):
                configprotect = line.split("|")[1].strip()
                for x in configprotect.split():
                    etpConst['configprotect'].append(x)
    
            if line.startswith("configprotectmask|") and (len(line.split("|")) == 2):
                configprotect = line.split("|")[1].strip()
                for x in configprotect.split():
                    etpConst['configprotectmask'].append(x)
    
            if line.startswith("configprotectskip|") and (len(line.split("|")) == 2):
                configprotect = line.split("|")[1].strip()
                for x in configprotect.split():
                    etpConst['configprotectskip'].append(x)

initConfig_clientConstants()