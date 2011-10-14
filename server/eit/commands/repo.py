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


class EitRepo(EitCommand):
    """
    Main Eit repo command.
    """

    NAME = "repo"
    ALIASES = []

    def parse(self):
        """ Overridden from EitRepo """
        return self._call_locked, [self._void, None]

    def _void(self, entropy_server):
        entropy_server._show_interface_status()
        entropy_server.Mirrors._show_interface_status(
            entropy_server.repository())
        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitRepo,
        EitRepo.NAME,
        _('show current repository'))
    )
