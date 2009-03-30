# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

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
import shutil
import subprocess
from entropy.client.interfaces import Client
from entropy.exceptions import *
from entropy.const import etpConst, etpCache
from entropy.output import darkred, darkgreen, red, brown, blue
from entropy.tools import getstatusoutput
from entropy.i18n import _

class FileUpdates:

    def __init__(self, EquoInstance):
        if not isinstance(EquoInstance,Client):
            mytxt = _("A valid Client instance or subclass is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        self.Entropy = EquoInstance
        from entropy.cache import EntropyCacher
        self.Cacher = EntropyCacher()
        self.scandata = None

    def merge_file(self, key):
        self.scanfs(dcache = True)
        self.do_backup(key)
        if os.access(etpConst['systemroot'] + self.scandata[key]['source'], os.R_OK):
            shutil.move(
                etpConst['systemroot'] + self.scandata[key]['source'],
                etpConst['systemroot'] + self.scandata[key]['destination']
            )
        self.remove_from_cache(key)

    def remove_file(self, key):
        self.scanfs(dcache = True)
        try:
            os.remove(etpConst['systemroot'] + self.scandata[key]['source'])
        except OSError:
            pass
        self.remove_from_cache(key)

    def do_backup(self, key):
        self.scanfs(dcache = True)
        if etpConst['filesbackup'] and os.path.isfile(etpConst['systemroot']+self.scandata[key]['destination']):
            bcount = 0
            backupfile = etpConst['systemroot'] + \
                os.path.dirname(self.scandata[key]['destination']) + \
                "/._equo_backup." + unicode(bcount) + "_" + \
                os.path.basename(self.scandata[key]['destination'])
            while os.path.lexists(backupfile):
                bcount += 1
                backupfile = etpConst['systemroot'] + \
                os.path.dirname(self.scandata[key]['destination']) + \
                "/._equo_backup." + unicode(bcount) + "_" + \
                os.path.basename(self.scandata[key]['destination'])
            try:
                shutil.copy2(etpConst['systemroot'] + self.scandata[key]['destination'],backupfile)
            except IOError:
                pass

    '''
    @description: scan for files that need to be merged
    @output: dictionary using filename as key
    '''
    def scanfs(self, dcache = True, quiet = False):

        if dcache:

            if self.scandata != None:
                return self.scandata

            # can we load cache?
            try:
                z = self.load_cache()
                if z != None:
                    self.scandata = z
                    return self.scandata
            except:
                pass

        # open client database to fill etpConst['dbconfigprotect']
        scandata = {}
        counter = 0
        name_cache = set()
        for path in etpConst['dbconfigprotect']:
            # it's a file?
            scanfile = False
            if os.path.isfile(path):
                # find inside basename
                path = os.path.dirname(path)
                scanfile = True

            for currentdir,subdirs,files in os.walk(path):
                for item in files:

                    if scanfile:
                        if path != item:
                            continue

                    filepath = os.path.join(currentdir,item)
                    if item.startswith("._cfg"):

                        # further check then
                        number = item[5:9]
                        try:
                            int(number)
                        except ValueError:
                            continue # not a valid etc-update file
                        if item[9] != "_": # no valid format provided
                            continue

                        if filepath in name_cache:
                            continue # skip, already done
                        name_cache.add(filepath)

                        mydict = self.generate_dict(filepath)
                        if mydict['automerge']:
                            if not quiet:
                                mytxt = _("Automerging file")
                                self.Entropy.updateProgress(
                                    darkred("%s: %s") % (
                                        mytxt,
                                        darkgreen(etpConst['systemroot'] + mydict['source']),
                                    ),
                                    importance = 0,
                                    type = "info"
                                )
                            if os.path.isfile(etpConst['systemroot']+mydict['source']):
                                try:
                                    shutil.move(    etpConst['systemroot']+mydict['source'],
                                                    etpConst['systemroot']+mydict['destination']
                                    )
                                except IOError, e:
                                    if not quiet:
                                        mytxt = "%s :: %s: %s. %s: %s" % (
                                            red(_("I/O Error")),
                                            red(_("Cannot automerge file")),
                                            brown(etpConst['systemroot'] + mydict['source']),
                                            blue("Error"),
                                            e,
                                        )
                                        self.Entropy.updateProgress(
                                            mytxt,
                                            importance = 1,
                                            type = "warning"
                                        )
                            continue
                        else:
                            counter += 1
                            scandata[counter] = mydict.copy()

                        if not quiet:
                            try:
                                self.Entropy.updateProgress(
                                    "("+blue(str(counter))+") " + red(" file: ") + \
                                    os.path.dirname(filepath) + "/" + os.path.basename(filepath)[10:],
                                    importance = 1,
                                    type = "info"
                                )
                            except:
                                pass # possible encoding issues
        # store data
        self.Cacher.push(etpCache['configfiles'],scandata)
        self.scandata = scandata.copy()
        return scandata

    def load_cache(self):
        sd = self.Cacher.pop(etpCache['configfiles'])
        if not isinstance(sd,dict):
            raise CacheCorruptionError("CacheCorruptionError")
        # quick test if data is reliable
        try:
            name_cache = set()

            for x in sd:
                mysource = sd[x]['source']
                # filter dupies
                if mysource in name_cache:
                    sd.pop(x)
                    continue
                if not os.path.isfile(etpConst['systemroot']+mysource):
                    raise CacheCorruptionError("CacheCorruptionError")
                name_cache.add(mysource)

            return sd
        except (KeyError,EOFError,IOError,):
            raise CacheCorruptionError("CacheCorruptionError")

    '''
    @description: prints information about config files that should be updated
    @attention: please be sure that filepath is properly formatted before using this function
    '''
    def add_to_cache(self, filepath, quiet = False):
        self.scanfs(dcache = True, quiet = quiet)
        keys = self.scandata.keys()
        try:
            for key in keys:
                if self.scandata[key]['source'] == filepath[len(etpConst['systemroot']):]:
                    del self.scandata[key]
        except:
            pass
        # get next counter
        if keys:
            keys = sorted(keys)
            index = keys[-1]
        else:
            index = 0
        index += 1
        mydata = self.generate_dict(filepath)
        self.scandata[index] = mydata.copy()
        self.Cacher.push(etpCache['configfiles'],self.scandata)

    def remove_from_cache(self, key):
        self.scanfs(dcache = True)
        try:
            del self.scandata[key]
        except:
            pass
        self.Cacher.push(etpCache['configfiles'],self.scandata)
        return self.scandata

    def generate_dict(self, filepath):

        item = os.path.basename(filepath)
        currentdir = os.path.dirname(filepath)
        tofile = item[10:]
        number = item[5:9]
        try:
            int(number)
        except:
            mytxt = _("Invalid config file number")
            raise InvalidDataType("InvalidDataType: %s '0000->9999'." % (mytxt,))
        tofilepath = currentdir+"/"+tofile
        mydict = {}
        mydict['revision'] = number
        mydict['destination'] = tofilepath[len(etpConst['systemroot']):]
        mydict['source'] = filepath[len(etpConst['systemroot']):]
        mydict['automerge'] = False
        if not os.path.isfile(tofilepath):
            mydict['automerge'] = True
        if (not mydict['automerge']):
            # is it trivial?
            try:
                if not os.path.lexists(filepath): # if file does not even exist
                    return mydict
                if os.path.islink(filepath):
                    # if it's broken, skip diff and automerge
                    if not os.path.exists(filepath):
                        return mydict
                result = getstatusoutput('diff -Nua "%s" "%s" | grep "^[+-][^+-]" | grep -v \'# .Header:.*\'' % (filepath,tofilepath,))[1]
                if not result:
                    mydict['automerge'] = True
            except:
                pass
            # another test
            if (not mydict['automerge']):
                try:
                    if not os.path.lexists(filepath): # if file does not even exist
                        return mydict
                    if os.path.islink(filepath):
                        # if it's broken, skip diff and automerge
                        if not os.path.exists(filepath):
                            return mydict
                    result = subprocess.call('diff -Bbua "%s" "%s" | egrep \'^[+-]\' | egrep -v \'^[+-][\t ]*#|^--- |^\+\+\+ \' | egrep -qv \'^[-+][\t ]*$\'' % (filepath,tofilepath,), shell = True)
                    if result == 1:
                        mydict['automerge'] = True
                except:
                    pass
        return mydict