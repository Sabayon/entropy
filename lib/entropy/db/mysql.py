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

from entropy.const import etpConst, const_setup_file, \
    const_isunicode, const_convert_to_unicode, const_get_buffer, \
    const_convert_to_rawstring, const_cmp, const_pid_exists, \
    const_is_python3
from entropy.exceptions import SystemDatabaseError, \
    OperationNotPermitted, RepositoryPluginError, SPMError
from entropy.output import brown, bold, red, blue, purple, darkred, darkgreen
from entropy.spm.plugins.factory import get_default_instance as get_spm
from entropy.i18n import _

import entropy.dep
import entropy.tools

from entropy.db.exceptions import IntegrityError, Error, OperationalError, \
    DatabaseError
from entropy.db.skel import EntropyRepositoryBase
from entropy.db.cache import EntropyRepositoryCacher

class MySQLProxy:

    _mod = None
    _excs = None
    _errnos = None
    _lock = threading.Lock()
    PORT = 3306

    @staticmethod
    def get():
        """
        Lazily load the MySQL module.
        """
        if MySQLProxy._mod is None:
            with MySQLProxy._lock:
                if MySQLProxy._mod is None:
                    import oursql
                    MySQLProxy._excs = oursql
                    MySQLProxy._mod = oursql
                    MySQLProxy._errnos = oursql.errnos
        return MySQLProxy._mod

    @staticmethod
    def exceptions():
        """
        Lazily load the MySQL exceptions module.
        """
        _mod = MySQLProxy.get()
        return MySQLProxy._excs

    @staticmethod
    def errno():
        """
        Lazily load the MySQL errno module.
        """
        _mod = MySQLProxy.get()
        return MySQLProxy._errnos


