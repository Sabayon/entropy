# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
from entropy.i18n import _
from entropy.output import TextInterface

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand

from solo.utils import read_client_release

class SoloVersion(SoloCommand):
    """
    Main Solo yell command.
    """

    NAME = "version"
    ALIASES = ["--version"]
    ALLOW_UNPRIVILEGED = True

    INTRODUCTION = """\
Show Equo version.
"""
    SEE_ALSO = "equo-help(1)"

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def parse(self):
        """
        Parse command
        """
        return self._show_version, []

    def _show_version(self, *args):
        # do not use entropy_client here
        # it is slow and might interfere with
        # other Client inits.
        release = read_client_release()
        text = TextInterface()
        text.output(release, level="generic")
        return 0

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloVersion,
        SoloVersion.NAME,
        _("show equo version"))
    )
