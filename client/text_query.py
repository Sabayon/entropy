#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy database query tools and library

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
from entropy.const import etpRepositories, etpUi
from entropy.output import darkgreen, darkred, red, blue, \
    brown, purple, bold, print_info, print_error, print_generic
from entropy.client.interfaces import Client as EquoInterface
from entropy.i18n import _


def query(options):

    rc_status = 0

    if not options:
        return -10

    do_deep = False
    myopts = []
    for opt in options:
        if (opt == "--deep"):
            do_deep = True
        elif opt.startswith("--"):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return -10
        else:
            if not opt.startswith("-"):
                myopts.append(opt)

    if not myopts:
        return -10

    if myopts[0] == "installed":
        rc_status = searchInstalledPackages(myopts[1:])

    elif myopts[0] == "belongs":
        rc_status = searchBelongs(myopts[1:])

    elif myopts[0] == "changelog":
        rc_status = searchChangeLog(myopts[1:])

    elif myopts[0] == "depends":
        rc_status = searchDepends(myopts[1:])

    elif myopts[0] == "files":
        rc_status = searchFiles(myopts[1:])

    elif myopts[0] == "needed":
        rc_status = searchNeeded(myopts[1:])

    elif myopts[0] == "required":
        rc_status = searchRequired(myopts[1:])

    elif myopts[0] == "removal":
        rc_status = searchRemoval(myopts[1:], deep = do_deep)

    elif myopts[0] == "tags":
        rc_status = searchTaggedPackages(myopts[1:])

    elif myopts[0] == "sets":
        rc_status = searchPackageSets(myopts[1:])

    elif myopts[0] == "license":
        rc_status = searchLicenses(myopts[1:])

    elif myopts[0] == "slot":
        if (len(myopts) > 1):
            rc_status = searchSlottedPackages(myopts[1:])

    elif myopts[0] == "orphans":
        rc_status = searchOrphans()

    elif myopts[0] == "list":
        mylistopts = options[1:]
        if len(mylistopts) > 0:
            if mylistopts[0] == "installed":
                rc_status = searchInstalled()
    elif myopts[0] == "description":
        rc_status = searchDescription(myopts[1:])
    else:
        rc_status = -10

    return rc_status


def searchInstalledPackages(packages, idreturn = False, dbconn = None,
    Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    if (not idreturn) and (not etpUi['quiet']):
        print_info(brown(" @@ ")+darkgreen("%s..." % (_("Searching"),) ))

    clientDbconn = dbconn
    if not dbconn:
        clientDbconn = Equo.clientDbconn

    pkg_data = set() # when idreturn is True
    for package in packages:
        slot = Equo.entropyTools.dep_getslot(package)
        tag = Equo.entropyTools.dep_gettag(package)
        package = Equo.entropyTools.remove_slot(package)
        package = Equo.entropyTools.remove_tag(package)

        idpackages = clientDbconn.searchPackages(package, slot = slot,
            tag = tag, just_id = True)
        if not idpackages:
            continue
        if idreturn:
            pkg_data |= set(idpackages)
            continue

        for idpackage in idpackages:
            printPackageInfo(idpackage, clientDbconn, clientSearch = True,
                Equo = Equo, extended = etpUi['verbose'])

        if not etpUi['quiet']:
            print_info(blue(" %s: " % (_("Keyword"),) ) + bold("\t"+package))
            print_info(blue(" %s:   " % (_("Found"),) ) + \
                bold("\t" + str(len(idpackages))) + \
                red(" %s" % (_("entries"),)))

    if idreturn:
        return pkg_data
    return 0


def searchBelongs(files, idreturn = False, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Belong Search"),)))

    clientDbconn = dbconn
    if not dbconn:
        clientDbconn = Equo.clientDbconn

    pkg_data = set() # when idreturn is True
    results = {}
    flatresults = {}
    for xfile in files:
        like = False
        if xfile.find("*") != -1:
            xfile.replace("*","%")
            like = True
        results[xfile] = set()
        idpackages = clientDbconn.searchBelongs(xfile, like)
        for idpackage in idpackages:
            if not flatresults.get(idpackage):
                results[xfile].add(idpackage)
                flatresults[idpackage] = True

    if results:
        for result in results:

            # print info
            xfile = result
            result = results[result]
            if idreturn:
                pkg_data |= result
                continue

            for idpackage in result:
                if etpUi['quiet']:
                    print_generic(clientDbconn.retrieveAtom(idpackage))
                else:
                    printPackageInfo(idpackage, clientDbconn,
                        clientSearch = True, Equo = Equo,
                        extended = etpUi['verbose'])
            if not etpUi['quiet']:
                print_info(blue(" %s: " % (_("Keyword"),) ) + bold("\t"+xfile))
                print_info(blue(" %s:   " % (_("Found"),) ) + \
                    bold("\t" + str(len(result))) + red(" entries"))

    if idreturn:
        return pkg_data
    return 0


def searchChangeLog(atoms, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("ChangeLog Search"),)))

    for atom in atoms:
        if dbconn != None:
            idpackage, rc = dbconn.atomMatch(atom)
            if rc != 0:
                print_info(darkred("%s: %s" % (_("No match for"), bold(atom),)))
                continue
        else:
            idpackage, r_id = Equo.atom_match(atom)
            if idpackage == -1:
                print_info(darkred("%s: %s" % (_("No match for"), bold(atom),)))
                continue
            dbconn = Equo.open_repository(r_id)

        db_atom = dbconn.retrieveAtom(idpackage)
        if etpUi['quiet']: print_generic("%s :" % (db_atom,))
        else: print_info(blue(" %s: " % (_("Atom"),) ) + bold("\t"+db_atom))

        changelog = dbconn.retrieveChangelog(idpackage)
        if not changelog:
            print_generic(_("No ChangeLog available"))
        else:
            print_generic(changelog)
        print "="*80

    return 0


