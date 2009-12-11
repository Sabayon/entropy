# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
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

    @todo: migrate to "_" (underscore) convention

"""
import sys
import os
import shutil
from entropy.const import etpConst, etpCache, const_setup_file, \
    const_isunicode, const_convert_to_unicode, const_get_buffer, \
    const_convert_to_rawstring, const_cmp
from entropy.exceptions import IncorrectParameter, InvalidAtom, \
    SystemDatabaseError, OperationNotPermitted, RepositoryPluginError, SPMError
from entropy.i18n import _
from entropy.output import brown, bold, red, blue, purple, darkred, darkgreen, \
    TextInterface
from entropy.cache import EntropyCacher
from entropy.core.settings.base import SystemSettings
from entropy.spm.plugins.factory import get_default_instance as get_spm
from entropy.db.plugin_store import EntropyRepositoryPluginStore

try: # try with sqlite3 from >=python 2.5
    from sqlite3 import dbapi2
except ImportError: # fallback to pysqlite
    try:
        from pysqlite2 import dbapi2
    except ImportError as e:
        raise SystemError(
            "%s. %s: %s" % (
                _("Entropy needs Python compiled with sqlite3 support"),
                _("Error"),
                e,
            )
        )

class EntropyRepository(EntropyRepositoryPluginStore, TextInterface):

    """
    EntropyRepository implements SQLite3 based storage. In a Model-View based
    pattern, it can be considered the "model".
    Actually it's the only one available but more model backends will be
    supported in future (which will inherit this class directly).

    Every Entropy repository storage interface MUST inherit from this base
    class.

    @todo: refactoring and generalization needed
    """

    SETTING_KEYS = [ "arch", "on_delete_cascade" ]

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
                    idpackage INTEGER
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

                CREATE TABLE messages (
                    idpackage INTEGER,
                    message VARCHAR,
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

                CREATE TABLE packagesignatures (
                    idpackage INTEGER PRIMARY KEY,
                    sha1 VARCHAR,
                    sha256 VARCHAR,
                    sha512 VARCHAR,
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

    import entropy.tools as entropyTools
    import entropy.dump as dumpTools
    import threading
    def __init__(self, readOnly = False, dbFile = None, xcache = False,
        dbname = 'etpdb:', indexing = True, skipChecks = False):

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
        """
        EntropyRepositoryPluginStore.__init__(self)

        self.dbclosed = True
        self.SystemSettings = SystemSettings()
        self.dbMatchCacheKey = etpCache['dbMatch']
        self.client_settings_plugin_id = \
            etpConst['system_settings_plugins_ids']['client_plugin']
        self.db_branch = self.SystemSettings['repositories']['branch']
        self.Cacher = EntropyCacher()

        self.dbname = dbname
        if self.dbname == etpConst['clientdbid']:
            self.db_branch = None

        if dbFile is None:
            raise IncorrectParameter("IncorrectParameter: %s" % (
                _("valid database path needed"),) )

        self.__write_mutex = self.threading.RLock()
        self.dbapi2 = dbapi2
        # setup service interface
        self.readOnly = readOnly
        self.xcache = xcache
        self.indexing = indexing
        self.skipChecks = skipChecks
        self.dbFile = dbFile
        self.live_cache = {}

        # create connection
        self.connection = self.dbapi2.connect(dbFile, timeout=300.0,
            check_same_thread = False)
        self.cursor = self.connection.cursor()

        # !!! enable foreign keys pragma !!! do not remove this
        # otherwise removePackage won't work properly
        self.cursor.execute("pragma foreign_keys = 1")

        structure_update = False
        if not self.skipChecks:

            if not self.entropyTools.is_user_in_entropy_group():
                # forcing since we won't have write access to db
                self.indexing = False
            # live systems don't like wasting RAM
            if self.entropyTools.islive():
                self.indexing = False

            try:
                if os.access(self.dbFile, os.W_OK) and \
                    self._doesTableExist('baseinfo') and \
                    self._doesTableExist('extrainfo'):

                    if self.entropyTools.islive(): # this works
                        if etpConst['systemroot']:
                            structure_update = True
                    else:
                        structure_update = True

            except self.dbapi2.Error:
                self.cursor.close()
                self.connection.close()
                raise

        # now we can set this to False
        self.dbclosed = False

        if structure_update:
            self._databaseStructureUpdates()

    def setCacheSize(self, size):
        """
        Change low-level, storage engine based cache size.

        @param size: new size
        @type size: int
        """
        self.cursor.execute('PRAGMA cache_size = %s' % (size,))

    def setDefaultCacheSize(self, size):
        """
        Change default low-level, storage engine based cache size.

        @param size: new default size
        @type size: int
        """
        self.cursor.execute('PRAGMA default_cache_size = %s' % (size,))


    def __del__(self):
        if not self.dbclosed:
            self.closeDB()

    def closeDB(self):
        """
        Close repository storage communication.
        Note: once issues this, you won't be able to use such instance
        anymore.
        """
        self.dbclosed = True

        try:

            if not self.readOnly:
                self.commitChanges()

            plugins = self.get_plugins()
            for plugin_id in sorted(plugins):
                plug_inst = plugins[plugin_id]
                exec_rc = plug_inst.close_repo_hook(self)
                if exec_rc:
                    raise RepositoryPluginError(
                        "[close_repo_hook] %s: status: %s" % (
                            plug_inst.get_id(), exec_rc,))

        finally:
            self.cursor.close()
            self.connection.close()

    def vacuum(self):
        """
        Repository storage cleanup and optimization function.
        """
        self.cursor.execute("vacuum")

    def commitChanges(self, force = False, no_plugins = False):
        """
        Commit actual changes and make them permanently stored.

        @keyword force: force commit, despite read-only bit being set
        @type force: bool
        """

        if force or (not self.readOnly):
            try:
                self.connection.commit()
            except self.dbapi2.Error:
                pass

        if no_plugins:
            return

        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.commit_hook(self)
            if exec_rc:
                raise RepositoryPluginError("[commit_hook] %s: status: %s" % (
                    plug_inst.get_id(), exec_rc,))

    def initializeDatabase(self):
        """
        WARNING: it will erase your database.
        This method (re)initializes the repository, dropping all its content.
        """
        my = self.Schema()
        for table in self.listAllTables():
            try:
                self.cursor.execute("DROP TABLE %s" % (table,))
            except self.dbapi2.OperationalError:
                # skip tables that can't be dropped
                continue
        self.cursor.executescript(my.get_init())
        self._databaseStructureUpdates()
        # set cache size
        self.setCacheSize(8192)
        self.setDefaultCacheSize(8192)
        self._setupInitialSettings()

        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.initialize_repo_hook(self)
            if exec_rc:
                raise RepositoryPluginError(
                    "[initialize_repo_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

        self.commitChanges()

    def filterTreeUpdatesActions(self, actions):
        """
        This method should be considered internal and not suited for general
        audience. Given a raw package name/slot updates list, it returns
        the action that should be really taken because not applied.

        @param actions: list of raw treeupdates actions, for example:
            ['move x11-foo/bar app-foo/bar', 'slotmove x11-foo/bar 2 3']
        @type actions: list
        @return: list of raw treeupdates actions that should be really
            worked out
        @rtype: list
        """
        new_actions = []
        for action in actions:

            if action in new_actions: # skip dupies
                continue

            doaction = action.split()
            if doaction[0] == "slotmove":

                # slot move
                atom = doaction[1]
                from_slot = doaction[2]
                to_slot = doaction[3]
                atom_key = self.entropyTools.dep_getkey(atom)
                category = atom_key.split("/")[0]
                matches, sm_rc = self.atomMatch(atom, matchSlot = from_slot,
                    multiMatch = True)
                if sm_rc == 1:
                    # nothing found in repo that matches atom
                    # this means that no packages can effectively
                    # reference to it
                    continue
                found = False
                # found atoms, check category
                for idpackage in matches:
                    myslot = self.retrieveSlot(idpackage)
                    mycategory = self.retrieveCategory(idpackage)
                    if mycategory == category:
                        if  (myslot != to_slot) and \
                        (action not in new_actions):
                            new_actions.append(action)
                            found = True
                            break
                if found:
                    continue
                # if we get here it means found == False
                # search into dependencies
                dep_atoms = self.searchDependency(atom_key, like = True,
                    multi = True, strings = True)
                dep_atoms = [x for x in dep_atoms if x.endswith(":"+from_slot) \
                    and self.entropyTools.dep_getkey(x) == atom_key]
                if dep_atoms:
                    new_actions.append(action)

            elif doaction[0] == "move":

                atom = doaction[1] # usually a key
                atom_key = self.entropyTools.dep_getkey(atom)
                category = atom_key.split("/")[0]
                matches, m_rc = self.atomMatch(atom, multiMatch = True)
                if m_rc == 1:
                    # nothing found in repo that matches atom
                    # this means that no packages can effectively
                    # reference to it
                    continue
                found = False
                for idpackage in matches:
                    mycategory = self.retrieveCategory(idpackage)
                    if (mycategory == category) and (action \
                        not in new_actions):
                        new_actions.append(action)
                        found = True
                        break
                if found:
                    continue
                # if we get here it means found == False
                # search into dependencies
                dep_atoms = self.searchDependency(atom_key, like = True,
                    multi = True, strings = True)
                dep_atoms = [x for x in dep_atoms if \
                    self.entropyTools.dep_getkey(x) == atom_key]
                if dep_atoms:
                    new_actions.append(action)

        return new_actions

    def runTreeUpdatesActions(self, actions):
        # this is the place to add extra actions support
        """
        Method not suited for general purpose usage.
        Executes package name/slot update actions passed.

        @param actions: list of raw treeupdates actions, for example:
            ['move x11-foo/bar app-foo/bar', 'slotmove x11-foo/bar 2 3']
        @type actions: list

        @return: list (set) of packages that should be repackaged
        @rtype: set
        """
        mytxt = "%s: %s, %s." % (
            bold(_("SPM")),
            blue(_("Running fixpackages")),
            red(_("it could take a while")),
        )
        self.updateProgress(
            mytxt,
            importance = 1,
            type = "warning",
            header = darkred(" * ")
        )
        try:
            spm = get_spm(self)
            spm.packages_repositories_metadata_update()
        except:
            self.entropyTools.print_traceback()

        spm_moves = set()
        quickpkg_atoms = set()
        for action in actions:
            command = action.split()
            mytxt = "%s: %s: %s." % (
                bold(_("ENTROPY")),
                red(_("action")),
                blue(action),
            )
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "warning",
                header = darkred(" * ")
            )
            if command[0] == "move":
                spm_moves.add(action)
                quickpkg_atoms |= self.runTreeUpdatesMoveAction(command[1:],
                    quickpkg_atoms)
            elif command[0] == "slotmove":
                quickpkg_atoms |= self.runTreeUpdatesSlotmoveAction(command[1:],
                    quickpkg_atoms)

            mytxt = "%s: %s." % (
                bold(_("ENTROPY")),
                blue(_("package move actions complete")),
            )
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "info",
                header = purple(" @@ ")
            )

        if spm_moves:
            try:
                self.doTreeupdatesSpmCleanup(spm_moves)
            except Exception as e:
                mytxt = "%s: %s: %s, %s." % (
                    bold(_("WARNING")),
                    red(_("Cannot run SPM cleanup, error")),
                    Exception,
                    e,
                )
                self.entropyTools.print_traceback()

        mytxt = "%s: %s." % (
            bold(_("ENTROPY")),
            blue(_("package moves completed successfully")),
        )
        self.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = brown(" @@ ")
        )

        # discard cache
        self.clearCache()

        return quickpkg_atoms


    def runTreeUpdatesMoveAction(self, move_command, quickpkg_queue):
        # -- move action:
        # 1) move package key to the new name: category + name + atom
        # 2) update all the dependencies in dependenciesreference to the new key
        # 3) run fixpackages which will update /var/db/pkg files
        # 4) automatically run quickpkg() to build the new binary and
        #    tainted binaries owning tainted iddependency and taint database
        """
        Method not suited for general purpose usage.
        Executes package name move action passed.

        @param move_command: raw treeupdates move action, for example:
            'move x11-foo/bar app-foo/bar'
        @type move_command: string
        @param quickpkg_queue: current package regeneration queue
        @type quickpkg_queue: list
        @return: updated package regeneration queue
        @rtype: list
        """
        dep_from = move_command[0]
        key_from = self.entropyTools.dep_getkey(dep_from)
        key_to = move_command[1]
        cat_to = key_to.split("/")[0]
        name_to = key_to.split("/")[1]
        matches = self.atomMatch(dep_from, multiMatch = True)
        iddependencies = set()

        for idpackage in matches[0]:

            slot = self.retrieveSlot(idpackage)
            old_atom = self.retrieveAtom(idpackage)
            new_atom = old_atom.replace(key_from, key_to)

            ### UPDATE DATABASE
            # update category
            self.setCategory(idpackage, cat_to)
            # update name
            self.setName(idpackage, name_to)
            # update atom
            self.setAtom(idpackage, new_atom)

            # look for packages we need to quickpkg again
            quickpkg_queue.add(key_to+":"+slot)

            plugins = self.get_plugins()
            for plugin_id in sorted(plugins):
                plug_inst = plugins[plugin_id]
                exec_rc = plug_inst.treeupdates_move_action_hook(self,
                    idpackage)
                if exec_rc:
                    raise RepositoryPluginError(
                        "[treeupdates_move_action_hook] %s: status: %s" % (
                            plug_inst.get_id(), exec_rc,))

        iddeps = self.searchDependency(key_from, like = True, multi = True)
        for iddep in iddeps:
            # update string
            mydep = self.getDependency(iddep)
            mydep_key = self.entropyTools.dep_getkey(mydep)
            # avoid changing wrong atoms -> dev-python/qscintilla-python would
            # become x11-libs/qscintilla if we don't do this check
            if mydep_key != key_from:
                continue
            mydep = mydep.replace(key_from, key_to)
            # now update
            # dependstable on server is always re-generated
            self.setDependency(iddep, mydep)
            # we have to repackage also package owning this iddep
            iddependencies |= self.searchIdpackageFromIddependency(iddep)

        self.commitChanges()
        quickpkg_queue = list(quickpkg_queue)
        for x in range(len(quickpkg_queue)):
            myatom = quickpkg_queue[x]
            myatom = myatom.replace(key_from, key_to)
            quickpkg_queue[x] = myatom
        quickpkg_queue = set(quickpkg_queue)
        for idpackage_owner in iddependencies:
            myatom = self.retrieveAtom(idpackage_owner)
            myatom = myatom.replace(key_from, key_to)
            quickpkg_queue.add(myatom)
        return quickpkg_queue


    def runTreeUpdatesSlotmoveAction(self, slotmove_command, quickpkg_queue):
        # -- slotmove action:
        # 1) move package slot
        # 2) update all the dependencies in dependenciesreference owning
        #    same matched atom + slot
        # 3) run fixpackages which will update /var/db/pkg files
        # 4) automatically run quickpkg() to build the new
        #    binary and tainted binaries owning tainted iddependency
        #    and taint database
        """
        Method not suited for general purpose usage.
        Executes package slot move action passed.

        @param slotmove_command: raw treeupdates slot move action, for example:
            'slotmove x11-foo/bar 2 3'
        @type slotmove_command: string
        @param quickpkg_queue: current package regeneration queue
        @type quickpkg_queue: list
        @return: updated package regeneration queue
        @rtype: list
        """
        atom = slotmove_command[0]
        atomkey = self.entropyTools.dep_getkey(atom)
        slot_from = slotmove_command[1]
        slot_to = slotmove_command[2]
        matches = self.atomMatch(atom, multiMatch = True)
        iddependencies = set()

        matched_idpackages = matches[0]
        for idpackage in matched_idpackages:

            ### UPDATE DATABASE
            # update slot
            self.setSlot(idpackage, slot_to)

            # look for packages we need to quickpkg again
            # note: quickpkg_queue is simply ignored if client_repo == True
            quickpkg_queue.add(atom+":"+slot_to)

            # only if we've found VALID matches !
            iddeps = self.searchDependency(atomkey, like = True, multi = True)
            for iddep in iddeps:
                # update string
                mydep = self.getDependency(iddep)
                mydep_key = self.entropyTools.dep_getkey(mydep)
                if mydep_key != atomkey:
                    continue
                if not mydep.endswith(":"+slot_from): # probably slotted dep
                    continue
                mydep_match = self.atomMatch(mydep)
                if mydep_match not in matched_idpackages:
                    continue
                mydep = mydep.replace(":"+slot_from, ":"+slot_to)
                # now update
                # dependstable on server is always re-generated
                self.setDependency(iddep, mydep)
                # we have to repackage also package owning this iddep
                iddependencies |= self.searchIdpackageFromIddependency(iddep)

            plugins = self.get_plugins()
            for plugin_id in sorted(plugins):
                plug_inst = plugins[plugin_id]
                exec_rc = plug_inst.treeupdates_slot_move_action_hook(self,
                    idpackage)
                if exec_rc:
                    raise RepositoryPluginError(
                        "[treeupdates_slot_move_action_hook] %s: status: %s" % (
                            plug_inst.get_id(), exec_rc,))

        self.commitChanges()
        for idpackage_owner in iddependencies:
            myatom = self.retrieveAtom(idpackage_owner)
            quickpkg_queue.add(myatom)
        return quickpkg_queue

    def doTreeupdatesSpmCleanup(self, spm_moves):
        """
        Erase dead Source Package Manager db entries.

        @todo: make more Portage independent (create proper entropy.spm
            methods for dealing with this)
        @param spm_moves: list of raw package name/slot update actions.
        @type spm_moves: list
        """
        # now erase Spm entries if necessary
        for action in spm_moves:
            command = action.split()
            if len(command) < 2:
                continue

            key = command[1]
            category, name = key.split("/", 1)
            dep_key = self.entropyTools.dep_getkey(key)

            try:
                spm = get_spm(self)
            except:
                self.entropyTools.print_traceback()
                continue

            script_path = spm.get_installed_package_build_script_path(dep_key)
            pkg_path = os.path.dirname(os.path.dirname(script_path))
            if not os.path.isdir(pkg_path):
                # no dir,  no party!
                continue

            mydirs = [os.path.join(pkg_path, x) for x in \
                os.listdir(pkg_path) if \
                self.entropyTools.dep_getkey(os.path.join(category, x)) \
                    == dep_key]
            mydirs = [x for x in mydirs if os.path.isdir(x)]

            # now move these dirs
            for mydir in mydirs:
                to_path = os.path.join(etpConst['packagestmpdir'],
                    os.path.basename(mydir))
                mytxt = "%s: %s '%s' %s '%s'" % (
                    bold(_("SPM")),
                    red(_("Moving old entry")),
                    blue(mydir),
                    red(_("to")),
                    blue(to_path),
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning",
                    header = darkred(" * ")
                )
                if os.path.isdir(to_path):
                    shutil.rmtree(to_path, True)
                    try:
                        os.rmdir(to_path)
                    except OSError:
                        pass
                shutil.move(mydir, to_path)


    def handlePackage(self, pkg_data, forcedRevision = -1,
        formattedContent = False):
        """
        Update or add a package to repository automatically handling
        its scope and thus removal of previous versions if requested by
        the given metadata.
        pkg_data is a dict() containing all the information bound to
        a package:

            {
                'signatures':
                    {
                        'sha256': 'zzz',
                        'sha1': 'zzz',
                        'sha512': 'zzz'
                 },
                'slot': '0',
                'datecreation': '1247681752.93',
                'description': 'Standard (de)compression library',
                'useflags': set(['kernel_linux']),
                'eclasses': set(['multilib']),
                'config_protect_mask': 'string string', 'etpapi': 3,
                'mirrorlinks': [],
                'cxxflags': '-Os -march=x86-64 -pipe',
                'injected': False,
                'licensedata': {'ZLIB': u"lictext"},
                'dependencies': {},
                'chost': 'x86_64-pc-linux-gn',
                'config_protect': 'string string',
                'download': 'packages/amd64/4/sys-libs:zlib-1.2.3-r1.tbz2',
                'conflicts': set([]),
                'digest': 'fd54248ae060c287b1ec939de3e55332',
                'size': '136302',
                'category': 'sys-libs',
                'license': 'ZLIB',
                'sources': set(),
                'name': 'zlib',
                'versiontag': '',
                'changelog': u"text",
                'provide': set([]),
                'trigger': 'text',
                'counter': 22331,
                'messages': [],
                'branch': '4',
                'content': {},
                'needed': [('libc.so.6', 2)],
                'version': '1.2.3-r1',
                'keywords': set(),
                'cflags': '-Os -march=x86-64 -pipe',
                'disksize': 932206, 'spm_phases': None,
                'homepage': 'http://www.zlib.net/',
                'systempackage': True,
                'revision': 0
            }

        @param pkg_data: Entropy package metadata dict
        @type pkg_data: dict
        @keyword forcedRevision: force a specific package revision
        @type forcedRevision: int
        @keyword formattedContent: tells whether content metadata is already
            formatted for insertion
        @type formattedContent: bool
        @return: tuple composed by
            - idpackage: unique Entropy Repository package identifier
            - revision: final package revision selected
            - pkg_data: new Entropy package metadata dict
        @rtype: tuple
        """

        def remove_conflicting_packages(pkgdata):

            manual_deps = set()
            removelist = self.retrieve_packages_to_remove(
                pkgdata['name'], pkgdata['category'],
                pkgdata['slot'], pkgdata['injected']
            )

            for r_idpackage in removelist:
                manual_deps |= self.retrieveManualDependencies(r_idpackage)
                self.removePackage(r_idpackage, do_cleanup = False,
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
        pkgatom = self.entropyTools.create_package_atom_string(
            pkg_data['category'], pkg_data['name'], pkg_data['version'],
            pkg_data['versiontag'])

        foundid = self.isAtomAvailable(pkgatom)
        if foundid < 0: # same atom doesn't exist in any branch
            remove_conflicting_packages(pkg_data)
            return self.addPackage(pkg_data, revision = forcedRevision,
                formatted_content = formattedContent)

        idpackages = self.getIDPackages(pkgatom)
        current_rev = forcedRevision

        for idpackage in idpackages:

            if forcedRevision == -1:
                myrev = self.retrieveRevision(idpackage)
                if myrev > current_rev:
                    current_rev = myrev

            # injected packages wouldn't be removed by addPackage
            self.removePackage(idpackage, do_cleanup = False, do_commit = False)

        if forcedRevision == -1:
            current_rev += 1

        # add the new one
        remove_conflicting_packages(pkg_data)
        return self.addPackage(pkg_data, revision = current_rev,
            formatted_content = formattedContent)

    def retrieve_packages_to_remove(self, name, category, slot, injected):
        """
        Return a list of packages that would be removed given name, category,
        slot and injection status.

        @param name: package name
        @type name: string
        @param category: package category
        @type category: string
        @param slot: package slot
        @type slot: string
        @param injected: injection status (packages marked as injected are
            always considered not automatically removable)
        @type injected: bool

        @return: list (set) of removable packages (idpackages)
        @rtype: set
        """

        removelist = set()
        if injected:
            # read: if package has been injected, we'll skip
            # the removal of packages in the same slot,
            # usually used server side btw
            return removelist

        searchsimilar = self.searchPackagesByNameAndCategory(
            name = name,
            category = category,
            sensitive = True
        )

        # FIXME: This is marginally, Entropy server-side stuff but also
        # part of the currently implemented metaphor (that will be moved
        # to separate class and used through future Rule Engine).

        # support for expiration-based packages handling, also internally
        # called Fat Scope.
        filter_similar = False
        srv_ss_plg = etpConst['system_settings_plugins_ids']['server_plugin']
        srv_ss_fs_plg = \
            etpConst['system_settings_plugins_ids']['server_plugin_fatscope']

        srv_plug_settings = self.SystemSettings.get(srv_ss_plg)
        if srv_plug_settings is not None:
            if srv_plug_settings['server']['exp_based_scope']:
                # in case support is enabled, return an empty set
                filter_similar = True

        if filter_similar:
            # filter out packages in the same scope that are allowed to stay
            idpkgs = self.SystemSettings[srv_ss_fs_plg]['repos'].get(
                self.dbname)
            if idpkgs:
                if -1 in idpkgs:
                    del searchsimilar[:]
                else:
                    searchsimilar = [x for x in searchsimilar if x[1] \
                        not in idpkgs]

        # :-)
        # end of FIXME
        # :-)

        for atom, idpackage in searchsimilar:
            # get the package slot
            myslot = self.retrieveSlot(idpackage)
            # we merely ignore packages with
            # negative counters, since they're the injected ones
            if self.isInjected(idpackage):
                continue
            if slot == myslot:
                # remove!
                removelist.add(idpackage)

        return removelist

    def addPackage(self, pkg_data, revision = -1, idpackage = None,
        do_commit = True, formatted_content = False):
        """
        Add package to this Entropy repository. The main difference between
        handlePackage and this is that from here, no packages are going to be
        removed, in any case.
        For more information about pkg_data layout, please see
        I{handlePackage()}.

        @param pkg_data: Entropy package metadata
        @type pkg_data: dict
        @keyword revision: force a specific Entropy package revision
        @type revision: int
        @keyword idpackage: add package to Entropy repository using the
            provided package identifier, this is very dangerous and could
            cause packages with the same identifier to be removed.
        @type idpackage: int
        @keyword do_commit: if True, automatically commits the executed
            transaction (could cause slowness)
        @type do_commit: bool
        @keyword formatted_content: if True, determines whether the content
            metadata (usually the biggest part) in pkg_data is already
            prepared for insertion
        @type formatted_content: bool
        @return: tuple composed by
            - idpackage: unique Entropy Repository package identifier
            - revision: final package revision selected
            - pkg_data: new Entropy package metadata dict
        @rtype: tuple
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
        catid = self.isCategoryAvailable(pkg_data['category'])
        if catid == -1:
            catid = self.addCategory(pkg_data['category'])

        # create new license if it doesn't exist
        licid = self.isLicenseAvailable(pkg_data['license'])
        if licid == -1:
            licid = self.addLicense(pkg_data['license'])

        idprotect = self.isProtectAvailable(pkg_data['config_protect'])
        if idprotect == -1:
            idprotect = self.addProtect(pkg_data['config_protect'])

        idprotect_mask = self.isProtectAvailable(
            pkg_data['config_protect_mask'])
        if idprotect_mask == -1:
            idprotect_mask = self.addProtect(pkg_data['config_protect_mask'])

        idflags = self.areCompileFlagsAvailable(pkg_data['chost'],
            pkg_data['cflags'], pkg_data['cxxflags'])
        if idflags == -1:
            idflags = self.addCompileFlags(pkg_data['chost'],
                pkg_data['cflags'], pkg_data['cxxflags'])

        trigger = 0
        if pkg_data['trigger']:
            trigger = 1

        # baseinfo
        pkgatom = self.entropyTools.create_package_atom_string(
            pkg_data['category'], pkg_data['name'], pkg_data['version'],
            pkg_data['versiontag'])
        # add atom metadatum
        pkg_data['atom'] = pkgatom

        mybaseinfo_data = (pkgatom, catid, pkg_data['name'],
            pkg_data['version'], pkg_data['versiontag'], revision,
            pkg_data['branch'], pkg_data['slot'],
            licid, pkg_data['etpapi'], trigger,
        )

        myidpackage_string = 'NULL'
        if isinstance(idpackage, int):

            manual_deps = self.retrieveManualDependencies(idpackage)

            # does it exist?
            self.removePackage(idpackage, do_cleanup = False,
                do_commit = False, from_add_package = True)
            myidpackage_string = '?'
            mybaseinfo_data = (idpackage,)+mybaseinfo_data

            # merge old manual dependencies
            dep_dict = pkg_data['dependencies']
            for manual_dep in manual_deps:
                if manual_dep in dep_dict:
                    continue
                dep_dict[manual_dep] = \
                    etpConst['dependency_type_ids']['mdepend_id']

        else:
            # force to None
            idpackage = None


        with self.__write_mutex:

            cur = self.cursor.execute("""
            INSERT INTO baseinfo VALUES (%s,?,?,?,?,?,?,?,?,?,?,?)""" % (
                myidpackage_string,), mybaseinfo_data)
            if idpackage is None:
                idpackage = cur.lastrowid

            # extrainfo
            self.cursor.execute(
                'INSERT INTO extrainfo VALUES (?,?,?,?,?,?,?,?)',
                (   idpackage,
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
            self.insertEclasses(idpackage, pkg_data['eclasses'])
            self.insertNeeded(idpackage, pkg_data['needed'])
            self.insertDependencies(idpackage, pkg_data['dependencies'])
            self.insertSources(idpackage, pkg_data['sources'])
            self.insertUseflags(idpackage, pkg_data['useflags'])
            self.insertKeywords(idpackage, pkg_data['keywords'])
            self.insertLicenses(pkg_data['licensedata'])
            self.insertMirrors(pkg_data['mirrorlinks'])
            # package ChangeLog
            if pkg_data.get('changelog'):
                self.insertChangelog(pkg_data['category'], pkg_data['name'],
                    pkg_data['changelog'])
            # package signatures
            if pkg_data.get('signatures'):
                signatures = pkg_data['signatures']
                sha1, sha256, sha512 = signatures['sha1'], \
                    signatures['sha256'], signatures['sha512']
                self.insertSignatures(idpackage, sha1, sha256, sha512)

            if pkg_data.get('provided_libs'):
                self._insertProvidedLibraries(idpackage, pkg_data['provided_libs'])

            # spm phases
            if pkg_data.get('spm_phases') is not None:
                self._insertSpmPhases(idpackage, pkg_data['spm_phases'])

            if pkg_data.get('spm_repository') is not None:
                self._insertSpmRepository(idpackage, pkg_data['spm_repository'])

            # not depending on other tables == no select done
            self.insertContent(idpackage, pkg_data['content'],
                already_formatted = formatted_content)

            # handle SPM UID<->idpackage binding
            pkg_data['counter'] = int(pkg_data['counter'])
            if not pkg_data['injected'] and (pkg_data['counter'] != -1):
                pkg_data['counter'] = self.bindSpmPackageUid(
                    idpackage, pkg_data['counter'], pkg_data['branch'])

            self.insertOnDiskSize(idpackage, pkg_data['disksize'])
            if pkg_data['trigger']:
                self.insertTrigger(idpackage, pkg_data['trigger'])
            self.insertConflicts(idpackage, pkg_data['conflicts'])

            if "provide_extended" not in pkg_data:
                self.insertProvide(idpackage, pkg_data['provide'])
            else:
                self.insertProvide(idpackage, pkg_data['provide_extended'])

            self.insertMessages(idpackage, pkg_data['messages'])
            self.insertConfigProtect(idpackage, idprotect)
            self.insertConfigProtect(idpackage, idprotect_mask, mask = True)
            # injected?
            if pkg_data.get('injected'):
                self.setInjected(idpackage, do_commit = False)
            # is it a system package?
            if pkg_data.get('systempackage'):
                self.setSystemPackage(idpackage, do_commit = False)

            self.clearCache() # we do live_cache.clear() here too
            if do_commit:
                self.commitChanges()

        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.add_package_hook(self, idpackage, pkg_data)
            if exec_rc:
                raise RepositoryPluginError(
                    "[add_package_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

        return idpackage, revision, pkg_data

    def removePackage(self, idpackage, do_cleanup = True, do_commit = True,
        from_add_package = False):
        """
        Remove package from this Entropy repository using it's identifier
        (idpackage).

        @param idpackage: Entropy repository package indentifier
        @type idpackage: int
        @keyword do_cleanup: if True, executes repository metadata cleanup
            at the end
        @type do_cleanup: bool
        @keyword do_commit: if True, commits the transaction (could cause
            slowness)
        @type do_commit: bool
        @keyword from_add_package: inform function that it's being called from
            inside addPackage().
        @type from_add_package: bool
        """
        # clear caches
        self.clearCache()

        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.remove_package_hook(self, idpackage,
                from_add_package)
            if exec_rc:
                raise RepositoryPluginError(
                    "[remove_package_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

        with self.__write_mutex:

            try:
                new_way = self.getSetting("on_delete_cascade")
            except KeyError:
                new_way = ''
            # TODO: deprecate this someday
            if new_way:
                # this will work thanks to ON DELETE CASCADE !
                self.cursor.execute(
                    "DELETE FROM baseinfo WHERE idpackage = (?)", (idpackage,))
            else:
                r_tup = (idpackage,)*20
                self.cursor.executescript("""
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
                    DELETE FROM messages WHERE idpackage = %d;
                    DELETE FROM counters WHERE idpackage = %d;
                    DELETE FROM sizes WHERE idpackage = %d;
                    DELETE FROM eclasses WHERE idpackage = %d;
                    DELETE FROM needed WHERE idpackage = %d;
                    DELETE FROM triggers WHERE idpackage = %d;
                    DELETE FROM systempackages WHERE idpackage = %d;
                    DELETE FROM injected WHERE idpackage = %d;
                    DELETE FROM installedtable WHERE idpackage = %d;
                """ % r_tup)

        if do_cleanup:
            # Cleanups if at least one package has been removed
            self.doCleanups()

        if do_commit:
            self.commitChanges()

    def removeMirrorEntries(self, mirrorname):
        """
        Remove source packages mirror entries from database for the given
        mirror name. This is a representation of Portage's "thirdpartymirrors".

        @param mirrorname: mirror name
        @type mirrorname: string
        """     
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM mirrorlinks WHERE mirrorname = (?)
            """, (mirrorname,))

    def addMirrors(self, mirrorname, mirrorlist):
        """
        Add source package mirror entry to database.
        This is a representation of Portage's "thirdpartymirrors".

        @param mirrorname: name of the mirror from which "mirrorlist" belongs
        @type mirrorname: string
        @param mirrorlist: list of URLs belonging to the given mirror name
        @type mirrorlist: list
        """
        with self.__write_mutex:
            self.cursor.executemany("""
            INSERT into mirrorlinks VALUES (?,?)
            """, [(mirrorname, x,) for x in mirrorlist])

    def addCategory(self, category):
        """
        Add package category string to repository. Return its identifier
        (idcategory).

        @param category: name of the category to add
        @type category: string
        @return: category identifier (idcategory)
        @rtype: int
        """
        with self.__write_mutex:
            cur = self.cursor.execute("""
            INSERT into categories VALUES (NULL,?)
            """, (category,))
            return cur.lastrowid

    def addProtect(self, protect):
        """
        Add a single, generic CONFIG_PROTECT (not defined as _MASK/whatever
        here) path. Return its identifier (idprotect).

        @param protect: CONFIG_PROTECT path to add
        @type protect: string
        @return: protect identifier (idprotect)
        @rtype: int
        """
        with self.__write_mutex:
            cur = self.cursor.execute("""
            INSERT into configprotectreference VALUES (NULL,?)
            """, (protect,))
            return cur.lastrowid

    def addSource(self, source):
        """
        Add source code package download path to repository. Return its
        identifier (idsource).

        @param source: source package download path
        @type source: string
        @return: source identifier (idprotect)
        @rtype: int
        """
        with self.__write_mutex:
            cur = self.cursor.execute("""
            INSERT into sourcesreference VALUES (NULL,?)
            """, (source,))
            return cur.lastrowid

    def addDependency(self, dependency):
        """
        Add dependency string to repository. Return its identifier
        (iddependency).

        @param dependency: dependency string
        @type dependency: string
        @return: dependency identifier (iddependency)
        @rtype: int
        """
        with self.__write_mutex:
            cur = self.cursor.execute("""
            INSERT into dependenciesreference VALUES (NULL,?)
            """, (dependency,))
            return cur.lastrowid

    def addKeyword(self, keyword):
        """
        Add package SPM keyword string to repository.
        Return its identifier (idkeyword).

        @param keyword: keyword string
        @type keyword: string
        @return: keyword identifier (idkeyword)
        @rtype: int
        """
        with self.__write_mutex:
            cur = self.cursor.execute("""
            INSERT into keywordsreference VALUES (NULL,?)
            """, (keyword,))
            return cur.lastrowid

    def addUseflag(self, useflag):
        """
        Add package USE flag string to repository.
        Return its identifier (iduseflag).

        @param useflag: useflag string
        @type useflag: string
        @return: useflag identifier (iduseflag)
        @rtype: int
        """
        with self.__write_mutex:
            cur = self.cursor.execute("""
            INSERT into useflagsreference VALUES (NULL,?)
            """, (useflag,))
            return cur.lastrowid

    def addEclass(self, eclass):
        """
        Add package SPM Eclass string to repository.
        Return its identifier (ideclass).

        @param eclass: eclass string
        @type eclass: string
        @return: eclass identifier (ideclass)
        @rtype: int
        """
        with self.__write_mutex:
            cur = self.cursor.execute("""
            INSERT into eclassesreference VALUES (NULL,?)
            """, (eclass,))
            return cur.lastrowid

    def addNeeded(self, needed):
        """
        Add package libraries' ELF object NEEDED string to repository.
        Return its identifier (idneeded).

        @param needed: NEEDED string (as shown in `readelf -d elf.so`) 
        @type needed: string
        @return: needed identifier (idneeded)
        @rtype: int
        """
        with self.__write_mutex:
            cur = self.cursor.execute("""
            INSERT into neededreference VALUES (NULL,?)
            """, (needed,))
            return cur.lastrowid

    def addLicense(self, pkglicense):
        """
        Add package license name string to repository.
        Return its identifier (idlicense).

        @param pkglicense: license name string
        @type pkglicense: string
        @return: license name identifier (idlicense)
        @rtype: int
        """
        if not self.entropyTools.is_valid_string(pkglicense):
            pkglicense = ' ' # workaround for broken license entries
        with self.__write_mutex:
            cur = self.cursor.execute("""
            INSERT into licenses VALUES (NULL,?)
            """, (pkglicense,))
            return cur.lastrowid

    def addCompileFlags(self, chost, cflags, cxxflags):
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
        with self.__write_mutex:
            cur = self.cursor.execute("""
            INSERT into flags VALUES (NULL,?,?,?)
            """, (chost, cflags, cxxflags,))
            return cur.lastrowid

    def setSystemPackage(self, idpackage, do_commit = True):
        """
        Mark a package as system package, which means that entropy.client
        will deny its removal.

        @param idpackage: package identifier
        @type idpackage: int
        @keyword do_commit: determine whether executing commit or not
        @type do_commit: bool
        """
        with self.__write_mutex:
            self.cursor.execute("""
            INSERT into systempackages VALUES (?)
            """, (idpackage,))
            if do_commit:
                self.commitChanges()

    def setInjected(self, idpackage, do_commit = True):
        """
        Mark package as injected, injection is usually set for packages
        manually added to repository. Injected packages are not removed
        automatically even when featuring conflicting scope with other
        that are being added. If a package is injected, it means that
        maintainers have to handle it manually.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword do_commit: determine whether executing commit or not
        @type do_commit: bool
        """
        with self.__write_mutex:
            if not self.isInjected(idpackage):
                self.cursor.execute("""
                INSERT into injected VALUES (?)
                """, (idpackage,))
            if do_commit:
                self.commitChanges()

    def setCreationDate(self, idpackage, date):
        """
        Update the creation date for package. Creation date is stored in
        string based unix time format.

        @param idpackage: package indentifier
        @type idpackage: int
        @param date: unix time in string form
        @type date: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE extrainfo SET datecreation = (?) WHERE idpackage = (?)
            """, (str(date), idpackage,))
            self.commitChanges()

    def setDigest(self, idpackage, digest):
        """
        Set package file md5sum for package. This information is used
        by entropy.client when downloading packages.

        @param idpackage: package indentifier
        @type idpackage: int
        @param digest: md5 hash for package file
        @type digest: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE extrainfo SET digest = (?) WHERE idpackage = (?)
            """, (digest, idpackage,))
            self.commitChanges()

    def setSignatures(self, idpackage, sha1, sha256, sha512):
        """
        Set package file extra hashes (sha1, sha256, sha512) for package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param sha1: SHA1 hash for package file
        @type sha1: string
        @param sha256: SHA256 hash for package file
        @type sha256: string
        @param sha512: SHA512 hash for package file
        @type sha512: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE packagesignatures SET sha1 = (?), sha256 = (?), sha512 = (?)
            WHERE idpackage = (?)
            """, (sha1, sha256, sha512, idpackage))

    def setDownloadURL(self, idpackage, url):
        """
        Set download URL prefix for package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param url: URL prefix to set
        @type url: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE extrainfo SET download = (?) WHERE idpackage = (?)
            """, (url, idpackage,))
            self.commitChanges()

    def setCategory(self, idpackage, category):
        """
        Set category name for package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param category: category to set
        @type category: string
        """
        # create new category if it doesn't exist
        catid = self.isCategoryAvailable(category)
        if catid == -1:
            # create category
            catid = self.addCategory(category)

        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE baseinfo SET idcategory = (?) WHERE idpackage = (?)
            """, (catid, idpackage,))
            self.commitChanges()

    def setCategoryDescription(self, category, description_data):
        """
        Set description for given category name.

        @param category: category name
        @type category: string
        @param description_data: category description for several locales.
            {'en': "This is blah", 'it': "Questo e' blah", ... }
        @type description_data: dict
        """
        with self.__write_mutex:

            self.cursor.execute("""
            DELETE FROM categoriesdescription WHERE category = (?)
            """, (category,))
            for locale in description_data:
                mydesc = description_data[locale]
                self.cursor.execute("""
                INSERT INTO categoriesdescription VALUES (?,?,?)
                """, (category, locale, mydesc,))

            self.commitChanges()

    def setName(self, idpackage, name):
        """
        Set name for package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param name: package name
        @type name: string

        """
        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE baseinfo SET name = (?) WHERE idpackage = (?)
            """, (name, idpackage,))
            self.commitChanges()

    def setDependency(self, iddependency, dependency):
        """
        Set dependency string for iddependency (dependency identifier).

        @param iddependency: dependency string identifier
        @type iddependency: int
        @param dependency: dependency string
        @type dependency: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE dependenciesreference SET dependency = (?)
            WHERE iddependency = (?)
            """, (dependency, iddependency,))
            self.commitChanges()

    def setAtom(self, idpackage, atom):
        """
        Set atom string for package. "Atom" is the full, unique name of
        a package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param atom: atom string
        @type atom: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE baseinfo SET atom = (?) WHERE idpackage = (?)
            """, (atom, idpackage,))
            self.commitChanges()

    def setSlot(self, idpackage, slot):
        """
        Set slot string for package. Please refer to Portage SLOT documentation
        for more info.

        @param idpackage: package indentifier
        @type idpackage: int
        @param slot: slot string
        @type slot: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE baseinfo SET slot = (?) WHERE idpackage = (?)
            """, (slot, idpackage,))
            self.commitChanges()

    def setRevision(self, idpackage, revision):
        """
        Set Entropy revision for package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param revision: new revision
        @type revision: int
        """
        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE baseinfo SET revision = (?) WHERE idpackage = (?)
            """, (revision, idpackage,))
            self.commitChanges()

    def removeLicensedata(self, license_name):
        """
        Remove license text for given license name identifier.

        @param license_name: available license name identifier
        @type license_name: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM licensedata WHERE licensename = (?)
            """, (license_name,))

    def removeDependencies(self, idpackage):
        """
        Remove all the dependencies of package.

        @param idpackage: package indentifier
        @type idpackage: int
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM dependencies WHERE idpackage = (?)
            """, (idpackage,))
            self.commitChanges()

    def insertDependencies(self, idpackage, depdata):
        """
        Insert dependencies for package. "depdata" is a dict() with dependency
        strings as keys and dependency type as values.

        @param idpackage: package indentifier
        @type idpackage: int
        @param depdata: dependency dictionary
            {'app-foo/foo': dep_type_integer, ...}
        @type depdata: dict
        """

        dcache = set()
        add_dep = self.addDependency
        is_dep_avail = self.isDependencyAvailable
        def mymf(dep):

            if dep in dcache:
                return 0
            iddep = is_dep_avail(dep)
            if iddep == -1:
                iddep = add_dep(dep)

            deptype = 0
            if isinstance(depdata, dict):
                deptype = depdata[dep]

            dcache.add(dep)
            return (idpackage, iddep, deptype,)

        deps = [x for x in map(mymf, depdata) if not isinstance(x, int)]
        with self.__write_mutex:
            self.cursor.executemany("""
            INSERT into dependencies VALUES (?,?,?)
            """, deps)

    def insertManualDependencies(self, idpackage, manual_deps):
        """
        Insert manually added dependencies to dep. list of package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param manual_deps: list of dependency strings
        @type manual_deps: list
        """
        mydict = {}
        for manual_dep in manual_deps:
            mydict[manual_dep] = etpConst['dependency_type_ids']['mdepend_id']
        return self.insertDependencies(idpackage, mydict)

    def removeContent(self, idpackage):
        """
        Remove content metadata for package.

        @param idpackage: package indentifier
        @type idpackage: int
        """
        with self.__write_mutex:
            self.cursor.execute("DELETE FROM content WHERE idpackage = (?)", (idpackage,))
            self.commitChanges()

    def insertContent(self, idpackage, content, already_formatted = False):
        """
        Insert content metadata for package. "content" can either be a dict()
        or a list of triples (tuples of length 3, (idpackage, path, type,)).

        @param idpackage: package indentifier
        @type idpackage: int
        @param content: content metadata to insert.
            {'/path/to/foo': 'obj(content type)',}
            or
            [(idpackage, path, type,) ...]
        @type content: dict, list
        @keyword already_formatted: if True, "content" is expected to be
            already formatted for insertion, this means that "content" must be
            a list of tuples of length 3.
        @type already_formatted: bool
        """

        with self.__write_mutex:

            if already_formatted:
                self.cursor.executemany("""
                INSERT INTO content VALUES (?,?,?)
                """, [(idpackage, x, y,) for a, x, y in content])
            else:
                self.cursor.executemany("""
                INSERT INTO content VALUES (?,?,?)
                """, [(idpackage, x, content[x],) for x in content])

    def _insertProvidedLibraries(self, idpackage, libs_metadata):
        """
        Insert library metadata owned by package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param libs_metadata: provided library metadata composed by list of
            tuples of length 3 containing library name, path and ELF class.
        @type libs_metadata: list
        """
        # TODO: remove this in future
        if not self._doesTableExist('provided_libs'):
            self._createProvidedLibs()

        with self.__write_mutex:
            self.cursor.executemany("""
            INSERT INTO provided_libs VALUES (?,?,?,?)
            """, [(idpackage, x, y, z,) for x, y, z in libs_metadata])

    def insertAutomergefiles(self, idpackage, automerge_data):
        """
        Insert configuration files automerge information for package.
        "automerge_data" contains configuration files paths and their belonging
        md5 hash.
        This features allows entropy.client to "auto-merge" or "auto-remove"
        configuration files never touched by user.

        @param idpackage: package indentifier
        @type idpackage: int
        @param automerge_data: list of tuples of length 2.
            [('/path/to/conf/file', 'md5_checksum_string',) ... ]
        @type automerge_data: list
        """
        with self.__write_mutex:
            self.cursor.executemany('INSERT INTO automergefiles VALUES (?,?,?)',
                [(idpackage, x, y,) for x, y in automerge_data])

    def insertChangelog(self, category, name, changelog_txt):
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
        with self.__write_mutex:

            mytxt = changelog_txt.encode('raw_unicode_escape')

            self.cursor.execute("""
            DELETE FROM packagechangelogs WHERE category = (?) AND name = (?)
            """, (category, name,))

            self.cursor.execute("""
            INSERT INTO packagechangelogs VALUES (?,?,?)
            """, (category, name, const_get_buffer()(mytxt),))

    def insertLicenses(self, licenses_data):
        """
        insert license data (license names and text) into repository.

        @param licenses_data: dictionary containing license names as keys and
            text as values
        @type licenses_data: dict
        """

        mylicenses = list(licenses_data.keys())
        def my_mf(mylicense):
            return not self.isLicensedataKeyAvailable(mylicense)

        def my_mm(mylicense):

            lic_data = licenses_data.get(mylicense, '')

            # support both utf8 and str input
            if const_isunicode(lic_data): # encode to str
                try:
                    lic_data = lic_data.encode('raw_unicode_escape')
                except (UnicodeDecodeError,):
                    lic_data = lic_data.encode('utf-8')

            return (mylicense, const_get_buffer()(lic_data), 0,)

        with self.__write_mutex:
            # set() used after filter to remove duplicates
            self.cursor.executemany("""
            INSERT into licensedata VALUES (?,?,?)
            """, list(map(my_mm, set(filter(my_mf, mylicenses)))))

    def insertConfigProtect(self, idpackage, idprotect, mask = False):
        """
        Insert CONFIG_PROTECT (configuration files protection) entry identifier
        for package. This entry is usually a space separated string of directory
        and files which are used to handle user-protected configuration files
        or directories, those that are going to be stashed in separate paths
        waiting for user merge decisions.

        @param idpackage: package indentifier
        @type idpackage: int
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
        with self.__write_mutex:
            self.cursor.execute("""
            INSERT into %s VALUES (?,?)
            """ % (mytable,), (idpackage, idprotect,))

    def insertMirrors(self, mirrors):
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
            self.removeMirrorEntries(mirrorname)
            # add new
            self.addMirrors(mirrorname, mirrorlist)

    def insertKeywords(self, idpackage, keywords):
        """
        Insert keywords for package. Keywords are strings contained in package
        metadata stating what architectures or subarchitectures are supported
        by package. It is historically used also for masking packages (making
        them not available).

        @param idpackage: package indentifier
        @type idpackage: int
        @param keywords: list of keywords
        @type keywords: list
        """

        def mymf(key):
            idkeyword = self.isKeywordAvailable(key)
            if idkeyword == -1:
                # create category
                idkeyword = self.addKeyword(key)
            return (idpackage, idkeyword,)

        with self.__write_mutex:
            self.cursor.executemany("""
            INSERT into keywords VALUES (?,?)
            """, list(map(mymf, keywords)))

    def insertUseflags(self, idpackage, useflags):
        """
        Insert Source Package Manager USE (components build) flags for package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param useflags: list of use flags strings
        @type useflags: list
        """

        def mymf(flag):
            iduseflag = self.isUseflagAvailable(flag)
            if iduseflag == -1:
                # create category
                iduseflag = self.addUseflag(flag)
            return (idpackage, iduseflag,)

        with self.__write_mutex:
            self.cursor.executemany("""
            INSERT into useflags VALUES (?,?)
            """, list(map(mymf, useflags)))

    def insertSignatures(self, idpackage, sha1, sha256, sha512):
        """
        Insert package file extra hashes (sha1, sha256, sha512) for package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param sha1: SHA1 hash for package file
        @type sha1: string
        @param sha256: SHA256 hash for package file
        @type sha256: string
        @param sha512: SHA512 hash for package file
        @type sha512: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            INSERT INTO packagesignatures VALUES (?,?,?,?)
            """, (idpackage, sha1, sha256, sha512))

    def _insertSpmPhases(self, idpackage, phases):
        """
        Insert Source Package Manager phases for package.
        Entropy can call several Source Package Manager (the PM which Entropy
        relies on) package installation/removal phases.
        Such phase names are listed here.

        @param idpackage: package indentifier
        @type idpackage: int
        @param phases: list of available Source Package Manager phases
        @type phases: list
        """
        with self.__write_mutex:
            self.cursor.execute("""
            INSERT INTO packagespmphases VALUES (?,?)
            """, (idpackage, phases,))

    def _insertSpmRepository(self, idpackage, repository):
        """
        Insert Source Package Manager repository for package.
        This medatatum describes the source repository where package has
        been compiled from.

        @param idpackage: package indentifier
        @type idpackage: int
        @param repository: Source Package Manager repository
        @type repository: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            INSERT INTO packagespmrepository VALUES (?,?)
            """, (idpackage, repository,))

    def insertSources(self, idpackage, sources):
        """
        Insert source code package download URLs for idpackage.

        @param idpackage: package indentifier
        @type idpackage: int
        @param sources: list of source URLs
        @type sources: list
        """
        def mymf(source):

            if (not source) or \
            (not self.entropyTools.is_valid_string(source)):
                return 0

            idsource = self.isSourceAvailable(source)
            if idsource == -1:
                idsource = self.addSource(source)

            return (idpackage, idsource,)

        with self.__write_mutex:
            self.cursor.executemany("""
            INSERT into sources VALUES (?,?)
            """, [x for x in map(mymf, sources) if x != 0])

    def insertConflicts(self, idpackage, conflicts):
        """
        Insert dependency conflicts for package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param conflicts: list of dep. conflicts
        @type conflicts: list
        """
        with self.__write_mutex:
            self.cursor.executemany("""
            INSERT into conflicts VALUES (?,?)
            """, [(idpackage, x,) for x in conflicts])

    def insertMessages(self, idpackage, messages):
        """
        Insert user messages for package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param messages: list of messages
        @type messages: list
        """
        with self.__write_mutex:
            self.cursor.executemany("""
            INSERT into messages VALUES (?,?)
            """, [(idpackage, x,) for x in messages])

    def insertProvide(self, idpackage, provides):
        """
        Insert PROVIDE metadata for idpackage.
        This has been added for supporting Portage Source Package Manager
        old-style meta-packages support.
        Packages can provide extra atoms, you can see it like aliases, where
        these can be given by multiple packages. This allowed to make available
        multiple applications providing the same functionality which depending
        packages can reference, without forcefully being bound to a single
        package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param provides: list of atom strings
        @type provides: list
        """
        # FIXME: backward compat, remove someday
        # this adds default provide information to set data if not available
        my_provides = set()
        for prov in provides:
            if not isinstance(prov, tuple):
                my_provides.add((prov, False,))
            else:
                my_provides.add(prov)

        with self.__write_mutex:
            self.cursor.executemany("""
            INSERT into provide VALUES (?,?,?)
            """, [(idpackage, x, y,) for x, y in my_provides])

    def insertNeeded(self, idpackage, neededs):
        """
        Insert package libraries' ELF object NEEDED string for package.
        Return its identifier (idneeded).

        @param idpackage: package indentifier
        @type idpackage: int
        @param neededs: list of NEEDED string (as shown in `readelf -d elf.so`)
        @type neededs: string
        """
        def mymf(needed_data):
            needed, elfclass = needed_data
            idneeded = self.isNeededAvailable(needed)
            if idneeded == -1:
                # create eclass
                idneeded = self.addNeeded(needed)
            return (idpackage, idneeded, elfclass,)

        with self.__write_mutex:
            self.cursor.executemany("""
            INSERT into needed VALUES (?,?,?)
            """, list(map(mymf, neededs)))

    def insertEclasses(self, idpackage, eclasses):
        """
        Insert Source Package Manager used build specification file classes.
        The term "eclasses" is derived from Portage.

        @param idpackage: package indentifier
        @type idpackage: int
        @param eclasses: list of classes
        @type eclasses: list
        """

        def mymf(eclass):
            idclass = self.isEclassAvailable(eclass)
            if idclass == -1:
                idclass = self.addEclass(eclass)
            return (idpackage, idclass,)

        with self.__write_mutex:
            self.cursor.executemany("""
            INSERT into eclasses VALUES (?,?)
            """, list(map(mymf, eclasses)))

    def insertOnDiskSize(self, idpackage, mysize):
        """
        Insert on-disk size (bytes) for package.

        @param idpackage: package indentifier
        @type idpackage: int
        @param mysize: package size (bytes)
        @type mysize: int
        """
        with self.__write_mutex:
            self.cursor.execute("""
            INSERT into sizes VALUES (?,?)
            """, (idpackage, mysize,))

    def insertTrigger(self, idpackage, trigger):
        """
        Insert built-in trigger script for package, containing
        pre-install, post-install, pre-remove, post-remove hooks.
        This feature should be considered DEPRECATED, and kept for convenience.
        Please use Source Package Manager features if possible.

        @param idpackage: package indentifier
        @type idpackage: int
        @param trigger: trigger file dump
        @type trigger: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            INSERT into triggers VALUES (?,?)
            """, (idpackage, const_get_buffer()(trigger),))

    def insertBranchMigration(self, repository, from_branch, to_branch,
        post_migration_md5sum, post_upgrade_md5sum):
        """
        Insert Entropy Client "branch migration" scripts hash metadata.
        When upgrading from a branch to another, it can happen that repositories
        ship with scripts aiming to ease the upgrade.
        This method stores in the repository information on such scripts.

        @param repository: repository identifier
        @type repository: string
        @param from_branch: original branch
        @type from_branch: string
        @param to_branch: destination branch
        @type to_branch: string
        @param post_migration_md5sum: md5 hash related to "post-migration"
            branch script file
        @type post_migration_md5sum: string
        @param post_upgrade_md5sum: md5 hash related to "post-upgrade on new
            branch" script file
        @type post_upgrade_md5sum: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
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
        Update "post-upgrade on new branch" script file md5 hash.
        When upgrading from a branch to another, it can happen that repositories
        ship with scripts aiming to ease the upgrade.
        This method stores in the repository information on such scripts.

        @param repository: repository identifier
        @type repository: string
        @param from_branch: original branch
        @type from_branch: string
        @param to_branch: destination branch
        @type to_branch: string
        @param post_upgrade_md5sum: md5 hash related to "post-upgrade on new
            branch" script file
        @type post_upgrade_md5sum: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE entropy_branch_migration SET post_upgrade_md5sum = (?) WHERE
            repository = (?) AND from_branch = (?) AND to_branch = (?)
            """, (post_upgrade_md5sum, repository, from_branch, to_branch,))


    def bindSpmPackageUid(self, idpackage, spm_package_uid, branch):
        """
        Bind Source Package Manager package identifier ("COUNTER" metadata
        for Portage) to Entropy package.
        If uid <= -2, a new negative UID will be allocated and returned.
        Negative UIDs are considered auto-allocated by Entropy.
        This is mainly used for binary packages not belonging to any SPM
        packages which are just "injected" inside the repository.

        @param idpackage: package indentifier
        @type idpackage: int
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
            my_uid = self.getNewNegativeSpmUid()

        with self.__write_mutex:
            try:
                self.cursor.execute('INSERT into counters VALUES (?,?,?)',
                    (my_uid, idpackage, branch,))
            except self.dbapi2.IntegrityError:
                # we have a PRIMARY KEY we need to remove
                self._migrateCountersTable()
                self.cursor.execute('INSERT into counters VALUES (?,?,?)',
                    (my_uid, idpackage, branch,))

        return my_uid

    def insertSpmUid(self, idpackage, spm_package_uid, branch = None):
        """
        Insert Source Package Manager unique package identifier and bind it
        to Entropy package identifier given (idpackage). This method is used
        by Entropy Client and differs from "bindSpmPackageUid" because
        any other colliding idpackage<->uid binding is overwritten by design.

        @param idpackage: package indentifier
        @type idpackage: int
        @param spm_package_uid: Source package Manager unique package identifier
        @type spm_package_uid: int
        @param branch: current running Entropy branch
        @type branch: string
        """
        if not branch:
            branch = self.db_branch
        if not branch:
            branch = self.SystemSettings['repositories']['branch']

        with self.__write_mutex:

            self.cursor.execute("""
            DELETE FROM counters WHERE (counter = (?) OR
            idpackage = (?)) AND branch = (?);
            """, (spm_package_uid, idpackage, branch,))
            self.cursor.execute("""
            INSERT INTO counters VALUES (?,?,?);
            """, (spm_package_uid, idpackage, branch,))

            self.commitChanges()

    def setTrashedUid(self, spm_package_uid):
        """
        Mark given Source Package Manager unique package identifier as
        "trashed". This is a trick to allow Entropy Server to support
        multiple repositories and parallel handling of them without
        make it messing with removed packages from the underlying system.

        @param spm_package_uid: Source package Manager unique package identifier
        @type spm_package_uid: int
        """
        with self.__write_mutex:
            self.cursor.execute("""
            INSERT OR REPLACE INTO trashedcounters VALUES (?)
            """, (spm_package_uid,))

    def setSpmUid(self, idpackage, spm_package_uid, branch = None):
        """
        Update Source Package Manager unique package identifier for given
        Entropy package identifier (idpackage).
        This method *only* updates a currently available binding setting a new
        "spm_package_uid"

        @param idpackage: package indentifier
        @type idpackage: int
        @param spm_package_uid: Source package Manager unique package identifier
        @type spm_package_uid: int
        @keyword branch: current Entropy repository branch
        @type branch: string
        """
        branchstring = ''
        insertdata = [spm_package_uid, idpackage]
        if branch:
            branchstring = ', branch = (?)'
            insertdata.insert(1, branch)

        with self.__write_mutex:
            try:
                self.cursor.execute("""
                UPDATE counters SET counter = (?) %s
                WHERE idpackage = (?)""" % (branchstring,), insertdata)
            except self.dbapi2.Error:
                if self.dbname == etpConst['clientdbid']:
                    raise
            self.commitChanges()

    def contentDiff(self, idpackage, dbconn, dbconn_idpackage):
        """
        Return content metadata difference between two packages.

        @param idpackage: package indentifier available in this repository
        @type idpackage: int
        @param dbconn: other repository class instance
        @type dbconn: EntropyRepository
        @param dbconn_idpackage: package identifier available in other
            repository
        @type dbconn_idpackage: int
        @return: content difference
        @rtype: set
        @raise AttributeError: when self instance and dbconn are the same
        """

        if self is dbconn:
            raise AttributeError("cannot diff inside the same db")

        self.connection.text_factory = lambda x: const_convert_to_unicode(x)

        # setup random table name
        randomtable = "cdiff%s" % (self.entropyTools.get_random_number(),)
        while self._doesTableExist(randomtable):
            randomtable = "cdiff%s" % (self.entropyTools.get_random_number(),)

        # create random table
        self.cursor.execute("""
            CREATE TEMPORARY TABLE %s ( file VARCHAR )""" % (randomtable,)
        )

        try:
            dbconn.connection.text_factory = lambda x: \
                const_convert_to_unicode(x)

            cur = dbconn.cursor.execute("""
            SELECT file FROM content WHERE idpackage = (?)
            """, (dbconn_idpackage,))
            self.cursor.executemany("""
            INSERT INTO %s VALUES (?)""" % (randomtable,), cur)

            # now compare
            cur = self.cursor.execute("""
            SELECT file FROM content 
            WHERE content.idpackage = (?) AND 
            content.file NOT IN (SELECT file from %s)""" % (randomtable,),
                (idpackage,))

            # suck back
            return self._cur2set(cur)

        finally:
            self.cursor.execute('DROP TABLE IF EXISTS %s' % (randomtable,))

    def doCleanups(self):
        """
        Run repository metadata cleanup over unused references.
        """
        self.cleanupUseflags()
        self.cleanupSources()
        self.cleanupEclasses()
        self.cleanupNeeded()
        self.cleanupDependencies()
        self.cleanupChangelogs()

    def cleanupUseflags(self):
        """
        Cleanup "USE flags" metadata unused references to save space.
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM useflagsreference 
            WHERE idflag NOT IN (SELECT idflag FROM useflags)""")

    def cleanupSources(self):
        """
        Cleanup "sources" metadata unused references to save space.
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM sourcesreference 
            WHERE idsource NOT IN (SELECT idsource FROM sources)""")

    def cleanupEclasses(self):
        """
        Cleanup "eclass" metadata unused references to save space.
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM eclassesreference 
            WHERE idclass NOT IN (SELECT idclass FROM eclasses)""")

    def cleanupNeeded(self):
        """
        Cleanup "needed" metadata unused references to save space.
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM neededreference 
            WHERE idneeded NOT IN (SELECT idneeded FROM needed)""")

    def cleanupDependencies(self):
        """
        Cleanup "dependencies" metadata unused references to save space.
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM dependenciesreference 
            WHERE iddependency NOT IN (SELECT iddependency FROM dependencies)
            """)

    def cleanupChangelogs(self):
        """
        Cleanup "changelog" metadata unused references to save space.
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM packagechangelogs 
            WHERE category || "/" || name NOT IN 
            (SELECT categories.category || "/" || baseinfo.name
                FROM baseinfo, categories 
                WHERE baseinfo.idcategory = categories.idcategory)
            """)

    def getNewNegativeSpmUid(self):
        """
        Obtain auto-generated available negative Source Package Manager
        package identifier.

        @return: new negative spm uid
        @rtype: int
        """
        try:
            cur = self.cursor.execute('SELECT min(counter) FROM counters')
            dbcounter = cur.fetchone()
            mycounter = 0
            if dbcounter:
                mycounter = dbcounter[0]

            if mycounter >= -1 or mycounter is None:
                counter = -2
            else:
                counter = mycounter-1

        except self.dbapi2.Error:
            counter = -2 # first available counter

        return counter

    def getApi(self):
        """
        Get Entropy repository API.

        @return: Entropy repository API
        @rtype: int
        """
        cur = self.cursor.execute('SELECT max(etpapi) FROM baseinfo')
        api = cur.fetchone()
        if api:
            return api[0]
        return -1

    def getDependency(self, iddependency):
        """
        Return dependency string for given dependency identifier.

        @param iddependency: dependency identifier
        @type iddependency: int
        @return: dependency string
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT dependency FROM dependenciesreference WHERE iddependency = (?)
        LIMIT 1
        """, (iddependency,))
        dep = cur.fetchone()
        if dep:
            return dep[0]

    def getCategory(self, idcategory):
        """
        Get category name from category identifier.

        @param idcategory: category identifier
        @type idcategory: int
        @return: category name
        @rtype: string
        """
        cur = self.cursor.execute("""
        SELECT category from categories WHERE idcategory = (?) LIMIT 1
        """, (idcategory,))
        cat = cur.fetchone()
        if cat:
            return cat[0]
        return cat

    def getSystemPackages(self):
        """
        Obtain a list of system packages on this repository.

        @return: list (set) of system package identifiers
        @rtype: set
        """
        cur = self.cursor.execute("SELECT idpackage FROM systempackages")
        return self._cur2set(cur)

    def getIDPackages(self, atom):
        """
        Obtain repository package identifiers from atom string.

        @param atom: package atom
        @type atom: string
        @return: list of matching idpackages found
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo WHERE atom = (?)
        """, (atom,))
        return self._cur2set(cur)

    def getIDPackageFromDownload(self, download_relative_path,
        endswith = False):
        """
        Obtain repository package identifier from its relative download path
        string.

        @param download_relative_path: relative download path string returned
            by "retrieveDownloadURL" method
        @type download_relative_path: string
        @keyword endswith: search for idpackage which download metadata ends
            with the one provided by download_relative_path
        @type endswith: bool
        @return: idpackage in repository or -1 if not found
        @rtype: int
        """
        if endswith:
            cur = self.cursor.execute("""
            SELECT baseinfo.idpackage FROM baseinfo,extrainfo
            WHERE extrainfo.download LIKE (?) AND
            baseinfo.idpackage = extrainfo.idpackage
            LIMIT 1
            """, ("%"+download_relative_path,))
        else:
            cur = self.cursor.execute("""
            SELECT baseinfo.idpackage FROM baseinfo,extrainfo
            WHERE extrainfo.download = (?) AND
            baseinfo.idpackage = extrainfo.idpackage
            LIMIT 1
            """, (download_relative_path,))

        idpackage = cur.fetchone()
        if idpackage:
            return idpackage[0]
        return -1

    def getIDPackagesFromFile(self, file):
        """
        Obtain repository package identifiers for packages owning the provided
        path string (file).

        @param file: path to file (or directory) to match
        @type file: string
        @return: list (set) of idpackages found
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT idpackage FROM content WHERE file = (?)
        """, (file,))
        return self._cur2list(cur)

    def getIDCategory(self, category):
        """
        Obtain category identifier from category name.

        @param category: category name
        @type category: string
        @return: idcategory or -1 if not found
        @rtype: int
        """
        cur = self.cursor.execute("""
        SELECT "idcategory" FROM categories WHERE category = (?)
        LIMIT 1
        """, (category,))
        idcat = cur.fetchone()
        if idcat:
            return idcat[0]
        return -1

    def getVersioningData(self, idpackage):
        """
        Get package version information for provided package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: tuple of length 3 composed by (version, tag, revision,)
            belonging to idpackage
        @rtype: tuple
        """
        cur = self.cursor.execute("""
        SELECT version, versiontag, revision FROM baseinfo WHERE idpackage = (?)
        LIMIT 1
        """, (idpackage,))
        return cur.fetchone()

    def getStrictData(self, idpackage):
        """
        Get a restricted (optimized) set of package metadata for provided
        package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: tuple of length 6 composed by
            (package key, slot, version, tag, revision, atom)
            belonging to idpackage
        @rtype: tuple
        """
        self.cursor.execute("""
        SELECT categories.category || "/" || baseinfo.name,
        baseinfo.slot,baseinfo.version,baseinfo.versiontag,
        baseinfo.revision,baseinfo.atom FROM baseinfo, categories
        WHERE baseinfo.idpackage = (?) AND 
        baseinfo.idcategory = categories.idcategory""", (idpackage,))
        return self.cursor.fetchone()

    def getStrictScopeData(self, idpackage):
        """
        Get a restricted (optimized) set of package metadata for provided
        identifier that can be used to determine the scope of package.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: tuple of length 3 composed by (atom, slot, revision,)
            belonging to idpackage
        @rtype: tuple
        """
        self.cursor.execute("""
        SELECT atom, slot, revision FROM baseinfo
        WHERE idpackage = (?)""", (idpackage,))
        rslt = self.cursor.fetchone()
        return rslt

    def getScopeData(self, idpackage):
        """
        Get a set of package metadata for provided identifier that can be
        used to determine the scope of package.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: tuple of length 9 composed by
            (atom, category name, name, version,
                slot, tag, revision, branch, api,)
            belonging to idpackage
        @rtype: tuple
        """
        self.cursor.execute("""
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
        """, (idpackage,))
        return self.cursor.fetchone()

    def getBaseData(self, idpackage):
        """
        Get a set of basic package metadata for provided package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: tuple of length 19 composed by
            (atom, name, version, tag, description, category name, CHOST,
            CFLAGS, CXXFLAGS, homepage, license, branch, download path, digest,
            slot, api, creation date, package size, revision,)
            belonging to idpackage
        @rtype: tuple
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
        self.cursor.execute(sql, (idpackage,))
        return self.cursor.fetchone()

    def getTriggerInfo(self, idpackage, content = True):
        """
        Get a set of basic package metadata for provided package identifier.
        This method is optimized to work with Entropy Client installation
        triggers returning only what is strictly needed.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword content: if True, grabs the "content" metadata too, othewise
            such dict key value will be shown as empty set().
        @type content: bool
        @return: dictionary containing package metadata

            data = {
                'atom': atom,
                'category': category,
                'name': name,
                'version': version,
                'versiontag': versiontag,
                'revision': revision,
                'branch': branch,
                'chost': chost,
                'cflags': cflags,
                'cxxflags': cxxflags,
                'etpapi': etpapi,
                'trigger': self.retrieveTrigger(idpackage),
                'eclasses': self.retrieveEclasses(idpackage),
                'content': pkg_content,
                'spm_phases': self.retrieveSpmPhases(idpackage),
            }

        @rtype: dict
        """

        atom, category, name, \
        version, slot, versiontag, \
        revision, branch, etpapi = self.getScopeData(idpackage)
        chost, cflags, cxxflags = self.retrieveCompileFlags(idpackage)

        pkg_content = set()
        if content:
            pkg_content = self.retrieveContent(idpackage)

        data = {
            'atom': atom,
            'category': category,
            'name': name,
            'version': version,
            'versiontag': versiontag,
            'revision': revision,
            'branch': branch,
            'chost': chost,
            'cflags': cflags,
            'cxxflags': cxxflags,
            'etpapi': etpapi,
            'trigger': self.retrieveTrigger(idpackage),
            'eclasses': self.retrieveEclasses(idpackage),
            'content': pkg_content,
            'spm_phases': self.retrieveSpmPhases(idpackage),
        }
        return data

    def getPackageData(self, idpackage, get_content = True,
            content_insert_formatted = False, trigger_unicode = False):
        """
        Reconstruct all the package metadata belonging to provided package
        identifier into a dict object.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword get_content:
        @type get_content: bool
        @keyword content_insert_formatted:
        @type content_insert_formatted: bool
        @keyword trigger_unicode:
        @type trigger_unicode: bool
        @return: package metadata in dict() form

        >>> data = {
            'atom': atom,
            'name': name,
            'version': version,
            'versiontag':versiontag,
            'description': description,
            'category': category,
            'chost': chost,
            'cflags': cflags,
            'cxxflags': cxxflags,
            'homepage': homepage,
            'license': mylicense,
            'branch': branch,
            'download': download,
            'digest': digest,
            'slot': slot,
            'etpapi': etpapi,
            'datecreation': datecreation,
            'size': size,
            'revision': revision,
            'counter': self.retrieveSpmUid(idpackage),
            'messages': self.retrieveMessages(idpackage),
            'trigger': self.retrieveTrigger(idpackage,
                get_unicode = trigger_unicode),
            'disksize': self.retrieveOnDiskSize(idpackage),
            'changelog': self.retrieveChangelog(idpackage),
            'injected': self.isInjected(idpackage),
            'systempackage': self.isSystemPackage(idpackage),
            'config_protect': self.retrieveProtect(idpackage),
            'config_protect_mask': self.retrieveProtectMask(idpackage),
            'useflags': self.retrieveUseflags(idpackage),
            'keywords': self.retrieveKeywords(idpackage),
            'sources': sources,
            'eclasses': self.retrieveEclasses(idpackage),
            'needed': self.retrieveNeeded(idpackage, extended = True),
            'provided_libs': self.retrieveProvidedLibraries(idpackage),
            'provide': provide (the old provide metadata version)
            'provide_extended': self.retrieveProvide(idpackage),
            'conflicts': self.retrieveConflicts(idpackage),
            'licensedata': self.retrieveLicensedata(idpackage),
            'content': content,
            'dependencies': dict((x, y,) for x, y in \
                self.retrieveDependencies(idpackage, extended = True)),
            'mirrorlinks': [[x,self.retrieveMirrorInfo(x)] for x in mirrornames],
            'signatures': signatures,
            'spm_phases': self.retrieveSpmPhases(idpackage),
            'spm_repository': self.retrieveSpmRepository(idpackage),
        }

        @rtype: dict
        """

        data = {}
        try:
            atom, name, version, versiontag, \
            description, category, chost, \
            cflags, cxxflags, homepage, \
            mylicense, branch, download, \
            digest, slot, etpapi, \
            datecreation, size, revision  = self.getBaseData(idpackage)
        except TypeError:
            return None

        content = {}
        if get_content:
            content = self.retrieveContent(
                idpackage, extended = True,
                formatted = True, insert_formatted = content_insert_formatted
            )

        sources = self.retrieveSources(idpackage)
        mirrornames = set()
        for x in sources:
            if x.startswith("mirror://"):
                mirrornames.add(x.split("/")[2])

        sha1, sha256, sha512 = self.retrieveSignatures(idpackage)
        signatures = {
            'sha1': sha1,
            'sha256': sha256,
            'sha512': sha512,
        }

        provide_extended = self.retrieveProvide(idpackage)
        # FIXME: backward compat, remove someday
        old_provide = set()
        for x in provide_extended:
            if isinstance(x, tuple):
                old_provide.add(x[0])
            else:
                old_provide.add(x)

        data = {
            'atom': atom,
            'name': name,
            'version': version,
            'versiontag': versiontag,
            'description': description,
            'category': category,
            'chost': chost,
            'cflags': cflags,
            'cxxflags': cxxflags,
            'homepage': homepage,
            'license': mylicense,
            'branch': branch,
            'download': download,
            'digest': digest,
            'slot': slot,
            'etpapi': etpapi,
            'datecreation': datecreation,
            'size': size,
            'revision': revision,
            # risky to add to the sql above, still
            'counter': self.retrieveSpmUid(idpackage),
            'messages': self.retrieveMessages(idpackage),
            'trigger': self.retrieveTrigger(idpackage,
                get_unicode = trigger_unicode),
            'disksize': self.retrieveOnDiskSize(idpackage),
            'changelog': self.retrieveChangelog(idpackage),
            'injected': self.isInjected(idpackage),
            'systempackage': self.isSystemPackage(idpackage),
            'config_protect': self.retrieveProtect(idpackage),
            'config_protect_mask': self.retrieveProtectMask(idpackage),
            'useflags': self.retrieveUseflags(idpackage),
            'keywords': self.retrieveKeywords(idpackage),
            'sources': sources,
            'eclasses': self.retrieveEclasses(idpackage),
            'needed': self.retrieveNeeded(idpackage, extended = True),
            'provided_libs': self.retrieveProvidedLibraries(idpackage),
            'provide': old_provide,
            'provide_extended': provide_extended,
            'conflicts': self.retrieveConflicts(idpackage),
            'licensedata': self.retrieveLicensedata(idpackage),
            'content': content,
            'dependencies': dict((x, y,) for x, y in \
                self.retrieveDependencies(idpackage, extended = True)),
            'mirrorlinks': [[x, self.retrieveMirrorInfo(x)] for x in mirrornames],
            'signatures': signatures,
            'spm_phases': self.retrieveSpmPhases(idpackage),
            'spm_repository': self.retrieveSpmRepository(idpackage),
        }

        return data

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

    def clearCache(self, depends = False):
        """
        Clear on-disk repository cache.

        @keyword depends: if True, clear reverse dependencies cache
        @type depends: bool
        """

        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.clear_cache_hook(self)
            if exec_rc:
                raise RepositoryPluginError(
                    "[clear_cache_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

        self.live_cache.clear()
        def do_clear(name):
            """
            docstring_title

            @param name:
            @type name:
            @return:
            @rtype:

            """
            dump_path = os.path.join(etpConst['dumpstoragedir'], name)
            dump_dir = os.path.dirname(dump_path)
            if os.path.isdir(dump_dir):
                for item in os.listdir(dump_dir):
                    try:
                        os.remove(os.path.join(dump_dir, item))
                    except OSError:
                        pass

        do_clear("%s/%s/" % (self.dbMatchCacheKey, self.dbname,))
        if depends:
            do_clear(etpCache['depends_tree'])
            do_clear(etpCache['dep_tree'])
            do_clear(etpCache['filter_satisfied_deps'])

    def retrieveRepositoryUpdatesDigest(self, repository):
        """
        This method should be considered internal and not suited for general
        audience. Return digest (md5 hash) bound to repository package
        names/slots updates.

        @param repository: repository identifier
        @type repository: string
        @return: digest string
        @rtype: string
        """
        cur = self.cursor.execute("""
        SELECT digest FROM treeupdates WHERE repository = (?) LIMIT 1
        """, (repository,))

        mydigest = cur.fetchone()
        if mydigest:
            return mydigest[0]
        return -1

    def listAllTreeUpdatesActions(self, no_ids_repos = False):
        """
        This method should be considered internal and not suited for general
        audience.
        List all the available "treeupdates" (package names/slots changes
            directives) actions.

        @keyword no_ids_repos: if True, it will just return a 3-length tuple
            list containing [(command, branch, unix_time,), ...]
        @type no_ids_repos: bool
        @return: list of tuples
        @rtype: list

        """
        if no_ids_repos:
            self.cursor.execute("""
            SELECT command, branch, date FROM treeupdatesactions
            """)
        else:
            self.cursor.execute('SELECT * FROM treeupdatesactions')
        return self.cursor.fetchall()

    def retrieveTreeUpdatesActions(self, repository, forbranch = None):
        """
        This method should be considered internal and not suited for general
        audience.
        Return all the available "treeupdates (package names/slots changes
            directives) actions for provided repository.

        @param repository: repository identifier
        @type repository: string
        @keyword forbranch: filter for specific Entropy branch, provide
            alternative branch string
        @type forbranch: string
        @return: list of raw-string commands to run
        @rtype: list
        """
        if forbranch is None:
            forbranch = self.db_branch
        if not forbranch:
            forbranch = self.SystemSettings['repositories']['branch']

        params = (repository,)
        branch_string = ''
        if forbranch:
            branch_string = 'and branch = (?)'
            params = (repository, forbranch,)

        self.cursor.execute("""
        SELECT command FROM treeupdatesactions WHERE 
        repository = (?) %s order by date""" % (branch_string,), params)
        return self._fetchall2list(self.cursor.fetchall())

    def bumpTreeUpdatesActions(self, updates):
        # mainly used to restore a previous table,
        # used by reagent in --initialize
        """
        This method should be considered internal and not suited for general
        audience.
        This method rewrites "treeupdates" metadata in repository.

        @param updates: new treeupdates metadata
        @type updates: list
        """
        with self.__write_mutex:
            self.cursor.execute('DELETE FROM treeupdatesactions')
            self.cursor.executemany("""
            INSERT INTO treeupdatesactions VALUES (?,?,?,?,?)
            """, updates)
            self.commitChanges()

    def removeTreeUpdatesActions(self, repository):
        """
        This method should be considered internal and not suited for general
        audience.
        This method removes "treeupdates" metadata in repository.

        @param repository: remove treeupdates metadata for provided repository
        @type repository: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM treeupdatesactions WHERE repository = (?)
            """, (repository,))
            self.commitChanges()

    def insertTreeUpdatesActions(self, updates, repository):
        """
        This method should be considered internal and not suited for general
        audience.
        This method insert "treeupdates" metadata in repository.

        @param updates: new treeupdates metadata
        @type updates: list
        @param repository: insert treeupdates metadata for provided repository
        @type repository: string
        """
        with self.__write_mutex:
            myupdates = [[repository]+list(x) for x in updates]
            self.cursor.executemany("""
            INSERT INTO treeupdatesactions VALUES (NULL,?,?,?,?)
            """, myupdates)
            self.commitChanges()

    def setRepositoryUpdatesDigest(self, repository, digest):
        """
        This method should be considered internal and not suited for general
        audience.
        Set "treeupdates" checksum (digest) for provided repository.

        @param repository: repository identifier
        @type repository: string
        @param digest: treeupdates checksum string (md5)
        @type digest: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM treeupdates where repository = (?)
            """, (repository,))
            self.cursor.execute("""
            INSERT INTO treeupdates VALUES (?,?)
            """, (repository, digest,))

    def addRepositoryUpdatesActions(self, repository, actions, branch):
        """
        This method should be considered internal and not suited for general
        audience.
        Add "treeupdates" actions for repository and branch provided.

        @param repository: repository identifier
        @type repository: string
        @param actions: list of raw treeupdates action strings
        @type actions: list
        @param branch: branch metadata to bind to the provided actions
        @type branch: string
        """

        mytime = str(self.entropyTools.get_current_unix_time())
        with self.__write_mutex:
            myupdates = [
                (repository, x, branch, mytime,) for x in actions \
                if not self.doesTreeupdatesActionExist(repository, x, branch)
            ]
            self.cursor.executemany("""
            INSERT INTO treeupdatesactions VALUES (NULL,?,?,?,?)
            """, myupdates)

    def doesTreeupdatesActionExist(self, repository, command, branch):
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
        self.cursor.execute("""
        SELECT * FROM treeupdatesactions 
        WHERE repository = (?) and command = (?)
        and branch = (?)""", (repository, command, branch,))

        result = self.cursor.fetchone()
        if result:
            return True
        return False

    def clearPackageSets(self):
        """
        Clear Package sets (group of packages) entries in repository.
        """
        self.cursor.execute('DELETE FROM packagesets')

    def insertPackageSets(self, sets_data):
        """
        Insert Package sets metadata into repository.

        @param sets_data: dictionary containing package set names as keys and
            list (set) of dependencies as value
        @type sets_data: dict
        """
        mysets = []
        for setname in sorted(sets_data):
            for dependency in sorted(sets_data[setname]):
                try:
                    mysets.append((const_convert_to_unicode(setname),
                        const_convert_to_unicode(dependency),))
                except (UnicodeDecodeError, UnicodeEncodeError,):
                    continue

        with self.__write_mutex:
            self.cursor.executemany('INSERT INTO packagesets VALUES (?,?)',
                mysets)

    def retrievePackageSets(self):
        """
        Return Package sets metadata stored in repository.

        @return: dictionary containing package set names as keys and
            list (set) of dependencies as value
        @rtype: dict
        """
        # FIXME backward compatibility
        if not self._doesTableExist('packagesets'):
            return {}

        cur = self.cursor.execute("SELECT setname, dependency FROM packagesets")
        data = cur.fetchall()

        sets = {}
        for setname, dependency in data:
            obj = sets.setdefault(setname, set())
            obj.add(dependency)
        return sets

    def retrievePackageSet(self, setname):
        """
        Return dependencies belonging to given package set name.
        This method does not check if the given package set name is
        available and returns an empty list (set) in these cases.

        @param setname: Package set name
        @type setname: string
        @return: list (set) of dependencies belonging to given package set name
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT dependency FROM packagesets WHERE setname = (?)""",
            (setname,))
        return self._cur2set(cur)

    def retrieveSystemPackages(self):
        """
        Return a list of package identifiers that are part of the base
        system (thus, marked as system packages).

        @return: list (set) of system package identifiers
        @rtype: set
        """
        cur = self.cursor.execute('SELECT idpackage FROM systempackages')
        return self._cur2set(cur)

    def retrieveAtom(self, idpackage):
        """
        Return "atom" metadatum for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: atom string
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT atom FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        atom = cur.fetchone()
        if atom:
            return atom[0]

    def retrieveBranch(self, idpackage):
        """
        Return "branch" metadatum for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: branch metadatum
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT branch FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        branch = cur.fetchone()
        if branch:
            return branch[0]

    def retrieveTrigger(self, idpackage, get_unicode = False):
        """
        Return "trigger" script content for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword get_unicode: return in unicode format
        @type get_unicode: bool
        @return: trigger script content
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT data FROM triggers WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        trigger = cur.fetchone()
        if not trigger:
            # backward compatibility with <=0.52.x
            if get_unicode:
                return const_convert_to_unicode('')
            return const_convert_to_rawstring('')
        if not get_unicode:
            return const_convert_to_rawstring(trigger[0])
        # cross fingers...
        return const_convert_to_unicode(trigger[0])

    def retrieveDownloadURL(self, idpackage):
        """
        Return "download URL" metadatum for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: download url metadatum
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT download FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        download = cur.fetchone()
        if download:
            return download[0]

    def retrieveDescription(self, idpackage):
        """
        Return "description" metadatum for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: package description
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT description FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        description = cur.fetchone()
        if description:
            return description[0]

    def retrieveHomepage(self, idpackage):
        """
        Return "homepage" metadatum for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: package homepage
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT homepage FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        home = cur.fetchone()
        if home:
            return home[0]

    def retrieveSpmUid(self, idpackage):
        """
        Return Source Package Manager unique identifier bound to Entropy
        package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: Spm UID or -1 (if not bound, valid for injected packages)
        @rtype: int
        """
        cur = self.cursor.execute("""
        SELECT counters.counter FROM counters,baseinfo
        WHERE counters.idpackage = (?) AND
        baseinfo.idpackage = counters.idpackage AND
        baseinfo.branch = counters.branch LIMIT 1
        """, (idpackage,))
        mycounter = cur.fetchone()
        if mycounter:
            return mycounter[0]
        return -1

    def retrieveMessages(self, idpackage):
        """
        Return "messages" metadatum for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: list of package messages (for making user aware of stuff)
        @rtype: list
        """
        cur = self.cursor.execute("""
        SELECT message FROM messages WHERE idpackage = (?)""", (idpackage,))
        return self._cur2list(cur)

    def retrieveSize(self, idpackage):
        """
        Return "size" metadatum for given package identifier.
        "size" refers to Entropy package file size in bytes.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: size of Entropy package for given package identifier
        @rtype: int or None
        """
        cur = self.cursor.execute("""
        SELECT size FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        size = cur.fetchone()
        if size:
            try:
                return int(size[0])
            except ValueError: # wtf?
                return 0

    # in bytes
    def retrieveOnDiskSize(self, idpackage):
        """
        Return "on disk size" metadatum for given package identifier.
        "on disk size" refers to unpacked Entropy package file size in bytes,
        which is in other words, the amount of space required on live system
        to have it installed (simplified explanation).

        @param idpackage: package indentifier
        @type idpackage: int
        @return: on disk size metadatum
        @rtype: int

        """
        cur = self.cursor.execute("""
        SELECT size FROM sizes WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        size = cur.fetchone()
        if size:
            return size[0]
        return 0

    def retrieveDigest(self, idpackage):
        """
        Return "digest" metadatum for given package identifier.
        "digest" refers to Entropy package file md5 checksum bound to given
        package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: md5 checksum for given package identifier
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT digest FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        digest = cur.fetchone()
        if digest:
            return digest[0]

    def retrieveSignatures(self, idpackage):
        """
        Return package file extra hashes (sha1, sha256, sha512) for given
        package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: tuple of length 3, sha1, sha256, sha512 package extra
            hashes if available, otherwise the same but with None as values.
        @rtype: tuple
        """
        # FIXME backward compatibility
        if not self._doesTableExist('packagesignatures'):
            return None, None, None

        cur = self.cursor.execute("""
        SELECT sha1, sha256, sha512 FROM packagesignatures
        WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        data = cur.fetchone()

        if data:
            return data
        return None, None, None

    def retrieveName(self, idpackage):
        """
        Return "name" metadatum for given package identifier.
        Attention: package name != atom, the former is just a subset of the
        latter.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: "name" metadatum for given package identifier
        @rtype: string or None

        """
        self.cursor.execute("""
        SELECT name FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        name = self.cursor.fetchone()
        if name:
            return name[0]

    def retrieveKeySlot(self, idpackage):
        """
        Return a tuple composed by package key and slot for given package
        identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: tuple of length 2 composed by (package_key, package_slot,)
        @rtupe: tuple or None
        """
        cur = self.cursor.execute("""
        SELECT categories.category || "/" || baseinfo.name,baseinfo.slot
        FROM baseinfo,categories
        WHERE baseinfo.idpackage = (?) AND
        baseinfo.idcategory = categories.idcategory LIMIT 1
        """, (idpackage,))
        return cur.fetchone()

    def retrieveKeySlotAggregated(self, idpackage):
        """
        Return package key and package slot string (aggregated form through
        ":", for eg.: app-foo/foo:2).
        This method has been implemented for performance reasons.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: package key + ":" + slot string
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT categories.category || "/" || baseinfo.name || ":" ||
        baseinfo.slot FROM baseinfo,categories
        WHERE baseinfo.idpackage = (?) AND
        baseinfo.idcategory = categories.idcategory LIMIT 1
        """, (idpackage,))
        data = cur.fetchone()
        if data:
            return data[0]

    def retrieveKeySlotTag(self, idpackage):
        """
        Return package key, slot and tag tuple for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: tuple of length 3 providing (package_key, slot, package_tag,)
        @rtype: tuple
        """
        cur = self.cursor.execute("""
        SELECT categories.category || "/" || baseinfo.name, baseinfo.slot,
        baseinfo.versiontag FROM baseinfo, categories WHERE
        baseinfo.idpackage = (?) AND
        baseinfo.idcategory = categories.idcategory LIMIT 1
        """, (idpackage,))
        return cur.fetchone()

    def retrieveVersion(self, idpackage):
        """
        Return package version for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: package version
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT version FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        ver = cur.fetchone()
        if ver:
            return ver[0]

    def retrieveRevision(self, idpackage):
        """
        Return package Entropy-revision for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: Entropy-revision for given package indentifier
        @rtype: int or None

        """
        cur = self.cursor.execute("""
        SELECT revision FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        rev = cur.fetchone()
        if rev:
            return rev[0]

    def retrieveCreationDate(self, idpackage):
        """
        Return creation date for given package identifier.
        Creation date returned is a string representation of UNIX time format.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: creation date for given package identifier
        @rtype: string or None

        """
        cur = self.cursor.execute("""
        SELECT datecreation FROM extrainfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        date = cur.fetchone()
        if date:
            return date[0]

    def retrieveApi(self, idpackage):
        """
        Return Entropy API in use when given package identifier was added.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: Entropy API for given package identifier
        @rtype: int or None
        """
        cur = self.cursor.execute("""
        SELECT etpapi FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        api = cur.fetchone()
        if api:
            return api[0]

    def retrieveUseflags(self, idpackage):
        """
        Return "USE flags" metadatum for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: list (set) of USE flags for given package identifier.
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT flagname FROM useflags,useflagsreference
        WHERE useflags.idpackage = (?) AND 
        useflags.idflag = useflagsreference.idflag
        """, (idpackage,))
        return self._cur2set(cur)

    def retrieveEclasses(self, idpackage):
        """
        Return "eclass" metadatum for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: list (set) of eclasses for given package identifier
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT classname FROM eclasses,eclassesreference
        WHERE eclasses.idpackage = (?) AND
        eclasses.idclass = eclassesreference.idclass""", (idpackage,))
        return self._cur2set(cur)

    def retrieveSpmPhases(self, idpackage):
        """
        Return "Source Package Manager install phases" for given package
        identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: "Source Package Manager available install phases" string
        @rtype: string or None
        """
        # FIXME backward compatibility
        if not self._doesTableExist('packagespmphases'):
            return None

        cur = self.cursor.execute("""
        SELECT phases FROM packagespmphases WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        spm_phases = cur.fetchone()

        if spm_phases:
            return spm_phases[0]

    def retrieveSpmRepository(self, idpackage):
        """
        Return Source Package Manager source repository used at compile time.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: Source Package Manager source repository
        @rtype: string or None
        """
        # FIXME backward compatibility
        if not self._doesTableExist('packagespmrepository'):
            return None
        cur = self.cursor.execute("""
        SELECT repository FROM packagespmrepository
        WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        spm_repo = cur.fetchone()

        if spm_repo:
            return spm_repo[0]

    def retrieveNeededRaw(self, idpackage):
        """
        Return (raw format) "NEEDED" ELF metadata for libraries contained
        in given package.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: list (set) of "NEEDED" entries contained in ELF objects
            packed into package file
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT library FROM needed,neededreference
        WHERE needed.idpackage = (?) AND 
        needed.idneeded = neededreference.idneeded""", (idpackage,))
        return self._cur2set(cur)

    def retrieveNeeded(self, idpackage, extended = False, format = False):
        """
        Return "NEEDED" elf metadata for libraries contained in given package.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword extended: also return ELF class information for every
            library name
        @type extended: bool
        @keyword format: properly format output, returning a dictionary with
            library name as key and ELF class as value
        @type format: bool
        @return: "NEEDED" metadata for libraries contained in given package.
        @rtype: list or set
        """
        if extended:

            cur = self.cursor.execute("""
            SELECT library,elfclass FROM needed,neededreference
            WHERE needed.idpackage = (?) AND
            needed.idneeded = neededreference.idneeded order by library
            """, (idpackage,))
            needed = cur.fetchall()

        else:

            cur = self.cursor.execute("""
            SELECT library FROM needed,neededreference
            WHERE needed.idpackage = (?) AND
            needed.idneeded = neededreference.idneeded ORDER BY library
            """, (idpackage,))
            needed = self._cur2list(cur)

        if extended and format:
            return dict((lib, elfclass,) for lib, elfclass in needed)
        return needed

    def retrieveProvidedLibraries(self, idpackage):
        """
        Return list of library names (from NEEDED ELF metadata) provided by
        given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: list of tuples of length 2 composed by library name and ELF
            class
        @rtype: list
        """
        # TODO: remove this in future, backward compat.
        if not self._doesTableExist('provided_libs'):
            return set()

        cur = self.cursor.execute("""
        SELECT library, path, elfclass FROM provided_libs
        WHERE idpackage = (?)
        """, (idpackage,))
        return set(cur.fetchall())

    def retrieveConflicts(self, idpackage):
        """
        Return list of conflicting dependencies for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: list (set) of conflicting package dependencies
        @rtype: set

        """
        cur = self.cursor.execute("""
        SELECT conflict FROM conflicts WHERE idpackage = (?)
        """, (idpackage,))
        return self._cur2set(cur)

    def retrieveProvide(self, idpackage):
        """
        Return list of dependencies/atoms are provided by the given package
        identifier (see Portage documentation about old-style PROVIDEs).

        @param idpackage: package indentifier
        @type idpackage: int
        @return: list (set) of atoms provided by package
        @rtype: set
        """
        # FIXME: added for backward compatibility, remove someday
        is_default_str = ',0'
        if self._doesColumnInTableExist("provide", "is_default"):
            is_default_str = ',is_default '

        cur = self.cursor.execute("""
        SELECT atom%s FROM provide WHERE idpackage = (?)
        """ % (is_default_str,), (idpackage,))
        if is_default_str:
            return set(cur.fetchall())
        return self._cur2set(cur)

    def retrieveDependenciesList(self, idpackage):
        """
        Return list of dependencies, including conflicts for given package
        identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: list (set) of dependencies of package
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT dependenciesreference.dependency
        FROM dependencies, dependenciesreference
        WHERE dependencies.idpackage = (?) AND
        dependencies.iddependency = dependenciesreference.iddependency
        UNION SELECT "!" || conflict FROM conflicts
        WHERE idpackage = (?)""", (idpackage, idpackage,))
        return self._cur2set(cur)

    def retrievePostDependencies(self, idpackage, extended = False):
        """
        Return list of post-merge package dependencies for given package
        identifier.
        Note: this function is just a wrapper of retrieveDependencies()
        providing deptype (dependency type) = post-dependencies.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword extended: return in extended format
        @type extended: bool
        """
        return self.retrieveDependencies(idpackage, extended = extended,
            deptype = etpConst['dependency_type_ids']['pdepend_id'])

    def retrieveManualDependencies(self, idpackage, extended = False):
        """
        Return manually added dependencies for given package identifier.
        Note: this function is just a wrapper of retrieveDependencies()
        providing deptype (dependency type) = manual-dependencies.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword extended: return in extended format
        @type extended: bool
        """
        return self.retrieveDependencies(idpackage, extended = extended,
            deptype = etpConst['dependency_type_ids']['mdepend_id'])

    def retrieveDependencies(self, idpackage, extended = False, deptype = None,
        exclude_deptypes = None):
        """
        Return dependencies for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword extended: return in extended format (list of tuples of length 2
            composed by dependency name and dependency type)
        @type extended: bool
        @keyword deptype: return only given type of dependencies
            see etpConst['dependency_type_ids']['*depend_id'] for dependency type
            identifiers
        @type deptype: bool
        @keyword exclude_deptypes: list of dependency types to exclude
        @type exclude_deptypes: list
        @return: dependencies of given package
        @rtype: list or set
        """
        searchdata = [idpackage]

        depstring = ''
        if deptype is not None:
            depstring = ' and dependencies.type = (?)'
            searchdata.append(deptype)

        excluded_deptypes_query = ""
        if exclude_deptypes is not None:
            for dep_type in exclude_deptypes:
                if not isinstance(dep_type, int):
                    # filter out crap
                    continue
                excluded_deptypes_query += " AND dependencies.type != %s" % (
                    dep_type,)

        if extended:
            cur = self.cursor.execute("""
            SELECT dependenciesreference.dependency,dependencies.type
            FROM dependencies,dependenciesreference
            WHERE dependencies.idpackage = (?) AND
            dependencies.iddependency =
            dependenciesreference.iddependency %s %s""" % (
                depstring, excluded_deptypes_query,), searchdata)
            return cur.fetchall()
        else:
            cur = self.cursor.execute("""
            SELECT dependenciesreference.dependency 
            FROM dependencies,dependenciesreference 
            WHERE dependencies.idpackage = (?) AND 
            dependencies.iddependency =
            dependenciesreference.iddependency %s %s""" % (
                depstring, excluded_deptypes_query,), searchdata)
            return self._cur2set(cur)

    def retrieveIdDependencies(self, idpackage):
        """
        Return list of dependency identifiers for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: list (set) of dependency identifiers
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT iddependency FROM dependencies WHERE idpackage = (?)
        """, (idpackage,))
        return self._cur2set(cur)

    def retrieveKeywords(self, idpackage):
        """
        Return package SPM keyword list for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: list (set) of keywords for given package identifier
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT keywordname FROM keywords,keywordsreference
        WHERE keywords.idpackage = (?) AND
        keywords.idkeyword = keywordsreference.idkeyword""", (idpackage,))
        return self._cur2set(cur)

    def retrieveProtect(self, idpackage):
        """
        Return CONFIG_PROTECT (configuration file protection) string
        (containing a list of space reparated paths) metadata for given
        package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: CONFIG_PROTECT string
        @rtype: string
        """
        cur = self.cursor.execute("""
        SELECT protect FROM configprotect,configprotectreference
        WHERE configprotect.idpackage = (?) AND
        configprotect.idprotect = configprotectreference.idprotect
        LIMIT 1
        """, (idpackage,))

        protect = cur.fetchone()
        if protect:
            return protect[0]
        return ''

    def retrieveProtectMask(self, idpackage):
        """
        Return CONFIG_PROTECT_MASK (mask for configuration file protection)
        string (containing a list of space reparated paths) metadata for given
        package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: CONFIG_PROTECT_MASK string
        @rtype: string
        """
        self.cursor.execute("""
        SELECT protect FROM configprotectmask,configprotectreference 
        WHERE idpackage = (?) AND 
        configprotectmask.idprotect = configprotectreference.idprotect
        """, (idpackage,))

        protect = self.cursor.fetchone()
        if protect:
            return protect[0]
        return ''

    def retrieveSources(self, idpackage, extended = False):
        """
        Return source package URLs for given package identifier.
        "source" as in source code.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword extended: 
        @type extended: bool
        @return: if extended is True, dict composed by source URLs as key
            and list of mirrors as value, otherwise just a list (set) of
            source package URLs.
        @rtype: dict or set
        """
        cur = self.cursor.execute("""
        SELECT sourcesreference.source FROM sources, sourcesreference
        WHERE idpackage = (?) AND
        sources.idsource = sourcesreference.idsource
        """, (idpackage,))
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
                        self.retrieveMirrorInfo(mirrorname)])

            else:
                source_data[source].add(source)

        return source_data

    def retrieveAutomergefiles(self, idpackage, get_dict = False):
        """
        Return previously merged protected configuration files list and
        their md5 hashes for given package identifier.
        This is part of the "automerge" feature which uses file md5 checksum
        to determine if a protected configuration file can be merged auto-
        matically.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword get_dict: return a dictionary with configuration file as key
            and md5 hash as value
        @type get_dict: bool
        @return: automerge metadata for given package identifier
        @rtype: list or set
        """
        # FIXME backward compatibility
        if not self._doesTableExist('automergefiles'):
            self._createAutomergefilesTable()

        # like portage does
        self.connection.text_factory = lambda x: const_convert_to_unicode(x)

        cur = self.cursor.execute("""
        SELECT configfile, md5 FROM automergefiles WHERE idpackage = (?)
        """, (idpackage,))
        data = cur.fetchall()

        if get_dict:
            data = dict(((x, y,) for x, y in data))
        return data

    def retrieveContent(self, idpackage, extended = False, contentType = None,
        formatted = False, insert_formatted = False, order_by = ''):
        """
        Return files contained in given package.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword extended: return in extended format
        @type extended: bool
        @keyword contentType: only return given entry type, which can be:
            "obj", "sym" or "dir"
        @type contentType: int
        @keyword formatted: return in dict() form
        @type formatted: bool
        @keyword insert_formatted: return in list of tuples form, ready to
            be added with insertContent()
        @keyword order_by: order by string, valid values are:
            "type" (if extended is True), "file" or "idpackage"
        @type order_by: string
        @return: content metadata
        @rtype: dict or list or set
        """
        extstring = ''
        if extended:
            extstring = ",type"
        extstring_idpackage = ''
        if insert_formatted:
            extstring_idpackage = 'idpackage,'

        searchkeywords = [idpackage]
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

                cur = self.cursor.execute("""
                SELECT %s file%s FROM content WHERE idpackage = (?) %s%s""" % (
                    extstring_idpackage, extstring,
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

            except self.dbapi2.OperationalError:

                if did_try:
                    raise
                did_try = True

                # FIXME support for old entropy db entries, which were
                # not inserted in utf-8
                self.connection.text_factory = lambda x: \
                    const_convert_to_unicode(x)
                continue

        return fl

    def retrieveChangelog(self, idpackage):
        """
        Return Source Package Manager ChangeLog for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: ChangeLog content
        @rtype: string or None
        """
        # FIXME backward compatibility
        if not self._doesTableExist('packagechangelogs'):
            return None

        cur = self.cursor.execute("""
        SELECT packagechangelogs.changelog
        FROM packagechangelogs, baseinfo, categories
        WHERE baseinfo.idpackage = (?) AND
        baseinfo.idcategory = categories.idcategory AND
        packagechangelogs.name = baseinfo.name AND
        packagechangelogs.category = categories.category
        LIMIT 1
        """, (idpackage,))
        changelog = cur.fetchone()
        if changelog:
            changelog = changelog[0]
            try:
                return const_convert_to_unicode(changelog)
            except UnicodeDecodeError:
                return const_convert_to_unicode(changelog, enctype = 'utf-8')

    def retrieveChangelogByKey(self, category, name):
        """
        Return Source Package Manager ChangeLog content for given package
        category and name.

        @param category: package category
        @type category: string
        @param name: package name
        @type name: string
        @return: ChangeLog content
        @rtype: string or None
        """
        # FIXME backward compatibility
        if not self._doesTableExist('packagechangelogs'):
            return None

        self.connection.text_factory = lambda x: const_convert_to_unicode(x)

        cur = self.cursor.execute("""
        SELECT changelog FROM packagechangelogs WHERE category = (?) AND
        name = (?) LIMIT 1
        """, (category, name,))

        changelog = cur.fetchone()
        if changelog:
            return const_convert_to_unicode(changelog[0])

    def retrieveSlot(self, idpackage):
        """
        Return "slot" metadatum for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: package slot
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT slot FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        slot = cur.fetchone()
        if slot:
            return slot[0]

    def retrieveVersionTag(self, idpackage):
        """
        Return "tag" metadatum for given package identifier.
        Tagging packages allows, for example, to support multiple
        different, colliding atoms in the same repository and still being
        able to exactly reference them. It's actually used to provide
        versions of external kernel modules for different kernels.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: tag string
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT versiontag FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        vtag = cur.fetchone()
        if vtag:
            return vtag[0]

    def retrieveMirrorInfo(self, mirrorname):
        """
        Return available mirror URls for given mirror name.

        @param mirrorname: mirror name (for eg. "openoffice")
        @type mirrorname: string
        @return: list (set) of URLs providing the "openoffice" mirroring service
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT mirrorlink FROM mirrorlinks WHERE mirrorname = (?)
        """, (mirrorname,))
        return self._cur2set(cur)

    def retrieveCategory(self, idpackage):
        """
        Return category name for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: category where package is in
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT category FROM baseinfo,categories
        WHERE baseinfo.idpackage = (?) AND
        baseinfo.idcategory = categories.idcategory LIMIT 1
        """, (idpackage,))

        cat = cur.fetchone()
        if cat:
            return cat[0]

    def retrieveCategoryDescription(self, category):
        """
        Return description text for given category.

        @param category: category name
        @type category: string
        @return: category description dict, locale as key, description as value
        @rtype: dict
        """
        cur = self.cursor.execute("""
        SELECT description, locale FROM categoriesdescription
        WHERE category = (?)
        """, (category,))

        return dict((locale, desc,) for desc, locale in cur.fetchall())

    def retrieveLicensedata(self, idpackage):
        """
        Return license metadata for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: dictionary composed by license name as key and license text
            as value
        @rtype: dict
        """

        licenses = self.retrieveLicense(idpackage)
        if licenses is None:
            return {}

        licdata = {}
        for licname in licenses.split():

            if not licname.strip():
                continue

            if not self.entropyTools.is_valid_string(licname):
                continue

            cur = self.cursor.execute("""
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

    def retrieveLicensedataKeys(self, idpackage):
        """
        Return license names available for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: list (set) of license names which text is available in
            repository
        @rtype: set
        """

        licenses = self.retrieveLicense(idpackage)
        if licenses is None:
            return set()

        licdata = set()
        for licname in licenses.split():

            if not licname.strip():
                continue

            if not self.entropyTools.is_valid_string(licname):
                continue

            cur = self.cursor.execute("""
            SELECT licensename FROM licensedata WHERE licensename = (?) LIMIT 1
            """, (licname,))
            lic_id = cur.fetchone()
            if lic_id:
                licdata.add(lic_id[0])

        return licdata

    def retrieveLicenseText(self, license_name):
        """
        Return license text for given license name.

        @param license_name: license name (for eg. GPL-2)
        @type license_name: string
        @return: license text
        @rtype: string (raw format) or None
        """

        self.connection.text_factory = lambda x: const_convert_to_unicode(x)

        cur = self.cursor.execute("""
        SELECT text FROM licensedata WHERE licensename = (?) LIMIT 1
        """, (license_name,))

        text = cur.fetchone()
        if text:
            return const_convert_to_rawstring(text[0])

    def retrieveLicense(self, idpackage):
        """
        Return "license" metadatum for given package identifier.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: license string
        @rtype: string or None
        """
        cur = self.cursor.execute("""
        SELECT license FROM baseinfo,licenses 
        WHERE baseinfo.idpackage = (?) AND 
        baseinfo.idlicense = licenses.idlicense LIMIT 1
        """, (idpackage,))

        licname = cur.fetchone()
        if licname:
            return licname[0]

    def retrieveCompileFlags(self, idpackage):
        """
        Return Compiler flags during building of package.
            (CHOST, CXXFLAGS, LDFLAGS)

        @param idpackage: package indentifier
        @type idpackage: int
        @return: tuple of length 3 composed by (CHOST, CFLAGS, CXXFLAGS)
        @rtype: tuple
        """
        self.cursor.execute("""
        SELECT chost,cflags,cxxflags FROM flags,extrainfo 
        WHERE extrainfo.idpackage = (?) AND 
        extrainfo.idflags = flags.idflags""", (idpackage,))
        flags = self.cursor.fetchone()
        if not flags:
            flags = ("N/A", "N/A", "N/A",)
        return flags

    def retrieveReverseDependencies(self, idpackage, atoms = False,
        key_slot = False, exclude_deptypes = None):
        """
        Return reverse (or inverse) dependencies for given package.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword atoms: if True, method returns list of atoms
        @type atoms: bool
        @keyword key_slot: if True, method returns list of dependencies in
            key:slot form, example: [('app-foo/bar','2',), ...]
        @type key_slot: bool
        @keyword exclude_deptypes: exclude given dependency types from returned
            data
        @type exclude_deptypes: iterable
        @return: reverse dependency list
        @rtype: list or set

        """

        # WARNING: never remove this, otherwise equo.db
        # (client database) dependstable will be always broken (trust me)
        # sanity check on the table
        c_tup = ("retrieveReverseDependencies_check",)
        if not self.live_cache.get(c_tup):
            self.live_cache[c_tup] = True
            if not self._isDependsTableSane(): # is empty, need generation
                self.generateReverseDependenciesMetadata(verbose = False)

        excluded_deptypes_query = ""
        if exclude_deptypes is not None:
            for dep_type in exclude_deptypes:
                excluded_deptypes_query += " AND dependencies.type != %s" % (
                    dep_type,)

        if atoms:
            cur = self.cursor.execute("""
            SELECT baseinfo.atom FROM dependstable,dependencies,baseinfo 
            WHERE dependstable.idpackage = (?) AND 
            dependstable.iddependency = dependencies.iddependency AND 
            baseinfo.idpackage = dependencies.idpackage %s""" % (
                excluded_deptypes_query,), (idpackage,))
            result = self._cur2set(cur)
        elif key_slot:
            cur = self.cursor.execute("""
            SELECT categories.category || "/" || baseinfo.name,baseinfo.slot 
            FROM baseinfo,categories,dependstable,dependencies 
            WHERE dependstable.idpackage = (?) AND 
            dependstable.iddependency = dependencies.iddependency AND 
            baseinfo.idpackage = dependencies.idpackage AND 
            categories.idcategory = baseinfo.idcategory %s""" % (
                excluded_deptypes_query,), (idpackage,))
            result = cur.fetchall()
        else:
            cur = self.cursor.execute("""
            SELECT dependencies.idpackage FROM dependstable,dependencies 
            WHERE dependstable.idpackage = (?) AND 
            dependstable.iddependency = dependencies.iddependency %s""" % (
                excluded_deptypes_query,), (idpackage,))
            result = self._cur2set(cur)

        return result

    def retrieveUnusedIdpackages(self):
        """
        Return packages (through their identifiers) not referenced by any
        other as dependency (unused packages).

        @return: unused idpackages ordered by atom
        @rtype: list
        """

        # WARNING: never remove this, otherwise equo.db (client database)
        # dependstable will be always broken (trust me)
        # sanity check on the table
        c_tup = ("retrieveUnusedIdpackages_check",)
        if not self.live_cache.get(c_tup):
            self.live_cache[c_tup] = True
            if not self._isDependsTableSane(): # is empty, need generation
                self.generateReverseDependenciesMetadata(verbose = False)

        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo 
        WHERE idpackage NOT IN (SELECT idpackage FROM dependstable)
        ORDER BY atom
        """)
        return self._cur2list(cur)

    def isAtomAvailable(self, atom):
        """
        Return whether given atom is available in repository.

        @param atom: package atom
        @type atom: string
        @return: idpackage or -1 if not found
        @rtype: int
        """
        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo WHERE atom = (?) LIMIT 1
        """, (atom,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def areIdpackagesAvailable(self, idpackages):
        """
        Return whether list of package identifiers are available.
        They must be all available to return True

        @param idpackages: list of package indentifiers
        @type idpackages: iterable
        @return: availability (True if all are available)
        @rtype: bool
        """
        sql = """SELECT count(idpackage) FROM baseinfo
        WHERE idpackage IN (%s)""" % (','.join(
            [str(x) for x in set(idpackages)]),
        )
        cur = self.cursor.execute(sql)
        count = cur.fetchone()[0]
        if count != len(idpackages):
            return False
        return True

    def isIdpackageAvailable(self, idpackage):
        """
        Return whether given package identifier is available in repository.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: availability (True if available)
        @rtype: bool
        """
        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        result = cur.fetchone()
        if not result:
            return False
        return True

    def isCategoryAvailable(self, category):
        """
        Return whether given category is available in repository.

        @param category: category name
        @type category: string
        @return: availability (True if available)
        @rtype: bool
        """
        cur = self.cursor.execute("""
        SELECT idcategory FROM categories WHERE category = (?) LIMIT 1
        """, (category,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def isProtectAvailable(self, protect):
        """
        Return whether given CONFIG_PROTECT* entry is available in repository.

        @param protect: CONFIG_PROTECT* entry (path to a protected directory
            or file that won't be overwritten by Entropy Client during
            package merge)
        @type protect: string
        @return: availability (True if available)
        @rtype: bool
        """
        cur = self.cursor.execute("""
        SELECT idprotect FROM configprotectreference WHERE protect = (?)
        LIMIT 1
        """, (protect,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def isFileAvailable(self, myfile, get_id = False):
        """
        Return whether given file path is available in repository (owned by
        one or more packages).

        @param myfile: path to file or directory
        @type myfile: string
        @keyword get_id: return list (set) of idpackages owning myfile
        @type get_id: bool
        @return: availability (True if available), when get_id is True,
            it returns a list (set) of idpackages owning myfile
        @rtype: bool or set
        """
        cur = self.cursor.execute("""
        SELECT idpackage FROM content WHERE file = (?)""", (myfile,))
        result = cur.fetchall()
        if get_id:
            return self._fetchall2set(result)
        elif result:
            return True
        return False

    def resolveNeeded(self, needed, elfclass = -1, extended = False):
        """
        Resolve NEEDED ELF entry (a library name) to idpackages owning given
        needed (stressing, needed = library name)

        @param needed: library name
        @type needed: string
        @keyword elfclass: look for library name matching given ELF class
        @type elfclass: int
        @keyword extended: return a list of tuple of length 2, first element
            is idpackage, second is actual library path
        @type extended: bool
        @return: list of packages owning given library
        @rtype: list or set
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
            cur = self.cursor.execute("""
            SELECT idpackage, path FROM provided_libs
            WHERE library = (?)""" + elfclass_txt, args)
            return cur.fetchall()

        cur = self.cursor.execute("""
        SELECT idpackage FROM provided_libs
        WHERE library = (?)""" + elfclass_txt, args)
        return self._cur2set(cur)

    def isSourceAvailable(self, source):
        """
        Return whether given source package URL is available in repository.
        Returns source package URL identifier (idsource).

        @param source: source package URL
        @type source: string
        @return: source package URL identifier (idsource) or -1 if not found
        @rtype: int

        """
        cur = self.cursor.execute("""
        SELECT idsource FROM sourcesreference WHERE source = (?) LIMIT 1
        """, (source,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def isDependencyAvailable(self, dependency):
        """
        Return whether given dependency string is available in repository.
        Returns dependency identifier (iddependency).

        @param dependency: dependency string
        @type dependency: string
        @return: dependency identifier (iddependency) or -1 if not found
        @rtype: int
        """
        cur = self.cursor.execute("""
        SELECT iddependency FROM dependenciesreference WHERE dependency = (?)
        LIMIT 1""", (dependency,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def isKeywordAvailable(self, keyword):
        """
        Return whether keyword string is available in repository.
        Returns keyword identifier (idkeyword)

        @param keyword: keyword string
        @type keyword: string
        @return: keyword identifier (idkeyword) or -1 if not found
        @rtype: int
        """
        cur = self.cursor.execute("""
        SELECT idkeyword FROM keywordsreference WHERE keywordname = (?) LIMIT 1
        """, (keyword,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def isUseflagAvailable(self, useflag):
        """
        Return whether USE flag name is available in repository.
        Returns USE flag identifier (idflag).

        @param useflag: USE flag name
        @type useflag: string
        @return: USE flag identifier or -1 if not found
        @rtype: int
        """
        cur = self.cursor.execute("""
        SELECT idflag FROM useflagsreference WHERE flagname = (?) LIMIT 1
        """, (useflag,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def isEclassAvailable(self, eclass):
        """
        Return whether eclass name is available in repository.
        Returns Eclass identifier (idclass)

        @param eclass: eclass name
        @type eclass: string
        @return: Eclass identifier or -1 if not found
        @rtype: int
        """
        cur = self.cursor.execute("""
        SELECT idclass FROM eclassesreference WHERE classname = (?) LIMIT 1
        """, (eclass,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def isNeededAvailable(self, needed):
        """
        Return whether NEEDED ELF entry (library name) is available in
        repository.
        Returns NEEDED entry identifier

        @param needed: NEEDED ELF entry (library name)
        @type needed: string
        @return: NEEDED entry identifier or -1 if not found
        @rtype: int
        """
        cur = self.cursor.execute("""
        SELECT idneeded FROM neededreference WHERE library = (?) LIMIT 1
        """, (needed,))
        result = cur.fetchone()
        if result:
            return result[0]
        return -1

    def isSpmUidAvailable(self, spm_uid):
        """
        Return whether Source Package Manager package identifier is available
        in repository.

        @param spm_uid: Source Package Manager package identifier
        @type spm_uid: int
        @return: availability (True, if available)
        @rtype: bool
        """
        cur = self.cursor.execute("""
        SELECT counter FROM counters WHERE counter = (?) LIMIT 1
        """, (spm_uid,))
        result = cur.fetchone()
        if result:
            return True
        return False

    def isSpmUidTrashed(self, spm_uid):
        """
        Return whether Source Package Manager package identifier has been
        trashed. One is trashed when it gets removed from a repository while
        still sitting there in place on live system. This is a trick to allow
        multiple-repositories management to work fine when shitting around.

        @param spm_uid: Source Package Manager package identifier
        @type spm_uid: int
        @return: availability (True, if available)
        @rtype: bool
        """
        cur = self.cursor.execute("""
        SELECT counter FROM trashedcounters WHERE counter = (?) LIMIT 1
        """, (spm_uid,))
        result = cur.fetchone()
        if result:
            return True
        return False

    def isLicensedataKeyAvailable(self, license_name):
        """
        Return whether license name is available in License database, which is
        the one containing actual license texts.

        @param license_name: license name which license text is available
        @type license_name: string
        @return: availability (True, if available)
        @rtype: bool
        """
        cur = self.cursor.execute("""
        SELECT licensename FROM licensedata WHERE licensename = (?) LIMIT 1
        """, (license_name,))
        result = cur.fetchone()
        if not result:
            return False
        return True

    def isLicenseAccepted(self, license_name):
        """
        Return whether given license (through its name) has been accepted by
        user.

        @param license_name: license name
        @type license_name: string
        @return: if license name has been accepted by user
        @rtype: bool
        """
        cur = self.cursor.execute("""
        SELECT licensename FROM licenses_accepted WHERE licensename = (?)
        LIMIT 1
        """, (license_name,))
        result = cur.fetchone()
        if not result:
            return False
        return True

    def acceptLicense(self, license_name):
        """
        Mark license name as accepted by user.
        Only and only if user is allowed to accept them:
            - in entropy group
            - db not open in read only mode

        @param license_name: license name
        @type license_name: string
        @todo: check if readOnly is really required
        @todo: check if is_user_in_entropy_group is really required
        """
        if self.readOnly:
            return
        if not self.entropyTools.is_user_in_entropy_group():
            return

        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.accept_license_hook(self)
            if exec_rc:
                raise RepositoryPluginError(
                    "[accept_license_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

        with self.__write_mutex:
            self.cursor.execute("""
            INSERT OR IGNORE INTO licenses_accepted VALUES (?)
            """, (license_name,))
            self.commitChanges()

    def isLicenseAvailable(self, pkglicense):
        """
        Return whether license metdatatum (NOT license name) is available
        in repository.

        @param pkglicense: "license" package metadatum (returned by
            retrieveLicense)
        @type pkglicense: string
        @return: "license" metadatum identifier (idlicense)
        @rtype: int
        """
        if not self.entropyTools.is_valid_string(pkglicense):
            pkglicense = ' '

        cur = self.cursor.execute("""
        SELECT idlicense FROM licenses WHERE license = (?) LIMIT 1
        """, (pkglicense,))
        result = cur.fetchone()

        if result:
            return result[0]
        return -1

    def isSystemPackage(self, idpackage):
        """
        Return whether package is part of core system (though, a system
        package).

        @param idpackage: package indentifier
        @type idpackage: int
        @return: if True, package is part of core system
        @rtype: bool
        """
        cur = self.cursor.execute("""
        SELECT idpackage FROM systempackages WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        result = cur.fetchone()
        if result:
            return True
        return False

    def isInjected(self, idpackage):
        """
        Return whether package has been injected into repository (means that
        will be never ever removed due to colliding scope when other
        packages will be added).

        @param idpackage: package indentifier
        @type idpackage: int
        @return: injection status (True if injected)
        @rtype: bool
        """
        cur = self.cursor.execute("""
        SELECT idpackage FROM injected WHERE idpackage = (?) LIMIT 1
        """, (idpackage,))
        result = cur.fetchone()
        if result:
            return True
        return False

    def areCompileFlagsAvailable(self, chost, cflags, cxxflags):
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
        cur = self.cursor.execute("""
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
        Search packages which given file path belongs to.

        @param file: file path to search
        @type file: string
        @keyword like: do not match exact case
        @type like: bool
        @return: list (set) of package identifiers owning given file
        @rtype: set
        """
        if like:
            cur = self.cursor.execute("""
            SELECT content.idpackage FROM content,baseinfo
            WHERE file LIKE (?) AND
            content.idpackage = baseinfo.idpackage""", (file,))
        else:
            cur = self.cursor.execute("""SELECT content.idpackage
            FROM content, baseinfo WHERE file = (?)
            AND content.idpackage = baseinfo.idpackage""", (file,))

        return self._cur2set(cur)

    def searchEclassedPackages(self, eclass, atoms = False): # atoms = return atoms directly
        """
        Search packages which their Source Package Manager counterpar are using
        given eclass.

        @param eclass: eclass name to search
        @type eclass: string
        @keyword atoms: return list of atoms instead of package identifiers
        @type atoms: bool
        @return: list of packages using given eclass
        @rtype: set or list
        """
        if atoms:
            cur = self.cursor.execute("""
            SELECT baseinfo.atom,eclasses.idpackage
            FROM baseinfo, eclasses, eclassesreference
            WHERE eclassesreference.classname = (?) AND
            eclassesreference.idclass = eclasses.idclass AND
            eclasses.idpackage = baseinfo.idpackage""", (eclass,))
            return cur.fetchall()

        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo WHERE versiontag = (?)""", (eclass,))
        return self._cur2set(cur)

    def searchTaggedPackages(self, tag, atoms = False):
        """
        Search packages which "tag" metadatum matches the given one.

        @param tag: tag name to search
        @type tag: string
        @keyword atoms: return list of atoms instead of package identifiers
        @type atoms: bool
        @return: list of packages using given tag
        @rtype: set or list
        """
        if atoms:
            cur = self.cursor.execute("""
            SELECT atom, idpackage FROM baseinfo WHERE versiontag = (?)
            """, (tag,))
            return cur.fetchall()

        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo WHERE versiontag = (?)
        """, (tag,))
        return self._cur2set(cur)

    def searchLicenses(self, mylicense, caseSensitive = False, atoms = False):
        """
        Search packages using given license (mylicense).

        @param mylicense: license name to search
        @type mylicense: string
        @keyword caseSensitive: search in case sensitive mode (default off)
        @type caseSensitive: bool
        @keyword atoms: return list of atoms instead of package identifiers
        @type atoms: bool
        @return: list of packages using given license
        @rtype: set or list
        @todo: check if is_valid_string is really required
        """
        if not self.entropyTools.is_valid_string(mylicense):
            return []

        request = "baseinfo.idpackage"
        if atoms:
            request = "baseinfo.atom,baseinfo.idpackage"

        if caseSensitive:
            cur = self.cursor.execute("""
            SELECT %s FROM baseinfo,licenses
            WHERE licenses.license LIKE (?) AND
            licenses.idlicense = baseinfo.idlicense
            """ % (request,), ("%"+mylicense+"%",))
        else:
            cur = self.cursor.execute("""
            SELECT %s FROM baseinfo,licenses
            WHERE LOWER(licenses.license) LIKE (?) AND
            licenses.idlicense = baseinfo.idlicense
            """ % (request,), ("%"+mylicense+"%".lower(),))

        if atoms:
            return cur.fetchall()
        return self._cur2set(cur)

    def searchSlottedPackages(self, slot, atoms = False):
        """
        Search packages with given slot string.

        @param slot: slot to search
        @type slot: string
        @keyword atoms: return list of atoms instead of package identifiers
        @type atoms: bool
        @return: list of packages using given slot
        @rtype: set or list
        """
        if atoms:
            cur = self.cursor.execute("""
            SELECT atom,idpackage FROM baseinfo WHERE slot = (?)
            """, (slot,))
            return cur.fetchall()

        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo WHERE slot = (?)""", (slot,))
        return self._cur2set(cur)

    def searchKeySlot(self, key, slot):
        """
        Search package with given key and slot

        @param key: package key
        @type key: string
        @param slot: package slot
        @type slot: string
        @return: list (set) of package identifiers
        @rtype: set
        """
        cat, name = key.split("/")
        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo, categories
        WHERE baseinfo.idcategory = categories.idcategory AND
        categories.category = (?) AND
        baseinfo.name = (?) AND
        baseinfo.slot = (?)""", (cat, name, slot,))

        return cur.fetchall()

    def searchNeeded(self, needed, elfclass = -1, like = False):
        """
        Search packages that need given NEEDED ELF entry (library name).

        @param needed: NEEDED ELF entry (shared object library name)
        @type needed: string
        @param elfclass: search NEEDEDs only with given ELF class
        @type elfclass: int
        @keyword like: do not match exact case
        @type like: bool
        @return: list (set) of package identifiers
        @rtype: set
        """
        elfsearch = ''
        search_args = (needed,)
        if elfclass != -1:
            elfsearch = ' AND needed.elfclass = (?)'
            search_args = (needed, elfclass,)

        if like:
            cur = self.cursor.execute("""
            SELECT needed.idpackage FROM needed,neededreference
            WHERE library LIKE (?) %s AND
            needed.idneeded = neededreference.idneeded
            """ % (elfsearch,), search_args)
        else:
            cur = self.cursor.execute("""
            SELECT needed.idpackage FROM needed,neededreference
            WHERE library = (?) %s AND
            needed.idneeded = neededreference.idneeded
            """ % (elfsearch,), search_args)

        return self._cur2set(cur)

    def searchDependency(self, dep, like = False, multi = False,
        strings = False):
        """
        Search dependency name in repository.
        Returns dependency identifier (iddependency) or dependency strings
        (if strings argument is True).

        @param dep: dependency name
        @type dep: string
        @keyword like: do not match exact case
        @type like: bool
        @keyword multi: return all the matching dependency names
        @type multi: bool
        @keyword strings: return dependency names rather than dependency
            identifiers
        @type strings: bool
        @return: list of dependency identifiers (if multi is True) or
            strings (if strings is True) or dependency identifier
        @rtype: int or set
        """
        sign = "="
        if like:
            sign = "LIKE"
            dep = "%"+dep+"%"
        item = 'iddependency'
        if strings:
            item = 'dependency'

        cur = self.cursor.execute("""
        SELECT %s FROM dependenciesreference WHERE dependency %s (?)
        """ % (item, sign,), (dep,))

        if multi:
            return self._cur2set(cur)
        iddep = cur.fetchone()

        if iddep:
            return iddep[0]
        return -1

    def searchIdpackageFromIddependency(self, iddep):
        """
        Search package identifiers owning dependency given (in form of
        dependency identifier).

        @param iddep: dependency identifier
        @type iddep: int
        @return: list (set) of package identifiers owning given dependency
            identifier
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT idpackage FROM dependencies WHERE iddependency = (?)
        """, (iddep,))
        return self._cur2set(cur)

    def searchSets(self, keyword):
        """
        Search package sets in repository using given search keyword.

        @param keyword: package set name to search
        @type keyword: string
        @return: list (set) of package sets available matching given keyword
        @rtype: set

        """
        cur = self.cursor.execute("""
        SELECT DISTINCT(setname) FROM packagesets WHERE setname LIKE (?)
        """, ("%"+keyword+"%",))

        return self._cur2set(cur)

    def searchSimilarPackages(self, mystring, atom = False):
        """
        Search similar packages (basing on package string given by mystring
        argument) using SOUNDEX algorithm (ahhh Google...).

        @param mystring: package string to search
        @type mystring: string
        @keyword atom: return full atoms instead of package names
        @type atom: bool
        @return: list of similar package names
        @rtype: set
        """
        s_item = 'name'
        if atom:
            s_item = 'atom'
        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo 
        WHERE soundex(%s) = soundex((?)) ORDER BY %s
        """ % (s_item, s_item,), (mystring,))

        return self._cur2list(cur)

    def searchPackages(self, keyword, sensitive = False, slot = None,
            tag = None, order_by = 'atom', just_id = False):
        """
        Search packages using given package name "keyword" argument.

        @param keyword: package string
        @type keyword: string
        @keyword sensitive: case sensitive?
        @type sensitive: bool
        @keyword slot: search matching given slot
        @type slot: string
        @keyword tag: search matching given package tag
        @type tag: string
        @keyword order_by: order results by "atom", "name" or "version"
        @type order_by: string
        @keyword just_id: just return package identifiers (returning set())
        @type just_id: bool
        @return: packages found matching given search criterias
        @rtype: set or list
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
            cur = self.cursor.execute("""
            SELECT %s FROM baseinfo WHERE atom LIKE (?) %s %s %s""" %  (
                search_elements, slotstring, tagstring, order_by_string,),
                searchkeywords
            )
        else:
            cur = self.cursor.execute("""
            SELECT %s FROM baseinfo WHERE 
            LOWER(atom) LIKE (?) %s %s %s""" % (
                search_elements, slotstring, tagstring, order_by_string,),
                searchkeywords
            )

        if just_id:
            return self._cur2list(cur)
        return cur.fetchall()

    def searchProvide(self, keyword, slot = None, tag = None, justid = False,
        get_extended = False):
        """
        Search in old-style Portage PROVIDE metadata.
        WARNING: this method is deprecated and will be removed someday.

        @param keyword: search term
        @type keyword: string
        @keyword slot: match given package slot
        @type slot: string
        @keyword tag: match given package tag
        @type tag: string
        @keyword justid: return list of package identifiers (set())
        @type justid: bool
        @keyword get_extended: return data in extended format
        @type get_extended: bool
        @return: found PROVIDE metadata
        @rtype: list or set
        """
        searchkeywords = [keyword]

        slotstring = ''
        if slot:
            searchkeywords.append(slot)
            slotstring = ' and baseinfo.slot = (?)'

        tagstring = ''
        if tag:
            searchkeywords.append(tag)
            tagstring = ' and baseinfo.versiontag = (?)'

        atomstring = ''
        if not justid:
            atomstring = 'baseinfo.atom,'

        get_def_string = ''
        if get_extended:
            # FIXME: this small snipped is here for backward compat
            if self._doesColumnInTableExist("provide", "is_default"):
                get_def_string = ",provide.is_default"
            else:
                get_def_string = ",0"

        cur = self.cursor.execute("""
        SELECT %s baseinfo.idpackage%s FROM baseinfo,provide 
        WHERE provide.atom = (?) AND 
        provide.idpackage = baseinfo.idpackage %s %s""" % (
            atomstring, get_def_string, slotstring, tagstring,),
            searchkeywords
        )

        if justid and not get_extended:
            return self._cur2list(cur)
        return cur.fetchall()

    def searchPackagesByDescription(self, keyword):
        """
        Search packages using given description string as keyword.

        @param keyword: description sub-string to search
        @type keyword: string
        @return: list of tuples of length 2 containing atom and idpackage
            values
        @rtype: list
        """
        cur = self.cursor.execute("""
        SELECT baseinfo.atom, baseinfo.idpackage FROM extrainfo, baseinfo
        WHERE LOWER(extrainfo.description) LIKE (?) AND
        baseinfo.idpackage = extrainfo.idpackage
        """, ("%"+keyword.lower()+"%",))
        return cur.fetchall()

    def searchPackagesByName(self, keyword, sensitive = False, justid = False):
        """
        Search packages by package name.

        @param keyword: package name to search
        @type keyword: string
        @keyword sensitive: case sensitive?
        @type sensitive: bool
        @keyword justid: return list of package identifiers (set()) otherwise
            return a list of tuples of length 2 containing atom and idpackage
            values
        @type justid: bool
        @return: list of packages found
        @rtype: list or set
        """

        atomstring = ''
        if not justid:
            atomstring = 'atom,'

        if sensitive:
            cur = self.cursor.execute("""
            SELECT %s idpackage FROM baseinfo
            WHERE name = (?)
            """ % (atomstring,), (keyword,))
        else:
            cur = self.cursor.execute("""
            SELECT %s idpackage FROM baseinfo
            WHERE LOWER(name) = (?)
            """ % (atomstring,), (keyword.lower(),))

        if justid:
            return self._cur2list(cur)
        return cur.fetchall()


    def searchPackagesByCategory(self, keyword, like = False, branch = None):
        """
        Search packages by category name.

        @param keyword: category name
        @type keyword: string
        @keyword like: do not match exact case
        @type like: bool
        @keyword branch: search in given package branch
        @type branch: string
        @return: list of tuples of length 2 containing atom and idpackage
            values
        @rtype: list
        """
        searchkeywords = [keyword]
        branchstring = ''
        if branch:
            searchkeywords.append(branch)
            branchstring = 'and branch = (?)'

        if like:
            cur = self.cursor.execute("""
            SELECT baseinfo.atom,baseinfo.idpackage FROM baseinfo,categories
            WHERE categories.category LIKE (?) AND
            baseinfo.idcategory = categories.idcategory %s
            """ % (branchstring,), searchkeywords)
        else:
            cur = self.cursor.execute("""
            SELECT baseinfo.atom,baseinfo.idpackage FROM baseinfo,categories
            WHERE categories.category = (?) AND
            baseinfo.idcategory = categories.idcategory %s
            """ % (branchstring,), searchkeywords)

        return cur.fetchall()

    def searchPackagesByNameAndCategory(self, name, category, sensitive = False,
        justid = False):
        """
        Search packages matching given name and category strings.

        @param name: package name to search
        @type name: string
        @param category: package category to search
        @type category: string
        @keyword sensitive: case sensitive?
        @type sensitive: bool
        @keyword justid: return list of package identifiers (set()) otherwise
            return a list of tuples of length 2 containing atom and idpackage
            values
        @type justid: bool
        @return: list of packages found
        @rtype: list or set
        """

        atomstring = ''
        if not justid:
            atomstring = 'atom,'

        if sensitive:
            cur = self.cursor.execute("""
            SELECT %s idpackage FROM baseinfo
            WHERE name = (?) AND
            idcategory IN (
                SELECT idcategory FROM categories
                WHERE category = (?)
            )""" % (atomstring,), (name, category,))
        else:
            cur = self.cursor.execute("""
            SELECT %s idpackage FROM baseinfo
            WHERE LOWER(name) = (?) AND
            idcategory IN (
                SELECT idcategory FROM categories
                WHERE LOWER(category) = (?)
            )""" % (atomstring,), (name.lower(), category.lower(),))

        if justid:
            return self._cur2list(cur)
        return cur.fetchall()

    def isPackageScopeAvailable(self, atom, slot, revision):
        """
        Return whether given package scope is available.
        Also check if package found is masked and return masking reason
        identifier.

        @param atom: package atom string
        @type atom: string
        @param slot: package slot string
        @type slot: string
        @param revision: entropy package revision
        @type revision: int
        @return: tuple composed by (idpackage or -1, idreason or 0,)
        @rtype: tuple

        """
        searchdata = (atom, slot, revision,)
        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo
        where atom = (?)  AND slot = (?) AND revision = (?) LIMIT 1
        """, searchdata)
        rslt = cur.fetchone()

        if rslt: # check if it's masked
            return self.idpackageValidator(rslt[0])
        return -1, 0

    def isBranchMigrationAvailable(self, repository, from_branch, to_branch):
        """
        Returns whether branch migration metadata given by the provided key
        (repository, from_branch, to_branch,) is available.

        @param repository: repository identifier
        @type repository: string
        @param from_branch: original branch
        @type from_branch: string
        @param to_branch: destination branch
        @type to_branch: string
        @return: tuple composed by (1)post migration script md5sum and
            (2)post upgrade script md5sum
        @rtype: tuple
        """
        cur = self.cursor.execute("""
        SELECT post_migration_md5sum, post_upgrade_md5sum
        FROM entropy_branch_migration
        WHERE repository = (?) AND from_branch = (?) AND to_branch = (?)
        LIMIT 1
        """, (repository, from_branch, to_branch,))
        return cur.fetchone()

    def listAllPackages(self, get_scope = False, order_by = None):
        """
        List all packages in repository.

        @keyword get_scope: return also entropy package revision
        @type get_scope: bool
        @keyword order_by: order by given metadatum, "atom", "slot", "revision"
            or "idpackage"
        @type order_by: string
        @return: list of tuples of length 3 (or 4 if get_scope is True),
            containing (atom, idpackage, branch,) if get_scope is False and
            (idpackage, atom, slot, revision,) if get_scope is True
        @rtype: list
        """
        order_txt = ''
        if order_by:
            order_txt = ' ORDER BY %s' % (order_by,)

        if get_scope:
            cur = self.cursor.execute("""
            SELECT idpackage,atom,slot,revision FROM baseinfo""" + order_txt)
        else:
            cur = self.cursor.execute("""
            SELECT atom,idpackage,branch FROM baseinfo""" + order_txt)

        return cur.fetchall()

    def listAllInjectedPackages(self, just_files = False):
        """
        List all the "injected" package download URLs in repository.

        @keyword just_files: just return download URLs
        @type just_files: bool
        @return: list (set) of download URLs (if just_files) otherwise list
            of tuples of length 2 composed by (download URL, idpackage,)
        @rtype: set
        """
        cur = self.cursor.execute('SELECT idpackage FROM injected')
        injecteds = self._cur2set(cur)
        results = set()

        for injected in injecteds:
            download = self.retrieveDownloadURL(injected)
            if just_files:
                results.add(download)
            else:
                results.add((download, injected))

        return results

    def listAllSpmUids(self):
        """
        List all Source Package Manager unique package identifiers bindings
        with packages in repository.
        @return: list of tuples of length 2 composed by (spm_uid, idpackage,)
        @rtype: list
        """
        cur = self.cursor.execute('SELECT counter, idpackage FROM counters')
        return cur.fetchall()

    def listAllIdpackages(self, order_by = None):
        """
        List all package identifiers available in repository.

        @keyword order_by: order by "atom", "idpackage", "version", "name",
            "idcategory"
        @type order_by: string
        @return: list (if order_by) or set of package identifiers
        @rtype: list or set
        """
        orderbystring = ''
        if order_by:
            orderbystring = ' ORDER BY '+order_by

        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo""" + orderbystring)

        try:
            if order_by:
                return self._cur2list(cur)
            return self._cur2set(cur)
        except self.dbapi2.OperationalError:
            if order_by:
                return []
            return set()

    def listAllDependencies(self):
        """
        List all dependencies available in repository.

        @return: list of tuples of length 2 containing (iddependency, dependency
            name,)
        @rtype: list
        """
        cur = self.cursor.execute("""
        SELECT iddependency, dependency FROM dependenciesreference""")
        return cur.fetchall()

    def listIdPackagesInIdcategory(self, idcategory, order_by = 'atom'):
        """
        List package identifiers available in given category identifier.

        @param idcategory: cateogory identifier
        @type idcategory: int
        @keyword order_by: order by "atom", "name", "version"
        @type order_by: string
        @return: list (set) of available package identifiers in category.
        @rtype: set
        """
        order_by_string = ''
        if order_by in ("atom", "name", "version",):
            order_by_string = ' ORDER BY %s' % (order_by,)

        cur = self.cursor.execute("""
        SELECT idpackage FROM baseinfo where idcategory = (?)
        """ + order_by_string, (idcategory,))

        return self._cur2set(cur)

    def listAllDownloads(self, do_sort = True, full_path = False):
        """
        List all package download URLs stored in repository.

        @keyword do_sort: sort by name
        @type do_sort: bool
        @keyword full_path: return full URL (not just package file name)
        @type full_path: bool
        @return: list (or set if do_sort is True) of package download URLs
        @rtype: list or set
        """

        order_string = ''
        if do_sort:
            order_string = 'ORDER BY extrainfo.download'

        cur = self.cursor.execute("""
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

    def listAllFiles(self, clean = False, count = False):
        """
        List all file paths owned by packaged stored in repository.

        @keyword clean: return a clean list (not duplicates)
        @type clean: bool
        @keyword count: count elements and return number
        @type count: bool
        @return: list of files available or their count
        @rtype: int or list or set
        """
        self.connection.text_factory = lambda x: const_convert_to_unicode(x)

        if count:
            cur = self.cursor.execute('SELECT count(file) FROM content')
        else:
            cur = self.cursor.execute('SELECT file FROM content')

        if count:
            return cur.fetchone()[0]
        if clean:
            return self._cur2set(cur)
        return self._cur2list(cur)

    def listAllCategories(self, order_by = ''):
        """
        List all categories available in repository.

        @keyword order_by: order by "category", "idcategory"
        @type order_by: string
        @return: list of tuples of length 2 composed by (idcategory, category,)
        @rtype: list
        """
        order_by_string = ''
        if order_by: order_by_string = ' order by %s' % (order_by,)
        self.cursor.execute('SELECT idcategory,category FROM categories %s' % (
            order_by_string,))
        return self.cursor.fetchall()

    def listConfigProtectEntries(self, mask = False):
        """
        List CONFIG_PROTECT* entries (configuration file/directories
        protection).

        @keyword mask: return CONFIG_PROTECT_MASK metadata instead of
            CONFIG_PROTECT
        @type mask: bool
        @return: list of protected/masked directories
        @rtype: list
        """
        mask_t = ''
        if mask:
            mask_t = 'mask'
        cur = self.cursor.execute("""
        SELECT protect FROM configprotectreference WHERE idprotect IN
            (SELECT distinct(idprotect) FROM configprotect%s)
        ORDER BY protect""" % (mask_t,))

        results = self._cur2set(cur)
        dirs = set()
        for mystr in results:
            dirs.update(mystr.split())

        return sorted(dirs)

    def switchBranch(self, idpackage, tobranch):
        """
        Switch branch string in repository to new value.

        @param idpackage: package identifier
        @type idpackage: int
        @param tobranch: new branch value
        @type tobranch: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            UPDATE baseinfo SET branch = (?)
            WHERE idpackage = (?)""", (tobranch, idpackage,))
            self.commitChanges()
            self.clearCache()

    def getSetting(self, setting_name):
        """
        Return stored Repository setting.
        For currently supported setting_name values look at
        EntropyRepository.SETTING_KEYS.

        @param setting_name: name of repository setting
        @type setting_name: string
        @return: setting value
        @rtype: string
        @raise KeyError: if setting_name is not valid or available
        """
        if setting_name not in EntropyRepository.SETTING_KEYS:
            raise KeyError
        try:
            self.cursor.execute("""
            SELECT setting_value FROM settings WHERE setting_name = (?)
            """, (setting_name,))
        except self.dbapi2.Error:
            raise KeyError

        setting = self.cursor.fetchone()
        if setting is None:
            raise KeyError
        return setting[0]

    def _setupInitialSettings(self):
        """
        Setup initial repository settings
        """
        self.cursor.executescript("""
            INSERT OR REPLACE INTO settings VALUES ("arch", "%s");
            INSERT OR REPLACE INTO settings VALUES ("on_delete_cascade", "%s");
            """ % (etpConst['currentarch'], "1",)
        )

    def _databaseStructureUpdates(self):

        old_readonly = self.readOnly
        self.readOnly = False

        if not self._doesTableExist("licenses_accepted"):
            self._createLicensesAcceptedTable()

        if not self._doesColumnInTableExist("installedtable", "source"):
            self._createInstalledTableSource()

        if not self._doesColumnInTableExist("provide", "is_default"):
            self._createProvideDefault()

        if not self._doesTableExist('packagesets'):
            self._createPackagesetsTable()

        if not self._doesTableExist('packagechangelogs'):
            self._createPackagechangelogsTable()

        if not self._doesTableExist('automergefiles'):
            self._createAutomergefilesTable()

        if not self._doesTableExist('packagesignatures'):
            self._createPackagesignaturesTable()

        if not self._doesTableExist('packagespmphases'):
            self._createPackagespmphases()

        if not self._doesTableExist('packagespmrepository'):
            self._createPackagespmrepository()

        if not self._doesTableExist('entropy_branch_migration'):
            self._createEntropyBranchMigrationTable()

        if not self._doesTableExist('dependstable'):
            self._createDependsTable()

        if not self._doesTableExist('settings'):
            self._createSettingsTable()

        self._foreignKeySupport()

        self.readOnly = old_readonly
        self.connection.commit()

    def validateDatabase(self):
        """
        Validates Entropy repository by doing basic integrity checks.

        @raise SystemDatabaseError: when repository is not reliable
        """
        self.cursor.execute("""
        SELECT name FROM SQLITE_MASTER WHERE type = (?) AND name = (?)
        """, ("table", "baseinfo"))
        rslt = self.cursor.fetchone()
        if rslt is None:
            mytxt = _("baseinfo error. Either does not exist or corrupted.")
            raise SystemDatabaseError("SystemDatabaseError: %s" % (mytxt,))

        self.cursor.execute("""
        SELECT name FROM SQLITE_MASTER WHERE type = (?) AND name = (?)
        """, ("table", "extrainfo"))
        rslt = self.cursor.fetchone()
        if rslt is None:
            mytxt = _("extrainfo error. Either does not exist or corrupted.")
            raise SystemDatabaseError("SystemDatabaseError: %s" % (mytxt,))

    def getIdpackagesDifferences(self, foreign_idpackages):
        """
        Return differences between in-repository package identifiers and
        list provided.

        @param foreign_idpackages: list of foreign idpackages
        @type foreign_idpackages: iterable
        @return: tuple composed by idpackages that would be added and idpackages
            that would be removed
        @rtype: tuple
        """
        myids = self.listAllIdpackages()
        if isinstance(foreign_idpackages, (list, tuple)):
            outids = set(foreign_idpackages)
        else:
            outids = foreign_idpackages
        added_ids = outids - myids
        removed_ids = myids - outids
        return added_ids, removed_ids

    def uniformBranch(self, branch):
        """
        Enforce given branch string to all currently available packages.

        @param branch: branch string to enforce
        @type branch: string
        """
        with self.__write_mutex:
            self.cursor.execute('UPDATE baseinfo SET branch = (?)', (branch,))
            self.commitChanges()
            self.clearCache()

    def alignDatabases(self, dbconn, force = False, output_header = "  ",
        align_limit = 300):
        """
        Align packages contained in foreign repository "dbconn" and this
        instance.

        @param dbconn: foreign repository instance
        @type dbconn: entropy.db.EntropyRepository
        @keyword force: force alignment even if align_limit threshold is
            exceeded
        @type force: bool
        @keyword output_header: output header for printing purposes
        @type output_header: string
        @keyword align_limit: threshold within alignment is done if force is
            False
        @type align_limit: int
        @return: alignment status (0 = all good; 1 = dbs checksum not matching;
            -1 = nothing to do)
        @rtype: int
        """
        added_ids, removed_ids = self.getIdpackagesDifferences(
            dbconn.listAllIdpackages())

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
        self.updateProgress(
            mytxt,
            importance = 1,
            type = "info",
            header = output_header,
            back = True
        )

        maxcount = len(removed_ids)
        mycount = 0
        for idpackage in removed_ids:
            mycount += 1
            mytxt = "%s: %s" % (
                red(_("Removing entry")),
                blue(str(self.retrieveAtom(idpackage))),
            )
            self.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = output_header,
                back = True,
                count = (mycount, maxcount)
            )

            self.removePackage(idpackage, do_cleanup = False, do_commit = False)

        maxcount = len(added_ids)
        mycount = 0
        for idpackage in added_ids:
            mycount += 1
            mytxt = "%s: %s" % (
                red(_("Adding entry")),
                blue(str(dbconn.retrieveAtom(idpackage))),
            )
            self.updateProgress(
                mytxt,
                importance = 0,
                type = "info",
                header = output_header,
                back = True,
                count = (mycount, maxcount)
            )
            mydata = dbconn.getPackageData(idpackage, get_content = True,
                content_insert_formatted = True)
            self.addPackage(
                mydata,
                revision = mydata['revision'],
                idpackage = idpackage,
                do_commit = False,
                formatted_content = True
            )

        # do some cleanups
        self.doCleanups()
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
        """
        Check if repository EAPI (Entropy API) is not greater than the one
        that entropy.const ships.
        """

        dbapi = self.getApi()
        if int(dbapi) > int(etpConst['etpapi']):
            self.updateProgress(
                red(_("Repository EAPI > Entropy EAPI.")),
                importance = 1,
                type = "warning",
                header = " * ! * ! * ! * "
            )
            self.updateProgress(
                red(_("Please update Equo/Entropy as soon as possible !")),
                importance = 1,
                type = "warning",
                header = " * ! * ! * ! * "
            )

    def doDatabaseImport(self, dumpfile, dbfile):
        """
        Import SQLite3 dump file to this database.

        @param dumpfile: SQLite3 dump file to read
        @type dumpfile: string
        @param dbfile: database file to write to
        @type dbfile: string
        @return: sqlite3 import return code
        @rtype: int
        @todo: remove /usr/bin/sqlite3 dependency
        """
        import subprocess
        sqlite3_exec = "/usr/bin/sqlite3 %s < %s" % (dbfile, dumpfile,)
        retcode = subprocess.call(sqlite3_exec, shell = True)
        return retcode

    def doDatabaseExport(self, dumpfile, gentle_with_tables = True,
        exclude_tables = None):
        """
        Export running SQLite3 database to file.

        @param dumpfile: dump file object to write to
        @type dumpfile: file object (hint: open())
        @keyword gentle_with_tables: append "IF NOT EXISTS" to "CREATE TABLE"
            statements
        @type gentle_with_tables: bool
        @todo: when Python 2.6, look ad Connection.iterdump and replace this :)
        """
        if not exclude_tables:
            exclude_tables = []

        toraw = const_convert_to_rawstring

        dumpfile.write(toraw("BEGIN TRANSACTION;\n"))
        self.cursor.execute("""
        SELECT name, type, sql FROM sqlite_master
        WHERE sql NOT NULL AND type=='table'
        """)
        for name, x, sql in self.cursor.fetchall():

            self.updateProgress(
                red("%s " % (
                    _("Exporting database table"),
                ) ) + "["+blue(str(name))+"]",
                importance = 0,
                type = "info",
                back = True,
                header = "   "
            )

            if name == "sqlite_sequence":
                dumpfile.write(toraw("DELETE FROM sqlite_sequence;\n"))
            elif name == "sqlite_stat1":
                dumpfile.write(toraw("ANALYZE sqlite_master;\n"))
            elif name.startswith("sqlite_"):
                continue
            else:
                t_cmd = "CREATE TABLE"
                if sql.startswith(t_cmd) and gentle_with_tables:
                    sql = "CREATE TABLE IF NOT EXISTS"+sql[len(t_cmd):]
                dumpfile.write(toraw("%s;\n" % sql))

            if name in exclude_tables:
                continue

            self.cursor.execute("PRAGMA table_info('%s')" % name)
            cols = [r[1] for r in self.cursor.fetchall()]
            q = "SELECT 'INSERT INTO \"%(tbl_name)s\" VALUES("
            q += ", ".join(["'||quote(" + x + ")||'" for x in cols])
            q += ")' FROM '%(tbl_name)s'"
            self.cursor.execute(q % {'tbl_name': name})
            self.connection.text_factory = lambda x: \
                const_convert_to_unicode(x)
            for row in self.cursor:
                dumpfile.write(toraw("%s;\n" % (row[0],)))

        self.cursor.execute("""
        SELECT name, type, sql FROM sqlite_master
        WHERE sql NOT NULL AND type!='table' AND type!='meta'
        """)
        for name, x, sql in self.cursor.fetchall():
            dumpfile.write(toraw("%s;\n" % sql))

        dumpfile.write(toraw("COMMIT;\n"))
        try:
            dumpfile.flush()
        except:
            pass
        self.updateProgress(
            red(_("Database Export complete.")),
            importance = 0,
            type = "info",
            header = "   "
        )
        # remember to close the file

    def listAllTables(self):
        """
        List all available tables in this repository database.

        @return: available tables
        @rtype: list
        """
        cur = self.cursor.execute("""
        SELECT name FROM SQLITE_MASTER WHERE type = "table"
        """)
        return self._cur2list(cur)

    def _doesTableExist(self, table):

        # speed up a bit if we already reported a column as existing
        c_tup = ("_doesTableExist", table,)
        cached = self.live_cache.get(c_tup)
        if cached is not None:
            return cached

        cur = self.cursor.execute("""
        select name from SQLITE_MASTER where type = "table" and name = (?)
        LIMIT 1
        """, (table,))
        rslt = cur.fetchone()
        exists = rslt is not None
        if exists:
            self.live_cache[c_tup] = True
        return exists

    def _doesColumnInTableExist(self, table, column):

        # speed up a bit if we already reported a column as existing
        c_tup = ("_doesColumnInTableExist", table, column,)
        cached = self.live_cache.get(c_tup)
        if cached is not None:
            return cached

        cur = self.cursor.execute('PRAGMA table_info( %s )' % (table,))
        rslt = (x[1] for x in cur.fetchall())
        if column in rslt:
            self.live_cache[c_tup] = True
            return True
        return False

    def checksum(self, do_order = False, strict = True,
        strings = False):
        """
        Get Repository metadata checksum, useful for integrity verification.
        Note: result is cached in EntropyRepository.live_cache (dict).

        @keyword do_order: order metadata collection alphabetically
        @type do_order: bool
        @keyword strict: improve checksum accuracy
        @type strict: bool
        @keyword strings: return checksum in md5 hex form
        @type strings: bool
        @return: repository checksum
        @rtype: string
        """

        c_tup = ("checksum", do_order, strict, strings,)
        cache = self.live_cache.get(c_tup)
        if cache is not None:
            return cache

        idpackage_order = ''
        category_order = ''
        license_order = ''
        flags_order = ''
        if do_order:
            idpackage_order = 'order by idpackage'
            category_order = 'order by category'
            license_order = 'order by license'
            flags_order = 'order by chost'

        def do_update_md5(m, cursor):
            mydata = cursor.fetchall()
            for record in mydata:
                for item in record:
                    m.update(const_convert_to_rawstring(item))

        if strings:
            import hashlib
            m = hashlib.md5()


        cur = self.cursor.execute("""
        SELECT idpackage,atom,name,version,versiontag,
        revision,branch,slot,etpapi,trigger FROM 
        baseinfo %s""" % (idpackage_order,))
        if strings:
            do_update_md5(m, cur)
        else:
            a_hash = hash(tuple(cur.fetchall()))


        cur = self.cursor.execute("""
        SELECT idpackage, description, homepage,
        download, size, digest, datecreation FROM
        extrainfo %s""" % (idpackage_order,))
        if strings:
            do_update_md5(m, cur)
        else:
            b_hash = hash(tuple(cur.fetchall()))


        cur = self.cursor.execute("""
        SELECT category FROM categories %s
        """ % (category_order,))
        if strings:
            do_update_md5(m, cur)
        else:
            c_hash = hash(tuple(cur.fetchall()))


        d_hash = '0'
        e_hash = '0'
        if strict:
            cur = self.cursor.execute("""
            SELECT * FROM licenses %s""" % (license_order,))
            if strings:
                do_update_md5(m, cur)
            else:
                d_hash = hash(tuple(cur.fetchall()))

            cur = self.cursor.execute('select * from flags %s' % (flags_order,))
            if strings:
                do_update_md5(m, cur)
            else:
                e_hash = hash(tuple(cur.fetchall()))

        if strings:
            result = m.hexdigest()
        else:
            result = "%s:%s:%s:%s:%s" % (a_hash, b_hash, c_hash, d_hash,
                e_hash,)

        self.live_cache[c_tup] = result[:]
        return result


    def storeInstalledPackage(self, idpackage, repoid, source = 0):
        """
        Note: this is used by installed packages repository (also known as
        client db).
        Add package identifier to the "installed packages table",
        which contains repository identifier from where package has been
        installed and its install request source (user, pulled in
        dependency, etc).

        @param idpackage: package indentifier
        @type idpackage: int
        @param repoid: repository identifier
        @type repoid: string
        @param source: source identifier (pleas see:
            etpConst['install_sources'])
        @type source: int
        """
        with self.__write_mutex:
            self.cursor.execute('INSERT into installedtable VALUES (?,?,?)',
                (idpackage, repoid, source,))

    def getInstalledPackageRepository(self, idpackage):
        """
        Note: this is used by installed packages repository (also known as
        client db).
        Return repository identifier stored inside the "installed packages
        table".

        @param idpackage: package indentifier
        @type idpackage: int
        @return: repository identifier
        @rtype: string or None
        """
        with self.__write_mutex:
            try:
                cur = self.cursor.execute("""
                SELECT repositoryname FROM installedtable
                WHERE idpackage = (?) LIMIT 1""", (idpackage,))
                return cur.fetchone()[0]
            except (self.dbapi2.OperationalError, TypeError,):
                return None

    def dropInstalledPackageFromStore(self, idpackage):
        """
        Note: this is used by installed packages repository (also known as
        client db).
        Remove installed package metadata from "installed packages table".
        Note: this just removes extra metadata information such as repository
        identifier from where package has been installed and its install
        request source (user, pulled in dependency, etc).
        This method DOES NOT remove package from repository (see
        removePackage() instead).

        @param idpackage: package indentifier
        @type idpackage: int
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM installedtable
            WHERE idpackage = (?)""", (idpackage,))

    def _removePackageFromDependsTable(self, idpackage):
        with self.__write_mutex:
            try:
                self.cursor.execute("""
                DELETE FROM dependstable WHERE idpackage = (?)
                """, (idpackage,))
                return 0
            except (self.dbapi2.OperationalError,):
                return 1 # need reinit

    def _createDependsTable(self):
        with self.__write_mutex:
            self.cursor.executescript("""
            CREATE TABLE IF NOT EXISTS dependstable
            ( iddependency INTEGER PRIMARY KEY, idpackage INTEGER,
              FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE );
            INSERT INTO dependstable VALUES (-1,NULL);
            """)
            if self.indexing:
                self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS dependsindex_idpackage
                ON dependstable ( idpackage )
                """)
            self.commitChanges()

    def _sanitizeDependsTable(self):
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM dependstable where iddependency = -1
            """)
            self.commitChanges()

    def _isDependsTableSane(self):
        try:
            cur = self.cursor.execute("""
            SELECT iddependency FROM dependstable WHERE iddependency = -1
            """)
        except (self.dbapi2.OperationalError,):
            return False # table does not exist, please regenerate and re-run

        status = cur.fetchone()
        if status:
            return False

        cur = self.cursor.execute("SELECT count(*) FROM dependstable")
        try:
            dependstable_count = cur.fetchone()[0]
        except IndexError:
            dependstable_count = 0
        if dependstable_count < 2:
            return False
        return True

    def storeXpakMetadata(self, idpackage, blob):
        """
        Xpak metadata is Source Package Manager package metadata.
        This method stores such metadata inside repository.

        @param idpackage: package indentifier
        @type idpackage: int
        @param blob: metadata blob
        @type blob: string or buffer
        """
        with self.__write_mutex:
            self.cursor.execute('INSERT into xpakdata VALUES (?,?)',
                (int(idpackage), const_get_buffer()(blob),)
            )
            self.commitChanges()

    def retrieveXpakMetadata(self, idpackage):
        """
        Xpak metadata is Source Package Manager package metadata.
        This method returns such stored metadata inside repository.

        @param idpackage: package indentifier
        @type idpackage: int
        @return: stored metadata
        @rtype: buffer
        """
        try:
            cur = self.cursor.execute("""
            SELECT data from xpakdata where idpackage = (?) LIMIT 1
            """, (idpackage,))
            mydata = cur.fetchone()
            if not mydata:
                return ""
            return mydata[0]
        except (self.dbapi2.Error, TypeError, IndexError,):
            return ""

    def retrieveBranchMigration(self, to_branch):
        """
        This method returns branch migration metadata stored in Entropy
        Client database (installed packages database). It is used to
        determine whether to run per-repository branch migration scripts.

        @param to_branch: usually the current branch string
        @type to_branch: string
        @return: branch migration metadata contained in database
        @rtype: dict
        """
        if not self._doesTableExist('entropy_branch_migration'):
            return {}

        cur = self.cursor.execute("""
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
        Drop all "content" metadata from repository, usually a memory hog.
        Content metadata contains files and directories owned by packages.
        """
        with self.__write_mutex:
            self.cursor.execute('DELETE FROM content')

    def dropAllIndexes(self):
        """
        Drop all repository metadata indexes.
        """
        cur = self.cursor.execute("""
        SELECT name FROM SQLITE_MASTER WHERE type = "index"
        """)
        indexes = self._cur2set(cur)
        with self.__write_mutex:
            for index in indexes:
                try:
                    self.cursor.execute('DROP INDEX IF EXISTS %s' % (index,))
                except self.dbapi2.Error:
                    continue

    def listAllIndexes(self, only_entropy = True):
        """
        List all the available repository metadata index names.

        @keyword only_entropy: if True, return only entropy related indexes
        @type only_entropy: bool
        @return: list (set) of index names
        @rtype: set
        """
        cur = self.cursor.execute("""
        SELECT name FROM SQLITE_MASTER WHERE type = "index"
        """)
        indexes = self._cur2set(cur)

        if not only_entropy:
            return indexes
        return set([x for x in indexes if not x.startswith("sqlite")])

    def createAllIndexes(self):
        """
        Create all the repository metadata indexes internally available.
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
        self._createMessagesIndex()
        self._createSourcesIndex()
        self._createCountersIndex()
        self._createEclassesIndex()
        self._createCategoriesIndex()
        self._createCompileFlagsIndex()
        self._createPackagesetsIndex()
        self._createAutomergefilesIndex()
        self._createProvidedLibsIndex()

    def _createMirrorlinksIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS mirrorlinks_mirrorname
                ON mirrorlinks ( mirrorname )""")

    def _createPackagesetsIndex(self):
        if self.indexing:
            with self.__write_mutex:
                try:
                    self.cursor.execute("""
                    CREATE INDEX IF NOT EXISTS packagesetsindex
                    ON packagesets ( setname )""")
                except self.dbapi2.OperationalError:
                    pass

    def _createProvidedLibsIndex(self):
        if self.indexing:
            with self.__write_mutex:
                try:
                    self.cursor.executescript("""
                        CREATE INDEX IF NOT EXISTS provided_libs_library
                        ON provided_libs ( library );
                        CREATE INDEX IF NOT EXISTS provided_libs_idpackage
                        ON provided_libs ( idpackage );
                        CREATE INDEX IF NOT EXISTS provided_libs_lib_elf
                        ON provided_libs ( library, elfclass );
                    """)
                except self.dbapi2.OperationalError:
                    pass

    def _createAutomergefilesIndex(self):
        if self.indexing:
            with self.__write_mutex:
                try:
                    self.cursor.executescript("""
                        CREATE INDEX IF NOT EXISTS automergefiles_idpackage 
                        ON automergefiles ( idpackage );
                        CREATE INDEX IF NOT EXISTS automergefiles_file_md5 
                        ON automergefiles ( configfile, md5 );
                    """)
                except self.dbapi2.OperationalError:
                    pass

    def _createNeededIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.executescript("""
                    CREATE INDEX IF NOT EXISTS neededindex ON neededreference
                        ( library );
                    CREATE INDEX IF NOT EXISTS neededindex_idneeded ON needed
                        ( idneeded );
                    CREATE INDEX IF NOT EXISTS neededindex_idpackage ON needed
                        ( idpackage );
                    CREATE INDEX IF NOT EXISTS neededindex_elfclass ON needed
                        ( elfclass );
                """)

    def _createMessagesIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS messagesindex ON messages
                    ( idpackage )
                """)

    def _createCompileFlagsIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS flagsindex ON flags
                    ( chost, cflags, cxxflags )
                """)

    def _createUseflagsIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.executescript("""
                CREATE INDEX IF NOT EXISTS useflagsindex_useflags_idpackage
                    ON useflags ( idpackage );
                CREATE INDEX IF NOT EXISTS useflagsindex_useflags_idflag
                    ON useflags ( idflag );
                CREATE INDEX IF NOT EXISTS useflagsindex
                    ON useflagsreference ( flagname );
                """)

    def _createContentIndex(self):
        if self.indexing:
            with self.__write_mutex:
                if self._doesTableExist("content"):
                    self.cursor.executescript("""
                        CREATE INDEX IF NOT EXISTS contentindex_couple
                            ON content ( idpackage );
                        CREATE INDEX IF NOT EXISTS contentindex_file
                            ON content ( file );
                    """)

    def _createConfigProtectReferenceIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS configprotectreferenceindex
                    ON configprotectreference ( protect )
                """)

    def _createBaseinfoIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.executescript("""
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
            with self.__write_mutex:
                self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS licensedataindex
                    ON licensedata ( licensename )
                """)

    def _createLicensesIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS licensesindex ON licenses ( license )
                """)

    def _createCategoriesIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS categoriesindex_category
                    ON categories ( category )
                """)

    def _createKeywordsIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.executescript("""
                CREATE INDEX IF NOT EXISTS keywordsreferenceindex
                    ON keywordsreference ( keywordname );
                CREATE INDEX IF NOT EXISTS keywordsindex_idpackage
                    ON keywords ( idpackage );
                CREATE INDEX IF NOT EXISTS keywordsindex_idkeyword
                    ON keywords ( idkeyword );
                """)

    def _createDependenciesIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.executescript("""
                CREATE INDEX IF NOT EXISTS dependenciesindex_idpackage
                    ON dependencies ( idpackage );
                CREATE INDEX IF NOT EXISTS dependenciesindex_iddependency
                    ON dependencies ( iddependency );
                CREATE INDEX IF NOT EXISTS dependenciesreferenceindex_dependency
                    ON dependenciesreference ( dependency );
                """)

    def _createCountersIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.executescript("""
                CREATE INDEX IF NOT EXISTS countersindex_idpackage
                    ON counters ( idpackage );
                CREATE INDEX IF NOT EXISTS countersindex_counter
                    ON counters ( counter );
                """)

    def _createSourcesIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.executescript("""
                CREATE INDEX IF NOT EXISTS sourcesindex_idpackage
                    ON sources ( idpackage );
                CREATE INDEX IF NOT EXISTS sourcesindex_idsource
                    ON sources ( idsource );
                CREATE INDEX IF NOT EXISTS sourcesreferenceindex_source
                    ON sourcesreference ( source );
                """)

    def _createProvideIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.executescript("""
                CREATE INDEX IF NOT EXISTS provideindex_idpackage
                    ON provide ( idpackage );
                CREATE INDEX IF NOT EXISTS provideindex_atom
                    ON provide ( atom );
                """)

    def _createConflictsIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.executescript("""
                CREATE INDEX IF NOT EXISTS conflictsindex_idpackage
                    ON conflicts ( idpackage );
                CREATE INDEX IF NOT EXISTS conflictsindex_atom
                    ON conflicts ( conflict );
                """)

    def _createExtrainfoIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.executescript("""
                CREATE INDEX IF NOT EXISTS extrainfoindex
                    ON extrainfo ( description );
                CREATE INDEX IF NOT EXISTS extrainfoindex_pkgindex
                    ON extrainfo ( idpackage );
                """)

    def _createEclassesIndex(self):
        if self.indexing:
            with self.__write_mutex:
                self.cursor.executescript("""
                CREATE INDEX IF NOT EXISTS eclassesindex_idpackage
                    ON eclasses ( idpackage );
                CREATE INDEX IF NOT EXISTS eclassesindex_idclass
                    ON eclasses ( idclass );
                CREATE INDEX IF NOT EXISTS eclassesreferenceindex_classname
                    ON eclassesreference ( classname );
                """)

    def dropContentIndex(self, only_file = False):
        """
        Drop "content" metadata index.

        @keyword only_file: drop only "file" index
        @type only_file: bool
        """
        with self.__write_mutex:
            self.cursor.execute("DROP INDEX IF EXISTS contentindex_file")
            if not only_file:
                self.cursor.executescript("""
                DROP INDEX IF EXISTS contentindex_couple;
                """)

    def regenerateSpmUidTable(self, verbose = False):
        """
        Regenerate Source Package Manager package identifiers table.
        This method will use the Source Package Manger interface.

        @keyword verbose: run in verbose mode
        @type verbose: bool
        """

        # Poll SPM, load variables
        spm = get_spm(self)

        # this is necessary now, counters table should be empty
        with self.__write_mutex:

            self.cursor.executescript("""
            DROP TABLE IF EXISTS counters_regen;
            CREATE TEMPORARY TABLE counters_regen (
                counter INTEGER,
                idpackage INTEGER,
                branch VARCHAR,
                PRIMARY KEY(idpackage, branch)
            );
            """)
            insert_data = []
            for myid in self.listAllIdpackages():

                try:
                    spm_uid = spm.resolve_package_uid(self, myid)
                except SPMError as err:
                    if verbose:
                        mytxt = "%s: %s: %s" % (
                            bold(_("ATTENTION")),
                            red(_("Spm error occured")),
                            str(err),
                        )
                        self.updateProgress(
                            mytxt,
                            importance = 1,
                            type = "warning"
                        )
                    continue

                if spm_uid is None:
                    if verbose:
                        mytxt = "%s: %s: %s" % (
                            bold(_("ATTENTION")),
                            red(_("Spm Unique Identifier not found for")),
                            self.retrieveAtom(myid),
                        )
                        self.updateProgress(
                            mytxt,
                            importance = 1,
                            type = "warning"
                        )
                    continue

                mybranch = self.retrieveBranch(myid)
                insert_data.append((spm_uid, myid, mybranch))

            self.cursor.executemany("""
            INSERT OR REPLACE into counters_regen VALUES (?,?,?)
            """, insert_data)

            self.cursor.executescript("""
            DELETE FROM counters;
            INSERT INTO counters (counter, idpackage, branch)
                SELECT counter, idpackage, branch FROM counters_regen;
            """)

        self.commitChanges()

    def clearTreeupdatesEntries(self, repository):
        """
        This method should be considered internal and not suited for general
        audience. Clear "treeupdates" metadata for given repository identifier.

        @param repository: repository identifier
        @type repository: string
        """
        with self.__write_mutex:
            self.cursor.execute("""
            DELETE FROM treeupdates WHERE repository = (?)
            """, (repository,))
            self.commitChanges()

    def resetTreeupdatesDigests(self):
        """
        This method should be considered internal and not suited for general
        audience. Reset "treeupdates" digest metadata.
        """
        with self.__write_mutex:
            self.cursor.execute('UPDATE treeupdates SET digest = "-1"')
            self.commitChanges()

    def _foreignKeySupport(self):

        # TODO: remove this by 2011/12/31

        tables = ("extrainfo", "dependencies" ,"provide",
            "conflicts", "configprotect", "configprotectmask", "sources",
            "useflags", "keywords", "content", "messages", "counters", "sizes",
            "eclasses", "needed", "triggers", "systempackages", "injected",
            "installedtable", "automergefiles", "packagesignatures",
            "packagespmphases", "provided_libs", "dependstable"
        )

        done_something = False
        for table in tables:
            if not self._doesTableExist(table): # wtf
                continue

            cur = self.cursor.execute("PRAGMA foreign_key_list(%s)" % (table,))
            foreign_keys = cur.fetchone()

            # print table, "foreign keys", foreign_keys
            if foreign_keys is not None:
                continue

            done_something = True
            # need to add foreign key to this table
            cur = self.cursor.execute("""SELECT sql FROM sqlite_master
            WHERE type='table' and name = (?)""", (table,))
            cur_sql = cur.fetchone()[0]

            # change table name
            tmp_table = table+"_fk_sup"
            self.cursor.execute("DROP TABLE IF EXISTS %s" % (tmp_table,))

            bracket_idx = cur_sql.find("(")
            cur_sql = cur_sql[bracket_idx:]
            cur_sql = "CREATE TABLE %s %s" % (tmp_table, cur_sql)

            # remove final parenthesis and strip
            cur_sql = cur_sql[:-1].strip()
            # add foreign key stmt
            cur_sql += """,
            FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE );"""
            self.cursor.executescript(cur_sql)
            self._moveContent(table, tmp_table)
            self._atomicRename(tmp_table, table)

        if done_something:
            self.cursor.execute("""
                INSERT OR REPLACE INTO settings
                VALUES ("on_delete_cascade", "1")
            """)

    def _moveContent(self, from_table, to_table):
        self.cursor.execute("""
            INSERT INTO %s SELECT * FROM %s
        """ % (to_table, from_table,))

    def _atomicRename(self, from_table, to_table):
        self.cursor.executescript("""
            BEGIN TRANSACTION;
            DROP TABLE IF EXISTS %s;
            ALTER TABLE %s RENAME TO %s;
            COMMIT;
        """ % (to_table, from_table, to_table,))

    def _migrateCountersTable(self):
        with self.__write_mutex:
            self.cursor.executescript("""
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
        with self.__write_mutex:
            self.cursor.executescript("""
                CREATE TABLE settings (
                    setting_name VARCHAR,
                    setting_value VARCHAR,
                    PRIMARY KEY(setting_name)
                );
            """)
            self._setupInitialSettings()

    def _createProvidedLibs(self):

        def do_create():
            self.cursor.executescript("""
                CREATE TABLE provided_libs (
                    idpackage INTEGER,
                    library VARCHAR,
                    path VARCHAR,
                    elfclass INTEGER,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );
            """)

        # TODO: this is going to be removed soon
        client_repo = self.get_plugins_metadata().get('client_repo')
        with self.__write_mutex:

            if client_repo and (self.dbname != etpConst['clientdbid']):
                return do_create()

            mytxt = "%s: %s" % (
                bold(_("ATTENTION")),
                red(_("generating provided_libs metadata, please wait!")),
            )
            self.updateProgress(
                mytxt,
                importance = 1,
                type = "warning"
            )

            try:
                self._generateProvidedLibsMetadata()
            except (IOError, OSError, self.dbapi2.Error) as err:
                mytxt = "%s: %s: [%s]" % (
                    bold(_("ATTENTION")),
                    red("cannot generate provided_libs metadata"),
                    err,
                )
                self.updateProgress(
                    mytxt,
                    importance = 1,
                    type = "warning"
                )
                do_create()


    def _generateProvidedLibsMetadata(self):

        def collect_provided(pkg_dir, content):

            provided_libs = set()
            ldpaths = self.entropyTools.collect_linker_paths()
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
                if not self.entropyTools.is_elf_file(unpack_obj):
                    continue

                elf_class = self.entropyTools.read_elf_class(unpack_obj)
                provided_libs.add((obj_name, obj, elf_class,))

            return provided_libs

        self.cursor.executescript("""
            DROP TABLE IF EXISTS provided_libs_tmp;
            CREATE TABLE provided_libs_tmp (
                idpackage INTEGER,
                library VARCHAR,
                path VARCHAR,
                elfclass INTEGER,
                FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
            );
        """)

        pkgs = self.listAllIdpackages()
        for idpackage in pkgs:

            content = self.retrieveContent(idpackage, extended = True,
                formatted = True)
            provided_libs = collect_provided(etpConst['systemroot'], content)

            self.cursor.executemany("""
            INSERT INTO provided_libs_tmp VALUES (?,?,?,?)
            """, [(idpackage, x, y, z,) for x, y, z in provided_libs])

        # rename
        self.cursor.execute("""
        ALTER TABLE provided_libs_tmp RENAME TO provided_libs;
        """)

    def _createProvideDefault(self):
        self.cursor.execute("""
        ALTER TABLE provide ADD COLUMN is_default INTEGER DEFAULT 0
        """)

    def _createInstalledTableSource(self):
        with self.__write_mutex:
            self.cursor.execute("""
            ALTER TABLE installedtable ADD source INTEGER;
            """)
            self.cursor.execute("""
            UPDATE installedtable SET source = (?)
            """, (etpConst['install_sources']['unknown'],))

    def _createPackagechangelogsTable(self):
        with self.__write_mutex:
            self.cursor.execute("""
            CREATE TABLE packagechangelogs ( category VARCHAR,
                name VARCHAR, changelog BLOB, PRIMARY KEY (category, name));
            """)

    def _createAutomergefilesTable(self):
        with self.__write_mutex:
            self.cursor.execute("""
            CREATE TABLE automergefiles ( idpackage INTEGER,
                configfile VARCHAR, md5 VARCHAR,
                FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE );
            """)

    def _createPackagesignaturesTable(self):
        with self.__write_mutex:
            self.cursor.execute("""
            CREATE TABLE packagesignatures (
            idpackage INTEGER PRIMARY KEY,
            sha1 VARCHAR,
            sha256 VARCHAR,
            sha512 VARCHAR,
            FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE );
            """)

    def _createPackagespmphases(self):
        with self.__write_mutex:
            self.cursor.execute("""
                CREATE TABLE packagespmphases (
                    idpackage INTEGER PRIMARY KEY,
                    phases VARCHAR,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );
            """)

    def _createPackagespmrepository(self):
        with self.__write_mutex:
            self.cursor.execute("""
                CREATE TABLE packagespmrepository (
                    idpackage INTEGER PRIMARY KEY,
                    repository VARCHAR,
                    FOREIGN KEY(idpackage) REFERENCES baseinfo(idpackage) ON DELETE CASCADE
                );
            """)

    def _createEntropyBranchMigrationTable(self):
        with self.__write_mutex:
            self.cursor.execute("""
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
        with self.__write_mutex:
            self.cursor.execute("""
            CREATE TABLE packagesets ( setname VARCHAR, dependency VARCHAR );
            """)

    def createCategoriesdescriptionTable(self):
        with self.__write_mutex:
            self.cursor.execute("""
            CREATE TABLE categoriesdescription ( category VARCHAR,
                locale VARCHAR, description VARCHAR );
            """)

    def createLicensedataTable(self):
        with self.__write_mutex:
            self.cursor.execute("""
            CREATE TABLE licensedata ( licensename VARCHAR UNIQUE,
                text BLOB, compressed INTEGER );
            """)

    def _createLicensesAcceptedTable(self):
        with self.__write_mutex:
            self.cursor.execute("""
            CREATE TABLE licenses_accepted ( licensename VARCHAR UNIQUE );
            """)

    def _addDependsRelationToDependsTable(self, iterable):
        with self.__write_mutex:
            self.cursor.executemany('INSERT into dependstable VALUES (?,?)',
                iterable)

    def taintReverseDependenciesMetadata(self):
        """
        Taint reverse (or inverse) dependencies metadata so that will be
        generated during the next request.
        """
        # FIXME: backward compatibility
        if not self._doesTableExist("dependstable"):
            return
        self.cursor.executescript("""
            DELETE FROM dependstable;
            INSERT INTO dependstable VALUES (-1,NULL);
        """)

    def generateReverseDependenciesMetadata(self, verbose = True):
        """
        Regenerate reverse (or inverse) dependencies metadata.

        @keyword verbose: enable verbosity
        @type verbose: bool
        """
        depends = self.listAllDependencies()
        count = 0
        total = len(depends)
        mydata = set()
        am = self.atomMatch
        up = self.updateProgress
        self.taintReverseDependenciesMetadata()
        self.commitChanges()
        for iddep, atom in depends:
            count += 1

            if verbose and ((count == 0) or (count % 150 == 0) or \
                (count == total)):
                up( red("Resolving %s") % (atom,), importance = 0,
                    type = "info", back = True, count = (count, total)
                )

            idpackage, rc = am(atom)
            if idpackage == -1:
                continue
            if iddep == -1:
                continue
            mydata.add((iddep, idpackage,))

        if mydata:
            try:
                self._addDependsRelationToDependsTable(mydata)
            except self.dbapi2.IntegrityError:
                # try to cope for the last time
                self.taintReverseDependenciesMetadata()
                self.commitChanges()
                self._addDependsRelationToDependsTable(mydata)

        # now validate dependstable
        self._sanitizeDependsTable()

        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.reverse_dependencies_tree_generation_hook(self)
            if exec_rc:
                raise RepositoryPluginError(
                    "[reverse_dependencies_tree_generation_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

    def moveSpmUidsToBranch(self, to_branch, from_branch = None):
        """
        Note: this is not intended for general audience.
        Move "branch" metadata contained in Source Package Manager package
        identifiers binding metadata to new value given by "from_branch"
        argument.

        @param to_branch:
        @type to_branch:
        @keyword from_branch:
        @type from_branch:
        @return:
        @rtype:

        """
        with self.__write_mutex:
            if from_branch is not None:
                self.cursor.execute("""
                UPDATE counters SET branch = (?) WHERE branch = (?)
                """, (to_branch, from_branch,))
            else:
                self.cursor.execute("""
                UPDATE counters SET branch = (?)
                """, (to_branch,))
            self.commitChanges()
            self.clearCache()

    def __atomMatchFetchCache(self, *args):
        if self.xcache:
            ck_sum = hash(self.checksum())
            cached = self.dumpTools.loadobj("%s/%s/%s_%s" % (
                self.dbMatchCacheKey, self.dbname, ck_sum, hash(tuple(args)),))
            if cached is not None:
                return cached

    def __atomMatchStoreCache(self, *args, **kwargs):
        if self.xcache:
            ck_sum = hash(self.checksum(strict = False))
            self.Cacher.push("%s/%s/%s_%s" % (
                self.dbMatchCacheKey, self.dbname, ck_sum, hash(tuple(args)),),
                kwargs.get('result')
            )

    def __atomMatchValidateCache(self, cached_obj, multiMatch, extendedResults):

        # time wasted for a reason
        data, rc = cached_obj
        if rc != 0:
            return cached_obj

        # data must be int !
        if not self.entropyTools.isnumber(data):
            return None

        if (not extendedResults) and (not multiMatch):
            if not self.isIdpackageAvailable(data):
                return None

        elif extendedResults and (not multiMatch):
            if not self.isIdpackageAvailable(data[0]):
                return None

        elif extendedResults and multiMatch:
            idpackages = set([x[0] for x in data])
            if not self.areIdpackagesAvailable(idpackages):
                return None

        elif (not extendedResults) and multiMatch:
            # (set([x[0] for x in dbpkginfo]),0)
            idpackages = set(data)
            if not self.areIdpackagesAvailable(idpackages):
                return None

        return cached_obj

    def _idpackageValidator_live(self, idpackage, reponame):

        ref = self.SystemSettings['pkg_masking_reference']
        if (idpackage, reponame) in \
            self.SystemSettings['live_packagemasking']['mask_matches']:

            # do not cache this
            return -1, ref['user_live_mask']

        elif (idpackage, reponame) in \
            self.SystemSettings['live_packagemasking']['unmask_matches']:

            return idpackage, ref['user_live_unmask']

    def _idpackageValidator_user_package_mask(self, idpackage, reponame, live):

        mykw = "%smask_ids" % (reponame,)
        user_package_mask_ids = self.SystemSettings.get(mykw)

        if not isinstance(user_package_mask_ids, (list, set)):
            user_package_mask_ids = set()

            for atom in self.SystemSettings['mask']:
                matches, r = self.atomMatch(atom, multiMatch = True,
                    packagesFilter = False)
                if r != 0:
                    continue
                user_package_mask_ids |= set(matches)

            self.SystemSettings[mykw] = user_package_mask_ids

        if idpackage in user_package_mask_ids:
            # sorry, masked
            ref = self.SystemSettings['pkg_masking_reference']
            myr = ref['user_package_mask']

            try:

                cl_data = self.SystemSettings[self.client_settings_plugin_id]
                validator_cache = cl_data['masking_validation']['cache']
                validator_cache[(idpackage, reponame, live)] = -1, myr

            except KeyError: # system settings client plugin not found
                pass

            return -1, myr

    def _idpackageValidator_user_package_unmask(self, idpackage, reponame,
        live):

        # see if we can unmask by just lookin into user
        # package.unmask stuff -> self.SystemSettings['unmask']
        mykw = "%sunmask_ids" % (reponame,)
        user_package_unmask_ids = self.SystemSettings.get(mykw)

        if not isinstance(user_package_unmask_ids, (list, set)):

            user_package_unmask_ids = set()
            for atom in self.SystemSettings['unmask']:
                matches, r = self.atomMatch(atom, multiMatch = True,
                    packagesFilter = False)
                if r != 0:
                    continue
                user_package_unmask_ids |= set(matches)

            self.SystemSettings[mykw] = user_package_unmask_ids

        if idpackage in user_package_unmask_ids:

            ref = self.SystemSettings['pkg_masking_reference']
            myr = ref['user_package_unmask']
            try:

                cl_data = self.SystemSettings[self.client_settings_plugin_id]
                validator_cache = cl_data['masking_validation']['cache']
                validator_cache[(idpackage, reponame, live)] = idpackage, myr

            except KeyError: # system settings client plugin not found
                pass

            return idpackage, myr

    def _idpackageValidator_packages_db_mask(self, idpackage, reponame, live):

        # check if repository packages.db.mask needs it masked
        repos_mask = {}
        client_plg_id = etpConst['system_settings_plugins_ids']['client_plugin']
        client_settings = self.SystemSettings.get(client_plg_id, {})
        if client_settings:
            repos_mask = client_settings['repositories']['mask']

        repomask = repos_mask.get(reponame)
        if isinstance(repomask, (list, set)):

            # first, seek into generic masking, all branches
            # (below) avoid issues with repository names
            mask_repo_id = "%s_ids@@:of:%s" % (reponame, reponame,)
            repomask_ids = repos_mask.get(mask_repo_id)

            if not isinstance(repomask_ids, set):
                repomask_ids = set()
                for atom in repomask:
                    matches, r = self.atomMatch(atom, multiMatch = True,
                        packagesFilter = False)
                    if r != 0:
                        continue
                    repomask_ids |= set(matches)
                repos_mask[mask_repo_id] = repomask_ids

            if idpackage in repomask_ids:

                ref = self.SystemSettings['pkg_masking_reference']
                myr = ref['repository_packages_db_mask']

                try:

                    plg_id = self.client_settings_plugin_id
                    cl_data = self.SystemSettings[plg_id]
                    validator_cache = cl_data['masking_validation']['cache']
                    validator_cache[(idpackage, reponame, live)] = -1, myr

                except KeyError: # system settings client plugin not found
                    pass

                return -1, myr

    def _idpackageValidator_package_license_mask(self, idpackage, reponame,
        live):

        if not self.SystemSettings['license_mask']:
            return

        mylicenses = self.retrieveLicense(idpackage)
        mylicenses = mylicenses.strip().split()
        lic_mask = self.SystemSettings['license_mask']
        for mylicense in mylicenses:

            if mylicense not in lic_mask:
                continue

            ref = self.SystemSettings['pkg_masking_reference']
            myr = ref['user_license_mask']
            try:

                cl_data = self.SystemSettings[self.client_settings_plugin_id]
                validator_cache = cl_data['masking_validation']['cache']
                validator_cache[(idpackage, reponame, live)] = -1, myr

            except KeyError: # system settings client plugin not found
                pass

            return -1, myr

    def _idpackageValidator_keyword_mask(self, idpackage, reponame, live):

        # WORKAROUND for buggy entries
        # ** is fine then
        mykeywords = self.retrieveKeywords(idpackage) or set([''])

        mask_ref = self.SystemSettings['pkg_masking_reference']

        # firstly, check if package keywords are in etpConst['keywords']
        # (universal keywords have been merged from package.keywords)
        same_keywords = etpConst['keywords'] & mykeywords
        if same_keywords:
            myr = mask_ref['system_keyword']
            try:

                cl_data = self.SystemSettings[self.client_settings_plugin_id]
                validator_cache = cl_data['masking_validation']['cache']
                validator_cache[(idpackage, reponame, live)] = idpackage, myr

            except KeyError: # system settings client plugin not found
                pass

            return idpackage, myr

        # if we get here, it means we didn't find mykeywords
        # in etpConst['keywords']
        # we need to seek self.SystemSettings['keywords']
        # seek in repository first
        keyword_repo = self.SystemSettings['keywords']['repositories']

        for keyword in list(keyword_repo.get(reponame, {}).keys()):

            if keyword not in mykeywords:
                continue

            keyword_data = keyword_repo[reponame].get(keyword)
            if not keyword_data:
                continue

            if "*" in keyword_data:
                # all packages in this repo with keyword "keyword" are ok
                myr = mask_ref['user_repo_package_keywords_all']
                try:

                    plg_id = self.client_settings_plugin_id
                    cl_data = self.SystemSettings[plg_id]
                    validator_cache = cl_data['masking_validation']['cache']
                    validator_cache[(idpackage, reponame, live)] = \
                        idpackage, myr

                except KeyError: # system settings client plugin not found
                    pass

                return idpackage, myr

            kwd_key = "%s_ids" % (keyword,)
            keyword_data_ids = keyword_repo[reponame].get(kwd_key)
            if not isinstance(keyword_data_ids, set):

                keyword_data_ids = set()
                for atom in keyword_data:
                    matches, r = self.atomMatch(atom, multiMatch = True,
                        packagesFilter = False)
                    if r != 0:
                        continue
                    keyword_data_ids |= matches

                keyword_repo[reponame][kwd_key] = keyword_data_ids

            if idpackage in keyword_data_ids:

                myr = mask_ref['user_repo_package_keywords']
                try:

                    plg_id = self.client_settings_plugin_id
                    cl_data = self.SystemSettings[plg_id]
                    validator_cache = cl_data['masking_validation']['cache']
                    validator_cache[(idpackage, reponame, live)] = \
                        idpackage, myr

                except KeyError: # system settings client plugin not found
                    pass
                return idpackage, myr

        keyword_pkg = self.SystemSettings['keywords']['packages']

        # if we get here, it means we didn't find a match in repositories
        # so we scan packages, last chance
        for keyword in list(keyword_pkg.keys()):
            # use .keys() because keyword_pkg gets modified during iteration

            # first of all check if keyword is in mykeywords
            if keyword not in mykeywords:
                continue

            keyword_data = keyword_pkg.get(keyword)
            if not keyword_data:
                continue

            kwd_key = "%s_ids" % (keyword,)
            keyword_data_ids = keyword_pkg.get(reponame+kwd_key)

            if not isinstance(keyword_data_ids, (list, set)):
                keyword_data_ids = set()
                for atom in keyword_data:
                    # match atom
                    matches, r = self.atomMatch(atom, multiMatch = True,
                        packagesFilter = False)
                    if r != 0:
                        continue
                    keyword_data_ids |= matches

                keyword_pkg[reponame+kwd_key] = keyword_data_ids

            if idpackage in keyword_data_ids:

                # valid!
                myr = mask_ref['user_package_keywords']
                try:

                    plg_id = self.client_settings_plugin_id
                    cl_data = self.SystemSettings[plg_id]
                    validator_cache = cl_data['masking_validation']['cache']
                    validator_cache[(idpackage, reponame, live)] = \
                        idpackage, myr

                except KeyError: # system settings client plugin not found
                    pass

                return idpackage, myr


        ## if we get here, it means that pkg it keyword masked
        ## and we should look at the very last resort, per-repository
        ## package keywords
        # check if repository contains keyword unmasking data

        plg_id = self.client_settings_plugin_id
        cl_data = self.SystemSettings.get(plg_id)
        if cl_data is None:
            # SystemSettings Entropy Client plugin not available
            return
        # let's see if something is available in repository config
        repo_keywords = cl_data['repositories']['repos_keywords'].get(reponame)
        if repo_keywords is None:
            # nopers, sorry!
            return

        # check universal keywords
        same_keywords = repo_keywords.get('universal') & mykeywords
        if same_keywords:
            # universal keyword matches!
            myr = mask_ref['repository_packages_db_keywords']
            validator_cache = cl_data['masking_validation']['cache']
            validator_cache[(idpackage, reponame, live)] = \
                idpackage, myr
            return idpackage, myr

        ## if we get here, it means that even universal masking failed
        ## and we need to look at per-package settings
        repo_settings = repo_keywords.get('packages')
        if not repo_settings:
            # it's empty, not worth checking
            return

        cached_key = "packages_ids"
        keyword_data_ids = repo_keywords.get(cached_key)
        if not isinstance(keyword_data_ids, dict):
            # create cache

            keyword_data_ids = {}
            for atom, values in list(repo_settings.items()):
                matches, r = self.atomMatch(atom, multiMatch = True,
                    packagesFilter = False)
                if r != 0:
                    continue
                for match in matches:
                    obj = keyword_data_ids.setdefault(match, set())
                    obj.update(values)

            repo_keywords[cached_key] = keyword_data_ids

        same_keywords = keyword_data_ids.get(idpackage, set()) & \
            etpConst['keywords']
        if same_keywords:
            # found! this pkg is not masked, yay!
            myr = mask_ref['repository_packages_db_keywords']
            validator_cache = cl_data['masking_validation']['cache']
            validator_cache[(idpackage, reponame, live)] = \
                idpackage, myr
            return idpackage, myr


    def idpackageValidator(self, idpackage, live = True):
        """
        Return whether given package identifier is available to user or not,
        reading package masking metadata stored in SystemSettings.

        @param idpackage: package indentifier
        @type idpackage: int
        @keyword live: use live masking feature
        @type live: bool
        @return: tuple composed by idpackage and masking reason. If idpackage
            returned idpackage value == -1, it means that package is masked
            and a valid masking reason identifier is returned as second
            value of the tuple (see SystemSettings['pkg_masking_reasons'])
        @rtype: tuple
        """

        if self.dbname == etpConst['clientdbid']:
            return idpackage, 0

        # FIXME: this is Entropy Client related but also part of the
        # currently implemented metaphor, so let's wait to have a Rule
        # Engine in place before removing the oddity of client_repo
        # metadatum.
        client_repo = self.get_plugins_metadata().get('client_repo')
        if not client_repo:
            # server-side repositories don't make any use of idpackage validator
            return idpackage, 0

        reponame = self.dbname[len(etpConst['dbnamerepoprefix']):]
        try:
            cl_data = self.SystemSettings[self.client_settings_plugin_id]
            validator_cache = cl_data['masking_validation']['cache']

            cached = validator_cache.get((idpackage, reponame, live))
            if cached is not None:
                return cached

            # avoid memleaks
            if len(validator_cache) > 10000:
                validator_cache.clear()

        except KeyError: # plugin does not exist
            pass

        if live:
            data = self._idpackageValidator_live(idpackage, reponame)
            if data:
                return data

        data = self._idpackageValidator_user_package_mask(idpackage,
            reponame, live)
        if data:
            return data

        data = self._idpackageValidator_user_package_unmask(idpackage,
            reponame, live)
        if data:
            return data

        data = self._idpackageValidator_packages_db_mask(idpackage, reponame,
            live)
        if data:
            return data

        data = self._idpackageValidator_package_license_mask(idpackage,
            reponame, live)
        if data:
            return data

        data = self._idpackageValidator_keyword_mask(idpackage, reponame, live)
        if data:
            return data

        # holy crap, can't validate
        myr = self.SystemSettings['pkg_masking_reference']['completely_masked']
        validator_cache[(idpackage, reponame, live)] = -1, myr
        return -1, myr


    def _packagesFilter(self, results):
        """
        Packages filter used by atomMatch, input must me foundIDs,
        a list like this: [608, 1867].

        """

        # keywordsFilter ONLY FILTERS results if
        # self.dbname.startswith(etpConst['dbnamerepoprefix'])
        # => repository database is open
        if not self.dbname.startswith(etpConst['dbnamerepoprefix']):
            return results

        newresults = set()
        for idpackage in results:
            idpackage, reason = self.idpackageValidator(idpackage)
            if idpackage == -1:
                continue
            newresults.add(idpackage)
        return newresults

    def __filterSlot(self, idpackage, slot):
        if slot is None:
            return idpackage
        dbslot = self.retrieveSlot(idpackage)
        if dbslot == slot:
            return idpackage

    def __filterTag(self, idpackage, tag, operators):
        if tag is None:
            return idpackage
        dbtag = self.retrieveVersionTag(idpackage)
        compare = const_cmp(tag, dbtag)
        if not operators or operators == "=":
            if compare == 0:
                return idpackage
        else:
            return self.__do_operator_compare(idpackage, operators, compare)

    def __filterUse(self, idpackage, use):
        if not use:
            return idpackage
        pkguse = self.retrieveUseflags(idpackage)
        disabled = set([x[1:] for x in use if x.startswith("-")])
        enabled = set([x for x in use if not x.startswith("-")])
        enabled_not_satisfied = enabled - pkguse
        # check enabled
        if enabled_not_satisfied:
            return None
        # check disabled
        disabled_not_satisfied = disabled - pkguse
        if len(disabled_not_satisfied) != len(disabled):
            return None
        return idpackage

    def __do_operator_compare(self, token, operators, compare):
        if operators == ">" and compare == -1:
            return token
        elif operators == ">=" and compare < 1:
            return token
        elif operators == "<" and compare == 1:
            return token
        elif operators == "<=" and compare > -1:
            return token

    def __filterSlotTagUse(self, foundIDs, slot, tag, use, operators):

        def myfilter(idpackage):

            idpackage = self.__filterSlot(idpackage, slot)
            if not idpackage:
                return False

            idpackage = self.__filterUse(idpackage, use)
            if not idpackage:
                return False

            idpackage = self.__filterTag(idpackage, tag, operators)
            if not idpackage:
                return False

            return True

        return set(filter(myfilter, foundIDs))

    def atomMatch(self, atom, caseSensitive = True, matchSlot = None,
        multiMatch = False, matchTag = None, matchUse = (),
        packagesFilter = True, matchRevision = None, extendedResults = False,
        useCache = True):

        """
        Match given atom (or dependency) in repository and return its package
        identifer and execution status.

        @param atom: atom or dependency to match in repository
        @type atom: unicode string
        @keyword caseSensitive: match in case sensitive mode
        @type caseSensitive: bool
        @keyword matchSlot: match packages with given slot
        @type matchSlot: string
        @keyword multiMatch: match all the available packages, not just the
            best one
        @type multiMatch: bool
        @keyword matchTag: match packages with given tag
        @type matchTag: string
        @keyword matchUse: match packages with given use flags
        @type matchUse: list or tuple or set
        @keyword packagesFilter: enable package masking filter
        @type packagesFilter: bool
        @keyword matchRevision: match packages with given entropy revision
        @type matchRevision: int
        @keyword extendedResults: return extended results
        @type extendedResults: bool
        @keyword useCache: use on-disk cache
        @type useCache: bool
        @return: tuple of length 2 composed by (idpackage or -1, command status
            (0 means found, 1 means error)) or, if extendedResults is True,
            also add versioning information to tuple.
            If multiMatch is True, a tuple composed by a set (containing package
            identifiers) and command status is returned.
        @rtype: tuple or set
        @todo: improve documentation here
        """

        if not atom:
            return -1, 1

        if useCache:
            cached = self.__atomMatchFetchCache(
                atom, caseSensitive, matchSlot,
                multiMatch, matchTag,
                matchUse, packagesFilter, matchRevision,
                extendedResults
            )
            if isinstance(cached, tuple):

                try:
                    cached = self.__atomMatchValidateCache(cached,
                        multiMatch, extendedResults)
                except (TypeError, ValueError, IndexError, KeyError,):
                    cached = None

            if isinstance(cached, tuple):
                return cached

        atomTag = self.entropyTools.dep_gettag(atom)
        try:
            atomUse = self.entropyTools.dep_getusedeps(atom)
        except InvalidAtom:
            atomUse = ()
        atomSlot = self.entropyTools.dep_getslot(atom)
        atomRev = self.entropyTools.dep_get_entropy_revision(atom)
        if isinstance(atomRev, int):
            if atomRev < 0: atomRev = None

        # use match
        scan_atom = self.entropyTools.remove_usedeps(atom)
        if (not matchUse) and (atomUse):
            matchUse = atomUse

        # tag match
        scan_atom = self.entropyTools.remove_tag(scan_atom)
        if (matchTag is None) and (atomTag is not None):
            matchTag = atomTag

        # slot match
        scan_atom = self.entropyTools.remove_slot(scan_atom)
        if (matchSlot is None) and (atomSlot is not None):
            matchSlot = atomSlot

        # revision match
        scan_atom = self.entropyTools.remove_entropy_revision(scan_atom)
        if (matchRevision is None) and (atomRev is not None):
            matchRevision = atomRev

        direction = ''
        justname = True
        pkgkey = ''
        pkgname = ''
        pkgcat = ''
        pkgversion = ''
        strippedAtom = ''
        foundIDs = []
        dbpkginfo = set()

        if scan_atom:

            while True:
                # check for direction
                strippedAtom = self.entropyTools.dep_getcpv(scan_atom)
                if scan_atom[-1] == "*":
                    strippedAtom += "*"
                direction = scan_atom[0:-len(strippedAtom)]

                justname = self.entropyTools.isjustname(strippedAtom)
                pkgkey = strippedAtom
                if justname == 0:
                    # get version
                    data = self.entropyTools.catpkgsplit(strippedAtom)
                    if data is None:
                        break # badly formatted
                    pkgversion = data[2]+"-"+data[3]
                    pkgkey = self.entropyTools.dep_getkey(strippedAtom)

                splitkey = pkgkey.split("/")
                if (len(splitkey) == 2):
                    pkgcat, pkgname = splitkey
                else:
                    pkgcat, pkgname = "null", splitkey[0]

                break


            # IDs found in the database that match our search
            foundIDs = self.__generate_found_ids_match(pkgkey, pkgname, pkgcat,
                caseSensitive, multiMatch)

        ### FILTERING
        # filter slot and tag
        if foundIDs:
            foundIDs = self.__filterSlotTagUse(foundIDs, matchSlot,
                matchTag, matchUse, direction)
            if packagesFilter:
                foundIDs = self._packagesFilter(foundIDs)
        ### END FILTERING

        if foundIDs:
            dbpkginfo = self.__handle_found_ids_match(foundIDs, direction,
                matchTag, matchRevision, justname, strippedAtom, pkgversion)

        if not dbpkginfo:
            if extendedResults:
                if multiMatch:
                    x = set()
                else:
                    x = (-1, 1, None, None, None,)
                self.__atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (x, 1)
                )
                return x, 1
            else:
                if multiMatch:
                    x = set()
                else:
                    x = -1
                self.__atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (x, 1)
                )
                return x, 1

        if multiMatch:
            if extendedResults:
                x = set([(x[0], 0, x[1], self.retrieveVersionTag(x[0]), \
                    self.retrieveRevision(x[0])) for x in dbpkginfo])
                self.__atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (x, 0)
                )
                return x, 0
            else:
                x = set([x[0] for x in dbpkginfo])
                self.__atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (x, 0)
                )
                return x, 0

        if len(dbpkginfo) == 1:
            x = dbpkginfo.pop()
            if extendedResults:
                x = (x[0], 0, x[1], self.retrieveVersionTag(x[0]),
                    self.retrieveRevision(x[0]),)

                self.__atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (x, 0)
                )
                return x, 0
            else:
                self.__atomMatchStoreCache(
                    atom, caseSensitive, matchSlot,
                    multiMatch, matchTag,
                    matchUse, packagesFilter, matchRevision,
                    extendedResults, result = (x[0], 0)
                )
                return x[0], 0

        dbpkginfo = list(dbpkginfo)
        pkgdata = {}
        versions = set()

        for x in dbpkginfo:
            info_tuple = (x[1], self.retrieveVersionTag(x[0]), \
                self.retrieveRevision(x[0]))
            versions.add(info_tuple)
            pkgdata[info_tuple] = x[0]

        newer = self.entropyTools.get_entropy_newer_version(list(versions))[0]
        x = pkgdata[newer]
        if extendedResults:
            x = (x, 0, newer[0], newer[1], newer[2])
            self.__atomMatchStoreCache(
                atom, caseSensitive, matchSlot,
                multiMatch, matchTag,
                matchUse, packagesFilter, matchRevision,
                extendedResults, result = (x, 0)
            )
            return x, 0
        else:
            self.__atomMatchStoreCache(
                atom, caseSensitive, matchSlot,
                multiMatch, matchTag,
                matchUse, packagesFilter, matchRevision,
                extendedResults, result = (x, 0)
            )
            return x, 0

    def __generate_found_ids_match(self, pkgkey, pkgname, pkgcat, caseSensitive,
        multiMatch):

        if pkgcat == "null":
            results = self.searchPackagesByName(pkgname,
                sensitive = caseSensitive, justid = True)
        else:
            results = self.searchPackagesByNameAndCategory(name = pkgname,
                category = pkgcat, sensitive = caseSensitive, justid = True
            )

        mypkgcat = pkgcat
        mypkgname = pkgname
        virtual = False
        # if it's a PROVIDE, search with searchProvide
        # there's no package with that name
        if (not results) and (mypkgcat == "virtual"):

            virtuals = self.searchProvide(pkgkey, justid = True,
                get_extended = True)
            if virtuals:
                virtual = True
                flat_virtuals = []
                default_virtual = virtuals[0][0]
                # look for default old-style virtual
                for v_id, v_is_default in virtuals:
                    if v_is_default == 1:
                        default_virtual = v_id
                    flat_virtuals.append(v_id)
                mypkgname = self.retrieveName(default_virtual)
                mypkgcat = self.retrieveCategory(default_virtual)
                results = flat_virtuals


        if not results: # nothing found
            return set()

        if len(results) > 1: # need to choose

            # if it's because category differs, it's a problem
            foundCat = None
            cats = set()
            for idpackage in results:
                cat = self.retrieveCategory(idpackage)
                cats.add(cat)
                if (cat == mypkgcat) or ((not virtual) and \
                    (mypkgcat == "virtual") and (cat == mypkgcat)):
                    # in case of virtual packages only
                    # (that they're not stored as provide)
                    foundCat = cat

            # if we found something at least...
            if (not foundCat) and (len(cats) == 1) and \
                (mypkgcat in ("virtual", "null")):

                foundCat = sorted(cats)[0]

            if not foundCat:
                # got the issue
                return set()

            # we can use foundCat
            mypkgcat = foundCat

            # we need to search using the category
            if (not multiMatch) and (pkgcat == "null" or virtual):
                # we searched by name, we need to search using category
                results = self.searchPackagesByNameAndCategory(
                    name = mypkgname, category = mypkgcat,
                    sensitive = caseSensitive, justid = True
                )

            # if we get here, we have found the needed IDs
            return set(results)

        ###
        ### just found one result
        ###

        idpackage = results[0]
        # if mypkgcat is virtual, it can be forced
        if (mypkgcat == "virtual") and (not virtual):
            # in case of virtual packages only
            # (that they're not stored as provide)
            mypkgcat = self.retrieveCategory(idpackage)

        # check if category matches
        if mypkgcat != "null":
            foundCat = self.retrieveCategory(idpackage)
            if mypkgcat == foundCat:
                return set([idpackage])
            return set() # nope nope

        # very good, here it is
        return set([idpackage])


    def __handle_found_ids_match(self, foundIDs, direction, matchTag,
            matchRevision, justname, strippedAtom, pkgversion):

        dbpkginfo = set()
        # now we have to handle direction
        if ((direction) or ((not direction) and (not justname)) or \
            ((not direction) and (not justname) \
                and strippedAtom.endswith("*"))) and foundIDs:

            if (not justname) and \
                ((direction == "~") or (direction == "=") or \
                ((not direction) and (not justname)) or ((not direction) and \
                    not justname and strippedAtom.endswith("*"))):
                # any revision within the version specified
                # OR the specified version

                if ((not direction) and (not justname)):
                    direction = "="

                # remove gentoo revision (-r0 if none)
                if (direction == "="):
                    if (pkgversion.split("-")[-1] == "r0"):
                        pkgversion = self.entropyTools.remove_revision(
                            pkgversion)

                if (direction == "~"):
                    pkgrevision = self.entropyTools.dep_get_spm_revision(
                        pkgversion)
                    pkgversion = self.entropyTools.remove_revision(pkgversion)

                for idpackage in foundIDs:

                    dbver = self.retrieveVersion(idpackage)
                    if (direction == "~"):
                        myrev = self.entropyTools.dep_get_spm_revision(
                            dbver)
                        myver = self.entropyTools.remove_revision(dbver)
                        if myver == pkgversion and pkgrevision <= myrev:
                            # found
                            dbpkginfo.add((idpackage, dbver))
                    else:
                        # media-libs/test-1.2* support
                        if pkgversion[-1] == "*":
                            if dbver.startswith(pkgversion[:-1]):
                                dbpkginfo.add((idpackage, dbver))
                        elif (matchRevision is not None) and (pkgversion == dbver):
                            dbrev = self.retrieveRevision(idpackage)
                            if dbrev == matchRevision:
                                dbpkginfo.add((idpackage, dbver))
                        elif (pkgversion == dbver) and (matchRevision is None):
                            dbpkginfo.add((idpackage, dbver))

            elif (direction.find(">") != -1) or (direction.find("<") != -1):

                if not justname:

                    # remove revision (-r0 if none)
                    if pkgversion.endswith("r0"):
                        # remove
                        self.entropyTools.remove_revision(pkgversion)

                    for idpackage in foundIDs:

                        revcmp = 0
                        tagcmp = 0
                        if matchRevision is not None:
                            dbrev = self.retrieveRevision(idpackage)
                            revcmp = const_cmp(matchRevision, dbrev)

                        if matchTag is not None:
                            dbtag = self.retrieveVersionTag(idpackage)
                            tagcmp = const_cmp(matchTag, dbtag)

                        dbver = self.retrieveVersion(idpackage)
                        pkgcmp = self.entropyTools.compare_versions(
                            pkgversion, dbver)

                        if pkgcmp is None:
                            import warnings
                            warnings.warn("WARNING, invalid version string " + \
                            "stored in %s: %s <-> %s" % (
                                self.dbname, pkgversion, dbver,)
                            )
                            continue

                        if direction == ">":

                            if pkgcmp < 0:
                                dbpkginfo.add((idpackage, dbver))
                            elif (matchRevision is not None) and pkgcmp <= 0 \
                                and revcmp < 0:
                                dbpkginfo.add((idpackage, dbver))

                            elif (matchTag is not None) and tagcmp < 0:
                                dbpkginfo.add((idpackage, dbver))

                        elif direction == "<":

                            if pkgcmp > 0:
                                dbpkginfo.add((idpackage, dbver))
                            elif (matchRevision is not None) and pkgcmp >= 0 \
                                and revcmp > 0:
                                dbpkginfo.add((idpackage, dbver))

                            elif (matchTag is not None) and tagcmp > 0:
                                dbpkginfo.add((idpackage, dbver))

                        elif direction == ">=":

                            if (matchRevision is not None) and pkgcmp <= 0:
                                if pkgcmp == 0:
                                    if revcmp <= 0:
                                        dbpkginfo.add((idpackage, dbver))
                                else:
                                    dbpkginfo.add((idpackage, dbver))
                            elif pkgcmp <= 0 and matchRevision is None:
                                dbpkginfo.add((idpackage, dbver))
                            elif (matchTag is not None) and tagcmp <= 0:
                                dbpkginfo.add((idpackage, dbver))

                        elif direction == "<=":

                            if (matchRevision is not None) and pkgcmp >= 0:
                                if pkgcmp == 0:
                                    if revcmp >= 0:
                                        dbpkginfo.add((idpackage, dbver))
                                else:
                                    dbpkginfo.add((idpackage, dbver))
                            elif pkgcmp >= 0 and matchRevision is None:
                                dbpkginfo.add((idpackage, dbver))
                            elif (matchTag is not None) and tagcmp >= 0:
                                dbpkginfo.add((idpackage, dbver))

        else: # just the key

            dbpkginfo = set([(x, self.retrieveVersion(x),) for x in foundIDs])

        return dbpkginfo
