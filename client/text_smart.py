#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy smart functionalities library

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
import shutil
from entropyConstants import *
from outputTools import *
import text_ui
from entropy.i18n import _

def smart(options):

    # check if I am root
    if (not text_ui.Equo.entropyTools.isRoot()):
        mytxt = _("You are not") # you are not root
        print_error(red(mytxt)+bold("root")+red("."))
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
        elif opt.startswith("--"):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return
        else:
            if savedir:
                try:
                    smartRequestSavedir = os.path.realpath(opt)
                except OSError:
                    smartRequestSavedir = None
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
        mytxt = _("No packages specified")
        if not etpUi['quiet']: print_error(darkred(" * ")+red(mytxt+"."))
        return 1

    if savedir == None:
        savedir = etpConst['packagestmpdir']
        if not os.path.isdir(etpConst['packagestmpdir']):
            os.makedirs(etpConst['packagestmpdir'])
    else:
        if not os.path.isdir(savedir):
            print_error(darkred(" * ")+red("--savedir ")+savedir+red(" %s." % (_("does not exist"),) ))
            return 4

    packages = []
    for opt in mypackages:
        match = text_ui.Equo.clientDbconn.atomMatch(opt)
        if match[0] != -1:
            packages.append(match)
        else:
            if not etpUi['quiet']: print_warning(darkred(" * ")+red("%s: " % (_("Cannot find"),))+bold(opt))
    packages = text_ui.Equo.entropyTools.filterDuplicatedEntries(packages)
    if (not packages):
        print_error(darkred(" * ")+red("%s." % (_("No valid packages specified"),)))
        return 2

    # print the list
    mytxt = _("This is the list of the packages that would be quickpkg'd")
    if (not etpUi['quiet']) or (etpUi['ask']): print_info(darkgreen(" * ")+red(mytxt+":"))
    pkgInfo = {}
    for pkg in packages:
        atom = text_ui.Equo.clientDbconn.retrieveAtom(pkg[0])
        pkgInfo[pkg] = {}
        pkgInfo[pkg]['atom'] = atom
        pkgInfo[pkg]['idpackage'] = pkg[0]
        print_info(brown("\t[")+red("%s:" % (_("from"),))+bold(_("installed"))+brown("]")+" - "+atom)

    if (not etpUi['quiet']) or (etpUi['ask']):
        rc = text_ui.Equo.askQuestion(">>   %s" % (_("Would you like to recompose the selected packages ?"),))
        if rc == "No":
            return 0

    for pkg in packages:
        if not etpUi['quiet']: print_info(brown(" * ")+red("%s: " % (_("Compressing"),))+darkgreen(pkgInfo[pkg]['atom']))
        pkgdata = text_ui.Equo.clientDbconn.getPackageData(pkgInfo[pkg]['idpackage'])
        resultfile = text_ui.Equo.quickpkg_handler(pkgdata = pkgdata, dirpath = savedir)
        if resultfile == None:
            if not etpUi['quiet']:
                print_error(darkred(" * ") + red("%s: " % (_("Error while creating package for"),)) + \
                    bold(pkgInfo[pkg])+darkred(". %s." % (_("Cannot continue"),)))
            return 3
        if not etpUi['quiet']:
            print_info(darkgreen("  * ")+red("%s: " % (_("Saved in"),))+resultfile)
    return 0

