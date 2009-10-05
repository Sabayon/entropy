# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""

import os
from entropy.const import etpUi, const_convert_to_unicode, \
    const_convert_to_rawstring
from entropy.output import darkgreen, darkred, red, blue, \
    brown, purple, bold, print_info, print_error, print_generic
from entropy.client.interfaces import Client as EquoInterface
from entropy.i18n import _
import entropy.tools as entropyTools


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
        rc_status = search_installed_packages(myopts[1:])

    elif myopts[0] == "belongs":
        rc_status = search_belongs(myopts[1:])

    elif myopts[0] == "changelog":
        rc_status = search_changelog(myopts[1:])

    elif myopts[0] == "depends":
        rc_status = search_inverse_dependencies(myopts[1:])

    elif myopts[0] == "files":
        rc_status = search_files(myopts[1:])

    elif myopts[0] == "needed":
        rc_status = search_needed_libraries(myopts[1:])

    elif myopts[0] == "required":
        rc_status = search_required_libraries(myopts[1:])

    elif myopts[0] == "removal":
        rc_status = search_removal_dependencies(myopts[1:], deep = do_deep)

    elif myopts[0] == "tags":
        rc_status = search_tagged_packages(myopts[1:])

    elif myopts[0] == "sets":
        rc_status = search_package_sets(myopts[1:])

    elif myopts[0] == "license":
        rc_status = search_licenses(myopts[1:])

    elif myopts[0] == "slot":
        if (len(myopts) > 1):
            rc_status = search_slotted_packages(myopts[1:])

    elif myopts[0] == "orphans":
        rc_status = search_orphaned_files()

    elif myopts[0] == "list":
        mylistopts = options[1:]
        if len(mylistopts) > 0:
            if mylistopts[0] == "installed":
                rc_status = list_installed_packages()
            elif mylistopts[0] == "available" and len(mylistopts) > 1:
                repoid = mylistopts[1]
                equo = EquoInterface()
                if repoid in equo.validRepositories:
                    repo_dbconn = equo.open_repository(repoid)
                    rc_status = list_installed_packages(dbconn = repo_dbconn)
                else:
                    rc_status = -10
            else:
                rc_status = -10
    elif myopts[0] == "description":
        rc_status = search_description(myopts[1:])
    else:
        rc_status = -10

    return rc_status


