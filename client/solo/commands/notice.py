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
from entropy.output import darkred, blue, brown, darkgreen

from entropy.client.interfaces.noticeboard import NoticeBoard

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand

class SoloNotice(SoloCommand):
    """
    Main Solo Notice command.
    """

    NAME = "notice"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True

    INTRODUCTION = """\
Read Repository Notice Board.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._nsargs = None

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
            SoloNotice.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloNotice.NAME))

        parser.add_argument("repo", nargs='+',
                            metavar="<repo>", help=_("repository"))

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

        self._nsargs = nsargs
        return self._call_shared, [self._reader]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        entropy_client = self._entropy_bashcomp()
        settings = entropy_client.Settings()
        repos = settings['repositories']['available']
        return self._bashcomp(sys.stdout, last_arg, repos)

    def _reader(self, entropy_client):
        """
        Solo Notice Board Reader.
        """
        exit_st = 0
        for repo in self._nsargs.repo:
            _exit_st = self._notice_reader(entropy_client, repo)
            if _exit_st != 0:
                exit_st = _exit_st
        return exit_st

    def _notice_reader(self, entropy_client, repo):
        """
        Solo Notice Board Reader for given Repository.
        """
        data = self._check_notice_board_availability(
            entropy_client, repo)
        if not data:
            return 1

        counter = len(data)
        while True:
            try:
                sel = self._show_notice_selector(
                    entropy_client, '', data)
            except KeyboardInterrupt:
                return 0
            if (sel >= 0) and (sel < counter):
                self._show_notice(
                    entropy_client, sel, data.get(sel))
            elif sel == -1:
                return 0

    def _check_notice_board_availability(self, entropy_client, repo):
        """
        Check Notice Board availability.
        """
        def show_err():
            entropy_client.output(
                blue(_("Notice board not available")),
                level="error", importance=1,
                header=darkred(" @@ "))

        nb = NoticeBoard(repo)
        try:
            data = nb.data()
        except KeyError:
            data = None

        if not data:
            show_err()
            return

        return data

    def _show_notice_selector(self, entropy_client, title, mydict):
        """
        Show interactive Notice Board selector.
        """
        mykeys = sorted(mydict.keys())

        for key in mykeys:
            mydata = mydict.get(key)
            mytxt = "[%s] [%s] %s: %s" % (
                blue(str(key)),
                brown(mydata['pubDate']),
                _("Title"),
                darkred(mydata['title']),
            )
            entropy_client.output(mytxt)

        mytxt = "[%s] %s" % (
            blue("-1"),
            darkred(_("Exit")),
        )
        entropy_client.output(mytxt)

        def fake_callback(s):
            return s
        input_params = [
            (
                'id',
                blue(_('Choose one by typing its identifier')),
                fake_callback,
                False)
            ]
        data = entropy_client.input_box(
            title, input_params, cancel_button = True)

        if not isinstance(data, dict):
            return -1
        try:
            return int(data['id'])
        except ValueError:
            return -2

    def _show_notice(self, entropy_client, key, mydict):
        """
        Show Notice Board element.
        """
        mytxt = "[%s] [%s] %s: %s" % (
            blue(str(key)),
            brown(mydict['pubDate']),
            _("Title"),
            darkred(mydict['title']),
        )
        entropy_client.output(mytxt)

        mytxt = "%s:\n\n%s\n" % (
            darkgreen(_("Content")),
            mydict['description'],
        )
        entropy_client.output(mytxt)
        mytxt = "%s: %s" % (
            darkgreen(_("Link")),
            blue(mydict['link']),
        )
        entropy_client.output(mytxt)

        def fake_callback(s):
            return True

        input_params = [
            ('idx', _("Press Enter to continue"), fake_callback, False)]
        entropy_client.input_box('', input_params, cancel_button = True)


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloNotice,
        SoloNotice.NAME,
        _("repository notice board reader"))
    )