def CommonFlate(mytbz2s, action, savedir = None):

    if (not mytbz2s):
        print_error(darkred(" * ")+red("%s." % (_("No packages specified"),)))
        return 1

    # test if portage is available
    try:
        Spm = text_ui.Equo.Spm()
        del Spm
    except Exception, e:
        text_ui.Equo.entropyTools.printTraceback()
        mytxt = _("Source Package Manager backend not available")
        print_error(darkred(" * ")+red("%s: %s" % (mytxt,e,)))
        return 1

    if savedir:
        if not os.path.isdir(savedir):
            print_error(darkred(" * ")+bold("--savedir")+":"+red(" %s." % (_("directory does not exist"),)))
            return 1
    else:
        savedir = etpConst['packagestmpdir']

    for tbz2 in mytbz2s:
        #print_info(brown(" * ")+darkred("Analyzing: ")+tbz2)
        if not (os.path.isfile(tbz2) and tbz2.endswith(etpConst['packagesext']) and \
            text_ui.Equo.entropyTools.isEntropyTbz2(tbz2)):
                print_error(darkred(" * ")+bold(tbz2)+red(" %s" % (_("is not a valid Entropy package"),)))
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

    print_info(brown(" %s: " % (_("Using branch"),))+bold(etpConst['branch']))

    # analyze files
    for tbz2 in mytbz2s:
        print_info(darkgreen(" * ")+darkred("Inflating: ")+tbz2, back = True)
        etptbz2path = savedir+"/"+os.path.basename(tbz2)
        if os.path.realpath(tbz2) != os.path.realpath(etptbz2path): # can convert a file without copying
            shutil.copy2(tbz2,etptbz2path)
        mydata = text_ui.Equo.extract_pkg_metadata(etptbz2path)
        # append arbitrary revision
        mydata['revision'] = 9999
        mydata['download'] = mydata['download'][:-5]+"~9999.tbz2"
        # migrate to the proper format
        final_tbz2path = os.path.join(os.path.dirname(etptbz2path),os.path.basename(mydata['download']))
        shutil.move(etptbz2path,final_tbz2path)
        etptbz2path = final_tbz2path
        # create temp database
        dbpath = etpConst['packagestmpdir']+"/"+str(text_ui.Equo.entropyTools.getRandomNumber())
        while os.path.isfile(dbpath):
            dbpath = etpConst['packagestmpdir']+"/"+str(text_ui.Equo.entropyTools.getRandomNumber())
        # create
        mydbconn = text_ui.Equo.openGenericDatabase(dbpath)
        mydbconn.initializeDatabase()
        idpackage, yyy, xxx = mydbconn.addPackage(mydata, revision = mydata['revision'])
        del yyy, xxx
        myQA = text_ui.Equo.QA()
        myQA.scan_missing_dependencies([idpackage], mydbconn)
        mydbconn.closeDB()
        text_ui.Equo.entropyTools.aggregateEdb(tbz2file = etptbz2path, dbfile = dbpath)
        os.remove(dbpath)
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Inflated package"),))+etptbz2path)

    return 0

def DeflateHandler(mytbz2s, savedir):

    # analyze files
    for tbz2 in mytbz2s:
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Deflating"),))+tbz2, back = True)
        mytbz2 = text_ui.Equo.entropyTools.removeEdb(tbz2,savedir)
        tbz2name = os.path.basename(mytbz2)[:-5] # remove .tbz2
        tbz2name = text_ui.Equo.entropyTools.remove_tag(tbz2name)+etpConst['packagesext']
        newtbz2 = os.path.dirname(mytbz2)+"/"+tbz2name
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Deflated package"),))+newtbz2)

    return 0

def ExtractHandler(mytbz2s, savedir):

    # analyze files
    for tbz2 in mytbz2s:
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Extracting Entropy metadata from"),))+tbz2, back = True)
        dbpath = savedir+"/"+os.path.basename(tbz2)[:-4]+"db"
        if os.path.isfile(dbpath):
            os.remove(dbpath)
        # extract
        out = text_ui.Equo.entropyTools.extractEdb(tbz2,dbpath = dbpath)
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Extracted Entropy metadata from"),))+out)

    return 0

