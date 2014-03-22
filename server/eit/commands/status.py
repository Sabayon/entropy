# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import sys
import os
import argparse

from entropy.const import etpConst
from entropy.i18n import _
from entropy.output import darkgreen, teal, brown, darkred, \
    bold, purple, blue

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand
from eit.utils import print_table


class EitStatus(EitCommand):
    """
    Main Eit status command.
    """

    NAME = "status"
    ALIASES = ["st"]
    ALLOW_UNPRIVILEGED = True

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitStatus.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitStatus.NAME))

        parser.add_argument("repo", nargs='?', default=None,
                            metavar="<repo>", help=_("repository"))

        return parser

    def bashcomp(self, last_arg):
        """
        Overridden from EitCommand
        """
        import sys

        entropy_server = self._entropy(handle_uninitialized=False,
                                       installed_repo=-1)
        outcome = entropy_server.repositories()
        for arg in self._args:
            if arg in outcome:
                # already given a repo
                outcome = []
                break

        def _startswith(string):
            if last_arg is not None:
                if last_arg not in outcome:
                    return string.startswith(last_arg)
            return True

        if self._args:
            # only filter out if last_arg is actually
            # something after this.NAME.
            outcome = sorted(filter(_startswith, outcome))

        for arg in self._args:
            if arg in outcome:
                outcome.remove(arg)

        sys.stdout.write(" ".join(outcome) + "\n")
        sys.stdout.flush()

    INTRODUCTION = """\
Show repository status (such as: *configured mirrors*,
*current branch*, *unstaged packages*, *packages ready for upload*, etc).
"""

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        """ Overridden from EitCommand """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        return self._call_exclusive, [self._status, nsargs.repo]

    def _status(self, entropy_server):

        repo_id = entropy_server.repository()
        # show interface info
        entropy_server._show_interface_status()
        entropy_server.Mirrors._show_interface_status(
            repo_id)

        plugin_id = etpConst['system_settings_plugins_ids']['server_plugin']
        repos_data = self._settings()[plugin_id]['server']['repositories']

        repo_data = repos_data[repo_id]
        repo_rev = entropy_server.local_repository_revision(repo_id)
        store_dir = entropy_server._get_local_store_directory(repo_id)
        upload_packages = entropy_server.Mirrors._calculate_local_upload_files(
            repo_id)
        key_sorter = lambda x: \
            entropy_server.open_repository(x[1]).retrieveAtom(x[0])

        to_be_added, to_be_removed, to_be_injected = \
            entropy_server.scan_package_changes()

        to_be_added = [x[0] for x in to_be_added]
        to_be_added.sort()

        toc = []

        toc.append("[%s] %s" % (purple(repo_id),
                                brown(repo_data['description']),))
        toc.append(("  %s:" % (blue(_("local revision")),),
                    str(repo_rev),))

        store_pkgs = []
        if os.path.isdir(store_dir):
            store_pkgs = os.listdir(store_dir)

        toc.append(("  %s:" % (darkgreen(_("stored packages")),),
                    str(len(store_pkgs)),))
        for pkg_rel in sorted(store_pkgs):
            toc.append((" ", brown(pkg_rel)))

        toc.append(("  %s:" % (darkgreen(_("upload packages")),),
                    str(len(upload_packages)),))
        for pkg_rel in sorted(upload_packages):
            toc.append((" ", brown(pkg_rel)))

        unstaged_len = len(to_be_added) + len(to_be_removed) + \
            len(to_be_injected)
        toc.append(("  %s:" % (darkgreen(_("unstaged packages")),),
                    str(unstaged_len),))

        print_table(entropy_server, toc)
        del toc[:]
        entropy_server.output("")

        def _get_spm_slot_repo(pkg_atom):
            try:
                spm_slot = entropy_server.Spm(
                    ).get_installed_package_metadata(pkg_atom, "SLOT")
                spm_repo = entropy_server.Spm(
                    ).get_installed_package_metadata(pkg_atom,
                                                     "repository")
            except KeyError:
                spm_repo = None
                spm_slot = None
            return spm_slot, spm_repo

        for pkg_atom in to_be_added:
            spm_slot, spm_repo = _get_spm_slot_repo(pkg_atom)

            pkg_str = teal(pkg_atom)
            if spm_repo is not None:
                pkg_id, repo_id = entropy_server.atom_match(pkg_atom,
                    match_slot = spm_slot)
                if pkg_id != -1:
                    etp_repo = entropy_server.open_repository(
                        repo_id).retrieveSpmRepository(pkg_id)
                    if etp_repo != spm_repo:
                        pkg_str += " [%s=>%s]" % (
                            etp_repo, spm_repo,)
            toc.append(("   %s:" % (purple(_("add")),), teal(pkg_str)))

        for package_id, repo_id in sorted(to_be_removed, key = key_sorter):
            pkg_atom = entropy_server.open_repository(
                repo_id).retrieveAtom(package_id)
            toc.append(("   %s:" % (darkred(_("remove")),),
                        brown(pkg_atom)))

        for package_id, repo_id in sorted(to_be_injected,
                                          key = key_sorter):
            pkg_atom = entropy_server.open_repository(
                repo_id).retrieveAtom( package_id)
            toc.append(("   %s:" % (bold(_("switch injected")),),
                        darkgreen(pkg_atom)))

        print_table(entropy_server, toc)
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitStatus,
        EitStatus.NAME,
        _("show repository status"))
    )
