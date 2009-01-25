#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy database query tools and library

    Copyright (C) 2007-2008 Fabio Erculiani

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

from entropyConstants import *
from outputTools import *
from entropy import EquoInterface
from entropy_i18n import _

########################################################
####
##   Query Tools
#

def query(options):

    rc = 0

    if not options:
        return -10

    equoRequestDeep = False
    myopts = []
    for opt in options:
        if (opt == "--deep"):
            equoRequestDeep = True
        elif opt.startswith("--"):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return -10
        else:
            if not opt.startswith("-"):
                myopts.append(opt)

    if not myopts:
        return -10

    if myopts[0] == "installed":
        rc = searchInstalledPackages(myopts[1:])

    elif myopts[0] == "belongs":
        rc = searchBelongs(myopts[1:])

    elif myopts[0] == "depends":
        rc = searchDepends(myopts[1:])

    elif myopts[0] == "files":
        rc = searchFiles(myopts[1:])

    elif myopts[0] == "needed":
        rc = searchNeeded(myopts[1:])

    elif myopts[0] == "required":
        rc = searchRequired(myopts[1:])

    elif myopts[0] == "removal":
        rc = searchRemoval(myopts[1:],deep = equoRequestDeep)

    elif myopts[0] == "tags":
        rc = searchTaggedPackages(myopts[1:])

    elif myopts[0] == "sets":
        rc = searchPackageSets(myopts[1:])

    elif myopts[0] == "license":
        rc = searchLicenses(myopts[1:])

    elif myopts[0] == "slot":
        if (len(myopts) > 1):
            rc = searchSlottedPackages(myopts[1:])

    elif myopts[0] == "orphans":
        rc = searchOrphans()

    elif myopts[0] == "list":
        mylistopts = options[1:]
        if len(mylistopts) > 0:
            if mylistopts[0] == "installed":
                rc = searchInstalled()
    elif myopts[0] == "description":
        rc = searchDescription(myopts[1:])
    else:
        rc = -10

    return rc



