#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy smart functionalities library

    Copyright (C) 2007 Fabio Erculiani

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
import shutil
from entropyConstants import *
from clientConstants import *
from outputTools import *
import equoTools
import uiTools
Equo = equoTools.EquoInterface()

def smart(options):

    # check if I am root
    if (not Equo.entropyTools.isRoot()):
        print_error(red("You are not ")+bold("root")+red("."))
	return 1

    # Options available for all the packages submodules
    smartRequestEmpty = False
    smartRequestSavedir = None
    savedir = False
    newopts = []
    for opt in options:
	if (opt == "--empty"):
	    smartRequestEmpty = True
	elif (opt == "--savedir"):
	    savedir = True
        else:
            if savedir:
                smartRequestSavedir = opt
                savedir = False
            else:
                newopts.append(opt)
    options = newopts

    rc = 0
    if (options[0] == "application"):
        rc = smartappsHandler(options[1:], emptydeps = smartRequestEmpty)
    elif (options[0] == "package"):
        rc = smartPackagesHandler(options[1:])
    elif (options[0] == "quickpkg"):
        rc = QuickpkgHandler(options[1:], savedir = smartRequestSavedir)
    elif (options[0] == "inflate") or (options[0] == "deflate") or (options[0] == "extract"):
        rc = CommonFlate(options[1:], action = options[0], savedir = smartRequestSavedir)
    else:
        rc = -10

    return rc


def QuickpkgHandler(mypackages, savedir = None):
    
    if (not mypackages):
        if not etpUi['quiet']: print_error(darkred(" * ")+red("No packages specified."))
        return 1
    
    if savedir == None:
        savedir = etpConst['packagestmpdir']
        if not os.path.isdir(etpConst['packagestmpdir']):
            os.makedirs(etpConst['packagestmpdir'])
    else:
        if not os.path.isdir(savedir):
            print_error(darkred(" * ")+red("--savedir ")+savedir+red(" does not exist."))
            return 4
    
    packages = []
    for opt in mypackages:
        match = Equo.clientDbconn.atomMatch(opt)
        if match[0] != -1:
            packages.append(match)
        else:
            if not etpUi['quiet']: print_warning(darkred(" * ")+red("Cannot find: ")+bold(opt))
    packages = Equo.entropyTools.filterDuplicatedEntries(packages)
    if (not packages):
        print_error(darkred(" * ")+red("No valid packages specified."))
        return 2

    # print the list
    if (not etpUi['quiet']) or (etpUi['ask']): print_info(darkgreen(" * ")+red("This is the list of the packages that would be quickpkg'd:"))
    pkgInfo = {}
    pkgData = {}
    for pkg in packages:
        atom = Equo.clientDbconn.retrieveAtom(pkg[0])
        pkgInfo[pkg] = atom
        pkgData[pkg] = Equo.clientDbconn.getPackageData(pkg[0])
        print_info(brown("\t[")+red("from:")+bold("installed")+brown("]")+" - "+atom)

    if (not etpUi['quiet']) or (etpUi['ask']):
        rc = Equo.entropyTools.askquestion(">>   Would you like to recompose the selected packages ?")
        if rc == "No":
            return 0

    for pkg in packages:
        if not etpUi['quiet']: print_info(brown(" * ")+red("Compressing: ")+darkgreen(pkgInfo[pkg]))
        resultfile = Equo.entropyTools.quickpkg(pkgdata = pkgData[pkg], dirpath = savedir)
        if resultfile == None:
            if not etpUi['quiet']: print_error(darkred(" * ")+red("Error creating package for: ")+bold(pkgInfo[pkg])+darkred(". Cannot continue."))
            return 3
        if not etpUi['quiet']: print_info(darkgreen("  * ")+red("Saved in: ")+resultfile)
    return 0

