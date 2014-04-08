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

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.cp import EitCp


class EitMv(EitCp):
    """
    Main Eit mv command.
    """

    NAME = "mv"
    ALIASES = []

    INTRODUCTION = """\
Move packages from source repository to destination repository.
The operation is transactional, first package is copied to destination,
then is removed from source.
"""
    SEE_ALSO = "eit-cp(1)"

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError as err:
            sys.stderr.write("%s\n" % (err,))
            return parser.print_help, []

        self._source = nsargs.source
        self._dest = nsargs.dest
        self._deps = nsargs.deps
        self._ask = not nsargs.quick
        self._packages += nsargs.packages
        self._copy = False
        self._entropy_class()._inhibit_treeupdates = nsargs.conservative

        return self._call_exclusive, [self._move_copy, self._source]


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitMv,
        EitMv.NAME,
        _('move packages from a repository to another'))
    )
