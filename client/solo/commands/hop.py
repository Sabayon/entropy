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
from entropy.output import brown, purple, teal, darkred, bold, \
    red, darkgreen

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand, exclusivelock

class SoloHop(SoloCommand):
    """
    Main Solo Update command.
    """

    NAME = "hop"
    ALIASES = []

    INTRODUCTION = """\
Upgrade the System to a new branch.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._branch = None

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloHop.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloHop.NAME))

        parser.add_argument(
            "branch", metavar="<branch>", help=_("branch"))

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

        self._branch = nsargs.branch

        return self._call_exclusive, [self._hop]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        return self._bashcomp(sys.stdout, last_arg, [])

    @exclusivelock
    def _hop(self, entropy_client, inst_repo):
        """
        Solo Hop command.
        """
        settings = entropy_client.Settings()

        # set the new branch
        if self._branch == settings['repositories']['branch']:
            mytxt = "%s: %s" % (
                darkred(_("Already on branch")),
                purple(self._branch),
            )
            entropy_client.output(
                mytxt, level="warning", importance=1,
                header=bold(" !!! "))
            return 2

        old_repo_paths = []
        avail_data = settings['repositories']['available']
        for repoid in sorted(avail_data):
            old_repo_paths.append(avail_data[repoid]['dbpath'][:])

        old_branch = settings['repositories']['branch'][:]
        entropy_client.set_branch(self._branch)
        status = True

        repo_conf = settings.get_setting_files_data()['repositories']
        try:
            repo_intf = entropy_client.Repositories(None, force = False,
                fetch_security = False)
        except AttributeError as err:
            entropy_client.output(
                "%s %s [%s]" % (
                    purple(_("No repositories specified in")),
                    teal(repo_conf),
                    err,
                ),
                header=darkred(" * "),
                level="error", importance=1)
            status = False
        else:
            rc = repo_intf.sync()
            if rc and rc != 1:
                # rc != 1 means not all the repos have been downloaded
                status = False

        if status:
            inst_repo.moveSpmUidsToBranch(self._branch)

            mytxt = "%s: %s" % (
                darkgreen(_("Succesfully switched to branch")),
                purple(self._branch),)
            entropy_client.output(
                mytxt,
                header=red(" @@ "))
            mytxt = "%s %s" % (
                brown(" ?? "),
                darkgreen(_("Now run 'equo upgrade' to "
                            "upgrade your distribution to")),
                )
            entropy_client.output(mytxt)
            return 0

        entropy_client.set_branch(old_branch)

        mytxt = "%s: %s" % (
            darkred(_("Unable to switch to branch")),
            purple(self._branch),)
        entropy_client.output(
            mytxt, level="error",
            importance=1, header=bold(" !!! "))

        return 3

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloHop,
        SoloHop.NAME,
        _("upgrade the System to a new branch"))
    )
