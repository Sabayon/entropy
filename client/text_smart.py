# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
import sys
if sys.hexversion >= 0x3000000:
    from subprocess import getoutput
else:
    from commands import getoutput
import shutil
from entropy.const import *
from entropy.output import *
from entropy.i18n import _
from entropy.client.interfaces import Client
Equo = Client()

def smart(options):

    # check if I am root
    if (not Equo.entropyTools.is_root()):
        mytxt = _("You are not") # you are not root
        print_error(red(mytxt)+bold("root")+red("."))
        return 1

    # Options available for all the packages submodules
    smartRequestSavedir = None
    savedir = False
    newopts = []
    for opt in options:
        if (opt == "--savedir"):
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
        rc = smartappsHandler(options[1:])
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
        match = Equo.clientDbconn.atomMatch(opt)
        if match[0] != -1:
            packages.append(match)
        else:
            if not etpUi['quiet']: print_warning(darkred(" * ")+red("%s: " % (_("Cannot find"),))+bold(opt))
    packages = Equo.entropyTools.filter_duplicated_entries(packages)
    if (not packages):
        print_error(darkred(" * ")+red("%s." % (_("No valid packages specified"),)))
        return 2

    # print the list
    mytxt = _("This is the list of the packages that would be quickpkg'd")
    if (not etpUi['quiet']) or (etpUi['ask']): print_info(darkgreen(" * ")+red(mytxt+":"))
    pkgInfo = {}
    for pkg in packages:
        atom = Equo.clientDbconn.retrieveAtom(pkg[0])
        pkgInfo[pkg] = {}
        pkgInfo[pkg]['atom'] = atom
        pkgInfo[pkg]['idpackage'] = pkg[0]
        print_info(brown("\t[")+red("%s:" % (_("from"),))+bold(_("installed"))+brown("]")+" - "+atom)

    if (not etpUi['quiet']) or (etpUi['ask']):
        rc = Equo.askQuestion(">>   %s" % (_("Would you like to recompose the selected packages ?"),))
        if rc == _("No"):
            return 0

    for pkg in packages:
        if not etpUi['quiet']: print_info(brown(" * ")+red("%s: " % (_("Compressing"),))+darkgreen(pkgInfo[pkg]['atom']))
        pkgdata = Equo.clientDbconn.getPackageData(pkgInfo[pkg]['idpackage'])
        resultfile = Equo.quickpkg_handler(pkgdata = pkgdata, dirpath = savedir)
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
        Spm = Equo.Spm()
        del Spm
    except Exception as e:
        Equo.entropyTools.print_traceback()
        mytxt = _("Source Package Manager backend not available")
        print_error(darkred(" * ")+red("%s: %s" % (mytxt, e,)))
        return 1

    if savedir:
        if not os.path.isdir(savedir):
            print_error(darkred(" * ")+bold("--savedir")+":"+red(" %s." % (_("directory does not exist"),)))
            return 1
    else:
        savedir = etpConst['packagestmpdir']

    for tbz2 in mytbz2s:

        valid_etp = True
        if action == "deflate":
            valid_etp = Equo.entropyTools.is_entropy_package_file(tbz2)
        if not (os.path.isfile(tbz2) and tbz2.endswith(etpConst['packagesext']) and \
            valid_etp):
                print_error(darkred(" * ")+bold(tbz2)+red(" %s" % (_("is not a valid Entropy package"),)))
                return 1

    if action == "inflate":
        rc = InflateHandler(mytbz2s, savedir)
    elif action == "deflate":
        rc = DeflateHandler(mytbz2s, savedir)
    elif action == "extract":
        rc = ExtractHandler(mytbz2s, savedir)
    else:
        rc = -10
    return rc


