# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
from entropy.const import etpConst
from entropy.i18n import _
from entropy.output import red, darkred, blue, brown

from .action import PackageAction


class _PackageConfigAction(PackageAction):
    """
    PackageAction used for package configuration.
    """

    NAME = "config"

    def __init__(self, entropy_client, package_match, opts = None):
        """
        Object constructor.
        """
        super(_PackageConfigAction, self).__init__(
            entropy_client, package_match, opts = opts)
        self._meta = None

    def finalize(self):
        """
        Finalize the object, release all its resources.
        """
        super(_PackageConfigAction, self).finalize()
        if self._meta is not None:
            meta = self._meta
            self._meta = None
            meta.clear()

    def metadata(self):
        """
        Return the package metadata dict object for manipulation.
        """
        return self._meta

    def setup(self):
        """
        Setup the PackageAction.
        """
        if self._meta is not None:
            # already configured
            return

        metadata = {}
        metadata['phases'] = []
        metadata['phases'].append(self._config_phase)

        self._meta = metadata

    def _run(self):
        """
        Execute the action. Return an exit status.
        """
        self.setup()

        exit_st = 0
        for method in self._meta['phases']:
            exit_st = method()
            if exit_st != 0:
                break
        return exit_st

    def _configure_package_unlocked(self, metadata):
        """
        Configure the package.
        """
        spm = self._entropy.Spm()

        self._entropy.output(
            "SPM: %s" % (
                brown(_("configuration phase")),
            ),
            importance = 0,
            header = red("   ## ")
        )

        try:
            spm.execute_package_phase(
                metadata, metadata,
                self.NAME, "configure")

        except spm.PhaseFailure as err:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Phase execution failed with %s, %d" % (
                    err.message, err.code))
            return err.code

        except spm.OutdatedPhaseError as err:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Source Package Manager is too old: %s" % (
                    err))

            err_msg = "%s: %s" % (
                brown(_("Source Package Manager is too old, please update it")),
                err)
            self._entropy.output(
                err_msg,
                importance = 1,
                header = darkred("   ## "),
                level = "error"
                )
            return 1

        except spm.PhaseError as err:
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Phase execution error: %s" % (
                    err))
            return 1

        return 0

    def _config_phase(self):
        """
        Execute the config phase.
        """
        inst_repo = self._entropy.installed_repository()
        with inst_repo.shared():
            exit_st = self._config_phase_unlocked(inst_repo)

        if exit_st == 1:
            txt = _("An error occurred while trying to configure the package")
            txt2 = "%s. %s: %s" % (
                red(_("Make sure that your system is healthy")),
                blue(_("Error")),
                exit_st,
            )
            self._entropy.output(
                darkred(txt),
                importance = 1,
                level = "error",
                header = red("   ## ")
            )
            self._entropy.output(
                txt2,
                importance = 1,
                level = "error",
                header = red("   ## ")
            )

        elif exit_st == 2:
            txt = _("An error occurred while trying to configure the package")
            txt2 = "%s. %s: %s" % (
                red(_("It seems that Source Package Manager entry is missing")),
                blue(_("Error")),
                exit_st,
            )
            self._entropy.output(
                darkred(txt),
                importance = 1,
                level = "error",
                header = red("   ## ")
            )
            self._entropy.output(
                txt2,
                importance = 1,
                level = "error",
                header = red("   ## ")
            )

        return exit_st


    def _config_phase_unlocked(self, inst_repo):
        """
        _config_phase(), assuming that the installed packages repository lock
        is held.
        """
        if not inst_repo.isPackageIdAvailable(self._package_id):
            self._entropy.output(
                darkred(_("The requested package is no longer available.")),
                importance = 1,
                level = "error",
                header = red("   ## ")
            )
            return 3

        metadata = {}
        metadata['atom'] = inst_repo.retrieveAtom(self._package_id)
        key, slot = inst_repo.retrieveKeySlot(self._package_id)
        metadata['key'], metadata['slot'] = key, slot
        metadata['version'] = inst_repo.retrieveVersion(self._package_id)
        metadata['category'] = inst_repo.retrieveCategory(self._package_id)
        metadata['name'] = inst_repo.retrieveName(self._package_id)
        metadata['spm_repository'] = inst_repo.retrieveSpmRepository(
            self._package_id)

        metadata['accept_license'] = self._get_licenses(
            inst_repo, self._package_id)

        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Configuring package"),
            metadata['atom'],
        )
        self._entropy.set_title(xterm_title)

        txt = "%s: %s" % (
            blue(_("Configuring package")),
            red(metadata['atom']),
        )
        self._entropy.output(
            txt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )
        return self._configure_package_unlocked(metadata)