def searchDepends(atoms, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Reverse Dependencies Search"),) ))

    match_repo = True
    if not hasattr(Equo,'atom_match'):
        match_repo = False

    clientDbconn = dbconn
    if not dbconn:
        clientDbconn = Equo.clientDbconn

    for atom in atoms:

        result = clientDbconn.atomMatch(atom)
        matchInRepo = False
        repoMasked = False

        if (result[0] == -1) and match_repo:
            matchInRepo = True
            result = Equo.atom_match(atom)

        if (result[0] == -1) and match_repo:
            result = Equo.atom_match(atom, packagesFilter = False)
            if result[0] != -1:
                repoMasked = True

        if (result[0] != -1):

            dbconn = clientDbconn
            if matchInRepo:
                dbconn = Equo.open_repository(result[1])

            found_atom = dbconn.retrieveAtom(result[0])
            if repoMasked:
                idpackage_masked, idmasking_reason = dbconn.idpackageValidator(
                    result[0])

            searchResults = dbconn.retrieveDepends(result[0])
            for idpackage in searchResults:
                printPackageInfo(idpackage, dbconn, clientSearch = True,
                    strictOutput = etpUi['quiet'], Equo = Equo,
                    extended = etpUi['verbose'])

            # print info
            if not etpUi['quiet']:
                print_info(blue(" %s: " % (_("Keyword"),) ) + bold("\t"+atom))
                print_info(blue(" %s: " % (_("Matched"),) ) + \
                    bold("\t"+found_atom))

                masking_reason = ''
                if repoMasked:
                    masking_reason = ", %s" % (
                        Equo.SystemSettings['pkg_masking_reasons'].get(
                            idmasking_reason),
                    )
                print_info(blue(" %s: " % (_("Masked"),) ) + \
                    bold("\t"+str(repoMasked)) + masking_reason)

                if matchInRepo:
                    where = " %s %s" % (_("from repository"), result[1],)
                else:
                    where = " %s" % (_("from installed packages database"),)

                print_info( blue(" %s:   " % (_("Found"),) ) + \
                    bold("\t"+str(len(searchResults))) + \
                    red(" %s" % (_("entries"),)) + where)

    return 0

def searchNeeded(atoms, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()


    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Needed Search"),) ))

    pkg_data = set()
    clientDbconn = dbconn
    if not dbconn:
        clientDbconn = Equo.clientDbconn

    for atom in atoms:
        match = clientDbconn.atomMatch(atom)
        if match[0] != -1:
            # print info
            myatom = clientDbconn.retrieveAtom(match[0])
            myneeded = clientDbconn.retrieveNeeded(match[0])
            for needed in myneeded:
                if etpUi['quiet']:
                    print_generic(needed)
                else:
                    print_info(blue("       # ") + red(str(needed)))
            if not etpUi['quiet']:
                print_info(blue("     %s: " % (_("Atom"),)) + bold("\t"+myatom))
                print_info(blue(" %s:   " % (_("Found"),)) + \
                    bold("\t"+str(len(myneeded))) + \
                    red(" %s" % (_("libraries"),)))

    return 0

def searchRequired(libraries, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()


    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Required Search"),)))

    clientDbconn = dbconn
    if not dbconn:
        clientDbconn = Equo.clientDbconn

    for library in libraries:
        search_lib = library.replace("*","%")
        results = clientDbconn.searchNeeded(search_lib, like = True)
        for result in results:

            if etpUi['quiet']:
                print_generic(clientDbconn.retrieveAtom(result))
                continue

            printPackageInfo(result, clientDbconn, clientSearch = True,
                strictOutput = True, Equo = Equo,
                extended = etpUi['verbose'])

        if not etpUi['quiet']:
            print_info(blue(" %s: " % (_("Library"),)) + bold("\t"+library))
            print_info(blue(" %s:   " % (_("Found"),) ) + \
                bold("\t"+str(len(results))) + red(" %s" % (_("packages"),) ))

    return 0

def searchEclass(eclasses, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()


    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Eclass Search"),)))

    clientDbconn = dbconn
    if not dbconn:
        clientDbconn = Equo.clientDbconn

    for eclass in eclasses:
        matches = clientDbconn.searchEclassedPackages(eclass, atoms = True)
        for match in matches:
            # print info
            myatom = match[0]
            idpackage = match[1]
            if etpUi['quiet']:
                print_generic(myatom)
                continue

            printPackageInfo(idpackage, clientDbconn, clientSearch = True,
                Equo = Equo, extended = etpUi['verbose'],
                strictOutput = not etpUi['verbose'])

        if not etpUi['quiet']:
            print_info(blue(" %s:   " % (_("Found"),)) + \
                bold("\t"+str(len(matches))) + red(" %s" % (_("packages"),) ))

    return 0

def searchFiles(atoms, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("Files Search..."))

    if not dbconn:
        results = searchInstalledPackages(atoms, idreturn = True)
        clientDbconn = Equo.clientDbconn
    else:
        results = searchInstalledPackages(atoms, idreturn = True,
        dbconn = dbconn, Equo = Equo)
        clientDbconn = dbconn

    for result in results:
        if result == -1:
            continue

        files = clientDbconn.retrieveContent(result)
        atom = clientDbconn.retrieveAtom(result)
        files = sorted(files)
        if etpUi['quiet']:
            for xfile in files:
                print_generic(xfile)
        else:
            for xfile in files:
                print_info(blue(" ### ") + red(xfile))

        if not etpUi['quiet']:
            print_info(blue(" %s: " % (_("Package"),)) + bold("\t"+atom))
            print_info(blue(" %s:   " % (_("Found"),)) + \
                bold("\t"+str(len(files))) + red(" %s" % (_("files"),)))

    return 0



def searchOrphans(Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    if (not etpUi['quiet']):
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Orphans Search"),)))

    clientDbconn = Equo.clientDbconn

    # start to list all files on the system:
    dirs = Equo.SystemSettings['system_dirs']
    filepath = Equo.entropyTools.get_random_temp_file()
    if os.path.isfile(filepath):
        os.remove(filepath)
    tdbconn = Equo.open_generic_database(filepath)
    tdbconn.initializeDatabase()
    tdbconn.dropAllIndexes()
    lib64_str = "/usr/lib64"
    lib64_len = len(lib64_str)

    count = 0
    for xdir in dirs:
        try:
            wd = os.walk(xdir)
        except RuntimeError: # maximum recursion?
            continue
        for currentdir, subdirs, files in wd:
            foundFiles = {}
            for filename in files:

                # failter python compiled objects?
                if filename.endswith(".pyo") or \
                    filename.endswith(".pyc") or \
                    filename == '.keep':
                    continue

                filename = os.path.join(currentdir, filename)
                if filename.endswith(".ph") and \
                    (filename.startswith("/usr/lib/perl") or \
                    filename.startswith("/usr/lib64/perl")):
                    continue

                mask = [x for x in Equo.SystemSettings['system_dirs_mask'] if \
                    filename.startswith(x)]
                if mask:
                    continue
                count += 1
                if not etpUi['quiet'] and ((count == 0) or (count % 500 == 0)):
                    count = 0
                    print_info(red(" @@ ")+blue("%s: " % (_("Analyzing"),)) + \
                        bold(unicode(filename[:50],'raw_unicode_escape')+"..."),
                        back = True)
                foundFiles[filename] = "obj"

            if foundFiles:
                tdbconn.insertContent(1, foundFiles)

    tdbconn.commitChanges()
    tdbconn.cursor.execute('select count(file) from content')
    totalfiles = tdbconn.cursor.fetchone()[0]

    if not etpUi['quiet']:
        print_info(red(" @@ ") + blue("%s: " % (_("Analyzed directories"),) )+ \
            ' '.join(Equo.SystemSettings['system_dirs']))
        print_info(red(" @@ ") + blue("%s: " % (_("Masked directories"),) ) + \
            ' '.join(Equo.SystemSettings['system_dirs_mask']))
        print_info(red(" @@ ")+blue("%s: " % (
            _("Number of files collected on the filesystem"),) ) + \
            bold(str(totalfiles)))
        print_info(red(" @@ ")+blue("%s..." % (
            _("Now looking into Installed Packages database"),)))


    idpackages = clientDbconn.listAllIdpackages()
    length = str(len(idpackages))
    count = 0

    # create index on content
    tdbconn.cursor.execute(
        "CREATE INDEX IF NOT EXISTS contentindex_file ON content ( file );")

    def gen_cont(idpackage):
        for path in clientDbconn.retrieveContent(idpackage):
            if path.startswith(lib64_str):
                path = "/usr/lib%s" % (path[lib64_len:],)
            yield (path,)

    for idpackage in idpackages:

        if not etpUi['quiet']:
            count += 1
            atom = clientDbconn.retrieveAtom(idpackage)
            txt = "["+str(count)+"/"+length+"] "
            print_info(red(" @@ ") + blue("%s: " % (
                _("Intersecting with content of the package"),) ) + txt + \
                bold(str(atom)), back = True)

        # remove from foundFiles
        tdbconn.cursor.executemany('delete from content where file = (?)',
            gen_cont(idpackage))

    tdbconn.commitChanges()
    tdbconn.cursor.execute('select count(file) from content')
    orpanedfiles = tdbconn.cursor.fetchone()[0]

    if not etpUi['quiet']:
        print_info(red(" @@ ") + blue("%s: " % (
            _("Intersection completed. Showing statistics"),) ))
        print_info(red(" @@ ") + blue("%s: " % (
            _("Number of total files"),) ) + bold(str(totalfiles)))
        print_info(red(" @@ ") + blue("%s: " % (
            _("Number of matching files"),) ) + \
            bold(str(totalfiles - orpanedfiles)))
        print_info(red(" @@ ") + blue("%s: " % (
            _("Number of orphaned files"),) ) + bold(str(orpanedfiles)))

    tdbconn.cursor.execute('select file from content order by file desc')
    if not etpUi['quiet']:
        fname = "/tmp/equo-orphans.txt"
        f = open(fname,"w")
        print_info(red(" @@ ")+blue("%s: " % (_
            ("Writing file to disk"),)) + bold(fname))

    tdbconn.connection.text_factory = lambda x: unicode(x, "raw_unicode_escape")
    myfile = tdbconn.cursor.fetchone()

    sizecount = 0
    while myfile:

        myfile = str(myfile[0].encode('raw_unicode_escape'))
        mysize = 0
        try:
            mysize += os.stat(myfile)[6]
        except OSError:
            mysize = 0
        sizecount += mysize

        if not etpUi['quiet']:
            f.write(myfile+"\n")
        else:
            print_generic(myfile)

        myfile = tdbconn.cursor.fetchone()

    humansize = Equo.entropyTools.bytes_into_human(sizecount)
    if not etpUi['quiet']:
        print_info(red(" @@ ") + \
            blue("%s: " % (_("Total wasted space"),) ) + bold(humansize))
        f.flush()
        f.close()
    else:
        print_generic(humansize)

    tdbconn.closeDB()
    if os.path.isfile(filepath):
        os.remove(filepath)

    return 0


def searchRemoval(atoms, deep = False, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    clientDbconn = Equo.clientDbconn

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Removal Search"),) ))

    found_atoms = [clientDbconn.atomMatch(x) for x in atoms]
    found_atoms = [x[0] for x in found_atoms if x[1] == 0]

    if not found_atoms:
        print_error(red("%s." % (_("No packages found"),) ))
        return 127

    removal_queue = []
    if not etpUi['quiet']:
        print_info(red(" @@ ") + blue("%s..." % (
            _("Calculating removal dependencies, please wait"),) ), back = True)
    treeview = Equo.generate_depends_tree(found_atoms, deep = deep)
    treelength = len(treeview[0])
    if treelength > 1:
        treeview = treeview[0]
        for dep_el in range(treelength)[::-1]:
            for dep_sub_el in treeview[dep_el]:
                removal_queue.append(dep_sub_el)

    if removal_queue:
        if not etpUi['quiet']:
            print_info(red(" @@ ") + \
                blue("%s:" % (
                _("These are the packages that would added to the removal queue"),)))

        totalatoms = str(len(removal_queue))
        atomscounter = 0

        for idpackage in removal_queue:

            atomscounter += 1
            rematom = clientDbconn.retrieveAtom(idpackage)
            if etpUi['quiet']:
                print_generic(rematom)
                continue

            installedfrom = clientDbconn.retrievePackageFromInstalledTable(
                idpackage)
            repo_info = bold("[") + red("%s: " % (_("from"),)) + \
                brown(installedfrom)+bold("]")
            stratomscounter = str(atomscounter)
            while len(stratomscounter) < len(totalatoms):
                stratomscounter = " "+stratomscounter
            print_info("   # " + red("(") + bold(stratomscounter) + "/" + \
                blue(str(totalatoms)) + red(")") + repo_info + " " + \
                blue(rematom))

    return 0



def searchInstalled(Equo = None, dbconn = None):

    if Equo == None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Installed Search"),)))

    clientDbconn = Equo.clientDbconn
    if dbconn:
        clientDbconn = dbconn

    inst_packages = clientDbconn.listAllPackages(order_by = "atom")

    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue("%s:" % (
            _("These are the installed packages"),) ))

    for atom, idpackage, branch in inst_packages:
        if not etpUi['verbose']:
            atom = Equo.entropyTools.dep_getkey(atom)
        branchinfo = ""
        sizeinfo = ""
        if etpUi['verbose']:
            branchinfo = darkgreen(" [")+red(branch)+darkgreen("] ")
            mysize = clientDbconn.retrieveOnDiskSize(idpackage)
            mysize = Equo.entropyTools.bytes_into_human(mysize)
            sizeinfo = brown(" [")+purple(mysize)+brown("]")
        if not etpUi['quiet']:
            print_info(red("  # ") + blue(str(idpackage)) + sizeinfo + \
                branchinfo + " " + atom)
        else:
            print_generic(atom)

    return 0


def searchPackage(packages, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    foundPackages = {}

    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Searching"),) ))
    # search inside each available database
    repoNumber = 0
    found = False
    for repo in Equo.validRepositories:
        foundPackages[repo] = {}
        repoNumber += 1

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repoNumber)) + \
                bold(" " + etpRepositories[repo]['description']))

        dbconn = Equo.open_repository(repo)
        for package in packages:
            slot = Equo.entropyTools.dep_getslot(package)
            tag = Equo.entropyTools.dep_gettag(package)
            package = Equo.entropyTools.remove_slot(package)
            package = Equo.entropyTools.remove_tag(package)

            try:

                result = dbconn.searchPackages(package, slot = slot,
                    tag = tag)
                if not result: # look for provide
                    result = dbconn.searchProvide(package, slot = slot,
                        tag = tag)
                if result:

                    foundPackages[repo][package] = result
                    found = True
                    for pkg in foundPackages[repo][package]:
                        printPackageInfo(pkg[1], dbconn, Equo = Equo,
                        extended = etpUi['verbose'])

                    if not etpUi['quiet']:
                        found_len = len(foundPackages[repo][package])
                        print_info(blue(" %s: " % (_("Keyword"),) ) + \
                            bold("\t"+package))
                        print_info(blue(" %s:   " % (_("Found"),) ) + \
                            bold("\t" + str(found_len)) + \
                            red(" %s" % (_("entries"),) ))

            except Equo.dbapi2.DatabaseError:
                continue

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def matchPackage(packages, multiMatch = False, multiRepo = False,
    showRepo = False, showDesc = False, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Matching"),) ),
            back = True)
    found = False

    for package in packages:

        if not etpUi['quiet']:
            print_info(blue("  # ")+bold(package))

        match = Equo.atom_match(package, multiMatch = multiMatch,
            multiRepo = multiRepo, packagesFilter = False)
        if match[1] != 1:

            if not multiMatch:
                if multiRepo:
                    matches = match[0]
                else:
                    matches = [match]
            else:
                matches = match[0]

            for match in matches:
                dbconn = Equo.open_repository(match[1])
                printPackageInfo(match[0], dbconn, showRepoOnQuiet = showRepo,
                    showDescOnQuiet = showDesc, Equo = Equo,
                    extended = etpUi['verbose'])
                found = True

            if not etpUi['quiet']:
                print_info(blue(" %s: " % (
                    _("Keyword"),) ) + bold("\t"+package))
                print_info(blue(" %s:   " % (_("Found"),) ) + \
                    bold("\t"+str(len(matches)))+red(" %s" % (_("entries"),) ))

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def searchSlottedPackages(slots, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    dbclose = True
    if dbconn:
        dbclose = False

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Slot Search"),) ))

    # search inside each available database
    repoNumber = 0
    for repo in Equo.validRepositories:
        repoNumber += 1

        if not etpUi['quiet']:
            print_info(blue("  #"+str(repoNumber)) + \
                bold(" " + etpRepositories[repo]['description']))

        if dbclose:
            dbconn = Equo.open_repository(repo)

        for slot in slots:

            results = dbconn.searchSlottedPackages(slot, atoms = True)
            for result in results:
                found = True
                printPackageInfo(result[1], dbconn, Equo = Equo,
                    extended = etpUi['verbose'], strictOutput = etpUi['quiet'])

            if not etpUi['quiet']:
                print_info(blue(" %s: " % (_("Keyword"),) ) + bold("\t"+slot))
                print_info(blue(" %s:   " % (_("Found"),) ) + \
                    bold("\t" + str(len(results))) + \
                    red(" %s" % (_("entries"),) ))

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def searchPackageSets(items, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (
            _("Package Set Search"),)))

    if not items:
        items.append('*')

    matchNumber = 0
    for item in items:
        results = Equo.package_set_search(item)
        for repo, set_name, set_data in results:
            matchNumber += 1
            found = True
            if not etpUi['quiet']:
                print_info(blue("  #" + str(matchNumber)) + \
                    bold(" " + set_name))
                elements = sorted(set_data)
                for element in elements:
                    print_info(brown("    "+element))

        if not etpUi['quiet']:
            print_info(blue(" %s: " % (_("Keyword"),)) + bold("\t"+item))
            print_info(blue(" %s:   " % (_("Found"),)) + \
                bold("\t" + str(matchNumber)) + red(" %s" % (_("entries"),)))

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def searchTaggedPackages(tags, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    dbclose = True
    if dbconn:
        dbclose = False

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Tag Search"),)))

    repoNumber = 0
    for repo in Equo.validRepositories:
        repoNumber += 1

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repoNumber)) + \
                bold(" " + etpRepositories[repo]['description']))

        if dbclose:
            dbconn = Equo.open_repository(repo)

        for tag in tags:
            results = dbconn.searchTaggedPackages(tag, atoms = True)
            found = True
            for result in results:
                printPackageInfo(result[1], dbconn, Equo = Equo,
                    extended = etpUi['verbose'], strictOutput = etpUi['quiet'])

            if not etpUi['quiet']:
                print_info(blue(" %s: " % (_("Keyword"),)) + \
                    bold("\t"+tag))
                print_info(blue(" %s:   " % (_("Found"),)) + \
                    bold("\t" + str(len(results))) + \
                    red(" %s" % (_("entries"),)))

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def searchLicenses(licenses, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    dbclose = True
    if dbconn:
        dbclose = False

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("License Search"),)))

    # search inside each available database
    repoNumber = 0
    for repo in Equo.validRepositories:
        repoNumber += 1

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repoNumber)) + \
                bold(" " + etpRepositories[repo]['description']))

        if dbclose:
            dbconn = Equo.open_repository(repo)

        for mylicense in licenses:

            results = dbconn.searchLicenses(mylicense, atoms = True)
            if not results:
                continue
            found = True
            for result in results:
                printPackageInfo(result[1], dbconn, Equo = Equo,
                    extended = etpUi['verbose'], strictOutput = etpUi['quiet'])

            if not etpUi['quiet']:
                print_info(blue(" %s: " % (_("Keyword"),)) + bold("\t" + \
                    mylicense))
                print_info(blue(" %s:   " % (_("Found"),)) + \
                    bold("\t" + str(len(results))) + \
                    red(" %s" % (_("entries"),) ))

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def searchDescription(descriptions, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Description Search"),) ))

    repo_number = 0
    for repo in Equo.validRepositories:
        repo_number += 1

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repo_number)) + \
                bold(" " + etpRepositories[repo]['description']))

        dbconn = Equo.open_repository(repo)
        descdata = searchDescriptions(descriptions, dbconn, Equo = Equo)
        if descdata:
            found = True

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def searchDescriptions(descriptions, dbconn, Equo = None):

    mydescdata = {}
    for desc in descriptions:

        result = dbconn.searchPackagesByDescription(desc)
        if not result: continue

        mydescdata[desc] = result
        for pkg in mydescdata[desc]:
            idpackage = pkg[1]
            if (etpUi['quiet']):
                print_generic(dbconn.retrieveAtom(idpackage))
            else:
                printPackageInfo(idpackage, dbconn, Equo = Equo,
                    extended = etpUi['verbose'], strictOutput = etpUi['quiet'])

        if not etpUi['quiet']:
            print_info(blue(" %s: " % (_("Keyword"),) ) + bold("\t"+desc))
            print_info(blue(" %s:   " % (_("Found"),) ) + \
                bold("\t" + str(len(mydescdata[desc]))) + \
                red(" %s" % (_("entries"),) ))

    return mydescdata

