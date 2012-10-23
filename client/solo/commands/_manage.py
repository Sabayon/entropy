# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import os
import sys
import argparse

from entropy.const import const_convert_to_unicode
from entropy.i18n import _, ngettext
from entropy.output import darkgreen, blue, purple, teal, brown, bold, \
    darkred

import entropy.tools

from solo.utils import enlightenatom
from solo.commands.command import SoloCommand

class SoloManage(SoloCommand):
    """
    Abstract class used by Solo Package management
    modules (remove, install, etc...).
    This class contains all the shared code.
    """

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._nsargs = None

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def parse(self):
        """
        Parse command
        """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._nsargs = nsargs
        return self._call_locked, [nsargs.func]

    def _show_config_files_update(self, entropy_client):
        """
        Inform User about configuration file updates, if any.
        """
        entropy_client.output(
            blue(_("Scanning configuration files to update")),
            header=darkgreen(" @@ "),
            back=True)

        updates = entropy_client.ConfigurationUpdates()
        scandata = updates.get()

        if not scandata:
            entropy_client.output(
                blue(_("No configuration files to update.")),
                header=darkgreen(" @@ "))
            return

        mytxt = ngettext(
            "There is %s configuration file needing update",
            "There are %s configuration files needing update",
            len(scandata)) % (len(scandata),)
        entropy_client.output(
            darkgreen(mytxt),
            level="warning")

        mytxt = "%s: %s" % (
            purple(_("Please run")),
            bold("equo conf update"))
        entropy_client.output(
            darkgreen(mytxt),
            level="warning")

    def _show_did_you_mean(self, entropy_client, package, from_installed):
        """
        Show "Did you mean?" results for the given package name.
        """
        items = entropy_client.get_meant_packages(
            package, from_installed=from_installed)
        if not items:
            return

        mytxt = "%s %s %s %s %s" % (
            bold(const_convert_to_unicode("   ?")),
            teal(_("When you wrote")),
            bold(const_convert_to_unicode(package)),
            darkgreen(_("You Meant(tm)")),
            teal(_("one of these below?")),
        )
        entropy_client.output(mytxt)

        _cache = set()
        for pkg_id, repo_id in items:
            if from_installed:
                repo = entropy_client.installed_repository()
            else:
                repo = entropy_client.open_repository(repo_id)

            key_slot = repo.retrieveKeySlotAggregated(pkg_id)
            if key_slot not in _cache:
                entropy_client.output(
                    enlightenatom(key_slot),
                    header=brown("    # "))
                _cache.add(key_slot)

    def _show_removal_info(self, entropy_client, package_ids,
                           manual = False):
        """
        Show packages removal information.
        """
        if manual:
            entropy_client.output(
                "%s:" % (
                    blue(_("These are the packages that "
                      "should be MANUALLY removed")),),
                header=darkred(" @@ "))
        else:
            entropy_client.output(
                "%s:" % (
                    blue(_("These are the packages that "
                      "would be removed")),),
                header=darkred(" @@ "))

        total = len(package_ids)
        count = 0
        inst_repo = entropy_client.installed_repository()

        for package_id in package_ids:
            count += 1
            atom = inst_repo.retrieveAtom(package_id)
            installedfrom = inst_repo.getInstalledPackageRepository(
                package_id)
            if installedfrom is None:
                installedfrom = _("Not available")

            on_disk_size = inst_repo.retrieveOnDiskSize(package_id)
            pkg_size = inst_repo.retrieveSize(package_id)
            extra_downloads = inst_repo.retrieveExtraDownload(package_id)
            for extra_download in extra_downloads:
                pkg_size += extra_download['size']
                on_disk_size += extra_download['disksize']

            disksize = entropy.tools.bytes_into_human(on_disk_size)
            disksize_info = "%s%s%s" % (
                bold("["),
                brown("%s" % (disksize,)),
                bold("]"))
            repo_info = bold("[") + brown(installedfrom) + bold("]")

            mytxt = "%s %s %s" % (
                repo_info,
                enlightenatom(atom),
                disksize_info)

            entropy_client.output(mytxt, header=darkred(" ## "))
