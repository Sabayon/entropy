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
import os

from entropy.i18n import _
from entropy.const import etpConst, const_setup_perms
from entropy.exceptions import InvalidPackageSet
from entropy.core.settings.base import SystemSettings

import entropy.tools


class Sets:

    SET_PREFIX = etpConst['packagesetprefix']

    def __init__(self, entropy_client):
        self._entropy = entropy_client
        self._settings = SystemSettings()


    def expand(self, package_set, raise_exceptions = True):

        max_recursion_level = 50
        recursion_level = 0
        set_prefix = Sets.SET_PREFIX

        def do_expand(myset, recursion_level, max_recursion_level):
            recursion_level += 1
            if recursion_level > max_recursion_level:
                raise InvalidPackageSet(
                    'corrupted, too many recursions: %s' % (myset,))

            set_data, set_rc = self.match(myset[len(set_prefix):])
            if not set_rc:
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

    def available(self, server_repos = None, serverInstance = None,
        matchRepo = None):
        return self.match('', matchRepo = matchRepo,
            server_repos = server_repos, serverInstance = serverInstance,
            search = True)[0]

    def search(self, package_set, server_repos = None, serverInstance = None,
        matchRepo = None):
        # search support
        if package_set == '*':
            package_set = ''
        return self.match(package_set, matchRepo = matchRepo,
            server_repos = server_repos, serverInstance = serverInstance,
            search = True)[0]

    def __match_open_db(self, repoid, server_inst):
        if server_inst is not None:
            return server_inst.open_server_repository(just_reading = True,
                repo = repoid)
        return self._entropy.open_repository(repoid)

    def match(self, package_set, multiMatch = False,
        matchRepo = None, server_repos = None, serverInstance = None,
        search = False):

        # support match in repository from shell
        # set@repo1,repo2,repo3
        package_set, repos = entropy.tools.dep_get_match_in_repos(
            package_set)
        if (matchRepo is None) and (repos is not None):
            matchRepo = repos

        if server_repos is not None:
            if not serverInstance:
                raise AttributeError("server_repos needs serverInstance")
            valid_repos = server_repos[:]
        else:
            valid_repos = self._entropy.repositories()

        if matchRepo and (type(matchRepo) in (list, tuple, set)):
            valid_repos = list(matchRepo)

        # if we search, we return all the matches available
        if search:
            multiMatch = True

        set_data = []

        while True:

            # check inside SystemSettings
            if not server_repos:
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
                        if not multiMatch:
                            break

            for repoid in valid_repos:
                dbconn = self.__match_open_db(repoid,
                    serverInstance)
                if search:
                    mysets = dbconn.searchSets(package_set)
                    for myset in mysets:
                        mydata = dbconn.retrievePackageSet(myset)
                        set_data.append((repoid, myset, mydata.copy(),))
                else:
                    mydata = dbconn.retrievePackageSet(package_set)
                    if mydata:
                        set_data.append((repoid, package_set, mydata,))
                    if not multiMatch:
                        break

            break

        if not set_data:
            return (), False

        if multiMatch:
            return set_data, True

        return set_data.pop(0), True

    def add(self, set_name, set_atoms):

        def _ensure_package_sets_dir():
            sets_dir = etpConst['confsetsdir']
            if not os.path.isdir(sets_dir):
                if os.path.lexists(sets_dir):
                    os.remove(sets_dir)
                os.makedirs(sets_dir, 0o775)
                const_setup_perms(sets_dir, etpConst['entropygid'])

        try:
            set_name = str(set_name)
        except (UnicodeEncodeError, UnicodeDecodeError,):
            raise InvalidPackageSet("InvalidPackageSet: %s %s" % (
                set_name, _("must be an ASCII string"),))

        if set_name.startswith(etpConst['packagesetprefix']):
            raise InvalidPackageSet("InvalidPackageSet: %s %s '%s'" % (
                set_name, _("cannot start with"), etpConst['packagesetprefix'],))
        set_match, rc = self.match(set_name)
        if rc: return -1, _("Name already taken")

        _ensure_package_sets_dir()
        set_file = os.path.join(etpConst['confsetsdir'], set_name)
        if os.path.isfile(set_file) and os.access(set_file, os.W_OK):
            try:
                os.remove(set_file)
            except OSError:
                return -2, _("Cannot remove the old element")
        if not os.access(os.path.dirname(set_file), os.W_OK):
            return -3, _("Cannot create the element")

        f = open(set_file, "w")
        for x in set_atoms: f.write("%s\n" % (x,))
        f.flush()
        f.close()
        self._settings['system_package_sets'][set_name] = set(set_atoms)
        return 0, _("All fine")

    def remove(self, set_name):

        try:
            set_name = str(set_name)
        except (UnicodeEncodeError, UnicodeDecodeError,):
            raise InvalidPackageSet("InvalidPackageSet: %s %s" % (
                set_name, _("must be an ASCII string"),))

        if set_name.startswith(etpConst['packagesetprefix']):
            raise InvalidPackageSet("InvalidPackageSet: %s %s '%s'" % (
                set_name, _("cannot start with"),
                    etpConst['packagesetprefix'],))

        set_match, rc = self.match(set_name)
        if not rc: return -1, _("Already removed")
        set_id, set_x, set_y = set_match

        if set_id != etpConst['userpackagesetsid']:
            return -2, _("Not defined by user")
        set_file = os.path.join(etpConst['confsetsdir'], set_name)
        if os.path.isfile(set_file) and os.access(set_file, os.W_OK):
            os.remove(set_file)
            if set_name in self._settings['system_package_sets']:
                del self._settings['system_package_sets'][set_name]
            return 0, _("All fine")
        return -3, _("Set not found or unable to remove")
