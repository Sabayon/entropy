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
import tempfile
import codecs
import time

from entropy.i18n import _
from entropy.output import purple, teal

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitPkgmove(EitCommand):
    """
    Main Eit pkgmove command.
    """

    NAME = "pkgmove"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._repository_id = None

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitPkgmove.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitPkgmove.NAME))

        parser.add_argument("repo", default=None,
                            metavar="<repo>", help=_("repository"))

        return parser

    def bashcomp(self, last_arg):
        """
        Overridden from EitCommand
        """
        import sys

        entropy_server = self._entropy(handle_uninitialized=False,
                                       installed_repo=-1)
        outcome = entropy_server.repositories()
        for arg in self._args:
            if arg in outcome:
                # already given a repo
                outcome = []
                break

        def _startswith(string):
            if last_arg is not None:
                if last_arg not in outcome:
                    return string.startswith(last_arg)
            return True

        if self._args:
            # only filter out if last_arg is actually
            # something after this.NAME.
            outcome = sorted(filter(_startswith, outcome))

        for arg in self._args:
            if arg in outcome:
                outcome.remove(arg)

        sys.stdout.write(" ".join(outcome) + "\n")
        sys.stdout.flush()

    def parse(self):
        parser = self._get_parser()
        try:
            nsargs = parser.parse_args(self._args)
        except IOError:
            return parser.print_help, []

        self._repository_id = nsargs.repo
        return self._call_locked, [self._pkgmove, self._repository_id]

    def _pkgmove(self, entropy_server):
        """
        Open $EDITOR and let user add/remove package moves.
        """
        notice_text = """\
# This is the package move metadata for repository %s, read this:
# - the statements must start with either "move" or "slotmove".
# - move statement syntax:
#      move <from package key> <to package key>
# - slotmove statement syntax:
#      slotmove <package dependency> <from slot> <to slot>
# - the order of the statements is taken into consideration (KEPT!).
# - lines not starting with "move" or "slotmove" will be ignored.
# - any line starting with "#" will be ignored as well.
#
# Example:
# move app-foo/bar app-bar/foo
# slotmove >=x11-libs/foo-2.0 0 2.0

""" % (self._repository_id,)
        tmp_path = None
        repo = entropy_server.open_server_repository(
            self._repository_id, read_only=False)
        actions = repo.retrieveTreeUpdatesActions(self._repository_id)
        new_actions = []
        while True:

            if tmp_path is None:
                tmp_fd, tmp_path = tempfile.mkstemp(
                    prefix = 'entropy.server.pkgmove',
                    suffix = ".conf")
                with os.fdopen(tmp_fd, "w") as tmp_f:
                    tmp_f.write(notice_text)
                    for action in actions:
                        tmp_f.write(action + "\n")
                    tmp_f.flush()

            success = entropy_server.edit_file(tmp_path)
            if not success:
                # retry ?
                os.remove(tmp_path)
                return 1

            del new_actions[:]
            invalid_lines = []
            with codecs.open(tmp_path, "r", encoding="utf-8") as tmp_f:
                for line in tmp_f.readlines():
                    if line.startswith("#"):
                        # skip
                        continue
                    strip_line = line.strip()
                    if not strip_line:
                        # ignore
                        continue
                    if strip_line.startswith("move"):
                        split_line = strip_line.split()
                        if len(split_line) != 3:
                            entropy_server.output(
                                "%s: %s !!!" % (_("invalid line"), strip_line),
                                importance=1, level="warning")
                            invalid_lines.append(strip_line)
                        else:
                            new_actions.append(strip_line)
                    elif strip_line.startswith("slotmove"):
                        split_line = strip_line.split()
                        if len(split_line) != 4:
                            entropy_server.output(
                                "%s: %s !!!" % (
                                    purple(_("invalid line")), strip_line),
                                importance=1, level="warning")
                            invalid_lines.append(strip_line)
                        else:
                            new_actions.append(strip_line)
                    else:
                        entropy_server.output(
                            "%s: %s !!!" % (
                                purple(_("invalid line")), strip_line),
                            importance=1, level="warning")
                        invalid_lines.append(strip_line)

            if invalid_lines:
                resp = entropy_server.ask_question(
                    _("Invalid syntax, what to do ?"),
                    responses=(_("Repeat"), _("Abort")))
                if resp == _("Abort"):
                    os.remove(tmp_path)
                    return 1
                else:
                    # repeat, edit same file
                    continue

            # show submitted info
            for action in new_actions:
                entropy_server.output(action, level="generic")
            entropy_server.output("", level="generic")

            # ask confirmation
            while True:
                try:
                    rc_question = entropy_server.ask_question(
                        "[%s] %s" % (
                            purple(self._repository_id),
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
                return 1
            # otherwise repeat everything again
            # keep tmp_path

        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except (OSError) as err:
                if err.errno != errno.ENOENT:
                    raise

        # write new actions
        branch = self._settings()['repositories']['branch']
        actions_meta = []
        cur_t = time.time()
        # time is completely fake, no particular precision required
        for action in new_actions:
            cur_t += 1
            actions_meta.append((action, branch, str(cur_t)))

        repo.removeTreeUpdatesActions(self._repository_id)
        try:
            repo.insertTreeUpdatesActions(actions_meta, self._repository_id)
        except Exception as err:
            repo.rollback()
            raise
        repo.commit()

        return 0


EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitPkgmove,
        EitPkgmove.NAME,
        _('edit automatic package moves for repository'))
    )