def smartPackagesHandler(mypackages):

    if (not mypackages):
        print_error(darkred(" * ")+red("%s." % (_("No packages specified"),)))
        return 1

    packages = []
    for opt in mypackages:
        match = text_ui.Equo.atomMatch(opt)
        if match[0] != -1:
            packages.append(match)
        else:
            print_warning(darkred(" * ")+red("%s: " % (_("Cannot find"),))+bold(opt))
    packages = text_ui.Equo.entropyTools.filterDuplicatedEntries(packages)
    if (not packages):
        print_error(darkred(" * ")+red("%s." % (_("No valid packages specified"),)))
        return 2

    # print the list
    print_info(darkgreen(" * ")+red("%s:" % (_("This is the list of the packages that would be merged into a single one"),)))
    pkgInfo = {}
    for pkg in packages:
        dbconn = text_ui.Equo.openRepositoryDatabase(pkg[1])
        atom = dbconn.retrieveAtom(pkg[0])
        pkgInfo[pkg] = atom
        print_info(brown("\t[")+red("%s:" % (_("from"),))+pkg[1]+brown("]")+" - "+atom)

    rc = text_ui.Equo.askQuestion(">>   %s" % (_("Would you like to create the packages above ?"),))
    if rc == "No":
        return 0

    print_info(darkgreen(" * ")+red("%s..." % (_("Creating merged Smart Package"),)))
    rc = smartpackagegenerator(packages)
    if rc != 0:
        print_error(darkred(" * ")+red("%s." % (_("Cannot continue"),)))
        return rc

    return 0


def smartpackagegenerator(matchedPackages):

    fetchdata = []
    matchedAtoms = {}
    for x in matchedPackages:
        xdbconn = text_ui.Equo.openRepositoryDatabase(x[1])
        matchedAtoms[x] = {}
        xatom = xdbconn.retrieveAtom(x[0])
        xdownload = xdbconn.retrieveDownloadURL(x[0])
        xrevision = xdbconn.retrieveRevision(x[0])
        matchedAtoms[x]['atom'] = xatom
        matchedAtoms[x]['download'] = xdownload
        matchedAtoms[x]['revision'] = xrevision
        fetchdata.append(x)
    # run installPackages with onlyfetch
    rc = text_ui.installPackages(atomsdata = fetchdata, deps = False, onlyfetch = True)
    if rc[1] != 0:
        return rc[0]

    # create unpack dir and unpack all packages
    unpackdir = etpConst['entropyunpackdir']+"/smartpackage-"+str(text_ui.Equo.entropyTools.getRandomNumber())
    while os.path.isdir(unpackdir):
        unpackdir = etpConst['entropyunpackdir']+"/smartpackage-"+str(text_ui.Equo.entropyTools.getRandomNumber())
    if os.path.isdir(unpackdir):
        shutil.rmtree(unpackdir)
    os.makedirs(unpackdir)
    os.mkdir(unpackdir+"/content")
    os.mkdir(unpackdir+"/db")
    # create master database
    dbfile = unpackdir+"/db/merged.db"
    mergeDbconn = text_ui.Equo.openGenericDatabase(dbfile, dbname = "client")
    mergeDbconn.initializeDatabase()
    mergeDbconn.createXpakTable()
    tmpdbfile = dbfile+"--readingdata"
    for package in matchedPackages:
        print_info(darkgreen("  * ")+brown(matchedAtoms[package]['atom'])+": "+red(_("collecting Entropy metadata")))
        text_ui.Equo.entropyTools.extractEdb(etpConst['entropyworkdir']+"/"+matchedAtoms[package]['download'],tmpdbfile)
        # read db and add data to mergeDbconn
        mydbconn = text_ui.Equo.openGenericDatabase(tmpdbfile)
        idpackages = mydbconn.listAllIdpackages()

        for myidpackage in idpackages:
            data = mydbconn.getPackageData(myidpackage)
            if len(idpackages) == 1:
                # just a plain package that would like to become smart
                xpakdata = text_ui.Equo.entropyTools.readXpak(etpConst['entropyworkdir']+"/"+matchedAtoms[package]['download'])
            else:
                xpakdata = mydbconn.retrieveXpakMetadata(myidpackage) # already a smart package
            # add
            idpk, rev, y = mergeDbconn.handlePackage(etpData = data, forcedRevision = matchedAtoms[package]['revision']) # get the original rev
            del y
            mergeDbconn.storeXpakMetadata(idpk,xpakdata)
        mydbconn.closeDB()
        os.remove(tmpdbfile)

    # now we have the new database
    mergeDbconn.closeDB()

    # merge packages
    for package in matchedPackages:
        print_info(darkgreen("  * ")+brown(matchedAtoms[package]['atom'])+": "+red("unpacking content"))
        rc = text_ui.Equo.entropyTools.uncompressTarBz2(etpConst['entropyworkdir']+"/"+matchedAtoms[x]['download'], extractPath = unpackdir+"/content")
        if rc != 0:
            print_error(darkred(" * ")+red("%s." % (_("Unpack failed due to unknown reasons"),)))
            return rc

    if not os.path.isdir(etpConst['smartpackagesdir']):
        os.makedirs(etpConst['smartpackagesdir'])
    print_info(darkgreen("  * ")+red(_("Compressing smart package")))
    atoms = []
    for x in matchedAtoms:
        atoms.append(matchedAtoms[x]['atom'].split("/")[1])
    atoms = '+'.join(atoms)
    rc = text_ui.Equo.entropyTools.compressTarBz2(etpConst['smartpackagesdir']+"/"+atoms+etpConst['packagesext'],unpackdir+"/content")
    if rc != 0:
        print_error(darkred(" * ")+red("%s." % (_("Compression failed due to unknown reasons"),)))
        return rc
    # adding entropy database
    if not os.path.isfile(etpConst['smartpackagesdir']+"/"+atoms+etpConst['packagesext']):
        print_error(darkred(" * ")+red("%s." % (_("Compressed file does not exist"),)))
        return 1

    text_ui.Equo.entropyTools.aggregateEdb(etpConst['smartpackagesdir']+"/"+atoms+etpConst['packagesext'],dbfile)
    print_info("\t"+etpConst['smartpackagesdir']+"/"+atoms+etpConst['packagesext'])
    shutil.rmtree(unpackdir,True)
    return 0


