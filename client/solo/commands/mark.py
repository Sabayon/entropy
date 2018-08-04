# -*- coding: utf-8 -*-
"""

    @author: Slawomir Nizio <slawomir.nizio@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Slawomir Nizio
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import sys
import argparse

from entropy.i18n import _
from entropy.const import etpConst, const_convert_to_unicode
from entropy.output import darkred, red, blue, brown, teal, purple

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand, exclusivelock


class SoloMark(SoloCommand):
    """
    Main Solo Mark command.
    """

    NAME = "mark"
    ALIASES = []
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Set properties on installed packages
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._commands = {}

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = {}
        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloMark.NAME)

        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloMark.NAME))

        subparsers = parser.add_subparsers(
            title="action",
            description=_("specify property to mark on a package"),
            help=_("available commands"))

        def _add_standard_arguments(p, _cmd_dict):
            p.add_argument(
                "packages", nargs='+',
                metavar="<package>", help=_("package name"))

            p.add_argument(
                    "--pretend", "-p", action="store_true",
                    default=False,
                    help=_("show what would be done"))
            _cmd_dict["--pretend"] = {}
            _cmd_dict["-p"] = {}

            p.add_argument(
                    "--ignore-missing", action="store_true",
                    default=False,
                    help=_("ignore packages that are not installed on system"))
            _cmd_dict["--ignore-missing"] = {}

            # It behaves differently than --multimatch from match.py,
            # thus a different name.
            p.add_argument(
                    "--multiple-versions", action="store_true",
                    default=False,
                    help=_("allow matching multiple versions of a package"))
            _cmd_dict["--multiple-versions"] = {}

        auto_parser = subparsers.add_parser(
            "auto",
            help=_("mark package as installed to satisfy a dependency"))
        _cmd_dict = {}
        _add_standard_arguments(auto_parser, _cmd_dict)
        auto_parser.set_defaults(func=self._auto)
        _commands["auto"] = _cmd_dict

        manual_parser = subparsers.add_parser(
            "manual",
            help=_("mark package as installed by user"))
        _cmd_dict = {}
        _add_standard_arguments(manual_parser, _cmd_dict)
        manual_parser.set_defaults(func=self._manual)
        _commands["manual"] = _cmd_dict

        self._commands = _commands
        return parser

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

        # Python 3.3 bug #16308
        if not hasattr(nsargs, "func"):
            return parser.print_help, []

        self._nsargs = nsargs
        return self._call_exclusive, [nsargs.func]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        self._get_parser() # this will generate self._commands
        return self._hierarchical_bashcomp(last_arg, [], self._commands)

    @exclusivelock
    def _auto(self, entropy_client, inst_repo):
        source_key = "automatic_dependency"
        return self._apply_source(
            entropy_client, inst_repo, source_key, **self._get_opts())

    @exclusivelock
    def _manual(self, entropy_client, inst_repo):
        source_key = "user"
        return self._apply_source(
            entropy_client, inst_repo, source_key, **self._get_opts())

    def _get_opts(self):
        opts = {
            'packages': self._nsargs.packages,
            'pretend': self._nsargs.pretend,
            'ignore_missing': self._nsargs.ignore_missing,
            'multiple_versions': self._nsargs.multiple_versions
        }
        return opts

    def _apply_source(self, entropy_client, inst_repo,
                      source_key, packages, pretend,
                      ignore_missing, multiple_versions):

        source = etpConst['install_sources'][source_key]

        reverse_install_sources = {
            0: _("unknown"),
            1: _("manual"),
            2: _("dependency")
        }
        other_source = _("other")

        source_txt = reverse_install_sources.get(source, other_source)

        packages = entropy_client.packages_expand(packages)
        package_ids = {}

        allfound = True
        for package in packages:
            if package in package_ids:
                continue
            pkg_ids, _rc = inst_repo.atomMatch(
                package, multiMatch=multiple_versions)

            if not multiple_versions:
                pkg_ids = set([pkg_ids])

            if _rc == 0:
                package_ids[package] = pkg_ids
            else:
                allfound = False
                entropy_client.output(
                    "!!! %s: %s %s." % (
                        purple(_("Warning")),
                        teal(const_convert_to_unicode(package)),
                        purple(_("is not installed")),
                    ))

        if not allfound:
            entropy_client.output(
                darkred(_("Some packages were not found")),
                level="info" if ignore_missing else "error",
                importance=1)
            if not ignore_missing:
                return 1

        for package in packages:
            if package not in package_ids:
                # Package was not found.
                continue

            for pkg_id in package_ids[package]:

                pkg_atom = inst_repo.retrieveAtom(pkg_id)
                current_source = inst_repo.getInstalledPackageSource(pkg_id)
                current_source_txt = reverse_install_sources.get(
                    current_source, other_source)

                if current_source == source:
                    txt = "%s: %s" % (
                        brown(pkg_atom),
                        _("no change"))
                    entropy_client.output(
                        txt,
                        header=blue(" @@ "))
                else:
                    txt = "%s: %s => %s" % (
                        brown(pkg_atom),
                        current_source_txt,
                        source_txt)
                    entropy_client.output(
                        txt,
                        header=red(" !! "))

                    if not pretend:
                        inst_repo.setInstalledPackageSource(pkg_id, source)

        return 0

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloMark,
        SoloMark.NAME,
        _("set properties on installed packages"))
    )