def search_installed_packages(packages, idreturn = False, dbconn = None,
    Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    if (not idreturn) and (not etpUi['quiet']):
        print_info(brown(" @@ ")+darkgreen("%s..." % (_("Searching"),) ))

    clientDbconn = dbconn
    if not dbconn:
        clientDbconn = Equo.clientDbconn

    if not packages:
        packages = [x[0] for x in \
            clientDbconn.listAllPackages(order_by = "atom")]

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
            print_package_info(idpackage, clientDbconn, clientSearch = True,
                Equo = Equo, extended = etpUi['verbose'])

        if not etpUi['quiet']:
            print_info(blue(" %s: " % (_("Keyword"),) ) + bold("\t"+package))
            print_info(blue(" %s:   " % (_("Found"),) ) + \
                bold("\t" + str(len(idpackages))) + \
                red(" %s" % (_("entries"),)))

    if idreturn:
        return pkg_data
    return 0


def search_belongs(files, idreturn = False, dbconn = None, Equo = None):

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
    reverse_symlink_map = Equo.SystemSettings['system_rev_symlinks']
    for xfile in files:
        like = False
        if xfile.find("*") != -1:
            xfile.replace("*", "%")
            like = True
        results[xfile] = set()
        idpackages = clientDbconn.searchBelongs(xfile, like)
        if not idpackages:
            # try real path if possible
            idpackages = clientDbconn.searchBelongs(
                os.path.realpath(xfile), like)
        if not idpackages:
            # try using reverse symlink mapping
            for sym_dir in reverse_symlink_map:
                if xfile.startswith(sym_dir):
                    for sym_child in reverse_symlink_map[sym_dir]:
                        my_file = sym_child+xfile[len(sym_dir):]
                        idpackages = clientDbconn.searchBelongs(my_file, like)
                        if idpackages:
                            break

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
                    print_package_info(idpackage, clientDbconn,
                        clientSearch = True, Equo = Equo,
                        extended = etpUi['verbose'])
            if not etpUi['quiet']:
                print_info(blue(" %s: " % (_("Keyword"),) ) + bold("\t"+xfile))
                print_info(blue(" %s:   " % (_("Found"),) ) + \
                    bold("\t" + str(len(result))) + red(" entries"))

    if idreturn:
        return pkg_data
    return 0


def search_changelog(atoms, dbconn = None, Equo = None):

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
        print_generic("="*80)

    return 0


def search_inverse_dependencies(atoms, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Inverse Dependencies Search"),) ))

    match_repo = True
    if not hasattr(Equo, 'atom_match'):
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

            searchResults = dbconn.retrieveReverseDependencies(result[0])
            for idpackage in searchResults:
                print_package_info(idpackage, dbconn, clientSearch = True,
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

def search_needed_libraries(atoms, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()


    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Needed Search"),) ))

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

def search_required_libraries(libraries, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()


    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + \
            darkgreen("%s..." % (_("Required Search"),)))

    clientDbconn = dbconn
    if not dbconn:
        clientDbconn = Equo.clientDbconn

    for library in libraries:
        search_lib = library.replace("*", "%")
        results = clientDbconn.searchNeeded(search_lib, like = True)
        for result in results:

            if etpUi['quiet']:
                print_generic(clientDbconn.retrieveAtom(result))
                continue

            print_package_info(result, clientDbconn, clientSearch = True,
                strictOutput = True, Equo = Equo,
                extended = etpUi['verbose'])

        if not etpUi['quiet']:
            print_info(blue(" %s: " % (_("Library"),)) + bold("\t"+library))
            print_info(blue(" %s:   " % (_("Found"),) ) + \
                bold("\t"+str(len(results))) + red(" %s" % (_("packages"),) ))

    return 0

def search_eclass(eclasses, dbconn = None, Equo = None):

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

            print_package_info(idpackage, clientDbconn, clientSearch = True,
                Equo = Equo, extended = etpUi['verbose'],
                strictOutput = not etpUi['verbose'])

        if not etpUi['quiet']:
            print_info(blue(" %s:   " % (_("Found"),)) + \
                bold("\t"+str(len(matches))) + red(" %s" % (_("packages"),) ))

    return 0

def search_files(atoms, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("Files Search..."))

    if not dbconn:
        results = search_installed_packages(atoms, idreturn = True)
        clientDbconn = Equo.clientDbconn
    else:
        results = search_installed_packages(atoms, idreturn = True,
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



def search_orphaned_files(Equo = None):

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

    import re
    reverse_symlink_map = Equo.SystemSettings['system_rev_symlinks']
    system_dirs_mask = [x for x in Equo.SystemSettings['system_dirs_mask'] \
        if entropyTools.is_valid_path(x)]
    system_dirs_mask_regexp = []
    for mask in Equo.SystemSettings['system_dirs_mask']:
        reg_mask = re.compile(mask)
        system_dirs_mask_regexp.append(reg_mask)

    count = 0
    for xdir in dirs:
        try:
            wd = os.walk(xdir)
        except RuntimeError: # maximum recursion?
            continue
        for currentdir, subdirs, files in wd:
            foundFiles = {}
            for filename in files:

                filename = os.path.join(currentdir, filename)

                # filter symlinks, broken ones will be reported
                if os.path.islink(filename) and os.path.lexists(filename):
                    continue

                do_cont = False
                for mask in system_dirs_mask:
                    if filename.startswith(mask):
                        do_cont = True
                        break
                if do_cont:
                    continue

                for mask in system_dirs_mask_regexp:
                    if mask.match(filename):
                        do_cont = True
                        break
                if do_cont:
                    continue

                count += 1
                if not etpUi['quiet'] and ((count == 0) or (count % 500 == 0)):
                    count = 0
                    fname = const_convert_to_unicode(filename[:50])
                    print_info(" %s %s: %s" % (
                            red("@@"),
                            blue(_("Analyzing")),
                            fname,
                        ),
                        back = True
                    )
                try:
                    foundFiles[const_convert_to_unicode(filename)] = \
                        const_convert_to_unicode("obj")
                except (UnicodeDecodeError, UnicodeEncodeError,) as e:
                    if etpUi['quiet']:
                        continue
                    print_generic("!!! error on", filename, "skipping:", repr(e))

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
            # reverse sym
            for sym_dir in reverse_symlink_map:
                if path.startswith(sym_dir):
                    for sym_child in reverse_symlink_map[sym_dir]:
                        yield (sym_child+path[len(sym_dir):],)
            # real path also
            yield (os.path.realpath(path),)
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
        f_out = open(fname, "w")
        print_info(red(" @@ ")+blue("%s: " % (_
            ("Writing file to disk"),)) + bold(fname))

    tdbconn.connection.text_factory = lambda x: const_convert_to_unicode(x)
    myfile = tdbconn.cursor.fetchone()

    sizecount = 0
    while myfile:

        myfile = const_convert_to_rawstring(myfile[0])
        mysize = 0
        try:
            mysize += os.stat(myfile)[6]
        except OSError:
            mysize = 0
        sizecount += mysize

        if not etpUi['quiet']:
            f_out.write(myfile+"\n")
        else:
            print_generic(myfile)

        myfile = tdbconn.cursor.fetchone()

    humansize = Equo.entropyTools.bytes_into_human(sizecount)
    if not etpUi['quiet']:
        print_info(red(" @@ ") + \
            blue("%s: " % (_("Total wasted space"),) ) + bold(humansize))
        f_out.flush()
        f_out.close()
    else:
        print_generic(humansize)

    tdbconn.closeDB()
    if os.path.isfile(filepath):
        os.remove(filepath)

    return 0


def search_removal_dependencies(atoms, deep = False, Equo = None):

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

            installedfrom = clientDbconn.getInstalledPackageRepository(
                idpackage)
            if installedfrom is None:
                installedfrom = _("Not available")
            repo_info = bold("[") + red("%s: " % (_("from"),)) + \
                brown(installedfrom)+bold("]")
            stratomscounter = str(atomscounter)
            while len(stratomscounter) < len(totalatoms):
                stratomscounter = " "+stratomscounter
            print_info("   # " + red("(") + bold(stratomscounter) + "/" + \
                blue(str(totalatoms)) + red(")") + repo_info + " " + \
                blue(rematom))

    return 0



def list_installed_packages(Equo = None, dbconn = None):

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


def search_package(packages, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    foundPackages = {}

    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Searching"),) ))
    # search inside each available database
    repo_number = 0
    found = False
    for repo in Equo.validRepositories:
        foundPackages[repo] = {}
        repo_number += 1

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repo_number)) + \
                bold(" " + Equo.SystemSettings['repositories']['available'][repo]['description']))

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
                        print_package_info(pkg[1], dbconn, Equo = Equo,
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

def match_package(packages, multiMatch = False, multiRepo = False,
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
                print_package_info(match[0], dbconn, showRepoOnQuiet = showRepo,
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

def search_slotted_packages(slots, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    dbclose = True
    if dbconn:
        dbclose = False

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ") + darkgreen("%s..." % (_("Slot Search"),) ))

    # search inside each available database
    repo_number = 0
    for repo in Equo.validRepositories:
        repo_number += 1

        if not etpUi['quiet']:
            print_info(blue("  #"+str(repo_number)) + \
                bold(" " + Equo.SystemSettings['repositories']['available'][repo]['description']))

        if dbclose:
            dbconn = Equo.open_repository(repo)

        for slot in slots:

            results = dbconn.searchSlottedPackages(slot, atoms = True)
            for result in results:
                found = True
                print_package_info(result[1], dbconn, Equo = Equo,
                    extended = etpUi['verbose'], strictOutput = etpUi['quiet'])

            if not etpUi['quiet']:
                print_info(blue(" %s: " % (_("Keyword"),) ) + bold("\t"+slot))
                print_info(blue(" %s:   " % (_("Found"),) ) + \
                    bold("\t" + str(len(results))) + \
                    red(" %s" % (_("entries"),) ))

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_package_sets(items, Equo = None):

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

def search_tagged_packages(tags, dbconn = None, Equo = None):

    if Equo == None:
        Equo = EquoInterface()

    dbclose = True
    if dbconn:
        dbclose = False

    found = False
    if not etpUi['quiet']:
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Tag Search"),)))

    repo_number = 0
    for repo in Equo.validRepositories:
        repo_number += 1

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repo_number)) + \
                bold(" " + Equo.SystemSettings['repositories']['available'][repo]['description']))

        if dbclose:
            dbconn = Equo.open_repository(repo)

        for tag in tags:
            results = dbconn.searchTaggedPackages(tag, atoms = True)
            found = True
            for result in results:
                print_package_info(result[1], dbconn, Equo = Equo,
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

def search_licenses(licenses, dbconn = None, Equo = None):

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
    repo_number = 0
    for repo in Equo.validRepositories:
        repo_number += 1

        if not etpUi['quiet']:
            print_info(blue("  #" + str(repo_number)) + \
                bold(" " + Equo.SystemSettings['repositories']['available'][repo]['description']))

        if dbclose:
            dbconn = Equo.open_repository(repo)

        for mylicense in licenses:

            results = dbconn.searchLicenses(mylicense, atoms = True)
            if not results:
                continue
            found = True
            for result in results:
                print_package_info(result[1], dbconn, Equo = Equo,
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

def search_description(descriptions, Equo = None):

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
                bold(" " + Equo.SystemSettings['repositories']['available'][repo]['description']))

        dbconn = Equo.open_repository(repo)
        descdata = search_descriptions(descriptions, dbconn, Equo = Equo)
        if descdata:
            found = True

    if not etpUi['quiet'] and not found:
        print_info(darkred(" @@ ") + darkgreen("%s." % (_("No matches"),) ))

    return 0

def search_descriptions(descriptions, dbconn, Equo = None):

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
                print_package_info(idpackage, dbconn, Equo = Equo,
                    extended = etpUi['verbose'], strictOutput = etpUi['quiet'])

        if not etpUi['quiet']:
            print_info(blue(" %s: " % (_("Keyword"),) ) + bold("\t"+desc))
            print_info(blue(" %s:   " % (_("Found"),) ) + \
                bold("\t" + str(len(mydescdata[desc]))) + \
                red(" %s" % (_("entries"),) ))

    return mydescdata

def print_package_info(idpackage, dbconn, clientSearch = False,
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

    pkghome = dbconn.retrieveHomepage(idpackage)
    pkgslot = dbconn.retrieveSlot(idpackage)
    pkgver = dbconn.retrieveVersion(idpackage)
    pkgtag = dbconn.retrieveVersionTag(idpackage)
    pkgrev = dbconn.retrieveRevision(idpackage)
    pkgdesc = dbconn.retrieveDescription(idpackage)
    pkgbranch = dbconn.retrieveBranch(idpackage)
    if not pkgtag:
        pkgtag = "NoTag"

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
        pkgname = dbconn.retrieveName(idpackage)
        pkgcat = dbconn.retrieveCategory(idpackage)
        print_info(darkgreen("       %s:\t\t" % (_("Category"),) ) + \
            blue(pkgcat))
        print_info(darkgreen("       %s:\t\t\t" % (_("Name"),) ) + \
            blue(pkgname))

    if extended:

        pkgmasked = False
        masking_reason = ''
        # check if it's masked
        idpackage_masked, idmasking_reason = dbconn.idpackageValidator(
            idpackage)
        if idpackage_masked == -1:
            pkgmasked = True
            masking_reason = ", %s" % (
                Equo.SystemSettings['pkg_masking_reasons'].get(
                    idmasking_reason),)

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
            pkgsize = dbconn.retrieveSize(idpackage)
            pkgsize = Equo.entropyTools.bytes_into_human(pkgsize)

            print_info(darkgreen("       %s:\t\t\t" % (_("Size"),) ) + \
                blue(str(pkgsize)))

            pkgbin = dbconn.retrieveDownloadURL(idpackage)
            print_info(darkgreen("       %s:\t\t" % (_("Download"),) ) + \
                brown(str(pkgbin)))

            pkgdigest = dbconn.retrieveDigest(idpackage)
            print_info(darkgreen("       %s:\t\t" % (_("Checksum"),) ) + \
                brown(str(pkgdigest)))

            pkgdeps = dbconn.retrieveDependencies(idpackage, extended = True)
            pkgconflicts = dbconn.retrieveConflicts(idpackage)
            if pkgdeps:
                print_info(darkred("       ##") + \
                    darkgreen(" %s:" % (_("Dependencies"),) ))
                for pdep, p_id in pkgdeps:
                    print_info(darkred("       ## \t\t\t") + blue(" [") + \
                        str(p_id) + blue("] ") + brown(pdep))

            if pkgconflicts:
                print_info(darkred("       ##") + \
                    darkgreen(" %s:" % (_("Conflicts"),) ))
                for conflict in pkgconflicts:
                    print_info(darkred("       ## \t\t\t") + brown(conflict))

    home_txt = darkgreen("       %s:\t\t" % (_("Homepage"),) )
    _my_formatted_print(pkghome, home_txt, "\t\t\t\t", color = brown,
        min_chars = 15)

    if not strictOutput:

        desc_txt = darkgreen("       %s:\t\t" % (_("Description"),) )
        _my_formatted_print(pkgdesc, desc_txt, "\t\t\t\t")

        if extended:
            pkguseflags = dbconn.retrieveUseflags(idpackage)
            use_txt = darkgreen("       %s:\t\t" % (_("USE flags"),) )
            _my_formatted_print(pkguseflags, use_txt, "\t\t\t\t", color = red)

    if not strictOutput:

        if extended:

            pkgflags = dbconn.retrieveCompileFlags(idpackage)
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

            pkgkeywords = dbconn.retrieveKeywords(idpackage)
            print_info(darkgreen("       %s:\t\t" % (_("Keywords"),) ) + \
                red(' '.join(pkgkeywords)))

            mydate = dbconn.retrieveCreationDate(idpackage)
            pkgcreatedate = "N/A"
            if mydate:
                pkgcreatedate = Equo.entropyTools.convert_unix_time_to_human_time(
                    float(mydate))
            print_info(darkgreen("       %s:\t\t" % (_("Created"),) ) + \
                pkgcreatedate)

        pkglic = dbconn.retrieveLicense(idpackage)
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
