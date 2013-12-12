# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import argparse
import sys

from entropy.const import etpConst, const_convert_to_unicode
from entropy.i18n import _
from entropy.output import brown, blue, darkred, darkgreen, purple, teal

from entropy.client.interfaces.package import preservedlibs

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand, sharedlock

from solo.utils import enlightenatom


class SoloPreservedLibs(SoloCommand):
    """
    Main Solo PreservedLibs command.
    """

    NAME = "preservedlibs"
    ALIASES = ["pl"]
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Tools to manage the preserved libraries currently stored on the system.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._nsargs = None
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
            SoloPreservedLibs.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloPreservedLibs.NAME))

        subparsers = parser.add_subparsers(
            title="action",
            description=_("manage preserved libraries"),
            help=_("available commands"))

        list_parser = subparsers.add_parser(
            "list", help=_("list the currently preserved libraries"))
        list_parser.set_defaults(func=self._list)
        self._setup_verbose_quiet_parser(list_parser)
        _commands["list"] = {}

        gc_parser = subparsers.add_parser(
            "gc", help=_("show libraries that could be garbage collected"))
        gc_parser.set_defaults(func=self._gc)
        _commands["gc"] = {}

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
        return self._call_shared, [nsargs.func]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        self._get_parser() # this will generate self._commands
        outcome = ["--quiet", "-q", "--verbose", "-v"]
        return self._hierarchical_bashcomp(
            last_arg, outcome, self._commands)

    @sharedlock
    def _list(self, entropy_client, inst_repo):
        """
        Solo PreservedLibs List command.
        """
        quiet = self._nsargs.quiet
        verbose = self._nsargs.verbose

        preserved_mgr = preservedlibs.PreservedLibraries(
            inst_repo, None, frozenset(),
            root=etpConst['systemroot'])

        preserved = preserved_mgr.list()

        if not preserved:
            if not quiet:
                entropy_client.output(
                    darkgreen(_("No preserved libraries found")),
                    header=darkred(" @@ "))

            return 0

        for library, elfclass, path, atom in preserved:

            if quiet:
                entropy_client.output(path, level="generic")
                continue

            needed_by_str = const_convert_to_unicode("")
            if verbose:
                needed_by_str += ", %s:" % (
                    darkgreen(_("needed by")),
                )

            entropy_client.output(
                "%s [%s:%s -> %s]%s" % (
                    darkred(path),
                    purple(library),
                    teal(const_convert_to_unicode(elfclass)),
                    enlightenatom(atom),
                    needed_by_str,
                ))

            if verbose:
                package_ids = inst_repo.searchNeeded(
                    library, elfclass=elfclass)
                for package_id in package_ids:
                    atom = inst_repo.retrieveAtom(package_id)
                    if atom is None:
                        continue

                    entropy_client.output(
                        "%s" % (enlightenatom(atom),),
                        header=brown(" -> "),
                        importance=0)

        return 0

    @sharedlock
    def _gc(self, entropy_client, inst_repo):
        """
        Solo PreservedLibs Gc command.
        """
        preserved_mgr = preservedlibs.PreservedLibraries(
            inst_repo, None, frozenset(),
            root=etpConst['systemroot'])

        collectables = preserved_mgr.collect()

        if not collectables:
            entropy_client.output(
                darkgreen(_("No preserved libraries to garbage collect")),
                header=darkred(" @@ "))
            return 0

        for library, elfclass, path in collectables:

            package_ids = inst_repo.isFileAvailable(path, get_id = True)

            entropy_client.output(
                "%s [%s:%s]" % (
                    darkred(path),
                    purple(library),
                    teal(const_convert_to_unicode(elfclass)),
                ))

            for package_id in package_ids:
                atom = inst_repo.retrieveAtom(package_id)
                if atom is None:
                    continue

                entropy_client.output(
                    "%s: %s, %s" % (
                        blue(_("but owned by")),
                        darkgreen(atom),
                        blue(_("then just unregister the library")),
                        ),
                    header=brown(" -> "),
                    importance=0
                    )

        return 0


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloPreservedLibs,
        SoloPreservedLibs.NAME,
        _("Tools to manage the preserved libraries on the system"))
    )
