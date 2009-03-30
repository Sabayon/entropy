# -*- coding: utf-8 -*-
'''
    # DESCRIPTION:
    # Entropy Object Oriented Interface

    Copyright (C) 2007-2009 Fabio Erculiani

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation; either version 2 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
'''

import os
from entropy.const import etpConst
from entropy.output import blue, darkgreen, red, darkred, bold, purple, brown
from entropy.exceptions import *
from entropy.i18n import _

class QAInterface:

    import entropy.tools as entropyTools
    from entropy.misc import Lifo
    def __init__(self, OutputInterface):

        self.Output = OutputInterface

        if not hasattr(self.Output,'updateProgress'):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))
        elif not callable(self.Output.updateProgress):
            mytxt = _("Output interface passed doesn't have the updateProgress method")
            raise IncorrectParameter("IncorrectParameter: %s" % (mytxt,))

    def test_depends_linking(self, idpackages, dbconn, repo = etpConst['officialrepositoryid']):

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
            scan_msg = "%s, %s:" % (blue(_("scanning for broken depends")),darkgreen(atom),)
            self.Output.updateProgress(
                "[repo:%s] %s" % (
                    darkgreen(repo),
                    scan_msg,
                ),
                importance = 1,
                type = "info",
                header = blue(" @@ "),
                back = True,
                count = (count,maxcount,)
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
                    count = (count,maxcount,)
                )
                mycontent = dbconn.retrieveContent(mydepend)
                mybreakages = self.content_test(mycontent)
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
                    count = (count,maxcount,)
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


    def scan_missing_dependencies(self, idpackages, dbconn, ask = True,
            self_check = False, repo = etpConst['officialrepositoryid'],
            black_list = None, black_list_adder = None):

        if not isinstance(black_list,set):
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
            if not atom: continue
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
                count = (count,maxcount,)
            )
            missing_extended, missing = self.get_missing_rdepends(dbconn, idpackage, self_check = self_check)
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
                count = (count,maxcount,)
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
                rc = self.Output.askQuestion(_("Do you want to add them?"))
                if rc == "No":
                    continue
                rc = self.Output.askQuestion(_("Selectively?"))
                if rc == "Yes":
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
                        rc = self.Output.askQuestion(_("Want to add?"))
                        if rc == "Yes":
                            newmissing.add(dependency)
                        else:
                            rc = self.Output.askQuestion(_("Want to blacklist?"))
                            if rc == "Yes":
                                new_blacklist.add(dependency)
                    if new_blacklist and (black_list_adder != None):
                        black_list_adder(new_blacklist, repo = repo)
                    missing = newmissing
            if missing:
                taint = True
                dbconn.insertDependencies(idpackage,missing)
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
                    count = (count,maxcount,)
                )

        return taint

    def content_test(self, mycontent):

        def is_contained(needed, content):
            for item in content:
                if os.path.basename(item) == needed:
                    return True
            return False

        mylibs = {}
        for myfile in mycontent:
            myfile = myfile.encode('raw_unicode_escape')
            if not os.access(myfile,os.R_OK):
                continue
            if not os.path.isfile(myfile):
                continue
            if not self.entropyTools.is_elf_file(myfile):
                continue
            mylibs[myfile] = self.entropyTools.read_elf_dynamic_libraries(myfile)

        broken_libs = {}
        for mylib in mylibs:
            for myneeded in mylibs[mylib]:
                # is this inside myself ?
                if is_contained(myneeded, mycontent):
                    continue
                found = self.resolve_dynamic_library(myneeded, mylib)
                if found:
                    continue
                if not broken_libs.has_key(mylib):
                    broken_libs[mylib] = set()
                broken_libs[mylib].add(myneeded)

        return broken_libs

    def resolve_dynamic_library(self, library, requiring_executable):

        def do_resolve(mypaths):
            found_path = None
            for mypath in mypaths:
                mypath = os.path.join(etpConst['systemroot']+mypath,library)
                if not os.access(mypath,os.R_OK):
                    continue
                if os.path.isdir(mypath):
                    continue
                if not self.entropyTools.is_elf_file(mypath):
                    continue
                found_path = mypath
                break
            return found_path

        mypaths = self.entropyTools.collect_linker_paths()
        found_path = do_resolve(mypaths)

        if not found_path:
            mypaths = self.entropyTools.read_elf_linker_paths(requiring_executable)
            found_path = do_resolve(mypaths)

        return found_path

    def get_missing_rdepends(self, dbconn, idpackage, self_check = False):

        rdepends = {}
        rdepends_plain = set()
        neededs = dbconn.retrieveNeeded(idpackage, extended = True)
        ldpaths = set(self.entropyTools.collect_linker_paths())
        deps_content = set()
        dependencies = self._get_deep_dependency_list(dbconn, idpackage, atoms = True)
        scope_cache = set()

        def update_depscontent(mycontent, dbconn, ldpaths):
            return set( \
                    [   x for x in mycontent if os.path.dirname(x) in ldpaths \
                        and (dbconn.isNeededAvailable(os.path.basename(x)) > 0) ] \
                    )

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
                scope_cache.add((key,slot))

        key, slot = dbconn.retrieveKeySlot(idpackage)
        mycontent = dbconn.retrieveContent(idpackage)
        deps_content |= update_depscontent(mycontent, dbconn, ldpaths)
        scope_cache.add((key,slot))

        idpackages_cache = set()
        idpackage_map = {}
        idpackage_map_reverse = {}
        for needed, elfclass in neededs:
            data_solved = dbconn.resolveNeeded(needed,elfclass)
            data_size = len(data_solved)
            data_solved = set([x for x in data_solved if x[0] not in idpackages_cache])
            if not data_solved or (data_size != len(data_solved)):
                continue

            if self_check:
                if is_in_content(needed,mycontent):
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
                    if (key,slot) not in scope_cache:
                        if not dbconn.isSystemPackage(r_idpackage):
                            if not rdepends.has_key((needed,elfclass)):
                                rdepends[(needed,elfclass)] = set()
                            if not idpackage_map.has_key((needed,elfclass)):
                                idpackage_map[(needed,elfclass)] = set()
                            keyslot = "%s:%s" % (key,slot,)
                            if not idpackage_map_reverse.has_key(keyslot):
                                idpackage_map_reverse[keyslot] = set()
                            idpackage_map_reverse[keyslot].add((needed,elfclass))
                            rdepends[(needed,elfclass)].add(keyslot)
                            idpackage_map[(needed,elfclass)].add(r_idpackage)
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
            if m_rc != 0: continue
            keyslot = dbconn.retrieveKeySlotAggregated(m_idpackage)
            if keyslot in rdepends_plain:
                r_keyslots.add(keyslot)

        rdepends_plain -= r_keyslots
        for r_keyslot in r_keyslots:
            keys = [x for x in idpackage_map_reverse.get(keyslot,set()) if x in rdepends]
            for key in keys:
                rdepends[key].discard(r_keyslot)
                if not rdepends[key]:
                    del rdepends[key]

        return rdepends, rdepends_plain

    def _get_deep_dependency_list(self, dbconn, idpackage, atoms = False):

        mybuffer = self.Lifo()
        matchcache = set()
        depcache = set()
        mydeps = dbconn.retrieveDependencies(idpackage)
        for mydep in mydeps:
            mybuffer.push(mydep)
        mydep = mybuffer.pop()

        while mydep:

            if mydep in depcache:
                mydep = mybuffer.pop()
                continue

            mymatch = dbconn.atomMatch(mydep)
            if atoms:
                matchcache.add(mydep)
            else:
                matchcache.add(mymatch[0])

            if mymatch[0] != -1:
                owndeps = dbconn.retrieveDependencies(mymatch[0])
                for owndep in owndeps: mybuffer.push(owndep)

            depcache.add(mydep)
            mydep = mybuffer.pop()

        if atoms and -1 in matchcache:
            matchcache.discard(-1)

        return matchcache

