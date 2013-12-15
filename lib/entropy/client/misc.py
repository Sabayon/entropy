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

from entropy.core.settings.base import SystemSettings
from entropy.const import etpConst, const_convert_to_rawstring, \
    const_convert_to_unicode, const_debug_write
from entropy.output import darkred, darkgreen, brown
from entropy.tools import getstatusoutput, rename_keep_permissions
from entropy.i18n import _


def sharedinstlock(method):
    """
    Decorator that acquires the Installed Packages Repository lock in
    shared mode and calls the wrapped function with an extra argument
    (the Installed Packages Repository object instance).

    This decorator expects that "self" has an installed_repository() method
    that returns the Installed Packages Repository instance.
    """
    def wrapped(self, *args, **kwargs):
        inst_repo = self.installed_repository()
        with inst_repo.shared():
            return method(self, *args, **kwargs)

    return wrapped


def exclusiveinstlock(method):
    """
    Decorator that acquires the Installed Packages Repository lock in
    exclusive mode and calls the wrapped function with an extra
    argument (the Installed Packages Repository object instance).

    This decorator expects that "self" has an installed_repository() method
    that returns the Installed Packages Repository instance.
    """
    def wrapped(self, *args, **kwargs):
        inst_repo = self.installed_repository()
        with inst_repo.exclusive():
            return method(self, *args, **kwargs)

    return wrapped


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

    This API is process and thread safe with regards to the Installed
    Packages Repository. There is no need to do external locking on it.
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
        misc_data = self._entropy.ClientSettings()['misc']
        config_protect = set()
        # also ask to Source Package Manager
        spm = self._entropy.Spm()

        if mask:
            config_protect |= misc_data['configprotectmask']
            # also read info from environment and merge here
            config_protect |= set(spm.get_merge_protected_paths_mask())
        else:
            config_protect |= misc_data['configprotect']
            # also read info from environment and merge here
            config_protect |= set(spm.get_merge_protected_paths())

        # get from our repositories
        for repository_id in self._repository_ids:
            # assume that all the repositories need separate locking.
            # this might be true in future.
            repo = self._entropy.open_repository(repository_id)
            with repo.shared():
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

    def _load_maybe_add(self, currentdir, item, filepath, number):
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

            for currentdir, _subdirs, files in os.walk(path):
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
                        currentdir, item, filepath, number)

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
