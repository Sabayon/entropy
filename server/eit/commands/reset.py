# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import sys
import argparse

from entropy.i18n import _
from entropy.output import darkgreen

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.pull import EitPull


class EitReset(EitPull):
    """
    Main Eit reset command.
    """

    NAME = "reset"
    ALIASES = []

    def __init__(self, args):
        EitPull.__init__(self, args)
        self._reset_repository_id = None
        self._local = False

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitReset.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitReset.NAME))

        parser.add_argument("repo", nargs='?', default=None,
                            metavar="<repo>", help=_("repository"))
        parser.add_argument("--quick", action="store_true",
                            default=False,
                            help=_("no stupid questions"))
        parser.add_argument("--local", action="store_true",
                            default=False,
                            help=_("do not pull the remote repository"))

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
        outcome += ["--quick", "--local"]

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
Discard all the changes made to the local repository by completely
re-fetching the remote version available on mirrors.
"""

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        """ Overridden from EitPull """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._local = nsargs.local
        self._ask = not nsargs.quick
        if nsargs.repo is not None:
            self._repositories.append(nsargs.repo)
            self._reset_repository_id = nsargs.repo

        return self._call_exclusive, [self._reset, nsargs.repo]

    def _reset(self, entropy_server):
        repository_id = self._reset_repository_id
        if repository_id is None:
            repository_id = entropy_server.repository()
        rev_path = entropy_server._get_local_repository_revision_file(
            repository_id)

        try:
            with open(rev_path, "w") as rev_f:
                rev_f.write("0\n")
        except (IOError, OSError) as err:
            entropy_server.output(
                "%s: %s" % (_("reset error"), err),
                importance=1, level="error")
            return 1

        entropy_server.output(
            darkgreen(_("local repository revision reset complete")),
            importance=1)
        if self._local:
            return 0

        return self._pull(entropy_server)

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitReset,
        EitReset.NAME,
        _('reset repository to remote status'))
    )
