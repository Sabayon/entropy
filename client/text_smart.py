# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Package Manager Client}.

"""
import os
import sys
if sys.hexversion >= 0x3000000:
    from subprocess import getoutput
else:
    from commands import getoutput
import shutil

from entropy.const import etpConst, etpUi
from entropy.output import red, darkred, darkgreen, brown, bold, \
    print_info, print_error, print_warning
from entropy.i18n import _
import entropy.dep
import entropy.tools

def smart(options):

    # check if I am root
    if not entropy.tools.is_root():
        mytxt = _("You are not") # you are not root
        print_error(red(mytxt)+" "+bold("root")+red("."))
        return 1

    # Options available for all the packages submodules
    smart_req_savedir = None
    savedir = False
    newopts = []
    for opt in options:
        if opt == "--savedir":
            savedir = True
        elif opt.startswith("--"):
            print_error(red(" %s." % (_("Wrong parameters"),) ))
            return
        else:
            if savedir:
                try:
                    smart_req_savedir = os.path.realpath(opt)
                except OSError:
                    smart_req_savedir = None
                savedir = False
            else:
                newopts.append(opt)
    options = newopts
    if not options:
        return -10

    rc = 0

    from entropy.client.interfaces import Client
    entropy_client = None
    acquired = False
    try:
        entropy_client = Client()
        acquired = entropy.tools.acquire_entropy_locks(entropy_client)
        if not acquired:
            print_error(darkgreen(
                _("Another Entropy is currently running.")))
            return 1

        if options[0] == "package":
            rc = smart_pkg_handler(entropy_client, options[1:])

        elif options[0] == "quickpkg":
            rc = quickpkg_handler(entropy_client,
                options[1:], savedir = smart_req_savedir)

        elif (options[0] == "inflate") or (options[0] == "deflate") or \
            (options[0] == "extract"):
            rc = common_flate(entropy_client,
                options[1:], action = options[0], savedir = smart_req_savedir)
        else:
            rc = -10
    finally:
        if acquired and (entropy_client is not None):
            entropy.tools.release_entropy_locks(entropy_client)
        if entropy_client is not None:
            entropy_client.shutdown()

    return rc


def quickpkg_handler(entropy_client, mypackages, savedir = None):

    if (not mypackages):
        mytxt = _("No packages specified")
        if not etpUi['quiet']:
            print_error(darkred(" * ")+red(mytxt+"."))
        return 1

    if savedir == None:
        savedir = etpConst['packagestmpdir']
        if not os.path.isdir(etpConst['packagestmpdir']):
            os.makedirs(etpConst['packagestmpdir'])
    else:
        if not os.path.isdir(savedir):
            print_error(darkred(" * ")+red("--savedir ") + \
                savedir+red(" %s." % (_("does not exist"),) ))
            return 4

    packages = []
    for opt in mypackages:
        match = entropy_client.installed_repository().atomMatch(opt)
        if match[0] != -1:
            packages.append(match)
        else:
            if not etpUi['quiet']: print_warning(darkred(" * ") + \
                red("%s: " % (_("Cannot find"),))+bold(opt))
    pkgs = []
    for pkg in packages:
        if pkg not in pkgs:
            pkgs.append(pkg)
    packages = pkgs
    if not packages:
        print_error(darkred(" * ")+red("%s." % (_("No valid packages specified"),)))
        return 2

    # print the list
    mytxt = _("This is the list of the packages that would be quickpkg'd")
    if (not etpUi['quiet']) or (etpUi['ask']): print_info(darkgreen(" * ")+red(mytxt+":"))
    pkgInfo = {}
    for pkg in packages:
        atom = entropy_client.installed_repository().retrieveAtom(pkg[0])
        pkgInfo[pkg] = {}
        pkgInfo[pkg]['atom'] = atom
        pkgInfo[pkg]['idpackage'] = pkg[0]
        print_info(brown("\t[")+red("%s:" % (_("from"),))+bold(_("installed"))+brown("]")+" - "+atom)

    if (not etpUi['quiet']) or (etpUi['ask']):
        rc = entropy_client.ask_question(">>   %s" % (_("Would you like to recompose the selected packages ?"),))
        if rc == _("No"):
            return 0

    for pkg in packages:
        if not etpUi['quiet']:
            print_info(brown(" * ")+red("%s: " % (_("Compressing"),))+darkgreen(pkgInfo[pkg]['atom']))
        pkgdata = entropy_client.installed_repository().getPackageData(pkgInfo[pkg]['idpackage'])
        resultfile = entropy_client.generate_package(pkgdata, save_directory = savedir)
        if resultfile == None:
            if not etpUi['quiet']:
                print_error(darkred(" * ") + red("%s: " % (_("Error while creating package for"),)) + \
                    bold(pkgInfo[pkg])+darkred(". %s." % (_("Cannot continue"),)))
            return 3
        if not etpUi['quiet']:
            print_info(darkgreen("  * ")+red("%s: " % (_("Saved in"),))+resultfile)

    return 0

def common_flate(entropy_client, mytbz2s, action, savedir = None):

    if (not mytbz2s):
        print_error(darkred(" * ")+red("%s." % (_("No packages specified"),)))
        return 1

    # test if portage is available
    try:
        Spm = entropy_client.Spm()
        del Spm
    except Exception as e:
        entropy.tools.print_traceback()
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
            valid_etp = entropy.tools.is_entropy_package_file(tbz2)
        if not (os.path.isfile(tbz2) and tbz2.endswith(etpConst['packagesext']) and \
            valid_etp):
                print_error(darkred(" * ")+bold(tbz2)+red(" %s" % (_("is not a valid Entropy package"),)))
                return 1

    if action == "inflate":
        rc = inflate_handler(entropy_client, mytbz2s, savedir)
    elif action == "deflate":
        rc = deflate_handler(mytbz2s, savedir)
    elif action == "extract":
        rc = extract_handler(mytbz2s, savedir)
    else:
        rc = -10
    return rc


def inflate_handler(entropy_client, mytbz2s, savedir):

    branch = entropy_client.Settings()['repositories']['branch']
    print_info(brown(" %s: " % (_("Using branch"),))+bold(branch))

    Spm = entropy_client.Spm()

    # analyze files
    for tbz2 in mytbz2s:
        print_info(darkgreen(" * ")+darkred("Inflating: ")+tbz2, back = True)
        etptbz2path = savedir+os.path.sep+os.path.basename(tbz2)
        if os.path.realpath(tbz2) != os.path.realpath(etptbz2path): # can convert a file without copying
            shutil.copy2(tbz2, etptbz2path)
        info_package = bold(os.path.basename(etptbz2path)) + ": "
        entropy_client.output(
            red(info_package + _("Extracting package metadata") + " ..."),
            importance = 0,
            level = "info",
            header = brown(" * "),
            back = True
        )
        mydata = Spm.extract_package_metadata(etptbz2path)
        entropy_client.output(
            red(info_package + _("Package extraction complete")),
            importance = 0,
            level = "info",
            header = brown(" * "),
            back = True
        )
        # append arbitrary revision
        mydata['revision'] = 9999
        mydata['download'] = mydata['download'][:-len(etpConst['packagesext'])] + \
            "~9999" + etpConst['packagesext']
        # migrate to the proper format
        final_tbz2path = os.path.join(os.path.dirname(etptbz2path), os.path.basename(mydata['download']))
        shutil.move(etptbz2path, final_tbz2path)
        etptbz2path = final_tbz2path
        # create temp database
        dbpath = etpConst['packagestmpdir']+os.path.sep+str(entropy.tools.get_random_number())
        while os.path.isfile(dbpath):
            dbpath = etpConst['packagestmpdir']+os.path.sep+str(entropy.tools.get_random_number())
        # create
        mydbconn = entropy_client.open_generic_repository(dbpath)
        mydbconn.initializeRepository()
        idpackage = mydbconn.addPackage(mydata, revision = mydata['revision'])
        mydbconn.close()
        entropy.tools.aggregate_entropy_metadata(etptbz2path, dbpath)
        os.remove(dbpath)
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Inflated package"),))+etptbz2path)

    return 0

def deflate_handler(mytbz2s, savedir):

    # analyze files
    for tbz2 in mytbz2s:
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Deflating"),))+tbz2, back = True)
        save_path = os.path.join(savedir, os.path.basename(tbz2))
        ext_rc = entropy.tools.remove_entropy_metadata(tbz2, save_path)
        if not ext_rc:
            return 1
        tbz2name = os.path.basename(tbz2)[:-len(etpConst['packagesext'])]
        tbz2name = entropy.dep.remove_tag(tbz2name)+etpConst['packagesext']
        newtbz2 = os.path.dirname(tbz2)+os.path.sep+tbz2name
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Deflated package"),))+newtbz2)

    return 0

def extract_handler(mytbz2s, savedir):

    # analyze files
    for tbz2 in mytbz2s:
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Extracting Entropy metadata from"),))+tbz2, back = True)
        dbpath = savedir+os.path.sep+os.path.basename(tbz2)
        dbpath = dbpath[:-len(etpConst['packagesext'])]+".db"
        if os.path.isfile(dbpath):
            os.remove(dbpath)
        # extract
        dump_rc = entropy.tools.dump_entropy_metadata(tbz2, dbpath)
        if not dump_rc:
            return 1
        print_info(darkgreen(" * ")+darkred("%s: " % (_("Extracted Entropy metadata from"),))+dbpath)

    return 0

def smart_pkg_handler(entropy_client, mypackages):

    if (not mypackages):
        print_error(darkred(" * ")+red("%s." % (_("No packages specified"),)))
        return 1

    packages = []
    for opt in mypackages:
        match = entropy_client.atom_match(opt)
        if match[0] != -1:
            packages.append(match)
        else:
            print_warning(darkred(" * ")+red("%s: " % (_("Cannot find"),))+bold(opt))
    pkgs = []
    for pkg in packages:
        if pkg not in pkgs:
            pkgs.append(pkg)
    packages = pkgs
    if not packages:
        print_error(darkred(" * ")+red("%s." % (_("No valid packages specified"),)))
        return 2

    # print the list
    print_info(darkgreen(" * ")+red("%s:" % (_("This is the list of the packages that would be merged into a single one"),)))
    pkgInfo = {}
    for pkg in packages:
        dbconn = entropy_client.open_repository(pkg[1])
        atom = dbconn.retrieveAtom(pkg[0])
        pkgInfo[pkg] = atom
        print_info(brown("\t[")+red("%s:" % (_("from"),))+pkg[1]+brown("]")+" - "+atom)

    rc = entropy_client.ask_question(">>   %s" % (_("Would you like to create the packages above ?"),))
    if rc == _("No"):
        return 0

    print_info(darkgreen(" * ")+red("%s..." % (_("Creating merged Smart Package"),)))
    rc = smartpackagegenerator(entropy_client, packages)
    if rc != 0:
        print_error(darkred(" * ")+red("%s." % (_("Cannot continue"),)))
        return rc

    return 0


def smartpackagegenerator(entropy_client, matched_pkgs):

    fetchdata = []
    matchedAtoms = {}
    for x in matched_pkgs:
        xdbconn = entropy_client.open_repository(x[1])
        matchedAtoms[x] = {}
        xatom = xdbconn.retrieveAtom(x[0])
        xdownload = xdbconn.retrieveDownloadURL(x[0])
        xrevision = xdbconn.retrieveRevision(x[0])
        matchedAtoms[x]['atom'] = xatom
        matchedAtoms[x]['download'] = xdownload
        matchedAtoms[x]['revision'] = xrevision
        fetchdata.append(x)

    from entropy.spm.plugins.interfaces.portage_plugin import xpaktools
    import text_ui
    # run install_packages with onlyfetch
    rc = text_ui.install_packages(entropy_client, atomsdata = fetchdata,
        deps = False, onlyfetch = True)
    if rc[1] != 0:
        return rc[0]

    # create unpack dir and unpack all packages
    unpackdir = etpConst['entropyunpackdir']+"/smartpackage-"+str(entropy.tools.get_random_number())
    while os.path.isdir(unpackdir):
        unpackdir = etpConst['entropyunpackdir']+"/smartpackage-"+str(entropy.tools.get_random_number())
    if os.path.isdir(unpackdir):
        shutil.rmtree(unpackdir)
    os.makedirs(unpackdir)
    os.mkdir(unpackdir+"/content")
    os.mkdir(unpackdir+"/db")
    # create master database
    dbfile = unpackdir+"/db/merged.db"
    mergeDbconn = entropy_client.open_generic_repository(dbfile, name = "client")
    mergeDbconn.initializeRepository()
    tmpdbfile = dbfile+"--readingdata"
    for package in matched_pkgs:
        print_info(darkgreen("  * ")+brown(matchedAtoms[package]['atom'])+": "+red(_("collecting Entropy metadata")))
        entropy.tools.dump_entropy_metadata(
            etpConst['entropypackagesworkdir'] + os.path.sep + \
                matchedAtoms[package]['download'], tmpdbfile)
        # read db and add data to mergeDbconn
        mydbconn = entropy_client.open_generic_repository(tmpdbfile)
        idpackages = mydbconn.listAllPackageIds()

        for myidpackage in idpackages:
            data = mydbconn.getPackageData(myidpackage)
            if len(idpackages) == 1:
                # just a plain package that would like to become smart
                xpakdata = xpaktools.read_xpak(
                    etpConst['entropypackagesworkdir'] + \
                        os.path.sep + matchedAtoms[package]['download'])
            else:
                xpakdata = mydbconn.retrieveSpmMetadata(myidpackage) # already a smart package
            # add
            idpk = mergeDbconn.handlePackage(data, forcedRevision = matchedAtoms[package]['revision']) # get the original rev
            if xpakdata is not None:
                mergeDbconn.storeSpmMetadata(idpk, xpakdata)
        mydbconn.close()
        os.remove(tmpdbfile)

    # now we have the new database
    mergeDbconn.close()

    # merge packages
    for package in matched_pkgs:
        print_info(darkgreen("  * ")+brown(matchedAtoms[package]['atom'])+": "+red("unpacking content"))
        rc = entropy.tools.uncompress_tarball(
            etpConst['entropypackagesworkdir'] + \
                os.path.sep+matchedAtoms[x]['download'],
                extract_path = os.path.join(unpackdir, "content"))
        if rc != 0:
            print_error(darkred(" * ")+red("%s." % (_("Unpack failed due to unknown reasons"),)))
            return rc

    if not os.path.isdir(etpConst['smartpackagesdir']):
        os.makedirs(etpConst['smartpackagesdir'])
    print_info(darkgreen("  * ")+red(_("Compressing smart package")))
    atoms = []
    for x in matchedAtoms:
        atoms.append(matchedAtoms[x]['atom'].split(os.path.sep)[1])
    atoms = '+'.join(atoms)
    smart_package_path = etpConst['smartpackagesdir'] + os.path.sep + atoms + \
        ".app"
    rc = entropy.tools.compress_tar_bz2(smart_package_path, unpackdir+"/content")
    if rc != 0:
        print_error(darkred(" * ")+red("%s." % (_("Compression failed due to unknown reasons"),)))
        return rc
    # adding entropy database
    if not os.path.isfile(smart_package_path):
        print_error(darkred(" * ")+red("%s." % (_("Compressed file does not exist"),)))
        return 1

    entropy.tools.aggregate_entropy_metadata(smart_package_path, dbfile)
    print_info("\t"+smart_package_path)
    shutil.rmtree(unpackdir, True)
    return 0

