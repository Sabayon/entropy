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
import shutil
import hashlib
import time
import thread
import threading
import subprocess
import warnings
from sqlite3 import dbapi2

from entropy.const import etpConst, const_setup_file, \
    const_isunicode, const_convert_to_unicode, const_get_buffer, \
    const_convert_to_rawstring, const_cmp, const_pid_exists
from entropy.exceptions import SystemDatabaseError, \
    OperationNotPermitted, RepositoryPluginError, SPMError
from entropy.output import brown, bold, red, blue, purple, darkred, darkgreen
from entropy.cache import EntropyCacher, MtimePingus
from entropy.spm.plugins.factory import get_default_instance as get_spm
from entropy.db.exceptions import IntegrityError, Error, OperationalError, \
    DatabaseError
from entropy.db.skel import EntropyRepositoryBase
from entropy.i18n import _

import entropy.tools
import entropy.dump


class EntropyRepository(EntropyRepositoryBase):

    """
    EntropyRepository implements SQLite3 based storage. In a Model-View based
    pattern, it can be considered the "model".
    Actually it's the only one available but more model backends will be
    supported in future (which will inherit this class directly).

    Every Entropy repository storage interface MUST inherit from this base
    class.
    """

    _SETTING_KEYS = [ "arch", "on_delete_cascade" ]

    class Schema:

        def get_init(self):
            return """
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

                CREATE TABLE content (
                    idpackage INTEGER,
                    file VARCHAR,
                    type VARCHAR,
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

                CREATE TABLE dependstable (
                    iddependency INTEGER PRIMARY KEY,
                    idpackage INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
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

                CREATE TABLE eclasses (
                    idpackage INTEGER,
                    idclass INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );

                CREATE TABLE eclassesreference (
                    idclass INTEGER PRIMARY KEY AUTOINCREMENT,
                    classname VARCHAR
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


    def __init__(self, readOnly = False, dbFile = None, xcache = False,
        dbname = etpConst['serverdbid'], indexing = True, skipChecks = False,
        temporary = False):

        """
        EntropyRepository constructor.

        @keyword readOnly: open file in read-only mode
        @type readOnly: bool
        @keyword dbFile: path to database to open
        @type dbFile: string
        @keyword xcache: enable on-disk cache
        @type xcache: bool
        @keyword dbname: EntropyRepository instance identifier
        @type dbname: string
        @keyword indexing: enable database indexes
        @type indexing: bool
        @keyword skipChecks: if True, skip integrity checks
        @type skipChecks: bool
        @keyword temporary: if True, dbFile will be automatically removed
            on closeDB()
        @type temporary: bool
        """
        self.__cursor_cache = {}
        self.__connection_cache = {}
        self._cleanup_stale_cur_conn_t = time.time()

        EntropyRepositoryBase.__init__(self, readOnly, xcache, temporary,
            dbname, indexing)

        # FIXME: remove before 20101010, backward compatibility
        self.dbFile = dbFile

        self._db_path = dbFile
        if self._db_path is None:
            raise AttributeError("valid database path needed")

        # setup service interface
        self.__skip_checks = skipChecks
        self.__live_cache = {}
        # this instance will set this to True if reverse dependencies
        # metadata is generated runtime
        self._temp_reverse_deps = False

        self.__structure_update = False
        if not self.__skip_checks:

            if not entropy.tools.is_user_in_entropy_group():
                # forcing since we won't have write access to db
                self.indexing = False
            # live systems don't like wasting RAM
            if entropy.tools.islive():
                self.indexing = False

            try:
                if os.access(self._db_path, os.W_OK) and \
                    self._doesTableExist('baseinfo') and \
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

    def _get_cur_th_key(self):
        return thread.get_ident(), os.getpid()

    def _cleanup_stale_cur_conn(self, kill_all = False):

        th_ids = [x.ident for x in threading.enumerate() if x.ident]

        def kill_me(th_id, pid):
            try:
                cur = self.__cursor_cache.pop((th_id, pid))
                cur.close()
            except KeyError:
                pass
            try:
                conn = self.__connection_cache.pop((th_id, pid))
                if not self.readonly:
                    try:
                        conn.commit()
                    except OperationalError:
                        # no transaction is active can cause this, bleh!
                        pass
                try:
                    conn.close()
                except OperationalError:
                    # heh, unable to close due to unfinalised statements
                    # interpreter shutdown?
                    pass
            except KeyError:
                pass

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
        cursor = self.__cursor_cache.get(c_key)
        if cursor is None:
            conn = self._connection()
            cursor = conn.cursor()
            # !!! enable foreign keys pragma !!! do not remove this
            # otherwise removePackage won't work properly
            cursor.execute("pragma foreign_keys = 1")
            self.__cursor_cache[c_key] = cursor
            # memory databases are critical because every new cursor brings
            # up a totally empty repository. So, enforce initialization.
            if self._db_path == ":memory:":
                self.initializeRepository()
        return cursor

    def _connection(self):
        self._cleanup_stale_cur_conn()
        c_key = self._get_cur_th_key()
        conn = self.__connection_cache.get(c_key)
        if conn is None:
            # check_same_thread still required for conn.close() called from
            # arbitrary thread
            conn = dbapi2.connect(self._db_path, timeout=300.0,
                check_same_thread = False)
            self.__connection_cache[c_key] = conn
        return conn

    def __show_info(self):
        first_part = "<EntropyRepository instance at %s, %s" % (
            hex(id(self)), self._db_path,)
        second_part = ", ro: %s, caching: %s, indexing: %s" % (
            self.readonly, self.xcache, self.indexing,)
        third_part = ", name: %s, skip_upd: %s, st_upd: %s" % (
            self.reponame, self.__skip_checks, self.__structure_update,)
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


    def __del__(self):
        self.closeDB()

    def closeDB(self):
        """
        Reimplemented from EntropyRepositoryBase.
        Needs to call superclass method.
        """
        super(EntropyRepository, self).closeDB()

        self._cleanup_stale_cur_conn(kill_all = True)
        if self.temporary and os.path.isfile(self._db_path):
            try:
                os.remove(self._db_path)
            except (OSError, IOError,):
                pass

    def vacuum(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("vacuum")

    def commitChanges(self, force = False, no_plugins = False):
        """
        Reimplemented from EntropyRepositoryBase.
        Needs to call superclass method.
        """
        super(EntropyRepository, self).commitChanges(force = force,
            no_plugins = no_plugins)

        if force or (not self.readonly):
            try:
                self._connection().commit()
            except Error:
                pass

    def initializeDatabase(self):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.initializeRepository()

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
        self._databaseStructureUpdates()
        # set cache size
        self._setCacheSize(8192)
        self._setDefaultCacheSize(8192)
        self._setupInitialSettings()

        self.commitChanges()
        super(EntropyRepository, self).initializeRepository()

    def handlePackage(self, pkg_data, forcedRevision = -1,
        formattedContent = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        def remove_conflicting_packages(pkgdata):

            manual_deps = set()
            removelist = self.getPackagesToRemove(
                pkgdata['name'], pkgdata['category'],
                pkgdata['slot'], pkgdata['injected']
            )

            for r_package_id in removelist:
                manual_deps |= self.retrieveManualDependencies(r_package_id)
                self.removePackage(r_package_id, do_cleanup = False,
                    do_commit = False)

            # inject old manual dependencies back to package metadata
            for manual_dep in manual_deps:
                if manual_dep in pkgdata['dependencies']:
                    continue
                pkgdata['dependencies'][manual_dep] = \
                    etpConst['dependency_type_ids']['mdepend_id']

        # FIXME: this is Entropy Client related but also part of the
        # currently implemented metaphor, so let's wait to have a Rule
        # Engine in place before removing the oddity of client_repo
        # metadatum.
        client_repo = self.get_plugins_metadata().get('client_repo')
        if client_repo:
            remove_conflicting_packages(pkg_data)
            return self.addPackage(pkg_data, revision = forcedRevision,
                formatted_content = formattedContent)

        # build atom string, server side
        pkgatom = entropy.tools.create_package_atom_string(
            pkg_data['category'], pkg_data['name'], pkg_data['version'],
            pkg_data['versiontag'])

        foundid = self._isAtomAvailable(pkgatom)
        if foundid < 0: # same atom doesn't exist in any branch
            remove_conflicting_packages(pkg_data)
            return self.addPackage(pkg_data, revision = forcedRevision,
                formatted_content = formattedContent)

        package_ids = self.getPackageIds(pkgatom)
        current_rev = forcedRevision

        for package_id in package_ids:

            if forcedRevision == -1:
                myrev = self.retrieveRevision(package_id)
                if myrev > current_rev:
                    current_rev = myrev

            # injected packages wouldn't be removed by addPackage
            self.removePackage(package_id, do_cleanup = False, do_commit = False)

        if forcedRevision == -1:
            current_rev += 1

        # add the new one
        remove_conflicting_packages(pkg_data)
        return self.addPackage(pkg_data, revision = current_rev,
            formatted_content = formattedContent)

    def addPackage(self, pkg_data, revision = -1, package_id = None,
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

        # create new category if it doesn't exist
        catid = self._isCategoryAvailable(pkg_data['category'])
        if catid == -1:
            catid = self._addCategory(pkg_data['category'])

        # create new license if it doesn't exist
        licid = self._isLicenseAvailable(pkg_data['license'])
        if licid == -1:
            licid = self._addLicense(pkg_data['license'])

        idprotect = self._isProtectAvailable(pkg_data['config_protect'])
        if idprotect == -1:
            idprotect = self._addProtect(pkg_data['config_protect'])

        idprotect_mask = self._isProtectAvailable(
            pkg_data['config_protect_mask'])
        if idprotect_mask == -1:
            idprotect_mask = self._addProtect(pkg_data['config_protect_mask'])

        idflags = self._areCompileFlagsAvailable(pkg_data['chost'],
            pkg_data['cflags'], pkg_data['cxxflags'])
        if idflags == -1:
            idflags = self._addCompileFlags(pkg_data['chost'],
                pkg_data['cflags'], pkg_data['cxxflags'])

        trigger = 0
        if pkg_data['trigger']:
            trigger = 1

        # baseinfo
        pkgatom = entropy.tools.create_package_atom_string(
            pkg_data['category'], pkg_data['name'], pkg_data['version'],
            pkg_data['versiontag'])
        # add atom metadatum
        pkg_data['atom'] = pkgatom

        mybaseinfo_data = (pkgatom, catid, pkg_data['name'],
            pkg_data['version'], pkg_data['versiontag'], revision,
            pkg_data['branch'], pkg_data['slot'],
            licid, pkg_data['etpapi'], trigger,
        )

        mypackage_id_string = 'NULL'
        if isinstance(package_id, int):

            manual_deps = self.retrieveManualDependencies(package_id)

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
        ### other information iserted below are not as
        ### critical as these above

        # tables using a select
        self._insertEclasses(package_id, pkg_data['eclasses'])
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

        self.clearCache() # we do live_cache.clear() here too
        if do_commit:
            self.commitChanges()

        super(EntropyRepository, self).addPackage(pkg_data, revision = revision,
            package_id = package_id, do_commit = do_commit,
            formatted_content = formatted_content)

        return package_id, revision, pkg_data

    def removePackage(self, package_id, do_cleanup = True, do_commit = True,
        from_add_package = False):
        """
        Reimplemented from EntropyRepositoryBase.
        Needs to call superclass method.
        """
        self.clearCache()

        super(EntropyRepository, self).removePackage(package_id,
            do_cleanup = do_cleanup, do_commit = do_commit,
            from_add_package = from_add_package)

        try:
            new_way = self.getSetting("on_delete_cascade")
        except KeyError:
            new_way = ''
        # TODO: deprecate this someday
        if new_way:
            # this will work thanks to ON DELETE CASCADE !
            self._cursor().execute(
                "DELETE FROM baseinfo WHERE idpackage = (?)", (package_id,))
        else:
            r_tup = (package_id,)*19
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
                DELETE FROM eclasses WHERE idpackage = %d;
                DELETE FROM needed WHERE idpackage = %d;
                DELETE FROM triggers WHERE idpackage = %d;
                DELETE FROM systempackages WHERE idpackage = %d;
                DELETE FROM injected WHERE idpackage = %d;
                DELETE FROM installedtable WHERE idpackage = %d;
            """ % r_tup)
            # FIXME: incorportate in query above before 2010-12-31
            if self._doesTableExist("packagedesktopmime"):
                self._cursor().execute("""
                DELETE FROM packagedesktopmime WHERE idpackage = (?)""",
                (package_id,))
            if self._doesTableExist("provided_mime"):
                self._cursor().execute("""
                DELETE FROM provided_mime WHERE idpackage = (?)""",
                (package_id,))

        if do_cleanup:
            # Cleanups if at least one package has been removed
            self.clean()

        if do_commit:
            self.commitChanges()

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
        cur = self._cursor().execute("""
        INSERT into useflagsreference VALUES (NULL,?)
        """, (useflag,))
        return cur.lastrowid

    def _addEclass(self, eclass):
        """
        Add package SPM Eclass string to repository.
        Return its identifier (ideclass).

        @param eclass: eclass string
        @type eclass: string
        @return: eclass identifier (ideclass)
        @rtype: int
        """
        cur = self._cursor().execute("""
        INSERT into eclassesreference VALUES (NULL,?)
        """, (eclass,))
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
            self.commitChanges()

    def setInjected(self, package_id, do_commit = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not self.isInjected(package_id):
            self._cursor().execute("""
            INSERT into injected VALUES (?)
            """, (package_id,))
        if do_commit:
            self.commitChanges()

    def setCreationDate(self, package_id, date):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE extrainfo SET datecreation = (?) WHERE idpackage = (?)
        """, (str(date), package_id,))
        self.commitChanges()

    def setDigest(self, package_id, digest):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE extrainfo SET digest = (?) WHERE idpackage = (?)
        """, (digest, package_id,))
        self.commitChanges()

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
        self.commitChanges()

    def setCategory(self, package_id, category):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # create new category if it doesn't exist
        catid = self._isCategoryAvailable(category)
        if catid == -1:
            # create category
            catid = self._addCategory(category)

        self._cursor().execute("""
        UPDATE baseinfo SET idcategory = (?) WHERE idpackage = (?)
        """, (catid, package_id,))
        self.commitChanges()

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

        self.commitChanges()

    def setName(self, package_id, name):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET name = (?) WHERE idpackage = (?)
        """, (name, package_id,))
        self.commitChanges()

    def setDependency(self, iddependency, dependency):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE dependenciesreference SET dependency = (?)
        WHERE iddependency = (?)
        """, (dependency, iddependency,))
        self.commitChanges()

    def setAtom(self, package_id, atom):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET atom = (?) WHERE idpackage = (?)
        """, (atom, package_id,))
        self.commitChanges()

    def setSlot(self, package_id, slot):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET slot = (?) WHERE idpackage = (?)
        """, (slot, package_id,))
        self.commitChanges()

    def setRevision(self, package_id, revision):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET revision = (?) WHERE idpackage = (?)
        """, (revision, package_id,))
        self.commitChanges()

    def removeDependencies(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM dependencies WHERE idpackage = (?)
        """, (package_id,))
        self.commitChanges()

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

    def _insertProvidedLibraries(self, package_id, libs_metadata):
        """
        Insert library metadata owned by package.

        @param package_id: package indentifier
        @type package_id: int
        @param libs_metadata: provided library metadata composed by list of
            tuples of length 3 containing library name, path and ELF class.
        @type libs_metadata: list
        """
        # TODO: remove this in future
        if not self._doesTableExist('provided_libs'):
            self._createProvidedLibs()

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
            self._cursor().execute("""
            INSERT INTO packagesignatures VALUES (?,?,?,?,?)
            """, (package_id, sha1, sha256, sha512, gpg))
        except OperationalError: # FIXME: remove this before 2010-12-31
            self._cursor().execute("""
            INSERT INTO packagesignatures VALUES (?,?,?,?)
            """, (package_id, sha1, sha256, sha512))

    def _insertDesktopMime(self, package_id, metadata):
        """
        Insert file association information for package.

        @param package_id: package indentifier
        @type package_id: int
        @param metadata: list of dict() containing file association metadata
        @type metadata: list
        """
        # FIXME: remove this before 2010-12-31
        if not self._doesTableExist("packagedesktopmime"):
            self._createPackageDesktopMimeTable()
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
        # FIXME: remove this before 2010-12-31
        if not self._doesTableExist("provided_mime"):
            self._createProvidedMimeTable()
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
        # FIXME backward compatibility
        if not self._doesTableExist('packagespmrepository'):
            self._createPackagespmrepository()
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
        # FIXME: backward compat, remove someday
        # this adds default provide information to set data if not available
        my_provides = set()
        for prov in provides:
            if not isinstance(prov, tuple):
                my_provides.add((prov, 0,))
            else:
                my_provides.add(prov)

        default_provides = [x for x in my_provides if x[1]]


        self._cursor().executemany("""
        INSERT into provide VALUES (?,?,?)
        """, [(package_id, x, y,) for x, y in my_provides])

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
                # create eclass
                idneeded = self._addNeeded(needed)
            return (package_id, idneeded, elfclass,)

        self._cursor().executemany("""
        INSERT into needed VALUES (?,?,?)
        """, list(map(mymf, neededs)))

    def _insertEclasses(self, package_id, eclasses):
        """
        Insert Source Package Manager used build specification file classes.
        The term "eclasses" is derived from Portage.

        @param package_id: package indentifier
        @type package_id: int
        @param eclasses: list of classes
        @type eclasses: list
        """

        def mymf(eclass):
            idclass = self._isEclassAvailable(eclass)
            if idclass == -1:
                idclass = self._addEclass(eclass)
            return (package_id, idclass,)

        self._cursor().executemany("""
        INSERT into eclasses VALUES (?,?)
        """, list(map(mymf, eclasses)))

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

        self.commitChanges()

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

        try:
            self._cursor().execute("""
            UPDATE counters SET counter = (?) %s
            WHERE idpackage = (?)""" % (branchstring,), insertdata)
        except Error:
            if self.reponame == etpConst['clientdbid']:
                raise
        self.commitChanges()

    def contentDiff(self, package_id, dbconn, dbconn_package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if self is dbconn:
            raise AttributeError("cannot diff inside the same db")

        self._connection().text_factory = lambda x: const_convert_to_unicode(x)

        # setup random table name
        randomtable = "cdiff%s" % (entropy.tools.get_random_number(),)
        while self._doesTableExist(randomtable, temporary = True):
            randomtable = "cdiff%s" % (entropy.tools.get_random_number(),)

        # create random table
        self._cursor().execute("""
            CREATE TEMPORARY TABLE %s ( file VARCHAR )""" % (randomtable,)
        )

        try:
            dbconn._connection().text_factory = lambda x: \
                const_convert_to_unicode(x)

            cur = dbconn._cursor().execute("""
            SELECT file FROM content WHERE idpackage = (?)
            """, (dbconn_package_id,))
            self._cursor().executemany("""
            INSERT INTO %s VALUES (?)""" % (randomtable,), cur)

            # now compare
            cur = self._cursor().execute("""
            SELECT file FROM content 
            WHERE content.idpackage = (?) AND 
            content.file NOT IN (SELECT file from %s)""" % (randomtable,),
                (package_id,))

            # suck back
            return self._cur2set(cur)

        finally:
            self._cursor().execute('DROP TABLE IF EXISTS %s' % (randomtable,))

    def clean(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cleanupUseflags()
        self._cleanupSources()
        self._cleanupEclasses()
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

    def _cleanupEclasses(self):
        """
        Cleanup "eclass" metadata unused references to save space.
        """
        self._cursor().execute("""
        DELETE FROM eclassesreference
        WHERE idclass NOT IN (SELECT idclass FROM eclasses)""")

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

    def _getCategory(self, idcategory):
        """
        Get category name from category identifier.

        @param idcategory: category identifier
        @type idcategory: int
        @return: category name
        @rtype: string
        """
        cur = self._cursor().execute("""
        SELECT category from categories WHERE idcategory = (?) LIMIT 1
        """, (idcategory,))
        cat = cur.fetchone()
        if cat:
            return cat[0]
        return cat

    def getPackageIds(self, atom):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo WHERE atom = (?)
        """, (atom,))
        return self._cur2set(cur)

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
        cur = self._cursor().execute("""
        SELECT version, versiontag, revision FROM baseinfo
        WHERE idpackage = (?)
        LIMIT 1
        """, (package_id,))
        return cur.fetchone()

    def getStrictData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        SELECT categories.category || "/" || baseinfo.name,
        baseinfo.slot,baseinfo.version,baseinfo.versiontag,
        baseinfo.revision,baseinfo.atom FROM baseinfo, categories
        WHERE baseinfo.idpackage = (?) AND 
        baseinfo.idcategory = categories.idcategory""", (package_id,))
        return self._cursor().fetchone()

    def getStrictScopeData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        SELECT atom, slot, revision FROM baseinfo
        WHERE idpackage = (?)""", (package_id,))
        rslt = self._cursor().fetchone()
        return rslt

    def getScopeData(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
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
        return self._cursor().fetchone()

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
        self._cursor().execute(sql, (package_id,))
        return self._cursor().fetchone()

    def _cur2set(self, cur):
        mycontent = set()
        for x in cur:
            mycontent |= set(x)
        return mycontent

    def _fetchall2set(self, item):
        mycontent = set()
        for x in item:
            mycontent |= set(x)
        return mycontent

    def _fetchall2list(self, item):
        content = []
        for x in item:
            content += x
        return content

    def _cur2list(self, cur):
        content = []
        for x in cur:
            content += x
        return content

    def clearCache(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        super(EntropyRepository, self).clearCache()

        self.__live_cache.clear()

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
            self._cursor().execute("""
            SELECT command, branch, date FROM treeupdatesactions
            """)
        else:
            self._cursor().execute('SELECT * FROM treeupdatesactions')
        return self._cursor().fetchall()

    def retrieveTreeUpdatesActions(self, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        params = (repository,)

        self._cursor().execute("""
        SELECT command FROM treeupdatesactions WHERE 
        repository = (?) order by date""", params)
        return self._fetchall2list(self._cursor().fetchall())

    def bumpTreeUpdatesActions(self, updates):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('DELETE FROM treeupdatesactions')
        self._cursor().executemany("""
        INSERT INTO treeupdatesactions VALUES (?,?,?,?,?)
        """, updates)
        self.commitChanges()

    def removeTreeUpdatesActions(self, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM treeupdatesactions WHERE repository = (?)
        """, (repository,))
        self.commitChanges()

    def insertTreeUpdatesActions(self, updates, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        myupdates = [[repository]+list(x) for x in updates]
        self._cursor().executemany("""
        INSERT INTO treeupdatesactions VALUES (NULL,?,?,?,?)
        """, myupdates)
        self.commitChanges()

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
        self._cursor().execute("""
        SELECT * FROM treeupdatesactions 
        WHERE repository = (?) and command = (?)
        and branch = (?)""", (repository, command, branch,))

        result = self._cursor().fetchone()
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
        # FIXME backward compatibility
        if not self._doesTableExist('packagesets'):
            return {}

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
        return self._cur2set(cur)

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

    def retrieveMessages(self, package_id):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return []

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
        cur = self._cursor().execute("""
        SELECT digest FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        digest = cur.fetchone()
        if digest:
            return digest[0]

    def retrieveSignatures(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # FIXME backward compatibility
        if not self._doesTableExist('packagesignatures'):
            return None, None, None, None

        try:
            cur = self._cursor().execute("""
            SELECT sha1, sha256, sha512, gpg FROM packagesignatures
            WHERE idpackage = (?) LIMIT 1
            """, (package_id,))
            data = cur.fetchone()
        except OperationalError:
            # FIXME: backward compat
            cur = self._cursor().execute("""
            SELECT sha1, sha256, sha512 FROM packagesignatures
            WHERE idpackage = (?) LIMIT 1
            """, (package_id,))
            data = cur.fetchone() + (None,)

        if data:
            return data
        return None, None, None, None

    def retrieveName(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        SELECT name FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        name = self._cursor().fetchone()
        if name:
            return name[0]

    def retrieveKeySplit(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT categories.category, baseinfo.name
        FROM baseinfo, categories
        WHERE baseinfo.idpackage = (?) AND
        baseinfo.idcategory = categories.idcategory LIMIT 1
        """, (package_id,))
        return cur.fetchone()

    def retrieveKeySlot(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT categories.category || "/" || baseinfo.name,baseinfo.slot
        FROM baseinfo,categories
        WHERE baseinfo.idpackage = (?) AND
        baseinfo.idcategory = categories.idcategory LIMIT 1
        """, (package_id,))
        return cur.fetchone()

    def retrieveKeySlotAggregated(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT categories.category || "/" || baseinfo.name || "%s" ||
        baseinfo.slot FROM baseinfo,categories
        WHERE baseinfo.idpackage = (?) AND
        baseinfo.idcategory = categories.idcategory LIMIT 1
        """ % (etpConst['entropyslotprefix'],), (package_id,))
        data = cur.fetchone()
        if data:
            return data[0]

    def retrieveKeySlotTag(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
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
        cur = self._cursor().execute("""
        SELECT version FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        ver = cur.fetchone()
        if ver:
            return ver[0]

    def retrieveRevision(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT revision FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        rev = cur.fetchone()
        if rev:
            return rev[0]

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
        cur = self._cursor().execute("""
        SELECT flagname FROM useflags,useflagsreference
        WHERE useflags.idpackage = (?) AND 
        useflags.idflag = useflagsreference.idflag
        """, (package_id,))
        return self._cur2set(cur)

    def retrieveEclasses(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT classname FROM eclasses,eclassesreference
        WHERE eclasses.idpackage = (?) AND
        eclasses.idclass = eclassesreference.idclass""", (package_id,))
        return self._cur2set(cur)

    def retrieveSpmPhases(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # FIXME backward compatibility
        if not self._doesTableExist('packagespmphases'):
            return None

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
        # FIXME backward compatibility
        if not self._doesTableExist('packagespmrepository'):
            return None
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
            return set()

        cur = self._cursor().execute("""
        SELECT mimetype FROM provided_mime WHERE idpackage = (?)""",
        (package_id,))
        return self._cur2set(cur)

    def retrieveNeededRaw(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT library FROM needed,neededreference
        WHERE needed.idpackage = (?) AND 
        needed.idneeded = neededreference.idneeded""", (package_id,))
        return self._cur2set(cur)

    def retrieveNeeded(self, package_id, extended = False, format = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if extended:

            cur = self._cursor().execute("""
            SELECT library,elfclass FROM needed,neededreference
            WHERE needed.idpackage = (?) AND
            needed.idneeded = neededreference.idneeded order by library
            """, (package_id,))
            needed = cur.fetchall()

        else:

            cur = self._cursor().execute("""
            SELECT library FROM needed,neededreference
            WHERE needed.idpackage = (?) AND
            needed.idneeded = neededreference.idneeded ORDER BY library
            """, (package_id,))
            needed = self._cur2list(cur)

        if extended and format:
            return dict((lib, elfclass,) for lib, elfclass in needed)
        return needed

    def retrieveProvidedLibraries(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # TODO: remove this in future, backward compat.
        if not self._doesTableExist('provided_libs'):
            return set()

        cur = self._cursor().execute("""
        SELECT library, path, elfclass FROM provided_libs
        WHERE idpackage = (?)
        """, (package_id,))
        return set(cur.fetchall())

    def retrieveConflicts(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT conflict FROM conflicts WHERE idpackage = (?)
        """, (package_id,))
        return self._cur2set(cur)

    def retrieveProvide(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # FIXME: added for backward compatibility, remove someday
        is_default_str = ',0'
        if self._doesColumnInTableExist("provide", "is_default"):
            is_default_str = ',is_default '

        cur = self._cursor().execute("""
        SELECT atom%s FROM provide WHERE idpackage = (?)
        """ % (is_default_str,), (package_id,))
        if is_default_str:
            return set(cur.fetchall())
        return self._cur2set(cur)

    def retrieveDependenciesList(self, package_id, exclude_deptypes = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        excluded_deptypes_query = ""
        if exclude_deptypes is not None:
            for dep_type in exclude_deptypes:
                excluded_deptypes_query += " AND dependencies.type != %s" % (
                    dep_type,)

        cur = self._cursor().execute("""
        SELECT dependenciesreference.dependency
        FROM dependencies, dependenciesreference
        WHERE dependencies.idpackage = (?) AND
        dependencies.iddependency = dependenciesreference.iddependency %s
        UNION SELECT "!" || conflict FROM conflicts
        WHERE idpackage = (?)""" % (excluded_deptypes_query,),
        (package_id, package_id,))
        return self._cur2set(cur)

    def retrieveBuildDependencies(self, package_id, extended = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return self.retrieveDependencies(package_id, extended = extended,
            deptype = etpConst['dependency_type_ids']['bdepend_id'])

    def retrievePostDependencies(self, package_id, extended = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return self.retrieveDependencies(package_id, extended = extended,
            deptype = etpConst['dependency_type_ids']['pdepend_id'])

    def retrieveManualDependencies(self, package_id, extended = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        return self.retrieveDependencies(package_id, extended = extended,
            deptype = etpConst['dependency_type_ids']['mdepend_id'])

    def retrieveDependencies(self, package_id, extended = False, deptype = None,
        exclude_deptypes = None):
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
                excluded_deptypes_query += " AND dependencies.type != %s" % (
                    dep_type,)

        if extended:
            cur = self._cursor().execute("""
            SELECT dependenciesreference.dependency,dependencies.type
            FROM dependencies,dependenciesreference
            WHERE dependencies.idpackage = (?) AND
            dependencies.iddependency =
            dependenciesreference.iddependency %s %s""" % (
                depstring, excluded_deptypes_query,), searchdata)
            return cur.fetchall()
        else:
            cur = self._cursor().execute("""
            SELECT dependenciesreference.dependency 
            FROM dependencies,dependenciesreference 
            WHERE dependencies.idpackage = (?) AND 
            dependencies.iddependency =
            dependenciesreference.iddependency %s %s""" % (
                depstring, excluded_deptypes_query,), searchdata)
            return self._cur2set(cur)

    def retrieveKeywords(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT keywordname FROM keywords,keywordsreference
        WHERE keywords.idpackage = (?) AND
        keywords.idkeyword = keywordsreference.idkeyword""", (package_id,))
        return self._cur2set(cur)

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
        self._cursor().execute("""
        SELECT protect FROM configprotectmask,configprotectreference 
        WHERE idpackage = (?) AND 
        configprotectmask.idprotect = configprotectreference.idprotect
        """, (package_id,))

        protect = self._cursor().fetchone()
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
        sources = self._cur2set(cur)
        if not extended:
            return sources

        source_data = {}
        mirror_str = "mirror://"
        for source in sources:

            source_data[source] = set()
            if source.startswith(mirror_str):

                mirrorname = source.split("/")[2]
                mirror_url =  source.split("/", 3)[3:][0]
                source_data[source] |= set(
                    [os.path.join(url, mirror_url) for url in \
                        self.retrieveMirrorData(mirrorname)])

            else:
                source_data[source].add(source)

        return source_data

    def retrieveAutomergefiles(self, package_id, get_dict = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # FIXME backward compatibility
        if not self._doesTableExist('automergefiles'):
            self._createAutomergefilesTable()

        # like portage does
        self._connection().text_factory = lambda x: const_convert_to_unicode(x)

        cur = self._cursor().execute("""
        SELECT configfile, md5 FROM automergefiles WHERE idpackage = (?)
        """, (package_id,))
        data = cur.fetchall()

        if get_dict:
            data = dict(((x, y,) for x, y in data))
        return data

    def retrieveContent(self, package_id, extended = False, contentType = None,
        formatted = False, insert_formatted = False, order_by = ''):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        extstring = ''
        if extended:
            extstring = ",type"
        extstring_package_id = ''
        if insert_formatted:
            extstring_package_id = 'idpackage,'

        searchkeywords = [package_id]
        contentstring = ''
        if contentType:
            searchkeywords.append(contentType)
            contentstring = ' and type = (?)'

        order_by_string = ''
        if order_by:
            order_by_string = ' order by %s' % (order_by,)

        did_try = False
        while True:
            try:

                cur = self._cursor().execute("""
                SELECT %s file%s FROM content WHERE idpackage = (?) %s%s""" % (
                    extstring_package_id, extstring,
                    contentstring, order_by_string,),
                searchkeywords)

                if extended and insert_formatted:
                    fl = cur.fetchall()

                elif extended and formatted:
                    fl = {}
                    items = cur.fetchone()
                    while items:
                        fl[items[0]] = items[1]
                        items = cur.fetchone()

                elif extended:
                    fl = cur.fetchall()

                else:
                    if order_by:
                        fl = self._cur2list(cur)
                    else:
                        fl = self._cur2set(cur)

                break

            except OperationalError:

                if did_try:
                    raise
                did_try = True

                # FIXME support for old entropy db entries, which were
                # not inserted in utf-8
                self._connection().text_factory = lambda x: \
                    const_convert_to_unicode(x)
                continue

        return fl

    def retrieveChangelog(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # FIXME backward compatibility
        if not self._doesTableExist('packagechangelogs'):
            return None

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
        # FIXME backward compatibility
        if not self._doesTableExist('packagechangelogs'):
            return None

        self._connection().text_factory = lambda x: const_convert_to_unicode(x)

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
        cur = self._cursor().execute("""
        SELECT slot FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        slot = cur.fetchone()
        if slot:
            return slot[0]

    def retrieveTag(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT versiontag FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (package_id,))
        vtag = cur.fetchone()
        if vtag:
            return vtag[0]

    def retrieveMirrorData(self, mirrorname):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT mirrorlink FROM mirrorlinks WHERE mirrorname = (?)
        """, (mirrorname,))
        return self._cur2set(cur)

    def retrieveCategory(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT category FROM baseinfo,categories
        WHERE baseinfo.idpackage = (?) AND
        baseinfo.idcategory = categories.idcategory LIMIT 1
        """, (package_id,))

        cat = cur.fetchone()
        if cat:
            return cat[0]

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
            return set()

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

        return licdata

    def retrieveLicenseText(self, license_name):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._connection().text_factory = lambda x: const_convert_to_unicode(x)

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
        self._cursor().execute("""
        SELECT chost,cflags,cxxflags FROM flags,extrainfo 
        WHERE extrainfo.idpackage = (?) AND 
        extrainfo.idflags = flags.idflags""", (package_id,))
        flags = self._cursor().fetchone()
        if not flags:
            flags = ("N/A", "N/A", "N/A",)
        return flags

    def retrieveReverseDependencies(self, package_id, atoms = False,
        key_slot = False, exclude_deptypes = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # WARNING: never remove this, otherwise equo.db
        # (client database) dependstable will be always broken (trust me)
        # sanity check on the table
        c_tup = ("retrieveReverseDependencies_check",)
        if not self.__live_cache.get(c_tup):
            self.__live_cache[c_tup] = True
            if not self._isDependsTableSane(): # is empty, need generation
                self.generateReverseDependenciesMetadata(verbose = False)
                # always force commit, if possible, otherwise this, for
                # read-only repos will be called over and over.
                self.commitChanges(force = True)

        excluded_deptypes_query = ""
        if exclude_deptypes is not None:
            for dep_type in exclude_deptypes:
                excluded_deptypes_query += " AND dependencies.type != %s" % (
                    dep_type,)

        table_name = self._getReverseDependenciesTable()
        if atoms:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom FROM %s,dependencies,baseinfo 
            WHERE %s.idpackage = (?) AND 
            %s.iddependency = dependencies.iddependency AND 
            baseinfo.idpackage = dependencies.idpackage %s""" % (
                table_name, table_name, table_name, excluded_deptypes_query,),
                (package_id,))
            result = self._cur2set(cur)
        elif key_slot:
            cur = self._cursor().execute("""
            SELECT categories.category || "/" || baseinfo.name,baseinfo.slot 
            FROM baseinfo,categories,%s,dependencies 
            WHERE %s.idpackage = (?) AND 
            %s.iddependency = dependencies.iddependency AND 
            baseinfo.idpackage = dependencies.idpackage AND 
            categories.idcategory = baseinfo.idcategory %s""" % (
                table_name, table_name, table_name, excluded_deptypes_query,),
                (package_id,))
            result = cur.fetchall()
        else:
            cur = self._cursor().execute("""
            SELECT dependencies.idpackage FROM %s,dependencies 
            WHERE %s.idpackage = (?) AND 
            %s.iddependency = dependencies.iddependency %s""" % (
                table_name, table_name, table_name, excluded_deptypes_query,),
                (package_id,))
            result = self._cur2set(cur)

        return result

    def retrieveUnusedIdpackages(self):
        """@deprecated"""
        warnings.warn("deprecated call!")
        return self.retrieveUnusedPackageIds()

    def retrieveUnusedPackageIds(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # WARNING: never remove this, otherwise equo.db (client database)
        # dependstable will be always broken (trust me)
        # sanity check on the table
        c_tup = ("retrieveUnusedPackageIds_check",)
        if not self.__live_cache.get(c_tup):
            self.__live_cache[c_tup] = True
            if not self._isDependsTableSane(): # is empty, need generation
                self.generateReverseDependenciesMetadata(verbose = False)
                # always force commit, if possible, otherwise this, for
                # read-only repos will be called over and over.
                self.commitChanges(force = True)

        table_name = self._getReverseDependenciesTable()
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo 
        WHERE idpackage NOT IN (SELECT idpackage FROM %s)
        ORDER BY atom
        """ % (table_name,))
        return self._cur2list(cur)

    def _isAtomAvailable(self, atom):
        """
        Return whether given atom is available in repository.

        @param atom: package atom
        @type atom: string
        @return: package_id or -1 if not found
        @rtype: int
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo WHERE atom = (?) LIMIT 1
        """, (atom,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

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

    def isIdpackageAvailable(self, package_id):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.isPackageIdAvailable(package_id)

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

    def isFileAvailable(self, path, get_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM content WHERE file = (?)""", (path,))
        result = cur.fetchall()
        if get_id:
            return self._fetchall2set(result)
        elif result:
            return True
        return False

    def resolveNeeded(self, needed, elfclass = -1, extended = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # TODO: remove this in future, backward compat.
        if not self._doesTableExist('provided_libs'):
            self._createProvidedLibs()

        args = (needed,)
        elfclass_txt = ''
        if elfclass != -1:
            elfclass_txt = ' AND provided_libs.elfclass = (?)'
            args = (needed, elfclass,)

        if extended:
            cur = self._cursor().execute("""
            SELECT idpackage, path FROM provided_libs
            WHERE library = (?)""" + elfclass_txt, args)
            return cur.fetchall()

        cur = self._cursor().execute("""
        SELECT idpackage FROM provided_libs
        WHERE library = (?)""" + elfclass_txt, args)
        return self._cur2set(cur)

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

    def _isEclassAvailable(self, eclass):
        """
        Return whether eclass name is available in repository.
        Returns Eclass identifier (idclass)

        @param eclass: eclass name
        @type eclass: string
        @return: Eclass identifier or -1 if not found
        @rtype: int
        """
        cur = self._cursor().execute("""
        SELECT idclass FROM eclassesreference WHERE classname = (?) LIMIT 1
        """, (eclass,))
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

    def isLicensedataKeyAvailable(self, license_name):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.isLicenseDataKeyAvailable(license_name)

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
        self.commitChanges()

    def _isLicenseAvailable(self, pkglicense):
        """
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

    def searchBelongs(self, file, like = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if like:
            cur = self._cursor().execute("""
            SELECT content.idpackage FROM content,baseinfo
            WHERE file LIKE (?) AND
            content.idpackage = baseinfo.idpackage""", (file,))
        else:
            cur = self._cursor().execute("""SELECT content.idpackage
            FROM content, baseinfo WHERE file = (?)
            AND content.idpackage = baseinfo.idpackage""", (file,))

        return self._cur2set(cur)

    def searchEclassedPackages(self, eclass, atoms = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if atoms:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom,eclasses.idpackage
            FROM baseinfo, eclasses, eclassesreference
            WHERE eclassesreference.classname = (?) AND
            eclassesreference.idclass = eclasses.idclass AND
            eclasses.idpackage = baseinfo.idpackage""", (eclass,))
            return cur.fetchall()

        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo WHERE versiontag = (?)""", (eclass,))
        return self._cur2set(cur)

    def searchTaggedPackages(self, tag, atoms = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if atoms:
            cur = self._cursor().execute("""
            SELECT atom, idpackage FROM baseinfo WHERE versiontag = (?)
            """, (tag,))
            return cur.fetchall()

        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo WHERE versiontag = (?)
        """, (tag,))
        return self._cur2set(cur)

    def searchRevisionedPackages(self, revision):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo WHERE revision = (?)
        """, (revision,))
        return self._cur2set(cur)

    def searchLicense(self, keyword, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not entropy.tools.is_valid_string(keyword):
            return []

        if just_id:
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM baseinfo,licenses
            WHERE LOWER(licenses.license) LIKE (?) AND
            licenses.idlicense = baseinfo.idlicense
            """, ("%"+keyword+"%".lower(),))
            return self._cur2set(cur)
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom,baseinfo.idpackage FROM baseinfo,licenses
            WHERE LOWER(licenses.license) LIKE (?) AND
            licenses.idlicense = baseinfo.idlicense
            """, ("%"+keyword+"%".lower(),))
            return cur.fetchall()

    def searchSlotted(self, keyword, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if just_id:
            cur = self._cursor().execute("""
            SELECT idpackage FROM baseinfo WHERE slot = (?)""", (keyword,))
            return self._cur2set(cur)
        else:
            cur = self._cursor().execute("""
            SELECT atom,idpackage FROM baseinfo WHERE slot = (?)
            """, (keyword,))
            return cur.fetchall()

    def searchKeySlot(self, key, slot):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cat, name = key.split("/")
        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo, categories
        WHERE baseinfo.idcategory = categories.idcategory AND
        categories.category = (?) AND
        baseinfo.name = (?) AND
        baseinfo.slot = (?)""", (cat, name, slot,))

        return cur.fetchall()

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

        return self._cur2set(cur)

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
            return self._cur2set(cur)
        iddep = cur.fetchone()

        if iddep:
            return iddep[0]
        return -1

    def searchIdpackageFromIddependency(self, iddep):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.searchPackageIdFromDependencyId(iddep)

    def searchPackageIdFromDependencyId(self, dependency_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute("""
        SELECT idpackage FROM dependencies WHERE iddependency = (?)
        """, (dependency_id,))
        return self._cur2set(cur)

    def searchSets(self, keyword):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # FIXME: remove this before 31-12-2011
        if not self._doesTableExist("packagesets"):
            return set()
        cur = self._cursor().execute("""
        SELECT DISTINCT(setname) FROM packagesets WHERE setname LIKE (?)
        """, ("%"+keyword+"%",))

        return self._cur2set(cur)

    def searchProvidedMime(self, mimetype):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        # FIXME: remove this before 31-12-2011
        if not self._doesTableExist("provided_mime"):
            return []
        cur = self._cursor().execute("""
        SELECT provided_mime.idpackage FROM provided_mime, baseinfo
        WHERE provided_mime.mimetype = (?)
        AND baseinfo.idpackage = provided_mime.idpackage
        ORDER BY baseinfo.atom""",
        (mimetype,))
        return self._cur2list(cur)

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

        return self._cur2list(cur)

    def searchPackages(self, keyword, sensitive = False, slot = None,
            tag = None, order_by = 'atom', just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        searchkeywords = ["%"+keyword+"%"]

        slotstring = ''
        if slot:
            searchkeywords.append(slot)
            slotstring = ' and slot = (?)'

        tagstring = ''
        if tag:
            searchkeywords.append(tag)
            tagstring = ' and versiontag = (?)'

        order_by_string = ''
        if order_by in ("atom", "idpackage", "branch",):
            order_by_string = ' order by %s' % (order_by,)

        search_elements = 'atom,idpackage,branch'
        if just_id:
            search_elements = 'idpackage'

        if sensitive:
            cur = self._cursor().execute("""
            SELECT %s FROM baseinfo WHERE atom LIKE (?) %s %s %s""" %  (
                search_elements, slotstring, tagstring, order_by_string,),
                searchkeywords
            )
        else:
            cur = self._cursor().execute("""
            SELECT %s FROM baseinfo WHERE 
            LOWER(atom) LIKE (?) %s %s %s""" % (
                search_elements, slotstring, tagstring, order_by_string,),
                searchkeywords
            )

        if just_id:
            return self._cur2list(cur)
        return cur.fetchall()

    def searchProvidedVirtualPackage(self, keyword):
        """
        Search in old-style Portage PROVIDE metadata.
        @todo: rewrite docstring :-)

        @param keyword: search term
        @type keyword: string
        @return: found PROVIDE metadata
        @rtype: list
        """
        # FIXME: this small snippet is here for backward compat
        if self._doesColumnInTableExist("provide", "is_default"):
            get_def_string = ",provide.is_default"
        else:
            get_def_string = ",0"

        cur = self._cursor().execute("""
        SELECT baseinfo.idpackage%s FROM baseinfo,provide 
        WHERE provide.atom = (?) AND 
        provide.idpackage = baseinfo.idpackage""" % (get_def_string,),
            (keyword,))

        return cur.fetchall()

    def searchDescription(self, keyword, just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if just_id:
            cur = self._cursor().execute("""
            SELECT baseinfo.idpackage FROM extrainfo, baseinfo
            WHERE LOWER(extrainfo.description) LIKE (?) AND
            baseinfo.idpackage = extrainfo.idpackage
            """, ("%"+keyword.lower()+"%",))
            return self._cur2set(cur)
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom, baseinfo.idpackage FROM extrainfo, baseinfo
            WHERE LOWER(extrainfo.description) LIKE (?) AND
            baseinfo.idpackage = extrainfo.idpackage
            """, ("%"+keyword.lower()+"%",))
            return cur.fetchall()

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
            return self._cur2set(cur)
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom, baseinfo.idpackage FROM extrainfo, baseinfo
            WHERE LOWER(extrainfo.homepage) LIKE (?) AND
            baseinfo.idpackage = extrainfo.idpackage
            """, ("%"+keyword.lower()+"%",))
            return cur.fetchall()

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
            return self._cur2list(cur)
        return cur.fetchall()


    def searchCategory(self, keyword, like = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if like:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom,baseinfo.idpackage FROM baseinfo,categories
            WHERE categories.category LIKE (?) AND
            baseinfo.idcategory = categories.idcategory
            """, (keyword,))
        else:
            cur = self._cursor().execute("""
            SELECT baseinfo.atom,baseinfo.idpackage FROM baseinfo,categories
            WHERE categories.category = (?) AND
            baseinfo.idcategory = categories.idcategory
            """, (keyword,))

        return cur.fetchall()

    def searchNameCategory(self, name, category, sensitive = False,
        just_id = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        atomstring = ''
        if not just_id:
            atomstring = 'atom,'

        if sensitive:
            cur = self._cursor().execute("""
            SELECT %s idpackage FROM baseinfo
            WHERE name = (?) AND
            idcategory IN (
                SELECT idcategory FROM categories
                WHERE category = (?)
            )""" % (atomstring,), (name, category,))
        else:
            cur = self._cursor().execute("""
            SELECT %s idpackage FROM baseinfo
            WHERE LOWER(name) = (?) AND
            idcategory IN (
                SELECT idcategory FROM categories
                WHERE LOWER(category) = (?)
            )""" % (atomstring,), (name.lower(), category.lower(),))

        if just_id:
            return self._cur2list(cur)
        return cur.fetchall()

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

    def listIdPackagesInIdcategory(self, *args, **kwargs):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.listPackageIdsInCategoryId(*args, **kwargs)

    def listPackageIdsInCategoryId(self, category_id, order_by = None):
        """
        List package identifiers available in given category identifier.

        @param category_id: cateogory identifier
        @type category_id: int
        @keyword order_by: order by "atom", "name", "version"
        @type order_by: string
        @return: list (set) of available package identifiers in category.
        @rtype: set
        """
        order_by_string = ''
        if order_by in ("atom", "name", "version",):
            order_by_string = ' ORDER BY %s' % (order_by,)

        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo where idcategory = (?)
        """ + order_by_string, (category_id,))

        return self._cur2set(cur)

    def listAllPackages(self, get_scope = False, order_by = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        order_txt = ''
        if order_by:
            order_txt = ' ORDER BY %s' % (order_by,)

        if get_scope:
            cur = self._cursor().execute("""
            SELECT idpackage,atom,slot,revision FROM baseinfo""" + order_txt)
        else:
            cur = self._cursor().execute("""
            SELECT atom,idpackage,branch FROM baseinfo""" + order_txt)

        return cur.fetchall()

    def listAllSpmUids(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        cur = self._cursor().execute('SELECT counter, idpackage FROM counters')
        return cur.fetchall()

    def listAllIdpackages(self, *args, **kwargs):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.listAllPackageIds(*args, **kwargs)

    def listAllPackageIds(self, order_by = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        orderbystring = ''
        if order_by:
            orderbystring = ' ORDER BY '+order_by

        cur = self._cursor().execute("""
        SELECT idpackage FROM baseinfo""" + orderbystring)

        try:
            if order_by:
                return self._cur2list(cur)
            return self._cur2set(cur)
        except OperationalError:
            if order_by:
                return []
            return set()

    def _listAllDependencies(self):
        """
        List all dependencies available in repository.

        @return: list of tuples of length 2 containing (iddependency, dependency
            name,)
        @rtype: list
        """
        cur = self._cursor().execute("""
        SELECT iddependency, dependency FROM dependenciesreference""")
        return cur.fetchall()

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
            results = self._cur2list(cur)
        else:
            results = self._cur2set(cur)

        if not full_path:
            results = [os.path.basename(x) for x in results]

        return results

    def listAllCategories(self, order_by = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        order_by_string = ''
        if order_by:
            order_by_string = ' order by %s' % (order_by,)
        self._cursor().execute('SELECT idcategory,category FROM categories %s' % (
            order_by_string,))
        return self._cursor().fetchall()

    def listConfigProtectEntries(self, mask = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        mask_t = ''
        if mask:
            mask_t = 'mask'
        cur = self._cursor().execute("""
        SELECT protect FROM configprotectreference WHERE idprotect IN
            (SELECT distinct(idprotect) FROM configprotect%s)
        ORDER BY protect""" % (mask_t,))

        results = self._cur2set(cur)
        dirs = set()
        for mystr in results:
            dirs.update(mystr.split())

        return sorted(dirs)

    def switchBranch(self, package_id, tobranch):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE baseinfo SET branch = (?)
        WHERE idpackage = (?)""", (tobranch, package_id,))
        self.commitChanges()
        self.clearCache()

    def getSetting(self, setting_name):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if setting_name not in self._SETTING_KEYS:
            raise KeyError
        try:
            self._cursor().execute("""
            SELECT setting_value FROM settings WHERE setting_name = (?)
            """, (setting_name,))
        except Error:
            raise KeyError

        setting = self._cursor().fetchone()
        if setting is None:
            raise KeyError
        return setting[0]

    def _setupInitialSettings(self):
        """
        Setup initial repository settings
        """
        self._cursor().executescript("""
            INSERT OR REPLACE INTO settings VALUES ("arch", "%s");
            INSERT OR REPLACE INTO settings VALUES ("on_delete_cascade", "%s");
            """ % (etpConst['currentarch'], "1",)
        )

    def _databaseStructureUpdates(self):

        old_readonly = self.readonly
        self.readonly = False

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

        if not self._doesTableExist("dependstable"):
            self._createDependsTable()

        if not self._doesTableExist("settings"):
            self._createSettingsTable()

        self._foreignKeySupport()

        self.readonly = old_readonly
        self._connection().commit()

    def validateDatabase(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        live_cache_id = ("validateDatabase",)
        cached = self.__live_cache.get(live_cache_id)
        if cached is not None:
            return
        self.__live_cache[live_cache_id] = True

        # use sqlite3 pragma
        pingus = MtimePingus()
        # since quick_check is slow, run it every 72 hours
        action_str = "EntropyRepository.validateDatabase(%s)" % (
            self.reponame,)
        passed = pingus.hours_passed(action_str, 72)
        if passed:
            cur = self._cursor().execute("PRAGMA quick_check(1)")
            try:
                check_data = cur.fetchone()[0]
                if check_data != "ok":
                    raise ValueError()
            except (IndexError, ValueError, TypeError,):
                mytxt = "sqlite3 reports database being corrupted"
                raise SystemDatabaseError("SystemDatabaseError: %s" % (mytxt,))
            pingus.ping(action_str)

        mytxt = "Repository is corrupted, missing SQL tables!"
        self._cursor().execute("""
        SELECT count(name) FROM SQLITE_MASTER WHERE type = "table" AND (
            name = "extrainfo" OR name = "baseinfo" OR name = "keywords" )
        """)
        rslt = self._cursor().fetchone()
        if rslt is None:
            raise SystemDatabaseError("SystemDatabaseError: %s" % (mytxt,))
        elif rslt[0] != 3:
            raise SystemDatabaseError("SystemDatabaseError: %s" % (mytxt,))

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
        self.commitChanges()
        self.generateReverseDependenciesMetadata(verbose = False)
        dbconn.clearCache()

        # verify both checksums, if they don't match, bomb out
        mycheck = self.checksum(do_order = True, strict = False)
        outcheck = dbconn.checksum(do_order = True, strict = False)
        if mycheck == outcheck:
            return 1
        return 0

    def checkDatabaseApi(self):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return

    def doDatabaseImport(self, *args, **kwargs):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.importRepository(*args, **kwargs)

    def doDatabaseExport(self, *args, **kwargs):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.exportRepository(*args, **kwargs)

    def importRepository(self, dumpfile, dbfile):
        """
        Reimplemented from EntropyRepositoryBase.
        @todo: remove /usr/bin/sqlite3 dependency
        """
        sqlite3_exec = "/usr/bin/sqlite3 %s < %s" % (dbfile, dumpfile,)
        retcode = subprocess.call(sqlite3_exec, shell = True)
        return retcode

    def exportRepository(self, dumpfile, gentle_with_tables = True,
        exclude_tables = None):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        if not exclude_tables:
            exclude_tables = []

        toraw = const_convert_to_rawstring

        dumpfile.write(toraw("BEGIN TRANSACTION;\n"))
        self._cursor().execute("""
        SELECT name, type, sql FROM sqlite_master
        WHERE sql NOT NULL AND type=='table'
        """)
        for name, x, sql in self._cursor().fetchall():

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

            self._cursor().execute("PRAGMA table_info('%s')" % name)
            cols = [r[1] for r in self._cursor().fetchall()]
            q = "SELECT 'INSERT INTO \"%(tbl_name)s\" VALUES("
            q += ", ".join(["'||quote(" + x + ")||'" for x in cols])
            q += ")' FROM '%(tbl_name)s'"
            self._cursor().execute(q % {'tbl_name': name})
            self._connection().text_factory = lambda x: \
                const_convert_to_unicode(x)
            for row in self._cursor():
                dumpfile.write(toraw("%s;\n" % (row[0],)))

        self._cursor().execute("""
        SELECT name, type, sql FROM sqlite_master
        WHERE sql NOT NULL AND type!='table' AND type!='meta'
        """)
        for name, x, sql in self._cursor().fetchall():
            dumpfile.write(toraw("%s;\n" % sql))

        dumpfile.write(toraw("COMMIT;\n"))
        try:
            dumpfile.flush()
        except:
            pass
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
        SELECT name FROM SQLITE_MASTER WHERE type = "table"
        """)
        return self._cur2list(cur)

    def _doesTableExist(self, table, temporary = False):

        # NOTE: override cache when temporary is True
        if temporary:
            # temporary table do not pop-up with the statement below, so
            # we need to handle them with "care"
            try:
                self._cursor().execute("""
                SELECT count(*) FROM (?) LIMIT 1""", (table,))
            except OperationalError:
                return False
            return True

        # speed up a bit if we already reported a table as existing
        c_tup = ("_doesTableExist", table,)
        cached = self.__live_cache.get(c_tup)
        if cached is not None:
            return cached

        cur = self._cursor().execute("""
        SELECT name FROM SQLITE_MASTER WHERE type = "table" AND name = (?)
        LIMIT 1
        """, (table,))
        rslt = cur.fetchone()
        exists = rslt is not None
        if exists:
            self.__live_cache[c_tup] = True
        return exists

    def _doesColumnInTableExist(self, table, column):

        # speed up a bit if we already reported a column as existing
        c_tup = ("_doesColumnInTableExist", table, column,)
        cached = self.__live_cache.get(c_tup)
        if cached is not None:
            return cached

        cur = self._cursor().execute('PRAGMA table_info( %s )' % (table,))
        rslt = (x[1] for x in cur.fetchall())
        if column in rslt:
            self.__live_cache[c_tup] = True
            return True
        return False

    def checksum(self, do_order = False, strict = True,
        strings = False, include_signatures = False):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        c_tup = ("checksum", do_order, strict, strings, include_signatures,)
        cache = self.__live_cache.get(c_tup)
        if cache is not None:
            return cache

        package_id_order = ''
        category_order = ''
        license_order = ''
        flags_order = ''
        if do_order:
            package_id_order = 'order by idpackage'
            category_order = 'order by category'
            license_order = 'order by license'
            flags_order = 'order by chost'

        def do_update_md5(m, cursor):
            mydata = cursor.fetchall()
            for record in mydata:
                for item in record:
                    m.update(const_convert_to_rawstring(item))

        if strings:
            m = hashlib.md5()


        if not self._doesTableExist("baseinfo"):
            if strings:
                m.update(const_convert_to_rawstring("~empty~"))
                result = m.hexdigest()
            else:
                result = "~empty_db~"
            self.__live_cache[c_tup] = result[:]
            return result

        cur = self._cursor().execute("""
        SELECT idpackage,atom,name,version,versiontag,
        revision,branch,slot,etpapi,trigger FROM 
        baseinfo %s""" % (package_id_order,))
        if strings:
            do_update_md5(m, cur)
        else:
            a_hash = hash(tuple(cur.fetchall()))


        cur = self._cursor().execute("""
        SELECT idpackage, description, homepage,
        download, size, digest, datecreation FROM
        extrainfo %s""" % (package_id_order,))
        if strings:
            do_update_md5(m, cur)
        else:
            b_hash = hash(tuple(cur.fetchall()))

        if include_signatures:
            # TODO: backward compatibility, remove this in future
            gpg_str = ", gpg"
            if not self._doesColumnInTableExist("packagesignatures", "gpg"):
                gpg_str = ""
            cur = self._cursor().execute("""
            SELECT idpackage, sha1%s FROM
            packagesignatures %s""" % (gpg_str, package_id_order,))
            if strings:
                do_update_md5(m, cur)
            else:
                b_hash = "%s%s" % (b_hash, hash(tuple(cur.fetchall())),)

        cur = self._cursor().execute("""
        SELECT category FROM categories %s
        """ % (category_order,))
        if strings:
            do_update_md5(m, cur)
        else:
            c_hash = hash(tuple(cur.fetchall()))


        d_hash = '0'
        e_hash = '0'
        if strict:
            cur = self._cursor().execute("""
            SELECT * FROM licenses %s""" % (license_order,))
            if strings:
                do_update_md5(m, cur)
            else:
                d_hash = hash(tuple(cur.fetchall()))

            cur = self._cursor().execute('select * from flags %s' % (flags_order,))
            if strings:
                do_update_md5(m, cur)
            else:
                e_hash = hash(tuple(cur.fetchall()))

        if strings:
            result = m.hexdigest()
        else:
            result = "%s:%s:%s:%s:%s" % (a_hash, b_hash, c_hash, d_hash,
                e_hash,)

        self.__live_cache[c_tup] = result[:]
        return result

    def storeInstalledPackage(self, package_id, repoid, source = 0):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('INSERT into installedtable VALUES (?,?,?)',
            (package_id, repoid, source,))

    def getInstalledPackageRepository(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        try:
            cur = self._cursor().execute("""
            SELECT repositoryname FROM installedtable
            WHERE idpackage = (?) LIMIT 1""", (package_id,))
            return cur.fetchone()[0]
        except (OperationalError, TypeError,):
            return None

    def dropInstalledPackageFromStore(self, package_id):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM installedtable
        WHERE idpackage = (?)""", (package_id,))

    def _createDependsTable(self, temporary = False):
        temp_txt = ""
        temp_txt_table = "dependstable"
        fk_data = """, FOREIGN KEY(idpackage) REFERENCES 
        baseinfo(idpackage) ON DELETE CASCADE"""
        if temporary:
            temp_txt = "TEMPORARY"
            temp_txt_table = "dependstable_temp"
            fk_data = ""

        self._cursor().executescript("""
        CREATE %s TABLE IF NOT EXISTS %s
        ( iddependency INTEGER PRIMARY KEY, idpackage INTEGER%s );
        INSERT INTO %s VALUES (-1,NULL);
        """ % (temp_txt, temp_txt_table, fk_data, temp_txt_table,))
        if self.indexing:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS dependsindex%s_idpackage
            ON %s ( idpackage )
            """ % (temp_txt_table, temp_txt_table,))
        self.commitChanges()

    def _sanitizeDependsTable(self):
        self._cursor().execute("""
        DELETE FROM dependstable where iddependency = -1
        """)
        self.commitChanges()

    def _isDependsTableSane(self):

        table_name = self._getReverseDependenciesTable()
        try:
            cur = self._cursor().execute("""
            SELECT iddependency FROM %s WHERE iddependency = -1
            """ % (table_name,))
        except (OperationalError,):
            return False # table does not exist, please regenerate and re-run

        status = cur.fetchone()
        if status:
            return False

        cur = self._cursor().execute("""
        SELECT count(iddependency) FROM %s
        """ % (table_name,))
        data = cur.fetchone()
        count = 0
        if data:
            count = data[0]

        return count > 1

    def storeXpakMetadata(self, *args, **kwargs):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.storeSpmMetadata(*args, **kwargs)

    def storeSpmMetadata(self, package_id, blob):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('INSERT into xpakdata VALUES (?,?)',
            (package_id, const_get_buffer()(blob),)
        )
        self.commitChanges()

    def retrieveXpakMetadata(self, *args, **kwargs):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.retrieveSpmMetadata(*args, **kwargs)

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
        """)
        indexes = self._cur2set(cur)
        for index in indexes:
            try:
                self._cursor().execute('DROP INDEX IF EXISTS %s' % (index,))
            except Error:
                continue

    def createAllIndexes(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
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
        self._createLicensesIndex()
        self._createConfigProtectReferenceIndex()
        self._createSourcesIndex()
        self._createCountersIndex()
        self._createEclassesIndex()
        self._createCategoriesIndex()
        self._createCompileFlagsIndex()
        self._createPackagesetsIndex()
        self._createAutomergefilesIndex()
        self._createProvidedLibsIndex()
        self._createDesktopMimeIndex()
        self._createProvidedMimeIndex()

    def _createMirrorlinksIndex(self):
        if self.indexing:
            try:
                self._cursor().execute("""
                CREATE INDEX IF NOT EXISTS mirrorlinks_mirrorname
                ON mirrorlinks ( mirrorname )""")
            except OperationalError:
                pass

    def _createDesktopMimeIndex(self):
        if self.indexing:
            try:
                self._cursor().execute("""
                CREATE INDEX IF NOT EXISTS packagedesktopmime_idpackage
                ON packagedesktopmime ( idpackage )""")
            except OperationalError:
                pass

    def _createProvidedMimeIndex(self):
        if self.indexing:
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
        if self.indexing:
            try:
                self._cursor().execute("""
                CREATE INDEX IF NOT EXISTS packagesetsindex
                ON packagesets ( setname )""")
            except OperationalError:
                pass

    def _createProvidedLibsIndex(self):
        if self.indexing:
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
        if self.indexing:
            try:
                self._cursor().executescript("""
                    CREATE INDEX IF NOT EXISTS automergefiles_idpackage 
                    ON automergefiles ( idpackage );
                    CREATE INDEX IF NOT EXISTS automergefiles_file_md5 
                    ON automergefiles ( configfile, md5 );
                """)
            except OperationalError:
                pass

    def _createNeededIndex(self):
        if self.indexing:
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

    def _createCompileFlagsIndex(self):
        if self.indexing:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS flagsindex ON flags
                ( chost, cflags, cxxflags )
            """)

    def _createUseflagsIndex(self):
        if self.indexing:
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS useflagsindex_useflags_idpackage
                ON useflags ( idpackage );
            CREATE INDEX IF NOT EXISTS useflagsindex_useflags_idflag
                ON useflags ( idflag );
            CREATE INDEX IF NOT EXISTS useflagsindex
                ON useflagsreference ( flagname );
            """)

    def _createContentIndex(self):
        if self.indexing:
            if self._doesTableExist("content"):
                self._cursor().executescript("""
                    CREATE INDEX IF NOT EXISTS contentindex_couple
                        ON content ( idpackage );
                    CREATE INDEX IF NOT EXISTS contentindex_file
                        ON content ( file );
                """)

    def _createConfigProtectReferenceIndex(self):
        if self.indexing:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS configprotectreferenceindex
                ON configprotectreference ( protect )
            """)

    def _createBaseinfoIndex(self):
        if self.indexing:
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS baseindex_atom
                ON baseinfo ( atom );
            CREATE INDEX IF NOT EXISTS baseindex_branch_name
                ON baseinfo ( name,branch );
            CREATE INDEX IF NOT EXISTS baseindex_branch_name_idcategory
                ON baseinfo ( name,idcategory,branch );
            CREATE INDEX IF NOT EXISTS baseindex_idcategory
                ON baseinfo ( idcategory );
            """)

    def _createLicensedataIndex(self):
        if self.indexing:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS licensedataindex
                ON licensedata ( licensename )
            """)

    def _createLicensesIndex(self):
        if self.indexing:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS licensesindex ON licenses ( license )
            """)

    def _createCategoriesIndex(self):
        if self.indexing:
            self._cursor().execute("""
            CREATE INDEX IF NOT EXISTS categoriesindex_category
                ON categories ( category )
            """)

    def _createKeywordsIndex(self):
        if self.indexing:
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS keywordsreferenceindex
                ON keywordsreference ( keywordname );
            CREATE INDEX IF NOT EXISTS keywordsindex_idpackage
                ON keywords ( idpackage );
            CREATE INDEX IF NOT EXISTS keywordsindex_idkeyword
                ON keywords ( idkeyword );
            """)

    def _createDependenciesIndex(self):
        if self.indexing:
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS dependenciesindex_idpackage
                ON dependencies ( idpackage );
            CREATE INDEX IF NOT EXISTS dependenciesindex_iddependency
                ON dependencies ( iddependency );
            CREATE INDEX IF NOT EXISTS dependenciesreferenceindex_dependency
                ON dependenciesreference ( dependency );
            """)

    def _createCountersIndex(self):
        if self.indexing:
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS countersindex_idpackage
                ON counters ( idpackage );
            CREATE INDEX IF NOT EXISTS countersindex_counter
                ON counters ( counter );
            """)

    def _createSourcesIndex(self):
        if self.indexing:
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS sourcesindex_idpackage
                ON sources ( idpackage );
            CREATE INDEX IF NOT EXISTS sourcesindex_idsource
                ON sources ( idsource );
            CREATE INDEX IF NOT EXISTS sourcesreferenceindex_source
                ON sourcesreference ( source );
            """)

    def _createProvideIndex(self):
        if self.indexing:
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS provideindex_idpackage
                ON provide ( idpackage );
            CREATE INDEX IF NOT EXISTS provideindex_atom
                ON provide ( atom );
            """)

    def _createConflictsIndex(self):
        if self.indexing:
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS conflictsindex_idpackage
                ON conflicts ( idpackage );
            CREATE INDEX IF NOT EXISTS conflictsindex_atom
                ON conflicts ( conflict );
            """)

    def _createExtrainfoIndex(self):
        if self.indexing:
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS extrainfoindex
                ON extrainfo ( description );
            CREATE INDEX IF NOT EXISTS extrainfoindex_pkgindex
                ON extrainfo ( idpackage );
            """)

    def _createEclassesIndex(self):
        if self.indexing:
            self._cursor().executescript("""
            CREATE INDEX IF NOT EXISTS eclassesindex_idpackage
                ON eclasses ( idpackage );
            CREATE INDEX IF NOT EXISTS eclassesindex_idclass
                ON eclasses ( idclass );
            CREATE INDEX IF NOT EXISTS eclassesreferenceindex_classname
                ON eclassesreference ( classname );
            """)

    def regenerateSpmUidTable(self, *args, **kwargs):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.regenerateSpmUidTable()

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

        self.commitChanges()

    def clearTreeupdatesEntries(self, repository):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        DELETE FROM treeupdates WHERE repository = (?)
        """, (repository,))
        self.commitChanges()

    def resetTreeupdatesDigests(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute('UPDATE treeupdates SET digest = "-1"')
        self.commitChanges()

    def _foreignKeySupport(self):

        # TODO: remove this by 2011/12/31

        # entropy.qa uses this dbname, must skip migration
        if self.reponame in ("qa_testing", "mem_repo"):
            return

        tables = ("extrainfo", "dependencies" ,"provide",
            "conflicts", "configprotect", "configprotectmask", "sources",
            "useflags", "keywords", "content", "counters", "sizes",
            "eclasses", "needed", "triggers", "systempackages", "injected",
            "installedtable", "automergefiles", "packagesignatures",
            "packagespmphases", "provided_libs", "dependstable"
        )

        done_something = False
        for table in tables:
            if not self._doesTableExist(table): # wtf
                continue

            cur = self._cursor().execute("PRAGMA foreign_key_list(%s)" % (table,))
            foreign_keys = cur.fetchone()

            # print table, "foreign keys", foreign_keys
            if foreign_keys is not None:
                continue

            if not done_something:
                mytxt = "%s: [%s] %s" % (
                    bold(_("ATTENTION")),
                    purple(self.reponame),
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
            self._cursor().execute("""
                INSERT OR REPLACE INTO settings
                VALUES ("on_delete_cascade", "1")
            """)
            # recreate indexes
            self.createAllIndexes()

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
            DROP TABLE IF EXISTS counterstemp;
            CREATE TABLE counterstemp (
                counter INTEGER, idpackage INTEGER, branch VARCHAR,
                PRIMARY KEY(idpackage,branch),
                FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
            );
            INSERT INTO counterstemp (counter, idpackage, branch)
                SELECT counter, idpackage, branch FROM counters;
            DROP TABLE counters;
            ALTER TABLE counterstemp RENAME TO counters;
        """)
        self.commitChanges()

    def _createSettingsTable(self):
        self._cursor().executescript("""
            CREATE TABLE settings (
                setting_name VARCHAR,
                setting_value VARCHAR,
                PRIMARY KEY(setting_name)
            );
        """)
        self._setupInitialSettings()

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

        # TODO: this is going to be removed soon
        client_repo = self.get_plugins_metadata().get('client_repo')

        if client_repo and (self.reponame != etpConst['clientdbid']):
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

    def _createProvideDefault(self):
        self._cursor().execute("""
        ALTER TABLE provide ADD COLUMN is_default INTEGER DEFAULT 0
        """)

    def _createInstalledTableSource(self):
        self._cursor().execute("""
        ALTER TABLE installedtable ADD source INTEGER;
        """)
        self._cursor().execute("""
        UPDATE installedtable SET source = (?)
        """, (etpConst['install_sources']['unknown'],))

    def _createPackagechangelogsTable(self):
        self._cursor().execute("""
        CREATE TABLE packagechangelogs ( category VARCHAR,
            name VARCHAR, changelog BLOB, PRIMARY KEY (category, name));
        """)

    def _createAutomergefilesTable(self):
        self._cursor().execute("""
        CREATE TABLE automergefiles ( idpackage INTEGER,
            configfile VARCHAR, md5 VARCHAR,
            FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage)
            ON DELETE CASCADE );
        """)

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

    def _createPackagesignaturesGpgColumn(self):
        self._cursor().execute("""
        ALTER TABLE packagesignatures ADD gpg BLOB;
        """)

    def _createPackagespmphases(self):
        self._cursor().execute("""
            CREATE TABLE packagespmphases (
                idpackage INTEGER PRIMARY KEY,
                phases VARCHAR,
                FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
            );
        """)

    def _createPackagespmrepository(self):
        self._cursor().execute("""
            CREATE TABLE packagespmrepository (
                idpackage INTEGER PRIMARY KEY,
                repository VARCHAR,
                FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
            );
        """)

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

    def _createPackagesetsTable(self):
        self._cursor().execute("""
        CREATE TABLE packagesets ( setname VARCHAR, dependency VARCHAR );
        """)

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

    def _createProvidedMimeTable(self):
        self._cursor().execute("""
        CREATE TABLE provided_mime (
            mimetype VARCHAR,
            idpackage INTEGER,
            FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
        );
        """)

    def createCategoriesdescriptionTable(self):
        self._cursor().execute("""
        CREATE TABLE categoriesdescription ( category VARCHAR,
            locale VARCHAR, description VARCHAR );
        """)

    def createLicensedataTable(self):
        self._cursor().execute("""
        CREATE TABLE licensedata ( licensename VARCHAR UNIQUE,
            text BLOB, compressed INTEGER );
        """)

    def _createLicensesAcceptedTable(self):
        self._cursor().execute("""
        CREATE TABLE licenses_accepted ( licensename VARCHAR UNIQUE );
        """)

    def _addDependsRelationToDependsTable(self, iterable):
        # since this is not bulletproof (because user can mess with this
        # stuff via SPM), we need to IGNORE IntegrityError exceptions
        # caused by foreign constraint violation
        try:
            self._cursor().executemany("""
                INSERT or REPLACE into dependstable VALUES (?,?)""",
                    iterable)
        except IntegrityError:
            # ouch, need to cope with that and execute each insert manually
            for iddep, package_id in iterable:
                try:
                    self._cursor().execute("""
                        INSERT or REPLACE into dependstable VALUES (?,?)""",
                            (iddep, package_id,))
                except IntegrityError:
                    continue
        except OperationalError:
            # ouch, we cannot write on db file, but still we need to store
            # the dep map and make unprivileged uids to get correct information
            # out of this, since it's stuff we can give away for free.
            # So, let's create a temp table, this will work.
            self._createDependsTable(temporary = True)
            self._cursor().executemany("""
                INSERT or REPLACE into dependstable_temp VALUES (?,?)""",
                    iterable)
            # from now on, reverse dependencies should be considered
            # runtime generated only.
            self._temp_reverse_deps = True
            # no need to execute stuff below this
            return

        # prune old iddependencies
        # NOTE: maybe use ON DELETE CASCADE + foreign key reference?
        cur = self._cursor().execute("SELECT iddependency from dependstable")
        cur_iddeps = self._cur2set(cur)
        my_iddeps = set(x for x, y in iterable)
        to_be_pruned = cur_iddeps - my_iddeps
        if to_be_pruned:
            prune_list = [(x,) for x in to_be_pruned]
            self._cursor().executemany("""
            DELETE FROM dependstable WHERE iddependency = (?)
            """, prune_list)

    def _getReverseDependenciesTable(self):
        """
        Internal method. When reverse dependencies table is not available
        and user has no privileges to make it automatically generated by
        the EntropyRepository logic, we need to fallback to a temporary table.
        This method just returns the available reverse dependency table that
        this instance should use. It does not check if user has write
        permissions but rather if the temporary table exists.
        """
        if self._temp_reverse_deps:
            return "dependstable_temp"
        return "dependstable"

    def taintReverseDependenciesMetadata(self):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        table_name = self._getReverseDependenciesTable()
        try:
            self._cursor().executescript("""
            INSERT or IGNORE INTO %s VALUES (-1,NULL);
            """ % (table_name,))
        except (OperationalError,):
            # FIXME: backward compatibility
            return

    def generateReverseDependenciesMetadata(self, verbose = True):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        depends = self._listAllDependencies()
        count = 0
        total = len(depends)
        mydata = set()
        self.taintReverseDependenciesMetadata()
        self.commitChanges()
        for iddep, atom in depends:
            count += 1
            if iddep == -1:
                continue

            if verbose and ((count == 0) or (count % 150 == 0) or \
                (count == total)):
                self.output( red("Resolving %s") % (atom,), importance = 0,
                    level = "info", back = True, count = (count, total))

            # not safe to use cache here, people messing with multiple
            # instances can make this crash
            package_id, rc = self.atomMatch(atom, useCache = False)
            if package_id != -1:
                mydata.add((iddep, package_id,))

        # after this step, it'll be sane for sure
        if mydata:
            # NOTE: no need to call _sanitizeDependsTable()
            # _addDependsRelationToDependsTable() already removes
            # iddependency = -1
            self._addDependsRelationToDependsTable(mydata)
        else:
            self._sanitizeDependsTable()

        super(EntropyRepository, self).generateReverseDependenciesMetadata(
            verbose = verbose)

    def moveSpmUidsToBranch(self, to_branch):
        """
        Reimplemented from EntropyRepositoryBase.
        """
        self._cursor().execute("""
        UPDATE counters SET branch = (?)
        """, (to_branch,))
        self.commitChanges()
        self.clearCache()

    def idpackageValidator(self, *args, **kwargs):
        """ @deprecated """
        warnings.warn("deprecated call!")
        return self.maskFilter(*args, **kwargs)
