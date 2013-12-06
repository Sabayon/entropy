# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import sys
import argparse
import collections

from entropy.const import const_convert_to_unicode
from entropy.i18n import _
from entropy.output import blue, darkred, darkgreen, purple, teal, brown, \
    bold
from entropy.exceptions import DependenciesNotRemovable

import entropy.tools

from solo.utils import enlightenatom
from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands._manage import SoloManage

class SoloRemove(SoloManage):
    """
    Main Solo Remove command.
    """

    NAME = "remove"
    ALIASES = ["rm"]
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Remove previously installed packages from system.
"""
    SEE_ALSO = "equo-install(1), equo-config(1)"

    def __init__(self, args):
        SoloManage.__init__(self, args)
        self._commands = {}

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = {}

        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloRemove.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloRemove.NAME))
        parser.set_defaults(func=self._remove)

        parser.add_argument(
            "packages", nargs='+',
            metavar="<package>", help=_("package name"))

        mg_group = parser.add_mutually_exclusive_group()
        mg_group.add_argument(
            "--ask", "-a", action="store_true",
            default=False,
            help=_("ask before making any changes"))
        _commands["--ask"] = {}
        _commands["-a"] = {}

        mg_group.add_argument(
            "--pretend", "-p", action="store_true",
            default=False,
            help=_("show what would be done"))
        _commands["--pretend"] = {}
        _commands["-p"] = {}

        parser.add_argument(
            "--verbose", "-v", action="store_true",
            default=False,
            help=_("verbose output"))
        _commands["--verbose"] = {}
        _commands["-v"] = {}

        parser.add_argument(
            "--nodeps", action="store_true",
            default=False,
            help=_("exclude package dependencies"))
        _commands["--nodeps"] = {}

        parser.add_argument(
            "--norecursive", action="store_true",
            default=False,
            help=_("do not calculate dependencies recursively"))
        _commands["--norecursive"] = {}

        parser.add_argument(
            "--deep", action="store_true",
            default=False,
            help=_("include dependencies no longer needed"))
        _commands["--deep"] = {}

        parser.add_argument(
            "--empty", action="store_true",
            default=False,
            help=_("when used with --deep, include virtual packages"))
        _commands["--empty"] = {}

        parser.add_argument(
            "--configfiles", action="store_true",
            default=False,
            help=_("remove package configuration files no longer needed"))
        _commands["--configfiles"] = {}

        parser.add_argument(
            "--force-system", action="store_true",
            default=False,
            help=_("force system packages removal (dangerous!)"))
        _commands["--force-system"] = {}

        self._commands = _commands
        return parser

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        self._get_parser() # this will generate self._commands
        return self._hierarchical_bashcomp(last_arg, [], self._commands)

    def _remove(self, entropy_client):
        """
        Solo Remove command.
        """
        pretend = self._nsargs.pretend
        ask = self._nsargs.ask
        deps = not self._nsargs.nodeps
        deep = self._nsargs.deep
        empty = self._nsargs.empty
        recursive = not self._nsargs.norecursive
        system_packages_check = not self._nsargs.force_system
        remove_config_files = self._nsargs.configfiles
        packages = self._nsargs.packages

        exit_st, _show_cfgupd = self._remove_action(
            entropy_client, pretend, ask, deps, deep, empty,
            recursive, system_packages_check, remove_config_files,
            packages)
        if _show_cfgupd:
            self._show_config_files_update(entropy_client)
            self._show_preserved_libraries(entropy_client)
        return exit_st

    @classmethod
    def _execute_action(cls, entropy_client, inst_repo, removal_queue,
                        remove_config_files):
        """
        Execute the actual packages removal activity.
        """
        final_queue = collections.deque()
        with inst_repo.shared():
            for package_id in removal_queue:
                if not inst_repo.isPackageIdAvailable(package_id):
                    continue

                atom = inst_repo.retrieveAtom(package_id)
                if atom is None:
                    continue

                final_queue.append((atom, package_id))

        action_factory = entropy_client.PackageActionFactory()

        for count, (atom, package_id) in enumerate(final_queue, 1):

            metaopts = {}
            metaopts['removeconfig'] = remove_config_files
            pkg = None
            try:
                pkg = action_factory.get(
                    action_factory.REMOVE_ACTION,
                    (package_id, inst_repo.repository_id()),
                    opts=metaopts)

                xterm_header = "equo (%s) :: %d of %d ::" % (
                    _("removal"), count, len(final_queue))
                pkg.set_xterm_header(xterm_header)

                entropy_client.output(
                    darkgreen(atom),
                    count=(count, len(final_queue)),
                    header=darkred(" --- ") + ">>> ")

                exit_st = pkg.start()
                if exit_st != 0:
                    return 1

            finally:
                if pkg is not None:
                    pkg.finalize()

        entropy_client.output(
            "%s." % (blue(_("All done")),),
            header=darkred(" @@ "))
        return 0

    def _show_removal_info(self, entropy_client, package_ids,
                           manual=False):
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

        inst_repo = entropy_client.installed_repository()

        for package_id in package_ids:

            atom = inst_repo.retrieveAtom(package_id)
            installedfrom = inst_repo.getInstalledPackageRepository(
                package_id)
            if installedfrom is None:
                installedfrom = _("Not available")

            on_disk_size = inst_repo.retrieveOnDiskSize(package_id)
            extra_downloads = inst_repo.retrieveExtraDownload(package_id)
            for extra_download in extra_downloads:
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

    def _prompt_final_removal(self, entropy_client,
                              inst_repo, removal_queue):
        """
        Prompt some final information to User with respect to
        the removal queue.
        """
        total = len(removal_queue)
        mytxt = "%s: %s" % (
            blue(_("Packages that would be removed")),
            darkred(const_convert_to_unicode(total)),
        )
        entropy_client.output(
            mytxt, header=darkred(" @@ "))

        total_removal_size = 0
        total_pkg_size = 0
        for package_id in set(removal_queue):
            on_disk_size = inst_repo.retrieveOnDiskSize(package_id)
            if on_disk_size is None:
                on_disk_size = 0

            pkg_size = inst_repo.retrieveSize(package_id)
            if pkg_size is None:
                pkg_size = 0

            extra_downloads = inst_repo.retrieveExtraDownload(package_id)
            for extra_download in extra_downloads:
                pkg_size += extra_download['size']
                on_disk_size += extra_download['disksize']

            total_removal_size += on_disk_size
            total_pkg_size += pkg_size

        human_removal_size = entropy.tools.bytes_into_human(
            total_removal_size)
        human_pkg_size = entropy.tools.bytes_into_human(total_pkg_size)

        mytxt = "%s: %s" % (
            blue(_("Freed disk space")),
            bold(const_convert_to_unicode(human_removal_size)),
        )
        entropy_client.output(
            mytxt, header=darkred(" @@ "))

        mytxt = "%s: %s" % (
            blue(_("Total bandwidth wasted")),
            bold(str(human_pkg_size)),
        )
        entropy_client.output(
            mytxt, header=darkred(" @@ "))

    def _remove_action(self, entropy_client, pretend, ask,
                       deps, deep, empty, recursive,
                       system_packages_check, remove_config_files,
                       packages, package_ids=None):
        """
        Solo Remove action implementation.
        """
        inst_repo = entropy_client.installed_repository()
        with inst_repo.shared():

            if package_ids is None:
                packages = entropy_client.packages_expand(packages)
                package_ids = self._scan_installed_packages(
                    entropy_client, inst_repo, packages)

            if not package_ids:
                entropy_client.output(
                    darkred(_("No packages found")),
                    level="error", importance=1)
                return 1, False

            removal_queue = []
            if deps:
                try:
                    removal_queue += entropy_client.get_removal_queue(
                        package_ids,
                        deep = deep, recursive = recursive,
                        empty = empty,
                        system_packages = system_packages_check)
                except DependenciesNotRemovable as err:
                    non_rm_pkg_names = sorted(
                        [inst_repo.retrieveAtom(x[0]) for x in err.value])
                    # otherwise we need to deny the request
                    entropy_client.output("", level="error")
                    entropy_client.output(
                        "  %s, %s:" % (
                            purple(_("Ouch!")),
                            brown(_("the following system packages"
                                    " were pulled in")),
                            ),
                        level="error", importance=1)
                    for pkg_name in non_rm_pkg_names:
                        entropy_client.output(
                            teal(pkg_name),
                            header=purple("    # "),
                            level="error")
                    entropy_client.output("", level="error")
                    return 1, False

            removal_queue += [x for x in package_ids if x not in removal_queue]
            self._show_removal_info(entropy_client, removal_queue)

            self._prompt_final_removal(
                entropy_client, inst_repo, removal_queue)

        if pretend:
            return 0, False

        if ask:
            question = "     %s" % (
                _("Would you like to proceed ?"),)
            rc = entropy_client.ask_question(question)
            if rc == _("No"):
                return 1, False

        exit_st = self._execute_action(
            entropy_client, inst_repo, removal_queue,
            remove_config_files)
        return exit_st, True


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloRemove,
        SoloRemove.NAME,
        _("remove packages from system"))
    )
