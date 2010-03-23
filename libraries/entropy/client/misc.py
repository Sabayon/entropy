# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Miscellaneous Interface}.

"""

import os
import sys
import shutil
import subprocess
from entropy.cache import EntropyCacher
from entropy.core.settings.base import SystemSettings
from entropy.client.interfaces import Client
from entropy.exceptions import CacheCorruptionError
from entropy.const import etpConst, const_convert_to_rawstring
from entropy.output import darkred, darkgreen, red, brown, blue
from entropy.tools import getstatusoutput
from entropy.i18n import _

class FileUpdates:

    CACHE_ID = "conf/scanfs"

    def __init__(self, entropy_client):
        if not isinstance(entropy_client, Client):
            mytxt = "A valid Client instance or subclass is needed"
            raise AttributeError(mytxt)
        self._entropy = entropy_client
        self._settings = SystemSettings()
        self._cacher = EntropyCacher()
        self._scandata = None

    def merge(self, key):
        self.scan(dcache = True)
        self._backup(key)
        source_file = etpConst['systemroot'] + self._scandata[key]['source']
        dest_file = etpConst['systemroot'] + self._scandata[key]['destination']
        if os.access(source_file, os.R_OK):
            shutil.move(source_file, dest_file)
        self.ignore(key)

    def remove(self, key):
        self.scan(dcache = True)
        source_file = etpConst['systemroot'] + self._scandata[key]['source']
        if os.path.isfile(source_file) and os.access(source_file, os.W_OK):
            os.remove(source_file)
        self.ignore(key)

    def _backup(self, key):
        self.scan(dcache = True)
        sys_set_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        files_backup = self._settings[sys_set_plg_id]['misc']['filesbackup']
        dest_file = etpConst['systemroot'] + self._scandata[key]['destination']
        if files_backup and os.path.isfile(dest_file):
            bcount = 0
            backupfile = etpConst['systemroot'] + \
                os.path.dirname(self._scandata[key]['destination']) + \
                "/._entropy_backup." + str(bcount) + "_" + \
                os.path.basename(self._scandata[key]['destination'])
            while os.path.lexists(backupfile):
                bcount += 1
                backupfile = etpConst['systemroot'] + \
                os.path.dirname(self._scandata[key]['destination']) + \
                "/._entropy_backup." + str(bcount) + "_" + \
                os.path.basename(self._scandata[key]['destination'])
            try:
                shutil.copy2(dest_file, backupfile)
            except IOError:
                pass

    def _get_system_config_protect(self, mask = False):

        inst_repo = self._entropy.installed_repository()
        if inst_repo is None:
            return []

        cl_id = etpConst['system_settings_plugins_ids']['client_plugin']
        misc_data = self._settings[cl_id]['misc']
        if mask:
            _pmask = inst_repo.listConfigProtectEntries(mask = True)
            config_protect = set(_pmask)
            config_protect |= set(misc_data['configprotectmask'])
        else:
            _protect = inst_repo.listConfigProtectEntries()
            config_protect = set(_protect)
            config_protect |= set(misc_data['configprotect'])
        config_protect = [etpConst['systemroot']+x for x in config_protect]

        return sorted(config_protect)

    def scan(self, dcache = True, quiet = False):

        if dcache:

            if self._scandata != None:
                return self._scandata

            # can we load cache?
            try:
                z = self._load_cache()
                if z != None:
                    self._scandata = z
                    return self._scandata
            except (CacheCorruptionError, KeyError, IOError, OSError,):
                pass

        scandata = {}
        counter = 0
        name_cache = set()
        client_conf_protect = self._get_system_config_protect()

        for path in client_conf_protect:

            # this avoids encoding issues hands down
            try:
                path = path.encode('utf-8')
            except (UnicodeEncodeError,):
                path = path.encode(sys.getfilesystemencoding())
            # it's a file?
            scanfile = False
            if os.path.isfile(path):
                # find inside basename
                path = os.path.dirname(path)
                scanfile = True

            for currentdir, subdirs, files in os.walk(path):
                for item in files:

                    if scanfile:
                        if path != item:
                            continue

                    filepath = os.path.join(currentdir, item)
                    # FIXME: with Python 3.x we can remove const_convert...
                    # and not use path.encode('utf-8')
                    if item.startswith(const_convert_to_rawstring("._cfg")): 

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

                        mydict = self._generate_dict(filepath)
                        if mydict['automerge']:
                            if not quiet:
                                mytxt = _("Automerging file")
                                self._entropy.output(
                                    darkred("%s: %s") % (
                                        mytxt,
                                        darkgreen(etpConst['systemroot'] + mydict['source']),
                                    ),
                                    importance = 0,
                                    type = "info"
                                )
                            if os.path.isfile(etpConst['systemroot']+mydict['source']):
                                try:
                                    os.rename(etpConst['systemroot']+mydict['source'],
                                        etpConst['systemroot']+mydict['destination'])
                                except (OSError, IOError,) as e:
                                    if not quiet:
                                        mytxt = "%s :: %s: %s. %s: %s" % (
                                            red(_("System Error")),
                                            red(_("Cannot automerge file")),
                                            brown(etpConst['systemroot'] + mydict['source']),
                                            blue("error"),
                                            e,
                                        )
                                        self._entropy.output(
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
                                self._entropy.output(
                                    "("+blue(str(counter))+") " + \
                                    red(" file: ") + \
                                    os.path.dirname(filepath) + "/" + \
                                    os.path.basename(filepath)[10:],
                                    importance = 1,
                                    type = "info"
                                )
                            except (UnicodeEncodeError, UnicodeDecodeError):
                                pass # possible encoding issues
        # store data
        self._cacher.push(FileUpdates.CACHE_ID, scandata)
        self._scandata = scandata.copy()
        return scandata

    def _load_cache(self):
        sd = self._cacher.pop(FileUpdates.CACHE_ID)
        if not isinstance(sd, dict):
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
        except (KeyError, EOFError, IOError,):
            raise CacheCorruptionError("CacheCorruptionError")

    def add(self, filepath, quiet = False):
        self.scan(dcache = True, quiet = quiet)
        keys = list(self._scandata.keys())
        root_len = len(etpConst['systemroot'])
        for key in keys:
            if key not in self._scandata:
                continue
            if self._scandata[key]['source'] == filepath[root_len:]:
                del self._scandata[key]
        # get next counter
        if keys:
            keys = sorted(keys)
            index = keys[-1]
        else:
            index = 0
        index += 1
        mydata = self._generate_dict(filepath)
        self._scandata[index] = mydata.copy()
        self._cacher.push(FileUpdates.CACHE_ID, self._scandata)

    def ignore(self, key):
        self.scan(dcache = True)
        if key in self._scandata:
            del self._scandata[key]
        self._cacher.push(FileUpdates.CACHE_ID, self._scandata)
        return self._scandata

    def _generate_dict(self, filepath):

        item = os.path.basename(filepath)
        currentdir = os.path.dirname(filepath)
        tofile = item[10:]
        number = item[5:9]
        try:
            int(number)
        except ValueError:
            raise ValueError("invalid config file number '0000->9999'.")
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
                result = getstatusoutput('diff -Nua "%s" "%s" | grep "^[+-][^+-]" | grep -v \'# .Header:.*\'' % (filepath, tofilepath,))[1]
                if not result:
                    mydict['automerge'] = True
            except:
                pass
            # another test
            if not mydict['automerge']:
                try:
                    # if file does not even exist
                    if not os.path.lexists(filepath):
                        return mydict
                    if os.path.islink(filepath):
                        # if it's broken, skip diff and automerge
                        if not os.path.exists(filepath):
                            return mydict
                    result = subprocess.call('diff -Bbua "%s" "%s" | egrep \'^[+-]\' | egrep -v \'^[+-][\t ]*#|^--- |^\+\+\+ \' | egrep -qv \'^[-+][\t ]*$\'' % (filepath, tofilepath,), shell = True)
                    if result == 1:
                        mydict['automerge'] = True
                except:
                    pass
        return mydict