def CommonFlate(mytbz2s, action, savedir = None):

    if (not mytbz2s):
        print_error(darkred(" * ")+red("No packages specified."))
        return 1

    # test if portage is available
    try:
        import portageTools
    except:
        print_error(darkred(" * ")+bold("Portage")+red(" is not available."))
        return 1
    
    if savedir:
        if not os.path.isdir(savedir):
            print_error(darkred(" * ")+bold("--savedir")+red(" specified does not exist."))
            return 1
    else:
        savedir = etpConst['packagestmpdir']

    for tbz2 in mytbz2s:
        #print_info(brown(" * ")+darkred("Analyzing: ")+tbz2)
        if not (os.path.isfile(tbz2) and tbz2.endswith(".tbz2") and Equo.entropyTools.isEntropyTbz2(tbz2)):
            print_error(darkred(" * ")+bold(tbz2)+red(" is not a valid tbz2"))
            return 1
    
    if action == "inflate":
        rc = InflateHandler(mytbz2s, savedir)
    elif action == "deflate":
        rc = DeflateHandler(mytbz2s, savedir)
    elif action == "extract":
        rc = ExtractHandler(mytbz2s,savedir)
    else:
        rc = -10
    return rc


def InflateHandler(mytbz2s, savedir):

    print_info(brown(" Using branch: ")+bold(etpConst['branch']))

    # analyze files
    for tbz2 in mytbz2s:
        print_info(darkgreen(" * ")+darkred("Inflating: ")+tbz2, back = True)
        etptbz2path = savedir+"/"+os.path.basename(tbz2)
        if os.path.realpath(tbz2) != os.path.realpath(etptbz2path): # can convert a file without copying
            shutil.copy2(tbz2,etptbz2path)
        mydata = Equo.entropyTools.extractPkgData(etptbz2path)
        # append arbitrary revision
        mydata['revision'] = 9999
        # create temp database
        dbpath = etpConst['packagestmpdir']+"/"+str(Equo.entropyTools.getRandomNumber())
        while os.path.isfile(dbpath):
            dbpath = etpConst['packagestmpdir']+"/"+str(Equo.entropyTools.getRandomNumber())
        # create
        mydbconn = Equo.openGenericDatabase(dbpath)
        mydbconn.initializeDatabase()
        mydbconn.addPackage(mydata, revision = mydata['revision'])
        mydbconn.closeDB()
        Equo.entropyTools.aggregateEdb(tbz2file = etptbz2path, dbfile = dbpath)
        os.remove(dbpath)
        print_info(darkgreen(" * ")+darkred("Inflated package: ")+etptbz2path)

    return 0

def DeflateHandler(mytbz2s, savedir):

    # analyze files
    for tbz2 in mytbz2s:
        print_info(darkgreen(" * ")+darkred("Deflating: ")+tbz2, back = True)
        mytbz2 = Equo.entropyTools.removeEdb(tbz2,savedir)
        tbz2name = os.path.basename(mytbz2)[:-5] # remove .tbz2
        tbz2name = Equo.entropyTools.remove_tag(tbz2name)+".tbz2"
        newtbz2 = os.path.dirname(mytbz2)+"/"+tbz2name
        print_info(darkgreen(" * ")+darkred("Deflated package: ")+newtbz2)

    return 0

def ExtractHandler(mytbz2s, savedir):

    # analyze files
    for tbz2 in mytbz2s:
        print_info(darkgreen(" * ")+darkred("Extracting Entropy metadata from: ")+tbz2, back = True)
        dbpath = savedir+"/"+os.path.basename(tbz2)[:-4]+"db"
        if os.path.isfile(dbpath):
            os.remove(dbpath)
        # extract
        out = Equo.entropyTools.extractEdb(tbz2,dbpath = dbpath)
        print_info(darkgreen(" * ")+darkred("Extracted Entropy metadata from: ")+out)

    return 0

