# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayonlinux.org>
    @contact: lxnay@sabayonlinux.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Source Package Manager "Portage" Plugin}.

"""
from __future__ import with_statement
import os
import sys
import shutil
import tempfile
from entropy.const import etpConst, etpUi
from entropy.exceptions import FileNotFound, SPMError, InvalidDependString, \
    InvalidData
from entropy.output import darkred, darkgreen, brown, darkblue, purple, red, \
    bold
from entropy.i18n import _
from entropy.core.settings.base import SystemSettings
from entropy.misc import LogFile
from entropy.spm.plugins.skel import SpmPlugin

class PortagePackageGroups(dict):
    """
    Entropy Package categories group representation
    """
    def __init__(self):
        dict.__init__(self)

        data = {
            'office': {
                'name': _("Office"),
                'description': _("Applications used in office environments"),
                'categories': [u'app-office', u'app-pda', u'app-mobilephone',
                    u'app-cdr', u'app-antivirus', u'app-laptop', u'mail-',
                ],
            },
            'development': {
                'name': _("Development"),
                'description': _("Applications or system libraries"),
                'categories': [u'dev-', u'sys-devel'],
            },
            'system': {
                'name': _("System"),
                'description': _("System applications or libraries"),
                'categories': [u'sys-'],
            },
            'games': {
                'name': _("Games"),
                'description': _("Games, enjoy your spare time"),
                'categories': [u'games-'],
            },
            'gnome': {
                'name': _("GNOME Desktop"),
                'description': \
                    _("Applications and libraries for the GNOME Desktop"),
                'categories': [u'gnome-'],
            },
            'kde': {
                'name': _("KDE Desktop"),
                'description': \
                    _("Applications and libraries for the KDE Desktop"),
                'categories': [u'kde-'],
            },
            'xfce': {
                'name': _("XFCE Desktop"),
                'description': \
                    _("Applications and libraries for the XFCE Desktop"),
                'categories': [u'xfce-'],
            },
            'lxde': {
                'name': _("LXDE Desktop"),
                'description': \
                    _("Applications and libraries for the LXDE Desktop"),
                'categories': [u'lxde-'],
            },
            'multimedia': {
                'name': _("Multimedia"),
                'description': \
                    _("Applications and libraries for Multimedia"),
                'categories': [u'media-'],
            },
            'networking': {
                'name': _("Networking"),
                'description': \
                    _("Applications and libraries for Networking"),
                'categories': [u'net-', u'www-'],
            },
            'science': {
                'name': _("Science"),
                'description': \
                    _("Scientific applications and libraries"),
                'categories': [u'sci-'],
            },
            'x11': {
                'name': _("X11"),
                'description': \
                    _("Applications and libraries for X11"),
                'categories': [u'x11-'],
            },
        }
        self.update(data)

class PortagePlugin(SpmPlugin):

    builtin_pkg_sets = [
        "system","world","installed","module-rebuild",
        "security","preserved-rebuild","live-rebuild",
        "downgrade","unavailable"
    ]

    package_phases_map = {
        'setup': 'setup',
        'preinstall': 'preinst',
        'postinstall': 'postinst',
        'preremove': 'prerm',
        'postremove': 'postrm',
    }

    PLUGIN_API_VERSION = 0

    SUPPORTED_MATCH_TYPES = [
        "bestmatch-visible", "cp-list", "list-visible", "match-all",
        "match-visible", "minimum-all", "minimum-visible"
    ]

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

    import entropy.tools as entropyTools
    def init_singleton(self, OutputInterface):

        mytxt = _("OutputInterface does not have an updateProgress method")
        if not hasattr(OutputInterface,'updateProgress'):
            raise AttributeError(mytxt)
        elif not callable(OutputInterface.updateProgress):
            raise AttributeError(mytxt)

        # interface only needed OutputInterface functions
        self.updateProgress = OutputInterface.updateProgress
        self.askQuestion = OutputInterface.askQuestion
        sys.path.append("/usr/lib/gentoolkit/pym")

        # importing portage stuff
        import portage
        self.portage = portage
        self.EAPI = 1
        try:
            import portage.const as portage_const
        except ImportError:
            import portage_const
        if hasattr(portage_const, "EAPI"):
            self.EAPI = portage_const.EAPI
        self.portage_const = portage_const

        from portage.versions import best
        self._portage_best = best

        try:
            import portage.util as portage_util
        except ImportError:
            import portage_util
        self.portage_util = portage_util

        try:
            import portage.sets as portage_sets
            self.portage_sets = portage_sets
        except ImportError:
            self.portage_sets = None

        try:
            import glsa
            self.glsa = glsa
        except ImportError:
            self.glsa = None

        if hasattr(self.portage,'exception'):
            self.portage_exception = self.portage.exception
        else: # portage <2.2 workaround
            self.portage_exception = Exception

    @staticmethod
    def get_package_groups():
        """
        Return package groups available metadata (Spm categories are grouped
        into macro categories called "groups").
        """
        return PortagePackageGroups()

    def package_metadata_keys(self):
        """
        Reimplemented from SpmPlugin class.
        """
        # return what's inside vartree because it's more complete
        dbapi = self._get_portage_vartree().dbapi
        if hasattr(dbapi, '_aux_cache_keys'):
            return list(dbapi._aux_cache_keys)

        sys.stderr.write("PortagePlugin: missing vardb._aux_cache_keys !\n")
        return ["CHOST", "COUNTER", "DEPEND", "DESCRIPTION",
            "EAPI", "HOMEPAGE", "IUSE", "KEYWORDS",
            "LICENSE", "PDEPEND", "PROPERTIES", "PROVIDE", "RDEPEND",
            "repository", "RESTRICT" , "SLOT", "USE"
        ]

    def get_cache_directory(self, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if root is None:
            root = etpConst['systemroot'] + os.path.sep
        cache_path = self.portage_const.CACHE_PATH.lstrip(os.path.sep)
        return os.path.join(root, cache_path)

    def get_package_metadata(self, package, key):
        """
        Reimplemented from SpmPlugin class.
        """
        return self.portage.portdb.aux_get(package, [key])[0]

    def get_package_changelog(self, package):
        """
        Reimplemented from SpmPlugin class.
        """
        ebuild_path = self.get_package_build_script_path(package)
        if isinstance(ebuild_path, basestring):

            clog_path = os.path.join(os.path.dirname(ebuild_path), "ChangeLog")
            if os.access(clog_path, os.R_OK | os.F_OK):
                with open(clog_path, "r") as clog_f:
                    return clog_f.read()

    def get_package_build_script_path(self, package):
        """
        Reimplemented from SpmPlugin class.
        """
        return self.portage.portdb.findname(package)

    def get_installed_package_build_script_path(self, package, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        return os.path.join(self._get_vdb_path(root = root), package,
            package.split("/")[-1] + etpConst['spm']['source_build_ext'])

    def get_installed_package_metadata(self, package, key, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if root is None:
            root = etpConst['systemroot'] + os.path.sep
        vartree = self._get_portage_vartree(root = root)
        return vartree.dbapi.aux_get(package, [key])[0]

    def get_system_packages(self):
        """
        Reimplemented from SpmPlugin class.
        """
        system = []
        for package in self.portage.settings.packages:
            pkgs = self.match_installed_package(package, match_all = True)
            system.extend(pkgs)
        system.extend(etpConst['spm']['system_packages'])
        return system

    def get_package_categories(self):
        """
        Reimplemented from SpmPlugin class.
        """
        return self._get_portage_config(os.path.sep, os.path.sep).categories

    def get_package_category_description_metadata(self, category):
        """
        Reimplemented from SpmPlugin class.
        """
        from xml.dom import minidom
        data = {}
        portdir = self.portage.settings['PORTDIR']
        myfile = os.path.join(portdir,category,"metadata.xml")
        if os.access(myfile,os.R_OK) and os.path.isfile(myfile):
            doc = minidom.parse(myfile)
            longdescs = doc.getElementsByTagName("longdescription")
            for longdesc in longdescs:
                data[longdesc.getAttribute("lang").strip()] = \
                    ' '.join([x.strip() for x in \
                        longdesc.firstChild.data.strip().split("\n")])
        return data

    def get_security_packages(self, security_property):
        """
        Reimplemented from SpmPlugin class.
        """
        if not self.glsa:
            return []
        if security_property not in ['new','all','affected']:
            return []

        glsaconfig = self.glsa.checkconfig(
            self.portage.config(clone=self.portage.settings))
        completelist = self.glsa.get_glsa_list(
            glsaconfig["GLSA_DIR"], glsaconfig)

        glsalist = []
        if security_property == "new":

            checklist = []
            if os.access(glsaconfig["CHECKFILE"], os.R_OK | os.F_OK):
                with open(glsaconfig["CHECKFILE"], "r") as check_f:
                    checklist.extend([x.strip() for x in check_f.readlines()])
            glsalist = [x for x in completelist if x not in checklist]

        elif security_property == "all":
            glsalist = completelist

        elif security_property == "affected":

            # maybe this should be todolist instead
            for glsa_item in completelist:
                try:
                    myglsa = self.glsa.Glsa(glsa_item, glsaconfig)
                except (self.glsa.GlsaTypeException,
                    self.glsa.GlsaFormatException,):
                    continue

                if not myglsa.isVulnerable():
                    continue

                glsalist.append(glsa_item)

        return glsalist

    def get_security_advisory_metadata(self, advisory_id):
        """
        Reimplemented from SpmPlugin class.
        """
        if not self.glsa:
            return {}

        glsaconfig = self.glsa.checkconfig(
            self.portage.config(clone=self.portage.settings))
        try:
            myglsa = self.glsa.Glsa(advisory_id, glsaconfig)
        except (self.glsa.GlsaTypeException, self.glsa.GlsaFormatException):
            return {}

        mydict = {
            'glsa_id': advisory_id,
            'number': myglsa.nr,
            'access': myglsa.access,
            'title': myglsa.title,
            'synopsis': myglsa.synopsis,
            'announced': myglsa.announced,
            'revised': myglsa.revised,
            'bugs': myglsa.bugs,
            'description': myglsa.description,
            'resolution': myglsa.resolution,
            'impact': myglsa.impact_text,
            'impacttype': myglsa.impact_type,
            'affected': myglsa.affected,
            'background': myglsa.background,
            'glsatype': myglsa.glsatype,
            'packages': myglsa.packages,
            'services': myglsa.services,
            'product': myglsa.product,
            'references': myglsa.references,
            'workaround': myglsa.workaround,
        }

        status = "[U]"
        if myglsa.isApplied():
            status = "[A]"
        elif myglsa.isVulnerable():
            status = "[N]"
        mydict['status'] = status

        return mydict

    def get_setting(self, key):
        """
        Reimplemented from SpmPlugin class.
        """
        return self.portage.settings[key]

    def get_user_installed_packages_file(self, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        world_file = self.portage_const.WORLD_FILE
        if root is None:
            root = etpConst['systemroot'] + os.path.sep
        return os.path.join(root, world_file)

    def get_merge_protected_paths(self):
        """
        Reimplemented from SpmPlugin class.
        """
        config_protect = self.portage.settings['CONFIG_PROTECT']
        return [os.path.expandvars(x) for x in config_protect.split()]

    def get_merge_protected_paths_mask(self):
        """
        Reimplemented from SpmPlugin class.
        """
        config_protect = self.portage.settings['CONFIG_PROTECT_MASK']
        return [os.path.expandvars(x) for x in config_protect.split()]

    def get_download_mirrors(self, mirror_name):
        """
        Reimplemented from SpmPlugin class.
        """
        mirrors = []
        if self.portage.thirdpartymirrors.has_key(mirror_name):
            mirrors.extend(self.portage.thirdpartymirrors[mirror_name])
        return mirrors

    def packages_repositories_metadata_update(self):
        """
        Reimplemented from SpmPlugin class.
        """
        root = etpConst['systemroot'] + os.path.sep
        mydb = {}
        mydb[root] = {}
        mydb[root]['vartree'] = self._get_portage_vartree(root)
        mydb[root]['porttree'] = self._get_portage_portagetree(root)
        mydb[root]['bintree'] = self._get_portage_binarytree(root)
        mydb[root]['virtuals'] = self.portage.settings.getvirtuals(root)

        if etpUi['mute']:
            pid = os.fork()
            if pid > 0:
                os.waitpid(pid, 0)
            else:
                log = LogFile(
                    level = etpConst['spmloglevel'],
                    filename = etpConst['spmlogfile'],
                    header = "[spm]"
                )
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = log
                sys.stderr = log

                self.portage._global_updates(mydb, {})

                sys.stdout = old_stdout
                sys.stderr = old_stderr
                log.flush()
                log.close()
                os._exit(0)
        else:
            self.portage._global_updates(mydb, {}) # always force

    def match_package(self, package, match_type = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if match_type is None:
            match_type = "bestmatch-visible"
        elif match_type not in PortagePlugin.SUPPORTED_MATCH_TYPES:
            raise KeyError

        return self.portage.portdb.xmatch(match_type, package)

    def match_installed_package(self, package, match_all = False, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if root is None:
            root = etpConst['systemroot'] + os.path.sep

        vartree = self._get_portage_vartree(root = root)
        matches = vartree.dep_match(package) or []

        if match_all:
            return matches
        elif matches:
            return matches[-1]
        return ''

    def generate_package(self, package, file_save_path):
        """
        Reimplemented from SpmPlugin class.
        """
        pkgcat, pkgname = package.split("/", 1)
        if not os.path.isdir(file_save_path):
            os.makedirs(file_save_path)
        file_save_path += "/" + pkgname + etpConst['packagesext']
        dbdir = os.path.join(self._get_vdb_path(), pkgcat, pkgname)

        import tarfile
        import stat
        trees = self.portage.db["/"]
        vartree = trees["vartree"]
        dblnk = self.portage.dblink(pkgcat, pkgname, "/", vartree.settings,
            treetype="vartree", vartree=vartree)
        dblnk.lockdb()
        tar = tarfile.open(file_save_path, "w:bz2")

        contents = dblnk.getcontents()
        paths = sorted(contents.keys())

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

            if stat.S_ISREG(exist.st_mode):
                tarinfo.mode = stat.S_IMODE(exist.st_mode)
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
        import entropy.xpak as xpak
        tbz2 = xpak.tbz2(file_save_path)
        tbz2.recompose(dbdir)

        dblnk.unlockdb()

        if os.access(file_save_path, os.F_OK):
            return file_save_path

        raise SPMError("SPMError: Spm:generate_package %s: %s %s" % (
                _("error"),
                file_save_path,
                _("not found"),
            )
        )

    def extract_package_metadata(self, package_file):
        """
        Reimplemented from SpmPlugin class.
        """
        data = {}
        system_settings = SystemSettings()

        # fill package name and version
        data['digest'] = self.entropyTools.md5sum(package_file)
        data['signatures'] = {
            'sha1': self.entropyTools.sha1(package_file),
            'sha256': self.entropyTools.sha256(package_file),
            'sha512': self.entropyTools.sha512(package_file),
        }
        data['datecreation'] = str(self.entropyTools.get_file_unix_mtime(
            package_file))
        data['size'] = str(self.entropyTools.get_file_size(package_file))

        tmp_dir = tempfile.mkdtemp()
        self.entropyTools.extract_xpak(package_file, tmp_dir)

        # package injection status always false by default
        # developer can change metadatum after this function
        data['injected'] = False
        data['branch'] = system_settings['repositories']['branch']

        portage_entries = self._extract_pkg_metadata_generate_extraction_dict()
        for item in portage_entries:

            value = ''
            try:

                item_path = os.path.join(tmp_dir, portage_entries[item]['path'])
                with open(item_path, "r") as item_f:
                    value = item_f.readline().strip().decode(
                        'raw_unicode_escape')

            except IOError:
                if portage_entries[item]['critical']:
                    raise
            data[item] = value


        # workout pf
        pf_atom = os.path.join(data['category'], data['pf'])
        pkgcat, pkgname, pkgver, pkgrev = self.entropyTools.catpkgsplit(
            pf_atom)
        if pkgrev != "r0":
            pkgver += "-%s" % (pkgrev,)
        data['name'] = pkgname
        data['version'] = pkgver
        # bye bye pf
        del data['pf']

        # setup spm_phases properly
        spm_defined_phases_path = os.path.join(tmp_dir,
            portage_entries['spm_phases']['path'])
        if not os.path.isfile(spm_defined_phases_path):
            # force to None, because metadatum can be '', which is valid
            data['spm_phases'] = None

        data['eclasses'] = set(data['eclasses'].split())
        try:
            data['counter'] = int(data['counter'])
        except ValueError:
            # -2 values will be insterted as incremental
            # negative values into the database
            data['counter'] = -2

        data['keywords'] = [x.strip() for x in data['keywords'].split() \
            if x.strip()]
        if not data['keywords']:
            # support for packages with no keywords
            data['keywords'].insert(0, "")

        data['keywords'] = set(data['keywords'])
        needed_file = os.path.join(tmp_dir,
            etpConst['spm']['xpak_entries']['needed'])

        data['needed'] = self._extract_pkg_metadata_needed(needed_file)
        data['needed_paths'] = self._extract_pkg_metadata_needed_paths(
            data['needed'])

        content_file = os.path.join(tmp_dir,
            etpConst['spm']['xpak_entries']['contents'])
        data['content'] = self._extract_pkg_metadata_content(content_file,
            package_file)
        data['disksize'] = self.entropyTools.sum_file_sizes(data['content'])

        # [][][] Kernel dependent packages hook [][][]
        data['versiontag'] = ''
        kernelstuff = False
        kernelstuff_kernel = False
        for item in data['content']:
            if item.startswith("/lib/modules/"):
                kernelstuff = True
                # get the version of the modules
                kmodver = item.split("/lib/modules/")[1]
                kmodver = kmodver.split("/")[0]

                lp = kmodver.split("-")[-1]
                if lp.startswith("r"):
                    kname = kmodver.split("-")[-2]
                    kver = kmodver.split("-")[0]+"-"+kmodver.split("-")[-1]
                else:
                    kname = kmodver.split("-")[-1]
                    kver = kmodver.split("-")[0]
                break

        # validate the results above
        if kernelstuff:
            matchatom = "linux-%s-%s" % (kname,kver,)
            if (matchatom == data['name']+"-"+data['version']):
                kernelstuff_kernel = True

            data['versiontag'] = kmodver
            if not kernelstuff_kernel:
                data['slot'] = kmodver # if you change this behaviour,
                # you must change "reagent update"
                # and "equo database gentoosync" consequentially

        file_ext = etpConst['spm']['ebuild_file_extension']
        ebuilds_in_path = [x for x in os.listdir(tmp_dir) if \
            x.endswith(".%s" % (file_ext,))]

        if not data['versiontag'] and ebuilds_in_path:
            # has the user specified a custom package tag inside the ebuild
            ebuild_path = os.path.join(tmp_dir, ebuilds_in_path[0])
            data['versiontag'] = self._extract_pkg_metadata_ebuild_entropy_tag(
                ebuild_path)

        data['download'] = etpConst['packagesrelativepath'] + data['branch'] \
            + "/"
        data['download'] += self.entropyTools.create_package_filename(
            data['category'], data['name'], data['version'], data['versiontag'])

        data['trigger'] = ""
        trigger_file = os.path.join(etpConst['triggersdir'], data['category'],
            data['name'], etpConst['triggername'])
        if os.access(trigger_file, os.F_OK | os.R_OK):
            with open(trigger_file,"rb") as trig_f:
                data['trigger'] = trig_f.read()

        # Get Spm ChangeLog
        pkgatom = "%s/%s-%s" % (data['category'], data['name'],
            data['version'],)
        try:
            data['changelog'] = unicode(self.get_package_changelog(pkgatom),
                'raw_unicode_escape')
        except (UnicodeEncodeError, UnicodeDecodeError,), e:
            sys.stderr.write("%s: %s, %s\n" % (
                "changelog string conversion error", e,
                package_file,)
            )
            data['changelog'] = None
        except:
            data['changelog'] = None

        portage_metadata = self._calculate_dependencies(
            data['iuse'], data['use'], data['license'], data['depend'],
            data['rdepend'], data['pdepend'], data['provide'], data['sources']
        )

        data['provide'] = set(portage_metadata['PROVIDE'].split())
        data['license'] = portage_metadata['LICENSE']
        data['useflags'] = []
        for my_use in portage_metadata['USE']:
            if my_use in portage_metadata['USE_MASK']:
                continue
            if my_use in portage_metadata['USE_FORCE']:
                data['useflags'].append(my_use)
                continue
            if my_use in portage_metadata['ENABLED_USE']:
                data['useflags'].append(my_use)
            else:
                data['useflags'].append("-"+my_use)

        # useflags must be a set, as returned by entropy.db.getPackageData
        data['useflags'] = set(data['useflags'])
        # sources must be a set, as returned by entropy.db.getPackageData
        data['sources'] = set(portage_metadata['SRC_URI'].split())
        data['dependencies'] = {}

        for x in portage_metadata['RDEPEND'].split():
            if x.startswith("!") or (x in ("(","||",")","")):
                continue
            data['dependencies'][x] = etpConst['spm']['(r)depend_id']

        for x in portage_metadata['PDEPEND'].split():
            if x.startswith("!") or (x in ("(","||",")","")):
                continue
            data['dependencies'][x] = etpConst['spm']['pdepend_id']

        data['conflicts'] = [x.replace("!","") for x in \
            portage_metadata['RDEPEND'].split() + \
            portage_metadata['PDEPEND'].split() if \
            x.startswith("!") and not x in ("(","||",")","")]

        if (kernelstuff) and (not kernelstuff_kernel):
            # add kname to the dependency
            kern_dep_key = u"=sys-kernel/linux-"+kname+"-"+kver+"~-1"
            data['dependencies'][kern_dep_key] = etpConst['spm']['(r)depend_id']

        # Conflicting tagged packages support
        # Needs Entropy Client System Settings Plugin,
        # but since entropy.server loads entropy.client, it's completely
        # fine as of now.
        key = data['category'] + "/" + data['name']
        plug_data = etpConst['system_settings_plugins_ids']
        client_sysset_plg_id = plug_data['client_plugin']
        client_data = system_settings.get(client_sysset_plg_id, {})
        confl_data = None

        if client_data:
            repo_data = client_data['repositories']
            confl_data = repo_data['conflicting_tagged_packages'].get(key)

        if confl_data:
            for conflict in confl_data:
                data['conflicts'].append(conflict)

        # conflicts must be a set, which is what is returned
        # by entropy.db.getPackageData
        data['conflicts'] = set(data['conflicts'])

        # Get License text if possible
        licenses_dir = os.path.join(self.get_setting('PORTDIR'), 'licenses')
        data['licensedata'] = self._extract_pkg_metadata_license_data(
            licenses_dir, data['license'])

        data['mirrorlinks'] = self._extract_pkg_metadata_mirror_links(
            data['sources'])

        # write only if it's a systempackage
        data['systempackage'] = False
        system_packages = [self.entropyTools.dep_getkey(x) for x in \
            self.get_system_packages()]
        if data['category'] + "/" + data['name'] in system_packages:
            data['systempackage'] = True

        # write only if it's a systempackage
        data['config_protect'] = ' '.join(self.get_merge_protected_paths())
        data['config_protect_mask'] = ' '.join(
            self.get_merge_protected_paths_mask())

        log_dir = etpConst['logdir']+"/elog"
        if not os.path.isdir(log_dir): os.makedirs(log_dir)
        data['messages'] = self._extract_pkg_metadata_messages(log_dir,
            data['category'], data['name'], data['version'])

        # etpapi must be int, as returned by entropy.db.getPackageData
        data['etpapi'] = int(etpConst['etpapi'])

        # removing temporary directory
        shutil.rmtree(tmp_dir, True)
        if os.path.isdir(tmp_dir):
            try:
                os.remove(tmp_dir)
            except OSError:
                pass

        # clear unused metadata
        del data['use'], data['iuse'], data['depend'], data['pdepend'], \
            data['rdepend']

        return data

    def enable_package_compile_options(self, package, options):
        """
        Reimplemented from SpmPlugin class.
        """
        result = self._unset_package_useflags(package, options)
        if not result:
            return False
        return self._handle_new_useflags(package, options, "")

    def disable_package_compile_options(self, package, options):
        """
        Reimplemented from SpmPlugin class.
        """
        result = self._unset_package_useflags(package, options)
        if not result:
            return False
        return self._handle_new_useflags(package, options, "-")

    def get_package_compile_options(self, package):
        """
        Reimplemented from SpmPlugin class.
        """
        matched_atom = self.match_package(package)
        if not matched_atom:
            return {}
        global_useflags = self._get_useflags()
        use_force = self._get_useflags_force()
        use_mask = self._get_useflags_mask()
        package_use_useflags = self._get_package_use_useflags(package)

        data = {}
        data['use_force'] = use_force.copy()
        data['use_mask'] = use_mask.copy()
        data['global_use'] = global_useflags.split()

        iuse = self.get_package_metadata(package, "IUSE")
        if not isinstance(iuse, basestring):
            iuse = ''
        data['iuse'] = iuse.split()[:]
        iuse = set()
        for myiuse in data['iuse']:
            if myiuse.startswith("+"):
                myiuse = myiuse[1:]
            iuse.add(myiuse)

        use = [f for f in data['global_use'] + \
            list(package_use_useflags['enabled']) if (f in iuse) \
                and (f not in use_mask) and \
                    (f not in package_use_useflags['disabled'])]

        use_disabled = [f for f in iuse if (f not in data['global_use']) \
            and (f not in use_mask) and \
                (f not in package_use_useflags['enabled'])]

        data['use'] = use[:]
        data['use_disabled'] = use_disabled[:]

        matched_slot = self.get_package_metadata(matched_atom, "SLOT")
        try:
            inst_key = "%s:%s" % (
                self.entropyTools.dep_getkey(package),
                matched_slot,
            )
            installed_atom = self.match_installed_package(inst_key)
        except self.portage_exception:
            installed_atom = ''

        if installed_atom:

            # get its useflags
            previous_iuse = self.get_installed_package_metadata(installed_atom,
                "IUSE").split()
            previous_use = self.get_installed_package_metadata(installed_atom,
                "USE").split()

            new_previous_iuse = set()
            for myuse in previous_iuse:
                if myuse.startswith("+"):
                    myuse = myuse[1:]
                new_previous_iuse.add(myuse)
            previous_iuse = list(new_previous_iuse)

            inst_use = [f for f in previous_iuse if (f in previous_use) and \
                (f not in use_mask)]
            #inst_use_disabled = [f for f in previous_use if \
            #    (f not in previous_iuse) and (f not in use_mask)]

            # check removed use
            use_removed = []
            for myuse in inst_use:
                if myuse not in use:
                    use_removed.append(myuse)

            # use not available
            use_not_avail = []
            for myuse in previous_iuse:
                if (myuse not in iuse) and (myuse not in use_removed):
                    use_not_avail.append(myuse)

            # check new use
            t_use = []
            for myuse in use:
                if myuse not in inst_use:
                    myuse = "+%s*" % (myuse,)
                t_use.append(myuse)
            use = t_use

            # check disabled use
            t_use_disabled = []
            for myuse in use_disabled:
                if myuse in inst_use:
                    if myuse in use_removed+use_not_avail:
                        continue
                    myuse = "-%s*" % (myuse,)
                else:
                    myuse = "-%s" % (myuse,)
                t_use_disabled.append(myuse)
            use_disabled = t_use_disabled

            for myuse in use_removed:
                use_disabled.append("(-%s*)" % (myuse,))
            for myuse in use_not_avail:
                use_disabled.append("(-%s)" % (myuse,))
        else:
            use_disabled = ["-"+x for x in use_disabled]

        data['use_string'] = ' '.join(sorted(use)+sorted([x for x in \
            use_disabled]))
        data['use_string_colored'] = ' '.join(
                sorted([darkred(x) for x in use if not x.startswith("+")] + \
                        [darkgreen(x) for x in use if x.startswith("+")]) + \
                sorted([darkblue(x) for x in use_disabled if x.startswith("-")] + \
                    [brown(x) for x in use_disabled if x.startswith("(") and \
                        (x.find("*") == -1)] + \
                    [purple(x) for x in use_disabled if x.startswith("(") and \
                        (x.find("*") != -1)]
                )
        )

        return data

    def get_installed_package_compile_options(self, package, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        matched_atom = self.match_installed_package(package, root = root)
        if not matched_atom:
            return {}

        global_use = self.get_installed_package_metadata(matched_atom, "USE",
            root = root)
        use_mask = self._get_useflags_mask()

        data = {}
        data['use_mask'] = use_mask.copy()
        data['global_use'] = global_use.split()

        iuse = self.get_installed_package_metadata(matched_atom, "IUSE",
            root = root)
        if not isinstance(iuse, basestring):
            iuse = ''
        data['iuse'] = iuse.split()[:]
        iuse = set()
        for myiuse in data['iuse']:
            if myiuse.startswith("+"):
                myiuse = myiuse[1:]
            iuse.add(myiuse)

        use = [f for f in data['global_use'] if (f in iuse) and \
            (f not in use_mask)]
        use_disabled = [f for f in iuse if (f not in data['global_use']) and \
            (f not in use_mask)]
        data['use'] = use[:]
        data['use_disabled'] = use_disabled[:]

        data['use_string'] = ' '.join(sorted(use)+sorted([x for x in \
            use_disabled]))
        data['use_string_colored'] = ' '.join(
                sorted([darkred(x) for x in use if not x.startswith("+")] + \
                        [darkgreen(x) for x in use if x.startswith("+")]) + \
                sorted([darkblue(x) for x in use_disabled if x.startswith("-")] + \
                    [brown(x) for x in use_disabled if x.startswith("(") and \
                        (x.find("*") == -1)] + \
                    [purple(x) for x in use_disabled if x.startswith("(") and \
                        (x.find("*") != -1)]
                )
        )
        return data

    def get_installed_package_content(self, package, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if root is None:
            root = etpConst['systemroot'] + os.path.sep
        mytree = self._get_portage_vartree(root)

        cat, pkgv = package.split("/")
        return sorted(self.portage.dblink(cat, pkgv, root,
            self.portage.settings).getcontents())

    def get_packages(self, categories = None, filter_reinstalls = True):
        """
        Reimplemented from SpmPlugin class.
        """
        if categories is None:
            categories = []

        root = etpConst['systemroot'] + os.path.sep
        mysettings = self._get_portage_config(os.path.sep, root)
        portdb = self.portage.portdbapi(mysettings["PORTDIR"],
            mysettings = mysettings)

        cps = portdb.cp_all()
        visibles = set()
        for cp in cps:
            if categories and cp.split("/")[0] not in categories:
                continue

            # get slots
            slots = set()
            atoms = self.match_package(cp, match_type = "match-visible")
            if atoms:
                for atom in atoms:
                    slots.add(portdb.aux_get(atom, ["SLOT"])[0])
                for slot in slots:
                    visibles.add(cp+":"+slot)

        # now match visibles
        available = set()
        for visible in visibles:

            match = self.match_package(visible)
            if not match:
                continue

            if filter_reinstalls:
                installed = self.match_installed_package(visible)
                if installed != match:
                    available.add(match)
            else:
                available.add(match)

        return available

    def get_installed_packages(self, categories = None, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        vartree = self._get_portage_vartree(root = root)
        packages = vartree.dbapi.cpv_all()
        if not categories:
            return packages

        def catfilter(pkg):
            if pkg.split("/", 1)[0] in categories:
                return True
            return False

        return filter(catfilter, packages)

    def get_package_sets(self, builtin_sets):
        """
        Reimplemented from SpmPlugin class.
        """
        config = self._get_set_config()
        if config == None:
            return {}

        mysets = config.getSets()
        if not builtin_sets:
            builtin_pkg_sets = [x for x in PortagePlugin.builtin_pkg_sets if \
                x in mysets]
            for pkg_set in builtin_pkg_sets:
                mysets.pop(pkg_set)

        return dict((x, y.getAtoms(),) for x, y in mysets.items())

    def assign_uid_to_installed_package(self, package, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if root is None:
            root = etpConst['systemroot'] + os.path.sep

        vartree = self._get_portage_vartree(root)
        dbbuild = self.get_installed_package_build_script_path(package,
            root = root)

        counter_dir = os.path.dirname(dbbuild)
        counter_name = etpConst['spm']['xpak_entries']['counter']
        counter_path = os.path.join(counter_dir, counter_name)

        if not os.access(counter_dir, os.W_OK):
            raise SPMError("SPM package directory not found")

        with open(counter_path, "w") as count_f:
            new_counter = vartree.dbapi.counter_tick(root, mycpv = package)
            count_f.write(str(new_counter))
            count_f.flush()

        return new_counter

    def search_paths_owners(self, paths, exact_match = True):
        """
        Reimplemented from SpmPlugin class.
        """
        if not isinstance(paths, (list, set, frozenset, dict, tuple,)):
            raise AttributeError("iterable needed")
        root = etpConst['systemroot'] + os.path.sep
        mytree = self._get_portage_vartree(root)
        packages = mytree.dbapi.cpv_all()
        matches = {}

        for package in packages:
            cat, pkgv = package.split("/")
            content = self.portage.dblink(cat, pkgv, root,
                self.portage.settings).getcontents()

            if exact_match:
                for filename in paths:
                    if filename in content:
                        myslot = self.get_installed_package_metadata(package,
                            "SLOT")
                        obj = matches.setdefault((package, myslot,), set())
                        obj.add(filename)
            else:
                for filename in paths:
                    for myfile in content:
                        if myfile.find(filename) == -1:
                            continue
                        myslot = self.get_installed_package_metadata(package,
                            "SLOT")
                        obj = matches.setdefault((package, myslot,), set())
                        obj.add(filename)

        return matches

    def _portage_doebuild(self, myebuild, mydo, tree, cpv,
        portage_tmpdir = None, licenses = None):
        # myebuild = path/to/ebuild.ebuild with a valid unpacked xpak metadata
        # tree = "bintree"
        # cpv = atom
        # mydbapi = portage.fakedbapi(settings=portage.settings)
        # vartree = portage.vartree(root=myroot)

        if licenses is None:
            licenses = []

        oldsystderr = sys.stderr
        dev_null = open("/dev/null","w")
        if not etpUi['debug']:
            sys.stderr = dev_null

        ### SETUP ENVIRONMENT
        # if mute, supress portage output
        domute = False
        if etpUi['mute']:
            domute = True
            oldsysstdout = sys.stdout
            sys.stdout = dev_null

        root = etpConst['systemroot'] + os.path.sep

        # old way to avoid loop of deaths for entropy portage hooks
        os.environ["SKIP_EQUO_SYNC"] = "1"

        # load metadata
        myebuilddir = os.path.dirname(myebuild)
        keys = self.portage.auxdbkeys
        metadata = {}

        for key in keys:
            mykeypath = os.path.join(myebuilddir,key)
            if os.path.isfile(mykeypath) and os.access(mykeypath,os.R_OK):
                f = open(mykeypath,"r")
                metadata[key] = f.readline().strip()
                f.close()

        ### END SETUP ENVIRONMENT

        # find config
        mysettings = self._get_portage_config(os.path.sep, root)
        mysettings['EBUILD_PHASE'] = mydo

        # crappy, broken, ebuilds, put accept_license eutils call
        # in pkg_setup, when environment variables are not setup yet
        # WARNING WARNING WARNING:
        # if some other hook fails for other reasons, it's because
        # it may miss env variable here.
        mysettings['LICENSE'] = str(' '.join(licenses))
        if licenses:
            # we already do this early
            mysettings["ACCEPT_LICENSE"] = mysettings['LICENSE']
            mysettings.backup_changes("ACCEPT_LICENSE")

        mysettings['EAPI'] = "0"
        if metadata.has_key('EAPI'):
            mysettings['EAPI'] = metadata['EAPI']

        # workaround for scripts asking for user intervention
        mysettings['ROOT'] = root
        mysettings['CD_ROOT'] = "/tmp"

        mysettings.backup_changes("EAPI")
        mysettings.backup_changes("LICENSE")
        mysettings.backup_changes("EBUILD_PHASE")
        mysettings.backup_changes("ROOT")
        mysettings.backup_changes("CD_ROOT")

        try: # this is a >portage-2.1.4_rc11 feature
            mysettings._environ_whitelist = set(mysettings._environ_whitelist)
            # put our vars into whitelist
            mysettings._environ_whitelist.add("SKIP_EQUO_SYNC")
            mysettings._environ_whitelist.add("ACCEPT_LICENSE")
            mysettings._environ_whitelist.add("CD_ROOT")
            mysettings._environ_whitelist.add("ROOT")
            mysettings._environ_whitelist = frozenset(mysettings._environ_whitelist)
        except (AttributeError,):
            self.log_message(self.entropyTools.get_traceback())

        cpv = str(cpv)
        mysettings.setcpv(cpv)
        portage_tmpdir_created = False # for pkg_postrm, pkg_prerm
        if portage_tmpdir:
            if not os.path.isdir(portage_tmpdir):
                os.makedirs(portage_tmpdir)
                portage_tmpdir_created = True
            mysettings['PORTAGE_TMPDIR'] = str(portage_tmpdir)
            mysettings.backup_changes("PORTAGE_TMPDIR")

        # create FAKE ${PORTDIR} directory and licenses subdir
        portdir = os.path.join(portage_tmpdir, "portdir")
        portdir_lic = os.path.join(portdir, "licenses")
        if not os.path.isdir(portdir):
            os.mkdir(portdir) # portage_tmpdir must be available!
        # create licenses subdir
        if not os.path.isdir(portdir_lic):
            os.mkdir(portdir_lic)

        # set fake PORTDIR
        old_portdir = mysettings["PORTDIR"][:]
        mysettings["PORTDIR"] = portdir
        mysettings.backup_changes("PORTDIR")

        ### WORKAROUND for buggy check_license() in eutils.eclass
        ### that looks for file availability before considering
        ### ACCEPT_LICENSE
        for lic in licenses:
            lic_path = os.path.join(portdir_lic, lic)
            if not os.access(lic_path, os.F_OK):
                lic_f = open(lic_path, "w")
                lic_f.close()

        mydbapi = self.portage.fakedbapi(settings=mysettings)
        mydbapi.cpv_inject(cpv, metadata = metadata)

        # cached vartree class
        vartree = self._get_portage_vartree(root = root)

        try:
            rc = self.portage.doebuild(
                myebuild = str(myebuild),
                mydo = str(mydo),
                myroot = root,
                tree = tree,
                mysettings = mysettings,
                mydbapi = mydbapi,
                vartree = vartree,
                use_cache = 0
            )
        except:
            self.log_message(self.entropyTools.get_traceback())
            raise

        # if mute, restore old stdout/stderr
        if domute:
            sys.stdout = oldsysstdout

        sys.stderr = oldsystderr
        dev_null.close()

        if portage_tmpdir_created:
            shutil.rmtree(portage_tmpdir,True)

        # reset PORTDIR back to its old path
        # for security !
        mysettings["PORTDIR"] = old_portdir
        mysettings.backup_changes("PORTDIR")

        del mydbapi
        del metadata
        del keys
        return rc

    def execute_package_phase(self, package, build_script_path, phase_name,
        work_dir = None, licenses_accepted = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if licenses_accepted is None:
            licenses_accepted = []

        portage_phase = PortagePlugin.package_phases_map[phase_name]
        return self._portage_doebuild(build_script_path, portage_phase,
            "bintree", package, work_dir, licenses_accepted)

    def _get_portage_vartree(self, root = None):

        if root is None:
            root = etpConst['systemroot'] + os.path.sep

        if not etpConst['spm']['cache'].has_key('portage'):
            etpConst['spm']['cache']['portage'] = {}
        if not etpConst['spm']['cache']['portage'].has_key('vartree'):
            etpConst['spm']['cache']['portage']['vartree'] = {}

        cached = etpConst['spm']['cache']['portage']['vartree'].get(root)
        if cached != None:
            return cached

        try:
            mytree = self.portage.vartree(root=root)
        except Exception, e:
            raise SPMError("SPMError: %s: %s" % (Exception,e,))
        etpConst['spm']['cache']['portage']['vartree'][root] = mytree
        return mytree

    def _get_portage_portagetree(self, root):

        if not etpConst['spm']['cache'].has_key('portage'):
            etpConst['spm']['cache']['portage'] = {}
        if not etpConst['spm']['cache']['portage'].has_key('portagetree'):
            etpConst['spm']['cache']['portage']['portagetree'] = {}

        cached = etpConst['spm']['cache']['portage']['portagetree'].get(root)
        if cached != None:
            return cached

        try:
            mytree = self.portage.portagetree(root=root)
        except Exception, e:
            raise SPMError("SPMError: %s: %s" % (Exception,e,))
        etpConst['spm']['cache']['portage']['portagetree'][root] = mytree
        return mytree

    def _get_portage_binarytree(self, root):

        if not etpConst['spm']['cache'].has_key('portage'):
            etpConst['spm']['cache']['portage'] = {}
        if not etpConst['spm']['cache']['portage'].has_key('binarytree'):
            etpConst['spm']['cache']['portage']['binarytree'] = {}

        cached = etpConst['spm']['cache']['portage']['binarytree'].get(root)
        if cached != None:
            return cached

        pkgdir = root+self.portage.settings['PKGDIR']
        try:
            mytree = self.portage.binarytree(root,pkgdir)
        except Exception, e:
            raise SPMError("SPMError: %s: %s" % (Exception,e,))
        etpConst['spm']['cache']['portage']['binarytree'][root] = mytree
        return mytree

    def _get_portage_config(self, config_root, root, use_cache = True):

        if use_cache:
            if not etpConst['spm']['cache'].has_key('portage'):
                etpConst['spm']['cache']['portage'] = {}
            if not etpConst['spm']['cache']['portage'].has_key('config'):
                etpConst['spm']['cache']['portage']['config'] = {}

            cached = etpConst['spm']['cache']['portage']['config'].get((config_root,root))
            if cached != None:
                return cached

        try:
            mysettings = self.portage.config(config_root = config_root, target_root = root, config_incrementals = self.portage_const.INCREMENTALS)
        except Exception, e:
            raise SPMError("SPMError: %s: %s" % (Exception,e,))
        if use_cache:
            etpConst['spm']['cache']['portage']['config'][(config_root,root)] = mysettings
        return mysettings

    def _get_package_use_file(self):
        return os.path.join(self.portage_const.USER_CONFIG_PATH,'package.use')

    def _handle_new_useflags(self, atom, useflags, mark):
        matched_atom = self.match_package(atom)
        if not matched_atom:
            return False
        use_file = self._get_package_use_file()

        if not (os.path.isfile(use_file) and os.access(use_file,os.W_OK)):
            return False
        f = open(use_file,"r")
        content = [x.strip() for x in f.readlines()]
        f.close()

        def handle_line(line, useflags):

            data = line.split()
            if len(data) < 2:
                return False, line

            myatom = data[0]
            if matched_atom != self.match_package(myatom):
                return False, line

            flags = data[1:]
            base_flags = []
            added_flags = []
            for flag in flags:
                myflag = flag
                if myflag.startswith("+"):
                    myflag = myflag[1:]
                elif myflag.startswith("-"):
                    myflag = myflag[1:]
                if not myflag:
                    continue
                base_flags.append(myflag)

            for useflag in useflags:
                if mark+useflag in base_flags:
                    continue
                added_flags.append(mark+useflag)

            new_line = "%s %s" % (myatom, ' '.join(flags+added_flags))
            return True, new_line


        atom_found = False
        new_content = []
        for line in content:

            changed, elaborated_line = handle_line(line, useflags)
            if changed: atom_found = True
            new_content.append(elaborated_line)

        if not atom_found:
            myline = "%s %s" % (atom, ' '.join([mark+x for x in useflags]))
            new_content.append(myline)


        f = open(use_file+".tmp","w")
        for line in new_content:
            f.write(line+"\n")
        f.flush()
        f.close()
        os.rename(use_file+".tmp", use_file)
        return True

    def _unset_package_useflags(self, atom, useflags):
        matched_atom = self.match_package(atom)
        if not matched_atom:
            return False

        use_file = self._get_package_use_file()
        if not (os.path.isfile(use_file) and os.access(use_file,os.W_OK)):
            return False

        with open(use_file, "r") as f:
            content = [x.strip() for x in f.readlines()]

        new_content = []
        for line in content:

            data = line.split()
            if len(data) < 2:
                new_content.append(line)
                continue

            myatom = data[0]
            if matched_atom != self.match_package(myatom):
                new_content.append(line)
                continue

            flags = data[1:]
            new_flags = []
            for flag in flags:
                myflag = flag

                if myflag.startswith("+"):
                    myflag = myflag[1:]
                elif myflag.startswith("-"):
                    myflag = myflag[1:]

                if myflag in useflags:
                    continue
                elif not flag:
                    continue

                new_flags.append(flag)

            if new_flags:
                new_line = "%s %s" % (myatom, ' '.join(new_flags))
                new_content.append(new_line)

        with open(use_file+".tmp", "w") as f:
            for line in new_content:
                f.write(line+"\n")
            f.flush()

        os.rename(use_file+".tmp", use_file)
        return True

    def _get_package_use_useflags(self, atom):

        data = {
            'enabled': set(),
            'disabled': set(),
        }

        matched_atom = self.match_package(atom)
        if not matched_atom:
            return data

        use_file = self._get_package_use_file()
        if not (os.path.isfile(use_file) and os.access(use_file,os.W_OK)):
            return data

        use_data = self.portage_util.grabdict(use_file)
        for myatom in use_data:
            mymatch = self.match_package(myatom)
            if mymatch != matched_atom:
                continue
            for flag in use_data[myatom]:
                if flag.startswith("-"):
                    myflag = flag[1:]
                    data['enabled'].discard(myflag)
                    data['disabled'].add(myflag)
                else:
                    myflag = flag
                    if myflag.startswith("+"):
                        myflag = myflag[1:]
                    data['disabled'].discard(myflag)
                    data['enabled'].add(myflag)

        return data

    def _get_useflags(self):
        return self.portage.settings['USE']

    def _get_useflags_force(self):
        return self.portage.settings.useforce

    def _get_useflags_mask(self):
        return self.portage.settings.usemask

    def _resolve_enabled_useflags(self, iuse_list, use_list):
        use = set()
        use_mask = self._get_useflags_mask()
        use_force = self._get_useflags_force()
        for myiuse in iuse_list:
            if myiuse[0] in ("+", "-",):
                myiuse = myiuse[1:]
            if ((myiuse in use_list) or (myiuse in use_force)) and \
                (myiuse not in use_mask):
                use.add(myiuse)
        return use

    def _calculate_dependencies(self, my_iuse, my_use, my_license, my_depend,
        my_rdepend, my_pdepend, my_provide, my_src_uri):

        metadata = {
            'LICENSE': my_license,
            'DEPEND': my_depend,
            'PDEPEND': my_pdepend,
            'RDEPEND': my_rdepend,
            'PROVIDE': my_provide,
            'SRC_URI': my_src_uri,
            'USE_MASK': sorted(self._get_useflags_mask()),
            'USE_FORCE': sorted(self._get_useflags_force()),
        }

        # generate USE flags metadata
        raw_use = my_use.split()
        enabled_use = sorted(self._resolve_enabled_useflags(
            my_iuse.split(), raw_use))

        metadata['ENABLED_USE'] = enabled_use
        use = raw_use + [x for x in metadata['USE_FORCE'] if x not in raw_use]
        metadata['USE'] = sorted([unicode(x) for x in use if x not in \
            metadata['USE_MASK']])

        for k in "LICENSE", "RDEPEND", "DEPEND", "PDEPEND", "PROVIDE", "SRC_URI":
            try:
                if k == "SRC_URI":
                    deps = self._src_uri_paren_reduce(metadata[k])
                else:
                    deps = self._paren_reduce(metadata[k])
                deps = self._use_reduce(deps, uselist = raw_use)
                deps = self.paren_normalize(deps)
                if k == "LICENSE":
                    deps = self._paren_license_choose(deps)
                else:
                    deps = self._paren_choose(deps)
                if k.endswith("DEPEND"):
                    deps = self._usedeps_reduce(deps, enabled_use)
                deps = ' '.join(deps)
            except Exception, e:
                self.entropyTools.print_traceback()
                self.updateProgress(
                    darkred("%s: %s: %s :: %s") % (
                        _("Error calculating dependencies"),
                        str(Exception),
                        k,
                        e,
                    ),
                    importance = 1,
                    type = "error",
                    header = red(" !!! ")
                )
                deps = ''
                continue
            metadata[k] = deps
        return metadata

    def _src_uri_paren_reduce(self, src_uris):
        src_uris = self._paren_reduce(src_uris)
        newlist = []
        skip_next = False
        for src_uri in src_uris:
            if skip_next:
                skip_next = False
                continue
            if src_uri == "->":
                skip_next = True
                continue
            newlist.append(src_uri)
        return newlist

    def _usedeps_reduce(self, dependencies, enabled_useflags):
        newlist = []

        def strip_use(xuse):
            myuse = xuse[:]
            if myuse[0] == "!":
                myuse = myuse[1:]
            if myuse[-1] in ("=","?",):
                myuse = myuse[:-1]
            return myuse

        for dependency in dependencies:
            use_deps = self.entropyTools.dep_getusedeps(dependency)
            if use_deps:
                new_use_deps = []
                for use in use_deps:
                    """
                    explicitly support only specific types
                    """
                    if (use[0] == "!") and (use[-1] not in ("=","?",)):
                        # this does not exist atm
                        continue
                    elif use[-1] == "=":
                        if use[0] == "!":
                            # foo[!bar=] means bar? ( foo[-bar] ) !bar? ( foo[bar] )
                            s_use = strip_use(use)
                            if s_use in enabled_useflags:
                                new_use_deps.append("-%s" % (s_use,))
                            else:
                                new_use_deps.append(s_use)
                            continue
                        else:
                            # foo[bar=] means bar? ( foo[bar] ) !bar? ( foo[-bar] )
                            s_use = strip_use(use)
                            if s_use in enabled_useflags:
                                new_use_deps.append(s_use)
                            else:
                                new_use_deps.append("-%s" % (s_use,))
                            continue
                    elif use[-1] == "?":
                        if use[0] == "!":
                            # foo[!bar?] means bar? ( foo ) !bar? ( foo[-bar] )
                            s_use = strip_use(use)
                            if s_use not in enabled_useflags:
                                new_use_deps.append("-%s" % (s_use,))
                            continue
                        else:
                            # foo[bar?] means bar? ( foo[bar] ) !bar? ( foo )
                            s_use = strip_use(use)
                            if s_use in enabled_useflags:
                                new_use_deps.append(s_use)
                            continue
                    new_use_deps.append(use)

                if new_use_deps:
                    dependency = "%s[%s]" % (
                        self.entropyTools.remove_usedeps(dependency),
                        ','.join(new_use_deps),
                    )
                else:
                    dependency = self.entropyTools.remove_usedeps(dependency)

            newlist.append(dependency)
        return newlist

    def _paren_reduce(self, mystr):
        """

            # deps.py -- Portage dependency resolution functions
            # Copyright 2003-2004 Gentoo Foundation
            # Distributed under the terms of the GNU General Public License v2
            # $Id: portage_dep.py 9174 2008-01-11 05:49:02Z zmedico $

        Take a string and convert all paren enclosed entities into sublists, optionally
        futher splitting the list elements by spaces.

        Example usage:
                >>> paren_reduce('foobar foo ( bar baz )',1)
                ['foobar', 'foo', ['bar', 'baz']]
                >>> paren_reduce('foobar foo ( bar baz )',0)
                ['foobar foo ', [' bar baz ']]

        @param mystr: The string to reduce
        @type mystr: String
        @rtype: Array
        @return: The reduced string in an array
        """
        mylist = []
        while mystr:
            left_paren = mystr.find("(")
            has_left_paren = left_paren != -1
            right_paren = mystr.find(")")
            has_right_paren = right_paren != -1
            if not has_left_paren and not has_right_paren:
                freesec = mystr
                subsec = None
                tail = ""
            elif mystr[0] == ")":
                return [mylist,mystr[1:]]
            elif has_left_paren and not has_right_paren:
                raise InvalidDependString(
                        "InvalidDependString: %s: '%s'" % (_("missing right parenthesis"),mystr,))
            elif has_left_paren and left_paren < right_paren:
                freesec,subsec = mystr.split("(",1)
                subsec,tail = self._paren_reduce(subsec)
            else:
                subsec,tail = mystr.split(")",1)
                subsec = self._strip_empty(subsec.split(" "))
                return [mylist+subsec,tail]
            mystr = tail
            if freesec:
                mylist = mylist + self._strip_empty(freesec.split(" "))
            if subsec is not None:
                mylist = mylist + [subsec]
        return mylist

    def _strip_empty(self, myarr):
        """

            # deps.py -- Portage dependency resolution functions
            # Copyright 2003-2004 Gentoo Foundation
            # Distributed under the terms of the GNU General Public License v2
            # $Id: portage_dep.py 9174 2008-01-11 05:49:02Z zmedico $

        Strip all empty elements from an array

        @param myarr: The list of elements
        @type myarr: List
        @rtype: Array
        @return: The array with empty elements removed
        """
        for x in range(len(myarr)-1, -1, -1):
                if not myarr[x]:
                        del myarr[x]
        return myarr

    def _use_reduce(self, deparray, uselist = None, masklist = None,
        matchall = 0, excludeall = None):
        """

            # deps.py -- Portage dependency resolution functions
            # Copyright 2003-2004 Gentoo Foundation
            # Distributed under the terms of the GNU General Public License v2
            # $Id: portage_dep.py 9174 2008-01-11 05:49:02Z zmedico $

        Takes a paren_reduce'd array and reduces the use? conditionals out
        leaving an array with subarrays

        @param deparray: paren_reduce'd list of deps
        @type deparray: List
        @param uselist: List of use flags
        @type uselist: List
        @param masklist: List of masked flags
        @type masklist: List
        @param matchall: Resolve all conditional deps unconditionally.  Used by repoman
        @type matchall: Integer
        @rtype: List
        @return: The use reduced depend array
        """

        if uselist is None:
            uselist = []
        if masklist is None:
            masklist = []
        if excludeall is None:
            excludeall = []

        # Quick validity checks
        for x in range(len(deparray)):
            if deparray[x] in ["||","&&"]:
                if len(deparray) - 1 == x or not isinstance(deparray[x+1], list):
                    mytxt = _("missing atom list in")
                    raise InvalidDependString(deparray[x]+" "+mytxt+" \""+str(deparray)+"\"")
        if deparray and deparray[-1] and deparray[-1][-1] == "?":
            mytxt = _("Conditional without target in")
            raise InvalidDependString("InvalidDependString: "+mytxt+" \""+str(deparray)+"\"")

        # This is just for use by emerge so that it can enable a backward compatibility
        # mode in order to gracefully deal with installed packages that have invalid
        # atoms or dep syntax.  For backward compatibility with api consumers, strict
        # behavior will be explicitly enabled as necessary.
        _dep_check_strict = False

        mydeparray = deparray[:]
        rlist = []
        while mydeparray:
            head = mydeparray.pop(0)

            if isinstance(head,list):
                additions = self._use_reduce(head, uselist, masklist, matchall, excludeall)
                if additions:
                    rlist.append(additions)
                elif rlist and rlist[-1] == "||":
                    #XXX: Currently some DEPEND strings have || lists without default atoms.
                    #	raise portage_exception.InvalidDependString("No default atom(s) in \""+paren_enclose(deparray)+"\"")
                    rlist.append([])
            else:
                if head[-1] == "?": # Use reduce next group on fail.
                    # Pull any other use conditions and the following atom or list into a separate array
                    newdeparray = [head]
                    while isinstance(newdeparray[-1], basestring) and newdeparray[-1][-1] == "?":
                        if mydeparray:
                            newdeparray.append(mydeparray.pop(0))
                        else:
                            raise ValueError, _("Conditional with no target")

                    # Deprecation checks
                    warned = 0
                    if len(newdeparray[-1]) == 0:
                        mytxt = "%s. (%s)" % (_("Empty target in string"),_("Deprecated"),)
                        self.updateProgress(
                            darkred("PortagePlugin._use_reduce(): %s" % (mytxt,)),
                            importance = 0,
                            type = "error",
                            header = bold(" !!! ")
                        )
                        warned = 1
                    if len(newdeparray) != 2:
                        mytxt = "%s. (%s)" % (_("Nested use flags without parenthesis"),_("Deprecated"),)
                        self.updateProgress(
                            darkred("PortagePlugin._use_reduce(): %s" % (mytxt,)),
                            importance = 0,
                            type = "error",
                            header = bold(" !!! ")
                        )
                        warned = 1
                    if warned:
                        self.updateProgress(
                            darkred("PortagePlugin._use_reduce(): "+" ".join(map(str,[head]+newdeparray))),
                            importance = 0,
                            type = "error",
                            header = bold(" !!! ")
                        )

                    # Check that each flag matches
                    ismatch = True
                    missing_flag = False
                    for head in newdeparray[:-1]:
                        head = head[:-1]
                        if not head:
                            missing_flag = True
                            break
                        if head.startswith("!"):
                            head_key = head[1:]
                            if not head_key:
                                missing_flag = True
                                break
                            if not matchall and head_key in uselist or \
                                head_key in excludeall:
                                ismatch = False
                                break
                        elif head not in masklist:
                            if not matchall and head not in uselist:
                                    ismatch = False
                                    break
                        else:
                            ismatch = False
                    if missing_flag:
                        mytxt = _("Conditional without flag")
                        raise InvalidDependString(
                                "InvalidDependString: "+mytxt+": \"" + \
                                str([head+"?", newdeparray[-1]])+"\"")

                    # If they all match, process the target
                    if ismatch:
                        target = newdeparray[-1]
                        if isinstance(target, list):
                            additions = self._use_reduce(target, uselist, masklist, matchall, excludeall)
                            if additions:
                                    rlist.append(additions)
                        elif not _dep_check_strict:
                            # The old deprecated behavior.
                            rlist.append(target)
                        else:
                            mytxt = _("Conditional without parenthesis")
                            raise InvalidDependString(
                                    "InvalidDependString: "+mytxt+": '%s?'" % head)

                else:
                    rlist += [head]
        return rlist

    def _paren_choose(self, dep_list):
        newlist = []
        do_skip = False
        for idx in range(len(dep_list)):

            if do_skip:
                do_skip = False
                continue

            item = dep_list[idx]
            if item == "||": # or
                next_item = dep_list[idx+1]
                if not next_item: # || ( asd? ( atom ) dsa? ( atom ) ) => [] if use asd and dsa are disabled
                    do_skip = True
                    continue
                item = self._dep_or_select(next_item) # must be a list
                if not item:
                    # no matches, transform to string and append, so reagent will fail
                    newlist.append(str(next_item))
                else:
                    newlist += item
                do_skip = True
            elif isinstance(item, list): # and
                item = self._dep_and_select(item)
                newlist += item
            else:
                newlist.append(item)

        return newlist

    def _dep_and_select(self, and_list):
        do_skip = False
        newlist = []
        for idx in range(len(and_list)):

            if do_skip:
                do_skip = False
                continue

            x = and_list[idx]
            if x == "||":
                x = self._dep_or_select(and_list[idx+1])
                do_skip = True
                if not x:
                    x = str(and_list[idx+1])
                else:
                    newlist += x
            elif isinstance(x, list):
                x = self._dep_and_select(x)
                newlist += x
            else:
                newlist.append(x)

        # now verify if all are satisfied
        for x in newlist:
            match = self.match_installed_package(x)
            if not match:
                return []

        return newlist

    def _dep_or_select(self, or_list):
        do_skip = False
        for idx in range(len(or_list)):
            if do_skip:
                do_skip = False
                continue
            x = or_list[idx]
            if x == "||": # or
                x = self._dep_or_select(or_list[idx+1])
                do_skip = True
            elif isinstance(x, list): # and
                x = self._dep_and_select(x)
                if not x:
                    continue
                # found
                return x
            else:
                x = [x]

            for y in x:
                match = self.match_installed_package(y)
                if match:
                    return [y]

        return []

    def _paren_license_choose(self, dep_list):

        newlist = set()
        for item in dep_list:

            if isinstance(item, list):
                # match the first
                data = set(self._paren_license_choose(item))
                newlist.update(data)
            else:
                if item not in ["||"]:
                    newlist.add(item)

        return list(newlist)

    def _get_vdb_path(self, root = None):
        if root is None:
            root = etpConst['systemroot'] + os.path.sep
        return os.path.join(root, self.portage_const.VDB_PATH)

    def _load_sets_config(self, settings, trees):

        # from portage.const import USER_CONFIG_PATH, GLOBAL_CONFIG_PATH
        setconfigpaths = [os.path.join(self.portage_const.GLOBAL_CONFIG_PATH, etpConst['setsconffilename'])]
        setconfigpaths.append(os.path.join(settings["PORTDIR"], etpConst['setsconffilename']))
        setconfigpaths += [os.path.join(x, etpConst['setsconffilename']) for x in settings["PORTDIR_OVERLAY"].split()]
        setconfigpaths.append(os.path.join(settings["PORTAGE_CONFIGROOT"],
            self.portage_const.USER_CONFIG_PATH.lstrip(os.path.sep), etpConst['setsconffilename']))
        return self.portage_sets.SetConfig(setconfigpaths, settings, trees)

    def _get_set_config(self):
        # old portage
        if self.portage_sets == None:
            return
        myroot = etpConst['systemroot'] + os.path.sep
        return self._load_sets_config(
            self.portage.settings,
            self.portage.db[myroot]
        )

    def _extract_pkg_metadata_generate_extraction_dict(self):
        data = {
            'pf': {
                'path': etpConst['spm']['xpak_entries']['pf'],
                'critical': True,
            },
            'chost': {
                'path': etpConst['spm']['xpak_entries']['chost'],
                'critical': True,
            },
            'description': {
                'path': etpConst['spm']['xpak_entries']['description'],
                'critical': False,
            },
            'homepage': {
                'path': etpConst['spm']['xpak_entries']['homepage'],
                'critical': False,
            },
            'slot': {
                'path': etpConst['spm']['xpak_entries']['slot'],
                'critical': False,
            },
            'cflags': {
                'path': etpConst['spm']['xpak_entries']['cflags'],
                'critical': False,
            },
            'cxxflags': {
                'path': etpConst['spm']['xpak_entries']['cxxflags'],
                'critical': False,
            },
            'category': {
                'path': etpConst['spm']['xpak_entries']['category'],
                'critical': True,
            },
            'rdepend': {
                'path': etpConst['spm']['xpak_entries']['rdepend'],
                'critical': False,
            },
            'pdepend': {
                'path': etpConst['spm']['xpak_entries']['pdepend'],
                'critical': False,
            },
            'depend': {
                'path': etpConst['spm']['xpak_entries']['depend'],
                'critical': False,
            },
            'use': {
                'path': etpConst['spm']['xpak_entries']['use'],
                'critical': False,
            },
            'iuse': {
                'path': etpConst['spm']['xpak_entries']['iuse'],
                'critical': False,
            },
            'license': {
                'path': etpConst['spm']['xpak_entries']['license'],
                'critical': False,
            },
            'provide': {
                'path': etpConst['spm']['xpak_entries']['provide'],
                'critical': False,
            },
            'sources': {
                'path': etpConst['spm']['xpak_entries']['src_uri'],
                'critical': False,
            },
            'eclasses': {
                'path': etpConst['spm']['xpak_entries']['inherited'],
                'critical': False,
            },
            'counter': {
                'path': etpConst['spm']['xpak_entries']['counter'],
                'critical': False,
            },
            'keywords': {
                'path': etpConst['spm']['xpak_entries']['keywords'],
                'critical': False,
            },
            'spm_phases': {
                'path': etpConst['spm']['xpak_entries']['defined_phases'],
                'critical': False,
            },
        }
        return data

    def _extract_pkg_metadata_content(self, content_file, package_path):

        pkg_content = {}

        if os.path.isfile(content_file):

            f = open(content_file,"r")
            content = [x.decode('raw_unicode_escape') for x in f.readlines()]
            f.close()
            outcontent = set()
            for line in content:
                line = line.strip().split()
                try:
                    datatype = line[0]
                    datafile = line[1:]
                    if datatype == 'obj':
                        datafile = datafile[:-2]
                        datafile = ' '.join(datafile)
                    elif datatype == 'dir':
                        datafile = ' '.join(datafile)
                    elif datatype == 'sym':
                        datafile = datafile[:-3]
                        datafile = ' '.join(datafile)
                    else:
                        myexc = "InvalidData: %s %s. %s." % (
                            datafile,
                            _("not supported"),
                            _("Probably Portage API has changed"),
                        )
                        raise InvalidData(myexc)
                    outcontent.add((datafile,datatype))
                except:
                    pass

            outcontent = sorted(outcontent)
            for datafile, datatype in outcontent:
                pkg_content[datafile] = datatype

        else:

            # CONTENTS is not generated when a package is emerged with portage and the option -B
            # we have to unpack the tbz2 and generate content dict
            mytempdir = etpConst['packagestmpdir']+"/"+os.path.basename(package_path)+".inject"
            if os.path.isdir(mytempdir):
                shutil.rmtree(mytempdir)
            if not os.path.isdir(mytempdir):
                os.makedirs(mytempdir)

            self.entropyTools.uncompress_tar_bz2(package_path, extractPath = mytempdir, catchEmpty = True)
            tmpdir_len = len(mytempdir)
            for currentdir, subdirs, files in os.walk(mytempdir):
                pkg_content[currentdir[tmpdir_len:]] = u"dir"
                for item in files:
                    item = currentdir+"/"+item
                    if os.path.islink(item):
                        pkg_content[item[tmpdir_len:]] = u"sym"
                    else:
                        pkg_content[item[tmpdir_len:]] = u"obj"

            # now remove
            shutil.rmtree(mytempdir,True)
            try:
                os.rmdir(mytempdir)
            except (OSError,):
                pass

        return pkg_content

    def _extract_pkg_metadata_needed(self, needed_file):

        pkg_needed = set()
        lines = []

        try:
            f = open(needed_file,"r")
            lines = [x.decode('raw_unicode_escape').strip() for x in f.readlines() if x.strip()]
            f.close()
        except IOError:
            return lines

        for line in lines:
            needed = line.split()
            if len(needed) == 2:
                ownlib = needed[0]
                ownelf = -1
                if os.access(ownlib,os.R_OK):
                    ownelf = self.entropyTools.read_elf_class(ownlib)
                for lib in needed[1].split(","):
                    #if lib.find(".so") != -1:
                    pkg_needed.add((lib,ownelf))

        return sorted(pkg_needed)

    def _extract_pkg_metadata_needed_paths(self, needed_libs):

        data = {}
        ldpaths = self.entropyTools.collect_linker_paths()

        for needed_lib, elf_class in needed_libs:
            for ldpath in ldpaths:
                my_lib = os.path.join(ldpath, needed_lib)
                if not os.access(my_lib, os.R_OK):
                    continue
                myclass = self.entropyTools.read_elf_class(my_lib)
                if myclass != elf_class:
                    continue
                obj = data.setdefault(needed_lib, set())
                obj.add((my_lib, myclass,))

        return data

    def _extract_pkg_metadata_messages(self, log_dir, category, name, version):

        pkg_messages = []
        if not os.path.isdir(log_dir):
            return pkg_messages

        elogfiles = os.listdir(log_dir)
        myelogfile = "%s:%s-%s" % (category, name, version,)
        foundfiles = [x for x in elogfiles if x.startswith(myelogfile)]
        if foundfiles:
            elogfile = foundfiles[0]
            if len(foundfiles) > 1:
                # get the latest
                mtimes = []
                for item in foundfiles: mtimes.append((self.entropyTools.get_file_unix_mtime(os.path.join(log_dir,item)),item))
                mtimes = sorted(mtimes)
                elogfile = mtimes[-1][1]
            messages = self.entropyTools.extract_elog(os.path.join(log_dir,elogfile))
            for message in messages:
                message = message.replace("emerge","install")
                pkg_messages.append(message.decode('raw_unicode_escape'))

        return pkg_messages

    def _extract_pkg_metadata_license_data(self, licenses_dir, license_string):

        pkg_licensedata = {}
        if licenses_dir and os.path.isdir(licenses_dir):
            licdata = [x.strip() for x in license_string.split() if x.strip() and self.entropyTools.is_valid_string(x.strip())]
            for mylicense in licdata:
                licfile = os.path.join(licenses_dir,mylicense)
                if os.access(licfile,os.R_OK):
                    if self.entropyTools.istextfile(licfile):
                        f = open(licfile)
                        content = ''
                        line = f.readline()
                        while line:
                            content += line
                            line = f.readline()
                        try:
                            try:
                                pkg_licensedata[mylicense] = content.decode('raw_unicode_escape')
                            except UnicodeDecodeError:
                                pkg_licensedata[mylicense] = unicode(content,'utf-8')
                        except (UnicodeDecodeError, UnicodeEncodeError,):
                            continue # sorry!
                        f.close()

        return pkg_licensedata

    def _extract_pkg_metadata_mirror_links(self, sources_list):

        # =mirror://openoffice|link1|link2|link3
        pkg_links = []
        for i in sources_list:
            if i.startswith("mirror://"):
                # parse what mirror I need
                mirrorURI = i.split("/")[2]
                mirrorlist = set(self.get_download_mirrors(mirrorURI))
                pkg_links.append([mirrorURI,mirrorlist])
                # mirrorURI = openoffice and mirrorlist = [link1, link2, link3]

        return pkg_links

    def _extract_pkg_metadata_ebuild_entropy_tag(self, ebuild):
        search_tag = etpConst['spm']['ebuild_pkg_tag_var']
        ebuild_tag = ''
        f = open(ebuild,"r")
        tags = [x.strip().decode('raw_unicode_escape') for x in f.readlines() if x.strip() and x.strip().startswith(search_tag)]
        f.close()
        if not tags: return ebuild_tag
        tag = tags[-1]
        tag = tag.split("=")[-1].strip('"').strip("'").strip()
        return tag

