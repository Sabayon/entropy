# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
import errno
import os

from entropy.const import etpConst, const_convert_to_unicode, \
    const_convert_to_rawstring, const_is_python3
from entropy.i18n import _
from entropy.output import red, purple, brown, darkred, blue, darkgreen

import entropy.tools

from .. import _content as Content

from .action import PackageAction


class _PackageInstallRemoveAction(PackageAction):
    """
    Abstract class that exposes shared functions between install
    and remove PackageAction classes.
    """

    def __init__(self, entropy_client, package_match, opts = None):
        super(_PackageInstallRemoveAction, self).__init__(
            entropy_client, package_match, opts = opts)
        self._meta = None

    def metadata(self):
        """
        Return the package metadata dict object for manipulation.
        """
        return self._meta

    def setup(self):
        """
        Overridden from PackageAction.
        """
        raise NotImplementedError()

    def _run(self):
        """
        Overridden from PackageAction.
        """
        raise NotImplementedError()

    def _get_system_root(self):
        """
        Return the path to the system root directory.
        """
        metadata = self.metadata()
        return metadata.get('unittest_root', "") + etpConst['systemroot']

    def _get_config_protect_skip(self):
        """
        Return the configuration protection path set.
        """
        misc_settings = self._entropy.ClientSettings()['misc']
        protectskip = misc_settings['configprotectskip']

        if not const_is_python3():
            protectskip = set((
                const_convert_to_rawstring(
                    x, from_enctype = etpConst['conf_encoding']) for x in
                misc_settings['configprotectskip']))

        return protectskip

    def _get_config_protect(self, entropy_repository, package_id, mask = False):
        """
        Return configuration protection (or mask) metadata for the given
        package.
        This method should not be used as source for storing metadata into
        repositories since the returned objects may not be decoded in utf-8.
        Data returned by this method is expected to be used only by internal
        functions.
        """
        cl_id = etpConst['system_settings_plugins_ids']['client_plugin']
        misc_data = self._settings[cl_id]['misc']

        if mask:
            paths = entropy_repository.retrieveProtectMask(package_id).split()
            misc_key = "configprotectmask"
        else:
            paths = entropy_repository.retrieveProtect(package_id).split()
            misc_key = "configprotect"

        root = etpConst['systemroot']
        config = set(("%s%s" % (root, path) for path in paths))
        config.update(misc_data[misc_key])

        # os.* methods in Python 2.x do not expect unicode strings
        # This set of data is only used by _handle_config_protect atm.
        if not const_is_python3():
            config = set((const_convert_to_rawstring(x) for x in config))

        return config

    def _get_config_protect_metadata(self, installed_repository,
                                     installed_package_id):
        """
        Get the config_protect+mask metadata object.
        Make sure to call this before the package goes away from the
        repository.
        """
        protect = self._get_config_protect(
            installed_repository, installed_package_id)
        mask = self._get_config_protect(
            installed_repository, installed_package_id, mask = True)

        metadata = {
            'config_protect+mask': (protect, mask)
        }
        return metadata

    def _handle_config_protect(self, protect, mask, protectskip,
                               fromfile, tofile,
                               do_allocation_check = True,
                               do_quiet = False):
        """
        Handle configuration file protection. This method contains the logic
        for determining if a file should be protected from overwrite.
        """
        protected = False
        do_continue = False
        in_mask = False

        if tofile in protect:
            protected = True
            in_mask = True

        elif os.path.dirname(tofile) in protect:
            protected = True
            in_mask = True

        else:
            tofile_testdir = os.path.dirname(tofile)
            old_tofile_testdir = None
            while tofile_testdir != old_tofile_testdir:
                if tofile_testdir in protect:
                    protected = True
                    in_mask = True
                    break
                old_tofile_testdir = tofile_testdir
                tofile_testdir = os.path.dirname(tofile_testdir)

        if protected: # check if perhaps, file is masked, so unprotected

            if tofile in mask:
                protected = False
                in_mask = False

            elif os.path.dirname(tofile) in mask:
                protected = False
                in_mask = False

            else:
                tofile_testdir = os.path.dirname(tofile)
                old_tofile_testdir = None
                while tofile_testdir != old_tofile_testdir:
                    if tofile_testdir in mask:
                        protected = False
                        in_mask = False
                        break
                    old_tofile_testdir = tofile_testdir
                    tofile_testdir = os.path.dirname(tofile_testdir)

        if not os.path.lexists(tofile):
            protected = False # file doesn't exist

        # check if it's a text file
        if protected:
            protected = entropy.tools.istextfile(tofile)
            in_mask = protected

        if fromfile is not None:
            if protected and os.path.lexists(fromfile) and \
                (not os.path.exists(fromfile)) and os.path.islink(fromfile):
                # broken symlink, don't protect
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! Failed to handle file protection for: " \
                    "%s, broken symlink in package" % (
                        tofile,
                    )
                )
                msg = _("Cannot protect broken symlink")
                mytxt = "%s:" % (
                    purple(msg),
                )
                self._entropy.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = brown("   ## ")
                )
                self._entropy.output(
                    tofile,
                    level = "warning",
                    header = brown("   ## ")
                )
                protected = False

        if not protected:
            return in_mask, protected, tofile, do_continue

        ##                  ##
        # file is protected  #
        ##__________________##

        # check if protection is disabled for this element
        if tofile in protectskip:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Skipping config file installation/removal, " \
                "as stated in client.conf: %s" % (tofile,)
            )
            if not do_quiet:
                mytxt = "%s: %s" % (
                    _("Skipping file installation/removal"),
                    tofile,
                )
                self._entropy.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = darkred("   ## ")
                )
            do_continue = True
            return in_mask, protected, tofile, do_continue

        ##                      ##
        # file is protected (2)  #
        ##______________________##

        prot_status = True
        if do_allocation_check:
            spm_class = self._entropy.Spm_class()
            tofile, prot_status = spm_class.allocate_protected_file(fromfile,
                tofile)

        if not prot_status:
            # a protected file with the same content
            # is already in place, so not going to protect
            # the same file twice
            protected = False
            return in_mask, protected, tofile, do_continue

        ##                      ##
        # file is protected (3)  #
        ##______________________##

        oldtofile = tofile
        if oldtofile.find("._cfg") != -1:
            oldtofile = os.path.join(os.path.dirname(oldtofile),
                os.path.basename(oldtofile)[10:])

        if not do_quiet:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Protecting config file: %s" % (oldtofile,)
            )
            mytxt = red("%s: %s") % (_("Protecting config file"), oldtofile,)
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = darkred("   ## ")
            )

        return in_mask, protected, tofile, do_continue

    def _remove_content_from_system_loop(self, inst_repo, remove_content,
                                         directories, directories_cache,
                                         not_removed_due_to_collisions,
                                         colliding_path_messages,
                                         automerge_metadata, col_protect,
                                         protect, mask, protectskip,
                                         sys_root):
        """
        Body of the _remove_content_from_system() method.
        """
        info_dirs = self._get_info_directories()
        metadata = self.metadata()

        for _pkg_id, item, _ftype in remove_content:

            if not item:
                continue # empty element??

            sys_root_item = sys_root + item
            sys_root_item_encoded = sys_root_item
            if not const_is_python3():
                # this is coming from the db, and it's pure utf-8
                sys_root_item_encoded = const_convert_to_rawstring(
                    sys_root_item,
                    from_enctype = etpConst['conf_raw_encoding'])

            # collision check
            if col_protect > 0:

                if inst_repo.isFileAvailable(item) \
                    and os.path.isfile(sys_root_item_encoded):

                    # in this way we filter out directories
                    colliding_path_messages.add(sys_root_item)
                    not_removed_due_to_collisions.add(item)
                    continue

            protected = False
            in_mask = False

            if not metadata['removeconfig']:

                protected_item_test = sys_root_item
                (in_mask, protected, _x,
                 do_continue) = self._handle_config_protect(
                     protect, mask, protectskip, None, protected_item_test,
                     do_allocation_check = False, do_quiet = True
                 )

                if do_continue:
                    protected = True

            # when files have not been modified by the user
            # and they are inside a config protect directory
            # we could even remove them directly
            if in_mask:

                oldprot_md5 = automerge_metadata.get(item)
                if oldprot_md5:

                    try:
                        in_system_md5 = entropy.tools.md5sum(
                            protected_item_test)
                    except (OSError, IOError) as err:
                        if err.errno != errno.ENOENT:
                            raise
                        in_system_md5 = "?"

                    if oldprot_md5 == in_system_md5:
                        prot_msg = _("Removing config file, never modified")
                        mytxt = "%s: %s" % (
                            darkgreen(prot_msg),
                            blue(item),
                        )
                        self._entropy.output(
                            mytxt,
                            importance = 1,
                            level = "info",
                            header = red("   ## ")
                        )
                        protected = False
                        do_continue = False

            # Is file or directory a protected item?
            if protected:
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['verbose_loglevel_id'],
                    "[remove] Protecting config file: %s" % (sys_root_item,)
                )
                mytxt = "[%s] %s: %s" % (
                    red(_("remove")),
                    brown(_("Protecting config file")),
                    sys_root_item,
                )
                self._entropy.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = red("   ## ")
                )
                continue

            try:
                os.lstat(sys_root_item_encoded)
            except OSError as err:
                if err.errno in (errno.ENOENT, errno.ENOTDIR):
                    continue # skip file, does not exist
                raise

            except UnicodeEncodeError:
                msg = _("This package contains a badly encoded file !!!")
                mytxt = brown(msg)
                self._entropy.output(
                    red("QA: ")+mytxt,
                    importance = 1,
                    level = "warning",
                    header = darkred("   ## ")
                )
                continue # file has a really bad encoding

            if os.path.isdir(sys_root_item_encoded) and \
                os.path.islink(sys_root_item_encoded):
                # S_ISDIR returns False for directory symlinks,
                # so using os.path.isdir valid directory symlink
                if sys_root_item not in directories_cache:
                    # collect for Trigger
                    metadata['affected_directories'].add(item)
                    directories.add((sys_root_item, "link"))
                    directories_cache.add(sys_root_item)
                continue

            if os.path.isdir(sys_root_item_encoded):
                # plain directory
                if sys_root_item not in directories_cache:
                    # collect for Trigger
                    metadata['affected_directories'].add(item)
                    directories.add((sys_root_item, "dir"))
                    directories_cache.add(sys_root_item)
                continue

            # files, symlinks or not
            # just a file or symlink or broken
            # directory symlink (remove now)

            try:
                os.remove(sys_root_item_encoded)
            except OSError as err:
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "[remove] Unable to remove %s, error: %s" % (
                        sys_root_item, err,)
                )
                continue

            # collect for Trigger
            dir_name = os.path.dirname(item)
            metadata['affected_directories'].add(dir_name)

            # account for info files, if any
            if dir_name in info_dirs:
                for _ext in self._INFO_EXTS:
                    if item.endswith(_ext):
                        metadata['affected_infofiles'].add(item)
                        break

            # add its parent directory
            dirobj = const_convert_to_unicode(
                os.path.dirname(sys_root_item_encoded))
            if dirobj not in directories_cache:
                if os.path.isdir(dirobj) and os.path.islink(dirobj):
                    directories.add((dirobj, "link"))
                elif os.path.isdir(dirobj):
                    directories.add((dirobj, "dir"))

                directories_cache.add(dirobj)

    def _remove_content_from_system(self, installed_repository,
                                    automerge_metadata = None):
        """
        Remove installed package content (files/directories) from live system.

        @keyword automerge_metadata: Entropy "automerge metadata"
        @type automerge_metadata: dict
        """
        if automerge_metadata is None:
            automerge_metadata = {}

        metadata = self.metadata()
        sys_root = etpConst['systemroot']
        # load CONFIG_PROTECT and CONFIG_PROTECT_MASK
        misc_settings = self._entropy.ClientSettings()['misc']
        col_protect = misc_settings['collisionprotect']

        # remove files from system
        directories = set()
        directories_cache = set()
        not_removed_due_to_collisions = set()
        colliding_path_messages = set()

        protect_mask = metadata['config_protect+mask']
        if protect_mask is not None:
            protect, mask = protect_mask
        else:
            protect, mask = set(), set()
        protectskip = self._get_config_protect_skip()

        remove_content = None
        try:
            # simulate a removecontent list/set object
            remove_content = []
            if metadata['removecontent_file'] is not None:
                remove_content = Content.FileContentReader(
                    metadata['removecontent_file'])

            self._remove_content_from_system_loop(
                installed_repository,
                remove_content, directories, directories_cache,
                not_removed_due_to_collisions, colliding_path_messages,
                automerge_metadata, col_protect, protect, mask, protectskip,
                sys_root)

        finally:
            if hasattr(remove_content, "close"):
                remove_content.close()

        if colliding_path_messages:
            self._entropy.output(
                "%s:" % (_("Collision found during removal of"),),
                importance = 1,
                level = "warning",
                header = red("   ## ")
            )

        for path in sorted(colliding_path_messages):
            self._entropy.output(
                purple(path),
                importance = 0,
                level = "warning",
                header = red("   ## ")
            )
            self._entropy.logger.log(
                "[Package]", etpConst['logging']['normal_loglevel_id'],
                "Collision found during removal of %s - cannot overwrite" % (
                    path,)
            )

        # removing files not removed from removecontent.
        # it happened that boot services not removed due to
        # collisions got removed from their belonging runlevels
        # by postremove step.
        # since this is a set, it is a mapped type, so every
        # other instance around will feature this update
        if not_removed_due_to_collisions:
            def _filter(_path):
                return _path not in not_removed_due_to_collisions
            Content.filter_content_file(
                metadata['removecontent_file'],
                _filter)

        # now handle directories
        directories = sorted(directories, reverse = True)
        while True:
            taint = False
            for directory, dirtype in directories:
                mydir = "%s%s" % (sys_root, directory,)
                if dirtype == "link":
                    try:
                        mylist = os.listdir(mydir)
                        if not mylist:
                            try:
                                os.remove(mydir)
                                taint = True
                            except OSError:
                                pass
                    except OSError:
                        pass
                elif dirtype == "dir":
                    try:
                        mylist = os.listdir(mydir)
                        if not mylist:
                            try:
                                os.rmdir(mydir)
                                taint = True
                            except OSError:
                                pass
                    except OSError:
                        pass

            if not taint:
                break

        del directories_cache
        del directories

    def _spm_remove_package(self, atom):
        """
        Call Source Package Manager interface and tell it to remove our
        just removed package.

        @return: execution status
        @rtype: int
        """
        spm = self._entropy.Spm()
        self._entropy.logger.log(
            "[Package]",
            etpConst['logging']['normal_loglevel_id'],
            "Removing from SPM: %s" % (atom,)
        )
        return spm.remove_installed_package(self.metadata())