def smartPackagesHandler(mypackages):
    
    if (not mypackages):
        print_error(darkred(" * ")+red("No packages specified."))
        return 1
    
    packages = []
    for opt in mypackages:
        match = Equo.atomMatch(opt)
        if match[0] != -1:
            packages.append(match)
        else:
            print_warning(darkred(" * ")+red("Cannot find: ")+bold(opt))
    packages = Equo.entropyTools.filterDuplicatedEntries(packages)
    if (not packages):
        print_error(darkred(" * ")+red("No valid packages specified."))
        return 2

    # print the list
    print_info(darkgreen(" * ")+red("This is the list of the packages that would be merged into a single one:"))
    pkgInfo = {}
    for pkg in packages:
        dbconn = Equo.openRepositoryDatabase(pkg[1])
        atom = dbconn.retrieveAtom(pkg[0])
        pkgInfo[pkg] = atom
        print_info(brown("\t[")+red("from:")+pkg[1]+brown("]")+" - "+atom)

    rc = Equo.entropyTools.askquestion(">>   Would you like to create the packages above ?")
    if rc == "No":
        return 0

    print_info(darkgreen(" * ")+red("Creating merged Smart Package..."))
    rc = smartpackagegenerator(packages)
    if rc != 0:
        print_error(darkred(" * ")+red("Cannot continue."))
        return rc

    return 0


def smartpackagegenerator(matchedPackages):

    fetchdata = []
    matchedAtoms = {}
    for x in matchedPackages:
        xdbconn = Equo.openRepositoryDatabase(x[1])
        matchedAtoms[x] = {}
        xatom = xdbconn.retrieveAtom(x[0])
        xdownload = xdbconn.retrieveDownloadURL(x[0])
        xrevision = xdbconn.retrieveRevision(x[0])
        matchedAtoms[x]['atom'] = xatom
        matchedAtoms[x]['download'] = xdownload
        matchedAtoms[x]['revision'] = xrevision
        fetchdata.append([xatom,x])
    # run installPackages with onlyfetch
    rc = uiTools.installPackages(atomsdata = fetchdata, deps = False, onlyfetch = True)
    if rc[1] != 0:
        return rc[0]

    # create unpack dir and unpack all packages
    unpackdir = etpConst['entropyunpackdir']+"/smartpackage-"+str(Equo.entropyTools.getRandomNumber())
    while os.path.isdir(unpackdir):
        unpackdir = etpConst['entropyunpackdir']+"/smartpackage-"+str(Equo.entropyTools.getRandomNumber())
    if os.path.isdir(unpackdir):
        shutil.rmtree(unpackdir)
    os.makedirs(unpackdir)
    os.mkdir(unpackdir+"/content")
    os.mkdir(unpackdir+"/db")
    # create master database
    dbfile = unpackdir+"/db/merged.db"
    mergeDbconn = Equo.openGenericDatabase(dbfile, dbname = "client")
    mergeDbconn.initializeDatabase()
    mergeDbconn.createXpakTable()
    tmpdbfile = dbfile+"--readingdata"
    for package in matchedPackages:
        print_info(darkgreen("  * ")+brown(matchedAtoms[package]['atom'])+": "+red("collecting Entropy metadata"))
        Equo.entropyTools.extractEdb(etpConst['entropyworkdir']+"/"+matchedAtoms[package]['download'],tmpdbfile)
        # read db and add data to mergeDbconn
        mydbconn = Equo.openGenericDatabase(tmpdbfile)
        idpackages = mydbconn.listAllIdpackages()
        
        for myidpackage in idpackages:
            data = mydbconn.getPackageData(myidpackage)
            if len(idpackages) == 1:
                # just a plain package that would like to become smart
                xpakdata = Equo.entropyTools.readXpak(etpConst['entropyworkdir']+"/"+matchedAtoms[package]['download'])
            else:
                xpakdata = mydbconn.retrieveXpakMetadata(myidpackage) # already a smart package
            # add
            idpk, rev, y, status = mergeDbconn.handlePackage(etpData = data, forcedRevision = matchedAtoms[package]['revision']) # get the original rev
            del y
            mergeDbconn.storeXpakMetadata(idpk,xpakdata)
        mydbconn.closeDB()
        os.remove(tmpdbfile)
    
    # now we have the new database
    mergeDbconn.closeDB()
    
    # merge packages
    for package in matchedPackages:
        print_info(darkgreen("  * ")+brown(matchedAtoms[package]['atom'])+": "+red("unpacking content"))
        rc = Equo.entropyTools.uncompressTarBz2(etpConst['entropyworkdir']+"/"+matchedAtoms[x]['download'], extractPath = unpackdir+"/content")
        if rc != 0:
            print_error(darkred(" * ")+red("Unpack failed due to unknown reasons."))
            return rc
    
    if not os.path.isdir(etpConst['smartpackagesdir']):
        os.makedirs(etpConst['smartpackagesdir'])
    print_info(darkgreen("  * ")+red("Compressing smart package"))
    atoms = []
    for x in matchedAtoms:
        atoms.append(matchedAtoms[x]['atom'].split("/")[1])
    atoms = '+'.join(atoms)
    rc = Equo.entropyTools.compressTarBz2(etpConst['smartpackagesdir']+"/"+atoms+".tbz2",unpackdir+"/content")
    if rc != 0:
        print_error(darkred(" * ")+red("Compress failed due to unknown reasons."))
        return rc
    # adding entropy database
    if not os.path.isfile(etpConst['smartpackagesdir']+"/"+atoms+".tbz2"):
        print_error(darkred(" * ")+red("Compressed file does not exist."))
        return 1
    
    Equo.entropyTools.aggregateEdb(etpConst['smartpackagesdir']+"/"+atoms+".tbz2",dbfile)
    print_info("\t"+etpConst['smartpackagesdir']+"/"+atoms+".tbz2")
    shutil.rmtree(unpackdir,True)
    return 0


