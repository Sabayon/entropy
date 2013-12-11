# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
from entropy.const import etpConst
from entropy.exceptions import SPMError
from entropy.i18n import _
from entropy.output import blue, red, darkred, brown

import entropy.dep

from ._manage import _PackageInstallRemoveAction
from ._triggers import Trigger

from .. import preservedlibs


class _PackageRemoveAction(_PackageInstallRemoveAction):
    """
    PackageAction used for package removal.
    """

    NAME = "remove"

    def __init__(self, entropy_client, package_match, opts = None):
        """
        Object constructor.
        """
        super(_PackageRemoveAction, self).__init__(
            entropy_client, package_match, opts = opts)

    def finalize(self):
        """
        Finalize the object, release all its resources.
        """
        super(_PackageRemoveAction, self).finalize()
        if self._meta is not None:
            meta = self._meta
            self._meta = None
            meta.clear()

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

        inst_repo = self._entropy.open_repository(self._repository_id)
        metadata['configprotect_data'] = []

        metadata['removeconfig'] = self._opts.get('removeconfig', False)

        # used by Spm.remove_installed_package()
        metadata['slot'] = inst_repo.retrieveSlot(self._package_id)
        metadata['versiontag'] = inst_repo.retrieveTag(self._package_id)

        # collects directories whose content has been modified
        # this information is then handed to the Trigger
        metadata['affected_directories'] = set()
        metadata['affected_infofiles'] = set()

        metadata['phases'] = [
            self._remove_phase,
        ]
        self._meta = metadata

    def _pre_remove_package_unlocked(self, atom, data):
        """
        Run the pre-remove phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Pre-remove"),
            atom,
        )
        self._entropy.set_title(xterm_title)

        trigger = Trigger(
            self._entropy,
            self.NAME,
            "preremove",
            data,
            None)

        exit_st = 0
        ack = trigger.prepare()
        if ack:
            exit_st = trigger.run()
        trigger.kill()

        return exit_st

    def _remove_phase(self):
        """
        Run the remove phase.
        """
        inst_repo = self._entropy.open_repository(self._repository_id)
        with inst_repo.exclusive():

            if not inst_repo.isPackageIdAvailable(self._package_id):
                self._entropy.output(
                    darkred(_("The requested package is no longer available")),
                    importance = 1,
                    level = "warning",
                    header = brown(" @@ ")
                )

                # install.py assumes that a zero exit status is returned
                # in this case.
                return 0

            atom = inst_repo.retrieveAtom(self._package_id)

            xterm_title = "%s %s: %s" % (
                self._xterm_header,
                _("Removing"),
                atom,
            )
            self._entropy.set_title(xterm_title)

            self._entropy.output(
                "%s: %s" % (
                    blue(_("Removing")),
                    red(atom),
                ),
                importance = 1,
                level = "info",
                header = red("   ## ")
            )

            self._entropy.logger.log("[Package]",
                etpConst['logging']['normal_loglevel_id'],
                    "Removing package: %s" % (atom,))

            txt = "%s: %s" % (
                blue(_("Removing from Entropy")),
                red(atom),
            )
            self._entropy.output(
                txt,
                importance = 1,
                level = "info",
                header = red("   ## ")
            )

            return self._remove_phase_unlocked(inst_repo)

    def _remove_phase_unlocked(self, inst_repo):
        """
        _remove_phase(), assuming that the installed packages repository lock
        is held.
        """
        self._entropy.clear_cache()

        removecontent_file = self._generate_content_file(
            inst_repo.retrieveContentIter(
                self._package_id, order_by="file", reverse=True)
        )

        atom = inst_repo.retrieveAtom(self._package_id)

        trigger_data = self._get_remove_trigger_data(
            inst_repo, self._package_id)

        config_protect_metadata = self._get_config_protect_metadata(
            inst_repo, self._package_id, _metadata = self._meta)

        automerge_metadata = inst_repo.retrieveAutomergefiles(
            self._package_id, get_dict = True)
        provided_libraries = inst_repo.retrieveProvidedLibraries(
            self._package_id)

        # end of data collection

        exit_st = self._pre_remove_package_unlocked(atom, trigger_data)
        if exit_st != 0:
            return exit_st

        inst_repo.removePackage(self._package_id)
        # commit changes, to avoid users pressing CTRL+C and still having
        # all the db entries in, so we need to commit at every iteration
        inst_repo.commit()

        sys_root = self._get_system_root(self._meta)
        preserved_mgr = preservedlibs.PreservedLibraries(
            inst_repo, None, provided_libraries,
            root = sys_root)

        self._remove_content_from_system(
            inst_repo,
            atom,
            self._meta['removeconfig'],
            sys_root,
            config_protect_metadata['config_protect+mask'],
            removecontent_file,
            automerge_metadata,
            self._meta['affected_directories'],
            self._meta['affected_infofiles'],
            preserved_mgr)

        # garbage collect preserved libraries that are no longer needed
        self._garbage_collect_preserved_libs(preserved_mgr)

        exit_st = self._post_remove_package_unlocked(atom, trigger_data)
        if exit_st != 0:
            return exit_st

        exit_st = self._post_remove_remove_package_unlocked(
            inst_repo, atom)
        if exit_st != 0:
            return exit_st

        return 0

    def _post_remove_package_unlocked(self, atom, data):
        """
        Run the first post-remove phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Post-remove"),
            atom,
        )
        self._entropy.set_title(xterm_title)

        trigger = Trigger(
            self._entropy,
            self.NAME,
            "postremove",
            data,
            None)

        exit_st = 0
        ack = trigger.prepare()
        if ack:
            exit_st = trigger.run()
        trigger.kill()

        return exit_st

    def _spm_update_package_uid(self, installed_package_id, spm_atom):
        """
        Update Source Package Manager <-> Entropy package identifiers coupling.
        Entropy can handle multiple packages in the same scope from a SPM POV
        (see the "package tag" feature to provide linux kernel module packages
        for different kernel versions). This method just reassigns a new SPM
        unique package identifier to Entropy.

        @param installed_package_id: Entropy package identifier bound to
            given spm_atom
        @type installed_package_id: int
        @param spm_atom: SPM package atom
        @type spm_atom: string
        @return: execution status
        @rtype: int
        """
        spm = self._entropy.Spm()

        try:
            spm_uid = spm.assign_uid_to_installed_package(spm_atom)
        except (SPMError, KeyError,):
            # installed package not available, we must ignore it
            self._entropy.logger.log(
                "[Package]",
                etpConst['logging']['normal_loglevel_id'],
                "Spm uid not available for Spm package: %s (pkg not avail?)" % (
                    spm_atom,
                )
            )
            spm_uid = -1

        if spm_uid != -1:
            inst_repo = self._entropy.open_repository(self._repository_id)
            inst_repo.insertSpmUid(installed_package_id, spm_uid)
            inst_repo.commit()

    def _post_remove_remove_package_unlocked(self, inst_repo, atom):
        """
        Post-remove phase of package remove action, this step removes SPM
        package entries if there are no other Entropy-tagged packages installed.
        """
        # remove pkg
        # -- now it's possible to remove SPM package entry.
        # if another package with the same atom is installed in
        # Entropy db, do not call SPM at all because it would cause
        # to get that package removed from there resulting in matching
        # inconsistencies.
        # -- of course, we need to drop versiontag before being able to look
        # for other pkgs with same atom but different tag (which is an
        # entropy-only metadatum)
        spm = self._entropy.Spm()

        test_atom = entropy.dep.remove_tag(atom)
        spm_atom = spm.convert_from_entropy_package_name(atom)

        installed_package_ids = inst_repo.getPackageIds(test_atom)
        if not installed_package_ids:
            exit_st = self._spm_remove_package(
                spm_atom, self._meta)
            if exit_st != 0:
                return exit_st

        for installed_package_id in installed_package_ids:
            # we have one installed, we need to update SPM uid
            self._spm_update_package_uid(installed_package_id, spm_atom)

        return 0

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
