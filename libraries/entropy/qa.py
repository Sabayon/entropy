# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Framework QA module}.

    This module contains various Quality Assurance routines used by Entropy.

    B{QAInterface} is the main class for QA routines used by Entropy Server
    and Entropy Client such as binary packages health check, dependency
    test, broken or missing library tes.

    B{ErrorReportInterface} is the HTTP POST based class for Entropy Client
    exceptions (errors) submission.

"""
import os
import sys
import subprocess
import tempfile

from entropy.const import etpConst, etpSys
from entropy.output import blue, darkgreen, red, darkred, bold, purple, brown
from entropy.exceptions import IncorrectParameter, PermissionDenied, \
    SystemDatabaseError
from entropy.i18n import _
from entropy.core import SystemSettings

class QAInterface:

    """
    Entropy QA interface. This class contains all the Entropy
    QA routines used by Entropy Server and Entropy Client.

    An instance of QAInterface can be easily retrieved from
    entropy.client.interfaces.Client or entropy.server.interfaces.Server
    through an exposed QA() method.
    This is anyway a stand-alone class.

    @todo: remove non-QA methods

    """

    import entropy.tools as entropyTools
    from entropy.misc import Lifo
    def __init__(self, OutputInterface):
        """
        QAInterface constructor.

        @param OutputInterface: class instance used to print output.
        Even if not enforced at the moment, it should be a subclass of
        entropy.qa.TextInterface exposing the updateProgress() method
        with proper signature.
        @type OutputInterface: TextInterface class or subclass instance
        """
        self.Output = OutputInterface
        self.SystemSettings = SystemSettings()

        if not hasattr(self.Output, 'updateProgress'):
            mytxt = _("Output interface has no updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        elif not callable(self.Output.updateProgress):
            mytxt = _("Output interface has no updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

    def test_depends_linking(self, idpackages, dbconn, repo = None):
        """
        Scan for broken shared objects linking for the given idpackages on
        the given entropy.db.LocalRepository based instance.
        Note: this only works for packages actually installed on the running
        system.
        It is used by Entropy Server during packages injection into database
        to warn about potentially broken packages.

        @param idpackages: list of valid idpackages (int) on the given dbconn
            argument passed
        @type idpackages: list
        @param dbconn: entropy.db.LocalRepository instance containing the
            given idpackages list
        @type dbconn: entropy.db.LocalRepository
        @keyword repo: repository identifer from which dbconn and idpackages
            arguments belong. Note: at the moment it's only used for output
            purposes.
        @type repo: string
        @return: True if any breakage is found, otherwise False
        @rtype: bool
        """
        if repo is None:
            repo = self.SystemSettings['repositories']['default_repository']

        scan_msg = blue(_("Now searching for broken depends"))
        self.Output.updateProgress(
            "[repo:%s] %s..." % (
                        darkgreen(repo),
                        scan_msg,
                    ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        broken = False

        count = 0
        maxcount = len(idpackages)
        for idpackage in idpackages:
            count += 1
            atom = dbconn.retrieveAtom(idpackage)
            scan_msg = "%s, %s:" % (
                blue(_("scanning for broken depends")),
                darkgreen(atom),
            )
            self.Output.updateProgress(
                "[repo:%s] %s" % (
                    darkgreen(repo),
                    scan_msg,
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True,
                count = (count, maxcount,)
            )
            mydepends = dbconn.retrieveDepends(idpackage)
            if not mydepends:
                continue
            for mydepend in mydepends:
                myatom = dbconn.retrieveAtom(mydepend)
                self.Output.updateProgress(
                    "[repo:%s] %s => %s" % (
                        darkgreen(repo),
                        darkgreen(atom),
                        darkred(myatom),
                    ),
                    importance = 0,
                    type = "info",
                    header = blue(" @@ "),
                    back = True,
                    count = (count, maxcount,)
                )
                mycontent = dbconn.retrieveContent(mydepend)
                mybreakages = self._content_test(mycontent)
                if not mybreakages:
                    continue
                broken = True
                self.Output.updateProgress(
                    "[repo:%s] %s %s => %s" % (
                        darkgreen(repo),
                        darkgreen(atom),
                        darkred(myatom),
                        bold(_("broken libraries detected")),
                    ),
                    importance = 1,
                    type = "warning",
                    header = purple(" @@ "),
                    count = (count, maxcount,)
                )
                for mylib in mybreakages:
                    self.Output.updateProgress(
                        "%s %s:" % (
                            darkgreen(mylib),
                            red(_("needs")),
                        ),
                        importance = 1,
                        type = "warning",
                        header = brown("   ## ")
                    )
                    for needed in mybreakages[mylib]:
                        self.Output.updateProgress(
                            "%s" % (
                                red(needed),
                            ),
                            importance = 1,
                            type = "warning",
                            header = purple("     # ")
                        )
        return broken

    def test_missing_dependencies(self, idpackages, dbconn, ask = True,
            self_check = False, repo = None, black_list = None,
            black_list_adder = None):
        """
        Scan missing dependencies for the given idpackages on the given
        entropy.db.LocalRepository "dbconn" instance. In addition, this method
        will allow the user through OutputInterface to interactively add (if ask
        == True) missing dependencies or blacklist them.

        @param idpackages: list of valid idpackages (int) on the given dbconn
            argument passed
        @type idpackages: list
        @param dbconn: entropy.db.LocalRepository instance containing the
            given idpackages list
        @type dbconn: entropy.db.LocalRepository
        @keyword ask: request user interaction when finding missing dependencies
        @type ask: bool
        @keyword self_check: also introspect inside the complaining package
            (to avoid reporting false positives when circular dependencies
            occur)
        @type self_check: bool
        @keyword repo: repository identifier of the given
            entropy.db.LocalRepository dbconn instance.
            It is used to correctly place blacklisted items.
        @type repo: string
        @keyword black_list: list of dependencies already blacklisted.
        @type black_list: set
        @keyword black_list_adder: callable function that accepts two arguments:
            (1) list (set) of new dependencies to blacklist for the
            given (2) repository identifier.
        @type black_list_adder: callable
        @return: tainting status, if any dependency has been added
        @rtype: bool
        """
        if repo is None:
            repo = self.SystemSettings['repositories']['default_repository']

        if not isinstance(black_list, set):
            black_list = set()

        taint = False
        scan_msg = blue(_("Now searching for missing RDEPENDs"))
        self.Output.updateProgress(
            "[repo:%s] %s..." % (
                        darkgreen(repo),
                        scan_msg,
                    ),
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )
        scan_msg = blue(_("scanning for missing RDEPENDs"))
        count = 0
        maxcount = len(idpackages)
        for idpackage in idpackages:
            count += 1
            atom = dbconn.retrieveAtom(idpackage)
            if not atom:
                continue
            self.Output.updateProgress(
                "[repo:%s] %s: %s" % (
                            darkgreen(repo),
                            scan_msg,
                            darkgreen(atom),
                        ),
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True,
                count = (count, maxcount,)
            )
            missing_extended, missing = self._get_missing_rdepends(dbconn,
                idpackage, self_check = self_check)
            missing -= black_list
            for item in missing_extended.keys():
                missing_extended[item] -= black_list
                if not missing_extended[item]:
                    del missing_extended[item]
            if (not missing) or (not missing_extended):
                continue
            self.Output.updateProgress(
                "[repo:%s] %s: %s %s:" % (
                            darkgreen(repo),
                            blue("package"),
                            darkgreen(atom),
                            blue(_("is missing the following dependencies")),
                        ),
                importance = 1,
                type = "info",
                header = red(" @@ "),
                count = (count, maxcount,)
            )
            for missing_data in missing_extended:
                self.Output.updateProgress(
                        "%s:" % (brown(unicode(missing_data)),),
                        importance = 0,
                        type = "info",
                        header = purple("   ## ")
                )
                for dependency in missing_extended[missing_data]:
                    self.Output.updateProgress(
                            "%s" % (darkred(dependency),),
                            importance = 0,
                            type = "info",
                            header = blue("     # ")
                    )
            if ask:
                rc_ask = self.Output.askQuestion(_("Do you want to add them?"))
                if rc_ask == "No":
                    continue
                rc_ask = self.Output.askQuestion(_("Selectively?"))
                if rc_ask == "Yes":
                    newmissing = set()
                    new_blacklist = set()
                    for dependency in missing:
                        self.Output.updateProgress(
                            "[repo:%s|%s] %s" % (
                                    darkgreen(repo),
                                    brown(atom),
                                    blue(dependency),
                            ),
                            importance = 0,
                            type = "info",
                            header = blue(" @@ ")
                        )
                        rc_ask = self.Output.askQuestion(_("Want to add?"))
                        if rc_ask == "Yes":
                            newmissing.add(dependency)
                        else:
                            rc_ask = self.Output.askQuestion(
                                _("Want to blacklist?"))
                            if rc_ask == "Yes":
                                new_blacklist.add(dependency)
                    if new_blacklist and (black_list_adder != None):
                        black_list_adder(new_blacklist, repo = repo)
                    missing = newmissing
            if missing:
                taint = True
                dbconn.insertDependencies(idpackage, missing)
                dbconn.commitChanges()
                self.Output.updateProgress(
                    "[repo:%s] %s: %s" % (
                        darkgreen(repo),
                        darkgreen(atom),
                        blue(_("missing dependencies added")),
                    ),
                    importance = 1,
                    type = "info",
                    header = red(" @@ "),
                    count = (count, maxcount,)
                )

        return taint

    def test_shared_objects(self, dbconn, broken_symbols = False,
        task_bombing_func = None):

        """
        Scan system looking for broken shared object ELF library dependencies.

        @param dbconn: entropy.db.LocalRepository instance which contains
            information on packages installed on the system (for example:
            entropy.client.interfaces.Client.clientDbconn ).
        @type dbconn: entropy.db.LocalRepository instance
        @keyword broken_symbols: enable or disable broken symbols extra check.
            Symbols which are going to be checked have to be listed into:
            /etc/entropy/brokensyms.conf (regexp supported).
        @type broken_symbols: bool
        @keyword task_bombing_func: callable that will be called on every
            scan iteration to allow external routines to cleanly stop the
            execution of this function.
        @type task_bombing_func: callable
        packagesMatched, plain_brokenexecs, 0
        @return: tuple of length 3, composed by (1) a dict of matched packages,
            (2) a list (set) of broken ELF objects and (3) the execution status
            (int, 0 means success).
        @rtype: tuple
        """

        self.Output.updateProgress(
            blue(_("Libraries test")),
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )

        myroot = etpConst['systemroot'] + "/"
        if not etpConst['systemroot']:
            myroot = "/"

        # run ldconfig first
        subprocess.call("ldconfig -r %s &> /dev/null" % (myroot,), shell = True)
        # open /etc/ld.so.conf
        ld_conf = etpConst['systemroot'] + "/etc/ld.so.conf"

        if not os.path.isfile(ld_conf):
            self.Output.updateProgress(
                blue(_("Cannot find "))+red(ld_conf),
                importance = 1,
                type = "error",
                header = red(" @@ ")
            )
            return {}, set(), -1

        reverse_symlink_map = self.SystemSettings['system_rev_symlinks']
        broken_syms_list = self.SystemSettings['broken_syms']
        broken_libs_mask = self.SystemSettings['broken_libs_mask']

        import re

        broken_syms_list_regexp = []
        for broken_sym in broken_syms_list:
            reg_sym = re.compile(broken_sym)
            broken_syms_list_regexp.append(reg_sym)

        broken_libs_mask_regexp = []
        for broken_lib in broken_libs_mask:
            reg_lib = re.compile(broken_lib)
            broken_libs_mask_regexp.append(reg_lib)

        ldpaths = set(self.entropyTools.collect_linker_paths())
        ldpaths |= self.entropyTools.collect_paths()

        # some crappy packages put shit here too
        ldpaths.add("/usr/share")
        # always force /usr/libexec too
        ldpaths.add("/usr/libexec")

        # remove duplicated dirs (due to symlinks) to speed up scanning
        for real_dir in reverse_symlink_map.keys():
            syms = reverse_symlink_map[real_dir]
            for sym in syms:
                if sym in ldpaths:
                    ldpaths.discard(real_dir)
                    self.Output.updateProgress(
                        "%s: %s, %s: %s" % (
                            brown(_("discarding directory")),
                            purple(real_dir),
                            brown(_("because it's symlinked on")),
                            purple(sym),
                        ),
                        importance = 0,
                        type = "info",
                        header = darkgreen(" @@ ")
                    )
                    break

        executables = set()
        total = len(ldpaths)
        count = 0
        sys_root_len = len(etpConst['systemroot'])
        for ldpath in ldpaths:

            if callable(task_bombing_func):
                task_bombing_func()
            count += 1
            self.Output.updateProgress(
                blue("Tree: ")+red(etpConst['systemroot'] + ldpath),
                importance = 0,
                type = "info",
                count = (count,total),
                back = True,
                percent = True,
                header = "  "
            )
            ldpath = ldpath.encode(sys.getfilesystemencoding())
            mywalk_iter = os.walk(etpConst['systemroot'] + ldpath)

            def mywimf(dt):

                currentdir, subdirs, files = dt

                def mymf(item):
                    filepath = os.path.join(currentdir,item)
                    if not os.access(filepath, os.R_OK):
                        return 0
                    if not os.path.isfile(filepath):
                        return 0
                    if not self.entropyTools.is_elf_file(filepath):
                        return 0
                    return filepath[sys_root_len:]

                return set([x for x in map(mymf, files) if type(x) != int])

            for x in map(mywimf,mywalk_iter):
                executables |= x

        self.Output.updateProgress(
            blue(_("Collecting broken executables")),
            importance = 2,
            type = "info",
            header = red(" @@ ")
        )
        t = red(_("Attention")) + ": " + \
            blue(_("don't worry about libraries that are shown here but not later."))
        self.Output.updateProgress(
            t,
            importance = 1,
            type = "info",
            header = red(" @@ ")
        )

        plain_brokenexecs = set()
        total = len(executables)
        count = 0
        scan_txt = blue("%s ..." % (_("Scanning libraries"),))
        for executable in executables:

            # task bombing hook
            if callable(task_bombing_func):
                task_bombing_func()

            count += 1
            if (count % 10 == 0) or (count == total) or (count == 1):
                self.Output.updateProgress(
                    scan_txt,
                    importance = 0,
                    type = "info",
                    count = (count,total),
                    back = True,
                    percent = True,
                    header = "  "
                )

            myelfs = self.entropyTools.read_elf_dynamic_libraries(
                etpConst['systemroot'] + executable)

            def mymf2(mylib):
                return not self.entropyTools.resolve_dynamic_library(mylib,
                    executable)

            mylibs = set(filter(mymf2, myelfs))

            # filter broken libraries
            if mylibs:

                mylib_filter = set()
                for mylib in mylibs:
                    mylib_matched = False
                    for reg_lib in broken_libs_mask_regexp:
                        if reg_lib.match(mylib):
                            mylib_matched = True
                            break
                    if mylib_matched: # filter out
                        mylib_filter.add(mylib)
                mylibs -= mylib_filter


            broken_sym_found = set()
            if broken_symbols and not mylibs:

                read_broken_syms = self.entropyTools.read_elf_broken_symbols(
                        etpConst['systemroot'] + executable)
                my_broken_syms = set()
                for read_broken_sym in read_broken_syms:
                    for reg_sym in broken_syms_list_regexp:
                        if reg_sym.match(read_broken_sym):
                            my_broken_syms.add(read_broken_sym)
                            break
                broken_sym_found.update(my_broken_syms)

            if not (mylibs or broken_sym_found):
                continue

            if mylibs:
                alllibs = blue(' :: ').join(sorted(mylibs))
                self.Output.updateProgress(
                    red(etpConst['systemroot']+executable)+" [ "+alllibs+" ]",
                    importance = 1,
                    type = "info",
                    percent = True,
                    count = (count,total),
                    header = "  "
                )
            elif broken_sym_found:

                allsyms = darkred(' :: ').join(
                    [brown(x) for x in list(broken_sym_found)])
                if len(allsyms) > 50:
                    allsyms = brown(_('various broken symbols'))

                self.Output.updateProgress(
                    red(etpConst['systemroot']+executable)+" { "+allsyms+" }",
                    importance = 1,
                    type = "info",
                    percent = True,
                    count = (count,total),
                    header = "  "
                )

            plain_brokenexecs.add(executable)

        del executables
        packagesMatched = {}

        if not etpSys['serverside']:

            # we are client side
            # this is hackish and must be fixed sooner or later
            # but for now, it works
            # Client class is singleton and is surely already
            # loaded when we get here
            from entropy.client.interfaces import Client
            client = Client()

            self.Output.updateProgress(
                blue(_("Matching broken libraries/executables")),
                importance = 1,
                type = "info",
                header = red(" @@ ")
            )
            matched = set()
            for brokenlib in plain_brokenexecs:
                idpackages = dbconn.searchBelongs(brokenlib)

                for idpackage in idpackages:

                    key, slot = dbconn.retrieveKeySlot(idpackage)
                    mymatch = client.atom_match(key, matchSlot = slot)
                    if mymatch[0] == -1:
                        matched.add(brokenlib)
                        continue

                    cmpstat = client.get_package_action(mymatch)
                    if cmpstat == 0:
                        continue
                    if not packagesMatched.has_key(brokenlib):
                        packagesMatched[brokenlib] = set()

                    packagesMatched[brokenlib].add(mymatch)
                    matched.add(brokenlib)

            plain_brokenexecs -= matched

        return packagesMatched, plain_brokenexecs, 0

    def _content_test(self, mycontent):
        """
        Test whether the given list of files contain files
        with broken shared object links.

        @param mycontent: list of file paths
        @type mycontent: list or set
        @return: dict containing a map between file path
        and list (set) of broken libraries (just the library name,
            the same that is contained inside ELF metadata)
        @rtype: dict
        """
        def is_contained(needed, content):
            for item in content:
                if os.path.basename(item) == needed:
                    return True
            return False

        mylibs = {}
        for myfile in mycontent:
            myfile = myfile.encode('raw_unicode_escape')
            if not os.access(myfile, os.R_OK):
                continue
            if not os.path.isfile(myfile):
                continue
            if not self.entropyTools.is_elf_file(myfile):
                continue
            mylibs[myfile] = self.entropyTools.read_elf_dynamic_libraries(
                myfile)

        broken_libs = {}
        for mylib in mylibs:
            for myneeded in mylibs[mylib]:
                # is this inside myself ?
                if is_contained(myneeded, mycontent):
                    continue
                found = self.entropyTools.resolve_dynamic_library(myneeded,
                    mylib)
                if found:
                    continue
                if not broken_libs.has_key(mylib):
                    broken_libs[mylib] = set()
                broken_libs[mylib].add(myneeded)

        return broken_libs

    def _get_missing_rdepends(self, dbconn, idpackage, self_check = False):
        """
        Service method able to determine whether dependencies are missing
        on the given idpackage (belonging to the given
        entropy.db.LocalRepository "dbconn" argument) using shared objects
        linking information between packages.

        @todo: swap the first two arguments?
        @param dbconn: entropy.db.LocalRepository instance from which idpackage
            argument belongs
        @type dbconn: entropy.db.LocalRepository instance
        @param idpackage: entropy.db.LocalRepository package identifier
        @type idpackage: int
        @keyword self_check: also check inside the given package
            (idpackage) itself
        @type self_check: bool
        @return: tuple of length 2, composed by a dictionary with the
            following structure:
            {('KEY', 'SLOT': set([list of missing deps for the given key])}
            and a "plain" list (set) of missing dependencies
            set([list of missing dependencies])
        @rtype: tuple
        """
        rdepends = {}
        rdepends_plain = set()
        neededs = dbconn.retrieveNeeded(idpackage, extended = True)
        ldpaths = set(self.entropyTools.collect_linker_paths())
        deps_content = set()
        dependencies = self.get_deep_dependency_list(dbconn, idpackage,
            atoms = True)
        scope_cache = set()

        def update_depscontent(mycontent, dbconn, ldpaths):
            return set( \
                [x for x in mycontent if os.path.dirname(x) in ldpaths \
                and (dbconn.isNeededAvailable(os.path.basename(x)) > 0) ])

        def is_in_content(myneeded, content):
            for item in content:
                item = os.path.basename(item)
                if myneeded == item:
                    return True
            return False

        for dependency in dependencies:
            match = dbconn.atomMatch(dependency)
            if match[0] != -1:
                mycontent = dbconn.retrieveContent(match[0])
                deps_content |= update_depscontent(mycontent, dbconn, ldpaths)
                key, slot = dbconn.retrieveKeySlot(match[0])
                scope_cache.add((key, slot))

        key, slot = dbconn.retrieveKeySlot(idpackage)
        mycontent = dbconn.retrieveContent(idpackage)
        deps_content |= update_depscontent(mycontent, dbconn, ldpaths)
        scope_cache.add((key, slot))

        idpackages_cache = set()
        idpackage_map = {}
        idpackage_map_reverse = {}
        for needed, elfclass in neededs:
            data_solved = dbconn.resolveNeeded(needed, elfclass = elfclass,
                extended = True)
            data_size = len(data_solved)
            data_solved = set([x for x in data_solved if x[0] \
                not in idpackages_cache])
            if not data_solved or (data_size != len(data_solved)):
                continue

            if self_check:
                if is_in_content(needed, mycontent):
                    continue

            found = False
            for data in data_solved:
                if data[1] in deps_content:
                    found = True
                    break
            if not found:
                for data in data_solved:
                    r_idpackage = data[0]
                    key, slot = dbconn.retrieveKeySlot(r_idpackage)
                    if (key, slot) not in scope_cache:
                        if not dbconn.isSystemPackage(r_idpackage):
                            if not rdepends.has_key((needed, elfclass)):
                                rdepends[(needed, elfclass)] = set()
                            if not idpackage_map.has_key((needed, elfclass)):
                                idpackage_map[(needed, elfclass)] = set()
                            keyslot = "%s:%s" % (key, slot,)
                            obj = idpackage_map_reverse.setdefault(
                                keyslot, set())
                            obj.add((needed, elfclass,))
                            rdepends[(needed, elfclass)].add(keyslot)
                            idpackage_map[(needed, elfclass)].add(r_idpackage)
                            rdepends_plain.add(keyslot)
                        idpackages_cache.add(r_idpackage)

        # now reduce dependencies

        r_deplist = set()
        for key in idpackage_map:
            r_idpackages = idpackage_map.get(key)
            for r_idpackage in r_idpackages:
                r_deplist |= dbconn.retrieveDependencies(r_idpackage)

        r_keyslots = set()
        for r_dep in r_deplist:
            m_idpackage, m_rc = dbconn.atomMatch(r_dep)
            if m_rc != 0:
                continue
            keyslot = dbconn.retrieveKeySlotAggregated(m_idpackage)
            if keyslot in rdepends_plain:
                r_keyslots.add(keyslot)

        rdepends_plain -= r_keyslots
        for r_keyslot in r_keyslots:
            keys = [x for x in idpackage_map_reverse.get(keyslot, set()) if \
                x in rdepends]
            for key in keys:
                rdepends[key].discard(r_keyslot)
                if not rdepends[key]:
                    del rdepends[key]

        return rdepends, rdepends_plain

    def get_deep_dependency_list(self, dbconn, idpackage, atoms = False):
        """
        Service method which returns a complete, expanded list of dependencies
        for the given idpackage on the given entropy.db.LocalRepository
        "dbconn" instance.

        @param dbconn: entropy.db.LocalRepository instance which contains
            the given idpackage item.
        @type dbconn: entropy.db.LocalRepository instance
        @param idpackage: Entropy database package key
        @type idpackage: int
        @keyword atoms: !! return type modifier !! , make method returning
            a list of atom strings instead of list of db match tuples.
        @type atoms: bool
        @return: list of dependencies in form of matching tuple list
            ( [(idpackage, repoid,) ... ] ) or plain dependency list (if
            atom == True -- set([atom_string1, atom_string2, atom_string3])
        @rtype: list or set
        """
        mybuffer = self.Lifo()
        matchcache = set()
        depcache = set()
        mydeps = dbconn.retrieveDependencies(idpackage)
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

            my_idpackage, my_rc = dbconn.atomMatch(mydep)
            if atoms:
                matchcache.add(mydep)
            else:
                matchcache.add(my_idpackage)

            if my_idpackage != -1:
                owndeps = dbconn.retrieveDependencies(my_idpackage)
                for owndep in owndeps:
                    mybuffer.push(owndep)

            depcache.add(mydep)
            try:
                mydep = mybuffer.pop()
            except ValueError:
                break # stack empty

        # always discard -1 in set
        matchcache.discard(-1)
        return matchcache

    def __analyze_package_edb(self, pkg_path):
        """
        Check if the physical Entropy package file contains
        a valid Entropy embedded database.

        @param pkg_path: path to physical entropy package file
        @type pkg_path: string
        @return: package validity
        @rtype: bool
        """
        from entropy.db import LocalRepository, dbapi2
        fd, tmp_path = tempfile.mkstemp()
        extract_path = self.entropyTools.extract_edb(pkg_path, tmp_path)
        if extract_path is None:
            os.remove(tmp_path)
            os.close(fd)
            return False # error!
        try:
            dbc = LocalRepository(
                readOnly = False,
                dbFile = tmp_path,
                clientDatabase = True,
                dbname = 'qa_testing',
                xcache = False,
                indexing = False,
                OutputInterface = self.Output,
                skipChecks = False
            )
        except dbapi2.Error:
            os.remove(tmp_path)
            os.close(fd)
            return False

        valid = True
        try:
            dbc.validateDatabase()
        except SystemDatabaseError:
            valid = False

        if valid:
            try:
                for idpackage in dbc.listAllIdpackages():
                    dbc.retrieveContent(idpackage, extended = True,
                        formatted = True, insert_formatted = True)
            except dbapi2.Error:
                valid = False

        dbc.closeDB()
        os.remove(tmp_path)
        os.close(fd)

        return valid

    def entropy_package_checks(self, package_path):
        """
        Main method for the execution of QA tests on physical Entropy
        package files.

        @param package_path: path to physical Entropy package file path
        @type package_path: string
        @return: True, if all checks passed
        @rtype: bool
        """
        qa_methods = [self.__analyze_package_edb]
        for method in qa_methods:
            qa_rc = method(package_path)
            if not qa_rc:
                return False
        return True


class ErrorReportInterface:

    """

    Interface used by Entropy Client to remotely send errors via HTTP POST.
    Some anonymous info about the running system are collected and sent over,
    once the user gives the acknowledgement for this operation.
    User should be asked for valid credentials, such as name, surname and email.
    This has two advantages: block stupid and lazy people and make possible
    for Entropy developers to contact him/her back.
    Moreover, the same applies for a simple description. To improve the
    ability to debug an issue, it is also asked the user to describe his/her
    action prior to the error.

    Sample code:

        >>> from entropy.qa import ErrorReportInterface
        >>> error = ErrorReportInterface('http://url_for_http_post')
        >>> error.prepare('traceback_text', 'John Foo', 'john@foo.com',
                report_data = 'extra traceback info',
                description = 'I was installing foo!')
        >>> error.submit()

    """

    import entropy.tools as entropyTools
    def __init__(self, post_url):
        """
        ErrorReportInterface constructor.

        @param post_url: HTTP post url where to submit data
        @type post_url: string
        """
        from entropy.misc import MultipartPostHandler
        import urllib2
        self.url = post_url
        self.opener = urllib2.build_opener(MultipartPostHandler)
        self.generated = False
        self.params = {}

        sys_settings = SystemSettings()
        proxy_settings = sys_settings['system']['proxy']
        mydict = {}
        if proxy_settings['ftp']:
            mydict['ftp'] = proxy_settings['ftp']
        if proxy_settings['http']:
            mydict['http'] = proxy_settings['http']
        if mydict:
            mydict['username'] = proxy_settings['username']
            mydict['password'] = proxy_settings['password']
            self.entropyTools.add_proxy_opener(urllib2, mydict)
        else:
            # unset
            urllib2._opener = None

    def prepare(self, tb_text, name, email, report_data = "", description = ""):

        """
        This method must be called prior to submit(). It is used to prepare
        and collect system information before the submission.
        It is intentionally split from submit() to allow easy reimplementation.

        @param tb_text: Python traceback text to send
        @type tb_text: string
        @param name: submitter name
        @type name: string
        @param email: submitter email address
        @type email: string
        @keyword report_data: extra information
        @type report_data: string
        @keyword description: submitter action description
        @type description: string
        @return: None
        @rtype: None
        """

        import sys
        from entropy.tools import getstatusoutput
        self.params['arch'] = etpConst['currentarch']
        self.params['stacktrace'] = tb_text
        self.params['name'] = name
        self.params['email'] = email
        self.params['version'] = etpConst['entropyversion']
        self.params['errordata'] = report_data
        self.params['description'] = description
        self.params['arguments'] = ' '.join(sys.argv)
        self.params['uid'] = etpConst['uid']
        self.params['system_version'] = "N/A"
        if os.access(etpConst['systemreleasefile'], os.R_OK):
            f_rel = open(etpConst['systemreleasefile'], "r")
            self.params['system_version'] = f_rel.readline().strip()
            f_rel.close()

        self.params['processes'] = getstatusoutput('ps auxf')[1]
        self.params['lspci'] = getstatusoutput('/usr/sbin/lspci')[1]
        self.params['dmesg'] = getstatusoutput('dmesg')[1]
        self.params['locale'] = getstatusoutput('locale -v')[1]

        self.generated = True

    # params is a dict, key(HTTP post item name): value
    def submit(self):
        """
        Submit collected data remotely via HTTP POST.

        @raise PermissionDenied: when prepare() hasn't been called.
        @return: None
        @rtype: None
        """
        if self.generated:
            result = self.opener.open(self.url, self.params).read()
            if result.strip() == "1":
                return True
            return False
        else:
            mytxt = _("Not prepared yet")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))
