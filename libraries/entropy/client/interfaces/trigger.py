# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package installation triggers Interface}.

"""

from __future__ import with_statement
import subprocess
import shutil
from entropy.client.interfaces.client import Client
from entropy.const import *
from entropy.exceptions import *
from entropy.output import *
from entropy.i18n import _

class Trigger:

    VALID_PHASES = ("preinstall", "postinstall", "preremove", "postremove",)

    import entropy.tools as entropyTools
    def __init__(self, entropy_client, phase, pkgdata, package_action = None):

        if not isinstance(entropy_client, Client):
            mytxt = "A valid Entropy Instance is needed"
            raise AttributeError, mytxt

        self.Entropy = entropy_client
        self.pkgdata = pkgdata
        self.prepared = False
        self.triggers = []
        self._trigger_data = {}
        self.package_action = package_action

        self.spm_support = True
        try:
            Spm = self.Entropy.Spm()
            self.Spm = Spm
        except Exception, e:
            self.entropyTools.print_traceback()
            mytxt = darkred("%s, %s: %s, %s !") % (
                _("Source Package Manager interface can't be loaded"),
                _("Error"),
                e,
                _("please fix"),
            )
            self.Entropy.updateProgress(
                mytxt,
                importance = 0,
                header = bold(" !!! ")
            )
            self.spm_support = False

        self.phase = phase
        # validate phase
        if self.phase not in Trigger.VALID_PHASES:
            mytxt = "Valid phases: %s" % (Trigger.VALID_PHASES,)
            raise AttributeError, mytxt

    def prepare(self):
        func = getattr(self, self.phase)
        self.triggers = func()
        self.prepared = True
        return len(self.triggers) > 0

    def run(self):
        for trigger_func in self.triggers:
            trigger_func()

    def kill(self):
        self.prepared = False
        self._trigger_data.clear()
        del self.triggers[:]

    def postinstall(self):

        functions = []
        if self.spm_support:
            while 1:
                if self.pkgdata['spm_phases'] != None:
                    if etpConst['spm']['postinst_phase'] not \
                        in self.pkgdata['spm_phases']:
                        break
                functions.append(self.trigger_spm_postinstall)
                break

        # load linker paths
        ldpaths = self.Entropy.entropyTools.collect_linker_paths()
        for x in self.pkgdata['content']:

            if self.trigger_env_update not in functions:
                if x.startswith('/etc/env.d/'):
                    functions.append(self.trigger_env_update)

            if self.trigger_run_ldconfig not in functions:
                if (os.path.dirname(x) in ldpaths):
                    if x.find(".so") > -1:
                        functions.append(self.trigger_run_ldconfig)

        if self.pkgdata['trigger']:
            functions.append(self.trigger_call_ext_postinstall)

        del ldpaths
        return functions

    def preinstall(self):

        functions = []

        # Portage phases
        if self.spm_support:
            while 1:
                if self.pkgdata['spm_phases'] != None:
                    if etpConst['spm']['preinst_phase'] not \
                        in self.pkgdata['spm_phases']:
                        break
                functions.append(self.trigger_spm_preinstall)
                break

        if self.pkgdata['trigger']:
            functions.append(self.trigger_call_ext_preinstall)

        return functions

    def postremove(self):

        functions = []

        # load linker paths
        ldpaths = self.Entropy.entropyTools.collect_linker_paths()

        for x in self.pkgdata['removecontent']:

            # env_update; run_ldconfig
            if len(functions) == 2:
                break # no need to go further

            if self.trigger_env_update not in functions:
                if x.startswith('/etc/env.d/'):
                    functions.append(self.trigger_env_update)

            if self.trigger_run_ldconfig not in functions:
                if (os.path.dirname(x) in ldpaths):
                    if x.find(".so") > -1:
                        functions.append(self.trigger_run_ldconfig)

        if self.pkgdata['trigger']:
            functions.append(self.trigger_call_ext_postremove)

        del ldpaths
        return functions


    def preremove(self):

        functions = []

        # Portage hook
        if self.spm_support:

            while 1:
                if self.pkgdata['spm_phases'] != None:
                    if etpConst['spm']['prerm_phase'] not \
                        in self.pkgdata['spm_phases']:
                        break
                functions.append(self.trigger_spm_preremove)
                break

            # doing here because we need /var/db/pkg stuff
            # in place and also because doesn't make any difference
            while 1:
                if self.pkgdata['spm_phases'] != None:
                    if etpConst['spm']['postrm_phase'] not \
                        in self.pkgdata['spm_phases']:
                        break
                functions.append(self.trigger_spm_postremove)
                break

        if self.pkgdata['trigger']:
            functions.append(self.trigger_call_ext_preremove)

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
        mytxt = "%s %s" % (_("Regenerating"), "/etc/ld.so.cache",)
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
        if os.access(etpConst['systemroot']+ "/usr/sbin/env-update", os.X_OK):
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

    def trigger_spm_postinstall(self):

        stdfile = open("/dev/null", "w")
        oldstderr = sys.stderr
        oldstdout = sys.stdout
        sys.stderr = stdfile

        myebuild = None
        if os.path.isdir(self.pkgdata['xpakdir']) and \
            os.access(self.pkgdata['xpakdir'], os.R_OK):

            myebuild = [self.pkgdata['xpakdir']+"/"+x for x \
                in os.listdir(self.pkgdata['xpakdir']) if \
                x.endswith(etpConst['spm']['source_build_ext'])]

        if myebuild:
            myebuild = myebuild[0]
            portage_atom = self.pkgdata['category'] + "/" + \
                self.pkgdata['name'] + "-" + self.pkgdata['version']
            self.Entropy.updateProgress(
                "SPM: %s" % (brown(_("post-install phase")),),
                importance = 0,
                header = red("   ## ")
            )
            try:

                if not etpUi['debug']:
                    sys.stdout = stdfile
                self.__ebuild_setup_phase(myebuild, portage_atom)
                if not etpUi['debug']:
                    sys.stdout = oldstdout

                rc = self.Spm.execute_package_phase(portage_atom, myebuild,
                    "postinstall",
                    work_dir = self.pkgdata['unpackdir'],
                    licenses_accepted = self.pkgdata['accept_license']
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[POST] ATTENTION Cannot properly run Source Package Manager post-install (pkg_postinst()) trigger for " + \
                        str(portage_atom) + ". Something bad happened."
                        )

            except Exception, e:
                sys.stdout = oldstdout
                self.entropyTools.print_traceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[POST] ATTENTION Cannot run Source Package Manager trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Source Package Manager trigger for")),
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
        env_file = os.path.join(self.pkgdata['unpackdir'], "portage",
            portage_atom, "temp/environment")
        if not os.path.isfile(env_file):

            # FIXME: please remove as soon as upstream fixes it
            # FIXME: workaround for buggy linux-info.eclass not being
            # ported to EAPI=2 yet.
            # It is required to make depmod running properly for the
            # kernel modules inside this ebuild
            # fix KV_OUT_DIR= inside environment
            bz2envfile = os.path.join(self.pkgdata['xpakdir'],
                "environment.bz2")
            if "linux-info" in self.pkgdata['eclasses'] and \
                os.path.isfile(bz2envfile) and self.pkgdata['versiontag']:

                import bz2
                envfile = self.Entropy.entropyTools.unpack_bzip2(bz2envfile)
                bzf = bz2.BZ2File(bz2envfile,"w")
                f = open(envfile,"r")
                line = f.readline()
                while line:
                    if line == "KV_OUT_DIR=/usr/src/linux\n":
                        line = "KV_OUT_DIR=/lib/modules/%s/build\n" % (
                            self.pkgdata['versiontag'],)
                    bzf.write(line)
                    line = f.readline()
                f.close()
                bzf.close()
                os.remove(envfile)

            rc = self.Spm.execute_package_phase(portage_atom, ebuild,
                "setup",
                work_dir = self.pkgdata['unpackdir'],
                licenses_accepted = self.pkgdata['accept_license']
            )
            if rc == 1:
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[POST] ATTENTION Cannot properly run Source Package Manager setup"
                    " phase for "+str(portage_atom)+". Something bad happened."
                )
        return rc


    def trigger_spm_preinstall(self):

        stdfile = open("/dev/null", "w")
        oldstderr = sys.stderr
        oldstdout = sys.stdout
        sys.stderr = stdfile

        myebuild = None
        if os.path.isdir(self.pkgdata['xpakdir']) and \
            os.access(self.pkgdata['xpakdir'], os.R_OK):

            myebuild = [self.pkgdata['xpakdir']+"/"+x for x in \
                os.listdir(self.pkgdata['xpakdir']) if \
                x.endswith(etpConst['spm']['source_build_ext'])]

        if myebuild:
            myebuild = myebuild[0]
            portage_atom = self.pkgdata['category'] + "/" + \
                self.pkgdata['name'] + "-" + self.pkgdata['version']
            self.Entropy.updateProgress(
                "SPM: %s" % (brown(_("pre-install phase")),),
                importance = 0,
                header = red("   ## ")
            )
            try:

                if not etpUi['debug']:
                    sys.stdout = stdfile
                self.__ebuild_setup_phase(myebuild, portage_atom)
                if not etpUi['debug']:
                    sys.stdout = oldstdout

                rc = self.Spm.execute_package_phase(portage_atom, myebuild,
                    "preinstall",
                    work_dir = self.pkgdata['unpackdir'],
                    licenses_accepted = self.pkgdata['accept_license']
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[PRE] ATTENTION Cannot properly run Source Package Manager pre-install (pkg_preinst()) trigger for " + \
                        str(portage_atom)+". Something bad happened."
                    )
            except Exception, e:
                sys.stdout = oldstdout
                self.entropyTools.print_traceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] ATTENTION Cannot run Source Package Manager preinst trigger for "+portage_atom+"!! "+str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Source Package Manager trigger for")),
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

    def trigger_spm_preremove(self):

        stdfile = open("/dev/null", "w")
        oldstderr = sys.stderr
        sys.stderr = stdfile

        portage_atom = self.pkgdata['category'] + "/" + self.pkgdata['name'] + \
            "-" + self.pkgdata['version']

        myebuild = self.Spm.get_installed_package_build_script_path(
            portage_atom)

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
                "SPM: %s" % (brown(_("pre-remove phase")),),
                importance = 0,
                header = red("   ## ")
            )
            try:
                rc = self.Spm.execute_package_phase(portage_atom, myebuild,
                    "preremove",
                    work_dir = etpConst['entropyunpackdir']+"/"+portage_atom,
                    licenses_accepted = self.pkgdata['accept_license']
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[PRE] ATTENTION Cannot properly run Source Package Manager trigger for " + \
                        str(portage_atom)+". Something bad happened."
                    )
            except Exception, e:
                sys.stderr = oldstderr
                stdfile.close()
                self.entropyTools.print_traceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] ATTENTION Cannot run Source Package Manager " + \
                        "pre-remove trigger for " + portage_atom + "!! " + \
                        str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Source Package Manager trigger for")),
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

    def trigger_spm_postremove(self):

        stdfile = open("/dev/null", "w")
        oldstderr = sys.stderr
        sys.stderr = stdfile

        portage_atom = self.pkgdata['category'] + "/" + self.pkgdata['name'] + \
            "-" + self.pkgdata['version']

        myebuild = self.Spm.get_installed_package_build_script_path(
            portage_atom)

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
                "SPM: %s" % (brown(_("post-remove phase")),),
                importance = 0,
                header = red("   ## ")
            )
            try:
                rc = self.Spm.execute_package_phase(portage_atom, myebuild,
                    "postremove",
                    work_dir = etpConst['entropyunpackdir']+"/"+portage_atom,
                    licenses_accepted = self.pkgdata['accept_license']
                )
                if rc == 1:
                    self.Entropy.clientLog.log(
                        ETP_LOGPRI_INFO,
                        ETP_LOGLEVEL_NORMAL,
                        "[PRE] ATTENTION Cannot properly run Source Package Manager postremove trigger for " + \
                        str(portage_atom)+". Something bad happened."
                    )
            except Exception, e:
                sys.stderr = oldstderr
                stdfile.close()
                self.entropyTools.print_traceback()
                self.Entropy.clientLog.log(
                    ETP_LOGPRI_INFO,
                    ETP_LOGLEVEL_NORMAL,
                    "[PRE] ATTENTION Cannot run Source Package Manager postremove trigger for " + \
                    portage_atom+"!! "+str(Exception)+": "+str(e)
                )
                mytxt = "%s: %s %s. %s. %s: %s" % (
                    bold(_("QA")),
                    brown(_("Cannot run Source Package Manager trigger for")),
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
            self.Spm._ebuild_env_setup_hook(myebuild)

        return myebuild

    def _remove_overlayed_ebuild(self):

        if not self.myebuild_moved:
            return
        if not os.path.isfile(self.myebuild_moved):
            return

        mydir = os.path.dirname(self.myebuild_moved)
        shutil.rmtree(mydir, True)
        mydir = os.path.dirname(mydir)
        content = os.listdir(mydir)
        while not content:
            os.rmdir(mydir)
            mydir = os.path.dirname(mydir)
            content = os.listdir(mydir)
