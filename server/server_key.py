# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server GPG Keys text interface}.

"""
from entropy.output import blue, purple, darkgreen, bold, brown, teal, darkred
from entropy.const import const_convert_to_rawstring, etpConst
from entropy.server.interfaces import Server
from entropy.security import Repository
from entropy.i18n import _
from entropy.tools import convert_unix_time_to_human_time

GPG_MSG_SHOWN = False

def get_gpg(entropy_srv):
    obj = Repository()
    global GPG_MSG_SHOWN
    if not GPG_MSG_SHOWN:
        entropy_srv.output("%s: %s" % (
            blue(_("GPG interface loaded, home directory")),
            brown(Repository.GPG_HOME),)
        )
        GPG_MSG_SHOWN = True
    return obj

def key(myopts):

    if not myopts:
        return -10
    cmd = myopts.pop(0)

    rc = -10
    entropy_srv = Server()
    sys_settings_plugin_id = \
        etpConst['system_settings_plugins_ids']['server_plugin']
    sys_set = entropy_srv.Settings()[sys_settings_plugin_id]['server']
    avail_repos = sys_set['repositories']

    def validate_repos(repos, entropy_srv):
        for repo in repos:
            if repo not in avail_repos:
                entropy_srv.output("'%s' %s" % (
                    blue(repo), _("repository not available"),),
                    level = "error")
                return 1
        return 0

    try:

        repos = myopts
        if cmd in ("create", "delete", "sign", "import", "export") and not \
            repos:
            return rc
        elif cmd in ("create", "delete", "sign",):
            v_rc = validate_repos(repos, entropy_srv)
            if v_rc != 0:
                return v_rc

        try:
            repo_sec = get_gpg(entropy_srv)
        except Repository.GPGError as err:
            entropy_srv.output("%s: %s" % (
                _("GnuPG not available"), err,),
                    level = "error")
            return 1

        if cmd == "create" and repos:
            for repo in repos:
                rc = _create_keys(entropy_srv, repo)
                if rc != 0:
                    break

        elif cmd == "delete" and repos:
            for repo in repos:
                rc = _delete_keys(entropy_srv, repo)
                if rc != 0:
                    break

        elif cmd == "status":
            if not repos:
                repo_sec = get_gpg(entropy_srv)
                repos = sorted(repo_sec.get_keys(private = True))
            for repo in repos:
                rc = _show_status(entropy_srv, repo)
                if rc != 0:
                    break

        elif cmd == "sign" and repos:
            for repo in repos:
                rc = _sign_packages(entropy_srv, repo)
                if rc != 0:
                    break

        elif cmd == "import" and len(repos) == 3:
            rc = _import_key(entropy_srv, repos[0], repos[1], repos[2])

        elif cmd == "export-public" and len(repos) == 2:
            rc = _export_key(entropy_srv, True, repos[0], repos[1])

        elif cmd == "export-private" and len(repos) == 2:
            rc = _export_key(entropy_srv, False, repos[0], repos[1])

    finally:
        if entropy_srv is not None:
            entropy_srv.shutdown()

    del entropy_srv
    return rc


def _import_key(entropy_srv, repo, privkey_path, pubkey_path):

    entropy_srv.output("%s: %s" % (
        blue(_("Importing keypair for repository")), purple(repo),))

    repo_sec = get_gpg(entropy_srv)
    if repo_sec.is_keypair_available(repo):
        entropy_srv.output("%s: %s" % (
                blue(_("Another keypair already exists for repository")),
                purple(repo),
            ),
            level = "error"
        )
        return 1

    # install private key
    finger_print = repo_sec.install_key(repo, privkey_path)
    repo_sec.install_key(repo, pubkey_path, ignore_nothing_imported = True)

    entropy_srv.output("%s: %s" % (
            darkgreen(_("Imported GPG key with fingerprint")),
            bold(finger_print),
        ),
        level = "info"
    )
    entropy_srv.output("%s: %s" % (
            darkgreen(_("Now you should sign all the packages in it")),
            blue(repo),
        ),
        level = "warning"
    )

    return 0

def _export_key(entropy_srv, is_pubkey, repo, store_path):

    repo_sec = get_gpg(entropy_srv)

    key_msg = _("Exporting private key for repository")
    func_check = repo_sec.is_privkey_available
    if is_pubkey:
        func_check = repo_sec.is_pubkey_available
        key_msg = _("Exporting public key for repository")

    try:
        if not func_check(repo):
            entropy_srv.output("%s: %s" % (
                    blue(_("No keypair available for repository")),
                    purple(repo),
                ),
                level = "error"
            )
            return 1
    except repo_sec.KeyExpired:
        entropy_srv.output("%s: %s" % (
                darkred(_("Keypair is EXPIRED for repository")),
                purple(repo),
            ),
            level = "error"
        )
        return 1

    entropy_srv.output("%s: %s" % (blue(key_msg), purple(repo),))
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
        entropy_srv.output("%s: %s [%s]" % (
                darkgreen(_("Unable to export GPG key for repository")),
                bold(repo),
                err,
            ),
            level = "error"
        )
        return 1

    entropy_srv.output("%s: %s [%s]" % (
            darkgreen(_("Exported GPG key for repository")),
            bold(repo),
            brown(store_path),
        ),
        level = "info"
    )

    return 0

def _create_keys(entropy_srv, repo):

    entropy_srv.output("%s: %s" % (
        blue(_("Creating keys for repository")), purple(repo),))

    repo_sec = get_gpg(entropy_srv)
    if repo_sec.is_keypair_available(repo):
        entropy_srv.output("%s: %s" % (
                blue(_("Another key already exists for repository")),
                purple(repo),
            ),
            level = "warning"
        )
        answer = entropy_srv.ask_question(_("Would you like to continue?"))
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
        ('expiration', purple(_("Insert expiration days (0=no expiration)")),
            mycb_int, False),
        ('pass', purple(_("Insert passphrase (empty=no passphrase)")),
            mycb_ok, False),
    ]
    data = entropy_srv.input_box(
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
    entropy_srv.output("%s: %s" % (
            darkgreen(_("Produced GPG key with fingerprint")),
            bold(key_fp),
        ),
        level = "info"
    )
    entropy_srv.output("%s: %s" % (
            darkgreen(_("Now you should sign all the packages in it")),
            blue(repo),
        ),
        level = "warning"
    )
    entropy_srv.output(
        darkgreen(_("Make friggin' sure to generate a revoke key and store it in a very safe place.")),
        level = "warning"
    )
    entropy_srv.output(
        "# gpg --homedir '%s' --armor --output revoke.asc --gen-revoke '%s'" % (
            Repository.GPG_HOME, key_fp),
        level = "info"
    )
    entropy_srv.output("%s" % (
            darkgreen(_("You may also want to send your keys to a key server")),
        ),
        level = "info"
    )

    # remove signatures from repository database
    dbconn = entropy_srv.open_server_repository(repo = repo, read_only = False)
    dbconn.dropGpgSignatures()

    return 0

def _delete_keys(entropy_srv, repo):
    entropy_srv.output("%s: %s" % (
        blue(_("Deleting keys for repository")), purple(repo),))

    repo_sec = get_gpg(entropy_srv)
    if not repo_sec.is_keypair_available(repo):
        entropy_srv.output("%s: %s" % (
                blue(_("No keys available for given repository")),
                purple(repo),
            ),
            level = "warning"
        )
        return 0

    answer = entropy_srv.ask_question(_("Are you really sure?"))
    if answer == _("No"):
        return 1

    try:
        key_meta = repo_sec.get_key_metadata(repo)
    except KeyError:
        entropy_srv.output("%s: %s" % (
                darkgreen(_("Keys metadata not available for")),
                bold(repo),
            ),
            level = "error"
        )
        return 1

    # remove signatures from repository database
    dbconn = entropy_srv.open_server_repository(repo = repo, read_only = False)
    dbconn.dropGpgSignatures()

    repo_sec.delete_keypair(repo)
    entropy_srv.output("%s: %s" % (
            darkgreen(_("Deleted GPG key with fingerprint")),
            bold(key_meta['fingerprint']),
        ),
        level = "info"
    )
    return 0

def _show_status(entropy_srv, repo):
    repo_sec = get_gpg(entropy_srv)

    try:
        key_meta = repo_sec.get_key_metadata(repo)
    except KeyError:
        entropy_srv.output("%s: %s" % (
                darkgreen(_("Keys metadata not available for")),
                bold(repo),
            ),
            level = "error"
        )
        return 1

    entropy_srv.output("%s: %s" % (
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
        entropy_srv.output("%s: %s" % (
            teal(key_desc), out_func(key_meta[key_id]),))

    return 0

def _sign_packages(entropy_srv, repo):

    errors, fine, failed = entropy_srv.sign_local_packages(repo = repo,
        ask = True)
    if errors:
        return 2

    return 0
