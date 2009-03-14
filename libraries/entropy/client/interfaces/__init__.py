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
from entropy.core import Singleton
from entropy.output import TextInterface
from entropy.const import *
from entropy.exceptions import *
from entropy.i18n import _
from entropy.db import dbapi2
from entropy.client.interfaces.loaders import Loaders
from entropy.client.interfaces.cache import Cache
from entropy.client.interfaces.dep import Calculators
from entropy.client.interfaces.methods import Repository as CRepository, Misc, Match
from entropy.client.interfaces.fetch import Fetchers
from entropy.client.interfaces.metadata import Extractors

class Client(Singleton,TextInterface,Loaders,Cache,
        Calculators,CRepository,Misc,
        Match,Fetchers,Extractors):

    def init_singleton(self, indexing = True, noclientdb = 0,
            xcache = True, user_xcache = False, repo_validation = True,
            load_ugc = True, url_fetcher = None,
            multiple_url_fetcher = None):

        self.__instance_destroyed = False
        self.atomMatchCacheKey = etpCache['atomMatch']
        self.dbapi2 = dbapi2 # export for third parties
        self.FileUpdates = None
        self._package_match_validator_cache = {}
        self.validRepositories = []
        self.UGC = None
        # supporting external updateProgress stuff, you can point self.progress
        # to your progress bar and reimplement updateProgress
        self.progress = None
        self.clientDbconn = None
        self.safe_mode = 0
        self.indexing = indexing
        self.repo_validation = repo_validation
        self.noclientdb = False
        self.openclientdb = True

        # modules import
        import entropy.dump as dumpTools
        import entropy.tools as entropyTools
        self.dumpTools = dumpTools
        self.entropyTools = entropyTools
        from entropy.misc import LogFile
        self.clientLog = LogFile(level = etpConst['equologlevel'],
            filename = etpConst['equologfile'], header = "[client]")

        self.MultipleUrlFetcher = multiple_url_fetcher
        self.urlFetcher = url_fetcher
        if self.urlFetcher == None:
            from entropy.transceivers import urlFetcher
            self.urlFetcher = urlFetcher
        if self.MultipleUrlFetcher == None:
            from entropy.transceivers import MultipleUrlFetcher
            self.MultipleUrlFetcher = MultipleUrlFetcher

        from entropy.cache import EntropyCacher
        self.Cacher = EntropyCacher()

        from entropy.client.misc import FileUpdates
        self.FileUpdates = FileUpdates(self)

        from entropy.client.mirrors import StatusInterface
        # mirror status interface
        self.MirrorStatus = StatusInterface()

        from entropy.core import SystemSettings
        # setup package settings (masking and other stuff)
        self.SystemSettings = SystemSettings(self)

        # load User Generated Content Interface
        if load_ugc:
            from entropy.client.services.ugc.interfaces import Client as ugcClient
            self.UGC = ugcClient(self)

        # class init
        Loaders.__init__(self, self)
        Cache.__init__(self, self)
        Calculators.__init__(self, self)
        CRepository.__init__(self, self)
        Misc.__init__(self, self)
        Match.__init__(self, self)
        Fetchers.__init__(self, self)
        Extractors.__init__(self, self)

        if noclientdb in (False,0):
            self.noclientdb = False
        elif noclientdb in (True,1):
            self.noclientdb = True
        elif noclientdb == 2:
            self.noclientdb = True
            self.openclientdb = False
        self.xcache = xcache
        shell_xcache = os.getenv("ETP_NOCACHE")
        if shell_xcache:
            self.xcache = False

        do_validate_repo_cache = False
        # now if we are on live, we should disable it
        # are we running on a livecd? (/proc/cmdline has "cdroot")
        if self.entropyTools.islive():
            self.xcache = False
        elif (not self.entropyTools.is_user_in_entropy_group()) and not user_xcache:
            self.xcache = False
        elif not user_xcache:
            do_validate_repo_cache = True

        if not self.xcache and (self.entropyTools.is_user_in_entropy_group()):
            try: self.purge_cache(False)
            except: pass

        if self.openclientdb:
            self.open_client_repository()

        # needs to be started here otherwise repository cache will be
        # always dropped
        if self.xcache:
            self.Cacher.start()

        if do_validate_repo_cache:
            self.validate_repositories_cache()
        if self.repo_validation:
            self.validate_repositories()

    def destroy(self):
        self.__instance_destroyed = True
        if hasattr(self,'clientDbconn'):
            if self.clientDbconn != None:
                self.clientDbconn.closeDB()
                del self.clientDbconn
        if hasattr(self,'FileUpdates'):
            del self.FileUpdates
        if hasattr(self,'clientLog'):
            self.clientLog.close()
        if hasattr(self,'Cacher'):
            self.Cacher.stop()
        if hasattr(self,'SystemSettings'):
            if hasattr(self.SystemSettings,'destroy'):
                self.SystemSettings.destroy()

        self.close_all_repositories(mask_clear = False)
        self.closeAllSecurity()
        self.closeAllQA()

    def is_destroyed(self):
        return self.__instance_destroyed

    def __del__(self):
        self.destroy()


