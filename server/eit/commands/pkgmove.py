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
from entropy.output import purple, teal
from entropy.const import const_mkstemp

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

    INTRODUCTION = """\
Packages can be renamed or get their SLOT changed over time (say
thanks to Source Package Managers like Portage :-/).
To ensure that Entropy Clients do update their metadata accordingly,
any change done server-side is recorded into the repository itself.
This tool makes possible to edit such "raw" metadata.
The risk of completely disrupting Entropy Clients (and distro installs)
is very high, use this tool *only, and only if* you know what you're
doing.
"""

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

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
        return self._call_exclusive, [self._pkgmove, self._repository_id]

    def _pkgmove(self, entropy_server):
        """
        Open $EDITOR and let user add/remove package moves.
        """
        notice_text = """\
# This is the package move metadata for repository %s, read this:
# - the statements must start with either "move" or "slotmove".
# - move statement syntax:
#      <unix time> move <from package key> <to package key>
# - slotmove statement syntax:
#      <unix time> slotmove <package dependency> <from slot> <to slot>
# - the order of the statements is given by the unix time (ASC).
# - lines not starting with "<unix time> move" or "<unix time> slotmove"
#   will be ignored.
# - any line starting with "#" will be ignored as well.
#
# Example:
# 1319039371.22 move app-foo/bar app-bar/foo
# 1319039323.10 slotmove >=x11-libs/foo-2.0 0 2.0

""" % (self._repository_id,)
        tmp_path = None

        branch = self._settings()['repositories']['branch']
        repo = entropy_server.open_server_repository(
            self._repository_id, read_only=False)
        treeupdates = [(unix_time, t_action) for \
                           idupd, t_repo, t_action, t_branch, unix_time in \
                           repo.listAllTreeUpdatesActions() \
                           if t_repo == self._repository_id \
                           and t_branch == branch]
        key_sorter = lambda x: x[0]

        treeupdates.sort(key=key_sorter)
        new_actions = []
        while True:

            if tmp_path is None:
                tmp_fd, tmp_path = const_mkstemp(
                    prefix = 'entropy.server.pkgmove',
                    suffix = ".conf")
                with os.fdopen(tmp_fd, "w") as tmp_f:
                    tmp_f.write(notice_text)
                    for unix_time, action in treeupdates:
                        tmp_f.write("%s %s\n" % (unix_time, action))
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

                    split_line = strip_line.split()
                    try:
                        unix_time = split_line.pop(0)
                        unix_time = str(float(unix_time))
                    except ValueError:
                        # invalid unix time
                        entropy_server.output(
                            "%s: %s !!!" % (
                                purple(_("invalid line (time field)")),
                                strip_line),
                            importance=1, level="warning")
                        invalid_lines.append(strip_line)
                        continue
                    except IndexError:
                        entropy_server.output(
                            "%s: %s !!!" % (
                                purple(_("invalid line (empty)")),
                                strip_line),
                            importance=1, level="warning")
                        invalid_lines.append(strip_line)
                        continue

                    if not split_line:
                        # nothing left??
                        entropy_server.output(
                            "%s: %s !!!" % (
                                purple(_("invalid line (incomplete)")),
                                strip_line),
                            importance=1, level="warning")
                        invalid_lines.append(strip_line)
                        continue

                    cmd = split_line.pop(0)
                    if cmd == "move":
                        if len(split_line) != 2:
                            entropy_server.output(
                                "%s: %s !!!" % (_("invalid line"), strip_line),
                                importance=1, level="warning")
                            invalid_lines.append(strip_line)
                        elif split_line[0] == split_line[1]:
                            entropy_server.output(
                                "%s: %s !!!" % (
                                    _("invalid line (copy)"), strip_line),
                                importance=1, level="warning")
                            invalid_lines.append(strip_line)
                        else:
                            new_action = " ".join(["move"] + split_line)
                            new_actions.append((unix_time, new_action))
                    elif cmd == "slotmove":
                        if len(split_line) != 3:
                            entropy_server.output(
                                "%s: %s !!!" % (
                                    purple(_("invalid line")), strip_line),
                                importance=1, level="warning")
                            invalid_lines.append(strip_line)
                        elif split_line[1] == split_line[2]:
                            entropy_server.output(
                                "%s: %s !!!" % (
                                    purple(_("invalid line (copy)")),
                                    strip_line),
                                importance=1, level="warning")
                            invalid_lines.append(strip_line)
                        else:
                            new_action = " ".join(["slotmove"] + split_line)
                            new_actions.append((unix_time, new_action))
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
            new_actions.sort(key=key_sorter)
            for unix_time, action in new_actions:
                entropy_server.output(
                    "%s %s" % (unix_time, action), level="generic")
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
        actions_meta = []
        # time is completely fake, no particular precision required
        for unix_time, action in new_actions:
            # make sure unix_time has final .XX
            if "." not in unix_time:
                unix_time += ".00"
            elif unix_time.index(".") == (len(unix_time) - 2):
                # only .X and not .XX
                unix_time += "0"
            actions_meta.append((action, branch, unix_time))

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