class ErrorReportInterface:

    import entropy.tools as entropyTools
    def __init__(self, post_url = etpConst['handlers']['errorsend']):
        from entropy.misc import MultipartPostHandler
        import urllib2
        self.url = post_url
        self.opener = urllib2.build_opener(MultipartPostHandler)
        self.generated = False
        self.params = {}

        mydict = {}
        if etpConst['proxy']['ftp']:
            mydict['ftp'] = etpConst['proxy']['ftp']
        if etpConst['proxy']['http']:
            mydict['http'] = etpConst['proxy']['http']
        if mydict:
            mydict['username'] = etpConst['proxy']['username']
            mydict['password'] = etpConst['proxy']['password']
            self.entropyTools.add_proxy_opener(urllib2,mydict)
        else:
            # unset
            urllib2._opener = None

    def prepare(self, tb_text, name, email, report_data = "", description = ""):

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
        if os.access(etpConst['systemreleasefile'],os.R_OK):
            f = open(etpConst['systemreleasefile'],"r")
            self.params['system_version'] = f.readlines()
            f.close()

        self.params['processes'] = getstatusoutput('ps auxf')[1]
        self.params['lspci'] = getstatusoutput('/usr/sbin/lspci')[1]
        self.params['dmesg'] = getstatusoutput('dmesg')[1]
        self.params['locale'] = getstatusoutput('locale -v')[1]
        self.params['stacktrace'] += "\n\n"+self.params['locale'] # just for a while, won't hurt

        self.generated = True

    # params is a dict, key(HTTP post item name): value
    def submit(self):
        if self.generated:
            result = self.opener.open(self.url, self.params).read()
            if result.strip() == "1":
                return True
            return False
        else:
            mytxt = _("Not prepared yet")
            raise PermissionDenied("PermissionDenied: %s" % (mytxt,))


