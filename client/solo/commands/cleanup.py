# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import os
import sys
import argparse

from entropy.i18n import _
from entropy.const import etpConst

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand
from solo.utils import cleanup

class SoloCleanup(SoloCommand):
    """
    Main Solo Match command.
    """

    NAME = "cleanup"
    ALIASES = []

    INTRODUCTION = """\
Remove downloaded packages and clean temporary directories.
"""
    SEE_ALSO = "equo-cache(1)"

    def __init__(self, args):
        SoloCommand.__init__(self, args)

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        return self._bashcomp(sys.stdout, last_arg, [])

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloCleanup.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloCleanup.NAME))

        return parser

    def parse(self):
        """
        Parse command.
        """
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        return self._call_exclusive, [self._cleanup]

    def _cleanup(self, entropy_client):
        """
        Solo Cleanup command.
        """
        dirs = [etpConst['logdir'], etpConst['entropyunpackdir']]
        for rel in etpConst['packagesrelativepaths']:
            # backward compatibility, packages are moved to packages/ dir,
            # including nonfree, restricted etc.
            dirs.append(os.path.join(etpConst['entropyworkdir'], rel))
            # new location
            dirs.append(os.path.join(
                    etpConst['entropypackagesworkdir'],
                    rel))
        cleanup(entropy_client, dirs)
        return 0

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloCleanup,
        SoloCleanup.NAME,
        _("remove downloaded packages and clean temp. directories"))
    )
