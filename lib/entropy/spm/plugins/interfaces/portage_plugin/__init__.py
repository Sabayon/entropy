# -*- coding: utf-8 -*-
"""

    @author: Fabio Erculiani <lxnay@sabayon.org>
    @contact: lxnay@sabayon.org
    @copyright: Fabio Erculiani
    @license: GPL-2

    B{Entropy Source Package Manager "Portage" Plugin}.

"""
import os
import errno
import bz2
import hashlib
import shlex
import stat
import sys
import shutil
import stat
import subprocess
import tarfile
import time
import codecs
import warnings
import gc

from entropy.const import etpConst, const_get_stringtype, \
    const_convert_to_unicode, const_convert_to_rawstring, \
    const_setup_perms, const_setup_file, const_is_python3, \
    const_debug_enabled, const_mkdtemp, const_mkstemp, \
    const_file_readable, const_dir_readable
from entropy.exceptions import FileNotFound, InvalidDependString, \
    InvalidAtom, EntropyException
from entropy.output import darkred, darkgreen, brown, darkblue, teal, \
    purple, red, bold, blue, getcolor, decolorize, is_mute, is_interactive
from entropy.i18n import _
from entropy.core.settings.base import SystemSettings
from entropy.misc import LogFile, ParallelTask
from entropy.spm.plugins.skel import SpmPlugin
import entropy.dep
import entropy.tools
from entropy.spm.plugins.interfaces.portage_plugin import xpak
from entropy.spm.plugins.interfaces.portage_plugin import xpaktools


class StdoutSplitter(object):

    def __init__(self, phase, logger, std):
        self._phase = phase
        self._logger = logger
        self._std = std
        self._closed = False
        self._rfd, self._wfd = os.pipe()

        self._task = ParallelTask(self._pusher)
        self._task.name = "StdoutSplitterPusher"
        self._task.daemon = True
        self._task.start()

        if const_is_python3():

            class Writer(object):

                def __init__(self, parent, buf):
                    self._buf = buf
                    self._parent = parent

                def write(self, b):
                    self._buf.write(b)
                    self._parent.write(const_convert_to_unicode(b))

                def flush(self):
                    self._buf.flush()
                    self._parent.flush()

            self.buffer = Writer(self, self._std.buffer)

    def __iter__(self):
        return self._std

    def __hash__(self):
        return hash(self._std)

    def _pusher(self):
        while True:
            try:
                chunk = os.read(self._rfd, 512) # BLOCKS
            except (IOError, OSError) as err:
                # both can raise EINTR
                if err.errno == errno.EINTR:
                    continue
                if err.errno == errno.EBADF:
                    # fd has been closed
                    break
                raise
            try:
                if const_is_python3():
                    self._std.buffer.write(chunk)
                else:
                    self._std.write(chunk)
            except (OSError, IOError) as err:
                sys.__stderr__.write(
                    "_pusher thread: "
                    "cannot write to stdout: "
                    "%s" % (repr(err),))
            try:
                # write directly without mangling
                os.write(self._logger.fileno(), chunk)
            except (OSError, IOError) as err:
                sys.__stderr__.write(
                    "_pusher thread: "
                    "cannot write to logger: "
                    "%s" % (repr(err),))
            if self._closed:
                break

    @property
    def softspace(self):
        return self._std.softspace

    @property
    def name(self):
        return self._std.name

    @property
    def newlines(self):
        return self._std.newlines

    @property
    def mode(self):
        return self._std.mode

    @property
    def errors(self):
        return self._std.errors

    @property
    def encoding(self):
        return self._std.encoding

    @property
    def closed(self):
        return self._closed

    def fileno(self):
        # redirect Portage to our pipe
        return self._wfd

    def flush(self):
        self._logger.flush()
        return self._std.flush()

    def close(self):
        self._closed = True
        err = None
        try:
            os.close(self._wfd)
        except OSError as _err:
            err = _err
        try:
            os.close(self._rfd)
        except OSError as _err:
            err = _err

        self._task.join()
        if err is not None:
            raise err

    def isatty(self):
        return self._std.isatty()

    def next(self):
        return self._std.next()

    def __next__(self):
        return next(self._std)

    def read(self, *args, **kwargs):
        return self._std.read(*args, **kwargs)

    def readline(self, *args, **kwargs):
        return self._std.readline(*args, **kwargs)

    def readlines(self, *args, **kwargs):
        return self._std.readlines(*args, **kwargs)

    def seek(self, *args, **kwargs):
        return self._std.seek(*args, **kwargs)

    def tell(self):
        return self._std.tell()

    def truncate(self, *args, **kwargs):
        return self._std.truncate(*args, **kwargs)

    def write(self, mystr):
        try:
            raw_string = const_convert_to_rawstring(mystr)
        except UnicodeEncodeError:
            raw_string = const_convert_to_rawstring(
                mystr, etpConst['conf_encoding'])

        to_write = len(raw_string)
        count = 0
        while to_write < count:
            try:
                count += os.write(self._wfd, raw_string[count:])
            except (IOError, OSError) as err:
                # both can raise EINTR
                if err.errno == errno.EINTR:
                    continue
                raise

    def writelines(self, lst):
        for line in lst:
            self.write(line)

    if const_is_python3():

        # line_buffering readable seekable writable
        def readable(self):
            return self._std.readable()

        def seekable(self):
            return self._std.seekable()

        def writable(self):
            return self._std.writable()

        @property
        def line_buffering(self):
            return self._std.line_buffering

    else:
        def xreadlines(self):
            return self._std.xreadlines()


class PortagePackageGroups(dict):
    """
    Entropy Package categories group representation
    """
    def __init__(self):
        dict.__init__(self)

        data = {
            'accessibility': {
                'name': _("Accessibility"),
                'description': \
                    _("Accessibility applications"),
                'categories': ['app-accessibility'],
            },
            'office': {
                'name': _("Office"),
                'description': _("Applications used in office environments"),
                'categories': ['app-office', 'app-pda', 'app-mobilephone',
                    'app-cdr', 'app-antivirus', 'app-laptop', 'mail-',
                ],
            },
            'development': {
                'name': _("Development"),
                'description': _("Applications or system libraries"),
                'categories': ['dev-', 'sys-devel'],
            },
            'system': {
                'name': _("System"),
                'description': _("System applications or libraries"),
                'categories': ['sys-'],
            },
            'games': {
                'name': _("Games"),
                'description': _("Games, enjoy your spare time"),
                'categories': ['games-'],
            },
            'gnome': {
                'name': _("GNOME Desktop"),
                'description': \
                    _("Applications and libraries for the GNOME Desktop"),
                'categories': ['gnome-'],
            },
            'kde': {
                'name': _("KDE Desktop"),
                'description': \
                    _("Applications and libraries for the KDE Desktop"),
                'categories': ['kde-'],
            },
            'xfce': {
                'name': _("XFCE Desktop"),
                'description': \
                    _("Applications and libraries for the XFCE Desktop"),
                'categories': ['xfce-'],
            },
            'lxde': {
                'name': _("LXDE Desktop"),
                'description': \
                    _("Applications and libraries for the LXDE Desktop"),
                'categories': ['lxde-'],
            },
            'multimedia': {
                'name': _("Multimedia"),
                'description': \
                    _("Applications and libraries for Multimedia"),
                'categories': ['media-'],
            },
            'networking': {
                'name': _("Networking"),
                'description': \
                    _("Applications and libraries for Networking"),
                'categories': ['net-', 'www-'],
            },
            'science': {
                'name': _("Science"),
                'description': \
                    _("Scientific applications and libraries"),
                'categories': ['sci-'],
            },
            'security': {
                'name': _("Security"),
                'description': \
                    _("Security oriented applications"),
                'categories': ['app-antivirus', 'net-analyzer', 'net-firewall'],
            },
            'x11': {
                'name': _("X11"),
                'description': \
                    _("Applications and libraries for X11"),
                'categories': ['x11-'],
            },
        }
        self.update(data)


class PortageMetaphor:

    """
    This class (will) contains Portage packages metaphor related functions.
    It is intended for internal (plugin) use only. So, go away from here ;)
    """

    # used to properly sort /usr/portage/profiles/updates files
    @staticmethod
    def sort_update_files(update_list):
        """
        docstring_title

        @param update_list: 
        @type update_list: 
        @return: 
        @rtype: 
        """
        sort_dict = {}
        # sort per year
        for item in update_list:
            # get year
            year = item.split("-")[1]
            if year in sort_dict:
                sort_dict[year].append(item)
            else:
                sort_dict[year] = []
                sort_dict[year].append(item)
        new_list = []
        keys = sorted(sort_dict.keys())
        for key in keys:
            sort_dict[key].sort()
            new_list += sort_dict[key]
        del sort_dict
        return new_list


class PortageEntropyDepTranslator(object):
    """
    Conditional dependency string translator from Portage to Entropy.

    Example usage:
    >>> translator = PortageEntropyDepTranslator(portage_string)
    >>> entropy_string = translator.translate()
    entropy_string

    """

    class ParseError(EntropyException):
        """
        Parse error.
        """

    def __init__(self, portage_dependency):
        """
        PortageEntropyDepTranslator constructor.

        @param portage_dependency: Portage dependency string
        @type portage_dependency: string
        """
        self.__dep = portage_dependency

    def __produce_entropy_dep(self, split_dep):
        """
        Digest Portage raw dependency data produced by __extract_scope()
        """
        dep_str_list = []
        operator, sub_split = split_dep[0], split_dep[1:]

        for dep in sub_split:
            if isinstance(dep, list):
                _str = self.__produce_entropy_dep(dep)
            else:
                _str = dep
            dep_str_list.append(_str)

        return "( " + (" " + operator + " ").join(dep_str_list) + " )"

    def __extract_scope(self, split_sub):
        """
        Prepare split Portage dependency string for complete digestion.
        """
        scope_list = []
        nest_level = 0
        skip_count = 0
        sub_count = 0

        for sub_idx in range(len(split_sub)):

            sub_count += 1
            if skip_count:
                skip_count -= 1
                continue

            sub = split_sub[sub_idx]
            if sub == "||": # or
                try:
                    next_sub = split_sub[sub_idx+1]
                except IndexError as err:
                    raise PortageEntropyDepTranslator.ParseError(
                        "Index Error")
                if next_sub != "(":
                    raise PortageEntropyDepTranslator.ParseError(
                        "Syntax Error")

                local_sub_count, sub_scope = self.__extract_scope(
                    split_sub[sub_idx+2:])
                skip_count += local_sub_count
                scope_list.append(
                    [entropy.dep.DependencyStringParser.LOGIC_OR] + sub_scope)

            elif sub == "(":
                local_sub_count, sub_scope = self.__extract_scope(
                    split_sub[sub_idx+1:])
                skip_count += local_sub_count
                scope_list.append(
                    [entropy.dep.DependencyStringParser.LOGIC_AND] + sub_scope)
                nest_level += 1

            elif sub == ")":
                if nest_level == 0:
                    break # end of scope
                nest_level -= 1

            else:
                scope_list.append(sub)

        return sub_count, scope_list

    def translate(self):
        """
        Effectively translate Portage dependency string returning Entropy one.

        @return: Entropy dependency string
        @rtype: string
        @raise PortageEntropyDepTranslator.ParseError: in case of malformed
            Portage dependency.
        """
        split_sub = [x.strip() for x in self.__dep.split() if x.strip()]
        count, split_dep = self.__extract_scope(split_sub)
        return self.__produce_entropy_dep(split_dep[0])


