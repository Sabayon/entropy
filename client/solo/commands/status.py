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
from entropy.output import darkred, red, brown, purple, teal, blue, \
    darkgreen, bold
from entropy.const import etpConst, const_convert_to_unicode

import entropy.tools

from solo.commands.descriptor import SoloCommandDescriptor
from solo.commands.command import SoloCommand

class SoloStatus(SoloCommand):
    """
    Main Solo Status command.
    """

    NAME = "status"
    ALIASES = ["st", "--info"]
    ALLOW_UNPRIVILEGED = True

    INTRODUCTION = """\
Show Repositories status.
"""
    SEE_ALSO = ""

    def __init__(self, args):
        SoloCommand.__init__(self, args)

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
            SoloStatus.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], SoloStatus.NAME))

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

        return self._call_shared, [self._status]

    def bashcomp(self, last_arg):
        """
        Overridden from SoloCommand.
        """
        return self._bashcomp(sys.stdout, last_arg, [])

    def _status(self, entropy_client):
        """
        Command implementation.
        """
        settings = entropy_client.Settings()
        repo_enum = enumerate(settings['repositories']['order'], 1)
        for repo_idx, repository_id in repo_enum:
            self._repository_status(entropy_client, repo_idx,
                                    repository_id)
        return 0

    def _repository_status(self, entropy_client, repo_idx, repository_id):

        settings = entropy_client.Settings()
        avail_data = settings['repositories']['available']
        repo_data = avail_data[repository_id]

        entropy_client.output(
            "%s %s %s" % (
                brown(const_convert_to_unicode("#")),
                teal(const_convert_to_unicode(repo_idx)),
                purple(repo_data['description']),))

        entropy_client.output(
            "%s: %s" % (
                brown(_("Repository name")),
                darkgreen(repository_id),),
            header="    ")

        repo_class = entropy_client.get_repository(
            repository_id)

        entropy_client.output(
            "%s: %s" % (
                brown(_("Revision")),
                darkgreen(
                    const_convert_to_unicode(
                        repo_class.revision(repository_id)))),
            header="    ")

        repo_class_str = const_convert_to_unicode(
            "%s.%s" % (
                repo_class.__module__,
                repo_class.__name__))
        entropy_client.output(
            "%s: %s" % (
                brown(_("Repository class")),
                darkgreen(repo_class_str)),
            header="    ")

        gpg_pubkey = repo_data.get("gpg_pubkey", _("Not available"))
        entropy_client.output(
            "%s: %s" % (
                brown(_("GPG")),
                darkgreen(gpg_pubkey),),
            header="    ")

        notice_board = repo_data.get("notice_board", _("Not available"))
        entropy_client.output(
            "%s: %s" % (
                brown(_("Notice Board")),
                darkgreen(notice_board),),
            header="    ")

        repository_path = repo_data.get('dbpath', _("Not available"))
        entropy_client.output(
            "%s: %s" % (
                brown(_("Path")),
                darkgreen(repository_path),),
            header="    ")

        entropy_client.output(
            "%s: %s" % (
                brown(_("Repository URL")),
                darkgreen(repo_data['plain_database']),),
            header="    ")

        if repo_data['packages']:
            entropy_client.output(
                "%s:" % (
                    blue(_("Package URLs")),),
                header="    ")
        urlcount = 0
        for packages_url in repo_data['plain_packages']:
            urlcount += 1
            entropy_client.output(
                "%s. %s" % (
                    purple(const_convert_to_unicode(urlcount)),
                    brown(packages_url),),
                header="     ")

SoloCommandDescriptor.register(
    SoloCommandDescriptor(
        SoloStatus,
        SoloStatus.NAME,
        _("show Repositories status"))
    )
