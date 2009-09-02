# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
from __future__ import with_statement
import os
import errno
import stat
import shutil
from entropy.const import etpConst, etpSys, etpCache, const_setup_perms, \
    ETP_LOGPRI_INFO, ETP_LOGLEVEL_NORMAL, ETP_LOGLEVEL_VERBOSE
from entropy.exceptions import PermissionDenied, InvalidData, IncorrectParameter
from entropy.i18n import _
from entropy.output import TextInterface, brown, blue, bold, darkgreen, \
    darkblue, red, purple, darkred, print_info, print_error, print_warning
from entropy.misc import TimeScheduled
from entropy.db import dbapi2, EntropyRepository
from entropy.client.interfaces.client import Client
from entropy.cache import EntropyCacher
import entropy.tools

class Package:

    def __init__(self, EquoInstance):

        if not isinstance(EquoInstance, Client):
            mytxt = _("A valid Client instance or subclass is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        self.Entropy = EquoInstance

        self.Cacher = EntropyCacher()
        self.pkgmeta = {}
        self.__prepared = False
        self.matched_atom = ()
        self.valid_actions = ("source", "fetch", "multi_fetch", "remove",
            "remove_conflict", "install", "config"
        )
        self.action = None
        self.fetch_abort_function = None
        self.xterm_title = ''

    def kill(self):
        self.pkgmeta.clear()

        self.matched_atom = ()
        self.valid_actions = ()
        self.action = None
        self.__prepared = False
        self.fetch_abort_function = None

    def error_on_prepared(self):
        if self.__prepared:
            mytxt = _("Already prepared")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))

    def error_on_not_prepared(self):
        if not self.__prepared:
            mytxt = _("Not yet prepared")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))

    def check_action_validity(self, action):
        if action not in self.valid_actions:
            mytxt = _("Action must be in")
            raise InvalidData("InvalidData: %s %s" % (mytxt,
                self.valid_actions,)
            )

    def match_checksum(self, repository = None, checksum = None,
        download = None, signatures = None):

        self.error_on_not_prepared()

        if repository is None:
            repository = self.pkgmeta['repository']
        if checksum is None:
            checksum = self.pkgmeta['checksum']
        if download is None:
            download = self.pkgmeta['download']
        if signatures is None:
            signatures = self.pkgmeta['signatures']

        def do_signatures_validation(signatures):
            # check signatures, if available
            if isinstance(signatures, dict):
                for hash_type in sorted(signatures):
                    hash_val = signatures[hash_type]
                    # XXX workaround bug on unreleased
                    # entropy versions
                    if hash_val in signatures:
                        continue
                    elif hash_val is None:
                        continue
                    elif not hasattr(entropy.tools, 'compare_%s' % (hash_type,)):
                        continue

                    self.Entropy.updateProgress(
                        "%s: %s" % (blue(_("Checking package hash")),
                            purple(hash_type.upper()),),
                        importance = 0,
                        type = "info",
                        header = red("   ## "),
                        back = True
                    )
                    cmp_func = getattr(entropy.tools,
                        'compare_%s' % (hash_type,))
                    mydownload = os.path.join(etpConst['entropyworkdir'],
                        download)
                    valid = cmp_func(mydownload, hash_val)
                    if not valid:
                        self.Entropy.updateProgress(
                            "%s: %s %s" % (
                                darkred(_("Package hash")),
                                purple(hash_type.upper()),
                                darkred(_("does not match the recorded one")),
                            ),
                            importance = 0,
                            type = "warning",
                            header = darkred("   ## ")
                        )
                        return 1
                    self.Entropy.updateProgress(
                        "%s %s" % (
                            purple(hash_type.upper()),
                            darkgreen(_("matches")),
                        ),
                        importance = 0,
                        type = "info",
                        header = "      : "
                    )
            return 0

        dlcount = 0
        match = False
        while dlcount <= 5:

            self.Entropy.updateProgress(
                blue(_("Checking package checksum...")),
                importance = 0,
                type = "info",
                header = red("   ## "),
                back = True
            )

            dlcheck = self.Entropy.check_needed_package_download(download,
                checksum = checksum)
            if dlcheck == 0:
                basef = os.path.basename(download)
                self.Entropy.updateProgress(
                    "%s: %s" % (
                        blue(_("Package checksum matches")),
                        darkgreen(basef),
                    ),
                    importance = 0,
                    type = "info",
                    header = red("   ## ")
                )

                dlcheck = do_signatures_validation(signatures)
                if dlcheck == 0:
                    self.pkgmeta['verified'] = True
                    match = True
                    break # file downloaded successfully

            if dlcheck != 0:
                dlcount += 1
                mytxt = _("Checksum does not match. Download attempt #%s") % (
                    dlcount,
                )
                self.Entropy.updateProgress(
                    darkred(mytxt),
                    importance = 0,
                    type = "warning",
                    header = darkred("   ## ")
                )
                myrelative_uri = \
                    self.Entropy.get_branch_from_download_relative_uri(download)
                fetch = self.Entropy.fetch_file_on_mirrors(
                    repository,
                    myrelative_uri,
                    download,
                    checksum,
                    fetch_abort_function = self.fetch_abort_function
                )
                if fetch != 0:
                    self.Entropy.updateProgress(
                        blue(_("Cannot properly fetch package! Quitting.")),
                        importance = 0,
                        type = "error",
                        header = darkred("   ## ")
                    )
                    return fetch

                # package is fetched, let's loop one more time
                # to make sure to run all the checksum checks
                continue

        if not match:
            mytxt = _("Cannot fetch package or checksum does not match")
            mytxt2 = _("Try to download latest repositories")
            for txt in (mytxt, mytxt2,):
                self.Entropy.updateProgress(
                    "%s." % (blue(txt),),
                    importance = 0,
                    type = "info",
                    header = red("   ## ")
                )
            return 1

        return 0

    def multi_match_checksum(self):
        rc = 0
        for repository, branch, download, digest, signatures in \
            self.pkgmeta['multi_checksum_list']:

            rc = self.match_checksum(repository, digest, download, signatures)
            if rc != 0:
                break

        return rc

    def __unpack_package(self):

        if not self.pkgmeta['merge_from']:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Unpacking package: %s" % (self.pkgmeta['atom'],)
            )
        else:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Merging package: %s" % (self.pkgmeta['atom'],)
            )

        unpack_dir = self.pkgmeta['unpackdir']
        unpack_dir_raw = self.pkgmeta['unpackdir'].encode('raw_unicode_escape')

        if os.path.isdir(unpack_dir):
            shutil.rmtree(unpack_dir_raw)
        elif os.path.isfile(unpack_dir):
            os.remove(unpack_dir_raw)
        os.makedirs(self.pkgmeta['imagedir'])

        if not os.path.isfile(self.pkgmeta['pkgpath']) and \
            not self.pkgmeta['merge_from']:

            if os.path.isdir(self.pkgmeta['pkgpath']):
                shutil.rmtree(self.pkgmeta['pkgpath'])
            if os.path.islink(self.pkgmeta['pkgpath']):
                os.remove(self.pkgmeta['pkgpath'])
            self.pkgmeta['verified'] = False
            rc = self.fetch_step()
            if rc != 0:
                return rc

        if not self.pkgmeta['merge_from']:

            # extract entropy database from package file
            # in order to avoid having to read content data
            # from the repository database, which, in future
            # is allowed to not provide such info.
            pkg_dbdir = os.path.dirname(self.pkgmeta['pkgdbpath'])
            if not os.path.isdir(pkg_dbdir):
                os.makedirs(pkg_dbdir, 0755)

            # extract edb
            entropy.tools.extract_edb(self.pkgmeta['pkgpath'],
                self.pkgmeta['pkgdbpath'])

            unpack_tries = 3
            while 1:
                unpack_tries -= 1
                try:
                    rc = entropy.tools.spawn_function(
                        entropy.tools.uncompress_tar_bz2,
                        self.pkgmeta['pkgpath'],
                        self.pkgmeta['imagedir'],
                        catchEmpty = True
                    )
                except EOFError:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO, ETP_LOGLEVEL_NORMAL, 
                        "EOFError on " + self.pkgmeta['pkgpath']
                    )
                    rc = 1
                except:
                    # this will make devs to actually catch the
                    # right exception and prepare a fix
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "Raising Unicode/Pickling Error for " + \
                            self.pkgmeta['pkgpath']
                    )
                    rc = entropy.tools.uncompress_tar_bz2(
                        self.pkgmeta['pkgpath'],
                        self.pkgmeta['imagedir'],
                        catchEmpty = True
                    )
                if rc == 0:
                    break

                if unpack_tries <= 0:
                    return rc
                # otherwise, try to download it again
                self.pkgmeta['verified'] = False
                f_rc = self.fetch_step()
                if f_rc != 0:
                    return f_rc

        else:

            pid = os.fork()
            if pid > 0:
                os.waitpid(pid, 0)
            else:
                self.__fill_image_dir(self.pkgmeta['merge_from'],
                    self.pkgmeta['imagedir'])
                os._exit(0)

        # FIXME: add new entropy.spm plugin method

        # unpack xpak ?
        if os.path.isdir(self.pkgmeta['xpakpath']):
            shutil.rmtree(self.pkgmeta['xpakpath'], True)

        # create data dir where we'll unpack the xpak
        xpak_dir = self.pkgmeta['xpakpath'] + os.path.sep + \
            etpConst['entropyxpakdatarelativepath']

        os.makedirs(xpak_dir, 0755)

        xpak_path = self.pkgmeta['xpakpath'] + os.path.sep + \
            etpConst['entropyxpakfilename']

        if not self.pkgmeta['merge_from']:

            if self.pkgmeta['smartpackage']:

                # we need to get the .xpak from database
                xdbconn = self.Entropy.open_repository(
                    self.pkgmeta['repository'])
                xpakdata = xdbconn.retrieveXpakMetadata(
                    self.pkgmeta['idpackage'])
                if xpakdata:
                    # save into a file
                    f = open(xpak_path, "wb")
                    f.write(xpakdata)
                    f.flush()
                    f.close()
                    self.pkgmeta['xpakstatus'] = entropy.tools.unpack_xpak(
                        xpak_path,
                        xpak_dir
                    )
                else:
                    self.pkgmeta['xpakstatus'] = None
                del xpakdata

            else:
                self.pkgmeta['xpakstatus'] = entropy.tools.extract_xpak(
                    self.pkgmeta['pkgpath'],
                    xpak_dir
                )

        else: # merge_from

            tolink_dir = xpak_dir
            if os.path.isdir(tolink_dir):
                shutil.rmtree(tolink_dir, True)
            # now link
            os.symlink(self.pkgmeta['xpakdir'], tolink_dir)

        # create fake portage ${D} linking it to imagedir
        portage_cpv = self.pkgmeta['category'] + "/" + \
            self.pkgmeta['name'] + "-" + self.pkgmeta['version']

        portage_db_fakedir = os.path.join(
            self.pkgmeta['unpackdir'],
            "portage/" + portage_cpv
        )

        os.makedirs(portage_db_fakedir, 0755)
        # now link it to self.pkgmeta['imagedir']
        os.symlink(self.pkgmeta['imagedir'],
            os.path.join(portage_db_fakedir, "image"))

        return 0

    def __configure_package(self):

        try:
            Spm = self.Entropy.Spm()
        except Exception, err:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Source Package Manager not available: %s | %s" % (
                    type(Exception), err,
                )
            )
            return 1

        self.Entropy.updateProgress(
            "SPM: %s" % (brown(_("configuration phase")),),
            importance = 0,
            header = red("   ## ")
        )
        return Spm.configure_installed_package(self.pkgmeta)


    def __remove_package(self):

        self.__clear_cache()

        self.Entropy.clientLog.log(ETP_LOGPRI_INFO, ETP_LOGLEVEL_NORMAL,
            "Removing package: %s" % (self.pkgmeta['removeatom'],))

        mytxt = "%s: %s" % (
            blue(_("Removing from Entropy")),
            red(self.pkgmeta['removeatom']),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        automerge_metadata = \
            self.Entropy.clientDbconn.retrieveAutomergefiles(
                self.pkgmeta['removeidpackage'], get_dict = True
            )
        self.remove_installed_package(self.pkgmeta['removeidpackage'])

        spm_rc = self.spm_remove_package()
        if spm_rc != 0:
            return spm_rc

        self.remove_content_from_system(self.pkgmeta['removeidpackage'],
            automerge_metadata)

        return 0

    def remove_installed_package(self, idpackage):
        """
        Remove installed package from Entropy installed packages repository.

        @param idpackage: Entropy Repository package identifier
        @type idpackage: int
        """
        self.Entropy.clientDbconn.removePackage(idpackage, do_commit = False,
            do_cleanup = False)

    def remove_content_from_system(self, idpackage, automerge_metadata = None):
        """
        Remove installed package content (files/directories) from live system.

        @param idpackage: Entropy Repository package identifier
        @type idpackage: int
        @keyword automerge_metadata: Entropy "automerge metadata"
        @type automerge_metadata: dict
        """
        if automerge_metadata is None:
            automerge_metadata = {}

        sys_root = etpConst['systemroot']
        # load CONFIG_PROTECT and CONFIG_PROTECT_MASK
        sys_settings = self.Entropy.SystemSettings
        protect = self.Entropy.get_installed_package_config_protect(idpackage)
        mask = self.Entropy.get_installed_package_config_protect(idpackage,
            mask = True)

        sys_set_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        col_protect = sys_settings[sys_set_plg_id]['misc']['collisionprotect']

        # remove files from system
        directories = set()
        directories_cache = set()
        not_removed_due_to_collisions = set()
        colliding_path_messages = set()

        remove_content = sorted(self.pkgmeta['removecontent'], reverse = True)
        for item in remove_content:

            if not item:
                continue # empty element??

            sys_root_item = sys_root + item

            # collision check
            if col_protect > 0:

                if self.Entropy.clientDbconn.isFileAvailable(item) \
                    and os.path.isfile(sys_root_item):

                    # in this way we filter out directories
                    colliding_path_messages.add(sys_root_item)
                    not_removed_due_to_collisions.add(item)
                    continue

            protected = False
            in_mask = False

            if (not self.pkgmeta['removeconfig']) and \
                (not self.pkgmeta['diffremoval']):

                protected_item_test = sys_root_item
                if isinstance(protected_item_test, unicode):
                    protected_item_test = protected_item_test.encode('utf-8')

                in_mask, protected, x, do_continue = \
                    self._handle_config_protect(
                        protect, mask, None, protected_item_test,
                        do_allocation_check = False, do_quiet = True
                    )

                if do_continue:
                    protected = True

            # when files have not been modified by the user
            # and they are inside a config protect directory
            # we could even remove them directly
            if in_mask:

                oldprot_md5 = automerge_metadata.get(item)
                if oldprot_md5 and os.path.exists(protected_item_test) and \
                    os.access(protected_item_test, os.R_OK):

                    in_system_md5 = entropy.tools.md5sum(
                        protected_item_test)

                    if oldprot_md5 == in_system_md5:
                        prot_msg = _("Removing config file, never modified")
                        mytxt = "%s: %s" % (
                            darkgreen(prot_msg),
                            blue(item),
                        )
                        self.Entropy.updateProgress(
                            mytxt,
                            importance = 1,
                            type = "info",
                            header = red("   ## ")
                        )
                        protected = False
                        do_continue = False

            # Is file or directory a protected item?
            if protected:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_VERBOSE,
                    "[remove] Protecting config file: %s" % (sys_root_item,)
                )
                mytxt = "[%s] %s: %s" % (
                    red(_("remove")),
                    brown(_("Protecting config file")),
                    sys_root_item,
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )
                continue


            try:
                os.lstat(sys_root_item)

            except OSError:
                continue # skip file, does not exist

            except UnicodeEncodeError:
                msg = _("This package contains a badly encoded file !!!")
                mytxt = brown(msg)
                self.Entropy.updateProgress(
                    red("QA: ")+mytxt,
                    importance = 1,
                    type = "warning",
                    header = darkred("   ## ")
                )
                continue # file has a really bad encoding

            if os.path.isdir(sys_root_item) and \
                os.path.islink(sys_root_item):
                # S_ISDIR returns False for directory symlinks,
                # so using os.path.isdir valid directory symlink
                if sys_root_item not in directories_cache:
                    directories.add((sys_root_item, "link"))
                    directories_cache.add(sys_root_item)
                continue

            if os.path.isdir(sys_root_item):
                # plain directory
                if sys_root_item not in directories_cache:
                    directories.add((sys_root_item, "dir"))
                    directories_cache.add(sys_root_item)
                continue

            # files, symlinks or not
            # just a file or symlink or broken
            # directory symlink (remove now)

            try:
                os.remove(sys_root_item)
            except OSError, err:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[remove] Unable to remove %s, error: %s" % (
                        sys_root_item, err,)
                )
                continue

            # add its parent directory
            dirobj = os.path.dirname(sys_root_item)
            if dirobj not in directories_cache:
                if os.path.isdir(dirobj) and os.path.islink(dirobj):
                    directories.add((dirobj, "link"))
                elif os.path.isdir(dirobj):
                    directories.add((dirobj, "dir"))

                directories_cache.add(dirobj)


        if colliding_path_messages:
            self.Entropy.updateProgress(
                "%s:" % (_("Collision found during removal of"),),
                importance = 1,
                type = "warning",
                header = red("   ## ")
            )

        for path in sorted(colliding_path_messages):
            self.Entropy.updateProgress(
                purple(path),
                importance = 0,
                type = "warning",
                header = red("   ## ")
            )
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO, ETP_LOGLEVEL_NORMAL,
                "Collision found during removal of %s - cannot overwrite" % (
                    path,)
            )

        # removing files not removed from removecontent.
        # it happened that boot services not removed due to
        # collisions got removed from their belonging runlevels
        # by postremove step.
        # since this is a set, it is a mapped type, so every
        # other instance around will feature this update
        self.pkgmeta['removecontent'] -= not_removed_due_to_collisions

        # now handle directories
        directories = sorted(directories, reverse = True)
        while 1:
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

    def _cleanup_package(self, unpack_dir):
        # remove unpack dir
        shutil.rmtree(unpack_dir, True)
        try: 
            os.rmdir(unpack_dir)
        except OSError:
            pass
        return 0

    def __clear_cache(self):
        self.Entropy.clear_dump_cache(etpCache['advisories'])
        self.Entropy.clear_dump_cache(etpCache['filter_satisfied_deps'])
        self.Entropy.clear_dump_cache(etpCache['depends_tree'])
        self.Entropy.clear_dump_cache(etpCache['check_package_update'])
        self.Entropy.clear_dump_cache(etpCache['dep_tree'])
        self.Entropy.clear_dump_cache(etpCache['dbMatch'] + \
            etpConst['clientdbid']+"/")
        self.Entropy.clear_dump_cache(etpCache['dbSearch'] + \
            etpConst['clientdbid']+"/")

        # clear caches, the bad way
        self.Entropy.clear_dump_cache(etpCache['world_available'])
        self.Entropy.clear_dump_cache(etpCache['world_update'])
        self.Entropy.clear_dump_cache(etpCache['critical_update'])

    def __install_package(self):

        # clear on-disk cache
        self.__clear_cache()

        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "Installing package: %s" % (self.pkgmeta['atom'],)
        )

        already_protected_config_files = {}
        if self.pkgmeta['removeidpackage'] != -1:
            already_protected_config_files = \
                self.Entropy.clientDbconn.retrieveAutomergefiles(
                    self.pkgmeta['removeidpackage'], get_dict = True
                )

        # copy files over - install
        # use fork? (in this case all the changed structures
        # need to be pushed back)
        rc = self.move_image_to_system(already_protected_config_files)
        if rc != 0:
            return rc

        # inject into database
        mytxt = "%s: %s" % (
            blue(_("Updating database")),
            red(self.pkgmeta['atom']),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        idpackage = self.add_installed_package()

        # remove old files and spm stuff
        if self.pkgmeta['removeidpackage'] != -1:

            # doing a diff removal
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Remove old package: %s" % (self.pkgmeta['removeatom'],)
            )

            self.Entropy.updateProgress(
                blue(_("Cleaning previously installed information...")),
                importance = 1,
                type = "info",
                header = red("   ## ")
            )

            spm_rc = self.spm_remove_package()
            if spm_rc != 0:
                return spm_rc

            self.remove_content_from_system(self.pkgmeta['removeidpackage'],
                automerge_metadata = already_protected_config_files)

        return self.spm_install_package(idpackage)

    def spm_install_package(self, idpackage):
        """
        Call Source Package Manager interface and tell it to register our
        newly installed package.

        @param idpackage: Entropy repository package identifier
        @type idpackage: int
        @return: execution status
        @rtype: int
        """
        try:
            Spm = self.Entropy.Spm()
        except Exception, err:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Source Package Manager not available: %s | %s" % (
                    type(Exception), err,
                )
            )
            return -1

        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "Installing new SPM entry: %s" % (self.pkgmeta['atom'],)
        )

        spm_uid = Spm.add_installed_package(self.pkgmeta)
        if spm_uid != -1:
            self.Entropy.clientDbconn.insertSpmUid(idpackage, spm_uid)

        return 0

    def spm_remove_package(self):
        """
        Call Source Package Manager interface and tell it to remove our
        just removed package.

        @return: execution status
        @rtype: int
        """
        try:
            Spm = self.Entropy.Spm()
        except Exception, err:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Source Package Manager not available: %s | %s" % (
                    type(Exception), err,
                )
            )
            return -1

        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "Removing from SPM: %s" % (self.pkgmeta['removeatom'],)
        )

        return Spm.remove_installed_package(self.pkgmeta)


    def add_installed_package(self):
        """
        For internal use only.
        Copy package from repository to installed packages one.
        """

        # fetch info
        smart_pkg = self.pkgmeta['smartpackage']
        dbconn = self.Entropy.open_repository(self.pkgmeta['repository'])

        if smart_pkg or self.pkgmeta['merge_from']:

            data = dbconn.getPackageData(self.pkgmeta['idpackage'],
                content_insert_formatted = True)

            if self.pkgmeta['removeidpackage'] != -1:
                self.pkgmeta['removecontent'].update(
                    self.Entropy.clientDbconn.contentDiff(
                        self.pkgmeta['removeidpackage'],
                        dbconn,
                        self.pkgmeta['idpackage']
                    )
                )

        else:

            # normal repositories
            data = dbconn.getPackageData(self.pkgmeta['idpackage'],
                get_content = False)
            pkg_dbconn = self.Entropy.open_generic_database(
                self.pkgmeta['pkgdbpath'])
            # it is safe to consider that package dbs coming from repos
            # contain only one entry
            pkg_idpackage = sorted(pkg_dbconn.listAllIdpackages())[0]
            content = pkg_dbconn.retrieveContent(
                pkg_idpackage, extended = True,
                formatted = True, insert_formatted = True
            )
            real_idpk = self.pkgmeta['idpackage']
            content = [(real_idpk, x, y,) for orig_idpk, x, y in content]
            data['content'] = content

            if self.pkgmeta['removeidpackage'] != -1:
                self.pkgmeta['removecontent'].update(
                    self.Entropy.clientDbconn.contentDiff(
                        self.pkgmeta['removeidpackage'],
                        pkg_dbconn,
                        pkg_idpackage
                    )
                )

            pkg_dbconn.closeDB()

        # this is needed to make postinstall trigger to work properly
        trigger_content = set((x[1] for x in data['content']))
        self.pkgmeta['triggers']['install']['content'] = trigger_content

        # open client db
        # always set data['injected'] to False
        # installed packages database SHOULD never have more
        # than one package for scope (key+slot)
        data['injected'] = False
        # spm counter will be set in self._install_package_into_spm_database()
        data['counter'] = -1
        # branch must be always set properly, it could happen it's not
        # when installing packages through their .tbz2s
        data['branch'] = self.Entropy.SystemSettings['repositories']['branch']
        # there is no need to store needed paths into db
        if data.get('needed_paths'):
            del data['needed_paths']

        idpackage, rev, x = self.Entropy.clientDbconn.handlePackage(
            data, forcedRevision = data['revision'], formattedContent = True)

        # update datecreation
        ctime = entropy.tools.get_current_unix_time()
        self.Entropy.clientDbconn.setCreationDate(idpackage, str(ctime))

        # add idpk to the installedtable
        self.Entropy.clientDbconn.dropInstalledPackageFromStore(idpackage)
        self.Entropy.clientDbconn.storeInstalledPackage(idpackage,
            self.pkgmeta['repository'], self.pkgmeta['install_source'])

        automerge_data = self.pkgmeta.get('configprotect_data')
        if automerge_data:
            self.Entropy.clientDbconn.insertAutomergefiles(idpackage,
                automerge_data)

        # clear depends table, this will make clientdb dependstable to be
        # regenerated during the next request (retrieveReverseDependencies)
        self.Entropy.clientDbconn.taintReverseDependenciesMetadata()
        return idpackage

    def __fill_image_dir(self, mergeFrom, image_dir):

        dbconn = self.Entropy.open_repository(self.pkgmeta['repository'])
        # this is triggered by merge_from pkgmeta metadata
        # even if repositories are allowed to not have content
        # metadata, in this particular case, it is mandatory
        package_content = dbconn.retrieveContent(
            self.pkgmeta['idpackage'], extended = True, formatted = True)
        contents = sorted(package_content)

        # collect files
        for path in contents:
            # convert back to filesystem str
            encoded_path = path
            path = os.path.join(mergeFrom, encoded_path[1:])
            topath = os.path.join(image_dir, encoded_path[1:])
            path = path.encode('raw_unicode_escape')
            topath = topath.encode('raw_unicode_escape')

            try:
                exist = os.lstat(path)
            except OSError:
                continue # skip file
            ftype = package_content[encoded_path]

            if 'dir' == ftype and \
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
                if not os.path.isdir(topath):
                    os.makedirs(topath)
                    copystat = True
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


    def move_image_to_system(self, already_protected_config_files):

        # load CONFIG_PROTECT and its mask
        protect = self.Entropy.get_package_match_config_protect(
            self.matched_atom)
        mask = self.Entropy.get_package_match_config_protect(
            self.matched_atom, mask = True)
        sys_root = etpConst['systemroot']
        sys_set_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        misc_data = self.Entropy.SystemSettings[sys_set_plg_id]['misc']
        col_protect = misc_data['collisionprotect']
        items_installed = set()

        # setup image_dir properly
        image_dir = self.pkgmeta['imagedir']
        encoded_image_dir = image_dir.encode('utf-8')
        movefile = entropy.tools.movefile

        def workout_subdir(currentdir, subdir):

            imagepath_dir = "%s/%s" % (currentdir, subdir,)
            rootdir = "%s%s" % (sys_root, imagepath_dir[len(image_dir):],)

            # handle broken symlinks
            if os.path.islink(rootdir) and not os.path.exists(rootdir):
                # broken symlink
                os.remove(rootdir)

            # if our directory is a file on the live system
            elif os.path.isfile(rootdir): # really weird...!

                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "WARNING!!! %s is a file when it should be " \
                    "a directory !! Removing in 20 seconds..." % (rootdir,)
                )
                mytxt = darkred(_("%s is a file when should be a " \
                "directory !! Removing in 20 seconds...") % (rootdir,))

                self.Entropy.updateProgress(
                    red("QA: ")+mytxt,
                    importance = 1,
                    type = "warning",
                    header = red(" !!! ")
                )
                entropy.tools.ebeep(20)
                os.remove(rootdir)

            # if our directory is a symlink instead, then copy the symlink
            if os.path.islink(imagepath_dir):

                # if our live system features a directory instead of
                # a symlink, we should consider removing the directory
                if not os.path.islink(rootdir) and os.path.isdir(rootdir):
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "WARNING!!! %s is a directory when it should be " \
                        "a symlink !! Removing in 20 seconds..." % (
                            rootdir,)
                    )
                    mytxt = "%s: %s" % (
                        _("directory expected, symlink found"),
                        rootdir,
                    )
                    mytxt2 = _("Removing in 20 seconds !!")
                    for txt in (mytxt, mytxt2,):
                        self.Entropy.updateProgress(
                            darkred("QA: ") + darkred(txt),
                            importance = 1,
                            type = "warning",
                            header = red(" !!! ")
                        )

                    entropy.tools.ebeep(20)
                    # fucking kill it in any case!
                    # rootdir must die! die die die die!
                    # /me brings chainsaw
                    try:
                        shutil.rmtree(rootdir, True)
                    except (shutil.Error, OSError,), err:
                        self.Entropy.clientLog.log(
                            ETP_LOGPRI_INFO,
                            ETP_LOGLEVEL_NORMAL,
                            "WARNING!!! Failed to rm %s " \
                            "directory ! [workout_subdir/1]: %s" % (
                                rootdir, err,
                            )
                        )

                tolink = os.readlink(imagepath_dir)
                live_tolink = None
                if os.path.islink(rootdir):
                    live_tolink = os.readlink(rootdir)

                if tolink != live_tolink:
                    if os.path.lexists(rootdir):
                        # at this point, it must be a file
                        os.remove(rootdir)
                    os.symlink(tolink, rootdir)

            elif not os.path.isdir(rootdir) and not \
                os.access(rootdir, os.R_OK):
                # directory not found, we need to create it

                try:
                    # really force a simple mkdir first of all
                    os.mkdir(rootdir)
                except OSError:
                    os.makedirs(rootdir)


            if not os.path.islink(rootdir) and os.access(rootdir, os.W_OK):

                # symlink doesn't need permissions, also
                # until os.walk ends they might be broken
                # XXX also, added os.access() check because
                # there might be directories/files unwritable
                # what to do otherwise?
                user = os.stat(imagepath_dir)[stat.ST_UID]
                group = os.stat(imagepath_dir)[stat.ST_GID]
                os.chown(rootdir, user, group)
                shutil.copystat(imagepath_dir, rootdir)

            item_dir, item_base = os.path.split(rootdir)
            item_dir = os.path.realpath(item_dir)
            item_inst = os.path.join(item_dir, item_base)
            items_installed.add(item_inst)


        def workout_file(currentdir, item):

            fromfile = "%s/%s" % (currentdir, item,)
            tofile = "%s%s" % (sys_root, fromfile[len(image_dir):],)

            if col_protect > 1:
                todbfile = fromfile[len(image_dir):]
                myrc = self._handle_install_collision_protect(tofile,
                    todbfile)
                if not myrc:
                    return

            prot_old_tofile = tofile[len(sys_root):]
            pre_tofile = tofile[:]
            in_mask, protected, tofile, do_return = \
                self._handle_config_protect(protect, mask, fromfile, tofile)

            # collect new config automerge data
            if in_mask and os.path.exists(fromfile):
                try:
                    prot_md5 = entropy.tools.md5sum(fromfile)
                    self.pkgmeta['configprotect_data'].append(
                        (prot_old_tofile, prot_md5,))
                except (IOError,), err:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "WARNING!!! Failed to get md5 of %s " \
                        "file ! [workout_file/1]: %s" % (
                            fromfile, err,
                        )
                    )

            # check if it's really necessary to protect file
            if protected:

                # second task
                oldprot_md5 = already_protected_config_files.get(
                    prot_old_tofile)

                if oldprot_md5 and os.path.exists(pre_tofile) and \
                    os.access(pre_tofile, os.R_OK):

                    try:
                        in_system_md5 = entropy.tools.md5sum(pre_tofile)
                    except (IOError,):
                        # which is a clearly invalid value
                        in_system_md5 = "0000"

                    if oldprot_md5 == in_system_md5:
                        # we can merge it, files, even if
                        # contains changes have not been modified
                        # by the user
                        msg = _("Automerging config file, never modified")
                        mytxt = "%s: %s" % (
                            darkgreen(msg),
                            blue(pre_tofile),
                        )
                        self.Entropy.updateProgress(
                            mytxt,
                            importance = 1,
                            type = "info",
                            header = red("   ## ")
                        )
                        protected = False
                        do_return = False
                        tofile = pre_tofile

            if do_return:
                return

            if os.path.realpath(fromfile) == os.path.realpath(tofile) and \
                os.path.islink(tofile):
                # there is a serious issue here, better removing tofile,
                # happened to someone.

                try:
                    # try to cope...
                    os.remove(tofile)
                except (OSError, IOError,), err:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "WARNING!!! Failed to cope to oddity of %s " \
                        "file ! [workout_file/2]: %s" % (
                            tofile, err,
                        )
                    )

            # if our file is a dir on the live system
            if os.path.isdir(tofile) and not os.path.islink(tofile):

                # really weird...!
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "WARNING!!! %s is a directory when it should " \
                    "be a file !! Removing in 20 seconds..." % (tofile,)
                )

                mytxt = "%s: %s" % (
                    _("file expected, directory found"),
                    tofile,
                )
                mytxt2 = _("Removing in 20 seconds !!")
                for txt in (mytxt, mytxt2,):
                    self.Entropy.updateProgress(
                        darkred("QA: ") + darkred(txt),
                        importance = 1,
                        type = "warning",
                        header = red(" !!! ")
                    )
                entropy.tools.ebeep(20)

                try:
                    shutil.rmtree(tofile, True)
                except (shutil.Error, IOError,), err:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "WARNING!!! Failed to cope to oddity of %s " \
                        "file ! [workout_file/3]: %s" % (
                            tofile, err,
                        )
                    )

            # moving file using the raw format
            try:
                done = movefile(fromfile, tofile,
                    src_basedir = encoded_image_dir)
            except (IOError,), err:
                # try to move forward, sometimes packages might be
                # fucked up and contain broken things
                if err.errno not in (errno.ENOENT, errno.EACCES,):
                    raise

                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "WARNING!!! Error during file move" \
                    " to system: %s => %s | IGNORED: %s" % (
                        fromfile,
                        tofile,
                        err,
                    )
                )
                done = True

            if not done:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "WARNING!!! Error during file move" \
                    " to system: %s => %s" % (fromfile, tofile,)
                )
                mytxt = "%s: %s => %s, %s" % (
                    _("File move error"),
                    fromfile,
                    tofile,
                    _("please report"),
                )
                self.Entropy.updateProgress(
                    red("QA: ")+darkred(mytxt),
                    importance = 1,
                    type = "warning",
                    header = red(" !!! ")
                )
                return 4

            item_dir = os.path.realpath(os.path.dirname(tofile))
            item_inst = os.path.join(item_dir, os.path.basename(tofile))
            items_installed.add(item_inst)

            if protected:
                # add to disk cache
                self.Entropy.FileUpdates.add_to_cache(tofile, quiet = True)


        # merge data into system
        for currentdir, subdirs, files in os.walk(encoded_image_dir):

            # create subdirs
            for subdir in subdirs:
                workout_subdir(currentdir, subdir)

            for item in files:
                workout_file(currentdir, item)

        # this is useful to avoid the removal of installed
        # files by __remove_package just because
        # there's a difference in the directory path, perhaps,
        # which is not handled correctly by
        # EntropyRepository.contentDiff for obvious reasons
        # (think about stuff in /usr/lib and /usr/lib64,
        # where the latter is just a symlink to the former)
        if self.pkgmeta.get('removecontent'):
            my_remove_content = set()
            for mypath in self.pkgmeta['removecontent']:

                if not mypath:
                    continue # empty?

                item_dir = os.path.dirname("%s%s" % (sys_root, mypath,))
                item = os.path.join(os.path.realpath(item_dir),
                    os.path.basename(mypath))

                if item in items_installed:
                    my_remove_content.add(item)

            self.pkgmeta['removecontent'] -= my_remove_content

        return 0

    def _handle_config_protect(self, protect, mask, fromfile, tofile,
        do_allocation_check = True, do_quiet = False):
        """
        Handle configuration file protection. This method contains the logic
        for determining if a file should be protected from overwrite.
        """

        protected = False
        tofile_before_protect = tofile
        do_continue = False
        in_mask = False
        encoded_protect = [x.encode('raw_unicode_escape') for x in protect]

        if tofile in encoded_protect:
            protected = True
            in_mask = True

        elif os.path.dirname(tofile) in encoded_protect:
            protected = True
            in_mask = True

        else:
            tofile_testdir = os.path.dirname(tofile)
            old_tofile_testdir = None
            while tofile_testdir != old_tofile_testdir:
                if tofile_testdir in encoded_protect:
                    protected = True
                    in_mask = True
                    break
                old_tofile_testdir = tofile_testdir
                tofile_testdir = os.path.dirname(tofile_testdir)

        if protected: # check if perhaps, file is masked, so unprotected
            newmask = [x.encode('raw_unicode_escape') for x in mask]

            if tofile in newmask:
                protected = False
                in_mask = False

            elif os.path.dirname(tofile) in newmask:
                protected = False
                in_mask = False

            else:
                tofile_testdir = os.path.dirname(tofile)
                old_tofile_testdir = None
                while tofile_testdir != old_tofile_testdir:
                    if tofile_testdir in newmask:
                        protected = False
                        in_mask = False
                        break
                    old_tofile_testdir = tofile_testdir
                    tofile_testdir = os.path.dirname(tofile_testdir)

        if not os.path.lexists(tofile):
            protected = False # file doesn't exist

        # check if it's a text file
        if protected and os.access(tofile, os.F_OK | os.R_OK):
            protected = entropy.tools.istextfile(tofile)
            in_mask = protected
        else:
            protected = False # it's not a file

        if not protected:
            return in_mask, protected, tofile, do_continue

        ##                  ##
        # file is protected  #
        ##__________________##

        sys_set_plg_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        client_settings = self.Entropy.SystemSettings[sys_set_plg_id]
        misc_settings = client_settings['misc']

        # check if protection is disabled for this element
        if tofile in misc_settings['configprotectskip']:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Skipping config file installation/removal, " \
                "as stated in client.conf: %s" % (tofile,)
            )
            if not do_quiet:
                mytxt = "%s: %s" % (
                    _("Skipping file installation/removal"),
                    tofile,
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = darkred("   ## ")
                )
            do_continue = True
            return in_mask, protected, tofile, do_continue

        ##                      ##
        # file is protected (2)  #
        ##______________________##

        prot_status = True
        if do_allocation_check:
            tofile, prot_status = entropy.tools.allocate_masked_file(
                tofile, fromfile)

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
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Protecting config file: %s" % (oldtofile,)
            )
            mytxt = red("%s: %s") % (_("Protecting config file"), oldtofile,)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = darkred("   ## ")
            )

        return in_mask, protected, tofile, do_continue


    def _handle_install_collision_protect(self, tofile, todbfile):

        avail = self.Entropy.clientDbconn.isFileAvailable(todbfile,
            get_id = True)

        if (self.pkgmeta['removeidpackage'] not in avail) and avail:
            mytxt = darkred(_("Collision found during install for"))
            mytxt += " %s - %s" % (
                blue(tofile),
                darkred(_("cannot overwrite")),
            )
            self.Entropy.updateProgress(
                red("QA: ")+mytxt,
                importance = 1,
                type = "warning",
                header = darkred("   ## ")
            )
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "WARNING!!! Collision found during install " \
                "for %s - cannot overwrite" % (tofile,)
            )
            return False

        return True

    def sources_fetch_step(self):
        self.error_on_not_prepared()

        down_data = self.pkgmeta['download']
        down_keys = down_data.keys()
        d_cache = set()
        rc = 0
        key_cache = [os.path.basename(x) for x in down_keys]

        for key in sorted(down_keys):

            key_name = os.path.basename(key)
            if key_name in d_cache: continue
            # first fine wins

            for url in down_data[key]:

                file_name = os.path.basename(url)
                if self.pkgmeta.get('fetch_path'):
                    dest_file = os.path.join(self.pkgmeta['fetch_path'],
                        file_name)
                else:
                    dest_file = os.path.join(self.pkgmeta['unpackdir'],
                        file_name)

                rc = self._fetch_source(url, dest_file)
                if rc == 0:
                    d_cache.add(key_name)
                    break

            key_cache.remove(key_name)
            if rc != 0 and key_name not in key_cache:
                break

            rc = 0

        return rc

    def _fetch_source(self, url, dest_file):
        rc = 1
        try:

            mytxt = "%s: %s" % (blue(_("Downloading")), brown(url),)
            # now fetch the new one
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red("   ## ")
            )

            rc, data_transfer, resumed = self.Entropy.fetch_file(
                url,
                None,
                None,
                False,
                fetch_file_abort_function = self.fetch_abort_function,
                filepath = dest_file
            )
            if rc == 0:
                mytxt = blue("%s: ") % (_("Successfully downloaded from"),)
                mytxt += red(entropy.tools.spliturl(url)[1])
                human_bytes = entropy.tools.bytes_into_human(data_transfer)
                mytxt += " %s %s/%s" % (_("at"), human_bytes, _("second"),)
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = red("   ## ")
                )
                self.Entropy.updateProgress(
                    "%s: %s" % (blue(_("Local path")), brown(dest_file),),
                    importance = 1,
                    type = "info",
                    header = red("      # ")
                )
            else:
                error_message = blue("%s: %s") % (
                    _("Error downloading from"),
                    red(entropy.tools.spliturl(url)[1]),
                )
                # something bad happened
                if rc == -1:
                    error_message += " - %s." % (
                        _("file not available on this mirror"),
                    )
                elif rc == -3:
                    error_message += " - not found."
                elif rc == -100:
                    error_message += " - %s." % (_("discarded download"),)
                else:
                    error_message += " - %s: %s" % (_("unknown reason"), rc,)
                self.Entropy.updateProgress(
                    error_message,
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )

        except KeyboardInterrupt:
            pass

        return rc

    def fetch_step(self):
        self.error_on_not_prepared()

        mytxt = "%s: %s" % (blue(_("Downloading archive")),
            red(os.path.basename(self.pkgmeta['download'])),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )

        rc = 0
        if not self.pkgmeta['verified']:

            branch = self.Entropy.get_branch_from_download_relative_uri(
                self.pkgmeta['download'])
            rc = self.Entropy.fetch_file_on_mirrors(
                self.pkgmeta['repository'],
                branch,
                self.pkgmeta['download'],
                self.pkgmeta['checksum'],
                fetch_abort_function = self.fetch_abort_function
            )

        if rc == 0:
            return 0

        mytxt = "%s. %s: %s" % (
            red(_("Package cannot be fetched. Try to update repositories")),
            blue(_("Error")),
            rc,
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "error",
            header = darkred("   ## ")
        )

        return rc

    def multi_fetch_step(self):
        self.error_on_not_prepared()

        m_fetch_len = len(self.pkgmeta['multi_fetch_list'])
        mytxt = "%s: %s %s" % (
            blue(_("Downloading")),
            darkred(str(m_fetch_len)),
            _("archives"),
        )

        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        rc, err_list = self.Entropy.fetch_files_on_mirrors(
            self.pkgmeta['multi_fetch_list'],
            self.pkgmeta['checksum'],
            fetch_abort_function = self.fetch_abort_function
        )

        if rc == 0:
            return 0

        mytxt = _("Some packages cannot be fetched")
        mytxt2 = _("Try to update your repositories and retry")
        mytxt3 = "%s: %s" % (brown(_("Error")), bold(str(rc)),)
        for txt in (mytxt, mytxt2,):
            self.Entropy.updateProgress(
                "%s." % (darkred(txt),),
                importance = 0,
                type = "info",
                header = red("   ## ")
            )
        self.Entropy.updateProgress(
            mytxt3,
            importance = 0,
            type = "info",
            header = red("   ## ")
        )

        for repo, branch, fname, cksum, signatures in err_list:
            self.Entropy.updateProgress(
                "[%s:%s|%s] %s" % (blue(repo), brown(branch),
                    darkgreen(cksum), darkred(fname),),
                importance = 1,
                type = "error",
                header = darkred("    # ")
            )

        return rc

    def fetch_not_available_step(self):
        self.Entropy.updateProgress(
            blue(_("Package cannot be downloaded, unknown error.")),
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        return 0

    def vanished_step(self):
        self.Entropy.updateProgress(
            blue(_("Installed package in queue vanished, skipping.")),
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        return 0

    def checksum_step(self):
        self.error_on_not_prepared()
        return self.match_checksum()

    def multi_checksum_step(self):
        self.error_on_not_prepared()
        return self.multi_match_checksum()

    def unpack_step(self):
        self.error_on_not_prepared()

        if not self.pkgmeta['merge_from']:
            mytxt = "%s: %s" % (
                blue(_("Unpacking package")),
                red(os.path.basename(self.pkgmeta['download'])),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red("   ## ")
        )
        else:
            mytxt = "%s: %s" % (
                blue(_("Merging package")),
                red(os.path.basename(self.pkgmeta['atom'])),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red("   ## ")
            )
        rc = self.__unpack_package()
        if rc != 0:
            if rc == 512:
                errormsg = "%s. %s. %s: 512" % (
                    red(_("You are running out of disk space")),
                    red(_("I bet, you're probably Michele")),
                    blue(_("Error")),
                )
            else:
                msg = _("An error occured while trying to unpack the package")
                errormsg = "%s. %s. %s: %s" % (
                    red(msg),
                    red(_("Check if your system is healthy")),
                    blue(_("Error")),
                    rc,
                )
            self.Entropy.updateProgress(
                errormsg,
                importance = 1,
                type = "error",
                header = red("   ## ")
            )
        return rc

    def install_step(self):
        self.error_on_not_prepared()
        mytxt = "%s: %s" % (
            blue(_("Installing package")),
            red(self.pkgmeta['atom']),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        if self.pkgmeta.get('description'):
            mytxt = "[%s]" % (purple(self.pkgmeta.get('description')),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red("   ## ")
            )

        rc = self.__install_package()
        if rc != 0:
            mytxt = "%s. %s. %s: %s" % (
                red(_("An error occured while trying to install the package")),
                red(_("Check if your system is healthy")),
                blue(_("Error")),
                rc,
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = red("   ## ")
            )
        return rc

    def remove_step(self):
        self.error_on_not_prepared()
        mytxt = "%s: %s" % (
            blue(_("Removing data")),
            red(self.pkgmeta['removeatom']),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )

        rc = self.__remove_package()
        if rc != 0:
            mytxt = "%s. %s. %s: %s" % (
                red(_("An error occured while trying to remove the package")),
                red(_("Check if you have enough disk space on your hard disk")),
                blue(_("Error")),
                rc,
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = red("   ## ")
            )
        return rc

    def cleanup_step(self):
        self.error_on_not_prepared()
        mytxt = "%s: %s" % (
            blue(_("Cleaning")),
            red(self.pkgmeta['atom']),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        self._cleanup_package(self.pkgmeta['unpackdir'])
        # we don't care if cleanupPackage fails since it's not critical
        return 0

    def logmessages_step(self):
        for msg in self.pkgmeta['messages']:
            self.Entropy.clientLog.write(">>>  "+msg)
        return 0

    def postinstall_step(self):
        self.error_on_not_prepared()
        pkgdata = self.pkgmeta['triggers'].get('install')
        if pkgdata:
            trigger = self.Entropy.Triggers('postinstall', pkgdata, self.action)
            do = trigger.prepare()
            if do:
                trigger.run()
            trigger.kill()
        del pkgdata
        return 0

    def preinstall_step(self):
        self.error_on_not_prepared()
        pkgdata = self.pkgmeta['triggers'].get('install')
        if pkgdata:

            trigger = self.Entropy.Triggers('preinstall', pkgdata, self.action)
            do = trigger.prepare()
            if self.pkgmeta.get("diffremoval") and do:
                # diffremoval is true only when the
                # removal is triggered by a package install
                remdata = self.pkgmeta['triggers'].get('remove')
                if remdata:
                    r_trigger = self.Entropy.Triggers('preremove', remdata,
                        self.action)
                    r_trigger.prepare()
                    r_trigger.triggers = [x for x in trigger.triggers if x \
                        not in r_trigger.triggers]
                    r_trigger.kill()
                del remdata
            if do:
                trigger.run()
            trigger.kill()

        del pkgdata
        return 0

    def preremove_step(self):
        self.error_on_not_prepared()
        remdata = self.pkgmeta['triggers'].get('remove')
        if remdata:
            trigger = self.Entropy.Triggers('preremove', remdata, self.action)
            do = trigger.prepare()
            if do:
                trigger.run()
                trigger.kill()
        del remdata
        return 0

    def postremove_step(self):
        self.error_on_not_prepared()
        remdata = self.pkgmeta['triggers'].get('remove')
        if remdata:

            trigger = self.Entropy.Triggers('postremove', remdata, self.action)
            do = trigger.prepare()
            if self.pkgmeta['diffremoval'] and \
                (self.pkgmeta.get("atom") is not None) and do:
                # diffremoval is true only when the remove
                # action is triggered by installPackages()
                pkgdata = self.pkgmeta['triggers'].get('install')
                if pkgdata:
                    i_trigger = self.Entropy.Triggers('postinstall', pkgdata,
                        self.action)
                    i_trigger.prepare()
                    i_trigger.triggers = [x for x in trigger.triggers if x \
                        not in i_trigger.triggers]
                    i_trigger.kill()
                del pkgdata
            if do:
                trigger.run()
            trigger.kill()

        del remdata
        return 0

    def removeconflict_step(self):
        self.error_on_not_prepared()

        for idpackage in self.pkgmeta['conflicts']:
            if not self.Entropy.clientDbconn.isIdpackageAvailable(idpackage):
                continue

            pkg = self.Entropy.Package()
            pkg.prepare((idpackage,), "remove_conflict",
                self.pkgmeta['remove_metaopts'])

            rc = pkg.run(xterm_header = self.xterm_title)
            pkg.kill()
            if rc != 0:
                return rc

        return 0

    def config_step(self):
        self.error_on_not_prepared()

        mytxt = "%s: %s" % (
            blue(_("Configuring package")),
            red(self.pkgmeta['atom']),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )

        conf_rc = self.__configure_package()
        if conf_rc == 1:
            mytxt = _("An error occured while trying to configure the package")
            mytxt2 = "%s. %s: %s" % (
                red(_("Make sure that your system is healthy")),
                blue(_("Error")),
                conf_rc,
            )
            self.Entropy.updateProgress(
                darkred(mytxt),
                importance = 1,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy.updateProgress(
                mytxt2,
                importance = 1,
                type = "error",
                header = red("   ## ")
            )

        elif conf_rc == 2:
            mytxt = _("An error occured while trying to configure the package")
            mytxt2 = "%s. %s: %s" % (
                red(_("It seems that Source Package Manager entry is missing")),
                blue(_("Error")),
                conf_rc,
            )
            self.Entropy.updateProgress(
                darkred(mytxt),
                importance = 1,
                type = "error",
                header = red("   ## ")
            )
            self.Entropy.updateProgress(
                mytxt2,
                importance = 1,
                type = "error",
                header = red("   ## ")
            )

        return conf_rc

    def run_stepper(self, xterm_header):
        if xterm_header is None:
            xterm_header = ""

        if self.pkgmeta.has_key('remove_installed_vanished'):
            self.xterm_title += ' %s' % (_("Installed package vanished"),)
            self.Entropy.setTitle(self.xterm_title)
            rc = self.vanished_step()
            return rc

        if self.pkgmeta.has_key('fetch_not_available'):
            self.xterm_title += ' %s' % (_("Fetch not available"),)
            self.Entropy.setTitle(self.xterm_title)
            rc = self.fetch_not_available_step()
            return rc

        def do_fetch():
            self.xterm_title += ' %s: %s' % (
                _("Fetching"),
                os.path.basename(self.pkgmeta['download']),
            )
            self.Entropy.setTitle(self.xterm_title)
            return self.fetch_step()

        def do_multi_fetch():
            self.xterm_title += ' %s: %s %s' % (_("Multi Fetching"),
                len(self.pkgmeta['multi_fetch_list']), _("packages"),)
            self.Entropy.setTitle(self.xterm_title)
            return self.multi_fetch_step()

        def do_sources_fetch():
            self.xterm_title += ' %s: %s' % (
                _("Fetching sources"),
                os.path.basename(self.pkgmeta['atom']),)
            self.Entropy.setTitle(self.xterm_title)
            return self.sources_fetch_step()

        def do_checksum():
            self.xterm_title += ' %s: %s' % (_("Verifying"),
                os.path.basename(self.pkgmeta['download']),)
            self.Entropy.setTitle(self.xterm_title)
            return self.checksum_step()

        def do_multi_checksum():
            self.xterm_title += ' %s: %s %s' % (_("Multi Verification"),
                len(self.pkgmeta['multi_checksum_list']), _("packages"),)
            self.Entropy.setTitle(self.xterm_title)
            return self.multi_checksum_step()

        def do_unpack():
            if not self.pkgmeta['merge_from']:
                mytxt = _("Unpacking")
                self.xterm_title += ' %s: %s' % (
                    mytxt,
                    os.path.basename(self.pkgmeta['download']),
                )
            else:
                mytxt = _("Merging")
                self.xterm_title += ' %s: %s' % (
                    mytxt,
                    os.path.basename(self.pkgmeta['atom']),
                )
            self.Entropy.setTitle(self.xterm_title)
            return self.unpack_step()

        def do_remove_conflicts():
            return self.removeconflict_step()

        def do_install():
            self.xterm_title += ' %s: %s' % (
                _("Installing"),
                self.pkgmeta['atom'],
            )
            self.Entropy.setTitle(self.xterm_title)
            return self.install_step()

        def do_remove():
            self.xterm_title += ' %s: %s' % (
                _("Removing"),
                self.pkgmeta['removeatom'],
            )
            self.Entropy.setTitle(self.xterm_title)
            return self.remove_step()

        def do_logmessages():
            return self.logmessages_step()

        def do_cleanup():
            self.xterm_title += ' %s: %s' % (
                _("Cleaning"),
                self.pkgmeta['atom'],
            )
            self.Entropy.setTitle(self.xterm_title)
            return self.cleanup_step()

        def do_postinstall():
            self.xterm_title += ' %s: %s' % (
                _("Postinstall"),
                self.pkgmeta['atom'],
            )
            self.Entropy.setTitle(self.xterm_title)
            return self.postinstall_step()

        def do_preinstall():
            self.xterm_title += ' %s: %s' % (
                _("Preinstall"),
                self.pkgmeta['atom'],
            )
            self.Entropy.setTitle(self.xterm_title)
            return self.preinstall_step()

        def do_preremove():
            self.xterm_title += ' %s: %s' % (
                _("Preremove"),
                self.pkgmeta['removeatom'],
            )
            self.Entropy.setTitle(self.xterm_title)
            return self.preremove_step()

        def do_postremove():
            self.xterm_title += ' %s: %s' % (
                _("Postremove"),
                self.pkgmeta['removeatom'],
            )
            self.Entropy.setTitle(self.xterm_title)
            return self.postremove_step()

        def do_config():
            self.xterm_title += ' %s: %s' % (
                _("Configuring"),
                self.pkgmeta['atom'],
            )
            self.Entropy.setTitle(self.xterm_title)
            return self.config_step()

        steps_data = {
            "fetch": do_fetch,
            "multi_fetch": do_multi_fetch,
            "multi_checksum": do_multi_checksum,
            "sources_fetch": do_sources_fetch,
            "checksum": do_checksum,
            "unpack": do_unpack,
            "remove_conflicts": do_remove_conflicts,
            "install": do_install,
            "remove": do_remove,
            "logmessages": do_logmessages,
            "cleanup": do_cleanup,
            "postinstall": do_postinstall,
            "preinstall": do_preinstall,
            "postremove": do_postremove,
            "preremove": do_preremove,
            "config": do_config,
        }

        rc = 0
        for step in self.pkgmeta['steps']:
            self.xterm_title = xterm_header
            rc = steps_data.get(step)()
            if rc != 0:
                break
        return rc


    def run(self, xterm_header = None):
        self.error_on_not_prepared()

        gave_up = self.Entropy.lock_check(self.Entropy.resources_check_lock)
        if gave_up:
            return 20

        locked = self.Entropy.application_lock_check()
        if locked:
            return 21

        # lock
        acquired = self.Entropy.resources_create_lock()
        if not acquired:
            self.Entropy.updateProgress(
                blue(_("Cannot acquire Entropy resources lock.")),
                importance = 2,
                type = "error",
                header = darkred("   ## ")
            )
            return 4 # app locked during lock acquire
        try:
            rc = self.run_stepper(xterm_header)
        finally:
            self.Entropy.resources_remove_lock()

        # remove lock
        self.Entropy.resources_remove_lock()

        if rc != 0:
            self.Entropy.updateProgress(
                blue(_("An error occured. Action aborted.")),
                importance = 2,
                type = "error",
                header = darkred("   ## ")
            )
        return rc

    def prepare(self, matched_atom, action, metaopts = None):
        self.error_on_prepared()

        self.check_action_validity(action)

        self.action = action
        self.matched_atom = matched_atom

        if metaopts is None:
            metaopts = {}
        self.metaopts = metaopts

        # generate metadata dictionary
        self.generate_metadata()

    def generate_metadata(self):
        self.error_on_prepared()

        self.check_action_validity(self.action)

        if self.action == "fetch":
            self.__generate_fetch_metadata()
        elif self.action == "multi_fetch":
            self.__generate_multi_fetch_metadata()
        elif self.action in ("remove", "remove_conflict"):
            self.__generate_remove_metadata()
        elif self.action == "install":
            self.__generate_install_metadata()
        elif self.action == "source":
            self.__generate_fetch_metadata(sources = True)
        elif self.action == "config":
            self.__generate_config_metadata()

        self.__prepared = True

    def __generate_remove_metadata(self):

        self.pkgmeta.clear()
        idpackage = self.matched_atom[0]

        if not self.Entropy.clientDbconn.isIdpackageAvailable(idpackage):
            self.pkgmeta['remove_installed_vanished'] = True
            return 0

        self.pkgmeta['idpackage'] = idpackage
        self.pkgmeta['removeidpackage'] = idpackage
        self.pkgmeta['configprotect_data'] = []
        self.pkgmeta['triggers'] = {}
        self.pkgmeta['removeatom'] = \
            self.Entropy.clientDbconn.retrieveAtom(idpackage)
        self.pkgmeta['slot'] = \
            self.Entropy.clientDbconn.retrieveSlot(idpackage)
        self.pkgmeta['versiontag'] = \
            self.Entropy.clientDbconn.retrieveVersionTag(idpackage)
        self.pkgmeta['diffremoval'] = False

        remove_config = False
        if self.metaopts.has_key('removeconfig'):
            remove_config = self.metaopts.get('removeconfig')
        self.pkgmeta['removeconfig'] = remove_config

        self.pkgmeta['removecontent'] = \
            self.Entropy.clientDbconn.retrieveContent(idpackage)
        self.pkgmeta['triggers']['remove'] = \
            self.Entropy.clientDbconn.getTriggerInfo(idpackage)
        self.pkgmeta['triggers']['remove']['removecontent'] = \
            self.pkgmeta['removecontent']
        self.pkgmeta['triggers']['remove']['accept_license'] = \
            self.Entropy.clientDbconn.retrieveLicensedataKeys(idpackage)

        self.pkgmeta['steps'] = [
            "preremove", "remove", "postremove"
        ]

        return 0

    def __generate_config_metadata(self):
        self.pkgmeta.clear()
        idpackage = self.matched_atom[0]

        self.pkgmeta['atom'] = \
            self.Entropy.clientDbconn.retrieveAtom(idpackage)
        key, slot = self.Entropy.clientDbconn.retrieveKeySlot(idpackage)
        self.pkgmeta['key'], self.pkgmeta['slot'] = key, slot
        self.pkgmeta['version'] = \
            self.Entropy.clientDbconn.retrieveVersion(idpackage)
        self.pkgmeta['accept_license'] = \
            self.Entropy.clientDbconn.retrieveLicensedataKeys(idpackage)
        self.pkgmeta['steps'] = []
        self.pkgmeta['steps'].append("config")

        return 0

    def __generate_install_metadata(self):
        self.pkgmeta.clear()

        idpackage, repository = self.matched_atom
        self.pkgmeta['idpackage'] = idpackage
        self.pkgmeta['repository'] = repository

        # fetch abort function
        if self.metaopts.has_key('fetch_abort_function'):
            self.fetch_abort_function = \
                self.metaopts.pop('fetch_abort_function')

        install_source = etpConst['install_sources']['unknown']
        meta_inst_source = self.metaopts.get('install_source', install_source)
        if meta_inst_source in etpConst['install_sources'].values():
            install_source = meta_inst_source
        self.pkgmeta['install_source'] = install_source

        self.pkgmeta['configprotect_data'] = []
        dbconn = self.Entropy.open_repository(repository)
        self.pkgmeta['triggers'] = {}
        self.pkgmeta['atom'] = dbconn.retrieveAtom(idpackage)
        self.pkgmeta['slot'] = dbconn.retrieveSlot(idpackage)

        ver, tag, rev = dbconn.getVersioningData(idpackage)
        self.pkgmeta['version'] = ver
        self.pkgmeta['versiontag'] = tag
        self.pkgmeta['revision'] = rev

        self.pkgmeta['category'] = dbconn.retrieveCategory(idpackage)
        self.pkgmeta['download'] = dbconn.retrieveDownloadURL(idpackage)
        self.pkgmeta['name'] = dbconn.retrieveName(idpackage)
        self.pkgmeta['messages'] = dbconn.retrieveMessages(idpackage)
        self.pkgmeta['checksum'] = dbconn.retrieveDigest(idpackage)
        sha1, sha256, sha512 = dbconn.retrieveSignatures(idpackage)
        signatures = {
            'sha1': sha1,
            'sha256': sha256,
            'sha512': sha512,
        }
        self.pkgmeta['signatures'] = signatures
        self.pkgmeta['accept_license'] = \
            dbconn.retrieveLicensedataKeys(idpackage)
        self.pkgmeta['conflicts'] = \
            self.Entropy.get_match_conflicts(self.matched_atom)

        description = dbconn.retrieveDescription(idpackage)
        if description:
            if len(description) > 74:
                description = description[:74].strip()
                description += "..."
        self.pkgmeta['description'] = description

        # fill action queue
        self.pkgmeta['removeidpackage'] = -1
        removeConfig = False
        if self.metaopts.has_key('removeconfig'):
            removeConfig = self.metaopts.get('removeconfig')

        self.pkgmeta['remove_metaopts'] = {
            'removeconfig': True,
        }
        if self.metaopts.has_key('remove_metaopts'):
            self.pkgmeta['remove_metaopts'] = \
                self.metaopts.get('remove_metaopts')

        self.pkgmeta['merge_from'] = None
        mf = self.metaopts.get('merge_from')
        if mf != None:
            self.pkgmeta['merge_from'] = unicode(mf)
        self.pkgmeta['removeconfig'] = removeConfig

        pkgkey = entropy.tools.dep_getkey(self.pkgmeta['atom'])
        inst_idpackage, inst_rc = self.Entropy.clientDbconn.atomMatch(pkgkey,
            matchSlot = self.pkgmeta['slot'])

        # filled later...
        self.pkgmeta['removecontent'] = set()
        self.pkgmeta['removeidpackage'] = inst_idpackage

        if self.pkgmeta['removeidpackage'] != -1:
            avail = self.Entropy.clientDbconn.isIdpackageAvailable(
                self.pkgmeta['removeidpackage'])
            if avail:
                inst_atom = self.Entropy.clientDbconn.retrieveAtom(
                    self.pkgmeta['removeidpackage'])
                self.pkgmeta['removeatom'] = inst_atom
            else:
                self.pkgmeta['removeidpackage'] = -1

        # smartpackage ?
        self.pkgmeta['smartpackage'] = False
        # set unpack dir and image dir
        if self.pkgmeta['repository'].endswith(etpConst['packagesext']):

            # FIXME: add repository arch metadata to entropy.db
            # do arch check
            compiled_arch = dbconn.retrieveDownloadURL(idpackage)
            if compiled_arch.find("/"+etpSys['arch']+"/") == -1:
                self.pkgmeta.clear()
                self.__prepared = False
                return -1

            repo_data = self.Entropy.SystemSettings['repositories']
            repo_meta = repo_data['available'][self.pkgmeta['repository']]
            self.pkgmeta['smartpackage'] = repo_meta['smartpackage']
            self.pkgmeta['pkgpath'] = repo_meta['pkgpath']

        else:
            self.pkgmeta['pkgpath'] = etpConst['entropyworkdir'] + \
                os.path.sep + self.pkgmeta['download']

        self.pkgmeta['unpackdir'] = etpConst['entropyunpackdir'] + \
            os.path.sep + self.pkgmeta['download']

        self.pkgmeta['imagedir'] = etpConst['entropyunpackdir'] + \
            os.path.sep + self.pkgmeta['download'] + os.path.sep + \
            etpConst['entropyimagerelativepath']

        self.pkgmeta['pkgdbpath'] = os.path.join(self.pkgmeta['unpackdir'],
            "edb/pkg.db")

        # compare both versions and if they match, disable removeidpackage
        if self.pkgmeta['removeidpackage'] != -1:

            # differential remove list
            self.pkgmeta['diffremoval'] = True
            self.pkgmeta['removeatom'] = \
                self.Entropy.clientDbconn.retrieveAtom(
                    self.pkgmeta['removeidpackage'])

            self.pkgmeta['triggers']['remove'] = \
                self.Entropy.clientDbconn.getTriggerInfo(
                    self.pkgmeta['removeidpackage']
                )
            self.pkgmeta['triggers']['remove']['removecontent'] = \
                self.pkgmeta['removecontent'] # pass reference, not copy! nevva!
            self.pkgmeta['triggers']['remove']['accept_license'] = \
                self.Entropy.clientDbconn.retrieveLicensedataKeys(
                    self.pkgmeta['removeidpackage'])

        # set steps
        self.pkgmeta['steps'] = []
        if self.pkgmeta['conflicts']:
            self.pkgmeta['steps'].append("remove_conflicts")
        # install
        self.pkgmeta['steps'].append("unpack")
        # preinstall placed before preremove in order
        # to respect Spm order
        self.pkgmeta['steps'].append("preinstall")
        if (self.pkgmeta['removeidpackage'] != -1):
            self.pkgmeta['steps'].append("preremove")
        self.pkgmeta['steps'].append("install")
        if (self.pkgmeta['removeidpackage'] != -1):
            self.pkgmeta['steps'].append("postremove")
        self.pkgmeta['steps'].append("postinstall")
        self.pkgmeta['steps'].append("logmessages")
        self.pkgmeta['steps'].append("cleanup")

        self.pkgmeta['triggers']['install'] = dbconn.getTriggerInfo(idpackage)
        self.pkgmeta['triggers']['install']['accept_license'] = \
            self.pkgmeta['accept_license']
        self.pkgmeta['triggers']['install']['unpackdir'] = \
            self.pkgmeta['unpackdir']
        self.pkgmeta['triggers']['install']['imagedir'] = \
            self.pkgmeta['imagedir']

        # FIXME: move to entropy.spm

        self.pkgmeta['xpakpath'] = etpConst['entropyunpackdir'] + \
            os.path.sep + self.pkgmeta['download'] + os.path.sep + \
            etpConst['entropyxpakrelativepath']

        if not self.pkgmeta['merge_from']:
            self.pkgmeta['xpakstatus'] = None
            self.pkgmeta['xpakdir'] = self.pkgmeta['xpakpath'] + \
                os.path.sep + etpConst['entropyxpakdatarelativepath']

        else:
            self.pkgmeta['xpakstatus'] = True
            portdbdir = 'var/db/pkg' # XXX hard coded ?
            portdbdir = os.path.join(self.pkgmeta['merge_from'], portdbdir)
            portdbdir = os.path.join(portdbdir, self.pkgmeta['category'])
            portdbdir = os.path.join(portdbdir, self.pkgmeta['name'] + "-" + \
                self.pkgmeta['version'])

            self.pkgmeta['xpakdir'] = portdbdir

        self.pkgmeta['triggers']['install']['xpakdir'] = \
            self.pkgmeta['xpakdir']


        return 0

    def __generate_fetch_metadata(self, sources = False):
        self.pkgmeta.clear()

        idpackage, repository = self.matched_atom
        dochecksum = True

        # fetch abort function
        if self.metaopts.has_key('fetch_abort_function'):
            self.fetch_abort_function = \
                self.metaopts.pop('fetch_abort_function')

        if self.metaopts.has_key('dochecksum'):
            dochecksum = self.metaopts.get('dochecksum')

        # fetch_path is the path where data should be downloaded
        # at the moment is implemented only for sources = True
        if self.metaopts.has_key('fetch_path'):
            fetch_path = self.metaopts.get('fetch_path')
            if entropy.tools.is_valid_path(fetch_path):
                self.pkgmeta['fetch_path'] = fetch_path

        self.pkgmeta['repository'] = repository
        self.pkgmeta['idpackage'] = idpackage
        dbconn = self.Entropy.open_repository(repository)
        self.pkgmeta['atom'] = dbconn.retrieveAtom(idpackage)
        if sources:
            self.pkgmeta['download'] = dbconn.retrieveSources(idpackage,
                extended = True)
        else:
            self.pkgmeta['checksum'] = dbconn.retrieveDigest(idpackage)
            sha1, sha256, sha512 = dbconn.retrieveSignatures(idpackage)
            signatures = {
                'sha1': sha1,
                'sha256': sha256,
                'sha512': sha512,
            }
            self.pkgmeta['signatures'] = signatures
            self.pkgmeta['download'] = dbconn.retrieveDownloadURL(idpackage)

        if not self.pkgmeta['download']:
            self.pkgmeta['fetch_not_available'] = True
            return 0

        self.pkgmeta['verified'] = False
        self.pkgmeta['steps'] = []
        if not repository.endswith(etpConst['packagesext']) and not sources:
            dl_check = self.Entropy.check_needed_package_download(
                self.pkgmeta['download'], None)

            if dl_check < 0:
                self.pkgmeta['steps'].append("fetch")
            if dochecksum:
                self.pkgmeta['steps'].append("checksum")

        elif sources:
            self.pkgmeta['steps'].append("sources_fetch")

        if sources:
            # create sources destination directory
            unpack_dir = os.path.join(etpConst['entropyunpackdir'],
                "sources", self.pkgmeta['atom'])
            self.pkgmeta['unpackdir'] = unpack_dir

            if not self.pkgmeta.get('fetch_path'):
                if os.path.lexists(unpack_dir):
                    if os.path.isfile(unpack_dir):
                        os.remove(unpack_dir)
                    elif os.path.isdir(unpack_dir):
                        shutil.rmtree(unpack_dir, True)
                if not os.path.lexists(unpack_dir):
                    os.makedirs(unpack_dir, 0775)
                const_setup_perms(unpack_dir, etpConst['entropygid'])
            return 0

        # downloading binary package
        # if file exists, first checksum then fetch
        down_path = os.path.join(etpConst['entropyworkdir'],
            self.pkgmeta['download'])
        if os.access(down_path, os.R_OK | os.F_OK):
            # check size first
            repo_size = dbconn.retrieveSize(idpackage)
            f = open(down_path, "r")
            f.seek(0, os.SEEK_END)
            disk_size = f.tell()
            f.close()
            if repo_size == disk_size:
                self.pkgmeta['steps'].reverse()

        return 0

    def __generate_multi_fetch_metadata(self):
        self.pkgmeta.clear()

        if not isinstance(self.matched_atom, list):
            raise IncorrectParameter("IncorrectParameter: "
                "matched_atom must be a list of tuples, not %s" % (
                    type(self.matched_atom,)
                )
            )

        dochecksum = True

        # meta options
        if self.metaopts.has_key('fetch_abort_function'):
            self.fetch_abort_function = \
                self.metaopts.pop('fetch_abort_function')

        if self.metaopts.has_key('dochecksum'):
            dochecksum = self.metaopts.get('dochecksum')
        self.pkgmeta['checksum'] = dochecksum

        matches = self.matched_atom
        self.pkgmeta['matches'] = matches
        self.pkgmeta['atoms'] = []
        self.pkgmeta['repository_atoms'] = {}
        temp_fetch_list = []
        temp_checksum_list = []
        temp_already_downloaded_count = 0
        etp_workdir = etpConst['entropyworkdir']
        for idpackage, repository in matches:

            if repository.endswith(etpConst['packagesext']):
                continue

            dbconn = self.Entropy.open_repository(repository)
            myatom = dbconn.retrieveAtom(idpackage)

            # general purpose metadata
            self.pkgmeta['atoms'].append(myatom)
            if not self.pkgmeta['repository_atoms'].has_key(repository):
                self.pkgmeta['repository_atoms'][repository] = set()
            self.pkgmeta['repository_atoms'][repository].add(myatom)

            download = dbconn.retrieveDownloadURL(idpackage)
            digest = dbconn.retrieveDigest(idpackage)

            sha1, sha256, sha512 = dbconn.retrieveSignatures(idpackage)
            signatures = {
                'sha1': sha1,
                'sha256': sha256,
                'sha512': sha512,
            }

            repo_size = dbconn.retrieveSize(idpackage)
            orig_branch = self.Entropy.get_branch_from_download_relative_uri(
                download)
            if self.Entropy.check_needed_package_download(download, None) < 0:
                obj = (repository, orig_branch, download, digest, signatures,)
                temp_fetch_list.append(obj)
                continue

            elif dochecksum:
                obj = (repository, orig_branch, download, digest, signatures,)
                temp_checksum_list.append(obj)

            down_path = os.path.join(etp_workdir, download)
            if os.path.isfile(down_path):
                with open(down_path, "r") as f:
                    f.seek(0, os.SEEK_END)
                    disk_size = f.tell()
                if repo_size == disk_size:
                    temp_already_downloaded_count += 1

        self.pkgmeta['steps'] = []
        self.pkgmeta['multi_fetch_list'] = temp_fetch_list
        self.pkgmeta['multi_checksum_list'] = temp_checksum_list
        if self.pkgmeta['multi_fetch_list']:
            self.pkgmeta['steps'].append("multi_fetch")
        if self.pkgmeta['multi_checksum_list']:
            self.pkgmeta['steps'].append("multi_checksum")
        if temp_already_downloaded_count == len(temp_checksum_list):
            self.pkgmeta['steps'].reverse()

        return 0
