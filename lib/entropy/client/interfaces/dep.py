# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Dependency handling Interface}.

"""
import os
import collections
import hashlib

from entropy.const import etpConst, const_debug_write, \
    const_isnumber, const_convert_to_rawstring, const_convert_to_unicode, \
    const_debug_enabled, const_file_readable
from entropy.exceptions import RepositoryError, SystemDatabaseError, \
    DependenciesNotFound, DependenciesNotRemovable, DependenciesCollision
from entropy.graph import Graph
from entropy.misc import Lifo
from entropy.output import bold, darkgreen, darkred, blue, purple, teal, brown
from entropy.i18n import _
from entropy.db.exceptions import IntegrityError, OperationalError, \
    DatabaseError, InterfaceError, Error as EntropyRepositoryError
from entropy.db.skel import EntropyRepositoryBase
from entropy.client.interfaces.db import InstalledPackagesRepository
from entropy.client.misc import sharedinstlock

import entropy.dep


class CalculatorsMixin:

    @sharedinstlock
    def dependencies_test(self):

        # get all the installed packages
        installed_packages = self.installed_repository().listAllPackageIds()

        pdepend_id = etpConst['dependency_type_ids']['pdepend_id']
        bdepend_id = etpConst['dependency_type_ids']['bdepend_id']
        deps_not_matched = set()
        deps_cache = set()

        total = len(installed_packages)
        for count, package_id in enumerate(installed_packages, 1):

            if (count % 150 == 0) or (count == total) or (count == 1):
                atom = self.installed_repository().retrieveAtom(package_id)
                self.output(
                    darkgreen(_("Checking %s") % (bold(atom),)),
                    importance = 0,
                    level = "info",
                    back = True,
                    count = (count, total),
                    header = darkred(" @@ ")
                )

            xdeps = self.installed_repository().retrieveDependencies(package_id,
                exclude_deptypes = (pdepend_id, bdepend_id,))

            # filter out already matched pkgs
            xdeps = [x for x in xdeps if x not in deps_cache]
            deps_cache.update(xdeps)

            needed_deps = [(x, self.installed_repository().atomMatch(x),) for \
                x in xdeps]
            deps_not_matched |= set(
                [x for x, (y, z,) in needed_deps if y == -1])

        return deps_not_matched

    def __handle_multi_repo_matches(self, results, extended_results,
        valid_repos):

        pkg_info = {}
        ver_info = {}
        # package repos have always the precedence, so if we find them,
        # we should second what user wants, installing his package
        pkg_repos = [x for x in results if x.endswith(etpConst['packagesext'])]
        if pkg_repos:
            newrepos = results.copy()
            for x in newrepos:
                if x.endswith(etpConst['packagesext']):
                    continue
                del results[x]

        version_duplicates = set()
        versions = set()
        for repo in results:
            pkg_info[repo] = {}
            if extended_results:
                version = results[repo][1]
                pkg_info[repo]['versiontag'] = results[repo][2]
                pkg_info[repo]['revision'] = results[repo][3]
            else:
                dbconn = self.open_repository(repo)
                pkg_info[repo]['versiontag'] = dbconn.retrieveTag(results[repo])
                pkg_info[repo]['revision'] = dbconn.retrieveRevision(
                    results[repo])
                version = dbconn.retrieveVersion(results[repo])
            pkg_info[repo]['version'] = version
            ver_info[version] = repo
            if version in versions:
                version_duplicates.add(version)
            versions.add(version)

        newer_ver = entropy.dep.get_newer_version(list(versions))[0]
        # if no duplicates are found or newer version is not in
        # duplicates we're done
        if (not version_duplicates) or (newer_ver not in version_duplicates):
            reponame = ver_info.get(newer_ver)
            return (results[reponame], reponame)

        # we have two repositories with >two packages with the same version
        # check package tag

        conflict_entries = {}
        tags_duplicates = set()
        tags = set()
        tagsInfo = {}
        for repo in pkg_info:
            if pkg_info[repo]['version'] != newer_ver:
                continue
            conflict_entries[repo] = {}
            versiontag = pkg_info[repo]['versiontag']
            if versiontag in tags:
                tags_duplicates.add(versiontag)
            tags.add(versiontag)
            tagsInfo[versiontag] = repo
            conflict_entries[repo]['versiontag'] = versiontag
            conflict_entries[repo]['revision'] = pkg_info[repo]['revision']

        # tags will always be != []
        newer_tag = entropy.dep.sort_entropy_package_tags(tags)[-1]
        if newer_tag not in tags_duplicates:
            reponame = tagsInfo.get(newer_tag)
            return (results[reponame], reponame)

        # in this case, we have >two packages with the same version and tag
        # check package revision

        conflictingRevisions = {}
        revisions = set()
        revisions_duplicates = set()
        revisionInfo = {}
        for repo in conflict_entries:
            if conflict_entries[repo]['versiontag'] == newer_tag:
                conflictingRevisions[repo] = {}
                versionrev = conflict_entries[repo]['revision']
                if versionrev in revisions:
                    revisions_duplicates.add(versionrev)
                revisions.add(versionrev)
                revisionInfo[versionrev] = repo
                conflictingRevisions[repo]['revision'] = versionrev

        newerRevision = max(revisions)
        if newerRevision not in revisions_duplicates:
            reponame = revisionInfo.get(newerRevision)
            return (results[reponame], reponame)

        # final step, in this case we have >two packages with
        # the same version, tag and revision
        # get the repository with the biggest priority
        for reponame in valid_repos:
            if reponame in conflictingRevisions:
                return (results[reponame], reponame)

    def atom_match(self, atom, match_slot = None, mask_filter = True,
            multi_match = False, multi_repo = False, match_repo = None,
            extended_results = False, use_cache = True):
        """
        Match one or more packages inside all the available repositories.
        """
        # support match in repository from shell
        # atom@repo1,repo2,repo3
        atom, repos = entropy.dep.dep_get_match_in_repos(atom)
        if (match_repo is None) and (repos is not None):
            match_repo = repos
        if match_repo is None:
            match_repo = tuple()

        cache_key = None
        if self.xcache and use_cache:
            sha = hashlib.sha1()

            cache_fmt = "a{%s}mr{%s}ms{%s}rh{%s}mf{%s}"
            cache_fmt += "ar{%s}m{%s}cm{%s}s{%s;%s;%s}"
            cache_s = cache_fmt % (
                atom,
                ";".join(match_repo),
                match_slot,
                self.repositories_checksum(),
                mask_filter,
                ";".join(sorted(self._settings['repositories']['available'])),
                self._settings.packages_configuration_hash(),
                self._settings_client_plugin.packages_configuration_hash(),
                multi_match,
                multi_repo,
                extended_results)
            sha.update(const_convert_to_rawstring(cache_s))

            cache_key = "atom_match/atom_match_%s" % (sha.hexdigest(),)

            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        valid_repos = self._enabled_repos
        if match_repo and (type(match_repo) in (list, tuple, set)):
            valid_repos = list(match_repo)

        repo_results = {}

        # simple "or" dependency support
        # app-foo/foo-1.2.3;app-foo/bar-1.4.3?
        if atom.endswith(etpConst['entropyordepquestion']):
            # or dependency!
            atoms = atom[:-1].split(etpConst['entropyordepsep'])
            for s_atom in atoms:
                for repo in valid_repos:
                    data, rc = self.atom_match(s_atom, match_slot = match_slot,
                        mask_filter = mask_filter, multi_match = multi_match,
                        multi_repo = multi_repo, match_repo = match_repo,
                        extended_results = extended_results,
                        use_cache = use_cache)
                    if rc != 1:
                        # checking against 1 works in any case here
                        # for simple, multi and extended match
                        return data, rc
        else:
            for repo in valid_repos:

                # search
                try:
                    dbconn = self.open_repository(repo)
                except (RepositoryError, SystemDatabaseError):
                    # ouch, repository not available or corrupted !
                    continue
                xuse_cache = use_cache

                while True:
                    try:
                        query_data, query_rc = dbconn.atomMatch(
                            atom,
                            matchSlot = match_slot,
                            maskFilter = mask_filter,
                            extendedResults = extended_results,
                            useCache = xuse_cache
                        )
                        if query_rc == 0:
                            # package found, add to our dictionary
                            if extended_results:
                                repo_results[repo] = (query_data[0],
                                    query_data[2], query_data[3],
                                    query_data[4])
                            else:
                                repo_results[repo] = query_data
                    except TypeError:
                        if not xuse_cache:
                            raise
                        xuse_cache = False
                        continue
                    except (OperationalError, DatabaseError):
                        # OperationalError => error in data format
                        # DatabaseError => database disk image is malformed
                        # repository fooked, skip!
                        break
                    break

        dbpkginfo = (-1, 1)
        if extended_results:
            dbpkginfo = ((-1, None, None, None), 1)

        if multi_repo and repo_results:

            data = set()
            for repoid in repo_results:
                data.add((repo_results[repoid], repoid))
            dbpkginfo = (data, 0)

        elif len(repo_results) == 1:
            # one result found
            repo = list(repo_results.keys())[0]
            dbpkginfo = (repo_results[repo], repo)

        elif len(repo_results) > 1:

            # we have to decide which version should be taken
            mypkginfo = self.__handle_multi_repo_matches(repo_results,
                extended_results, valid_repos)
            if mypkginfo is not None:
                dbpkginfo = mypkginfo

        # multimatch support
        if multi_match:

            if dbpkginfo[1] == 1:
                dbpkginfo = set(), 1
            else: # can be "0" or a string, but 1 means failure
                if multi_repo:
                    data = set()
                    for q_id, q_repo in dbpkginfo[0]:
                        dbconn = self.open_repository(q_repo)
                        query_data, query_rc = dbconn.atomMatch(
                            atom,
                            matchSlot = match_slot,
                            maskFilter = mask_filter,
                            multiMatch = True,
                            extendedResults = extended_results
                        )
                        if extended_results:
                            for item in query_data:
                                _item_d = (item[0], item[2], item[3], item[4])
                                data.add((_item_d, q_repo))
                        else:
                            for x in query_data:
                                data.add((x, q_repo))
                    dbpkginfo = (data, 0)
                else:
                    dbconn = self.open_repository(dbpkginfo[1])
                    query_data, query_rc = dbconn.atomMatch(
                        atom,
                        matchSlot = match_slot,
                        maskFilter = mask_filter,
                        multiMatch = True,
                        extendedResults = extended_results
                    )
                    if extended_results:
                        dbpkginfo = (
                            set([((x[0], x[2], x[3], x[4]), dbpkginfo[1]) \
                                     for x in query_data]), 0)
                    else:
                        dbpkginfo = (
                            set([(x, dbpkginfo[1]) for x in query_data]), 0)

        if cache_key is not None:
            self._cacher.push(cache_key, dbpkginfo)

        return dbpkginfo

    def atom_search(self, keyword, description = False, repositories = None,
                    use_cache = True):
        """
        Search packages inside all the available repositories, including the
        installed packages one.
        Results are returned in random order by default, and as a list of
        package matches (pkg_id_int, repo_string).

        @param keyword: string to search
        @type keyword: string
        @keyword description: if True, also search through package description
        @type description: bool
        @keyword repositories: list of repository identifiers to search
            packages into
        @type repositories: string
        @keyword use_cache: if True, on-disk caching is used
        @type use_cache: bool
        """
        if repositories is None:
            repositories = self.repositories()[:]
            repositories.insert(0, InstalledPackagesRepository.NAME)

        cache_key = None
        if self.xcache and use_cache:
            sha = hashlib.sha1()

            cache_s = "k{%s}re{%s}de{%s}rh{%s}m{%s}cm{%s}ar{%s}" % (
                keyword,
                ";".join(repositories),
                description,
                self.repositories_checksum(),
                self._settings.packages_configuration_hash(),
                self._settings_client_plugin.packages_configuration_hash(),
                ";".join(sorted(self._settings['repositories']['available'])),
                )
            sha.update(const_convert_to_rawstring(cache_s))

            cache_key = "atom_search/s_%s" % (sha.hexdigest(),)

            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        atom = keyword[:]
        match_slot = entropy.dep.dep_getslot(atom)
        if match_slot:
            atom = entropy.dep.remove_slot(atom)
        search_tag = entropy.dep.dep_gettag(atom)
        if search_tag:
            atom = entropy.dep.remove_tag(atom)

        matches = []

        for repository in repositories:

            try:
                repo = self.open_repository(repository)
            except (RepositoryError, SystemDatabaseError):
                # ouch, repository not available or corrupted !
                continue

            pkg_ids = repo.searchPackages(
                atom, slot = match_slot,
                tag = search_tag,
                just_id = True)

            matches.extend((pkg_id, repository) for pkg_id in pkg_ids)

        # less relevance
        if description:
            matches_cache = set()
            matches_cache.update(matches)

            for repository in repositories:

                try:
                    repo = self.open_repository(repository)
                except (RepositoryError, SystemDatabaseError):
                    # ouch, repository not available or corrupted !
                    continue

                pkg_ids = repo.searchDescription(keyword, just_id = True)
                pkg_matches = [(pkg_id, repository) for pkg_id in pkg_ids]
                matches.extend(pkg_match for pkg_match in pkg_matches if \
                                   pkg_match not in matches_cache)
                matches_cache.update(pkg_matches)

            matches_cache.clear()

        if cache_key is not None:
            self._cacher.push(cache_key, matches)

        return matches

    def _resolve_or_dependencies(self, dependencies, selected_matches,
                                 _selected_matches_cache = None):
        """
        Resolve a simple or dependency like "foo;bar;baz?" by looking at the
        currently installed packages and those that would be installed.
        The outcome is the selected dependency, if possible.

        @param dependencies: ordered list of or dependencies, recursion not
            supported.
        @type dependencies: list
        @param selected_matches: a list of package matches that
            compose the dependency graph.
        @type selected_matches: list
        @return: the new dependency string
        @rtype: tuple
        """
        inst_repo = self.installed_repository()
        if _selected_matches_cache is None:
            cache = {}
        else:
            cache = _selected_matches_cache

        def _generate_keyslot_cache():
            keyslot_map = {}
            keyslot_set = set()
            for package_id, repository_id in selected_matches:
                repo = self.open_repository(repository_id)
                keyslot = repo.retrieveKeySlot(package_id)
                keyslot_set.add(keyslot)

                obj = keyslot_map.setdefault(keyslot, set())
                obj.add((package_id, repository_id))
            cache['map'] = keyslot_map
            cache['set'] = keyslot_set

        selected = False
        found_matches = []
        for dep in dependencies:

            # determine if dependency has been explicitly selected
            matches, _pkg_rc = self.atom_match(
                dep, multi_match = True, multi_repo = True)
            if matches:
                found_matches.append((dep, matches))
            if const_debug_enabled():
                const_debug_write(
                    __name__,
                    "_resolve_or_dependency, "
                    "or dependency, filtering %s, got matches: %s" % (
                        dep, matches,))

        if const_debug_enabled():
            const_debug_write(
                __name__,
                "_resolve_or_dependency, "
                "filtered list: %s" % (found_matches,))

        for dep, matches in found_matches:
            common = set(matches) & selected_matches
            if common:
                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "_resolve_or_dependency, "
                        "or dependency candidate => %s, "
                        "has been explicitly selected. "
                        "Found the dependency though." % (dep,))
                dependency = dep
                selected = True
                break

            package_ids, _pkg_rc = inst_repo.atomMatch(
                dep, multiMatch = True)
            if not package_ids:
                # no matches, skip this.
                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "_resolve_or_dependency, "
                        "or dependency candidate => %s, no "
                        "installed matches, skipping for now" % (dep,))
                continue

            if const_debug_enabled():
                const_debug_write(
                    __name__,
                    "_resolve_or_dependency, "
                    "or dependency candidate => %s ?" % (
                        dep,))

            # generate cache now.
            if not cache:
                _generate_keyslot_cache()

            dep_keyslot_set = set()
            for package_id in package_ids:
                dep_keyslot_set.add(
                    inst_repo.retrieveKeySlot(package_id))
            common = cache['set'] & dep_keyslot_set

            if not common:
                # there is nothing in common between the
                # dependency and the selected matches.
                # We found it !
                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "_resolve_or_dependency, "
                        "or dependency candidate => %s, "
                        "no common keyslots between selected and this. "
                        "Found the dependency though." % (dep,))
                dependency = dep
                selected = True
                break

            if const_debug_enabled():
                const_debug_write(
                    __name__,
                    "_resolve_or_dependency, "
                    "or dependency candidate => %s, "
                    "common slots with selected matches: %s "
                    "(selected matches: %s)" % (
                        dep, common, selected_matches,))

            if common:
                common_pkg_matches = set()
                for keyslot in common:
                    common_pkg_matches.update(cache['map'][keyslot])

                # determining if the new packages are still matching
                # the selected dependency in the or literal.
                repo_matches, repo_rc = self.atom_match(
                    dep, multi_match = True, multi_repo = True)
                common = set(repo_matches) & common_pkg_matches

                if const_debug_enabled():
                    if common:
                        const_debug_write(
                            __name__,
                            "_resolve_or_dependency, "
                            "or dependency candidate => %s, "
                            "common slots with selected matches: %s "
                            "(selected matches: %s)" % (
                                dep, common, selected_matches,))
                    else:
                        const_debug_write(
                            __name__,
                            "_resolve_or_dependency, "
                            "or dependency candidate => %s, "
                            "installing %s would make the dependency "
                            "invalid." % (dep, common,))

            if not common:
                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "_resolve_or_dependency, "
                        "or dependency candidate => %s, "
                        "no common packages found. Sorry." % (
                            dep,))
                continue

            if const_debug_enabled():
                const_debug_write(
                    __name__,
                    "_resolve_or_dependency, "
                    "or dependency, selected => %s, from: %s" % (
                        dep, dependencies,))
            # found it, rewrite dependency and c_ids
            dependency = dep
            selected = True
            break

        if not selected:
            # then pick the first available in repositories, if any,
            # which is considered the default choice.
            if found_matches:
                dependency, _matches = found_matches[0]
                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "_resolve_or_dependency, "
                        "or dependency candidate => %s, will "
                        "pick this (the default one)" % (dependency,))
            else:
                dependency = dependencies[0]
                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "_resolve_or_dependency, "
                        "or dependency candidate => %s, nothing found, "
                        "will pick this (the first one)" % (dependency,))

        return dependency

    DISABLE_SLOT_INTERSECTION = os.getenv("ETP_DISABLE_SLOT_INTERSECTION")

    def _get_unsatisfied_dependencies(self, dependencies, deep_deps = False,
                                      relaxed_deps = False, depcache = None,
                                      match_repo = None):

        inst_repo = self.installed_repository()
        cl_settings = self.ClientSettings()
        misc_settings = cl_settings['misc']
        ignore_spm_downgrades = misc_settings['ignore_spm_downgrades']
        cache_key = None

        if self.xcache:
            sha = hashlib.sha1()

            cache_s = "%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|v7" % (
                ";".join(sorted(dependencies)),
                deep_deps,
                inst_repo.checksum(),
                self.repositories_checksum(),
                self._settings.packages_configuration_hash(),
                self._settings_client_plugin.packages_configuration_hash(),
                ";".join(sorted(self._settings['repositories']['available'])),
                relaxed_deps,
                ignore_spm_downgrades,
                match_repo)
            sha.update(const_convert_to_rawstring(cache_s))

            cache_key = "unsat_deps/%s" % (
                sha.hexdigest())

            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        if const_debug_enabled():
            const_debug_write(__name__,
            "_get_unsatisfied_dependencies (not cached, deep: %s) for => %s" % (
                deep_deps, dependencies,))

        etp_cmp = entropy.dep.entropy_compare_versions
        etp_get_rev = entropy.dep.dep_get_entropy_revision

        if depcache is None:
            depcache = {}

        def push_to_cache(dependency, is_unsat):
            # push to cache
            depcache[dependency] = is_unsat

        def _my_get_available_tags(dependency, installed_tags):
            available_tags = set()
            matches, t_rc = self.atom_match(dependency, multi_match = True,
                multi_repo = True, match_repo = match_repo)
            for pkg_id, repo_id in matches:
                dbconn = self.open_repository(repo_id)
                t_ver_tag = dbconn.retrieveTag(pkg_id)
                if installed_tags is None:
                    available_tags.add(t_ver_tag)
                elif t_ver_tag in installed_tags:
                    available_tags.add(t_ver_tag)
            return sorted(available_tags, reverse = True)

        def _is_matching_tag(c_ids, pkg_dep, tag):
            for c_id in c_ids:
                c_slot = inst_repo.retrieveSlot(c_id)
                # pkg_dep already contains the tag part
                a_id, a_repo_id = self.atom_match(pkg_dep,
                    match_slot = c_slot, match_repo = match_repo)
                if a_repo_id == 1:
                    continue
                return True
            return False

        unsatisfied = set()
        for dependency in dependencies:

            if dependency in depcache:
                # already analized ?
                is_unsat = depcache[dependency]
                if is_unsat:
                    unsatisfied.add(dependency)
                if const_debug_enabled():
                    const_debug_write(__name__,
                    "_get_unsatisfied_dependencies control cached for => %s" % (
                        dependency,))
                    const_debug_write(__name__, "...")
                continue

            ### conflict
            if dependency.startswith("!"):
                package_id, rc = inst_repo.atomMatch(
                    dependency[1:])
                if package_id != -1:
                    if const_debug_enabled():
                        const_debug_write(
                            __name__,
                            "_get_unsatisfied_dependencies conflict not "
                            "found on system for => %s" % (dependency,))
                        const_debug_write(__name__, "...")
                    unsatisfied.add(dependency)
                    push_to_cache(dependency, True)
                    continue

                if const_debug_enabled():
                    const_debug_write(__name__, "...")
                push_to_cache(dependency, False)
                continue

            c_ids, c_rc = inst_repo.atomMatch(dependency,
                multiMatch = True)
            if c_rc != 0:

                # check if dependency can be matched in available repos and
                # if it is a tagged package, in this case, we need to rewrite
                # the dependency string to restrict its scope
                dependency_tag = entropy.dep.dep_gettag(dependency)
                if not dependency_tag:
                    # also filter out empty tags (pkgs without tags)
                    av_tags = [x for x in \
                        _my_get_available_tags(dependency, None) if x]
                    if av_tags:
                        matching_tags = set()
                        i_key = entropy.dep.dep_getkey(dependency)
                        for a_tag in av_tags:
                            a_dep_tag = i_key + \
                                etpConst['entropytagprefix'] + a_tag
                            c_ids, c_rc = inst_repo.atomMatch(
                                a_dep_tag, multiMatch = True)
                            if c_rc != 0:
                                continue
                            if _is_matching_tag(c_ids, a_dep_tag, a_tag):
                                matching_tags.add(a_tag)

                        if matching_tags:
                            best_tag = entropy.dep.sort_entropy_package_tags(
                                matching_tags)[-1]
                            dependency += etpConst['entropytagprefix'] + \
                                best_tag

                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "_get_unsatisfied_dependencies not "
                        "satisfied on system for => %s" % (
                            dependency,))
                    const_debug_write(__name__, "...")
                unsatisfied.add(dependency)
                push_to_cache(dependency, True)
                continue

            # support for app-foo/foo-123~-1
            # -1 revision means, always pull the latest
            do_rev_deep = False
            if not deep_deps:
                string_rev = etp_get_rev(dependency)
                if string_rev == -1:
                    do_rev_deep = True

            # force_unsatisfied is another way to see "deep_deps".
            # in this case, we are going to consider valid any dep that
            # matches something in installed packages repo.
            if (not deep_deps) and (not do_rev_deep) and (relaxed_deps):
                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "_get_unsatisfied_dependencies "
                        "(force unsat) SATISFIED => %s" % (
                            dependency,))
                    const_debug_write(__name__, "...")
                push_to_cache(dependency, False)
                continue

            # WARN: unfortunately, need to deal with Portage (and other
            # backends) old-style PROVIDE metadata
            if entropy.dep.dep_getcat(dependency) == \
                EntropyRepositoryBase.VIRTUAL_META_PACKAGE_CATEGORY:
                provide_stop = False
                for c_id in c_ids:
                    # optimize speed with a trick
                    _provide = dict(
                        inst_repo.retrieveProvide(c_id))
                    if dependency in _provide:
                        if const_debug_enabled():
                            const_debug_write(
                                __name__,
                                "_get_unsatisfied_dependencies old-style "
                                "provide, satisfied => %s" % (
                                    dependency,))
                            const_debug_write(__name__, "...")
                        push_to_cache(dependency, False)
                        provide_stop = True
                        break
                if provide_stop:
                    continue

            r_id, r_repo = self.atom_match(dependency, match_repo = match_repo)
            if r_id == -1:
                if const_debug_enabled():
                    const_debug_write(__name__,
                    "_get_unsatisfied_dependencies repository match "
                    "not found for => %s, CONSIDER SATISFIED !" % (dependency,))
                    const_debug_write(__name__, "...")
                push_to_cache(dependency, False)
                continue

            # Slot intersection support:
            # certain dependency strings could have
            # cross-SLOT scope (multiple slots for same package are valid)
            # causing unwanted dependencies to be pulled in.
            # For example: if dependency is "dev-lang/python"
            # and we have dev-lang/python-2 installed, python-3
            # should be filtered out (if possible) by checking if
            # the installed best dependency match slot is still
            # available in repositories.
            # If it is, restrict the dependency scope to the intersection
            # between available SLOTs and installed SLOT.
            multi_repo = False
            if match_repo is None:
                multi_repo = True

            available_slots = set()
            if not self.DISABLE_SLOT_INTERSECTION:
                r_matches, r_rcs = self.atom_match(
                    dependency, match_repo = match_repo,
                    multi_match = True, multi_repo = multi_repo)
                available_slots |= set(self.open_repository(x[1]).retrieveSlot(
                        x[0]) for x in r_matches)
            if len(available_slots) > 1:
                # more than one slot available
                # pick the best one by calling atomMatch() without multiMatch
                c_id, c_rc = inst_repo.atomMatch(
                    dependency)
                installed_slot = None
                if c_id != -1:
                    installed_slot = inst_repo.retrieveSlot(
                            c_id)
                if installed_slot in available_slots:
                    # restrict my matching to installed_slot, rewrite
                    # r_id r_repo
                    # NOTE: assume that dependency has no tag nor etp rev
                    # also, if we got multiple slots, it means that the
                    # same dep is expressed without slot.
                    old_r_id = r_id
                    old_r_repo = r_repo
                    r_id, r_repo = self.atom_match(
                        dependency, match_slot = installed_slot)
                    if r_id != -1:
                        # append slot to dependency
                        dependency += etpConst['entropyslotprefix'] \
                            + installed_slot

                    if const_debug_enabled():
                        from_atom = self.open_repository(
                            old_r_repo).retrieveAtom(old_r_id)
                        to_atom = self.open_repository(
                            r_repo).retrieveAtom(r_id)
                        const_debug_write(
                            __name__,
                            "_get_unsatisfied_dependencies "
                            " SLOT intersection: installed: "
                            "%s, available: %s, from: %s [%s], to: %s [%s]" % (
                                installed_slot, available_slots,
                                (old_r_id, old_r_repo),
                                from_atom, (r_id, r_repo),
                                to_atom,))

            dbconn = self.open_repository(r_repo)
            try:
                repo_pkgver, repo_pkgtag, repo_pkgrev = \
                    dbconn.getVersioningData(r_id)
                # note: read rationale below
                repo_digest = dbconn.retrieveDigest(r_id)
            except (InterfaceError, TypeError,):
                # package entry is broken
                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "_get_unsatisfied_dependencies repository "
                        "entry broken for match => %s" % (
                            (r_id, r_repo),))
                    const_debug_write(__name__, "...")
                unsatisfied.add(dependency)
                push_to_cache(dependency, True)
                continue

            client_data = set()
            for c_id in c_ids:
                try:
                    installed_ver, installed_tag, installed_rev = \
                        inst_repo.getVersioningData(c_id)
                    # note: read rationale below
                    installed_digest = inst_repo.retrieveDigest(
                        c_id)
                except TypeError: # corrupted entry?
                    installed_ver = "0"
                    installed_tag = ''
                    installed_rev = 0
                    installed_digest = None
                client_data.add((installed_ver, installed_tag, installed_rev,
                    installed_digest,))

            # restrict dependency matching scope inside mutually available
            # package tags. Equals to tags available in both installed and
            # available repositories.
            dependency_tag = entropy.dep.dep_gettag(dependency)
            installed_tags = [x[1] for x in client_data if x[1]]
            if installed_tags and not dependency_tag:

                installed_tags = set(installed_tags)
                available_tags = _my_get_available_tags(dependency,
                    installed_tags)

                if available_tags:
                    # always take the higher tag.
                    # NOW, reset variables used here below to make them
                    # pointing to proper tagged package, keeping scoped
                    # handling.
                    best_tag = entropy.dep.sort_entropy_package_tags(
                        available_tags)[-1]

                    # also change "dependency" to make it pointing to a
                    # stricter set of possible matches.
                    dependency = dependency + \
                        etpConst['entropytagprefix'] + best_tag
                    r_id, r_repo = self.atom_match(dependency,
                        match_repo = match_repo)
                    dbconn = self.open_repository(r_repo)
                    repo_pkgver, repo_pkgtag, repo_pkgrev = \
                        dbconn.getVersioningData(r_id)
                    repo_digest = dbconn.retrieveDigest(r_id)

            # this is required for multi-slotted packages (like python)
            # and when people mix Entropy and Portage
            do_cont = False
            for installed_ver, installed_tag, installed_rev, cdigest in client_data:

                vcmp = etp_cmp((repo_pkgver, repo_pkgtag, repo_pkgrev,),
                    (installed_ver, installed_tag, installed_rev,))

                # check if both pkgs share the same branch and digest, this must
                # be done to avoid system inconsistencies across branch upgrades
                if vcmp == 0:
                    # cdigest == "0" if repo has been manually (user-side)
                    # generated
                    if (cdigest != repo_digest) and (cdigest != "0"):
                        vcmp = 1

                # check against SPM downgrades and ignore_spm_downgrades
                if (vcmp < 0) and ignore_spm_downgrades and \
                    (installed_rev == etpConst['spmetprev']) \
                    and (installed_rev != repo_pkgrev):
                    # In this case, do not override Source Package Manager
                    # installed pkgs
                    if const_debug_enabled():
                        const_debug_write(__name__,
                        "_get_unsatisfied_dependencies => SPM downgrade! " + \
                            "(not cached, deep: %s) => %s" % (
                                deep_deps, dependency,))
                    vcmp = 0

                if vcmp == 0:
                    if const_debug_enabled():
                        const_debug_write(__name__,
                        "_get_unsatisfied_dependencies SATISFIED equals " + \
                            "(not cached, deep: %s) => %s" % (
                                deep_deps, dependency,))
                        const_debug_write(__name__, "...")
                    do_cont = True
                    push_to_cache(dependency, False)
                    break

                ver_tag_repo = (repo_pkgver, repo_pkgtag,)
                ver_tag_inst = (installed_ver, installed_tag,)
                rev_match = repo_pkgrev != installed_rev

                if do_rev_deep and rev_match and (ver_tag_repo == ver_tag_inst):
                    # this is unsatisfied then, need to continue to exit from
                    # for cycle and add it to unsatisfied
                    continue

                if deep_deps:
                    # also this is clearly unsatisfied if deep is enabled
                    continue

                if (ver_tag_repo == ver_tag_inst) and rev_match:
                    if const_debug_enabled():
                        const_debug_write(__name__,
                        "_get_unsatisfied_dependencies SATISFIED " + \
                            "w/o rev (not cached, deep: %s) => %s" % (
                                deep_deps, dependency,))
                        const_debug_write(__name__, "...")
                    do_cont = True
                    push_to_cache(dependency, False)
                    break

            if do_cont:
                continue

            # if we get here it means that there are no matching packages
            if const_debug_enabled():
                const_debug_write(
                    __name__,
                    "_get_unsatisfied_dependencies NOT SATISFIED "
                    "(not cached, deep: %s) => %s" % (
                        deep_deps, dependency,))
                const_debug_write(__name__, "...")

            unsatisfied.add(dependency)
            push_to_cache(dependency, True)

        if self.xcache:
            self._cacher.push(cache_key, unsatisfied)

        return unsatisfied

    def packages_expand(self, packages):
        """
        Given a list of user requested packages, expands it resolving for
        instance, items such as package sets.

        @param packages: list of user requested packages
        @type packages: list
        @return: expanded list
        @rtype: list
        """
        new_packages = []
        sets = self.Sets()

        set_pfx = etpConst['packagesetprefix']
        for pkg_id in range(len(packages)):
            package = packages[pkg_id]

            # expand package sets
            if package.startswith(set_pfx):
                cur_sets = sets.expand(package, raise_exceptions = False)
                set_pkgs = sorted(cur_sets)
                new_packages.extend([x for x in set_pkgs if x not in packages])
            else:
                new_packages.append(package)

        return new_packages

    def __generate_dependency_tree_inst_hooks(self, installed_match,
                                              pkg_match, build_deps,
                                              elements_cache,
                                              ldpaths):

        if const_debug_enabled():
            inst_atom = self.installed_repository().retrieveAtom(
                installed_match[0])
            atom = self.open_repository(pkg_match[1]
                ).retrieveAtom(pkg_match[0])
            const_debug_write(__name__,
                "__generate_dependency_tree_inst_hooks "
                "input: installed %s, avail %s" % (inst_atom, atom,))

        # these are inverse dependencies
        broken_children_matches = self._lookup_library_drops(pkg_match,
            installed_match[0])
        if const_debug_enabled():
            const_debug_write(__name__,
            "__generate_dependency_tree_inst_hooks "
            "_lookup_library_drops, broken_children_matches => %s" % (
                broken_children_matches,))

        after_pkgs, before_pkgs = self._lookup_library_breakages(
            pkg_match, installed_match[0], ldpaths)
        if const_debug_enabled():
            const_debug_write(__name__,
                "__generate_dependency_tree_inst_hooks "
                "_lookup_library_breakages, "
                "after => %s, before => %s" % (
                    after_pkgs, before_pkgs,))

        inverse_deps = self._lookup_inverse_dependencies(pkg_match,
            installed_match[0], build_deps, elements_cache)
        if const_debug_enabled():
            const_debug_write(__name__,
            "__generate_dependency_tree_inst_hooks "
            "_lookup_inverse_dependencies, inverse_deps => %s" % (
                inverse_deps,))

        return broken_children_matches, after_pkgs, before_pkgs, inverse_deps

    def __generate_dependency_tree_analyze_conflict(self, pkg_match,
        conflict_str, conflicts, stack, graph, deep_deps):

        conflict_atom = conflict_str[1:]
        c_package_id, xst = self.installed_repository().atomMatch(conflict_atom)
        if c_package_id == -1:
            return # conflicting pkg is not installed

        confl_replacement = self._lookup_conflict_replacement(
            conflict_atom, c_package_id, deep_deps = deep_deps)

        if const_debug_enabled():
            const_debug_write(__name__,
                "__generate_dependency_tree_analyze_conflict "
                "replacement => %s" % (confl_replacement,))

        if confl_replacement is not None:
            graph.add(pkg_match, set([confl_replacement]))
            stack.push(confl_replacement)
            return

        # conflict is installed, we need to record it
        conflicts.add(c_package_id)

    def __generate_dependency_tree_resolve_conditional(self, unsatisfied_deps,
        selected_matches, selected_matches_cache):

        # expand list of package dependencies evaluating conditionals
        unsatisfied_deps = entropy.dep.expand_dependencies(unsatisfied_deps,
            [self.open_repository(repo_id) for repo_id in self._enabled_repos],
            selected_matches = selected_matches)

        def _simple_or_dep_map(dependency):
            # simple or dependency format support.
            if dependency.endswith(etpConst['entropyordepquestion']):
                deps = dependency[:-1].split(etpConst['entropyordepsep'])
                return self._resolve_or_dependencies(
                    deps, selected_matches,
                    _selected_matches_cache=selected_matches_cache)
            return dependency

        return set(map(_simple_or_dep_map, unsatisfied_deps))

    DISABLE_REWRITE_SELECTED_MATCHES = os.getenv(
        "ETP_DISABLE_REWRITE_SELECTED_MATCHES")

    def __rewrite_selected_matches(self, unsatisfied_deps, selected_matches):
        """
        This function scans the unsatisfied dependencies and tries to rewrite
        them if they are in the "selected_matches" set. This set contains the
        unordered list of package matches requested by the user. We should
        respect them as much as we can.

        See Sabayon bug #4475. This is a fixup code and hopefully runs in
        O(len(unsatisfied_deps)) thanks to memoization.
        """
        if (not selected_matches) or self.DISABLE_REWRITE_SELECTED_MATCHES:
            return unsatisfied_deps

        def _in_selected_matches(dep):
            matches, m_rc = self.atom_match(
                dep, multi_match = True, multi_repo = True)
            common = selected_matches & matches
            if common:
                # we deterministically pick the first entry
                # because the other ones will be pulled in anyway.
                for package_id, repository_id in sorted(common):
                    repo = self.open_repository(repository_id)
                    keyslot = repo.retrieveKeySlotAggregated(package_id)
                    if keyslot is None:
                        continue

                    const_debug_write(
                        __name__,
                        "__rewrite_selected_matches, rewritten: "
                        "%s to %s" % (dep, keyslot,))
                    return keyslot
            return dep

        return set(map(_in_selected_matches, unsatisfied_deps))

    DISABLE_AUTOCONFLICT = os.getenv("ETP_DISABLE_AUTOCONFLICT")

    def __generate_dependency_tree_analyze_deplist(self, pkg_match, repo_db,
        stack, graph, deps_not_found, conflicts, unsat_cache, relaxed_deps,
        build_deps, deep_deps, empty_deps, recursive, selected_matches,
        elements_cache, selected_matches_cache):

        pkg_id, repo_id = pkg_match
        # exclude build dependencies
        excluded_deptypes = [etpConst['dependency_type_ids']['pdepend_id']]
        if not build_deps:
            excluded_deptypes += [etpConst['dependency_type_ids']['bdepend_id']]

        myundeps = repo_db.retrieveDependenciesList(pkg_id,
            exclude_deptypes = excluded_deptypes,
            resolve_conditional_deps = False)

        # this solves some conditional dependencies using selected_matches.
        # also expands all the conditional dependencies using
        # entropy.dep.expand_dependencies()
        if const_debug_enabled():
            atom = repo_db.retrieveAtom(pkg_id)
            const_debug_write(__name__,
                "__generate_dependency_tree_analyze_deplist conditionals "
                "%s, %s, current dependency list => %s" % (
                    pkg_match, atom, myundeps,))
        myundeps = self.__generate_dependency_tree_resolve_conditional(
            myundeps, selected_matches, selected_matches_cache)
        if const_debug_enabled():
            const_debug_write(__name__,
                "__generate_dependency_tree_analyze_deplist conditionals, "
                "new dependency list => %s" % (myundeps,))

        my_conflicts = set([x for x in myundeps if x.startswith("!")])

        auto_conflicts = self._generate_dependency_inverse_conflicts(
            pkg_match)
        my_conflicts |= auto_conflicts

        # check conflicts
        if my_conflicts:
            myundeps -= my_conflicts
            for my_conflict in my_conflicts:
                self.__generate_dependency_tree_analyze_conflict(
                    pkg_match, my_conflict,
                    conflicts, stack, graph, deep_deps)

        if const_debug_enabled():
            const_debug_write(__name__,
                "__generate_dependency_tree_analyze_deplist filtered "
                "dependency list => %s" % (myundeps,))

        if not empty_deps:

            myundeps = self._get_unsatisfied_dependencies(myundeps,
                deep_deps = deep_deps, relaxed_deps = relaxed_deps,
                depcache = unsat_cache)
            myundeps = self.__rewrite_selected_matches(
                myundeps, selected_matches)

            if const_debug_enabled():
                const_debug_write(__name__,
                    "__generate_dependency_tree_analyze_deplist " + \
                        "filtered UNSATISFIED dependencies => %s" % (myundeps,))

        def _post_deps_filter(post_dep):
            pkg_matches, rc = self.atom_match(post_dep,
                multi_match = True, multi_repo = True)
            commons = pkg_matches & elements_cache
            if commons:
                return False
            return True

        post_deps = []
        # PDEPENDs support
        myundeps, post_deps = self._lookup_post_dependencies(repo_db,
            pkg_id, myundeps)
        if (not empty_deps) and post_deps:
            # validate post dependencies, make them not contain matches already
            # pulled in, this cuts potential circular dependencies:
            # nvidia-drivers pulls in nvidia-userspace which has nvidia-drivers
            # listed as post-dependency
            post_deps = list(filter(_post_deps_filter, post_deps))
            post_deps = self.__generate_dependency_tree_resolve_conditional(
                post_deps, selected_matches, selected_matches_cache)
            post_deps = self._get_unsatisfied_dependencies(post_deps,
                deep_deps = deep_deps, relaxed_deps = relaxed_deps,
                depcache = unsat_cache)

        if const_debug_enabled():
            const_debug_write(__name__,
                "generate_dependency_tree POST dependencies ADDED => %s" % (
                    post_deps,))

        deps = set()
        for unsat_dep in myundeps:
            match_pkg_id, match_repo_id = self.atom_match(unsat_dep)
            if match_pkg_id == -1:
                # dependency not found !
                deps_not_found.add(unsat_dep)
                continue

            deps.add((match_pkg_id, match_repo_id))
            if recursive:
                # push to stack only if recursive
                stack.push((match_pkg_id, match_repo_id))

        post_deps_matches = set()
        for post_dep in post_deps:
            match_pkg_id, match_repo_id = self.atom_match(post_dep)
            # if post dependency is not found, we can happily ignore the fact
            if match_pkg_id == -1:
                # not adding to deps_not_found
                continue
            post_deps_matches.add((match_pkg_id, match_repo_id))
            if recursive:
                # push to stack only if recursive
                stack.push((match_pkg_id, match_repo_id))

        return deps, post_deps_matches

    def _generate_dependency_inverse_conflicts(self, package_match,
                                               just_id = False):
        """
        Given a package match, generate a list of conflicts by looking
        at the installed packages repository and its "!<dep>" dependency
        strings. This is useful because sometimes, packages miss conflict
        information on both sides. A hates B, but B doesn't say anything about
        A, A is the installed package.

        @param package_match: an Entropy package match
        @type package_match: tuple
        @keyword just_id: if True, return installed package ids instead of
          conflict dependency strings
        @type just_id: bool
        @return: a list (set) of conflicts
        @rtype: set
        """
        conflicts = set()
        # XXX Experimental feature, make possible to override it XXX
        if self.DISABLE_AUTOCONFLICT is not None:
            return conflicts

        pkg_id, repository_id = package_match
        repo_db = self.open_repository(repository_id)

        pkg_key = entropy.dep.dep_getkey(repo_db.retrieveAtom(pkg_id))
        potential_conflicts = self.installed_repository().searchConflict(
            pkg_key)

        for dep_package_id, conflict_str in potential_conflicts:
            confl_pkg_ids, confl_pkg_rc = repo_db.atomMatch(
                conflict_str, multiMatch = True)

            # is this really me? ignore the rc, just go straight to ids
            if pkg_id not in confl_pkg_ids:
                continue

            if just_id:
                conflicts.add(dep_package_id)
                break
            else:
                # yes, this is really me!
                dep_key_slot = self.installed_repository().retrieveKeySlot(
                    dep_package_id)
                if dep_key_slot is not None:
                    dep_key, dep_slot = dep_key_slot
                    dep_confl_str = "!%s%s%s" % (dep_key,
                        etpConst['entropyslotprefix'], dep_slot)
                    conflicts.add(dep_confl_str)
                    if const_debug_enabled():
                        const_debug_write(__name__,
                        "_generate_dependency_inverse_conflict "
                        "adding auto-conflict => %s, conflict_str was: %s" % (
                            dep_confl_str, conflict_str,))
                    break

        return conflicts

    def _generate_dependency_tree(self, matched_atom, graph,
        empty_deps = False, relaxed_deps = False, build_deps = False,
        only_deps = False, deep_deps = False, unsatisfied_deps_cache = None,
        elements_cache = None, post_deps_cache = None, recursive = True,
        selected_matches = None, selected_matches_cache = None, ldpaths = None):

        pkg_id, pkg_repo = matched_atom
        if (pkg_id == -1) or (pkg_repo == 1):
            raise AttributeError("invalid matched_atom: %s" % (matched_atom,))

        # this cache avoids adding the same element to graph
        # several times, when it is supposed to be already handled
        if elements_cache is None:
            elements_cache = set()
        if unsatisfied_deps_cache is None:
            unsatisfied_deps_cache = {}
        if post_deps_cache is None:
            post_deps_cache = {}

        if selected_matches is None:
            selected_matches = set()

        if ldpaths is None:
            ldpaths = frozenset()

        deps_not_found = set()
        conflicts = set()
        first_element = True

        stack = Lifo()
        stack.push(matched_atom)
        inverse_dep_stack_cache = {}
        graph_cache = set()

        while stack.is_filled():

            # get item from stack
            pkg_id, repo_id = stack.pop()
            pkg_match = (pkg_id, repo_id)

            if pkg_match in elements_cache:
                # already pushed to graph
                continue
            elements_cache.add(pkg_match)

            # now we are ready to open repository
            repo_db = self.open_repository(repo_id)

            ## first element checks
            add_to_graph = True
            if first_element:
                first_element = False

                if only_deps:
                    # in this case, we only add pkg_match to
                    # the graph if it's a dependency of something else
                    # also, with only_deps we should ignore if pkg is masked
                    add_to_graph = False
                else:
                    # we need to check if first element is masked because of
                    # course, we don't trust function caller.
                    mask_pkg_id, idreason = repo_db.maskFilter(pkg_id)
                    if mask_pkg_id == -1:
                        mask_atom = repo_db.retrieveAtom(pkg_id)
                        if mask_atom is None:
                            mask_atom = 'N/A' # wtf?
                        deps_not_found.add(mask_atom)
                        continue # back to while

            # search inside installed packages repository if there's something
            # in the same slot, if so, do some extra checks first.
            try:
                pkg_key, pkg_slot = repo_db.retrieveKeySlot(pkg_id)
            except TypeError:
                deps_not_found.add("unknown_%s_%s" % (pkg_id, repo_id,))
                continue
            cm_package_id, cm_result = self.installed_repository().atomMatch(
                pkg_key, matchSlot = pkg_slot)

            if cm_package_id != -1:
                # this method does:
                # - broken libraries detection
                # - inverse dependencies check
                children_matches, after_pkgs, before_pkgs, inverse_deps = \
                    self.__generate_dependency_tree_inst_hooks(
                        (cm_package_id, cm_result), pkg_match,
                        build_deps, elements_cache, ldpaths)
                # this is fine this way, these are strong inverse deps
                # and their order is already written in stone
                for inv_match in inverse_deps:
                    stack.push(inv_match)
                # children_matches are always inverse dependencies, and
                # must be stated as such, once they eventually end into
                # the graph (see below)
                for child_match in children_matches:
                    obj = inverse_dep_stack_cache.setdefault(child_match, set())
                    obj.add(pkg_match)
                    stack.push(child_match)

                # these are misc and cannot be differentiated
                for br_match in after_pkgs: # don't care about the position
                    if br_match in children_matches:
                        # already pushed and inverse dep
                        continue
                    stack.push(br_match)
                for br_match in before_pkgs:
                    # enforce dependency explicitly?
                    if br_match in children_matches:
                        # already pushed and inverse dep
                        continue
                    stack.push(br_match)
                if before_pkgs:
                    graph.add(pkg_match, before_pkgs)

            dep_matches, post_dep_matches = \
                self.__generate_dependency_tree_analyze_deplist(
                    pkg_match, repo_db, stack, graph, deps_not_found,
                    conflicts, unsatisfied_deps_cache, relaxed_deps,
                    build_deps, deep_deps, empty_deps, recursive,
                    selected_matches, elements_cache, selected_matches_cache)

            if post_dep_matches:
                obj = post_deps_cache.setdefault(pkg_match, set())
                obj.update(post_dep_matches)

            # eventually add our package match to depgraph
            if add_to_graph:
                graph.add(pkg_match, dep_matches)
            graph_cache.add(pkg_match)
            pkg_match_set = set([pkg_match])
            for post_dep_match in post_dep_matches:
                graph.add(post_dep_match, pkg_match_set)

        # add cached "inverse of inverse (==direct)" deps, if available
        for pkg_match in graph_cache:
            inv_deps = inverse_dep_stack_cache.get(pkg_match)
            if inv_deps:
                graph.add(pkg_match, inv_deps)
                if const_debug_enabled():
                    atom = self.open_repository(pkg_match[1]).retrieveAtom(
                        pkg_match[0])
                    wanted_deps = [self.open_repository(y).retrieveAtom(x) \
                        for x, y in inv_deps]
                    const_debug_write(__name__,
                    "_generate_dependency_tree(revdep cache) %s wants %s" % (
                        purple(atom), blue(" ".join(wanted_deps)),))

        graph_cache.clear()
        inverse_dep_stack_cache.clear()
        # if deps not found, we won't do dep-sorting at all
        if deps_not_found:
            #del stack
            raise DependenciesNotFound(deps_not_found)

        return graph, conflicts

    def _lookup_post_dependencies(self, repo_db, repo_package_id,
        unsatisfied_deps):

        post_deps = repo_db.retrievePostDependencies(repo_package_id)

        if const_debug_enabled():
            const_debug_write(__name__,
                "_lookup_post_dependencies POST dependencies for %s => %s" % (
                    (repo_package_id, repo_db.repository_id()), post_deps,))

        if post_deps:

            # do some filtering
            # it is correct to not use my_dep_filter here
            unsatisfied_deps = [x for x in unsatisfied_deps \
                if x not in post_deps]

        return unsatisfied_deps, post_deps


    def _lookup_system_mask_repository_deps(self):

        client_settings = self.ClientSettings()
        data = client_settings['repositories']['system_mask']

        if not data:
            return []
        mydata = []
        cached_items = set()
        for atom in data:
            mymatch = self.atom_match(atom)
            if mymatch[0] == -1: # ignore missing ones intentionally
                continue
            if mymatch in cached_items:
                continue
            if mymatch not in mydata:
                # check if not found
                myaction = self._get_package_action(mymatch)
                # only if the package is not installed
                if myaction == 1:
                    mydata.append(mymatch)
            cached_items.add(mymatch)
        return mydata

    def _lookup_conflict_replacement(self, conflict_atom, client_package_id,
        deep_deps):

        if entropy.dep.isjustname(conflict_atom):
            return

        conflict_match = self.atom_match(conflict_atom)
        mykey, myslot = self.installed_repository().retrieveKeySlot(
            client_package_id)
        new_match = self.atom_match(mykey, match_slot = myslot)
        if (conflict_match == new_match) or (new_match[1] == 1):
            return

        action = self._get_package_action(
            new_match, installed_package_id = client_package_id)
        if (action == 0) and (not deep_deps):
            return

        return new_match

    def _lookup_inverse_dependencies(self, match, installed_package_id,
                                     build_deps, elements_cache):
        """
        Lookup inverse dependencies and return them as a list of package
        matches.
        """
        cmpstat = self._get_package_action(
            match, installed_package_id = installed_package_id)
        if cmpstat == 0:
            return set()

        keyslots_cache = set()
        match_cache = {}
        results = set()
        inst_repo = self.installed_repository()

        excluded_dep_types = (
            etpConst['dependency_type_ids']['bdepend_id'],)
        if build_deps:
            excluded_dep_types = None

        reverse_deps = inst_repo.retrieveReverseDependencies(
            installed_package_id, exclude_deptypes = excluded_dep_types)

        for inst_package_id in reverse_deps:

            key_slot = inst_repo.retrieveKeySlotAggregated(
                inst_package_id)
            if key_slot is None:
                continue
            if key_slot in keyslots_cache:
                continue

            keyslots_cache.add(key_slot)

            # grab its deps
            mydeps = inst_repo.retrieveDependencies(
                inst_package_id, exclude_deptypes = excluded_dep_types)
            found = False

            for mydep in mydeps:
                mymatch = match_cache.get(mydep, 0)
                if mymatch == 0:
                    mymatch = self.atom_match(mydep)
                    match_cache[mydep] = mymatch
                if mymatch == match:
                    found = True
                    break

            if not found:
                mymatch = self.atom_match(key_slot)
                if mymatch[0] == -1:
                    continue
                cmpstat = self._get_package_action(
                    mymatch, installed_package_id = inst_package_id)
                if cmpstat == 0:
                    continue

                # this will take a life, also check if we haven't already
                # pulled this match in.
                # This happens because the reverse dependency string is
                # too much generic and could pull in conflicting packages.
                # NOTE: this is a hack and real weighted graph
                # would be required
                mymatches, rc = self.atom_match(
                    key_slot, multi_match = True,
                    multi_repo = True)
                got_it = mymatches & elements_cache
                if got_it:
                    if const_debug_enabled():
                        atom = self.open_repository(
                            mymatch[1]).retrieveAtom(mymatch[0])
                        const_debug_write(__name__,
                        "_lookup_inverse_dependencies, ignoring "
                        "%s, %s -- because already pulled in as: %s" % (
                            atom, mymatch, got_it,))
                    # yeah, pulled in, ignore
                    continue

                if const_debug_enabled():
                    atom = self.open_repository(mymatch[1]).retrieveAtom(
                        mymatch[0])
                    const_debug_write(__name__,
                    "_lookup_inverse_dependencies, "
                    "adding inverse dep => %s" % (atom,))
                results.add(mymatch)

        return results

    def _lookup_library_drops(self, match, installed_package_id):
        """
        Look for packages that would break if package match
        at "match" would be installed and the current version
        at "installed_package_id" replaced.
        This method looks at what a package provides in terms of
        libraries.

        @param match: the package match that would be installed
        @type match: tuple
        @param installed_package_id: the installed package identifier
          that would be replaced
        @type installed_package_id: int
        @return: package matches that should be updated as well
        @rtype: set
        """
        match_package_id, match_repo_id = match

        inst_repo = self.installed_repository()
        match_repo = self.open_repository(match_repo_id)
        repo_libs = match_repo.retrieveProvidedLibraries(match_package_id)

        # compute a list of sonames that are going to be dropped
        client_libs = inst_repo.retrieveProvidedLibraries(
            installed_package_id)
        removed_libs = [x for x in client_libs if x not in repo_libs]

        if not removed_libs:
            if const_debug_enabled():
                inst_atom = inst_repo.retrieveAtom(installed_package_id)
                atom = match_repo.retrieveAtom(match_package_id)
                const_debug_write(
                    __name__,
                    "_lookup_library_drops, "
                    "no libraries would be removed for: "
                    "[%s] and [%s] (%s -> %s)" % (
                        match, installed_package_id,
                        atom, inst_atom))
            return set()

        # look for installed packages needing these to-be-dropped
        # sonames
        inst_package_ids = set()
        for lib, path, elf in removed_libs:
            inst_package_ids |= inst_repo.searchNeeded(lib,
                elfclass = elf)
        if not inst_package_ids:
            return set()

        # this is used to filter out "match" from broken_matches
        # in the for loop below
        match_keyslot = None

        broken_matches = set()
        for inst_package_id in inst_package_ids:

            # is this package available in repos?
            # maybe it's been dropped upstream...
            keyslot = inst_repo.retrieveKeySlotAggregated(
                inst_package_id)
            if keyslot is None:
                continue
            package_id, repository_id = self.atom_match(keyslot)
            if package_id == -1:
                continue

            # do we already have the latest version installed?
            cmpstat = self._get_package_action(
                (package_id, repository_id),
                installed_package_id = inst_package_id)
            if cmpstat == 0:
                const_debug_write(
                    __name__,
                    "_lookup_library_drops, "
                    "a package would break but no updates are available. "
                    "(%s, %s)" % (keyslot, match,))
                continue

            # not against myself. it can happen...
            # this is faster than key+slot lookup
            if (package_id, repository_id) == match:
                const_debug_write(
                    __name__,
                    "_lookup_library_drops, not adding myself. "
                    "match %s is the same." % (match,))
                continue

            # not against the same key+slot
            if match_keyslot is None:
                match_keyslot = match_repo.retrieveKeySlotAggregated(
                    match_repo_id)
                # assuming that a repeatedly None value does not hurt
            if keyslot == match_keyslot:
                const_debug_write(
                    __name__,
                    "_lookup_library_drops, not adding myself. "
                    "keyslot %s is the same for %s and %s" % (
                        keyslot, match,
                        (package_id, repository_id),)
                    )
                continue

            if const_debug_enabled():
                atom = self.open_repository(repository_id).retrieveAtom(
                    package_id)
                const_debug_write(__name__,
                "_lookup_library_drops, "
                "adding broken library link package => %s, pulling: %s" % (
                    keyslot, atom,))

            broken_matches.add((package_id, repository_id))

        if const_debug_enabled() and broken_matches:
            const_debug_write(__name__,
            "_lookup_library_drops, "
            "total removed libs for iteration: %s" % (removed_libs,))

        return broken_matches

    def __get_library_breakages(self, package_match, installed_package_id):
        """
        Get a list of library dependencies (at ELF metadata level)
        that have been bumped for the given package.
        The newly added ones, are considered a bump. In this way, whether
        they are already present in the package dependencies or not, a
        proper relation will be inserted on the dependency graph.
        It can happen that a library may be considered satisfied
        as package dependency but not on the current system state.
        """
        package_id, repository_id = package_match
        inst_repo = self.installed_repository()
        repo = self.open_repository(repository_id)

        # Ignore user library path and user library soname, not relevant.
        repo_needed = {
            (soname, elf, rpath) for _usr_path, _usr_soname, soname, elf, rpath
            in repo.retrieveNeededLibraries(package_id)}
        installed_needed = {
            (soname, elf, rpath) for _usr_path, _usr_soname, soname, elf, rpath
            in inst_repo.retrieveNeededLibraries(installed_package_id)}

        # intersect the two dicts and find the libraries that
        # have not changed. We assume that a pkg cannot link
        # the same SONAME with two different elf classes.
        # but that is what retrieveNeededLibraries() assumes as well
        common_libs = repo_needed & installed_needed
        for lib_data in common_libs:
            repo_needed.discard(lib_data)
            installed_needed.discard(lib_data)

        soname_ext = const_convert_to_unicode(".so")
        # x[0] is soname.
        repo_split = {x: tuple(x[0].split(soname_ext)) for x in repo_needed}
        installed_split = {
            x: tuple(x[0].split(soname_ext)) for x in installed_needed}

        inst_lib_dumps = set() # was installed_side
        repo_lib_dumps = set() # was repo_side
        # ^^ library dumps using repository NEEDED metadata

        for lib_data, lib_name in installed_split.items():
            lib, elfclass, rpath = lib_data
            if lib_name in repo_split.values():
                # (library name, elf class)
                inst_lib_dumps.add((lib, elfclass, rpath))

        for lib_data, lib_name in repo_split.items():
            lib, elfclass, rpath = lib_data
            if lib_name in installed_split.values():
                repo_lib_dumps.add((lib, elfclass, rpath))

        # now consider the case in where we have new libraries
        # that are not in the installed libraries set.
        new_libraries = set(repo_split.values()) - set(installed_split.values())
        if new_libraries:

            # Reverse repo_split in order to generate a mapping
            # between a library name and its set of full libraries
            reversed_repo_split = {}
            for lib_data, lib_name in repo_split.items():
                lib, elfclass, rpath = lib_data
                obj = reversed_repo_split.setdefault(lib_name, set())
                obj.add((lib, elfclass, rpath))

            for lib_name in new_libraries:
                repo_lib_dumps |= reversed_repo_split[lib_name]

        return inst_lib_dumps, repo_lib_dumps

    def _lookup_library_breakages(self, match, installed_package_id, ldpaths):
        """
        Lookup packages that need to be bumped because "match" is being
        installed and "installed_package_id" removed.

        This method uses ELF NEEDED package metadata in order to accomplish
        this task.
        """
        inst_repo = self.installed_repository()
        cache_key = None

        if self.xcache:
            cache_s = "%s|%s|%s|%s|%s|%s|%s|%s|r8" % (
                match,
                installed_package_id,
                inst_repo.checksum(),
                self.repositories_checksum(),
                self._settings.packages_configuration_hash(),
                self._settings_client_plugin.packages_configuration_hash(),
                ";".join(sorted(self._settings['repositories']['available'])),
                ";".join(sorted(ldpaths)),
            )
            sha = hashlib.sha1()
            sha.update(const_convert_to_rawstring(cache_s))

            cache_key = "library_breakage/%s" % (sha.hexdigest(),)

            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        client_side, repo_side = self.__get_library_breakages(
            match, installed_package_id)

        matches = self._lookup_library_breakages_available(
            match, repo_side, ldpaths)
        installed_matches = self._lookup_library_breakages_installed(
            installed_package_id, client_side)

        # filter out myself
        installed_matches.discard(match)
        # drop items in repo_patches from installed_matches
        installed_matches -= matches

        if self.xcache:
            self._cacher.push(cache_key, (installed_matches, matches))

        return installed_matches, matches

    def _lookup_library_breakages_available(self, package_match,
                                            bumped_needed_libs,
                                            ldpaths):
        """
        Generate a list of package matches that should be bumped
        if the given libraries were installed.
        The returned list is composed by packages which are providing
        the new libraries.

        We assume that a repository is in a consistent state and
        packages requiring libfoo.so.1 have been dropped alltogether.
        """
        package_id, repository_id = package_match
        excluded_dep_types = (
            etpConst['dependency_type_ids']['bdepend_id'],)

        matched_deps = set()
        virtual_cat = EntropyRepositoryBase.VIRTUAL_META_PACKAGE_CATEGORY

        repo = self.open_repository(repository_id)
        dependencies = repo.retrieveDependencies(
            package_id, exclude_deptypes = excluded_dep_types)
        for dependency in dependencies:
            depmatch = self.atom_match(dependency)
            if depmatch[0] == -1:
                continue

            # Properly handle virtual packages
            dep_pkg_id, dep_repo = depmatch
            dep_db = self.open_repository(dep_repo)
            depcat = dep_db.retrieveCategory(dep_pkg_id)

            if depcat == virtual_cat:
                # in this case, we must go down one level in order to catch
                # the real, underlying dependencies. Otherwise, the
                # condition "if x in matched_deps" below will fail.
                # Scenario: dev-libs/glib depends against virtual/libffi.
                # virtual/libffi points to dev-libs/libffi which got a
                # soname bump. Buggy outcome: dev-libs/libffi is not
                # pulled in as dependency when it should be.
                virtual_dependencies = dep_db.retrieveDependencies(
                    dep_pkg_id, exclude_deptypes = excluded_dep_types)
                for virtual_dependency in virtual_dependencies:
                    virtualmatch = self.atom_match(virtual_dependency)
                    if virtualmatch[0] == -1:
                        continue
                    matched_deps.add(virtualmatch)

            matched_deps.add(depmatch)

        found_matches = set()
        keyslot = repo.retrieveKeySlotAggregated(package_id)
        for needed, elfclass, rpath in bumped_needed_libs:

            package_ldpaths = ldpaths | set(entropy.tools.parse_rpath(rpath))

            found = False
            for s_repo_id in self._settings['repositories']['order']:

                s_repo = self.open_repository(s_repo_id)
                solved_needed = s_repo.resolveNeeded(
                    needed, elfclass = elfclass, extended = True)

                # Filter out resolved needed that are not in package LDPATH.
                solved_needed = filter(
                    lambda x: os.path.dirname(x[1]) in package_ldpaths,
                    solved_needed)

                for repo_pkg_id, path in solved_needed:
                    repo_pkg_match = (repo_pkg_id, s_repo_id)

                    if package_match == repo_pkg_match:
                        # myself? no!
                        continue

                    if repo_pkg_match not in matched_deps:
                        # not a matched dep!
                        continue

                    s_keyslot = s_repo.retrieveKeySlotAggregated(
                        repo_pkg_id)
                    if s_keyslot == keyslot:
                        # do not pull anything inside the same keyslot!
                        continue

                    found_matches.add(repo_pkg_match)
                    found = True
                    break

                if found:
                    break

            if not found:
                # TODO: make it a real warning
                const_debug_write(
                    __name__,
                    "_lookup_library_breakages_available, HUGE QA BUG, "
                    "no (%s, %s) needed dependency for %s" % (
                        needed, elfclass, package_match,))

        matches = set()
        for _package_id, _repository_id in found_matches:
            _match = _package_id, _repository_id

            cmpstat = self._get_package_action(_match)
            if cmpstat == 0:
                continue

            if const_debug_enabled():
                atom = self.open_repository(
                    _repository_id).retrieveAtom(_package_id)
                const_debug_write(
                    __name__,
                    "_lookup_library_breakages_available, "
                    "adding repo atom => %s" % (atom,))

            matches.add(_match)

        return matches

    def _lookup_library_breakages_installed(self,
            installed_package_id, bumped_needed_libs):
        """
        Generate a list of package matches that should be bumped
        if the given libraries were removed.

        For instance: a package needs libfoo.so.2 while
        its installed version needs libfoo.so.1. This method will
        produce a list of updatable package matches that were
        relying on libfoo.so.1.
        We assume that a repository is in a consistent state and
        packages requiring libfoo.so.1 have been dropped alltogether.
        """
        inst_repo = self.installed_repository()

        # all the packages in bumped_needed_libs should be
        # pulled in and updated
        installed_package_ids = set()
        for needed, elfclass, rpath in bumped_needed_libs:
            found_neededs = inst_repo.searchNeeded(
                needed, elfclass = elfclass)
            installed_package_ids |= found_neededs
        # drop myself
        installed_package_ids.discard(installed_package_id)

        inst_keyslots = {inst_repo.retrieveKeySlotAggregated(x): x
                         for x in installed_package_ids}
        inst_keyslots.pop(None, None)

        # these can be pulled in after
        installed_matches = set()
        for keyslot, inst_package_id in inst_keyslots.items():

            package_id, repository_id = self.atom_match(keyslot)
            if package_id == -1:
                continue
            pkg_match = package_id, repository_id

            cmpstat = self._get_package_action(
                pkg_match, installed_package_id = inst_package_id)
            if cmpstat == 0:
                continue

            if const_debug_enabled():
                atom = self.open_repository(
                    repository_id).retrieveAtom(package_id)
                const_debug_write(
                    __name__,
                    "_lookup_library_breakages, "
                    "adding client atom => %s (%s)" % (atom, pkg_match))

            installed_matches.add(pkg_match)

        return installed_matches

    DISABLE_ASAP_SCHEDULING = os.getenv("ETP_DISABLE_ASAP_SCHEDULING")

    def __get_required_packages_asap_scheduling(self, deptree, adj_map,
        post_deps_cache):
        """
        Rewrite dependency tree generate by Graph in order to have
        post-dependencies scheduled as soon as possible.
        """
        def _shift_deptree():
            for lvl in sorted(deptree.keys(), reverse = True):
                deptree[lvl+1] = deptree[lvl]
            min_lvl = min(deptree.keys())
            deptree[min_lvl] = tuple()

        def _make_room(xlevel):
            for lvl in sorted(deptree.keys(), reverse = True):
                if lvl >= xlevel:
                    deptree[lvl+1] = deptree[lvl]
                else:
                    break
            deptree[xlevel] = tuple()

        def _find_first_requiring(dep_match, start_level):
            # find the closest
            for lvl in sorted(deptree.keys(), reverse = True):
                if lvl >= start_level:
                    continue
                deps = deptree[lvl]
                for dep in deps:
                    if dep_match in adj_map[dep]:
                        # found !
                        return dep

        levels = {}
        def _setup_levels():
            for lvl, deps in deptree.items():
                for dep in deps:
                    levels[dep] = lvl
        _setup_levels()

        for pkg_match, post_deps in post_deps_cache.items():
            for post_dep in post_deps:
                level = levels[post_dep]
                first_requiring = _find_first_requiring(post_dep, level)
                # NOTE: this heuristic only works if nothing is requiring
                # post dependency
                if first_requiring is None:
                    # add it right after
                    stick_level = levels[pkg_match] - 1
                    if stick_level == 0:
                        _shift_deptree()
                        _setup_levels()
                        stick_level = levels[pkg_match] - 1
                        level = levels[post_dep]

                    # NOTE: this can leave holes in the tree
                    # rewrite
                    deptree[level] = tuple((x for x in deptree[level] \
                        if x != post_dep))
                    deptree[stick_level] = tuple((x for x in \
                        deptree[stick_level] if x != post_dep))

                    if deptree[stick_level]:
                        _make_room(stick_level)

                    deptree[stick_level] = (post_dep,)
                    _setup_levels()

    def _get_required_packages(self, package_matches, empty_deps = False,
        deep_deps = False, relaxed_deps = False, build_deps = False,
        only_deps = False, quiet = False, recursive = True):

        ldpaths = frozenset(entropy.tools.collect_linker_paths())
        inst_repo = self.installed_repository()
        cache_key = None

        if self.xcache:
            sha = hashlib.sha1()

            cache_s = "%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|v8" % (
                ";".join(["%s" % (x,) for x in sorted(package_matches)]),
                empty_deps,
                deep_deps,
                relaxed_deps,
                build_deps,
                only_deps,
                recursive,
                inst_repo.checksum(),
                self.repositories_checksum(),
                self._settings.packages_configuration_hash(),
                self._settings_client_plugin.packages_configuration_hash(),
                ";".join(sorted(self._settings['repositories']['available'])),
                # needed when users do bogus things like editing config files
                # manually (branch setting)
                self._settings['repositories']['branch'],
                ";".join(sorted(ldpaths)))

            sha.update(const_convert_to_rawstring(cache_s))
            cache_key = "deptree/dep_tree_%s" % (sha.hexdigest(),)

            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        graph = Graph()
        deptree_conflicts = set()
        atomlen = len(package_matches)
        count = 0
        deps_not_found = set()

        # check if there are repositories needing some mandatory packages
        forced_matches = self._lookup_system_mask_repository_deps()
        if forced_matches:
            # XXX: can cause conflicting packages to be listed together.
            # should verify if each package_match points to the same match?
            # we can have conflicting pkgs in repo or even across repos.
            if isinstance(package_matches, (tuple, list)):
                package_matches = forced_matches + [x for x in package_matches \
                    if x not in forced_matches]
            elif isinstance(package_matches, set):
                # we cannot do anything about the order here
                package_matches |= set(forced_matches)
            else:
                raise AttributeError("unsupported package_matches type")

        sort_dep_text = _("Sorting dependencies")
        unsat_deps_cache = {}
        elements_cache = set()
        selected_matches_cache = {}
        selected_matches_set = set(package_matches)
        post_deps_cache = {}
        matchfilter = set()
        for matched_atom in package_matches:

            pkg_id, pkg_repo = matched_atom
            if (pkg_id == -1) or (pkg_repo == 1):
                raise AttributeError("invalid matched_atom: %s" % (
                    matched_atom,))

            if const_debug_enabled():
                const_debug_write(__name__,
                    "_get_required_packages matched_atom => %s" % (
                        matched_atom,))

            if not quiet:
                count += 1
                if (count%10 == 0) or (count == atomlen) or (count == 1):
                    self.output(sort_dep_text, importance = 0,
                        level = "info", back = True, header = ":: ",
                        footer = " ::", percent = True,
                        count = (count, atomlen)
                    )

            if matched_atom in matchfilter:
                continue

            try:
                mygraph, conflicts = self._generate_dependency_tree(
                    matched_atom, graph, empty_deps = empty_deps,
                    deep_deps = deep_deps, relaxed_deps = relaxed_deps,
                    build_deps = build_deps, only_deps = only_deps,
                    elements_cache = elements_cache,
                    unsatisfied_deps_cache = unsat_deps_cache,
                    post_deps_cache = post_deps_cache,
                    recursive = recursive,
                    selected_matches = selected_matches_set,
                    selected_matches_cache = selected_matches_cache,
                    ldpaths = ldpaths
                )
            except DependenciesNotFound as err:
                deps_not_found |= err.value
                conflicts = set()

            deptree_conflicts |= conflicts

        if deps_not_found:
            graph.destroy()
            raise DependenciesNotFound(deps_not_found)

        # get adjacency map before it gets destroyed by solve()
        adj_map = dict((x.item(), set(k.item() for k in y)) \
            for x, y in graph.get_adjacency_map().items())
        # solve depgraph and append conflicts
        deptree = graph.solve()
        if 0 in deptree:
            graph.destroy()
            raise KeyError("Graph contains a dep_level == 0")

        # now check and report dependencies with colliding scope and in case,
        # raise DependenciesCollision, containing information about collisions
        _dup_deps_collisions = {}
        for _level, _deps in deptree.items():
            for pkg_id, pkg_repo in _deps:
                keyslot = self.open_repository(pkg_repo).retrieveKeySlot(pkg_id)
                ks_set = _dup_deps_collisions.setdefault(keyslot, set())
                ks_set.add((pkg_id, pkg_repo))
        _colliding_deps = [x for x in _dup_deps_collisions.values() if \
            len(x) > 1]
        if _colliding_deps:
            graph.destroy()
            raise DependenciesCollision(_colliding_deps)

        # now use the ASAP herustic to anticipate post-dependencies
        # as much as possible
        if self.DISABLE_ASAP_SCHEDULING is None:
            # NOTE: this method can leave holes in deptree
            # they are removed right below
            self.__get_required_packages_asap_scheduling(deptree,
                adj_map, post_deps_cache)

        # reverse ketys in deptree, this allows correct order (not inverse)
        level_count = 0
        reverse_tree = {}
        for key in sorted(deptree, reverse = True):
            level_count += 1
            # fixup possible holes
            if not deptree[key]:
                continue
            reverse_tree[level_count] = deptree[key]

        graph.destroy()
        reverse_tree[0] = deptree_conflicts

        if self.xcache:
            self._cacher.push(cache_key, reverse_tree)

        return reverse_tree

    def __filter_depends_multimatched_atoms(self, package_id, repo_id, depends,
        filter_match_cache = None):

        remove_depends = set()
        excluded_dep_types = (etpConst['dependency_type_ids']['bdepend_id'],)
        if filter_match_cache is None:
            filter_match_cache = {}
        # filter_match_cache dramatically improves performance

        for d_package_id, d_repo_id in depends:

            cached = filter_match_cache.get((d_package_id, d_repo_id))
            if cached is None:

                my_remove_depends = set()

                dbconn = self.open_repository(d_repo_id)
                mydeps = dbconn.retrieveDependencies(d_package_id,
                    exclude_deptypes = excluded_dep_types)

                for mydep in mydeps:

                    matches, rslt = dbconn.atomMatch(mydep,
                        multiMatch = True)
                    if rslt != 0:
                        continue
                    matches = set((x, d_repo_id) for x in matches)

                    if len(matches) > 1:
                        if (package_id, repo_id) in matches:
                            # are all in depends?
                            matches -= depends
                            if matches:
                                # no, they aren't
                                my_remove_depends.add((d_package_id, d_repo_id))

                filter_match_cache[(d_package_id, d_repo_id)] = my_remove_depends
                cached = my_remove_depends

            remove_depends |= cached

        depends -= remove_depends
        return depends

    def _get_installed_packages_system_mask(self):
        """
        Get the installed packages matches system mask metadata.
        """
        sha = hashlib.sha1()

        inst_repo = self.installed_repository()
        cache_s = "%s|%s|v1" % (
            inst_repo.checksum(),
            self._settings['repositories']['branch'])

        sha.update(const_convert_to_rawstring(cache_s))
        cache_key = "system_mask/mask_%s" % (sha.hexdigest(),)

        if self.xcache:
            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        settings = self.Settings()
        cl_settings = self.ClientSettings()
        repo_settings = cl_settings['repositories']
        repos_mask_list = repo_settings['system_mask']
        m_list = repos_mask_list + settings['system_mask']

        mc_cache = set()
        mask_installed = []
        mask_installed_keys = {}

        for atom in m_list:
            try:
                m_ids, m_r = inst_repo.atomMatch(
                    atom, multiMatch = True)
                if m_r != 0:
                    continue
            except EntropyRepositoryError:
                continue

            mykey = entropy.dep.dep_getkey(atom)
            obj = mask_installed_keys.setdefault(mykey, set())
            for m_id in m_ids:
                if m_id in mc_cache:
                    continue
                mc_cache.add(m_id)
                mask_installed.append(m_id)
                obj.add(m_id)

        data = {
            'ids': mask_installed,
            'keys': mask_installed_keys,
        }

        if self.xcache:
            self._cacher.push(cache_key, data, async = False)

        return data

    DISABLE_NEEDED_SCANNING = os.getenv("ETP_DISABLE_ELF_NEEDED_SCANNING")

    def _generate_reverse_dependency_tree(self, matched_atoms, deep = False,
        recursive = True, empty = False, system_packages = True,
        elf_needed_scanning = True):

        """
        @raise DependenciesNotRemovable: if at least one dependencies is
        considered vital for the system.
        """

        # experimental feature, make possible to override it
        # please remove in future.
        if self.DISABLE_NEEDED_SCANNING:
            elf_needed_scanning = False

        if const_debug_enabled():
            const_debug_write(__name__,
                "\n_generate_reverse_dependency_tree " \
                "[m:%s => %s|d:%s|r:%s|e:%s|s:%s|es:%s]" \
                    % (matched_atoms,
                    [self.open_repository(x[1]).retrieveAtom(x[0]) \
                        for x in matched_atoms], deep, recursive, empty,
                        system_packages, elf_needed_scanning))

        inst_repo = self.installed_repository()
        cache_key = None

        if self.xcache:
            sha = hashlib.sha1()

            cache_s = "ma{%s}s{%s;%s;%s;%s;%s;%s;%s;%s;%s;%s}v5" % (
                ";".join(["%s" % (x,) for x in sorted(matched_atoms)]),
                deep,
                recursive,
                empty,
                system_packages,
                elf_needed_scanning,
                inst_repo.checksum(),
                self.repositories_checksum(),
                self._settings.packages_configuration_hash(),
                self._settings_client_plugin.packages_configuration_hash(),
                ";".join(sorted(self._settings['repositories']['available'])),
                )
            sha.update(const_convert_to_rawstring(cache_s))

            cache_key = "depends/tree_%s" % (sha.hexdigest(),)

            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        if const_debug_enabled():
            const_debug_write(__name__,
                "\n_generate_reverse_dependency_tree [m:%s] not cached!" % (
                    matched_atoms,))

        count = 0
        match_cache = set()
        stack = Lifo()
        graph = Graph()
        not_removable_deps = set()
        deep_dep_map = {}
        filter_multimatch_cache = {}
        needed_providers_left = {}

        system_mask_data = self._get_installed_packages_system_mask()

        # post-dependencies won't be pulled in
        pdepend_id = etpConst['dependency_type_ids']['pdepend_id']
        bdepend_id = etpConst['dependency_type_ids']['bdepend_id']
        rem_dep_text = _("Calculating inverse dependencies for")
        for match in matched_atoms:
            stack.push(match)

        def get_deps(repo_db, d_deps):
            deps = set()
            for d_dep in d_deps:
                if repo_db is self.installed_repository():
                    m_package_id, m_rc_x = repo_db.atomMatch(d_dep)
                    m_rc = InstalledPackagesRepository.NAME
                else:
                    m_package_id, m_rc = self.atom_match(d_dep)

                if m_package_id != -1:
                    deps.add((m_package_id, m_rc))

            return deps

        def get_direct_deps(repo_db, pkg_id):
            return repo_db.retrieveDependencies(pkg_id,
                exclude_deptypes = (bdepend_id,))

        def filter_deps(raw_deps):
            filtered_deps = set()
            for mydep, m_repo_id in raw_deps:
                m_repo_db = self.open_repository(m_repo_id)

                if system_packages:
                    if m_repo_db.isSystemPackage(mydep):
                        if const_debug_enabled():
                            const_debug_write(__name__,
                            "\n_generate_reverse_dependency_tree [md:%s] "
                                "cannot calculate, it's a system package" \
                                % ((mydep, m_repo_id),))
                        continue
                    if m_repo_db is self.installed_repository():
                        if mydep in system_mask_data['ids']:
                            if const_debug_enabled():
                                const_debug_write(__name__,
                                "\n_generate_reverse_dependency_tree [md:%s] "
                                    "cannot calculate, it's in sysmask" \
                                    % ((mydep, m_repo_id),))
                            continue

                filtered_deps.add((mydep, m_repo_id,))
            return filtered_deps

        def _filter_simple_or_revdeps(pkg_id, repo_id, repo_db,
            reverse_deps_ids):
            # filter out reverse dependencies whose or dependencies
            # are anyway satisfied
            reverse_deps = set()
            for dep_pkg_id, dep_str in reverse_deps_ids:
                if dep_str.endswith(etpConst['entropyordepquestion']):
                    or_dep_lst = dep_str[:-1].split(etpConst['entropyordepsep'])
                    # how many are currently installed?
                    or_dep_ids = set()
                    for or_dep in or_dep_lst:
                        or_pkg_id, or_rc = repo_db.atomMatch(or_dep)
                        if or_rc == 0:
                            or_dep_ids.add(or_pkg_id)
                    if pkg_id in or_dep_ids:
                        or_dep_ids.discard(pkg_id)
                    if or_dep_ids:
                        # drop already analyzed matches
                        or_dep_matches = set((x, repo_id) for x in or_dep_ids)
                        or_dep_matches -= match_cache
                        if or_dep_matches:
                            # we can ignore this
                            if const_debug_enabled():
                                const_debug_write(__name__,
                                brown("\n_generate_reverse_dependency_tree" \
                                    ".get_revdeps ignoring %s => %s " \
                                    "due to: %s, for %s" % (
                                    (pkg_id, repo_id),
                                    self.open_repository(repo_id).retrieveAtom(
                                        pkg_id),
                                    dep_str,
                                    self.open_repository(repo_id).retrieveAtom(
                                        dep_pkg_id))))
                            continue
                        elif const_debug_enabled():
                            const_debug_write(__name__,
                                teal("\n_generate_reverse_dependency_tree" \
                                ".get_revdeps cannot ignore %s :: %s " \
                                ":: dep_str: %s, for : %s" % (
                                (pkg_id, repo_id),
                                self.open_repository(repo_id).retrieveAtom(
                                    pkg_id),
                                dep_str,
                                self.open_repository(repo_id).retrieveAtom(
                                    dep_pkg_id))))
                reverse_deps.add((dep_pkg_id, repo_id))
            return reverse_deps

        def get_revdeps(pkg_id, repo_id, repo_db):
            # obtain its inverse deps
            reverse_deps_ids = repo_db.retrieveReverseDependencies(
                pkg_id, exclude_deptypes = (pdepend_id, bdepend_id,),
                extended = True)
            if const_debug_enabled():
                const_debug_write(__name__,
                "\n_generate_reverse_dependency_tree.get_revdeps: " \
                    "orig revdeps: %s => %s" % (sorted(reverse_deps_ids),
                    sorted([repo_db.retrieveAtom(x[0]) for x in \
                        reverse_deps_ids]),))

            reverse_deps = _filter_simple_or_revdeps(pkg_id, repo_id, repo_db,
                reverse_deps_ids)
            if const_debug_enabled():
                const_debug_write(__name__,
                "\n_generate_reverse_dependency_tree.get_revdeps: " \
                    "after filter: %s => %s" % (sorted(reverse_deps),
                    sorted([repo_db.retrieveAtom(x[0]) for x in \
                        reverse_deps]),))

            if reverse_deps:
                reverse_deps = self.__filter_depends_multimatched_atoms(
                    pkg_id, repo_id, reverse_deps,
                    filter_match_cache = filter_multimatch_cache)
                if const_debug_enabled():
                    const_debug_write(__name__,
                    "\n_generate_reverse_dependency_tree.get_revdeps: " \
                        "after filter_depends: %s => %s" % (
                            sorted(reverse_deps),
                            sorted([repo_db.retrieveAtom(x[0]) for x in \
                                reverse_deps]),))

            return reverse_deps

        def get_revdeps_lib(pkg_id, repo_id, repo_db):
            provided_libs = repo_db.retrieveProvidedLibraries(pkg_id)
            reverse_deps = set()

            for needed, path, elfclass in provided_libs:
                # let's see what package is actually resolving
                # this library, if there are more than one, we
                # can still be happy.
                needed_key = (needed, elfclass)
                needed_providers = needed_providers_left.get(needed_key)
                if needed_providers is None:
                    needed_providers = set(repo_db.resolveNeeded(
                        needed, elfclass = elfclass))
                    needed_providers_left[needed_key] = needed_providers

                # remove myself
                needed_providers.discard(pkg_id)
                if needed_providers:
                    # another package is providing the same library
                    # so it's not a problem to skip this package.
                    if const_debug_enabled():
                        const_debug_write(
                            __name__,
                            "_generate_reverse_dependency_tree.get_revdeps_lib:"
                            " skipping needed dependencies for (%s, %s, %s),"
                            " still having: %s" % (
                                needed, path, elfclass,
                                [repo_db.retrieveAtom(x)
                                 for x in needed_providers]))
                    continue

                for needed_package_id in repo_db.searchNeeded(
                        needed, elfclass = elfclass):
                    reverse_deps.add((needed_package_id, repo_id))

            if reverse_deps:
                reverse_deps = self.__filter_depends_multimatched_atoms(
                    pkg_id, repo_id, reverse_deps,
                    filter_match_cache = filter_multimatch_cache)
            # remove myself
            reverse_deps.discard((pkg_id, repo_id))

            # remove packages in the same slot, this is required in a case
            # like this:
            #    _generate_reverse_dependency_tree [m:(17434, '__system__')
            #    => x11-drivers/xf86-video-virtualbox-4.0.4#2.6.37-sabayon]
            #    rev_deps: set([(17432, '__system__'),
            #    (17435, '__system__')]) =>
            #  ['x11-drivers/xf86-video-virtualbox-4.0.4#2.6.38-sabayon',
            #   'app-emulation/virtualbox-guest-additions-4.0.4#2.6.37-sabayon']
            #   :: reverse_deps_lib: set([(17432, '__system__')])
            # where xf86-video-virtualbox erroneously pulls in its cousin :-)
            keyslot = None
            pkg_tag = None
            if reverse_deps:
                # only if we advertise a package tag
                pkg_tag = repo_db.retrieveTag(pkg_id)
                if pkg_tag:
                    keyslot = repo_db.retrieveKeySlotAggregated(pkg_id)

            if keyslot and pkg_tag:
                keyslot = entropy.dep.remove_tag_from_slot(keyslot)
                filtered_reverse_deps = set()
                for revdep_match in reverse_deps:
                    revdep_pkg_id, revdep_repo_id = revdep_match
                    revdep_db = self.open_repository(revdep_repo_id)
                    revdep_keyslot = revdep_db.retrieveKeySlotAggregated(
                        revdep_pkg_id)
                    if revdep_keyslot is not None:
                        revdep_keyslot = entropy.dep.remove_tag_from_slot(
                            revdep_keyslot)
                    if revdep_keyslot != keyslot:
                        filtered_reverse_deps.add(revdep_match)
                reverse_deps = filtered_reverse_deps

            return reverse_deps

        def setup_revdeps(filtered_deps):
            for d_rev_dep, d_repo_id in filtered_deps:
                d_repo_db = self.open_repository(d_repo_id)
                mydepends = d_repo_db.retrieveReverseDependencies(
                    d_rev_dep, exclude_deptypes = \
                        (pdepend_id, bdepend_id,))
                deep_dep_map[(d_rev_dep, d_repo_id)] = \
                    set((x, d_repo_id) for x in mydepends)

                if const_debug_enabled():
                    const_debug_write(__name__,
                    "\n_generate_reverse_dependency_tree [d_dep:%s] " \
                        "reverse deps: %s" % ((d_rev_dep, d_repo_id),
                        mydepends,))

        while stack.is_filled():

            pkg_id, repo_id = stack.pop()
            if (pkg_id, repo_id) in match_cache:
                # already analyzed
                continue
            match_cache.add((pkg_id, repo_id))

            if system_packages:
                system_pkg = not self.validate_package_removal(pkg_id,
                    repo_id = repo_id)

                if system_pkg:
                    # this is a system package, removal forbidden
                    not_removable_deps.add((pkg_id, repo_id))
                    if const_debug_enabled():
                        const_debug_write(__name__,
                        "\n_generate_reverse_dependency_tree %s is sys_pkg!" % (
                        (pkg_id, repo_id),))
                    continue

            repo_db = self.open_repository(repo_id)

            count += 1
            p_atom = repo_db.retrieveAtom(pkg_id)
            if p_atom is None:
                if const_debug_enabled():
                    const_debug_write(__name__,
                    "\n_generate_reverse_dependency_tree %s not available!" % (
                    (pkg_id, repo_id),))
                continue
            self.output(
                blue(rem_dep_text + " %s" % (purple(p_atom),)),
                importance = 0,
                level = "info",
                back = True,
                header = '|/-\\'[count%4]+" "
            )

            reverse_deps = get_revdeps(pkg_id, repo_id, repo_db)
            if const_debug_enabled():
                const_debug_write(__name__,
                    "\n_generate_reverse_dependency_tree, [m:%s => %s], " \
                    "get_revdeps: %s => %s" % (
                    (pkg_id, repo_id), p_atom, reverse_deps,
                    [self.open_repository(x[1]).retrieveAtom(x[0]) \
                        for x in reverse_deps]))

            reverse_deps_lib = set()
            if elf_needed_scanning:
                # use metadata collected during package generation to
                # look for dependencies based on ELF NEEDED.
                # a nice example is libpng-1.2 vs libpng-1.4 when pkg
                # lists a generic media-libs/libpng as dependency.
                reverse_deps_lib = get_revdeps_lib(pkg_id, repo_id, repo_db)
                reverse_deps |= reverse_deps_lib

            if const_debug_enabled():
                const_debug_write(__name__,
                    "\n_generate_reverse_dependency_tree [m:%s => %s] " \
                    "rev_deps: %s => %s :: reverse_deps_lib: %s" % (
                    (pkg_id, repo_id), p_atom, reverse_deps,
                    [self.open_repository(x[1]).retrieveAtom(x[0]) \
                        for x in reverse_deps],
                        reverse_deps_lib,))

            if deep:

                d_deps = get_direct_deps(repo_db, pkg_id)
                if const_debug_enabled():
                    const_debug_write(__name__,
                    "\n_generate_reverse_dependency_tree [m:%s] d_deps: %s" % (
                    (pkg_id, repo_id), d_deps,))

                # now filter them
                mydeps = filter_deps(get_deps(repo_db, d_deps))

                if const_debug_enabled():
                    const_debug_write(__name__,
                    "\n_generate_reverse_dependency_tree done filtering out" \
                        " direct dependencies: %s" % (mydeps,))

                if empty:
                    reverse_deps |= mydeps
                    if const_debug_enabled():
                        const_debug_write(__name__,
                        "\n_generate_reverse_dependency_tree done empty=True," \
                            " adding: %s" % (mydeps,))
                else:
                    # to properly pull in every direct dependency with no
                    # reverse dependencies, we need to setup a dependency
                    # map first, and then make sure there are no chained
                    # package identifiers by removing direct dependencies
                    # from the list of reverse dependencies
                    setup_revdeps(mydeps)

                if empty:
                    empty = False

            if recursive:
                for rev_dep in reverse_deps:
                    stack.push(rev_dep)
            graph.add((pkg_id, repo_id), reverse_deps)


        del stack
        if not_removable_deps:
            raise DependenciesNotRemovable(not_removable_deps)
        deptree = graph.solve()

        if deep:
            # in order to catch unused reverse dependencies
            # it is required to iterate over the direct dependencies
            # every time a new direct dependency gets pulled in in
            # the removal queue.
            # in this way, every orphan package will be considered
            # for removal automatically.

            flat_dep_tree = set()
            for r_deps in deptree.values():
                flat_dep_tree.update(r_deps)

            while True:
                change = False
                # now try to deeply remove unused packages
                # iterate over a copy
                for pkg_match in deep_dep_map.keys():
                    deep_dep_map[pkg_match] -= flat_dep_tree
                    if (not deep_dep_map[pkg_match]) and \
                        (pkg_match not in flat_dep_tree):

                        graph.add(pkg_match, set())
                        flat_dep_tree.add(pkg_match)

                        # get direct dependencies
                        pkg_id, pkg_repo = pkg_match
                        repo_db = self.open_repository(pkg_repo)
                        pkg_d_deps = get_direct_deps(repo_db, pkg_id)
                        pkg_d_matches = filter_deps(
                            get_deps(repo_db, pkg_d_deps))
                        setup_revdeps(pkg_d_matches)
                        change = True

                if not change:
                    break

            deptree = graph.solve()
            del flat_dep_tree

        graph.destroy()

        if cache_key is not None:
            self._cacher.push(cache_key, deptree)

        return deptree

    @sharedinstlock
    def calculate_masked_packages(self, use_cache = True):
        """
        Compute a list of masked packages. For masked packages it is meant
        a list of packages that cannot be installed without explicit user
        confirmation.

        @keyword use_cache: use on-disk cache
        @type use_cache: bool
        @return: list of masked package matches + mask reason id
            [((package_id, repository_id), reason_id), ...]
        @rtype: list
        """
        sha = hashlib.sha1()

        cache_s = "{%s;%s}v2" % (
            self.repositories_checksum(),
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self._settings['repositories']['branch'])
        sha.update(const_convert_to_rawstring(cache_s))

        cache_key = "available/masked_%s" % (sha.hexdigest(),)

        if use_cache and self.xcache:
            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        masked = []
        for repository_id in self.filter_repositories(self.repositories()):
            repo = self.open_repository(repository_id)
            try:
                # db may be corrupted, we cannot deal with it here
                package_ids = repo.listAllPackageIds()
            except OperationalError:
                continue

            def fm(pkg_id):
                pkg_id_filtered, reason_id = repo.maskFilter(pkg_id)
                if pkg_id_filtered == -1:
                    return ((pkg_id, repository_id,), reason_id)
                return None
            masked += [x for x in map(fm, package_ids) if x is not None]

        # add live unmasked elements too
        unmasks = self._settings['live_packagemasking']['unmask_matches']
        live_reason_id = etpConst['pkg_masking_reference']['user_live_unmask']
        for package_id, repository_id in unmasks:
            match_data = ((package_id, repository_id), live_reason_id,)
            if match_data in masked:
                continue
            masked.append(match_data)

        if self.xcache:
            self._cacher.push(cache_key, masked)

        return masked

    @sharedinstlock
    def calculate_available_packages(self, use_cache = True):
        """
        Compute a list of available packages in repositories. For available
        packages it is meant a list of non-installed packages.

        @keyword use_cache: use on-disk cache
        @type use_cache: bool
        @return: list of available package matches
        @rtype: list
        """
        sha = hashlib.sha1()

        cache_s = "{%s;%s}v2" % (
            self.repositories_checksum(),
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self._settings['repositories']['branch'])
        sha.update(const_convert_to_rawstring(cache_s))

        cache_key = "available/packages_%s" % (sha.hexdigest(),)

        if use_cache and self.xcache:
            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        available = []
        for repository_id in self.filter_repositories(self.repositories()):
            repo = self.open_repository(repository_id)
            try:
                # db may be corrupted, we cannot deal with it here
                package_ids = [x for x in repo.listAllPackageIds(
                    order_by = 'atom') if repo.maskFilter(x)[0] != -1]
            except OperationalError:
                continue
            myavailable = []
            do_break = False
            for package_id in package_ids:
                if do_break:
                    break
                # get key + slot
                try:
                    key_slot = repo.retrieveKeySlot(package_id)
                    if key_slot is None:
                        # mmh... invalid entry, ignore
                        continue
                    key, slot = key_slot
                    matches = self.installed_repository().searchKeySlot(key, slot)
                except (DatabaseError, IntegrityError, OperationalError,):
                    do_break = True
                    continue
                if not matches:
                    myavailable.append((package_id, repository_id))

            available += myavailable[:]

        if self.xcache:
            self._cacher.push(cache_key, available)

        return available

    @sharedinstlock
    def calculate_critical_updates(self, use_cache = True):

        # check if we are branch migrating
        # in this case, critical pkgs feature is disabled
        in_branch_upgrade = etpConst['etp_in_branch_upgrade_file']
        if const_file_readable(in_branch_upgrade):
            return set(), []

        enabled_repos = self.filter_repositories(self.repositories())
        repo_order = [x for x in self._settings['repositories']['order'] if
            x in enabled_repos]

        inst_repo = self.installed_repository()

        cache_s = "%s|%s|%s|%s|%s|%s|%s|%s|v5" % (
            enabled_repos,
            inst_repo.checksum(),
            self.repositories_checksum(),
            self._settings.packages_configuration_hash(),
                self._settings_client_plugin.packages_configuration_hash(),
            ";".join(sorted(self._settings['repositories']['available'])),
            repo_order,
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self._settings['repositories']['branch'],
        )
        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring(cache_s))

        cache_key = "critical/%s" % (sha.hexdigest(),)

        if use_cache and self.xcache:
            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        client_settings = self.ClientSettings()
        critical_data = client_settings['repositories']['critical_updates']

        # do not match package repositories, never consider them in updates!
        # that would be a nonsense, since package repos are temporary.
        enabled_repos = self.filter_repositories(self.repositories())
        match_repos = tuple([x for x in \
            self._settings['repositories']['order'] if x in enabled_repos])

        atoms = set()
        atom_matches = {}
        for repoid in critical_data:
            for atom in critical_data[repoid]:
                match_id, match_repo = self.atom_match(atom,
                    match_repo = match_repos)
                if match_repo == 1:
                    continue
                atom_matches[atom] = (match_id, match_repo,)
                atoms.add(atom)

        atoms = self._get_unsatisfied_dependencies(atoms, relaxed_deps = True,
            match_repo = match_repos)
        matches = [atom_matches.get(atom) for atom in atoms]
        data = (atoms, matches)

        if self.xcache:
            self._cacher.push(cache_key, data, async = False)

        return data

    @sharedinstlock
    def calculate_security_updates(self, use_cache = True):
        """
        Return a list of security updates available using Entropy Security
        interface and Client.calculate_updates().

        @keyword use_cache: Use Entropy cache, if available
        @type use_cache: bool
        @return: list of Entropy package matches that should be updated
        @rtype: list
        """
        outcome = self.calculate_updates(
            critical_updates = False, use_cache = use_cache)
        update, remove = outcome['update'], outcome['remove']
        fine, spm_fine = outcome['fine'], outcome['spm_fine']
        if not update:
            return []

        deps = set()

        security = self.Security()
        for advisory_id in security.list():
            deps.update(security.affected_id(advisory_id))

        sec_updates = []
        inst_repo = self.installed_repository()
        for vul_dep in deps:
            pkg_id, rc = inst_repo.atomMatch(vul_dep)
            if pkg_id == -1:
                continue

            matches, rc = self.atom_match(vul_dep, multi_repo = True,
                multi_match = True)

            # filter dups, keeping order
            matches = [x for x in matches if x not in sec_updates]
            sec_updates += [x for x in matches if x in update]

        return sec_updates

    @sharedinstlock
    def calculate_updates(self, empty = False, use_cache = True,
        critical_updates = True, quiet = False):
        """
        Calculate package updates. By default, this method also handles critical
        updates priority. Updates (as well as other objects here) are returned
        in alphabetical order. To generate a valid installation queue, have a
        look at Client.get_install_queue().

        @keyword empty: consider the installed packages repository
            empty. Mark every package as update.
        @type empty: bool
        @keyword use_cache: use Entropy cache
        @type use_cache: bool
        @keyword critical_updates: if False, disable critical updates check
            priority.
        @type critical_updates: bool
        @keyword quiet: do not print any status info if True
        @type quiet: bool
        @return: dict composed by (list of package matches ("update" key),
            list of installed package identifiers ("remove" key), list of
            package names already up-to-date ("fine" key), list of package names
            already up-to-date when user enabled "ignore-spm-downgrades",
            "spm_fine" key), if critical updates were found ("critical_found"
            key). If critical_found is True, relaxed dependencies calculation
            must be enforced.
        @rtype: tuple
        """
        cl_settings = self.ClientSettings()
        misc_settings = cl_settings['misc']

        # critical updates hook, if enabled
        # this will force callers to receive only critical updates
        if misc_settings.get('forcedupdates') and critical_updates:
            _atoms, update = self.calculate_critical_updates(
                use_cache = use_cache)
            if update:
                return {
                    'update': update,
                    'remove': [],
                    'fine': [],
                    'spm_fine': [],
                    'critical_found': True,
                    }

        inst_repo = self.installed_repository()
        ignore_spm_downgrades = misc_settings['ignore_spm_downgrades']
        enabled_repos = self.filter_repositories(self.repositories())
        repo_order = [x for x in self._settings['repositories']['order'] if
                      x in enabled_repos]

        cache_s = "%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|v7" % (
            empty,
            enabled_repos,
            inst_repo.checksum(),
            self.repositories_checksum(),
            self._settings.packages_configuration_hash(),
            self._settings_client_plugin.packages_configuration_hash(),
            ";".join(sorted(self._settings['repositories']['available'])),
            repo_order,
            ignore_spm_downgrades,
            # needed when users do bogus things like editing config files
            # manually (branch setting)
            self._settings['repositories']['branch'],
        )

        sha = hashlib.sha1()
        sha.update(const_convert_to_rawstring(cache_s))
        cache_key = "updates/%s_v1" % (sha.hexdigest(),)

        if use_cache and self.xcache:
            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        # do not match package repositories, never consider them in updates!
        # that would be a nonsense, since package repos are temporary.
        enabled_repos = self.filter_repositories(self.repositories())
        match_repos = tuple([x for x in \
            self._settings['repositories']['order'] if x in enabled_repos])

        # get all the installed packages
        try:
            package_ids = collections.deque(
                self.installed_repository().listAllPackageIds())
        except OperationalError:
            # client db is broken!
            raise SystemDatabaseError("installed packages repository is broken")

        count = 0
        total = len(package_ids)
        last_count = 0
        remove = collections.deque()
        fine = collections.deque()
        spm_fine = collections.deque()
        update = set()

        while True:
            try:
                package_id = package_ids.pop()
            except IndexError:
                break
            count += 1

            if not quiet:

                avg = int(float(count) / total * 100)
                execute = avg % 10 == 9 and last_count < count
                if not execute:
                    execute = (count == total) or (count == 1)

                if execute:
                    last_count = count
                    self.output(
                        _("Calculating updates"),
                        importance = 0,
                        level = "info",
                        back = True,
                        header = ":: ",
                        count = (count, total),
                        percent = True,
                        footer = " ::"
                    )

            try:
                cl_pkgkey, cl_slot, cl_version, \
                    cl_tag, cl_revision, \
                    cl_atom = self.installed_repository().getStrictData(
                        package_id)
            except TypeError:
                # check against broken entries, or removed during iteration
                continue
            use_match_cache = True
            do_continue = False

            # try to search inside package tag, if it's available,
            # otherwise, do the usual duties.
            cl_pkgkey_tag = None
            if cl_tag:
                cl_pkgkey_tag = "%s%s%s" % (
                    cl_pkgkey,
                    etpConst['entropytagprefix'],
                    cl_tag)

            while True:
                try:
                    match = None
                    if cl_pkgkey_tag is not None:
                        # search with tag first, if nothing
                        # pops up, fallback
                        # to usual search?
                        match = self.atom_match(
                            cl_pkgkey_tag,
                            match_slot = cl_slot,
                            extended_results = True,
                            use_cache = use_match_cache,
                            match_repo = match_repos
                        )
                        try:
                            if const_isnumber(match[1]):
                                match = None
                        except TypeError:
                            if not use_match_cache:
                                raise
                            use_match_cache = False
                            continue

                    if match is None:
                        match = self.atom_match(
                            cl_pkgkey,
                            match_slot = cl_slot,
                            extended_results = True,
                            use_cache = use_match_cache,
                            match_repo = match_repos
                        )
                except OperationalError:
                    # ouch, but don't crash here
                    do_continue = True
                    break
                try:
                    m_package_id = match[0][0]
                except TypeError:
                    if not use_match_cache:
                        raise
                    use_match_cache = False
                    continue
                break

            if do_continue:
                continue

            # now compare
            # version: cl_version
            # tag: cl_tag
            # revision: cl_revision
            if (m_package_id != -1):
                repoid = match[1]
                version = match[0][1]
                tag = match[0][2]
                revision = match[0][3]
                if empty:
                    update.add((m_package_id, repoid))
                    continue
                if cl_revision != revision:
                    # different revision
                    if cl_revision == etpConst['spmetprev'] \
                            and ignore_spm_downgrades:
                        # no difference, we're ignoring revision 9999
                        fine.append(cl_atom)
                        spm_fine.append((m_package_id, repoid))
                        continue
                    else:
                        update.add((m_package_id, repoid))
                        continue
                elif (cl_version != version):
                    # different versions
                    update.add((m_package_id, repoid))
                    continue
                elif (cl_tag != tag):
                    # different tags
                    update.add((m_package_id, repoid))
                    continue
                else:

                    # Note: this is a bugfix to improve branch migration
                    # and really check if pkg has been repackaged
                    # first check branch
                    if package_id is not None:

                        c_digest = self.installed_repository().retrieveDigest(
                            package_id)
                        # If the repo has been manually (user-side)
                        # regenerated, digest == "0". In this case
                        # skip the check.
                        if c_digest != "0":
                            c_repodb = self.open_repository(repoid)
                            r_digest = c_repodb.retrieveDigest(m_package_id)

                            if (r_digest != c_digest) and \
                               (r_digest is not None) \
                               and (c_digest is not None):
                                update.add((m_package_id, repoid))
                                continue

                    # no difference
                    fine.append(cl_atom)
                    continue

            # don't take action if it's just masked
            maskedresults = self.atom_match(
                cl_pkgkey, match_slot = cl_slot,
                mask_filter = False, match_repo = match_repos)
            if maskedresults[0] == -1:
                remove.append(package_id)

        # validate remove, do not return installed packages that are
        # still referenced by others as "removable"
        # check inverse dependencies at the cost of growing complexity
        if remove:
            remove = [
                x for x in remove if not \
                    self.installed_repository().retrieveReverseDependencies(x)]
        else:
            remove = list(remove)

        # sort data
        upd_sorter = lambda x: self.open_repository(x[1]).retrieveAtom(x[0])
        rm_sorter = lambda x: self.installed_repository().retrieveAtom(x)
        update = sorted(update, key = upd_sorter)
        fine = sorted(fine)
        spm_fine = sorted(spm_fine, key = upd_sorter)
        remove = sorted(remove, key = rm_sorter)

        outcome = {
            'update': update,
            'remove': remove,
            'fine': fine,
            'spm_fine': spm_fine,
            'critical_found': False,
            }

        if self.xcache:
            self._cacher.push(cache_key, outcome, async = False)
            self._cacher.sync()

        if not update:
            # delete branch upgrade file if exists, since there are
            # no updates, this file does not deserve to be saved anyway
            br_path = etpConst['etp_in_branch_upgrade_file']
            try:
                os.remove(br_path)
            except OSError:
                pass

        return outcome

    @sharedinstlock
    def calculate_orphaned_packages(self, use_cache = True):
        """
        Collect Installed Packages that are no longer available
        in Entropy repositories due to their support being
        discontinued. If no orphaned packages are found, empty
        lists will be returned.

        @return: tuple composed by manually removable installed
        package ids (list) and automatically removable ones (list)
        @rtype: tuple
        """
        outcome = self.calculate_updates(use_cache = use_cache)
        update, remove = outcome['update'], outcome['remove']
        fine, spm_fine = outcome['fine'], outcome['spm_fine']

        installed_repo = self.installed_repository()
        # verify that client database package_id still exist,
        # validate here before passing removePackage() wrong info
        remove = [x for x in remove if \
                      installed_repo.isPackageIdAvailable(x)]
        # Filter out packages installed from unavailable
        # repositories, this is mainly required to allow
        # 3rd party packages installation without
        # erroneously inform user about unavailability.
        unavail_pkgs = []
        manual_unavail_pkgs = []
        repos = self.repositories()
        for package_id in remove:
            repo_id = installed_repo.getInstalledPackageRepository(
                package_id)
            if not repo_id:
                continue
            if repo_id in repos:
                continue
            if repo_id == etpConst['spmdbid']:
                etp_rev = installed_repo.retrieveRevision(
                    package_id)
                if etp_rev == etpConst['spmetprev']:
                    unavail_pkgs.append(package_id)
                    continue
            unavail_pkgs.append(package_id)
            manual_unavail_pkgs.append(package_id)

        remove = [x for x in remove if x not in unavail_pkgs]
        # drop system packages for automatic removal,
        # user has to do it manually.
        system_unavail_pkgs = [x for x in remove if \
            not self.validate_package_removal(x)]
        remove = [x for x in remove if x not in system_unavail_pkgs]

        manual_removal = []
        if (manual_unavail_pkgs or remove or system_unavail_pkgs) and \
                self.repositories():
            manual_removal.extend(sorted(
                set(manual_unavail_pkgs + system_unavail_pkgs)))

        return manual_removal, remove

    def _get_masked_packages_tree(self, package_match, atoms = False,
        flat = False, matchfilter = None):

        if matchfilter is None:
            matchfilter = set()
        maskedtree = {}
        mybuffer = Lifo()
        depcache = set()
        treelevel = -1

        match_id, match_repo = package_match
        mydbconn = self.open_repository(match_repo)
        myatom = mydbconn.retrieveAtom(match_id)
        package_id, idreason = mydbconn.maskFilter(match_id)
        if package_id == -1:
            treelevel += 1
            if atoms:
                mydict = {myatom: idreason}
            else:
                mydict = {package_match: idreason}
            if flat:
                maskedtree.update(mydict)
            else:
                maskedtree[treelevel] = mydict

        excluded_deps = [etpConst['dependency_type_ids']['bdepend_id']]
        mydeps = mydbconn.retrieveDependencies(match_id,
            exclude_deptypes = excluded_deps)
        for mydep in mydeps:
            mybuffer.push(mydep)

        try:
            mydep = mybuffer.pop()
        except ValueError:
            mydep = None # stack empty

        while mydep:

            if mydep in depcache:
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    break # stack empty
                continue
            depcache.add(mydep)

            package_id, repoid = self.atom_match(mydep)
            if (package_id, repoid) in matchfilter:
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    break # stack empty
                continue

            if package_id != -1:
                # doing even here because atomMatch with
                # maskFilter = False can pull something different
                matchfilter.add((package_id, repoid))

            # collect masked
            if package_id == -1:
                package_id, repoid = self.atom_match(mydep,
                    mask_filter = False)
                if package_id != -1:
                    treelevel += 1
                    if treelevel not in maskedtree and not flat:
                        maskedtree[treelevel] = {}
                    dbconn = self.open_repository(repoid)
                    vpackage_id, idreason = dbconn.maskFilter(package_id)
                    if atoms:
                        mydict = {dbconn.retrieveAtom(package_id): idreason}
                    else:
                        mydict = {(package_id, repoid): idreason}

                    if flat:
                        maskedtree.update(mydict)
                    else:
                        maskedtree[treelevel].update(mydict)

            # push its dep into the buffer
            if package_id != -1:
                matchfilter.add((package_id, repoid))
                dbconn = self.open_repository(repoid)
                owndeps = dbconn.retrieveDependencies(package_id,
                    exclude_deptypes = excluded_deps)
                for owndep in owndeps:
                    mybuffer.push(owndep)

            try:
                mydep = mybuffer.pop()
            except ValueError:
                break # stack empty

        return maskedtree

    @sharedinstlock
    def check_package_update(self, atom, deep = False):

        inst_repo = self.installed_repository()
        cache_key = None

        if self.xcache:
            sha = hashlib.sha1()

            cache_s = "{%s;%s;%s;%s;%s;%s;%s}v5" % (
                atom,
                deep,
                inst_repo.checksum(),
                self.repositories_checksum(),
                self._settings.packages_configuration_hash(),
                self._settings_client_plugin.packages_configuration_hash(),
                ";".join(sorted(self._settings['repositories']['available'])),
                )
            sha.update(const_convert_to_rawstring(cache_s))

            cache_key = "check_update/package_update_%s" % (sha.hexdigest(),)

            cached = self._cacher.pop(cache_key)
            if cached is not None:
                return cached

        found = False
        pkg_id, pkg_rc = inst_repo.atomMatch(atom)
        matched = None
        if pkg_id != -1:
            myatom = inst_repo.retrieveAtom(pkg_id)
            mytag = entropy.dep.dep_gettag(myatom)
            myatom = entropy.dep.remove_tag(myatom)
            myrev = inst_repo.retrieveRevision(pkg_id)
            pkg_match = "="+myatom+"~"+str(myrev)
            if mytag is not None:
                pkg_match += "%s%s" % (etpConst['entropytagprefix'], mytag,)
            pkg_unsatisfied = self._get_unsatisfied_dependencies([pkg_match],
                deep_deps = deep)
            if pkg_unsatisfied:
                # does it really exist on current repos?
                pkg_key = entropy.dep.dep_getkey(myatom)
                f_pkg_id, pkg_repo = self.atom_match(pkg_key)
                if f_pkg_id != -1:
                    found = True
            matched = self.atom_match(pkg_match)

        if cache_key is not None:
            self._cacher.push(cache_key, (found, matched))

        return found, matched

    @sharedinstlock
    def validate_package_removal(self, package_id, repo_id = None):
        """
        Determine whether given package identifier is allowed to be removed.
        System packages or per-repository-specified ones (generally handled
        by repository admins) could be critical for the health of the system.
        If repo_id is None, package_id has to point to an installed package
        identifier. In general, this function works with every repository, not
        just the installed packages one.

        @param package_id: Entropy package identifier
        @type package_id: int
        @keyword repo_id: Entropy Repository identifier
        @type repo_id: string
        @return: return True, if package can be removed, otherwise False.
        @rtype: bool
        """

        if repo_id is None:
            dbconn = self.installed_repository()
        else:
            dbconn = self.open_repository(repo_id)

        pkgatom = dbconn.retrieveAtom(package_id)
        pkgkey = entropy.dep.dep_getkey(pkgatom)
        system_mask_data = self._get_installed_packages_system_mask()

        # cannot check this for pkgs not coming from installed pkgs repo
        if dbconn is self.installed_repository():
            if package_id in system_mask_data['ids']:
                package_ids = system_mask_data['keys'].get(pkgkey)
                if not package_ids:
                    return False
                if len(package_ids) > 1:
                    return True
                return False # sorry!

        def is_system_pkg():
            if dbconn.isSystemPackage(package_id):
                return True
            visited = set()
            reverse_deps = dbconn.retrieveReverseDependencies(package_id,
                key_slot = True)
            # with virtual packages, it can happen that system packages
            # are not directly marked as such. so, check direct inverse deps
            # and see if we find one
            for rev_pkg_key, rev_pkg_slot in reverse_deps:
                rev_pkg_id, rev_repo_id = self.atom_match(rev_pkg_key,
                    match_slot = rev_pkg_slot)
                if rev_pkg_id == -1:
                    # can't find
                    continue
                rev_repo_db = self.open_repository(rev_repo_id)
                if rev_repo_db.isSystemPackage(rev_pkg_id):
                    return True
            return False

        # did we store the bastard in the db?
        system_pkg = is_system_pkg()
        if not system_pkg:
            return True
        # check if the package is slotted and exist more
        # than one installed first
        matches, rc = dbconn.atomMatch(pkgkey, multiMatch = True)
        if len(matches) < 2:
            return False
        return True

    @sharedinstlock
    def get_masked_packages(self, package_matches):
        """
        Return a list of masked packages which are dependencies of given package
        matches.
        NOTE: dependencies are not sorted.

        @param package_matches: list of package matches coming from
            Client.atom_match()
        @type package_matches: list
        @return: dictionary composed by package match as key, and masking
            reason id as value (see etpConst['pkg_masking_reasons'] and
            etpConst['pkg_masking_reference']).
        @rtype: dict
        """
        matchfilter = set()
        masks = {}
        for match in package_matches:
            mymasks = self._get_masked_packages_tree(match, atoms = False,
                flat = True, matchfilter = matchfilter)
            masks.update(mymasks)
        return masks

    @sharedinstlock
    def get_removal_queue(self, package_identifiers, deep = False,
        recursive = True, empty = False, system_packages = True):
        """
        Return removal queue (list of installed packages identifiers).

        @param package_identifiers: list of package identifiers proposed
            for removal (returned by inst_repo.listAllPackageIds())
        @type package_identifiers: list
        @keyword deep: deeply scan inverse dependencies to include unused
            packages
        @type deep: bool
        @keyword recursive: scan inverse dependencies recursively, building
            a complete dependency graph
        @type recursive: bool
        @keyword empty: when used with "deep", includes more reverse
            dependencies, especially useful for the removal of virtual packages.
        @type empty: bool
        @keyword system_packages: exclude system packages from reverse
            dependencies
        @type system_packages: bool
        @return: list of installed package identifiers
        @rtype: list
        @raise DependenciesNotRemovable: if at least one reverse dependency
            is a system package and cannot be removed. The exception instance
            contains a "value" attribute providing a list of system package
            matches.
        """
        repo_name = InstalledPackagesRepository.NAME
        _package_ids = [(x, repo_name) for x in package_identifiers]
        treeview = self._generate_reverse_dependency_tree(_package_ids,
            deep = deep, recursive = recursive, empty = empty,
            system_packages = system_packages)
        queue = []
        for x in sorted(treeview, reverse = True):
            queue.extend(treeview[x])
        return [x for x, y in queue]

    @sharedinstlock
    def get_reverse_queue(self, package_matches, deep = False,
        recursive = True, empty = False, system_packages = True):
        """
        Return a list of reverse dependecies for given package matches.
        This method works for every repository, not just the installed packages
        one.

        @type deep: bool
        @keyword recursive: scan inverse dependencies recursively, building
            a complete dependency graph
        @type recursive: bool
        @keyword empty: when used with "deep", includes more reverse
            dependencies, especially useful for the removal of virtual packages.
        @type empty: bool
        @keyword system_packages: exclude system packages from reverse
            dependencies
        @type system_packages: bool
        @return: list of package matches
        @rtype: list
        @raise DependenciesNotRemovable: if at least one reverse dependency
            is a system package and cannot be removed. The exception instance
            contains a "value" attribute providing a list of system package
            matches.
        """
        treeview = self._generate_reverse_dependency_tree(package_matches,
            deep = deep, recursive = recursive, empty = empty,
            system_packages = system_packages)
        queue = []
        for x in sorted(treeview, reverse = True):
            queue.extend(treeview[x])
        return queue

    @sharedinstlock
    def get_install_queue(self, package_matches, empty, deep,
        relaxed = False, build = False, quiet = False, recursive = True,
        only_deps = False, critical_updates = True):
        """
        Return the ordered installation queue (including dependencies, if
        required), for given package matches.

        @param package_matches: list of package matches coming from
            Client.atom_match()
        @type package_matches: list
        @param empty: consider installed packages repository as empty, pull
            in the complete dependency graph
        @type empty: bool
        @param deep: deeply scan dependencies, also include "softly" satisfied
            dependencies.
        @type deep: bool
        @keyword relaxed: use relaxed dependencies resolution algorithm,
            ignoring possible binary libraries with only API bumps (and no ABI).
            By default, Entropy Client also pulls in package updates even when
            not strictly required by the related dependency string.
        @type relaxed: bool
        @keyword build: Also include build-time dependencies.
        @type build: bool
        @keyword quiet: do not print progress
        @type quiet: bool
        @keyword recursive: scan dependencies recursively (usually, this is
            the wanted behaviour)
        @type recursive: bool
        @keyword only_deps: only pull in package_matches dependencies and not
            themselves, unless they are also dependencies.
        @type only_deps: bool
        @keyword critical_updates: pull in critical updates if any
        @type critical_updates: bool
        @return: tuple composed by a list of package matches to install and
            a list of package matches to remove (informational)
        @raise DependenciesCollision: packages pulled in conflicting depedencies
            perhaps sharing the same key and slot (but different version).
            In this case, user should mask one or the other by hand.
            The value encapsulated .value object attribute contains the list of
            colliding package (list of lists).
        @raise DependenciesNotFound: one or more dependencies required are not
            found. The encapsulated .value object attribute contains a list of
            not found dependencies.
        """
        cl_settings = self.ClientSettings()
        misc_settings = cl_settings['misc']
        install = []
        removal = []
        # we don't know the input type, standardize to list()
        internal_matches = list(package_matches)

        def _filter_key_slot(pkg_matches):
            """
            Return True if pkg_match (through its
            key + slot) is already pulled in, in internal_matches
            """
            internal_matches_key_slot = set()
            internal_matches_set = set(internal_matches)

            # simple match filter, set is faster -> O(log n)
            pkg_matches = [x for x in pkg_matches if \
                               x not in internal_matches_set]

            for pkg_id, _repo_id in internal_matches_set:
                _key_slot = self.open_repository(_repo_id).retrieveKeySlot(
                    pkg_id)
                if _key_slot is not None:
                    internal_matches_key_slot.add(_key_slot)

            new_pkg_matches = []
            for pkg_match in pkg_matches:
                pkg_id, _repo_id = pkg_match
                _key_slot = self.open_repository(_repo_id).retrieveKeySlot(
                    pkg_id)
                # ignore None
                if _key_slot not in internal_matches_key_slot:
                    new_pkg_matches.append(pkg_match)

            if const_debug_enabled():
                const_debug_write(
                    __name__,
                    "get_install_queue(), "
                    "critical updates filtered: %s" % (new_pkg_matches,))

            return new_pkg_matches

        # critical updates hook, if enabled
        # this will force callers to receive only critical updates
        if misc_settings.get('forcedupdates') and critical_updates:
            upd_atoms, upd_matches = self.calculate_critical_updates(
                use_cache = self.xcache)
            if upd_matches:
                if const_debug_enabled():
                    const_debug_write(
                        __name__,
                        "get_install_queue(), "
                        "critical updates available: %s" % (upd_matches,))
                internal_matches += _filter_key_slot(upd_matches)

        try:
            deptree = self._get_required_packages(
                internal_matches, empty_deps = empty, deep_deps = deep,
                relaxed_deps = relaxed, only_deps = only_deps,
                build_deps = build, quiet = quiet, recursive = recursive)
        except DependenciesCollision as exc:
            # Packages pulled in conflicting dependencies, these sharing the
            # same key+slot. For example, repositories contain one or more
            # packages with key "www-servers/apache" and slot "2" and
            # user is requiring packages that require both. In this case,
            # user should mask one or the other by hand
            raise
        except DependenciesNotFound as exc:
            # One or more dependencies pulled in by packages are not
            # found in repositories
            raise

        # format
        removal = deptree.pop(0, set())
        for dep_level in sorted(deptree):
            install.extend(deptree[dep_level])

        # filter out packages that are in actionQueue comparing key + slot
        if install and removal:
            inst_repo = self.installed_repository()

            myremmatch = {}
            for rm_package_id in removal:
                keyslot = inst_repo.retrieveKeySlot(rm_package_id)
                # check if users removed package_id while this
                # whole instance is running
                if keyslot is None:
                    continue
                myremmatch[keyslot] = rm_package_id

            for pkg_id, pkg_repo in install:
                dbconn = self.open_repository(pkg_repo)
                testtuple = dbconn.retrieveKeySlot(pkg_id)
                removal.discard(myremmatch.get(testtuple))

        return install, sorted(removal)
