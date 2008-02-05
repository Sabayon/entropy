#!/usr/bin/python
'''
    # DESCRIPTION:
    # Entropy Portage Interface

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

############
# Portage initialization
#####################################################################################

from entropyConstants import *
import entropyTools
import portage

############
# Functions and Classes
#####################################################################################

def getThirdPartyMirrors(mirrorname):
    try:
        return portage.thirdpartymirrors[mirrorname]
    except KeyError:
        return []

def getPortageEnv(var):
    return portage.settings[var]

# Packages in system (in the Portage language -> emerge system, remember?)
def getPackagesInSystem():
    system = portage.settings.packages
    sysoutput = []
    for x in system:
        y = getInstalledAtoms(x)
        if (y != None):
            for z in y:
                sysoutput.append(z)
    sysoutput.append("sys-kernel/linux-sabayon") # our kernel
    sysoutput.append("dev-db/sqlite") # our interface
    sysoutput.append("dev-python/pysqlite") # our python interface to our interface (lol)
    sysoutput.append("virtual/cron") # our cron service
    sysoutput.append("app-admin/equo") # our package manager (client)
    sysoutput.append("sys-apps/entropy") # our package manager (server+client)
    return sysoutput

def getConfigProtectAndMask():
    import commands
    config_protect = portage.settings['CONFIG_PROTECT']
    config_protect = config_protect.split()
    config_protect_mask = portage.settings['CONFIG_PROTECT_MASK']
    config_protect_mask = config_protect_mask.split()
    # explode
    protect = []
    for x in config_protect:
        if x.startswith("$"): #FIXME: small hack
            x = commands.getoutput("echo "+x).split("\n")[0]
        protect.append(x)
    mask = []
    for x in config_protect_mask:
        if x.startswith("$"): #FIXME: small hack
            x = commands.getoutput("echo "+x).split("\n")[0]
        mask.append(x)
    return ' '.join(protect),' '.join(mask)

# resolve atoms automagically (best, not current!)
# sys-libs/application --> sys-libs/application-1.2.3-r1
def getBestAtom(atom, match = "bestmatch-visible"):
    try:
        rc = portage.portdb.xmatch(match,str(atom))
        return rc
    except ValueError:
        return "!!conflicts"

# same as above but includes masked ebuilds
def getBestMaskedAtom(atom):
    atoms = portage.portdb.xmatch("match-all",str(atom))
    # find the best
    from portage_versions import best
    rc = best(atoms)
    return rc

# should be only used when a pkgcat/pkgname <-- is not specified (example: db, amarok, AND NOT media-sound/amarok)
def getAtomCategory(atom):
    try:
        rc = portage.portdb.xmatch("match-all",str(atom))[0].split("/")[0]
        return rc
    except:
        return None

# please always force =pkgcat/pkgname-ver if possible
def getInstalledAtom(atom):
    mypath = etpConst['systemroot']+"/"
    try:
        cached = portageRoots.get(mypath)
        if cached == None:
            mytree = portage.vartree(root=mypath)
            portageRoots[mypath] = mytree
        else:
            mytree = cached
    except NameError:
        mytree = portage.vartree(root=mypath)
    rc = mytree.dep_match(str(atom))
    if (rc != []):
        if (len(rc) == 1):
            return rc[0]
        else:
            return rc[len(rc)-1]
    else:
        return None

def getPackageSlot(atom):
    mypath = etpConst['systemroot']+"/"
    try:
        cached = portageRoots.get(mypath)
        if cached == None:
            mytree = portage.vartree(root=mypath)
            portageRoots[mypath] = mytree
        else:
            mytree = cached
    except NameError:
        mytree = portage.vartree(root=mypath)
    if atom.startswith("="):
        atom = atom[1:]
    rc = mytree.getslot(atom)
    if rc != "":
        return rc
    else:
        return None

def getInstalledAtoms(atom):
    mypath = etpConst['systemroot']+"/"
    try:
        cached = portageRoots.get(mypath)
        if cached == None:
            mytree = portage.vartree(root=mypath)
            portageRoots[mypath] = mytree
        else:
            mytree = cached
    except NameError:
        mytree = portage.vartree(root=mypath)
    rc = mytree.dep_match(str(atom))
    if (rc != []):
        return rc
    else:
        return None

def parseElogFile(atom):

    import commands

    if atom.startswith("="):
        atom = atom[1:]
    if atom.startswith(">"):
        atom = atom[1:]
    if atom.startswith("<"):
        atom = atom[1:]
    if (atom.find("/") != -1):
        pkgcat = atom.split("/")[0]
        pkgnamever = atom.split("/")[1]+"*.log"
    else:
        pkgcat = "*"
        pkgnamever = atom+"*.log"
    elogfile = pkgcat+":"+pkgnamever
    reallogfile = commands.getoutput("find "+etpConst['logdir']+"/elog/ -name '"+elogfile+"'").split("\n")[0].strip()
    if os.path.isfile(reallogfile):
        # FIXME: improve this part
        logline = False
        logoutput = []
        f = open(reallogfile,"r")
        reallog = f.readlines()
        f.close()
        for line in reallog:
            if line.startswith("INFO: postinst") or line.startswith("LOG: postinst"):
                logline = True
                continue
                # disable all the others
            elif line.startswith("INFO:") or line.startswith("LOG:"):
                logline = False
                continue
            if (logline) and (line.strip() != ""):
                # trap !
                logoutput.append(line.strip())
        return logoutput
    else:
        return []

# create a .tbz2 file in the specified path
def quickpkg(atom,dirpath):

    # getting package info
    pkgname = atom.split("/")[1]
    pkgcat = atom.split("/")[0]
    #pkgfile = pkgname+".tbz2"
    if not os.path.isdir(dirpath):
        os.makedirs(dirpath)
    dirpath += "/"+pkgname+".tbz2"
    dbdir = getPortageAppDbPath()+"/"+pkgcat+"/"+pkgname+"/"

    import tarfile
    import stat
    trees = portage.db["/"]
    vartree = trees["vartree"]
    dblnk = portage.dblink(pkgcat, pkgname, "/", vartree.settings, treetype="vartree", vartree=vartree)
    dblnk.lockdb()
    tar = tarfile.open(dirpath,"w:bz2")

    contents = dblnk.getcontents()
    id_strings = {}
    paths = contents.keys()
    paths.sort()

    for path in paths:
        try:
            exist = os.lstat(path)
        except OSError:
            continue # skip file
        ftype = contents[path][0]
        lpath = path
        arcname = path[1:]
        if 'dir' == ftype and \
            not stat.S_ISDIR(exist.st_mode) and \
            os.path.isdir(lpath):
            lpath = os.path.realpath(lpath)
        tarinfo = tar.gettarinfo(lpath, arcname)
        tarinfo.uname = id_strings.setdefault(tarinfo.uid, str(tarinfo.uid))
        tarinfo.gname = id_strings.setdefault(tarinfo.gid, str(tarinfo.gid))

        if stat.S_ISREG(exist.st_mode):
            tarinfo.type = tarfile.REGTYPE
            f = open(path)
            try:
                tar.addfile(tarinfo, f)
            finally:
                f.close()
        else:
            tar.addfile(tarinfo)

    tar.close()

    # appending xpak informations
    import etpXpak
    tbz2 = etpXpak.tbz2(dirpath)
    tbz2.recompose(dbdir)

    dblnk.unlockdb()

    if os.path.isfile(dirpath):
        return dirpath
    else:
        return False

def getUSEFlags():
    return portage.settings['USE']

def getUSEForce():
    return portage.settings.useforce

def getUSEMask():
    return portage.settings.usemask

def getMAKEOPTS():
    return portage.settings['MAKEOPTS']

def getCFLAGS():
    return portage.settings['CFLAGS']

def getLDFLAGS():
    return portage.settings['LDFLAGS']

# you must provide a complete atom
def getPackageIUSE(atom):
    return getPackageVar(atom,"IUSE")

def getPackageVar(atom,var):
    if atom.startswith("="):
        atom = atom[1:]
    # can't check - return error
    if (atom.find("/") == -1):
        return 1
    return portage.portdb.aux_get(atom,[var])[0]

class paren_normalize(list):
    """Take a dependency structure as returned by paren_reduce or use_reduce
    and generate an equivalent structure that has no redundant lists."""
    def __init__(self, src):
        list.__init__(self)
        self._zap_parens(src, self)

    def _zap_parens(self, src, dest, disjunction=False):
        if not src:
            return dest
        i = iter(src)
        for x in i:
            if isinstance(x, basestring):
                if x == '||':
                    x = self._zap_parens(i.next(), [], disjunction=True)
                    if len(x) == 1:
                        dest.append(x[0])
                    else:
                        dest.append("||")
                        dest.append(x)
                elif x.endswith("?"):
                    dest.append(x)
                    dest.append(self._zap_parens(i.next(), []))
                else:
                    dest.append(x)
            else:
                if disjunction:
                    x = self._zap_parens(x, [])
                    if len(x) == 1:
                        dest.append(x[0])
                    else:
                        dest.append(x)
                else:
                    self._zap_parens(x, dest)
        return dest

def calculate_dependencies(my_iuse, my_use, my_license, my_depend, my_rdepend, my_pdepend, my_provide, my_src_uri):
    metadata = {}
    metadata['USE'] = my_use
    metadata['IUSE'] = my_iuse
    metadata['LICENSE'] = my_license
    metadata['DEPEND'] = my_depend
    metadata['PDEPEND'] = my_pdepend
    metadata['RDEPEND'] = my_rdepend
    metadata['PROVIDE'] = my_provide
    metadata['SRC_URI'] = my_src_uri
    use = metadata['USE'].split()
    raw_use = use
    iuse = set(metadata['IUSE'].split())
    use = [f for f in use if f in iuse]
    use.sort()
    metadata['USE'] = " ".join(use)
    # FIXME: there's some portage trunk stuff
    try:
        from portage_dep import paren_reduce, use_reduce, paren_enclose
        p_normalize = paren_normalize
    except ImportError:
        from portage.dep import paren_reduce, use_reduce, paren_normalize as p_normalize, paren_enclose
    for k in "LICENSE", "RDEPEND", "DEPEND", "PDEPEND", "PROVIDE", "SRC_URI":
        try:
            deps = paren_reduce(metadata[k])
            deps = use_reduce(deps, uselist=raw_use)
            deps = p_normalize(deps)
            if k == "LICENSE":
                deps = paren_license_choose(deps)
            else:
                deps = paren_choose(deps)
            deps = ' '.join(deps)
        except exceptionTools.InvalidDependString, e:
            print_error("%s: %s\n" % (k, str(e)))
            raise
        metadata[k] = deps
    return metadata

def paren_choose(dep_list):

    newlist = []
    do_skip = False
    for idx in range(len(dep_list)):

        if do_skip:
            do_skip = False
            continue

        item = dep_list[idx]
        if item == "||":
            item = dep_or_select(dep_list[idx+1]) # must be a list
            if item == None:
                # no matches, transform to string and append, so reagent will fail
                newlist.append(str(dep_list[idx+1]))
            else:
                newlist.append(item)
            do_skip = True
        else:
            newlist.append(x)

    return newlist

def dep_or_select(or_list):
    do_skip = False
    for idx in range(len(or_list)):
        if do_skip:
            do_skip = False
            continue
        x = or_list[idx]
        if x == "||":
            x = dep_or_select(or_list[idx+1])
            do_skip = True
        match = getInstalledAtom(x)
        if match != None:
            return x

def paren_license_choose(dep_list):

    newlist = []
    for item in dep_list:

        if isinstance(item, list):
            # match the first
            for x in item:
                newlist.append(x)
        else:
            if item not in ["||"]:
                newlist.append(item)
    return newlist

##
## HIGHLY DEPRECATED, USE calculate_dependencies
##
def synthetizeRoughDependencies(roughDependencies, useflags = None):
    if useflags is None:
        useflags = getUSEFlags()
    # returns dependencies, conflicts

    useMatch = False
    openParenthesis = 0
    openParenthesisFromOr = 0
    openOr = False
    useFlagQuestion = False
    dependencies = ""
    conflicts = ""
    useflags = useflags.split()

    length = len(roughDependencies)
    atomcount = -1

    while atomcount < length:

        atomcount += 1
        try:
            atom = roughDependencies[atomcount]
        except:
            break

        if atom.startswith("("):
            if (openOr):
                openParenthesisFromOr += 1
            openParenthesis += 1
            curparenthesis = openParenthesis # 2
            if (useFlagQuestion) and (not useMatch):
                skip = True
                while (skip):
                    atomcount += 1
                    atom = roughDependencies[atomcount]
                    if atom.startswith("("):
                        curparenthesis += 1
                    elif atom.startswith(")"):
                        if (curparenthesis == openParenthesis):
                            skip = False
                        curparenthesis -= 1
                useFlagQuestion = False

        elif atom.endswith("?"):

            #if (useFlagQuestion) and (not useMatch): # if we're already in a question and the question is not accepted, skip the cycle
            #    continue
            # we need to see if that useflag is enabled
            useFlag = atom.split("?")[0]
            useFlagQuestion = True # V
            #openParenthesisFromLastUseFlagQuestion = 0
            if useFlag.startswith("!"):
                checkFlag = useFlag[1:]
                try:
                    useflags.index(checkFlag)
                    useMatch = False
                except:
                    useMatch = True
            else:
                try:
                    useflags.index(useFlag)
                    useMatch = True # V
                except:
                    useMatch = False

        elif atom.startswith(")"):

            openParenthesis -= 1
            if (openParenthesis == 0):
                useFlagQuestion = False
                useMatch = False

            if (openOr):
                # remove last "_or_" from dependencies
                if (openParenthesisFromOr == 1):
                    openOr = False
                    if dependencies.endswith(dbOR):
                        dependencies = dependencies[:len(dependencies)-len(dbOR)]
                        dependencies += " "
                elif (openParenthesisFromOr == 2):
                    if dependencies.endswith("|and|"):
                        dependencies = dependencies[:len(dependencies)-len("|and|")]
                        dependencies += dbOR
                openParenthesisFromOr -= 1

        elif atom.startswith("||"):
            openOr = True # V

        elif (atom.find("/") != -1) and (not atom.startswith("!")) and (not atom.endswith("?")):
            # it's a package name <pkgcat>/<pkgname>-???
            if (useFlagQuestion == useMatch):
                # check if there's an OR
                if (openOr):
                    dependencies += atom
                    # check if the or is fucked up
                    if openParenthesisFromOr > 1:
                        dependencies += "|and|" # !!
                    else:
                        dependencies += dbOR
                else:
                    dependencies += atom
                    dependencies += " "

        elif atom.startswith("!") and (not atom.endswith("?")):
            if ((useFlagQuestion) and (useMatch)) or ((not useFlagQuestion) and (not useMatch)):
                conflicts += atom
                if (openOr):
                    conflicts += dbOR
                else:
                    conflicts += " "


    # format properly
    tmpConflicts = list(set(conflicts.split()))
    conflicts = ''
    tmpData = []
    for i in tmpConflicts:
        i = i[1:] # remove "!"
        tmpData.append(i)
    conflicts = ' '.join(tmpData)

    tmpData = []
    tmpDeps = list(set(dependencies.split()))
    dependencies = ''
    for i in tmpDeps:
	tmpData.append(i)

    # now filter |or| and |and|
    _tmpData = []
    for dep in tmpData:

        if dep.find("|or|") != -1:
            deps = dep.split("|or|")
            # find the best
            results = []
            for x in deps:
                if x.find("|and|") != -1:
                    anddeps = x.split("|and|")
                    results.append(anddeps)
                else:
                    if x:
                        results.append([x])

            # now parse results
            for result in results:
                outdeps = result[:]
                for y in result:
                    yresult = getInstalledAtoms(y)
                    if (yresult != None):
                        outdeps.remove(y)
                if (not outdeps):
                    # find it
                    for y in result:
                        _tmpData.append(y)
                    break

        else:
            _tmpData.append(dep)

    dependencies = ' '.join(_tmpData)

    return dependencies, conflicts

def getPortageAppDbPath():
    import portage_const
    rc = etpConst['systemroot']+"/"+portage_const.VDB_PATH
    if (not rc.endswith("/")):
        return rc+"/"
    return rc

def getAvailablePackages(categories = [], filter_reinstalls = True):
    import portage_const
    mypath = etpConst['systemroot']+"/"
    mysettings = portage.config(config_root="/", target_root=mypath, config_incrementals=portage_const.INCREMENTALS)
    portdb = portage.portdbapi(mysettings["PORTDIR"], mysettings = mysettings)
    cps = portdb.cp_all()
    visibles = set()
    for cp in cps:
        if categories and cp.split("/")[0] not in categories:
            continue
        # get slots
        slots = set()
        atoms = getBestAtom(cp, "match-visible")
        for atom in atoms:
            slots.add(portdb.aux_get(atom, ["SLOT"])[0])
        for slot in slots:
            visibles.add(cp+":"+slot)
    del cps

    # now match visibles
    available = set()
    for visible in visibles:
        match = getBestAtom(visible)
        if filter_reinstalls:
            installed = getInstalledAtom(visible)
            # if not installed, installed == None
            if installed != match:
                available.add(match)
        else:
            available.add(match)
    del visibles

    return available


# Collect installed packages
def getInstalledPackages(dbdir = None):
    if not dbdir:
        appDbDir = getPortageAppDbPath()
    else:
        appDbDir = dbdir
    dbDirs = os.listdir(appDbDir)
    installedAtoms = []
    for pkgsdir in dbDirs:
        if os.path.isdir(appDbDir+pkgsdir):
            pkgdir = os.listdir(appDbDir+pkgsdir)
            for pdir in pkgdir:
                pkgcat = pkgsdir.split("/")[len(pkgsdir.split("/"))-1]
                pkgatom = pkgcat+"/"+pdir
                if pkgatom.find("-MERGING-") == -1:
                    installedAtoms.append(pkgatom)
    return installedAtoms, len(installedAtoms)

def getInstalledPackagesCounters():
    appDbDir = getPortageAppDbPath()
    dbDirs = os.listdir(appDbDir)
    installedAtoms = set()
    for pkgsdir in dbDirs:
        if not os.path.isdir(appDbDir+pkgsdir):
            continue
        pkgdir = os.listdir(appDbDir+pkgsdir)
        for pdir in pkgdir:
            pkgcat = pkgsdir.split("/")[len(pkgsdir.split("/"))-1]
            pkgatom = pkgcat+"/"+pdir
            if pkgatom.find("-MERGING-") == -1:
                # get counter
                try:
                    f = open(appDbDir+pkgsdir+"/"+pdir+"/"+dbCOUNTER,"r")
                except IOError:
                    continue
                counter = f.readline().strip()
                f.close()
                installedAtoms.add((pkgatom,int(counter)))
    return installedAtoms, len(installedAtoms)

def refillCounter():
    appDbDir = getPortageAppDbPath()
    counters = set()
    for catdir in os.listdir(appDbDir):
        catdir = appDbDir+catdir
        if not os.path.isdir(catdir):
            continue
        for pkgdir in os.listdir(catdir):
            pkgdir = catdir+"/"+pkgdir
            if not os.path.isdir(pkgdir):
                continue
            counterfile = pkgdir+"/"+dbCOUNTER
            if not os.path.isfile(pkgdir+"/"+dbCOUNTER):
                continue
            try:
                f = open(counterfile,"r")
                counter = int(f.readline().strip())
                counters.add(counter)
                f.close()
            except:
                continue
    newcounter = max(counters)
    if not os.path.isdir(os.path.dirname(etpConst['edbcounter'])):
        os.makedirs(os.path.dirname(etpConst['edbcounter']))
    try:
        f = open(etpConst['edbcounter'],"w")
    except IOError, e:
        if e[0] == 21:
            import shutil
            shutil.rmtree(etpConst['edbcounter'],True)
            try:
                os.rmdir(etpConst['edbcounter'])
            except:
                pass
        f = open(etpConst['edbcounter'],"w")
    f.write(str(newcounter))
    f.flush()
    f.close()
    del counters
    return newcounter

def portage_doebuild(myebuild, mydo, tree, cpv, portage_tmpdir = None):
    import portage_const
    # myebuild = path/to/ebuild.ebuild with a valid unpacked xpak metadata
    # tree = "bintree"
    # tree = "bintree"
    # cpv = atom
    '''
        # This is a demonstration that Sabayon team love Gentoo so much
        [01:46] <zmedico> if you want something to stay in mysettings
        [01:46] <zmedico> do mysettings.backup_changes("CFLAGS") for example
        [01:46] <zmedico> otherwise your change can get lost inside doebuild()
        [01:47] <zmedico> because it calls mysettings.reset()
        # ^^^ this is DA MAN!
    '''
    # mydbapi = portage.fakedbapi(settings=portage.settings)
    # vartree = portage.vartree(root=myroot)

    oldsystderr = sys.stderr
    f = open("/dev/null","w")
    sys.stderr = f

    ### SETUP ENVIRONMENT
    # if mute, supress portage output
    if etpUi['mute']:
        oldsysstdout = sys.stdout
        sys.stdout = f

    # XXX? always accept license if etpUi['mute']
    if etpUi['mute']:
        if os.path.isdir("/usr/portage/licenses"):
            os.environ["ACCEPT_LICENSE"] = str(' '.join(os.listdir("/usr/portage/licenses")))
    os.environ["SKIP_EQUO_SYNC"] = "1"
    os.environ["CD_ROOT"] = "/tmp" # workaround for scripts asking for user intervention

    # load metadata
    myebuilddir = os.path.dirname(myebuild)
    keys = portage.auxdbkeys
    metadata = {}

    for key in keys:
        mykeypath = os.path.join(myebuilddir,key)
        if os.path.isfile(mykeypath) and os.access(mykeypath,os.R_OK):
            f = open(mykeypath,"r")
            metadata[key] = f.readline().strip()
            f.close()

    ### END SETUP ENVIRONMENT

    mypath = etpConst['systemroot']+"/"
    # find config
    if portageConfigs.has_key(mypath):
        mysettings = portageConfigs.get(mypath)
    else:
        mysettings = portage.config(config_root="/", target_root=mypath, config_incrementals=portage_const.INCREMENTALS)
        portageConfigs[mypath] = mysettings

    try: # this is a >portage-2.1.4_rc11 feature
        mysettings._environ_whitelist = set(mysettings._environ_whitelist)
        # put our vars into whitelist
        mysettings._environ_whitelist.add("SKIP_EQUO_SYNC")
        mysettings._environ_whitelist.add("ACCEPT_LICENSE")
        mysettings._environ_whitelist.add("CD_ROOT")
        mysettings._environ_whitelist = frozenset(mysettings._environ_whitelist)
    except:
        pass

    cpv = str(cpv)
    mysettings.setcpv(cpv)
    portage_tmpdir_created = False # for pkg_postrm, pkg_prerm
    if portage_tmpdir:
        if not os.path.isdir(portage_tmpdir):
            os.makedirs(portage_tmpdir)
            portage_tmpdir_created = True
        mysettings['PORTAGE_TMPDIR'] = str(portage_tmpdir)
        mysettings.backup_changes("PORTAGE_TMPDIR")

    mydbapi = portage.fakedbapi(settings=mysettings)
    mydbapi.cpv_inject(cpv, metadata = metadata)

    # cached vartree class
    if portageRoots.has_key(mypath):
        vartree = portageRoots.get(mypath)
    else:
        vartree = portage.vartree(root=mypath)
        portageRoots[mypath] = vartree

    rc = portage.doebuild(myebuild = str(myebuild), mydo = str(mydo), myroot = mypath, tree = tree, mysettings = mysettings, mydbapi = mydbapi, vartree = vartree, use_cache = 0) ### FIXME: add support for cache_overlay
    # avoid python/portage memleaks
    import gc; gc.collect()

    # if mute, restore old stdout/stderr
    if etpUi['mute']:
        sys.stdout = oldsysstdout

    sys.stderr = oldsystderr
    f.close()

    if portage_tmpdir_created:
        import shutil
        shutil.rmtree(portage_tmpdir,True)

    del mydbapi
    del metadata
    del keys
    return rc