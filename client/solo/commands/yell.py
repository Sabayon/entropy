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
from entropy.output import TextInterface
from entropy.cache import EntropyCacher

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand

class SoloYell(SoloCommand):
    """
    Main Solo yell command.
    """

    NAME = "yell"
    ALIASES = []
    CATCH_ALL = False
    ALLOW_UNPRIVILEGED = True
    HIDDEN = True

    _CACHE_KEY = "SoloYellStatus"
    _MESSAGES = {
        0: _("You should run equo --help"),
        1: _("You didn't run equo --help, did you?"),
        2: _("Did you even read equo --help??"),
        3: _("I give up. Run that equo --help !!!!!!!"),
        4: _("OH MY GOD. RUN equo --heeeeeeeeeeeeeelp"),
        5: _("Illiteracy is a huge problem in this world"),
        6: _("Ok i give up, you are hopeless"),
        7: _("Go to hell."),
        8: _("Go to hell."),
        9: _("Go to hell."),
        10: _("Go to hell."),
        11: _("Go to hell."),
        12: _("Stop that, you idiot."),
        13: _("Go to hell."),
    }

    INTRODUCTION = """\
Yell at user.
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
        return self._show_yell, []

    @staticmethod
    def read():
        cacher = EntropyCacher()
        status = cacher.pop(SoloYell._CACHE_KEY)
        if status is None:
            status = 0
            SoloYell.write(status)
        return status

    @staticmethod
    def write(status):
        cacher = EntropyCacher()
        try:
            cacher.save(SoloYell._CACHE_KEY, status)
        except IOError:
            pass

    @staticmethod
    def reset():
        """
        Reset Yell Status.
        """
        cacher = EntropyCacher()
        try:
            cacher.save(SoloYell._CACHE_KEY, 0)
        except IOError:
            pass

    def _show_yell(self, *args):
        yell_id = SoloYell.read()
        max_id = max(list(SoloYell._MESSAGES.keys()))
        yell_message = SoloYell._MESSAGES.get(
            yell_id, max_id)
        # do not use entropy_client here
        # it is slow and might interfere with
        # other Client inits.
        text = TextInterface()
        text.output(
            yell_message,
            importance=1,
            level="warning")
        new_yell_id = yell_id + 1
        if new_yell_id <= max_id:
            SoloYell.write(new_yell_id)
        return 1

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloYell,
        SoloYell.NAME,
        _("yell at user"))
    )
