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

from entropy.i18n import _
from entropy.output import darkred, darkgreen, blue, brown

from solo.utils import enlightenatom
from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands._manage import SoloManage

class SoloConfig(SoloManage):
    """
    Main Solo Config command.
    """

    NAME = "config"
    ALIASES = []
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Configure installed packages (calling pkg_config() hook).
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloManage.__init__(self, args)
        self._commands = {}

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = {}

        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloConfig.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloConfig.NAME))
        parser.set_defaults(func=self._config)

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

        self._commands = _commands
        return parser

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        self._get_parser() # this will generate self._commands
        return self._hierarchical_bashcomp(last_arg, [], self._config)

    def _config(self, entropy_client):
        """
        Solo config command.
        """
        exit_st, _show_cfgupd = self._config_action(entropy_client)
        if _show_cfgupd:
            self._show_config_files_update(entropy_client)
            self._show_preserved_libraries(entropy_client)
        return exit_st

    def _config_action(self, entropy_client):
        """
        Solo Config command action.
        """
        ask = self._nsargs.ask
        pretend = self._nsargs.pretend
        verbose = self._nsargs.verbose

        inst_repo = entropy_client.installed_repository()
        with inst_repo.shared():

            packages = entropy_client.packages_expand(
                self._nsargs.packages)
            package_ids = self._scan_installed_packages(
                entropy_client, inst_repo, packages)

            if not package_ids:
                entropy_client.output(
                    "%s." % (
                        darkred(_("No packages found")),),
                    level="error", importance=1)
                return 1, False

            for count, package_id in enumerate(package_ids, 1):

                atom = inst_repo.retrieveAtom(package_id)
                installed_from = inst_repo.getInstalledPackageRepository(
                    package_id)
                if installed_from is None:
                    installed_from = _("Not available")

                mytxt = "%s | %s: %s" % (
                    enlightenatom(atom),
                    brown(_("installed from")),
                    darkred(installed_from),
                    )
                entropy_client.output(
                    mytxt,
                    count=(count, len(package_ids)),
                    header=darkgreen("   # "))

        if verbose or ask or pretend:
            entropy_client.output(
                "%s: %s" % (
                    blue(_("Packages involved")),
                    len(package_ids),),
                header=darkred(" @@ "))

        if ask:
            exit_st = entropy_client.ask_question(
                question = "     %s" % (
                    _("Would you like to continue ?"),))
            if exit_st == _("No"):
                return 1, False

        if pretend:
            return 0, False

        action_factory = entropy_client.PackageActionFactory()

        for count, package_id in enumerate(package_ids, 1):

            atom = inst_repo.retrieveAtom(package_id)
            pkg = None

            try:
                pkg = action_factory.get(
                    action_factory.CONFIG_ACTION,
                    (package_id, inst_repo.repository_id()))

                xterm_header = "equo (%s) :: %d of %d ::" % (
                    _("configure"), count, len(package_ids))
                pkg.set_xterm_header(xterm_header)

                entropy_client.output(
                    darkgreen(atom),
                    count=(count, len(package_ids)),
                    header=darkred(" ::: ") + ">>> ")

                exit_st = pkg.start()
                if exit_st not in (0, 3):
                    return 1, True

            finally:
                if pkg is not None:
                    pkg.finalize()

        return 0, True


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloConfig,
        SoloConfig.NAME,
        _("configure installed packages"))
    )
