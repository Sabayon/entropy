# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package installation triggers Interface}.

"""
import codecs
import os
import subprocess
import sys
import threading

from entropy.const import etpConst, etpSys, const_convert_to_rawstring, \
    const_mkstemp
from entropy.output import brown, bold, darkred, red, teal, purple
from entropy.i18n import _

import entropy.dep
import entropy.tools


class Trigger(object):

    """
    Entropy Client Package installation phases trigger functions.
    The place where Source Package Manager (SPM) is called in order to
    work out installation, removal phases (setup, pre-install, post-install,
    post-remove, etc).
    """

    VALID_PHASES = ("setup", "preinstall", "postinstall", "preremove",
        "postremove",)
    INSTALL_INFO_EXEC = "/usr/bin/install-info"

    def __init__(self, entropy_client, action, phase, package_metadata,
        action_metadata):
        """
        Trigger manager interface constructor.

        @param entropy_client: Entropy Client interface object
        @type entropy_client: entropy.client.interfaces.client.Client
        @param action: package handling action, can be "install", "remove",
            etc. see entropy.client.interfaces.package.Package
        @type action: string
        @param phase: the package phase that is required to be run, can be
            either on of the Trigger.VALID_PHASES values.
        @type phase: string
        @param package_metadata: package metadata that can be used by
            this Trigger interface
        @type package_metadata: dict
        @param action_metadata: trigger metadata bound to action (and not
            to phase)
        @type action_metadata: dict or None
        """
        self._entropy = entropy_client
        self._pkgdata = package_metadata
        self._action = action
        self._action_metadata = action_metadata
        self._prepared = False
        self._triggers = []
        self._trigger_data = {}

        self._real_spm = None
        self._real_spm_lock = threading.Lock()

        self._phase = phase
        # validate phase
        if self._phase not in Trigger.VALID_PHASES:
            mytxt = "Valid phases: %s" % (Trigger.VALID_PHASES,)
            raise AttributeError(mytxt)

    @property
    def _spm(self):
        """
        Return the Source Package Manager object.
        """
        with self._real_spm_lock:
            if self._real_spm is None:
                self._real_spm = self._entropy.Spm()

        return self._real_spm

    def prepare(self):
        """
        This method must be called right after the constructor in order
        to prepare data strctures used in the run() phase.
        @return: number of triggers that will be executed once run() is called
        @rtype: int
        """
        if not self._prepared:
            func = getattr(self, "_" + self._phase)
            self._triggers = func()
            self._prepared = True
        return len(self._triggers) > 0

    def run(self):
        """
        Run the actual triggers, this method must be called after prepare().
        This method returns an error code, non-zero values must be considered
        an error and further phase execution must be stopped.
        """
        assert self._prepared, "prepare() not called"

        for trigger_func in self._triggers:
            code = trigger_func()
            if code != 0:
                return code
        return 0

    def kill(self):
        """
        Kill all the data structures created on prepare(). This method must
        be called after run().
        """
        self._prepared = False
        self._trigger_data.clear()
        del self._triggers[:]

    def _postinstall(self):
        """
        The postinstall phases generator.
        """
        functions = []
        spm_class = self._entropy.Spm_class()

        phases_map = spm_class.package_phases_map()
        while True:
            if self._pkgdata['spm_phases'] is not None:
                if phases_map.get('postinstall') not \
                    in self._pkgdata['spm_phases']:
                    break
            functions.append(self._trigger_spm_postinstall)
            break

        cont_dirs = self._pkgdata['affected_directories']
        ldpaths = entropy.tools.collect_linker_paths()
        if len(cont_dirs) != len(cont_dirs - set(ldpaths)):
            functions.insert(0, self._trigger_env_update)
        else:
            # check if environment dirs have been touched
            env_dirs = spm_class.ENV_DIRS
            if len(env_dirs) != len(env_dirs - cont_dirs):
                functions.insert(0, self._trigger_env_update)

        if self._pkgdata['affected_infofiles']:
            functions.append(self._trigger_infofile_install)

        if self._pkgdata['trigger']:
            functions.append(self._trigger_call_ext_postinstall)
        return functions

    def _setup(self):
        """
        The setup phase generator.
        """
        functions = []

        append_setup = False
        if self._pkgdata['spm_phases'] != None:
            if "setup" in self._pkgdata['spm_phases']:
                append_setup = True
        else:
            append_setup = True
        if append_setup:
            functions.append(self._trigger_spm_setup)

        if self._pkgdata['trigger']:
            functions.append(self._trigger_call_ext_setup)

        return functions

    def _preinstall(self):
        """
        The preinstall phases generator.
        """
        functions = []
        spm_class = self._entropy.Spm_class()

        phases_map = spm_class.package_phases_map()
        while True:
            if self._pkgdata['spm_phases'] != None:
                if phases_map.get('preinstall') not \
                    in self._pkgdata['spm_phases']:
                    break
            functions.append(self._trigger_spm_preinstall)
            break

        if self._pkgdata['trigger']:
            functions.append(self._trigger_call_ext_preinstall)

        return functions

    def _postremove(self):
        """
        The postremove phases generator.
        """
        functions = []
        spm_class = self._entropy.Spm_class()

        phases_map = spm_class.package_phases_map()

        # doing here because we need /var/db/pkg stuff
        # in place and also because doesn't make any difference
        while True:
            if self._pkgdata['spm_phases'] != None:
                if phases_map.get('postremove') not \
                    in self._pkgdata['spm_phases']:
                    break
            functions.append(self._trigger_spm_postremove)
            break

        cont_dirs = self._pkgdata['affected_directories']
        ldpaths = entropy.tools.collect_linker_paths()
        if len(cont_dirs) != len(cont_dirs - set(ldpaths)):
            functions.insert(0, self._trigger_env_update)
        else:
            # check if environment dirs have been touched
            env_dirs = spm_class.ENV_DIRS
            if len(env_dirs) != len(env_dirs - cont_dirs):
                functions.insert(0, self._trigger_env_update)

        if self._pkgdata['trigger']:
            functions.append(self._trigger_call_ext_postremove)

        return functions

    def _preremove(self):
        """
        The preremove phases generator.
        """
        functions = []
        spm_class = self._entropy.Spm_class()

        phases_map = spm_class.package_phases_map()

        while True:
            if self._pkgdata['spm_phases'] != None:
                if phases_map.get('preremove') not \
                    in self._pkgdata['spm_phases']:
                    break
            functions.append(self._trigger_spm_preremove)
            break

        if self._pkgdata['trigger']:
            functions.append(self._trigger_call_ext_preremove)

        return functions

    def _trigger_call_ext_setup(self):
        return self._trigger_call_ext_generic()

    def _trigger_call_ext_preinstall(self):
        return self._trigger_call_ext_generic()

    def _trigger_call_ext_postinstall(self):
        return self._trigger_call_ext_generic()

    def _trigger_call_ext_preremove(self):
        return self._trigger_call_ext_generic()

    def _trigger_call_ext_postremove(self):
        return self._trigger_call_ext_generic()

    def _trigger_call_ext_generic(self):
        try:
            return self._do_trigger_call_ext_generic()
        except Exception as err:
            mykey = self._pkgdata['category']+"/"+self._pkgdata['name']
            tback = entropy.tools.get_traceback()
            self._entropy.output(tback, importance = 0, level = "error")
            self._entropy.logger.write(tback)
            self._entropy.logger.log(
                "[Trigger]",
                etpConst['logging']['normal_loglevel_id'],
                "[POST] ATTENTION Cannot run External trigger for " + \
                    mykey + "!! " + str(Exception) + ": " + repr(err)
            )
            mytxt = "%s: %s %s. %s." % (
                bold(_("QA")),
                brown(_("Cannot run External trigger for")),
                bold(mykey),
                brown(_("Please report it")),
            )
            self._entropy.output(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return 0

    class _EntropyShSandbox:

        def __init__(self, entropy_client):
            self._entropy = entropy_client

        def __env_setup(self, stage, pkgdata):

            # mandatory variables
            category = pkgdata.get('category')
            category = const_convert_to_rawstring(category,
                from_enctype = "utf-8")

            pn = pkgdata.get('name')
            pn = const_convert_to_rawstring(pn,
                from_enctype = "utf-8")

            pv_utf = pkgdata.get('version')
            pv = const_convert_to_rawstring(pv_utf,
                from_enctype = "utf-8")

            pr = entropy.dep.dep_get_spm_revision(pv_utf)
            pvr = pv
            if pr == "r0":
                pvr += "-%s" % (pr,)
            pvr = const_convert_to_rawstring(pvr,
                from_enctype = "utf-8")
            pr = const_convert_to_rawstring(pr,
                from_enctype = "utf-8")

            pet = pkgdata.get('versiontag')
            pet = const_convert_to_rawstring(pet,
                from_enctype = "utf-8")

            per = pkgdata.get('revision')
            per = const_convert_to_rawstring(per,
                from_enctype = "utf-8")

            etp_branch = pkgdata.get('branch')
            etp_branch = const_convert_to_rawstring(etp_branch,
                from_enctype = "utf-8")

            slot = pkgdata.get('slot')
            slot = const_convert_to_rawstring(slot,
                from_enctype = "utf-8")

            pkgatom = pkgdata.get('atom')
            pkgkey = entropy.dep.dep_getkey(pkgatom)
            pvrte = pkgatom[len(pkgkey)+1:]
            pvrte = const_convert_to_rawstring(pvrte,
                from_enctype = "utf-8")

            etpapi = pkgdata.get('etpapi')
            etpapi = const_convert_to_rawstring(etpapi,
                from_enctype = "utf-8")

            p = pkgatom
            p = const_convert_to_rawstring(p,
                from_enctype = "utf-8")

            chost, cflags, cxxflags = pkgdata.get('chost'), \
                pkgdata.get('cflags'), pkgdata.get('cxxflags')

            if chost is None:
                chost = ""
            if cflags is None:
                cflags = ""
            if cxxflags is None:
                cxxflags = ""
            chost = const_convert_to_rawstring(chost,
                from_enctype = "utf-8")
            cflags = const_convert_to_rawstring(cflags,
                from_enctype = "utf-8")
            cxxflags = const_convert_to_rawstring(cxxflags,
                from_enctype = "utf-8")

            # Not mandatory variables

            unpackdir = pkgdata.get('unpackdir', '')
            imagedir = pkgdata.get('imagedir', '')

            sb_dirs = [unpackdir, imagedir]
            sb_write = const_convert_to_rawstring(':'.join(sb_dirs),
                from_enctype = "utf-8")

            myenv = {
                "ETP_API": etpSys['api'],
                "ETP_STAGE": stage, # entropy trigger stage
                "ETP_PHASE": self.__get_sh_stage(stage), # entropy trigger phase
                "ETP_BRANCH": etp_branch,
                "CATEGORY": category, # package category
                "PN": pn, # package name
                "PV": pv, # package version
                "PR": pr, # package revision (portage)
                "PVR": pvr, # package version+revision
                # package version+revision+entropy tag+entropy rev
                "PVRTE": pvrte,
                "PER": per, # package entropy revision
                "PET": pet, # package entropy tag
                "SLOT": slot, # package slot
                "PAPI": etpapi, # package entropy api
                "P": p, # complete package atom
                "WORKDIR": unpackdir, # temporary package workdir
                "B": unpackdir, # unpacked binary package directory?
                # package unpack destination (before merging to live)
                "D": imagedir,
                # entropy temporary directory
                "ENTROPY_TMPDIR": etpConst['entropyunpackdir'],
                "CFLAGS": cflags, # compile flags
                "CXXFLAGS": cxxflags, # compile flags
                "CHOST": chost, # *nix CHOST
                "ROOT": etpConst['systemroot'],
                "SANDBOX_WRITE": sb_write,
            }
            sysenv = os.environ.copy()
            sysenv.update(myenv)
            return sysenv

        def __get_sh_stage(self, stage):
            mydict = {
                "setup": "pkg_setup",
                "preinstall": "pkg_preinst",
                "postinstall": "pkg_postinst",
                "preremove": "pkg_prerm",
                "postremove": "pkg_postrm",
            }
            return mydict.get(stage)

        def run(self, stage, pkgdata, trigger_file):
            env = self.__env_setup(stage, pkgdata)
            args = [etpConst['trigger_sh_interpreter'], trigger_file, stage]
            p = subprocess.Popen(
                args, stdout = sys.stdout, stderr = sys.stderr,
                env = env)
            rc = p.wait()
            return rc

    class _EntropyPySandbox:

        def __init__(self, entropy_client):
            self._entropy = entropy_client

        def run(self, stage, pkgdata, trigger_file):
            globalz = globals()
            local = locals()
            enc = etpConst['conf_encoding']
            if os.path.isfile(trigger_file):
                with codecs.open(trigger_file, "r", encoding=enc) as trig_f:
                    exec(compile(trig_f.read(), trigger_file, 'exec'),
                        globalz, local)
            if os.path.isfile(trigger_file):
                os.remove(trigger_file)
            return local.get("my_ext_status", 1)

    def _do_trigger_call_ext_generic(self):

        entropy_sh = "#!%s" % (etpConst['trigger_sh_interpreter'],)
        entropy_sh = const_convert_to_rawstring(entropy_sh)
        tmp_fd, tmp_path = const_mkstemp(prefix="_do_trigger_call_ext_generic")
        with os.fdopen(tmp_fd, "ab+") as tr_f:
            tr_f.write(const_convert_to_rawstring(self._pkgdata['trigger']))
            tr_f.flush()
            tr_f.seek(0)
            interpreter = tr_f.read(128)
            tr_f.seek(0)
            shell_intr = False
            if interpreter.startswith(entropy_sh):
                shell_intr = True

        try:
            if shell_intr:
                exc = self._EntropyShSandbox(self._entropy)
            else:
                exc = self._EntropyPySandbox(self._entropy)
            return exc.run(self._phase, self._pkgdata, tmp_path)
        finally:
            if shell_intr:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _trigger_env_update(self):
        self._entropy.logger.log(
            "[Trigger]",
            etpConst['logging']['normal_loglevel_id'],
            "[POST] Running env_update"
        )
        return self._spm.environment_update()

    def _trigger_infofile_install(self):
        info_exec = Trigger.INSTALL_INFO_EXEC
        if not os.path.isfile(info_exec):
            self._entropy.logger.log(
                "[Trigger]",
                etpConst['logging']['normal_loglevel_id'],
                "[POST] %s is not available" % (info_exec,)
            )
            return 0

        env = os.environ.copy()
        for info_file in self._pkgdata['affected_infofiles']:
            self._entropy.output(
                "%s: %s" % (
                    teal(_("Installing info")),
                    info_file,),
                importance = 0,
                header = purple("    # ")
            )
            info_root = os.path.dirname(info_file)
            args = (
                info_exec,
                "--dir-file=%s/dir" % (info_root,),
                info_file)
            proc = subprocess.Popen(
                args, stdout = sys.stdout, stderr = sys.stderr,
                env = env)
            proc.wait() # ignore any error
        return 0

    def _execute_package_phase(self, action_metadata, package_metadata,
                               action_name, phase_name):
        """
        Wrapper against Source Package Manager's execute_package_phase.
        This method handles both fatal and non-fatal exceptions.
        """
        self._entropy.output(
            "%s: %s" % (brown(_("Package phase")), teal(phase_name),),
            importance = 0,
            header = red("   ## "))

        spm = self._spm

        try:
            spm.execute_package_phase(
                action_metadata, package_metadata,
                action_name, phase_name)

        except spm.PhaseFailure as err:
            txt = "%s: %s %s, %s. %s." % (
                bold(_("QA")),
                brown(_("Cannot run phase")),
                bold(phase_name),
                err.message,
                brown(_("Please report it")),
                )
            self._entropy.output(
                txt,
                importance = 1,
                header = red("   ## "),
                level = "warning")
            return 0  # non-fatal

        except spm.OutdatedPhaseError as err:
            err_msg = "%s: %s" % (
                brown(_("Source Package Manager is too old, "
                        "please update it")),
                err)
            self._entropy.output(
                err_msg,
                importance = 1,
                header = darkred("   ## "),
                level = "error"
                )
            return 1

        except spm.PhaseError as err:
            err_msg = "%s: %s" % (
                brown(_("Source Package Manager phase error")),
                err)
            self._entropy.output(
                err_msg,
                importance = 1,
                header = darkred("   ## "),
                level = "error"
                )
            return 1

        return 0

    def _trigger_spm_postinstall(self):
        return self._execute_package_phase(
            self._action_metadata,
            self._pkgdata, self._action, "postinstall")

    def _trigger_spm_preinstall(self):
        return self._execute_package_phase(
            self._action_metadata,
            self._pkgdata, self._action, "preinstall")

    def _trigger_spm_setup(self):
        return self._execute_package_phase(
            self._action_metadata,
            self._pkgdata, self._action, "setup")

    def _trigger_spm_preremove(self):
        return self._execute_package_phase(
            self._action_metadata,
            self._pkgdata, self._action, "preremove")

    def _trigger_spm_postremove(self):
        return self._execute_package_phase(
            self._action_metadata,
            self._pkgdata, self._action, "postremove")
