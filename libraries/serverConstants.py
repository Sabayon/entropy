#!/usr/bin/python
'''
    # DESCRIPTION:
    # Variables container for server side applications

    Copyright (C) 2007-2008 Fabio Erculiani

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

from entropyConstants import *
etpSys['serverside'] = True

def initConfig_serverConstants():

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
            elif line.startswith("mirror-download|") and (len(line.split("mirror-download|")) == 2):
                uri = line.split("mirror-download|")[1]
                if uri.endswith("/"):
                    uri = uri[:len(uri)-1]
                etpConst['activatordownloaduris'].append(uri)
            elif line.startswith("database-format|") and (len(line.split("database-format|")) == 2):
                format = line.split("database-format|")[1]
                if format in etpConst['etpdatabasesupportedcformats']:
                    etpConst['etpdatabasefileformat'] = format
            elif line.startswith("loglevel|") and (len(line.split("loglevel|")) == 2):
                loglevel = line.split("loglevel|")[1]
                try:
                    loglevel = int(loglevel)
                except:
                    pass
                if (loglevel > -1) and (loglevel < 3):
                    etpConst['activatorloglevel'] = loglevel
                else:
                    pass

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
                    pass
                if (loglevel > -1) and (loglevel < 3):
                    etpConst['reagentloglevel'] = loglevel
                else:
                    pass
            elif line.startswith("rss-feed|") and (len(line.split("rss-feed|")) == 2):
                feed = line.split("rss-feed|")[1]
                if feed in ("enable","enabled","true","1"):
                    etpConst['rss-feed'] = True
                elif feed in ("disable","disabled","false","0"):
                    etpConst['rss-feed'] = False
            elif line.startswith("rss-name|") and (len(line.split("rss-name|")) == 2):
                feedname = line.split("rss-name|")[1].strip()
                etpConst['rss-name'] = feedname
            elif line.startswith("rss-base-url|") and (len(line.split("rss-base-url|")) == 2):
                etpConst['rss-base-url'] = line.split("rss-base-url|")[1].strip()
                if not etpConst['rss-base-url'][-1] == "/":
                    etpConst['rss-base-url'] += "/"
            elif line.startswith("rss-website-url|") and (len(line.split("rss-website-url|")) == 2):
                etpConst['rss-website-url'] = line.split("rss-website-url|")[1].strip()
            elif line.startswith("managing-editor|") and (len(line.split("managing-editor|")) == 2):
                etpConst['rss-managing-editor'] = line.split("managing-editor|")[1].strip()
            elif line.startswith("max-rss-entries|") and (len(line.split("max-rss-entries|")) == 2):
                try:
                    entries = int(line.split("max-rss-entries|")[1].strip())
                    etpConst['rss-max-entries'] = entries
                except:
                    pass

    # generic settings section
    if (os.path.isfile(etpConst['serverconf'])):
        f = open(etpConst['serverconf'],"r")
        serverconf = f.readlines()
        f.close()
        for line in serverconf:
            if line.startswith("branches|") and (len(line.split("branches|")) == 2):
                branches = line.split("branches|")[1]
                etpConst['branches'] = []
                for branch in branches.split():
                    etpConst['branches'].append(branch)
                if etpConst['branch'] not in etpConst['branches']:
                    etpConst['branches'].append(etpConst['branch'])

    if etpConst['uid'] != 0:
        import exceptionTools
        raise exceptionTools.PermissionDenied("PermissionDenied: Entropy server must be run as root")

initConfig_serverConstants()