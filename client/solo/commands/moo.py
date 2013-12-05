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

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand

class SoloFunny(SoloCommand):

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def parse(self):
        """
        Parse command
        """
        return self._show_msg, []

    def _get_message(self):
        """
        Return the funny message to show.
        """
        raise NotImplementedError()

    def _show_msg(self, *args):
        entropy_client = self._entropy()
        entropy_client.output(self._get_message())
        return 0


class SoloMoo(SoloFunny):
    """
    Main Solo moo command.
    """

    NAME = "moo"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True
    HIDDEN = True

    INTRODUCTION = """\
Moo at user.
"""
    SEE_ALSO = ""

    def _get_message(self):
        """
        Reimplemented from SoloFunny.
        """
        t = """
 _____________
< Entromoooo! >
 -------------
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\\
                ||----w |
                ||     ||
"""
        return t


class SoloLxnay(SoloFunny):
    """
    Main Solo lxnay command.
    """

    NAME = "lxnay"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True
    HIDDEN = True

    INTRODUCTION = """\
Bow to the Highness.
"""
    SEE_ALSO = ""

    def _get_message(self):
        """
        Reimplemented from SoloFunny.
        """
        t = """
 ________________________
< Hail to the king, baby! >
 ------------------------
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\\
                ||----w |
                ||     ||
"""
        return t


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloMoo,
        SoloMoo.NAME,
        _("moo at user"))
    )

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloLxnay,
        SoloLxnay.NAME,
        _("bow to lxnay"))
    )
