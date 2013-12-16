# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import os
import errno
import sys
import argparse
import subprocess

from entropy.const import const_convert_to_unicode, const_is_python3, \
    const_mkstemp
if const_is_python3():
    from subprocess import getoutput
else:
    from commands import getoutput

from entropy.i18n import _
from entropy.output import readtext, darkgreen, brown, teal, purple, \
    blue, darkred

import entropy.tools

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand


class SoloConf(SoloCommand):
    """
    Main Solo Conf command.
    """

    NAME = "conf"
    ALIASES = []
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
Manage package file updates.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)
        self._nsargs = None
        self._commands = []

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = []

        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloConf.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloConf.NAME))

        subparsers = parser.add_subparsers(
            title="action",
            description=_("manage configuration file updates"),
            help=_("available commands"))

        update_parser = subparsers.add_parser(
            "update", help=_("update configuration files"))
        update_parser.set_defaults(func=self._update)
        _commands.append("update")

        self._commands = _commands
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

        # Python 3.3 bug #16308
        if not hasattr(nsargs, "func"):
            return parser.print_help, []

        self._nsargs = nsargs
        return self._call_shared, [nsargs.func]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        outcome = []
        parser = self._get_parser()
        try:
            command = self._args[0]
        except IndexError:
            command = None

        if not self._args:
            # show all the commands
            outcome += self._commands

        elif command not in self._commands:
            # return all the commands anyway
            # last_arg will filter them
            outcome += self._commands

        elif command == "update":
            pass # nothing to add

        return self._bashcomp(sys.stdout, last_arg, outcome)

    def _update(self, entropy_client, cmd=None):
        """
        Solo Conf Enable command.
        """
        docmd = False
        if cmd != None:
            docmd = True

        updates = entropy_client.ConfigurationUpdates()
        paths_map = {}
        first_pass = True

        while True:
            entropy_client.output(
                "%s..." % (
                    darkgreen(_("Scanning filesystem")),),
                header=brown(" @@ "))

            scandata = updates.get()
            if not scandata:
                entropy_client.output(
                    teal(_("All fine baby. Nothing to do!"))
                    )
                break
            root = scandata.root()

            if first_pass:
                paths_map.update(dict(enumerate(sorted(scandata.keys()), 1)))
            first_pass = False

            for idx in sorted(paths_map.keys()):
                x = paths_map[idx]
                try:
                    obj = scandata[x]
                except KeyError:
                    # duplicated entry?
                    del paths_map[idx]
                    continue
                file_path = root + obj['destination']
                entropy_client.output(
                    "(%s) %s: %s" % (
                        blue("%d" % (idx,)),
                        darkgreen(_("file")),
                        x))

            if not paths_map:
                entropy_client.output(
                    teal(_("All fine baby. Nothing to do!")))
                break

            if not docmd:
                cmd = self._selfile(entropy_client)
            else:
                docmd = False
            try:
                cmd = int(cmd)
            except (ValueError, TypeError):
                entropy_client.output(
                    _("Type a number"),
                    level="error", importance=1)
                continue

            # actions
            if cmd == -1:
                # exit
                return -1

            elif cmd in (-3, -5):
                # automerge files asking one by one
                self._automerge(cmd, entropy_client,
                                root, paths_map, scandata)
                break

            elif cmd in (-7, -9):
                self._autodiscard(cmd, entropy_client,
                             root, paths_map, scandata)
                break

            elif cmd > 0:
                if self._handle_command(
                    cmd, entropy_client, root,
                    paths_map, scandata):
                    continue
                break

    def _selfile(self, entropy_client):
        entropy_client.output(
            darkred(
                _("Please choose a file to update by typing "
                  "its identification number.")))

        entropy_client.output(
            darkred(_("Other options are:")))
        entropy_client.output(
            "  (%s) %s" % (
                blue(const_convert_to_unicode("-1")),
                darkgreen(_("Exit")),
                ))
        entropy_client.output(
            "  (%s) %s" % (
                blue(const_convert_to_unicode("-3")),
                brown(_("Automerge all the files asking you one by one")),
                ))
        entropy_client.output(
            "  (%s) %s" % (
                blue(const_convert_to_unicode("-5")),
                darkred(_("Automerge all the files without questioning")),
                ))
        entropy_client.output(
            "  (%s) %s" % (
                blue(const_convert_to_unicode("-7")),
                brown(_("Discard all the files asking you one by one")),
                ))
        entropy_client.output(
            "  (%s) %s" % (
                blue(const_convert_to_unicode("-9")),
                darkred(_("Discard all the files without questioning")),
                ))

        # wait user interaction
        try:
            action = readtext(
                _("Your choice (type a number and press enter):")+" ")
        except EOFError:
            action = None
        return action

    def _selaction(self, entropy_client):
        entropy_client.output(darkred(
                _("Please choose an action to take for"
                  " the selected file.")))
        entropy_client.output(
            "  (%s) %s" % (
                blue(const_convert_to_unicode("-1")),
                darkgreen(_("Come back to the files list")),
                ))
        entropy_client.output(
            "  (%s) %s" % (
                blue(const_convert_to_unicode("1")),
                brown(_("Replace original with update")),
                ))
        entropy_client.output(
            "  (%s) %s" % (
                blue(const_convert_to_unicode("2")),
                darkred(_("Delete update, keeping original as is")),
                ))
        entropy_client.output(
            "  (%s) %s" % (
                blue(const_convert_to_unicode("3")),
                brown(_("Edit proposed file and show diffs again")),
                ))
        entropy_client.output(
            "  (%s) %s" % (
                blue(const_convert_to_unicode("4")),
                brown(_("Interactively merge original with update")),
                ))
        entropy_client.output(
            "  (%s) %s" % (
                blue(const_convert_to_unicode("5")),
                darkred(_("Show differences again")),
                ))

        # wait user interaction
        try:
            action = readtext(
                _("Your choice (type a number and press enter):")+" ")
        except EOFError:
            action = None
        return action

    def _showdiff(self, entropy_client, fromfile, tofile):

        args = ["diff", "-Nu", "'"+fromfile+"'", "'"+tofile+"'"]
        output = getoutput(' '.join(args)).split("\n")

        coloured = []
        for line in output:
            if line.startswith("---"):
                line = darkred(line)
            elif line.startswith("+++"):
                line = darkgreen(line)
            elif line.startswith("@@"):
                line = brown(line)
            elif line.startswith("-"):
                line = blue(line)
            elif line.startswith("+"):
                line = darkgreen(line)
            coloured.append(line + "\n")

        fd, tmp_path = None, None
        try:
            fd, tmp_path = const_mkstemp(
                suffix="equo.conf.showdiff")
            with os.fdopen(fd, "w") as f:
                f.writelines(coloured)
                f.flush()
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

        print("")
        pager = os.getenv("PAGER", "/usr/bin/less")
        if os.path.lexists(pager):
            if pager == "/usr/bin/less":
                args = [pager, "-R", "--no-init",
                        "--QUIT-AT-EOF", tmp_path]
            else:
                args = [pager, tmp_path]
        else:
            args = ["/bin/cat", tmp_path]
        try:
            subprocess.call(args)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
            args = ["/bin/cat", tmp_path]
            subprocess.call(args)

        os.remove(tmp_path)

        if output == ['']:
            return []
        return output

    def _automerge(self, cmd, entropy_client, root, paths_map, scandata):
        """
        Execute -3 and -5 actions.
        """
        idxs = sorted(paths_map.keys())
        for idx in idxs:
            self._merge(cmd, entropy_client, root,
                        paths_map, idx, scandata)

    def _merge(self, cmd, entropy_client, root, paths_map, idx, scandata):
        """
        Execute the config file merge action.
        """
        try:
            source = paths_map[idx]
        except KeyError:
            # idiot
            return

        data = scandata.get(source)
        if data is None:
            return

        source_path = root + source
        destination_path = root + data['destination']

        entropy_client.output(
            "%s: %s" % (
                darkred(_("Source file")),
                teal(source_path),)
        )
        entropy_client.output(
            "%s: %s" % (
                darkred(_("Destination file")),
                purple(destination_path),)
        )
        if cmd == -3:
            rc = entropy_client.ask_question(
                _("Overwrite ?"))
            if rc == _("No"):
                return

        merged = scandata.merge(source)
        del paths_map[idx]
        if not merged:
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("Cannot merge")),
                    brown(source_path),),
                level="warning")

        entropy_client.output("--")

    def _autodiscard(self, cmd, entropy_client, root,
                     paths_map, scandata):
        """
        Execute -7 and -9 actions.
        """
        idxs = sorted(paths_map.keys())
        for idx in idxs:
            self._discard(cmd, entropy_client, root,
                          paths_map, idx, scandata)

    def _discard(self, cmd, entropy_client, root,
                 paths_map, idx, scandata):
        """
        Execute the config file discard action.
        """
        try:
            source = paths_map[idx]
        except KeyError:
            # idiot
            return

        data = scandata.get(source)
        if data is None:
            return

        source_path = root + source
        destination_path = root + data['destination']

        entropy_client.output(
            "%s: %s" % (
                darkred(_("Source file")),
                teal(source_path),)
        )
        entropy_client.output(
            "%s: %s" % (
                darkred(_("Destination file")),
                purple(destination_path),)
        )
        if cmd == -7:
            rc = entropy_client.ask_question(
                _("Discard ?"))
            if rc == _("No"):
                return

        entropy_client.output(
            "%s: %s" % (
                darkred(_("Discarding")),
                teal(source_path),)
        )

        removed = scandata.remove(source)
        del paths_map[idx]
        if not removed:
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("Cannot remove")),
                    brown(source_path),),
                level="warning")

        entropy_client.output("--")

    def _edit_file(self, idx, entropy_client, root, source, dest,
                   paths_map, scandata):
        """
        Edit the given source file.
        """
        source_path = root + source
        dest_path = root + dest

        entropy_client.output(
            "%s: %s" % (
                darkred(_("Editing file")),
                darkgreen(source_path),))

        entropy_client.edit_file(source_path)

        entropy_client.output(
            "%s: %s, %s" % (
                darkred(_("Edited file")),
                darkgreen(source_path),
                darkred(_("showing difference")))
            )

        diff = self._showdiff(
            entropy_client, dest_path, source_path)
        if not diff:
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("Automerging")),
                    teal(source_path),)
                )
            scandata.merge(source)
            del paths_map[idx]
            return True, False

        return False, True

    def _interactive_merge_diff(self, source, destination):
        tmp_fd, tmp_path = None, None
        try:
            tmp_fd, tmp_path = const_mkstemp(
                suffix="equo.conf.intmerge")
            args = ("/usr/bin/sdiff", "-o", tmp_path,
                    source, destination)
            rc = subprocess.call(args)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
            rc = 2
            os.remove(tmp_path)
        finally:
            if tmp_fd is not None:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
        return tmp_path, rc

    def _interactive_merge(self, idx, entropy_client,
                           root, source, dest,
                           paths_map, scandata):
        """
        Interactively merge config file.
        """
        source_path = root + source
        dest_path = root + dest

        entropy_client.output(
            "%s: %s" % (
                darkred(_("Interactive merge")),
                darkgreen(source_path),)
            )

        merge_outcome_path, exit_status = self._interactive_merge_diff(
            source_path, dest_path)
        if exit_status in (2, 130):
            # quit
            return False, True

        try:
            entropy.tools.rename_keep_permissions(
                merge_outcome_path, source_path)
        except OSError as err:
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("OSError during interactive merge")),
                    repr(err),),
                level="error")
            return False, True
        except IOError as err:
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("IOError during interactive merge")),
                    repr(err),),
                level="error")
            return False, True

        merged = scandata.merge(source)
        del paths_map[idx]
        if not merged:
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("Unable to merge file")),
                    darkgreen(source_path),),
                level="error")
        return True, False

    def _handle_command(self, idx, entropy_client,
                        root, paths_map, scandata):
        """
        Execute > 0 commands.
        """
        try:
            source = paths_map[idx]
        except KeyError:
            return True

        source_path = root + source
        if not scandata.exists(source):
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("Discarding")),
                    teal(source_path),)
                )
            scandata.remove(source)
            del paths_map[idx]
            return True

        dest = scandata[source]['destination']
        dest_path = root + dest
        if not scandata.exists(dest):
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("Automerging")),
                    teal(source_path),)
                )
            scandata.merge(source)
            del paths_map[idx]
            return True

        diff = self._showdiff(entropy_client, dest_path, source_path)
        if not diff:
            entropy_client.output(
                "%s: %s" % (
                    darkred(_("Automerging")),
                    teal(source_path),)
                )
            scandata.merge(source)
            del paths_map[idx]
            return True

        mytxt = "%s: %s" % (
            darkred(_("Selected file")),
            darkgreen(source_path),
        )
        entropy_client.output(mytxt)

        comeback = False
        while True:
            action = self._selaction(entropy_client)
            try:
                action = int(action)
            except (ValueError, TypeError):
                entropy_client.output(
                    _("Type a number"), level="error")
                continue

            # actions handling
            if action == -1:
                comeback = True
                break

            elif action == 1:
                entropy_client.output(
                    _("Replacing %s with %s") % (
                        darkgreen(dest_path),
                        darkred(source_path),))

                merged = scandata.merge(source)
                if not merged:
                    entropy_client.output(
                        _("Cannot merge %s") % (
                            darkred(source_path),))
                del paths_map[idx]
                comeback = True
                break

            elif action == 2:
                entropy_client.output(
                    _("Deleting %s") % (
                        darkgreen(source_path),))

                removed = scandata.remove(source)
                if not removed:
                    entropy_client.output(
                        _("Cannot remove %s") % (
                            darkred(source_path),),
                        level="warning")
                del paths_map[idx]
                comeback = True
                break

            elif action == 3:
                comeback, _continue = self._edit_file(
                    idx, entropy_client, root, source, dest,
                    paths_map, scandata)
                if _continue:
                    continue
                break

            elif action == 4:
                comeback, _continue = self._interactive_merge(
                    idx, entropy_client, root, source, dest,
                    paths_map, scandata)
                if _continue:
                    continue
                break

            elif action == 5:
                # show diff again
                diff = self._showdiff(
                    entropy_client, dest_path, source_path)
                continue

        if comeback:
            return True
        return False


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloConf,
        SoloConf.NAME,
        _("manage package file updates"))
    )
