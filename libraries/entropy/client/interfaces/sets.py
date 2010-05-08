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
from entropy.const import etpConst, const_setup_perms, const_convert_to_unicode
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

    def available(self, match_repo = None):
        return self.match('', match_repo = match_repo, search = True)[0]

    def search(self, package_set, match_repo = None):
        # search support
        if package_set == '*':
            package_set = ''
        return self.match(package_set, match_repo = match_repo, search = True)[0]

    def match(self, package_set, multi_match = False, match_repo = None,
        search = False):

        # support match in repository from shell
        # set@repo1,repo2,repo3
        package_set, repos = entropy.tools.dep_get_match_in_repos(
            package_set)
        if (match_repo is None) and (repos is not None):
            match_repo = repos

        valid_repos = self._entropy.repositories()

        if match_repo and (type(match_repo) in (list, tuple, set)):
            valid_repos = list(match_repo)

        # if we search, we return all the matches available
        if search:
            multi_match = True

        set_data = []

        while True:

            # check inside SystemSettings
            # XXX: remove this in future
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
            return (), False

        if multi_match:
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