class Trigger:

    import entropy.tools as entropyTools
    def __init__(self, EquoInstance, phase, pkgdata, package_action = None):

        if not isinstance(EquoInstance,Client):
            mytxt = _("A valid Entropy Instance is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        self.Entropy = EquoInstance
        self.clientLog = self.Entropy.clientLog
        self.validPhases = ("preinstall","postinstall","preremove","postremove")
        self.pkgdata = pkgdata
        self.prepared = False
        self.triggers = set()
        self.gentoo_compat = etpConst['gentoo-compat']
	self.package_action = package_action

        '''
        @ description: Gentoo toolchain variables
        '''
        self.MODULEDB_DIR="/var/lib/module-rebuild/"
        self.INITSERVICES_DIR="/var/lib/init.d/"

        ''' portage stuff '''
        if self.gentoo_compat:
            try:
                Spm = self.Entropy.Spm()
                self.Spm = Spm
            except Exception, e:
                self.entropyTools.printTraceback()
                mytxt = darkred("%s, %s: %s, %s !") % (
                    _("Portage interface can't be loaded"),
                    _("Error"),
                    e,
                    _("please fix"),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = bold(" !!! ")
                )
                self.gentoo_compat = False

        self.phase = phase
        # validate phase
        self.phaseValidation()

    def phaseValidation(self):
        if self.phase not in self.validPhases:
            mytxt = "%s: %s" % (_("Valid phases"),self.validPhases,)
            raise InvalidData("InvalidData: %s" % (mytxt,))

    def prepare(self):
        func = getattr(self,self.phase)
        self.triggers = func()
        remove = set()
        for trigger in self.triggers:
            if trigger in etpUi[self.phase+'_triggers_disable']:
                remove.add(trigger)
        self.triggers = [x for x in self.triggers if x not in remove]
        del remove
        self.prepared = True

    def run(self):
        for trigger in self.triggers:
            fname = 'trigger_%s' % (trigger,)
            if not hasattr(self,fname): continue
            getattr(self,fname)()

    def kill(self):
        self.prepared = False
        del self.triggers[:]

    def postinstall(self):

        functions = []
        # Gentoo hook
        if self.gentoo_compat:
            functions.append('ebuild_postinstall')

        # equo purge cache
        if self.pkgdata['category']+"/"+self.pkgdata['name'] == "sys-apps/entropy":
            functions.append("purgecache")

        # binutils configuration
        if self.pkgdata['category']+"/"+self.pkgdata['name'] == "sys-devel/binutils":
            functions.append("binutilsswitch")

        # opengl configuration
        if (self.pkgdata['category'] == "x11-drivers") and \
            (self.pkgdata['name'].startswith("nvidia-") or \
            self.pkgdata['name'].startswith("ati-")):
                if "ebuild_postinstall" in functions:
                    # disabling gentoo postinstall since we reimplemented it
                    functions.remove("ebuild_postinstall")
                functions.append("openglsetup")

        # load linker paths
        ldpaths = self.Entropy.entropyTools.collectLinkerPaths()
        for x in self.pkgdata['content']:

            if (x.startswith("/etc/conf.d") or \
                x.startswith("/etc/init.d")) and \
                ("conftouch" not in functions):
                    functions.append('conftouch')

            if x.startswith('/lib/modules/') and ("kernelmod" not in functions):
                if "ebuild_postinstall" in functions:
                    # disabling gentoo postinstall since we reimplemented it
                    functions.remove("ebuild_postinstall")
                functions.append('kernelmod')

            if x.startswith('/boot/kernel-') and ("addbootablekernel" not in functions):
                functions.append('addbootablekernel')

            if x.startswith('/usr/src/') and ("createkernelsym" not in functions):
                functions.append('createkernelsym')

            if x.startswith('/etc/env.d/') and ("env_update" not in functions):
                functions.append('env_update')

            if (os.path.dirname(x) in ldpaths) and ("run_ldconfig" not in functions):
                if x.find(".so") > -1:
                    functions.append('run_ldconfig')

        if self.pkgdata['trigger']:
            functions.append('call_ext_postinstall')

        del ldpaths
        return functions

    def preinstall(self):

        functions = []

        # Gentoo hook
        if self.gentoo_compat:
            functions.append('ebuild_preinstall')

        for x in self.pkgdata['content']:
            if x.startswith("/etc/init.d/") and ("initinform" not in functions):
                functions.append('initinform')
            if x.startswith("/boot") and ("mountboot" not in functions):
                functions.append('mountboot')

        if self.pkgdata['trigger']:
            functions.append('call_ext_preinstall')

        return functions

    def postremove(self):

        functions = []

        # load linker paths
        ldpaths = self.Entropy.entropyTools.collectLinkerPaths()

        for x in self.pkgdata['removecontent']:
            if x.startswith('/boot/kernel-') and ("removebootablekernel" not in functions):
                functions.append('removebootablekernel')
            if x.startswith('/etc/init.d/') and ("initdisable" not in functions):
                functions.append('initdisable')
            if x.endswith('.py') and ("cleanpy" not in functions):
                functions.append('cleanpy')
            if x.startswith('/etc/env.d/') and ("env_update" not in functions):
                functions.append('env_update')
            if (os.path.dirname(x) in ldpaths) and ("run_ldconfig" not in functions):
                if x.find(".so") > -1:
                    functions.append('run_ldconfig')

        if self.pkgdata['trigger']:
            functions.append('call_ext_postremove')

        del ldpaths
        return functions


    def preremove(self):

        functions = []

        # Gentoo hook
        if self.gentoo_compat:
            functions.append('ebuild_preremove')
            functions.append('ebuild_postremove')
            # doing here because we need /var/db/pkg stuff in place and also because doesn't make any difference

        # opengl configuration
        if (self.pkgdata['category'] == "x11-drivers") and (self.pkgdata['name'].startswith("nvidia-") or self.pkgdata['name'].startswith("ati-")):
            if "ebuild_preremove" in functions:
                functions.remove("ebuild_preremove")
            if "ebuild_postremove" in functions:
                # disabling gentoo postinstall since we reimplemented it
                functions.remove("ebuild_postremove")
            if self.package_action not in ["remove_conflict"]:
                functions.append("openglsetup_xorg")

        for x in self.pkgdata['removecontent']:
            if x.startswith("/boot"):
                functions.append('mountboot')
                break

        if self.pkgdata['trigger']:
            functions.append('call_ext_preremove')

        return functions


    '''
        Real triggers
    '''
    def trigger_call_ext_preinstall(self):
        return self.trigger_call_ext_generic()

    def trigger_call_ext_postinstall(self):
        return self.trigger_call_ext_generic()

    def trigger_call_ext_preremove(self):
        return self.trigger_call_ext_generic()

    def trigger_call_ext_postremove(self):
        return self.trigger_call_ext_generic()

    def trigger_call_ext_generic(self):
        try:
            return self.do_trigger_call_ext_generic()
        except Exception, e:
            mykey = self.pkgdata['category']+"/"+self.pkgdata['name']
            tb = self.entropyTools.getTraceback()
            self.Entropy.updateProgress(tb, importance = 0, type = "error")
            self.Entropy.clientLog.write(tb)
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] ATTENTION Cannot run External trigger for "+mykey+"!! "+str(Exception)+": "+str(e)
            )
            mytxt = "%s: %s %s. %s." % (
                bold(_("QA")),
                brown(_("Cannot run External trigger for")),
                bold(mykey),
                brown(_("Please report it")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return 0

    class EntropyShSandbox:

        def __env_setup(self, stage, pkgdata):

            # mandatory variables
            category = pkgdata.get('category')
            if isinstance(category,unicode):
                category = category.encode('utf-8')

            pn = pkgdata.get('name')
            if isinstance(pn,unicode):
                pn = pn.encode('utf-8')

            pv = pkgdata.get('version')
            if isinstance(pv,unicode):
                pv = pv.encode('utf-8')

            pr = self.entropyTools.dep_get_portage_revision(pv)
            pvr = pv
            if pr == "r0": pvr += "-%s" % (pr,)

            pet = pkgdata.get('versiontag')
            if isinstance(pet,unicode):
                pet = pet.encode('utf-8')

            per = pkgdata.get('revision')
            if isinstance(per,unicode):
                per = per.encode('utf-8')

            etp_branch = pgkdata.get('branch')
            if isinstance(etp_branch,unicode):
                etp_branch = etp_branch.encode('utf-8')

            slot = pgkdata.get('slot')
            if isinstance(slot,unicode):
                slot = slot.encode('utf-8')

            pkgatom = pkgdata.get('atom')
            pkgkey = self.entropyTools.dep_getkey(pkgatom)
            pvrte = pkgatom[len(pkgkey)+1:]
            if isinstance(pvrte,unicode):
                pvrte = pvrte.encode('utf-8')

            etpapi = pkgdata.get('etpapi')
            if isinstance(etpapi,unicode):
                etpapi = etpapi.encode('utf-8')

            p = pkgatom
            if isinstance(p,unicode):
                p = p.encode('utf-8')

            chost, cflags, cxxflags = pkgdata.get('chost'), pkgdata.get('cflags'), pkgdata.get('cxxflags')

            chost = pkgdata.get('etpapi')
            if isinstance(chost,unicode):
                chost = chost.encode('utf-8')

            cflags = pkgdata.get('etpapi')
            if isinstance(cflags,unicode):
                cflags = cflags.encode('utf-8')

            cxxflags = pkgdata.get('etpapi')
            if isinstance(cxxflags,unicode):
                cxxflags = cxxflags.encode('utf-8')

            # Not mandatory variables

            eclasses = ' '.join(pkgdata.get('eclasses',[]))
            if isinstance(eclasses,unicode):
                eclasses = eclasses.encode('utf-8')

            unpackdir = pkgdata.get('unpackdir','')
            if isinstance(unpackdir,unicode):
                unpackdir = unpackdir.encode('utf-8')

            imagedir = pkgdata.get('imagedir','')
            if isinstance(imagedir,unicode):
                imagedir = imagedir.encode('utf-8')

            sb_dirs = [unpackdir,imagedir]
            sb_write = ':'.join(sb_dirs)

            myenv = {
                "ETP_API": etpSys['api'],
                "ETP_LOG": self.Entropy.clientLog.get_fpath(),
                "ETP_STAGE": stage, # entropy trigger stage
                "ETP_PHASE": self.__get_sh_stage(), # entropy trigger phase
                "ETP_BRANCH": etp_branch,
                "CATEGORY": category, # package category
                "PN": pn, # package name
                "PV": pv, # package version
                "PR": pr, # package revision (portage)
                "PVR": pvr, # package version+revision
                "PVRTE": pvrte, # package version+revision+entropy tag+entropy rev
                "PER": per, # package entropy revision
                "PET": pet, # package entropy tag
                "SLOT": slot, # package slot
                "PAPI": etpapi, # package entropy api
                "P": p, # complete package atom
                "WORKDIR": unpackdir, # temporary package workdir
                "B": unpackdir, # unpacked binary package directory?
                "D": imagedir, # package unpack destination (before merging to live)
                "ENTROPY_TMPDIR": etpConst['packagestmpdir'], # entropy temporary directory
                "CFLAGS": cflags, # compile flags
                "CXXFLAGS": cxxflags, # compile flags
                "CHOST": chost, # *nix CHOST
                "PORTAGE_ECLASSES": eclasses, # portage eclasses, " " separated
                "ROOT": etpConst['systemroot'],
                "SANDBOX_WRITE": sb_write,
            }
            sysenv = os.environ.copy()
            sysenv.update(myenv)
            return sysenv

        def __get_sh_stage(self, stage):
            mydict = {
                "preinstall": "pkg_preinst",
                "postinstall": "pkg_postinst",
                "preremove": "pkg_prerm",
                "postremove": "pkg_postrm",
            }
            return mydict.get(stage)

        def run(self, stage, pkgdata, trigger_file):
            env = self.__env_setup(stage, pkgdata)
            p = subprocess.Popen([trigger_file, stage],
                stdout = sys.stdout, stderr = sys.stderr,
                env = env
            )
            rc = p.wait()
            if os.path.isfile(trigger_file):
                os.remove(trigger_file)
            return rc

    class EntropyPySandbox:

        def run(self, stage, pkgdata, trigger_file):
            my_ext_status = 1
            if os.path.isfile(trigger_file):
                execfile(trigger_file)
            if os.path.isfile(trigger_file):
                os.remove(trigger_file)
            return my_ext_status

    def do_trigger_call_ext_generic(self):

        # if mute, supress portage output
        if etpUi['mute']:
            oldsystderr = sys.stderr
            oldsysstdout = sys.stdout
            stdfile = open("/dev/null","w")
            sys.stdout = stdfile
            sys.stderr = stdfile

        tg_pfx = "%s/trigger-" % (etpConst['entropyunpackdir'],)
        while 1:
            triggerfile = "%s%s" % (tg_pfx,self.Entropy.entropyTools.getRandomNumber(),)
            if not os.path.isfile(triggerfile): break

        triggerdir = os.path.dirname(triggerfile)
        if not os.path.isdir(triggerdir):
            os.makedirs(triggerdir)

        f = open(triggerfile,"w")
        chunk = 1024
        start = 0
        while 1:
            buf = self.pkgdata['trigger'][start:]
            if not buf: break
            f.write(buf)
            start += chunk
        f.flush()
        f.close()

        # if mute, restore old stdout/stderr
        if etpUi['mute']:
            sys.stderr = oldsystderr
            sys.stdout = oldsysstdout
            stdfile.close()

        f = open(triggerfile,"r")
        interpreter = f.readline().strip()
        f.close()
        entropy_sh = etpConst['trigger_sh_interpreter']
        if interpreter == "#!%s" % (entropy_sh,):
            os.chmod(triggerfile,0775)
            my = self.EntropyShSandbox()
        else:
            my = self.EntropyPySandbox()
        return my.run(self.phase, self.pkgdata, triggerfile)


    def trigger_purgecache(self):
        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "[POST] Purging Entropy cache..."
        )

        mytxt = "%s: %s." % (_("Please remember"),_("It is always better to leave Entropy updates isolated"),)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        mytxt = "%s ..." % (_("Purging Entropy cache"),)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        self.Entropy.purge_cache(False)

    def trigger_conftouch(self):
        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "[POST] Updating {conf.d,init.d} mtime..."
        )
        mytxt = "%s ..." % (_("Updating {conf.d,init.d} mtime"),)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        for item in self.pkgdata['content']:
            if not (item.startswith("/etc/conf.d") or item.startswith("/etc/conf.d")):
                continue
            if not os.path.isfile(item):
                continue
            if not os.access(item,os.W_OK):
                continue
            try:
                f = open(item,"abw")
                f.flush()
                f.close()
            except (OSError,IOError,):
                pass

    def trigger_binutilsswitch(self):
        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "[POST] Configuring Binutils Profile..."
        )
        mytxt = "%s ..." % (_("Configuring Binutils Profile"),)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        # get binutils profile
        pkgsplit = self.Entropy.entropyTools.catpkgsplit(
            self.pkgdata['category'] + "/" + self.pkgdata['name'] + "-" + self.pkgdata['version']
        )
        profile = self.pkgdata['chost']+"-"+pkgsplit[2]
        self.trigger_set_binutils_profile(profile)

    def trigger_kernelmod(self):
        if self.pkgdata['category'] != "sys-kernel":
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Updating moduledb..."
            )
            mytxt = "%s ..." % (_("Updating moduledb"),)
            self.Entropy.updateProgress(
                brown(mytxt),
                importance = 0,
                header = red("   ## ")
            )
            item = 'a:1:'+self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
            self.trigger_update_moduledb(item)
        mytxt = "%s ..." % (_("Running depmod"),)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        # get kernel modules dir name
        name = ''
        for item in self.pkgdata['content']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/lib/modules/"):
                name = item[len(etpConst['systemroot']):]
                name = name.split("/")[3]
                break
        if name:
            self.trigger_run_depmod(name)

    def trigger_initdisable(self):
        for item in self.pkgdata['removecontent']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/etc/init.d/") and os.path.isfile(item):
                myroot = "/"
                if etpConst['systemroot']:
                    myroot = etpConst['systemroot']+"/"
                runlevels_dir = etpConst['systemroot']+"/etc/runlevels"
                runlevels = []
                if os.path.isdir(runlevels_dir) and os.access(runlevels_dir,os.R_OK):
                    runlevels = [x for x in os.listdir(runlevels_dir) \
                        if os.path.isdir(os.path.join(runlevels_dir,x)) \
                        and os.path.isfile(os.path.join(runlevels_dir,x,os.path.basename(item)))
                    ]
                for runlevel in runlevels:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[POST] Removing boot service: %s, runlevel: %s" % (os.path.basename(item),runlevel,)
                    )
                    mytxt = "%s: %s : %s" % (brown(_("Removing boot service")),os.path.basename(item),runlevel,)
                    self.Entropy.updateProgress(
                        mytxt,
                        importance = 0,
                        header = red("   ## ")
                    )
                    cmd = 'ROOT="%s" rc-update del %s %s' % (myroot, os.path.basename(item), runlevel)
                    subprocess.call(cmd, shell = True)

    def trigger_initinform(self):
        for item in self.pkgdata['content']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/etc/init.d/") and not os.path.isfile(etpConst['systemroot']+item):
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] A new service will be installed: %s" % (item,)
                )
                mytxt = "%s: %s" % (brown(_("A new service will be installed")),item,)
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )

    def trigger_openglsetup(self):
        opengl = "xorg-x11"
        if self.pkgdata['name'] == "nvidia-drivers":
            opengl = "nvidia"
        elif self.pkgdata['name'] == "ati-drivers":
            opengl = "ati"
        # is there eselect ?
        eselect = subprocess.call("eselect opengl &> /dev/null", shell = True)
        if eselect == 0:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Reconfiguring OpenGL to %s ..." % (opengl,)
            )
            mytxt = "%s ..." % (brown(_("Reconfiguring OpenGL")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            quietstring = ''
            if etpUi['quiet']: quietstring = " &>/dev/null"
            if etpConst['systemroot']:
                subprocess.call('echo "eselect opengl set --use-old %s" | chroot %s %s' % (opengl,etpConst['systemroot'],quietstring,), shell = True)
            else:
                subprocess.call('eselect opengl set --use-old %s %s' % (opengl,quietstring,), shell = True)
        else:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Eselect NOT found, cannot run OpenGL trigger"
            )
            mytxt = "%s !" % (brown(_("Eselect NOT found, cannot run OpenGL trigger")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ##")
            )

    def trigger_openglsetup_xorg(self):
        eselect = subprocess.call("eselect opengl &> /dev/null", shell = True)
        if eselect == 0:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Reconfiguring OpenGL to fallback xorg-x11 ..."
            )
            mytxt = "%s ..." % (brown(_("Reconfiguring OpenGL")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            quietstring = ''
            if etpUi['quiet']: quietstring = " &>/dev/null"
            if etpConst['systemroot']:
                subprocess.call('echo "eselect opengl set xorg-x11" | chroot %s %s' % (etpConst['systemroot'],quietstring,), shell = True)
            else:
                subprocess.call('eselect opengl set xorg-x11 %s' % (quietstring,), shell = True)
        else:
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Eselect NOT found, cannot run OpenGL trigger"
            )
            mytxt = "%s !" % (brown(_("Eselect NOT found, cannot run OpenGL trigger")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ##")
            )

    # FIXME: this only supports grub (no lilo support)
    def trigger_addbootablekernel(self):
        boot_mount = False
        if os.path.ismount("/boot"):
            boot_mount = True
        kernels = [x for x in self.pkgdata['content'] if x.startswith("/boot/kernel-")]
        if boot_mount:
            kernels = [x[len("/boot"):] for x in kernels]
        for kernel in kernels:
            mykernel = kernel.split('/kernel-')[1]
            initramfs = "/boot/initramfs-"+mykernel
            if initramfs not in self.pkgdata['content']:
                initramfs = ''
            elif boot_mount:
                initramfs = initramfs[len("/boot"):]

            # configure GRUB
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Configuring GRUB bootloader. Adding the new kernel..."
            )
            mytxt = "%s. %s ..." % (
                _("Configuring GRUB bootloader"),
                _("Adding the new kernel"),
            )
            self.Entropy.updateProgress(
                brown(mytxt),
                importance = 0,
                header = red("   ## ")
            )
            self.trigger_configure_boot_grub(kernel,initramfs)

    # FIXME: this only supports grub (no lilo support)
    def trigger_removebootablekernel(self):
        kernels = [x for x in self.pkgdata['content'] if x.startswith("/boot/kernel-")]
        for kernel in kernels:
            initramfs = "/boot/initramfs-"+kernel[13:]
            if initramfs not in self.pkgdata['content']:
                initramfs = ''
            # configure GRUB
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] Configuring GRUB bootloader. Removing the selected kernel..."
            )
            mytxt = "%s. %s ..." % (
                _("Configuring GRUB bootloader"),
                _("Removing the selected kernel"),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            self.trigger_remove_boot_grub(kernel,initramfs)

    def trigger_mountboot(self):
        # is in fstab?
        if etpConst['systemroot']:
            return
        if os.path.isfile("/etc/fstab"):
            f = open("/etc/fstab","r")
            fstab = f.readlines()
            fstab = self.Entropy.entropyTools.listToUtf8(fstab)
            f.close()
            for line in fstab:
                fsline = line.split()
                if len(fsline) > 1:
                    if fsline[1] == "/boot":
                        if not os.path.ismount("/boot"):
                            # trigger mount /boot
                            rc = subprocess.call("mount /boot &> /dev/null", shell = True)
                            if rc == 0:
                                self.Entropy.clientLog.log(
                                    ETP_LOGPRI_INFO,
                                    ETP_LOGLEVEL_NORMAL,
                                    "[PRE] Mounted /boot successfully"
                                )
                                self.Entropy.updateProgress(
                                    brown(_("Mounted /boot successfully")),
                                    importance = 0,
                                    header = red("   ## ")
                                )
                            elif rc != 8192: # already mounted
                                self.Entropy.clientLog.log(
                                    ETP_LOGPRI_INFO,
                                    ETP_LOGLEVEL_NORMAL,
                                    "[PRE] Cannot mount /boot automatically !!"
                                )
                                self.Entropy.updateProgress(
                                    brown(_("Cannot mount /boot automatically !!")),
                                    importance = 0,
                                    header = red("   ## ")
                                )
                            break

    def trigger_cleanpy(self):
        pyfiles = [x for x in self.pkgdata['content'] if x.endswith(".py")]
        for item in pyfiles:
            item = etpConst['systemroot']+item
            if os.path.isfile(item+"o"):
                try: os.remove(item+"o")
                except OSError: pass
            if os.path.isfile(item+"c"):
                try: os.remove(item+"c")
                except OSError: pass

    def trigger_createkernelsym(self):
        for item in self.pkgdata['content']:
            item = etpConst['systemroot']+item
            if item.startswith(etpConst['systemroot']+"/usr/src/"):
                # extract directory
                try:
                    todir = item[len(etpConst['systemroot']):]
                    todir = todir.split("/")[3]
                except:
                    continue
                if os.path.isdir(etpConst['systemroot']+"/usr/src/"+todir):
                    # link to /usr/src/linux
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[POST] Creating kernel symlink "+etpConst['systemroot']+"/usr/src/linux for /usr/src/"+todir
                    )
                    mytxt = "%s %s %s %s" % (
                        _("Creating kernel symlink"),
                        etpConst['systemroot']+"/usr/src/linux",
                        _("for"),
                        "/usr/src/"+todir,
                    )
                    self.Entropy.updateProgress(
                        brown(mytxt),
                        importance = 0,
                        header = red("   ## ")
                    )
                    if os.path.isfile(etpConst['systemroot']+"/usr/src/linux") or \
                        os.path.islink(etpConst['systemroot']+"/usr/src/linux"):
                            os.remove(etpConst['systemroot']+"/usr/src/linux")
                    if os.path.isdir(etpConst['systemroot']+"/usr/src/linux"):
                        mydir = etpConst['systemroot']+"/usr/src/linux."+str(self.Entropy.entropyTools.getRandomNumber())
                        while os.path.isdir(mydir):
                            mydir = etpConst['systemroot']+"/usr/src/linux."+str(self.Entropy.entropyTools.getRandomNumber())
                        shutil.move(etpConst['systemroot']+"/usr/src/linux",mydir)
                    try:
                        os.symlink(todir,etpConst['systemroot']+"/usr/src/linux")
                    except OSError: # not important in the end
                        pass
                    break

    def trigger_run_ldconfig(self):
        if not etpConst['systemroot']:
            myroot = "/"
        else:
            myroot = etpConst['systemroot']+"/"
        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "[POST] Running ldconfig"
        )
        mytxt = "%s %s" % (_("Regenerating"),"/etc/ld.so.cache",)
        self.Entropy.updateProgress(
            brown(mytxt),
            importance = 0,
            header = red("   ## ")
        )
        subprocess.call("ldconfig -r %s &> /dev/null" % (myroot,), shell = True)

    def trigger_env_update(self):

        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "[POST] Running env-update"
        )
        if os.access(etpConst['systemroot']+"/usr/sbin/env-update",os.X_OK):
            mytxt = "%s ..." % (_("Updating environment"),)
            self.Entropy.updateProgress(
                brown(mytxt),
                importance = 0,
                header = red("   ## ")
            )
            if etpConst['systemroot']:
                subprocess.call("echo 'env-update --no-ldconfig' | chroot %s &> /dev/null" % (etpConst['systemroot'],), shell = True)
            else:
                subprocess.call('env-update --no-ldconfig &> /dev/null', shell = True)

    def trigger_ebuild_postinstall(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        oldstdout = sys.stdout
        sys.stderr = stdfile

        myebuild = [self.pkgdata['xpakdir']+"/"+x for x in os.listdir(self.pkgdata['xpakdir']) if x.endswith(etpConst['spm']['source_build_ext'])]
        if myebuild:
            myebuild = myebuild[0]
            portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
            self.Entropy.updateProgress(
                brown("Ebuild: pkg_postinst()"),
                importance = 0,
                header = red("   ## ")
            )
            try:

                if not os.path.isfile(self.pkgdata['unpackdir']+"/portage/"+portage_atom+"/temp/environment"):
                    # if environment is not yet created, we need to run pkg_setup()
                    sys.stdout = stdfile
                    rc = self.Spm.spm_doebuild(
                        myebuild,
                        mydo = "setup",
                        tree = "bintree",
                        cpv = portage_atom,
                        portage_tmpdir = self.pkgdata['unpackdir'],
                        licenses = self.pkgdata['accept_license']
                    )
                    if rc == 1:
                        self.Entropy.clientLog.log(
                            ETP_LOGPRI_INFO,
                            ETP_LOGLEVEL_NORMAL,
                            "[POST] ATTENTION Cannot properly run Gentoo postinstall (pkg_setup())"
                            " trigger for "+str(portage_atom)+". Something bad happened."
                        )
                    sys.stdout = oldstdout

                rc = self.Spm.spm_doebuild(
                    myebuild,
                    mydo = "postinst",
                    tree = "bintree",
                    cpv = portage_atom,
                    portage_tmpdir = self.pkgdata['unpackdir'],
                    licenses = self.pkgdata['accept_license']
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[POST] ATTENTION Cannot properly run Gentoo postinstall (pkg_postinst()) trigger for " + \
                        str(portage_atom) + ". Something bad happened."
                        )

            except Exception, e:
                sys.stdout = oldstdout
                self.entropyTools.printTraceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[POST] ATTENTION Cannot run Portage trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Portage trigger for")),
                    bold(str(portage_atom)),
                    brown(_("Please report it")),
                    bold(_("Attach this")),
                    darkred(etpConst['spmlogfile']),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
        sys.stderr = oldstderr
        sys.stdout = oldstdout
        stdfile.close()
        return 0

    def trigger_ebuild_preinstall(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        oldstdout = sys.stdout
        sys.stderr = stdfile

        myebuild = [self.pkgdata['xpakdir']+"/"+x for x in os.listdir(self.pkgdata['xpakdir']) if x.endswith(etpConst['spm']['source_build_ext'])]
        if myebuild:
            myebuild = myebuild[0]
            portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
            self.Entropy.updateProgress(
                brown(" Ebuild: pkg_preinst()"),
                importance = 0,
                header = red("   ##")
            )
            try:
                sys.stdout = stdfile
                rc = self.Spm.spm_doebuild(
                    myebuild,
                    mydo = "setup",
                    tree = "bintree",
                    cpv = portage_atom,
                    portage_tmpdir = self.pkgdata['unpackdir'],
                    licenses = self.pkgdata['accept_license']
                ) # create mysettings["T"]+"/environment"
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[PRE] ATTENTION Cannot properly run Portage preinstall (pkg_setup()) trigger for " + \
                        str(portage_atom) + ". Something bad happened."
                    )
                sys.stdout = oldstdout
                rc = self.Spm.spm_doebuild(
                    myebuild,
                    mydo = "preinst",
                    tree = "bintree",
                    cpv = portage_atom,
                    portage_tmpdir = self.pkgdata['unpackdir'],
                    licenses = self.pkgdata['accept_license']
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[PRE] ATTENTION Cannot properly run Gentoo preinstall (pkg_preinst()) trigger for " + \
                        str(portage_atom)+". Something bad happened."
                    )
            except Exception, e:
                sys.stdout = oldstdout
                self.entropyTools.printTraceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] ATTENTION Cannot run Gentoo preinst trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Portage trigger for")),
                    bold(str(portage_atom)),
                    brown(_("Please report it")),
                    bold(_("Attach this")),
                    darkred(etpConst['spmlogfile']),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
        sys.stderr = oldstderr
        sys.stdout = oldstdout
        stdfile.close()
        return 0

    def trigger_ebuild_preremove(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        sys.stderr = stdfile

        portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
        try:
            myebuild = self.Spm.get_vdb_path()+portage_atom+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']+etpConst['spm']['source_build_ext']
        except:
            myebuild = ''

        self.myebuild_moved = None
        if os.path.isfile(myebuild):
            try:
                myebuild = self._setup_remove_ebuild_environment(myebuild, portage_atom)
            except EOFError, e:
                sys.stderr = oldstderr
                stdfile.close()
                # stuff on system is broken, ignore it
                self.Entropy.updateProgress(
                    darkred("!!! Ebuild: pkg_prerm() failed, EOFError: ")+str(e)+darkred(" - ignoring"),
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )
                return 0
            except ImportError, e:
                sys.stderr = oldstderr
                stdfile.close()
                # stuff on system is broken, ignore it
                self.Entropy.updateProgress(
                    darkred("!!! Ebuild: pkg_prerm() failed, ImportError: ")+str(e)+darkred(" - ignoring"),
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )
                return 0

        if os.path.isfile(myebuild):

            self.Entropy.updateProgress(
                                    brown(" Ebuild: pkg_prerm()"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            try:
                rc = self.Spm.spm_doebuild(
                    myebuild,
                    mydo = "prerm",
                    tree = "bintree",
                    cpv = portage_atom,
                    portage_tmpdir = etpConst['entropyunpackdir'] + "/" + portage_atom
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[PRE] ATTENTION Cannot properly run Portage trigger for " + \
                        str(portage_atom)+". Something bad happened."
                    )
            except Exception, e:
                sys.stderr = oldstderr
                stdfile.close()
                self.entropyTools.printTraceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] ATTENTION Cannot run Portage preremove trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Portage trigger for")),
                    bold(str(portage_atom)),
                    brown(_("Please report it")),
                    bold(_("Attach this")),
                    darkred(etpConst['spmlogfile']),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
                return 0

        sys.stderr = oldstderr
        stdfile.close()
        self._remove_overlayed_ebuild()
        return 0

    def trigger_ebuild_postremove(self):
        stdfile = open("/dev/null","w")
        oldstderr = sys.stderr
        sys.stderr = stdfile

        portage_atom = self.pkgdata['category']+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']
        try:
            myebuild = self.Spm.get_vdb_path()+portage_atom+"/"+self.pkgdata['name']+"-"+self.pkgdata['version']+etpConst['spm']['source_build_ext']
        except:
            myebuild = ''

        self.myebuild_moved = None
        if os.path.isfile(myebuild):
            try:
                myebuild = self._setup_remove_ebuild_environment(myebuild, portage_atom)
            except EOFError, e:
                sys.stderr = oldstderr
                stdfile.close()
                # stuff on system is broken, ignore it
                self.Entropy.updateProgress(
                    darkred("!!! Ebuild: pkg_postrm() failed, EOFError: ")+str(e)+darkred(" - ignoring"),
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )
                return 0
            except ImportError, e:
                sys.stderr = oldstderr
                stdfile.close()
                # stuff on system is broken, ignore it
                self.Entropy.updateProgress(
                    darkred("!!! Ebuild: pkg_postrm() failed, ImportError: ")+str(e)+darkred(" - ignoring"),
                    importance = 1,
                    type = "warning",
                    header = red("   ## ")
                )
                return 0

        if os.path.isfile(myebuild):
            self.Entropy.updateProgress(
                                    brown(" Ebuild: pkg_postrm()"),
                                    importance = 0,
                                    header = red("   ##")
                                )
            try:
                rc = self.Spm.spm_doebuild(
                    myebuild,
                    mydo = "postrm",
                    tree = "bintree",
                    cpv = portage_atom,
                    portage_tmpdir = etpConst['entropyunpackdir']+"/"+portage_atom
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[PRE] ATTENTION Cannot properly run Gentoo postremove trigger for " + \
                        str(portage_atom)+". Something bad happened."
                    )
            except Exception, e:
                sys.stderr = oldstderr
                stdfile.close()
                self.entropyTools.printTraceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] ATTENTION Cannot run Gentoo postremove trigger for " + \
                    portage_atom+"!! "+str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Portage trigger for")),
                    bold(str(portage_atom)),
                    brown(_("Please report it")),
                    bold(_("Attach this")),
                    darkred(etpConst['spmlogfile']),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
                return 0

        sys.stderr = oldstderr
        stdfile.close()
        self._remove_overlayed_ebuild()
        return 0

    def _setup_remove_ebuild_environment(self, myebuild, portage_atom):

        ebuild_dir = os.path.dirname(myebuild)
        ebuild_file = os.path.basename(myebuild)

        # copy the whole directory in a safe place
        dest_dir = os.path.join(etpConst['entropyunpackdir'],"vardb/"+portage_atom)
        if os.path.exists(dest_dir):
            if os.path.isdir(dest_dir):
                shutil.rmtree(dest_dir,True)
            elif os.path.isfile(dest_dir) or os.path.islink(dest_dir):
                os.remove(dest_dir)
        os.makedirs(dest_dir)
        items = os.listdir(ebuild_dir)
        for item in items:
            myfrom = os.path.join(ebuild_dir,item)
            myto = os.path.join(dest_dir,item)
            shutil.copy2(myfrom,myto)

        newmyebuild = os.path.join(dest_dir,ebuild_file)
        if os.path.isfile(newmyebuild):
            myebuild = newmyebuild
            self.myebuild_moved = myebuild
            self._ebuild_env_setup_hook(myebuild)
        return myebuild

    def _ebuild_env_setup_hook(self, myebuild):
        ebuild_path = os.path.dirname(myebuild)
        if not etpConst['systemroot']:
            myroot = "/"
        else:
            myroot = etpConst['systemroot']+"/"

        # we need to fix ROOT= if it's set inside environment
        bz2envfile = os.path.join(ebuild_path,"environment.bz2")
        if os.path.isfile(bz2envfile) and os.path.isdir(myroot):
            import bz2
            envfile = self.Entropy.entropyTools.unpackBzip2(bz2envfile)
            bzf = bz2.BZ2File(bz2envfile,"w")
            f = open(envfile,"r")
            line = f.readline()
            while line:
                if line.startswith("ROOT="):
                    line = "ROOT=%s\n" % (myroot,)
                bzf.write(line)
                line = f.readline()
            f.close()
            bzf.close()
            os.remove(envfile)

    def _remove_overlayed_ebuild(self):
        if not self.myebuild_moved:
            return

        if os.path.isfile(self.myebuild_moved):
            mydir = os.path.dirname(self.myebuild_moved)
            shutil.rmtree(mydir,True)
            mydir = os.path.dirname(mydir)
            content = os.listdir(mydir)
            while not content:
                os.rmdir(mydir)
                mydir = os.path.dirname(mydir)
                content = os.listdir(mydir)

    '''
        Internal ones
    '''

    '''
    @description: set chosen gcc profile
    @output: returns int() as exit status
    '''
    def trigger_set_gcc_profile(self, profile):
        if os.access(etpConst['systemroot']+'/usr/bin/gcc-config',os.X_OK):
            redirect = ""
            if etpUi['quiet']:
                redirect = " &> /dev/null"
            if etpConst['systemroot']:
                subprocess.call("echo '/usr/bin/gcc-config %s' | chroot %s %s" % (profile,etpConst['systemroot'],redirect,), shell = True)
            else:
                subprocess.call('/usr/bin/gcc-config %s %s' % (profile,redirect,), shell = True)
        return 0

    '''
    @description: set chosen binutils profile
    @output: returns int() as exit status
    '''
    def trigger_set_binutils_profile(self, profile):
        if os.access(etpConst['systemroot']+'/usr/bin/binutils-config',os.X_OK):
            redirect = ""
            if etpUi['quiet']:
                redirect = " &> /dev/null"
            if etpConst['systemroot']:
                subprocess.call("echo '/usr/bin/binutils-config %s' | chroot %s %s" % (profile,etpConst['systemroot'],redirect,), shell = True)
            else:
                subprocess.call('/usr/bin/binutils-config %s %s' % (profile,redirect,), shell = True)
        return 0

    '''
    @description: updates moduledb
    @output: returns int() as exit status
    '''
    def trigger_update_moduledb(self, item):
        if os.access(etpConst['systemroot']+'/usr/sbin/module-rebuild',os.X_OK):
            if os.path.isfile(etpConst['systemroot']+self.MODULEDB_DIR+'moduledb'):
                f = open(etpConst['systemroot']+self.MODULEDB_DIR+'moduledb',"r")
                moduledb = f.readlines()
                moduledb = self.Entropy.entropyTools.listToUtf8(moduledb)
                f.close()
                avail = [x for x in moduledb if x.strip() == item]
                if (not avail):
                    f = open(etpConst['systemroot']+self.MODULEDB_DIR+'moduledb',"aw")
                    f.write(item+"\n")
                    f.flush()
                    f.close()
        return 0

    '''
    @description: insert kernel object into kernel modules db
    @output: returns int() as exit status
    '''
    def trigger_run_depmod(self, name):
        if os.access('/sbin/depmod',os.X_OK):
            if not etpConst['systemroot']:
                myroot = "/"
            else:
                myroot = etpConst['systemroot']+"/"
            subprocess.call('/sbin/depmod -a -b %s -r %s &> /dev/null' % (myroot,name,), shell = True)
        return 0

    def __get_entropy_kernel_grub_line(self, kernel):
        return "title="+etpConst['systemname']+" ("+os.path.basename(kernel)+")\n"

    '''
    @description: append kernel entry to grub.conf
    @output: returns int() as exit status
    '''
    def trigger_configure_boot_grub(self, kernel,initramfs):

        if not os.path.isdir(etpConst['systemroot']+"/boot/grub"):
            os.makedirs(etpConst['systemroot']+"/boot/grub")
        if os.path.isfile(etpConst['systemroot']+"/boot/grub/grub.conf"):
            # open in append
            grub = open(etpConst['systemroot']+"/boot/grub/grub.conf","aw")
            shutil.copy2(etpConst['systemroot']+"/boot/grub/grub.conf",etpConst['systemroot']+"/boot/grub/grub.conf.old.add")
            # get boot dev
            boot_dev = self.trigger_get_grub_boot_dev()
            # test if entry has been already added
            grubtest = open(etpConst['systemroot']+"/boot/grub/grub.conf","r")
            content = grubtest.readlines()
            content = [unicode(x,'raw_unicode_escape') for x in content]
            for line in content:
                if line.find(self.__get_entropy_kernel_grub_line(kernel)) != -1:
                    grubtest.close()
                    return
                # also check if we have the same kernel listed
                if (line.find("kernel") != 1) and (line.find(os.path.basename(kernel)) != -1) and not line.strip().startswith("#"):
                    grubtest.close()
                    return
        else:
            # create
            boot_dev = "(hd0,0)"
            grub = open(etpConst['systemroot']+"/boot/grub/grub.conf","w")
            # write header - guess (hd0,0)... since it is weird having a running system without a bootloader, at least, grub.
            grub_header = '''
default=0
timeout=10
            '''
            grub.write(grub_header)
        cmdline = ' '
        if os.path.isfile("/proc/cmdline"):
            f = open("/proc/cmdline","r")
            cmdline = " "+f.readline().strip()
            params = cmdline.split()
            if "dolvm" not in params: # support new kernels >= 2.6.23
                cmdline += " dolvm "
            f.close()
        grub.write(self.__get_entropy_kernel_grub_line(kernel))
        grub.write("\troot "+boot_dev+"\n")
        grub.write("\tkernel "+kernel+cmdline+"\n")
        if initramfs:
            grub.write("\tinitrd "+initramfs+"\n")
        grub.write("\n")
        grub.flush()
        grub.close()

    def trigger_remove_boot_grub(self, kernel,initramfs):
        if os.path.isdir(etpConst['systemroot']+"/boot/grub") and os.path.isfile(etpConst['systemroot']+"/boot/grub/grub.conf"):
            shutil.copy2(etpConst['systemroot']+"/boot/grub/grub.conf",etpConst['systemroot']+"/boot/grub/grub.conf.old.remove")
            f = open(etpConst['systemroot']+"/boot/grub/grub.conf","r")
            grub_conf = f.readlines()
            f.close()
            content = [unicode(x,'raw_unicode_escape') for x in grub_conf]
            try:
                kernel, initramfs = (unicode(kernel,'raw_unicode_escape'),unicode(initramfs,'raw_unicode_escape'))
            except TypeError:
                pass
            #kernelname = os.path.basename(kernel)
            new_conf = []
            skip = False
            for line in content:

                if (line.find(self.__get_entropy_kernel_grub_line(kernel)) != -1):
                    skip = True
                    continue

                if line.strip().startswith("title"):
                    skip = False

                if not skip or line.strip().startswith("#"):
                    new_conf.append(line)

            f = open(etpConst['systemroot']+"/boot/grub/grub.conf","w")
            for line in new_conf:
                try:
                    f.write(line)
                except UnicodeEncodeError:
                    f.write(line.encode('utf-8'))
            f.flush()
            f.close()

    def trigger_get_grub_boot_dev(self):
        if etpConst['systemroot']:
            return "(hd0,0)"
        import re
        df_avail = subprocess.call("which df &> /dev/null", shell = True)
        if df_avail != 0:
            mytxt = "%s: %s! %s. %s (hd0,0)." % (
                bold(_("QA")),
                brown(_("Cannot find df")),
                brown(_("Cannot properly configure the kernel")),
                brown(_("Defaulting to")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return "(hd0,0)"
        grub_avail = subprocess.call("which grub &> /dev/null", shell = True)
        if grub_avail != 0:
            mytxt = "%s: %s! %s. %s (hd0,0)." % (
                bold(_("QA")),
                brown(_("Cannot find grub")),
                brown(_("Cannot properly configure the kernel")),
                brown(_("Defaulting to")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return "(hd0,0)"

        from entropy.tools import getstatusoutput
        gboot = getstatusoutput("df /boot")[1].split("\n")[-1].split()[0]
        if gboot.startswith("/dev/"):
            # it's ok - handle /dev/md
            if gboot.startswith("/dev/md"):
                md = os.path.basename(gboot)
                if not md.startswith("md"):
                    md = "md"+md
                f = open("/proc/mdstat","r")
                mdstat = f.readlines()
                mdstat = [x for x in mdstat if x.startswith(md)]
                f.close()
                if mdstat:
                    mdstat = mdstat[0].strip().split()
                    mddevs = []
                    for x in mdstat:
                        if x.startswith("sd"):
                            mddevs.append(x[:-3])
                    mddevs = sorted(mddevs)
                    if mddevs:
                        gboot = "/dev/"+mddevs[0]
                    else:
                        gboot = "/dev/sda1"
                else:
                    gboot = "/dev/sda1"
            # get disk
            match = re.subn("[0-9]","",gboot)
            gdisk = match[0]
            if gdisk == '':

                mytxt = "%s: %s %s %s. %s! %s (hd0,0)." % (
                    bold(_("QA")),
                    brown(_("cannot match device")),
                    brown(str(gboot)),
                    brown(_("with a grub one")), # 'cannot match device /dev/foo with a grub one'
                    brown(_("Cannot properly configure the kernel")),
                    brown(_("Defaulting to")),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
                return "(hd0,0)"
            match = re.subn("[a-z/]","",gboot)
            try:
                gpartnum = str(int(match[0])-1)
            except ValueError:
                mytxt = "%s: %s: %s. %s. %s (hd0,0)." % (
                    bold(_("QA")),
                    brown(_("grub translation not supported for")),
                    brown(str(gboot)),
                    brown(_("Cannot properly configure grub.conf")),
                    brown(_("Defaulting to")),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
                return "(hd0,0)"
            # now match with grub
            device_map = etpConst['packagestmpdir']+"/grub.map"
            if os.path.isfile(device_map):
                os.remove(device_map)
            # generate device.map
            subprocess.call('echo "quit" | grub --device-map="%s" --no-floppy --batch &> /dev/null' % (device_map,), shell = True)
            if os.path.isfile(device_map):
                f = open(device_map,"r")
                device_map_file = f.readlines()
                f.close()
                grub_dev = [x for x in device_map_file if (x.find(gdisk) != -1)]
                if grub_dev:
                    grub_disk = grub_dev[0].strip().split()[0]
                    grub_dev = grub_disk[:-1]+","+gpartnum+")"
                    return grub_dev
                else:
                    mytxt = "%s: %s. %s! %s (hd0,0)." % (
                        bold(_("QA")),
                        brown(_("cannot match grub device with a Linux one")),
                        brown(_("Cannot properly configure the kernel")),
                        brown(_("Defaulting to")),
                    )
                    self.Entropy.updateProgress(
                        mytxt,
                        importance = 0,
                        header = red("   ## ")
                    )
                    return "(hd0,0)"
            else:
                mytxt = "%s: %s. %s! %s (hd0,0)." % (
                    bold(_("QA")),
                    brown(_("cannot find generated device.map")),
                    brown(_("Cannot properly configure the kernel")),
                    brown(_("Defaulting to")),
                )
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 0,
                    header = red("   ## ")
                )
                return "(hd0,0)"
        else:
            mytxt = "%s: %s. %s! %s (hd0,0)." % (
                bold(_("QA")),
                brown(_("cannot run df /boot")),
                brown(_("Cannot properly configure the kernel")),
                brown(_("Defaulting to")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return "(hd0,0)"

class Repository:

    import entropy.dump as dumpTools
    import entropy.tools as entropyTools
    import socket
    def __init__(self, EquoInstance, reponames = [], forceUpdate = False, noEquoCheck = False, fetchSecurity = True):

        self.LockScanner = None
        if not isinstance(EquoInstance,Client):
            mytxt = _("A valid Equo instance or subclass is needed")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

        self.supported_download_items = (
            "db","rev","ck",
            "lock","mask","system_mask","dbdump", "conflicting_tagged",
            "dbdumpck","lic_whitelist","make.conf",
            "package.mask","package.unmask","package.keywords","profile.link",
            "package.use","server.cert","ca.cert","meta_file",
            "notice_board"
        )
        self.big_socket_timeout = 25
        self.Entropy = EquoInstance
        from entropy.cache import EntropyCacher
        self.Cacher = EntropyCacher()
        self.dbapi2 = dbapi2
        self.reponames = reponames
        self.forceUpdate = forceUpdate
        self.syncErrors = False
        self.dbupdated = False
        self.newEquo = False
        self.fetchSecurity = fetchSecurity
        self.noEquoCheck = noEquoCheck
        self.alreadyUpdated = 0
        self.notAvailable = 0
        self.valid_eapis = [1,2,3]
        self.reset_dbformat_eapi(None)
        self.current_repository_got_locked = False
        self.updated_repos = set()

        # check etpRepositories
        if not etpRepositories:
            mytxt = _("No repositories specified in %s") % (etpConst['repositoriesconf'],)
            raise MissingParameter("MissingParameter: %s" % (mytxt,))

        if not self.reponames:
            self.reponames.extend(etpRepositories.keys()[:])

    def __del__(self):
        if self.LockScanner != None:
            self.LockScanner.kill()

    def get_eapi3_connection(self, repository):
        # get database url
        dburl = etpRepositories[repository]['plain_database']
        if dburl.startswith("file://"):
            return None
        try:
            dburl = dburl.split("/")[2]
        except IndexError:
            return None
        port = etpRepositories[repository]['service_port']
        try:
            from entropy.services.ugc.interfaces import Client
            from entropy.client.services.ugc.commands import Client as CommandsClient
            eapi3_socket = Client(self.Entropy, CommandsClient, output_header = "\t")
            eapi3_socket.socket_timeout = self.big_socket_timeout
            eapi3_socket.connect(dburl, port)
            return eapi3_socket
        except (ConnectionError,self.socket.error,):
            return None

    def check_eapi3_availability(self, repository):
        conn = self.get_eapi3_connection(repository)
        if conn == None: return False
        try:
            conn.disconnect()
        except (self.socket.error,AttributeError,):
            return False
        return True

    def reset_dbformat_eapi(self, repository):

        self.dbformat_eapi = 2
        if repository != None:
            eapi_avail = self.check_eapi3_availability(repository)
            if eapi_avail:
                self.dbformat_eapi = 3

        # FIXME, find a way to do that without needing sqlite3 exec.
        if not os.access("/usr/bin/sqlite3",os.X_OK) or self.entropyTools.islive():
            self.dbformat_eapi = 1
        else:
            rc = subprocess.call("/usr/bin/sqlite3 -version &> /dev/null", shell = True)
            if rc != 0: self.dbformat_eapi = 1

        eapi_env = os.getenv("FORCE_EAPI")
        if eapi_env != None:
            try:
                myeapi = int(eapi_env)
            except (ValueError,TypeError,):
                return
            if myeapi in self.valid_eapis:
                self.dbformat_eapi = myeapi


    def __validate_repository_id(self, repoid):
        if repoid not in self.reponames:
            mytxt = _("Repository is not listed in self.reponames")
            raise InvalidData("InvalidData: %s" % (mytxt,))

    def __validate_compression_method(self, repo):

        self.__validate_repository_id(repo)

        cmethod = etpConst['etpdatabasecompressclasses'].get(etpRepositories[repo]['dbcformat'])
        if cmethod == None:
            mytxt = _("Wrong database compression method")
            raise InvalidDataType("InvalidDataType: %s" % (mytxt,))

        return cmethod

    def __ensure_repository_path(self, repo):

        self.__validate_repository_id(repo)

        # create dir if it doesn't exist
        if not os.path.isdir(etpRepositories[repo]['dbpath']):
            os.makedirs(etpRepositories[repo]['dbpath'],0775)

        const_setup_perms(etpConst['etpdatabaseclientdir'],etpConst['entropygid'])

    def _construct_paths(self, item, repo, cmethod):

        if item not in self.supported_download_items:
            mytxt = _("Supported items: %s") % (self.supported_download_items,)
            raise InvalidData("InvalidData: %s" % (mytxt,))
        if (item in ("db","dbdump", "dbdumpck",)) and (cmethod == None):
                mytxt = _("For %s, cmethod can't be None") % (item,)
                raise InvalidData("InvalidData: %s" % (mytxt,))

        repo_db = etpRepositories[repo]['database']
        repo_dbpath = etpRepositories[repo]['dbpath']
        ec_rev = etpConst['etpdatabaserevisionfile']
        ec_hash = etpConst['etpdatabasehashfile']
        ec_maskfile = etpConst['etpdatabasemaskfile']
        ec_sysmaskfile = etpConst['etpdatabasesytemmaskfile']
        ec_confl_taged = etpConst['etpdatabaseconflictingtaggedfile']
        make_conf_file = os.path.basename(etpConst['spm']['global_make_conf'])
        pkg_mask_file = os.path.basename(etpConst['spm']['global_package_mask'])
        pkg_unmask_file = os.path.basename(etpConst['spm']['global_package_unmask'])
        pkg_keywords_file = os.path.basename(etpConst['spm']['global_package_keywords'])
        pkg_use_file = os.path.basename(etpConst['spm']['global_package_use'])
        sys_profile_lnk = etpConst['spm']['global_make_profile_link_name']
        pkg_lic_wl_file = etpConst['etpdatabaselicwhitelistfile']
        repo_lock_file = etpConst['etpdatabasedownloadlockfile']
        ca_cert_file = etpConst['etpdatabasecacertfile']
        server_cert_file = etpConst['etpdatabaseservercertfile']
        notice_board_filename = os.path.basename(etpRepositories[repo]['notice_board'])
        meta_file = etpConst['etpdatabasemetafilesfile']
        ec_cm2 = None
        ec_cm3 = None
        ec_cm4 = None
        if cmethod != None:
            ec_cm2 = etpConst[cmethod[2]]
            ec_cm3 = etpConst[cmethod[3]]
            ec_cm4 = etpConst[cmethod[4]]

        mymap = {
            'db': ("%s/%s" % (repo_db,ec_cm2,),"%s/%s" % (repo_dbpath,ec_cm2,),),
            'dbdump': ("%s/%s" % (repo_db,ec_cm3,),"%s/%s" % (repo_dbpath,ec_cm3,),),
            'rev': ("%s/%s" % (repo_db,ec_rev,),"%s/%s" % (repo_dbpath,ec_rev,),),
            'ck': ("%s/%s" % (repo_db,ec_hash,),"%s/%s" % (repo_dbpath,ec_hash,),),
            'dbdumpck': ("%s/%s" % (repo_db,ec_cm4,),"%s/%s" % (repo_dbpath,ec_cm4,),),
            'mask': ("%s/%s" % (repo_db,ec_maskfile,),"%s/%s" % (repo_dbpath,ec_maskfile,),),
            'system_mask': ("%s/%s" % (repo_db,ec_sysmaskfile,),"%s/%s" % (repo_dbpath,ec_sysmaskfile,),),
            'conflicting_tagged': ("%s/%s" % (repo_db,ec_confl_taged,),"%s/%s" % (repo_dbpath,ec_confl_taged,),),
            'make.conf': ("%s/%s" % (repo_db,make_conf_file,),"%s/%s" % (repo_dbpath,make_conf_file,),),
            'package.mask': ("%s/%s" % (repo_db,pkg_mask_file,),"%s/%s" % (repo_dbpath,pkg_mask_file,),),
            'package.unmask': ("%s/%s" % (repo_db,pkg_unmask_file,),"%s/%s" % (repo_dbpath,pkg_unmask_file,),),
            'package.keywords': ("%s/%s" % (repo_db,pkg_keywords_file,),"%s/%s" % (repo_dbpath,pkg_keywords_file,),),
            'package.use': ("%s/%s" % (repo_db,pkg_use_file,),"%s/%s" % (repo_dbpath,pkg_use_file,),),
            'profile.link': ("%s/%s" % (repo_db,sys_profile_lnk,),"%s/%s" % (repo_dbpath,sys_profile_lnk,),),
            'lic_whitelist': ("%s/%s" % (repo_db,pkg_lic_wl_file,),"%s/%s" % (repo_dbpath,pkg_lic_wl_file,),),
            'lock': ("%s/%s" % (repo_db,repo_lock_file,),"%s/%s" % (repo_dbpath,repo_lock_file,),),
            'server.cert': ("%s/%s" % (repo_db,server_cert_file,),"%s/%s" % (repo_dbpath,server_cert_file,),),
            'ca.cert': ("%s/%s" % (repo_db,ca_cert_file,),"%s/%s" % (repo_dbpath,ca_cert_file,),),
            'notice_board': (etpRepositories[repo]['notice_board'],"%s/%s" % (repo_dbpath,notice_board_filename,),),
            'meta_file': ("%s/%s" % (repo_db,meta_file,),"%s/%s" % (repo_dbpath,meta_file,),),
        }

        return mymap.get(item)

    def __remove_repository_files(self, repo, cmethod):

        dbfilenameid = cmethod[2]
        self.__validate_repository_id(repo)
        repo_dbpath = etpRepositories[repo]['dbpath']

        def remove_eapi1(repo_dbpath, dbfilenameid):
            if os.path.isfile(repo_dbpath+"/"+etpConst['etpdatabasehashfile']):
                os.remove(repo_dbpath+"/"+etpConst['etpdatabasehashfile'])
            if os.path.isfile(repo_dbpath+"/"+etpConst[dbfilenameid]):
                os.remove(repo_dbpath+"/"+etpConst[dbfilenameid])
            if os.path.isfile(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile']):
                os.remove(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile'])

        if self.dbformat_eapi == 1:
            remove_eapi1(repo_dbpath, dbfilenameid)
        elif self.dbformat_eapi in (2,3,):
            remove_eapi1(repo_dbpath, dbfilenameid)
            if os.path.isfile(repo_dbpath+"/"+cmethod[4]):
                os.remove(repo_dbpath+"/"+cmethod[4])
            if os.path.isfile(repo_dbpath+"/"+etpConst[cmethod[3]]):
                os.remove(repo_dbpath+"/"+etpConst[cmethod[3]])
            if os.path.isfile(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile']):
                os.remove(repo_dbpath+"/"+etpConst['etpdatabaserevisionfile'])
        else:
            mytxt = _("self.dbformat_eapi must be in (1,2)")
            raise InvalidData('InvalidData: %s' % (mytxt,))

    def __unpack_downloaded_database(self, repo, cmethod):

        self.__validate_repository_id(repo)
        rc = 0
        path = None

        if self.dbformat_eapi == 1:
            myfile = etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[2]]
            try:
                path = eval("self.entropyTools."+cmethod[1])(myfile)
            except EOFError:
                rc = 1
            if os.path.isfile(myfile):
                os.remove(myfile)
        elif self.dbformat_eapi == 2:
            myfile = etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[3]]
            try:
                path = eval("self.entropyTools."+cmethod[1])(myfile)
            except EOFError:
                rc = 1
            if os.path.isfile(myfile):
                os.remove(myfile)
        else:
            mytxt = _("self.dbformat_eapi must be in (1,2)")
            raise InvalidData('InvalidData: %s' % (mytxt,))

        if rc == 0:
            self.Entropy.setup_default_file_perms(path)

        return rc

    def __verify_database_checksum(self, repo, cmethod = None):

        self.__validate_repository_id(repo)

        if self.dbformat_eapi == 1:
            dbfile = etpConst['etpdatabasefile']
            try:
                f = open(etpRepositories[repo]['dbpath']+"/"+etpConst['etpdatabasehashfile'],"r")
                md5hash = f.readline().strip()
                md5hash = md5hash.split()[0]
                f.close()
            except:
                return -1
        elif self.dbformat_eapi == 2:
            dbfile = etpConst[cmethod[3]]
            try:
                f = open(etpRepositories[repo]['dbpath']+"/"+etpConst[cmethod[4]],"r")
                md5hash = f.readline().strip()
                md5hash = md5hash.split()[0]
                f.close()
            except:
                return -1
        else:
            mytxt = _("self.dbformat_eapi must be in (1,2)")
            raise InvalidData('InvalidData: %s' % (mytxt,))

        rc = self.entropyTools.compareMd5(etpRepositories[repo]['dbpath']+"/"+dbfile,md5hash)
        return rc

    # @returns -1 if the file is not available
    # @returns int>0 if the revision has been retrieved
    def get_online_repository_revision(self, repo):

        self.__validate_repository_id(repo)

        url = etpRepositories[repo]['database']+"/"+etpConst['etpdatabaserevisionfile']
        status = self.entropyTools.get_remote_data(url)
        if (status):
            status = status[0].strip()
            try:
                status = int(status)
            except ValueError:
                status = -1
            return status
        else:
            return -1

    def get_online_eapi3_lock(self, repo):
        self.__validate_repository_id(repo)
        url = etpRepositories[repo]['database']+"/"+etpConst['etpdatabaseeapi3lockfile']
        data = self.entropyTools.get_remote_data(url)
        if not data:
            return False
        return True

    def is_repository_eapi3_locked(self, repo):
        self.__validate_repository_id(repo)
        return self.get_online_eapi3_lock(repo)

    def is_repository_updatable(self, repo):

        self.__validate_repository_id(repo)

        onlinestatus = self.get_online_repository_revision(repo)
        if (onlinestatus != -1):
            localstatus = self.Entropy.get_repository_revision(repo)
            if (localstatus == onlinestatus) and (not self.forceUpdate):
                return False
        return True

    def is_repository_unlocked(self, repo):

        self.__validate_repository_id(repo)

        rc = self.download_item("lock", repo, disallow_redirect = True)
        if rc: # cannot download database
            self.syncErrors = True
            return False
        return True

    def clear_repository_cache(self, repo):
        self.__validate_repository_id(repo)
        self.Entropy.clear_dump_cache("%s/%s%s/" % (etpCache['dbMatch'],etpConst['dbnamerepoprefix'],repo,))
        self.Entropy.clear_dump_cache("%s/%s%s/" % (etpCache['dbSearch'],etpConst['dbnamerepoprefix'],repo,))

    # this function can be reimplemented
    def download_item(self, item, repo, cmethod = None, lock_status_func = None, disallow_redirect = True):

        self.__validate_repository_id(repo)
        url, filepath = self._construct_paths(item, repo, cmethod)

        # to avoid having permissions issues
        # it's better to remove the file before,
        # otherwise new permissions won't be written
        if os.path.isfile(filepath):
            os.remove(filepath)
        filepath_dir = os.path.dirname(filepath)
        if not os.path.isdir(filepath_dir) and not os.path.lexists(filepath_dir):
            os.makedirs(filepath_dir,0775)
            const_setup_perms(filepath_dir, etpConst['entropygid'])

        fetchConn = self.Entropy.urlFetcher(
            url,
            filepath,
            resume = False,
            abort_check_func = lock_status_func,
            disallow_redirect = disallow_redirect
        )
        fetchConn.progress = self.Entropy.progress

        rc = fetchConn.download()
        del fetchConn
        if rc in ("-1","-2","-3","-4"):
            return False
        self.Entropy.setup_default_file_perms(filepath)
        return True

    def check_downloaded_database(self, repo, cmethod):
        dbfilename = etpConst['etpdatabasefile']
        if self.dbformat_eapi == 2:
            dbfilename = etpConst[cmethod[3]]
        # verify checksum
        mytxt = "%s %s %s" % (red(_("Checking downloaded database")),darkgreen(dbfilename),red("..."))
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            back = True,
            type = "info",
            header = "\t"
        )
        db_status = self.__verify_database_checksum(repo, cmethod)
        if db_status == -1:
            mytxt = "%s. %s !" % (red(_("Cannot open digest")),red(_("Cannot verify database integrity")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )
        elif db_status:
            mytxt = "%s: %s" % (red(_("Downloaded database status")),bold(_("OK")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = "\t"
            )
        else:
            mytxt = "%s: %s" % (red(_("Downloaded database status")),darkred(_("ERROR")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = "\t"
            )
            mytxt = "%s. %s" % (red(_("An error occured while checking database integrity")),red(_("Giving up")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "error",
                header = "\t"
            )
            return 1
        return 0


    def show_repository_information(self, repo, count_info):

        self.Entropy.updateProgress(
            bold("%s") % ( etpRepositories[repo]['description'] ),
            importance = 2,
            type = "info",
            count = count_info,
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database URL")),darkgreen(etpRepositories[repo]['database']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database local path")),darkgreen(etpRepositories[repo]['dbpath']),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = blue("  # ")
        )
        mytxt = "%s: %s" % (red(_("Database EAPI")),darkgreen(str(self.dbformat_eapi)),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = blue("  # ")
        )

    def get_eapi3_local_database(self, repo):

        dbfile = os.path.join(etpRepositories[repo]['dbpath'],etpConst['etpdatabasefile'])
        mydbconn = None
        try:
            mydbconn = self.Entropy.open_generic_database(dbfile, xcache = False, indexing_override = False)
            mydbconn.validateDatabase()
        except (
            self.Entropy.dbapi2.OperationalError,
            self.Entropy.dbapi2.IntegrityError,
            SystemDatabaseError,
            IOError,
            OSError,):
                mydbconn = None
        return mydbconn

    def get_eapi3_database_differences(self, eapi3_interface, repo, idpackages, session):

        data = eapi3_interface.CmdInterface.differential_packages_comparison(
            session, idpackages, repo, etpConst['currentarch'], etpConst['product']
        )
        if isinstance(data,bool): # then it's probably == False
            return False,False,False
        elif not isinstance(data,dict):
            return None,None,None
        elif not data.has_key('added') or \
            not data.has_key('removed') or \
            not data.has_key('checksum'):
                return None,None,None
        return data['added'],data['removed'],data['checksum']

    def get_eapi3_database_treeupdates(self, eapi3_interface, repo, session):
        self.socket.setdefaulttimeout(self.big_socket_timeout)
        data = eapi3_interface.CmdInterface.get_repository_treeupdates(
            session, repo, etpConst['currentarch'], etpConst['product']
        )
        if not isinstance(data,dict): return None,None
        return data.get('digest'), data.get('actions')

    def get_eapi3_package_sets(self, eapi3_interface, repo, session):
        self.socket.setdefaulttimeout(self.big_socket_timeout)
        data = eapi3_interface.CmdInterface.get_package_sets(
            session, repo, etpConst['currentarch'], etpConst['product']
        )
        if not isinstance(data,dict): return {}
        return data

    def handle_eapi3_database_sync(self, repo, threshold = 1500, chunk_size = 12):

        def prepare_exit(mysock, session = None):
            try:
                if session != None:
                    mysock.close_session(session)
                mysock.disconnect()
            except (self.socket.error,):
                pass

        eapi3_interface = self.get_eapi3_connection(repo)
        if eapi3_interface == None: return False

        session = eapi3_interface.open_session()

        # AttributeError because mydbconn can be == None
        try:
            mydbconn = self.get_eapi3_local_database(repo)
            myidpackages = mydbconn.listAllIdpackages()
        except (self.dbapi2.DatabaseError,self.dbapi2.IntegrityError,self.dbapi2.OperationalError,AttributeError,):
            prepare_exit(eapi3_interface, session)
            return False

        added_ids, removed_ids, checksum = self.get_eapi3_database_differences(
            eapi3_interface, repo,
            myidpackages, session
        )
        if (None in (added_ids,removed_ids,checksum)) or \
            (not added_ids and not removed_ids and self.forceUpdate):
                mydbconn.closeDB()
                prepare_exit(eapi3_interface, session)
                return False

        elif not checksum: # {added_ids, removed_ids, checksum} == False
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            mytxt = "%s: %s" % ( blue(_("EAPI3 Service status")), darkred(_("remote database suddenly locked")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = blue("  # "),
            )
            return None

        # is it worth it?
        if len(added_ids) > threshold:
            mytxt = "%s: %s (%s: %s/%s)" % (
                blue(_("EAPI3 Service")), darkred(_("skipping differential sync")),
                brown(_("threshold")), blue(str(len(added_ids))), darkred(str(threshold)),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = blue("  # "),
            )
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            return False

        count = 0
        added_segments = []
        mytmp = set()

        for idpackage in added_ids:
            count += 1
            mytmp.add(idpackage)
            if count % chunk_size == 0:
                added_segments.append(list(mytmp))
                mytmp.clear()
        if mytmp: added_segments.append(list(mytmp))
        del mytmp

        # fetch and store
        count = 0
        maxcount = len(added_segments)
        for segment in added_segments:

            count += 1
            mytxt = "%s %s" % (blue(_("Fetching segments")), "...",)
            self.Entropy.updateProgress(
                mytxt, importance = 0, type = "info",
                header = "\t", back = True, count = (count,maxcount,)
            )
            fetch_count = 0
            max_fetch_count = 5

            while 1:

                # anti loop protection
                if fetch_count > max_fetch_count:
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return False

                fetch_count += 1
                pkgdata = eapi3_interface.CmdInterface.get_package_information(
                    session, segment, repo, etpConst['currentarch'], etpConst['product']
                )
                if pkgdata == None:
                    mytxt = "%s: %s" % ( blue(_("Fetch error on segment")), darkred(str(segment)),)
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "warning",
                        header = "\t", count = (count,maxcount,)
                    )
                    continue
                elif not pkgdata: # pkgdata == False
                    mytxt = "%s: %s" % (
                        blue(_("Service status")),
                        darkred("remote database suddenly locked"),
                    )
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "info",
                        header = "\t", count = (count,maxcount,)
                    )
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return None
                elif isinstance(pkgdata,tuple):
                    mytxt = "%s: %s, %s. %s" % ( blue(_("Service status")), pkgdata[0], pkgdata[1], darkred("Error processing the command"),)
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "info",
                        header = "\t", count = (count,maxcount,)
                    )
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return None

                try:
                    for idpackage in pkgdata:
                        self.dumpTools.dumpobj(
                            "%s%s" % (etpCache['eapi3_fetch'],idpackage,),
                            pkgdata[idpackage],
                            ignoreExceptions = False
                        )
                except (IOError,EOFError,OSError,), e:
                    mytxt = "%s: %s: %s." % ( blue(_("Local status")), darkred("Error storing data"), e,)
                    self.Entropy.updateProgress(
                        mytxt, importance = 1, type = "info",
                        header = "\t", count = (count,maxcount,)
                    )
                    mydbconn.closeDB()
                    prepare_exit(eapi3_interface, session)
                    return None

                break

        del added_segments

        # get treeupdates stuff
        dbdigest, treeupdates_actions = self.get_eapi3_database_treeupdates(eapi3_interface, repo, session)
        if dbdigest == None:
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            mytxt = "%s: %s" % ( blue(_("EAPI3 Service status")), darkred(_("treeupdates data not available")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = blue("  # "),
            )
            return None

        try:
            mydbconn.setRepositoryUpdatesDigest(repo, dbdigest)
            mydbconn.bumpTreeUpdatesActions(treeupdates_actions)
        except (self.dbapi2.DatabaseError,self.dbapi2.IntegrityError,self.dbapi2.OperationalError,):
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            mytxt = "%s: %s" % (blue(_("EAPI3 Service status")), darkred(_("cannot update treeupdates data")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = blue("  # "),
            )
            return None


        # get updated package sets
        repo_sets = self.get_eapi3_package_sets(eapi3_interface, repo, session)
        try:
            mydbconn.clearPackageSets()
            mydbconn.insertPackageSets(repo_sets)
        except (self.dbapi2.DatabaseError,self.dbapi2.IntegrityError,self.dbapi2.OperationalError,):
            mydbconn.closeDB()
            prepare_exit(eapi3_interface, session)
            mytxt = "%s: %s" % (blue(_("EAPI3 Service status")), darkred(_("cannot update package sets data")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = blue("  # "),
            )
            return None

        # I don't need you anymore
        # disconnect socket
        prepare_exit(eapi3_interface, session)

        # now that we have all stored, add
        count = 0
        maxcount = len(added_ids)
        for idpackage in added_ids:
            count += 1
            mydata = self.Cacher.pop("%s%s" % (etpCache['eapi3_fetch'],idpackage,))
            if mydata == None:
                mytxt = "%s: %s" % (
                    blue(_("Fetch error on segment while adding")),
                    darkred(str(segment)),
                )
                self.Entropy.updateProgress(
                    mytxt, importance = 1, type = "warning",
                    header = "\t", count = (count,maxcount,)
                )
                mydbconn.closeDB()
                return False

            mytxt = "%s %s" % (blue(_("Injecting package")), darkgreen(mydata['atom']),)
            self.Entropy.updateProgress(
                mytxt, importance = 0, type = "info",
                header = "\t", back = True, count = (count,maxcount,)
            )
            mydbconn.addPackage(
                mydata, revision = mydata['revision'],
                idpackage = idpackage, do_remove = False,
                do_commit = False, formatted_content = True
            )

        self.Entropy.updateProgress(
            blue(_("Packages injection complete")), importance = 0,
            type = "info", header = "\t",
        )

        # now remove
        maxcount = len(removed_ids)
        count = 0
        for idpackage in removed_ids:
            myatom = mydbconn.retrieveAtom(idpackage)
            count += 1
            mytxt = "%s: %s" % (blue(_("Removing package")), darkred(str(myatom)),)
            self.Entropy.updateProgress(
                mytxt, importance = 0, type = "info",
                header = "\t", back = True, count = (count,maxcount,)
            )
            mydbconn.removePackage(idpackage, do_cleanup = False, do_commit = False)

        self.Entropy.updateProgress(
            blue(_("Packages removal complete")),
            importance = 0, type = "info",
            header = "\t",
        )

        mydbconn.commitChanges()
        mydbconn.clearCache()
        # now verify if both checksums match
        result = False
        mychecksum = mydbconn.database_checksum(do_order = True, strict = False, strings = True)
        if checksum == mychecksum:
            result = True
        else:
            mytxt = "%s: %s: %s | %s: %s" % (
                blue(_("Database checksum doesn't match remote.")),
                darkgreen(_("local")), mychecksum,
                darkred(_("remote")), checksum,
            )
            self.Entropy.updateProgress(
                mytxt, importance = 0,
                type = "info", header = "\t",
            )

        mydbconn.closeDB()
        return result

    def run_sync(self):

        self.dbupdated = False
        repocount = 0
        repolength = len(self.reponames)
        for repo in self.reponames:

            repocount += 1
            self.reset_dbformat_eapi(repo)
            self.show_repository_information(repo, (repocount,repolength))

            if not self.forceUpdate:
                updated = self.handle_repository_update(repo)
                if updated:
                    self.Entropy.cycleDone()
                    self.alreadyUpdated += 1
                    continue

            locked = self.handle_repository_lock(repo)
            if locked:
                self.notAvailable += 1
                self.Entropy.cycleDone()
                continue

            # clear database interface cache belonging to this repository
            self.clear_repository_cache(repo)
            self.__ensure_repository_path(repo)

            # dealing with EAPI
            # setting some vars
            do_skip = False
            skip_this_repo = False
            db_down_status = False
            do_db_update_transfer = False
            rc = 0
            # some variables
            dumpfile = os.path.join(etpRepositories[repo]['dbpath'],etpConst['etpdatabasedump'])
            dbfile = os.path.join(etpRepositories[repo]['dbpath'],etpConst['etpdatabasefile'])
            dbfile_old = dbfile+".sync"
            cmethod = self.__validate_compression_method(repo)

            while 1:

                if do_skip:
                    break

                if self.dbformat_eapi < 3:

                    down_status = self.handle_database_download(repo, cmethod)
                    if not down_status:
                        self.Entropy.cycleDone()
                        self.notAvailable += 1
                        do_skip = True
                        skip_this_repo = True
                        continue
                    db_down_status = self.handle_database_checksum_download(repo, cmethod)
                    break

                elif self.dbformat_eapi == 3 and not (os.path.isfile(dbfile) and os.access(dbfile,os.W_OK)):

                    do_db_update_transfer = None
                    self.dbformat_eapi -= 1
                    continue

                elif self.dbformat_eapi == 3:

                    status = False
                    try:
                        status = self.handle_eapi3_database_sync(repo)
                    except self.socket.error, e:
                        mytxt = "%s: %s" % (
                            blue(_("EAPI3 Service error")),
                            darkred(unicode(e)),
                        )
                        self.Entropy.updateProgress(
                            mytxt,
                            importance = 0,
                            type = "info",
                            header = blue("  # "),
                        )
                    except:
                        # avoid broken entries, deal with every exception
                        self.__remove_repository_files(repo, cmethod)
                        raise

                    if status == None: # remote db not available anymore ?
                        time.sleep(5)
                        locked = self.handle_repository_lock(repo)
                        if locked:
                            self.Entropy.cycleDone()
                            self.notAvailable += 1
                            do_skip = True
                            skip_this_repo = True
                        else: # ah, well... dunno then...
                            do_db_update_transfer = None
                            self.dbformat_eapi -= 1
                        continue
                    elif not status: # (status == False)
                        # set to none and completely skip database alignment
                        do_db_update_transfer = None
                        self.dbformat_eapi -= 1
                        continue

                    break

            if skip_this_repo:
                continue

            if self.dbformat_eapi in (1,2,):

                if self.dbformat_eapi == 2 and db_down_status:
                    rc = self.check_downloaded_database(repo, cmethod)
                    if rc != 0:
                        # delete all
                        self.__remove_repository_files(repo, cmethod)
                        self.syncErrors = True
                        self.Entropy.cycleDone()
                        continue

                if isinstance(do_db_update_transfer,bool) and not do_db_update_transfer:
                    if os.path.isfile(dbfile):
                        try:
                            shutil.move(dbfile,dbfile_old)
                            do_db_update_transfer = True
                        except:
                            pass

                # unpack database
                unpack_status = self.handle_downloaded_database_unpack(repo, cmethod)
                if not unpack_status:
                    # delete all
                    self.__remove_repository_files(repo, cmethod)
                    self.syncErrors = True
                    self.Entropy.cycleDone()
                    continue

                if self.dbformat_eapi == 1 and db_down_status:
                    rc = self.check_downloaded_database(repo, cmethod)
                    if rc != 0:
                        # delete all
                        self.__remove_repository_files(repo, cmethod)
                        self.syncErrors = True
                        self.Entropy.cycleDone()
                        if os.path.isfile(dbfile_old):
                            os.remove(dbfile_old)
                        continue

                # re-validate
                if not os.path.isfile(dbfile):
                    do_db_update_transfer = False
                elif os.path.isfile(dbfile) and not do_db_update_transfer and (self.dbformat_eapi != 1):
                    os.remove(dbfile)

                if self.dbformat_eapi == 2:
                    rc = self.do_eapi2_inject_downloaded_dump(dumpfile, dbfile, cmethod)

                if do_db_update_transfer:
                    self.do_eapi1_eapi2_databases_alignment(dbfile, dbfile_old)
                if self.dbformat_eapi == 2:
                    # remove the dump
                    os.remove(dumpfile)

            if rc != 0:
                # delete all
                self.__remove_repository_files(repo, cmethod)
                self.syncErrors = True
                self.Entropy.cycleDone()
                if os.path.isfile(dbfile_old):
                    os.remove(dbfile_old)
                continue

            if os.path.isfile(dbfile) and os.access(dbfile,os.W_OK):
                try:
                    self.Entropy.setup_default_file_perms(dbfile)
                except OSError: # notification applet
                    pass

            # database is going to be updated
            self.dbupdated = True
            self.do_standard_items_download(repo)
            self.Entropy.update_repository_revision(repo)
            if self.Entropy.indexing:
                self.do_database_indexing(repo)
            if (repo == etpConst['officialrepositoryid']):
                try:
                    self.run_config_files_updates(repo)
                except Exception, e:
                    self.entropyTools.printTraceback()
                    mytxt = "%s: %s" % (
                        blue(_("Configuration files update error, not critical, continuing")),
                        darkred(unicode(e)),
                    )
                    self.Entropy.updateProgress(mytxt, importance = 0, type = "info", header = blue("  # "),)
            self.updated_repos.add(repo)
            self.Entropy.cycleDone()

            # remove garbage
            if os.path.isfile(dbfile_old):
                os.remove(dbfile_old)

        # keep them closed
        self.Entropy.close_all_repositories()
        self.Entropy.validate_repositories()
        self.Entropy.close_all_repositories()

        # clean caches, fetch security
        if self.dbupdated:
            self.Entropy.generate_cache(
                depcache = self.Entropy.xcache,
                configcache = False,
                client_purge = False,
                install_queue = False
            )
            if self.fetchSecurity:
                self.do_update_security_advisories()
            # do treeupdates
            if isinstance(self.Entropy.clientDbconn,LocalRepository):
                for repo in self.reponames:
                    dbc = self.Entropy.open_repository(repo)
                    dbc.clientUpdatePackagesData(self.Entropy.clientDbconn)
                self.Entropy.close_all_repositories()

        if self.syncErrors:
            self.Entropy.updateProgress(
                red(_("Something bad happened. Please have a look.")),
                importance = 1,
                type = "warning",
                header = darkred(" @@ ")
            )
            self.syncErrors = True
            self.Entropy._resources_run_remove_lock()
            return 128

        if not self.noEquoCheck:
            self.check_entropy_updates()

        return 0

    def run_config_files_updates(self, repo):

        # are we root?
        if etpConst['uid'] != 0:
            self.Entropy.updateProgress(
                brown(_("Skipping configuration files update, you are not root.")),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            return

        # make.conf
        self._config_updates_make_conf(repo)
        self._config_updates_make_profile(repo)


    def _config_updates_make_conf(self, repo):

        ## WARNING: it doesn't handle multi-line variables, yet. remember this.
        url, repo_make_conf = self._construct_paths("make.conf", repo, None)
        system_make_conf = etpConst['spm']['global_make_conf']
        make_conf_variables_check = ["CHOST"]

        if os.path.isfile(repo_make_conf) and os.access(repo_make_conf,os.R_OK):

            if not os.path.isfile(system_make_conf):
                self.Entropy.updateProgress(
                    "%s %s. %s." % (red(system_make_conf),blue(_("does not exist")),blue(_("Overwriting")),),
                    importance = 1,
                    type = "info",
                    header = blue(" @@ ")
                )
                if os.path.lexists(system_make_conf):
                    shutil.move(
                        system_make_conf,
                        "%s.backup_%s" % (system_make_conf,self.entropyTools.getRandomNumber(),)
                    )
                shutil.copy2(repo_make_conf,system_make_conf)

            elif os.access(system_make_conf,os.W_OK):

                repo_f = open(repo_make_conf,"r")
                sys_f = open(system_make_conf,"r")
                repo_make_c = [x.strip() for x in repo_f.readlines()]
                sys_make_c = [x.strip() for x in sys_f.readlines()]
                repo_f.close()
                sys_f.close()

                # read repository settings
                repo_data = {}
                for setting in make_conf_variables_check:
                    for line in repo_make_c:
                        if line.startswith(setting+"="):
                            # there can't be bash vars with a space after its name on declaration
                            repo_data[setting] = line
                            # I don't break, because there might be other overlapping settings

                differences = {}
                # update make.conf data in memory
                for setting in repo_data:
                    for idx in range(len(sys_make_c)):
                        line = sys_make_c[idx]
                        if line.startswith(setting+"=") and (line != repo_data[setting]):
                            # there can't be bash vars with a space after its name on declaration
                            self.Entropy.updateProgress(
                                "%s: %s %s. %s." % (
                                    red(system_make_conf), bold(unicode(setting)),
                                    blue(_("variable differs")), red(_("Updating")),
                                ),
                                importance = 1,
                                type = "info",
                                header = blue(" @@ ")
                            )
                            differences[setting] = repo_data[setting]
                            line = repo_data[setting]
                        sys_make_c[idx] = line

                if differences:

                    self.Entropy.updateProgress(
                        "%s: %s." % (red(system_make_conf), blue(_("updating critical variables")),),
                        importance = 1,
                        type = "info",
                        header = blue(" @@ ")
                    )
                    # backup user make.conf
                    shutil.copy2(system_make_conf,"%s.entropy_backup" % (system_make_conf,))

                    self.Entropy.updateProgress(
                        "%s: %s." % (
                            red(system_make_conf), darkgreen("writing changes to disk"),
                        ),
                        importance = 1,
                        type = "info",
                        header = blue(" @@ ")
                    )
                    # write to disk, safely
                    tmp_make_conf = "%s.entropy_write" % (system_make_conf,)
                    f = open(tmp_make_conf,"w")
                    for line in sys_make_c: f.write(line+"\n")
                    f.flush()
                    f.close()
                    shutil.move(tmp_make_conf,system_make_conf)

                # update environment
                for var in differences:
                    try:
                        myval = '='.join(differences[var].strip().split("=")[1:])
                        if myval:
                            if myval[0] in ("'",'"',): myval = myval[1:]
                            if myval[-1] in ("'",'"',): myval = myval[:-1]
                    except IndexError:
                        myval = ''
                    os.environ[var] = myval

    def _config_updates_make_profile(self, repo):
        url, repo_make_profile = self._construct_paths("profile.link", repo, None)
        system_make_profile = etpConst['spm']['global_make_profile']
        if not (os.path.isfile(repo_make_profile) and os.access(repo_make_profile,os.R_OK)):
            return
        f = open(repo_make_profile,"r")
        repo_profile_link_data = f.readline().strip()
        f.close()
        current_profile_link = ''
        if os.path.islink(system_make_profile) and os.access(system_make_profile,os.R_OK):
            current_profile_link = os.readlink(system_make_profile)
        if repo_profile_link_data != current_profile_link:
            self.Entropy.updateProgress(
                "%s: %s %s. %s." % (
                    red(system_make_profile), blue("link"),
                    blue(_("differs")), red(_("Updating")),
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ ")
            )
            merge_sfx = ".entropy_merge"
            os.symlink(repo_profile_link_data,system_make_profile+merge_sfx)
            if self.entropyTools.is_valid_path(system_make_profile+merge_sfx):
                os.rename(system_make_profile+merge_sfx,system_make_profile)
            else:
                # revert change, link does not exist yet
                self.Entropy.updateProgress(
                    "%s: %s %s. %s." % (
                        red(system_make_profile), blue("new link"),
                        blue(_("does not exist")), red(_("Reverting")),
                    ),
                    importance = 1,
                    type = "info",
                    header = blue(" @@ ")
                )
                os.remove(system_make_profile+merge_sfx)


    def check_entropy_updates(self):
        rc = False
        if not self.noEquoCheck:
            try:
                rc = self.Entropy.check_package_update("sys-apps/entropy", deep = True)
            except:
                pass
        if rc:
            self.newEquo = True
            mytxt = "%s: %s. %s." % (
                bold("Equo/Entropy"),
                blue(_("a new release is available")),
                darkred(_("Mind to install it before any other package")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = bold(" !!! ")
            )

    def handle_downloaded_database_unpack(self, repo, cmethod):

        file_to_unpack = etpConst['etpdatabasedump']
        if self.dbformat_eapi == 1:
            file_to_unpack = etpConst['etpdatabasefile']
        mytxt = "%s %s %s" % (red(_("Unpacking database to")),darkgreen(file_to_unpack),red("..."),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = "\t"
        )

        myrc = self.__unpack_downloaded_database(repo, cmethod)
        if myrc != 0:
            mytxt = "%s %s !" % (red(_("Cannot unpack compressed package")),red(_("Skipping repository")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )
            return False
        return True


    def handle_database_checksum_download(self, repo, cmethod):

        hashfile = etpConst['etpdatabasehashfile']
        downitem = 'ck'
        if self.dbformat_eapi == 2: # EAPI = 2
            hashfile = etpConst[cmethod[4]]
            downitem = 'dbdumpck'

        mytxt = "%s %s %s" % (red(_("Downloading checksum")),darkgreen(hashfile),red("..."),)
        # download checksum
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = "\t"
        )

        db_down_status = self.download_item(downitem, repo, cmethod, disallow_redirect = True)
        if not db_down_status:
            mytxt = "%s %s !" % (red(_("Cannot fetch checksum")),red(_("Cannot verify database integrity")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )
        return db_down_status

    def load_background_repository_lock_check(self, repo):
        # kill previous
        self.current_repository_got_locked = False
        self.kill_previous_repository_lock_scanner()
        self.LockScanner = TimeScheduled(5, self.repository_lock_scanner, repo)
        self.LockScanner.start()

    def kill_previous_repository_lock_scanner(self):
        if self.LockScanner != None:
            self.LockScanner.kill()

    def repository_lock_scanner(self, repo):
        locked = self.handle_repository_lock(repo)
        if locked:
            self.current_repository_got_locked = True

    def repository_lock_scanner_status(self):
        # raise an exception if repo got suddenly locked
        if self.current_repository_got_locked:
            mytxt = _("Current repository got suddenly locked. Download aborted.")
            raise RepositoryError('RepositoryError %s' % (mytxt,))

    def handle_database_download(self, repo, cmethod):

        def show_repo_locked_message():
            mytxt = "%s: %s." % (bold(_("Attention")),red(_("remote database got suddenly locked")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )

        # starting to download
        mytxt = "%s ..." % (red(_("Downloading repository database")),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = "\t"
        )

        down_status = False
        if self.dbformat_eapi == 2:
            # start a check in background
            self.load_background_repository_lock_check(repo)
            down_status = self.download_item("dbdump", repo, cmethod, lock_status_func = self.repository_lock_scanner_status, disallow_redirect = True)
            if self.current_repository_got_locked:
                self.kill_previous_repository_lock_scanner()
                show_repo_locked_message()
                return False
        if not down_status: # fallback to old db
            # start a check in background
            self.load_background_repository_lock_check(repo)
            self.dbformat_eapi = 1
            down_status = self.download_item("db", repo, cmethod, lock_status_func = self.repository_lock_scanner_status, disallow_redirect = True)
            if self.current_repository_got_locked:
                self.kill_previous_repository_lock_scanner()
                show_repo_locked_message()
                return False

        if not down_status:
            mytxt = "%s: %s." % (bold(_("Attention")),red(_("database does not exist online")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )

        self.kill_previous_repository_lock_scanner()
        return down_status

    def handle_repository_update(self, repo):
        # check if database is already updated to the latest revision
        update = self.is_repository_updatable(repo)
        if not update:
            mytxt = "%s: %s." % (bold(_("Attention")),red(_("database is already up to date")),)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = "\t"
            )
            return True
        # also check for eapi3 lock
        if self.dbformat_eapi == 3:
            locked = self.is_repository_eapi3_locked(repo)
            if locked:
                mytxt = "%s: %s." % (bold(_("Attention")),red(_("database will be ready soon")),)
                self.Entropy.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "info",
                    header = "\t"
                )
                return True
        return False

    def handle_repository_lock(self, repo):
        # get database lock
        unlocked = self.is_repository_unlocked(repo)
        if not unlocked:
            mytxt = "%s: %s. %s." % (
                bold(_("Attention")),
                red(_("Repository is being updated")),
                red(_("Try again in a few minutes")),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = "\t"
            )
            return True
        return False

    def do_eapi1_eapi2_databases_alignment(self, dbfile, dbfile_old):

        dbconn = self.Entropy.open_generic_database(dbfile, xcache = False, indexing_override = False)
        old_dbconn = self.Entropy.open_generic_database(dbfile_old, xcache = False, indexing_override = False)
        upd_rc = 0
        try:
            upd_rc = old_dbconn.alignDatabases(dbconn, output_header = "\t")
        except (self.dbapi2.OperationalError,self.dbapi2.IntegrityError,):
            pass
        old_dbconn.closeDB()
        dbconn.closeDB()
        if upd_rc > 0:
            # -1 means no changes, == force used
            # 0 means too much hassle
            shutil.move(dbfile_old,dbfile)
        return upd_rc

    def do_eapi2_inject_downloaded_dump(self, dumpfile, dbfile, cmethod):

        # load the dump into database
        mytxt = "%s %s, %s %s" % (
            red(_("Injecting downloaded dump")),
            darkgreen(etpConst[cmethod[3]]),
            red(_("please wait")),
            red("..."),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 0,
            type = "info",
            header = "\t"
        )
        dbconn = self.Entropy.open_generic_database(dbfile, xcache = False, indexing_override = False)
        rc = dbconn.doDatabaseImport(dumpfile, dbfile)
        dbconn.closeDB()
        return rc


    def do_update_security_advisories(self):
        # update Security Advisories
        try:
            securityConn = self.Entropy.Security()
            securityConn.fetch_advisories()
        except Exception, e:
            self.entropyTools.printTraceback(f = self.Entropy.clientLog)
            mytxt = "%s: %s" % (red(_("Advisories fetch error")),e,)
            self.Entropy.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = darkred(" @@ ")
            )

    def do_standard_items_download(self, repo):

        g_make_conf = os.path.basename(etpConst['spm']['global_make_conf'])
        pkg_unmask = os.path.basename(etpConst['spm']['global_package_unmask'])
        pkg_keywords = os.path.basename(etpConst['spm']['global_package_keywords'])
        pkg_use = os.path.basename(etpConst['spm']['global_package_use'])
        profile_link = etpConst['spm']['global_make_profile_link_name']
        notice_board = os.path.basename(etpRepositories[repo]['local_notice_board'])

        objects_to_unpack = ("meta_file",)

        download_items = [
            (
                "meta_file",
                etpConst['etpdatabasemetafilesfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading repository metafile")),
                    darkgreen(etpConst['etpdatabasemetafilesfile']),
                    red("..."),
                )
            ),
            (
                "ca.cert",
                etpConst['etpdatabasecacertfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading SSL CA certificate")),
                    darkgreen(etpConst['etpdatabasecacertfile']),
                    red("..."),
                )
            ),
            (
                "server.cert",
                etpConst['etpdatabaseservercertfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading SSL Server certificate")),
                    darkgreen(etpConst['etpdatabaseservercertfile']),
                    red("..."),
                )
            ),
            (
                "mask",
                etpConst['etpdatabasemaskfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading package mask")),
                    darkgreen(etpConst['etpdatabasemaskfile']),
                    red("..."),
                )
            ),
            (
                "system_mask",
                etpConst['etpdatabasesytemmaskfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading packages system mask")),
                    darkgreen(etpConst['etpdatabasesytemmaskfile']),
                    red("..."),
                )
            ),
            (
                "conflicting_tagged",
                etpConst['etpdatabaseconflictingtaggedfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading conflicting tagged packages file")),
                    darkgreen(etpConst['etpdatabaseconflictingtaggedfile']),
                    red("..."),
                )
            ),
            (
                "lic_whitelist",
                etpConst['etpdatabaselicwhitelistfile'],
                True,
                "%s %s %s" % (
                    red(_("Downloading license whitelist")),
                    darkgreen(etpConst['etpdatabaselicwhitelistfile']),
                    red("..."),
                )
            ),
            (
                "rev",
                etpConst['etpdatabaserevisionfile'],
                False,
                "%s %s %s" % (
                    red(_("Downloading revision")),
                    darkgreen(etpConst['etpdatabaserevisionfile']),
                    red("..."),
                )
            ),
            (
                "make.conf",
                g_make_conf,
                True,
                "%s %s %s" % (
                    red(_("Downloading SPM global configuration")),
                    darkgreen(g_make_conf),
                    red("..."),
                )
            ),
            (
                "package.unmask",
                pkg_unmask,
                True,
                "%s %s %s" % (
                    red(_("Downloading SPM package unmasking configuration")),
                    darkgreen(pkg_unmask),
                    red("..."),
                )
            ),
            (
                "package.keywords",
                pkg_keywords,
                True,
                "%s %s %s" % (
                    red(_("Downloading SPM package keywording configuration")),
                    darkgreen(pkg_keywords),
                    red("..."),
                )
            ),
            (
                "package.use",
                pkg_use,
                True,
                "%s %s %s" % (
                    red(_("Downloading SPM package USE flags configuration")),
                    darkgreen(pkg_use),
                    red("..."),
                )
            ),
            (
                "profile.link",
                profile_link,
                True,
                "%s %s %s" % (
                    red(_("Downloading SPM Profile configuration")),
                    darkgreen(profile_link),
                    red("..."),
                )
            ),
            (
                "notice_board",
                notice_board,
                True,
                "%s %s %s" % (
                    red(_("Downloading Notice Board")),
                    darkgreen(notice_board),
                    red("..."),
                )
            )
        ]

        def my_show_info(txt):
            self.Entropy.updateProgress(
                txt,
                importance = 0,
                type = "info",
                header = "\t",
                back = True
            )

        def my_show_down_status(message, mytype):
            self.Entropy.updateProgress(
                message,
                importance = 0,
                type = mytype,
                header = "\t"
            )

        def my_show_file_unpack(fp):
            self.Entropy.updateProgress(
                "%s: %s" % (darkgreen(_("unpacked meta file")),brown(fp),),
                header = blue(u"\t  << ")
            )

        downloaded_by_unpack = set()
        for item, myfile, ignorable, mytxt in download_items:

            # if it's been already downloaded, skip
            if myfile in downloaded_by_unpack: continue

            my_show_info(mytxt)
            mystatus = self.download_item(item, repo, disallow_redirect = True)
            mytype = 'info'

            # download failed, is it critical?
            if not mystatus:
                if ignorable:
                    message = "%s: %s." % (blue(myfile),red(_("not available, it's ok")))
                else:
                    mytype = 'warning'
                    message = "%s: %s." % (blue(myfile),darkred(_("not available, not much ok!")))
                my_show_down_status(message, mytype)
                continue

            myurl, mypath = self._construct_paths(item, repo, None)
            message = "%s: %s." % (blue(myfile),darkgreen(_("available, w00t!")))
            my_show_down_status(message, mytype)
            if item not in objects_to_unpack: continue
            if not (os.path.isfile(mypath) and os.access(mypath,os.R_OK)): continue

            while 1:
                tmpdir = os.path.join(os.path.dirname(mypath),"meta_unpack_%s" % (random.randint(1,10000),))
                if not os.path.lexists(tmpdir): break
            os.makedirs(tmpdir,0775)

            repo_dir = etpRepositories[repo]['dbpath']
            try:
                done = self.entropyTools.universal_uncompress(mypath, tmpdir, catch_empty = True)
                if not done: continue
                myfiles_to_move = set(os.listdir(tmpdir))

                # exclude files not available by default
                files_not_found_file = etpConst['etpdatabasemetafilesnotfound']
                if files_not_found_file in myfiles_to_move:
                    myfiles_to_move.remove(files_not_found_file)
                    try:
                        with open(os.path.join(tmpdir,files_not_found_file),"r") as f:
                            f_nf = [x.strip() for x in f.readlines()]
                            downloaded_by_unpack |= set(f_nf)
                    except IOError:
                        pass

                for myfile in sorted(myfiles_to_move):
                    from_mypath = os.path.join(tmpdir,myfile)
                    to_mypath = os.path.join(repo_dir,myfile)
                    try:
                        os.rename(from_mypath,to_mypath)
                        downloaded_by_unpack.add(myfile)
                        my_show_file_unpack(myfile)
                    except OSError:
                        continue

            finally:

                shutil.rmtree(tmpdir,True)
                try: os.rmdir(tmpdir)
                except OSError: pass


        mytxt = "%s: %s" % (
            red(_("Repository revision")),
            bold(str(self.Entropy.get_repository_revision(repo))),
        )
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = "\t"
        )



    def do_database_indexing(self, repo):

        # renice a bit, to avoid eating resources
        old_prio = self.Entropy.set_priority(15)
        mytxt = red("%s ...") % (_("Indexing Repository metadata"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = "\t",
            back = True
        )
        dbconn = self.Entropy.open_repository(repo)
        dbconn.createAllIndexes()
        # get list of indexes
        repo_indexes = dbconn.listAllIndexes()
        if self.Entropy.clientDbconn != None:
            try: # client db can be absent
                client_indexes = self.Entropy.clientDbconn.listAllIndexes()
                if repo_indexes != client_indexes:
                    self.Entropy.clientDbconn.createAllIndexes()
            except:
                pass
        self.Entropy.set_priority(old_prio)


    def sync(self):

        # close them
        self.Entropy.close_all_repositories()

        # let's dance!
        mytxt = darkgreen("%s ...") % (_("Repositories synchronization"),)
        self.Entropy.updateProgress(
            mytxt,
            importance = 2,
            type = "info",
            header = darkred(" @@ ")
        )

        gave_up = self.Entropy.lock_check(self.Entropy._resources_run_check_lock)
        if gave_up:
            return 3

        locked = self.Entropy.application_lock_check()
        if locked:
            self.Entropy._resources_run_remove_lock()
            return 4

        # lock
        self.Entropy._resources_run_create_lock()
        try:
            rc = self.run_sync()
        except:
            self.Entropy._resources_run_remove_lock()
            raise
        if rc: return rc

        # remove lock
        self.Entropy._resources_run_remove_lock()

        if (self.notAvailable >= len(self.reponames)):
            return 2
        elif (self.notAvailable > 0):
            return 1

        return 0

