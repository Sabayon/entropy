# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client Dependency handling Interface}.

"""
from entropy.misc import Lifo
from entropy.const import *
from entropy.exceptions import *
from entropy.output import bold, darkgreen, darkred, blue, red
from entropy.i18n import _

class CalculatorsMixin:

    def dependencies_test(self, dbconn = None):

        if dbconn == None:
            dbconn = self.clientDbconn
        # get all the installed packages
        installed_packages = dbconn.listAllIdpackages()

        pdepend_id = etpConst['spm']['pdepend_id']
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
                    count = (count,length),
                    header = darkred(" @@ ")
                )

            xdeps = dbconn.retrieveDependencies(idpackage,
                exclude_deptypes = (pdepend_id,))
            needed_deps = [(x,dbconn.atomMatch(x),) for x in xdeps]
            deps_not_matched |= set([x for x,(y,z,) in needed_deps if y == -1])

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
                        i,r = rdbconn.idpackageValidator(i)
                        if i == -1:
                            continue
                        iatom = rdbconn.retrieveAtom(i)
                        crying_atoms.add((iatom,repo))
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
            return (results[reponame],reponame)

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
        newerTag = sorted(list(tags), reverse = True)[0]
        if newerTag not in tags_duplicates:
            reponame = tagsInfo.get(newerTag)
            return (results[reponame],reponame)

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
            return (results[reponame],reponame)

        # final step, in this case we have >two packages with the same version, tag and revision
        # get the repository with the biggest priority

        for reponame in valid_repos:
            if reponame in conflictingRevisions:
                return (results[reponame],reponame)

    def __validate_atom_match_cache(self, cached_obj, multiMatch, extendedResults, multiRepo, server_inst):

        data, rc = cached_obj
        if rc == 1: return cached_obj

        if multiRepo or multiMatch:
            matches = data # set([(14789, 'sabayonlinux.org'), (14479, 'sabayonlinux.org')])
            if extendedResults:
                # set([((14789, u'3.3.8b', u'', 0), 'sabayonlinux.org')])
                matches = [(x[0][0],x[1],) for x in data]
            for m_id, m_repo in matches:
                m_db = self.__atom_match_open_db(m_repo, server_inst)
                if not m_db.isIdpackageAvailable(m_id):
                    return None
        else:
            m_id, m_repo = cached_obj # (14479, 'sabayonlinux.org')
            if extendedResults:
                # ((14479, u'4.4.2', u'', 0), 'sabayonlinux.org')
                m_id, m_repo = cached_obj[0][0],cached_obj[1]
            m_db = self.__atom_match_open_db(m_repo, server_inst)
            if not m_db.isIdpackageAvailable(m_id):
                return None

        return cached_obj

    def __atom_match_open_db(self, repoid, server_inst):
        if server_inst != None:
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
        if (matchRepo == None) and (repos != None):
            matchRepo = repos

        u_hash = ""
        k_ms = "//"
        k_mt = "@#@"
        k_mr = "-1"
        if isinstance(matchRepo,(list,tuple,set)):
            u_hash = hash(frozenset(matchRepo))
        if isinstance(matchSlot,basestring):
            k_ms = matchSlot
        if isinstance(matchTag,basestring):
            k_mt = matchTag
        if isinstance(matchRevision,basestring):
            k_mr = matchRevision

        c_hash = "|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s" % (
            atom,k_ms,k_mt,hash(packagesFilter),
            hash(frozenset(self.validRepositories)),
            hash(frozenset(self.SystemSettings['repositories']['available'])),
            hash(multiMatch),hash(multiRepo),hash(caseSensitive),
            k_mr,hash(extendedResults),
            u_hash,
        )
        c_hash = "%s%s" % (self.atomMatchCacheKey,hash(c_hash),)

        if self.xcache and useCache:
            cached = self.Cacher.pop(c_hash)
            if cached != None:
                try:
                    cached = self.__validate_atom_match_cache(cached, multiMatch, extendedResults, multiRepo, serverInstance)
                except (TypeError,ValueError,IndexError,KeyError,):
                    cached = None
            if cached != None:
                return cached

        if server_repos:
            if not serverInstance:
                t = _("server_repos needs serverInstance")
                raise IncorrectParameter("IncorrectParameter: %s" % (t,))
            valid_repos = server_repos[:]
        else:
            valid_repos = self.validRepositories
        if matchRepo and (type(matchRepo) in (list,tuple,set)):
            valid_repos = list(matchRepo)

        repoResults = {}
        for repo in valid_repos:

            # search
            dbconn = self.__atom_match_open_db(repo, serverInstance)
            use_cache = useCache
            while 1:
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
                            repoResults[repo] = (query_data[0],query_data[2],query_data[3],query_data[4])
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

        dbpkginfo = (-1,1)
        if extendedResults:
            dbpkginfo = ((-1,None,None,None),1)

        if multiRepo and repoResults:

            data = set()
            for repoid in repoResults:
                data.add((repoResults[repoid],repoid))
            dbpkginfo = (data,0)

        elif len(repoResults) == 1:
            # one result found
            repo = list(repoResults.keys())[0]
            dbpkginfo = (repoResults[repo],repo)

        elif len(repoResults) > 1:

            # we have to decide which version should be taken
            mypkginfo = self.__handle_multi_repo_matches(repoResults, extendedResults, valid_repos, serverInstance)
            if mypkginfo != None: dbpkginfo = mypkginfo

        # multimatch support
        if multiMatch:

            if dbpkginfo[1] == 1:
                dbpkginfo = (set(), 1)
            else: # can be "0" or a string, but 1 means failure
                if multiRepo:
                    data = set()
                    for q_id,q_repo in dbpkginfo[0]:
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
                                data.add(((item[0],item[2],item[3],item[4]),q_repo))
                        else:
                            for x in query_data: data.add((x,q_repo))
                    dbpkginfo = (data,0)
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
                        dbpkginfo = (set([((x[0],x[2],x[3],x[4]),dbpkginfo[1]) for x in query_data]),0)
                    else:
                        dbpkginfo = (set([(x,dbpkginfo[1]) for x in query_data]),0)

        if self.xcache and useCache:
            self.Cacher.push(c_hash,dbpkginfo)

        return dbpkginfo

    # expands package sets, and in future something more perhaps
    def packages_expand(self, packages):
        new_packages = []

        for pkg_id in range(len(packages)):
            package = packages[pkg_id]

            # expand package sets
            if package.startswith(etpConst['packagesetprefix']):
                set_pkgs = sorted(list(self.package_set_expand(package, raise_exceptions = False)))
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
            package_set = "%s%s" % (etpConst['packagesetprefix'],package_set,)

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
        if server_inst != None:
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
        if (matchRepo == None) and (repos != None):
            matchRepo = repos

        if server_repos:
            if not serverInstance:
                t = _("server_repos needs serverInstance")
                raise IncorrectParameter("IncorrectParameter: %s" % (t,))
            valid_repos = server_repos[:]
        else:
            valid_repos = self.validRepositories

        if matchRepo and (type(matchRepo) in (list,tuple,set)):
            valid_repos = list(matchRepo)

        # if we search, we return all the matches available
        if search: multiMatch = True

        set_data = []

        while 1:

            # check inside SystemSettings
            if not server_repos:
                sys_pkgsets = self.SystemSettings['system_package_sets']
                if search:
                    mysets = [x for x in list(sys_pkgsets.keys()) if \
                        (x.find(package_set) != -1)]
                    for myset in mysets:
                        mydata = sys_pkgsets.get(myset)
                        set_data.append((etpConst['userpackagesetsid'],
                            unicode(myset), mydata.copy(),))
                else:
                    mydata = sys_pkgsets.get(package_set)
                    if mydata is not None:
                        set_data.append((etpConst['userpackagesetsid'],
                            unicode(package_set), mydata,))
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
            return (),False

        if multiMatch:
            return set_data,True

        return set_data.pop(0),True

    def get_unsatisfied_dependencies(self, dependencies, deep_deps = False, depcache = None):

        if self.xcache:
            c_data = sorted(dependencies)
            client_checksum = self.clientDbconn.checksum()
            c_hash = hash("%s|%s|%s" % (c_data,deep_deps,client_checksum,))
            c_hash = "%s%s" % (etpCache['filter_satisfied_deps'],c_hash,)
            cached = self.Cacher.pop(c_hash)
            if cached != None: return cached

        const_debug_write(__name__,
            "get_unsatisfied_dependencies (not cached, deep: %s) for => %s" % (
                deep_deps, dependencies,))

        if not isinstance(depcache,dict):
            depcache = {}

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
        am = self.atom_match
        open_repo = self.open_repository
        intf_error = self.dbapi2.InterfaceError
        cdb_getversioning = self.clientDbconn.getVersioningData
        cdb_retrieveBranch = self.clientDbconn.retrieveBranch
        cdb_retrieveDigest = self.clientDbconn.retrieveDigest
        etp_cmp = self.entropyTools.entropy_compare_versions
        etp_get_rev = self.entropyTools.dep_get_entropy_revision

        def fm_dep(dependency):

            cached = depcache.get(dependency)
            if cached != None:
                const_debug_write(__name__,
                    "get_unsatisfied_dependencies control cached for => %s" % (
                        dependency,))
                const_debug_write(__name__, "...")
                return cached

            ### conflict
            if dependency.startswith("!"):
                idpackage,rc = cdb_am(dependency[1:])
                if idpackage != -1:
                    depcache[dependency] = dependency
                    const_debug_write(__name__,
                        "get_unsatisfied_dependencies conflict not found on system for => %s" % (
                            dependency,))
                    const_debug_write(__name__, "...")
                    return dependency
                depcache[dependency] = 0
                const_debug_write(__name__, "...")
                return 0

            c_ids, c_rc = cdb_am(dependency, multiMatch = True)
            if c_rc != 0:
                depcache[dependency] = dependency
                const_debug_write(__name__,
                    "get_unsatisfied_dependencies not satisfied on system for => %s" % (
                        dependency,))
                const_debug_write(__name__, "...")
                return dependency

            r_id, r_repo = am(dependency)
            if r_id == -1:
                depcache[dependency] = dependency
                const_debug_write(__name__,
                    "get_unsatisfied_dependencies repository match not found for => %s" % (
                        dependency,))
                const_debug_write(__name__, "...")
                return dependency

            # satisfied dependencies filter support
            # package.satisfied file support
            if (r_id, r_repo,) in satisfied_data:
                return 0 # satisfied

            dbconn = open_repo(r_repo)
            try:
                repo_pkgver, repo_pkgtag, repo_pkgrev = dbconn.getVersioningData(r_id)
                # note: read rationale below
                repo_branch = dbconn.retrieveBranch(r_id)
                repo_digest = dbconn.retrieveDigest(r_id)
            except (intf_error, TypeError,):
                # package entry is broken
                const_debug_write(__name__,
                    "get_unsatisfied_dependencies repository entry broken for match => %s" % (
                        (r_id, r_repo),))
                const_debug_write(__name__, "...")
                return dependency

            client_data = set()
            for c_id in c_ids:
                try:
                    installedVer, installedTag, installedRev = cdb_getversioning(c_id)
                    # note: read rationale below
                    installedBranch = cdb_retrieveBranch(c_id)
                    installedDigest = cdb_retrieveDigest(c_id)
                except TypeError: # corrupted entry?
                    installedVer = "0"
                    installedTag = ''
                    installedRev = 0
                    installedBranch = None
                    installedDigest = None
                client_data.add((installedVer, installedTag, installedRev,
                    installedBranch, installedDigest,))

            # support for app-foo/foo-123~-1
            # -1 revision means, always pull the latest
            do_deep = deep_deps
            if not do_deep:
                string_rev = etp_get_rev(dependency)
                if string_rev == -1:
                    do_deep = True

            # this is required for multi-slotted packages (like python)
            # and when people mix Entropy and Portage
            for installedVer, installedTag, installedRev, cbranch, cdigest in client_data:

                vcmp = etp_cmp((repo_pkgver,repo_pkgtag,repo_pkgrev,),
                    (installedVer,installedTag,installedRev,))

                # check if both pkgs share the same branch and digest, this must
                # be done to avoid system inconsistencies across branch upgrades
                if (vcmp == 0) and (cbranch != repo_branch) and \
                    (cdigest != repo_digest):
                    vcmp = 1

                if (vcmp == 0):
                    const_debug_write(__name__,
                        "get_unsatisfied_dependencies SATISFIED equals (not cached, deep: %s) => %s" % (
                            deep_deps, dependency,))
                    depcache[dependency] = 0
                    const_debug_write(__name__, "...")
                    return 0

                ver_tag_repo = (repo_pkgver, repo_pkgtag,)
                ver_tag_inst = (installedVer, installedTag,)
                rev_match = repo_pkgrev != installedRev

                if not do_deep and (ver_tag_repo == ver_tag_inst) and rev_match:

                    depcache[dependency] = 0
                    const_debug_write(__name__,
                        "get_unsatisfied_dependencies SATISFIED w/o rev (not cached, deep: %s) => %s" % (
                            deep_deps, dependency,))
                    const_debug_write(__name__, "...")
                    return 0

            # if we get here it means that there are no matching packages
            const_debug_write(__name__,
                "get_unsatisfied_dependencies NOT SATISFIED (not cached, deep: %s) => %s" % (
                    deep_deps, dependency,))

            depcache[dependency] = dependency
            const_debug_write(__name__, "...")
            return dependency

        unsatisfied = list(map(fm_dep,dependencies))
        unsatisfied = set([x for x in unsatisfied if x != 0])

        if self.xcache:
            self.Cacher.push(c_hash,unsatisfied)

        return unsatisfied

    def get_masked_packages_tree(self, match, atoms = False, flat = False, matchfilter = None):

        if not isinstance(matchfilter,set):
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
                        mydict = {(idpackage,repoid): idreason}
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


    def generate_dependency_tree(self,
        matched_atom, empty_deps = False, deep_deps = False, matchfilter = None,
        flat = False, filter_unsat_cache = None, treecache = None, keyslotcache = None):

        if not isinstance(matchfilter,set):
            matchfilter = set()
        if not isinstance(filter_unsat_cache,dict):
            filter_unsat_cache = {}
        if not isinstance(treecache,set):
            treecache = set()
        if not isinstance(keyslotcache,set):
            keyslotcache = set()

        mydbconn = self.open_repository(matched_atom[1])
        myatom = mydbconn.retrieveAtom(matched_atom[0])

        # caches
        # special events
        deps_not_found = set()
        conflicts = set()

        mydep = (1,myatom)
        mybuffer = Lifo()
        deptree = set()
        if matched_atom not in matchfilter:
            deptree.add((1,matched_atom))

        virgin = True
        open_repo = self.open_repository
        atom_match = self.atom_match
        cdb_atom_match = self.clientDbconn.atomMatch
        lookup_conflict_replacement = self._lookup_conflict_replacement
        lookup_library_breakages = self._lookup_library_breakages
        lookup_inverse_dependencies = self._lookup_inverse_dependencies
        get_unsatisfied_deps = self.get_unsatisfied_dependencies

        def my_dep_filter(x):
            if x in treecache: return False
            if tuple(x.split(":")) in keyslotcache: return False
            return True

        while mydep:

            const_debug_write(__name__,
                "generate_dependency_tree analyzing => %s" % (
                    mydep,))

            dep_level, dep_atom = mydep

            # already analyzed in this call
            if dep_atom in treecache:
                const_debug_write(__name__,
                    "generate_dependency_tree already in treecache => %s" % (
                        dep_atom,))
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    const_debug_write(__name__, "---empty--")
                    break # stack empty
                const_debug_write(__name__, "---")
                continue
            treecache.add(dep_atom)

            if dep_atom is None: # corrupted entry
                const_debug_write(__name__,
                    "generate_dependency_tree broken entry in DB => %s" % (
                        mydep,))
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    const_debug_write(__name__, "---empty2--")
                    break # stack empty
                const_debug_write(__name__, "---")
                continue

            # conflicts
            if dep_atom[0] == "!":
                c_idpackage, xst = cdb_atom_match(dep_atom[1:])
                if c_idpackage != -1:
                    myreplacement = lookup_conflict_replacement(dep_atom[1:],
                        c_idpackage, deep_deps = deep_deps)

                    const_debug_write(__name__,
                        "generate_dependency_tree conflict replacement => %s" % (
                            myreplacement,))

                    if (myreplacement != None) and (myreplacement not in treecache):
                        mybuffer.push((dep_level+1,myreplacement))
                    else:
                        conflicts.add(c_idpackage)
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    const_debug_write(__name__, "---empty3---")
                    break # stack empty
                const_debug_write(__name__, "---")
                continue

            # atom found?
            if virgin:

                virgin = False
                m_idpackage, m_repo = matched_atom
                dbconn = open_repo(m_repo)
                myidpackage, idreason = dbconn.idpackageValidator(m_idpackage)

                const_debug_write(__name__,
                    "generate_dependency_tree virgin match masked? => %s - %s" % (
                        myidpackage, idreason,))

                if myidpackage == -1:
                    m_idpackage = -1

            else:
                m_idpackage, m_repo = atom_match(dep_atom)
                const_debug_write(__name__,
                    "generate_dependency_tree matching %s => (%s, %s)" % (
                        dep_atom, m_idpackage, m_repo,))

            if m_idpackage == -1:

                const_debug_write(__name__,
                    "generate_dependency_tree dep not found => %s" % (
                        dep_atom,))

                deps_not_found.add(dep_atom)
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    const_debug_write(__name__, "---empty3---")
                    break # stack empty
                const_debug_write(__name__, "---")
                continue

            # check if atom has been already pulled in
            matchdb = open_repo(m_repo)
            matchatom = matchdb.retrieveAtom(m_idpackage)
            matchkey, matchslot = matchdb.retrieveKeySlot(m_idpackage)

            const_debug_write(__name__,
                "generate_dependency_tree idpackage %s => %s - %s:%s" % (
                    m_idpackage, matchatom, matchkey, matchslot))

            if (dep_atom != matchatom) and (matchatom in treecache):
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    const_debug_write(__name__, "---empty4---")
                    break # stack empty
                const_debug_write(__name__,
                    "generate_dependency_tree matchatom %s already in cache" % (
                        matchatom,))
                const_debug_write(__name__, "---")
                continue

            treecache.add(matchatom)

            const_debug_write(__name__,
                "generate_dependency_tree check if key + slot cache => %s" % (
                    (matchslot, matchkey),))

            # check if key + slot has been already pulled in
            if (matchslot, matchkey) in keyslotcache:
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    const_debug_write(__name__, "---empty5---")
                    break # stack empty
                const_debug_write(__name__, "---")
                continue
            else:
                keyslotcache.add((matchslot, matchkey))

            const_debug_write(__name__,
                "generate_dependency_tree not in key + slot cache => %s" % (
                    (matchslot, matchkey),))

            match = (m_idpackage, m_repo,)
            # result already analyzed?
            if match in matchfilter:
                try:
                    mydep = mybuffer.pop()
                except ValueError:
                    const_debug_write(__name__, "---empty6---")
                    break # stack empty
                const_debug_write(__name__, "---")
                continue

            const_debug_write(__name__,
                "generate_dependency_tree match NOT already analyzed => %s" % (
                    match,))

            # all checks passed, well done
            matchfilter.add(match)
            treedepth = dep_level+1
            deptree.add((dep_level,match)) # add match

            # extra hooks
            cm_idpackage, cm_result = cdb_atom_match(matchkey,
                matchSlot = matchslot)
            if cm_idpackage != -1:

                broken_children_atoms = self._lookup_library_drops(match,
                    (cm_idpackage, cm_result,))

                broken_atoms = lookup_library_breakages(match,
                    (cm_idpackage, cm_result,))
                const_debug_write(__name__,
                    "generate_dependency_tree lib broken atoms for %s => %s" % (
                        matchkey+":"+matchslot, broken_atoms,))

                inverse_deps = lookup_inverse_dependencies(match,
                    (cm_idpackage, cm_result,))
                const_debug_write(__name__,
                    "generate_dependency_tree inverse deps for %s => %s" % (
                        matchkey+":"+matchslot, inverse_deps,))

                if inverse_deps:
                    deptree.remove((dep_level,match))
                    for ikey,islot in inverse_deps:
                        iks_str = '%s:%s' % (ikey,islot,)
                        if ((ikey,islot) not in keyslotcache) and (iks_str not in treecache):
                            mybuffer.push((dep_level,iks_str))
                            keyslotcache.add((ikey,islot))
                    deptree.add((treedepth,match))
                    treedepth += 1

                # broken children atoms can be added to broken atoms
                # and pulled into dep calculation
                broken_atoms |= broken_children_atoms
                for x in broken_atoms:
                    if (tuple(x.split(":")) not in keyslotcache) and \
                        (x not in treecache):
                        mybuffer.push((treedepth,x))

            m_deplist = matchdb.retrieveDependenciesList(m_idpackage)

            const_debug_write(__name__,
                "generate_dependency_tree dependency list for %s => %s" % (
                    m_idpackage, m_deplist,))

            myundeps = list(filter(my_dep_filter, m_deplist))

            const_debug_write(__name__,
                "generate_dependency_tree filtered dependency list => %s" % (
                    myundeps,))

            if not empty_deps:

                m_unsat_deplist = get_unsatisfied_deps(myundeps, deep_deps,
                    depcache = filter_unsat_cache)

                const_debug_write(__name__,
                    "generate_dependency_tree unsatisfied dependencies (deep: %s) => %s" % (
                        deep_deps, m_unsat_deplist,))

                myundeps = list(filter(my_dep_filter, m_unsat_deplist))

                const_debug_write(__name__,
                    "generate_dependency_tree filtered UNSATISFIED dependencies => %s" % (
                        myundeps,))

            # PDEPENDs support
            if myundeps:

                post_deps = [x for x in \
                    matchdb.retrievePostDependencies(m_idpackage) if x \
                    in myundeps]

                const_debug_write(__name__,
                    "generate_dependency_tree POST dependencies => %s" % (
                        post_deps,))

                if post_deps:

                    # do some filtering
                    # it is correct to not use my_dep_filter here
                    myundeps = [x for x in myundeps if x not in post_deps]

                    const_debug_write(__name__,
                        "generate_dependency_tree POST dependencies ADDED => %s" % (
                            myundeps,))

                for x in post_deps:
                    mybuffer.push((-1, x)) # always after the package itself

            for x in myundeps:
                mybuffer.push((treedepth, x))

            try:
                mydep = mybuffer.pop()
            except ValueError:
                const_debug_write(__name__, "---empty7---")
                break # stack empty
            const_debug_write(__name__, "---")

        if deps_not_found:
            return list(deps_not_found), -2

        if flat:
            return [x[1] for x in deptree], 0

        newdeptree = {}
        for key, item in deptree:
            if key >= 0:
                # this makes sure that key is never = 0
                key += 1
            obj = newdeptree.setdefault(key, set())
            obj.add(item)
        # conflicts
        newdeptree[0] = conflicts

        return newdeptree,0 # note: newtree[0] contains possible conflicts


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
                if myaction == 1: mydata.append(mymatch)
            cached_items.add(mymatch)
        return mydata

    def _lookup_conflict_replacement(self, conflict_atom, client_idpackage, deep_deps):
        if self.entropyTools.isjustname(conflict_atom):
            return None
        conflict_match = self.atom_match(conflict_atom)
        mykey, myslot = self.clientDbconn.retrieveKeySlot(client_idpackage)
        new_match = self.atom_match(mykey, matchSlot = myslot)
        if (conflict_match == new_match) or (new_match[1] == 1):
            return None
        action = self.get_package_action(new_match)
        if (action == 0) and (not deep_deps):
            return None
        return "%s:%s" % (mykey,myslot,)

    def _lookup_inverse_dependencies(self, match, clientmatch):

        cmpstat = self.get_package_action(match)
        if cmpstat == 0: return set()

        keyslots = set()
        mydepends = self.clientDbconn.retrieveReverseDependencies(clientmatch[0])
        am = self.atom_match
        cdb_rdeps = self.clientDbconn.retrieveDependencies
        cdb_rks = self.clientDbconn.retrieveKeySlot
        gpa = self.get_package_action
        keyslots_cache = set()
        match_cache = {}

        for idpackage in mydepends:
            try:
                key, slot = cdb_rks(idpackage)
            except TypeError:
                continue
            if (key,slot) in keyslots_cache: continue
            keyslots_cache.add((key,slot))
            if (key,slot) in keyslots: continue
            # grab its deps
            mydeps = cdb_rdeps(idpackage)
            found = False
            for mydep in mydeps:
                mymatch = match_cache.get(mydep, 0)
                if mymatch == 0:
                    mymatch = am(mydep)
                    match_cache[mydep] = mymatch
                if mymatch == match:
                    found = True
                    break
            if not found:
                mymatch = am(key, matchSlot = slot)
                if mymatch[0] == -1: continue
                cmpstat = gpa(mymatch)
                if cmpstat == 0: continue
                keyslots.add((key,slot))

        return keyslots

    def _lookup_library_drops(self, match, client_match):

        broken_atoms = set()

        match_id, match_repo = match
        match_db = self.open_repository(match_repo)
        repo_libs = match_db.retrieveProvidedLibraries(match_id)

        client_libs = self.clientDbconn.retrieveProvidedLibraries(
            client_match[0])
        removed_libs = set([x for x in client_libs if x not in repo_libs])

        idpackages = set()
        for lib, path, elf in removed_libs:
            idpackages |= self.clientDbconn.searchNeeded(lib, elfclass = elf)

        for c_idpackage in idpackages:

            keyslot = self.clientDbconn.retrieveKeySlotAggregated(c_idpackage)
            idpackage, repo = self.atom_match(keyslot)
            if idpackage == -1:
                continue

            cmpstat = self.get_package_action((idpackage, repo))
            if cmpstat == 0:
                continue

            broken_atoms.add(keyslot)

        return broken_atoms


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

        # these should be pulled in before
        repo_atoms = set()
        # these can be pulled in after
        client_atoms = set()

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
        client_keyslots = set([x for x in map(mymf,client_idpackages) \
            if x != 0])

        # all the packages in repo_side should be pulled in too
        repodata = {}
        for needed in repo_side:
            repodata[needed] = reponeeded[needed]
        del repo_side,reponeeded

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

        for idpackage,repo in found_matches:
            cmpstat = self.get_package_action((idpackage,repo))
            if cmpstat == 0:
                continue
            mydbc = self.open_repository(repo)
            repo_atoms.add(mydbc.retrieveAtom(idpackage))

        for key, slot in client_keyslots:
            idpackage, repo = self.atom_match(key, matchSlot = slot)
            if idpackage == -1:
                continue
            cmpstat = self.get_package_action((idpackage, repo))
            if cmpstat == 0:
                continue
            mydbc = self.open_repository(repo)
            client_atoms.add(mydbc.retrieveAtom(idpackage))

        client_atoms |= repo_atoms

        if self.xcache:
            self.Cacher.push(c_hash,client_atoms)

        return client_atoms

    def __deptree_prioritize_systempkgs(self, deptree):


        conflicts_key = 0
        # save list of conflicts, actually at key 0
        conflicts = deptree.get(conflicts_key, set()).copy()

        system_tree = {}
        normal_tree = {}
        system_pkgs_cache = {}


        for deplevel in deptree:

            if deplevel == conflicts_key: # skip conflicts
                continue

            for idpackage, repoid in deptree[deplevel]:

                if repoid not in system_pkgs_cache:
                    repodb = self.open_repository(repoid)
                    system_pkgs_cache[repoid] = repodb.getSystemPackages()

                if idpackage in system_pkgs_cache[repoid]:
                    obj = system_tree.setdefault(deplevel, set())
                    obj.add((idpackage, repoid,))
                else:
                    obj = normal_tree.setdefault(deplevel, set())
                    obj.add((idpackage, repoid,))

        # now create new deptree
        # system_tree is used because it's already half ready
        # it just needs entries from normal tree
        if system_tree:
            min_deplevel = max(system_tree)
        else:
            min_deplevel = conflicts_key

        for deplevel in normal_tree:

            # start from the next available
            min_deplevel += 1
            system_tree[min_deplevel] = normal_tree[deplevel]

        # add conflicts back
        system_tree[conflicts_key] = conflicts

        return system_tree

    def get_required_packages(self, matched_atoms, empty_deps = False, deep_deps = False, quiet = False):

        c_hash = "%s%s" % (
            etpCache['dep_tree'],
            hash("%s|%s|%s|%s|%s" % (
                hash(frozenset(sorted(matched_atoms))),
                empty_deps,
                deep_deps,
                self.clientDbconn.checksum(),
                # needed when users do bogus things like editing config files
                # manually (branch setting)
                self.SystemSettings['repositories']['branch'],
        )),)
        if self.xcache:
            cached = self.Cacher.pop(c_hash)
            if cached is not None:
                return cached

        deptree = {}
        deptree[0] = set()

        atomlen = len(matched_atoms); count = 0
        error_generated = 0
        error_tree = set()

        # check if there are repositories needing some mandatory packages
        forced_matches = self._lookup_system_mask_repository_deps()
        if forced_matches:
            if isinstance(matched_atoms, list):
                matched_atoms = forced_matches + [x for x in matched_atoms if x not in forced_matches]
            elif isinstance(matched_atoms, set): # we cannot do anything about the order here
                matched_atoms |= set(forced_matches)

        sort_dep_text = _("Sorting dependencies")
        filter_unsat_cache = {}
        treecache = set()
        keyslotcache = set()
        matchfilter = set()
        for matched_atom in matched_atoms:
            const_debug_write(__name__,
                "get_required_packages matched_atom => %s" % (matched_atom,))

            if not quiet:
                count += 1
                if (count%10 == 0) or (count == atomlen) or (count == 1):
                    self.updateProgress(sort_dep_text, importance = 0, type = "info",
                        back = True, header = ":: ", footer = " ::",
                        percent = True, count = (count,atomlen))

            if matched_atom in matchfilter:
                continue
            newtree, result = self.generate_dependency_tree(
                matched_atom, empty_deps, deep_deps,
                matchfilter = matchfilter, filter_unsat_cache = filter_unsat_cache, treecache = treecache,
                keyslotcache = keyslotcache
            )

            const_debug_write(__name__,
                "get_required_packages deptree => %s -- %s" % (
                    newtree, result,))

            if result == -2: # deps not found
                error_generated = -2
                error_tree |= set(newtree) # it is a list, we convert it into set and update error_tree
            elif result != 0:
                return newtree, result
            elif newtree:
                # add conflicts
                max_parent_key = max(deptree)
                deptree[0] |= newtree.pop(0)
                levelcount = 0
                for mylevel in sorted(list(newtree.keys()), reverse = True):
                    levelcount += 1
                    deptree[max_parent_key+levelcount] = newtree.get(mylevel)

        if error_generated != 0:
            return error_tree, error_generated

        # now we need to move system packages at the top
        deptree = self.__deptree_prioritize_systempkgs(deptree)

        if self.xcache:
            self.Cacher.push(c_hash,(deptree, 0))

        return deptree, 0

    def _filter_depends_multimatched_atoms(self, idpackage, depends, monotree):
        remove_depends = set()
        for d_idpackage in depends:
            mydeps = self.clientDbconn.retrieveDependencies(d_idpackage)
            for mydep in mydeps:
                matches, rslt = self.clientDbconn.atomMatch(mydep, multiMatch = True)
                if rslt == 1: continue
                if idpackage in matches and len(matches) > 1:
                    # are all in depends?
                    for mymatch in matches:
                        if mymatch not in depends and mymatch not in monotree:
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
            if cached != None: return cached

        dependscache = set()
        treeview = set(idpackages)
        treelevel = set(idpackages)
        tree = {}
        # I start from level 1 because level 0 is idpackages itself
        treedepth = 0
        tree[treedepth] = set(idpackages)
        monotree = set(idpackages) # monodimensional tree

        # post-dependencies won't be pulled in
        pdepend_id = etpConst['spm']['pdepend_id']
        # check if dependstable is sane before beginning
        self.clientDbconn.retrieveReverseDependencies(idpackages[0])
        count = 0

        rem_dep_text = _("Calculating inverse dependencies for")
        while 1:
            treedepth += 1
            tree[treedepth] = set()
            for idpackage in treelevel:

                count += 1
                p_atom = self.clientDbconn.retrieveAtom(idpackage)
                self.updateProgress(
                    blue(rem_dep_text + " %s" % (red(p_atom),)),
                    importance = 0,
                    type = "info",
                    back = True,
                    header = '|/-\\'[count%4]+" "
                )

                systempkg = not self.validate_package_removal(idpackage)
                if (idpackage in dependscache) or systempkg:
                    if idpackage in treeview:
                        treeview.remove(idpackage)
                    continue

                # obtain its inverse deps
                depends = self.clientDbconn.retrieveReverseDependencies(idpackage,
                    exclude_deptypes = (pdepend_id,))
                # filter already satisfied ones
                depends = set([x for x in depends if x not in monotree])
                depends = set([x for x in depends if \
                    self.validate_package_removal(x)])
                if depends:
                    depends = self._filter_depends_multimatched_atoms(
                        idpackage, depends, monotree)
                if depends: # something depends on idpackage
                    tree[treedepth] |= depends
                    monotree |= depends
                    treeview |= depends
                elif deep: # if deep, grab its dependencies and check

                    mydeps = set()
                    for x in self.clientDbconn.retrieveDependencies(idpackage):
                        match = self.clientDbconn.atomMatch(x)
                        if match[0] != -1:
                            mydeps.add(match[0])

                    # now filter them
                    mydeps = [x for x in mydeps if x not in monotree and not \
                        (self.clientDbconn.isSystemPackage(x) or \
                            self.is_installed_idpackage_in_system_mask(x) )]
                    for x in mydeps:
                        mydepends = self.clientDbconn.retrieveReverseDependencies(x)
                        mydepends -= set([y for y in mydepends if y \
                            not in monotree])
                        if not mydepends:
                            tree[treedepth].add(x)
                            monotree.add(x)
                            treeview.add(x)

                dependscache.add(idpackage)
                if idpackage in treeview:
                    treeview.remove(idpackage)

            treelevel = treeview.copy()
            if not treelevel:
                if not tree[treedepth]:
                    del tree[treedepth] # probably the last one is empty then
                break

        # now filter newtree
        for count in sorted(list(tree.keys()), reverse = True):
            x = 0
            while x < count:
                tree[x] -= tree[count]
                x += 1

        if self.xcache:
            self.Cacher.push(c_hash,(tree,0))
        # treeview is used to show deps while
        # tree is used to run the dependency code.
        return tree,0

    def calculate_available_packages(self, use_cache = True):

        c_hash = self.get_available_packages_chash()
        if use_cache and self.xcache:
            cached = self.get_available_packages_cache(myhash = c_hash)
            if cached != None:
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
                        count = (count,maxlen),
                        percent = True,
                        footer = " ::"
                    )
                # get key + slot
                try:
                    key, slot = dbconn.retrieveKeySlot(idpackage)
                    matches = self.clientDbconn.searchKeySlot(key, slot)
                except (self.dbapi2.DatabaseError,self.dbapi2.IntegrityError,self.dbapi2.OperationalError,):
                    self.cycleDone()
                    do_break = True
                    continue
                if not matches: myavailable.append((idpackage,repo))
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
            if cached != None:
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

        atoms = self.get_unsatisfied_dependencies(atoms)
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
            if cached != None:
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
                    count = (count,maxlen),
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
            while 1:
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
                    if (m_idpackage,repoid) not in update:
                        update.append((m_idpackage,repoid))
                    continue
                elif (cl_revision != revision):
                    # different revision
                    if cl_revision == 9999 and ignore_spm_downgrades:
                        # no difference, we're ignoring revision 9999
                        fine.append(cl_atom)
                        if (m_idpackage,repoid) not in update:
                            spm_fine.append((m_idpackage,repoid))
                        continue
                    else:
                        if (m_idpackage,repoid) not in update:
                            update.append((m_idpackage,repoid))
                        continue
                elif (cl_version != version):
                    # different versions
                    if (m_idpackage,repoid) not in update:
                        update.append((m_idpackage,repoid))
                    continue
                elif (cl_tag != tag):
                    # different tags
                    if (m_idpackage,repoid) not in update:
                        update.append((m_idpackage,repoid))
                    continue
                else:

                    # Note: this is a bugfix to improve branch migration
                    # and really check if pkg has been repackaged and branch
                    # changed.
                    # first check branch
                    if idpackage is not None:

                        c_branch = self.clientDbconn.retrieveBranch(idpackage)
                        c_repodb = self.open_repository(repoid)
                        r_branch = c_repodb.retrieveBranch(m_idpackage)

                        if (c_branch != r_branch) and (c_branch is not None) \
                            and (r_branch is not None):

                            c_digest = self.clientDbconn.retrieveDigest(idpackage)
                            r_digest = c_repodb.retrieveDigest(m_idpackage)

                            if (r_digest != c_digest) and (r_digest is not None) \
                                and (c_digest is not None):
                                if (m_idpackage,repoid) not in update:
                                    update.append((m_idpackage,repoid))
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
            self.Cacher.push("%s%s" % (etpCache['world_update'],c_hash,),
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
            if cached != None:
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
            if mytag != None:
                pkg_match += "#%s" % (mytag,)
            pkg_unsatisfied = self.get_unsatisfied_dependencies([pkg_match], deep_deps = deep)
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
            self.Cacher.push(c_hash,(found, matched))
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
        treeview, status = self.generate_depends_tree(idpackages, deep = deep)
        if status == 0:
            for x in range(len(treeview))[::-1]: queue.extend(treeview[x])
        return queue

    def get_install_queue(self, matched_atoms, empty_deps, deep_deps, quiet = False):

        install = []
        removal = []
        treepackages, result = self.get_required_packages(matched_atoms,
            empty_deps, deep_deps, quiet = quiet)

        if result == -2:
            return treepackages,removal,result

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

