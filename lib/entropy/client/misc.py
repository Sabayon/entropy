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
from entropy.const import etpConst, const_convert_to_rawstring, \
    const_convert_to_unicode, const_debug_write, const_file_readable
from entropy.output import darkred, darkgreen, red, brown, blue
from entropy.tools import getstatusoutput, rename_keep_permissions
from entropy.i18n import _

class ConfigurationFiles(dict):

    """
    Configuration Files Updates descriptor.
    Each configuration file update action is described
    as a mapping between the source file and its destination
    target.
    Each key (a string representing a source file) points to
    a dictionary, containing the following items:
        "destination": path to destination file (string)
        "automerge": if source can be automerged to destination (bool)
    """

    def __init__(self, entropy_client, quiet=False):
        self._quiet = quiet
        self._entropy = entropy_client
        self._settings = SystemSettings()
        dict.__init__(self)
        self._load()

    @property
    def _repository_ids(self):
        """
        Return a the list of repository identifiers the object
        is using.
        """
        inst_repo = self._entropy.installed_repository()
        return [inst_repo.repository_id()]

    @staticmethod
    def root():
        """
        Return the current ROOT ("/") prefix
        """
        return etpConst['systemroot']

    def _get_config_protect(self, mask=False):
        """
        Get CONFIG_PROTECT or CONFIG_PROTECT_MASK values from
        _repository_ids.
        """
        cl_id = etpConst['system_settings_plugins_ids']['client_plugin']
        misc_data = self._settings[cl_id]['misc']
        config_protect = set()
        # also ask to Source Package Manager
        spm = self._entropy.Spm()

        if mask:
            config_protect |= set(misc_data['configprotectmask'])
            # also read info from environment and merge here
            config_protect |= set(spm.get_merge_protected_paths_mask())
        else:
            config_protect |= set(misc_data['configprotect'])
            # also read info from environment and merge here
            config_protect |= set(spm.get_merge_protected_paths())

        # get from our repositories
        for repository_id in self._repository_ids:
            repo = self._entropy.open_repository(repository_id)
            if mask:
                _mask = repo.listConfigProtectEntries(mask = True)
            else:
                _mask = repo.listConfigProtectEntries()
            config_protect |= set(_mask)

        root = ConfigurationFiles.root()
        config_protect = [root + x for x in config_protect]
        config_protect.sort()
        return config_protect

    def _encode_path(self, path):
        """
        Encode path using proper encoding for use with os functions.
        """
        try:
            path = const_convert_to_rawstring(
                path, from_enctype=etpConst['conf_encoding'])
        except (UnicodeEncodeError,):
            path = const_convert_to_rawstring(
                path, from_enctype=sys.getfilesystemencoding())
        return path

    def _unicode_path(self, path):
        """
        Convert a potentially raw string into a well formed unicode
        one. Usually, this method is called on string that went through
        _encode_path()
        """
        try:
            path = const_convert_to_unicode(
                path, enctype=etpConst['conf_encoding'])
        except (UnicodeDecodeError,):
            path = const_convert_to_unicode(
                path, enctype=sys.getfilesystemencoding())
        return path

    def _strip_root(self, path):
        """
        Strip root prefix from path
        """
        root = ConfigurationFiles.root()
        new_path = path[len(root):]
        return os.path.normpath(new_path)

    def _load_can_automerge(self, source, destination):
        """
        Determine if source file path equals destination file path,
        thus it can be automerged.
        """
        def _vanished():
            # file went away? not really needed, but...
            if not os.path.lexists(source):
                return True
            # broken symlink
            if os.path.islink(source) and not os.path.exists(source):
                return True
            return False

        if _vanished():
            return True

        # first diff test
        try:
            exit_st = getstatusoutput(
                'diff -Nua "%s" "%s" | grep '
                '"^[+-][^+-]" | grep -v \'# .Header:.*\'' % (
                    source, destination,))[1]
        except (OSError, IOError):
            exit_st = 1
        if exit_st == os.EX_OK:
            return True
        elif _vanished():
            return True

        # second diff test
        try:
            exit_st = subprocess.call(
                'diff -Bbua "%s" "%s" | '
                'egrep \'^[+-]\' | '
                'egrep -v \'^[+-][\t ]*#|^--- |^\+\+\+ \' | '
                'egrep -qv \'^[-+][\t ]*$\'' % (
                    source, destination,), shell = True)
        except (IOError, OSError,):
            exit_st = 0
        if exit_st == 1:
            return True

        if _vanished():
            return True
        # requires manual merge
        return False

    def _load_maybe_add(self, currentdir, item, filepath,
                        scanfile, number):
        """
        Scan given path and store config file update information
        if needed.
        """
        try:
            tofile = item[10:]
            number = item[5:9]
        except IndexError as err:
            const_debug_write(
                __name__, "load_maybe_add, IndexError: "
                "%s, locals: %s" % (
                    repr(err), locals()))
            return

        try:
            int(number)
        except ValueError as err:
            # not a number
            const_debug_write(
                __name__, "load_maybe_add, ValueError: "
                "%s, locals: %s" % (
                    repr(err), locals()))
            return

        tofilepath = os.path.join(currentdir, tofile)
        # tofile is the target filename now
        # before adding, determine if we should automerge it
        if self._load_can_automerge(filepath, tofilepath):
            if not self._quiet:
                self._entropy.output(
                    darkred("%s: %s") % (
                        _("Automerging file"),
                        darkgreen(filepath),
                        ),
                    importance = 0,
                    level = "info"
                )
            try:
                rename_keep_permissions(
                    filepath, tofilepath)
            except OSError as err:
                const_debug_write(
                    __name__, "load_maybe_add, OSError: "
                    "%s, locals: %s" % (
                        repr(err), locals()))
            except IOError as err:
                const_debug_write(
                    __name__, "load_maybe_add, IOError: "
                    "%s, locals: %s" % (
                        repr(err), locals()))
            return

        # store
        save_filepath = self._strip_root(
            self._unicode_path(filepath))
        obj = {
            'destination': self._strip_root(
                self._unicode_path(tofilepath)),
            'automerge': False, # redundant but backward compat
        }
        self[save_filepath] = obj

        if not self._quiet:
            self._entropy.output(
                "%s: %s" % (
                    brown(_("Found update")),
                    self._unicode_path(
                        darkgreen(filepath)),),
                importance = 0,
                level = "info"
            )

    def _load(self):
        """
        Load configuration file updates reading from disk.
        """
        name_cache = set()
        client_conf_protect = self._get_config_protect()
        # NOTE: with Python 3.x we can remove const_convert...
        # and avoid using _encode_path.
        cfg_pfx = const_convert_to_rawstring("._cfg")

        for path in client_conf_protect:
            path = self._encode_path(path)

            # is it a file?
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

                    if not item.startswith(cfg_pfx):
                        continue

                    # further check then
                    number = item[5:9]
                    try:
                        int(number)
                    except ValueError:
                        continue # not a valid etc-update file
                    if item[9] != "_": # no valid format provided
                        continue

                    filepath = os.path.join(currentdir, item)
                    if filepath in name_cache:
                        continue # skip, already done
                    name_cache.add(filepath)

                    self._load_maybe_add(
                        currentdir, item, filepath, scanfile, number)

    def _backup(self, dest_path):
        """
        Execute a backup of the given path if User enabled
        the feature through Entropy Client configuration.
        """
        client_settings = self._entropy.ClientSettings()
        files_backup = client_settings['misc']['filesbackup']
        if not files_backup:
            return

        dest_path = self._encode_path(dest_path)
        if not os.path.isfile(dest_path):
            return

        backup_pfx = self._encode_path("._entropy_backup.")
        sep = self._encode_path("_")
        dirname, basename = os.path.split(dest_path)
        bcount = 0

        bcount_str = self._encode_path("%d" % (bcount,))
        backup_path = os.path.join(
            dirname, backup_pfx + bcount_str + sep + basename)
        while os.path.lexists(backup_path):
            bcount += 1
            bcount_str = self._encode_path("%d" % (bcount,))
            backup_path = os.path.join(
                dirname, backup_pfx + bcount_str + sep + basename)

        # I don't know if copy2 likes bytes()
        # time will tell!
        try:
            shutil.copy2(dest_path, backup_path)
        except OSError as err:
            const_debug_write(
                __name__, "_backup, OSError: "
                "%s, locals: %s" % (
                    repr(err), locals()))
        except IOError as err:
            const_debug_write(
                __name__, "_backup, IOError: "
                "%s, locals: %s" % (
                    repr(err), locals()))

    def remove(self, source):
        """
        Remove proposed source configuration file.
        "source" must be a key of this dictionary, if
        not, True is returned. If file pointed at source
        doesn't exist or removal fails, False is returned.
        """
        obj = self.pop(source, None)
        if obj is None:
            return True

        root = ConfigurationFiles.root()
        source_file = root + source
        source_file = self._encode_path(source_file)
        try:
            os.remove(source_file)
        except OSError as err:
            const_debug_write(
                __name__, "remove, OSError: "
                "%s, locals: %s" % (
                    repr(err), locals()))
            return False
        return True

    def merge(self, source):
        """
        Merge proposed source configuration file.
        "source" must be a key of this dictionary, if
        not, True is returned. If file pointed at source
        doesn't exist or merge fails, False is returned.
        """
        obj = self.pop(source, None)
        if obj is None:
            return True

        root = ConfigurationFiles.root()
        source_file = root + source
        dest_file = root + obj['destination']
        self._backup(dest_file)
        source_file = self._encode_path(source_file)
        dest_file = self._encode_path(dest_file)
        try:
            rename_keep_permissions(
                source_file, dest_file)
        except OSError as err:
            const_debug_write(
                __name__, "merge, OSError: "
                "%s, locals: %s" % (
                    repr(err), locals()))
            return False
        return True

    def exists(self, path):
        """
        Return True if path exists.
        This methods automatically appends the ROOT
        prefix and handles unicode correctly
        """
        root = ConfigurationFiles.root()
        source_file = root + path
        source_file = self._encode_path(source_file)
        return os.path.lexists(source_file)