def printPackageInfo(idpackage, dbconn, clientSearch = False,
    strictOutput = False, extended = False, Equo = None,
    showRepoOnQuiet = False, showDescOnQuiet = False):

    if Equo == None:
        Equo = EquoInterface()

    # now fetch essential info
    pkgatom = dbconn.retrieveAtom(idpackage)
    if etpUi['quiet']:
        repoinfo = ''
        desc = ''
        if showRepoOnQuiet:
            repoinfo = "[%s] " % (dbconn.dbname,)
        if showDescOnQuiet:
            desc = ' %s' % (dbconn.retrieveDescription(idpackage),)
        print_generic("%s%s%s" % (repoinfo, pkgatom, desc,))
        return

    if not strictOutput:
        pkgname = dbconn.retrieveName(idpackage)
        pkgcat = dbconn.retrieveCategory(idpackage)
        pkglic = dbconn.retrieveLicense(idpackage)
        pkgsize = dbconn.retrieveSize(idpackage)
        pkgbin = dbconn.retrieveDownloadURL(idpackage)
        pkgflags = dbconn.retrieveCompileFlags(idpackage)
        pkgkeywords = dbconn.retrieveKeywords(idpackage)
        pkgdigest = dbconn.retrieveDigest(idpackage)
        mydate = dbconn.retrieveDateCreation(idpackage)
        pkgcreatedate = "N/A"
        if mydate:
            pkgcreatedate = Equo.entropyTools.convert_unix_time_to_human_time(
                float(mydate))
        pkgsize = Equo.entropyTools.bytes_into_human(pkgsize)
        pkgdeps = dbconn.retrieveDependencies(idpackage, extended = True)
        pkgconflicts = dbconn.retrieveConflicts(idpackage)

    pkghome = dbconn.retrieveHomepage(idpackage)
    pkgslot = dbconn.retrieveSlot(idpackage)
    pkgver = dbconn.retrieveVersion(idpackage)
    pkgtag = dbconn.retrieveVersionTag(idpackage)
    pkgrev = dbconn.retrieveRevision(idpackage)
    pkgdesc = dbconn.retrieveDescription(idpackage)
    pkguseflags = dbconn.retrieveUseflags(idpackage)
    pkgbranch = dbconn.retrieveBranch(idpackage)
    if (not pkgtag):
        pkgtag = "NoTag"

    pkgmasked = False
    masking_reason = ''
    # check if it's masked
    idpackage_masked, idmasking_reason = dbconn.idpackageValidator(idpackage)
    if idpackage_masked == -1:
        pkgmasked = True
        masking_reason = ", %s" % (
            Equo.SystemSettings['pkg_masking_reasons'].get(idmasking_reason),)

    if not clientSearch:

        # client info
        installedVer = _("Not installed")
        installedTag = _("N/A")
        installedRev = _("N/A")
        try:
            pkginstalled = Equo.clientDbconn.atomMatch(
                Equo.entropyTools.dep_getkey(pkgatom), matchSlot = pkgslot)
            if pkginstalled[1] == 0:
                idx = pkginstalled[0]
                # found
                installedVer = Equo.clientDbconn.retrieveVersion(idx)
                installedTag = Equo.clientDbconn.retrieveVersionTag(idx)
                if not installedTag:
                    installedTag = "NoTag"
                installedRev = Equo.clientDbconn.retrieveRevision(idx)
        except:
            clientSearch = True

    print_info(red("     @@ %s: " % (_("Package"),) ) + bold(pkgatom) + \
        "\t\t" + blue("branch: ") + bold(pkgbranch))
    if not strictOutput and extended:
        print_info(darkgreen("       %s:\t\t" % (_("Category"),) ) + \
            blue(pkgcat))
        print_info(darkgreen("       %s:\t\t\t" % (_("Name"),) ) + \
            blue(pkgname))

    if extended:
        print_info(darkgreen("       %s:\t\t" % (_("Masked"),) ) + \
            blue(str(pkgmasked)) + masking_reason)

    print_info(darkgreen("       %s:\t\t" % (_("Available"),) ) + \
        blue("%s: " % (_("version"),) ) + bold(pkgver) + blue(" ~ tag: ") + \
        bold(pkgtag) + blue(" ~ %s: " % (_("revision"),) ) + bold(str(pkgrev)))

    if not clientSearch:
        print_info(darkgreen("       %s:\t\t" % (_("Installed"),) ) + \
            blue("%s: " % (_("version"),) ) + bold(installedVer) + \
            blue(" ~ tag: ") + bold(installedTag) + \
            blue(" ~ %s: " % (_("revision"),) ) + bold(str(installedRev)))

    if not strictOutput:
        print_info(darkgreen("       %s:\t\t\t" % (_("Slot"),) ) + \
            blue(str(pkgslot)))

        if extended:
            print_info(darkgreen("       %s:\t\t\t" % (_("Size"),) ) + \
                blue(str(pkgsize)))
            print_info(darkgreen("       %s:\t\t" % (_("Download"),) ) + \
                brown(str(pkgbin)))
            print_info(darkgreen("       %s:\t\t" % (_("Checksum"),) ) + \
                brown(str(pkgdigest)))

        if pkgdeps and extended:
            print_info(darkred("       ##") + \
                darkgreen(" %s:" % (_("Dependencies"),) ))
            for pdep, p_id in pkgdeps:
                print_info(darkred("       ## \t\t\t") + blue(" [") + \
                    unicode(p_id)+blue("] ") + brown(pdep))

        if pkgconflicts and extended:
            print_info(darkred("       ##") + \
                darkgreen(" %s:" % (_("Conflicts"),) ))
            for conflict in pkgconflicts:
                print_info(darkred("       ## \t\t\t") + brown(conflict))

    print_info(darkgreen("       %s:\t\t" % (_("Homepage"),) ) + red(pkghome))

    if not strictOutput:
        # print description
        desc_txt = darkgreen("       %s:\t\t" % (_("Description"),) )
        _my_formatted_print(pkgdesc, desc_txt, "\t\t\t\t")
        # print use flags
        if extended:
            use_txt = darkgreen("       %s:\t\t" % (_("USE flags"),) )
            _my_formatted_print(pkguseflags, use_txt, "\t\t\t\t", color = red)

    if not strictOutput:

        if extended:
            print_info(darkgreen("       %s:\t\t" % (_("CHOST"),) ) + \
                blue(pkgflags[0]))
            print_info(darkgreen("       %s:\t\t" % (_("CFLAGS"),) ) + \
                red(pkgflags[1]))
            print_info(darkgreen("       %s:\t\t" % (_("CXXFLAGS"),) ) + \
                blue(pkgflags[2]))

            sources = dbconn.retrieveSources(idpackage)
            eclasses = dbconn.retrieveEclasses(idpackage)
            etpapi = dbconn.retrieveApi(idpackage)

            eclass_txt = "       %s:\t" % (_("Portage eclasses"),)
            _my_formatted_print(eclasses, darkgreen(eclass_txt), "\t\t\t\t",
                color = red)

            if sources:
                print_info(darkgreen("       %s:" % (_("Sources"),) ))
                for source in sources:
                    print_info(darkred("         # %s: " % (_("Source"),) ) + \
                        blue(source))

            print_info(darkgreen("       %s:\t\t" % (_("Entry API"),) ) + \
                red(str(etpapi)))

            print_info(darkgreen("       %s:\t" % (_("Compiled with"),) ) + \
                blue(pkgflags[1]))

            print_info(darkgreen("       %s:\t\t" % (_("Keywords"),) ) + \
                red(' '.join(pkgkeywords)))
            print_info(darkgreen("       %s:\t\t" % (_("Created"),) ) + \
                pkgcreatedate)

        print_info(darkgreen("       %s:\t\t" % (_("License"),) ) + \
            red(pkglic))

def _my_formatted_print(data, header, reset_columns, min_chars = 25,
    color = None):

    if type(data) is set:
        mydata = list(data)
    elif type(data) is not list:
        mydata = data.split()
    else:
        mydata = data

    fcount = 0
    desc_text = header
    for item in mydata:
        fcount += len(item)
        if color:
            desc_text += color(item)+" "
        else:
            desc_text += item+" "
        if fcount > min_chars:
            fcount = 0
            print_info(desc_text)
            desc_text = reset_columns

    if fcount > 0:
        print_info(desc_text)
