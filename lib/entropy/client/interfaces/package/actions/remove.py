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
from entropy.output import blue, red

import entropy.dep

from ._manage import _PackageInstallRemoveAction

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
        metadata['triggers'] = {}
        metadata['atom'] = inst_repo.retrieveAtom(self._package_id)
        # removeatom metadata key used by Spm.remove_installed_package()
        metadata['removeatom'] = metadata['atom']
        metadata['slot'] = inst_repo.retrieveSlot(self._package_id)
        metadata['versiontag'] = inst_repo.retrieveTag(self._package_id)
        metadata['removeconfig'] = self._opts.get('removeconfig', False)

        content = inst_repo.retrieveContentIter(
            self._package_id, order_by="file", reverse=True)
        metadata['removecontent_file'] = self._generate_content_file(
            content)

        # collects directories whose content has been modified
        # this information is then handed to the Trigger
        metadata['affected_directories'] = set()
        metadata['affected_infofiles'] = set()

        trigger = inst_repo.getTriggerData(self._package_id)
        metadata['triggers']['remove'] = trigger

        trigger['affected_directories'] = metadata['affected_directories']
        trigger['affected_infofiles'] = metadata['affected_infofiles']
        trigger['spm_repository'] = inst_repo.retrieveSpmRepository(
            self._package_id)

        trigger['accept_license'] = self._get_licenses(
            inst_repo, self._package_id)
        trigger.update(splitdebug_metadata)

        # setup config_protect and config_protect+mask metadata before it's
        # too late.
        protect = self._get_config_protect_metadata(
            inst_repo, self._package_id, _metadata = metadata)
        metadata.update(protect)

        metadata['phases'] = [
            self._pre_remove,
            self._remove,
            self._post_remove,
            self._post_remove_remove,
        ]
        self._meta = metadata

    def _pre_remove(self):
        """
        Run the pre-remove phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Pre-remove"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        exit_st = 0
        data = self._meta['triggers']['remove']
        if not data:
            return exit_st

        trigger = self._entropy.Triggers(
            self.NAME, "preremove", data, None)
        ack = trigger.prepare()
        if ack:
            exit_st = trigger.run()
        trigger.kill()

        return exit_st

    def _remove(self):
        """
        Run the remove phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Removing"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        self._entropy.output(
            "%s: %s" % (
                blue(_("Removing")),
                red(self._meta['atom']),
            ),
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        self._entropy.clear_cache()

        self._entropy.logger.log("[Package]",
            etpConst['logging']['normal_loglevel_id'],
                "Removing package: %s" % (self._meta['atom'],))

        txt = "%s: %s" % (
            blue(_("Removing from Entropy")),
            red(self._meta['atom']),
        )
        self._entropy.output(
            txt,
            importance = 1,
            level = "info",
            header = red("   ## ")
        )

        inst_repo = self._entropy.open_repository(self._repository_id)
        automerge_metadata = inst_repo.retrieveAutomergefiles(
            self._package_id, get_dict = True)
        provided_libraries = inst_repo.retrieveProvidedLibraries(
            self._package_id)

        inst_repo.removePackage(self._package_id)
        # commit changes, to avoid users pressing CTRL+C and still having
        # all the db entries in, so we need to commit at every iteration
        inst_repo.commit()

        preserved_mgr = preservedlibs.PreservedLibraries(
            inst_repo, None, provided_libraries,
            root = self._get_system_root(self._meta))

        self._remove_content_from_system(
            inst_repo, automerge_metadata, preserved_mgr)

        return 0

    def _post_remove(self):
        """
        Run the first post-remove phase.
        """
        xterm_title = "%s %s: %s" % (
            self._xterm_header,
            _("Post-remove"),
            self._meta['atom'],
        )
        self._entropy.set_title(xterm_title)

        exit_st = 0
        data = self._meta['triggers']['remove']
        if not data:
            return exit_st

        trigger = self._entropy.Triggers(
            self.NAME, "postremove", data, None)
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

    def _post_remove_remove(self):
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

        atom = self._meta['atom']
        inst_repo = self._entropy.open_repository(self._repository_id)
        test_atom = entropy.dep.remove_tag(atom)
        installed_package_ids = inst_repo.getPackageIds(test_atom)

        spm = self._entropy.Spm()
        spm_atom = spm.convert_from_entropy_package_name(atom)

        if not installed_package_ids:
            exit_st = self._spm_remove_package(spm_atom)
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
