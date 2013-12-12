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
import codecs

from entropy.const import etpConst
from entropy.i18n import _
from entropy.output import darkgreen, teal, brown, purple, blue
from entropy.client.interfaces.db import InstalledPackagesRepository
from entropy.server.interfaces.main import ServerSystemSettingsPlugin

import entropy.tools

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand

class EitRemote(EitCommand):
    """
    Main Eit remote command.
    """

    NAME = "remote"
    ALIASES = []
    ALLOW_UNPRIVILEGED = True

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitRemote.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitRemote.NAME))

        subparsers = parser.add_subparsers(
            title="action", description=_("execute action"),
            help=_("available actions"))

        list_parser = subparsers.add_parser("list",
            help=_("list repositories"))
        list_parser.set_defaults(func=self._list)

        add_parser = subparsers.add_parser("add",
           help=_("add repository"))
        add_parser.add_argument("repository", metavar="<repository>",
                                help=_("repository id"))
        add_parser.add_argument("--desc", metavar="<description>",
                                default=None,
                                help=_("repository description"))
        add_parser.add_argument("uri", metavar="<uri>", nargs="+",
                                help=_("repository uri"))

        add_parser.set_defaults(func=self._add)

        return parser

    INTRODUCTION = """\
Manage (add, remove, list) configured repositories.
"""
    SEE_ALSO = "eit-status(1)"

    def man(self):
        """
        Overridden from EitCommand.
        """
        return self._man()

    def parse(self):
        """ Overridden from EitCommand """
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
        return self._call_exclusive, [nsargs.func, None]

    def _add(self, entropy_server):
        """
        Add a Repository.
        """
        repository_id = self._nsargs.repository
        description = self._nsargs.desc
        uris = self._nsargs.uri

        if not entropy.tools.validate_repository_id(repository_id):
            entropy_server.output(
                purple(_("Invalid repository name")),
                importance=1, level="error")
            return 1

        if repository_id in entropy_server.repositories():
            entropy_server.output(
                purple(_("Repository already available")),
                importance=1, level="error")
            return 1

        if description:
            description = description.strip()
            if not description:
                description = None

        for uri in uris:
            if not entropy.tools.is_valid_uri(uri):
                entropy_server.output(
                    "%s: %s" % (
                        purple(_("Invalid URI")),
                        uri),
                    importance=1, level="error")
                return 1

        server_conf = ServerSystemSettingsPlugin.server_conf_path()
        enc = etpConst['conf_encoding']
        content = ""
        try:
            with codecs.open(server_conf, encoding=enc) as server_f:
                content = server_f.read()
        except IOError as err:
            if err.errno == errno.EPERM:
                entropy_server.output(
                    "%s: %s" % (
                        purple(_("Cannot read configuration file")),
                        server_conf,),
                    importance=1, level="error")
                return 1
            if err.errno != errno.ENOENT:
                raise

        if not content.endswith("\n") and content:
            content += "\n"
        elif not content:
            content += "default-repository = %s\n" % (repository_id,)
        content += "repository = %s|%s|%s\n" % (
            repository_id, description,
            " ".join(uris),)

        if not description:
            description = _("no description")
        entropy_server.output(
            "%s: %s [%s]" % (
                darkgreen(_("Adding repository")),
                teal(repository_id),
                darkgreen(description),
            ))
        for uri in uris:
            entropy_server.output(
                "++ %s" % (
                    brown(uri),
                ))
        entropy_server.output(
            "%s: %s" % (
                darkgreen(_("Configuration file")),
                purple(server_conf),
            ))
        entropy_server.output(
            "%s: '%s %s'" % (
                darkgreen(_("Please initialize the repository using")),
                teal("eit init"),
                brown(repository_id),
            ))

        entropy.tools.atomic_write(
            server_conf, content, enc)

        return 0

    def _list(self, entropy_server):
        """
        List Available Repositories.
        """
        repositories = entropy_server.repositories()
        default_repo = entropy_server.repository()
        for repository_id in repositories:
            repo_class = entropy_server.get_repository(repository_id)
            if repo_class == InstalledPackagesRepository:
                continue

            default_str = ""
            if repository_id == default_repo:
                default_str = " (%s)" % (purple("*"),)
            meta = entropy_server.repository_metadata(repository_id)
            description = meta['description']
            repo_mirrors = meta['repo_mirrors']
            pkg_mirrors = meta['pkg_mirrors']

            entropy_server.output(
                "%s [%s]%s" % (
                    teal(repository_id),
                    darkgreen(description),
                    default_str,
                ))
            for repo_mirror in repo_mirrors:
                entropy_server.output(
                    "  %s: %s" % (
                        blue(_("repository")),
                        brown(repo_mirror),
                    ))
            for pkg_mirror in pkg_mirrors:
                entropy_server.output(
                    "  %s: %s" % (
                        blue(_("packages")),
                        brown(pkg_mirror),
                    ))

        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitRemote,
        EitRemote.NAME,
        _('manage repositories'))
    )
