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
from entropy.const import etpConst
from entropy.output import red, blue, brown, darkgreen

import entropy.tools

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand, sharedlock


class SoloUnused(SoloCommand):
    """
    Main Solo Unused command.
    """

    NAME = "unusedpackages"
    ALIASES = ["unused"]
    ALLOW_UNPRIVILEGED = True

    INTRODUCTION = """\
Report unused packages that could be removed.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._quiet = False
        self._sortbysize = False
        self._byuser = False
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
            SoloUnused.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloUnused.NAME))

        parser.add_argument("--quiet", "-q", action="store_true",
                            default=self._quiet,
                            help=_("show less details (useful for scripting)"))
        _commands.append("--quiet")
        _commands.append("-q")

        parser.add_argument("--sortbysize", action="store_true",
                            default=self._sortbysize,
                            help=_("sort packages by size"))
        _commands.append("--sortbysize")

        parser.add_argument("--by-user", action="store_true",
                            default=self._byuser,
                            help=_("include packages installed by user"))
        _commands.append("--by-user")

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

        self._quiet = nsargs.quiet
        self._sortbysize = nsargs.sortbysize
        self._byuser = nsargs.by_user

        return self._call_shared, [self._unused]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        import sys

        self._get_parser()
        return self._bashcomp(sys.stdout, last_arg, self._commands)

    @sharedlock
    def _unused(self, entropy_client, inst_repo):
        """
        Command implementation.
        """
        if not self._quiet:
            entropy_client.output(
                "%s..." % (
                    blue(_("Running unused packages test, "
                      "pay attention, there can be false positives")),),
                header=red(" @@ "))

        def _unused_packages_test():
            return [x for x in inst_repo.retrieveUnusedPackageIds() \
                        if entropy_client.validate_package_removal(x)]

        data = [(inst_repo.retrieveOnDiskSize(x), x, \
            inst_repo.retrieveAtom(x),) for x in \
                _unused_packages_test()]

        def _user_filter(item):
            _size, _pkg_id, _atom = item
            _source = inst_repo.getInstalledPackageSource(_pkg_id)
            if _source == etpConst['install_sources']['user']:
                # remove from list, user installed stuff not going
                # to be listed
                return False
            return True

        # filter: --by-user not provided -> if package has been installed
        # by user, exclude from list.
        if not self._byuser:
            data = list(filter(_user_filter, data))

        if self._sortbysize:
            data.sort(key = lambda x: x[0])

        if self._quiet:
            entropy_client.output(
                '\n'.join([x[2] for x in data]),
                level="generic")
        else:
            for disk_size, idpackage, atom in data:
                disk_size = entropy.tools.bytes_into_human(disk_size)
                entropy_client.output(
                    "# %s%s%s %s" % (
                        blue("["), brown(disk_size),
                        blue("]"), darkgreen(atom),))

        return 0

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloUnused,
        SoloUnused.NAME,
        _("look for unused packages (pay attention)"))
    )