class PortagePlugin(SpmPlugin):

    xpak_entries = {
        'description': "DESCRIPTION",
        'homepage': "HOMEPAGE",
        'chost': "CHOST",
        'category': "CATEGORY",
        'cflags': "CFLAGS",
        'cxxflags': "CXXFLAGS",
        'license': "LICENSE",
        'src_uri': "SRC_URI",
        'use': "USE",
        'iuse': "IUSE",
        'slot': "SLOT",
        'provide': "PROVIDE",
        'depend': "DEPEND",
        'rdepend': "RDEPEND",
        'pdepend': "PDEPEND",
        'needed': "NEEDED",
        'needed.elf.2': "NEEDED.ELF.2",
        'inherited': "INHERITED",
        'keywords': "KEYWORDS",
        'contents': "CONTENTS",
        'counter': "COUNTER",
        'defined_phases': "DEFINED_PHASES",
        'repository': "repository",
        'pf': "PF",
        'eapi': "EAPI",
        'features': "FEATURES",
    }

    _xpak_const = {
        # xpak temp directory path
        'entropyxpakrelativepath': "xpak",
        # xpak metadata directory path
        'entropyxpakdatarelativepath': "data",
        # xpak metadata file name
        'entropyxpakfilename': "metadata.xpak",
    }

    _ebuild_entries = {
        'ebuild_pkg_tag_var': "ENTROPY_PROJECT_TAG",
    }

    _cmd_map = {
        'env_update_cmd': "/usr/sbin/env-update",
        'ask_cmd': "--ask",
        'info_cmd': "--info",
        'remove_cmd': "-C",
        'nodeps_cmd': "--nodeps",
        'fetchonly_cmd': "--fetchonly",
        'buildonly_cmd': "--buildonly",
        'oneshot_cmd': "--oneshot",
        'pretend_cmd': "--pretend",
        'verbose_cmd': "--verbose",
        'nocolor_cmd': "--color=n",
        'source_profile_cmd': "source /etc/profile",
        'exec_cmd': "/usr/bin/emerge",
    }

    _package_phases_map = {
        'setup': 'setup',
        'preinstall': 'preinst',
        'postinstall': 'postinst',
        'preremove': 'prerm',
        'postremove': 'postrm',
        'configure': 'config',
    }

    _config_files_map = {
        'global_make_conf': "/etc/make.conf",
        'global_make_conf_new': "/etc/portage/make.conf",
        'global_package_keywords': "/etc/portage/package.keywords",
        'global_package_use': "/etc/portage/package.use",
        'global_package_mask': "/etc/portage/package.mask",
        'global_package_unmask': "/etc/portage/package.unmask",
        'global_make_profile': "/etc/make.profile",
    }

    PLUGIN_API_VERSION = 12

    SUPPORTED_MATCH_TYPES = [
        "bestmatch-visible", "cp-list", "list-visible", "match-all",
        "match-visible", "minimum-all", "minimum-visible"
    ]

    CACHE = {
        'vartree': {},
        'binarytree': {},
        'config': {},
        'portagetree': {},
    }

    IS_DEFAULT = True
    PLUGIN_NAME = 'portage'
    ENV_FILE_COMP = "environment.bz2"
    EBUILD_EXT = ".ebuild"
    KERNEL_CATEGORY = "sys-kernel"
    _PORTAGE_ENTROPY_PACKAGE_NAME = "sys-apps/portage"
    _ACCEPT_PROPERTIES = const_convert_to_unicode("* -interactive")

    ENV_DIRS = set(["/etc/env.d"])

    if "/usr/lib/gentoolkit/pym" not in sys.path:
        sys.path.append("/usr/lib/gentoolkit/pym")

    # Portage now installs its modules into site-packages.
    # However, if it's compiled only for py2.7, running
    # this code with py3.3 won't work. So, add the real
    # portage/pym path.
    if "/usr/lib/portage/pym" not in sys.path:
        sys.path.append("/usr/lib/portage/pym")

    def init_singleton(self, output_interface):

        self.__output = output_interface
        self.__entropy_repository_treeupdate_digests = {}

        # setup licenses according to Gentoo bug #234300 comment 9.
        # EAPI < 3.
        os.environ["ACCEPT_PROPERTIES"] = self._ACCEPT_PROPERTIES

        # setup color status
        if not getcolor():
            # Entropy color output is disable, disable Portage
            os.environ['NOCOLOR'] = "yes"
        elif "NOCOLOR" in os.environ:
            del os.environ['NOCOLOR']

        # importing portage stuff
        import portage.const
        # Portage 2.1.9x, enable package sets for overlay.
        portage.const._ENABLE_SET_CONFIG = True
        import portage
        import portage.util
        self._portage = portage

    def _reload_modules(self):

        """
        WARNING: this function reloads Portage modules in RAM
        it brutally kills the current instance by removing
        it from sys.modules and calling a new import.
        There may be resource leaks but since this can only be run
        once per "session", that's nothing to worry about.
        """
        mytxt = "%s..." % (
            brown(_("Reloading Portage modules")),
        )
        self.__output.output(
            mytxt,
            importance = 0,
            header = red("   ## ")
        )

        self.clear()

        for obj in tuple(PortagePlugin.CACHE.values()):
            obj.clear()

        port_key = "portage"
        emerge_key = "_emerge"
        # we have a portage module instance in here too
        # need to kill it
        current_module_name = __name__ + "." + port_key
        if current_module_name in sys.modules:
            del sys.modules[current_module_name]

        for key in tuple(sys.modules.keys()):
            if key.startswith(port_key):
                del sys.modules[key]
            elif key.startswith(emerge_key):
                del sys.modules[key]
        # now reimport everything

        # Portage 2.1.9x, enable package sets for overlay.
        import portage.const
        portage.const._ENABLE_SET_CONFIG = True
        import portage
        import portage.util
        # reassign portage variable, pointing to a fresh object
        self._portage = portage

    def clear(self):
        """
        Reimplemented from SpmPlugin class.
        """
        for root, tree in list(PortagePlugin.CACHE['portagetree'].items()):
            dbapi = tree.dbapi

            dbapi.melt()
            dbapi._aux_cache.clear()
            dbapi.clear_caches()
            tree.dbapi = portage.dbapi.porttree.portdbapi(
                mysettings=dbapi.settings)

        for root, tree in list(PortagePlugin.CACHE['vartree'].items()):
            dbapi = tree.dbapi
            if hasattr(dbapi, "_clear_cache"):
                dbapi._clear_cache()

        gc.collect()

    @staticmethod
    def get_package_groups():
        """
        Return package groups available metadata (Spm categories are grouped
        into macro categories called "groups").
        """
        return PortagePackageGroups()

    @staticmethod
    def binary_packages_extensions():
        """
        Reimplemented from SpmPlugin class.
        """
        return ["tbz2"]

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
            "repository", "RESTRICT", "SLOT", "USE"
        ]

    def get_cache_directory(self, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if root is None:
            root = etpConst['systemroot'] + os.path.sep
        cache_path = self._portage.const.CACHE_PATH.lstrip(os.path.sep)
        return os.path.join(root, cache_path)

    def get_package_metadata(self, package, key):
        """
        Reimplemented from SpmPlugin class.
        """
        return self._portage.portdb.aux_get(package, [key])[0]

    def get_package_changelog(self, package):
        """
        Reimplemented from SpmPlugin class.
        """
        ebuild_path = self.get_package_build_script_path(package)
        if isinstance(ebuild_path, const_get_stringtype()):
            clog_path = os.path.join(os.path.dirname(ebuild_path), "ChangeLog")
            try:
                with open(clog_path, "rb") as clog_f:
                    return clog_f.read()
            except (OSError, IOError) as err:
                if err.errno != errno.ENOENT:
                    raise

    def get_package_build_script_path(self, package):
        """
        Reimplemented from SpmPlugin class.
        """
        return self._portage.portdb.findname(package)

    def get_installed_package_build_script_path(self, package, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        return os.path.join(self._get_vdb_path(root = root), package,
            package.split("/")[-1] + PortagePlugin.EBUILD_EXT)

    def get_installed_package_metadata(self, package, key, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        data = self._get_installed_package_metadata(
            package, key, root = root)
        if key == "SLOT" and data:
            # EAPI5, strip /* from SLOT
            data = self._strip_slash_from_slot(data)
        return data

    def _get_installed_package_metadata(self, package, key, root = None):
        """
        Internal version of get_installed_package_metadata().
        This method doesn't do any automagic mangling to returned
        data.
        """
        if root is None:
            root = etpConst['systemroot'] + os.path.sep
        vartree = self._get_portage_vartree(root = root)
        try:
            return vartree.dbapi.aux_get(package, [key])[0]
        except KeyError: # make clear that we raise KeyError
            raise
        except OSError as err:
            raise KeyError("Original OSError: %s" % (err,))

    def get_system_packages(self):
        """
        Reimplemented from SpmPlugin class.
        """
        system = []
        for package in self._portage.settings.packages:
            pkgs = self.match_installed_package(package, match_all = True)
            system.extend(pkgs)
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
        portdir = self._portage.settings['PORTDIR']
        myfile = os.path.join(portdir, category, "metadata.xml")
        if const_file_readable(myfile):
            doc = minidom.parse(myfile)
            longdescs = doc.getElementsByTagName("longdescription")
            for longdesc in longdescs:
                data[longdesc.getAttribute("lang").strip()] = \
                    ' '.join([x.strip() for x in \
                        longdesc.firstChild.data.strip().split("\n")])
        return data

    def _get_glsa(self):
        try:
            import glsa
            glsa_mod = glsa
        except ImportError:
            glsa_mod = None
        return glsa_mod

    def get_security_packages(self, security_property):
        """
        Reimplemented from SpmPlugin class.
        """
        _glsa = self._get_glsa()
        if _glsa is None:
            return []
        if security_property not in ['new', 'all', 'affected']:
            return []

        glsaconfig = _glsa.checkconfig(
            self._portage.config(clone=self._portage.settings))
        completelist = _glsa.get_glsa_list(
            glsaconfig["GLSA_DIR"], glsaconfig)

        glsalist = []
        if security_property == "new":

            checklist = []
            try:
                enc = etpConst['conf_encoding']
                with codecs.open(glsaconfig["CHECKFILE"], "r", encoding=enc) \
                        as check_f:
                    checklist.extend([x.strip() for x in check_f.readlines()])
            except (OSError, IOError) as err:
                if err.errno != errno.ENOENT:
                    raise
            glsalist = [x for x in completelist if x not in checklist]

        elif security_property == "all":
            glsalist = completelist

        elif security_property == "affected":

            # maybe this should be todolist instead
            for glsa_item in completelist:
                try:
                    myglsa = _glsa.Glsa(glsa_item, glsaconfig)
                except (_glsa.GlsaTypeException, _glsa.GlsaFormatException,):
                    continue

                if not myglsa.isVulnerable():
                    continue

                glsalist.append(glsa_item)

        return glsalist

    def get_security_advisory_metadata(self, advisory_id):
        """
        Reimplemented from SpmPlugin class.
        """
        _glsa = self._get_glsa()
        if _glsa is None:
            return {}

        glsaconfig = _glsa.checkconfig(
            self._portage.config(clone=self._portage.settings))
        try:
            myglsa = _glsa.Glsa(advisory_id, glsaconfig)
        except (_glsa.GlsaTypeException, _glsa.GlsaFormatException):
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
        return self._portage.settings[key]

    def get_user_installed_packages_file(self, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        world_file = self._portage.const.WORLD_FILE
        if root is None:
            root = etpConst['systemroot'] + os.path.sep
        return os.path.join(root, world_file)

    def get_merge_protected_paths(self):
        """
        Reimplemented from SpmPlugin class.
        """
        config_protect = self._portage.settings['CONFIG_PROTECT']
        return [os.path.expandvars(x) for x in config_protect.split()]

    def get_merge_protected_paths_mask(self):
        """
        Reimplemented from SpmPlugin class.
        """
        config_protect = self._portage.settings['CONFIG_PROTECT_MASK']
        return [os.path.expandvars(x) for x in config_protect.split()]

    def get_download_mirrors(self, mirror_name):
        """
        Reimplemented from SpmPlugin class.
        """
        mirrors = []
        if mirror_name in self._portage.thirdpartymirrors:
            mirrors.extend(self._portage.thirdpartymirrors[mirror_name])
        return mirrors

    def packages_repositories_metadata_update(self, actions):
        """
        Reimplemented from SpmPlugin class.
        """
        root = etpConst['systemroot'] + os.path.sep
        vartree = self._get_portage_vartree(root = root)
        move = vartree.dbapi.move_ent
        slotmove = vartree.dbapi.move_slot_ent

        def prepare_move(command):
            cmd, old, new = command
            try:
                return [
                    cmd,
                    self._portage.dep.Atom(old),
                    self._portage.dep.Atom(new)]
            except self._portage.exception.InvalidAtom:
                return None

        def prepare_slotmove(command):
            cmd, atom, old, new = command
            try:
                return [
                    cmd,
                    self._portage.dep.Atom(atom),
                    old,
                    new]
            except self._portage.exception.InvalidAtom:
                return None

        commands = []
        for action in actions:
            mytxt = "%s: %s: %s." % (
                brown(_("SPM")),
                purple(_("action")),
                blue(action),
            )
            self.__output.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = darkred(" * ")
            )

            command = action.split()
            if command[0] == "move":
                command = prepare_move(command)
                if command is None:
                    continue
                move(command)
                commands.append(command)
            elif command[0] == "slotmove":
                command = prepare_slotmove(command)
                if command is None:
                    continue
                slotmove(command)
                commands.append(command)

        mytxt = "%s: %s." % (
            brown(_("SPM")),
            purple(_("updating metadata")),
        )
        self.__output.output(
            mytxt,
            importance = 1,
            level = "warning",
            header = darkred(" * ")
        )
        vartree.dbapi.update_ents(commands)

    def match_package(self, package, match_type = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if match_type is None:
            match_type = "bestmatch-visible"
        elif match_type not in PortagePlugin.SUPPORTED_MATCH_TYPES:
            raise KeyError()
        try:
            return self._portage.portdb.xmatch(match_type, package)
        except self._portage.exception.PortageException:
            raise KeyError()

    def match_installed_package(self, package, match_all = False, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if root is None:
            root = etpConst['systemroot'] + os.path.sep

        # Portage >=2.2_alpha50 returns AmbiguousPackageName
        # if the package dependency passed is too ambiguous
        # By contract, we have to raise KeyError.
        ambiguous_pkg_name_exception = getattr(self._portage.exception,
            "AmbiguousPackageName", self._portage.exception.PortageException)
        vartree = self._get_portage_vartree(root = root)
        try:
            matches = vartree.dep_match(package) or []
        except self._portage.exception.InvalidAtom as err:
            raise KeyError(err)
        except ambiguous_pkg_name_exception as err:
            raise KeyError(err)

        if match_all:
            return matches
        elif matches:
            return matches[-1]
        return ''

    def generate_package(self, package, file_save_dir, builtin_debug = False):
        """
        Reimplemented from SpmPlugin class.
        """
        pkgcat, pkgname = package.split("/", 1)
        file_save_name = file_save_dir + os.path.sep + pkgcat + ":" + \
            pkgname
        file_save_path = file_save_name + etpConst['packagesext']

        dbdir = os.path.join(self._get_vdb_path(), pkgcat, pkgname)

        trees = self._portage.db["/"]
        vartree = trees["vartree"]
        dblnk = self._portage.dblink(pkgcat, pkgname, "/", vartree.settings,
            treetype="vartree", vartree=vartree)
        locked = False
        if etpConst['uid'] == 0:
            dblnk.lockdb()
            locked = True

        generated_package_files = []
        # store package file in temporary directory, then move
        # atomicity ftw

        tmp_fd, tmp_file = None, None
        debug_tmp_fd, debug_tmp_file = None, None
        try:
            tmp_fd, tmp_file = const_mkstemp(dir = file_save_dir,
                prefix = "entropy.spm.Portage.generate_package._tar")
            os.close(tmp_fd)
            tmp_fd = None
            # cannot use fdopen with tarfile
            tar = tarfile.open(tmp_file, mode = "w:bz2")
            debug_tar = None
            debug_tmp_file = None
            debug_file_save_path = None
            if not builtin_debug:
                # since we cannot add entropy revision yet, we at least use
                # the timestamp (md5 hashed) as part of the filename
                cur_t = time.time()
                m = hashlib.md5()
                m.update(const_convert_to_rawstring(cur_t))
                m.update(const_convert_to_rawstring(package))
                debug_file_save_path = file_save_name + "." + m.hexdigest() + \
                    etpConst['packagesdebugext']
                debug_tmp_fd, debug_tmp_file = const_mkstemp(
                    dir = file_save_dir,
                    prefix = "entropy.spm.Portage.generate_package._debug_tar")
                os.close(debug_tmp_fd)
                debug_tmp_fd = None
                debug_tar = tarfile.open(debug_tmp_file, mode = "w:bz2")

            contents = dblnk.getcontents()
            paths = sorted(contents)

            def _is_debug_path(obj):
                for debug_path in etpConst['splitdebug_dirs']:
                    if obj.startswith(debug_path):
                        return True
                return False

            debug_empty = True
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

                tar_obj = None
                if debug_tar is not None:
                    if _is_debug_path(path):
                        tar_obj = debug_tar
                        if not tarinfo.isdir():
                            debug_empty = False
                if tar_obj is None:
                    tar_obj = tar

                if stat.S_ISREG(exist.st_mode):
                    with open(path, "rb") as f:
                        tar_obj.addfile(tarinfo, f)
                else:
                    tar_obj.addfile(tarinfo)

            tar.close()
            if debug_tar is not None:
                debug_tar.close()
            # appending xpak informations
            tbz2 = xpak.tbz2(tmp_file)
            tbz2.recompose(dbdir)
            if locked:
                dblnk.unlockdb()
            # now do atomic move
            const_setup_file(tmp_file, etpConst['entropygid'], 0o664)
            os.rename(tmp_file, file_save_path)
            generated_package_files.append(file_save_path)

            if debug_tar is not None:
                if debug_empty:
                    os.remove(debug_tmp_file)
                else:
                    const_setup_file(
                        debug_tmp_file, etpConst['entropygid'], 0o664)
                    os.rename(debug_tmp_file, debug_file_save_path)
                    generated_package_files.append(debug_file_save_path)

            for package_file in generated_package_files:
                if not const_file_readable(package_file):
                    raise self.Error(
                        "Spm:generate_package %s: %s %s" % (
                            _("error"),
                            package_file,
                            _("not readable"),
                        )
                    )

            return generated_package_files

        finally:
            for fd in (tmp_fd, debug_tmp_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            for path in (tmp_file, debug_tmp_file):
                if path is not None:
                    try:
                        os.remove(path)
                    except OSError as err:
                        if err.errno != errno.ENOENT:
                            raise

    def _add_kernel_dependency_to_pkg(self, pkg_data, pkg_dir_prefix):

        # NOTE: i hate hardcoded shit, but our SPM doesn't support
        # kernel dependencies.
        kmod_pfx = "/lib/modules"
        kmox_sfx = ".ko"

        # these have to be kept in sync with kswitch
        kernels_dir = "/etc/kernels"
        release_level = "RELEASE_LEVEL"

        content = [x for x in pkg_data['content'] if x.startswith(kmod_pfx)]
        content = [x for x in content if x.endswith(kmox_sfx)]
        enc = etpConst['conf_encoding']

        # filter out hidden files
        if not content:
            return

        def read_kern_vermagic(ko_path):

            # apparently upstream is idiot 100% tested
            modinfo_path = None
            for _path in ("/sbin", "/usr/bin", "/bin"):
                modinfo_path = os.path.join(_path, "modinfo")
                if os.path.lexists(modinfo_path):
                    break
            if modinfo_path is None:
                warnings.warn("Something is wrong, no modinfo on the system")
                return

            tmp_fd, tmp_file = const_mkstemp(
                prefix="entropy.spm.portage._add_kernel_dependency_to_pkg")
            try:
                with os.fdopen(tmp_fd, "w") as tmp_fw:
                    rc = subprocess.call((modinfo_path, "-F", "vermagic",
                        ko_path), stdout = tmp_fw, stderr = tmp_fw)

                with codecs.open(tmp_file, "r", encoding=enc) as tmp_r:
                    modinfo_output = tmp_r.read().strip()
            finally:
                try:
                    os.close(tmp_fd)
                except OSError:
                    pass
                os.remove(tmp_file)

            if rc != 0:
                warnings.warn(
                    "Cannot properly guess kernel module vermagic, error" + \
                    modinfo_output)
                return

            return modinfo_output.split()[0]

        def find_kernel(vermagic):
            k_dirs = []
            try:
                k_dirs += os.listdir(kernels_dir)
            except (OSError, IOError):
                pass

            k_dirs = [os.path.join(kernels_dir, x) for x in k_dirs]
            k_dirs = [x for x in k_dirs if os.path.isdir(x)]

            for k_dir in k_dirs:
                rl_path = os.path.join(k_dir, release_level)
                if not os.path.lexists(rl_path):
                    # skip without trying to open() it.
                    continue

                level = None
                try:
                    with codecs.open(rl_path, "r", encoding = enc) as rl_f:
                        level = rl_f.read(512).strip()
                except (OSError, IOError):
                    continue

                if level != vermagic:
                    # not the vermagic we're looking for.
                    continue

                owners = self.search_paths_owners([rl_path])
                if not owners:
                    # wtf? ignore dependency then
                    continue
                atom_slot = sorted(owners.keys())[0]  # deterministic
                return atom_slot  # (atom, slot) tuple

        vermagic_cache = set()
        for item in content:

            # read vermagic
            item_pkg_path = os.path.join(pkg_dir_prefix, item[1:])
            kern_vermagic = read_kern_vermagic(item_pkg_path)
            if kern_vermagic is None:
                continue

            if kern_vermagic in vermagic_cache:
                # skip, already processed
                continue
            vermagic_cache.add(kern_vermagic)

            if not entropy.dep.is_valid_package_tag(kern_vermagic):
                # argh! wtf, this is invalid!
                continue

            # properly set package tag and slot
            pkg_data['versiontag'] = kern_vermagic
            # tweak slot, yeah
            pkg_data['slot'] = "%s,%s" % (pkg_data['slot'], kern_vermagic,)

            # now try to guess package providing that vermagic
            k_atom_slot = find_kernel(kern_vermagic)
            if k_atom_slot is None:
                # cannot bind a kernel package to this vermagic
                continue

            k_atom, _k_slot = k_atom_slot
            # yippie, kernel dep installed also for SPM
            return "=%s~-1" % (k_atom,)

    def _get_default_virtual_pkg(self, virtual_key):
        defaults = self._portage.settings.getvirtuals()[virtual_key]
        if defaults:
            return defaults[0]

    def __source_env_get_var(self, env_file, env_var):
        current_mod = sys.modules[__name__].__file__
        dirname = os.path.dirname(current_mod)
        exec_path = os.path.join(dirname, "env_sourcer.sh")
        args = [exec_path, env_file, env_var]
        tmp_fd, tmp_path = None, None
        tmp_err_fd, tmp_err_path = None, None
        raw_enc = etpConst['conf_raw_encoding']

        try:
            tmp_fd, tmp_path = const_mkstemp(
                prefix="entropy.spm.__source_env_get_var")
            tmp_err_fd, tmp_err_path = const_mkstemp(
                prefix="entropy.spm.__source_env_get_var_err")

            sts = subprocess.call(args, stdout = tmp_fd, stderr = tmp_err_fd)
            if sts != 0:
                raise IOError("cannot source %s and get %s" % (
                        env_file, env_var,))

            # this way buffers are flushed out
            os.close(tmp_fd)
            tmp_fd = None
            with codecs.open(tmp_path, "r", encoding = raw_enc) as tmp_r:
                # cut down to 1M... anything longer is just insane
                output = tmp_r.read(1024000).rstrip()

            return const_convert_to_unicode(output, enctype = raw_enc)

        finally:
            for fd in (tmp_fd, tmp_err_fd):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
            for path in (tmp_path, tmp_err_path):
                if path is not None:
                    try:
                        os.remove(path)
                    except OSError as err:
                        if err.errno != errno.ENOENT:
                            raise

    def __pkg_sources_filtering(self, sources):
        sources.discard("->")
        sources = set((x for x in sources if "/" in x))
        return sources

    @staticmethod
    def dump_package_metadata(entropy_package_path, metadata_path):
        """
        Reimplemented from SpmPlugin class.
        """
        return xpaktools.suck_xpak(entropy_package_path, metadata_path)

    @staticmethod
    def aggregate_package_metadata(entropy_package_path, metadata_path):
        """
        Reimplemented from SpmPlugin class.
        """
        return xpaktools.aggregate_xpak(entropy_package_path, metadata_path)

    def extract_package_metadata(self, package_file, license_callback = None,
        restricted_callback = None):
        """
        Reimplemented from SpmPlugin class.
        """
        data = {}
        system_settings = SystemSettings()

        # fill package name and version
        data['digest'] = entropy.tools.md5sum(package_file)
        data['signatures'] = {
            'sha1': entropy.tools.sha1(package_file),
            'sha256': entropy.tools.sha256(package_file),
            'sha512': entropy.tools.sha512(package_file),
            'gpg': None, # GPG signature will be filled later on, if enabled
        }
        data['datecreation'] = str(os.path.getmtime(package_file))
        data['size'] = str(entropy.tools.get_file_size(package_file))

        tmp_dir = const_mkdtemp(prefix="entropy.spm._extract")
        meta_dir = os.path.join(tmp_dir, "portage")
        pkg_dir = os.path.join(tmp_dir, "pkg")
        os.mkdir(meta_dir)
        os.mkdir(pkg_dir)

        # extract stuff
        xpaktools.extract_xpak(package_file, meta_dir)
        empty_content = False
        try:
            entropy.tools.uncompress_tarball(package_file,
                extract_path = pkg_dir, catch_empty = False)
        except tarfile.ReadError:
            empty_content = True

        env_bz2 = os.path.join(meta_dir, PortagePlugin.ENV_FILE_COMP)
        uncompressed_env_file = None
        if const_file_readable(env_bz2):
            # when extracting fake metadata, env_bz2 can be unavailable
            uncompressed_env_file = entropy.tools.unpack_bzip2(env_bz2)

        # package injection status always false by default
        # developer can change metadatum after this function
        data['injected'] = False
        data['branch'] = system_settings['repositories']['branch']

        portage_entries = self._extract_pkg_metadata_generate_extraction_dict()
        enc = etpConst['conf_encoding']
        for item in portage_entries:

            value = ''
            try:
                item_path = os.path.join(meta_dir,
                    portage_entries[item]['path'])
                with codecs.open(item_path, "r", encoding=enc) as item_f:
                    value = item_f.readline().strip()
            except IOError:
                if portage_entries[item]['critical']:
                    if uncompressed_env_file is None:
                        raise
                    env_var = portage_entries[item].get('env')
                    if env_var is None:
                        raise
                    value = self.__source_env_get_var(
                        uncompressed_env_file, env_var)
            data[item] = value

        # EAPI5 support
        data['slot'] = self._strip_slash_from_slot(data['slot'])

        #if not data['chost']:
        #    # stupid portage devs and virtual pkgs!
        #    # try to cope
        #    # WARNING: this can be erroneously set to currently running
        #    # system CHOST that could not match the CHOST the package was
        #    # built with
        #    data['chost'] = self._portage.settings['CHOST']

        # Entropy PMS support inside Portage.
        # This way it is possible to append Entropy-related
        # dependencies to packages, supported variables:
        # ENTROPY_RDEPEND, ENTROPY_PDEPEND, ENTROPY_DEPEND
        e_dep_lst = [
            ("ENTROPY_RDEPEND", "rdepend"),
            ("ENTROPY_PDEPEND", "pdepend"),
            ("ENTROPY_DEPEND", "depend"),
        ]
        if uncompressed_env_file is not None:
            for e_dep, dkey in e_dep_lst:
                e_xdepend = self.__source_env_get_var(
                    uncompressed_env_file, e_dep)
                if e_xdepend:
                    data[dkey] += " "
                    data[dkey] += e_xdepend

        if not data['spm_repository']: # make sure it's set to None
            data['spm_repository'] = None

        if not data['sources'] and (uncompressed_env_file is not None):
            # when extracting fake metadata, env_bz2 can be unavailable
            uncompressed_env_file = entropy.tools.unpack_bzip2(env_bz2)
            # unfortunately upstream dropped SRC_URI file support
            data['sources'] = self.__source_env_get_var(
                uncompressed_env_file, "SRC_URI")

        # workout pf
        pf_atom = os.path.join(data['category'], data['pf'])
        pkgcat, pkgname, pkgver, pkgrev = entropy.dep.catpkgsplit(
            pf_atom)
        if pkgrev != "r0":
            pkgver += "-%s" % (pkgrev,)
        data['name'] = pkgname
        data['version'] = pkgver
        # bye bye pf
        del data['pf']

        # setup spm_phases properly
        spm_defined_phases_path = os.path.join(meta_dir,
            portage_entries['spm_phases']['path'])
        if not os.path.isfile(spm_defined_phases_path):
            # force to None, because metadatum can be '', which is valid
            data['spm_phases'] = None

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
            data['keywords'].insert(0, "**")

        data['keywords'] = set(data['keywords'])

        content_file = os.path.join(meta_dir,
            PortagePlugin.xpak_entries['contents'])
        # even if pkg_dir is tweaked after this, it's fine anyway for
        # packages emerge with -B, because for those, we also get the
        # full package_file (not a fake one).
        data['content'] = self._extract_pkg_metadata_content(content_file,
                package_file, pkg_dir)
        # There are packages providing no files, even if given package_file
        # is complete (meaning, it contains real file. Not a fake one, like
        # it can happen with "equo rescue spmsync", to make things quicker).
        # So, to differentiate between "complete package file with no content"
        # and "fake package file, with arbitrary content", we check
        # data['content']. If empty_content is True but data['content'] is
        # contains something, then we have a fake package_file.
        if data['content'] and empty_content:
            # fake package_file, need to tweak pkg_dir to systemroot
            pkg_dir = etpConst['systemroot'] + os.path.sep

        # at this point, pkg_dir must point to a valid "root" directory
        # because checksums have to be calculated against files being available
        # in the package. The case above (when using equo rescue spmsync) is
        # fine too.
        data['content_safety'] = self._extract_pkg_metadata_content_safety(
            data['content'], pkg_dir)
        data['disksize'] = entropy.tools.sum_file_sizes_hardlinks([
                os.path.join(pkg_dir, x) for x, y in data['content'].items() \
                    if y == "obj"])
        data['provided_libs'] = self._extract_pkg_metadata_provided_libs(
            pkg_dir, data['content'])

        needed_elf_file = os.path.join(meta_dir,
            PortagePlugin.xpak_entries['needed.elf.2'])
        needed_file = os.path.join(meta_dir,
            PortagePlugin.xpak_entries['needed'])

        if os.path.isfile(needed_elf_file):
            needed_libs = self._extract_pkg_metadata_needed_libs_elf_2(
                needed_elf_file)
            # deprecated, kept for backward compatibility
            data['needed'] = tuple(
                sorted((soname, elfc) for _x, _x, soname, elfc, _x
                       in needed_libs)
            )
            data['needed_libs'] = needed_libs
        elif os.path.isfile(needed_file):
            needed_libs = self._extract_pkg_metadata_needed_libs(
                needed_elf_file)
            # deprecated, kept for backward compatibility
            # fallback to old NEEDED file
            data['needed'] = tuple(
                sorted((soname, elfc) for _x, _x, soname, elfc, _x
                       in needed_libs)
            )
            data['needed_libs'] = needed_libs
        else:
            needed_libs = self._generate_needed_libs_elf_2(
                pkg_dir, data['content'])
            # deprecated, kept for backward compatibility
            # some PMS like pkgcore don't generate NEEDED.ELF.2
            # generate one ourselves if possible. May generate
            # a slighly different (more complete?) content.
            data['needed'] = tuple(
                sorted((soname, elfc) for _x, _x, soname, elfc, _x
                       in needed_libs)
            )
            data['needed_libs'] = needed_libs

        # [][][] Kernel dependent packages hook [][][]
        data['versiontag'] = ''
        kern_dep_key = None

        if data['category'] != PortagePlugin.KERNEL_CATEGORY:
            kern_dep_key = self._add_kernel_dependency_to_pkg(data, pkg_dir)
        elif uncompressed_env_file is not None:
            # we may have packages in sys-kernel category holding
            # kernel modules without being kernels
            # ETYPE is a typical environment variable used by kernel
            # sources and binaries (and firmwares).
            # If it's set, it means that this is a kernel ebuild.
            etype = self.__source_env_get_var(
                uncompressed_env_file, "ETYPE")
            if not etype:
                kern_dep_key = self._add_kernel_dependency_to_pkg(data, pkg_dir)

        file_ext = PortagePlugin.EBUILD_EXT
        ebuilds_in_path = [x for x in os.listdir(meta_dir) if \
            x.endswith(file_ext)]

        if not data['versiontag'] and ebuilds_in_path:
            # has the user specified a custom package tag inside the ebuild
            ebuild_path = os.path.join(meta_dir, ebuilds_in_path[0])
            data['versiontag'] = self._extract_pkg_metadata_ebuild_entropy_tag(
                ebuild_path)

        data['trigger'] = const_convert_to_rawstring("")
        triggers_dir = SpmPlugin.external_triggers_dir()
        trigger_file = os.path.join(triggers_dir, data['category'],
            data['name'], etpConst['triggername'])

        try:
            with open(trigger_file, "rb") as trig_f:
                data['trigger'] = trig_f.read()
        except (OSError, IOError) as err:
            if err.errno != errno.ENOENT:
                raise

        # Get Spm ChangeLog
        pkgatom = "%s/%s-%s" % (data['category'], data['name'],
            data['version'],)
        try:
            changelog = self.get_package_changelog(pkgatom)
            if changelog is not None:
                data['changelog'] = const_convert_to_unicode(changelog)
            else:
                data['changelog'] = None
        except (UnicodeEncodeError, UnicodeDecodeError,) as e:
            sys.stderr.write("%s: %s, %s\n" % (
                "changelog string conversion error", e,
                package_file,)
            )
            data['changelog'] = None
        except:
            data['changelog'] = None

        if not data['eapi']:
            data['eapi'] = None
        portage_metadata = self._calculate_dependencies(
            data['iuse'], data['use'], data['license'], data['depend'],
            data['rdepend'], data['pdepend'], data['provide'], data['sources'],
            data['eapi']
        )

        data['license'] = " ".join(portage_metadata['LICENSE'])
        data['useflags'] = []
        data['useflags'].extend(portage_metadata['ENABLED_USE'])
        # consider forced use flags always on
        data['useflags'].extend(portage_metadata['USE_FORCE'])
        for my_use in portage_metadata['DISABLED_USE']:
            data['useflags'].append("-"+my_use)

        # useflags must be a set, as returned by entropy.db.getPackageData
        data['useflags'] = set(data['useflags'])
        # sources must be a set, as returned by entropy.db.getPackageData
        data['sources'] = set(portage_metadata['SRC_URI'])
        data['sources'] = self.__pkg_sources_filtering(data['sources'])

        data['pkg_dependencies'] = set()

        dep_keys = {
            "RDEPEND": etpConst['dependency_type_ids']['rdepend_id'],
            "PDEPEND": etpConst['dependency_type_ids']['pdepend_id'],
            "DEPEND": etpConst['dependency_type_ids']['bdepend_id'],
        }
        dep_duplicates = set()
        for dep_key, dep_val in dep_keys.items():
            for x in portage_metadata[dep_key]:
                if x.startswith("!") or (x in ("(", "||", ")", "")):
                    continue

                if (x, dep_val) in dep_duplicates:
                    continue
                dep_duplicates.add((x, dep_val))

                data['pkg_dependencies'].add((x, dep_val))

        dep_duplicates.clear()

        data['conflicts'] = [x.replace("!", "") for x in \
            portage_metadata['RDEPEND'] + \
            portage_metadata['PDEPEND'] if \
            x.startswith("!") and not x in ("(", "||", ")", "")]

        if kern_dep_key is not None:
            kern_dep_id = etpConst['dependency_type_ids']['rdepend_id']
            data['pkg_dependencies'].add((kern_dep_key, kern_dep_id))

        # force a tuple object
        data['pkg_dependencies'] = tuple(data['pkg_dependencies'])

        # conflicts must be a set, which is what is returned
        # by entropy.db.getPackageData
        data['conflicts'] = set(data['conflicts'])

        # old-style virtual support, we need to check if this pkg provides
        # PROVIDE metadatum which points to itself, if so, this is the
        # default
        del data['provide']
        provide_extended = set()
        myself_provide_key = data['category'] + "/" + data['name']
        for provide_key in set(portage_metadata['PROVIDE']):
            is_provide_default = 0
            try:
                profile_default_provide = self._get_default_virtual_pkg(
                    provide_key)
            except KeyError:
                profile_default_provide = 1 # cant be this

            if profile_default_provide == myself_provide_key:
                is_provide_default = 1

            provide_extended.add((provide_key, is_provide_default,))

        # this actually changes provide format
        data['provide_extended'] = provide_extended

        # Get License text if possible
        # NOTE: this is sucky, because Portage XPAK metadata doesn't contain
        # license text, and we need to rely on PORTDIR, which is very bad
        data['licensedata'] = self._extract_pkg_metadata_license_data(
            data['spm_repository'], data['license'])

        data['desktop_mime'], data['provided_mime'] = \
            self._extract_pkg_metadata_desktop_mime(
                pkg_dir, data['content'])

        data['mirrorlinks'] = self._extract_pkg_metadata_mirror_links(
            data['sources'])

        # write only if it's a systempackage
        data['systempackage'] = False
        system_packages = [entropy.dep.dep_getkey(x) for x in \
            self.get_system_packages()]
        if data['category'] + "/" + data['name'] in system_packages:
            data['systempackage'] = True

        # write only if it's a systempackage
        data['config_protect'] = ' '.join(self.get_merge_protected_paths())
        data['config_protect_mask'] = ' '.join(
            self.get_merge_protected_paths_mask())

        # etpapi must be int, as returned by entropy.db.getPackageData
        data['etpapi'] = int(etpConst['etpapi'])

        # prepare download URL string, check licenses
        nonfree = False
        restricted = False
        if license_callback is not None:
            nonfree = not license_callback(data)
        if restricted_callback is not None:
            restricted = restricted_callback(data)
        data['download'] = entropy.tools.create_package_dirpath(data['branch'],
            nonfree = nonfree, restricted = restricted)
        data['download'] = os.path.join(data['download'],
            entropy.dep.create_package_relative_path(
                data['category'], data['name'], data['version'],
                data['versiontag'],
                sha1=data['signatures']['sha1']))

        # removing temporary directory
        shutil.rmtree(tmp_dir, True)

        # clear unused metadata
        del data['use'], data['iuse'], data['depend'], data['pdepend'], \
            data['rdepend'], data['eapi']

        return data

    def get_installed_package_content(self, package, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if root is None:
            root = etpConst['systemroot'] + os.path.sep

        cat, pkgv = package.split("/")
        return sorted(self._portage.dblink(cat, pkgv, root,
            self._portage.settings).getcontents())

    def get_packages(self, categories = None, filter_reinstalls = True):
        """
        Reimplemented from SpmPlugin class.
        """
        if categories is None:
            categories = []

        root = etpConst['systemroot'] + os.path.sep
        mysettings = self._get_portage_config(os.path.sep, root)
        portdb = self._get_portage_portagetree(root).dbapi

        cps = portdb.cp_all()
        visibles = set()
        for cp in cps:
            if categories:
                if cp.split("/")[0] not in categories:
                    continue

            # get slots
            slots = set()
            atoms = self.match_package(cp, match_type = "match-visible")
            if atoms:
                for atom in atoms:
                    slot = portdb.aux_get(atom, ["SLOT"])[0]
                    slot = self._strip_slash_from_slot(slot)
                    slots.add(slot)
                for slot in slots:
                    visibles.add(cp + ":" + slot)

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

    def compile_packages(self, packages, stdin = None, stdout = None,
        stderr = None, environ = None, pid_write_func = None,
        pretend = False, verbose = False, fetch_only = False,
        build_only = False, no_dependencies = False,
        ask = False, coloured_output = False, oneshot = False):

        cmd = [PortagePlugin._cmd_map['exec_cmd']]
        if pretend:
            cmd.append(PortagePlugin._cmd_map['pretend_cmd'])
        if verbose:
            cmd.append(PortagePlugin._cmd_map['verbose_cmd'])
        if ask:
            cmd.append(PortagePlugin._cmd_map['ask_cmd'])
        if oneshot:
            cmd.append(PortagePlugin._cmd_map['oneshot_cmd'])
        if not coloured_output:
            cmd.append(PortagePlugin._cmd_map['nocolor_cmd'])
        if fetch_only:
            cmd.append(PortagePlugin._cmd_map['fetchonly_cmd'])
        if build_only:
            cmd.append(PortagePlugin._cmd_map['buildonly_cmd'])
        if no_dependencies:
            cmd.append(PortagePlugin._cmd_map['nodeps_cmd'])

        cmd.extend(packages)
        cmd_string = """\
        %s && %s && %s
        """ % (PortagePlugin._cmd_map['env_update_cmd'],
            PortagePlugin._cmd_map['source_profile_cmd'],
            ' '.join(cmd)
        )

        env = os.environ.copy()
        if environ is not None:
            env.update(environ)

        proc = subprocess.Popen(cmd_string, stdout = stdout, stderr = stderr,
            stdin = stdin, env = env, shell = True)
        if pid_write_func is not None:
            pid_write_func(proc.pid)
        return proc.wait()

    def environment_update(self):
        args = (PortagePlugin._cmd_map['env_update_cmd'],)
        try:
            # inherit stdin, stderr, stdout from parent
            proc = subprocess.Popen(args, stdout = sys.stdout,
                stderr = sys.stderr, stdin = sys.stdin)
        except OSError as err:
            if err.errno != errno.ENOENT:
                raise
            return
        return proc.wait()

    def print_build_environment_info(self, stdin = None, stdout = None,
        stderr = None, environ = None, pid_write_func = None,
        coloured_output = False):

        cmd = [PortagePlugin._cmd_map['exec_cmd'],
            PortagePlugin._cmd_map['info_cmd']]
        if not coloured_output:
            cmd.append(PortagePlugin._cmd_map['nocolor_cmd'])

        cmd_string = """\
        %s && %s && %s
        """ % (PortagePlugin._cmd_map['env_update_cmd'],
            PortagePlugin._cmd_map['source_profile_cmd'],
            ' '.join(cmd)
        )

        env = os.environ.copy()
        if environ is not None:
            env.update(environ)

        proc = subprocess.Popen(cmd_string, stdout = stdout, stderr = stderr,
            stdin = stdin, env = env, shell = True)
        if pid_write_func is not None:
            pid_write_func(proc.pid)
        return proc.wait()

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

        return list(filter(catfilter, packages))

    def get_package_sets(self, builtin_sets):
        """
        Reimplemented from SpmPlugin class.
        """
        config = self._get_set_config()
        if config == None:
            return {}

        mysets = config.getSets()
        if not builtin_sets:
            # attention, this is sensible to Portage API changes
            files = self._get_portage_sets_files_object()
            if files is not None:
                static_file_class = files.StaticFileSet
                # filter out Portage-generated sets object, those not being
                # an instance of portage._sets.files.StaticFileSet
                for key, obj in tuple(mysets.items()):
                    if not isinstance(obj, static_file_class):
                        mysets.pop(key)

        set_data = {}
        for k, obj in mysets.items():
            pset = obj.getAtoms()
            pset |= obj.getNonAtoms()
            set_data[k] = pset
        return set_data

    def convert_from_entropy_package_name(self, entropy_package_name):
        """
        Reimplemented from SpmPlugin class.
        """
        spm_name = entropy.dep.remove_tag(entropy_package_name)
        spm_name = entropy.dep.remove_entropy_revision(spm_name)
        return spm_name

    def assign_uid_to_installed_package(self, package, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        if root is None:
            root = etpConst['systemroot'] + os.path.sep

        with self._PortageVdbLocker(self, root = root):

            vartree = self._get_portage_vartree(root)
            dbbuild = self.get_installed_package_build_script_path(package,
                root = root)

            counter_dir = os.path.dirname(dbbuild)
            counter_name = PortagePlugin.xpak_entries['counter']
            counter_path = os.path.join(counter_dir, counter_name)

            if not const_dir_readable(counter_dir):
                raise self.Error("SPM package directory not found")

            enc = etpConst['conf_encoding']
            try:
                with codecs.open(counter_path, "w", encoding=enc) as count_f:
                    new_counter = vartree.dbapi.counter_tick(
                        root, mycpv = package)
                    count_f.write(const_convert_to_unicode(new_counter))
            finally:
                self._bump_vartree_mtime(package, root = root)

        return new_counter

    def resolve_package_uid(self, entropy_repository,
        entropy_repository_package_id):
        """
        Reimplemented from SpmPlugin class.
        """
        counter_path = PortagePlugin.xpak_entries['counter']
        entropy_atom = entropy_repository.retrieveAtom(
            entropy_repository_package_id)

        spm_name = self.convert_from_entropy_package_name(entropy_atom)
        build_path = self.get_installed_package_build_script_path(spm_name)
        atom_counter_path = os.path.join(os.path.dirname(build_path),
            counter_path)

        enc = etpConst['conf_encoding']
        try:
            with codecs.open(atom_counter_path, "r", encoding=enc) as f:
                counter = int(f.readline().strip())
        except (OSError, IOError) as err:
            if err.errno == errno.ENOENT:
                return None
            raise
        except ValueError:
            raise self.Error("invalid Unique Identifier found")
        except Exception as e:
            raise self.Error("General SPM Error: %s" % (repr(e),))

        return counter

    def resolve_spm_package_uid(self, package):
        """
        Reimplemented from SpmPlugin class.
        """
        try:
            return int(self.get_installed_package_metadata(package, "COUNTER"))
        except ValueError:
            raise KeyError("invalid counter")

    def search_paths_owners(self, paths, exact_match = True):
        """
        Reimplemented from SpmPlugin class.
        """
        if not isinstance(paths, (list, set, frozenset, dict, tuple)):
            raise AttributeError("iterable needed")

        matches = {}
        root = etpConst['systemroot'] + os.path.sep

        # if qfile is avail, it's much faster than using Portage API
        qfile_exec = "/usr/bin/qfile"
        if os.path.lexists(qfile_exec):

            qfile_args = (qfile_exec, "-q", "-C", "-R", root,)
            if exact_match:
                qfile_args += ("-e",)

            rc = 0
            for filename in paths:

                proc = subprocess.Popen(qfile_args + (filename,),
                    stdout = subprocess.PIPE)
                rc = proc.wait()
                if rc != 0:
                    # wtf?, fallback to old way
                    proc.stdout.close()
                    matches.clear()
                    break

                pkgs = set([x.strip() for x in proc.stdout.readlines()])
                for pkg in pkgs:
                    slot = self.get_installed_package_metadata(pkg, "SLOT")
                    obj = matches.setdefault((pkg, slot,), set())
                    obj.add(filename)

                proc.stdout.close()

            if rc == 0:
                return matches

        mytree = self._get_portage_vartree(root)
        packages = mytree.dbapi.cpv_all()

        for package in packages:
            cat, pkgv = package.split("/")
            content = self._portage.dblink(cat, pkgv, root,
                self._portage.settings).getcontents()

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

    def _reload_portage_if_required(self, phase, package_metadata):
        # filter out unwanted phases
        if phase not in ("postrm", "postinst"):
            return
        category, name = package_metadata['category'], package_metadata['name']
        key = category + "/" + name
        # reload portage modules only if we're dealing with sys-apps/portage
        if key == PortagePlugin._PORTAGE_ENTROPY_PACKAGE_NAME:
            self._reload_modules()

    def _portage_doebuild(self, myebuild, action, action_metadata, mydo,
        tree, cpv, portage_tmpdir = None, licenses = None):

        if licenses is None:
            licenses = []

        root = etpConst['systemroot'] + os.path.sep

        # old way to avoid loop of deaths for entropy portage hooks
        os.environ["SKIP_EQUO_SYNC"] = "1"

        # load metadata
        myebuilddir = os.path.dirname(myebuild)
        keys = sorted(self._portage.auxdbkeys) + ["repository"]
        metadata = {}
        enc = etpConst['conf_encoding']

        for key in keys:
            mykeypath = os.path.join(myebuilddir, key)
            try:
                with codecs.open(mykeypath, "r", encoding=enc) as f:
                    metadata[key] = f.readline().strip()
            except (OSError, IOError) as err:
                if err.errno != errno.ENOENT:
                    raise

        ### END SETUP ENVIRONMENT

        # find config
        mysettings = self._get_portage_config(os.path.sep, root)
        mysettings['EBUILD_PHASE'] = mydo
        mysettings['EMERGE_FROM'] = "binary"

        # Always turn off FEATURES=noauto as it breaks the phase
        # execution. This has been also fixed in Portage in
        # commit 10017a62b227558ed446419a2133c1584676c01c
        mysettings.features.discard("noauto")

        # Turn off ccache if it's set, pointless and might
        # generate warnings
        mysettings.features.discard("ccache")

        # EAPI >=3
        mysettings["ACCEPT_LICENSE"] = const_convert_to_unicode(
            " ".join(licenses))
        mysettings.backup_changes("ACCEPT_LICENSE")
        mysettings.regenerate()

        mysettings['EAPI'] = "0"
        if 'EAPI' in metadata:
            mysettings['EAPI'] = metadata['EAPI']

        # workaround for scripts asking for user intervention
        mysettings['ROOT'] = root
        mysettings['CD_ROOT'] = "/tmp"

        mysettings.backup_changes("EAPI")
        mysettings.backup_changes("EBUILD_PHASE")
        mysettings.backup_changes("EMERGE_FROM")
        mysettings.backup_changes("ROOT")
        mysettings.backup_changes("CD_ROOT")

        try: # this is a >portage-2.1.4_rc11 feature
            env_wl = set(mysettings._environ_whitelist)
            # put our vars into whitelist
            env_wl.add("SKIP_EQUO_SYNC")
            env_wl.add("ACCEPT_LICENSE")
            env_wl.add("CD_ROOT")
            env_wl.add("ROOT")
            mysettings._environ_whitelist = frozenset(env_wl)
        except (AttributeError,):
            self.log_message(entropy.tools.get_traceback())

        portage_tmpdir_created = False # for pkg_postrm, pkg_prerm

        if portage_tmpdir is None:
            # /tmp might be mounted using tmpfs, noexec, etc
            portage_tmpdir = const_mkdtemp(prefix="tmpdir_doebuild")
            portage_tmpdir_created = True
        elif not os.path.isdir(portage_tmpdir):
            os.makedirs(portage_tmpdir, 0o744)
            const_setup_perms(portage_tmpdir, etpConst['entropygid'],
                recursion = False)

        if portage_tmpdir:
            mysettings['PORTAGE_TMPDIR'] = str(portage_tmpdir)
            mysettings.backup_changes("PORTAGE_TMPDIR")

        # make sure that PORTDIR exists
        portdir = mysettings["PORTDIR"]
        try:
            os.makedirs(os.path.join(portdir, "licenses"), 0o755)
        except OSError:
            # best effort
            pass

        cpv = str(cpv)
        mydbapi = self._portage.fakedbapi(settings=mysettings)

        mydbapi.cpv_inject(cpv, metadata = metadata)
        mysettings.setcpv(cpv, mydb = mydbapi)

        # This is part of EAPI=4, but Portage doesn't set REPLACED_BY_VERSION
        # if not inside dblink.treewalk(). So, we must set it here
        if (action == "install") and (action_metadata is not None) and \
            (mydo in ("prerm", "postrm")):
            # NOTE: this is done AFTER setcpv to avoid having it to reset
            # this setting. It is better to NOT backup this variable
            mysettings["REPLACED_BY_VERSION"] = action_metadata['version']

        # cached vartree class
        vartree = self._get_portage_vartree(root = root)

        if const_debug_enabled():
            self.__output.output(
                "PortagePlugin<_portage_doebuild>, env: %s" % (
                    locals(),),
                importance = 0,
                header = ""
            )

        with LogFile(level = SystemSettings()['system']['log_level'],
            filename = etpConst['entropylogfile'], header = "[spm]") as logger:

            oldsysstdout = sys.stdout
            oldsysstderr = sys.stderr
            splitter_out = None
            splitter_err = None
            try:
                if is_mute():
                    tmp_fd, tmp_file = const_mkstemp(
                        prefix="entropy.spm.portage._portage_doebuild")
                    tmp_fw = os.fdopen(tmp_fd, "w")
                    fd_pipes = {
                        0: sys.stdin.fileno(),
                        1: tmp_fw.fileno(),
                        2: tmp_fw.fileno(),
                    }
                else:
                    splitter_out = StdoutSplitter(
                        mydo, logger, sys.stdout)
                    splitter_err = StdoutSplitter(
                        mydo, logger, sys.stderr)
                    fd_pipes = {
                        0: sys.stdin.fileno(),
                        1: splitter_out.fileno(),
                        2: splitter_err.fileno(),
                    }

                rc = self._portage.doebuild(
                    str(myebuild),
                    str(mydo),
                    settings = mysettings,
                    tree = tree,
                    mydbapi = mydbapi,
                    vartree = vartree,
                    debug = const_debug_enabled(),
                    fd_pipes = fd_pipes,
                    use_cache = 0
                )

            except self._portage.exception.UnsupportedAPIException as err:
                logger.write(entropy.tools.get_traceback())
                raise self.OutdatedPhaseError(err)

            except Exception as err:
                logger.write(entropy.tools.get_traceback())
                raise self.PhaseError(err)

            finally:
                sys.stdout = oldsysstdout
                sys.stderr = oldsysstderr
                if splitter_out is not None:
                    try:
                        splitter_out.close()
                    except OSError:
                        pass
                if splitter_err is not None:
                    try:
                        splitter_err.close()
                    except OSError:
                        pass
                if is_mute():
                    tmp_fw.flush()
                    tmp_fw.close()
                    try:
                        os.remove(tmp_file)
                    except OSError:
                        pass

                if portage_tmpdir_created:
                    shutil.rmtree(portage_tmpdir, True)

                del mydbapi
                del metadata
                del keys

        if rc != 0:
            raise self.PhaseFailure(
                "Phase terminated with exit status: %d" % (rc,),
                rc)

    @staticmethod
    def _pkg_compose_atom(package_metadata):
        return package_metadata['category'] + "/" + \
                package_metadata['name'] + "-" + package_metadata['version']

    @staticmethod
    def _pkg_compose_xpak_ebuild(package_metadata):
        package = PortagePlugin._pkg_compose_atom(package_metadata)
        return os.path.join(package_metadata['xpakdir'],
            os.path.basename(package) + PortagePlugin.EBUILD_EXT)

    def _pkg_remove_overlayed_ebuild(self, moved_ebuild):

        mydir = os.path.dirname(moved_ebuild)
        shutil.rmtree(mydir, True)
        mydir = os.path.dirname(mydir)
        content = os.listdir(mydir)
        while not content:
            try:
                os.rmdir(mydir)
            except OSError:
                # cannot remove further
                break
            mydir = os.path.dirname(mydir)
            content = os.listdir(mydir)

    def _pkg_remove_ebuild_env_setup_hook(self, ebuild):

        ebuild_path = os.path.dirname(ebuild)

        myroot = os.path.sep
        if etpConst['systemroot']:
            myroot = etpConst['systemroot'] + os.path.sep

        # we need to fix ROOT= if it's set inside environment
        bz2envfile = os.path.join(ebuild_path, PortagePlugin.ENV_FILE_COMP)
        if os.path.isfile(bz2envfile) and os.path.isdir(myroot):
            envfile = entropy.tools.unpack_bzip2(bz2envfile)
            bzf = bz2.BZ2File(bz2envfile, "w")
            with open(envfile, "rb") as f:
                line = f.readline()
                root_tag = const_convert_to_rawstring("ROOT=")
                while line:
                    if line.startswith(root_tag):
                        line = const_convert_to_rawstring(
                            "ROOT=%s\n" % (myroot,))
                    bzf.write(line)
                    line = f.readline()
            bzf.close()
            os.remove(envfile)

    def _pkg_remove_setup_ebuild_env(self, myebuild, portage_atom):

        ebuild_dir = os.path.dirname(myebuild)
        ebuild_file = os.path.basename(myebuild)
        moved_ebuild = None

        # copy the whole directory in a safe place
        dest_dir = os.path.join(etpConst['entropyunpackdir'],
            "vardb/" + portage_atom)
        if os.path.exists(dest_dir):
            if os.path.isdir(dest_dir):
                shutil.rmtree(dest_dir, True)
            elif os.path.isfile(dest_dir) or os.path.islink(dest_dir):
                os.remove(dest_dir)

        os.makedirs(dest_dir)
        items = os.listdir(ebuild_dir)
        for item in items:
            myfrom = os.path.join(ebuild_dir, item)
            myto = os.path.join(dest_dir, item)
            if const_file_readable(myfrom):
                # make sure it is readable before copying
                shutil.copy2(myfrom, myto)

        newmyebuild = os.path.join(dest_dir, ebuild_file)
        if os.path.isfile(newmyebuild):
            myebuild = newmyebuild
            moved_ebuild = myebuild
            self._pkg_remove_ebuild_env_setup_hook(myebuild)

        return myebuild, moved_ebuild

    def _pkg_setup(self, action_name, action_metadata, package_metadata):

        package = PortagePlugin._pkg_compose_atom(package_metadata)
        env_file = os.path.join(package_metadata['unpackdir'], "portage",
            package, "temp/environment")

        if os.path.isfile(env_file):
            # setup phase already called
            return

        ebuild = PortagePlugin._pkg_compose_xpak_ebuild(package_metadata)
        # is ebuild available ?
        if not const_file_readable(ebuild):
            self.log_message(
                "[SETUP] ATTENTION Cannot properly run SPM setup"
                " phase for %s. Ebuild path: %s not found." % (
                    package, ebuild,)
            )
            raise self.PhaseFailure(
                "Ebuild not found at path: %s" % (
                    ebuild,), 1)

        try:
            self._portage_doebuild(
                ebuild, action_name, action_metadata,
                "setup", "bintree", package,
                portage_tmpdir = package_metadata['unpackdir'],
                licenses = package_metadata.get('accept_license'))

        except self.PhaseError:
            # by contract, this exception must be raised.
            raise

        except self.PhaseFailure:
            # and this as well must be raised.
            raise

        except Exception as err:
            entropy.tools.print_traceback()
            raise self.PhaseFailure("%s" % (err,), 1)

    def _pkg_fooinst(self, action_metadata, package_metadata, action_name,
        phase):

        package = PortagePlugin._pkg_compose_atom(package_metadata)
        ebuild = PortagePlugin._pkg_compose_xpak_ebuild(package_metadata)

        # is ebuild available ?
        if not const_file_readable(ebuild):
            self.log_message(
                "[PRE] ATTENTION Cannot properly run SPM %s"
                " phase for %s. Ebuild path: %s not found." % (
                    phase, package, ebuild,)
            )
            raise self.PhaseFailure(
                "Ebuild not found at path: %s" % (
                    ebuild,), 1)

        self._pkg_setup(action_name, action_metadata, package_metadata)

        try:
            self._portage_doebuild(
                ebuild, action_name, action_metadata,
                phase, "bintree", package,
                portage_tmpdir = package_metadata['unpackdir'],
                licenses = package_metadata.get('accept_license'))

        except self.PhaseError as err:
            # by contract, this exception must be raised.
            raise

        except self.PhaseFailure:
            # and this as well must be raised.
            raise

        except Exception as err:
            entropy.tools.print_traceback()
            raise self.PhaseFailure("%s" % (err,), 1)

        finally:
            self._reload_portage_if_required(phase, package_metadata)

    def _pkg_foorm(self, action_metadata, package_metadata, action_name, phase):

        rc = 0
        moved_ebuild = None
        package = PortagePlugin._pkg_compose_atom(package_metadata)
        ebuild = self.get_installed_package_build_script_path(package)

        if not os.path.isfile(ebuild):
            return

        try:
            ebuild, moved_ebuild = self._pkg_remove_setup_ebuild_env(
                ebuild, package)

        except EOFError as err:
            # stuff on system is broken, ignore it
            entropy.tools.print_traceback()
            err_msg = "Ebuild: pkg_%s() failed, EOFError: %s - ignoring" % (
                phase, err)
            self.__output.output(
                err_msg,
                importance = 1,
                level = "warning",
                header = red("   ## ")
            )
            raise self.PhaseFailure(
                "Phase failed with EOFError", 1)

        except OSError as err:
            # this means something really bad
            # but for now we just push out a warning
            entropy.tools.print_traceback()
            err_msg = "Ebuild: pkg_%s() failed, OSError: %s - ignoring" % (
                phase, err)
            self.__output.output(
                err_msg,
                importance = 1,
                level = "warning",
                header = red("   ## ")
            )
            raise self.PhaseFailure(
                "Phase failed with OSError", 1)

        except ImportError as err:
            # stuff on system is broken, ignore it
            entropy.tools.print_traceback()
            err_msg = "Ebuild: pkg_%s() failed, ImportError: %s - ignoring" % (
                phase, err)
            self.__output.output(
                err_msg,
                importance = 1,
                level = "warning",
                header = red("   ## ")
            )
            raise self.PhaseFailure(
                "Phase failed with ImportError", 1)

        work_dir = os.path.join(etpConst['entropyunpackdir'],
            package.replace("/", "_"))

        try:
            self._reload_portage_if_required(phase, package_metadata)

            self._portage_doebuild(
                ebuild, action_name, action_metadata,
                phase, "bintree", package, portage_tmpdir = work_dir,
                licenses = package_metadata.get('accept_license'))

        except self.PhaseError as err:
            # by contract, this exception must be raised.
            raise

        except self.PhaseFailure:
            # and this as well must be raised.
            raise

        except Exception as err:
            entropy.tools.print_traceback()
            raise self.PhaseFailure("%s" % (err,), 1)

        finally:
            if os.path.isdir(work_dir):
                shutil.rmtree(work_dir, True)

        if moved_ebuild is not None:
            if os.path.isfile(moved_ebuild):
                self._pkg_remove_overlayed_ebuild(moved_ebuild)

    def _pkg_preinst(self, action_name, action_metadata, package_metadata):
        return self._pkg_fooinst(action_metadata, package_metadata,
            action_name, "preinst")

    def _pkg_postinst(self, action_name, action_metadata, package_metadata):
        return self._pkg_fooinst(action_metadata, package_metadata,
            action_name, "postinst")

    def _pkg_prerm(self, action_name, action_metadata, package_metadata):
        return self._pkg_foorm(action_metadata, package_metadata, action_name,
            "prerm")

    def _pkg_postrm(self, action_name, action_metadata, package_metadata):
        return self._pkg_foorm(action_metadata, package_metadata, action_name,
            "postrm")

    def _pkg_config(self, action_name, action_metadata, package_metadata):

        package = PortagePlugin._pkg_compose_atom(package_metadata)
        ebuild = self.get_installed_package_build_script_path(package)
        if not os.path.isfile(ebuild):
            raise self.PhaseFailure("No ebuild found: %s" % (ebuild,), 2)

        try:
            self._portage_doebuild(
                ebuild, action_name, action_metadata,
                "config", "bintree", package,
                licenses = package_metadata.get('accept_license'))

        except self.PhaseError as err:
            # by contract, this exception must be raised.
            raise

        except self.PhaseFailure:
            # and this as well must be raised.
            raise

        except Exception as err:
            entropy.tools.print_traceback()
            raise self.PhaseFailure("%s" % (err,), 1)

    def append_metadata_to_package(self, entropy_package_name, package_path):
        """
        Reimplemented from SpmPlugin class.
        """
        spm_name = self.convert_from_entropy_package_name(entropy_package_name)
        dbbuild = self.get_installed_package_build_script_path(spm_name)
        dbdir = os.path.dirname(dbbuild)

        if os.path.isdir(dbdir):
            tbz2 = xpak.tbz2(package_path)
            tbz2.recompose(dbdir)
            return True
        return False

    def __run_pkg_sync_quickpkg(self, entropy_server, atoms, repo_db, repo):
        """
        Executes packages regeneration for given atoms.
        """
        package_paths = []
        runatoms = set()
        for myatom in atoms:
            mymatch = repo_db.atomMatch(myatom)
            if mymatch[0] == -1:
                continue
            myatom = repo_db.retrieveAtom(mymatch[0])
            myatom = entropy.dep.remove_tag(myatom)
            runatoms.add(myatom)

        for myatom in runatoms:

            # check if atom is available
            try:
                inst_match = self.match_installed_package(myatom)
            except KeyError:
                inst_match = None
            if not inst_match:
                self.__output.output(
                    red("%s: " % (_("package not available on system"),) ) + \
                        blue(myatom),
                    importance = 1,
                    level = "warning",
                    header = purple("  # ")
                )
                continue
            else:
                self.__output.output(
                    red("%s: " % (_("repackaging"),) )+blue(myatom),
                    importance = 1,
                    level = "warning",
                    header = blue("  # ")
                )

            mydest = entropy_server._get_local_store_directory(repo)
            try:
                pkg_list = self.generate_package(myatom, mydest)
            except Exception:
                entropy.tools.print_traceback()
                mytxt = "%s: %s: %s, %s." % (
                    bold(_("WARNING")),
                    red(_("Cannot complete quickpkg for atom")),
                    blue(myatom),
                    _("do it manually"),
                )
                self.__output.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = darkred(" * ")
                )
                continue
            package_paths.append(pkg_list)
        packages_data = [(pkg_list, False,) for pkg_list in package_paths]
        idpackages = entropy_server.add_packages_to_repository(repo,
            packages_data, ask = is_interactive())

        if not idpackages:

            mytxt = "%s: %s. %s." % (
                bold(_("ATTENTION")),
                red(_("package files rebuild did not run properly")),
                red(_("Please update packages manually")),
            )
            self.__output.output(
                mytxt,
                importance = 1,
                level = "warning",
                header = darkred(" * ")
            )

    def __portage_updates_md5(self, repo_updates_file):

        root = etpConst['systemroot'] + os.path.sep

        portdb = self._get_portage_portagetree(root).dbapi
        mdigest = hashlib.md5()
        # this way, if no matches are found, the same value is returned
        if const_is_python3():
            mdigest.update(const_convert_to_rawstring("begin"))
        else:
            mdigest.update("begin")

        for repo_name in portdb.getRepositories():
            repo_path = portdb.getRepositoryPath(repo_name)
            updates_dir = os.path.join(repo_path, "profiles", "updates")
            if not os.path.isdir(updates_dir):
                continue

            # get checksum
            # update
            ndigest = entropy.tools.md5obj_directory(updates_dir)
            mdigest.update(ndigest.digest())

        # also checksum etpConst['etpdatabaseupdatefile']
        if os.path.isfile(repo_updates_file):
            with open(repo_updates_file, "rb") as f:
                block = f.read(1024)
                while block:
                    mdigest.update(block)
                    block = f.read(1024)

        return mdigest

    def _get_portage_update_actions(self, repo_updates_file):

        root = etpConst['systemroot'] + os.path.sep

        updates_map = {}
        portdb = self._get_portage_portagetree(root).dbapi

        for repo_name in portdb.getRepositories():
            repo_path = portdb.getRepositoryPath(repo_name)
            updates_dir = os.path.join(repo_path, "profiles", "updates")
            if not os.path.isdir(updates_dir):
                continue

            update_files_repo = [x for x in os.listdir(updates_dir) if x \
                not in ("CVS", ".svn")]
            for update_id in update_files_repo:
                obj = updates_map.setdefault(update_id, [])
                obj.append(os.path.join(updates_dir, update_id))

        update_actions = []
        sorted_ids = PortageMetaphor.sort_update_files(list(updates_map.keys()))
        enc = etpConst['conf_encoding']
        for update_id in sorted_ids:
            update_files = updates_map[update_id]

            # now load actions from files
            for update_file in update_files:
                with codecs.open(update_file, "r", encoding=enc) as f:
                    mycontent = f.readlines()
                lines = [x.strip() for x in mycontent if x.strip()]
                update_actions.extend(lines)

        # add entropy packages.db.repo_updates content
        if os.path.isfile(repo_updates_file):
            with codecs.open(repo_updates_file, "r", encoding=enc) as f:
                mycontent = f.readlines()
            lines = [x.strip() for x in mycontent if x.strip() and \
                not x.strip().startswith("#")]
            update_actions.extend(lines)

        return update_actions

    def package_names_update(self, entropy_repository, entropy_repository_id,
        entropy_server, entropy_branch):

        repo_updates_file = \
            entropy_server._get_local_repository_treeupdates_file(
                entropy_repository_id)
        do_rescan = False

        stored_digest = entropy_repository.retrieveRepositoryUpdatesDigest(
            entropy_repository_id)
        if stored_digest == -1:
            do_rescan = True

        # check portage files for changes if do_rescan is still false
        portage_dirs_digest = "0"
        if not do_rescan:

            if entropy_repository_id in \
                self.__entropy_repository_treeupdate_digests:

                portage_dirs_digest = \
                    self.__entropy_repository_treeupdate_digests.get(
                        entropy_repository_id)
            else:
                mdigest = self.__portage_updates_md5(repo_updates_file)
                portage_dirs_digest = mdigest.hexdigest()
                self.__entropy_repository_treeupdate_digests[entropy_repository_id] = \
                    portage_dirs_digest

        if do_rescan or (str(stored_digest) != str(portage_dirs_digest)):

            # force parameters, only ServerEntropyRepository exposes
            # the setReadonly method
            entropy_repository.setReadonly(False)
            # disable upload trigger
            from entropy.server.interfaces.main import \
                ServerEntropyRepositoryPlugin
            entropy_repository.set_plugin_metadata(
                ServerEntropyRepositoryPlugin.PLUGIN_ID, "no_upload", True)

            # reset database tables
            entropy_repository.clearTreeupdatesEntries(entropy_repository_id)
            update_actions = self._get_portage_update_actions(
                repo_updates_file)

            # now filter the required actions
            update_actions = entropy_repository.filterTreeUpdatesActions(
                update_actions)
            if update_actions:

                mytxt = "%s: %s. %s %s" % (
                    bold(_("ATTENTION")),
                    red(_("forcing package updates")),
                    red(_("Syncing with")),
                    blue("Portage"),
                )
                self.__output.output(
                    mytxt,
                    importance = 1,
                    level = "info",
                    header = brown(" * ")
                )
                # lock database
                if entropy_repository.get_plugins_metadata().get("lock_remote"):
                    no_upload = entropy_repository.get_plugins_metadata().get(
                        "no_upload")
                    entropy_server._server_repository_sync_lock(
                        entropy_repository_id, no_upload)
                # now run queue
                try:
                    quickpkg_list = entropy_repository.runTreeUpdatesActions(
                        update_actions)
                except:
                    # destroy digest
                    entropy_repository.setRepositoryUpdatesDigest(
                        entropy_repository_id, "-1")
                    raise

                if quickpkg_list:
                    # quickpkg package and packages owning it as a dependency
                    try:
                        self.__run_pkg_sync_quickpkg(
                            entropy_server,
                            quickpkg_list, entropy_repository,
                            entropy_repository_id)
                    except:
                        entropy.tools.print_traceback()
                        mytxt = "%s: %s: %s, %s." % (
                            bold(_("WARNING")),
                            red(_("Cannot complete quickpkg for atoms")),
                            blue(str(sorted(quickpkg_list))),
                            _("do it manually"),
                        )
                        self.__output.output(
                            mytxt,
                            importance = 1,
                            level = "warning",
                            header = darkred(" * ")
                        )
                    entropy_repository.commit(force = True, no_plugins = True)

                # store new actions
                entropy_repository.addRepositoryUpdatesActions(
                    entropy_repository_id, update_actions, entropy_branch)

            # store new digest into database
            entropy_repository.setRepositoryUpdatesDigest(
                entropy_repository_id, portage_dirs_digest)
            entropy_repository.commit(force = True, no_plugins = True)

    @staticmethod
    def package_phases_map():
        """
        Reimplemented from SpmPlugin class.
        """
        return PortagePlugin._package_phases_map.copy()

    @staticmethod
    def config_files_map():
        """
        Reimplemented from SpmPlugin class.
        """
        config_map = PortagePlugin._config_files_map.copy()
        # extend with config files inside directories
        for key, path in list(config_map.items()):
            if os.path.exists(path) and os.path.isdir(path):
                try:
                    path_list = os.listdir(path)
                except (OSError, IOError):
                    continue
                for path_file in path_list:
                    if path_file.startswith("."):
                        # ignore hidden files
                        # like: ._cfg0000-blah
                        continue
                    full_path_file = os.path.join(path, path_file)
                    if os.path.isfile(full_path_file):
                        file_key = key + ":" + path_file
                        config_map[file_key] = full_path_file
        return config_map

    def execute_package_phase(self, action_metadata, package_metadata,
        action_name, phase_name):
        """
        Reimplemented from SpmPlugin class.
        """
        portage_phase = PortagePlugin._package_phases_map[phase_name]
        phase_calls = {
            'setup': self._pkg_setup,
            'preinst': self._pkg_preinst,
            'postinst': self._pkg_postinst,
            'prerm': self._pkg_prerm,
            'postrm': self._pkg_postrm,
            'config': self._pkg_config,
        }
        phase_calls[portage_phase](action_name, action_metadata,
                                   package_metadata)

    def _bump_vartree_mtime(self, portage_cpv, root = None):
        """
        Properly bump pkg vdb entry mtime. As oppsed to
        vartree.dbapi._bump_mtime() this method also bumps
        mtime of the pkg directory, which is vital as well.
        """
        if root is None:
            root = etpConst['systemroot'] + os.path.sep
        base = self._get_vdb_path(root = root)
        pkg_path = os.path.join(base, portage_cpv)
        catdir = os.path.dirname(pkg_path)
        t = time.time()
        t = (t, t)
        for x in (pkg_path, catdir, base):
            try:
                os.utime(x, t)
            except OSError as err:
                sys.stderr.write("OSError, cannot update %s mtime, %s\n" % (
                    x, err,))
            except IOError as err:
                sys.stderr.write("IOError, cannot update %s mtime, %s\n" % (
                        x, err,))

    def __splitdebug_update_contents_file(self, contents_path, splitdebug_dirs):

        if not const_file_readable(contents_path):
            return

        # Portage metadata is encoded using raw_unicode_escape.
        # Do not change enc to UTF-8, or xblast installation will fail.
        enc = etpConst['conf_raw_encoding']
        with codecs.open(contents_path, "r", encoding=enc) as cont_f:
            with codecs.open(contents_path+".tmp", "w", encoding=enc) \
                    as cont_new_f:
                line = cont_f.readline()
                while line:
                    do_skip = False
                    split_line = line.split()
                    if len(split_line) > 1:
                        for splitdebug_dir in splitdebug_dirs:
                            if split_line[1].startswith(splitdebug_dir):
                                do_skip = True
                                break
                    if do_skip:
                        line = cont_f.readline()
                        continue
                    cont_new_f.write(line)
                    line = cont_f.readline()

        os.rename(contents_path+".tmp", contents_path)

    def _create_contents_file_if_not_available(
            self, pkg_dir, entropy_package_metadata):

        root = etpConst['systemroot'] + os.path.sep
        with self._PortageVdbLocker(self, root = root):
            return self._create_contents_file_if_not_available_unlocked(
                root, pkg_dir, entropy_package_metadata)

    def _create_contents_file_if_not_available_unlocked(
            self, root, pkg_dir, entropy_package_metadata):

        c_file = PortagePlugin.xpak_entries['contents']
        cont_path = os.path.join(pkg_dir, c_file)
        contents_file_exists = os.path.exists(cont_path)
        if contents_file_exists:
            return # all fine already

        from portage.dbapi.vartree import write_contents

        entropy_content_iter = entropy_package_metadata['content']
        sys_root = const_convert_to_rawstring(etpConst['systemroot'])
        content_meta = {}

        try:
            for _package_id, _path, _ftype in entropy_content_iter:

                _ftype = const_convert_to_rawstring(_ftype)
                path_orig = const_convert_to_rawstring(_path)
                path = sys_root + path_orig

                is_sym = os.path.islink(path)
                if os.path.isfile(path) and not is_sym:
                    md5sum = entropy.tools.md5sum(path)
                    mtime = int(os.path.getmtime(path))
                    content_meta[path] = (_ftype, mtime, md5sum)
                elif os.path.isdir(path) and not is_sym:
                    content_meta[path] = (_ftype,)
                elif is_sym:
                    try:
                        mtime = int(os.path.getmtime(path))
                    except OSError:
                        # broken symlink!
                        mtime = int(time.time())
                    content_meta[path] = (_ftype, mtime, os.readlink(path))
                else:
                    try:
                        lstat = os.lstat(path)
                    except (OSError, AttributeError):
                        lstat = None
                    if lstat is not None:
                        if stat.S_ISFIFO(lstat[stat.ST_MODE]):
                            content_meta[path] = (_ftype,)
                        elif not stat.S_ISREG(lstat[stat.ST_MODE]):
                            # device?
                            content_meta[path] = (_ftype,)
        finally:
            if hasattr(entropy_content_iter, "close"):
                entropy_content_iter.close()

        portage_cpv = PortagePlugin._pkg_compose_atom(
            entropy_package_metadata)
        self._bump_vartree_mtime(portage_cpv, root = root)

        enc = etpConst['conf_encoding']
        with codecs.open(cont_path, "w", encoding=enc) as cont_f:
            # NOTE: content_meta contains paths with ROOT prefix, it's ok
            write_contents(content_meta, root, cont_f)

        self._bump_vartree_mtime(portage_cpv, root = root)

    def _get_portage_sets_object(self):
        try:
            import portage._sets as sets
        except ImportError:
            try:
                # older portage, <= 2.2_rc67
                import portage.sets as sets
            except ImportError:
                sets = None
        return sets

    def _get_portage_sets_files_object(self):
        try:
            import portage._sets.files as files
        except ImportError:
            try:
                # older portage, <= 2.2_rc67
                import portage.sets.files as files
            except ImportError:
                files = None
        return files

    def _get_world_set_object(self):
        try:
            from portage._sets.files import WorldSelectedSet
        except ImportError:
            try:
                # older portage, <= 2.2_rc67
                from portage.sets.files import WorldSelectedSet
            except ImportError:
                WorldSelectedSet = None
        return WorldSelectedSet

    class _PortageVdbLocker(object):

        def __init__(self, parent, root = None):
            self.__vdb_path = parent._get_vdb_path(root = root)
            self.__vdb_lock = None
            self.__parent = parent
            self.__locked = 0

        def __enter__(self):
            if self.__locked == 0:
                self.__vdb_lock = self.__parent._portage.locks.lockdir(
                    self.__vdb_path)
            self.__locked += 1

        def __exit__(self, exc_type, exc_value, traceback):
            if self.__locked > 0:
                self.__locked -= 1
            if (self.__locked == 0) and (self.__vdb_lock is not None):
                self.__parent._portage.locks.unlockdir(
                    self.__vdb_lock)
                self.__vdb_lock = None

    class _PortageWorldSetLocker(object):

        def __init__(self, parent, root = None):
            self.__world_set = None
            world_set = parent._get_world_set_object()
            if world_set is not None:
                if root is None:
                    self.__root = etpConst['systemroot'] + os.path.sep
                else:
                    self.__root = root
                self.__world_set = world_set(self.__root)
            self.__locked = 0

        def __enter__(self):
            if self.__world_set is not None:
                if self.__locked == 0:
                    self.__world_set.lock()
                self.__locked += 1

        def __exit__(self, exc_type, exc_value, traceback):
            if self.__world_set is not None:
                if self.__locked > 0:
                    self.__locked -= 1
                if self.__locked == 0:
                    self.__world_set.unlock()

    def add_installed_package(self, package_metadata):
        """
        Reimplemented from SpmPlugin class.
        """
        root = etpConst['systemroot'] + os.path.sep
        with self._PortageVdbLocker(self, root = root):
            return self._add_installed_package_unlocked(
                root, package_metadata)

    def _add_installed_package_unlocked(self, root, package_metadata):
        """
        add_installed_package() body assuming that vdb lock has been
        already acquired.
        """
        atomsfound = set()
        spm_package = PortagePlugin._pkg_compose_atom(package_metadata)
        key = entropy.dep.dep_getkey(spm_package)
        category = key.split("/")[0]

        build = self.get_installed_package_build_script_path(
            spm_package, root = root)
        pkg_dir = package_metadata.get('unittest_root', '') + \
            os.path.dirname(build)
        cat_dir = os.path.dirname(pkg_dir)

        if os.path.isdir(cat_dir):
            my_findings = [os.path.join(category, x) for x in \
                os.listdir(cat_dir)]
            # filter by key
            real_findings = [x for x in my_findings if \
                key == entropy.dep.dep_getkey(x)]
            atomsfound.update(real_findings)

        myslot = package_metadata['slot']
        for xatom in atomsfound:

            try:
                if self.get_installed_package_metadata(
                    xatom, "SLOT", root = root) != myslot:
                    continue
            except KeyError: # package not found??
                continue

            mybuild = self.get_installed_package_build_script_path(
                xatom, root = root)
            remove_path = os.path.dirname(mybuild)
            shutil.rmtree(remove_path, True)

        # we now install it
        xpak_rel_path = PortagePlugin._xpak_const['entropyxpakdatarelativepath']
        proposed_xpak_dir = os.path.join(package_metadata['xpakpath'],
            xpak_rel_path)

        # dealing with merge_from feature
        copypath_avail = True
        copypath = proposed_xpak_dir
        if package_metadata['merge_from']:
            copypath = package_metadata['xpakdir']
            if not os.path.isdir(copypath):
                copypath_avail = False

        counter = -1
        if (package_metadata['xpakstatus'] != None) and \
            os.path.isdir(proposed_xpak_dir) or \
            (package_metadata['merge_from'] and copypath_avail):

            if not os.path.isdir(cat_dir):
                os.makedirs(cat_dir, 0o755)

            splitdebug = package_metadata.get("splitdebug", False)
            splitdebug_dirs = package_metadata.get("splitdebug_dirs", tuple())

            if not splitdebug and splitdebug_dirs:
                contents_path = os.path.join(copypath,
                    PortagePlugin.xpak_entries['contents'])
                self.__splitdebug_update_contents_file(contents_path,
                    splitdebug_dirs)

            tmp_dir = const_mkdtemp(
                dir=cat_dir, prefix="-MERGING-")

            vdb_failed = False
            try:
                for f_name in os.listdir(copypath):
                    f_path = os.path.join(copypath, f_name)
                    dest_path = os.path.join(tmp_dir, f_name)
                    shutil.copy2(f_path, dest_path)
                # this should not really exist here
                if os.path.isdir(pkg_dir):
                    shutil.rmtree(pkg_dir)
                os.chmod(tmp_dir, 0o755)
                os.rename(tmp_dir, pkg_dir)
            except (IOError, OSError) as err:
                mytxt = "%s: %s: %s: %s" % (red(_("QA")),
                    brown(_("Cannot update Portage package metadata")),
                    purple(tmp_dir), err,)
                self.__output.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = darkred("   ## ")
                )
                shutil.rmtree(tmp_dir)
                vdb_failed = True

            # this is a Unit Testing setting, so it's always not available
            # unless in unit testing code
            if not package_metadata.get('unittest_root') and \
                (not vdb_failed):

                # Packages emerged with -B don't contain CONTENTS file
                # in their metadata, so we have to create one
                self._create_contents_file_if_not_available(pkg_dir,
                    package_metadata)

                try:
                    counter = self.assign_uid_to_installed_package(
                        spm_package, root = root)
                except self.Error as err:
                    mytxt = "%s: %s [%s]" % (
                        brown(_("SPM uid update error")), pkg_dir, err,
                    )
                    self.__output.output(
                        red("QA: ") + mytxt,
                        importance = 1,
                        level = "warning",
                        header = darkred("   ## ")
                    )
                    counter = -1

        self._bump_vartree_mtime(spm_package, root = root)

        user_inst_source = etpConst['install_sources']['user']
        if package_metadata['install_source'] != user_inst_source:
            # only user selected packages in Portage world file
            return counter

        myslot = package_metadata['slot'][:]
        # old slot protocol for kernel packages
        # XXX: remove before 2011-12-31
        if (package_metadata['versiontag'] == package_metadata['slot']) \
            and package_metadata['versiontag']:
            # usually kernel packages
            myslot = "0"
        elif package_metadata['versiontag'] and \
            ("," in package_metadata['slot']):
            # new slot format for kernel tagged packages
            myslot = entropy.dep.remove_tag_from_slot(myslot)

        keyslot = key + ":" + myslot
        key = const_convert_to_rawstring(key)
        world_file = self.get_user_installed_packages_file()
        world_dir = os.path.dirname(world_file)
        world_atoms = set()
        enc = etpConst['conf_encoding']

        try:

            with self._PortageWorldSetLocker(self, root = root):

                try:
                    with codecs.open(world_file, "r", encoding=enc) \
                            as world_f:
                        world_atoms |= set((x.strip() for x in \
                            world_f.readlines() if x.strip()))
                except (OSError, IOError) as err:
                    if err.errno != errno.ENOENT:
                        raise

                if keyslot not in world_atoms and \
                    entropy.tools.istextfile(world_file):

                    world_atoms.discard(key)
                    world_atoms.add(keyslot)
                    world_file_tmp = world_file+".entropy_inst"

                    newline = const_convert_to_unicode("\n")
                    with codecs.open(world_file_tmp, "w", encoding=enc) \
                            as world_f:
                        for item in sorted(world_atoms):
                            world_f.write(item + newline)

                    os.rename(world_file_tmp, world_file)

        except (UnicodeDecodeError, UnicodeEncodeError,) as e:

            mytxt = "%s: %s" % (
                brown(_("Cannot update SPM installed pkgs file")), world_file,
            )
            self.__output.output(
                red("QA: ") + mytxt + ": " + repr(e),
                importance = 1,
                level = "warning",
                header = darkred("   ## ")
            )

        return counter

    def remove_installed_package(self, atom, package_metadata):
        """
        Reimplemented from SpmPlugin class.
        """
        root = etpConst['systemroot'] + os.path.sep

        with self._PortageVdbLocker(self, root = root):
            return self._remove_installed_package_unlocked(
                root, atom, package_metadata)

    def _remove_installed_package_unlocked(self, root, atom, package_metadata):
        """
        remove_installed_package() body assuming that vdb lock has been
        already acquired.
        """
        atom = self.convert_from_entropy_package_name(atom)
        remove_build = self.get_installed_package_build_script_path(atom)
        remove_path = os.path.dirname(remove_build)
        key = entropy.dep.dep_getkey(atom)

        try:
            others_installed = self.match_installed_package(key,
                match_all = True)
        except KeyError:
            others_installed = []

        # Support for tagged packages
        slot = package_metadata['slot']
        tag = package_metadata['versiontag']
        if (tag == slot) and tag:
            # old kernel tagged pkgs protocol
            slot = "0"
        elif tag and ("," in slot):
            # new kernel tagged pkgs protocol
            slot = entropy.dep.remove_tag_from_slot(slot)

        def do_rm_path_atomic(xpath):
            for my_el in os.listdir(xpath):
                my_el = os.path.join(xpath, my_el)
                try:
                    os.remove(my_el)
                except OSError:
                    pass
            try:
                os.rmdir(xpath)
            except OSError:
                pass

        if os.path.isdir(remove_path):
            do_rm_path_atomic(remove_path)

        # also remove parent directory if empty
        category_path = os.path.dirname(remove_path)
        if os.path.isdir(category_path):
            if not os.listdir(category_path):
                try:
                    os.rmdir(category_path)
                except OSError:
                    pass

        if isinstance(others_installed, (list, set, tuple)):

            for myatom in others_installed:

                if myatom == atom:
                    # do not remove self
                    continue

                try:
                    myslot = self.get_installed_package_metadata(myatom,
                        "SLOT")
                except KeyError:
                    # package got removed or not available or broken
                    continue

                if myslot != slot:
                    continue
                mybuild = self.get_installed_package_build_script_path(
                    myatom)
                mydir = os.path.dirname(mybuild)
                if not os.path.isdir(mydir):
                    continue
                do_rm_path_atomic(mydir)

        with self._PortageWorldSetLocker(self, root = root):
            try:
                self.__remove_update_world_file(key, slot)
            except UnicodeDecodeError:
                # world file is fucked up
                mytxt = "%s: %s" % (
                    red("QA"),
                    brown(_("Portage world file is corrupted")),
                )
                self.__output.output(
                    mytxt,
                    importance = 1,
                    level = "warning",
                    header = darkred("   ## ")
                )

        return 0

    def __remove_update_world_file(self, key, slot):
        # otherwise update Portage world file
        world_file = self.get_user_installed_packages_file()
        world_file_tmp = world_file + ".entropy.tmp"
        enc = etpConst['conf_encoding']

        try:
            with codecs.open(world_file_tmp, "w", encoding=enc) as new:
                with codecs.open(world_file, "r", encoding=enc) as old:
                    line = old.readline()
                    sep = const_convert_to_unicode(":")
                    keyslot = key+sep+slot
                    while line:
                        if line.find(key) != -1:
                            line = old.readline()
                            continue
                        if line.find(keyslot) != -1:
                            line = old.readline()
                            continue
                        new.write(line)
                        line = old.readline()

        except (OSError, IOError) as err:
            if err.errno not in (errno.ENOENT, errno.EACCES):
                raise
        else:
            # this must complete successfully
            os.rename(world_file_tmp, world_file)

    @staticmethod
    def _qa_check_preserved_libraries(entropy_output, portage):
        """
        Ask portage whether there are preserved libraries on the system.
        This usually indicates that Entropy packages should not be really
        pushed.
        """
        root = etpConst['systemroot'] + os.path.sep
        mytree = portage.vartree(root=root)
        vardb = mytree.dbapi
        if vardb._plib_registry is None:
            # unsupported in current Portage version
            return 0, None

        vardb._plib_registry.load()
        if vardb._plib_registry.hasEntries():
            # just warn for now
            entropy_output.output("", importance = 0, level = "warning")
            txt = "%s: %s:" % (
                teal(_("Attention")),
                purple(_("preserved libraries have been found on system")),
            )
            entropy_output.output(txt,
                importance = 1,
                level = "warning",
                header = brown(" !!! "),
            )
            preserved_libs = vardb._plib_registry.getPreservedLibs()
            for cpv, path_list in preserved_libs.items():
                if path_list:
                    entropy_output.output(
                        darkblue(cpv),
                        importance = 0,
                        level = "warning",
                        header = teal(" @@ "),
                    )
                for path in path_list:
                    entropy_output.output(
                        path,
                        importance = 0,
                        level = "warning",
                        header = purple("    # "),
                    )
            entropy_output.output("", importance = 0, level = "warning")
        return 0, None

    @staticmethod
    def execute_system_qa_tests(entropy_output):
        """
        Reimplemented from SpmPlugin class.
        """
        import portage
        methods = (PortagePlugin._qa_check_preserved_libraries,)
        for method in methods:
            exit_st, msg = method(entropy_output, portage)
            if exit_st != 0:
                return exit_st, msg

        return 0, ""

    @staticmethod
    def execute_qa_tests(package_path):
        """
        Reimplemented from SpmPlugin class.
        """
        tests = [PortagePlugin._test_environment_bz2]
        msg = None
        exec_rc = 0
        for test in tests:
            exec_rc, msg = test(package_path)
            if exec_rc != 0:
                break
        return exec_rc, msg

    @staticmethod
    def _test_environment_bz2(package_path):

        tmp_path = None
        try:
            tmp_path = const_mkdtemp(prefix="_test_environment_bz2")

            xpaktools.extract_xpak(package_path, tmpdir = tmp_path)
            if not os.listdir(tmp_path):
                return 1, "unable to extract xpak metadata"

            # make sure we have the environment.bz2 file to check
            env_file = os.path.join(tmp_path, PortagePlugin.ENV_FILE_COMP)
            if not const_file_readable(env_file):
                return 2, "unable to locate %s file" % (
                    PortagePlugin.ENV_FILE_COMP,)

            # check if we have an alternate setting for LC*
            sys_settings = SystemSettings()
            plug_id = etpConst['system_settings_plugins_ids']['server_plugin']
            try:
                qa_langs = sys_settings[plug_id]['server']['qa_langs']
            except KeyError:
                qa_langs = ["en_US", "C"]

            qa_rlangs = [const_convert_to_rawstring(
                    "LC_ALL="+x) for x in qa_langs]

            valid_lc_all = False
            lc_found = False
            msg = None
            lc_all_str = const_convert_to_rawstring("LC_ALL")
            found_lang = None
            bz_f = None
            try:

                # read env file
                bz_f = bz2.BZ2File(env_file, "r")

                for line in bz_f.readlines():
                    if not line.startswith(lc_all_str):
                        continue
                    lc_found = True
                    found_lang = line.strip()
                    for lang in qa_rlangs:
                        if line.startswith(lang):
                            valid_lc_all = True
                            break
            finally:
                if bz_f is not None:
                    bz_f.close()

            env_rc = 0
            if lc_found and (not valid_lc_all):
                msg = "LC_ALL not set to => %s (but: %s)" % (
                    qa_langs, found_lang,)
                env_rc = 1

            return env_rc, msg

        finally:
            if tmp_path is not None:
                shutil.rmtree(tmp_path)

    @staticmethod
    def _config_updates_make_conf(entropy_client, repo):

        config_map = PortagePlugin._config_files_map

        ## WARNING: it doesn't handle multi-line variables, yet. remember this.
        system_make_conf = config_map['global_make_conf']
        if not os.path.isfile(system_make_conf):
            # default to the new location then
            system_make_conf = config_map['global_make_conf_new']

        sys_settings = SystemSettings()
        avail_data = sys_settings['repositories']['available']
        repo_dbpath = avail_data[repo]['dbpath']
        repo_make_conf = os.path.join(repo_dbpath,
            os.path.basename(system_make_conf))
        enc = etpConst['conf_encoding']

        if not const_file_readable(repo_make_conf):
            return

        make_conf_variables_check = ["CHOST"]

        if not os.path.isfile(system_make_conf):
            entropy_client.output(
                "%s %s. %s." % (
                    red(system_make_conf),
                    blue(_("does not exist")), blue(_("Overwriting")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            if os.path.lexists(system_make_conf):
                shutil.move(
                    system_make_conf,
                    "%s.backup_%s" % (system_make_conf,
                        entropy.tools.get_random_number(),)
                )
            shutil.copy2(repo_make_conf, system_make_conf)

        elif const_file_readable(system_make_conf):

            with codecs.open(repo_make_conf, "r", encoding=enc) as repo_f:
                repo_make_c = [x.strip() for x in repo_f.readlines()]
            with codecs.open(system_make_conf, "r", encoding=enc) as sys_f:
                sys_make_c = [x.strip() for x in sys_f.readlines()]

            # read repository settings
            repo_data = {}
            for setting in make_conf_variables_check:
                for line in repo_make_c:
                    if line.startswith(setting+"="):
                        # there can't be bash vars with a space
                        # after its name on declaration
                        repo_data[setting] = line
                        # I don't break, because there might be
                        # other overlapping settings

            differences = {}
            # update make.conf data in memory
            for setting in repo_data:
                for idx in range(len(sys_make_c)):
                    line = sys_make_c[idx]

                    if line.startswith(setting+"=") and \
                        (line != repo_data[setting]):

                        # there can't be bash vars with a
                        # space after its name on declaration
                        entropy_client.output(
                            "%s: %s %s. %s." % (
                                red(system_make_conf), bold(repr(setting)),
                                blue(_("variable differs")), red(_("Updating")),
                            ),
                            importance = 1,
                            level = "info",
                            header = blue(" @@ ")
                        )
                        differences[setting] = repo_data[setting]
                        line = repo_data[setting]
                    sys_make_c[idx] = line

            if differences:

                entropy_client.output(
                    "%s: %s." % (
                        red(system_make_conf),
                        blue(_("updating critical variables")),
                    ),
                    importance = 1,
                    level = "info",
                    header = blue(" @@ ")
                )
                # backup user make.conf
                shutil.copy2(system_make_conf,
                    "%s.entropy_backup" % (system_make_conf,))

                entropy_client.output(
                    "%s: %s." % (
                        red(system_make_conf),
                        darkgreen("writing changes to disk"),
                    ),
                    importance = 1,
                    level = "info",
                    header = blue(" @@ ")
                )
                # write to disk, safely
                tmp_make_conf = "%s.entropy_write" % (system_make_conf,)
                with codecs.open(tmp_make_conf, "w", encoding=enc) as f:
                    for line in sys_make_c:
                        f.write(line)
                        f.write("\n")
                shutil.move(tmp_make_conf, system_make_conf)

            # update environment
            for var in differences:
                try:
                    myval = '='.join(differences[var].strip().split("=")[1:])
                    if myval:
                        if myval[0] in ("'", '"',):
                            myval = myval[1:]
                        if myval[-1] in ("'", '"',):
                            myval = myval[:-1]
                except IndexError:
                    myval = ''
                os.environ[var] = myval

    @staticmethod
    def _config_updates_make_profile(entropy_client, repo):

        sys_settings = SystemSettings()
        avail_data = sys_settings['repositories']['available']
        repo_dbpath = avail_data[repo]['dbpath']
        profile_link = PortagePlugin._config_files_map['global_make_profile']
        profile_link_name = os.path.basename(profile_link)

        repo_make_profile = os.path.join(repo_dbpath, profile_link_name)

        if not const_file_readable(repo_make_profile):
            return

        system_make_profile = \
            PortagePlugin._config_files_map['global_make_profile']

        enc = etpConst['conf_encoding']
        with codecs.open(repo_make_profile, "r", encoding=enc) as f:
            repo_profile_link_data = f.readline().strip()
        current_profile_link = ''
        if os.path.islink(system_make_profile) and \
            const_file_readable(system_make_profile):

            current_profile_link = os.readlink(system_make_profile)

        if (repo_profile_link_data != current_profile_link) and \
            repo_profile_link_data:

            entropy_client.output(
                "%s: %s %s. %s." % (
                    red(system_make_profile), blue("link"),
                    blue(_("differs")), red(_("Updating")),
                ),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            merge_sfx = ".entropy_merge"
            os.symlink(repo_profile_link_data, system_make_profile+merge_sfx)
            if entropy.tools.is_valid_path(system_make_profile+merge_sfx):
                os.rename(system_make_profile+merge_sfx, system_make_profile)
            else:
                # revert change, link does not exist yet
                entropy_client.output(
                    "%s: %s %s. %s." % (
                        red(system_make_profile), blue("new link"),
                        blue(_("does not exist")), red(_("Reverting")),
                    ),
                    importance = 1,
                    level = "info",
                    header = blue(" @@ ")
                )
                os.remove(system_make_profile+merge_sfx)

    @staticmethod
    def entropy_client_post_repository_update_hook(entropy_client,
        entropy_repository_id):

        # are we root?
        if etpConst['uid'] != 0:
            entropy_client.output(
                brown(_("Skipping configuration files update, you are not root.")),
                importance = 1,
                level = "info",
                header = blue(" @@ ")
            )
            return 0

        sys_settings = SystemSettings()
        default_repo = sys_settings['repositories']['default_repository']

        if default_repo == entropy_repository_id:
            PortagePlugin._config_updates_make_conf(entropy_client,
                entropy_repository_id)
            PortagePlugin._config_updates_make_profile(entropy_client,
                entropy_repository_id)

        return 0

    @staticmethod
    def entropy_install_setup_hook(entropy_client, package_metadata):
        """
        Reimplemented from SpmPlugin class.
        """
        install_dict = package_metadata['__install_trigger__']

        install_dict['xpakpath'] = os.path.join(
            package_metadata['unpackdir'],
            PortagePlugin._xpak_const['entropyxpakrelativepath'])

        if not package_metadata['merge_from']:

            install_dict['xpakstatus'] = None
            install_dict['xpakdir'] = os.path.join(
                install_dict['xpakpath'],
                PortagePlugin._xpak_const['entropyxpakdatarelativepath'])

        else:

            install_dict['xpakstatus'] = True

            try:
                import portage.const as pc
                portdbdir = pc.VDB_PATH
            except ImportError:
                portdbdir = 'var/db/pkg'

            portdbdir = os.path.join(package_metadata['merge_from'], portdbdir)
            portdbdir = os.path.join(portdbdir,
                PortagePlugin._pkg_compose_atom(package_metadata))

            install_dict['xpakdir'] = portdbdir

        package_metadata['xpakpath'] = install_dict['xpakpath']
        package_metadata['xpakdir'] = install_dict['xpakdir']
        package_metadata['xpakstatus'] = install_dict['xpakstatus']

        return 0

    @staticmethod
    def entropy_install_unpack_hook(entropy_client, package_metadata):
        """
        Reimplemented from SpmPlugin class.
        """
        # unpack xpak ?
        if os.path.isdir(package_metadata['xpakpath']):
            shutil.rmtree(package_metadata['xpakpath'], True)

        # create data dir where we'll unpack the xpak
        xpak_dir = os.path.join(package_metadata['xpakpath'],
            PortagePlugin._xpak_const['entropyxpakdatarelativepath'])

        os.makedirs(xpak_dir, 0o755)

        xpak_path = os.path.join(package_metadata['xpakpath'],
            PortagePlugin._xpak_const['entropyxpakfilename'])

        if not package_metadata['merge_from']:

            if package_metadata['smartpackage']:

                # we need to get the .xpak from database
                xdbconn = entropy_client.open_repository(
                    package_metadata['repository_id'])
                xpakdata = xdbconn.retrieveSpmMetadata(
                    package_metadata['package_id'])
                if xpakdata:
                    # save into a file
                    with open(xpak_path, "wb") as xpak_f:
                        xpak_f.write(xpakdata)
                    package_metadata['xpakstatus'] = \
                        xpaktools.unpack_xpak(
                            xpak_path,
                            xpak_dir
                        )
                else:
                    package_metadata['xpakstatus'] = None
                del xpakdata

            else:
                package_metadata['xpakstatus'] = xpaktools.extract_xpak(
                    package_metadata['pkgpath'],
                    xpak_dir
                )

        else: # merge_from

            tolink_dir = xpak_dir
            if os.path.isdir(tolink_dir):
                shutil.rmtree(tolink_dir, True)
            # now link
            os.symlink(package_metadata['xpakdir'], tolink_dir)

        # create fake portage ${D} linking it to imagedir
        portage_cpv = PortagePlugin._pkg_compose_atom(package_metadata)

        portage_db_fakedir = os.path.join(
            package_metadata['unpackdir'],
            "portage/" + portage_cpv
        )

        try:
            os.makedirs(portage_db_fakedir, 0o755)
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise
            shutil.rmtree(portage_db_fakedir, True)
            os.makedirs(portage_db_fakedir, 0o755)
        # now link it to package_metadata['imagedir']
        os.symlink(package_metadata['imagedir'],
            os.path.join(portage_db_fakedir, "image"))

        return 0

    def installed_mtime(self, root = None):
        """
        Reimplemented from SpmPlugin class.
        """
        dbapi = self._get_portage_vartree(root = root).dbapi
        vdb_path = self._get_vdb_path(root = root)
        try:
            mtime = max(0.0, os.path.getmtime(vdb_path))
        except OSError:
            mtime = 0.0
        for cpv in dbapi.cpv_all():
            vdb_entry = os.path.join(vdb_path, cpv)
            vdb_entry_parent = os.path.dirname(vdb_entry)
            try:
                mtime = max(mtime, os.path.getmtime(vdb_entry))
                mtime = max(mtime, os.path.getmtime(vdb_entry_parent))
            except OSError:
                pass
        return mtime

    def _get_portage_vartree(self, root = None):

        if root is None:
            root = etpConst['systemroot'] + os.path.sep

        cached = PortagePlugin.CACHE['vartree'].get(root)
        if cached is not None:
            return cached

        try:
            settings = self._get_portage_config(os.path.sep, root)
            mytree = self._portage.vartree(root=root, settings=settings)
        except Exception as err:
            raise self.Error(err)
        PortagePlugin.CACHE['vartree'][root] = mytree
        return mytree

    def _get_portage_portagetree(self, root):

        cached = PortagePlugin.CACHE['portagetree'].get(root)
        if cached is not None:
            return cached

        try:
            settings = self._get_portage_config(os.path.sep, root)
            mytree = self._portage.portagetree(settings=settings)
        except Exception as err:
            raise self.Error(err)
        PortagePlugin.CACHE['portagetree'][root] = mytree
        return mytree

    def _get_portage_binarytree(self, root):

        cached = PortagePlugin.CACHE['binarytree'].get(root)
        if cached is not None:
            return cached

        pkgdir = root+self._portage.settings['PKGDIR']
        try:
            mytree = self._portage.binarytree(root, pkgdir)
        except Exception as err:
            raise self.Error(err)
        PortagePlugin.CACHE['binarytree'][root] = mytree
        return mytree

    def _get_portage_config(self, config_root, root, use_cache = True):

        if use_cache:
            cached = PortagePlugin.CACHE['config'].get((config_root, root))
            if cached is not None:
                return cached

        try:
            mysettings = self._portage.config(config_root = config_root,
                target_root = root,
                config_incrementals = self._portage.const.INCREMENTALS)
        except Exception as err:
            raise self.Error(err)
        if use_cache:
            PortagePlugin.CACHE['config'][(config_root, root)] = mysettings

        return mysettings

    def _get_useflags(self):
        return self._portage.settings['USE']

    def _get_useflags_force(self):
        return self._portage.settings.useforce

    def _get_useflags_mask(self):
        return self._portage.settings.usemask

    def _resolve_useflags(self, iuse_list, use_list, use_force):
        use = set()
        disabled_use = set()
        plus = const_convert_to_rawstring("+")
        minus = const_convert_to_rawstring("-")
        for myiuse in iuse_list:
            if myiuse[0] in (plus, minus,):
                myiuse = myiuse[1:]
            if ((myiuse in use_list) or (myiuse in use_force)):
                use.add(myiuse)
            elif (myiuse not in use_list) and (myiuse not in use_force):
                disabled_use.add(myiuse)
        return use, disabled_use

    def _calculate_dependencies(self, my_iuse, my_use, my_license, my_depend,
        my_rdepend, my_pdepend, my_provide, my_src_uri, my_eapi):

        metadata = {
            'LICENSE': my_license,
            'DEPEND': my_depend,
            'PDEPEND': my_pdepend,
            'RDEPEND': my_rdepend,
            'PROVIDE': my_provide,
            'SRC_URI': my_src_uri,
        }

        # generate USE flags metadata
        use_force = self._get_useflags_force()
        raw_use = my_use.split()
        enabled_use, disabled_use = self._resolve_useflags(
            my_iuse.split(), raw_use, use_force)
        enabled_use = sorted(enabled_use)
        disabled_use = sorted(disabled_use)

        metadata['ENABLED_USE'] = enabled_use
        metadata['DISABLED_USE'] = disabled_use
        use = raw_use + [x for x in use_force if x not in raw_use]
        metadata['USE'] = sorted([const_convert_to_unicode(x) for x in use])
        metadata['USE_FORCE'] = sorted(use_force)
        variables = "LICENSE", "RDEPEND", "DEPEND", "PDEPEND", \
            "PROVIDE", "SRC_URI"

        for k in variables:
            try:
                deps = self._portage.dep.use_reduce(metadata[k],
                    uselist = enabled_use, is_src_uri = (k == "SRC_URI"),
                    eapi = my_eapi)
                if k == "LICENSE":
                    deps = self._paren_license_choose(deps)
                else:
                    deps = self._paren_choose(deps)
                if k.endswith("DEPEND"):
                    deps = self._slotdeps_eapi5_reduce(deps)
                    deps = self._usedeps_reduce(deps, enabled_use)
            except Exception as e:
                entropy.tools.print_traceback()
                self.__output.output(
                    darkred("%s: %s :: %s") % (
                        _("Error calculating dependencies"),
                        k,
                        repr(e),
                    ),
                    importance = 1,
                    level = "error",
                    header = red(" !!! ")
                )
                deps = ''
                continue
            metadata[k] = deps

        return metadata

    def _strip_slash_from_slot(self, slot_s):
        """
        EAPI5: strip /* substring from SLOT string.
        """
        slash_idx = slot_s.find("/")
        if slash_idx != -1:
            slot_s = slot_s[:slash_idx]
        return slot_s

    def _slotdeps_eapi5_reduce(self, dependencies):
        newlist = []

        for raw_dependency in dependencies:

            split_deps = entropy.dep.dep_split_or_deps(raw_dependency)
            filtered_deps = []
            for depstring in split_deps:

                new_depstring = []
                # conditional deps support
                for _depstring in depstring.split():

                    # keep use dependencies
                    slot = entropy.dep.dep_getslot(_depstring)

                    # support conditional dependencies
                    # as in, just ignore any filtering if
                    # _depstring is an "operator"
                    # however, I don't know why we have this here
                    if slot and _depstring not in ("(", ")", "&", "|"):

                        usedeps = entropy.dep.dep_getusedeps(_depstring)
                        _depstring = entropy.dep.remove_usedeps(_depstring)

                        if slot in ("=", "*"):
                            # build related slot operators
                            # filter them out
                            _depstring = entropy.dep.remove_slot(
                                _depstring)

                        elif slot[-1] in ("=", "*"):
                            # if slot part ends with either = or *
                            # then kill them.
                            _depstring = entropy.dep.remove_slot(
                                _depstring)
                            _depstring = _depstring + ":" + \
                                self._strip_slash_from_slot(slot[:-1])

                        elif "/" in slot:
                            _depstring = entropy.dep.remove_slot(
                                _depstring)
                            _depstring = _depstring + ":" + \
                                self._strip_slash_from_slot(slot)

                        # re-add usedeps if any
                        if usedeps:
                            _depstring = "%s[%s]" % (
                                _depstring,
                                ','.join(usedeps),)

                    new_depstring.append(_depstring)

                depstring = " ".join(new_depstring)
                filtered_deps.append(depstring)

            if len(filtered_deps) > 1:
                or_dep = etpConst['entropyordepsep']
                raw_dependency = or_dep.join(filtered_deps) + \
                    etpConst['entropyordepquestion']
            else:
                raw_dependency = filtered_deps[0]
            newlist.append(raw_dependency)

        return newlist

    def _usedeps_reduce(self, dependencies, enabled_useflags):
        newlist = []

        def strip_use(xuse):
            myuse = xuse[:]
            if myuse[0] == "!":
                myuse = myuse[1:]
            if myuse[-1] in ("=", "?",):
                myuse = myuse[:-1]
            return myuse

        def filter_use_deps(dependency):
            new_use_deps = []
            for use in use_deps:
                """
                explicitly support only specific types
                """
                if (use[0] == "!") and (use[-1] not in ("=", "?",)):
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
                elif use.endswith("(-)"):
                    # EAPI=4 USE defaults
                    # in entropy cases, this can be always ignored.
                    # :: -foo(-), i don't want foo, and if foo doesn't
                    # exist on target, consider it disabled.
                    # :: foo(-), i want foo, and if foo doesn't exist
                    # on target, consider it disabled.
                    use = use[:-3]
                new_use_deps.append(use)
            return new_use_deps


        for raw_dependency in dependencies:

            split_deps = entropy.dep.dep_split_or_deps(raw_dependency)
            filtered_deps = []
            for depstring in split_deps:

                new_depstring = []
                # conditional deps support
                for _depstring in depstring.split():
                    if _depstring in ("(", ")", "&", "|"):
                        new_depstring.append(_depstring)
                        continue

                    use_deps = entropy.dep.dep_getusedeps(_depstring)
                    if not use_deps:
                        new_depstring.append(_depstring)
                        continue

                    new_use_deps = filter_use_deps(_depstring)

                    if new_use_deps:
                        _depstring = "%s[%s]" % (
                            entropy.dep.remove_usedeps(_depstring),
                            ','.join(new_use_deps),
                            )
                    else:
                        _depstring = entropy.dep.remove_usedeps(
                            _depstring)
                    new_depstring.append(_depstring)
                depstring = " ".join(new_depstring)

                filtered_deps.append(depstring)

            if len(filtered_deps) > 1:
                or_dep = etpConst['entropyordepsep']
                raw_dependency = or_dep.join(filtered_deps) + \
                    etpConst['entropyordepquestion']
            else:
                raw_dependency = filtered_deps[0]
            newlist.append(raw_dependency)

        return newlist

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

    def _paren_choose(self, dep_list):
        newlist = []
        do_skip = False
        for idx, item in enumerate(dep_list):

            if do_skip:
                do_skip = False
                continue

            # OR, no conditional deps support
            if item == "||":
                next_item = dep_list[idx+1]
                # || ( asd? ( atom ) dsa? ( atom ) )
                # => [] if use asd and dsa are disabled
                if not next_item:
                    do_skip = True
                    continue
                # must be a list
                item = self._dep_or_select(next_item, top_level = True)
                if not item:
                    # no matches, transform to string and append,
                    # so reagent will fail
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
        for idx, x in enumerate(and_list):

            if do_skip:
                do_skip = False
                continue

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

        return newlist

    def _dep_or_select_conditional(self, or_list):

        def _flatten_rec(idx, item, parent_list, accum):
            if isinstance(item, const_get_stringtype()):
                accum.append(item)
                if item == "||":
                    # or
                    accum.append("(")
                    next_item = parent_list[idx + 1]
                    for _idx, _item in enumerate(next_item):
                        _flatten_rec(_idx, _item, next_item, accum)
                    accum.append(")")
            elif isinstance(item, (list, set, frozenset, tuple)):
                # and
                accum.append("(")
                for _idx, _item in enumerate(item):
                    _flatten_rec(_idx, _item, item, accum)
                accum.append(")")
            else:
                raise PortageEntropyDepTranslator.ParseError(
                    "WTF error")

        deps = []
        try:
            for idx, item in enumerate(or_list):
                _flatten_rec(idx, item, or_list, deps)
        except PortageEntropyDepTranslator.ParseError:
            return None

        dep_string = "|| ( " + " ".join(deps) + " )"
        tr = PortageEntropyDepTranslator(dep_string)
        try:
            return tr.translate()
        except PortageEntropyDepTranslator.ParseError as err:
            sys.stderr.write("%s: %s, %s\n" % (
                "ParseError", err,
                or_list,)
            )
            return None

    def _dep_or_select(self, or_list, top_level = False):

        conditional_deps_enable = os.getenv(
            "ETP_PORTAGE_CONDITIONAL_DEPS_ENABLE")
        if conditional_deps_enable:
            dep = self._dep_or_select_conditional(or_list)
            if not dep:
                return []
            return [dep]

        if top_level:
            simple_or_list = [x for x in or_list if \
                isinstance(x, const_get_stringtype())] == or_list
            if simple_or_list:
                return [etpConst['entropyordepsep'].join(or_list) + \
                    etpConst['entropyordepquestion']]

        def select_or_dep(dep_list):
            for item in dep_list:
                if isinstance(item, const_get_stringtype()):
                    # match in currently running system
                    try:
                        item_match = self.match_installed_package(item)
                    except KeyError:
                        item_match = None
                    if item_match:
                        return [item]
                else:
                    # and deps, all have to match
                    all_matched = True
                    for dep in item:
                        try:
                            item_match = self.match_installed_package(dep)
                        except KeyError:
                            item_match = None
                        if not item_match:
                            all_matched = False
                            break
                    if all_matched:
                        return item

            # no match found, bailing out
            return [','.join(entropy.tools.flatten(dep_list))]

        deps = []
        skip_next = False

        for idx, item in enumerate(or_list):
            if skip_next:
                skip_next = False
                continue
            if item == "||":
                # get next item
                deps += self._dep_or_select(or_list[idx+1])
                skip_next = True
            elif not isinstance(item, const_get_stringtype()):
                # AND list, all have to match
                # must append one item that is a list
                dep = self._dep_and_select(item)
                if not dep:
                    # holy! add the whole dep as string (so it will fail)
                    dep = ['&'.join(item)]
                deps.append(dep)
            else:
                deps.append(item)

        return select_or_dep(deps)

    def _paren_license_choose(self, dep_list):

        newlist = set()
        for item in dep_list:
            if not isinstance(item, const_get_stringtype()):
                # match the first
                newlist.update(self._paren_license_choose(item))
            elif item != "||":
                newlist.add(item)

        return sorted(newlist)

    def _get_vdb_path(self, root = None):
        if root is None:
            root = etpConst['systemroot'] + os.path.sep
        return os.path.join(root, self._portage.const.VDB_PATH)

    def _load_sets_config(self, settings, trees):

        sets = self._get_portage_sets_object()
        if sets is None:
            return None
        return sets.load_default_config(settings, trees)

    def _get_set_config(self):
        myroot = etpConst['systemroot'] + os.path.sep
        return self._load_sets_config(
            self._portage.settings,
            self._portage.db[myroot]
        )

    def _extract_pkg_metadata_generate_extraction_dict(self):
        data = {
            'eapi': {
                'path': PortagePlugin.xpak_entries['eapi'],
                'critical': False,
            },
            'pf': {
                'path': PortagePlugin.xpak_entries['pf'],
                'critical': True,
                'env': "PF",
            },
            'chost': {
                'path': PortagePlugin.xpak_entries['chost'],
                'critical': False, # we deal with it afterwards
            },
            'description': {
                'path': PortagePlugin.xpak_entries['description'],
                'critical': False,
            },
            'homepage': {
                'path': PortagePlugin.xpak_entries['homepage'],
                'critical': False,
            },
            'slot': {
                'path': PortagePlugin.xpak_entries['slot'],
                'critical': False,
            },
            'cflags': {
                'path': PortagePlugin.xpak_entries['cflags'],
                'critical': False,
                'env': "CFLAGS",
            },
            'cxxflags': {
                'path': PortagePlugin.xpak_entries['cxxflags'],
                'critical': False,
                'env': "CXXFLAGS",
            },
            'category': {
                'path': PortagePlugin.xpak_entries['category'],
                'critical': True,
                'env': "CATEGORY",
            },
            'rdepend': {
                'path': PortagePlugin.xpak_entries['rdepend'],
                'critical': False,
            },
            'pdepend': {
                'path': PortagePlugin.xpak_entries['pdepend'],
                'critical': False,
            },
            'depend': {
                'path': PortagePlugin.xpak_entries['depend'],
                'critical': False,
            },
            'use': {
                'path': PortagePlugin.xpak_entries['use'],
                'critical': False,
            },
            'iuse': {
                'path': PortagePlugin.xpak_entries['iuse'],
                'critical': False,
            },
            'license': {
                'path': PortagePlugin.xpak_entries['license'],
                'critical': False,
            },
            'provide': {
                'path': PortagePlugin.xpak_entries['provide'],
                'critical': False,
            },
            'sources': {
                'path': PortagePlugin.xpak_entries['src_uri'],
                'critical': False, # we deal with it afterwards
            },
            'counter': {
                'path': PortagePlugin.xpak_entries['counter'],
                'critical': False,
            },
            'keywords': {
                'path': PortagePlugin.xpak_entries['keywords'],
                'critical': False,
            },
            'spm_phases': {
                'path': PortagePlugin.xpak_entries['defined_phases'],
                'critical': False,
            },
            'spm_repository': {
                'path': PortagePlugin.xpak_entries['repository'],
                'critical': False,
            },
        }
        return data

    def _extract_pkg_metadata_content_safety(self, content_data, pkg_dir):

        def is_reg(file_path):
            try:
                st = os.lstat(file_path)
            except OSError:
                return False
            return stat.S_ISREG(st.st_mode)

        def gen_meta(real_path, repo_path):
            return {
                'sha256': entropy.tools.sha256(real_path),
                'mtime': os.path.getmtime(real_path),
            }

        pkg_files = [(os.path.join(pkg_dir, k.lstrip("/")), k) for k, v in \
            content_data.items() if v == "obj"]
        pkg_files = [(real_path, repo_path) for real_path, repo_path in \
            pkg_files if is_reg(real_path)]
        return dict((repo_path, gen_meta(real_path, repo_path)) \
            for real_path, repo_path in pkg_files)

    def _extract_pkg_metadata_content(self, content_file, package_path,
                                      pkg_dir):

        pkg_content = {}
        obj_t = const_convert_to_unicode("obj")
        sym_t = const_convert_to_unicode("sym")
        fif_t = const_convert_to_unicode("fif")
        dev_t = const_convert_to_unicode("dev")
        dir_t = const_convert_to_unicode("dir")

        if os.path.isfile(content_file):

            with open(content_file, "rb") as f:
                content = [const_convert_to_unicode(x) for x in f.readlines()]

            outcontent = set()
            for line in content:
                line = line.strip().split()
                try:
                    datatype = line[0]
                    datafile = line[1:]
                    if datatype == obj_t:
                        datafile = datafile[:-2]
                        datafile = ' '.join(datafile)
                    elif datatype in (dir_t, fif_t, dev_t):
                        datafile = ' '.join(datafile)
                    elif datatype == sym_t:
                        datafile = datafile[:-3]
                        datafile = ' '.join(datafile)
                    else:
                        myexc = "%s %s. %s." % (
                            datafile,
                            _("not supported"),
                            _("Probably Portage API has changed"),
                        )
                        raise AttributeError(myexc)
                    if not datafile.strip():
                        warnings.warn(
                            "Empty file path detected, skipping!")
                        continue
                    outcontent.add((datafile, datatype))
                except:
                    pass

            outcontent = sorted(outcontent)
            for datafile, datatype in outcontent:
                pkg_content[datafile] = datatype

        else:

            # CONTENTS is not generated when a package is emerged with
            # portage and the option -B
            # we have to use the unpacked package file and generate content dict
            tmpdir_len = len(pkg_dir)
            for currentdir, subdirs, files in os.walk(pkg_dir):
                cur_dir = currentdir[tmpdir_len:]
                if cur_dir: # ignore "" entries
                    pkg_content[cur_dir] = dir_t
                for item in files:
                    item = currentdir + os.path.sep + item
                    item_rel = item[tmpdir_len:]
                    if not item_rel.strip():
                        warnings.warn(
                            "Empty file path detected, skipping!")
                        continue
                    if os.path.islink(item):
                        pkg_content[item_rel] = sym_t
                    else:
                        pkg_content[item_rel] = obj_t

        return pkg_content

    def _generate_needed_libs_elf_2(self, pkg_dir, content):
        """
        Generate NEEDED.ELF.2 metadata by scraping the package
        content directly. For: needed_libs metadata.
        """
        needed_libs = set()
        for obj, ftype in content.items():

            if ftype != "obj":
                continue
            obj_dir, obj_name = os.path.split(obj)

            unpack_obj = os.path.join(pkg_dir, obj.lstrip("/"))
            try:
                os.stat(unpack_obj)
            except OSError:
                continue

            try:
                if not entropy.tools.is_elf_file(unpack_obj):
                    continue
                elf_class = entropy.tools.read_elf_class(unpack_obj)
            except IOError as err:
                self.__output.output("%s: %s => %s" % (
                    _("IOError while reading"), unpack_obj, repr(err),),
                    level = "warning")
                continue

            meta = entropy.tools.read_elf_metadata(unpack_obj)
            if meta is None:
                continue

            for soname in meta['needed']:
                needed_libs.add((
                    obj, meta['soname'], soname, elf_class, meta['runpath']))

        return frozenset(needed_libs)

    def _extract_pkg_metadata_needed_libs_elf_2(self, needed_file):

        try:
            with open(needed_file, "rb") as f:
                lines = [x.strip() for x in f.readlines() if x.strip()]
                lines = [const_convert_to_unicode(x) for x in lines]
        except IOError:
            return frozenset()

        needed_libs = set()
        for line in lines:
            data = line.split(";")
            elfclass_str, lib_user_path, usr_soname, rpath, libs_str = data[0:5]
            elfclass = entropy.tools.elf_class_strtoint(elfclass_str)

            for soname in libs_str.split(","):
                needed_libs.add(
                    (lib_user_path, usr_soname, soname, elfclass, rpath))

        return frozenset(needed_libs)

    def _extract_pkg_metadata_needed_libs(self, needed_file):

        try:
            with open(needed_file, "rb") as f:
                lines = [x.strip() for x in f.readlines() if x.strip()]
                lines = [const_convert_to_unicode(x) for x in lines]
        except IOError:
            return frozenset()

        needed_libs = set()
        for line in lines:
            data = line.split()
            if len(data) == 2:
                lib_user_path, libs_str = data
                elfclass = -1
                if const_file_readable(lib_user_path):
                    elfclass = entropy.tools.read_elf_class(lib_user_path)

                for soname in libs_str.split(","):
                    needed_libs.add(
                        (lib_user_path, "", soname, elfclass, ""))

        return frozenset(needed_libs)

    def _extract_pkg_metadata_provided_libs(self, pkg_dir, content):

        # NOTE: this does not take into account changes to environment
        # caused by the installation of the package, if this metadata
        # is read off a non-installed one.
        provided_libs = set()
        for obj, ftype in content.items():

            if ftype not in ("obj", "sym"):
                continue
            obj_dir, obj_name = os.path.split(obj)

            unpack_obj = os.path.join(pkg_dir, obj.lstrip("/"))
            try:
                os.stat(unpack_obj)
            except OSError:
                continue

            # do not trust ftype
            if os.path.isdir(unpack_obj):
                continue

            try:
                if not entropy.tools.is_elf_file(unpack_obj):
                    continue
            except IOError as err:
                self.__output.output("%s: %s => %s" % (
                    _("IOError while reading"), unpack_obj, repr(err),),
                    level = "warning")
                continue

            try:
                elf_meta = entropy.tools.read_elf_metadata(unpack_obj)
            except FileNotFound:
                continue

            if elf_meta is None:
                continue

            if elf_meta['soname']:  # no soname == no shared library
                provided_libs.add((elf_meta['soname'], obj, elf_meta['class'],))

        return provided_libs

    def _extract_pkg_metadata_desktop_mime(self, pkg_dir, content):

        valid_paths = [x for x in content if x.endswith(".desktop")]
        if not valid_paths:
            return [], set()

        data_dirs = [os.path.join(x, "applications") for x in \
            os.getenv("XDG_DATA_DIRS", "/usr/share").split(":")]

        def filter_valid_paths(path):
            for data_dir in data_dirs:
                if path.startswith(data_dir):
                    return True
            return False

        valid_paths = list(filter(filter_valid_paths, valid_paths))
        valid_paths = [os.path.join(pkg_dir, x[1:]) for x in valid_paths]

        desktop_mime = []
        provided_mime = set()
        enc = etpConst['conf_encoding']
        raw_enc = etpConst['conf_raw_encoding']

        def _read_file(desktop_path, encoding):
            with codecs.open(desktop_path, "r", encoding=encoding) as desk_f:
                desk_data = [x.strip().split("=", 1) for x in \
                    desk_f.readlines() if len(x.strip().split("=", 1)) == 2]
                raw_desk_meta = dict(desk_data)
            return raw_desk_meta

        for desktop_path in sorted(valid_paths):
            if not const_file_readable(desktop_path):
                continue

            try:
                raw_desk_meta = _read_file(desktop_path, enc)
            except UnicodeDecodeError:
                # sometimes files are stored in raw unicode format
                raw_desk_meta = _read_file(desktop_path, raw_enc)

            if "MimeType" not in raw_desk_meta:
                continue
            elif "Name" not in raw_desk_meta:
                continue
            provided_mime.update(raw_desk_meta['MimeType'].split(";"))
            desk_meta = {
                "name": raw_desk_meta['Name'],
                "mimetype": raw_desk_meta['MimeType'],
                "executable": raw_desk_meta.get('Exec'),
                "icon": raw_desk_meta.get("Icon"),
            }
            desktop_mime.append(desk_meta)

        provided_mime.discard("")
        return desktop_mime, provided_mime

    def _extract_pkg_metadata_license_data(self, spm_repository, license_string):

        root = etpConst['systemroot'] + os.path.sep
        portdb = self._get_portage_portagetree(root).dbapi
        license_dirs = [os.path.join(self.get_setting('PORTDIR'), "licenses")]
        if spm_repository is not None:
            repo_path = portdb.getRepositoryPath(spm_repository)
            if repo_path is not None:
                license_dirs.append(os.path.join(repo_path, "licenses"))

        pkg_licensedata = {}
        licdata = [x.strip() for x in license_string.split() if x.strip() \
            and entropy.tools.is_valid_string(x.strip())]

        for mylicense in licdata:
            found_lic = False
            for license_dir in license_dirs:
                licfile = os.path.join(license_dir, mylicense)

                if not const_file_readable(licfile):
                    continue

                if not entropy.tools.istextfile(licfile):
                    continue

                with open(licfile, "rb") as f:
                    content = const_convert_to_rawstring('')
                    line = f.readline()
                    while line:
                        content += line
                        line = f.readline()
                    try:

                        try:
                            pkg_licensedata[mylicense] = \
                                const_convert_to_unicode(content)
                        except UnicodeDecodeError:
                            pkg_licensedata[mylicense] = \
                                const_convert_to_unicode(content, 'utf-8')

                    except (UnicodeDecodeError, UnicodeEncodeError,):
                        continue # sorry!
                found_lic = True
                break

            if not found_lic:
                # make sure we always collect license and show something to
                # user. Also set a default sorry text, in case we are not
                # able to print it.
                pkg_licensedata[mylicense] = """We're sorry, %s license couldn't
be retrieved correcly, so this is a placeholder. I know it's a suboptimal
advice, but please make sure to read it, just google '%s license' and you'll
find it. By accepting this, you agree that your distribution won't be
responsible in any way.""" % (mylicense, mylicense,)

        return pkg_licensedata

    def _extract_pkg_metadata_mirror_links(self, sources_list):

        # =mirror://openoffice|link1|link2|link3
        pkg_links = []
        for i in sources_list:
            if i.startswith("mirror://"):
                # parse what mirror I need
                mirrorURI = i.split("/")[2]
                mirrorlist = set(self.get_download_mirrors(mirrorURI))
                pkg_links.append([mirrorURI, mirrorlist])
                # mirrorURI = openoffice and mirrorlist = [link1, link2, link3]

        return pkg_links

    def _extract_pkg_metadata_ebuild_entropy_tag(self, ebuild):
        search_tag = PortagePlugin._ebuild_entries['ebuild_pkg_tag_var']
        # search inside build environment
        ebuild_tag = os.getenv(search_tag, "")
        if ebuild_tag:
            return ebuild_tag

        enc = etpConst['conf_encoding']
        with codecs.open(ebuild, "r", encoding=enc) as f:
            tags = [x.strip() for x in f.readlines() \
                        if x.strip() and x.strip().startswith(search_tag)]
        if not tags:
            return ebuild_tag
        tag = tags[-1]
        tag = tag.split("=")[-1].strip('"').strip("'").strip()

        if not entropy.dep.is_valid_package_tag(tag):
            # invalid
            mytxt = "%s: %s: %s" % (
                bold(_("QA")),
                brown(_("illegal Entropy package tag in ebuild")),
                tag,
            )
            self.__output.output(
                mytxt,
                importance = 0,
                header = red("   ## ")
            )
            return ebuild_tag
        return tag
