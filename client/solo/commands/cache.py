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
from entropy.output import blue, brown, darkgreen

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand, sharedlock

class SoloCache(SoloCommand):
    """
    Main Solo Repo command.
    """

    NAME = "cache"
    ALIASES = []
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Manage Entropy Library Cache.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._nsargs = None
        self._commands = []

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = []

        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloCache.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloCache.NAME))

        subparsers = parser.add_subparsers(
            title="action", description=_("manage cache"),
            help=_("available commands"))

        clean_parser = subparsers.add_parser(
            "clean", help=_("clean Entropy Library Cache"))
        clean_parser.add_argument(
            "--verbose", "-v", action="store_true", default=False,
            help=_("show more details"))
        clean_parser.add_argument(
            "--quiet", "-q", action="store_true", default=False,
            help=_("print results in a scriptable way"))

        clean_parser.set_defaults(func=self._clean)
        _commands.append("clean")

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
        outcome = []
        parser = self._get_parser()
        try:
            command = self._args[0]
        except IndexError:
            command = None

        if not self._args:
            # show all the commands
            outcome += self._commands

        elif command not in self._commands:
            # return all the commands anyway
            # last_arg will filter them
            outcome += self._commands

        elif command == "enable":
            outcome += ["--verbose", "-v", "--quiet", "-q"]

        return self._bashcomp(sys.stdout, last_arg, outcome)

    @sharedlock  # clear_cache uses inst_repo
    def _clean(self, entropy_client, _inst_repo):
        """
        Solo Cache Clean command.
        """
        entropy_client.output(
            blue(_("Cleaning Entropy cache, please wait ...")),
            level = "info",
            header = brown(" @@ "),
            back = True
        )
        entropy_client.clear_cache()
        entropy_client.output(
            darkgreen(_("Entropy cache cleaned.")),
            level = "info",
            header = brown(" @@ ")
        )
        return 0


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloCache,
        SoloCache.NAME,
        _("manage Entropy Library Cache"))
    )
