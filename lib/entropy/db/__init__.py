# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework repository database module}.
    Entropy repositories (server and client) are implemented as relational
    databases. Currently, EntropyRepository class is the object that wraps
    sqlite3 database queries and repository logic: there are no more
    abstractions between the two because there is only one implementation
    available at this time. In future, entropy.db will feature more backends
    such as MySQL embedded, SparQL, remote repositories support via TCP socket,
    etc. This will require a new layer between the repository interface now
    offered by EntropyRepository and the underlying data retrieval logic.
    Every repository interface available inherits from EntropyRepository
    class and has to reimplement its own Schema subclass and its get_init
    method (see EntropyRepository documentation for more information).

    I{EntropyRepository} is the sqlite3 implementation of the repository
    interface, as written above.

"""
import sys
import os
import hashlib
import itertools
import time
try:
    import thread
except ImportError:
    import _thread as thread
import threading
import subprocess
from sqlite3 import dbapi2

from entropy.const import etpConst, const_setup_file, \
    const_isunicode, const_convert_to_unicode, const_get_buffer, \
    const_convert_to_rawstring, const_cmp, const_pid_exists, \
    const_is_python3
from entropy.exceptions import SystemDatabaseError, \
    OperationNotPermitted, RepositoryPluginError, SPMError
from entropy.output import brown, bold, red, blue, purple, darkred, darkgreen
from entropy.cache import EntropyCacher
from entropy.spm.plugins.factory import get_default_instance as get_spm
from entropy.db.exceptions import IntegrityError, Error, OperationalError, \
    DatabaseError
from entropy.db.skel import EntropyRepositoryBase
from entropy.i18n import _
from entropy.core import Singleton

import entropy.dep
import entropy.tools
import entropy.dump

import weakref

class EntropyRepositoryCacher(Singleton):
    """
    Tiny singleton-based helper class used by EntropyRepository in order
    to keep cached items in RAM.
    """
    def init_singleton(self):
        self.__live_cache = {}

    def clear(self):
        """
        Clear all the cached items
        """
        self.__live_cache.clear()

    def clear_key(self, key):
        """
        Clear just the cached item at key (hash table).
        """
        try:
            del self.__live_cache[key]
        except KeyError:
            pass

    def keys(self):
        """
        Return a list of available cache keys
        """
        return list(self.__live_cache.keys())

    def discard(self, key):
        """
        Discard all the cache items with hash table key starting with "key".
        """
        for dkey in tuple(self.__live_cache.keys()):
            if dkey.startswith(key):
                try:
                    self.__live_cache.pop(dkey)
                except KeyError:
                    pass

    def get(self, key):
        """
        Get the cached item, if exists.
        """
        obj = self.__live_cache.get(key)
        if isinstance(obj, weakref.ref):
            return obj()
        return obj

    def set(self, key, value):
        """
        Set item in cache.
        """
        if isinstance(value, (set, frozenset)):
            self.__live_cache[key] = weakref.ref(value)
        else:
            self.__live_cache[key] = value


class EntropyRepository(EntropyRepositoryBase):

    """
    EntropyRepository implements SQLite3 based storage. In a Model-View based
    pattern, it can be considered the "model".
    Actually it's the only one available but more model backends will be
    supported in future (which will inherit this class directly).
    Beside the underlying SQLite3 calls are thread safe, you are responsible
    of the semantic of your calls.

    Every Entropy repository storage interface MUST inherit from this base
    class.
    """

    # bump this every time schema changes and databaseStructureUpdate
    # should be triggered
    _SCHEMA_REVISION = 3
    # Enable new database schema? keep it disabled for now
    _SCHEMA_2010_SUPPORT = True
    if os.getenv("ETP_REPO_DISABLE_SCHEMA_2010"):
        _SCHEMA_2010_SUPPORT = False

    _SETTING_KEYS = ("arch", "on_delete_cascade", "schema_revision",
        "_baseinfo_extrainfo_2010")

    class Schema:

        def get_init(self):
            if EntropyRepository._SCHEMA_2010_SUPPORT:
                data = """
                    CREATE TABLE baseinfo (
                        idpackage INTEGER PRIMARY KEY AUTOINCREMENT,
                        atom VARCHAR,
                        category VARCHAR,
                        name VARCHAR,
                        version VARCHAR,
                        versiontag VARCHAR,
                        revision INTEGER,
                        branch VARCHAR,
                        slot VARCHAR,
                        license VARCHAR,
                        etpapi INTEGER,
                        trigger INTEGER
                    );

                    CREATE TABLE extrainfo (
                        idpackage INTEGER PRIMARY KEY,
                        description VARCHAR,
                        homepage VARCHAR,
                        download VARCHAR,
                        size VARCHAR,
                        chost VARCHAR,
                        cflags VARCHAR,
                        cxxflags VARCHAR,
                        digest VARCHAR,
                        datecreation VARCHAR,
                        FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                    );
                """
            else:
                data = """
                    CREATE TABLE baseinfo (
                        idpackage INTEGER PRIMARY KEY AUTOINCREMENT,
                        atom VARCHAR,
                        idcategory INTEGER,
                        name VARCHAR,
                        version VARCHAR,
                        versiontag VARCHAR,
                        revision INTEGER,
                        branch VARCHAR,
                        slot VARCHAR,
                        idlicense INTEGER,
                        etpapi INTEGER,
                        trigger INTEGER
                    );

                    CREATE TABLE extrainfo (
                        idpackage INTEGER PRIMARY KEY,
                        description VARCHAR,
                        homepage VARCHAR,
                        download VARCHAR,
                        size VARCHAR,
                        idflags INTEGER,
                        digest VARCHAR,
                        datecreation VARCHAR,
                        FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                    );

                    CREATE TABLE categories (
                        idcategory INTEGER PRIMARY KEY AUTOINCREMENT,
                        category VARCHAR
                    );

                    CREATE TABLE licenses (
                        idlicense INTEGER PRIMARY KEY AUTOINCREMENT,
                        license VARCHAR
                    );

                    CREATE TABLE flags (
                        idflags INTEGER PRIMARY KEY AUTOINCREMENT,
                        chost VARCHAR,
                        cflags VARCHAR,
                        cxxflags VARCHAR
                    );
                """
            data += """
                CREATE TABLE content (
                    idpackage INTEGER,
                    file VARCHAR,
                    type VARCHAR,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE contentsafety (
                    idpackage INTEGER,
                    file VARCHAR,
                    mtime FLOAT,
                    sha256 VARCHAR,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE provide (
                    idpackage INTEGER,
                    atom VARCHAR,
                    is_default INTEGER DEFAULT 0,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE dependencies (
                    idpackage INTEGER,
                    iddependency INTEGER,
                    type INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE dependenciesreference (
                    iddependency INTEGER PRIMARY KEY AUTOINCREMENT,
                    dependency VARCHAR
                );

                CREATE TABLE conflicts (
                    idpackage INTEGER,
                    conflict VARCHAR,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE mirrorlinks (
                    mirrorname VARCHAR,
                    mirrorlink VARCHAR
                );

                CREATE TABLE sources (
                    idpackage INTEGER,
                    idsource INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE sourcesreference (
                    idsource INTEGER PRIMARY KEY AUTOINCREMENT,
                    source VARCHAR
                );

                CREATE TABLE useflags (
                    idpackage INTEGER,
                    idflag INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE useflagsreference (
                    idflag INTEGER PRIMARY KEY AUTOINCREMENT,
                    flagname VARCHAR
                );

                CREATE TABLE keywords (
                    idpackage INTEGER,
                    idkeyword INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE keywordsreference (
                    idkeyword INTEGER PRIMARY KEY AUTOINCREMENT,
                    keywordname VARCHAR
                );

                CREATE TABLE configprotect (
                    idpackage INTEGER PRIMARY KEY,
                    idprotect INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE configprotectmask (
                    idpackage INTEGER PRIMARY KEY,
                    idprotect INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE configprotectreference (
                    idprotect INTEGER PRIMARY KEY AUTOINCREMENT,
                    protect VARCHAR
                );

                CREATE TABLE systempackages (
                    idpackage INTEGER PRIMARY KEY,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE injected (
                    idpackage INTEGER PRIMARY KEY,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE installedtable (
                    idpackage INTEGER PRIMARY KEY,
                    repositoryname VARCHAR,
                    source INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE sizes (
                    idpackage INTEGER PRIMARY KEY,
                    size INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE counters (
                    counter INTEGER,
                    idpackage INTEGER,
                    branch VARCHAR,
                    PRIMARY KEY(idpackage,branch),
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE trashedcounters (
                    counter INTEGER
                );

                CREATE TABLE needed (
                    idpackage INTEGER,
                    idneeded INTEGER,
                    elfclass INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE neededreference (
                    idneeded INTEGER PRIMARY KEY AUTOINCREMENT,
                    library VARCHAR
                );

                CREATE TABLE provided_libs (
                    idpackage INTEGER,
                    library VARCHAR,
                    path VARCHAR,
                    elfclass INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE treeupdates (
                    repository VARCHAR PRIMARY KEY,
                    digest VARCHAR
                );

                CREATE TABLE treeupdatesactions (
                    idupdate INTEGER PRIMARY KEY AUTOINCREMENT,
                    repository VARCHAR,
                    command VARCHAR,
                    branch VARCHAR,
                    date VARCHAR
                );

                CREATE TABLE licensedata (
                    licensename VARCHAR UNIQUE,
                    text BLOB,
                    compressed INTEGER
                );

                CREATE TABLE licenses_accepted (
                    licensename VARCHAR UNIQUE
                );

                CREATE TABLE triggers (
                    idpackage INTEGER PRIMARY KEY,
                    data BLOB,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE entropy_misc_counters (
                    idtype INTEGER PRIMARY KEY,
                    counter INTEGER
                );

                CREATE TABLE categoriesdescription (
                    category VARCHAR,
                    locale VARCHAR,
                    description VARCHAR
                );

                CREATE TABLE packagesets (
                    setname VARCHAR,
                    dependency VARCHAR
                );

                CREATE TABLE packagechangelogs (
                    category VARCHAR,
                    name VARCHAR,
                    changelog BLOB,
                    PRIMARY KEY (category, name)
                );

                CREATE TABLE automergefiles (
                    idpackage INTEGER,
                    configfile VARCHAR,
                    md5 VARCHAR,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagedesktopmime (
                    idpackage INTEGER,
                    name VARCHAR,
                    mimetype VARCHAR,
                    executable VARCHAR,
                    icon VARCHAR,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagedownloads (
                    idpackage INTEGER,
                    download VARCHAR,
                    type VARCHAR,
                    size INTEGER,
                    disksize INTEGER,
                    md5 VARCHAR,
                    sha1 VARCHAR,
                    sha256 VARCHAR,
                    sha512 VARCHAR,
                    gpg BLOB,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE provided_mime (
                    mimetype VARCHAR,
                    idpackage INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagesignatures (
                    idpackage INTEGER PRIMARY KEY,
                    sha1 VARCHAR,
                    sha256 VARCHAR,
                    sha512 VARCHAR,
                    gpg BLOB,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagespmphases (
                    idpackage INTEGER PRIMARY KEY,
                    phases VARCHAR,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagespmrepository (
                    idpackage INTEGER PRIMARY KEY,
                    repository VARCHAR,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE entropy_branch_migration (
                    repository VARCHAR,
                    from_branch VARCHAR,
                    to_branch VARCHAR,
                    post_migration_md5sum VARCHAR,
                    post_upgrade_md5sum VARCHAR,
                    PRIMARY KEY (repository, from_branch, to_branch)
                );

                CREATE TABLE xpakdata (
                    idpackage INTEGER PRIMARY KEY,
                    data BLOB
                );

                CREATE TABLE settings (
                    setting_name VARCHAR,
                    setting_value VARCHAR,
                    PRIMARY KEY(setting_name)
                );

            """
            return data

    def __init__(self, readOnly = False, dbFile = None, xcache = False,
        name = None, indexing = True, skipChecks = False, temporary = False):
        """
        EntropyRepository constructor.

        @keyword readOnly: open file in read-only mode
        @type readOnly: bool
        @keyword dbFile: path to database to open
        @type dbFile: string
        @keyword xcache: enable on-disk cache
        @type xcache: bool
        @keyword name: repository identifier
        @type name: string
        @keyword indexing: enable database indexes
        @type indexing: bool
        @keyword skipChecks: if True, skip integrity checks
        @type skipChecks: bool
        @keyword temporary: if True, dbFile will be automatically removed
            on close()
        @type temporary: bool
        """
        self._live_cacher = EntropyRepositoryCacher()
        self.__connlock = threading.RLock()
        self.__settings_cache = {}
        self.__cursor_cache = {}
        self.__connection_cache = {}
        self._cleanup_stale_cur_conn_t = time.time()
        self.__indexing = indexing
        if name is None:
            name = etpConst['genericdbid']

        EntropyRepositoryBase.__init__(self, readOnly, xcache, temporary,
            name)

        self._db_path = dbFile
        if self._db_path is None:
            raise AttributeError("valid database path needed")

        # tracking mtime to validate repository Live cache as
        # well.
        try:
            self._cur_mtime = self.mtime()
        except OSError:
            self._cur_mtime = None

        # setup service interface
        self.__skip_checks = skipChecks

        self.__structure_update = False
        if not self.__skip_checks:

            if not entropy.tools.is_user_in_entropy_group():
                # forcing since we won't have write access to db
                self.__indexing = False
            # live systems don't like wasting RAM
            if entropy.tools.islive() and not etpConst['systemroot']:
                self.__indexing = False

            def _is_avail():
                if self._db_path == ":memory:":
                    return True
                return os.access(self._db_path, os.W_OK)

            try:
                if _is_avail() and self._doesTableExist('baseinfo') and \
                    self._doesTableExist('extrainfo'):

                    if entropy.tools.islive(): # this works
                        if etpConst['systemroot']:
                            self.__structure_update = True
                    else:
                        self.__structure_update = True

            except Error:
                self._cleanup_stale_cur_conn(kill_all = True)
                raise

        if self.__structure_update:
            self._databaseStructureUpdates()

    def readonly(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if (not self._readonly) and (self._db_path != ":memory:"):
            if os.getuid() != 0:
                # make sure that user can write to file
                # before returning False, override actual
                # readonly status
                return not os.access(self._db_path, os.W_OK)
        return self._readonly

    def setIndexing(self, indexing):
        """
        Enable or disable metadata indexing.

        @param indexing: True, to enable indexing.
        @type indexing: bool
        """
        self.__indexing = bool(indexing)

    def _get_cur_th_key(self):
        return thread.get_ident(), os.getpid()

    def _cleanup_stale_cur_conn(self, kill_all = False):

        th_ids = [x.ident for x in threading.enumerate() if x.ident]

        def kill_me(th_id, pid):
            with self.__connlock:
                cur = self.__cursor_cache.pop((th_id, pid), None)
                if cur is not None:
                    cur.close()
                conn = self.__connection_cache.pop((th_id, pid), None)

            if conn is not None:
                if not self._readonly:
                    try:
                        conn.commit()
                    except OperationalError:
                        # no transaction is active can
                        # cause this, bleh!
                        pass
                try:
                    conn.close()
                except OperationalError:
                    try:
                        conn.interrupt()
                        conn.close()
                    except OperationalError:
                        # heh, unable to close due to
                        # unfinalized statements
                        # interpreter shutdown?
                        pass

        with self.__connlock:
            th_data = set(self.__cursor_cache.keys())
            th_data |= set(self.__connection_cache.keys())
            for th_id, pid in th_data:
                do_kill = False
                if kill_all:
                    do_kill = True
                elif th_id not in th_ids:
                    do_kill = True
                elif not const_pid_exists(pid):
                    do_kill = True
                if do_kill:
                    kill_me(th_id, pid)

    def _cursor(self):

        # thanks to hotshot
        # this avoids calling _cleanup_stale_cur_conn logic zillions of time
        t1 = time.time()
        if abs(t1 - self._cleanup_stale_cur_conn_t) > 3:
            self._cleanup_stale_cur_conn()
            self._cleanup_stale_cur_conn_t = t1

        c_key = self._get_cur_th_key()
        with self.__connlock:
            cursor = self.__cursor_cache.get(c_key)
        if cursor is None:
            conn = self._connection()
            cursor = conn.cursor()
            # !!! enable foreign keys pragma !!! do not remove this
            # otherwise removePackage won't work properly
            cursor.execute("pragma foreign_keys = 1").fetchall()
            # setup temporary tables and indices storage
            # to in-memory value
            # http://www.sqlite.org/pragma.html#pragma_temp_store
            cursor.execute("pragma temp_store = 2").fetchall()
            with self.__connlock:
                self.__cursor_cache[c_key] = cursor
            # memory databases are critical because every new cursor brings
            # up a totally empty repository. So, enforce initialization.
            if self._db_path == ":memory:":
                self.initializeRepository()
        return cursor

    def _connection(self):
        self._cleanup_stale_cur_conn()
        c_key = self._get_cur_th_key()
        with self.__connlock:
            conn = self.__connection_cache.get(c_key)
        if conn is None:
            # check_same_thread still required for
            # conn.close() called from
            # arbitrary thread
            conn = dbapi2.connect(self._db_path, timeout=300.0,
                                  check_same_thread = False)
            with self.__connlock:
                self.__connection_cache[c_key] = conn
        return conn

    def __show_info(self):
        first_part = "<EntropyRepository instance at %s, %s" % (
            hex(id(self)), self._db_path,)
        second_part = ", ro: %s|%s, caching: %s, indexing: %s" % (
            self._readonly, self.readonly(), self.caching(),
            self.__indexing,)
        third_part = ", name: %s, skip_upd: %s, st_upd: %s" % (
            self.name, self.__skip_checks, self.__structure_update,)
        fourth_part = ", conn_cache: %s, cursor_cache: %s>" % (
            self.__connection_cache, self.__cursor_cache,)

        return first_part + second_part + third_part + fourth_part

    def __repr__(self):
        return self.__show_info()

    def __str__(self):
        return self.__show_info()

    def __unicode__(self):
        return self.__show_info()

    def __hash__(self):
        return id(self)

    def _setCacheSize(self, size):
        """
        Change low-level, storage engine based cache size.

        @param size: new size
        @type size: int
        """
        self._cursor().execute('PRAGMA cache_size = %s' % (size,))

    def _setDefaultCacheSize(self, size):
        """
        Change default low-level, storage engine based cache size.

        @param size: new default size
        @type size: int
        """
        self._cursor().execute('PRAGMA default_cache_size = %s' % (size,))

    def _getLiveCacheKey(self):
        return etpConst['systemroot'] + "_" + self._db_path + "_" + \
            self.name + "_"

    def _clearLiveCache(self, key):
        self._live_cacher.clear_key(self._getLiveCacheKey() + key)

    def _discardLiveCache(self):
        self._live_cacher.discard(self._getLiveCacheKey())

    def _setLiveCache(self, key, value):
        self._live_cacher.set(self._getLiveCacheKey() + key, value)

    def _getLiveCache(self, key):
        try:
            mtime = self.mtime()
        except OSError:
            mtime = None
        if self._cur_mtime != mtime:
            self._cur_mtime = mtime
            self._discardLiveCache()
        return self._live_cacher.get(self._getLiveCacheKey() + key)

    @staticmethod
    def update(entropy_client, repository_id, force, gpg):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return EntropyRepositoryBase.update(entropy_client, repository_id,
            force, gpg)

    @staticmethod
    def revision(repository_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return EntropyRepositoryBase.revision(repository_id)

    @staticmethod
    def remote_revision(repository_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return EntropyRepositoryBase.remote_revision(repository_id)

    def close(self):
        """
        Reimplemented from EntropyRepositoryBase.
        Needs to call superclass method.
        """
        super(EntropyRepository, self).close()

        self._cleanup_stale_cur_conn(kill_all = True)
        if self._temporary and (self._db_path != ":memory:") and \
            os.path.isfile(self._db_path):
            try:
                os.remove(self._db_path)
            except (OSError, IOError,):
                pass
        # live cache must be discarded every time the repository is closed
        # in order to avoid data mismatches for long-running processes
        # that load and unload Entropy Framework often.
        # like "client-updates-daemon".
        self._discardLiveCache()

    def vacuum(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("vacuum")

    def commit(self, force = False, no_plugins = False):
        """
        Reimplemented from EntropyRepositoryBase.
        Needs to call superclass method.
        """
        if force or (not self.readonly()):
            # NOTE: the actual commit MUST be executed before calling
            # the superclass method (that is going to call EntropyRepositoryBase
            # plugins). This to avoid that other connection to the same exact
            # database file are opened and used before data is actually written
            # to disk, causing a tricky race condition hard to exploit.
            # So, FIRST commit changes, then call plugins.
            try:
                self._connection().commit()
            except Error:
                pass

        super(EntropyRepository, self).commit(force = force,
            no_plugins = no_plugins)

    def rollback(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._connection().rollback()

    def initializeRepository(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        my = self.Schema()
        self.dropAllIndexes()
        for table in self._listAllTables():
            try:
                self._cursor().execute("DROP TABLE %s" % (table,))
            except OperationalError:
                # skip tables that can't be dropped
                continue
        self._cursor().executescript(my.get_init())
        self.commit()
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")
        self._setupInitialSettings()
        # set cache size
        self._setCacheSize(8192)
        self._setDefaultCacheSize(8192)
        self._databaseStructureUpdates()

        self.commit()
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")
        super(EntropyRepository, self).initializeRepository()

    def handlePackage(self, pkg_data, forcedRevision = -1,
        formattedContent = False):
        """
        Reimplemented from EntropyRepositoryBase. Raises NotImplementedError.
        Subclasses have to reimplement this.
        @raise NotImplementedError: guess what, you need to implement this.
        """
        raise NotImplementedError()

    def addPackage(self, pkg_data, revision = -1, package_id = None,
        do_commit = True, formatted_content = False):
        """
        Reimplemented from EntropyRepositoryBase.
        Needs to call superclass method.
        """
        try:
            return self._addPackage(pkg_data, revision = revision,
                package_id = package_id, do_commit = do_commit,
                formatted_content = formatted_content)
        except:
            self._connection().rollback()
            raise

    def _addPackage(self, pkg_data, revision = -1, package_id = None,
        do_commit = True, formatted_content = False):
        """
        Reimplemented from EntropyRepositoryBase.
        Needs to call superclass method.
        """
        if revision == -1:
            try:
                revision = int(pkg_data['revision'])
            except (KeyError, ValueError):
                pkg_data['revision'] = 0 # revision not specified
                revision = 0
        elif 'revision' not in pkg_data:
            pkg_data['revision'] = revision

        _baseinfo_extrainfo_2010 = self._isBaseinfoExtrainfo2010()
        catid = None
        licid = None
        idflags = None
        if not _baseinfo_extrainfo_2010:
            # create new category if it doesn't exist
            catid = self._isCategoryAvailable(pkg_data['category'])
            if catid == -1:
                catid = self._addCategory(pkg_data['category'])

            # create new license if it doesn't exist
            licid = self._isLicenseAvailable(pkg_data['license'])
            if licid == -1:
                licid = self._addLicense(pkg_data['license'])

            idflags = self._areCompileFlagsAvailable(pkg_data['chost'],
                pkg_data['cflags'], pkg_data['cxxflags'])
            if idflags == -1:
                idflags = self._addCompileFlags(pkg_data['chost'],
                    pkg_data['cflags'], pkg_data['cxxflags'])


        idprotect = self._isProtectAvailable(pkg_data['config_protect'])
        if idprotect == -1:
            idprotect = self._addProtect(pkg_data['config_protect'])

        idprotect_mask = self._isProtectAvailable(
            pkg_data['config_protect_mask'])
        if idprotect_mask == -1:
            idprotect_mask = self._addProtect(pkg_data['config_protect_mask'])

        trigger = 0
        if pkg_data['trigger']:
            trigger = 1

        # baseinfo
        pkgatom = entropy.dep.create_package_atom_string(
            pkg_data['category'], pkg_data['name'], pkg_data['version'],
            pkg_data['versiontag'])
        # add atom metadatum
        pkg_data['atom'] = pkgatom

        if not _baseinfo_extrainfo_2010:
            mybaseinfo_data = (pkgatom, catid, pkg_data['name'],
                pkg_data['version'], pkg_data['versiontag'], revision,
                pkg_data['branch'], pkg_data['slot'],
                licid, pkg_data['etpapi'], trigger,
            )
        else:
            mybaseinfo_data = (pkgatom, pkg_data['category'], pkg_data['name'],
                pkg_data['version'], pkg_data['versiontag'], revision,
                pkg_data['branch'], pkg_data['slot'],
                pkg_data['license'], pkg_data['etpapi'], trigger,
            )

        mypackage_id_string = 'NULL'
        if isinstance(package_id, int):

            manual_deps = self.retrieveManualDependencies(package_id,
                resolve_conditional_deps = False)

            # does it exist?
            self.removePackage(package_id, do_cleanup = False,
                do_commit = False, from_add_package = True)
            mypackage_id_string = '?'
            mybaseinfo_data = (package_id,)+mybaseinfo_data

            # merge old manual dependencies
            dep_dict = pkg_data['dependencies']
            for manual_dep in manual_deps:
                if manual_dep in dep_dict:
                    continue
                dep_dict[manual_dep] = \
                    etpConst['dependency_type_ids']['mdepend_id']

        else:
            # force to None
            package_id = None

        cur = self._cursor().execute("""
        INSERT INTO baseinfo VALUES (%s,?,?,?,?,?,?,?,?,?,?,?)""" % (
            mypackage_id_string,), mybaseinfo_data)
        if package_id is None:
            package_id = cur.lastrowid

        # extrainfo
        if not _baseinfo_extrainfo_2010:
            self._cursor().execute(
                'INSERT INTO extrainfo VALUES (?,?,?,?,?,?,?,?)',
                (   package_id,
                    pkg_data['description'],
                    pkg_data['homepage'],
                    pkg_data['download'],
                    pkg_data['size'],
                    idflags,
                    pkg_data['digest'],
                    pkg_data['datecreation'],
                )
            )
        else:
            self._cursor().execute(
                'INSERT INTO extrainfo VALUES (?,?,?,?,?,?,?,?,?,?)',
                (   package_id,
                    pkg_data['description'],
                    pkg_data['homepage'],
                    pkg_data['download'],
                    pkg_data['size'],
                    pkg_data['chost'],
                    pkg_data['cflags'],
                    pkg_data['cxxflags'],
                    pkg_data['digest'],
                    pkg_data['datecreation'],
                )
            )
        # baseinfo and extrainfo are tainted
        self.clearCache()
        ### other information iserted below are not as
        ### critical as these above

        # tables using a select
        self._insertNeeded(package_id, pkg_data['needed'])
        self.insertDependencies(package_id, pkg_data['dependencies'])
        self._insertSources(package_id, pkg_data['sources'])
        self._insertUseflags(package_id, pkg_data['useflags'])
        self._insertKeywords(package_id, pkg_data['keywords'])
        self._insertLicenses(pkg_data['licensedata'])
        self._insertMirrors(pkg_data['mirrorlinks'])

        # packages and file association metadata
        desktop_mime = pkg_data.get('desktop_mime')
        if desktop_mime:
            self._insertDesktopMime(package_id, desktop_mime)
        provided_mime = pkg_data.get('provided_mime')
        if provided_mime:
            self._insertProvidedMime(package_id, provided_mime)

        # package ChangeLog
        if pkg_data.get('changelog'):
            self._insertChangelog(pkg_data['category'], pkg_data['name'],
                pkg_data['changelog'])
        # package signatures
        if pkg_data.get('signatures'):
            signatures = pkg_data['signatures']
            sha1, sha256, sha512, gpg = signatures['sha1'], \
                signatures['sha256'], signatures['sha512'], \
                signatures.get('gpg')
            self._insertSignatures(package_id, sha1, sha256, sha512,
                gpg = gpg)

        # extra package download URLs
        if pkg_data.get('extra_download'):
            extra_download = pkg_data['extra_download']
            self._insertExtraDownload(package_id, extra_download)

        if pkg_data.get('provided_libs'):
            self._insertProvidedLibraries(package_id, pkg_data['provided_libs'])

        # spm phases
        if pkg_data.get('spm_phases') is not None:
            self._insertSpmPhases(package_id, pkg_data['spm_phases'])

        if pkg_data.get('spm_repository') is not None:
            self._insertSpmRepository(package_id, pkg_data['spm_repository'])

        # not depending on other tables == no select done
        self.insertContent(package_id, pkg_data['content'],
            already_formatted = formatted_content)
        # insert content safety metadata (checksum, mtime), if metadatum exists
        content_safety = pkg_data.get('content_safety')
        if content_safety is not None:
            self._insertContentSafety(package_id, content_safety)

        # handle SPM UID<->package_id binding
        pkg_data['counter'] = int(pkg_data['counter'])
        if not pkg_data['injected'] and (pkg_data['counter'] != -1):
            pkg_data['counter'] = self._bindSpmPackageUid(
                package_id, pkg_data['counter'], pkg_data['branch'])

        self._insertOnDiskSize(package_id, pkg_data['disksize'])
        if pkg_data['trigger']:
            self._insertTrigger(package_id, pkg_data['trigger'])
        self._insertConflicts(package_id, pkg_data['conflicts'])

        if "provide_extended" not in pkg_data:
            self._insertProvide(package_id, pkg_data['provide'])
        else:
            self._insertProvide(package_id, pkg_data['provide_extended'])

        self._insertConfigProtect(package_id, idprotect)
        self._insertConfigProtect(package_id, idprotect_mask, mask = True)
        # injected?
        if pkg_data.get('injected'):
            self.setInjected(package_id, do_commit = False)
        # is it a system package?
        if pkg_data.get('systempackage'):
            self._setSystemPackage(package_id, do_commit = False)

        # this will always be optional ! (see entropy.client.interfaces.package)
        original_repository = pkg_data.get('original_repository')
        if original_repository is not None:
            self.storeInstalledPackage(package_id, original_repository)

        # baseinfo and extrainfo are tainted
        # ensure that cache is clear even here
        self.clearCache()

        if do_commit:
            self.commit()

        super(EntropyRepository, self).addPackage(pkg_data, revision = revision,
            package_id = package_id, do_commit = do_commit,
            formatted_content = formatted_content)

        return package_id

    def removePackage(self, package_id, do_cleanup = True, do_commit = True,
        from_add_package = False):
        """
        Reimplemented from EntropyRepositoryBase.
        Needs to call superclass method.
        """
        try:
            return self._removePackage(package_id, do_cleanup = do_cleanup,
                do_commit = do_commit, from_add_package = from_add_package)
        except:
            self._connection().rollback()
            raise

    def _removePackage(self, package_id, do_cleanup = True, do_commit = True,
        from_add_package = False):
        """
        Reimplemented from EntropyRepositoryBase.
        Needs to call superclass method.
        """
        self.clearCache()
        super(EntropyRepository, self).removePackage(package_id,
            do_cleanup = do_cleanup, do_commit = do_commit,
            from_add_package = from_add_package)
        self.clearCache()

        try:
            new_way = self.getSetting("on_delete_cascade")
        except KeyError:
            new_way = ''
        # TODO: remove this before 31-12-2011 (deprecate)
        if new_way:
            # this will work thanks to ON DELETE CASCADE !
            self._cursor().execute(
                "DELETE FROM baseinfo WHERE idpackage = (?)", (package_id,))
        else:
            r_tup = (package_id,)*20
            self._cursor().executescript("""
                DELETE FROM baseinfo WHERE idpackage = %d;
                DELETE FROM extrainfo WHERE idpackage = %d;
                DELETE FROM dependencies WHERE idpackage = %d;
                DELETE FROM provide WHERE idpackage = %d;
                DELETE FROM conflicts WHERE idpackage = %d;
                DELETE FROM configprotect WHERE idpackage = %d;
                DELETE FROM configprotectmask WHERE idpackage = %d;
                DELETE FROM sources WHERE idpackage = %d;
                DELETE FROM useflags WHERE idpackage = %d;
                DELETE FROM keywords WHERE idpackage = %d;
                DELETE FROM content WHERE idpackage = %d;
                DELETE FROM counters WHERE idpackage = %d;
                DELETE FROM sizes WHERE idpackage = %d;
                DELETE FROM needed WHERE idpackage = %d;
                DELETE FROM triggers WHERE idpackage = %d;
                DELETE FROM systempackages WHERE idpackage = %d;
                DELETE FROM injected WHERE idpackage = %d;
                DELETE FROM installedtable WHERE idpackage = %d;
                DELETE FROM packagedesktopmime WHERE idpackage = %d;
                DELETE FROM provided_mime WHERE idpackage = %d;
            """ % r_tup)
            # Added on Aug. 2011
            if self._doesTableExist("packagedownloads"):
                self._cursor().execute("""
                DELETE FROM packagedownloads WHERE idpackage = (?)""",
                (package_id,))

        if do_cleanup:
            # Cleanups if at least one package has been removed
            self.clean()

        if do_commit:
            self.commit()

    def _removeMirrorEntries(self, mirrorname):
        """
        Remove source packages mirror entries from database for the given
        mirror name. This is a representation of Portage's "thirdpartymirrors".

        @param mirrorname: mirror name
        @type mirrorname: string
        """
        self._cursor().execute("""
        DELETE FROM mirrorlinks WHERE mirrorname = (?)
        """, (mirrorname,))

    def _addMirrors(self, mirrorname, mirrorlist):
        """
        Add source package mirror entry to database.
        This is a representation of Portage's "thirdpartymirrors".

        @param mirrorname: name of the mirror from which "mirrorlist" belongs
        @type mirrorname: string
        @param mirrorlist: list of URLs belonging to the given mirror name
        @type mirrorlist: list
        """
        self._cursor().executemany("""
        INSERT into mirrorlinks VALUES (?,?)
        """, [(mirrorname, x,) for x in mirrorlist])

    def _addCategory(self, category):
        """
        NOTE: only working with _baseinfo_extrainfo_2010 disabled

        Add package category string to repository. Return its identifier
        (idcategory).

        @param category: name of the category to add
        @type category: string
        @return: category identifier (idcategory)
        @rtype: int
        """
        cur = self._cursor().execute("""
        INSERT into categories VALUES (NULL,?)
        """, (category,))
        self._clearLiveCache("retrieveCategory")
        self._clearLiveCache("searchNameCategory")
        self._clearLiveCache("retrieveKeySlot")
        self._clearLiveCache("retrieveKeySplit")
        self._clearLiveCache("searchKeySlot")
        self._clearLiveCache("searchKeySlotTag")
        self._clearLiveCache("retrieveKeySlotAggregated")
        self._clearLiveCache("getStrictData")
        return cur.lastrowid

    def _addProtect(self, protect):
        """
        Add a single, generic CONFIG_PROTECT (not defined as _MASK/whatever
        here) path. Return its identifier (idprotect).

        @param protect: CONFIG_PROTECT path to add
        @type protect: string
        @return: protect identifier (idprotect)
        @rtype: int
        """
        cur = self._cursor().execute("""
        INSERT into configprotectreference VALUES (NULL,?)
        """, (protect,))
        return cur.lastrowid

    def _addSource(self, source):
        """
        Add source code package download path to repository. Return its
        identifier (idsource).

        @param source: source package download path
        @type source: string
        @return: source identifier (idprotect)
        @rtype: int
        """
        cur = self._cursor().execute("""
        INSERT into sourcesreference VALUES (NULL,?)
        """, (source,))
        return cur.lastrowid

    def _addDependency(self, dependency):
        """
        Add dependency string to repository. Return its identifier
        (iddependency).

        @param dependency: dependency string
        @type dependency: string
        @return: dependency identifier (iddependency)
        @rtype: int
        """
        cur = self._cursor().execute("""
        INSERT into dependenciesreference VALUES (NULL,?)
        """, (dependency,))
        return cur.lastrowid

    def _addKeyword(self, keyword):
        """
        Add package SPM keyword string to repository.
        Return its identifier (idkeyword).

        @param keyword: keyword string
        @type keyword: string
        @return: keyword identifier (idkeyword)
        @rtype: int
        """
        cur = self._cursor().execute("""
        INSERT into keywordsreference VALUES (NULL,?)
        """, (keyword,))
        return cur.lastrowid

    def _addUseflag(self, useflag):
        """
        Add package USE flag string to repository.
        Return its identifier (iduseflag).

        @param useflag: useflag string
        @type useflag: string
        @return: useflag identifier (iduseflag)
        @rtype: int
        """
        self._clearLiveCache("retrieveUseflags")
        cur = self._cursor().execute("""
        INSERT into useflagsreference VALUES (NULL,?)
        """, (useflag,))
        return cur.lastrowid

    def _addNeeded(self, needed):
        """
        Add package libraries' ELF object NEEDED string to repository.
        Return its identifier (idneeded).

        @param needed: NEEDED string (as shown in `readelf -d elf.so`) 
        @type needed: string
        @return: needed identifier (idneeded)
        @rtype: int
        """
        cur = self._cursor().execute("""
        INSERT into neededreference VALUES (NULL,?)
        """, (needed,))
        return cur.lastrowid

    def _addLicense(self, pkglicense):
        """
        NOTE: only working with _baseinfo_extrainfo_2010 disabled

        Add package license name string to repository.
        Return its identifier (idlicense).

        @param pkglicense: license name string
        @type pkglicense: string
        @return: license name identifier (idlicense)
        @rtype: int
        """
        if not entropy.tools.is_valid_string(pkglicense):
            pkglicense = ' ' # workaround for broken license entries
        cur = self._cursor().execute("""
        INSERT into licenses VALUES (NULL,?)
        """, (pkglicense,))
        return cur.lastrowid

    def _addCompileFlags(self, chost, cflags, cxxflags):
        """
        NOTE: only working with _baseinfo_extrainfo_2010 disabled

        Add package Compiler flags used to repository.
        Return its identifier (idflags).

        @param chost: CHOST string
        @type chost: string
        @param cflags: CFLAGS string
        @type cflags: string
        @param cxxflags: CXXFLAGS string
        @type cxxflags: string
        @return: Compiler flags triple identifier (idflags)
        @rtype: int
        """
        cur = self._cursor().execute("""
        INSERT into flags VALUES (NULL,?,?,?)
        """, (chost, cflags, cxxflags,))
        return cur.lastrowid

    def _setSystemPackage(self, package_id, do_commit = True):
        """
        Mark a package as system package, which means that entropy.client
        will deny its removal.

        @param package_id: package identifier
        @type package_id: int
        @keyword do_commit: determine whether executing commit or not
        @type do_commit: bool
        """
        self._cursor().execute("""
        INSERT into systempackages VALUES (?)
        """, (package_id,))
        if do_commit:
            self.commit()

    def setInjected(self, package_id, do_commit = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not self.isInjected(package_id):
            self._cursor().execute("""
            INSERT into injected VALUES (?)
            """, (package_id,))
        if do_commit:
            self.commit()

    def setCreationDate(self, package_id, date):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE extrainfo SET datecreation = (?) WHERE idpackage = (?)
        """, (str(date), package_id,))
        self.commit()

    def setDigest(self, package_id, digest):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE extrainfo SET digest = (?) WHERE idpackage = (?)
        """, (digest, package_id,))
        self._clearLiveCache("retrieveDigest")
        self.commit()

    def setSignatures(self, package_id, sha1, sha256, sha512, gpg = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE packagesignatures SET sha1 = (?), sha256 = (?), sha512 = (?),
        gpg = (?) WHERE idpackage = (?)
        """, (sha1, sha256, sha512, gpg, package_id))

    def setDownloadURL(self, package_id, url):
        """
        Set download URL prefix for package.

        @param package_id: package indentifier
        @type package_id: int
        @param url: URL prefix to set
        @type url: string
        """
        self._cursor().execute("""
        UPDATE extrainfo SET download = (?) WHERE idpackage = (?)
        """, (url, package_id,))
        self.commit()

    def setCategory(self, package_id, category):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if self._isBaseinfoExtrainfo2010():
            self._cursor().execute("""
            UPDATE baseinfo SET category = (?) WHERE idpackage = (?)
            """, (category, package_id,))
        else:
            # create new category if it doesn't exist
            catid = self._isCategoryAvailable(category)
            if catid == -1:
                # create category
                catid = self._addCategory(category)
            self._cursor().execute("""
            UPDATE baseinfo SET idcategory = (?) WHERE idpackage = (?)
            """, (catid, package_id,))

        self._clearLiveCache("retrieveCategory")
        self._clearLiveCache("searchNameCategory")
        self._clearLiveCache("retrieveKeySlot")
        self._clearLiveCache("retrieveKeySplit")
        self._clearLiveCache("searchKeySlot")
        self._clearLiveCache("searchKeySlotTag")
        self._clearLiveCache("retrieveKeySlotAggregated")
        self._clearLiveCache("getStrictData")
        self.commit()

    def setCategoryDescription(self, category, description_data):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM categoriesdescription WHERE category = (?)
        """, (category,))
        for locale in description_data:
            mydesc = description_data[locale]
            self._cursor().execute("""
            INSERT INTO categoriesdescription VALUES (?,?,?)
            """, (category, locale, mydesc,))

        self.commit()

    def setName(self, package_id, name):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET name = (?) WHERE idpackage = (?)
        """, (name, package_id,))
        self._clearLiveCache("searchNameCategory")
        self._clearLiveCache("retrieveKeySlot")
        self._clearLiveCache("retrieveKeySplit")
        self._clearLiveCache("searchKeySlot")
        self._clearLiveCache("searchKeySlotTag")
        self._clearLiveCache("retrieveKeySlotAggregated")
        self._clearLiveCache("getStrictData")
        self.commit()

    def setDependency(self, iddependency, dependency):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE dependenciesreference SET dependency = (?)
        WHERE iddependency = (?)
        """, (dependency, iddependency,))
        self.commit()

    def setAtom(self, package_id, atom):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET atom = (?) WHERE idpackage = (?)
        """, (atom, package_id,))
        self._clearLiveCache("searchNameCategory")
        self._clearLiveCache("getStrictScopeData")
        self._clearLiveCache("getStrictData")
        self.commit()

    def setSlot(self, package_id, slot):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET slot = (?) WHERE idpackage = (?)
        """, (slot, package_id,))
        self._clearLiveCache("retrieveSlot")
        self._clearLiveCache("retrieveKeySlot")
        self._clearLiveCache("searchKeySlot")
        self._clearLiveCache("searchKeySlotTag")
        self._clearLiveCache("retrieveKeySlotAggregated")
        self._clearLiveCache("getStrictScopeData")
        self._clearLiveCache("getStrictData")
        self.commit()

    def setRevision(self, package_id, revision):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET revision = (?) WHERE idpackage = (?)
        """, (revision, package_id,))
        self._clearLiveCache("retrieveRevision")
        self._clearLiveCache("getVersioningData")
        self._clearLiveCache("getStrictScopeData")
        self._clearLiveCache("getStrictData")
        self.commit()

    def removeDependencies(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM dependencies WHERE idpackage = (?)
        """, (package_id,))
        self.commit()

    def insertDependencies(self, package_id, depdata):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        dcache = set()
        add_dep = self._addDependency
        is_dep_avail = self._isDependencyAvailable

        deps = []
        for dep in depdata:
            if dep in dcache:
                continue
            iddep = is_dep_avail(dep)
            if iddep == -1:
                iddep = add_dep(dep)

            deptype = 0
            if isinstance(depdata, dict):
                deptype = depdata[dep]

            dcache.add(dep)
            deps.append((package_id, iddep, deptype,))

        del dcache

        self._cursor().executemany("""
        INSERT into dependencies VALUES (?,?,?)
        """, deps)

    def insertContent(self, package_id, content, already_formatted = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if already_formatted:
            self._cursor().executemany("""
            INSERT INTO content VALUES (?,?,?)
            """, [(package_id, x, y,) for a, x, y in content])
        else:
            self._cursor().executemany("""
            INSERT INTO content VALUES (?,?,?)
            """, [(package_id, x, content[x],) for x in content])

    def _insertContentSafety(self, package_id, content_safety):
        """
        Currently supported: sha256, mtime.
        Insert into contentsafety table package files sha256sum and mtime.
        """
        if self._doesTableExist("contentsafety"):
            self._cursor().executemany("""
            INSERT into contentsafety VALUES (?,?,?,?)
            """, [(package_id, k, v['mtime'], v['sha256']) for k, v in \
                content_safety.items()])

    def _insertProvidedLibraries(self, package_id, libs_metadata):
        """
        Insert library metadata owned by package.

        @param package_id: package indentifier
        @type package_id: int
        @param libs_metadata: provided library metadata composed by list of
            tuples of length 3 containing library name, path and ELF class.
        @type libs_metadata: list
        """
        self._cursor().executemany("""
        INSERT INTO provided_libs VALUES (?,?,?,?)
        """, [(package_id, x, y, z,) for x, y, z in libs_metadata])

    def insertAutomergefiles(self, package_id, automerge_data):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().executemany('INSERT INTO automergefiles VALUES (?,?,?)',
            [(package_id, x, y,) for x, y in automerge_data])

    def _insertChangelog(self, category, name, changelog_txt):
        """
        Insert package changelog for package (in this case using category +
        name as key).

        @param category: package category
        @type category: string
        @param name: package name
        @type name: string
        @param changelog_txt: changelog text
        @type changelog_txt: string
        """
        mytxt = changelog_txt.encode('raw_unicode_escape')

        self._cursor().execute("""
        DELETE FROM packagechangelogs WHERE category = (?) AND name = (?)
        """, (category, name,))

        self._cursor().execute("""
        INSERT INTO packagechangelogs VALUES (?,?,?)
        """, (category, name, const_get_buffer()(mytxt),))

    def _insertLicenses(self, licenses_data):
        """
        insert license data (license names and text) into repository.

        @param licenses_data: dictionary containing license names as keys and
            text as values
        @type licenses_data: dict
        """

        mylicenses = list(licenses_data.keys())
        def my_mf(mylicense):
            return not self.isLicenseDataKeyAvailable(mylicense)

        def my_mm(mylicense):

            lic_data = licenses_data.get(mylicense, '')

            # support both utf8 and str input
            if const_isunicode(lic_data): # encode to str
                try:
                    lic_data = lic_data.encode('raw_unicode_escape')
                except (UnicodeDecodeError,):
                    lic_data = lic_data.encode('utf-8')

            return (mylicense, const_get_buffer()(lic_data), 0,)

        # set() used after filter to remove duplicates
        self._cursor().executemany("""
        INSERT into licensedata VALUES (?,?,?)
        """, list(map(my_mm, set(filter(my_mf, mylicenses)))))

    def _insertConfigProtect(self, package_id, idprotect, mask = False):
        """
        Insert CONFIG_PROTECT (configuration files protection) entry identifier
        for package. This entry is usually a space separated string of directory
        and files which are used to handle user-protected configuration files
        or directories, those that are going to be stashed in separate paths
        waiting for user merge decisions.

        @param package_id: package indentifier
        @type package_id: int
        @param idprotect: configuration files protection identifier
        @type idprotect: int
        @keyword mask: if True, idproctect will be considered a "mask" entry,
            meaning that configuration files starting with paths referenced
            by idprotect will be forcefully merged.
        @type mask: bool
        """

        mytable = 'configprotect'
        if mask:
            mytable += 'mask'
        self._cursor().execute("""
        INSERT into %s VALUES (?,?)
        """ % (mytable,), (package_id, idprotect,))

    def _insertMirrors(self, mirrors):
        """
        Insert list of "mirror name" and "mirror list" into repository.
        The term "mirror" in this case references to Source Package Manager
        package download mirrors.
        Argument format is like this for historical reasons and may change in
        future.

        @todo: change argument format
        @param mirrors: list of tuples of length 2 containing string as first
            item and list as second.
            [('openoffice', ['http://openoffice1', 'http://..."],), ...]
        @type mirrors: list
        """

        for mirrorname, mirrorlist in mirrors:
            # remove old
            self._removeMirrorEntries(mirrorname)
            # add new
            self._addMirrors(mirrorname, mirrorlist)

    def _insertKeywords(self, package_id, keywords):
        """
        Insert keywords for package. Keywords are strings contained in package
        metadata stating what architectures or subarchitectures are supported
        by package. It is historically used also for masking packages (making
        them not available).

        @param package_id: package indentifier
        @type package_id: int
        @param keywords: list of keywords
        @type keywords: list
        """

        def mymf(key):
            idkeyword = self._isKeywordAvailable(key)
            if idkeyword == -1:
                # create category
                idkeyword = self._addKeyword(key)
            return (package_id, idkeyword,)

        self._cursor().executemany("""
        INSERT into keywords VALUES (?,?)
        """, list(map(mymf, keywords)))

    def _insertUseflags(self, package_id, useflags):
        """
        Insert Source Package Manager USE (components build) flags for package.

        @param package_id: package indentifier
        @type package_id: int
        @param useflags: list of use flags strings
        @type useflags: list
        """

        def mymf(flag):
            iduseflag = self._isUseflagAvailable(flag)
            if iduseflag == -1:
                # create category
                iduseflag = self._addUseflag(flag)
            return (package_id, iduseflag,)

        self._cursor().executemany("""
        INSERT into useflags VALUES (?,?)
        """, list(map(mymf, useflags)))
        self._clearLiveCache("retrieveUseflags")

    def _insertSignatures(self, package_id, sha1, sha256, sha512, gpg = None):
        """
        Insert package file extra hashes (sha1, sha256, sha512) for package.

        @param package_id: package indentifier
        @type package_id: int
        @param sha1: SHA1 hash for package file
        @type sha1: string
        @param sha256: SHA256 hash for package file
        @type sha256: string
        @param sha512: SHA512 hash for package file
        @type sha512: string
        @keyword gpg: GPG signature file content
        @type gpg: string
        """
        try:
            # be optimistic and delay if condition, _doesColumnInTableExist
            # is really slow
            self._cursor().execute("""
            INSERT INTO packagesignatures VALUES (?,?,?,?,?)
            """, (package_id, sha1, sha256, sha512, gpg))
        except OperationalError:
            # perhaps, gpg column does not exist, check now
            if self._doesColumnInTableExist("packagesignatures", "gpg"):
                # something is really wrong, and it's not about our cols
                raise
            # fallback to old instert (without gpg table)
            self._cursor().execute("""
            INSERT INTO packagesignatures VALUES (?,?,?,?)
            """, (package_id, sha1, sha256, sha512))

    def _insertExtraDownload(self, package_id, package_downloads_data):
        """
        Insert extra package files download objects to repository.

        @param package_id: package indentifier
        @type package_id: int
        @param package_downloads_data: list of dict composed by
            (download, type, size, md5, sha1, sha256, sha512, gpg) as keys
        @type package_downloads_data: list
        """
        def _do_insert():
            self._cursor().executemany("""
            INSERT INTO packagedownloads VALUES (?,?,?,?,?,?,?,?,?,?)
            """, [(package_id, edw['download'], edw['type'], edw['size'],
                    edw['disksize'], edw['md5'], edw['sha1'], edw['sha256'],
                    edw['sha512'], edw['gpg']) for edw in \
                        package_downloads_data])

        try:
            # be optimistic and delay if condition
            _do_insert()
        except OperationalError:
            if self._doesTableExist("packagedownloads"):
                raise
            self._createPackageDownloadsTable()
            _do_insert()

    def _insertDesktopMime(self, package_id, metadata):
        """
        Insert file association information for package.

        @param package_id: package indentifier
        @type package_id: int
        @param metadata: list of dict() containing file association metadata
        @type metadata: list
        """
        mime_data = [(package_id, x['name'], x['mimetype'], x['executable'],
            x['icon']) for x in metadata]
        self._cursor().executemany("""
        INSERT INTO packagedesktopmime VALUES (?,?,?,?,?)""", mime_data)

    def _insertProvidedMime(self, package_id, mimetypes):
        """
        Insert file association information for package in a way useful for
        making direct and inverse queries (having a mimetype or having a
        package identifier)

        @param package_id: package indentifier
        @type package_id: int
        @param mimetypes: list of mimetypes supported by package
        @type mimetypes: list
        """
        self._cursor().executemany("""
        INSERT INTO provided_mime VALUES (?,?)""",
            [(x, package_id) for x in mimetypes])

    def _insertSpmPhases(self, package_id, phases):
        """
        Insert Source Package Manager phases for package.
        Entropy can call several Source Package Manager (the PM which Entropy
        relies on) package installation/removal phases.
        Such phase names are listed here.

        @param package_id: package indentifier
        @type package_id: int
        @param phases: list of available Source Package Manager phases
        @type phases: list
        """
        self._cursor().execute("""
        INSERT INTO packagespmphases VALUES (?,?)
        """, (package_id, phases,))

    def _insertSpmRepository(self, package_id, repository):
        """
        Insert Source Package Manager repository for package.
        This medatatum describes the source repository where package has
        been compiled from.

        @param package_id: package indentifier
        @type package_id: int
        @param repository: Source Package Manager repository
        @type repository: string
        """
        self._cursor().execute("""
        INSERT INTO packagespmrepository VALUES (?,?)
        """, (package_id, repository,))

    def _insertSources(self, package_id, sources):
        """
        Insert source code package download URLs for package_id.

        @param package_id: package indentifier
        @type package_id: int
        @param sources: list of source URLs
        @type sources: list
        """
        def mymf(source):

            if (not source) or \
            (not entropy.tools.is_valid_string(source)):
                return 0

            idsource = self._isSourceAvailable(source)
            if idsource == -1:
                idsource = self._addSource(source)

            return (package_id, idsource,)

        self._cursor().executemany("""
        INSERT into sources VALUES (?,?)
        """, [x for x in map(mymf, sources) if x != 0])

    def _insertConflicts(self, package_id, conflicts):
        """
        Insert dependency conflicts for package.

        @param package_id: package indentifier
        @type package_id: int
        @param conflicts: list of dep. conflicts
        @type conflicts: list
        """
        self._cursor().executemany("""
        INSERT into conflicts VALUES (?,?)
        """, [(package_id, x,) for x in conflicts])

    def _insertProvide(self, package_id, provides):
        """
        Insert PROVIDE metadata for package_id.
        This has been added for supporting Portage Source Package Manager
        old-style meta-packages support.
        Packages can provide extra atoms, you can see it like aliases, where
        these can be given by multiple packages. This allowed to make available
        multiple applications providing the same functionality which depending
        packages can reference, without forcefully being bound to a single
        package.

        @param package_id: package indentifier
        @type package_id: int
        @param provides: list of atom strings
        @type provides: list
        """
        default_provides = [x for x in provides if x[1]]

        self._cursor().executemany("""
        INSERT into provide VALUES (?,?,?)
        """, [(package_id, x, y,) for x, y in provides])

        if default_provides:
            # reset previously set default provides
            self._cursor().executemany("""
            UPDATE provide SET is_default=0 WHERE atom = (?) AND
            idpackage != (?)
            """, default_provides)

    def _insertNeeded(self, package_id, neededs):
        """
        Insert package libraries' ELF object NEEDED string for package.
        Return its identifier (idneeded).

        @param package_id: package indentifier
        @type package_id: int
        @param neededs: list of NEEDED string (as shown in `readelf -d elf.so`)
        @type neededs: string
        """
        def mymf(needed_data):
            needed, elfclass = needed_data
            idneeded = self.isNeededAvailable(needed)
            if idneeded == -1:
                idneeded = self._addNeeded(needed)
            return (package_id, idneeded, elfclass,)

        self._cursor().executemany("""
        INSERT into needed VALUES (?,?,?)
        """, list(map(mymf, neededs)))

    def _insertOnDiskSize(self, package_id, mysize):
        """
        Insert on-disk size (bytes) for package.

        @param package_id: package indentifier
        @type package_id: int
        @param mysize: package size (bytes)
        @type mysize: int
        """
        self._cursor().execute("""
        INSERT into sizes VALUES (?,?)
        """, (package_id, mysize,))

    def _insertTrigger(self, package_id, trigger):
        """
        Insert built-in trigger script for package, containing
        pre-install, post-install, pre-remove, post-remove hooks.
        This feature should be considered DEPRECATED, and kept for convenience.
        Please use Source Package Manager features if possible.

        @param package_id: package indentifier
        @type package_id: int
        @param trigger: trigger file dump
        @type trigger: string
        """
        self._cursor().execute("""
        INSERT into triggers VALUES (?,?)
        """, (package_id, const_get_buffer()(trigger),))

    def insertBranchMigration(self, repository, from_branch, to_branch,
        post_migration_md5sum, post_upgrade_md5sum):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        INSERT OR REPLACE INTO entropy_branch_migration VALUES (?,?,?,?,?)
        """, (
                repository, from_branch,
                to_branch, post_migration_md5sum,
                post_upgrade_md5sum,
            )
        )

    def setBranchMigrationPostUpgradeMd5sum(self, repository, from_branch,
        to_branch, post_upgrade_md5sum):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE entropy_branch_migration SET post_upgrade_md5sum = (?) WHERE
        repository = (?) AND from_branch = (?) AND to_branch = (?)
        """, (post_upgrade_md5sum, repository, from_branch, to_branch,))


    def _bindSpmPackageUid(self, package_id, spm_package_uid, branch):
        """
        Bind Source Package Manager package identifier ("COUNTER" metadata
        for Portage) to Entropy package.
        If uid <= -2, a new negative UID will be allocated and returned.
        Negative UIDs are considered auto-allocated by Entropy.
        This is mainly used for binary packages not belonging to any SPM
        packages which are just "injected" inside the repository.

        @param package_id: package indentifier
        @type package_id: int
        @param spm_package_uid: Source package Manager unique package identifier
        @type spm_package_uid: int
        @param branch: current running Entropy branch
        @type branch: string
        @return: uid set
        @rtype: int
        """

        my_uid = spm_package_uid

        if my_uid <= -2:
            # special cases
            my_uid = self.getFakeSpmUid()

        try:
            self._cursor().execute('INSERT into counters VALUES (?,?,?)',
                (my_uid, package_id, branch,))
        except IntegrityError:
            # we have a PRIMARY KEY we need to remove
            self._migrateCountersTable()
            self._cursor().execute('INSERT into counters VALUES (?,?,?)',
                (my_uid, package_id, branch,))

        return my_uid

    def insertSpmUid(self, package_id, spm_package_uid):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        branch = self._settings['repositories']['branch']

        self._cursor().execute("""
        DELETE FROM counters WHERE (counter = (?) OR
        idpackage = (?)) AND branch = (?);
        """, (spm_package_uid, package_id, branch,))
        self._cursor().execute("""
        INSERT INTO counters VALUES (?,?,?);
        """, (spm_package_uid, package_id, branch,))

        self.commit()

    def setTrashedUid(self, spm_package_uid):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        INSERT OR REPLACE INTO trashedcounters VALUES (?)
        """, (spm_package_uid,))

    def setSpmUid(self, package_id, spm_package_uid, branch = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        branchstring = ''
        insertdata = (spm_package_uid, package_id)
        if branch:
            branchstring = ', branch = (?)'
            insertdata += (branch,)

        self._cursor().execute("""
        UPDATE or REPLACE counters SET counter = (?) %s
        WHERE idpackage = (?)""" % (branchstring,), insertdata)

        self.commit()

    def setContentSafety(self, package_id, content_safety):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM contentsafety where idpackage = (?)
        """, (package_id,))
        self._insertContentSafety(package_id, content_safety)

    def contentDiff(self, package_id, dbconn, dbconn_package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if self is dbconn:
            raise AttributeError("cannot diff inside the same db")

        content = set((x,) for x in dbconn.retrieveContent(dbconn_package_id))

        # setup random table name
        random_str = "%svs%s_%s" % (package_id, id(dbconn),
            dbconn_package_id)
        if const_is_python3():
            random_str = const_convert_to_rawstring(random_str)
        randomtable = "cdiff%s" % (hashlib.md5(random_str).hexdigest(),)

        # create random table
        self._cursor().executescript("""
            DROP TABLE IF EXISTS `%s`;
            CREATE TEMPORARY TABLE `%s` ( file VARCHAR );
            """ % (randomtable, randomtable,)
        )

        try:

            self._cursor().executemany("""
            INSERT INTO `%s` VALUES (?)""" % (randomtable,), content)

            # remove this when the one in retrieveContent will be removed
            self._connection().text_factory = const_convert_to_unicode

            # now compare
            cur = self._cursor().execute("""
            SELECT file FROM content 
            WHERE content.idpackage = (?) AND 
            content.file NOT IN (SELECT file from `%s`)""" % (randomtable,),
                (package_id,))

            # suck back
            return self._cur2frozenset(cur)

        finally:
            self._cursor().execute('DROP TABLE IF EXISTS `%s`' % (randomtable,))

    def clean(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cleanupUseflags()
        self._cleanupSources()
        self._cleanupNeeded()
        self._cleanupDependencies()
        self._cleanupChangelogs()

    def _cleanupUseflags(self):
        """
        Cleanup "USE flags" metadata unused references to save space.
        """
        self._cursor().execute("""
        DELETE FROM useflagsreference
        WHERE idflag NOT IN (SELECT idflag FROM useflags)""")

    def _cleanupSources(self):
        """
        Cleanup "sources" metadata unused references to save space.
        """
        self._cursor().execute("""
        DELETE FROM sourcesreference
        WHERE idsource NOT IN (SELECT idsource FROM sources)""")

    def _cleanupNeeded(self):
        """
        Cleanup "needed" metadata unused references to save space.
        """
        self._cursor().execute("""
        DELETE FROM neededreference
        WHERE idneeded NOT IN (SELECT idneeded FROM needed)""")

    def _cleanupDependencies(self):
        """
        Cleanup "dependencies" metadata unused references to save space.
        """
        self._cursor().execute("""
        DELETE FROM dependenciesreference
        WHERE iddependency NOT IN (SELECT iddependency FROM dependencies)
        """)

    def _cleanupChangelogs(self):
        """
        Cleanup "changelog" metadata unused references to save space.
        """
        if self._isBaseinfoExtrainfo2010():
            self._cursor().execute("""
            DELETE FROM packagechangelogs
            WHERE category || "/" || name NOT IN
            (SELECT baseinfo.category || "/" || baseinfo.name FROM baseinfo)
            """)
        else:
            self._cursor().execute("""
            DELETE FROM packagechangelogs
            WHERE category || "/" || name NOT IN
            (SELECT categories.category || "/" || baseinfo.name
                FROM baseinfo, categories
                WHERE baseinfo.idcategory = categories.idcategory)
            """)

    def getFakeSpmUid(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        try:
            cur = self._cursor().execute('SELECT min(counter) FROM counters')
            dbcounter = cur.fetchone()
        except Error:
            # first available counter
            return -2

        counter = 0
        if dbcounter:
            counter = dbcounter[0]

        if (counter >= -1) or (counter is None):
            counter = -2
        else:
            counter -= 1

        return counter

    def getApi(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute('SELECT max(etpapi) FROM baseinfo')
        api = cur.fetchone()
        if api:
            return api[0]
        return -1

    def getDependency(self, iddependency):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT dependency FROM dependenciesreference WHERE iddependency = (?)
        LIMIT 1
        """, (iddependency,))
        dep = cur.fetchone()
        if dep:
            return dep[0]

    def getPackageIds(self, atom):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo WHERE atom = (?)
        """, (atom,))
        return self._cur2frozenset(cur)

    def getPackageIdFromDownload(self, download_relative_path,
        endswith = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if endswith:
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM baseinfo,extrainfo
            WHERE extrainfo.download LIKE (?) AND
            baseinfo.idpackage = extrainfo.idpackage
            LIMIT 1
            """, ("%"+download_relative_path,))
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM baseinfo,extrainfo
            WHERE extrainfo.download = (?) AND
            baseinfo.idpackage = extrainfo.idpackage
            LIMIT 1
            """, (download_relative_path,))

        package_id = cur.fetchone()
        if package_id:
            return package_id[0]
        return -1

    def getVersioningData(self, package_id): 
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("getVersioningData")
        if cached is None:
            cur = self._cursor().execute("""
            SELECT idpackage, version, versiontag, revision FROM baseinfo
            """)
            cached = dict((pkg_id, (ver, tag, rev)) for pkg_id, ver, tag,
                rev in cur.fetchall())
            self._setLiveCache("getVersioningData", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def getStrictData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("getStrictData")
        if cached is None:
            if self._isBaseinfoExtrainfo2010():
                cur = self._cursor().execute("""
                SELECT idpackage, category || "/" || name, slot, version,
                    versiontag, revision, atom FROM baseinfo
                """)
            else:
                # we must guarantee backward compatibility
                cur = self._cursor().execute("""
                SELECT baseinfo.idpackage, categories.category || "/" ||
                    baseinfo.name, baseinfo.slot, baseinfo.version,
                    baseinfo.versiontag, baseinfo.revision, baseinfo.atom
                FROM baseinfo, categories
                WHERE baseinfo.idcategory = categories.idcategory
                """)
            cached = dict((pkg_id, (key, slot, version, tag, rev, atom)) for
                pkg_id, key, slot, version, tag, rev, atom in cur.fetchall())
            self._setLiveCache("getStrictData", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def getStrictScopeData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("getStrictScopeData")
        if cached is None:
            cur = self._cursor().execute("""
            SELECT idpackage, atom, slot, revision FROM baseinfo
            """)
            cached = dict((pkg_id, (atom, slot, rev)) for pkg_id, atom, slot,
                rev in cur.fetchall())
            self._setLiveCache("getStrictScopeData", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def getScopeData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if self._isBaseinfoExtrainfo2010():
            cur = self._cursor().execute("""
            SELECT atom, category, name, version, slot, versiontag,
                revision, branch, etpapi FROM baseinfo
            WHERE baseinfo.idpackage = (?)""", (package_id,))
        else:
            # we must guarantee backward compatibility
            cur = self._cursor().execute("""
            SELECT
                baseinfo.atom,
                categories.category,
                baseinfo.name,
                baseinfo.version,
                baseinfo.slot,
                baseinfo.versiontag,
                baseinfo.revision,
                baseinfo.branch,
                baseinfo.etpapi
            FROM
                baseinfo,
                categories
            WHERE
                baseinfo.idpackage = (?)
                and baseinfo.idcategory = categories.idcategory
            """, (package_id,))
        return cur.fetchone()

    def getBaseData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if self._isBaseinfoExtrainfo2010():
            sql = """
            SELECT
                baseinfo.atom,
                baseinfo.name,
                baseinfo.version,
                baseinfo.versiontag,
                extrainfo.description,
                baseinfo.category,
                extrainfo.chost,
                extrainfo.cflags,
                extrainfo.cxxflags,
                extrainfo.homepage,
                baseinfo.license,
                baseinfo.branch,
                extrainfo.download,
                extrainfo.digest,
                baseinfo.slot,
                baseinfo.etpapi,
                extrainfo.datecreation,
                extrainfo.size,
                baseinfo.revision
            FROM
                baseinfo,
                extrainfo
            WHERE
                baseinfo.idpackage = (?)
                AND baseinfo.idpackage = extrainfo.idpackage
            """
        else:
            sql = """
            SELECT
                baseinfo.atom,
                baseinfo.name,
                baseinfo.version,
                baseinfo.versiontag,
                extrainfo.description,
                categories.category,
                flags.chost,
                flags.cflags,
                flags.cxxflags,
                extrainfo.homepage,
                licenses.license,
                baseinfo.branch,
                extrainfo.download,
                extrainfo.digest,
                baseinfo.slot,
                baseinfo.etpapi,
                extrainfo.datecreation,
                extrainfo.size,
                baseinfo.revision
            FROM
                baseinfo,
                extrainfo,
                categories,
                flags,
                licenses
            WHERE
                baseinfo.idpackage = (?)
                and baseinfo.idpackage = extrainfo.idpackage
                and baseinfo.idcategory = categories.idcategory
                and extrainfo.idflags = flags.idflags
                and baseinfo.idlicense = licenses.idlicense
            """
        cur = self._cursor().execute(sql, (package_id,))
        return cur.fetchone()

    def _cur2frozenset(self, cur):
        mycontent = set()
        for x in cur:
            mycontent |= set(x)
        return frozenset(mycontent)

    def _cur2tuple(self, cur):
        return tuple(itertools.chain.from_iterable(cur))

    def clearCache(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._live_cacher.clear()
        super(EntropyRepository, self).clearCache()
        self._live_cacher.clear()

    def retrieveRepositoryUpdatesDigest(self, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT digest FROM treeupdates WHERE repository = (?) LIMIT 1
        """, (repository,))

        mydigest = cur.fetchone()
        if mydigest:
            return mydigest[0]
        return -1

    def listAllTreeUpdatesActions(self, no_ids_repos = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if no_ids_repos:
            cur = self._cursor().execute("""
            SELECT command, branch, date FROM treeupdatesactions
            """)
        else:
            cur = self._cursor().execute("""
            SELECT idupdate, repository, command, branch, date
            FROM treeupdatesactions
            """)
        return tuple(cur)

    def retrieveTreeUpdatesActions(self, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        params = (repository,)

        cur = self._cursor().execute("""
        SELECT command FROM treeupdatesactions WHERE 
        repository = (?) order by date""", params)
        return self._cur2tuple(cur)

    def bumpTreeUpdatesActions(self, updates):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('DELETE FROM treeupdatesactions')
        self._cursor().executemany("""
        INSERT INTO treeupdatesactions VALUES (?,?,?,?,?)
        """, updates)
        self.commit()

    def removeTreeUpdatesActions(self, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM treeupdatesactions WHERE repository = (?)
        """, (repository,))
        self.commit()

    def insertTreeUpdatesActions(self, updates, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        myupdates = [[repository]+list(x) for x in updates]
        self._cursor().executemany("""
        INSERT INTO treeupdatesactions VALUES (NULL,?,?,?,?)
        """, myupdates)
        self.commit()

    def setRepositoryUpdatesDigest(self, repository, digest):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM treeupdates where repository = (?)
        """, (repository,))
        self._cursor().execute("""
        INSERT INTO treeupdates VALUES (?,?)
        """, (repository, digest,))

    def addRepositoryUpdatesActions(self, repository, actions, branch):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        mytime = str(time.time())
        myupdates = [
            (repository, x, branch, mytime,) for x in actions \
            if not self._doesTreeupdatesActionExist(repository, x, branch)
        ]
        self._cursor().executemany("""
        INSERT INTO treeupdatesactions VALUES (NULL,?,?,?,?)
        """, myupdates)

    def _doesTreeupdatesActionExist(self, repository, command, branch):
        """
        This method should be considered internal and not suited for general
        audience.
        Return whether provided "treeupdates" action in repository with
        provided branch exists.

        @param repository: repository identifier
        @type repository: string
        @param command: treeupdates command
        @type command: string
        @param branch: branch metadata bound to command argument value given
        @type branch: string
        @return: if True, provided treeupdates action already exists
        @rtype: bool
        """
        cur = self._cursor().execute("""
        SELECT * FROM treeupdatesactions 
        WHERE repository = (?) and command = (?)
        and branch = (?)""", (repository, command, branch,))

        result = cur.fetchone()
        if result:
            return True
        return False

    def clearPackageSets(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('DELETE FROM packagesets')

    def insertPackageSets(self, sets_data):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        mysets = []
        for setname in sorted(sets_data):
            for dependency in sorted(sets_data[setname]):
                try:
                    mysets.append((const_convert_to_unicode(setname),
                        const_convert_to_unicode(dependency),))
                except (UnicodeDecodeError, UnicodeEncodeError,):
                    continue

        self._cursor().executemany('INSERT INTO packagesets VALUES (?,?)',
            mysets)

    def retrievePackageSets(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("SELECT setname, dependency FROM packagesets")
        data = cur.fetchall()

        sets = {}
        for setname, dependency in data:
            obj = sets.setdefault(setname, set())
            obj.add(dependency)
        return sets

    def retrievePackageSet(self, setname):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT dependency FROM packagesets WHERE setname = (?)""",
            (setname,))
        return self._cur2frozenset(cur)

    def retrieveAtom(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT atom FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        atom = cur.fetchone()
        if atom:
            return atom[0]

    def retrieveBranch(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT branch FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        branch = cur.fetchone()
        if branch:
            return branch[0]

    def retrieveTrigger(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT data FROM triggers WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        trigger = cur.fetchone()
        if not trigger:
            # backward compatibility with <=0.52.x
            return const_convert_to_rawstring('')
        return const_convert_to_rawstring(trigger[0])

    def retrieveDownloadURL(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT download FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        download = cur.fetchone()
        if download:
            return download[0]

    def retrieveDescription(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT description FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        description = cur.fetchone()
        if description:
            return description[0]

    def retrieveHomepage(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT homepage FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        home = cur.fetchone()
        if home:
            return home[0]

    def retrieveSpmUid(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT counters.counter FROM counters,baseinfo
        WHERE counters.idpackage = (?) AND
        baseinfo.idpackage = counters.idpackage AND
        baseinfo.branch = counters.branch LIMIT 1
        """, (package_id,))
        mycounter = cur.fetchone()
        if mycounter:
            return mycounter[0]
        return -1

    def retrieveSize(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT size FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        size = cur.fetchone()
        if size:
            try:
                return int(size[0])
            except ValueError: # wtf?
                return 0

    def retrieveOnDiskSize(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT size FROM sizes WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        size = cur.fetchone()
        if size:
            return size[0]
        return 0

    def retrieveDigest(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("retrieveDigest")
        if cached is None:
            cur = self._cursor().execute("""
            SELECT idpackage, digest FROM extrainfo
            """)
            cached = dict(cur)
            self._setLiveCache("retrieveDigest", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def retrieveSignatures(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        try:
            cur = self._cursor().execute("""
            SELECT sha1, sha256, sha512, gpg FROM packagesignatures
            WHERE idpackage = (?) LIMIT 1
            """, (package_id,))
            data = cur.fetchone()
        except OperationalError:
            # TODO: remove this before 31-12-2011
            cur = self._cursor().execute("""
            SELECT sha1, sha256, sha512 FROM packagesignatures
            WHERE idpackage = (?) LIMIT 1
            """, (package_id,))
            data = cur.fetchone() + (None,)

        if data:
            return data
        return None, None, None, None

    def retrieveExtraDownload(self, package_id, down_type = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        down_type_str = ""
        params = [package_id]
        if down_type is not None:
            down_type_str = " AND down_type = (?)"
            params.append(down_type)

        try:
            cur = self._cursor().execute("""
            SELECT download, type, size, disksize, md5, sha1,
                sha256, sha512, gpg
            FROM packagedownloads WHERE idpackage = (?)
            """ + down_type_str, params)
        except OperationalError:
            if self._doesTableExist("packagedownloads"):
                raise
            return tuple()

        result = []
        for download, d_type, size, d_size, md5, sha1, sha256, sha512, gpg in \
            cur.fetchall():
            result.append({
                "download": download,
                "type": d_type,
                "size": size,
                "disksize": d_size,
                "md5": md5,
                "sha1": sha1,
                "sha256": sha256,
                "sha512": sha512,
                "gpg": gpg,
            })
        return tuple(result)

    def retrieveName(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT name FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        name = cur.fetchone()
        if name:
            return name[0]

    def retrieveKeySplit(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("retrieveKeySplit")
        if cached is None:
            if self._isBaseinfoExtrainfo2010():
                cur = self._cursor().execute("""
                SELECT idpackage, category, name FROM baseinfo
                """)
            else:
                cur = self._cursor().execute("""
                SELECT baseinfo.idpackage, categories.category, baseinfo.name
                FROM baseinfo, categories
                WHERE categories.idcategory = baseinfo.idcategory
                """)
            cached = dict((pkg_id, (category, name)) for pkg_id, category,
                name in cur.fetchall())
            self._setLiveCache("retrieveKeySplit", cached)

        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def retrieveKeySlot(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("retrieveKeySlot")
        if cached is None:
            if self._isBaseinfoExtrainfo2010():
                cur = self._cursor().execute("""
                SELECT idpackage, category || "/" || name, slot FROM baseinfo
                """)
            else:
                cur = self._cursor().execute("""
                SELECT baseinfo.idpackage,
                    categories.category || "/" || baseinfo.name, baseinfo.slot
                FROM baseinfo, categories
                WHERE baseinfo.idcategory = categories.idcategory
                """)
            cached = dict((pkg_id, (key, slot)) for pkg_id, key, slot in \
                cur.fetchall())
            self._setLiveCache("retrieveKeySlot", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def retrieveKeySlotAggregated(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("retrieveKeySlotAggregated")
        if cached is None:
            if self._isBaseinfoExtrainfo2010():
                cur = self._cursor().execute("""
                SELECT idpackage, category || "/" || name || "%s" || slot
                FROM baseinfo
                """ % (etpConst['entropyslotprefix'],))
            else:
                cur = self._cursor().execute("""
                SELECT baseinfo.idpackage, categories.category || "/" ||
                    baseinfo.name || "%s" || baseinfo.slot
                FROM baseinfo, categories
                WHERE baseinfo.idcategory = categories.idcategory
                """ % (etpConst['entropyslotprefix'],))
            cached = dict((pkg_id, key) for pkg_id, key in cur.fetchall())
            self._setLiveCache("retrieveKeySlotAggregated", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def retrieveKeySlotTag(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if self._isBaseinfoExtrainfo2010():
            cur = self._cursor().execute("""
            SELECT category || "/" || name, slot,
            versiontag FROM baseinfo WHERE
            idpackage = (?) LIMIT 1
            """, (package_id,))
        else:
            cur = self._cursor().execute("""
            SELECT categories.category || "/" || baseinfo.name, baseinfo.slot,
            baseinfo.versiontag FROM baseinfo, categories WHERE
            baseinfo.idpackage = (?) AND
            baseinfo.idcategory = categories.idcategory LIMIT 1
            """, (package_id,))
        return cur.fetchone()

    def retrieveVersion(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("retrieveVersion")
        if cached is None:
            cur = self._cursor().execute("""
            SELECT idpackage, version FROM baseinfo
            """)
            cached = dict(cur)
            self._setLiveCache("retrieveVersion", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def retrieveRevision(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("retrieveRevision")
        if cached is None:
            cur = self._cursor().execute("""
            SELECT idpackage, revision FROM baseinfo
            """)
            cached = dict(cur)
            self._setLiveCache("retrieveRevision", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def retrieveCreationDate(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT datecreation FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        date = cur.fetchone()
        if date:
            return date[0]

    def retrieveApi(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT etpapi FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        api = cur.fetchone()
        if api:
            return api[0]

    def retrieveUseflags(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("retrieveUseflags")
        if cached is None:
            cur = self._cursor().execute("""
            SELECT useflags.idpackage, useflagsreference.flagname
            FROM useflags, useflagsreference
            WHERE useflags.idflag = useflagsreference.idflag
            """)
            cached = {}
            for pkg_id, flag in cur.fetchall():
                obj = cached.setdefault(pkg_id, set())
                obj.add(flag)
            self._setLiveCache("retrieveUseflags", cached)
        # avoid python3.x memleak
        obj = frozenset(cached.get(package_id, frozenset()))
        del cached
        return obj

    def retrieveSpmPhases(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT phases FROM packagespmphases WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        spm_phases = cur.fetchone()

        if spm_phases:
            return spm_phases[0]

    def retrieveSpmRepository(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT repository FROM packagespmrepository
        WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        spm_repo = cur.fetchone()

        if spm_repo:
            return spm_repo[0]

    def retrieveDesktopMime(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not self._doesTableExist("packagedesktopmime"):
            return []

        cur = self._cursor().execute("""
        SELECT name, mimetype, executable, icon FROM packagedesktopmime
        WHERE idpackage = (?)""", (package_id,))
        data = []
        for row in cur.fetchall():
            item = {}
            item['name'], item['mimetype'], item['executable'], \
                item['icon'] = row
            data.append(item)
        return data

    def retrieveProvidedMime(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not self._doesTableExist("provided_mime"):
            return frozenset()

        cur = self._cursor().execute("""
        SELECT mimetype FROM provided_mime WHERE idpackage = (?)""",
        (package_id,))
        return self._cur2frozenset(cur)

    def retrieveNeededRaw(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT library FROM needed,neededreference
        WHERE needed.idpackage = (?) AND
        needed.idneeded = neededreference.idneeded""", (package_id,))
        return self._cur2frozenset(cur)

    def retrieveNeeded(self, package_id, extended = False, formatted = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if extended:

            cur = self._cursor().execute("""
            SELECT library,elfclass FROM needed,neededreference
            WHERE needed.idpackage = (?) AND
            needed.idneeded = neededreference.idneeded ORDER BY library
            """, (package_id,))
            needed = tuple(cur)

        else:

            cur = self._cursor().execute("""
            SELECT library FROM needed,neededreference
            WHERE needed.idpackage = (?) AND
            needed.idneeded = neededreference.idneeded ORDER BY library
            """, (package_id,))
            needed = self._cur2tuple(cur)

        if extended and formatted:
            return dict((lib, elfclass,) for lib, elfclass in needed)
        return needed

    def retrieveProvidedLibraries(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT library, path, elfclass FROM provided_libs
        WHERE idpackage = (?)
        """, (package_id,))
        return frozenset(cur)

    def retrieveConflicts(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT conflict FROM conflicts WHERE idpackage = (?)
        """, (package_id,))
        return self._cur2frozenset(cur)

    def retrieveProvide(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        try:
            # be optimistic, _doesColumnInTableExist is very slow.
            cur = self._cursor().execute("""
            SELECT atom,is_default FROM provide WHERE idpackage = (?)
            """, (package_id,))
        except OperationalError:
            # TODO: remove this before 31-12-2011
            if self._doesColumnInTableExist("provide", "is_default"):
                # something is really wrong
                raise
            cur = self._cursor().execute("""
            SELECT atom,0 FROM provide WHERE idpackage = (?)
            """, (package_id,))

        return frozenset(cur)

    def retrieveDependenciesList(self, package_id, exclude_deptypes = None,
        resolve_conditional_deps = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        excluded_deptypes_query = ""
        if exclude_deptypes is not None:
            for dep_type in exclude_deptypes:
                excluded_deptypes_query += " AND dependencies.type != %d" % (
                    dep_type,)

        cur = self._cursor().execute("""
        SELECT dependenciesreference.dependency
        FROM dependencies, dependenciesreference
        WHERE dependencies.idpackage = (?) AND
        dependencies.iddependency = dependenciesreference.iddependency %s
        UNION SELECT "!" || conflict FROM conflicts
        WHERE idpackage = (?)""" % (excluded_deptypes_query,),
        (package_id, package_id,))
        if resolve_conditional_deps:
            return frozenset(entropy.dep.expand_dependencies(cur, [self]))
        else:
            return self._cur2frozenset(cur)

    def retrieveBuildDependencies(self, package_id, extended = False,
        resolve_conditional_deps = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return self.retrieveDependencies(package_id, extended = extended,
            deptype = etpConst['dependency_type_ids']['bdepend_id'],
            resolve_conditional_deps = resolve_conditional_deps)

    def retrieveRuntimeDependencies(self, package_id, extended = False,
        resolve_conditional_deps = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return self.retrieveDependencies(package_id, extended = extended,
            deptype = etpConst['dependency_type_ids']['rdepend_id'],
            resolve_conditional_deps = resolve_conditional_deps)

    def retrievePostDependencies(self, package_id, extended = False,
        resolve_conditional_deps = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return self.retrieveDependencies(package_id, extended = extended,
            deptype = etpConst['dependency_type_ids']['pdepend_id'],
            resolve_conditional_deps = resolve_conditional_deps)

    def retrieveManualDependencies(self, package_id, extended = False,
        resolve_conditional_deps = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return self.retrieveDependencies(package_id, extended = extended,
            deptype = etpConst['dependency_type_ids']['mdepend_id'],
            resolve_conditional_deps = resolve_conditional_deps)

    def retrieveDependencies(self, package_id, extended = False, deptype = None,
        exclude_deptypes = None, resolve_conditional_deps = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        searchdata = (package_id,)

        depstring = ''
        if deptype is not None:
            depstring = 'and dependencies.type = (?)'
            searchdata += (deptype,)

        excluded_deptypes_query = ""
        if exclude_deptypes is not None:
            for dep_type in exclude_deptypes:
                excluded_deptypes_query += " AND dependencies.type != %d" % (
                    dep_type,)

        if extended:
            cur = self._cursor().execute("""
            SELECT dependenciesreference.dependency,dependencies.type
            FROM dependencies,dependenciesreference
            WHERE dependencies.idpackage = (?) AND
            dependencies.iddependency =
            dependenciesreference.iddependency %s %s""" % (
                depstring, excluded_deptypes_query,), searchdata)
            return tuple(entropy.dep.expand_dependencies(cur, [self]))
        else:
            cur = self._cursor().execute("""
            SELECT dependenciesreference.dependency
            FROM dependencies,dependenciesreference
            WHERE dependencies.idpackage = (?) AND
            dependencies.iddependency =
            dependenciesreference.iddependency %s %s""" % (
                depstring, excluded_deptypes_query,), searchdata)
            return frozenset(entropy.dep.expand_dependencies(cur, [self]))

    def retrieveKeywords(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT keywordname FROM keywords,keywordsreference
        WHERE keywords.idpackage = (?) AND
        keywords.idkeyword = keywordsreference.idkeyword""", (package_id,))
        return self._cur2frozenset(cur)

    def retrieveProtect(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT protect FROM configprotect,configprotectreference
        WHERE configprotect.idpackage = (?) AND
        configprotect.idprotect = configprotectreference.idprotect
        LIMIT 1
        """, (package_id,))

        protect = cur.fetchone()
        if protect:
            return protect[0]
        return ''

    def retrieveProtectMask(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT protect FROM configprotectmask,configprotectreference 
        WHERE idpackage = (?) AND
        configprotectmask.idprotect = configprotectreference.idprotect
        """, (package_id,))

        protect = cur.fetchone()
        if protect:
            return protect[0]
        return ''

    def retrieveSources(self, package_id, extended = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT sourcesreference.source FROM sources, sourcesreference
        WHERE idpackage = (?) AND
        sources.idsource = sourcesreference.idsource
        """, (package_id,))
        sources = self._cur2frozenset(cur)
        if not extended:
            return sources

        source_data = {}
        mirror_str = "mirror://"
        for source in sources:

            source_data[source] = set()
            if source.startswith(mirror_str):

                mirrorname = source.split("/")[2]
                # avoid leading "/"
                mirror_url =  source.split("/", 3)[3:][0].lstrip("/")
                source_data[source] |= set(
                    [url.rstrip("/") + "/" + mirror_url for url in \
                        self.retrieveMirrorData(mirrorname)])

            else:
                source_data[source].add(source)

        return source_data

    def retrieveAutomergefiles(self, package_id, get_dict = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # like portage does
        self._connection().text_factory = const_convert_to_unicode

        cur = self._cursor().execute("""
        SELECT configfile, md5 FROM automergefiles WHERE idpackage = (?)
        """, (package_id,))
        data = frozenset(cur)

        if get_dict:
            data = dict(((x, y,) for x, y in data))
        return data

    def retrieveContent(self, package_id, extended = False,
        formatted = False, insert_formatted = False, order_by = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        extstring = ''
        if extended:
            extstring = ",type"
        extstring_package_id = ''
        if insert_formatted:
            extstring_package_id = 'idpackage,'

        searchkeywords = (package_id,)
        order_by_string = ''
        if order_by is not None:
            if order_by not in ("package_id", "idpackage", "file", "type",):
                raise AttributeError("invalid order_by argument")
            if order_by == "package_id":
                order_by = "idpackage"
            order_by_string = ' order by %s' % (order_by,)

        did_try = False
        while True:
            try:

                cur = self._cursor().execute("""
                SELECT %s file%s FROM content WHERE idpackage = (?) %s""" % (
                    extstring_package_id, extstring, order_by_string,),
                    searchkeywords)

                if extended and insert_formatted:
                    fl = tuple(cur)

                elif extended and formatted:
                    fl = {}
                    items = cur.fetchone()
                    while items:
                        fl[items[0]] = items[1]
                        items = cur.fetchone()

                elif extended:
                    fl = tuple(cur)

                else:
                    if order_by:
                        fl = self._cur2tuple(cur)
                    else:
                        fl = self._cur2frozenset(cur)

                break

            except OperationalError:

                if did_try:
                    raise
                did_try = True

                # TODO: remove this before 31-12-2011
                # Support for old entropy db entries, which were
                # not inserted in utf-8
                self._connection().text_factory = const_convert_to_unicode
                continue

        return fl

    def retrieveContentSafety(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # TODO: remove this before 31-12-2012
        if not self._doesTableExist('contentsafety'):
            return {}

        cur = self._cursor().execute("""
        SELECT file, sha256, mtime from contentsafety WHERE idpackage = (?)
        """, (package_id,))
        return dict((path, {'sha256': sha256, 'mtime': mtime}) for path, \
            sha256, mtime in cur.fetchall())

    def retrieveChangelog(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if self._isBaseinfoExtrainfo2010():
            cur = self._cursor().execute("""
            SELECT packagechangelogs.changelog
            FROM packagechangelogs, baseinfo
            WHERE baseinfo.idpackage = (?) AND
            packagechangelogs.category = baseinfo.category AND
            packagechangelogs.name = baseinfo.name
            LIMIT 1
            """, (package_id,))
        else:
            cur = self._cursor().execute("""
            SELECT packagechangelogs.changelog
            FROM packagechangelogs, baseinfo, categories
            WHERE baseinfo.idpackage = (?) AND
            baseinfo.idcategory = categories.idcategory AND
            packagechangelogs.name = baseinfo.name AND
            packagechangelogs.category = categories.category
            LIMIT 1
            """, (package_id,))
        changelog = cur.fetchone()
        if changelog:
            changelog = changelog[0]
            try:
                return const_convert_to_unicode(changelog)
            except UnicodeDecodeError:
                return const_convert_to_unicode(changelog, enctype = 'utf-8')

    def retrieveChangelogByKey(self, category, name):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._connection().text_factory = const_convert_to_unicode

        cur = self._cursor().execute("""
        SELECT changelog FROM packagechangelogs WHERE category = (?) AND
        name = (?) LIMIT 1
        """, (category, name,))

        changelog = cur.fetchone()
        if changelog:
            return const_convert_to_unicode(changelog[0])

    def retrieveSlot(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("retrieveSlot")
        if cached is None:
            cur = self._cursor().execute("""
            SELECT idpackage, slot FROM baseinfo
            """)
            cached = dict(cur)
            self._setLiveCache("retrieveSlot", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def retrieveTag(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("retrieveTag")
        # gain 2% speed on atomMatch()
        if cached is None:
            cur = self._cursor().execute("""
            SELECT idpackage, versiontag FROM baseinfo
            """)
            cached = dict(cur)
            self._setLiveCache("retrieveTag", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def retrieveMirrorData(self, mirrorname):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT mirrorlink FROM mirrorlinks WHERE mirrorname = (?)
        """, (mirrorname,))
        return self._cur2frozenset(cur)

    def retrieveCategory(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("retrieveCategory")
        # this gives 14% speed boost in atomMatch()
        if cached is None:
            if self._isBaseinfoExtrainfo2010():
                cur = self._cursor().execute("""
                SELECT idpackage, category FROM baseinfo
                """)
            else:
                cur = self._cursor().execute("""
                SELECT baseinfo.idpackage, categories.category
                FROM baseinfo,categories WHERE
                baseinfo.idcategory = categories.idcategory
                """)
            cached = dict(cur)
            self._setLiveCache("retrieveCategory", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def retrieveCategoryDescription(self, category):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT description, locale FROM categoriesdescription
        WHERE category = (?)
        """, (category,))

        return dict((locale, desc,) for desc, locale in cur.fetchall())

    def retrieveLicenseData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        licenses = self.retrieveLicense(package_id)
        if licenses is None:
            return {}

        licdata = {}
        for licname in licenses.split():

            if not licname.strip():
                continue

            if not entropy.tools.is_valid_string(licname):
                continue

            cur = self._cursor().execute("""
            SELECT text FROM licensedata WHERE licensename = (?) LIMIT 1
            """, (licname,))
            lictext = cur.fetchone()
            if lictext is not None:
                lictext = lictext[0]
                try:
                    licdata[licname] = const_convert_to_unicode(lictext)
                except UnicodeDecodeError:
                    licdata[licname] = \
                        const_convert_to_unicode(lictext, enctype = 'utf-8')

        return licdata

    def retrieveLicenseDataKeys(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        licenses = self.retrieveLicense(package_id)
        if licenses is None:
            return frozenset()

        licdata = set()
        for licname in licenses.split():

            if not licname.strip():
                continue

            if not entropy.tools.is_valid_string(licname):
                continue

            cur = self._cursor().execute("""
            SELECT licensename FROM licensedata WHERE licensename = (?) LIMIT 1
            """, (licname,))
            lic_id = cur.fetchone()
            if lic_id:
                licdata.add(lic_id[0])

        return frozenset(licdata)

    def retrieveLicenseText(self, license_name):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._connection().text_factory = const_convert_to_unicode

        cur = self._cursor().execute("""
        SELECT text FROM licensedata WHERE licensename = (?) LIMIT 1
        """, (license_name,))

        text = cur.fetchone()
        if text:
            return const_convert_to_rawstring(text[0])

    def retrieveLicense(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if self._isBaseinfoExtrainfo2010():
            cur = self._cursor().execute("""
            SELECT license FROM baseinfo
            WHERE idpackage = (?) LIMIT 1
            """, (package_id,))
        else:
            cur = self._cursor().execute("""
            SELECT license FROM baseinfo,licenses
            WHERE baseinfo.idpackage = (?) AND
            baseinfo.idlicense = licenses.idlicense LIMIT 1
            """, (package_id,))

        licname = cur.fetchone()
        if licname:
            return licname[0]

    def retrieveCompileFlags(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if self._isBaseinfoExtrainfo2010():
            cur = self._cursor().execute("""
            SELECT chost,cflags,cxxflags FROM extrainfo
            WHERE extrainfo.idpackage = (?)""", (package_id,))
        else:
            cur = self._cursor().execute("""
            SELECT chost,cflags,cxxflags FROM flags,extrainfo
            WHERE extrainfo.idpackage = (?) AND
            extrainfo.idflags = flags.idflags""", (package_id,))
        flags = cur.fetchone()
        if not flags:
            flags = ("N/A", "N/A", "N/A",)
        return flags

    def retrieveReverseDependencies(self, package_id, atoms = False,
        key_slot = False, exclude_deptypes = None, extended = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("reverseDependenciesMetadata")
        if cached is None:
            cached = self.__generateReverseDependenciesMetadata()

        dep_ids = set((k for k, v in cached.items() if package_id in v))
        if not dep_ids:
            # avoid python3.x memleak
            del cached
            if key_slot:
                return tuple()
            return frozenset()

        dep_ids_str = ', '.join((str(x) for x in dep_ids))
        excluded_deptypes_query = ""
        if exclude_deptypes is not None:
            for dep_type in exclude_deptypes:
                excluded_deptypes_query += " AND dependencies.type != %d" % (
                    dep_type,)

        if atoms:
            if extended:
                cur = self._cursor().execute("""
                SELECT baseinfo.atom, dependenciesreference.dependency
                FROM dependencies, baseinfo, dependenciesreference
                WHERE baseinfo.idpackage = dependencies.idpackage %s AND
                dependencies.iddependency =
                    dependenciesreference.iddependency AND
                dependencies.iddependency IN ( %s )""" % (
                    excluded_deptypes_query, dep_ids_str,))
                result = tuple(cur)
            else:
                cur = self._cursor().execute("""
                SELECT baseinfo.atom FROM dependencies, baseinfo
                WHERE baseinfo.idpackage = dependencies.idpackage %s AND
                dependencies.iddependency IN ( %s )""" % (
                    excluded_deptypes_query, dep_ids_str,))
                result = self._cur2frozenset(cur)
        elif key_slot:
            if self._isBaseinfoExtrainfo2010():
                if extended:
                    cur = self._cursor().execute("""
                    SELECT baseinfo.category || "/" || baseinfo.name,
                        baseinfo.slot, dependenciesreference.dependency
                    FROM baseinfo, dependencies, dependenciesreference
                    WHERE baseinfo.idpackage = dependencies.idpackage %s AND
                    dependencies.iddependency =
                        dependenciesreference.iddependency AND
                    dependencies.iddependency IN ( %s )""" % (
                        excluded_deptypes_query, dep_ids_str,))
                else:
                    cur = self._cursor().execute("""
                    SELECT baseinfo.category || "/" || baseinfo.name,
                        baseinfo.slot
                    FROM baseinfo, dependencies
                    WHERE baseinfo.idpackage = dependencies.idpackage %s AND
                    dependencies.iddependency IN ( %s )""" % (
                        excluded_deptypes_query, dep_ids_str,))
            else:
                if extended:
                    cur = self._cursor().execute("""
                    SELECT categories.category || "/" || baseinfo.name,
                        baseinfo.slot, dependenciesreference.dependency
                    FROM baseinfo, categories,
                        dependencies, dependenciesreference
                    WHERE baseinfo.idpackage = dependencies.idpackage AND
                    dependencies.iddependency =
                        dependenciesreference.iddependency AND
                    categories.idcategory = baseinfo.idcategory %s AND
                    dependencies.iddependency IN ( %s )""" % (
                        excluded_deptypes_query, dep_ids_str,))
                else:
                    cur = self._cursor().execute("""
                    SELECT categories.category || "/" || baseinfo.name,
                        baseinfo.slot
                    FROM baseinfo, categories, dependencies
                    WHERE baseinfo.idpackage = dependencies.idpackage AND
                    categories.idcategory = baseinfo.idcategory %s AND
                    dependencies.iddependency IN ( %s )""" % (
                        excluded_deptypes_query, dep_ids_str,))
            result = tuple(cur)
        elif excluded_deptypes_query:
            if extended:
                cur = self._cursor().execute("""
                SELECT dependencies.idpackage, dependenciesreference.dependency
                FROM dependencies, dependenciesreference
                WHERE %s AND
                dependencies.iddependency =
                    dependenciesreference.iddependency AND
                dependencies.iddependency IN ( %s )""" % (
                    excluded_deptypes_query.lstrip("AND "), dep_ids_str,))
                result = tuple(cur)
            else:
                cur = self._cursor().execute("""
                SELECT dependencies.idpackage FROM dependencies
                WHERE %s AND dependencies.iddependency IN ( %s )""" % (
                    excluded_deptypes_query.lstrip("AND "), dep_ids_str,))
                result = self._cur2frozenset(cur)
        else:
            if extended:
                cur = self._cursor().execute("""
                SELECT dependencies.idpackage, dependenciesreference.dependency
                FROM dependencies, dependenciesreference
                WHERE
                dependencies.iddependency =
                    dependenciesreference.iddependency AND
                dependencies.iddependency IN ( %s )""" % (dep_ids_str,))
                result = tuple(cur)
            else:
                cur = self._cursor().execute("""
                SELECT dependencies.idpackage FROM dependencies
                WHERE dependencies.iddependency IN ( %s )""" % (dep_ids_str,))
                result = self._cur2frozenset(cur)

        # avoid python3.x memleak
        del cached
        return result

    def retrieveUnusedPackageIds(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("reverseDependenciesMetadata")
        if cached is None:
            cached = self.__generateReverseDependenciesMetadata()

        pkg_ids = set()
        for v in cached.values():
            pkg_ids |= v
        if not pkg_ids:
            # avoid python3.x memleak
            del cached
            return tuple()
        pkg_ids_str = ', '.join((str(x) for x in pkg_ids))

        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo
        WHERE idpackage NOT IN ( %s )
        ORDER BY atom
        """ % (pkg_ids_str,))
        # avoid python3.x memleak
        del cached
        return self._cur2tuple(cur)

    def arePackageIdsAvailable(self, package_ids):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        sql = """SELECT count(idpackage) FROM baseinfo
        WHERE idpackage IN (%s)""" % (','.join(
            [str(x) for x in set(package_ids)]),
        )
        cur = self._cursor().execute(sql)
        count = cur.fetchone()[0]
        if count != len(package_ids):
            return False
        return True

    def isPackageIdAvailable(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        result = cur.fetchone()
        if not result:
            return False
        return True

    def _isCategoryAvailable(self, category):
        """
        NOTE: only working with _baseinfo_extrainfo_2010 disabled
        Return whether given category is available in repository.

        @param category: category name
        @type category: string
        @return: availability (True if available)
        @rtype: bool
        """
        cur = self._cursor().execute("""
        SELECT idcategory FROM categories WHERE category = (?) LIMIT 1
        """, (category,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def _isProtectAvailable(self, protect):
        """
        Return whether given CONFIG_PROTECT* entry is available in repository.

        @param protect: CONFIG_PROTECT* entry (path to a protected directory
            or file that won't be overwritten by Entropy Client during
            package merge)
        @type protect: string
        @return: availability (True if available)
        @rtype: bool
        """
        cur = self._cursor().execute("""
        SELECT idprotect FROM configprotectreference WHERE protect = (?)
        LIMIT 1
        """, (protect,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def _isLicenseAvailable(self, pkglicense):
        """
        NOTE: only working with _baseinfo_extrainfo_2010 disabled

        Return whether license metdatatum (NOT license name) is available
        in repository.

        @param pkglicense: "license" package metadatum (returned by
            retrieveLicense)
        @type pkglicense: string
        @return: "license" metadatum identifier (idlicense)
        @rtype: int
        """
        if not entropy.tools.is_valid_string(pkglicense):
            pkglicense = ' '

        cur = self._cursor().execute("""
        SELECT idlicense FROM licenses WHERE license = (?) LIMIT 1
        """, (pkglicense,))
        result = cur.fetchone()

        if result:
            return result[0]
        return -1

    def isFileAvailable(self, path, get_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM content WHERE file = (?)""", (path,))
        result = self._cur2frozenset(cur)
        if get_id:
            return result
        elif result:
            return True
        return False

    def resolveNeeded(self, needed, elfclass = -1, extended = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        args = (needed,)
        elfclass_txt = ''
        if elfclass != -1:
            elfclass_txt = ' AND provided_libs.elfclass = (?)'
            args = (needed, elfclass,)

        if extended:
            cur = self._cursor().execute("""
            SELECT idpackage, path FROM provided_libs
            WHERE library = (?)""" + elfclass_txt, args)
            return frozenset(cur)

        cur = self._cursor().execute("""
        SELECT idpackage FROM provided_libs
        WHERE library = (?)""" + elfclass_txt, args)
        return self._cur2frozenset(cur)

    def _isSourceAvailable(self, source):
        """
        Return whether given source package URL is available in repository.
        Returns source package URL identifier (idsource).

        @param source: source package URL
        @type source: string
        @return: source package URL identifier (idsource) or -1 if not found
        @rtype: int
        """
        cur = self._cursor().execute("""
        SELECT idsource FROM sourcesreference WHERE source = (?) LIMIT 1
        """, (source,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def _isDependencyAvailable(self, dependency):
        """
        Return whether given dependency string is available in repository.
        Returns dependency identifier (iddependency).

        @param dependency: dependency string
        @type dependency: string
        @return: dependency identifier (iddependency) or -1 if not found
        @rtype: int
        """
        cur = self._cursor().execute("""
        SELECT iddependency FROM dependenciesreference WHERE dependency = (?)
        LIMIT 1""", (dependency,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def _isKeywordAvailable(self, keyword):
        """
        Return whether keyword string is available in repository.
        Returns keyword identifier (idkeyword)

        @param keyword: keyword string
        @type keyword: string
        @return: keyword identifier (idkeyword) or -1 if not found
        @rtype: int
        """
        cur = self._cursor().execute("""
        SELECT idkeyword FROM keywordsreference WHERE keywordname = (?) LIMIT 1
        """, (keyword,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def _isUseflagAvailable(self, useflag):
        """
        Return whether USE flag name is available in repository.
        Returns USE flag identifier (idflag).

        @param useflag: USE flag name
        @type useflag: string
        @return: USE flag identifier or -1 if not found
        @rtype: int
        """
        cur = self._cursor().execute("""
        SELECT idflag FROM useflagsreference WHERE flagname = (?) LIMIT 1
        """, (useflag,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def isNeededAvailable(self, needed):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idneeded FROM neededreference WHERE library = (?) LIMIT 1
        """, (needed,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def isSpmUidAvailable(self, spm_uid):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT counter FROM counters WHERE counter = (?) LIMIT 1
        """, (spm_uid,))
        result = cur.fetchone()
        if result:
            return True
        return False

    def isSpmUidTrashed(self, spm_uid):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT counter FROM trashedcounters WHERE counter = (?) LIMIT 1
        """, (spm_uid,))
        result = cur.fetchone()
        if result:
            return True
        return False

    def isLicenseDataKeyAvailable(self, license_name):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT licensename FROM licensedata WHERE licensename = (?) LIMIT 1
        """, (license_name,))
        result = cur.fetchone()
        if not result:
            return False
        return True

    def isLicenseAccepted(self, license_name):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT licensename FROM licenses_accepted WHERE licensename = (?)
        LIMIT 1
        """, (license_name,))
        result = cur.fetchone()
        if not result:
            return False
        return True

    def acceptLicense(self, license_name):
        """
        Reimplemented from EntropyRepositoryBase.
        Needs to call superclass method.
        """
        super(EntropyRepository, self).acceptLicense(license_name)

        self._cursor().execute("""
        INSERT OR IGNORE INTO licenses_accepted VALUES (?)
        """, (license_name,))
        self.commit()

    def isSystemPackage(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM systempackages WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        result = cur.fetchone()
        if result:
            return True
        return False

    def isInjected(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM injected WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        result = cur.fetchone()
        if result:
            return True
        return False

    def _areCompileFlagsAvailable(self, chost, cflags, cxxflags):
        """
        NOTE: only working with _baseinfo_extrainfo_2010 disabled
        Return whether given Compiler FLAGS are available in repository.

        @param chost: CHOST flag
        @type chost: string
        @param cflags: CFLAGS flag
        @type cflags: string
        @param cxxflags: CXXFLAGS flag
        @type cxxflags: string
        @return: availability (True if available)
        @rtype: bool
        """
        cur = self._cursor().execute("""
        SELECT idflags FROM flags WHERE chost = (?)
        AND cflags = (?) AND cxxflags = (?) LIMIT 1
        """,
            (chost, cflags, cxxflags,)
        )
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def searchBelongs(self, bfile, like = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if like:
            cur = self._cursor().execute("""
            SELECT content.idpackage FROM content,baseinfo
            WHERE file LIKE (?) AND
            content.idpackage = baseinfo.idpackage""", (bfile,))
        else:
            cur = self._cursor().execute("""SELECT content.idpackage
            FROM content, baseinfo WHERE file = (?)
            AND content.idpackage = baseinfo.idpackage""", (bfile,))

        return self._cur2frozenset(cur)

    def searchContentSafety(self, sfile):
        """
        Search content safety metadata (usually, sha256 and mtime) related to
        given file path. A list of dictionaries is returned, each dictionary
        item contains at least the following fields "path", "sha256", "mtime").

        @param sfile: file path to search
        @type sfile: string
        @return: content safety metadata list
        @rtype: tuple
        """
        cur = self._cursor().execute("""
        SELECT idpackage, file, sha256, mtime
        FROM contentsafety WHERE file = (?)""", (sfile,))
        return tuple(({'package_id': x, 'path': y, 'sha256': z, 'mtime': m} for
            x, y, z, m in cur))

    def searchTaggedPackages(self, tag, atoms = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if atoms:
            cur = self._cursor().execute("""
            SELECT atom, idpackage FROM baseinfo WHERE versiontag = (?)
            """, (tag,))
            return frozenset(cur)

        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo WHERE versiontag = (?)
        """, (tag,))
        return self._cur2frozenset(cur)

    def searchRevisionedPackages(self, revision):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo WHERE revision = (?)
        """, (revision,))
        return self._cur2frozenset(cur)

    def searchLicense(self, keyword, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not entropy.tools.is_valid_string(keyword):
            return frozenset()

        license_query = """baseinfo, licenses
            WHERE LOWER(licenses.license) LIKE (?) AND
            licenses.idlicense = baseinfo.idlicense"""
        if self._isBaseinfoExtrainfo2010():
            license_query = "baseinfo WHERE LOWER(baseinfo.license) LIKE (?)"

        if just_id:
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM %s
            """ % (license_query,), ("%"+keyword+"%".lower(),))
            return self._cur2frozenset(cur)
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom, baseinfo.idpackage FROM %s
            """ % (license_query,), ("%"+keyword+"%".lower(),))
            return frozenset(cur)

    def searchSlotted(self, keyword, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if just_id:
            cur = self._cursor().execute("""
            SELECT idpackage FROM baseinfo WHERE slot = (?)""", (keyword,))
            return self._cur2frozenset(cur)
        else:
            cur = self._cursor().execute("""
            SELECT atom,idpackage FROM baseinfo WHERE slot = (?)
            """, (keyword,))
            return frozenset(cur)

    def searchKeySlot(self, key, slot):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("searchKeySlot")
        if cached is None:
            if self._isBaseinfoExtrainfo2010():
                cur = self._cursor().execute("""
                SELECT category, name, slot, idpackage FROM baseinfo
                """)
            else:
                cur = self._cursor().execute("""
                SELECT categories.category, baseinfo.name, baseinfo.slot,
                    baseinfo.idpackage
                FROM baseinfo, categories
                WHERE baseinfo.idcategory = categories.idcategory
                """)
            cached = {}
            for d_cat, d_name, d_slot, pkg_id in cur.fetchall():
                obj = cached.setdefault(
                    (d_cat, d_name, d_slot), set())
                obj.add(pkg_id)
            self._setLiveCache("searchKeySlot", cached)
        cat, name = key.split("/", 1)
        # avoid python3.x memleak
        obj = frozenset(cached.get((cat, name, slot), frozenset()))
        del cached
        return obj

    def searchKeySlotTag(self, key, slot, tag):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("searchKeySlotTag")
        if cached is None:
            if self._isBaseinfoExtrainfo2010():
                cur = self._cursor().execute("""
                SELECT category, name, slot, versiontag, idpackage
                FROM baseinfo
                """)
            else:
                cur = self._cursor().execute("""
                SELECT categories.category, baseinfo.name, baseinfo.slot,
                    baseinfo.versiontag, baseinfo.idpackage
                FROM baseinfo, categories
                WHERE baseinfo.idcategory = categories.idcategory
                """)
            cached = {}
            for d_cat, d_name, d_slot, d_tag, pkg_id in cur.fetchall():
                obj = cached.setdefault(
                    (d_cat, d_name, d_slot, d_tag), set())
                obj.add(pkg_id)
            self._setLiveCache("searchKeySlotTag", cached)
        cat, name = key.split("/", 1)
        # avoid python3.x memleak
        obj = frozenset(cached.get((cat, name, slot, tag), frozenset()))
        del cached
        return obj

    def searchNeeded(self, needed, elfclass = -1, like = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if like:
            needed = needed.replace("*", "%")
        elfsearch = ''
        search_args = (needed,)
        if elfclass != -1:
            elfsearch = ' AND needed.elfclass = (?)'
            search_args = (needed, elfclass,)

        if like:
            cur = self._cursor().execute("""
            SELECT needed.idpackage FROM needed,neededreference
            WHERE library LIKE (?) %s AND
            needed.idneeded = neededreference.idneeded
            """ % (elfsearch,), search_args)
        else:
            cur = self._cursor().execute("""
            SELECT needed.idpackage FROM needed,neededreference
            WHERE library = (?) %s AND
            needed.idneeded = neededreference.idneeded
            """ % (elfsearch,), search_args)

        return self._cur2frozenset(cur)

    def searchConflict(self, conflict, strings = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        keyword = "%"+conflict+"%"
        if strings:
            cur = self._cursor().execute("""
            SELECT conflict FROM conflicts WHERE conflict LIKE (?)
            """, (keyword,))
            return self._cur2tuple(cur)

        cur = self._cursor().execute("""
        SELECT idpackage, conflict FROM conflicts WHERE conflict LIKE (?)
        """, (keyword,))
        return tuple(cur)

    def searchDependency(self, dep, like = False, multi = False,
        strings = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        sign = "="
        if like:
            sign = "LIKE"
            dep = "%"+dep+"%"
        item = 'iddependency'
        if strings:
            item = 'dependency'

        cur = self._cursor().execute("""
        SELECT %s FROM dependenciesreference WHERE dependency %s (?)
        """ % (item, sign,), (dep,))

        if multi:
            return self._cur2frozenset(cur)
        iddep = cur.fetchone()

        if iddep:
            return iddep[0]
        return -1

    def searchPackageIdFromDependencyId(self, dependency_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM dependencies WHERE iddependency = (?)
        """, (dependency_id,))
        return self._cur2frozenset(cur)

    def searchSets(self, keyword):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # FIXME: remove this before 31-12-2011
        if not self._doesTableExist("packagesets"):
            return frozenset()
        cur = self._cursor().execute("""
        SELECT DISTINCT(setname) FROM packagesets WHERE setname LIKE (?)
        """, ("%"+keyword+"%",))

        return self._cur2frozenset(cur)

    def searchProvidedMime(self, mimetype):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # FIXME: remove this before 31-12-2011
        if not self._doesTableExist("provided_mime"):
            return tuple()
        cur = self._cursor().execute("""
        SELECT provided_mime.idpackage FROM provided_mime, baseinfo
        WHERE provided_mime.mimetype = (?)
        AND baseinfo.idpackage = provided_mime.idpackage
        ORDER BY baseinfo.atom""",
        (mimetype,))
        return self._cur2tuple(cur)

    def searchSimilarPackages(self, keyword, atom = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        s_item = 'name'
        if atom:
            s_item = 'atom'
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo
        WHERE soundex(%s) = soundex((?)) ORDER BY %s
        """ % (s_item, s_item,), (keyword,))

        return self._cur2tuple(cur)

    def searchPackages(self, keyword, sensitive = False, slot = None,
            tag = None, order_by = None, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        like_keyword = "%"+keyword+"%"
        if not sensitive:
            like_keyword = like_keyword.lower()
        searchkeywords = (like_keyword, like_keyword)

        slotstring = ''
        if slot:
            searchkeywords += (slot,)
            slotstring = ' AND slot = (?)'

        tagstring = ''
        if tag:
            searchkeywords += (tag,)
            tagstring = ' AND versiontag = (?)'

        order_by_string = ''
        if order_by is not None:
            valid_order_by = ("atom", "idpackage", "package_id", "branch",
                "name", "version", "versiontag", "revision", "slot")
            if order_by not in valid_order_by:
                raise AttributeError("invalid order_by argument")
            if order_by == "package_id":
                order_by = "idpackage"
            order_by_string = ' ORDER BY %s' % (order_by,)

        # atom idpackage branch
        # idpackage
        search_elements_all = """\
        t.atom AS atom, t.idpackage AS idpackage, t.branch AS branch,
        t.name AS name, t.version AS version, t.versiontag AS versiontag,
        t.revision AS revision, t.slot AS slot"""
        search_elements_provide_all = """\
        d.atom AS atom, d.idpackage AS idpackage, d.branch AS branch,
        d.name AS name, d.version AS version, d.versiontag AS versiontag,
        d.revision AS revision, d.slot AS slot"""

        search_elements = 'atom, idpackage, branch'
        if just_id:
            search_elements = 'idpackage'

        if sensitive:
            cur = self._cursor().execute("""
            SELECT DISTINCT %s FROM (
                SELECT %s FROM baseinfo t
                    WHERE t.atom LIKE (?)
                UNION ALL
                SELECT %s FROM baseinfo d, provide as p
                    WHERE d.idpackage = p.idpackage
                    AND p.atom LIKE (?)
            ) WHERE 1=1 %s %s %s
            """ % (search_elements, search_elements_all,
                search_elements_provide_all, slotstring, tagstring,
                order_by_string), searchkeywords)
        else:
            cur = self._cursor().execute("""
            SELECT DISTINCT %s FROM (
                SELECT %s FROM baseinfo t
                    WHERE LOWER(t.atom) LIKE (?)
                UNION ALL
                SELECT %s FROM baseinfo d, provide as p
                    WHERE d.idpackage = p.idpackage
                    AND LOWER(p.atom) LIKE (?)
            ) WHERE 1=1 %s %s %s
            """ % (search_elements, search_elements_all,
                search_elements_provide_all, slotstring, tagstring,
                order_by_string), searchkeywords)

        if just_id:
            return self._cur2tuple(cur)
        return tuple(cur)

    def searchProvidedVirtualPackage(self, keyword):
        """
        Search in old-style Portage PROVIDE metadata.
        @todo: rewrite docstring :-)

        @param keyword: search term
        @type keyword: string
        @return: found PROVIDE metadata
        @rtype: list
        """
        try:
            # be optimistic, cope with _doesColumnInTableExist slowness
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage,provide.is_default FROM baseinfo,provide
            WHERE provide.atom = (?) AND
            provide.idpackage = baseinfo.idpackage""", (keyword,))
        except OperationalError:
            # TODO: remove this before 31-12-2011
            if self._doesColumnInTableExist("provide", "is_default"):
                # something is really wrong
                raise
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage,0 FROM baseinfo,provide
            WHERE provide.atom = (?) AND
            provide.idpackage = baseinfo.idpackage""", (keyword,))

        return tuple(cur)

    def searchDescription(self, keyword, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        keyword_split = keyword.split()
        query_str_list = []
        query_args = []
        for sub_keyword in keyword_split:
            query_str_list.append("LOWER(extrainfo.description) LIKE (?)")
            query_args.append("%" + sub_keyword + "%")
        query_str = " AND ".join(query_str_list)
        if just_id:
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM extrainfo, baseinfo
            WHERE %s AND
            baseinfo.idpackage = extrainfo.idpackage
            """ % (query_str,), query_args)
            return self._cur2frozenset(cur)
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom, baseinfo.idpackage FROM extrainfo, baseinfo
            WHERE %s AND
            baseinfo.idpackage = extrainfo.idpackage
            """ % (query_str,), query_args)
            return frozenset(cur)

    def searchUseflag(self, keyword, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if just_id:
            cur = self._cursor().execute("""
            SELECT useflags.idpackage FROM useflags, useflagsreference
            WHERE useflags.idflag = useflagsreference.idflag
            AND useflagsreference.flagname = (?)
            """, (keyword,))
            return self._cur2frozenset(cur)
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom, useflags.idpackage
            FROM baseinfo, useflags, useflagsreference
            WHERE useflags.idflag = useflagsreference.idflag
            AND baseinfo.idpackage = useflags.idpackage
            AND useflagsreference.flagname = (?)
            """, (keyword,))
            return frozenset(cur)

    def searchHomepage(self, keyword, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if just_id:
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM extrainfo, baseinfo
            WHERE LOWER(extrainfo.homepage) LIKE (?) AND
            baseinfo.idpackage = extrainfo.idpackage
            """, ("%"+keyword.lower()+"%",))
            return self._cur2frozenset(cur)
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom, baseinfo.idpackage FROM extrainfo, baseinfo
            WHERE LOWER(extrainfo.homepage) LIKE (?) AND
            baseinfo.idpackage = extrainfo.idpackage
            """, ("%"+keyword.lower()+"%",))
            return frozenset(cur)

    def searchName(self, keyword, sensitive = False, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        atomstring = ''
        if not just_id:
            atomstring = 'atom,'

        if sensitive:
            cur = self._cursor().execute("""
            SELECT %s idpackage FROM baseinfo
            WHERE name = (?)
            """ % (atomstring,), (keyword,))
        else:
            cur = self._cursor().execute("""
            SELECT %s idpackage FROM baseinfo
            WHERE LOWER(name) = (?)
            """ % (atomstring,), (keyword.lower(),))

        if just_id:
            return self._cur2tuple(cur)
        return frozenset(cur)


    def searchCategory(self, keyword, like = False, just_id = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        like_string = "= (?)"
        if like:
            like_string = "LIKE (?)"

        if self._isBaseinfoExtrainfo2010():
            if just_id:
                cur = self._cursor().execute("""
                SELECT idpackage FROM baseinfo
                WHERE baseinfo.category %s
                """ % (like_string,), (keyword,))
            else:
                cur = self._cursor().execute("""
                SELECT atom, idpackage FROM baseinfo
                WHERE baseinfo.category %s
                """ % (like_string,), (keyword,))
        else:
            if just_id:
                cur = self._cursor().execute("""
                SELECT baseinfo.idpackage FROM baseinfo,categories
                WHERE categories.category %s AND
                baseinfo.idcategory = categories.idcategory
                """ % (like_string,), (keyword,))
            else:
                cur = self._cursor().execute("""
                SELECT baseinfo.atom,baseinfo.idpackage FROM baseinfo,categories
                WHERE categories.category %s AND
                baseinfo.idcategory = categories.idcategory
                """ % (like_string,), (keyword,))

        if just_id:
            return self._cur2frozenset(cur)
        return frozenset(cur)

    def searchNameCategory(self, name, category, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("searchNameCategory")
        # this gives 30% speed boost on atomMatch()
        if cached is None:
            if self._isBaseinfoExtrainfo2010():
                cur = self._cursor().execute("""
                SELECT name, category, atom, idpackage FROM baseinfo
                """)
            else:
                cur = self._cursor().execute("""
                SELECT baseinfo.name,categories.category,
                baseinfo.atom, baseinfo.idpackage FROM baseinfo,categories
                WHERE baseinfo.idcategory = categories.idcategory
                """)
            cached = {}
            for nam, cat, atom, pkg_id in cur.fetchall():
                obj = cached.setdefault((nam, cat), set())
                obj.add((atom, pkg_id))
            self._setLiveCache("searchNameCategory", cached)
        data = frozenset(cached.get((name, category), frozenset()))
        # This avoids memory leaks with python 3.x
        del cached
        if just_id:
            return frozenset((y for x, y in data))
        return data

    def isPackageScopeAvailable(self, atom, slot, revision):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        searchdata = (atom, slot, revision,)
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo
        where atom = (?)  AND slot = (?) AND revision = (?) LIMIT 1
        """, searchdata)
        rslt = cur.fetchone()

        if rslt: # check if it's masked
            return self.maskFilter(rslt[0])
        return -1, 0

    def isBranchMigrationAvailable(self, repository, from_branch, to_branch):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT post_migration_md5sum, post_upgrade_md5sum
        FROM entropy_branch_migration
        WHERE repository = (?) AND from_branch = (?) AND to_branch = (?)
        LIMIT 1
        """, (repository, from_branch, to_branch,))
        return cur.fetchone()

    def listPackageIdsInCategory(self, category, order_by = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        order_by_string = ''
        if order_by is not None:
            valid_order_by = ("atom", "idpackage", "package_id", "branch",
                "name", "version", "versiontag", "revision", "slot")
            if order_by not in valid_order_by:
                raise AttributeError("invalid order_by argument")
            if order_by == "package_id":
                order_by = "idpackage"
            order_by_string = ' order by %s' % (order_by,)

        if self._isBaseinfoExtrainfo2010():
            cur = self._cursor().execute("""
            SELECT idpackage FROM baseinfo where category = (?)
            """ + order_by_string, (category,))
        else:
            cur = self._cursor().execute("""
            SELECT idpackage FROM baseinfo, categories WHERE
                categories.category = (?) AND
                baseinfo.idcategory = categories.idcategory
            """ + order_by_string, (category,))

        return self._cur2frozenset(cur)

    def listAllPackages(self, get_scope = False, order_by = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        order_by_string = ''
        if order_by is not None:
            valid_order_by = ("atom", "idpackage", "package_id", "branch",
                "name", "version", "versiontag", "revision", "slot")
            if order_by not in valid_order_by:
                raise AttributeError("invalid order_by argument")
            if order_by == "package_id":
                order_by = "idpackage"
            order_by_string = ' order by %s' % (order_by,)

        if get_scope:
            cur = self._cursor().execute("""
            SELECT idpackage,atom,slot,revision FROM baseinfo""" + \
                order_by_string)
        else:
            cur = self._cursor().execute("""
            SELECT atom,idpackage,branch FROM baseinfo""" + order_by_string)

        return tuple(cur)

    def listAllSpmUids(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute('SELECT counter, idpackage FROM counters')
        return tuple(cur)

    def listAllPackageIds(self, order_by = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        order_by_string = ''
        if order_by is not None:
            valid_order_by = ("atom", "idpackage", "package_id", "branch",
                "name", "version", "versiontag", "revision", "slot", "date")
            if order_by not in valid_order_by:
                raise AttributeError("invalid order_by argument")
            if order_by == "package_id":
                order_by = "idpackage"
            order_by_string = ' order by %s' % (order_by,)

        if order_by == "date":
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM baseinfo, extrainfo
            WHERE baseinfo.idpackage = extrainfo.idpackage
            ORDER BY extrainfo.datecreation DESC""")
        else:
            cur = self._cursor().execute("""
            SELECT idpackage FROM baseinfo""" + order_by_string)

        try:
            if order_by:
                return self._cur2tuple(cur)
            return self._cur2frozenset(cur)
        except OperationalError:
            if order_by:
                return tuple()
            return frozenset()

    def _listAllDependencies(self):
        """
        List all dependencies available in repository.

        @return: list of tuples of length 2 containing (iddependency, dependency
            name,)
        @rtype: list
        """
        cur = self._cursor().execute("""
        SELECT iddependency, dependency FROM dependenciesreference""")
        return tuple(cur)

    def listAllDownloads(self, do_sort = True, full_path = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        order_string = ''
        if do_sort:
            order_string = 'ORDER BY extrainfo.download'

        cur = self._cursor().execute("""
        SELECT extrainfo.download FROM baseinfo, extrainfo
        WHERE baseinfo.idpackage = extrainfo.idpackage %s
        """ % (order_string,))

        if do_sort:
            results = self._cur2tuple(cur)
        else:
            results = self._cur2frozenset(cur)

        if not full_path:
            results = tuple((os.path.basename(x) for x in results))

        return results

    def listAllExtraDownloads(self, do_sort = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        order_string = ''
        if do_sort:
            order_string = ' ORDER BY download'
        try:
            cur = self._cursor().execute("""
            SELECT download FROM packagedownloads
            """ + order_string)
        except OperationalError:
            if self._doesTableExist("packagedownloads"):
                raise
            return tuple()

        if do_sort:
            results = self._cur2tuple(cur)
        else:
            results = self._cur2frozenset(cur)
        return results

    def listAllFiles(self, clean = False, count = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._connection().text_factory = const_convert_to_unicode

        if count:
            cur = self._cursor().execute('SELECT count(file) FROM content')
        else:
            cur = self._cursor().execute('SELECT file FROM content')

        if count:
            return cur.fetchone()[0]
        if clean:
            return self._cur2frozenset(cur)
        return self._cur2tuple(cur)

    def listAllCategories(self, order_by = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        order_by_string = ''
        if order_by is not None:
            valid_order_by = ("category",)
            if order_by not in valid_order_by:
                raise AttributeError("invalid order_by argument")
            order_by_string = 'ORDER BY %s' % (order_by,)

        if self._isBaseinfoExtrainfo2010():
            cur = self._cursor().execute(
                "SELECT DISTINCT category FROM baseinfo %s" % (
                    order_by_string,))
        else:
            cur = self._cursor().execute(
                "SELECT category FROM categories %s" % (order_by_string,))
        return self._cur2frozenset(cur)

    def listConfigProtectEntries(self, mask = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        mask_t = ''
        if mask:
            mask_t = 'mask'
        dirs = set()

        cur = self._cursor().execute("""
        SELECT protect FROM configprotectreference WHERE idprotect IN
            (SELECT distinct(idprotect) FROM configprotect%s)
        """ % (mask_t,))

        for mystr in self._cur2frozenset(cur):
            dirs.update(mystr.split())

        return sorted(dirs)

    def switchBranch(self, package_id, tobranch):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET branch = (?)
        WHERE idpackage = (?)""", (tobranch, package_id,))
        self.commit()
        self.clearCache()

    def getSetting(self, setting_name):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self.__settings_cache.get(setting_name)
        if isinstance(cached, KeyError):
            raise cached
        elif cached is not None:
            return cached

        try:
            cur = self._cursor().execute("""
            SELECT setting_value FROM settings WHERE setting_name = (?)
            """, (setting_name,))
        except Error:
            obj = KeyError("cannot find setting_name '%s'" % (setting_name,))
            self.__settings_cache[setting_name] = obj
            raise obj

        setting = cur.fetchone()
        if setting is None:
            obj = KeyError("setting unavaliable '%s'" % (setting_name,))
            self.__settings_cache[setting_name] = obj
            raise obj

        obj = setting[0]
        self.__settings_cache[setting_name] = obj
        return obj

    def _setSetting(self, setting_name, setting_value):
        """
        Internal method, set new setting for setting_name with value
        setting_value.
        """
        cur = self._cursor().execute("""
        INSERT OR REPLACE INTO settings VALUES (?, ?)
        """, (setting_name, setting_value,))
        self.commit()
        self.__settings_cache.clear()

    def _setupInitialSettings(self):
        """
        Setup initial repository settings
        """
        query = """
        INSERT OR REPLACE INTO settings VALUES ("arch", "%s");
        INSERT OR REPLACE INTO settings VALUES ("on_delete_cascade", "%s");
        """ % (etpConst['currentarch'], "1")
        if EntropyRepository._SCHEMA_2010_SUPPORT:
            query += """
            INSERT OR REPLACE INTO settings VALUES ("_baseinfo_extrainfo_2010",
            "%s");""" % ("1",)
        self._cursor().executescript(query)
        self.commit()
        self.__settings_cache.clear()

    def _databaseStructureUpdates(self):
        """
        Do not forget to bump _SCHEMA_REVISION whenever you add more tables
        """
        try:
            current_schema_rev = int(self.getSetting("schema_revision"))
        except (KeyError, ValueError):
            current_schema_rev = -1

        if (current_schema_rev == EntropyRepository._SCHEMA_REVISION) and \
            (not os.getenv("ETP_REPO_SCHEMA_UPDATE")):
            return

        old_readonly = self._readonly
        self._readonly = False

        if not self._doesTableExist("packagedesktopmime"):
            self._createPackageDesktopMimeTable()
        if not self._doesTableExist("provided_mime"):
            self._createProvidedMimeTable()

        if not self._doesTableExist("licenses_accepted"):
            self._createLicensesAcceptedTable()

        if not self._doesColumnInTableExist("installedtable", "source"):
            self._createInstalledTableSource()

        if not self._doesColumnInTableExist("provide", "is_default"):
            self._createProvideDefault()

        if not self._doesTableExist("packagesets"):
            self._createPackagesetsTable()

        if not self._doesTableExist("packagechangelogs"):
            self._createPackagechangelogsTable()

        if not self._doesTableExist("automergefiles"):
            self._createAutomergefilesTable()

        if not self._doesTableExist("packagesignatures"):
            self._createPackagesignaturesTable()
        elif not self._doesColumnInTableExist("packagesignatures", "gpg"):
            self._createPackagesignaturesGpgColumn()

        if not self._doesTableExist("packagespmphases"):
            self._createPackagespmphases()

        if not self._doesTableExist("packagespmrepository"):
            self._createPackagespmrepository()

        if not self._doesTableExist("entropy_branch_migration"):
            self._createEntropyBranchMigrationTable()

        if not self._doesTableExist("settings"):
            self._createSettingsTable()

        # added on Aug, 2010
        if not self._doesTableExist("contentsafety"):
            self._createContentSafetyTable()
        if not self._doesTableExist('provided_libs'):
            self._createProvidedLibs()

        # added on Aug. 2011
        if not self._doesTableExist("packagedownloads"):
            self._createPackageDownloadsTable()

        # added on Sept. 2010, keep forever? ;-)
        self._migrateBaseinfoExtrainfo()

        self._foreignKeySupport()

        self._readonly = old_readonly
        self._connection().commit()

        if not old_readonly:
            # it seems that it's causing locking issues
            # so, just execute it when in read/write mode
            self._setSetting("schema_revision",
                str(EntropyRepository._SCHEMA_REVISION))

    def integrity_check(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("PRAGMA quick_check(1)")
        try:
            check_data = cur.fetchone()[0]
            if check_data != "ok":
                raise ValueError()
        except (IndexError, ValueError, TypeError,):
            raise SystemDatabaseError(
                "sqlite3 reports database being corrupted")

    def validate(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("validate")
        if cached is not None:
            # avoid python3.x memleak
            del cached
            return
        self._setLiveCache("validate", True)
        # avoid python3.x memleak
        del cached

        mytxt = "Repository is corrupted, missing SQL tables!"
        cur = self._cursor().execute("""
        SELECT count(name) FROM SQLITE_MASTER WHERE type = "table" AND
            name IN ("extrainfo", "baseinfo", "keywords")
        """)
        rslt = cur.fetchone()
        if rslt is None:
            raise SystemDatabaseError(mytxt)
        elif rslt[0] != 3:
            raise SystemDatabaseError(mytxt)

        # execute checksum
        try:
            self.checksum()
        except (OperationalError, DatabaseError,) as err:
            mytxt = "Repository is corrupted, checksum error"
            raise SystemDatabaseError("%s: %s" % (mytxt, err,))

    def _getIdpackagesDifferences(self, foreign_package_ids):
        """
        Return differences between in-repository package identifiers and
        list provided.

        @param foreign_package_ids: list of foreign package_ids
        @type foreign_package_ids: iterable
        @return: tuple composed by package_ids that would be added and package_ids
            that would be removed
        @rtype: tuple
        """
        myids = self.listAllPackageIds()
        if isinstance(foreign_package_ids, (list, tuple)):
            outids = set(foreign_package_ids)
        else:
            outids = foreign_package_ids
        added_ids = outids - myids
        removed_ids = myids - outids
        return added_ids, removed_ids

    def alignDatabases(self, dbconn, force = False, output_header = "  ",
        align_limit = 300):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        added_ids, removed_ids = self._getIdpackagesDifferences(
            dbconn.listAllPackageIds())

        if not force:
            if len(added_ids) > align_limit: # too much hassle
                return 0
            if len(removed_ids) > align_limit: # too much hassle
                return 0

        if not added_ids and not removed_ids:
            return -1

        mytxt = red("%s, %s ...") % (
            _("Syncing current database"),
            _("please wait"),
        )
        self.output(
            mytxt,
            importance = 1,
            level = "info",
            header = output_header,
            back = True
        )

        maxcount = len(removed_ids)
        mycount = 0
        for package_id in removed_ids:
            mycount += 1
            mytxt = "%s: %s" % (
                red(_("Removing entry")),
                blue(str(self.retrieveAtom(package_id))),
            )
            self.output(
                mytxt,
                importance = 0,
                level = "info",
                header = output_header,
                back = True,
                count = (mycount, maxcount)
            )

            self.removePackage(package_id, do_cleanup = False, do_commit = False)

        maxcount = len(added_ids)
        mycount = 0
        for package_id in added_ids:
            mycount += 1
            mytxt = "%s: %s" % (
                red(_("Adding entry")),
                blue(str(dbconn.retrieveAtom(package_id))),
            )
            self.output(
                mytxt,
                importance = 0,
                level = "info",
                header = output_header,
                back = True,
                count = (mycount, maxcount)
            )
            mydata = dbconn.getPackageData(package_id, get_content = True,
                content_insert_formatted = True)
            self.addPackage(
                mydata,
                revision = mydata['revision'],
                package_id = package_id,
                do_commit = False,
                formatted_content = True
            )

        # do some cleanups
        self.clean()
        # clear caches
        self.clearCache()
        self.commit()
        dbconn.clearCache()

        # verify both checksums, if they don't match, bomb out
        mycheck = self.checksum(do_order = True, strict = False)
        outcheck = dbconn.checksum(do_order = True, strict = False)
        if mycheck == outcheck:
            return 1
        return 0

    @staticmethod
    def importRepository(dumpfile, dbfile):
        """
        Reimplemented from EntropyRepositoryBase.
        @todo: remove /usr/bin/sqlite3 dependency
        """
        dbfile = os.path.realpath(dbfile)
        tmp_dbfile = dbfile + ".import_repository"
        dumpfile = os.path.realpath(dumpfile)
        if not entropy.tools.is_valid_path_string(dbfile):
            raise AttributeError("dbfile value is invalid")
        if not entropy.tools.is_valid_path_string(dumpfile):
            raise AttributeError("dumpfile value is invalid")
        with open(dumpfile, "rb") as in_f:
            try:
                proc = subprocess.Popen(("/usr/bin/sqlite3", tmp_dbfile,),
                    bufsize = -1, stdin = in_f)
            except OSError:
                # ouch ! wtf!
                return 1
            rc = proc.wait()
            if rc == 0:
                os.rename(tmp_dbfile, dbfile)
        return rc

    def exportRepository(self, dumpfile):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        exclude_tables = []
        gentle_with_tables = True
        toraw = const_convert_to_rawstring

        dumpfile.write(toraw("BEGIN TRANSACTION;\n"))
        cur = self._cursor().execute("""
        SELECT name, type, sql FROM sqlite_master
        WHERE sql NOT NULL AND type=='table'
        """)
        for name, x, sql in cur.fetchall():

            self.output(
                red("%s " % (
                    _("Exporting database table"),
                ) ) + "["+blue(str(name))+"]",
                importance = 0,
                level = "info",
                back = True,
                header = "   "
            )
            if name.startswith("sqlite_"):
                continue

            t_cmd = "CREATE TABLE"
            if sql.startswith(t_cmd) and gentle_with_tables:
                sql = "CREATE TABLE IF NOT EXISTS"+sql[len(t_cmd):]
            dumpfile.write(toraw("%s;\n" % sql))

            if name in exclude_tables:
                continue

            cur2 = self._cursor().execute("PRAGMA table_info('%s')" % name)
            cols = [r[1] for r in cur2.fetchall()]
            q = "SELECT 'INSERT INTO \"%(tbl_name)s\" VALUES("
            q += ", ".join(["'||quote(" + x + ")||'" for x in cols])
            q += ")' FROM '%(tbl_name)s'"
            self._connection().text_factory = const_convert_to_unicode
            cur3 = self._cursor().execute(q % {'tbl_name': name})
            for row in cur3:
                dumpfile.write(toraw("%s;\n" % (row[0],)))

        cur4 = self._cursor().execute("""
        SELECT name, type, sql FROM sqlite_master
        WHERE sql NOT NULL AND type!='table' AND type!='meta'
        """)
        for name, x, sql in cur4.fetchall():
            dumpfile.write(toraw("%s;\n" % sql))

        dumpfile.write(toraw("COMMIT;\n"))
        if hasattr(dumpfile, 'flush'):
            dumpfile.flush()

        self.output(
            red(_("Database Export complete.")),
            importance = 0,
            level = "info",
            header = "   "
        )
        # remember to close the file

    def _listAllTables(self):
        """
        List all available tables in this repository database.

        @return: available tables
        @rtype: list
        """
        cur = self._cursor().execute("""
        SELECT name FROM SQLITE_MASTER
        WHERE type = "table" AND NOT name LIKE "sqlite_%"
        """)
        return self._cur2tuple(cur)

    def _doesTableExist(self, table, temporary = False):

        # NOTE: override cache when temporary is True
        if temporary:
            # temporary table do not pop-up with the statement below, so
            # we need to handle them with "care"
            try:
                cur = self._cursor().execute("""
                SELECT count(*) FROM (?) LIMIT 1""", (table,))
                cur.fetchone()
            except OperationalError:
                return False
            return True

        # speed up a bit if we already reported a table as existing
        cached = self._getLiveCache("_doesTableExist")
        if cached is None:
            cached = {}
        elif table in cached:
            # avoid memleak with python3.x
            obj = cached[table]
            del cached
            return obj

        cur = self._cursor().execute("""
        SELECT name FROM SQLITE_MASTER WHERE type = "table" AND name = (?)
        LIMIT 1
        """, (table,))
        rslt = cur.fetchone()
        exists = rslt is not None

        cached[table] = exists
        self._setLiveCache("_doesTableExist", cached)
        # avoid python3.x memleak
        del cached

        return exists

    def _doesColumnInTableExist(self, table, column):

        # speed up a bit if we already reported a column as existing
        d_tup = (table, column,)
        cached = self._getLiveCache("_doesColumnInTableExist")
        if cached is None:
            cached = {}
        elif d_tup in cached:
            # avoid memleak with python3.x
            obj = cached[d_tup]
            del cached
            return obj

        try:
            self._cursor().execute("""
            SELECT `%s` FROM `%s` LIMIT 1
            """ % (column, table))
            exists = True
        except OperationalError:
            exists = False
        cached[d_tup] = exists
        self._setLiveCache("_doesColumnInTableExist", cached)
        # avoid python3.x memleak
        del cached

        return exists

    def mtime(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if self._db_path is None:
            return 0.0
        if self._db_path == ":memory:":
            return 0.0
        return os.path.getmtime(self._db_path)

    def checksum(self, do_order = False, strict = True,
        strings = True, include_signatures = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cache_key = "checksum_%s_%s_%s_%s" % (do_order, strict, strings,
            include_signatures)
        cached = self._getLiveCache(cache_key)
        if cached is not None:
            return cached
        # avoid memleak with python3.x
        del cached

        package_id_order = ''
        category_order = ''
        license_order = ''
        flags_order = ''
        if do_order:
            package_id_order = 'order by idpackage'
            category_order = 'order by category'
            license_order = 'order by license'
            flags_order = 'order by chost'

        def do_update_hash(m, cursor):
            # this could slow things down a lot, so be careful
            # NOTE: this function must guarantee platform, architecture,
            # interpreter independent results. Cannot use hash() then.
            # Even repr() might be risky! But on the other hand, the
            # conversion to string cannot take forever.
            if const_is_python3():
                for record in cursor:
                    m.update(repr(record).encode("utf-8"))
            else:
                for record in cursor:
                    m.update(repr(record))

        if strings:
            m = hashlib.sha1()

        if not self._doesTableExist("baseinfo"):
            if strings:
                m.update(const_convert_to_rawstring("~empty~"))
                result = m.hexdigest()
            else:
                result = "~empty_db~"
                self._setLiveCache(cache_key, result)
            return result

        if strict:
            cur = self._cursor().execute("""
            SELECT * FROM baseinfo
            %s""" % (package_id_order,))
        else:
            cur = self._cursor().execute("""
            SELECT idpackage, atom, name, version, versiontag, revision,
            branch, slot, etpapi, trigger FROM baseinfo
            %s""" % (package_id_order,))
        if strings:
            do_update_hash(m, cur)
        else:
            a_hash = hash(tuple(cur))

        if strict:
            cur = self._cursor().execute("""
            SELECT * FROM extrainfo %s
            """ % (package_id_order,))
        else:
            cur = self._cursor().execute("""
            SELECT idpackage, description, homepage, download, size,
            digest, datecreation FROM extrainfo %s
            """ % (package_id_order,))
        if strings:
            do_update_hash(m, cur)
        else:
            b_hash = hash(tuple(cur))

        _baseinfo_extrainfo_2010 = self._isBaseinfoExtrainfo2010()
        c_hash = '0'
        if not _baseinfo_extrainfo_2010:
            cur = self._cursor().execute("""
            SELECT category FROM categories %s
            """ % (category_order,))
            if strings:
                do_update_hash(m, cur)
            else:
                c_hash = hash(tuple(cur))

        d_hash = '0'
        e_hash = '0'
        if not _baseinfo_extrainfo_2010:
            if strict:
                cur = self._cursor().execute("""
                SELECT * FROM licenses %s""" % (license_order,))
                if strings:
                    do_update_hash(m, cur)
                else:
                    d_hash = hash(tuple(cur))

                cur = self._cursor().execute('select * from flags %s' % (
                    flags_order,))
                if strings:
                    do_update_hash(m, cur)
                else:
                    e_hash = hash(tuple(cur))

        if include_signatures:
            try:
                # be optimistic and delay if condition, _doesColumnInTableExist
                # is really slow
                cur = self._cursor().execute("""
                SELECT idpackage, sha1,gpg FROM
                packagesignatures %s""" % (package_id_order,))
            except OperationalError:
                # TODO: remove this before 31-12-2011
                if self._doesColumnInTableExist("packagesignatures", "gpg"):
                    # something is really wrong
                    raise
                cur = self._cursor().execute("""
                SELECT idpackage, sha1 FROM
                packagesignatures %s""" % (package_id_order,))
            if strings:
                do_update_hash(m, cur)
            else:
                b_hash = "%s%s" % (b_hash, hash(tuple(cur)),)

        if strings:
            result = m.hexdigest()
        else:
            result = "%s:%s:%s:%s:%s" % (a_hash, b_hash, c_hash, d_hash, e_hash)

        self._setLiveCache(cache_key, result)
        return result

    def storeInstalledPackage(self, package_id, repoid, source = 0):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._clearLiveCache("getInstalledPackageRepository")
        self._clearLiveCache("getInstalledPackageSource")
        self._cursor().execute("""
        INSERT OR REPLACE INTO installedtable VALUES (?,?,?)
        """, (package_id, repoid, source,))

    def getInstalledPackageRepository(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("getInstalledPackageRepository")
        if cached is None:
            cur = self._cursor().execute("""
            SELECT idpackage, repositoryname FROM installedtable
            """)
            cached = dict(cur)
            self._setLiveCache("getInstalledPackageRepository", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def getInstalledPackageSource(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cached = self._getLiveCache("getInstalledPackageSource")
        if cached is None:
            try:
                # be optimistic, delay _doesColumnInTableExist as much as
                # possible
                cur = self._cursor().execute("""
                SELECT idpackage, source FROM installedtable
                """)
                cached = dict(cur)
            except OperationalError:
                # TODO: drop this check in future, backward compatibility
                if self._doesColumnInTableExist("installedtable", "source"):
                    # something is really wrong
                    raise
                cached = {}
            self._setLiveCache("getInstalledPackageSource", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def dropInstalledPackageFromStore(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM installedtable
        WHERE idpackage = (?)""", (package_id,))
        self._clearLiveCache("getInstalledPackageRepository")
        self._clearLiveCache("getInstalledPackageSource")

    def storeSpmMetadata(self, package_id, blob):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('INSERT into xpakdata VALUES (?,?)',
            (package_id, const_get_buffer()(blob),)
        )
        self.commit()

    def retrieveSpmMetadata(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not self._doesTableExist("xpakdata"):
            buf = const_get_buffer()
            return buf("")

        cur = self._cursor().execute("""
        SELECT data from xpakdata where idpackage = (?) LIMIT 1
        """, (package_id,))
        mydata = cur.fetchone()
        if not mydata:
            buf = const_get_buffer()
            return buf("")
        return mydata[0]

    def retrieveBranchMigration(self, to_branch):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not self._doesTableExist('entropy_branch_migration'):
            return {}

        cur = self._cursor().execute("""
        SELECT repository, from_branch, post_migration_md5sum,
        post_upgrade_md5sum FROM entropy_branch_migration WHERE to_branch = (?)
        """, (to_branch,))

        data = cur.fetchall()
        meta = {}
        for repo, from_branch, post_migration_md5, post_upgrade_md5 in data:
            obj = meta.setdefault(repo, {})
            obj[from_branch] = (post_migration_md5, post_upgrade_md5,)
        return meta

    def dropContent(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('DELETE FROM content')
        self.dropContentSafety()

    def dropContentSafety(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        try:
            self._cursor().execute('DELETE FROM contentsafety')
        except OperationalError:
            # table doesn't exist, ignore
            pass

    def dropChangelog(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('DELETE FROM packagechangelogs')

    def dropGpgSignatures(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('UPDATE packagesignatures set gpg = NULL')

    def dropAllIndexes(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT name FROM SQLITE_MASTER WHERE type = "index"
        AND name NOT LIKE "sqlite_%"
        """)
        for index in self._cur2frozenset(cur):
            try:
                self._cursor().execute('DROP INDEX IF EXISTS %s' % (index,))
            except Error:
                continue

    def createAllIndexes(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not self.__indexing:
            return

        self._createMirrorlinksIndex()
        self._createContentIndex()
        self._createBaseinfoIndex()
        self._createKeywordsIndex()
        self._createDependenciesIndex()
        self._createProvideIndex()
        self._createConflictsIndex()
        self._createExtrainfoIndex()
        self._createNeededIndex()
        self._createUseflagsIndex()
        self._createLicensedataIndex()
        self._createConfigProtectReferenceIndex()
        self._createSourcesIndex()
        self._createCountersIndex()
        self._createPackagesetsIndex()
        self._createAutomergefilesIndex()
        self._createProvidedLibsIndex()
        self._createDesktopMimeIndex()
        self._createProvidedMimeIndex()
        self._createPackageDownloadsIndex()
        if not self._isBaseinfoExtrainfo2010():
            self._createLicensesIndex()
            self._createCategoriesIndex()
            self._createCompileFlagsIndex()
        # make sure to commit here, or ANALYZE below
        # might deadlock
        self.commit(force=True)
        self._cursor().execute("ANALYZE").fetchall()

    def _createMirrorlinksIndex(self):
        try:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS mirrorlinks_mirrorname
            ON mirrorlinks ( mirrorname )""")
        except OperationalError:
            pass

    def _createCompileFlagsIndex(self):
        self._cursor().execute("""
        CREATE INDEX IF NOT EXISTS flagsindex ON flags
            ( chost, cflags, cxxflags )
        """)

    def _createDesktopMimeIndex(self):
        try:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS packagedesktopmime_idpackage
            ON packagedesktopmime ( idpackage )""")
        except OperationalError:
            pass

    def _createProvidedMimeIndex(self):
        try:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS provided_mime_idpackage
            ON provided_mime ( idpackage )""")
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS provided_mime_mimetype
            ON provided_mime ( mimetype )""")
        except OperationalError:
            pass

    def _createPackagesetsIndex(self):
        try:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS packagesetsindex
            ON packagesets ( setname )""")
        except OperationalError:
            pass

    def _createProvidedLibsIndex(self):
        try:
            self._cursor().executescript("""
                CREATE INDEX IF NOT EXISTS provided_libs_library
                ON provided_libs ( library );
                CREATE INDEX IF NOT EXISTS provided_libs_idpackage
                ON provided_libs ( idpackage );
                CREATE INDEX IF NOT EXISTS provided_libs_lib_elf
                ON provided_libs ( library, elfclass );
            """)
        except OperationalError:
            pass

    def _createAutomergefilesIndex(self):
        try:
            self._cursor().executescript("""
                CREATE INDEX IF NOT EXISTS automergefiles_idpackage 
                ON automergefiles ( idpackage );
                CREATE INDEX IF NOT EXISTS automergefiles_file_md5 
                ON automergefiles ( configfile, md5 );
            """)
        except OperationalError:
            pass

    def _createPackageDownloadsIndex(self):
        try:
            self._cursor().executescript("""
                CREATE INDEX IF NOT EXISTS packagedownloads_idpackage
                ON packagedownloads ( idpackage );
                CREATE INDEX IF NOT EXISTS packagedownloads_idpackage_type
                ON packagedownloads ( idpackage, type );
            """)
        except OperationalError:
            pass

    def _createNeededIndex(self):
        try:
            self._cursor().executescript("""
                CREATE INDEX IF NOT EXISTS neededindex ON neededreference
                    ( library );
                CREATE INDEX IF NOT EXISTS neededindex_idneeded ON needed
                    ( idneeded );
                CREATE INDEX IF NOT EXISTS neededindex_idpackage ON needed
                    ( idpackage );
                CREATE INDEX IF NOT EXISTS neededindex_elfclass ON needed
                    ( elfclass );
            """)
        except OperationalError:
            pass

    def _createUseflagsIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS useflagsindex_useflags_idpackage
            ON useflags ( idpackage );
        CREATE INDEX IF NOT EXISTS useflagsindex_useflags_idflag
            ON useflags ( idflag );
        CREATE INDEX IF NOT EXISTS useflagsindex
            ON useflagsreference ( flagname );
        """)

    def _createContentIndex(self):
        if self._doesTableExist("content"):
            self._cursor().executescript("""
                CREATE INDEX IF NOT EXISTS contentindex_couple
                    ON content ( idpackage );
                CREATE INDEX IF NOT EXISTS contentindex_file
                    ON content ( file );
            """)

    def _createConfigProtectReferenceIndex(self):
        self._cursor().execute("""
        CREATE INDEX IF NOT EXISTS configprotectreferenceindex
            ON configprotectreference ( protect )
        """)

    def _createBaseinfoIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS baseindex_atom
            ON baseinfo ( atom );
        CREATE INDEX IF NOT EXISTS baseindex_branch_name
            ON baseinfo ( name,branch );
        """)
        if self._isBaseinfoExtrainfo2010():
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS baseindex_branch_name_category
                ON baseinfo ( name, category, branch );
            CREATE INDEX IF NOT EXISTS baseindex_category
                ON baseinfo ( category );
            """)
        else:
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS baseindex_branch_name_idcategory
                ON baseinfo ( name,idcategory,branch );
            """)

    def _createLicensedataIndex(self):
        self._cursor().execute("""
        CREATE INDEX IF NOT EXISTS licensedataindex
            ON licensedata ( licensename )
        """)

    def _createLicensesIndex(self):
        self._cursor().execute("""
        CREATE INDEX IF NOT EXISTS licensesindex ON licenses ( license )
        """)

    def _createCategoriesIndex(self):
        self._cursor().execute("""
        CREATE INDEX IF NOT EXISTS categoriesindex_category
            ON categories ( category )
        """)

    def _createKeywordsIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS keywordsreferenceindex
            ON keywordsreference ( keywordname );
        CREATE INDEX IF NOT EXISTS keywordsindex_idpackage
            ON keywords ( idpackage );
        CREATE INDEX IF NOT EXISTS keywordsindex_idkeyword
            ON keywords ( idkeyword );
        """)

    def _createDependenciesIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS dependenciesindex_idpackage
            ON dependencies ( idpackage );
        CREATE INDEX IF NOT EXISTS dependenciesindex_iddependency
            ON dependencies ( iddependency );
        CREATE INDEX IF NOT EXISTS dependenciesreferenceindex_dependency
            ON dependenciesreference ( dependency );
        """)

    def _createCountersIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS countersindex_idpackage
            ON counters ( idpackage );
        CREATE INDEX IF NOT EXISTS countersindex_counter
            ON counters ( counter );
        """)

    def _createSourcesIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS sourcesindex_idpackage
            ON sources ( idpackage );
        CREATE INDEX IF NOT EXISTS sourcesindex_idsource
            ON sources ( idsource );
        CREATE INDEX IF NOT EXISTS sourcesreferenceindex_source
            ON sourcesreference ( source );
        """)

    def _createProvideIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS provideindex_idpackage
            ON provide ( idpackage );
        CREATE INDEX IF NOT EXISTS provideindex_atom
            ON provide ( atom );
        """)

    def _createConflictsIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS conflictsindex_idpackage
            ON conflicts ( idpackage );
        CREATE INDEX IF NOT EXISTS conflictsindex_atom
            ON conflicts ( conflict );
        """)

    def _createExtrainfoIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS extrainfoindex
            ON extrainfo ( description );
        CREATE INDEX IF NOT EXISTS extrainfoindex_pkgindex
            ON extrainfo ( idpackage );
        """)

    def regenerateSpmUidMapping(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        spm = get_spm(self)

        # this is necessary now, counters table should be empty
        self._cursor().executescript("""
        DROP TABLE IF EXISTS counters_regen;
        CREATE TEMPORARY TABLE counters_regen (
            counter INTEGER,
            idpackage INTEGER,
            branch VARCHAR,
            PRIMARY KEY(idpackage, branch)
        );
        """)
        insert_data = []
        for myid in self.listAllPackageIds():

            try:
                spm_uid = spm.resolve_package_uid(self, myid)
            except SPMError as err:
                mytxt = "%s: %s: %s" % (
                    bold(_("ATTENTION")),
                    red(_("Spm error occured")),
                    str(err),
                )
                self.output(
                    mytxt,
                    importance = 1,
                    level = "warning"
                )
                continue

            if spm_uid is None:
                mytxt = "%s: %s: %s" % (
                    bold(_("ATTENTION")),
                    red(_("Spm Unique Identifier not found for")),
                    self.retrieveAtom(myid),
                )
                self.output(
                    mytxt,
                    importance = 1,
                    level = "warning"
                )
                continue

            mybranch = self.retrieveBranch(myid)
            insert_data.append((spm_uid, myid, mybranch))

        self._cursor().executemany("""
        INSERT OR REPLACE into counters_regen VALUES (?,?,?)
        """, insert_data)

        self._cursor().executescript("""
        DELETE FROM counters;
        INSERT INTO counters (counter, idpackage, branch)
            SELECT counter, idpackage, branch FROM counters_regen;
        """)

        self.commit()

    def clearTreeupdatesEntries(self, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM treeupdates WHERE repository = (?)
        """, (repository,))
        self.commit()

    def resetTreeupdatesDigests(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('UPDATE treeupdates SET digest = "-1"')
        self.commit()

    def _isBaseinfoExtrainfo2010(self):
        """
        Return is _baseinfo_extrainfo_2010 setting is found via getSetting()
        """
        try:
            self.getSetting("_baseinfo_extrainfo_2010")
            # extra check to avoid issues with settings table creation
            # before the actual schema update, check if baseinfo has the
            # category column.
            return self._doesColumnInTableExist("baseinfo", "category")
        except KeyError:
            return False

    def _migrateBaseinfoExtrainfo(self):
        """
        Support for optimized baseinfo table, migration function.
        """
        if not EntropyRepository._SCHEMA_2010_SUPPORT:
            # support not yet enabled.
            return
        if self._isBaseinfoExtrainfo2010():
            return
        if not self._doesTableExist("baseinfo"):
            return
        if not self._doesTableExist("extrainfo"):
            return
        if not self._doesTableExist("licenses"):
            return
        if not self._doesTableExist("categories"):
            return
        if not self._doesTableExist("flags"):
            return

        mytxt = "%s: [%s] %s" % (
            bold(_("ATTENTION")),
            purple(self.name),
            red(_("updating repository metadata layout, please wait!")),
        )
        self.output(
            mytxt,
            importance = 1,
            level = "warning")

        self.dropAllIndexes()
        self._cursor().execute("pragma foreign_keys = OFF").fetchall()
        self._cursor().executescript("""
            BEGIN TRANSACTION;

            DROP TABLE IF EXISTS baseinfo_new_temp;
            CREATE TABLE baseinfo_new_temp (
                idpackage INTEGER PRIMARY KEY AUTOINCREMENT,
                atom VARCHAR,
                category VARCHAR,
                name VARCHAR,
                version VARCHAR,
                versiontag VARCHAR,
                revision INTEGER,
                branch VARCHAR,
                slot VARCHAR,
                license VARCHAR,
                etpapi INTEGER,
                trigger INTEGER
            );
            INSERT INTO baseinfo_new_temp
                SELECT idpackage, atom, category, name, version, versiontag,
                    revision, branch, slot, license, etpapi, trigger
                FROM baseinfo, licenses, categories WHERE
                    categories.idcategory = baseinfo.idcategory AND
                    licenses.idlicense = baseinfo.idlicense;
            DROP TABLE baseinfo;
            ALTER TABLE baseinfo_new_temp RENAME TO baseinfo;
            DROP TABLE categories;
            DROP TABLE licenses;

            DROP TABLE IF EXISTS extrainfo_new_temp;
            CREATE TABLE extrainfo_new_temp (
                idpackage INTEGER PRIMARY KEY,
                description VARCHAR,
                homepage VARCHAR,
                download VARCHAR,
                size VARCHAR,
                chost VARCHAR,
                cflags VARCHAR,
                cxxflags VARCHAR,
                digest VARCHAR,
                datecreation VARCHAR,
                FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
            );
            INSERT INTO extrainfo_new_temp
                SELECT idpackage, description, homepage, download, size,
                    flags.chost, flags.cflags, flags.cxxflags, digest, datecreation
                FROM extrainfo, flags WHERE flags.idflags = extrainfo.idflags;
            DROP TABLE extrainfo;
            ALTER TABLE extrainfo_new_temp RENAME TO extrainfo;
            DROP TABLE flags;

            COMMIT;
        """)
        self._cursor().execute("pragma foreign_keys = ON").fetchall()

        self._setSetting("_baseinfo_extrainfo_2010", "1")

    def _foreignKeySupport(self):

        # entropy.qa uses this name, must skip migration
        if self.name in ("qa_testing", "mem_repo"):
            return

        tables = ("extrainfo", "dependencies" , "provide",
            "conflicts", "configprotect", "configprotectmask", "sources",
            "useflags", "keywords", "content", "counters", "sizes",
            "needed", "triggers", "systempackages", "injected",
            "installedtable", "automergefiles", "packagesignatures",
            "packagespmphases", "provided_libs"
        )

        done_something = False
        foreign_keys_supported = False
        for table in tables:
            if not self._doesTableExist(table): # wtf
                continue

            cur = self._cursor().execute("PRAGMA foreign_key_list(%s)" % (table,))
            foreign_keys = cur.fetchone()

            # print table, "foreign keys", foreign_keys
            if foreign_keys is not None:
                # seems so, more or less
                foreign_keys_supported = True
                continue

            if not done_something:
                mytxt = "%s: [%s] %s" % (
                    bold(_("ATTENTION")),
                    purple(self.name),
                    red(_("updating repository metadata layout, please wait!")),
                )
                self.output(
                    mytxt,
                    importance = 1,
                    level = "warning"
                )

            done_something = True
            # need to add foreign key to this table
            cur = self._cursor().execute("""SELECT sql FROM sqlite_master
            WHERE type='table' and name = (?)""", (table,))
            cur_sql = cur.fetchone()[0]

            # change table name
            tmp_table = table+"_fk_sup"
            self._cursor().execute("DROP TABLE IF EXISTS %s" % (tmp_table,))

            bracket_idx = cur_sql.find("(")
            cur_sql = cur_sql[bracket_idx:]
            cur_sql = "CREATE TABLE %s %s" % (tmp_table, cur_sql)

            # remove final parenthesis and strip
            cur_sql = cur_sql[:-1].strip()
            # add foreign key stmt
            cur_sql += """,
            FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE );"""
            self._cursor().executescript(cur_sql)
            self._moveContent(table, tmp_table)
            self._atomicRename(tmp_table, table)

        if done_something:
            self._setSetting("on_delete_cascade", "1")
            # recreate indexes
            self.createAllIndexes()
        elif foreign_keys_supported:
            # some devel version didn't have this set
            try:
                self.getSetting("on_delete_cascade")
            except KeyError:
                self._setSetting("on_delete_cascade", "1")

    def _moveContent(self, from_table, to_table):
        self._cursor().execute("""
            INSERT INTO %s SELECT * FROM %s
        """ % (to_table, from_table,))

    def _atomicRename(self, from_table, to_table):
        self._cursor().executescript("""
            BEGIN TRANSACTION;
            DROP TABLE IF EXISTS %s;
            ALTER TABLE %s RENAME TO %s;
            COMMIT;
        """ % (to_table, from_table, to_table,))

    def _migrateCountersTable(self):
        self._cursor().executescript("""
            BEGIN TRANSACTION;
            DROP TABLE IF EXISTS counterstemp;
            CREATE TABLE counterstemp (
                counter INTEGER, idpackage INTEGER, branch VARCHAR,
                PRIMARY KEY(idpackage,branch),
                FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
            );
            INSERT INTO counterstemp (counter, idpackage, branch)
                SELECT counter, idpackage, branch FROM counters;
            DROP TABLE IF EXISTS counters;
            ALTER TABLE counterstemp RENAME TO counters;
            COMMIT;
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createSettingsTable(self):
        self._cursor().executescript("""
            CREATE TABLE settings (
                setting_name VARCHAR,
                setting_value VARCHAR,
                PRIMARY KEY(setting_name)
            );
        """)
        self._setupInitialSettings()
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createProvidedLibs(self):

        def do_create():
            self._cursor().executescript("""
                CREATE TABLE provided_libs (
                    idpackage INTEGER,
                    library VARCHAR,
                    path VARCHAR,
                    elfclass INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage)
                    ON DELETE CASCADE
                );
            """)
            self._clearLiveCache("_doesTableExist")
            self._clearLiveCache("_doesColumnInTableExist")

        if self.name != etpConst['clientdbid']:
            return do_create()

        mytxt = "%s: %s" % (
            bold(_("ATTENTION")),
            red(_("generating provided_libs metadata, please wait!")),
        )
        self.output(
            mytxt,
            importance = 1,
            level = "warning"
        )

        try:
            self._generateProvidedLibsMetadata()
        except (IOError, OSError, Error) as err:
            mytxt = "%s: %s: [%s]" % (
                bold(_("ATTENTION")),
                red("cannot generate provided_libs metadata"),
                err,
            )
            self.output(
                mytxt,
                importance = 1,
                level = "warning"
            )
            do_create()

    def _createPackageDownloadsTable(self):
        self._cursor().executescript("""
            CREATE TABLE packagedownloads (
                idpackage INTEGER,
                download VARCHAR,
                type VARCHAR,
                size INTEGER,
                disksize INTEGER,
                md5 VARCHAR,
                sha1 VARCHAR,
                sha256 VARCHAR,
                sha512 VARCHAR,
                gpg BLOB,
                FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
            );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _generateProvidedLibsMetadata(self):

        def collect_provided(pkg_dir, content):

            provided_libs = set()
            ldpaths = entropy.tools.collect_linker_paths()
            for obj, ftype in list(content.items()):

                if ftype == "dir":
                    continue
                obj_dir, obj_name = os.path.split(obj)

                if obj_dir not in ldpaths:
                    continue

                unpack_obj = os.path.join(pkg_dir, obj)
                try:
                    os.stat(unpack_obj)
                except OSError:
                    continue

                # do not trust ftype
                if os.path.isdir(unpack_obj):
                    continue
                if not entropy.tools.is_elf_file(unpack_obj):
                    continue

                elf_class = entropy.tools.read_elf_class(unpack_obj)
                provided_libs.add((obj_name, obj, elf_class,))

            return provided_libs

        self._cursor().executescript("""
            DROP TABLE IF EXISTS provided_libs_tmp;
            CREATE TABLE provided_libs_tmp (
                idpackage INTEGER,
                library VARCHAR,
                path VARCHAR,
                elfclass INTEGER,
                FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage)
                ON DELETE CASCADE
            );
        """)

        pkgs = self.listAllPackageIds()
        for package_id in pkgs:

            content = self.retrieveContent(package_id, extended = True,
                formatted = True)
            provided_libs = collect_provided(etpConst['systemroot'], content)

            self._cursor().executemany("""
            INSERT INTO provided_libs_tmp VALUES (?,?,?,?)
            """, [(package_id, x, y, z,) for x, y, z in provided_libs])

        # rename
        self._cursor().execute("""
        ALTER TABLE provided_libs_tmp RENAME TO provided_libs;
        """)
        # make sure that live_cache reports correct info regarding tables
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createProvideDefault(self):
        self._cursor().execute("""
        ALTER TABLE provide ADD COLUMN is_default INTEGER DEFAULT 0
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createInstalledTableSource(self):
        self._cursor().execute("""
        ALTER TABLE installedtable ADD source INTEGER;
        """)
        self._cursor().execute("""
        UPDATE installedtable SET source = (?)
        """, (etpConst['install_sources']['unknown'],))
        self._clearLiveCache("getInstalledPackageRepository")
        self._clearLiveCache("getInstalledPackageSource")
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createPackagechangelogsTable(self):
        self._cursor().execute("""
        CREATE TABLE packagechangelogs ( category VARCHAR,
            name VARCHAR, changelog BLOB, PRIMARY KEY (category, name));
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createAutomergefilesTable(self):
        self._cursor().execute("""
        CREATE TABLE automergefiles ( idpackage INTEGER,
            configfile VARCHAR, md5 VARCHAR,
            FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage)
            ON DELETE CASCADE );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createPackagesignaturesTable(self):
        self._cursor().execute("""
        CREATE TABLE packagesignatures (
        idpackage INTEGER PRIMARY KEY,
        sha1 VARCHAR,
        sha256 VARCHAR,
        sha512 VARCHAR,
        gpg BLOB,
        FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createPackagesignaturesGpgColumn(self):
        self._cursor().execute("""
        ALTER TABLE packagesignatures ADD gpg BLOB;
        """)
        self._clearLiveCache("_doesColumnInTableExist")

    def _createPackagespmphases(self):
        self._cursor().execute("""
            CREATE TABLE packagespmphases (
                idpackage INTEGER PRIMARY KEY,
                phases VARCHAR,
                FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
            );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createPackagespmrepository(self):
        self._cursor().execute("""
            CREATE TABLE packagespmrepository (
                idpackage INTEGER PRIMARY KEY,
                repository VARCHAR,
                FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
            );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createEntropyBranchMigrationTable(self):
        self._cursor().execute("""
            CREATE TABLE entropy_branch_migration (
                repository VARCHAR,
                from_branch VARCHAR,
                to_branch VARCHAR,
                post_migration_md5sum VARCHAR,
                post_upgrade_md5sum VARCHAR,
                PRIMARY KEY (repository, from_branch, to_branch)
            );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createPackagesetsTable(self):
        self._cursor().execute("""
        CREATE TABLE packagesets ( setname VARCHAR, dependency VARCHAR );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createPackageDesktopMimeTable(self):
        self._cursor().execute("""
        CREATE TABLE packagedesktopmime (
            idpackage INTEGER,
            name VARCHAR,
            mimetype VARCHAR,
            executable VARCHAR,
            icon VARCHAR,
            FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
        );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createProvidedMimeTable(self):
        self._cursor().execute("""
        CREATE TABLE provided_mime (
            mimetype VARCHAR,
            idpackage INTEGER,
            FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
        );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createLicensesAcceptedTable(self):
        self._cursor().execute("""
        CREATE TABLE licenses_accepted ( licensename VARCHAR UNIQUE );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createContentSafetyTable(self):
        self._cursor().execute("""
        CREATE TABLE contentsafety (
            idpackage INTEGER,
            file VARCHAR,
            mtime FLOAT,
            sha256 VARCHAR,
            FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
        );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def __generateReverseDependenciesMetadata(self):
        """
        Reverse dependencies dynamic metadata generation.
        """
        checksum = self.checksum()
        try:
            mtime = repr(self.mtime())
        except OSError:
            mtime = "0.0"
        hash_str = "%s|%s|%s|%s|%s" % (
            repr(self._db_path),
            repr(etpConst['systemroot']),
            repr(self.name),
            repr(checksum),
            mtime,
        )
        if const_is_python3():
            hash_str = hash_str.encode("utf-8")
        sha = hashlib.sha1()
        sha.update(hash_str)
        cache_key = "__generateReverseDependenciesMetadata2_" + \
            sha.hexdigest()
        rev_deps_data = self._cacher.pop(cache_key)
        if rev_deps_data is not None:
            self._setLiveCache("reverseDependenciesMetadata",
                rev_deps_data)
            return rev_deps_data

        dep_data = {}
        for iddep, atom in self._listAllDependencies():

            if iddep == -1:
                continue

            if atom.endswith(etpConst['entropyordepquestion']):
                or_atoms = atom[:-1].split(etpConst['entropyordepsep'])
                for or_atom in or_atoms:
                    # not safe to use cache here, people messing with multiple
                    # instances can make this crash
                    package_id, rc = self.atomMatch(or_atom, useCache = False)
                    if package_id != -1:
                        obj = dep_data.setdefault(iddep, set())
                        obj.add(package_id)
            else:
                # not safe to use cache here, people messing with multiple
                # instances can make this crash
                package_id, rc = self.atomMatch(atom, useCache = False)
                if package_id != -1:
                    obj = dep_data.setdefault(iddep, set())
                    obj.add(package_id)

        self._setLiveCache("reverseDependenciesMetadata",
                dep_data)
        try:
            self._cacher.save(cache_key, dep_data)
        except IOError:
            # race condition, ignore
            pass
        return dep_data

    def moveSpmUidsToBranch(self, to_branch):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE counters SET branch = (?)
        """, (to_branch,))
        self.commit()
        self.clearCache()