class ConfigurationUpdates:

    """
    Entropy Configuration File Updates management class.
    """

    def __init__(self, entropy_client, _config_class=None):
        if _config_class is None:
            self._config_class = ConfigurationFiles
        else:
            self._config_class = _config_class
        self._entropy = entropy_client
        self._settings = self._entropy.Settings()

    def get(self, quiet=False):
        """
        Return a new ConfigurationFiles object.
        """
        return self._config_class(self._entropy)


class FileUpdates:

    CACHE_ID = "conf/scanfs"
    """
    @deprecated do not use this class
    @todo: remove after 2012-12-31
    """

    def __init__(self, entropy_client, repository_ids = None):
        self._entropy = entropy_client
        if repository_ids is None:
            repository_ids = []
            inst_repo = self._entropy.installed_repository()
            if inst_repo is not None:
                repository_ids.append(inst_repo.repository_id())
        self._repository_ids = repository_ids
        self._settings = SystemSettings()
        self._cacher = EntropyCacher()
        self._scandata = None

    def merge(self, key):
        self.scan(dcache = True)
        self._backup(key)
        source_file = etpConst['systemroot'] + self._scandata[key]['source']
        dest_file = etpConst['systemroot'] + self._scandata[key]['destination']
        if const_file_readable(source_file):
            shutil.move(source_file, dest_file)
        self.ignore(key)

    def remove(self, key):
        self.scan(dcache = True)
        source_file = etpConst['systemroot'] + self._scandata[key]['source']
        try:
            os.remove(source_file)
        except OSError:
            pass
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

        cl_id = etpConst['system_settings_plugins_ids']['client_plugin']
        misc_data = self._settings[cl_id]['misc']
        config_protect = set()
        # also ask to Source Package Manager
        spm = self._entropy.Spm()

        if mask:
            config_protect |= set(misc_data['configprotectmask'])
            # also read info from environment and merge here
            config_protect |= set(spm.get_merge_protected_paths_mask())
        else:
            config_protect |= set(misc_data['configprotect'])
            # also read info from environment and merge here
            config_protect |= set(spm.get_merge_protected_paths())

        # get from our repositories
        for repository_id in self._repository_ids:
            repo = self._entropy.open_repository(repository_id)
            if mask:
                _mask = repo.listConfigProtectEntries(mask = True)
            else:
                _mask = repo.listConfigProtectEntries()
            config_protect |= set(_mask)

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
                    # NOTE: with Python 3.x we can remove const_convert...
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
                                    level = "info"
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
                                            level = "warning"
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
                                    level = "info"
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
            if not os.path.lexists(filepath): # if file does not even exist
                return mydict
            if os.path.islink(filepath):
                # if it's broken, skip diff and automerge
                if not os.path.exists(filepath):
                    return mydict
            result = 1
            try:
                result = getstatusoutput('diff -Nua "%s" "%s" | grep "^[+-][^+-]" | grep -v \'# .Header:.*\'' % (filepath, tofilepath,))[1]
            except (OSError, IOError):
                pass
            if not result:
                mydict['automerge'] = True
            # another test
            if not mydict['automerge']:
                # if file does not even exist
                if not os.path.lexists(filepath):
                    return mydict
                if os.path.islink(filepath):
                    # if it's broken, skip diff and automerge
                    if not os.path.exists(filepath):
                        return mydict
                result = 0
                try:
                    result = subprocess.call('diff -Bbua "%s" "%s" | egrep \'^[+-]\' | egrep -v \'^[+-][\t ]*#|^--- |^\+\+\+ \' | egrep -qv \'^[-+][\t ]*$\'' % (filepath, tofilepath,),
                        shell = True)
                except (IOError, OSError,):
                    pass
                if result == 1:
                    mydict['automerge'] = True
        return mydict