def searchInstalledPackages(packages, idreturn = False, dbconn = None, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    if (not idreturn) and (not etpUi['quiet']):
        print_info(brown(" @@ ")+darkgreen("%s..." % (_("Searching"),) ))

    if not dbconn:
        clientDbconn = Equo.clientDbconn
    else:
        clientDbconn = dbconn

    dataInfo = set() # when idreturn is True
    for package in packages:
        slot = Equo.entropyTools.dep_getslot(package)
        tag = Equo.entropyTools.dep_gettag(package)
        package = Equo.entropyTools.remove_slot(package)
        package = Equo.entropyTools.remove_tag(package)

        result = clientDbconn.searchPackages(package, slot = slot, tag = tag)
        if (result):
            for pkg in result:
                idpackage = pkg[1]
                if (idreturn):
                    dataInfo.add(idpackage)
                else:
                    printPackageInfo(idpackage, clientDbconn, clientSearch = True, EquoConnection = Equo)
            # print info
            if (not idreturn) and (not etpUi['quiet']):
                print_info(blue(" %s: " % (_("Keyword"),) )+bold("\t"+package))
                print_info(blue(" %s:   " % (_("Found"),) )+bold("\t"+str(len(result)))+red(" %s" % (_("entries"),)))

    if (idreturn):
        return dataInfo
    return 0


def searchBelongs(files, idreturn = False, dbconn = None, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Belong Search"),)))

    if not dbconn:
        clientDbconn = Equo.clientDbconn
    else:
        clientDbconn = dbconn

    dataInfo = set() # when idreturn is True
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

    if (results):
        for result in results:
            # print info
            xfile = result
            result = results[result]
            for idpackage in result:
                if (idreturn):
                    dataInfo.add(idpackage)
                elif (etpUi['quiet']):
                    print clientDbconn.retrieveAtom(idpackage)
                else:
                    printPackageInfo(idpackage, clientDbconn, clientSearch = True, EquoConnection = Equo)
            if (not idreturn) and (not etpUi['quiet']):
                print_info(blue(" %s: " % (_("Keyword"),) )+bold("\t"+xfile))
                print_info(blue(" %s:   " % (_("Found"),) )+bold("\t"+str(len(result)))+red(" entries"))

    if (idreturn):
        return dataInfo
    return 0



def searchDepends(atoms, idreturn = False, dbconn = None, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Depends Search"),) ))

    # XXX hack to get Equo.atomMatch to not raise AttributeError
    match_repo = True
    try:
        x = Equo.atomMatch
        del x
    except AttributeError:
        match_repo = False

    if not dbconn:
        clientDbconn = Equo.clientDbconn
    else:
        clientDbconn = dbconn

    dataInfo = set() # when idreturn is True
    for atom in atoms:
        result = clientDbconn.atomMatch(atom)
        matchInRepo = False
        repoMasked = False
        if (result[0] == -1) and match_repo:
            matchInRepo = True
            result = Equo.atomMatch(atom)
        if (result[0] == -1) and match_repo:
            result = Equo.atomMatch(atom, packagesFilter = False)
            if result[0] != -1:
                repoMasked = True
        if (result[0] != -1):
            if (matchInRepo):
                dbconn = Equo.openRepositoryDatabase(result[1])
            else:
                dbconn = clientDbconn
            found_atom = dbconn.retrieveAtom(result[0])
            if repoMasked:
                idpackage_masked, idmasking_reason = dbconn.idpackageValidator(result[0])
            searchResults = dbconn.retrieveDepends(result[0])
            for idpackage in searchResults:
                if (idreturn):
                    dataInfo.add(idpackage)
                else:
                    if (etpUi['verbose']):
                        printPackageInfo(idpackage, dbconn, clientSearch = True, EquoConnection = Equo)
                    else:
                        printPackageInfo(idpackage, dbconn, clientSearch = True, strictOutput = True, EquoConnection = Equo)
            # print info
            if (not idreturn) and (not etpUi['quiet']):
                print_info(blue(" %s: " % (_("Keyword"),) )+bold("\t"+atom))
                print_info(blue(" %s: " % (_("Matched"),) )+bold("\t"+found_atom))
                masking_reason = ''
                if repoMasked:
                    masking_reason = ", %s" % (Equo.SystemSettings['pkg_masking_reasons'].get(idmasking_reason),)
                print_info(blue(" %s: " % (_("Masked"),) )+bold("\t"+str(repoMasked))+masking_reason)
                if (matchInRepo):
                    where = " %s %s" % (_("from repository"),result[1],)
                else:
                    where = " %s" % (_("from installed packages database"),)
                print_info( blue(" %s:   " % (_("Found"),) ) + bold("\t"+str(len(searchResults))) + \
                    red(" %s" % (_("entries"),))+where)
        else:
            continue
        if (matchInRepo):
            dbconn.closeDB()
            del dbconn

    if (idreturn):
        return dataInfo
    return 0

def searchNeeded(atoms, idreturn = False, dbconn = None, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()


    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Needed Search"),) ))

    dataInfo = set()
    if not dbconn:
        clientDbconn = Equo.clientDbconn
    else:
        clientDbconn = dbconn

    for atom in atoms:
        match = clientDbconn.atomMatch(atom)
        if (match[0] != -1):
            # print info
            myatom = clientDbconn.retrieveAtom(match[0])
            myneeded = clientDbconn.retrieveNeeded(match[0])
            for needed in myneeded:
                if (idreturn):
                    dataInfo.add(needed)
                elif (etpUi['quiet']):
                    print needed
                else:
                    print_info(blue("       # ")+red(str(needed)))
            if (not idreturn) and (not etpUi['quiet']):
                print_info(blue("     %s: " % (_("Atom"),))+bold("\t"+myatom))
                print_info(blue(" %s:   " % (_("Found"),))+bold("\t"+str(len(myneeded)))+red(" %s" % (_("libraries"),)))

    if (idreturn):
        return dataInfo
    return 0

def searchRequired(libraries, idreturn = False, dbconn = None, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()


    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Needed Search"),)))

    dataInfo = set()
    if not dbconn:
        clientDbconn = Equo.clientDbconn
    else:
        clientDbconn = dbconn

    for library in libraries:
        search_lib = library.replace("*","%")
        results = clientDbconn.searchNeeded(search_lib, like = True)
        for result in results:
            if (idreturn):
                dataInfo.add(result)
            elif (etpUi['quiet']):
                print clientDbconn.retrieveAtom(result)
            else:
                printPackageInfo(result, clientDbconn, clientSearch = True, strictOutput = True, EquoConnection = Equo)

        if (not idreturn) and (not etpUi['quiet']):
            print_info(blue(" %s: " % (_("Library"),))+bold("\t"+library))
            print_info(blue(" %s:   " % (_("Found"),) )+bold("\t"+str(len(results)))+red(" %s" % (_("packages"),) ))

    if (idreturn):
        return dataInfo
    return 0

def searchEclass(eclasses, idreturn = False, dbconn = None, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()


    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Eclass Search"),)))

    if not dbconn:
        clientDbconn = Equo.clientDbconn
    else:
        clientDbconn = dbconn

    dataInfo = set()
    for eclass in eclasses:
        matches = clientDbconn.searchEclassedPackages(eclass, atoms = True)
        for match in matches:
            if (idreturn):
                dataInfo.add(match)
                continue
            # print info
            myatom = match[0]
            idpackage = match[1]
            if (etpUi['quiet']):
                print myatom
            else:
                if (etpUi['verbose']):
                    printPackageInfo(idpackage, clientDbconn, clientSearch = True, EquoConnection = Equo)
                else:
                    printPackageInfo(idpackage, clientDbconn, clientSearch = True, strictOutput = True, EquoConnection = Equo)
        if (not etpUi['quiet']):
            print_info(blue(" %s:   " % (_("Found"),))+bold("\t"+str(len(matches)))+red(" %s" % (_("packages"),) ))

    if (idreturn):
        return dataInfo
    return 0

def searchFiles(atoms, idreturn = False, dbconn = None, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("Files Search..."))

    if not dbconn:
        results = searchInstalledPackages(atoms, idreturn = True)
        clientDbconn = Equo.clientDbconn
    else:
        results = searchInstalledPackages(atoms, idreturn = True, dbconn = dbconn, EquoConnection = EquoConnection)
        clientDbconn = dbconn

    dataInfo = set() # when idreturn is True
    for result in results:
        if (result != -1):
            files = clientDbconn.retrieveContent(result)
            atom = clientDbconn.retrieveAtom(result)
            files = list(files)
            files.sort()
            # print info
            if (idreturn):
                dataInfo.add((result,files))
            else:
                if etpUi['quiet']:
                    for xfile in files:
                        print xfile
                else:
                    for xfile in files:
                        print_info(blue(" ### ")+red(xfile))
            if (not idreturn) and (not etpUi['quiet']):
                print_info(blue(" %s: " % (_("Package"),))+bold("\t"+atom))
                print_info(blue(" %s:   " % (_("Found"),))+bold("\t"+str(len(files)))+red(" %s" % (_("files"),)))

    if (idreturn):
        return dataInfo
    return 0



def searchOrphans(EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    if (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Orphans Search"),)))

    clientDbconn = Equo.clientDbconn

    # start to list all files on the system:
    dirs = Equo.SystemSettings['system_dirs']
    filepath = Equo.entropyTools.getRandomTempFile()
    if os.path.isfile(filepath):
        os.remove(filepath)
    tdbconn = Equo.openGenericDatabase(filepath)
    tdbconn.initializeDatabase()
    for xdir in dirs:
        try:
            wd = os.walk(xdir)
        except RuntimeError: # maximum recursion?
            continue
        for currentdir,subdirs,files in wd:
            foundFiles = {}
            for filename in files:
                # filter python compiled objects?
                if filename.endswith(".pyo") or filename.endswith(".pyc") or filename == '.keep':
                    continue
                filename = os.path.join(currentdir,filename)
                if filename.endswith(".ph") and \
                    (filename.startswith("/usr/lib/perl") or filename.startswith("/usr/lib64/perl")):
                        continue
                mask = [x for x in Equo.SystemSettings['system_dirs_mask'] if filename.startswith(x)]
                if not mask:
                    if not etpUi['quiet']:
                        print_info(red(" @@ ")+blue("%s: " % (_("Analyzing"),))+bold(unicode(filename[:50],'raw_unicode_escape')+"..."), back = True)
                    foundFiles[filename] = "obj"
            if foundFiles:
                tdbconn.insertContent(1,foundFiles)

    tdbconn.commitChanges()
    # FIXME bad bad bad
    tdbconn.cursor.execute('select count(file) from content')
    totalfiles = tdbconn.cursor.fetchone()[0]

    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue("%s: " % (_("Analyzed directories"),) )+' '.join(Equo.SystemSettings['system_dirs']))
        print_info(red(" @@ ")+blue("%s: " % (_("Masked directories"),) )+' '.join(Equo.SystemSettings['system_dirs_mask']))
        print_info(red(" @@ ")+blue("%s: " % (_("Number of files collected on the filesystem"),) )+bold(str(totalfiles)))
        print_info(red(" @@ ")+blue("%s..." % (_("Now looking into Installed Packages database"),) ))

    # list all idpackages
    idpackages = clientDbconn.listAllIdpackages()
    # create content list
    length = str(len(idpackages))
    count = 0
    for idpackage in idpackages:
        if not etpUi['quiet']:
            count += 1
            atom = clientDbconn.retrieveAtom(idpackage)
            txt = "["+str(count)+"/"+length+"] "
            print_info(red(" @@ ")+blue("%s: " % (_("Intersecting with content of the package"),) )+txt+bold(str(atom)), back = True)
        content = set()
        for x in clientDbconn.retrieveContent(idpackage):
            if x.startswith("/usr/lib64"):
                x = "/usr/lib"+x[len("/usr/lib64"):]
            content.add(x)
        # remove from foundFiles
        for item in content:
            tdbconn.cursor.execute('delete from content where file = (?)', (item,))

    # FIXME BAD BAD BAD
    tdbconn.commitChanges()
    tdbconn.cursor.execute('select count(file) from content')
    orpanedfiles = tdbconn.cursor.fetchone()[0]

    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("%s: " % (_("Intersection completed. Showing statistics"),) ))
        print_info(red(" @@ ")+blue("%s: " % (_("Number of total files"),) )+bold(str(totalfiles)))
        print_info(red(" @@ ")+blue("%s: " % (_("Number of matching files"),) )+bold(str(totalfiles - orpanedfiles)))
        print_info(red(" @@ ")+blue("%s: " % (_("Number of orphaned files"),) )+bold(str(orpanedfiles)))

    tdbconn.cursor.execute('select file from content order by file desc')
    if not etpUi['quiet']:
        f = open("/tmp/equo-orphans.txt","w")
        print_info(red(" @@ ")+blue("%s: " % (_("Writing file to disk"),))+bold("/tmp/equo-orphans.txt"))

    tdbconn.connection.text_factory = lambda x: unicode(x, "raw_unicode_escape")
    myfile = tdbconn.cursor.fetchone()

    sizecount = 0
    while myfile:
        myfile = str(myfile[0].encode('raw_unicode_escape'))
        try:
            sizecount += os.stat(myfile)[6]
        except OSError:
            pass
        if not etpUi['quiet']:
            f.write(myfile+"\n")
        else:
            print myfile
        myfile = tdbconn.cursor.fetchone()

    humansize = Equo.entropyTools.bytesIntoHuman(sizecount)
    if not etpUi['quiet']:
        print_info(red(" @@ ")+blue("%s: " % (_("Total wasted space"),) )+bold(humansize))
        f.flush()
        f.close()
    else:
        print humansize

    tdbconn.closeDB()
    try:
        os.remove(filepath)
    except OSError:
        pass

    return 0


def searchRemoval(atoms, idreturn = False, deep = False, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    clientDbconn = Equo.clientDbconn

    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Removal Search"),) ))

    foundAtoms = []
    for atom in atoms:
        match = clientDbconn.atomMatch(atom)
        if match[1] == 0:
            foundAtoms.append(match[0])

    # are packages in foundAtoms?
    if (len(foundAtoms) == 0):
        print_error(red("%s." % (_("No packages found"),) ))
        return 127,-1

    choosenRemovalQueue = []
    if (not etpUi['quiet']):
        print_info(red(" @@ ")+blue("%s..." % (_("Calculating removal dependencies, please wait"),) ), back = True)
    treeview = Equo.generate_depends_tree(foundAtoms, deep = deep)
    treelength = len(treeview[0])
    if treelength > 1:
        treeview = treeview[0]
        for x in range(treelength)[::-1]:
            for y in treeview[x]:
                choosenRemovalQueue.append(y)

    if (choosenRemovalQueue):
        if (not etpUi['quiet']):
            print_info(red(" @@ ")+blue("%s:" % (_("These are the packages that would added to the removal queue"),)))
        totalatoms = str(len(choosenRemovalQueue))
        atomscounter = 0

        for idpackage in choosenRemovalQueue:
            atomscounter += 1
            rematom = clientDbconn.retrieveAtom(idpackage)
            if (not etpUi['quiet']):
                installedfrom = clientDbconn.retrievePackageFromInstalledTable(idpackage)
                repositoryInfo = bold("[")+red("%s: " % (_("from"),))+brown(installedfrom)+bold("]")
                stratomscounter = str(atomscounter)
                while len(stratomscounter) < len(totalatoms):
                    stratomscounter = " "+stratomscounter
                print_info("   # "+red("(")+bold(stratomscounter)+"/"+blue(str(totalatoms))+red(")")+repositoryInfo+" "+blue(rematom))
            else:
                print rematom

    if idreturn:
        return treeview
    return 0



def searchInstalled(idreturn = False, EquoConnection = None, dbconn = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Installed Search"),)))

    if dbconn:
        clientDbconn = dbconn
    else:
        clientDbconn = Equo.clientDbconn

    installedPackages = clientDbconn.listAllPackages()
    installedPackages.sort()
    if not idreturn:
        if (not etpUi['quiet']):
            print_info(red(" @@ ")+blue("%s:" % (_("These are the installed packages"),) ))
        for package in installedPackages:
            if (not etpUi['verbose']):
                atom = Equo.entropyTools.dep_getkey(package[0])
            else:
                atom = package[0]
            branchinfo = ""
            if (etpUi['verbose']):
                branchinfo = darkgreen(" [")+red(package[2])+darkgreen("]")
            if (not etpUi['quiet']):
                print_info(red("  #")+blue(str(package[1]))+branchinfo+" "+atom)
            else:
                print atom
        return 0
    else:
        idpackages = set()
        for x in installedPackages:
            idpackages.add(x[1])
        return list(idpackages)


def searchPackage(packages, idreturn = False, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None: Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    foundPackages = {}
    dataInfo = set() # when idreturn is True

    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Searching"),) ))
    # search inside each available database
    repoNumber = 0
    for repo in Equo.validRepositories:
        foundPackages[repo] = {}
        repoNumber += 1

        if (not idreturn) and (not etpUi['quiet']):
            print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))

        dbconn = Equo.openRepositoryDatabase(repo)
        for package in packages:
            slot = Equo.entropyTools.dep_getslot(package)
            tag = Equo.entropyTools.dep_gettag(package)
            package = Equo.entropyTools.remove_slot(package)
            package = Equo.entropyTools.remove_tag(package)
            result = dbconn.searchPackages(package, slot = slot, tag = tag)

            if (not result): # look for provide
                result = dbconn.searchProvide(package, slot = slot, tag = tag)

            if (result):
                foundPackages[repo][package] = result
                # print info
                for pkg in foundPackages[repo][package]:
                    idpackage = pkg[1]
                    if (idreturn):
                        dataInfo.add((idpackage,repo))
                    else:
                        printPackageInfo(idpackage,dbconn, EquoConnection = Equo)
                if (not idreturn) and (not etpUi['quiet']):
                    print_info(blue(" %s: " % (_("Keyword"),) )+bold("\t"+package))
                    print_info(blue(" %s:   " % (_("Found"),) )+bold("\t"+str(len(foundPackages[repo][package])))+red(" %s" % (_("entries"),) ))


    if (idreturn):
        return dataInfo
    return 0

def matchPackage(packages, idreturn = False, multiMatch = False, multiRepo = False, showRepo = False, showDesc = False, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    dataInfo = set() # when idreturn is True

    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Matching"),) ), back = True)
    found = False

    for package in packages:

        if (not idreturn) and (not etpUi['quiet']):
            print_info(blue("  # ")+bold(package))

        match = Equo.atomMatch(package, multiMatch = multiMatch, multiRepo = multiRepo, packagesFilter = False)
        if match[1] != 1:
            if not multiMatch:
                if multiRepo:
                    matches = match[0]
                else:
                    matches = [match]
            else:
                matches = match[0]
            for match in matches:
                if (idreturn):
                    dataInfo.add(tuple(match))
                else:
                    dbconn = Equo.openRepositoryDatabase(match[1])
                    printPackageInfo(match[0],dbconn, showRepoOnQuiet = showRepo, showDescOnQuiet = showDesc, EquoConnection = Equo)
                    found = True
            if (not idreturn) and (not etpUi['quiet']):
                print_info(blue(" %s: " % (_("Keyword"),) )+bold("\t"+package))
                print_info(blue(" %s:   " % (_("Found"),) )+bold("\t"+str(len(matches)))+red(" %s" % (_("entries"),) ))

    if (not idreturn) and (not etpUi['quiet']) and (not found):
        print_info(darkred(" @@ ")+darkgreen("%s." % (_("No matches"),) ))

    if (idreturn):
        return dataInfo
    return 0

def searchSlottedPackages(slots, datareturn = False, dbconn = None, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    foundPackages = {}
    dbclose = True
    if dbconn:
        dbclose = False

    if (not datareturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Slot Search"),) ))
    # search inside each available database
    repoNumber = 0
    for repo in Equo.validRepositories:
        foundPackages[repo] = {}
        repoNumber += 1

        if (not datareturn) and (not etpUi['quiet']):
            print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))

        if dbclose:
            dbconn = Equo.openRepositoryDatabase(repo)
        for slot in slots:
            results = dbconn.searchSlottedPackages(slot, atoms = True)
            for result in results:
                foundPackages[repo][result[1]] = result[0]
                # print info
                if (not datareturn):
                    printPackageInfo(result[1],dbconn, EquoConnection = Equo)
            if (not datareturn) and (not etpUi['quiet']):
                print_info(blue(" %s: " % (_("Keyword"),) )+bold("\t"+slot))
                print_info(blue(" %s:   " % (_("Found"),) )+bold("\t"+str(len(results)))+red(" %s" % (_("entries"),) ))

    if (datareturn):
        return foundPackages
    return 0

def searchPackageSets(items, datareturn = False, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    foundPackages = {}

    if (not datareturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Package Set Search"),)))

    if not items: items.append('*')

    matchNumber = 0
    for item in items:
        results = Equo.packageSetSearch(item)
        for repo, set_name, set_data in results:
            matchNumber += 1
            if (not datareturn) and (not etpUi['quiet']):
                print_info(blue("  #"+str(matchNumber))+bold(" "+set_name))
                if (not datareturn):
                    elements = sorted(list(set_data))
                    for element in elements:
                        print_info(brown("    "+element))

        if (not datareturn) and (not etpUi['quiet']):
            print_info(blue(" %s: " % (_("Keyword"),))+bold("\t"+item))
            print_info(blue(" %s:   " % (_("Found"),))+bold("\t"+str(matchNumber))+red(" %s" % (_("entries"),)))

    if datareturn:
        return foundPackages
    return 0

def searchTaggedPackages(tags, datareturn = False, dbconn = None, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    foundPackages = {}
    dbclose = True
    if dbconn:
        dbclose = False

    if (not datareturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Tag Search"),)))
    # search inside each available database
    repoNumber = 0
    for repo in Equo.validRepositories:
        foundPackages[repo] = {}
        repoNumber += 1

        if (not datareturn) and (not etpUi['quiet']):
            print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))

        if dbclose:
            dbconn = Equo.openRepositoryDatabase(repo)
        for tag in tags:
            results = dbconn.searchTaggedPackages(tag, atoms = True)
            for result in results:
                foundPackages[repo][result[1]] = result[0]
                if (not datareturn):
                    printPackageInfo(result[1],dbconn, EquoConnection = Equo)
            if (not datareturn) and (not etpUi['quiet']):
                print_info(blue(" %s: " % (_("Keyword"),))+bold("\t"+tag))
                print_info(blue(" %s:   " % (_("Found"),))+bold("\t"+str(len(results)))+red(" %s" % (_("entries"),)))

    if (datareturn):
        return foundPackages
    return 0

def searchLicenses(licenses, datareturn = False, dbconn = None, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    foundPackages = {}
    dbclose = True
    if dbconn:
        dbclose = False

    if (not datareturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("License Search"),)))
    # search inside each available database
    repoNumber = 0
    for repo in Equo.validRepositories:
        foundPackages[repo] = {}
        repoNumber += 1

        if (not datareturn) and (not etpUi['quiet']):
            print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))

        if dbclose:
            dbconn = Equo.openRepositoryDatabase(repo)
        for mylicense in licenses:
            results = dbconn.searchLicenses(mylicense, atoms = True)
            if not results:
                continue
            for result in results:
                foundPackages[repo][result[1]] = result[0]
                # print info
                if (not datareturn):
                    printPackageInfo(result[1],dbconn, EquoConnection = Equo)
            if (not datareturn) and (not etpUi['quiet']):
                print_info(blue(" %s: " % (_("Keyword"),))+bold("\t"+mylicense))
                print_info(blue(" %s:   " % (_("Found"),))+bold("\t"+str(len(results)))+red(" %s" % (_("entries"),) ))

    if (datareturn):
        return foundPackages
    return 0

def searchDescription(descriptions, idreturn = False, EquoConnection = None):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    foundPackages = {}

    if (not idreturn) and (not etpUi['quiet']):
        print_info(darkred(" @@ ")+darkgreen("%s..." % (_("Description Search"),) ))
    # search inside each available database
    repoNumber = 0
    for repo in Equo.validRepositories:
        foundPackages[repo] = {}
        repoNumber += 1

        if (not idreturn) and (not etpUi['quiet']):
            print_info(blue("  #"+str(repoNumber))+bold(" "+etpRepositories[repo]['description']))

        dbconn = Equo.openRepositoryDatabase(repo)
        dataInfo, descdata = searchDescriptions(descriptions, dbconn, idreturn, EquoConnection = Equo)
        foundPackages[repo].update(descdata)

    if (idreturn):
        return dataInfo
    return 0

'''
   Internal functions
'''
def searchDescriptions(descriptions, dbconn, idreturn = False, EquoConnection = None):
    dataInfo = set() # when idreturn is True
    mydescdata = {}

    for desc in descriptions:
        result = dbconn.searchPackagesByDescription(desc)
        if (result):
            mydescdata[desc] = result
            for pkg in mydescdata[desc]:
                idpackage = pkg[1]
                if (idreturn):
                    dataInfo.add(idpackage)
                elif (etpUi['quiet']):
                    print dbconn.retrieveAtom(idpackage)
                else:
                    printPackageInfo(idpackage,dbconn, EquoConnection = EquoConnection)
            # print info
            if (not idreturn) and (not etpUi['quiet']):
                print_info(blue(" %s: " % (_("Keyword"),) )+bold("\t"+desc))
                print_info(blue(" %s:   " % (_("Found"),) )+bold("\t"+str(len(mydescdata[desc])))+red(" %s" % (_("entries"),) ))
    return dataInfo,mydescdata

def printPackageInfo(idpackage, dbconn, clientSearch = False, strictOutput = False, extended = False, EquoConnection = None, showRepoOnQuiet = False, showDescOnQuiet = False):

    if EquoConnection != None:
        Equo = EquoConnection
    else:
        try:
            if Equo == None:
                Equo = EquoInterface()
        except NameError:
            Equo = EquoInterface()

    # now fetch essential info
    pkgatom = dbconn.retrieveAtom(idpackage)
    if pkgatom == None:
        return # doesn't exist
    if (etpUi['quiet']):
        repoinfo = ''
        desc = ''
        if showRepoOnQuiet:
            repoinfo = "[%s] " % (dbconn.dbname,)
        if showDescOnQuiet:
            desc = ' %s' % (dbconn.retrieveDescription(idpackage),)
        print "%s%s%s" % (repoinfo,pkgatom,desc,)
        return

    if (not strictOutput):
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
            pkgcreatedate = Equo.entropyTools.convertUnixTimeToHumanTime(float(mydate))
        pkgsize = Equo.entropyTools.bytesIntoHuman(pkgsize)
        pkgdeps = dbconn.retrieveDependencies(idpackage)
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
        masking_reason = ", %s" % (Equo.SystemSettings['pkg_masking_reasons'].get(idmasking_reason),)

    if (not clientSearch):

        # client info
        installedVer = _("Not installed")
        installedTag = _("N/A")
        installedRev = _("N/A")
        try:
            pkginstalled = Equo.clientDbconn.atomMatch(Equo.entropyTools.dep_getkey(pkgatom), matchSlot = pkgslot)
            if (pkginstalled[1] == 0):
                idx = pkginstalled[0]
                # found
                installedVer = Equo.clientDbconn.retrieveVersion(idx)
                installedTag = Equo.clientDbconn.retrieveVersionTag(idx)
                if not installedTag:
                    installedTag = "NoTag"
                installedRev = Equo.clientDbconn.retrieveRevision(idx)
        except:
            clientSearch = True

    print_info(red("     @@ %s: " % (_("Package"),) )+bold(pkgatom)+"\t\t"+blue("branch: ")+bold(pkgbranch))
    if (not strictOutput):
        print_info(darkgreen("       %s:\t\t" % (_("Category"),) )+blue(pkgcat))
        print_info(darkgreen("       %s:\t\t\t" % (_("Name"),) )+blue(pkgname))
    print_info(darkgreen("       %s:\t\t" % (_("Masked"),) )+blue(str(pkgmasked))+masking_reason)
    print_info(darkgreen("       %s:\t\t" % (_("Available"),) )+blue("%s: " % (_("version"),) )+bold(pkgver)+blue(" ~ tag: ")+bold(pkgtag)+blue(" ~ %s: " % (_("revision"),) )+bold(str(pkgrev)))
    if (not clientSearch):
        print_info(darkgreen("       %s:\t\t" % (_("Installed"),) )+blue("%s: " % (_("version"),) )+bold(installedVer)+blue(" ~ tag: ")+bold(installedTag)+blue(" ~ %s: " % (_("revision"),) )+bold(str(installedRev)))
    if (not strictOutput):
        print_info(darkgreen("       %s:\t\t\t" % (_("Slot"),) )+blue(str(pkgslot)))
        print_info(darkgreen("       %s:\t\t\t" % (_("Size"),) )+blue(str(pkgsize)))
        print_info(darkgreen("       %s:\t\t" % (_("Download"),) )+brown(str(pkgbin)))
        print_info(darkgreen("       %s:\t\t" % (_("Checksum"),) )+brown(str(pkgdigest)))
        if (pkgdeps):
            print_info(darkred("       ##")+darkgreen(" %s:" % (_("Dependencies"),) ))
            for pdep in pkgdeps:
                print_info(darkred("       ## \t\t\t")+brown(pdep))
        if (pkgconflicts):
            print_info(darkred("       ##")+darkgreen(" %s:" % (_("Conflicts"),) ))
            for conflict in pkgconflicts:
                print_info(darkred("       ## \t\t\t")+brown(conflict))
    print_info(darkgreen("       %s:\t\t" % (_("Homepage"),) )+red(pkghome))

    if (not strictOutput):
        # print description
        _my_formatted_print(pkgdesc,darkgreen("       %s:\t\t" % (_("Description"),) ),"\t\t\t\t")
        # print use flags
        _my_formatted_print(pkguseflags,darkgreen("       %s:\t\t" % (_("USE flags"),) ),"\t\t\t\t", color = red)

    if (not strictOutput):
        if (extended):
            print_info(darkgreen("       %s:\t\t" % (_("CHOST"),) )+blue(pkgflags[0]))
            print_info(darkgreen("       %s:\t\t" % (_("CFLAGS"),) )+red(pkgflags[1]))
            print_info(darkgreen("       %s:\t\t" % (_("CXXFLAGS"),) )+blue(pkgflags[2]))
            sources = dbconn.retrieveSources(idpackage)
            eclasses = dbconn.retrieveEclasses(idpackage)
            etpapi = dbconn.retrieveApi(idpackage)
            _my_formatted_print(eclasses,darkgreen("       %s:\t" % (_("Gentoo eclasses"),) ),"\t\t\t\t", color = red)
            if (sources):
                print_info(darkgreen("       %s:" % (_("Sources"),) ))
                for source in sources:
                    print_info(darkred("         # %s: " % (_("Source"),) )+blue(source))
            print_info(darkgreen("       %s:\t\t" % (_("Entry API"),) )+red(str(etpapi)))
        else:
            print_info(darkgreen("       %s:\t" % (_("Compiled with"),) )+blue(pkgflags[1]))
        print_info(darkgreen("       %s:\t\t" % (_("Keywords"),) )+red(' '.join(pkgkeywords)))
        print_info(darkgreen("       %s:\t\t" % (_("Created"),) )+pkgcreatedate)
        print_info(darkgreen("       %s:\t\t" % (_("License"),) )+red(pkglic))

def _my_formatted_print(data,header,reset_columns, min_chars = 25, color = None):
    if type(data) is set:
        mydata = list(data)
    elif type(data) is not list:
        mydata = data.split()
    else:
        mydata = data
    fcount = 0
    desc_text = header
    for x in mydata:
        fcount += len(x)
        if color:
            desc_text += color(x)+" "
        else:
            desc_text += x+" "
        if fcount > min_chars:
            fcount = 0
            print_info(desc_text)
            desc_text = reset_columns
    if fcount > 0: print_info(desc_text)
