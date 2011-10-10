# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import argparse

from entropy.i18n import _

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand

class EitHelp(EitCommand):
    """
    Main Eit help command.
    """

    NAME = "help"
    ALIASES = ["-h", "--help"]
    CATCH_ALL = True

    def parse(self):
        """
        Parse help command
        """
        return self._show_help, []

    def _show_help(self, *args):
        parser = argparse.ArgumentParser(
            description=_("Entropy Infrastructure Toolkit"),
            epilog="http://www.sabayon.org",
            formatter_class=argparse.RawDescriptionHelpFormatter)

        descriptors = EitCommandDescriptor.obtain()
        descriptors.sort(key = lambda x: x.get_name())
        group = parser.add_argument_group("command", "available commands")
        for descriptor in descriptors:
            aliases_str = ", ".join(descriptor.get_class().ALIASES)
            if aliases_str:
                aliases_str = " [%s]" % (aliases_str,)
            name = "%s%s" % (descriptor.get_name(), aliases_str)
            group.add_argument(name,
                               help=descriptor.get_description(),
                               action="store_true")
        parser.print_help()
        if not self._args:
            return 1
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitHelp,
        EitHelp.NAME,
        _("this help"))
    )
