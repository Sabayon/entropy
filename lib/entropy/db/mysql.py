# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    I{EntropyRepository} is the MySQL implementation of the repository
    interface.

"""
import os
import hashlib
import time
try:
    import thread
except ImportError:
    import _thread as thread
import threading
import subprocess

from entropy.const import etpConst, const_debug_write, \
    const_convert_to_unicode, const_pid_exists

import entropy.dep
import entropy.tools

from entropy.db.sql import EntropySQLRepository, SQLConnectionWrapper, \
    SQLCursorWrapper

from entropy.db.exceptions import Warning, Error, InterfaceError, \
    DatabaseError, DataError, OperationalError, IntegrityError, \
    InternalError, ProgrammingError, NotSupportedError, RestartTransaction

class MySQLCursorWrapper(SQLCursorWrapper):

    """
    This class wraps a MySQL cursor and
    makes execute(), executemany() return
    the cursor itself.
    """

    def __init__(self, cursor, exceptions, errno):
        self._errno = errno
        self._conn_wr = cursor.connection
        super(MySQLCursorWrapper, self).__init__(cursor, exceptions)

    def _proxy_call(self, *args, **kwargs):
        """
        Reimplemented from SQLCursorWrapper.
        Raise RestartTransaction if MySQL fails to execute
        the query due to a detected deadlock.
        """
        try:
            return super(MySQLCursorWrapper, self)._proxy_call(
                *args, **kwargs)
        except ProgrammingError as err:
            tx_errnos = (
                self._errno['ER_LOCK_WAIT_TIMEOUT'],
                self._errno['ER_LOCK_DEADLOCK'])
            if err.args[0].errno in tx_errnos:
                const_debug_write(
                    __name__,
                    "deadlock detected, asking to restart transaction")
                # rollback, is it needed?
                self._conn_wr.rollback()
                raise RestartTransaction(err.args[0])
            raise

    def wrap(self, method, *args, **kwargs):
        return self._proxy_call(method, *args, **kwargs)

    def execute(self, *args, **kwargs):
        # force oursql to empty the resultset
        self._cur = self._cur.connection.cursor()
        self._proxy_call(self._cur.execute, *args, **kwargs)
        return self

    def executemany(self, *args, **kwargs):
        # force oursql to empty the resultset
        self._cur = self._cur.connection.cursor()
        self._proxy_call(self._cur.executemany, *args, **kwargs)
        return self

    def close(self, *args, **kwargs):
        return self._proxy_call(self._cur.close, *args, **kwargs)

    def fetchone(self, *args, **kwargs):
        return self._proxy_call(self._cur.fetchone, *args, **kwargs)

    def fetchall(self, *args, **kwargs):
        return self._proxy_call(self._cur.fetchall, *args, **kwargs)

    def fetchmany(self, *args, **kwargs):
        return self._proxy_call(self._cur.fetchmany, *args, **kwargs)

    def executescript(self, script):
        for sql in script.split(";"):
            if not sql.strip():
                continue
            self.execute(sql)
        return self

    def callproc(self, *args, **kwargs):
        return self._proxy_call(self._cur.callproc, *args, **kwargs)

    def nextset(self, *args, **kwargs):
        return self._proxy_call(self._cur.nextset, *args, **kwargs)

    def __iter__(self):
        cur = iter(self._cur)
        return MySQLCursorWrapper(cur, self._excs)

    def __next__(self):
        return self.wrap(next, self._cur)

    def next(self):
        return self.wrap(self._cur.next)


class MySQLConnectionWrapper(SQLConnectionWrapper):

    """
    This class wraps a MySQL connection and
    makes execute(), executemany() return
    the connection itself.
    """

    def __init__(self, connection, exceptions):
        SQLConnectionWrapper.__init__(self, connection, exceptions)

    def interrupt(self):
        """
        Reimplemented from SQLConnectionWrapper.
        """
        # Not supported by MySQL, NO-OP
        return

    def ping(self):
        """
        Reimplemented from SQLConnectionWrapper.
        """
        return self._proxy_call(self._excs, self._con.ping)

    def unicode(self):
        """
        Reimplemented from SQLConnectionWrapper.
        """
        # This is a NO-OP, we are always unicode
        return


class EntropyMySQLRepository(EntropySQLRepository):

    """
    EntropyMySQLRepository implements MySQL based storage. In a Model-View based
    design pattern, this can be considered the "model".
    """

    # bump this every time schema changes and databaseStructureUpdate
    # should be triggered
    _SCHEMA_REVISION = 1

    _INSERT_OR_REPLACE = "REPLACE"
    _INSERT_OR_IGNORE = "INSERT IGNORE"
    _UPDATE_OR_REPLACE = None

    class MySQLSchema(object):

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
                    mtime REAL,
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

                CREATE TABLE needed_libs (
                    idpackage INTEGER(10) UNSIGNED NOT NULL,
                    lib_user_path VARCHAR(512) NOT NULL,
                    lib_user_soname VARCHAR(75) NOT NULL,
                    soname VARCHAR(75) NOT NULL,
                    elfclass INTEGER(10) NOT NULL,
                    rpath VARCHAR(1024) NOT NULL,
                    FOREIGN KEY(idpackage)
                        REFERENCES baseinfo(idpackage) ON DELETE CASCADE
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

    class MySQLProxy(object):

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
            if EntropyMySQLRepository.MySQLProxy._mod is None:
                with EntropyMySQLRepository.MySQLProxy._lock:
                    if EntropyMySQLRepository.MySQLProxy._mod is None:
                        import oursql
                        EntropyMySQLRepository.MySQLProxy._excs = oursql
                        EntropyMySQLRepository.MySQLProxy._mod = oursql
                        EntropyMySQLRepository.MySQLProxy._errnos = \
                            oursql.errnos
            return EntropyMySQLRepository.MySQLProxy._mod

        @staticmethod
        def exceptions():
            """
            Get the MySQL exceptions module.
            """
            _mod = EntropyMySQLRepository.MySQLProxy.get()
            return EntropyMySQLRepository.MySQLProxy._excs

        @staticmethod
        def errno():
            """
            Get the MySQL errno module.
            """
            _mod = EntropyMySQLRepository.MySQLProxy.get()
            return EntropyMySQLRepository.MySQLProxy._errnos

    Schema = MySQLSchema
    ModuleProxy = MySQLProxy

    def __init__(self, uri, readOnly = False, xcache = False,
                 name = None, indexing = True, skipChecks = False,
                 direct = False):
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
        @keyword direct: True, if direct mode should be always enabled
        @type direct: bool
        """
        self._mysql = self.ModuleProxy.get()

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
                db = ":".join(db_port.split(":")[:-1])
            else:
                db = db_port
        except IndexError:
            raise DatabaseError("Invalid Database Name")

        if db == ":memory:":
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
            self._port = EntropyMySQLRepository.MySQLProxy.PORT
        except ValueError:
            raise DatabaseError("Invalid Port")

        EntropySQLRepository.__init__(
            self, db, readOnly, skipChecks, indexing,
            xcache, False, name)

        self.__structure_update = False
        if not self._skip_checks:

            try:
                if self._doesTableExist('baseinfo') and \
                        self._doesTableExist('extrainfo'):
                    self.__structure_update = True

            except Error:
                self._cleanup_all(
                    _cleanup_main_thread=False)
                raise

        if self.__structure_update:
            self._databaseStructureUpdates()

    def _concatOperator(self, fields):
        """
        Reimplemented from EntropySQLRepository.
        """
        return "CONCAT(" + ", ".join(fields) + ")"

    def _cursor(self):
        """
        Reimplemented from EntropySQLRepository.
        """
        current_thread = threading.current_thread()
        c_key = self._cursor_connection_pool_key()

        cursor = None
        with self._cursor_pool_mutex():
            threads = set()
            cursor_pool = self._cursor_pool()
            cursor_data = cursor_pool.get(c_key)
            if cursor_data is not None:
                cursor, threads = cursor_data
            # handle possible thread ident clashing
            # in the cleanup thread function, because
            # thread idents are recycled
            # on thread termination
            threads.add(current_thread)

            if cursor is None:
                conn = self._connection_impl(_from_cursor=True)
                cursor = conn.cursor()
                cursor.execute("SET storage_engine=InnoDB;")
                cursor.execute("SET autocommit=OFF;")
                cursor = MySQLCursorWrapper(
                    cursor, self.ModuleProxy.exceptions(),
                    self.ModuleProxy().errno())
                cursor_pool[c_key] = cursor, threads
                self._start_cleanup_monitor(current_thread, c_key)

        return cursor

    def _connection_impl(self, _from_cursor=False):
        """
        Connection getter method implementation, adds
        _from_cursor argument to avoid calling the
        cleanup routine if True.
        """
        current_thread = threading.current_thread()
        c_key = self._cursor_connection_pool_key()

        conn = None
        with self._connection_pool_mutex():
            threads = set()
            connection_pool = self._connection_pool()
            conn_data = connection_pool.get(c_key)
            if conn_data is not None:
                conn, threads = conn_data
            # handle possible thread ident clashing
            # in the cleanup thread function
            # because thread idents are recycled on
            # thread termination
            threads.add(current_thread)

            if conn is None:
                conn = MySQLConnectionWrapper.connect(
                    self.ModuleProxy, self._mysql,
                    MySQLConnectionWrapper,
                    host = self._host, user = self._user,
                    passwd = self._password, db = self._db,
                    port = self._port, autoreconnect = True)
                connection_pool[c_key] = conn, threads
                if not _from_cursor:
                    self._start_cleanup_monitor(current_thread, c_key)
            else:
                conn.ping()
        return conn

    def _connection(self):
        """
        Reimplemented from EntropySQLRepository.
        """
        return self._connection_impl()

    def __show_info(self):
        password = hashlib.new("md5")
        password.update(self._password)
        first_part = "<EntropyRepository instance at " + \
        "%s - host: %s, db: %s, port: %s, user: %s, hpass: %s" % (
            hex(id(self)), self._host, self._db, self._port, self._user,
            password.hexdigest(),)
        second_part = ", ro: %s|%s, caching: %s, indexing: %s" % (
            self._readonly, self.readonly(), self.caching(),
            self._indexing,)
        third_part = ", name: %s, skip_upd: %s, st_upd: %s" % (
            self.name, self._skip_checks, self.__structure_update,)
        fourth_part = ", conn_pool: %s, cursor_cache: %s>" % (
            self._connection_pool(), self._cursor_pool(),)

        return first_part + second_part + third_part + fourth_part

    def __repr__(self):
        return self.__show_info()

    def __str__(self):
        return self.__show_info()

    def __unicode__(self):
        return self.__show_info()

    def close(self, safe=False):
        """
        Reimplemented from EntropyRepositoryBase.
        Needs to call superclass method.
        """
        super(EntropyMySQLRepository, self).close()

        self._cleanup_all(_cleanup_main_thread=not safe)
        # live cache must be discarded every time the repository is closed
        # in order to avoid data mismatches for long-running processes
        # that load and unload Entropy Framework often.
        # like "client-updates-daemon".
        self._discardLiveCache()

    def vacuum(self):
        """
        Reimplemented from EntropyRepositoryBase.
        @todo: should it run OPTIMIZE TABLE for each table?
        """
        return

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
                    cur = self._cursor().execute(
                        "DROP TABLE %s" % (table,))
                except OperationalError:
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

    def setSpmUid(self, package_id, spm_package_uid, branch = None):
        """
        Reimplemented from EntropySQLRepository.
        Specialized version that only handles UNIQUE
        constraint violations.
        """
        branchstring = ''
        insertdata = (spm_package_uid, package_id)
        if branch:
            branchstring = ', branch = (?)'
            insertdata += (branch,)

        try:
            cur = self._cursor().execute("""
            UPDATE counters SET counter = ? %s
            WHERE idpackage = ?""" % (branchstring,), insertdata)
        except IntegrityError as err:
            errno = self.ModuleProxy.errno()
            if err.args[0].errno != errno['ER_DUP_ENTRY']:
                raise
            # fallback to replace
            cur = self._cursor().execute("""
            REPLACE INTO counters SET counter = ? %s
            WHERE idpackage = ?""" % (branchstring,), insertdata)

    def handlePackage(self, pkg_data, revision = None,
                      formattedContent = False):
        """
        Reimplemented from EntropySQLRepository.
        """
        raise NotImplementedError()

    def _setupInitialSettings(self):
        """
        Setup initial repository settings
        """
        query = """
        REPLACE INTO settings VALUES ("arch", '%s');
        """ % (etpConst['currentarch'],)
        self._cursor().executescript(query)
        self.commit()
        self._settings_cache.clear()

    def _databaseStructureUpdates(self):
        """
        Do not forget to bump _SCHEMA_REVISION whenever
        you add more tables
        """
        try:
            current_schema_rev = int(self.getSetting("schema_revision"))
        except (KeyError, ValueError):
            current_schema_rev = -1

        if current_schema_rev == EntropyMySQLRepository._SCHEMA_REVISION \
                and not os.getenv("ETP_REPO_SCHEMA_UPDATE"):
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
        raise IOError("Not supported by MySQL Repository")

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
                except OperationalError:
                    continue
                except IntegrityError as err:
                    errno = self.ModuleProxy.errno()
                    if err.args[0].errno != errno['ER_DROP_INDEX_FK']:
                        raise
