# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Server GPG Keys text interface}.

"""
from entropy.output import red, blue, purple, darkgreen, bold, brown, teal
from entropy.const import etpConst, const_convert_to_rawstring
from entropy.server.interfaces import Server
from entropy.security import Repository
from entropy.i18n import _
from entropy.tools import convert_unix_time_to_human_time

def key(myopts):

    if not myopts:
        return -10
    cmd = myopts.pop(0)
    repos = myopts

    rc = -10
    Entropy = Server()
    sys_set = Entropy.SystemSettings[Entropy.sys_settings_plugin_id]['server']
    avail_repos = sys_set['repositories']
    for repo in repos:
        if repo not in avail_repos:
            Entropy.updateProgress("'%s' %s" % (
                blue(repo), _("repository not available"),),
                type = "error")
            Entropy.destroy()
            return 1

    if cmd in ("create", "delete", "sign",) and not repos:
        return rc

    try:
        repo_sec = Repository()
    except Repository.GPGError as err:
        Entropy.updateProgress("%s: %s" % (
            _("GnuPG not available"), err,),
                type = "error")
        Entropy.destroy()
        return 1

    try:
        if cmd == "create" and repos:
            for repo in repos:
                rc = _create_keys(Entropy, repo)
                if rc != 0:
                    break

        elif cmd == "delete" and repos:
            for repo in repos:
                rc = _delete_keys(Entropy, repo)
                if rc != 0:
                    break

        elif cmd == "status":
            if not repos:
                repo_sec = Repository()
                repos = sorted(repo_sec.get_keys(private = True))
            for repo in repos:
                rc = _show_status(Entropy, repo)
                if rc != 0:
                    break

        elif cmd == "sign" and repos:
            for repo in repos:
                rc = _sign_packages(Entropy, repo)
                if rc != 0:
                    break

    finally:
        Entropy.destroy()
    del Entropy
    return rc

def _create_keys(entropy_srv, repo):

    entropy_srv.updateProgress("%s: %s" % (
        blue(_("Creating keys for repository")), purple(repo),))

    repo_sec = Repository()
    if repo_sec.is_keypair_available(repo):
        entropy_srv.updateProgress("%s: %s" % (
                blue(_("Another key already exists for repository")),
                purple(repo),
            ),
            type = "warning"
        )
        answer = entropy_srv.askQuestion(_("Would you like to continue?"))
        if answer == _("No"):
            return 1

    def mycb(s):
        return s

    def mycb_int(s):
        try:
            int(s)
        except ValueError:
            return False
        return True

    def mycb_ok(s):
        return True

    input_data = [
        ('name_email', purple(_("Insert e-mail")), mycb, False),
        ('expiration', purple(_("Insert expiration days (0=no expiration)")),
            mycb_int, False),
        ('pass', purple(_("Insert passphrase (empty=no passphrase)")),
            mycb_ok, False),
    ]
    data = entropy_srv.inputBox(
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
    entropy_srv.updateProgress("%s: %s" % (
            darkgreen(_("Produced GPG key with fingerprint")),
            bold(key_fp),
        ),
        type = "info"
    )
    entropy_srv.updateProgress("%s: %s" % (
            darkgreen(_("Now you should sign all the packages in it")),
            blue(repo),
        ),
        type = "warning"
    )

    # remove signatures from repository database
    dbconn = entropy_srv.open_server_repository(repo = repo, read_only = False)
    dbconn.dropGpgSignatures()

    return 0

def _delete_keys(entropy_srv, repo):
    entropy_srv.updateProgress("%s: %s" % (
        blue(_("Deleting keys for repository")), purple(repo),))

    repo_sec = Repository()
    if not repo_sec.is_keypair_available(repo):
        entropy_srv.updateProgress("%s: %s" % (
                blue(_("No keys available for given repository")),
                purple(repo),
            ),
            type = "warning"
        )
        return 0

    answer = entropy_srv.askQuestion(_("Are you really sure?"))
    if answer == _("No"):
        return 1

    try:
        key_meta = repo_sec.get_key_metadata(repo)
    except KeyError:
        entropy_srv.updateProgress("%s: %s" % (
                darkgreen(_("Keys metadata not available for")),
                bold(repo),
            ),
            type = "error"
        )
        return 1

    # remove signatures from repository database
    dbconn = entropy_srv.open_server_repository(repo = repo, read_only = False)
    dbconn.dropGpgSignatures()

    repo_sec.delete_keypair(repo)
    entropy_srv.updateProgress("%s: %s" % (
            darkgreen(_("Deleted GPG key with fingerprint")),
            bold(key_meta['fingerprint']),
        ),
        type = "info"
    )
    return 0

def _show_status(entropy_srv, repo):
    repo_sec = Repository()

    try:
        key_meta = repo_sec.get_key_metadata(repo)
    except KeyError:
        entropy_srv.updateProgress("%s: %s" % (
                darkgreen(_("Keys metadata not available for")),
                bold(repo),
            ),
            type = "error"
        )
        return 1

    entropy_srv.updateProgress("%s: %s" % (
            brown(_("GPG information for repository")),
            bold(repo),
        ),
        type = "info"
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
        entropy_srv.updateProgress("%s: %s" % (
            teal(key_desc), out_func(key_meta[key_id]),))

    return 0

def _sign_packages(entropy_srv, repo):

    errors, fine, failed = entropy_srv.sign_local_packages(repo = repo,
        ask = True)
    if errors:
        return 2

    return 0