def InflateHandler(mytbz2s, savedir):

    branch = Equo.SystemSettings['repositories']['branch']
    print_info(brown(" %s: " % (_("Using branch"),))+bold(branch))

    Spm = Equo.Spm()
    Qa = Equo.QA()

    # analyze files
    for tbz2 in mytbz2s:
        print_info(darkgreen(" * ")+darkred("Inflating: ")+tbz2, back = True)
        etptbz2path = savedir+"/"+os.path.basename(tbz2)
        if os.path.realpath(tbz2) != os.path.realpath(etptbz2path): # can convert a file without copying
            shutil.copy2(tbz2, etptbz2path)
        info_package = bold(os.path.basename(etptbz2path)) + ": "
        Equo.updateProgress(
            red(info_package + _("Extracting package metadata") + " ..."),
            importance = 0,
            type = "info",
            header = brown(" * "),
            back = True
        )
        mydata = Spm.extract_package_metadata(etptbz2path)
        Equo.updateProgress(
            red(info_package + _("Package extraction complete")),
            importance = 0,
            type = "info",
            header = brown(" * "),
            back = True
        )
        # append arbitrary revision
        mydata['revision'] = 9999
        mydata['download'] = mydata['download'][:-5]+"~9999.tbz2"
        # migrate to the proper format
        final_tbz2path = os.path.join(os.path.dirname(etptbz2path), os.path.basename(mydata['download']))
        shutil.move(etptbz2path, final_tbz2path)
        etptbz2path = final_tbz2path
        # create temp database
        dbpath = etpConst['packagestmpdir']+"/"+str(Equo.entropyTools.get_random_number())
        while os.path.isfile(dbpath):
            dbpath = etpConst['packagestmpdir']+"/"+str(Equo.entropyTools.get_random_number())
        # create
        mydbconn = Equo.open_generic_database(dbpath)
        mydbconn.initializeDatabase()
        idpackage, yyy, xxx = mydbconn.addPackage(mydata, revision = mydata['revision'])
        del yyy, xxx
        Qa.test_missing_dependencies([idpackage], mydbconn)
        mydbconn.closeDB()
        Equo.entropyTools.aggregate_edb(tbz2file = etptbz2path, dbfile = dbpath)
        os.remove(dbpath)
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Inflated package"),))+etptbz2path)

    return 0

def DeflateHandler(mytbz2s, savedir):

    # analyze files
    for tbz2 in mytbz2s:
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Deflating"),))+tbz2, back = True)
        mytbz2 = Equo.entropyTools.remove_edb(tbz2, savedir)
        tbz2name = os.path.basename(mytbz2)[:-5] # remove .tbz2
        tbz2name = Equo.entropyTools.remove_tag(tbz2name)+etpConst['packagesext']
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
        out = Equo.entropyTools.extract_edb(tbz2, dbpath = dbpath)
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Extracted Entropy metadata from"),))+out)

    return 0

