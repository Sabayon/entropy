# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package installation triggers Interface}.

"""

import subprocess
import shutil
from entropy.client.interfaces.client import Client
from entropy.const import *
from entropy.exceptions import *
from entropy.output import *
from entropy.i18n import _

class Trigger:

    VALID_PHASES = ("preinstall", "postinstall", "preremove", "postremove",)
    ENV_VARS_DIR = etpConst['spm']['env_dir_reference']
    ENV_UPDATE_HOOK = etpConst['spm']['env_update_cmd']
    PHASES = {
        'preinstall': "preinstall",
        'postinstall': "postinstall",
        'preremove': "preremove",
        'postremove': "postremove",
    }

    import entropy.tools as entropyTools
    def __init__(self, entropy_client, phase, pkgdata, package_action = None):

        if not isinstance(entropy_client, Client):
            mytxt = "A valid Entropy Instance is needed"
            raise AttributeError(mytxt)

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
        except Exception as e:
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
            raise AttributeError(mytxt)

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
            while True:
                if self.pkgdata['spm_phases'] != None:
                    if etpConst['spm']['postinst_phase'] not \
                        in self.pkgdata['spm_phases']:
                        break
                functions.append(self.trigger_spm_postinstall)
                break

        cont_dirs = set((os.path.dirname(x) for x in self.pkgdata['content']))

        if Trigger.ENV_VARS_DIR in cont_dirs:
            functions.append(self.trigger_env_update)
        else:
            ldpaths = self.Entropy.entropyTools.collect_linker_paths()
            if len(cont_dirs) != len(cont_dirs - set(ldpaths)):
                functions.append(self.trigger_env_update)

        if self.pkgdata['trigger']:
            functions.append(self.trigger_call_ext_postinstall)

        return functions

    def preinstall(self):

        functions = []

        # Portage phases
        if self.spm_support:
            while True:
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

        cont_dirs = set((os.path.dirname(x) for x in \
            self.pkgdata['removecontent']))

        if Trigger.ENV_VARS_DIR in cont_dirs:
            functions.append(self.trigger_env_update)
        else:
            ldpaths = self.Entropy.entropyTools.collect_linker_paths()
            if len(cont_dirs) != len(cont_dirs - set(ldpaths)):
                functions.append(self.trigger_env_update)

        if self.pkgdata['trigger']:
            functions.append(self.trigger_call_ext_postremove)

        return functions


    def preremove(self):

        functions = []

        # Portage hook
        if self.spm_support:

            while True:
                if self.pkgdata['spm_phases'] != None:
                    if etpConst['spm']['prerm_phase'] not \
                        in self.pkgdata['spm_phases']:
                        break
                functions.append(self.trigger_spm_preremove)
                break

            # doing here because we need /var/db/pkg stuff
            # in place and also because doesn't make any difference
            while True:
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
        except Exception as e:
            mykey = self.pkgdata['category']+"/"+self.pkgdata['name']
            tb = self.entropyTools.get_traceback()
            self.Entropy.updateProgress(tb, importance = 0, type = "error")
            self.Entropy.clientLog.write(tb)
            self.Entropy.clientLog.log(
                ETP_LOGPRI_INFO,
                ETP_LOGLEVEL_NORMAL,
                "[POST] ATTENTION Cannot run External trigger for " + \
                    mykey + "!! " + str(Exception) + ": " + str(e)
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
            if const_isunicode(category):
                category = category.encode('utf-8')

            pn = pkgdata.get('name')
            if const_isunicode(pn):
                pn = pn.encode('utf-8')

            pv = pkgdata.get('version')
            if const_isunicode(pv):
                pv = pv.encode('utf-8')

            pr = self.entropyTools.dep_get_portage_revision(pv)
            pvr = pv
            if pr == "r0": pvr += "-%s" % (pr,)

            pet = pkgdata.get('versiontag')
            if const_isunicode(pet):
                pet = pet.encode('utf-8')

            per = pkgdata.get('revision')
            if const_isunicode(per):
                per = per.encode('utf-8')

            etp_branch = pkgdata.get('branch')
            if const_isunicode(etp_branch):
                etp_branch = etp_branch.encode('utf-8')

            slot = pkgdata.get('slot')
            if const_isunicode(slot):
                slot = slot.encode('utf-8')

            pkgatom = pkgdata.get('atom')
            pkgkey = self.entropyTools.dep_getkey(pkgatom)
            pvrte = pkgatom[len(pkgkey)+1:]
            if const_isunicode(pvrte):
                pvrte = pvrte.encode('utf-8')

            etpapi = pkgdata.get('etpapi')
            if const_isunicode(etpapi):
                etpapi = etpapi.encode('utf-8')

            p = pkgatom
            if const_isunicode(p):
                p = p.encode('utf-8')

            chost, cflags, cxxflags = pkgdata.get('chost'), \
                pkgdata.get('cflags'), pkgdata.get('cxxflags')

            chost = pkgdata.get('etpapi')
            if const_isunicode(chost):
                chost = chost.encode('utf-8')

            cflags = pkgdata.get('etpapi')
            if const_isunicode(cflags):
                cflags = cflags.encode('utf-8')

            cxxflags = pkgdata.get('etpapi')
            if const_isunicode(cxxflags):
                cxxflags = cxxflags.encode('utf-8')

            # Not mandatory variables

            eclasses = ' '.join(pkgdata.get('eclasses', []))
            if const_isunicode(eclasses):
                eclasses = eclasses.encode('utf-8')

            unpackdir = pkgdata.get('unpackdir', '')
            if const_isunicode(unpackdir):
                unpackdir = unpackdir.encode('utf-8')

            imagedir = pkgdata.get('imagedir', '')
            if const_isunicode(imagedir):
                imagedir = imagedir.encode('utf-8')

            sb_dirs = [unpackdir, imagedir]
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
                with open(trigger_file) as trig_f:
                    exec(compile(trig_f.read(), trigger_file, 'exec'))
            if os.path.isfile(trigger_file):
                os.remove(trigger_file)
            return my_ext_status

    def do_trigger_call_ext_generic(self):

        # if mute, supress portage output
        if etpUi['mute']:
            oldsystderr = sys.stderr
            oldsysstdout = sys.stdout
            stdfile = open("/dev/null", "w")
            sys.stdout = stdfile
            sys.stderr = stdfile

        tg_pfx = "%s/trigger-" % (etpConst['entropyunpackdir'],)
        while True:
            triggerfile = "%s%s" % (tg_pfx, self.Entropy.entropyTools.get_random_number(),)
            if not os.path.isfile(triggerfile): break

        triggerdir = os.path.dirname(triggerfile)
        if not os.path.isdir(triggerdir):
            os.makedirs(triggerdir)

        f = open(triggerfile, "w")
        chunk = 1024
        start = 0
        while True:
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

        f = open(triggerfile, "r")
        interpreter = f.readline().strip()
        f.close()
        entropy_sh = etpConst['trigger_sh_interpreter']
        if interpreter == "#!%s" % (entropy_sh,):
            os.chmod(triggerfile, 0o775)
            my = self.EntropyShSandbox(self.Entropy)
        else:
            my = self.EntropyPySandbox(self.Entropy)
        return my.run(self.phase, self.pkgdata, triggerfile)

    def trigger_env_update(self):

        self.Entropy.clientLog.log(
            ETP_LOGPRI_INFO,
            ETP_LOGLEVEL_NORMAL,
            "[POST] Running env-update"
        )
        subprocess.call([Trigger.ENV_UPDATE_HOOK])

    def trigger_spm_postinstall(self):

        self.Entropy.updateProgress(
            "SPM: %s" % (brown(_("post-install phase")),),
            importance = 0,
            header = red("   ## ")
        )
        return self.Spm.execute_package_phase(self.pkgdata,
            Trigger.PHASES['postinstall'])

    def trigger_spm_preinstall(self):

        self.Entropy.updateProgress(
            "SPM: %s" % (brown(_("pre-install phase")),),
            importance = 0,
            header = red("   ## ")
        )
        return self.Spm.execute_package_phase(self.pkgdata,
            Trigger.PHASES['preinstall'])

    def trigger_spm_preremove(self):

        self.Entropy.updateProgress(
            "SPM: %s" % (brown(_("pre-remove phase")),),
            importance = 0,
            header = red("   ## ")
        )
        return self.Spm.execute_package_phase(self.pkgdata,
            Trigger.PHASES['preremove'])

    def trigger_spm_postremove(self):

        self.Entropy.updateProgress(
            "SPM: %s" % (brown(_("post-remove phase")),),
            importance = 0,
            header = red("   ## ")
        )
        return self.Spm.execute_package_phase(self.pkgdata,
            Trigger.PHASES['postremove'])
