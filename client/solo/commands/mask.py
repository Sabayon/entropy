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

from entropy.i18n import _
from entropy.const import const_convert_to_unicode
from entropy.output import purple, teal, darkred, brown, red, \
    darkgreen, blue

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand
from solo.utils import enlightenatom

class SoloMaskUnmask(SoloCommand):

    def __init__(self, args, action):
        SoloCommand.__init__(self, args)
        self._ask = False
        self._pretend = False
        self._action = action

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        descriptor = SoloCommandDescriptor.obtain_descriptor(
            self.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], self.NAME))

        parser.add_argument("packages", nargs='+',
                            metavar="<package>", help=_("package name"))

        group = parser.add_mutually_exclusive_group()
        group.add_argument("--ask", "-a", action="store_true",
                           default=self._ask,
                           help=_('ask before making any changes'))

        group.add_argument("--pretend", "-p", action="store_true",
                           default=self._pretend,
                           help=_('only show what would be done'))

        return parser

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        args = ["--ask", "-a", "--pretend", "-p"]
        args.sort()
        return self._bashcomp(sys.stdout, last_arg, args)

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def parse(self):
        """
        Parse command.
        """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._packages = nsargs.packages
        self._pretend = nsargs.pretend
        self._ask = nsargs.ask

        return self._call_shared, [self._run]

    def _run(self, entropy_client):
        """
        Mask/Unmask code logic.
        """
        found_pkg_atoms = []
        for package in self._packages:
            package_id, repoid = entropy_client.atom_match(
                package, mask_filter = False)

            if package_id == -1:
                mytxt = "!!! %s: %s %s." % (
                    purple(_("Warning")),
                    teal(const_convert_to_unicode(package)),
                    purple(_("is not available")),
                )
                entropy_client.output("!!!", level="warning", importance=1)
                entropy_client.output(mytxt, level="warning", importance=1)
                entropy_client.output("!!!", level="warning", importance=1)
                if len(package) > 3:
                    self._show_did_you_mean(
                        entropy_client, package,
                        from_installed=False)
                    entropy_client.output("!!!", level="warning", importance=1)
                continue

            found_pkg_atoms.append(package)

        if not found_pkg_atoms:
            entropy_client.output(
                "%s." % (
                    darkred(_("No packages found")),
                    ),
                level="error", importance=1)
            return 1

        if self._ask or self._pretend:
            mytxt = "%s:" % (
                blue(_("These are the packages that would be handled")),
                )
            entropy_client.output(
                mytxt,
                header=red(" @@ "))

        match_data = {}
        for package in found_pkg_atoms:
            matches, rc = entropy_client.atom_match(
                package, multi_match = True, multi_repo = True,
                    mask_filter = False)
            match_data[package] = matches

            flags = darkgreen(" [")
            if self._action == "mask":
                flags += brown("M")
            else:
                flags += red("U")
            flags += darkgreen("] ")
            entropy_client.output(
                darkred(" ##") + flags + purple(package))

            if rc == 0:
                # also show found pkgs
                for package_id, repository_id in matches:
                    repo = entropy_client.open_repository(repository_id)
                    atom = repo.retrieveAtom(package_id)
                    entropy_client.output(
                        "    -> " + enlightenatom(atom))

        if self._pretend:
            return 0

        if self._ask:
            answer = entropy_client.ask_question(
                _("Would you like to continue?"))
            if answer == _("No"):
                return 0

        for package, matches in match_data.items():
            for match in matches:
                if self._action == "mask":
                    done = entropy_client.mask_package_generic(match, package)
                else:
                    done = entropy_client.unmask_package_generic(match, package)
                if not done:
                    mytxt = "!!! %s: %s %s." % (
                        purple(_("Warning")),
                        teal(const_convert_to_unicode(package)),
                        purple(_("action not executed")),
                    )
                    entropy_client.output("!!!", level="warning", importance=1)
                    entropy_client.output(mytxt, level="warning", importance=1)
                    entropy_client.output("!!!", level="warning", importance=1)

        entropy_client.output("Have a nice day.")
        return 0


class SoloMask(SoloMaskUnmask):
    """
    Main Solo Mask command.
    """

    NAME = "mask"
    ALIASES = []

    INTRODUCTION = """\
Mask packages so that installation and update will be inhibited.
"""
    SEE_ALSO = "equo-unmask(1)"

    def __init__(self, args):
        SoloMaskUnmask.__init__(self, args, SoloMask.NAME)


class SoloUnmask(SoloMaskUnmask):
    """
    Main Solo Mask command.
    """

    NAME = "unmask"
    ALIASES = []

    INTRODUCTION = """\
Unmask packages so that installation and update will be allowed.
"""
    SEE_ALSO = "equo-mask(1)"

    def __init__(self, args):
        SoloMaskUnmask.__init__(self, args, SoloUnmask.NAME)


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloMask,
        SoloMask.NAME,
        _("mask one or more packages"))
    )

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloUnmask,
        SoloUnmask.NAME,
        _("unmask one or more packages"))
    )