def smartPackagesHandler(mypackages):

    if (not mypackages):
        print_error(darkred(" * ")+red("%s." % (_("No packages specified"),)))
        return 1

    packages = []
    for opt in mypackages:
        match = Equo.atom_match(opt)
        if match[0] != -1:
            packages.append(match)
        else:
            print_warning(darkred(" * ")+red("%s: " % (_("Cannot find"),))+bold(opt))
    packages = Equo.entropyTools.filter_duplicated_entries(packages)
    if (not packages):
        print_error(darkred(" * ")+red("%s." % (_("No valid packages specified"),)))
        return 2

    # print the list
    print_info(darkgreen(" * ")+red("%s:" % (_("This is the list of the packages that would be merged into a single one"),)))
    pkgInfo = {}
    for pkg in packages:
        dbconn = Equo.open_repository(pkg[1])
        atom = dbconn.retrieveAtom(pkg[0])
        pkgInfo[pkg] = atom
        print_info(brown("\t[")+red("%s:" % (_("from"),))+pkg[1]+brown("]")+" - "+atom)

    rc = Equo.askQuestion(">>   %s" % (_("Would you like to create the packages above ?"),))
    if rc == _("No"):
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
        xdbconn = Equo.open_repository(x[1])
        matchedAtoms[x] = {}
        xatom = xdbconn.retrieveAtom(x[0])
        xdownload = xdbconn.retrieveDownloadURL(x[0])
        xrevision = xdbconn.retrieveRevision(x[0])
        matchedAtoms[x]['atom'] = xatom
        matchedAtoms[x]['download'] = xdownload
        matchedAtoms[x]['revision'] = xrevision
        fetchdata.append(x)
    import text_ui
    # run installPackages with onlyfetch
    rc = text_ui.installPackages(atomsdata = fetchdata, deps = False, onlyfetch = True)
    if rc[1] != 0:
        return rc[0]

    # create unpack dir and unpack all packages
    unpackdir = etpConst['entropyunpackdir']+"/smartpackage-"+str(Equo.entropyTools.get_random_number())
    while os.path.isdir(unpackdir):
        unpackdir = etpConst['entropyunpackdir']+"/smartpackage-"+str(Equo.entropyTools.get_random_number())
    if os.path.isdir(unpackdir):
        shutil.rmtree(unpackdir)
    os.makedirs(unpackdir)
    os.mkdir(unpackdir+"/content")
    os.mkdir(unpackdir+"/db")
    # create master database
    dbfile = unpackdir+"/db/merged.db"
    mergeDbconn = Equo.open_generic_database(dbfile, dbname = "client")
    mergeDbconn.initializeDatabase()
    tmpdbfile = dbfile+"--readingdata"
    for package in matchedPackages:
        print_info(darkgreen("  * ")+brown(matchedAtoms[package]['atom'])+": "+red(_("collecting Entropy metadata")))
        Equo.entropyTools.extract_edb(etpConst['entropyworkdir']+"/"+matchedAtoms[package]['download'], tmpdbfile)
        # read db and add data to mergeDbconn
        mydbconn = Equo.open_generic_database(tmpdbfile)
        idpackages = mydbconn.listAllIdpackages()

        for myidpackage in idpackages:
            data = mydbconn.getPackageData(myidpackage)
            if len(idpackages) == 1:
                # just a plain package that would like to become smart
                xpakdata = Equo.entropyTools.read_xpak(etpConst['entropyworkdir']+"/"+matchedAtoms[package]['download'])
            else:
                xpakdata = mydbconn.retrieveXpakMetadata(myidpackage) # already a smart package
            # add
            idpk, rev, y = mergeDbconn.handlePackage(data, forcedRevision = matchedAtoms[package]['revision']) # get the original rev
            del y
            mergeDbconn.storeXpakMetadata(idpk, xpakdata)
        mydbconn.closeDB()
        os.remove(tmpdbfile)

    # now we have the new database
    mergeDbconn.closeDB()

    # merge packages
    for package in matchedPackages:
        print_info(darkgreen("  * ")+brown(matchedAtoms[package]['atom'])+": "+red("unpacking content"))
        rc = Equo.entropyTools.uncompress_tar_bz2(etpConst['entropyworkdir']+"/"+matchedAtoms[x]['download'], extractPath = unpackdir+"/content")
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
    smart_package_path = etpConst['smartpackagesdir'] + "/" + atoms + \
        etpConst['smartappsext']
    rc = Equo.entropyTools.compress_tar_bz2(smart_package_path, unpackdir+"/content")
    if rc != 0:
        print_error(darkred(" * ")+red("%s." % (_("Compression failed due to unknown reasons"),)))
        return rc
    # adding entropy database
    if not os.path.isfile(smart_package_path):
        print_error(darkred(" * ")+red("%s." % (_("Compressed file does not exist"),)))
        return 1

    Equo.entropyTools.aggregate_edb(smart_package_path, dbfile)
    print_info("\t"+smart_package_path)
    shutil.rmtree(unpackdir, True)
    return 0


def smartappsHandler(mypackages):

    if (not mypackages):
        print_error(darkred(" * ")+red("%s." % (_("No packages specified"),)))
        return 1

    gplusplus = os.system("which g++ &> /dev/null")
    if gplusplus != 0:
        print_error(darkred(" * ")+red("%s." % (_("Cannot find G++ compiler"),)))
        return gplusplus

    packages = []
    for opt in mypackages:
        if opt in packages:
            continue
        match = Equo.atom_match(opt)
        if match[0] != -1:
            packages.append(match)
        else:
            print_warning(darkred(" * ") + red("%s: " %(_("Cannot find"),)) + \
                bold(opt))

    if not packages:
        print_error(darkred(" * ") + \
            red("%s." % (_("No valid packages specified"),)))
        return 2

    # print the list
    print_info(darkgreen(" * ") + \
        red("%s:" % (
            _("This is the list of the packages that would be worked out"),)))

    for pkg in packages:
        dbconn = Equo.open_repository(pkg[1])
        atom = dbconn.retrieveAtom(pkg[0])
        print_info(brown("\t[") + red("%s:" % (_("from"),)) + pkg[1] + \
            red("|SMART") + brown("]") + " - " + atom)

    rc = Equo.askQuestion(">>   %s" % (
        _("Would you like to create the packages above ?"),))
    if rc == _("No"):
        return 0

    rc = smartgenerator(packages)
    if rc != 0:
        print_error(darkred(" * ")+red("%s." % (_("Cannot continue"),)))
    return rc

