
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
from __future__ import with_statement
import os
import subprocess
import time
import shutil
from entropy.const import *
from entropy.exceptions import *
from entropy.i18n import _
from entropy.output import TextInterface, brown, blue, bold, darkgreen, darkblue, red, purple, darkred, print_info, print_error, print_warning
from entropy.misc import TimeScheduled
from entropy.db import dbapi2, LocalRepository
from entropy.client.interfaces.client import Client

class Package:

    import entropy.tools as entropyTools
    import entropy.dump as dumpTools
    def __init__(self, EquoInstance):

        if not isinstance(EquoInstance,Client):
            mytxt = _("A valid Client instance or subclass is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        self.Entropy = EquoInstance
        from entropy.cache import EntropyCacher
        self.Cacher = EntropyCacher()
        self.infoDict = {}
        self.prepared = False
        self.matched_atom = ()
        self.valid_actions = ("source","fetch","multi_fetch","remove",
            "remove_conflict","install","config"
        )
        self.action = None
        self.fetch_abort_function = None
        self.xterm_title = ''

    def kill(self):
        self.infoDict.clear()
        self.matched_atom = ()
        self.valid_actions = ()
        self.action = None
        self.prepared = False
        self.fetch_abort_function = None

    def error_on_prepared(self):
        if self.prepared:
            mytxt = _("Already prepared")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))

    def error_on_not_prepared(self):
        if not self.prepared:
            mytxt = _("Not yet prepared")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))

    def check_action_validity(self, action):
        if action not in self.valid_actions:
            mytxt = _("Action must be in")
            raise InvalidData("InvalidData: %s %s" % (mytxt,self.valid_actions,))

    def match_checksum(self, repository = None, checksum = None, download = None):
        self.error_on_not_prepared()

        if repository == None:
            repository = self.infoDict['repository']
        if checksum == None:
            checksum = self.infoDict['checksum']
        if download == None:
            download = self.infoDict['download']

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
            dlcheck = self.Entropy.check_needed_package_download(download, checksum = checksum)
            if dlcheck == 0:
                basef = os.path.basename(download)
                self.Entropy.updateProgress(
                    "%s: %s" % (blue(_("Package checksum matches")),darkgreen(basef),),
                    importance = 0,
                    type = "info",
                    header = red("   ## ")
                )
                self.infoDict['verified'] = True
                match = True
                break # file downloaded successfully
            else:
                dlcount += 1
                self.Entropy.updateProgress(
                    blue(_("Package checksum does not match. Redownloading... attempt #%s") % (dlcount,)),
                    importance = 0,
                    type = "info",
                    header = red("   ## "),
                    back = True
                )
                fetch = self.Entropy.fetch_file_on_mirrors(
                    repository,
                    self.Entropy.get_branch_from_download_relative_uri(download),
                    download,
                    checksum,
                    fetch_abort_function = self.fetch_abort_function
                )
                if fetch != 0:
                    self.Entropy.updateProgress(
                        blue(_("Cannot properly fetch package! Quitting.")),
                        importance = 0,
                        type = "info",
                        header = red("   ## ")
                    )
                    return fetch
                self.infoDict['verified'] = True
                match = True
                break
        if (not match):
            mytxt = _("Cannot properly fetch package or checksum does not match. Try download latest repositories.")
            self.Entropy.updateProgress(
                blue(mytxt),
                importance = 0,
                type = "info",
                header = red("   ## ")
            )
            return 1
        return 0

    def multi_match_checksum(self):
        rc = 0
        for repository, branch, download, digest in self.infoDict['multi_checksum_list']:
            rc = self.match_checksum(repository, digest, download)
            if rc != 0: break
        return rc

    '''
    @description: unpack the given package file into the unpack dir
    @input infoDict: dictionary containing package information
    @output: 0 = all fine, >0 = error!
    '''
    def __unpack_package(self):

        if not self.infoDict['merge_from']:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Unpacking package: "+str(self.infoDict['atom']))
        else:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Merging package: "+str(self.infoDict['atom']))

        if os.path.isdir(self.infoDict['unpackdir']):
            shutil.rmtree(self.infoDict['unpackdir'].encode('raw_unicode_escape'))
        elif os.path.isfile(self.infoDict['unpackdir']):
            os.remove(self.infoDict['unpackdir'].encode('raw_unicode_escape'))
        os.makedirs(self.infoDict['imagedir'])

        if not os.path.isfile(self.infoDict['pkgpath']) and not self.infoDict['merge_from']:
            if os.path.isdir(self.infoDict['pkgpath']):
                shutil.rmtree(self.infoDict['pkgpath'])
            if os.path.islink(self.infoDict['pkgpath']):
                os.remove(self.infoDict['pkgpath'])
            self.infoDict['verified'] = False
            rc = self.fetch_step()
            if rc != 0: return rc

        if not self.infoDict['merge_from']:
            unpack_tries = 3
            while 1:
                unpack_tries -= 1
                try:
                    rc = self.entropyTools.spawn_function(
                        self.entropyTools.uncompress_tar_bz2,
                        self.infoDict['pkgpath'],
                        self.infoDict['imagedir'],
                        catchEmpty = True
                    )
                except EOFError:
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"EOFError on "+self.infoDict['pkgpath'])
                    rc = 1
                except (UnicodeEncodeError, UnicodeDecodeError, self.dumpTools.pickle.PicklingError,):
                    # this will make devs to actually catch the right exception and prepare a fix
                    self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Raising Unicode/Pickling Error for "+self.infoDict['pkgpath'])
                    rc = self.entropyTools.uncompress_tar_bz2(
                        self.infoDict['pkgpath'],self.infoDict['imagedir'],
                        catchEmpty = True
                    )
                if rc == 0:
                    break
                if unpack_tries <= 0:
                    return rc
                # otherwise, try to download it again
                self.infoDict['verified'] = False
                f_rc = self.fetch_step()
                if f_rc != 0: return f_rc
        else:
            pid = os.fork()
            if pid > 0:
                os.waitpid(pid, 0)
            else:
                self.__fill_image_dir(self.infoDict['merge_from'],self.infoDict['imagedir'])
                os._exit(0)

        # unpack xpak ?
        if etpConst['gentoo-compat']:
            if os.path.isdir(self.infoDict['xpakpath']):
                shutil.rmtree(self.infoDict['xpakpath'])
            try:
                os.rmdir(self.infoDict['xpakpath'])
            except OSError:
                pass

            # create data dir where we'll unpack the xpak
            os.makedirs(self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'],0755)
            #os.mkdir(self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath'])
            xpakPath = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakfilename']

            if not self.infoDict['merge_from']:
                if (self.infoDict['smartpackage']):
                    # we need to get the .xpak from database
                    xdbconn = self.Entropy.open_repository(self.infoDict['repository'])
                    xpakdata = xdbconn.retrieveXpakMetadata(self.infoDict['idpackage'])
                    if xpakdata:
                        # save into a file
                        f = open(xpakPath,"wb")
                        f.write(xpakdata)
                        f.flush()
                        f.close()
                        self.infoDict['xpakstatus'] = self.entropyTools.unpack_xpak(
                            xpakPath,
                            self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                        )
                    else:
                        self.infoDict['xpakstatus'] = None
                    del xpakdata
                else:
                    self.infoDict['xpakstatus'] = self.entropyTools.extract_xpak(
                        self.infoDict['pkgpath'],
                        self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                    )
            else:
                # link xpakdir to self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                tolink_dir = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
                if os.path.isdir(tolink_dir):
                    shutil.rmtree(tolink_dir,True)
                # now link
                os.symlink(self.infoDict['xpakdir'],tolink_dir)

            # create fake portage ${D} linking it to imagedir
            portage_db_fakedir = os.path.join(
                self.infoDict['unpackdir'],
                "portage/"+self.infoDict['category'] + "/" + self.infoDict['name'] + "-" + self.infoDict['version']
            )

            os.makedirs(portage_db_fakedir,0755)
            # now link it to self.infoDict['imagedir']
            os.symlink(self.infoDict['imagedir'],os.path.join(portage_db_fakedir,"image"))

        return 0

    def __configure_package(self):

        try: Spm = self.Entropy.Spm()
        except: return 1

        spm_atom = self.infoDict['key']+"-"+self.infoDict['version']
        myebuild = Spm.get_vdb_path()+spm_atom+"/"+self.infoDict['key'].split("/")[1]+"-"+self.infoDict['version']+etpConst['spm']['source_build_ext']
        if not os.path.isfile(myebuild):
            return 2

        self.Entropy.updateProgress(
            brown(" Ebuild: pkg_config()"),
            importance = 0,
            header = red("   ##")
        )

        try:
            rc = Spm.spm_doebuild(
                myebuild,
                mydo = "config",
                tree = "bintree",
                cpv = spm_atom
            )
            if rc == 1:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] ATTENTION Cannot properly run Spm pkg_config() for " + \
                    str(spm_atom)+". Something bad happened."
                )
                return 3
        except Exception, e:
            self.entropyTools.print_traceback()
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[PRE] ATTENTION Cannot run Spm pkg_config() for "+spm_atom+"!! "+str(type(Exception))+": "+str(e)
            )
            mytxt = "%s: %s %s. %s. %s: %s, %s" % (
                bold(_("QA")),
                brown(_("Cannot run Spm pkg_config() for")),
                bold(str(spm_atom)),
                brown(_("Please report it")),
                bold(_("Error")),
                type(Exception),
                e,
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return 1

        return 0


    def __remove_package(self):

        # clear on-disk cache
        self.__clear_cache()

        self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing package: %s" % (self.infoDict['removeatom'],))

        protected_removable_config_files = {}
        # remove from database
        if self.infoDict['removeidpackage'] != -1:
            mytxt = "%s: " % (_("Removing from Entropy"),)
            self.Entropy.updateProgress(
                blue(mytxt) + red(self.infoDict['removeatom']),
                importance = 1,
                type = "info",
                header = red("   ## ")
            )
            protected_removable_config_files = self.Entropy.clientDbconn.retrieveAutomergefiles(
                self.infoDict['removeidpackage'], get_dict = True
            )
            self.__remove_package_from_database()

        # Handle gentoo database
        if etpConst['gentoo-compat']:
            gentooAtom = self.entropyTools.remove_tag(self.infoDict['removeatom'])
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"Removing from Portage: "+str(gentooAtom))
            self.__remove_package_from_gentoo_database(gentooAtom)

        self.__remove_content_from_system(protected_removable_config_files)
        return 0

    def __remove_content_from_system(self, protected_removable_config_files):

        # load CONFIG_PROTECT and its mask
        # client database at this point has been surely opened,
        # so our dicts are already filled
        protect = etpConst['dbconfigprotect']
        mask = etpConst['dbconfigprotectmask']
        sys_root = etpConst['systemroot']
        col_protect = self.Entropy.SystemSettings['client']['collisionprotect']

        # remove files from system
        directories = set()
        for item in self.infoDict['removecontent']:
            sys_root_item = sys_root+item
            # collision check
            if col_protect > 0:

                if self.Entropy.clientDbconn.isFileAvailable(item) and os.path.isfile(sys_root_item):
                    # in this way we filter out directories
                    mytxt = red(_("Collision found during removal of")) + " " + sys_root_item + " - "
                    mytxt += red(_("cannot overwrite"))
                    self.Entropy.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "warning",
                        header = red("   ## ")
                    )
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "Collision found during remove of "+sys_root_item+" - cannot overwrite"
                    )
                    continue

            protected = False
            if (not self.infoDict['removeconfig']) and (not self.infoDict['diffremoval']):

                protected_item_test = sys_root_item
                if isinstance(protected_item_test,unicode):
                    protected_item_test = protected_item_test.encode('utf-8')

                in_mask, protected, x, do_continue = self._handle_config_protect(
                    protect, mask, None, protected_item_test,
                    do_allocation_check = False, do_quiet = True)

                if do_continue: protected = True

                # when files have not been modified by the user
                # and they are inside a config protect directory
                # we could even remove them directly
                if in_mask:

                    oldprot_md5 = protected_removable_config_files.get(item)
                    if oldprot_md5 and os.path.exists(protected_item_test) and \
                        os.access(protected_item_test, os.R_OK):

                        in_system_md5 = self.entropyTools.md5sum(protected_item_test)
                        if oldprot_md5 == in_system_md5:
                            mytxt = "%s: %s" % (
                                darkgreen(_("Removing config file, never modified")),
                                blue(item),)
                            self.Entropy.updateProgress(
                                mytxt,
                                importance = 1,
                                type = "info",
                                header = red("   ## ")
                            )
                            protected = False
                            do_continue = False

            if protected:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_VERBOSE,
                    "[remove] Protecting config file: "+sys_root_item
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
            else:
                try:
                    os.lstat(sys_root_item)
                except OSError:
                    continue # skip file, does not exist
                except UnicodeEncodeError:
                    mytxt = brown(_("This package contains a badly encoded file !!!"))
                    self.Entropy.updateProgress(
                        red("QA: ")+mytxt,
                        importance = 1,
                        type = "warning",
                        header = darkred("   ## ")
                    )
                    continue # file has a really bad encoding

                if os.path.isdir(sys_root_item) and os.path.islink(sys_root_item):
                    # S_ISDIR returns False for directory symlinks, so using os.path.isdir
                    # valid directory symlink
                    directories.add((sys_root_item,"link"))
                elif os.path.isdir(sys_root_item):
                    # plain directory
                    directories.add((sys_root_item,"dir"))
                else: # files, symlinks or not
                    # just a file or symlink or broken directory symlink (remove now)
                    try:
                        os.remove(sys_root_item)
                        # add its parent directory
                        dirfile = os.path.dirname(sys_root_item)
                        if os.path.isdir(dirfile) and os.path.islink(dirfile):
                            directories.add((dirfile,"link"))
                        elif os.path.isdir(dirfile):
                            directories.add((dirfile,"dir"))
                    except OSError:
                        pass

        # now handle directories
        directories = sorted(directories, reverse = True)
        while 1:
            taint = False
            for directory, dirtype in directories:
                mydir = "%s%s" % (sys_root,directory,)
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
        del directories


    '''
    @description: remove package entry from Gentoo database
    @input gentoo package atom (cat/name+ver):
    @output: 0 = all fine, <0 = error!
    '''
    def __remove_package_from_gentoo_database(self, atom):

        # handle gentoo-compat
        try:
            Spm = self.Entropy.Spm()
        except:
            return -1 # no Spm support ??

        portDbDir = Spm.get_vdb_path()
        removePath = portDbDir+atom
        key = self.entropyTools.dep_getkey(atom)
        others_installed = Spm.search_keys(key)
        slot = self.infoDict['slot']
        tag = self.infoDict['versiontag']
        if (tag == slot) and tag: slot = "0"
        if os.path.isdir(removePath):
            shutil.rmtree(removePath,True)
        elif others_installed:
            for myatom in others_installed:
                myslot = Spm.get_installed_package_slot(myatom)
                if myslot != slot:
                    continue
                shutil.rmtree(portDbDir+myatom,True)

        if not others_installed:
            world_file = Spm.get_world_file()
            world_file_tmp = world_file+".entropy.tmp"
            if os.access(world_file,os.W_OK) and os.path.isfile(world_file):
                new = open(world_file_tmp,"w")
                old = open(world_file,"r")
                line = old.readline()
                while line:
                    if line.find(key) != -1:
                        line = old.readline()
                        continue
                    if line.find(key+":"+slot) != -1:
                        line = old.readline()
                        continue
                    new.write(line)
                    line = old.readline()
                new.flush()
                new.close()
                old.close()
                shutil.move(world_file_tmp,world_file)

        return 0

    '''
    @description: function that runs at the end of the package installation process, just removes data left by other steps
    @output: 0 = all fine, >0 = error!
    '''
    def _cleanup_package(self, unpack_dir):
        # remove unpack dir
        shutil.rmtree(unpack_dir,True)
        try: os.rmdir(unpack_dir)
        except OSError: pass
        return 0

    def __remove_package_from_database(self, do_commit = False, do_cleanup = False):
        self.error_on_not_prepared()
        self.Entropy.clientDbconn.removePackage(self.infoDict['removeidpackage'],
            do_commit = do_commit, do_cleanup = do_cleanup)
        return 0

    def __clear_cache(self):
        self.Entropy.clear_dump_cache(etpCache['advisories'])
        self.Entropy.clear_dump_cache(etpCache['filter_satisfied_deps'])
        self.Entropy.clear_dump_cache(etpCache['depends_tree'])
        self.Entropy.clear_dump_cache(etpCache['check_package_update'])
        self.Entropy.clear_dump_cache(etpCache['dep_tree'])
        self.Entropy.clear_dump_cache(etpCache['dbMatch']+etpConst['clientdbid']+"/")
        self.Entropy.clear_dump_cache(etpCache['dbSearch']+etpConst['clientdbid']+"/")

        self.__update_available_cache()
        try:
            self.__update_world_cache()
        except:
            self.Entropy.clear_dump_cache(etpCache['world_update'])

    def __update_world_cache(self):
        if self.Entropy.xcache and (self.action in ("install","remove",)):
            wc_dir = os.path.dirname(os.path.join(etpConst['dumpstoragedir'],etpCache['world_update']))
            wc_filename = os.path.basename(etpCache['world_update'])
            wc_cache_files = [os.path.join(wc_dir,x) for x in os.listdir(wc_dir) if x.startswith(wc_filename)]
            for cache_file in wc_cache_files:

                try:
                    data = self.Entropy.dumpTools.loadobj(cache_file, complete_path = True)
                    (update, remove, fine) = data['r']
                    empty_deps = data['empty_deps']
                except:
                    self.Entropy.clear_dump_cache(etpCache['world_update'])
                    return

                if empty_deps:
                    continue

                if self.action == "install":
                    if self.matched_atom in update:
                        update.remove(self.matched_atom)
                        self.Entropy.dumpTools.dumpobj(
                            cache_file,
                            {'r':(update, remove, fine),'empty_deps': empty_deps},
                            complete_path = True
                        )
                else:
                    key, slot = self.Entropy.clientDbconn.retrieveKeySlot(self.infoDict['removeidpackage'])
                    matches = self.Entropy.atom_match(key, matchSlot = slot, multiMatch = True, multiRepo = True)
                    if matches[1] != 0:
                        # hell why! better to rip all off
                        self.Entropy.clear_dump_cache(etpCache['world_update'])
                        return
                    taint = False
                    for match in matches[0]:
                        if match in update:
                            taint = True
                            update.remove(match)
                        if match in remove:
                            taint = True
                            remove.remove(match)
                    if taint:
                        self.Entropy.dumpTools.dumpobj(
                            cache_file,
                            {'r':(update, remove, fine),'empty_deps': empty_deps},
                            complete_path = True
                        )

        elif (not self.Entropy.xcache) or (self.action in ("install",)):
            self.Entropy.clear_dump_cache(etpCache['world_update'])

    def __update_available_cache(self):

        # update world available cache
        if self.Entropy.xcache and (self.action in ("remove","install")):

            disk_cache = self.Cacher.pop(etpCache['world_available'])
            if disk_cache != None:
                c_hash = self.Entropy.get_available_packages_chash(etpConst['branch'])
                try:
                    if disk_cache['chash'] == c_hash:

                        # remove and old install
                        if self.infoDict['removeidpackage'] != -1:
                            taint = False
                            key = self.entropyTools.dep_getkey(self.infoDict['removeatom'])
                            slot = self.infoDict['slot']
                            matches = self.Entropy.atom_match(key, matchSlot = slot, multiRepo = True, multiMatch = True)
                            if matches[1] == 0:
                                for mymatch in matches[0]:
                                    if mymatch not in disk_cache['available']:
                                        disk_cache['available'].append(mymatch)
                                        taint = True
                            if taint:
                                mydata = {}
                                mylist = []
                                for myidpackage,myrepo in disk_cache['available']:
                                    mydbc = self.Entropy.open_repository(myrepo)
                                    mydata[mydbc.retrieveAtom(myidpackage)] = (myidpackage,myrepo)
                                mykeys = sorted(mydata.keys())
                                for mykey in mykeys:
                                    mylist.append(mydata[mykey])
                                disk_cache['available'] = mylist

                        # install, doing here because matches[0] could contain self.matched_atoms
                        if self.matched_atom in disk_cache['available']:
                            disk_cache['available'].remove(self.matched_atom)

                        self.Cacher.push(etpCache['world_available'],disk_cache)

                except KeyError:
                    self.Cacher.push(etpCache['world_available'],{})

        elif not self.Entropy.xcache:
            self.Entropy.clear_dump_cache(etpCache['world_available'])


    '''
    @description: install unpacked files, update database and also update gentoo db if requested
    @output: 0 = all fine, >0 = error!
    '''
    def __install_package(self):

        # clear on-disk cache
        self.__clear_cache()

        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "Installing package: %s" % (self.infoDict['atom'],)
        )

        already_protected_config_files = {}
        if self.infoDict['removeidpackage'] != -1:
            already_protected_config_files = self.Entropy.clientDbconn.retrieveAutomergefiles(
                self.infoDict['removeidpackage'], get_dict = True
            )

        # copy files over - install
        # use fork? (in this case all the changed structures need to be pushed back)
        rc = self.__move_image_to_system(already_protected_config_files)
        if rc != 0:
            return rc
        del already_protected_config_files

        # inject into database
        mytxt = "%s: %s" % (blue(_("Updating database")),red(self.infoDict['atom']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        newidpackage = self._install_package_into_database()

        # remove old files and gentoo stuff
        if self.infoDict['removeidpackage'] != -1:
            # doing a diff removal
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Remove old package: %s" % (self.infoDict['removeatom'],)
            )
            self.infoDict['removeidpackage'] = -1 # disabling database removal

            if etpConst['gentoo-compat']:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "Removing Entropy and Gentoo database entry for %s" % (self.infoDict['removeatom'],)
                )
            else:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "Removing Entropy (only) database entry for %s" % (self.infoDict['removeatom'],)
                )

            self.Entropy.updateProgress(
                                    blue(_("Cleaning old package files...")),
                                    importance = 1,
                                    type = "info",
                                    header = red("   ## ")
                                )
            self.__remove_package()

        rc = 0
        if etpConst['gentoo-compat']:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Installing new Gentoo database entry: %s" % (self.infoDict['atom'],)
            )
            rc = self._install_package_into_gentoo_database(newidpackage)

        return rc

    '''
    @description: inject the database information into the Gentoo database
    @output: 0 = all fine, !=0 = error!
    '''
    def _install_package_into_gentoo_database(self, newidpackage):

        # handle gentoo-compat
        try:
            Spm = self.Entropy.Spm()
        except:
            return -1 # no Portage support
        portDbDir = Spm.get_vdb_path()
        if os.path.isdir(portDbDir):

            # extract xpak from unpackDir+etpConst['packagecontentdir']+"/"+package
            key = self.infoDict['category']+"/"+self.infoDict['name']
            atomsfound = set()
            dbdirs = os.listdir(portDbDir)
            if self.infoDict['category'] in dbdirs:
                catdirs = os.listdir(portDbDir+"/"+self.infoDict['category'])
                dirsfound = set([self.infoDict['category']+"/"+x for x in catdirs if \
                    key == self.entropyTools.dep_getkey(self.infoDict['category']+"/"+x)])
                atomsfound.update(dirsfound)

            ### REMOVE
            # parse slot and match and remove
            if atomsfound:
                pkgToRemove = ''
                for atom in atomsfound:
                    atomslot = Spm.get_installed_package_slot(atom)
                    # get slot from gentoo db
                    if atomslot == self.infoDict['slot']:
                        pkgToRemove = atom
                        break
                if (pkgToRemove):
                    removePath = portDbDir+pkgToRemove
                    shutil.rmtree(removePath,True)
                    try:
                        os.rmdir(removePath)
                    except OSError:
                        pass
            del atomsfound

            # we now install it
            if ((self.infoDict['xpakstatus'] != None) and \
                    os.path.isdir( self.infoDict['xpakpath'] + "/" + etpConst['entropyxpakdatarelativepath'])) or \
                    self.infoDict['merge_from']:

                if self.infoDict['merge_from']:
                    copypath = self.infoDict['xpakdir']
                    if not os.path.isdir(copypath):
                        return 0
                else:
                    copypath = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']

                if not os.path.isdir(portDbDir+self.infoDict['category']):
                    os.makedirs(portDbDir+self.infoDict['category'],0755)
                destination = portDbDir+self.infoDict['category']+"/"+self.infoDict['name']+"-"+self.infoDict['version']
                if os.path.isdir(destination):
                    shutil.rmtree(destination)

                try:
                    shutil.copytree(copypath,destination)
                except (IOError,), e:
                    mytxt = "%s: %s: %s: %s" % (red(_("QA")),
                        brown(_("Cannot update Portage database to destination")),
                        purple(destination),e,)
                    self.Entropy.updateProgress(
                        mytxt,
                        importance = 1,
                        type = "warning",
                        header = darkred("   ## ")
                    )

                # test if /var/cache/edb/counter is fine
                if os.path.isfile(etpConst['edbcounter']):
                    try:
                        f = open(etpConst['edbcounter'],"r")
                        counter = int(f.readline().strip())
                        f.close()
                    except:
                        # need file recreation, parse gentoo tree
                        counter = Spm.refill_counter()
                else:
                    counter = Spm.refill_counter()

                # write new counter to file
                if os.path.isdir(destination):
                    counter += 1
                    f = open(destination+"/"+etpConst['spm']['xpak_entries']['counter'],"w")
                    f.write(str(counter))
                    f.flush()
                    f.close()
                    f = open(etpConst['edbcounter'],"w")
                    f.write(str(counter))
                    f.flush()
                    f.close()
                    # update counter inside clientDatabase
                    self.Entropy.clientDbconn.insertCounter(newidpackage,counter)
                else:
                    mytxt = brown(_("Cannot update Portage counter, destination %s does not exist.") % (destination,))
                    self.Entropy.updateProgress(
                        red("QA: ")+mytxt,
                        importance = 1,
                        type = "warning",
                        header = darkred("   ## ")
                    )

            # add to Portage world
            # key: key
            # slot: self.infoDict['slot']
            myslot = self.infoDict['slot']
            if (self.infoDict['versiontag'] == self.infoDict['slot']) and self.infoDict['versiontag']:
                # usually kernel packages
                myslot = "0"
            keyslot = key+":"+myslot
            world_file = Spm.get_world_file()
            world_atoms = set()

            if os.access(world_file,os.R_OK) and os.path.isfile(world_file):
                f = open(world_file,"r")
                world_atoms = set([x.strip() for x in f.readlines() if x.strip()])
                f.close()
            else:
                mytxt = brown(_("Cannot update Portage world file, destination %s does not exist.") % (world_file,))
                self.Entropy.updateProgress(
                    red("QA: ")+mytxt,
                    importance = 1,
                    type = "warning",
                    header = darkred("   ## ")
                )
                return 0

            try:
                if keyslot not in world_atoms and \
                    os.access(os.path.dirname(world_file),os.W_OK) and \
                    self.entropyTools.istextfile(world_file):
                        world_atoms.discard(key)
                        world_atoms.add(keyslot)
                        world_atoms = sorted(list(world_atoms))
                        world_file_tmp = world_file+".entropy_inst"
                        f = open(world_file_tmp,"w")
                        for item in world_atoms:
                            f.write(item+"\n")
                        f.flush()
                        f.close()
                        shutil.move(world_file_tmp,world_file)
            except (UnicodeDecodeError,UnicodeEncodeError), e:
                self.entropyTools.print_traceback(f = self.Entropy.clientLog)
                mytxt = brown(_("Cannot update Portage world file, destination %s is corrupted.") % (world_file,))
                self.Entropy.updateProgress(
                    red("QA: ")+mytxt+": "+unicode(e),
                    importance = 1,
                    type = "warning",
                    header = darkred("   ## ")
                )

        return 0

    '''
    @description: injects package info into the installed packages database
    @output: 0 = all fine, >0 = error!
    '''
    def _install_package_into_database(self):

        # fetch info
        dbconn = self.Entropy.open_repository(self.infoDict['repository'])
        data = dbconn.getPackageData(self.infoDict['idpackage'], content_insert_formatted = True)
        # open client db
        # always set data['injected'] to False
        # installed packages database SHOULD never have more than one package for scope (key+slot)
        data['injected'] = False
        data['counter'] = -1 # gentoo counter will be set in self._install_package_into_gentoo_database()

        idpackage, rev, x = self.Entropy.clientDbconn.handlePackage(
            etpData = data, forcedRevision = data['revision'],
            formattedContent = True)

        # update datecreation
        ctime = self.entropyTools.get_current_unix_time()
        self.Entropy.clientDbconn.setDateCreation(idpackage, str(ctime))

        # add idpk to the installedtable
        self.Entropy.clientDbconn.removePackageFromInstalledTable(idpackage)
        self.Entropy.clientDbconn.addPackageToInstalledTable(idpackage,
            self.infoDict['repository'], self.infoDict['install_source'])

        automerge_data = self.infoDict.get('configprotect_data')
        if automerge_data:
            self.Entropy.clientDbconn.insertAutomergefiles(idpackage,
                automerge_data)

        # clear depends table, this will make clientdb dependstable to be
        # regenerated during the next request (retrieveDepends)
        self.Entropy.clientDbconn.clearDependsTable()
        return idpackage

    def __fill_image_dir(self, mergeFrom, imageDir):

        dbconn = self.Entropy.open_repository(self.infoDict['repository'])
        package_content = dbconn.retrieveContent(self.infoDict['idpackage'], extended = True, formatted = True)
        contents = sorted(package_content)

        # collect files
        for path in contents:
            # convert back to filesystem str
            encoded_path = path
            path = os.path.join(mergeFrom,encoded_path[1:])
            topath = os.path.join(imageDir,encoded_path[1:])
            path = path.encode('raw_unicode_escape')
            topath = topath.encode('raw_unicode_escape')

            try:
                exist = os.lstat(path)
            except OSError:
                continue # skip file
            ftype = package_content[encoded_path]
            if str(ftype) == '0': ftype = 'dir' # force match below, '0' means databases without ftype
            if 'dir' == ftype and \
                not stat.S_ISDIR(exist.st_mode) and \
                os.path.isdir(path): # workaround for directory symlink issues
                path = os.path.realpath(path)

            copystat = False
            # if our directory is a symlink instead, then copy the symlink
            if os.path.islink(path):
                tolink = os.readlink(path)
                if os.path.islink(topath):
                    os.remove(topath)
                os.symlink(tolink,topath)
            elif os.path.isdir(path):
                if not os.path.isdir(topath):
                    os.makedirs(topath)
                    copystat = True
            elif os.path.isfile(path):
                if os.path.isfile(topath):
                    os.remove(topath) # should never happen
                shutil.copy2(path,topath)
                copystat = True

            if copystat:
                user = os.stat(path)[stat.ST_UID]
                group = os.stat(path)[stat.ST_GID]
                os.chown(topath,user,group)
                shutil.copystat(path,topath)


    def __move_image_to_system(self, already_protected_config_files):

        # load CONFIG_PROTECT and its mask
        protect = etpRepositories[self.infoDict['repository']]['configprotect']
        mask = etpRepositories[self.infoDict['repository']]['configprotectmask']
        sys_root = etpConst['systemroot']
        col_protect = self.Entropy.SystemSettings['client']['collisionprotect']
        items_installed = set()

        # setup imageDir properly
        imageDir = self.infoDict['imagedir']
        encoded_imageDir = imageDir.encode('utf-8')
        movefile = self.entropyTools.movefile

        # merge data into system
        for currentdir,subdirs,files in os.walk(encoded_imageDir):
            # create subdirs
            for subdir in subdirs:

                imagepathDir = "%s/%s" % (currentdir,subdir,)
                rootdir = "%s%s" % (sys_root,imagepathDir[len(imageDir):],)

                # handle broken symlinks
                if os.path.islink(rootdir) and not os.path.exists(rootdir):# broken symlink
                    os.remove(rootdir)

                # if our directory is a file on the live system
                elif os.path.isfile(rootdir): # really weird...!
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "WARNING!!! %s is a file when it should be a directory !! Removing in 20 seconds..." % (rootdir,)
                    )
                    mytxt = darkred(_("%s is a file when should be a directory !! Removing in 20 seconds...") % (rootdir,))
                    self.Entropy.updateProgress(
                        red("QA: ")+mytxt,
                        importance = 1,
                        type = "warning",
                        header = red(" !!! ")
                    )
                    self.entropyTools.ebeep(20)
                    os.remove(rootdir)

                # if our directory is a symlink instead, then copy the symlink
                if os.path.islink(imagepathDir) and not os.path.isdir(rootdir):
                    # for security we skip live items that are dirs
                    tolink = os.readlink(imagepathDir)
                    if os.path.islink(rootdir):
                        os.remove(rootdir)
                    os.symlink(tolink,rootdir)
                elif (not os.path.isdir(rootdir)) and (not os.access(rootdir,os.R_OK)):
                    try:
                        # we should really force a simple mkdir first of all
                        os.mkdir(rootdir)
                    except OSError:
                        os.makedirs(rootdir)

                if not os.path.islink(rootdir) and os.access(rootdir,os.W_OK):
                    # symlink doesn't need permissions, also until os.walk ends they might be broken
                    # XXX also, added os.access() check because there might be directories/files unwritable
                    # what to do otherwise?
                    user = os.stat(imagepathDir)[stat.ST_UID]
                    group = os.stat(imagepathDir)[stat.ST_GID]
                    os.chown(rootdir,user,group)
                    shutil.copystat(imagepathDir,rootdir)

                items_installed.add(os.path.join(os.path.realpath(os.path.dirname(rootdir)),os.path.basename(rootdir)))

            for item in files:

                fromfile = "%s/%s" % (currentdir,item,)
                tofile = "%s%s" % (sys_root,fromfile[len(imageDir):],)

                if col_protect > 1:
                    todbfile = fromfile[len(imageDir):]
                    myrc = self._handle_install_collision_protect(tofile, todbfile)
                    if not myrc:
                        continue

                prot_old_tofile = tofile[len(sys_root):]
                pre_tofile = tofile[:]
                in_mask, protected, tofile, do_continue = self._handle_config_protect(
                    protect, mask, fromfile, tofile)

                # collect new config automerge data
                if in_mask and os.path.exists(fromfile):
                    try:
                        prot_md5 = self.entropyTools.md5sum(fromfile)
                        self.infoDict['configprotect_data'].append(
                            (prot_old_tofile,prot_md5,))
                    except (IOError,):
                        pass

                # check if it's really necessary to protect file
                if protected:

                    try:

                        # second task
                        oldprot_md5 = already_protected_config_files.get(
                            prot_old_tofile)

                        if oldprot_md5 and os.path.exists(pre_tofile) and \
                            os.access(pre_tofile, os.R_OK):

                            in_system_md5 = self.entropyTools.md5sum(pre_tofile)
                            if oldprot_md5 == in_system_md5:
                                # we can merge it, files, even if
                                # contains changes have not been modified
                                # by the user
                                mytxt = "%s: %s" % (
                                    darkgreen(_("Automerging config file, never modified")),
                                    blue(pre_tofile),)
                                self.Entropy.updateProgress(
                                    mytxt,
                                    importance = 1,
                                    type = "info",
                                    header = red("   ## ")
                                )
                                protected = False
                                do_continue = False
                                tofile = pre_tofile

                    except (IOError,):
                        pass

                if do_continue:
                    continue

                try:

                    if os.path.realpath(fromfile) == os.path.realpath(tofile) and os.path.islink(tofile):
                        # there is a serious issue here, better removing tofile, happened to someone:
                        try: # try to cope...
                            os.remove(tofile)
                        except OSError:
                            pass

                    # if our file is a dir on the live system
                    if os.path.isdir(tofile) and not os.path.islink(tofile): # really weird...!
                        self.Entropy.clientLog.log(
                            ETP_LOGPRI_INFO,
                            ETP_LOGLEVEL_NORMAL,
                            "WARNING!!! %s is a directory when it should be a file !! Removing in 20 seconds..." % (tofile,)
                        )
                        mytxt = _("%s is a directory when it should be a file !! Removing in 20 seconds...") % (tofile,)
                        self.Entropy.updateProgress(
                            red("QA: ")+darkred(mytxt),
                            importance = 1,
                            type = "warning",
                            header = red(" !!! ")
                        )
                        self.entropyTools.ebeep(10)
                        time.sleep(20)
                        try:
                            shutil.rmtree(tofile, True)
                            os.rmdir(tofile)
                        except:
                            pass
                        try: # if it was a link
                            os.remove(tofile)
                        except OSError:
                            pass

                    # XXX
                    # XXX moving file using the raw format like portage does
                    # XXX
                    done = movefile(fromfile, tofile, src_basedir = encoded_imageDir)
                    if not done:
                        self.Entropy.clientLog.log(
                            ETP_LOGPRI_INFO,
                            ETP_LOGLEVEL_NORMAL,
                            "WARNING!!! Error during file move to system: %s => %s" % (fromfile,tofile,)
                        )
                        mytxt = "%s: %s => %s, %s" % (_("File move error"),fromfile,tofile,_("please report"),)
                        self.Entropy.updateProgress(
                            red("QA: ")+darkred(mytxt),
                            importance = 1,
                            type = "warning",
                            header = red(" !!! ")
                        )
                        return 4

                except IOError, e:
                    # try to move forward, sometimes packages might be
                    # fucked up and contain broken things
                    if e.errno != 2: raise

                items_installed.add(os.path.join(os.path.realpath(os.path.dirname(tofile)),os.path.basename(tofile)))
                if protected:
                    # add to disk cache
                    self.Entropy.FileUpdates.add_to_cache(tofile, quiet = True)

        # this is useful to avoid the removal of installed files by __remove_package just because
        # there's a difference in the directory path, perhaps, which is not handled correctly by
        # LocalRepository.contentDiff for obvious reasons (think about stuff in /usr/lib and /usr/lib64,
        # where the latter is just a symlink to the former)
        if self.infoDict.get('removecontent'):
            my_remove_content = set([x for x in self.infoDict['removecontent'] \
                if os.path.join(os.path.realpath(
                    os.path.dirname("%s%s" % (sys_root,x,))),os.path.basename(x)
                ) in items_installed])
            self.infoDict['removecontent'] -= my_remove_content

        return 0

    def _handle_config_protect(self, protect, mask, fromfile, tofile,
        do_allocation_check = True, do_quiet = False):

        protected = False
        tofile_before_protect = tofile
        do_continue = False
        in_mask = False

        try:
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

            if not os.path.lexists(tofile):
                protected = False # file doesn't exist

            # check if it's a text file
            if (protected) and os.path.isfile(tofile):
                protected = self.entropyTools.istextfile(tofile)
                in_mask = protected
            else:
                protected = False # it's not a file

            # request new tofile then
            if protected:
                client_settings = self.Entropy.SystemSettings['client']
                if tofile not in client_settings['configprotectskip']:
                    prot_status = True
                    if do_allocation_check:
                        tofile, prot_status = self.entropyTools.allocate_masked_file(tofile, fromfile)
                    if not prot_status:
                        protected = False
                    else:
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
                            mytxt = red("%s: %s") % (_("Protecting config file"),oldtofile,)
                            self.Entropy.updateProgress(
                                mytxt,
                                importance = 1,
                                type = "warning",
                                header = darkred("   ## ")
                            )
                else:
                    if not do_quiet:
                        self.Entropy.clientLog.log(
                            ETP_LOGPRI_INFO,
                            ETP_LOGLEVEL_NORMAL,
                            "Skipping config file installation/removal, as stated in client.conf: %s" % (tofile,)
                        )
                        mytxt = "%s: %s" % (_("Skipping file installation/removal"),tofile,)
                        self.Entropy.updateProgress(
                            mytxt,
                            importance = 1,
                            type = "warning",
                            header = darkred("   ## ")
                        )
                    do_continue = True

        except Exception, e:
            self.entropyTools.print_traceback()
            protected = False # safely revert to false
            tofile = tofile_before_protect
            mytxt = darkred("%s: %s") % (_("Cannot check CONFIG PROTECTION. Error"),e,)
            self.Entropy.updateProgress(
                red("QA: ")+mytxt,
                importance = 1,
                type = "warning",
                header = darkred("   ## ")
            )

        return in_mask, protected, tofile, do_continue


    def _handle_install_collision_protect(self, tofile, todbfile):
        avail = self.Entropy.clientDbconn.isFileAvailable(todbfile, get_id = True)
        if (self.infoDict['removeidpackage'] not in avail) and avail:
            mytxt = darkred(_("Collision found during install for"))
            mytxt += " %s - %s" % (blue(tofile),darkred(_("cannot overwrite")),)
            self.Entropy.updateProgress(
                red("QA: ")+mytxt,
                importance = 1,
                type = "warning",
                header = darkred("   ## ")
            )
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "WARNING!!! Collision found during install for %s - cannot overwrite" % (tofile,)
            )
            return False
        return True

    def sources_fetch_step(self):
        self.error_on_not_prepared()
        down_data = self.infoDict['download']
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
                if self.infoDict.get('fetch_path'):
                    dest_file = os.path.join(self.infoDict['fetch_path'],
                        file_name)
                else:
                    dest_file = os.path.join(self.infoDict['unpackdir'],
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
            mytxt = "%s: %s" % (blue(_("Downloading")),brown(url),)
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
                mytxt += red(self.entropyTools.spliturl(url)[1])
                mytxt += " %s %s/%s" % (_("at"),self.entropyTools.bytes_into_human(data_transfer),_("second"),)
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = red("   ## ")
                )
                self.Entropy.updateProgress(
                    "%s: %s" % (blue(_("Local path")),brown(dest_file),),
                    importance = 1,
                    type = "info",
                    header = red("      # ")
                )
            else:
                error_message = blue("%s: %s") % (
                    _("Error downloading from"),
                    red(self.entropyTools.spliturl(url)[1]),
                )
                # something bad happened
                if rc == -1:
                    error_message += " - %s." % (_("file not available on this mirror"),)
                elif rc == -3:
                    error_message += " - not found."
                elif rc == -100:
                    error_message += " - %s." % (_("discarded download"),)
                else:
                    error_message += " - %s: %s" % (_("unknown reason"),rc,)
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
        mytxt = "%s: %s" % (blue(_("Downloading archive")),red(os.path.basename(self.infoDict['download'])),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )

        rc = 0
        if not self.infoDict['verified']:
            rc = self.Entropy.fetch_file_on_mirrors(
                self.infoDict['repository'],
                self.Entropy.get_branch_from_download_relative_uri(self.infoDict['download']),
                self.infoDict['download'],
                self.infoDict['checksum'],
                fetch_abort_function = self.fetch_abort_function
            )
        if rc != 0:
            mytxt = "%s. %s: %s" % (
                red(_("Package cannot be fetched. Try to update repositories and retry")),
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
        m_fetch_len = len(self.infoDict['multi_fetch_list'])
        mytxt = "%s: %s %s" % (blue(_("Downloading")),darkred(str(m_fetch_len)),_("archives"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        # fetch_files_on_mirrors(self, download_list, checksum = False, fetch_abort_function = None)
        rc, err_list = self.Entropy.fetch_files_on_mirrors(
            self.infoDict['multi_fetch_list'],
            self.infoDict['checksum'],
            fetch_abort_function = self.fetch_abort_function
        )
        if rc != 0:
            mytxt = "%s. %s: %s" % (
                red(_("Some packages cannot be fetched. Try to update repositories and retry")),
                blue(_("Error")),
                rc,
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = darkred("   ## ")
            )
            for repo,branch,fname,cksum in err_list:
                self.Entropy.updateProgress(
                    "[%s:%s|%s] %s" % (blue(repo),brown(branch),
                        darkgreen(cksum),darkred(fname),),
                    importance = 1,
                    type = "error",
                    header = darkred("    # ")
                )
        return rc

    def fetch_not_available_step(self):
        self.Entropy.updateProgress(
            blue(_("Fetch for the chosen package is not available, unknown error.")),
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

        if not self.infoDict['merge_from']:
            mytxt = "%s: %s" % (blue(_("Unpacking package")),red(os.path.basename(self.infoDict['download'])),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = red("   ## ")
        )
        else:
            mytxt = "%s: %s" % (blue(_("Merging package")),red(os.path.basename(self.infoDict['atom'])),)
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
                errormsg = "%s. %s. %s: %s" % (
                    red(_("An error occured while trying to unpack the package")),
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
        mytxt = "%s: %s" % (blue(_("Installing package")),red(self.infoDict['atom']),)
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
        mytxt = "%s: %s" % (blue(_("Removing data")),red(self.infoDict['removeatom']),)
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
        mytxt = "%s: %s" % (blue(_("Cleaning")),red(self.infoDict['atom']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        self._cleanup_package(self.infoDict['unpackdir'])
        # we don't care if cleanupPackage fails since it's not critical
        return 0

    def logmessages_step(self):
        for msg in self.infoDict['messages']:
            self.Entropy.clientLog.write(">>>  "+msg)
        return 0

    def messages_step(self):
        self.error_on_not_prepared()
        # get messages
        if self.infoDict['messages']:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "Message from %s:" % (self.infoDict['atom'],)
            )
            mytxt = "%s:" % (darkgreen(_("Compilation messages")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "warning",
                header = brown("   ## ")
            )
        for msg in self.infoDict['messages']:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,msg)
            self.Entropy.updateProgress(
                msg,
                importance = 0,
                type = "warning",
                header = brown("   ## ")
            )
        if self.infoDict['messages']:
            self.Entropy.clientLog.log(ETP_LOGPRI_INFO,ETP_LOGLEVEL_NORMAL,"End message.")

    def postinstall_step(self):
        self.error_on_not_prepared()
        pkgdata = self.infoDict['triggers'].get('install')
        if pkgdata:
            trigger = self.Entropy.Triggers('postinstall',pkgdata, self.action)
            do = trigger.prepare()
            if do:
                trigger.run()
            trigger.kill()
        del pkgdata
        return 0

    def preinstall_step(self):
        self.error_on_not_prepared()
        pkgdata = self.infoDict['triggers'].get('install')
        if pkgdata:

            trigger = self.Entropy.Triggers('preinstall',pkgdata, self.action)
            do = trigger.prepare()
            if self.infoDict.get("diffremoval") and do:
                # diffremoval is true only when the
                # removal is triggered by a package install
                remdata = self.infoDict['triggers'].get('remove')
                if remdata:
                    r_trigger = self.Entropy.Triggers('preremove',remdata, self.action)
                    r_trigger.prepare()
                    r_trigger.triggers = [x for x in trigger.triggers if x not in r_trigger.triggers]
                    r_trigger.kill()
                del remdata
            if do:
                trigger.run()
            trigger.kill()

        del pkgdata
        return 0

    def preremove_step(self):
        self.error_on_not_prepared()
        remdata = self.infoDict['triggers'].get('remove')
        if remdata:
            trigger = self.Entropy.Triggers('preremove',remdata, self.action)
            do = trigger.prepare()
            if do:
                trigger.run()
                trigger.kill()
        del remdata
        return 0

    def postremove_step(self):
        self.error_on_not_prepared()
        remdata = self.infoDict['triggers'].get('remove')
        if remdata:

            trigger = self.Entropy.Triggers('postremove',remdata, self.action)
            do = trigger.prepare()
            if self.infoDict['diffremoval'] and (self.infoDict.get("atom") != None) and do:
                # diffremoval is true only when the remove action is triggered by installPackages()
                pkgdata = self.infoDict['triggers'].get('install')
                if pkgdata:
                    i_trigger = self.Entropy.Triggers('postinstall',pkgdata, self.action)
                    i_trigger.prepare()
                    i_trigger.triggers = [x for x in trigger.triggers if x not in i_trigger.triggers]
                    i_trigger.kill()
                del pkgdata
            if do:
                trigger.run()
            trigger.kill()

        del remdata
        return 0

    def removeconflict_step(self):
        self.error_on_not_prepared()
        for idpackage in self.infoDict['conflicts']:
            if not self.Entropy.clientDbconn.isIDPackageAvailable(idpackage):
                continue
            pkg = self.Entropy.Package()
            pkg.prepare((idpackage,),"remove_conflict", self.infoDict['remove_metaopts'])
            rc = pkg.run(xterm_header = self.xterm_title)
            pkg.kill()
            if rc != 0:
                return rc

        return 0

    def config_step(self):
        self.error_on_not_prepared()
        mytxt = "%s: %s" % (blue(_("Configuring package")),red(self.infoDict['atom']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = red("   ## ")
        )
        rc = self.__configure_package()
        if rc == 1:
            mytxt = "%s. %s. %s: %s" % (
                red(_("An error occured while trying to configure the package")),
                red(_("Make sure that your system is healthy")),
                blue(_("Error")),
                rc,
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = red("   ## ")
            )
        elif rc == 2:
            mytxt = "%s. %s. %s: %s" % (
                red(_("An error occured while trying to configure the package")),
                red(_("It seems that the Source Package Manager entry is missing")),
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

    def run_stepper(self, xterm_header):
        if xterm_header == None:
            xterm_header = ""

        if self.infoDict.has_key('remove_installed_vanished'):
            self.xterm_title += ' Installed package vanished'
            self.Entropy.setTitle(self.xterm_title)
            rc = self.vanished_step()
            return rc

        if self.infoDict.has_key('fetch_not_available'):
            self.xterm_title += ' Fetch not available'
            self.Entropy.setTitle(self.xterm_title)
            rc = self.fetch_not_available_step()
            return rc

        def do_fetch():
            self.xterm_title += ' %s: %s' % (_("Fetching"),os.path.basename(self.infoDict['download']),)
            self.Entropy.setTitle(self.xterm_title)
            return self.fetch_step()

        def do_multi_fetch():
            self.xterm_title += ' %s: %s %s' % (_("Multi Fetching"),
                len(self.infoDict['multi_fetch_list']),_("packages"),)
            self.Entropy.setTitle(self.xterm_title)
            return self.multi_fetch_step()

        def do_sources_fetch():
            self.xterm_title += ' %s: %s' % (_("Fetching sources"),os.path.basename(self.infoDict['atom']),)
            self.Entropy.setTitle(self.xterm_title)
            return self.sources_fetch_step()

        def do_checksum():
            self.xterm_title += ' %s: %s' % (_("Verifying"),os.path.basename(self.infoDict['download']),)
            self.Entropy.setTitle(self.xterm_title)
            return self.checksum_step()

        def do_multi_checksum():
            self.xterm_title += ' %s: %s %s' % (_("Multi Verification"),
                len(self.infoDict['multi_checksum_list']),_("packages"),)
            self.Entropy.setTitle(self.xterm_title)
            return self.multi_checksum_step()

        def do_unpack():
            if not self.infoDict['merge_from']:
                mytxt = _("Unpacking")
                self.xterm_title += ' %s: %s' % (mytxt,os.path.basename(self.infoDict['download']),)
            else:
                mytxt = _("Merging")
                self.xterm_title += ' %s: %s' % (mytxt,os.path.basename(self.infoDict['atom']),)
            self.Entropy.setTitle(self.xterm_title)
            return self.unpack_step()

        def do_remove_conflicts():
            return self.removeconflict_step()

        def do_install():
            self.xterm_title += ' %s: %s' % (_("Installing"),self.infoDict['atom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.install_step()

        def do_remove():
            self.xterm_title += ' %s: %s' % (_("Removing"),self.infoDict['removeatom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.remove_step()

        def do_showmessages():
            return self.messages_step()

        def do_logmessages():
            return self.logmessages_step()

        def do_cleanup():
            self.xterm_title += ' %s: %s' % (_("Cleaning"),self.infoDict['atom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.cleanup_step()

        def do_postinstall():
            self.xterm_title += ' %s: %s' % (_("Postinstall"),self.infoDict['atom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.postinstall_step()

        def do_preinstall():
            self.xterm_title += ' %s: %s' % (_("Preinstall"),self.infoDict['atom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.preinstall_step()

        def do_preremove():
            self.xterm_title += ' %s: %s' % (_("Preremove"),self.infoDict['removeatom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.preremove_step()

        def do_postremove():
            self.xterm_title += ' %s: %s' % (_("Postremove"),self.infoDict['removeatom'],)
            self.Entropy.setTitle(self.xterm_title)
            return self.postremove_step()

        def do_config():
            self.xterm_title += ' %s: %s' % (_("Configuring"),self.infoDict['atom'],)
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
            "showmessages": do_showmessages,
            "logmessages": do_logmessages,
            "cleanup": do_cleanup,
            "postinstall": do_postinstall,
            "preinstall": do_preinstall,
            "postremove": do_postremove,
            "preremove": do_preremove,
            "config": do_config,
        }

        rc = 0
        for step in self.infoDict['steps']:
            self.xterm_title = xterm_header
            rc = steps_data.get(step)()
            if rc != 0: break
        return rc


    '''
        @description: execute the requested steps
        @input xterm_header: purely optional
    '''
    def run(self, xterm_header = None):
        self.error_on_not_prepared()

        gave_up = self.Entropy.lock_check(self.Entropy._resources_run_check_lock)
        if gave_up:
            return 20

        locked = self.Entropy.application_lock_check()
        if locked:
            self.Entropy._resources_run_remove_lock()
            return 21

        # lock
        self.Entropy._resources_run_create_lock()

        try:
            rc = self.run_stepper(xterm_header)
        except:
            self.Entropy._resources_run_remove_lock()
            raise

        # remove lock
        self.Entropy._resources_run_remove_lock()

        if rc != 0:
            self.Entropy.updateProgress(
                blue(_("An error occured. Action aborted.")),
                importance = 2,
                type = "error",
                header = darkred("   ## ")
            )
        return rc

    '''
       Install/Removal process preparation function
       - will generate all the metadata needed to run the action steps, creating infoDict automatically
       @input matched_atom(tuple): is what is returned by EquoInstance.atom_match:
            (idpackage,repoid):
            (2000,u'sabayonlinux.org')
            NOTE: in case of remove action, matched_atom must be:
            (idpackage,)
            NOTE: in case of multi_fetch, matched_atom can be a list of matches
        @input action(string): is an action to take, which must be one in self.valid_actions
    '''
    def prepare(self, matched_atom, action, metaopts = {}):

        self.error_on_prepared()
        self.check_action_validity(action)

        self.action = action
        self.matched_atom = matched_atom
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
        elif self.action in ("remove","remove_conflict"):
            self.__generate_remove_metadata()
        elif self.action == "install":
            self.__generate_install_metadata()
        elif self.action == "source":
            self.__generate_fetch_metadata(sources = True)
        elif self.action == "config":
            self.__generate_config_metadata()
        self.prepared = True

    def __generate_remove_metadata(self):
        self.infoDict.clear()
        idpackage = self.matched_atom[0]

        if not self.Entropy.clientDbconn.isIDPackageAvailable(idpackage):
            self.infoDict['remove_installed_vanished'] = True
            return 0

        self.infoDict['configprotect_data'] = []
        self.infoDict['triggers'] = {}
        self.infoDict['removeatom'] = self.Entropy.clientDbconn.retrieveAtom(idpackage)
        self.infoDict['slot'] = self.Entropy.clientDbconn.retrieveSlot(idpackage)
        self.infoDict['versiontag'] = self.Entropy.clientDbconn.retrieveVersionTag(idpackage)
        self.infoDict['removeidpackage'] = idpackage
        self.infoDict['diffremoval'] = False
        removeConfig = False
        if self.metaopts.has_key('removeconfig'):
            removeConfig = self.metaopts.get('removeconfig')
        self.infoDict['removeconfig'] = removeConfig
        self.infoDict['removecontent'] = self.Entropy.clientDbconn.retrieveContent(idpackage)
        self.infoDict['triggers']['remove'] = self.Entropy.clientDbconn.getTriggerInfo(idpackage)
        self.infoDict['triggers']['remove']['removecontent'] = self.infoDict['removecontent']
        self.infoDict['steps'] = []
        self.infoDict['steps'].append("preremove")
        self.infoDict['steps'].append("remove")
        self.infoDict['steps'].append("postremove")

        return 0

    def __generate_config_metadata(self):
        self.infoDict.clear()
        idpackage = self.matched_atom[0]

        self.infoDict['atom'] = self.Entropy.clientDbconn.retrieveAtom(idpackage)
        key, slot = self.Entropy.clientDbconn.retrieveKeySlot(idpackage)
        self.infoDict['key'], self.infoDict['slot'] = key, slot
        self.infoDict['version'] = self.Entropy.clientDbconn.retrieveVersion(idpackage)
        self.infoDict['steps'] = []
        self.infoDict['steps'].append("config")

        return 0

    def __generate_install_metadata(self):
        self.infoDict.clear()

        idpackage, repository = self.matched_atom
        self.infoDict['idpackage'] = idpackage
        self.infoDict['repository'] = repository

        # fetch abort function
        if self.metaopts.has_key('fetch_abort_function'):
            self.fetch_abort_function = self.metaopts.pop('fetch_abort_function')

        install_source = etpConst['install_sources']['unknown']
        meta_inst_source = self.metaopts.get('install_source', install_source)
        if meta_inst_source in etpConst['install_sources'].values():
            install_source = meta_inst_source
        self.infoDict['install_source'] = install_source

        self.infoDict['configprotect_data'] = []
        dbconn = self.Entropy.open_repository(repository)
        self.infoDict['triggers'] = {}
        self.infoDict['atom'] = dbconn.retrieveAtom(idpackage)
        self.infoDict['slot'] = dbconn.retrieveSlot(idpackage)
        self.infoDict['version'], self.infoDict['versiontag'], self.infoDict['revision'] = dbconn.getVersioningData(idpackage)
        self.infoDict['category'] = dbconn.retrieveCategory(idpackage)
        self.infoDict['download'] = dbconn.retrieveDownloadURL(idpackage)
        self.infoDict['name'] = dbconn.retrieveName(idpackage)
        self.infoDict['messages'] = dbconn.retrieveMessages(idpackage)
        self.infoDict['checksum'] = dbconn.retrieveDigest(idpackage)
        self.infoDict['accept_license'] = dbconn.retrieveLicensedataKeys(idpackage)
        self.infoDict['conflicts'] = self.Entropy.get_match_conflicts(self.matched_atom)

        # fill action queue
        self.infoDict['removeidpackage'] = -1
        removeConfig = False
        if self.metaopts.has_key('removeconfig'):
            removeConfig = self.metaopts.get('removeconfig')

        self.infoDict['remove_metaopts'] = {
            'removeconfig': True,
        }
        if self.metaopts.has_key('remove_metaopts'):
            self.infoDict['remove_metaopts'] = self.metaopts.get('remove_metaopts')

        self.infoDict['merge_from'] = None
        mf = self.metaopts.get('merge_from')
        if mf != None:
            self.infoDict['merge_from'] = unicode(mf)
        self.infoDict['removeconfig'] = removeConfig

        pkgkey = self.entropyTools.dep_getkey(self.infoDict['atom'])
        inst_match = self.Entropy.clientDbconn.atomMatch(pkgkey, matchSlot = self.infoDict['slot'])
        inst_idpackage = -1
        if inst_match[1] == 0: inst_idpackage = inst_match[0]
        self.infoDict['removeidpackage'] = inst_idpackage

        if self.infoDict['removeidpackage'] != -1:
            avail = self.Entropy.clientDbconn.isIDPackageAvailable(self.infoDict['removeidpackage'])
            if avail:
                self.infoDict['removeatom'] = self.Entropy.clientDbconn.retrieveAtom(self.infoDict['removeidpackage'])
            else:
                self.infoDict['removeidpackage'] = -1

        # smartpackage ?
        self.infoDict['smartpackage'] = False
        # set unpack dir and image dir
        if self.infoDict['repository'].endswith(etpConst['packagesext']):
            # do arch check
            compiled_arch = dbconn.retrieveDownloadURL(idpackage)
            if compiled_arch.find("/"+etpSys['arch']+"/") == -1:
                self.infoDict.clear()
                self.prepared = False
                return -1
            self.infoDict['smartpackage'] = etpRepositories[self.infoDict['repository']]['smartpackage']
            self.infoDict['pkgpath'] = etpRepositories[self.infoDict['repository']]['pkgpath']
        else:
            self.infoDict['pkgpath'] = etpConst['entropyworkdir']+"/"+self.infoDict['download']
        self.infoDict['unpackdir'] = etpConst['entropyunpackdir']+"/"+self.infoDict['download']
        self.infoDict['imagedir'] = etpConst['entropyunpackdir']+"/"+self.infoDict['download']+"/"+etpConst['entropyimagerelativepath']

        # gentoo xpak data
        if etpConst['gentoo-compat']:
            self.infoDict['xpakpath'] = etpConst['entropyunpackdir']+"/"+self.infoDict['download']+"/"+etpConst['entropyxpakrelativepath']
            if not self.infoDict['merge_from']:
                self.infoDict['xpakstatus'] = None
                self.infoDict['xpakdir'] = self.infoDict['xpakpath']+"/"+etpConst['entropyxpakdatarelativepath']
            else:
                self.infoDict['xpakstatus'] = True
                portdbdir = 'var/db/pkg' # XXX hard coded ?
                portdbdir = os.path.join(self.infoDict['merge_from'],portdbdir)
                portdbdir = os.path.join(portdbdir,self.infoDict['category'])
                portdbdir = os.path.join(portdbdir,self.infoDict['name']+"-"+self.infoDict['version'])
                self.infoDict['xpakdir'] = portdbdir

        # compare both versions and if they match, disable removeidpackage
        if self.infoDict['removeidpackage'] != -1:
            installedVer, installedTag, installedRev = self.Entropy.clientDbconn.getVersioningData(self.infoDict['removeidpackage'])
            pkgcmp = self.entropyTools.entropy_compare_versions(
                (self.infoDict['version'], self.infoDict['versiontag'], self.infoDict['revision'],),
                (installedVer, installedTag, installedRev,)
            )
            if pkgcmp == 0:
                self.infoDict['removeidpackage'] = -1
            else:
                # differential remove list
                self.infoDict['diffremoval'] = True
                self.infoDict['removeatom'] = self.Entropy.clientDbconn.retrieveAtom(self.infoDict['removeidpackage'])
                self.infoDict['removecontent'] = self.Entropy.clientDbconn.contentDiff(
                        self.infoDict['removeidpackage'],
                        dbconn,
                        idpackage
                )
                self.infoDict['triggers']['remove'] = self.Entropy.clientDbconn.getTriggerInfo(
                        self.infoDict['removeidpackage']
                )
                self.infoDict['triggers']['remove']['removecontent'] = self.infoDict['removecontent']

        # set steps
        self.infoDict['steps'] = []
        if self.infoDict['conflicts']:
            self.infoDict['steps'].append("remove_conflicts")
        # install
        self.infoDict['steps'].append("unpack")
        # preinstall placed before preremove in order
        # to respect Spm order
        self.infoDict['steps'].append("preinstall")
        if (self.infoDict['removeidpackage'] != -1):
            self.infoDict['steps'].append("preremove")
        self.infoDict['steps'].append("install")
        if (self.infoDict['removeidpackage'] != -1):
            self.infoDict['steps'].append("postremove")
        self.infoDict['steps'].append("postinstall")
        if not etpConst['gentoo-compat']: # otherwise gentoo triggers will show that
            self.infoDict['steps'].append("showmessages")
        else:
            self.infoDict['steps'].append("logmessages")
        self.infoDict['steps'].append("cleanup")

        self.infoDict['triggers']['install'] = dbconn.getTriggerInfo(idpackage)
        self.infoDict['triggers']['install']['accept_license'] = self.infoDict['accept_license']
        self.infoDict['triggers']['install']['unpackdir'] = self.infoDict['unpackdir']
        self.infoDict['triggers']['install']['imagedir'] = self.infoDict['imagedir']
        if etpConst['gentoo-compat']:
            #self.infoDict['triggers']['install']['xpakpath'] = self.infoDict['xpakpath']
            self.infoDict['triggers']['install']['xpakdir'] = self.infoDict['xpakdir']

        return 0

    def __generate_fetch_metadata(self, sources = False):
        self.infoDict.clear()

        idpackage, repository = self.matched_atom
        dochecksum = True

        # fetch abort function
        if self.metaopts.has_key('fetch_abort_function'):
            self.fetch_abort_function = self.metaopts.pop('fetch_abort_function')

        if self.metaopts.has_key('dochecksum'):
            dochecksum = self.metaopts.get('dochecksum')

        # fetch_path is the path where data should be downloaded
        # at the moment is implemented only for sources = True
        if self.metaopts.has_key('fetch_path'):
            fetch_path = self.metaopts.get('fetch_path')
            if self.entropyTools.is_valid_path(fetch_path):
                self.infoDict['fetch_path'] = fetch_path

        self.infoDict['repository'] = repository
        self.infoDict['idpackage'] = idpackage
        dbconn = self.Entropy.open_repository(repository)
        self.infoDict['atom'] = dbconn.retrieveAtom(idpackage)
        if sources:
            self.infoDict['download'] = dbconn.retrieveSources(idpackage, extended = True)
        else:
            self.infoDict['checksum'] = dbconn.retrieveDigest(idpackage)
            self.infoDict['download'] = dbconn.retrieveDownloadURL(idpackage)

        if not self.infoDict['download']:
            self.infoDict['fetch_not_available'] = True
            return 0

        self.infoDict['verified'] = False
        self.infoDict['steps'] = []
        if not repository.endswith(etpConst['packagesext']) and not sources:
            if self.Entropy.check_needed_package_download(self.infoDict['download'], None) < 0:
                self.infoDict['steps'].append("fetch")
            if dochecksum:
                self.infoDict['steps'].append("checksum")
        elif sources:
            self.infoDict['steps'].append("sources_fetch")

        if sources:
            # create sources destination directory
            unpack_dir = etpConst['entropyunpackdir']+"/sources/"+self.infoDict['atom']
            self.infoDict['unpackdir'] = unpack_dir
            if os.path.lexists(unpack_dir):
                if os.path.isfile(unpack_dir):
                    os.remove(unpack_dir)
                elif os.path.isdir(unpack_dir):
                    shutil.rmtree(unpack_dir,True)
            if not os.path.lexists(unpack_dir):
                os.makedirs(unpack_dir,0775)
            const_setup_perms(unpack_dir,etpConst['entropygid'])

        else:
            # if file exists, first checksum then fetch
            if os.path.isfile(os.path.join(etpConst['entropyworkdir'],self.infoDict['download'])):
                # check size first
                repo_size = dbconn.retrieveSize(idpackage)
                f = open(os.path.join(etpConst['entropyworkdir'],self.infoDict['download']),"r")
                f.seek(0,2)
                disk_size = f.tell()
                f.close()
                if repo_size == disk_size:
                    self.infoDict['steps'].reverse()
        return 0

    def __generate_multi_fetch_metadata(self):
        self.infoDict.clear()

        if not isinstance(self.matched_atom,list):
            raise IncorrectParameter("IncorrectParameter: "
                "matched_atom must be a list of tuples, not %s" % (type(self.matched_atom,))
            )

        dochecksum = True

        # meta options
        if self.metaopts.has_key('fetch_abort_function'):
            self.fetch_abort_function = self.metaopts.pop('fetch_abort_function')
        if self.metaopts.has_key('dochecksum'):
            dochecksum = self.metaopts.get('dochecksum')
        self.infoDict['checksum'] = dochecksum

        matches = self.matched_atom
        self.infoDict['matches'] = matches
        self.infoDict['atoms'] = []
        self.infoDict['repository_atoms'] = {}
        temp_fetch_list = []
        temp_checksum_list = []
        temp_already_downloaded_count = 0
        etp_workdir = etpConst['entropyworkdir']
        for idpackage, repository in matches:
            if repository.endswith(etpConst['packagesext']): continue

            dbconn = self.Entropy.open_repository(repository)
            myatom = dbconn.retrieveAtom(idpackage)

            # general purpose metadata
            self.infoDict['atoms'].append(myatom)
            if not self.infoDict['repository_atoms'].has_key(repository):
                self.infoDict['repository_atoms'][repository] = set()
            self.infoDict['repository_atoms'][repository].add(myatom)

            download = dbconn.retrieveDownloadURL(idpackage)
            #branch = dbconn.retrieveBranch(idpackage)
            digest = dbconn.retrieveDigest(idpackage)
            repo_size = dbconn.retrieveSize(idpackage)
            orig_branch = self.Entropy.get_branch_from_download_relative_uri(download)
            if self.Entropy.check_needed_package_download(download, None) < 0:
                temp_fetch_list.append((repository, orig_branch, download, digest))
                continue
            elif dochecksum:
                temp_checksum_list.append((repository, orig_branch, download, digest))
            down_path = os.path.join(etp_workdir,download)
            if os.path.isfile(down_path):
                with open(down_path,"r") as f:
                    f.seek(0,2)
                    disk_size = f.tell()
                if repo_size == disk_size:
                    temp_already_downloaded_count += 1

        self.infoDict['steps'] = []
        self.infoDict['multi_fetch_list'] = temp_fetch_list
        self.infoDict['multi_checksum_list'] = temp_checksum_list
        if self.infoDict['multi_fetch_list']:
            self.infoDict['steps'].append("multi_fetch")
        if self.infoDict['multi_checksum_list']:
            self.infoDict['steps'].append("multi_checksum")
        if temp_already_downloaded_count == len(temp_checksum_list):
            self.infoDict['steps'].reverse()

        return 0
