# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework repository database prototype classes module}.
"""
import base64
import os
import shutil
import warnings
import hashlib
import codecs
import collections
import contextlib
import threading

from entropy.i18n import _
from entropy.exceptions import InvalidAtom
from entropy.const import etpConst, const_cmp, const_debug_write, \
    const_convert_to_rawstring, const_mkstemp, const_is_python3
from entropy.output import TextInterface, brown, bold, red, blue, purple, \
    darkred, darkgreen
from entropy.cache import EntropyCacher
from entropy.core import EntropyPluginStore
from entropy.core.settings.base import SystemSettings
from entropy.exceptions import RepositoryPluginError
from entropy.spm.plugins.factory import get_default_instance as get_spm, \
    get_default_class as get_spm_class
from entropy.db.exceptions import OperationalError
from entropy.db.cache import EntropyRepositoryCachePolicies

import entropy.dep
import entropy.tools

class EntropyRepositoryPlugin(object):
    """
    This is the base class for implementing EntropyRepository plugin hooks.
    You have to subclass this, implement not implemented methods and provide
    it to EntropyRepository class as described below.

    Every plugin hook function features this signature:
        int something_hook(entropy_repository_instance)
    Where entropy_repository_instance is the calling EntropyRepository instance.
    Every method should return a return status code which, when nonzero causes
    a RepositoryPluginError exception to be thrown.
    Every method returns 0 in the base class implementation.
    """

    def get_id(self):
        """
        Return string identifier of myself.

        @return: EntropyRepositoryPlugin identifier.
        @rtype: string
        """
        return str(self)

    def get_metadata(self):
        """
        Developers reimplementing EntropyRepositoryPlugin can provide metadata
        along with every instance.
        If you want to provide read-only metadata, this method should really
        return a copy of the metadata object, otherwise, return its direct
        reference.
        Metadata format is a map-like object (dictionary, dict()).
        By default this method does return an empty dict.
        Make sure that your metadata dictionaries around don't have keys in
        common, otherwise those will be randomly overwritten eachothers.

        @return: plugin metadata
        @rtype: dict
        """
        return {}

    def add_plugin_hook(self, entropy_repository_instance):
        """
        Called during EntropyRepository plugin addition.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def remove_plugin_hook(self, entropy_repository_instance):
        """
        Called during EntropyRepository plugin removal.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def commit_hook(self, entropy_repository_instance):
        """
        Called during EntropyRepository data commit.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def close_repo_hook(self, entropy_repository_instance):
        """
        Called during EntropyRepository instance shutdown (close()).

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def add_package_hook(self, entropy_repository_instance, package_id,
        package_data):
        """
        Called after the addition of a package from EntropyRepository.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @param package_id: Entropy repository package identifier
        @type package_id: int
        @param package_data: package metadata used for insertion
            (see addPackage)
        @type package_data: dict
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def remove_package_hook(self, entropy_repository_instance, package_id,
        from_add_package):
        """
        Called after the removal of a package from EntropyRepository.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @param package_id: Entropy repository package identifier
        @type package_id: int
        @param from_add_package: inform whether removePackage() is called inside
            addPackage()
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def clear_cache_hook(self, entropy_repository_instance):
        """
        Called during EntropyRepository cache cleanup (clearCache).

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def initialize_repo_hook(self, entropy_repository_instance):
        """
        Called during EntropyRepository data initialization (not instance init).

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def accept_license_hook(self, entropy_repository_instance):
        """
        Called during EntropyRepository acceptLicense call.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def treeupdates_move_action_hook(self, entropy_repository_instance,
        package_id):
        """
        Called after EntropyRepository treeupdates move action execution for
        given package_id in given EntropyRepository instance.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @param package_id: Entropy repository package identifier
        @type package_id: int
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def treeupdates_slot_move_action_hook(self, entropy_repository_instance,
        package_id):
        """
        Called after EntropyRepository treeupdates slot move action
        execution for given package_id in given EntropyRepository instance.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @param package_id: Entropy repository package identifier
        @type package_id: int
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

class EntropyRepositoryPluginStore(EntropyPluginStore):

    """
    EntropyRepository plugin interface. This is the EntropyRepository part
    aimed to handle connected plugins.
    """

    _PERMANENT_PLUGINS = {}

    def __init__(self):
        EntropyPluginStore.__init__(self)
        permanent_plugs = EntropyRepositoryPluginStore.get_permanent_plugins()
        for plug in permanent_plugs.values():
            plug.add_plugin_hook(self)

    def add_plugin(self, entropy_repository_plugin):
        """
        Overloaded from EntropyPluginStore, adds support for hooks execution.
        """
        inst = entropy_repository_plugin
        if not isinstance(inst, EntropyRepositoryPlugin):
            raise AttributeError("EntropyRepositoryPluginStore: " + \
                    "expected valid EntropyRepositoryPlugin instance")
        EntropyPluginStore.add_plugin(self, inst.get_id(), inst)
        inst.add_plugin_hook(self)

    def remove_plugin(self, plugin_id):
        """
        Overloaded from EntropyPluginStore, adds support for hooks execution.
        """
        plugins = self.get_plugins()
        plug_inst = plugins.get(plugin_id)
        if plug_inst is not None:
            plug_inst.remove_plugin_hook(self)
        return EntropyPluginStore.remove_plugin(self, plugin_id)

    @staticmethod
    def add_permanent_plugin(entropy_repository_plugin):
        """
        Add EntropyRepository permanent plugin. This plugin object will be
        used across all the instantiated EntropyRepositoryPluginStore classes.
        Each time a new instance is created, add_plugin_hook will be executed
        for all the permanent plugins.

        @param entropy_repository_plugin: EntropyRepositoryPlugin instance
        @type entropy_repository_plugin: EntropyRepositoryPlugin instance
        """
        inst = entropy_repository_plugin
        if not isinstance(inst, EntropyRepositoryPlugin):
            raise AttributeError("EntropyRepositoryPluginStore: " + \
                    "expected valid EntropyRepositoryPlugin instance")
        EntropyRepositoryPluginStore._PERMANENT_PLUGINS[inst.get_id()] = inst

    @staticmethod
    def remove_permanent_plugin(plugin_id):
        """
        Remove EntropyRepository permanent plugin. This plugin object will be
        removed across all the EntropyRepository instances around.
        Please note: due to the fact that there are no destructors around,
        the "remove_plugin_hook" callback won't be executed when calling this
        static method.

        @param plugin_id: EntropyRepositoryPlugin identifier
        @type plugin_id: string
        @raise KeyError: in case of unavailable plugin identifier
        """
        del EntropyRepositoryPluginStore._PERMANENT_PLUGINS[plugin_id]

    @staticmethod
    def get_permanent_plugins():
        """
        Return EntropyRepositoryStore installed permanent plugins.

        @return: copy of internal permanent plugins dict
        @rtype: dict
        """
        return EntropyRepositoryPluginStore._PERMANENT_PLUGINS.copy()

    def get_plugins(self):
        """
        Overloaded from EntropyPluginStore, adds support for permanent plugins.
        """
        plugins = EntropyPluginStore.get_plugins(self)
        plugins.update(EntropyRepositoryPluginStore.get_permanent_plugins())
        return plugins

    def get_plugins_metadata(self):
        """
        Return EntropyRepositoryPluginStore registered plugins metadata.

        @return: plugins metadata
        @rtype: dict
        """
        plugins = self.get_plugins()
        meta = {}
        for plugin_id in plugins:
            meta.update(plugins[plugin_id].get_metadata())
        return meta

    def get_plugin_metadata(self, plugin_id, key):
        """
        Return EntropyRepositoryPlugin metadata value referenced by "key".

        @param plugin_id. EntropyRepositoryPlugin identifier
        @type plugin_id: string
        @param key: EntropyRepositoryPlugin metadatum identifier
        @type key: string
        @return: metadatum value
        @rtype: any Python object
        @raise KeyError: if provided key or plugin_id is not available
        """
        plugins = self.get_plugins()
        return plugins[plugin_id][key]

    def set_plugin_metadata(self, plugin_id, key, value):
        """
        Set EntropyRepositoryPlugin stored metadata.

        @param plugin_id. EntropyRepositoryPlugin identifier
        @type plugin_id: string
        @param key: EntropyRepositoryPlugin metadatum identifier
        @type key: string
        @param value: value to set
        @type value: any valid Python object
        @raise KeyError: if plugin_id is not available
        """
        plugins = self.get_plugins()
        meta = plugins[plugin_id].get_metadata()
        meta[key] = value