def smartappsHandler(mypackages, emptydeps = False):

    if (not mypackages):
        print_error(darkred(" * ")+red("%s." % (_("No packages specified"),)))
        return 1

    gplusplus = os.system("which g++ &> /dev/null")
    if gplusplus != 0:
        print_error(darkred(" * ")+red("%s." % (_("Cannot find G++ compiler"),)))
        return gplusplus

    packages = set()
    for opt in mypackages:
        match = text_ui.Equo.atomMatch(opt)
        if match[0] != -1:
            packages.add(match)
        else:
            print_warning(darkred(" * ")+red("%s: " %(_("Cannot find"),))+bold(opt))

    if (not packages):
        print_error(darkred(" * ")+red("%s." % (_("No valid packages specified"),)))
        return 2

    # print the list
    print_info(darkgreen(" * ")+red("%s:" % (_("This is the list of the packages that would be worked out"),)))
    pkgInfo = {}
    for pkg in packages:
        dbconn = text_ui.Equo.openRepositoryDatabase(pkg[1])
        atom = dbconn.retrieveAtom(pkg[0])
        pkgInfo[pkg] = atom
        print_info(brown("\t[")+red("%s:" % (_("from"),))+pkg[1]+red("|SMART")+brown("]")+" - "+atom)

    rc = text_ui.Equo.askQuestion(">>   %s" % (_("Would you like to create the packages above ?"),))
    if rc == "No":
        return 0

    for pkg in packages:
        print_info(darkgreen(" * ")+red("%s " % (_("Creating Smart Application from"),))+bold(pkgInfo[pkg]))
        rc = smartgenerator(pkg, emptydeps = emptydeps)
        if rc != 0:
            print_error(darkred(" * ")+red("%s." % (_("Cannot continue"),)))
            return rc
    return 0

