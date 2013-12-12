# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Infrastructure Toolkit}.

"""
import sys
import argparse

from entropy.output import blue, purple, darkgreen, bold, brown, teal, \
    darkred
from entropy.const import const_convert_to_rawstring
from entropy.i18n import _
from entropy.security import Repository
from entropy.tools import convert_unix_time_to_human_time

from eit.commands.descriptor import EitCommandDescriptor
from eit.commands.command import EitCommand


class EitKey(EitCommand):
    """
    Main Eit key command.
    """

    NAME = "key"
    ALIASES = []

    def __init__(self, args):
        EitCommand.__init__(self, args)
        self._nsargs = None
        self._gpg_msg_shown = False

    def _get_parser(self):
        """ Overridden from EitCommand """
        descriptor = EitCommandDescriptor.obtain_descriptor(
            EitKey.NAME)
        parser = argparse.ArgumentParser(
            description=descriptor.get_description(),
            formatter_class=argparse.RawDescriptionHelpFormatter,
            prog="%s %s" % (sys.argv[0], EitKey.NAME))

        subparsers = parser.add_subparsers(
            title="action", description=_("execute action"),
            help=_("available actions"))

        create_parser = subparsers.add_parser("create",
            help=_("create keypair for repository and packages"))
        create_parser.add_argument("repo", metavar="<repo>",
                                   help=_("repository"))
        create_parser.set_defaults(func=self._create)

        delete_parser = subparsers.add_parser("delete",
            help=_("delete keypair (and signatures) from repository"))
        delete_parser.add_argument("repo", metavar="<repo>",
                                   help=_("repository"))
        delete_parser.set_defaults(func=self._delete)

        status_parser = subparsers.add_parser("status",
            help=_("show keypair status for repository"))
        status_parser.add_argument("repo", metavar="<repo>",
                                   help=_("repository"))
        status_parser.set_defaults(func=self._status)

        sign_parser = subparsers.add_parser("sign",
            help=_("sign packages in repository using current keypair"))
        sign_parser.add_argument("repo", metavar="<repo>",
                                 help=_("repository"))
        sign_parser.set_defaults(func=self._sign)

        import_parser = subparsers.add_parser("import",
            help=_("import keypair, bind to given repository"))
        import_parser.add_argument("repo", metavar="<repo>",
                                   help=_("repository"))
        import_parser.add_argument("privkey",
            metavar="<private key>", type=file,
            help=_("private key path"))
        import_parser.add_argument("pubkey",
            metavar="<pub key path>", type=file,
            help=_("public key path"))
        import_parser.set_defaults(func=self._import)

        export_pub_parser = subparsers.add_parser("export-public",
            help=_("export the repository public key to file"))
        export_pub_parser.add_argument("repo", metavar="<repo>",
                                       help=_("repository"))
        export_pub_parser.add_argument("key",
            metavar="<public key>", type=argparse.FileType('w'),
            help=_("public key path"))
        export_pub_parser.set_defaults(func=self._export_pub)

        export_priv_parser = subparsers.add_parser("export-private",
            help=_("export the repository private key to file"))
        export_priv_parser.add_argument("repo", metavar="<repo>",
                                        help=_("repository"))
        export_priv_parser.add_argument("key",
            metavar="<private key>", type=argparse.FileType('w'),
            help=_("private key path"))
        export_priv_parser.set_defaults(func=self._export_priv)

        return parser

    INTRODUCTION = """\
