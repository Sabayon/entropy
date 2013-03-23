# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    I{EntropySQLiteRepository} is the SQLite3 implementation of
    the repository interface.

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

from entropy.const import etpConst, const_convert_to_unicode, \
    const_get_buffer, const_convert_to_rawstring, const_pid_exists, \
    const_is_python3, const_debug_write
from entropy.exceptions import SystemDatabaseError
from entropy.output import bold, red, blue, purple

from entropy.db.exceptions import Warning, Error, InterfaceError, \
    DatabaseError, DataError, OperationalError, IntegrityError, \
    InternalError, ProgrammingError, NotSupportedError
from entropy.db.sql import EntropySQLRepository, SQLConnectionWrapper, \
    SQLCursorWrapper

from entropy.i18n import _

import entropy.dep
import entropy.tools


class SQLiteCursorWrapper(SQLCursorWrapper):

    """
    This class wraps a SQLite cursor in order to have
    it thrown entropy.db.exceptions objects.
    The API is a subset of the one specified in
    Python DBAPI 2.0.
    """

    def __init__(self, cursor, exceptions):
        super(SQLiteCursorWrapper, self).__init__(cursor, exceptions)

    def execute(self, *args, **kwargs):
        return self._proxy_call(self._cur.execute, *args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._proxy_call(self._cur.executemany, *args, **kwargs)

    def close(self, *args, **kwargs):
        return self._proxy_call(self._cur.close, *args, **kwargs)

    def fetchone(self, *args, **kwargs):
        return self._proxy_call(self._cur.fetchone, *args, **kwargs)

    def fetchall(self, *args, **kwargs):
        return self._proxy_call(self._cur.fetchall, *args, **kwargs)

    def fetchmany(self, *args, **kwargs):
        return self._proxy_call(self._cur.fetchmany, *args, **kwargs)

    def executescript(self, *args, **kwargs):
        return self._proxy_call(self._cur.executescript, *args, **kwargs)

    def callproc(self, *args, **kwargs):
        return self._proxy_call(self._cur.callproc, *args, **kwargs)

    def nextset(self, *args, **kwargs):
        return self._proxy_call(self._cur.nextset, *args, **kwargs)

    def __iter__(self):
        return iter(self._cur)


class SQLiteConnectionWrapper(SQLConnectionWrapper):
    """
    This class wraps a SQLite connection and
    makes execute(), executemany() return
    the connection itself.
    """

    def __init__(self, connection, exceptions):
        SQLConnectionWrapper.__init__(self, connection, exceptions)

    def ping(self):
        return

    def unicode(self):
        self._con.text_factory = const_convert_to_unicode

    def rawstring(self):
        self._con.text_factory = const_convert_to_rawstring

    def interrupt(self):
        return self._proxy_call(self._excs, self._con.interrupt)

    def _iterdump(self):
        return self._con.iterdump()


class EntropySQLiteRepository(EntropySQLRepository):

    """
    EntropySQLiteRepository implements SQLite3 based storage.
    In a Model-View based pattern, it can be considered the "model".
    Actually it's the only one available but more model backends will be
    supported in future (which will inherit this class directly).
    Beside the underlying SQLite3 calls are thread safe, you are responsible
    of the semantic of your calls.
    """

    # bump this every time schema changes and databaseStructureUpdate
    # should be triggered
    _SCHEMA_REVISION = 3

    _INSERT_OR_REPLACE = "INSERT OR REPLACE"
    _INSERT_OR_IGNORE = "INSERT OR IGNORE"
    _UPDATE_OR_REPLACE = "UPDATE OR REPLACE"

    SETTING_KEYS = ("arch", "on_delete_cascade", "schema_revision",
        "_baseinfo_extrainfo_2010")

    class SQLiteProxy(object):

        _mod = None
        _excs = None
        _lock = threading.Lock()

        @staticmethod
        def get():
            """
            Lazily load the SQLite3 module.
            """
            if EntropySQLiteRepository.SQLiteProxy._mod is None:
                with EntropySQLiteRepository.SQLiteProxy._lock:
                    if EntropySQLiteRepository.SQLiteProxy._mod is None:
                        from sqlite3 import dbapi2
                        EntropySQLiteRepository.SQLiteProxy._excs = dbapi2
                        EntropySQLiteRepository.SQLiteProxy._mod = dbapi2
            return EntropySQLiteRepository.SQLiteProxy._mod

        @staticmethod
        def exceptions():
            """
            Get the SQLite3 exceptions module.
            """
            _mod = EntropySQLiteRepository.SQLiteProxy.get()
            return EntropySQLiteRepository.SQLiteProxy._excs

        @staticmethod
        def errno():
            """
            Get the SQLite3 errno module (not avail).
            """
            raise NotImplementedError()

    ModuleProxy = SQLiteProxy

    def __init__(self, readOnly = False, dbFile = None, xcache = False,
        name = None, indexing = True, skipChecks = False, temporary = False):
        """
        EntropySQLiteRepository constructor.

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
        self._sqlite = self.ModuleProxy.get()

        EntropySQLRepository.__init__(
            self, dbFile, readOnly, skipChecks, indexing,
            xcache, temporary, name)

        if self._db is None:
            raise AttributeError("valid database path needed")

        # tracking mtime to validate repository Live cache as
        # well.
        try:
            self.__cur_mtime = self.mtime()
        except (OSError, IOError):
            self.__cur_mtime = None

        self.__structure_update = False
        if not self._skip_checks:

            if not entropy.tools.is_user_in_entropy_group():
                # forcing since we won't have write access to db
                self._indexing = False
            # live systems don't like wasting RAM
            if entropy.tools.islive() and not etpConst['systemroot']:
                self._indexing = False

            def _is_avail():
                if self._db == ":memory:":
                    return True
                return os.access(self._db, os.W_OK)

            try:
                if _is_avail() and self._doesTableExist('baseinfo') and \
                        self._doesTableExist('extrainfo'):

                    if entropy.tools.islive(): # this works
                        if etpConst['systemroot']:
                            self.__structure_update = True
                    else:
                        self.__structure_update = True

            except Error:
                self._cleanup_all(_cleanup_main_thread=False)
                raise

        if self.__structure_update:
            self._databaseStructureUpdates()

    def _concatOperator(self, fields):
        """
        Reimplemented from EntropySQLRepository.
        """
        return " || ".join(fields)

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

    def readonly(self):
        """
        Reimplemented from EntropySQLRepository.
        """
        if (not self._readonly) and (self._db != ":memory:"):
            if os.getuid() != 0:
                # make sure that user can write to file
                # before returning False, override actual
                # readonly status
                return not os.access(self._db, os.W_OK)
        return self._readonly

    def _cursor(self):
        """
        Reimplemented from EntropySQLRepository.
        """
        current_thread = threading.current_thread()
        c_key = self._cursor_connection_pool_key()

        _init_db = False
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
                cursor = SQLiteCursorWrapper(
                    conn.cursor(),
                    self.ModuleProxy.exceptions())
                # !!! enable foreign keys pragma !!! do not remove this
                # otherwise removePackage won't work properly
                cursor.execute("pragma foreign_keys = 1").fetchall()
                # setup temporary tables and indices storage
                # to in-memory value
                # http://www.sqlite.org/pragma.html#pragma_temp_store
                cursor.execute("pragma temp_store = 2").fetchall()
                cursor_pool[c_key] = cursor, threads
                self._start_cleanup_monitor(current_thread, c_key)
                _init_db = True
        # memory databases are critical because every new cursor brings
        # up a totally empty repository. So, enforce initialization.
        if _init_db and self._db == ":memory:":
            self.initializeRepository()
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
                # check_same_thread still required for
                # conn.close() called from
                # arbitrary thread
                conn = SQLiteConnectionWrapper.connect(
                    self.ModuleProxy, self._sqlite,
                    SQLiteConnectionWrapper,
                    self._db, timeout=30.0,
                    check_same_thread=False)
                connection_pool[c_key] = conn, threads
                if not _from_cursor:
                    self._start_cleanup_monitor(current_thread, c_key)
        return conn

    def _connection(self):
        """
        Reimplemented from EntropySQLRepository.
        """
        return self._connection_impl()

    def __show_info(self):
        first_part = "<EntropySQLiteRepository instance at %s, %s" % (
            hex(id(self)), self._db,)
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

    def __setCacheSize(self, size):
        """
        Change low-level, storage engine based cache size.

        @param size: new size
        @type size: int
        """
        self._cursor().execute('PRAGMA cache_size = %s' % (size,))

    def __setDefaultCacheSize(self, size):
        """
        Change default low-level, storage engine based cache size.

        @param size: new default size
        @type size: int
        """
        self._cursor().execute('PRAGMA default_cache_size = %s' % (size,))

    def _getLiveCache(self, key):
        """
        Reimplemented from EntropySQLRepository.
        """
        try:
            mtime = self.mtime()
        except (OSError, IOError):
            mtime = None
        if self.__cur_mtime != mtime:
            self.__cur_mtime = mtime
            self._discardLiveCache()
        return self._live_cacher.get(self._getLiveCacheKey() + key)

    def close(self, safe=False):
        """
        Reimplemented from EntropySQLRepository.
        Needs to call superclass method.
        """
        super(EntropySQLiteRepository, self).close(safe=safe)

        self._cleanup_all(_cleanup_main_thread=not safe)
        if self._temporary and (self._db != ":memory:") and \
            os.path.isfile(self._db):
            try:
                os.remove(self._db)
            except (OSError, IOError,):
                pass
        # live cache must be discarded every time the repository is closed
        # in order to avoid data mismatches for long-running processes
        # that load and unload Entropy Framework often.
        # like "client-updates-daemon".
        self._discardLiveCache()

    def vacuum(self):
        """
        Reimplemented from EntropySQLRepository.
        """
        self._cursor().execute("vacuum")

    def initializeRepository(self):
        """
        Reimplemented from EntropySQLRepository.
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
        self.__setCacheSize(8192)
        self.__setDefaultCacheSize(8192)
        self._databaseStructureUpdates()

        self.commit()
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")
        super(EntropySQLiteRepository, self).initializeRepository()

    def handlePackage(self, pkg_data, forcedRevision = -1,
        formattedContent = False):
        """
        Reimplemented from EntropySQLRepository.
        """
        raise NotImplementedError()

    def _removePackage(self, package_id, from_add_package = False):
        """
        Reimplemented from EntropySQLRepository.
        We must handle on_delete_cascade.
        """
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

    def _addCategory(self, category):
        """
        Reimplemented from EntropySQLRepository.
        """
        self._clearLiveCache("retrieveCategory")
        self._clearLiveCache("searchNameCategory")
        self._clearLiveCache("retrieveKeySlot")
        self._clearLiveCache("retrieveKeySplit")
        self._clearLiveCache("searchKeySlot")
        self._clearLiveCache("searchKeySlotTag")
        self._clearLiveCache("retrieveKeySlotAggregated")
        self._clearLiveCache("getStrictData")
        return super(EntropySQLiteRepository, self)._addCategory(category)

    def setCategory(self, package_id, category):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010 and live cache.
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

    def setName(self, package_id, name):
        """
        Reimplemented from EntropySQLRepository.
        We must handle live cache.
        """
        super(EntropySQLiteRepository, self).setName(package_id, name)
        self._clearLiveCache("searchNameCategory")
        self._clearLiveCache("retrieveKeySlot")
        self._clearLiveCache("retrieveKeySplit")
        self._clearLiveCache("searchKeySlot")
        self._clearLiveCache("searchKeySlotTag")
        self._clearLiveCache("retrieveKeySlotAggregated")
        self._clearLiveCache("getStrictData")

    def setAtom(self, package_id, atom):
        """
        Reimplemented from EntropySQLRepository.
        We must handle live cache.
        """
        super(EntropySQLiteRepository, self).setAtom(package_id, atom)
        self._clearLiveCache("searchNameCategory")
        self._clearLiveCache("getStrictScopeData")
        self._clearLiveCache("getStrictData")

    def setSlot(self, package_id, slot):
        """
        Reimplemented from EntropySQLRepository.
        We must handle live cache.
        """
        super(EntropySQLiteRepository, self).setSlot(package_id, slot)
        self._clearLiveCache("retrieveSlot")
        self._clearLiveCache("retrieveKeySlot")
        self._clearLiveCache("searchKeySlot")
        self._clearLiveCache("searchKeySlotTag")
        self._clearLiveCache("retrieveKeySlotAggregated")
        self._clearLiveCache("getStrictScopeData")
        self._clearLiveCache("getStrictData")

    def setRevision(self, package_id, revision):
        """
        Reimplemented from EntropySQLRepository.
        We must handle live cache.
        """
        super(EntropySQLiteRepository, self).setRevision(
            package_id, revision)
        self._clearLiveCache("retrieveRevision")
        self._clearLiveCache("getVersioningData")
        self._clearLiveCache("getStrictScopeData")
        self._clearLiveCache("getStrictData")

    def _insertUseflags(self, package_id, useflags):
        """
        Reimplemented from EntropySQLRepository.
        We must handle live cache.
        """
        super(EntropySQLiteRepository, self)._insertUseflags(
            package_id, useflags)
        self._clearLiveCache("retrieveUseflags")

    def _insertExtraDownload(self, package_id, package_downloads_data):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            # be optimistic and delay if condition
            super(EntropySQLiteRepository, self)._insertExtraDownload(
                package_id, package_downloads_data)
        except OperationalError as err:
            if self._doesTableExist("packagedownloads"):
                raise
            self._createPackageDownloadsTable()
            super(EntropySQLiteRepository, self)._insertExtraDownload(
                package_id, package_downloads_data)

    def _bindSpmPackageUid(self, package_id, spm_package_uid, branch):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self)._bindSpmPackageUid(
                package_id, spm_package_uid, branch)
        except IntegrityError:
            # we have a PRIMARY KEY we need to remove
            self._migrateCountersTable()
            return super(EntropySQLiteRepository,
                         self)._bindSpmPackageUid(
                package_id, spm_package_uid, branch)

    def _cleanupChangelogs(self):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        """
        if self._isBaseinfoExtrainfo2010():
            return super(EntropySQLiteRepository,
                         self)._cleanupChangelogs()

        # backward compatibility
        self._cursor().execute("""
        DELETE FROM packagechangelogs
        WHERE category || "/" || name NOT IN
        (SELECT categories.category || "/" || baseinfo.name
            FROM baseinfo, categories
            WHERE baseinfo.idcategory = categories.idcategory)
        """)

    def getVersioningData(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must use the in-memory cache to do some memoization.
        """
        cached = self._getLiveCache("getVersioningData")
        if cached is None:
            cur = self._cursor().execute("""
            SELECT idpackage, version, versiontag, revision FROM baseinfo
            """)
            cached = dict((pkg_id, (ver, tag, rev)) for pkg_id, ver, tag,
                rev in cur)
            self._setLiveCache("getVersioningData", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def getStrictData(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must use the in-memory cache to do some memoization.
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
            cached = dict((pkg_id, (key, slot, version, tag, rev, atom)) \
                              for pkg_id, key, slot, version, tag, \
                                  rev, atom in cur)
            self._setLiveCache("getStrictData", cached)

        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def getStrictScopeData(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must use the in-memory cache to do some memoization.
        """
        cached = self._getLiveCache("getStrictScopeData")
        if cached is None:
            cur = self._cursor().execute("""
            SELECT idpackage, atom, slot, revision FROM baseinfo
            """)
            cached = dict((pkg_id, (atom, slot, rev)) for pkg_id, \
                              atom, slot, rev in cur)
            self._setLiveCache("getStrictScopeData", cached)
        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def getScopeData(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        if self._isBaseinfoExtrainfo2010():
            return super(EntropySQLiteRepository, self).getScopeData(
                package_id)

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
        LIMIT 1
        """, (package_id,))
        return cur.fetchone()

    def getBaseData(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        if self._isBaseinfoExtrainfo2010():
            return super(EntropySQLiteRepository, self).getBaseData(
                package_id)

        # we must guarantee backward compatibility
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
        LIMIT 1
        """
        cur = self._cursor().execute(sql, (package_id,))
        return cur.fetchone()

    def retrieveDigest(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must use the in-memory cache to do some memoization.
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
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).retrieveSignatures(
                package_id)
        except OperationalError:
            data = None
            if self._doesTableExist("packagesignatures"):
                # TODO: drop after 2013?
                cur = self._cursor().execute("""
                SELECT sha1, sha256, sha512 FROM packagesignatures
                WHERE idpackage = (?) LIMIT 1
                """, (package_id,))
                data = cur.fetchone()
                if data:
                    data = data + (None,)
            if data:
                return data
            return None, None, None, None

    def retrieveExtraDownload(self, package_id, down_type = None):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).retrieveExtraDownload(
                package_id, down_type = down_type)
        except OperationalError:
            if self._doesTableExist("packagedownloads"):
                raise
            return tuple()

    def retrieveKeySplit(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must use the in-memory cache to do some memoization.
        We must handle _baseinfo_extrainfo_2010.
        """
        cached = self._getLiveCache("retrieveKeySplit")
        if cached is None:
            if self._isBaseinfoExtrainfo2010():
                cur = self._cursor().execute("""
                SELECT idpackage, category, name FROM baseinfo
                """)
            else:
                cur = self._cursor().execute("""
                SELECT baseinfo.idpackage, categories.category,
                    baseinfo.name
                FROM baseinfo, categories
                WHERE categories.idcategory = baseinfo.idcategory
                """)
            cached = dict((pkg_id, (category, name)) for pkg_id, category,
                name in cur)
            self._setLiveCache("retrieveKeySplit", cached)

        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def retrieveKeySlot(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        We must use the in-memory cache to do some memoization.
        We must handle _baseinfo_extrainfo_2010.
        """
        cached = self._getLiveCache("retrieveKeySlot")
        if cached is None:
            if self._isBaseinfoExtrainfo2010():
                cur = self._cursor().execute("""
                SELECT idpackage, category || "/" || name,
                    slot FROM baseinfo
                """)
            else:
                cur = self._cursor().execute("""
                SELECT baseinfo.idpackage,
                    categories.category || "/" || baseinfo.name,
                    baseinfo.slot
                FROM baseinfo, categories
                WHERE baseinfo.idcategory = categories.idcategory
                """)
            cached = dict((pkg_id, (key, slot)) for pkg_id, key, slot in \
                cur)
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
            SELECT categories.category || "/" || baseinfo.name,
                baseinfo.slot, baseinfo.versiontag
            FROM baseinfo, categories WHERE
            baseinfo.idpackage = (?) AND
            baseinfo.idcategory = categories.idcategory LIMIT 1
            """, (package_id,))
        return cur.fetchone()

    def retrieveVersion(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must use the in-memory cache to do some memoization.
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
        Reimplemented from EntropySQLRepository.
        We must use the in-memory cache to do some memoization.
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

    def retrieveUseflags(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must use the in-memory cache to do some memoization.
        """
        cached = self._getLiveCache("retrieveUseflags")
        if cached is None:
            cur = self._cursor().execute("""
            SELECT useflags.idpackage, useflagsreference.flagname
            FROM useflags, useflagsreference
            WHERE useflags.idflag = useflagsreference.idflag
            """)
            cached = {}
            for pkg_id, flag in cur:
                obj = cached.setdefault(pkg_id, set())
                obj.add(flag)
            self._setLiveCache("retrieveUseflags", cached)

        # avoid python3.x memleak
        obj = frozenset(cached.get(package_id, frozenset()))
        del cached
        return obj

    def retrieveDesktopMime(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).retrieveDesktopMime(package_id)
        except OperationalError:
            if self._doesTableExist("packagedesktopmime"):
                raise
            return []

    def retrieveProvidedMime(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).retrieveProvidedMime(package_id)
        except OperationalError:
            if self._doesTableExist("provided_mime"):
                raise
            return frozenset()

    def retrieveProvide(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                  self).retrieveProvide(package_id)
        except OperationalError as err:
            # TODO: remove after 2013?
            if self._doesColumnInTableExist("provide", "is_default"):
                raise
            cur = self._cursor().execute("""
            SELECT atom, 0 FROM provide WHERE idpackage = (?)
            """, (package_id,))
            return frozenset(cur)

    def retrieveContentSafety(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).retrieveContentSafety(package_id)
        except OperationalError:
            # TODO: remove after 2013?
            if self._doesTableExist('contentsafety'):
                raise
            return {}

    def retrieveContentSafetyIter(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).retrieveContentSafetyIter(package_id)
        except OperationalError:
            # TODO: remove after 2013?
            if self._doesTableExist('contentsafety'):
                raise
            return iter([])

    def retrieveChangelog(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        """
        if self._isBaseinfoExtrainfo2010():
            return super(EntropySQLiteRepository,
                         self).retrieveChangelog(package_id)

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
                return const_convert_to_unicode(
                    changelog, enctype = 'utf-8')

    def retrieveSlot(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must use the in-memory cache to do some memoization.
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
        Reimplemented from EntropySQLRepository.
        We must use the in-memory cache to do some memoization.
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

    def retrieveCategory(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        We must use the in-memory cache to do some memoization.
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

    def retrieveCompileFlags(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        """
        if self._isBaseinfoExtrainfo2010():
            return super(EntropySQLiteRepository,
                         self).retrieveCompileFlags(package_id)

        cur = self._cursor().execute("""
        SELECT chost,cflags,cxxflags FROM flags,extrainfo
        WHERE extrainfo.idpackage = (?) AND
        extrainfo.idflags = flags.idflags
        LIMIT 1""", (package_id,))
        flags = cur.fetchone()
        if not flags:
            flags = ("N/A", "N/A", "N/A")
        return flags

    def searchLicense(self, keyword, just_id = False):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        """
        if self._isBaseinfoExtrainfo2010():
            return super(EntropySQLiteRepository,
                         self).searchLicense(keyword, just_id = just_id)

        # backward compatibility
        if not entropy.tools.is_valid_string(keyword):
            return frozenset()

        license_query = """baseinfo, licenses
            WHERE LOWER(licenses.license) LIKE (?) AND
            licenses.idlicense = baseinfo.idlicense"""
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

    def searchKeySlot(self, key, slot):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        We must use the in-memory cache to do some memoization.
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
            for d_cat, d_name, d_slot, pkg_id in cur:
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
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        We must use the in-memory cache to do some memoization.
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

    def searchSets(self, keyword):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository, self).searchSets(keyword)
        except OperationalError:
            # TODO: remove this after 2012?
            if self._doesTableExist("packagesets"):
                raise
            return frozenset()

    def searchProvidedMime(self, mimetype):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).searchProvidedMime(mimetype)
        except OperationalError:
            # TODO: remove this after 2012?
            if self._doesTableExist("provided_mime"):
                raise
            return tuple()

    def searchProvidedVirtualPackage(self, keyword):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).searchProvidedVirtualPackage(keyword)
        except OperationalError as err:
            # TODO: remove this after 2012?
            if self._doesColumnInTableExist("provide", "is_default"):
                # something is really wrong
                raise
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage, 0 FROM baseinfo,provide
            WHERE provide.atom = (?) AND
            provide.idpackage = baseinfo.idpackage""", (keyword,))
            return tuple(cur)

    def searchCategory(self, keyword, like = False, just_id = True):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        """
        if self._isBaseinfoExtrainfo2010():
            return super(EntropySQLiteRepository,
                         self).searchCategory(
                keyword, like = like, just_id = just_id)

        # backward compatibility
        like_string = "= (?)"
        if like:
            like_string = "LIKE (?)"

        if just_id:
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM baseinfo, categories
            WHERE categories.category %s AND
            baseinfo.idcategory = categories.idcategory
            """ % (like_string,), (keyword,))
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom,baseinfo.idpackage
            FROM baseinfo, categories
            WHERE categories.category %s AND
            baseinfo.idcategory = categories.idcategory
            """ % (like_string,), (keyword,))

        if just_id:
            return self._cur2frozenset(cur)
        return frozenset(cur)

    def searchNameCategory(self, name, category, just_id = False):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        We must use the in-memory cache to do some memoization.
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
            for nam, cat, atom, pkg_id in cur:
                obj = cached.setdefault((nam, cat), set())
                obj.add((atom, pkg_id))
            self._setLiveCache("searchNameCategory", cached)

        data = frozenset(cached.get((name, category), frozenset()))
        # This avoids memory leaks with python 3.x
        del cached

        if just_id:
            return frozenset((y for x, y in data))
        return data

    def listPackageIdsInCategory(self, category, order_by = None):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        """
        if self._isBaseinfoExtrainfo2010():
            return super(EntropySQLiteRepository,
                         self).listPackageIdsInCategory(
                category, order_by = order_by)

        # backward compatibility
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
        SELECT idpackage FROM baseinfo, categories WHERE
            categories.category = (?) AND
            baseinfo.idcategory = categories.idcategory
        """ + order_by_string, (category,))
        return self._cur2frozenset(cur)

    def listAllExtraDownloads(self, do_sort = True):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).listAllExtraDownloads(
                do_sort = do_sort)
        except OperationalError:
            if self._doesTableExist("packagedownloads"):
                raise
            return tuple()

    def listAllCategories(self, order_by = None):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        """
        if self._isBaseinfoExtrainfo2010():
            return super(EntropySQLiteRepository,
                         self).listAllCategories(
                order_by = order_by)

        # backward compatibility
        order_by_string = ''
        if order_by is not None:
            valid_order_by = ("category",)
            if order_by not in valid_order_by:
                raise AttributeError("invalid order_by argument")
            order_by_string = 'ORDER BY %s' % (order_by,)

        cur = self._cursor().execute(
            "SELECT category FROM categories %s" % (order_by_string,))
        return self._cur2frozenset(cur)

    def _setupInitialSettings(self):
        """
        Setup initial repository settings
        """
        query = """
        INSERT OR REPLACE INTO settings VALUES ("arch", "%s");
        INSERT OR REPLACE INTO settings VALUES ("on_delete_cascade", "%s");
        INSERT OR REPLACE INTO settings VALUES ("_baseinfo_extrainfo_2010",
            "%s");
        """ % (etpConst['currentarch'], "1", "1")
        self._cursor().executescript(query)
        self.commit()
        self._settings_cache.clear()

    def _databaseStructureUpdates(self):
        """
        Do not forget to bump _SCHEMA_REVISION whenever you add more tables
        """
        try:
            current_schema_rev = int(self.getSetting("schema_revision"))
        except (KeyError, ValueError):
            current_schema_rev = -1

        if current_schema_rev == EntropySQLiteRepository._SCHEMA_REVISION \
                and not os.getenv("ETP_REPO_SCHEMA_UPDATE"):
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
                EntropySQLiteRepository._SCHEMA_REVISION)
            self._connection().commit()

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

    @staticmethod
    def importRepository(dumpfile, db, data = None):
        """
        Reimplemented from EntropyRepositoryBase.
        @todo: remove /usr/bin/sqlite3 dependency
        """
        dbfile = os.path.realpath(db)
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
            self._connection().unicode()
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

    def mtime(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if self._db is None:
            return 0.0
        if self._db == ":memory:":
            return 0.0
        return os.path.getmtime(self._db)

    def checksum(self, do_order = False, strict = True,
        strings = True, include_signatures = False):
        """
        Reimplemented from EntropySQLRepository.
        We have to handle _baseinfo_extrainfo_2010.
        We must use the in-memory cache to do some memoization.
        """
        _baseinfo_extrainfo_2010 = self._isBaseinfoExtrainfo2010()
        if _baseinfo_extrainfo_2010:
            return super(EntropySQLiteRepository,
                         self).checksum(
                do_order = do_order,
                strict = strict,
                strings = strings,
                include_signatures = include_signatures)

        # backward compatibility
        # !!! keep aligned !!!
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

        cur = self._cursor().execute("""
        SELECT category FROM categories %s
        """ % (category_order,))
        if strings:
            do_update_hash(m, cur)
        else:
            c_hash = hash(tuple(cur))

        d_hash = '0'
        e_hash = '0'
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
                # be optimistic and delay if condition,
                # _doesColumnInTableExist
                # is really slow
                cur = self._cursor().execute("""
                SELECT idpackage, sha1, gpg FROM
                packagesignatures %s""" % (package_id_order,))
            except OperationalError as err:
                # TODO: remove this before 31-12-2011
                if self._doesColumnInTableExist(
                    "packagesignatures", "gpg"):
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

        self._setLiveCache(cache_key, result)
        return result

    def storeInstalledPackage(self, package_id, repoid, source = 0):
        """
        Reimplemented from EntropySQLRepository.
        """
        super(EntropySQLiteRepository, self).storeInstalledPackage(
            package_id, repoid, source = source)
        self._clearLiveCache("getInstalledPackageRepository")
        self._clearLiveCache("getInstalledPackageSource")

    def getInstalledPackageRepository(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must use the in-memory cache to do some memoization.
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
        Reimplemented from EntropySQLRepositoryBase.
        We must use the in-memory cache to do some memoization.
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
            except OperationalError as err:
                # TODO: drop this check in future, backward compatibility
                if self._doesColumnInTableExist(
                    "installedtable", "source"):
                    raise
                cached = {}
            self._setLiveCache("getInstalledPackageSource", cached)

        # avoid python3.x memleak
        obj = cached.get(package_id)
        del cached
        return obj

    def dropInstalledPackageFromStore(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle live cache.
        """
        super(EntropySQLiteRepository, self).dropInstalledPackageFromStore(
            package_id)
        self._clearLiveCache("getInstalledPackageRepository")
        self._clearLiveCache("getInstalledPackageSource")

    def retrieveSpmMetadata(self, package_id):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).retrieveSpmMetadata(
                package_id)
        except OperationalError:
            if self._doesTableExist("xpakdata"):
                raise
            buf = const_get_buffer()
            return buf("")

    def retrieveBranchMigration(self, to_branch):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).retrieveBranchMigration(
                to_branch)
        except OperationalError:
            if self._doesTableExist('entropy_branch_migration'):
                raise
            return {}

    def dropContentSafety(self):
        """
        Reimplemented from EntropySQLRepository.
        We must handle backward compatibility.
        """
        try:
            return super(EntropySQLiteRepository,
                         self).dropContentSafety()
        except OperationalError:
            if self._doesTableExist('contentsafety'):
                raise
            # table doesn't exist, ignore

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
            except OperationalError:
                continue

    def createAllIndexes(self):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        """
        super(EntropySQLiteRepository, self).createAllIndexes()
        if not self._isBaseinfoExtrainfo2010():
            self.__createLicensesIndex()
            self.__createCategoriesIndex()
            self.__createCompileFlagsIndex()

    def __createCompileFlagsIndex(self):
        try:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS flagsindex ON flags
                ( chost, cflags, cxxflags )
            """)
        except OperationalError:
            pass

    def __createCategoriesIndex(self):
        self._cursor().execute("""
        CREATE INDEX IF NOT EXISTS categoriesindex_category
            ON categories ( category )
        """)

    def __createLicensesIndex(self):
        self._cursor().execute("""
        CREATE INDEX IF NOT EXISTS licensesindex ON licenses ( license )
        """)

    def _createBaseinfoIndex(self):
        """
        Reimplemented from EntropySQLRepository.
        We must handle _baseinfo_extrainfo_2010.
        """
        if self._isBaseinfoExtrainfo2010():
            return super(EntropySQLiteRepository,
                         self)._createBaseinfoIndex()

        # backward compatibility
        self._cursor().executescript("""
        CREATE INDEX IF NOT EXISTS baseindex_atom
            ON baseinfo ( atom );
        CREATE INDEX IF NOT EXISTS baseindex_branch_name
            ON baseinfo ( name, branch );
        CREATE INDEX IF NOT EXISTS baseindex_branch_name_idcategory
            ON baseinfo ( name, idcategory, branch );
        CREATE INDEX IF NOT EXISTS baseindex_idlicense
            ON baseinfo ( idlicense, idcategory );
        """)

    def _isBaseinfoExtrainfo2010(self):
        """
        Return is _baseinfo_extrainfo_2010 setting is
        found via getSetting()
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
                FOREIGN KEY(idpackage)
                    REFERENCES baseinfo(idpackage) ON DELETE CASCADE
            );
            INSERT INTO extrainfo_new_temp
                SELECT idpackage, description, homepage, download, size,
                    flags.chost, flags.cflags, flags.cxxflags,
                    digest, datecreation
                FROM extrainfo, flags WHERE flags.idflags = extrainfo.idflags;
            DROP TABLE extrainfo;
            ALTER TABLE extrainfo_new_temp RENAME TO extrainfo;
            DROP TABLE flags;

            COMMIT;
        """)
        self._cursor().execute("pragma foreign_keys = ON").fetchall()

        self._clearLiveCache("_doesColumnInTableExist")
        self._setSetting("_baseinfo_extrainfo_2010", "1")
        self._connection().commit()

    def _foreignKeySupport(self):

        # entropy.qa uses this name, must skip migration
        if self.name in ("qa_testing", "mem_repo"):
            return

        tables = ("extrainfo", "dependencies" , "provide",
            "conflicts", "configprotect", "configprotectmask", "sources",
            "useflags", "keywords", "content", "counters", "sizes",
            "needed", "triggers", "systempackages", "injected",
            "installedtable", "automergefiles", "packagesignatures",
            "packagespmphases", "provided_libs")

        done_something = False
        foreign_keys_supported = False
        for table in tables:
            if not self._doesTableExist(table): # wtf
                continue

            cur = self._cursor().execute("""
            PRAGMA foreign_key_list(%s)
            """ % (table,))
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
            FOREIGN KEY(idpackage) REFERENCES
                baseinfo(idpackage) ON DELETE CASCADE );"""
            self._cursor().executescript(cur_sql)
            self._moveContent(table, tmp_table)
            self._atomicRename(tmp_table, table)

        if done_something:
            self._setSetting("on_delete_cascade", "1")
            self._connection().commit()
            # recreate indexes
            self.createAllIndexes()
        elif foreign_keys_supported:
            # some devel version didn't have this set
            try:
                self.getSetting("on_delete_cascade")
            except KeyError:
                self._setSetting("on_delete_cascade", "1")
                self._connection().commit()

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
                FOREIGN KEY(idpackage)
                    REFERENCES baseinfo(idpackage) ON DELETE CASCADE
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
                FOREIGN KEY(idpackage)
                    REFERENCES baseinfo(idpackage) ON DELETE CASCADE
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
        FOREIGN KEY(idpackage)
            REFERENCES baseinfo(idpackage) ON DELETE CASCADE );
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
                FOREIGN KEY(idpackage)
                    REFERENCES baseinfo(idpackage) ON DELETE CASCADE
            );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createPackagespmrepository(self):
        self._cursor().execute("""
            CREATE TABLE packagespmrepository (
                idpackage INTEGER PRIMARY KEY,
                repository VARCHAR,
                FOREIGN KEY(idpackage)
                    REFERENCES baseinfo(idpackage) ON DELETE CASCADE
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
            FOREIGN KEY(idpackage)
                REFERENCES baseinfo(idpackage) ON DELETE CASCADE
        );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")

    def _createProvidedMimeTable(self):
        self._cursor().execute("""
        CREATE TABLE provided_mime (
            mimetype VARCHAR,
            idpackage INTEGER,
            FOREIGN KEY(idpackage)
                REFERENCES baseinfo(idpackage) ON DELETE CASCADE
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
            FOREIGN KEY(idpackage)
                REFERENCES baseinfo(idpackage) ON DELETE CASCADE
        );
        """)
        self._clearLiveCache("_doesTableExist")
        self._clearLiveCache("_doesColumnInTableExist")
