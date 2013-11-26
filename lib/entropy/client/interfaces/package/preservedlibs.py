# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Interface}.

"""
import os


class PreservedLibraries(object):
    """
    Preserved libraries management class.

    This class can be used to determine if a library should be
    preserved, garbage collect the currently preserved libraries,
    retrieving the list of preserved libraries, etc.

    An instance of this class should be used just for one package and then
    thrown away.
    """

    def __init__(self, installed_repository, provided_libraries, root = None):
        """
        Object constructor.

        @param installed_repository: an EntropyRepository object pointing
            to the installed packages repository
        @type installed_repository: EntropyRepository
        @param provided_libraries: set of libraries that a package provides,
            typically this is the data returned by
            EntropyRepository.retrieveProvidedLibraries()
        @type provided_libraries: set
        @keyword root: path to the root directory minus the trailing "/".
            For "/" it's just "" or None.
        @type root: string
        """
        self._inst_repo = installed_repository
        self._raw_provided = provided_libraries
        self._provided = dict(((l_path, (library, l_path, elfclass)) for
                               library, l_path, elfclass in provided_libraries))
        self._root = root or ""
        self._search_needed_cache = {}

    def installed_repository(self):
        """
        Return the installed packages repository used by this object.
        """
        return self._inst_repo

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

        library, _path, elfclass = provided_path

        installed_package_ids = self._search_needed(library, elfclass)
        if not installed_package_ids:
            # no packages need this library
            return paths

        recursion = 100
        root_library_path = self._root + library_path

        paths.add(library_path)
        while os.path.islink(root_library_path) and recursion:
            # avoid infinite recursion
            recursion -= 1

            path_link = os.readlink(root_library_path)
            root_library_path = os.path.join(
                os.path.dirname(root_library_path),
                path_link)

            library_path = os.path.join(
                os.path.dirname(library_path),
                path_link)
            paths.add(library_path)

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

        library, _path, elfclass = provided_path
        return self._search_needed(library, elfclass)

    def collect(self):
        """
        Return a list of collectable preserved libraries items that can be
        removed from the registry in the installed packages repository.

        @return: a list of preserved library items (library, elfclass, path)
        @rtype: list
        """
        preserved_libs = self._inst_repo.listAllPreservedLibraries()

        collectables = []
        for library, elfclass, path in preserved_libs:

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

            # is the file owned by a package in the repo?
            # if so, we assume that the entry could be removed
            # from the registry
            if self._inst_repo.isFileAvailable(path):
                collectables.append(item)
                continue

        return collectables

    def remove(self, library, elfclass, path):
        """
        Remove the given preserved library element from the registry in
        the installed packages repository.
        """
        self._inst_repo.removePreservedLibrary(library, elfclass, path)
