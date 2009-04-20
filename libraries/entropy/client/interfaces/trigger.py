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
import subprocess
import shutil
from entropy.client.interfaces.client import Client
from entropy.const import *
from entropy.exceptions import *
from entropy.output import *
from entropy.i18n import _

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
                self.entropyTools.print_traceback()
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
        self.prepared = True
        return len(self.triggers) > 0

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
            while 1:
                if self.pkgdata['spm_phases'] != None:
                    if etpConst['spm']['postinst_phase'] not \
                        in self.pkgdata['spm_phases']:
                        break
                functions.append('ebuild_postinstall')
                break

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
        ldpaths = self.Entropy.entropyTools.collect_linker_paths()
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

        # Portage phases
        if self.gentoo_compat:
            while 1:
                if self.pkgdata['spm_phases'] != None:
                    if etpConst['spm']['preinst_phase'] not \
                        in self.pkgdata['spm_phases']:
                        break
                functions.append('ebuild_preinstall')
                break

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
        ldpaths = self.Entropy.entropyTools.collect_linker_paths()

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

            while 1:
                if self.pkgdata['spm_phases'] != None:
                    if etpConst['spm']['prerm_phase'] not \
                        in self.pkgdata['spm_phases']:
                        break
                functions.append('ebuild_preremove')
                break

            # doing here because we need /var/db/pkg stuff
            # in place and also because doesn't make any difference
            while 1:
                if self.pkgdata['spm_phases'] != None:
                    if etpConst['spm']['postrm_phase'] not \
                        in self.pkgdata['spm_phases']:
                        break
                functions.append('ebuild_postremove')
                break

        # opengl configuration
        if (self.pkgdata['category'] == "x11-drivers") and \
            (self.pkgdata['name'].startswith("nvidia-") or \
                self.pkgdata['name'].startswith("ati-")):

            if "ebuild_preremove" in functions:
                functions.remove("ebuild_preremove")
            if "ebuild_postremove" in functions:
                # disabling gentoo postinstall since we reimplemented it
                functions.remove("ebuild_postremove")
            if self.package_action in ("remove",):
                functions.append("openglsetup_xorg")

        for x in self.pkgdata['removecontent']:
            if x.startswith("/boot"):
                functions.append('mountboot')
                break

        if self.pkgdata['trigger']:
            functions.append('call_ext_preremove')

        return functions


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
            tb = self.entropyTools.get_traceback()
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

        def __init__(self, Entropy):
            self.Entropy = Entropy
            import entropy.tools as entropyTools
            self.entropyTools = entropyTools

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

            etp_branch = pkgdata.get('branch')
            if isinstance(etp_branch,unicode):
                etp_branch = etp_branch.encode('utf-8')

            slot = pkgdata.get('slot')
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

            chost, cflags, cxxflags = pkgdata.get('chost'), \
                pkgdata.get('cflags'), pkgdata.get('cxxflags')

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

        def __init__(self, Entropy):
            self.Entropy = Entropy

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
            triggerfile = "%s%s" % (tg_pfx,self.Entropy.entropyTools.get_random_number(),)
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
            my = self.EntropyShSandbox(self.Entropy)
        else:
            my = self.EntropyPySandbox(self.Entropy)
        return my.run(self.phase, self.pkgdata, triggerfile)


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
            if etpUi['quiet']: quietstring = " &> /dev/null"
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
            if etpUi['quiet']: quietstring = "&> /dev/null"
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
            self.trigger_configure_boot_grub(kernel, initramfs)

    # FIXME: this only supports grub (no lilo support)
    def trigger_removebootablekernel(self):
        kernels = [x for x in self.pkgdata['content'] if \
            x.startswith("/boot/kernel-")]
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
            fstab = self.Entropy.entropyTools.list_to_utf8(fstab)
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
                        mydir = etpConst['systemroot']+"/usr/src/linux."+str(self.Entropy.entropyTools.get_random_number())
                        while os.path.isdir(mydir):
                            mydir = etpConst['systemroot']+"/usr/src/linux."+str(self.Entropy.entropyTools.get_random_number())
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

                sys.stdout = stdfile
                self.__ebuild_setup_phase(myebuild, portage_atom)
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
                self.entropyTools.print_traceback()
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

    def __ebuild_setup_phase(self, ebuild, portage_atom):
        rc = 0
        env_file = self.pkgdata['unpackdir']+"/portage/"+portage_atom+"/temp/environment"
        if not os.path.isfile(env_file):
            # if environment is not yet created, we need to run pkg_setup()
            rc = self.Spm.spm_doebuild(
                ebuild,
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
                    "[POST] ATTENTION Cannot properly run Portage pkg_setup()"
                    " phase for "+str(portage_atom)+". Something bad happened."
                )
        return rc


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
                self.__ebuild_setup_phase(myebuild, portage_atom)
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
                self.entropyTools.print_traceback()
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
                self.entropyTools.print_traceback()
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
                self.entropyTools.print_traceback()
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
            envfile = self.Entropy.entropyTools.unpack_bzip2(bz2envfile)
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
                subprocess.call("echo '/usr/bin/gcc-config %s' | chroot %s %s" % (
                    profile, etpConst['systemroot'], redirect,), shell = True)
            else:
                subprocess.call('/usr/bin/gcc-config %s %s' % (
                    profile, redirect,), shell = True)
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
                moduledb = self.Entropy.entropyTools.list_to_utf8(moduledb)
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
            subprocess.call('/sbin/depmod -a -b %s -r %s &> /dev/null' % (
                myroot, name,), shell = True)
        return 0

    def __get_entropy_kernel_grub_line(self, kernel):
        sys_name = self.Entropy.SystemSettings['system']['name']
        return "title=%s (%s)\n" % (sys_name, os.path.basename(kernel),)

    '''
    @description: append kernel entry to grub.conf
    @output: returns int() as exit status
    '''
    def trigger_configure_boot_grub(self, kernel, initramfs):

        if not os.path.isdir(etpConst['systemroot']+"/boot/grub"):
            os.makedirs(etpConst['systemroot']+"/boot/grub")

        if os.path.isfile(etpConst['systemroot']+"/boot/grub/grub.conf"):

            # open in append
            grub = open(etpConst['systemroot']+"/boot/grub/grub.conf","aw")
            shutil.copy2(etpConst['systemroot']+"/boot/grub/grub.conf",
                etpConst['systemroot']+"/boot/grub/grub.conf.old.add")
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
                if (line.find("kernel") != 1) and \
                    (line.find(os.path.basename(kernel)) != -1) and not \
                    line.strip().startswith("#"):

                    grubtest.close()
                    return
        else:

            # create
            boot_dev = "(hd0,0)"
            grub = open(etpConst['systemroot']+"/boot/grub/grub.conf","w")
            # write header - guess (hd0,0)... since it is weird
            # having a running system without a bootloader, at least, grub.
            grub.write("default=0\ntimeout=10\n")

        grub.write(self.__get_entropy_kernel_grub_line(kernel))
        grub.write("\troot "+boot_dev+"\n")
        grub.write("\tkernel "+kernel+"\n")
        if initramfs:
            grub.write("\tinitrd "+initramfs+"\n")
        grub.write("\tsavedefault\n")
        grub.write("\n")
        grub.flush()
        grub.close()

    def trigger_remove_boot_grub(self, kernel,initramfs):

        if os.path.isdir(etpConst['systemroot']+"/boot/grub") and \
            os.path.isfile(etpConst['systemroot']+"/boot/grub/grub.conf"):

            shutil.copy2(etpConst['systemroot']+"/boot/grub/grub.conf",
                etpConst['systemroot']+"/boot/grub/grub.conf.old.remove")
            f = open(etpConst['systemroot']+"/boot/grub/grub.conf","r")
            grub_conf = f.readlines()
            f.close()

            content = [unicode(x,'raw_unicode_escape') for x in grub_conf]
            try:
                kernel, initramfs = (unicode(kernel,'raw_unicode_escape'),
                    unicode(initramfs,'raw_unicode_escape'),)
            except TypeError:
                pass

            new_conf = []
            skip = False
            for line in content:

                kernel_grub_line = self.__get_entropy_kernel_grub_line(kernel)
                if (line.find(kernel_grub_line) != -1):
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
