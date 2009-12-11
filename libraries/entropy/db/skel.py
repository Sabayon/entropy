# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework repository database prototype classes module}.
"""


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
        Called during EntropyRepository instance shutdown (closeDB).

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def add_package_hook(self, entropy_repository_instance, idpackage,
        package_data):
        """
        Called after the addition of a package from EntropyRepository.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @param idpackage: Entropy repository package identifier
        @type idpackage: int
        @param package_data: package metadata used for insertion
            (see addPackage)
        @type package_data: dict
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def remove_package_hook(self, entropy_repository_instance, idpackage,
        from_add_package):
        """
        Called after the removal of a package from EntropyRepository.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @param idpackage: Entropy repository package identifier
        @type idpackage: int
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
        idpackage):
        """
        Called after EntropyRepository treeupdates move action execution for
        given idpackage in given EntropyRepository instance.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @param idpackage: Entropy repository package identifier
        @type idpackage: int
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def treeupdates_slot_move_action_hook(self, entropy_repository_instance,
        idpackage):
        """
        Called after EntropyRepository treeupdates slot move action
        execution for given idpackage in given EntropyRepository instance.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @param idpackage: Entropy repository package identifier
        @type idpackage: int
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0

    def reverse_dependencies_tree_generation_hook(self,
        entropy_repository_instance):
        """
        This hook is called inside
        EntropyRepository.generateReverseDependenciesMetadata() method at
        the very end of the function code.
        Every time that repository is "tainted" with new packages, sooner or
        later that function is called.

        @param entropy_repository_instance: EntropyRepository instance
        @type entropy_repository_instance: EntropyRepository
        @return: execution status code, return nonzero for errors, this will
            raise a RepositoryPluginError exception.
        @rtype: int
        """
        return 0
