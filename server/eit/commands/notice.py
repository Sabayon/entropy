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
import errno
import argparse
import codecs

from entropy.i18n import _
from entropy.output import blue, darkred, darkgreen, purple, brown, teal
from entropy.const import const_mkstemp

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitNotice(EitCommand):
    """
    Main Eit notice command.
    """

    NAME = "notice"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._repository_id = None

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitNotice.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitNotice.NAME))

        subparsers = parser.add_subparsers(
            title="action", description=_("execute given action"),
            help=_("available actions"))

        add_parser = subparsers.add_parser("add",
            help=_("add notice-board entry"))
        add_parser.add_argument("repo", nargs='?', default=None,
                                metavar="<repo>", help=_("repository"))
        add_parser.set_defaults(func=self._add)

        remove_parser = subparsers.add_parser("remove",
            help=_("remove notice-board entry"))
        remove_parser.add_argument("repo", nargs='?', default=None,
                                   metavar="<repo>", help=_("repository"))
        remove_parser.set_defaults(func=self._remove)

        show_parser = subparsers.add_parser("show",
            help=_("show notice-board"))
        show_parser.add_argument("repo", nargs='?', default=None,
                                   metavar="<repo>", help=_("repository"))
        show_parser.set_defaults(func=self._show)

        return parser

    INTRODUCTION = """\
Notice-board is the way to communicate news or other misc info to your users
through repositories. The repository notice-board is downloaded (if available)
whenever the user updates the local repositories. The Entropy Client is going to
list notice-board titles for user consumption.
"""

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError:
            return parser.print_help, []

        # Python 3.3 bug #16308
        if not hasattr(nsargs, "func"):
            return parser.print_help, []

        self._repository_id = nsargs.repo
        return self._call_exclusive, [nsargs.func, self._repository_id]

    def _add_notice_editor(self, entropy_server, repository_id):
        """
        Open $EDITOR and let user write his notice-board entry.
        """
        notice_text = """

# Please enter the notice-board text above as follows:
# - the first line is considered the title
# - the following lines are considered the actual message
#   body of the notice-board entry
# - the last line, if starting with URL: will be parsed as the
#   actual notice-board entry URL
# - any line starting with "#" will be removed
#
# Example:
# [message title]
# [message
#         body]
# URL: http://<url>
"""
        notice_title = None
        notice_body = ""
        notice_url = None
        tmp_path = None
        while True:

            if tmp_path is None:
                tmp_fd, tmp_path = const_mkstemp(
                    prefix = 'entropy.server',
                    suffix = ".conf")
                with os.fdopen(tmp_fd, "w") as tmp_f:
                    tmp_f.write(notice_text)
                    tmp_f.flush()

            success = entropy_server.edit_file(tmp_path)
            if not success:
                # retry ?
                os.remove(tmp_path)
                tmp_path = None
                continue

            notice_title = None
            notice_body = ""
            notice_url = None
            all_good = False
            with codecs.open(tmp_path, "r", encoding="utf-8") as tmp_f:
                line = None
                last_line = None
                for line in tmp_f.readlines():
                    if line.startswith("#"):
                        # skip
                        continue
                    strip_line = line.strip()
                    if not strip_line:
                        # ignore
                        continue
                    if notice_title is None:
                        notice_title = strip_line
                        continue
                    last_line = line
                    notice_body += line
                if last_line is not None:
                    if last_line.startswith("URL:"):
                        url = last_line.strip()[4:].strip()
                        if url:
                            notice_url = url
                        # drop last line then
                        notice_body = notice_body[:-len(last_line)]
            if notice_title and notice_body:
                all_good = True

            if not all_good:
                os.remove(tmp_path)
                tmp_path = None
                continue

            # show submitted info
            entropy_server.output(
                "%s: %s" % (
                    darkgreen(_("Title")),
                    purple(notice_title)),
                level="generic")
            entropy_server.output("", level="generic")
            entropy_server.output(
                notice_body, level="generic")
            url = notice_url
            if url is None:
                url = _("no URL")
            entropy_server.output(
                "%s: %s" % (teal(_("URL")), brown(url)),
                level="generic")
            entropy_server.output("", level="generic")

            # ask confirmation
            while True:
                try:
                    rc_question = entropy_server.ask_question(
                        "[%s] %s" % (
                            purple(repository_id),
                            teal(_("Do you agree?"))
                        ),
                        responses = (_("Yes"), _("Repeat"), _("No"),)
                    )
                except KeyboardInterrupt:
                    # do not allow, we're in a critical region
                    continue
                break
            if rc_question == _("Yes"):
                break
            elif rc_question == _("No"):
                return None, None, None
            # otherwise repeat everything again
            # keep tmp_path

        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except (OSError) as err:
                if err.errno != errno.ENOENT:
                    raise

        return notice_title, notice_body, notice_url

    def _add(self, entropy_server):
        """
        Actual Eit notice add code.
        """
        if self._repository_id is None:
            self._repository_id = entropy_server.repository()

        notice_title, notice_body, notice_url = \
            self._add_notice_editor(entropy_server, self._repository_id)
        if (notice_title is None) or (notice_body is None):
            return 1

        status = entropy_server.Mirrors.update_notice_board(
            self._repository_id, notice_title, notice_body,
            link = notice_url)
        if status:
            return 0
        return 1

    def _remove(self, entropy_server):
        """
        Actual Eit notice remove code.
        """
        if self._repository_id is None:
            self._repository_id = entropy_server.repository()

        data = entropy_server.Mirrors.read_notice_board(
            self._repository_id)
        if data is None:
            entropy_server.output(
                purple(_("Notice board not available")),
                importance=1, level="error")
            return 1

        items, counter = data
        changed = False
        while True:
            try:
                sel = self._show_notice_selector(
                    entropy_server,
                    darkgreen(_("Choose the one you want to remove")),
                    items)
            except KeyboardInterrupt:
                break

            if (sel >= 0) and (sel <= counter):
                self._show_notice(entropy_server, sel, items.get(sel))
                q_rc = entropy_server.ask_question(
                    _("Are you sure you want to remove this?"))
                if q_rc == _("Yes"):
                    changed = True
                    entropy_server.Mirrors.remove_from_notice_board(
                        self._repository_id, sel)
                    data = entropy_server.Mirrors.read_notice_board(
                        self._repository_id, do_download = False)
                    items, counter = data
            elif sel == -1:
                break

        if changed or (counter == 0):
            if counter == 0:
                status = entropy_server.Mirrors.remove_notice_board(
                    self._repository_id)
            else:
                status = entropy_server.Mirrors.upload_notice_board(
                    self._repository_id)
            if not status:
                return 1
        return 0

    def _show(self, entropy_server):
        """
        Actual Eit notice show code.
        """
        if self._repository_id is None:
            self._repository_id = entropy_server.repository()

        data = entropy_server.Mirrors.read_notice_board(
            self._repository_id)
        if data is None:
            entropy_server.output(
                purple(_("Notice board not available")),
                importance=1, level="error")
            return 1

        items, counter = data
        while True:
            try:
                sel = self._show_notice_selector(entropy_server, '', items)
            except KeyboardInterrupt:
                return 0
            if (sel >= 0) and (sel <= counter):
                self._show_notice(entropy_server, sel, items.get(sel))
            elif sel == -1:
                return 0

        return 0

    def _show_notice(self, entropy_server, key, mydict):
        """
        Print notice board entry content
        """
        mytxt = "[%s] [%s]" % (
            blue(str(key)),
            brown(mydict['pubDate']),
        )
        entropy_server.output(mytxt)
        entropy_server.output("", level="generic")
        entropy_server.output(
            "%s: %s" % (darkgreen(_("Title")),
                        purple(mydict['title'])),
            level="generic")

        entropy_server.output("", level="generic")
        entropy_server.output(mydict['description'], level="generic")
        entropy_server.output("", level="generic")

        mytxt = "%s: %s" % (
            darkgreen(_("URL")),
            blue(mydict['link']),
        )
        entropy_server.output(mytxt)

        def fake_callback(dummy_s):
            return True

        input_params = [
            ('idx', _('Press Enter to continue'), fake_callback, False)
            ]
        data = entropy_server.input_box(
            '', input_params, cancel_button = True)

    def _show_notice_selector(self, entropy_server, title, mydict):
        """
        Show notice board entries selector, return selected entry id.
        """
        entropy_server.output("")
        mykeys = sorted(mydict.keys())

        for key in mykeys:
            mydata = mydict.get(key)
            mytxt = "[%s] [%s] %s: %s" % (
                blue(str(key)),
                brown(mydata['pubDate']),
                _("Title"),
                darkred(mydata['title']),
            )
            entropy_server.output(mytxt)

        entropy_server.output("")
        mytxt = "[%s] %s" % (
            blue("-1"),
            darkred(_("Exit/Commit")),
        )
        entropy_server.output(mytxt)

        def fake_callback(s):
            return s
        input_params = [
            ('id', blue(_('Choose one by typing its identifier')),
            fake_callback, False)]
        data = entropy_server.input_box(title, input_params,
            cancel_button = True)
        if not isinstance(data, dict):
            return -1
        try:
            return int(data['id'])
        except ValueError:
            return -2


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitNotice,
        EitNotice.NAME,
        _('manage repository notice-board'))
    )
