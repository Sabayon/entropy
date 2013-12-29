# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Package Sets Interface}.
    Package sets can be considered groups of packages organized by
    features. For example, KDE 5.1 packages are grouped inside @kde-5.1
    set and user can install all of them by just choosing to @kde-5.1.

"""
import errno
import os
import codecs

from entropy.i18n import _
from entropy.const import etpConst, const_setup_perms, \
    const_convert_to_unicode, const_isunicode
from entropy.exceptions import InvalidPackageSet
from entropy.core.settings.base import SystemSettings

import entropy.dep


class Sets(object):

    """
    Entropy Client Package Sets interface.
    Package sets are (..) sets of package strings that can be referenced
    using a mnemonic name. For exmaple: the @entropy set is composed by
    all the packages that are part of the Entropy project (equo, reagent, etc).
    """

    SET_PREFIX = etpConst['packagesetprefix']

    def __init__(self, entropy_client):
        self._entropy = entropy_client
        self._settings = SystemSettings()

    def expand(self, package_set, raise_exceptions = True):
        """
        Expand given package set into a set of package matches, recursively.

        @param package_set: the package set name (including its "@" prefix)
        @type package_set: string
        @keyword raise_exceptions: if True, the function is allowed to turn
            possible warnings (max recursion reached, invalid package set) into
            errors (raising entropy.exceptions.InvalidPackageSet)
        @type raise_exceptions: bool

        @raise entropy.exceptions.InvalidPackageSet: if raise_exceptions is
            True and a maximum recursion level has been reached or a package set
            is not found.
        """
        max_recursion_level = 50
        recursion_level = 0
        set_prefix = Sets.SET_PREFIX

        def do_expand(myset, recursion_level, max_recursion_level):
            recursion_level += 1
            if recursion_level > max_recursion_level:
                raise InvalidPackageSet(
                    'corrupted, too many recursions: %s' % (myset,))

            set_data = self.match(myset)
            if not set_data:
                raise InvalidPackageSet('not found: %s' % (myset,))
            set_from, package_set, mydata = set_data

            mypkgs = set()
            for fset in mydata: # recursively
                if fset.startswith(set_prefix):
                    mypkgs |= do_expand(fset, recursion_level,
                        max_recursion_level)
                else:
                    mypkgs.add(fset)

            return mypkgs

        if not package_set.startswith(set_prefix):
            package_set = "%s%s" % (set_prefix, package_set,)

        try:
            mylist = do_expand(package_set, recursion_level,
                max_recursion_level)
        except InvalidPackageSet:
            if raise_exceptions:
                raise
            mylist = set()

        return mylist

    def available(self, match_repo = None):
        """
        Return a list of available package sets data (list of tuples composed by
           (repository id [__user__ for use defined set], set name, set content)

        @keyword match_repo: match given repository identifiers list (if passed)
        @type match_repo: tuple
        @return: list of available package sets data
        @rtype: list
        """
        return self.match('', match_repo = match_repo, search = True)

    def search(self, package_set, match_repo = None):
        """
        Search a package set among available repositories.
        Return a list of package sets data (list of tuples composed by
           (repository id [__user__ for use defined set], set name, set content)

        @param package_set: package set search term
        @type package_set: string
        @keyword match_repo: match given repository identifiers list (if passed)
        @type match_repo: tuple
        @return: list of package sets data
        @rtype: list
        """
        if package_set == '*':
            package_set = ''
        return self.match(package_set, match_repo = match_repo, search = True)

    def match(self, package_set, multi_match = False, match_repo = None,
        search = False):
        """
        Match a package set, returning its data.
        If multi_match is False (default), data returned will be in tuple form,
        composed by 3 elements: (repository [__user__ if user defined],
        set name, list (frozenset) of package names in set).
        If multi_match is True, a list of tuples (like the one above) will be
        returned.

        @keyword multi_match: match across all the repositories and return
            all the results (not just the best one)
        @type multi_match: bool
        @keyword match_repo: match given repository identifiers list (if passed)
        @type match_repo: tuple
        @keyword search: use search instead of matching (default is False)
        @type search: bool
        """
        # strip out "@" from "@packageset", so that both ways are supported
        package_set = package_set.lstrip(Sets.SET_PREFIX)
        # support match in repository from shell
        # set@repo1,repo2,repo3
        package_set, repos = entropy.dep.dep_get_match_in_repos(
            package_set)
        if (match_repo is None) and (repos is not None):
            match_repo = repos

        valid_repos = self._entropy.filter_repositories(
            self._entropy.repositories())

        if match_repo and (type(match_repo) in (list, tuple, set)):
            valid_repos = list(match_repo)

        # if we search, we return all the matches available
        if search:
            multi_match = True

        set_data = []

        while True:

            # ALLOW server-side caller to match sets in /etc/entropy/sets
            # if not server_repos:
            sys_pkgsets = self._settings['system_package_sets']
            if search:
                mysets = [x for x in list(sys_pkgsets.keys()) if \
                    (x.find(package_set) != -1)]
                for myset in mysets:
                    mydata = sys_pkgsets.get(myset)
                    set_data.append((etpConst['userpackagesetsid'],
                        const_convert_to_unicode(myset), mydata.copy(),))
            else:
                mydata = sys_pkgsets.get(package_set)
                if mydata is not None:
                    set_data.append((etpConst['userpackagesetsid'],
                        const_convert_to_unicode(package_set), mydata,))
                    if not multi_match:
                        break

            for repoid in valid_repos:
                dbconn = self._entropy.open_repository(repoid)
                if search:
                    mysets = dbconn.searchSets(package_set)
                    for myset in mysets:
                        mydata = dbconn.retrievePackageSet(myset)
                        set_data.append((repoid, myset, mydata.copy(),))
                else:
                    mydata = dbconn.retrievePackageSet(package_set)
                    if mydata:
                        set_data.append((repoid, package_set, mydata,))
                        if not multi_match:
                            break

            break

        if not set_data:
            if multi_match:
                return []
            return tuple()

        if multi_match:
            return set_data

        return set_data.pop(0)

    def add(self, set_name, set_atoms):
        """
        Add a user-defined package set to Entropy Client (changes are permanent)

        @param set_name: package set name
        @type set_name: string
        @param set_atoms: list of package names in given set
        @type set_atoms: list (set)
        @raise entropy.exceptions.InvalidPackageSet: if package set data
            passed is invalid (non ASCII chars, invalid set_name).
            The encapsulated error string will contain a mnemonic reason.
        """
        def _ensure_package_sets_dir():
            sets_dir = SystemSettings.packages_sets_directory()
            if not os.path.isdir(sets_dir):
                if os.path.lexists(sets_dir):
                    os.remove(sets_dir)
                os.makedirs(sets_dir, 0o775)
                const_setup_perms(sets_dir, etpConst['entropygid'],
                    recursion = False)

        if not const_isunicode(set_name):
            raise InvalidPackageSet("%s %s" % (
                set_name, "must be unicode",))

        if set_name.startswith(etpConst['packagesetprefix']):
            raise InvalidPackageSet("%s %s '%s'" % (
                set_name, "cannot start with", etpConst['packagesetprefix'],))
        set_match = self.match(set_name)
        if set_match:
            raise InvalidPackageSet(_("Name already taken"))

        _ensure_package_sets_dir()
        set_file = os.path.join(SystemSettings.packages_sets_directory(),
                                set_name)

        set_file_tmp = set_file + ".sets_add_tmp"
        enc = etpConst['conf_encoding']
        try:
            with codecs.open(set_file_tmp, "w", encoding=enc) as f:
                for x in set_atoms:
                    f.write(x)
                    f.write("\n")
            os.rename(set_file_tmp, set_file)
        except (OSError, IOError) as err:
            raise InvalidPackageSet(_("Cannot create the element"))
        self._settings['system_package_sets'][set_name] = set(set_atoms)

    def remove(self, set_name):
        """
        Remove a user-defined package set from Entropy Client
        (changes are permanent)

        @param set_name: package set name
        @type set_name: string
        @raise entropy.exceptions.InvalidPackageSet: if package set data
            passed is invalid (non ASCII chars, invalid set_name).
            The encapsulated error string will contain a mnemonic reason.
        """
        if not const_isunicode(set_name):
            raise InvalidPackageSet("%s %s" % (
                set_name, "must be unicode",))

        if set_name.startswith(etpConst['packagesetprefix']):
            raise InvalidPackageSet("InvalidPackageSet: %s %s '%s'" % (
                set_name, _("cannot start with"),
                    etpConst['packagesetprefix'],))

        set_match = self.match(set_name)
        if not set_match:
            raise InvalidPackageSet(_("Already removed"))
        set_id, set_x, set_y = set_match

        if set_id != etpConst['userpackagesetsid']:
            raise InvalidPackageSet(_("Not defined by user"))
        set_file = os.path.join(SystemSettings.packages_sets_directory(),
                                set_name)

        try:
            os.remove(set_file)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise InvalidPackageSet(_("Set not found or unable to remove"))

        self._settings['system_package_sets'].pop(set_name, None)