class EntropyRepositoryBase(TextInterface, EntropyRepositoryPluginStore):
    """
    EntropyRepository interface base class.
    This is an abstact class containing abstract methods that
    subclasses need to reimplement.
    Every Entropy repository object has to inherit this class.
    """

    VIRTUAL_META_PACKAGE_CATEGORY = "virtual"
    # You can extend this with custom settings for your Repository
    SETTING_KEYS = ("arch", "schema_revision")

    class ModuleProxy(object):

        @staticmethod
        def get():
            """
            Lazily load the Repository module.
            """
            raise NotImplementedError()

        @staticmethod
        def exceptions():
            """
            Get the Repository exceptions module.
            """
            raise NotImplementedError()

        @staticmethod
        def errno():
            """
            Get the Repository errno module.
            """
            raise NotImplementedError()


    def __init__(self, readonly, xcache, temporary, name, direct=False,
                 cache_policy=None):
        """
        EntropyRepositoryBase constructor.

        @param readonly: readonly bit
        @type readonly: bool
        @param xcache: xcache bit (enable on-disk cache?)
        @type xcache: bool
        @param temporary: is this repo a temporary (non persistent) one?
        @type temporary: bool
        @param name: repository identifier (or name)
        @type name: string
        @keyword direct: True, if direct mode should be always enabled
        @type direct: bool
        """
        self._tls = threading.local()
        self._direct_enabled = direct
        if cache_policy is None:
            cache_policy = EntropyRepositoryCachePolicies.DEFAULT_CACHE_POLICY
        self._cache_policy = cache_policy

        TextInterface.__init__(self)
        self._readonly = readonly
        self._caching = xcache
        self._temporary = temporary
        self.name = name
        # backward compatibility
        self.reponame = name
        self._settings = SystemSettings()
        self._cacher = EntropyCacher()
        self.__db_match_cache_key = "match/db"

        EntropyRepositoryPluginStore.__init__(self)

    def lock_path(self):
        """
        Return the path of the file lock for this repository.
        """
        return os.path.join(
            etpConst['entropyrundir'],
            "repository", self.name + ".lock")

    @contextlib.contextmanager
    def direct(self):
        """
        Avoid acquiring any kind of lock, disable caches and access directly
        to the underlying repository data.

        In latency sensitive code paths, acquiring locks (especially file locks)
        and blocking may be impractical. This context manager makes possible to
        avoid that, at the price of returning stale or null data.

        This method uses Thread Local Storage. In order to determine if
        direct mode is enabled, just call directed().
        memory cache is not cleared by this method, but both shared() and
        exclusive() do that.
        Nested calls are reference counted, so it's possible to enter the
        direct() context more than once (in a nested way) without problems.

        This method exists because some subclasses may have implemented their
        own in-memory caches and if the locks aren't acquired, they may contain
        stale data. However, keeping the cache clear may result in a big
        performance penalty due to the fact that cold caches kill latency.
        """
        counter = getattr(self._tls, "_EntropyRepositoryCacheCounter", 0)
        self._tls._EntropyRepositoryCacheCounter = counter + 1

        try:
            yield
        finally:
            self._tls._EntropyRepositoryCacheCounter -= 1

    def cache_policy(self):
        """
        Return the currently set in-RAM cache policy.
        """
        return self._cache_policy

    def cache_policy_all(self):
        """
        Return whether the cache policy is EntropyRepositoryCachePolicies.ALL.
        """
        return self.cache_policy() == EntropyRepositoryCachePolicies.ALL

    def cache_policy_none(self):
        """
        Return whether the cache policy is EntropyRepositoryCachePolicies.NONE.
        """
        return self.cache_policy() == EntropyRepositoryCachePolicies.NONE

    def directed(self):
        """
        Return whether direct mode is enabled or not for the current thread.
        See direct() for more information.
        """
        if self._direct_enabled:
            return True
        return getattr(self._tls, "_EntropyRepositoryCacheCounter", 0) != 0

    @contextlib.contextmanager
    def shared(self):
        """
        Acquire a shared file lock for this repository (context manager).
        This is used for inter-process synchronization only.

        This locking infrastructure assumes that resources initialized during
        object instantiation are valid throughout the whole object lifecycle.
        If this is not the case, please synchronize using the Entropy Resources
        Lock.

        If direct mode is enabled, this method is a no-op.
        """
        opaque = None
        try:
            opaque = self.try_acquire_shared()
            if opaque is None:
                lock_path = self.lock_path()

                self.output(
                    "%s %s ..." % (
                        darkred(_("Acquiring shared lock on")),
                        darkgreen(lock_path),
                    ),
                    level = "warning", # use stderr, avoid breaking --quiet
                    back = True,
                    importance = 0)

                opaque = self.acquire_shared()

                self.output(
                    "%s %s" % (
                        darkred(_("Acquired shared lock on")),
                        darkgreen(lock_path),
                    ),
                    level = "warning", # use stderr, avoid breaking --quiet
                    back = True,
                    importance = 0)

            yield

        finally:
            if opaque is not None:
                self.release_shared(opaque)

    @contextlib.contextmanager
    def exclusive(self):
        """
        Acquire an exclusive file lock for this repository (context manager).
        This is used for inter-process synchronization only.

        This locking infrastructure assumes that resources initialized during
        object instantiation are valid throughout the whole object lifecycle.
        If this is not the case, please synchronize using the Entropy Resources
        Lock.

        If direct mode is enabled, this method is a no-op.
        """
        opaque = None
        try:
            opaque = self.try_acquire_exclusive()
            if opaque is None:
                lock_path = self.lock_path()

                self.output(
                    "%s %s ..." % (
                        darkred(_("Acquiring exclusive lock on")),
                        darkgreen(lock_path),
                    ),
                    level = "warning", # use stderr, avoid breaking --quiet
                    back = True,
                    importance = 0)

                opaque = self.acquire_exclusive()

                self.output(
                    "%s %s" % (
                        darkred(_("Acquired exclusive lock on")),
                        darkgreen(lock_path),
                    ),
                    level = "warning", # use stderr, avoid breaking --quiet
                    back = True,
                    importance = 0)

            yield

        finally:
            if opaque is not None:
                self.release_exclusive(opaque)

    def acquire_shared(self):
        """
        Acquire a shared file lock for this repository.
        This is used for inter-process synchronization only.

        This locking infrastructure assumes that resources initialized during
        object instantiation are valid throughout the whole object lifecycle.
        If this is not the case, please synchronize using the Entropy Resources
        Lock.

        The only effect of not using these synchronization methods is that
        stale results, incomplete results, None (in case of using a no
        longer valid package id, for instance) could be returned by methods.
        If your code can deal with such conditions, it is perfectly fine to
        avoid locking.

        If direct mode is enabled, this method is a no-op.

        This method can raise entropy.db.exceptions.LockAcquireError in
        case of lock acquisition errors.

        @return: an opaque that must be used to release the lock.
        @rtype: object
        """
        raise NotImplementedError()

    def acquire_exclusive(self):
        """
        Acquire an exclusive file lock for this repository.
        This is used for inter-process synchronization only.

        This locking infrastructure assumes that resources initialized during
        object instantiation are valid throughout the whole object lifecycle.
        If this is not the case, please synchronize using the Entropy Resources
        Lock.

        The only effect of not using these synchronization methods is that
        stale results, incomplete results, None (in case of using a no
        longer valid package id, for instance) could be returned by methods.
        If your code can deal with such conditions, it is perfectly fine to
        avoid locking.

        If direct mode is enabled, this method is a no-op.

        This method can raise entropy.db.exceptions.LockAcquireError in
        case of lock acquisition errors.

        @return: an opaque that must be used to release the lock.
        @rtype: object
        """
        raise NotImplementedError()

    def try_acquire_shared(self):
        """
        Try to acquire a shared file lock for this repository.
        This is used for inter-process synchronization only.

        This locking infrastructure assumes that resources initialized during
        object instantiation are valid throughout the whole object lifecycle.
        If this is not the case, please synchronize using the Entropy Resources
        Lock.

        The only effect of not using these synchronization methods is that
        stale results, incomplete results, None (in case of using a no
        longer valid package id, for instance) could be returned by methods.
        If your code can deal with such conditions, it is perfectly fine to
        avoid locking.

        If direct mode is enabled, this method is a no-op.

        This method can raise entropy.db.exceptions.LockAcquireError in
        case of lock acquisition errors.

        @return: an opaque object that must be used to release the lock, None
            otherwise.
        @rtype: object or None
        """
        raise NotImplementedError()

    def try_acquire_exclusive(self):
        """
        Try to acquire an exclusive file lock for this repository.
        This is used for inter-process synchronization only.

        This locking infrastructure assumes that resources initialized during
        object instantiation are valid throughout the whole object lifecycle.
        If this is not the case, please synchronize using the Entropy Resources
        Lock.

        The only effect of not using these synchronization methods is that
        stale results, incomplete results, None (in case of using a no
        longer valid package id, for instance) could be returned by methods.
        If your code can deal with such conditions, it is perfectly fine to
        avoid locking.

        If direct mode is enabled, this method is a no-op.

        This method can raise entropy.db.exceptions.LockAcquireError in
        case of lock acquisition errors.

        @return: an opaque object that must be used to release the lock, None
            otherwise.
        @rtype: object or None
        """
        raise NotImplementedError()

    def release_shared(self, opaque):
        """
        Release the previously acquired shared file lock for this repository.
        This is used for inter-process synchronization only.

        Make sure to commit any pending transaction before releasing the lock.

        The only effect of not using these synchronization methods is that
        stale results, incomplete results, None (in case of using a no
        longer valid package id, for instance) could be returned by methods.
        If your code can deal with such conditions, it is perfectly fine to
        avoid locking.

        If direct mode is enabled, this method is a no-op.

        @param opaque: the opaque object returned by *acquire_shared methods.
        @type opaque: object
        """
        raise NotImplementedError()

    def release_exclusive(self, opaque):
        """
        Release the previously acquired exclusive file lock for this repository.
        This is used for inter-process synchronization only.

        Make sure to commit any pending transaction before releasing the lock.

        The only effect of not using these synchronization methods is that
        stale results, incomplete results, None (in case of using a no
        longer valid package id, for instance) could be returned by methods.
        If your code can deal with such conditions, it is perfectly fine to
        avoid locking.

        If direct mode is enabled, this method is a no-op.

        This method can raise entropy.db.exceptions.LockAcquireError in
        case of lock acquisition errors.

        @param opaque: the opaque object returned by *acquire_exclusive methods.
        @type opaque: object
        """
        raise NotImplementedError()

    def caching(self):
        """
        Return whether caching is enabled in this repository.

        @return: True, if caching is enabled
        @rtype: bool
        """
        return self._caching

    def temporary(self):
        """
        Return wheter the repository is temporary (in-memory, for example).

        @return: True, if repository is temporary
        @rtype: bool
        """
        return self._temporary

    def readonly(self):
        """
        Return whether the repository is read-only.
        This method shall always check real access
        permissions.

        @return: True, if repository is read-only
        @rtype: bool
        """
        return self._readonly

    def repository_id(self):
        """
        Return the repository identifier assigned to this instance.

        @return: the repository identifier
        @rtype: string
        """
        return self.name

    def close(self, safe=False):
        """
        Close repository storage communication and open disk files.
        You can still use this instance, but closed files will be reopened.
        Attention: call this method from your subclass, otherwise
        EntropyRepositoryPlugins won't be notified of a repo close.

        @param safe: if True, the MainThread resources won't be
        released. This is vital if both MainThread and a random
        thread access the Repository concurrently. With safe=False
        (original behaviour) MainThread cursors may become invalid
        and cause random exceptions in a racey fashion.
        But on the other hand, if closing all the resources is what
        is really wanted, safe must be False, or the MainThread ones
        will be never released.
        @type safe: bool
        """
        if not self._readonly:
            self.commit()

        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.close_repo_hook(self)
            if exec_rc:
                raise RepositoryPluginError(
                    "[close_repo_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

    def vacuum(self):
        """
        Repository storage cleanup and optimization function.
        """
        raise NotImplementedError()

    def commit(self, force = False, no_plugins = False):
        """
        Commit actual changes and make them permanently stored.
        Attention: call this method from your subclass, otherwise
        EntropyRepositoryPlugins won't be notified.

        @keyword force: force commit, despite read-only bit being set
        @type force: bool
        @keyword no_plugins: disable EntropyRepository plugins execution
        @type no_plugins: bool
        """
        if no_plugins:
            return

        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.commit_hook(self)
            if exec_rc:
                raise RepositoryPluginError("[commit_hook] %s: status: %s" % (
                    plug_inst.get_id(), exec_rc,))

    def rollback(self):
        """
        Rollback last transaction, if it hasn't been already committed.
        """
        raise NotImplementedError()

    def initializeRepository(self):
        """
        This method (re)initializes the repository, dropping all its content.
        Attention: call this method from your subclass, otherwise
        EntropyRepositoryPlugins won't be notified (AT THE END).
        """
        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.initialize_repo_hook(self)
            if exec_rc:
                raise RepositoryPluginError(
                    "[initialize_repo_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

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

        # pre-filter:
        # discard any f(a -> b) if f(b -> a)
        filtered_actions = collections.OrderedDict()
        filtered_cache = set()
        for action in actions:

            # filter duplicates
            if action in filtered_cache:
                continue
            filtered_cache.add(action)

            parts = action.split()
            try:
                cmd, args = parts[0], parts[1:]
            except (IndexError, ValueError):
                entropy.tools.print_traceback()
                continue

            action_key = (cmd, tuple(sorted(args)))
            filtered_action = filtered_actions.get(action_key)
            if filtered_action is None:
                filtered_actions[action_key] = (action, cmd, args)
                continue

            # cases:
            # a -> b and a -> b already stored: skip
            # a -> b and b -> a already stored: replace
            _ignore, _ignore, act_args = filtered_action
            replace = False
            if act_args == args:
                # a -> b and a -> b already stored
                # this is unlikely to happen, but better safe than sorry
                pass
            elif cmd == "move":
                replace = args == list(reversed(act_args))
            elif cmd == "slotmove":
                dep, from_slot, to_slot = args
                replace = [dep, to_slot, from_slot] == act_args

            if replace:
                const_debug_write(__name__, "%s: replacing: %s with %s" % (
                    self.name, act_args, args))
                # a -> b and b -> a already stored
                del filtered_actions[action_key]  # discard order
                filtered_actions[action_key] = (action, cmd, args)

        new_actions = []
        pkg_id_slotmove_actions = {}
        for action_key in filtered_actions:

            action, cmd, args = filtered_actions[action_key]
            if action in new_actions: # skip dupies
                continue

            if cmd == "slotmove":

                # slot move
                atom, from_slot, to_slot = args
                atom_key = entropy.dep.dep_getkey(atom)
                category = atom_key.split("/")[0]
                matches, sm_rc = self.atomMatch(atom, matchSlot = from_slot,
                    multiMatch = True, maskFilter = False)

                if sm_rc == 1:
                    # before giving up, check if we scheduled another
                    # slotmove that undoes it, use to_slot.
                    # This is a PMS violation, but on 2013-12-18 it was found
                    # that somebody managed to commit this.
                    # 2Q-2013: profiles/updates/2Q-2013?r1=1.1&r2=1.2
                    # 4Q-2013: profiles/updates/4Q-2013?r1=1.1&r2=1.2
                    matches, sm_rc = self.atomMatch(
                        atom, matchSlot = to_slot,
                        multiMatch = True, maskFilter = False)

                    for package_id in matches:
                        pkg_slotmove = pkg_id_slotmove_actions.get(package_id)
                        if pkg_slotmove is None:
                            continue
                        (old_from_slot, old_to_slot, old_action) = pkg_slotmove
                        if (to_slot, from_slot) == (old_from_slot, old_to_slot):
                            # bingo, this is a PMS violation we need to deal
                            # with.
                            self.output(
                                "QA: '%s' overrides an old slotmove (%s)" % (
                                    action, old_action),
                                importance = 1,
                                level = "error",
                                header = darkred(" !!! ")
                            )
                            try:
                                new_actions.remove(old_action)
                            except ValueError:
                                pass

                    continue

                if sm_rc == 1:
                    # nothing found in repo that matches atom
                    # this means that no packages can effectively
                    # reference to it
                    continue

                found = False
                # found atoms, check category
                for package_id in matches:
                    myslot = self.retrieveSlot(package_id)
                    mycategory = self.retrieveCategory(package_id)
                    if mycategory == category:
                        if  (myslot != to_slot) and \
                        (action not in new_actions):
                            pkg_id_slotmove_actions[package_id] = (
                                from_slot, to_slot, action)

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
                    and entropy.dep.dep_getkey(x) == atom_key]
                if dep_atoms:
                    new_actions.append(action)

            elif cmd == "move":

                atom = args[0]  # usually a key
                atom_key = entropy.dep.dep_getkey(atom)
                category = atom_key.split("/")[0]
                matches, m_rc = self.atomMatch(atom, multiMatch = True,
                    maskFilter = False)
                if m_rc == 1:
                    # nothing found in repo that matches atom
                    # this means that no packages can effectively
                    # reference to it
                    continue
                found = False
                for package_id in matches:
                    mycategory = self.retrieveCategory(package_id)
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
                    entropy.dep.dep_getkey(x) == atom_key]
                if dep_atoms:
                    new_actions.append(action)

        return new_actions

    def handlePackage(self, pkg_data, revision = None,
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
                'config_protect_mask': 'string string', 'etpapi': 3,
                'mirrorlinks': [],
                'cxxflags': '-Os -march=x86-64 -pipe',
                'injected': False,
                'licensedata': {'ZLIB': u"lictext"},
                'pkg_dependencies': tuple(),
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
                'provide_extended': set([]),
                'trigger': 'text',
                'counter': 22331,
                'branch': '4',
                'content': {},
                'content_safety': {},
                'needed_libs': [('/usr/bin/foo', 'foo', 'libc.so.6', 2, '')],
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
        @keyword revision: force a specific package revision
        @type revision: int
        @keyword formattedContent: tells whether content metadata is already
            formatted for insertion
        @type formattedContent: bool
        @return: package identifier
        @rtype: int
        """
        raise NotImplementedError()

    def getPackagesToRemove(self, name, category, slot, injected):
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

        @return: list (set) of removable packages (package_ids)
        @rtype: set
        """
        removelist = set()
        if injected:
            # read: if package has been injected, we'll skip
            # the removal of packages in the same slot,
            # usually used server side btw
            return removelist

        searchsimilar = self.searchNameCategory(name, category)

        # support for expiration-based packages handling, also internally
        # called Fat Scope.
        filter_similar = False
        srv_ss_plg = etpConst['system_settings_plugins_ids']['server_plugin']
        srv_ss_fs_plg = \
            etpConst['system_settings_plugins_ids']['server_plugin_fatscope']

        srv_plug_settings = self._settings.get(srv_ss_plg)
        if srv_plug_settings is not None:
            if srv_plug_settings['server']['exp_based_scope']:
                # in case support is enabled, return an empty set
                filter_similar = True

        if filter_similar:
            # filter out packages in the same scope that are allowed to stay
            idpkgs = self._settings[srv_ss_fs_plg]['repos'].get(
                self.name)
            if idpkgs:
                if -1 in idpkgs:
                    searchsimilar = []
                else:
                    searchsimilar = [x for x in searchsimilar if x[1] \
                        not in idpkgs]

        for atom, package_id in searchsimilar:
            # get the package slot
            myslot = self.retrieveSlot(package_id)
            # we merely ignore packages with
            # negative counters, since they're the injected ones
            if self.isInjected(package_id):
                continue
            if slot == myslot:
                # remove!
                removelist.add(package_id)

        return removelist

    def addPackage(self, pkg_data, revision = -1, package_id = None,
        formatted_content = False):
        """
        Add package to this Entropy repository. The main difference between
        handlePackage and this is that from here, no packages are going to be
        removed, in any case.
        For more information about pkg_data layout, please see
        I{handlePackage()}.
        Attention: call this method from your subclass (AT THE END), otherwise
        EntropyRepositoryPlugins won't be notified.

        @param pkg_data: Entropy package metadata
        @type pkg_data: dict
        @keyword revision: force a specific Entropy package revision
        @type revision: int
        @keyword package_id: add package to Entropy repository using the
            provided package identifier, this is very dangerous and could
            cause packages with the same identifier to be removed.
        @type package_id: int
        @keyword formatted_content: if True, determines whether the content
            metadata (usually the biggest part) in pkg_data is already
            prepared for insertion
        @type formatted_content: bool
        @return: new package identifier
        @rtype: int
        """
        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.add_package_hook(self, package_id, pkg_data)
            if exec_rc:
                raise RepositoryPluginError(
                    "[add_package_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

    def removePackage(self, package_id, from_add_package = False):
        """
        Remove package from this Entropy repository using it's identifier
        (package_id).
        Attention: call this method from your subclass, otherwise
        EntropyRepositoryPlugins won't be notified.

        @param package_id: Entropy repository package indentifier
        @type package_id: int
        @keyword from_add_package: inform function that it's being called from
            inside addPackage().
        @type from_add_package: bool
        """
        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.remove_package_hook(self, package_id,
                from_add_package)
            if exec_rc:
                raise RepositoryPluginError(
                    "[remove_package_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

    def setInjected(self, package_id):
        """
        Mark package as injected, injection is usually set for packages
        manually added to repository. Injected packages are not removed
        automatically even when featuring conflicting scope with other
        that are being added. If a package is injected, it means that
        maintainers have to handle it manually.

        @param package_id: package indentifier
        @type package_id: int
        """
        raise NotImplementedError()

    def setCreationDate(self, package_id, date):
        """
        Update the creation date for package. Creation date is stored in
        string based unix time format.

        @param package_id: package indentifier
        @type package_id: int
        @param date: unix time in string form
        @type date: string
        """
        raise NotImplementedError()

    def setDigest(self, package_id, digest):
        """
        Set package file md5sum for package. This information is used
        by entropy.client when downloading packages.

        @param package_id: package indentifier
        @type package_id: int
        @param digest: md5 hash for package file
        @type digest: string
        """
        raise NotImplementedError()

    def setSignatures(self, package_id, sha1, sha256, sha512, gpg = None):
        """
        Set package file extra hashes (sha1, sha256, sha512) for package.

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
        raise NotImplementedError()

    def setDownloadURL(self, package_id, url):
        """
        Set download URL prefix for package.

        @param package_id: package indentifier
        @type package_id: int
        @param url: URL prefix to set
        @type url: string
        """
        raise NotImplementedError()

    def setName(self, package_id, name):
        """
        Set name for package.

        @param package_id: package indentifier
        @type package_id: int
        @param name: package name
        @type name: string
        """
        raise NotImplementedError()

    def setAtom(self, package_id, atom):
        """
        Set atom string for package. "Atom" is the full, unique name of
        a package.

        @param package_id: package indentifier
        @type package_id: int
        @param atom: atom string
        @type atom: string
        """
        raise NotImplementedError()

    def setSlot(self, package_id, slot):
        """
        Set slot string for package. Please refer to Portage SLOT documentation
        for more info.

        @param package_id: package indentifier
        @type package_id: int
        @param slot: slot string
        @type slot: string
        """
        raise NotImplementedError()

    def setDependency(self, iddependency, dependency):
        """
        Set dependency string for iddependency (dependency identifier).

        @param iddependency: dependency string identifier
        @type iddependency: int
        @param dependency: dependency string
        @type dependency: string
        """
        raise NotImplementedError()

    def setCategory(self, package_id, category):
        """
        Set category name for package.

        @param package_id: package indentifier
        @type package_id: int
        @param category: category to set
        @type category: string
        """
        raise NotImplementedError()

    def setCategoryDescription(self, category, description_data):
        """
        Set description for given category name.

        @param category: category name
        @type category: string
        @param description_data: category description for several locales.
            {'en': "This is blah", 'it': "Questo e' blah", ... }
        @type description_data: dict
        """
        raise NotImplementedError()

    def setRevision(self, package_id, revision):
        """
        Set Entropy revision for package.

        @param package_id: package indentifier
        @type package_id: int
        @param revision: new revision
        @type revision: int
        """
        raise NotImplementedError()

    def setContentSafety(self, package_id, content_safety):
        """
        Set (overwriting previous entries) new content safety metadata.

        @param package_id: package indentifier
        @type package_id: int
        @param content_safety: dictionary with the same data structure of the
            one returned by retrieveContentSafety()
        @type content_safety: dict
        """
        raise NotImplementedError()

    def removeDependencies(self, package_id):
        """
        Remove all the dependencies of package.

        @param package_id: package indentifier
        @type package_id: int
        """
        raise NotImplementedError()

    def insertDependencies(self, package_id, depdata):
        """
        Insert dependencies for package. "depdata" is a dict() with dependency
        strings as keys and dependency type as values or a sequence of tuples
        composed by (dep, dep type).

        @param package_id: package indentifier
        @type package_id: int
        @param depdata: dependency dictionary
            {'app-foo/foo': dep_type_integer, ...}
        @type depdata: dict
        """
        raise NotImplementedError()

    def removeConflicts(self, package_id):
        """
        Remove all the conflicts of package.

        @param package_id: package indentifier
        @type package_id: int
        """
        raise NotImplementedError()

    def insertConflicts(self, package_id, conflicts):
        """
        Insert dependency conflicts for package.

        @param package_id: package indentifier
        @type package_id: int
        @param conflicts: list of dep. conflicts
        @type conflicts: list
        """
        raise NotImplementedError()

    def insertContent(self, package_id, content, already_formatted = False):
        """
        Insert content metadata for package. "content" can either be a dict()
        or a list of triples (tuples of length 3, (package_id, path, type,)).
        This method expects Unicode strings. Passing 8-bit raw strings will
        cause unpredictable results.

        @param package_id: package indentifier
        @type package_id: int
        @param content: content metadata to insert.
            {'/path/to/foo': 'obj(content type)',}
            or
            [(package_id, path, type,) ...]
        @type content: dict, list
        @keyword already_formatted: if True, "content" is expected to be
            already formatted for insertion, this means that "content" must be
            a list of tuples of length 3.
        @type already_formatted: bool
        """
        raise NotImplementedError()

    def insertAutomergefiles(self, package_id, automerge_data):
        """
        Insert configuration files automerge information for package.
        "automerge_data" contains configuration files paths and their belonging
        md5 hash.
        This features allows entropy.client to "auto-merge" or "auto-remove"
        configuration files never touched by user.
        This method expects Unicode strings. Passing 8-bit raw strings will
        cause unpredictable results.

        @param package_id: package indentifier
        @type package_id: int
        @param automerge_data: list of tuples of length 2.
            [('/path/to/conf/file', 'md5_checksum_string',) ... ]
        @type automerge_data: list
        """
        raise NotImplementedError()

    def insertPreservedLibrary(self, library, elfclass, path, atom):
        """
        Mark a library as preserved.

        @param library: the library name (SONAME)
        @type library: string
        @param elfclass: the ELF class of the library
        @type elfclass: int
        @param path: the path where the library is currently stored
        @param atom: the atom string of the package providing the library
        @type atom: string
        """
        raise NotImplementedError()

    def removePreservedLibrary(self, library, elfclass, path):
        """
        Remove a previously library marked as preserved.

        @param library: the library name (SONAME)
        @type library: string
        @param elfclass: the ELF class of the library
        @type elfclass: int
        @param path: the path where the library is currently stored
        """
        raise NotImplementedError()

    def listAllPreservedLibraries(self):
        """
        Return a list of all the recorded preserved libraries.

        @return: a list (tuple) of tuples composed by
            (library, elfclass, path, atom).
        @rtype: tuple
        """
        raise NotImplementedError()

    def retrievePreservedLibraries(self, library, elfclass):
        """
        Return a list of paths associated with the given preserved library,
        if any.

        @return: the list (tuple) of paths associated with a SONAME
            and its ELF class.
        @rtype: frozenset
        """
        raise NotImplementedError()

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
        raise NotImplementedError()

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
        raise NotImplementedError()

    def insertSpmUid(self, package_id, spm_package_uid):
        """
        Insert Source Package Manager unique package identifier and bind it
        to Entropy package identifier given (package_id). This method is used
        by Entropy Client and differs from "_bindSpmPackageUid" because
        any other colliding package_id<->uid binding is overwritten by design.

        @param package_id: package indentifier
        @type package_id: int
        @param spm_package_uid: Source package Manager unique package identifier
        @type spm_package_uid: int
        """
        raise NotImplementedError()

    def setTrashedUid(self, spm_package_uid):
        """
        Mark given Source Package Manager unique package identifier as
        "trashed". This is a trick to allow Entropy Server to support
        multiple repositories and parallel handling of them without
        make it messing with removed packages from the underlying system.

        @param spm_package_uid: Source package Manager unique package identifier
        @type spm_package_uid: int
        """
        raise NotImplementedError()

    def removeTrashedUids(self, spm_package_uids):
        """
        Remove given Source Package Manager unique package identifiers from
        the "trashed" list. This is only used by Entropy Server.
        """
        raise NotImplementedError()

    def setSpmUid(self, package_id, spm_package_uid, branch = None):
        """
        Update Source Package Manager unique package identifier for given
        Entropy package identifier (package_id).
        This method *only* updates a currently available binding setting a new
        "spm_package_uid"

        @param package_id: package indentifier
        @type package_id: int
        @param spm_package_uid: Source package Manager unique package identifier
        @type spm_package_uid: int
        @keyword branch: current Entropy repository branch
        @type branch: string
        """
        raise NotImplementedError()

    def contentDiff(self, package_id, dbconn, dbconn_package_id,
                    extended = False):
        """
        Return content metadata difference between two packages.

        @param package_id: package indentifier available in this repository
        @type package_id: int
        @param dbconn: other repository class instance
        @type dbconn: EntropyRepository
        @param dbconn_package_id: package identifier available in other
            repository
        @type dbconn_package_id: int
        @keyword extended: also return filetype (it is not considered in
           the comparison)
        @type extended: bool
        @return: content difference
        @rtype: frozenset
        @raise AttributeError: when self instance and dbconn are the same
        """
        raise NotImplementedError()

    def clean(self):
        """
        Run repository metadata cleanup over unused references.
        """
        raise NotImplementedError()

    def getDependency(self, iddependency):
        """
        Return dependency string for given dependency identifier.

        @param iddependency: dependency identifier
        @type iddependency: int
        @return: dependency string
        @rtype: string or None
        """
        raise NotImplementedError()

    def getFakeSpmUid(self):
        """
        Obtain auto-generated available negative Source Package Manager
        package identifier.

        @return: new negative spm uid
        @rtype: int
        """
        raise NotImplementedError()

    def getApi(self):
        """
        Get Entropy repository API.

        @return: Entropy repository API
        @rtype: int
        """
        raise NotImplementedError()

    def getPackageIds(self, atom):
        """
        Obtain repository package identifiers from atom string.

        @param atom: package atom
        @type atom: string
        @return: list of matching package_ids found
        @rtype: frozenset
        """
        raise NotImplementedError()

    def getPackageIdFromDownload(self, download_relative_path,
        endswith = False):
        """
        Obtain repository package identifier from its relative download path
        string.

        @param download_relative_path: relative download path string returned
            by "retrieveDownloadURL" method
        @type download_relative_path: string
        @keyword endswith: search for package_id which download metadata ends
            with the one provided by download_relative_path
        @type endswith: bool
        @return: package_id in repository or -1 if not found
        @rtype: int
        """
        raise NotImplementedError()

    def getVersioningData(self, package_id):
        """
        Get package version information for provided package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: tuple of length 3 composed by (version, tag, revision,)
            belonging to package_id
        @rtype: tuple
        """
        raise NotImplementedError()

    def getStrictData(self, package_id):
        """
        Get a restricted (optimized) set of package metadata for provided
        package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: tuple of length 6 composed by
            (package key, slot, version, tag, revision, atom)
            belonging to package_id
        @rtype: tuple
        """
        raise NotImplementedError()

    def getStrictScopeData(self, package_id):
        """
        Get a restricted (optimized) set of package metadata for provided
        identifier that can be used to determine the scope of package.

        @param package_id: package indentifier
        @type package_id: int
        @return: tuple of length 3 composed by (atom, slot, revision,)
            belonging to package_id
        @rtype: tuple
        """
        raise NotImplementedError()

    def getScopeData(self, package_id):
        """
        Get a set of package metadata for provided identifier that can be
        used to determine the scope of package.

        @param package_id: package indentifier
        @type package_id: int
        @return: tuple of length 9 composed by
            (atom, category name, name, version,
                slot, tag, revision, branch, api,)
            belonging to package_id
        @rtype: tuple
        """
        raise NotImplementedError()

    def getBaseData(self, package_id):
        """
        Get a set of basic package metadata for provided package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: tuple of length 19 composed by
            (atom, name, version, tag, description, category name, CHOST,
            CFLAGS, CXXFLAGS, homepage, license, branch, download path, digest,
            slot, api, creation date, package size, revision,)
            belonging to package_id
        @rtype: tuple
        """
        raise NotImplementedError()

    def getTriggerData(self, package_id, content = True):
        """
        Get a set of basic package metadata for provided package identifier.
        This method is optimized to work with Entropy Client installation
        triggers returning only what is strictly needed.

        @param package_id: package indentifier
        @type package_id: int
        @keyword content: if True, grabs the "content" metadata too, othewise
            such dict key value will be shown as empty set().
        @type content: bool
        @return: dictionary containing package metadata

            data = {
                'atom': atom,
                'category': category,
                'name': name,
                'version': version,
                'slot': slot,
                'versiontag': versiontag,
                'revision': revision,
                'branch': branch,
                'chost': chost,
                'cflags': cflags,
                'cxxflags': cxxflags,
                'etpapi': etpapi,
                'trigger': self.retrieveTrigger(package_id),
                'content': pkg_content,
                'spm_phases': self.retrieveSpmPhases(package_id),
            }

        @rtype: dict or None
        """
        scope_data = self.getScopeData(package_id)
        if scope_data is None:
            return
        atom, category, name, \
        version, slot, versiontag, \
        revision, branch, etpapi = scope_data
        chost, cflags, cxxflags = self.retrieveCompileFlags(package_id)

        pkg_content = set()
        if content:
            pkg_content = self.retrieveContent(package_id)

        data = {
            'atom': atom,
            'category': category,
            'name': name,
            'version': version,
            'slot': slot,
            'versiontag': versiontag,
            'revision': revision,
            'branch': branch,
            'chost': chost,
            'cflags': cflags,
            'cxxflags': cxxflags,
            'etpapi': etpapi,
            'trigger': self.retrieveTrigger(package_id),
            'content': pkg_content,
            'spm_phases': self.retrieveSpmPhases(package_id),
        }
        return data

    def getPackageData(self, package_id, get_content = True,
            content_insert_formatted = False, get_changelog = True,
            get_content_safety = True):
        """
        Reconstruct all the package metadata belonging to provided package
        identifier into a dict object.

        @param package_id: package indentifier
        @type package_id: int
        @keyword get_content:
        @type get_content: bool
        @keyword content_insert_formatted:
        @type content_insert_formatted: bool
        @keyword get_changelog:  return ChangeLog text metadatum or None
        @type get_changelog: bool
        @keyword get_content_safety: return content_safety metadata or {}
        @type get_content_safety: bool
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
            'counter': self.retrieveSpmUid(package_id),
            'trigger': self.retrieveTrigger(package_id),
            'disksize': self.retrieveOnDiskSize(package_id),
            'changelog': self.retrieveChangelog(package_id),
            'injected': self.isInjected(package_id),
            'systempackage': self.isSystemPackage(package_id),
            'config_protect': self.retrieveProtect(package_id),
            'config_protect_mask': self.retrieveProtectMask(package_id),
            'useflags': self.retrieveUseflags(package_id),
            'keywords': self.retrieveKeywords(package_id),
            'sources': sources,
            'needed_libs': self.retrieveNeededLibraries(package_id)
            'provided_libs': self.retrieveProvidedLibraries(package_id),
            'provide_extended': self.retrieveProvide(package_id),
            'conflicts': self.retrieveConflicts(package_id),
            'licensedata': self.retrieveLicenseData(package_id),
            'content': content,
            'content_safety': {},
            'pkg_dependencies': self.retrieveDependencies(package_id,
                                                          extended = True),
            'mirrorlinks': [[x,self.retrieveMirrorData(x)] for x in mirrornames],
            'signatures': signatures,
            'spm_phases': self.retrieveSpmPhases(package_id),
            'spm_repository': self.retrieveSpmRepository(package_id),
            'desktop_mime': [],
            'provided_mime': [],
            'original_repository': self.getInstalledPackageRepository(package_id),
            'extra_download': self.retrieveExtraDownload(package_id),
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
            datecreation, size, revision  = self.getBaseData(package_id)
        except TypeError:
            return None

        content = {}
        if get_content:
            content = self.retrieveContent(
                package_id, extended = True,
                formatted = True, insert_formatted = content_insert_formatted
            )

        sources = self.retrieveSources(package_id)
        mirrornames = set()
        for x in sources:
            if x.startswith("mirror://"):
                mirrornames.add(x.split("/")[2])

        sha1, sha256, sha512, gpg = self.retrieveSignatures(package_id)
        signatures = {
            'sha1': sha1,
            'sha256': sha256,
            'sha512': sha512,
            'gpg': gpg,
        }

        changelog = None
        if get_changelog:
            changelog = self.retrieveChangelog(package_id)
        content_safety = {}
        if get_content_safety:
            content_safety = self.retrieveContentSafety(package_id)

        deps = self.retrieveDependencies(
            package_id, extended = True,
            resolve_conditional_deps = False)

        needed_libs = self.retrieveNeededLibraries(package_id)
        compat_needed_libs = tuple(
            sorted((soname, elfclass) for _x, _x, soname, elfclass, _x
                    in needed_libs)
        )

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
            'counter': self.retrieveSpmUid(package_id),
            'trigger': self.retrieveTrigger(package_id),
            'disksize': self.retrieveOnDiskSize(package_id),
            'changelog': changelog,
            'injected': self.isInjected(package_id),
            'systempackage': self.isSystemPackage(package_id),
            'config_protect': self.retrieveProtect(package_id),
            'config_protect_mask': self.retrieveProtectMask(package_id),
            'useflags': self.retrieveUseflags(package_id),
            'keywords': self.retrieveKeywords(package_id),
            'sources': sources,
            'needed': compat_needed_libs,
            'needed_libs': needed_libs,
            'provided_libs': self.retrieveProvidedLibraries(package_id),
            'provide_extended': self.retrieveProvide(package_id),
            'conflicts': self.retrieveConflicts(package_id),
            'licensedata': self.retrieveLicenseData(package_id),
            'content': content,
            'content_safety': content_safety,
            'pkg_dependencies': deps,
            'mirrorlinks': [[x, self.retrieveMirrorData(x)] for x in mirrornames],
            'signatures': signatures,
            'spm_phases': self.retrieveSpmPhases(package_id),
            'spm_repository': self.retrieveSpmRepository(package_id),
            'desktop_mime': self.retrieveDesktopMime(package_id),
            'provided_mime': self.retrieveProvidedMime(package_id),
            'original_repository': self.getInstalledPackageRepository(package_id),
            'extra_download': self.retrieveExtraDownload(package_id),
        }

        return data

    def getPackageXmlData(self, package_ids, get_content=True,
                          get_changelog=True, get_content_safety=True):
        """
        Generate the XML of the packages passed through package_ids. It is
        possible to validate the schema using either package.dtd or package.xsd.
        The returned string does not contain any xml header and the root tag is
        <packages>.
        Please note that the current implementation generates the
        XML tree in RAM and doesn't do any kind of "streaming".

        @param package_ids: list of package identifiers
        @type package_ids: list
        @keyword get_content: include the package content in the XML
        @type get_content: bool
        @keyword get_changelog: include the package changelog in the XML
        @type get_changelog: bool
        @keyword get_content_safety: include the content safety metadata in the
            XML
        @type get_content_safety: bool
        @return: valid XML data
        @rtype: string
        """
        from xml.dom import minidom
        doc = minidom.Document()
        packages = doc.createElement("packages")
        source_mirror_id = 1
        source_mirrors = {}
        package_changelogs_id = 1
        package_changelogs = {}

        for package_id in package_ids:
            data = self.getPackageData(
                package_id, get_content = get_content,
                get_changelog = get_changelog,
                get_content_safety = get_content_safety)

            package = doc.createElement("package")
            package.setAttribute("id", "id-%d" % (package_id,))

            is_system = "false"
            if data['systempackage']:
                is_system = "true"
            package.setAttribute("system", is_system)

            is_injected = "false"
            if data['injected']:
                is_injected = "true"
            package.setAttribute("injected", is_injected)

            package.setAttribute("creationdate", data['datecreation'])
            package.setAttribute("etpapi", "%d" % (data['etpapi'],))
            package.setAttribute("spm-repository", data['spm_repository'])

            atom = doc.createElement("atom")
            atom.appendChild(doc.createTextNode(data['atom']))
            package.appendChild(atom)

            category = doc.createElement("category")
            category.appendChild(doc.createTextNode(data['category']))
            package.appendChild(category)

            name = doc.createElement("name")
            name.appendChild(doc.createTextNode(data['name']))
            name.setAttribute("natural-name", data['name'].capitalize())
            package.appendChild(name)

            version = doc.createElement("version")
            version.appendChild(doc.createTextNode(data['version']))
            package.appendChild(version)

            if data['versiontag']:
                versiontag = doc.createElement("versiontag")
                versiontag.appendChild(doc.createTextNode(data['versiontag']))
                package.appendChild(versiontag)

            revision = doc.createElement("revision")
            revision.appendChild(doc.createTextNode("%d" % (data['revision'],)))
            package.appendChild(revision)

            branch = doc.createElement("branch")
            branch.appendChild(doc.createTextNode(data['branch']))
            package.appendChild(branch)

            slot = doc.createElement("slot")
            slot.appendChild(doc.createTextNode(data['slot']))
            package.appendChild(slot)

            lics = data['license'].split()
            lic_data = data['licensedata']
            licenses = doc.createElement("licenses")
            for lic in lics:
                lic_el = doc.createElement("license")

                lic_text = lic_data.get(lic, " ")
                if lic_text:
                    lic_text = base64.b64encode(
                        const_convert_to_rawstring(
                            lic_text, from_enctype = "utf-8"))
                    lic_el.appendChild(doc.createTextNode(lic_text))
                lic_el.setAttribute("name", lic)
                lic_el.setAttribute("enc", "base64")
                licenses.appendChild(lic_el)
            if lics:
                package.appendChild(licenses)

            if data['trigger']:
                trigger = doc.createElement("trigger")
                trigger.appendChild(doc.createTextNode(
                    base64.b64encode(data['trigger'])))
                package.appendChild(trigger)

            description = doc.createElement("description")
            description.appendChild(doc.createTextNode(data['description']))
            package.appendChild(description)

            homepage = doc.createElement("homepage")
            homepage.appendChild(doc.createTextNode(data['homepage']))
            package.appendChild(homepage)

            size = doc.createElement("size")
            size.appendChild(doc.createTextNode("%s" % (data['size'],)))
            package.appendChild(size)

            chost = doc.createElement("chost")
            chost.appendChild(doc.createTextNode(data['chost']))
            package.appendChild(chost)

            cflags = doc.createElement("cflags")
            cflags.appendChild(doc.createTextNode(data['cflags']))
            package.appendChild(cflags)

            cxxflags = doc.createElement("cxxflags")
            cxxflags.appendChild(doc.createTextNode(data['cxxflags']))
            package.appendChild(cxxflags)

            content = doc.createElement("content")
            if data['content']:
                for path in sorted(data['content']):
                    con_type = data['content'][path]
                    path_el = doc.createElement("path")
                    path_el.setAttribute("type", con_type)
                    path_cs = data['content_safety'].get(path)
                    if path_cs:
                        path_el.setAttribute(
                            "mtime", "%f" % (path_cs['mtime'],))
                        path_el.setAttribute("sha256", path_cs['sha256'])
                    path_el.appendChild(doc.createTextNode(path))
                    content.appendChild(path_el)
                package.appendChild(content)

            provides = doc.createElement("provides")
            if data['provide_extended']:
                for provide, is_default in sorted(data['provide_extended']):
                    provide_el = doc.createElement("provide")
                    default = "0"
                    if is_default:
                        default = "1"
                    provide_el.setAttribute("default", default)
                    provides.appendChild(provide_el)
                package.appendChild(provides)

            dependencies = doc.createElement("dependencies")
            if data.get('pkg_dependencies'):
                dep_type_ids = etpConst['dependency_type_ids']
                dep_type_map = {
                    dep_type_ids['bdepend_id']: "buildtime",
                    dep_type_ids['rdepend_id']: "runtime",
                    dep_type_ids['pdepend_id']: "post-runtime",
                    dep_type_ids['mdepend_id']: "manual",
                }
                for dep in sorted(data['conflicts']):
                    dependency = doc.createElement("dependency")
                    dependency.appendChild(doc.createTextNode(dep))
                    dependency.setAttribute("type", "runtime")
                    dependency.setAttribute("conflict", "true")
                    dependencies.appendChild(dependency)

                for dep, dep_type in sorted(data['pkg_dependencies']):
                    dependency = doc.createElement("dependency")
                    dependency.appendChild(doc.createTextNode(dep))
                    dependency.setAttribute("type", dep_type)
                    dependency.setAttribute("conflict", "false")
                    dependencies.appendChild(dependency)

                package.appendChild(dependencies)

            for mirror_name, mirrors in data['mirrorlinks']:
                obj = source_mirrors.setdefault(mirror_name, {})
                if not obj:
                    obj.update({'id': source_mirror_id,
                                'mirrors': set(mirrors),})
                    source_mirror_id += 1
                else:
                    obj['mirrors'].update(mirrors)

            sources = doc.createElement("sources")
            if data['sources']:
                for source in sorted(data['sources']):
                    source_el = doc.createElement("source")
                    source_el.appendChild(doc.createTextNode(source))
                    sources.appendChild(source_el)
                package.appendChild(sources)

            useflags = doc.createElement("useflags")
            if data['useflags']:
                for useflag in sorted(data['useflags']):
                    useflag_el = doc.createElement("useflag")
                    useflag_el.setAttribute("name", useflag)
                    useflags.appendChild(useflag_el)
                package.appendChild(useflags)

            keywords = doc.createElement("keywords")
            if data['keywords']:
                for keyword in sorted(data['keywords']):
                    keyword_el = doc.createElement("keyword")
                    keyword_el.setAttribute("arch", keyword)
                    keywords.appendChild(keyword_el)
                package.appendChild(keywords)

            if data['config_protect']:
                config_protect = doc.createElement("config-protect")
                config_protect.appendChild(
                    doc.createTextNode(data['config_protect']))
                package.appendChild(config_protect)

            if data['config_protect_mask']:
                config_protect_mask = doc.createElement("config-protect-mask")
                config_protect_mask.appendChild(
                    doc.createTextNode(data['config_protect_mask']))
                package.appendChild(config_protect_mask)

            needed_libs = doc.createElement("needed-libs")
            if "needed_libs" in data:
                for _x, _x, needed, elf_class, _x in sorted(
                        data['needed_libs']):
                    needed_el = doc.createElement("needed-lib")
                    needed_el.setAttribute("name", needed)
                    needed_el.setAttribute("elfclass", "%d" % (elf_class,))
                    needed_libs.appendChild(needed_el)
                package.appendChild(needed_libs)
            else:  # needed
                for needed, elf_class in sorted(data['needed']):
                    needed_el = doc.createElement("needed-lib")
                    needed_el.setAttribute("name", needed)
                    needed_el.setAttribute("elfclass", "%d" % (elf_class,))
                    needed_libs.appendChild(needed_el)
                package.appendChild(needed_libs)

            provided_libs = doc.createElement("provided-libs")
            if data['provided_libs']:
                for libname, path, elf_class in sorted(data['provided_libs']):
                    provided_el = doc.createElement("provided-lib")
                    provided_el.setAttribute("name", libname)
                    provided_el.setAttribute("elfclass", "%d" % (elf_class,))
                    provided_el.appendChild(doc.createTextNode(path))
                    provided_libs.appendChild(provided_el)
                package.appendChild(provided_libs)

            if data['changelog']:
                changelog_key = (data['category'], data['name'])
                obj = package_changelogs.setdefault(changelog_key, {})
                if not obj:
                    obj.update({
                        'id': package_changelogs_id,
                        'changelog': data['changelog'],
                    })
                    package_changelogs_id += 1

                changelog = doc.createElement("changelog")
                changelog.setAttribute("pkg-changelog-id", "%d" % (obj['id'],))
                package.appendChild(changelog)

            desktop_mimes = doc.createElement("desktop-mimes")
            if data['desktop_mime']:
                for mime in data['desktop_mime']:
                    mime_el = doc.createElement("desktop-mime")
                    mime_el.setAttribute("name", mime['name'])
                    mime_el.setAttribute("mimetype", mime['mimetype'])
                    mime_el.setAttribute("icon", mime['icon'])
                    mime_el.appendChild(doc.createTextNode(mime['executable']))
                    desktop_mimes.appendChild(mime_el)
                package.appendChild(desktop_mimes)

            signature_id = 1
            signatures = {}
            download = doc.createElement("download")
            download.setAttribute("signature-id", "sign-%d-%d" % (
                package_id, signature_id,))
            package.appendChild(download)
            signatures[1] = {
                'url': data['download'],
                'md5': data['digest'],
                'sha1': data['signatures']['sha1'],
                'sha256': data['signatures']['sha256'],
                'sha512': data['signatures']['sha512'],
                'gpg': data['signatures']['gpg'],
            }
            signature_id += 1

            extra_downloads = doc.createElement("extra-downloads")
            if data['extra_download']:
                for extra_download in data['extra_download']:
                    extra_download_el = doc.createElement("extra-download")
                    extra_download_el.setAttribute(
                        "type", extra_download['type'])
                    extra_download_el.setAttribute(
                        "size", "%d" % (extra_download['size'],))
                    extra_download_el.setAttribute(
                        "disksize", "%d" % (extra_download['disksize'],))
                    extra_download_el.setAttribute(
                        "signature-id",
                        "sign-%d-%d" % (package_id, signature_id,))
                    signatures[signature_id] = {
                        'url': extra_download['download'],
                        'md5': extra_download['md5'],
                        'sha1': extra_download['sha1'],
                        'sha256': extra_download['sha256'],
                        'sha512': extra_download['sha512'],
                        'gpg': extra_download['gpg'],
                    }
                    signature_id += 1
                    extra_downloads.appendChild(extra_download_el)
                package.appendChild(extra_downloads)

            signatures_el = doc.createElement("signatures")
            for signature_id in sorted(signatures):
                sign_data = signatures[signature_id]
                signature_el = doc.createElement("signature")
                signature_el.setAttribute("id", "sign-%d-%d" % (
                    package_id, signature_id,))

                sign_url = doc.createElement("url")
                sign_url.appendChild(doc.createTextNode(sign_data['url']))
                signature_el.appendChild(sign_url)

                sign_md5 = doc.createElement("md5")
                sign_md5.appendChild(doc.createTextNode(sign_data['md5']))
                signature_el.appendChild(sign_md5)

                sha1 = sign_data['sha1'] or ""
                sign_sha1 = doc.createElement("sha1")
                sign_sha1.appendChild(doc.createTextNode(sha1))
                signature_el.appendChild(sign_sha1)

                sha256 = sign_data['sha256'] or ""
                sign_sha256 = doc.createElement("sha256")
                sign_sha256.appendChild(doc.createTextNode(sha256))
                signature_el.appendChild(sign_sha256)

                sha512 = sign_data['sha256'] or ""
                sign_sha512 = doc.createElement("sha512")
                sign_sha512.appendChild(doc.createTextNode(sha512))
                signature_el.appendChild(sign_sha512)

                gpg = sign_data['gpg'] or ""
                sign_gpg = doc.createElement("gpg")
                sign_gpg.appendChild(doc.createTextNode(gpg))
                signature_el.appendChild(sign_gpg)

                signatures_el.appendChild(signature_el)

            package.appendChild(signatures_el)

            provided_mimes = doc.createElement("provided-mimes")
            if data['provided_mime']:
                for mime in sorted(data['provided_mime']):
                    provided_mime = doc.createElement("provided-mime")
                    provided_mime.setAttribute("mimetype", mime)
                    provided_mimes.appendChild(provided_mime)
                package.appendChild(provided_mimes)

            spm_phases = doc.createElement("spm-phases")
            if data['spm_phases']:
                for spm_phase in data['spm_phases'].split():
                    spm_phase_el = doc.createElement("spm-phase")
                    spm_phase_el.appendChild(doc.createTextNode(spm_phase))
                    spm_phases.appendChild(spm_phase_el)
                package.appendChild(spm_phases)

            spm_payload_el = doc.createElement("spm-payload")
            spm_payload = self.retrieveSpmMetadata(package_id)
            if spm_payload:
                spm_payload = base64.b64encode(spm_payload)
                spm_payload_el.appendChild(doc.createTextNode(spm_payload))
                package.appendChild(spm_payload_el)

            packages.appendChild(package)

        source_mirrors_el = doc.createElement("source-mirrors")
        if source_mirrors:
            for mirror_name in sorted(source_mirrors):
                obj = source_mirrors[mirror_name]
                source_mirror = doc.createElement("source-mirror")
                source_mirror.setAttribute(
                    "id", "source-mirror-%d" % (obj['id'],))
                source_mirror.setAttribute("name", mirror_name)
                for mirror in sorted(obj['mirrors']):
                    mirror_el = doc.createElement("mirror")
                    mirror_el.appendChild(doc.createTextNode(mirror))
                    source_mirror.appendChild(mirror_el)
                source_mirrors_el.appendChild(source_mirror)
            packages.appendChild(source_mirrors_el)

        pkg_changelogs_el = doc.createElement("pkg-changelogs")
        if package_changelogs:
            for changelog_key, cl in package_changelogs.items():
                pkg_changelog = doc.createElement("pkg-changelog")
                pkg_changelog.appendChild(doc.createTextNode(cl['changelog']))
                pkg_changelog.setAttribute("id", "%d" % (cl['id'],))
                pkg_changelogs_el.appendChild(pkg_changelog)
            packages.appendChild(pkg_changelogs_el)

        return packages.toprettyxml(indent="  ")

    def clearCache(self):
        """
        Clear repository cache.
        Attention: call this method from your subclass, otherwise
        EntropyRepositoryPlugins won't be notified.
        """
        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.clear_cache_hook(self)
            if exec_rc:
                raise RepositoryPluginError(
                    "[clear_cache_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

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
        raise NotImplementedError()

    def _runConfigurationFilesUpdate(self, actions, files,
        protect_overwrite = True):
        """
        Routine that takes all the executed actions and updates configuration
        files.
        """
        spm_class = get_spm_class()
        updated_files = set()

        actions_map = {}
        for action in actions:
            command = action.split()
            dep_key = entropy.dep.dep_getkey(command[1])
            obj = actions_map.setdefault(dep_key, [])
            obj.append(tuple(command))

        def _workout_line(line):
            if not line.strip():
                return line
            if line.lstrip().startswith("#"):
                return line

            split_line = line.split()
            if not split_line:
                return line

            pkg_dep = split_line[0]
            pkg_key = entropy.dep.dep_getkey(pkg_dep)

            pkg_commands = actions_map.get(pkg_key)
            if pkg_commands is None:
                return line

            for command in pkg_commands:
                if command[0] == "move":
                    dep_from, key_to = command[1:]
                    dep_from_key = entropy.dep.dep_getkey(dep_from)
                    # NOTE: dep matching not supported, only using key
                    if dep_from_key == pkg_key:
                        # found, replace package name
                        split_line[0] = pkg_dep.replace(dep_from_key, key_to)
                        new_line = " ".join(split_line) + "\n"
                        const_debug_write(__name__,
                            "_runConfigurationFilesUpdate: replacing: " + \
                            "'%s' => '%s'" % (line, new_line,))
                        line = new_line
                        # keep going, since updates are incremental
                # NOTE: slotmove not supported

            return line

        enc = etpConst['conf_encoding']
        for file_path in files:
            tmp_fd, tmp_path = None, None
            try:
                with codecs.open(file_path, "r", encoding=enc) as source_f:
                    tmp_fd, tmp_path = const_mkstemp(
                        prefix="entropy.db._runConfigurationFilesUpdate",
                        dir=os.path.dirname(file_path))
                    with entropy.tools.codecs_fdopen(tmp_fd, "w", enc) \
                            as dest_f:
                        line = source_f.readline()
                        while line:
                            dest_f.write(_workout_line(line))
                            line = source_f.readline()

                if protect_overwrite:
                    new_file_path, prot_status = \
                        spm_class.allocate_protected_file(
                            tmp_path, file_path)
                    if prot_status:
                        # it has been replaced
                        os.rename(tmp_path, new_file_path)
                        updated_files.add(new_file_path)
                    else:
                        os.remove(tmp_path)
                else:
                    os.rename(tmp_path, file_path)

                tmp_path = None
                tmp_fd = None

            except (OSError, IOError,) as err:
                const_debug_write(__name__, "error: %s" % (err,))
                continue
            finally:
                if tmp_fd is not None:
                    try:
                        os.close(tmp_fd)
                    except (OSError, IOError):
                        pass
                if tmp_path is not None:
                    try:
                        os.remove(tmp_path)
                    except (OSError, IOError):
                        pass

        return updated_files

    def runTreeUpdatesActions(self, actions):
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
            blue(_("Running packages metadata update")),
            red(_("it could take a while")),
        )
        self.output(
            mytxt,
            importance = 1,
            level = "warning",
            header = darkred(" * ")
        )
        try:
            spm = get_spm(self)
            spm.packages_repositories_metadata_update(actions)
        except Exception:
            entropy.tools.print_traceback()

        quickpkg_atoms = set()
        executed_actions = []
        for action in actions:
            command = action.split()
            mytxt = "%s: %s: %s." % (
                bold(_("Entropy")),
                red(_("action")),
                blue(action),
            )
            self.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = darkred(" * ")
            )
            if command[0] == "move":
                move_actions = self._runTreeUpdatesMoveAction(command[1:],
                    quickpkg_atoms)
                if move_actions:
                    executed_actions.append(action)
                quickpkg_atoms |= move_actions
            elif command[0] == "slotmove":
                slotmove_actions = self._runTreeUpdatesSlotmoveAction(
                    command[1:],
                    quickpkg_atoms)
                if slotmove_actions:
                    executed_actions.append(action)
                quickpkg_atoms |= slotmove_actions

            mytxt = "%s: %s." % (
                bold(_("Entropy")),
                blue(_("package move actions complete")),
            )
            self.output(
                mytxt,
                importance = 1,
                level = "info",
                header = purple(" @@ ")
            )

        mytxt = "%s: %s." % (
            bold(_("Entropy")),
            blue(_("package moves completed successfully")),
        )
        self.output(
            mytxt,
            importance = 1,
            level = "info",
            header = brown(" @@ ")
        )

        if executed_actions:
            # something actually happened, update configuration files
            files = self._settings.get_updatable_configuration_files(
                self.repository_id())
            self._runConfigurationFilesUpdate(executed_actions, files)

        # discard cache
        self.clearCache()

        return quickpkg_atoms


    def _runTreeUpdatesMoveAction(self, move_command, quickpkg_queue):
        """
        Method not suited for general purpose usage.
        Executes package name move action passed.
        No need to override.

        -- move action:
        1) move package key to the new name: category + name + atom
        2) update all the dependencies in dependenciesreference to the new key
        3) run fixpackages which will update /var/db/pkg files
        4) automatically run generate_package() to build the new binary and
           tainted binaries owning tainted iddependency and taint database

        @param move_command: raw treeupdates move action, for example:
            'move x11-foo/bar app-foo/bar'
        @type move_command: string
        @param quickpkg_queue: current package regeneration queue
        @type quickpkg_queue: list
        @return: updated package regeneration queue
        @rtype: list
        """
        dep_from = move_command[0]
        key_from = entropy.dep.dep_getkey(dep_from)
        key_to = entropy.dep.dep_getkey(move_command[1])
        cat_to, name_to = key_to.split("/", 1)
        matches = self.atomMatch(dep_from, multiMatch = True,
            maskFilter = False)
        iddependencies = set()
        slot_pfx = etpConst['entropyslotprefix']

        matched_package_ids = matches[0]
        for package_id in matched_package_ids:

            slot = self.retrieveSlot(package_id)
            old_atom = self.retrieveAtom(package_id)
            new_atom = old_atom.replace(key_from, key_to)

            ### UPDATE DATABASE
            # update category
            self.setCategory(package_id, cat_to)
            # update name
            self.setName(package_id, name_to)
            # update atom
            self.setAtom(package_id, new_atom)

            # look for packages we need to quickpkg again
            quickpkg_queue.add(key_to + slot_pfx + slot)

            plugins = self.get_plugins()
            for plugin_id in sorted(plugins):
                plug_inst = plugins[plugin_id]
                exec_rc = plug_inst.treeupdates_move_action_hook(self,
                    package_id)
                if exec_rc:
                    raise RepositoryPluginError(
                        "[treeupdates_move_action_hook] %s: status: %s" % (
                            plug_inst.get_id(), exec_rc,))

        iddeps = self.searchDependency(key_from, like = True, multi = True)
        for iddep in iddeps:

            mydep = self.getDependency(iddep)
            # replace with new key and test
            mydep = mydep.replace(key_from, key_to)

            pkg_ids, pkg_rc = self.atomMatch(mydep, multiMatch = True,
                maskFilter = False)

            pointing_to_me = False
            for pkg_id in pkg_ids:
                if pkg_id not in matched_package_ids:
                    # not my business
                    continue
                # is this really pointing to me?
                mydep_key, _slot = self.retrieveKeySlot(pkg_id)
                if mydep_key != key_to:
                    # not me!
                    continue
                # yes, it's pointing to me
                pointing_to_me = True
                break

            if not pointing_to_me:
                # meh !
                continue

            # now update
            # dependstable on server is always re-generated
            self.setDependency(iddep, mydep)
            # we have to repackage also package owning this iddep
            iddependencies |= self.searchPackageIdFromDependencyId(iddep)

        self.commit()
        quickpkg_queue = list(quickpkg_queue)
        for x in range(len(quickpkg_queue)):
            myatom = quickpkg_queue[x]
            myatom = myatom.replace(key_from, key_to)
            quickpkg_queue[x] = myatom
        quickpkg_queue = set(quickpkg_queue)
        for package_id_owner in iddependencies:
            myatom = self.retrieveAtom(package_id_owner)
            if myatom is None:
                # reverse deps table out of sync
                continue
            myatom = myatom.replace(key_from, key_to)
            quickpkg_queue.add(myatom)
        return quickpkg_queue


    def _runTreeUpdatesSlotmoveAction(self, slotmove_command, quickpkg_queue):
        """
        Method not suited for general purpose usage.
        Executes package slot move action passed.
        No need to override.

        -- slotmove action:
        1) move package slot
        2) update all the dependencies in dependenciesreference owning
           same matched atom + slot
        3) run fixpackages which will update /var/db/pkg files
        4) automatically run generate_package() to build the new
           binary and tainted binaries owning tainted iddependency
           and taint database

        @param slotmove_command: raw treeupdates slot move action, for example:
            'slotmove x11-foo/bar 2 3'
        @type slotmove_command: string
        @param quickpkg_queue: current package regeneration queue
        @type quickpkg_queue: list
        @return: updated package regeneration queue
        @rtype: list
        """
        atom = slotmove_command[0]
        atomkey = entropy.dep.dep_getkey(atom)
        slot_from = slotmove_command[1]
        slot_to = slotmove_command[2]
        matches = self.atomMatch(atom, multiMatch = True, maskFilter = False)
        iddependencies = set()
        slot_pfx = etpConst['entropyslotprefix']

        matched_package_ids = matches[0]
        for package_id in matched_package_ids:

            # only if we've found VALID matches !
            iddeps = self.searchDependency(atomkey, like = True, multi = True)
            for iddep in iddeps:
                # update string
                mydep = self.getDependency(iddep)

                if mydep.find(slot_pfx + slot_from) == -1:
                    # doesn't contain any trace of slot string, skipping
                    continue

                pkg_ids, pkg_rc = self.atomMatch(mydep, multiMatch = True,
                    maskFilter = False)

                pointing_to_me = False
                for pkg_id in pkg_ids:
                    if pkg_id not in matched_package_ids:
                        # not my business
                        continue
                    # is this really pointing to me?
                    mydep_key, mydep_slot = self.retrieveKeySlot(pkg_id)
                    if mydep_key != atomkey:
                        # not me!
                        continue
                    if mydep_slot != slot_from:
                        # not me!
                        continue
                    # yes, it's pointing to me
                    pointing_to_me = True
                    break

                if not pointing_to_me:
                    # meh !
                    continue

                mydep = mydep.replace(slot_pfx + slot_from, slot_pfx + slot_to)
                # now update
                # dependstable on server is always re-generated
                self.setDependency(iddep, mydep)
                # we have to repackage also package owning this iddep
                iddependencies |= self.searchPackageIdFromDependencyId(iddep)

            ### UPDATE DATABASE
            # update slot, do it here to avoid messing up with package match
            # code up here
            self.setSlot(package_id, slot_to)

            # look for packages we need to quickpkg again
            # NOTE: quickpkg_queue is simply ignored if this is a client side
            # repository
            quickpkg_queue.add(atom + slot_pfx + slot_to)

            plugins = self.get_plugins()
            for plugin_id in sorted(plugins):
                plug_inst = plugins[plugin_id]
                exec_rc = plug_inst.treeupdates_slot_move_action_hook(self,
                    package_id)
                if exec_rc:
                    raise RepositoryPluginError(
                        "[treeupdates_slot_move_action_hook] %s: status: %s" % (
                            plug_inst.get_id(), exec_rc,))

        self.commit()
        for package_id_owner in iddependencies:
            myatom = self.retrieveAtom(package_id_owner)
            if myatom is None:
                # reverse deps table out of sync
                continue
            quickpkg_queue.add(myatom)
        return quickpkg_queue

    def listAllTreeUpdatesActions(self, no_ids_repos = False):
        """
        This method should be considered internal and not suited for general
        audience.
        List all the available "treeupdates" (package names/slots changes
            directives) actions.
        Actions must be sorted by date (FLOAT).

        @keyword no_ids_repos: if True, it will just return a tuple of 3-length
            tuples containing ((command, branch, unix_time,), ...)
        @type no_ids_repos: bool
        @return: tuple of tuples
        @rtype: tuple
        """
        raise NotImplementedError()

    def retrieveTreeUpdatesActions(self, repository):
        """
        This method should be considered internal and not suited for general
        audience.
        Return all the available "treeupdates (package names/slots changes
            directives) actions for provided repository.
        Actions must be sorted by date (FLOAT).

        @param repository: repository identifier
        @type repository: string
        @return: tuple of raw-string commands to run
        @rtype: tuple
        """
        raise NotImplementedError()

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
        raise NotImplementedError()

    def removeTreeUpdatesActions(self, repository):
        """
        This method should be considered internal and not suited for general
        audience.
        This method removes "treeupdates" metadata in repository.

        @param repository: remove treeupdates metadata for provided repository
        @type repository: string
        """
        raise NotImplementedError()

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
        raise NotImplementedError()

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
        raise NotImplementedError()

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
        raise NotImplementedError()

    def clearPackageSets(self):
        """
        Clear Package sets (group of packages) entries in repository.
        """
        raise NotImplementedError()

    def insertPackageSets(self, sets_data):
        """
        Insert Package sets metadata into repository.

        @param sets_data: dictionary containing package set names as keys and
            list (set) of dependencies as value
        @type sets_data: dict
        """
        raise NotImplementedError()

    def retrievePackageSets(self):
        """
        Return Package sets metadata stored in repository.

        @return: dictionary containing package set names as keys and
            list (set) of dependencies as value
        @rtype: dict
        """
        raise NotImplementedError()

    def retrievePackageSet(self, setname):
        """
        Return dependencies belonging to given package set name.
        This method does not check if the given package set name is
        available and returns an empty list (set) in these cases.

        @param setname: Package set name
        @type setname: string
        @return: list (set) of dependencies belonging to given package set name
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveAtom(self, package_id):
        """
        Return "atom" metadatum for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: atom string
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveBranch(self, package_id):
        """
        Return "branch" metadatum for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: branch metadatum
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveTrigger(self, package_id):
        """
        Return "trigger" script content for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: trigger script content
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveDownloadURL(self, package_id):
        """
        Return "download URL" metadatum for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: download url metadatum
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveDescription(self, package_id):
        """
        Return "description" metadatum for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: package description
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveHomepage(self, package_id):
        """
        Return "homepage" metadatum for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: package homepage
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveSpmUid(self, package_id):
        """
        Return Source Package Manager unique identifier bound to Entropy
        package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: Spm UID or -1 (if not bound, valid for injected packages)
        @rtype: int
        """
        raise NotImplementedError()

    def retrieveSize(self, package_id):
        """
        Return "size" metadatum for given package identifier.
        "size" refers to Entropy package file size in bytes.

        @param package_id: package indentifier
        @type package_id: int
        @return: size of Entropy package for given package identifier
        @rtype: int or None
        """
        raise NotImplementedError()

    def retrieveOnDiskSize(self, package_id):
        """
        Return "on disk size" metadatum for given package identifier.
        "on disk size" refers to unpacked Entropy package file size in bytes,
        which is in other words, the amount of space required on live system
        to have it installed (simplified explanation).

        @param package_id: package indentifier
        @type package_id: int
        @return: on disk size metadatum
        @rtype: int
        """
        raise NotImplementedError()

    def retrieveDigest(self, package_id):
        """
        Return "digest" metadatum for given package identifier.
        "digest" refers to Entropy package file md5 checksum bound to given
        package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: md5 checksum for given package identifier
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveSignatures(self, package_id):
        """
        Return package file extra hashes (sha1, sha256, sha512) for given
        package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: tuple of length 3, sha1, sha256, sha512 package extra
            hashes if available, otherwise the same but with None as values.
        @rtype: tuple
        """
        raise NotImplementedError()

    def retrieveExtraDownload(self, package_id, down_type = None):
        """
        Retrieve a list of extra package file URLs for package identifier.
        These URLs usually contain extra files that can be optionally installed
        by Entropy Client, for example: debug files.
        All the extra download file names must end with etpConst['packagesextraext']
        extension.

        @param package_id: package indentifier
        @type package_id: int
        @keyword down_type: retrieve data for a given entry type.
            Currently supported entry types are: "debug", "data".
        @type down_type: string
        @return: list (tuple) of dict containing "download", "type", "size",
            "disksize, "md5", "sha1","sha256", "sha512", "gpg" keys. "download"
            contains the relative URL (like the one returned by
            retrieveDownloadURL())
        @rtype: tuple
        @raise AttributeError: if provided down_type value is invalid
        """
        raise NotImplementedError()

    def retrieveName(self, package_id):
        """
        Return "name" metadatum for given package identifier.
        Attention: package name != atom, the former is just a subset of the
        latter.

        @param package_id: package indentifier
        @type package_id: int
        @return: "name" metadatum for given package identifier
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveKeySplit(self, package_id):
        """
        Return a tuple composed by package category and package name for
        given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: tuple of length 2 composed by (package_category, package_name,)
        @rtupe: tuple or None
        """
        raise NotImplementedError()

    def retrieveKeySlot(self, package_id):
        """
        Return a tuple composed by package key and slot for given package
        identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: tuple of length 2 composed by (package_key, package_slot,)
        @rtupe: tuple or None
        """
        raise NotImplementedError()

    def retrieveKeySlotAggregated(self, package_id):
        """
        Return package key and package slot string (aggregated form through
        ":", for eg.: app-foo/foo:2).
        This method has been implemented for performance reasons.

        @param package_id: package indentifier
        @type package_id: int
        @return: package key + ":" + slot string
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveKeySlotTag(self, package_id):
        """
        Return package key, slot and tag tuple for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: tuple of length 3 providing (package_key, slot, package_tag,)
        @rtype: tuple
        """
        raise NotImplementedError()

    def retrieveVersion(self, package_id):
        """
        Return package version for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: package version
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveRevision(self, package_id):
        """
        Return package Entropy-revision for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: Entropy-revision for given package indentifier
        @rtype: int or None
        """
        raise NotImplementedError()

    def retrieveCreationDate(self, package_id):
        """
        Return creation date for given package identifier.
        Creation date returned is a string representation of UNIX time format.

        @param package_id: package indentifier
        @type package_id: int
        @return: creation date for given package identifier
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveApi(self, package_id):
        """
        Return Entropy API in use when given package identifier was added.

        @param package_id: package indentifier
        @type package_id: int
        @return: Entropy API for given package identifier
        @rtype: int or None
        """
        raise NotImplementedError()

    def retrieveUseflags(self, package_id):
        """
        Return "USE flags" metadatum for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: list (frozenset) of USE flags for given package identifier.
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveSpmPhases(self, package_id):
        """
        Return "Source Package Manager install phases" for given package
        identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: "Source Package Manager available install phases" string
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveSpmRepository(self, package_id):
        """
        Return Source Package Manager source repository used at compile time.

        @param package_id: package indentifier
        @type package_id: int
        @return: Source Package Manager source repository
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveDesktopMime(self, package_id):
        """
        Return file association metadata for package.

        @param package_id: package indentifier
        @type package_id: int
        @return: list of dict() containing file association information
        @rtype: list
        """
        raise NotImplementedError()

    def retrieveProvidedMime(self, package_id):
        """
        Return mime types associated to package. Mimetypes whose package
        can handle.

        @param package_id: package indentifier
        @type package_id: int
        @return: list (frozenset) of mimetypes
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveNeeded(self, package_id, extended = False, formatted = False):
        """
        Return "NEEDED" elf metadata for libraries contained in given package.
        Deprecated, use retrieveNeededLibraries.

        @param package_id: package indentifier
        @type package_id: int
        @keyword extended: also return ELF class information for every
            library name
        @type extended: bool
        @keyword formatted: properly format output, returning a dictionary with
            library name as key and ELF class as value
        @type formatted: bool
        @return: "NEEDED" metadata for libraries contained in given package.
        @rtype: tuple or dict
        """
        raise NotImplementedError()

    def retrieveNeededLibraries(self, package_id):
        """
        Return the needed libraries for a given package.

        @param package_id: package indentifier
        @type package_id: int
        @return: list (frozenset) of tuples composed by library user path,
            library user soname, soname, elf class, rpath.
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveProvidedLibraries(self, package_id):
        """
        Return list of library names (from NEEDED ELF metadata) provided by
        given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: list (frozenset) of tuples of length 3 composed by library
            name, path and ELF class
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveConflicts(self, package_id):
        """
        Return list of conflicting dependencies for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: list (frozenset) of conflicting package dependencies
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveProvide(self, package_id):
        """
        Return list of dependencies/atoms are provided by the given package
        identifier (see Portage documentation about old-style PROVIDEs).

        @param package_id: package indentifier
        @type package_id: int
        @return: list (frozenset) of atoms provided by package
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveDependenciesList(self, package_id, exclude_deptypes = None,
        resolve_conditional_deps = True):
        """
        Return list of dependencies, including conflicts for given package
        identifier.

        @param package_id: package indentifier
        @type package_id: int
        @keyword exclude_deptypes: exclude given dependency types from returned
            data. Please see etpConst['dependency_type_ids'] for valid values.
            Anything != int will raise AttributeError
        @type exclude_deptypes: list
        @keyword resolve_conditional_deps: resolve conditional dependencies
            automatically by default, stuff like
            ( app-foo/foo | app-foo/bar ) & bar-baz/foo
        @type resolve_conditional_deps: bool
        @return: list (frozenset) of dependencies of package
        @rtype: frozenset
        @raise AttributeError: if exclude_deptypes contains illegal values
        """
        raise NotImplementedError()

    def retrieveBuildDependencies(self, package_id, extended = False,
        resolve_conditional_deps = True):
        """
        Return list of build time package dependencies for given package
        identifier.
        Note: this function is just a wrapper of retrieveDependencies()
        providing deptype (dependency type) = post-dependencies.

        @param package_id: package indentifier
        @type package_id: int
        @keyword extended: return in extended format
        @type extended: bool
        @keyword resolve_conditional_deps: resolve conditional dependencies
            automatically by default, stuff like
            ( app-foo/foo | app-foo/bar ) & bar-baz/foo
        @type resolve_conditional_deps: bool
        @return: list (frozenset) of build dependencies of package
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveRuntimeDependencies(self, package_id, extended = False,
        resolve_conditional_deps = True):
        """
        Return list of runtime package dependencies for given package
        identifier.
        Note: this function is just a wrapper of retrieveDependencies()
        providing deptype (dependency type) = runtime-dependencies.

        @param package_id: package indentifier
        @type package_id: int
        @keyword extended: return in extended format
        @type extended: bool
        @keyword resolve_conditional_deps: resolve conditional dependencies
            automatically by default, stuff like
            ( app-foo/foo | app-foo/bar ) & bar-baz/foo
        @type resolve_conditional_deps: bool
        @return: list (frozenset) of build dependencies of package
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrievePostDependencies(self, package_id, extended = False,
        resolve_conditional_deps = True):
        """
        Return list of post-merge package dependencies for given package
        identifier.
        Note: this function is just a wrapper of retrieveDependencies()
        providing deptype (dependency type) = post-dependencies.

        @param package_id: package indentifier
        @type package_id: int
        @keyword extended: return in extended format
        @type extended: bool
        @keyword resolve_conditional_deps: resolve conditional dependencies
            automatically by default, stuff like
            ( app-foo/foo | app-foo/bar ) & bar-baz/foo
        @type resolve_conditional_deps: bool
        @return: list (frozenset) of post dependencies of package
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveManualDependencies(self, package_id, extended = False,
        resolve_conditional_deps = True):
        """
        Return manually added dependencies for given package identifier.
        Note: this function is just a wrapper of retrieveDependencies()
        providing deptype (dependency type) = manual-dependencies.

        @param package_id: package indentifier
        @type package_id: int
        @keyword extended: return in extended format
        @type extended: bool
        @keyword resolve_conditional_deps: resolve conditional dependencies
            automatically by default, stuff like
            ( app-foo/foo | app-foo/bar ) & bar-baz/foo
        @type resolve_conditional_deps: bool
        @return: list (frozenset) of manual dependencies of package
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveDependencies(self, package_id, extended = False, deptype = None,
        exclude_deptypes = None, resolve_conditional_deps = True):
        """
        Return dependencies for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @keyword extended: return in extended format (list of tuples of length 2
            composed by dependency name and dependency type)
        @type extended: bool
        @keyword deptype: return only given type of dependencies
            see etpConst['dependency_type_ids']['*depend_id'] for dependency type
            identifiers
        @type deptype: bool
        @keyword exclude_deptypes: exclude given dependency types from returned
            data. Please see etpConst['dependency_type_ids'] for valid values.
            Anything != int will raise AttributeError
        @type exclude_deptypes: list
        @keyword resolve_conditional_deps: resolve conditional dependencies
            automatically by default, stuff like
            ( app-foo/foo | app-foo/bar ) & bar-baz/foo
        @type resolve_conditional_deps: bool
        @return: dependencies of given package
        @rtype: tuple or frozenset
        @raise AttributeError: if exclude_deptypes contains illegal values
        """
        raise NotImplementedError()

    def retrieveKeywords(self, package_id):
        """
        Return package SPM keyword list for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: list (frozenset) of keywords for given package identifier
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveProtect(self, package_id):
        """
        Return CONFIG_PROTECT (configuration file protection) string
        (containing a list of space reparated paths) metadata for given
        package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: CONFIG_PROTECT string
        @rtype: string
        """
        raise NotImplementedError()

    def retrieveProtectMask(self, package_id):
        """
        Return CONFIG_PROTECT_MASK (mask for configuration file protection)
        string (containing a list of space reparated paths) metadata for given
        package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: CONFIG_PROTECT_MASK string
        @rtype: string
        """
        raise NotImplementedError()

    def retrieveSources(self, package_id, extended = False):
        """
        Return source package URLs for given package identifier.
        "source" as in source code.

        @param package_id: package indentifier
        @type package_id: int
        @keyword extended: 
        @type extended: bool
        @return: if extended is True, dict composed by source URLs as key
            and list of mirrors as value, otherwise just a list (frozenset) of
            source package URLs.
        @rtype: dict or frozenset
        """
        raise NotImplementedError()

    def retrieveAutomergefiles(self, package_id, get_dict = False):
        """
        Return previously merged protected configuration files list and
        their md5 hashes for given package identifier.
        This is part of the "automerge" feature which uses file md5 checksum
        to determine if a protected configuration file can be merged auto-
        matically.

        @param package_id: package indentifier
        @type package_id: int
        @keyword get_dict: return a dictionary with configuration file as key
            and md5 hash as value
        @type get_dict: bool
        @return: automerge metadata for given package identifier
        @rtype: frozenset or dict
        """
        raise NotImplementedError()

    def retrieveContent(self, package_id, extended = False,
        formatted = False, insert_formatted = False, order_by = None):
        """
        Return files contained in given package.

        @param package_id: package indentifier
        @type package_id: int
        @keyword extended: return in extended format
        @type extended: bool
        @keyword formatted: return in dict() form
        @type formatted: bool
        @keyword insert_formatted: return in list of tuples form, ready to
            be added with insertContent()
        @keyword order_by: order by string, valid values are:
            "type" (if extended is True), "file" or "package_id"
        @type order_by: string
        @return: content metadata
        @rtype: dict or tuple or frozenset
        @raise AttributeError: if order_by value is invalid
        """
        raise NotImplementedError()

    def retrieveContentIter(self, package_id, order_by = None,
                            reverse = False):
        """
        Return an iterator that makes possible to retrieve the files
        contained in given package. Please note that the iterator returned
        will fail if the EntropyRepository object is closed (call to close()).
        The iterator thus becomes invalid.
        Moreover, do not execute any other call that could invalidate
        the cursor object state before being done with it.

        @param package_id: package indentifier
        @type package_id: int
        @keyword order_by: order by string, valid values are:
            "type" (if extended is True), "file" or "package_id"
        @type order_by: string
        @keyword reverse: return elements in reverse order
        @type reverse: bool
        @return: content metadata
        @rtype: iterator
        @raise AttributeError: if order_by value is invalid
        """
        raise NotImplementedError()

    def retrieveContentSafety(self, package_id):
        """
        Return supported content safety metadata for given package.
        Data returned is a dictionary, using package file path as key and
        dictionary as value. The latter, contains supported SPM content
        safety metadata, such as "sha256" (string) checksum, and "mtime"
        (float). The barely minimum is in fact, supporting sha256 and mtime
        of package files.

        @param package_id: package indentifier
        @type package_id: int
        @return: content safety metadata
        @rtype: dict
        """
        raise NotImplementedError()

    def retrieveContentSafetyIter(self, package_id):
        """
        Return supported content safety metadata for given package in
        iterator form.
        Each iterator item is composed by a (path, sha256, mtime) tuple.
        Please note that the iterator returned will fail if the
        EntropyRepository object is closed (call to close()).
        The iterator thus becomes invalid.
        Moreover, do not execute any other call that could invalidate
        the cursor object state before being done with it.

        @param package_id: package indentifier
        @type package_id: int
        @keyword order_by: order by string, valid values are:
            "type" (if extended is True), "file" or "package_id"
        @return: contentsafety metadata
        @rtype: iterator
        """
        raise NotImplementedError()

    def retrieveChangelog(self, package_id):
        """
        Return Source Package Manager ChangeLog for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: ChangeLog content
        @rtype: string or None
        """
        raise NotImplementedError()

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
        raise NotImplementedError()

    def retrieveSlot(self, package_id):
        """
        Return "slot" metadatum for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: package slot
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveTag(self, package_id):
        """
        Return "tag" metadatum for given package identifier.
        Tagging packages allows, for example, to support multiple
        different, colliding atoms in the same repository and still being
        able to exactly reference them. It's actually used to provide
        versions of external kernel modules for different kernels.

        @param package_id: package indentifier
        @type package_id: int
        @return: tag string
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveMirrorData(self, mirrorname):
        """
        Return available mirror URls for given mirror name.

        @param mirrorname: mirror name (for eg. "openoffice")
        @type mirrorname: string
        @return: list (frozenset) of URLs providing the "openoffice"
            mirroring service
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveCategory(self, package_id):
        """
        Return category name for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: category where package is in
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveCategoryDescription(self, category):
        """
        Return description text for given category.

        @param category: category name
        @type category: string
        @return: category description dict, locale as key, description as value
        @rtype: dict
        """
        raise NotImplementedError()

    def retrieveLicenseData(self, package_id):
        """
        Return license metadata for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: dictionary composed by license name as key and license text
            as value
        @rtype: dict
        """
        raise NotImplementedError()

    def retrieveLicenseDataKeys(self, package_id):
        """
        Return license names available for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: list (frozenset) of license names which text is available in
            repository
        @rtype: frozenset
        """
        raise NotImplementedError()

    def retrieveLicenseText(self, license_name):
        """
        Return license text for given license name.

        @param license_name: license name (for eg. GPL-2)
        @type license_name: string
        @return: license text
        @rtype: string (raw format) or None
        """
        raise NotImplementedError()

    def retrieveLicense(self, package_id):
        """
        Return "license" metadatum for given package identifier.

        @param package_id: package indentifier
        @type package_id: int
        @return: license string
        @rtype: string or None
        """
        raise NotImplementedError()

    def retrieveCompileFlags(self, package_id):
        """
        Return Compiler flags during building of package.
            (CHOST, CXXFLAGS, LDFLAGS)

        @param package_id: package indentifier
        @type package_id: int
        @return: tuple of length 3 composed by (CHOST, CFLAGS, CXXFLAGS)
        @rtype: tuple
        """
        raise NotImplementedError()

    def retrieveReverseDependencies(self, package_id, atoms = False,
        key_slot = False, exclude_deptypes = None, extended = False):
        """
        Return reverse (or inverse) dependencies for given package.

        @param package_id: package indentifier
        @type package_id: int
        @keyword atoms: if True, method returns list of atoms
        @type atoms: bool
        @keyword key_slot: if True, method returns list of dependencies in
            key:slot form, example: (('app-foo/bar','2',), ...)
        @type key_slot: bool
        @keyword exclude_deptypes: exclude given dependency types from returned
            data. Please see etpConst['dependency_type_ids'] for valid values.
            Anything != int will raise AttributeError
        @type exclude_deptypes: iterable of ints
        @keyword extended: if True, the original dependency string will
            be returned along with the rest of information. So, if data
            returned would be a list of package identifiers (int),
            if extended = True this method will return a list of tuples
            composed by (package_id, dep_string). Same for atoms = True and
            key_slot = True.
        @type extended: bool
        @return: reverse dependency list (tuple) (or list of lists in case
            of extended = True)
        @rtype: tuple or frozenset
        @raise AttributeError: if exclude_deptypes contains illegal values
        """
        raise NotImplementedError()

    def retrieveUnusedPackageIds(self):
        """
        Return packages (through their identifiers) not referenced by any
        other as dependency (unused packages).

        @return: unused package_ids ordered by atom
        @rtype: tuple
        """
        raise NotImplementedError()

    def arePackageIdsAvailable(self, package_ids):
        """
        Return whether list of package identifiers are available.
        They must be all available to return True

        @param package_ids: list of package indentifiers
        @type package_ids: iterable
        @return: availability (True if all are available)
        @rtype: bool
        """
        raise NotImplementedError()

    def isPackageIdAvailable(self, package_id):
        """
        Return whether given package identifier is available in repository.

        @param package_id: package indentifier
        @type package_id: int
        @return: availability (True if available)
        @rtype: bool
        """
        raise NotImplementedError()

    def isFileAvailable(self, path, get_id = False):
        """
        Return whether given file path is available in repository (owned by
        one or more packages).

        @param path: path to file or directory
        @type path: string
        @keyword get_id: return list (set) of package_ids owning myfile
        @type get_id: bool
        @return: availability (True if available), when get_id is True,
            it returns a list (frozenset) of package_ids owning myfile
        @rtype: bool or frozenset
        """
        raise NotImplementedError()

    def resolveNeeded(self, needed, elfclass = -1, extended = False):
        """
        Resolve NEEDED ELF entry (a library name) to package_ids owning given
        needed (stressing, needed = library name)

        @param needed: library name
        @type needed: string
        @keyword elfclass: look for library name matching given ELF class
        @type elfclass: int
        @keyword extended: return a frozenset of tuple of length 2, first
            element is package_id, second is actual library path
        @type extended: bool
        @return: list of packages owning given library
        @rtype: frozenset
        """
        raise NotImplementedError()

    def isSpmUidAvailable(self, spm_uid):
        """
        Return whether Source Package Manager package identifier is available
        in repository.

        @param spm_uid: Source Package Manager package identifier
        @type spm_uid: int
        @return: availability (True, if available)
        @rtype: bool
        """
        raise NotImplementedError()

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
        raise NotImplementedError()

    def isLicenseDataKeyAvailable(self, license_name):
        """
        Return whether license name is available in License database, which is
        the one containing actual license texts.

        @param license_name: license name which license text is available
        @type license_name: string
        @return: availability (True, if available)
        @rtype: bool
        """
        raise NotImplementedError()

    def isLicenseAccepted(self, license_name):
        """
        Return whether given license (through its name) has been accepted by
        user.

        @param license_name: license name
        @type license_name: string
        @return: if license name has been accepted by user
        @rtype: bool
        """
        raise NotImplementedError()

    def acceptLicense(self, license_name):
        """
        Mark license name as accepted by user.
        Only and only if user is allowed to accept them:
            - in entropy group
            - db not open in read only mode
        Attention: call this method from your subclass, otherwise
        EntropyRepositoryPlugins won't be notified.

        @param license_name: license name
        @type license_name: string
        """
        plugins = self.get_plugins()
        for plugin_id in sorted(plugins):
            plug_inst = plugins[plugin_id]
            exec_rc = plug_inst.accept_license_hook(self)
            if exec_rc:
                raise RepositoryPluginError(
                    "[accept_license_hook] %s: status: %s" % (
                        plug_inst.get_id(), exec_rc,))

    def isSystemPackage(self, package_id):
        """
        Return whether package is part of core system (though, a system
        package).

        @param package_id: package indentifier
        @type package_id: int
        @return: if True, package is part of core system
        @rtype: bool
        """
        raise NotImplementedError()

    def isInjected(self, package_id):
        """
        Return whether package has been injected into repository (means that
        will be never ever removed due to colliding scope when other
        packages will be added).

        @param package_id: package indentifier
        @type package_id: int
        @return: injection status (True if injected)
        @rtype: bool
        """
        raise NotImplementedError()

    def searchProvidedVirtualPackage(self, keyword):
        """
        Search in old-style Portage PROVIDE metadata.
        @todo: rewrite docstring :-)

        @param keyword: search term
        @type keyword: string
        @return: found PROVIDE metadata
        @rtype: list
        """
        raise NotImplementedError()

    def searchBelongs(self, bfile, like = False):
        """
        Search packages which given file path belongs to.

        @param bfile: file path to search
        @type bfile: string
        @keyword like: do not match exact case
        @type like: bool
        @return: list (frozenset) of package identifiers owning given file
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchContentSafety(self, sfile):
        """
        Search content safety metadata (usually, sha256 and mtime) related to
        given file path. A list of dictionaries is returned, each dictionary
        item contains at least the following fields "package_id", "path",
        "sha256", "mtime").

        @param sfile: file path to search
        @type sfile: string
        @return: content safety metadata list (tuple)
        @rtype: tuple
        """
        raise NotImplementedError()

    def searchTaggedPackages(self, tag, atoms = False):
        """
        Search packages which "tag" metadatum matches the given one.

        @param tag: tag name to search
        @type tag: string
        @keyword atoms: return list of atoms instead of package identifiers
        @type atoms: bool
        @return: list of packages using given tag
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchRevisionedPackages(self, revision):
        """
        Search packages which "revision" metadatum matches the given one.

        @param revision: Entropy revision to search
        @type revision: string
        @return: list (frozenset) of packages using given tag
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchLicense(self, keyword, just_id = False):
        """
        Search packages using given license (mylicense).

        @param keyword: license name to search
        @type keyword: string
        @keyword just_id: just return package identifiers, otherwise a frozenset
            of tuples of length 2 is returned
        @type just_id: bool
        @return: list (frozenset) of packages using given license
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchSlotted(self, keyword, just_id = False):
        """
        Search packages with given slot string.

        @param keyword: slot to search
        @type keyword: string
        @keyword just_id: just return package identifiers, otherwise a frozenset
            of tuples of length 2 is returned
        @type just_id: bool
        @return: list (frozenset) of packages using given slot
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchKeySlot(self, key, slot):
        """
        Search package with given key and slot

        @param key: package key
        @type key: string
        @param slot: package slot
        @type slot: string
        @return: list (frozenset) of package identifiers
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchKeySlotTag(self, key, slot, tag):
        """
        Search package with given key, slot and tag.

        @param key: package key
        @type key: string
        @param slot: package slot
        @type slot: string
        @param tag: restrict search using tag, if provided
        @type tag: string
        @return: list (frozenset) of package identifiers
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchNeeded(self, needed, elfclass = -1, like = False):
        """
        Search packages that need given NEEDED ELF entry (library name).
        You must implement "*" wildcard support if like is True.

        @param needed: NEEDED ELF entry (shared object library name)
        @type needed: string
        @param elfclass: search NEEDEDs only with given ELF class
        @type elfclass: int
        @keyword like: do not match exact case
        @type like: bool
        @return: list (frozenset) of package identifiers
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchConflict(self, conflict, strings = False):
        """
        Search conflict dependency among packages.

        @param conflict:
        @type conflict: string
        @keyword strings: return a list of conflict names instead of a tuple of
            tuples of entropy package identifier and conflict dependency.
        @type strings: bool
        @return: if "strings" is False, a tuple of tuples of entropy package
            identifier and conflict dependency. if "strings" is True, a list
            (tuple) of conflict dependencies.
        @rtype tuple
        """
        raise NotImplementedError()

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
        @return: list (frozenset) of dependency identifiers (if multi is True)
            or strings (if strings is True) or dependency identifier
        @rtype: int or frozenset
        """
        raise NotImplementedError()

    def searchPackageIdFromDependencyId(self, dependency_id):
        """
        Search package identifiers owning dependency given (in form of
        dependency identifier).

        @param dependency_id: dependency identifier
        @type dependency_id: int
        @return: list (frozenset) of package identifiers owning given dependency
            identifier
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchSets(self, keyword):
        """
        Search package sets in repository using given search keyword.

        @param keyword: package set name to search
        @type keyword: string
        @return: list (frozenset) of package sets available matching given
            keyword
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchProvidedMime(self, mimetype):
        """
        Search package identifiers owning given mimetype. Results are returned
        sorted by package name.

        @param mimetype: mimetype to search
        @type mimetype: string
        @return: list (tuple) of package indentifiers owning given mimetype.
        @rtype: tuple
        """
        raise NotImplementedError()

    def searchSimilarPackages(self, keyword, atom = False):
        """
        Search similar packages (basing on package string given by mystring
        argument) using SOUNDEX algorithm.

        @param keyword: package string to search
        @type keyword: string
        @keyword atom: return full atoms instead of package names
        @type atom: bool
        @return: list (tuple) of similar package names
        @rtype: tuple
        """
        raise NotImplementedError()

    def searchPackages(self, keyword, sensitive = False, slot = None,
            tag = None, order_by = None, just_id = False):
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
        @keyword order_by: order results by "atom", "package_id", "branch",
            "name", "version", "versiontag", "revision", "slot"
        @type order_by: string
        @keyword just_id: just return package identifiers
        @type just_id: bool
        @return: packages found matching given search criterias
        @rtype: tuple
        @raise AttributeError: if order_by value is invalid
        """
        raise NotImplementedError()

    def searchDescription(self, keyword, just_id = False):
        """
        Search packages using given description string as keyword.

        @param keyword: description sub-string to search
        @type keyword: string
        @keyword just_id: if True, only return a list of Entropy package
            identifiers
        @type just_id: bool
        @return: frozenset of tuples of length 2 containing atom and package_id
            values. While if just_id is True, return a list (frozenset) of
            package_ids
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchUseflag(self, keyword, just_id = False):
        """
        Search packages using given use flag string as keyword. An exact search
        will be performed (keyword must match use flag)

        @param keyword: use flag to search
        @type keyword: string
        @keyword just_id: if True, only return a list of Entropy package
            identifiers
        @type just_id: bool
        @return: frozenset of tuples of length 2 containing atom and package_id
            values. While if just_id is True, return a list (frozenset) of
            package_ids
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchHomepage(self, keyword, just_id = False):
        """
        Search packages using given homepage string as keyword.

        @param keyword: description sub-string to search
        @type keyword: string
        @keyword just_id: if True, only return a list of Entropy package
            identifiers
        @type just_id: bool
        @return: frozenset of tuples of length 2 containing atom and package_id
            values. While if just_id is True, return a list (frozenset) of
            package_ids
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchName(self, keyword, sensitive = False, just_id = False):
        """
        Search packages by package name.

        @param keyword: package name to search
        @type keyword: string
        @keyword sensitive: case sensitive?
        @type sensitive: bool
        @keyword just_id: return list of package identifiers (set()) otherwise
            return a list of tuples of length 2 containing atom and package_id
            values
        @type just_id: bool
        @return: list (frozenset) of packages found
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchCategory(self, keyword, like = False, just_id = False):
        """
        Search packages by category name.

        @param keyword: category name
        @type keyword: string
        @keyword like: do not match exact case
        @type like: bool
        @keyword just_id: return list of package identifiers (set()) otherwise
            return a list of tuples of length 2 containing atom and package_id
            values
        @type just_id: bool
        @return: list (frozenset) of tuples of length 2 containing atom and
            package_id values
        @rtype: frozenset
        """
        raise NotImplementedError()

    def searchNameCategory(self, name, category, just_id = False):
        """
        Search packages matching given name and category strings.
        The search is always considered case sensitive.

        @param name: package name to search
        @type name: string
        @param category: package category to search
        @type category: string
        @keyword just_id: return list of package identifiers (set()) otherwise
            return a list of tuples of length 2 containing atom and package_id
            values
        @type just_id: bool
        @return: list (frozenset) of packages found
        @rtype: frozenset
        """
        raise NotImplementedError()

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
        @return: tuple composed by (package_id or -1, idreason or 0,)
        @rtype: tuple
        """
        raise NotImplementedError()

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
        raise NotImplementedError()

    def listAllPackages(self, get_scope = False, order_by = None):
        """
        List all packages in repository.

        @keyword get_scope: return also entropy package revision
        @type get_scope: bool
        @keyword order_by: order by "atom", "idpackage", "package_id", "branch",
            "name", "version", "versiontag", "revision", "slot"
        @type order_by: string
        @return: tuple of tuples of length 3 (or 4 if get_scope is True),
            containing (atom, package_id, branch,) if get_scope is False and
            (package_id, atom, slot, revision,) if get_scope is True
        @rtype: tuple
        @raise AttributeError: if order_by value is invalid
        """
        raise NotImplementedError()

    def listPackageIdsInCategory(self, category, order_by = None):
        """
        List package identifiers available in given category name.

        @param category_id: cateogory name
        @type category_id: int
        @keyword order_by: order by "atom", "idpackage", "package_id", "branch",
            "name", "version", "versiontag", "revision", "slot"
        @type order_by: string
        @return: list (frozenset) of available package identifiers in category.
        @rtype: frozenset
        @raise AttributeError: if order_by value is invalid
        """
        raise NotImplementedError()

    def listAllPackageIds(self, order_by = None):
        """
        List all package identifiers available in repository.

        @keyword order_by: order by "atom", "idpackage", "package_id", "branch",
            "name", "version", "versiontag", "revision", "slot", "date"
        @type order_by: string
        @return: tuple (if order_by) or frozenset of package identifiers
        @rtype: tuple or frozenset
        @raise AttributeError: if order_by value is invalid
        """
        raise NotImplementedError()

    def listAllInjectedPackageIds(self):
        """
        List all injected package identifiers available in repository.

        Injected packages are those not tracking any Source Package Manager
        packages.

        @return: frozenset of package identifiers
        @rtype: frozenset
        """
        raise NotImplementedError()

    def listAllSystemPackageIds(self):
        """
        List all system package identifiers available in repository.

        System packages are those directly marked as part of the base system.

        @return: frozenset of package identifiers
        @rtype: frozenset
        """
        raise NotImplementedError()

    def listAllDependencies(self):
        """
        List all dependencies available in repository.

        @return: list of tuples of length 2 containing
            (dependency id, dependency,)
        @rtype: list
        """
        raise NotImplementedError()

    def listAllSpmUids(self):
        """
        List all Source Package Manager unique package identifiers bindings
        with packages in repository.
        @return: tuple of tuples of length 2 composed by (spm_uid, package_id,)
        @rtype: tuple
        """
        raise NotImplementedError()

    def listAllTrashedSpmUids(self):
        """
        List all Source Package Manager unique package identifiers that have
        been marked as "trashed" by Entropy Server.
        @return: list of identifiers
        @rtype: tuple
        """
        raise NotImplementedError()

    def listAllDownloads(self, do_sort = True, full_path = False):
        """
        List all package download URLs stored in repository.

        @keyword do_sort: sort by name
        @type do_sort: bool
        @keyword full_path: return full URL (not just package file name)
        @type full_path: bool
        @return: tuple (or set if do_sort is True) of package download URLs
        @rtype: tuple or frozenset
        """
        raise NotImplementedError()

    def listAllExtraDownloads(self, do_sort = True):
        """
        List all package extra download URLs stored in repository.
        All the extra download file names must end with etpConst['packagesextraext']
        extension.

        @keyword do_sort: sort by name
        @type do_sort: bool
        @keyword full_path: return full URL (not just package file name)
        @type full_path: bool
        @return: tuple (or set if do_sort is True) of package download URLs
        @rtype: tuple or frozenset
        """
        raise NotImplementedError()

    def listAllFiles(self, clean = False, count = False):
        """
        List all file paths owned by packaged stored in repository.

        @keyword clean: return a clean list (not duplicates)
        @type clean: bool
        @keyword count: count elements and return number
        @type count: bool
        @return: tuple of files available or their count
        @rtype: int or tuple or frozenset
        """
        raise NotImplementedError()

    def listAllCategories(self, order_by = None):
        """
        List all categories available in repository.

        @keyword order_by: order by "category"
        @type order_by: string
        @return: list (frozenset) of available package categories
        @rtype: frozenset
        @raise AttributeError: if order_by value is invalid
        """
        raise NotImplementedError()

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
        raise NotImplementedError()

    def switchBranch(self, package_id, tobranch):
        """
        Switch branch string in repository to new value.

        @param package_id: package identifier
        @type package_id: int
        @param tobranch: new branch value
        @type tobranch: string
        """
        raise NotImplementedError()

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
        raise NotImplementedError()

    def validate(self):
        """
        Validates Entropy repository by doing basic integrity checks.

        @raise SystemDatabaseError: when repository is not reliable
        """
        raise NotImplementedError()

    def integrity_check(self):
        """
        Validates Entropy repository by doing advanced integrity checks.

        @raise SystemDatabaseError: when repository is not reliable
        """
        raise NotImplementedError()

    def _getIdpackagesDifferences(self, foreign_package_ids):
        """
        Return differences between in-repository package identifiers and
        list provided.

        @param foreign_package_ids: list of foreign package_ids
        @type foreign_package_ids: iterable
        @return: tuple composed by package_ids that would be added
            and package_ids that would be removed
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

            self.removePackage(package_id)

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
    def importRepository(dumpfile, db, data = None):
        """
        Import dump file to this database.

        @param dumpfile: dump file to read
        @type dumpfile: string
        @param dbfile: database file path or reference name
        @type dbfile: string
        @keyword data: connection data (dict object)
        @type data: dict or None
        @return: import return code (0 = OK)
        @rtype: int
        @raise AttributeError: if given paths are invalid
        """
        raise NotImplementedError()

    def exportRepository(self, dumpfile):
        """
        Export running database to file.

        @param dumpfile: dump file object to write to
        @type dumpfile: file object (hint: open())
        """
        raise NotImplementedError()

    def checksum(self, do_order = False, strict = True,
                 include_signatures = False, include_dependencies = False):
        """
        Get Repository metadata checksum, useful for integrity verification.
        Note: result is cached in EntropyRepository.live_cache (dict).

        @keyword do_order: order metadata collection alphabetically
        @type do_order: bool
        @keyword strict: improve checksum accuracy
        @type strict: bool
        @keyword include_signatures: also include packages signatures (GPG,
            SHA1, SHA2, etc) into the returned hash
        @type include_signatures: bool
        @keyword include_dependencies: also include package dependencies into
            the returned hash
        @type include_dependencies: bool
        @return: repository checksum
        @rtype: string
        """
        raise NotImplementedError()

    def mtime(self):
        """
        Return last modification time of given repository.

        @return: mtime
        @rtype: float
        @raise IOError: if mtime cannot be retrieved
        @raise OSError: if mtime cannot be retrieved (Operating System error)
        """
        raise NotImplementedError()

    def storeInstalledPackage(self, package_id, repoid, source = 0):
        """
        Note: this is used by installed packages repository (also known as
        client db).
        Add package identifier to the "installed packages table",
        which contains repository identifier from where package has been
        installed and its install request source (user, pulled in
        dependency, etc).

        @param package_id: package indentifier
        @type package_id: int
        @param repoid: repository identifier
        @type repoid: string
        @param source: source identifier (pleas see:
            etpConst['install_sources'])
        @type source: int
        """
        raise NotImplementedError()

    def getInstalledPackageRepository(self, package_id):
        """
        Return repository identifier from where package has been installed from.

        @param package_id: package indentifier
        @type package_id: int
        @return: repository identifier
        @rtype: string or None
        """
        raise NotImplementedError()

    def getInstalledPackageSource(self, package_id):
        """
        Return installed package source id (corresponding to "as dependency",
        "by user", in other words, the reason why the package is installed).
        Its value can be either one of the etpConst['install_sources'] values.
        In case of unavailable information, None is returned.

        @param package_id: package indentifier
        @type package_id: int
        @return: install source identifier
        @rtype: int or None
        """
        raise NotImplementedError()

    def dropInstalledPackageFromStore(self, package_id):
        """
        Note: this is used by installed packages repository (also known as
        client db).
        Remove installed package metadata from "installed packages table".
        Note: this just removes extra metadata information such as repository
        identifier from where package has been installed and its install
        request source (user, pulled in dependency, etc).
        This method DOES NOT remove package from repository (see
        removePackage() instead).

        @param package_id: package indentifier
        @type package_id: int
        """
        raise NotImplementedError()

    def storeSpmMetadata(self, package_id, blob):
        """
        This method stores Source Package Manager package metadata inside
        repository.

        @param package_id: package indentifier
        @type package_id: int
        @param blob: metadata blob
        @type blob: string or buffer
        """
        raise NotImplementedError()

    def retrieveSpmMetadata(self, package_id):
        """
        This method retrieves Source Package Manager package metadata stored
        inside repository.

        @param package_id: package indentifier
        @type package_id: int
        @return: stored metadata
        @rtype: buffer
        """
        raise NotImplementedError()

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
        raise NotImplementedError()

    def dropContent(self):
        """
        Drop all "content" metadata from repository, usually a memory hog.
        Content metadata contains files and directories owned by packages.
        """
        raise NotImplementedError()

    def dropContentSafety(self):
        """
        Drop all "contentsafety" metadata from repository, usually a memory hog.
        ContentSafety metadata contains mtime and sha256 hashes of files owned
        by package.
        """
        raise NotImplementedError()

    def dropChangelog(self):
        """
        Drop all packages' ChangeLogs metadata from repository, a memory hog.
        """
        raise NotImplementedError()

    def dropGpgSignatures(self):
        """
        Drop all packages' GPG signatures.
        """
        raise NotImplementedError()

    def dropAllIndexes(self):
        """
        Drop all repository metadata indexes. Not cache!
        """
        raise NotImplementedError()

    def createAllIndexes(self):
        """
        Create all the repository metadata indexes internally available.
        """
        raise NotImplementedError()

    def regenerateSpmUidMapping(self):
        """
        Regenerate Source Package Manager <-> Entropy package identifiers
        mapping.
        This method will use the Source Package Manger interface.
        """
        raise NotImplementedError()

    def clearTreeupdatesEntries(self, repository):
        """
        This method should be considered internal and not suited for general
        audience. Clear "treeupdates" metadata for given repository identifier.

        @param repository: repository identifier
        @type repository: string
        """
        raise NotImplementedError()

    def resetTreeupdatesDigests(self):
        """
        This method should be considered internal and not suited for general
        audience. Reset "treeupdates" digest metadata.
        """
        raise NotImplementedError()

    def moveSpmUidsToBranch(self, to_branch):
        """
        Note: this is not intended for general audience.
        Move "branch" metadata contained in Source Package Manager package
        identifiers binding metadata to new value given by "from_branch"
        argument.

        @param to_branch: new branch string
        @type to_branch: string
        @keyword from_branch: old branch string
        @type from_branch: string
        """
        raise NotImplementedError()

    # Update status flags, self explanatory.
    REPOSITORY_ALREADY_UPTODATE = -1
    REPOSITORY_NOT_AVAILABLE = -2
    REPOSITORY_GENERIC_ERROR = -3
    REPOSITORY_CHECKSUM_ERROR = -4
    REPOSITORY_PERMISSION_DENIED_ERROR = -5
    REPOSITORY_UPDATED_OK = 0

    @staticmethod
    def update(entropy_client, repository_id, force, gpg):
        """
        Update the content of this repository. Every subclass can implement
        its own update way.
        This method must return a status code that can be either
        EntropyRepositoryBase.REPOSITORY_ALREADY_UPTODATE or
        EntropyRepositoryBase.REPOSITORY_NOT_AVAILABLE or
        EntropyRepositoryBase.REPOSITORY_GENERIC_ERROR or
        EntropyRepositoryBase.REPOSITORY_CHECKSUM_ERROR or
        EntropyRepositoryBase.REPOSITORY_UPDATED_OK
        If your repository is not supposed to be remotely updated, just
        ignore this method.
        Otherwise, if you intend to implement this method, make sure that
        any unprivileged call raises entropy.exceptions.PermissionDenied().
        Only superuser should call this method.

        @param entropy_client: Entropy Client based object
        @type entropy_client: entropy.client.interfaces.Client
        @param repository_id: repository identifier
        @type repository_id: string
        @param force: force update anyway
        @type force: bool
        @param gpg: GPG feature enable
        @type gpg: bool
        @return: status code
        @rtype: int
        """
        raise NotImplementedError()

    @staticmethod
    def revision(repository_id):
        """
        Returns the repository local revision in int format or None, if
        no revision is available.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: repository revision
        @rtype: int or None
        @raise KeyError: if repository is not available
        """
        raise NotImplementedError()

    @staticmethod
    def remote_revision(repository_id):
        """
        Returns the repository remote revision in int format or None, if
        no revision is available.

        @param repository_id: repository identifier
        @type repository_id: string
        @return: repository revision
        @rtype: int or None
        @raise KeyError: if repository is not available
        """
        raise NotImplementedError()

    def maskFilter(self, package_id, live = True):
        """
        Return whether given package identifier is available to user or not,
        reading package masking metadata stored in SystemSettings.
        NOTE: by default, this method doesn't filter any package. Subclasses
        have to reimplement this and setup a filtering logic in order to apply
        some filtering.

        @param package_id: package indentifier
        @type package_id: int
        @keyword live: use live masking feature
        @type live: bool
        @return: tuple composed by package_id and masking reason. If package_id
            returned package_id value == -1, it means that package is masked
            and a valid masking reason identifier is returned as second
            value of the tuple (see SystemSettings['pkg_masking_reasons'])
        @rtype: tuple
        """
        return package_id, 0

    def atomMatchCacheKey(self):
        """
        Return a string that shall be used as part of the atomMatch cache key
        string generation.

        This method is intended to be used by subclasses. The base
        implementation returns an empty string.
        """
        return ""

    def atomMatch(self, atom, matchSlot = None, multiMatch = False,
        maskFilter = True, extendedResults = False, useCache = True):
        """
        Match given atom (or dependency) in repository and return its package
        identifer and execution status.

        @param atom: atom or dependency to match in repository
        @type atom: unicode string
        @keyword matchSlot: match packages with given slot
        @type matchSlot: string
        @keyword multiMatch: match all the available packages, not just the
            best one
        @type multiMatch: bool
        @keyword maskFilter: enable package masking filter
        @type maskFilter: bool
        @keyword extendedResults: return extended results
        @type extendedResults: bool
        @keyword useCache: use on-disk cache
        @type useCache: bool
        @return: tuple of length 2 composed by (package_id or -1, command status
            (0 means found, 1 means error)) or, if extendedResults is True,
            also add versioning information to tuple.
            If multiMatch is True, a tuple composed by a set (containing package
            identifiers) and command status is returned.
        @rtype: tuple or set
        """
        if not atom:
            return -1, 1

        if useCache:
            cached = self.__atomMatchFetchCache(atom, matchSlot,
                multiMatch, maskFilter, extendedResults)
            if cached is not None:
                return cached

        # "or" dependency support
        # app-foo/foo-1.2.3;app-foo/bar-1.4.3?
        if atom.endswith(etpConst['entropyordepquestion']):
            # or dependency!
            atoms = atom[:-1].split(etpConst['entropyordepsep'])
            for s_atom in atoms:
                data, rc = self.atomMatch(s_atom, matchSlot = matchSlot,
                    multiMatch = multiMatch, maskFilter = maskFilter,
                    extendedResults = extendedResults, useCache = useCache)
                if rc == 0:
                    return data, rc

        matchTag = entropy.dep.dep_gettag(atom)
        try:
            matchUse = entropy.dep.dep_getusedeps(atom)
        except InvalidAtom:
            matchUse = ()
        atomSlot = entropy.dep.dep_getslot(atom)
        matchRevision = entropy.dep.dep_get_entropy_revision(atom)
        if isinstance(matchRevision, int):
            if matchRevision < 0:
                matchRevision = None

        # use match
        scan_atom = entropy.dep.remove_usedeps(atom)
        # tag match
        scan_atom = entropy.dep.remove_tag(scan_atom)

        # slot match
        scan_atom = entropy.dep.remove_slot(scan_atom)
        if (matchSlot is None) and (atomSlot is not None):
            matchSlot = atomSlot

        # revision match
        scan_atom = entropy.dep.remove_entropy_revision(scan_atom)

        direction = ''
        justname = True
        pkgkey = ''
        pkgname = ''
        pkgcat = ''
        pkgversion = ''
        stripped_atom = ''
        found_ids = []
        default_package_ids = None

        if scan_atom:

            while True:
                # check for direction
                scan_cpv = entropy.dep.dep_getcpv(scan_atom)
                stripped_atom = scan_cpv
                if scan_atom.endswith("*"):
                    stripped_atom += "*"
                direction = scan_atom[0:-len(stripped_atom)]

                justname = entropy.dep.isjustname(scan_cpv)
                pkgkey = stripped_atom
                if justname == 0:
                    # get version
                    data = entropy.dep.catpkgsplit(scan_cpv)
                    if data is None:
                        break # badly formatted
                    wildcard = ""
                    if scan_atom.endswith("*"):
                        wildcard = "*"
                    pkgversion = data[2]+wildcard+"-"+data[3]
                    pkgkey = entropy.dep.dep_getkey(stripped_atom)

                splitkey = pkgkey.split("/")
                if (len(splitkey) == 2):
                    pkgcat, pkgname = splitkey
                else:
                    pkgcat, pkgname = "null", splitkey[0]

                break


            # IDs found in the database that match our search
            try:
                found_ids, default_package_ids = self.__generate_found_ids_match(
                    pkgkey, pkgname, pkgcat, multiMatch)
            except OperationalError:
                # we are fault tolerant, cannot crash because
                # tables are not available and validateDatabase()
                # hasn't run
                # found_ids = []
                # default_package_ids = None
                pass

        ### FILTERING
        # filter slot and tag
        if found_ids:
            found_ids = self.__filterSlotTagUse(found_ids, matchSlot,
                matchTag, matchUse, direction)
            if maskFilter:
                def _filter(pkg_id):
                    pkg_id, pkg_reason = self.maskFilter(pkg_id)
                    return pkg_id != -1
                found_ids = set(filter(_filter, found_ids))

        ### END FILTERING

        dbpkginfo = set()
        if found_ids:
            dbpkginfo = self.__handle_found_ids_match(found_ids, direction,
                matchTag, matchRevision, justname, stripped_atom, pkgversion)

        if not dbpkginfo:
            if extendedResults:
                if multiMatch:
                    x = set()
                else:
                    x = (-1, 1, None, None, None,)
                self.__atomMatchStoreCache(
                    atom, matchSlot,
                    multiMatch, maskFilter,
                    extendedResults, result = (x, 1)
                )
                return x, 1
            else:
                if multiMatch:
                    x = set()
                else:
                    x = -1
                self.__atomMatchStoreCache(
                    atom, matchSlot,
                    multiMatch, maskFilter,
                    extendedResults, result = (x, 1)
                )
                return x, 1

        if multiMatch:
            if extendedResults:
                x = set([(x[0], 0, x[1], self.retrieveTag(x[0]), \
                    self.retrieveRevision(x[0])) for x in dbpkginfo])
                self.__atomMatchStoreCache(
                    atom, matchSlot,
                    multiMatch, maskFilter,
                    extendedResults, result = (x, 0)
                )
                return x, 0
            else:
                x = set([x[0] for x in dbpkginfo])
                self.__atomMatchStoreCache(
                    atom, matchSlot,
                    multiMatch, maskFilter,
                    extendedResults, result = (x, 0)
                )
                return x, 0

        if len(dbpkginfo) == 1:
            x = dbpkginfo.pop()
            if extendedResults:
                x = (x[0], 0, x[1], self.retrieveTag(x[0]),
                    self.retrieveRevision(x[0]),)

                self.__atomMatchStoreCache(
                    atom, matchSlot,
                    multiMatch, maskFilter,
                    extendedResults, result = (x, 0)
                )
                return x, 0
            else:
                self.__atomMatchStoreCache(
                    atom, matchSlot,
                    multiMatch, maskFilter,
                    extendedResults, result = (x[0], 0)
                )
                return x[0], 0

        # if a default_package_id is given by __generate_found_ids_match
        # we need to respect it
        # NOTE: this is only used by old-style virtual packages
        # if (len(found_ids) > 1) and (default_package_id is not None):
        #    if default_package_id in found_ids:
        #        found_ids = set([default_package_id])
        dbpkginfo = list(dbpkginfo)
        if default_package_ids is not None:
            # at this point, if default_package_ids is not None (== set())
            # we must exclude all the package_ids not available in this list
            # from dbpkginfo
            dbpkginfo = [x for x in dbpkginfo if x[0] in default_package_ids]
        # dbpkginfo might have become empty now!

        pkgdata = {}
        versions = set()

        for x in dbpkginfo:
            info_tuple = (x[1], self.retrieveTag(x[0]), \
                self.retrieveRevision(x[0]))
            versions.add(info_tuple)
            pkgdata[info_tuple] = x[0]

        # if matchTag is not specified, and tagged and non-tagged packages
        # are available, prefer non-tagged ones, excluding others.
        if not matchTag and dbpkginfo:

            non_tagged_available = False
            tagged_available = False
            for ver, tag, rev in versions:
                if tag:
                    tagged_available = True
                else:
                    non_tagged_available = True
                if tagged_available and non_tagged_available:
                    break

            if tagged_available and non_tagged_available:
                # filter out tagged
                versions = set(((ver, tag, rev) for ver, tag, rev in versions \
                    if not tag))

        if versions:
            # it looks like we wiped out all the
            newer = entropy.dep.get_entropy_newer_version(list(versions))[0]
            x = pkgdata[newer]
            rc = 0
        else:
            # this is due to dbpkginfo being empty, return
            # not found. This is due to default_package_ids
            # email search: "description: playing freecell in KPatience"
            newer = (None, None, None)
            x = -1
            rc = 1

        if extendedResults:
            x = (x, rc, newer[0], newer[1], newer[2])
            self.__atomMatchStoreCache(
                atom, matchSlot,
                multiMatch, maskFilter,
                extendedResults, result = (x, rc)
            )
            return x, rc
        else:
            self.__atomMatchStoreCache(
                atom, matchSlot,
                multiMatch, maskFilter,
                extendedResults, result = (x, rc)
            )
            return x, rc

    def __generate_found_ids_match(self, pkgkey, pkgname, pkgcat, multiMatch):

        if pkgcat == "null":
            results = self.searchName(pkgname, sensitive = True,
                just_id = True)
        else:
            results = self.searchNameCategory(pkgname, pkgcat, just_id = True)

        old_style_virtuals = None
        # if it's a PROVIDE, search with searchProvide
        # there's no package with that name
        if (not results) and (pkgcat == self.VIRTUAL_META_PACKAGE_CATEGORY):

            # look for default old-style virtual
            virtuals = self.searchProvidedVirtualPackage(pkgkey)
            if virtuals:
                old_style_virtuals = set([x[0] for x in virtuals if x[1]])
                flat_virtuals = [x[0] for x in virtuals]
                if not old_style_virtuals:
                    old_style_virtuals = set(flat_virtuals)
                results = flat_virtuals

        if not results: # nothing found
            del results
            return set(), old_style_virtuals

        if len(results) > 1: # need to choose

            # if we are dealing with old-style virtuals, there is no need
            # to go further and search stuff using category and name since
            # we wouldn't find anything new
            if old_style_virtuals is not None:
                return set(results), old_style_virtuals

            # if it's because category differs, it's a problem
            found_cat = None
            found_id = None
            cats = set()
            for package_id in results:
                cat = self.retrieveCategory(package_id)
                cats.add(cat)
                if (cat == pkgcat) or \
                    ((pkgcat == self.VIRTUAL_META_PACKAGE_CATEGORY) and \
                        (cat == pkgcat)):
                    # in case of virtual packages only
                    # (that they're not stored as provide)
                    found_cat = cat

            # if we found something at least...
            if (not found_cat) and (len(cats) == 1) and \
                (pkgcat in (self.VIRTUAL_META_PACKAGE_CATEGORY, "null")):
                found_cat = sorted(cats)[0]

            if not found_cat:
                # got the issue
                del results
                return set(), old_style_virtuals

            # we can use found_cat
            pkgcat = found_cat

            # we need to search using the category
            if (not multiMatch) and (pkgcat == "null"):
                # we searched by name, we need to search using category
                results = self.searchNameCategory(
                    pkgname, pkgcat, just_id = True)

            # if we get here, we have found the needed IDs
            return set(results), old_style_virtuals

        ###
        ### just found one result
        ###

        package_id = set(results).pop()
        # if pkgcat is virtual, it can be forced
        if (pkgcat == self.VIRTUAL_META_PACKAGE_CATEGORY) and \
            (old_style_virtuals is not None):
            # in case of virtual packages only
            # (that they're not stored as provide)
            pkgcat, pkgname = self.retrieveKeySplit(package_id)

        # check if category matches
        if pkgcat != "null":
            found_cat = self.retrieveCategory(package_id)
            if pkgcat == found_cat:
                return set([package_id]), old_style_virtuals
            del results
            return set(), old_style_virtuals # nope nope

        # very good, here it is
        del results
        return set([package_id]), old_style_virtuals


    def __handle_found_ids_match(self, found_ids, direction, matchTag,
            matchRevision, justname, stripped_atom, pkgversion):

        dbpkginfo = set()
        # now we have to handle direction
        if ((direction) or ((not direction) and (not justname)) or \
            ((not direction) and (not justname) \
                and stripped_atom.endswith("*"))) and found_ids:

            if (not justname) and \
                ((direction == "~") or (direction == "=") or \
                ((not direction) and (not justname)) or ((not direction) and \
                    not justname and stripped_atom.endswith("*"))):
                # any revision within the version specified
                # OR the specified version

                if ((not direction) and (not justname)):
                    direction = "="

                # remove gentoo revision (-r0 if none)
                if (direction == "="):
                    if (pkgversion.split("-")[-1] == "r0"):
                        pkgversion = entropy.dep.remove_revision(
                            pkgversion)

                if (direction == "~"):
                    pkgrevision = entropy.dep.dep_get_spm_revision(
                        pkgversion)
                    pkgversion = entropy.dep.remove_revision(pkgversion)

                for package_id in found_ids:

                    dbver = self.retrieveVersion(package_id)
                    if (direction == "~"):
                        myrev = entropy.dep.dep_get_spm_revision(
                            dbver)
                        myver = entropy.dep.remove_revision(dbver)
                        if myver == pkgversion and pkgrevision <= myrev:
                            # found
                            dbpkginfo.add((package_id, dbver))
                    else:
                        # media-libs/test-1.2* support
                        if pkgversion[-1] == "*":
                            if dbver.startswith(pkgversion[:-1]):
                                dbpkginfo.add((package_id, dbver))
                        elif (matchRevision is not None) and (pkgversion == dbver):
                            dbrev = self.retrieveRevision(package_id)
                            if dbrev == matchRevision:
                                dbpkginfo.add((package_id, dbver))
                        elif (pkgversion == dbver) and (matchRevision is None):
                            dbpkginfo.add((package_id, dbver))

            elif (direction.find(">") != -1) or (direction.find("<") != -1):

                if not justname:

                    # remove revision (-r0 if none)
                    if pkgversion.endswith("r0"):
                        # remove
                        entropy.dep.remove_revision(pkgversion)

                    for package_id in found_ids:

                        revcmp = 0
                        tagcmp = 0
                        if matchRevision is not None:
                            dbrev = self.retrieveRevision(package_id)
                            revcmp = const_cmp(matchRevision, dbrev)

                        if matchTag is not None:
                            dbtag = self.retrieveTag(package_id)
                            tagcmp = const_cmp(matchTag, dbtag)

                        dbver = self.retrieveVersion(package_id)
                        pkgcmp = entropy.dep.compare_versions(
                            pkgversion, dbver)

                        if pkgcmp is None:
                            warnings.warn("WARNING, invalid version string " + \
                            "stored in %s: %s <-> %s" % (
                                self.name, pkgversion, dbver,)
                            )
                            continue

                        if direction == ">":

                            if pkgcmp < 0:
                                dbpkginfo.add((package_id, dbver))
                            elif (matchRevision is not None) and pkgcmp <= 0 \
                                and revcmp < 0:
                                dbpkginfo.add((package_id, dbver))

                            elif (matchTag is not None) and tagcmp < 0:
                                dbpkginfo.add((package_id, dbver))

                        elif direction == "<":

                            if pkgcmp > 0:
                                dbpkginfo.add((package_id, dbver))
                            elif (matchRevision is not None) and pkgcmp >= 0 \
                                and revcmp > 0:
                                dbpkginfo.add((package_id, dbver))

                            elif (matchTag is not None) and tagcmp > 0:
                                dbpkginfo.add((package_id, dbver))

                        elif direction == ">=":

                            if (matchRevision is not None) and pkgcmp <= 0:
                                if pkgcmp == 0:
                                    if revcmp <= 0:
                                        dbpkginfo.add((package_id, dbver))
                                else:
                                    dbpkginfo.add((package_id, dbver))
                            elif pkgcmp <= 0 and matchRevision is None:
                                dbpkginfo.add((package_id, dbver))
                            elif (matchTag is not None) and tagcmp <= 0:
                                dbpkginfo.add((package_id, dbver))

                        elif direction == "<=":

                            if (matchRevision is not None) and pkgcmp >= 0:
                                if pkgcmp == 0:
                                    if revcmp >= 0:
                                        dbpkginfo.add((package_id, dbver))
                                else:
                                    dbpkginfo.add((package_id, dbver))
                            elif pkgcmp >= 0 and matchRevision is None:
                                dbpkginfo.add((package_id, dbver))
                            elif (matchTag is not None) and tagcmp >= 0:
                                dbpkginfo.add((package_id, dbver))

        else: # just the key

            dbpkginfo = set([(x, self.retrieveVersion(x),) for x in found_ids])

        return dbpkginfo

    def __atomMatchFetchCache(self, *args):
        if self._caching:
            ck_sum = self.checksum(strict = False)
            hash_str = self.__atomMatch_gen_hash_str(args)
            cached = entropy.dump.loadobj(
                "%s/%s/%s_%s_%s" % (
                    self.__db_match_cache_key,
                    self.name,
                    self.atomMatchCacheKey(),
                    ck_sum,
                    hash_str,
                    )
                )
            return cached

    def __atomMatch_gen_hash_str(self, args):
        data_str = repr(args)
        sha1 = hashlib.sha1()
        if const_is_python3():
            sha1.update(data_str.encode("utf-8"))
        else:
            sha1.update(data_str)
        return sha1.hexdigest()

    def __atomMatchStoreCache(self, *args, **kwargs):
        if self._caching:
            ck_sum = self.checksum(strict = False)
            hash_str = self.__atomMatch_gen_hash_str(args)
            self._cacher.push(
                "%s/%s/%s_%s_%s" % (
                    self.__db_match_cache_key,
                    self.name,
                    self.atomMatchCacheKey(),
                    ck_sum,
                    hash_str,
                    ),
                kwargs.get('result'),
                async = False)

    def __filterSlot(self, package_id, slot):
        if slot is None:
            return package_id
        dbslot = self.retrieveSlot(package_id)
        if dbslot == slot:
            return package_id

    def __filterTag(self, package_id, tag, operators):
        if tag is None:
            return package_id

        dbtag = self.retrieveTag(package_id)
        compare = const_cmp(tag, dbtag)
        # cannot do operator compare because it breaks the tag concept
        if compare == 0:
            return package_id

    def __filterUse(self, package_id, uses):
        if not uses:
            return package_id
        pkguse = set(self.retrieveUseflags(package_id))
        enabled = set([x for x in uses if not x.startswith("-")])
        disabled = set(uses) - enabled

        # USE defaults support
        enabled_use = set()
        for use in enabled:
            if use.endswith("(+)"):
                use = use[:-3]
                dis_use = "-" + use
                if dis_use not in pkguse:
                    # consider it enabled by default if it's not
                    # disabled
                    pkguse.add(use)
            elif use.endswith("(-)"):
                # NOTE: this case should be filtered out by SPM
                use = use[:-3]
                if use not in pkguse:
                    # force disabled by default if it's not
                    # enabled
                    pkguse.add("-" + use)
            enabled_use.add(use)

        disabled_use = set()
        for use in disabled:
            # use starts with "-" here, example: -foo
            if use.endswith("(+)"):
                use = use[:-3]
                # 3 cases here:
                # 1 - use flag is not enabled (but available)
                #     do nothing. we want it not enabled anyway
                # 2 - use flag is enabled (and available)
                #     do nothing, this will be caught later in the function
                # 3 - use flag is not enabled (and also NOT available)
                #     since we cannot detect if a use flag is not available
                #     let's suppose that it won't be available and won't be
                #     added
                # TODO: for case 3, we would need a new metadatum called
                #       "disabled_useflags"
                en_use = use[1:]
                if use not in pkguse:
                    pkguse.add(en_use)
            elif use.endswith("(-)"):
                # NOTE: this case should be filtered out by SPM
                use = use[:-3]
                en_use = use[1:]
                # mark it as disabled if it's not available
                if en_use not in pkguse:
                    pkguse.add(use)
            else:
                # for compatibility reasons with older Entropy versions,
                # use flags not in pkguse are considered disabled.
                en_use = use[1:]
                if en_use not in pkguse:
                    pkguse.add(use)
            disabled_use.add(use)

        enabled_not_satisfied = enabled_use - pkguse
        # check enabled
        if enabled_not_satisfied:
            return None
        # check disabled
        disabled_not_satisfied = disabled_use - pkguse
        if disabled_not_satisfied:
            return None
        return package_id

    def __filterSlotTagUse(self, found_ids, slot, tag, use, operators):

        def myfilter(package_id):

            package_id = self.__filterSlot(package_id, slot)
            if not package_id:
                return False

            package_id = self.__filterUse(package_id, use)
            if not package_id:
                return False

            package_id = self.__filterTag(package_id, tag, operators)
            if not package_id:
                return False

            return True

        return set(filter(myfilter, found_ids))
