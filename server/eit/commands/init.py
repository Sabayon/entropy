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

from entropy.i18n import _
from entropy.output import darkgreen, teal

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitInit(EitCommand):
    """
    Main Eit init command.
    """

    NAME = "init"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._ask = True

    def _get_parser(self):
        """ Overridden from EitInit """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitInit.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitInit.NAME))

        parser.add_argument("repo", nargs=1, default=None,
                            metavar="<repo>", help=_("repository"))
        parser.add_argument("--quick", action="store_true",
                            default=not self._ask,
                            help=_("no stupid questions"))

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
        outcome += ["--quick"]

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
Initialize a given repository. The same must be already configured
in */etc/entropy/server.conf* for this tool to work as expected.
So, please setup your repository there and only then run *eit init <repo>*.
"""

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        """ Overridden from EitInit """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._ask = not nsargs.quick
        return self._call_exclusive, [self._init, nsargs.repo[0]]

    def _init(self, entropy_server):
        rc = entropy_server.initialize_repository(
            entropy_server.repository(), ask=self._ask)
        if rc == 0:
            entropy_server.output(
                teal(_("Entropy repository has been initialized")),
                header=darkgreen(" * "),
                importance=1)
            return 0
        return 1

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitInit,
        EitInit.NAME,
        _('initialize repository (erasing all its content)'))
    )