# tool that generates .tar.bz2 packages with all the binary dependencies included
def smartgenerator(atomInfo, emptydeps = False):

    import entropyTools
    dbconn = text_ui.Equo.openRepositoryDatabase(atomInfo[1])
    idpackage = atomInfo[0]
    atom = dbconn.retrieveAtom(idpackage)

    # check if the application package is available, otherwise, download
    pkgfilepath = dbconn.retrieveDownloadURL(idpackage)
    pkgcontent = dbconn.retrieveContent(idpackage)
    pkgbranch = dbconn.retrieveBranch(idpackage)
    pkgfilename = os.path.basename(pkgfilepath)
    pkgname = pkgfilename.split(etpConst['packagesext'])[0].replace(":","_").replace("~","_")

    pkgdependencies, removal, result = text_ui.Equo.retrieveInstallQueue([atomInfo], empty_deps = emptydeps, deep_deps = False)
    #FIXME: fix dependencies stuff
    # flatten them
    if (result == 0):
        pkgs = pkgdependencies
    else:
        print_error(darkgreen(" * ")+red("%s: " % (_("Missing dependencies"),)))
        for x in pkgdependencies:
            print_error(darkgreen("   ## ")+x)
        return 1

    pkgs = [x for x in pkgs if x != atomInfo]
    if pkgs:
        print_info(darkgreen(" * ")+red("%s:" % (_("This is the list of the dependencies that would be included"),)))
    for i in pkgs:
        mydbconn = text_ui.Equo.openRepositoryDatabase(i[1])
        atom = mydbconn.retrieveAtom(i[0])
        print_info(darkgreen("   (x) ")+red(atom))

    fetchdata = []
    fetchdata.append(atomInfo)
    fetchdata += pkgs
    # run installPackages with onlyfetch
    rc = text_ui.installPackages(atomsdata = fetchdata, deps = False, onlyfetch = True)
    if rc[1] != 0:
        return rc[0]

    # create the working directory
    pkgtmpdir = os.path.join(etpConst['entropyunpackdir'],pkgname)
    pkgdatadir = os.path.join(pkgtmpdir,pkgname)
    if os.path.isdir(pkgdatadir):
        shutil.rmtree(pkgdatadir)
    os.makedirs(pkgdatadir)
    mainBinaryPath = os.path.join(etpConst['packagesbindir'],pkgbranch,pkgfilename)
    print_info(darkgreen(" * ")+red("%s " % (_("Unpacking the main package"),))+bold(str(pkgfilename)))
    entropyTools.uncompressTarBz2(mainBinaryPath,pkgdatadir) # first unpack

    binaryExecs = []
    for item in pkgcontent:
        filepath = pkgdatadir+item
        import commands
        if os.access(filepath,os.X_OK):
            if commands.getoutput("file %s" % (filepath,)).find("LSB executable") != -1:
                binaryExecs.append(item)

    # now uncompress all the rest
    for dep in pkgs:
        mydbconn = text_ui.Equo.openRepositoryDatabase(dep[1])
        download = os.path.basename(mydbconn.retrieveDownloadURL(dep[0]))
        depbranch = mydbconn.retrieveBranch(dep[0])
        depatom = mydbconn.retrieveAtom(dep[0])
        print_info(darkgreen(" * ")+red("%s " % (_("Unpacking dependency package"),))+bold(depatom))
        deppath = os.path.join(etpConst['packagesbindir'],depbranch,download)
        entropyTools.uncompressTarBz2(deppath,pkgdatadir) # first unpack

    # now create the bash script for each binaryExecs
    os.makedirs(pkgdatadir+"/wrp")
    sh_script = """
#!/bin/sh
cd $1
MYPYP=$(find $PWD/lib/python2.4/site-packages/ -type d -printf %p: 2> /dev/null)
MYPYP2=$(find $PWD/lib/python2.5/site-packages/ -type d -printf %p: 2> /dev/null)
MYPYP3=$(find $PWD/lib/python2.6/site-packages/ -type d -printf %p: 2> /dev/null)
export PYTHONPATH=$MYPYP:$MYPYP2:$MYPYP3:$PYTHONPATH
export PATH=$PWD:$PWD/sbin:$PWD/bin:$PWD/usr/bin:$PWD/usr/sbin:$PWD/usr/X11R6/bin:$PWD/libexec:$PWD/usr/local/bin:$PWD/usr/local/sbin:$PATH
export LD_LIBRARY_PATH=$PWD/lib:$PWD/lib64:$PWD/usr/lib:$PWD/usr/lib64:$PWD/usr/lib/nss:$PWD/usr/lib/nspr:$PWD/usr/lib64/nss:$PWD/usr/lib64/nspr:$PWD/usr/qt/3/lib:$PWD/usr/qt/3/lib64:$PWD/usr/kde/3.5/lib:$PWD/usr/kde/3.5/lib64:$LD_LIBRARY_PATH
export KDEDIRS=$PWD/usr/kde/3.5:$PWD/usr:$KDEDIRS
export PERL5LIB=$PWD/usr/lib/perl5:$PWD/share/perl5:$PWD/usr/lib/perl5/5.8.1:$PWD/usr/lib/perl5/5.8.2:$PWD/usr/lib/perl5/5.8.3:$PWD/usr/lib/perl5/5.8.4:$PWD/usr/lib/perl5/5.8.5:$PWD/usr/lib/perl5/5.8.6:$PWD/usr/lib/perl5/5.8.7:$PWD/usr/lib/perl5/5.8.8:$PWD/usr/lib/perl5/5.8.9:$PWD/usr/lib/perl5/5.8.10
export MANPATH=$PWD/share/man:$MANPATH
export GUILE_LOAD_PATH=$PWD/share/:$GUILE_LOAD_PATH
export SCHEME_LIBRARY_PATH=$PWD/share/slib:$SCHEME_LIBRARY_PATH
# Setup pango
PANGODIR=$PWD/usr/lib/pango
if [ -d "$PANGODIR" ]; then
    MYPANGODIR=$(find $PWD/usr/lib/pango -name modules)
    if [ -n "$MYPANGODIR" ]; then
        export PANGO_RC_FILE=$PWD/etc/pango/pangorc
        echo "[Pango]" > $PANGO_RC_FILE
        echo "ModulesPath=${MYPANGODIR}" >> $PANGO_RC_FILE
        echo "ModuleFiles=${PWD}/etc/pango/pango.modules" >> $PANGO_RC_FILE
        pango-querymodules > ${PWD}/etc/pango/pango.modules
    fi
fi
$2
"""
    wrapper_path = pkgdatadir+"/wrp/wrapper"
    f = open(wrapper_path,"w")
    f.write(sh_script)
    f.flush()
    f.close()
    # chmod
    os.chmod(wrapper_path,0755)

    cc_content = """
#include <cstdlib>
#include <cstdio>
#include <stdio.h>
int main() {
    int rc = system("pid=$(pidof --item--.exe);"
                    "listpid=$(ps x | grep $pid);"
                "filename=$(echo $listpid | cut -d' ' -f 5);"
                "currdir=$(dirname $filename);"
                "/bin/sh $currdir/wrp/wrapper $currdir --item--" );
    return rc;
}
"""

    for item in binaryExecs:
        item = item.split("/")[-1]
        item_content = cc_content.replace("--item--",item)
        item_cc = "%s/%s.cc" % (pkgdatadir,item,)
        f = open(item_cc,"w")
        f.write(item_content)
        f.flush()
        f.close()
        # now compile
        os.system("cd %s/; g++ -Wall %s.cc -o %s.exe" % (pkgdatadir,item,item,))
        os.remove(item_cc)

    smartpath = "%s/%s-%s%s" % (etpConst['smartappsdir'],pkgname,etpConst['currentarch'],etpConst['packagesext'],)
    print_info(darkgreen(" * ")+red("%s: " % (_("Compressing smart application"),))+bold(atom))
    print_info("\t%s" % (smartpath,))
    text_ui.Equo.entropyTools.compressTarBz2(smartpath,pkgtmpdir)
    shutil.rmtree(pkgtmpdir,True)

    return 0