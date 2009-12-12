# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Dependency handling Interface}.

"""
from entropy.const import *
from entropy.exceptions import *
from entropy.graph import Graph
from entropy.misc import Lifo
from entropy.output import bold, darkgreen, darkred, blue, red, purple
from entropy.i18n import _

class CalculatorsMixin:

    def dependencies_test(self, dbconn = None):

        if dbconn == None:
            dbconn = self.clientDbconn
        # get all the installed packages
        installed_packages = dbconn.listAllIdpackages()

        pdepend_id = etpConst['dependency_type_ids']['pdepend_id']
        deps_not_matched = set()
        # now look
        length = len(installed_packages)
        count = 0
        for idpackage in installed_packages:
            count += 1

            if (count%150 == 0) or (count == length) or (count == 1):
                atom = dbconn.retrieveAtom(idpackage)
                self.updateProgress(
                    darkgreen(_("Checking %s") % (bold(atom),)),
                    importance = 0,
                    type = "info",
                    back = True,
                    count = (count, length),
                    header = darkred(" @@ ")
                )

            xdeps = dbconn.retrieveDependencies(idpackage,
                exclude_deptypes = (pdepend_id,))
            needed_deps = [(x, dbconn.atomMatch(x),) for x in xdeps]
            deps_not_matched |= set([x for x, (y, z,) in needed_deps if y == -1])

        return deps_not_matched

    def find_belonging_dependency(self, matched_atoms):
        crying_atoms = set()
        for atom in matched_atoms:
            for repo in self.validRepositories:
                rdbconn = self.open_repository(repo)
                riddep = rdbconn.searchDependency(atom)
                if riddep != -1:
                    ridpackages = rdbconn.searchIdpackageFromIddependency(riddep)
                    for i in ridpackages:
                        i, r = rdbconn.idpackageValidator(i)
                        if i == -1:
                            continue
                        iatom = rdbconn.retrieveAtom(i)
                        crying_atoms.add((iatom, repo))
        return crying_atoms

    def __handle_multi_repo_matches(self, results, extended_results, valid_repos, server_inst):

        packageInformation = {}
        versionInformation = {}
        # .tbz2 repos have always the precedence, so if we find them,
        # we should second what user wants, installing his tbz2
        tbz2repos = [x for x in results if x.endswith(etpConst['packagesext'])]
        if tbz2repos:
            del tbz2repos
            newrepos = results.copy()
            for x in newrepos:
                if x.endswith(etpConst['packagesext']):
                    continue
                del results[x]

        version_duplicates = set()
        versions = set()
        for repo in results:
            packageInformation[repo] = {}
            if extended_results:
                version = results[repo][1]
                packageInformation[repo]['versiontag'] = results[repo][2]
                packageInformation[repo]['revision'] = results[repo][3]
            else:
                dbconn = self.__atom_match_open_db(repo, server_inst)
                packageInformation[repo]['versiontag'] = dbconn.retrieveVersionTag(results[repo])
                packageInformation[repo]['revision'] = dbconn.retrieveRevision(results[repo])
                version = dbconn.retrieveVersion(results[repo])
            packageInformation[repo]['version'] = version
            versionInformation[version] = repo
            if version in versions:
                version_duplicates.add(version)
            versions.add(version)

        newerVersion = self.entropyTools.get_newer_version(list(versions))[0]
        # if no duplicates are found or newer version is not in duplicates we're done
        if (not version_duplicates) or (newerVersion not in version_duplicates):
            reponame = versionInformation.get(newerVersion)
            return (results[reponame], reponame)

        # we have two repositories with >two packages with the same version
        # check package tag

        conflictingEntries = {}
        tags_duplicates = set()
        tags = set()
        tagsInfo = {}
        for repo in packageInformation:
            if packageInformation[repo]['version'] != newerVersion:
                continue
            conflictingEntries[repo] = {}
            versiontag = packageInformation[repo]['versiontag']
            if versiontag in tags:
                tags_duplicates.add(versiontag)
            tags.add(versiontag)
            tagsInfo[versiontag] = repo
            conflictingEntries[repo]['versiontag'] = versiontag
            conflictingEntries[repo]['revision'] = packageInformation[repo]['revision']

        # tags will always be != []
        newerTag = sorted(tags, reverse = True)[0]
        if newerTag not in tags_duplicates:
            reponame = tagsInfo.get(newerTag)
            return (results[reponame], reponame)

        # in this case, we have >two packages with the same version and tag
        # check package revision

        conflictingRevisions = {}
        revisions = set()
        revisions_duplicates = set()
        revisionInfo = {}
        for repo in conflictingEntries:
            if conflictingEntries[repo]['versiontag'] == newerTag:
                conflictingRevisions[repo] = {}
                versionrev = conflictingEntries[repo]['revision']
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

    def __validate_atom_match_cache(self, cached_obj, multiMatch,
        extendedResults, multiRepo, server_inst):

        data, rc = cached_obj
        if rc == 1:
            return cached_obj

        if multiRepo or multiMatch:
            # set([(14789, 'sabayonlinux.org'), (14479, 'sabayonlinux.org')])
            matches = data
            if extendedResults:
                # set([((14789, '3.3.8b', '', 0), 'sabayonlinux.org')])
                matches = [(x[0][0], x[1],) for x in data]
            for m_id, m_repo in matches:
                m_db = self.__atom_match_open_db(m_repo, server_inst)
                if not m_db.isIdpackageAvailable(m_id):
                    return None
        else:
            # (14479, 'sabayonlinux.org')
            m_id, m_repo = cached_obj
            if extendedResults:
                # ((14479, '4.4.2', '', 0), 'sabayonlinux.org')
                m_id, m_repo = cached_obj[0][0], cached_obj[1]
            m_db = self.__atom_match_open_db(m_repo, server_inst)
            if not m_db.isIdpackageAvailable(m_id):
                return None

        return cached_obj

    def __atom_match_open_db(self, repoid, server_inst):
        if server_inst is not None:
            dbconn = server_inst.open_server_repository(just_reading = True,
                repo = repoid, do_treeupdates = False)
        else:
            dbconn = self.open_repository(repoid)
        return dbconn

    def atom_match(self, atom, caseSensitive = True, matchSlot = None,
            matchTag = None, packagesFilter = True,
            multiMatch = False, multiRepo = False, matchRevision = None,
            matchRepo = None, server_repos = [], serverInstance = None,
            extendedResults = False, useCache = True):

        # support match in repository from shell
        # atom@repo1,repo2,repo3
        atom, repos = self.entropyTools.dep_get_match_in_repos(atom)
        if (matchRepo == None) and (repos is not None):
            matchRepo = repos

        u_hash = ""
        k_ms = "//"
        k_mt = "@#@"
        k_mr = "-1"
        if isinstance(matchRepo, (list, tuple, set)):
            u_hash = hash(frozenset(matchRepo))
        if const_isstring(matchSlot):
            k_ms = matchSlot
        if const_isstring(matchTag):
            k_mt = matchTag
        if const_isstring(matchRevision):
            k_mr = matchRevision
        repos_ck = self.all_repositories_checksum()

        c_hash = "%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s" % (
            repos_ck,
            atom, k_ms, k_mt, hash(packagesFilter),
            hash(frozenset(self.validRepositories)),
            hash(frozenset(self.SystemSettings['repositories']['available'])),
            hash(multiMatch), hash(multiRepo), hash(caseSensitive),
            k_mr, hash(extendedResults),
            u_hash,
        )
        c_hash = "%s%s" % (self.atomMatchCacheKey, hash(c_hash),)

        if self.xcache and useCache:
            cached = self.Cacher.pop(c_hash)
            if cached is not None:
                try:
                    cached = self.__validate_atom_match_cache(cached,
                        multiMatch, extendedResults, multiRepo, serverInstance)
                except (TypeError, ValueError, IndexError, KeyError,):
                    cached = None
            if cached is not None:
                return cached

        if server_repos:
            if not serverInstance:
                t = _("server_repos needs serverInstance")
                raise IncorrectParameter("IncorrectParameter: %s" % (t,))
            valid_repos = server_repos[:]
        else:
            valid_repos = self.validRepositories
        if matchRepo and (type(matchRepo) in (list, tuple, set)):
            valid_repos = list(matchRepo)

        repoResults = {}
        for repo in valid_repos:

            # search
            dbconn = self.__atom_match_open_db(repo, serverInstance)
            use_cache = useCache
            while True:
                try:
                    query_data, query_rc = dbconn.atomMatch(
                        atom,
                        caseSensitive = caseSensitive,
                        matchSlot = matchSlot,
                        matchTag = matchTag,
                        packagesFilter = packagesFilter,
                        matchRevision = matchRevision,
                        extendedResults = extendedResults,
                        useCache = use_cache
                    )
                    if query_rc == 0:
                        # package found, add to our dictionary
                        if extendedResults:
                            repoResults[repo] = (query_data[0], query_data[2],
                                query_data[3], query_data[4])
                        else:
                            repoResults[repo] = query_data
                except TypeError:
                    if not use_cache:
                        raise
                    use_cache = False
                    continue
                except dbconn.dbapi2.OperationalError:
                    # repository fooked, skip!
                    break
                break

        dbpkginfo = (-1, 1)
        if extendedResults:
            dbpkginfo = ((-1, None, None, None), 1)

        if multiRepo and repoResults:

            data = set()
            for repoid in repoResults:
                data.add((repoResults[repoid], repoid))
            dbpkginfo = (data, 0)

        elif len(repoResults) == 1:
            # one result found
            repo = list(repoResults.keys())[0]
            dbpkginfo = (repoResults[repo], repo)

        elif len(repoResults) > 1:

            # we have to decide which version should be taken
            mypkginfo = self.__handle_multi_repo_matches(repoResults,
                extendedResults, valid_repos, serverInstance)
            if mypkginfo is not None:
                dbpkginfo = mypkginfo

        # multimatch support
        if multiMatch:

            if dbpkginfo[1] == 1:
                dbpkginfo = (set(), 1)
            else: # can be "0" or a string, but 1 means failure
                if multiRepo:
                    data = set()
                    for q_id, q_repo in dbpkginfo[0]:
                        dbconn = self.__atom_match_open_db(q_repo, serverInstance)
                        query_data, query_rc = dbconn.atomMatch(
                            atom,
                            caseSensitive = caseSensitive,
                            matchSlot = matchSlot,
                            matchTag = matchTag,
                            packagesFilter = packagesFilter,
                            multiMatch = True,
                            extendedResults = extendedResults
                        )
                        if extendedResults:
                            for item in query_data:
                                data.add(((item[0], item[2], item[3], item[4]), q_repo))
                        else:
                            for x in query_data: data.add((x, q_repo))
                    dbpkginfo = (data, 0)
                else:
                    dbconn = self.__atom_match_open_db(dbpkginfo[1], serverInstance)
                    query_data, query_rc = dbconn.atomMatch(
                        atom,
                        caseSensitive = caseSensitive,
                        matchSlot = matchSlot,
                        matchTag = matchTag,
                        packagesFilter = packagesFilter,
                        multiMatch = True,
                        extendedResults = extendedResults
                    )
                    if extendedResults:
                        dbpkginfo = (set([((x[0], x[2], x[3], x[4]), dbpkginfo[1]) \
                            for x in query_data]), 0)
                    else:
                        dbpkginfo = (set([(x, dbpkginfo[1]) for x in query_data]), 0)

        if self.xcache and useCache:
            self.Cacher.push(c_hash, dbpkginfo)

        return dbpkginfo

    # expands package sets, and in future something more perhaps
    def packages_expand(self, packages):
        new_packages = []

        for pkg_id in range(len(packages)):
            package = packages[pkg_id]

            # expand package sets
            if package.startswith(etpConst['packagesetprefix']):
                set_pkgs = sorted(self.package_set_expand(package, raise_exceptions = False))
                new_packages.extend([x for x in set_pkgs if x not in packages]) # atomMatch below will filter dupies
            else:
                new_packages.append(package)

        return new_packages

    def package_set_expand(self, package_set, raise_exceptions = True):

        max_recursion_level = 50
        recursion_level = 0

        def do_expand(myset, recursion_level, max_recursion_level):
            recursion_level += 1
            if recursion_level > max_recursion_level:
                raise InvalidPackageSet('InvalidPackageSet: corrupted, too many recursions: %s' % (myset,))
            set_data, set_rc = self.package_set_match(myset[len(etpConst['packagesetprefix']):])
            if not set_rc:
                raise InvalidPackageSet('InvalidPackageSet: not found: %s' % (myset,))
            (set_from, package_set, mydata,) = set_data

            mypkgs = set()
            for fset in mydata: # recursively
                if fset.startswith(etpConst['packagesetprefix']):
                    mypkgs |= do_expand(fset, recursion_level, max_recursion_level)
                else:
                    mypkgs.add(fset)

            return mypkgs

        if not package_set.startswith(etpConst['packagesetprefix']):
            package_set = "%s%s" % (etpConst['packagesetprefix'], package_set,)

        try:
            mylist = do_expand(package_set, recursion_level, max_recursion_level)
        except InvalidPackageSet:
            if raise_exceptions: raise
            mylist = set()

        return mylist

    def package_set_list(self, server_repos = [], serverInstance = None, matchRepo = None):
        return self.package_set_match('', matchRepo = matchRepo, server_repos = server_repos, serverInstance = serverInstance, search = True)[0]

    def package_set_search(self, package_set, server_repos = [], serverInstance = None, matchRepo = None):
        # search support
        if package_set == '*': package_set = ''
        return self.package_set_match(package_set, matchRepo = matchRepo, server_repos = server_repos, serverInstance = serverInstance, search = True)[0]

    def __package_set_match_open_db(self, repoid, server_inst):
        if server_inst is not None:
            dbconn = server_inst.open_server_repository(just_reading = True, repo = repoid)
        else:
            dbconn = self.open_repository(repoid)
        return dbconn

    def package_set_match(self, package_set, multiMatch = False,
        matchRepo = None, server_repos = [], serverInstance = None,
        search = False):

        # support match in repository from shell
        # set@repo1,repo2,repo3
        package_set, repos = self.entropyTools.dep_get_match_in_repos(
            package_set)
        if (matchRepo == None) and (repos is not None):
            matchRepo = repos

        if server_repos:
            if not serverInstance:
                t = _("server_repos needs serverInstance")
                raise IncorrectParameter("IncorrectParameter: %s" % (t,))
            valid_repos = server_repos[:]
        else:
            valid_repos = self.validRepositories

        if matchRepo and (type(matchRepo) in (list, tuple, set)):
            valid_repos = list(matchRepo)

        # if we search, we return all the matches available
        if search: multiMatch = True

        set_data = []

        while True:

            # check inside SystemSettings
            if not server_repos:
                sys_pkgsets = self.SystemSettings['system_package_sets']
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
                dbconn = self.__package_set_match_open_db(repoid,
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

    def _get_unsatisfied_dependencies(self, dependencies, deep_deps = False,
        relaxed_deps = False, depcache = None):

        # NOTE: to avoid user complaints, the magic toy is "relaxed_deps"

        if self.xcache:
            c_data = sorted(dependencies)
            client_checksum = self.clientDbconn.checksum()
            c_hash = hash("%s|%s|%s|%s" % (c_data, deep_deps,
                client_checksum, relaxed_deps,))
            c_hash = "%s%s" % (etpCache['filter_satisfied_deps'], c_hash,)
            cached = self.Cacher.pop(c_hash)
            if cached is not None:
                return cached

        const_debug_write(__name__,
            "_get_unsatisfied_dependencies (not cached, deep: %s) for => %s" % (
                deep_deps, dependencies,))

        # satisfied dependencies filter support
        # package.satisfied file support
        satisfied_kw = '__%s__satisfied_ids' % (__name__,)
        satisfied_data = self.SystemSettings.get(satisfied_kw)
        if satisfied_data is None:
            satisfied_list = self.SystemSettings['satisfied']
            tmp_satisfied_data = set()
            for atom in satisfied_list:
                matches, m_res = self.atom_match(atom, multiMatch = True,
                    packagesFilter = False, multiRepo = True)
                if m_res == 0:
                    tmp_satisfied_data |= matches
            satisfied_data = tmp_satisfied_data
            self.SystemSettings[satisfied_kw] = satisfied_data

        cdb_am = self.clientDbconn.atomMatch
        intf_error = self.dbapi2.InterfaceError
        cdb_getversioning = self.clientDbconn.getVersioningData
        cdb_retrieveBranch = self.clientDbconn.retrieveBranch
        cdb_retrieveDigest = self.clientDbconn.retrieveDigest
        etp_cmp = self.entropyTools.entropy_compare_versions
        etp_get_rev = self.entropyTools.dep_get_entropy_revision

        if depcache is None:
            depcache = {}

        def push_to_cache(dependency, is_unsat):
            # push to cache
            depcache[dependency] = is_unsat

        unsatisfied = set()
        for dependency in dependencies:

            if dependency in depcache:
                # already analized ?
                is_unsat = depcache[dependency]
                if is_unsat:
                    unsatisfied.add(dependency)
                const_debug_write(__name__,
                    "_get_unsatisfied_dependencies control cached for => %s" % (
                        dependency,))
                const_debug_write(__name__, "...")
                continue

            ### conflict
            if dependency.startswith("!"):
                idpackage, rc = cdb_am(dependency[1:])
                if idpackage != -1:
                    const_debug_write(__name__,
                        "_get_unsatisfied_dependencies conflict not found on system for => %s" % (
                            dependency,))
                    const_debug_write(__name__, "...")
                    unsatisfied.add(dependency)
                    push_to_cache(dependency, True)
                    continue

                const_debug_write(__name__, "...")
                push_to_cache(dependency, False)
                continue

            c_ids, c_rc = cdb_am(dependency, multiMatch = True)
            if c_rc != 0:
                const_debug_write(__name__,
                    "_get_unsatisfied_dependencies not satisfied on system for => %s" % (
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
            if c_ids and (not deep_deps) and (not do_rev_deep) and (relaxed_deps):
                const_debug_write(__name__,
                    "_get_unsatisfied_dependencies (force unsat) SATISFIED => %s" % (
                        dependency,))
                const_debug_write(__name__, "...")
                push_to_cache(dependency, False)
                continue

            r_id, r_repo = self.atom_match(dependency)
            if r_id == -1:
                const_debug_write(__name__,
                    "_get_unsatisfied_dependencies repository match not found for => %s" % (
                        dependency,))
                const_debug_write(__name__, "...")
                unsatisfied.add(dependency)
                push_to_cache(dependency, True)
                continue

            # satisfied dependencies filter support
            # package.satisfied file support
            if (r_id, r_repo,) in satisfied_data:
                push_to_cache(dependency, False)
                continue # satisfied

            dbconn = self.open_repository(r_repo)
            try:
                repo_pkgver, repo_pkgtag, repo_pkgrev = dbconn.getVersioningData(r_id)
                # note: read rationale below
                repo_digest = dbconn.retrieveDigest(r_id)
            except (intf_error, TypeError,):
                # package entry is broken
                const_debug_write(__name__,
                    "_get_unsatisfied_dependencies repository entry broken for match => %s" % (
                        (r_id, r_repo),))
                const_debug_write(__name__, "...")
                unsatisfied.add(dependency)
                push_to_cache(dependency, True)
                continue

            client_data = set()
            for c_id in c_ids:
                try:
                    installedVer, installedTag, installedRev = cdb_getversioning(c_id)
                    # note: read rationale below
                    installedDigest = cdb_retrieveDigest(c_id)
                except TypeError: # corrupted entry?
                    installedVer = "0"
                    installedTag = ''
                    installedRev = 0
                    installedDigest = None
                client_data.add((installedVer, installedTag, installedRev,
                    installedDigest,))

            # this is required for multi-slotted packages (like python)
            # and when people mix Entropy and Portage
            do_cont = False
            for installedVer, installedTag, installedRev, cdigest in client_data:

                vcmp = etp_cmp((repo_pkgver, repo_pkgtag, repo_pkgrev,),
                    (installedVer, installedTag, installedRev,))

                # check if both pkgs share the same branch and digest, this must
                # be done to avoid system inconsistencies across branch upgrades
                if (vcmp == 0) and (cdigest != repo_digest):
                    vcmp = 1

                if vcmp == 0:
                    const_debug_write(__name__,
                        "_get_unsatisfied_dependencies SATISFIED equals " + \
                            "(not cached, deep: %s) => %s" % (
                                deep_deps, dependency,))
                    const_debug_write(__name__, "...")
                    do_cont = True
                    push_to_cache(dependency, False)
                    break

                ver_tag_repo = (repo_pkgver, repo_pkgtag,)
                ver_tag_inst = (installedVer, installedTag,)
                rev_match = repo_pkgrev != installedRev

                if do_rev_deep and rev_match and (ver_tag_repo == ver_tag_inst):
                    # this is unsatisfied then, need to continue to exit from
                    # for cycle and add it to unsatisfied
                    continue

                if deep_deps:
                    # also this is clearly unsatisfied if deep is enabled
                    continue

                if (ver_tag_repo == ver_tag_inst) and rev_match:
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
            const_debug_write(__name__,
                "_get_unsatisfied_dependencies NOT SATISFIED (not cached, deep: %s) => %s" % (
                    deep_deps, dependency,))

            const_debug_write(__name__, "...")
            unsatisfied.add(dependency)
            push_to_cache(dependency, True)

        if self.xcache:
            self.Cacher.push(c_hash, unsatisfied)

        return unsatisfied

    def get_masked_packages_tree(self, match, atoms = False, flat = False,
        matchfilter = None):

        if not isinstance(matchfilter, set):
            matchfilter = set()

        maskedtree = {}
        mybuffer = Lifo()
        depcache = set()
        treelevel = -1

        match_id, match_repo = match

        mydbconn = self.open_repository(match_repo)
        myatom = mydbconn.retrieveAtom(match_id)
        idpackage, idreason = mydbconn.idpackageValidator(match_id)
        if idpackage == -1:
            treelevel += 1
            if atoms:
                mydict = {myatom: idreason,}
            else:
                mydict = {match: idreason,}
            if flat:
                maskedtree.update(mydict)
            else:
                maskedtree[treelevel] = mydict

        mydeps = mydbconn.retrieveDependencies(match_id)
        for mydep in mydeps: mybuffer.push(mydep)
        try:
            mydep = mybuffer.pop()
        except ValueError:
            mydep = None # stack empty

        open_db = self.open_repository
        am = self.atom_match
        while mydep:

            if mydep in depcache:
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    break # stack empty
                continue
            depcache.add(mydep)

            idpackage, repoid = am(mydep)
            if (idpackage, repoid) in matchfilter:
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    break # stack empty
                continue

            if idpackage != -1:
                # doing even here because atomMatch with packagesFilter = False can pull
                # something different
                matchfilter.add((idpackage, repoid))

            # collect masked
            if idpackage == -1:
                idpackage, repoid = am(mydep, packagesFilter = False)
                if idpackage != -1:
                    treelevel += 1
                    if treelevel not in maskedtree and not flat:
                        maskedtree[treelevel] = {}
                    dbconn = open_db(repoid)
                    vidpackage, idreason = dbconn.idpackageValidator(idpackage)
                    if atoms:
                        mydict = {dbconn.retrieveAtom(idpackage): idreason}
                    else:
                        mydict = {(idpackage, repoid): idreason}
                    if flat: maskedtree.update(mydict)
                    else: maskedtree[treelevel].update(mydict)

            # push its dep into the buffer
            if idpackage != -1:
                matchfilter.add((idpackage, repoid))
                dbconn = open_db(repoid)
                owndeps = dbconn.retrieveDependencies(idpackage)
                for owndep in owndeps:
                    mybuffer.push(owndep)

            try:
                mydep = mybuffer.pop()
            except ValueError:
                break # stack empty

        return maskedtree

    def __generate_dependency_tree_inst_hooks(self, installed_match, pkg_match,
        stack):

        broken_children_matches = self._lookup_library_drops(pkg_match,
            installed_match)

        broken_matches = self._lookup_library_breakages(pkg_match,
            installed_match)

        inverse_deps = self._lookup_inverse_dependencies(pkg_match,
            installed_match)
        for inv_match in inverse_deps:
            stack.push(inv_match)

        # broken children atoms can be added to broken atoms
        # and pulled into dep calculation
        broken_matches |= broken_children_matches
        for br_match in broken_matches:
            stack.push(br_match)

    def __generate_dependency_tree_analyze_conflict(self, conflict_str,
        conflicts, stack, deep_deps):

        conflict_atom = conflict_str[1:]
        c_idpackage, xst = self.clientDbconn.atomMatch(conflict_atom)
        if c_idpackage == -1:
            return # conflicting pkg is not installed

        confl_replacement = self._lookup_conflict_replacement(
            conflict_atom, c_idpackage, deep_deps = deep_deps)

        const_debug_write(__name__,
            "__generate_dependency_tree_analyze_conflict "
            "replacement => %s" % (confl_replacement,))

        if confl_replacement is not None:
            stack.push(confl_replacement)
            return

        # conflict is installed, we need to record it
        conflicts.add(c_idpackage)

    def __generate_dependency_tree_analyze_deplist(self, pkg_match, repo_db,
        stack, deps_not_found, conflicts, unsat_cache, relaxed_deps, deep_deps,
        empty_deps):

        pkg_id, repo_id = pkg_match
        myundeps = repo_db.retrieveDependenciesList(pkg_id)

        # check conflicts
        my_conflicts = set([x for x in myundeps if x.startswith("!")])
        if my_conflicts:
            myundeps -= my_conflicts
            for my_conflict in my_conflicts:
                self.__generate_dependency_tree_analyze_conflict(my_conflict,
                    conflicts, stack, deep_deps)

        const_debug_write(__name__,
            "__generate_dependency_tree_analyze_deplist filtered "
            "dependency list => %s" % (myundeps,))

        if not empty_deps:

            myundeps = self._get_unsatisfied_dependencies(myundeps,
                deep_deps = deep_deps, relaxed_deps = relaxed_deps,
                depcache = unsat_cache)

            const_debug_write(__name__,
                "__generate_dependency_tree_analyze_deplist " + \
                    "filtered UNSATISFIED dependencies => %s" % (myundeps,))

        post_deps = []
        # PDEPENDs support
        if myundeps:
            myundeps, post_deps = self._lookup_post_dependencies(repo_db,
                pkg_id, myundeps)

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
            stack.push((match_pkg_id, match_repo_id))

        post_deps_matches = set()
        for post_dep in post_deps:
            match_pkg_id, match_repo_id = self.atom_match(post_dep)
            # if post dependency is not found, we can happily ignore the fact
            if match_pkg_id == -1:
                # not adding to deps_not_found
                continue
            post_deps_matches.add((match_pkg_id, match_repo_id))
            stack.push((match_pkg_id, match_repo_id))

        return deps, post_deps_matches

    def _generate_dependency_tree(self, matched_atom, graph,
        empty_deps = False, relaxed_deps = False, deep_deps = False,
        unsatisfied_deps_cache = None, elements_cache = None):

        # this cache avoids adding the same element to graph
        # several times, when it is supposed to be already handled
        if elements_cache is None:
            elements_cache = set()
        if unsatisfied_deps_cache is None:
            unsatisfied_deps_cache = {}
        deps_not_found = set()
        conflicts = set()
        first_element = True

        stack = Lifo()
        stack.push(matched_atom)


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
            if first_element:
                first_element = False
                # we need to check if first element is masked because of
                # course, we don't trust function caller.
                mask_pkg_id, idreason = repo_db.idpackageValidator(pkg_id)
                if mask_pkg_id == -1:
                    mask_atom = repo_db.retrieveAtom(pkg_id)
                    if mask_atom is None:
                        mask_atom = 'N/A' # wtf?
                    deps_not_found.add(mask_atom)
                    continue # back to while

            # search inside installed packages repository if there's something
            # in the same slot, if so, do some extra checks first.
            pkg_key, pkg_slot = repo_db.retrieveKeySlot(pkg_id)
            cm_idpackage, cm_result = self.clientDbconn.atomMatch(pkg_key,
                matchSlot = pkg_slot)

            if cm_idpackage != -1:
                # this method does:
                # - broken libraries detection
                # - inverse dependencies check
                # - broken "dropped" libraries check (see _lookup_library_drops)
                self.__generate_dependency_tree_inst_hooks(
                    (cm_idpackage, cm_result), pkg_match, stack)

            dep_matches, post_dep_matches = \
                self.__generate_dependency_tree_analyze_deplist(
                    pkg_match, repo_db, stack, deps_not_found,
                    conflicts, unsatisfied_deps_cache,
                    relaxed_deps, deep_deps, empty_deps)

            # eventually add our package match to depgraph
            graph.add(pkg_match, dep_matches)
            for post_dep_match in post_dep_matches:
                graph.add(post_dep_match, set([pkg_match]))


        # if deps not found, we won't do dep-sorting at all
        if deps_not_found:
            del stack
            raise DependenciesNotFound(deps_not_found)

        return graph, conflicts

    def _lookup_post_dependencies(self, repo_db, repo_idpackage,
        unsatisfied_deps):

        post_deps = [x for x in \
            repo_db.retrievePostDependencies(repo_idpackage) if x \
            in unsatisfied_deps]

        const_debug_write(__name__,
            "_lookup_post_dependencies POST dependencies => %s" % (
                post_deps,))

        if post_deps:

            # do some filtering
            # it is correct to not use my_dep_filter here
            unsatisfied_deps = [x for x in unsatisfied_deps \
                if x not in post_deps]

        return unsatisfied_deps, post_deps


    def _lookup_system_mask_repository_deps(self):

        client_settings = self.SystemSettings[self.sys_settings_client_plugin_id]
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
                myaction = self.get_package_action(mymatch)
                # only if the package is not installed
                if myaction == 1:
                    mydata.append(mymatch)
            cached_items.add(mymatch)
        return mydata

    def _lookup_conflict_replacement(self, conflict_atom, client_idpackage, deep_deps):
        if self.entropyTools.isjustname(conflict_atom):
            return

        conflict_match = self.atom_match(conflict_atom)
        mykey, myslot = self.clientDbconn.retrieveKeySlot(client_idpackage)
        new_match = self.atom_match(mykey, matchSlot = myslot)
        if (conflict_match == new_match) or (new_match[1] == 1):
            return

        action = self.get_package_action(new_match)
        if (action == 0) and (not deep_deps):
            return

        return new_match

    def _lookup_inverse_dependencies(self, match, clientmatch):

        cmpstat = self.get_package_action(match)
        if cmpstat == 0:
            return set()

        keyslots_cache = set()
        match_cache = {}
        results = set()

        cdb_rdeps = self.clientDbconn.retrieveDependencies
        cdb_rks = self.clientDbconn.retrieveKeySlot
        gpa = self.get_package_action
        mydepends = \
            self.clientDbconn.retrieveReverseDependencies(clientmatch[0])

        for idpackage in mydepends:
            try:
                key, slot = cdb_rks(idpackage)
            except TypeError:
                continue

            if (key, slot) in keyslots_cache:
                continue
            keyslots_cache.add((key, slot))

            # grab its deps
            mydeps = cdb_rdeps(idpackage)
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
                mymatch = self.atom_match(key, matchSlot = slot)
                if mymatch[0] == -1:
                    continue
                cmpstat = gpa(mymatch)
                if cmpstat == 0:
                    continue
                results.add(mymatch)

        return results

    def _lookup_library_drops(self, match, client_match):

        match_id, match_repo = match
        match_db = self.open_repository(match_repo)
        repo_libs = match_db.retrieveProvidedLibraries(match_id)

        client_libs = self.clientDbconn.retrieveProvidedLibraries(
            client_match[0])
        removed_libs = set([x for x in client_libs if x not in repo_libs])

        idpackages = set()
        for lib, path, elf in removed_libs:
            idpackages |= self.clientDbconn.searchNeeded(lib, elfclass = elf)

        broken_matches = set()
        for c_idpackage in idpackages:

            keyslot = self.clientDbconn.retrieveKeySlotAggregated(c_idpackage)
            if keyslot is None:
                continue
            idpackage, repo = self.atom_match(keyslot)
            if idpackage == -1:
                continue

            cmpstat = self.get_package_action((idpackage, repo))
            if cmpstat == 0:
                continue

            broken_matches.add((idpackage, repo))

        return broken_matches


    def __get_lib_breaks_client_and_repo_side(self, match_db, match_idpackage,
        client_idpackage):

        soname = ".so"
        repo_needed = match_db.retrieveNeeded(match_idpackage,
            extended = True, format = True)
        client_needed = self.clientDbconn.retrieveNeeded(client_idpackage,
            extended = True, format = True)

        repo_split = [x.split(soname)[0] for x in repo_needed]
        client_split = [x.split(soname)[0] for x in client_needed]

        client_lib_dumps = set() # was client_side
        repo_lib_dumps = set() # was repo_side
        # ^^ library dumps using repository NEEDED metadata
        lib_removes = set()

        for lib in client_needed:
            if lib in repo_needed:
                continue
            lib_name = lib.split(soname)[0]
            if lib_name in repo_split:
                client_lib_dumps.add(lib)
            else:
                lib_removes.add(lib)

        for lib in repo_needed:
            if lib in client_needed:
                continue
            lib_name = lib.split(soname)[0]
            if lib_name in client_split:
                repo_lib_dumps.add(lib)

        return repo_needed, lib_removes, client_lib_dumps, repo_lib_dumps

    def _lookup_library_breakages(self, match, clientmatch):

        # there is no need to update this cache when "match"
        # will be installed, because at that point
        # clientmatch[0] will differ.
        c_hash = "%s|%s" % (
            match,
            clientmatch,
        )
        c_hash = "%s%s" % (etpCache['library_breakage'], hash(c_hash),)
        if self.xcache:
            cached = self.Cacher.pop(c_hash)
            if cached is not None:
                return cached

        matchdb = self.open_repository(match[1])
        reponeeded, lib_removes, client_side, repo_side = \
            self.__get_lib_breaks_client_and_repo_side(matchdb,
                match[0], clientmatch[0])

        # all the packages in client_side should be pulled in and updated
        client_idpackages = set()
        for needed in client_side:
            client_idpackages |= self.clientDbconn.searchNeeded(needed)

        client_keyslots = set()
        def mymf(idpackage):
            if idpackage == clientmatch[0]:
                return 0
            ks = self.clientDbconn.retrieveKeySlot(idpackage)
            if ks is None:
                return 0
            return ks
        client_keyslots = set([x for x in map(mymf, client_idpackages) \
            if x != 0])

        # all the packages in repo_side should be pulled in too
        repodata = {}
        for needed in repo_side:
            repodata[needed] = reponeeded[needed]
        del repo_side, reponeeded

        repo_dependencies = matchdb.retrieveDependencies(match[0])
        matched_deps = set()
        matched_repos = set()
        for dependency in repo_dependencies:
            depmatch = self.atom_match(dependency)
            if depmatch[0] == -1:
                continue
            matched_repos.add(depmatch[1])
            matched_deps.add(depmatch)

        matched_repos = [x for x in self.SystemSettings['repositories']['order'] \
            if x in matched_repos]
        found_matches = set()
        for needed in repodata:
            for myrepo in matched_repos:
                mydbc = self.open_repository(myrepo)
                solved_needed = mydbc.resolveNeeded(needed,
                    repodata[needed])
                found = False
                for idpackage in solved_needed:
                    x = (idpackage, myrepo)
                    if x in matched_deps:
                        found_matches.add(x)
                        found = True
                        break
                if found:
                    break

        # these should be pulled in before
        repo_matches = set()
        # these can be pulled in after
        client_matches = set()

        for idpackage, repo in found_matches:
            cmpstat = self.get_package_action((idpackage, repo))
            if cmpstat == 0:
                continue
            repo_matches.add((idpackage, repo))

        for key, slot in client_keyslots:
            idpackage, repo = self.atom_match(key, matchSlot = slot)
            if idpackage == -1:
                continue
            cmpstat = self.get_package_action((idpackage, repo))
            if cmpstat == 0:
                continue
            client_matches.add((idpackage, repo))

        client_matches |= repo_matches

        if self.xcache:
            self.Cacher.push(c_hash, client_matches)

        return client_matches

    def get_required_packages(self, matched_atoms, empty_deps = False,
        deep_deps = False, relaxed_deps = False, quiet = False):

        c_hash = "%s%s" % (
            etpCache['dep_tree'],
            hash("%s|%s|%s|%s|%s|%s" % (
                hash(frozenset(sorted(matched_atoms))),
                empty_deps,
                deep_deps,
                relaxed_deps,
                self.clientDbconn.checksum(),
                # needed when users do bogus things like editing config files
                # manually (branch setting)
                self.SystemSettings['repositories']['branch'],
        )),)
        if self.xcache:
            cached = self.Cacher.pop(c_hash)
            if cached is not None:
                return cached

        graph = Graph()
        deptree_conflicts = set()
        atomlen = len(matched_atoms); count = 0
        error_generated = 0
        error_tree = set()

        # check if there are repositories needing some mandatory packages
        forced_matches = self._lookup_system_mask_repository_deps()
        if forced_matches:
            if isinstance(matched_atoms, list):
                matched_atoms = forced_matches + [x for x in matched_atoms \
                    if x not in forced_matches]

            elif isinstance(matched_atoms, set):
                # we cannot do anything about the order here
                matched_atoms |= set(forced_matches)

        sort_dep_text = _("Sorting dependencies")
        unsat_deps_cache = {}
        elements_cache = set()
        matchfilter = set()
        for matched_atom in matched_atoms:

            const_debug_write(__name__,
                "get_required_packages matched_atom => %s" % (matched_atom,))

            if not quiet:
                count += 1
                if (count%10 == 0) or (count == atomlen) or (count == 1):
                    self.updateProgress(sort_dep_text, importance = 0,
                        type = "info", back = True, header = ":: ",
                        footer = " ::", percent = True,
                        count = (count, atomlen)
                    )

            if matched_atom in matchfilter:
                continue

            try:
                mygraph, conflicts = self._generate_dependency_tree(
                    matched_atom, graph, empty_deps = empty_deps,
                    deep_deps = deep_deps, relaxed_deps = relaxed_deps,
                    unsatisfied_deps_cache = unsat_deps_cache,
                    elements_cache = elements_cache
                )
            except DependenciesNotFound as err:
                error_generated = -2
                error_tree |= err.value
                conflicts = set()

            deptree_conflicts |= conflicts

        if error_generated != 0:
            del graph
            return error_tree, error_generated

        # solve depgraph and append conflicts
        deptree = graph.solve()
        if 0 in deptree:
            del graph
            raise KeyError("Graph contains a dep_level == 0")

        # reverse ketys in deptree, this allows correct order (not inverse)
        level_count = 0
        reverse_tree = {}
        for key in sorted(deptree.keys(), reverse = True):
            level_count += 1
            reverse_tree[level_count] = deptree[key]

        del deptree, graph
        reverse_tree[0] = deptree_conflicts

        if self.xcache:
            self.Cacher.push(c_hash, (reverse_tree, 0))

        return reverse_tree, 0

    def _filter_depends_multimatched_atoms(self, idpackage, depends):

        remove_depends = set()
        for d_idpackage in depends:
            mydeps = self.clientDbconn.retrieveDependencies(d_idpackage)
            for mydep in mydeps:

                matches, rslt = self.clientDbconn.atomMatch(mydep,
                    multiMatch = True)
                if rslt == 1:
                    continue

                if idpackage in matches and len(matches) > 1:
                    # are all in depends?
                    for mymatch in matches:
                        if mymatch not in depends:
                            remove_depends.add(d_idpackage)
                            break

        depends -= remove_depends
        return depends

    def generate_depends_tree(self, idpackages, deep = False):

        c_hash = "%s%s" % (
            etpCache['depends_tree'],
            hash("%s|%s" % (
                    tuple(sorted(idpackages)),
                    deep,
                ),
            ),
        )
        if self.xcache:
            cached = self.Cacher.pop(c_hash)
            # XXX drop old cache object format
            if not isinstance(cached, dict):
                cached = None
            if cached is not None:
                return cached

        count = 0
        match_cache = set()
        stack = Lifo()
        graph = Graph()

        # post-dependencies won't be pulled in
        pdepend_id = etpConst['dependency_type_ids']['pdepend_id']
        rem_dep_text = _("Calculating inverse dependencies for")
        for idpackage in idpackages:
            stack.push(idpackage)

        while stack.is_filled():

            idpackage = stack.pop()
            if idpackage in match_cache:
                # already analyzed
                continue
            match_cache.add(idpackage)

            system_pkg = not self.validate_package_removal(idpackage)
            if system_pkg:
                # this is a system package, removal forbidden
                continue

            count += 1
            p_atom = self.clientDbconn.retrieveAtom(idpackage)
            self.updateProgress(
                blue(rem_dep_text + " %s" % (purple(p_atom),)),
                importance = 0,
                type = "info",
                back = True,
                header = '|/-\\'[count%4]+" "
            )

            # obtain its inverse deps
            reverse_deps = self.clientDbconn.retrieveReverseDependencies(
                idpackage, exclude_deptypes = (pdepend_id,))
            if reverse_deps:
                reverse_deps = self._filter_depends_multimatched_atoms(
                    idpackage, reverse_deps)

            if deep:

                mydeps = set()
                for x in self.clientDbconn.retrieveDependencies(idpackage):
                    match = self.clientDbconn.atomMatch(x)
                    if match[0] != -1:
                        mydeps.add(match[0])

                # now filter them
                mydeps = [x for x in mydeps if not \
                    (self.clientDbconn.isSystemPackage(x) or \
                        self.is_installed_idpackage_in_system_mask(x) )]

                for x in mydeps:
                    mydepends = self.clientDbconn.retrieveReverseDependencies(x)
                    if not mydepends:
                        reverse_deps.add(x)

            for rev_dep in reverse_deps:
                stack.push(rev_dep)
            graph.add(idpackage, reverse_deps)


        del stack
        deptree = graph.solve()
        del graph

        if self.xcache:
            self.Cacher.push(c_hash, deptree)
        return deptree

    def calculate_available_packages(self, use_cache = True):

        c_hash = self.get_available_packages_chash()
        if use_cache and self.xcache:
            cached = self.get_available_packages_cache(myhash = c_hash)
            if cached is not None:
                return cached

        available = []
        self.setTotalCycles(len(self.validRepositories))
        avail_dep_text = _("Calculating available packages for")
        for repo in self.validRepositories:
            try:
                dbconn = self.open_repository(repo)
                dbconn.validateDatabase()
            except (RepositoryError, SystemDatabaseError):
                self.cycleDone()
                continue
            try:
                # db may be corrupted, we cannot deal with it here
                idpackages = [x for x in dbconn.listAllIdpackages(
                    order_by = 'atom') if dbconn.idpackageValidator(x)[0] != -1]
            except dbconn.dbapi2.OperationalError:
                self.cycleDone()
                continue
            count = 0
            maxlen = len(idpackages)
            myavailable = []
            do_break = False
            for idpackage in idpackages:
                if do_break:
                    break
                count += 1
                if (count % 10 == 0) or (count == 1) or (count == maxlen):
                    self.updateProgress(
                        avail_dep_text + " %s" % (repo,),
                        importance = 0,
                        type = "info",
                        back = True,
                        header = "::",
                        count = (count, maxlen),
                        percent = True,
                        footer = " ::"
                    )
                # get key + slot
                try:
                    key, slot = dbconn.retrieveKeySlot(idpackage)
                    matches = self.clientDbconn.searchKeySlot(key, slot)
                except (self.dbapi2.DatabaseError, self.dbapi2.IntegrityError, self.dbapi2.OperationalError,):
                    self.cycleDone()
                    do_break = True
                    continue
                if not matches: myavailable.append((idpackage, repo))
            available += myavailable[:]
            self.cycleDone()

        if self.xcache:
            self.Cacher.push("%s%s" % (
                etpCache['world_available'], c_hash), available)
        return available

    def calculate_critical_updates(self, use_cache = True):

        # check if we are branch migrating
        # in this case, critical pkgs feature is disabled
        in_branch_upgrade = etpConst['etp_in_branch_upgrade_file']
        if os.access(in_branch_upgrade, os.R_OK) and \
            os.path.isfile(in_branch_upgrade):
            return set(), []

        db_digest = self.all_repositories_checksum()
        if use_cache and self.xcache:
            cached = self.get_critical_updates_cache(db_digest = db_digest)
            if cached is not None:
                return cached

        client_settings = self.SystemSettings[self.sys_settings_client_plugin_id]
        critical_data = client_settings['repositories']['critical_updates']

        atoms = set()
        atom_matches = {}
        for repoid in critical_data:
            for atom in critical_data[repoid]:
                match_id, match_repo = self.atom_match(atom)
                if match_repo == 1:
                    continue
                atom_matches[atom] = (match_id, match_repo,)
                atoms.add(atom)

        atoms = self._get_unsatisfied_dependencies(atoms)
        matches = [atom_matches.get(atom) for atom in atoms]
        data = (atoms, matches)

        if self.xcache:
            c_hash = self.get_critical_update_cache_hash(db_digest)
            self.Cacher.push("%s%s" % (etpCache['critical_update'], c_hash,),
                data, async = False)

        return data


    def calculate_world_updates(self, empty_deps = False, use_cache = True,
        critical_updates = True):

        cl_settings = self.SystemSettings[self.sys_settings_client_plugin_id]
        misc_settings = cl_settings['misc']
        update = []
        remove = []
        fine = []
        spm_fine = []

        # critical updates hook, if enabled
        # this will force callers to receive only critical updates
        if misc_settings.get('forcedupdates') and critical_updates:
            upd_atoms, upd_matches = self.calculate_critical_updates(
                use_cache = use_cache)
            if upd_atoms:
                return upd_matches, remove, fine, spm_fine

        db_digest = self.all_repositories_checksum()
        if use_cache and self.xcache:
            cached = self.get_world_update_cache(empty_deps = empty_deps,
                db_digest = db_digest)
            if cached is not None:
                return cached


        ignore_spm_downgrades = misc_settings['ignore_spm_downgrades']

        # get all the installed packages
        try:
            idpackages = self.clientDbconn.listAllIdpackages(order_by = 'atom')
        except self.dbapi2.OperationalError:
            # client db is broken!
            raise SystemDatabaseError("installed packages database is broken")

        maxlen = len(idpackages)
        count = 0
        mytxt = _("Calculating world packages")
        for idpackage in idpackages:

            count += 1
            if (count%10 == 0) or (count == maxlen) or (count == 1):
                self.updateProgress(
                    mytxt,
                    importance = 0,
                    type = "info",
                    back = True,
                    header = ":: ",
                    count = (count, maxlen),
                    percent = True,
                    footer = " ::"
                )

            try:
                cl_pkgkey, cl_slot, cl_version, \
                    cl_tag, cl_revision, \
                    cl_atom = self.clientDbconn.getStrictData(idpackage)
            except TypeError:
                # check against broken entries, or removed during iteration
                continue
            use_match_cache = True
            do_continue = False
            while True:
                try:
                    match = self.atom_match(
                        cl_pkgkey,
                        matchSlot = cl_slot,
                        extendedResults = True,
                        useCache = use_match_cache
                    )
                except self.dbapi2.OperationalError:
                    # ouch, but don't crash here
                    do_continue = True
                    break
                try:
                    m_idpackage = match[0][0]
                except TypeError:
                    if not use_match_cache: raise
                    use_match_cache = False
                    continue
                break
            if do_continue: continue
            # now compare
            # version: cl_version
            # tag: cl_tag
            # revision: cl_revision
            if (m_idpackage != -1):
                repoid = match[1]
                version = match[0][1]
                tag = match[0][2]
                revision = match[0][3]
                if empty_deps:
                    if (m_idpackage, repoid) not in update:
                        update.append((m_idpackage, repoid))
                    continue
                elif (cl_revision != revision):
                    # different revision
                    if cl_revision == 9999 and ignore_spm_downgrades:
                        # no difference, we're ignoring revision 9999
                        fine.append(cl_atom)
                        if (m_idpackage, repoid) not in update:
                            spm_fine.append((m_idpackage, repoid))
                        continue
                    else:
                        if (m_idpackage, repoid) not in update:
                            update.append((m_idpackage, repoid))
                        continue
                elif (cl_version != version):
                    # different versions
                    if (m_idpackage, repoid) not in update:
                        update.append((m_idpackage, repoid))
                    continue
                elif (cl_tag != tag):
                    # different tags
                    if (m_idpackage, repoid) not in update:
                        update.append((m_idpackage, repoid))
                    continue
                else:

                    # Note: this is a bugfix to improve branch migration
                    # and really check if pkg has been repackaged
                    # first check branch
                    if idpackage is not None:

                        c_repodb = self.open_repository(repoid)
                        c_digest = self.clientDbconn.retrieveDigest(idpackage)
                        r_digest = c_repodb.retrieveDigest(m_idpackage)

                        if (r_digest != c_digest) and (r_digest is not None) \
                            and (c_digest is not None):
                            if (m_idpackage, repoid) not in update:
                                update.append((m_idpackage, repoid))
                            continue

                    # no difference
                    fine.append(cl_atom)
                    continue

            # don't take action if it's just masked
            maskedresults = self.atom_match(cl_pkgkey, matchSlot = cl_slot,
                packagesFilter = False)
            if maskedresults[0] == -1:
                remove.append(idpackage)
                # look for packages that would match key
                # with any slot (for eg: gcc, kernel updates)
                matchresults = self.atom_match(cl_pkgkey)
                if matchresults[0] != -1:
                    m_action = self.get_package_action(matchresults)
                    if m_action > 0 and (matchresults not in update):
                        update.append(matchresults)

        if self.xcache:
            c_hash = self.get_world_update_cache_hash(db_digest, empty_deps,
                ignore_spm_downgrades)
            data = (update, remove, fine, spm_fine,)
            self.Cacher.push("%s%s" % (etpCache['world_update'], c_hash,),
                data, async = False)

        if not update:
            # delete branch upgrade file if exists, since there are
            # no updates, this file does not deserve to be saved anyway
            br_path = etpConst['etp_in_branch_upgrade_file']
            if os.access(br_path, os.W_OK) and os.path.isfile(br_path):
                os.remove(br_path)

        return update, remove, fine, spm_fine

    def check_package_update(self, atom, deep = False):

        c_hash = "%s%s" % (etpCache['check_package_update'],
                hash("%s%s" % (atom, deep,)
            ),
        )
        if self.xcache:
            cached = self.Cacher.pop(c_hash)
            if cached is not None:
                return cached

        found = False
        match = self.clientDbconn.atomMatch(atom)
        matched = None
        if match[0] != -1:
            myatom = self.clientDbconn.retrieveAtom(match[0])
            mytag = self.entropyTools.dep_gettag(myatom)
            myatom = self.entropyTools.remove_tag(myatom)
            myrev = self.clientDbconn.retrieveRevision(match[0])
            pkg_match = "="+myatom+"~"+str(myrev)
            if mytag is not None:
                pkg_match += "#%s" % (mytag,)
            pkg_unsatisfied = self._get_unsatisfied_dependencies([pkg_match],
                deep_deps = deep)
            if pkg_unsatisfied:
                # does it really exist on current repos?
                pkg_key = self.entropyTools.dep_getkey(myatom)
                pkg_id, pkg_repo = self.atom_match(pkg_key)
                if pkg_id != -1:
                    found = True
            del pkg_unsatisfied
            matched = self.atom_match(pkg_match)
        del match

        if self.xcache:
            self.Cacher.push(c_hash, (found, matched))
        return found, matched

    def validate_package_removal(self, idpackage):

        pkgatom = self.clientDbconn.retrieveAtom(idpackage)
        pkgkey = self.entropyTools.dep_getkey(pkgatom)
        client_settings = self.SystemSettings[self.sys_settings_client_plugin_id]
        mask_installed_keys = client_settings['system_mask']['repos_installed_keys']

        if self.is_installed_idpackage_in_system_mask(idpackage):
            idpackages = mask_installed_keys.get(pkgkey)
            if not idpackages: return False
            if len(idpackages) > 1:
                return True
            return False # sorry!

        # did we store the bastard in the db?
        system_pkg = self.clientDbconn.isSystemPackage(idpackage)
        if not system_pkg: return True
        # check if the package is slotted and exist more than one installed first
        matches, rc = self.clientDbconn.atomMatch(pkgkey, multiMatch = True)
        if len(matches) < 2:
            return False
        return True


    def get_removal_queue(self, idpackages, deep = False):
        queue = []
        if not idpackages:
            return queue
        treeview = self.generate_depends_tree(idpackages, deep = deep)
        for x in sorted(treeview, reverse = True):
            queue.extend(treeview[x])
        return queue

    def get_install_queue(self, matched_atoms, empty_deps, deep_deps,
        relaxed_deps = False, quiet = False):

        install = []
        removal = []
        treepackages, result = self.get_required_packages(matched_atoms,
            empty_deps = empty_deps, deep_deps = deep_deps,
            relaxed_deps = relaxed_deps, quiet = quiet)

        if result == -2:
            return treepackages, removal, result

        # format
        removal = treepackages.pop(0, set())
        for dep_level in sorted(treepackages):
            install.extend(treepackages[dep_level])

        # filter out packages that are in actionQueue comparing key + slot
        if install and removal:
            myremmatch = {}
            for rm_idpackage in removal:
                keyslot = self.clientDbconn.retrieveKeySlot(rm_idpackage)
                # check if users removed idpackage while this
                # whole instance is running
                if keyslot is None:
                    continue
                myremmatch[keyslot] = rm_idpackage

            for pkg_id, pkg_repo in install:
                dbconn = self.open_repository(pkg_repo)
                testtuple = dbconn.retrieveKeySlot(pkg_id)
                removal.discard(myremmatch.get(testtuple))

        return install, sorted(removal), 0

