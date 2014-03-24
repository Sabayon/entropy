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
import shutil
import stat
import time

from entropy.const import etpConst, const_convert_to_unicode, \
    const_mkdtemp, const_mkstemp, const_convert_to_rawstring, \
    const_is_python3, const_debug_write
from entropy.exceptions import EntropyException
from entropy.i18n import _
from entropy.output import darkred, red, purple, brown, blue, darkgreen, teal

import entropy.dep
import entropy.tools

from ._manage import _PackageInstallRemoveAction
from ._triggers import Trigger

from .. import _content as Content
from .. import preservedlibs


class _PackageInstallAction(_PackageInstallRemoveAction):
    """
    PackageAction used for package installation.
    """

    class InvalidArchitecture(EntropyException):
        """
        Raised when a package for another architecture is attempted
        to be installed.
        """

    NAME = "install"

    def __init__(self, entropy_client, package_match, opts = None):
        """
        Object constructor.
        """
        super(_PackageInstallAction, self).__init__(
            entropy_client, package_match, opts = opts)

    def finalize(self):
        """
        Finalize the object, release all its resources.
        """
        super(_PackageInstallAction, self).finalize()
        if self._meta is not None:
            meta = self._meta
            self._meta = None
            meta.clear()

    def _get_remove_package_id_unlocked(self, inst_repo):
        """
        Return the installed packages repository package id
        that would be removed.
        """
        repo = self._entropy.open_repository(self._repository_id)
        key_slot = repo.retrieveKeySlotAggregated(self._package_id)
        remove_package_id, _inst_rc = inst_repo.atomMatch(key_slot)
        return remove_package_id

    def setup(self):
        """
        Setup the PackageAction.
        """
        if self._meta is not None:
            # already configured
            return

        metadata = {}
        splitdebug_metadata = self._get_splitdebug_metadata()
        metadata.update(splitdebug_metadata)

        misc_settings = self._entropy.ClientSettings()['misc']
        metadata['edelta_support'] = misc_settings['edelta_support']
        is_package_repo = self._entropy._is_package_repository(
            self._repository_id)

        # These are used by Spm.entropy_install_unpack_hook()
        metadata['package_id'] = self._package_id
        metadata['repository_id'] = self._repository_id

        # if splitdebug is enabled, check if it's also enabled
        # via package.splitdebug
        if metadata['splitdebug']:
            # yeah, this has to affect exported splitdebug setting
            # because it is read during package files installation
            # Older splitdebug data was in the same package file of
            # the actual content. Later on, splitdebug data was moved
            # to its own package file that gets downloaded and unpacked
            # only if required (if splitdebug is enabled)
            metadata['splitdebug'] = self._package_splitdebug_enabled(
                self._package_match)

        # fetch abort function
        metadata['fetch_abort_function'] = self._opts.get(
            'fetch_abort_function')

        # Used by Spm.entropy_install_unpack_hook()
        metadata['repository_id'] = self._repository_id
        metadata['package_id'] = self._package_id

        install_source = etpConst['install_sources']['unknown']
        meta_inst_source = self._opts.get('install_source', install_source)
        if meta_inst_source in list(etpConst['install_sources'].values()):
            install_source = meta_inst_source
        metadata['install_source'] = install_source

        metadata['already_protected_config_files'] = {}
        metadata['configprotect_data'] = []

        repo = self._entropy.open_repository(self._repository_id)

        metadata['atom'] = repo.retrieveAtom(self._package_id)

        # use by Spm.entropy_install_unpack_hook(),
        # and remove_installed_package()
        metadata['category'] = repo.retrieveCategory(self._package_id)
        metadata['name'] = repo.retrieveName(self._package_id)
        metadata['version'] = repo.retrieveVersion(self._package_id)
        metadata['versiontag'] = repo.retrieveTag(self._package_id)
        metadata['slot'] = repo.retrieveSlot(self._package_id)

        metadata['extra_download'] = []
        metadata['splitdebug_pkgfile'] = True
        if not is_package_repo:
            metadata['splitdebug_pkgfile'] = False
            extra_download = repo.retrieveExtraDownload(self._package_id)
            if not metadata['splitdebug']:
                extra_download = [x for x in extra_download if \
                    x['type'] != "debug"]
            metadata['extra_download'] += extra_download

        metadata['download'] = repo.retrieveDownloadURL(self._package_id)

        description = repo.retrieveDescription(self._package_id)
        if description:
            if len(description) > 74:
                description = description[:74].strip()
                description += "..."
        metadata['description'] = description

        metadata['remove_metaopts'] = {
            'removeconfig': True,
        }
        metadata['remove_metaopts'].update(
            self._opts.get('remove_metaopts', {}))

        metadata['merge_from'] = None
        mf = self._opts.get('merge_from')
        if mf is not None:
            metadata['merge_from'] = const_convert_to_unicode(mf)
        metadata['removeconfig'] = self._opts.get('removeconfig', False)

        # collects directories whose content has been modified
        # this information is then handed to the Trigger
        metadata['affected_directories'] = set()
        metadata['affected_infofiles'] = set()

        # craete an atomically safe unpack directory path
        unpack_dir = os.path.join(
            etpConst['entropyunpackdir'],
            self._escape_path(metadata['atom']).lstrip(os.path.sep))
        try:
            os.makedirs(unpack_dir, 0o755)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise

        metadata['smartpackage'] = False
        # set unpack dir and image dir
        if is_package_repo:

            try:
                compiled_arch = repo.getSetting("arch")
                arch_fine = compiled_arch == etpConst['currentarch']
            except KeyError:
                arch_fine = True # sorry, old db, cannot check

            if not arch_fine:
                raise self.InvalidArchitecture(
                    "Package compiled for a different architecture")

            repo_data = self._settings['repositories']
            repo_meta = repo_data['available'][self._repository_id]
            metadata['smartpackage'] = repo_meta['smartpackage']

            # create a symlink into a generic entropy temp directory
            # and reference the file from there. This will avoid
            # Entropy locking code to change ownership and permissions
            # of the directory containing the package file.
            pkg_dir = const_mkdtemp(dir=unpack_dir, prefix="repository_pkgdir")
            pkgpath = os.path.join(
                pkg_dir, os.path.basename(repo_meta['pkgpath']))

            os.symlink(repo_meta['pkgpath'], pkgpath)

            metadata['pkgpath'] = pkgpath

        else:
            metadata['pkgpath'] = self.get_standard_fetch_disk_path(
                metadata['download'])

        metadata['unpackdir'] = const_mkdtemp(dir=unpack_dir)

        metadata['imagedir'] = os.path.join(
            metadata['unpackdir'],
            etpConst['entropyimagerelativepath'])

        metadata['pkgdbpath'] = os.path.join(metadata['unpackdir'],
            "edb", "pkg.db")

        metadata['phases'] = []
        metadata['phases'].append(self._remove_conflicts_phase)

        if metadata['merge_from']:
            metadata['phases'].append(self._merge_phase)
        else:
            metadata['phases'].append(self._unpack_phase)

        metadata['phases'].append(self._setup_package_phase)
        metadata['phases'].append(self._tarball_ownership_fixup_phase)
        metadata['phases'].append(self._pre_install_phase)
        metadata['phases'].append(self._install_phase)
        metadata['phases'].append(self._post_install_phase)
        metadata['phases'].append(self._cleanup_phase)

        # SPM can place metadata here if it should be copied to
        # the install trigger
        metadata['__install_trigger__'] = {}

        self._meta = metadata

    def _run(self):
        """
        Execute the action. Return an exit status.
        """
        self.setup()

        spm_class = self._entropy.Spm_class()
        exit_st = spm_class.entropy_install_setup_hook(
            self._entropy, self._meta)
        if exit_st != 0:
            return exit_st

        for method in self._meta['phases']:
            exit_st = method()
            if exit_st != 0:
                break
        return exit_st

    def _escape_path(self, path):
        """
        Some applications (like ld) don't like ":" in path, others just don't
        escape paths at all. So, it's better to avoid to use field separators
        in path.
        """
        path = path.replace(":", "_")
        path = path.replace("~", "_")
        return path

    def _get_package_conflicts_unlocked(self, inst_repo, entropy_repository,
                                        package_id):
        """
        Return a set of conflict dependencies for the given package.
        """
        conflicts = entropy_repository.retrieveConflicts(package_id)

        found_conflicts = set()
        for conflict in conflicts:
            inst_package_id, _inst_rc = inst_repo.atomMatch(conflict)
            if inst_package_id == -1:
                continue

            # check if the package shares the same key and slot
            match_data = entropy_repository.retrieveKeySlot(package_id)
            installed_match_data = inst_repo.retrieveKeySlot(inst_package_id)
            if match_data != installed_match_data:
                found_conflicts.add(inst_package_id)

        # auto conflicts support
        found_conflicts |= self._entropy._generate_dependency_inverse_conflicts(
            (package_id, entropy_repository.name), just_id=True)

        return found_conflicts

    def _remove_conflicts_phase(self):
        """
        Execute the package conflicts removal phase.
        """
        inst_repo = self._entropy.installed_repository()
        with inst_repo.shared():

            repo = self._entropy.open_repository(self._repository_id)
            confl_package_ids = self._get_package_conflicts_unlocked(
                inst_repo, repo, self._package_id)
            if not confl_package_ids:
                return 0

            # calculate removal dependencies
            # system_packages must be False because we should not exclude
            # them from the dependency tree in any case. Also, we cannot trigger
            # DependenciesNotRemovable() exception, too.
            proposed_pkg_ids = self._entropy.get_removal_queue(
                confl_package_ids, system_packages = False)
            # we don't want to remove the whole inverse dependencies of course,
            # but just the conflicting ones, in a proper order
            package_ids = [x for x in proposed_pkg_ids if x in
                           confl_package_ids]
            # make sure that every package is listed in package_ids before
            # proceeding, cannot keep packages behind anyway, and must be fault
            # tolerant. Besides, having missing packages here should never
            # happen.
            package_ids += [x for x in confl_package_ids if x not in \
                package_ids]

            if not package_ids:
                return 0

        # make sure to run this without locks, or deadlock happenz
        factory = self._entropy.PackageActionFactory()
        for package_id in package_ids:

            pkg = factory.get(
                factory.REMOVE_ACTION,
                (package_id, inst_repo.name),
                opts = self._meta['remove_metaopts'])
            pkg.set_xterm_header(self._xterm_header)

            exit_st = pkg.start()
            pkg.finalize()
            if exit_st != 0:
                return exit_st

        return 0

    def _unpack_package(self, package_path, image_dir, pkg_dbpath):
        """
        Effectively unpack the package tarballs.
        """
        txt = "%s: %s" % (
            blue(_("Unpacking")),
            red(os.path.basename(package_path)),
        )
        self._entropy.output(
            txt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        self._entropy.logger.log(
            "[Package]",
            etpConst['logging']['normal_loglevel_id'],
            "Unpacking package: %s" % (package_path,)
        )

        # removed in the meantime? fail.
        # this is just a safety measure, but won't do anything
        # against races.
        if not os.path.isfile(package_path):
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Error, package was removed: %s" % (package_path,)
            )
            return 1

        # make sure image_dir always exists
        # pkgs not providing any file would cause image_dir
        # to not be created by uncompress_tarball
        try:
            os.makedirs(image_dir, 0o755)
        except OSError as err:
            if err.errno != errno.EEXIST:
                self._entropy.logger.log(
                    "[Package]", etpConst['logging']['normal_loglevel_id'],
                    "Unable to mkdir: %s, error: %s" % (
                        image_dir, repr(err),)
                )
                self._entropy.output(
                    "%s: %s" % (brown(_("Unpack error")), err.errno,),
                    importance = 1,
                    level = "error",
                    header = red("   ## ")
                )
                return 1

        # pkg_dbpath is only non-None for the base package file
        # extra package files don't carry any other edb information
        if pkg_dbpath is not None:
            # extract entropy database from package file
            # in order to avoid having to read content data
            # from the repository database, which, in future
            # is allowed to not provide such info.
            pkg_dbdir = os.path.dirname(pkg_dbpath)
            try:
                os.makedirs(pkg_dbdir, 0o755)
            except OSError as err:
                if err.errno != errno.EEXIST:
                    raise
            # extract edb
            dump_exit_st = entropy.tools.dump_entropy_metadata(
                package_path, pkg_dbpath)
            if not dump_exit_st:
                # error during entropy db extraction from package file
                # might be because edb entry point is not found or
                # because there is not enough space for it
                self._entropy.logger.log(
                    "[Package]", etpConst['logging']['normal_loglevel_id'],
                    "Unable to dump edb for: " + pkg_dbpath
                )
                self._entropy.output(
                    brown(_("Unable to find Entropy metadata in package")),
                    importance = 1,
                    level = "error",
                    header = red("   ## ")
                )
                return 1

        try:
            exit_st = entropy.tools.uncompress_tarball(
                package_path,
                extract_path = image_dir,
                catch_empty = True
            )
        except EOFError as err:
            self._entropy.logger.log(
                "[Package]", etpConst['logging']['normal_loglevel_id'],
                "EOFError on " + package_path + " " + \
                repr(err)
            )
            entropy.tools.print_traceback()
            # try again until unpack_tries goes to 0
            exit_st = 1
        except Exception as err:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Ouch! error while unpacking " + \
                package_path + " " + repr(err)
            )
            entropy.tools.print_traceback()
            # try again until unpack_tries goes to 0
            exit_st = 1

        if exit_st != 0:
            self._entropy.logger.log(
                "[Package]", etpConst['logging']['normal_loglevel_id'],
                "Unable to unpack: %s" % (package_path,)
            )
            self._entropy.output(
                brown(_("Unable to unpack package")),
                importance = 1,
                level = "error",
                header = red("   ## ")
            )

        return exit_st

    def _fill_image_dir(self, merge_from, image_dir):
        """
        Fill the image directory with content from a filesystme path.
        """
        repo = self._entropy.open_repository(self._repository_id)
        # this is triggered by merge_from pkgmeta metadata
        # even if repositories are allowed to not have content
        # metadata, in this particular case, it is mandatory
        contents = repo.retrieveContentIter(
            self._package_id,
            order_by = "file")

        for path, ftype in contents:
            # convert back to filesystem str
            encoded_path = path
            path = os.path.join(merge_from, encoded_path[1:])
            topath = os.path.join(image_dir, encoded_path[1:])
            path = const_convert_to_rawstring(path)
            topath = const_convert_to_rawstring(topath)

            try:
                exist = os.lstat(path)
            except OSError:
                continue # skip file

            if "dir" == ftype and \
                not stat.S_ISDIR(exist.st_mode) and \
                os.path.isdir(path):
                # workaround for directory symlink issues
                path = os.path.realpath(path)

            copystat = False
            # if our directory is a symlink instead, then copy the symlink
            if os.path.islink(path):
                tolink = os.readlink(path)
                if os.path.islink(topath):
                    os.remove(topath)
                os.symlink(tolink, topath)
            elif os.path.isdir(path):
                try:
                    os.makedirs(topath)
                    copystat = True
                except OSError as err:
                    if err.errno != errno.EEXIST:
                        raise
            elif os.path.isfile(path):
                if os.path.isfile(topath):
                    os.remove(topath) # should never happen
                shutil.copy2(path, topath)
                copystat = True

            if copystat:
                user = os.stat(path)[stat.ST_UID]
                group = os.stat(path)[stat.ST_GID]
                os.chown(topath, user, group)
                shutil.copystat(path, topath)

    def _merge_phase(self):
        """
        Execute the merge (from) phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Merging"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        txt = "%s: %s" % (
            blue(_("Merging package")),
            red(self._meta['atom']),
        )
        self._entropy.output(
            txt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        self._entropy.logger.log(
            "[Package]",
            etpConst['logging']['normal_loglevel_id'],
            "Merging package: %s" % (self._meta['atom'],)
        )

        self._fill_image_dir(self._meta['merge_from'],
            self._meta['imagedir'])
        spm_class = self._entropy.Spm_class()
        return spm_class.entropy_install_unpack_hook(self._entropy,
            self._meta)

    def _unpack_phase(self):
        """
        Execute the unpack phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Unpacking"),
            self._meta['download'],
        )
        self._entropy.set_title(xterm_title)

        def _unpack_error(exit_st):
            msg = _("An error occurred while trying to unpack the package")
            errormsg = "%s. %s. %s: %s" % (
                red(msg),
                red(_("Check if your system is healthy")),
                blue(_("Error")),
                exit_st,
            )
            self._entropy.output(
                errormsg,
                importance = 1,
                level = "error",
                header = red("   ## ")
            )

        locks = []
        try:
            download_path = self._meta['pkgpath']
            lock = self.path_lock(download_path)
            locks.append(lock)

            with lock.shared():

                if not self._stat_path(download_path):
                    const_debug_write(
                        __name__,
                        "_unpack_phase: %s vanished" % (
                            download_path,))
                    _unpack_error(2)
                    return 2

                exit_st = self._unpack_package(
                    download_path,
                    self._meta['imagedir'],
                    self._meta['pkgdbpath'])

                if exit_st != 0:
                    const_debug_write(
                        __name__,
                        "_unpack_phase: %s unpack error: %s" % (
                            download_path, exit_st))
                    _unpack_error(exit_st)
                    return exit_st

            for extra_download in self._meta['extra_download']:
                download = extra_download['download']
                download_path = self.get_standard_fetch_disk_path(download)
                extra_lock = self.path_lock(download_path)
                locks.append(extra_lock)

                with extra_lock.shared():
                    if not self._stat_path(download_path):
                        const_debug_write(
                            __name__,
                            "_unpack_phase: %s vanished" % (
                                download_path,))
                        _unpack_error(2)
                        return 2

                    exit_st = self._unpack_package(
                        download_path,
                        self._meta['imagedir'],
                        None)

                    if exit_st != 0:
                        const_debug_write(
                            __name__,
                            "_unpack_phase: %s unpack error: %s" % (
                                download_path, exit_st,))
                        _unpack_error(exit_st)
                        return exit_st

        finally:
            for l in locks:
                l.close()

        spm_class = self._entropy.Spm_class()
        # call Spm unpack hook
        return spm_class.entropy_install_unpack_hook(self._entropy,
            self._meta)

    def _setup_package_phase(self):
        """
        Execute the package setup phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Setup"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        data = self._get_install_trigger_data()
        trigger = Trigger(
            self._entropy,
            self.NAME,
            "setup",
            data,
            data)

        exit_st = 0
        ack = trigger.prepare()
        if ack:
            exit_st = trigger.run()
        trigger.kill()

        if exit_st != 0:
            return exit_st

        return 0

    def _pre_install_phase(self):
        """
        Execute the pre-install phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Pre-install"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        data = self._get_install_trigger_data()
        trigger = Trigger(
            self._entropy,
            self.NAME,
            "preinstall",
            data,
            data)

        exit_st = 0
        ack = trigger.prepare()
        if ack:
            exit_st = trigger.run()
        trigger.kill()

        return exit_st

    def _tarball_ownership_fixup_phase(self):
        """
        Execute the tarball file ownership fixup phase.
        New uid or gids could have created after the setup phase.
        """
        # NOTE: fixup permissions in the image directory
        # the setup phase could have created additional users and groups
        package_paths = [self._meta['pkgpath']]
        for extra_download in self._meta['extra_download']:
            package_paths.append(
                self.get_standard_fetch_disk_path(extra_download['download'])
            )

        for package_path in package_paths:
            lock = None

            try:
                lock = self.path_lock(package_path)
                with lock.shared():

                    if not self._stat_path(package_path):
                        const_debug_write(
                            __name__,
                            "_tarball_ownership_fixup_phase: %s vanished" % (
                                package_path,))

                        self._entropy.output(
                            "%s: vanished" % (
                                brown(_("Error during package files "
                                        "permissions setup"))
                                ,),
                            importance = 1,
                            level = "error",
                            header = darkred(" !!! ")
                        )
                        return 1

                    try:
                        entropy.tools.apply_tarball_ownership(
                            package_path, self._meta['imagedir'])
                    except IOError as err:
                        msg = "%s: %s" % (
                            brown(_("Error during package files "
                                    "permissions setup")),
                            err,)

                        self._entropy.output(
                            msg,
                            importance = 1,
                            level = "error",
                            header = darkred(" !!! ")
                        )
                        return 1

            finally:
                if lock is not None:
                    lock.close()

        return 0

    def _get_install_trigger_data(self):
        """
        Get the metadata used during removal phases by Trigger.
        """
        repo = self._entropy.open_repository(self._repository_id)

        data = {}
        data.update(repo.getTriggerData(self._package_id))

        splitdebug_metadata = self._get_splitdebug_metadata()
        data.update(splitdebug_metadata)

        data['unpackdir'] = self._meta['unpackdir']
        data['imagedir'] = self._meta['imagedir']

        data['affected_directories'] = self._meta['affected_directories']
        data['affected_infofiles'] = self._meta['affected_infofiles']
        data['spm_repository'] = repo.retrieveSpmRepository(self._package_id)
        data['accept_license'] = self._get_licenses(repo, self._package_id)

        # replace current empty "content" metadata info
        # content metadata is required by
        # _spm_install_package() -> Spm.add_installed_package()
        # in case of injected packages (SPM metadata might be
        # incomplete).
        data['content'] = self._meta.get('content', data['content'])

        # SPM hook
        data.update(self._meta['__install_trigger__'])

        return data

    def _pre_remove_package_unlocked(self, data):
        """
        Execute the pre-remove phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Pre-remove"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        trigger = Trigger(
            self._entropy,
            self.NAME,
            "preremove",
            data,
            self._get_install_trigger_data())

        exit_st = 0
        ack = trigger.prepare()
        if ack:
            exit_st = trigger.run()
        trigger.kill()

        return exit_st

    def _install_clean_unlocked(self, inst_repo, installed_package_id,
                                clean_content, removecontent_file,
                                remove_atom, removed_libs,
                                config_protect_metadata):
        """
        Cleanup package files not used anymore by newly installed version.
        This is part of the atomic install, which overwrites the live fs with
        new files and removes old afterwards.
        """
        sys_root = self._get_system_root(self._meta)

        preserved_mgr = preservedlibs.PreservedLibraries(
            inst_repo, installed_package_id,
            removed_libs, root = sys_root)

        if clean_content:
            self._entropy.output(
                blue(_("Cleaning previously installed application data.")),
                importance = 1,
                level = "info",
                header = red("   ## ")
            )

            self._remove_content_from_system(
                inst_repo,
                remove_atom,
                self._meta['removeconfig'],
                sys_root,
                config_protect_metadata['config_protect+mask'],
                removecontent_file,
                self._meta['already_protected_config_files'],
                self._meta['affected_directories'],
                self._meta['affected_infofiles'],
                preserved_mgr)

        # garbage collect preserved libraries that are no longer needed
        self._garbage_collect_preserved_libs(preserved_mgr)

        return 0

    def _post_remove_package_unlocked(self, data):
        """
        Execute the post-remove phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Post-remove"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        trigger = Trigger(
            self._entropy,
            self.NAME,
            "postremove",
            data,
            self._get_install_trigger_data())

        exit_st = 0
        ack = trigger.prepare()
        if ack:
            exit_st = trigger.run()
        trigger.kill()

        return exit_st

    def _post_remove_install_package_unlocked(self, atom):
        """
        Execute the post-remove SPM package metadata phase.
        """
        self._entropy.logger.log(
            "[Package]",
            etpConst['logging']['normal_loglevel_id'],
            "Remove old package (spm data): %s" % (atom,)
        )

        return self._spm_remove_package(atom, self._meta)

    def _install_spm_package_unlocked(self, inst_repo, installed_package_id):
        """
        Execute the installation of SPM package metadata.
        """
        spm = self._entropy.Spm()

        self._entropy.logger.log(
            "[Package]",
            etpConst['logging']['normal_loglevel_id'],
            "Installing new SPM entry: %s" % (self._meta['atom'],)
        )

        spm_uid = spm.add_installed_package(self._meta)
        if spm_uid != -1:
            inst_repo.insertSpmUid(installed_package_id, spm_uid)
            inst_repo.commit()

        return 0

    def _post_install_phase(self):
        """
        Execute the post-install phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Post-install"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        data = self._get_install_trigger_data()
        trigger = Trigger(
            self._entropy,
            self.NAME,
            "postinstall",
            data,
            data)

        exit_st = 0
        ack = trigger.prepare()
        if ack:
            exit_st = trigger.run()
        trigger.kill()

        return exit_st

    def _cleanup_phase(self):
        """
        Execute the cleanup phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Cleaning"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        txt = "%s: %s" % (
            blue(_("Cleaning")),
            red(self._meta['atom']),
        )
        self._entropy.output(
            txt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        # shutil.rmtree wants raw strings, otherwise it will explode
        unpack_dir = const_convert_to_rawstring(self._meta['unpackdir'])

        # best-effort below.
        try:
            shutil.rmtree(unpack_dir, True)
        except shutil.Error as err:
            self._entropy.logger.log(
                "[Package]", etpConst['logging']['normal_loglevel_id'],
                "WARNING!!! Failed to cleanup directory %s," \
                " error: %s" % (unpack_dir, err,))
        try:
            os.rmdir(unpack_dir)
        except OSError:
            pass

        return 0

    def _filter_out_files_installed_on_diff_path(self, content_file,
                                                 installed_content):
        """
        Use case: if a package provided files in /lib then, a new version
        of that package moved the same files under /lib64, we need to check
        if both directory paths solve to the same inode and if so,
        add to our set that we're going to return.
        """
        sys_root = self._get_system_root(self._meta)
        second_pass_removal = set()

        if not installed_content:
            # nothing to filter, no-op
            return
        def _main_filter(_path):
            item_dir = os.path.dirname("%s%s" % (
                    sys_root, _path,))
            item = os.path.join(
                os.path.realpath(item_dir),
                os.path.basename(_path))
            if item in installed_content:
                second_pass_removal.add(item)
                return False
            return True

        # first pass, remove direct matches, schedule a second pass
        # list of files
        Content.filter_content_file(content_file, _main_filter)

        if not second_pass_removal:
            # done then
            return

        # second pass, drop remaining files
        # unfortunately, this is the only way to work it out
        # with iterators
        def _filter(_path):
            return _path not in second_pass_removal
        Content.filter_content_file(content_file, _filter)

    def _add_installed_package_unlocked(self, inst_repo,removecontent_file,
                                        items_installed, items_not_installed):
        """
        For internal use only.
        Copy package from repository to installed packages one.
        """

        def _merge_removecontent(inst_repo, repo, _package_id):

            # nothing to do if there is no content to remove
            if removecontent_file is None:
                return

            # determine if there is a package to remove first
            remove_package_id = self._get_remove_package_id_unlocked(inst_repo)
            if remove_package_id == -1:
                return

            # NOTE: this could be a source of memory consumption
            # but generally, the difference between two contents
            # is really small
            content_diff = list(inst_repo.contentDiff(
                remove_package_id,
                repo,
                _package_id,
                extended=True))

            if content_diff:

                # reverse-order compare
                def _cmp_func(_path, _spath):
                    if _path > _spath:
                        return -1
                    elif _path == _spath:
                        return 0
                    return 1

                # must be sorted, and in reverse order
                # or the merge step won't work
                content_diff.sort(reverse=True)

                Content.merge_content_file(
                    removecontent_file,
                    content_diff, _cmp_func)

        smart_pkg = self._meta['smartpackage']
        repo = self._entropy.open_repository(self._repository_id)

        splitdebug, splitdebug_dirs = (
            self._meta['splitdebug'],
            self._meta['splitdebug_dirs'])

        if smart_pkg or self._meta['merge_from']:

            data = repo.getPackageData(self._package_id,
                content_insert_formatted = True,
                get_changelog = False, get_content = False,
                get_content_safety = False)

            content = repo.retrieveContentIter(
                self._package_id)
            content_file = self._generate_content_file(
                content, package_id = self._package_id,
                filter_splitdebug = True,
                splitdebug = splitdebug,
                splitdebug_dirs = splitdebug_dirs)

            content_safety = repo.retrieveContentSafetyIter(
                self._package_id)
            content_safety_file = self._generate_content_safety_file(
                content_safety)

            _merge_removecontent(inst_repo, repo, self._package_id)

        else:

            # normal repositories
            data = repo.getPackageData(self._package_id,
                get_content = False, get_changelog = False)

            # indexing_override = False : no need to index tables
            # xcache = False : no need to use on-disk cache
            # skipChecks = False : creating missing tables is unwanted,
            # and also no foreign keys update
            # readOnly = True: no need to open in write mode
            pkg_repo = self._entropy.open_generic_repository(
                self._meta['pkgdbpath'], skip_checks = True,
                indexing_override = False, read_only = True,
                xcache = False)

            # it is safe to consider that package dbs coming from repos
            # contain only one entry
            pkg_package_id = sorted(pkg_repo.listAllPackageIds(),
                reverse = True)[0]
            content = pkg_repo.retrieveContentIter(
                pkg_package_id)
            content_file = self._generate_content_file(
                content, package_id = self._package_id,
                filter_splitdebug = True,
                splitdebug = splitdebug,
                splitdebug_dirs = splitdebug_dirs)

            # setup content safety metadata, get from package
            content_safety = pkg_repo.retrieveContentSafetyIter(
                pkg_package_id)
            content_safety_file = self._generate_content_safety_file(
                content_safety)

            _merge_removecontent(inst_repo, pkg_repo, pkg_package_id)

            pkg_repo.close()

        # items_installed is useful to avoid the removal of installed
        # files by __remove_package just because
        # there's a difference in the directory path, perhaps,
        # which is not handled correctly by
        # EntropyRepository.contentDiff for obvious reasons
        # (think about stuff in /usr/lib and /usr/lib64,
        # where the latter is just a symlink to the former)
        # --
        # fix removecontent, need to check if we just installed files
        # that resolves at the same directory path (different symlink)
        if removecontent_file is not None:
            self._filter_out_files_installed_on_diff_path(
                removecontent_file, items_installed)

        # filter out files not installed from content metadata
        # these include splitdebug files, when splitdebug is
        # disabled.
        if items_not_installed:
            def _filter(_path):
                return _path not in items_not_installed
            Content.filter_content_file(
                content_file, _filter)

        # always set data['injected'] to False
        # installed packages database SHOULD never have more
        # than one package for scope (key+slot)
        data['injected'] = False
        # spm counter will be set in self._install_package_into_spm_database()
        data['counter'] = -1
        # branch must be always set properly, it could happen it's not
        # when installing packages through their .tbz2s
        data['branch'] = self._settings['repositories']['branch']
        # there is no need to store needed paths into db
        if "needed_paths" in data:
            del data['needed_paths']
        # there is no need to store changelog data into db
        if "changelog" in data:
            del data['changelog']
        # we don't want it to be added now, we want to add install source
        # info too.
        if "original_repository" in data:
            del data['original_repository']
        # rewrite extra_download metadata with the currently provided,
        # and accepted extra_download items (in case of splitdebug being
        # disable, we're not going to add those entries, for example)
        data['extra_download'] = self._meta['extra_download']

        data['content'] = None
        data['content_safety'] = None
        try:
            # now we are ready to craft a 'content' iter object
            data['content'] = Content.FileContentReader(
                content_file)
            data['content_safety'] = Content.FileContentSafetyReader(
                content_safety_file)
            package_id = inst_repo.handlePackage(
                data, revision = data['revision'],
                formattedContent = True)
        finally:
            if data['content'] is not None:
                try:
                    data['content'].close()
                    data['content'] = None
                except (OSError, IOError):
                    data['content'] = None
            if data['content_safety'] is not None:
                try:
                    data['content_safety'].close()
                    data['content_safety'] = None
                except (OSError, IOError):
                    data['content_safety'] = None

        # update datecreation
        ctime = time.time()
        inst_repo.setCreationDate(package_id, str(ctime))

        # add idpk to the installedtable
        inst_repo.dropInstalledPackageFromStore(package_id)
        inst_repo.storeInstalledPackage(package_id,
            self._repository_id, self._meta['install_source'])

        automerge_data = self._meta.get('configprotect_data')
        if automerge_data:
            inst_repo.insertAutomergefiles(package_id, automerge_data)

        inst_repo.commit()

        # replace current empty "content" metadata info
        # content metadata is required by
        # _spm_install_package() -> Spm.add_installed_package()
        # in case of injected packages (SPM metadata might be
        # incomplete).
        self._meta['content'] = Content.FileContentReader(content_file)

        return package_id

    def _install_package_unlocked(self, inst_repo, remove_package_id):
        """
        Execute the package installation code.
        """
        self._entropy.clear_cache()

        self._entropy.logger.log(
            "[Package]",
            etpConst['logging']['normal_loglevel_id'],
            "Installing package: %s" % (self._meta['atom'],)
        )

        if remove_package_id != -1:
            am_files = inst_repo.retrieveAutomergefiles(
                remove_package_id,
                get_dict = True)
            self._meta['already_protected_config_files'].clear()
            self._meta['already_protected_config_files'].update(am_files)

        # items_*installed will be filled by _move_image_to_system
        # then passed to _add_installed_package()
        items_installed = set()
        items_not_installed = set()
        exit_st = self._move_image_to_system_unlocked(
            inst_repo, remove_package_id,
            items_installed, items_not_installed)

        if exit_st != 0:
            txt = "%s. %s. %s: %s" % (
                red(_("An error occurred while trying to install the package")),
                red(_("Check if your system is healthy")),
                blue(_("Error")),
                exit_st,
            )
            self._entropy.output(
                txt,
                importance = 1,
                level = "error",
                header = red("   ## ")
            )
            return exit_st, None, None

        txt = "%s: %s" % (
            blue(_("Updating installed packages repository")),
            teal(self._meta['atom']),
        )
        self._entropy.output(
            txt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        # generate the files and directories that would be removed
        removecontent_file = None
        if remove_package_id != -1:
            removecontent_file = self._generate_content_file(
                inst_repo.retrieveContentIter(
                    remove_package_id,
                    order_by="file",
                    reverse=True)
            )

        package_id = self._add_installed_package_unlocked(
            inst_repo, removecontent_file,
            items_installed, items_not_installed)

        return 0, package_id, removecontent_file

    def _install_phase(self):
        """
        Execute the install phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Installing"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        txt = "%s: %s" % (
            blue(_("Installing package")),
            red(self._meta['atom']),
        )
        self._entropy.output(
            txt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        self._entropy.output(
            "[%s]" % (
                purple(self._meta['description']),
            ),
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        if self._meta['splitdebug']:
            if self._meta.get('splitdebug_pkgfile'):
                txt = "[%s]" % (
                    teal(_("unsupported splitdebug usage (package files)")),)
                level = "warning"
            else:
                txt = "[%s]" % (
                    teal(_("<3 debug files installation enabled <3")),)
                level = "info"
            self._entropy.output(
                txt,
                importance = 1,
                level = level,
                header = red("   ## ")
            )

        inst_repo = self._entropy.installed_repository()
        with inst_repo.exclusive():
            return self._install_phase_unlocked(inst_repo)

    def _install_phase_unlocked(self, inst_repo):
        """
        _install_phase(), assuming that the installed packages repository
        lock is held in exclusive mode.
        """
        remove_package_id = self._get_remove_package_id_unlocked(inst_repo)

        remove_atom = None
        if remove_package_id != -1:
            remove_atom = inst_repo.retrieveAtom(remove_package_id)

        # save trigger data
        remove_trigger_data = None
        if remove_package_id != -1:
            remove_trigger_data = self._get_remove_trigger_data(
                inst_repo, remove_package_id)

        if remove_package_id == -1:
            removed_libs = frozenset()
        else:
            repo = self._entropy.open_repository(self._repository_id)
            repo_libs = repo.retrieveProvidedLibraries(self._package_id)
            inst_libs = inst_repo.retrieveProvidedLibraries(
                remove_package_id)
            removed_libs = frozenset(inst_libs - repo_libs)

        config_protect_metadata = None
        if remove_package_id != -1:
            config_protect_metadata = self._get_config_protect_metadata(
                inst_repo, remove_package_id, _metadata = self._meta)

        # after this point, old package metadata is no longer available

        (exit_st, installed_package_id,
         removecontent_file) = self._install_package_unlocked(
             inst_repo, remove_package_id)
        if exit_st != 0:
            return exit_st

        if remove_trigger_data:
            exit_st = self._pre_remove_package_unlocked(remove_trigger_data)
            if exit_st != 0:
                return exit_st

        clean_content = remove_package_id != -1
        exit_st = self._install_clean_unlocked(
            inst_repo, installed_package_id,
            clean_content, removecontent_file,
            remove_atom, removed_libs,
            config_protect_metadata)
        if exit_st != 0:
            return exit_st

        if remove_trigger_data:
            exit_st = self._post_remove_package_unlocked(
                remove_trigger_data)
            if exit_st != 0:
                return exit_st

        if remove_package_id != -1:
            exit_st = self._post_remove_install_package_unlocked(
                remove_atom)
            if exit_st != 0:
                return exit_st

        exit_st = self._install_spm_package_unlocked(
            inst_repo, installed_package_id)
        if exit_st != 0:
            return exit_st

        return 0

    def _handle_install_collision_protect_unlocked(self, inst_repo,
                                                   remove_package_id,
                                                   tofile,
                                                   todbfile):
        """
        Handle files collition protection for the install phase.
        """

        avail = inst_repo.isFileAvailable(
            const_convert_to_unicode(todbfile),
            get_id = True)

        if (remove_package_id not in avail) and avail:
            mytxt = darkred(_("Collision found during install for"))
            mytxt += "%s %s - %s" % (
                blue(_("QA:")),
                blue(tofile),
                darkred(_("cannot overwrite")),
            )
            self._entropy.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = darkred("   ## ")
            )
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "WARNING!!! Collision found during install " \
                "for %s - cannot overwrite" % (tofile,)
            )
            return False

        return True

    def _move_image_to_system_unlocked(self, inst_repo, remove_package_id,
                                       items_installed, items_not_installed):
        """
        Internal method that moves the package image directory to the live
        filesystem.
        """
        metadata = self.metadata()
        repo = self._entropy.open_repository(self._repository_id)
        protect = self._get_config_protect(repo, self._package_id)
        mask = self._get_config_protect(repo, self._package_id,
                                        mask = True)
        protectskip = self._get_config_protect_skip()

        # support for unit testing settings
        sys_root = self._get_system_root(metadata)
        misc_data = self._entropy.ClientSettings()['misc']
        col_protect = misc_data['collisionprotect']
        splitdebug, splitdebug_dirs = metadata['splitdebug'], \
            metadata['splitdebug_dirs']
        info_dirs = self._get_info_directories()

        # setup image_dir properly
        image_dir = metadata['imagedir'][:]
        if not const_is_python3():
            # image_dir comes from unpackdir, which comes from download
            # metadatum, which is utf-8 (conf_encoding)
            image_dir = const_convert_to_rawstring(image_dir,
                from_enctype = etpConst['conf_encoding'])
        movefile = entropy.tools.movefile

        def workout_subdir(currentdir, subdir):

            imagepath_dir = os.path.join(currentdir, subdir)
            rel_imagepath_dir = imagepath_dir[len(image_dir):]
            rootdir = sys_root + rel_imagepath_dir

            # splitdebug (.debug files) support
            # If splitdebug is not enabled, do not create splitdebug directories
            # and move on instead (return)
            if not splitdebug:
                for split_dir in splitdebug_dirs:
                    if rootdir.startswith(split_dir):
                        # also drop item from content metadata. In this way
                        # SPM has in sync information on what the package
                        # content really is.
                        # ---
                        # we should really use unicode
                        # strings for items_not_installed
                        unicode_rootdir = const_convert_to_unicode(rootdir)
                        items_not_installed.add(unicode_rootdir)
                        return 0

            # handle broken symlinks
            if os.path.islink(rootdir) and not os.path.exists(rootdir):
                # broken symlink
                os.remove(rootdir)

            # if our directory is a file on the live system
            elif os.path.isfile(rootdir): # really weird...!

                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! %s is a file when it should be " \
                    "a directory" % (rootdir,)
                )
                mytxt = darkred(_("QA: %s is a file when it should "
                                  "be a directory") % (rootdir,))

                self._entropy.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = red(" !!! ")
                )
                rootdir_dir = os.path.dirname(rootdir)
                rootdir_name = os.path.basename(rootdir)
                tmp_fd, tmp_path = None, None
                try:
                    tmp_fd, tmp_path = const_mkstemp(
                        dir = rootdir_dir, prefix=rootdir_name)
                    os.rename(rootdir, tmp_path)
                finally:
                    if tmp_fd is not None:
                        try:
                            os.close(tmp_fd)
                        except OSError:
                            pass

                self._entropy.output(
                    "%s: %s -> %s" % (
                        darkred(_("File moved")),
                        blue(rootdir),
                        darkred(tmp_path),
                    ),
                    importance = 1,
                    level = "warning",
                    header = brown(" @@ ")
                )

            # if our directory is a symlink instead, then copy the symlink
            if os.path.islink(imagepath_dir):

                # if our live system features a directory instead of
                # a symlink, we should consider removing the directory
                if not os.path.islink(rootdir) and os.path.isdir(rootdir):
                    self._entropy.logger.log(
                        "[Package]",
                        etpConst['logging']['normal_loglevel_id'],
                        "WARNING!!! %s is a directory when it should be " \
                        "a symlink !!" % (rootdir,)
                    )
                    txt = "%s: %s" % (
                        _("QA: symlink expected, directory found"),
                        rootdir,
                    )
                    self._entropy.output(
                        darkred(txt),
                        importance = 1,
                        level = "warning",
                        header = red(" !!! ")
                    )

                    return 0

                tolink = os.readlink(imagepath_dir)
                live_tolink = None
                if os.path.islink(rootdir):
                    live_tolink = os.readlink(rootdir)

                if tolink != live_tolink:
                    _symfail = False
                    if os.path.lexists(rootdir):
                        # at this point, it must be a file
                        try:
                            os.remove(rootdir)
                        except OSError as err:
                            _symfail = True
                            # must be atomic, too bad if it fails
                            self._entropy.logger.log(
                                "[Package]",
                                etpConst['logging']['normal_loglevel_id'],
                                "WARNING!!! Failed to remove %s " \
                                "file ! [workout_file/0]: %s" % (
                                    rootdir, err,
                                )
                            )
                            msg = _("Cannot remove symlink")
                            mytxt = "%s: %s => %s" % (
                                purple(msg),
                                blue(rootdir),
                                repr(err),
                            )
                            self._entropy.output(
                                mytxt,
                                importance = 1,
                                level = "warning",
                                header = brown("   ## ")
                            )
                    if not _symfail:
                        os.symlink(tolink, rootdir)

            elif not os.path.isdir(rootdir):
                # directory not found, we need to create it
                try:
                    # really force a simple mkdir first of all
                    os.mkdir(rootdir)
                except (OSError, IOError) as err:
                    # the only two allowed errors are these
                    if err.errno not in (errno.EEXIST, errno.ENOENT):
                        raise

                    # if the error is about ENOENT, try creating
                    # the whole directory tree and check against races
                    # (EEXIST).
                    if err.errno == errno.ENOENT:
                        try:
                            os.makedirs(rootdir)
                        except (OSError, IOError) as err2:
                            if err2.errno != errno.EEXIST:
                                raise

            if not os.path.islink(rootdir):

                # symlink doesn't need permissions, also
                # until os.walk ends they might be broken
                user = os.stat(imagepath_dir)[stat.ST_UID]
                group = os.stat(imagepath_dir)[stat.ST_GID]
                try:
                    os.chown(rootdir, user, group)
                    shutil.copystat(imagepath_dir, rootdir)
                except (OSError, IOError) as err:
                    self._entropy.logger.log(
                        "[Package]",
                        etpConst['logging']['normal_loglevel_id'],
                        "Error during workdir setup " \
                        "%s, %s, errno: %s" % (
                                rootdir,
                                err,
                                err.errno,
                            )
                    )
                    # skip some errors because we may have
                    # unwritable directories
                    if err.errno not in (
                            errno.EPERM, errno.ENOENT,
                            errno.ENOTDIR):
                        mytxt = "%s: %s, %s, %s" % (
                            brown("Error during workdir setup"),
                            purple(rootdir), err,
                            err.errno
                        )
                        self._entropy.output(
                            mytxt,
                            importance = 1,
                            level = "error",
                            header = darkred(" !!! ")
                        )
                        return 4

            item_dir, item_base = os.path.split(rootdir)
            item_dir = os.path.realpath(item_dir)
            item_inst = os.path.join(item_dir, item_base)
            item_inst = const_convert_to_unicode(item_inst)
            items_installed.add(item_inst)

            return 0


        def workout_file(currentdir, item):

            fromfile = os.path.join(currentdir, item)
            rel_fromfile = fromfile[len(image_dir):]
            rel_fromfile_dir = os.path.dirname(rel_fromfile)
            tofile = sys_root + rel_fromfile

            rel_fromfile_dir_utf = const_convert_to_unicode(
                rel_fromfile_dir)
            metadata['affected_directories'].add(
                rel_fromfile_dir_utf)

            # account for info files, if any
            if rel_fromfile_dir_utf in info_dirs:
                rel_fromfile_utf = const_convert_to_unicode(
                    rel_fromfile)
                for _ext in self._INFO_EXTS:
                    if rel_fromfile_utf.endswith(_ext):
                        metadata['affected_infofiles'].add(
                            rel_fromfile_utf)
                        break

            # splitdebug (.debug files) support
            # If splitdebug is not enabled, do not create
            # splitdebug directories and move on instead (return)
            if not splitdebug:
                for split_dir in splitdebug_dirs:
                    if tofile.startswith(split_dir):
                        # also drop item from content metadata. In this way
                        # SPM has in sync information on what the package
                        # content really is.
                        # ---
                        # we should really use unicode
                        # strings for items_not_installed
                        unicode_tofile = const_convert_to_unicode(tofile)
                        items_not_installed.add(unicode_tofile)
                        return 0

            if col_protect > 1:
                todbfile = fromfile[len(image_dir):]
                myrc = self._handle_install_collision_protect_unlocked(
                    inst_repo, remove_package_id, tofile, todbfile)
                if not myrc:
                    return 0

            prot_old_tofile = tofile[len(sys_root):]
            # configprotect_data is passed to insertAutomergefiles()
            # which always expects unicode data.
            # revert back to unicode (we previously called encode on
            # image_dir (which is passed to os.walk, which generates
            # raw strings)
            prot_old_tofile = const_convert_to_unicode(prot_old_tofile)

            pre_tofile = tofile[:]
            (in_mask, protected,
             tofile, do_return) = self._handle_config_protect(
                 protect, mask, protectskip, fromfile, tofile)

            # collect new config automerge data
            if in_mask and os.path.exists(fromfile):
                try:
                    prot_md5 = const_convert_to_unicode(
                        entropy.tools.md5sum(fromfile))
                    metadata['configprotect_data'].append(
                        (prot_old_tofile, prot_md5,))
                except (IOError,) as err:
                    self._entropy.logger.log(
                        "[Package]",
                        etpConst['logging']['normal_loglevel_id'],
                        "WARNING!!! Failed to get md5 of %s " \
                        "file ! [workout_file/1]: %s" % (
                            fromfile, err,
                        )
                    )

            # check if it's really necessary to protect file
            if protected:

                # second task
                # prot_old_tofile is always unicode, it must be, see above
                oldprot_md5 = metadata['already_protected_config_files'].get(
                    prot_old_tofile)

                if oldprot_md5:

                    try:
                        in_system_md5 = entropy.tools.md5sum(pre_tofile)
                    except (OSError, IOError) as err:
                        if err.errno != errno.ENOENT:
                            raise
                        in_system_md5 = "?"

                    if oldprot_md5 == in_system_md5:
                        # we can merge it, files, even if
                        # contains changes have not been modified
                        # by the user
                        msg = _("Automerging config file, never modified")
                        mytxt = "%s: %s" % (
                            darkgreen(msg),
                            blue(pre_tofile),
                        )
                        self._entropy.output(
                            mytxt,
                            importance = 1,
                            level = "info",
                            header = red("   ## ")
                        )
                        protected = False
                        do_return = False
                        tofile = pre_tofile

            if do_return:
                return 0

            try:
                from_r_path = os.path.realpath(fromfile)
            except RuntimeError:
                # circular symlink, fuck!
                # really weird...!
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! %s is a circular symlink !!!" % (fromfile,)
                )
                txt = "%s: %s" % (
                    _("QA: circular symlink issue"),
                    const_convert_to_unicode(fromfile),
                )
                self._entropy.output(
                    darkred(txt),
                    importance = 1,
                    level = "warning",
                    header = red(" !!! ")
                )
                from_r_path = fromfile

            try:
                to_r_path = os.path.realpath(tofile)
            except RuntimeError:
                # circular symlink, fuck!
                # really weird...!
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! %s is a circular symlink !!!" % (tofile,)
                )
                mytxt = "%s: %s" % (
                    _("QA: circular symlink issue"),
                    const_convert_to_unicode(tofile),
                )
                self._entropy.output(
                    darkred(mytxt),
                    importance = 1,
                    level = "warning",
                    header = red(" !!! ")
                )
                to_r_path = tofile

            if from_r_path == to_r_path and os.path.islink(tofile):
                # there is a serious issue here, better removing tofile,
                # happened to someone.

                try:
                    # try to cope...
                    os.remove(tofile)
                except (OSError, IOError,) as err:
                    self._entropy.logger.log(
                        "[Package]",
                        etpConst['logging']['normal_loglevel_id'],
                        "WARNING!!! Failed to cope to oddity of %s " \
                        "file ! [workout_file/2]: %s" % (
                            tofile, err,
                        )
                    )

            # if our file is a dir on the live system
            if os.path.isdir(tofile) and not os.path.islink(tofile):

                # really weird...!
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! %s is a directory when it should " \
                    "be a file !!" % (tofile,)
                )

                txt = "%s: %s" % (
                    _("Fatal: file expected, directory found"),
                    const_convert_to_unicode(tofile),
                )
                self._entropy.output(
                    darkred(txt),
                    importance = 1,
                    level = "error",
                    header = red(" !!! ")
                )
                return 1

            # moving file using the raw format
            try:
                done = movefile(fromfile, tofile, src_basedir = image_dir)
            except (IOError,) as err:
                # try to move forward, sometimes packages might be
                # fucked up and contain broken things
                if err.errno not in (errno.ENOENT, errno.EACCES,):
                    raise

                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! Error during file move" \
                    " to system: %s => %s | IGNORED: %s" % (
                        const_convert_to_unicode(fromfile),
                        const_convert_to_unicode(tofile),
                        err,
                    )
                )
                done = True

            if not done:
                self._entropy.logger.log(
                    "[Package]",
                    etpConst['logging']['normal_loglevel_id'],
                    "WARNING!!! Error during file move" \
                    " to system: %s => %s" % (fromfile, tofile,)
                )
                mytxt = "%s: %s => %s, %s" % (
                    _("QA: file move error"),
                    const_convert_to_unicode(fromfile),
                    const_convert_to_unicode(tofile),
                    _("please report"),
                )
                self._entropy.output(
                    darkred(mytxt),
                    importance = 1,
                    level = "warning",
                    header = red(" !!! ")
                )
                return 4

            item_dir = os.path.realpath(os.path.dirname(tofile))
            item_inst = os.path.join(item_dir, os.path.basename(tofile))
            item_inst = const_convert_to_unicode(item_inst)
            items_installed.add(item_inst)

            if protected and \
                    os.getenv("ENTROPY_CLIENT_ENABLE_OLD_FILEUPDATES"):
                # add to disk cache
                file_updates = self._entropy.PackageFileUpdates()
                file_updates.add(tofile, quiet = True)

            return 0

        # merge data into system
        for currentdir, subdirs, files in os.walk(image_dir):

            # create subdirs
            for subdir in subdirs:
                exit_st = workout_subdir(currentdir, subdir)
                if exit_st != 0:
                    return exit_st

            for item in files:
                move_st = workout_file(currentdir, item)
                if move_st != 0:
                    return move_st

        return 0