class EntropyMySQLRepository(EntropyRepositoryBase):

    """
    EntropyMySQLRepository implements MySQL based storage. In a Model-View based
    design pattern, this can be considered the "model".
    """

    # bump this every time schema changes and databaseStructureUpdate
    # should be triggered
    _SCHEMA_REVISION = 1

    _SETTING_KEYS = ("arch", "schema_revision")

    class Schema:

        def get_init(self):
            data = """
                CREATE TABLE baseinfo (
                    idpackage INTEGER(10) UNSIGNED NOT NULL
                        AUTO_INCREMENT PRIMARY KEY,
                    atom VARCHAR(75) NOT NULL,
                    category VARCHAR(128) NOT NULL,
                    name VARCHAR(75) NOT NULL,
                    version VARCHAR(75) NOT NULL,
                    versiontag VARCHAR(75) NOT NULL,
                    revision INTEGER(10) NOT NULL,
                    branch VARCHAR(75) NOT NULL,
                    slot VARCHAR(75) NOT NULL,
                    license VARCHAR(256) NOT NULL,
                    etpapi INTEGER(10) NOT NULL,
                    `trigger` INTEGER(10) NOT NULL
                );

                CREATE TABLE extrainfo (
                    idpackage INTEGER(10) UNSIGNED PRIMARY KEY NOT NULL,
                    description VARCHAR(256) NOT NULL,
                    homepage VARCHAR(1024) NOT NULL,
                    download VARCHAR(512) NOT NULL,
                    size VARCHAR(128) NOT NULL,
                    chost VARCHAR(256) NOT NULL,
                    cflags VARCHAR(512) NOT NULL,
                    cxxflags VARCHAR(512) NOT NULL,
                    digest CHAR(32) NOT NULL,
                    datecreation VARCHAR(32) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );
                CREATE TABLE content (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    file VARCHAR(512) NOT NULL,
                    type VARCHAR(3) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE contentsafety (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    file VARCHAR(512) NOT NULL,
                    mtime FLOAT,
                    sha256 CHAR(64) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE provide (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    atom VARCHAR(75) NOT NULL,
                    is_default INTEGER(10) NOT NULL DEFAULT 0,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE dependencies (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    iddependency INTEGER(10) UNSIGNED NOT NULL,
                    type INTEGER(10) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE dependenciesreference (
                    iddependency INTEGER(10) UNSIGNED NOT NULL
                        AUTO_INCREMENT PRIMARY KEY,
                    dependency VARCHAR(1024) NOT NULL
                );

                CREATE TABLE conflicts (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    conflict VARCHAR(128) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE mirrorlinks (
                    mirrorname VARCHAR(75) NOT NULL,
                    mirrorlink VARCHAR(512) NOT NULL
                );

                CREATE TABLE sources (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    idsource INTEGER(10) UNSIGNED NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE sourcesreference (
                    idsource INTEGER(10) UNSIGNED NOT NULL
                        AUTO_INCREMENT PRIMARY KEY,
                    source VARCHAR(512) NOT NULL
                );

                CREATE TABLE useflags (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    idflag INTEGER(10) UNSIGNED NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE useflagsreference (
                    idflag INTEGER(10) UNSIGNED NOT NULL
                        AUTO_INCREMENT PRIMARY KEY,
                    flagname VARCHAR(75) NOT NULL
                );

                CREATE TABLE keywords (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    idkeyword INTEGER(10) UNSIGNED NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE keywordsreference (
                    idkeyword INTEGER(10) UNSIGNED NOT NULL
                        AUTO_INCREMENT PRIMARY KEY,
                    keywordname VARCHAR(75) NOT NULL
                );

                CREATE TABLE configprotect (
                    idpackage INTEGER(10) UNSIGNED NOT NULL PRIMARY KEY,
                    idprotect INTEGER(10) UNSIGNED NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE configprotectmask (
                    idpackage INTEGER(10) UNSIGNED NOT NULL PRIMARY KEY,
                    idprotect INTEGER(10) UNSIGNED NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE configprotectreference (
                    idprotect INTEGER(10) UNSIGNED NOT NULL
                        AUTO_INCREMENT PRIMARY KEY,
                    protect VARCHAR(512) NOT NULL
                );

                CREATE TABLE systempackages (
                    idpackage INTEGER(10) UNSIGNED NOT NULL PRIMARY KEY,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE injected (
                    idpackage INTEGER(10) UNSIGNED NOT NULL PRIMARY KEY,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE installedtable (
                    idpackage INTEGER(10) UNSIGNED NOT NULL PRIMARY KEY,
                    repositoryname VARCHAR(75) NOT NULL,
                    source INTEGER(10) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE sizes (
                    idpackage INTEGER(10) UNSIGNED NOT NULL PRIMARY KEY,
                    size BIGINT UNSIGNED NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE counters (
                    counter INTEGER(10) NOT NULL,
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    branch VARCHAR(75) NOT NULL,
                    PRIMARY KEY(idpackage, branch),
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE trashedcounters (
                    counter INTEGER(10) NOT NULL
                );

                CREATE TABLE needed (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    idneeded INTEGER(10) UNSIGNED NOT NULL,
                    elfclass INTEGER(10) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE neededreference (
                    idneeded INTEGER(10) UNSIGNED NOT NULL
                        AUTO_INCREMENT PRIMARY KEY,
                    library VARCHAR(75) NOT NULL
                );

                CREATE TABLE provided_libs (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    library VARCHAR(75) NOT NULL,
                    path VARCHAR(75) NOT NULL,
                    elfclass INTEGER(10) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE treeupdates (
                    repository VARCHAR(75) NOT NULL PRIMARY KEY,
                    digest CHAR(32) NOT NULL
                );

                CREATE TABLE treeupdatesactions (
                    idupdate INTEGER(10) UNSIGNED NOT NULL
                        AUTO_INCREMENT PRIMARY KEY,
                    repository VARCHAR(75) NOT NULL,
                    command VARCHAR(256) NOT NULL,
                    branch VARCHAR(75) NOT NULL,
                    date VARCHAR(75) NOT NULL
                );

                CREATE TABLE licensedata (
                    licensename VARCHAR(75) NOT NULL UNIQUE,
                    `text` MEDIUMBLOB,
                    compressed INTEGER(10) NOT NULL
                );

                CREATE TABLE licenses_accepted (
                    licensename VARCHAR(75) NOT NULL UNIQUE
                );

                CREATE TABLE triggers (
                    idpackage INTEGER(10) UNSIGNED NOT NULL PRIMARY KEY,
                    data MEDIUMBLOB,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE entropy_misc_counters (
                    idtype INTEGER(10) NOT NULL PRIMARY KEY,
                    counter INTEGER(10) NOT NULL
                );

                CREATE TABLE categoriesdescription (
                    category VARCHAR(128) NOT NULL,
                    locale VARCHAR(75) NOT NULL,
                    description VARCHAR(256) NOT NULL
                );

                CREATE TABLE packagesets (
                    setname VARCHAR(75) NOT NULL,
                    dependency VARCHAR(1024) NOT NULL
                );

                CREATE TABLE packagechangelogs (
                    category VARCHAR(75) NOT NULL,
                    name VARCHAR(75) NOT NULL,
                    changelog MEDIUMBLOB NOT NULL,
                    PRIMARY KEY (category, name)
                );

                CREATE TABLE automergefiles (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    configfile VARCHAR(512) NOT NULL,
                    `md5` CHAR(32) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagedesktopmime (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    name VARCHAR(75),
                    mimetype VARCHAR(4096),
                    executable VARCHAR(128),
                    icon VARCHAR(75),
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagedownloads (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    download VARCHAR(512) NOT NULL,
                    type VARCHAR(75) NOT NULL,
                    size BIGINT UNSIGNED NOT NULL,
                    disksize BIGINT UNSIGNED NOT NULL,
                    `md5` CHAR(32) NOT NULL,
                    `sha1` CHAR(40) NOT NULL,
                    `sha256` CHAR(64) NOT NULL,
                    `sha512` CHAR(128) NOT NULL,
                    `gpg` BLOB,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE provided_mime (
                    mimetype VARCHAR(640) NOT NULL,
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagesignatures (
                    idpackage INTEGER(10) UNSIGNED NOT NULL PRIMARY KEY,
                    sha1 CHAR(40),
                    sha256 CHAR(64),
                    sha512 CHAR(128),
                    gpg BLOB,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagespmphases (
                    idpackage INTEGER(10) UNSIGNED NOT NULL PRIMARY KEY,
                    phases VARCHAR(512) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE packagespmrepository (
                    idpackage INTEGER(10) UNSIGNED NOT NULL PRIMARY KEY,
                    repository VARCHAR(75) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE entropy_branch_migration (
                    repository VARCHAR(75) NOT NULL,
                    from_branch VARCHAR(75) NOT NULL,
                    to_branch VARCHAR(75) NOT NULL,
                    post_migration_md5sum CHAR(32) NOT NULL,
                    post_upgrade_md5sum CHAR(32) NOT NULL,
                    PRIMARY KEY (repository, from_branch, to_branch)
                );

                CREATE TABLE xpakdata (
                    idpackage INTEGER(10) UNSIGNED NOT NULL PRIMARY KEY,
                    data LONGBLOB NOT NULL
                );

                CREATE TABLE settings (
                    setting_name VARCHAR(75) NOT NULL,
                    setting_value VARCHAR(75) NOT NULL,
                    PRIMARY KEY(setting_name)
                );

            """
            return data

    def __init__(self, uri, readOnly = False, xcache = False,
        name = None, indexing = True, skipChecks = False):
        """
        EntropyMySQLRepository constructor.

        @param uri: the connection URI
        @type uri: string
        @keyword readOnly: open file in read-only mode
        @type readOnly: bool
        @keyword xcache: enable on-disk cache
        @type xcache: bool
        @keyword name: repository identifier
        @type name: string
        @keyword indexing: enable database indexes
        @type indexing: bool
        @keyword skipChecks: if True, skip integrity checks
        @type skipChecks: bool
        """
        self._mysql = MySQLProxy.get()

        self._live_cacher = EntropyRepositoryCacher()
        self.__connection_pool = {}
        self.__connection_pool_mutex = threading.RLock()
        self.__cursor_pool_mutex = threading.RLock()
        self.__cursor_pool = {}

        self.__settings_cache = {}
        self._cleanup_stale_cur_conn_t = time.time()
        self.__indexing = indexing
        if name is None:
            name = etpConst['genericdbid']

        EntropyRepositoryBase.__init__(self, readOnly, xcache, False,
            name)

        # setup uri mysql://user:pass@host/database
        split_url = entropy.tools.spliturl(uri)
        if split_url is None:
            raise DatabaseError("Invalid URI")
        if split_url.scheme != "mysql":
            raise DatabaseError("Invalid Scheme")
        netloc = split_url.netloc
        if not netloc:
            raise DatabaseError("Invalid Netloc")
        try:
            self._host = netloc.split("@", 1)[-1]
        except IndexError:
            raise DatabaseError("Invalid Host")
        try:
            user_pass = "@".join(netloc.split("@")[:-1])
            self._user = user_pass.split(":")[0]
        except IndexError:
            raise DatabaseError("Invalid User")
        try:
            self._password = user_pass.split(":", 1)[1]
        except IndexError:
            raise DatabaseError("Invalid Password")

        db_port = split_url.path.lstrip("/")
        if not db_port:
            raise DatabaseError("Invalid Database")
        try:
            if ":" in db_port:
                self._db = ":".join(db_port.split(":")[:-1])
            else:
                self._db = db_port
        except IndexError:
            raise DatabaseError("Invalid Database Name")

        if self._db == ":memory:":
            raise DatabaseError(
                "Memory Database not supported (I use BLOBs)")

        try:
            if ":" in db_port:
                port = db_port.split(":")[-1].strip()
                if port:
                    self._port = int(port)
                else:
                    raise ValueError()
            else:
                raise IndexError()
        except IndexError:
            self._port = MySQLProxy.PORT
        except ValueError:
            raise DatabaseError("Invalid Port")

        # MySQL repositories don't support mtime
        self._cur_mtime = None

        # setup service interface
        self.__skip_checks = skipChecks

        self.__structure_update = False
        if not self.__skip_checks:

            try:
                if self._doesTableExist('baseinfo') and \
                        self._doesTableExist('extrainfo') and \
                        self._doesTableExist('settings'):
                    self.__structure_update = True

            except MySQLProxy.exceptions().Error:
                self._cleanup_stale_cur_conn(kill_all = True)
                raise

        if self.__structure_update:
            self._databaseStructureUpdates()

    def _connection_pool(self):
        """
        Return the Connection Pool mapping object
        """
        return self.__connection_pool

    def _connection_pool_mutex(self):
        """
        Return the Connection Pool mapping mutex
        """
        return self.__connection_pool_mutex

    def _cursor_pool(self):
        """
        Return the Cursor Pool mapping object
        """
        return self.__cursor_pool

    def _cursor_pool_mutex(self):
        """
        Return the Cursor Pool mapping mutex
        """
        return self.__cursor_pool_mutex

    def readonly(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return self._readonly

    def setIndexing(self, indexing):
        """
        Enable or disable metadata indexing.

        @param indexing: True, to enable indexing.
        @type indexing: bool
        """
        self.__indexing = bool(indexing)

    def _get_cur_th_key(self):
        return self._db, thread.get_ident(), os.getpid()

    def _cleanup_stale_cur_conn(self, kill_all = False):

        th_ids = [x.ident for x in threading.enumerate() if x.ident]

        def kill_me(path, th_id, pid):
            with self._cursor_pool_mutex():
                with self._connection_pool_mutex():
                    cur = self._cursor_pool().pop((path, th_id, pid), None)
                    if cur is not None:
                        cur.close()
                    conn = self._connection_pool().pop((path, th_id, pid), None)

            if conn is not None:
                if not self._readonly:
                    try:
                        conn.commit()
                    except MySQLProxy.exceptions().OperationalError:
                        # no transaction is active can
                        # cause this, bleh!
                        pass
                try:
                    conn.close()
                except MySQLProxy.exceptions().OperationalError:
                    try:
                        conn.close()
                    except MySQLProxy.exceptions().OperationalError:
                        # heh, unable to close due to
                        # unfinalized statements
                        # interpreter shutdown?
                        pass

        with self._cursor_pool_mutex():
            with self._connection_pool_mutex():
                th_data = set(self._cursor_pool().keys())
                th_data |= set(self._connection_pool().keys())
                for path, th_id, pid in th_data:
                    do_kill = False
                    if kill_all:
                        do_kill = True
                    elif th_id not in th_ids:
                        do_kill = True
                    elif not const_pid_exists(pid):
                        do_kill = True
                    if do_kill:
                        kill_me(path, th_id, pid)

    def _cursor(self):

        class MySQLCursorWrapper:
            """
            This class wraps a MySQL cursor and
            makes execute(), executemany() return
            the cursor itself.
            """

            def __init__(self, cursor):
                self._cur = cursor

            def execute(self, *args, **kwargs):
                # force oursql to empty the resultset
                self._cur = self._cur.connection.cursor()
                self._cur.execute(*args, **kwargs)
                return self

            def executemany(self, *args, **kwargs):
                # force oursql to empty the resultset
                self._cur = self._cur.connection.cursor()
                self._cur.executemany(*args, **kwargs)
                return self

            def close(self, *args, **kwargs):
                return self._cur.close(*args, **kwargs)

            def fetchone(self, *args, **kwargs):
                return self._cur.fetchone(*args, **kwargs)

            def fetchall(self, *args, **kwargs):
                return self._cur.fetchall(*args, **kwargs)

            def fetchmany(self, *args, **kwargs):
                return self._cur.fetchmany(*args, **kwargs)

            def executescript(self, script):
                for sql in script.split(";"):
                    if not sql.strip():
                        continue
                    self.execute(sql)
                return self

            def __iter__(self):
                return iter(self._cur)

            def next(self):
                return self._cur.next()

            @property
            def lastrowid(self):
                return self._cur.lastrowid

            @property
            def rowcount(self):
                return self._cur.rowcount

        # thanks to hotshot
        # this avoids calling _cleanup_stale_cur_conn logic zillions of time
        t1 = time.time()
        if abs(t1 - self._cleanup_stale_cur_conn_t) > 3:
            self._cleanup_stale_cur_conn()
            self._cleanup_stale_cur_conn_t = t1

        c_key = self._get_cur_th_key()
        with self._cursor_pool_mutex():
            cursor = self._cursor_pool().get(c_key)
            if cursor is None:
                conn = self._connection()
                cursor = conn.cursor()
                cursor.execute("SET storage_engine=InnoDB;")
                cursor.execute("SET autocommit=OFF;")
                cursor = MySQLCursorWrapper(cursor)
                self._cursor_pool()[c_key] = cursor
        return cursor

    def _connection(self):
        self._cleanup_stale_cur_conn()
        c_key = self._get_cur_th_key()
        with self._connection_pool_mutex():
            conn = self._connection_pool().get(c_key)
            if conn is None:
                kwargs = {
                    "host": self._host,
                    "user": self._user,
                    "passwd": self._password,
                    "db": self._db,
                    "port": self._port,
                    }
                try:
                    conn = self._mysql.connect(**kwargs)
                except MySQLProxy.exceptions().OperationalError as err:
                    raise OperationalError("Cannot connect: %s" % (repr(err),))
                self._connection_pool()[c_key] = conn
            else:
                conn.ping()
        return conn

    def __show_info(self):
        password = hashlib.new("md5")
        password.update(self._password)
        first_part = "<EntropyRepository instance at "
        "%s - host: %s, db: %s, port: %s, user: %s, hpass: %s" % (
            hex(id(self)), self._host, self._db, self._port, self._user,
            password.hexdigest(),)
        second_part = ", ro: %s|%s, caching: %s, indexing: %s" % (
            self._readonly, self.readonly(), self.caching(),
            self.__indexing,)
        third_part = ", name: %s, skip_upd: %s, st_upd: %s" % (
            self.name, self.__skip_checks, self.__structure_update,)
        fourth_part = ", conn_pool: %s, cursor_cache: %s>" % (
            self._connection_pool(), self._cursor_pool(),)

        return first_part + second_part + third_part + fourth_part

    def __repr__(self):
        return self.__show_info()

    def __str__(self):
        return self.__show_info()

    def __unicode__(self):
        return self.__show_info()

    def __hash__(self):
        return id(self)

    def _getLiveCacheKey(self):
        return etpConst['systemroot'] + "_" + self._db + "_" + \
            self.name + "_"

    def _clearLiveCache(self, key):
        self._live_cacher.clear_key(self._getLiveCacheKey() + key)

    def _discardLiveCache(self):
        self._live_cacher.discard(self._getLiveCacheKey())

    def _setLiveCache(self, key, value):
        self._live_cacher.set(self._getLiveCacheKey() + key, value)

    def _getLiveCache(self, key):
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
        super(EntropyMySQLRepository, self).close()

        self._cleanup_stale_cur_conn(kill_all = True)
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
        if force or not self.readonly():
            # NOTE: the actual commit MUST be executed before calling
            # the superclass method (that is going to call EntropyRepositoryBase
            # plugins). This to avoid that other connection to the same exact
            # database file are opened and used before data is actually written
            # to disk, causing a tricky race condition hard to exploit.
            # So, FIRST commit changes, then call plugins.
            try:
                self._connection().commit()
            except MySQLProxy.exceptions().Error:
                pass
        elif self.readonly():
            # rollback instead if read-only
            self.rollback()

        super(EntropyMySQLRepository, self).commit(force = force,
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
        self._cursor().execute("SET FOREIGN_KEY_CHECKS = 0;")
        try:
            for table in self._listAllTables():
                try:
                    cur = self._cursor().execute("DROP TABLE %s" % (table,))
                except MySQLProxy.exceptions().OperationalError:
                    # skip tables that can't be dropped
                    continue
        finally:
            self._cursor().execute("SET FOREIGN_KEY_CHECKS = 1;")
        self.commit()
        self._cursor().executescript(my.get_init())
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")
        self._setupInitialSettings()
        self._databaseStructureUpdates()

        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")
        self.commit()

        super(EntropyMySQLRepository, self).initializeRepository()

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

        mybaseinfo_data = (
            pkgatom, pkg_data['category'], pkg_data['name'],
            pkg_data['version'], pkg_data['versiontag'], revision,
            pkg_data['branch'], pkg_data['slot'],
            pkg_data['license'], pkg_data['etpapi'], trigger)

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
        INSERT INTO baseinfo VALUES
        (%s, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""" % (
            mypackage_id_string,), mybaseinfo_data)
        if package_id is None:
            package_id = cur.lastrowid

        # extrainfo
        self._cursor().execute(
            """INSERT INTO extrainfo VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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

        super(EntropyMySQLRepository, self).addPackage(
            pkg_data, revision = revision,
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
        super(EntropyMySQLRepository, self).removePackage(package_id,
            do_cleanup = do_cleanup, do_commit = do_commit,
            from_add_package = from_add_package)
        self.clearCache()

        # this will work thanks to ON DELETE CASCADE !
        self._cursor().execute(
            "DELETE FROM baseinfo WHERE idpackage = ?", (package_id,))

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
        DELETE FROM mirrorlinks WHERE mirrorname = ?
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
        INSERT into mirrorlinks VALUES (?, ?)
        """, [(mirrorname, x,) for x in mirrorlist])

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
        INSERT into configprotectreference VALUES (NULL, ?)
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
        INSERT into sourcesreference VALUES (NULL, ?)
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
        INSERT into dependenciesreference VALUES (NULL, ?)
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
        INSERT into keywordsreference VALUES (NULL, ?)
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
        cur = self._cursor().execute("""
        INSERT into useflagsreference VALUES (NULL, ?)
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
        INSERT into neededreference VALUES (NULL, ?)
        """, (needed,))
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
        UPDATE extrainfo SET datecreation = ? WHERE idpackage = ?
        """, (str(date), package_id,))

    def setDigest(self, package_id, digest):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE extrainfo SET digest = ? WHERE idpackage = ?
        """, (digest, package_id,))

    def setSignatures(self, package_id, sha1, sha256, sha512, gpg = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE packagesignatures SET sha1 = ?, sha256 = ?, sha512 = ?,
        gpg = ? WHERE idpackage = ?
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
        UPDATE extrainfo SET download = ? WHERE idpackage = ?
        """, (url, package_id,))

    def setCategory(self, package_id, category):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET category = ? WHERE idpackage = ?
        """, (category, package_id,))

    def setCategoryDescription(self, category, description_data):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM categoriesdescription WHERE category = ?
        """, (category,))
        for locale in description_data:
            mydesc = description_data[locale]
            self._cursor().execute("""
            INSERT INTO categoriesdescription VALUES (?, ?, ?)
            """, (category, locale, mydesc,))

    def setName(self, package_id, name):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET name = ? WHERE idpackage = ?
        """, (name, package_id,))

    def setDependency(self, iddependency, dependency):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE dependenciesreference SET dependency = ?
        WHERE iddependency = ?
        """, (dependency, iddependency,))

    def setAtom(self, package_id, atom):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET atom = ? WHERE idpackage = ?
        """, (atom, package_id,))

    def setSlot(self, package_id, slot):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET slot = ? WHERE idpackage = ?
        """, (slot, package_id,))

    def setRevision(self, package_id, revision):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET revision = ? WHERE idpackage = ?
        """, (revision, package_id,))

    def removeDependencies(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM dependencies WHERE idpackage = ?
        """, (package_id,))

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
        INSERT into dependencies VALUES (?, ?, ?)
        """, deps)

    def insertContent(self, package_id, content, already_formatted = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # respect iterators, so that if they're true iterators
        # we save a lot of memory.
        class MyIter:
            def __init__(self, _package_id, _content, _already_fmt):
                self._package_id = _package_id
                self._content = _content
                self._iter = iter(_content)
                self._already_fmt = _already_fmt

            def __iter__(self):
                return self

            def next(self):
                if self._already_fmt:
                    a, x, y = self._iter.next()
                    return self._package_id, x, y
                else:
                    x = self._iter.next()
                    return self._package_id, x, self._content[x]

        if already_formatted:
            self._cursor().executemany("""
            INSERT INTO content VALUES (?, ?, ?)
            """, MyIter(package_id, content, already_formatted))
        else:
            self._cursor().executemany("""
            INSERT INTO content VALUES (?, ?, ?)
            """, MyIter(package_id, content, already_formatted))

    def _insertContentSafety(self, package_id, content_safety):
        """
        Currently supported: sha256, mtime.
        Insert into contentsafety table package files sha256sum and mtime.
        """
        if isinstance(content_safety, dict):
            self._cursor().executemany("""
            INSERT into contentsafety VALUES (?, ?, ?, ?)
            """, [(package_id, k, v['mtime'], v['sha256']) \
                      for k, v in content_safety.items()])
        else:
            # support for iterators containing tuples like this:
            # (path, sha256, mtime)
            class MyIterWrapper:
                def __init__(self, _iter):
                    self._iter = _iter
                def __iter__(self):
                    return self
                def next(self):
                    path, sha256, mtime = self._iter.next()
                    # this is the insert order, with mtime
                    # and sha256 swapped.
                    return package_id, path, mtime, sha256

            self._cursor().executemany("""
            INSERT into contentsafety VALUES (?, ?, ?, ?)
            """, MyIterWrapper(content_safety))

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
        INSERT INTO provided_libs VALUES (?, ?, ?, ?)
        """, [(package_id, x, y, z,) for x, y, z in libs_metadata])

    def insertAutomergefiles(self, package_id, automerge_data):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().executemany("""
        INSERT INTO automergefiles VALUES (?, ?, ?)""",
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
        DELETE FROM packagechangelogs WHERE category = ? AND name = ?
        """, (category, name,))

        self._cursor().execute("""
        INSERT INTO packagechangelogs VALUES (?, ?, ?)
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
        INSERT INTO licensedata VALUES (?, ?, ?)
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
        INSERT INTO %s VALUES (?, ?)
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
        INSERT INTO keywords VALUES (?, ?)
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
        INSERT INTO useflags VALUES (?, ?)
        """, list(map(mymf, useflags)))

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
        self._cursor().execute("""
        INSERT INTO packagesignatures VALUES (?, ?, ?, ?, ?)
        """, (package_id, sha1, sha256, sha512, gpg))

    def _insertExtraDownload(self, package_id, package_downloads_data):
        """
        Insert extra package files download objects to repository.

        @param package_id: package indentifier
        @type package_id: int
        @param package_downloads_data: list of dict composed by
            (download, type, size, md5, sha1, sha256, sha512, gpg) as keys
        @type package_downloads_data: list
        """
        self._cursor().executemany("""
        INSERT INTO packagedownloads VALUES
        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [(package_id, edw['download'], edw['type'], edw['size'],
                edw['disksize'], edw['md5'], edw['sha1'], edw['sha256'],
                edw['sha512'], edw['gpg']) for edw in \
                    package_downloads_data])

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
        INSERT INTO packagedesktopmime VALUES (?, ?, ?, ?, ?)
        """, mime_data)

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
        INSERT INTO provided_mime VALUES (?, ?)""",
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
        INSERT INTO packagespmphases VALUES (?, ?)
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
        INSERT INTO packagespmrepository VALUES (?, ?)
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
        INSERT INTO sources VALUES (?, ?)
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
        INSERT INTO conflicts VALUES (?, ?)
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
        INSERT INTO provide VALUES (?, ?, ?)
        """, [(package_id, x, y,) for x, y in provides])

        if default_provides:
            # reset previously set default provides
            self._cursor().executemany("""
            UPDATE provide SET is_default=0 WHERE atom = ? AND
            idpackage != ?
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
        INSERT INTO needed VALUES (?, ?, ?)
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
        INSERT INTO sizes VALUES (?, ?)
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
        INSERT INTO triggers VALUES (?, ?)
        """, (package_id, const_get_buffer()(trigger),))

    def insertBranchMigration(self, repository, from_branch, to_branch,
        post_migration_md5sum, post_upgrade_md5sum):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        REPLACE INTO entropy_branch_migration VALUES (?, ?, ?, ?, ?)
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
        UPDATE entropy_branch_migration SET post_upgrade_md5sum = ? WHERE
        repository = ? AND from_branch = ? AND to_branch = ?
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

        self._cursor().execute('INSERT INTO counters VALUES (?, ?, ?)',
            (my_uid, package_id, branch,))

        return my_uid

    def insertSpmUid(self, package_id, spm_package_uid):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        branch = self._settings['repositories']['branch']

        self._cursor().execute("""
        DELETE FROM counters WHERE counter = ?
        AND branch = ?
        """, (spm_package_uid, branch,))
        # the "OR REPLACE" clause handles the UPDATE
        # of the counter value in case of clashing
        self._cursor().execute("""
        REPLACE INTO counters VALUES (?, ?, ?);
        """, (spm_package_uid, package_id, branch,))

    def setTrashedUid(self, spm_package_uid):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        REPLACE INTO trashedcounters VALUES ?
        """, (spm_package_uid,))

    def removeTrashedUids(self, spm_package_uids):
        """
        Remove given Source Package Manager unique package identifiers from
        the "trashed" list. This is only used by Entropy Server.
        """
        self._cursor().executemany("""
        DELETE FROM trashedcounters WHERE counter = ?
        """, [(x,) for x in spm_package_uids])

    def setSpmUid(self, package_id, spm_package_uid, branch = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        branchstring = ''
        insertdata = (spm_package_uid, package_id)
        if branch:
            branchstring = ', branch = ?'
            insertdata += (branch,)

        self._cursor().execute("""
        UPDATE or REPLACE counters SET counter = ? %s
        WHERE idpackage = ?""" % (branchstring,), insertdata)

    def setContentSafety(self, package_id, content_safety):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM contentsafety where idpackage = ?
        """, (package_id,))
        self._insertContentSafety(package_id, content_safety)

    def contentDiff(self, package_id, dbconn, dbconn_package_id,
                    extended = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # setup random table name
        random_str = "%svs%s_%s" % (package_id, id(dbconn),
            dbconn_package_id)
        if const_is_python3():
            random_str = const_convert_to_rawstring(random_str)
        randomtable = "cdiff%s" % (hashlib.md5(random_str).hexdigest(),)

        # create random table
        self._cursor().executescript("""
            DROP TABLE IF EXISTS `%s`;
            CREATE TEMPORARY TABLE `%s` ( file VARCHAR(75), ftype VARCHAR(3) );
            """ % (randomtable, randomtable,)
        )

        try:

            content_iter = dbconn.retrieveContentIter(dbconn_package_id)
            self._cursor().executemany("""
            INSERT INTO `%s` VALUES (?, ?)""" % (randomtable,),
                content_iter)

            # remove this when the one in retrieveContent will be removed
            self._connection().text_factory = const_convert_to_unicode

            # now compare
            ftype_str = ""
            if extended:
                ftype_str = ", type"
            cur = self._cursor().execute("""
            SELECT file%s FROM content
            WHERE content.idpackage = ? AND
            content.file NOT IN (SELECT file from `%s`)""" % (
                    ftype_str, randomtable,), (package_id,))

            # suck back
            if extended:
                return tuple(cur)
            return self._cur2frozenset(cur)

        finally:
            self._cursor().execute('DROP TABLE IF EXISTS `%s`' % (
                    randomtable,))

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
        self._cursor().execute("""
        DELETE FROM packagechangelogs
        WHERE CONCAT(category, '/', name) NOT IN
        (SELECT CONCAT(baseinfo.category, '/', baseinfo.name) FROM baseinfo)
        """)

    def getFakeSpmUid(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        try:
            cur = self._cursor().execute("""
            SELECT min(counter) FROM counters LIMIT 1
            """)
            dbcounter = cur.fetchone()
        except MySQLProxy.exceptions().Error:
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
        cur = self._cursor().execute("""
        SELECT max(etpapi) FROM baseinfo LIMIT 1
        """)
        api = cur.fetchone()
        if api:
            return api[0]
        return -1

    def getDependency(self, iddependency):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT dependency FROM dependenciesreference WHERE iddependency = ?
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
        SELECT idpackage FROM baseinfo WHERE atom = ?
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
            WHERE extrainfo.download LIKE ? AND
            baseinfo.idpackage = extrainfo.idpackage
            LIMIT 1
            """, ("%"+download_relative_path,))
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM baseinfo,extrainfo
            WHERE extrainfo.download = ? AND
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
        cur = self._cursor().execute("""
        SELECT version, versiontag, revision FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        return cur.fetchone()

    def getStrictData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT CONCAT(category, '/', name), slot, version,
            versiontag, revision, atom FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        return cur.fetchone()

    def getStrictScopeData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT atom, slot, revision FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        return cur.fetchone()

    def getScopeData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT atom, category, name, version, slot, versiontag,
            revision, branch, etpapi FROM baseinfo
        WHERE baseinfo.idpackage = ? LIMIT 1
        """, (package_id,))
        return cur.fetchone()

    def getBaseData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
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
            baseinfo.idpackage = ?
            AND baseinfo.idpackage = extrainfo.idpackage
        LIMIT 1
        """
        cur = self._cursor().execute(sql, (package_id,))
        return cur.fetchone()

    def _cur2frozenset(self, cur):
        mycontent = set()
        for x in cur:
            mycontent |= set(x)
        return frozenset(mycontent)

    def _cur2tuple(self, cur):
        # NOTE: fetchall() is required in order to force
        # oursql to transfer all data from MySQL.
        return tuple(itertools.chain.from_iterable(cur))

    def clearCache(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._live_cacher.clear()
        super(EntropyMySQLRepository, self).clearCache()
        self._live_cacher.clear()

    def retrieveRepositoryUpdatesDigest(self, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT digest FROM treeupdates WHERE repository = ? LIMIT 1
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
        repository = ? order by date""", params)
        return self._cur2tuple(cur)

    def bumpTreeUpdatesActions(self, updates):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('DELETE FROM treeupdatesactions')
        self._cursor().executemany("""
        INSERT INTO treeupdatesactions VALUES (?, ?, ?, ?, ?)
        """, updates)

    def removeTreeUpdatesActions(self, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM treeupdatesactions WHERE repository = ?
        """, (repository,))

    def insertTreeUpdatesActions(self, updates, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        myupdates = [[repository]+list(x) for x in updates]
        self._cursor().executemany("""
        INSERT INTO treeupdatesactions VALUES (NULL, ?, ?, ?, ?)
        """, myupdates)

    def setRepositoryUpdatesDigest(self, repository, digest):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM treeupdates where repository = ?
        """, (repository,))
        self._cursor().execute("""
        INSERT INTO treeupdates VALUES (?, ?)
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
        INSERT INTO treeupdatesactions VALUES (NULL, ?, ?, ?, ?)
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
        SELECT idupdate FROM treeupdatesactions
        WHERE repository = ? and command = ?
        and branch = ? LIMIT 1
        """, (repository, command, branch,))

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

        self._cursor().executemany('INSERT INTO packagesets VALUES (?, ?)',
            mysets)

    def retrievePackageSets(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("SELECT setname, dependency FROM packagesets")

        sets = {}
        for setname, dependency in cur:
            obj = sets.setdefault(setname, set())
            obj.add(dependency)
        return sets

    def retrievePackageSet(self, setname):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT dependency FROM packagesets WHERE setname = ?""",
            (setname,))
        return self._cur2frozenset(cur)

    def retrieveAtom(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT atom FROM baseinfo WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        atom = cur.fetchone()
        if atom:
            return atom[0]

    def retrieveBranch(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT branch FROM baseinfo WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        branch = cur.fetchone()
        if branch:
            return branch[0]

    def retrieveTrigger(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT data FROM triggers WHERE idpackage = ? LIMIT 1
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
        SELECT download FROM extrainfo WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        download = cur.fetchone()
        if download:
            return download[0]

    def retrieveDescription(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT description FROM extrainfo WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        description = cur.fetchone()
        if description:
            return description[0]

    def retrieveHomepage(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT homepage FROM extrainfo WHERE idpackage = ? LIMIT 1
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
        WHERE counters.idpackage = ? AND
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
        SELECT size FROM extrainfo WHERE idpackage = ? LIMIT 1
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
        SELECT size FROM sizes WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        size = cur.fetchone()
        if size:
            return size[0]
        return 0

    def retrieveDigest(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT digest FROM extrainfo WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        digest = cur.fetchone()
        if digest:
            return digest[0]
        return None

    def retrieveSignatures(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT sha1, sha256, sha512, gpg FROM packagesignatures
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        data = cur.fetchone()

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
            down_type_str = " AND down_type = ?"
            params.append(down_type)

        cur = self._cursor().execute("""
        SELECT download, type, size, disksize, md5, sha1,
            sha256, sha512, gpg
        FROM packagedownloads WHERE idpackage = ?
        """ + down_type_str, params)

        result = []
        for download, d_type, size, d_size, md5, sha1, sha256, sha512, gpg in \
                cur:
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
        SELECT name FROM baseinfo WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        name = cur.fetchone()
        if name:
            return name[0]

    def retrieveKeySplit(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT category, name FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        return cur.fetchone()

    def retrieveKeySlot(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT CONCAT(category, '/', name), slot FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        return cur.fetchone()

    def retrieveKeySlotAggregated(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT CONCAT(category, '/', name, '%s', slot) FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """ % (etpConst['entropyslotprefix'],), (package_id,))
        keyslot = cur.fetchone()
        if keyslot:
            return keyslot[0]
        return None

    def retrieveKeySlotTag(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT CONCAT(category, '/', name), slot,
        versiontag FROM baseinfo WHERE
        idpackage = ? LIMIT 1
        """, (package_id,))
        return cur.fetchone()

    def retrieveVersion(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT version FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        version = cur.fetchone()
        if version:
            return version[0]
        return None

    def retrieveRevision(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT revision FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        rev = cur.fetchone()
        if rev:
            return rev[0]
        return None

    def retrieveCreationDate(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT datecreation FROM extrainfo WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        date = cur.fetchone()
        if date:
            return date[0]

    def retrieveApi(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT etpapi FROM baseinfo WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        api = cur.fetchone()
        if api:
            return api[0]

    def retrieveUseflags(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT useflagsreference.flagname
        FROM useflags, useflagsreference
        WHERE useflags.idpackage = ?
        AND useflags.idflag = useflagsreference.idflag
        """, (package_id,))
        return self._cur2frozenset(cur)

    def retrieveSpmPhases(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT phases FROM packagespmphases WHERE idpackage = ? LIMIT 1
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
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        spm_repo = cur.fetchone()

        if spm_repo:
            return spm_repo[0]

    def retrieveDesktopMime(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT name, mimetype, executable, icon FROM packagedesktopmime
        WHERE idpackage = ?""", (package_id,))
        data = []
        for row in cur:
            item = {}
            item['name'], item['mimetype'], item['executable'], \
                item['icon'] = row
            data.append(item)
        return data

    def retrieveProvidedMime(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT mimetype FROM provided_mime WHERE idpackage = ?
        """, (package_id,))
        return self._cur2frozenset(cur)

    def retrieveNeededRaw(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT library FROM needed,neededreference
        WHERE needed.idpackage = ? AND
        needed.idneeded = neededreference.idneeded""", (package_id,))
        return self._cur2frozenset(cur)

    def retrieveNeeded(self, package_id, extended = False, formatted = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if extended:

            cur = self._cursor().execute("""
            SELECT library,elfclass FROM needed,neededreference
            WHERE needed.idpackage = ? AND
            needed.idneeded = neededreference.idneeded ORDER BY library
            """, (package_id,))
            needed = tuple(cur)

        else:

            cur = self._cursor().execute("""
            SELECT library FROM needed,neededreference
            WHERE needed.idpackage = ? AND
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
        WHERE idpackage = ?
        """, (package_id,))
        return frozenset(cur)

    def retrieveConflicts(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT conflict FROM conflicts WHERE idpackage = ?
        """, (package_id,))
        return self._cur2frozenset(cur)

    def retrieveProvide(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # be optimistic, _doesColumnInTableExist is very slow.
        cur = self._cursor().execute("""
        SELECT atom,is_default FROM provide WHERE idpackage = ?
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
        WHERE dependencies.idpackage = ? AND
        dependencies.iddependency = dependenciesreference.iddependency %s
        UNION SELECT CONCAT('!', conflict) FROM conflicts
        WHERE idpackage = ?""" % (excluded_deptypes_query,),
        (package_id, package_id,))
        if resolve_conditional_deps:
            return frozenset(entropy.dep.expand_dependencies(
                    cur, [self]))
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
            depstring = 'and dependencies.type = ?'
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
            WHERE dependencies.idpackage = ? AND
            dependencies.iddependency =
            dependenciesreference.iddependency %s %s""" % (
                depstring, excluded_deptypes_query,), searchdata)
            return tuple(entropy.dep.expand_dependencies(
                    cur, [self]))
        else:
            cur = self._cursor().execute("""
            SELECT dependenciesreference.dependency
            FROM dependencies,dependenciesreference
            WHERE dependencies.idpackage = ? AND
            dependencies.iddependency =
            dependenciesreference.iddependency %s %s""" % (
                depstring, excluded_deptypes_query,), searchdata)
            return frozenset(entropy.dep.expand_dependencies(
                    cur, [self]))

    def retrieveKeywords(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT keywordname FROM keywords,keywordsreference
        WHERE keywords.idpackage = ? AND
        keywords.idkeyword = keywordsreference.idkeyword""", (package_id,))
        return self._cur2frozenset(cur)

    def retrieveProtect(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT protect FROM configprotect,configprotectreference
        WHERE configprotect.idpackage = ? AND
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
        WHERE idpackage = ? AND
        configprotectmask.idprotect = configprotectreference.idprotect
        LIMIT 1
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
        WHERE idpackage = ? AND
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
        SELECT configfile, md5 FROM automergefiles WHERE idpackage = ?
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

        cur = self._cursor().execute("""
        SELECT %s file%s FROM content WHERE idpackage = ? %s""" % (
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

        return fl

    def retrieveContentIter(self, package_id, order_by = None,
                            reverse = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        class MyIter:

            def __init__(self, _cur):
                self._cur = cur

            def __iter__(self):
                return self

            def next(self):
                return self._cur.next()

        searchkeywords = (package_id,)
        order_by_string = ''
        if order_by is not None:
            if order_by not in ("package_id", "idpackage", "file", "type",):
                raise AttributeError("invalid order_by argument")
            if order_by == "package_id":
                order_by = "idpackage"
            ordering_term = "ASC"
            if reverse:
                ordering_term = "DESC"
            order_by_string = " order by %s %s" % (
                order_by, ordering_term)

        cur = self._cursor().execute("""
        SELECT file, type FROM content WHERE idpackage = ? %s""" % (
            order_by_string,), searchkeywords)
        return MyIter(cur)

    def retrieveContentSafety(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT file, sha256, mtime from contentsafety WHERE idpackage = ?
        """, (package_id,))
        return dict((path, {'sha256': sha256, 'mtime': mtime}) for path, \
            sha256, mtime in cur)

    def retrieveContentSafetyIter(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        class MyIter:

            def __init__(self, _cur):
                self._cur = cur

            def __iter__(self):
                return self

            def next(self):
                return self._cur.next()

        cur = self._cursor().execute("""
        SELECT file, sha256, mtime from contentsafety WHERE idpackage = ?
        """, (package_id,))
        return MyIter(cur)
        return dict((path, {'sha256': sha256, 'mtime': mtime}) for path, \
            sha256, mtime in cur)

    def retrieveChangelog(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT packagechangelogs.changelog
        FROM packagechangelogs, baseinfo
        WHERE baseinfo.idpackage = ? AND
        packagechangelogs.category = baseinfo.category AND
        packagechangelogs.name = baseinfo.name
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
        SELECT changelog FROM packagechangelogs WHERE category = ? AND
        name = ? LIMIT 1
        """, (category, name,))

        changelog = cur.fetchone()
        if changelog:
            return const_convert_to_unicode(changelog[0])

    def retrieveSlot(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT slot FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        slot = cur.fetchone()
        if slot:
            return slot[0]
        return None

    def retrieveTag(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT versiontag FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        tag = cur.fetchone()
        if tag:
            return tag[0]
        return None

    def retrieveMirrorData(self, mirrorname):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT mirrorlink FROM mirrorlinks WHERE mirrorname = ?
        """, (mirrorname,))
        return self._cur2frozenset(cur)

    def retrieveCategory(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT category FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        category = cur.fetchone()
        if category:
            return category[0]
        return None

    def retrieveCategoryDescription(self, category):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT description, locale FROM categoriesdescription
        WHERE category = ?
        """, (category,))

        return dict((locale, desc,) for desc, locale in cur)

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
            SELECT text FROM licensedata WHERE licensename = ? LIMIT 1
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
            SELECT licensename FROM licensedata WHERE licensename = ? LIMIT 1
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
        SELECT text FROM licensedata WHERE licensename = ? LIMIT 1
        """, (license_name,))

        text = cur.fetchone()
        if text:
            return const_convert_to_rawstring(text[0])

    def retrieveLicense(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT license FROM baseinfo
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))

        licname = cur.fetchone()
        if licname:
            return licname[0]

    def retrieveCompileFlags(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT chost,cflags,cxxflags FROM extrainfo
        WHERE extrainfo.idpackage = ? LIMIT 1""", (package_id,))
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
            if extended:
                cur = self._cursor().execute("""
                SELECT CONCAT(baseinfo.category, '/', baseinfo.name),
                    baseinfo.slot, dependenciesreference.dependency
                FROM baseinfo, dependencies, dependenciesreference
                WHERE baseinfo.idpackage = dependencies.idpackage %s AND
                dependencies.iddependency =
                    dependenciesreference.iddependency AND
                dependencies.iddependency IN ( %s )""" % (
                    excluded_deptypes_query, dep_ids_str,))
            else:
                cur = self._cursor().execute("""
                SELECT CONCAT(baseinfo.category, '/', baseinfo.name),
                    baseinfo.slot
                FROM baseinfo, dependencies
                WHERE baseinfo.idpackage = dependencies.idpackage %s AND
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
        WHERE idpackage IN (%s) LIMIT 1""" % (','.join(
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
        SELECT idpackage FROM baseinfo WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        result = cur.fetchone()
        if not result:
            return False
        return True

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
        SELECT idprotect FROM configprotectreference WHERE protect = ? LIMIT 1
        """, (protect,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def isFileAvailable(self, path, get_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM content WHERE file = ?""", (path,))
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
            elfclass_txt = ' AND provided_libs.elfclass = ?'
            args = (needed, elfclass,)

        if extended:
            cur = self._cursor().execute("""
            SELECT idpackage, path FROM provided_libs
            WHERE library = ?""" + elfclass_txt, args)
            return frozenset(cur)

        cur = self._cursor().execute("""
        SELECT idpackage FROM provided_libs
        WHERE library = ?""" + elfclass_txt, args)
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
        SELECT idsource FROM sourcesreference WHERE source = ? LIMIT 1
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
        SELECT iddependency FROM dependenciesreference WHERE dependency = ?
        LIMIT 1
        """, (dependency,))
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
        SELECT idkeyword FROM keywordsreference WHERE keywordname = ? LIMIT 1
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
        SELECT idflag FROM useflagsreference WHERE flagname = ? LIMIT 1
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
        SELECT idneeded FROM neededreference WHERE library = ? LIMIT 1
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
        SELECT counter FROM counters WHERE counter = ? LIMIT 1
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
        SELECT counter FROM trashedcounters WHERE counter = ? LIMIT 1
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
        SELECT licensename FROM licensedata WHERE licensename = ? LIMIT 1
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
        SELECT licensename FROM licenses_accepted WHERE licensename = ? LIMIT 1
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
        super(EntropyMySQLRepository, self).acceptLicense(license_name)

        self._cursor().execute("""
        INSERT IGNORE INTO licenses_accepted VALUES (?)
        """, (license_name,))

    def isSystemPackage(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM systempackages WHERE idpackage = ? LIMIT 1
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
        SELECT idpackage FROM injected WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        result = cur.fetchone()
        if result:
            return True
        return False

    def searchBelongs(self, bfile, like = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if like:
            cur = self._cursor().execute("""
            SELECT content.idpackage FROM content,baseinfo
            WHERE file LIKE ? AND
            content.idpackage = baseinfo.idpackage""", (bfile,))
        else:
            cur = self._cursor().execute("""SELECT content.idpackage
            FROM content, baseinfo WHERE file = ?
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
        FROM contentsafety WHERE file = ?""", (sfile,))
        return tuple(({'package_id': x, 'path': y, 'sha256': z, 'mtime': m} for
            x, y, z, m in cur))

    def searchTaggedPackages(self, tag, atoms = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if atoms:
            cur = self._cursor().execute("""
            SELECT atom, idpackage FROM baseinfo WHERE versiontag = ?
            """, (tag,))
            return frozenset(cur)

        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo WHERE versiontag = ?
        """, (tag,))
        return self._cur2frozenset(cur)

    def searchRevisionedPackages(self, revision):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo WHERE revision = ?
        """, (revision,))
        return self._cur2frozenset(cur)

    def searchLicense(self, keyword, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not entropy.tools.is_valid_string(keyword):
            return frozenset()

        if just_id:
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM
            baseinfo WHERE LOWER(baseinfo.license) LIKE ?
            """, ("%"+keyword+"%".lower(),))
            return self._cur2frozenset(cur)
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom, baseinfo.idpackage FROM
            baseinfo WHERE LOWER(baseinfo.license) LIKE ?
            """, ("%"+keyword+"%".lower(),))
            return frozenset(cur)

    def searchSlotted(self, keyword, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if just_id:
            cur = self._cursor().execute("""
            SELECT idpackage FROM baseinfo WHERE slot = ?""", (keyword,))
            return self._cur2frozenset(cur)
        else:
            cur = self._cursor().execute("""
            SELECT atom, idpackage FROM baseinfo WHERE slot = ?
            """, (keyword,))
            return frozenset(cur)

    def searchKeySlot(self, key, slot):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo
        WHERE CONCAT(category, '/', name) = ? AND slot = ?
        """, (key, slot,))
        return self._cur2frozenset(cur)

    def searchKeySlotTag(self, key, slot, tag):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo
        WHERE CONCAT(category, '/', name) = ? AND slot = ?
        AND tag = ?
        """, (key, slot, tag))
        return self._cur2frozenset(cur)

    def searchNeeded(self, needed, elfclass = -1, like = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if like:
            needed = needed.replace("*", "%")
        elfsearch = ''
        search_args = (needed,)
        if elfclass != -1:
            elfsearch = ' AND needed.elfclass = ?'
            search_args = (needed, elfclass,)

        if like:
            cur = self._cursor().execute("""
            SELECT needed.idpackage FROM needed,neededreference
            WHERE library LIKE ? %s AND
            needed.idneeded = neededreference.idneeded
            """ % (elfsearch,), search_args)
        else:
            cur = self._cursor().execute("""
            SELECT needed.idpackage FROM needed,neededreference
            WHERE library = ? %s AND
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
            SELECT conflict FROM conflicts WHERE conflict LIKE ?
            """, (keyword,))
            return self._cur2tuple(cur)

        cur = self._cursor().execute("""
        SELECT idpackage, conflict FROM conflicts WHERE conflict LIKE ?
        """, (keyword,))
        return tuple(cur)

    def searchDependency(self, dep, like = False, multi = False,
        strings = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        sign = "="
        limit = ""
        if like:
            sign = "LIKE"
            dep = "%"+dep+"%"
        item = 'iddependency'
        if strings:
            item = 'dependency'
        if not multi:
            limit = "LIMIT 1"

        cur = self._cursor().execute("""
        SELECT %s FROM dependenciesreference WHERE dependency %s ? %s
        """ % (item, sign, limit), (dep,))

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
        SELECT idpackage FROM dependencies WHERE iddependency = ?
        """, (dependency_id,))
        return self._cur2frozenset(cur)

    def searchSets(self, keyword):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT DISTINCT(setname) FROM packagesets WHERE setname LIKE ?
        """, ("%"+keyword+"%",))

        return self._cur2frozenset(cur)

    def searchProvidedMime(self, mimetype):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT provided_mime.idpackage FROM provided_mime, baseinfo
        WHERE provided_mime.mimetype = ?
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
        WHERE soundex(%s) = soundex(?) ORDER BY %s
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
            slotstring = ' AND slot = ?'

        tagstring = ''
        if tag:
            searchkeywords += (tag,)
            tagstring = ' AND versiontag = ?'

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
                    WHERE t.atom LIKE ?
                UNION ALL
                SELECT %s FROM baseinfo d, provide as p
                    WHERE d.idpackage = p.idpackage
                    AND p.atom LIKE ?
            ) WHERE 1=1 %s %s %s
            """ % (search_elements, search_elements_all,
                search_elements_provide_all, slotstring, tagstring,
                order_by_string), searchkeywords)
        else:
            cur = self._cursor().execute("""
            SELECT DISTINCT %s FROM (
                SELECT %s FROM baseinfo t
                    WHERE LOWER(t.atom) LIKE ?
                UNION ALL
                SELECT %s FROM baseinfo d, provide as p
                    WHERE d.idpackage = p.idpackage
                    AND LOWER(p.atom) LIKE ?
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
            WHERE provide.atom = ? AND
            provide.idpackage = baseinfo.idpackage""", (keyword,))
        except MySQLProxy.exceptions().OperationalError:
            # TODO: remove this before 31-12-2011
            if self._doesColumnInTableExist("provide", "is_default"):
                # something is really wrong
                raise
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage,0 FROM baseinfo,provide
            WHERE provide.atom = ? AND
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
            query_str_list.append("LOWER(extrainfo.description) LIKE ?")
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
            AND useflagsreference.flagname = ?
            """, (keyword,))
            return self._cur2frozenset(cur)
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom, useflags.idpackage
            FROM baseinfo, useflags, useflagsreference
            WHERE useflags.idflag = useflagsreference.idflag
            AND baseinfo.idpackage = useflags.idpackage
            AND useflagsreference.flagname = ?
            """, (keyword,))
            return frozenset(cur)

    def searchHomepage(self, keyword, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if just_id:
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM extrainfo, baseinfo
            WHERE LOWER(extrainfo.homepage) LIKE ? AND
            baseinfo.idpackage = extrainfo.idpackage
            """, ("%"+keyword.lower()+"%",))
            return self._cur2frozenset(cur)
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom, baseinfo.idpackage FROM extrainfo, baseinfo
            WHERE LOWER(extrainfo.homepage) LIKE ? AND
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
            WHERE name = ?
            """ % (atomstring,), (keyword,))
        else:
            cur = self._cursor().execute("""
            SELECT %s idpackage FROM baseinfo
            WHERE LOWER(name) = ?
            """ % (atomstring,), (keyword.lower(),))

        if just_id:
            return self._cur2tuple(cur)
        return frozenset(cur)


    def searchCategory(self, keyword, like = False, just_id = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        like_string = "= ?"
        if like:
            like_string = "LIKE ?"

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

        if just_id:
            return self._cur2frozenset(cur)
        return frozenset(cur)

    def searchNameCategory(self, name, category, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if just_id:
            cur = self._cursor().execute("""
            SELECT idpackage FROM baseinfo
            WHERE name = ? AND category = ?
            """, (name, category))
            return self._cur2frozenset(cur)

        cur = self._cursor().execute("""
        SELECT atom, idpackage FROM baseinfo
        WHERE name = ? AND category = ?
        """, (name, category))
        return tuple(cur)

    def isPackageScopeAvailable(self, atom, slot, revision):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        searchdata = (atom, slot, revision,)
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo
        where atom = ?  AND slot = ? AND revision = ? LIMIT 1
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
        WHERE repository = ? AND from_branch = ? AND to_branch = ? LIMIT 1
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

        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo where category = ?
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

    def listAllTrashedSpmUids(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute('SELECT counter FROM trashedcounters')
        return self._cur2frozenset(cur)

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
        except MySQLProxy.exceptions().OperationalError:
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
        cur = self._cursor().execute("""
        SELECT download FROM packagedownloads
        """ + order_string)

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
            cur = self._cursor().execute("""
            SELECT count(file) FROM content LIMIT 1
            """)
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

        cur = self._cursor().execute(
            "SELECT DISTINCT category FROM baseinfo %s" % (
                order_by_string,))
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
        UPDATE baseinfo SET branch = ?
        WHERE idpackage = ?""", (tobranch, package_id,))
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
            SELECT setting_value FROM settings WHERE setting_name = ? LIMIT 1
            """, (setting_name,))
        except MySQLProxy.exceptions().Error:
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
        # Always force const_convert_to_unicode() to setting_value
        # and setting_name or "OR REPLACE" won't work (sqlite3 bug?)
        cur = self._cursor().execute("""
        REPLACE INTO settings VALUES (?, ?)
        """, (const_convert_to_unicode(setting_name),
              const_convert_to_unicode(setting_value),))
        self.__settings_cache.clear()

    def _setupInitialSettings(self):
        """
        Setup initial repository settings
        """
        query = """
        REPLACE INTO settings VALUES ("arch", '%s');
        """ % (etpConst['currentarch'],)
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

        if (current_schema_rev == EntropyMySQLRepository._SCHEMA_REVISION) and \
            (not os.getenv("ETP_REPO_SCHEMA_UPDATE")):
            return

        old_readonly = self._readonly
        self._readonly = False

        # !!! insert schema changes here

        self._readonly = old_readonly
        self._connection().commit()

        if not old_readonly:
            # it seems that it's causing locking issues
            # so, just execute it when in read/write mode
            self._setSetting("schema_revision",
                EntropyMySQLRepository._SCHEMA_REVISION)
            self._connection().commit()

    def integrity_check(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return

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
        if not (self._doesTableExist("extrainfo") and \
                    self._doesTableExist("baseinfo") and \
                    self._doesTableExist("keywords")):
            raise SystemDatabaseError(mytxt)

        # execute checksum
        _exceptions = (
            MySQLProxy.exceptions().OperationalError,
            MySQLProxy.exceptions().DatabaseError
            )
        try:
            self.checksum()
        except _exceptions as err:
            mytxt = "Repository is corrupted, checksum error"
            raise SystemDatabaseError("%s: %s" % (mytxt, err,))

    @staticmethod
    def importRepository(dumpfile, db, data = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        dumpfile = os.path.realpath(dumpfile)
        if not entropy.tools.is_valid_path_string(dumpfile):
            raise AttributeError("dumpfile value is invalid")
        if data is None:
            raise AttributeError(
                "connection data required (dict)")

        try:
            host, port, user, password = data['host'], \
                data['port'], data['user'], data['password']
        except KeyError as err:
            raise AttributeError(err)

        try:
            with open(dumpfile, "rb") as f_in:
                proc = subprocess.Popen(
                    ("/usr/bin/mysql",
                     "-u", user, "-h", host,
                     "-P", str(port), "-p" + password,
                     "-D", db), bufsize = -1, stdin = f_in)
                return proc.wait()
        except OSError:
            return 1

    def exportRepository(self, dumpfile):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        try:
            proc = subprocess.Popen(
                ("/usr/bin/mysqldump",
                 "-u", self._user, "-h", self._host,
                 "-P", str(self._port), "-p" + self._password,
                 "--databases", self._db), bufsize = -1, stdout = dumpfile)
            return proc.wait()
        except OSError:
            return 1

        raise NotImplementedError()

    def _listAllTables(self):
        """
        List all available tables in this repository database.

        @return: available tables
        @rtype: list
        """
        cur = self._cursor().execute("SHOW TABLES;")
        return self._cur2tuple(cur)

    def _doesTableExist(self, table, temporary = False):

        # NOTE: override cache when temporary is True
        if temporary:
            # temporary table do not pop-up with the statement below, so
            # we need to handle them with "care"
            try:
                cur = self._cursor().execute("""
                SELECT count(*) FROM `%s` LIMIT 1""" % (table,))
                cur.fetchone()
            except MySQLProxy.exceptions().OperationalError:
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

        exists = False
        query = "SHOW TABLES LIKE '%s'" % (table,)
        cur = self._cursor().execute(query)
        rslt = cur.fetchone() is not None

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

        exists = False
        try:
            cur = self._cursor().execute("""
            SHOW COLUMNS FROM `%s` WHERE field = `%s`
            """ % (column, table))
            rslt = cur.fetchone() is not None
        except MySQLProxy.exceptions().OperationalError:
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
        raise IOError("Not supported by MySQL Repository")

    def checksum(self, do_order = False, strict = True,
        strings = True, include_signatures = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
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
            return result

        if strict:
            cur = self._cursor().execute("""
            SELECT * FROM baseinfo
            %s""" % (package_id_order,))
        else:
            cur = self._cursor().execute("""
            SELECT idpackage, atom, name, version, versiontag, revision,
            branch, slot, etpapi, `trigger` FROM baseinfo
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

        c_hash = '0'
        d_hash = '0'
        e_hash = '0'

        if include_signatures:
            try:
                # be optimistic and delay if condition, _doesColumnInTableExist
                # is really slow
                cur = self._cursor().execute("""
                SELECT idpackage, sha1, gpg FROM
                packagesignatures %s""" % (package_id_order,))
            except MySQLProxy.exceptions().OperationalError:
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
            result = "%s:%s:%s:%s:%s" % (
                a_hash, b_hash, c_hash, d_hash, e_hash)

        return result

    def storeInstalledPackage(self, package_id, repoid, source = 0):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        REPLACE INTO installedtable VALUES (?, ?, ?)
        """, (package_id, repoid, source,))

    def getInstalledPackageRepository(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT repositoryname FROM installedtable
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        repo = cur.fetchone()
        if repo:
            return repo[0]
        return None

    def getInstalledPackageSource(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # be optimistic, delay _doesColumnInTableExist as much as
        # possible
        cur = self._cursor().execute("""
        SELECT source FROM installedtable
        WHERE idpackage = ? LIMIT 1
        """, (package_id,))
        source = cur.fetchone()
        if source:
            return source[0]
        return None

    def dropInstalledPackageFromStore(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM installedtable
        WHERE idpackage = ?""", (package_id,))

    def storeSpmMetadata(self, package_id, blob):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('INSERT INTO xpakdata VALUES (?, ?)',
            (package_id, const_get_buffer()(blob),)
        )

    def retrieveSpmMetadata(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT data from xpakdata where idpackage = ? LIMIT 1
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
        cur = self._cursor().execute("""
        SELECT repository, from_branch, post_migration_md5sum,
        post_upgrade_md5sum FROM entropy_branch_migration WHERE to_branch = ?
        """, (to_branch,))

        meta = {}
        for repo, from_branch, post_migration_md5, post_upgrade_md5 in cur:
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
        except MySQLProxy.exceptions().OperationalError:
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
        for table in self._listAllTables():
            cur = self._cursor().execute("""
            SHOW INDEX FROM `%s` WHERE Key_name != 'PRIMARY';
            """ % (table,))
            for index_tuple in cur:
                index = index_tuple[2]
                try:
                    self._cursor().execute(
                        "DROP INDEX `%s` ON `%s`" % (
                            index, table,))
                except MySQLProxy.exceptions().OperationalError:
                    continue
                except MySQLProxy.exceptions().IntegrityError as err:
                    errno = MySQLProxy.errno()
                    if err.errno != errno['ER_DROP_INDEX_FK']:
                        raise

    def createAllIndexes(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not self.__indexing:
            return

        self._createTrashedCountersIndex()
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

    def _createTrashedCountersIndex(self):
        try:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS trashedcounters_counter
            ON trashedcounters ( counter )""")
        except MySQLProxy.exceptions().OperationalError:
            pass

    def _createMirrorlinksIndex(self):
        try:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS mirrorlinks_mirrorname
            ON mirrorlinks ( mirrorname )""")
        except MySQLProxy.exceptions().OperationalError:
            pass

    def _createDesktopMimeIndex(self):
        try:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS packagedesktopmime_idpackage
            ON packagedesktopmime ( idpackage )""")
        except MySQLProxy.exceptions().OperationalError:
            pass

    def _createProvidedMimeIndex(self):
        try:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS provided_mime_idpackage
            ON provided_mime ( idpackage )""")
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS provided_mime_mimetype
            ON provided_mime ( mimetype )""")
        except MySQLProxy.exceptions().OperationalError:
            pass

    def _createPackagesetsIndex(self):
        try:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS packagesetsindex
            ON packagesets ( setname )""")
        except MySQLProxy.exceptions().OperationalError:
            pass

    def _createProvidedLibsIndex(self):
        try:
            self._cursor().executescript("""
                CREATE INDEX IF NOT EXISTS provided_libs_idpackage
                ON provided_libs ( idpackage );
                CREATE INDEX IF NOT EXISTS provided_libs_lib_elf
                ON provided_libs ( library, elfclass );
            """)
        except MySQLProxy.exceptions().OperationalError:
            pass

    def _createAutomergefilesIndex(self):
        try:
            self._cursor().executescript("""
                CREATE INDEX IF NOT EXISTS automergefiles_idpackage
                ON automergefiles ( idpackage );
                CREATE INDEX IF NOT EXISTS automergefiles_file_md5
                ON automergefiles ( configfile, md5 );
            """)
        except MySQLProxy.exceptions().OperationalError:
            pass

    def _createPackageDownloadsIndex(self):
        try:
            self._cursor().executescript("""
                CREATE INDEX IF NOT EXISTS packagedownloads_idpackage_type
                ON packagedownloads ( idpackage, type );
            """)
        except MySQLProxy.exceptions().OperationalError:
            pass

    def _createNeededIndex(self):
        try:
            self._cursor().executescript("""
                CREATE INDEX IF NOT EXISTS neededindex ON neededreference
                    ( library );
                CREATE INDEX IF NOT EXISTS neededindex_idpk_idneeded ON needed
                    ( idpackage, idneeded );
                CREATE INDEX IF NOT EXISTS neededindex_idn_elfclass ON needed
                    ( idneeded, elfclass );
            """)
        except MySQLProxy.exceptions().OperationalError:
            pass

    def _createUseflagsIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS useflagsindex_useflags_idpackage
            ON useflags ( idpackage );
        CREATE INDEX IF NOT EXISTS useflagsindex_useflags_idflag
            ON useflags ( idflag );
        CREATE INDEX IF NOT EXISTS useflagsindex_useflags_idflag_idpk
            ON useflags ( idflag, idpackage );
        CREATE INDEX IF NOT EXISTS useflagsindex
            ON useflagsreference ( flagname );
        """)

    def _createContentIndex(self):
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
            ON baseinfo ( name, branch );
        """)
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS baseindex_branch_name_category
            ON baseinfo ( name, category, branch );
        CREATE INDEX IF NOT EXISTS baseindex_category
            ON baseinfo ( category );
        """)

    def _createLicensedataIndex(self):
        self._cursor().execute("""
        CREATE INDEX IF NOT EXISTS licensedataindex
            ON licensedata ( licensename )
        """)

    def _createKeywordsIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS keywordsreferenceindex
            ON keywordsreference ( keywordname );
        CREATE INDEX IF NOT EXISTS keywordsindex_idpackage_idkw
            ON keywords ( idpackage, idkeyword );
        """)

    def _createDependenciesIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS dependenciesindex_idpk_iddp_type
            ON dependencies ( idpackage, iddependency, type );
        CREATE INDEX IF NOT EXISTS dependenciesreferenceindex_dependency
            ON dependenciesreference ( dependency );
        """)

    def _createCountersIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS countersindex_counter_branch_idpk
            ON counters ( counter, branch, idpackage );
        """)

    def _createSourcesIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS sourcesindex_idpk_idsource
            ON sources ( idpackage, idsource );
        CREATE INDEX IF NOT EXISTS sourcesindex_idsource
            ON sources ( idsource );
        CREATE INDEX IF NOT EXISTS sourcesreferenceindex_source
            ON sourcesreference ( source );
        """)

    def _createProvideIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS provideindex_idpk_atom
            ON provide ( idpackage, atom );
        """)

    def _createConflictsIndex(self):
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS conflictsindex_idpackage
            ON conflicts ( idpackage );
        """)

    def _createExtrainfoIndex(self):
        # no indexes set. However, we may need two of them on
        # datecreation and download (two separate I mean)
        # to speed up ORDER BY datecreation and ORDER BY download.
        # Even though, listAllPackageIds(order_by="date") and
        # listAllDownloads(do_sort=True) are not critical
        # functions.
        pass

    def regenerateSpmUidMapping(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        spm = get_spm(self)

        # this is necessary now, counters table should be empty
        self._cursor().executescript("""
        DROP TABLE IF EXISTS counters_regen;
        CREATE TEMPORARY TABLE counters_regen (
            counter INTEGER(10),
            idpackage INTEGER(10),
            branch VARCHAR(75),
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
        REPLACE into counters_regen VALUES (?, ?, ?)
        """, insert_data)

        self._cursor().executescript("""
        DELETE FROM counters;
        INSERT INTO counters (counter, idpackage, branch)
            SELECT counter, idpackage, branch FROM counters_regen;
        """)

    def clearTreeupdatesEntries(self, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM treeupdates WHERE repository = ?
        """, (repository,))

    def resetTreeupdatesDigests(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('UPDATE treeupdates SET digest = "-1"')

    def __generateReverseDependenciesMetadata(self):
        """
        Reverse dependencies dynamic metadata generation.
        """
        checksum = self.checksum()
        try:
            mtime = repr(self.mtime())
        except (OSError, IOError):
            mtime = "0.0"
        hash_str = "%s|%s|%s|%s|%s" % (
            repr(self._db),
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

        self._setLiveCache("reverseDependenciesMetadata", dep_data)
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
        UPDATE counters SET branch = ?
        """, (to_branch,))
        self.clearCache()