# tool that generates .tar.bz2 packages with all the binary dependencies included
def smartgenerator(matched_atoms):

    import entropy.tools as entropyTools

    master_atom = matched_atoms[0]
    dbconn = Equo.open_repository(master_atom[1])
    idpackage = master_atom[0]
    atom = dbconn.retrieveAtom(idpackage)
    pkgfilepath = dbconn.retrieveDownloadURL(idpackage)
    pkgcontent = dbconn.retrieveContent(idpackage)
    pkgbranch = dbconn.retrieveBranch(idpackage)
    pkgfilename = os.path.basename(pkgfilepath)
    pkgname = pkgfilename.split(etpConst['packagesext'])[0].replace(":", "_").replace("~", "_")

    fetchdata = matched_atoms
    # run installPackages with onlyfetch
    import text_ui
    rc = text_ui.installPackages(atomsdata = fetchdata, deps = False, onlyfetch = True)
    if rc[1] != 0:
        return rc[0]


    # create the working directory
    pkgtmpdir = os.path.join(etpConst['entropyunpackdir'], pkgname)
    pkg_data_dir = os.path.join(pkgtmpdir, pkgname)
    if os.path.isdir(pkg_data_dir):
        shutil.rmtree(pkg_data_dir)
    os.makedirs(pkg_data_dir)
    main_bin_path = os.path.join(etpConst['packagesbindir'], pkgbranch,
        pkgfilename)
    print_info(darkgreen(" * ") + \
        red("%s " % (_("Unpacking the main package"),)) + \
        bold(str(pkgfilename)))
    entropyTools.uncompress_tar_bz2(main_bin_path, pkg_data_dir) # first unpack

    binary_execs = []
    for item in pkgcontent:
        filepath = pkg_data_dir + item
        if os.access(filepath, os.X_OK):
            if getoutput("file %s" % (filepath,)).find("LSB executable") != -1:
                binary_execs.append(item)

    # now uncompress all the rest
    for dep_idpackage, dep_repo in matched_atoms[1:]:
        mydbconn = Equo.open_repository(dep_repo)
        download = os.path.basename(mydbconn.retrieveDownloadURL(dep_idpackage))
        depbranch = mydbconn.retrieveBranch(dep_idpackage)
        depatom = mydbconn.retrieveAtom(dep_idpackage)
        print_info(darkgreen(" * ") + \
            red("%s " % (_("Unpacking dependency package"),)) + bold(depatom))
        deppath = os.path.join(etpConst['packagesbindir'], depbranch, download)
        entropyTools.uncompress_tar_bz2(deppath, pkg_data_dir) # first unpack

    # now create the bash script for each binary_execs
    os.makedirs(pkg_data_dir+"/wrp")
    wrapper_file = os.path.join(etpConst['installdir'], "services/smartapp_wrapper")
    if not os.path.isfile(wrapper_file):
        wrapper_file = "../services/smartapp_wrapper"

    wrapper_path = pkg_data_dir+"/wrp/wrapper"
    shutil.copy2(wrapper_file, wrapper_path)
    # chmod
    os.chmod(wrapper_path, 0o755)

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

    for item in binary_execs:
        item = item.split("/")[-1]
        item_content = cc_content.replace("--item--",item)
        item_cc = "%s/%s.cc" % (pkg_data_dir,item,)
        f = open(item_cc,"w")
        f.write(item_content)
        f.flush()
        f.close()
        # now compile
        os.system("cd %s/; g++ -Wall %s.cc -o %s.exe" % (pkg_data_dir,item,item,))
        os.remove(item_cc)

    smartpath = "%s/%s-%s%s" % (etpConst['smartappsdir'],pkgname,etpConst['currentarch'],etpConst['smartappsext'],)
    print_info(darkgreen(" * ")+red("%s: " % (_("Compressing smart application"),))+bold(atom))
    print_info("\t%s" % (smartpath,))
    Equo.entropyTools.compress_tar_bz2(smartpath, pkgtmpdir)
    shutil.rmtree(pkgtmpdir,True)

    return 0