Toolset for handling repository GPG keys.
Entropy Server offers *built-in* support for digitally signing
package and repository files through *gnupg*.
"""

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
        return self._call_exclusive, [nsargs.func, nsargs.repo]

    def __get_gpg(self, entropy_server):
        obj = Repository()
        if not self._gpg_msg_shown:
            self._gpg_msg_shown = True
            entropy_server.output("%s: %s" % (
                blue(_("GPG interface loaded, home directory")),
                brown(Repository.GPG_HOME),)
            )
        return obj

    def _get_gpg(self, entropy_server):
        try:
            repo_sec = self.__get_gpg(entropy_server)
        except Repository.GPGError as err:
            entropy_server.output("%s: %s" % (
                _("GnuPG not available"), err,),
                    level="error")
            return None
        return repo_sec

    def _create(self, entropy_server):
        """
        Actual Eit key create code.
        """
        repo_sec = self._get_gpg(entropy_server)
        if repo_sec is None:
            return 1
        repo = entropy_server.repository()

        entropy_server.output("%s: %s" % (
            blue(_("Creating keys for repository")), purple(repo),))

        if repo_sec.is_keypair_available(repo):
            entropy_server.output("%s: %s" % (
                    blue(_("Another key already exists for repository")),
                    purple(repo),
                ),
                level = "warning"
            )
            answer = entropy_server.ask_question(
                _("Would you like to continue?"))
            if answer == _("No"):
                return 1

        def mycb(sstr):
            return sstr

        def mycb_int(sstr):
            try:
                int(sstr)
            except ValueError:
                return False
            return True

        def mycb_ok(sstr):
            return True

        input_data = [
            ('name_email', purple(_("Insert e-mail")), mycb, False),
            ('expiration',
             purple(_("Insert expiration days (0=no expiration)")),
                mycb_int, False),
            ('pass', purple(_("Insert passphrase (empty=no passphrase)")),
                mycb_ok, False),
        ]
        data = entropy_server.input_box(
            blue("%s") % (_("Repository GPG keypair creation"),),
            input_data, cancel_button = True)

        if not data:
            return 1
        elif not isinstance(data, dict):
            return 1

        if not data['pass']:
            data['pass'] = None
        else:
            data['pass'] = const_convert_to_rawstring(data['pass'])
        key_fp = repo_sec.create_keypair(repo, passphrase = data['pass'],
            name_email = data['name_email'],
            expiration_days = int(data['expiration']))
        entropy_server.output("%s: %s" % (
                darkgreen(_("Produced GPG key with fingerprint")),
                bold(key_fp),
            ),
            level = "info"
        )
        entropy_server.output("%s: %s" % (
                darkgreen(_("Now you should sign all the packages in it")),
                blue(repo),
            ),
            level = "warning"
        )
        entropy_server.output(
            darkgreen(
                _("Generate a revoke key and store it in a safe place")),
            level = "warning"
        )
        entropy_server.output(
            "# gpg --homedir '%s' --armor --output revoke.asc --gen-revoke '%s'" % (
                Repository.GPG_HOME, key_fp),
            level = "info"
        )
        entropy_server.output("%s" % (
                darkgreen(
                    _("You may want to send your keys to a key server")),
            ),
            level = "info"
        )

        # remove signatures from repository database
        dbconn = entropy_server.open_server_repository(
            repo, read_only = False)
        dbconn.dropGpgSignatures()
        return 0

    def _delete(self, entropy_server):
        """
        Actual Eit key delete code.
        """
        repo_sec = self._get_gpg(entropy_server)
        if repo_sec is None:
            return 1
        repo = entropy_server.repository()

        entropy_server.output("%s: %s" % (
            blue(_("Deleting keys for repository")), purple(repo),))

        if not repo_sec.is_keypair_available(repo):
            entropy_server.output("%s: %s" % (
                    blue(_("No keys available for given repository")),
                    purple(repo),
                ),
                level = "warning"
            )
            return 0

        answer = entropy_server.ask_question(_("Are you really sure?"))
        if answer == _("No"):
            return 1

        try:
            key_meta = repo_sec.get_key_metadata(repo)
        except KeyError:
            entropy_server.output("%s: %s" % (
                    darkgreen(_("Keys metadata not available for")),
                    bold(repo),
                ),
                level = "error"
            )
            return 1

        # remove signatures from repository database
        dbconn = entropy_server.open_server_repository(
            repo, read_only = False)
        dbconn.dropGpgSignatures()

        repo_sec.delete_keypair(repo)
        entropy_server.output("%s: %s" % (
                darkgreen(_("Deleted GPG key with fingerprint")),
                bold(key_meta['fingerprint']),
            ),
            level = "info"
        )
        return 0

    def _status(self, entropy_server):
        """
        Actual Eit key status code.
        """
        repo_sec = self._get_gpg(entropy_server)
        if repo_sec is None:
            return 1
        repo = entropy_server.repository()

        try:
            key_meta = repo_sec.get_key_metadata(repo)
        except KeyError:
            entropy_server.output("%s: %s" % (
                    darkgreen(_("Keys metadata not available for")),
                    bold(repo),
                ),
                level = "error"
            )
            return 1

        entropy_server.output("%s: %s" % (
                brown(_("GPG information for repository")),
                bold(repo),
            ),
            level = "info"
        )

        def just_print(mystr):
            return purple(mystr)

        def print_list(myl):
            return purple(' '.join(myl))

        def print_date(mydate):
            if not mydate:
                return _("N/A")
            try:
                return convert_unix_time_to_human_time(int(mydate))
            except (ValueError, TypeError,):
                return _("N/A")

        out_data = [
            ('uids', _("Description"), print_list),
            ('keyid', _("Public key identifier"), just_print),
            ('fingerprint', _("Public key fingerprint"), just_print),
            ('length', _("Key size"), just_print),
            ('date', _("Creation date"), print_date),
            ('expires', _("Expires on"), print_date),
        ]
        for key_id, key_desc, out_func in out_data:
            entropy_server.output("%s: %s" % (
                teal(key_desc), out_func(key_meta[key_id]),))

        return 0

    def _sign(self, entropy_server):
        """
        Actual Eit key sign code.
        """
        repo_sec = self._get_gpg(entropy_server)
        if repo_sec is None:
            return 1
        repo = entropy_server.repository()

        errors, fine, failed = entropy_server.sign_local_packages(
            repo, ask = True)
        if errors:
            return 1

        return 0

    def _import(self, entropy_server):
        """
        Actual Eit key import code.
        """
        repo_sec = self._get_gpg(entropy_server)
        if repo_sec is None:
            return 1
        repo = entropy_server.repository()
        privkey_path = self._nsargs.privkey.name
        pubkey_path = self._nsargs.pubkey.name
        # no need to close files here

        entropy_server.output("%s: %s" % (
            blue(_("Importing keypair")),
            purple(repo),))

        if repo_sec.is_keypair_available(repo):
            entropy_server.output(
                "%s: %s" % (
                    blue(_("Another keypair already exists")),
                    purple(repo),
                ),
                level = "error"
            )
            return 1

        # install private key
        finger_print = repo_sec.install_key(repo, privkey_path)
        repo_sec.install_key(repo, pubkey_path,
            ignore_nothing_imported = True)

        entropy_server.output("%s: %s" % (
                darkgreen(_("Imported GPG key with fingerprint")),
                bold(finger_print),
            ),
            level = "info"
        )
        entropy_server.output("%s: %s" % (
                darkgreen(_("Now sign all the packages in it")),
                blue(repo),
            ),
            level = "warning"
        )

        return 0

    def _export_pub(self, entropy_server):
        """
        Actual Eit key export-public code.
        """
        repo_sec = self._get_gpg(entropy_server)
        if repo_sec is None:
            return 1
        # close file to avoid truncation on exit
        key_path = self._nsargs.key.name
        self._nsargs.key.close()

        return self.__export_key(
            entropy_server, repo_sec, True, entropy_server.repository(),
            key_path)

    def _export_priv(self, entropy_server):
        """
        Actual Eit key export-private code.
        """
        repo_sec = self._get_gpg(entropy_server)
        if repo_sec is None:
            return 1
        # close file to avoid truncation on exit
        key_path = self._nsargs.key.name
        self._nsargs.key.close()

        return self.__export_key(
            entropy_server, repo_sec, False, entropy_server.repository(),
            key_path)

    def __export_key(self, entropy_server, repo_sec, is_pubkey, repo,
                     store_path):
        """
        Internal key export logic.
        """
        key_msg = _("Exporting private key for repository")
        func_check = repo_sec.is_privkey_available
        if is_pubkey:
            func_check = repo_sec.is_pubkey_available
            key_msg = _("Exporting public key for repository")

        try:
            if not func_check(repo):
                entropy_server.output("%s: %s" % (
                        blue(_("No keypair available for repository")),
                        purple(repo),
                    ),
                    level = "error"
                )
                return 1
        except repo_sec.KeyExpired:
            entropy_server.output("%s: %s" % (
                    darkred(_("Keypair is EXPIRED for repository")),
                    purple(repo),
                ),
                level = "error"
            )
            return 1

        entropy_server.output("%s: %s" % (blue(key_msg), purple(repo),))
        if is_pubkey:
            key_stream = repo_sec.get_pubkey(repo)
        else:
            key_stream = repo_sec.get_privkey(repo)

        # write to file
        try:
            with open(store_path, "w") as dest_w:
                dest_w.write(key_stream)
                dest_w.flush()
        except IOError as err:
            entropy_server.output("%s: %s [%s]" % (
                    darkgreen(
                        _("Unable to export GPG key for repository")),
                    bold(repo),
                    err,
                ),
                level = "error"
            )
            return 1

        entropy_server.output("%s: %s [%s]" % (
                darkgreen(_("Exported GPG key for repository")),
                bold(repo),
                brown(store_path),
            ),
            level = "info"
        )

        return 0

EitCommandDescriptor.register(
    EitCommandDescriptor(
        EitKey,
        EitKey.NAME,
        _('manage repository GPG keys'))
    )
