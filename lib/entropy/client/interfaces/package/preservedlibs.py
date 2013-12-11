# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
import collections
import errno
import os
import stat

from entropy.const import const_convert_to_unicode


class PreservedLibraries(object):
    """
    Preserved libraries management class.

    This class can be used to determine if a library should be
    preserved, garbage collect the currently preserved libraries,
    retrieving the list of preserved libraries, etc.

    An instance of this class should be used just for one package and then
    thrown away.

    Installed Packages Repository locking must be done externally.
    """

    def __init__(self, installed_repository, installed_package_id,
                 provided_libraries, root = None):
        """
        Object constructor.

        @param installed_repository: an EntropyRepository object pointing
            to the installed packages repository
        @type installed_repository: EntropyRepository
        @param installed_package_id: the installed packages repository package
            identifier
        @type installed_package_id: int
        @param provided_libraries: set of libraries that a package provides,
            typically this is the data returned by
            EntropyRepository.retrieveProvidedLibraries()
        @type provided_libraries: set
        @keyword root: path to the root directory minus the trailing "/".
            For "/" it's just "" or None.
        @type root: string
        """
        self._inst_repo = installed_repository
        self._package_id = installed_package_id
        self._raw_provided = provided_libraries
        self._provided = dict(((l_path, (library, elfclass, l_path)) for
                               library, l_path, elfclass in provided_libraries))
        self._root = root or const_convert_to_unicode("")
        self._search_needed_cache = {}

    def installed_repository(self):
        """
        Return the installed packages repository used by this object.
        """
        return self._inst_repo

    def package_id(self):
        """
        Return the installed packages repository package identifier.
        """
        return self._package_id

    def resolve(self, library_path):
        """
        Resolve the given library path into a (library, elfclass, path) tuple.
        A tuple is returned iff it can be found in the provided libraries
        metadata passed during initialization of this object, None otherwise.

        @param library_path: path to a library that would be removed (without
            the root prefix)
        @type library_path: string
        @return: a (library name, elf class, library path) tuple or None
        """
        return self._provided.get(library_path)

    def determine(self, library_path):
        """
        Determine if the passed library path requires protection.

        The returned data is a set of paths that should be protected and
        stored in the installed packages repository.

        @param library_path: path to a library that would be removed (without
            the root prefix)
        @type library_path: string
        @return: set of paths to protect
        @rtype: set
        """
        provided_path = self._provided.get(library_path)
        paths = set()

        if provided_path is None:
            # the item should not be protected
            return paths

        library, elfclass, _path = provided_path

        installed_package_ids = set(self._search_needed(library, elfclass))
        # drop myself from the list
        installed_package_ids.discard(self._package_id)

        if not installed_package_ids:
            # no packages need this library
            return paths

        paths.update(self._follow(library_path))
        return paths

    def _follow(self, library_path):
        """
        Follow library_path symlinks and generate a sequence of paths.

        @param library_path: path to a library that would be removed (without
            the root prefix)
        @type library_path: string
        @return: a sequence of paths
        @rtype: collections.deque
        """
        paths = collections.deque()

        recursion = 128
        root_library_path = self._root + library_path
        symlinks = {}
        hardlinks = set()

        # Also see:
        # portage.git commit: 32d19be14e22ada479963ba8627452f5f2d89b94

        while recursion:
            recursion -= 1

            try:
                l_stat = os.lstat(root_library_path)
            except OSError as err:
                if err.errno != errno.ENOENT:
                    raise
                break

            if stat.S_ISLNK(l_stat.st_mode):
                path_link = os.readlink(root_library_path)
                root_library_path = os.path.join(
                    os.path.dirname(root_library_path),
                    path_link)

                # delay symlinks add, due to Gentoo bug #406837
                symlinks[library_path] = path_link

                library_path = os.path.join(
                    os.path.dirname(library_path),
                    path_link)

                continue

            elif stat.S_ISREG(l_stat.st_mode):
                paths.append(library_path)
                hardlinks.add(library_path)

            break

        for library_path, target in symlinks.items():
            target_path = os.path.join(
                os.path.dirname(library_path), target)
            if target_path in hardlinks:
                paths.append(library_path)

        return paths

    def _search_needed(self, library, elfclass):
        """
        Search the package ids that need the given library.
        """
        cache_key = (library, elfclass)
        installed_package_ids = self._search_needed_cache.get(
            cache_key)
        if installed_package_ids is None:
            installed_package_ids = self._inst_repo.searchNeeded(
                library, elfclass = elfclass)
            self._search_needed_cache[cache_key] = installed_package_ids

        return installed_package_ids

    def needed(self, library_path):
        """
        Return a set of installed packages identifiers that need the
        given library.

        @param library_path: path to a library that would be removed (without
            the root prefix)
        @type library_path: string
        @return: set of package identifiers
        @rtype: set
        """
        provided_path = self._provided.get(library_path)
        if provided_path is None:
            return set()

        library, elfclass, _path = provided_path
        return self._search_needed(library, elfclass)

    def list(self):
        """
        Return a list of all the preserved libraries items stored in the
        registry.
        The list is composed of a tuple (library, elfclass, path, atom).

        @return: a list of preserved library items (library,
            elfclass, path, atom)
        @rtype: list
        """
        return self._inst_repo.listAllPreservedLibraries()

    def collect(self):
        """
        Return a list of collectable preserved libraries items that can be
        removed from the registry in the installed packages repository.

        @return: a list of preserved library items (library, elfclass, path)
        @rtype: list
        """
        collectables = []

        for library, elfclass, path, _atom in self.list():

            item = (library, elfclass, path)
            root_path = self._root + path

            # path no longer exists
            if not os.path.lexists(root_path):
                collectables.append(item)
                continue

            # broken symlink, gc
            if not os.path.exists(root_path):
                collectables.append(item)
                continue

            # are all installed packages happy?
            package_ids = self._search_needed(library, elfclass)
            if not package_ids:
                collectables.append(item)
                continue

            # is the library provided by any package?
            providers = self._inst_repo.resolveNeeded(
                library, elfclass = elfclass, extended = True)

            # There is a trade-off here. We would like to check if
            # the provider is the same of path, but we would miss the
            # libraries that moved from like /lib to /usr/lib.
            # An alternative would be to check if all the packages
            # in package_ids can reach at least one of the providers
            # but this would be quite expensive to do. Since this is
            # anyway a best-effort service and 99% of the cases are already
            # handled on the packaging side ("server" side), we could
            # just accept that providers, if any, are reachable by consumers.
            if providers:
                collectables.append(item)
                continue

        return collectables

    def remove(self, library_path):
        """
        Remove the given preserved library element from the system.
        This method will not unregister the element from the registry,
        please use unregister().

        @param library_path: the path to the library
        @type library_path: string
        @return: a sequence of path that haven't been removed and their reasons
        @rtype: collections.queue
        """
        failed = collections.deque()

        for lib_path in self._follow(library_path):
            root_lib_path = self._root + lib_path

            try:
                os.remove(root_lib_path)
            except (OSError, IOError) as err:
                if err.errno != errno.ENOENT:
                    failed.append((root_lib_path, err))

        return failed

    def register(self, library, elfclass, path, atom):
        """
        Register the given preserved library element into the registry in
        the installed packages repository.

        @param library: the library name
        @type library: string
        @param elfclass: the ELF class of the library
        @type elfclass: int
        @param path: the path to the library
        @type path: string
        """
        return self._inst_repo.insertPreservedLibrary(
            library, elfclass, path, atom)

    def unregister(self, library, elfclass, path):
        """
        Unregister the given preserved library element from the registry in
        the installed packages repository.

        @param library: the library name
        @type library: string
        @param elfclass: the ELF class of the library
        @type elfclass: int
        @param path: the path to the library
        @type path: string
        """
        return self._inst_repo.removePreservedLibrary(library, elfclass, path)
