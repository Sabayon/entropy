# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework constants module}.

    This module contains all the Entropy constants used all around
    the "entropy" package.

    Some of the constants in this module are used as "default" for
    the SystemSettings interface. So, make sure to read the documentation
    of SystemSettings in the "entropy.core" module.

    Even if possible, etpConst, etpUi, and etpSys objects
    *SHOULD* be I{never ever modified manually}. This freedom could change
    in future, so, if you want to produce a stable code, DON'T do that at all!

    Basic Entropy constants handling functions are available in this module
    and are all prefixed with "I{const_*}" or "I{initconfig_*}".
    If you are writing a third party application, you should always try
    to avoid to deal directly with functions here unless specified otherwise.
    In fact, usually these here are wrapper in upper-level modules
    (entropy.client, entropy.server, entropy.services).


"""
import sys
import os
import time
import codecs


import stat
import errno
import fcntl
import signal
import gzip
import bz2
import grp
import pwd
import traceback
import threading
try:
    import thread
except ImportError:
    # python 3.x
    import _thread as thread
from entropy.i18n import _, ENCODING, RAW_ENCODING

# Setup debugger hook on SIGUSR1
def debug_signal(signum, frame):
    import pdb
    pdb.set_trace()
if os.getuid() == 0:
    signal.signal(signal.SIGUSR1, debug_signal)

# Setup thread dump hook on SIGQUIT
def dump_signal(signum, frame, extended=True, stderr=sys.stderr):

    def _std_print_err(msg):
        stderr.write(msg + '\n')
        stderr.flush()

    _std_print_err("")
    _std_print_err("")
    _std_print_err("---- DUMP START [cut here] ----")
    thread_count = 0
    threads_map = dict((x.ident, x) for x in threading.enumerate())
    for thread_id, stack in sys._current_frames().items():
        thread_count += 1
        thread_obj = threads_map.get(thread_id, "N/A")
        _std_print_err("Thread: %s, object: %s" % (thread_id, thread_obj))

        stack_list = []
        _stack = stack
        while True:
            stack_list.append(_stack)
            _stack = _stack.f_back
            if _stack is None:
                break

        for filename, lineno, name, line in traceback.extract_stack(stack):
            _std_print_err("File: '%s', line %d, in %s'" % (
                    filename, lineno, name,))
            if line:
                _std_print_err("  %s" % (line.rstrip(),))
            else:
                _std_print_err("  ???")

            if not extended:
                continue

            try:
                _stack = stack_list.pop()
            except IndexError:
                _stack = None
            if _stack is None:
                continue

            for key, value in _stack.f_locals.items():
                cur_str = "\t%20s = " % key
                try:
                    cur_str += repr(value)
                except (AttributeError, NameError, TypeError):
                    cur_str += "<ERROR WHILE PRINTING VALUE>"
                _std_print_err(cur_str)

        _std_print_err("--")
        _std_print_err("")
    _std_print_err("[thread count: %d]" % (thread_count,))
    _std_print_err("---- DUMP END [cut here] ----")
    _std_print_err("")

_installed_sigquit = False
if os.getuid() == 0:
    _installed_sigquit = True
    signal.signal(signal.SIGQUIT, dump_signal)

_uname_m = os.uname()[4]
_rootdir = os.getenv("ETP_ROOT", "").rstrip("/")
_arch_override_file = os.path.join("/", _rootdir, "etc/entropy/.arch")
ETP_ARCH_CONST = None
if os.path.isfile(_arch_override_file):
    try:
        with codecs.open(_arch_override_file, "r", encoding=ENCODING) \
                as arch_f:
            _arch_const = arch_f.readline().strip()
            if _arch_const:
                ETP_ARCH_CONST = _arch_const
    except (IOError, OSError) as err:
        const_debug_write("_init_", repr(err))

# ETP_ARCH_CONST setup
# add more arches here
ETP_ARCH_MAP = {
    ("i386", "i486", "i586", "i686",): "x86",
    ("x86_64",): "amd64",
    ("mips", "mips64",): "mips",
}

if ETP_ARCH_CONST is None:
    for arches, arch in ETP_ARCH_MAP.items():
        if _uname_m in arches:
            ETP_ARCH_CONST = arch
            break

_more_keywords = None
if _uname_m.startswith("arm"):
    # ARM is "special", multiple subarches
    # ahead, better use the full uname value
    # and account "arm" to etpSys['keywords']
    if ETP_ARCH_CONST is None:
        ETP_ARCH_CONST = _uname_m
    _more_keywords = set(["arm", "~arm"])
elif ETP_ARCH_CONST is None:
    ETP_ARCH_CONST = "UNKNOWN"

etpSys = {
    'archs': ['alpha', 'amd64', 'amd64-fbsd', 'arm', 'hppa', 'ia64', 'm68k',
        'mips', 'ppc', 'ppc64', 's390', 'sh', 'sparc', 'sparc-fbsd', 'x86',
        'x86-fbsd'],
    'keywords': set([ETP_ARCH_CONST, "~"+ETP_ARCH_CONST]),
    'api': '3',
    'arch': ETP_ARCH_CONST,
    'rootdir': _rootdir,
    'serverside': False,
    'unittest': False,
}
if _more_keywords is not None:
    etpSys['keywords'] |= _more_keywords

# debug mode flag, will be triggered by ETP_DEBUG env var.
_DEBUG = os.getenv("ETP_DEBUG") is not None

if _DEBUG and not _installed_sigquit:
    # install the dump signal function at
    # SIGQUIT anyway if --debug is enabled
    signal.signal(signal.SIGQUIT, dump_signal)

etpConst = {}

def initconfig_entropy_constants(rootdir):

    """
    Main constants configurators, this is the only function that you should
    call from the outside, anytime you want. it will reset all the variables
    excluding those backed up previously.

    @param rootdir: current root directory, if any, or ""
    @type rootdir: string
    @rtype: None
    @return: None
    @raise AttributeError: when specified rootdir is not a directory
    """

    if rootdir and not os.path.isdir(rootdir):
        raise AttributeError("not a valid chroot.")

    # set env ROOT
    # this way it doesn't need to be set around the code
    os.environ['ROOT'] = rootdir + os.path.sep

    # save backed up settings
    if 'backed_up' in etpConst:
        backed_up_settings = etpConst.pop('backed_up')
    else:
        backed_up_settings = {}

    const_default_settings(rootdir)
    const_read_entropy_release()
    const_create_working_dirs()
    const_setup_entropy_pid()
    const_configure_lock_paths()

    # reflow back settings
    etpConst.update(backed_up_settings)
    etpConst['backed_up'] = backed_up_settings.copy()

    # try to set proper permissions for /etc/entropy (at least group)
    # /etc/entropy should be always writeable by "entropy" group !
    # DO NOT FRIGGIN REMOVE
    const_setup_perms(etpConst['confdir'], etpConst['entropygid'],
        recursion = False)

    # setup pid file directory if not existing
    # this is really important, build system should also handle this
    # but better being paranoid and do stuff ourselves :-)
    if not os.path.isdir(etpConst['pidfiledir']):
        try:
            const_setup_directory(etpConst['pidfiledir'])
        except (OSError, IOError) as err:
            sys.stderr.write("WARNING: cannot create %s, %s\n" % (
                    etpConst['pidfiledir'], repr(err),))

    # also setup /var/tmp/entropy if it doesn't exist.
    # /var/tmp can be mounted on tmpfs
    if not os.path.isdir(etpConst['entropyunpackdir']):
        try:
            const_setup_directory(etpConst['entropyunpackdir'])
        except (OSError, IOError) as err:
            sys.stderr.write("WARNING: cannot create %s: %s\n" % (
                    etpConst['entropyunpackdir'], repr(err),))

    const_setup_perms(etpConst['pidfiledir'], etpConst['entropygid'],
        recursion = False)

    if sys.excepthook is sys.__excepthook__:
        sys.excepthook = __const_handle_exception

def const_default_settings(rootdir):
    """
    Initialization of all the Entropy base settings.

    @param rootdir: current root directory, if any, or ""
    @type rootdir: string
    @rtype: None
    @return: None
    """
    original_rootdir = rootdir
    if not rootdir.strip():
        rootdir = os.path.sep
    default_etp_dir = os.getenv(
        'DEV_ETP_VAR_DIR',
        os.path.join(rootdir, "var/lib/entropy"))
    default_etp_tmpdir = "/tmp"
    default_etp_dbdir_name = "database"

    default_etp_dbdir = os.path.join(
        default_etp_dbdir_name, ETP_ARCH_CONST)
    default_etp_dbfile = "packages.db"
    default_etp_dbclientfile = "equo.db"
    default_etp_client_repodir = "client"
    default_etp_cachesdir = "caches"
    default_etp_securitydir = "glsa"
    default_etp_logdir = "logs"

    default_etp_confdir = os.getenv(
        'DEV_ETP_ETC_DIR',
        os.path.join(rootdir, "etc/entropy"))
    default_etp_syslogdir = os.getenv(
        'DEV_ETP_LOG_DIR',
        os.path.join(rootdir, "var/log/entropy"))
    default_etp_vardir = os.getenv(
        'DEV_ETP_TMP_DIR',
        os.path.join(rootdir, "var/tmp/entropy"))

    default_etp_tmpcache_dir = os.getenv('DEV_ETP_CACHE_DIR',
        os.path.join(default_etp_dir, default_etp_cachesdir))

    etpConst.clear()
    my_const = {
        'logging': {
            'normal_loglevel_id': 1,
            'verbose_loglevel_id': 2,
        },
        'backed_up': {},
        # entropy default installation directory
        'installdir': '/usr/lib/entropy',

        # directory where entropy stores its configuration
        'confdir': default_etp_confdir,
        # name of the package sets directory
        'confsetsdirname': "sets",

        # used by entropy.spm to build pkgs relative URL metadata ("download",
        # returned by EntropyRepository.retrieveDownloadURL())
        'packagesrelativepath_basedir': "packages",
        'packagesrelativepath_basedir_nonfree': "packages-nonfree",
        'packagesrelativepath_basedir_restricted': "packages-restricted",
        'packagesrelativepaths': ("packages", "packages-nonfree",
            "packages-restricted"),
        'packagesrelativepath_basename': ETP_ARCH_CONST,
        'databaserelativepath_basedir': default_etp_dbdir_name,

        'entropyworkdir': default_etp_dir, # Entropy workdir
        # new (since 0.99.48) Entropy downloaded packages location
        # equals to /var/lib/entropy/client/packages containing packages/,
        # packages-nonfree/, packages-restricted/ etc
        'entropypackagesworkdir': os.path.join(default_etp_dir,
            default_etp_client_repodir, "packages"),
        # Entropy unpack directory
        'entropyunpackdir': default_etp_vardir,
        # Entropy packages image directory
        'entropyimagerelativepath': "image",

        # entropy repository database upload timestamp
        'etpdatabasetimestampfile': default_etp_dbfile+".timestamp",
        # entropy repository database owned (in repo) package files
        'etpdatabasepkglist': default_etp_dbfile+".pkglist",
        # same for extra_download metadata
        'etpdatabaseextrapkglist': default_etp_dbfile+".extra_pkglist",
        # file containing a list of packages that are strictly
        # required by the repository, thus forced
        'etpdatabasesytemmaskfile': default_etp_dbfile+".system_mask",
        'etpdatabasemaskfile': default_etp_dbfile+".mask",
        'etpdatabasekeywordsfile': default_etp_dbfile+".keywords",
        'etpdatabaseupdatefile': default_etp_dbfile+".repo_updates",
        'etpdatabaselicwhitelistfile': default_etp_dbfile+".lic_whitelist",
        'etpdatabasecriticalfile': default_etp_dbfile+".critical",
        'etpdatabasemirrorsfile': default_etp_dbfile+".mirrors",
        'etpdatabasefallbackmirrorsfile': default_etp_dbfile+".fallback_mirrors",
        'etpdatabasewebservicesfile': default_etp_dbfile+".webservices",

        # per-repository configuration file to list legally sensible pkgs
        'etpdatabaserestrictedfile': default_etp_dbfile+".restricted",
        # the local/remote database revision file
        'etpdatabaserevisionfile': default_etp_dbfile+".revision",
        # missing dependencies black list file
        'etpdatabasemissingdepsblfile': default_etp_dbfile + \
            ".missing_deps_blacklist",
        # compressed file that contains all the "meta"
        # files in a repository dir
        'etpdatabasemetafilesfile': default_etp_dbfile+".meta",
        # file that contains a list of the "meta"
        # files not available in the repository
        'etpdatabasemetafilesnotfound': default_etp_dbfile+".meta_notfound",
        # database file checksum
        'etpdatabasehashfile': default_etp_dbfile+".md5",

        # the remote database lock file
        'etpdatabaselockfile': default_etp_dbfile+".lock",
        # the remote database download lock file
        'etpdatabasedownloadlockfile': default_etp_dbfile+".download.lock",
        # eapi3 "there are updates" signal file
        # used to let EAPI3 remote service daemon know about repository updates
        'etpdatabaseeapi3updates': default_etp_dbfile+".eapi3_updates",
        # "there are updates" signal file for webinstall packages
        # can be used to trigger the generation of new webinstall files
        'etpdatabasewebinstallupdates': default_etp_dbfile+".webinst_updates",
        # repository GPG public key file
        'etpdatabasegpgfile': "signature.asc",
        'etpgpgextension': ".asc",
        # Entropy Client GPG repositories keyring path
        'etpclientgpgdir': default_etp_confdir+"/client-gpg-keys",
        # when this file exists, the database is not synced
        # anymore with the online one
        'etpdatabasetaintfile': default_etp_dbfile+".tainted",

        # Entropy sqlite database file default_etp_dir + \
        #    default_etp_dbdir+"/packages.db"
        'etpdatabasefile': default_etp_dbfile,
        # Entropy sqlite database file (gzipped)
        'etpdatabasefilegzip': default_etp_dbfile+".gz",
        'etpdatabasefilegziphash': default_etp_dbfile+".gz.md5",
        # Entropy sqlite database file (bzipped2)
        'etpdatabasefilebzip2': default_etp_dbfile+".bz2",
        'etpdatabasefilebzip2hash': default_etp_dbfile+".bz2.md5",

        # Entropy sqlite database file (gzipped)
        'etpdatabasefilegziplight': default_etp_dbfile+".light.gz",
        'etpdatabasefilehashgziplight': default_etp_dbfile+".light.gz.md5",
        # Entropy sqlite database file (bzipped2)
        'etpdatabasefilebzip2light': default_etp_dbfile+".light.bz2",
        'etpdatabasefilehashbzip2light': default_etp_dbfile+".light.bz2.md5",

        # Entropy sqlite database dump file (bzipped2)
        'etpdatabasedumpbzip2': default_etp_dbfile+".dump.bz2",
        'etpdatabasedumphashfilebz2': default_etp_dbfile+".dump.bz2.md5",
        # Entropy sqlite database dump file (gzipped)
        'etpdatabasedumpgzip': default_etp_dbfile+".dump.gz",
        'etpdatabasedumphashfilegzip': default_etp_dbfile+".dump.gz.md5",

        # Entropy sqlite database dump file
        'etpdatabasedump': default_etp_dbfile+".dump",

        # Entropy sqlite database dump file (bzipped2) light ver
        'etpdatabasedumplightbzip2': default_etp_dbfile+".dumplight.bz2",
        # Entropy sqlite database dump file (gzipped) light ver
        'etpdatabasedumplightgzip': default_etp_dbfile+".dumplight.gz",
        # Entropy sqlite database dump file, light ver (no content)
        'etpdatabasedumplighthashfilebz2': default_etp_dbfile+".dumplight.bz2.md5",
        'etpdatabasedumplighthashfilegzip': default_etp_dbfile+".dumplight.gz.md5",
        'etpdatabasedumplight': default_etp_dbfile+".dumplight",
        # expiration based server-side packages removal

        'etpdatabaseexpbasedpkgsrm': default_etp_dbfile+".fatscope",

        # Entropy default compressed database format
        'etpdatabasefileformat': "bz2",
        # Entropy compressed databases format support
        'etpdatabasesupportedcformats': ["bz2", "gz"],
        'etpdatabasecompressclasses': {
            "bz2": (bz2.BZ2File, "unpack_bzip2", "etpdatabasefilebzip2",
                "etpdatabasedumpbzip2", "etpdatabasedumphashfilebz2",
                "etpdatabasedumplightbzip2", "etpdatabasedumplighthashfilebz2",
                "etpdatabasefilebzip2light", "etpdatabasefilehashbzip2light",
                "etpdatabasefilebzip2hash",),
            "gz": (gzip.GzipFile, "unpack_gzip", "etpdatabasefilegzip",
                "etpdatabasedumpgzip", "etpdatabasedumphashfilegzip",
                "etpdatabasedumplightgzip", "etpdatabasedumplighthashfilegzip",
                "etpdatabasefilegziplight", "etpdatabasefilehashgziplight",
                "etpdatabasefilegziphash",)
        },
        # Distribution website URL
        'distro_website_url': "http://www.sabayon.org",
        'packages_website_url': "https://packages.sabayon.org",
        'changelog_filename': "ChangeLog",
        'changelog_filename_compressed': "ChangeLog.bz2",
        'changelog_date_format': "%a, %d %b %Y %X +0000",
        # enable/disable packages RSS feed feature
        'rss-feed': True,
        # default name of the RSS feed
        'rss-name': "packages.rss",
         # light version of rss-name
        'rss-light-name': "updates.rss",
        # default URL to the entropy web interface
        # (overridden in reagent.conf)
        'rss-base-url': "http://packages.sabayon.org/",
        # default URL to the Operating System website
        # (overridden in reagent.conf)
        'rss-website-url': "http://www.sabayon.org/",
        # xml file where will be dumped ServerInterface.rssMessages dictionary
        'rss-dump-name': "rss_database_actions",
        'rss-max-entries': 1000, # maximum rss entries
        'rss-light-max-entries': 300, # max entries for the light version
        'rss-managing-editor': "lxnay@sabayon.org", # updates submitter
        # repository RSS-based notice board content
        'rss-notice-board': "notice.rss",
        # File containing user data related to repository notice board
        'rss-notice-board-userdata': "notice.rss.userdata",
        # default Entropy Client GPG support bit
        'client_gpg': True,
        # "or" dependencies support
        # app-foo/foo;app-foo/abc?
        'entropyordepsep': ";",
        'entropyordepquestion': "?",
        'entropyslotprefix': ":",
        'entropytagprefix': "#",
        'packagesetprefix': "@",
        'entropyrepoprefix': "@",
        'entropyrepoprefix_alt': "::",
        'entropyrevisionprefix': "~",
        'userpackagesetsid': "__user__",
        'cachedumpext': ".dmp",
        'packagesext': ".tbz2",
        # extra download package file extension (mandatory)
        'packagesextraext': ".tar.bz2",
        'packagesdebugext': ".debug.tar.bz2", # .tar.bz2
        'packagesext_webinstall': ".etp",
        # entropy package files binary delta extension
        'packagesdeltaext': ".edelta",
        # entropy package files binary delta subdir
        'packagesdeltasubdir': "deltas",
        # Extension of the file that contains the checksum
        # of its releated package file
        'packagesmd5fileext': ".md5",
        'packagessha512fileext': ".sha512",
        'packagessha256fileext': ".sha256",
        'packagessha1fileext': ".sha1",
        # Supported Entropy Client package hashes encodings
        'packagehashes': ("sha1", "sha256", "sha512", "gpg"),
        # Used by Entropy client to override some digest checks
        'packagemtimefileext': ".mtime",
        # Extension of the file that "contains" expiration mtime
        'packagesexpirationfileext': ".expired",
        # number of days after a package will be removed from mirrors
        'packagesexpirationdays': 15,
        # name of the trigger file that would be executed
        # by equo inside triggerTools
        'triggername': "trigger",
        'trigger_sh_interpreter': rootdir+"/usr/sbin/entropy.sh",
        # entropy hardware hash generator executable
        'etp_hw_hash_gen': rootdir+"/usr/bin/entropy_hwgen.sh",
        # entropy client post valid branch migration (equo hop) script name
        'etp_post_branch_hop_script': default_etp_dbfile+".post_branch.sh",
        # entropy client post branch upgrade script
        'etp_post_branch_upgrade_script': default_etp_dbfile+".post_upgrade.sh",
        # previous branch file container
        'etp_previous_branch_file': default_etp_confdir+"/.previous_branch",
        'etp_in_branch_upgrade_file': default_etp_confdir+"/.in_branch_upgrade",
        # entropy client post repository update script (this is executed
        # every time)
        'etp_post_repo_update_script': default_etp_dbfile+".post_update.sh",

        # proxy configuration constants, used system wide
        'proxy': {
            'ftp': os.getenv("FTP_PROXY"),
            'http': os.getenv("HTTP_PROXY"),
            'rsync': os.getenv("RSYNC_PROXY"),
            'username': None,
            'password': None
        },
        # Entropy log level (default: 1 - see entropy.conf for more info)
        'entropyloglevel': 1,
        # Entropy Socket Interface log level
        'socketloglevel': 2,
        # Log dir where ebuilds store their stuff
        'logdir': os.path.join(default_etp_dir, default_etp_logdir),

        # Entropy system tools log directory
        'syslogdir': default_etp_syslogdir,
        'entropylogfile': os.path.join(
            default_etp_syslogdir, "entropy.log"),
        'securitylogfile': os.path.join(
            default_etp_syslogdir, "security.log"),

        'etpdatabaseclientdir': os.path.join(
            default_etp_dir, default_etp_client_repodir,
            default_etp_dbdir),
        # path to equo.db - client side database file
        'etpdatabaseclientfilepath': os.path.join(
            default_etp_dir, default_etp_client_repodir,
            default_etp_dbdir, default_etp_dbclientfile),
        # prefix of database backups
        'dbbackupprefix': 'entropy_backup_',

        # Entropy database API revision
        'etpapi': etpSys['api'],
        # Entropy database API currently supported
        'supportedapis': (1, 2, 3),
        # contains the current running architecture
        'currentarch': etpSys['arch'],
        # Entropy supported Archs
        'supportedarchs': etpSys['archs'],

        # default choosen branch (overridden by setting in repositories.conf)
        'branch': "5",
         # default allowed package keywords
        'keywords': etpSys['keywords'].copy(),
        # allow multiple packages in single scope server-side?
        # this makes possible to have multiple versions of packages
        # and handle the removal through expiration (using creation date)
        'expiration_based_scope': False,
        # our official repository name
        'defaultserverrepositoryid': None,
        'officialrepositoryid': "sabayonlinux.org",
        # tag to append to .tbz2 file before entropy database (must be 32bytes)
        'databasestarttag': "|ENTROPY:PROJECT:DB:MAGIC:START|",
        # Entropy resources lock file path
        'pidfiledir': "/var/run/entropy",
        'pidfile': "/var/run/entropy/entropy.lock",
        # option to keep a backup of config files after
        # being overwritten by equo conf update
        'filesbackup': True,
        # option to enable Entropy Client splitdebug support
        'splitdebug': False,
        # directories where debug symbols are stored
        'splitdebug_dirs': ("/usr/lib/debug",),
        # option to enable forced installation of critical updates
        'forcedupdates': True,
        # collision protection option, see client.conf for more info
        'collisionprotect': 1,
        # list of user specified CONFIG_PROTECT directories
        # (see Gentoo manual to understand the meaining of this parameter)
        'configprotect': [],
        # list of user specified CONFIG_PROTECT_MASK directories
        'configprotectmask': [],
        # list of user specified configuration files that
        # should be ignored and kept as they are
        'configprotectskip': [],
        # installed database CONFIG_PROTECT directories
        'dbconfigprotect': [],
        # installed database CONFIG_PROTECT_MASK directories
        'dbconfigprotectmask': [],
        # this will be used to show the number of updated
        # files at the end of the processes
        'configprotectcounter': 0,
        # default Entropy release version
        'entropyversion': "1.0",
        # default system name (overidden by entropy.conf settings)
        'systemname': "Sabayon Linux",
        # Product identificator (standard, professional...)
        'product': "standard",
        'systemroot': original_rootdir, # default system root
        'uid': os.getuid(), # current running UID
        'entropygid': None,
        'entropygid_nopriv': None,
        'sysgroup': "entropy",
        'sysgroup_nopriv': "entropy-nopriv",
        'sysuser_nopriv': "entropy-nopriv",
        'sysuser_nopriv_fallback': "nobody",
        'defaultumask': 0o22,
        'storeumask': 0o02,
        'gentle_nice': 15,
        'current_nice': 0,
        'default_nice': 0,
        # Default download socket timeout for Entropy Client transceivers
        'default_download_timeout': 30,
        # Entropy package dependencies type identifiers
        'dependency_type_ids': {
            'rdepend_id': 0, # runtime dependencies
            'pdepend_id': 1, # post dependencies
            'mdepend_id': 2, # actually, this is entropy-only
            'bdepend_id': 3, # build dependencies
        },
        'dependency_type_ids_desc': {
            'rdepend_id': _("Runtime dependency"),
            'pdepend_id': _("Post dependency"),
            'mdepend_id': _('Manually added (by staff) dependency'),
            'bdepend_id': _('Build dependency'),
        },

        # entropy client packages download speed limit (in kb/sec)
        'downloadspeedlimit': None,

        # data storage directory, useful to speed up
        # entropy client across multiple issued commands
        'dumpstoragedir': default_etp_tmpcache_dir,
        # where GLSAs are stored
        'securitydir': os.path.join(
            default_etp_dir, default_etp_securitydir),
        'securityurl': "http://community.sabayon.org/security"
            "/security-advisories.tar.bz2",

        'safemodeerrors': {
            'clientdb': 1,
        },
        'safemodereasons': {
            0: _("All fine"),
            1: _("Corrupted Client Repository. Please restore a backup."),
        },

        'misc_counters': {
            'forced_atoms_update_ids': {
                '__idtype__': 1,
                'kde': 1,
            },
        },

        'system_settings_plugins_ids': {
            'client_plugin': "client_plugin",
            'server_plugin': "server_plugin",
            'server_plugin_fatscope': "server_plugin_fatscope",
            'server_plugin_fake_client': "server_plugin_fake_client",
        },

        'clientserverrepoid': "__system__", # these two values have to match!
        'clientdbid': "__system__", # these two values have to match!
        'serverdbid': "__server__",
        'genericdbid': "__generic__",
        'spmdbid': "spm-db",
        'spmetprev': 9999,
        'systemreleasefile': "/etc/sabayon-release",

        'install_sources': {
            'unknown': 0,
            'user': 1,
            'automatic_dependency': 2,
        },

        'pkg_masking_reasons': {
            0: _('reason not available'),
            1: _('user package.mask'),
            2: _('system keywords'),
            3: _('user package.unmask'),
            4: _('user repo package.keywords (all packages)'),
            5: _('user repo package.keywords'),
            6: _('user package.keywords'),
            7: _('completely masked (by keyword?)'),
            8: _('repository general packages.db.mask'),
            9: _('repository general packages.db.keywords'),
            10: _('user license.mask'),
            11: _('user live unmask'),
            12: _('user live mask'),
        },
        'pkg_masking_reference': {
            'reason_not_avail': 0,
            'user_package_mask': 1,
            'system_keyword': 2,
            'user_package_unmask': 3,
            'user_repo_package_keywords_all': 4,
            'user_repo_package_keywords': 5,
            'user_package_keywords': 6,
            'completely_masked': 7,
            'repository_packages_db_mask': 8,
            'repository_packages_db_keywords': 9,
            'user_license_mask': 10,
            'user_live_unmask': 11,
            'user_live_mask': 12,
        },

        # default entropy configuration files encoding
        'conf_encoding': ENCODING,
        'conf_raw_encoding': RAW_ENCODING,

    }

    # set current nice level
    try:
        my_const['current_nice'] = os.nice(0)
    except OSError:
        pass

    etpConst.update(my_const)

def const_is_python3():
    """
    Return whether Python3 is interpreting this code.
    """
    return sys.hexversion >= 0x3000000

def const_set_nice_level(nice_level = 0):
    """
    Change current process scheduler "nice" level.

    @param nice_level: new valid nice level
    @type nice_level: int
    @rtype: int
    @return: current_nice new nice level
    """
    default_nice = etpConst['default_nice']
    current_nice = etpConst['current_nice']
    delta = current_nice - default_nice
    try:
        etpConst['current_nice'] = os.nice(delta*-1+nice_level)
    except OSError:
        pass
    return current_nice

def const_read_entropy_release():
    """
    Read Entropy release file content and fill etpConst['entropyversion']

    @rtype: None
    @return: None
    """
    # handle Entropy Version
    revision_file = "../lib/entropy/revision"
    if not os.path.isfile(revision_file):
        revision_file = os.path.join(etpConst['installdir'],
            'lib/entropy/revision')
    if os.path.isfile(revision_file) and \
        os.access(revision_file, os.R_OK):

        with codecs.open(revision_file, "r", encoding=ENCODING) as rev_f:
            myrev = rev_f.readline().strip()
            etpConst['entropyversion'] = myrev

def const_pid_exists(pid):
    """
    Determine whether given pid exists.

    @param pid: process id
    @type pid: int
    @return: pid exists? 1; pid does not exist? 0
    @rtype: int
    """
    try:
        os.kill(pid, signal.SIG_DFL)
        return 1
    except OverflowError:
        # pid is invalid int, signed integer is greater than maximum
        return 0
    except OSError as err:
        return err.errno == errno.EPERM

_ENTROPY_PID_F_MAP = {}
_ENTROPY_PID_MUTEX = threading.Lock()
def const_setup_entropy_pid(just_read = False, force_handling = False):
    """
    Setup Entropy pid file, if possible and if UID = 0 (root).
    If the application is run with --no-pid-handling argument
    (or ETP_NO_PID_HANDLING env var is set),
    this function will have no effect. If just_read is specified,
    this function will only try to read the current pid string in
    the Entropy pid file (etpConst['pidfile']). If any other entropy
    istance is currently owning the contained pid, the second bool of the tuple
    is True.

    @keyword just_read: only read the current pid file, if any and if possible
    @type just_read: bool
    @keyword force_handling: force pid handling even if "--no-pid-handling" is
        given
    @type force_handling: bool
    @rtype: tuple
    @return: tuple composed by two bools, (if pid lock file has been acquired,
        locked resources)
    """
    with _ENTROPY_PID_MUTEX:

        no_pid_handling = ("--no-pid-handling" in sys.argv) or \
            os.getenv("ETP_NO_PID_HANDLING")

        if (no_pid_handling and not force_handling) and not just_read:
            return False, False

        pid = os.getpid()
        _entropy_pid_f = _ENTROPY_PID_F_MAP.get(pid)
        if _entropy_pid_f is not None:
            # we have already acquired the lock, we're safe
            return False, False

        setup_done = False
        locked = False
        # acquire the pid file exclusively, in non-blocking mode
        # if the acquisition fails, it means that another process
        # is holding it. No matter what is the pid written inside,
        # which itself is unreliable since pids can be reused
        # quite easily.
        flags = fcntl.LOCK_EX | fcntl.LOCK_NB

        # PID creation
        pid_file = etpConst['pidfile']
        pid_f = None

        locked = True
        try:
            pid_f = open(pid_file, "a+")
            fcntl.flock(pid_f.fileno(), flags)
            locked = False
        except IOError as err:
            if err.errno == errno.EWOULDBLOCK:
                locked = True
            elif err.errno not in (errno.EROFS, errno.EACCES):
                # readonly filesystem or permission denied
                raise
            else:
                # in any other case, the lock is not acquired,
                # so locked is False
                locked = False

        if (not just_read) and (pid_f is not None) and (not locked):
            # write my pid in it then, not that it matters...
            try:
                pid_f.seek(0)
                pid_f.truncate()
                pid_f.write(str(pid))
                pid_f.flush()
            except IOError as err:
                if err.errno not in (errno.EROFS, errno.EACCES):
                    # readonly filesystem or permission denied
                    raise
                # who cares otherwise...

            try:
                const_chmod_entropy_pid()
            except OSError:
                pass
            setup_done = True

        if (pid_f is not None) and locked:
            # the lock file is acquired by another process
            # and we were not able to get it. So, close pid_f
            # and set it to None. So that next time we get here
            # we'll retry the whole procedure.
            pid_f.close()
            pid_f = None
        if pid_f is not None:
            _ENTROPY_PID_F_MAP[pid] = pid_f
        return setup_done, locked

def const_unsetup_entropy_pid():
    """
    Drop Entropy Pid Lock if acquired. Return True if dropped,
    False otherwise.
    """

    with _ENTROPY_PID_MUTEX:
        pid = os.getpid()
        _entropy_pid_f = _ENTROPY_PID_F_MAP.get(pid)
        if _entropy_pid_f is not None:
            fcntl.flock(_entropy_pid_f.fileno(), fcntl.LOCK_UN)
            _entropy_pid_f.close()
            del _ENTROPY_PID_F_MAP[pid]
            return True
        return False

def const_secure_config_file(config_file):
    """
    Setup entropy file needing strict permissions, no world readable.

    @param config_file: valid config file path
    @type config_file: string
    @rtype: None
    @return: None
    """
    try:
        mygid = const_get_entropy_gid()
    except KeyError:
        mygid = 0
    try:
        const_setup_file(config_file, mygid, 0o660)
    except (OSError, IOError,):
        pass

def const_drop_privileges(unpriv_uid = None, unpriv_gid = None):
    """
    This function does its best to drop process privileges. If it fails, an
    exception is raised. You can consider this function security-safe.

    @param unpriv_uid: override default unprivileged uid
    @type unpriv_uid: int
    @param unpriv_gid: override default unprivileged gid
    @type unpriv_gid: int
    @raise entropy.exceptions.SecurityError: if unprivileged uid/gid cannot
        be retrieived.
    @raise ValueError: if program is already running as unprivileged user,
        but this differs from the usual entropy unprivileged user.
    @raise OSError: if privileges can't be dropped, the underlying syscall
        fails.
    @todo: when Python 2.7, see os.setresuid()
    """
    cur_uid = os.getuid()

    if unpriv_uid is None:
        unpriv_uid = const_get_lazy_nopriv_uid()
    if unpriv_gid is None:
        unpriv_gid = const_get_lazy_nopriv_gid()

    if cur_uid in (unpriv_uid, etpConst['sysuser_nopriv_fallback']):
        # already unprivileged
        return
    elif cur_uid != 0:
        raise ValueError("already running as another unprivileged user")

    # privileges can be dropped
    os.setregid(unpriv_gid, 0)
    os.setreuid(unpriv_uid, 0) # real uid, effective uid

    # make sure
    if os.getuid() != unpriv_uid:
        raise OSError("privileges (uid) have not been dropped")
    if os.getgid() != unpriv_gid:
        raise OSError("privileges (gid) have not been dropped")

    etpConst['uid'] = unpriv_uid

def const_regain_privileges():
    """
    This function should be called if, and only if, a previous
    const_drop_privileges() has been called. It makes the program able to
    get back privileges that were dropped previously.

    @raise entropy.exceptions.SecurityError: if unprivileged uid/gid cannot
        be retrieived.
    @todo: when Python 2.7, see os.getresuid()
    """
    cur_uid = os.getuid()

    if cur_uid == 0:
        # already running privileged
        return

    # privileges can be dropped
    # set like this, otherwise we won't get back all our privs!
    os.setreuid(0, 0) # real uid, effective uid
    os.setregid(0, 0)

    # make sure
    if os.getuid() != 0:
        raise OSError("privileges (uid) have not been dropped")
    if os.getgid() != 0:
        raise OSError("privileges (gid) have not been dropped")

    etpConst['uid'] = 0

def const_chmod_entropy_pid():
    """
    Setup entropy pid file permissions, if possible.

    @return: None
    """
    try:
        mygid = const_get_entropy_gid()
    except KeyError:
        mygid = 0
    const_setup_file(etpConst['pidfile'], mygid, 0o664)

def const_create_working_dirs():

    """
    Setup Entropy directory structure, as much automagically as possible.

    @rtype: None
    @return: None
    """

    # handle pid file, this is /var/run and usually tmpfs
    piddir = etpConst['pidfiledir']
    if etpConst['uid'] == 0:
        const_setup_directory(piddir)

    # create group if it doesn't exist
    gid = None
    try:
        gid = const_get_entropy_gid()
    except KeyError:
        if etpConst['uid'] == 0:
            _const_add_entropy_group(etpConst['sysgroup'])
            try:
                gid = const_get_entropy_gid()
            except KeyError:
                pass

    # create unprivileged entropy-nopriv group
    nopriv_gid = None
    try:
        nopriv_gid = const_get_entropy_nopriv_gid()
    except KeyError:
        if etpConst['uid'] == 0:
            _const_add_entropy_group(etpConst['sysgroup_nopriv'])
            try:
                nopriv_gid = const_get_entropy_nopriv_gid()
            except KeyError:
                pass

    if gid is not None:
        etpConst['entropygid'] = gid
    if nopriv_gid is not None:
        etpConst['entropygid_nopriv'] = nopriv_gid

def const_convert_log_level(entropy_log_level):
    """
    Converts Entropy log levels (0, 1, 2) to logging.ERROR, logging.INFO,
    logging.DEBUG.

    @param entropy_log_level: entropy log level id (0, 1, 2), bogus values are
        return logging.DEBUG
    @type entropy_log_level: int
    @return: logging.{ERROR,INFO,DEBUG} value
    @rtype: int
    """
    import logging
    log_map = {
        0: logging.ERROR,
        1: logging.INFO,
        2: logging.DEBUG
    }
    return log_map.get(entropy_log_level, logging.INFO)

def const_configure_lock_paths():
    """
    Setup Entropy lock file paths.

    @rtype: None
    @return: None
    """
    etpConst['locks'] = {
        'using_resources': os.path.join(etpConst['entropyworkdir'],
            '.using_resources'),
    }

def const_setup_perms(mydir, gid, f_perms = None, recursion = True, uid = -1):
    """
    Setup permissions and group id (GID) to a directory, recursively.

    @param mydir: valid file path
    @type mydir: string
    @param gid: valid group id (GID)
    @type gid: int
    @keyword f_perms: file permissions in octal type
    @type f_perms: octal
    @keyword recursion: set permissions recursively?
    @type recursion: bool
    @keyword uid: usually this argument shouldn't be used, but in cae
        it sets the uid to the file
    @type uid: int
    @rtype: None
    @return: None
    """

    if gid == None:
        return
    if f_perms is None:
        f_perms = 0o664

    def do_setup_dir(currentdir):
        try:
            cur_gid = os.stat(currentdir)[stat.ST_GID]
            if cur_gid != gid:
                os.chown(currentdir, uid, gid)
            cur_mod = const_get_chmod(currentdir)
            if cur_mod != oct(0o775):
                os.chmod(currentdir, 0o775)
        except OSError:
            pass

    do_setup_dir(mydir)
    if recursion:
        for currentdir, subdirs, files in os.walk(mydir):
            do_setup_dir(currentdir)
            for item in files:
                item = os.path.join(currentdir, item)
                try:
                    const_setup_file(item, gid, f_perms, uid = uid)
                except OSError:
                    pass

def const_setup_file(myfile, gid, chmod, uid = -1):
    """
    Setup file permissions and group id (GID).

    @param myfile: valid file path
    @type myfile: string
    @param gid: valid group id (GID)
    @type gid: int
    @param chmod: permissions
    @type chmod: integer representing an octal
    @keyword uid: usually this argument shouldn't be used, but in cae
        it sets the uid to the file
    @type uid: int
    """
    cur_gid = os.stat(myfile)[stat.ST_GID]
    if cur_gid != gid:
        os.chown(myfile, uid, gid)
    const_set_chmod(myfile, chmod)

def const_setup_directory(dirpath):
    """
    Setup Entropy directory, creating it if required, changing
    ownership and permissions as well.

    @param dirpath: path to entropy directory
    @type dirpath: string
    @raise OSError: if permissions are fucked up
    """
    try:
        os.makedirs(dirpath)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise
    const_setup_perms(dirpath, etpConst['entropygid'],
                      recursion=False)

def const_get_chmod(myfile):
    """
    This function get the current permissions of the specified
    file. If you want to use the returning value with const_set_chmod
    you need to convert it back to int.

    @param myfile: valid file path
    @type myfile: string
    @rtype: integer(8) (octal)
    @return: octal representing permissions
    """
    myst = os.stat(myfile)[stat.ST_MODE]
    return oct(myst & 0o777)

def const_set_chmod(myfile, chmod):
    """
    This function sets specified permissions to a file.
    If they differ from the current ones.

    @param myfile: valid file path
    @type myfile: string
    @param chmod: permissions
    @type chmod: integer representing an octal
    @rtype: None
    @return: None
    """
    cur_mod = const_get_chmod(myfile)
    if cur_mod != oct(chmod):
        os.chmod(myfile, chmod)

def const_get_entropy_gid():
    """
    This function tries to retrieve the "entropy" user group
    GID.

    @rtype: int
    @return: entropy group id
    @raise KeyError: when "entropy" system GID is not available
    """
    return int(grp.getgrnam(etpConst['sysgroup']).gr_gid)

def const_get_entropy_nopriv_gid():
    """
    This function tries to retrieve the "entropy-nopriv" user group
    GID. This is the unprivileged entropy users group.

    @rtype: int
    @return: entropy-nopriv group id
    @raise KeyError: when "entropy-nopriv" system GID is not available
    """
    return int(grp.getgrnam(etpConst['sysgroup_nopriv']).gr_gid)

def const_get_entropy_nopriv_uid():
    """
    This function tries to retrieve the "entropy-nopriv" user id (uid).

    @rtype: int
    @return: entropy-nopriv user id
    @raise KeyError: when "entropy-nopriv" system UID is not available
    """
    return int(pwd.getpwnam(etpConst['sysuser_nopriv']).pw_uid)

def const_get_fallback_nopriv_uid():
    """
    Fallback function that tries to retrieve the "nobody" user id (uid).
    It is used when const_get_entropy_nopriv_uid() fails.

    @rtype: int
    @return: nobody user id
    @raise KeyError: when "nobody" system UID is not available
    """
    return int(pwd.getpwnam("nobody").pw_uid)

def const_get_lazy_nopriv_uid():
    """
    This function returns an unprivileged uid by first trying to call
    const_get_entropy_nopriv_uid() and then const_get_fallback_nopriv_uid()

    @return: uid
    @rtype: int
    @raise entropy.exceptions.SecurityError: if unprivileged user id is not
        available.
    """
    unpriv_uid = None
    try:
        unpriv_uid = const_get_entropy_nopriv_uid()
    except KeyError:
        # fallback to "nobody"
        try:
            unpriv_uid = const_get_fallback_nopriv_uid()
        except KeyError:
            from entropy.exceptions import SecurityError
            raise SecurityError("cannot find unprivileged user")

    return unpriv_uid

def const_get_lazy_nopriv_gid():
    """
    This function returns an unprivileged gid by first trying to call
    const_get_entropy_nopriv_gid() and then const_get_fallback_nopriv_gid()

    @return: uid
    @rtype: int
    @raise entropy.exceptions.SecurityError: if unprivileged group id is not
        available.
    """
    unpriv_gid = None
    try:
        unpriv_gid = const_get_entropy_nopriv_gid()
    except KeyError:
        try:
            unpriv_gid = const_get_fallback_nopriv_gid()
        except KeyError:
            from entropy.exceptions import SecurityError
            raise SecurityError("cannot find unprivileged group")

    return unpriv_gid

def const_get_fallback_nopriv_gid():
    """
    Fallback function that tries to retrieve the "nogroup" group id (gid).
    It is used when const_get_entropy_nopriv_gid() fails.

    @rtype: int
    @return: nogroup user id
    @raise KeyError: when "nogroup" system GID is not available
    """
    return grp.getgrnam("nogroup").gr_gid

def _const_add_entropy_group(group_name):
    """
    This function looks for an "entropy" user group.
    If not available, it tries to create one.

    @rtype: None
    @return: None
    @raise KeyError: if ${ROOT}/etc/group is not found
    """
    group_file = etpConst['systemroot']+'/etc/group'
    if not os.path.isfile(group_file):
        raise KeyError
    ids = set()

    with codecs.open(group_file, "r", encoding=ENCODING) \
            as group_f:
        for line in group_f.readlines():
            if line and line.split(":"):
                try:
                    myid = int(line.split(":")[2])
                except ValueError:
                    pass
                ids.add(myid)
        if ids:
            # starting from 1000, get the first free
            new_id = 1000
            while True:
                new_id += 1
                if new_id not in ids:
                    break
        else:
            new_id = 10000

    with codecs.open(group_file, "a", encoding=ENCODING) \
            as group_fw:
        group_fw.seek(0, 2)
        app_line = "%s:x:%s:\n" % (group_name, new_id,)
        group_fw.write(app_line)
        group_fw.flush()

def const_get_stringtype():
    """
    Return generic string type for usage in isinstance().
    On Python 2.x, it returns basestring while on Python 3.x it returns
    (str, bytes,)
    """
    if const_is_python3():
        return (str, bytes,)
    else:
        return (basestring,)

def const_isstring(obj):
    """
    Return whether obj is a string (unicode or raw).

    @param obj: Python object
    @type obj: Python object
    @return: True, if object is string
    @rtype: bool
    """
    if const_is_python3():
        return isinstance(obj, (str, bytes))
    else:
        return isinstance(obj, basestring)

def const_isunicode(obj):
    """
    Return whether obj is a unicode.

    @param obj: Python object
    @type obj: Python object
    @return: True, if object is unicode
    @rtype: bool
    """
    if const_is_python3():
        return isinstance(obj, str)
    else:
        return isinstance(obj, unicode)

def const_israwstring(obj):
    if const_is_python3():
        return isinstance(obj, bytes)
    else:
        return isinstance(obj, str)

def const_convert_to_unicode(obj, enctype = RAW_ENCODING):
    """
    Convert generic string to unicode format, this function supports both
    Python 2.x and Python 3.x unicode bullshit.

    @param obj: generic string object
    @type obj: string
    @return: unicode string object
    @rtype: unicode object
    """

    # None support
    if obj is None:
        if const_is_python3():
            return "None"
        else:
            return unicode("None")

    # int support
    if isinstance(obj, const_get_int()):
        if const_is_python3():
            return str(obj)
        else:
            return unicode(obj)

    # buffer support
    if isinstance(obj, const_get_buffer()):
        if const_is_python3():
            return str(obj.tobytes(), enctype)
        else:
            return unicode(obj, enctype)

    # string/unicode support
    if const_isunicode(obj):
        return obj
    if hasattr(obj, 'decode'):
        return obj.decode(enctype)
    else:
        if const_is_python3():
            return str(obj, enctype)
        else:
            return unicode(obj, enctype)

def const_convert_to_rawstring(obj, from_enctype = RAW_ENCODING):
    """
    Convert generic string to raw string (str for Python 2.x or bytes for
    Python 3.x).

    @param obj: input string
    @type obj: string object
    @keyword from_enctype: encoding which string is using
    @type from_enctype: string
    @return: raw string
    @rtype: bytes
    """
    if obj is None:
        return const_convert_to_rawstring("None")
    if const_isnumber(obj):
        if const_is_python3():
            return bytes(str(obj), from_enctype)
        else:
            return str(obj)
    if isinstance(obj, const_get_buffer()):
        if const_is_python3():
            return obj.tobytes()
        else:
            return str(obj)
    if not const_isunicode(obj):
        return obj
    return obj.encode(from_enctype)

def const_get_buffer():
    """
    Return generic buffer object (supporting both Python 2.x and Python 3.x)
    """
    if const_is_python3():
        return memoryview
    else:
        return buffer

def const_get_int():
    """
    Return generic int object (supporting both Python 2.x and Python 3.x).
    For Python 2.x a (long, int) tuple is returned.
    For Python 3.x a (int,) tuple is returned.
    """
    if const_is_python3():
        return (int,)
    else:
        return (long, int,)

def const_isfileobj(obj):
    """
    Return whether obj is a file object
    """
    if const_is_python3():
        import io
        return isinstance(obj, io.IOBase)
    else:
        return isinstance(obj, file)

def const_isnumber(obj):
    """
    Return whether obj is an int, long object.
    """
    if const_is_python3():
        return isinstance(obj, int)
    else:
        return isinstance(obj, (int, long,))

def const_cmp(a, b):
    """
    cmp() is gone in Python 3.x provide our own implementation.
    """
    return (a > b) - (a < b)

_CMDLINE = None
def const_islive():
    """
    Live environments (Operating System running off a CD/DVD)
    must feature the "cdroot" parameter in kernel /proc/cmdline

    Sample code:
        >>> from entropy.const import const_islive
        >>> const_islive()
        False

    @rtype: bool
    @return: determine wether this is a Live system or not
    """
    global _CMDLINE
    if _CMDLINE is None:
        try:
            with codecs.open("/proc/cmdline", "r", encoding=ENCODING) \
                    as cmdline_f:
                _CMDLINE = cmdline_f.readline().strip().split()
        except IOError as err:
            if err.errno not in (errno.EPERM, errno.ENOENT):
                raise
            _CMDLINE = []
    return "cdroot" in _CMDLINE

def const_kill_threads(wait_seconds = 120.0):
    """
    Entropy threads killer. Even if Python threads cannot
    be stopped or killed, TimeScheduled ones can, exporting
    the kill() method.

    Sample code:
        >>> from entropy.const import const_kill_threads
        >>> const_kill_threads()

    @param wait_seconds: number of seconds thread.join() should wait
    @type wait_seconds: int
    @rtype: None
    @return: None
    """
    threads = threading.enumerate()
    for running_t in threads:
        # do not join current thread
        if running_t.getName() == 'MainThread':
            continue
        if hasattr(running_t, 'kill'):
            running_t.kill()
        if thread.get_ident() == running_t.ident:
            # do not try to kill myself
            continue
        if running_t.daemon:
            # will be killed by the VM
            continue
        running_t.join(wait_seconds) # wait n seconds?

def __const_handle_exception(etype, value, t_back):
    """
    Our default Python exception handler. It kills
    all the threads generated by Entropy before
    raising exceptions. Overloads sys.excepthook,
    internal function !!

    @param etype: exception type
    @type etype: exception type
    @param value: exception data
    @type value: string
    @param t_back: traceback object?
    @type t_back: Python traceback object
    @rtype: default Python exceptions hook
    @return: sys.__excepthook__
    """
    try:
        const_kill_threads()
    except (AttributeError, ImportError, TypeError,):
        pass
    return sys.__excepthook__(etype, value, t_back)

def const_debug_enabled():
    """
    Return whether debug is enabled.

    @return: True, if debug is enabled
    @rtype: bool
    """
    return _DEBUG

_DEBUG_W_LOCK = threading.Lock()
def const_debug_write(identifier, msg, force = False, stdout=None):
    """
    Entropy debugging output write functions.

    @param identifier: debug identifier
    @type identifier: string
    @param msg: debugging message
    @type msg: string
    @keyword force: force print even if debug mode is off
    @type force: bool
    @keyword stdout: provide an alternative stdout file object
    @type stdout: file object or None
    @rtype: None
    @return: None
    """
    if const_debug_enabled() or force:
        if stdout is None:
            stdout = sys.stdout
        # XXX: hierarchy violation, but hey, we're debugging shit
        from entropy.output import brown, purple, teal, darkgreen, darkred
        current_thread = threading.current_thread()
        th_identifier = "[id:%s, name:%s, daemon:%s, ts:%s] %s" % (
            brown(repr(current_thread.ident)),
            purple(repr(current_thread.name)),
            teal(repr(current_thread.daemon)), darkgreen(repr(time.time())),
            darkred(identifier),)
        with _DEBUG_W_LOCK:
            if const_is_python3():
                stdout.buffer.write(
                    const_convert_to_rawstring(th_identifier) + \
                        b" " + const_convert_to_rawstring(msg) + b"\n")
            else:
                stdout.write("%s: %s" % (th_identifier, msg + "\n"))
            stdout.flush()

def const_get_caller():
    """
    When called inside a function, return the caller function name.

    @return: caller function name
    @rtype: string
    """
    import inspect
    try:
        return inspect.stack()[3][3]
    except IndexError:
        return inspect.stack()[2][3]

def const_get_stack():
    """
    Return current function stack in form of list of tuples

    @return: current function stack
    @rtype: list
    """
    import inspect
    return inspect.stack()

def const_get_cpus():
    """
    Return the number of CPUs/Cores the Operating system exposes

    @return: number of CPUs/Cores available
    @rtype: int
    """
    import multiprocessing
    return multiprocessing.cpu_count()

# load config
initconfig_entropy_constants(etpSys['rootdir'])

# Debug Watchdog support. If enabled, a thread dump
# will be pushed to stderr every ETP_DEBUG_WATCHDOG_INTERVAL
# seconds (or 60 seconds if unset).
_debug_watchdog = os.getenv("ETP_DEBUG_WATCHDOG")
if _debug_watchdog is not None:
    from threading import Timer
    _default_debug_watchdog_interval = 60
    _debug_watchdog_interval = os.getenv(
        "ETP_DEBUG_WATCHDOG_INTERVAL",
        _default_debug_watchdog_interval)
    try:
        _debug_watchdog_interval = int(_debug_watchdog_interval)
    except (ValueError, TypeError):
        _debug_watchdog_interval = _default_debug_watchdog_interval

    const_debug_write(
        __name__,
        "DebugWatchdogTimer enabled, interval: %d" % (
            _debug_watchdog_interval,))

    def _dumper():
        dump_signal(None, None)
        _setup_timer()

    def _setup_timer():
        _timer = Timer(_debug_watchdog_interval, _dumper)
        _timer.name = "DebugWatchdogTimer"
        _timer.daemon = True
        _timer.start()
    _setup_timer()
