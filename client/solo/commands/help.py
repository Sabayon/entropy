# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import argparse

from entropy.i18n import _
from entropy.output import teal, purple, darkgreen

from _entropy.solo.colorful import ColorfulFormatter
from _entropy.solo.commands.descriptor import SoloCommandDescriptor
from _entropy.solo.commands.command import SoloCommand

class SoloHelp(SoloCommand):
    """
    Main Solo help command.
    """

    NAME = "help"
    ALIASES = ["-h", "--help"]
    CATCH_ALL = True

    def parse(self):
        """
        Parse help command
        """
        return self._show_help, []

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand
        """
        import sys

        descriptors = SoloCommandDescriptor.obtain()
        descriptors.sort(key = lambda x: x.get_name())
        outcome = []
        for descriptor in descriptors:
            name = descriptor.get_name()
            if name == SoloHelp.NAME:
                # do not add self
                continue
            outcome.append(name)
            aliases = descriptor.get_class().ALIASES
            outcome.extend(aliases)

        def _startswith(string):
            if last_arg is not None:
                return string.startswith(last_arg)
            return True

        outcome = sorted(filter(_startswith, outcome))
        sys.stdout.write(" ".join(outcome) + "\n")
        sys.stdout.flush()

    def _show_help(self, *args):
        # equo help <foo> <bar>
        if len(self._args) > 1:
            # syntax error
            return -10

        parser = argparse.ArgumentParser(
            description=_("Entropy Command Line Client, Equo"),
            epilog="http://www.sabayon.org",
            formatter_class=ColorfulFormatter)

        # filtered out in solo.main. Will never get here
        parser.add_argument(
            "--color", action="store_true",
            default=None, help=_("force colored output"))

        descriptors = SoloCommandDescriptor.obtain()
        descriptors.sort(key = lambda x: x.get_name())
        group = parser.add_argument_group("command", "available commands")
        for descriptor in descriptors:
            if descriptor.get_class().HIDDEN:
                continue
            aliases = descriptor.get_class().ALIASES
            aliases_str = ", ".join([teal(x) for x in aliases])
            if aliases_str:
                aliases_str = " [%s]" % (aliases_str,)
            name = "%s%s" % (purple(descriptor.get_name()),
                aliases_str)
            desc = descriptor.get_description()
            group.add_argument(name, help=darkgreen(desc), action="store_true")
        parser.print_help()
        if not self._args:
            return 1
        return 0

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloHelp,
        SoloHelp.NAME,
        _("this help"))
    )
