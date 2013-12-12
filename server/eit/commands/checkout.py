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

from entropy.output import darkgreen, blue
from entropy.i18n import _

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitCheckout(EitCommand):
    """
    Main Eit checkout command.
    """

    NAME = "checkout"
    ALIASES = ["co"]

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitCheckout.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitCheckout.NAME))

        parser.add_argument("repo", metavar="<repo>",
                            help=_("repository"))
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
Change the current working repository. Unlike *git checkout* this
doesn't work with package names or whatever. Current functionalities
are just limited to repository hopping. If you want to switch to
another branch, iuse *eit branch*.
"""
    SEE_ALSO = "eit-branch(1)"

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
            return parser.print_help, []

        return self._call_exclusive, [self._checkout, nsargs.repo]

    def _checkout(self, entropy_server):
        """
        Actual Entropy Repository checkout function
        """
        repository_id = entropy_server.repository()
        entropy_server.switch_default_repository(repository_id,
            save = True)
        # show interface info
        entropy_server._show_interface_status()
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitCheckout,
        EitCheckout.NAME,
        _('switch from a repository to another'))
    )