def smartappsHandler(mypackages, emptydeps = False):
    
    if (not mypackages):
        print_error(darkred(" * ")+red("No packages specified."))
        return 1
    
    gplusplus = os.system("which g++ &> /dev/null")
    if gplusplus != 0:
        print_error(darkred(" * ")+red("Cannot find G++ compiler."))
        return gplusplus
    
    packages = set()
    for opt in mypackages:
        match = Equo.atomMatch(opt)
        if match[0] != -1:
            packages.add(match)
        else:
            print_warning(darkred(" * ")+red("Cannot find: ")+bold(opt))

    if (not packages):
        print_error(darkred(" * ")+red("No valid packages specified."))
        return 2

    # print the list
    print_info(darkgreen(" * ")+red("This is the list of the packages that would be worked out:"))
    pkgInfo = {}
    for pkg in packages:
        dbconn = Equo.openRepositoryDatabase(pkg[1])
        atom = dbconn.retrieveAtom(pkg[0])
        pkgInfo[pkg] = atom
        print_info(brown("\t[")+red("from:")+pkg[1]+red("|SMART")+brown("]")+" - "+atom)

    rc = Equo.entropyTools.askquestion(">>   Would you like to create the packages above ?")
    if rc == "No":
        return 0

    for pkg in packages:
        print_info(darkgreen(" * ")+red("Creating Smart Application from ")+bold(pkgInfo[pkg]))
        rc = smartgenerator(pkg, emptydeps = emptydeps)
        if rc != 0:
            print_error(darkred(" * ")+red("Cannot continue."))
            return rc
    return 0

