# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Command Line Client}.

"""
import os
import sys
import argparse

from entropy.i18n import _
from entropy.output import darkgreen, darkred, brown, blue, red, \
    darkblue, bold, purple, teal

import entropy.tools

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.install import SoloInstall
from solo.utils import print_table


class SoloSecurity(SoloInstall):
    """
    Main Solo Security command.
    """

    NAME = "security"
    ALIASES = ["sec"]
    ALLOW_UNPRIVILEGED = False

    INTRODUCTION = """\
System security tools.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloInstall.__init__(self, args)
        self._nsargs = None
        self._commands = {}

    def man(self):
        """
        Overridden from SoloCommand.
        """
        return self._man()

    def _get_parser(self):
        """
        Overridden from SoloCommand.
        """
        _commands = {}

        descriptor = SoloCommandDescriptor.obtain_descriptor(
            SoloSecurity.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloSecurity.NAME))

        self._setup_verbose_quiet_parser(parser)

        subparsers = parser.add_subparsers(
            title="action", description=_("system security tools"),
            help=_("available commands"))

        oscheck_parser = subparsers.add_parser(
            "oscheck",
            help=_("verify installed files using stored checksums"))
        self._setup_verbose_quiet_parser(oscheck_parser)
        oscheck_parser.add_argument(
            "--mtime", action="store_true", default=False,
            help=_("consider mtime instead of SHA256 "
                   "(false positives ahead)"))
        oscheck_parser.add_argument(
            "--assimilate", action="store_true", default=False,
            help=_("update hashes and mtime (useful after "
                   "editing config files)"))
        oscheck_parser.add_argument(
            "--reinstall", action="store_true", default=False,
            help=_("reinstall faulty packages"))

        mg_group = oscheck_parser.add_mutually_exclusive_group()
        mg_group.add_argument(
            "--ask", "-a", action="store_true", default=False,
            help=_("ask before making any changes"))
        mg_group.add_argument(
            "--pretend", "-p", action="store_true", default=False,
            help=_("show what would be done"))
        oscheck_parser.add_argument(
            "--fetch", action="store_true", default=False,
            help=_("just download packages"))

        oscheck_parser.set_defaults(func=self._oscheck)
        _commands["oscheck"] = {
            "--mtime": {},
            "--assimilate": {},
            "--reinstall": {},
            "--pretend": {},
            "-p": {},
            "--ask": {},
            "-a": {},
            "--fetch": {},
        }

        update_parser = subparsers.add_parser(
            "update",
            help=_("download the latest Security Advisories"))
        self._setup_verbose_quiet_parser(update_parser)
        update_parser.add_argument(
            "--force", action="store_true", default=False,
            help=_("force download"))

        update_parser.set_defaults(func=self._update)
        _commands["update"] = {
            "--force": {},
        }

        list_parser = subparsers.add_parser(
            "list",
            help=_("list all the available Security Advisories"))
        self._setup_verbose_quiet_parser(list_parser)

        mg_group = list_parser.add_mutually_exclusive_group()
        mg_group.add_argument(
            "--affected", action="store_true", default=False,
            help=_("list only affected"))
        mg_group.add_argument(
            "--unaffected", action="store_true", default=False,
            help=_("list only unaffected"))
        list_parser.set_defaults(func=self._list)
        _commands["list"] = {
            "--affected": {},
            "--unaffected": {},
        }

        info_parser = subparsers.add_parser(
            "info",
            help=_("show information about provided "
                   "advisories identifiers"))
        self._setup_verbose_quiet_parser(info_parser)
        info_parser.add_argument(
            "ids", nargs='+',
            metavar="<id>", help=_("advisory indentifier"))
        info_parser.set_defaults(func=self._info)
        _commands["info"] = {}


        install_parser = subparsers.add_parser(
            "install",
            help=_("automatically install all the "
                   "available security updates"))
        self._setup_verbose_quiet_parser(install_parser)

        mg_group = install_parser.add_mutually_exclusive_group()
        mg_group.add_argument(
            "--ask", "-a", action="store_true", default=False,
            help=_("ask before making any changes"))
        mg_group.add_argument(
            "--pretend", "-p", action="store_true", default=False,
            help=_("show what would be done"))
        install_parser.add_argument(
            "--fetch", action="store_true", default=False,
            help=_("just download packages"))

        install_parser.set_defaults(func=self._install)
        _commands["install"] = {
            "--ask": {},
            "-a": {},
            "--fetch": {},
            "--pretend": {},
            "-p": {},
        }

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
        self._get_parser() # this will generate self._commands
        outcome = ["--quiet", "-q", "--verbose", "-v"]
        return self._hierarchical_bashcomp(
            last_arg, outcome, self._commands)

    def _print_advisory_information(self, entropy_client,
                                    advisory_data, key):
        """
        Print Security Advisory.
        """
        toc = []

        # print advisory code
        toc.append(
            blue(" @@ ") + \
                red("%s " % (_("Advisory Identifier"),)) + bold(key) + \
                red(" | ")+blue(advisory_data['url']))

        # title
        toc.append((darkgreen("    %s:" % (_("Title"),)),
            darkred(advisory_data['title'])))

        # description
        description = advisory_data['description'].split("\n")
        desc_text = darkgreen("    %s:" % (_("Description"),) )
        for x in description:
            toc.append((desc_text, x.strip()))
            desc_text = " "

        for item in advisory_data['description_items']:
            desc_text = " %s " % (darkred("(*)"),)
            count = 8
            mystr = []
            for word in item.split():
                count -= 1
                mystr.append(word)
                if count < 1:
                    toc.append((" ", desc_text+' '.join(mystr)))
                    desc_text = "   "
                    mystr = []
                    count = 8
            if count < 8:
                toc.append((" ", desc_text+' '.join(mystr)))

        # background
        if advisory_data['background']:
            background = advisory_data['background'].split("\n")
            bg_text = darkgreen("    %s:" % (_("Background"),))
            for x in background:
                toc.append((bg_text, purple(x.strip())))
                bg_text = " "

        # access
        if advisory_data['access']:
            toc.append((darkgreen("    %s:" % (_("Exploitable"),)),
                bold(advisory_data['access'])))

        # impact
        if advisory_data['impact']:
            impact = advisory_data['impact'].split("\n")
            imp_text = darkgreen("    %s:" % (_("Impact"),))
            for x in impact:
                toc.append((imp_text, brown(x.strip())))
                imp_text = " "

        # impact type
        if advisory_data['impacttype']:
            toc.append((darkgreen("    %s:" % (_("Impact type"),)),
                bold(advisory_data['impacttype'])))

        # revised
        if advisory_data['revised']:
            toc.append((darkgreen("    %s:" % (_("Revised"),)),
                brown(advisory_data['revised'])))

        # announced
        if advisory_data['announced']:
            toc.append((darkgreen("    %s:" % (_("Announced"),)),
                brown(advisory_data['announced'])))

        # synopsis
        synopsis = advisory_data['synopsis'].split("\n")
        syn_text = darkgreen("    %s:" % (_("Synopsis"),))
        for x in synopsis:
            toc.append((syn_text, x.strip()))
            syn_text = " "

        # references
        if advisory_data['references']:
            toc.append(darkgreen("    %s:" % (_("References"),)))
            for reference in advisory_data['references']:
                toc.append((" ", darkblue(reference)))

        # gentoo bugs
        if advisory_data['bugs']:
            toc.append(darkgreen("    %s:" % (_("Upstream bugs"),)))
            for bug in advisory_data['bugs']:
                toc.append((" ", darkblue(bug)))

        # affected
        if advisory_data['affected']:
            toc.append(darkgreen("    %s:" % (_("Affected"),)))
            for key in advisory_data['affected']:
                toc.append((" ", darkred(key)))
                affected_data = advisory_data['affected'][key][0]
                vul_vers = affected_data['vul_vers']
                unaff_vers = affected_data['unaff_vers']
                if vul_vers:
                    toc.append((" ", brown("%s: " % (
                        _("vulnerable versions"),))+", ".join(vul_vers)))
                if unaff_vers:
                    toc.append((" ", brown("%s: " % (
                        _("unaffected versions"),))+", ".join(unaff_vers)))

        # workaround
        workaround = advisory_data['workaround'].split("\n")
        if advisory_data['workaround']:
            work_text = darkgreen("    %s:" % (_("Workaround"),))
            for x in workaround:
                toc.append((work_text, darkred(x.strip())))
                work_text = " "

        # resolution
        if advisory_data['resolution']:
            res_text = darkgreen("    %s:" % (_("Resolution"),))
            resolutions = advisory_data['resolution']
            for resolution in resolutions:
                for x in resolution.split("\n"):
                    toc.append((res_text, x.strip()))
                    res_text = " "

        print_table(entropy_client, toc, cell_spacing=3)

    def _oscheck_scan_unlocked(self, entropy_client, inst_repo,
                               quiet, verbose, assimilate):
        """
        Execute the filesystem scan.
        """
        pkg_ids = inst_repo.listAllPackageIds()
        total = len(pkg_ids)
        faulty_pkg_ids = []

        for count, pkg_id in enumerate(pkg_ids, 1):

            pkg_atom = inst_repo.retrieveAtom(pkg_id)
            sts_txt = "%s%s/%s%s %s" % (
                blue("["),
                darkgreen(str(count)),
                purple(str(total)),
                blue("]"),
                brown(pkg_atom))

            if not quiet:
                entropy_client.output(
                    sts_txt,
                    header=blue(" @@ "), back=True)

            cont_s = inst_repo.retrieveContentSafety(pkg_id)
            if not cont_s:
                if not quiet and verbose:
                    entropy_client.output(
                        "%s: %s" % (
                            brown(pkg_atom),
                            _("no checksum information"),),
                        header=darkred(" @@ "))
                # if pkg provides content!
                continue

            paths_tainted = []
            paths_unavailable = []
            for path, safety_data in cont_s.items():
                tainted = False
                mtime = None
                sha256 = None

                if not os.path.lexists(path):
                    # file does not exist
                    # NOTE: current behaviour is to ignore
                    # file not available
                    # this might change in future.
                    paths_unavailable.append(path)
                    continue

                elif not mtime:
                    # verify sha256
                    sha256 = entropy.tools.sha256(path)
                    tainted = sha256 != safety_data['sha256']
                    if tainted:
                        cont_s[path]['sha256'] = sha256
                else:
                    # verify mtime
                    mtime = os.path.getmtime(path)
                    tainted = mtime != safety_data['mtime']
                    if tainted:
                        cont_s[path]['mtime'] = mtime

                if assimilate:
                    if mtime is None:
                        cont_s[path]['mtime'] = os.path.getmtime(path)
                    elif sha256 is None:
                        cont_s[path]['sha256'] = entropy.tools.sha256(path)

                if tainted:
                    paths_tainted.append(path)

            if paths_tainted:
                faulty_pkg_ids.append(pkg_id)
                paths_tainted.sort()
                if not quiet:
                    entropy_client.output(
                        "%s: %s" % (
                            teal(pkg_atom),
                            _("found altered files"),),
                        header=darkred(" @@ "))

                for path in paths_tainted:
                    if quiet:
                        entropy_client.output(
                            path,
                            level="generic")
                    else:
                        txt = " %s" % (purple(path),)
                        entropy_client.output(
                            purple(path),
                            header=" ")

                if assimilate:
                    if not quiet:
                        entropy_client.output(
                            "%s, %s" % (
                                sts_txt,
                                teal(_("assimilated new "
                                       "hashes and mtime"))),
                            header=blue(" @@ "))
                    inst_repo.setContentSafety(pkg_id, cont_s)

            if paths_unavailable:
                paths_unavailable.sort()
                if not quiet and verbose:
                    for path in paths_unavailable:
                        txt = " %s [%s]" % (
                            teal(path),
                            purple(_("unavailable"))
                        )
                        entropy_client.output(txt)

        return faulty_pkg_ids

    def _oscheck(self, entropy_client):
        """
        Solo Security Oscheck command.
        """
        mtime = self._nsargs.mtime
        assimilate = self._nsargs.assimilate
        reinstall = self._nsargs.reinstall
        verbose = self._nsargs.verbose
        quiet = self._nsargs.quiet
        ask = self._nsargs.ask
        pretend = self._nsargs.pretend
        fetch = self._nsargs.fetch

        if not quiet:
            entropy_client.output(
                "%s..." % (
                    blue(_("Checking system files")),),
                header=darkred(" @@ "))

        inst_repo = entropy_client.installed_repository()
        with inst_repo.shared():
            faulty_pkg_ids = self._oscheck_scan_unlocked(
                entropy_client, inst_repo, quiet, verbose, assimilate)

        if not faulty_pkg_ids:
            if not quiet:
                entropy_client.output(
                    darkgreen(_("No altered files found")),
                    header=darkred(" @@ "))
            return 0

        rc = 0
        if faulty_pkg_ids:
            rc = 10
        valid_matches = set()

        if reinstall and faulty_pkg_ids:
            for pkg_id in faulty_pkg_ids:
                key_slot = inst_repo.retrieveKeySlotAggregated(pkg_id)
                package_id, repository_id = entropy_client.atom_match(
                    key_slot)
                if package_id != -1:
                    valid_matches.add((package_id, repository_id))

            if valid_matches:
                rc, _show_cfgupd = self._install_action(
                    entropy_client, True, True,
                    pretend, ask, False, quiet, False,
                    False, False, fetch, False, False,
                    False, 1, [], package_matches=list(valid_matches))

        if not quiet:
            entropy_client.output(
                purple(_("Altered files have been found")),
                header=darkred(" @@ "))
            if reinstall and (rc == 0) and valid_matches:
                entropy_client.output(
                    purple(_("Packages have been "
                             "reinstalled successfully")),
                    header=darkred(" @@ "))

        return rc

    def _update(self, entropy_client):
        """
        Solo Security Update command.
        """
        sec = entropy_client.Security()
        return sec.update(force=self._nsargs.force)

    def _list(self, entropy_client):
        """
        Solo Security List command.
        """
        affected = self._nsargs.affected
        unaffected = self._nsargs.unaffected
        sec = entropy_client.Security()

        if not (affected or unaffected):
            advisory_ids = sec.list()
        elif affected:
            advisory_ids = sec.vulnerabilities()
        else:
            advisory_ids = sec.fixed_vulnerabilities()

        if not advisory_ids:
            entropy_client.output(
                "%s." % (
                    darkgreen(_("No advisories available or applicable")),
                    ),
                header=brown(" :: "))
            return 0

        for advisory_id in sorted(advisory_ids):

            affected_deps = sec.affected_id(advisory_id)
            if affected and not affected_deps:
                continue
            if unaffected and affected_deps:
                continue

            if affected_deps:
                affection_string = darkred("A")
            else:
                affection_string = darkgreen("N")

            advisory = sec.advisory(advisory_id)
            if advisory is None:
                continue

            affected_data = advisory['affected']
            if not affected_data:
                continue

            for a_key in list(affected_data.keys()):
                k_data = advisory['affected'][a_key]
                vulnerables = ', '.join(k_data[0]['vul_vers'])
                description = "[Id:%s:%s][%s] %s: %s" % (
                    darkgreen(advisory_id),
                    affection_string,
                    brown(vulnerables),
                    darkred(a_key),
                    blue(advisory['title']))
                entropy_client.output(description)

        return 0

    def _info(self, entropy_client):
        """
        Solo Security Info command.
        """
        advisory_ids = self._nsargs.ids

        sec = entropy_client.Security()
        exit_st = 1

        for advisory_id in advisory_ids:

            advisory = sec.advisory(advisory_id)
            if advisory is None:
                entropy_client.output(
                    "%s: %s." % (
                        darkred(_("Advisory does not exist")),
                        blue(advisory_id),),
                    header=brown(" :: "))
                continue

            self._print_advisory_information(
                entropy_client, advisory, key=advisory_id)
            exit_st = 0

        return exit_st

    def _install(self, entropy_client):
        """
        Solo Security Install command.
        """
        quiet = self._nsargs.quiet
        pretend = self._nsargs.pretend
        ask = self._nsargs.ask
        fetch = self._nsargs.fetch

        sec = entropy_client.Security()

        entropy_client.output(
            "%s..."  % (
                blue(_("Calculating security updates")),),
            header=darkred(" @@ "))

        inst_repo = entropy_client.installed_repository()
        with inst_repo.shared():

            affected_deps = set()
            for advisory_id in sec.list():
                affected_deps.update(sec.affected_id(advisory_id))

            valid_matches = set()
            for atom in affected_deps:
                inst_package_id, pkg_rc = inst_repo.atomMatch(atom)
                if pkg_rc != 0:
                    continue

                key_slot = inst_repo.retrieveKeySlotAggregated(
                    inst_package_id)
                package_id, repository_id = entropy_client.atom_match(key_slot)
                if package_id != -1:
                    valid_matches.add((package_id, repository_id))

        if not valid_matches:
            entropy_client.output(
                "%s." % (
                    blue(_("All the available updates "
                           "have been already installed")),),
                header=darkred(" @@ "))
            return 0

        exit_st, _show_cfgupd = self._install_action(
            entropy_client, True, True,
            pretend, ask, False, quiet, False,
            False, False, fetch, False, False,
            False, 1, [], package_matches=list(valid_matches))
        return exit_st


SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloSecurity,
        SoloSecurity.NAME,
        _("system security tools"))
    )