# tool that generates .tar.bz2 packages with all the binary dependencies included
def smartgenerator(atomInfo, emptydeps = False):
    
    dbconn = Equo.openRepositoryDatabase(atomInfo[1])
    idpackage = atomInfo[0]
    atom = dbconn.retrieveAtom(idpackage)
    
    # check if the application package is available, otherwise, download
    pkgfilepath = dbconn.retrieveDownloadURL(idpackage)
    pkgcontent = dbconn.retrieveContent(idpackage)
    pkgbranch = dbconn.retrieveBranch(idpackage)
    pkgfilename = os.path.basename(pkgfilepath)
    pkgname = pkgfilename.split(".tbz2")[0]
    
    pkgdependencies, removal, result = Equo.retrieveInstallQueue([atomInfo], empty_deps = emptydeps)
    # flatten them
    pkgs = []
    if (result == 0):
	for x in range(len(pkgdependencies)):
	    #print x
	    for a in pkgdependencies[x]:
		pkgs.append(a)
    else:
	print_error(darkgreen(" * ")+red("Missing dependencies: "))
        for x in pkgdependencies:
            print_error(darkgreen("   ## ")+x)
	return 1

    pkgs = [x for x in pkgs if x != atomInfo]
    if pkgs:
        print_info(darkgreen(" * ")+red("This is the list of the dependencies that would be included:"))
    for i in pkgs:
        mydbconn = Equo.openRepositoryDatabase(i[1])
	atom = mydbconn.retrieveAtom(i[0])
        print_info(darkgreen("   (x) ")+red(atom))

    fetchdata = []
    fetchdata.append([atom,atomInfo])
    for x in pkgs:
        xdbconn = Equo.openRepositoryDatabase(x[1])
        xatom = xdbconn.retrieveAtom(x[0])
        fetchdata.append([xatom,x])
    # run installPackages with onlyfetch
    rc = uiTools.installPackages(atomsdata = fetchdata, deps = False, onlyfetch = True)
    if rc[1] != 0:
        return rc[0]

    # create the working directory
    pkgtmpdir = etpConst['entropyunpackdir']+"/"+pkgname
    #print "DEBUG: "+pkgtmpdir
    if os.path.isdir(pkgtmpdir):
	shutil.rmtree(pkgtmpdir)
    os.makedirs(pkgtmpdir)
    mainBinaryPath = etpConst['packagesbindir']+"/"+pkgbranch+"/"+pkgfilename
    print_info(darkgreen(" * ")+red("Unpacking main package ")+bold(str(pkgfilename)))
    Equo.entropyTools.uncompressTarBz2(mainBinaryPath,pkgtmpdir) # first unpack

    binaryExecs = []
    for item in pkgcontent:
	# remove /
	filepath = pkgtmpdir+item
	import commands
	if os.access(filepath,os.X_OK):
	    # test if it's an exec
	    out = commands.getoutput("file "+filepath).split("\n")[0]
	    if out.find("LSB executable") != -1:
		binaryExecs.append(item)
	# check if file is executable

    # now uncompress all the rest
    for dep in pkgs:
        mydbconn = Equo.openRepositoryDatabase(dep[1])
	download = os.path.basename(mydbconn.retrieveDownloadURL(dep[0]))
	depbranch = mydbconn.retrieveBranch(dep[0])
        depatom = mydbconn.retrieveAtom(dep[0])
	print_info(darkgreen(" * ")+red("Unpacking dependency package ")+bold(depatom))
	deppath = etpConst['packagesbindir']+"/"+depbranch+"/"+download
	Equo.entropyTools.uncompressTarBz2(deppath,pkgtmpdir) # first unpack
	

    # remove unwanted files (header files)
    os.system('for file in `find '+pkgtmpdir+' -name "*.h"`; do rm $file; done')

    # now create the bash script for each binaryExecs
    os.makedirs(pkgtmpdir+"/wrp")
    bashScript = []
    bashScript.append(
    			'#!/bin/sh\n'
			'cd $1\n'

			'MYPYP=$(find $PWD/lib/python2.4/site-packages/ -type d -printf %p: 2> /dev/null)\n'
			'MYPYP2=$(find $PWD/lib/python2.5/site-packages/ -type d -printf %p: 2> /dev/null)\n'
			'export PYTHONPATH=$MYPYP:MYPYP2:$PYTHONPATH\n'

			'export PATH=$PWD:$PWD/sbin:$PWD/bin:$PWD/usr/bin:$PWD/usr/sbin:$PWD/usr/X11R6/bin:$PWD/libexec:$PWD/usr/local/bin:$PWD/usr/local/sbin:$PATH\n'
			
			'export LD_LIBRARY_PATH='
			'$PWD/lib:'
			'$PWD/lib64:'
			'$PWD/usr/lib:'
			'$PWD/usr/lib64:'
			'$PWD/usr/lib/nss:'
			'$PWD/usr/lib/nspr:'
			'$PWD/usr/lib64/nss:'
			'$PWD/usr/lib64/nspr:'
			'$PWD/usr/qt/3/lib:'
			'$PWD/usr/qt/3/lib64:'
			'$PWD/usr/kde/3.5/lib:'
			'$PWD/usr/kde/3.5/lib64:'
			'$LD_LIBRARY_PATH\n'
			
			'export KDEDIRS=$PWD/usr/kde/3.5:$PWD/usr:$KDEDIRS\n'
			
			'export PERL5LIB=$PWD/usr/lib/perl5:$PWD/share/perl5:$PWD/usr/lib/perl5/5.8.1'
			':$PWD/usr/lib/perl5/5.8.2:'
			':$PWD/usr/lib/perl5/5.8.3:'
			':$PWD/usr/lib/perl5/5.8.4:'
			':$PWD/usr/lib/perl5/5.8.5:'
			':$PWD/usr/lib/perl5/5.8.6:'
			':$PWD/usr/lib/perl5/5.8.7:'
			':$PWD/usr/lib/perl5/5.8.8:'
			':$PWD/usr/lib/perl5/5.8.9:'
			':$PWD/usr/lib/perl5/5.8.10\n'
			
			'export MANPATH=$PWD/share/man:$MANPATH\n'
			'export GUILE_LOAD_PATH=$PWD/share/:$GUILE_LOAD_PATH\n'
			'export SCHEME_LIBRARY_PATH=$PWD/share/slib:$SCHEME_LIBRARY_PATH\n'
			
			'# Setup pango\n'
			'MYPANGODIR=$(find $PWD/usr/lib/pango -name modules)\n'
			'if [ -n "$MYPANGODIR" ]; then\n'
			'    export PANGO_RC_FILE=$PWD/etc/pango/pangorc\n'
			'    echo "[Pango]" > $PANGO_RC_FILE\n'
			'    echo "ModulesPath=${MYPANGODIR}" >> $PANGO_RC_FILE\n'
			'    echo "ModuleFiles=${PWD}/etc/pango/pango.modules" >> $PANGO_RC_FILE\n'
			'    pango-querymodules > ${PWD}/etc/pango/pango.modules\n'
			'fi\n'
			'$2\n'
    )
    f = open(pkgtmpdir+"/wrp/wrapper","w")
    f.writelines(bashScript)
    f.flush()
    f.close()
    # chmod
    os.chmod(pkgtmpdir+"/wrp/wrapper",0755)
    
    # now list files in /sh and create .desktop files
    for item in binaryExecs:
	item = file.split("/")[len(item.split("/"))-1]
	runFile = []
	runFile.append(
			'#include <cstdlib>\n'
			'#include <cstdio>\n'
			'#include <stdio.h>\n'
			'int main() {\n'
			'  int rc = system(\n'
			'                "pid=$(pidof '+item+'.exe);"\n'
			'                "listpid=$(ps x | grep $pid);"\n'
			'                "filename=$(echo $listpid | cut -d\' \' -f 5);"'
			'                "currdir=$(dirname $filename);"\n'
			'                "/bin/sh $currdir/wrp/wrapper $currdir '+item+'" );\n'
			'  return rc;\n'
			'}\n'
	)
	f = open(pkgtmpdir+"/"+item+".cc","w")
	f.writelines(runFile)
	f.flush()
	f.close()
	# now compile
	Equo.entropyTools.spawnCommand("cd "+pkgtmpdir+"/ ; g++ -Wall "+item+".cc -o "+item+".exe")
	os.remove(pkgtmpdir+"/"+item+".cc")

    smartpath = etpConst['smartappsdir']+"/"+pkgname+"-"+etpConst['currentarch']+".tbz2"
    print_info(darkgreen(" * ")+red("Compressing smart application: ")+bold(atom))
    print_info("\t"+smartpath)
    Equo.entropyTools.compressTarBz2(smartpath,pkgtmpdir+"/")
    shutil.rmtree(pkgtmpdir,True)
    
    return 0